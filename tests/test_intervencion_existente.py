# -*- coding: utf-8 -*-
"""Prueba de "Editar / Intervenir edificación existente" — el bloque
"INTERVENCIÓN EN EDIFICACIÓN EXISTENTE" que `analyzer/ai_generator.py`
inyecta en el prompt cuando `params["intervencion_existente"]["tipo"] ==
"edificacion_existente"`, y su paso a través de `app.py:
_parse_generar_params`.

Ejecutar:  python tests/test_intervencion_existente.py

`analyzer/interview/compilador.py` (quien produce esta clave desde modo
experto) tiene su propia cobertura en `tests/test_interview_compilador.py`
(sección 17) — este archivo cubre exclusivamente la mitad que consume esa
clave (`ai_generator._compilar_bloque_intervencion`/`_build_user_message`)
y la mitad que la reenvía tal cual sobre un body crudo de `/api/generar`
(`app.py:_parse_generar_params`, sin arrancar el servidor Flask: son
funciones puras). Cero llamadas a la API real de Anthropic — ninguno de
estos tests construye un cliente `anthropic.Anthropic`.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

os.environ.pop("ANTHROPIC_API_KEY", None)  # este test no debe poder llamar a la IA aunque quisiera

from analyzer import ai_generator  # noqa: E402

fallos = []
comprobaciones = 0


def check(nombre, cond, detalle=""):
    global comprobaciones
    comprobaciones += 1
    estado = "OK  " if cond else "FALLO"
    print("  [%s] %s%s" % (estado, nombre, ("  -> " + str(detalle)) if detalle else ""))
    if not cond:
        fallos.append(nombre)


def _params_base(intervencion=None):
    params = {
        "proyecto": {"ciudad": "Valencia", "tipologia": "plurifamiliar", "zona_cte": "B"},
        "solar": {"superficie_m2": 800, "forma": "rectangular", "ancho_m": 20, "largo_m": 40, "norte_grados": 180.0},
        "edificio": {"plantas": 4, "altura_libre_m": 2.8, "planta_baja_comercial": False},
        "mix_viviendas": {"dorm_1": 0, "dorm_2": 4, "dorm_3": 0, "superficie_minima_m2": 40},
        "normativa": {"ocupacion_maxima_pct": 70, "retranqueos_m": 3, "edificabilidad_maxima": None, "plantas_maximas": None},
    }
    if intervencion is not None:
        params["intervencion_existente"] = intervencion
    return params


# =============================================================================
# 1. _compilar_bloque_intervencion() — plantilla determinista, sin IA
# =============================================================================
print("=" * 70)
print("1. _compilar_bloque_intervencion()")
print("=" * 70)

check("ausente -> ''", ai_generator._compilar_bloque_intervencion(None) == "")
check("dict vacío -> ''", ai_generator._compilar_bloque_intervencion({}) == "")
check("tipo='obra_nueva' -> ''", ai_generator._compilar_bloque_intervencion({"tipo": "obra_nueva"}) == "")
check(
    "tipo con basura ('rehabilitacion_parcial') -> ''",
    ai_generator._compilar_bloque_intervencion({"tipo": "rehabilitacion_parcial"}) == "",
)
check("no es un dict (string) -> ''", ai_generator._compilar_bloque_intervencion("edificacion_existente") == "")

bloque_sin_conservar = ai_generator._compilar_bloque_intervencion({"tipo": "edificacion_existente"})
check("edificacion_existente sin elementos_a_conservar -> SÍ produce bloque", bloque_sin_conservar != "")
check("el bloque tiene el título literal pedido", bloque_sin_conservar.startswith("INTERVENCIÓN EN EDIFICACIÓN EXISTENTE:"))
check("indica que NO parta de un solar vacío", "no" in bloque_sin_conservar.lower() and "obra nueva" in bloque_sin_conservar.lower())
check("sin conservar declarado -> pide al modelo que proponga una estrategia razonable", "estrategia" in bloque_sin_conservar.lower())

bloque_con_conservar = ai_generator._compilar_bloque_intervencion({
    "tipo": "edificacion_existente",
    "elementos_a_conservar": "Conservar estructura principal y fachadas. Demoler distribución interior.",
})
check(
    "con elementos_a_conservar -> el texto literal del usuario aparece citado",
    "Conservar estructura principal y fachadas. Demoler distribución interior." in bloque_con_conservar,
)
check("con conservar declarado -> NO le pide al modelo que invente la estrategia", "estrategia" not in bloque_con_conservar.lower())

bloque_conservar_blanco = ai_generator._compilar_bloque_intervencion({
    "tipo": "edificacion_existente", "elementos_a_conservar": "   ",
})
check(
    "elementos_a_conservar en blanco se trata como 'no declarado' (mismo texto que sin la clave)",
    bloque_conservar_blanco == bloque_sin_conservar,
)

bloque_conservar_no_str = ai_generator._compilar_bloque_intervencion({
    "tipo": "edificacion_existente", "elementos_a_conservar": 123,
})
check("elementos_a_conservar que no es string no rompe -> se trata como ausente", bloque_conservar_no_str == bloque_sin_conservar)


# =============================================================================
# 2. Integración en _build_user_message() — compatibilidad y orden
# =============================================================================
print("=" * 70)
print("2. _build_user_message()")
print("=" * 70)

mensaje_sin_clave = ai_generator._build_user_message(_params_base())
mensaje_obra_nueva = ai_generator._build_user_message(_params_base({"tipo": "obra_nueva"}))
check(
    "sin la clave 'intervencion_existente' el mensaje es BYTE A BYTE el de siempre",
    "INTERVENCIÓN EN EDIFICACIÓN EXISTENTE" not in mensaje_sin_clave,
)
check("con tipo='obra_nueva' el mensaje es idéntico al de 'sin la clave'", mensaje_obra_nueva == mensaje_sin_clave)

mensaje_existente = ai_generator._build_user_message(_params_base({
    "tipo": "edificacion_existente", "elementos_a_conservar": "Conservar la fachada principal.",
}))
check("con edificacion_existente el bloque SÍ aparece en el mensaje final", "INTERVENCIÓN EN EDIFICACIÓN EXISTENTE" in mensaje_existente)
check("el texto de elementos_a_conservar llega literal al mensaje final", "Conservar la fachada principal." in mensaje_existente)
check(
    "el bloque va DESPUÉS del bloque JSON de datos del proyecto (contrato §8.2, mismo criterio que directivas)",
    mensaje_existente.index("INTERVENCIÓN EN EDIFICACIÓN EXISTENTE") > mensaje_existente.index("Datos del proyecto (JSON):"),
)

# Combinado con una directiva cualitativa real: ambos bloques deben convivir,
# ninguno pisa al otro.
mensaje_combinado = ai_generator._build_user_message({
    **_params_base({"tipo": "edificacion_existente", "elementos_a_conservar": "Conservar la estructura."}),
    "contexto_cualitativo": {
        "especificacion_id": "spec-test",
        "directivas": [{
            "especificacion_id": "usuarios.accesibilidad", "categoria": "accesibilidad", "fuerza": "dura",
            "texto_origen": "x",
            "texto_prompt": "Garantiza un itinerario accesible sin escalones y al menos un baño accesible en cada vivienda.",
            "verificable_geometricamente": True,
        }],
        "texto_prompt": "",
    },
})
check("con directivas Y con intervención existente, las directivas SÍ siguen apareciendo", "DEBES CUMPLIR" in mensaje_combinado)
check("con directivas Y con intervención existente, la intervención SÍ sigue apareciendo", "INTERVENCIÓN EN EDIFICACIÓN EXISTENTE" in mensaje_combinado)
check(
    "orden: directivas (contexto_cualitativo) antes que intervención (mismo orden en que se anexan en el código)",
    mensaje_combinado.index("DEBES CUMPLIR") < mensaje_combinado.index("INTERVENCIÓN EN EDIFICACIÓN EXISTENTE"),
)


# =============================================================================
# 3. app.py:_parse_generar_params — reenvío tal cual desde un body crudo
# =============================================================================
print("=" * 70)
print("3. app.py:_parse_generar_params()")
print("=" * 70)

import app  # noqa: E402  (después de los tests 1-2 a propósito: si esto fallara al importar, no se pierde la cobertura de ai_generator)

BODY_MINIMO = {
    "solar": {"superficie_m2": 500, "forma": "rectangular", "norte_grados": 0},
    "mix_viviendas": {"dorm_1": 1, "dorm_2": 0, "dorm_3": 0},
}

params_sin_clave = app._parse_generar_params(dict(BODY_MINIMO))
check("body sin 'intervencion_existente' -> la clave NI SIQUIERA se añade (igual que contexto_cualitativo)", "intervencion_existente" not in params_sin_clave)

params_con_clave = app._parse_generar_params({
    **BODY_MINIMO,
    "intervencion_existente": {"tipo": "edificacion_existente", "elementos_a_conservar": "Conservar fachadas."},
})
check(
    "body CON 'intervencion_existente' (dict) -> se reenvía tal cual, sin revalidar aquí su forma interna",
    params_con_clave.get("intervencion_existente") == {"tipo": "edificacion_existente", "elementos_a_conservar": "Conservar fachadas."},
)

params_clave_basura = app._parse_generar_params({**BODY_MINIMO, "intervencion_existente": "no es un dict"})
check(
    "body con 'intervencion_existente' que NO es un dict -> se descarta silenciosamente (mismo criterio que contexto_cualitativo)",
    "intervencion_existente" not in params_clave_basura,
)

# End-to-end de las dos mitades juntas: el dict que produce app.py alimenta
# directamente a ai_generator sin ningún paso intermedio.
mensaje_end_to_end = ai_generator._build_user_message({
    **params_con_clave,
    "proyecto": {**params_con_clave["proyecto"], "zona_cte": "B"},
})
check(
    "end-to-end: params de _parse_generar_params -> _build_user_message produce el bloque",
    "INTERVENCIÓN EN EDIFICACIÓN EXISTENTE" in mensaje_end_to_end and "Conservar fachadas." in mensaje_end_to_end,
)


# =============================================================================
# RESUMEN
# =============================================================================
print("=" * 70)
print("RESUMEN: %d comprobaciones, %d fallos" % (comprobaciones, len(fallos)))
print("=" * 70)
if fallos:
    print("Fallos:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("Todo OK.")
