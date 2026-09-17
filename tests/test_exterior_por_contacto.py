# -*- coding: utf-8 -*-
"""`C-21`: una pieza exterior es de la vivienda con cuya construida cerrada linda.

**Firmado por Pablo, 2026-09-17:** «Una pieza exterior pertenece a la vivienda con
cuya construida cerrada rotulada comparte borde, o de la que queda separada
únicamente por la tolerancia geométrica existente. Si cumple esto con más de una
vivienda, queda dudosa.» Sólo decide cuando el reparto por cercanía es dudoso; si
el borde y la cercanía señalan viviendas distintas, celda vacía con motivo.

**El caso, medido en el plano maestro (fuera del repositorio).** Una terraza en
franja larga y su tendedero lindan con la construida rotulada de su vivienda y con
ninguna otra, pero su centro queda lejos del rótulo de la vivienda: el reparto por
cercanía era dudoso y la tabla salía sin terraza, sin tendedero y sin totales.

Plano sintético, con coordenadas escritas a mano (metros).
"""
from __future__ import annotations

import os
import sys
import tempfile

import ezdxf

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import medicion, parser  # noqa: E402
from analyzer import plantilla_cuadro as pc  # noqa: E402

CAPA = "00 areas"
PIEZAS = (("Salón/cocina", 0.0, 0.0, 6.0, 5.0), ("Dormitorio 1", 6.0, 0.0, 10.0, 5.0),
          ("Salón/cocina", 20.0, 0.0, 26.0, 5.0), ("Dormitorio 1", 26.0, 0.0, 30.0, 5.0))
CONSTRUIDA_V1 = [(-0.2, -0.2), (10.2, -0.2), (10.2, 5.2), (-0.2, 5.2)]
CONSTRUIDA_V2 = [(19.8, -0.2), (30.2, -0.2), (30.2, 5.2), (19.8, 5.2)]
#: Rótulos lejos, abajo: el centro de la terraza queda a 9,46 m del de VT1/1 y a
#: 15,32 m del de VT2/1 (holgura 1,62, dudosa). Linda con la construida de VT1/1.
ROTULOS_LEJOS = ((3.0, -3.0), (25.0, -3.0))
TERRAZA_ALARGADA = (10.2, -0.2, 11.2, 5.2)


def _plano(terraza=TERRAZA_ALARGADA, rotulos=ROTULOS_LEJOS, construidas=True):
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    doc.layers.add(CAPA)
    doc.layers.add("00 CONSTRUIDA")
    msp = doc.modelspace()
    for rotulo, x0, y0, x1, y1 in PIEZAS + (("Terraza",) + terraza,):
        msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                           dxfattribs={"layer": CAPA})
        msp.add_mtext(rotulo, dxfattribs={"layer": CAPA, "char_height": 0.125,
                                          "insert": ((x0 + x1) / 2, (y0 + y1) / 2)})
    for nombre, (x, y) in zip(("VT1/1", "VT2/1"), rotulos):
        msp.add_mtext(nombre, dxfattribs={"layer": CAPA, "char_height": 0.3, "insert": (x, y)})
    if construidas:
        for contorno, x in ((CONSTRUIDA_V1, 1.0), (CONSTRUIDA_V2, 25.0)):
            msp.add_lwpolyline(contorno, close=True, dxfattribs={"layer": "00 CONSTRUIDA"})
            msp.add_mtext("S. construida cerrada", dxfattribs={
                "layer": CAPA, "char_height": 0.125, "insert": (x, 5.5)})
    ruta = os.path.join(tempfile.mkdtemp(prefix="am_contacto_"), "p.dxf")
    doc.saveas(ruta)
    doc = parser.load_document(ruta)
    return doc, parser.leer_plano(doc, layer=CAPA)


def _fila(plantilla, rotulo):
    return next(f for f in list(plantilla.interiores) + list(plantilla.exteriores) if f.rotulo == rotulo)


def _dudosa(plano, vivienda):
    v = next(v for v in medicion.medir_planta(plano).viviendas if v.nombre == vivienda)
    return [d.pieza for d in v.repartos_dudosos]


def test_el_caso_la_terraza_alargada_tiene_el_reparto_por_cercania_dudoso():
    _doc, plano = _plano()
    assert _dudosa(plano, "VT1/1") == ["Terraza"]


def test_la_terraza_que_linda_con_su_construida_es_suya_y_los_totales_salen():
    doc, plano = _plano()
    p = pc.construir(doc, plano, "VT1/1")
    assert _fila(p, "Terraza").valor == "5,40 m²"
    assert p.impedimentos == ()
    assert p.cierre[0][1] == "50,00 m²" and p.cierre[0][3] == "5,40 m²"
    assert not any("Terraza" in n for n in p.notas), p.notas


def test_separada_solo_por_la_tolerancia_tambien_es_suya():
    x0 = 10.2 + pc.TOLERANCIA_CONTENCION_M * 0.8
    doc, plano = _plano(terraza=(x0, -0.2, x0 + 1.0, 5.2))
    assert _fila(pc.construir(doc, plano, "VT1/1"), "Terraza").valor == "5,40 m²"


def test_mas_alla_de_la_tolerancia_sigue_dudosa():
    x0 = 10.2 + pc.TOLERANCIA_CONTENCION_M * 3
    doc, plano = _plano(terraza=(x0, -0.2, x0 + 1.0, 5.2))
    p = pc.construir(doc, plano, "VT1/1")
    assert _fila(p, "Terraza").valor == ""
    assert p.cierre[0][1] == ""


def test_si_linda_con_dos_construidas_queda_dudosa():
    doc, plano = _plano(terraza=(10.2, -0.2, 19.8, 1.0))
    vivienda = "VT2/1" if _dudosa(plano, "VT2/1") else "VT1/1"
    p = pc.construir(doc, plano, vivienda)
    assert _fila(p, "Terraza").valor == ""
    assert p.cierre[0][1] == "" and p.cierre[0][3] == ""


def test_si_el_borde_y_la_cercania_senalan_viviendas_distintas_celda_vacia_con_motivo():
    """Más cerca del rótulo de VT1/1 (9,83 m frente a 10,42), pero linda con la
    construida de VT2/1: no se escribe en ninguna de las dos."""
    doc, plano = _plano(terraza=(14.5, -0.2, 19.8, 5.2), rotulos=((9.0, -3.0), (26.0, -3.0)))
    assert _dudosa(plano, "VT1/1") == ["Terraza"]
    p = pc.construir(doc, plano, "VT1/1")
    assert _fila(p, "Terraza").valor == ""
    nota = " ".join(n for n in p.notas if n.startswith("Terraza"))
    assert "VT2/1" in nota and "linda" in nota, p.notas
    assert p.cierre[0][3] == ""


def test_sin_construida_rotulada_no_cambia_nada():
    doc, plano = _plano(construidas=False)
    assert _fila(pc.construir(doc, plano, "VT1/1"), "Terraza").valor == ""

