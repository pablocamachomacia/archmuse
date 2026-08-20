# -*- coding: utf-8 -*-
"""`POST /api/preguntar` — la primera puerta de conversación real (sesión
2026-08-19, noche): intención -> ¿hay una Skill registrada que la resuelva?
-> se ejecuta de verdad -> se responde con lo que produjo. Nada más.

Ejecutar:  pytest tests/test_preguntar_endpoint.py

El criterio que más importa, y el que se comprueba contando llamadas al
cliente guionizado, no leyendo el texto (mismo principio que
`tests/test_copiloto_endpoint.py`):

**Cuando la pregunta no coincide con ninguna capacidad registrada, el LLM
NUNCA hace una segunda llamada para "ayudar" con conocimiento general.** Una
sola llamada de clasificación, y se acabó — coincide o no coincide, no hay
una tercera vía donde el modelo redacta una respuesta por su cuenta.
"""
from __future__ import annotations

import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

_TMP_DATA = tempfile.mkdtemp(prefix="archmuse_test_preguntar_")
os.environ.setdefault("ARCHMUSE_DATA_DIR", _TMP_DATA)

from analyzer import storage  # noqa: E402
storage.init_db()

import app as app_module  # noqa: E402
from scripts.generar_acta_legible_demo import _construir_dxf_sintetico  # noqa: E402
from tests.test_agente_nucleo import (  # noqa: E402
    BloqueHerramienta, RespuestaFalsa, ClienteGuionizado,
)

SKILL = "superficies.medicion_de_planta"


@pytest.fixture(scope="module")
def dxf_bytes() -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        ruta = _construir_dxf_sintetico(Path(tmp))
        return Path(ruta).read_bytes()


@pytest.fixture()
def cliente_http(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-no-es-una-clave-real")
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def _guionizar(monkeypatch, *turnos):
    doble = ClienteGuionizado(*turnos)
    monkeypatch.setattr("ia.cliente.crear_cliente", lambda *a, **k: doble)
    return doble


def _pedir(http, pregunta, dxf_bytes=None, nombre_dxf="planta_sintetica.dxf",
           autorizar_efectos=True):
    # `autorizar_efectos` por defecto en `True`: la mayoría de los tests de
    # este fichero prueban la clasificación, no `SEG-1` -- el camino sin
    # autorizar tiene su propio test explícito, más abajo.
    data = {"pregunta": pregunta}
    if dxf_bytes is not None:
        data["dxf"] = (BytesIO(dxf_bytes), nombre_dxf)
    if autorizar_efectos:
        data["autorizar_efectos"] = "1"
    return http.post("/api/preguntar", data=data, content_type="multipart/form-data")


# --- Validación de entrada, sin llegar a la IA ------------------------------

def test_sin_pregunta_da_400_no_500(cliente_http, dxf_bytes):
    resp = _pedir(cliente_http, "", dxf_bytes)
    assert resp.status_code == 400
    assert resp.get_json().get("error")


def test_sin_dxf_da_400_no_500(cliente_http):
    resp = _pedir(cliente_http, "¿cuánta superficie útil tiene esta planta?")
    assert resp.status_code == 400
    assert resp.get_json().get("error")


def test_sin_api_key_da_503_explicito(monkeypatch, dxf_bytes):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app_module.app.config["TESTING"] = True
    http = app_module.app.test_client()
    resp = _pedir(http, "¿cuánta superficie útil tiene esta planta?", dxf_bytes)
    assert resp.status_code == 503
    assert resp.get_json().get("codigo") == "ia_no_disponible"


# --- El criterio central: coincide -> Skill real, no coincide -> nunca inventa --

def test_pregunta_que_coincide_ejecuta_la_skill_de_verdad(cliente_http, monkeypatch, dxf_bytes):
    """Una sola llamada al modelo (clasificar), y el resto es la Skill real
    -- mismo camino que `/api/acta-legible`: el caso conocido (VT1/1, solape)
    llega renderizado con su porqué y su cifra."""
    doble = _guionizar(monkeypatch, RespuestaFalsa(
        BloqueHerramienta("clasificar_pregunta", {"capacidad": SKILL})))

    resp = _pedir(cliente_http, "¿cuánta superficie útil tiene esta planta?", dxf_bytes)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
    datos = resp.get_json()

    assert datos["coincide"] is True
    assert datos["capacidad"] == SKILL
    assert "VT1/1" in datos["html"]
    assert "class='porque'" in datos["html"]
    assert "class='cifra'" in datos["html"]
    # Una única llamada al modelo: clasificar, no "clasificar + redactar".
    assert len(doble.llamadas) == 1


def test_sin_autorizar_efectos_pide_confirmacion_y_no_ejecuta_la_skill(cliente_http, monkeypatch, dxf_bytes):
    """`SEG-1` (`docs/AGENTE_BACKLOG.md` §11): aunque la pregunta coincide con
    la Skill, sin `autorizar_efectos` el endpoint se para antes de que la
    Skill escriba su informe PDF intermedio -- 428, no 200, con la solicitud
    estructurada que la interfaz tendría que preguntar."""
    doble = _guionizar(monkeypatch, RespuestaFalsa(
        BloqueHerramienta("clasificar_pregunta", {"capacidad": SKILL})))

    resp = _pedir(cliente_http, "¿cuánta superficie útil tiene esta planta?", dxf_bytes,
                  autorizar_efectos=False)
    assert resp.status_code == 428, resp.get_data(as_text=True)[:500]
    cuerpo = resp.get_json()
    assert cuerpo["confirmacion_requerida"] is True
    assert cuerpo["solicitud"]["quien"] == "api:preguntar"
    # La clasificación sí ocurrió (es previa a ejecutar la Skill) -- lo que
    # no ocurrió es la ejecución de la Skill misma.
    assert len(doble.llamadas) == 1


def test_pregunta_que_no_coincide_nunca_inventa_una_respuesta(cliente_http, monkeypatch, dxf_bytes):
    """La regla de oro, en su forma más simple: sin Skill que la resuelva,
    ArchMuse lo dice explícitamente y no hay una segunda llamada al modelo
    intentando responder con conocimiento general."""
    doble = _guionizar(monkeypatch, RespuestaFalsa(
        BloqueHerramienta("clasificar_pregunta", {"capacidad": None})))

    resp = _pedir(cliente_http, "¿cuánto va a costar este proyecto?", dxf_bytes)
    assert resp.status_code == 200
    datos = resp.get_json()

    assert datos["coincide"] is False
    assert "no tiene todavía" in datos["mensaje"]
    assert "capacidad" not in datos
    assert "html" not in datos
    # Ni una sola llamada de más: se paró en la clasificación.
    assert len(doble.llamadas) == 1


def test_una_capacidad_inventada_por_el_modelo_se_trata_como_no_coincide(cliente_http, monkeypatch, dxf_bytes):
    """Defensa en profundidad: aunque el `enum` de la herramienta ya se lo
    impide al modelo, si por lo que sea devolviera un id que no está en el
    catálogo real, el servidor no se fía de él -- lo trata como `None`."""
    doble = _guionizar(monkeypatch, RespuestaFalsa(
        BloqueHerramienta("clasificar_pregunta", {"capacidad": "normativa.consultar_cte"})))

    resp = _pedir(cliente_http, "¿qué dice el CTE sobre esto?", dxf_bytes)
    datos = resp.get_json()

    assert datos["coincide"] is False
    assert len(doble.llamadas) == 1


def test_la_pagina_aparte_ya_no_existe(cliente_http):
    """Sesión 2026-08-19 (noche 4): la interfaz de conversación se movió
    dentro de la SPA (`#conversacion-archmuse` en `static/index.html`) --
    `/preguntar` como página aparte queda retirada, no duplicada."""
    resp = cliente_http.get("/preguntar")
    assert resp.status_code == 404


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
