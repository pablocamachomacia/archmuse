# -*- coding: utf-8 -*-
"""`C-8` para `NUMERO UDS`: lo que el plano declara junto al rótulo de la vivienda.

PRD `docs/prd/2026-09-17-modo-preguntar.md`, D-9 (propuesta, pendiente de firma).

**Medido en el plano maestro (fuera del repositorio):** cada tipo lleva debajo de su
rótulo un texto suelto «8uds.», «1 ud.», «3 uds.», a 1,5-1,7 alturas; el rótulo de
otro tipo queda a más de 13 m. Y la forma que dio Pablo: «VT1/3 8 uds», en el propio
rótulo. El número nunca se deduce: si el plano no lo escribe, la celda queda vacía.

Planos sintéticos con coordenadas escritas a mano.
"""
from __future__ import annotations

import os
import sys

import ezdxf
import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import parser  # noqa: E402
from analyzer import plantilla_cuadro as pc  # noqa: E402
from analyzer import unidades_declaradas as ud  # noqa: E402
from tests._carpetas_temporales import carpeta_temporal_de_test  # noqa: E402

CAPA = "00 areas"
ALTURA = 0.15


def _plano(rotulo="VT1/3", sueltos=(), otro_rotulo=None, mtext=False, altura=ALTURA):
    """Una vivienda de dos piezas con su rótulo en (5, 7), y `sueltos`: `(texto, x, y)`."""
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    doc.layers.add(CAPA)
    msp = doc.modelspace()
    for nombre, x0, y0, x1, y1 in (("Salón/cocina", 0, 0, 6, 5), ("Baño", 6, 0, 8, 2),
                                   ("Dormitorio 1", 6, 2, 9, 5), ("Aseo", 8, 0, 9, 2)):
        msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                           dxfattribs={"layer": CAPA})
        msp.add_mtext(nombre, dxfattribs={"layer": CAPA, "char_height": 0.125,
                                          "insert": ((x0 + x1) / 2, (y0 + y1) / 2)})
    if mtext:
        msp.add_mtext(rotulo, dxfattribs={"layer": CAPA, "char_height": altura, "insert": (5, 7)})
    else:
        msp.add_text(rotulo, dxfattribs={"layer": CAPA, "height": altura, "insert": (5, 7)})
    if otro_rotulo:
        texto, x, y = otro_rotulo
        msp.add_text(texto, dxfattribs={"layer": CAPA, "height": ALTURA, "insert": (x, y)})
    for texto, x, y in sueltos:
        msp.add_text(texto, dxfattribs={"layer": CAPA, "height": ALTURA, "insert": (x, y)})
    ruta = os.path.join(carpeta_temporal_de_test("archmuse_test_c8_"), "p.dxf")
    doc.saveas(ruta)
    doc = parser.load_document(ruta)
    return doc, parser.leer_plano(doc, layer=CAPA)


def _unidades(rotulo="VT1/3", **kw):
    doc, plano = _plano(rotulo, **kw)
    nombre = next(n for n, *_ in plano.unit_labels if n.upper().startswith("VT1"))
    p = pc.construir(doc, plano, nombre)
    notas = [n for n in p.notas if n.startswith("NUMERO UDS")]
    return p.cierre[3][3], notas, p


@pytest.mark.parametrize("rotulo, esperado", [
    ("VT1/3 8 uds", "8"),                 # la forma de Pablo
    ("VT1/3 8 uds.", "8"),
    ("VT1/3 8uds", "8"),
    ("VT1/3 - 8 uds.", "8"),
    ("VT1/3 (8 uds)", "8"),
    ("VT1/3: 1 ud.", "1"),
    ("VT1/3 12 UNIDADES", "12"),
    ("VT1/3 1 unidad", "1"),
    ("VT1 /3  8  UDS", "8"),
])
def test_el_numero_escrito_en_el_rotulo(rotulo, esperado):
    valor, notas, p = _unidades(rotulo)
    assert valor == esperado
    assert not notas, notas
    # La celda del tipo no repite lo que va en la de unidades.
    assert p.cierre[3][1] == ud.sin_unidades(rotulo)
    assert "ud" not in p.cierre[3][1].lower()


def test_el_numero_en_un_mtext_de_dos_lineas():
    valor, notas, _p = _unidades("VT1/3\\P8 uds", mtext=True)
    assert valor == "8" and not notas


@pytest.mark.parametrize("texto, esperado", [
    ("8uds.", "8"),        # medido en el maestro
    ("1 ud.", "1"),        # medido en el maestro
    ("3 uds.", "3"),
    ("4 uds", "4"),
    ("2 UDS", "2"),
    ("12 unidades", "12"),
])
def test_el_numero_en_un_texto_suelto_debajo_del_rotulo(texto, esperado):
    # A 0,23 por debajo con textos de 0,15: la geometría del maestro.
    valor, notas, _p = _unidades(sueltos=[(texto, 5.01, 6.77)])
    assert valor == esperado and not notas, notas


def test_sin_declaracion_la_celda_queda_vacia_y_no_se_cuenta():
    valor, notas, p = _unidades()
    assert valor == ""
    assert notas and "no declara el número de unidades" in notas[0]
    assert "Nº de unidades: a mano" in pc.notas_del_dibujo(p)


def test_un_numero_pegado_al_tipo_no_se_lee():
    """«VT1/38 uds» no dice si es VT1/3 con 8 unidades o VT1/38."""
    assert ud.en_el_rotulo("VT1/38 uds") is None


def test_un_texto_suelto_fuera_del_alcance_no_cuenta():
    # 3 alturas de 0,15 son 0,45: a 0,60 ya no.
    valor, notas, _p = _unidades(sueltos=[("8 uds.", 5.0, 6.40)])
    assert valor == "" and "no declara" in notas[0]


def test_un_texto_suelto_mas_cerca_de_otro_rotulo_no_es_de_esta_vivienda():
    # A 0,40 de su rótulo (dentro del alcance) y a 0,35 del de VT2/2.
    valor, _notas, _p = _unidades(sueltos=[("8 uds.", 5.0, 7.40)], otro_rotulo=("VT2/2", 5.0, 7.75))
    assert valor == ""


def test_dos_numeros_distintos_no_se_elige_ninguno():
    valor, notas, _p = _unidades(sueltos=[("8 uds.", 5.0, 6.77), ("9 uds.", 5.0, 7.25)])
    assert valor == ""
    assert "distintos" in notas[0] and "8" in notas[0] and "9" in notas[0]


def test_el_rotulo_y_el_texto_de_al_lado_que_no_coinciden_no_se_elige_ninguno():
    valor, notas, _p = _unidades("VT1/3 8 uds", sueltos=[("9 uds.", 5.0, 6.77)])
    assert valor == "" and "distintos" in notas[0]


def test_el_rotulo_y_el_texto_de_al_lado_que_coinciden_dan_el_numero():
    valor, notas, _p = _unidades("VT1/3 8 uds", sueltos=[("8 uds.", 5.0, 6.77)])
    assert valor == "8" and not notas


def test_cero_unidades_no_es_un_numero_de_viviendas():
    valor, notas, _p = _unidades("VT1/3 0 uds")
    assert valor == "" and "0 unidades" in notas[0]


def test_la_tabla_sigue_sin_cifras_inventadas_con_el_numero():
    """El número de unidades no es una superficie: ni m² ni cero en ninguna celda."""
    _valor, _notas, p = _unidades(sueltos=[("8uds.", 5.0, 6.77)])
    textos = [t for _f, _c, t in p.celdas()]
    assert "8" in textos
    assert not any(t.startswith("0,00") for t in textos)
