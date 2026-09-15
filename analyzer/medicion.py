# -*- coding: utf-8 -*-
"""Medición de superficies útiles de una planta, vivienda por vivienda.

**El hueco que esto cierra, medido y no supuesto.** Hasta hoy el trabajo del
cuadro de superficies se negaba a empezar en cuanto el DXF tenía más de una
vivienda: «esta función de momento solo admite un DXF con una única vivienda
detectada». Ese es el caso raro, no el normal — una planta de un edificio
residencial tiene tres, cuatro o seis viviendas —, así que el producto sólo
funcionaba sobre el plano recortado de un piso. Con el segundo plano real del
cliente (tres viviendas rotuladas `VT1/3`, `VT2/2` y `VT3/3`) ArchMuse no
entregaba nada.

**Lo que sí existía y no usaba nadie.** El reparto de recintos por vivienda ya
estaba resuelto y probado en `evaluator.group_rooms_by_unit_label`: cada
recinto va a la etiqueta `VT…` más cercana. Este módulo no lo reimplementa —lo
usa— y añade las tres cosas que hacen falta para que el resultado se pueda
entregar en vez de sólo consultar:

1. **Auditar el reparto.** Que el reparto exista no lo hace firme. Un recinto
   casi equidistante entre dos etiquetas se asigna a una de las dos y nadie se
   entera. Aquí se mide la holgura (`HOLGURA_MINIMA_DE_REPARTO`) y un reparto
   apretado se declara: es lo que separa «medido» de «adivinado».
2. **Cruzar la suma contra la geometría.** La suma de las piezas y la unión
   geométrica de las piezas tienen que dar lo mismo. Cuando no lo dan, hay
   metros contados dos veces, y la diferencia exacta es el dato que lo prueba.
   Sobre el plano real del cliente son **7,08 m²**.
3. **No perder ninguna pieza.** Toda pieza dibujada aparece en la medición: en
   su ámbito si su rótulo lo dice, y como «sin clasificar» si no. Una pieza que
   desaparece de un cuadro de superficies es superficie que falta sin que nadie
   lo sepa.

**Dos magnitudes, no una** (criterio del arquitecto, 2026-09-07). Una vivienda
lleva **superficie útil interior** y **superficie útil exterior**, y no se
suman: hasta el 2026-09-08 existía un único `total_util_m2` que las sumaba al
100 %, con lo que una terraza pesaba en el resultado igual que un dormitorio.
Ese campo se ha eliminado del modelo, del acta, del PDF, de la API y de la
pantalla — no se conserva en paralelo.

**La regla de los totales, y es deliberadamente dura.** Una cifra que puede
estar mal es peor que su ausencia: la primera se copia a la memoria del
proyecto y la segunda se pregunta. Así que **basta un impedimento —cualquiera
de los tres— para que esa vivienda no lleve ninguna de las dos cifras**. Las
piezas siguen midiéndose una a una, que es donde está casi todo el valor, y el
impedimento va escrito con su magnitud.

**Este módulo no emite criterio profesional** (`D-7`). No dice si una vivienda
es pequeña, ni si un solape es un error del plano o una convención de su autor:
dice qué piezas hay, cuánto miden y qué no cuadra. Clasificar una terraza como
superficie exterior no es criterio: es la estructura del propio cuadro del
plano (`ESPACIOS EXTERIORES`), y los patrones se leen de allí en vez de
copiarse aquí.

**No escribe nada y no importa `ezdxf`.** Recibe un `PlanoLeido` ya en metros.
Lo que escribe el documento es `analyzer/medicion_pdf.py`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from shapely.geometry import Point
from shapely.ops import unary_union

from .cuadro_superficies import (
    _PATRON_ASEO,
    _PATRON_BALCON,
    _PATRON_BANO,
    _PATRON_DISTRIBUIDOR,
    _PATRON_PORCHE,
    _PATRON_SALON_Y_COCINA,
    _PATRON_SOLO_COCINA,
    _PATRON_SOLO_PASILLO,
    _PATRON_SOLO_SALON,
    _PATRON_TENDEDERO,
    _PATRON_TERRAZA,
    _PATRON_VESTIBULO_RECIBIDOR_HALL,
    _normalizar,
)

#: Decimales con los que se publica una superficie. Los mismos dos con los que
#: se firma un cuadro de superficies: publicar más dígitos sugiere una exactitud
#: que la geometría de un DXF no tiene.
DECIMALES = 2

AMBITO_INTERIOR = "interior"
AMBITO_EXTERIOR = "exterior"
AMBITO_SIN_CLASIFICAR = "sin_clasificar"

#: Cuántas veces más lejos tiene que estar la segunda etiqueta de vivienda que
#: la primera para que el reparto de un recinto se considere firme.
#:
#: **Por qué 2 y no otra cosa.** Sobre el plano real de tres viviendas la
#: holgura peor de las 22 piezas es 2,67 y la mejor 7,4: el umbral pasa con
#: margen en un plano bien dibujado. Y en el caso que de verdad importa —dos
#: viviendas medianeras, sin hueco entre ellas— el reparto por cercanía deja de
#: ser fiable justo cuando esta relación se acerca a 1, que es cuando esto lo
#: declara en vez de callárselo. No es una tolerancia de cálculo: es la frontera
#: entre medir y adivinar.
HOLGURA_MINIMA_DE_REPARTO = 2.0

#: Un recinto se reparte por su rótulo con el mismo vocabulario que ya usa el
#: cuadro de superficies del plano. **El orden importa y el exterior va
#: primero**: una pieza rotulada explícitamente «terraza» o «tendedero» es
#: superficie exterior aunque su rótulo mencione además otra estancia, y el
#: patrón de salón+cocina es una alternancia ancha que se la llevaría.
#:
#: Añadir una familia es añadir una línea aquí. Lo que NO se hace nunca es
#: clasificar por defecto lo que no se reconoce: eso va a `sin_clasificar`, se
#: enseña con su superficie, y bloquea el total de esa vivienda.
_PATRON_DORMITORIO = re.compile(r"\bDORMITORIO\b")

#: **Decisión 3 de Pablo (2026-09-13).** «Salón» solo es su propia familia,
#: igual que «cocina»; «distribuidor» se separa de «pasillo»; «recibidor» y
#: «hall» son «vestíbulo»; «balcón» y «porche» son exteriores. «salón + cocina»
#: exige las dos palabras: hasta ese día bastaba cualquiera de ellas, y un
#: «Salón» a secas se contaba como salón y cocina.
FAMILIAS: Tuple[Tuple[re.Pattern, str, str], ...] = (
    (_PATRON_TERRAZA, "terraza", AMBITO_EXTERIOR),
    (_PATRON_BALCON, "balcón", AMBITO_EXTERIOR),
    (_PATRON_PORCHE, "porche", AMBITO_EXTERIOR),
    (_PATRON_TENDEDERO, "tendedero", AMBITO_EXTERIOR),
    (_PATRON_SALON_Y_COCINA, "salón + cocina", AMBITO_INTERIOR),
    (_PATRON_SOLO_SALON, "salón", AMBITO_INTERIOR),
    (_PATRON_SOLO_COCINA, "cocina", AMBITO_INTERIOR),
    (_PATRON_DORMITORIO, "dormitorio", AMBITO_INTERIOR),
    (_PATRON_BANO, "baño", AMBITO_INTERIOR),
    (_PATRON_ASEO, "aseo", AMBITO_INTERIOR),
    (_PATRON_SOLO_PASILLO, "pasillo", AMBITO_INTERIOR),
    (_PATRON_DISTRIBUIDOR, "distribuidor", AMBITO_INTERIOR),
    (_PATRON_VESTIBULO_RECIBIDOR_HALL, "vestíbulo", AMBITO_INTERIOR),
)

#: Cómo se han separado las viviendas. Las dos formas no valen lo mismo y por
#: eso viajan en el resultado: la primera es lo que declaró el arquitecto en su
#: propio plano; la segunda es una suposición geométrica de ArchMuse.
POR_ROTULOS = "rótulos de vivienda del plano"
POR_PROXIMIDAD = "proximidad geométrica (el plano no rotula sus viviendas)"


def _redondear(valor: float) -> float:
    return round(float(valor), DECIMALES)


def _m2(valor: float) -> str:
    """Una superficie escrita como se escribe en un cuadro: con coma decimal.

    Los motivos de este módulo los lee un arquitecto en un documento, no un
    programa. Un motivo que dice «7.08 m2» dentro de un texto en castellano se
    lee como descuido, y el descuido se contagia a la cifra que acompaña.
    """
    return ("%.2f m²" % float(valor)).replace(".", ",")


@dataclass(frozen=True)
class PiezaMedida:
    """Un recinto del plano, medido y clasificado. Nada más."""

    rotulo: Optional[str]
    familia: str            # "" cuando el rótulo no corresponde a ninguna conocida
    ambito: str
    area_m2: float
    capa: str

    @property
    def nombre(self) -> str:
        return (self.rotulo or "").strip() or "(sin rótulo)"


@dataclass(frozen=True)
class Solape:
    """Dos piezas que se pisan: metros contados dos veces, con su magnitud."""

    una: str
    otra: str
    area_m2: float


@dataclass(frozen=True)
class RepartoDudoso:
    """Un recinto cuya vivienda no se puede afirmar, con las dos candidatas."""

    pieza: str
    asignada_a: str
    distancia_m: float
    siguiente: str
    distancia_siguiente_m: float

    @property
    def holgura(self) -> float:
        if self.distancia_m <= 0:
            return float("inf")
        return self.distancia_siguiente_m / self.distancia_m


def motivo_c13(nombre: str, cuantas: int) -> str:
    """`C-13` (firmado por Pablo, 2026-09-13): dos viviendas que no se pueden
    distinguir no se fusionan; se declara y no se escribe ninguna cifra suya.

    Una sola redacción para todas las salidas —medición, cuadro, web, agente—:
    el arquitecto tiene que leer lo mismo venga por donde venga."""
    return ("hay %d viviendas rotuladas «%s» en esta planta y ArchMuse no las distingue: "
            "no se escribe ninguna cifra suya ni se suman entre sí (C-13)" % (cuantas, nombre))


@dataclass(frozen=True)
class ViviendaMedida:
    """Una vivienda de la planta, con sus piezas y con lo que no cuadra."""

    nombre: str
    piezas: Tuple[PiezaMedida, ...]
    solapes: Tuple[Solape, ...] = field(default_factory=tuple)
    repartos_dudosos: Tuple[RepartoDudoso, ...] = field(default_factory=tuple)
    #: Unión geométrica de todas las piezas, **sin redondear**: la superficie que
    #: ocupa la vivienda contando una sola vez lo que esté dibujado dos.
    superficie_por_union_m2: float = 0.0
    #: Suma de las áreas **sin redondear**. No es lo mismo que sumar las cifras
    #: publicadas, y la diferencia importa: contra la unión hay que cruzar ésta,
    #: porque redondear ocho piezas a dos decimales y sumarlas produce hasta un
    #: céntimo de metro de descuadre que no es ningún solape. Publicar ese
    #: céntimo como «metros dibujados dos veces» sería un aviso falso, y un aviso
    #: falso destruye la confianza en los verdaderos.
    suma_cruda_m2: float = 0.0
    #: Cuántas viviendas de la planta llevan este mismo rótulo, ella incluida.
    #: `1` es lo normal; más de una es `C-13`: no se distinguen, y ninguna cifra
    #: suya se publica. Sus piezas sí se enseñan, una a una.
    viviendas_con_el_mismo_rotulo: int = 1

    # -- Sumas por ámbito ---------------------------------------------------

    def _suma(self, ambito: str) -> float:
        return _redondear(sum(p.area_m2 for p in self.piezas if p.ambito == ambito))

    @property
    def suma_interior_m2(self) -> float:
        """La suma de lo interior, **sin la regla dura**. Uso interno y del
        motivo de un impedimento: publicar esto es lo que hacen
        `util_interior_m2` y `util_exterior_m2`, que sí la aplican."""
        return self._suma(AMBITO_INTERIOR)

    @property
    def suma_exterior_m2(self) -> float:
        return self._suma(AMBITO_EXTERIOR)

    @property
    def sin_clasificar(self) -> Tuple[PiezaMedida, ...]:
        return tuple(p for p in self.piezas if p.ambito == AMBITO_SIN_CLASIFICAR)

    @property
    def suma_de_piezas_m2(self) -> float:
        """La suma de las cifras **publicadas**, para que la tabla cuadre.

        Un arquitecto suma la columna a mano, y una tabla cuyo total no es la
        suma de sus filas se lee como un error de cálculo aunque sea el
        redondeo. Para detectar solapes se usa `suma_cruda_m2`, que es otra cosa.
        """
        return _redondear(sum(p.area_m2 for p in self.piezas))

    @property
    def diferencia_con_la_union_m2(self) -> float:
        """Metros contados dos veces: sobre las magnitudes crudas, no las
        publicadas."""
        return _redondear(self.suma_cruda_m2 - self.superficie_por_union_m2)

    # -- La regla dura de los totales ---------------------------------------

    @property
    def impedimentos(self) -> Tuple[str, ...]:
        """Por qué esta vivienda no lleva total. Vacío = el total es publicable.

        Los tres motivos se declaran con su magnitud, porque «no se puede
        totalizar» sin la cifra que lo explica es indistinguible de un fallo del
        programa.
        """
        motivos: List[str] = []
        # El primero porque es el más grave: con los otros, la cifra puede estar
        # mal; con éste, no se sabe ni de qué vivienda es.
        if self.viviendas_con_el_mismo_rotulo > 1:
            motivos.append(motivo_c13(self.nombre, self.viviendas_con_el_mismo_rotulo))
        if self.solapes:
            motivos.append(
                "hay %s dibujados dos veces: la suma de las piezas da %s y la "
                "superficie que ocupan realmente es %s"
                % (_m2(self.diferencia_con_la_union_m2), _m2(self.suma_de_piezas_m2),
                   _m2(self.superficie_por_union_m2))
            )
        if self.repartos_dudosos:
            motivos.append(
                "el reparto de %d pieza(s) entre viviendas no es firme: %s"
                % (len(self.repartos_dudosos),
                   ", ".join("«%s» está a %.2f m de %s y a %.2f m de %s"
                             % (r.pieza, r.distancia_m, r.asignada_a,
                                r.distancia_siguiente_m, r.siguiente)
                             for r in self.repartos_dudosos))
            )
        sueltas = self.sin_clasificar
        if sueltas:
            motivos.append(
                "%d pieza(s) no se sabe si son superficie interior o exterior por su "
                "rótulo (%s): sumarlas a un lado u otro sería decidirlo por el arquitecto"
                % (len(sueltas),
                   "; ".join("«%s» %s" % (p.nombre, _m2(p.area_m2)) for p in sueltas))
            )
        return tuple(motivos)

    @property
    def util_interior_m2(self) -> Optional[float]:
        """Superficie útil **interior**, o `None` **con motivo en `impedimentos`**.

        **Son dos magnitudes, no una, y no se suman** (criterio dictaminado por
        el arquitecto el 2026-09-07, ver `PROGRESS.md`). Hasta hoy existía un
        único `total_util_m2` que sumaba interior y exterior al 100 %: una
        terraza entraba en el total de superficie útil con el mismo peso que un
        dormitorio, que no es como se firma un cuadro de superficies. El campo
        único **se ha eliminado**, no se conserva en paralelo: dejarlo vivo era
        dejar la cifra vieja al alcance de cualquier consumidor nuevo.

        **La regla dura se hereda entera, y ahora vale para las dos.** Antes los
        parciales se publicaban aunque el total estuviera bloqueado, porque eran
        el desglose de una cifra que el lector ya veía ausente. Al pasar a ser
        ellos mismos el resultado, publicarlos con un impedimento abierto sería
        exactamente el «total que puede estar mal» que este módulo existe para
        no dar: un solape puede caer dentro de lo interior, dentro de lo
        exterior o a caballo, y una pieza sin clasificar no se sabe de qué lado
        cuenta. Con cualquier impedimento, **las dos** son `None` y las piezas
        se siguen enseñando una a una, que es donde está casi todo el valor.
        """
        if self.impedimentos:
            return None
        return self.suma_interior_m2

    @property
    def util_exterior_m2(self) -> Optional[float]:
        """Superficie útil **exterior** (terrazas y tendederos), o `None`.
        Mismo criterio que `util_interior_m2`."""
        if self.impedimentos:
            return None
        return self.suma_exterior_m2


@dataclass(frozen=True)
class Medicion:
    """La planta entera, medida."""

    viviendas: Tuple[ViviendaMedida, ...]
    agrupacion: str
    #: Rótulos `VT…` del plano a los que no ha ido a parar ningún recinto. No es
    #: un error —un plano trae etiquetas de otras plantas o de una leyenda— pero
    #: callarlo escondería una vivienda entera que no se ha medido.
    rotulos_sin_piezas: Tuple[str, ...] = field(default_factory=tuple)
    #: Geometría que el lector del DXF ha descartado, con su motivo. Un descarte
    #: silencioso es superficie que falta sin que nadie lo sepa.
    geometria_no_leida: Tuple[dict, ...] = field(default_factory=tuple)
    #: Contornos que estaban mal construidos y han entrado REPARADOS, sin que su
    #: superficie cambie (`C-10`). Hermano del anterior y por el mismo motivo:
    #: una reparación callada es peor que un descarte callado, porque el número
    #: sale bien y nadie va a ir a mirar por qué.
    geometria_reparada: Tuple[dict, ...] = field(default_factory=tuple)
    #: La correccion de rotulos APLICADA en esta medicion, si alguna. `None` es
    #: lo normal. Cuando no lo es, la cifra depende de ella y tiene que constar:
    #: una medicion que se apoya en un desplazamiento y no lo dice es una cifra
    #: sin procedencia.
    rotulos_alineados: Optional[dict] = None
    #: El desfase DETECTADO, se haya aplicado o no. Es lo que permite al cliente
    #: preguntar: sin esto, el comando no sabe que hay nada que ofrecer.
    rotulos_desplazados: Optional[dict] = None
    #: De que capa salen los nombres de las estancias, y con que reparto.
    capa_de_rotulos: Optional[dict] = None

    @property
    def viviendas_con_total(self) -> int:
        return sum(1 for v in self.viviendas if v.util_interior_m2 is not None)

    @property
    def piezas(self) -> int:
        return sum(len(v.piezas) for v in self.viviendas)

    # -- El total de la planta ----------------------------------------------
    #
    # **La misma regla dura que arriba, un nivel por encima.** Una vivienda no
    # lleva total si algo lo impide; una planta no lleva total si le falta una
    # vivienda. Sin esto, quien quisiera el total de la planta lo sumaba a mano
    # —que es justo el trabajo que se viene a delegar— o, peor, lo sumaba en
    # código de presentación saltándose las que no se pudieron medir. Eso
    # último es exactamente el defecto que se corrigió el 2026-09-03 en
    # `agente/skills/superficies.py`: 295,10 m² publicados sobre un plano de
    # seis viviendas de las que sólo cinco se habían medido.

    @property
    def viviendas_sin_total(self) -> Tuple[str, ...]:
        return tuple(v.nombre for v in self.viviendas if v.util_interior_m2 is None)

    @property
    def impedimentos(self) -> Tuple[str, ...]:
        """Por qué esta planta no lleva total. Vacío = el total es publicable."""
        if not self.viviendas:
            return ("no se ha medido ninguna vivienda en esta planta",)
        sin_total = self.viviendas_sin_total
        if sin_total:
            return (
                "%s no lleva%s superficie útil total, y una planta a la que le falta "
                "una vivienda entera no se totaliza: el motivo de cada una está en su "
                "cuadro" % (", ".join("«%s»" % n for n in sin_total),
                            "" if len(sin_total) == 1 else "n"),
            )
        return ()

    @property
    def advertencias(self) -> Tuple[str, ...]:
        """Lo que NO impide el total pero hay que leer pegado a él.

        **Por qué esto no bloquea.** Un rótulo `VT…` al que no ha ido a parar
        ningún recinto puede ser una vivienda de esta planta que no se ha
        medido —y entonces al total le falta— o una etiqueta de otra planta o
        de una leyenda, y entonces no falta nada. No se puede decidir cuál es
        sin mirar el plano, así que ni se bloquea el total (haría inútil la
        cifra: los dos planos reales del cliente traen «VT22/1») ni se calla
        (sería publicar un total que puede estar corto sin avisar). Va junto al
        número, no en una lista al pie.
        """
        if not self.rotulos_sin_piezas:
            return ()
        return (
            "el plano rotula %s y ningún recinto ha ido a parar ahí: si es una vivienda "
            "de esta planta, el total no la incluye"
            % ", ".join("«%s»" % r for r in self.rotulos_sin_piezas),
        )

    @property
    def util_interior_m2(self) -> Optional[float]:
        """Superficie útil interior de la planta, o `None` **con motivo en
        `impedimentos`**.

        Suma las cifras **publicadas** de cada vivienda, no las magnitudes
        crudas: el arquitecto suma la columna a mano y una planta cuya cifra no
        es la suma de sus viviendas se lee como un error de cálculo.
        """
        if self.impedimentos:
            return None
        return _redondear(sum(v.util_interior_m2 or 0.0 for v in self.viviendas))

    @property
    def util_exterior_m2(self) -> Optional[float]:
        """Superficie útil exterior de la planta. Mismo criterio que la
        interior — **y nunca se suman entre sí**."""
        if self.impedimentos:
            return None
        return _redondear(sum(v.util_exterior_m2 or 0.0 for v in self.viviendas))


# ---------------------------------------------------------------------------
# El cálculo
# ---------------------------------------------------------------------------

def clasificar(rotulo: Optional[str]) -> Tuple[str, str]:
    """`(familia, ámbito)` de un rótulo. Lo desconocido no se fuerza a nada."""
    normalizado = _normalizar(rotulo or "")
    if not normalizado.strip():
        return "", AMBITO_SIN_CLASIFICAR
    for patron, familia, ambito in FAMILIAS:
        if patron.search(normalizado):
            return familia, ambito
    return "", AMBITO_SIN_CLASIFICAR


def _pieza(room) -> PiezaMedida:
    familia, ambito = clasificar(room.label)
    return PiezaMedida(
        rotulo=room.label,
        familia=familia,
        ambito=ambito,
        area_m2=_redondear(room.polygon.area),
        capa=room.layer,
    )


def _solapes(rooms: Sequence) -> Tuple[Solape, ...]:
    """Los pares de recintos que se pisan, con la superficie compartida.

    Compartir un borde no es solaparse: la intersección de dos polígonos
    contiguos es una línea, de área cero. Se compara redondeado a los mismos dos
    decimales con los que se publica todo lo demás — declarar un solape de
    0,0001 m² sería un aviso falso, y un aviso falso destruye la confianza en
    los verdaderos.

    Los pares llegan ordenados por superficie descendente: el solape grande es
    el que explica por qué no cuadra la suma.
    """
    encontrados: List[Solape] = []
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            try:
                compartida = rooms[i].polygon.intersection(rooms[j].polygon).area
            except Exception:                     # noqa: BLE001 - geometría rota
                continue
            if _redondear(compartida) > 0:
                encontrados.append(Solape(
                    una=(rooms[i].label or "(sin rótulo)"),
                    otra=(rooms[j].label or "(sin rótulo)"),
                    area_m2=_redondear(compartida),
                ))
    return tuple(sorted(encontrados, key=lambda s: -s.area_m2))


def _repartos_dudosos(rooms: Sequence, nombre: str,
                      unit_labels: Sequence) -> Tuple[RepartoDudoso, ...]:
    """Audita el reparto que ha hecho `group_rooms_by_unit_label`.

    No lo rehace: mide su holgura. Con una sola etiqueta no hay reparto que
    dudar, y sin etiquetas el reparto no se ha hecho por rótulo — lo declara
    `Medicion.agrupacion`, no esto.
    """
    if len(unit_labels) < 2:
        return ()
    import numpy as np

    # **Las mismas dos distancias, sin un `Point` por pareja** (medido el
    # 2026-09-15: con 52 viviendas y 208 rótulos, 387.486 `Point` y 7,9 s de los
    # 27 de una medición). numpy descarta los rótulos que no pueden ser de los
    # dos más cercanos; los que quedan —con holgura para el último decimal— se
    # ordenan con la distancia de shapely y el desempate por texto de siempre.
    lx = np.array([float(x) for _e, x, _y in unit_labels])
    ly = np.array([float(y) for _e, _x, y in unit_labels])
    dudosos: List[RepartoDudoso] = []
    for room in rooms:
        centro = room.polygon.centroid
        aproximadas = np.hypot(lx - centro.x, ly - centro.y)
        umbral = np.partition(aproximadas, 1)[1] * (1 + 1e-9) + 1e-9
        distancias = sorted(
            (centro.distance(Point(unit_labels[i][1], unit_labels[i][2])), unit_labels[i][0])
            for i in np.flatnonzero(aproximadas <= umbral)
        )
        (d1, _primera), (d2, segunda) = distancias[0], distancias[1]
        # `d1 == 0` es el rótulo dibujado justo encima del recinto: la
        # asignación más firme que puede haber, no una división por cero.
        if d1 <= 0 or d2 / d1 >= HOLGURA_MINIMA_DE_REPARTO:
            continue
        dudosos.append(RepartoDudoso(
            pieza=(room.label or "(sin rótulo)"),
            asignada_a=nombre,
            distancia_m=d1,
            siguiente=segunda,
            distancia_siguiente_m=d2,
        ))
    return tuple(dudosos)


def medir_planta(plano) -> Medicion:
    """Mide todas las viviendas de un `PlanoLeido` ya en metros.

    El reparto en viviendas lo hace `evaluator`, que es donde vive y donde está
    probado. Aquí se mide, se audita ese reparto y se declara lo que no cuadra.
    """
    # Import perezoso y local: `evaluator` arrastra las 38 reglas de evaluación
    # y este módulo no usa ninguna — sólo el agrupador. Importarlo arriba
    # convertiría una medición en una dependencia de todo el evaluador.
    from . import evaluator

    unit_labels: List[Tuple[str, float, float]] = list(
        getattr(plano, "unit_labels", None) or [])
    rooms = list(plano.rooms)
    if unit_labels:
        unidades = evaluator.group_rooms_by_unit_label(rooms, unit_labels)
        agrupacion = POR_ROTULOS
    else:
        unidades = evaluator.group_rooms_by_proximity(rooms)
        agrupacion = POR_PROXIMIDAD

    from collections import Counter

    # `C-13`: el agrupador ya no funde dos rótulos iguales; aquí se cuenta cuántas
    # viviendas comparten cada uno para que ninguna de ellas publique una cifra.
    mismo_rotulo = Counter(u.name for u in unidades)

    viviendas: List[ViviendaMedida] = []
    for unidad in unidades:
        piezas = tuple(_pieza(r) for r in unidad.rooms)
        union = unary_union([r.polygon for r in unidad.rooms]).area if unidad.rooms else 0.0
        viviendas.append(ViviendaMedida(
            nombre=unidad.name,
            piezas=piezas,
            solapes=_solapes(unidad.rooms),
            repartos_dudosos=_repartos_dudosos(unidad.rooms, unidad.name, unit_labels),
            superficie_por_union_m2=union,
            suma_cruda_m2=sum(r.polygon.area for r in unidad.rooms),
            viviendas_con_el_mismo_rotulo=mismo_rotulo[unidad.name],
        ))

    con_piezas = {v.nombre for v in viviendas}
    rotulos_sin_piezas = tuple(
        etiqueta for etiqueta, _x, _y in unit_labels if etiqueta not in con_piezas
    )

    descartes: List[dict] = []
    for descarte in getattr(plano, "geometria_no_leida", None) or ():
        descartes.append({
            "motivo": getattr(descarte, "motivo", ""),
            "capa": getattr(descarte, "capa", ""),
            "tipo": getattr(descarte, "tipo", ""),
            "entidad": getattr(descarte, "handle", None) or "",
        })

    reparaciones: List[dict] = []
    for reparada in getattr(plano, "geometria_reparada", None) or ():
        reparaciones.append({
            "capa": getattr(reparada, "capa", ""),
            "tipo": getattr(reparada, "tipo", ""),
            "entidad": getattr(reparada, "handle", None) or "",
            "detalle": getattr(reparada, "detalle", ""),
        })

    alineados = getattr(plano, "rotulos_alineados", None)
    detectado = getattr(plano, "rotulos_desplazados", None)
    reparto = getattr(plano, "reparto_de_rotulos", None)

    return Medicion(
        viviendas=tuple(viviendas),
        agrupacion=agrupacion,
        rotulos_sin_piezas=rotulos_sin_piezas,
        geometria_no_leida=tuple(descartes),
        geometria_reparada=tuple(reparaciones),
        rotulos_alineados=(
            {"dx": alineados.dx, "dy": alineados.dy,
             "recintos_explicados": alineados.explicados,
             "recintos_mirados": alineados.mirados}
            if alineados is not None else None),
        rotulos_desplazados=(
            {"dx": detectado.dx, "dy": detectado.dy, "limpio": detectado.limpio,
             "recintos_sin_rotulo": detectado.sin_rotulo,
             "recintos_explicados": detectado.explicados,
             "recintos_mirados": detectado.mirados,
             "aplicado": alineados is not None}
            if detectado is not None else None),
        capa_de_rotulos=(
            {"capa": reparto.capa, "ambiguo": reparto.ambiguo,
             "reparto": [list(par) for par in reparto.recuento]}
            if reparto is not None and reparto.recuento else None),
    )


# ---------------------------------------------------------------------------
# Serialización — la misma forma que consume el PDF y que viaja en el acta
# ---------------------------------------------------------------------------

def a_dict(medicion: Medicion) -> Dict:
    """La medición en tipos simples. Nada se calcula aquí que no esté ya."""
    return {
        "agrupacion": medicion.agrupacion,
        "viviendas": [
            {
                "vivienda": v.nombre,
                "piezas": [
                    {
                        "rotulo": p.nombre,
                        "familia": p.familia,
                        "ambito": p.ambito,
                        "area_m2": p.area_m2,
                        "capa": p.capa,
                    }
                    for p in v.piezas
                ],
                # Las dos magnitudes que se publican, cada una con su regla dura
                # aplicada. **Nunca se suman entre sí** -- ver `util_interior_m2`.
                "util_interior_m2": v.util_interior_m2,
                "util_exterior_m2": v.util_exterior_m2,
                "suma_de_piezas_m2": v.suma_de_piezas_m2,
                "superficie_por_union_m2": _redondear(v.superficie_por_union_m2),
                "impedimentos": list(v.impedimentos),
                "solapes": [
                    {"una": s.una, "otra": s.otra, "area_m2": s.area_m2}
                    for s in v.solapes
                ],
                "repartos_dudosos": [
                    {
                        "pieza": r.pieza,
                        "asignada_a": r.asignada_a,
                        "distancia_m": _redondear(r.distancia_m),
                        "siguiente": r.siguiente,
                        "distancia_siguiente_m": _redondear(r.distancia_siguiente_m),
                    }
                    for r in v.repartos_dudosos
                ],
            }
            for v in medicion.viviendas
        ],
        "viviendas_medidas": len(medicion.viviendas),
        "viviendas_con_total": medicion.viviendas_con_total,
        # El total de la planta, con la misma forma que el de una vivienda:
        # la cifra o `None`, y en el segundo caso el motivo. `advertencias`
        # viaja aunque haya total -- ver el docstring de la propiedad.
        "util_interior_m2": medicion.util_interior_m2,
        "util_exterior_m2": medicion.util_exterior_m2,
        "viviendas_sin_total": list(medicion.viviendas_sin_total),
        "impedimentos_del_total": list(medicion.impedimentos),
        "advertencias_del_total": list(medicion.advertencias),
        "piezas": medicion.piezas,
        "rotulos_sin_piezas": list(medicion.rotulos_sin_piezas),
        "geometria_no_leida": [dict(d) for d in medicion.geometria_no_leida],
        "geometria_reparada": [dict(d) for d in medicion.geometria_reparada],
        "rotulos_alineados": (dict(medicion.rotulos_alineados)
                              if medicion.rotulos_alineados else None),
        "rotulos_desplazados": (dict(medicion.rotulos_desplazados)
                                if medicion.rotulos_desplazados else None),
        "capa_de_rotulos": (dict(medicion.capa_de_rotulos)
                            if medicion.capa_de_rotulos else None),
    }
