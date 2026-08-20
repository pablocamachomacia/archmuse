# -*- coding: utf-8 -*-
"""Adjuntar hablando + sugerencia en línea, panel de conversación (sesión
2026-08-19, noche 7, dos peticiones directas de Pablo en el mismo turno).

Ejecutar:  pytest tests/test_conversacion_adjuntar_y_sugerencias.py

Mismo criterio que `tests/test_conversacion_saludo.py`: las funciones puras
(`_convEsIntencionDeAdjuntar`, `_convSugerirCompletado`) se extraen tal cual
de `static/app.js` y se ejecutan de verdad en Node -- nada reimplementado en
Python que pudiera divergir del comportamiento real. Requiere `node` en PATH.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
JS = (RAIZ / "static" / "app.js").read_text(encoding="utf-8")


def _extraer(inicio_marca: str, fin_marca: str) -> str:
    inicio = JS.index(inicio_marca)
    fin = JS.index(fin_marca, inicio)
    return JS[inicio:fin]


FUNCION_ADJUNTAR = _extraer("var CONV_VERBOS_ADJUNTAR = [", "\n  function convRegistrarArchivoUsado")
FUNCION_SUGERIR = _extraer("function _convSinAcentos(s) {", "\n\n  function convActualizarSugerencia")


def _node(programa: str):
    resultado = subprocess.run(
        ["node", "-e", programa],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert resultado.returncode == 0, "node falló: %s" % resultado.stderr
    return json.loads(resultado.stdout)


# --- _convEsIntencionDeAdjuntar ---------------------------------------------

CASOS_ADJUNTAR = [
    ("abre el plano de mi escritorio", True),
    ("analiza este DXF", True),
    ("Sube el archivo", True),
    ("adjunta el plano, por favor", True),
    ("carga el fichero nuevo", True),
    ("", False),
    ("hola", False),
    # Nunca sobre una pregunta real -- el "?" es la señal de que es una
    # pregunta, no una orden, aunque mencione "plano"/"dxf" igual.
    ("¿puedes abrir este plano y decirme la superficie?", False),
    ("¿cuánta superficie útil tiene esta planta?", False),
    ("¿cuánto va a costar construir este edificio?", False),
    # Menciona un sustantivo de fichero pero sin verbo de acción -- no es
    # una orden de adjuntar.
    ("el plano está muy bien", False),
]


def test_intencion_de_adjuntar_no_choca_con_preguntas_reales():
    llamadas = ",\n".join(
        "[%s, _convEsIntencionDeAdjuntar(%s)]" % (json.dumps(e), json.dumps(e))
        for e, _ in CASOS_ADJUNTAR
    )
    programa = FUNCION_ADJUNTAR + "\nconsole.log(JSON.stringify([\n" + llamadas + "\n]));"
    pares = _node(programa)
    fallos = [
        "%r -> esperado %s, obtenido %s" % (e, esperado, obtenido)
        for (e, esperado), (_, obtenido) in zip(CASOS_ADJUNTAR, pares)
        if obtenido != esperado
    ]
    assert not fallos, "\n".join(fallos)


# --- _convSugerirCompletado --------------------------------------------------

def test_sugerir_completado_devuelve_el_resto_correcto():
    programa = FUNCION_SUGERIR + """
console.log(JSON.stringify(
  _convSugerirCompletado("cuanta", ["cuanta superficie util tiene esta planta"])
));
"""
    r = _node(programa)
    assert r == {"completo": "cuanta superficie util tiene esta planta", "resto": " superficie util tiene esta planta"}


def test_sugerir_completado_no_distingue_mayusculas_en_el_prefijo():
    programa = FUNCION_SUGERIR + """
console.log(JSON.stringify(
  _convSugerirCompletado("Cuánta", ["cuánta superficie útil tiene esta planta"])
));
"""
    r = _node(programa)
    assert r["completo"] == "cuánta superficie útil tiene esta planta"


def test_sugerir_completado_ignora_apertura_de_interrogacion_y_acentos():
    """Bug real encontrado en la verificación en vivo: `CONV_EJEMPLOS`
    empieza con "¿Cuánta..." pero el usuario teclea "cu" (sin "¿") o
    "cuanta" (sin tilde, habitual al escribir rápido) -- ninguno de los
    dos puede quedarse sin sugerencia sólo por eso."""
    candidatas = ["¿Cuánta superficie útil tiene esta planta?"]
    programa = FUNCION_SUGERIR + """
console.log(JSON.stringify([
  _convSugerirCompletado("cu", %s),
  _convSugerirCompletado("cuanta", %s)
]));
""" % (json.dumps(candidatas), json.dumps(candidatas))
    r = _node(programa)
    for resultado in r:
        assert resultado is not None
        assert resultado["completo"] == "¿Cuánta superficie útil tiene esta planta?"
    # El primer caso ("cu"): el resto es lo que falta de la candidata SIN
    # el "¿" inicial -- eso vive en el propio texto ya escrito, no en el
    # fantasma.
    assert r[0]["resto"] == "ánta superficie útil tiene esta planta?"


def test_sugerir_completado_null_si_nada_encaja():
    programa = FUNCION_SUGERIR + """
console.log(JSON.stringify([
  _convSugerirCompletado("presupuesto de", ["cuanta superficie util tiene esta planta"]),
  _convSugerirCompletado("", ["cuanta superficie util tiene esta planta"]),
  _convSugerirCompletado("cuanta superficie util tiene esta planta", ["cuanta superficie util tiene esta planta"])
]));
"""
    r = _node(programa)
    assert r == [None, None, None]  # el tercero: ya está completo, no queda "resto" que ofrecer


# --- Guardianes estáticos: sin red, sin normativa/coste/3D en la sugerencia -

def test_convactualizarsugerencia_es_puramente_local():
    """El objetivo explícito del encargo: "ninguna llamada a la API del
    modelo... para no gastar tokens sólo por escribir en la caja"."""
    inicio = JS.index("function convActualizarSugerencia()")
    fin = JS.index("\n  }", inicio)
    cuerpo = JS[inicio:fin]
    assert "fetch(" not in cuerpo


def test_el_registro_de_sugerencias_no_promete_capacidades_inexistentes():
    """`CONV_SUGERENCIAS_POR_CAPACIDAD` sólo puede completar hacia preguntas
    de una capacidad REALMENTE registrada -- nunca normativa, coste o 3D,
    aunque sea sólo como sugerencia de texto (misma regla de oro que
    prohíbe inventar una respuesta)."""
    inicio = JS.index("var CONV_SUGERENCIAS_POR_CAPACIDAD = {")
    # Sin exigir "\n\n  " justo antes del `function`: un comentario explicativo
    # delante de la función (como el que se añadió el 2026-08-20 al dar
    # prioridad al modo activo) es contenido legítimo, no un cambio del
    # propio registro que este test vigila.
    fin = JS.index("function _convCandidatasDeSugerencia", inicio)
    bloque = JS[inicio:fin]
    for termino in ("normativa", "presupuesto", "coste", "€", "%", "geometría 3d", "cumplimiento"):
        assert termino not in bloque.lower(), "encontrado %r en el registro de sugerencias" % termino


def test_los_chips_prueba_en_su_lugar_ya_no_estan_en_fuera_de_alcance():
    """Sustituidos por la sugerencia en línea (petición directa de Pablo,
    "en vez de chips") -- `CONV_EJEMPLOS` sigue viva, pero ya no se
    renderiza como chips dentro de `convTarjetaFueraDeAlcance`."""
    inicio = JS.index("function convTarjetaFueraDeAlcance(mensaje) {")
    fin = JS.index("\n\n  function convTarjetaError", inicio)
    cuerpo = JS[inicio:fin]
    # Se quitan los comentarios de línea antes de comprobar: el propio
    # comentario que documenta la retirada de los chips menciona su nombre
    # literal ("los chips 'Prueba en su lugar' desaparecen de aquí") --
    # explicar que algo se quitó no es lo mismo que seguir mostrándolo (ver
    # el mismo criterio en test_conversacion_archmuse_ui.py).
    cuerpo_sin_comentarios = re.sub(r"//[^\n]*", "", cuerpo)
    assert "Prueba en su lugar" not in cuerpo_sin_comentarios
    assert "data-pregunta" not in cuerpo_sin_comentarios
    # El roadmap "en el mapa, todavía no" SIGUE ahí -- no es lo que se pidió quitar.
    assert "En el mapa, todavía no" in cuerpo_sin_comentarios


def test_tab_acepta_la_sugerencia_sin_enviar_el_formulario():
    inicio = JS.index('e.key === "Tab" && convState.sugerenciaActual')
    fin = JS.index('if (e.key === "Enter"', inicio)
    bloque = JS[inicio:fin]
    assert "e.preventDefault();" in bloque
    assert "textarea.value = convState.sugerenciaActual.completo;" in bloque


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
