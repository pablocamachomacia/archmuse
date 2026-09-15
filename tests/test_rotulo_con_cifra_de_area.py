# -*- coding: utf-8 -*-
"""`C-18` (firmado por Pablo, 2026-09-15): una cifra de área nunca es el nombre de una pieza.

**El caso (AutoCAD, 0.3.12, maestro del estudio).** Cada recinto lleva DOS textos:
el nombre («Salón/cocina») y un campo de área («23.24m²»). ArchMuse tomaba el de
área como rótulo, no reconocía ninguna pieza, bloqueaba los totales y la
construida, y acababa preguntando «¿Qué es «M»? ¿Interior o exterior?». La «M»
sale de `clave_de_familia("23.24m²")`: se quitan cifras y signos, el «²» se
normaliza a «2» y también se va, y queda «m».

Es `D-7` en un plano real: con dos textos de la misma capa y el mismo tipo, el
nombre dependía del orden en que llegaban (`test_dos_vias_leen_igual.py` lo tenía
en xfail sobre otro plano: «Salón/cocina» pasaba a llamarse «21.90m²»).

La regla de Pablo:

1. Un texto que es sólo una cifra de área (23.24m², 8,53 m2, 3.16…) nunca es el
   nombre de una pieza.
2. Con varios textos en un recinto gana el que es un nombre reconocible, sin
   depender del orden.
3. Si hay dos nombres distintos, no se elige: se deja vacío con motivo.
4. Nunca se pregunta por un rótulo sin sentido como «M».

Todo sobre planos **sintéticos**.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from shapely.geometry import Polygon

from analyzer import parser
from analyzer import plantilla_cuadro as pc
from analyzer.geometria_recibida import SubidaMaterializada, payload_desde_dxf, validar

CAPA = "00 areas"


# --- 1. Qué es una cifra de área ------------------------------------------------

@pytest.mark.parametrize("texto", [
    "23.24m²", "8,53 m2", "3.16", "12,00 m²", "7.00 M2", "21.90m\\U+00B2", "4.22 m² ", "9m2",
])
def test_una_cifra_de_area_no_es_un_nombre(texto):
    assert parser._es_cifra_de_area(texto), texto


@pytest.mark.parametrize("texto", [
    "Salón/cocina", "Dormitorio 1", "SALON 12.00 m2", "Baño", "VT1/3", "Terraza 2",
])
def test_un_nombre_no_es_una_cifra_de_area(texto):
    assert not parser._es_cifra_de_area(texto), texto


# --- 2. El rótulo de un recinto con varios textos -----------------------------------

CUADRADO = Polygon([(0, 0), (5, 0), (5, 4), (0, 4)])


def _rotulo(textos, conflicto=None):
    labels = [(t, 1.0 + i * 0.5, 2.0, CAPA) for i, t in enumerate(textos)]
    return parser.match_label_to_room(CUADRADO, labels, capas_validas={CAPA}, conflicto=conflicto)


@pytest.mark.parametrize("textos", [
    ["23.24m²", "Salón/cocina"], ["Salón/cocina", "23.24m²"],
    ["F", "Salón/cocina", "23.24m²"], ["23.24m²", "F", "Salón/cocina"],
], ids=["area-nombre", "nombre-area", "codigo-nombre-area", "area-codigo-nombre"])
def test_gana_el_nombre_reconocible_en_cualquier_orden(textos):
    assert _rotulo(textos) == "Salón/cocina"


def test_con_solo_una_cifra_de_area_el_recinto_se_queda_sin_nombre():
    assert _rotulo(["23.24m²"]) is None


@pytest.mark.parametrize("textos", [["Dormitorio 1", "Baño"], ["Baño", "Dormitorio 1", "8,53 m2"]])
def test_dos_nombres_distintos_no_se_elige_y_queda_el_motivo(textos):
    conflicto = []
    assert _rotulo(textos, conflicto) is None
    assert sorted(conflicto) == ["Baño", "Dormitorio 1"]


def test_el_mismo_nombre_dos_veces_no_es_un_conflicto():
    assert _rotulo(["Baño", "Baño"]) == "Baño"


# --- 3. De punta a punta: la tabla ----------------------------------------------------

PIEZAS = (  # nombre, x0, y0, x1, y1, texto de área
    ("Salón/cocina", 0.0, 0.0, 5.0, 4.0, "20.00m²"),
    ("Dormitorio 1", 0.0, 4.1, 3.0, 7.1, "9,00 m2"),
    ("Baño", 5.1, 0.0, 7.1, 2.0, "4.00"),
    ("Terraza", 7.2, 0.0, 10.2, 1.0, "3.00 m²"),
)


def _dxf(ruta: Path, extra=()) -> Path:
    import ezdxf

    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    doc.layers.add(CAPA)
    msp = doc.modelspace()
    for nombre, x0, y0, x1, y1, area in PIEZAS:
        msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                           dxfattribs={"layer": CAPA})
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        # El campo de área debajo del nombre, como en el plano del estudio.
        msp.add_mtext(nombre, dxfattribs={"layer": CAPA, "char_height": 0.15, "insert": (cx, cy + 0.2)})
        msp.add_mtext(area, dxfattribs={"layer": CAPA, "char_height": 0.15, "insert": (cx, cy - 0.2)})
    for nombre, texto, x0, y0, x1, y1 in extra:
        msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                           dxfattribs={"layer": CAPA})
        for i, t in enumerate(texto):
            msp.add_mtext(t, dxfattribs={"layer": CAPA, "char_height": 0.15,
                                         "insert": ((x0 + x1) / 2, (y0 + y1) / 2 + 0.3 * i)})
    msp.add_mtext("VT1/1", dxfattribs={"layer": CAPA, "char_height": 0.3, "insert": (4.0, 8.0)})
    doc.saveas(str(ruta))
    return ruta


def _plantilla(tmp_path, payload, nombre):
    destino = tmp_path / ("%s.dxf" % nombre)
    SubidaMaterializada(validar(payload)).save(str(destino))
    doc = parser.load_document(str(destino))
    return pc.construir(doc, parser.leer_plano(doc, layer=CAPA), "VT1/1")


@pytest.mark.parametrize("invertir", [False, True], ids=["orden-del-dxf", "orden-invertido"])
def test_la_tabla_lleva_los_nombres_y_no_pregunta_por_ninguna_cifra(tmp_path, invertir):
    payload = payload_desde_dxf(str(_dxf(tmp_path / "planta.dxf")), CAPA)
    if invertir:
        payload["textos"] = list(reversed(payload["textos"]))
    p = _plantilla(tmp_path, payload, "invertido" if invertir else "normal")
    rotulos = sorted(f.rotulo for f in p.interiores + p.exteriores)
    assert rotulos == ["Baño", "Dormitorio 1", "Salón/cocina", "Terraza"], rotulos
    assert next(f.valor for f in p.interiores if f.rotulo == "Salón/cocina") == "20,00 m²"
    assert not p.preguntas, [q.texto for q in p.preguntas]
    assert not p.sin_fila


def test_nunca_se_pregunta_por_un_rotulo_sin_sentido(tmp_path):
    """Un recinto con sólo su cifra de área, y otro con sólo un código de
    mobiliario («LD»): ninguno es un nombre, y no se pregunta por ellos."""
    extra = (("solo-area", ["6.00 m²"], 0.0, 8.0, 3.0, 10.0),
             ("codigo", ["LD"], 3.1, 8.0, 5.1, 10.0))
    payload = payload_desde_dxf(str(_dxf(tmp_path / "planta.dxf", extra)), CAPA)
    p = _plantilla(tmp_path, payload, "sin-sentido")
    assert not p.preguntas, [q.texto for q in p.preguntas]
    assert all("«M»" not in n and "«Ld»" not in n for n in p.notas), p.notas
    assert len(p.sin_fila) == 2


def test_un_contorno_que_agrupa_piezas_con_nombre_se_sigue_descartando(tmp_path):
    """**Medido el 2026-09-15 en el maestro, con la primera versión de `C-18`.** El
    contorno de color que agrupa terraza y tendedero, y la envolvente de toda la
    vivienda, llevan dentro los nombres de sus piezas. Antes se quedaban con el
    primero y `_discard_container_candidates` los descartaba como duplicados; con
    dos nombres dentro se quedaban sin rótulo, no se descartaban, y la vivienda
    salía con 66,52 m² dibujados dos veces y la tabla vacía."""
    import ezdxf

    ruta = _dxf(tmp_path / "planta.dxf")
    doc = ezdxf.readfile(str(ruta))
    msp = doc.modelspace()
    # Contorno ACI 10 alrededor de Baño y Terraza, y envolvente ACI 150 de todo.
    msp.add_lwpolyline([(5.05, -0.05), (10.25, -0.05), (10.25, 2.05), (5.05, 2.05)], close=True,
                       dxfattribs={"layer": CAPA, "color": 10})
    msp.add_lwpolyline([(-0.05, -0.05), (10.25, -0.05), (10.25, 7.15), (-0.05, 7.15)], close=True,
                       dxfattribs={"layer": CAPA, "color": 150})
    doc.saveas(str(ruta))
    for invertir in (False, True):
        payload = payload_desde_dxf(str(ruta), CAPA)
        if invertir:
            payload["textos"] = list(reversed(payload["textos"]))
        p = _plantilla(tmp_path, payload, "agrupadores-%s" % invertir)
        assert not p.impedimentos, p.impedimentos
        assert sorted(f.rotulo for f in p.interiores + p.exteriores) == \
            ["Baño", "Dormitorio 1", "Salón/cocina", "Terraza"]


def test_dos_nombres_en_un_recinto_dejan_la_pieza_sin_fila_y_lo_dicen(tmp_path):
    extra = (("dos", ["Dormitorio 2", "Aseo"], 0.0, 8.0, 3.0, 10.0),)
    payload = payload_desde_dxf(str(_dxf(tmp_path / "planta.dxf", extra)), CAPA)
    p = _plantilla(tmp_path, payload, "dos-nombres")
    nota = next((n for n in p.notas if "«Aseo»" in n and "«Dormitorio 2»" in n), None)
    assert nota and "no se elige" in nota, p.notas
    assert not p.preguntas
