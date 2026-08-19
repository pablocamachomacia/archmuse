# -*- coding: utf-8 -*-
"""La parcela real en `/mvp` (CP-4, cableada 2026-08-19, tarea abierta de
`PROGRESS.md`: "cablear la parcela real; hoy es un formulario").

Ejecutar:  pytest tests/test_mvp_parcela_real.py

Lo que este test protege, y por qué importa más que "el buscador funciona":
`analyzer/normativa_madrid.py` investigó en vivo y decidió, documentado, que
los 4 campos urbanísticos (ocupación/retranqueos/edificabilidad/plantas) NO
tienen hoy una traducción numérica verificada -- rellenarlos automáticamente
con algo plausible sería exactamente la alucinación con buena presentación
que la regla de oro de `CLAUDE.md` prohíbe. Este test comprueba que el
cableado de la parcela real respeta esa frontera: sólo `#solar` (superficie,
que SÍ viene de Catastro) se autorellena; los demás campos, nunca.

Mismo criterio que `test_mvp_no_mezcla_auditado_con_generado.py`: lee el
fuente en vez de renderizar la página.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
JS = (RAIZ / "static" / "mvp.js").read_text(encoding="utf-8")
HTML = (RAIZ / "static" / "mvp.html").read_text(encoding="utf-8")

_INICIO = "// --- Parcela real (CP-4, cableada 2026-08-19)"
_FIN_MARCA = "\n// ---"


def _bloque_parcela() -> str:
    inicio = JS.index(_INICIO)
    fin = JS.find(_FIN_MARCA, inicio + len(_INICIO))
    return JS[inicio: fin if fin != -1 else len(JS)]


BLOQUE = _bloque_parcela()

#: Los campos que la propia investigación de `normativa_madrid.py` prohíbe
#: rellenar automáticamente -- ninguno puede recibir una asignación `.value =`
#: dentro del bloque de parcela real.
CAMPOS_PROHIBIDOS = ("ocupacion", "retranqueos", "edificabilidad", "plantasmax",
                     "ancho", "largo", "norte")


def test_el_buscador_llama_a_geocodificar_real():
    assert '"/api/geocodificar?q="' in BLOQUE.replace("'", '"') or \
        "/api/geocodificar?q=" in BLOQUE


def test_elegir_un_resultado_consulta_catastro_real():
    assert '"/api/analizar-sitio"' in BLOQUE


def test_solo_la_superficie_se_autorellena_desde_catastro():
    """La única CIFRA que este bloque escribe en un campo del formulario es
    `$("solar").value` -- todo lo demás que Catastro/Mapbox devuelven se
    enseña como texto de estado, nunca como valor de un campo editable.
    (`buscarParcela` no cuenta: ahí sólo se repite la etiqueta que el propio
    arquitecto acaba de elegir en la lista, no un dato nuevo)."""
    asignaciones = [c for c in re.findall(r'\$\("([a-zA-Z]+)"\)\.value\s*=', BLOQUE)
                    if c != "buscarParcela"]
    assert asignaciones == ["solar"], (
        "el bloque de parcela real asigna .value a %r -- sólo 'solar' debería "
        "autorellenarse desde una fuente real" % asignaciones
    )


def test_ningun_campo_urbanistico_se_toca_desde_la_parcela_real():
    for campo in CAMPOS_PROHIBIDOS:
        assert ('$("%s").value' % campo) not in BLOQUE, (
            "«%s» no debe tocarse desde el cableado de parcela real -- "
            "no hay fuente automática verificada (ver analyzer/normativa_madrid.py)" % campo
        )


def test_la_normativa_de_madrid_es_solo_una_nota_nunca_un_valor():
    """`/api/normativa-urbanistica-punto` sólo puede alimentar `.textContent`
    de la nota informativa -- si alguna vez escribe `.value` de un campo,
    estaría autorrellenando un límite numérico que el propio módulo declara
    no tener verificado."""
    inicio = BLOQUE.index('fetch("/api/normativa-urbanistica-punto')
    resto = BLOQUE[inicio:]
    fin_funcion = resto.index("\n}")
    cuerpo = resto[:fin_funcion]
    assert ".value" not in cuerpo
    assert "notaNormativa" in cuerpo


def test_las_etiquetas_dejan_claro_que_es_entrada_manual():
    assert "lo ajustas tú" in HTML
    assert "introducidos por ti" in HTML


def test_el_marcado_de_busqueda_existe():
    for id_esperado in ("buscarParcela", "resultadosParcela", "estadoParcela", "notaNormativa"):
        assert 'id="%s"' % id_esperado in HTML


if __name__ == "__main__":  # pragma: no cover
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
