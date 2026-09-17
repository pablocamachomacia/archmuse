# -*- coding: utf-8 -*-
"""Si ArchMuse no puede demostrar que una cifra es de esa vivienda, no la muestra.

**Regla de Pablo, 2026-09-17: propuesta, pendiente de firma.**

**El caso, medido en el plano maestro (fuera del repositorio).** Una vivienda escribía
en su tabla, con cifra, un aseo que según el cuadro del arquitecto es de la vecina. El
reparto por cercanía lo daba por firme (holgura 2,11, por encima de 2). Pero el aseo
está dentro de la superficie construida que el plano **rotula** (`C-12`) y que contiene
todas las piezas de reparto firme de la vecina: el propio plano dice que es suyo.

**Sin heurísticas nuevas.** Sólo se cruzan dos señales que ya existen: el reparto
firme y la construida rotulada leída con `C-12` (una sola polilínea al alcance del
rótulo; contiene todas las piezas interiores firmes de una vivienda y ninguna
exterior). Si una pieza está dentro de la construida de **otra** vivienda, su celda
queda vacía con motivo. Sin construida rotulada, nada cambia.

Plano sintético, con coordenadas escritas a mano.
"""
from __future__ import annotations

import os
import sys
import tempfile

import ezdxf
import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import parser  # noqa: E402
from analyzer import plantilla_cuadro as pc  # noqa: E402

CAPA = "00 areas"
V1_PIEZAS = (("Salón/cocina", 12.0, -3.0, 18.0, 3.0), ("Baño", 19.0, -6.0, 21.0, -4.0))
V2_PIEZAS = (("Salón/cocina", 23.0, 8.0, 33.0, 14.0), ("Dormitorio 1", 23.0, 14.1, 28.0, 17.0))
#: Más cerca del rótulo de VT1/1 (6 m) que del de VT2/1 (16,3 m): reparto firme a VT1/1.
ASEO = ("Aseo", 20.5, 0.0, 22.5, 2.0)
#: La construida de VT2/1: rodea sus piezas y el aseo.
CONSTRUIDA_V2 = [(20.0, -0.5), (34.0, -0.5), (34.0, 17.5), (20.0, 17.5)]


def _plano(con_construida=True, construida=CONSTRUIDA_V2):
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    doc.layers.add(CAPA)
    doc.layers.add("00 CONSTRUIDA")
    msp = doc.modelspace()
    for rotulo, x0, y0, x1, y1 in V1_PIEZAS + V2_PIEZAS + (ASEO,):
        msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                           dxfattribs={"layer": CAPA})
        msp.add_mtext(rotulo, dxfattribs={"layer": CAPA, "char_height": 0.125,
                                          "insert": ((x0 + x1) / 2, (y0 + y1) / 2)})
    msp.add_mtext("VT1/1", dxfattribs={"layer": CAPA, "char_height": 0.3, "insert": (21.5, -5.0)})
    msp.add_mtext("VT2/1", dxfattribs={"layer": CAPA, "char_height": 0.3, "insert": (28.0, 16.0)})
    if con_construida:
        msp.add_lwpolyline(construida, close=True, dxfattribs={"layer": "00 CONSTRUIDA"})
        arriba = max(y for _x, y in construida)
        msp.add_mtext("S. construida cerrada", dxfattribs={
            "layer": CAPA, "char_height": 0.125, "insert": (27.0, arriba + 0.2)})
    ruta = os.path.join(tempfile.mkdtemp(prefix="am_ajena_"), "p.dxf")
    doc.saveas(ruta)
    doc = parser.load_document(ruta)
    return doc, parser.leer_plano(doc, layer=CAPA)


def _fila(plantilla, rotulo):
    return next(f for f in list(plantilla.interiores) + list(plantilla.exteriores) if f.rotulo == rotulo)


def test_el_caso_el_reparto_da_el_aseo_por_firme_a_la_vivienda_equivocada():
    from analyzer import medicion

    _doc, plano = _plano()
    v1 = next(v for v in medicion.medir_planta(plano).viviendas if v.nombre == "VT1/1")
    assert "Aseo" in [p.nombre for p in v1.piezas]
    assert not v1.repartos_dudosos, "el caso es un reparto firme, no dudoso"


def test_la_pieza_dentro_de_la_construida_de_otra_vivienda_no_lleva_cifra():
    doc, plano = _plano()
    p = pc.construir(doc, plano, "VT1/1")
    aseo = _fila(p, "Aseo")
    assert aseo.valor == ""
    nota = " ".join(n for n in p.notas if n.startswith("Aseo"))
    assert "VT2/1" in nota and "construida" in nota, p.notas
    assert p.cierre[0][1] == "", "sin esa cifra el total interior estaría corto"
    # Las piezas que sí son suyas siguen con cifra.
    assert _fila(p, "Salón/cocina").valor == "36,00 m²"


def test_la_vivienda_duena_de_la_construida_no_pierde_nada():
    doc, plano = _plano()
    p = pc.construir(doc, plano, "VT2/1")
    assert _fila(p, "Salón/cocina").valor == "60,00 m²"
    assert _fila(p, "Dormitorio 1").valor


def test_sin_construida_rotulada_no_cambia_nada():
    """No hay señal del plano que contradiga el reparto: no se inventa ninguna."""
    doc, plano = _plano(con_construida=False)
    assert _fila(pc.construir(doc, plano, "VT1/1"), "Aseo").valor == "4,00 m²"


def test_una_construida_que_no_contiene_todas_las_piezas_de_nadie_no_cuenta():
    """Si la construida no es de ninguna vivienda por `C-12`, no dice de quién es la pieza."""
    solo_el_aseo = [(20.0, -0.5), (23.0, -0.5), (23.0, 2.5), (20.0, 2.5)]
    doc, plano = _plano(construida=solo_el_aseo)
    assert _fila(pc.construir(doc, plano, "VT1/1"), "Aseo").valor == "4,00 m²"
