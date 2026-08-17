# -*- coding: utf-8 -*-
"""Entrevista Guiada — navegación "Anterior", omisión de preguntas geográficas ya resueltas por el Paso 0
("Mapa/Parcela Primero") y barra de progreso dinámica. Tres encargos distintos, 2026-08-15, agrupados en un
solo archivo porque los tres tocan la misma superficie (`analyzer/interview/motor.py` + `app.py`, sección
"ENTREVISTADOR").

Ejecutar:  python tests/test_interview_deshacer_y_progreso.py

Mismo estilo que el resto de `tests/`: script sin pytest, `check()` acumula fallos, sale con código 1 si
algo falla. Nunca llama a Claude de verdad — `FakeInterprete` (copiado de `test_interview_motor.py`/
`test_interview_api.py`, redefinido aquí para no depender de otro archivo de test) programa lo que debe
devolver cada llamada.
"""
import os
import sys
import tempfile
from unittest.mock import patch

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

TMP = tempfile.mkdtemp(prefix="archmuse_test_interview_deshacer_")
os.environ["ARCHMUSE_DATA_DIR"] = TMP

from analyzer import storage  # noqa: E402
storage.init_db()

import app as app_module  # noqa: E402
from analyzer.interview import claude_interprete, modelo  # noqa: E402
from analyzer.interview import motor  # noqa: E402
from analyzer.interview import preguntas as preguntas_mod  # noqa: E402

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


class FakeInterprete:
    def __init__(self):
        self._bloque_fijo = []

    def programar_bloque_fijo(self, campos, contradiccion=None):
        self._bloque_fijo.append((campos, contradiccion))

    def interpretar_bloque_fijo(self, respuestas_crudas, turno_id):
        campos, contradiccion = self._bloque_fijo.pop(0)
        respuestas = [
            modelo.RespuestaInterpretada(
                respuesta_id=modelo.nuevo_id(), turno_id=turno_id, especificacion_id=c["especificacion_id"],
                respuesta_cruda="...", naturaleza=c["naturaleza"], valor=c.get("valor"),
                confianza=c.get("confianza"), motivo=c.get("motivo"),
            )
            for c in campos
        ]
        return claude_interprete.ResultadoInterpretacion(respuestas=respuestas, contradiccion_detectada=contradiccion)

    def interpretar_texto_libre(self, pregunta, respuesta_cruda, turno_id):
        raise AssertionError("no programado para este test")


def _ps_para(*pregunta_ids):
    preguntas = tuple(preguntas_mod.PREGUNTAS_POR_ID[pid] for pid in pregunta_ids)
    return motor.PreguntaSiguiente(turno_id=modelo.nuevo_id(), preguntas=preguntas, motivo="test_directo")


def _bloque_fijo_estandar(fake, mix="mas_pequenas_mas_viviendas"):
    campos = [
        {"especificacion_id": "programa.descripcion_libre", "naturaleza": "Hecho", "valor": "descripción libre"},
        {"especificacion_id": "programa.sensacion_buscada", "naturaleza": "Inferencia", "valor": "luminosa", "confianza": "Media"},
        {"especificacion_id": "prioridades.no_negociables", "naturaleza": "Hecho", "valor": "tres dormitorios"},
        {"especificacion_id": "prioridades.lo_de_menos_importa", "naturaleza": "Hecho", "valor": "el garaje"},
        {"especificacion_id": "prioridades.trade_off", "naturaleza": "Inferencia", "valor": "luz", "confianza": "Media"},
        {"especificacion_id": "programa.num_viviendas_mix", "naturaleza": "Inferencia", "valor": mix, "confianza": "Media"},
    ]
    fake.programar_bloque_fijo(campos)


RESPUESTAS_COMPLETAS = {
    "p1": "Quiero una casa en Sevilla para vivir yo, con mucha luz natural.",
    "p4": "Tres dormitorios y un salón grande.",
    "p5": "El garaje no me importa.",
    "p2": "vivir",
    "p3": "tengo la parcela",
    "p3_ciudad": "Sevilla",
    "p3_superficie": "800",
    "p3_forma": "rectangular",
    "p6": "más pequeñas y más",
    "p7": "3 plantas",
    "p8": "sur",
    "p9": "180000",
    "p10": "ahorro energético",
    "p11": "Casa moderna",
    "p12": "normal",
    "p13": "no",
    "p14": "espacio exterior propio",
    "p15": "abierta",
    "p_tipologia_directa": "unifamiliar",
}


#: Respuestas del bloque fijo con texto real y sustancioso -- "..." se normaliza a cadena vacía
#: (`motor._normalizar`) y `_es_desconocido` lo trataría como un "no sé" silencioso, saltándose por
#: completo la llamada al interprete que estos tests necesitan ejercitar de verdad.
RESPUESTAS_BLOQUE_FIJO = {"p1": RESPUESTAS_COMPLETAS["p1"], "p4": RESPUESTAS_COMPLETAS["p4"], "p5": RESPUESTAS_COMPLETAS["p5"]}


def _ejecutar(estado, respuestas_por_pregunta, interprete=None, max_iter=40):
    """Igual que en `test_interview_motor.py`: recorre `siguiente_pregunta()`/`responder()` hasta que no
    queda nada que preguntar o aparece una contradicción, devolviendo la lista de `pregunta_id` REALMENTE
    preguntados (para poder comprobar que uno concreto NUNCA se llegó a preguntar)."""
    preguntados = []
    for _ in range(max_iter):
        ps = motor.siguiente_pregunta(estado)
        if ps is None or ps.es_resolucion_contradiccion:
            break
        for p in ps.preguntas:
            preguntados.append(p.pregunta_id)
        respuestas_crudas = {p.pregunta_id: respuestas_por_pregunta.get(p.pregunta_id, "no lo sé") for p in ps.preguntas}
        motor.responder(estado, ps, respuestas_crudas, interprete=interprete)
    return preguntados


# =============================================================================
print("=" * 70)
print("1. sembrar_hecho_externo — 'Omite las preguntas geográficas redundantes'")
print("=" * 70)

estado1 = motor.iniciar_entrevista()
motor.sembrar_hecho_externo(estado1, "contexto.ciudad", "Madrid", "detectado en el Paso 0")
check("el campo queda resuelto", motor.campo_tiene_respuesta(estado1, "contexto.ciudad"))
check("valor sembrado correcto", motor._valor_actual(estado1, "contexto.ciudad") == "Madrid")
check("NO crea ningún Turno (no hubo pregunta real)", estado1.historial_turnos == [])
check("NO toca turnos_totales", estado1.turnos_totales == 0)
check("el turno_id queda marcado como sembrado externo, no un turno real",
      all(r.turno_id == motor.TURNO_ID_SEMBRADO_EXTERNO for r in estado1.respuestas_interpretadas))

motor.sembrar_hecho_externo(estado1, "contexto.ciudad", "Barcelona", "un segundo intento no debería pisar el primero")
check("sembrar dos veces el mismo campo no sobrescribe en silencio (nunca se pisa)",
      motor._valor_actual(estado1, "contexto.ciudad") == "Madrid")
check("y no duplica la entrada",
      len([r for r in estado1.respuestas_interpretadas if r.especificacion_id == "contexto.ciudad"]) == 1)

estado1b = motor.iniciar_entrevista()
motor.sembrar_hecho_externo(estado1b, "contexto.ciudad", "Sevilla", "Paso 0")
motor.sembrar_hecho_externo(estado1b, "solar.superficie_m2", 800.0, "Paso 0")
fake1b = FakeInterprete()
_bloque_fijo_estandar(fake1b)
preguntados1b = _ejecutar(estado1b, RESPUESTAS_COMPLETAS, interprete=fake1b)
check("p3_ciudad NUNCA se pregunta (ya resuelto por el Paso 0)", "p3_ciudad" not in preguntados1b, preguntados1b)
check("p3_superficie NUNCA se pregunta (ya resuelto por el Paso 0)", "p3_superficie" not in preguntados1b, preguntados1b)
check("p3 (gateway) SÍ se sigue preguntando -- no es 'geográfica redundante', es el propio gateway",
      "p3" in preguntados1b, preguntados1b)
check("p3_forma SÍ se sigue preguntando -- Catastro da un polígono, no una etiqueta rectangular/irregular",
      "p3_forma" in preguntados1b, preguntados1b)
cierre1b = motor.evaluar_cierre(estado1b)
check("la entrevista sigue pudiendo cerrarse con normalidad", cierre1b.puede_cerrar, cierre1b.motivo)

# "Si el usuario eligió 'Laboratorio' (sin parcela real), mantén las preguntas geográficas activas": no
# sembrar nada es exactamente ese camino -- se comprueba con el resto de tests de este archivo (sección 3,
# que no siembra nada y sí pregunta p3_ciudad/p3_superficie con normalidad).


# =============================================================================
print()
print("=" * 70)
print("2. puede_deshacer / deshacer_ultimo_turno — botón 'Anterior'")
print("=" * 70)

estado2 = motor.iniciar_entrevista()
check("primer paso: nada que deshacer todavía", not motor.puede_deshacer(estado2))
try:
    motor.deshacer_ultimo_turno(estado2)
    check("deshacer sin nada que deshacer lanza ValueError", False)
except ValueError:
    check("deshacer sin nada que deshacer lanza ValueError", True)

fake2 = FakeInterprete()
_bloque_fijo_estandar(fake2)
ps2 = motor.siguiente_pregunta(estado2)
motor.responder(estado2, ps2, RESPUESTAS_BLOQUE_FIJO, interprete=fake2)
check("tras el bloque fijo: turnos_totales == 1", estado2.turnos_totales == 1)
check("tras el bloque fijo: puede_deshacer == True", motor.puede_deshacer(estado2))
check("no_negociables recoge 'tres dormitorios'", "tres dormitorios" in estado2.no_negociables)
llamadas_antes = estado2.llamadas_ia_consumidas
check("consumió 1 llamada a IA", llamadas_antes == 1)

motor.deshacer_ultimo_turno(estado2)
check("deshacer el bloque fijo: turnos_totales vuelve a 0", estado2.turnos_totales == 0)
check("deshacer el bloque fijo: historial_turnos queda vacío", estado2.historial_turnos == [])
check("deshacer el bloque fijo: ninguna respuesta de ese turno sobrevive", estado2.respuestas_interpretadas == [])
check("deshacer el bloque fijo: no_negociables se recalcula a vacío (era derivado de ese turno)",
      estado2.no_negociables == [])
check("llamadas_ia_consumidas NO se devuelve (limitación conocida, documentada)",
      estado2.llamadas_ia_consumidas == llamadas_antes)
check("puede_deshacer vuelve a False: estamos otra vez en el primer paso", not motor.puede_deshacer(estado2))
siguiente2 = motor.siguiente_pregunta(estado2)
check("siguiente_pregunta() vuelve a proponer el bloque fijo inicial",
      siguiente2 is not None and siguiente2.motivo == "bloque_fijo_inicial")

# --- Un turno normal (una sola pregunta cerrada) --------------------------------------------------------
_bloque_fijo_estandar(fake2)  # el primer programado ya se consumió (pop) al deshacer y volver a contestar
motor.responder(estado2, motor.siguiente_pregunta(estado2), RESPUESTAS_BLOQUE_FIJO, interprete=fake2)
motor.responder(estado2, _ps_para("p2"), {"p2": "vivir"})
check("p2 respondida: usuarios.destino resuelto", motor.campo_tiene_respuesta(estado2, "usuarios.destino"))
turnos_antes_p2 = estado2.turnos_totales
motor.deshacer_ultimo_turno(estado2)
check("deshacer p2: usuarios.destino vuelve a estar sin resolver", not motor.campo_tiene_respuesta(estado2, "usuarios.destino"))
check("deshacer p2: turnos_totales decrementado en 1", estado2.turnos_totales == turnos_antes_p2 - 1)
check("p2 vuelve a ser una candidata elegible (aunque no sea forzosamente la de mayor prioridad ahora mismo --"
      " usuarios.destino no es uno de los 8 imprescindibles, así que otras preguntas SÍ pueden colarse por"
      " delante; lo que importa es que ya no está descartada como 'ya respondida')",
      any(p.pregunta_id == "p2" for p in motor._candidatas_adaptativas(estado2)))
siguiente2b = motor.siguiente_pregunta(estado2)
check("siguiente_pregunta() sigue devolviendo algo válido (la entrevista no se rompe tras deshacer)",
      siguiente2b is not None and not siguiente2b.es_resolucion_contradiccion)


# =============================================================================
print()
print("=" * 70)
print("2b. deshacer a través de una contradicción (reabrir resolución / borrar conflicto fantasma)")
print("=" * 70)

estado2c = motor.iniciar_entrevista()
fake2c = FakeInterprete()
_bloque_fijo_estandar(fake2c, mix="mas_pequenas_mas_viviendas")
motor.responder(estado2c, motor.siguiente_pregunta(estado2c), RESPUESTAS_BLOQUE_FIJO, interprete=fake2c)
motor.responder(estado2c, _ps_para("p6"), {"p6": "viviendas muy grandes"})  # contradice el bloque fijo

contradiccion2c = motor._contradiccion_pendiente(estado2c, "programa.num_viviendas_mix")
check("se detectó la contradicción", contradiccion2c is not None)
check("puede_deshacer sigue siendo True con una contradicción pendiente", motor.puede_deshacer(estado2c))

motor.responder_contradiccion(estado2c, contradiccion2c.contradiccion_id, "mas_pequenas_mas_viviendas")
check("resuelta tras responder_contradiccion", contradiccion2c.resuelta)
check("3 respuestas para el campo (dos en conflicto + la resolución)",
      len([r for r in estado2c.respuestas_interpretadas if r.especificacion_id == "programa.num_viviendas_mix"]) == 3)

motor.deshacer_ultimo_turno(estado2c)  # deshace el turno de RESOLUCIÓN
check("tras deshacer la resolución: la contradicción vuelve a estar pendiente", not contradiccion2c.resuelta)
check("tras deshacer la resolución: valor_resuelto limpio", contradiccion2c.valor_resuelto is None)
check("tras deshacer la resolución: siguen las 2 respuestas originales en conflicto (no 3, no 1)",
      len([r for r in estado2c.respuestas_interpretadas if r.especificacion_id == "programa.num_viviendas_mix"]) == 2)
check("sigue en la lista de contradicciones (no se borró de más)", contradiccion2c in estado2c.contradicciones)

motor.deshacer_ultimo_turno(estado2c)  # deshace ahora el turno de p6, que fue el que CREÓ la contradicción
check("tras deshacer p6: la contradicción fantasma desaparece del todo", contradiccion2c not in estado2c.contradicciones)
check("tras deshacer p6: el campo vuelve al valor original del bloque fijo, sin conflicto",
      motor.campo_tiene_respuesta(estado2c, "programa.num_viviendas_mix")
      and motor._valor_actual(estado2c, "programa.num_viviendas_mix") == "mas_pequenas_mas_viviendas")
check("tras deshacer p6: solo queda 1 respuesta para ese campo", len(
    [r for r in estado2c.respuestas_interpretadas if r.especificacion_id == "programa.num_viviendas_mix"]) == 1)


# =============================================================================
print()
print("=" * 70)
print("3. estimar_pasos_totales — barra de progreso dinámica, nunca clavada en un número fijo")
print("=" * 70)

estado3 = motor.iniciar_entrevista()
estimado_inicial = motor.estimar_pasos_totales(estado3)
check("estimación inicial > 0", estimado_inicial > 0, estimado_inicial)

fake3 = FakeInterprete()
_bloque_fijo_estandar(fake3)
preguntados3 = []
for _ in range(40):
    ps = motor.siguiente_pregunta(estado3)
    if ps is None:
        break
    if ps.es_resolucion_contradiccion:
        break
    for p in ps.preguntas:
        preguntados3.append(p.pregunta_id)
    respuestas = {p.pregunta_id: RESPUESTAS_COMPLETAS.get(p.pregunta_id, "no lo sé") for p in ps.preguntas}
    motor.responder(estado3, ps, respuestas, interprete=fake3)
check("siguiente_pregunta() se agotó de verdad (no hay más candidatas)", motor.siguiente_pregunta(estado3) is None)
check("al final, la estimación coincide EXACTAMENTE con los turnos ya hechos (100% real, no aproximado)",
      motor.estimar_pasos_totales(estado3) == estado3.turnos_totales,
      (motor.estimar_pasos_totales(estado3), estado3.turnos_totales))

# Sembrar ciudad/superficie reduce la estimación una vez p3 ("¿ya tienes la parcela?") se responde -- p3_
# ciudad/p3_superficie solo se ACTIVAN a partir de ahí (`condicion_activacion`), así que sembrar ANTES de
# eso no cambia nada todavía (no son candidatas de ninguna manera hasta que p3 se conteste) -- la prueba
# dinámica y honesta de que esta estimación se recalcula según lo que ya se sabe EN CADA punto del camino,
# no un número fijo calculado una sola vez al principio.
estado3b = motor.iniciar_entrevista()
motor.responder(estado3b, _ps_para("p3"), {"p3": "tengo la parcela"})
estimado_sin_sembrar = motor.estimar_pasos_totales(estado3b)
estado3c = motor.iniciar_entrevista()
motor.sembrar_hecho_externo(estado3c, "contexto.ciudad", "Sevilla", "Paso 0")
motor.sembrar_hecho_externo(estado3c, "solar.superficie_m2", 800.0, "Paso 0")
motor.responder(estado3c, _ps_para("p3"), {"p3": "tengo la parcela"})
estimado_con_sembrado = motor.estimar_pasos_totales(estado3c)
check("sembrar hechos externos reduce la estimación total de pasos (preguntas que ya no hace falta hacer)",
      estimado_con_sembrado < estimado_sin_sembrar, (estimado_sin_sembrar, estimado_con_sembrado))


# =============================================================================
print()
print("=" * 70)
print("4. Capa HTTP (app.py) — /api/entrevista con 'parcela' + /deshacer")
print("=" * 70)

r4_crear = client.post("/api/entrevista", json={
    "modo_entrada": "entrevista_guiada",
    "parcela": {"ciudad": "Sevilla", "superficie_m2": 800},
})
check("crear con 'parcela' -> 201", r4_crear.status_code == 201, r4_crear.status_code)
sesion4 = r4_crear.get_json()["sesion_id"]
check("respuesta ya trae 'pasos_estimados_totales'", isinstance(r4_crear.get_json().get("pasos_estimados_totales"), int))
check("respuesta ya trae 'puede_deshacer' == False (primer paso)", r4_crear.get_json().get("puede_deshacer") is False)

fake4 = FakeInterprete()
_bloque_fijo_estandar(fake4)
with patch("app._construir_interprete_entrevista", return_value=fake4):
    r4_bf = client.post("/api/entrevista/%s/responder" % sesion4, json={
        "respuestas": RESPUESTAS_BLOQUE_FIJO,
    })
check("bloque fijo -> 200", r4_bf.status_code == 200, r4_bf.get_json())
check("'puede_deshacer' ya es True tras el primer turno", r4_bf.get_json().get("puede_deshacer") is True)

r4_p2 = client.post("/api/entrevista/%s/responder" % sesion4, json={"respuestas": {"p2": "vivir"}})
check("p2 -> 200", r4_p2.status_code == 200)
r4_p3 = client.post("/api/entrevista/%s/responder" % sesion4, json={"respuestas": {"p3": "tengo la parcela"}})
check("p3 (gateway) -> 200", r4_p3.status_code == 200)

siguiente_ids_4 = []
for _ in range(15):
    body = client.get("/api/entrevista/%s" % sesion4).get_json()
    pregunta = body.get("pregunta_actual")
    if not pregunta or pregunta.get("es_resolucion_contradiccion"):
        break
    ids = [p["pregunta_id"] for p in pregunta["preguntas"]]
    siguiente_ids_4.extend(ids)
    if "p3_ciudad" in ids or "p3_superficie" in ids:
        break
    respuestas = {pid: RESPUESTAS_COMPLETAS.get(pid, "no lo sé") for pid in ids}
    client.post("/api/entrevista/%s/responder" % sesion4, json={"respuestas": respuestas})
check("a través de la API HTTP, p3_ciudad/p3_superficie tampoco se llegan a preguntar",
      "p3_ciudad" not in siguiente_ids_4 and "p3_superficie" not in siguiente_ids_4, siguiente_ids_4)

antes_deshacer = client.get("/api/entrevista/%s" % sesion4).get_json()
r4_deshacer = client.post("/api/entrevista/%s/deshacer" % sesion4, json={})
check("/deshacer -> 200", r4_deshacer.status_code == 200, r4_deshacer.get_json())
despues_deshacer = r4_deshacer.get_json()
check("/deshacer decrementa turnos_totales en 1",
      despues_deshacer["turnos_totales"] == antes_deshacer["turnos_totales"] - 1,
      (antes_deshacer["turnos_totales"], despues_deshacer["turnos_totales"]))

# --- Casos de error del endpoint ------------------------------------------------------------------------
r4_404 = client.post("/api/entrevista/000000000000/deshacer", json={})
check("/deshacer sobre una sesión inexistente -> 404", r4_404.status_code == 404, r4_404.status_code)

r4_nuevo = client.post("/api/entrevista", json={"modo_entrada": "entrevista_guiada"})
sesion4_nuevo = r4_nuevo.get_json()["sesion_id"]
r4_409 = client.post("/api/entrevista/%s/deshacer" % sesion4_nuevo, json={})
check("/deshacer en el primer paso (nada que deshacer) -> 409", r4_409.status_code == 409, r4_409.status_code)


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
