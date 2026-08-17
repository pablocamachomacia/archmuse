# -*- coding: utf-8 -*-
"""Prueba de `analyzer/estilos.py` y su integración en `app.py`/
`ai_generator.py`.

Ejecutar:  python tests/test_estilos.py

La rama de catálogo (14 estilos base) y `aplicar_estilo_a_prompt` son
deterministas, sin red. La rama de texto libre se prueba con un cliente
Anthropic FALSO (nunca el real `anthropic.Anthropic`) — mismo criterio que
`FakeInterprete` en `tests/test_interview_motor.py`: cero llamadas reales en
la suite normal, y se puede afirmar con certeza qué se le pidió al "modelo"
sin depender de lo que responda de verdad.
"""
import json
import os
import sys
from types import SimpleNamespace

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

os.environ.pop("ANTHROPIC_API_KEY", None)  # este test no debe poder llamar a la IA aunque quisiera

from analyzer.estilos import (  # noqa: E402
    CATALOGO_ESTILOS,
    DEFAULT_ESTILO,
    ORIENTACIONES_HUECOS,
    TIPOS_RITMO,
    ErrorDeEstilo,
    aplicar_estilo_a_prompt,
    obtener_estilo,
)

fallos = []


def check(nombre, cond, detalle=""):
    estado = "OK  " if cond else "FALLO"
    print("  [%s] %s%s" % (estado, nombre, ("  -> " + str(detalle)) if detalle else ""))
    if not cond:
        fallos.append(nombre)


print("1. Catálogo de 14 estilos base")
check("hay exactamente 14 estilos", len(CATALOGO_ESTILOS) == 14, len(CATALOGO_ESTILOS))
check("«racionalista» es el valor por defecto y existe en el catálogo", DEFAULT_ESTILO in CATALOGO_ESTILOS)

CAMPOS_OBLIGATORIOS = {
    "nombre_estilo", "proporcion_huecos", "ritmo_fachada",
    "materiales_compatibles", "solucion_cubierta", "vuelo_maximo_m", "textura",
}
for clave, estilo in CATALOGO_ESTILOS.items():
    check("%s: trae los 7 campos obligatorios" % clave, set(estilo.keys()) == CAMPOS_OBLIGATORIOS, sorted(estilo.keys()))
    check("%s: proporcion_huecos.orientacion es válida" % clave,
          estilo["proporcion_huecos"]["orientacion"] in ORIENTACIONES_HUECOS)
    check("%s: ritmo_fachada.tipo es válido" % clave, estilo["ritmo_fachada"]["tipo"] in TIPOS_RITMO)
    check("%s: materiales_compatibles no está vacío" % clave, len(estilo["materiales_compatibles"]) > 0)
    check("%s: vuelo_maximo_m es un número positivo razonable (<=3.5m)" % clave,
          0 < estilo["vuelo_maximo_m"] <= 3.5, estilo["vuelo_maximo_m"])

print("\n2. obtener_estilo() por clave de catálogo — determinista, sin cliente")
brutalista = obtener_estilo("brutalista")
check("devuelve el estilo del catálogo tal cual", brutalista == CATALOGO_ESTILOS["brutalista"])
check("acepta variaciones de tildes/mayúsculas/guiones", obtener_estilo("Clásico Contemporáneo") == CATALOGO_ESTILOS["clasico_contemporaneo"])
check("acepta guion en vez de guion bajo", obtener_estilo("high-tech") == CATALOGO_ESTILOS["high_tech"])
check(
    "una clave de catálogo nunca necesita cliente ni levanta ErrorDeEstilo",
    obtener_estilo("nordico", client_anthropic="esto rompería si se llegara a usar") == CATALOGO_ESTILOS["nordico"],
)

print("\n3. obtener_estilo() con texto libre — cliente Anthropic FALSO, cero red")


class _BloqueFalso:
    type = "tool_use"

    def __init__(self, input_):
        self.input = input_


class _RespuestaFalsa:
    def __init__(self, input_, stop_reason="tool_use"):
        self.stop_reason = stop_reason
        self.content = [_BloqueFalso(input_)] if input_ is not None else []


class _ClienteFalso:
    """Nunca importa ni construye `anthropic.Anthropic` real. Guarda la
    última llamada para poder comprobar qué se le pidió."""

    def __init__(self, respuesta):
        self._respuesta = respuesta
        self.ultima_llamada = None
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.ultima_llamada = kwargs
        return self._respuesta


ESTILO_INTERPRETADO = {
    "nombre_estilo": "Brutalismo mediterráneo",
    "proporcion_huecos": {"ratio_alto_ancho": 1.1, "orientacion": "vertical"},
    "ritmo_fachada": {"modulo_m": 3.2, "tipo": "irregular"},
    "materiales_compatibles": ["hormigón visto", "piedra local"],
    "solucion_cubierta": "plana con petos altos",
    "vuelo_maximo_m": 1.8,
    "textura": "rugosa",
}
cliente_falso = _ClienteFalso(_RespuestaFalsa(ESTILO_INTERPRETADO))
resultado_libre = obtener_estilo("brutalismo mediterráneo, con aire a Chipperfield", client_anthropic=cliente_falso)
check("devuelve exactamente lo que la herramienta forzada rellenó", resultado_libre == ESTILO_INTERPRETADO)
check("se llamó a tool_choice forzado (determinismo del esquema)",
      cliente_falso.ultima_llamada["tool_choice"]["name"] == "registrar_estilo_arquitectonico")
check("el SYSTEM_PROMPT va cacheado", cliente_falso.ultima_llamada["system"][0]["cache_control"] == {"type": "ephemeral"})
check("el texto libre viaja en el mensaje de usuario",
      "brutalismo mediterráneo" in cliente_falso.ultima_llamada["messages"][0]["content"])

print("\n4. obtener_estilo() con texto libre — fallos del modelo, nunca un resultado a medias")
cliente_rechazo = _ClienteFalso(_RespuestaFalsa(None, stop_reason="refusal"))
try:
    obtener_estilo("algo raro", client_anthropic=cliente_rechazo)
    check("rechazo del modelo -> ErrorDeEstilo", False)
except ErrorDeEstilo as exc:
    check("rechazo del modelo -> ErrorDeEstilo", "rechazó" in str(exc))

cliente_sin_tool_use = _ClienteFalso(_RespuestaFalsa(None, stop_reason="end_turn"))
try:
    obtener_estilo("algo raro", client_anthropic=cliente_sin_tool_use)
    check("sin bloque tool_use -> ErrorDeEstilo", False)
except ErrorDeEstilo as exc:
    check("sin bloque tool_use -> ErrorDeEstilo", "herramienta forzada" in str(exc))

print("\n5. aplicar_estilo_a_prompt() — determinista, sin IA")
base = "Genera la propuesta de distribución para este proyecto plurifamiliar en Madrid."
check("estilo None/vacío -> el mensaje no cambia ni un carácter", aplicar_estilo_a_prompt(None, base) == base)
check("estilo {} -> el mensaje no cambia ni un carácter", aplicar_estilo_a_prompt({}, base) == base)

con_estilo = aplicar_estilo_a_prompt(CATALOGO_ESTILOS["mediterraneo"], base)
check("el mensaje base sigue intacto al principio", con_estilo.startswith(base))
check("el bloque menciona el nombre del estilo", "Mediterráneo" in con_estilo)
check("el bloque incluye los materiales", "piedra local" in con_estilo)
check("el bloque incluye la solución de cubierta", "teja árabe" in con_estilo)
check("el bloque incluye el vuelo máximo", "0.6" in con_estilo)
check("el título del bloque es el esperado", "DIRECTIVA DE ESTILO ARQUITECTÓNICO" in con_estilo)

print("\n6. Integración: _build_user_message() de ai_generator.py aplica el estilo")
from analyzer.ai_generator import _build_user_message  # noqa: E402

params_sin_estilo = {
    "solar": {"superficie_m2": 500, "forma": "rectangular", "norte_grados": 0},
    "edificio": {"plantas": 4, "altura_libre_m": 2.8, "planta_baja_comercial": False},
    "mix_viviendas": {"dorm_1": 2, "dorm_2": 4, "dorm_3": 2, "superficie_minima_m2": 45},
    "normativa": {"ocupacion_maxima_pct": 70, "retranqueos_m": 3, "edificabilidad_maxima": None, "plantas_maximas": None},
    "proyecto": {"ciudad": "Madrid", "tipologia": "plurifamiliar", "zona_cte": "D"},
}
mensaje_sin_estilo = _build_user_message(params_sin_estilo)
check("sin estilo_dict -> sin bloque de estilo en el mensaje", "DIRECTIVA DE ESTILO" not in mensaje_sin_estilo)

params_con_estilo = dict(params_sin_estilo, estilo_dict=CATALOGO_ESTILOS["japandi"])
mensaje_con_estilo = _build_user_message(params_con_estilo)
check("con estilo_dict -> el bloque aparece en el mensaje", "DIRECTIVA DE ESTILO ARQUITECTÓNICO: Japandi" in mensaje_con_estilo)
check("el bloque va DESPUÉS del JSON de datos, no mezclado con él",
      mensaje_con_estilo.index("Datos del proyecto (JSON)") < mensaje_con_estilo.index("DIRECTIVA DE ESTILO"))

print("\n7. Integración: app.py resuelve el estilo por defecto sin llamar a la IA")
import app as app_module  # noqa: E402

params_defecto = app_module._parse_generar_params({
    "solar": {"superficie_m2": 500}, "mix_viviendas": {"dorm_1": 1},
})
check(
    "sin «estilo» en el body -> estilo_dict = racionalista (catálogo, sin red)",
    params_defecto["estilo_dict"] == CATALOGO_ESTILOS["racionalista"],
)
params_clave = app_module._parse_generar_params({
    "solar": {"superficie_m2": 500}, "mix_viviendas": {"dorm_1": 1}, "estilo": "nordico",
})
check("con «estilo»=«nordico» -> estilo_dict correcto", params_clave["estilo_dict"] == CATALOGO_ESTILOS["nordico"])

print("\n8. GET /api/estilos")
cliente_http = app_module.app.test_client()
r = cliente_http.get("/api/estilos")
datos = r.get_json()
check("200 OK", r.status_code == 200)
check("devuelve los 14 estilos", len(datos["estilos"]) == 14)
check("declara el estilo por defecto", datos["estilo_por_defecto"] == "racionalista")

print("\n" + "=" * 55)
if fallos:
    print("FALLOS (%d): %s" % (len(fallos), ", ".join(fallos)))
    sys.exit(1)
print("Todas las comprobaciones OK")
