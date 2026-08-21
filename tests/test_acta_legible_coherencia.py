# -*- coding: utf-8 -*-
"""Fuga de jerga interna y triplicación en la vista en pantalla del acta de
`revision.coherencia_del_plano` (2026-08-21, hallazgo de Pablo verificando la
demo contra `v2s.dxf`).

Ejecutar:  pytest tests/test_acta_legible_coherencia.py

Tres problemas, en la misma página, los tres reales (confirmados contra
`v2s.dxf`, no hipotéticos):

1. `agente/acta.py:_limitaciones_de`/`_limitaciones_de_capacidad` anteponen
   SIEMPRE "<id interno> no comprueba: " a cada limitación declarada
   (`revision.coherencia_del_plano`, `plano.coherencia`,
   `plano.entregable_en_pdf` -- antes `plano.informe_de_coherencia`, fusionada
   el 2026-08-21, Prompt 1.7, cierre de C4) -- un id con puntos/snake_case no
   es español llano.
2. La Skill y las dos capacidades que invoca declaran, a propósito, algunas
   limitaciones con las MISMAS palabras -- sin quitar el id, cada una cuenta
   como un texto distinto y sale repetida.
3. Un `TODO`/"sin caso real" sin caso probado se mostraba con esas palabras
   literales, vocabulario de desarrollo.

Ejecuta la Skill real (mismo camino que usa `/api/preguntar`), no una copia a
mano del acta -- si el contrato de `agente/acta.py` cambia, este test lo
nota solo.
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

_TMP_DATA = tempfile.mkdtemp(prefix="archmuse_test_acta_coherencia_")
os.environ.setdefault("ARCHMUSE_DATA_DIR", _TMP_DATA)

from analyzer import storage  # noqa: E402
storage.init_db()

import app as app_module  # noqa: E402
from analyzer import acta_legible  # noqa: E402
from tests.test_coherencia import construir  # noqa: E402

PIEZAS = (
    ("Salon", (0.0, 0.0), (4.0, 3.0)),
    ("Cocina", (4.0, 0.0), (7.0, 3.0)),
    ("Dormitorio 1", (0.0, 4.0), (4.0, 7.0)),
)


@pytest.fixture(scope="module")
def pagina() -> str:
    """La página real de `revision.coherencia_del_plano`, tal como la
    devolvería `/api/preguntar` -- misma función, mismo DXF sintético
    limpio (sin cuadro, sin hallazgos): la triplicación de "no comprueba"
    no depende de que el plano tenga defectos, sale siempre que la Skill
    se ejecuta con éxito."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta = construir(PIEZAS, destino=Path(tmp))
        with open(ruta, "rb") as f:
            from werkzeug.datastructures import FileStorage
            fs = FileStorage(f, filename="plano.dxf")
            return app_module._revisar_coherencia_y_renderizar_acta(
                fs, "plano.dxf", None, None,
                quien="test-fuga-interna", autorizar_efectos=True)


# --- 1. Ningún id interno visible ------------------------------------------

#: Un id de capacidad/Skill: minúsculas, puntos, snake_case -- el contrato
#: exacto que usa `agente/acta.py:_limitaciones_de`. Cualquier coincidencia
#: en la página renderizada es una fuga, sea cual sea el id concreto.
_RE_ID_INTERNO_NO_COMPRUEBA = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+ no comprueba")

_IDS_CONOCIDOS = (
    "revision.coherencia_del_plano", "plano.coherencia", "plano.entregable_en_pdf",
)


def test_ningun_id_interno_conocido_es_visible(pagina):
    for id_interno in _IDS_CONOCIDOS:
        assert id_interno not in pagina, (
            "%r sigue visible en la página del acta de coherencia" % id_interno)


def test_ningun_id_interno_con_forma_de_snake_case_o_puntos_es_visible(pagina):
    """No sólo los tres conocidos -- ningún id con esa FORMA, por si mañana
    aparece uno nuevo (otra capacidad, otra Skill) con el mismo contrato de
    `agente/acta.py`."""
    encontrado = _RE_ID_INTERNO_NO_COMPRUEBA.search(pagina)
    assert encontrado is None, (
        "la página muestra lo que parece un id interno: %r"
        % pagina[max(0, encontrado.start() - 20):encontrado.end() + 20] if encontrado else None)


# --- 2. Sin triplicación -----------------------------------------------------

def test_el_mismo_aviso_no_aparece_repetido_tres_veces(pagina):
    """El caso real encontrado en `v2s.dxf`: la Skill y `plano.coherencia`
    declaran, PALABRA POR PALABRA, la misma frase para "no comprueba
    normativa" -- antes salía dos veces (una por cada id); ahora, una.

    `plano.entregable_en_pdf` (antes `plano.informe_de_coherencia`, fusionada
    el 2026-08-21) declara una frase relacionada pero NO idéntica ("...el
    informe dice si el plano..."), ahora con el prefijo "(tipo=coherencia) "
    -- esa sigue apareciendo aparte, a propósito: la deduplicación es por
    texto EXACTO, no por tema
    (ver el porqué en `analyzer/acta_legible.py::_seccion_limitaciones`), así
    que este test comprueba la frase completa, no un fragmento que las dos
    comparten."""
    frase_exacta = "no comprueba normativa: dice si el plano es coherente consigo mismo, no si el proyecto cumple"
    assert pagina.count(frase_exacta) == 1, (
        "%r aparece %d veces en la página (se esperaba 1, deduplicada)"
        % (frase_exacta, pagina.count(frase_exacta)))


def test_no_lee_muros_huecos_ni_carpinteria_tampoco_esta_triplicado(pagina):
    """Segundo caso real de triplicación exacta encontrado en `v2s.dxf`:
    la Skill y `plano.coherencia` declaran, palabra por palabra, "no lee
    muros, huecos ni carpintería"."""
    frase = "no lee muros, huecos ni carpintería"
    assert pagina.count(frase) == 1, (
        "%r aparece %d veces en la página (se esperaba 1, deduplicada)"
        % (frase, pagina.count(frase)))


# --- 3. Sin vocabulario de desarrollo ---------------------------------------

def test_todo_y_sin_caso_real_no_son_visibles_por_defecto(pagina):
    assert "TODO" not in pagina
    assert "sin caso real" not in pagina.lower()


# --- La deduplicación no rompe lo que sí funcionaba -------------------------

def test_los_casos_conocidos_y_los_datos_establecidos_siguen_intactos(pagina):
    """Restricción explícita del encargo: no se toca "Qué se ha
    establecido" ni las tarjetas de hallazgo. Sobre un plano limpio (sin
    hallazgos), el acta sigue diciendo que no se ha encontrado nada y qué
    se ha comprobado -- este test sólo confirma que la deduplicación de
    "Qué no se ha comprobado" no se ha llevado por delante nada de eso."""
    assert "recinto(s) leído(s) en el plano" in pagina
    assert "Comprobado:" in pagina


def test_al_menos_un_bloque_de_limitacion_sigue_viendose(pagina):
    """Que no se haya deduplicado TODO hasta dejar la sección vacía --
    quedan limitaciones reales que declarar (p. ej. "sólo admite un DXF con
    una única vivienda detectada")."""
    bloques = re.findall(r"<details class='limitacion'>.*?</details>", pagina, re.S)
    assert bloques


# --- La función pura, aislada -----------------------------------------------

def test_sin_prefijo_interno_quita_exactamente_el_contrato_de_agente_acta():
    """`agente/acta.py:_limitaciones_de` construye siempre
    `"%s no comprueba: %s" % (id, l)` -- se prueba ese contrato exacto,
    tal como lo usan los tres ids reales de esta Skill."""
    for id_interno in _IDS_CONOCIDOS:
        entrada = "%s no comprueba: algo que no se comprueba" % id_interno
        assert acta_legible._sin_prefijo_interno(entrada) == "algo que no se comprueba"


def test_sin_prefijo_interno_no_toca_un_texto_que_no_encaja_con_el_contrato():
    """Un motivo redactado a mano (el "sin total" de medición, por ejemplo)
    no tiene ese prefijo -- no se recorta a ciegas."""
    entrada = "«VT1/3» no lleva superficie útil total: hay 7,08 m² dibujados dos veces"
    assert acta_legible._sin_prefijo_interno(entrada) == entrada


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
