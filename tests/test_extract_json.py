# -*- coding: utf-8 -*-
"""`_extract_json` (analyzer/ai_analyst.py) — fix 2026-08-16 de un fallo real reportado en
producción: `json.JSONDecodeError: Unterminated string starting at...` al parsear la respuesta de
la IA. Compartida por `ai_analyst.py`, `ai_generator.py` y `interview/claude_interprete.py` (los
tres importan la misma función, nunca la duplican) -- este archivo prueba la función una sola vez
y confirma por identidad que los otros dos módulos usan exactamente la misma.

Ejecutar:  python tests/test_extract_json.py

Mismo estilo que el resto de `tests/`: script sin pytest, `check()` acumula fallos, sale con
código 1 si algo falla. Nunca llama a Claude de verdad -- son todo cadenas de texto fabricadas a
mano, simulando respuestas reales del modelo con los defectos de formato que de verdad se han
observado.
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import ai_analyst  # noqa: E402
from analyzer import ai_generator  # noqa: E402
from analyzer.interview import claude_interprete  # noqa: E402

fallos = []
comprobaciones = 0


def check(nombre, cond, detalle=""):
    global comprobaciones
    comprobaciones += 1
    estado = "OK  " if cond else "FALLO"
    print("  [%s] %s%s" % (estado, nombre, ("  -> " + str(detalle)) if detalle else ""))
    if not cond:
        fallos.append(nombre)


extraer = ai_analyst._extract_json

# =============================================================================
print("=" * 70)
print("1. Casos ya soportados antes del fix (no deben romperse)")
print("=" * 70)

check("JSON limpio, sin nada alrededor", extraer('{"a": 1}') == {"a": 1})
check("Envuelto en ```json ... ```", extraer('```json\n{"a": 1}\n```') == {"a": 1})
check("Envuelto en ``` ... ``` sin la etiqueta 'json'", extraer('```\n{"a": 1}\n```') == {"a": 1})
check("Con espacios/saltos de línea alrededor del objeto", extraer('  \n{"a": 1}\n  ') == {"a": 1})


# =============================================================================
print()
print("=" * 70)
print("2. Preámbulo/cierre en texto plano alrededor del objeto (nuevo)")
print("=" * 70)

check(
    "Preámbulo antes del objeto, sin bloque de código",
    extraer('Aquí tienes el JSON solicitado:\n{"a": 1}') == {"a": 1},
)
check(
    "Preámbulo Y cierre en texto plano",
    extraer('Aquí tienes el JSON:\n{"a": 1}\n¿Necesitas algo más?') == {"a": 1},
)
check(
    "Preámbulo/cierre alrededor de un bloque ```json fenced",
    extraer('Aquí tienes el JSON:\n```json\n{"a": 1}\n```\n¿Necesitas algo más?') == {"a": 1},
)


# =============================================================================
print()
print("=" * 70)
print("3. Comas finales antes de '}' o ']' (error común de formato en JSON de un LLM)")
print("=" * 70)

check("Coma final antes de '}'", extraer('{"a": 1,}') == {"a": 1})
check("Coma final antes de ']'", extraer('{"a": [1, 2, 3,]}') == {"a": [1, 2, 3]})
check("Coma final en objeto anidado", extraer('{"a": {"b": 1,},}') == {"a": {"b": 1}})
check(
    "Coma final NO se confunde con una coma dentro de una cadena",
    extraer('{"a": "uno, dos, tres"}') == {"a": "uno, dos, tres"},
)


# =============================================================================
print()
print("=" * 70)
print("4. EL BUG REAL: salto de línea sin escapar dentro de una cadena")
print("=" * 70)
print("   ('Unterminated string starting at...' reportado en producción)")

# Antes del fix, esto reventaba: json.loads estricto rechaza un carácter de control (\n) literal
# dentro de una cadena con "Invalid control character", y en la práctica el parser terminaba
# perdiendo la referencia de dónde cerraba la cadena, produciendo el "Unterminated string" real.
texto_con_salto_literal = '{"justificacion": "Primera línea.\nSegunda línea.", "plantas": []}'
resultado = extraer(texto_con_salto_literal)
check("con strict=False, ya NO lanza json.JSONDecodeError", resultado is not None)
check(
    "el salto de línea literal se conserva tal cual en el valor (no se pierde información)",
    resultado.get("justificacion") == "Primera línea.\nSegunda línea.",
    resultado.get("justificacion"),
)
check("el resto del objeto se parsea con normalidad", resultado.get("plantas") == [])

# Con \n correctamente escapado (el caso "bueno", el que pide el prompt) sigue funcionando igual.
texto_bien_escapado = '{"justificacion": "Primera línea.\\nSegunda línea."}'
check(
    "con \\n correctamente escapado (caso ya válido) sigue funcionando",
    extraer(texto_bien_escapado).get("justificacion") == "Primera línea.\nSegunda línea.",
)

# Combinación real: bloque markdown + coma final + salto de línea sin escapar, los tres defectos
# a la vez, tal como podría llegar de verdad una respuesta del modelo.
texto_combinado = (
    "Aquí está el proyecto generado:\n"
    "```json\n"
    '{"justificacion": "Distribución en dos plantas.\nOrientación sur.", "plantas": [1, 2,],}\n'
    "```\n"
    "Espero que te sea de ayuda."
)
resultado_combinado = extraer(texto_combinado)
check(
    "los tres defectos combinados (markdown + coma final + salto sin escapar) se resuelven juntos",
    resultado_combinado == {"justificacion": "Distribución en dos plantas.\nOrientación sur.", "plantas": [1, 2]},
    resultado_combinado,
)


# =============================================================================
print()
print("=" * 70)
print("5. Respuesta genuinamente truncada -- NUNCA se repara con un cierre inventado")
print("=" * 70)

texto_truncado = '{"justificacion": "Se corta a mitad de es'  # ni comilla de cierre ni '}'
try:
    extraer(texto_truncado)
    check("una respuesta truncada SIGUE lanzando (nunca fabrica un cierre)", False)
except json.JSONDecodeError as exc:
    check("una respuesta truncada SIGUE lanzando (nunca fabrica un cierre)", True)
    check(
        "pero con un mensaje honesto que dice 'se cortó', no el genérico de json",
        "se cortó" in str(exc) and "límite de tokens" in str(exc),
        str(exc),
    )

# Un error de formato real (comilla mal escapada) EN MITAD del texto, lejos del final -- no debe
# etiquetarse como "truncado" (sería un diagnóstico falso): sigue siendo el error real de json.
texto_con_comilla_suelta = '{"a": "valor con una " comilla suelta", "b": 2}'
try:
    extraer(texto_con_comilla_suelta)
    check("comilla suelta en mitad del texto: json.loads debería fallar igualmente", False)
except json.JSONDecodeError as exc:
    check(
        "el error de una comilla suelta en mitad del texto NO se etiqueta como 'truncado'",
        "se cortó" not in str(exc),
        str(exc),
    )


# =============================================================================
print()
print("=" * 70)
print("6. Los tres módulos comparten literalmente la misma función (nunca duplicada)")
print("=" * 70)

check("ai_generator._extract_json ES ai_analyst._extract_json (misma función, no una copia)",
      ai_generator._extract_json is ai_analyst._extract_json)
check("claude_interprete._extract_json ES ai_analyst._extract_json (misma función, no una copia)",
      claude_interprete._extract_json is ai_analyst._extract_json)


# =============================================================================
print()
print("=" * 70)
print("7. Los tres prompts refuerzan explícitamente el escape de \\n y \\\" (preventivo)")
print("=" * 70)

check("SYSTEM_PROMPT de ai_generator.py menciona el escape de saltos de línea/comillas",
      "Escapa" in ai_generator.SYSTEM_PROMPT and "salto de línea" in ai_generator.SYSTEM_PROMPT)
check("SYSTEM_PROMPT de ai_analyst.py menciona el escape de saltos de línea/comillas",
      "Escapa" in ai_analyst.SYSTEM_PROMPT and "salto de línea" in ai_analyst.SYSTEM_PROMPT)
check("SYSTEM_PROMPT de claude_interprete.py menciona el escape de saltos de línea/comillas",
      "Escapa" in claude_interprete.SYSTEM_PROMPT and "salto de línea" in claude_interprete.SYSTEM_PROMPT)


# =============================================================================
print()
print("=" * 70)
if fallos:
    print("RESUMEN: %d comprobaciones, %d fallos" % (comprobaciones, len(fallos)))
    print("Fallaron:")
    for f in fallos:
        print("  - " + f)
    print("=" * 70)
    sys.exit(1)
else:
    print("RESUMEN: %d comprobaciones, 0 fallos" % comprobaciones)
    print("=" * 70)
    print("Todo OK.")
