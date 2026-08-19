# -*- coding: utf-8 -*-
"""Guardianes estáticos de la interfaz de conversación (sesión 2026-08-19,
noche 4): `#conversacion-archmuse` en `static/index.html`/`app.js`/`style.css`.

Ejecutar:  pytest tests/test_conversacion_archmuse_ui.py

Mismo criterio que `tests/test_mvp_no_mezcla_auditado_con_generado.py`: leer
el fuente en vez de renderizar la página (sin infraestructura de navegador en
esta suite), para que un regreso a un patrón prohibido falle en milisegundos.

Lo que se vigila viene directo de la sección PROHIBIDO del encargo: ningún
porcentaje de cumplimiento normativo, ninguna cifra de presupuesto, ningún
visor 3D, ninguna "recomendación de IA" genérica y ninguna mascota/avatar —
y, del criterio de aceptación, que los "TODO, sin caso real" del acta nunca
se muestren abiertos por defecto.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
HTML = (RAIZ / "static" / "index.html").read_text(encoding="utf-8")
JS = (RAIZ / "static" / "app.js").read_text(encoding="utf-8")
CSS = (RAIZ / "static" / "style.css").read_text(encoding="utf-8")

_INICIO = "// Conversación con ArchMuse (sesión 2026-08-19, noche 4)"
_FIN = "// --- Fase 5: formulario"


def _bloque_conversacion() -> str:
    inicio = JS.index(_INICIO)
    # La segunda aparición (comentario del botón del ribbon) es anterior al
    # bloque principal -- se busca la marca de cabecera de sección, con las
    # rayas `====` justo antes, para no confundir las dos.
    inicio = JS.index(_INICIO, inicio + 1) if JS.count(_INICIO) > 1 else inicio
    fin = JS.index(_FIN, inicio)
    return JS[inicio:fin]


BLOQUE = _bloque_conversacion()


def test_el_overlay_vive_en_la_spa_no_en_una_pagina_aparte():
    """HAZ del encargo: "dentro de la SPA existente (no una página aparte
    como /preguntar)"."""
    assert 'id="conversacion-archmuse"' in HTML
    assert 'id="conv-form"' in HTML
    assert 'id="conv-pregunta"' in HTML
    assert 'id="conv-dxf"' in HTML


def test_reutiliza_el_backend_tal_cual_sin_logica_nueva():
    """HAZ #2 de la tarea original (sesión 2026-08-19, noche 4): cero lógica
    nueva de backend -- el panel llama a endpoints que ya existían/se
    probaron por su cuenta, y no reimplementa ninguna función de `app.py`
    en el propio JS.

    Ampliado la noche 11 (MJ-4, PRD aprobado): `/api/memoria-superficies`
    es un endpoint real y nuevo, pero de una tarea distinta y con su propio
    PRD (`docs/prd/2026-08-19-memoria-justificativa-automatica.md`) y sus
    propios tests (`tests/test_memoria_superficies_endpoint.py`) -- lo que
    este test sigue protegiendo es que el bloque de conversación no
    invente una URL que no esté probada en ningún sitio, no que se quede
    congelado en un único endpoint para siempre."""
    assert '"/api/preguntar"' in BLOQUE
    assert "formData.append(\"pregunta\"" in BLOQUE
    assert "formData.append(\"dxf\"" in BLOQUE
    # Ninguna URL de backend fuera de las dos ya probadas por su cuenta.
    llamadas_fetch = re.findall(r'fetch\("([^"]+)"', BLOQUE)
    assert set(llamadas_fetch) == {"/api/preguntar", "/api/memoria-superficies"}


def test_los_todo_del_acta_nunca_se_muestran_abiertos_por_defecto():
    """HAZ #3: "NO muestres los TODOs / 'sin caso real' al usuario por
    defecto (...) nunca abiertos por defecto"."""
    # El único `<details>` que el JS construye para el detalle del acta.
    assert re.search(r'<details class=\\?"conv-detalle\\?"[^>]*>', BLOQUE)
    assert not re.search(r'<details class=\\?"conv-detalle\\?"[^>]*\bopen\b', BLOQUE)
    # Y a nivel de CSS: `.conv-detalle` no fuerza `display` a un estado
    # abierto -- el `[open]` sólo aparece para el marcador visual (▾), nunca
    # para forzar la apertura.
    assert "conv-detalle { display" not in CSS.replace("\n", " ")


def test_ningun_dato_prohibido_en_el_bloque_de_conversacion():
    """La lista PROHIBIDO del encargo, palabra por palabra: nada de esto
    puede aparecer en el bloque nuevo, porque ArchMuse no tiene ninguna Skill
    real detrás de ello hoy.

    Se comprueba sobre el código sin comentarios de línea: el rediseño de la
    noche 5 documenta la ausencia de mascota/avatar en un comentario junto a
    `convAnadirRespuesta` (igual que "Geometría 3D" en el roadmap no era una
    cifra, ver `test_el_roadmap_...` más abajo) -- explicar por qué algo NO
    está no es lo mismo que mostrarlo."""
    bloque_sin_comentarios = re.sub(r"//[^\n]*", "", BLOQUE)
    prohibido = {
        "€": "cifra de coste/presupuesto",
        "presupuesto_": "variable de presupuesto",
        "coste_estimado": "coste inventado",
        "cumplimiento_pct": "porcentaje de cumplimiento normativo",
        "score_cumplimiento": "puntuación de cumplimiento normativo",
        "THREE.": "visor 3D (three.js) en el panel de conversación",
        "<canvas": "lienzo 3D/gráfico en el panel de conversación",
        "mascota": "mascota/avatar",
        "avatar": "mascota/avatar",
        "<img": "imagen (posible avatar) en el panel de conversación",
    }
    for marca, motivo in prohibido.items():
        assert marca not in bloque_sin_comentarios, \
            "encontrado %r (%s) en el bloque de conversación (fuera de un comentario)" % (marca, motivo)


def test_el_roadmap_reutiliza_la_etiqueta_ya_existente_de_proximamente():
    """HAZ #5: un hueco reservado para una capacidad futura lleva una
    etiqueta explícita e inconfundible -- y aquí se reutiliza la que ya
    existe en el sidebar (`sidebar-badge-proximamente`) en vez de inventar
    una nueva, y nunca lleva un número al lado."""
    assert "sidebar-badge-proximamente" in BLOQUE
    assert "CONV_ROADMAP" in BLOQUE
    # Ninguna entrada del roadmap lleva una magnitud (porcentaje, euros, un
    # número suelto de progreso) -- "3D" es sólo el nombre del área, no un
    # dato, así que el guardián es contra la FORMA de una cifra, no contra
    # cualquier dígito.
    seccion_roadmap = re.search(r"CONV_ROADMAP\s*=\s*\[(.*?)\];", BLOQUE, re.S)
    assert seccion_roadmap
    assert not re.search(r"\d+\s*(%|€|/\s*100)", seccion_roadmap.group(1))


def test_el_acta_completa_se_inserta_por_propiedad_no_por_html_en_crudo():
    """Mismo criterio de seguridad que `/api/acta-legible` en el ribbon: el
    HTML completo del acta se asigna a `.srcdoc` como propiedad del DOM,
    nunca se concatena dentro de una cadena de HTML ni se usa
    `document.write`."""
    assert ".srcdoc = r.json.html" in BLOQUE
    assert "document.write" not in BLOQUE


def test_las_tarjetas_de_hallazgo_y_fuera_de_alcance_usan_distinto_color():
    """La decisión de diseño para "sin capacidad": nunca la misma tinta que
    un hallazgo real, y nunca la tinta de error/crítico."""
    assert "conv-badge-fuera { color: var(--text-tertiary)" in CSS
    assert "conv-badge-hallazgo { color: var(--color-important)" in CSS
    assert "conv-badge-error { color: var(--color-critical)" in CSS
    # La tarjeta "fuera de alcance" no usa la insignia de error ni la de
    # hallazgo -- son tres estados visualmente distintos.
    assert "conv-badge-hallazgo" not in re.search(
        r"function convTarjetaFueraDeAlcance.*?\n  \}", BLOQUE, re.S).group(0)


if __name__ == "__main__":  # pragma: no cover
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
