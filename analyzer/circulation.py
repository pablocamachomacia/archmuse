"""Análisis de recorridos y circulaciones: modela la vivienda como un grafo
de adyacencias físicas entre habitaciones (dos habitaciones son vecinas si
comparten un tramo de muro — misma detección que
`evaluator._is_adjacent`/`_shared_edge_length`, ya usada por la regla
acústica del Bloque 16) y traza recorridos sobre ese grafo.

Limitación de base, igual que el resto del módulo (ver
`evaluator.get_missing_data_warnings`): el modelo no tiene datos reales de
puertas. Toda adyacencia física (muro compartido) se asume como una posible
conexión de circulación — esto puede INFRAESTIMAR recorridos absurdos (si
dos habitaciones adyacentes en el plano no tienen puerta entre sí en la
realidad, el algoritmo las tratará igualmente como conectadas), nunca
sobreestimarlos, porque las rutas se calculan como el camino MÁS CORTO
disponible en el grafo: si existe una adyacencia directa entre dos
habitaciones, ningún cruce intermedio se marcará como problemático aunque en
la práctica no hubiera puerta ahí.

5 comprobaciones:
1. `_check_absurd_routes` — recorrido dormitorio→baño que cruza una pieza
   social (Salón/Cocina): el ejemplo típico que da el enunciado.
2. `_wrap_oversized_corridor` — NO se recalcula: envuelve
   `UnitScore.circulation_efficiency_result`, ya calculado por
   `evaluator.evaluate_circulation_efficiency` (Bloque 14, mismo umbral del
   15%).
3. `_check_pass_through_rooms` — habitaciones (no etiquetadas como
   circulación) que quedan en el camino más corto entre otras dos piezas
   habitables: actúan como pasillo sin serlo.
4. `_check_bathroom_access` — baños con una adyacencia DIRECTA a Salón/Cocina
   (sin pasillo/vestíbulo intermedio).
5. `_check_evacuation_route` — recorrido más largo (por el grafo, sumando
   distancias centroide-a-centroide reales de cada tramo, no en línea recta)
   desde cualquier pieza habitable hasta el Pasillo (mismo proxy de
   entrada/salida que `evaluator.evaluate_entry_distance`). Distinto de
   `evaluator.evaluate_evacuation_distance` (Bloque 17, que mide la recta
   más corta a cualquier punto del perímetro exterior de la vivienda, sin
   pasar por el grafo de habitaciones) — comparten el mismo umbral legal
   (`MAX_EVACUATION_DISTANCE_M`, CTE DB-SI) pero miden algo distinto: aquí
   sí importa la topología real de circulación interior.

`generate_circulation_svg` dibuja los recorridos como flechas sobre el mismo
layout que usa `plan_svg`/`spatial_quality` (`layout_room_polygons`), en
verde si el recorrido es correcto y en rojo si es problemático.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

from modelo import compat as modelo_compat

from . import adyacencia as ady
from .evaluator import (
    MAX_EVACUATION_DISTANCE_M,
    Unit,
    UnitScore,
    _normalize,
)
from .parser import Room
from .plan_svg import _VIEWBOX_H, _VIEWBOX_MARGIN, _VIEWBOX_W, _exterior_rings, layout_room_polygons

ROUTE_COLOR_OK = "#16A34A"  # verde
ROUTE_COLOR_PROBLEM = "#DC2626"  # rojo

SCORE_IMPACT_ABSURD_ROUTE = 15.0
SCORE_IMPACT_PASS_THROUGH_ROOM = 10.0
SCORE_IMPACT_BATHROOM_ACCESS = 15.0
SCORE_IMPACT_OVERSIZED_CORRIDOR = 10.0
SCORE_IMPACT_EVACUATION = 20.0

_SCORE_IMPACT_BY_TIPO = {
    "recorrido_absurdo": SCORE_IMPACT_ABSURD_ROUTE,
    "espacio_de_paso": SCORE_IMPACT_PASS_THROUGH_ROOM,
    "bano_sin_antesala": SCORE_IMPACT_BATHROOM_ACCESS,
    "pasillo_sobredimensionado": SCORE_IMPACT_OVERSIZED_CORRIDOR,
    "evacuacion": SCORE_IMPACT_EVACUATION,
}

# Etiquetas reconocidas como espacio de circulación/antesala dedicado —
# además de "Pasillo" (la única que usan los planos vistos hasta ahora), se
# reconocen estos sinónimos habituales si el arquitecto los usa en el DXF.
#
# E3 (docs/prd/2026-08-11-e3-clasificacion-circulation.md) — DELIBERADAMENTE
# SIN MIGRAR. Su paridad con el modelo no está demostrada: ningún recinto de
# ejemplo.dxf pertenece a esta familia, y `modelo.constructor.CLASIFICACION`
# no tiene entrada para "ANTESALA". Migrarlo sin datos sería inventar una
# equivalencia, no medirla (E3.1, §1.4 del PRD).
_CIRCULATION_ROOM_PATTERN = re.compile(r"PASILLO|VESTIBULO|DISTRIBUIDOR|RECIBIDOR|ANTESALA")

# E3 — los 4 patrones con paridad demostrada en E3.1 (34/34 sobre ejemplo.dxf,
# cero divergencias) pasan a comparar el tipo que asigna el modelo, vía
# `modelo_compat.tipos_de_unidad`, contra estos conjuntos — en vez de su
# propio regex sobre `room.label`. El mapeo es el del §5 del PRD, literal.
_TIPOS_DORMITORIO: FrozenSet[str] = frozenset({"dormitorio"})
_TIPOS_SALON: FrozenSet[str] = frozenset({"salon", "cocina"})
_TIPOS_BANO_O_ASEO: FrozenSet[str] = frozenset({"bano", "aseo"})
_TIPOS_DESTINO: FrozenSet[str] = frozenset({"salon", "cocina", "dormitorio", "bano", "aseo"})


def _tiene_tipo(room: Room, tipos: Dict[int, FrozenSet[str]], conjunto: FrozenSet[str]) -> bool:
    """¿El tipo (o alguno de los `tipos_ambiguos`) que el modelo asigna a
    `room` cae dentro de `conjunto`? Sustituye a los 4 regex migrados en E3.
    Un recinto sin tipo reconocido (`tipos.get` vacío) no cae en ningún
    conjunto — mismo comportamiento que un regex que no casaba con nada."""
    return bool(tipos.get(id(room), frozenset()) & conjunto)


@dataclass
class CirculationRoute:
    tipo: str  # "recorrido_absurdo" | "espacio_de_paso" | "bano_sin_antesala" | "pasillo_sobredimensionado" | "evacuacion"
    passed: bool
    message: str
    path: List[Room] = field(default_factory=list)  # secuencia de habitaciones del recorrido (>=1)
    metric_value: Optional[float] = None  # metros del recorrido, o ratio del pasillo, según `tipo`

    @property
    def color(self) -> str:
        return ROUTE_COLOR_OK if self.passed else ROUTE_COLOR_PROBLEM

    @property
    def path_labels(self) -> List[str]:
        return [r.label or "(sin etiqueta)" for r in self.path]


@dataclass
class UnitCirculation:
    unit_name: str
    routes: List[CirculationRoute] = field(default_factory=list)
    score_pct: float = 100.0


# ---------------------------------------------------------------------------
# Grafo de adyacencias físicas
# ---------------------------------------------------------------------------

# El grafo vive ahora en `analyzer/adyacencia.py`, para que `evaluator.py`
# pueda medir recorridos reales sin duplicarlo (este módulo importa
# `evaluator`, así que el grafo no podía quedarse aquí). Se conservan los
# nombres locales para no tocar el resto del archivo: mismo código, misma
# tolerancia, mismos resultados — el refactor se hizo con la salida de
# `ejemplo.dxf` congelada y comparada antes y después.
_AdjacencyGraph = ady.Grafo
WALL_GAP_TOLERANCE_M = ady.WALL_GAP_TOLERANCE_M
_rooms_are_connected = ady.rooms_are_connected
_bfs_path = ady.bfs_path
_weighted_shortest_path = ady.weighted_shortest_path


def _build_adjacency_graph(unit: Unit) -> _AdjacencyGraph:
    """Grafo de adyacencias de una vivienda.

    **E1.13 — primer consumidor del modelo común.** La topología se calcula
    ahora en `modelo/`, que es el único sitio donde se decide qué significa
    que dos recintos estén juntos. Antes había cinco criterios repartidos por
    el repositorio con cuatro umbrales distintos
    (`docs/brain/KNOWLEDGE_GRAPH.md` §1); éste es el primer módulo que deja de
    tener el suyo.

    La forma del resultado no cambia —sigue siendo el `dict` de
    `analyzer/adyacencia.py`, con los mismos objetos `Room`— para que el resto
    de este fichero no se entere. Y el umbral tampoco: el modelo lee
    `adyacencia.WALL_GAP_TOLERANCE_M`, que sigue siendo la única definición
    del número en todo el repositorio.

    Comprobado equivalente, no supuesto: mismas aristas, mismos pesos y el
    mismo **orden de vecinos** —que es lo que decide qué camino gana cuando
    dos empatan— en las seis viviendas de `ejemplo.dxf`
    (`tests/test_modelo_compat.py`), y las 12 comprobaciones de circulación
    idénticas (`tests/fixtures/golden/G4_circulacion.json`).

    **Sin interruptor** (E1.15). Durante E1.13 hubo un `ARCHMUSE_MODELO=0` que
    devolvía el camino anterior, y se retiró en cuanto los dos caminos
    quedaron probados equivalentes: mantener dos implementaciones de la misma
    topología «por si acaso» es precisamente la duplicación que este modelo
    existe para eliminar, y la que se pudre primero porque nadie ejecuta la
    rama apagada. La vuelta atrás, si hiciera falta, es un `git revert` de un
    fichero, no una variable de entorno.
    """
    return modelo_compat.grafo_de_adyacencia(unit)


# ---------------------------------------------------------------------------
# 1. Recorridos absurdos: dormitorio → baño cruzando una pieza social
# ---------------------------------------------------------------------------


def _check_absurd_routes(unit: Unit, graph: _AdjacencyGraph,
                         tipos: Dict[int, FrozenSet[str]]) -> List[CirculationRoute]:
    dormitorios = [r for r in unit.rooms if _tiene_tipo(r, tipos, _TIPOS_DORMITORIO)]
    banos = [r for r in unit.rooms if _tiene_tipo(r, tipos, _TIPOS_BANO_O_ASEO)]

    routes: List[CirculationRoute] = []
    for dorm in dormitorios:
        for bano in banos:
            path = _bfs_path(graph, dorm, bano)
            if path is None:
                continue  # no conectados en el grafo de adyacencias (dato insuficiente para evaluar)

            crossed_social = [r for r in path[1:-1] if _tiene_tipo(r, tipos, _TIPOS_SALON)]
            if crossed_social:
                culprit = crossed_social[0]
                routes.append(CirculationRoute(
                    tipo="recorrido_absurdo",
                    passed=False,
                    message=(
                        f"{dorm.label} → {bano.label}: el recorrido cruza {culprit.label} — "
                        "hay que atravesar una pieza social para llegar al baño"
                    ),
                    path=path,
                ))
            else:
                routes.append(CirculationRoute(
                    tipo="recorrido_absurdo",
                    passed=True,
                    message=f"{dorm.label} → {bano.label}: recorrido directo, sin cruzar piezas sociales",
                    path=path,
                ))
    return routes


# ---------------------------------------------------------------------------
# 2. Pasillos sobredimensionados — envuelve el resultado ya existente
# ---------------------------------------------------------------------------


def _wrap_oversized_corridor(unit_score: UnitScore) -> Optional[CirculationRoute]:
    """No recalcula nada: envuelve `unit_score.circulation_efficiency_result`
    (`evaluator.evaluate_circulation_efficiency`, Bloque 14, umbral del 15%)
    como una `CirculationRoute` de un único nodo (el/los Pasillo de la
    vivienda), para poder resaltarlo junto al resto de recorridos."""
    ce = unit_score.circulation_efficiency_result
    if ce is None:
        return None
    pasillos = [r for r in unit_score.unit.rooms if r.label and "PASILLO" in _normalize(r.label)]
    return CirculationRoute(
        tipo="pasillo_sobredimensionado",
        passed=ce.passed,
        message=ce.message,
        path=pasillos,
        metric_value=ce.ratio,
    )


# ---------------------------------------------------------------------------
# 3. Espacios de paso: habitaciones no-circulación forzadas como corredor
# ---------------------------------------------------------------------------


def _check_pass_through_rooms(unit: Unit, graph: _AdjacencyGraph,
                              tipos: Dict[int, FrozenSet[str]]) -> List[CirculationRoute]:
    destinations = [r for r in unit.rooms if _tiene_tipo(r, tipos, _TIPOS_DESTINO)]

    flagged: Dict[int, Room] = {}
    for i in range(len(destinations)):
        for j in range(i + 1, len(destinations)):
            path = _bfs_path(graph, destinations[i], destinations[j])
            if not path:
                continue
            for room in path[1:-1]:
                # SIN MIGRAR a propósito (E3, ver cabecera de _CIRCULATION_ROOM_PATTERN).
                if room.label and _CIRCULATION_ROOM_PATTERN.search(_normalize(room.label)):
                    continue  # es un pasillo/vestíbulo: función esperada, no un espacio de paso "accidental"
                flagged[id(room)] = room

    return [
        CirculationRoute(
            tipo="espacio_de_paso",
            passed=False,
            message=(
                f"{room.label or '(sin etiqueta)'}: funciona como paso obligado entre otras "
                "estancias sin ser un espacio de circulación dedicado"
            ),
            path=[room],
        )
        for room in flagged.values()
    ]


# ---------------------------------------------------------------------------
# 4. Acceso a baños: sin antesala si la única vía es directa desde el salón
# ---------------------------------------------------------------------------


def _check_bathroom_access(unit: Unit, graph: _AdjacencyGraph,
                           tipos: Dict[int, FrozenSet[str]]) -> List[CirculationRoute]:
    banos = [r for r in unit.rooms if _tiene_tipo(r, tipos, _TIPOS_BANO_O_ASEO)]

    routes: List[CirculationRoute] = []
    for bano in banos:
        neighbors = graph.get(id(bano), [])
        direct_social = [n for n, _dist in neighbors if _tiene_tipo(n, tipos, _TIPOS_SALON)]
        if direct_social:
            salon = direct_social[0]
            routes.append(CirculationRoute(
                tipo="bano_sin_antesala",
                passed=False,
                message=f"{bano.label}: acceso directo desde {salon.label}, sin antesala/pasillo intermedio",
                path=[salon, bano],
            ))
    return routes


# ---------------------------------------------------------------------------
# 5. Recorrido de evacuación más largo hasta el Pasillo (grafo, no recta)
# ---------------------------------------------------------------------------

# Union de _TIPOS_SALON y _TIPOS_DORMITORIO — mismo conjunto que representaba
# la lista original [_SALON_PATTERN, _DORMITORIO_ANY_PATTERN].
_TIPOS_DESTINO_EVACUACION: FrozenSet[str] = _TIPOS_SALON | _TIPOS_DORMITORIO


def _check_evacuation_route(unit: Unit, graph: _AdjacencyGraph,
                            tipos: Dict[int, FrozenSet[str]]) -> Optional[CirculationRoute]:
    # SIN MIGRAR a propósito: no es uno de los 5 patrones de circulation.py
    # (E3 sólo migra _DORMITORIO_ANY_PATTERN, _SALON_PATTERN,
    # _BANO_OR_ASEO_PATTERN y _DESTINATION_PATTERN — ver PRD §4).
    pasillo = next((r for r in unit.rooms if r.label and "PASILLO" in _normalize(r.label)), None)
    if pasillo is None:
        return None  # sin pasillo, no evaluable (misma convención que evaluator.evaluate_entry_distance)

    destinations = [r for r in unit.rooms if _tiene_tipo(r, tipos, _TIPOS_DESTINO_EVACUACION)]

    worst_path: Optional[List[Room]] = None
    worst_distance = -1.0
    for room in destinations:
        path, distance = _weighted_shortest_path(graph, room, pasillo)
        if path is None:
            continue
        if distance > worst_distance:
            worst_distance = distance
            worst_path = path

    if worst_path is None:
        return None

    passed = worst_distance <= MAX_EVACUATION_DISTANCE_M
    origin = worst_path[0]
    return CirculationRoute(
        tipo="evacuacion",
        passed=passed,
        message=(
            f"Recorrido de evacuación más largo: {origin.label} → {pasillo.label}, "
            f"{worst_distance:.1f}m" + ("" if passed else f" — supera el máximo de {MAX_EVACUATION_DISTANCE_M}m (CTE DB-SI)")
        ),
        path=worst_path,
        metric_value=worst_distance,
    )


# ---------------------------------------------------------------------------
# Orquestación y puntuación
# ---------------------------------------------------------------------------


def evaluate_circulation(unit_score: UnitScore) -> UnitCirculation:
    unit = unit_score.unit
    graph = _build_adjacency_graph(unit)
    # E3 — el tipo de cada Room, según el modelo (docs/prd/2026-08-11-e3-clasificacion-circulation.md).
    # Se calcula una vez aquí y se pasa a las 4 comprobaciones migradas.
    tipos = modelo_compat.tipos_de_unidad(unit)

    routes: List[CirculationRoute] = []
    routes.extend(_check_absurd_routes(unit, graph, tipos))
    routes.extend(_check_pass_through_rooms(unit, graph, tipos))
    routes.extend(_check_bathroom_access(unit, graph, tipos))

    corridor_route = _wrap_oversized_corridor(unit_score)
    if corridor_route is not None:
        routes.append(corridor_route)

    evacuation_route = _check_evacuation_route(unit, graph, tipos)
    if evacuation_route is not None:
        routes.append(evacuation_route)

    penalty = sum(_SCORE_IMPACT_BY_TIPO[r.tipo] for r in routes if not r.passed)
    score_pct = max(0.0, 100.0 - penalty)

    return UnitCirculation(unit_name=unit.name, routes=routes, score_pct=score_pct)


# ---------------------------------------------------------------------------
# Visualización: flechas sobre el plano, verde = correcto / rojo = problemático
# ---------------------------------------------------------------------------


def _svg_defs(colors) -> str:
    markers = []
    for color in colors:
        marker_id = f"arrow-{color.lstrip('#')}"
        markers.append(
            f'<marker id="{marker_id}" viewBox="0 0 10 10" refX="8" refY="5" '
            f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
        )
    return f"<defs>{''.join(markers)}</defs>"


def generate_circulation_svg(unit_score: UnitScore, circulation: UnitCirculation) -> str:
    """Dibuja el mismo plano posicionado que `plan_svg.generate_plan_svg`
    (reutilizando `layout_room_polygons`) con contornos neutros, y encima
    una flecha por recorrido de `circulation.routes`: una polilínea entre
    los centroides (ya posicionados) de las habitaciones de `route.path`,
    verde si `passed` o roja si no. Los recorridos de un único nodo (Bloque
    2, pasillo sobredimensionado) se marcan con un círculo en vez de una
    flecha, al no tener origen/destino."""
    rooms = unit_score.unit.rooms
    if not rooms:
        return ""

    layout = layout_room_polygons(unit_score)
    positioned_by_id = {id(room): polygon for room, polygon in layout}

    bounds = [polygon.bounds for _room, polygon in layout]
    minx = min(b[0] for b in bounds)
    miny = min(b[1] for b in bounds)
    maxx = max(b[2] for b in bounds)
    maxy = max(b[3] for b in bounds)
    width_m = max(maxx - minx, 0.01)
    height_m = max(maxy - miny, 0.01)

    avail_w = _VIEWBOX_W - 2 * _VIEWBOX_MARGIN
    avail_h = _VIEWBOX_H - 2 * _VIEWBOX_MARGIN
    scale = min(avail_w / width_m, avail_h / height_m)
    drawn_w = width_m * scale
    drawn_h = height_m * scale
    offset_x = (_VIEWBOX_W - drawn_w) / 2
    offset_y = (_VIEWBOX_H - drawn_h) / 2

    def to_screen(x: float, y: float) -> Tuple[float, float]:
        return offset_x + (x - minx) * scale, offset_y + (maxy - y) * scale

    parts = [f'<svg viewBox="0 0 {_VIEWBOX_W} {_VIEWBOX_H}" xmlns="http://www.w3.org/2000/svg">']

    for _room, polygon in layout:
        for xs, ys in _exterior_rings(polygon):
            points = " ".join(f"{sx:.2f},{sy:.2f}" for sx, sy in (to_screen(x, y) for x, y in zip(xs, ys)))
            parts.append(f'<polygon points="{points}" fill="#F4F5F7" stroke="#9AA3B2" stroke-width="1.0"/>')

    colors_used = {r.color for r in circulation.routes}
    parts.append(_svg_defs(colors_used))

    for route in circulation.routes:
        positioned_path = [positioned_by_id.get(id(r)) for r in route.path]
        if not positioned_path or any(p is None for p in positioned_path):
            continue

        if len(positioned_path) == 1:
            cx, cy = to_screen(positioned_path[0].centroid.x, positioned_path[0].centroid.y)
            parts.append(
                f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="16" fill="none" '
                f'stroke="{route.color}" stroke-width="3" opacity="0.85"/>'
            )
            continue

        screen_points = [to_screen(p.centroid.x, p.centroid.y) for p in positioned_path]
        points_str = " ".join(f"{x:.2f},{y:.2f}" for x, y in screen_points)
        marker_id = f"arrow-{route.color.lstrip('#')}"
        parts.append(
            f'<polyline points="{points_str}" fill="none" stroke="{route.color}" '
            f'stroke-width="2.5" marker-end="url(#{marker_id})" opacity="0.85"/>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Serialización JSON (para la API REST, ver analyzer/api_serializer.py)
# ---------------------------------------------------------------------------


def _serialize_route(route: CirculationRoute) -> dict:
    return {
        "tipo": route.tipo,
        "correcto": route.passed,
        "mensaje": route.message,
        "color": route.color,
        "recorrido": route.path_labels,
        "valor": round(route.metric_value, 2) if route.metric_value is not None else None,
    }


def serialize_unit_circulation(unit_score: UnitScore, circulation: UnitCirculation) -> dict:
    return {
        "vivienda": circulation.unit_name,
        "puntuacion": round(circulation.score_pct),
        "recorridos": [_serialize_route(r) for r in circulation.routes],
        "svg": generate_circulation_svg(unit_score, circulation),
    }
