"""Lectura y extracción de datos desde archivos DXF.

Se encarga de:
- Abrir el archivo DXF.
- Localizar polilíneas cerradas en el layer de áreas (habitaciones).
- Localizar etiquetas MTEXT y asociarlas a la habitación más cercana.
- Construir los objetos `Room` con su polígono (shapely) y área.
- Llevar el plano a metros (`leer_plano`), o negarse si no sabe en qué unidad
  está dibujado.

**Dos niveles, y la diferencia importa.** Las funciones sueltas
(`extract_room_polygons`, `extract_labels`, `extract_unit_labels`,
`build_rooms_from_document`) trabajan en **unidades de dibujo**, tal cual
vienen del DXF, y no saben nada de escala. `leer_plano` es la entrada de
verdad: lee todo junto, decide la escala y la aplica a la geometría *y* a las
coordenadas de las etiquetas de vivienda a la vez.

Todo lo que mire un plano de un usuario debe usar `leer_plano`. Escalar las
habitaciones y olvidarse de las etiquetas de vivienda —o al revés— produce
viviendas mal agrupadas sin ningún error visible, que es justo la clase de
fallo que este módulo existe ahora para evitar.
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import ezdxf
from ezdxf.document import Drawing
from shapely.affinity import scale as escalar_geometria
from shapely.geometry import Point, Polygon
from shapely.validation import explain_validity

from . import escala as escala_mod

_log = logging.getLogger(__name__)

AREA_LAYER = "00 areas"
BYLAYER_COLOR = 256

# ---------------------------------------------------------------------------
# Catálogo cerrado de capas del contrato de clasificación
#
# Fase 1 operó `AM_UTIL_INT`/`AM_CONS_CER`. Fase 3 añade `AM_UTIL_EXT`
# (superficie útil exterior: terrazas, tendederos, balcones...) y
# `AM_CONS_EXT` (superficie construida exterior), con el mismo patrón de
# lectura y validación que las dos primeras -- nunca como `Room`, nunca
# mezcladas entre categorías. `AM_DESCUENTO` sigue RESERVADA: el nombre
# existe para que un estudio que empiece a usarla pronto no tenga que migrar
# nada más adelante, pero ningún código de este módulo lee su contenido.
# Ver docs de diseño de las Fases 1 y 3 del contrato de clasificación DXF.
# ---------------------------------------------------------------------------

CAPA_UTIL_INTERIOR = "AM_UTIL_INT"
CAPA_CONSTRUIDA_CERRADA = "AM_CONS_CER"
CAPA_UTIL_EXTERIOR = "AM_UTIL_EXT"
CAPA_CONSTRUIDA_EXTERIOR = "AM_CONS_EXT"
CAPA_DESCUENTO = "AM_DESCUENTO"           # reservada, no operativa todavía

CAPAS_AM_OPERATIVAS = (
    CAPA_UTIL_INTERIOR, CAPA_CONSTRUIDA_CERRADA, CAPA_UTIL_EXTERIOR, CAPA_CONSTRUIDA_EXTERIOR,
)
CAPAS_AM_RESERVADAS = (CAPA_DESCUENTO,)
CATALOGO_CAPAS_AM = CAPAS_AM_OPERATIVAS + CAPAS_AM_RESERVADAS

# --- Motivos estables de descarte, para el inventario de geometría no leída
MOTIVO_TIPO_NO_SOPORTADO = "TIPO_NO_SOPORTADO"
MOTIVO_POLILINEA_ABIERTA = "POLILINEA_ABIERTA"
MOTIVO_MENOS_DE_3_VERTICES = "MENOS_DE_3_VERTICES"
MOTIVO_GEOMETRIA_INVALIDA = "GEOMETRIA_INVALIDA"

# Tipos de anotación: nunca representan el contorno de un recinto (son
# rótulos, cotas, líneas de referencia...) y su presencia en una capa de
# habitaciones -- heredada o `AM_*` -- es completamente normal: toda capa de
# áreas lleva el nombre de cada estancia escrito dentro. Si se inventariaran
# como "tipo no soportado", el inventario se llenaría de una entrada por
# cada rótulo del plano, y la señal real (un HATCH, un SPLINE, una LINE
# donde debería haber una polilínea) quedaría enterrada en ese ruido.
_TIPOS_ANOTACION = frozenset({
    "MTEXT", "TEXT", "ATTRIB", "ATTDEF", "DIMENSION", "LEADER", "MLEADER",
})


@dataclass(frozen=True)
class EntidadDescartada:
    """Una entidad del DXF que no ha entrado en el resultado, y por qué.

    Nunca se pierde en silencio: cualquier motivo de descarte (tipo no
    soportado, polilínea genuinamente abierta, geometría inválida...) queda
    aquí, con el handle cuando existe, para poder auditar sin releer el DXF
    a mano. `handle` puede ser `None` -- una entidad "virtual" generada al
    atravesar un bloque (`_recorrer_plano`) no siempre conserva uno propio.
    """

    motivo: str
    capa: str
    tipo: str
    handle: Optional[str] = None
    detalle: str = ""


def _handle_de(entity) -> Optional[str]:
    try:
        handle = entity.dxf.handle
        return handle or None
    except Exception:  # noqa: BLE001 - entidad ajena o virtual sin handle
        return None

# Umbral de contención para descartar contornos agrupadores: si un polígono
# cubre al menos este porcentaje del área de otro polígono más pequeño, se
# considera que lo "contiene" (ver `_discard_container_candidates`).
CONTAINMENT_THRESHOLD = 0.9

# Etiquetas de vivienda del plano, tipo "VT1/3", "VT2/2"... (distintas de las
# etiquetas de nombre de habitación como "Dormitorio 1").
UNIT_LABEL_PATTERN = re.compile(r"^VT\s*\d+", re.IGNORECASE)


@dataclass
class Room:
    """Habitación detectada: polígono cerrado + etiqueta de texto asociada."""

    label: Optional[str]
    polygon: Polygon
    layer: str

    @property
    def area_m2(self) -> float:
        """Área del polígono, en m² si la habitación viene de `leer_plano`.

        Antes este cálculo llevaba el comentario «se asume metros», y esa
        suposición era el peor defecto del proyecto: un DXF en milímetros
        entraba con cada área multiplicada por 1.000.000 y no fallaba —
        cumplía todas las superficies mínimas y salía con una puntuación alta
        y creíble. Ahora la conversión la hace `leer_plano`, que se niega a
        seguir si no sabe en qué unidad está dibujado el plano.

        Una `Room` construida por las funciones de bajo nivel sigue estando en
        unidades de dibujo: son ellas las que no saben de escala, no esta
        propiedad.
        """
        return self.polygon.area


class EscalaIndeterminada(ValueError):
    """No se puede saber en qué unidad está dibujado el plano.

    Lleva la `EscalaDetectada` completa —con su mensaje y, si la hay, la
    unidad sugerida— para que quien la reciba pueda preguntárselo al
    arquitecto en vez de tener que adivinarlo otra vez.
    """

    def __init__(self, deteccion):
        super().__init__(deteccion.mensaje)
        self.deteccion = deteccion


class CapaIndeterminada(ValueError):
    """No se sabe qué capa del DXF contiene las habitaciones.

    Lleva las candidatas ordenadas para poder preguntárselo al arquitecto con
    fundamento —«he encontrado 24 polilíneas cerradas en SUPERFICIES»— en vez
    de con un «no se pudo analizar el plano».
    """

    def __init__(self, candidatas, pedida: Optional[str] = None):
        self.candidatas = candidatas
        self.pedida = pedida
        super().__init__(_mensaje_de_capa(candidatas, pedida))


def _describir_capa(candidata) -> str:
    partes = ["%d polilíneas cerradas" % candidata.n_poligonos]
    if candidata.proporcion_rotulada:
        partes.append("%d%% con rótulo dentro" % round(candidata.proporcion_rotulada * 100))
    return "«%s» (%s)" % (candidata.nombre, ", ".join(partes))


def _mensaje_de_capa(candidatas, pedida: Optional[str]) -> str:
    if not candidatas:
        return (
            "No he encontrado ninguna capa con polilíneas cerradas que puedan ser habitaciones. "
            "ArchMuse necesita que cada estancia esté dibujada como una polilínea cerrada; si en "
            "este plano las superficies son sombreados o están dentro de bloques, todavía no "
            "puede leerlas."
        )
    lista = "; ".join(_describir_capa(c) for c in candidatas[:4])
    if pedida:
        return (
            "El plano no tiene ninguna capa llamada «%s» con habitaciones dentro. Las que más se "
            "parecen son: %s. Indica cuál contiene las estancias." % (pedida, lista)
        )
    return (
        "He encontrado varias capas que podrían contener las estancias y ninguna destaca lo "
        "suficiente: %s. Indica cuál es la buena." % lista
    )


@dataclass
class PlanoLeido:
    """Un DXF ya leído y llevado a metros."""

    rooms: List[Room] = field(default_factory=list)
    unit_labels: List[Tuple[str, float, float]] = field(default_factory=list)
    escala: object = None
    layer: str = AREA_LAYER
    capa: object = None
    # --- Contrato de clasificación (Fase 1) --------------------------------
    # Envolventes cerradas leídas de `AM_CONS_CER`, ya en metros. NUNCA son
    # `Room`: no tienen vivienda asignada aquí (eso es tarea de
    # `evaluator.asignar_envolvente_cerrada`, sobre `Unit`, no sobre
    # `PlanoLeido`) ni participan en ningún cálculo de superficie de este
    # módulo. Vacía si no hay `AM_CONS_CER` en el plano.
    envolventes_cerradas: List[Polygon] = field(default_factory=list)
    # --- Contrato de clasificación (Fase 3) --------------------------------
    # Mismo patrón exacto que `envolventes_cerradas`, una lista por
    # categoría -- nunca mezcladas entre sí ni con `rooms`. `AM_UTIL_EXT`
    # (superficie útil exterior: terrazas, tendederos, balcones...) y
    # `AM_CONS_EXT` (superficie construida exterior) admiten varias piezas
    # por vivienda a propósito (una vivienda puede tener más de una
    # terraza), así que aquí no hay ninguna decisión de unicidad que tomar
    # -- eso, si hace falta, es tarea de quien agrupe por vivienda
    # (`evaluator.asignar_superficies_exteriores`), no de esta lectura.
    superficies_utiles_exteriores: List[Polygon] = field(default_factory=list)
    envolventes_exteriores: List[Polygon] = field(default_factory=list)
    # Inventario de entidades descartadas -- de las capas `AM_*` operativas
    # SIEMPRE, y de la capa heredada (`00 areas` u otra elegida por
    # `capas_candidatas`) cuando no hay ninguna capa `AM_*` operativa en uso.
    # Ver `EntidadDescartada`.
    geometria_no_leida: List[EntidadDescartada] = field(default_factory=list)


def load_document(dxf_path: str) -> Drawing:
    """Abre un archivo DXF y devuelve el documento de ezdxf."""
    try:
        return ezdxf.readfile(dxf_path)
    except IOError as exc:
        raise FileNotFoundError(f"No se pudo abrir el archivo DXF: {dxf_path}") from exc
    except ezdxf.DXFStructureError as exc:
        raise ValueError(f"El archivo DXF está dañado o no es válido: {dxf_path}") from exc


def _polyline_points(entity) -> List[Tuple[float, float]]:
    """Devuelve los vértices (x, y) de una LWPOLYLINE o POLYLINE clásica."""
    if entity.dxftype() == "LWPOLYLINE":
        return [(float(p[0]), float(p[1])) for p in entity.get_points()]
    if entity.dxftype() == "POLYLINE":
        return [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in entity.vertices]
    return []


# Tolerancia RELATIVA para recuperar como cerrada una polilínea con
# `closed=False` cuyo primer y último vértice casi coinciden: una fracción de
# la diagonal de su propia caja envolvente, no un valor absoluto en unidades
# de dibujo -- que no significan nada sin conocer la escala del plano (mm, cm
# o m; ver docstring del módulo). Mismo criterio que `TOLERANCIA_ETIQUETA` más
# abajo, aplicado aquí al cierre en vez de al rótulo.
#
# Calibrada contra dos DXF reales donde se detectó el fallo que esta
# constante corrige (`tests/test_cierre_recuperado.py`, casos con `V5.dxf` y
# `v2s.dxf`): el hueco real más grande encontrado fue el 0,70% de la diagonal
# (una polilínea de "Dormitorio 3" en V5.dxf, capa "00 areas"). 1% deja
# margen sin acercarse a lo que sería una polilínea genuinamente abierta.
TOLERANCIA_CIERRE = 0.01


def _extremos_coinciden(points: List[Tuple[float, float]]) -> bool:
    """True si el primer y el último vértice de `points` están lo bastante
    cerca -- relativo al tamaño de la propia polilínea -- como para tratarla
    como un anillo cerrado aunque el flag DXF diga lo contrario.

    El tamaño de referencia es la diagonal de la caja envolvente: barato de
    calcular (no hace falta construir el polígono) y sólo es cero cuando
    todos los vértices coinciden -- una polilínea degenerada, que aquí NO se
    recupera.
    """
    if len(points) < 3:
        return False
    x0, y0 = points[0]
    x1, y1 = points[-1]
    gap = math.hypot(x1 - x0, y1 - y0)
    if gap == 0.0:
        return True
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    diagonal = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    if diagonal <= 0.0:
        return False
    return gap <= TOLERANCIA_CIERRE * diagonal


def _recuperar_cierre_por_geometria(entity) -> bool:
    """Segunda oportunidad para una polilínea con `closed=False`: si sus
    extremos casi coinciden (`_extremos_coinciden`), se trata como cerrada.

    La recuperación se registra SIEMPRE con `_log.warning`, nunca en
    silencio: tratar como cerrada una polilínea que el propio archivo declara
    abierta es una corrección de datos, no un hecho neutro, y tiene que
    quedar visible para quien audite después por qué una habitación entró
    (o no) en el análisis.
    """
    points = _polyline_points(entity)
    if not _extremos_coinciden(points):
        return False
    x0, y0 = points[0]
    x1, y1 = points[-1]
    gap = math.hypot(x1 - x0, y1 - y0)
    _log.warning(
        "Polilinea con closed=False tratada como cerrada: el primer y el "
        "ultimo vertice distan %.4g unidades de dibujo (capa %r, handle %r). "
        "El flag 'closed' del DXF de origen esta mal puesto.",
        gap,
        getattr(entity.dxf, "layer", "?"),
        getattr(entity.dxf, "handle", "?"),
    )
    return True


def _esta_cerrada(entity, recuperar_geometria: bool = True) -> bool:
    """True si la polilínea debe tratarse como un anillo cerrado.

    Primero mira el flag DXF (`closed` / `is_closed`), que es la fuente de
    verdad cuando está bien puesto. Si el flag dice que no lo está, se da una
    segunda oportunidad geométrica (`_recuperar_cierre_por_geometria`): un
    hueco de redondeo de unos pocos centímetros entre el primer y el último
    vértice no es una polilínea abierta, es un flag mal puesto -- un fallo
    real, no hipotético: es la causa exacta de que el salón de una vivienda
    entera (VT1/3) desapareciera del análisis en dos proyectos reales
    (`tests/test_cierre_recuperado.py`).

    `recuperar_geometria=False` conserva el comportamiento exacto de antes de
    este cambio (sólo cuenta el flag). Lo usa `_poligonos_cerrados_por_capa`
    -- el heurístico de detección de capa (`capas_candidatas`) -- porque esta
    corrección no toca el sistema de capas: cambia qué habitaciones se leen
    de la capa ya elegida, no qué capa se elige.
    """
    tipo = entity.dxftype()
    if tipo not in ("LWPOLYLINE", "POLYLINE"):
        return False
    try:
        cerrada_por_flag = bool(entity.closed) if tipo == "LWPOLYLINE" else bool(entity.is_closed)
    except Exception:  # noqa: BLE001 - DXF ajeno: entidad mal formada
        return False
    if cerrada_por_flag:
        return True
    if not recuperar_geometria:
        return False
    return _recuperar_cierre_por_geometria(entity)


# ---------------------------------------------------------------------------
# Recorrido del plano, bloques incluidos (tarea 8 del PRD de ingesta)
# ---------------------------------------------------------------------------

# Hasta dónde se desciende por referencias de bloque anidadas. Tres niveles
# cubren el montaje habitual (planta → vivienda → mobiliario) sin arriesgarse a
# dar vueltas en un DXF con bloques que se referencian entre sí.
PROFUNDIDAD_MAX_BLOQUES = 3

# Tope de entidades a examinar. Un plano de urbanización con miles de
# inserciones puede multiplicar el trabajo sin aportar ni una habitación; antes
# que tardar un minuto sin decir nada, se corta.
MAX_ENTIDADES = 400_000


def _capa_efectiva(entity, capa_del_insert: Optional[str]) -> str:
    """Capa real de una entidad, resolviendo la herencia dentro de bloques.

    Una entidad dibujada en la capa «0» dentro de un bloque **no está en la
    capa 0**: toma la capa de la referencia que la inserta. Es convención DXF
    de toda la vida y ezdxf no la aplica — `virtual_entities()` devuelve la
    capa literal—, así que hay que hacerlo aquí. Comprobado antes de escribir
    esto: un polígono en capa «0» dentro de un bloque insertado en «AREAS»
    vuelve de `virtual_entities()` como «0».

    Sin esta resolución, atravesar los bloques serviría de poco: dibujar las
    habitaciones en la capa 0 dentro del bloque es justo lo más habitual.
    """
    try:
        propia = entity.dxf.layer
    except AttributeError:
        propia = "0"
    if capa_del_insert is not None and propia == "0":
        return capa_del_insert
    return propia


def _recorrer_plano(doc: Drawing):
    """Genera `(entidad, capa_efectiva)` de todo el modelspace, **entrando en
    las referencias de bloque**.

    Hasta ahora `parser.py` solo miraba el primer nivel del modelspace, así que
    todo lo que estuviera dentro de un bloque era invisible: cero habitaciones
    y ninguna explicación. `virtual_entities()` devuelve las entidades ya
    transformadas al sistema de coordenadas del plano (traslación, rotación y
    escala del INSERT incluidas), así que aquí no se transforma nada a mano;
    lo único que hay que resolver es la capa (ver `_capa_efectiva`).
    """
    presupuesto = [MAX_ENTIDADES]

    def bajar(entidades, capa_del_insert, profundidad):
        for entity in entidades:
            if presupuesto[0] <= 0:
                return
            presupuesto[0] -= 1
            capa = _capa_efectiva(entity, capa_del_insert)
            if entity.dxftype() == "INSERT":
                if profundidad >= PROFUNDIDAD_MAX_BLOQUES:
                    continue
                try:
                    hijos = list(entity.virtual_entities())
                except Exception:  # noqa: BLE001 - bloque roto o referencia circular
                    continue
                yield from bajar(hijos, capa, profundidad + 1)
            else:
                yield entity, capa

    yield from bajar(doc.modelspace(), None, 0)


def _closed_polygons_with_color(
    doc: Drawing, layer: str, descartes: Optional[List[EntidadDescartada]] = None
) -> List[Tuple[Polygon, int]]:
    """Polilíneas cerradas del layer indicado como (polígono, color DXF),
    bloques incluidos.

    `descartes`, si se pasa una lista, se rellena con el inventario de
    entidades de esta capa que NO han entrado en el resultado (tipo no
    soportado, o polilínea que sigue abierta incluso con la recuperación
    geométrica de `_esta_cerrada`). Es aditivo y opcional a propósito: por
    defecto (`descartes=None`) el resultado y el comportamiento son
    idénticos a antes de que existiera este parámetro -- el modo heredado
    NO valida `is_valid` aquí, para no excluir de golpe geometría que hoy SÍ
    se acepta como `Room` (ver informe de la Fase 1 del contrato de
    clasificación DXF).
    """
    entries: List[Tuple[Polygon, int]] = []
    for entity, capa in _recorrer_plano(doc):
        if capa != layer:
            continue
        tipo = entity.dxftype()
        if tipo in _TIPOS_ANOTACION:
            continue
        if not _esta_cerrada(entity):
            if descartes is not None:
                motivo = (
                    MOTIVO_TIPO_NO_SOPORTADO if tipo not in ("LWPOLYLINE", "POLYLINE")
                    else MOTIVO_POLILINEA_ABIERTA
                )
                descartes.append(EntidadDescartada(
                    motivo=motivo, capa=capa, tipo=tipo, handle=_handle_de(entity)))
            continue
        points = _polyline_points(entity)
        if len(points) >= 3:
            entries.append((Polygon(points), entity.dxf.color))
        elif descartes is not None:
            descartes.append(EntidadDescartada(
                motivo=MOTIVO_MENOS_DE_3_VERTICES, capa=capa, tipo=tipo,
                handle=_handle_de(entity)))
    return entries


def _normalize_room_label(label: Optional[str]) -> str:
    return (label or "").strip().upper()


def _discard_container_candidates(
    entries: List[Tuple[Polygon, int, Optional[str]]], threshold: float = CONTAINMENT_THRESHOLD
) -> List[Polygon]:
    """Descarta polígonos que sean el contorno agrupador de una habitación ya
    representada por su propio polígono independiente (p. ej. el contorno del
    salón + cocina abierto de toda una planta, cuando ese salón ya tiene su
    propia polilínea más pequeña, o el bloque completo de tendederos de una
    fachada cuando cada tendedero ya está dibujado por separado). Mismo patrón
    de bug ya detectado y corregido en ArchSurface.

    Un polígono se descarta como "contenedor duplicado" solo si:
    - su color DXF explícito NO es BYLAYER (las habitaciones reales de estos
      planos siempre usan el color del layer; los contornos agrupadores se
      dibujan con un color propio, típicamente ACI 10 o ACI 150),
    - contiene geométricamente a otro polígono real (BYLAYER) más pequeño del
      mismo layer (la intersección cubre >= `threshold` del área de ese
      polígono menor), y
    - ese polígono contenido tiene la MISMA etiqueta que el propio contenedor
      (misma habitación, ya representada de forma independiente).

    Si el contorno contiene otras habitaciones de tipo distinto (p. ej. un
    dormitorio o un baño dentro del mismo perímetro del salón) pero NINGUNA
    con su propia etiqueta, se conserva: es la única representación de esa
    habitación en el plano, y descartarlo dejaría a la vivienda sin esa
    superficie habitable.
    """
    kept: List[Polygon] = []
    for i, (polygon, color, label) in enumerate(entries):
        own_label = _normalize_room_label(label)
        is_duplicate = color != BYLAYER_COLOR and own_label != "" and any(
            j != i
            and other_color == BYLAYER_COLOR
            and _normalize_room_label(other_label) == own_label
            and polygon.area > other.area
            and polygon.intersection(other).area >= threshold * other.area
            for j, (other, other_color, other_label) in enumerate(entries)
        )
        if not is_duplicate:
            kept.append(polygon)
    return kept


def extract_room_polygons(
    doc: Drawing, layer: str = AREA_LAYER, descartes: Optional[List[EntidadDescartada]] = None
) -> List[Polygon]:
    """Busca polilíneas cerradas en el layer indicado, las convierte en
    polígonos shapely y descarta los contornos agrupadores duplicados
    (ver `_discard_container_candidates`). `descartes`: ver
    `_closed_polygons_with_color`."""
    entries = _closed_polygons_with_color(doc, layer, descartes=descartes)
    labels = extract_labels(doc)
    labeled_entries = [
        (polygon, color, match_label_to_room(polygon, labels)) for polygon, color in entries
    ]
    return _discard_container_candidates(labeled_entries)


def _punto_de_texto(entity) -> Optional[Tuple[float, float]]:
    """Punto de inserción efectivo de un MTEXT o un TEXT.

    Un `TEXT` alineado —centrado dentro de la habitación, que es como se rotula
    media España— guarda su posición real en `align_point`, no en `insert`.
    Según la especificación DXF, `align_point` solo cuenta si `halign` o
    `valign` son distintos de cero; si se ignora esa regla, un rótulo centrado
    aterriza donde no está y se asocia a la habitación equivocada.
    """
    try:
        punto = None
        if entity.dxftype() == "TEXT":
            halign = entity.dxf.get("halign", 0) or 0
            valign = entity.dxf.get("valign", 0) or 0
            if (halign or valign) and entity.dxf.hasattr("align_point"):
                punto = entity.dxf.align_point
        if punto is None:
            punto = entity.dxf.insert
        return float(punto.x), float(punto.y)
    except Exception:  # noqa: BLE001 - DXF ajeno: la entidad puede venir sin punto usable
        return None


def _texto_de(entity) -> str:
    """Contenido legible de un MTEXT o un TEXT, sin códigos de formato."""
    try:
        return entity.plain_text().strip()
    except Exception:  # noqa: BLE001
        try:
            return str(entity.dxf.text).strip()
        except Exception:  # noqa: BLE001
            return ""


def extract_labels(doc: Drawing) -> List[Tuple[str, float, float]]:
    """Rótulos del plano como (texto, x, y), **con los MTEXT antes que los TEXT**.

    Ese orden no es cosmético, es la regla de desempate: `match_label_to_room`
    se queda con el primer rótulo que caiga dentro del polígono, así que un
    MTEXT gana a un TEXT que esté dentro de la misma habitación.

    Hace falta porque un plano que rotula las estancias con MTEXT usa los TEXT
    para otras cosas. En `ejemplo.dxf`, sin ir más lejos, hay cinco TEXT del
    tipo «PE-01» y «VE-01» —marcas de carpintería— y dos caen dentro de una
    habitación: leerlos sin prioridad renombraría dos estancias, y el tipo de
    habitación es de donde cuelga medio motor de reglas.

    En un plano rotulado solo con TEXT no hay MTEXT que compita y se usan
    directamente, que es de lo que trata la tarea 7 del PRD de ingesta.
    """
    por_tipo = {"MTEXT": [], "TEXT": []}

    for entity, _capa in _recorrer_plano(doc):
        tipo = entity.dxftype()
        if tipo not in por_tipo:
            continue
        text = _texto_de(entity)
        if not text:
            continue
        punto = _punto_de_texto(entity)
        if punto is None:
            continue
        por_tipo[tipo].append((text, punto[0], punto[1]))

    # El recorrido devuelve las entidades entremezcladas, así que la prioridad
    # de MTEXT sobre TEXT se restablece aquí, al agrupar.
    return por_tipo["MTEXT"] + por_tipo["TEXT"]


# Cuánto puede alejarse un rótulo del borde de su habitación, medido en
# "lados equivalentes" de esa habitación (la raíz de su superficie). Un rótulo
# sacado con una directriz desde un aseo pequeño está a las afueras de la
# estancia; el nombre de otra vivienda está a decenas de metros.
#
# El umbral es RELATIVO a propósito. Un valor absoluto en metros sería una
# suposición de escala más, y este módulo acaba de dejar de hacer suposiciones
# de escala: `match_label_to_room` trabaja en unidades de dibujo, antes de la
# conversión, así que "3 metros" no significa nada aquí. Un cociente entre dos
# longitudes del mismo dibujo se comporta igual en metros que en milímetros.
#
# El valor es PROVISIONAL y no está calibrado contra nada: en `ejemplo.dxf` las
# 34 habitaciones tienen su rótulo dentro, así que este repliegue no se ejecuta
# ni una vez sobre el único plano real disponible. Es una salvaguarda para
# planos ajenos, no un parámetro medido, y hay que revisarlo con los archivos
# de la tarea 2 del PRD.
#
# Límite conocido: acotar la distancia hace la búsqueda LOCAL, no EXCLUSIVA.
# Dos estancias contiguas pueden caer las dos dentro del límite de un mismo
# rótulo y quedárselo las dos. Resolverlo pide una asignación global —cada
# rótulo a una sola habitación— que es otro problema y otra tarea.
TOLERANCIA_ETIQUETA = 0.5


def match_label_to_room(polygon: Polygon, labels: List[Tuple[str, float, float]]) -> Optional[str]:
    """Asocia el rótulo más adecuado a un polígono, o `None` si no hay ninguno
    que pueda ser suyo.

    Primero busca rótulos cuyo punto de inserción caiga dentro del polígono
    (caso habitual: el texto está dentro de la habitación). Como `extract_labels`
    devuelve los MTEXT antes que los TEXT, un MTEXT gana a un TEXT que esté
    dentro de la misma estancia.

    Si no hay ninguno dentro, se recurre al más cercano **pero solo si está lo
    bastante cerca**. Antes no había límite: el rótulo más próximo de todo el
    plano se adjudicaba a la habitación aunque estuviera a la otra punta, así
    que en un plano con varias viviendas separadas una estancia podía heredar
    el nombre de otra vivienda, y todas las estancias sin rótulo del plano
    acababan llamándose igual. Verificado con un caso reproducible al escribir
    `tests/test_etiquetas.py`.

    Preferir `None` a un nombre ajeno no es una pérdida: una habitación sin
    nombre se evalúa por lo que se puede medir de ella, mientras que una
    habitación con el nombre equivocado se evalúa contra las reglas de otro
    tipo de estancia — un salón juzgado como dormitorio, o al revés.
    """
    inside = [text for text, x, y in labels if polygon.contains(Point(x, y))]
    if inside:
        return inside[0]

    if not labels or polygon.is_empty or polygon.area <= 0:
        return None

    # Distancia al BORDE, no al centroide: lo que interesa es cuánto se aleja
    # el rótulo de la habitación, no cuánto mide la habitación.
    texto, x, y = min(labels, key=lambda item: polygon.distance(Point(item[1], item[2])))
    limite = TOLERANCIA_ETIQUETA * math.sqrt(polygon.area)
    if polygon.distance(Point(x, y)) > limite:
        return None
    return texto


def extract_unit_labels(doc: Drawing) -> List[Tuple[str, float, float]]:
    """Etiquetas de vivienda del plano: rótulos con formato 'VT<n>/<m>'
    (ej. 'VT1/3'), que identifican las viviendas reales del proyecto — a
    diferencia de las etiquetas de nombre de habitación que devuelve
    `extract_labels`.

    Lee MTEXT y TEXT, igual que `extract_labels`: no hay ninguna razón para que
    la etiqueta de una vivienda tenga que estar dibujada como MTEXT.
    """
    return [etiqueta for etiqueta in extract_labels(doc) if UNIT_LABEL_PATTERN.match(etiqueta[0])]


def build_rooms_from_document(
    doc: Drawing, layer: str = AREA_LAYER, descartes: Optional[List[EntidadDescartada]] = None
) -> List[Room]:
    """Habitaciones del documento, **en unidades de dibujo**.

    No convierte a metros: para eso está `leer_plano`, que es lo que debe usar
    cualquier código que mire el plano de un usuario. Esta función se conserva
    porque es el escalón sobre el que se apoya `leer_plano` y porque el
    guardián de regresión (`tests/test_ingesta_regresion.py`) la usa
    precisamente para vigilar que la lectura en crudo no cambie.

    `descartes`: ver `_closed_polygons_with_color`.
    """
    polygons = extract_room_polygons(doc, layer, descartes=descartes)
    labels = extract_labels(doc)

    rooms: List[Room] = []
    for polygon in polygons:
        label = match_label_to_room(polygon, labels)
        rooms.append(Room(label=label, polygon=polygon, layer=layer))

    return rooms


# ---------------------------------------------------------------------------
# Lectura validada de capas AM_* operativas (Fase 1 del contrato de
# clasificación DXF)
# ---------------------------------------------------------------------------


def _leer_capa_am(doc: Drawing, capa: str) -> Tuple[List[Polygon], List[EntidadDescartada]]:
    """Polígonos válidos de una capa `AM_*` operativa, y el inventario de lo
    que se ha descartado y por qué.

    Reutiliza `_recorrer_plano` (herencia de capa dentro de bloques) y
    `_esta_cerrada` (con la recuperación geométrica ya existente) tal cual
    están -- esta función no reimplementa nada de eso. Lo único que añade es
    la validación que el contrato de clasificación exige para una capa
    `AM_*`: cerrada, >= 3 vértices, polígono geométricamente válido. Ninguna
    geometría inválida se repara nunca aquí -- se descarta y se reporta.
    """
    poligonos: List[Polygon] = []
    descartes: List[EntidadDescartada] = []
    for entity, capa_efectiva in _recorrer_plano(doc):
        if capa_efectiva != capa:
            continue
        tipo = entity.dxftype()
        if tipo in _TIPOS_ANOTACION:
            continue
        if tipo not in ("LWPOLYLINE", "POLYLINE"):
            descartes.append(EntidadDescartada(
                motivo=MOTIVO_TIPO_NO_SOPORTADO, capa=capa, tipo=tipo,
                handle=_handle_de(entity)))
            continue
        if not _esta_cerrada(entity):
            descartes.append(EntidadDescartada(
                motivo=MOTIVO_POLILINEA_ABIERTA, capa=capa, tipo=tipo,
                handle=_handle_de(entity)))
            continue
        points = _polyline_points(entity)
        if len(points) < 3:
            descartes.append(EntidadDescartada(
                motivo=MOTIVO_MENOS_DE_3_VERTICES, capa=capa, tipo=tipo,
                handle=_handle_de(entity)))
            continue
        polygon = Polygon(points)
        if not polygon.is_valid:
            descartes.append(EntidadDescartada(
                motivo=MOTIVO_GEOMETRIA_INVALIDA, capa=capa, tipo=tipo,
                handle=_handle_de(entity), detalle=explain_validity(polygon)))
            continue
        poligonos.append(polygon)
    return poligonos, descartes


def leer_plano(doc: Drawing, layer: Optional[str] = None, factor_escala: Optional[float] = None) -> PlanoLeido:
    """Lee el plano entero y lo lleva a metros. Entrada única del pipeline.

    Resuelve dos incógnitas, en este orden, y con el mismo criterio en las dos:
    **qué capa** contiene las estancias y **en qué unidad** está dibujado. Si
    cualquiera de las dos no se puede resolver con seguridad, se lanza
    `CapaIndeterminada` o `EscalaIndeterminada` —las dos hijas de `ValueError`,
    las dos con la información necesaria para preguntar— en vez de suponer.
    Preferir un error a un análisis inventado es el cambio de criterio que
    introduce esta función.

    `layer` es la respuesta del arquitecto cuando la hay. Si viene a `None` se
    deduce: primero se mira si `AREA_LAYER` existe y sirve —de ahí que
    sobreviva como valor por defecto y no como requisito—, y si no, se elige
    por parecido (`capas_candidatas`).

    Si `factor_escala` viene informado, se aplica sin más. Si no, se deduce
    cruzando `$INSUNITS` con el tamaño de las estancias (`analyzer/escala.py`).

    La escala se aplica a la geometría de las habitaciones y a las coordenadas
    de las etiquetas de vivienda **en el mismo sitio y a la vez**, que es la
    razón de que esta función exista en lugar de un parámetro suelto en cada
    extractor: `group_rooms_by_unit_label` compara distancias entre unas y
    otras, así que escalar solo la mitad agruparía mal las viviendas sin dar
    ningún error.

    **Contrato de clasificación (Fase 1).** Antes de decidir de dónde salen
    las habitaciones, se leen las dos capas `AM_*` operativas
    (`_leer_capa_am`). Si `AM_UTIL_INT` tiene algún polígono válido, ES la
    fuente de las habitaciones -- ni se llama a `_resolver_capa` ni se toca
    el modo heredado en absoluto; mezclar los dos duplicaría habitaciones si
    el plano tuviera, por ejemplo, las mismas piezas dibujadas a la vez en
    "00 areas" y en "AM_UTIL_INT". Si `AM_UTIL_INT` está vacía o ausente, el
    modo heredado se comporta exactamente igual que antes de esta función
    saber nada de capas `AM_*` -- es la garantía de que un plano sin
    clasificar no cambia de resultado ni un metro cuadrado. `AM_CONS_CER`,
    `AM_UTIL_EXT` y `AM_CONS_EXT` (Fase 3) son independientes de cuál de los
    dos caminos anteriores se tome, e independientes también entre sí: cada
    una alimenta su propia lista si tiene contenido válido, y queda vacía si
    no. Ninguna de las cuatro capas exige que otra exista -- pueden coexistir
    todas, algunas, o ninguna.

    **Presente pero sin recintos válidos no es lo mismo que ausente.** Si
    `AM_UTIL_INT` tiene contenido -aunque sea solo geometría descartada, p.
    ej. una capa recién creada con una polilínea todavía abierta- se
    considera declarada y se usa igualmente como fuente (con `rooms=[]` si
    no queda nada válido). Caer al modo heredado en ese caso mezclaría en
    silencio una capa que el arquitecto ya empezó a clasificar con una capa
    distinta que nunca quiso usar -- justo el tipo de sustitución silenciosa
    que este contrato existe para evitar. Esta regla es exclusiva de
    `AM_UTIL_INT`, la única de las cuatro que puede sustituir al modo
    heredado; las otras tres solo se leen, sin sustituir nada.
    """
    geometria_no_leida: List[EntidadDescartada] = []

    poligonos_util_int, descartes_util = _leer_capa_am(doc, CAPA_UTIL_INTERIOR)
    geometria_no_leida.extend(descartes_util)
    poligonos_cons_cer, descartes_cons = _leer_capa_am(doc, CAPA_CONSTRUIDA_CERRADA)
    geometria_no_leida.extend(descartes_cons)
    poligonos_util_ext, descartes_util_ext = _leer_capa_am(doc, CAPA_UTIL_EXTERIOR)
    geometria_no_leida.extend(descartes_util_ext)
    poligonos_cons_ext, descartes_cons_ext = _leer_capa_am(doc, CAPA_CONSTRUIDA_EXTERIOR)
    geometria_no_leida.extend(descartes_cons_ext)

    usa_capa_am = bool(poligonos_util_int) or bool(descartes_util)
    if usa_capa_am:
        labels = extract_labels(doc)
        rooms = [
            Room(label=match_label_to_room(polygon, labels), polygon=polygon, layer=CAPA_UTIL_INTERIOR)
            for polygon in poligonos_util_int
        ]
        capa = None
        nombre_capa = CAPA_UTIL_INTERIOR
    else:
        capa = _resolver_capa(doc, layer)
        nombre_capa = capa.nombre
        rooms = build_rooms_from_document(doc, capa.nombre, descartes=geometria_no_leida)

    unit_labels = extract_unit_labels(doc)

    if factor_escala is not None:
        deteccion = escala_mod.escala_confirmada(factor_escala)
    else:
        deteccion = escala_mod.detectar_escala(
            escala_mod.leer_insunits(doc), [room.polygon.area for room in rooms]
        )
        if not deteccion.decidida:
            raise EscalaIndeterminada(deteccion)

    factor = deteccion.factor
    if factor != 1.0:
        # `origin=(0, 0)` y no el centro: esto es un cambio de unidad, no un
        # zoom. Con el origen por defecto las áreas saldrían bien y todo el
        # plano quedaría desplazado.
        rooms = [
            Room(
                label=room.label,
                polygon=escalar_geometria(room.polygon, xfact=factor, yfact=factor, origin=(0, 0)),
                layer=room.layer,
            )
            for room in rooms
        ]
        unit_labels = [(texto, x * factor, y * factor) for texto, x, y in unit_labels]
        poligonos_cons_cer = [
            escalar_geometria(p, xfact=factor, yfact=factor, origin=(0, 0)) for p in poligonos_cons_cer
        ]
        poligonos_util_ext = [
            escalar_geometria(p, xfact=factor, yfact=factor, origin=(0, 0)) for p in poligonos_util_ext
        ]
        poligonos_cons_ext = [
            escalar_geometria(p, xfact=factor, yfact=factor, origin=(0, 0)) for p in poligonos_cons_ext
        ]

    return PlanoLeido(
        rooms=rooms, unit_labels=unit_labels, escala=deteccion, layer=nombre_capa, capa=capa,
        envolventes_cerradas=poligonos_cons_cer,
        superficies_utiles_exteriores=poligonos_util_ext,
        envolventes_exteriores=poligonos_cons_ext,
        geometria_no_leida=geometria_no_leida)


def build_rooms(dxf_path: str, layer: Optional[str] = None) -> List[Room]:
    """Pipeline completo: lee el DXF y devuelve las habitaciones ya en metros."""
    return leer_plano(load_document(dxf_path), layer).rooms


# ---------------------------------------------------------------------------
# Capas candidatas (tarea 5 del PRD de ingesta de DXF ajenos)
#
# `AREA_LAYER` es el nombre que usa un único estudio. Cualquier otro DXF llama
# a su capa de áreas `SUPERFICIES`, `A-AREA-IDEN`, `00_AREAS` o lo que sea, y
# hoy eso significa cero habitaciones sin ninguna explicación. Estas funciones
# no adivinan el nombre: miden qué contiene cada capa y ordenan las que se
# parecen a habitaciones, para poder preguntar con fundamento.
# ---------------------------------------------------------------------------

# Por debajo de esto una capa no se considera candidata: tres polígonos no son
# una planta, y la mediana de dos números no significa nada.
MINIMO_POLIGONOS_CAPA = 3

# Tope de polígonos que se examinan por capa al medir cuántos llevan rótulo
# dentro. Es un muestreo: comprobar 5.000 polígonos contra 3.000 textos serían
# 15 millones de pruebas de contención para afinar un decimal de una
# heurística. Con 150 la proporción ya es estable.
_MUESTRA_MAXIMA = 150

# Fragmentos de nombre habituales en la capa de áreas. Valen como desempate y
# nada más — pesan 0,05 sobre 1: si el nombre decidiera, estaríamos otra vez
# donde estábamos.
_PISTAS_DE_NOMBRE = ("area", "área", "superficie", "estancia", "recinto", "room", "sup", "local")


@dataclass
class CapaCandidata:
    """Una capa del DXF y cuánto se parece a la capa de habitaciones."""

    nombre: str
    n_poligonos: int
    area_mediana: float
    proporcion_rotulada: float
    escalas_compatibles: List[str] = field(default_factory=list)
    puntuacion: float = 0.0
    motivo: str = ""


def _mediana(valores: List[float]) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    n = len(ordenados)
    if n % 2:
        return ordenados[n // 2]
    return (ordenados[n // 2 - 1] + ordenados[n // 2]) / 2.0


def _poligonos_cerrados_por_capa(doc: Drawing) -> dict:
    """Todas las polilíneas cerradas del plano —bloques incluidos—, agrupadas
    por capa.

    Al revés que `_closed_polygons_with_color`, que filtra por un nombre de
    capa concreto: aquí el nombre es justo lo que no se sabe.

    `recuperar_geometria=False`: este heurístico no participa de la
    recuperación de cierre por geometría (`_esta_cerrada`) a propósito. Esta
    corrección es sobre qué habitaciones se leen de la capa ya elegida, no
    sobre qué capa se elige -- cambiar también aquí alteraría qué capa parece
    ganadora en algún DXF, y eso es una decisión aparte que nadie ha pedido.
    """
    por_capa: dict = {}
    for entity, capa in _recorrer_plano(doc):
        if not _esta_cerrada(entity, recuperar_geometria=False):
            continue
        puntos = _polyline_points(entity)
        if len(puntos) < 3:
            continue
        por_capa.setdefault(capa, []).append(Polygon(puntos))
    return por_capa


def _proporcion_rotulada(polygons: List[Polygon], labels: List[Tuple[str, float, float]]) -> float:
    """Fracción de polígonos que contienen dentro el punto de inserción de
    algún texto.

    Es la señal que mejor separa una capa de habitaciones de una de mobiliario:
    una habitación lleva su nombre y su superficie escritos dentro; una silla,
    una puerta o una sombra de hueco, no. Pesa más que ninguna otra por eso.
    """
    if not polygons or not labels:
        return 0.0

    muestra = polygons[:_MUESTRA_MAXIMA]
    rotulados = 0
    for polygon in muestra:
        minx, miny, maxx, maxy = polygon.bounds
        for _texto, x, y in labels:
            # Prefiltro por caja: descarta la inmensa mayoría sin construir un
            # Point ni llamar a `contains`.
            if minx <= x <= maxx and miny <= y <= maxy and polygon.contains(Point(x, y)):
                rotulados += 1
                break
    return rotulados / float(len(muestra))


def capas_candidatas(doc: Drawing) -> List[CapaCandidata]:
    """Capas que podrían contener las habitaciones, de más a menos probable.

    La puntuación combina cuatro señales, y su reparto es deliberadamente
    explicable en vez de afinado — se está calibrando contra **un solo DXF
    real**, así que cualquier precisión mayor sería inventada. `motivo` explica
    cada resultado en una frase para que se pueda discutir sin leer el código.
    Los pesos deben revisarse cuando la tarea 2 del PRD aporte archivos ajenos:

    - 0,45 que los polígonos lleven rótulo dentro (lo que separa habitaciones
      de mobiliario),
    - 0,35 que su tamaño sea el de una estancia bajo alguna unidad métrica
      (lo que descarta puertas, sombras de hueco y despieces),
    - 0,15 el volumen relativo frente a la capa más poblada,
    - 0,05 una pista en el nombre, como desempate y nada más.
    """
    por_capa = _poligonos_cerrados_por_capa(doc)
    if not por_capa:
        return []

    labels = extract_labels(doc)
    maximo = max(len(p) for p in por_capa.values())

    candidatas: List[CapaCandidata] = []
    for nombre, polygons in por_capa.items():
        if len(polygons) < MINIMO_POLIGONOS_CAPA:
            continue

        areas = [p.area for p in polygons if p.area > 0]
        area_mediana = _mediana(areas)
        escalas = escala_mod.unidades_plausibles(areas)
        rotulada = _proporcion_rotulada(polygons, labels)
        pista = any(p in nombre.lower() for p in _PISTAS_DE_NOMBRE)

        puntuacion = (
            0.45 * rotulada
            + 0.35 * (1.0 if escalas else 0.0)
            + 0.15 * (len(polygons) / float(maximo))
            + 0.05 * (1.0 if pista else 0.0)
        )

        razones = ["%d polígonos" % len(polygons)]
        razones.append(
            "%d%% con rótulo dentro" % round(rotulada * 100)
            if rotulada else "ninguno lleva rótulo dentro"
        )
        razones.append(
            "tamaño de estancia en %s" % escalas[0] if escalas
            else "tamaño incompatible con una estancia"
        )
        if pista:
            razones.append("el nombre sugiere áreas")

        candidatas.append(CapaCandidata(
            nombre=nombre,
            n_poligonos=len(polygons),
            area_mediana=area_mediana,
            proporcion_rotulada=rotulada,
            escalas_compatibles=escalas,
            puntuacion=round(puntuacion, 4),
            motivo="; ".join(razones),
        ))

    # A igualdad de puntuación gana la más poblada, y después el nombre, para
    # que el orden sea estable entre ejecuciones y no dependa del DXF.
    candidatas.sort(key=lambda c: (-c.puntuacion, -c.n_poligonos, c.nombre))
    return candidatas


# Una candidata por debajo de esto no se parece lo bastante a una planta como
# para proponerla sola, aunque sea la mejor de un archivo malo.
UMBRAL_CAPA_ACEPTABLE = 0.5

# Y aunque supere el umbral, tiene que despegarse de la segunda: dos capas
# parecidas casi siempre son plantas distintas, o áreas contra un duplicado, y
# elegir por su cuenta sería adivinar.
VENTAJA_MINIMA = 1.5


def _buscar_capa(candidatas: List[CapaCandidata], nombre: str) -> Optional[CapaCandidata]:
    """Candidata con ese nombre, sin distinguir mayúsculas: «00 Areas» y
    «00 areas» son la misma capa para un arquitecto, aunque no para el filtro
    de consulta de ezdxf."""
    exacta = next((c for c in candidatas if c.nombre == nombre), None)
    if exacta is not None:
        return exacta
    objetivo = nombre.strip().lower()
    return next((c for c in candidatas if c.nombre.strip().lower() == objetivo), None)


def _decidir_capa(candidatas: List[CapaCandidata]) -> Optional[CapaCandidata]:
    """La ganadora, si la hay, sobre una lista ya calculada."""
    if not candidatas:
        return None
    mejor = candidatas[0]
    if mejor.puntuacion < UMBRAL_CAPA_ACEPTABLE:
        return None
    if len(candidatas) > 1 and candidatas[1].puntuacion > 0:
        if mejor.puntuacion < candidatas[1].puntuacion * VENTAJA_MINIMA:
            return None
    return mejor


def elegir_capa(doc: Drawing, preferida: Optional[str] = None):
    """Decide qué capa contiene las habitaciones, o admite que no lo sabe.

    Devuelve `(elegida, candidatas)`. `elegida` es `None` cuando hay que
    preguntar al arquitecto, y entonces `candidatas` es la lista ordenada que
    hay que enseñarle. Mismo criterio que `analyzer/escala.py`: se prefiere una
    pregunta a una suposición.

    `preferida` corta el proceso: es la respuesta del arquitecto.
    """
    candidatas = capas_candidatas(doc)
    if preferida:
        return _buscar_capa(candidatas, preferida), candidatas
    return _decidir_capa(candidatas), candidatas


def _resolver_capa(doc: Drawing, pedida: Optional[str]) -> CapaCandidata:
    """La capa con la que leer el plano, o `CapaIndeterminada` si hay que
    preguntar. Calcula las candidatas una sola vez.

    Cuando nadie ha elegido, `AREA_LAYER` tiene preferencia si existe y llega
    al umbral. No es porque su nombre sea especial —lo tiene que ganar como
    cualquier otra—, sino porque un nombre que el arquitecto ya usa es una
    respuesta suya anterior, y respetarla evita cambiarle el resultado por una
    heurística nueva.
    """
    candidatas = capas_candidatas(doc)

    if pedida:
        elegida = _buscar_capa(candidatas, pedida)
        if elegida is None:
            raise CapaIndeterminada(candidatas, pedida=pedida)
        return elegida

    por_defecto = _buscar_capa(candidatas, AREA_LAYER)
    if por_defecto is not None and por_defecto.puntuacion >= UMBRAL_CAPA_ACEPTABLE:
        return por_defecto

    elegida = _decidir_capa(candidatas)
    if elegida is None:
        raise CapaIndeterminada(candidatas)
    return elegida
