# -*- coding: utf-8 -*-
"""Posicionamiento del cuadro de entrada + simplificación de "Adjuntar DXF"
y "Medir superficies" en el panel de conversación de "/" (2026-08-21,
encargo explícito de Pablo).

Ejecutar:  pytest tests/test_conversacion_entrada_y_adjuntar.py

Mismo tipo de guardián estático que `tests/test_conversacion_landing.py`:
sin infraestructura de navegador, sólo aserciones sobre el fuente de
`static/app.js`/`static/index.html`/`static/style.css`. Tres cambios, tres
bloques de test:

1. El cuadro sólo se mueve por trabajo real (adjuntar o enviar), nunca por
   foco/click/tecleo sin más.
2. "Medir superficies" desaparece del frontend como atajo -- la capacidad
   sigue intacta en el backend (no se toca `app.py`).
3. "Adjuntar DXF" pasa de botón de texto a icono "+", mismo flujo de
   selección de archivo.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

JS = (RAIZ / "static" / "app.js").read_text(encoding="utf-8")
HTML = (RAIZ / "static" / "index.html").read_text(encoding="utf-8")
CSS = (RAIZ / "static" / "style.css").read_text(encoding="utf-8")
APP_PY = (RAIZ / "app.py").read_text(encoding="utf-8")


# --- 1. El cuadro no se mueve por foco/click/tecleo, sólo por trabajo real -

def test_el_textarea_no_dispara_convactivar_en_mousedown_ni_keydown():
    """El defecto reportado: hoy con sólo hacer click o teclear (sin enviar
    ni adjuntar) la caja saltaba abajo. `mousedown`/`keydown` sobre el
    textarea ya no pueden llamar a `convActivar`."""
    assert 'textarea.addEventListener("mousedown", convActivar)' not in JS
    assert 'textarea.addEventListener("keydown", convActivar)' not in JS


def test_el_handler_de_input_del_textarea_no_llama_a_convactivar():
    """Escribir sin enviar tampoco es "trabajo real" (el encargo lo fija
    expresamente): sólo el `input` handler del textarea, aislado del resto
    del fichero, para no colar un falso positivo de otro `convActivar()`
    en otra función."""
    m = re.search(
        r'textarea\.addEventListener\("input",\s*function\s*\(\)\s*\{(.*?)\}\);',
        JS, re.S)
    assert m, "no se encuentra el handler de 'input' del textarea"
    assert "convActivar" not in m.group(1)


def test_convenviarpregunta_activa_la_pantalla_al_principio():
    """La única forma de "escribir" que cuenta como trabajo real es enviar
    -- `convActivar()` tiene que ser de lo primero que hace
    `convEnviarPregunta`, antes de cualquiera de sus ramas (saludo, orden de
    adjuntar, sin archivo, camino feliz), para que las cuatro activen la
    pantalla igual."""
    inicio = JS.index("function convEnviarPregunta(pregunta)")
    cuerpo_temprano = JS[inicio:JS.index("if (_convEsSaludo(pregunta))", inicio)]
    assert "convActivar();" in cuerpo_temprano


def test_convactivar_solo_se_llama_desde_adjuntar_y_enviar():
    """Cierre del criterio: en todo `static/app.js`, `convActivar()` sólo se
    invoca desde `convAdjuntarArchivo` y `convEnviarPregunta` (más su propia
    definición) -- ninguna otra función lo dispara por su cuenta."""
    llamadas = [m.start() for m in re.finditer(r"\bconvActivar\(\);", JS)]
    # Dos llamadas reales: una en convAdjuntarArchivo, otra en convEnviarPregunta.
    assert len(llamadas) == 2
    for pos in llamadas:
        antes = JS[max(0, pos - 900):pos]
        assert ("function convAdjuntarArchivo(file, animar)" in antes
                or "function convEnviarPregunta(pregunta)" in antes), (
            "convActivar() se llama fuera de convAdjuntarArchivo/convEnviarPregunta")


def test_conv_activo_sigue_siendo_el_unico_interruptor_de_layout():
    """El mecanismo de fondo (una clase CSS de un solo sentido) no cambia --
    sólo cuándo se dispara. Si esto desapareciera, el criterio "se queda
    abajo aunque se borre el adjunto" (encargo, punto 2) dejaría de
    cumplirse sin que ningún test de arriba lo detectara."""
    assert 'main.classList.add("conv-activo")' in JS
    assert ".conv-main:not(.conv-activo)" in CSS


# --- 2. "Medir superficies" desaparece del frontend, no del backend -------

def _sin_comentarios_html(fuente: str) -> str:
    return re.sub(r"<!--.*?-->", "", fuente, flags=re.S)


def _sin_comentarios_js(fuente: str) -> str:
    return re.sub(r"//[^\n]*", "", fuente)


def test_medir_superficies_no_aparece_como_texto_visible():
    """"Eliminar por completo el botón/opción" es sobre lo que VE el
    arquitecto -- los comentarios que documentan por qué se retiró (varios,
    a propósito, en app.js e index.html) mencionan la frase legítimamente y
    no cuentan como "seguir apareciendo en la interfaz"."""
    assert "Medir superficies" not in _sin_comentarios_html(HTML)
    assert "Medir superficies" not in _sin_comentarios_js(JS)
    assert "Medir superficies" not in CSS  # CSS no debería mencionarlo en absoluto, ni en comentario


def test_conv_modos_solo_trae_revisar_coherencia():
    """El selector de modo pierde la opción "Medir superficies", no la
    lista entera -- sigue ofreciendo "Revisar coherencia". (El roadmap de
    "próximamente" que este desplegable también llevaba se retiró después,
    encargo del 2026-08-21 -- ver `test_conversacion_menus_barra_entrada.py`;
    `CONV_MODOS`, que es lo que este test mira, nunca lo incluyó.)"""
    m = re.search(r"var CONV_MODOS = \[(.*?)\];", JS, re.S)
    assert m, "no se encuentra CONV_MODOS"
    cuerpo = m.group(1)
    assert "superficies.medicion_de_planta" not in cuerpo
    assert "revision.coherencia_del_plano" in cuerpo


def test_la_skill_de_medicion_sigue_registrada_en_el_backend():
    """Restricción explícita del encargo: no se toca la clasificación de
    `/api/preguntar` ni los ejecutores. Este test vigila que ese fichero
    (que este cambio no debía tocar) siga intacto en lo que importa."""
    assert '"superficies.medicion_de_planta": (' in APP_PY
    assert '_medir_planta_y_renderizar_acta' in APP_PY


# --- 3. "Adjuntar DXF": de botón de texto a icono "+" ----------------------

def test_el_boton_adjuntar_ya_no_es_un_boton_de_texto():
    assert ">Adjuntar DXF<" not in HTML
    assert 'aria-label="Adjuntar DXF"' in HTML
    assert 'id="conv-btn-adjuntar"' in HTML


def test_el_change_de_inputdxf_sigue_yendo_a_la_misma_funcion_de_siempre():
    """"Cambia sólo el disparador visual, no la lógica de subida ni el
    endpoint" (encargo del 2026-08-21, punto 3): el `change` de `#conv-dxf`
    (el `<input type="file">` nativo) sigue yendo a la misma
    `convAdjuntarArchivo` de siempre -- eso no se ha tocado.

    El propio `click` de `#conv-btn-adjuntar` SÍ cambió después (encargo del
    2026-08-21, "Objetivo: eliminar una fuga..."): ya no abre `#conv-dxf`
    directamente, despliega `abrirConvAdjuntarDropdown()` primero -- ver
    `tests/test_conversacion_menus_barra_entrada.py` para ese contrato."""
    assert "if (inputDxf.files && inputDxf.files[0]) convAdjuntarArchivo(inputDxf.files[0]);" in JS


def test_el_boton_adjuntar_es_visible_en_reposo():
    """A diferencia del resto de controles que sólo aparecen tras activar
    la pantalla, el icono "+" tiene que estar disponible desde el primer
    segundo -- por eso sale de la lista de ocultos en reposo."""
    assert re.search(
        r"\.conv-main:not\(\.conv-activo\)\s*#conv-btn-adjuntar", CSS) is None
    # Y el selector de modo sigue oculto en reposo -- no se ha tocado ese criterio.
    assert re.search(
        r"\.conv-main:not\(\.conv-activo\)[^{]*#conv-modo-trigger", CSS)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
