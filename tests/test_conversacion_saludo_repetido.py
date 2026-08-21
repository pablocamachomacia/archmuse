# -*- coding: utf-8 -*-
"""El saludo repetido sin DXF ya no es un calco exacto (hallazgo de Pablo,
2026-08-21): "hola", "hola" otra vez y "qué tal" -- las tres sin DXF
adjunto -- daban antes la bienvenida completa palabra por palabra las tres
veces. Diagnóstico confirmado por escrito antes de tocar nada: no era un
fallo de clasificación (`_convEsSaludo` acierta las tres), era que
`convMensajeSaludo()` no tenía memoria de que ya se había saludado --
ver `tests/test_conversacion_saludo.py` para la clasificación en sí, este
fichero es sólo sobre la memoria de sesión.

Ejecutar:  pytest tests/test_conversacion_saludo_repetido.py

`convMensajeSaludo()` sigue siendo una función PURA (lee `convState`, no
toca el DOM) -- se ejecuta de verdad en Node contra un `convState` de
mentira, mismo criterio que el resto de funciones puras de esta sesión.
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

BIENVENIDA = ("Hola, soy ArchMuse. ¿Analizamos un plano? Adjunta un DXF y "
              "pregúntame lo que necesites medir.")


def _extraer(desde: str, hasta: str) -> str:
    inicio = JS.index(desde)
    fin = JS.index(hasta, inicio)
    return JS[inicio:fin]


FUNCION_CONVMENSAJESALUDO = _extraer("function convMensajeSaludo() {", "\n  }") + "\n  }"


def _ejecutar_js(programa: str):
    resultado = subprocess.run(
        ["node", "-e", programa], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert resultado.returncode == 0, "node falló: %s" % resultado.stderr
    return json.loads(resultado.stdout)


def _mensaje(archivo_adjunto, saludos_sin_adjunto: int) -> str:
    """Una llamada AISLADA a `convMensajeSaludo()` con el `convState` que
    se le pida -- para las secuencias reales (saluda, saluda, adjunta,
    saluda) ver `test_la_transicion_saludo_a_dxf_adjuntado_no_cambia`."""
    convstate_js = "var convState = {archivoAdjunto: %s, saludosSinAdjunto: %d};" % (
        json.dumps(archivo_adjunto), saludos_sin_adjunto)
    programa = convstate_js + "\n" + FUNCION_CONVMENSAJESALUDO + "\nconsole.log(JSON.stringify(convMensajeSaludo()));"
    return _ejecutar_js(programa)


# --- 1. Primer saludo: la bienvenida de siempre, intacta -------------------

def test_primer_saludo_sin_dxf_es_la_bienvenida_de_siempre_sin_cambiar_ni_una_palabra():
    """`saludosSinAdjunto` vale 1 en la llamada real (se incrementa ANTES
    de llamar aquí, en `convEnviarPregunta`) -- éste es el valor real del
    primer saludo de una sesión."""
    assert _mensaje(None, 1) == BIENVENIDA


# --- 2. Segundo saludo y siguientes: variante corta, no el calco -----------

def test_segundo_saludo_sin_dxf_no_repite_la_bienvenida_completa():
    mensaje = _mensaje(None, 2)
    assert mensaje != BIENVENIDA
    assert "Hola, soy ArchMuse" not in mensaje  # no es un calco parcial tampoco


def test_tercer_saludo_sin_dxf_tampoco_repite_la_bienvenida():
    """El caso exacto que reportó Pablo: "hola", "hola", "qué tal" -- las
    tres sin DXF. La tercera (`saludosSinAdjunto == 3`) tampoco puede
    coincidir con la bienvenida original."""
    assert _mensaje(None, 3) != BIENVENIDA


def test_la_variante_sigue_hablando_estrictamente_de_adjuntar_el_dxf():
    """Restricción explícita del encargo: "no simular charla libre... el
    ámbito sigue siendo estrictamente 'sin DXF, no puedo hacer nada
    todavía'". La variante corta tiene que seguir mencionando lo único que
    de verdad hace falta -- el DXF -- no inventar un tema de conversación
    nuevo."""
    mensaje = _mensaje(None, 2).lower()
    assert "dxf" in mensaje or "plano" in mensaje


# --- 3. Con DXF adjunto: sin cambios, pase lo que pase con el contador -----

def test_con_dxf_el_mensaje_no_depende_del_contador_de_saludos():
    """Criterio explícito de Pablo: la rama "con DXF" es exactamente la
    misma de siempre, para cualquier valor de `saludosSinAdjunto` -- el
    contador de saludos SIN adjunto es irrelevante en cuanto hay uno."""
    esperado = "Hola, soy ArchMuse. Ya tienes plano.dxf adjunto -- ¿qué quieres que mida?"
    for contador in (0, 1, 2, 5):
        assert _mensaje({"name": "plano.dxf"}, contador) == esperado


def test_la_transicion_saludo_a_dxf_adjuntado_no_cambia():
    """La transición real que pidió comprobar Pablo explícitamente: saluda
    (una o varias veces) sin DXF, LUEGO adjunta el DXF, y el comportamiento
    con DXF tiene que ser exactamente el de siempre -- nunca "atascado" en
    el modo de saludo genérico. Se simula la secuencia real de
    `convEnviarPregunta` en un solo programa de Node: dos saludos sin
    archivo (incrementando `saludosSinAdjunto` como haría esa función),
    luego se adjunta un DXF, y se llama una tercera vez."""
    programa = (
        "var convState = {archivoAdjunto: null, saludosSinAdjunto: 0};\n" +
        FUNCION_CONVMENSAJESALUDO + "\n"
        "var respuestas = [];\n"
        "convState.saludosSinAdjunto += 1; respuestas.push(convMensajeSaludo());  // 1er saludo\n"
        "convState.saludosSinAdjunto += 1; respuestas.push(convMensajeSaludo());  // 2o saludo\n"
        "convState.archivoAdjunto = {name: 'plano.dxf'};  // el arquitecto adjunta el DXF\n"
        "respuestas.push(convMensajeSaludo());  // 3er saludo, ya con DXF\n"
        "console.log(JSON.stringify(respuestas));"
    )
    primero, segundo, tercero = _ejecutar_js(programa)
    assert primero == BIENVENIDA
    assert segundo != BIENVENIDA
    assert tercero == "Hola, soy ArchMuse. Ya tienes plano.dxf adjunto -- ¿qué quieres que mida?"


# --- 4. El contador se lleva donde debe, y sólo ahí -------------------------

def test_el_contador_se_incrementa_en_convenviarpregunta_solo_sin_archivo():
    """`convMensajeSaludo()` es de lectura pura (no muta `convState`) --
    el incremento vive en `convEnviarPregunta`, gated a `!archivo`, y
    ANTES de llamar a `convMensajeSaludo()`."""
    cuerpo = _extraer("if (_convEsSaludo(pregunta)) {", "\n    }")
    assert "convState.saludosSinAdjunto += 1;" in cuerpo
    pos_incremento = cuerpo.index("if (!archivo) convState.saludosSinAdjunto += 1;")
    # La llamada REAL, no una mención de su nombre en un comentario (este
    # mismo bloque tiene una, explicando por qué el incremento no vive
    # dentro de `convMensajeSaludo()`) -- se ancla a la línea completa.
    pos_mensaje = cuerpo.index("convAnadirRespuesta(convTarjetaSaludo(convMensajeSaludo()));")
    assert pos_incremento < pos_mensaje


def test_convmensajesaludo_no_muta_convstate():
    """Función de lectura pura -- si empezara a incrementar el contador
    ella misma, dos llamadas seguidas (p. ej. desde un futuro caller
    distinto) contarían saludos que no se han enviado de verdad."""
    cuerpo = FUNCION_CONVMENSAJESALUDO
    assert not re.search(r"convState\.\w+\s*(\+\+|\+=|=[^=])", cuerpo), (
        "convMensajeSaludo() ya no es una función pura: muta convState")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
