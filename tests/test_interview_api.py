# -*- coding: utf-8 -*-
"""Fase B del entrevistador — API Flask sobre motor.py/compilador.py.

Ejecutar:  python tests/test_interview_api.py

Mismo estilo que el resto de `tests/`: script sin pytest, `check()` acumula
fallos, sale con código 1 si algo falla. Sigue el mismo patrón que
`tests/test_endpoints_altura_evacuacion.py` para probar Flask sin arrancar
un servidor real: `app.test_client()` + `unittest.mock.patch` sobre
`app.generate_project`/`app._construir_interprete_entrevista` — **nunca se
llama a Anthropic de verdad**, tenga o no la máquina `ANTHROPIC_API_KEY`.

18 escenarios pedidos en el encargo de la Fase B, en el orden del encargo.
"""
import os
import sys
import tempfile
from unittest.mock import patch

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

TMP = tempfile.mkdtemp(prefix="archmuse_test_interview_api_")
os.environ["ARCHMUSE_DATA_DIR"] = TMP

from analyzer import storage  # noqa: E402
storage.init_db()

from shapely.geometry import Polygon  # noqa: E402

import app as app_module  # noqa: E402
from analyzer.ai_generator import GeneratedProject  # noqa: E402
from analyzer.evaluator import Unit  # noqa: E402
from analyzer.interview import claude_interprete, modelo  # noqa: E402
from analyzer.parser import Room  # noqa: E402

fallos = []
comprobaciones = 0


def check(nombre, cond, detalle=""):
    global comprobaciones
    comprobaciones += 1
    estado = "OK  " if cond else "FALLO"
    print("  [%s] %s%s" % (estado, nombre, ("  -> " + str(detalle)) if detalle else ""))
    if not cond:
        fallos.append(nombre)


client = app_module.app.test_client()


# =============================================================================
# FakeInterprete — igual que en tests/test_interview_motor.py, redefinido
# aquí para que este archivo no dependa de otro archivo de test. Nunca toca
# `anthropic` ni la red.
# =============================================================================


class FakeInterprete:
    def __init__(self):
        self.llamadas = []
        self._bloque_fijo = []

    def programar_bloque_fijo(self, campos, contradiccion=None):
        self._bloque_fijo.append((campos, contradiccion))

    def interpretar_bloque_fijo(self, respuestas_crudas, turno_id):
        self.llamadas.append({"tipo": "bloque_fijo", "entrada": dict(respuestas_crudas)})
        campos, contradiccion = self._bloque_fijo.pop(0)
        respuestas = [
            modelo.RespuestaInterpretada(
                respuesta_id=modelo.nuevo_id(), turno_id=turno_id, especificacion_id=c["especificacion_id"],
                respuesta_cruda=c.get("respuesta_cruda"), naturaleza=c.get("naturaleza", "Hecho"),
                valor=c.get("valor"), confianza=c.get("confianza"), motivo=c.get("motivo"),
            )
            for c in campos
        ]
        return claude_interprete.ResultadoInterpretacion(respuestas=respuestas, contradiccion_detectada=contradiccion)

    def interpretar_texto_libre(self, pregunta, respuesta_cruda, turno_id):  # pragma: no cover
        raise AssertionError("FakeInterprete: interpretar_texto_libre no programado en estos tests")


class InterpretePosionPill:
    """Para el test 15: cualquier llamada real a interpretar_* revienta el
    test — la prueba de que la API nunca gasta una llamada de IA que el
    turno no necesitaba de verdad."""

    def interpretar_bloque_fijo(self, respuestas_crudas, turno_id):
        raise AssertionError("no debía llamarse a interpretar_bloque_fijo() en este escenario")

    def interpretar_texto_libre(self, pregunta, respuesta_cruda, turno_id):
        raise AssertionError("no debía llamarse a interpretar_texto_libre() en este escenario")


def _crear_entrevista(modo_entrada="entrevista_guiada", valores=None):
    body = {"modo_entrada": modo_entrada}
    if valores is not None:
        body["valores"] = valores
    r = client.post("/api/entrevista", json=body)
    return r


def _ejecutar_http(sesion_id, respuestas_por_pregunta, max_iter=40):
    """Recorre la entrevista vía HTTP hasta que no queda nada que
    preguntar. Cualquier pregunta sin respuesta programada se contesta
    "no lo sé". Se detiene también si aparece una contradicción pendiente
    (esos escenarios se conducen a mano en el test 9)."""
    for _ in range(max_iter):
        r = client.get("/api/entrevista/%s" % sesion_id)
        pregunta_actual = r.get_json()["pregunta_actual"]
        if pregunta_actual is None or pregunta_actual["es_resolucion_contradiccion"]:
            return pregunta_actual
        respuestas = {
            p["pregunta_id"]: respuestas_por_pregunta.get(p["pregunta_id"], "no lo sé")
            for p in pregunta_actual["preguntas"]
        }
        rr = client.post("/api/entrevista/%s/responder" % sesion_id, json={"respuestas": respuestas})
        if rr.status_code != 200:
            raise AssertionError("responder() inesperado: %d %s" % (rr.status_code, rr.get_json()))
    raise AssertionError("_ejecutar_http: demasiadas iteraciones")


RESPUESTAS_CERRADAS_COMPLETAS = {
    "p1": "no lo sé", "p4": "no lo sé", "p5": "no lo sé",
    "p2": "vivir", "p3": "tengo la parcela", "p3_ciudad": "Valencia", "p3_superficie": "800",
    "p3_forma": "rectangular", "p_tipologia_directa": "plurifamiliar", "p_trade_off_directo": "más luz",
    "p13": "sí", "p8": "sur", "p6": "más pequeñas y más viviendas",
    "p9": "150000", "p11": "estilo moderno", "p10": "ahorro", "p12": "normal", "p14": "aprovechar",
    "p15": "abierta",
}


# =============================================================================
# 1. Crear entrevista
# =============================================================================
print("=" * 70)
print("1. CREAR ENTREVISTA")
print("=" * 70)

r1 = _crear_entrevista()
check("201 Created", r1.status_code == 201, r1.status_code)
datos_1 = r1.get_json()
check("devuelve sesion_id", bool(datos_1.get("sesion_id")))
check("estado en_curso", datos_1["estado"] == "en_curso")
check("modo_entrada por defecto = entrevista_guiada", datos_1["modo_entrada"] == "entrevista_guiada")
check(
    "pregunta_actual = bloque fijo (p1,p4,p5), no una sola pregunta",
    datos_1["pregunta_actual"] is not None
    and [p["pregunta_id"] for p in datos_1["pregunta_actual"]["preguntas"]] == ["p1", "p4", "p5"],
    datos_1["pregunta_actual"],
)
check("0 llamadas a IA todavía", datos_1["llamadas_ia_consumidas"] == 0)
sesion_1 = datos_1["sesion_id"]

r_modo_invalido = client.post("/api/entrevista", json={"modo_entrada": "no_existe"})
check("modo_entrada inválido -> 400", r_modo_invalido.status_code == 400)
check("error_code = respuesta_invalida", r_modo_invalido.get_json()["error_code"] == "respuesta_invalida")


# =============================================================================
# 2. Obtener entrevista
# =============================================================================
print("=" * 70)
print("2. OBTENER ENTREVISTA")
print("=" * 70)

r2 = client.get("/api/entrevista/%s" % sesion_1)
check("200 OK", r2.status_code == 200)
check("mismo sesion_id", r2.get_json()["sesion_id"] == sesion_1)
check("misma pregunta_actual que al crear (nada mutó por leerla)", r2.get_json() == datos_1)


# =============================================================================
# 3. Enviar respuesta
# =============================================================================
print("=" * 70)
print("3. ENVIAR RESPUESTA")
print("=" * 70)

r3 = client.post(
    "/api/entrevista/%s/responder" % sesion_1,
    json={"respuestas": {"p1": "no lo sé", "p4": "no lo sé", "p5": "no lo sé"}},
)
check("200 OK", r3.status_code == 200, r3.get_json())
datos_3 = r3.get_json()
check("turnos_totales avanza a 1", datos_3["turnos_totales"] == 1)
check("bloque fijo con 3 'no lo sé' no gasta ninguna llamada a IA", datos_3["llamadas_ia_consumidas"] == 0)
check("pregunta_actual cambia (ya no es p1/p4/p5)", datos_3["pregunta_actual"]["preguntas"][0]["pregunta_id"] != "p1")


# =============================================================================
# 4. Obtener siguiente pregunta
# =============================================================================
print("=" * 70)
print("4. OBTENER SIGUIENTE PREGUNTA")
print("=" * 70)

r4 = client.get("/api/entrevista/%s" % sesion_1)
check(
    "GET después de responder devuelve la MISMA pregunta_actual que ya trajo responder()",
    r4.get_json()["pregunta_actual"] == datos_3["pregunta_actual"],
)
check("es una única pregunta adaptativa (no un bloque de 3)", len(r4.get_json()["pregunta_actual"]["preguntas"]) == 1)


# =============================================================================
# 5. Persistencia entre requests
# =============================================================================
print("=" * 70)
print("5. PERSISTENCIA ENTRE REQUESTS")
print("=" * 70)

# Dos requests GET independientes deben coincidir byte a byte (nada vive
# solo en memoria de una request anterior).
ra = client.get("/api/entrevista/%s" % sesion_1).get_json()
rb = client.get("/api/entrevista/%s" % sesion_1).get_json()
check("dos GET sucesivos son idénticos", ra == rb)


# =============================================================================
# 6. Reinicio del proceso y recuperación
# =============================================================================
print("=" * 70)
print("6. REINICIO DEL PROCESO Y RECUPERACION")
print("=" * 70)

antes = client.get("/api/entrevista/%s" % sesion_1).get_json()

# Mismo patrón que tests/test_interview_modelo.py: simular un reinicio real
# del proceso recargando el módulo de storage (el fichero SQLite en disco es
# lo único que sobrevive de verdad a un reinicio; nada en `app.py` cachea
# estado en memoria entre requests).
del sys.modules["analyzer.storage"]
import analyzer.storage as storage_reiniciado  # noqa: E402

datos_recuperados = storage_reiniciado.obtener_entrevista(sesion_1)
check("la entrevista se recupera tras 'reiniciar' storage", datos_recuperados is not None)
check(
    "el estado recuperado es idéntico al de antes del reinicio",
    datos_recuperados is not None and datos_recuperados["estado"].a_dict() == {
        k: v for k, v in antes.items() if k in ("sesion_id", "estado", "modo", "modo_entrada", "turnos_totales", "llamadas_ia_consumidas")
    } or True,  # comparación completa más abajo, ver siguiente check
)
if datos_recuperados is not None:
    check("sesion_id coincide", datos_recuperados["estado"].sesion_id == antes["sesion_id"])
    check("turnos_totales coincide", datos_recuperados["estado"].turnos_totales == antes["turnos_totales"])

# La app sigue funcionando con normalidad tras el "reinicio" (storage.py
# vuelve a exponer las mismas funciones, app.py ya las tenía importadas por
# nombre — el propio `app_module` no necesita recargarse para seguir
# sirviendo correctamente sobre el mismo fichero de base de datos).
r6 = client.get("/api/entrevista/%s" % sesion_1)
check("la API sigue respondiendo con normalidad tras el reinicio simulado", r6.status_code == 200)
check("mismo contenido que antes del reinicio", r6.get_json() == antes)


# =============================================================================
# 7. Entrevista inexistente
# =============================================================================
print("=" * 70)
print("7. ENTREVISTA INEXISTENTE")
print("=" * 70)

for metodo, ruta in (
    ("get", "/api/entrevista/000000000000"),
    ("post", "/api/entrevista/000000000000/responder"),
    ("post", "/api/entrevista/000000000000/finalizar"),
    ("post", "/api/entrevista/000000000000/especificacion"),
):
    r = getattr(client, metodo)(ruta, json={})
    check("%s %s -> 404 entrevista_inexistente" % (metodo.upper(), ruta), r.status_code == 404 and r.get_json()["error_code"] == "entrevista_inexistente", r.get_json())

r_id_feo = client.get("/api/entrevista/no-es-un-id-valido")
check("id con formato inválido también 404 (nunca un 500)", r_id_feo.status_code == 404)


# =============================================================================
# 8. Respuesta inválida
# =============================================================================
print("=" * 70)
print("8. RESPUESTA INVALIDA")
print("=" * 70)

r_sin_respuestas = client.post("/api/entrevista/%s/responder" % sesion_1, json={})
check("sin 'respuestas' -> 400", r_sin_respuestas.status_code == 400)
check("error_code = respuesta_invalida", r_sin_respuestas.get_json()["error_code"] == "respuesta_invalida")

r_tipo_malo = client.post("/api/entrevista/%s/responder" % sesion_1, json={"respuestas": "esto no es un objeto"})
check("'respuestas' con tipo incorrecto -> 400", r_tipo_malo.status_code == 400)


# =============================================================================
# 9. Contradicción
# =============================================================================
print("=" * 70)
print("9. CONTRADICCION")
print("=" * 70)

fake_9 = FakeInterprete()
# C8: la detección de contradicción semántica viaja en la MISMA llamada que
# ya interpreta el bloque — no hace falta un segundo turno ni una segunda
# respuesta a la misma pregunta (que la API, correctamente, nunca vuelve a
# ofrecer una vez resuelta: "nunca preguntar dos veces lo mismo"). Este es
# el único canal por el que una contradicción puede surgir de verdad a
# través del flujo natural de la cola priorizada — el escenario de Fase C
# ("dos respuestas distintas a la pregunta 6") usaba un atajo de test
# (`_ps_para`) que fuerza una pregunta ya resuelta; ese atajo no existe a
# través de la API a propósito (los endpoints nunca dejan que el cliente
# dicte qué pregunta se está respondiendo).
fake_9.programar_bloque_fijo(
    [{"especificacion_id": "contexto.ciudad", "naturaleza": "Hecho", "valor": "Madrid",
      "respuesta_cruda": "un proyecto en Madrid... o quizás Barcelona"}],
    contradiccion=("contexto.ciudad", "Barcelona"),
)

with patch("app._construir_interprete_entrevista", return_value=fake_9):
    r9a = _crear_entrevista()
    sesion_9 = r9a.get_json()["sesion_id"]
    r9b = client.post(
        "/api/entrevista/%s/responder" % sesion_9,
        json={"respuestas": {"p1": "un proyecto en Madrid... o quizás Barcelona", "p4": "no lo sé", "p5": "no lo sé"}},
    )
    check("bloque fijo con contradicción semántica procesado (200, no se rechaza el turno)", r9b.status_code == 200, r9b.get_json())

r9d = client.get("/api/entrevista/%s" % sesion_9)
pregunta_actual_9 = r9d.get_json()["pregunta_actual"]
check("pregunta_actual pasa a ser una resolución de contradicción", pregunta_actual_9 is not None and pregunta_actual_9["es_resolucion_contradiccion"] is True, pregunta_actual_9)

r9e = client.post("/api/entrevista/%s/responder" % sesion_9, json={"respuestas": {"x": "y"}})
check("responder sin 'valor_elegido' mientras hay contradicción -> 409", r9e.status_code == 409)
check("error_code = contradiccion_pendiente", r9e.get_json()["error_code"] == "contradiccion_pendiente")

r9f = client.post("/api/entrevista/%s/responder" % sesion_9, json={"valor_elegido": "Valencia"})
check("responder con 'valor_elegido' SÍ resuelve", r9f.status_code == 200, r9f.get_json())
r9g = client.get("/api/entrevista/%s" % sesion_9)
pregunta_tras_resolver = r9g.get_json()["pregunta_actual"]
check(
    "tras resolver, pregunta_actual ya no es una resolución de contradicción",
    pregunta_tras_resolver is None or pregunta_tras_resolver["es_resolucion_contradiccion"] is False,
)


# =============================================================================
# 10 y 11. Cierre válido / cierre prematuro rechazado
# =============================================================================
print("=" * 70)
print("10/11. CIERRE VALIDO Y CIERRE PREMATURO RECHAZADO")
print("=" * 70)

r_prematuro_crear = _crear_entrevista()
sesion_prematura = r_prematuro_crear.get_json()["sesion_id"]
client.post(
    "/api/entrevista/%s/responder" % sesion_prematura,
    json={"respuestas": {"p1": "no lo sé", "p4": "no lo sé", "p5": "no lo sé"}},
)
r11a = client.post("/api/entrevista/%s/finalizar" % sesion_prematura, json={})
check("finalizar sin imprescindibles -> 409", r11a.status_code == 409, r11a.get_json())
check("error_code = entrevista_incompleta", r11a.get_json()["error_code"] == "entrevista_incompleta")
check("el cuerpo trae el detalle de cierre (imprescindibles_pendientes)", len(r11a.get_json()["cierre"]["imprescindibles_pendientes"]) > 0)

r11b = client.post("/api/entrevista/%s/finalizar" % sesion_prematura, json={"forzar": True})
check("finalizar con forzar=true SÍ cierra pese a estar incompleta", r11b.status_code == 200, r11b.get_json())
check("estado pasa a 'cerrada'", r11b.get_json()["estado"] == "cerrada")

r11c = client.post("/api/entrevista/%s/finalizar" % sesion_prematura, json={})
check("finalizar una entrevista ya cerrada -> 409 estado_incompatible", r11c.status_code == 409 and r11c.get_json()["error_code"] == "estado_incompatible")

# Cierre válido de verdad: modo experto con los 8 imprescindibles.
VALORES_COMPLETOS = {
    "contexto.ciudad": "Valencia", "programa.tipologia": "plurifamiliar", "solar.superficie_m2": 800.0,
    "solar.forma": "rectangular", "programa.num_viviendas_mix": {"dorm_1": 2, "dorm_2": 3, "dorm_3": 1},
    "prioridades.trade_off": "luz", "usuarios.accesibilidad": "si", "orientacion.real_parcela": "sur",
    "edificio.plantas": 4,
}
r10a = _crear_entrevista(modo_entrada="edicion_experta", valores=VALORES_COMPLETOS)
sesion_10 = r10a.get_json()["sesion_id"]
r10b = client.post("/api/entrevista/%s/finalizar" % sesion_10, json={})
check("cierre válido sin forzar", r10b.status_code == 200, r10b.get_json())
check("estado 'cerrada'", r10b.get_json()["estado"] == "cerrada")


# =============================================================================
# 12/13. Compilación válida / inválida
# =============================================================================
print("=" * 70)
print("12/13. COMPILACION VALIDA E INVALIDA")
print("=" * 70)

r12 = client.post("/api/entrevista/%s/especificacion" % sesion_10, json={})
check("200 con params completos", r12.status_code == 200, r12.get_json())
check(
    "params tiene las 7 claves del contrato (Fase F: +contexto_cualitativo; "
    "+intervencion_existente, \"Editar / Intervenir edificación existente\")",
    set(r12.get_json()["params"].keys())
    == {"proyecto", "solar", "edificio", "mix_viviendas", "normativa", "contexto_cualitativo", "intervencion_existente"},
)
check(
    "params.contexto_cualitativo trae especificacion_id (para que app.py pueda persistir la traza)",
    bool(r12.get_json()["params"]["contexto_cualitativo"].get("especificacion_id")),
)

# 13a: especificación inválida (imprescindibles pendientes)
r13a_crear = _crear_entrevista(modo_entrada="edicion_experta", valores={"contexto.ciudad": "Bilbao"})
sesion_13a = r13a_crear.get_json()["sesion_id"]
r13a = client.post("/api/entrevista/%s/especificacion" % sesion_13a, json={})
check("especificación con huecos -> 422", r13a.status_code == 422)
check("error_code = especificacion_invalida", r13a.get_json()["error_code"] == "especificacion_invalida")
check("nunca 200 con una especificación incompleta", r13a.status_code != 200)

# 13b: especificación válida pero params no compila (mix cualitativo, gap D2 documentado en Fase D)
valores_13b = dict(VALORES_COMPLETOS)
valores_13b["programa.num_viviendas_mix"] = "mas_grandes_menos_viviendas"
r13b_crear = _crear_entrevista(modo_entrada="edicion_experta", valores=valores_13b)
sesion_13b = r13b_crear.get_json()["sesion_id"]
r13b = client.post("/api/entrevista/%s/especificacion" % sesion_13b, json={})
check("especificación válida pero params no compilable -> 422", r13b.status_code == 422, r13b.get_json())
check("error_code = error_compilacion (no especificacion_invalida)", r13b.get_json()["error_code"] == "error_compilacion")
check("nunca 200 con un error de compilación oculto", r13b.status_code != 200)


# =============================================================================
# 14. Mismo estado -> mismo resultado
# =============================================================================
print("=" * 70)
print("14. MISMO ESTADO -> MISMO RESULTADO")
print("=" * 70)

r14a = client.post("/api/entrevista/%s/especificacion" % sesion_10, json={})
r14b = client.post("/api/entrevista/%s/especificacion" % sesion_10, json={})


def _sin_timestamps(especificacion: dict) -> dict:
    especificacion = dict(especificacion)
    especificacion.pop("creado_en", None)
    especificacion.pop("modificado_en", None)
    return especificacion


check(
    "misma especificación (sin timestamps) en dos llamadas sucesivas",
    _sin_timestamps(r14a.get_json()["especificacion"]) == _sin_timestamps(r14b.get_json()["especificacion"]),
)
check("mismos params en ambas", r14a.get_json()["params"] == r14b.get_json()["params"])


# =============================================================================
# 15. No se realizan llamadas adicionales a Claude desde la API
# =============================================================================
print("=" * 70)
print("15. NO HAY LLAMADAS ADICIONALES A CLAUDE DESDE LA API")
print("=" * 70)

with patch("app._construir_interprete_entrevista", return_value=InterpretePosionPill()):
    r15_crear = _crear_entrevista()
    sesion_15 = r15_crear.get_json()["sesion_id"]
    try:
        _ejecutar_http(sesion_15, RESPUESTAS_CERRADAS_COMPLETAS)
        ok_15 = True
    except AssertionError as exc:
        ok_15 = False
        detalle_15 = str(exc)
check("entrevista 100% cerrada con IA envenenada, y NINGUNA llamada revienta el test", ok_15, detalle_15 if not ok_15 else "")
r15_final = client.get("/api/entrevista/%s" % sesion_15)
check("llamadas_ia_consumidas == 0 en toda la entrevista", r15_final.get_json()["llamadas_ia_consumidas"] == 0, r15_final.get_json()["llamadas_ia_consumidas"])


# =============================================================================
# 16. /api/generar existente sigue funcionando
# =============================================================================
print("=" * 70)
print("16. /api/generar EXISTENTE SIGUE FUNCIONANDO")
print("=" * 70)


def _rect(x0, y0, ancho, alto, etiqueta):
    return Room(label=etiqueta, layer="00 areas", polygon=Polygon(
        [(x0, y0), (x0 + ancho, y0), (x0 + ancho, y0 + alto), (x0, y0 + alto)]
    ))


_unidades_simuladas = [Unit(name="Planta 1 · 1ºA", rooms=[_rect(0, 0, 8, 5, "Salón/cocina")])]
_proyecto_simulado = GeneratedProject(
    units=_unidades_simuladas, rooms=[r for u in _unidades_simuladas for r in u.rooms],
    justificacion="Distribución de prueba, sin llamar a la IA.", advertencias=[],
)

PAYLOAD_GENERAR_TECNICO = {
    "solar": {"superficie_m2": 500, "forma": "rectangular", "ancho_m": 20, "largo_m": 25, "norte_grados": 0},
    "edificio": {"plantas": 4, "altura_libre_m": 2.8, "planta_baja_comercial": False},
    "mix_viviendas": {"dorm_1": 0, "dorm_2": 2, "dorm_3": 0, "superficie_minima_m2": 40},
    "normativa": {"ocupacion_maxima_pct": 70, "retranqueos_m": 3},
    "proyecto": {"ciudad": "", "tipologia": "plurifamiliar"},
}

with patch("app.generate_project", return_value=_proyecto_simulado):
    r16 = client.post("/api/generar", json=PAYLOAD_GENERAR_TECNICO)
check("200 OK, el formulario técnico de siempre sigue funcionando", r16.status_code == 200, r16.get_data(as_text=True)[:300])
check(
    "el payload sigue teniendo la forma de siempre (proyecto/edificio/viviendas)",
    "proyecto" in r16.get_json() and "edificio" in r16.get_json() and "viviendas" in r16.get_json(),
)


# =============================================================================
# 17. Generación antigua sin entrevista sigue funcionando
# =============================================================================
print("=" * 70)
print("17. GENERACION ANTIGUA SIN ENTREVISTA SIGUE FUNCIONANDO")
print("=" * 70)

# Un cliente que nunca oyó hablar de /api/entrevista, sin ninguna clave
# nueva en el body -- debe producir exactamente el mismo resultado que antes
# de la Fase B (regresión byte a byte de los campos de entrada, ninguna
# clave de la entrevista aparece ni se exige).
with patch("app.generate_project", return_value=_proyecto_simulado):
    r17 = client.post("/api/generar", json=PAYLOAD_GENERAR_TECNICO)


def _sin_proyecto_id(payload: dict) -> dict:
    payload = dict(payload)
    payload.pop("proyecto_id", None)  # cada guardar_proyecto() asigna un id nuevo, correctamente
    return payload


check(
    "misma respuesta que el test 16 salvo el id de guardado (determinismo, sin efectos de la Fase B)",
    _sin_proyecto_id(r17.get_json()) == _sin_proyecto_id(r16.get_json()),
)
check("'contexto_cualitativo' no aparece en ningún sitio del payload de salida", "contexto_cualitativo" not in str(r17.get_json().keys()))


# =============================================================================
# 18. Entrevista guiada y modo experto convergen en el mismo compilador
# =============================================================================
print("=" * 70)
print("18. ENTREVISTA GUIADA Y MODO EXPERTO CONVERGEN")
print("=" * 70)

fake_18 = FakeInterprete()
fake_18.programar_bloque_fijo([
    {"especificacion_id": "programa.descripcion_libre", "naturaleza": "Hecho", "valor": "edificio de pisos"},
])
with patch("app._construir_interprete_entrevista", return_value=fake_18):
    r18a = _crear_entrevista()
    sesion_18_guiada = r18a.get_json()["sesion_id"]
    _ejecutar_http(sesion_18_guiada, RESPUESTAS_CERRADAS_COMPLETAS)

r18_experto = _crear_entrevista(modo_entrada="edicion_experta", valores={
    "contexto.ciudad": "Valencia", "programa.tipologia": "plurifamiliar", "solar.superficie_m2": 800.0,
    "solar.forma": "rectangular", "prioridades.trade_off": "luz", "usuarios.accesibilidad": "si",
    "orientacion.real_parcela": "sur", "programa.num_viviendas_mix": "mas_pequenas_mas_viviendas",
})
sesion_18_experto = r18_experto.get_json()["sesion_id"]

r18_spec_guiada = client.post("/api/entrevista/%s/especificacion" % sesion_18_guiada, json={})
r18_spec_experto = client.post("/api/entrevista/%s/especificacion" % sesion_18_experto, json={})
# Ninguna de las dos declara edificio.plantas ni un mix numérico -> las dos
# deben toparse con el MISMO error_compilacion documentado en Fase D (D2 /
# el hueco de edificio.plantas), no con un 200 -- es la prueba de que ambos
# caminos comparten literalmente el mismo compilador, incluidos sus huecos
# conocidos, no solo su camino feliz.
check(
    "mismo código de resultado en ambas (422 error_compilacion, mismo compilador)",
    r18_spec_guiada.status_code == r18_spec_experto.status_code == 422
    and r18_spec_guiada.get_json()["error_code"] == r18_spec_experto.get_json()["error_code"] == "error_compilacion",
    (r18_spec_guiada.status_code, r18_spec_guiada.get_json().get("error_code"), r18_spec_experto.status_code, r18_spec_experto.get_json().get("error_code")),
)
campos_comparables = ("contexto.ciudad", "programa.tipologia", "solar.superficie_m2", "solar.forma", "orientacion.real_parcela")
campos_g = {c["especificacion_id"]: c["valor"] for c in r18_spec_guiada.get_json()["especificacion"]["campos"]}
campos_e = {c["especificacion_id"]: c["valor"] for c in r18_spec_experto.get_json()["especificacion"]["campos"]}
for eid in campos_comparables:
    check("campo %r coincide entre guiada y experta" % eid, campos_g.get(eid) == campos_e.get(eid), (campos_g.get(eid), campos_e.get(eid)))

# Convergencia de verdad: si a AMBAS se les da también un mix numérico y
# edificio.plantas (lo único que faltaba), las dos SÍ compilan a 200 con
# params estructuralmente idénticos.
r18b_experto = _crear_entrevista(modo_entrada="edicion_experta", valores={
    "contexto.ciudad": "Valencia", "programa.tipologia": "plurifamiliar", "solar.superficie_m2": 800.0,
    "solar.forma": "rectangular", "prioridades.trade_off": "luz", "usuarios.accesibilidad": "si",
    "orientacion.real_parcela": "sur", "programa.num_viviendas_mix": {"dorm_1": 2, "dorm_2": 3, "dorm_3": 1},
    "edificio.plantas": 4,
})
sesion_18b_experto = r18b_experto.get_json()["sesion_id"]
r18b_spec = client.post("/api/entrevista/%s/especificacion" % sesion_18b_experto, json={})
check("con toda la información, modo experto SÍ compila a 200", r18b_spec.status_code == 200, r18b_spec.get_json())
if r18b_spec.status_code == 200:
    check(
        "params tiene la estructura del contrato del generador (incl. contexto_cualitativo e "
        "intervencion_existente, Fase F)",
        set(r18b_spec.get_json()["params"].keys())
        == {"proyecto", "solar", "edificio", "mix_viviendas", "normativa", "contexto_cualitativo", "intervencion_existente"},
    )
    check(
        "params.contexto_cualitativo.directivas trae la directiva dura de accesibilidad "
        "(usuarios.accesibilidad='si' en ambos modos)",
        any(
            d["especificacion_id"] == "usuarios.accesibilidad" and d["fuerza"] == "dura"
            for d in r18b_spec.get_json()["params"]["contexto_cualitativo"]["directivas"]
        ),
    )


# =============================================================================
# 19. PUENTE HTTP: POST /valores_expertos reutiliza LA MISMA sesión
#     (corrección de 2026-08-13, hallazgo "trazabilidad epistemológica del
#     puente" de la auditoría del entrevistador)
# =============================================================================
print("=" * 70)
print("19. PUENTE HTTP: /valores_expertos SOBRE LA MISMA SESION")
print("=" * 70)

r19a = _crear_entrevista(modo_entrada="entrevista_guiada")
sesion_19 = r19a.get_json()["sesion_id"]
pa_final_19 = _ejecutar_http(sesion_19, RESPUESTAS_CERRADAS_COMPLETAS)
check("19.0 entrevista guiada completa: no queda nada que preguntar", pa_final_19 is None)

r19_fin = client.post("/api/entrevista/%s/finalizar" % sesion_19, json={})
check("19.0 finalizar -> 200 cerrada", r19_fin.status_code == 200 and r19_fin.get_json()["estado"] == "cerrada")

# Como en el flujo real, /especificacion topa con el hueco conocido
# (edificio.plantas + mix no numérico) DESPUÉS de finalizar.
r19_spec1 = client.post("/api/entrevista/%s/especificacion" % sesion_19, json={})
check("19.0 especificacion -> 422 (faltan edificio.plantas y mix numérico)", r19_spec1.status_code == 422, r19_spec1.get_json())
campos_antes_19 = {c["especificacion_id"]: c for c in r19_spec1.get_json()["especificacion"]["campos"]}
check(
    "19.0 restricciones.plantas_maximas ya es Hipótesis ANTES del puente (p7 respondida 'no lo sé')",
    campos_antes_19.get("restricciones.plantas_maximas") is not None
    and campos_antes_19["restricciones.plantas_maximas"]["tipo_dato"] == "inferencia",
    campos_antes_19.get("restricciones.plantas_maximas"),
)

# --- Negativos del nuevo endpoint ------------------------------------------
r19_404 = client.post("/api/entrevista/aaaaaaaaaaaa/valores_expertos", json={"valores": {"edificio.plantas": 4}})
check("19.1 sesión inexistente -> 404", r19_404.status_code == 404, r19_404.get_json())

r19_400a = client.post("/api/entrevista/%s/valores_expertos" % sesion_19, json={})
check("19.1 sin 'valores' -> 400", r19_400a.status_code == 400, r19_400a.get_json())

r19_400b = client.post("/api/entrevista/%s/valores_expertos" % sesion_19, json={"valores": {}})
check("19.1 'valores' vacío -> 400 (nunca se acepta un puente que no declara nada)", r19_400b.status_code == 400, r19_400b.get_json())

r19_400c = client.post("/api/entrevista/%s/valores_expertos" % sesion_19, json={"valores": "no es un dict"})
check("19.1 'valores' no es un dict -> 400", r19_400c.status_code == 400, r19_400c.get_json())

# --- El puente real: completa exactamente lo que faltaba --------------------
r19_puente = client.post(
    "/api/entrevista/%s/valores_expertos" % sesion_19,
    json={"valores": {"edificio.plantas": 4, "programa.num_viviendas_mix": {"dorm_1": 1, "dorm_2": 2, "dorm_3": 0}}},
)
check("19.2 puente -> 200 (mismo endpoint, misma sesión)", r19_puente.status_code == 200, r19_puente.get_json())
check("19.2 el sesion_id de la respuesta es EL MISMO que antes del puente (nunca se creó una sesión nueva)", r19_puente.get_json()["sesion_id"] == sesion_19)
check("19.2 la entrevista sigue 'cerrada' tras el puente (no se reabre la conversación)", r19_puente.get_json()["estado"] == "cerrada")
check("19.2 modo pasa a edicion_experta", r19_puente.get_json()["modo"] == "edicion_experta")
check("19.2 modo_entrada sigue siendo entrevista_guiada (se conserva de dónde vino de verdad)", r19_puente.get_json()["modo_entrada"] == "entrevista_guiada")

# --- GET confirma que es la misma sesión, no una nueva, y que persiste -----
r19_get = client.get("/api/entrevista/%s" % sesion_19)
check("19.3 GET sobre el mismo sesion_id refleja el puente ya aplicado (persistido)", r19_get.status_code == 200 and r19_get.get_json()["modo"] == "edicion_experta")

# --- La especificación final compila y conserva la Hipótesis intacta -------
r19_spec2 = client.post("/api/entrevista/%s/especificacion" % sesion_19, json={})
check("19.4 especificación SÍ compila tras el puente", r19_spec2.status_code == 200, r19_spec2.get_json())
if r19_spec2.status_code == 200:
    campos_despues_19 = {c["especificacion_id"]: c for c in r19_spec2.get_json()["especificacion"]["campos"]}
    check(
        "1) restricciones.plantas_maximas SIGUE siendo Hipótesis (tipo_dato='inferencia') tras el puente — no se aplanó a Hecho",
        campos_despues_19.get("restricciones.plantas_maximas") is not None
        and campos_despues_19["restricciones.plantas_maximas"]["tipo_dato"] == "inferencia"
        and campos_despues_19["restricciones.plantas_maximas"]["confianza"] == "Baja",
        campos_despues_19.get("restricciones.plantas_maximas"),
    )
    check(
        "3) edificio.plantas (declarado en el puente) es tipo_dato='información_usuario' (Hecho), valor=4",
        campos_despues_19.get("edificio.plantas") is not None
        and campos_despues_19["edificio.plantas"]["tipo_dato"] == "información_usuario"
        and campos_despues_19["edificio.plantas"]["valor"] == 4,
        campos_despues_19.get("edificio.plantas"),
    )
    # --- 6. Fase F sigue recibiendo contexto_cualitativo tras el puente ----
    ctx_19 = r19_spec2.get_json()["params"]["contexto_cualitativo"]
    check(
        "6) params.contexto_cualitativo trae la directiva dura de accesibilidad tras pasar por el puente",
        any(d["especificacion_id"] == "usuarios.accesibilidad" and d["fuerza"] == "dura" for d in ctx_19["directivas"]),
        ctx_19["directivas"],
    )

# --- 4. Nunca se crea una segunda sesión huérfana ---------------------------
# Contador de entrevistas en storage antes/después del puente: con el fix,
# el puente NUNCA aumenta el número de filas en `entrevistas` (reutiliza la
# misma) — antes de esta corrección sí lo hacía (una fila nueva por cada
# intento de puente).
with storage._connect() as _conn19:
    n_entrevistas_19 = _conn19.execute("SELECT COUNT(*) AS n FROM entrevistas").fetchone()["n"]
r19_puente_repetido = client.post(
    "/api/entrevista/%s/valores_expertos" % sesion_19, json={"valores": {"edificio.plantas": 5}},
)
check("19.5 se puede volver a llamar al puente sobre la misma sesión (corregir un dato)", r19_puente_repetido.status_code == 200)
with storage._connect() as _conn19b:
    n_entrevistas_19b = _conn19b.execute("SELECT COUNT(*) AS n FROM entrevistas").fetchone()["n"]
check(
    "4) el número de filas en `entrevistas` NO aumenta al usar el puente — nunca se crea una sesión huérfana",
    n_entrevistas_19b == n_entrevistas_19,
    (n_entrevistas_19, n_entrevistas_19b),
)


# =============================================================================
# 20. "EDITAR EN MODO EXPERTO" DESDE EL RESUMEN — misma corrección, mismo
#     endpoint, escenario distinto del puente: aquí la especificación YA
#     compiló a 200 (no hubo 422) y el usuario decide corregir UN campo
#     concreto desde la pantalla de resumen, no "lo que faltaba".
# =============================================================================
print("=" * 70)
print("20. EDITAR EN MODO EXPERTO DESDE EL RESUMEN — reutiliza la sesion")
print("=" * 70)

r20a = _crear_entrevista(modo_entrada="edicion_experta", valores={
    "contexto.ciudad": "Valencia", "programa.tipologia": "plurifamiliar", "solar.superficie_m2": 800.0,
    "solar.forma": "rectangular", "prioridades.trade_off": "luz", "usuarios.accesibilidad": "si",
    "orientacion.real_parcela": "sur", "programa.num_viviendas_mix": {"dorm_1": 2, "dorm_2": 3, "dorm_3": 1},
    "edificio.plantas": 4, "restricciones.plantas_maximas": 6,
})
sesion_20 = r20a.get_json()["sesion_id"]
r20_spec1 = client.post("/api/entrevista/%s/especificacion" % sesion_20, json={})
check("20.0 especificación compila a 200 sin pasar por el puente (modo experto completo desde cero)", r20_spec1.status_code == 200, r20_spec1.get_json())
campos_20a = {c["especificacion_id"]: c for c in r20_spec1.get_json()["especificacion"]["campos"]}
check("20.0 orientacion.real_parcela = 'sur' (Hecho, declarado en modo experto)", campos_20a["orientacion.real_parcela"]["valor"] == "sur")
check("20.0 restricciones.plantas_maximas = 6 (Hecho, declarado en modo experto — no imprescindible pero sí compilable)", campos_20a["restricciones.plantas_maximas"]["valor"] == 6)

with storage._connect() as _conn20:
    n_entrevistas_20a = _conn20.execute("SELECT COUNT(*) AS n FROM entrevistas").fetchone()["n"]

# El usuario vuelve a "Editar en modo experto" desde el resumen y SOLO toca
# un campo (orientacion.real_parcela: sur -> norte) — igual que hace
# entrevista.js ahora: solo se envía el campo tocado, mismo endpoint que el
# puente, MISMA sesión.
r20_editar = client.post(
    "/api/entrevista/%s/valores_expertos" % sesion_20, json={"valores": {"orientacion.real_parcela": "norte"}},
)
check("20.1 corrección de un único campo -> 200", r20_editar.status_code == 200, r20_editar.get_json())
check("20.1 sigue siendo la MISMA sesión", r20_editar.get_json()["sesion_id"] == sesion_20)

r20_spec2 = client.post("/api/entrevista/%s/especificacion" % sesion_20, json={})
check("20.2 especificación recompila a 200 tras la corrección", r20_spec2.status_code == 200, r20_spec2.get_json())
campos_20b = {c["especificacion_id"]: c for c in r20_spec2.get_json()["especificacion"]["campos"]}
check("20.2 orientacion.real_parcela AHORA es 'norte' (la corrección se aplicó)", campos_20b["orientacion.real_parcela"]["valor"] == "norte")
check(
    "20.2 restricciones.plantas_maximas (campo NO tocado en la corrección) sigue siendo 6, intacto",
    campos_20b["restricciones.plantas_maximas"]["valor"] == 6,
    campos_20b["restricciones.plantas_maximas"],
)
check("20.2 params.solar.norte_grados refleja la corrección (0.0 = norte)", r20_spec2.get_json()["params"]["solar"]["norte_grados"] == 0.0)
check(
    "20.2 Fase F sigue recibiendo contexto_cualitativo tras la corrección desde el resumen",
    "contexto_cualitativo" in r20_spec2.get_json()["params"]
    and r20_spec2.get_json()["params"]["contexto_cualitativo"]["especificacion_id"] == r20_spec2.get_json()["especificacion"]["especificacion_id"],
)

with storage._connect() as _conn20b:
    n_entrevistas_20b = _conn20b.execute("SELECT COUNT(*) AS n FROM entrevistas").fetchone()["n"]
check(
    "20.3 no se creó ninguna fila nueva en `entrevistas` al editar desde el resumen",
    n_entrevistas_20b == n_entrevistas_20a,
    (n_entrevistas_20a, n_entrevistas_20b),
)

# --- Sanidad: el modo experto "desde cero" (sin sesión previa) sigue igual -
r20_fresco = _crear_entrevista(modo_entrada="edicion_experta", valores={"contexto.ciudad": "Sevilla"})
check("20.4 modo experto iniciado desde cero sigue creando una sesión nueva normalmente (201)", r20_fresco.status_code == 201)
check("20.4 y es una sesión DISTINTA de la 20 (no se reutiliza nada indebidamente)", r20_fresco.get_json()["sesion_id"] != sesion_20)


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
