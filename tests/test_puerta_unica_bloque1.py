# -*- coding: utf-8 -*-
"""Bloque 1 (`docs/design/2026-08-20-reorientacion-estrategica-v1.md` §7/§8,
aprobado por Pablo con una precisión explícita): `/` sirve el flujo de
revisión como puerta única, con un enlace visible a `/proyectos` etiquetado
EXACTAMENTE con la frase que propone el documento -- "no lo suavices ni lo
acortes", instrucción textual de Pablo.

Ejecutar:  pytest tests/test_puerta_unica_bloque1.py
"""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
HTML = (RAIZ / "static" / "index.html").read_text(encoding="utf-8")
JS = (RAIZ / "static" / "app.js").read_text(encoding="utf-8")

ETIQUETA_EXACTA = (
    "Verificación normativa, sin corpus firmado todavía — usa esto bajo tu "
    "propio criterio profesional."
)


def test_la_etiqueta_del_enlace_a_proyectos_es_exactamente_la_aprobada():
    """Ni acortada ni suavizada -- verbatim, y en dos sitios: el `title`
    (para quien pase el ratón) y un texto siempre visible (mismo criterio que
    `.sidebar-item:disabled`, ver el comentario junto a `.sidebar-etiqueta`
    en `static/style.css`: la explicación no puede depender sólo de un
    tooltip)."""
    assert HTML.count(ETIQUETA_EXACTA) == 2


def test_el_enlace_a_proyectos_sigue_apuntando_a_proyectos():
    inicio = HTML.index('href="/proyectos"')
    fin = HTML.index("</a>", inicio)
    bloque = HTML[inicio:fin]
    assert "Proyectos" in bloque


def test_slash_sigue_abriendo_la_conversacion_como_puerta_unica():
    """No se ha tocado la decisión del 19/8 (noche 5): `/` sigue abriendo el
    panel de conversación sin ningún clic previo. Bloque 1 añade el enlace
    honesto a `/proyectos`, no cambia cuál es la puerta principal."""
    assert 'if (window.location.pathname === "/") {' in JS
    assert "abrirConversacion();" in JS


def test_mvp_no_se_ha_tocado():
    """Bloque 1 congela `/mvp` explícitamente -- no se elimina ni se
    modifica su ruta en esta sesión."""
    import app as app_module
    reglas = [str(r) for r in app_module.app.url_map.iter_rules()]
    assert any("/mvp" in r for r in reglas)


if __name__ == "__main__":  # pragma: no cover
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
