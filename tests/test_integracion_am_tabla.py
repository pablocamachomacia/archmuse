# -*- coding: utf-8 -*-
"""Cierre de la integración del contrato de clasificación DXF `AM_*`
(`AM_UTIL_INT`/`AM_CONS_CER`/`AM_UTIL_EXT`/`AM_CONS_EXT`) hasta la tabla que
ve el arquitecto.

Ejecutar:  python -m pytest tests/test_integracion_am_tabla.py -v

A diferencia de `tests/test_capas_am.py` y `tests/test_validacion_capas_am.py`
(que prueban `parser.py`/`evaluator.py`/`validacion_capas.py` como unidades
sueltas), este fichero recorre la cadena REAL y completa, sin sustituir nada:

    DXF (ezdxf, guardado a disco) -> POST /api/analizar (Flask)
    -> parser.leer_plano -> evaluator.asignar_envolvente_cerrada /
       asignar_superficies_exteriores -> validacion_capas.validar_capas_am
    -> api_serializer.serialize_analysis -> JSON de "viviendas"
       (lo que pinta static/app.js, `modoEspacioHtml`/`capasAmHtml`).

Qué protege, por bloque:

A. Las 4 capas AM_* simultáneamente, sin mezclarse entre sí ni con
   `superficie_total_m2`.
B. Solo algunas capas presentes (recintos heredados + AM_UTIL_EXT).
C. Varias superficies útiles exteriores en la misma vivienda (no es
   ambigüedad, a diferencia de D).
D. Envolvente cerrada ambigua (dos candidatas para la misma vivienda):
   `envolvente_cerrada_m2` se queda en null y aparece un diagnóstico
   ENVOLVENTE_AMBIGUA.
E. Geometría inválida en una capa AM_*: descartada, inventariada en
   "geometria_no_leida" y diagnosticada con severidad ERROR.
F. Plano antiguo sin ninguna capa AM_*: regresión bit a bit (las tres listas
   nuevas vacías, "clasificacion_capas" = "heredado", superficie_total_m2 sin
   tocar).
G. Diagnósticos adicionales (capa casi correcta, capa reservada en uso)
   llegan tal cual al JSON.
H. VIVIENDA_SIN_ENVOLVENTE llega al JSON con la vivienda exacta que le falta,
   sin marcar la que sí tiene la suya (cierre de la auditoría 2026-08-13).
I. ENVOLVENTE_SIN_VIVIENDA en sus dos variantes -- etiqueta VT sin ninguna
   habitación agrupada, y plano sin ninguna etiqueta VT en absoluto -- con el
   campo "vivienda" tal cual lo necesita el filtro de `static/app.js`
   (`diagnosticosCapasAmSinVivienda`: sin nombre, o con un nombre que no está
   en "viviendas") para decidir la entrada de PROYECTO en vez de la local.
J. Polilínea abierta en una capa AM_* operativa: MOTIVO_POLILINEA_ABIERTA
   llega como diagnóstico WARNING, igual que su gemelo ya cubierto en E
   (MOTIVO_GEOMETRIA_INVALIDA, severidad ERROR).
"""
from __future__ import annotations

import os
import sys
import tempfile
from io import BytesIO

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

# Mismo patrón que tests/golden.py y tests/test_analizar_planta.py: entorno
# determinista y aislado ANTES de importar `analyzer/`/`app` -- sin API key
# (sin red, sin coste) y con la base de datos en un directorio temporal.
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.setdefault("ARCHMUSE_DATA_DIR", tempfile.mkdtemp(prefix="archmuse_test_am_tabla_"))

import ezdxf  # noqa: E402

from analyzer import storage  # noqa: E402

storage.init_db()

import app as app_module  # noqa: E402  (después de fijar ARCHMUSE_DATA_DIR)
from analyzer import parser  # noqa: E402

CLIENTE = app_module.app.test_client()


# ---------------------------------------------------------------------------
# Helpers de construcción -- mismo estilo que tests/test_capas_am.py y
# tests/test_validacion_capas_am.py, sin reimplementar nada de `leer_plano`.
# ---------------------------------------------------------------------------


def _doc_vacio(*capas):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6  # metros
    for capa in capas:
        doc.layers.add(capa)
    return doc


def _rect(msp, capa, x0, y0, ancho, alto, etiqueta=None, closed=True):
    pts = [(x0, y0), (x0 + ancho, y0), (x0 + ancho, y0 + alto), (x0, y0 + alto)]
    msp.add_lwpolyline(pts, close=closed, dxfattribs={"layer": capa})
    if etiqueta:
        msp.add_mtext(etiqueta, dxfattribs={"layer": capa}).set_location(
            (x0 + ancho / 2, y0 + alto / 2)
        )


def _analizar(doc, tmp_path, nombre="plano.dxf"):
    """Guarda `doc` a disco y lo sube tal cual a `POST /api/analizar` -- el
    mismo camino que recorre un DXF real subido desde la SPA, sin sustituir
    `load_document` ni `leer_plano` (a diferencia de la sección H de
    `tests/test_analizar_planta.py`, que sí los sustituye por un doble)."""
    ruta = os.path.join(str(tmp_path), nombre)
    doc.saveas(ruta)
    with open(ruta, "rb") as fh:
        datos = {"dxf": (BytesIO(fh.read()), nombre)}
        resp = CLIENTE.post("/api/analizar", data=datos, content_type="multipart/form-data")
    assert resp.status_code == 200, "esperaba 200, obtuvo %d: %s" % (
        resp.status_code, resp.get_data(as_text=True)[:500]
    )
    return resp.get_json()


def _vivienda(payload, nombre="VT1/1"):
    encontradas = [v for v in payload["viviendas"] if v["nombre"] == nombre]
    assert encontradas, "no se encontró la vivienda %r entre %r" % (
        nombre, [v["nombre"] for v in payload["viviendas"]]
    )
    return encontradas[0]


def _por_codigo(payload, codigo):
    return [d for d in payload["diagnosticos_clasificacion"] if d["codigo"] == codigo]


# ---------------------------------------------------------------------------
# A. Las 4 capas AM_* simultáneamente
# ---------------------------------------------------------------------------


def test_las_cuatro_capas_simultaneamente(tmp_path):
    doc = _doc_vacio(
        parser.CAPA_UTIL_INTERIOR, parser.CAPA_CONSTRUIDA_CERRADA,
        parser.CAPA_UTIL_EXTERIOR, parser.CAPA_CONSTRUIDA_EXTERIOR,
    )
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))
    _rect(msp, parser.CAPA_CONSTRUIDA_CERRADA, -0.3, -0.3, 6.6, 4.6)
    _rect(msp, parser.CAPA_UTIL_EXTERIOR, 7, 0, 3, 2, "Terraza")
    _rect(msp, parser.CAPA_CONSTRUIDA_EXTERIOR, 6.9, -0.3, 3.2, 2.6)

    payload = _analizar(doc, tmp_path)
    v = _vivienda(payload)

    assert v["superficie_total_m2"] == 24.0  # solo el Salón/cocina, sin tocar
    assert v["envolvente_cerrada_m2"] == round(6.6 * 4.6, 2)
    assert v["superficie_util_exterior_m2"] == 6.0
    assert v["envolvente_exterior_m2"] == round(3.2 * 2.6, 2)
    assert v["clasificacion_capas"] == "am"

    assert sorted(payload["capas_am_detectadas"]) == sorted([
        parser.CAPA_UTIL_INTERIOR, parser.CAPA_CONSTRUIDA_CERRADA,
        parser.CAPA_UTIL_EXTERIOR, parser.CAPA_CONSTRUIDA_EXTERIOR,
    ])
    assert payload["geometria_no_leida"] == []
    assert payload["diagnosticos_clasificacion"] == []


# ---------------------------------------------------------------------------
# B. Solo algunas capas presentes: recintos heredados + AM_UTIL_EXT
# ---------------------------------------------------------------------------


def test_solo_algunas_capas_presentes_heredado_mas_util_ext(tmp_path):
    doc = _doc_vacio(parser.AREA_LAYER, parser.CAPA_UTIL_EXTERIOR)
    msp = doc.modelspace()
    _rect(msp, parser.AREA_LAYER, 0, 0, 6, 4, "Salón/cocina")
    _rect(msp, parser.AREA_LAYER, 7, 0, 4, 3, "Dormitorio 1")
    _rect(msp, parser.AREA_LAYER, 12, 0, 3, 3, "Baño")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.AREA_LAYER}).set_location((-3, 2))
    _rect(msp, parser.CAPA_UTIL_EXTERIOR, 20, 0, 3, 2, "Terraza")

    payload = _analizar(doc, tmp_path)
    v = _vivienda(payload)

    assert v["clasificacion_capas"] == "heredado"  # rooms de "00 areas", no de AM_UTIL_INT
    assert v["envolvente_cerrada_m2"] is None
    assert v["superficie_util_exterior_m2"] == 6.0
    assert v["envolvente_exterior_m2"] == 0.0
    assert payload["capas_am_detectadas"] == [parser.CAPA_UTIL_EXTERIOR]


# ---------------------------------------------------------------------------
# C. Varias terrazas en la misma vivienda -- no es ambigüedad
# ---------------------------------------------------------------------------


def test_varias_terrazas_en_la_misma_vivienda(tmp_path):
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, parser.CAPA_UTIL_EXTERIOR)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))
    _rect(msp, parser.CAPA_UTIL_EXTERIOR, 7, 0, 3, 2, "Terraza A")
    _rect(msp, parser.CAPA_UTIL_EXTERIOR, 7, 3, 3, 2, "Terraza B")

    payload = _analizar(doc, tmp_path)
    v = _vivienda(payload)

    assert v["superficie_util_exterior_m2"] == 12.0  # las dos, sumadas
    assert payload["diagnosticos_clasificacion"] == []  # ninguna ambigüedad


# ---------------------------------------------------------------------------
# D. Envolvente cerrada ambigua
# ---------------------------------------------------------------------------


def test_envolvente_ambigua(tmp_path):
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, parser.CAPA_CONSTRUIDA_CERRADA)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))
    # Dos envolventes, ambas mas cerca de VT1/1 que de cualquier otra
    # etiqueta (no hay otra en este plano): ambigüedad real, ninguna se elige.
    _rect(msp, parser.CAPA_CONSTRUIDA_CERRADA, -0.3, -0.3, 6.6, 4.6)
    _rect(msp, parser.CAPA_CONSTRUIDA_CERRADA, -0.5, -0.5, 7.0, 5.0)

    payload = _analizar(doc, tmp_path)
    v = _vivienda(payload)

    assert v["envolvente_cerrada_m2"] is None

    ambiguas = _por_codigo(payload, "ENVOLVENTE_AMBIGUA")
    assert len(ambiguas) == 1
    assert ambiguas[0]["severidad"] == "WARNING"
    assert ambiguas[0]["vivienda"] == "VT1/1"


# ---------------------------------------------------------------------------
# E. Geometría inválida en una capa AM_*
# ---------------------------------------------------------------------------


def test_geometria_invalida_en_capa_am(tmp_path):
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, parser.CAPA_UTIL_EXTERIOR)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))
    bowtie = [(10, 0), (14, 4), (14, 0), (10, 4)]  # autointersecante, is_valid == False
    msp.add_lwpolyline(bowtie, close=True, dxfattribs={"layer": parser.CAPA_UTIL_EXTERIOR})

    payload = _analizar(doc, tmp_path)
    v = _vivienda(payload)

    assert v["superficie_util_exterior_m2"] == 0.0

    descartes = [d for d in payload["geometria_no_leida"] if d["capa"] == parser.CAPA_UTIL_EXTERIOR]
    assert len(descartes) == 1
    assert descartes[0]["motivo"] == parser.MOTIVO_GEOMETRIA_INVALIDA
    assert descartes[0]["detalle"] != ""

    diagnosticos = _por_codigo(payload, parser.MOTIVO_GEOMETRIA_INVALIDA)
    assert len(diagnosticos) == 1
    assert diagnosticos[0]["severidad"] == "ERROR"
    assert diagnosticos[0]["capa"] == parser.CAPA_UTIL_EXTERIOR


# ---------------------------------------------------------------------------
# F. Plano antiguo sin ninguna capa AM_* -- regresión completa
# ---------------------------------------------------------------------------


def test_plano_antiguo_sin_am_regresion(tmp_path):
    doc = _doc_vacio(parser.AREA_LAYER)
    msp = doc.modelspace()
    _rect(msp, parser.AREA_LAYER, 0, 0, 6, 4, "Salón/cocina")
    _rect(msp, parser.AREA_LAYER, 7, 0, 4, 3, "Dormitorio 1")
    _rect(msp, parser.AREA_LAYER, 12, 0, 3, 3, "Baño")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.AREA_LAYER}).set_location((-3, 2))

    payload = _analizar(doc, tmp_path)
    v = _vivienda(payload)

    assert v["clasificacion_capas"] == "heredado"
    assert v["envolvente_cerrada_m2"] is None
    assert v["superficie_util_exterior_m2"] == 0.0
    assert v["envolvente_exterior_m2"] == 0.0
    # Nada de lo que ya existía cambia: la misma suma de las 3 habitaciones
    # de siempre (24 + 12 + 9), sin ninguna contribución AM_*.
    assert v["superficie_total_m2"] == 24.0 + 12.0 + 9.0

    assert payload["capas_am_detectadas"] == []
    assert payload["geometria_no_leida"] == []
    assert payload["diagnosticos_clasificacion"] == []


# ---------------------------------------------------------------------------
# G. Diagnósticos adicionales (capa casi correcta, reservada en uso)
# ---------------------------------------------------------------------------


def test_diagnosticos_casi_correcta_y_reservada_llegan_al_json(tmp_path):
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, "AM_UTIL_INT_", parser.CAPA_DESCUENTO)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))
    _rect(msp, parser.CAPA_DESCUENTO, 20, 0, 2, 2)  # capa reservada, con contenido

    payload = _analizar(doc, tmp_path)

    casi = _por_codigo(payload, "CAPA_CASI_CORRECTA")
    assert len(casi) == 1
    assert casi[0]["capa"] == "AM_UTIL_INT_"

    reservada = _por_codigo(payload, "RESERVADA_NO_OPERATIVA")
    assert len(reservada) == 1
    assert reservada[0]["capa"] == parser.CAPA_DESCUENTO
    assert reservada[0]["severidad"] == "INFO"


# ---------------------------------------------------------------------------
# H. VIVIENDA_SIN_ENVOLVENTE -- dos viviendas, solo una tiene envolvente
# ---------------------------------------------------------------------------


def test_vivienda_sin_envolvente_llega_al_json(tmp_path):
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, parser.CAPA_CONSTRUIDA_CERRADA)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 20, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT2/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((17, 2))
    # Envolvente SOLO para VT1/1 -- VT2/1 se queda sin ninguna.
    _rect(msp, parser.CAPA_CONSTRUIDA_CERRADA, -0.3, -0.3, 6.6, 4.6)

    payload = _analizar(doc, tmp_path)
    v1 = _vivienda(payload, "VT1/1")
    v2 = _vivienda(payload, "VT2/1")

    assert v1["envolvente_cerrada_m2"] is not None
    assert v2["envolvente_cerrada_m2"] is None

    sin_envolvente = _por_codigo(payload, "VIVIENDA_SIN_ENVOLVENTE")
    assert len(sin_envolvente) == 1
    assert sin_envolvente[0]["vivienda"] == "VT2/1"
    assert sin_envolvente[0]["severidad"] == "WARNING"
    # VT1/1 SI tiene envolvente: no debe aparecer también como sin ella --
    # partición exhaustiva y sin solape con ENVOLVENTE_AMBIGUA (ya cubierta
    # en el bloque D de este mismo fichero).
    assert "VT1/1" not in {d["vivienda"] for d in sin_envolvente}
    assert _por_codigo(payload, "ENVOLVENTE_AMBIGUA") == []


# ---------------------------------------------------------------------------
# I. ENVOLVENTE_SIN_VIVIENDA -- dos variantes, con el campo "vivienda" tal
#    cual lo necesita el filtro de la entrada de PROYECTO en static/app.js
# ---------------------------------------------------------------------------


def test_envolvente_sin_vivienda_etiqueta_sin_habitaciones(tmp_path):
    """Hay una etiqueta VT en el plano (VT9/9) pero ninguna habitación
    agrupada bajo ella: la envolvente más cercana a esa etiqueta no tiene
    Unit final a la que asignarse. El nombre de la etiqueta SÍ viaja en
    "vivienda", pero no coincide con ninguna de "viviendas" -- exactamente el
    caso límite §6.3 del PRD que `diagnosticosCapasAmSinVivienda()` resuelve
    (`nombres.indexOf(d.vivienda) === -1`), no `diagnosticosCapasAmDeVivienda`."""
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, parser.CAPA_CONSTRUIDA_CERRADA)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))
    _rect(msp, parser.CAPA_CONSTRUIDA_CERRADA, -0.3, -0.3, 6.6, 4.6)  # la de VT1/1
    # Etiqueta sin ninguna habitación cerca, con una envolvente junto a ella.
    msp.add_mtext("VT9/9", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((50, 50))
    _rect(msp, parser.CAPA_CONSTRUIDA_CERRADA, 49, 49, 3, 3)

    payload = _analizar(doc, tmp_path)
    nombres_viviendas = {v["nombre"] for v in payload["viviendas"]}
    assert nombres_viviendas == {"VT1/1"}  # VT9/9 nunca se convierte en Unit

    huerfanas = _por_codigo(payload, "ENVOLVENTE_SIN_VIVIENDA")
    assert len(huerfanas) == 1
    assert huerfanas[0]["vivienda"] == "VT9/9"
    assert huerfanas[0]["severidad"] == "WARNING"
    # Tal cual lo consume `diagnosticosCapasAmSinVivienda()`: el nombre no
    # está entre las viviendas finales, así que cae en la entrada de proyecto.
    assert huerfanas[0]["vivienda"] not in nombres_viviendas


def test_envolvente_sin_vivienda_sin_ninguna_etiqueta_vt(tmp_path):
    """Plano sin ninguna etiqueta VT en absoluto: la envolvente se reporta
    huérfana con "vivienda" vacío -- el otro caso que
    `diagnosticosCapasAmSinVivienda()` cubre (`!d.vivienda`)."""
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, parser.CAPA_CONSTRUIDA_CERRADA)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")  # sin etiqueta VT
    _rect(msp, parser.CAPA_CONSTRUIDA_CERRADA, -0.3, -0.3, 6.6, 4.6)

    payload = _analizar(doc, tmp_path)

    huerfanas = _por_codigo(payload, "ENVOLVENTE_SIN_VIVIENDA")
    assert len(huerfanas) == 1
    assert huerfanas[0]["vivienda"] == ""
    assert not huerfanas[0]["vivienda"]  # falsy en JS: `!d.vivienda` es true


# ---------------------------------------------------------------------------
# J. Polilínea abierta en una capa AM_* operativa
# ---------------------------------------------------------------------------


def test_polilinea_abierta_en_capa_am_llega_al_json(tmp_path):
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, parser.CAPA_UTIL_EXTERIOR)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))
    # Polilínea ABIERTA (closed=False, primer/último vértice lejos entre sí:
    # no la recupera la tolerancia de cierre) en una capa AM_* operativa.
    msp.add_lwpolyline(
        [(10, 0), (13, 0), (13, 2)], close=False,
        dxfattribs={"layer": parser.CAPA_UTIL_EXTERIOR},
    )

    payload = _analizar(doc, tmp_path)
    v = _vivienda(payload)
    assert v["superficie_util_exterior_m2"] == 0.0  # la abierta no cuenta

    descartes = [d for d in payload["geometria_no_leida"] if d["capa"] == parser.CAPA_UTIL_EXTERIOR]
    assert len(descartes) == 1
    assert descartes[0]["motivo"] == parser.MOTIVO_POLILINEA_ABIERTA

    diagnosticos = _por_codigo(payload, parser.MOTIVO_POLILINEA_ABIERTA)
    assert len(diagnosticos) == 1
    assert diagnosticos[0]["severidad"] == "WARNING"
    assert diagnosticos[0]["capa"] == parser.CAPA_UTIL_EXTERIOR
