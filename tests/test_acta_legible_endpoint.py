# -*- coding: utf-8 -*-
"""Integración de `DOC-1` (`docs/AGENTE_BACKLOG.md` §10): `POST /api/acta-legible`.

Ejecutar:  pytest tests/test_acta_legible_endpoint.py

`tests/test_acta_legible.py` ya prueba `analyzer/acta_legible.py` a nivel
unitario (nada muda, ni un `<details>` vacío). Lo que ESTE fichero prueba es
la pieza que faltaba en la sesión anterior: que el endpoint HTTP real —el
que ahora usa la SPA (`static/app.js`, botón "Acta de procedencia legible")—
ejecuta de verdad la Skill sobre un DXF subido por HTTP y sirve la misma
página, con el mismo caso conocido (la vivienda «VT1/1» con un solape,
mismo patrón que el defecto real de `v2s.dxf`/«VT1/3» — ver el docstring de
`analyzer/acta_legible.py`) correctamente renderizado.

El DXF sintético es el mismo que genera
`scripts/generar_acta_legible_demo._construir_dxf_sintetico` — no se duplica
la geometría aquí, se importa.
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

# `app.py` llama a `init_db()` al importarse (ver `app.py:146`), así que
# `ARCHMUSE_DATA_DIR` tiene que apuntar a un directorio temporal ANTES del
# import -- mismo patrón que `tests/test_exportar_cuadro_superficies_endpoint.py`
# y `tests/test_analizar_planta.py`, para no tocar la base de datos de desarrollo.
_TMP_DATA = tempfile.mkdtemp(prefix="archmuse_test_acta_endpoint_")
os.environ.setdefault("ARCHMUSE_DATA_DIR", _TMP_DATA)

from analyzer import storage  # noqa: E402
storage.init_db()

import app as app_module  # noqa: E402
from scripts.generar_acta_legible_demo import _construir_dxf_sintetico  # noqa: E402


@pytest.fixture(scope="module")
def dxf_bytes() -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        ruta = _construir_dxf_sintetico(Path(tmp))
        return Path(ruta).read_bytes()


@pytest.fixture(scope="module")
def client():
    return app_module.app.test_client()


def test_sin_archivo_da_400_no_500(client):
    resp = client.post("/api/acta-legible", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert resp.get_json().get("error")


def test_archivo_no_dxf_da_400_no_500(client):
    resp = client.post(
        "/api/acta-legible",
        data={"dxf": (BytesIO(b"no soy un dxf"), "plano.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert resp.get_json().get("error")


def test_el_endpoint_devuelve_html_con_el_caso_real_renderizado(client, dxf_bytes):
    """La prueba central: subida real por HTTP -> Skill real -> acta real ->
    página real, con el caso conocido (VT1/1, solape) explicado y no mudo.

    `autorizar_efectos=1` porque la Skill escribe su informe PDF intermedio
    (`SEG-1`, ver `test_sin_autorizar_efectos_pide_confirmacion_y_no_escribe_nada`
    para el camino sin autorizar) -- aquí se comprueba el camino feliz, con el
    arquitecto ya habiendo dicho que sí."""
    resp = client.post(
        "/api/acta-legible",
        data={"dxf": (BytesIO(dxf_bytes), "planta_sintetica.dxf"), "autorizar_efectos": "1"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
    assert resp.content_type.startswith("text/html")

    html = resp.get_data(as_text=True)

    # La vivienda con el solape aparece, con su desplegable de limitación.
    assert "VT1/1" in html
    assert "<details class='limitacion'>" in html

    # El caso conocido lleva su explicación en lenguaje llano Y su cifra --
    # no el TODO genérico que sí deben llevar el resto de limitaciones.
    assert "class='porque'" in html
    assert "class='cifra'" in html
    assert "2,00 m²" in html  # la cifra de mentira del DXF sintético, no 7,08 (real, no commiteado)

    # Sigue habiendo pendientes explícitos: no se ha inventado una
    # explicación para las limitaciones sin caso real, ni aquí ni al pasar
    # por HTTP.
    assert "class='todo'" in html


def test_el_endpoint_no_deja_ningun_desplegable_vacio(client, dxf_bytes):
    """Mismo criterio que `test_la_pagina_renderizada_no_deja_ningun_
    desplegable_vacio` de `tests/test_acta_legible.py`, pero contra lo que
    de verdad sirve el endpoint -- no una llamada directa a `render()`."""
    import re

    resp = client.post(
        "/api/acta-legible",
        data={"dxf": (BytesIO(dxf_bytes), "planta_sintetica.dxf"), "autorizar_efectos": "1"},
        content_type="multipart/form-data",
    )
    html = resp.get_data(as_text=True)
    bloques = re.findall(r"<details class='limitacion'>.*?</details>", html, re.S)
    assert bloques, "el endpoint no ha devuelto ninguna limitación"
    for bloque in bloques:
        cuerpo = bloque[bloque.index("</summary>") + len("</summary>"):-len("</details>")]
        assert cuerpo.strip(), "desplegable vacío servido por el endpoint: %s" % bloque[:120]


def test_sin_autorizar_efectos_pide_confirmacion_y_no_escribe_nada(client, dxf_bytes):
    """`SEG-1` (`docs/AGENTE_BACKLOG.md` §11): la Skill escribe un fichero
    (su informe PDF intermedio) y hasta ahora el backend se autoconcedía ese
    permiso sin preguntar. Sin `autorizar_efectos`, el endpoint tiene que
    pararse -- 428, no 200 y no 500 -- y decir exactamente qué efecto le
    falta, con la misma estructura (`agente.efectos.solicitud`) que usaría
    cualquier otro llamador (CLI, MCP)."""
    import glob

    antes = set(glob.glob(os.path.join(tempfile.gettempdir(), "archmuse_acta_*")))
    resp = client.post(
        "/api/acta-legible",
        data={"dxf": (BytesIO(dxf_bytes), "planta_sintetica.dxf")},
        content_type="multipart/form-data",
    )
    despues = set(glob.glob(os.path.join(tempfile.gettempdir(), "archmuse_acta_*")))

    assert resp.status_code == 428, resp.get_data(as_text=True)[:500]
    cuerpo = resp.get_json()
    assert cuerpo["confirmacion_requerida"] is True
    efectos = [e["efecto"] for e in cuerpo["solicitud"]["efectos"]]
    assert efectos == ["escribe_fichero"]
    assert cuerpo["solicitud"]["quien"] == "api:acta-legible"
    # Ni un directorio temporal huérfano: no se detiene DESPUÉS de escribir,
    # se detiene ANTES.
    assert despues - antes == set(), "el endpoint escribió algo sin autorización"


def test_el_dxf_subido_no_se_persiste_en_ningun_sitio(client, dxf_bytes):
    """Mismo criterio que `/api/analizar`: el fichero temporal se borra al
    salir de la función. No hay forma de comprobar "no existe en ningún
    disco", pero sí de comprobar que no queda ningún resto con su nombre en
    el temp del sistema tras la llamada."""
    import glob

    antes = set(glob.glob(os.path.join(tempfile.gettempdir(), "archmuse_acta_*")))
    client.post(
        "/api/acta-legible",
        data={"dxf": (BytesIO(dxf_bytes), "planta_sintetica.dxf")},
        content_type="multipart/form-data",
    )
    despues = set(glob.glob(os.path.join(tempfile.gettempdir(), "archmuse_acta_*")))
    assert despues - antes == set(), "el endpoint ha dejado directorios temporales huérfanos"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
