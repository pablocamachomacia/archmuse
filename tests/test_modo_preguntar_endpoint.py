# -*- coding: utf-8 -*-
"""Modo preguntar por la vía del comando: preguntas, respuestas y guardado por plano.

PRD `docs/prd/2026-09-17-modo-preguntar.md`. Reproduce las peticiones del `.lsp`
3.10.0 contra el servidor, con el plano sintético de `test_modo_preguntar.py`:
el clic, la medición con `preguntar`, las respuestas de vuelta con `preguntas_hechas`,
la polilínea marcada viajando con su respuesta, y una segunda pasada que ya no pregunta.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import respuestas_del_arquitecto as rda  # noqa: E402
from analyzer.geometria_recibida import payload_desde_dxf  # noqa: E402
from tests import test_modo_preguntar as sintetico  # noqa: E402
from tests._carpetas_temporales import carpeta_temporal_de_test  # noqa: E402

PLANO = r"C:\Proyectos\Bloque\plantas.dwg"
PUNTO = [3.0, 2.5]


@pytest.fixture(scope="module")
def client():
    import app as modulo

    modulo.app.config["TESTING"] = True
    with modulo.app.test_client() as cliente:
        yield cliente


@pytest.fixture
def datos(monkeypatch):
    carpeta = carpeta_temporal_de_test("archmuse_test_datos_preguntar_")
    monkeypatch.setenv("ARCHMUSE_DATA_DIR", carpeta)
    return carpeta


@pytest.fixture(scope="module")
def cuerpo():
    doc, _plano = sintetico._plano()
    return payload_desde_dxf(doc.filename, sintetico.CAPA), doc


def _clic(client, payload, **extra):
    datos = {k: v for k, v in payload.items() if k != "otras_polilineas"}
    datos.update(punto=PUNTO, **extra)
    uno = client.post("/api/vivienda-en-punto", json=datos).get_json()
    assert uno["ok"], uno
    return uno


def _medir(client, payload, uno, otras=None, **extra):
    datos = dict(payload, punto=PUNTO, vivienda=json.loads(uno["vivienda_json"]),
                 otras_polilineas=[] if otras is None else otras, plano=PLANO, preguntar=True,
                 **extra)
    r = client.post("/api/medicion-geometria", json=datos)
    assert r.status_code == 200, r.data[:800]
    (reparto,) = r.get_json()["repartos"]
    assert reparto["ok"], reparto
    return reparto


def _celda(reparto, texto):
    celdas = reparto["cuadro_a_dibujar"]["celdas"]
    fila = next(c["fila"] for c in celdas if c["texto"] == texto and c["columna"] in (0, 2))
    columna = next(c["columna"] for c in celdas if c["texto"] == texto and c["fila"] == fila) + 1
    return next((c["texto"] for c in celdas if c["fila"] == fila and c["columna"] == columna), "")


def test_de_la_primera_pregunta_a_la_tabla_completa_y_la_segunda_vez_sin_preguntas(client, cuerpo, datos):
    payload, doc = cuerpo
    uno = _clic(client, payload, plano=PLANO)
    assert uno["polilineas_del_arquitecto"] == []

    primera = _medir(client, payload, uno)
    (pregunta,) = primera["preguntas_al_arquitecto"]
    assert pregunta["tipo"] == rda.PERTENENCIA and pregunta["texto"] == "¿Pertenece a esta vivienda?"
    assert pregunta["opciones"] == ["Si", "No", "RevisarDespues"]
    assert _celda(primera, "Dormitorio 1") == ""

    segunda = _medir(client, payload, uno, preguntas_hechas=1,
                     respuestas_del_arquitecto=[{"id": pregunta["id"], "valor": "Si"}])
    assert _celda(segunda, "Dormitorio 1") == "16,00 m²"
    assert segunda["respuestas_guardadas"] == 1
    (construida,) = segunda["preguntas_al_arquitecto"]
    assert construida["tipo"] == rda.CONSTRUIDA

    # El comando no manda esa polilínea con las zonas (el plano no la rotula): llega con
    # la respuesta, como la marcaría él con el clic.
    marcada = next(o for o in payload["otras_polilineas"] if o["capa"] == "00 CONSTRUIDA")
    tercera = _medir(client, payload, uno, preguntas_hechas=2, respuestas_del_arquitecto=[
        {"id": construida["id"], "valor": marcada["handle"], "polilinea": marcada}])
    assert _celda(tercera, "S. CONSTRUIDA C.") == "225,20 m²"
    assert tercera["preguntas_al_arquitecto"] == []
    assert set(tercera["confirmadas_por_el_arquitecto"]) == {"Dormitorio 1", "S. CONSTRUIDA C."}
    assert "Confirmado por el arquitecto: 2 datos" in tercera["cuadro_a_dibujar"]["notas_del_dibujo"]

    # Otra pasada del comando sobre el mismo plano: no pregunta, y pide la marcada.
    uno_bis = _clic(client, payload, plano=PLANO)
    assert uno_bis["polilineas_del_arquitecto"] == [marcada["handle"]]
    otra = _medir(client, payload, uno_bis, otras=[marcada])
    assert otra["preguntas_al_arquitecto"] == []
    assert otra["cuadro_a_dibujar"]["celdas"] == tercera["cuadro_a_dibujar"]["celdas"]
    assert otra["respuestas_guardadas"] == 0

    guardado = os.listdir(os.path.join(datos, rda.CARPETA))
    assert len(guardado) == 1
    with open(os.path.join(datos, rda.CARPETA, guardado[0]), encoding="utf-8") as f:
        texto = f.read()
    assert "225" not in texto and "16,00" not in texto, "en el fichero no hay ninguna cifra"


def test_sin_plano_se_aplican_las_respuestas_pero_no_se_guarda_nada(client, cuerpo, datos):
    payload, _doc = cuerpo
    uno = _clic(client, payload)
    datos_peticion = dict(payload, punto=PUNTO, vivienda=json.loads(uno["vivienda_json"]),
                          otras_polilineas=[], preguntar=True)
    r = client.post("/api/medicion-geometria", json=datos_peticion).get_json()
    (pregunta,) = r["repartos"][0]["preguntas_al_arquitecto"]
    r = client.post("/api/medicion-geometria", json=dict(
        datos_peticion, respuestas_del_arquitecto=[{"id": pregunta["id"], "valor": "No"}],
        preguntas_hechas=1)).get_json()
    (reparto,) = r["repartos"]
    assert "Dormitorio 1" not in [c["texto"] for c in reparto["cuadro_a_dibujar"]["celdas"]]
    assert reparto["respuestas_guardadas"] == 0
    assert not os.path.exists(os.path.join(datos, rda.CARPETA))


def test_sin_preguntar_el_comando_anterior_recibe_lo_mismo_que_antes(client, cuerpo, datos):
    payload, _doc = cuerpo
    uno = _clic(client, payload)
    r = client.post("/api/medicion-geometria", json=dict(
        payload, punto=PUNTO, vivienda=json.loads(uno["vivienda_json"]),
        otras_polilineas=[])).get_json()
    (reparto,) = r["repartos"]
    assert reparto["preguntas_al_arquitecto"] == []


def test_revisar_despues_deja_la_celda_pendiente_y_no_se_guarda(client, cuerpo, datos):
    payload, _doc = cuerpo
    uno = _clic(client, payload, plano=PLANO)
    (pregunta,) = _medir(client, payload, uno)["preguntas_al_arquitecto"]
    reparto = _medir(client, payload, uno, preguntas_hechas=1,
                      pendientes_de_confirmar=[pregunta["id"]])
    assert _celda(reparto, "Dormitorio 1") == ""
    assert any("Dormitorio 1" in n["motivo"] and n["motivo"].endswith(rda.PENDIENTE_DE_CONFIRMAR)
               for n in reparto["no_escritas"])
    assert pregunta["id"] not in [q["id"] for q in reparto["preguntas_al_arquitecto"]]
    assert reparto["respuestas_guardadas"] == 0
    assert "1 pendiente de confirmar" in reparto["cuadro_a_dibujar"]["notas_del_dibujo"]


def test_la_respuesta_para_el_comando_lleva_las_preguntas_en_lisp(client, cuerpo, datos):
    payload, _doc = cuerpo
    uno = _clic(client, payload, plano=PLANO)
    datos_peticion = dict(payload, punto=PUNTO, vivienda=json.loads(uno["vivienda_json"]),
                          otras_polilineas=[], plano=PLANO, preguntar=True)
    texto = client.post("/api/medicion-geometria?formato=lisp",
                        json=datos_peticion).get_data(as_text=True)
    assert '("preguntas_al_arquitecto" . ((' in texto
    assert '("texto" . "¿Pertenece a esta vivienda?")' in texto
    assert '("resaltar" . ("' in texto
