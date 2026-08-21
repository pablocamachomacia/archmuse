# -*- coding: utf-8 -*-
"""Dos encargos del 2026-08-21, ambos sobre el panel de conversación de "/":

1. "Eliminar una fuga de detalle interno visible al usuario, y limpiar dos
   controles de la barra de entrada" -- las claves internas de Skills
   dejan de verse, "+" despliega un menú propio antes de abrir el selector
   de archivos del sistema, y el selector de capacidad pasa a icono
   discreto sin las opciones "próximamente".
2. "Eliminar la etiqueta 'ArchMuse' que aparece encima de la burbuja de
   respuesta."

Ejecutar:  pytest tests/test_conversacion_menus_barra_entrada.py

Mismo tipo de guardián estático que el resto de la sesión: aserciones sobre
el fuente de `static/app.js`/`static/index.html`/`static/style.css`, sin
infraestructura de navegador.
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


def _sin_comentarios_html(fuente: str) -> str:
    return re.sub(r"<!--.*?-->", "", fuente, flags=re.S)


def _sin_comentarios_js(fuente: str) -> str:
    return re.sub(r"//[^\n]*", "", fuente)


def _extraer(desde: str, hasta: str) -> str:
    inicio = JS.index(desde)
    fin = JS.index(hasta, inicio)
    return JS[inicio:fin]


# --- 1. [Prioridad alta] Ninguna clave interna de Skill visible -----------

CLAVES_INTERNAS = ("superficies.medicion_de_planta", "revision.coherencia_del_plano")


def test_ninguna_clave_interna_de_skill_visible_por_defecto_en_el_html():
    """Criterio de aceptación literal del encargo: "ningún texto con claves
    internas de Skills... es visible en la interfaz por defecto". Se
    comprueba fuera de comentarios -- un comentario que las mencione para
    explicar una decisión no es lo mismo que mostrarlas en pantalla."""
    html_visible = _sin_comentarios_html(HTML)
    for clave in CLAVES_INTERNAS:
        assert clave not in html_visible, "%r sigue visible en index.html" % clave


def test_conv_statusbar_ya_no_tiene_el_span_de_capacidad():
    assert 'class="conv-statusbar-capacidad"' not in _sin_comentarios_html(HTML)
    assert ".conv-statusbar-capacidad {" not in CSS


def test_no_se_ha_anadido_ningun_mecanismo_de_debug_nuevo_para_esto():
    """El encargo permitía dejar el texto "detrás de un flag de entorno",
    pero eso exige que el backend exponga ese flag (`/api/config` en
    `app.py`, fuera de alcance -- "Qué NO tocar: backend"). Este test fija
    que no se ha improvisado, ALREDEDOR DE LA CLAVE DE SKILL retirada, un
    mecanismo a medias (query string) para simularlo desde el frontend
    solo -- la clave desaparece, sin más, tal como permite el propio
    encargo. (No se prueba contra `localStorage` en general: ese mecanismo
    ya existe en el fichero para algo totalmente distinto -- el plegado del
    inspector -- y no tiene nada que ver con este cambio.)"""
    assert "URLSearchParams" not in _sin_comentarios_js(JS)
    assert "?debug" not in _sin_comentarios_js(JS)


# --- 2. [Prioridad media] "+" despliega un menú antes del selector nativo -

def test_click_en_adjuntar_ya_no_abre_directamente_el_selector_nativo():
    cuerpo = _extraer('var btnAdjuntar = document.getElementById("conv-btn-adjuntar");',
                      "inputDxf.addEventListener(\"change\"")
    assert "inputDxf.click()" not in cuerpo, (
        "el click en \"+\" sigue abriendo el selector de archivos directamente")
    assert "abrirConvAdjuntarDropdown()" in cuerpo


def test_abrirconvadjuntardropdown_despliega_un_menu_con_una_opcion():
    cuerpo = _extraer("function abrirConvAdjuntarDropdown() {", "\n  }") + "\n  }"
    assert "Adjuntar DXF" in cuerpo
    assert 'data-accion="adjuntar-dxf"' in cuerpo
    # El selector nativo sólo se abre DENTRO del listener de click del
    # propio menú (al elegir la opción), nunca antes.
    assert "inputDxf.click()" in cuerpo
    pos_listener = cuerpo.index("abrirConvDropdown(")
    pos_click_nativo = cuerpo.index("inputDxf.click()")
    assert pos_listener < pos_click_nativo


def test_el_menu_de_adjuntar_usa_el_mismo_mecanismo_que_el_selector_de_modo():
    """No es un componente nuevo y distinto -- reutiliza
    `abrirConvDropdown`/`cerrarConvDropdown`, el mismo mecanismo genérico
    que ya usaba el selector de modo antes de este encargo."""
    assert 'abrirConvDropdown("conv-btn-adjuntar",' in JS
    assert 'abrirConvDropdown("conv-modo-trigger",' in JS
    # Y sólo hay un mecanismo de abrir/cerrar -- no dos copias.
    assert JS.count("function abrirConvDropdown(triggerId, itemsHtml, onClick)") == 1
    assert JS.count("function cerrarConvDropdown() {") == 1


# --- 3. [Prioridad media] Selector de capacidad: icono, sin roadmap -------

def test_el_boton_de_capacidad_ya_no_tiene_texto_visible_en_el_html():
    """Ni el nombre de la capacidad activa ni la flecha viven ya como texto
    en el marcado -- sólo el icono (aria-hidden). "Revisar coherencia" SÍ
    puede (y debe) seguir apareciendo en `aria-label`/`title` -- ahí no es
    texto visible en pantalla, es lo que anuncia un lector de pantalla o el
    tooltip -- por eso se recorta desde el cierre de la etiqueta de
    apertura (`>`), no desde `id=`, que ya incluiría esos atributos."""
    inicio_atributos = HTML.index('id="conv-modo-trigger"')
    inicio_contenido = HTML.index(">", inicio_atributos) + 1
    fin = HTML.index("</button>", inicio_contenido)
    contenido_visible = HTML[inicio_contenido:fin]
    assert "Revisar coherencia" not in contenido_visible
    assert "conv-modo-etiqueta" not in contenido_visible
    assert "conv-modo-flecha" not in contenido_visible
    assert 'aria-label="Elegir capacidad: Revisar coherencia"' in HTML


def test_renderconvmodotrigger_ya_no_escribe_textcontent_visible():
    cuerpo = _extraer("function renderConvModoTrigger() {", "\n  }") + "\n  }"
    assert "textContent" not in cuerpo
    assert "trigger.title" in cuerpo
    assert 'trigger.setAttribute("aria-label"' in cuerpo


def test_el_desplegable_de_modo_ya_no_ofrece_las_opciones_proximamente():
    """Las tres "próximamente" (Normativa CTE, Presupuesto, Geometría 3D)
    salen del desplegable de la barra de entrada -- criterio de aceptación
    literal del encargo."""
    cuerpo = _extraer("function abrirConvModoDropdown() {", "\n  }") + "\n  }"
    assert "CONV_ROADMAP" not in cuerpo
    assert "próximamente" not in cuerpo
    assert "sidebar-badge-proximamente" not in cuerpo


def test_conv_roadmap_sigue_vivo_para_fuera_de_alcance_no_se_ha_borrado():
    """El encargo pide retirarlo SÓLO de la barra de entrada -- "si se
    quiere comunicar el roadmap en algún sitio, que sea en otra parte...
    no en el control de uso más frecuente". `convTarjetaFueraDeAlcance` es
    ese "otro sitio" (ya existente, no nuevo) y no se ha tocado."""
    cuerpo = _extraer("function convTarjetaFueraDeAlcance(mensaje) {", "\n  }") + "\n  }"
    assert "CONV_ROADMAP" in cuerpo


def test_no_se_ha_anadido_texto_nuevo_sobre_capacidades_futuras():
    """Restricción explícita: "no añadir texto nuevo sobre capacidades
    futuras en ningún sitio nuevo sin pedirlo explícitamente". Las tres
    frases del roadmap siguen apareciendo EXACTAMENTE una vez cada una en
    todo `app.js` -- la de siempre, en `CONV_ROADMAP`; ningún sitio nuevo
    las repite."""
    for frase in ("Normativa (CTE)", "Presupuesto", "Geometría 3D"):
        assert JS.count(frase) == 1, "%r aparece %d veces, se esperaba 1" % (frase, JS.count(frase))


def test_seguir_pudiendo_elegir_revisar_coherencia_a_mano():
    """Criterio de aceptación: "el icono de capacidad sigue permitiendo
    elegir explícitamente 'Revisar coherencia'"."""
    cuerpo = _extraer("function abrirConvModoDropdown() {", "\n  }") + "\n  }"
    assert "CONV_MODOS.map(function (m) {" in cuerpo
    assert "data-modo" in cuerpo
    assert "convState.modoActivo = btn.dataset.modo;" in cuerpo


# --- 4. Sin etiqueta "ArchMuse" encima de la burbuja de respuesta ---------

def test_convanadirrespuesta_ya_no_crea_la_marca_archmuse():
    cuerpo = _extraer("function convAnadirRespuesta(htmlTarjeta) {", "\n  }") + "\n  }"
    assert "conv-burbuja-marca" not in cuerpo
    assert '"ArchMuse"' not in cuerpo


def test_conv_burbuja_marca_ya_no_existe_en_el_css():
    assert ".conv-burbuja-marca" not in re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


def test_la_burbuja_del_usuario_no_se_ha_tocado():
    """Restricción explícita: "no tocar la burbuja del usuario"."""
    cuerpo = _extraer("function convAnadirFilaUsuario(pregunta, nombreArchivo) {", "\n  }") + "\n  }"
    assert "conv-fila-usuario" in cuerpo
    assert "conv-burbuja-marca" not in cuerpo  # nunca la tuvo -- confirma que sigue sin tenerla


def test_el_cuerpo_de_la_respuesta_sigue_intacto():
    """Restricción explícita: "no tocar la lógica de qué se muestra dentro
    de la burbuja, sólo el label superior" -- `envoltorio.innerHTML =
    htmlTarjeta` sigue siendo la única fuente del contenido."""
    cuerpo = _extraer("function convAnadirRespuesta(htmlTarjeta) {", "\n  }") + "\n  }"
    assert "envoltorio.innerHTML = htmlTarjeta;" in cuerpo


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
