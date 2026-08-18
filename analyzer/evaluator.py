"""Evaluación de reglas de calidad sobre las habitaciones detectadas.

Reglas básicas de superficie mínima:
- Salón / cocina  -> área > 20 m²
- Dormitorio 1    -> área > 10 m²
- Dormitorio 2/3  -> área > 7 m²
- Baño            -> área > 3 m²

Reglas avanzadas de calidad arquitectónica:
1. Proporciones: ninguna habitación debe ser "tubo" (lado largo > 2.5x lado corto).
2. Jerarquía de dormitorios: Dormitorio 1 > Dormitorio 2 > Dormitorio 3, dentro
   de cada vivienda.
3. Eficiencia: superficie útil (sin terrazas/tendederos) >= 80% de la superficie
   total, por vivienda.
4. Orientación solar: hacia qué lado da la fachada más larga de cada
   habitación, y si esa orientación es adecuada para su uso.

El emparejamiento habitación-regla se hace por el texto de la etiqueta
(normalizado: sin acentos, en mayúsculas), no por el nombre exacto del layer.
Las reglas 2 y 3 son por vivienda: se agrupan las habitaciones usando las
etiquetas de vivienda del plano ('VT1/3', 'VT2/2'...) vía
`group_rooms_by_unit_label`; si el plano no tiene esas etiquetas, se recurre
a `group_rooms_by_proximity` como aproximación geométrica.
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from modelo import AlmacenGeometria, HUELLA_2D
from modelo.geometria import tramo_enfrentado_m

from . import adyacencia
from .parser import Room


@dataclass
class RuleResult:
    room_label: Optional[str]
    area_m2: float
    rule_name: str
    min_area_m2: float
    passed: bool

    @property
    def message(self) -> str:
        label = self.room_label or "(sin etiqueta)"
        if self.passed:
            return (
                f"{label}: {self.area_m2:.2f} m² cumple regla '{self.rule_name}' "
                f"(> {self.min_area_m2} m²)"
            )
        return (
            f"{label}: {self.area_m2:.2f} m² NO cumple regla '{self.rule_name}' "
            f"(mínimo {self.min_area_m2} m²)"
        )


def _normalize(text: str) -> str:
    """Quita acentos/diacríticos y pasa a mayúsculas para comparar de forma robusta."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.upper().strip()


# Cada regla: (nombre descriptivo, patrón regex sobre texto normalizado, área mínima en m²)
RULES = [
    ("Salón/Cocina", re.compile(r"SALON|COCINA"), 20.0),
    ("Dormitorio 1", re.compile(r"DORMITORIO\s*1\b"), 10.0),
    ("Dormitorio 2", re.compile(r"DORMITORIO\s*2\b"), 8.0),
    ("Dormitorio 3", re.compile(r"DORMITORIO\s*3\b"), 6.0),
    ("Baño", re.compile(r"BANO"), 3.0),
    ("Aseo", re.compile(r"ASEO"), 1.5),
]


def evaluate_room(room: Room) -> List[RuleResult]:
    """Devuelve los resultados de las reglas que apliquen a esta habitación (puede ser ninguna)."""
    if not room.label:
        return []

    normalized = _normalize(room.label)
    results: List[RuleResult] = []
    for rule_name, pattern, min_area in RULES:
        if pattern.search(normalized):
            results.append(
                RuleResult(
                    room_label=room.label,
                    area_m2=room.area_m2,
                    rule_name=rule_name,
                    min_area_m2=min_area,
                    passed=room.area_m2 > min_area,
                )
            )
    return results


def evaluate_rooms(rooms: List[Room]) -> List[RuleResult]:
    """Evalúa todas las habitaciones y devuelve la lista completa de resultados."""
    results: List[RuleResult] = []
    for room in rooms:
        results.extend(evaluate_room(room))
    return results


# ---------------------------------------------------------------------------
# CTE básico: limitaciones de datos del modelo actual
# ---------------------------------------------------------------------------

MIN_CEILING_HEIGHT_M = 2.5  # CTE DB-SUA: altura libre mínima en zonas habitables
MIN_STAIR_WIDTH_M = 1.0  # CTE DB-SUA: anchura mínima de escalera de uso privado


def get_missing_data_warnings(
    superficie_solar_m2: Optional[float] = None,
    normativa: Optional[dict] = None,
    solar: Optional[dict] = None,
    zona_cte: Optional[str] = None,
    zona_cte_supuesta: bool = False,
    ciudad: Optional[str] = None,
) -> List[str]:
    """Avisos informativos (no penalizables) sobre comprobaciones que el
    modelo actual no puede evaluar por falta de datos: geométricos (altura,
    escalera, retranqueos — siempre ausentes, ni el DXF ni el generador los
    modelan) o de parámetros de proyecto (superficie de solar,
    edificabilidad máxima — solo ausentes si no se han indicado). Van al
    campo "limitaciones" del JSON de salida (a nivel de proyecto) — es
    transparencia hacia el arquitecto, no una penalización de diseño.

    `zona_cte_supuesta` (tarea 6 del `REFACTOR_MASTERPLAN.md`) es distinto del
    resto: no dice que algo no se haya podido comprobar, sino que **sí se ha
    comprobado, con un dato inventado**. Lo calcula
    `cte_zonas.resolver_zona_cte`, y quien llama tiene que pasarlo — este
    módulo no importa `cte_zonas` a propósito, para no arrastrar `normativa/`
    dentro de `evaluator.py`. Si nadie lo pasa, no hay aviso: el valor por
    defecto `False` conserva exactamente la salida anterior a la tarea 6.
    """
    normativa = normativa or {}
    solar = solar or {}
    warnings = [
        "Altura libre: no evaluable — el modelo actual no contiene datos "
        f"de sección vertical. Mínimo CTE DB-SUA: {MIN_CEILING_HEIGHT_M}m "
        "en zonas habitables.",
        "Escalera: no evaluable — el modelo actual no contiene elementos "
        f"de escalera. Mínimo CTE DB-SUA: {MIN_STAIR_WIDTH_M}m de anchura "
        "libre.",
    ]
    if zona_cte_supuesta:
        nombre_ciudad = (ciudad or "").strip()
        motivo = (
            f"la ciudad indicada («{nombre_ciudad}») no está en la tabla de "
            "municipios de ArchMuse"
            if nombre_ciudad
            else "no se ha indicado la ciudad del proyecto"
        )
        warnings.append(
            f"Zona climática: supuesta, no verificada — {motivo}. El análisis "
            f"se ha hecho como zona {zona_cte or DEFAULT_ZONA_CTE} (CTE DB-HE, "
            "Apéndice B), que es el valor por defecto: las comprobaciones que "
            "dependen del clima (riesgo de condensaciones, horas de sol, "
            "compacidad) salen de esa suposición, no de un dato del proyecto."
        )
    if not superficie_solar_m2:
        warnings.append("Ocupación solar: no evaluable sin superficie real del solar.")
    if normativa.get("edificabilidad_maxima") is None:
        warnings.append("Edificabilidad: parámetro no proporcionado — no evaluable.")
    if not (solar.get("ancho_m") and solar.get("largo_m") and normativa.get("retranqueos_m") is not None):
        warnings.append(
            "Retranqueos: no evaluables — el modelo actual no contiene información "
            "de linderos ni geometría del solar. Comprobar según normativa "
            "municipal aplicable."
        )
    warnings.append(
        "Aislamiento entre viviendas: no evaluable — el modelo actual no "
        "contiene información de espesores de muros medianeros. Mínimo "
        "CTE DB-HR: Rw ≥ 45 dB."
    )
    warnings.append(
        "Compartimentación contra incendios: no evaluable — el modelo "
        "actual no contiene información de resistencia al fuego de muros "
        "y forjados. Verificar CTE DB-SI: cada vivienda debe ser sector "
        "de incendio independiente (EI-60 mínimo)."
    )
    warnings.append(
        "Puertas de evacuación: no evaluable — el modelo actual no "
        "contiene elementos de carpintería. Mínimo CTE DB-SI 3, apartado 4 "
        "(Tabla 4.1): 0.80m de anchura libre en puertas de salida."
    )
    warnings.append(
        "Demanda energética: no evaluable — el modelo actual no contiene "
        "información de transmitancias de cerramientos ni puentes "
        "térmicos. Verificar CTE DB-HE1: demanda de calefacción y "
        "refrigeración según zona climática."
    )
    warnings.append(
        "Anchura de puertas: no evaluable — el modelo actual no contiene "
        "elementos de carpintería. Mínimo CTE DB-SUA: 0.80m en puertas de "
        "paso, 1.20m en puertas de entrada a la vivienda."
    )
    return warnings


# ---------------------------------------------------------------------------
# 1. Proporciones de habitaciones ("habitaciones tubo")
# ---------------------------------------------------------------------------

MAX_ASPECT_RATIO = 2.5


@dataclass
class ProportionResult:
    room_label: Optional[str]
    area_m2: float
    long_side_m: float
    short_side_m: float
    ratio: float
    passed: bool

    @property
    def ratio_str(self) -> str:
        return f"1:{self.ratio:.1f}"

    @property
    def message(self) -> str:
        label = self.room_label or "(sin etiqueta)"
        dims = f"{self.long_side_m:.2f} x {self.short_side_m:.2f} m"
        if self.passed:
            return f"{label}: proporción {self.ratio_str} ({dims}) — correcta"
        return (
            f"{label}: proporción {self.ratio_str} ({dims}) — habitación 'tubo', "
            f"supera el máximo permitido de 1:{MAX_ASPECT_RATIO}"
        )


def _bounding_sides(polygon: Polygon) -> Tuple[float, float]:
    """Lados (largo, corto) del rectángulo mínimo que envuelve el polígono.

    Se usa el rectángulo de área mínima (`minimum_rotated_rectangle`) en vez
    del bounding box alineado a los ejes, para que la proporción sea correcta
    también en habitaciones giradas respecto a los ejes del plano.
    """
    min_rect = polygon.minimum_rotated_rectangle
    coords = list(min_rect.exterior.coords)[:-1]
    if len(coords) < 4:
        return 0.0, 0.0
    side_a = Point(coords[0]).distance(Point(coords[1]))
    side_b = Point(coords[1]).distance(Point(coords[2]))
    return max(side_a, side_b), min(side_a, side_b)


def evaluate_proportions(rooms: List[Room]) -> List[ProportionResult]:
    """Evalúa la proporción largo/corto de cada habitación (excepto
    Pasillo: una franja de circulación larga y estrecha es correcta
    arquitectónicamente, no una habitación "tubo").

    E3.4 (`docs/prd/2026-08-11-e3-clasificacion-circulation.md` — mismo PRD,
    ampliado a esta regla): los lados y el alargamiento se piden a
    `AlmacenGeometria` en vez de a `_bounding_sides`, que sigue existiendo
    para `spatial_quality.py` (no se toca, no se elimina). El almacén es un
    `AlmacenGeometria()` de usar y tirar: no hay identidad ni geometría que
    persista más allá de esta llamada, sólo se reutiliza el cálculo del
    rectángulo envolvente mínimo que el modelo ya tiene que hacer bien."""
    results: List[ProportionResult] = []
    almacen = AlmacenGeometria()
    for room in rooms:
        if room.label and "PASILLO" in _normalize(room.label):
            continue
        geom_id = almacen.insertar(room.polygon, HUELLA_2D, unidad="m")
        long_side = almacen.lado_mayor_m(geom_id)
        short_side = almacen.lado_menor_m(geom_id)
        if short_side <= 0:
            continue
        ratio = almacen.alargamiento(geom_id)
        results.append(
            ProportionResult(
                room_label=room.label,
                area_m2=room.area_m2,
                long_side_m=long_side,
                short_side_m=short_side,
                ratio=ratio,
                passed=ratio <= MAX_ASPECT_RATIO,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Agrupación de habitaciones en viviendas
# ---------------------------------------------------------------------------


@dataclass
class Unit:
    """Vivienda: conjunto de habitaciones que pertenecen a la misma unidad."""

    name: str
    rooms: List[Room]
    # Contrato de clasificación (Fase 1): envolvente construida cerrada
    # (`AM_CONS_CER`) de esta vivienda, si el plano la declara y se ha podido
    # asignar sin ambigüedad (`asignar_envolvente_cerrada`). NUNCA es un
    # `Room` ni participa en `total_area_m2`: es un dato aparte, no una
    # habitación más -- meterla en `rooms` duplicaría de golpe la superficie
    # total de la vivienda y dispararía falsos solapes contra cada
    # habitación que contiene (ver informe de la Fase 1 del contrato de
    # clasificación DXF).
    envolvente_cerrada: Optional[Polygon] = None
    # Contrato de clasificación (Fase 3): superficie útil exterior
    # (`AM_UTIL_EXT` -- terrazas, tendederos, balcones...) y superficie
    # construida exterior (`AM_CONS_EXT`) de esta vivienda. Mismo criterio
    # que `envolvente_cerrada`: NUNCA son `Room`, nunca participan en
    # `total_area_m2`, nunca se mezclan entre sí ni con `rooms`. A
    # diferencia de `envolvente_cerrada` (0 o 1 por vivienda), estas dos
    # admiten varias piezas por vivienda -- una terraza y un tendedero son
    # dos superficies útiles exteriores distintas de la misma vivienda, no
    # una ambigüedad que resolver -- así que aquí no hay ninguna decisión de
    # unicidad: es la lista completa de lo que se le haya asignado
    # (`asignar_superficies_exteriores`), vacía si no hay ninguna.
    superficies_utiles_exteriores: List[Polygon] = field(default_factory=list)
    envolventes_exteriores: List[Polygon] = field(default_factory=list)

    @property
    def total_area_m2(self) -> float:
        return sum(r.area_m2 for r in self.rooms)


def group_rooms_by_unit_label(
    rooms: List[Room], unit_labels: List[Tuple[str, float, float]]
) -> List[Unit]:
    """Agrupa habitaciones en viviendas usando las etiquetas de vivienda reales
    del plano (MTEXT tipo 'VT1/3', 'VT2/2'...): cada habitación se asigna a la
    etiqueta VT más cercana a su centroide.

    Esto sustituye a la agrupación por proximidad espacial (más frágil) por
    la agrupación real del proyecto, tal y como la definió el arquitecto en
    el propio DXF.
    """
    if not unit_labels:
        return group_rooms_by_proximity(rooms)

    groups: Dict[str, List[Room]] = {}
    for room in rooms:
        centroid = room.polygon.centroid
        name, _, _ = min(
            unit_labels, key=lambda item: centroid.distance(Point(item[1], item[2]))
        )
        groups.setdefault(name, []).append(room)

    def unit_sort_key(name: str):
        match = re.match(r"VT\s*(\d+)(?:\s*/\s*(\d+))?", name, re.IGNORECASE)
        if match:
            primary = int(match.group(1))
            secondary = int(match.group(2)) if match.group(2) else 0
            return (0, primary, secondary)
        return (1, 0, name)

    return [Unit(name=name, rooms=groups[name]) for name in sorted(groups, key=unit_sort_key)]


MAX_GAP_BETWEEN_ROOMS_M = 2.0
"""Distancia máxima (m) entre los contornos de dos habitaciones para
considerarlas parte de la misma vivienda. Solo se usa como heurística de
respaldo (`group_rooms_by_proximity`) cuando el plano no tiene etiquetas de
vivienda ('VT<n>/<m>')."""


def group_rooms_by_proximity(
    rooms: List[Room], max_gap_m: float = MAX_GAP_BETWEEN_ROOMS_M
) -> List[Unit]:
    """Agrupa habitaciones en viviendas por componentes conexas geométricas:
    dos habitaciones pertenecen a la misma vivienda si la distancia entre sus
    contornos es <= `max_gap_m` (directamente, o a través de otras
    habitaciones intermedias). Es una aproximación; úsala solo cuando no haya
    etiquetas de vivienda fiables en el plano.
    """
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
            if rooms[i].polygon.distance(rooms[j].polygon) <= max_gap_m:
                union(i, j)

    clusters: Dict[int, List[Room]] = {}
    for i, room in enumerate(rooms):
        clusters.setdefault(find(i), []).append(room)

    def cluster_key(cluster: List[Room]):
        xs = [r.polygon.centroid.x for r in cluster]
        ys = [r.polygon.centroid.y for r in cluster]
        return (-sum(ys) / len(ys), sum(xs) / len(xs))

    ordered_clusters = sorted(clusters.values(), key=cluster_key)
    return [Unit(name=f"Vivienda {i}", rooms=c) for i, c in enumerate(ordered_clusters, start=1)]


def agrupar_por_vivienda_mas_cercana(
    geometrias: List[Polygon],
    unit_labels: List[Tuple[str, float, float]],
) -> Dict[str, List[Polygon]]:
    """Agrupa cada geometría por la etiqueta de vivienda ('VT<n>/<m>') cuyo
    punto de inserción está más cerca de su centroide -- mismo criterio que
    `group_rooms_by_unit_label` usa para las habitaciones.

    Función PURA, sin decidir nada sobre ambigüedad: no elige, no descarta,
    solo agrupa. `asignar_envolvente_cerrada` la usa para quedarse con la
    asignación cuando es inequívoca; un validador (Fase 2 del contrato de
    clasificación DXF) la usa sobre el mismo resultado para explicar por qué
    una vivienda se quedó sin envolvente o por qué una envolvente no se pudo
    asignar -- las dos leen la misma agrupación, ninguna la recalcula con
    otro criterio.

    Devuelve `{}` si falta cualquiera de los dos datos: sin geometrías no
    hay nada que agrupar, y sin etiquetas no hay con qué agrupar.
    """
    agrupadas: Dict[str, List[Polygon]] = {}
    if not geometrias or not unit_labels:
        return agrupadas
    for geometria in geometrias:
        centroide = geometria.centroid
        nombre, _, _ = min(
            unit_labels, key=lambda item: centroide.distance(Point(item[1], item[2]))
        )
        agrupadas.setdefault(nombre, []).append(geometria)
    return agrupadas


def asignar_envolvente_cerrada(
    units: List[Unit],
    envolventes: List[Polygon],
    unit_labels: List[Tuple[str, float, float]],
) -> List[Unit]:
    """Empareja cada envolvente cerrada (`AM_CONS_CER`, `PlanoLeido.envolventes_cerradas`)
    con la vivienda más cercana, y devuelve una copia de `units` con
    `envolvente_cerrada` poblado donde el emparejamiento es inequívoco.

    Es una función aparte, no un parámetro más de `group_rooms_by_unit_label`,
    a propósito: esa función tiene casi dos docenas de consumidores hoy
    (producción, `modelo/`, media suite de tests) y no hacía falta tocar su
    firma para esto -- `Unit` ya admite el campo con valor por defecto
    `None`, así que ningún llamador existente cambia de comportamiento si no
    llama a esta función.

    **Casos sin resolver en esta fase, a propósito, en vez de adivinar:**
    - Sin `unit_labels` (plano sin etiquetas VT, viviendas formadas por
      `group_rooms_by_proximity`): no hay ningún emparejamiento fiable por
      proximidad a un rótulo que no existe, así que ninguna `Unit` recibe
      envolvente aquí -- se devuelven tal cual.
    - Dos o más envolventes cuyo centroide cae más cerca de la misma
      etiqueta de vivienda: es una ambigüedad real del plano (¿dos capas
      `AM_CONS_CER` para la misma vivienda? ¿una envolvente que en realidad
      es de otra unidad?), y no se elige ninguna de las dos por descarte
      -- esa vivienda se queda con `envolvente_cerrada=None`. Explicarlo por
      qué es tarea del validador de conformidad (Fase 2), no de esta función.
    """
    if not envolventes or not unit_labels:
        return units

    asignadas = agrupar_por_vivienda_mas_cercana(envolventes, unit_labels)

    resultado: List[Unit] = []
    for unit in units:
        candidatas = asignadas.get(unit.name, [])
        envolvente_unica = candidatas[0] if len(candidatas) == 1 else None
        resultado.append(Unit(
            name=unit.name, rooms=unit.rooms, envolvente_cerrada=envolvente_unica,
            # Preserva lo que ya llevara la Unit de entrada: esta función y
            # `asignar_superficies_exteriores` pueden encadenarse en
            # cualquier orden (Fase 3, coexistencia de las 4 categorías) y
            # ninguna debe borrar lo que ya asignó la otra.
            superficies_utiles_exteriores=unit.superficies_utiles_exteriores,
            envolventes_exteriores=unit.envolventes_exteriores,
        ))
    return resultado


def asignar_superficies_exteriores(
    units: List[Unit],
    superficies_utiles_exteriores: List[Polygon],
    envolventes_exteriores: List[Polygon],
    unit_labels: List[Tuple[str, float, float]],
) -> List[Unit]:
    """Empareja las superficies útiles exteriores (`AM_UTIL_EXT`) y las
    envolventes exteriores (`AM_CONS_EXT`) con la vivienda más cercana, y
    devuelve una copia de `units` con las dos listas pobladas.

    Mismo criterio de cercanía que `asignar_envolvente_cerrada`
    (`agrupar_por_vivienda_mas_cercana`), pero SIN su lógica de unicidad: una
    vivienda con tres terrazas no es una ambigüedad, es una vivienda con tres
    terrazas -- así que aquí se asigna la lista completa de candidatas,
    nunca `None` por tener más de una. Sin `unit_labels` (plano sin
    etiquetas VT), ninguna `Unit` recibe nada, igual que
    `asignar_envolvente_cerrada`.

    Función aparte de `asignar_envolvente_cerrada`, no una ampliación de su
    firma, por la misma razón de aquella: no hacía falta tocar una función
    ya escrita para añadir dos campos más -- `Unit` ya los admite con
    `[]` por defecto.
    """
    if not unit_labels or (not superficies_utiles_exteriores and not envolventes_exteriores):
        return units

    utiles_por_vivienda = agrupar_por_vivienda_mas_cercana(superficies_utiles_exteriores, unit_labels)
    envolventes_ext_por_vivienda = agrupar_por_vivienda_mas_cercana(envolventes_exteriores, unit_labels)

    resultado: List[Unit] = []
    for unit in units:
        resultado.append(Unit(
            name=unit.name, rooms=unit.rooms, envolvente_cerrada=unit.envolvente_cerrada,
            superficies_utiles_exteriores=utiles_por_vivienda.get(unit.name, []),
            envolventes_exteriores=envolventes_ext_por_vivienda.get(unit.name, []),
        ))
    return resultado


# ---------------------------------------------------------------------------
# 2. Jerarquía de dormitorios (Dormitorio 1 > 2 > 3) dentro de cada vivienda
# ---------------------------------------------------------------------------

DORMITORIO_PATTERNS = [
    ("Dormitorio 1", re.compile(r"DORMITORIO\s*1\b")),
    ("Dormitorio 2", re.compile(r"DORMITORIO\s*2\b")),
    ("Dormitorio 3", re.compile(r"DORMITORIO\s*3\b")),
]

HIERARCHY_TOLERANCE_M2 = 0.5  # margen constructivo antes de penalizar la jerarquía


@dataclass
class HierarchyResult:
    unit_name: str
    higher_name: str
    higher_area_m2: float
    lower_name: str
    lower_area_m2: float
    passed: bool

    @property
    def message(self) -> str:
        status = "cumple" if self.passed else "NO cumple"
        return (
            f"{self.unit_name}: {status} jerarquía {self.higher_name} "
            f"({self.higher_area_m2:.2f} m²) > {self.lower_name} "
            f"({self.lower_area_m2:.2f} m²)"
        )


def _find_room_by_pattern(rooms: List[Room], pattern: "re.Pattern[str]") -> Optional[Room]:
    for room in rooms:
        if room.label and pattern.search(_normalize(room.label)):
            return room
    return None


def evaluate_dormitory_hierarchy(units: List[Unit]) -> List[HierarchyResult]:
    """Comprueba, dentro de cada vivienda, que Dormitorio 1 > Dormitorio 2 > Dormitorio 3.

    Si una vivienda no tiene alguno de los dos dormitorios de una comparación,
    esa comparación se omite (no se puede evaluar).
    """
    results: List[HierarchyResult] = []
    for unit in units:
        dorms = [
            (name, _find_room_by_pattern(unit.rooms, pattern))
            for name, pattern in DORMITORIO_PATTERNS
        ]
        for (higher_name, higher_room), (lower_name, lower_room) in zip(dorms, dorms[1:]):
            if higher_room is None or lower_room is None:
                continue
            results.append(
                HierarchyResult(
                    unit_name=unit.name,
                    higher_name=higher_name,
                    higher_area_m2=higher_room.area_m2,
                    lower_name=lower_name,
                    lower_area_m2=lower_room.area_m2,
                    passed=lower_room.area_m2 <= higher_room.area_m2 + HIERARCHY_TOLERANCE_M2,
                )
            )
    return results


# ---------------------------------------------------------------------------
# 3. Eficiencia de la vivienda: ratio superficie útil / superficie total
# ---------------------------------------------------------------------------

MIN_USEFUL_RATIO = 0.80

# Tipos de habitación que no computan como superficie útil.
NON_USEFUL_PATTERN = re.compile(r"TERRAZA|TENDEDERO")


def _superficie_suelo_agregada_m2(unit: "Unit") -> float:
    """Suma de las áreas de las piezas de la vivienda, excluyendo las que
    casan `NON_USEFUL_PATTERN` (Terraza/Tendedero).

    **Refactorización preparatoria de CAP-1, sin cambio de semántica.** Esta
    expresión estaba escrita tres veces, idéntica, en `evaluate_unit_efficiency`,
    `evaluate_unit_minimum_area` y `evaluate_circulation_efficiency`. Se ha
    unificado aquí antes de que la ocupación de DB-SI (CAP-3) se convirtiera en
    el cuarto duplicado. El cálculo es exactamente el de antes: misma geometría,
    mismo orden de suma, mismos decimales.

    **El nombre no es un descuido.** Esto NO es la «superficie útil» del DB-SI,
    que su Anejo SI A define como *«superficie en planta de un recinto, sector o
    edificio ocupable por las personas»* — una terraza lo es, y aquí se excluye.
    Tampoco es superficie construida: los recintos vienen dibujados a cara
    interior de muro, así que el espesor de los cerramientos queda fuera. Es un
    criterio propio de ArchMuse, útil para las reglas que ya lo usan y **no
    citable como magnitud normativa**; ponerle el nombre de la norma es
    justamente lo que `docs/design/DB-SI_FACT_MODEL.md` §3.5 decidió no hacer.

    Dos límites conocidos que esta función **no** corrige, porque corregirlos
    cambiaría los números de todos los proyectos ya guardados y es una decisión
    aparte (`docs/design/DB-SI_DECISIONS.md` D3, D4):

    - Es una suma, no una unión: donde dos polígonos se solapan, los metros se
      cuentan dos veces. `evaluate_room_overlap` lo detecta y lo dice.
    - Depende del rótulo del plano, no de una propiedad del recinto.
    """
    return sum(
        r.area_m2
        for r in unit.rooms
        if not (r.label and NON_USEFUL_PATTERN.search(_normalize(r.label)))
    )


@dataclass
class EfficiencyResult:
    unit_name: str
    total_area_m2: float
    useful_area_m2: float
    ratio: float
    passed: bool

    @property
    def message(self) -> str:
        status = "cumple" if self.passed else "NO cumple"
        return (
            f"{self.unit_name}: {status} ratio útil/total "
            f"{self.ratio * 100:.1f}% (útil {self.useful_area_m2:.2f} m² / "
            f"total {self.total_area_m2:.2f} m², mínimo {MIN_USEFUL_RATIO * 100:.0f}%)"
        )


def evaluate_unit_efficiency(units: List[Unit]) -> List[EfficiencyResult]:
    """Calcula, por vivienda, el ratio entre superficie útil y superficie total."""
    results: List[EfficiencyResult] = []
    for unit in units:
        total_area = unit.total_area_m2
        if total_area <= 0:
            continue
        useful_area = _superficie_suelo_agregada_m2(unit)
        ratio = useful_area / total_area
        results.append(
            EfficiencyResult(
                unit_name=unit.name,
                total_area_m2=total_area,
                useful_area_m2=useful_area,
                ratio=ratio,
                passed=ratio >= MIN_USEFUL_RATIO,
            )
        )
    return results


# ---------------------------------------------------------------------------
# 4. Orientación solar
# ---------------------------------------------------------------------------

# (nombre descriptivo, patrón, orientaciones óptimas, orientaciones penalizadas)
ORIENTATION_RULES = [
    ("Salón/Cocina", re.compile(r"SALON|COCINA"), {"S", "SO"}, {"N"}),
    ("Dormitorio 1", re.compile(r"DORMITORIO\s*1\b"), {"E", "S"}, {"N"}),
    ("Dormitorio 2", re.compile(r"DORMITORIO\s*2\b"), {"E", "S"}, {"N"}),
    ("Dormitorio 3", re.compile(r"DORMITORIO\s*3\b"), set(), {"N"}),
    ("Baño", re.compile(r"BANO"), set(), {"N"}),
    ("Aseo", re.compile(r"ASEO"), set(), {"N"}),
    ("Tendedero", re.compile(r"TENDEDERO"), {"S"}, {"N"}),
]

COMPASS_POINTS = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]


def _bearing_to_compass(bearing_deg: float) -> str:
    index = round(bearing_deg / 45) % 8
    return COMPASS_POINTS[index]


def _building_centroid(rooms: List[Room]) -> Point:
    xs = [r.polygon.centroid.x for r in rooms]
    ys = [r.polygon.centroid.y for r in rooms]
    return Point(sum(xs) / len(xs), sum(ys) / len(ys))


def _long_edge_midpoints(polygon: Polygon) -> Optional[Tuple[Point, Point, Point]]:
    """Centro y puntos medios de los dos lados largos (opuestos) del
    rectángulo mínimo que envuelve el polígono."""
    min_rect = polygon.minimum_rotated_rectangle
    if min_rect.geom_type != "Polygon":
        return None
    coords = list(min_rect.exterior.coords)[:-1]
    if len(coords) != 4:
        return None

    p0, p1, p2, p3 = (Point(c) for c in coords)
    len01 = p0.distance(p1)
    len12 = p1.distance(p2)
    if len01 >= len12:
        edge_a, edge_b = (p0, p1), (p2, p3)
    else:
        edge_a, edge_b = (p1, p2), (p3, p0)

    mid_a = Point((edge_a[0].x + edge_a[1].x) / 2, (edge_a[0].y + edge_a[1].y) / 2)
    mid_b = Point((edge_b[0].x + edge_b[1].x) / 2, (edge_b[0].y + edge_b[1].y) / 2)
    center = Point((coords[0][0] + coords[2][0]) / 2, (coords[0][1] + coords[2][1]) / 2)
    return center, mid_a, mid_b


def _facade_bearing_deg(
    room: Room, all_rooms: List[Room], norte_grados: float, building_center: Point
) -> Optional[float]:
    """Azimut (0=Norte, 90=Este...) hacia el que da la fachada más larga de
    la habitación.

    La fachada más larga de un rectángulo tiene dos lados opuestos posibles;
    para decidir cuál de los dos es el exterior (la fachada real) se
    comprueba, justo al otro lado de cada uno, si hay otra habitación: si la
    hay, ese lado es un tabique interior y la fachada es el lado opuesto. Si
    ninguno de los dos linda con otra habitación (caso ambiguo, p.ej. una
    habitación exenta), se usa como desempate el lado que se aleja más del
    centro del edificio.
    """
    edges = _long_edge_midpoints(room.polygon)
    if edges is None:
        return None
    center, mid_a, mid_b = edges

    def unit_normal(mid: Point) -> Tuple[float, float]:
        dx, dy = mid.x - center.x, mid.y - center.y
        length = math.hypot(dx, dy)
        if length == 0:
            return (0.0, 0.0)
        return (dx / length, dy / length)

    dir_a, dir_b = unit_normal(mid_a), unit_normal(mid_b)

    eps = 0.3
    point_a = Point(mid_a.x + dir_a[0] * eps, mid_a.y + dir_a[1] * eps)
    point_b = Point(mid_b.x + dir_b[0] * eps, mid_b.y + dir_b[1] * eps)

    others = [r.polygon for r in all_rooms if r is not room]
    a_is_interior = any(poly.contains(point_a) for poly in others)
    b_is_interior = any(poly.contains(point_b) for poly in others)

    if a_is_interior and not b_is_interior:
        facing = dir_b
    elif b_is_interior and not a_is_interior:
        facing = dir_a
    else:
        away_a = (mid_a.x - building_center.x, mid_a.y - building_center.y)
        away_b = (mid_b.x - building_center.x, mid_b.y - building_center.y)
        dot_a = dir_a[0] * away_a[0] + dir_a[1] * away_a[1]
        dot_b = dir_b[0] * away_b[0] + dir_b[1] * away_b[1]
        facing = dir_a if dot_a >= dot_b else dir_b

    # atan2(dx, dy) da el ángulo respecto al eje +Y del plano, en sentido
    # horario (0=+Y, 90=+X), que es la convención de azimut si 'arriba'=Norte.
    plan_bearing = math.degrees(math.atan2(facing[0], facing[1])) % 360
    return (plan_bearing + norte_grados) % 360


@dataclass
class OrientationResult:
    room: Room
    bearing_deg: float
    compass: str
    rating: str  # "óptima" | "aceptable" | "penalizada" | "sin regla"
    note: str

    @property
    def room_label(self) -> str:
        return self.room.label or "(sin etiqueta)"

    @property
    def message(self) -> str:
        return (
            f"{self.room_label}: fachada larga orientada a {self.compass} "
            f"({self.bearing_deg:.0f}°) — {self.note}"
        )


def evaluate_orientation(rooms: List[Room], norte_grados: float = 0.0) -> List[OrientationResult]:
    """Evalúa la orientación de la fachada más larga de cada habitación.

    `norte_grados` es el azimut (grados, sentido horario, 0=Norte) hacia el
    que apunta 'arriba' (+Y) en el plano DXF. Con el valor por defecto (0),
    'arriba' se interpreta directamente como Norte.
    """
    if not rooms:
        return []

    building_center = _building_centroid(rooms)
    results: List[OrientationResult] = []

    for room in rooms:
        bearing = _facade_bearing_deg(room, rooms, norte_grados, building_center)
        if bearing is None:
            continue
        compass = _bearing_to_compass(bearing)

        applicable = None
        if room.label:
            normalized = _normalize(room.label)
            for rule_name, pattern, optimal, penalized in ORIENTATION_RULES:
                if pattern.search(normalized):
                    applicable = (rule_name, optimal, penalized)
                    break

        if applicable is None:
            rating = "sin regla"
            note = "Sin regla de orientación definida para este tipo de habitación."
        else:
            rule_name, optimal, penalized = applicable
            ideal = "/".join(sorted(optimal))
            # Con `optimal` vacío (p. ej. Dormitorio 3, Baño, Aseo: permisivos
            # en óptima a propósito) no tiene sentido mostrar "(ideal: )" en
            # blanco — se omite esa parte del mensaje por completo.
            ideal_part = f" (ideal: {ideal})" if ideal else ""
            if compass in optimal:
                rating = "óptima"
                note = f"Orientación {compass} óptima para {rule_name}{ideal_part}."
            elif compass in penalized:
                rating = "penalizada"
                evitar = "/".join(sorted(penalized))
                ideal_suffix = f"; ideal: {ideal}" if ideal else ""
                note = f"Orientación {compass} desaconsejada para {rule_name} (evitar: {evitar}{ideal_suffix})."
            else:
                rating = "aceptable"
                note = f"Orientación {compass} aceptable para {rule_name}{ideal_part}."

        results.append(
            OrientationResult(
                room=room, bearing_deg=bearing, compass=compass, rating=rating, note=note
            )
        )

    return results


# ---------------------------------------------------------------------------
# 5. Ventilación natural: habitaciones habitables sin fachada exterior
# ---------------------------------------------------------------------------


def _room_has_exterior_facade(room: Room, all_rooms: List[Room]) -> bool:
    """True si al menos uno de los dos lados largos del rectángulo mínimo
    de `room` NO linda con otra habitación de `all_rooms` — misma técnica
    de detección interior/exterior que `_facade_bearing_deg` (un punto
    justo al otro lado del lado, comprobando si cae dentro de otro
    polígono), pero aquí interesan los DOS lados, no solo cuál se reporta
    como "la fachada" cuando ambos son ambiguos."""
    edges = _long_edge_midpoints(room.polygon)
    if edges is None:
        return True  # geometría degenerada: no se puede evaluar, no se penaliza

    center, mid_a, mid_b = edges

    def unit_normal(mid: Point) -> Tuple[float, float]:
        dx, dy = mid.x - center.x, mid.y - center.y
        length = math.hypot(dx, dy)
        if length == 0:
            return (0.0, 0.0)
        return (dx / length, dy / length)

    eps = 0.3
    others = [r.polygon for r in all_rooms if r is not room]

    for mid in (mid_a, mid_b):
        dx, dy = unit_normal(mid)
        point = Point(mid.x + dx * eps, mid.y + dy * eps)
        if not any(poly.contains(point) for poly in others):
            return True
    return False


@dataclass
class NaturalLightResult:
    room: Room
    room_label: Optional[str]
    has_exterior_facade: bool

    @property
    def passed(self) -> bool:
        return self.has_exterior_facade

    @property
    def message(self) -> str:
        label = self.room_label or "(sin etiqueta)"
        return f"{label}: sin ventilación posible — no da a fachada exterior (CTE DB-HS3)"


_NATURAL_LIGHT_PATTERNS = [re.compile(r"SALON|COCINA")] + [pattern for _, pattern in DORMITORIO_PATTERNS]


def evaluate_natural_light(unit: Unit) -> List[NaturalLightResult]:
    """Comprueba que cada Salón/cocina y Dormitorio 1/2/3 de `unit` tenga
    al menos un lado largo que sea fachada exterior (no un tabique
    compartido con otra habitación de la misma vivienda)."""
    results: List[NaturalLightResult] = []
    for room in unit.rooms:
        if not room.label:
            continue
        normalized = _normalize(room.label)
        if not any(pattern.search(normalized) for pattern in _NATURAL_LIGHT_PATTERNS):
            continue
        has_facade = _room_has_exterior_facade(room, unit.rooms)
        results.append(
            NaturalLightResult(room=room, room_label=room.label, has_exterior_facade=has_facade)
        )
    return results


# ---------------------------------------------------------------------------
# 6. Anchura mínima de pasillo (CTE DB-SUA)
# ---------------------------------------------------------------------------


@dataclass
class CorridorWidthResult:
    room: Room
    room_label: Optional[str]
    short_side_m: float
    min_width_m: float
    passed: bool

    @property
    def message(self) -> str:
        label = self.room_label or "(sin etiqueta)"
        return (
            f"{label}: anchura {self.short_side_m:.2f}m insuficiente "
            f"— mínimo {self.min_width_m}m (CTE DB-SUA)"
        )


def evaluate_corridor_width(unit: Unit, tipologia: str = "plurifamiliar") -> List[CorridorWidthResult]:
    """Comprueba que cada 'Pasillo' de la vivienda tenga al menos el ancho
    mínimo de paso de personas (CTE DB-SUA) en su lado corto. El mínimo
    depende de la tipología (`UMBRALES_TIPOLOGIA["corridor_width_min"]`;
    definido más abajo en el archivo — se usa el literal "plurifamiliar"
    como default aquí, no la constante `DEFAULT_TIPOLOGIA`, para evitar una
    referencia hacia delante).

    **No citar DB-SI 3 apartado 4 aquí** (`docs/audits/DB-SI_REVIEW.md`
    §3.2, ficha C10, revisado en el Bloque B): ese apartado dimensiona los
    pasillos COMUNES de evacuación, no el pasillo interior de una vivienda
    — en Residencial Vivienda el origen de evacuación se sitúa en la
    puerta de la vivienda (Anejo SI A), así que el DB-SI no dimensiona lo
    que hay dentro. El mínimo de esta regla es materia de habitabilidad
    autonómica (`CTE-DB-SUA-1`, ya correcto), no del CTE DB-SI. Si en el
    futuro alguien "refuerza" esta cita hacia DB-SI 3.4, es un error, no
    una mejora.

    E3.4 — el lado corto se pide a `AlmacenGeometria.lado_menor_m`, no a
    `_bounding_sides` (que sigue existiendo para `spatial_quality.py`). Ver
    el docstring de `evaluate_proportions` para el criterio."""
    min_width_m = UMBRALES_TIPOLOGIA.get(tipologia, UMBRALES_TIPOLOGIA["plurifamiliar"])["corridor_width_min"]
    results: List[CorridorWidthResult] = []
    almacen = AlmacenGeometria()
    for room in unit.rooms:
        if not room.label or "PASILLO" not in _normalize(room.label):
            continue
        geom_id = almacen.insertar(room.polygon, HUELLA_2D, unidad="m")
        short_side = almacen.lado_menor_m(geom_id)
        results.append(
            CorridorWidthResult(
                room=room,
                room_label=room.label,
                short_side_m=short_side,
                min_width_m=min_width_m,
                passed=short_side >= min_width_m,
            )
        )
    return results


# ---------------------------------------------------------------------------
# 7. Superficie mínima de vivienda (LOE / normativa autonómica general)
# ---------------------------------------------------------------------------

# Umbrales por tipología de proyecto (ver params["proyecto"]["tipologia"]
# en app.py). "plurifamiliar" reproduce los valores históricos de esta app
# (fallback si `tipologia` no se reconoce).
UMBRALES_TIPOLOGIA = {
    "plurifamiliar": {
        "min_unit_area_m2": 30.0, "bathroom_ratio_strict": True,
        "corridor_width_min": 0.90, "turning_space_min": 1.50,
    },
    "unifamiliar": {
        "min_unit_area_m2": 40.0, "bathroom_ratio_strict": False,
        "corridor_width_min": 0.80, "turning_space_min": 1.20,
    },
    "rehabilitacion": {
        "min_unit_area_m2": 24.0, "bathroom_ratio_strict": False,
        "corridor_width_min": 0.80, "turning_space_min": 1.20,
    },
}
DEFAULT_TIPOLOGIA = "plurifamiliar"


def _umbrales_tipologia(tipologia: str) -> dict:
    return UMBRALES_TIPOLOGIA.get(tipologia, UMBRALES_TIPOLOGIA[DEFAULT_TIPOLOGIA])


@dataclass
class UnitMinimumAreaResult:
    unit_name: str
    useful_area_m2: float
    min_area_m2: float
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"Vivienda: superficie útil {self.useful_area_m2:.1f}m² por debajo "
            f"del mínimo legal de {self.min_area_m2:.0f}m²"
        )


def evaluate_unit_minimum_area(unit: Unit, tipologia: str = DEFAULT_TIPOLOGIA) -> UnitMinimumAreaResult:
    """Comprueba que la superficie útil total de la vivienda (todo excepto
    Terraza/Tendedero, igual criterio que `evaluate_unit_efficiency`)
    alcance el mínimo legal de vivienda. El mínimo depende de la tipología
    (`UMBRALES_TIPOLOGIA`)."""
    useful_area = _superficie_suelo_agregada_m2(unit)
    min_area = _umbrales_tipologia(tipologia)["min_unit_area_m2"]
    return UnitMinimumAreaResult(
        unit_name=unit.name,
        useful_area_m2=useful_area,
        min_area_m2=min_area,
        passed=useful_area >= min_area,
    )


# ---------------------------------------------------------------------------
# 8. Accesibilidad de baño (CTE DB-SUA: espacio mínimo de giro)
# ---------------------------------------------------------------------------

ACCESSIBLE_BATHROOM_MIN_SHORT_M = 1.2
ACCESSIBLE_BATHROOM_MIN_LONG_M = 1.8

_BANO_ROOM_PATTERN = re.compile(r"BANO")


@dataclass
class BathroomAccessibilityResult:
    unit_name: str
    has_accessible_bathroom: bool

    @property
    def passed(self) -> bool:
        return self.has_accessible_bathroom

    @property
    def message(self) -> str:
        return (
            "Baño: dimensiones insuficientes para accesibilidad — mínimo "
            f"{ACCESSIBLE_BATHROOM_MIN_SHORT_M}×{ACCESSIBLE_BATHROOM_MIN_LONG_M}m (CTE DB-SUA)"
        )


def evaluate_bathroom_accessibility(unit: Unit) -> Optional[BathroomAccessibilityResult]:
    """Comprueba que al menos un Baño de la vivienda tenga espacio mínimo
    de giro accesible (CTE DB-SUA, 1.2x1.8m). Si la vivienda no tiene
    ningún Baño, no se evalúa (esa carencia la cubre `evaluate_bathroom_ratio`)."""
    banos = [r for r in unit.rooms if r.label and _BANO_ROOM_PATTERN.search(_normalize(r.label))]
    if not banos:
        return None

    def _is_accessible(room: Room) -> bool:
        long_side, short_side = _bounding_sides(room.polygon)
        return short_side >= ACCESSIBLE_BATHROOM_MIN_SHORT_M and long_side >= ACCESSIBLE_BATHROOM_MIN_LONG_M

    return BathroomAccessibilityResult(
        unit_name=unit.name,
        has_accessible_bathroom=any(_is_accessible(r) for r in banos),
    )


# ---------------------------------------------------------------------------
# 9. Ratio dormitorios/baños
# ---------------------------------------------------------------------------

_ASEO_ROOM_PATTERN = re.compile(r"ASEO")
_DORMITORIO_ANY_PATTERN = re.compile(r"DORMITORIO")


@dataclass
class BathroomRatioResult:
    unit_name: str
    n_dormitorios: int
    n_banos: int
    missing_description: str
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"Vivienda: {self.n_dormitorios} dormitorios pero solo {self.n_banos} baño(s) "
            f"— se recomienda añadir {self.missing_description}"
        )


def evaluate_bathroom_ratio(unit: Unit, tipologia: str = DEFAULT_TIPOLOGIA) -> Optional[BathroomRatioResult]:
    """1-2 dormitorios -> mínimo 1 Baño (exigido en cualquier tipología).
    3+ dormitorios -> además, mínimo 1 Aseo — pero solo si la tipología es
    "estricta" (`UMBRALES_TIPOLOGIA["bathroom_ratio_strict"]`; hoy solo
    plurifamiliar): en unifamiliar/rehabilitación no se exige el Aseo
    adicional, un único Baño compartido es habitual y aceptable en esos
    casos. Si la vivienda no tiene ningún dormitorio (p. ej. un local
    comercial), la regla no aplica (devuelve None)."""
    n_dorm = sum(
        1 for r in unit.rooms if r.label and _DORMITORIO_ANY_PATTERN.search(_normalize(r.label))
    )
    if n_dorm <= 0:
        return None

    n_banos = sum(1 for r in unit.rooms if r.label and _BANO_ROOM_PATTERN.search(_normalize(r.label)))
    n_aseos = sum(1 for r in unit.rooms if r.label and _ASEO_ROOM_PATTERN.search(_normalize(r.label)))
    strict = _umbrales_tipologia(tipologia)["bathroom_ratio_strict"]

    missing = []
    if n_banos < 1:
        missing.append("un Baño")
    if strict and n_dorm >= 3 and n_aseos < 1:
        missing.append("un Aseo")

    return BathroomRatioResult(
        unit_name=unit.name,
        n_dormitorios=n_dorm,
        n_banos=n_banos,
        missing_description=" y ".join(missing),
        passed=not missing,
    )


# ---------------------------------------------------------------------------
# 10. Horas de sol estimadas (orientación solar avanzada)
# ---------------------------------------------------------------------------

# (verano, invierno) en horas, por punto cardinal — latitud media España ~40°N.
SOLAR_HOURS_TABLE = {
    "S": (6.0, 6.0),
    "SE": (5.0, 5.0),
    "SO": (5.0, 5.0),
    "E": (4.0, 3.0),
    "O": (4.0, 3.0),
    "NE": (2.0, 1.0),
    "NO": (2.0, 1.0),
    "N": (0.0, 0.0),
}

# Umbrales por zona climática CTE DB-HE (A-E, ver analyzer/cte_zonas.py).
# A/B (clima suave): más permisivos. C: valores históricos de esta app
# (fallback si `zona_cte` no se reconoce). D/E (clima severo): más exigentes.
UMBRALES_ZONA = {
    "A": {"compact_ratio_min": 1.2, "solar_hours_good_winter": 3.0, "solar_hours_acceptable_winter": 1.5},
    "B": {"compact_ratio_min": 1.3, "solar_hours_good_winter": 3.5, "solar_hours_acceptable_winter": 1.5},
    "C": {"compact_ratio_min": 1.5, "solar_hours_good_winter": 4.0, "solar_hours_acceptable_winter": 2.0},
    "D": {"compact_ratio_min": 1.8, "solar_hours_good_winter": 4.5, "solar_hours_acceptable_winter": 2.5},
    "E": {"compact_ratio_min": 2.0, "solar_hours_good_winter": 5.0, "solar_hours_acceptable_winter": 3.0},
}
DEFAULT_ZONA_CTE = "C"


def _umbrales_zona(zona_cte: str) -> dict:
    return UMBRALES_ZONA.get(zona_cte, UMBRALES_ZONA[DEFAULT_ZONA_CTE])


_SOLAR_HOURS_PATTERNS = [re.compile(r"SALON|COCINA")] + [pattern for _, pattern in DORMITORIO_PATTERNS]


@dataclass
class SolarHoursResult:
    room: Room
    room_label: str
    compass: str
    hours_summer: float
    hours_winter: float
    rating: str  # "bueno" | "aceptable" | "deficiente"

    @property
    def message(self) -> str:
        return (
            f"{self.room_label}: estimación {self.hours_winter:.0f}h de sol en invierno "
            "— orientación deficiente para vivienda en España"
        )


def evaluate_solar_hours(
    unit: Unit, norte_grados: float = 0.0, zona_cte: str = DEFAULT_ZONA_CTE
) -> List[SolarHoursResult]:
    """Estima horas de sol directo (verano/invierno, latitud media España
    ~40°N) de cada Salón/cocina y Dormitorio 1/2/3 de la vivienda, a partir
    de la misma técnica de detección de fachada que usa `evaluate_orientation`
    (recalculada aquí con las habitaciones de `unit` como único contexto de
    vecinos — no evalúa Baño/Aseo/Pasillo). Los umbrales de horas "buenas"/
    "aceptables" dependen de la zona climática CTE (`UMBRALES_ZONA`)."""
    if not unit.rooms:
        return []

    umbrales = _umbrales_zona(zona_cte)
    building_center = _building_centroid(unit.rooms)
    results: List[SolarHoursResult] = []
    for room in unit.rooms:
        if not room.label:
            continue
        normalized = _normalize(room.label)
        if not any(pattern.search(normalized) for pattern in _SOLAR_HOURS_PATTERNS):
            continue

        bearing = _facade_bearing_deg(room, unit.rooms, norte_grados, building_center)
        if bearing is None:
            continue
        compass = _bearing_to_compass(bearing)
        hours_summer, hours_winter = SOLAR_HOURS_TABLE.get(compass, (0.0, 0.0))

        if hours_winter >= umbrales["solar_hours_good_winter"]:
            rating = "bueno"
        elif hours_winter >= umbrales["solar_hours_acceptable_winter"]:
            rating = "aceptable"
        else:
            rating = "deficiente"

        results.append(
            SolarHoursResult(
                room=room,
                room_label=room.label,
                compass=compass,
                hours_summer=hours_summer,
                hours_winter=hours_winter,
                rating=rating,
            )
        )
    return results


# ---------------------------------------------------------------------------
# 11. Ventilación cruzada
# ---------------------------------------------------------------------------

_CROSS_VENTILATION_PATTERNS = [re.compile(r"SALON|COCINA")] + [pattern for _, pattern in DORMITORIO_PATTERNS]


@dataclass
class CrossVentilationResult:
    unit_name: str
    compasses: List[str]
    passed: bool

    @property
    def message(self) -> str:
        return "Vivienda: sin ventilación cruzada — todas las fachadas orientadas al mismo lado"


def _are_opposite_or_perpendicular(compass_a: str, compass_b: str) -> bool:
    """True si dos puntos cardinales (de los 8 de `COMPASS_POINTS`) están
    opuestos (180°, p. ej. N-S) o perpendiculares (90°, p. ej. N-E)."""
    idx_a = COMPASS_POINTS.index(compass_a)
    idx_b = COMPASS_POINTS.index(compass_b)
    diff = abs(idx_a - idx_b) % 8
    diff = min(diff, 8 - diff)
    return diff in (2, 4)


def evaluate_cross_ventilation(unit: Unit, norte_grados: float = 0.0) -> Optional[CrossVentilationResult]:
    """Comprueba que la vivienda tenga al menos dos habitaciones habitables
    (Salón/cocina o Dormitorio) con fachada exterior en orientaciones
    opuestas o perpendiculares entre sí — condición necesaria para la
    ventilación cruzada. Igual que `evaluate_solar_hours`, recalcula la
    fachada usando solo las habitaciones de `unit` como contexto de vecinos.
    Si la vivienda no tiene ninguna habitación habitable (p. ej. un local
    comercial), la regla no aplica (devuelve None)."""
    habitable_rooms = [
        r for r in unit.rooms
        if r.label and any(p.search(_normalize(r.label)) for p in _CROSS_VENTILATION_PATTERNS)
    ]
    if not habitable_rooms:
        return None

    building_center = _building_centroid(unit.rooms)
    compasses: List[str] = []
    for room in habitable_rooms:
        if not _room_has_exterior_facade(room, unit.rooms):
            continue
        bearing = _facade_bearing_deg(room, unit.rooms, norte_grados, building_center)
        if bearing is None:
            continue
        compasses.append(_bearing_to_compass(bearing))

    passed = any(
        _are_opposite_or_perpendicular(compasses[i], compasses[j])
        for i in range(len(compasses))
        for j in range(i + 1, len(compasses))
    )
    return CrossVentilationResult(unit_name=unit.name, compasses=compasses, passed=passed)


# ---------------------------------------------------------------------------
# 12. Recorrido entrada-dormitorio (informativo)
# ---------------------------------------------------------------------------

MAX_ENTRY_DISTANCE_M = 5.0
_PASILLO_PATTERN = re.compile(r"PASILLO")


@dataclass
class EntryDistanceResult:
    room: Room
    room_label: str
    distance_m: float
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"{self.room_label}: acceso largo desde entrada — "
            f"{self.distance_m:.1f}m hasta el pasillo (recomendado < {MAX_ENTRY_DISTANCE_M}m)"
        )


def evaluate_entry_distance(unit: Unit) -> List[EntryDistanceResult]:
    """Estima, para cada Dormitorio de la vivienda, la distancia desde su
    centroide hasta el centroide del Pasillo — proxy geométrico del
    recorrido entrada→dormitorio (el modelo no tiene datos de puertas ni
    de circulación real). Informativo: no participa en `score_pct`, igual
    que `evaluate_solar_hours`. Si la vivienda no tiene Pasillo, no se
    puede evaluar (lista vacía)."""
    pasillo = _find_room_by_pattern(unit.rooms, _PASILLO_PATTERN)
    if pasillo is None:
        return []

    results: List[EntryDistanceResult] = []
    for room in unit.rooms:
        if not room.label:
            continue
        normalized = _normalize(room.label)
        if not any(pattern.search(normalized) for _, pattern in DORMITORIO_PATTERNS):
            continue
        distance = room.polygon.centroid.distance(pasillo.polygon.centroid)
        results.append(
            EntryDistanceResult(
                room=room,
                room_label=room.label,
                distance_m=distance,
                passed=distance <= MAX_ENTRY_DISTANCE_M,
            )
        )
    return results


# ---------------------------------------------------------------------------
# 13. Jerarquía espacial: Salón/cocina debe ser la pieza mayor
# ---------------------------------------------------------------------------

_SALON_PATTERN = re.compile(r"SALON|COCINA")


@dataclass
class SpatialHierarchyResult:
    unit_name: str
    salon_area_m2: float
    dormitorio1_area_m2: float
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"Jerarquía: Dormitorio 1 ({self.dormitorio1_area_m2:.1f}m²) mayor "
            f"que Salón/cocina ({self.salon_area_m2:.1f}m²) — el salón debe "
            "ser la pieza principal"
        )


def evaluate_spatial_hierarchy(unit: Unit) -> Optional[SpatialHierarchyResult]:
    """Comprueba que el Salón/cocina sea la pieza mayor de la vivienda.
    Complementa a `evaluate_dormitory_hierarchy` (que solo ordena los
    dormitorios entre sí) con la pieza principal de la vivienda. Si falta
    el Salón/cocina o el Dormitorio 1, la regla no aplica (devuelve None)."""
    salon = _find_room_by_pattern(unit.rooms, _SALON_PATTERN)
    dorm1 = _find_room_by_pattern(unit.rooms, DORMITORIO_PATTERNS[0][1])
    if salon is None or dorm1 is None:
        return None
    return SpatialHierarchyResult(
        unit_name=unit.name,
        salon_area_m2=salon.area_m2,
        dormitorio1_area_m2=dorm1.area_m2,
        passed=salon.area_m2 >= dorm1.area_m2,
    )


# ---------------------------------------------------------------------------
# 14. Eficiencia de circulación (informativo)
# ---------------------------------------------------------------------------

MAX_CIRCULATION_RATIO = 0.15


@dataclass
class CirculationEfficiencyResult:
    unit_name: str
    corridor_area_m2: float
    useful_area_m2: float
    ratio: float
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"Circulación: el pasillo ocupa {self.ratio * 100:.0f}% de la "
            f"superficie útil — recomendado < {MAX_CIRCULATION_RATIO * 100:.0f}%"
        )


def evaluate_circulation_efficiency(unit: Unit) -> Optional[CirculationEfficiencyResult]:
    """Ratio entre la superficie de Pasillo y la superficie útil total de
    la vivienda (mismo criterio de superficie útil que
    `evaluate_unit_efficiency`: excluye Terraza/Tendedero). Informativo:
    no participa en `score_pct`. Si la vivienda no tiene Pasillo o no
    tiene superficie útil, no se evalúa (devuelve None)."""
    corridor_area = sum(
        r.area_m2 for r in unit.rooms if r.label and _PASILLO_PATTERN.search(_normalize(r.label))
    )
    if corridor_area <= 0:
        return None

    useful_area = _superficie_suelo_agregada_m2(unit)
    if useful_area <= 0:
        return None

    ratio = corridor_area / useful_area
    return CirculationEfficiencyResult(
        unit_name=unit.name,
        corridor_area_m2=corridor_area,
        useful_area_m2=useful_area,
        ratio=ratio,
        passed=ratio <= MAX_CIRCULATION_RATIO,
    )


# ---------------------------------------------------------------------------
# 15. Iluminación natural avanzada: profundidad y factor de luz natural
# ---------------------------------------------------------------------------

MAX_ROOM_DEPTH_M = 6.0
MIN_NATURAL_LIGHT_FACTOR_PCT = 1.5

# Estimación de la superficie de hueco. El DXF no trae carpintería, así que
# hay que suponerla, y son DOS suposiciones independientes, no una:
#   - qué fracción del ANCHO de fachada ocupa el hueco, y
#   - qué altura libre tiene ese hueco.
# Antes de 2026-08-05 solo existía la primera y el resultado —en metros— se
# comparaba, bajo el nombre `window_area_m2`, contra umbrales expresados en
# porcentaje de SUPERFICIE. Eran magnitudes de dimensión distinta: metros
# divididos entre metros cuadrados. La regla seguía ordenando bien las
# habitaciones (penalizaba las profundas frente a las anchas), pero el número
# que enseñaba no era el que decía ser, y el umbral legal de 1/8 no se estaba
# comprobando de verdad.
WINDOW_TO_FACADE_RATIO = 0.25  # fracción del ancho de fachada ocupada por hueco
ALTURA_HUECO_ESTIMADA_M = 1.30  # antepecho ~0.90m, dintel ~2.20m


def _superficie_hueco_estimada_m2(ancho_fachada_m: float) -> float:
    """Superficie de hueco estimada de una pieza, en m² de verdad.

    Único sitio donde se estima un hueco en todo el módulo: los Bloques 15
    (`NaturalLightFactorResult`) y 19 (`WindowOpeningRatioResult`) comparten
    esta estimación y difieren solo en el umbral contra el que la comparan.
    Tenerla en una función y no repetida en los dos sitios es lo que evita
    que vuelvan a divergir.

    ADVERTENCIA para quien lea un resultado que salga de aquí: el valor
    depende íntegramente de dos constantes supuestas, ninguna medible en un
    DXF. Un cambio del 10% en cualquiera de las dos mueve el resultado un
    10%, y varias piezas de un plano real caen a menos de medio punto
    porcentual del umbral de 1/8. Es una estimación con la que se puede
    ordenar y priorizar; no es una medición de carpintería.
    """
    return ancho_fachada_m * WINDOW_TO_FACADE_RATIO * ALTURA_HUECO_ESTIMADA_M


_NATURAL_LIGHTING_PATTERNS = [re.compile(r"SALON|COCINA")] + [pattern for _, pattern in DORMITORIO_PATTERNS]


@dataclass
class RoomDepthResult:
    room: Room
    room_label: str
    depth_m: float
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"{self.room_label}: profundidad {self.depth_m:.1f}m excede el "
            f"máximo de {MAX_ROOM_DEPTH_M}m para iluminación natural adecuada"
        )


@dataclass
class NaturalLightFactorResult:
    room: Room
    room_label: str
    fln_pct: float
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"{self.room_label}: factor de luz natural estimado {self.fln_pct:.1f}% "
            f"por debajo del mínimo recomendado de {MIN_NATURAL_LIGHT_FACTOR_PCT}% "
            "(CTE DB-HE)"
        )


@dataclass
class NaturalLightingAnalysis:
    depth_results: List[RoomDepthResult] = field(default_factory=list)
    factor_results: List[NaturalLightFactorResult] = field(default_factory=list)


def evaluate_natural_lighting(unit: Unit) -> NaturalLightingAnalysis:
    """Dos comprobaciones de iluminación natural para cada Salón/cocina y
    Dormitorio 1/2/3 de `unit` con fachada exterior (las que no la tienen ya
    las penaliza `evaluate_natural_light`, no se duplica aquí):

    1. Profundidad: la fachada de una habitación es siempre su lado largo
       (misma convención que `_facade_bearing_deg`/`_long_edge_midpoints`),
       así que la profundidad perpendicular a esa fachada es el lado corto
       del rectángulo mínimo (`_bounding_sides`). No debe superar
       `MAX_ROOM_DEPTH_M`.
    2. RETIRADA (2026-08-05). El "factor de luz natural" comparaba la misma
       superficie de hueco estimada que el Bloque 19 contra un umbral del
       1,5%, mientras el Bloque 19 la compara contra 1/8 (12,5%). Medido
       sobre `ejemplo.dxf`, los valores reales caen entre el 5% y el 17%: el
       umbral del 1,5% **no puede fallar nunca** y el del 12,5% falla casi
       siempre. Eran dos reglas sobre la misma medida, una vacua y otra
       exigente, y la vacua aportaba 16 aprobados gratis a la puntuación de
       cada análisis.

       Además, el nombre era incorrecto: el factor de luz natural es una
       magnitud fotométrica (iluminancia interior frente a exterior), no el
       cociente hueco/suelo. Calcularlo así y llamarlo FLN era prometer una
       medida que nunca se hizo.

       Se conserva `factor_results` como lista vacía para no romper el
       contrato del JSON ni de los consumidores. La comprobación de hueco
       vive ahora en un solo sitio: el Bloque 19.
    """
    depth_results: List[RoomDepthResult] = []
    factor_results: List[NaturalLightFactorResult] = []

    for room in unit.rooms:
        if not room.label:
            continue
        normalized = _normalize(room.label)
        if not any(pattern.search(normalized) for pattern in _NATURAL_LIGHTING_PATTERNS):
            continue
        if not _room_has_exterior_facade(room, unit.rooms):
            continue

        long_side, short_side = _bounding_sides(room.polygon)
        if short_side <= 0 or room.area_m2 <= 0:
            continue

        depth_m = short_side
        depth_results.append(
            RoomDepthResult(
                room=room,
                room_label=room.label,
                depth_m=depth_m,
                passed=depth_m <= MAX_ROOM_DEPTH_M,
            )
        )

    # `factor_results` se queda vacío a propósito desde 2026-08-05: ver la
    # nota de retirada del "factor de luz natural" sobre esta función.
    return NaturalLightingAnalysis(depth_results=depth_results, factor_results=factor_results)


# ---------------------------------------------------------------------------
# 16. Acústica básica: adyacencia ruidosa y exposición a ruido exterior
# ---------------------------------------------------------------------------

_ADJACENCY_MIN_LENGTH_M = 0.3
_NOISY_ROOM_PATTERN = re.compile(r"BANO|ASEO")


@dataclass
class AcousticAdjacencyResult:
    room: Room  # el dormitorio afectado
    room_label: str
    noisy_label: str
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"{self.room_label} adyacente a {self.noisy_label} — verificar "
            "aislamiento acústico entre ambas estancias (CTE DB-HR: Rw ≥ 45 dB)"
        )


def evaluate_acoustic_adjacency(unit: Unit) -> List[AcousticAdjacencyResult]:
    """Para cada par (Dormitorio, Baño/Aseo) de la vivienda, comprueba que
    no compartan un tramo de muro (adyacencia real, > 0.3m) — el ruido de
    instalaciones y de impacto de baños/aseos no debería transmitirse
    directo a un dormitorio (CTE DB-HR). El Salón/cocina, al ser en España
    habitualmente un espacio abierto, queda deliberadamente fuera de esta
    regla: solo se evalúa Baño/Aseo.

    **Cambio de comportamiento aprobado**
    (`docs/prd/2026-08-11-adyacencia-acustica-tramo-enfrentado.md`, decisión
    A de E3.5). Antes medía si los polígonos se TOCAN (`_is_adjacent`), que
    en un DXF real casi nunca ocurre — cada recinto se dibuja en la cara
    interior de su propio muro, así que dos habitaciones que comparten
    tabique tienen un hueco entre polígonos, no un borde compartido. Medido
    sobre `ejemplo.dxf` (E3.5): 0 de 11 pares disparaban con el criterio
    antiguo; 9 de 11 disparan con éste. Ahora mide con
    `modelo.geometria.tramo_enfrentado_m`, que sí tolera ese hueco, sobre un
    `AlmacenGeometria` de usar y tirar. El umbral `_ADJACENCY_MIN_LENGTH_M`
    (0.3m) no cambia de valor; lo que cambia es la función que produce el
    número que compara. La distancia que tolera "seguir siendo el mismo
    muro" es `adyacencia.WALL_GAP_TOLERANCE_M` (0.5m) — se lee, no se
    copia."""
    dormitorios = [r for r in unit.rooms if r.label and _DORMITORIO_ANY_PATTERN.search(_normalize(r.label))]
    ruidosas = [r for r in unit.rooms if r.label and _NOISY_ROOM_PATTERN.search(_normalize(r.label))]

    almacen = AlmacenGeometria()
    results: List[AcousticAdjacencyResult] = []
    for dorm in dormitorios:
        for ruidosa in ruidosas:
            geom_dorm = almacen.insertar(dorm.polygon, HUELLA_2D, unidad="m")
            geom_ruidosa = almacen.insertar(ruidosa.polygon, HUELLA_2D, unidad="m")
            tramo = tramo_enfrentado_m(almacen, geom_dorm, geom_ruidosa, adyacencia.WALL_GAP_TOLERANCE_M)
            results.append(
                AcousticAdjacencyResult(
                    room=dorm,
                    room_label=dorm.label,
                    noisy_label=ruidosa.label,
                    passed=tramo <= _ADJACENCY_MIN_LENGTH_M,
                )
            )
    return results


_ACOUSTIC_EXPOSURE_COMPASSES_MEDIA = {"S", "E"}
_ACOUSTIC_EXPOSURE_COMPASSES_ALTA = {"N", "NE", "NO", "E", "S"}
_DORMITORIO_1_PATTERN = DORMITORIO_PATTERNS[0][1]


@dataclass
class AcousticExposureResult:
    room: Room
    room_label: str
    compass: str
    # True si `densidad_urbana` eleva este aviso a IMPORTANTE (entra en
    # `classify_problems`); False si se queda como aviso informativo (el
    # comportamiento original, densidad "media").
    importante: bool = False

    @property
    def message(self) -> str:
        return (
            f"{self.room_label}: fachada {self.compass} — verificar nivel de "
            "ruido exterior (DB-HR). Considerar doble acristalamiento."
        )


def evaluate_acoustic_exposure(
    unit: Unit,
    orientation_results: List[OrientationResult],
    densidad_urbana: str = "media",
) -> List[AcousticExposureResult]:
    """Si el Dormitorio 1 de la vivienda tiene su fachada orientada a una de
    las comprobadas, recomienda verificar el aislamiento acústico (CTE
    DB-HR). El conjunto de fachadas comprobadas y la severidad dependen de
    `densidad_urbana` (`cte_zonas.get_densidad_urbana`):
    - "alta" (grandes ciudades, tráfico urbano intenso): amplía a
      N/NE/NO/E/S y el aviso se marca `importante=True` (entra en
      `classify_problems` como IMPORTANTE).
    - "media" (comportamiento original, sin cambios): solo S/E — las de
      mayor exposición solar en España, pero también de mayor exposición a
      ruido de calle —, `importante=False` (aviso siempre informativo).
    - "baja" (núcleos pequeños, tráfico irrelevante): sin aviso.

    Reutiliza `orientation_results` (ya calculado por `evaluate_orientation`
    para toda la vivienda) en vez de recalcular la fachada del dormitorio."""
    if densidad_urbana == "baja":
        return []
    if densidad_urbana == "alta":
        compasses = _ACOUSTIC_EXPOSURE_COMPASSES_ALTA
        importante = True
    else:
        compasses = _ACOUSTIC_EXPOSURE_COMPASSES_MEDIA
        importante = False

    results: List[AcousticExposureResult] = []
    for o in orientation_results:
        if (
            o.room.label
            and _DORMITORIO_1_PATTERN.search(_normalize(o.room.label))
            and o.compass in compasses
        ):
            results.append(
                AcousticExposureResult(
                    room=o.room, room_label=o.room.label, compass=o.compass, importante=importante
                )
            )
    return results


_CONDENSATION_RISK_COMPASSES = {"N", "NO", "NE"}
_CONDENSATION_RISK_ZONAS = {"D", "E"}


@dataclass
class CondensacionesResult:
    room: Room
    room_label: str
    compass: str

    @property
    def message(self) -> str:
        return (
            f"{self.room_label}: fachada {self.compass} — riesgo de condensaciones "
            "por orientación norte en zona climática fría (CTE DB-HE)"
        )


def evaluate_condensaciones(
    unit: Unit, orientation_results: List[OrientationResult], zona_cte: str = DEFAULT_ZONA_CTE
) -> Optional[CondensacionesResult]:
    """Proxy simple de riesgo de condensaciones superficiales: en zonas
    climáticas frías (D/E), una fachada exterior orientada a norte,
    noroeste o noreste recibe poco sol directo y se enfría más — mayor
    riesgo de condensación si el aislamiento/barrera de vapor no está bien
    resuelto (CTE DB-HE). En zonas A/B/C (clima suave) el riesgo se
    considera bajo y no se avisa. Reutiliza `orientation_results` (ya
    calculado por `evaluate_orientation` con el `norte_grados` real del
    proyecto, igual que `evaluate_acoustic_exposure`) en vez de recalcular
    fachadas — así no hace falta pasar `norte_grados` aquí. Devuelve la
    primera habitación con fachada exterior a N/NO/NE que encuentre, o
    None si no hay riesgo (zona cálida) o ninguna habitación aplica."""
    if zona_cte not in _CONDENSATION_RISK_ZONAS:
        return None
    for o in orientation_results:
        if o.compass in _CONDENSATION_RISK_COMPASSES and _room_has_exterior_facade(o.room, unit.rooms):
            return CondensacionesResult(room=o.room, room_label=o.room_label, compass=o.compass)
    return None


# ---------------------------------------------------------------------------
# 17. Seguridad contra incendios: recorrido de evacuación
# ---------------------------------------------------------------------------

MAX_EVACUATION_DISTANCE_M = 25.0  # CTE DB-SI: uso residencial, sin rociadores

_EVACUATION_PATTERNS = [re.compile(r"SALON|COCINA")] + [pattern for _, pattern in DORMITORIO_PATTERNS]

# Piezas de circulación. Un plano puede llamar al mismo espacio "Pasillo",
# "Vestíbulo", "Distribuidor", "Recibidor" o "Hall" — depende del estudio, no
# del proyecto. Reconocer solo "Pasillo" convierte una convención de dibujo
# ajena en un incumplimiento; es exactamente el fallo que tenían R17 y R18c.
# Mismo vocabulario que `circulation._CIRCULATION_ROOM_PATTERN`.
_CIRCULACION_PATTERN = re.compile(r"PASILLO|VESTIBULO|DISTRIBUIDOR|RECIBIDOR|ANTESALA|HALL")


@dataclass
class EvacuationDistanceResult:
    """Recorrido interior medido hasta la pieza de circulación de la
    vivienda. `passed` se conserva por compatibilidad, pero desde el
    Bloque B (`docs/audits/DB-SI_REVIEW.md` §3.2, ficha C09) ya no
    alimenta ningún veredicto: ni `classify_problems`, ni el `score_pct`
    de la vivienda (`score_unit`), ni el resaltado de `plan_svg`. Motivo:
    los 25 m del CTE DB-SI se miden hasta la salida del EDIFICIO, no hasta
    la puerta de una vivienda -- comprobarlo de verdad exige geometría de
    zonas comunes que el modelo no tiene (ver docstring de
    `evaluate_evacuation_distance`)."""
    room: Room
    room_label: str
    distance_m: float
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"{self.room_label}: recorrido interior estimado "
            f"{self.distance_m:.1f}m -- métrica informativa de "
            f"circulación, no el recorrido normativo de evacuación "
            f"(que se mide hasta la salida de planta y no es evaluable "
            f"con el modelo actual)"
        )


def evaluate_evacuation_distance(unit: Unit) -> Tuple[List[EvacuationDistanceResult], Optional[str]]:
    """Recorrido de evacuación real de cada pieza habitable hasta la salida de
    la vivienda, andando por piezas contiguas (`analyzer/adyacencia.py`).

    Devuelve `(resultados, motivo_no_evaluable)`. Si el motivo no es None, la
    lista viene vacía y la regla NO se ha comprobado — no es que se cumpla.

    **Qué se cambió el 2026-08-05 y por qué.** Antes esto medía
    `unit_boundary.distance(room.polygon.centroid)`: la distancia del
    centroide de la pieza al punto MÁS CERCANO del contorno de su propia
    vivienda. Eso no es un recorrido, es aproximadamente medio ancho de la
    habitación. Medido sobre `ejemplo.dxf`: máximo 2,88 m contra un umbral de
    25 m, un margen de 22 m. La regla se presentaba como CRÍTICO citando el
    CTE DB-SI y era, en la práctica, un "cumple" constante — el peor modo de
    fallo posible en materia de incendios, porque no avisa de que no ha
    comprobado nada.

    Ahora se anda el grafo de piezas contiguas hasta la salida. La salida se
    toma como la pieza de circulación (pasillo, vestíbulo, distribuidor,
    recibidor), que es donde da la puerta de una vivienda. **Si no hay
    ninguna pieza de circulación no se puede saber por dónde se sale, y
    entonces la regla no es evaluable**: se dice, en vez de devolver un
    aprobado que nadie ha comprobado.

    **Límite que conviene tener presente al leer el resultado.** Los 25 m del
    DB-SI son la longitud del recorrido hasta la salida del EDIFICIO, no
    hasta la puerta de un piso. Medido dentro de una vivienda, el peor
    recorrido de `ejemplo.dxf` es de 10,7 m: el umbral no llega a apretar
    casi nunca a esta escala. Lo que aporta esta regla no es tanto el
    aprobado como la medida del recorrido y, sobre todo, decir cuándo no ha
    podido comprobarlo. Comprobar los 25 m de verdad exige la geometría de
    zonas comunes (portal y escalera), que el modelo no tiene."""
    if not unit.rooms:
        return [], None

    salida = next(
        (r for r in unit.rooms if r.label and _CIRCULACION_PATTERN.search(_normalize(r.label))),
        None,
    )
    if salida is None:
        return [], (
            f"Recorrido de evacuación en {unit.name}: no evaluable — la vivienda no tiene "
            "ninguna pieza de circulación (pasillo, vestíbulo, distribuidor o recibidor) "
            "desde la que situar la salida. El modelo no contiene puertas, así que no hay "
            "forma de saber por dónde se sale."
        )

    graph = adyacencia.construir_grafo(unit.rooms)
    results: List[EvacuationDistanceResult] = []
    for room in unit.rooms:
        if not room.label:
            continue
        normalized = _normalize(room.label)
        if not any(pattern.search(normalized) for pattern in _EVACUATION_PATTERNS):
            continue
        _camino, distance = adyacencia.weighted_shortest_path(graph, room, salida)
        if _camino is None:
            # Pieza incomunicada del resto: es un problema de geometría, no una
            # evacuación larga. No se inventa un número.
            continue
        results.append(
            EvacuationDistanceResult(
                room=room,
                room_label=room.label,
                distance_m=distance,
                passed=distance <= MAX_EVACUATION_DISTANCE_M,
            )
        )
    return results, None


# ---------------------------------------------------------------------------
# 18. Accesibilidad universal: espacio de giro y anchura mínima
# ---------------------------------------------------------------------------

MIN_BATHROOM_TURNING_SPACE_M = 1.50  # CTE DB-SUA: círculo de giro accesible (fallback si tipología no reconocida)


@dataclass
class BathroomTurningSpaceResult:
    room: Room
    room_label: str
    min_dimension_m: float
    min_required_m: float
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"{self.room_label}: dimensión mínima {self.min_dimension_m:.2f}m "
            f"insuficiente para espacio de giro de {self.min_required_m}m "
            "(CTE DB-SUA accesibilidad)"
        )


def evaluate_bathroom_turning_space(
    unit: Unit, tipologia: str = DEFAULT_TIPOLOGIA
) -> List[BathroomTurningSpaceResult]:
    """Comprueba que cada Baño de la vivienda tenga al menos una dimensión
    >= el mínimo de espacio de giro — proxy geométrico del círculo de giro
    que exige el CTE DB-SUA delante de los sanitarios, dependiente de la
    tipología (`UMBRALES_TIPOLOGIA["turning_space_min"]`). Distinta de
    `evaluate_bathroom_accessibility` (exige 1.2×1.8m en AL MENOS un baño
    de la vivienda, agregado): aquí se evalúa cada Baño individualmente."""
    min_required_m = _umbrales_tipologia(tipologia)["turning_space_min"]
    results: List[BathroomTurningSpaceResult] = []
    for room in unit.rooms:
        if not room.label or not _BANO_ROOM_PATTERN.search(_normalize(room.label)):
            continue
        _, short_side = _bounding_sides(room.polygon)
        if short_side <= 0:
            continue
        results.append(
            BathroomTurningSpaceResult(
                room=room,
                room_label=room.label,
                min_dimension_m=short_side,
                min_required_m=min_required_m,
                passed=short_side >= min_required_m,
            )
        )
    return results


MIN_HABITABLE_ROOM_WIDTH_M = 2.40

_MIN_ROOM_WIDTH_PATTERNS = [re.compile(r"SALON|COCINA")] + [pattern for _, pattern in DORMITORIO_PATTERNS]


@dataclass
class MinimumRoomWidthResult:
    room: Room
    room_label: str
    width_m: float
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"{self.room_label}: anchura mínima {self.width_m:.2f}m "
            f"insuficiente para uso habitable (mínimo {MIN_HABITABLE_ROOM_WIDTH_M}m)"
        )


def evaluate_minimum_room_width(unit: Unit) -> List[MinimumRoomWidthResult]:
    """Comprueba que cada Salón/cocina y Dormitorio de la vivienda tenga su
    lado corto >= `MIN_HABITABLE_ROOM_WIDTH_M` — proxy geométrico de
    accesibilidad universal (mobiliario básico + paso de silla de ruedas),
    complementario a la anchura mínima de vivienda de 3.0m que exige el
    CTE (no medible directamente sin datos reales de pasillos/puertas)."""
    results: List[MinimumRoomWidthResult] = []
    for room in unit.rooms:
        if not room.label:
            continue
        normalized = _normalize(room.label)
        if not any(pattern.search(normalized) for pattern in _MIN_ROOM_WIDTH_PATTERNS):
            continue
        _, short_side = _bounding_sides(room.polygon)
        if short_side <= 0:
            continue
        results.append(
            MinimumRoomWidthResult(
                room=room,
                room_label=room.label,
                width_m=short_side,
                passed=short_side >= MIN_HABITABLE_ROOM_WIDTH_M,
            )
        )
    return results


MIN_ITINERARIO_ACCESIBLE_M = 1.20  # CTE DB-SUA-2: itinerario accesible


@dataclass
class ItinerarioAccesibleResult:
    unit_name: str

    @property
    def message(self) -> str:
        return (
            f"Vivienda: sin itinerario accesible — ningún Pasillo alcanza "
            f"{MIN_ITINERARIO_ACCESIBLE_M}m de anchura libre (CTE DB-SUA-2)"
        )


def evaluate_itinerario_accesible(
    unit: Unit, tipologia: str
) -> Tuple[Optional[ItinerarioAccesibleResult], Optional[str]]:
    """Solo aplica a plurifamiliar (itinerario accesible es exigencia de
    zonas comunes/vivienda accesible en edificios plurifamiliares; DB-SUA
    no lo exige igual en unifamiliar/rehabilitación). Comprueba que al menos
    una pieza de circulación de la vivienda tenga lado corto >=
    `MIN_ITINERARIO_ACCESIBLE_M`.

    Devuelve `(resultado, motivo_no_evaluable)`. Con resultado a None y
    motivo a None, la vivienda cumple; con motivo informado, no se ha podido
    comprobar.

    **Qué se cambió el 2026-08-05 y por qué.** Antes esto buscaba
    literalmente la palabra "PASILLO" y, si no encontraba ninguna pieza así
    etiquetada, devolvía INCUMPLIMIENTO. En `ejemplo.dxf` no hay una sola
    pieza etiquetada "Pasillo" —el vocabulario del plano son ocho etiquetas y
    esa no está—, así que la regla fallaba en las 6 viviendas de 6: seis
    incidencias IMPORTANTE, el 16% del total del proyecto, **ninguna
    correspondiente a un defecto real**. Se estaba convirtiendo la convención
    de rotulación de un estudio ajeno en un incumplimiento de accesibilidad.

    Dos cambios: se reconoce el vocabulario habitual de circulación
    (`_CIRCULACION_PATTERN`, compartido con R17 y con `circulation.py`), y la
    ausencia total de piezas de circulación pasa a ser **no evaluable** en vez
    de incumplimiento. Una vivienda de planta abierta sin distribuidor no
    incumple nada: sencillamente no hay pasillo que medir, y no se puede
    afirmar que su itinerario sea accesible ni que no lo sea sin las puertas,
    que el modelo no tiene."""
    if tipologia != "plurifamiliar":
        return None, None

    circulaciones = [
        r for r in unit.rooms if r.label and _CIRCULACION_PATTERN.search(_normalize(r.label))
    ]
    if not circulaciones:
        return None, (
            f"Itinerario accesible en {unit.name}: no evaluable — la vivienda no tiene ninguna "
            "pieza de circulación que medir (planta abierta, o el plano no rotula el "
            f"distribuidor). El mínimo aplicable sería {MIN_ITINERARIO_ACCESIBLE_M}m de anchura "
            "libre."
        )

    for room in circulaciones:
        _, short_side = _bounding_sides(room.polygon)
        if short_side >= MIN_ITINERARIO_ACCESIBLE_M:
            return None, None
    return ItinerarioAccesibleResult(unit_name=unit.name), None


# ---------------------------------------------------------------------------
# 19. Superficie de huecos de iluminación natural (regla legal 1/8)
# ---------------------------------------------------------------------------
# Distinta de `evaluate_natural_lighting` (Bloque 15, `NaturalLightFactorResult`):
# esa es una estimación técnica de "factor de luz natural" con un umbral
# heurístico bajo (1.5%); esta es la regla legal explícita y más exigente que
# citan CTE DB-HS3 y los decretos autonómicos de habitabilidad: la superficie
# de huecos de iluminación de cada pieza habitable debe ser, como mínimo,
# 1/8 de su superficie útil. Reutiliza `_superficie_hueco_estimada_m2` —la
# misma estimación que el Bloque 15— porque el modelo no tiene datos reales
# de carpintería: las dos reglas comparten proxy y difieren solo en el umbral.

MIN_WINDOW_TO_FLOOR_RATIO = 1 / 8  # CTE DB-HS3 y decretos autonómicos de habitabilidad

_WINDOW_OPENING_PATTERNS = [re.compile(r"SALON|COCINA")] + [pattern for _, pattern in DORMITORIO_PATTERNS]


@dataclass
class WindowOpeningRatioResult:
    room: Room
    room_label: str
    window_area_m2: float
    ratio: float
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"{self.room_label}: hueco de iluminación estimado {self.ratio * 100:.1f}% "
            f"de la superficie útil — no alcanza el mínimo legal de 1/8 "
            f"({MIN_WINDOW_TO_FLOOR_RATIO * 100:.1f}%, CTE DB-HS3)"
        )


def evaluate_window_opening_ratio(unit: Unit) -> List[WindowOpeningRatioResult]:
    """Comprueba, para cada Salón/cocina y Dormitorio 1/2/3 de `unit` con
    fachada exterior, que la superficie de hueco estimada
    (`_superficie_hueco_estimada_m2`, misma estimación que
    `evaluate_natural_lighting`) alcance al menos 1/8 de la superficie de la
    pieza — una comparación entre dos superficies. Las habitaciones sin
    fachada exterior ya las penaliza `evaluate_natural_light`; no se duplica
    aquí."""
    results: List[WindowOpeningRatioResult] = []
    for room in unit.rooms:
        if not room.label:
            continue
        normalized = _normalize(room.label)
        if not any(pattern.search(normalized) for pattern in _WINDOW_OPENING_PATTERNS):
            continue
        if not _room_has_exterior_facade(room, unit.rooms):
            continue

        long_side, _short_side = _bounding_sides(room.polygon)
        if long_side <= 0 or room.area_m2 <= 0:
            continue

        window_area_m2 = _superficie_hueco_estimada_m2(long_side)
        ratio = window_area_m2 / room.area_m2
        results.append(
            WindowOpeningRatioResult(
                room=room,
                room_label=room.label,
                window_area_m2=window_area_m2,
                ratio=ratio,
                passed=ratio >= MIN_WINDOW_TO_FLOOR_RATIO,
            )
        )
    return results


# ---------------------------------------------------------------------------
# 20. Superficie mínima de dormitorios según ocupación (individual/doble)
# ---------------------------------------------------------------------------
# Distinta de la regla básica de `RULES` (que fija el mínimo por posición en
# la jerarquía: Dormitorio 1 >10m², 2 >8m², 3 >6m²): esta regla aplica el
# criterio legal de habitabilidad por USO previsto de la pieza (individual
# vs. doble), independientemente de qué número de dormitorio sea. No es un
# código del CTE (los DB no fijan superficies mínimas por pieza) sino de
# LOE/decretos autonómicos de habitabilidad. El modelo no tiene un dato
# explícito de ocupación prevista salvo que la etiqueta del plano lo indique
# ("Dormitorio Doble"...); si no lo indica, se asume individual (el criterio
# más permisivo) — limitación documentada, igual que el resto de proxies del
# módulo.

BEDROOM_MIN_AREA_INDIVIDUAL_M2 = 6.0
BEDROOM_MIN_AREA_DOUBLE_M2 = 10.0

_BEDROOM_DOUBLE_PATTERN = re.compile(r"DOBLE")


@dataclass
class BedroomMinimumAreaResult:
    room: Room
    room_label: str
    area_m2: float
    ocupacion: str  # "individual" | "doble"
    min_area_m2: float
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"{self.room_label}: {self.area_m2:.2f} m² por debajo del mínimo "
            f"legal de {self.min_area_m2:.0f} m² para dormitorio {self.ocupacion}"
        )


def evaluate_bedroom_minimum_area(unit: Unit) -> List[BedroomMinimumAreaResult]:
    """Comprueba la superficie mínima legal de cada Dormitorio de `unit`
    según su ocupación prevista: 6m² individual (por defecto), 10m² doble
    (si la etiqueta contiene "Doble")."""
    results: List[BedroomMinimumAreaResult] = []
    for room in unit.rooms:
        if not room.label:
            continue
        normalized = _normalize(room.label)
        if not _DORMITORIO_ANY_PATTERN.search(normalized):
            continue

        if _BEDROOM_DOUBLE_PATTERN.search(normalized):
            ocupacion, min_area = "doble", BEDROOM_MIN_AREA_DOUBLE_M2
        else:
            ocupacion, min_area = "individual", BEDROOM_MIN_AREA_INDIVIDUAL_M2

        results.append(
            BedroomMinimumAreaResult(
                room=room,
                room_label=room.label,
                area_m2=room.area_m2,
                ocupacion=ocupacion,
                min_area_m2=min_area,
                passed=room.area_m2 >= min_area,
            )
        )
    return results


# ---------------------------------------------------------------------------
# 21. Baño adaptado: superficie y espacio de giro (CTE DB-SUA)
# ---------------------------------------------------------------------------
# Complementa a `evaluate_bathroom_accessibility` (Bloque 8, exige un
# rectángulo mínimo de 1.2×1.8m en al menos un Baño) con el criterio de
# superficie útil total que exigen las guías técnicas de accesibilidad para
# un baño adaptado: >=3.60m² de superficie, con un espacio libre de giro de
# diámetro 1.50m (reutiliza `MIN_BATHROOM_TURNING_SPACE_M`, ya definida en
# el Bloque 18, como proxy del diámetro de giro: la dimensión menor del baño
# debe alcanzarlo).

ACCESSIBLE_BATHROOM_MIN_AREA_M2 = 3.60


@dataclass
class AccessibleBathroomAreaResult:
    unit_name: str
    best_area_m2: float
    has_accessible_bathroom: bool

    @property
    def passed(self) -> bool:
        return self.has_accessible_bathroom

    @property
    def message(self) -> str:
        return (
            "Baño: ningún baño alcanza los "
            f"{ACCESSIBLE_BATHROOM_MIN_AREA_M2}m² de superficie con espacio de giro "
            f"de ⌀{MIN_BATHROOM_TURNING_SPACE_M}m que exige un baño adaptado (CTE DB-SUA)"
        )


def evaluate_accessible_bathroom_area(unit: Unit) -> Optional[AccessibleBathroomAreaResult]:
    """Comprueba que al menos un Baño de la vivienda cumpla, a la vez,
    superficie >= `ACCESSIBLE_BATHROOM_MIN_AREA_M2` y espacio de giro
    (dimensión menor) >= `MIN_BATHROOM_TURNING_SPACE_M`. Si la vivienda no
    tiene ningún Baño, no se evalúa (esa carencia la cubre
    `evaluate_bathroom_ratio`)."""
    banos = [r for r in unit.rooms if r.label and _BANO_ROOM_PATTERN.search(_normalize(r.label))]
    if not banos:
        return None

    def _is_accessible(room: Room) -> bool:
        _, short_side = _bounding_sides(room.polygon)
        return room.area_m2 >= ACCESSIBLE_BATHROOM_MIN_AREA_M2 and short_side >= MIN_BATHROOM_TURNING_SPACE_M

    best_area = max((r.area_m2 for r in banos), default=0.0)
    return AccessibleBathroomAreaResult(
        unit_name=unit.name,
        best_area_m2=best_area,
        has_accessible_bathroom=any(_is_accessible(r) for r in banos),
    )


# ---------------------------------------------------------------------------
# Puntuación por vivienda
# ---------------------------------------------------------------------------

SCORE_GREEN_THRESHOLD = 85.0
SCORE_YELLOW_THRESHOLD = 70.0


def score_rating(score_pct: float) -> str:
    if score_pct >= SCORE_GREEN_THRESHOLD:
        return "verde"
    if score_pct >= SCORE_YELLOW_THRESHOLD:
        return "amarillo"
    return "rojo"


def rating_con_severidad(score_pct: float, n_criticos: int) -> str:
    """Valoración de color teniendo en cuenta la gravedad, no solo el
    porcentaje. **Un solo incumplimiento CRÍTICO veta el verde y el
    amarillo.**

    El problema que esto corrige: `score_pct` es el porcentaje de
    comprobaciones superadas, así que 2 fallos entre 45 dan 95,6 y el color
    sale verde — aunque los dos fallos sean críticos. En `ejemplo.dxf`, VT1/3
    se presentaba como **"Cumplimiento correcto", 92, junto a 2 críticos de
    accesibilidad**. Ningún arquitecto que firme un proyecto acepta que esas
    dos cosas convivan en la misma pantalla, y con razón: un crítico es, por
    definición, algo que puede bloquear el visado. Promediarlo con cuarenta
    aciertos no lo hace menos bloqueante.

    Se mantiene `score_rating` sin tocar para el código que solo dispone del
    número (informe CLI, `scoring.py`), pero cualquier presentación que tenga
    a mano las incidencias debe usar esta función.

    Deliberadamente NO se toca `score_pct`: el número sigue midiendo lo que
    medía, para no alterar el histórico de proyectos ya guardados. Lo que
    cambia es el veredicto que lo acompaña. Unificar los dos sistemas de
    puntuación que conviven hoy sigue siendo una decisión pendiente — está
    documentada en `docs/design/2026-08-02-dos-sistemas-de-puntuacion.md` y
    cambia los números de todos los proyectos guardados, así que no se hace
    de paso en una corrección de coherencia."""
    if n_criticos > 0:
        return "rojo"
    return score_rating(score_pct)


# ---------------------------------------------------------------------------
# Bloque 12: clasificación de problemas por gravedad
# ---------------------------------------------------------------------------
# Convierte los resultados "NO superados" de toda la aplicación (por
# vivienda/habitación, vía AdvancedAnalysis, + por edificio, vía los 5
# parámetros opcionales que no viven en AdvancedAnalysis porque dependen de
# datos de solar/normativa que evaluate_advanced_for_units nunca recibe) en
# una lista plana de IssueReport con severidad, código normativo, impacto y
# solución — pensada para que un frontend (o un informe PDF) pueda
# priorizar sin tener que interpretar el texto de cada .message.


@dataclass
class IssueReport:
    severity: str  # "CRITICO" | "IMPORTANTE" | "RECOMENDACION"
    bloque: int  # 1-11 (bloque numerado de este módulo); 0 = integridad del
    # dato, no una regla de proyecto; 12 = sintetizado por `chain_effects.py`
    codigo: str  # código normativo, p. ej. "CTE-DB-SI-3"
    titulo: str  # frase corta
    descripcion: str  # qué falla con valores reales (el .message del resultado)
    impacto: str  # consecuencia si no se corrige
    solucion: str  # acción concreta
    room_label: str  # habitación/vivienda afectada, "" si es de edificio
    unit_name: str = ""  # nombre exacto de la vivienda (== v.nombre en el JSON), "" si es de edificio
    # Cuántos puntos subiría `scoring.ScoringBreakdown.puntuacion_total` si
    # se corrigiera ESTE issue en concreto (el resto igual) — lo rellena
    # `scoring.compute_puntos_ganados` sobre la lista de `classify_problems`,
    # no este módulo; queda en 0.0 por defecto para instancias de `IssueReport`
    # que nunca pasan por ahí (p. ej. los `problema_origen` sintéticos de
    # `chain_effects.py`, que tienen su propio `impacto_coste_estimado`).
    puntos_ganados: float = 0.0


def _issue_room_label(result) -> str:
    """`room_label` del resultado si lo tiene; si no, `unit_name`
    (resultados a nivel de vivienda); si no, "" (resultados a nivel de
    edificio, sin habitación ni vivienda asociada)."""
    return getattr(result, "room_label", None) or getattr(result, "unit_name", None) or ""


def classify_problems(
    analysis: AdvancedAnalysis,
    solar_occupation: Optional[SolarOccupationResult] = None,
    buildability: Optional[BuildabilityResult] = None,
    max_floors: Optional[MaxFloorsResult] = None,
    compactness: Optional[BuildingCompactnessResult] = None,
    building_orientation: Optional[BuildingOrientationResult] = None,
    retranqueos: Optional[RetranqueosResult] = None,
    ceiling_height: Optional[CeilingHeightResult] = None,
    fire_compartmentation: Optional[List[FireCompartmentationResult]] = None,
    tipologia: str = DEFAULT_TIPOLOGIA,
    zona_cte: str = DEFAULT_ZONA_CTE,
) -> List[IssueReport]:
    """Clasifica en CRITICO (incumple CTE/normativa urbanística obligatoria),
    IMPORTANTE (habitabilidad y bienestar) o RECOMENDACION (eficiencia y
    confort, no obligatorio) cada resultado "NO superado" de `analysis` y de
    los 5 resultados de edificio pasados aparte. Quedan fuera a propósito
    `OrientationResult`/`SolarHoursResult` (sin `passed`, se consumen en el
    frontend como datos de orientación/soleamiento, no como problemas).
    `AcousticExposureResult` solo entra como IMPORTANTE cuando
    `importante=True` (densidad urbana "alta" — ver
    `evaluate_acoustic_exposure`); en densidad "media" (por defecto) sigue
    siendo un aviso siempre informativo, sin condición de fallo, que no pasa
    por aquí. `tipologia` baja `BathroomAccessibilityResult` de CRITICO a
    IMPORTANTE en unifamiliar/rehabilitación (obra existente/vivienda
    unipersonal: menos determinante que en plurifamiliar).

    Itera `analysis.unit_scores` (no las listas planas de `analysis.*`) para
    poder anotar en cada `IssueReport.unit_name` de qué vivienda viene —
    `UnitScore` ya trae todos los resultados de una vivienda agrupados
    (`us.natural_light_results`, `us.proportion_results`...), así que no
    hace falta recalcular nada, solo leer de ahí en vez de las listas ya
    aplanadas de `analysis`. Los 7 resultados de edificio (los 5 originales
    más `ceiling_height` y `fire_compartmentation`) quedan con `unit_name=""`
    salvo `fire_compartmentation`, cuyo `unit_name` combina las dos
    viviendas afectadas (no pertenece a ninguna por separado)."""
    bathroom_accessibility_severity = (
        "IMPORTANTE" if tipologia in ("unifamiliar", "rehabilitacion") else "CRITICO"
    )

    def _issue(
        result, severity: str, bloque: int, codigo: str, titulo: str, impacto: str, solucion: str, unit_name: str = ""
    ) -> IssueReport:
        return IssueReport(
            severity=severity,
            bloque=bloque,
            codigo=codigo,
            titulo=titulo,
            descripcion=result.message,
            impacto=impacto,
            solucion=solucion,
            room_label=_issue_room_label(result),
            unit_name=unit_name,
        )

    issues: List[IssueReport] = []

    for us in analysis.unit_scores:
        unit_name = us.unit.name

        # ---- CRITICO (por vivienda) --------------------------------------
        r = us.unit_minimum_area_result
        if r is not None and not r.passed:
            issues.append(_issue(
                r, "CRITICO", 2, "CTE-DB-HE", "Superficie útil de vivienda insuficiente",
                "Riesgo de no obtener cédula de habitabilidad o licencia de primera ocupación.",
                "Redistribuir o ampliar la vivienda hasta superar el mínimo legal de superficie útil.",
                unit_name,
            ))
        # Accesibilidad de baño: UNA incidencia por vivienda, no tres.
        #
        # Hasta 2026-08-05 había tres reglas sobre el mismo objeto físico, y
        # las tres emitían CRÍTICO por separado: el Bloque 8 (rectángulo
        # 1.2×1.8m en al menos un baño), el Bloque 18a (lado corto >= 1.50m,
        # y además por CADA baño) y el Bloque 21 (>= 3.60m² con giro de
        # 1.50m en al menos un baño). En VT1/3 de `ejemplo.dxf` salían dos
        # CRÍTICOS sobre el mismo baño, y `scoring.compute_puntos_ganados`
        # prometía +2.3 puntos por arreglar cada uno: el mismo defecto
        # penalizado dos veces y la misma recompensa ofrecida dos veces.
        #
        # Las tres siguen midiéndose (cada una aporta un criterio distinto y
        # todas entran en `checks`); lo que cambia es que se presentan
        # juntas, con los criterios que han fallado enumerados en la
        # descripción. Un baño no accesible es un problema, no tres.
        fallos_bano = []
        if us.bathroom_accessibility_result is not None and not us.bathroom_accessibility_result.passed:
            fallos_bano.append(
                f"no hay ningún baño con un rectángulo libre de "
                f"{ACCESSIBLE_BATHROOM_MIN_SHORT_M}×{ACCESSIBLE_BATHROOM_MIN_LONG_M}m"
            )
        if us.accessible_bathroom_area_result is not None and not us.accessible_bathroom_area_result.passed:
            fallos_bano.append(
                f"ninguno alcanza {ACCESSIBLE_BATHROOM_MIN_AREA_M2}m² de superficie con giro de "
                f"⌀{MIN_BATHROOM_TURNING_SPACE_M}m"
            )
        estrechos = [r for r in us.bathroom_turning_space_results if not r.passed]
        if estrechos:
            fallos_bano.append(
                "%s por debajo de %.2fm en su dimensión menor"
                % (", ".join(r.room_label for r in estrechos), estrechos[0].min_required_m)
            )
        if fallos_bano:
            referencia = (
                us.accessible_bathroom_area_result
                or us.bathroom_accessibility_result
                or estrechos[0]
            )
            issues.append(IssueReport(
                severity=bathroom_accessibility_severity,
                bloque=11,
                codigo="CTE-DB-SUA-1",
                titulo="Ningún baño de la vivienda es accesible",
                descripcion="Baño: " + "; ".join(fallos_bano) + ".",
                impacto=(
                    "Incumple la accesibilidad universal exigida por normativa; puede bloquear el "
                    "visado y obligar a reforma posterior."
                ),
                solucion=(
                    f"Redimensionar un baño de la vivienda hasta alcanzar a la vez "
                    f"{ACCESSIBLE_BATHROOM_MIN_AREA_M2}m² de superficie y un espacio libre de giro "
                    f"de ⌀{MIN_BATHROOM_TURNING_SPACE_M}m."
                ),
                room_label=_issue_room_label(referencia),
                unit_name=unit_name,
            ))
        for r in us.bedroom_minimum_area_results:
            if not r.passed:
                issues.append(_issue(
                    r, "CRITICO", 2, "HABITABILIDAD-SUP", "Dormitorio por debajo de la superficie mínima legal",
                    "Riesgo de no obtener cédula de habitabilidad o licencia de primera ocupación.",
                    "Ampliar el dormitorio hasta el mínimo legal según su ocupación prevista "
                    f"({BEDROOM_MIN_AREA_INDIVIDUAL_M2:.0f}m² individual, {BEDROOM_MIN_AREA_DOUBLE_M2:.0f}m² doble).",
                    unit_name,
                ))
        for r in us.corridor_width_results:
            if not r.passed:
                issues.append(_issue(
                    r, "CRITICO", 2, "CTE-DB-SUA-1", "Pasillo por debajo del ancho mínimo de paso",
                    "Dificulta el paso de personas y mobiliario; incumple el ancho mínimo de evacuación interior.",
                    "Ampliar el pasillo hasta al menos 0.9m de anchura libre.",
                    unit_name,
                ))
        # `evacuation_distance_results` (Bloque 17) NO genera incidencia aquí
        # desde el Bloque B (DB-SI_REVIEW.md §3.2, ficha C09): mide el
        # recorrido interior de la vivienda, no el recorrido normativo del
        # CTE (que llega hasta la salida de EDIFICIO). Presentarlo como
        # CRITICO con cita CTE-DB-SI-3 era un veredicto que el dato no
        # sostiene. El valor sigue calculado y disponible en
        # `us.evacuation_distance_results` como métrica informativa.
        # El espacio de giro por baño (Bloque 18a) ya se ha contado arriba,
        # dentro de la incidencia única de accesibilidad de baño.

        # ---- IMPORTANTE (por vivienda) ------------------------------------
        condensaciones = evaluate_condensaciones(us.unit, us.orientation_results, zona_cte)
        if condensaciones is not None:
            issues.append(_issue(
                condensaciones, "IMPORTANTE", 7, "CTE-DB-HE-COND", "Riesgo de condensaciones en fachada norte",
                "Las superficies frías en fachada norte, en climas fríos, son más propensas a "
                "condensación superficial si el aislamiento es insuficiente — puede derivar en "
                "humedades y moho.",
                f"Verificar aislamiento y barrera de vapor en fachadas norte — especialmente "
                f"crítico en zona CTE {zona_cte}.",
                unit_name,
            ))
        itinerario = us.itinerario_accesible_result
        if itinerario is not None:
            issues.append(_issue(
                itinerario, "IMPORTANTE", 11, "CTE-DB-SUA-2-ITIN", "Sin itinerario accesible ≥1.20m",
                "Dificulta el desplazamiento de una silla de ruedas entre zonas de la vivienda; "
                "incumple el itinerario accesible exigido en edificios plurifamiliares.",
                "Ampliar al menos un pasillo a ≥1.20m para garantizar itinerario accesible entre "
                "zonas de la vivienda.",
                unit_name,
            ))
        for r in us.natural_light_results:
            if not r.passed:
                issues.append(_issue(
                    r, "IMPORTANTE", 1, "CTE-DB-HS", "Habitación sin ventilación/iluminación natural",
                    "La estancia no da a fachada exterior; puede generar humedades y no cumple ventilación mínima habitable.",
                    "Reubicar la habitación junto a una fachada exterior o redistribuir la vivienda para darle hueco al exterior.",
                    unit_name,
                ))
        for r in us.proportion_results:
            if not r.passed:
                issues.append(_issue(
                    r, "IMPORTANTE", 1, "HABITABILIDAD", "Habitación con proporción 'tubo'",
                    "Dificulta amueblar la estancia con criterios funcionales; reduce el confort de uso.",
                    "Ajustar la geometría de la habitación para acercar la proporción largo/corto a 1:2.5 o menos.",
                    unit_name,
                ))
        for r in us.hierarchy_results:
            if not r.passed:
                issues.append(_issue(
                    r, "IMPORTANTE", 1, "HABITABILIDAD", "Jerarquía de dormitorios incorrecta",
                    "Un dormitorio secundario es igual o mayor que uno de rango superior, lo que confunde el uso previsto de cada pieza.",
                    "Redimensionar los dormitorios para que Dormitorio 1 > Dormitorio 2 > Dormitorio 3.",
                    unit_name,
                ))
        for r in us.room_depth_results:
            if not r.passed:
                issues.append(_issue(
                    r, "IMPORTANTE", 7, "CTE-DB-HS", "Profundidad de habitación excesiva desde fachada",
                    "La luz natural no alcanza el fondo de la estancia; puede requerir iluminación artificial permanente.",
                    "Reducir la profundidad de la habitación o añadir una segunda fachada/patio que aporte luz.",
                    unit_name,
                ))
        # "Factor de luz natural insuficiente" retirado el 2026-08-05: medía lo
        # mismo que "Superficie de huecos (regla 1/8)" con un umbral que no
        # podía fallar nunca. `natural_light_factor_results` llega siempre
        # vacía; el bucle se elimina en vez de dejarlo iterando en el vacío.
        for r in us.window_opening_results:
            if not r.passed:
                issues.append(_issue(
                    r, "IMPORTANTE", 7, "CTE-DB-HS3", "Superficie de huecos de iluminación insuficiente (regla 1/8)",
                    "Incumple el mínimo legal de iluminación natural directa de la pieza; puede impedir "
                    "obtener cédula de habitabilidad.",
                    "Ampliar el hueco de ventana en fachada hasta alcanzar 1/8 de la superficie útil de "
                    "la pieza, o reducir la superficie de la habitación.",
                    unit_name,
                ))
        r = us.cross_ventilation_result
        if r is not None and not r.passed:
            issues.append(_issue(
                r, "IMPORTANTE", 5, "CTE-DB-HS3", "Vivienda sin ventilación cruzada",
                "Sin fachadas opuestas o perpendiculares, la renovación de aire depende solo de ventilación forzada; peor calidad del aire interior.",
                "Reorganizar las habitaciones habitables para que al menos dos den a fachadas opuestas o perpendiculares.",
                unit_name,
            ))
        for r in us.acoustic_adjacency_results:
            if not r.passed:
                issues.append(_issue(
                    r, "IMPORTANTE", 8, "CTE-DB-HR", "Dormitorio adyacente a zona húmeda sin aislamiento verificado",
                    "Riesgo de transmisión de ruido de instalaciones y de impacto al dormitorio si no se refuerza el aislamiento.",
                    "Verificar/reforzar el aislamiento acústico del tabique compartido hasta Rw ≥ 45 dB, o separar ambas estancias con un elemento intermedio.",
                    unit_name,
                ))
        for r in us.acoustic_exposure_results:
            if r.importante:
                issues.append(_issue(
                    r, "IMPORTANTE", 8, "CTE-DB-HR", "Fachada expuesta a ruido urbano intenso",
                    "En ciudades de alta densidad, la fachada del Dormitorio 1 da a una orientación con "
                    "tráfico urbano intenso; riesgo de incumplir los niveles de aislamiento acústico exigidos.",
                    "Verificar el aislamiento acústico a ruido aéreo exterior (DB-HR) y valorar doble "
                    "acristalamiento o carpintería de mayor prestación acústica.",
                    unit_name,
                ))
        for r in us.minimum_room_width_results:
            if not r.passed:
                issues.append(_issue(
                    r, "IMPORTANTE", 11, "CTE-DB-SUA", "Anchura de habitación insuficiente para accesibilidad",
                    "Dificulta el paso y maniobra de una silla de ruedas y limita la disposición de mobiliario básico.",
                    "Ampliar el lado corto de la habitación hasta al menos 2.40m.",
                    unit_name,
                ))
        r = us.bathroom_ratio_result
        if r is not None and not r.passed:
            issues.append(_issue(
                r, "IMPORTANTE", 2, "CTE-DB-HS", "Ratio de baños insuficiente para el número de dormitorios",
                "Reduce la habitabilidad y el confort de uso diario de la vivienda.",
                "Añadir el baño o aseo que falte según el número de dormitorios de la vivienda.",
                unit_name,
            ))
        for r in us.entry_distance_results:
            if not r.passed:
                issues.append(_issue(
                    r, "IMPORTANTE", 5, "EFICIENCIA", "Acceso largo desde la entrada al dormitorio",
                    "Recorrido interior poco eficiente; puede indicar una distribución subóptima de la vivienda.",
                    "Acercar el dormitorio a la zona de circulación o replantear el recorrido de acceso.",
                    unit_name,
                ))

        # ---- RECOMENDACION (por vivienda) ---------------------------------
        r = us.spatial_hierarchy_result
        if r is not None and not r.passed:
            issues.append(_issue(
                r, "RECOMENDACION", 5, "EFICIENCIA", "El salón no es la pieza principal de la vivienda",
                "El salón/cocina debería ser el espacio de mayor superficie; si no lo es, la jerarquía funcional de la vivienda es confusa.",
                "Redimensionar el salón/cocina o el Dormitorio 1 para que el salón sea la estancia de mayor tamaño.",
                unit_name,
            ))
        r = us.circulation_efficiency_result
        if r is not None and not r.passed:
            issues.append(_issue(
                r, "RECOMENDACION", 5, "EFICIENCIA", "El pasillo ocupa demasiada superficie útil",
                "Superficie de circulación por encima de lo recomendable; reduce la superficie útil aprovechable de la vivienda.",
                "Reducir la longitud o el área del pasillo, o replantear la distribución para minimizar la circulación.",
                unit_name,
            ))
        r = us.efficiency_result
        if r is not None and not r.passed:
            issues.append(_issue(
                r, "RECOMENDACION", 5, "EFICIENCIA", "Ratio de superficie útil/total por debajo del recomendado",
                "Una parte significativa de la vivienda son terrazas/tendederos en vez de superficie útil habitable, reduciendo el aprovechamiento comercial.",
                "Reducir la superficie de terrazas/tendederos o aumentar la superficie útil interior de la vivienda.",
                unit_name,
            ))

    # ---- CRITICO / RECOMENDACION de edificio (unit_name="") ----------------
    if solar_occupation is not None and not solar_occupation.passed:
        issues.append(_issue(
            solar_occupation, "CRITICO", 6, "URBANISMO-OC", "Ocupación del solar por encima del máximo",
            "El proyecto no cumple el planeamiento urbanístico vigente; la licencia de obras será denegada tal como está.",
            "Reducir la huella en planta baja o redistribuir superficie en más plantas para bajar el % de ocupación.",
        ))
    if buildability is not None and not buildability.passed:
        issues.append(_issue(
            buildability, "CRITICO", 6, "URBANISMO-ED", "Edificabilidad por encima del máximo permitido",
            "Supera el aprovechamiento urbanístico máximo del solar; la licencia de obras será denegada tal como está.",
            "Reducir la superficie total construida o el número de plantas hasta cumplir el ratio m²techo/m²suelo permitido.",
        ))
    if max_floors is not None and not max_floors.passed:
        issues.append(_issue(
            max_floors, "CRITICO", 6, "URBANISMO-AL", "Número de plantas por encima del máximo permitido",
            "Incumple la altura máxima reguladora del planeamiento; la licencia de obras será denegada tal como está.",
            "Reducir el número de plantas del edificio hasta el máximo permitido por la normativa municipal.",
        ))
    if retranqueos is not None:
        issues.append(_issue(
            retranqueos, retranqueos.severity, 6, "URBANISMO-RETR", "Retranqueos insuficientes (estimación)",
            "La huella edificable con los retranqueos indicados es nula, negativa o deja un margen "
            "ínfimo — proxy simplificado, sin geometría real de linderos.",
            "Aumentar las dimensiones del solar, reducir los retranqueos exigidos o replantear la "
            "huella del edificio.",
        ))
    if compactness is not None and not compactness.passed:
        issues.append(_issue(
            compactness, "RECOMENDACION", 10, "EFICIENCIA-ENE", "Edificio poco compacto",
            "Mayor superficie de envolvente por m³ habitado; mayor pérdida de calor en invierno y mayor demanda energética.",
            "Simplificar la geometría del edificio (menos entrantes/salientes) para reducir la superficie de fachada por m³ construido.",
        ))
    if building_orientation is not None and not building_orientation.passed:
        issues.append(_issue(
            building_orientation, "RECOMENDACION", 10, "EFICIENCIA-ENE", "Poca superficie habitable orientada a sur",
            "Menor aprovechamiento solar pasivo; mayor demanda de calefacción en invierno.",
            "Reorientar el edificio o redistribuir las estancias habitables hacia fachadas sur, sureste o suroeste.",
        ))
    if ceiling_height is not None and not ceiling_height.passed:
        issues.append(_issue(
            ceiling_height, "CRITICO", 2, "CTE-DB-SUA-1", "Altura libre por debajo del mínimo en zonas habitables",
            "Incumple la altura libre mínima exigida por el CTE; puede impedir la licencia de obras o "
            "la cédula de habitabilidad.",
            f"Aumentar la altura libre del edificio hasta al menos {MIN_CEILING_HEIGHT_M}m en zonas habitables.",
        ))
    for r in fire_compartmentation or []:
        # Bloque B (DB-SI_REVIEW.md §3.2, ficha C01): este check compara
        # huellas de vivienda, no comprueba nada de lo que exige DB-SI 1 §1
        # (ni los 2.500 m², ni el EI 60 -- eso lo publica `sectorizacion.py`,
        # CAP-4). Es integridad geométrica del dibujo, igual que
        # `room_overlap` (mismo código no-CTE, distinto sufijo para no
        # fusionar el solape intra-vivienda con el solape entre viviendas).
        issues.append(_issue(
            r, "CRITICO", 9, "GEOMETRIA-SOLAPE-VIVIENDAS", "Solape de huella entre viviendas",
            "Dos viviendas comparten la misma superficie en el plano; indica un error de "
            "geometría o de agrupación de habitaciones, no un incumplimiento normativo "
            "verificado.",
            "Revisar la geometría de ambas viviendas: separarlas físicamente o corregir la agrupación "
            "de habitaciones si se trata de un error de etiquetado.",
            unit_name=f"{r.unit_a_name} / {r.unit_b_name}",
        ))

    # Integridad geométrica. Se lee directamente de `analysis` (no hace falta
    # parámetro nuevo: se calcula siempre, en los dos flujos). Va al final
    # porque no es un incumplimiento del proyecto sino del dato: cuando esto
    # aparece, las superficies de esa vivienda —y todo lo que se derive de
    # ellas, incluida su puntuación— no son fiables.
    for r in analysis.room_overlap:
        issues.append(_issue(
            r, "CRITICO", 0, "GEOMETRIA-SOLAPE", "Superficies solapadas dentro de la vivienda",
            "Dos piezas de la misma vivienda ocupan los mismos metros cuadrados, así que la "
            "superficie útil, la superficie total y la puntuación de esta vivienda están "
            "infladas. Ninguna cifra de superficie de esta vivienda es fiable mientras esto no "
            "se resuelva.",
            "Revisar el plano: lo habitual es que un contorno agrupador (el perímetro de la "
            "vivienda o de una zona abierta) esté dibujado en la misma capa que las estancias y "
            "se haya leído como una habitación más. Darle una capa propia, o etiquetarlo igual "
            "que la estancia que representa, resuelve el caso.",
            r.unit_name,
        ))

    return issues


@dataclass
class UnitScore:
    unit: Unit
    total_checks: int
    passed_checks: int
    score_pct: float
    basic_results: List[RuleResult] = field(default_factory=list)
    proportion_results: List[ProportionResult] = field(default_factory=list)
    hierarchy_results: List[HierarchyResult] = field(default_factory=list)
    efficiency_result: Optional[EfficiencyResult] = None
    orientation_results: List[OrientationResult] = field(default_factory=list)
    natural_light_results: List[NaturalLightResult] = field(default_factory=list)
    corridor_width_results: List[CorridorWidthResult] = field(default_factory=list)
    unit_minimum_area_result: Optional[UnitMinimumAreaResult] = None
    bathroom_accessibility_result: Optional[BathroomAccessibilityResult] = None
    bathroom_ratio_result: Optional[BathroomRatioResult] = None
    solar_hours_results: List[SolarHoursResult] = field(default_factory=list)
    cross_ventilation_result: Optional[CrossVentilationResult] = None
    entry_distance_results: List[EntryDistanceResult] = field(default_factory=list)
    spatial_hierarchy_result: Optional[SpatialHierarchyResult] = None
    circulation_efficiency_result: Optional[CirculationEfficiencyResult] = None
    room_depth_results: List[RoomDepthResult] = field(default_factory=list)
    natural_light_factor_results: List[NaturalLightFactorResult] = field(default_factory=list)
    acoustic_adjacency_results: List[AcousticAdjacencyResult] = field(default_factory=list)
    acoustic_exposure_results: List[AcousticExposureResult] = field(default_factory=list)
    evacuation_distance_results: List[EvacuationDistanceResult] = field(default_factory=list)
    bathroom_turning_space_results: List[BathroomTurningSpaceResult] = field(default_factory=list)
    minimum_room_width_results: List[MinimumRoomWidthResult] = field(default_factory=list)
    window_opening_results: List[WindowOpeningRatioResult] = field(default_factory=list)
    bedroom_minimum_area_results: List[BedroomMinimumAreaResult] = field(default_factory=list)
    accessible_bathroom_area_result: Optional[AccessibleBathroomAreaResult] = None
    itinerario_accesible_result: Optional[ItinerarioAccesibleResult] = None
    # Reglas que aplicaban a esta vivienda y NO se han podido comprobar por
    # falta de dato. No son incumplimientos ni cumplimientos: son huecos, y
    # tienen que verse. Van al campo "limitaciones" del JSON, junto a los
    # avisos de `get_missing_data_warnings`. Una regla no evaluable tampoco
    # entra en `checks`, para que no infle ni hunda la puntuación.
    limitaciones: List[str] = field(default_factory=list)

    @property
    def rating(self) -> str:
        return score_rating(self.score_pct)


def score_unit(
    unit: Unit,
    hierarchy: List[HierarchyResult],
    efficiency: List[EfficiencyResult],
    orientation: List[OrientationResult],
    norte_grados: float = 0.0,
    zona_cte: str = DEFAULT_ZONA_CTE,
    tipologia: str = DEFAULT_TIPOLOGIA,
    densidad_urbana: str = "media",
) -> UnitScore:
    """Calcula la puntuación de una vivienda como el % de comprobaciones
    superadas entre todas las reglas aplicables (básicas + avanzadas)."""
    basic_results = evaluate_rooms(unit.rooms)
    proportion_results = evaluate_proportions(unit.rooms)
    hierarchy_results = [h for h in hierarchy if h.unit_name == unit.name]
    efficiency_result = next((e for e in efficiency if e.unit_name == unit.name), None)
    natural_light_results = evaluate_natural_light(unit)
    corridor_width_results = evaluate_corridor_width(unit, tipologia)
    unit_minimum_area_result = evaluate_unit_minimum_area(unit, tipologia)
    bathroom_accessibility_result = evaluate_bathroom_accessibility(unit)
    bathroom_ratio_result = evaluate_bathroom_ratio(unit, tipologia)
    solar_hours_results = evaluate_solar_hours(unit, norte_grados, zona_cte)  # informativo, no entra en checks
    cross_ventilation_result = evaluate_cross_ventilation(unit, norte_grados)
    entry_distance_results = evaluate_entry_distance(unit)  # informativo, no entra en checks
    spatial_hierarchy_result = evaluate_spatial_hierarchy(unit)
    circulation_efficiency_result = evaluate_circulation_efficiency(unit)  # informativo, no entra en checks
    natural_lighting = evaluate_natural_lighting(unit)
    room_depth_results = natural_lighting.depth_results
    natural_light_factor_results = natural_lighting.factor_results
    acoustic_adjacency_results = evaluate_acoustic_adjacency(unit)  # informativo, no entra en checks
    evacuation_distance_results, evacuacion_no_evaluable = evaluate_evacuation_distance(unit)
    bathroom_turning_space_results = evaluate_bathroom_turning_space(unit, tipologia)
    minimum_room_width_results = evaluate_minimum_room_width(unit)
    window_opening_results = evaluate_window_opening_ratio(unit)
    bedroom_minimum_area_results = evaluate_bedroom_minimum_area(unit)
    accessible_bathroom_area_result = evaluate_accessible_bathroom_area(unit)

    # El itinerario accesible se calculaba dentro de `classify_problems`, y
    # `chain_effects` lo volvía a calcular por su cuenta: tres evaluaciones del
    # mismo predicado en un solo análisis. Ahora se calcula aquí, una vez, y
    # los dos lo leen de `UnitScore`.
    itinerario_accesible_result, itinerario_no_evaluable = evaluate_itinerario_accesible(unit, tipologia)

    limitaciones = [m for m in (evacuacion_no_evaluable, itinerario_no_evaluable) if m]

    unit_room_ids = {id(r) for r in unit.rooms}
    orientation_results = [o for o in orientation if id(o.room) in unit_room_ids]
    acoustic_exposure_results = evaluate_acoustic_exposure(unit, orientation_results, densidad_urbana)

    checks: List[bool] = []
    # `basic_results` (la tabla `RULES`: Salón>20, D1>10, D2>8, D3>6, Baño>3,
    # Aseo>1.5) NO entra en la puntuación desde 2026-08-05.
    #
    # Duplicaba el Bloque 20 (`evaluate_bedroom_minimum_area`) con umbrales
    # distintos y, a diferencia de aquel, no producía ninguna incidencia:
    # bajaba la nota sin que nada lo explicara. Caso real de `ejemplo.dxf`:
    # el Dormitorio 2 de VT3/3, de 7.17 m², FALLABA aquí (mínimo 8) y CUMPLÍA
    # el Bloque 20 (mínimo legal 6), así que la vivienda perdía puntos
    # mientras la regla visible declaraba que esa pieza estaba bien.
    #
    # De las dos, la que cita una fuente es el Bloque 20; ésta es una
    # convención de jerarquía por número de dormitorio, no un mínimo legal.
    # Se conserva el cálculo porque `plan_svg.room_problems` lo usa para
    # resaltar piezas y porque `main.py` (el flujo CLI) lo sigue listando.
    checks.extend(p.passed for p in proportion_results)
    checks.extend(h.passed for h in hierarchy_results)
    if efficiency_result is not None:
        checks.append(efficiency_result.passed)
    checks.extend(o.rating != "penalizada" for o in orientation_results if o.rating != "sin regla")
    checks.extend(nl.passed for nl in natural_light_results)
    checks.extend(cw.passed for cw in corridor_width_results)
    checks.append(unit_minimum_area_result.passed)
    if bathroom_accessibility_result is not None:
        checks.append(bathroom_accessibility_result.passed)
    if bathroom_ratio_result is not None:
        checks.append(bathroom_ratio_result.passed)
    if cross_ventilation_result is not None:
        checks.append(cross_ventilation_result.passed)
    if spatial_hierarchy_result is not None:
        checks.append(spatial_hierarchy_result.passed)
    checks.extend(d.passed for d in room_depth_results)
    # `natural_light_factor_results` ya no entra: regla retirada (siempre vacía).
    # `evacuation_distance_results` tampoco entra desde el Bloque B: es una
    # métrica informativa, no un veredicto (ver EvacuationDistanceResult).
    checks.extend(bt.passed for bt in bathroom_turning_space_results)
    checks.extend(mw.passed for mw in minimum_room_width_results)
    checks.extend(wo.passed for wo in window_opening_results)
    checks.extend(bm.passed for bm in bedroom_minimum_area_results)
    if accessible_bathroom_area_result is not None:
        checks.append(accessible_bathroom_area_result.passed)

    total = len(checks)
    passed = sum(1 for c in checks if c)
    score_pct = (passed / total * 100) if total else 100.0

    return UnitScore(
        unit=unit,
        total_checks=total,
        passed_checks=passed,
        score_pct=score_pct,
        basic_results=basic_results,
        proportion_results=proportion_results,
        hierarchy_results=hierarchy_results,
        efficiency_result=efficiency_result,
        orientation_results=orientation_results,
        natural_light_results=natural_light_results,
        corridor_width_results=corridor_width_results,
        unit_minimum_area_result=unit_minimum_area_result,
        bathroom_accessibility_result=bathroom_accessibility_result,
        bathroom_ratio_result=bathroom_ratio_result,
        solar_hours_results=solar_hours_results,
        cross_ventilation_result=cross_ventilation_result,
        entry_distance_results=entry_distance_results,
        spatial_hierarchy_result=spatial_hierarchy_result,
        circulation_efficiency_result=circulation_efficiency_result,
        room_depth_results=room_depth_results,
        natural_light_factor_results=natural_light_factor_results,
        acoustic_adjacency_results=acoustic_adjacency_results,
        acoustic_exposure_results=acoustic_exposure_results,
        evacuation_distance_results=evacuation_distance_results,
        bathroom_turning_space_results=bathroom_turning_space_results,
        minimum_room_width_results=minimum_room_width_results,
        window_opening_results=window_opening_results,
        bedroom_minimum_area_results=bedroom_minimum_area_results,
        accessible_bathroom_area_result=accessible_bathroom_area_result,
        itinerario_accesible_result=itinerario_accesible_result,
        limitaciones=limitaciones,
    )


# ---------------------------------------------------------------------------
# Orquestación del análisis avanzado
# ---------------------------------------------------------------------------


@dataclass
class AdvancedAnalysis:
    units: List[Unit]
    proportions: List[ProportionResult]
    hierarchy: List[HierarchyResult]
    efficiency: List[EfficiencyResult]
    orientation: List[OrientationResult]
    natural_light: List[NaturalLightResult]
    corridor_width: List[CorridorWidthResult]
    unit_minimum_area: List[UnitMinimumAreaResult]
    bathroom_accessibility: List[BathroomAccessibilityResult]
    bathroom_ratio: List[BathroomRatioResult]
    solar_hours: List[SolarHoursResult]
    cross_ventilation: List[CrossVentilationResult]
    entry_distance: List[EntryDistanceResult]
    spatial_hierarchy: List[SpatialHierarchyResult]
    circulation_efficiency: List[CirculationEfficiencyResult]
    room_depth: List[RoomDepthResult]
    natural_light_factor: List[NaturalLightFactorResult]
    acoustic_adjacency: List[AcousticAdjacencyResult]
    acoustic_exposure: List[AcousticExposureResult]
    evacuation_distance: List[EvacuationDistanceResult]
    bathroom_turning_space: List[BathroomTurningSpaceResult]
    minimum_room_width: List[MinimumRoomWidthResult]
    window_opening: List[WindowOpeningRatioResult]
    bedroom_minimum_area: List[BedroomMinimumAreaResult]
    accessible_bathroom_area: List[AccessibleBathroomAreaResult]
    fire_compartmentation: List[FireCompartmentationResult]
    room_overlap: List[RoomOverlapResult]
    unit_scores: List[UnitScore]


def evaluate_advanced_for_units(
    units: List[Unit],
    rooms: List[Room],
    norte_grados: float = 0.0,
    zona_cte: str = DEFAULT_ZONA_CTE,
    tipologia: str = DEFAULT_TIPOLOGIA,
    densidad_urbana: str = "media",
) -> AdvancedAnalysis:
    """Igual que `evaluate_advanced`, pero para cuando las viviendas ya están
    formadas de antemano (p. ej. `ai_generator`, que conoce de antemano qué
    habitación pertenece a qué vivienda porque las ha generado él mismo) en
    vez de tener que inferirlas por etiqueta o proximidad geométrica."""
    proportions = evaluate_proportions(rooms)
    hierarchy = evaluate_dormitory_hierarchy(units)
    efficiency = evaluate_unit_efficiency(units)
    orientation = evaluate_orientation(rooms, norte_grados)

    unit_scores = [
        score_unit(unit, hierarchy, efficiency, orientation, norte_grados, zona_cte, tipologia, densidad_urbana)
        for unit in units
    ]
    natural_light = [nl for us in unit_scores for nl in us.natural_light_results]
    corridor_width = [cw for us in unit_scores for cw in us.corridor_width_results]
    unit_minimum_area = [us.unit_minimum_area_result for us in unit_scores]
    bathroom_accessibility = [
        us.bathroom_accessibility_result for us in unit_scores if us.bathroom_accessibility_result is not None
    ]
    bathroom_ratio = [us.bathroom_ratio_result for us in unit_scores if us.bathroom_ratio_result is not None]
    solar_hours = [sh for us in unit_scores for sh in us.solar_hours_results]
    cross_ventilation = [
        us.cross_ventilation_result for us in unit_scores if us.cross_ventilation_result is not None
    ]
    entry_distance = [ed for us in unit_scores for ed in us.entry_distance_results]
    spatial_hierarchy = [
        us.spatial_hierarchy_result for us in unit_scores if us.spatial_hierarchy_result is not None
    ]
    circulation_efficiency = [
        us.circulation_efficiency_result for us in unit_scores if us.circulation_efficiency_result is not None
    ]
    room_depth = [rd for us in unit_scores for rd in us.room_depth_results]
    natural_light_factor = [nf for us in unit_scores for nf in us.natural_light_factor_results]
    acoustic_adjacency = [aa for us in unit_scores for aa in us.acoustic_adjacency_results]
    acoustic_exposure = [ae for us in unit_scores for ae in us.acoustic_exposure_results]
    evacuation_distance = [ev for us in unit_scores for ev in us.evacuation_distance_results]
    bathroom_turning_space = [bt for us in unit_scores for bt in us.bathroom_turning_space_results]
    minimum_room_width = [mw for us in unit_scores for mw in us.minimum_room_width_results]
    window_opening = [wo for us in unit_scores for wo in us.window_opening_results]
    bedroom_minimum_area = [bm for us in unit_scores for bm in us.bedroom_minimum_area_results]
    accessible_bathroom_area = [
        us.accessible_bathroom_area_result for us in unit_scores if us.accessible_bathroom_area_result is not None
    ]
    fire_compartmentation = evaluate_fire_compartmentation(units)
    room_overlap = evaluate_room_overlap(units)

    return AdvancedAnalysis(
        units=units,
        proportions=proportions,
        hierarchy=hierarchy,
        efficiency=efficiency,
        orientation=orientation,
        natural_light=natural_light,
        corridor_width=corridor_width,
        unit_minimum_area=unit_minimum_area,
        bathroom_accessibility=bathroom_accessibility,
        solar_hours=solar_hours,
        bathroom_ratio=bathroom_ratio,
        cross_ventilation=cross_ventilation,
        entry_distance=entry_distance,
        spatial_hierarchy=spatial_hierarchy,
        circulation_efficiency=circulation_efficiency,
        room_depth=room_depth,
        natural_light_factor=natural_light_factor,
        acoustic_adjacency=acoustic_adjacency,
        acoustic_exposure=acoustic_exposure,
        evacuation_distance=evacuation_distance,
        bathroom_turning_space=bathroom_turning_space,
        minimum_room_width=minimum_room_width,
        window_opening=window_opening,
        bedroom_minimum_area=bedroom_minimum_area,
        accessible_bathroom_area=accessible_bathroom_area,
        fire_compartmentation=fire_compartmentation,
        room_overlap=room_overlap,
        unit_scores=unit_scores,
    )


def evaluate_advanced(
    rooms: List[Room],
    unit_labels: Optional[List[Tuple[str, float, float]]] = None,
    norte_grados: float = 0.0,
    max_gap_m: float = MAX_GAP_BETWEEN_ROOMS_M,
    zona_cte: str = DEFAULT_ZONA_CTE,
    tipologia: str = DEFAULT_TIPOLOGIA,
    densidad_urbana: str = "media",
) -> AdvancedAnalysis:
    """Ejecuta las cuatro reglas avanzadas (proporciones, jerarquía,
    eficiencia, orientación) y calcula la puntuación de cada vivienda.

    Si se pasan `unit_labels` (etiquetas 'VT<n>/<m>' del plano), se usan para
    agrupar en viviendas reales; si no, se recurre a la agrupación por
    proximidad geométrica.
    """
    if unit_labels:
        units = group_rooms_by_unit_label(rooms, unit_labels)
    else:
        units = group_rooms_by_proximity(rooms, max_gap_m)

    return evaluate_advanced_for_units(units, rooms, norte_grados, zona_cte, tipologia, densidad_urbana)


# ---------------------------------------------------------------------------
# Urbanismo básico: ocupación, edificabilidad y plantas (a nivel de edificio)
# ---------------------------------------------------------------------------
# Estas reglas no evalúan habitaciones ni viviendas sino el edificio
# completo frente al solar y la normativa urbanística. Solo tienen sentido
# para un proyecto generado (`ai_generator`): un DXF analizado no trae
# datos de solar ni de normativa. El resultado va al campo
# "problemas_edificio" del JSON de salida, no a "problemas" de ninguna
# vivienda ni habitación, y no participa en `score_pct`.

_PLANTA_NAME_PATTERN = re.compile(r"^Planta\s*(\d+)", re.IGNORECASE)


def compute_floor_areas(units: List[Unit]) -> Dict[int, float]:
    """Superficie construida (suma de áreas de vivienda/local) por planta,
    a partir del nombre de la vivienda ('Planta <n> · <nombre>', la
    convención que usa `ai_generator._unit_from_dict`). Viviendas cuyo
    nombre no empieza así (p. ej. agrupación 'VT<n>/<m>' de un DXF
    analizado) no se asignan a ninguna planta."""
    areas: Dict[int, float] = {}
    for unit in units:
        match = _PLANTA_NAME_PATTERN.match(unit.name)
        if not match:
            continue
        floor = int(match.group(1))
        areas[floor] = areas.get(floor, 0.0) + unit.total_area_m2
    return areas


@dataclass
class SolarOccupationResult:
    ocupacion_pct: float
    maximo_pct: float
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"Ocupación: {self.ocupacion_pct:.0f}% supera el máximo permitido "
            f"de {self.maximo_pct:.0f}% (normativa urbanística)"
        )


def evaluate_solar_occupation(
    superficie_planta_baja_m2: float,
    superficie_solar_m2: float,
    normativa: dict,
) -> Optional[SolarOccupationResult]:
    """Ocupación = superficie construida en planta baja / superficie del
    solar — la ocupación urbanística española se mide sobre la huella en
    planta baja, no sobre el total edificado (eso lo cubre
    `evaluate_buildability`). Si no hay superficie de solar o la normativa
    no trae `ocupacion_maxima_pct`, no es evaluable (devuelve None)."""
    if not superficie_solar_m2:
        return None
    maximo_pct = normativa.get("ocupacion_maxima_pct")
    if maximo_pct is None:
        return None
    ocupacion_pct = superficie_planta_baja_m2 / superficie_solar_m2 * 100
    return SolarOccupationResult(
        ocupacion_pct=ocupacion_pct,
        maximo_pct=maximo_pct,
        passed=ocupacion_pct <= maximo_pct,
    )


@dataclass
class BuildabilityResult:
    edificabilidad_real: float
    maximo: float
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"Edificabilidad: {self.edificabilidad_real:.2f} m²/m² supera el "
            f"máximo permitido de {self.maximo:.2f} m²/m²"
        )


def evaluate_buildability(
    superficie_total_construida_m2: float,
    superficie_solar_m2: float,
    normativa: dict,
) -> Optional[BuildabilityResult]:
    """Edificabilidad = superficie total construida (todas las plantas) /
    superficie del solar, en m² techo / m² suelo. Parámetro opcional
    (`normativa["edificabilidad_maxima"]`, sin valor por defecto porque
    varía mucho según el municipio): si no viene informado, o no hay
    superficie de solar, no es evaluable (devuelve None)."""
    if not superficie_solar_m2:
        return None
    maximo = normativa.get("edificabilidad_maxima")
    if maximo is None:
        return None
    edificabilidad_real = superficie_total_construida_m2 / superficie_solar_m2
    return BuildabilityResult(
        edificabilidad_real=edificabilidad_real,
        maximo=maximo,
        passed=edificabilidad_real <= maximo,
    )


@dataclass
class MaxFloorsResult:
    plantas: int
    maximo: int
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"Altura: {self.plantas} plantas supera el máximo permitido de "
            f"{self.maximo} plantas (normativa urbanística)"
        )


def evaluate_max_floors(edificio: dict, normativa: dict) -> Optional[MaxFloorsResult]:
    """Si la normativa indica un número máximo de plantas
    (`normativa["plantas_maximas"]`, parámetro opcional), comprueba que el
    edificio no lo supere. Si no viene informado, no es evaluable
    (devuelve None; a diferencia de las dos reglas anteriores, esta
    ausencia no genera aviso en `get_missing_data_warnings` — el enunciado
    no lo pide)."""
    maximo = normativa.get("plantas_maximas")
    if maximo is None:
        return None
    plantas = edificio.get("plantas", 0)
    return MaxFloorsResult(plantas=plantas, maximo=maximo, passed=plantas <= maximo)


@dataclass
class RetranqueosResult:
    huella_ancho_m: float
    huella_largo_m: float
    severity: str  # "CRITICO" | "IMPORTANTE"

    @property
    def message(self) -> str:
        dims = f"{self.huella_ancho_m:.1f}×{self.huella_largo_m:.1f}m"
        if self.severity == "CRITICO":
            return (
                f"Retranqueos: la huella edificable resultante ({dims}) es nula o "
                "negativa — los retranqueos indicados no caben en las dimensiones del solar."
            )
        return (
            f"Retranqueos: la huella edificable resultante ({dims}) deja un margen "
            "muy ajustado (< 3m en algún lado)."
        )


def evaluate_retranqueos(solar: dict, normativa: dict) -> Optional[RetranqueosResult]:
    """Proxy simple de retranqueos, SIN geometría real de solar (ver
    advertencia condicional en `get_missing_data_warnings`, que sigue
    avisando cuando esto no es evaluable): resta 2×`retranqueos_m` del
    ancho y del largo del solar (asume solar rectangular y retranqueo
    simétrico en los 4 lados) y comprueba que la huella resultante sea
    positiva y no quede con un margen ínfimo. Si el solar no tiene
    ancho_m/largo_m (p. ej. forma "irregular") o no hay retranqueos_m, no
    es evaluable (devuelve None)."""
    ancho = solar.get("ancho_m")
    largo = solar.get("largo_m")
    retranqueo = normativa.get("retranqueos_m")
    if not ancho or not largo or retranqueo is None:
        return None

    huella_ancho = ancho - 2 * retranqueo
    huella_largo = largo - 2 * retranqueo

    if huella_ancho <= 0 or huella_largo <= 0:
        return RetranqueosResult(huella_ancho, huella_largo, "CRITICO")
    if huella_ancho < 3 or huella_largo < 3:
        return RetranqueosResult(huella_ancho, huella_largo, "IMPORTANTE")
    return None


# ---------------------------------------------------------------------------
# Compartimentación contra incendios por sector (proxy geométrico)
# ---------------------------------------------------------------------------
# El modelo no tiene datos de resistencia al fuego de muros ni forjados (ver
# aviso en `get_missing_data_warnings`), así que no se puede verificar la
# resistencia EI-60 real que exige el CTE DB-SI para separar sectores de
# incendio. Lo que sí se puede verificar geométricamente es una condición
# necesaria: que dos viviendas no compartan huella construida — si sus
# polígonos se solapan, la sectorización está rota (o hay un error de
# geometría/agrupación en el propio plano). No sustituye la comprobación de
# resistencia al fuego de los cerramientos, que sigue sin ser evaluable.

FIRE_COMPARTMENTATION_OVERLAP_TOLERANCE_M2 = 0.01


@dataclass
class FireCompartmentationResult:
    unit_a_name: str
    unit_b_name: str
    overlap_area_m2: float
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"Solape de huella: {self.unit_a_name} y {self.unit_b_name} comparten "
            f"{self.overlap_area_m2:.2f} m² -- error de geometría o de agrupación de "
            "habitaciones, no una comprobación normativa"
        )


def evaluate_fire_compartmentation(units: List[Unit]) -> List[FireCompartmentationResult]:
    """Comprueba, para cada par de viviendas, que sus huellas (unión de los
    polígonos de sus habitaciones) no se solapen más allá de una tolerancia
    geométrica mínima. Solo devuelve resultados para los pares con solape
    real (mismo criterio que `evaluate_condensaciones`/`evaluate_retranqueos`:
    lista de hallazgos, no de todas las combinaciones evaluadas)."""
    results: List[FireCompartmentationResult] = []
    footprints = [(unit, unary_union([r.polygon for r in unit.rooms])) for unit in units if unit.rooms]

    for i in range(len(footprints)):
        unit_a, footprint_a = footprints[i]
        for j in range(i + 1, len(footprints)):
            unit_b, footprint_b = footprints[j]
            overlap_area = footprint_a.intersection(footprint_b).area
            if overlap_area > FIRE_COMPARTMENTATION_OVERLAP_TOLERANCE_M2:
                results.append(
                    FireCompartmentationResult(
                        unit_a_name=unit_a.name,
                        unit_b_name=unit_b.name,
                        overlap_area_m2=overlap_area,
                        passed=False,
                    )
                )
    return results


# ---------------------------------------------------------------------------
# Integridad geométrica: solape entre piezas de una MISMA vivienda
# ---------------------------------------------------------------------------
# `evaluate_fire_compartmentation` (arriba) compara vivienda contra vivienda.
# Nadie comprobaba lo de dentro, y ahí es donde estaba el fallo más caro del
# motor: si `_discard_container_candidates` (parser.py) conserva el contorno
# agrupador de una vivienda porque ninguna pieza interior comparte su
# etiqueta, ese contorno entra en el análisis como si fuera una habitación
# más. Entonces la vivienda tiene una "pieza" que contiene físicamente a las
# demás, y toda superficie derivada —útil, total, ratio útil/total, superficie
# mínima de vivienda, puntuación— cuenta dos o tres veces los mismos metros.
#
# Medido en `ejemplo.dxf` el 2026-08-05: VT5/1 duplicaba 12,43 m² (18% de la
# vivienda) y VT6/2 duplicaba 27,32 m² (26%), con el Dormitorio 1 y el Baño
# íntegramente dentro del supuesto "Salón/cocina".
#
# ESTO DETECTA, NO CURA. La causa está en el parser y arreglarla ahí cambia
# las superficies de todos los proyectos ya guardados, así que es una decisión
# aparte. Lo que esta regla garantiza es que el análisis deje de ser
# silenciosamente falso: si las piezas se solapan, se dice.

ROOM_OVERLAP_TOLERANCE_M2 = 0.05  # ruido de dibujo; mismo orden que DEAD_SPACE_AREA_TOLERANCE_M2


@dataclass
class RoomOverlapResult:
    unit_name: str
    room_a_label: str
    room_b_label: str
    overlap_m2: float
    # % del área de la pieza MENOR que queda cubierta. 100% significa que una
    # pieza está entera dentro de la otra, que es la firma del contorno
    # agrupador colado como habitación.
    overlap_pct_menor: float
    passed: bool = False

    @property
    def room_label(self) -> str:
        return self.room_a_label

    @property
    def message(self) -> str:
        return (
            f"{self.room_a_label} y {self.room_b_label} se solapan "
            f"{self.overlap_m2:.2f} m² ({self.overlap_pct_menor:.0f}% de la pieza menor) "
            "— las superficies de esta vivienda están contadas más de una vez"
        )


def evaluate_room_overlap(units: List[Unit]) -> List[RoomOverlapResult]:
    """Pares de piezas de una misma vivienda cuyos polígonos se solapan.

    Devuelve solo los pares con solape real (mismo criterio de "lista de
    hallazgos, no de comprobaciones" que `evaluate_fire_compartmentation`).
    Dos piezas contiguas comparten borde pero no área, así que un solape por
    encima de la tolerancia no es ruido de dibujo: o el plano está mal, o el
    parser ha metido un contorno agrupador como si fuera una habitación."""
    results: List[RoomOverlapResult] = []
    for unit in units:
        rooms = unit.rooms
        for i in range(len(rooms)):
            for j in range(i + 1, len(rooms)):
                a, b = rooms[i], rooms[j]
                overlap = a.polygon.intersection(b.polygon).area
                if overlap <= ROOM_OVERLAP_TOLERANCE_M2:
                    continue
                menor = min(a.polygon.area, b.polygon.area)
                results.append(
                    RoomOverlapResult(
                        unit_name=unit.name,
                        room_a_label=a.label or "(sin etiqueta)",
                        room_b_label=b.label or "(sin etiqueta)",
                        overlap_m2=overlap,
                        overlap_pct_menor=(overlap / menor * 100) if menor > 0 else 0.0,
                    )
                )
    return results


# ---------------------------------------------------------------------------
# Altura libre mínima por uso (CTE DB-SUA-1, a nivel de edificio)
# ---------------------------------------------------------------------------
# Solo evaluable en proyectos generados (`altura_libre_m` es un parámetro de
# `edificio` que el arquitecto indica; un DXF analizado no trae datos de
# sección vertical — sigue cubierto por el aviso "no evaluable" de
# `get_missing_data_warnings` en ese flujo). El modelo no distingue zonas
# comunes de la vivienda (no hay geometría de portal/escalera), así que solo
# se comprueba el mínimo de zona habitable (2.50m); el mínimo de zonas
# comunes (2.20m) se deja como referencia informativa en el mensaje.

MIN_CEILING_HEIGHT_COMMON_M = 2.20  # CTE DB-SUA: altura libre mínima en zonas comunes (informativo, no evaluable)


@dataclass
class CeilingHeightResult:
    altura_libre_m: float
    minimo_m: float
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"Altura libre: {self.altura_libre_m:.2f}m por debajo del mínimo de "
            f"{self.minimo_m}m en zonas habitables (CTE DB-SUA-1; zonas comunes: "
            f"{MIN_CEILING_HEIGHT_COMMON_M}m)"
        )


def evaluate_ceiling_height(altura_libre_m: float) -> Optional[CeilingHeightResult]:
    """Comprueba que la altura libre del edificio (parámetro de proyecto,
    único dato de sección vertical disponible) alcance el mínimo CTE DB-SUA-1
    para zonas habitables. Si no se informa (<=0), no es evaluable."""
    if altura_libre_m <= 0:
        return None
    return CeilingHeightResult(
        altura_libre_m=altura_libre_m,
        minimo_m=MIN_CEILING_HEIGHT_M,
        passed=altura_libre_m >= MIN_CEILING_HEIGHT_M,
    )


# ---------------------------------------------------------------------------
# Eficiencia energética: compacidad y orientación pasiva (a nivel de edificio)
# ---------------------------------------------------------------------------
# Igual que la sección de urbanismo básico: estas reglas solo tienen
# sentido para un proyecto generado (`ai_generator`), se calculan en
# app.py junto a ocupación/edificabilidad/plantas máximas, y van al mismo
# campo "problemas_edificio" — no participan en `score_pct`.


def _floor_rooms(units: List[Unit], floor: int) -> List[Room]:
    """Habitaciones de todas las viviendas de una planta concreta,
    parseando el prefijo 'Planta <n> ·' del nombre (misma convención que
    `compute_floor_areas`)."""
    rooms: List[Room] = []
    for unit in units:
        match = _PLANTA_NAME_PATTERN.match(unit.name)
        if match and int(match.group(1)) == floor:
            rooms.extend(unit.rooms)
    return rooms


def compute_floor_perimeter_m(units: List[Unit], floor: int) -> float:
    """Perímetro de la unión de todas las habitaciones de una planta.

    ADVERTENCIA: en plantas con más de una vivienda, esto NO da el
    perímetro real del edificio — `ai_generator` sitúa cada vivienda en su
    propio carril de coordenadas, muy separado de las demás (ver
    `UNIT_OFFSET_M` en `ai_generator.py`), así que `unary_union` no las
    fusiona en una única huella: el resultado es la suma de los
    perímetros individuales de cada vivienda, sobreestimando el perímetro
    real (que descontaría los muros medianeros compartidos entre
    viviendas contiguas). Limitación conocida del modelo actual."""
    rooms = _floor_rooms(units, floor)
    if not rooms:
        return 0.0
    return unary_union([r.polygon for r in rooms]).boundary.length


@dataclass
class BuildingCompactnessResult:
    compacidad: float
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"Compacidad: {self.compacidad:.2f} m³/m² — edificio poco "
            "compacto, mayor pérdida de calor en invierno. Considerar "
            "geometría más regular (CTE DB-HE)"
        )


def evaluate_building_compactness(
    superficie_total_construida_m2: float,
    perimetro_planta_baja_m: float,
    altura_libre_m: float,
    zona_cte: str = DEFAULT_ZONA_CTE,
) -> Optional[BuildingCompactnessResult]:
    """Compacidad C = Volumen / Superficie envolvente (a mayor C, más
    compacto, menos pérdida de calor por m³ habitado). Volumen y
    superficie envolvente se estiman a partir de la superficie total
    construida, el perímetro de planta baja (ver advertencia de
    sobreestimación en `compute_floor_perimeter_m`) y la altura libre. El
    mínimo aceptable depende de la zona climática CTE (`UMBRALES_ZONA`).
    Solo evaluable con datos de edificio generado (siempre en
    `/api/generar`; nunca en un DXF analizado)."""
    if superficie_total_construida_m2 <= 0 or altura_libre_m <= 0:
        return None
    volumen = superficie_total_construida_m2 * altura_libre_m
    superficie_envolvente = (
        perimetro_planta_baja_m * altura_libre_m + 2 * superficie_total_construida_m2
    )
    if superficie_envolvente <= 0:
        return None
    compacidad = volumen / superficie_envolvente
    return BuildingCompactnessResult(
        compacidad=compacidad,
        passed=compacidad >= _umbrales_zona(zona_cte)["compact_ratio_min"],
    )


_ORIENTATION_RATIO_PATTERNS = [re.compile(r"SALON|COCINA")] + [pattern for _, pattern in DORMITORIO_PATTERNS]
_GOOD_PASSIVE_COMPASSES = {"S", "SE", "SO"}
MIN_SOUTH_FACING_RATIO_PCT = 40.0


@dataclass
class BuildingOrientationResult:
    south_facing_pct: float
    passed: bool

    @property
    def message(self) -> str:
        return (
            f"Orientación: solo {self.south_facing_pct:.0f}% de la "
            "superficie habitable orientada a sur/sureste/suroeste — "
            f"recomendado > {MIN_SOUTH_FACING_RATIO_PCT:.0f}% para "
            "eficiencia energética pasiva (CTE DB-HE)"
        )


def evaluate_building_orientation_ratio(
    orientation_results: List[OrientationResult],
) -> Optional[BuildingOrientationResult]:
    """Porcentaje de la superficie habitable (Salón/cocina + Dormitorios)
    de todo el edificio cuya fachada más larga se orienta a sur, sureste o
    suroeste — las orientaciones que más aportan a la eficiencia
    energética pasiva en España (CTE DB-HE). Reutiliza los
    `OrientationResult` ya calculados por `evaluate_orientation` para
    todas las viviendas del proyecto, sin recalcular fachadas. Informativo:
    va a `problemas_edificio` pero no participa en `score_pct` (que solo
    puntúa reglas por vivienda, nunca reglas de edificio)."""
    habitable = [
        o
        for o in orientation_results
        if o.room.label and any(p.search(_normalize(o.room.label)) for p in _ORIENTATION_RATIO_PATTERNS)
    ]
    total_area = sum(o.room.area_m2 for o in habitable)
    if total_area <= 0:
        return None
    south_area = sum(o.room.area_m2 for o in habitable if o.compass in _GOOD_PASSIVE_COMPASSES)
    south_facing_pct = south_area / total_area * 100
    return BuildingOrientationResult(
        south_facing_pct=south_facing_pct,
        passed=south_facing_pct >= MIN_SOUTH_FACING_RATIO_PCT,
    )
