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
  fila también). `NUMERO UDS` vacía: el plano lo declara y leerlo es `C-8`, sin
  implementar.
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
import re
import unicodedata
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from shapely.geometry import Point, Polygon

from . import medicion
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
MOTIVO_NUMERO_UDS = ("el plano lo declara, pero leer lo que el plano declara (C-8) "
                     "no está implementado todavía: se escribe a mano.")

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

    **Se calcula sobre las dos cifras que escribe la tabla**, ya redondeadas a
    céntimos, no sobre la suma sin redondear: así quien la lea puede rehacerla a
    mano con lo que tiene delante y le sale lo mismo. El resultado se redondea a
    céntimos **hacia arriba en el medio** (`ROUND_HALF_UP`): la mitad de una
    exterior impar deja un tercer decimal (7,55 → 3,775). *Las dos cosas son
    decisión mía, declarada y sin firmar*; `C-14` no dice nada del redondeo.

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

    salida: List[RotuloDeConstruida] = []
    for entidad in doc.modelspace().query("TEXT MTEXT"):
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
        puntos = [(x * factor, y * factor) for x, y in parser._polyline_points(entidad)]
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


def _unidad(plano, nombre: str):
    from . import evaluator

    rooms = list(plano.rooms)
    if plano.unit_labels:
        unidades = evaluator.group_rooms_by_unit_label(rooms, list(plano.unit_labels))
    else:
        unidades = evaluator.group_rooms_by_proximity(rooms)
    return next((u for u in unidades if u.name == nombre), None)


def viviendas(plano) -> Tuple[str, ...]:
    return tuple(v.nombre for v in medicion.medir_planta(plano).viviendas)


def construir(doc, plano, nombre_vivienda: str,
              ambitos: Optional[Mapping[str, str]] = None, medida=None) -> Plantilla:
    """La plantilla de una vivienda. `ambitos` son las respuestas del arquitecto
    a las preguntas de `PreguntaDeAmbito`: `{"TRASTERO": "interior"}`.

    `medida` es la `Medicion` de la planta si ya se ha hecho: en un plano de 25
    viviendas, medirlo una vez por vivienda son 25 mediciones iguales."""
    respuestas = {clave_de_familia(k): str(v).strip().lower()
                  for k, v in (ambitos or {}).items()}
    medida = medida if medida is not None else medicion.medir_planta(plano)
    mismas = [v for v in medida.viviendas if v.nombre == nombre_vivienda]
    if len(mismas) > 1:
        # `C-13`. Coger la primera por nombre —lo que hacía este `next` hasta el
        # 2026-09-13— dibujaría la tabla de una vivienda bajo el rótulo de otra.
        raise ViviendaIndistinguible(medicion.motivo_c13(nombre_vivienda, len(mismas)))
    vivienda = next((v for v in medida.viviendas if v.nombre == nombre_vivienda), None)
    unidad = _unidad(plano, nombre_vivienda)
    if vivienda is None or unidad is None:
        raise ValueError("no hay ninguna vivienda «%s» en este plano (hay: %s)"
                         % (nombre_vivienda, ", ".join(v.nombre for v in medida.viviendas)))

    solapadas = {s.una for s in vivienda.solapes} | {s.otra for s in vivienda.solapes}
    notas = _Notas()
    filas: Dict[str, List[FilaDePieza]] = {INTERIOR: [], EXTERIOR: []}
    rooms: Dict[str, List] = {INTERIOR: [], EXTERIOR: []}
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
    for room, pieza in zip(unidad.rooms, vivienda.piezas, strict=True):
        familia, ambito = pieza.familia, pieza.ambito
        if ambito == medicion.AMBITO_SIN_CLASIFICAR:
            clave = clave_de_familia(pieza.rotulo)
            respuesta = respuestas.get(clave) if clave else None
            if respuesta in (INTERIOR, EXTERIOR):
                ambito, familia = respuesta, ""
                if clave not in declaradas:
                    declaradas.append(clave)
            else:
                etiqueta = "%s (%s)" % (pieza.nombre, _m2(pieza.area_m2))
                sin_fila.append(pieza.nombre)
                if not clave:
                    notas.add(etiqueta, "no tiene rótulo: no se sabe qué estancia es ni en "
                                        "qué lado del cuadro va. Está medida y no tiene fila (C-6).")
                else:
                    preguntas.setdefault(clave, []).append(etiqueta)
                    notas.add(etiqueta, "ArchMuse no reconoce «%s» y no sabe si es un espacio "
                                        "interior o exterior; sin respuesta no tiene fila (C-6)."
                              % pieza.nombre)
                reclasificadas.append(pieza)
                continue
        reclasificadas.append(dataclasses.replace(pieza, familia=familia, ambito=ambito))
        rooms[ambito].append(room)
        valor = _m2(pieza.area_m2)
        if es_superficie_cero(valor):
            valor = ""
            incompleto[ambito] = True
            notas.add(pieza.nombre, "su superficie redondea a cero: una estancia no mide cero y su "
                                    "cifra no se escribe (D-13).")
        elif pieza.nombre in solapadas:
            valor = ""
            incompleto[ambito] = True
            notas.add(pieza.nombre, "se solapa con otra pieza dibujada: cuenta metros dos veces "
                                    "y no se escribe su cifra.")
        filas[ambito].append(FilaDePieza(pieza.nombre, valor, familia, pieza.area_m2))

    impedimentos = dataclasses.replace(vivienda, piezas=tuple(reclasificadas)).impedimentos

    valores_de_total = {}
    #: Lo que `C-14` puede sumar de cada lado: la cifra que se escribe; `0` si el
    #: lado no tiene ningún espacio; `None` si no se puede afirmar.
    sumandos: Dict[str, Optional[float]] = {}
    for ambito, etiqueta in ((INTERIOR, TOTAL_INTERIOR), (EXTERIOR, TOTAL_EXTERIOR)):
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
            cifra = round(sum(f.area_m2 for f in filas[ambito]), 2)
            total = _m2(cifra)
            if es_superficie_cero(total):
                motivo, total = "sus cifras suman cero y eso no es una superficie (D-13).", ""
            else:
                sumandos[ambito] = cifra
        if motivo:
            notas.add(etiqueta, motivo)
            valores_de_total[ambito] = ""
        else:
            valores_de_total[ambito] = total

    if C12_FIRMADO:
        construida = medir_construida(doc, plano, rooms[INTERIOR], rooms[EXTERIOR])
    else:
        construida = Construida("", MOTIVO_C12_SIN_FIRMAR, None)
    util_total, motivo_util_total = _total_util(sumandos)
    if motivo_util_total:
        notas.add(TOTAL_UTIL, motivo_util_total)
    if construida.motivo:
        notas.add(CONSTRUIDA, construida.motivo)
    notas.add(NUMERO_UDS.rstrip(":"), MOTIVO_NUMERO_UDS)

    cierre = (
        (TOTAL_INTERIOR, valores_de_total[INTERIOR], TOTAL_EXTERIOR, valores_de_total[EXTERIOR]),
        (TOTAL_UTIL, util_total, "", ""),
        (CONSTRUIDA, construida.valor, "", ""),
        (VIVIENDA_TIPO, vivienda.nombre, NUMERO_UDS, ""),
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
    )


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
        "preguntas_de_ambito": [
            {"familia": p.familia, "texto": p.texto, "piezas": list(p.piezas)}
            for p in plantilla.preguntas],
        "sin_fila": list(plantilla.sin_fila),
        "medicion_limpia": plantilla.medicion_limpia,
        "impedimentos": list(plantilla.impedimentos),
        "construida_handle": plantilla.construida_handle,
        "declaradas": list(plantilla.declaradas),
    }
