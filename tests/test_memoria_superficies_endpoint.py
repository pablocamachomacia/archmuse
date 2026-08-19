# -*- coding: utf-8 -*-
"""`POST /api/memoria-superficies` (MJ-3). Sesión 2026-08-19, noche 11.

Ejecutar:  pytest tests/test_memoria_superficies_endpoint.py

Mismo patrón que `tests/test_acta_legible_endpoint.py`: sube el DXF
sintético real (VT1/1, con un solape) por HTTP, ejecuta la Skill real
`superficies.medicion_de_planta`, y comprueba que el PDF que vuelve es de
verdad el apartado de superficies de ESA medición -- no un documento
genérico ni un mock.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

_TMP_DATA = tempfile.mkdtemp(prefix="archmuse_test_memoria_endpoint_")
os.environ.setdefault("ARCHMUSE_DATA_DIR", _TMP_DATA)

from analyzer import storage  # noqa: E402
storage.init_db()

import app as app_module  # noqa: E402
from pypdf import PdfReader  # noqa: E402
from scripts.generar_acta_legible_demo import _construir_dxf_sintetico  # noqa: E402


@pytest.fixture(scope="module")
def dxf_bytes() -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        ruta = _construir_dxf_sintetico(Path(tmp))
        return Path(ruta).read_bytes()


@pytest.fixture(scope="module")
def client():
    return app_module.app.test_client()


def _texto(pdf_bytes: bytes) -> str:
    return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf_bytes)).pages)


def test_sin_archivo_da_400_no_500(client):
    resp = client.post("/api/memoria-superficies", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert resp.get_json().get("error")


def test_archivo_no_dxf_da_400_no_500(client):
    resp = client.post(
        "/api/memoria-superficies",
        data={"dxf": (BytesIO(b"no soy un dxf"), "plano.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert resp.get_json().get("error")


def test_el_endpoint_devuelve_un_pdf_real_con_el_caso_conocido(client, dxf_bytes):
    resp = client.post(
        "/api/memoria-superficies",
        data={"dxf": (BytesIO(dxf_bytes), "planta_sintetica.dxf")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
    assert resp.content_type == "application/pdf"
    assert resp.data[:5] == b"%PDF-"
    assert "attachment" in resp.headers.get("Content-Disposition", "")

    texto = _texto(resp.data)
    assert "VT1/1" in texto
    assert "APARTADO DE SUPERFICIES" in texto
    assert "BORRADOR PARA REVISIÓN DE UN COLEGIADO" in texto
    # El caso conocido: sin total útil, por el solape del DXF sintético.
    assert "Sin superficie útil total" in texto


def test_el_dxf_subido_no_se_persiste_en_ningun_sitio(client, dxf_bytes):
    import glob

    antes = set(glob.glob(os.path.join(tempfile.gettempdir(), "archmuse_acta_*")))
    client.post(
        "/api/memoria-superficies",
        data={"dxf": (BytesIO(dxf_bytes), "planta_sintetica.dxf")},
        content_type="multipart/form-data",
    )
    despues = set(glob.glob(os.path.join(tempfile.gettempdir(), "archmuse_acta_*")))
    assert despues - antes == set(), "el endpoint ha dejado directorios temporales huérfanos"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
