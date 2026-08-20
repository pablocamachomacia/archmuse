"""Análisis de calidad espacial: heurísticas de diseño (no normativas/CTE,
a diferencia de `evaluator.py`) que puntúan cada habitación y cada vivienda
según 5 criterios de confort y eficiencia proyectual:

1. Proporción "tubo" (`_check_tubo`) — reutiliza el mismo umbral
   (`MAX_ASPECT_RATIO`) que `evaluator.evaluate_proportions`, pero se
   recalcula directamente sobre `Room` (en vez de envolver `ProportionResult`,
   que no guarda una referencia al `Room` y complicaría resaltarlo en el SVG).
2. Profundidad de iluminación (`_check_daylight_depth`) — distinta de
   `evaluator.evaluate_natural_lighting` (que usa un máximo absoluto fijo de
   6m): aquí el máximo es relativo a una altura de ventana estimada
   (`ASSUMED_WINDOW_HEIGHT_M`, el modelo no tiene carpintería real), regla
   clásica de "2.5× la altura del hueco" para la profundidad de penetración
   de luz natural.
3. Escala humana (`_check_human_scale`) — ratio superficie/altura libre
   dentro de un rango de confort por tipo de uso. Heurística propia (no hay
   código normativo que fije esto), documentada como tal.
4. Espacios muertos (`_check_dead_space`) — apertura morfológica
   (erosión + dilatación) del polígono de la habitación para aislar
   recovecos/esquinas más estrechos que el umbral: es la técnica estándar de
   geometría computacional para "eliminar entrantes más finos que X".
5. Jerarquía espacial (`_issues_from_hierarchy`) — no se recalcula: envuelve
   los resultados YA calculados por `evaluator.evaluate_dormitory_hierarchy`,
   `evaluate_spatial_hierarchy` y `evaluate_circulation_efficiency` (vía
   `UnitScore`), para no duplicar esa lógica.

Cada problema detectado resta puntos a la puntuación de su habitación
(`RoomQuality.score_pct`, 100 menos la suma de impactos) y, agregado, a la
de la vivienda (`UnitQuality.score_pct`). `generate_spatial_quality_svg`
dibuja el resultado reutilizando el mismo motor de layout que
`plan_svg.generate_plan_svg` (`layout_room_polygons`, ya expuesto como API
pública para justo este tipo de reuso) con una capa translúcida por
problema, coloreada según `SPATIAL_ISSUE_COLORS` (un color fijo por tipo).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from shapely.affinity import translate
from shapely.geometry import Polygon

from .evaluator import (
    DORMITORIO_PATTERNS,
    MAX_ASPECT_RATIO,
    MIN_CEILING_HEIGHT_M,
    Unit,
    UnitScore,
    _SALON_PATTERN,
    _bounding_sides,
    _find_room_by_pattern,
    _normalize,
    _room_has_exterior_facade,
)
from .parser import Room
from .plan_svg import (
    _VIEWBOX_H, _VIEWBOX_W,
    calcular_transformador_de_pantalla, exterior_rings, layout_room_polygons, room_type, svg_points,
)

# ---------------------------------------------------------------------------
# Colores por tipo de problema (para el resaltado en el SVG y la leyenda)
# ---------------------------------------------------------------------------

SPATIAL_ISSUE_COLORS = {
    "tubo": "#F59E0B",  # naranja
    "iluminacion_profunda": "#7C3AED",  # púrpura
    "escala_humana": "#0EA5E9",  # azul
    "espacio_muerto": "#DC2626",  # rojo
    "jerarquia": "#EAB308",  # dorado
}

# Puntos deducidos por incidencia. Nombrados como constantes (igual que el
# resto de umbrales del módulo) para poder recalibrarlos sin buscar números
# mágicos en el código.
SCORE_IMPACT_TUBO = 15.0
SCORE_IMPACT_ILUMINACION = 20.0
SCORE_IMPACT_ESCALA_HUMANA = 10.0
SCORE_IMPACT_ESPACIO_MUERTO_MAX = 30.0
SCORE_IMPACT_JERARQUIA = 10.0


@dataclass
class SpatialIssue:
    tipo: str  # "tubo" | "iluminacion_profunda" | "escala_humana" | "espacio_muerto" | "jerarquia"
    room_label: str  # "" si es un problema de vivienda completa (jerarquía)
    severity: str  # "ALTO" | "MEDIO" | "BAJO"
    message: str
    score_impact: float
    # Habitación a resaltar en el SVG (su polígono ORIGINAL, sin posicionar
    # — `generate_spatial_quality_svg` calcula la traslación al layout). None
    # si no se pudo identificar una habitación concreta (caso raro).
    highlight_room: Optional[Room] = None
    # Geometría concreta a resaltar dentro de esa habitación; si es None se
    # resalta el polígono completo de `highlight_room` (el caso habitual —
    # solo "espacio_muerto" resalta una sub-zona, no la habitación entera).
    highlight_polygon: Optional[Polygon] = None

    @property
    def color(self) -> str:
        return SPATIAL_ISSUE_COLORS.get(self.tipo, "#999999")


@dataclass
class RoomQuality:
    room: Room
    issues: List[SpatialIssue] = field(default_factory=list)
    score_pct: float = 100.0


@dataclass
class UnitQuality:
    unit_name: str
    room_qualities: List[RoomQuality] = field(default_factory=list)
    unit_issues: List[SpatialIssue] = field(default_factory=list)  # jerarquía espacial
    score_pct: float = 100.0


# ---------------------------------------------------------------------------
# 1. Proporción "tubo"
# ---------------------------------------------------------------------------


def _check_tubo(room: Room) -> Optional[SpatialIssue]:
    if room.label and "PASILLO" in _normalize(room.label):
        return None  # una franja larga y estrecha es correcta en un pasillo
    long_side, short_side = _bounding_sides(room.polygon)
    if short_side <= 0:
        return None
    ratio = long_side / short_side
    if ratio <= MAX_ASPECT_RATIO:
        return None
    label = room.label or "(sin etiqueta)"
    return SpatialIssue(
        tipo="tubo",
        room_label=label,
        severity="MEDIO",
        message=(
            f"{label}: proporción 1:{ratio:.1f} ({long_side:.2f}×{short_side:.2f}m) — "
            f"habitación \"tubo\", supera el máximo de 1:{MAX_ASPECT_RATIO}"
        ),
        score_impact=SCORE_IMPACT_TUBO,
        highlight_room=room,
    )


# ---------------------------------------------------------------------------
# 2. Profundidad de iluminación
# ---------------------------------------------------------------------------

ASSUMED_WINDOW_HEIGHT_M = 1.30  # estimación estándar residencial (antepecho ~0.90m, dintel ~2.20m)
DAYLIGHT_DEPTH_FACTOR = 2.5


def _check_daylight_depth(room: Room, unit: Unit) -> Optional[SpatialIssue]:
    if not room.label:
        return None
    if not _room_has_exterior_facade(room, unit.rooms):
        return None  # sin fachada exterior, ya lo penaliza evaluator.evaluate_natural_light
    _long_side, short_side = _bounding_sides(room.polygon)
    if short_side <= 0:
        return None
    max_depth = DAYLIGHT_DEPTH_FACTOR * ASSUMED_WINDOW_HEIGHT_M
    if short_side <= max_depth:
        return None
    return SpatialIssue(
        tipo="iluminacion_profunda",
        room_label=room.label,
        severity="ALTO",
        message=(
            f"{room.label}: profundidad {short_side:.2f}m supera {max_depth:.2f}m "
            f"(2.5× la altura de ventana estimada de {ASSUMED_WINDOW_HEIGHT_M}m) — "
            "zona oscura al fondo de la pieza"
        ),
        score_impact=SCORE_IMPACT_ILUMINACION,
        highlight_room=room,
    )


# ---------------------------------------------------------------------------
# 3. Escala humana
# ---------------------------------------------------------------------------

# Rango confortable de ratio superficie(m²)/altura libre(m) por tipo de uso.
# Heurística propia del módulo (no hay código normativo que fije esto): por
# debajo del mínimo, la pieza se percibe angosta para su altura; por encima
# del máximo, desproporcionadamente baja/expansiva para su superficie.
HUMAN_SCALE_RANGES = {
    "salon_cocina": (6.0, 16.0),
    "dormitorio": (2.5, 6.0),
    "bano": (1.0, 3.0),
    "otro": (1.5, 10.0),
}


def _check_human_scale(room: Room, altura_libre_m: float) -> Optional[SpatialIssue]:
    if not room.label or altura_libre_m <= 0:
        return None
    tipo_uso = room_type(room)
    if tipo_uso in ("terraza", "tendedero"):
        return None  # espacio exterior, sin escala de confort interior aplicable
    min_ratio, max_ratio = HUMAN_SCALE_RANGES.get(tipo_uso, HUMAN_SCALE_RANGES["otro"])
    ratio = room.area_m2 / altura_libre_m
    if min_ratio <= ratio <= max_ratio:
        return None
    detalle = (
        "se percibe desproporcionadamente estrecha para su altura libre"
        if ratio < min_ratio
        else "se percibe desproporcionadamente baja/expansiva para su superficie"
    )
    return SpatialIssue(
        tipo="escala_humana",
        room_label=room.label,
        severity="BAJO",
        message=(
            f"{room.label}: ratio superficie/altura {ratio:.1f} fuera del rango confortable "
            f"[{min_ratio:.1f}-{max_ratio:.1f}] para su uso — {detalle}"
        ),
        score_impact=SCORE_IMPACT_ESCALA_HUMANA,
        highlight_room=room,
    )


# ---------------------------------------------------------------------------
# 4. Espacios muertos
# ---------------------------------------------------------------------------

DEAD_SPACE_MIN_WIDTH_M = 0.6
# Erosionar por la mitad del umbral y volver a dilatar (apertura morfológica)
# elimina exactamente las zonas más estrechas que `DEAD_SPACE_MIN_WIDTH_M` —
# técnica estándar de geometría computacional, no una aproximación ad-hoc.
_DEAD_SPACE_EROSION_M = DEAD_SPACE_MIN_WIDTH_M / 2
DEAD_SPACE_AREA_TOLERANCE_M2 = 0.05  # ruido geométrico mínimo a ignorar
DEAD_SPACE_FULL_PENALTY_RATIO = 0.30  # % de superficie "muerta" a partir del cual se aplica el impacto máximo


def _check_dead_space(room: Room) -> Optional[SpatialIssue]:
    polygon = room.polygon
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.area <= 0:
        return None

    opened = polygon.buffer(-_DEAD_SPACE_EROSION_M).buffer(_DEAD_SPACE_EROSION_M)
    dead_zone = polygon.difference(opened)
    dead_area = dead_zone.area
    if dead_area <= DEAD_SPACE_AREA_TOLERANCE_M2:
        return None

    label = room.label or "(sin etiqueta)"
    dead_ratio = dead_area / max(room.area_m2, 0.01)
    score_impact = min(
        SCORE_IMPACT_ESPACIO_MUERTO_MAX,
        SCORE_IMPACT_ESPACIO_MUERTO_MAX * dead_ratio / DEAD_SPACE_FULL_PENALTY_RATIO,
    )
    return SpatialIssue(
        tipo="espacio_muerto",
        room_label=label,
        severity="BAJO",
        message=(
            f"{label}: {dead_area:.2f} m² de recovecos/esquinas más estrechos que "
            f"{DEAD_SPACE_MIN_WIDTH_M}m — espacio sin uso funcional claro"
        ),
        score_impact=score_impact,
        highlight_room=room,
        highlight_polygon=dead_zone,
    )


# ---------------------------------------------------------------------------
# 5. Jerarquía espacial (envuelve resultados ya calculados por evaluator.py)
# ---------------------------------------------------------------------------

_HIERARCHY_PATTERN_BY_NAME = {name: pattern for name, pattern in DORMITORIO_PATTERNS}


def _issues_from_hierarchy(unit_score: UnitScore) -> List[SpatialIssue]:
    """No recalcula nada: envuelve `unit_score.hierarchy_results`,
    `.spatial_hierarchy_result` y `.circulation_efficiency_result` (ya
    calculados por `evaluator.score_unit`) como `SpatialIssue`, re-buscando
    la habitación implicada solo para poder resaltarla en el SVG."""
    unit = unit_score.unit
    issues: List[SpatialIssue] = []

    for h in unit_score.hierarchy_results:
        if h.passed:
            continue
        pattern = _HIERARCHY_PATTERN_BY_NAME.get(h.lower_name)
        lower_room = _find_room_by_pattern(unit.rooms, pattern) if pattern else None
        issues.append(SpatialIssue(
            tipo="jerarquia",
            room_label="",
            severity="MEDIO",
            message=h.message,
            score_impact=SCORE_IMPACT_JERARQUIA,
            highlight_room=lower_room,
        ))

    sh = unit_score.spatial_hierarchy_result
    if sh is not None and not sh.passed:
        salon = _find_room_by_pattern(unit.rooms, _SALON_PATTERN)
        issues.append(SpatialIssue(
            tipo="jerarquia",
            room_label="",
            severity="MEDIO",
            message=sh.message,
            score_impact=SCORE_IMPACT_JERARQUIA,
            highlight_room=salon,
        ))

    ce = unit_score.circulation_efficiency_result
    if ce is not None and not ce.passed:
        pasillo = next((r for r in unit.rooms if r.label and "PASILLO" in _normalize(r.label)), None)
        issues.append(SpatialIssue(
            tipo="jerarquia",
            room_label="",
            severity="BAJO",
            message=ce.message,
            score_impact=SCORE_IMPACT_JERARQUIA / 2,
            highlight_room=pasillo,
        ))

    return issues


# ---------------------------------------------------------------------------
# Orquestación y puntuación
# ---------------------------------------------------------------------------


def evaluate_spatial_quality(unit_score: UnitScore, altura_libre_m: Optional[float] = None) -> UnitQuality:
    """Evalúa los 5 criterios sobre cada habitación de `unit_score.unit` y
    agrega el resultado en una puntuación por habitación y por vivienda (100
    menos la suma de los impactos de sus problemas, sin bajar de 0).
    `altura_libre_m` solo está disponible en proyectos generados
    (`edificio.altura_libre_m`); si no se informa, se usa el mínimo CTE
    (`MIN_CEILING_HEIGHT_M`) como referencia — un DXF analizado no tiene
    datos de sección vertical, igual que el resto de comprobaciones de
    altura de `evaluator.py`."""
    unit = unit_score.unit
    effective_height = altura_libre_m if altura_libre_m and altura_libre_m > 0 else MIN_CEILING_HEIGHT_M

    room_qualities: List[RoomQuality] = []
    for room in unit.rooms:
        issues = [
            issue
            for issue in (
                _check_tubo(room),
                _check_daylight_depth(room, unit),
                _check_human_scale(room, effective_height),
                _check_dead_space(room),
            )
            if issue is not None
        ]
        total_impact = sum(i.score_impact for i in issues)
        room_qualities.append(RoomQuality(room=room, issues=issues, score_pct=max(0.0, 100.0 - total_impact)))

    unit_issues = _issues_from_hierarchy(unit_score)
    unit_penalty = sum(i.score_impact for i in unit_issues)
    base_unit_score = (
        sum(rq.score_pct for rq in room_qualities) / len(room_qualities) if room_qualities else 100.0
    )

    return UnitQuality(
        unit_name=unit.name,
        room_qualities=room_qualities,
        unit_issues=unit_issues,
        score_pct=max(0.0, base_unit_score - unit_penalty),
    )


# ---------------------------------------------------------------------------
# Visualización: resalta cada problema en el plano con el color de su tipo
# ---------------------------------------------------------------------------


def _iter_all_issues(quality: UnitQuality):
    for rq in quality.room_qualities:
        yield from rq.issues
    yield from quality.unit_issues


def generate_spatial_quality_svg(unit_score: UnitScore, quality: UnitQuality) -> str:
    """Dibuja el mismo plano que `plan_svg.generate_plan_svg` (reutilizando
    `layout_room_polygons` para la disposición real/compactada/cuadrícula,
    y el mismo cálculo de escala a un viewBox `0 0 800 600`) pero con
    contornos neutros y una capa translúcida por problema detectado,
    coloreada según `SPATIAL_ISSUE_COLORS`. `highlight_polygon` (o el
    polígono completo de `highlight_room` si no hay uno más específico) está
    en las coordenadas ORIGINALES de `room.polygon`; se traslada aquí a la
    posición del layout comparando centroides (el layout de
    `layout_room_polygons` solo traslada, nunca rota, así que la diferencia
    de centroides es la traslación exacta)."""
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
    to_screen, _scale, _offset_x, _offset_y = calcular_transformador_de_pantalla(minx, miny, maxx, maxy)

    def render_geometry(geom, fill: str, stroke: str, stroke_width: float, opacity: float = 1.0) -> str:
        parts = []
        for xs, ys in exterior_rings(geom):
            points = svg_points(xs, ys, to_screen)
            parts.append(
                f'<polygon points="{points}" fill="{fill}" fill-opacity="{opacity}" '
                f'stroke="{stroke}" stroke-width="{stroke_width}" stroke-linejoin="round"/>'
            )
        return "".join(parts)

    parts = [f'<svg viewBox="0 0 {_VIEWBOX_W} {_VIEWBOX_H}" xmlns="http://www.w3.org/2000/svg">']

    for _room, polygon in layout:
        parts.append(render_geometry(polygon, "#F4F5F7", "#9AA3B2", 1.0))

    for issue in _iter_all_issues(quality):
        if issue.highlight_room is None:
            continue
        positioned = positioned_by_id.get(id(issue.highlight_room))
        if positioned is None:
            continue
        dx = positioned.centroid.x - issue.highlight_room.polygon.centroid.x
        dy = positioned.centroid.y - issue.highlight_room.polygon.centroid.y
        geom = issue.highlight_polygon if issue.highlight_polygon is not None else issue.highlight_room.polygon
        positioned_geom = translate(geom, dx, dy)
        parts.append(render_geometry(positioned_geom, issue.color, issue.color, 1.5, opacity=0.35))

    parts.append("</svg>")
    return "\n".join(parts)



# ---------------------------------------------------------------------------
# Serialización JSON (para la API REST, ver analyzer/api_serializer.py)
# ---------------------------------------------------------------------------


def _polygon_to_points(geom) -> List[List[float]]:
    """Mismo formato que `api_serializer._polygon_points`: anillo exterior
    en metros, sin el punto de cierre duplicado. Para un MultiPolygon usa
    solo el sub-polígono de mayor área."""
    if geom is None:
        return []
    if geom.geom_type == "MultiPolygon":
        geom = max(geom.geoms, key=lambda g: g.area, default=None)
        if geom is None:
            return []
    if geom.geom_type != "Polygon":
        return []
    coords = list(geom.exterior.coords)
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return [[round(x, 3), round(y, 3)] for x, y in coords]


def _serialize_issue(issue: SpatialIssue) -> dict:
    geom = issue.highlight_polygon if issue.highlight_polygon is not None else (
        issue.highlight_room.polygon if issue.highlight_room else None
    )
    return {
        "tipo": issue.tipo,
        "room_label": issue.room_label or (issue.highlight_room.label if issue.highlight_room else ""),
        "severidad": issue.severity,
        "mensaje": issue.message,
        "impacto_puntos": round(issue.score_impact, 1),
        "color": issue.color,
        "poligono": _polygon_to_points(geom),
    }


def serialize_unit_quality(unit_score: UnitScore, quality: UnitQuality) -> dict:
    return {
        "vivienda": quality.unit_name,
        "puntuacion": round(quality.score_pct),
        "habitaciones": [
            {
                "nombre": rq.room.label or "(sin etiqueta)",
                "puntuacion": round(rq.score_pct),
                "problemas": [_serialize_issue(i) for i in rq.issues],
            }
            for rq in quality.room_qualities
        ],
        "problemas_vivienda": [_serialize_issue(i) for i in quality.unit_issues],
        "leyenda": [{"tipo": tipo, "color": color} for tipo, color in SPATIAL_ISSUE_COLORS.items()],
        "svg": generate_spatial_quality_svg(unit_score, quality),
    }
