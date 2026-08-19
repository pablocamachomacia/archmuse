# -*- coding: utf-8 -*-
"""¿Es este plano coherente consigo mismo? La revisión previa a la entrega.

PRD: `docs/prd/2026-08-19-revision-de-coherencia-del-plano.md`.

**Qué contesta y qué no.** Contesta si el dibujo y el cuadro de superficies del
propio fichero hablan del mismo piso, y si la geometría está bien construida.
**No contesta si el proyecto cumple normativa**, y ninguna comprobación de este
módulo usa un umbral de ninguna norma. Es una distinción de producto, no de
implementación: un informe limpio de aquí no significa que un plano sea
correcto, significa que no se contradice a sí mismo.

**El hallazgo que justifica que esto exista.** Casi todo lo de aquí ya se
calculaba y se tiraba. Los solapes servían para negarse a medir —el arquitecto
veía el efecto, nunca la causa—; las polilíneas con el flag `closed` mal puesto
iban a `_log.warning`, es decir a un terminal que nadie lee, pese a que el
propio parser documenta que «tiene que quedar visible para quien audite»; y la
etiqueta repetida acababa como una celda `BLOQUEADO`. Ejecutado sobre el plano
real del cliente, esto produce **siete hallazgos** sin escribir una sola
comprobación nueva de geometría.

**La regla dura de este módulo: no se gradúa la gravedad.** Ningún `Hallazgo`
lleva severidad, ni crítico, ni leve, ni prioridad. Se dice qué es y cuánto
mide. «Se solapan 4,00 m²» es un hecho comprobable; «esto es grave» es criterio
profesional, y el criterio profesional de ArchMuse está sin firmar (`D-7`).
Quien añada aquí un campo `severidad` tiene que saber que está cruzando esa
frontera y no ajustando un formato.

**Y la segunda: un hallazgo que no se puede ir a comprobar no se emite.** Cada
uno nombra su entidad —la etiqueta, la superficie, el `handle` del DXF— para que
un tercero pueda abrir el fichero y verlo. Un aviso que no se puede localizar no
ahorra tiempo: lo gasta.
"""
from __future__ import annotations

import collections
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

# --- El vocabulario de tipos, cerrado a propósito --------------------------
#
# Cerrado porque quien consume esto (el PDF, la Skill, un plugin) tiene que
# poder agrupar por tipo sin adivinar, y porque una lista abierta se convierte
# en doce variantes de la misma frase en tres meses.

SOLAPE = "solape_entre_recintos"
POLILINEA_MAL_CERRADA = "polilinea_mal_cerrada"
GEOMETRIA_DESCARTADA = "geometria_descartada"
ETIQUETA_DUPLICADA = "etiqueta_duplicada"
RECINTO_SIN_ETIQUETA = "recinto_sin_etiqueta"
CUADRO_PIDE_PIEZA_NO_DIBUJADA = "el_cuadro_pide_una_pieza_que_no_esta_dibujada"
PIEZA_DIBUJADA_FUERA_DEL_CUADRO = "pieza_dibujada_que_el_cuadro_no_contempla"
RECUENTO_NO_COINCIDE = "el_cuadro_y_el_plano_no_cuentan_lo_mismo"
SIN_RECINTOS = "no_se_ha_leido_ningun_recinto"

TIPOS = (
    SOLAPE,
    POLILINEA_MAL_CERRADA,
    GEOMETRIA_DESCARTADA,
    ETIQUETA_DUPLICADA,
    RECINTO_SIN_ETIQUETA,
    CUADRO_PIDE_PIEZA_NO_DIBUJADA,
    PIEZA_DIBUJADA_FUERA_DEL_CUADRO,
    RECUENTO_NO_COINCIDE,
    SIN_RECINTOS,
)

#: Lo que se ha mirado, en el orden en que se mira, para que un informe sin
#: hallazgos pueda enumerarlo. Un informe vacío se lee como «no ha funcionado»;
#: un informe que dice qué ha comprobado se lee como lo que es.
COMPROBACIONES = (
    ("Recintos leídos", "que la capa de recintos dé alguna pieza"),
    ("Solapes entre recintos", "que dos piezas de la misma vivienda no se pisen"),
    ("Polilíneas mal cerradas", "que ningún contorno se haya cerrado por suposición"),
    ("Geometría descartada", "qué entidades no han entrado en el análisis, y por qué"),
    ("Rótulos", "que ninguna pieza esté sin rotular y que ningún rótulo se repita"),
    ("Cuadro contra dibujo", "que el cuadro y el plano nombren las mismas piezas"),
)

_RE_AVISO_CERRADA = re.compile(
    r"distan\s+([\d.eE+-]+)\s+unidades de dibujo\s+\(capa\s+'([^']*)',\s+handle\s+'([^']*)'\)"
)

#: Sufijo numérico de un campo del cuadro (`terraza_1` -> `terraza`). El cuadro
#: numera los huecos de una familia; el plano rotula las piezas por su nombre.
#: Comparar sin normalizar produciría un hallazgo falso por cada terraza.
_RE_SUFIJO = re.compile(r"_\d+$")

#: Campos del cuadro que no nombran una pieza del plano: totales, superficies
#: construidas, el tipo de vivienda y el número de unidades. Compararlos contra
#: los rótulos del dibujo daría cuatro hallazgos falsos garantizados.
_PREFIJOS_NO_PIEZA = ("total", "superficie_", "numero_", "vivienda_")


@dataclass(frozen=True)
class Hallazgo:
    """Algo que no cuadra, dicho con su entidad y su magnitud. **Sin gravedad.**

    `entidad` es lo que permite ir a verlo en el DXF: un rótulo, un par de
    rótulos, un `handle`. `magnitud` es la cifra que lo dimensiona cuando la
    hay —metros cuadrados de solape, centímetros de hueco—; `None` cuando el
    hallazgo no es cuantitativo, y entonces se dice `None` en vez de un cero
    que se leería como «cero, medido».
    """

    tipo: str
    descripcion: str
    entidad: str
    magnitud: Optional[float] = None
    unidad: str = ""
    #: Datos crudos para quien quiera reconstruir el hallazgo sin releer el DXF.
    detalle: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.tipo not in TIPOS:
            raise ValueError(
                "«%s» no está en el catálogo cerrado de tipos de hallazgo: %s"
                % (self.tipo, list(TIPOS))
            )
        if not self.entidad:
            raise ValueError(
                "un hallazgo sin entidad no se puede ir a comprobar, y un aviso "
                "que no se puede localizar gasta tiempo en vez de ahorrarlo "
                "(tipo: %s)" % self.tipo
            )

    def a_dict(self) -> Dict[str, Any]:
        return {
            "tipo": self.tipo,
            "descripcion": self.descripcion,
            "entidad": self.entidad,
            "magnitud": self.magnitud,
            "unidad": self.unidad,
            "detalle": dict(self.detalle),
        }


class _CapturaDeAvisos(logging.Handler):
    """Recoge los avisos que el parser emite mientras lee, sin tocar el resto.

    **Por qué hace falta y por qué se aísla tanto.** El parser documenta que la
    recuperación de una polilínea mal cerrada «se registra SIEMPRE con
    `_log.warning`, nunca en silencio», porque «tiene que quedar visible para
    quien audite». Un `logging.warning` es visible para un programador con una
    terminal abierta, no para el arquitecto que va a entregar el plano — así que
    hoy ese aviso, en la práctica, no existe.

    Se instala sobre el logger de `analyzer.parser` y **se retira siempre**, en
    un `finally`. Dejarlo puesto contaminaría la configuración de log del
    proceso anfitrión, que puede ser un servidor web o el AutoCAD de alguien.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.mensajes: List[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.mensajes.append(record.getMessage())
        except Exception:                          # pragma: no cover - defensivo
            pass


def leer_plano_capturando_avisos(doc, *, layer=None, factor_escala=None):
    """`parser.leer_plano`, pero conservando lo que avisó por el camino.

    Devuelve `(plano, avisos)`. No traduce ni filtra los avisos: eso es trabajo
    de `_polilineas_mal_cerradas`, que sabe qué forma tienen.
    """
    from analyzer import parser

    captura = _CapturaDeAvisos()
    log = logging.getLogger(parser.__name__)
    log.addHandler(captura)
    try:
        plano = parser.leer_plano(doc, layer=layer, factor_escala=factor_escala)
    finally:
        log.removeHandler(captura)
    return plano, tuple(captura.mensajes)


# --- Las comprobaciones ----------------------------------------------------

def _agrupar_en_viviendas(plano) -> List:
    """Las viviendas del plano, con el mismo criterio que el resto del motor.

    Se prefiere el rótulo `VT<n>` cuando lo hay —es lo que el arquitecto ha
    declarado— y sólo se cae a la proximidad cuando no hay ninguno, que es
    exactamente el repliegue de `evaluator`. Agrupar aquí de otra manera haría
    que la revisión hablara de unas viviendas y el cuadro de otras.
    """
    from analyzer import evaluator

    if not plano.rooms:
        return []
    if getattr(plano, "unit_labels", None):
        return list(evaluator.group_rooms_by_unit_label(plano.rooms, plano.unit_labels))
    return list(evaluator.group_rooms_by_proximity(plano.rooms))


def _solapes(unidades: Sequence) -> List[Hallazgo]:
    """Dos piezas de la misma vivienda que se pisan: metros contados dos veces.

    No se reimplementa la detección: se usa `evaluator.evaluate_room_overlap`,
    que ya tiene la tolerancia calibrada (`ROOM_OVERLAP_TOLERANCE_M2`, ruido de
    dibujo, no umbral de ninguna norma) y que distingue dos piezas contiguas
    —comparten borde, no área— de dos piezas solapadas.
    """
    from analyzer import evaluator

    if not unidades:
        return []
    salida = []
    for s in evaluator.evaluate_room_overlap(list(unidades)):
        salida.append(Hallazgo(
            tipo=SOLAPE,
            descripcion=(
                "«%s» y «%s» se solapan %.2f m² (el %.0f %% de la pieza menor). "
                "Esa superficie se está contando dos veces."
                % (s.room_a_label, s.room_b_label, s.overlap_m2, s.overlap_pct_menor)
            ),
            entidad="%s + %s" % (s.room_a_label, s.room_b_label),
            magnitud=round(s.overlap_m2, 2),
            unidad="m2",
            detalle={"pct_de_la_pieza_menor": round(s.overlap_pct_menor, 1),
                     "vivienda": s.unit_name},
        ))
    return salida


def _polilineas_mal_cerradas(avisos: Sequence[str]) -> List[Hallazgo]:
    """Contornos que el DXF declara abiertos y el parser ha cerrado por su cuenta.

    Es una **corrección de datos**, no un hecho neutro: la superficie de esa
    pieza se está calculando sobre una suposición razonable pero no comprobada.
    Un hueco de tres centímetros entre el primer y el último vértice puede ser
    ruido de dibujo o puede ser un contorno que en realidad no cierra.
    """
    salida = []
    for mensaje in dict.fromkeys(avisos):
        casa = _RE_AVISO_CERRADA.search(mensaje)
        if not casa:
            continue
        try:
            hueco_m = float(casa.group(1))
        except ValueError:                         # pragma: no cover - defensivo
            continue
        capa, handle = casa.group(2), casa.group(3)
        salida.append(Hallazgo(
            tipo=POLILINEA_MAL_CERRADA,
            descripcion=(
                "El contorno «%s» de la capa «%s» está marcado como ABIERTO en el "
                "DXF y se ha tratado como cerrado porque sus extremos distan "
                "%.4g unidades de dibujo. Su superficie se ha calculado sobre esa "
                "suposición." % (handle, capa, hueco_m)
            ),
            entidad="handle %s" % handle,
            magnitud=hueco_m,
            unidad="unidades de dibujo",
            detalle={"capa": capa, "handle": handle},
        ))
    return salida


def _geometria_descartada(plano) -> List[Hallazgo]:
    """Lo que no ha entrado en el análisis, con su motivo. Un descarte
    silencioso es una superficie que falta sin que nadie lo sepa."""
    salida = []
    for d in (getattr(plano, "geometria_no_leida", None) or ()):
        handle = getattr(d, "handle", None)
        salida.append(Hallazgo(
            tipo=GEOMETRIA_DESCARTADA,
            descripcion=(
                "Una entidad %s de la capa «%s» no ha entrado en el análisis: %s"
                % (d.tipo, d.capa, d.motivo)
            ),
            entidad="handle %s" % handle if handle else "%s en «%s»" % (d.tipo, d.capa),
            detalle={"capa": d.capa, "tipo": d.tipo, "motivo": d.motivo,
                     "handle": handle, "detalle": getattr(d, "detalle", "")},
        ))
    return salida


def _rotulos(unidades: Sequence) -> List[Hallazgo]:
    """Piezas sin rotular y rótulos repetidos, **dentro de cada vivienda**.

    Un rótulo repetido no es un error del arquitecto —dos tendederos son dos
    tendederos— pero **impide el reparto automático**: el cuadro tiene un hueco
    por familia, y ArchMuse no reparte por orden de aparición. Se dice lo que
    es: dos piezas con el mismo nombre, con sus superficies, para que el
    arquitecto decida.

    **Por vivienda y no por plano, y esto lo enseñó el segundo plano real.** En
    `V5.dxf` hay tres viviendas en un mismo fichero, cada una con su programa
    completo y correcto: tres «Salón/cocina», tres «Baño», tres «Dormitorio 1».
    Contando sobre el plano entero salían **ocho hallazgos, los ocho falsos**,
    sobre un plano perfectamente bien dibujado. Un rótulo sólo se repite —en el
    sentido que importa— cuando se repite dentro de la misma vivienda, porque
    es ahí donde el cuadro tiene un único hueco para él.
    """
    salida = []
    for unidad in unidades:
        rooms = unidad.rooms
        donde = " en «%s»" % unidad.name if len(unidades) > 1 else ""

        sin_rotulo = [r for r in rooms if not (r.label or "").strip()]
        if sin_rotulo:
            salida.append(Hallazgo(
                tipo=RECINTO_SIN_ETIQUETA,
                descripcion=(
                    "%d pieza(s)%s no tienen rótulo. Sin nombre no se pueden cruzar "
                    "contra el cuadro de superficies." % (len(sin_rotulo), donde)
                ),
                entidad="%d recinto(s) de %.2f m² en total%s"
                        % (len(sin_rotulo), sum(r.area_m2 for r in sin_rotulo), donde),
                magnitud=round(sum(r.area_m2 for r in sin_rotulo), 2),
                unidad="m2",
                detalle={"areas_m2": [round(r.area_m2, 2) for r in sin_rotulo],
                         "vivienda": unidad.name},
            ))

        cuenta = collections.Counter(
            (r.label or "").strip() for r in rooms if (r.label or "").strip())
        for etiqueta, n in sorted(cuenta.items()):
            if n < 2:
                continue
            areas = sorted(round(r.area_m2, 2) for r in rooms
                           if (r.label or "").strip() == etiqueta)
            salida.append(Hallazgo(
                tipo=ETIQUETA_DUPLICADA,
                descripcion=(
                    "El rótulo «%s» aparece %d veces%s, con superficies de %s m². El "
                    "cuadro tiene un hueco por familia, así que hay que decir cuál es "
                    "cuál." % (etiqueta, n, donde, " y ".join("%.2f" % a for a in areas))
                ),
                entidad="%s%s" % (etiqueta, donde),
                magnitud=float(n),
                unidad="piezas",
                detalle={"areas_m2": areas, "vivienda": unidad.name},
            ))
    return salida


def _normalizar(texto: str) -> str:
    """El rótulo del plano y el campo del cuadro, llevados a la misma forma.

    Sin esto, «Salón/cocina» y `salon_cocina` serían dos piezas distintas y el
    informe daría dos hallazgos falsos por cada habitación del plano — que es
    exactamente el fallo que destruye la confianza en los verdaderos.
    """
    import unicodedata

    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto or "")
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", "_", sin_tildes.lower()).strip("_")


def _familias_del_cuadro(cuadro) -> Dict[str, List[str]]:
    """Familia -> campos del cuadro que la piden (`terraza` -> terraza_1, _2)."""
    familias: Dict[str, List[str]] = collections.OrderedDict()
    for celda in (getattr(cuadro, "celdas", None) or ()):
        campo = celda.campo
        if campo.startswith(_PREFIJOS_NO_PIEZA):
            continue
        familias.setdefault(_RE_SUFIJO.sub("", campo), []).append(campo)
    return familias


def _familia_del_rotulo(etiqueta: str) -> str:
    """«Dormitorio 1» -> `dormitorio`. La misma normalización que el cuadro.

    **El falso positivo que esto evita, encontrado al probarlo sobre el plano
    real.** El cuadro numera los *huecos* (`dormitorio_1`, `dormitorio_2`,
    `dormitorio_3`) y el arquitecto numera los *rótulos* («Dormitorio 1»...).
    Comparando sin quitar el sufijo a los dos lados, un piso de tres
    dormitorios producía **seis hallazgos falsos**: tres «el cuadro pide un
    dormitorio que no está dibujado» y tres «el plano dibuja un dormitorio que
    el cuadro no contempla», sobre las mismas tres habitaciones perfectamente
    correctas. Seis avisos falsos en el primer plano real habrían bastado para
    que nadie volviera a abrir el informe (`DESTROY_ARCHMUSE.md` §5.1).
    """
    return _RE_SUFIJO.sub("", _normalizar(etiqueta))


def _cuadro_contra_dibujo(rooms: Sequence, cuadro) -> List[Hallazgo]:
    """¿Nombran el cuadro y el plano las mismas piezas, y las mismas cuántas?

    Se compara **por familia y por recuento**, no por presencia: «el cuadro
    reserva dos terrazas y el plano dibuja una» dice mucho más que «terraza:
    sí/no», y es la forma en la que un arquitecto revisa esto a mano.

    **Se emite como discrepancia, nunca como defecto**, y la diferencia importa:
    un pasillo puede no dibujarse como recinto propio y no por eso el plano está
    mal. Llamar «error» a eso sería inventar criterio profesional, que es
    justamente lo que este módulo no hace.
    """
    if cuadro is None:
        return []
    familias = _familias_del_cuadro(cuadro)
    dibujadas: Dict[str, List[str]] = collections.OrderedDict()
    for r in rooms:
        etiqueta = (r.label or "").strip()
        if etiqueta:
            dibujadas.setdefault(_familia_del_rotulo(etiqueta), []).append(etiqueta)

    salida = []
    for familia, campos in familias.items():
        rotulos = dibujadas.get(familia, [])
        if not rotulos:
            salida.append(Hallazgo(
                tipo=CUADRO_PIDE_PIEZA_NO_DIBUJADA,
                descripcion=(
                    "El cuadro reserva %s para «%s» y no hay ninguna pieza rotulada "
                    "así en el plano. Puede ser que no se dibuje como recinto "
                    "propio, o que falte: conviene mirarlo."
                    % ("un hueco" if len(campos) == 1 else "%d huecos" % len(campos),
                       familia.replace("_", " "))
                ),
                entidad=", ".join(campos),
                magnitud=float(len(campos)),
                unidad="huecos del cuadro",
                detalle={"campos": list(campos)},
            ))
        elif len(rotulos) != len(campos):
            salida.append(Hallazgo(
                tipo=RECUENTO_NO_COINCIDE,
                descripcion=(
                    "El cuadro reserva %d hueco(s) para «%s» y el plano dibuja %d "
                    "pieza(s) con ese nombre (%s). Sobra o falta una, o hay que "
                    "decir cuál va en cada hueco."
                    % (len(campos), familia.replace("_", " "), len(rotulos),
                       ", ".join(sorted(rotulos)))
                ),
                entidad=", ".join(campos),
                magnitud=float(len(rotulos) - len(campos)),
                unidad="piezas de diferencia",
                detalle={"campos": list(campos), "rotulos": sorted(rotulos),
                         "huecos": len(campos), "dibujadas": len(rotulos)},
            ))

    for familia, rotulos in dibujadas.items():
        if familia in familias:
            continue
        unicos = sorted(set(rotulos))
        salida.append(Hallazgo(
            tipo=PIEZA_DIBUJADA_FUERA_DEL_CUADRO,
            descripcion=(
                "El plano dibuja «%s» y el cuadro no tiene ningún hueco para esa "
                "pieza, así que su superficie no aparecerá en el cuadro."
                % ", ".join(unicos)
            ),
            entidad=", ".join(unicos),
            magnitud=float(len(rotulos)),
            unidad="piezas",
            detalle={"rotulos": unicos},
        ))
    return salida


# --- La auditoría completa -------------------------------------------------

@dataclass(frozen=True)
class Revision:
    """El resultado: los hallazgos, lo comprobado, y lo que no se ha podido mirar."""

    hallazgos: Tuple[Hallazgo, ...]
    comprobado: Tuple[Tuple[str, str], ...]
    no_comprobado: Tuple[str, ...] = ()
    recintos: int = 0
    #: Cuántas viviendas se han detectado en el fichero. Importa decirlo: un DXF
    #: con tres viviendas es perfectamente normal —`V5.dxf` lo es— y cambia lo
    #: que significa cada comprobación.
    viviendas: int = 0
    capa_de_recintos: str = ""
    unidad_del_dibujo: str = ""

    @property
    def limpio(self) -> bool:
        return not self.hallazgos

    def por_tipo(self) -> Dict[str, int]:
        cuenta: Dict[str, int] = collections.OrderedDict()
        for tipo in TIPOS:
            n = sum(1 for h in self.hallazgos if h.tipo == tipo)
            if n:
                cuenta[tipo] = n
        return cuenta

    def a_dict(self) -> Dict[str, Any]:
        return {
            "hallazgos": [h.a_dict() for h in self.hallazgos],
            "comprobado": [{"que": q, "para": p} for q, p in self.comprobado],
            "no_comprobado": list(self.no_comprobado),
            "recuento_por_tipo": self.por_tipo(),
            "recintos": self.recintos,
            "viviendas": self.viviendas,
            "capa_de_recintos": self.capa_de_recintos,
            "unidad_del_dibujo": self.unidad_del_dibujo,
            "limpio": self.limpio,
        }


def revisar(doc, *, layer=None, factor_escala=None) -> Revision:
    """La revisión entera de un DXF ya abierto. **No escribe nada.**

    Lanza `EscalaIndeterminada` o `CapaIndeterminada` tal cual las lanza el
    parser: si no se sabe en qué unidad está el plano, medir solapes en metros
    cuadrados produciría cifras de siete dígitos presentadas con toda seriedad.
    Preferir la pregunta al número inventado es la misma decisión que en `SK-1`.
    """
    from analyzer import cuadro_superficies as cs

    plano, avisos = leer_plano_capturando_avisos(
        doc, layer=layer, factor_escala=factor_escala)
    rooms = plano.rooms

    hallazgos: List[Hallazgo] = []
    no_comprobado: List[str] = []

    if not rooms:
        hallazgos.append(Hallazgo(
            tipo=SIN_RECINTOS,
            descripcion=(
                "No se ha leído ninguna pieza en la capa «%s». Casi siempre "
                "significa que los recintos están en otra capa." % plano.layer
            ),
            entidad="capa «%s»" % plano.layer,
            detalle={"capa": plano.layer},
        ))

    # Se agrupa UNA vez y con el criterio del resto del motor, y todo lo que
    # depende de «qué es una vivienda» usa esa misma agrupación. Contar sobre el
    # plano entero es lo que hacía que `V5.dxf` —tres viviendas correctas en un
    # fichero— saliera con ocho hallazgos, los ocho falsos.
    unidades = _agrupar_en_viviendas(plano)

    hallazgos.extend(_solapes(unidades))
    hallazgos.extend(_polilineas_mal_cerradas(avisos))
    hallazgos.extend(_geometria_descartada(plano))
    hallazgos.extend(_rotulos(unidades))

    cuadro = cs.detectar_cuadro_superficies(doc)
    if cuadro is None:
        no_comprobado.append(
            "el contraste entre el cuadro y el dibujo: este DXF no trae cuadro de "
            "superficies, así que no hay con qué comparar los rótulos del plano")
    elif len(unidades) > 1:
        # Un cuadro describe UNA vivienda. Cruzarlo contra los rótulos de tres
        # daría discrepancias en todas las familias y ninguna sería cierta. Se
        # dice que no se ha comprobado, con el motivo, en vez de comprobarlo mal.
        no_comprobado.append(
            "el contraste entre el cuadro y el dibujo: el fichero tiene %d viviendas "
            "(%s) y un cuadro describe una sola, así que cruzarlos daría "
            "discrepancias falsas en todas las familias"
            % (len(unidades), ", ".join(u.name for u in unidades)))
    else:
        hallazgos.extend(_cuadro_contra_dibujo(rooms, cuadro))

    return Revision(
        hallazgos=tuple(hallazgos),
        comprobado=COMPROBACIONES,
        no_comprobado=tuple(no_comprobado),
        recintos=len(rooms),
        viviendas=len(unidades),
        capa_de_recintos=plano.layer,
        unidad_del_dibujo=getattr(plano.escala, "unidad", "") or "",
    )
