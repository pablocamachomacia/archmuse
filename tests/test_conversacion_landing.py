# -*- coding: utf-8 -*-
""""/" abre la conversación sola (sesión 2026-08-19, noche 5, petición
directa de Pablo): el usuario no encontraba el botón "Preguntar a
ArchMuse" dentro del ribbon, así que ahora es lo primero que se ve al
cargar la raíz -- sin clics previos, con su propio selector de DXF.

Ejecutar:  pytest tests/test_conversacion_landing.py

Dos ángulos, igual que el resto de la suite de esta sesión: un test de
servidor (¿"/" y "/proyectos" sirven el SPA de verdad?) y un guardián
estático sobre el fuente (¿el arranque de `app.js` abre la conversación
SOLO en "/", nunca en "/proyectos"?) -- sin infraestructura de navegador.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

_TMP_DATA = tempfile.mkdtemp(prefix="archmuse_test_conv_landing_")
os.environ.setdefault("ARCHMUSE_DATA_DIR", _TMP_DATA)

from analyzer import storage  # noqa: E402
storage.init_db()

import app as app_module  # noqa: E402

JS = (RAIZ / "static" / "app.js").read_text(encoding="utf-8")


@pytest.fixture()
def cliente_http():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


# --- Servidor: qué se sirve en cada ruta -------------------------------

def test_la_raiz_sirve_el_spa(cliente_http):
    resp = cliente_http.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # Es el mismo `index.html` de siempre: trae tanto el panel de
    # conversación como la portada clásica -- quién se ve primero lo
    # decide el JS por `location.pathname`, no el servidor.
    assert 'id="conversacion-archmuse"' in html
    assert 'src="/app.js' in html


def test_proyectos_sirve_el_mismo_fichero_que_la_raiz(cliente_http):
    """La portada clásica no desaparece -- se muda a `/proyectos`, con el
    mismo contenido byte a byte que "/" (misma SPA, distinto arranque)."""
    raiz = cliente_http.get("/").get_data(as_text=True)
    proyectos = cliente_http.get("/proyectos").get_data(as_text=True)
    assert raiz == proyectos


# --- Guardián estático: quién abre la conversación sola, y quién no ----

def test_la_raiz_abre_la_conversacion_sin_clics():
    """El arranque de `app.js` llama a `abrirConversacion()` cuando
    `location.pathname` es exactamente "/" -- sin eso, "/" seguiría
    mostrando la portada de subir un DXF, que es justo lo que se pidió
    dejar de hacer."""
    assert re.search(
        r'window\.location\.pathname === "/"\s*\)\s*\{\s*abrirConversacion\(\);',
        JS,
    )


def test_abrirconversacion_automatico_no_se_dispara_fuera_de_la_raiz():
    """Defensa en profundidad: la llamada automática a `abrirConversacion()`
    vive DENTRO del condicional de pathname, no suelta al nivel del
    arranque -- si alguien la sacara del `if` por accidente, `/proyectos`
    (mismo fichero) abriría la conversación también, que es justo el
    caso que no debe pasar."""
    llamadas_automaticas = [
        m.start() for m in re.finditer(r"^\s*abrirConversacion\(\);\s*$", JS, re.M)
    ]
    assert len(llamadas_automaticas) == 1
    pos = llamadas_automaticas[0]
    antes = JS[max(0, pos - 200):pos]
    assert 'window.location.pathname === "/"' in antes


def test_abrirconversacion_no_depende_de_un_proyecto_ya_analizado():
    """El panel trae su propio selector de DXF (`#conv-dxf` / "Adjuntar
    DXF") y funciona sin `state.archivoAnalizado` -- condición necesaria
    para que abrirse solo en "/" (donde nunca hay un proyecto analizado
    todavía) no deje al usuario ante un panel roto."""
    inicio = JS.index("function abrirConversacion()")
    fin = JS.index("function cerrarConversacion()", inicio)
    cuerpo = JS[inicio:fin]
    # El único uso de `state.archivoAnalizado` aquí es como precarga
    # OPCIONAL (`if (... && state.archivoAnalizado)`), nunca como
    # condición de entrada que impida abrir el panel.
    assert "if (!convState.archivoAdjunto && state.archivoAnalizado)" in cuerpo
    assert re.search(r"if\s*\(!state\.archivoAnalizado\)\s*return;", cuerpo) is None


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
