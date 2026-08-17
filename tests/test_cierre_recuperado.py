# -*- coding: utf-8 -*-
"""Fase 0 (informe de diagnostico DXF, 2026-08-13): por que ArchMuse no leia
el salon de VT1/3 en dos proyectos reales (`V5.dxf`, `v2s.dxf`).

Causa medida: la polilinea del salon esta geometricamente cerrada (su primer
y ultimo vertice coinciden) pero el flag DXF `closed` vale `False` -- un
error de dibujo real, no hipotetico. `_esta_cerrada()` confiaba ciegamente en
ese flag y descartaba la entidad antes de construir ningun poligono, sin
ningun aviso.

Que protege este archivo:

1. Que una polilinea con `closed=False` pero extremos coincidentes (dentro
   de tolerancia) se reconozca como cerrada -- y que una polilinea
   genuinamente abierta siga descartandose exactamente igual que antes.
2. Que la recuperacion quede SIEMPRE registrada (`logging.WARNING`), nunca en
   silencio: tratar como cerrada una polilinea que el propio archivo declara
   abierta es una correccion de datos, no un hecho neutro.
3. Que el heuristico de deteccion de capa (`capas_candidatas`,
   `_poligonos_cerrados_por_capa`) NO participe de esta recuperacion -- esta
   correccion es sobre que habitaciones se leen de la capa ya elegida, no
   sobre que capa se elige (fuera de alcance a proposito, ver informe).
4. Que VT1/3 vuelva a detectar su "Salon/cocina", con evidencia sintetica
   (portable, no depende de ningun archivo local) y, si estan disponibles,
   con los dos DXF reales donde se midio el fallo.

Sobre V5.dxf / v2s.dxf: son proyectos reales de un cliente (>18 MB cada uno)
y no se versionan en el repositorio. Mismo patron que `tests/test_capas.py`
ya usa con `ejemplo.dxf`: se buscan en las ubicaciones donde pueden vivir sin
estar versionados y, si no aparecen, la prueba se SALTA en vez de fallar.
Ninguna ruta de una maquina concreta queda escrita aqui.
"""
from __future__ import annotations

import logging
import math
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import ezdxf  # noqa: E402

from analyzer import evaluator, parser  # noqa: E402

LOGGER = "analyzer.parser"


# ---------------------------------------------------------------------------
# `_extremos_coinciden` -- la comprobacion geometrica pura, sin ezdxf
# ---------------------------------------------------------------------------


def test_extremos_coinciden_gap_cero():
    """El caso real medido en V5.dxf y v2s.dxf: el salon tenia el primer y el
    ultimo vertice EXACTAMENTE en el mismo punto."""
    puntos = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)]
    assert parser._extremos_coinciden(puntos) is True


def test_extremos_no_coinciden_polilinea_genuinamente_abierta():
    """Un hueco grande (aqui, el ultimo vertice cae en el centro del
    poligono) no es un flag mal puesto: es una polilinea abierta de verdad,
    y no debe recuperarse."""
    puntos = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (5.0, 5.0)]
    assert parser._extremos_coinciden(puntos) is False


def test_extremos_coinciden_justo_dentro_de_la_tolerancia():
    """Caso limite: un hueco al 99% del umbral (relativo a la diagonal de la
    caja envolvente) SI se recupera."""
    lado = 10.0
    diagonal = lado * math.sqrt(2)
    umbral = parser.TOLERANCIA_CIERRE * diagonal
    hueco = umbral * 0.99
    puntos = [(0.0, 0.0), (lado, 0.0), (lado, lado), (0.0, lado), (hueco, 0.0)]
    assert parser._extremos_coinciden(puntos) is True


def test_extremos_no_coinciden_justo_fuera_de_la_tolerancia():
    """Mismo caso limite, al 101% del umbral: NO se recupera."""
    lado = 10.0
    diagonal = lado * math.sqrt(2)
    umbral = parser.TOLERANCIA_CIERRE * diagonal
    hueco = umbral * 1.01
    puntos = [(0.0, 0.0), (lado, 0.0), (lado, lado), (0.0, lado), (hueco, 0.0)]
    assert parser._extremos_coinciden(puntos) is False


def test_extremos_coinciden_exactamente_en_el_limite():
    """El umbral es `<=`, no `<`: el hueco exactamente igual al umbral
    tambien se recupera."""
    lado = 10.0
    diagonal = lado * math.sqrt(2)
    umbral = parser.TOLERANCIA_CIERRE * diagonal
    puntos = [(0.0, 0.0), (lado, 0.0), (lado, lado), (0.0, lado), (umbral, 0.0)]
    assert parser._extremos_coinciden(puntos) is True


def test_menos_de_tres_vertices_no_se_recupera():
    assert parser._extremos_coinciden([(0.0, 0.0), (1.0, 1.0)]) is False


# ---------------------------------------------------------------------------
# `_esta_cerrada` sobre entidades ezdxf reales (sin guardar a disco: los
# atributos que importan aqui -- closed, dxf.layer, dxf.handle -- ya estan
# poblados nada mas anadir la entidad al modelspace)
# ---------------------------------------------------------------------------


def _doc_con_polilinea(puntos, closed):
    doc = ezdxf.new("R2010")
    doc.layers.add(parser.AREA_LAYER)
    msp = doc.modelspace()
    entidad = msp.add_lwpolyline(puntos, close=closed, dxfattribs={"layer": parser.AREA_LAYER})
    return doc, entidad


def test_closed_true_se_reconoce_cerrada_sin_aviso(caplog):
    doc, e = _doc_con_polilinea([(0, 0), (6, 0), (6, 4), (0, 4)], closed=True)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        resultado = parser._esta_cerrada(e)
    assert resultado is True
    assert caplog.records == []


def test_closed_false_extremos_coincidentes_se_recupera_y_se_registra(caplog):
    doc, e = _doc_con_polilinea([(0, 0), (6, 0), (6, 4), (0, 4), (0, 0)], closed=False)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        resultado = parser._esta_cerrada(e)
    assert resultado is True
    assert len(caplog.records) == 1
    mensaje = caplog.records[0].getMessage()
    assert "closed=False" in mensaje
    assert "tratada como cerrada" in mensaje
    assert parser.AREA_LAYER in mensaje


def test_closed_false_abierta_de_verdad_no_se_recupera_ni_avisa(caplog):
    doc, e = _doc_con_polilinea([(0, 0), (6, 0), (6, 4), (0, 4), (3, 2)], closed=False)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        resultado = parser._esta_cerrada(e)
    assert resultado is False
    assert caplog.records == []


def test_recuperar_geometria_false_preserva_el_comportamiento_previo():
    """El parametro que usa `_poligonos_cerrados_por_capa` (heuristico de
    capas): con `recuperar_geometria=False` el flag DXF es la unica fuente,
    exactamente como antes de este cambio."""
    doc, e = _doc_con_polilinea([(0, 0), (6, 0), (6, 4), (0, 4), (0, 0)], closed=False)
    assert parser._esta_cerrada(e) is True
    assert parser._esta_cerrada(e, recuperar_geometria=False) is False


def test_tipo_no_soportado_sigue_fuera_de_alcance():
    """HATCH/SPLINE/LINE no son LWPOLYLINE ni POLYLINE: la recuperacion
    geometrica no les aplica, igual que antes de este cambio. Este fallo es,
    a proposito, solo sobre el flag `closed` de una polilinea -- no una
    ampliacion del tipo de geometria que ArchMuse sabe leer."""
    doc = ezdxf.new("R2010")
    doc.layers.add(parser.AREA_LAYER)
    msp = doc.modelspace()
    linea = msp.add_line((0, 0), (6, 0), dxfattribs={"layer": parser.AREA_LAYER})
    assert parser._esta_cerrada(linea) is False


def test_polyline_clasica_closed_true_sin_cambios():
    """POLYLINE (formato antiguo, no LWPOLYLINE) con flag ya correcto: la
    rama del flag sigue intacta."""
    doc = ezdxf.new("R2010")
    doc.layers.add(parser.AREA_LAYER)
    msp = doc.modelspace()
    entidad = msp.add_polyline2d(
        [(0, 0), (6, 0), (6, 4), (0, 4)], close=True, dxfattribs={"layer": parser.AREA_LAYER}
    )
    assert parser._esta_cerrada(entidad) is True


# ---------------------------------------------------------------------------
# El heuristico de capas no cambia de comportamiento (no se toca a proposito)
# ---------------------------------------------------------------------------


def test_capas_candidatas_no_cuenta_la_polilinea_recuperada():
    """`_poligonos_cerrados_por_capa` (de donde sale `capas_candidatas`) debe
    seguir contando solo lo que ya contaba antes -- la recuperacion de cierre
    es del lector de habitaciones, no del heuristico de capa."""
    doc = ezdxf.new("R2010")
    doc.layers.add(parser.AREA_LAYER)
    msp = doc.modelspace()

    # El "salon" con closed=False y extremos casi coincidentes: se recupera
    # para LEER habitaciones, pero no debe contar aqui.
    msp.add_lwpolyline(
        [(0, 0), (6, 0), (6, 4), (0, 4), (0, 0)], close=False, dxfattribs={"layer": parser.AREA_LAYER}
    )
    msp.add_mtext("Salón/cocina", dxfattribs={"layer": parser.AREA_LAYER}).set_location((3, 2))

    # Tres habitaciones mas, bien cerradas, para superar MINIMO_POLIGONOS_CAPA.
    for i, nombre in enumerate(["Dormitorio 1", "Dormitorio 2", "Baño"]):
        x0 = 7.0 + i * 4
        pts = [(x0, 0), (x0 + 3, 0), (x0 + 3, 3), (x0, 3)]
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": parser.AREA_LAYER})
        msp.add_mtext(nombre, dxfattribs={"layer": parser.AREA_LAYER}).set_location((x0 + 1.5, 1.5))

    poligonos = parser._poligonos_cerrados_por_capa(doc)
    assert len(poligonos[parser.AREA_LAYER]) == 3, "el salon casi-cerrado no debe contar aqui"


# ---------------------------------------------------------------------------
# End-to-end sintetico: una vivienda "VT1/3" con el mismo patron que en
# V5.dxf/v2s.dxf, sin depender de ningun archivo real
# ---------------------------------------------------------------------------

# Geometria en METROS ($INSUNITS=6): salon 6x4=24 m2, dormitorios y anexos de
# tamano plausible, todo en el rango que `analyzer/escala.py` acepta sin
# preguntar.
_ROOMS_VT1_3 = [
    ("Dormitorio 1", 7.0, 0.0, 4.0, 3.0),
    ("Dormitorio 2", 7.0, 3.5, 3.0, 3.0),
    ("Dormitorio 3", 10.5, 3.5, 3.0, 3.0),
    ("Aseo", 7.0, 7.0, 2.0, 2.0),
    ("Baño", 9.5, 7.0, 2.0, 2.0),
    ("Terraza", 0.0, 4.5, 3.0, 3.0),
    ("Tendedero", 3.5, 4.5, 2.0, 2.0),
]


def _construir_plano_vt1_3(hueco_salon: float):
    """Reproduce, en miniatura, el patron real de V5.dxf/v2s.dxf: un
    "Salón/cocina" con `closed=False` cuyo ultimo vertice esta desplazado
    `hueco_salon` unidades del primero, mas el resto de una vivienda de 3
    dormitorios ya bien cerrada."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6  # metros
    doc.layers.add(parser.AREA_LAYER)
    msp = doc.modelspace()

    salon = [(0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0), (hueco_salon, 0.0)]
    msp.add_lwpolyline(salon, close=False, dxfattribs={"layer": parser.AREA_LAYER})
    msp.add_mtext("Salón/cocina", dxfattribs={"layer": parser.AREA_LAYER}).set_location((3.0, 2.0))

    for nombre, x0, y0, ancho, alto in _ROOMS_VT1_3:
        pts = [(x0, y0), (x0 + ancho, y0), (x0 + ancho, y0 + alto), (x0, y0 + alto)]
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": parser.AREA_LAYER})
        msp.add_mtext(nombre, dxfattribs={"layer": parser.AREA_LAYER}).set_location(
            (x0 + ancho / 2, y0 + alto / 2)
        )

    msp.add_mtext("VT1/3", dxfattribs={"layer": parser.AREA_LAYER}).set_location((-3.0, 2.0))
    return doc


def _unidad_vt1_3(doc):
    plano = parser.leer_plano(doc)
    unidades = evaluator.group_rooms_by_unit_label(plano.rooms, plano.unit_labels)
    assert len(unidades) == 1, [u.name for u in unidades]
    return unidades[0]


def test_vt1_3_sintetico_recupera_el_salon(caplog):
    """El caso pedido explicitamente: con el mismo patron que V5.dxf/v2s.dxf
    (extremos EXACTAMENTE coincidentes), VT1/3 vuelve a detectar su
    "Salón/cocina"."""
    doc = _construir_plano_vt1_3(hueco_salon=0.0)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        vt1_3 = _unidad_vt1_3(doc)
    labels = [r.label for r in vt1_3.rooms]
    assert any(l and "ocina" in l for l in labels), labels
    assert len(vt1_3.rooms) == len(_ROOMS_VT1_3) + 1, labels
    assert any("tratada como cerrada" in r.getMessage() for r in caplog.records)


def test_vt1_3_sintetico_hueco_pequeno_tambien_se_recupera(caplog):
    """Igual que el anterior pero con un hueco pequeno y no nulo (0.03
    unidades, el orden de magnitud medido en V5.dxf para otra polilinea del
    mismo plano) -- sigue dentro de tolerancia."""
    doc = _construir_plano_vt1_3(hueco_salon=0.03)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        vt1_3 = _unidad_vt1_3(doc)
    labels = [r.label for r in vt1_3.rooms]
    assert any(l and "ocina" in l for l in labels), labels


def test_vt1_3_sintetico_gap_grande_no_se_recupera(caplog):
    """Con un hueco grande (mayor que el propio salon) la polilinea es
    abierta de verdad: sigue sin leerse, exactamente igual que antes de este
    cambio -- y sin ningun aviso, porque no hay nada que recuperar."""
    doc = _construir_plano_vt1_3(hueco_salon=5.0)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        vt1_3 = _unidad_vt1_3(doc)
    labels = [r.label for r in vt1_3.rooms]
    assert not any(l and "ocina" in l for l in labels), labels
    assert len(vt1_3.rooms) == len(_ROOMS_VT1_3), labels


# ---------------------------------------------------------------------------
# Regresion sobre los dos proyectos reales, si estan disponibles en esta
# maquina (ver docstring del modulo: no se versionan, no se fuerza su
# presencia, ninguna ruta de una maquina concreta queda escrita en el codigo)
# ---------------------------------------------------------------------------


def _ruta_proyecto_real(nombre: str):
    candidatas = [
        os.path.join(os.path.dirname(RAIZ), nombre),
        os.path.join(os.path.expanduser("~"), "Desktop", nombre),
    ]
    return next((c for c in candidatas if os.path.isfile(c)), None)


@pytest.mark.parametrize("nombre", ["V5.dxf", "v2s.dxf"])
def test_regresion_vt1_3_recupera_salon_en_proyecto_real(nombre, caplog):
    ruta = _ruta_proyecto_real(nombre)
    if ruta is None:
        pytest.skip(
            "%s no esta disponible en esta maquina (proyecto real de cliente, "
            "no versionado)" % nombre
        )
    doc = parser.load_document(ruta)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        plano = parser.leer_plano(doc)
    unidades = evaluator.group_rooms_by_unit_label(plano.rooms, plano.unit_labels)
    vt1_3 = next((u for u in unidades if u.name == "VT1/3"), None)
    assert vt1_3 is not None, [u.name for u in unidades]
    labels = [r.label for r in vt1_3.rooms]
    assert any(l and "ocina" in l for l in labels), labels
    assert any("tratada como cerrada" in r.getMessage() for r in caplog.records)
