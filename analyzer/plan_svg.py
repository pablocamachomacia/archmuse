"""Visualización del plano analizado: SVG puro escrito a mano, una fila por
vivienda — sin matplotlib ni ninguna otra librería de gráficos.

Cada vivienda se escala a un viewBox fijo `0 0 800 600` (preservando su
aspect ratio real, sin distorsión) y se dibuja como texto SVG plano:
- cada habitación es un `<polygon>` coloreado según su TIPO de uso
  (salón/cocina, dormitorio, baño, terraza, tendedero) con una paleta
  pastel muy suave; los muros entre habitaciones son el trazo (`stroke`) de
  ese mismo polígono, en un gris oscuro neutro;
- las habitaciones con algún problema detectado llevan un trazo rojo y un
  leve tinte rojizo en el relleno, en vez del gris/pastel normal;
- cada habitación lleva un atributo `data-room="<índice>"` en su `<g>`
  envolvente, para que el frontend (SPA) pueda enlazar el hover del ratón
  con los datos de esa habitación (nombre, área, problemas) y mostrar un
  tooltip flotante propio — el SVG en sí no lleva `<title>` nativo, ese
  tooltip se construye en JavaScript a partir del JSON de la API;
- nombre + superficie centrados dentro de la habitación, en un tamaño de
  fuente proporcional a su área — y solo si el texto cabe dentro de su
  propio contorno; si no cabe, se muestra solo la superficie, y si ni eso
  cabe, no se dibuja texto;
- una pequeña flecha de norte (rota según `norte_grados`) en la esquina.

`generate_plan_svg` construye el SVG de una única vivienda — usada tanto por
`render_plan_section` (informe HTML del CLI) como por `api_serializer`
(API JSON de la SPA).
"""
from __future__ import annotations

import html
import math
import re
from typing import Dict, List, Tuple

from shapely.affinity import translate
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from .evaluator import (
    DORMITORIO_PATTERNS,
    UnitScore,
    _bounding_sides,
    _normalize,
    evaluate_proportions,
    evaluate_room,
)
from .parser import Room

_SCORE_BADGE_CLASS = {"verde": "badge-green", "amarillo": "badge-yellow", "rojo": "badge-red"}

# Paleta por tipo de habitación (pasteles muy suaves, arquitectónicos). La
# clave (p. ej. "dormitorio") también se expone en el JSON de la API
# (`api_serializer`) para que el frontend pueda mostrar un icono por tipo.
_ROOM_TYPES = [
    ("salon_cocina", re.compile(r"SALON|COCINA"), "#d4edda"),
    ("dormitorio", re.compile(r"DORMITORIO"), "#dce8f5"),
    ("bano", re.compile(r"BANO|ASEO"), "#fdf3e3"),
    ("terraza", re.compile(r"TERRAZA"), "#fce8d5"),
    ("tendedero", re.compile(r"TENDEDERO"), "#ede8f5"),
]
_NEUTRAL_TYPE = "otro"
_NEUTRAL_FILL = "#E9EAEE"

# Lienzo: viewBox fijo, cada vivienda se escala a él por separado
# preservando su aspect ratio real (nunca se distorsiona la geometría). El
# SVG no pinta su propio fondo (sin `<rect>` de fondo): lo deja transparente
# a propósito para que el contenedor HTML que lo envuelve pueda mostrar
# detrás su propia textura (p. ej. la cuadrícula de papel de arquitecto de
# la SPA); el informe HTML del CLI simplemente le pone un fondo oscuro liso
# al contenedor, con el mismo resultado visual.
_VIEWBOX_W = 800
_VIEWBOX_H = 600
_VIEWBOX_MARGIN = 40

# El SVG se inserta inline en el DOM de la SPA (nunca como <img> ni
# background-image), así que sus atributos de presentación (`stroke`,
# `fill` de texto) pueden referenciar directamente las custom properties
# del tema claro/oscuro — el navegador las resuelve igual que en CSS. Esto
# NO vale para `fill` de habitación (mezclado a mano en `_blend_hex`, que
# hace aritmética de bytes sobre el hex): esos siguen siendo hex reales,
# sin tocar, tal como pide el enunciado ("los colores de fondo... están
# bien, solo ajusta...").
_WALL_COLOR = "var(--border)"
_WALL_STROKE_WIDTH = 1.0
# Envolvente: contorno construido de la vivienda (§5.2 del PRD de
# legibilidad). MISMO color que las particiones, a propósito — en un plano la
# jerarquía la marca el GROSOR, no el color; dos tonos distintos para muro
# exterior e interior es lenguaje de infografía, no de arquitectura.
_ENVELOPE_STROKE_WIDTH = 2.2
_TEXT_COLOR = "var(--text-primary)"  # línea del nombre de la habitación
_TEXT_COLOR_SECONDARY = "var(--text-secondary)"  # línea de la superficie (m²), debajo
_NORTH_ARROW_COLOR = "var(--text-tertiary)"

# Hex real (no var()): sigue alimentando `_blend_hex` para teñir el relleno
# de las habitaciones con problemas, aritmética que no entiende `var(...)`.
_PROBLEM_EDGE_COLOR = "#EF4444"
# Trazo de habitación con problema: si no se refina por severidad desde el
# frontend (ver `static/index.html`, que sí conoce CRITICO/IMPORTANTE de
# `calidad_espacial`/`circulacion` además de `evaluator.py`), este es el
# color por defecto — mismo tono "crítico" que ya usaba `_PROBLEM_EDGE_COLOR`.
_PROBLEM_STROKE_COLOR = "var(--color-critical)"
_PROBLEM_STROKE_WIDTH = 1.5
_PROBLEM_TINT = 0.22  # fracción de mezcla del rojo en el relleno, sutil

_FONT_FAMILY = "Inter, sans-serif"
_FONT_MIN_PX = 9.0
_FONT_MAX_PX = 13.0
_FONT_AREA_MIN_M2 = 3.0
_FONT_AREA_MAX_M2 = 25.0

# Estimaciones (sin motor de métricas de fuente) para decidir si el texto
# cabe dentro del propio contorno de la habitación antes de dibujarlo.
_CHAR_WIDTH_FACTOR = 0.58
_LINE_HEIGHT_FACTOR = 1.2
_FIT_MARGIN = 0.86

# Una vivienda puede tener sus habitaciones repartidas en varios grupos
# físicamente separados en el DXF (p. ej. la zona de noche y una terraza al
# otro lado de un patio). Dos habitaciones se consideran del mismo grupo si
# la distancia entre sus contornos no supera este umbral (metros).
_CLUSTER_GAP_THRESHOLD_M = 2.0

# Si el hueco entre grupos supera esta fracción del tamaño total de la
# vivienda, ya no se intenta compactar conservando las posiciones relativas
# reales: se reorganizan directamente todas las habitaciones en una
# cuadrícula limpia (prioriza claridad visual sobre precisión geográfica).
_FLOATING_GAP_RATIO = 0.20

# Hueco dejado entre grupos compactados, como fracción del tamaño TOTAL de
# la vivienda (no del tamaño de cada grupo) — así se mantiene discreto sea
# cual sea el tamaño relativo de los grupos.
_COMPACT_GAP_FRAC = 0.05
# Relleno alrededor de cada habitación en su celda de la cuadrícula, como
# fracción del lado más largo de la habitación más grande.
_GRID_CELL_PADDING_FRAC = 0.3


def _blend_hex(base_hex: str, tint_hex: str, t: float) -> str:
    """Mezcla `base_hex` con `tint_hex` en una fracción `t` (0-1)."""
    base = tuple(int(base_hex[i : i + 2], 16) for i in (1, 3, 5))
    tint = tuple(int(tint_hex[i : i + 2], 16) for i in (1, 3, 5))
    mixed = tuple(round(base[i] * (1 - t) + tint[i] * t) for i in range(3))
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def room_type(room: Room) -> str:
    """Tipo de habitación (p. ej. "dormitorio", "bano", "otro") según su
    etiqueta. Se usa tanto para el color de relleno del plano como para el
    icono por tipo del panel de detalle en la SPA."""
    if room.label:
        normalized = _normalize(room.label)
        for key, pattern, _color in _ROOM_TYPES:
            if pattern.search(normalized):
                return key
    return _NEUTRAL_TYPE


def _room_type_fill(room: Room) -> str:
    """Color de relleno según el tipo de habitación (por su etiqueta), no
    según su valoración de calidad — así el plano se lee por uso, como un
    plano de arquitectura real."""
    if room.label:
        normalized = _normalize(room.label)
        for _key, pattern, color in _ROOM_TYPES:
            if pattern.search(normalized):
                return color
    return _NEUTRAL_FILL


def room_problems(room: Room, unit_score: UnitScore) -> List[str]:
    """Mensajes de las comprobaciones que esta habitación concreta incumple
    (superficie mínima, proporción, orientación, jerarquía de dormitorios si
    aplica). La eficiencia útil/total es una métrica de vivienda completa y
    no se atribuye a una sola habitación."""
    problems: List[str] = []

    for r in evaluate_room(room):
        if not r.passed:
            problems.append(r.message)

    for p in evaluate_proportions([room]):
        if not p.passed:
            problems.append(p.message)

    for o in unit_score.orientation_results:
        if o.room is room and o.rating == "penalizada":
            problems.append(o.message)

    for nl in unit_score.natural_light_results:
        if nl.room is room and not nl.passed:
            problems.append(nl.message)

    for cw in unit_score.corridor_width_results:
        if cw.room is room and not cw.passed:
            problems.append(cw.message)

    for sh in unit_score.solar_hours_results:
        if sh.room is room and sh.rating == "deficiente":
            problems.append(sh.message)

    for ed in unit_score.entry_distance_results:
        if ed.room is room and not ed.passed:
            problems.append(ed.message)

    for rd in unit_score.room_depth_results:
        if rd.room is room and not rd.passed:
            problems.append(rd.message)

    for nf in unit_score.natural_light_factor_results:
        if nf.room is room and not nf.passed:
            problems.append(nf.message)

    for aa in unit_score.acoustic_adjacency_results:
        if aa.room is room and not aa.passed:
            problems.append(aa.message)

    for ae in unit_score.acoustic_exposure_results:
        if ae.room is room:
            problems.append(ae.message)

    # `evacuation_distance_results` no resalta la habitación desde el
    # Bloque B (DB-SI_REVIEW.md §3.2, ficha C09): es una métrica
    # informativa de circulación, no un incumplimiento verificado.

    for bt in unit_score.bathroom_turning_space_results:
        if bt.room is room and not bt.passed:
            problems.append(bt.message)

    for mw in unit_score.minimum_room_width_results:
        if mw.room is room and not mw.passed:
            problems.append(mw.message)

    for wo in unit_score.window_opening_results:
        if wo.room is room and not wo.passed:
            problems.append(wo.message)

    for bm in unit_score.bedroom_minimum_area_results:
        if bm.room is room and not bm.passed:
            problems.append(bm.message)

    if room.label:
        normalized = _normalize(room.label)
        for name, pattern in DORMITORIO_PATTERNS:
            if pattern.search(normalized):
                for h in unit_score.hierarchy_results:
                    if (h.higher_name == name or h.lower_name == name) and not h.passed:
                        problems.append(h.message)

    return problems


def exterior_rings(polygon):
    """Anillos exteriores (xs, ys) del polígono, contemplando el caso (raro)
    de un MultiPolygon.

    Público (tarea 14): lo importan `circulation.py` y `spatial_quality.py`,
    y un nombre privado importado desde otro módulo es una contradicción."""
    if polygon.geom_type == "Polygon":
        return [polygon.exterior.xy]
    if polygon.geom_type == "MultiPolygon":
        return [g.exterior.xy for g in polygon.geoms]
    return []


def svg_points(xs, ys, to_screen) -> str:
    """El atributo `points` de un `<polygon>` SVG para el anillo `(xs, ys)`,
    con cada vértice pasado por `to_screen` y redondeado a 2 decimales.

    **Por qué existe** (tarea 14 del `REFACTOR_MASTERPLAN.md`). Esta línea
    estaba copiada literalmente cuatro veces: dos en este módulo, una en
    `circulation.py` y una en `spatial_quality.py`. Cuatro copias de una
    conversión no son cuatro sitios donde leer lo mismo, son cuatro sitios
    donde arreglarlo la próxima vez — y la tarea 7, que acaba de añadir
    `strict=True`, tuvo que tocar las cuatro para decir una sola cosa.

    Los 2 decimales no son cosméticos: son la precisión del SVG y salen en el
    fixture de cualquier comparación de plano. Cambiarlos aquí los cambia en
    los tres generadores a la vez, que es exactamente el punto.

    `strict=True` documenta que un anillo tiene tantas X como Y. Con anillos
    de `shapely` no puede fallar (los dos arrays salen del mismo
    `CoordinateSequence`); queda por si algún día entran por otra vía.
    """
    return " ".join(
        f"{sx:.2f},{sy:.2f}"
        for sx, sy in (to_screen(x, y) for x, y in zip(xs, ys, strict=True))
    )


def calcular_transformador_de_pantalla(minx: float, miny: float, maxx: float, maxy: float):
    """La otra mitad de la tarea 14, la que quedaba: el cálculo de `scale`,
    `offset_x`, `offset_y` y el propio cierre `to_screen` -- que encaja un
    bounding box en metros dentro del `viewBox` fijo con margen (`_VIEWBOX_W`,
    `_VIEWBOX_H`, `_VIEWBOX_MARGIN`) -- también estaba copiado tal cual en
    `generate_plan_svg` (este módulo), `generate_circulation_svg`
    (`circulation.py`) y `generate_spatial_quality_svg`
    (`spatial_quality.py`). `svg_points` ya resolvió la conversión de un
    anillo; esto resuelve cómo se construye el `to_screen` que le pasan los
    tres.

    Devuelve `(to_screen, scale, offset_x, offset_y)` -- los tres generadores
    sólo usan `to_screen`, salvo `generate_plan_svg`, que además publica
    `scale`/`offset_x`/`offset_y` como `data-escala`/`data-ox`/`data-oy` para
    que el frontend pueda invertir la transformación.
    """
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
        # El eje Y del DXF/shapely crece hacia arriba; el de SVG, hacia
        # abajo -- se invierte aquí para que "arriba" del plano quede arriba
        # en pantalla.
        return offset_x + (x - minx) * scale, offset_y + (maxy - y) * scale

    return to_screen, scale, offset_x, offset_y


def _envelope_rings(layout: List[Tuple[Room, BaseGeometry]]):
    """Anillos de la envolvente de la vivienda: la unión de todos los
    polígonos de habitación, de la que se toman tanto el contorno exterior
    como los interiores (patios).

    El plano NO tiene muros: `parser.py` lee una sola capa del DXF y una
    habitación es solo su polígono, así que lo que parece un muro es el borde
    compartido de dos habitaciones. La unión es lo más cercano al perímetro
    construido que se puede deducir del dato disponible, y basta para lo único
    que se pretende: que el edificio se lea antes que sus divisiones.

    Habitaciones que se tocan por una arista se funden en un solo polígono;
    las que no, quedan como piezas sueltas del MultiPolygon y cada una aporta
    su anillo. Los patios son anillos interiores y también son envolvente: por
    dentro de un patio se está fuera de la vivienda."""
    polygons = [polygon for _room, polygon in layout if not polygon.is_empty]
    if not polygons:
        return []

    union = unary_union(polygons)
    piezas = list(union.geoms) if union.geom_type.startswith("Multi") else [union]

    rings = []
    for pieza in piezas:
        if pieza.is_empty or pieza.geom_type != "Polygon":
            continue
        rings.append(pieza.exterior.xy)
        rings.extend(interior.xy for interior in pieza.interiors)
    return rings


def _envelope_svg(layout: List[Tuple[Room, BaseGeometry]], to_screen) -> str:
    """Envolvente como grupo propio, dibujado DESPUÉS de las habitaciones
    para que su trazo quede por encima del de las particiones.

    `pointer-events="none"` no es opcional: sin él, este grupo se pone encima
    de las habitaciones y se queda el clic, el hover y las coordenadas. Ya ha
    pasado dos veces en este proyecto (con las etiquetas `<text>` y con los
    polígonos sin relleno), así que aquí va desde el principio."""
    rings = _envelope_rings(layout)
    if not rings:
        return ""

    partes = ['<g class="plan-envolvente" pointer-events="none">']
    for xs, ys in rings:
        points = svg_points(xs, ys, to_screen)
        partes.append(
            f'<polygon points="{points}" fill="none" stroke="{_WALL_COLOR}" '
            f'stroke-width="{_ENVELOPE_STROKE_WIDTH}" stroke-linejoin="round"/>'
        )
    partes.append("</g>")
    return "".join(partes)


def _cluster_rooms(rooms: List[Room], gap_threshold_m: float) -> List[List[Room]]:
    """Agrupa habitaciones en grupos conexos: dos habitaciones están en el
    mismo grupo si la distancia entre sus contornos es <= `gap_threshold_m`
    (directamente o a través de otras habitaciones intermedias). Sirve para
    detectar si una vivienda está partida en varios bloques físicamente
    separados en el DXF."""
    n = len(rooms)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    for i in range(n):
        for j in range(i + 1, n):
            if rooms[i].polygon.distance(rooms[j].polygon) <= gap_threshold_m:
                union(i, j)

    groups: Dict[int, List[Room]] = {}
    for i, room in enumerate(rooms):
        groups.setdefault(find(i), []).append(room)
    return list(groups.values())


def _cluster_bounds(cluster: List[Room]) -> Tuple[float, float, float, float]:
    bounds = [room.polygon.bounds for room in cluster]
    return (
        min(b[0] for b in bounds),
        min(b[1] for b in bounds),
        max(b[2] for b in bounds),
        max(b[3] for b in bounds),
    )


def _max_cluster_gap(clusters: List[List[Room]]) -> Tuple[float, float]:
    """Mayor hueco real entre grupos adyacentes (a lo largo del eje en el
    que más se separan) y el tamaño total de la vivienda — para decidir si
    ese hueco es demasiado grande para compactarlo con sentido."""
    all_bounds = [room.polygon.bounds for cluster in clusters for room in cluster]
    minx = min(b[0] for b in all_bounds)
    miny = min(b[1] for b in all_bounds)
    maxx = max(b[2] for b in all_bounds)
    maxy = max(b[3] for b in all_bounds)
    total_size = max(maxx - minx, maxy - miny, 0.01)

    if len(clusters) <= 1:
        return 0.0, total_size

    cluster_bounds = [_cluster_bounds(c) for c in clusters]
    cxs = [(b[0] + b[2]) / 2 for b in cluster_bounds]
    cys = [(b[1] + b[3]) / 2 for b in cluster_bounds]
    vertical = (max(cys) - min(cys)) >= (max(cxs) - min(cxs))

    if vertical:
        ordered = sorted(cluster_bounds, key=lambda b: -(b[1] + b[3]) / 2)
        gaps = [ordered[i][1] - ordered[i + 1][3] for i in range(len(ordered) - 1)]
    else:
        ordered = sorted(cluster_bounds, key=lambda b: (b[0] + b[2]) / 2)
        gaps = [ordered[i + 1][0] - ordered[i][2] for i in range(len(ordered) - 1)]

    max_gap = max((g for g in gaps), default=0.0)
    return max(max_gap, 0.0), total_size


def _compact_clusters(clusters: List[List[Room]], total_size: float) -> List[Tuple[Room, BaseGeometry]]:
    """Empaqueta los grupos desconectados a lo largo de su eje de mayor
    separación, con un hueco pequeño entre ellos (una fracción del tamaño
    total de la vivienda, no del tamaño de cada grupo, para que el hueco se
    mantenga visualmente discreto sea cual sea el tamaño de los grupos) —
    conserva la disposición real de las habitaciones dentro de cada grupo
    (solo se traslada el grupo en bloque, nunca se rota ni se distorsiona).
    Solo se llama con 2 o más grupos; `_layout_rooms` resuelve el caso de un
    único grupo devolviendo directamente las posiciones reales."""
    infos = []
    for cluster in clusters:
        minx, miny, maxx, maxy = _cluster_bounds(cluster)
        infos.append({
            "rooms": cluster, "minx": minx, "miny": miny, "maxx": maxx, "maxy": maxy,
            "w": maxx - minx, "h": maxy - miny, "cx": (minx + maxx) / 2, "cy": (miny + maxy) / 2,
        })

    vertical = (max(c["cy"] for c in infos) - min(c["cy"] for c in infos)) >= \
        (max(c["cx"] for c in infos) - min(c["cx"] for c in infos))
    order = sorted(infos, key=(lambda c: -c["cy"]) if vertical else (lambda c: c["cx"]))

    gap = max(total_size * _COMPACT_GAP_FRAC, 0.01)

    transformed: List[Tuple[Room, BaseGeometry]] = []
    cursor = 0.0
    for c in order:
        if vertical:
            dy = cursor - c["maxy"]
            dx = -c["cx"]
            cursor -= c["h"] + gap
        else:
            dx = cursor - c["minx"]
            dy = -c["cy"]
            cursor += c["w"] + gap
        for room in c["rooms"]:
            transformed.append((room, translate(room.polygon, xoff=dx, yoff=dy)))
    return transformed


def _grid_layout(rooms: List[Room]) -> List[Tuple[Room, BaseGeometry]]:
    """Coloca cada habitación en su propia celda de una cuadrícula limpia,
    conservando su forma y superficie reales pero ignorando su posición
    original en el DXF — para viviendas cuyas habitaciones están demasiado
    dispersas para que una vista "real" tenga sentido."""
    if not rooms:
        return []

    cols = max(1, math.ceil(math.sqrt(len(rooms))))
    dims = [room.polygon.bounds for room in rooms]
    max_w = max(b[2] - b[0] for b in dims)
    max_h = max(b[3] - b[1] for b in dims)
    cell_w = max_w * (1 + _GRID_CELL_PADDING_FRAC)
    cell_h = max_h * (1 + _GRID_CELL_PADDING_FRAC)

    transformed: List[Tuple[Room, BaseGeometry]] = []
    for i, room in enumerate(rooms):
        row, col = divmod(i, cols)
        minx, miny, maxx, maxy = room.polygon.bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        target_cx = col * cell_w + cell_w / 2
        target_cy = -row * cell_h - cell_h / 2
        transformed.append((room, translate(room.polygon, xoff=target_cx - cx, yoff=target_cy - cy)))
    return transformed


def _layout_rooms(rooms: List[Room]) -> Tuple[List[Tuple[Room, BaseGeometry]], bool]:
    """Decide cómo posicionar las habitaciones de una vivienda para el
    plano: posiciones reales si forman un solo bloque, un empaquetado
    compacto (conservando cada bloque) si están en varios grupos con un
    hueco moderado entre ellos, o una cuadrícula limpia si el hueco es
    excesivo (> `_FLOATING_GAP_RATIO` del tamaño total). Devuelve la lista
    (habitación, polígono ya posicionado) y si se usó la cuadrícula (en
    cuyo caso ya no tiene sentido mostrar la flecha de norte)."""
    clusters = _cluster_rooms(rooms, _CLUSTER_GAP_THRESHOLD_M)
    if len(clusters) <= 1:
        return [(room, room.polygon) for room in rooms], False

    max_gap, total_size = _max_cluster_gap(clusters)
    if max_gap / total_size > _FLOATING_GAP_RATIO:
        return _grid_layout(rooms), True
    return _compact_clusters(clusters, total_size), False


def _font_size_for_area(area_m2: float) -> float:
    """Tamaño de fuente (px) proporcional al área de la habitación, entre
    `_FONT_MIN_PX` y `_FONT_MAX_PX`."""
    span = _FONT_AREA_MAX_M2 - _FONT_AREA_MIN_M2
    t = (area_m2 - _FONT_AREA_MIN_M2) / span if span > 0 else 1.0
    t = min(max(t, 0.0), 1.0)
    return _FONT_MIN_PX + (_FONT_MAX_PX - _FONT_MIN_PX) * t


def _text_fits(lines: List[str], font_size: float, room_w_px: float, room_h_px: float) -> bool:
    if not lines:
        return True
    text_w_px = max(len(line) for line in lines) * font_size * _CHAR_WIDTH_FACTOR
    text_h_px = len(lines) * font_size * _LINE_HEIGHT_FACTOR
    return text_w_px <= room_w_px * _FIT_MARGIN and text_h_px <= room_h_px * _FIT_MARGIN


def _room_text_element(room: Room, polygon: BaseGeometry, scale: float, cx: float, cy: float) -> str:
    """`<text>` con nombre + superficie (o solo superficie, o nada) centrado
    en (cx, cy), solo si cabe dentro del propio contorno de la habitación.
    `polygon` es la geometría ya posicionada para el plano (real, compactada
    o de cuadrícula), no necesariamente `room.polygon`."""
    font_size = _font_size_for_area(room.area_m2)
    long_side_m, short_side_m = _bounding_sides(polygon)
    room_w_px = long_side_m * scale
    room_h_px = short_side_m * scale

    area_line = f"{room.area_m2:.2f} m²"
    lines = [room.label, area_line] if room.label else [area_line]

    if not _text_fits(lines, font_size, room_w_px, room_h_px):
        lines = [area_line]
        if not _text_fits(lines, font_size, room_w_px, room_h_px):
            return ""

    line_height = font_size * _LINE_HEIGHT_FACTOR
    text_y = cy - line_height * (len(lines) - 1) / 2

    # Nombre en `_TEXT_COLOR` (texto principal), m² en `_TEXT_COLOR_SECONDARY`
    # justo debajo — pero si el nombre no cupo y solo queda la línea de m²
    # (fallback de `_text_fits` de arriba), esa única línea SÍ es el color
    # principal: es lo único que se muestra de esa habitación.
    colors = [_TEXT_COLOR, _TEXT_COLOR_SECONDARY] if len(lines) == 2 else [_TEXT_COLOR]

    tspans = "".join(
        f'<tspan x="{cx:.2f}" dy="{0 if i == 0 else line_height:.2f}" fill="{colors[i]}">{html.escape(line)}</tspan>'
        for i, line in enumerate(lines)
    )
    # `class="plan-label"`: el panel de capas del workspace CAD apaga y
    # enciende las etiquetas como una capa. Sin clase habría que seleccionar
    # todos los <text> del SVG, incluida la "N" de la rosa de los vientos.
    return (
        f'<text class="plan-label" x="{cx:.2f}" y="{text_y:.2f}" text-anchor="middle" '
        f'dominant-baseline="central" '
        f'font-family="{_FONT_FAMILY}" font-size="{font_size:.1f}">'
        f"{tspans}</text>"
    )


def _north_arrow_svg(norte_grados: float) -> str:
    """Rosa de los vientos en la esquina superior derecha: círculo de 32px
    con 4 marcas cardinales finas; rota en sentido horario `norte_grados`
    grados (0° por defecto = arriba del plano = Norte), misma convención de
    azimut que `evaluator.py` — así la N (única etiquetada) siempre señala
    el norte real."""
    cx, cy = _VIEWBOX_W - 40, 46
    r = 16.0
    tick = 5.0
    return (
        f'<g class="plan-north" transform="rotate({norte_grados:.1f} {cx} {cy})" opacity="0.9">'
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="{_NORTH_ARROW_COLOR}" stroke-width="1"/>'
        f'<line x1="{cx:.1f}" y1="{cy - r:.1f}" x2="{cx:.1f}" y2="{cy - r + tick:.1f}" stroke="{_NORTH_ARROW_COLOR}" stroke-width="1"/>'
        f'<line x1="{cx:.1f}" y1="{cy + r:.1f}" x2="{cx:.1f}" y2="{cy + r - tick:.1f}" stroke="{_NORTH_ARROW_COLOR}" stroke-width="1"/>'
        f'<line x1="{cx - r:.1f}" y1="{cy:.1f}" x2="{cx - r + tick:.1f}" y2="{cy:.1f}" stroke="{_NORTH_ARROW_COLOR}" stroke-width="1"/>'
        f'<line x1="{cx + r:.1f}" y1="{cy:.1f}" x2="{cx + r - tick:.1f}" y2="{cy:.1f}" stroke="{_NORTH_ARROW_COLOR}" stroke-width="1"/>'
        f'<text x="{cx:.1f}" y="{cy - r - 4:.1f}" text-anchor="middle" '
        f'font-family="{_FONT_FAMILY}" font-size="11" font-weight="600" '
        f'fill="{_NORTH_ARROW_COLOR}">N</text>'
        "</g>"
    )


def layout_room_polygons(vivienda: UnitScore) -> List[Tuple[Room, BaseGeometry]]:
    """Habitaciones de `vivienda` con el mismo layout (posiciones reales,
    compactado o cuadrícula) que dibuja `generate_plan_svg`, en metros reales
    (sin escalar al viewBox). Wrapper público de `_layout_rooms` para que
    otros consumidores (p. ej. `api_serializer`, para el visor 3D) puedan
    reusar exactamente la misma disposición que ve el arquitecto en el plano
    2D, en vez de recalcularla o usar `room.polygon` directamente (que no
    refleja el compactado/cuadrícula cuando la vivienda está partida en
    varios bloques)."""
    layout, _is_floating = _layout_rooms(vivienda.unit.rooms)
    return layout


def generate_plan_svg(vivienda: UnitScore, norte_grados: float = 0.0) -> str:
    """Genera el SVG (viewBox fijo `0 0 800 600`) de una única vivienda,
    escrito a mano en SVG puro: sin matplotlib, sin ejes, sin márgenes de
    figura, sin "chips" de fondo — solo `<rect>`, `<polygon>`, `<text>` y la
    flecha de norte. Devuelve cadena vacía si la vivienda no tiene
    habitaciones."""
    rooms = vivienda.unit.rooms
    if not rooms:
        return ""

    # El índice de `data-room` debe coincidir con la posición de la
    # habitación en `vivienda.unit.rooms`, el mismo orden que usa
    # `api_serializer` para construir el JSON de `habitaciones` — el layout
    # (compactado o de cuadrícula) puede reordenar las habitaciones respecto
    # a ese orden original, así que se busca por identidad, no por posición
    # en `layout`.
    original_index = {id(room): i for i, room in enumerate(rooms)}
    layout, is_floating = _layout_rooms(rooms)

    bounds = [polygon.bounds for _room, polygon in layout]
    minx = min(b[0] for b in bounds)
    miny = min(b[1] for b in bounds)
    maxx = max(b[2] for b in bounds)
    maxy = max(b[3] for b in bounds)
    to_screen, scale, offset_x, offset_y = calcular_transformador_de_pantalla(minx, miny, maxx, maxy)

    # --- Transformación publicada para el frontend -------------------------
    # El lienzo tipo CAD necesita convertir píxel del SVG → metro real, y esa
    # conversión NO es deducible del SVG por sí sola: `_compact_clusters` y
    # `_grid_layout` TRASLADAN habitaciones respecto a su posición en el DXF
    # (a propósito, para que una vivienda dispersa sea legible). Se publica
    # aquí lo justo para poder invertirla:
    #
    #   metro_dibujo_x = (px - ox) / escala + minx
    #   metro_dibujo_y = maxy - (py - oy) / escala
    #   metro_real     = metro_dibujo + (dx, dy) de esa habitación
    #
    # Ambos layouts solo trasladan (nunca rotan ni deforman), así que un
    # desplazamiento por habitación basta para recuperar su posición real.
    # `data-fiel="1"` significa que no se movió nada y las coordenadas del
    # dibujo YA son las del DXF en toda la superficie del lienzo, no solo
    # dentro de las habitaciones.
    deltas = {}
    for room, polygon in layout:
        deltas[id(room)] = (
            room.polygon.bounds[0] - polygon.bounds[0],
            room.polygon.bounds[1] - polygon.bounds[1],
        )
    fiel = all(abs(dx) < 1e-6 and abs(dy) < 1e-6 for dx, dy in deltas.values())

    parts = [
        f'<svg viewBox="0 0 {_VIEWBOX_W} {_VIEWBOX_H}" xmlns="http://www.w3.org/2000/svg"'
        f' data-escala="{scale:.6f}" data-ox="{offset_x:.4f}" data-oy="{offset_y:.4f}"'
        f' data-minx="{minx:.4f}" data-maxy="{maxy:.4f}" data-fiel="{1 if fiel else 0}">'
    ]

    for room, polygon in layout:
        room_index = original_index[id(room)]
        delta_x, delta_y = deltas[id(room)]
        problems = room_problems(room, vivienda)
        has_problems = bool(problems)
        base_fill = _room_type_fill(room)
        fill = _blend_hex(base_fill, _PROBLEM_EDGE_COLOR, _PROBLEM_TINT) if has_problems else base_fill
        stroke = _PROBLEM_STROKE_COLOR if has_problems else _WALL_COLOR
        stroke_width = _PROBLEM_STROKE_WIDTH if has_problems else _WALL_STROKE_WIDTH

        parts.append(
            f'<g data-room="{room_index}" class="plan-room"'
            f' data-dx="{delta_x:.4f}" data-dy="{delta_y:.4f}">'
        )
        for xs, ys in exterior_rings(polygon):
            points = svg_points(xs, ys, to_screen)
            parts.append(
                f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" '
                f'stroke-width="{stroke_width}" stroke-linejoin="round"/>'
            )
        parts.append("</g>")

        cx, cy = to_screen(polygon.centroid.x, polygon.centroid.y)
        text_element = _room_text_element(room, polygon, scale, cx, cy)
        if text_element:
            parts.append(text_element)

    # La envolvente se dibuja al final para que su trazo quede por encima del
    # de las particiones. Se omite por el MISMO motivo que la flecha de norte:
    # en modo cuadrícula las habitaciones están en posiciones sintéticas, así
    # que su unión no es el perímetro de nada. Dibujar ahí un contorno sería
    # afirmar una forma construida que no existe.
    if not is_floating:
        parts.append(_envelope_svg(layout, to_screen))

    # La flecha de norte solo tiene sentido si las habitaciones conservan su
    # orientación real (posiciones reales o compactadas); en modo cuadrícula
    # la disposición es puramente sintética y mostrarla induciría a error.
    if not is_floating:
        parts.append(_north_arrow_svg(norte_grados))
    parts.append("</svg>")
    return "\n".join(parts)


def _render_legend_html() -> str:
    items = [
        ("Salón / cocina", "#d4edda"),
        ("Dormitorio", "#dce8f5"),
        ("Baño / aseo", "#fdf3e3"),
        ("Terraza", "#fce8d5"),
        ("Tendedero", "#ede8f5"),
        ("Otros espacios", _NEUTRAL_FILL),
    ]
    swatches = "".join(
        '<span class="plan-legend-item">'
        f'<span class="plan-legend-swatch" style="background:{color}"></span>{label}</span>'
        for label, color in items
    )
    problem_swatch = (
        '<span class="plan-legend-item">'
        '<span class="plan-legend-swatch plan-legend-swatch--problem"></span>'
        "Borde rojo: habitación con incidencias detectadas"
        "</span>"
    )
    return f'<div class="plan-legend">{swatches}{problem_swatch}</div>'


def render_plan_section(unit_scores: List[UnitScore], norte_grados: float = 0.0) -> str:
    """Construye el contenido completo de la sección "Plano analizado": una
    fila por vivienda (cada una con su propio SVG a todo el ancho) seguida de
    la leyenda de tipos de espacio. Devuelve cadena vacía si no hay ninguna
    habitación que dibujar."""
    if not any(u.unit.rooms for u in unit_scores):
        return ""

    parts = ['<div class="plan-units">']
    for u in unit_scores:
        svg = generate_plan_svg(u, norte_grados=norte_grados)
        if not svg:
            continue
        badge_class = _SCORE_BADGE_CLASS[u.rating]
        parts.append('<div class="plan-unit">')
        parts.append(
            '<div class="plan-unit-header">'
            f"<h3>{html.escape(u.unit.name)}</h3>"
            f'<span class="badge {badge_class}">{u.score_pct:.0f}%</span>'
            "</div>"
        )
        parts.append(f'<div class="plan-svg-wrap">{svg}</div>')
        parts.append("</div>")
    parts.append("</div>")
    parts.append(_render_legend_html())
    return "\n".join(parts)
