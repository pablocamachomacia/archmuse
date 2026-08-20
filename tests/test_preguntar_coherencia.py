# -*- coding: utf-8 -*-
"""`POST /api/preguntar` con `revision.coherencia_del_plano` (Bloque 1,
`docs/design/2026-08-20-reorientacion-estrategica-v1.md` §7/§8).

Ejecutar:  pytest tests/test_preguntar_coherencia.py

Hasta este bloque, esta Skill estaba `HECHO` y probada
(`tests/test_agente_skill_coherencia.py`) pero sin ninguna ruta HTTP que la
alcanzara -- `_SKILLS_DISPONIBLES_PARA_PREGUNTAR` sólo tenía
`superficies.medicion_de_planta`. Este fichero es el mismo tipo de prueba que
`tests/test_preguntar_endpoint.py` ya hace para medición, para la segunda
capacidad: coincide -> se ejecuta de verdad -> `SEG-1` sigue pidiendo
autorización antes de escribir el informe.

Reutiliza el mismo DXF sintético que `test_preguntar_endpoint.py` (tiene un
solape real de propósito, ver `analyzer/acta_legible.py`) -- el mismo defecto
que el motor de medición ve como "sin total", el de coherencia lo ve como un
hallazgo real de tipo solape, así que sirve para probar el camino "con
hallazgos", no sólo el camino limpio.
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

_TMP_DATA = tempfile.mkdtemp(prefix="archmuse_test_preguntar_coherencia_")
os.environ.setdefault("ARCHMUSE_DATA_DIR", _TMP_DATA)

from analyzer import storage  # noqa: E402
storage.init_db()

import app as app_module  # noqa: E402
from scripts.generar_acta_legible_demo import _construir_dxf_sintetico  # noqa: E402
from tests.test_agente_nucleo import (  # noqa: E402
    BloqueHerramienta, RespuestaFalsa, ClienteGuionizado,
)

SKILL = "revision.coherencia_del_plano"


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
    data = {"pregunta": pregunta}
    if dxf_bytes is not None:
        data["dxf"] = (BytesIO(dxf_bytes), nombre_dxf)
    if autorizar_efectos:
        data["autorizar_efectos"] = "1"
    return http.post("/api/preguntar", data=data, content_type="multipart/form-data")


def test_pregunta_de_coherencia_ejecuta_la_skill_de_verdad(cliente_http, monkeypatch, dxf_bytes):
    """Bloque 1: una pregunta de coherencia ya no cae en "sin capacidad" --
    coincide, ejecuta `revision.coherencia_del_plano` de verdad, y el acta
    vuelve renderizada."""
    doble = _guionizar(monkeypatch, RespuestaFalsa(
        BloqueHerramienta("clasificar_pregunta", {"capacidad": SKILL})))

    resp = _pedir(cliente_http, "¿hay algo solapado o repetido en este plano?", dxf_bytes)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
    datos = resp.get_json()

    assert datos["coincide"] is True
    assert datos["capacidad"] == SKILL
    assert "acta de procedencia" in datos["html"]
    assert len(doble.llamadas) == 1


def test_sin_autorizar_efectos_pide_confirmacion_y_no_escribe_el_informe(cliente_http, monkeypatch, dxf_bytes):
    """`SEG-1` cubre también esta Skill, no sólo medición: sin autorización,
    428 con la solicitud estructurada, sin escribir el informe de
    coherencia."""
    doble = _guionizar(monkeypatch, RespuestaFalsa(
        BloqueHerramienta("clasificar_pregunta", {"capacidad": SKILL})))

    resp = _pedir(cliente_http, "¿hay algo solapado o repetido en este plano?", dxf_bytes,
                  autorizar_efectos=False)
    assert resp.status_code == 428, resp.get_data(as_text=True)[:500]
    cuerpo = resp.get_json()
    assert cuerpo["confirmacion_requerida"] is True
    assert cuerpo["solicitud"]["quien"] == "api:preguntar"
    assert len(doble.llamadas) == 1


def test_el_solape_real_del_dxf_aparece_como_hallazgo_de_coherencia(cliente_http, monkeypatch, dxf_bytes):
    """El mismo DXF que el motor de medición ve como "sin total" (el solape
    de VT1/1), el motor de coherencia lo ve como un hallazgo de tipo solape
    -- mismo defecto, dos motores (ver `analyzer/acta_legible.py`). El acta
    debe traerlo en "Qué se ha establecido", con el formateador de
    `revision.hallazgos` (`_dato_revision_hallazgos`), no como un dict de
    Python en crudo."""
    doble = _guionizar(monkeypatch, RespuestaFalsa(
        BloqueHerramienta("clasificar_pregunta", {"capacidad": SKILL})))

    resp = _pedir(cliente_http, "¿hay algo solapado o repetido en este plano?", dxf_bytes)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
    html = resp.get_json()["html"]
    assert "hallazgo(s):" in html
    assert "{" not in html.split("Qué se ha establecido")[1].split("Qué no se ha comprobado")[0]


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
