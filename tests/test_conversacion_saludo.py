# -*- coding: utf-8 -*-
"""Saludo vs. pregunta real en el panel de conversación (sesión 2026-08-19,
noche 6, petición directa de Pablo): "hola" no debe chocar con el bloqueo
"Adjunta un DXF antes de preguntar" -- ese bloqueo es la regla de oro y sigue
vigente para una pregunta de medición real, sólo no para un saludo.

Ejecutar:  pytest tests/test_conversacion_saludo.py

`_convEsSaludo` es una función JS PURA (sin DOM) a propósito -- este archivo
la extrae de `static/app.js` tal cual y la ejecuta de verdad en Node (no una
reimplementación en Python que pudiera divergir del comportamiento real, ni
un guardián sólo de texto sobre el fuente). Requiere `node` en PATH, igual
que `node --check static/app.js` en el resto de la suite.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
JS = (RAIZ / "static" / "app.js").read_text(encoding="utf-8")

_INICIO = "var CONV_SALUDOS = ["
# 2026-08-21: antes había un salto de línea en blanco justo delante de
# `function convMensajeSaludo` (`\n\n  function...`) -- ese hueco ya no es
# fiable como marcador: ahora puede haber un bloque de comentario entre
# medias (ver el hallazgo de Pablo sobre el saludo repetido). Se ancla al
# propio `function convMensajeSaludo(` en su lugar, que es único en el
# fichero (comprobado) y no depende de cuánto comentario le precede.
_FIN = "\n  function convMensajeSaludo("


def _extraer_funcion_pura() -> str:
    inicio = JS.index(_INICIO)
    fin = JS.index(_FIN, inicio)
    return JS[inicio:fin]


FUNCION_JS = _extraer_funcion_pura()

# Casos reales: (entrada, se_trata_como_saludo)
CASOS = [
    ("hola", True),
    ("Hola", True),
    ("  hola  ", True),
    ("hola!", True),
    ("¿qué tal?", True),
    ("Buenas tardes", True),
    ("buenos días", True),
    ("hey", True),
    ("gracias", True),
    ("hola, buenas", True),
    ("Hola ArchMuse", True),
    ("", False),
    ("   ", False),
    # La pregunta real que de verdad importa proteger: contiene un saludo
    # como subcadena, pero NO es sólo un saludo -- debe seguir bloqueando
    # sin DXF (regla de oro), nunca tratarse como charla.
    ("hola, ¿cuánta superficie útil tiene esta planta?", False),
    ("¿cuánta superficie útil tiene esta planta?", False),
    ("buenas, necesito el cuadro de superficies de este plano", False),
    ("¿cuánto va a costar construir este edificio?", False),
    ("hola qué tal, mide la superficie del salón", False),
]


def _ejecutar_casos(casos):
    llamadas = ",\n".join(
        "[%s, _convEsSaludo(%s)]" % (json.dumps(entrada), json.dumps(entrada))
        for entrada, _ in casos
    )
    programa = FUNCION_JS + "\nconsole.log(JSON.stringify([\n" + llamadas + "\n]));"
    resultado = subprocess.run(
        ["node", "-e", programa],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert resultado.returncode == 0, "node falló: %s" % resultado.stderr
    return json.loads(resultado.stdout)


def test_convesaludo_distingue_charla_de_pregunta_real():
    pares = _ejecutar_casos(CASOS)
    fallos = []
    for (entrada, esperado), (entrada_vista, obtenido) in zip(CASOS, pares):
        assert entrada_vista == entrada
        if obtenido != esperado:
            fallos.append("%r -> esperado %s, obtenido %s" % (entrada, esperado, obtenido))
    assert not fallos, "\n".join(fallos)


def test_el_mensaje_de_error_original_sigue_existiendo_para_preguntas_reales():
    """No se pidió borrar el bloqueo -- sólo dejar de aplicarlo a saludos.
    Si esta cadena desaparece, la regla de oro (M2/M3 de la especificación:
    ninguna medición sin su plano) dejó de protegerse en la interfaz."""
    assert "Adjunta un DXF antes de preguntar" in JS


def test_el_saludo_se_gestiona_antes_de_llamar_al_backend():
    """`_convEsSaludo` decide y sale de `convEnviarPregunta` con un
    `return` ANTES de la única llamada a `/api/preguntar` del fichero --
    ni un saludo, ni el bloqueo por falta de DXF, tocan la red.

    `SEG-1` (docs/AGENTE_BACKLOG.md §11): la llamada pasa ahora por
    `fetchConAutorizacion(url, formData)` en vez de `fetch(url, {...})`
    directo -- mismo endpoint, un envoltorio que sabe reintentar una vez
    si el backend pide autorización (428)."""
    inicio = JS.index("function convEnviarPregunta(pregunta)")
    fin_saludo = JS.index("if (_convEsSaludo(pregunta)) {", inicio)
    fin_return = JS.index("return;", fin_saludo)
    fin_fetch = JS.index('fetchConAutorizacion("/api/preguntar"', inicio)
    assert fin_saludo < fin_return < fin_fetch


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
