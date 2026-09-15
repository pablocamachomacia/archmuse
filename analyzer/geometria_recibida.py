# -*- coding: utf-8 -*-
"""Geometría enviada por un cliente CAD -> un DXF que el motor ya sabe leer.

**Qué problema resuelve y por qué no es un motor nuevo.** Un script de AutoCAD
no puede subir el DXF del arquitecto: pesa 20 MB, y montar un `multipart` con un
cuerpo binario desde AutoLISP no es viable. Lo que sí puede es mandar los
vértices de lo que ha seleccionado. Este módulo recibe esos vértices y **escribe
un DXF mínimo**, para que la medición entre por el mismo sitio por el que entra
un fichero subido: misma Skill, misma acta de procedencia, mismo PDF, mismo
mecanismo de autorización de efectos, mismo contrato congelado.

**Es la salida A del PRD** (`docs/prd/2026-09-08-integracion-autocad-autolisp.md`
§4.1), y se eligió por lo que NO hace falta tocar: no hay capacidad nueva en el
registro —el guardián de `C4` sigue donde estaba, con `D-12` sin gastar—, no
cambia la firma de `plano.medicion_de_la_planta` —el contrato de `CAD-2` sigue
congelado— y el motor de medición no se entera de nada.

**Lo que este módulo NO hace, y es deliberado:**

- **No empareja rótulos con recintos.** El cliente manda las polilíneas y los
  textos **en crudo**; quien decide qué rótulo es de qué recinto sigue siendo
  `parser.match_label_to_room`, que ya es código probado. Reimplementar ese
  criterio en el cliente sería una segunda implementación de un criterio
  profesional, que es justo lo que prohíbe `D-7`.
- **No decide la escala.** Recibe el `$INSUNITS` que el cliente ha leído de su
  dibujo y lo escribe en la cabecera del DXF; la decisión la sigue tomando
  `analyzer/escala.py` con el mismo cruce entre cabecera y tamaño de lo dibujado.
- **No decide qué rótulo gana dentro de un recinto.** El payload dice de qué
  **tipo** es cada texto —`MTEXT` o `TEXT`— y aquí se escribe eso y nada más.
  El desempate entre dos rótulos que caen en la misma habitación sigue siendo de
  `parser.extract_labels`, que da prioridad al MTEXT. Escribirlo todo de un tipo
  —que es lo que se hacía hasta el 2026-09-12— no era simplificar: era **borrar
  el dato con el que ese criterio decide**. Ver `_tipo_de_texto`.
- **No descarta nada en silencio.** Una polilínea con menos de tres vértices no
  se puede medir, pero tampoco se tira: sale en `descartes` con su motivo y su
  handle para que llegue al arquitecto.

**Sobre los handles.** Cada recinto viaja con el handle de la entidad real de
AutoCAD. No se puede forzar ese mismo handle en el DXF que se escribe aquí, así
que **no hay correspondencia celda a celda**: lo que se conserva es el inventario
de qué entidades del dibujo del arquitecto han producido esta medición, que es
lo que hace falta para poder ir a mirarlas. La correspondencia fina es trabajo
del plugin nativo, donde el proceso es el mismo que dibuja.

**Desde el `.lsp` 3.6.0 el handle de origen viaja además en XDATA**
(`APPID_HANDLE`, `handle_de_origen`), porque `C-12` nombra en sus notas las
polilíneas que ha mirado y esas notas se dibujan en el plano del arquitecto. Hoy
sólo lo lee `C-12`; el resto de la medición sigue como está.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import ezdxf

#: Capa en la que se escribe todo. El cliente manda la suya en cada entidad y se
#: respeta; ésta es sólo el valor por defecto cuando no la manda, y es el mismo
#: nombre por defecto que ya usa el repositorio.
CAPA_POR_DEFECTO = "00 areas"

#: Mínimo de vértices para que un contorno cerrado tenga superficie.
VERTICES_MINIMOS = 3

#: **Este módulo escribe un DXF y NO le estampa la marca de borrador de `C3`.**
#: El guardián `test_ningun_modulo_guarda_un_dxf_sin_pasar_por_la_marca` lo caza
#: y hace bien: cualquier módulo de `analyzer/` que guarde un DXF tiene que
#: justificarse. Ésta es la justificación, y son dos razones independientes.
#:
#: 1. **Este fichero no es un entregable.** `C3` marca lo que llega a una
#:    persona. Esto vive unos segundos en un temporal del servidor, lo lee el
#:    parser y se borra con el directorio: nadie lo abre, nadie lo recibe y
#:    nadie lo firma. El entregable de este flujo es el PDF y la tabla que
#:    dibuja el cliente CAD, y **ésos sí la llevan** — el PDF por
#:    `medicion_pdf.py` y la tabla porque el PRD lo exige sin opción de
#:    desactivarlo.
#: 2. **Estamparla aquí falsearía la medición.** La marca es un `MTEXT`. Este
#:    DXF existe para que `parser.leer_plano` lo lea, y el parser mira todos los
#:    `MTEXT` buscando rótulos de estancia. Un texto que ArchMuse se ha
#:    inventado y que cae dentro de un recinto puede acabar siendo el rótulo de
#:    ese recinto. Sería el producto contaminando su propia entrada.
#:
#: El nombre es feo a propósito: tiene que saltar a la vista en un `grep` y
#: obligar a quien lo copie a leer por qué.
DXF_INTERNO_SIN_MARCA_DE_BORRADOR = (
    "DXF interno y efímero: no se entrega a nadie, y estamparle la marca "
    "metería un MTEXT que el propio parser podría leer como rótulo de estancia."
)


class PayloadInvalido(ValueError):
    """El cuerpo recibido no es geometría medible, y se dice por qué.

    Es un error del cliente (400), no un fallo del motor: se levanta **antes**
    de escribir nada, para que no quede a medias un DXF que nadie va a leer.
    """


@dataclass(frozen=True)
class GeometriaRecibida:
    """Lo que el cliente ha mandado, ya validado."""

    recintos: Tuple[dict, ...]
    textos: Tuple[dict, ...]
    insunits: int
    #: Lo que llegó y no se puede medir, con su motivo. Nunca vacío por omisión:
    #: si algo se ha caído, está aquí.
    descartes: Tuple[dict, ...] = field(default_factory=tuple)
    #: Las polilíneas de las demás capas (`.lsp` 3.6.0). **No son recintos** y no
    #: se miden: están para que el servidor encuentre la construida que el
    #: arquitecto rotula, que puede estar en otra capa (`C-12`). Sin color.
    otras_polilineas: Tuple[dict, ...] = field(default_factory=tuple)

    @property
    def handles(self) -> Tuple[str, ...]:
        return tuple(r["handle"] for r in self.recintos if r.get("handle"))


def _numero(valor: Any, donde: str) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise PayloadInvalido("%s no es un número: %r" % (donde, valor))
    if numero != numero or numero in (float("inf"), float("-inf")):
        raise PayloadInvalido("%s no es un número finito: %r" % (donde, valor))
    return numero


def _vertices(bruto: Any, donde: str) -> List[Tuple[float, float]]:
    if not isinstance(bruto, (list, tuple)):
        raise PayloadInvalido("%s: se esperaba una lista de vértices" % donde)
    puntos: List[Tuple[float, float]] = []
    for i, punto in enumerate(bruto):
        if not isinstance(punto, (list, tuple)) or len(punto) < 2:
            raise PayloadInvalido(
                "%s, vértice %d: se esperaba [x, y] y llegó %r" % (donde, i, punto))
        puntos.append((_numero(punto[0], "%s, vértice %d, x" % (donde, i)),
                       _numero(punto[1], "%s, vértice %d, y" % (donde, i))))
    return puntos


#: Color DXF «el de la capa». Es el que lleva una habitación normal; un contorno
#: agrupador lleva uno propio, y esa diferencia es la que permite distinguirlos.
COLOR_POR_CAPA = 256


def _color(bruto: Any) -> int:
    """El código de color ACI de un recinto, o el de la capa si no viene.

    Un payload antiguo —o un cliente que no lo mande— sigue funcionando: se
    comporta como antes de que el color viajara. Lo que no puede pasar es que un
    valor raro reviente la medición, así que lo que no sea un entero de color
    cuenta como BYLAYER.
    """
    try:
        valor = int(bruto)
    except (TypeError, ValueError):
        return COLOR_POR_CAPA
    return valor if 0 <= valor <= 256 else COLOR_POR_CAPA


#: Los dos tipos de entidad de texto que el payload puede declarar. No es la
#: lista de lo que ArchMuse sabe dibujar: es **la misma lista que mira
#: `parser.extract_labels`**, que devuelve los MTEXT antes que los TEXT para
#: desempatar dos rótulos que caigan dentro del mismo recinto.
TIPOS_DE_TEXTO = ("MTEXT", "TEXT")

#: Lo que se escribe cuando el payload no declara el tipo: **MTEXT, porque es lo
#: que se escribía antes** de que el tipo viajara. Un cliente antiguo sigue
#: produciendo exactamente la misma medición que producía ayer.
TIPO_DE_TEXTO_POR_DEFECTO = "MTEXT"


def _tipo_de_texto(bruto: Any) -> str:
    """El tipo de entidad de un texto recibido, o el de siempre si no viene.

    **Por qué el tipo tiene que viajar, medido el 2026-09-11 sobre
    `plantasimple.dxf`.** Este módulo escribía *todos* los textos como MTEXT.
    `parser.extract_labels` ordena los MTEXT antes que los TEXT justamente para
    que un MTEXT gane a un TEXT dentro del mismo recinto, así que aplanar los
    dos tipos a uno cambia **qué rótulo gana**, y con él qué contornos se
    reconocen como agrupadores: el mismo plano daba **157 recintos y 16
    viviendas con superficie por la vía web, y 169 y 3 por la del comando** —12
    contornos contando superficie dos veces y `C-6` bloqueando 13 viviendas.

    Es una divergencia `C-9` de manual, y se cierra sin criterio nuevo: **el
    payload declara lo que el arquitecto tiene dibujado y aquí se respeta**. La
    prioridad MTEXT-sobre-TEXT sigue viviendo donde vivía, en `extract_labels`,
    que es donde está probada.

    Lo que no sea uno de los dos tipos cuenta como el de siempre, igual que hace
    `_color` con un código de color raro: un payload antiguo o un valor
    inesperado no pueden reventar la medición.
    """
    tipo = str(bruto or "").strip().upper()
    return tipo if tipo in TIPOS_DE_TEXTO else TIPO_DE_TEXTO_POR_DEFECTO


def _altura(bruto: Any) -> Optional[float]:
    """La altura de un texto, o `None` si no viene o no es una altura.

    **Viaja por `D-14`** (2026-09-13): la altura mínima legible de la tabla de
    ArchMuse sale de los rótulos de estancia del plano cuando no hay cuadro del
    arquitecto. Un payload antiguo sin alturas sigue midiendo igual; lo único
    que no puede es maquetar sin cuadro.
    """
    try:
        valor = float(bruto)
    except (TypeError, ValueError):
        return None
    return valor if 0 < valor < float("inf") else None


#: **Marca de «este texto llegó sin altura».** ezdxf escribe `40 = 2,5` en todo
#: MTEXT y TEXT que no la trae, **y también si se le pasa 0** —medido el
#: 2026-09-13—, así que el DXF materializado no puede decir con la altura que
#: no la había. Sin esta marca, la tabla de `D-14` maquetaba con una altura de
#: 2,5 que nadie dibujó y el rótulo de `C-12` buscaba su polilínea a 7,50 m.
APPID_SIN_ALTURA = "ARCHMUSE_SIN_ALTURA"


#: **El handle de la entidad en el dibujo del arquitecto** (`.lsp` 3.6.0). El DXF
#: materializado no puede conservar los handles de AutoCAD, así que el de origen
#: viaja en XDATA. Sin esto, la nota de `C-12` por la vía del comando nombraba
#: polilíneas «3C» o «31» que no existen en su plano, y la web nombraba las de
#: verdad: la misma nota, distinta por las dos vías (`C-9`). Medido el
#: 2026-09-13 sobre `ejemplo.dxf`, VT6/2.
APPID_HANDLE = "ARCHMUSE_HANDLE"


def handle_de_origen(entidad) -> str:
    """El handle con el que el arquitecto encuentra esta entidad en SU dibujo:
    el de XDATA si la entidad viene de un payload, el suyo si no."""
    try:
        if entidad.has_xdata(APPID_HANDLE):
            for codigo, valor in entidad.get_xdata(APPID_HANDLE):
                if codigo == 1000 and valor:
                    return str(valor)
    except Exception:  # noqa: BLE001 - entidad de un DXF ajeno
        pass
    return entidad.dxf.handle


def altura_de_texto(entidad) -> Optional[float]:
    """La altura de un MTEXT o TEXT **tal como la dibujó el arquitecto**, o
    `None`. Es la única lectura de alturas que respeta `APPID_SIN_ALTURA`: quien
    lea `dxf.char_height` directamente se lleva el 2,5 de ezdxf."""
    try:
        if entidad.has_xdata(APPID_SIN_ALTURA):
            return None
    except Exception:  # noqa: BLE001 - entidad de un DXF ajeno
        pass
    clave = "char_height" if entidad.dxftype() == "MTEXT" else "height"
    valor = entidad.dxf.get(clave)
    return float(valor) if isinstance(valor, (int, float)) and valor > 0 else None


def _estilo(bruto: Any) -> Optional[str]:
    """El nombre del estilo de texto de un rótulo, tal cual, o `None`.

    **Viaja desde el `.lsp` 3.5.0** (2026-09-13): la tabla de ArchMuse se dibuja
    con un estilo de texto que ya existe en el plano, y si no hay cuadro del
    arquitecto, ese estilo sale de sus rótulos de estancia. Un payload sin
    estilos sigue midiendo igual; lo único que no puede es dibujar la tabla.
    """
    nombre = str(bruto or "").strip()
    return nombre or None


def validar(cuerpo: Any) -> GeometriaRecibida:
    """El cuerpo JSON -> `GeometriaRecibida`, o `PayloadInvalido` con el motivo.

    Se valida **todo antes de escribir nada**. Un DXF a medio escribir con la
    mitad de los recintos produciría una medición que parece buena y le falta
    media vivienda, que es el modo de fallo más caro de este producto.
    """
    if not isinstance(cuerpo, dict):
        raise PayloadInvalido("el cuerpo tiene que ser un objeto JSON")

    brutos = cuerpo.get("recintos")
    if not isinstance(brutos, list) or not brutos:
        raise PayloadInvalido(
            "no ha llegado ningún recinto: manda «recintos» con al menos una "
            "polilínea cerrada")

    recintos: List[dict] = []
    descartes: List[dict] = []
    for i, bruto in enumerate(brutos):
        if not isinstance(bruto, dict):
            raise PayloadInvalido("recinto %d: se esperaba un objeto" % i)
        handle = str(bruto.get("handle") or "").strip()
        capa = str(bruto.get("capa") or CAPA_POR_DEFECTO).strip() or CAPA_POR_DEFECTO
        puntos = _vertices(bruto.get("vertices"), "recinto %d" % i)
        cerrada = bruto.get("cerrada", True) is not False
        # Un contorno que repite el primer punto al final es lo normal en un DXF
        # cerrado, y ahí sobra porque la polilínea se escribe con `close=True`.
        #
        # **Pero si el flag dice que NO está cerrada, ese punto repetido es la
        # única prueba de que sí lo está.** Es exactamente el caso del salón de
        # `v1plantas.dxf` (handle A61724, hueco 0,00): quitarlo y escribir la
        # polilínea abierta convierte un anillo en una línea con los extremos en
        # esquinas distintas, `_recuperar_cierre_por_geometria` ya no la
        # recupera, y el salón desaparece de la medición. Medido el 2026-09-10:
        # 21,90 m² que se convertían en un `0,00 m²` escrito en el cuadro.
        if cerrada and len(puntos) >= 2 and puntos[0] == puntos[-1]:
            puntos = puntos[:-1]
        if len(puntos) < VERTICES_MINIMOS:
            descartes.append({
                "handle": handle,
                "capa": capa,
                "tipo": "LWPOLYLINE",
                "motivo": ("la polilínea llega con %d vértice(s) distintos y hacen "
                           "falta %d para encerrar una superficie: no se ha medido"
                           % (len(puntos), VERTICES_MINIMOS)),
            })
            continue
        # **El color viaja, y no es cosmético.** `parser._discard_container_candidates`
        # distingue una habitación de un contorno agrupador por si el polígono
        # lleva color propio o el de su capa: un contorno se dibuja aparte,
        # típicamente en ACI 10 o 150. Si el payload no lo trae, el DXF que se
        # materializa sale entero en BYLAYER, el contorno deja de reconocerse y
        # su superficie se cuenta dos veces — medido sobre `v1plantas.dxf` el
        # 2026-09-10: por esta vía la vivienda pasaba de 8 piezas a 10 y de
        # ningún impedimento a 7,08 m² dibujados dos veces.
        recintos.append({"handle": handle, "capa": capa, "vertices": puntos,
                         "color": _color(bruto.get("color")),
                         "cerrada": cerrada})

    if not recintos:
        raise PayloadInvalido(
            "ninguno de los %d recinto(s) recibidos encierra una superficie" % len(brutos))

    # **Las polilíneas de las demás capas** (`C-12`, `.lsp` 3.6.0). Una que llegara
    # sin capa se escribiría en la de recintos y se mediría como una estancia; una
    # de la propia capa de recintos contaría dos veces. Las dos cosas son un
    # cliente roto, y se dicen. Una de menos de tres vértices se deja fuera **sin
    # descarte**: no es superficie que falte en la medición —estas polilíneas no
    # se miden— y no puede ser una construida.
    capa_de_recintos = str(cuerpo.get("capa_de_recintos") or "").strip().lower()
    otras: List[dict] = []
    for i, bruto in enumerate(cuerpo.get("otras_polilineas") or ()):
        if not isinstance(bruto, dict):
            raise PayloadInvalido("otra polilínea %d: se esperaba un objeto" % i)
        capa = str(bruto.get("capa") or "").strip()
        if not capa:
            raise PayloadInvalido(
                "otra polilínea %d: llega sin capa, y escrita en la de recintos se "
                "mediría como una estancia" % i)
        if capa_de_recintos and capa.lower() == capa_de_recintos:
            raise PayloadInvalido(
                "otra polilínea %d: es de la capa de recintos «%s», que viaja en "
                "«recintos», y contaría dos veces" % (i, capa))
        puntos = _vertices(bruto.get("vertices"), "otra polilínea %d" % i)
        cerrada = bruto.get("cerrada", True) is not False
        if cerrada and len(puntos) >= 2 and puntos[0] == puntos[-1]:
            puntos = puntos[:-1]
        if len(puntos) < VERTICES_MINIMOS:
            continue
        otras.append({"handle": str(bruto.get("handle") or "").strip(), "capa": capa,
                      "vertices": puntos, "cerrada": cerrada})

    textos: List[dict] = []
    for i, bruto in enumerate(cuerpo.get("textos") or ()):
        if not isinstance(bruto, dict):
            raise PayloadInvalido("texto %d: se esperaba un objeto" % i)
        contenido = str(bruto.get("texto") or "").strip()
        if not contenido:
            continue
        textos.append({
            "handle": str(bruto.get("handle") or "").strip(),
            "capa": str(bruto.get("capa") or CAPA_POR_DEFECTO).strip() or CAPA_POR_DEFECTO,
            "texto": contenido,
            "tipo": _tipo_de_texto(bruto.get("tipo")),
            "x": _numero(bruto.get("x"), "texto %d, x" % i),
            "y": _numero(bruto.get("y"), "texto %d, y" % i),
            "altura": _altura(bruto.get("altura")),
            "estilo": _estilo(bruto.get("estilo")),
        })

    bruto_unidades = cuerpo.get("insunits", 0)
    try:
        insunits = int(bruto_unidades or 0)
    except (TypeError, ValueError):
        raise PayloadInvalido("«insunits» no es un código de unidad: %r" % bruto_unidades)

    return GeometriaRecibida(
        recintos=tuple(recintos), textos=tuple(textos), insunits=insunits,
        descartes=tuple(descartes), otras_polilineas=tuple(otras))


def escribir_dxf(geometria: GeometriaRecibida, ruta: str) -> str:
    """Materializa un DXF mínimo con lo recibido. Devuelve la ruta escrita.

    Lo que se escribe y nada más: las polilíneas cerradas en su capa, los textos
    en la suya, y `$INSUNITS` en la cabecera. Sin bloques, sin estilos, sin
    cajetín — este fichero vive unos segundos en un temporal del servidor y
    existe sólo para que el lector de siempre tenga algo que leer.
    """
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = geometria.insunits
    msp = doc.modelspace()

    capas = ({r["capa"] for r in geometria.recintos} | {t["capa"] for t in geometria.textos}
             | {p["capa"] for p in geometria.otras_polilineas})
    for capa in sorted(capas):
        if capa not in doc.layers:
            doc.layers.add(capa)

    if APPID_HANDLE not in doc.appids:
        doc.appids.new(APPID_HANDLE)

    def _con_handle(entidad, handle):
        if handle:
            entidad.set_xdata(APPID_HANDLE, [(1000, handle)])

    for recinto in geometria.recintos:
        # `close` es el flag TAL COMO VIENE del dibujo del arquitecto, no un
        # `True` fijo. Escribirlo mal aquí sería decidir en el cliente algo que
        # decide `parser._esta_cerrada` — que además sabe recuperar la polilínea
        # cerrada geométricamente con el flag mal puesto, y `ssget` no.
        _con_handle(msp.add_lwpolyline(recinto["vertices"],
                                       close=recinto.get("cerrada", True),
                                       dxfattribs={"layer": recinto["capa"],
                                                   "color": recinto.get("color", COLOR_POR_CAPA)}),
                    recinto.get("handle"))

    # En su capa y con su flag, **sin color**: no lo trae, y la construida no se
    # reconoce por él (`C-12`).
    for polilinea in geometria.otras_polilineas:
        _con_handle(msp.add_lwpolyline(polilinea["vertices"], close=polilinea.get("cerrada", True),
                                       dxfattribs={"layer": polilinea["capa"]}),
                    polilinea.get("handle"))

    # El estilo de cada texto, con su nombre y sin fuente: el servidor sólo lo lee
    # para decir con qué estilo del plano se dibuja la tabla (`.lsp` 3.5.0). Un
    # nombre que ezdxf no admite en su tabla de estilos no tumba la medición: ese
    # texto se escribe sin estilo, y no cuenta como candidato.
    estilos_escritos = set()
    for texto in geometria.textos:
        estilo = texto.get("estilo")
        if not estilo or estilo in estilos_escritos:
            continue
        try:
            if estilo not in doc.styles:
                doc.styles.add(estilo)
            estilos_escritos.add(estilo)
        except Exception:  # noqa: BLE001 - nombre de un plano ajeno
            continue

    if any(not t.get("altura") for t in geometria.textos) and APPID_SIN_ALTURA not in doc.appids:
        doc.appids.new(APPID_SIN_ALTURA)

    for texto in geometria.textos:
        # **Cada texto se escribe con el tipo que el cliente ha declarado.** No
        # es cosmético y no es un criterio nuevo: `parser.extract_labels`
        # desempata dos rótulos dentro de un mismo recinto dando prioridad al
        # MTEXT, así que escribirlo todo como MTEXT le quita a esa regla el
        # dato con el que decide. Ver `_tipo_de_texto` para las cifras.
        #
        # El punto que llega es el punto de inserción **efectivo** —`x`/`y` los
        # calcula `parser._punto_de_texto` en el servidor y `am:punto-de-texto`
        # en el cliente, con la misma regla del código 11—, así que aquí se
        # escribe como `insert` con `halign`/`valign` a cero y el lector lo
        # vuelve a leer en el mismo sitio.
        altura = texto.get("altura")
        estilo = texto.get("estilo") if texto.get("estilo") in estilos_escritos else None
        if texto.get("tipo", TIPO_DE_TEXTO_POR_DEFECTO) == "TEXT":
            atributos = {"layer": texto["capa"]}
            if altura:
                atributos["height"] = altura
            if estilo:
                atributos["style"] = estilo
            entidad = msp.add_text(texto["texto"], dxfattribs=atributos)
            entidad.set_placement((texto["x"], texto["y"]))
        else:
            atributos = {"layer": texto["capa"]}
            if altura:
                atributos["char_height"] = altura
            if estilo:
                atributos["style"] = estilo
            entidad = msp.add_mtext(texto["texto"], dxfattribs=atributos)
            entidad.set_location((texto["x"], texto["y"]))
        if not altura:
            entidad.set_xdata(APPID_SIN_ALTURA, [(1000, "el dibujo de origen no trae altura")])
        _con_handle(entidad, texto.get("handle"))

    doc.saveas(ruta)
    return ruta


class SubidaMaterializada:
    """Un DXF materializado que se comporta como el fichero de una subida.

    **Ésta es toda la costura.** `_ejecutar_medicion_de_planta` sólo le pide a lo
    que recibe un método `save(ruta)`; dárselo aquí es lo que permite que la
    geometría entre por el camino existente sin tocar ni una línea de él, de la
    Skill, de la capacidad ni del motor.
    """

    def __init__(self, geometria: GeometriaRecibida):
        self._geometria = geometria
        self.filename = "geometria_recibida.dxf"

    def save(self, ruta: str) -> None:
        # **La misma geometría se escribe una vez** (medido el 2026-09-15: 2,4 s por
        # escritura con 6.279 textos, y una petición la escribía dos veces, para la
        # medición y para la tabla). Los mismos bytes, además, hacen que
        # `parser.leer_fichero` reconozca la segunda lectura como la primera.
        if _ULTIMA_ESCRITA[0] is self._geometria:
            with open(ruta, "wb") as fichero:
                fichero.write(_ULTIMA_ESCRITA[1])
            return
        escribir_dxf(self._geometria, ruta)
        with open(ruta, "rb") as fichero:
            _ULTIMA_ESCRITA[:] = [self._geometria, fichero.read()]


#: `[geometría, bytes del DXF]` de la última materialización.
_ULTIMA_ESCRITA: list = [None, b""]


def a_sexpresion(valor: Any) -> str:
    """El resultado como s-expresión, que AutoLISP lee con `read` en una línea.

    **Por qué existe.** AutoLISP no trae parser JSON. Escribir uno en el cliente
    serían ~150 líneas que no se pueden probar sin AutoCAD instalado — la pieza
    más frágil del prototipo, y la única imposible de verificar antes del trial.
    Diez líneas de Python aquí, con sus tests, sustituyen a eso.

    El mapeo es el de una lista de asociación de LISP, que es como se lee un
    diccionario allí: `{"a": 1}` -> `(("a" . 1))`. `None` sale como `nil`, que es
    exactamente lo que significa una superficie que no se publica.
    """
    if valor is None:
        return "nil"
    if valor is True:
        return "T"
    if valor is False:
        return "nil"
    if isinstance(valor, (int, float)):
        return repr(valor)
    if isinstance(valor, str):
        return '"%s"' % valor.replace("\\", "\\\\").replace('"', '\\"')
    if isinstance(valor, dict):
        return "(%s)" % " ".join(
            "(%s . %s)" % (a_sexpresion(str(k)), a_sexpresion(v))
            for k, v in valor.items())
    if isinstance(valor, (list, tuple)):
        return "(%s)" % " ".join(a_sexpresion(v) for v in valor)
    return a_sexpresion(str(valor))


def payload_desde_dxf(ruta: str, capa: Optional[str] = None) -> Dict[str, Any]:
    """El payload que mandaría el cliente CAD, derivado de un DXF real.

    **Para los tests, y por eso vive aquí y no en ellos.** Un payload escrito a
    mano probaría el test, no el producto: se parecería a lo que el autor del
    test cree que manda AutoCAD. Éste sale de un DXF de verdad, y por eso la
    comparación contra `/api/medicion` sobre ese mismo fichero significa algo.

    Simula lo que hace el cliente CAD: coge **todas** las polilíneas de la capa
    de recintos —con su flag de cerrada tal como esté— y **todos** los textos,
    sin emparejar ni filtrar nada.

    ### Por qué manda también las que el flag declara abiertas

    Porque `ssget` sólo sabe filtrar por el bit del código 70, y ese bit **está
    mal puesto en los planos reales**: 3 de 22 en `V5.dxf`, 2 de 10 en
    `v2s.dxf`, 9 de 53 en `ejemplo.dxf`, y **2 de 10 en `v1plantas.dxf` — una de
    ellas el salón**. Si el cliente filtra por el flag, esas polilíneas no salen
    del dibujo y el servidor no puede recuperarlas: sobre `v1plantas.dxf` eso
    convertía un salón de 21,90 m² en un **`0,00 m²` escrito en el cuadro del
    arquitecto**, con la medición aparentemente limpia y sin ningún aviso.

    Así que el cliente manda todo y **decide el servidor**, con
    `parser._esta_cerrada`, que es donde vive ese criterio y donde ya está
    probado (`tests/test_cierre_recuperado.py`). El flag viaja en `cerrada` para
    que la decisión se tome sobre el dato real del dibujo, no sobre una
    suposición.
    """
    from . import parser

    doc = parser.load_document(ruta)
    capa_elegida, _pedida = parser._resolver_capa(doc, capa)
    nombre_capa = capa_elegida.nombre

    recintos: List[dict] = []
    for entidad in doc.modelspace():
        if entidad.dxftype() != "LWPOLYLINE":
            continue
        if entidad.dxf.layer != nombre_capa:
            continue
        puntos = parser._polyline_points(entidad)
        if len(puntos) < VERTICES_MINIMOS:
            continue
        recintos.append({
            "handle": entidad.dxf.handle,
            "capa": entidad.dxf.layer,
            "color": int(entidad.dxf.color),
            "cerrada": bool(parser._esta_cerrada(entidad, recuperar_geometria=False)),
            "vertices": [[round(x, 6), round(y, 6)] for x, y in puntos],
        })

    textos: List[dict] = []
    for entidad in doc.modelspace():
        if entidad.dxftype() not in ("TEXT", "MTEXT"):
            continue
        contenido = parser._texto_de(entidad)
        punto = parser._punto_de_texto(entidad)
        if not contenido or punto is None:
            continue
        altura = altura_de_texto(entidad)
        textos.append({
            "handle": entidad.dxf.handle,
            "capa": entidad.dxf.layer,
            "texto": contenido,
            "tipo": entidad.dxftype(),
            "x": round(punto[0], 6),
            "y": round(punto[1], 6),
            "altura": round(float(altura), 6) if altura else None,
            # Lo que manda el `.lsp`: el código 7, o «Standard» si no lo trae.
            "estilo": entidad.dxf.get("style") or "Standard",
        })

    # Lo que manda `am:otras-polilineas` (3.6.0): todas las LWPOLYLINE del espacio
    # modelo que no son de la capa de recintos, en crudo y sin color.
    otras: List[dict] = []
    for entidad in doc.modelspace():
        if entidad.dxftype() != "LWPOLYLINE" or entidad.dxf.layer.lower() == nombre_capa.lower():
            continue
        otras.append({
            "handle": entidad.dxf.handle,
            "capa": entidad.dxf.layer,
            "cerrada": bool(parser._esta_cerrada(entidad, recuperar_geometria=False)),
            "vertices": [[round(x, 6), round(y, 6)] for x, y in parser._polyline_points(entidad)],
        })

    from . import escala as escala_mod

    return {
        "insunits": escala_mod.leer_insunits(doc),
        "capa_de_recintos": nombre_capa,
        "recintos": recintos,
        "textos": textos,
        "otras_polilineas": otras,
    }
