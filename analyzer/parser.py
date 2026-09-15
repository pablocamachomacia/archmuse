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
from typing import Dict, List, Optional, Tuple

import ezdxf
from ezdxf.document import Drawing
from shapely import STRtree
from shapely.affinity import scale as escalar_geometria
from shapely.affinity import translate as trasladar_geometria
from shapely.geometry import Point, Polygon
from shapely.validation import explain_validity, make_valid

from . import escala as escala_mod
from .texto_dxf import decodificar_escapes

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


@dataclass(frozen=True)
class GeometriaReparada:
    """Un recinto que estaba mal construido y ha entrado **reparado**, sin que
    su superficie cambie ni un centímetro cuadrado.

    Es el reverso de `EntidadDescartada`: aquélla dice qué no ha entrado; ésta,
    qué ha entrado de otra forma que como estaba dibujado. Las dos existen por
    lo mismo — que nada pase en silencio (`C-6`) — y ninguna de las dos es
    opcional: una reparación callada es peor que un descarte callado, porque el
    número sale bien y nadie va a ir a mirar por qué.

    `area` está en unidades de dibujo, sin escalar, igual que el resto de este
    nivel del parser.
    """

    capa: str
    tipo: str
    handle: Optional[str] = None
    area: float = 0.0
    #: `explain_validity()` del polígono original: dice qué estaba mal y dónde.
    detalle: str = ""


@dataclass(frozen=True)
class CapaIgnorada:
    """Una capa del plano que no es ninguna de las capas de recintos que se
    han mirado, con cuántas entidades tiene.

    Distinta de `EntidadDescartada`: aquélla es una entidad DENTRO de la capa
    elegida que no se ha podido leer (tipo no soportado, geometría inválida).
    Ésta es una capa ENTERA que ni siquiera se ha mirado -- mobiliario, cotas,
    ejes, cajetín... Un descarte silencioso es superficie que falta sin que
    nadie lo sepa, y eso vale igual para una entidad suelta que para una capa
    entera que el informe nunca menciona.
    """

    capa: str
    entidades: int
    motivo: str = "no es ninguna de las capas de recintos que se han mirado"


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
    # Capas enteras del plano que no son ninguna de las capas de recintos
    # miradas -- mobiliario, cotas, ejes, cajetín... Ver `CapaIgnorada`.
    capas_ignoradas: List[CapaIgnorada] = field(default_factory=list)
    # True cuando `layer` se ha elegido por parecido entre varias candidatas
    # (`capas_candidatas`/`_decidir_capa`) y no porque el arquitecto la haya
    # confirmado ni porque coincida con `AREA_LAYER` por sí sola. Es la
    # frontera entre un hecho declarado y una inferencia -- y una inferencia
    # declara su hipótesis, no se presenta como si fuera un hecho.
    capa_elegida_por_heuristico: bool = False
    # Una traslacion rigida que meteria los rotulos dentro de los recintos,
    # cuando el plano sale entero sin rotular y hay una que lo explica. `None`
    # en un plano normal. **Es un diagnostico, no una correccion**: nadie la
    # aplica, y `leer_plano` devuelve los recintos tal y como estan dibujados.
    # Ver `detectar_desplazamiento_de_rotulos`.
    rotulos_desplazados: Optional["DesplazamientoDeRotulos"] = None
    # Recintos que estaban mal construidos y han entrado reparados, sin que su
    # superficie cambie (`C-10`). Hermano de `geometria_no_leida`: aquella dice
    # que no entro; esta, que entro de otra forma. Ninguna de las dos puede
    # quedar en silencio.
    geometria_reparada: List[GeometriaReparada] = field(default_factory=list)
    # La corrección que SE HA APLICADO a los rótulos en esta lectura, si alguna.
    # `None` es lo normal: no se alinea nada salvo que el arquitecto lo pida
    # **y** el desfase sea limpio. Cuando no es `None`, la medición depende de
    # ella y tiene que constar en el acta — condición de la firma de Pablo, y la
    # diferencia entre una corrección y una manipulación.
    rotulos_alineados: Optional["DesplazamientoDeRotulos"] = None
    # De que capa salen los nombres de las estancias de este plano, y con que
    # reparto. `capa=None` + `ambiguo=True` significa que hay dos candidatas
    # parejas y NO se ha elegido: se declara y se deja todo como estaba.
    reparto_de_rotulos: "RepartoDeRotulos" = field(default_factory=lambda: RepartoDeRotulos())


def load_document(dxf_path: str) -> Drawing:
    """Abre un archivo DXF y devuelve el documento de ezdxf."""
    try:
        return ezdxf.readfile(dxf_path)
    except IOError as exc:
        raise FileNotFoundError(f"No se pudo abrir el archivo DXF: {dxf_path}") from exc
    except ezdxf.DXFStructureError as exc:
        raise ValueError(f"El archivo DXF está dañado o no es válido: {dxf_path}") from exc


#: Las últimas lecturas: `(sha256 del fichero, capa, factor, alinear) -> (doc, plano)`.
_LECTURAS: "Dict[tuple, Tuple[Drawing, PlanoLeido]]" = {}
_LECTURAS_MAXIMAS = 2


def leer_fichero(ruta: str, layer: Optional[str] = None, factor_escala: Optional[float] = None,
                 alinear_rotulos: bool = False) -> "Tuple[Drawing, PlanoLeido]":
    """`ezdxf.readfile` + `leer_plano`, **reutilizando la lectura del mismo
    contenido con los mismos parámetros**.

    **Por qué (medido el 2026-09-15).** Una petición del comando lee el mismo DXF
    tres veces: la medición, el PDF de la medición y la tabla. Con un plano de 674
    recintos y 6.279 textos eran 5,2 s de `readfile` y 4,4 de `leer_plano`, para
    obtener tres veces lo mismo. La clave es el contenido del fichero, no su ruta:
    cada paso escribe el suyo en su propio temporal.

    Nadie modifica lo que devuelve (buscado el 2026-09-15: ningún código de
    producción asigna ni añade a `plano.rooms` o `plano.unit_labels`). Un error de
    lectura no se guarda: cada llamada lo vuelve a lanzar."""
    import hashlib

    with open(ruta, "rb") as fichero:
        huella = hashlib.sha256(fichero.read()).hexdigest()
    clave = (huella, layer, factor_escala, bool(alinear_rotulos))
    with _CERROJO_DE_LECTURAS:
        if clave in _LECTURAS:
            return _LECTURAS[clave]
    doc = ezdxf.readfile(ruta)
    resultado = (doc, leer_plano(doc, layer=layer, factor_escala=factor_escala,
                                 alinear_rotulos=alinear_rotulos))
    # El servidor atiende en hilos (`waitress`): el diccionario no se toca sin cerrojo.
    with _CERROJO_DE_LECTURAS:
        while len(_LECTURAS) >= _LECTURAS_MAXIMAS:
            _LECTURAS.pop(next(iter(_LECTURAS)))
        _LECTURAS[clave] = resultado
    return resultado


import threading as _threading  # noqa: E402

_CERROJO_DE_LECTURAS = _threading.Lock()


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


# ---------------------------------------------------------------------------
# C-10 · REPARAR LA GEOMETRÍA INVÁLIDA, Y DECLARARLO SIEMPRE
#
# Firmado por Pablo el 2026-09-11.
# PRD: `docs/prd/2026-09-11-reparar-geometria-invalida-c10.md`.
#
# **El problema.** `plantasimple.dxf` tiene 10 polilíneas auto-intersecantes de
# 206, y `evaluator.evaluate_room_overlap` revienta al intersecarlas: el plano
# entero devolvía HTTP 200 con CERO piezas y una `GEOSException` por toda
# explicación. El modo heredado NO validaba `is_valid` a propósito —«para no
# excluir de golpe geometría que hoy SÍ se acepta»—, con lo que la geometría no
# se excluía: entraba rota y tumbaba la medición cuarenta funciones más abajo.
#
# **Por qué se repara en vez de descartar, y por qué eso no es decidir por el
# arquitecto.** Medido en los diez casos: `make_valid` devuelve **exactamente la
# misma superficie**, hasta el sexto decimal. Son auto-intersecciones
# degeneradas —picos de área cero, vértices repetidos—, no lazos. Descartarlas
# costaría el 5,8% de la superficie de un plano real; repararlas no cambia
# ninguna cifra. **Cuando sí la cambia, no se repara**: una pajarita de verdad
# tiene un área ambigua, y ahí ArchMuse no elige.
#
#     Los 10 de plantasimple .... delta de área  0,000000 m²  -> se reparan
#     La pajarita de los tests .. delta de área  8,000000 m²  -> se descarta
#
# La tolerancia separa las dos cosas sola, sin que nadie tenga que clasificarlas
# a mano. Ésa es la única razón por la que este criterio es implementable.
#
# **Un solo criterio para los dos caminos.** Antes el modo `AM_*` descartaba
# toda geometría inválida y el heredado la dejaba pasar: dos criterios para el
# mismo defecto. Ahora los dos llaman aquí. Unificar no relaja el de `AM_*` —la
# pajarita de sus tests se sigue descartando, con la misma cifra— sino que lo
# **explica**: descartaba todo porque no sabía distinguir; ahora distingue.
# ---------------------------------------------------------------------------

#: Cuánto puede moverse la superficie para que la reparación siga siendo una
#: reparación y no una decisión. Medio centímetro cuadrado. No está ajustado
#: para que pasen los casos reales: ésos dan cero exacto, así que sobra por seis
#: órdenes de magnitud. Está puesto donde deja de ser ruido de coma flotante.
TOLERANCIA_REPARACION = 0.005

#: Detalle que acompaña al descarte cuando la reparación se ha intentado y no
#: vale. Viajan dentro de `EntidadDescartada.detalle`, junto a
#: `MOTIVO_GEOMETRIA_INVALIDA`, en vez de como motivos nuevos: el vocabulario de
#: motivos lo consumen `validacion_capas.py` y el PDF, y ampliarlo obliga a
#: tocar los dos para decir algo que es un matiz del mismo motivo.
DETALLE_REPARACION_CAMBIA_EL_AREA = (
    "se ha intentado reparar y la superficie cambiaba de %.4f a %.4f: no es un "
    "defecto de dibujo, es una figura ambigua, y ArchMuse no elige por ti")
DETALLE_REPARACION_PARTE_EL_RECINTO = (
    "se ha intentado reparar y el recinto se partía en %d piezas: cuál de ellas "
    "es la habitación no lo puede decidir ArchMuse")
DETALLE_REPARACION_SIN_SUPERFICIE = (
    "se ha intentado reparar y no queda ninguna superficie, sólo líneas")


def _partes_poligonales(geometria) -> List[Polygon]:
    """Sólo lo que tiene superficie. `make_valid` devuelve a menudo una
    `GeometryCollection` con el polígono bueno y, al lado, las líneas del pico
    degenerado que acaba de deshacer; esas líneas no son un recinto."""
    if isinstance(geometria, Polygon):
        return [] if geometria.is_empty else [geometria]
    if hasattr(geometria, "geoms"):
        partes: List[Polygon] = []
        for sub in geometria.geoms:
            partes.extend(_partes_poligonales(sub))
        return partes
    return []


def reparar_poligono(polygon: Polygon) -> Tuple[Optional[Polygon], str]:
    """El mismo recinto, válido — o `(None, motivo)` si repararlo sería decidir.

    Devuelve `(poligono, "")` cuando la reparación es segura, y
    `(None, detalle)` cuando no lo es, con el detalle ya redactado para que
    viaje al inventario de descartes.

    **No se llama sobre polígonos válidos**: quien llama comprueba `is_valid`
    antes, para que el camino normal no pague nada.
    """
    try:
        reparado = make_valid(polygon)
    except Exception as exc:  # noqa: BLE001 - GEOS puede fallar de muchas formas
        return None, "make_valid ha fallado: %s" % exc

    partes = _partes_poligonales(reparado)

    # Las astillas de área cero son el residuo del pico que se acaba de
    # deshacer, no piezas del recinto. Medido: la mayor de todo el corpus real
    # es de 0,000000196 m², cuatro órdenes de magnitud por debajo del umbral.
    con_superficie = [p for p in partes if p.area > TOLERANCIA_REPARACION]

    if not con_superficie:
        return None, DETALLE_REPARACION_SIN_SUPERFICIE
    if len(con_superficie) > 1:
        return None, DETALLE_REPARACION_PARTE_EL_RECINTO % len(con_superficie)

    unico = con_superficie[0]
    if abs(unico.area - polygon.area) > TOLERANCIA_REPARACION:
        return None, DETALLE_REPARACION_CAMBIA_EL_AREA % (polygon.area, unico.area)
    return unico, ""


def _validar_o_reparar(polygon, capa, tipo, handle, descartes, reparaciones):
    """El polígono que entra en el resultado, o `None`.

    **El único sitio donde se decide qué hacer con una geometría inválida**, y
    lo usan los dos caminos (heredado y `AM_*`) para que no vuelvan a divergir.
    Rellena el inventario que corresponda: `reparaciones` si ha entrado
    reparado, `descartes` si no ha entrado. Nunca los dos, nunca ninguno.
    """
    if polygon.is_valid:
        return polygon

    detalle_original = explain_validity(polygon)
    reparado, motivo = reparar_poligono(polygon)
    if reparado is None:
        if descartes is not None:
            descartes.append(EntidadDescartada(
                motivo=MOTIVO_GEOMETRIA_INVALIDA, capa=capa, tipo=tipo,
                handle=handle, detalle="%s; %s" % (detalle_original, motivo)))
        return None

    if reparaciones is not None:
        reparaciones.append(GeometriaReparada(
            capa=capa, tipo=tipo, handle=handle, area=reparado.area,
            detalle=detalle_original))
    return reparado


def _closed_polygons_with_color(
    doc: Drawing, layer: str, descartes: Optional[List[EntidadDescartada]] = None,
    reparaciones: Optional[List[GeometriaReparada]] = None,
) -> List[Tuple[Polygon, int]]:
    """Polilíneas cerradas del layer indicado como (polígono, color DXF),
    bloques incluidos.

    `descartes`, si se pasa una lista, se rellena con el inventario de
    entidades de esta capa que NO han entrado en el resultado (tipo no
    soportado, o polilínea que sigue abierta incluso con la recuperación
    geométrica de `_esta_cerrada`). Es aditivo y opcional a propósito: por
    defecto (`descartes=None`) el resultado y el comportamiento son
    idénticos a antes de que existiera este parámetro.

    **CAMBIO DEL 2026-09-11 (`C-10`).** Hasta hoy este camino NO validaba
    `is_valid` «para no excluir de golpe geometría que hoy SÍ se acepta como
    `Room`». La intención era buena y el efecto el contrario: la geometría no se
    excluía, entraba rota y tumbaba la medición entera con una `GEOSException`
    en `evaluate_room_overlap` — `plantasimple.dxf` devolvía cero piezas por 10
    polilíneas de 206. Ahora pasa por `_validar_o_reparar`, **el mismo criterio
    que el camino `AM_*`**, que repara lo que se puede reparar sin cambiar la
    superficie y descarta lo demás. Ninguno de los cinco planos de referencia
    cambia ni un m² (medido pieza a pieza antes de escribir esto).

    `reparaciones`, si se pasa una lista, recoge lo que ha entrado reparado.
    Aditivo y opcional igual que `descartes`, y por el mismo motivo.
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
        if len(points) < 3:
            if descartes is not None:
                descartes.append(EntidadDescartada(
                    motivo=MOTIVO_MENOS_DE_3_VERTICES, capa=capa, tipo=tipo,
                    handle=_handle_de(entity)))
            continue
        polygon = _validar_o_reparar(
            Polygon(points), capa, tipo, _handle_de(entity), descartes, reparaciones)
        if polygon is not None:
            entries.append((polygon, entity.dxf.color))
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
    - su color DXF explícito NO es BYLAYER (una habitación se dibuja con el
      color de su capa; un contorno agrupador se dibuja aparte, con un color
      propio, típicamente ACI 10 o ACI 150),
    - contiene geométricamente a otro polígono más pequeño del mismo layer (la
      intersección cubre >= `threshold` del área de ese polígono menor), y
    - ese polígono contenido tiene la MISMA etiqueta que el propio contenedor
      (misma habitación, ya representada de forma independiente).

    Si el contorno contiene otras habitaciones de tipo distinto (p. ej. un
    dormitorio o un baño dentro del mismo perímetro del salón) pero NINGUNA
    con su propia etiqueta, se conserva: es la única representación de esa
    habitación en el plano, y descartarlo dejaría a la vivienda sin esa
    superficie habitable.

    **Corregido el 2026-09-10: el polígono contenido ya no tiene que estar en
    BYLAYER.** Había una cuarta condición que lo exigía, apoyada en una
    suposición que este mismo docstring daba por buena —«las habitaciones
    reales de estos planos siempre usan el color del layer»— y que es falsa:
    en `v1plantas.dxf` el estudio dibuja sus piezas exteriores en verde (ACI 3)
    y el contorno que las agrupa en 150, así que el contorno de 8,63 m² se
    colaba como una habitación más y sus 7,08 m² se contaban dos veces, dejando
    a la vivienda entera sin publicar ninguna superficie. De qué color esté
    dibujado lo de dentro no dice nada sobre si lo de fuera es un contorno: eso
    lo dicen las otras tres condiciones. Ver `tests/test_contorno_agrupador.py`.
    """
    kept: List[Polygon] = []
    for i, (polygon, color, label) in enumerate(entries):
        own_label = _normalize_room_label(label)
        is_duplicate = color != BYLAYER_COLOR and own_label != "" and any(
            j != i
            and _normalize_room_label(other_label) == own_label
            and polygon.area > other.area
            and polygon.intersection(other).area >= threshold * other.area
            for j, (other, other_color, other_label) in enumerate(entries)
        )
        if not is_duplicate:
            kept.append(polygon)
    return kept


def extract_room_polygons(
    doc: Drawing, layer: str = AREA_LAYER, descartes: Optional[List[EntidadDescartada]] = None,
    reparaciones: Optional[List[GeometriaReparada]] = None,
    desplazamiento: Optional[Tuple[float, float]] = None,
) -> List[Polygon]:
    """Busca polilíneas cerradas en el layer indicado, las convierte en
    polígonos shapely y descarta los contornos agrupadores duplicados
    (ver `_discard_container_candidates`). `descartes` y `reparaciones`: ver
    `_closed_polygons_with_color`."""
    entries = _closed_polygons_with_color(
        doc, layer, descartes=descartes, reparaciones=reparaciones)
    labels = extract_labels(doc, con_capa=True, desplazamiento=desplazamiento)
    capas_validas, _reparto = _capas_que_nombran([p for p, _c in entries], labels, layer)
    labeled_entries = [
        (polygon, color, match_label_to_room(polygon, labels, capas_validas=capas_validas))
        for polygon, color in entries
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
    """Contenido legible de un MTEXT o un TEXT, sin códigos de formato.

    `plain_text()` quita el formato pero **no decodifica los escapes Unicode**
    (`ba\\U+00F1o`), y sin decodificarlos el rótulo no casa con ningún patrón de
    familia: es lo que hacía que el baño de un plano con eñes no se midiera. Ver
    `analyzer/texto_dxf.py` y `tests/test_escapes_unicode.py`.
    """
    try:
        return decodificar_escapes(entity.plain_text()).strip()
    except Exception:  # noqa: BLE001
        try:
            return decodificar_escapes(str(entity.dxf.text)).strip()
        except Exception:  # noqa: BLE001
            return ""


def extract_labels(doc: Drawing, con_capa: bool = False,
                   desplazamiento: Optional[Tuple[float, float]] = None) -> List[Tuple]:
    """Rótulos del plano como (texto, x, y) — o (texto, x, y, capa) si
    `con_capa=True` —, **con los MTEXT antes que los TEXT**.

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

    `con_capa`: `match_label_to_room` necesita saber en qué capa vive cada
    texto para no adjudicar a un recinto el texto de una cota o de un cajetín
    que sencillamente cae cerca. El resto de llamadas (`extract_unit_labels`,
    el heurístico de `capas_candidatas`) no lo necesitan, así que la forma de
    3 elementos se mantiene por defecto para no romper a nadie que ya
    desestructura `(texto, x, y)`.

    `desplazamiento`: `(dx, dy)` que se suma al punto de inserción de cada
    rótulo, **en memoria y sólo para esta lectura**. Es la única forma que tiene
    ArchMuse de alinear los rótulos de un plano que los lleva movidos en bloque
    (`docs/prd/2026-09-11-alinear-rotulos-desplazados.md`), y el sitio donde
    está puesto no es casual: aquí se leen coordenadas, no se escriben. **El DXF
    no se toca nunca**, ni el del disco ni el materializado; lo que cambia es la
    tupla que sale de esta función, que muere al acabar la medición.
    """
    from .propio import es_capa_de_archmuse

    por_tipo = {"MTEXT": [], "TEXT": []}
    dx, dy = desplazamiento if desplazamiento else (0.0, 0.0)

    for entity, capa in _recorrer_plano(doc):
        tipo = entity.dxftype()
        if tipo not in por_tipo:
            continue
        # **Lo que dibujó ArchMuse no rotula nada** (2026-09-15). Su cuadro, sus
        # notas y su marca van en sus capas. Leídos como rótulos, la casilla
        # «VT1/3» de su tabla era una segunda vivienda con ese nombre y la segunda
        # pasada no escribía ninguna cifra (`C-13`). Ver `analyzer/propio.py`.
        if es_capa_de_archmuse(capa):
            continue
        text = _texto_de(entity)
        if not text:
            continue
        punto = _punto_de_texto(entity)
        if punto is None:
            continue
        x, y = punto[0] + dx, punto[1] + dy
        fila = (text, x, y, capa) if con_capa else (text, x, y)
        por_tipo[tipo].append(fila)

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


class _IndiceDeRotulos:
    """Los rótulos con su punto ya creado y un índice espacial (2026-09-15).

    **Por qué existe.** Sobre un plano maestro real —677 recintos, 6.280 textos—
    el servidor tardaba 413 s (medido con el envío real del `.lsp`): casar cada
    recinto con cada rótulo creaba 28 millones de `Point` de shapely y probaba
    `contains` y `distance` contra todos. Aquí los puntos se crean una vez y un
    `STRtree` devuelve sólo los que pueden importar.

    **No cambia ningún resultado**, y es a propósito: los índices se devuelven en
    el orden de la lista —de ese orden sale la regla «un MTEXT gana a un TEXT»— y
    los empates de distancia se resuelven por ese mismo orden, como antes.
    """

    def __init__(self, labels):
        import numpy as np
        import shapely

        self.labels = labels
        self.n = len(labels)
        self.primero = labels[0] if labels else None
        self.ultimo = labels[-1] if labels else None
        self.capas = [etiqueta[3] if len(etiqueta) > 3 else None for etiqueta in labels]
        self.solo_numero = [_es_solo_numero(etiqueta[0]) for etiqueta in labels]
        self._np = np
        self.puntos = shapely.points([(etiqueta[1], etiqueta[2]) for etiqueta in labels]) \
            if labels else np.empty(0, dtype=object)
        self.arbol = shapely.STRtree(self.puntos)

    def sirve_para(self, labels) -> bool:
        return (self.labels is labels and len(labels) == self.n
                and (not labels or (labels[0] is self.primero and labels[-1] is self.ultimo)))

    def dentro(self, polygon: Polygon):
        """Índices, en orden, de los rótulos cuyo punto cae DENTRO del polígono."""
        if not self.n:
            return []
        return self._np.sort(self.arbol.query(polygon, predicate="contains")).tolist()

    def a_menos_de(self, polygon: Polygon, distancia: float):
        """Índices, en orden, de los rótulos a `distancia` o menos del polígono."""
        if not self.n:
            return []
        return self._np.sort(self.arbol.query(polygon, predicate="dwithin",
                                              distance=distancia)).tolist()


_ULTIMO_INDICE: List[Optional[_IndiceDeRotulos]] = [None]


def _indice_de(labels) -> _IndiceDeRotulos:
    """El índice de `labels`, reutilizado mientras sea la misma lista: un plano
    llama a esto una vez por recinto con la misma lista de rótulos."""
    indice = _ULTIMO_INDICE[0]
    if indice is None or not indice.sirve_para(labels):
        indice = _IndiceDeRotulos(labels)
        _ULTIMO_INDICE[0] = indice
    return indice


def _capas_de_rotulo(polygons: List[Polygon], labels: List[Tuple[str, float, float, str]],
                     capa_recintos: str):
    """Capas de las que sí puede salir un nombre de estancia en ESTE plano:
    la propia capa de recintos, más cualquier otra capa que en algún punto
    del plano tenga un texto cuyo punto de inserción caiga dentro de un
    recinto.

    Esto -no "la misma capa que la geometría"- es lo que separa una capa de
    rótulos real de una de ruido. Más de un estudio dibuja las estancias en
    una capa y sus nombres en otra dedicada a texto (comprobado en el propio
    plano de referencia del proyecto: recintos en `00 areas`, nombres en
    `00 TEXTO`); exigir coincidencia exacta con la capa de recintos perdería
    todos los rótulos de un plano así. Una capa de cotas, en cambio, no pone
    nunca un texto dentro de un recinto -sus textos viven en la línea de
    cota, fuera de cualquier estancia- así que nunca entra aquí.
    """
    capas = {capa_recintos}
    if not polygons or not labels:
        return capas
    indice = _indice_de(labels)
    for polygon in polygons:
        for i in indice.dentro(polygon):
            capas.add(indice.capas[i])
    return capas


# ---------------------------------------------------------------------------
# QUÉ CAPA PUEDE DAR NOMBRE A UNA ESTANCIA (2026-09-11)
#
# PRD: `docs/prd/2026-09-11-que-capa-nombra-las-estancias.md`, firmado por Pablo.
#
# **El agujero que esto tapa.** `_capas_de_rotulo` (arriba) admite cualquier capa
# que ponga un texto dentro de un recinto. Eso separa bien una capa de nombres de
# una de cotas —los textos de cota viven en la línea de cota— pero **no separa
# una capa de nombres de una de anotaciones**, y las dos ponen textos dentro.
#
# Se vio al alinear los rótulos de `plantasimple.dxf`: 46 de 159 recintos se
# llamaban «F», «FR» o «LD», códigos de electrodoméstico de la capa `00-INST`.
# El salón de 21,90 m² se llamaba «F», de frigorífico.
#
# **Es deuda preexistente, no un fallo nuevo**, y conviene que quede escrito:
# mientras los rótulos de ese plano estuvieron 50 m por debajo de los recintos,
# ningún texto caía dentro de nada y la regla no se notaba. Que haya salido ahora
# es suerte, no diseño — el mismo tipo de regla («vale cualquiera que cumpla algo
# una vez») puede estar en más sitios de este fichero.
#
# **La regla: la capa que más nombra, gana.** Medible, y no inventa vocabulario
# — no mira el texto, sólo cuenta. Lo que NO hace, y es la mitad del criterio:
# elegir cuando las dos primeras van parejas. Ahí se declara el reparto y se
# deja todo como estaba, porque elegir sería adivinar y no nombrar nada rompería
# planos que hoy funcionan.
# ---------------------------------------------------------------------------

#: Cuánto puede nombrar la segunda capa, en proporción a la primera, antes de que
#: la respuesta deje de ser única: la primera tiene que nombrar **más del doble**.
#:
#: Medido sobre los seis planos disponibles: cinco tienen **una sola** capa que
#: nombra (ratio 0,000) y el umbral no los toca; el único con varias está en
#: **0,414** (111 contra 46). El caso que Pablo puso como «no holgado» —111
#: contra 95— daría 0,856.
#:
#: **No hay ni un plano medido en la zona 0,4-0,6**, así que esto es una
#: convención declarada y no un óptimo medido. Se elige aquí porque «más del
#: doble» es una frase que un arquitecto puede discutir. Revisar con los planos
#: que traiga la beta.
UMBRAL_CAPA_DE_ROTULOS = 0.5


@dataclass(frozen=True)
class RepartoDeRotulos:
    """De qué capa salen los nombres de las estancias de este plano.

    `capa` es `None` cuando no se ha podido elegir — ni un recinto nombrado, o
    dos capas parejas. `ambiguo` distingue las dos cosas: no es lo mismo «aquí
    no hay nada que elegir» que «hay dos candidatas y no elijo».
    """

    capa: Optional[str] = None
    #: `(capa, recintos que nombraría)`, de más a menos. Es lo que hace
    #: discutible la decisión en vez de opaca.
    recuento: Tuple[Tuple[str, int], ...] = ()
    ambiguo: bool = False

    @property
    def proporcion(self) -> float:
        """Cuánto nombra la segunda respecto de la primera. 0,0 si sólo hay una."""
        if len(self.recuento) < 2 or not self.recuento[0][1]:
            return 0.0
        return self.recuento[1][1] / float(self.recuento[0][1])


def elegir_capa_de_rotulos(
    polygons: List[Polygon], labels: List[Tuple[str, float, float, str]],
    capas_validas,
) -> RepartoDeRotulos:
    """Cuenta cuántos recintos nombraría cada capa y decide, o admite que no.

    Cuenta **un recinto por capa como mucho**: lo que se mide es «a cuántas
    estancias les pone nombre esta capa», no cuántos textos tiene dentro. Una
    capa con seis anotaciones en la misma estancia nombra una estancia, no seis.
    """
    if not polygons or not labels:
        return RepartoDeRotulos()

    por_capa: Dict[str, int] = {}
    indice = _indice_de(labels)
    for polygon in polygons:
        vistas = set()
        for i in indice.dentro(polygon):
            capa = indice.capas[i]
            if capa in vistas or capa not in capas_validas:
                continue
            vistas.add(capa)
            por_capa[capa] = por_capa.get(capa, 0) + 1
    if not por_capa:
        return RepartoDeRotulos()

    recuento = tuple(sorted(por_capa.items(), key=lambda par: (-par[1], par[0])))
    reparto = RepartoDeRotulos(recuento=recuento)
    if reparto.proporcion > UMBRAL_CAPA_DE_ROTULOS:
        return RepartoDeRotulos(recuento=recuento, ambiguo=True)
    return RepartoDeRotulos(capa=recuento[0][0], recuento=recuento)


def _capas_que_nombran(polygons, labels, capa_recintos):
    """`(capas admitidas, reparto)` — el filtro de verdad, ya estrechado.

    Es lo que hay que llamar en lugar de `_capas_de_rotulo` a secas: aquella
    dice de qué capas *podría* salir un nombre y ésta cuál lo da. Cuando el
    reparto es ambiguo NO se estrecha nada: se devuelve lo de siempre y el
    `reparto` lleva el aviso, porque elegir en el empate sería adivinar y no
    nombrar nada rompería planos que hoy funcionan.

    La capa de los recintos se admite siempre, gane o no: hay planos que rotulan
    sobre la propia geometría (`v1plantas.dxf`), y quitarla los dejaría mudos.
    """
    capas = _capas_de_rotulo(polygons, labels, capa_recintos)
    reparto = elegir_capa_de_rotulos(polygons, labels, capas)
    if reparto.capa is None:
        return capas, reparto
    return {capa_recintos, reparto.capa}, reparto

# Cuánto tiene que ganarle el candidato más cercano al segundo más cercano
# para no ser ambiguo. Mismo criterio y mismo valor que `VENTAJA_MINIMA` en
# `capas_candidatas`: dos candidatos casi empatados en distancia no se
# resuelven eligiendo el que está un poco más cerca -- eso es adivinar con
# pasos extra. Sin este margen, un rótulo real y una cota ambos "cerca" de
# una estancia pequeña ganan o pierden por centímetros según el redondeo del
# dibujo, no por ninguna razón que el arquitecto reconocería.
MARGEN_DESAMBIGUACION_ETIQUETA = 1.5

# Un texto que es solo una cifra -una cota, una superficie suelta escrita
# aparte- no es nombre de estancia, tenga o no coma/punto decimal.
# «SALON 12.00 m2» no cae aquí porque lleva letras; «7.00» y «3,20» sí.
_PATRON_SOLO_NUMERO = re.compile(r"^[+-]?\d+([.,]\d+)?\s*$")


def _es_solo_numero(texto: str) -> bool:
    return bool(_PATRON_SOLO_NUMERO.match(texto.strip()))


# Un TÍTULO DE CAMPO: el texto que dice **qué magnitud** se mide, no **qué
# estancia** es. Los planos de este estudio rotulan cada recinto con dos MTEXT
# independientes, uno encima del otro:
#
#     superficie util          <- el título de campo
#     Dormitorio 1             <- el nombre
#
# Los dos caen dentro del polígono, así que hasta el 2026-09-11 el rótulo de la
# estancia era **el primero que llegara**, y eso no es lo mismo en
# `doc.modelspace()` que en un `ssget` de AutoCAD: el mismo plano daba
# «Dormitorio 1» leído de un DXF y «superficie util» leído desde el comando.
#
# El patrón es deliberadamente corto y literal. No intenta reconocer «cualquier
# cosa que parezca un título»: reconoce las cuatro fórmulas con las que un
# arquitecto nombra una magnitud —superficie útil, superficie construida, y sus
# variantes—, que además nunca son el nombre de una habitación. Una estancia no
# se llama «superficie útil»; si en algún plano se llamara, se queda sin rótulo,
# que es honesto, y no hereda el nombre de una magnitud.
_PATRON_TITULO_DE_CAMPO = re.compile(
    r"^\s*(superficie|sup\.?|s\.)\s*(util|construida|utiles|construidas)\b",
    re.IGNORECASE,
)


def _es_titulo_de_campo(texto: str) -> bool:
    """`"superficie util exterior"` sí; `"Salón/cocina"` no.

    Se compara sobre el texto con los escapes ya decodificados: en un DXF real
    llega con la tilde escapada (la «ú» como una secuencia `U+00FA`), y
    `decodificar_escapes` la deja en «superficie útil` antes de comparar.
    """
    return bool(_PATRON_TITULO_DE_CAMPO.match(decodificar_escapes(texto or "")))


def match_label_to_room(
    polygon: Polygon,
    labels: List[Tuple[str, float, float, str]],
    capas_validas=None,
) -> Optional[str]:
    """Asocia el rótulo más adecuado a un polígono, o `None` si no hay ninguno
    que pueda serlo **con fundamento**. `labels` son cuádruplas
    `(texto, x, y, capa)` -- ver `extract_labels(doc, con_capa=True)`.

    Antes de buscar nada, se descartan dos clases de candidato que nunca son
    un rótulo de estancia, aunque caigan cerca o incluso dentro del polígono:

    1. **Texto de una capa sin ningún rótulo confirmado.** `capas_validas` es
       el conjunto de capas de las que sí puede salir un nombre de estancia
       en ESTE plano -- ver `_capas_de_rotulo` para cómo se calcula. **No es
       "la misma capa que la geometría del recinto"**: más de un estudio
       dibuja las estancias en una capa y sus nombres en otra dedicada a
       texto (`00 areas` / `00 TEXTO` es la convención real del propio
       plano de referencia del proyecto), y exigir coincidencia exacta
       perdería todos los rótulos de un plano así. Lo que sí se descarta es
       un texto de una capa que en TODO el plano nunca ha puesto un nombre
       dentro de un recinto -una cota, un cajetín, una marca de mobiliario-,
       porque no hay ninguna razón para que el nombre de una estancia esté
       ahí. Si `capas_validas` es `None` (llamador que no sabe o no le
       importa la capa), no se filtra -- mantiene el comportamiento anterior.
    2. **Texto que es solo una cifra.** Una cota como «7.00» tiene toda la
       pinta de una superficie cuando cae cerca de una estancia pequeña, pero
       no es un nombre.

    Y entre los que quedan dentro del polígono, **un nombre gana siempre a un
    título de campo** («superficie util», «superficie construida cerrada»), que
    dice qué magnitud se mide y no cómo se llama la estancia — ver
    `_es_titulo_de_campo`. Sin esa preferencia el resultado dependía del orden
    de llegada de los textos, y el mismo plano daba «Dormitorio 1» por una vía y
    «superficie util» por la otra.

    Sobre lo que queda, primero busca rótulos cuyo punto de inserción caiga
    dentro del polígono (caso habitual: el texto está dentro de la
    habitación). Como `extract_labels` devuelve los MTEXT antes que los TEXT,
    un MTEXT gana a un TEXT que esté dentro de la misma estancia.

    Si no hay ninguno dentro, se recurre al más cercano **pero solo si está
    lo bastante cerca** (`TOLERANCIA_ETIQUETA`) **y solo si no hay un segundo
    candidato casi tan cerca** (`MARGEN_DESAMBIGUACION_ETIQUETA`): elegir
    entre dos casi empatados en distancia sería tan adivinar como elegir el
    primero de la lista.

    Preferir `None` a un nombre ajeno no es una pérdida: una habitación sin
    nombre se evalúa por lo que se puede medir de ella y aparece en el
    informe como pieza sin rotular (`recinto_sin_etiqueta`), mientras que una
    habitación con el nombre equivocado se evalúa en silencio contra las
    reglas de otro tipo de estancia -un salón juzgado como dormitorio, o al
    revés- o, peor, hereda una cifra que no es la suya.
    """
    # Con el índice de `_IndiceDeRotulos` (2026-09-15): mismos candidatos, mismo
    # orden y mismos desempates que recorriendo la lista entera, sin probar cada
    # rótulo contra cada recinto.
    indice = _indice_de(labels)

    def es_candidato(i: int) -> bool:
        return ((capas_validas is None or indice.capas[i] in capas_validas)
                and not indice.solo_numero[i])

    inside = [labels[i][0] for i in indice.dentro(polygon) if es_candidato(i)]
    if inside:
        # **Un nombre gana siempre a un título de campo**, esté donde esté en la
        # lista. Devolver `inside[0]` hacía que el rótulo dependiera del orden en
        # que llegaran los textos, que no es el mismo leyendo el DXF que
        # recibiéndolo de un `ssget`: el mismo plano daba dos resultados
        # distintos según por dónde entrara (`tests/test_rotulo_con_titulo_de_campo.py`).
        nombres = [texto for texto in inside if not _es_titulo_de_campo(texto)]
        if nombres:
            return nombres[0]
        # Sólo títulos dentro: esta pieza **se queda sin nombre**. Es lo honesto
        # —el informe ya tiene sitio para un `recinto_sin_etiqueta`— y evita que
        # se mida una estancia llamada «superficie util», que es lo que rompía el
        # reparto del cuadro.
        return None

    if polygon.is_empty or polygon.area <= 0:
        return None

    limite = TOLERANCIA_ETIQUETA * math.sqrt(polygon.area)
    # Distancia al BORDE, no al centroide: lo que interesa es cuánto se aleja
    # el rótulo de la habitación, no cuánto mide la habitación.
    #
    # **Sólo los que están a `limite × MARGEN` o menos**: más lejos, un rótulo ni
    # gana (el primero tiene que estar a `limite` o menos) ni empata (el segundo
    # empata si está a menos de `primero × MARGEN`, que no pasa de
    # `limite × MARGEN`). El desempate por distancia igual sigue siendo el orden
    # de la lista, como con `sorted` sobre todos.
    distancias = sorted(
        ((polygon.distance(indice.puntos[i]), i)
         for i in indice.a_menos_de(polygon, limite * MARGEN_DESAMBIGUACION_ETIQUETA)
         if es_candidato(i)),
    )
    if not distancias:
        return None
    distancia, primero = distancias[0]
    texto = labels[primero][0]

    if distancia > limite:
        return None

    if len(distancias) > 1:
        segunda_distancia = distancias[1][0]
        if segunda_distancia < distancia * MARGEN_DESAMBIGUACION_ETIQUETA:
            return None

    return texto


def extract_unit_labels(
    doc: Drawing, desplazamiento: Optional[Tuple[float, float]] = None
) -> List[Tuple[str, float, float]]:
    """Etiquetas de vivienda del plano: rótulos con formato 'VT<n>/<m>'
    (ej. 'VT1/3'), que identifican las viviendas reales del proyecto — a
    diferencia de las etiquetas de nombre de habitación que devuelve
    `extract_labels`.

    Lee MTEXT y TEXT, igual que `extract_labels`: no hay ninguna razón para que
    la etiqueta de una vivienda tenga que estar dibujada como MTEXT.

    `desplazamiento`: ver `extract_labels`. **Tiene que recibir el mismo que los
    rótulos de estancia**, y por un motivo que no es simetría: las etiquetas de
    vivienda viven en la misma fila del dibujo que los nombres de habitación, así
    que un plano con los rótulos movidos las tiene movidas también. Alinear unos
    y no las otras dejaría cada pieza bien nombrada y en la vivienda equivocada,
    que es peor que no alinear nada.
    """
    return [etiqueta for etiqueta in extract_labels(doc, desplazamiento=desplazamiento)
            if UNIT_LABEL_PATTERN.match(etiqueta[0])]


# ---------------------------------------------------------------------------
# Rótulos desplazados en bloque (2026-09-11)
#
# **Qué es esto y por qué existe.** En `plantasimple.dxf` las 206 polilíneas de
# «00 areas» no reciben ni un rótulo: los textos del plano están **50,00
# unidades de dibujo por debajo**, dx = 0 exacto. Medido, no supuesto — al
# aplicar (0, +50) encajan **152 de 152**, y el barrido de dy enseña una meseta
# limpia de 49,50 a 50,25 con dx=0, que es la forma que tiene un `DESPLAZA`
# deliberado y no una deriva.
#
# **No es la convención del estudio: es de este plano.** Comprobado en los otros
# cuatro DXF del mismo arquitecto (`v1plantas`, `v2s`, `v3s`, `V5`) y en
# `ejemplo.dxf`: los seis rotulan al 100% sin desplazar nada.
#
# **Por eso esto DETECTA y NO CORRIGE.** Aplicar el desplazamiento solo sería
# exactamente la decisión implícita sin dueño que prohíbe el cierre de
# `CLAUDE.md` («cada vez que el código parece resolver una ambigüedad que nadie
# escribió...»), y mover los rótulos de un plano ajeno para que cuadren es
# sustituir el dibujo del arquitecto por nuestra idea de su dibujo. Lo que sí se
# puede hacer, y es lo que se hace, es **decir la cifra**: tantos recintos sin
# rótulo, y una traslación concreta que los explicaría todos. Con eso él decide
# si su plano tiene un error o si ArchMuse no entiende su forma de dibujar.
# ---------------------------------------------------------------------------

#: Qué fracción de recintos tiene que estar sin rótulo para ir siquiera a mirar
#: si hay un desplazamiento. Por debajo de esto el plano está esencialmente
#: rotulado y los huecos son casos sueltos, que ya tienen su propio hallazgo
#: (`coherencia.RECINTO_SIN_ETIQUETA`) y no se explican con una traslación.
UMBRAL_SIN_ROTULO = 0.8

#: Y qué fracción tiene que explicar la traslación candidata para poder
#: afirmarla. Una que arregle la mitad del plano no es un desplazamiento en
#: bloque: es una coincidencia, y decirla sería peor que callarse.
UMBRAL_EXPLICADOS = 0.8

#: Y cuánto tiene que explicar para poder **ofrecer** aplicarla, que es otra
#: cosa. Declarar «aquí pasa algo raro» con el 80% es útil; proponerle al
#: arquitecto que mueva sus rótulos con el 80% sería proponerle que estropee uno
#: de cada cinco. Ver `docs/prd/2026-09-11-alinear-rotulos-desplazados.md`, §4.1.
UMBRAL_LIMPIO = 0.95

#: A partir de qué distancia dos traslaciones candidatas son **distintas** y no
#: la misma leída con una casilla de diferencia. Una unidad de dibujo: por
#: debajo de eso, en un plano en metros, es el mismo desplazamiento.
DISTANCIA_ENTRE_CANDIDATAS = 1.0

#: Cuánto puede explicar una candidata rival, en proporción a la ganadora, antes
#: de que la respuesta deje de ser única. Si otra traslación distinta explica el
#: 90% de lo que explica la mejor, hay dos hipótesis y elegir sería adivinar.
RIVAL_ACEPTABLE = 0.9

#: A cuánto se redondean los vectores al votar, en unidades de dibujo. Es la
#: resolución de la respuesta: un desplazamiento real se vota muchas veces y
#: cae siempre en la misma casilla; el ruido se reparte entre todas.
PASO_DEL_VOTO = 0.25

#: Cuántas traslaciones candidatas se verifican de verdad. La votación tiene un
#: sesgo conocido —el rótulo más cercano al centro de un recinto no siempre es
#: el suyo, y con 939 textos en el plano casi nunca lo es—, así que la más
#: votada puede no ser la buena y hay que probar varias.
CANDIDATAS_A_VERIFICAR = 8

#: Topes de la muestra, para que un plano enorme no convierta esto en un
#: producto cartesiano. Mismo criterio que `_MUESTRA_MAXIMA`.
_MUESTRA_POLIGONOS = 200
_MUESTRA_ROTULOS = 2000


@dataclass(frozen=True)
class DesplazamientoDeRotulos:
    """Una traslación rígida que metería los rótulos dentro de los recintos.

    **Es un diagnóstico, no una corrección.** Nadie la aplica: viaja hasta el
    arquitecto para que él diga qué hacer con ella.

    `dx`/`dy` están en **unidades de dibujo**, sin escalar, porque es lo que él
    teclearía en un `DESPLAZA` para comprobarlo en su AutoCAD.
    """

    dx: float
    dy: float
    #: Recintos que la traslación deja con rótulo dentro, sobre los mirados.
    explicados: int
    #: Los que estaban sin rótulo antes de trasladar nada.
    sin_rotulo: int
    #: Cuántos recintos se han mirado (la muestra, no siempre el plano entero).
    mirados: int
    #: **La frontera entre declarar y ofrecer.** `True` sólo cuando la respuesta
    #: es única: explica casi todo (`UMBRAL_LIMPIO`) y ninguna otra traslación
    #: distinta explica algo comparable. Un desfase detectado pero no limpio se
    #: dice y no se ofrece — proponerle al arquitecto que mueva sus rótulos con
    #: una hipótesis entre dos es peor que no proponerle nada.
    limpio: bool = False
    #: Cuántas traslaciones distintas explicarían el plano casi igual de bien.
    #: 0 en el caso limpio. Es la cifra que hace discutible el `limpio`.
    competidoras: int = 0

    def __str__(self) -> str:
        return ("los rótulos están %s respecto de los recintos "
                "(%d de %d encajarían al moverlos %+.2f, %+.2f)"
                % (_distancia_legible(self.dx, self.dy), self.explicados,
                   self.mirados, self.dx, self.dy))


def _distancia_legible(dx: float, dy: float) -> str:
    """«50,00 hacia abajo» / «50,00 hacia abajo y 3,00 a la izquierda».

    Se dice en la dirección en la que están LOS RÓTULOS respecto del recinto,
    que es lo que él ve al mirar el plano, no el vector de corrección.

    **Un eje sólo se nombra por encima de dos casillas de votación.** Con una
    sola no se está midiendo un desplazamiento: se está leyendo la rejilla con
    la que se votó. En `plantasimple.dxf` la ganadora sale `(+0,25, +50,00)` y
    lo honesto es decir «50,00 hacia abajo», no «y además 0,25 a la izquierda»,
    que suena a una precisión que este método no tiene. Las dos cifras exactas
    viajan igualmente en `dx`/`dy` para quien quiera comprobarlas.
    """
    minimo = 2 * PASO_DEL_VOTO
    partes = []
    if abs(dy) >= minimo:
        partes.append("%s hacia %s" % (_con_coma(abs(dy)), "abajo" if dy > 0 else "arriba"))
    if abs(dx) >= minimo:
        partes.append("%s hacia la %s" % (_con_coma(abs(dx)), "izquierda" if dx > 0 else "derecha"))
    if not partes:
        return "a menos de media unidad de dibujo"
    return "%s unidades de dibujo %s" % (partes[0].split(" ", 1)[0],
                                         " y ".join(p.split(" ", 1)[1] for p in partes))


def _con_coma(valor: float) -> str:
    """`50,00` y no `50.00`. Toda cifra que ve el arquitecto lleva coma decimal
    en el resto del producto; una que no la lleve delata de dónde sale."""
    return ("%.2f" % valor).replace(".", ",")


def _sin_rotulo_dentro(polygons: List[Polygon], arbol) -> int:
    """Cuántos de esos polígonos no contienen el punto de inserción de ningún
    texto. Con el índice espacial ya construido: sin él, un plano de 200
    recintos y 900 textos son 180.000 comprobaciones por cada traslación que se
    quiera probar."""
    fuera = 0
    for polygon in polygons:
        if len(arbol.query(polygon, predicate="contains")) == 0:
            fuera += 1
    return fuera


def detectar_desplazamiento_de_rotulos(
    polygons: List[Polygon],
    labels: List[Tuple[str, float, float]],
) -> Optional[DesplazamientoDeRotulos]:
    """La traslación que explicaría un plano entero sin rotular, o `None`.

    `None` significa las tres cosas que no hay que confundir, y en este orden:
    que el plano sí está rotulado (lo normal), que no hay con qué mirarlo, o
    que **no se ha encontrado ninguna traslación que lo explique** — y esta
    última es un resultado, no un fallo: quiere decir que los recintos están
    sin rótulo por otro motivo y que no hay que ir por aquí.
    """
    if not polygons or not labels:
        return None

    muestra = polygons[:_MUESTRA_POLIGONOS]
    textos = labels[:_MUESTRA_ROTULOS]
    puntos = [Point(x, y) for _texto, x, y in textos]
    arbol = STRtree(puntos)

    sin_rotulo = _sin_rotulo_dentro(muestra, arbol)
    if sin_rotulo < UMBRAL_SIN_ROTULO * len(muestra):
        return None

    # Un voto por cada pareja (recinto, rótulo): el vector que llevaría ese
    # rótulo al centro de ese recinto. La pareja verdadera vota siempre la
    # misma casilla; las 190.000 falsas se reparten.
    votos: Dict[Tuple[float, float], int] = {}
    for polygon in muestra:
        centro = polygon.centroid
        cx, cy = centro.x, centro.y
        for _texto, x, y in textos:
            casilla = (
                round((cx - x) / PASO_DEL_VOTO) * PASO_DEL_VOTO,
                round((cy - y) / PASO_DEL_VOTO) * PASO_DEL_VOTO,
            )
            votos[casilla] = votos.get(casilla, 0) + 1

    if not votos:
        return None

    candidatas = sorted(votos.items(), key=lambda par: (-par[1], par[0]))
    verificadas: List[Tuple[float, float, int]] = []
    for (dx, dy), _n in candidatas[:CANDIDATAS_A_VERIFICAR]:
        if dx == 0.0 and dy == 0.0:
            continue
        # Se traslada el RECINTO al revés en vez de los rótulos: así el índice
        # espacial de los textos se construye una sola vez para todo.
        movidos = [trasladar_geometria(p, xoff=-dx, yoff=-dy) for p in muestra]
        explicados = len(movidos) - _sin_rotulo_dentro(movidos, arbol)
        if explicados >= UMBRAL_EXPLICADOS * len(muestra):
            verificadas.append((dx, dy, explicados))

    if not verificadas:
        return None

    dx, dy, explicados = max(verificadas, key=lambda v: v[2])

    # **La prueba de rival, que es lo que separa declarar de ofrecer.** Una
    # traslación *distinta* —a más de una unidad de la ganadora— que explique
    # casi lo mismo no es una confirmación: es una segunda hipótesis. Dos
    # hipótesis y una sola respuesta significa adivinar, y aquí no se adivina.
    competidoras = sum(
        1 for otro_dx, otro_dy, otros in verificadas
        if math.hypot(otro_dx - dx, otro_dy - dy) > DISTANCIA_ENTRE_CANDIDATAS
        and otros >= RIVAL_ACEPTABLE * explicados
    )
    limpio = (explicados >= UMBRAL_LIMPIO * len(muestra)) and competidoras == 0

    return DesplazamientoDeRotulos(
        dx=dx, dy=dy, explicados=explicados, sin_rotulo=sin_rotulo,
        mirados=len(muestra), limpio=limpio, competidoras=competidoras)


def build_rooms_from_document(
    doc: Drawing, layer: str = AREA_LAYER, descartes: Optional[List[EntidadDescartada]] = None,
    reparaciones: Optional[List[GeometriaReparada]] = None,
    desplazamiento: Optional[Tuple[float, float]] = None,
) -> List[Room]:
    """Habitaciones del documento, **en unidades de dibujo**.

    No convierte a metros: para eso está `leer_plano`, que es lo que debe usar
    cualquier código que mire el plano de un usuario. Esta función se conserva
    porque es el escalón sobre el que se apoya `leer_plano` y porque el
    guardián de regresión (`tests/test_ingesta_regresion.py`) la usa
    precisamente para vigilar que la lectura en crudo no cambie.

    `descartes` y `reparaciones`: ver `_closed_polygons_with_color`.
    """
    polygons = extract_room_polygons(
        doc, layer, descartes=descartes, reparaciones=reparaciones,
        desplazamiento=desplazamiento)
    labels = extract_labels(doc, con_capa=True, desplazamiento=desplazamiento)
    capas_validas, _reparto = _capas_que_nombran(polygons, labels, layer)

    rooms: List[Room] = []
    for polygon in polygons:
        label = match_label_to_room(polygon, labels, capas_validas=capas_validas)
        rooms.append(Room(label=label, polygon=polygon, layer=layer))

    return rooms


# ---------------------------------------------------------------------------
# Lectura validada de capas AM_* operativas (Fase 1 del contrato de
# clasificación DXF)
# ---------------------------------------------------------------------------


def _leer_capa_am(
    doc: Drawing, capa: str
) -> Tuple[List[Polygon], List[EntidadDescartada], List[GeometriaReparada]]:
    """Polígonos válidos de una capa `AM_*` operativa, el inventario de lo que
    se ha descartado y por qué, y el de lo que ha entrado reparado.

    Reutiliza `_recorrer_plano` (herencia de capa dentro de bloques) y
    `_esta_cerrada` (con la recuperación geométrica ya existente) tal cual
    están -- esta función no reimplementa nada de eso. Lo único que añade es
    la validación que el contrato de clasificación exige para una capa
    `AM_*`: cerrada, >= 3 vértices, polígono geométricamente válido.

    **CAMBIO DEL 2026-09-11 (`C-10`).** Hasta hoy el docstring decía «ninguna
    geometría inválida se repara nunca aquí». Ya no es cierto, y el cambio es
    deliberado: se repara **lo que se puede reparar sin que la superficie se
    mueva**, que es justamente lo que no tiene contenido profesional. Lo demás
    se sigue descartando exactamente igual que antes — la pajarita de
    `tests/test_capas_am.py` incluida, cuya área pasaría de 0,00 a 8,00 m².
    """
    poligonos: List[Polygon] = []
    descartes: List[EntidadDescartada] = []
    reparaciones: List[GeometriaReparada] = []
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
        # **`C-10`, y aquí está la unificación.** Antes esta rama descartaba
        # TODA geometría inválida y el modo heredado la dejaba pasar: dos
        # criterios distintos para el mismo defecto. Ahora los dos llaman a
        # `_validar_o_reparar`. Esto no relaja el criterio de las capas `AM_*`
        # —una pajarita de verdad se sigue descartando, porque repararla movería
        # su área de 0,00 a 8,00 m²— sino que lo explica: descartaba todo porque
        # no sabía distinguir un defecto de dibujo de una figura ambigua.
        polygon = _validar_o_reparar(
            Polygon(points), capa, tipo, _handle_de(entity), descartes, reparaciones)
        if polygon is not None:
            poligonos.append(polygon)
    return poligonos, descartes, reparaciones


def _capas_ignoradas(doc: Drawing, capas_miradas) -> List[CapaIgnorada]:
    """Capas del plano que no son ninguna de `capas_miradas`, con cuántas
    entidades tiene cada una.

    Recorre el plano entero una vez más (bloques incluidos, vía
    `_recorrer_plano`) sólo para contar por capa -- barato frente al resto
    del pipeline y necesario porque nada más agrega por capa sobre el DXF
    completo: cada lector existente (`_leer_capa_am`, `_closed_polygons_with_color`)
    filtra por UNA capa conocida de antemano, que es justo lo que aquí no se
    tiene. Ordenadas por número de entidades, de más a menos: lo que más
    llama la atención primero.
    """
    recuento: Dict[str, int] = {}
    for _entity, capa in _recorrer_plano(doc):
        if capa in capas_miradas:
            continue
        recuento[capa] = recuento.get(capa, 0) + 1
    return [
        CapaIgnorada(capa=nombre, entidades=n)
        for nombre, n in sorted(recuento.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def leer_plano(doc: Drawing, layer: Optional[str] = None, factor_escala: Optional[float] = None,
               alinear_rotulos: bool = False) -> PlanoLeido:
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
    geometria_reparada: List[GeometriaReparada] = []

    poligonos_util_int, descartes_util, reparadas_util = _leer_capa_am(doc, CAPA_UTIL_INTERIOR)
    geometria_no_leida.extend(descartes_util)
    geometria_reparada.extend(reparadas_util)
    poligonos_cons_cer, descartes_cons, reparadas_cons = _leer_capa_am(doc, CAPA_CONSTRUIDA_CERRADA)
    geometria_no_leida.extend(descartes_cons)
    geometria_reparada.extend(reparadas_cons)
    poligonos_util_ext, descartes_util_ext, reparadas_util_ext = _leer_capa_am(doc, CAPA_UTIL_EXTERIOR)
    geometria_no_leida.extend(descartes_util_ext)
    geometria_reparada.extend(reparadas_util_ext)
    poligonos_cons_ext, descartes_cons_ext, reparadas_cons_ext = _leer_capa_am(doc, CAPA_CONSTRUIDA_EXTERIOR)
    geometria_no_leida.extend(descartes_cons_ext)
    geometria_reparada.extend(reparadas_cons_ext)

    # **Primero se leen los recintos sin alinear nada.** El detector necesita la
    # geometría ya leída para poder medir el desfase, así que este primer paso
    # es inevitable — y es también el único que ocurre en un plano normal.
    usa_capa_am = bool(poligonos_util_int) or bool(descartes_util)
    if usa_capa_am:
        capa = None
        nombre_capa = CAPA_UTIL_INTERIOR
        capa_por_heuristico = False
    else:
        capa, capa_por_heuristico = _resolver_capa(doc, layer)
        nombre_capa = capa.nombre

    reparto_visto = {}

    def _leer_recintos(desplazamiento):
        """Los recintos con los rótulos donde diga `desplazamiento`. `None` es
        «donde el arquitecto los dibujó», que es siempre la primera lectura."""
        if usa_capa_am:
            etiquetas = extract_labels(doc, con_capa=True, desplazamiento=desplazamiento)
            capas_validas, reparto = _capas_que_nombran(
                poligonos_util_int, etiquetas, CAPA_UTIL_INTERIOR)
            reparto_visto["r"] = reparto
            return [
                Room(label=match_label_to_room(p, etiquetas, capas_validas=capas_validas),
                     polygon=p, layer=CAPA_UTIL_INTERIOR)
                for p in poligonos_util_int
            ]
        rooms_leidos = build_rooms_from_document(
            doc, nombre_capa, descartes=geometria_no_leida,
            reparaciones=geometria_reparada, desplazamiento=desplazamiento)
        # El reparto de la ULTIMA lectura, que es la que produce los `Room` que
        # se devuelven: si se ha alineado, el bueno es el de la lectura alineada.
        reparto_visto["r"] = _capas_que_nombran(
            [r.polygon for r in rooms_leidos],
            extract_labels(doc, con_capa=True, desplazamiento=desplazamiento),
            nombre_capa)[1]
        return rooms_leidos

    rooms = _leer_recintos(None)
    unit_labels = extract_unit_labels(doc)

    # Antes de escalar, porque `dx`/`dy` se dicen en unidades de dibujo: es lo
    # que el arquitecto teclearia en un DESPLAZA para comprobarlo el mismo.
    #
    # Se le pasan TODOS los recintos, no sólo los que se han quedado sin
    # `label`: el detector cuenta por su cuenta cuántos no tienen ningún texto
    # dentro, y ése es justo el guardián que hace que en un plano normal esto no
    # cueste nada (un índice espacial y una consulta por recinto, y fuera).
    # Pasarle sólo los que no casaron daría el 100% siempre y el guardián no
    # llegaría a actuar nunca.
    rotulos_desplazados = detectar_desplazamiento_de_rotulos(
        [room.polygon for room in rooms],
        list(extract_labels(doc)),
    )

    # **Y sólo aquí, si alguien lo ha pedido Y el desfase es limpio, se alinea.**
    # Las dos condiciones, nunca una: `alinear_rotulos` es una petición del
    # arquitecto, no una orden, y un desfase con dos hipótesis no se aplica
    # aunque la pida (`docs/prd/2026-09-11-alinear-rotulos-desplazados.md`).
    #
    # Se vuelve a leer con los rótulos corridos. **Los polígonos son los mismos
    # objetos**: lo único que cambia es dónde se cree que están los textos, y eso
    # vive en una lista de tuplas que muere al terminar esta función. El DXF no
    # se toca, ni el del disco ni el que hay en memoria.
    rotulos_alineados = None
    if (alinear_rotulos and rotulos_desplazados is not None
            and rotulos_desplazados.limpio):
        corrimiento = (rotulos_desplazados.dx, rotulos_desplazados.dy)
        rooms = _leer_recintos(corrimiento)
        unit_labels = extract_unit_labels(doc, desplazamiento=corrimiento)
        rotulos_alineados = rotulos_desplazados

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

    capas_miradas = {nombre_capa, CAPA_UTIL_INTERIOR, CAPA_CONSTRUIDA_CERRADA,
                     CAPA_UTIL_EXTERIOR, CAPA_CONSTRUIDA_EXTERIOR}
    capas_ignoradas = _capas_ignoradas(doc, capas_miradas)

    return PlanoLeido(
        rooms=rooms, unit_labels=unit_labels, escala=deteccion, layer=nombre_capa, capa=capa,
        envolventes_cerradas=poligonos_cons_cer,
        superficies_utiles_exteriores=poligonos_util_ext,
        envolventes_exteriores=poligonos_cons_ext,
        geometria_no_leida=geometria_no_leida,
        geometria_reparada=geometria_reparada,
        rotulos_alineados=rotulos_alineados,
        reparto_de_rotulos=reparto_visto.get("r") or RepartoDeRotulos(),
        capas_ignoradas=capas_ignoradas,
        capa_elegida_por_heuristico=capa_por_heuristico,
        rotulos_desplazados=rotulos_desplazados)



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


def _resolver_capa(doc: Drawing, pedida: Optional[str]) -> Tuple[CapaCandidata, bool]:
    """La capa con la que leer el plano, o `CapaIndeterminada` si hay que
    preguntar. Calcula las candidatas una sola vez.

    Cuando nadie ha elegido, `AREA_LAYER` tiene preferencia si existe y llega
    al umbral. No es porque su nombre sea especial —lo tiene que ganar como
    cualquier otra—, sino porque un nombre que el arquitecto ya usa es una
    respuesta suya anterior, y respetarla evita cambiarle el resultado por una
    heurística nueva.

    Devuelve `(capa, por_heuristico)`. `por_heuristico` es `True` únicamente
    cuando la capa sale de `_decidir_capa` -elegida por parecido entre varias
    candidatas, sin que nadie la haya nombrado-: es una inferencia, y una
    inferencia declara su hipótesis en cualquier documento que la use (ver
    `PlanoLeido.capa_elegida_por_heuristico`). Cuando el arquitecto la ha
    confirmado (`pedida`) o cuando `AREA_LAYER` gana por sí sola, es un hecho
    declarado -una respuesta o un nombre que ya existía-, no una inferencia.
    """
    candidatas = capas_candidatas(doc)

    if pedida:
        elegida = _buscar_capa(candidatas, pedida)
        if elegida is None:
            raise CapaIndeterminada(candidatas, pedida=pedida)
        return elegida, False

    por_defecto = _buscar_capa(candidatas, AREA_LAYER)
    if por_defecto is not None and por_defecto.puntuacion >= UMBRAL_CAPA_ACEPTABLE:
        return por_defecto, False

    elegida = _decidir_capa(candidatas)
    if elegida is None:
        raise CapaIndeterminada(candidatas)
    return elegida, True
