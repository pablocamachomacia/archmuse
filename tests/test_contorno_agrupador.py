# -*- coding: utf-8 -*-
"""El contorno agrupador que envuelve a piezas que NO están en BYLAYER.

**Qué es esto.** `_discard_container_candidates` descarta el contorno que
envuelve a una habitación ya dibujada por su cuenta. Descartarlo importa mucho:
si se cuela, entra en el análisis como una habitación más y su superficie se
cuenta dos veces (`tests/test_solape_interno.py` documenta lo que costó eso en
`ejemplo.dxf`, hasta un 26% de una vivienda contado dos veces).

**El caso que este fichero añade, medido en `v1plantas.dxf` el 2026-09-10.** La
regla pedía tres cosas: que el contorno tenga color propio, que contenga a un
polígono más pequeño con SU MISMA etiqueta, y que ese polígono contenido esté en
**BYLAYER**. La tercera condición venía de una suposición escrita en el propio
docstring —«las habitaciones reales de estos planos siempre usan el color del
layer»— y **es falsa**: este estudio dibuja sus piezas exteriores en verde
(color ACI 3) y el contorno que las agrupa en 150.

Resultado sobre `v1plantas.dxf` antes de este arreglo:

  - contorno de 8,63 m² (color 150, rótulo «Tendedero») cubriendo el **94,8%**
    del Tendedero de 4,22 m² (color 3) y el **92,7%** de la Terraza de 3,32 m²;
  - `extract_room_polygons` devolvía **9** piezas donde el plano dibuja **8**;
  - `medir_planta` declaraba **7,08 m² dibujados dos veces** y dejaba la
    vivienda VT1/3 **sin publicar ninguna superficie**.

Y ése era el «Tendedero duplicado» que llevaba días abierto en las notas de
diseño: **no era una duplicación, era un contorno**. No hay dos tendederos en el
plano; hay un tendedero, una terraza y la línea que envuelve a los dos.

El arreglo quita la condición de BYLAYER del polígono contenido. Lo que
identifica a un contorno agrupador es lo otro: que él tenga color propio, que
envuelva a otro más pequeño y que los dos lleven la misma etiqueta. De qué color
esté dibujado lo que hay dentro no dice nada sobre si el de fuera es un contorno.
"""
from __future__ import annotations

import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import ezdxf  # noqa: E402

from analyzer import parser  # noqa: E402

CAPA = "00 areas"
BYLAYER = 256
VERDE = 3        # el color con el que este estudio dibuja lo exterior
CONTORNO = 150   # y el color del contorno que lo agrupa


def _rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _pieza(msp, puntos, etiqueta, color=BYLAYER):
    msp.add_lwpolyline(puntos, close=True,
                       dxfattribs={"layer": CAPA, "color": color})
    xs = [p[0] for p in puntos]
    ys = [p[1] for p in puntos]
    msp.add_text(etiqueta, dxfattribs={
        "layer": CAPA, "height": 0.2,
        "insert": (sum(xs) / len(xs), sum(ys) / len(ys))})


def _vivienda_con_contorno_exterior(color_de_las_piezas=VERDE):
    """El patrón de `v1plantas.dxf`, en miniatura y sin datos de nadie.

    Cuatro piezas interiores en BYLAYER, dos exteriores con color propio, y el
    contorno que envuelve a las dos exteriores — con el rótulo del tendedero
    dentro, que es lo que hace que el contorno herede esa etiqueta.
    """
    doc = ezdxf.new("R2010")
    doc.units = 6  # metros
    msp = doc.modelspace()

    _pieza(msp, _rect(0, 0, 5, 4), "Salón/cocina")
    _pieza(msp, _rect(0, 4, 3, 7), "Dormitorio 1")
    _pieza(msp, _rect(3, 4, 5, 7), "Dormitorio 2")
    _pieza(msp, _rect(0, 7, 2, 9), "Baño")

    # La zona exterior: tendedero y terraza, y el contorno que agrupa a los dos.
    # El contorno va PRIMERO en el DXF a propósito: el orden no debe importar.
    msp.add_lwpolyline(_rect(6, 0, 9, 5), close=True,
                       dxfattribs={"layer": CAPA, "color": CONTORNO})
    _pieza(msp, _rect(6, 0, 9, 2), "Tendedero", color=color_de_las_piezas)
    _pieza(msp, _rect(6, 3, 9, 5), "Terraza", color=color_de_las_piezas)
    return doc


def _areas(doc):
    return sorted(round(p.area, 3) for p in parser.extract_room_polygons(doc, CAPA))


# ---------------------------------------------------------------------------
# El caso nuevo: lo contenido NO está en BYLAYER
# ---------------------------------------------------------------------------

def test_el_contorno_se_descarta_aunque_lo_de_dentro_tenga_color_propio():
    """El caso de `v1plantas.dxf`. Antes de este arreglo salían 7 piezas."""
    doc = _vivienda_con_contorno_exterior(color_de_las_piezas=VERDE)
    areas = _areas(doc)
    assert 15.0 not in areas, (
        "el contorno de 3x5 se ha colado como una habitación más: %s" % areas)
    # Salón 5x4=20 · Dorm1 3x3=9 · Dorm2 2x3=6 · Baño 2x2=4 · tendedero
    # y terraza 3x2=6 cada uno. El contorno de 3x5=15 no está.
    assert areas == [4.0, 6.0, 6.0, 6.0, 9.0, 20.0], areas


def test_el_contorno_se_descarta_tambien_cuando_lo_de_dentro_es_bylayer():
    """El caso que ya funcionaba. No se puede arreglar uno rompiendo el otro."""
    doc = _vivienda_con_contorno_exterior(color_de_las_piezas=BYLAYER)
    assert 15.0 not in _areas(doc)


def test_la_superficie_no_se_cuenta_dos_veces():
    """La consecuencia que de verdad importa: sin el contorno, la suma de las
    piezas es la superficie que ocupan de verdad."""
    doc = _vivienda_con_contorno_exterior()
    poligonos = parser.extract_room_polygons(doc, CAPA)
    from shapely.ops import unary_union

    suma = sum(p.area for p in poligonos)
    union = unary_union(poligonos).area
    assert round(suma - union, 6) == 0.0, (
        "hay %.3f m² contados dos veces" % (suma - union))


# ---------------------------------------------------------------------------
# Lo que NO debe cambiar
# ---------------------------------------------------------------------------

def test_un_contorno_en_bylayer_se_conserva():
    """La primera condición sigue en pie: si el contorno está en BYLAYER no se
    considera contorno. Un polígono sin color propio es una habitación."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_lwpolyline(_rect(0, 0, 6, 6), close=True,
                       dxfattribs={"layer": CAPA, "color": BYLAYER})
    _pieza(msp, _rect(0, 0, 2, 2), "Salón/cocina", color=VERDE)
    areas = _areas(doc)
    assert 36.0 in areas, areas


def test_un_contorno_con_otra_etiqueta_se_conserva():
    """La tercera condición sigue en pie, y es la que evita el desastre: si el
    contorno NO comparte etiqueta con lo que hay dentro, es la única
    representación de esa habitación y descartarlo dejaría a la vivienda sin su
    superficie. Es exactamente el caso de `test_solape_interno.py`."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_lwpolyline(_rect(0, 0, 6, 6), close=True,
                       dxfattribs={"layer": CAPA, "color": CONTORNO})
    msp.add_text("Salón/cocina", dxfattribs={
        "layer": CAPA, "height": 0.2, "insert": (5.0, 5.0)})
    _pieza(msp, _rect(0, 0, 2, 2), "Dormitorio 1", color=VERDE)
    areas = _areas(doc)
    assert 36.0 in areas, (
        "se ha descartado un contorno que no comparte etiqueta con lo de "
        "dentro: eso deja a la vivienda sin esa superficie. %s" % areas)


def test_una_pieza_pequena_no_descarta_a_una_grande_por_estar_dentro():
    """El orden importa: sólo el que CONTIENE se descarta, nunca el contenido."""
    doc = _vivienda_con_contorno_exterior()
    areas = _areas(doc)
    assert 6.0 in areas, ("el tendedero, que es lo contenido, ha desaparecido: "
                          "%s" % areas)


# ---------------------------------------------------------------------------
# Regresión sobre el plano real, si está en esta máquina
# ---------------------------------------------------------------------------

def _ruta_v1plantas():
    candidatas = [
        os.path.join(os.path.dirname(RAIZ), "_material", "v1plantas.dxf"),
        os.path.join(os.path.dirname(RAIZ), "v1plantas.dxf"),
    ]
    return next((c for c in candidatas if os.path.isfile(c)), None)


@pytest.fixture(scope="module")
def plano_real():
    ruta = _ruta_v1plantas()
    if ruta is None:
        pytest.skip("v1plantas.dxf no está en esta máquina (plano real de "
                    "cliente, no versionado)")
    return parser.leer_plano(parser.load_document(ruta))


def test_v1plantas_mide_ocho_piezas_no_nueve(plano_real):
    """El plano dibuja 8 piezas. Antes de este arreglo se medían 9."""
    etiquetas = sorted((r.label or "") for r in plano_real.rooms)
    assert len(plano_real.rooms) == 8, etiquetas


def test_v1plantas_no_tiene_un_segundo_tendedero(plano_real):
    """No había dos tendederos: había un tendedero y el contorno de la zona
    exterior. Ésta es la comprobación que cierra esa nota de diseño."""
    tendederos = [r for r in plano_real.rooms
                  if (r.label or "").upper().startswith("TENDEDERO")]
    assert len(tendederos) == 1, [round(r.polygon.area, 3) for r in tendederos]
    assert round(tendederos[0].polygon.area, 2) == 4.22


def test_v1plantas_ya_no_declara_superficie_dibujada_dos_veces(plano_real):
    """La consecuencia en la medición: sin el contorno no hay solape, y el
    impedimento que dejaba a VT1/3 sin publicar ninguna superficie desaparece."""
    from analyzer import medicion

    m = medicion.medir_planta(plano_real)
    vt1 = next(v for v in m.viviendas if v.nombre == "VT1/3")
    dos_veces = [i for i in vt1.impedimentos if "dos veces" in i]
    assert dos_veces == [], dos_veces
    assert list(vt1.solapes) == [], vt1.solapes
