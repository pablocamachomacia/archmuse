# -*- coding: utf-8 -*-
"""Ninguna limitación del acta legible se muestra muda (`DOC-1`).

Ejecutar:  pytest tests/test_acta_legible.py

**El mismo patrón que `test_no_orphan_numbers` (§13 de `ARCHMUSE_SPEC.md`) y
que `ningun_hueco_mudo`** (una de las verificaciones de la Skill de medición),
aplicado a la página en vez de al cálculo: toda limitación que aparece en la
página tiene, debajo de su desplegable, o bien una explicación en lenguaje
llano con su cifra, o bien un TODO explícito que dice que no hay caso real
probado todavía. Lo que no puede pasar es que un desplegable se abra y no haya
nada — eso es peor que no tener la página, porque parece que se ha explicado y
no es cierto.

Los datos vienen de `scripts/generar_acta_legible_demo.generar_acta_demo()`:
la Skill real `superficies.medicion_de_planta`, ejecutada de verdad contra un
DXF sintético (no el plano del cliente — ver el docstring de ese script). No
hay nada recalculado a mano aquí: si el acta cambia porque cambió la Skill,
este test lo nota solo.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from analyzer import acta_legible  # noqa: E402
from scripts.generar_acta_legible_demo import generar_acta_demo  # noqa: E402

_PATRON_CIFRA = re.compile(r"\d+[.,]\d+\s*m²")


@pytest.fixture(scope="module")
def acta() -> dict:
    return generar_acta_demo()


def test_el_acta_demo_tiene_al_menos_una_limitacion_y_un_caso_conocido(acta):
    """Guardián contra el falso positivo: un test que sólo mira "pendientes"
    pasaría igual aunque `clasificar()` estuviera rota y no reconociera nunca
    el caso conocido."""
    no_comprobado = acta.get("no_comprobado") or ()
    assert no_comprobado, "el acta demo no tiene ninguna limitación que probar"

    clasificadas = [acta_legible.clasificar(t) for t in no_comprobado]
    conocidas = [c for c in clasificadas if c["tipo"] == "caso_conocido"]
    assert conocidas, (
        "ninguna limitación del acta demo se ha reconocido como caso conocido — "
        "¿ha cambiado el texto que produce la Skill de medición, o se ha roto "
        "el patrón de analyzer.acta_legible?")


def test_todo_caso_conocido_tiene_porque_y_cifra_no_vacios(acta):
    for texto in acta.get("no_comprobado") or ():
        ficha = acta_legible.clasificar(texto)
        if ficha["tipo"] != "caso_conocido":
            continue
        assert ficha["porque"] and ficha["porque"].strip(), (
            "caso conocido sin porqué: %s" % texto)
        assert ficha["cifra"] and ficha["cifra"].strip(), (
            "caso conocido sin cifra: %s" % texto)
        assert _PATRON_CIFRA.search(ficha["cifra"]), (
            "la cifra de «%s» no tiene forma de magnitud: %r" % (texto, ficha["cifra"]))
        # La cifra no está inventada: tiene que poder encontrarse en el propio
        # texto de la limitación, que es de donde `clasificar()` la extrae.
        assert ficha["cifra"] in texto, (
            "la cifra «%s» no aparece en el texto original del acta: %s"
            % (ficha["cifra"], texto))


def test_todo_pendiente_declara_que_lo_es_y_no_inventa_un_porque(acta):
    for texto in acta.get("no_comprobado") or ():
        ficha = acta_legible.clasificar(texto)
        if ficha["tipo"] != "pendiente":
            continue
        assert ficha["porque"] is None
        assert ficha["cifra"] is None


def test_la_pagina_renderizada_no_deja_ningun_desplegable_vacio(acta):
    """El mismo criterio a nivel de HTML: cada `<details>` de limitación tiene
    contenido detrás, sea la explicación o el TODO — nunca nada."""
    pagina = acta_legible.render(acta)

    bloques = re.findall(r"<details class='limitacion'>.*?</details>", pagina, re.S)
    no_comprobado = acta.get("no_comprobado") or ()
    assert len(bloques) == len(no_comprobado), (
        "la página muestra %d limitaciones y el acta tiene %d"
        % (len(bloques), len(no_comprobado)))

    for bloque in bloques:
        cuerpo = bloque[bloque.index("</summary>") + len("</summary>"):-len("</details>")]
        assert cuerpo.strip(), "un desplegable de limitación no tiene nada dentro: %s" % bloque[:120]
        tiene_porque = "class='porque'" in cuerpo
        tiene_todo = "class='todo'" in cuerpo
        assert tiene_porque or tiene_todo, (
            "el desplegable no muestra ni una explicación ni un TODO: %s" % bloque[:200])
        # Y nunca las dos cosas a la vez: mezclar "aquí está el porqué" con
        # "esto está pendiente" en el mismo bloque sería peor que cualquiera
        # de las dos por separado.
        assert not (tiene_porque and tiene_todo)


#: Marcas que sólo pueden aparecer si el renderizador ha vuelto a hacer
#: `str()` de una lista/dict de Python en vez de traducirla -- las cuatro
#: variantes cubren tanto el texto crudo como su forma escapada por
#: `html.escape` (que no toca `{`/`[`, pero sí convierte `'` en `&#x27;`).
_MARCAS_DE_DICT_CRUDO = ("{'", "{&#x27;", "[{'", "[{&#x27;")


def test_la_pagina_no_muestra_sintaxis_de_diccionario_python(acta):
    """El bug nº1 que Pablo confirmó mirando la página el 2026-08-19: el
    bloque "Qué se ha establecido" mostraba `[{'exterior_m2': 9.0, ...}]` en
    vez de una frase en español. Ver `analyzer/acta_legible.py::_formatear_dato`."""
    pagina = acta_legible.render(acta)
    for marca in _MARCAS_DE_DICT_CRUDO:
        assert marca not in pagina, (
            "la página parece mostrar un dict/list de Python en crudo (marca: %r)" % marca)


#: Ruta de Windows (`C:\` o `C:/`) o de Unix (`/algo`) en cualquier punto del
#: texto -- no sólo al principio, porque puede venir precedida de una frase.
_PATRON_RUTA_SO = re.compile(r"[A-Za-z]:[\\/]|(?:^|[\s'\"])/[A-Za-z0-9_./-]+")


def test_la_pagina_no_muestra_ninguna_ruta_del_sistema_operativo(acta):
    """El bug nº2 que Pablo confirmó: `medicion.informe` traía la ruta
    absoluta del PDF temporal (con la cuenta de usuario incluida) y se
    mostraba tal cual. Ver `analyzer/acta_legible.py::_dato_medicion_informe`."""
    pagina = acta_legible.render(acta)
    encontrada = _PATRON_RUTA_SO.search(pagina)
    assert encontrada is None, (
        "la página muestra lo que parece una ruta de fichero del sistema "
        "operativo: %r" % pagina[max(0, encontrada.start() - 30):encontrada.start() + 30]
        if encontrada else None)


def test_cada_limitacion_lleva_una_etiqueta_visible_de_caso_o_todo(acta):
    """El bug nº3: sin abrir el desplegable no había forma de distinguir un
    caso comprobado de un TODO. La etiqueta tiene que estar en el
    `<summary>`, no sólo en el cuerpo -- y las dos etiquetas nunca pueden
    coincidir en el mismo bloque."""
    pagina = acta_legible.render(acta)
    bloques = re.findall(r"<details class='limitacion'>.*?</details>", pagina, re.S)
    assert bloques
    for bloque in bloques:
        resumen = bloque[:bloque.index("</summary>")]
        tiene_comprobado = "etiqueta-comprobado" in resumen
        tiene_todo = "etiqueta-todo" in resumen
        assert tiene_comprobado or tiene_todo, (
            "el resumen (visible sin desplegar) no lleva ninguna etiqueta: %s" % bloque[:160])
        assert not (tiene_comprobado and tiene_todo)


def test_una_vista_no_varias_pestanas():
    """HAZ #1 del encargo del 2026-08-19 (noche): una sola vista."""
    fuente = (RAIZ / "analyzer" / "acta_legible.py").read_text(encoding="utf-8")
    assert "aria-selected" not in fuente
    assert "data-p=" not in fuente


def test_el_renderizador_no_recalcula_nada_de_la_skill():
    """Que `analyzer/acta_legible.py` no importe la maquinaria de cálculo: sólo
    puede leer el `dict` que ya produjo `agente/acta.py`."""
    fuente = (RAIZ / "analyzer" / "acta_legible.py").read_text(encoding="utf-8")
    for prohibido in ("from analyzer.medicion import", "from analyzer import medicion",
                      "medir_planta(", "from agente.ejecucion import"):
        assert prohibido not in fuente, (
            "analyzer/acta_legible.py parece recalcular en vez de sólo presentar "
            "(encontrado: %r)" % prohibido)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
