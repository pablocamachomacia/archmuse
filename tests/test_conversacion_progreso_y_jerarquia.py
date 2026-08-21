# -*- coding: utf-8 -*-
"""Progreso real (fases) + jerarquía del mensaje final en el panel de
conversación (2026-08-21, encargo explícito de Pablo: "estados de progreso
reales, no inventados" + "jerarquía visual en vez de bloque de texto plano").

Ejecutar:  pytest tests/test_conversacion_progreso_y_jerarquia.py

Mismo patrón que `tests/test_conversacion_hallazgos_coherencia.py`: las
funciones puras de `static/app.js` se ejecutan de verdad en Node (no se
reimplementan en Python); lo que depende de `DOMParser` (sin polyfill en
este repo) se prueba por la forma del código fuente, no por ejecución.

Tres bloques, uno por criterio de aceptación del encargo:
1. Las fases de progreso de cada Skill son DISTINTAS entre sí y comparten
   vocabulario real con `Skill.procedimiento` (`agente/skills/*.py`,
   importado tal cual, no copiado a mano).
2. El contenido final no pierde ningún dato al pasar de párrafo corrido a
   filas/secciones -- las funciones de parseo se ejecutan contra el `.dato`
   exacto que produce `analyzer/acta_legible.py`.
3. El camino de bloqueo (sin DXF) nunca inicia el temporizador de progreso.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

JS = (RAIZ / "static" / "app.js").read_text(encoding="utf-8")

from agente.skills.coherencia import SKILLS as _SKILLS_COHERENCIA  # noqa: E402
from agente.skills.medicion import SKILLS as _SKILLS_MEDICION  # noqa: E402
from analyzer.acta_legible import _dato_medicion_informe  # noqa: E402

SKILL_COHERENCIA = next(s for s in _SKILLS_COHERENCIA if s.id == "revision.coherencia_del_plano")
SKILL_MEDICION = next(s for s in _SKILLS_MEDICION if s.id == "superficies.medicion_de_planta")


def _ejecutar_js(programa: str):
    resultado = subprocess.run(
        ["node", "-e", programa], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert resultado.returncode == 0, "node falló: %s" % resultado.stderr
    return json.loads(resultado.stdout)


def _extraer(desde: str, hasta: str) -> str:
    inicio = JS.index(desde)
    fin = JS.index(hasta, inicio)
    return JS[inicio:fin]


# --- 1. Fases de progreso: reales, distintas por Skill --------------------

def _extraer_fases_progreso() -> dict:
    bloque = _extraer("var CONV_FASES_PROGRESO = {", "\n  };") + "\n  };"
    programa = bloque.replace("var CONV_FASES_PROGRESO", "var x") + "\nconsole.log(JSON.stringify(x));"
    return _ejecutar_js(programa)


FASES = _extraer_fases_progreso()


def test_las_dos_skills_tienen_fases_y_son_distintas():
    assert set(FASES) == {"revision.coherencia_del_plano", "superficies.medicion_de_planta"}
    coherencia = FASES["revision.coherencia_del_plano"]
    medicion = FASES["superficies.medicion_de_planta"]
    assert coherencia != medicion
    # "al menos 2-3 estados" (criterio de aceptación del encargo).
    assert len(coherencia) >= 3
    assert len(medicion) >= 3
    assert len(set(coherencia) & set(medicion)) < len(coherencia), (
        "las dos secuencias no pueden ser casi idénticas -- tienen que "
        "reflejar procedimientos reales distintos")


def test_las_fases_de_coherencia_comparten_vocabulario_con_su_procedimiento_real():
    """Las palabras de control tienen que estar en el `procedimiento` REAL
    de la Skill (importado de `agente/skills/coherencia.py`, no copiado) --
    si esto fallara, sería la propia Skill la que ha cambiado de
    vocabulario, no un error de este test."""
    procedimiento = " ".join(SKILL_COHERENCIA.procedimiento).lower()
    for palabra in ("unidad", "recintos", "cuadro"):
        assert palabra in procedimiento, "%r no está en el procedimiento real" % palabra

    fases = " ".join(FASES["revision.coherencia_del_plano"]).lower()
    assert "unidad" in fases      # paso 1: "Leer el plano comprobando la unidad..."
    assert "recintos" in fases    # paso 2: "Buscar recintos que se solapen..."
    assert "cuadro" in fases      # paso 5: "Contrastar el cuadro de superficies..."


def test_las_fases_de_medicion_comparten_vocabulario_con_su_procedimiento_real():
    procedimiento = " ".join(SKILL_MEDICION.procedimiento).lower()
    for palabra in ("unidad", "viviendas", "recinto"):
        assert palabra in procedimiento, "%r no está en el procedimiento real" % palabra

    fases = " ".join(FASES["superficies.medicion_de_planta"]).lower()
    assert "unidad" in fases      # paso 1: "Leer el plano comprobando la unidad..."
    assert "viviendas" in fases   # paso 2: "Separar las viviendas..."
    assert "recinto" in fases     # paso 4: "Medir cada recinto..."


def test_la_fase_final_usa_el_vocabulario_ya_establecido_del_producto():
    """"Redactando el acta" (coherencia) / "Redactando el informe"
    (medición) no son sinónimos elegidos al azar para esta pantalla: son
    los mismos sustantivos que ya usa el resto del producto para el
    documento de cada Skill -- `analyzer/acta_legible.py` (backend, sin
    tocar) para medición, y el propio "Ver el acta de procedencia
    completa" (`static/app.js`, ya existente antes de este cambio) para
    coherencia."""
    assert "informe" in _dato_medicion_informe("x.pdf").lower()
    assert "informe" in FASES["superficies.medicion_de_planta"][-1].lower()
    assert "acta de procedencia" in JS
    assert "acta" in FASES["revision.coherencia_del_plano"][-1].lower()


def test_convcapacidadprobable_distingue_las_dos_skills():
    """No es la clasificación real -- esa sigue siendo 100% el LLM del
    backend (`_capacidad_que_coincide`, `app.py`, sin tocar). Es sólo la
    estimación que decide qué secuencia enseñar mientras se espera; se
    prueba como lo que es, una función pura sobre texto."""
    palabras = _extraer("var CONV_PALABRAS_COHERENCIA", ";") + ";"
    funcion = _extraer("function _convCapacidadProbable(pregunta) {", "\n  }") + "\n  }"
    programa = (palabras + "\n" + funcion +
                "\nconsole.log(JSON.stringify([" +
                "_convCapacidadProbable('¿Hay algo solapado o repetido en este plano?')," +
                "_convCapacidadProbable('¿Cuánta superficie útil tiene esta planta?')" +
                "]));")
    coherencia, medicion = _ejecutar_js(programa)
    assert coherencia == "revision.coherencia_del_plano"
    assert medicion == "superficies.medicion_de_planta"


# --- 2. El contenido final no pierde ningún dato ---------------------------

_FUNCIONES_PURAS_HALLAZGO = _extraer(
    "function _convHumanizarTipo(tipo) {", "\n  // Tarjeta de un hallazgo real")


def _ejecutar_hallazgos_piezas(texto: str):
    programa = _FUNCIONES_PURAS_HALLAZGO + "\nconsole.log(JSON.stringify(_convHallazgosPiezas(%s)));" % json.dumps(texto)
    return _ejecutar_js(programa)


def _ejecutar_comprobado_piezas(texto: str):
    programa = _FUNCIONES_PURAS_HALLAZGO + "\nconsole.log(JSON.stringify(_convComprobadoPiezas(%s)));" % json.dumps(texto)
    return _ejecutar_js(programa)


def test_hallazgos_piezas_conserva_tipo_entidad_y_cifra_de_cada_hallazgo():
    """El mismo `.dato` que produce `_dato_revision_hallazgos()`
    (`analyzer/acta_legible.py`) -- se divide en filas sin perder ninguna
    de las tres piezas de información que ya traía (tipo, entidad, cifra),
    sólo reordenadas en HTML distinto."""
    texto = ("2 hallazgo(s): solape_entre_recintos en Salón/cocina + Dormitorio 1 2.00 m2; "
             "polilinea_mal_cerrada en handle A61724 0.03 unidades de dibujo.")
    piezas = _ejecutar_hallazgos_piezas(texto)
    assert len(piezas) == 2
    assert piezas[0] == {"tipo": "Solape entre recintos",
                         "resto": "Salón/cocina + Dormitorio 1 2.00 m2"}
    assert piezas[1] == {"tipo": "Polilinea mal cerrada",
                         "resto": "handle A61724 0.03 unidades de dibujo"}


def test_hallazgos_piezas_no_inventa_una_fila_si_el_contrato_de_texto_cambia():
    assert _ejecutar_hallazgos_piezas("No se ha encontrado ningún hallazgo en esta revisión.") == []


def test_humanizar_tipo_es_solo_formato_ninguna_palabra_nueva():
    programa = _FUNCIONES_PURAS_HALLAZGO + (
        "\nconsole.log(JSON.stringify(['solape_entre_recintos', 'etiqueta_duplicada']"
        ".map(_convHumanizarTipo)));")
    assert _ejecutar_js(programa) == ["Solape entre recintos", "Etiqueta duplicada"]


def test_comprobado_piezas_conserva_que_y_para_de_cada_comprobacion():
    """El mismo `.dato` que produce `_dato_revision_comprobado()` -- ningún
    dato nuevo, sólo dividido en filas."""
    texto = ("Comprobado: Recintos leídos (que la capa de recintos dé alguna pieza); "
             "Solapes entre recintos (que dos piezas de la misma vivienda no se pisen).")
    piezas = _ejecutar_comprobado_piezas(texto)
    assert piezas == [
        {"que": "Recintos leídos", "para": "que la capa de recintos dé alguna pieza"},
        {"que": "Solapes entre recintos", "para": "que dos piezas de la misma vivienda no se pisen"},
    ]


def test_comprobado_piezas_vacio_si_medicion_no_produce_ese_dato():
    """Medición no declara `medicion.comprobado` (ver
    `agente/skills/medicion.py:PRODUCE`) -- la sección "Qué se ha
    comprobado" simplemente no aparece para esa Skill, nunca se rellena
    con algo inventado para que las dos Skills "tengan lo mismo"."""
    assert "medicion.comprobado" not in SKILL_MEDICION.produce
    assert _ejecutar_comprobado_piezas("cualquier otra cosa") == []


def test_convtarjetahallazgo_pinta_la_lista_de_hallazgos_y_las_dos_secciones_plegables():
    """`convTarjetaHallazgo` depende de `DOMParser` (API de navegador, sin
    polyfill en este repo), así que -- mismo criterio que
    `test_conversacion_hallazgos_coherencia.py` -- esto es un test de
    fuente: comprueba que las piezas nuevas están conectadas, sin
    reimplementar la función."""
    cuerpo = _extraer("function convTarjetaHallazgo(capacidad, htmlActa) {",
                      "\n  // Reenvía el MISMO")
    assert "_convHallazgosPiezas(hallazgosDatos.texto)" in cuerpo
    assert "conv-hallazgos-lista" in cuerpo
    assert "_convComprobadoPiezas(datoComprobado)" in cuerpo
    assert "Qué se ha comprobado" in cuerpo
    assert "Qué no se ha comprobado" in cuerpo
    # El iframe con el acta completa sigue ahí -- nada se ha quitado, sólo
    # añadido encima.
    assert "conv-acta-frame" in cuerpo


# --- 3. Sin DXF, sin estados de progreso falsos ----------------------------

def test_iniciar_progreso_solo_se_llama_desde_el_camino_que_toca_la_red():
    """Las tres ramas que se resuelven sin backend (saludo, intención de
    adjuntar, sin DXF) tienen que devolver ANTES de la única llamada a
    `_convIniciarProgreso` en `convEnviarPregunta` -- si alguna la
    alcanzara, se vería un progreso de una Skill que nunca se ejecuta."""
    cuerpo = _extraer("function convEnviarPregunta(pregunta) {", "\n  }\n\n  //")
    pos_saludo = cuerpo.index("_convEsSaludo(pregunta)")
    pos_adjuntar_intento = cuerpo.index("_convEsIntencionDeAdjuntar(pregunta)")
    pos_sin_archivo = cuerpo.index("if (!archivo) {")
    pos_progreso = cuerpo.index("_convIniciarProgreso(pregunta)")
    assert pos_saludo < pos_adjuntar_intento < pos_sin_archivo < pos_progreso

    # Y las tres ramas de arriba SIEMPRE devuelven antes de esa línea --
    # ninguna "sigue de largo" hacia el progreso por accidente.
    for marcador in ("_convEsSaludo(pregunta)", "_convEsIntencionDeAdjuntar(pregunta)", "if (!archivo) {"):
        inicio_rama = cuerpo.index(marcador)
        fin_rama = cuerpo.index("return;", inicio_rama)
        assert fin_rama < pos_progreso


def test_iniciar_progreso_solo_se_llama_una_vez_en_todo_el_fichero():
    """Ni un segundo disparador escondido en otra función -- se cuentan las
    LLAMADAS, no la propia declaración de la función (que también contiene
    el texto `_convIniciarProgreso(pregunta)`, en su cabecera)."""
    llamadas = re.findall(r"(?<!function )_convIniciarProgreso\(pregunta\)", JS)
    assert len(llamadas) == 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
