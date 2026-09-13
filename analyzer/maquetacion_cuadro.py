# -*- coding: utf-8 -*-
"""`D-14` · Dónde y de qué tamaño se dibuja la tabla de ArchMuse.

PRD `docs/prd/2026-09-13-cuadro-plantilla-fija.md`, §4.6.

**El fallo que cierra, verificado en AutoCAD 2027 el 2026-09-13.** La tabla salió
con el texto varias veces más alto que el edificio y columnas tan estrechas que
partían las palabras letra a letra. `am:dibujar-cuadro` creaba la tabla con fila
1,0 y columna 14,0 fijas y sin fijar la altura de texto: **el tamaño era criterio
y vivía en LISP**. Ahora vive aquí, y el cliente CAD dibuja lo que se le da.

### Las tres reglas firmadas por Pablo

1. **La ventana manda.** El arquitecto marca dos esquinas y eso es una
   declaración (misma lógica que `C-8`). La tabla se dibuja **dentro**, con la
   mayor altura de texto con la que ella y sus notas caben.
2. **No se encoge hasta lo ilegible ni se desborda.** Si con la altura mínima
   legible no cabe, se devuelve `NoCabe` con el tamaño que haría falta.
3. **La altura mínima no es una constante:** la del texto del cuadro del
   arquitecto si lo hay; si no, la de los rótulos de estancia del propio plano
   (`altura_minima`). Medido el 2026-09-13 en los seis planos: rótulos 0,125 y
   cuadro 0,09.

### Ninguna palabra se parte, nunca

Una celda de tabla de AutoCAD parte el texto cuando no cabe en su ancho. Por eso
**cada columna es tan ancha como el texto más ancho que lleva**, medido con la
fuente real (`ezdxf.fonts`, `FUENTE`), más su margen. Y para que lo medido y lo
dibujado sean lo mismo, el cliente crea y aplica el estilo de texto
`ESTILO_DE_TEXTO` con esa misma fuente. `HOLGURA_DE_ANCHO` cubre la diferencia
entre el motor de `ezdxf` y el de AutoCAD: **sin verificar en AutoCAD**.

### Lo que NO son constantes de tamaño, y por qué

Las proporciones de abajo (`MARGEN`, `ALTO_DE_FILA`, …) no dicen de qué tamaño
es nada: dicen **cuántas alturas de texto** mide un margen o una fila. Una tabla
se escala entera con su texto, y eso es lo que hace que la misma plantilla sea
legible en un plano en metros y en uno en milímetros.

Este módulo no decide **qué** dice la tabla —eso es `plantilla_cuadro`— ni la
dibuja: devuelve números. No importa nada del proyecto.
"""
from __future__ import annotations

import functools
import statistics
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

#: La fuente con la que se mide cuando nadie ha medido: la exportación web, que
#: escribe un DXF sin AutoCAD delante. **El comando ya no la usa** (`.lsp` 3.5.0).
FUENTE = "arial.ttf"
#: El estilo de texto de la tabla en la exportación web. El comando dibuja con
#: un estilo que ya existe en el plano (`estilo_de_texto`) y no crea ninguno.
ESTILO_DE_TEXTO = "ARCHMUSE"

#: Holgura sobre la medida de AutoCAD (`textbox`): cubre que una línea de nota
#: se mida como sus palabras más sus espacios, y lo que pueda diferir un TEXT
#: medido de un MTEXT dentro de una casilla. **Sin verificar en AutoCAD.**
HOLGURA_DE_MEDIDA = 1.05
#: Lo que se mide para saber el ancho de un espacio: «x x» menos «xx».
TEXTOS_PARA_EL_ESPACIO = ("xx", "x x")

MOTIVO_SIN_ESTILO = (
    "el plano no tiene ni cuadro de superficies ni rótulos de estancia de los que "
    "sacar el estilo de texto de la tabla, y ArchMuse no inventa una fuente: no la "
    "dibujo.")

#: Margen a cada lado del texto dentro de su celda, en alturas de texto.
MARGEN = 0.5
#: Alto de una fila, en alturas de texto. **Medido** el 2026-09-13 en los cuadros
#: que dibuja el arquitecto (`ejemplo`, `v1plantas`, `v2s`, `v3s`, la misma
#: plantilla): 0,18 de fila para 0,09 de texto, exactamente 2,0.
ALTO_DE_FILA = 2.0
#: El título, más grande que el cuerpo: 0,12 frente a 0,09 en sus cuadros.
ESCALA_DEL_TITULO = 0.12 / 0.09
#: Y su fila, más alta: 0,22 frente a 0,09.
ALTO_DE_FILA_DEL_TITULO = 0.22 / 0.09
#: Margen por encima y por debajo del texto en su celda, en alturas de texto.
#:
#: **Es lo que impide que AutoCAD agrande las filas.** Una fila de tabla no mide
#: menos que su texto más los dos márgenes (regla de AutoCAD, **sin verificar en
#: AutoCAD**), así que con 0,25 la del cuerpo pide 1 + 0,5 = 1,5 y la del título
#: 1,33 + 0,5 = 1,83, y caben en las que se piden (2,0 y 2,44). Hasta el
#: 2026-09-13 no se fijaba y la tabla heredaba el estilo `Standard` del plano
#: —margen vertical 1,5 y texto 4,5, medidos en `v1plantas.dxf`—: filas decenas de
#: veces más altas de lo calculado y las notas encima de la cabecera.
MARGEN_VERTICAL = 0.25
#: El estilo de tabla que el cliente crea con esos márgenes y alturas, para no
#: depender del que tenga activo cada plano.
ESTILO_DE_TABLA = "ARCHMUSE"
#: La capa de la tabla y sus notas: suya, distinta de las del arquitecto, que la
#: apaga o la borra sin tocar nada de lo que él dibujó.
CAPA = "ARCHMUSE - CUADRO"
#: 7 = blanco o negro según el fondo: el color con el que se leen los textos del
#: cuadro del arquitecto (capa 0, PorCapa). La tabla y las notas van PorCapa y
#: dejan de heredar el color activo del dibujo (amarillo en `v1plantas.dxf`).
COLOR_DE_CAPA = 7
#: Lo que se ensancha la medida de `ezdxf` para cubrir la diferencia con el
#: motor de texto de AutoCAD. Riesgo declarado en el PRD, §9.
HOLGURA_DE_ANCHO = 1.15
#: Separación entre el borde inferior de la tabla y la primera nota.
SEPARACION_DE_NOTAS = 1.0
#: Distancia entre dos líneas de nota, en alturas de texto.
INTERLINEA_DE_NOTAS = 1.6

_TOLERANCIA = 1e-9

Punto = Tuple[float, float]
Caja = Tuple[Punto, Punto]


@functools.lru_cache(maxsize=1)
def _fuente():
    from ezdxf.fonts import fonts

    return fonts.make_font(FUENTE, cap_height=1.0)


def ancho_de_texto(texto: str, altura: float) -> float:
    """Lo que ocupa `texto` escrito a `altura`, con la holgura incluida."""
    if not texto:
        return 0.0
    return _fuente().text_width(texto) * altura * HOLGURA_DE_ANCHO


class MedidaIncompleta(ValueError):
    """Falta la medida de algún texto que hay que colocar: no se maqueta a ojo."""


def estilo_de_texto(estilos_de_cuadro: Sequence[str],
                    estilos_de_rotulos: Sequence[str]) -> Optional[str]:
    """Con qué estilo de texto del plano se dibuja la tabla (`.lsp` 3.5.0).

    **El de su cuadro de superficies; si no tiene, el de sus rótulos de estancia;
    y si no hay ninguno, `None`** —y la tabla no se dibuja—. En cada grupo, el
    más repetido; a igualdad, el primero que aparece. No hay estilo de reserva:
    elegir una fuente que el plano no usa sería inventarla (Pablo, 2026-09-13).
    """
    for candidatos in (estilos_de_cuadro, estilos_de_rotulos):
        validos = [str(e).strip() for e in candidatos or () if str(e or "").strip()]
        if validos:
            cuenta = {e: validos.count(e) for e in validos}
            return max(cuenta, key=lambda e: (cuenta[e], -validos.index(e)))
    return None


def estilos_de_rotulos(doc, rotulos: Sequence[str]) -> List[str]:
    """Los estilos de texto de los textos del plano que nombran una estancia
    medida, uno por texto. Vacío sólo si el plano no tiene rótulos de estancia.

    **`dxf.style` y no `dxf.get("style")`** — medido el 2026-09-13 sobre el DXF
    materializado del fixture: ezdxf no escribe el código 7 cuando vale
    «Standard», así que al leer `get` da `None` y `hasattr` da falso. Un TEXT o
    MTEXT sin código 7 usa «Standard» en AutoCAD, y el `.lsp` manda exactamente
    eso cuando no lo trae: leer el valor por defecto es leer lo que el plano
    tiene, no inventar una fuente.
    """
    from . import parser

    buscados = {(r or "").strip() for r in rotulos if r}
    estilos: List[str] = []
    for entidad in doc.modelspace().query("MTEXT TEXT"):
        if (parser._texto_de(entidad) or "").strip() not in buscados:
            continue
        estilo = (entidad.dxf.style or "").strip()
        if estilo:
            estilos.append(estilo)
    return estilos


def textos_a_medir(celdas: Sequence[Tuple[int, int, str]], notas: Sequence[str]) -> List[str]:
    """Lo que el cliente CAD tiene que medir con `textbox` para que se pueda
    maquetar: el texto de cada casilla, cada palabra de las notas y de la
    leyenda de borrador, y lo necesario para saber el ancho de un espacio. **Lo
    decide el servidor**; el `.lsp` sólo mide lo que se le pide."""
    from .marca_borrador import LEYENDA

    vistos, salida = set(), []

    def anadir(texto):
        if texto and texto not in vistos:
            vistos.add(texto)
            salida.append(texto)

    for _fila, _columna, texto in celdas:
        anadir(texto)
    for nota in notas:
        for palabra in nota.split():
            anadir(palabra)
    for palabra in LEYENDA.split():
        anadir(palabra)
    for texto in TEXTOS_PARA_EL_ESPACIO:
        anadir(texto)
    return salida


def medidor_de_medidas(textos: Sequence[str], anchos: Sequence[float]):
    """Una función `texto -> ancho a altura 1` hecha con las medidas de AutoCAD.

    Un texto medido tal cual se usa tal cual. Una línea de nota que no se ha
    medido entera se compone con sus palabras y sus espacios. Si falta alguna
    palabra, `MedidaIncompleta`: no se sustituye por una medida a ojo.
    """
    if len(textos) != len(anchos):
        raise MedidaIncompleta("llegan %d textos medidos y %d anchos" % (len(textos), len(anchos)))
    medidas = {}
    for texto, ancho in zip(textos, anchos, strict=True):
        valor = float(ancho)
        if not 0 <= valor < float("inf"):
            raise MedidaIncompleta("el ancho medido de «%s» no es una medida: %r" % (texto, ancho))
        medidas[str(texto)] = valor
    if not all(t in medidas for t in TEXTOS_PARA_EL_ESPACIO):
        raise MedidaIncompleta("falta la medida de «xx» y «x x», con la que se sabe el "
                               "ancho de un espacio")
    espacio = max(medidas["x x"] - medidas["xx"], 0.0)

    def medir(texto: str) -> float:
        if not texto:
            return 0.0
        if texto in medidas:
            return medidas[texto] * HOLGURA_DE_MEDIDA
        palabras = texto.split()
        faltan = sorted({p for p in palabras if p not in medidas})
        if faltan:
            raise MedidaIncompleta("AutoCAD no ha medido: %s" % ", ".join("«%s»" % p for p in faltan))
        return (sum(medidas[p] for p in palabras)
                + espacio * (len(palabras) - 1)) * HOLGURA_DE_MEDIDA

    return medir


def _medidor_por_defecto(texto: str) -> float:
    return ancho_de_texto(texto, 1.0)


def altura_minima(altura_cuadro: Optional[float],
                  alturas_rotulos: Sequence[float]) -> Optional[float]:
    """La altura por debajo de la cual la tabla no se dibuja (decisión 6).

    La del cuadro del arquitecto si se ha podido leer; si no, la mediana de sus
    rótulos de estancia —la mediana y no el mínimo, porque un plano mezcla
    rótulos pequeños con títulos grandes y el mínimo sería el de una nota—.
    `None` si no hay ni lo uno ni lo otro: sin referencia no se inventa una.
    """
    if altura_cuadro is not None and altura_cuadro > 0:
        return float(altura_cuadro)
    validas = [float(a) for a in alturas_rotulos if a and a > 0]
    return float(statistics.median(validas)) if validas else None


@dataclass(frozen=True)
class Maquetacion:
    """La tabla resuelta: lo único que el cliente CAD necesita para dibujarla."""

    esquina: Punto              # arriba a la izquierda
    altura_texto: float
    alto_fila: float
    margen: float
    anchos: Tuple[float, ...]
    n_filas: int
    n_columnas: int
    ancho_total: float
    alto_tabla: float
    alto_total: float           # tabla + notas
    notas: Tuple[Tuple[float, float, str], ...]
    estilo: str = ESTILO_DE_TEXTO
    fuente: str = FUENTE
    #: `(x, y, ancho)` de la marca de borrador (`C-3`), **debajo de las notas**.
    #: Hasta el 2026-09-13 el cliente la ponía bajo el borde de la tabla, que es
    #: donde ahora van las notas: se habrían pisado.
    marca: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    #: El título y su fila, más grandes que el cuerpo, como en sus cuadros.
    altura_titulo: float = 0.0
    alto_fila_titulo: float = 0.0
    #: El margen de arriba y abajo que deja cada fila del alto que se pide.
    margen_vertical: float = 0.0
    estilo_tabla: str = ESTILO_DE_TABLA
    capa: str = CAPA
    color_capa: int = COLOR_DE_CAPA


@dataclass(frozen=True)
class NoCabe:
    """No se dibuja, y se dice por qué y qué haría falta."""

    motivo: str
    ancho_necesario: float = 0.0
    alto_necesario: float = 0.0


def _normalizar_caja(caja) -> Caja:
    (x1, y1), (x2, y2) = caja
    return (min(x1, x2), min(y1, y2)), (max(x1, x2), max(y1, y2))


def _envolver(texto: str, ancho_maximo: float, medir) -> List[str]:
    """Parte una nota en líneas **por palabras**, nunca dentro de una palabra.
    `medir` da el ancho de un texto a altura 1."""
    lineas: List[str] = []
    actual = ""
    for palabra in texto.split():
        candidata = palabra if not actual else actual + " " + palabra
        if actual and medir(candidata) > ancho_maximo + _TOLERANCIA:
            lineas.append(actual)
            actual = palabra
        else:
            actual = candidata
    if actual:
        lineas.append(actual)
    return lineas


def _geometria_unitaria(celdas, notas, medir=None):
    """Todo a altura 1. Anchos y alturas escalan linealmente con la altura de
    texto, y el reparto de las notas en líneas no cambia al escalar (texto y
    ancho crecen igual), así que basta calcularlo una vez.

    `medir` da el ancho de un texto a altura 1: el de AutoCAD cuando lo ha
    medido (`medidor_de_medidas`), y si no, la fuente de `FUENTE`."""
    medir = medir or _medidor_por_defecto
    n_columnas = 1 + max((c for _f, c, _t in celdas), default=0)
    n_filas = 1 + max((f for f, _c, _t in celdas), default=0)
    anchos = [0.0] * n_columnas
    titulo = 0.0
    for fila, columna, texto in celdas:
        if fila == 0:
            # La fila 0 va fusionada a lo ancho, y con su texto más grande.
            titulo = max(titulo, medir(texto) * ESCALA_DEL_TITULO + 2 * MARGEN)
        else:
            anchos[columna] = max(anchos[columna], medir(texto) + 2 * MARGEN)
    # **Columnas iguales**, como las de sus cuadros (1,27 las cuatro, medido): la
    # que más texto lleva decide el ancho de todas, así que ninguna parte nada.
    anchos = [max(max(anchos, default=0.0), 2 * MARGEN)] * n_columnas
    if titulo > sum(anchos):
        anchos = [titulo / n_columnas] * n_columnas

    # Una palabra de una nota más ancha que la tabla ensancha la tabla: partirla
    # no es una opción. Repartido entre todas, para que sigan siendo iguales.
    palabra_mas_ancha = max((medir(p) for n in notas for p in n.split()), default=0.0)
    if palabra_mas_ancha > sum(anchos):
        anchos = [palabra_mas_ancha / n_columnas] * n_columnas

    ancho_total = sum(anchos)
    lineas = [linea for nota in notas for linea in _envolver(nota, ancho_total, medir)]
    alto_tabla = ALTO_DE_FILA_DEL_TITULO + (n_filas - 1) * ALTO_DE_FILA
    alto_notas = (SEPARACION_DE_NOTAS + len(lineas) * INTERLINEA_DE_NOTAS) if lineas else 0.0
    # La marca de borrador también cabe en la ventana: no es opcional (`C-3`).
    from .marca_borrador import LEYENDA

    alto_marca = (SEPARACION_DE_NOTAS
                  + len(_envolver(LEYENDA, ancho_total, medir)) * INTERLINEA_DE_NOTAS)
    return anchos, n_filas, n_columnas, ancho_total, alto_tabla, alto_notas, alto_marca, lineas


def tamano_necesario(celdas, notas, altura: float, medir=None) -> Tuple[float, float]:
    """`(ancho, alto)` que ocupa la tabla con sus notas escrita a `altura`."""
    _a, _f, _c, ancho, alto_tabla, alto_notas, alto_marca, _l = _geometria_unitaria(
        celdas, notas, medir)
    return ancho * altura, (alto_tabla + alto_notas + alto_marca) * altura


def _se_solapan(a: Caja, b: Caja) -> bool:
    (ax1, ay1), (ax2, ay2) = a
    (bx1, by1), (bx2, by2) = b
    return ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2


def maquetar(celdas: Sequence[Tuple[int, int, str]], notas: Sequence[str],
             ventana, altura_minima_legible: Optional[float],
             cajas_prohibidas: Sequence = (), medir=None):
    """La tabla dentro de `ventana`, o `NoCabe`.

    `celdas` son `(fila, columna, texto)`; la fila 0 es el título y va fusionada.
    `cajas_prohibidas` son los cuadros del arquitecto: la tabla no se dibuja
    encima de ninguno.
    """
    if altura_minima_legible is None or altura_minima_legible <= 0:
        return NoCabe("No sé con qué altura de texto dibujar: el plano no tiene ni "
                      "cuadro ni rótulos de estancia de los que sacarla.")
    (x1, y1), (x2, y2) = _normalizar_caja(ventana)
    ancho_ventana, alto_ventana = x2 - x1, y2 - y1

    anchos1, n_filas, n_columnas, ancho1, alto_tabla1, alto_notas1, alto_marca1, lineas = \
        _geometria_unitaria(celdas, notas, medir)
    alto1 = alto_tabla1 + alto_notas1 + alto_marca1

    altura = min(ancho_ventana / ancho1, alto_ventana / alto1) if ancho1 and alto1 else 0.0
    if altura < altura_minima_legible * (1 - _TOLERANCIA):
        ancho_necesario = ancho1 * altura_minima_legible
        alto_necesario = alto1 * altura_minima_legible
        return NoCabe(
            ("La ventana es pequeña: con el texto a la altura mínima legible "
             "(%s) la tabla y sus notas necesitan %s de ancho por %s de alto. "
             "Marca una ventana mayor." % (_num(altura_minima_legible),
                                          _num(ancho_necesario), _num(alto_necesario))),
            ancho_necesario, alto_necesario)

    esquina = (x1, y2)
    huella = ((x1, y2 - alto1 * altura), (x1 + ancho1 * altura, y2))
    for caja in cajas_prohibidas:
        if _se_solapan(huella, _normalizar_caja(caja)):
            return NoCabe("La tabla quedaría encima de tu cuadro de superficies. "
                          "Marca una ventana que no lo toque.")

    alto_tabla = alto_tabla1 * altura
    notas_colocadas = []
    y = y2 - alto_tabla - SEPARACION_DE_NOTAS * altura
    for i, linea in enumerate(lineas):
        notas_colocadas.append((x1, y - i * INTERLINEA_DE_NOTAS * altura, linea))

    return Maquetacion(
        esquina=esquina,
        altura_texto=altura,
        alto_fila=ALTO_DE_FILA * altura,
        margen=MARGEN * altura,
        anchos=tuple(a * altura for a in anchos1),
        n_filas=n_filas,
        n_columnas=n_columnas,
        ancho_total=ancho1 * altura,
        alto_tabla=alto_tabla,
        alto_total=alto1 * altura,
        notas=tuple(notas_colocadas),
        marca=(x1, y2 - (alto_tabla1 + alto_notas1 + SEPARACION_DE_NOTAS) * altura,
               ancho1 * altura),
        altura_titulo=ESCALA_DEL_TITULO * altura,
        alto_fila_titulo=ALTO_DE_FILA_DEL_TITULO * altura,
        margen_vertical=MARGEN_VERTICAL * altura,
    )


def maquetar_en_punto(celdas: Sequence[Tuple[int, int, str]], notas: Sequence[str],
                      punto: Punto, altura_minima_legible: Optional[float],
                      cajas_prohibidas: Sequence = (), medir=None):
    """La tabla colgada de un punto: su esquina de arriba a la izquierda.

    **El punto único** (Pablo, 2026-09-13): «el arquitecto no debe adivinar cuánto
    mide la tabla ni recibir "marca una ventana mayor"». Enmienda la primera regla
    de este módulo: ya no manda una ventana; manda el punto, y el tamaño es el que
    la tabla y sus notas necesitan **a la altura mínima legible** —la del cuadro
    del arquitecto o la de sus rótulos—, así que nunca hay nada que no quepa.

    La única negativa que queda es la que no depende del tamaño: si esa huella
    pisaría uno de sus cuadros, no se dibuja y se pide **otro punto**.
    """
    if altura_minima_legible is None or altura_minima_legible <= 0:
        return NoCabe("No sé con qué altura de texto dibujar: el plano no tiene ni "
                      "cuadro ni rótulos de estancia de los que sacarla.")
    x, y = float(punto[0]), float(punto[1])
    ancho, alto = tamano_necesario(celdas, notas, altura_minima_legible, medir)
    huella = ((x, y - alto), (x + ancho, y))
    for caja in cajas_prohibidas:
        if _se_solapan(huella, _normalizar_caja(caja)):
            return NoCabe("La tabla quedaría encima de tu cuadro de superficies: necesita "
                          "%s de ancho por %s de alto desde el punto marcado. Marca otro "
                          "punto, fuera de él." % (_num(ancho), _num(alto)), ancho, alto)
    return maquetar(celdas, notas, huella, altura_minima_legible, medir=medir)


def alturas_de_rotulos(doc, rotulos: Sequence[str]) -> List[float]:
    """Las alturas de los textos del plano que nombran una estancia medida.

    Son las del **plano** —las del DXF materializado, en la vía del comando—, en
    las mismas unidades de dibujo que la ventana. No se escala nada.
    """
    from . import parser
    from .geometria_recibida import altura_de_texto

    buscados = {(r or "").strip() for r in rotulos if r}
    alturas: List[float] = []
    for entidad in doc.modelspace().query("MTEXT TEXT"):
        if (parser._texto_de(entidad) or "").strip() not in buscados:
            continue
        # Por `altura_de_texto`: medido el 2026-09-13, un payload sin alturas
        # daba aquí [2.5, 2.5, …] —la altura por defecto de ezdxf, que nadie
        # dibujó— y la tabla se maquetaba con ella.
        altura = altura_de_texto(entidad)
        if altura:
            alturas.append(altura)
    return alturas


def _num(valor: float) -> str:
    return ("%.2f" % valor).replace(".", ",")


def a_dict(m) -> dict:
    """Para la respuesta del endpoint: números y listas, nada más."""
    if isinstance(m, NoCabe):
        return {"cabe": False, "motivo": m.motivo,
                "ancho_necesario": m.ancho_necesario, "alto_necesario": m.alto_necesario}
    return {
        "cabe": True,
        "x": m.esquina[0], "y": m.esquina[1],
        "altura_texto": m.altura_texto, "alto_fila": m.alto_fila, "margen": m.margen,
        "anchos": list(m.anchos), "n_filas": m.n_filas, "n_columnas": m.n_columnas,
        "estilo": m.estilo, "fuente": m.fuente,
        # Antes de `notas`, siempre: el cliente lee cada nota buscando `("x" . `
        # a partir de `notas`, y cualquier clave con números detrás se confundiría.
        "altura_titulo": m.altura_titulo, "alto_fila_titulo": m.alto_fila_titulo,
        "margen_vertical": m.margen_vertical, "estilo_tabla": m.estilo_tabla,
        "capa": m.capa, "color_capa": m.color_capa,
        "notas": [{"x": x, "y": y, "linea": linea} for x, y, linea in m.notas],
        # Con prefijo y al final a propósito: el cliente lee las notas buscando
        # `("x" . ` a partir de `notas`, y una `x` suelta de la marca detrás
        # se leería como una nota más.
        "marca_x": m.marca[0], "marca_y": m.marca[1], "marca_ancho": m.marca[2],
    }
