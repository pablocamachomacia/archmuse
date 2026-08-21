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
    contenido detrás, sea la explicación o el "pendiente de explicar" — nunca
    nada.

    2026-08-21 (hallazgo de Pablo): ya no es 1:1 con `no_comprobado` -- la
    página deduplica las limitaciones que sólo difieren en el id interno que
    las antepone (`agente/acta.py`, ver
    `analyzer/acta_legible.py::_sin_prefijo_interno`). El invariante real es
    "tantos bloques como textos únicos una vez quitado ese prefijo", no "tantos
    como entradas trae `no_comprobado`" -- se recalcula con la propia función
    de producción, nunca con un número fijo a mano."""
    pagina = acta_legible.render(acta)

    bloques = re.findall(r"<details class='limitacion'>.*?</details>", pagina, re.S)
    no_comprobado = acta.get("no_comprobado") or ()
    textos_unicos = list(dict.fromkeys(
        acta_legible._sin_prefijo_interno(t) for t in no_comprobado))
    assert len(bloques) == len(textos_unicos), (
        "la página muestra %d limitaciones y hay %d textos únicos (de %d "
        "entradas en no_comprobado)"
        % (len(bloques), len(textos_unicos), len(no_comprobado)))

    for bloque in bloques:
        cuerpo = bloque[bloque.index("</summary>") + len("</summary>"):-len("</details>")]
        assert cuerpo.strip(), "un desplegable de limitación no tiene nada dentro: %s" % bloque[:120]
        tiene_porque = "class='porque'" in cuerpo
        tiene_pendiente = "class='pendiente'" in cuerpo
        assert tiene_porque or tiene_pendiente, (
            "el desplegable no muestra ni una explicación ni un pendiente: %s" % bloque[:200])
        # Y nunca las dos cosas a la vez: mezclar "aquí está el porqué" con
        # "esto está pendiente" en el mismo bloque sería peor que cualquiera
        # de las dos por separado.
        assert not (tiene_porque and tiene_pendiente)


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


# --- El último eslabón: la pieza y la capa concretas del DXF ---------------
# (petición de Pablo, sesión 2026-08-19, noche 14: cada bloque desplegado
# explicaba el motivo pero no señalaba la entidad del DXF de la que sale.)

_PATRON_PIEZA_CAPA = re.compile(r"^Pieza: .+ · Capa: .+$")


def test_todo_caso_conocido_con_solapes_trae_las_piezas_implicadas(acta):
    """La entidad no se inventa desde el texto del motivo: sale de
    `medicion.viviendas` -> `solapes`, que es donde el motor de medición ya
    dice qué dos piezas se disputan el mismo suelo."""
    datos = acta.get("datos") or ()
    vio_alguna = False
    for texto in acta.get("no_comprobado") or ():
        ficha = acta_legible.clasificar(texto, datos)
        if ficha["tipo"] != "caso_conocido":
            continue
        vio_alguna = True
        assert ficha["entidades"], (
            "caso conocido sin ninguna pieza señalada: %s" % texto)
        for linea in ficha["entidades"]:
            assert _PATRON_PIEZA_CAPA.match(linea), (
                "la línea de entidad no tiene la forma «Pieza: ... · Capa: ...»: %r" % linea)
        # Las piezas nombradas tienen que ser las mismas que trae el acta
        # para esa vivienda -- no cualquier rótulo.
        vivienda = next(
            v for d in datos if d.get("nombre") == "medicion.viviendas"
            for v in d.get("valor") or () if v.get("vivienda") in texto
        )
        rotulos_reales = {p.get("rotulo") for p in vivienda.get("piezas") or ()}
        for linea in ficha["entidades"]:
            rotulo = linea.split(" · ")[0].removeprefix("Pieza: ")
            assert rotulo in rotulos_reales, (
                "la entidad nombra una pieza que no está en la vivienda: %r" % linea)
    assert vio_alguna, "el acta demo no tiene ningún caso conocido que probar"


def test_todo_pendiente_deja_explicito_que_no_hay_entidad_que_senalar(acta):
    """Criterio de Pablo: nunca en silencio -- para un TODO sin caso real
    tampoco hay pieza que señalar, y la página lo tiene que decir, no
    omitirlo."""
    datos = acta.get("datos") or ()
    vio_algun_pendiente = False
    for texto in acta.get("no_comprobado") or ():
        ficha = acta_legible.clasificar(texto, datos)
        if ficha["tipo"] != "pendiente":
            continue
        vio_algun_pendiente = True
        assert ficha["entidades"] is None

    assert vio_algun_pendiente, "el acta demo no tiene ningún pendiente que probar"

    pagina = acta_legible.render(acta)
    bloques = re.findall(r"<details class='limitacion'>.*?</details>", pagina, re.S)
    for bloque in bloques:
        # Cada bloque, sea caso conocido o TODO, tiene un `<div class='entidad'>`
        # (con las piezas) o un `<div class='entidad entidad-vacia'>` (con el
        # motivo de que no las hay) -- nunca ninguno de los dos.
        assert "class='entidad" in bloque, (
            "un desplegable no dice nada sobre la entidad del DXF: %s" % bloque[:200])


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


def test_el_fallback_generico_nunca_filtra_el_nombre_interno_del_campo():
    """2026-08-21, hallazgo de Pablo verificando la demo contra `v2s.dxf`:
    `revision.recintos_geometria` no tiene formateador propio a propósito
    (fuera de alcance del PRD que lo introdujo) y caía al genérico, que
    hasta hoy escribía el `nombre` interno tal cual --
    "sin traducción específica todavía para «revision.recintos_geometria»"--
    en la vista en pantalla. Un identificador con puntos/snake_case no es
    español llano, es fuga de detalle interno, aunque el resto de la frase
    sea honesto (sigue siendo cierto: NO hay descripción detallada). Se
    prueba `_formatear_dato` directamente, sin pasar por una Skill real --
    es la función que decide, y cualquier `nombre` futuro sin formateador
    tiene que quedar cubierto, no sólo el de hoy."""
    for nombre in ("revision.recintos_geometria", "medicion.algo_que_no_existe_todavia",
                  "otro.campo.con.puntos"):
        texto_lista = acta_legible._formatear_dato(nombre, [1, 2, 3])
        texto_dict = acta_legible._formatear_dato(nombre, {"a": 1})
        for texto in (texto_lista, texto_dict):
            assert nombre not in texto, (
                "%r se filtra en %r" % (nombre, texto))
            assert "«" not in texto and "»" not in texto, (
                "el fallback ya no debería necesitar comillas angulares "
                "para citar un identificador interno (texto: %r)" % texto)
    # Sigue siendo honesto -- no pretende tener una descripción que no tiene.
    assert "sin descripci" in texto_lista.lower() or "sin descripci" in texto_dict.lower()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
