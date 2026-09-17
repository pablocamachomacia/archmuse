# -*- coding: utf-8 -*-
"""La tabla de ArchMuse: una plantilla fija, con las filas que pone el plano.

PRD `docs/prd/2026-09-13-cuadro-plantilla-fija.md`, §4.1-§4.5.

### El cambio, en una frase

Hasta el 2026-09-13 ArchMuse **clonaba** las filas del cuadro del arquitecto y
por eso heredaba sus huecos: filas `pasillo` que el plano no dibuja —y que
acababan en `0,00 m²` (`D-13`)— y `terraza 2` para una sola terraza (`C-5`).
Ahora la tabla **la define ArchMuse** y es la misma en todos los proyectos:

    CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA
    ESPACIOS INTERIORES | SUPERFICIES UTILES INT. | ESPACIOS EXTERIORES | SUPERFICIES UTILES EXT.
    <una fila por estancia medida>
    TOTAL SUP. INTERIOR (m2) | … | TOTAL SUP. EXTERIOR (m2) | …
    TOTAL S. UTIL(m2)
    S. CONSTRUIDA C.
    VIVIENDA TIPO | … | NUMERO UDS: | …

El cuadro del arquitecto ya no entra aquí: sólo sirve para no dibujar encima
(`maquetacion_cuadro`).

### Las reglas, cada una con su dueño

- **Filas = estancias medidas.** Ninguna desaparece (`C-6`): la que no tiene
  fila va a una nota. Ninguna fila sin estancia.
- **Orden fijo por familia, nunca el del plano** (decisión 3): dos proyectos
  del mismo estudio se comparan de un vistazo.
- **Interior o exterior lo decide el arquitecto** cuando ArchMuse no lo sabe:
  una pregunta **por familia** (decisión 4), decidida aquí y mostrada por el
  cliente CAD, que no decide nada.
- **Una celda sin cifra queda vacía** y su motivo va en una nota al pie, fuera
  del marco (decisión 2). Dos celdas con el mismo motivo comparten nota: el
  mecanismo de `C-5`.
- **Ninguna cifra es `0,00 m²`** (`D-13`) y **ninguna cifra que no haya medido
  ArchMuse** (`C-11`).
- **Totales:** `C-2` (un impedimento bloquea los dos) y `C-6` (una pieza sin
  fila también).
- **`NUMERO UDS`: `C-8`** (2026-09-17, `unidades_declaradas`): lo que el plano
  declara junto al rótulo de la vivienda; si no lo declara, vacía con motivo.
- **`TOTAL S. UTIL`: `C-14`, firmado por un arquitecto colegiado el
  2026-09-13**, que deroga la parte de `C-1` que la dejaba vacía: la interior
  más el menor entre la mitad de la exterior y el 10 % de la interior. Si una de
  las dos no se puede afirmar, vacía con su motivo.
- **`S. CONSTRUIDA C.`: `C-12`, FIRMADO el 2026-09-13.** La polilínea que el
  arquitecto rotula «Superficie construida cerrada», de cualquier capa, nunca
  por color. Si el rótulo no identifica una sola, vacía con su motivo
  (`medir_construida`).

**Este módulo no dibuja y no maqueta**: devuelve qué dice cada celda. Dónde y de
qué tamaño, `maquetacion_cuadro`.
"""
from __future__ import annotations

import dataclasses
import itertools
import math
import re
import unicodedata
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from shapely.geometry import Point, Polygon

from . import medicion, unidades_declaradas
from .cuadro_superficies import _normalizar, es_superficie_cero

TITULO = "CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA"
ENCABEZADOS = ("ESPACIOS INTERIORES", "SUPERFICIES UTILES INT.",
               "ESPACIOS EXTERIORES", "SUPERFICIES UTILES EXT.")

#: Decisión 3 de Pablo. *Decisión mía, declarada en el PRD:* «salón» solo va
#: justo detrás de «salón + cocina».
ORDEN_INTERIOR = ("salón + cocina", "salón", "cocina", "pasillo", "distribuidor",
                  "dormitorio", "baño", "aseo", "vestíbulo")
ORDEN_EXTERIOR = ("terraza", "balcón", "porche", "tendedero")

TOTAL_INTERIOR = "TOTAL SUP. INTERIOR (m2)"
TOTAL_EXTERIOR = "TOTAL SUP. EXTERIOR (m2)"
TOTAL_UTIL = "TOTAL S. UTIL(m2)"
CONSTRUIDA = "S. CONSTRUIDA C."
VIVIENDA_TIPO = "VIVIENDA TIPO"
NUMERO_UDS = "NUMERO UDS:"

INTERIOR = medicion.AMBITO_INTERIOR
EXTERIOR = medicion.AMBITO_EXTERIOR

#: Holgura con la que una pieza cuenta como «dentro» de una envolvente: las
#: polilíneas del estudio van a cara de muro y comparten el borde con lo que
#: rodean. Medido sobre `v1plantas.dxf` y `ejemplo.dxf` el 2026-09-13.
TOLERANCIA_CONTENCION_M = 0.05

#: **`C-14`, firmado por un arquitecto colegiado el 2026-09-13**, que deroga la
#: parte de `C-1` que dejaba esta fila vacía: el total útil es la interior más
#: **el menor** de estos dos — la mitad de la exterior, o el 10 % de la interior.
PARTE_DEL_EXTERIOR = Decimal("0.50")
TOPE_SOBRE_EL_INTERIOR = Decimal("0.10")
_CENTESIMA = Decimal("0.01")

#: **`C-12` FIRMADO el 2026-09-13** (Pablo, con el arquitecto): la construida es
#: la polilínea que el arquitecto **rotula**, no la que ArchMuse deduce por su
#: color. Hasta ese día estuvo a `False` —«que lo confirme un arquitecto»— y
#: `medir_construida` elegía por color en la capa de recintos; eso ya no existe.
C12_FIRMADO = True

#: Las dos formas del rótulo que firmó el arquitecto, comparadas sin mayúsculas,
#: sin acentos y con los espacios colapsados. **Exactas**: «superficie construida
#: exterior» y «s. construida ext.» también dicen «construida» y no son esto.
#: Medido el 2026-09-13: la primera en `v1plantas`/`v2s`, la segunda en `ejemplo`
#: y `plantasimple`.
ROTULOS_DE_CONSTRUIDA = ("superficie construida cerrada", "s. construida cerrada")

#: Hasta dónde busca un rótulo su polilínea: **3 alturas de su propio texto**
#: desde el punto de inserción hasta el borde (firmado). Medido el 2026-09-13 con
#: textos de 0,125: el borde de la envolvente a 0,11-0,28 m, y lo siguiente a
#: 0,49 m o más, en `v1plantas` y `ejemplo`.
ALCANCE_EN_ALTURAS = 3

MOTIVO_SIN_ROTULO_DE_CONSTRUIDA = (
    "el plano no rotula ninguna polilínea como «Superficie construida cerrada» ni "
    "«S. construida cerrada», y sin ese rótulo no se escribe (C-12).")
MOTIVO_C12_SIN_FIRMAR = ("no se escribe: medirla sobre la envolvente dibujada es el criterio "
                         "C-12, propuesto y todavía sin confirmar por un arquitecto.")


@dataclass(frozen=True)
class FilaDePieza:
    rotulo: str
    valor: str          # "20,00 m²" o "" (con nota)
    familia: str        # "" si es una familia que ArchMuse no reconoce
    area_m2: float


@dataclass(frozen=True)
class PreguntaDeAmbito:
    """Lo que el cliente CAD pregunta al arquitecto, redactado aquí."""

    familia: str                 # la clave con la que se contesta: "TRASTERO"
    piezas: Tuple[str, ...]
    texto: str


@dataclass(frozen=True)
class PreguntaAlArquitecto:
    """Una pregunta del modo preguntar (PRD 2026-09-17), redactada aquí; el comando la
    enseña, resalta `resaltar` y devuelve `id` con la respuesta."""

    id: str
    tipo: str                    # `respuestas_del_arquitecto.PERTENENCIA`, ...
    contexto: str
    texto: str
    opciones: Tuple[str, ...]
    resaltar: Tuple[str, ...]    # handles del dibujo


@dataclass(frozen=True)
class Construida:
    valor: str
    motivo: Optional[str]
    handle: Optional[str]
    #: Las polilíneas rotuladas que contienen la vivienda. **La cifra sólo existe
    #: si aquí hay exactamente una** (guardián de `C-12`).
    rotuladas: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Plantilla:
    vivienda: str
    interiores: Tuple[FilaDePieza, ...]
    exteriores: Tuple[FilaDePieza, ...]
    cierre: Tuple[Tuple[str, str, str, str], ...]
    notas: Tuple[str, ...]
    preguntas: Tuple[PreguntaDeAmbito, ...]
    sin_fila: Tuple[str, ...]
    impedimentos: Tuple[str, ...]
    construida_handle: Optional[str] = None
    #: Las polilíneas rotuladas que contienen la vivienda: la cifra de la
    #: construida sólo existe si hay exactamente una (`C-12`, condición 3).
    construida_rotuladas: Tuple[str, ...] = ()
    titulo: str = TITULO
    encabezados: Tuple[str, ...] = ENCABEZADOS
    #: Las mismas notas sin aplanar: `((etiquetas, motivo), ...)`.
    notas_por_motivo: Tuple[Tuple[Tuple[str, ...], str], ...] = ()
    #: Las familias que clasificó el arquitecto con su respuesta, no ArchMuse.
    declaradas: Tuple[str, ...] = ()
    #: Modo preguntar (PRD 2026-09-17): lo que hay que preguntarle en esta pasada.
    preguntas_al_arquitecto: Tuple["PreguntaAlArquitecto", ...] = ()
    #: Las respuestas que ha usado esta tabla, listas para guardar (nunca una cifra).
    registros_aplicados: Tuple[dict, ...] = ()
    #: Dónde está el rótulo de la vivienda, en metros: su identidad en las respuestas.
    rotulo_de_la_vivienda: Optional[Tuple[float, float]] = None

    @property
    def filas_de_cuerpo(self) -> int:
        return max(len(self.interiores), len(self.exteriores))

    @property
    def n_filas(self) -> int:
        return 2 + self.filas_de_cuerpo + len(self.cierre)

    n_columnas = 4

    def celdas(self) -> List[Tuple[int, int, str]]:
        """`(fila, columna, texto)` de todo lo que lleva texto. Fila 0: el
        título, que el cliente fusiona a lo ancho."""
        salida: List[Tuple[int, int, str]] = [(0, 0, self.titulo)]
        salida.extend((1, c, t) for c, t in enumerate(self.encabezados))
        for i in range(self.filas_de_cuerpo):
            fila = 2 + i
            for columna, lado in ((0, self.interiores), (2, self.exteriores)):
                if i < len(lado):
                    salida.append((fila, columna, lado[i].rotulo))
                    if lado[i].valor:
                        salida.append((fila, columna + 1, lado[i].valor))
        base = 2 + self.filas_de_cuerpo
        for j, fila_de_cierre in enumerate(self.cierre):
            salida.extend((base + j, c, t) for c, t in enumerate(fila_de_cierre) if t)
        return salida

    @property
    def medicion_limpia(self) -> bool:
        return not self.impedimentos


class _Notas:
    """Notas al pie, **una por motivo**: dos celdas con el mismo motivo
    comparten nota y la nota nombra las dos (el mecanismo de `C-5`)."""

    def __init__(self):
        self._orden: List[str] = []
        self._etiquetas: Dict[str, List[str]] = {}

    def add(self, etiqueta: str, motivo: str) -> None:
        if motivo not in self._etiquetas:
            self._orden.append(motivo)
            self._etiquetas[motivo] = []
        if etiqueta not in self._etiquetas[motivo]:
            self._etiquetas[motivo].append(etiqueta)

    def lineas(self) -> Tuple[str, ...]:
        return tuple("%s: %s" % (", ".join(self._etiquetas[m]), m) for m in self._orden)

    def pares(self) -> Tuple[Tuple[Tuple[str, ...], str], ...]:
        """Lo mismo que `lineas`, sin aplanar: quien lo lea no tiene que partir
        un texto por «: », que también puede aparecer dentro de un motivo."""
        return tuple((tuple(self._etiquetas[m]), m) for m in self._orden)


def _m2(valor: float) -> str:
    return ("%.2f m²" % float(valor)).replace(".", ",")


def superficie_util_total(interior_m2: float, exterior_m2: float) -> Decimal:
    """`C-14`: la interior más el menor entre la mitad de la exterior y el 10 %
    de la interior.

    **Se calcula sobre la interior y la exterior sin redondear** (`C-19`, firmado
    el 2026-09-16, siguiendo al arquitecto): sólo el resultado se redondea, aunque
    a mano no se pueda rehacer exacto con las cifras de la tabla. Hasta ese día se
    calculaba sobre las cifras ya redondeadas. El redondeo es a céntimos **hacia
    arriba en el medio** (`ROUND_HALF_UP`), *decisión declarada*: ni `C-14` ni
    `C-19` dicen cómo se redondea un medio.

    Decimal y no `float`: `58,78 + 3,77` en coma flotante es `62.550000000000004`,
    y un redondeo en el medio no puede depender de eso."""
    interior = Decimal(str(interior_m2))
    exterior = Decimal(str(exterior_m2))
    computable = min(exterior * PARTE_DEL_EXTERIOR, interior * TOPE_SOBRE_EL_INTERIOR)
    return (interior + computable).quantize(_CENTESIMA, rounding=ROUND_HALF_UP)


def _total_util(sumandos: Mapping[str, Optional[float]]) -> Tuple[str, Optional[str]]:
    """La celda de `TOTAL S. UTIL` y, si queda vacía, su motivo.

    **Si la interior o la exterior no se pueden afirmar, el total tampoco**
    (`C-14`): no se calcula sobre una cifra bloqueada, ni poniendo un cero en su
    lugar. Un lado *sin espacios* sí está afirmado y aporta cero."""
    bloqueadas = [lado for lado, ambito in (("interior", INTERIOR), ("exterior", EXTERIOR))
                  if sumandos.get(ambito) is None]
    if len(bloqueadas) == 2:
        return "", ("ni la superficie útil interior ni la exterior se pueden afirmar (ver sus "
                    "notas), y el total no se calcula sobre una cifra bloqueada (C-14).")
    if bloqueadas:
        return "", ("la superficie útil %s no se puede afirmar (ver su nota), y el total no "
                    "se calcula sobre una cifra bloqueada (C-14)." % bloqueadas[0])
    if not sumandos[INTERIOR]:
        return "", ("la vivienda no tiene ningún espacio interior, y sin él no hay superficie "
                    "útil que totalizar (C-14).")
    total = _m2(superficie_util_total(sumandos[INTERIOR], sumandos[EXTERIOR]))
    if es_superficie_cero(total):
        return "", "sus cifras suman cero y eso no es una superficie (D-13)."
    return total, None


def clave_de_familia(rotulo: Optional[str]) -> str:
    """La familia de un rótulo que ArchMuse no reconoce: el rótulo sin números.
    «Trastero», «Trastero 2» y «TRASTERO 3» son la misma pregunta."""
    return " ".join(re.sub(r"[\d\W_]+", " ", _normalizar(rotulo or "")).split())


def _es_nombre(rotulo: Optional[str]) -> bool:
    """¿Nombra algo, o es un código («M», «LD», «PE-01»)? `C-18`: por un código
    nunca se pregunta si es interior o exterior."""
    from .parser import es_nombre_con_sentido

    return es_nombre_con_sentido(rotulo)


def _numero(rotulo: str) -> int:
    encontrado = re.search(r"\d+", rotulo or "")
    return int(encontrado.group()) if encontrado else 0


def _ordenar(filas: List[FilaDePieza], orden: Sequence[str]) -> Tuple[FilaDePieza, ...]:
    def clave(f: FilaDePieza):
        posicion = orden.index(f.familia) if f.familia in orden else len(orden)
        return (posicion, _numero(f.rotulo), _normalizar(f.rotulo), -f.area_m2)
    return tuple(sorted(filas, key=clave))


def _factor_a_metros(plano) -> float:
    """Cuántos metros mide una unidad de dibujo. Los recintos de `PlanoLeido`
    ya están en metros; las polilíneas que se leen de `doc`, no."""
    escala = getattr(plano, "escala", None)
    for nombre in ("factor", "factor_a_metros", "metros_por_unidad"):
        valor = getattr(escala, nombre, None)
        if isinstance(valor, (int, float)) and valor > 0:
            return float(valor)
    return 1.0


def _texto_comparable(texto: Optional[str]) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto or "")
    sin_acentos = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(sin_acentos.lower().split())


@dataclass(frozen=True)
class RotuloDeConstruida:
    handle: str
    punto: Tuple[float, float]        # en metros
    alcance_m: Optional[float]        # `None` si el texto no trae altura


def rotulos_de_construida(doc, factor: float) -> List[RotuloDeConstruida]:
    """Los textos del espacio modelo, de cualquier capa, que dicen una de las
    dos formas firmadas de `ROTULOS_DE_CONSTRUIDA`."""
    from . import parser
    from .geometria_recibida import altura_de_texto, handle_de_origen
    from .propio import es_de_archmuse

    salida: List[RotuloDeConstruida] = []
    for entidad in doc.modelspace().query("TEXT MTEXT"):
        # Lo que dibujó ArchMuse no rotula su construida (2026-09-15, `propio`).
        if es_de_archmuse(entidad):
            continue
        if _texto_comparable(parser._texto_de(entidad)) not in ROTULOS_DE_CONSTRUIDA:
            continue
        punto = parser._punto_de_texto(entidad)
        if punto is None:
            continue
        # Por `altura_de_texto` y no con `dxf.char_height`: en la vía del comando,
        # un texto que llega sin altura se escribe con el 2,5 de ezdxf, y con él
        # este rótulo buscaba su polilínea a 7,50 m —medido el 2026-09-13 en
        # `test_c12_escenarios[sin_altura]`: cuatro candidatas en vez de ninguna—.
        altura = altura_de_texto(entidad)
        alcance = ALCANCE_EN_ALTURAS * altura * factor if altura else None
        salida.append(RotuloDeConstruida(handle_de_origen(entidad),
                                         (punto[0] * factor, punto[1] * factor), alcance))
    return salida


def polilineas_del_plano(doc, factor: float) -> List[Tuple[str, Polygon]]:
    """Las `LWPOLYLINE` del espacio modelo **de cualquier capa**, cerradas —con el
    flag o recuperadas por `_esta_cerrada`, porque el flag está mal puesto en la
    construida de `v1plantas.dxf`—, válidas y con superficie.

    **Sin mirar el color, ni para descartar ni para desempatar** (`C-12`, Pablo:
    «nunca por color, ni como respaldo»)."""
    from . import parser
    from .geometria_recibida import handle_de_origen

    salida: List[Tuple[str, Polygon]] = []
    for entidad in doc.modelspace().query("LWPOLYLINE"):
        if not parser._esta_cerrada(entidad, recuperar_geometria=True):
            continue
        puntos = [(x * factor, y * factor) for x, y in parser._puntos_del_anillo(entidad)]
        if len(puntos) < 3:
            continue
        poligono = Polygon(puntos)
        if poligono.is_valid and poligono.area > 0:
            salida.append((handle_de_origen(entidad), poligono))
    return salida


def _metros(valor: float) -> str:
    return ("%.2f" % valor).replace(".", ",")


def medir_construida(doc, plano, interiores: Sequence, exteriores: Sequence) -> Construida:
    """`C-12`, **FIRMADO el 2026-09-13**: la superficie construida cerrada es la
    polilínea que el arquitecto rotula «Superficie construida cerrada» (o «S.
    construida cerrada»). Es declaración explícita, la lógica de `C-8`.

    Por cada rótulo, **las polilíneas de cualquier capa cuyo borde está a menos
    de 3 alturas de su texto**:

    - **más de una:** ese rótulo no identifica nada. Si alguna toca esta
      vivienda, la fila queda vacía y se dice cuáles eran. **Nunca la más grande
      ni la primera** (condición 1 de Pablo).
    - **una:** es la rotulada, y cuenta para esta vivienda sólo si contiene todas
      sus piezas interiores y ninguna exterior.

    **La cifra sólo sale si hay exactamente una polilínea rotulada que contenga
    la vivienda** y ningún rótulo dudoso que la toque (condición 3). Sin rótulo,
    vacía: **nunca otra polilínea parecida y nunca por color** (condición 2).

    Resultado previsto, medido el 2026-09-13 con la regla escrita antes del
    código: `v1plantas` 73,07 m²; `ejemplo` 5 de 6 (VT6/2 vacía: un rótulo suyo
    cae dentro de la construida exterior y tiene dos polilíneas a su alcance);
    `plantasimple`, `v3s` y `V5` vacías.
    """
    if not interiores:
        return Construida("", "la vivienda no tiene ninguna pieza interior contra la que "
                              "comprobar la polilínea rotulada (C-12).", None)
    factor = _factor_a_metros(plano)
    rotulos = rotulos_de_construida(doc, factor)
    if not rotulos:
        return Construida("", MOTIVO_SIN_ROTULO_DE_CONSTRUIDA, None)
    polilineas = polilineas_del_plano(doc, factor)
    piezas = list(interiores) + list(exteriores)

    def contiene_la_vivienda(poligono) -> bool:
        zona = poligono.buffer(TOLERANCIA_CONTENCION_M)
        return (all(zona.contains(r.polygon) for r in interiores)
                and not any(zona.contains(r.polygon) for r in exteriores))

    def toca_la_vivienda(poligono) -> bool:
        return any(poligono.intersects(r.polygon) for r in piezas)

    rotuladas: Dict[str, float] = {}
    dudosos: List[Tuple[RotuloDeConstruida, List[str]]] = []
    ajenas: List[Tuple[str, str]] = []
    sin_altura: List[str] = []
    for rotulo in rotulos:
        if rotulo.alcance_m is None:
            sin_altura.append(rotulo.handle)
            continue
        punto = Point(rotulo.punto)
        a_su_alcance = [(h, p) for h, p in polilineas
                        if p.exterior.distance(punto) <= rotulo.alcance_m]
        if len(a_su_alcance) > 1:
            if any(toca_la_vivienda(p) for _h, p in a_su_alcance):
                dudosos.append((rotulo, [h for h, _p in a_su_alcance]))
            continue
        if not a_su_alcance:
            continue
        handle, poligono = a_su_alcance[0]
        if contiene_la_vivienda(poligono):
            rotuladas[handle] = poligono.area
        elif toca_la_vivienda(poligono):
            ajenas.append((rotulo.handle, handle))

    nombres = tuple(rotuladas)
    if dudosos:
        rotulo, handles = dudosos[0]
        return Construida("", "el rótulo de la construida (%s) tiene %d polilíneas a menos de "
                              "%s m de su borde (%s): no se elige ninguna (C-12)."
                          % (rotulo.handle, len(handles), _metros(rotulo.alcance_m),
                             ", ".join(handles)), None, nombres)
    if len(rotuladas) > 1:
        return Construida("", "hay %d polilíneas rotuladas como construida cerrada que "
                              "contienen esta vivienda (%s): no se elige ninguna (C-12)."
                          % (len(rotuladas), ", ".join(nombres)), None, nombres)
    if len(rotuladas) == 1:
        handle, area = next(iter(rotuladas.items()))
        if es_superficie_cero(_m2(area)):
            return Construida("", "la polilínea rotulada mide cero: no es una superficie "
                                  "(D-13).", handle, nombres)
        return Construida(_m2(area), None, handle, nombres)
    if ajenas:
        rotulo_h, handle = ajenas[0]
        return Construida("", "el rótulo de la construida (%s) señala la polilínea %s, que no "
                              "contiene todas las piezas interiores de esta vivienda sin "
                              "ninguna exterior (C-12)." % (rotulo_h, handle), None)
    if len(sin_altura) == len(rotulos):
        return Construida("", "el rótulo de la construida (%s) no trae altura de texto, y sin "
                              "ella no se sabe hasta dónde buscar su polilínea (C-12)."
                          % ", ".join(sin_altura), None)
    return Construida("", "hay %d rótulo(s) de construida cerrada en el plano y ninguno está "
                          "a menos de %d alturas de texto de una sola polilínea que contenga "
                          "esta vivienda (C-12)." % (len(rotulos), ALCANCE_EN_ALTURAS), None)


class ViviendaIndistinguible(ValueError):
    """`C-13`: el plano tiene varias viviendas con este rótulo y no se sabe de
    cuál sería la tabla. Es un `ValueError` para que quien ya traduce «este DXF
    no permite el cuadro» a una pregunta lo haga también con esto."""


def _unidades(plano):
    from . import evaluator

    rooms = list(plano.rooms)
    if plano.unit_labels:
        return evaluator.group_rooms_by_unit_label(rooms, list(plano.unit_labels))
    return evaluator.group_rooms_by_proximity(rooms)


def construidas_rotuladas(doc, plano) -> List[Polygon]:
    """Las polilíneas que un rótulo de construida cerrada señala sin duda: la única a
    su alcance (la lectura de `C-12`). En metros."""
    factor = _factor_a_metros(plano)
    polilineas = polilineas_del_plano(doc, factor)
    salida: Dict[str, Polygon] = {}
    for rotulo in rotulos_de_construida(doc, factor):
        if rotulo.alcance_m is None:
            continue
        punto = Point(rotulo.punto)
        al_alcance = [(h, p) for h, p in polilineas if p.exterior.distance(punto) <= rotulo.alcance_m]
        if len(al_alcance) == 1:
            salida[al_alcance[0][0]] = al_alcance[0][1]
    return list(salida.values())


def piezas_de_otra_vivienda(doc, plano, medida, posicion_vivienda: int) -> Dict[int, str]:
    """`{índice de pieza: vivienda}` de las piezas que el reparto da a esta vivienda y
    que el plano atribuye a otra.

    **Regla de Pablo, 2026-09-17, propuesta y pendiente de firma:** si ArchMuse no puede
    demostrar que una cifra es de esa vivienda, no la muestra. **Sin heurísticas
    nuevas:** una construida rotulada es de una vivienda cuando la contiene como pide
    `C-12` —todas sus piezas interiores, ninguna exterior—, contando sólo las piezas de
    reparto firme (las dudosas ya van sin cifra). Si una pieza de esta vivienda está
    dentro de la construida de otra y no de la suya, el plano contradice al reparto:
    la pieza puede ser de la otra.

    Medido en el plano maestro: un aseo con reparto firme (holgura 2,11) dentro de la
    construida rotulada que contiene todas las piezas firmes de la vecina."""
    reparto = _construidas_y_duenas(doc, plano, medida)
    if reparto is None:
        return {}
    unidades, construidas, duenas_de = reparto
    salida: Dict[int, str] = {}
    for k, room in enumerate(unidades[posicion_vivienda].rooms):
        ajenas = []
        for construida, suyas in zip(construidas, duenas_de, strict=True):
            if suyas and construida.buffer(TOLERANCIA_CONTENCION_M).contains(room.polygon):
                if posicion_vivienda in suyas:
                    ajenas = []
                    break
                ajenas.extend(medida.viviendas[i].nombre for i in suyas)
        if ajenas:
            salida[k] = ", ".join(sorted(set(ajenas)))
    return salida


def exteriores_por_contacto(doc, plano, medida, posicion_vivienda: int) -> Dict[int, Set[int]]:
    """`{índice de pieza: posiciones de vivienda}` de las piezas **exteriores de reparto
    dudoso** de esta vivienda, con las viviendas con cuya construida rotulada lindan.

    **`C-21`, firmado por Pablo el 2026-09-17:** una pieza exterior pertenece a la
    vivienda con cuya construida cerrada rotulada comparte borde, o de la que queda
    separada únicamente por la tolerancia geométrica existente
    (`TOLERANCIA_CONTENCION_M`, sin umbral nuevo). Si linda con más de una, queda
    dudosa. Sólo decide cuando el reparto por cercanía es dudoso. La dueña de cada
    construida es la de `C-12`, la misma que usa `piezas_de_otra_vivienda`.

    Medido en el plano maestro: una terraza en franja larga y su tendedero lindan con
    la construida de su vivienda y con ninguna otra."""
    vivienda = medida.viviendas[posicion_vivienda]
    candidatas = [d.indice for d in vivienda.repartos_dudosos
                  if 0 <= d.indice < len(vivienda.piezas)
                  and vivienda.piezas[d.indice].ambito == medicion.AMBITO_EXTERIOR]
    if not candidatas:
        return {}
    reparto = _construidas_y_duenas(doc, plano, medida)
    if reparto is None:
        return {}
    unidades, construidas, duenas_de = reparto
    salida: Dict[int, Set[int]] = {}
    for k in candidatas:
        borde = unidades[posicion_vivienda].rooms[k].polygon.exterior
        salida[k] = {i for construida, suyas in zip(construidas, duenas_de, strict=True)
                     if suyas and borde.intersection(
                         construida.exterior.buffer(TOLERANCIA_CONTENCION_M)).length > 0
                     for i in suyas}
    return salida


#: La última lectura de construidas y dueñas: `(doc, plano, medida, resultado)`. Se
#: calcula una vez por plano y no una por vivienda: medido el 2026-09-17, en el plano
#: grande (52 viviendas, 9.220 polilíneas) rehacerla por vivienda pasaba el servidor de
#: menos de 20 s a 22,3 s.
_ULTIMA_LECTURA: List = []


def _construidas_y_duenas(doc, plano, medida):
    if _ULTIMA_LECTURA and _ULTIMA_LECTURA[0] is doc and _ULTIMA_LECTURA[1] is plano \
            and _ULTIMA_LECTURA[2] is medida:
        return _ULTIMA_LECTURA[3]
    resultado = _calcular_construidas_y_duenas(doc, plano, medida)
    _ULTIMA_LECTURA[:] = [doc, plano, medida, resultado]
    return resultado


def _calcular_construidas_y_duenas(doc, plano, medida):
    construidas = construidas_rotuladas(doc, plano)
    if not construidas:
        return None
    unidades = _unidades(plano)
    if len(unidades) != len(medida.viviendas):
        return None

    def dentro(poligono, construida):
        return construida.buffer(TOLERANCIA_CONTENCION_M).contains(poligono)

    def firmes(i):
        dudosas = {d.indice for d in medida.viviendas[i].repartos_dudosos}
        interiores, exteriores = [], []
        for k, (room, pieza) in enumerate(zip(unidades[i].rooms, medida.viviendas[i].piezas,
                                              strict=True)):
            if k in dudosas:
                continue
            if pieza.ambito == medicion.AMBITO_INTERIOR:
                interiores.append(room.polygon)
            elif pieza.ambito == medicion.AMBITO_EXTERIOR:
                exteriores.append(room.polygon)
        return interiores, exteriores

    piezas_firmes = [firmes(i) for i in range(len(unidades))]

    def duenas(construida):
        return [i for i, (interiores, exteriores) in enumerate(piezas_firmes)
                if interiores and all(dentro(p, construida) for p in interiores)
                and not any(dentro(p, construida) for p in exteriores)]

    return unidades, construidas, [duenas(c) for c in construidas]


#: Los textos del último plano leído para `C-8`: `(doc, textos)`. Una pasada por plano,
#: no una por vivienda (el plano grande tiene 6.280 textos).
_ULTIMOS_TEXTOS: List = []


def numero_de_unidades(doc, plano, posicion_vivienda: int) -> Tuple[str, Optional[str]]:
    """`C-8`: la celda `NUMERO UDS` de la vivienda en esa posición del agrupador, leída
    de lo que el plano declara junto a su rótulo (`unidades_declaradas`)."""
    etiqueta = _etiqueta_de_la_vivienda(plano, posicion_vivienda)
    if etiqueta is None:
        return unidades_declaradas.numero_de_unidades((), "", None)
    texto, x, y = etiqueta
    if not (_ULTIMOS_TEXTOS and _ULTIMOS_TEXTOS[0] is doc and _ULTIMOS_TEXTOS[1] is plano):
        alineados = getattr(plano, "rotulos_alineados", None)
        desplazamiento = (alineados.dx, alineados.dy) if alineados is not None else None
        _ULTIMOS_TEXTOS[:] = [doc, plano, unidades_declaradas.textos_del_plano(doc, desplazamiento)]
    factor = _factor_a_metros(plano)
    return unidades_declaradas.numero_de_unidades(_ULTIMOS_TEXTOS[2], texto,
                                                  (float(x) / factor, float(y) / factor))


#: El último agrupado por rótulo: `(plano, grupos)`.
_ULTIMO_AGRUPADO: List = []


def _agrupado(plano):
    from . import evaluator

    if not (_ULTIMO_AGRUPADO and _ULTIMO_AGRUPADO[0] is plano):
        etiquetas = list(getattr(plano, "unit_labels", None) or [])
        grupos = evaluator.agrupar_por_rotulo(list(plano.rooms), etiquetas) if etiquetas else []
        _ULTIMO_AGRUPADO[:] = [plano, grupos]
    return _ULTIMO_AGRUPADO[1]


def _etiqueta_de_la_vivienda(plano, posicion_vivienda: int) -> Optional[Tuple[str, float, float]]:
    """`(texto, x, y)` en metros del rótulo de la vivienda en esa posición, o `None` si el
    plano no rotula sus viviendas."""
    etiquetas = list(getattr(plano, "unit_labels", None) or [])
    grupos = _agrupado(plano)
    if not etiquetas or not 0 <= posicion_vivienda < len(grupos):
        return None
    texto, x, y = etiquetas[grupos[posicion_vivienda][0]][:3]
    return texto, float(x), float(y)


def _registro_de_pertenencia(handle, vivienda, suya: bool) -> dict:
    from . import respuestas_del_arquitecto as rda

    return {"tipo": rda.PERTENENCIA, "pieza": handle, "vivienda": vivienda.a_dict(),
            "es_suya": bool(suya)}


def _pregunta_de_pertenencia(candidatas, id_pregunta, vivienda, handle, contexto):
    """Apunta la pregunta «¿Esta pieza es de …?» y devuelve lo que necesita la celda."""
    from . import respuestas_del_arquitecto as rda

    if not id_pregunta:
        return None
    candidatas.setdefault(id_pregunta, PreguntaAlArquitecto(
        id=id_pregunta, tipo=rda.PERTENENCIA, contexto=contexto,
        texto="¿Esta pieza es de %s?" % vivienda.nombre, opciones=("Si", "No"),
        resaltar=(handle,)))
    return frozenset([id_pregunta])


#: `(plano, {posición de vivienda: [(recinto, índice del 2.º rótulo, d1, d2)]})`.
_ULTIMAS_DUDAS: List = []


def _dudas_por_distancia(plano):
    """Para cada vivienda, sus piezas cuyo reparto por cercanía no es firme, con el índice
    del segundo rótulo más cercano (el de la otra vivienda posible). Una vez por plano."""
    if _ULTIMAS_DUDAS and _ULTIMAS_DUDAS[0] is plano:
        return _ULTIMAS_DUDAS[1]
    import numpy as np

    etiquetas = list(getattr(plano, "unit_labels", None) or [])
    salida: Dict[int, List] = {}
    if len(etiquetas) >= 2:
        lx = np.array([float(e[1]) for e in etiquetas])
        ly = np.array([float(e[2]) for e in etiquetas])
        for j, (indice, piezas) in enumerate(_agrupado(plano)):
            for room in piezas:
                centro = room.polygon.centroid
                distancias = np.hypot(lx - centro.x, ly - centro.y)
                orden = np.argsort(distancias, kind="stable")
                d1 = float(distancias[indice])
                segundo = next(int(k) for k in orden if int(k) != indice)
                d2 = float(distancias[segundo])
                if d1 > 0 and d2 / d1 < medicion.HOLGURA_MINIMA_DE_REPARTO:
                    salida.setdefault(j, []).append((room, segundo, d1, d2))
    _ULTIMAS_DUDAS[:] = [plano, salida]
    return salida


def _piezas_vecinas_en_duda(plano, medida, posicion_vivienda, vivienda, respuestas):
    """Las piezas de **otras** viviendas cuyo reparto por cercanía no es firme y cuyo segundo
    rótulo más cercano es el de ésta: `(recinto, vecina, contexto, motivo)`, sin las que el
    arquitecto ya ha contestado para esta vivienda.

    **Bloquean los totales de ésta** (regla de Pablo del 2026-09-17 y `C-5`: una ambigüedad
    de reparto no se reparte ni se suma, y es de las dos viviendas). Medido en el banco del
    plano maestro: sin esto, al contestar «Sí» a la única pieza dudosa de una vivienda, sus
    totales salían sin dos piezas que su cuadro le da y que se habían medido con la vecina."""
    grupos = _agrupado(plano)
    if not 0 <= posicion_vivienda < len(grupos):
        return []
    mia = grupos[posicion_vivienda][0]
    salida = []
    for j, dudas in _dudas_por_distancia(plano).items():
        if j == posicion_vivienda:
            continue
        for room, segundo, d1, d2 in dudas:
            if segundo != mia or respuestas.pertenencia(getattr(room, "handle", None),
                                                        vivienda) is not None:
                continue
            nombre = room.label or "(sin rótulo)"
            vecina = medida.viviendas[j].nombre
            salida.append((room, vecina,
                           "«%s» (resaltada) se ha medido con %s, pero está casi igual de cerca del "
                           "rótulo de %s: a %s m del de %s y a %s m del de %s."
                           % (nombre, vecina, vivienda.nombre, _metros(d1), vecina, _metros(d2),
                              vivienda.nombre),
                           "«%s», medida con %s, puede ser de esta vivienda: está a %.2f m de su "
                           "rótulo y a %.2f m del de %s" % (nombre, vecina, d2, d1, vecina)))
    return salida


def _piezas_vecinas_en_mi_construida(doc, plano, medida, posicion_vivienda, vivienda, respuestas):
    """D-11 también para lo que el plano atribuye a esta vivienda: piezas de otra que están
    dentro de la construida rotulada de ésta (la misma lectura de `piezas_de_otra_vivienda`)."""
    reparto = _construidas_y_duenas(doc, plano, medida)
    if reparto is None:
        return []
    unidades, construidas, duenas_de = reparto
    mias = [c.buffer(TOLERANCIA_CONTENCION_M) for c, suyas in zip(construidas, duenas_de, strict=True)
            if suyas == [posicion_vivienda]]
    if not mias:
        return []
    salida = []
    for j, unidad in enumerate(unidades):
        if j == posicion_vivienda:
            continue
        for room in unidad.rooms:
            handle = getattr(room, "handle", None)
            if not handle or respuestas.pertenencia(handle, vivienda) is not None:
                continue
            if any(zona.contains(room.polygon) for zona in mias):
                salida.append((handle, "«%s» (resaltada) se ha medido con %s, pero está dentro de "
                                       "la superficie construida que el plano rotula para %s."
                               % (room.label or "(sin rótulo)", medida.viviendas[j].nombre,
                                  vivienda.nombre)))
    return salida


def _contiene_la_vivienda(poligono, interiores, exteriores) -> bool:
    """La comprobación de `C-12`: todas las piezas interiores dentro y ninguna exterior."""
    zona = poligono.buffer(TOLERANCIA_CONTENCION_M)
    return (all(zona.contains(r.polygon) for r in interiores)
            and not any(zona.contains(r.polygon) for r in exteriores))


def _construida_marcada(doc, plano, deducida: Construida, marcada: str, interiores,
                        exteriores) -> Construida:
    """D-6: la polilínea que él ha marcado como construida, medida y comprobada con `C-12`."""
    factor = _factor_a_metros(plano)
    poligono = next((p for h, p in polilineas_del_plano(doc, factor) if h == marcada), None)
    if poligono is None:
        # No ha llegado (o ya no existe): la respuesta no se aplica y se vuelve a preguntar.
        return deducida
    if deducida.valor and deducida.handle and deducida.handle != marcada:
        return Construida("", "el plano rotula como construida la polilínea %s y la que has marcado "
                              "es %s: no se elige ninguna (C-12)." % (deducida.handle, marcada), None)
    if not interiores or not _contiene_la_vivienda(poligono, interiores, exteriores):
        return Construida("", "la polilínea que has marcado (%s) no contiene todas las piezas "
                              "interiores de esta vivienda sin ninguna exterior: no se escribe "
                              "(C-12)." % marcada, None)
    if es_superficie_cero(_m2(poligono.area)):
        return Construida("", "la polilínea que has marcado mide cero: no es una superficie "
                              "(D-13).", None)
    return Construida(_m2(poligono.area), None, marcada, (marcada,))


def elegir_preguntas(candidatas, necesita, lado_de, bloqueo_comun, vacias_totales,
                     cupo: int) -> Tuple[Tuple[PreguntaAlArquitecto, ...], int]:
    """D-7: el conjunto de hasta `cupo` preguntas que más celdas rellena, si cada respuesta
    es la que completa la tabla. A igualdad, el de menos preguntas; después, el orden en
    que aparecen en la tabla. **La construida se pregunta la última** (D-8): depende de
    qué piezas son de la vivienda, así que sólo se pide cuando no queda ninguna otra
    pregunta que rellene algo. Devuelve `(elegidas, cuántas útiles quedan sin hacer)`.

    `necesita`: `{celda: frozenset(ids) | None}` de las celdas vacías (`None`, ninguna
    respuesta la arregla). `lado_de`: interior o exterior de cada celda de pieza.
    `bloqueo_comun`: lo que bloquea los dos totales (impedimentos de `C-2`)."""
    from . import respuestas_del_arquitecto as rda

    por_id = {p.id: p for p in candidatas}
    ids = [p.id for p in candidatas]
    if not ids:
        return (), 0

    def puntos(conjunto) -> int:
        respondidas = frozenset(conjunto)
        n = 0
        lado_libre = {INTERIOR: True, EXTERIOR: True}
        for celda, requisito in necesita.items():
            resuelta = requisito is not None and requisito <= respondidas
            n += resuelta
            lado = lado_de.get(celda)
            if lado in lado_libre and not resuelta:
                lado_libre[lado] = False
        comun = all(r is not None and r <= respondidas for r in bloqueo_comun)
        libres = {lado: comun and lado_libre[lado] for lado in lado_libre}
        n += bool(vacias_totales.get(TOTAL_INTERIOR)) and libres[INTERIOR]
        n += bool(vacias_totales.get(TOTAL_EXTERIOR)) and libres[EXTERIOR]
        n += bool(vacias_totales.get(TOTAL_UTIL)) and libres[INTERIOR] and libres[EXTERIOR]
        return int(n)

    base = puntos(())

    def mejor(grupo):
        elegido, ganancia = (), 0
        for k in range(1, min(cupo, len(grupo)) + 1):
            for conjunto in itertools.combinations(grupo, k):
                g = puntos(conjunto) - base
                if g > ganancia:
                    elegido, ganancia = conjunto, g
        return elegido, ganancia

    elegido, ganancia = (), 0
    if cupo:
        elegido, ganancia = mejor([i for i in ids if por_id[i].tipo != rda.CONSTRUIDA])
        if not ganancia:
            elegido, ganancia = mejor(ids)
    # Cuántas respuestas más harían falta para rellenar todo lo que se puede rellenar,
    # contadas sin repetir: se añaden de una en una, la que más rellena primero.
    todas, hechas, quedan = puntos(ids), list(elegido), 0
    while puntos(hechas) < todas:
        resto = [i for i in ids if i not in hechas]
        hechas.append(max(resto, key=lambda i: puntos(hechas + [i])))
        quedan += 1
    return tuple(por_id[i] for i in elegido), quedan


def _celdas_vacias(filas, sin_fila, valores_de_total, util_total, construida, unidades) -> int:
    """Las celdas de la tabla que se quedan sin cifra por algo (no un lado sin espacios)."""
    n = sum(1 for lado in filas.values() for f in lado if not f.valor) + len(sin_fila)
    n += sum(1 for ambito in (INTERIOR, EXTERIOR) if not valores_de_total[ambito]
             and filas[ambito])
    n += not util_total
    n += not construida
    n += not unidades
    return int(n)


def _unidad(plano, nombre: str, posicion: Optional[int] = None):
    unidades = _unidades(plano)
    if posicion is not None:
        if 0 <= posicion < len(unidades) and unidades[posicion].name == nombre:
            return unidades[posicion]
        return None
    return next((u for u in unidades if u.name == nombre), None)


def viviendas(plano) -> Tuple[str, ...]:
    return tuple(v.nombre for v in medicion.medir_planta(plano).viviendas)


def construir(doc, plano, nombre_vivienda: str,
              ambitos: Optional[Mapping[str, str]] = None, medida=None,
              posicion: Optional[int] = None, respuestas=None,
              preguntar: bool = False) -> Plantilla:
    """La plantilla de una vivienda. `ambitos` son las respuestas del arquitecto
    a las preguntas de `PreguntaDeAmbito`: `{"TRASTERO": "interior"}`.

    `medida` es la `Medicion` de la planta si ya se ha hecho: en un plano de 25
    viviendas, medirlo una vez por vivienda son 25 mediciones iguales.

    **Modo preguntar** (PRD `docs/prd/2026-09-17-modo-preguntar.md`): `respuestas`
    (`respuestas_del_arquitecto.Respuestas`) son las que ha dado el arquitecto —
    guardadas o de esta pasada— y se aplican antes de escribir nada. Con `preguntar`,
    la plantilla lleva además las preguntas que completarían la tabla, como mucho
    `MAXIMO_DE_PREGUNTAS` por pasada, y la nota de lo que queda si hacen falta más."""
    from . import respuestas_del_arquitecto as rda

    respuestas = respuestas if respuestas is not None else rda.Respuestas()
    if ambitos:
        sueltos = {clave_de_familia(k): str(v).strip().lower() for k, v in ambitos.items()}
        sueltos.update(respuestas.ambitos_sueltos)
        respuestas = dataclasses.replace(respuestas, ambitos_sueltos=sueltos)
    medida = medida if medida is not None else medicion.medir_planta(plano, distinguida=posicion)
    if posicion is not None:
        # **Un clic la ha distinguido por su posición** (enmienda de `C-13`, Pablo,
        # 2026-09-15): se busca por su sitio en el agrupador, no por su nombre, y
        # la medición tiene que haberla medido como distinguida.
        vivienda = (medida.viviendas[posicion]
                    if 0 <= posicion < len(medida.viviendas) else None)
        if vivienda is not None and vivienda.nombre != nombre_vivienda:
            vivienda = None
        if vivienda is not None and vivienda.viviendas_con_el_mismo_rotulo > 1:
            raise ValueError("la medición no distingue la vivienda del clic «%s»: hay que "
                             "medir con `distinguida`" % nombre_vivienda)
    else:
        mismas = [v for v in medida.viviendas if v.nombre == nombre_vivienda]
        if len(mismas) > 1:
            # `C-13`. Coger la primera por nombre —lo que hacía este `next` hasta el
            # 2026-09-13— dibujaría la tabla de una vivienda bajo el rótulo de otra.
            raise ViviendaIndistinguible(medicion.motivo_c13(nombre_vivienda, len(mismas)))
        vivienda = next((v for v in medida.viviendas if v.nombre == nombre_vivienda), None)
    unidad = _unidad(plano, nombre_vivienda, posicion)
    if vivienda is None or unidad is None:
        raise ValueError("no hay ninguna vivienda «%s» en este plano (hay: %s)"
                         % (nombre_vivienda, ", ".join(v.nombre for v in medida.viviendas)))

    notas = _Notas()
    filas: Dict[str, List[FilaDePieza]] = {INTERIOR: [], EXTERIOR: []}
    rooms: Dict[str, List] = {INTERIOR: [], EXTERIOR: []}
    #: El área de cada fila **sin redondear**: de ahí salen los totales (`C-19`).
    crudas: Dict[str, List[float]] = {INTERIOR: [], EXTERIOR: []}
    incompleto = {INTERIOR: False, EXTERIOR: False}
    preguntas: Dict[str, List[str]] = {}
    sin_fila: List[str] = []
    declaradas: List[str] = []
    reclasificadas = []

    # La posición i de las dos listas es el mismo recinto, y eso está decidido, no
    # sale del orden de un `for`: `medicion.medir_planta` construye
    # `piezas = tuple(_pieza(r) for r in unidad.rooms)` con el mismo agrupador de
    # `evaluator` y los mismos `plano.rooms` que `_unidad` aquí. `PiezaMedida` no
    # guarda su `Room`; si algún día los dos agrupados divergen en largo, esto
    # revienta en vez de emparejar una cifra con el recinto de otra.
    posicion_vivienda = next(i for i, v in enumerate(medida.viviendas) if v is vivienda)
    etiqueta = _etiqueta_de_la_vivienda(plano, posicion_vivienda)
    yo = rda.Vivienda(vivienda.nombre, None if etiqueta is None else (float(etiqueta[1]),
                                                                      float(etiqueta[2])))
    originales = list(zip(unidad.rooms, vivienda.piezas, strict=True))
    #: `C-21`: las exteriores de reparto dudoso que lindan con la construida rotulada de
    #: una sola vivienda. Si es ésta, dejan de ser dudosas; si es otra, celda vacía.
    lindantes = exteriores_por_contacto(doc, plano, medida, posicion_vivienda)
    resueltas = {id(originales[k][0]) for k, suyas in lindantes.items()
                 if suyas == {posicion_vivienda}}
    contradichas = {id(originales[k][0]): ", ".join(sorted(medida.viviendas[j].nombre
                                                           for j in suyas))
                    for k, suyas in lindantes.items()
                    if len(suyas) == 1 and posicion_vivienda not in suyas}
    #: Y las que el plano atribuye a otra vivienda con su construida rotulada.
    ajenas = {id(originales[k][0]): otra
              for k, otra in piezas_de_otra_vivienda(doc, plano, medida, posicion_vivienda).items()}

    # **Las respuestas de pertenencia** (D-4, D-5, D-11). «Sí» la deja firme; «No» —o
    # «Sí» a otra vivienda— la saca de la tabla con su nota; una pieza de otra vivienda
    # a la que él ha dicho «Sí» para ésta, entra.
    confirmadas: set = set()
    aplicados: List[dict] = []
    salen: Dict[int, Optional[str]] = {}
    for room, _pieza in originales:
        suya = respuestas.pertenencia(getattr(room, "handle", None), yo)
        if suya is True:
            confirmadas.add(id(room))
        elif suya is False:
            salen[id(room)] = respuestas.de_otra(room.handle, yo)
        if suya is not None:
            aplicados.append(_registro_de_pertenencia(room.handle, yo, suya))
    entran = [room for j, otra in enumerate(_unidades(plano)) if j != posicion_vivienda
              for room in otra.rooms
              if respuestas.pertenencia(getattr(room, "handle", None), yo) is True]
    for room in entran:
        confirmadas.add(id(room))
        aplicados.append(_registro_de_pertenencia(room.handle, yo, True))
    if salen or entran:
        lista = [room for room, _p in originales if id(room) not in salen] + entran
        piezas = tuple(p for room, p in originales if id(room) not in salen) + tuple(
            medicion._pieza(room) for room in entran)
        from shapely.ops import unary_union

        vivienda = dataclasses.replace(
            vivienda, piezas=piezas, solapes=medicion._solapes(lista),
            repartos_dudosos=medicion._repartos_dudosos(
                lista, vivienda.nombre, list(getattr(plano, "unit_labels", None) or [])),
            superficie_por_union_m2=unary_union([r.polygon for r in lista]).area if lista else 0.0,
            suma_cruda_m2=sum(r.polygon.area for r in lista))
        for id_room, otra in salen.items():
            nombre = next(p.nombre for room, p in originales if id(room) == id_room)
            notas.add(nombre, ("es de %s: no va en esta tabla. %s" % (otra, rda.CONFIRMADO)) if otra
                      else "no es de esta vivienda: no va en esta tabla. %s" % rda.CONFIRMADO)
    else:
        lista = [room for room, _p in originales]
    # Firmes por respuesta o por `C-21`: ya no son dudosas, y su impedimento se retira.
    vivienda = dataclasses.replace(vivienda, repartos_dudosos=tuple(
        d for d in vivienda.repartos_dudosos
        if not (0 <= d.indice < len(lista) and id(lista[d.indice]) in confirmadas | resueltas)))
    #: Las piezas cuyo reparto entre viviendas no es firme, por su recinto.
    dudosas = {id(lista[d.indice]): d for d in vivienda.repartos_dudosos if 0 <= d.indice < len(lista)}

    solapadas = {s.una for s in vivienda.solapes} | {s.otra for s in vivienda.solapes}
    #: Para elegir las preguntas (D-7): qué respuestas necesita cada celda vacía para
    #: tener cifra. `None` = ninguna respuesta cerrada la arregla (D-12).
    necesita: Dict[str, Optional[frozenset]] = {}
    lado_de: Dict[str, str] = {}
    candidatas: Dict[str, "PreguntaAlArquitecto"] = {}
    #: Lo que bloquea los dos totales a la vez (los impedimentos de `C-2`).
    bloqueo_comun: List[Optional[frozenset]] = []

    def celda_vacia(etiqueta_celda, ambito, requisito):
        necesita[etiqueta_celda] = requisito
        lado_de[etiqueta_celda] = ambito

    def con_respuesta_pendiente(motivo, id_pregunta):
        return motivo + (" " + rda.SIN_RESPUESTA if id_pregunta in respuestas.sin_respuesta else "")

    for room, pieza in zip(lista, vivienda.piezas, strict=True):
        handle = getattr(room, "handle", None)
        familia, ambito = pieza.familia, pieza.ambito
        #: Los solapes se nombran por el rótulo del plano: si él elige otro nombre, la
        #: pieza sigue siendo la que se solapa.
        nombre_en_el_plano = pieza.nombre
        if pieza.no_es_util:
            bloqueo_comun.append(None)
        conflicto = tuple(getattr(room, "rotulos_en_conflicto", ()) or ())
        if ambito == medicion.AMBITO_SIN_CLASIFICAR and conflicto and not pieza.no_es_util:
            # `C-18` con respuesta: él ha dicho cuál de los nombres es.
            opciones = tuple(sorted(conflicto, key=_normalizar))
            elegido = respuestas.nombre(handle, opciones)
            if elegido is not None:
                familia, ambito = medicion.clasificar(elegido)
                if ambito != medicion.AMBITO_SIN_CLASIFICAR:
                    pieza = dataclasses.replace(pieza, rotulo=elegido)
                    confirmadas.add(id(room))
                    aplicados.append({"tipo": rda.NOMBRE, "pieza": handle, "nombre": elegido})
                else:
                    familia, ambito = pieza.familia, pieza.ambito
        if ambito == medicion.AMBITO_SIN_CLASIFICAR:
            clave = clave_de_familia(pieza.rotulo)
            respuesta = respuestas.ambito(clave) if clave and not conflicto else None
            if respuesta in (INTERIOR, EXTERIOR):
                ambito, familia = respuesta, ""
                confirmadas.add(id(room))
                aplicados.append({"tipo": rda.AMBITO, "familia": clave, "ambito": respuesta})
                if clave not in declaradas:
                    declaradas.append(clave)
            else:
                etiqueta_nota = "%s (%s)" % (pieza.nombre, _m2(pieza.area_m2))
                sin_fila.append(pieza.nombre)
                requisito: Optional[frozenset] = None
                if conflicto:
                    # `C-18`: dos nombres distintos dentro, y no se elige ninguno.
                    id_pregunta = rda.id_nombre(handle) if handle else None
                    notas.add(etiqueta_nota, con_respuesta_pendiente(
                        "tiene dos nombres dentro (%s): no se elige ninguno. Está medida y no "
                        "tiene fila (C-18)." % " y ".join("«%s»" % n for n in conflicto), id_pregunta))
                    if id_pregunta and not pieza.no_es_util:
                        opciones = tuple(sorted(conflicto, key=_normalizar))
                        candidatas.setdefault(id_pregunta, PreguntaAlArquitecto(
                            id=id_pregunta, tipo=rda.NOMBRE,
                            contexto="La pieza resaltada tiene dos nombres dentro: %s."
                                     % " y ".join("«%s»" % n for n in opciones),
                            texto="¿Qué estancia es?", opciones=opciones, resaltar=(handle,)))
                        requisito = frozenset([id_pregunta])
                elif clave and not _es_nombre(pieza.rotulo):
                    # `C-18`: nunca se pregunta por un rótulo sin sentido («M», «LD»).
                    notas.add(etiqueta_nota, "su rótulo «%s» no es un nombre de estancia: no se "
                                             "sabe qué es ni en qué lado va. Está medida y no "
                                             "tiene fila (C-6)." % pieza.nombre)
                elif not clave:
                    notas.add(etiqueta_nota, "no tiene rótulo: no se sabe qué estancia es ni en "
                                             "qué lado del cuadro va. Está medida y no tiene "
                                             "fila (C-6).")
                else:
                    id_pregunta = rda.id_ambito(clave)
                    preguntas.setdefault(clave, []).append(etiqueta_nota)
                    notas.add(etiqueta_nota, con_respuesta_pendiente(
                        "ArchMuse no reconoce «%s» y no sabe si es un espacio interior o "
                        "exterior; sin respuesta no tiene fila (C-6)." % pieza.nombre, id_pregunta))
                    anterior = candidatas.get(id_pregunta)
                    candidatas[id_pregunta] = PreguntaAlArquitecto(
                        id=id_pregunta, tipo=rda.AMBITO,
                        contexto="ArchMuse no reconoce «%s»." % clave.capitalize(),
                        texto="¿Es un espacio interior o exterior?",
                        opciones=("Interior", "Exterior"),
                        resaltar=(anterior.resaltar if anterior else ()) + ((handle,) if handle else ()))
                    requisito = frozenset([id_pregunta])
                celda_vacia("fila:%d" % id(room), None, requisito)
                bloqueo_comun.append(requisito)
                reclasificadas.append(pieza)
                continue
        reclasificadas.append(dataclasses.replace(pieza, familia=familia, ambito=ambito))
        rooms[ambito].append(room)
        crudas[ambito].append(float(room.polygon.area))
        valor = _m2(pieza.area_m2)
        clave_celda = "fila:%d" % id(room)
        if pieza.no_es_util:
            # Regla de Pablo del 2026-09-16: un contorno rotulado como construida
            # nunca es superficie útil; con duda, tampoco. La fila, sin cifra.
            valor = ""
            incompleto[ambito] = True
            notas.add(pieza.nombre, pieza.no_es_util)
            celda_vacia(clave_celda, ambito, None)
        elif id(room) in ajenas and id(room) not in confirmadas:
            valor = ""
            incompleto[ambito] = True
            id_pregunta = rda.id_pertenencia(handle, yo) if handle else None
            notas.add(pieza.nombre, con_respuesta_pendiente(
                "puede ser de %s: está dentro de la superficie construida que el plano rotula "
                "para esa vivienda. No se escribe su superficie." % ajenas[id(room)], id_pregunta))
            celda_vacia(clave_celda, ambito, _pregunta_de_pertenencia(
                candidatas, id_pregunta, yo, handle,
                "«%s» (resaltada) está dentro de la superficie construida que el plano rotula "
                "para %s." % (pieza.nombre, ajenas[id(room)])))
        elif id(room) in contradichas and id(room) not in confirmadas:
            # `C-21`: el borde la da a otra vivienda y la cercanía a ésta.
            valor = ""
            incompleto[ambito] = True
            id_pregunta = rda.id_pertenencia(handle, yo) if handle else None
            notas.add(pieza.nombre, con_respuesta_pendiente(
                "linda con la superficie construida que el plano rotula para %s, pero está más "
                "cerca del rótulo de esta vivienda. No se escribe su superficie."
                % contradichas[id(room)], id_pregunta))
            celda_vacia(clave_celda, ambito, _pregunta_de_pertenencia(
                candidatas, id_pregunta, yo, handle,
                "«%s» (resaltada) linda con la superficie construida que el plano rotula para %s, "
                "pero está más cerca del rótulo de %s." % (pieza.nombre, contradichas[id(room)],
                                                          yo.nombre)))
        elif id(room) in dudosas:
            # Con duda, celda vacía con motivo (decisión propuesta, 2026-09-16): si
            # la pieza es de la vivienda de al lado, su cifra no va en esta tabla.
            duda = dudosas[id(room)]
            valor = ""
            incompleto[ambito] = True
            id_pregunta = rda.id_pertenencia(handle, yo) if handle else None
            notas.add(pieza.nombre, con_respuesta_pendiente(
                "no se sabe si es de esta vivienda o de %s: está a %s m de su rótulo y a %s m "
                "del de %s. No se escribe su superficie." % (
                    duda.siguiente, _metros(duda.distancia_m), _metros(duda.distancia_siguiente_m),
                    duda.siguiente), id_pregunta))
            requisito = _pregunta_de_pertenencia(
                candidatas, id_pregunta, yo, handle,
                "«%s» (resaltada) no se sabe si es de %s o de %s: está a %s m del rótulo de %s y "
                "a %s m del de %s." % (pieza.nombre, yo.nombre, duda.siguiente,
                                       _metros(duda.distancia_m), yo.nombre,
                                       _metros(duda.distancia_siguiente_m), duda.siguiente))
            celda_vacia(clave_celda, ambito, requisito)
        elif es_superficie_cero(valor):
            valor = ""
            incompleto[ambito] = True
            notas.add(pieza.nombre, "su superficie redondea a cero: una estancia no mide cero y su "
                                    "cifra no se escribe (D-13).")
            celda_vacia(clave_celda, ambito, None)
        elif nombre_en_el_plano in solapadas:
            valor = ""
            incompleto[ambito] = True
            notas.add(pieza.nombre, "se solapa con otra pieza dibujada: cuenta metros dos veces "
                                    "y no se escribe su cifra.")
            celda_vacia(clave_celda, ambito, None)
        if id(room) in dudosas:
            # El impedimento de reparto (`C-2`) bloquea los dos totales, aunque la celda la
            # explique otra rama (una pieza dentro de la construida de otra vivienda que
            # además duda por cercanía). Medido en el banco: sin esto, la prioridad elegía
            # preguntas sobre piezas de la vecina antes que la de la propia tabla.
            ident = rda.id_pertenencia(handle, yo) if handle else None
            bloqueo_comun.append(frozenset([ident]) if ident in candidatas else None)
        if valor and id(room) in confirmadas:
            notas.add(pieza.nombre, rda.CONFIRMADO)
        filas[ambito].append(FilaDePieza(pieza.nombre, valor, familia, pieza.area_m2))
    if vivienda.solapes:
        bloqueo_comun.append(None)

    # Piezas de otra vivienda que pueden ser de ésta (D-11). **La duda de reparto por
    # cercanía bloquea también los totales de ésta** (`C-5`): un total que no demuestra
    # que no le falta una pieza no se escribe. Con la respuesta del arquitecto se resuelve.
    vecinas_en_duda = []
    for room, _vecina, contexto, motivo in _piezas_vecinas_en_duda(plano, medida, posicion_vivienda,
                                                                  yo, respuestas):
        handle = getattr(room, "handle", None)
        id_pregunta = rda.id_pertenencia(handle, yo) if handle else None
        requisito = _pregunta_de_pertenencia(candidatas, id_pregunta, yo, handle, contexto)
        celda_vacia("vecina:%d" % id(room), None, requisito)
        bloqueo_comun.append(requisito)
        vecinas_en_duda.append(con_respuesta_pendiente(motivo, id_pregunta or ""))
    # Y las que el plano mete en la construida rotulada de ésta: una respuesta las traería.
    if preguntar:
        for handle, contexto in _piezas_vecinas_en_mi_construida(doc, plano, medida,
                                                                 posicion_vivienda, yo, respuestas):
            id_pregunta = rda.id_pertenencia(handle, yo)
            celda_vacia("vecina:%s" % handle, None, _pregunta_de_pertenencia(
                candidatas, id_pregunta, yo, handle, contexto))

    impedimentos = dataclasses.replace(vivienda, piezas=tuple(reclasificadas)).impedimentos
    impedimentos = tuple(impedimentos) + tuple(vecinas_en_duda)

    valores_de_total = {}
    bloqueados: Dict[str, bool] = {}
    #: Lo que `C-14` puede sumar de cada lado: la cifra que se escribe; `0` si el
    #: lado no tiene ningún espacio; `None` si no se puede afirmar.
    sumandos: Dict[str, Optional[float]] = {}
    for ambito, etiqueta_total in ((INTERIOR, TOTAL_INTERIOR), (EXTERIOR, TOTAL_EXTERIOR)):
        total = ""
        sumandos[ambito] = None
        if impedimentos:
            motivo = "no se escribe: %s (C-2)." % "; ".join(impedimentos)
        elif incompleto[ambito]:
            motivo = "alguna fila de este lado no lleva cifra, y un total sin ella sería falso."
        elif not filas[ambito]:
            # Sin escribir la cifra: una nota que dice «0,00 m²» se lee en el plano
            # como el mismo cero que `D-13` prohíbe en las celdas.
            motivo = ("no hay ningún espacio de este lado, y un total vacío no se escribe "
                      "como cero (D-13).")
            # Vacío en la tabla, pero afirmado: un lado sin espacios no aporta
            # nada al total útil (`C-14`, «sin exterior: 100 → 100»).
            sumandos[ambito] = 0.0
        else:
            motivo = None
            # `C-19`: la suma de las áreas sin redondear; sólo el resultado va a
            # céntimos. A mano la columna puede no cuadrar por un céntimo.
            cruda = sum(crudas[ambito])
            total = _m2(Decimal(repr(cruda)).quantize(_CENTESIMA, rounding=ROUND_HALF_UP))
            if es_superficie_cero(total):
                motivo, total = "sus cifras suman cero y eso no es una superficie (D-13).", ""
            else:
                sumandos[ambito] = cruda
        if motivo:
            notas.add(etiqueta_total, motivo)
            valores_de_total[ambito] = ""
        else:
            valores_de_total[ambito] = total
        #: Vacío porque algo lo bloquea, no porque el lado no tenga espacios.
        bloqueados[etiqueta_total] = bool(impedimentos or incompleto[ambito])

    construida = medir_construida(doc, plano, rooms[INTERIOR], rooms[EXTERIOR]) \
        if C12_FIRMADO else Construida("", MOTIVO_C12_SIN_FIRMAR, None)
    marcada = respuestas.construida(yo)
    id_construida = rda.id_construida(yo)
    if marcada and C12_FIRMADO:
        construida = _construida_marcada(doc, plano, construida, marcada, rooms[INTERIOR],
                                         rooms[EXTERIOR])
        if construida.handle == marcada and construida.valor:
            aplicados.append({"tipo": rda.CONSTRUIDA, "vivienda": yo.a_dict(), "polilinea": marcada})
    util_total, motivo_util_total = _total_util(sumandos)
    if motivo_util_total:
        notas.add(TOTAL_UTIL, motivo_util_total)
    if construida.motivo:
        notas.add(CONSTRUIDA, con_respuesta_pendiente(construida.motivo, id_construida))
        if not rooms[INTERIOR] or es_superficie_cero(construida.valor or "") or                 "mide cero" in construida.motivo:
            necesita[CONSTRUIDA] = None
        else:
            necesita[CONSTRUIDA] = frozenset([id_construida])
            candidatas.setdefault(id_construida, PreguntaAlArquitecto(
                id=id_construida, tipo=rda.CONSTRUIDA,
                contexto="El plano no identifica una sola polilínea como superficie construida "
                         "cerrada de %s." % yo.nombre,
                texto="Haz clic en la polilínea de superficie construida de %s" % yo.nombre,
                opciones=(), resaltar=()))
    elif marcada and construida.handle == marcada:
        notas.add(CONSTRUIDA, rda.CONFIRMADO)
    unidades, motivo_unidades = numero_de_unidades(doc, plano, posicion_vivienda)
    if motivo_unidades:
        notas.add(NUMERO_UDS.rstrip(":"), motivo_unidades)

    # **Qué preguntar** (D-7, D-8): el conjunto de hasta el cupo que más celdas rellena.
    elegidas: Tuple["PreguntaAlArquitecto", ...] = ()
    if preguntar:
        cupo = max(0, rda.MAXIMO_DE_PREGUNTAS - respuestas.preguntas_hechas)
        disponibles = [p for i, p in candidatas.items()
                       if i not in respuestas.sin_respuesta and i not in respuestas.respondidas]
        vacias_totales = {TOTAL_INTERIOR: bloqueados[TOTAL_INTERIOR],
                          TOTAL_EXTERIOR: bloqueados[TOTAL_EXTERIOR],
                          TOTAL_UTIL: not util_total and (bloqueados[TOTAL_INTERIOR]
                                                          or bloqueados[TOTAL_EXTERIOR])}
        elegidas, pendientes = elegir_preguntas(disponibles, necesita, lado_de, bloqueo_comun,
                                                vacias_totales, cupo)
        vacias = _celdas_vacias(filas, sin_fila, valores_de_total, util_total, construida.valor,
                                unidades)
        if pendientes and not elegidas and vacias:
            notas.add("Preguntas", "harían falta %d respuesta(s) más del arquitecto y ArchMuse "
                                   "pregunta como mucho %d cosas por vivienda: quedan %d celda(s) "
                                   "vacía(s) en la tabla." % (pendientes, rda.MAXIMO_DE_PREGUNTAS,
                                                              vacias))

    cierre = (
        (TOTAL_INTERIOR, valores_de_total[INTERIOR], TOTAL_EXTERIOR, valores_de_total[EXTERIOR]),
        (TOTAL_UTIL, util_total, "", ""),
        (CONSTRUIDA, construida.valor, "", ""),
        (VIVIENDA_TIPO, unidades_declaradas.sin_unidades(vivienda.nombre), NUMERO_UDS, unidades),
    )

    return Plantilla(
        vivienda=vivienda.nombre,
        interiores=_ordenar(filas[INTERIOR], ORDEN_INTERIOR),
        exteriores=_ordenar(filas[EXTERIOR], ORDEN_EXTERIOR),
        cierre=cierre,
        notas=notas.lineas(),
        preguntas=tuple(
            PreguntaDeAmbito(
                familia=clave, piezas=tuple(piezas),
                texto=("ArchMuse no reconoce «%s» (%s). ¿Es un espacio interior o exterior?"
                       % (clave.capitalize(), ", ".join(piezas))))
            for clave, piezas in preguntas.items()),
        sin_fila=tuple(sin_fila),
        impedimentos=tuple(impedimentos),
        construida_handle=construida.handle,
        construida_rotuladas=construida.rotuladas,
        notas_por_motivo=notas.pares(),
        declaradas=tuple(declaradas),
        preguntas_al_arquitecto=elegidas,
        registros_aplicados=tuple(aplicados),
        rotulo_de_la_vivienda=yo.rotulo,
    )


#: Lo que se dibuja bajo la tabla (Pablo, 2026-09-15, tras verlo en el maestro:
#: «demasiado texto y mal presentado»). Como mucho `MAX_NOTAS_EN_EL_DIBUJO` líneas;
#: el detalle, a la línea de comandos y al registro.
MAX_NOTAS_EN_EL_DIBUJO = 4

#: `(patrón del motivo, singular, plural)` de las notas que hablan de piezas: se
#: cuentan las piezas y se dicen en una línea.
_NOTAS_DE_PIEZAS = (
    (re.compile(r"no tiene rótulo|no es un nombre de estancia|no reconoce"),
     "%d pieza sin nombre reconocible", "%d piezas sin nombre reconocible"),
    (re.compile(r"dos nombres dentro"), "%d pieza con dos nombres", "%d piezas con dos nombres"),
    (re.compile(r"se solapa"), "%d pieza dibujada dos veces", "%d piezas dibujadas dos veces"),
    (re.compile(r"redondea a cero"), "%d pieza sin superficie", "%d piezas sin superficie"),
)


def notas_del_dibujo(plantilla: "Plantilla") -> Tuple[str, ...]:
    """Las notas **del plano**: cortas, en lenguaje de arquitecto, agrupadas por
    motivo y como mucho `MAX_NOTAS_EN_EL_DIBUJO` líneas. Ni un criterio (`C-…`),
    ni un handle, ni un nombre de pieza: eso es el detalle, y va a la línea de
    comandos y al registro con `plantilla.notas`."""
    from .respuestas_del_arquitecto import CONFIRMADO

    piezas = [0] * len(_NOTAS_DE_PIEZAS)
    totales = construida = unidades = False
    confirmados = 0
    lados_vacios: List[str] = []
    otros = 0
    for etiquetas, motivo in plantilla.notas_por_motivo:
        if motivo == CONFIRMADO:
            # Trazabilidad (Pablo, 2026-09-17): siempre en el dibujo, y la primera.
            confirmados += len(etiquetas)
            continue
        if motivo.endswith(CONFIRMADO):
            # Piezas que él ha dicho que no son de esta vivienda: no son una celda.
            continue
        for i, (patron, _uno, _varios) in enumerate(_NOTAS_DE_PIEZAS):
            if patron.search(motivo):
                piezas[i] += len(etiquetas)
                break
        else:
            for etiqueta in etiquetas:
                if etiqueta in (TOTAL_INTERIOR, TOTAL_EXTERIOR) and "ningún espacio" in motivo:
                    lados_vacios.append("exteriores" if etiqueta == TOTAL_EXTERIOR else "interiores")
                elif etiqueta in (TOTAL_INTERIOR, TOTAL_EXTERIOR, TOTAL_UTIL):
                    totales = True
                elif etiqueta == CONSTRUIDA:
                    construida = True
                elif etiqueta == NUMERO_UDS.rstrip(":"):
                    unidades = True
                else:
                    otros += 1
    lineas: List[str] = []
    if confirmados:
        lineas.append("Confirmado por el arquitecto: %d dato%s" % (confirmados,
                                                                "" if confirmados == 1 else "s"))
    for cuenta, (_patron, uno, varios) in zip(piezas, _NOTAS_DE_PIEZAS, strict=True):
        if cuenta:
            lineas.append((uno if cuenta == 1 else varios) % cuenta)
    if totales:
        lineas.append("Totales sin cifra")
    if construida:
        lineas.append("Construida sin cifra")
    for lado in lados_vacios:
        lineas.append("Sin espacios %s" % lado)
    if unidades:
        lineas.append("Nº de unidades: a mano")
    if otros:
        lineas.append("%d aviso%s más" % (otros, "" if otros == 1 else "s"))
    if len(lineas) > MAX_NOTAS_EN_EL_DIBUJO:
        resto = len(lineas) - (MAX_NOTAS_EN_EL_DIBUJO - 1)
        lineas = lineas[:MAX_NOTAS_EN_EL_DIBUJO - 1] + [
            "y %d aviso%s más en la línea de comandos" % (resto, "" if resto == 1 else "s")]
    return tuple(lineas)


def a_dict(plantilla: Plantilla) -> dict:
    """La plantilla en tipos simples, para el cliente CAD y la web."""
    return {
        "vivienda": plantilla.vivienda,
        "titulo": plantilla.titulo,
        "n_filas": plantilla.n_filas,
        "n_columnas": plantilla.n_columnas,
        "filas_totales": plantilla.n_filas,
        "celdas": [{"fila": f, "columna": c, "texto": t} for f, c, t in plantilla.celdas()],
        "notas": [{"texto": n, "linea": n} for n in plantilla.notas],
        # Lo que va en el plano; `notas`, el detalle para la línea de comandos.
        "notas_del_dibujo": list(notas_del_dibujo(plantilla)),
        "preguntas_de_ambito": [
            {"familia": p.familia, "texto": p.texto, "piezas": list(p.piezas)}
            for p in plantilla.preguntas],
        "sin_fila": list(plantilla.sin_fila),
        "medicion_limpia": plantilla.medicion_limpia,
        "impedimentos": list(plantilla.impedimentos),
        "construida_handle": plantilla.construida_handle,
        "declaradas": list(plantilla.declaradas),
        # Modo preguntar (PRD 2026-09-17).
        "preguntas_al_arquitecto": [
            {"id": p.id, "tipo": p.tipo, "contexto": p.contexto, "texto": p.texto,
             "opciones": list(p.opciones), "resaltar": list(p.resaltar)}
            for p in plantilla.preguntas_al_arquitecto],
        "confirmadas_por_el_arquitecto": [
            etiqueta for etiquetas, motivo in plantilla.notas_por_motivo
            if motivo == "Confirmado por el arquitecto." for etiqueta in etiquetas],
    }
