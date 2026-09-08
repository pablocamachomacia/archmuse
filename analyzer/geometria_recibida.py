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
- **No descarta nada en silencio.** Una polilínea con menos de tres vértices no
  se puede medir, pero tampoco se tira: sale en `descartes` con su motivo y su
  handle para que llegue al arquitecto.

**Sobre los handles.** Cada recinto viaja con el handle de la entidad real de
AutoCAD. No se puede forzar ese mismo handle en el DXF que se escribe aquí, así
que **no hay correspondencia celda a celda**: lo que se conserva es el inventario
de qué entidades del dibujo del arquitecto han producido esta medición, que es
lo que hace falta para poder ir a mirarlas. La correspondencia fina es trabajo
del plugin nativo, donde el proceso es el mismo que dibuja.
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
        # Un contorno que repite el primer punto al final es lo normal en un DXF
        # cerrado; aquí sobra, porque la polilínea se escribe con `close=True`.
        if len(puntos) >= 2 and puntos[0] == puntos[-1]:
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
        recintos.append({"handle": handle, "capa": capa, "vertices": puntos})

    if not recintos:
        raise PayloadInvalido(
            "ninguno de los %d recinto(s) recibidos encierra una superficie" % len(brutos))

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
            "x": _numero(bruto.get("x"), "texto %d, x" % i),
            "y": _numero(bruto.get("y"), "texto %d, y" % i),
        })

    bruto_unidades = cuerpo.get("insunits", 0)
    try:
        insunits = int(bruto_unidades or 0)
    except (TypeError, ValueError):
        raise PayloadInvalido("«insunits» no es un código de unidad: %r" % bruto_unidades)

    return GeometriaRecibida(
        recintos=tuple(recintos), textos=tuple(textos), insunits=insunits,
        descartes=tuple(descartes))


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

    capas = {r["capa"] for r in geometria.recintos} | {t["capa"] for t in geometria.textos}
    for capa in sorted(capas):
        if capa not in doc.layers:
            doc.layers.add(capa)

    for recinto in geometria.recintos:
        msp.add_lwpolyline(recinto["vertices"], close=True,
                           dxfattribs={"layer": recinto["capa"]})

    for texto in geometria.textos:
        msp.add_mtext(texto["texto"], dxfattribs={"layer": texto["capa"]}).set_location(
            (texto["x"], texto["y"]))

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
        escribir_dxf(self._geometria, ruta)


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

    Simula lo que hace `ssget` en el cliente: coge las polilíneas cerradas de la
    capa de recintos y **todos** los textos, sin emparejar nada.
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
        if not parser._esta_cerrada(entidad):
            continue
        puntos = parser._polyline_points(entidad)
        recintos.append({
            "handle": entidad.dxf.handle,
            "capa": entidad.dxf.layer,
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
        textos.append({
            "handle": entidad.dxf.handle,
            "capa": entidad.dxf.layer,
            "texto": contenido,
            "x": round(punto[0], 6),
            "y": round(punto[1], 6),
        })

    from . import escala as escala_mod

    return {
        "insunits": escala_mod.leer_insunits(doc),
        "capa_de_recintos": nombre_capa,
        "recintos": recintos,
        "textos": textos,
    }
