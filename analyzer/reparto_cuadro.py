# -*- coding: utf-8 -*-
"""El reparto: qué texto va en qué celda del cuadro del arquitecto.

**Este módulo es la frontera entre lo que decide ArchMuse y lo que escribe
AutoCAD.** Todo el criterio profesional vive aquí y en lo que este módulo llama;
lo que sale es una lista de `(fila, columna, texto)` y tres listas de lo que no
ha podido escribirse. El cliente CAD **no interpreta nada**: escribe esas celdas
con `vla-SetText` y enseña esas listas. Es lo que impide que exista un segundo
sitio donde se decida qué es un tendedero (`D-7`).

### Las tres listas, y por qué son tres y no una

`C-6` (criterio firmado el 2026-09-10) exige que **toda pieza medida acabe en
exactamente uno de tres sitios**: una celda, la lista de piezas sin fila, o la
de bloqueos con su motivo. La unión son todas las piezas y ninguna se repite.
`verificar_conservacion()` lo comprueba sobre cada reparto, y hay un test que lo
comprueba sobre los planos reales.

No es burocracia: una pieza medida que no aparece en ningún sitio deja el cuadro
**cuadrado y equivocado** — los totales no la incluyen y nada en el documento
revela que falta. Es el fallo que hace que un cuadro pase un visado diciendo una
cifra que no es.

### Las dos reglas de parada

1. **Si hay una pieza medida sin fila donde ir, el total correspondiente no se
   rellena** (`C-6`). Un total que no incluye una superficie medida es un total
   falso.
2. **Si no se puede escribir ninguna celda, no se escribe ninguna.** Rellenar
   tres celdas de diecisiete y callar las catorce restantes es peor que no haber
   empezado: el arquitecto ve un cuadro medio relleno y no sabe si lo demás está
   pendiente o mal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from . import cuadro_superficies as cs

#: Columnas de valor de un cuadro de 4 columnas: 1 es la del útil interior, 3 la
#: del exterior. Las columnas 0 y 2 son las etiquetas y no se tocan nunca.
COLUMNA_INTERIOR = 1
COLUMNA_EXTERIOR = 3


@dataclass(frozen=True)
class CeldaAEscribir:
    """Una celda del cuadro del arquitecto, lista para `vla-SetText`."""

    fila: int
    columna: int
    texto: str
    campo: str
    #: De qué piezas medidas sale esta cifra. Vacío para las celdas que no son
    #: una superficie medida (un total, o `VIVIENDA TIPO`).
    piezas: Tuple[str, ...] = ()


@dataclass(frozen=True)
class NoEscrita:
    """Una celda que se deja como está, y por qué.

    **No se escribe nada en ella** — ni `N/D`, ni un guion. En el cuadro del
    arquitecto la celda vacía es su estado normal, y `N/D` sería texto de
    ArchMuse dentro de su entregable. El motivo vive aquí, en el acta y en la
    línea de comandos.
    """

    campo: str
    motivo: str
    fila: int = -1
    columna: int = -1


@dataclass(frozen=True)
class PiezaSinFila:
    """Una pieza medida que el cuadro no contempla. No desaparece (`C-6`)."""

    rotulo: str
    area_m2: float
    motivo: str


@dataclass(frozen=True)
class Reparto:
    vivienda: str
    celdas: Tuple[CeldaAEscribir, ...] = ()
    no_escritas: Tuple[NoEscrita, ...] = ()
    piezas_sin_fila: Tuple[PiezaSinFila, ...] = ()
    #: Filas del cuadro que ArchMuse no ha sabido identificar, con su motivo.
    filas_no_entendidas: Tuple[Tuple[str, str], ...] = ()
    medicion_limpia: bool = True
    impedimentos: Tuple[str, ...] = ()

    @property
    def se_puede_escribir(self) -> bool:
        """Regla de parada 2: o se escribe algo, o no se toca el plano."""
        return bool(self.celdas)


def _piezas_de(rooms: Sequence) -> List[Tuple[str, float]]:
    return [((r.label or "").strip(), float(r.area_m2)) for r in rooms]


def calcular_reparto(unit, cuadro: cs.CuadroSuperficies, rooms: Sequence,
                     medicion_limpia: bool = True,
                     impedimentos: Sequence[str] = ()) -> Reparto:
    """El reparto completo de una vivienda sobre su cuadro.

    `medicion_limpia` era la condición de `C-4`, derogado el 2026-09-13 por
    `D-13`: ya no hay ningún `0,00 m²` que condicionar —ninguna habitación mide
    cero y `calcular_relleno_cuadro` no lo produce—. Se conserva en el `Reparto`
    porque dice algo cierto de la medición, no porque decida una celda.
    """
    relleno = cs.calcular_relleno_cuadro(unit, cuadro, rooms)

    celdas: List[CeldaAEscribir] = []
    no_escritas: List[NoEscrita] = []
    for r in relleno:
        celda = cuadro.celda(r.campo)
        fila = celda.fila if celda is not None else -1
        columna = celda.columna_indice if celda is not None else -1
        if not r.escribir or r.estado in (cs.BLOQUEADO, cs.NO_DISPONIBLE):
            no_escritas.append(NoEscrita(r.campo, r.motivo or "", fila, columna))
            continue
        if celda is None:
            # El campo se ha calculado pero el cuadro no tiene esa fila: no hay
            # dónde escribirlo, y decirlo es más útil que callarlo.
            no_escritas.append(NoEscrita(
                r.campo, "este cuadro no tiene una fila para «%s»" % r.campo))
            continue
        celdas.append(CeldaAEscribir(fila=fila, columna=columna, texto=r.texto,
                                     campo=r.campo))

    piezas_sin_fila = _piezas_que_no_caben(cuadro, rooms, relleno)

    # `C-6`, regla de parada 1: si sobra una pieza, los totales dejan de ser
    # verdad. Se retiran de lo que se va a escribir, con el motivo puesto.
    if piezas_sin_fila:
        motivo = ("hay %d pieza(s) medida(s) que este cuadro no contempla (%s): "
                  "el total no se rellena, porque un total que no las incluye "
                  "sería falso"
                  % (len(piezas_sin_fila),
                     ", ".join("%s %.2f m²" % (p.rotulo, p.area_m2)
                               for p in piezas_sin_fila)))
        conservadas = []
        for c in celdas:
            if c.campo in cs.CAMPOS_TOTAL_UTIL:
                no_escritas.append(NoEscrita(c.campo, motivo, c.fila, c.columna))
            else:
                conservadas.append(c)
        celdas = conservadas

    return Reparto(
        vivienda=getattr(unit, "name", "") or "",
        celdas=tuple(celdas),
        no_escritas=tuple(no_escritas),
        piezas_sin_fila=tuple(piezas_sin_fila),
        filas_no_entendidas=tuple(cuadro.etiquetas_sin_campo),
        medicion_limpia=medicion_limpia,
        impedimentos=tuple(impedimentos),
    )


def _piezas_que_no_caben(cuadro: cs.CuadroSuperficies, rooms: Sequence,
                         relleno: Sequence) -> List[PiezaSinFila]:
    """Piezas medidas cuya familia no tiene fila en ESTE cuadro.

    Se compara por familia, no por rótulo: el cuadro pide «dormitorio 1», el
    plano rotula «Dormitorio 1», y son la misma cosa. Lo que se busca es la
    pieza cuya familia entera falta —un trastero, un garaje, una despensa— en un
    cuadro que no la contempla.
    """
    campos_del_cuadro = {c.campo for c in cuadro.celdas}
    sin_fila: List[PiezaSinFila] = []
    for rotulo, area in _piezas_de(rooms):
        campo = cs.campo_de_la_pieza(rotulo)
        if campo is None:
            sin_fila.append(PiezaSinFila(
                rotulo, area,
                "«%s» no es ninguna de las familias que ArchMuse reconoce, así "
                "que no se sabe en qué fila del cuadro va" % rotulo))
        elif campo not in campos_del_cuadro:
            sin_fila.append(PiezaSinFila(
                rotulo, area,
                "«%s» se ha medido, pero este cuadro no tiene una fila para "
                "«%s»" % (rotulo, campo)))
    return sin_fila


def verificar_conservacion(reparto: Reparto, rooms: Sequence) -> List[str]:
    """`C-6`: toda pieza medida en exactamente uno de tres sitios.

    Devuelve la lista de problemas encontrados; vacía significa que se cumple.
    Se devuelve en vez de lanzar porque el sitio donde esto se comprueba —el
    test y el comando— quiere enseñarlos todos, no el primero.
    """
    problemas: List[str] = []
    medidas = [rotulo for rotulo, _a in _piezas_de(rooms)]

    en_celdas: List[str] = []
    for c in reparto.celdas:
        en_celdas.extend(c.piezas)
    en_sin_fila = [p.rotulo for p in reparto.piezas_sin_fila]

    # Una pieza está "contabilizada" si su familia tiene celda escrita, si está
    # declarada sin fila, o si su familia aparece entre lo no escrito.
    campos_no_escritos = {n.campo for n in reparto.no_escritas}
    campos_escritos = {c.campo for c in reparto.celdas}

    for rotulo in medidas:
        campo = cs.campo_de_la_pieza(rotulo)
        sitios = 0
        if rotulo in en_sin_fila:
            sitios += 1
        if campo is not None and campo in campos_escritos:
            sitios += 1
        if campo is not None and campo in campos_no_escritos:
            sitios += 1
        if sitios == 0:
            problemas.append(
                "la pieza «%s» no está en ninguno de los tres sitios: ni celda, "
                "ni pieza sin fila, ni bloqueo" % rotulo)
        elif sitios > 1:
            problemas.append(
                "la pieza «%s» está en %d sitios a la vez" % (rotulo, sitios))
    return problemas


def _sin_espacios(texto: str) -> str:
    """`"VT1 /3"` -> `"VT1/3"`. El arquitecto escribe el código de tipología con
    un espacio en el cuadro y sin él en el plano; es la misma vivienda."""
    return "".join((texto or "").split()).upper()


def elegir_vivienda(unidades: Sequence, cuadro: cs.CuadroSuperficies):
    """Qué vivienda del plano corresponde a ESTE cuadro.

    Devuelve `(unidad, motivo)`. Si no se puede saber, la unidad es `None` y el
    motivo lo explica — **nunca se elige "la primera"**: en un plano con VT1/3 y
    VT2/2, rellenar el cuadro de una con las cifras de la otra es el peor error
    posible de esta capacidad, porque el resultado parece correcto.

    El emparejamiento va por el código de tipología que el propio cuadro
    declara en su fila `VIVIENDA TIPO` (`VT1 /3`), comparado sin espacios con el
    rótulo del plano (`VT1/3`). Si el cuadro no lo declara y el plano tiene una
    sola vivienda, es ésa: no hay ambigüedad que resolver.
    """
    unidades = list(unidades)
    if not unidades:
        return None, "el plano no tiene ninguna vivienda medida"

    celda = cuadro.celda("vivienda_tipo")
    declarado = _sin_espacios(celda.texto_actual) if celda is not None else ""

    if declarado:
        candidatas = [u for u in unidades
                      if _sin_espacios(getattr(u, "name", "")) == declarado]
        if len(candidatas) == 1:
            return candidatas[0], None
        if not candidatas:
            return None, (
                "el cuadro dice ser de la vivienda «%s» y el plano no tiene "
                "ninguna con ese rótulo (tiene %s)"
                % (celda.texto_actual,
                   ", ".join(getattr(u, "name", "?") for u in unidades)))
        return None, (
            "hay %d viviendas en el plano rotuladas «%s»: no se sabe cuál es la "
            "de este cuadro" % (len(candidatas), celda.texto_actual))

    if len(unidades) == 1:
        return unidades[0], None
    return None, (
        "el cuadro no dice de qué vivienda es y el plano tiene %d (%s): "
        "rellenarlo sería elegir una al azar"
        % (len(unidades), ", ".join(getattr(u, "name", "?") for u in unidades)))


# ---------------------------------------------------------------------------
# El cuadro que ArchMuse dibuja al lado del suyo (PRD 2026-09-12)
# ---------------------------------------------------------------------------
#
# **Hasta aquí, `Reparto` dice qué cifra va en qué celda DE SU TABLA.** Lo de
# abajo lo convierte en una tabla propia: mismas filas, mismas etiquetas, mismas
# posiciones, y los valores calculados por ArchMuse. Su tabla no se toca.
#
# **Por qué se replica su rejilla y no se aplana a una lista.** Su cuadro lleva
# dos pares etiqueta/valor por fila —interiores a la izquierda, exteriores a la
# derecha—. Dibujarlo en una sola columna daría una tabla más larga y ninguna
# fila coincidiría de altura con la suya, que es exactamente lo que hace útil
# ponerlas una al lado de otra.

#: Título del cuadro de ArchMuse. **Dice BORRADOR y dice ArchMuse**, en ese
#: orden, porque lo primero que tiene que quedar claro al mirar un plano con dos
#: cuadros es cuál de los dos no lo ha escrito el arquitecto.
TITULO_DEL_CUADRO = "ArchMuse · BORRADOR"

#: Lo que se escribe en una celda cuyo valor no se puede afirmar. **No se deja
#: en blanco**: una celda vacía se lee como «se me olvidó». La marca remite a la
#: nota al pie, que es donde cabe el motivo entero.
MARCA_DE_NOTA = "(%d)"


@dataclass(frozen=True)
class CeldaDibujable:
    """Un texto en una casilla de la rejilla de ArchMuse (base 0)."""

    fila: int
    columna: int
    texto: str


@dataclass(frozen=True)
class NotaDelCuadro:
    """Una nota al pie del cuadro: por qué una celda no lleva cifra.

    Va **dentro del cuadro**, en una fila fusionada al pie, y no en la línea de
    comandos: el entregable es el plano, y el arquitecto que lo abra dentro de
    seis meses no tiene la consola delante.
    """

    marca: str
    texto: str


@dataclass(frozen=True)
class CuadroDibujable:
    """Todo lo que el cliente CAD necesita para dibujar el cuadro, y nada más.

    El cliente recorre `celdas` y llama a `vla-SetText`; fusiona las filas de
    `notas` y escribe su texto. **No decide nada**: ni qué va en cada casilla, ni
    qué se queda en blanco, ni por qué.
    """

    titulo: str
    n_filas: int
    n_columnas: int
    celdas: Tuple[CeldaDibujable, ...]
    notas: Tuple[NotaDelCuadro, ...]
    #: De dónde salen las filas: copiadas de su cuadro, o el formato de ArchMuse
    #: porque el plano no tenía ninguno. Se le dice, no se le deja adivinar.
    origen: str

    @property
    def filas_totales(self) -> int:
        """Las de la rejilla más el título y las notas al pie."""
        return 1 + self.n_filas + len(self.notas)


ORIGEN_COPIADO = ("filas copiadas de tu cuadro, con tu redacción")
ORIGEN_CANONICO = ("formato de ArchMuse: este plano no traía cuadro")


def cuadro_dibujable(reparto: Reparto, cuadro: cs.CuadroSuperficies,
                     origen: str = ORIGEN_COPIADO) -> CuadroDibujable:
    """El `Reparto` proyectado sobre las filas del cuadro, listo para dibujar.

    Lo que hace, y en este orden: copia cada etiqueta en su sitio, pone la cifra
    a su derecha si hay cifra, y si no la hay pone una marca que remite a una
    nota con el motivo. Al final añade las notas de lo que no cupo en ninguna
    fila —`C-6`, la conservación de la medida— y los impedimentos.

    **No calcula nada.** Si esta función decidiera un valor, habría dos sitios
    donde se decide qué dice el cuadro.
    """
    valores = {c.campo: c.texto for c in reparto.celdas}
    motivos = {n.campo: n.motivo for n in reparto.no_escritas if n.motivo}

    celdas: List[CeldaDibujable] = []
    notas: List[NotaDelCuadro] = []

    ya_dicho: Dict[str, str] = {}

    def _nota(texto: str) -> str:
        """La marca de una nota, reutilizando la que ya diga eso mismo.

        Las dos terrazas de un cuadro se bloquean por el **mismo** motivo —no se
        sabe cuál de las dos es cuál—, y numerarlo dos veces daría un pie de
        cuadro que repite párrafos palabra por palabra. Un pie que se repite se
        deja de leer, y estas notas son la mitad del valor del entregable.
        """
        if texto in ya_dicho:
            return ya_dicho[texto]
        marca = MARCA_DE_NOTA % (len(notas) + 1)
        notas.append(NotaDelCuadro(marca=marca, texto=texto))
        ya_dicho[texto] = marca
        return marca

    # Las filas del cuadro se desplazan una hacia abajo: la 0 es el título.
    for fila in cuadro.filas:
        celdas.append(CeldaDibujable(fila.fila + 1, max(fila.columna_etiqueta, 0),
                                     fila.etiqueta))
        if not fila.campo:
            continue
        columna_valor = fila.columna_valor if fila.columna_valor >= 0 else \
            max(fila.columna_etiqueta, 0) + 1
        if fila.campo in valores:
            celdas.append(CeldaDibujable(fila.fila + 1, columna_valor,
                                         valores[fila.campo]))
        elif fila.campo in motivos:
            celdas.append(CeldaDibujable(fila.fila + 1, columna_valor,
                                         _nota(motivos[fila.campo])))

    for pieza in reparto.piezas_sin_fila:
        _nota("%s, %s m²: %s" % (pieza.rotulo or "(sin rótulo)",
                                   ("%.2f" % pieza.area_m2).replace(".", ","),
                                   pieza.motivo))
    for impedimento in reparto.impedimentos:
        _nota(impedimento)

    n_filas = 1 + max((c.fila for c in celdas), default=0)
    n_columnas = 1 + max((c.columna for c in celdas), default=1)
    # El título, en la fila 0 y a lo ancho. El cliente la fusiona.
    celdas.insert(0, CeldaDibujable(0, 0, "%s — %s" % (
        TITULO_DEL_CUADRO, reparto.vivienda or "sin vivienda")))

    return CuadroDibujable(
        titulo=TITULO_DEL_CUADRO,
        n_filas=n_filas,
        n_columnas=max(n_columnas, 2),
        celdas=tuple(celdas),
        notas=tuple(notas),
        origen=origen,
    )
