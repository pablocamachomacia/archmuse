# -*- coding: utf-8 -*-
"""Fase C del entrevistador — motor de entrevista.

Ejecutar:  python tests/test_interview_motor.py

Mismo estilo que el resto de `tests/`: script sin pytest, `check()`
acumula fallos, sale con código 1 si algo falla. **Nunca llama a Claude de
verdad** — todo lo que necesita interpretación usa `FakeInterprete`, definido
más abajo, que nunca importa `anthropic` ni toca la red.

20 escenarios, en el orden pedido en el encargo de la Fase C, más un bloque
final de instrumentación de coste.
"""
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer.interview import claude_interprete  # noqa: E402
from analyzer.interview import modelo  # noqa: E402
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


# =============================================================================
# FakeInterprete — nunca llama a Claude. Se "programa" con lo que debe
# devolver cada llamada, en el orden en que se espera que ocurran.
# =============================================================================


class FakeInterprete:
    def __init__(self):
        self.llamadas = []  # instrumentación: [{"tipo":..., ...}]
        self._bloque_fijo = []
        self._texto_libre = {}

    def programar_bloque_fijo(self, campos, contradiccion=None):
        self._bloque_fijo.append(("ok", campos, contradiccion))

    def programar_fallo_bloque_fijo(self):
        self._bloque_fijo.append(("fallo", None, None))

    def programar_texto_libre(self, pregunta_id, campos, contradiccion=None):
        self._texto_libre.setdefault(pregunta_id, []).append(("ok", campos, contradiccion))

    def interpretar_bloque_fijo(self, respuestas_crudas, turno_id):
        self.llamadas.append({"tipo": "bloque_fijo", "entrada": dict(respuestas_crudas)})
        if not self._bloque_fijo:
            raise AssertionError("FakeInterprete: falta programar_bloque_fijo() para esta llamada")
        tipo, campos, contradiccion = self._bloque_fijo.pop(0)
        if tipo == "fallo":
            raise claude_interprete.InterpretacionError("fallo simulado (programado por el test)")
        return _construir_resultado(campos, contradiccion, turno_id)

    def interpretar_texto_libre(self, pregunta, respuesta_cruda, turno_id):
        self.llamadas.append({"tipo": "texto_libre", "pregunta_id": pregunta.pregunta_id, "entrada": respuesta_cruda})
        cola = self._texto_libre.get(pregunta.pregunta_id)
        if not cola:
            raise AssertionError("FakeInterprete: falta programar_texto_libre(%r, ...)" % (pregunta.pregunta_id,))
        tipo, campos, contradiccion = cola.pop(0)
        if tipo == "fallo":
            raise claude_interprete.InterpretacionError("fallo simulado (programado por el test)")
        return _construir_resultado(campos, contradiccion, turno_id)


def _construir_resultado(campos, contradiccion, turno_id):
    respuestas = [
        modelo.RespuestaInterpretada(
            respuesta_id=modelo.nuevo_id(), turno_id=turno_id, especificacion_id=c["especificacion_id"],
            respuesta_cruda=c.get("respuesta_cruda"), naturaleza=c.get("naturaleza", "Inferencia"),
            valor=c.get("valor"), confianza=c.get("confianza"), motivo=c.get("motivo"),
        )
        for c in campos
    ]
    return claude_interprete.ResultadoInterpretacion(respuestas=respuestas, contradiccion_detectada=contradiccion)


# --- Helpers de test ---------------------------------------------------


def _ps_para(*pregunta_ids):
    preguntas = tuple(preguntas_mod.PREGUNTAS_POR_ID[pid] for pid in pregunta_ids)
    return motor.PreguntaSiguiente(turno_id=modelo.nuevo_id(), preguntas=preguntas, motivo="test_directo")


def _ejecutar(estado, respuestas_por_pregunta, interprete=None, max_iter=40, detener_en_contradiccion=True):
    """Recorre `siguiente_pregunta()`/`responder()` hasta que no queda nada
    que preguntar. Cualquier pregunta sin respuesta programada se contesta
    "no lo sé" (nunca inventa, nunca llama a Claude por sorpresa)."""
    motivos = []
    for _ in range(max_iter):
        ps = motor.siguiente_pregunta(estado)
        if ps is None:
            break
        if ps.es_resolucion_contradiccion:
            if detener_en_contradiccion:
                motivos.append(ps.motivo)
                break
            raise AssertionError("contradicción sin resolver y detener_en_contradiccion=False")
        respuestas_crudas = {p.pregunta_id: respuestas_por_pregunta.get(p.pregunta_id, "no lo sé") for p in ps.preguntas}
        motor.responder(estado, ps, respuestas_crudas, interprete=interprete)
        motivos.append(ps.motivo)
    return motivos


def _bloque_fijo_estandar(fake, ciudad=None, tipologia=None, mix=None, trade_off="luz_sobre_superficie"):
    campos = [
        {"especificacion_id": "programa.descripcion_libre", "naturaleza": "Hecho",
         "valor": "descripción libre del proyecto", "respuesta_cruda_citada": "..."},
        {"especificacion_id": "programa.sensacion_buscada", "naturaleza": "Inferencia",
         "valor": "luminosa y amplia", "confianza": "Media"},
        {"especificacion_id": "prioridades.no_negociables", "naturaleza": "Hecho", "valor": "tres dormitorios"},
        {"especificacion_id": "prioridades.lo_de_menos_importa", "naturaleza": "Hecho", "valor": "el garaje"},
        {"especificacion_id": "prioridades.trade_off", "naturaleza": "Inferencia", "valor": trade_off, "confianza": "Media"},
    ]
    if ciudad:
        campos.append({"especificacion_id": "contexto.ciudad", "naturaleza": "Inferencia", "valor": ciudad, "confianza": "Media"})
    if tipologia:
        campos.append({"especificacion_id": "programa.tipologia", "naturaleza": "Inferencia", "valor": tipologia, "confianza": "Media"})
    if mix:
        campos.append({"especificacion_id": "programa.num_viviendas_mix", "naturaleza": "Inferencia", "valor": mix, "confianza": "Media"})
    fake.programar_bloque_fijo(campos)


RESPUESTAS_SABE_LO_QUE_QUIERE = {
    "p1": "Quiero una casa unifamiliar en Sevilla para vivir yo, con mucha luz natural.",
    "p4": "Que tenga tres dormitorios y un salón grande.",
    "p5": "El garaje no me importa mucho.",
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
    "p11": "Casa moderna minimalista",
    "p12": "normal",
    "p13": "no",
    "p14": "espacio exterior propio",
    "p15": "abierta",
    "p_tipologia_directa": "unifamiliar",
}


# =============================================================================
print("=" * 70)
print("1. USUARIO QUE SABE EXACTAMENTE LO QUE QUIERE")
print("=" * 70)

estado1 = motor.iniciar_entrevista()
fake1 = FakeInterprete()
_bloque_fijo_estandar(fake1)
motivos1 = _ejecutar(estado1, RESPUESTAS_SABE_LO_QUE_QUIERE, interprete=fake1)

cierre1 = motor.evaluar_cierre(estado1)
check("la entrevista puede cerrarse", cierre1.puede_cerrar, cierre1.motivo)
check("los 8 imprescindibles están resueltos", cierre1.imprescindibles_pendientes == [], cierre1.imprescindibles_pendientes)
check("no hace falta forzar por límite de turnos", not cierre1.limite_turnos_alcanzado)
check("no hace falta forzar por límite de llamadas", not cierre1.limite_llamadas_alcanzado)
check("solo 1 llamada a Claude (el bloque fijo, todo lo demás era cerrado/numérico)",
      estado1.llamadas_ia_consumidas == 1, estado1.llamadas_ia_consumidas)
check("muy por debajo del límite de turnos", estado1.turnos_totales < motor.LIMITE_TURNOS, estado1.turnos_totales)
check("orientación real registrada como Hecho 'sur'",
      any(r.especificacion_id == "orientacion.real_parcela" and r.valor == "sur" and r.naturaleza == "Hecho"
          for r in estado1.respuestas_interpretadas))
check("no_negociables recoge el texto del bloque fijo", "tres dormitorios" in estado1.no_negociables)
motor.cerrar_entrevista(estado1)
check("cerrar_entrevista() la deja en estado 'cerrada'", estado1.estado == "cerrada")


# =============================================================================
print()
print("=" * 70)
print("2. USUARIO QUE NO SABE NADA")
print("=" * 70)

estado2 = motor.iniciar_entrevista()
motivos2 = _ejecutar(estado2, {}, interprete=None)  # nunca se pasa un interprete: no debe hacer falta

cierre2 = motor.evaluar_cierre(estado2)
check("puede cerrarse igualmente (nunca bloquea sin salida)", cierre2.puede_cerrar, cierre2.motivo)
check("0 llamadas a Claude ('no sé' nunca dispara IA)", estado2.llamadas_ia_consumidas == 0, estado2.llamadas_ia_consumidas)
for especificacion_id in preguntas_mod.IMPRESCINDIBLES:
    respuestas_campo = [r for r in estado2.respuestas_interpretadas if r.especificacion_id == especificacion_id]
    check("%s quedó como Hipótesis explícita, nunca inventado" % especificacion_id,
          bool(respuestas_campo) and all(r.naturaleza == "Hipótesis" and r.valor is None for r in respuestas_campo),
          respuestas_campo)


# =============================================================================
print()
print("=" * 70)
print("3. USUARIO QUE RESPONDE CON FRASES VAGAS")
print("=" * 70)

estado3 = motor.iniciar_entrevista()
fake3 = FakeInterprete()
_bloque_fijo_estandar(fake3, ciudad="Valencia", tipologia="plurifamiliar", mix="mas_pequenas_mas_viviendas")
fake3.programar_texto_libre("p9", [
    {"especificacion_id": "presupuesto.cifra_horquilla", "naturaleza": "Hipótesis", "valor": "gama_media",
     "confianza": "Media", "motivo": "expresó no querer pasarse, sin cifra concreta"},
])
fake3.programar_texto_libre("p11", [
    {"especificacion_id": "identidad.referencias_esteticas", "naturaleza": "Preferencia",
     "valor": "estilo_mediterraneo_luminoso", "confianza": "Media"},
])
respuestas3 = dict(RESPUESTAS_SABE_LO_QUE_QUIERE)
respuestas3.update({
    "p9": "lo que haga falta, no quiero pasarme",
    "p11": "algo bonito pero no sé explicarlo bien, que se sienta como en casa",
})
_ejecutar(estado3, respuestas3, interprete=fake3)

check("p9 vaga necesitó interpretación (evento texto_libre)",
      any(c["tipo"] == "texto_libre" and c["pregunta_id"] == "p9" for c in fake3.llamadas))
check("p11 vaga necesitó interpretación (evento texto_libre)",
      any(c["tipo"] == "texto_libre" and c["pregunta_id"] == "p11" for c in fake3.llamadas))
check("presupuesto quedó como Hipótesis con motivo explícito",
      any(r.especificacion_id == "presupuesto.cifra_horquilla" and r.naturaleza == "Hipótesis" and r.motivo
          for r in estado3.respuestas_interpretadas))
check("3 llamadas en total (bloque fijo + p9 + p11), dentro de 3-5",
      estado3.llamadas_ia_consumidas == 3, estado3.llamadas_ia_consumidas)


# =============================================================================
print()
print("=" * 70)
print("4. RESPUESTAS CONTRADICTORIAS")
print("=" * 70)

estado4 = motor.iniciar_entrevista()
fake4 = FakeInterprete()
_bloque_fijo_estandar(fake4, mix="mas_pequenas_mas_viviendas")  # "quiero el máximo número de viviendas posible"
ps_fijo4 = motor.siguiente_pregunta(estado4)
motor.responder(estado4, ps_fijo4, {"p1": "Quiero el máximo número de viviendas posible", "p4": "no sé", "p5": "no sé"}, interprete=fake4)

check("de momento programa.num_viviendas_mix = mas_pequenas_mas_viviendas (sin contradicción)",
      motor._contradiccion_pendiente(estado4, "programa.num_viviendas_mix") is None)

# El usuario, más tarde, se contradice: "Quiero viviendas muy grandes."
motor.responder(estado4, _ps_para("p6"), {"p6": "viviendas muy grandes"})

contradiccion4 = motor._contradiccion_pendiente(estado4, "programa.num_viviendas_mix")
check("la contradicción queda registrada, no se sobrescribe en silencio", contradiccion4 is not None)
check("los DOS valores en conflicto siguen presentes",
      contradiccion4 is not None and len(contradiccion4.valores_en_conflicto) == 2
      and {v.valor for v in contradiccion4.valores_en_conflicto} == {"mas_pequenas_mas_viviendas", "mas_grandes_menos_viviendas"})
check("ambas RespuestaInterpretada siguen en el historial (nada se borra)",
      len([r for r in estado4.respuestas_interpretadas if r.especificacion_id == "programa.num_viviendas_mix"]) == 2)
check("el campo NO cuenta como resuelto mientras la contradicción esté pendiente",
      not motor.campo_tiene_respuesta(estado4, "programa.num_viviendas_mix"))

siguiente4 = motor.siguiente_pregunta(estado4)
check("resolver la contradicción tiene prioridad máxima sobre cualquier otra pregunta",
      siguiente4 is not None and siguiente4.es_resolucion_contradiccion
      and siguiente4.contradiccion_id == contradiccion4.contradiccion_id)

motor.responder_contradiccion(estado4, contradiccion4.contradiccion_id, "mas_pequenas_mas_viviendas")
check("tras resolver, la contradicción queda marcada resuelta", contradiccion4.resuelta and contradiccion4.valor_resuelto == "mas_pequenas_mas_viviendas")
check("el campo ahora SÍ cuenta como resuelto", motor.campo_tiene_respuesta(estado4, "programa.num_viviendas_mix"))
check("queda una 3ª entrada explicando la resolución, ninguna de las anteriores se tocó",
      len([r for r in estado4.respuestas_interpretadas if r.especificacion_id == "programa.num_viviendas_mix"]) == 3)


# =============================================================================
print()
print("=" * 70)
print("5. RESPUESTA QUE HACE INNECESARIA UNA PREGUNTA POSTERIOR")
print("=" * 70)

estado5 = motor.iniciar_entrevista()
fake5 = FakeInterprete()
_bloque_fijo_estandar(fake5, ciudad="Bilbao")  # el usuario mencionó la ciudad en la respuesta libre
motor.responder(estado5, motor.siguiente_pregunta(estado5),
                 {"p1": "Quiero construir en Bilbao, cerca del centro", "p4": "no sé", "p5": "no sé"}, interprete=fake5)

check("contexto.ciudad ya resuelto por el bloque fijo, sin necesidad de p3_ciudad",
      motor.campo_tiene_respuesta(estado5, "contexto.ciudad"))
antes_de_p3 = motor._candidatas_adaptativas(estado5)
check("p3_ciudad NO es candidata todavía (la puerta de p3 sigue cerrada)",
      "p3_ciudad" not in [p.pregunta_id for p in antes_de_p3])

motor.responder(estado5, _ps_para("p3"), {"p3": "tengo la parcela"})
despues_de_p3 = motor._candidatas_adaptativas(estado5)
check("tras abrirse la puerta de p3, p3_ciudad SIGUE sin ser candidata (ya se sabe la ciudad)",
      "p3_ciudad" not in [p.pregunta_id for p in despues_de_p3])
check("pero p3_superficie SÍ es candidata (eso no se ha preguntado todavía)",
      "p3_superficie" in [p.pregunta_id for p in despues_de_p3])


# =============================================================================
print()
print("=" * 70)
print("6. ACTIVACIÓN DE PREGUNTAS CONDICIONALES (bifurcación de la pregunta 3)")
print("=" * 70)

for valor_p3, etiqueta in (("tengo la parcela", "tengo_parcela"), ("todavía la estoy buscando", "buscando_parcela")):
    estado6 = motor.iniciar_entrevista()
    candidatas_antes = motor._candidatas_adaptativas(estado6)
    ids_antes = {p.pregunta_id for p in candidatas_antes}
    check("[%s] la rama no tomada (sub-preguntas de la 3) no se pregunta antes de responder p3" % etiqueta,
          {"p3_ciudad", "p3_superficie", "p3_forma"}.isdisjoint(ids_antes))

    motor.responder(estado6, _ps_para("p3"), {"p3": valor_p3})
    candidatas_despues = motor._candidatas_adaptativas(estado6)
    ids_despues = {p.pregunta_id for p in candidatas_despues}
    check("[%s] tras responder p3, las 3 sub-preguntas se activan" % etiqueta,
          {"p3_ciudad", "p3_superficie", "p3_forma"}.issubset(ids_despues))


# =============================================================================
print()
print("=" * 70)
print("7. INFORMACIÓN DERIVABLE QUE NO DEBE PREGUNTARSE")
print("=" * 70)

textos_catalogo = " ".join(p.texto.lower() + " " + p.que_pretende_obtener.lower() for p in preguntas_mod.PREGUNTAS)
ids_catalogo = " ".join(i for p in preguntas_mod.PREGUNTAS for i in p.especificacion_ids)
check("ninguna pregunta pide la zona climática CTE (se deriva de la ciudad, cte_zonas.py)",
      "zona climática" not in textos_catalogo and "zona_cte" not in ids_catalogo)
check("ninguna pregunta pide la comunidad autónoma (se deriva de la ciudad)",
      "comunidad autónoma" not in textos_catalogo and "comunidad_autonoma" not in ids_catalogo)
check("ninguna pregunta promete comprobar normativa municipal (§6.4, honesto)",
      "lo comprobamos por ti" not in textos_catalogo)


# =============================================================================
print()
print("=" * 70)
print("8. ACCESIBILIDAD")
print("=" * 70)

estado8 = motor.iniciar_entrevista()
resultado8 = motor.responder(estado8, _ps_para("p13"), {"p13": "sí, mi madre usa silla de ruedas"})
check("accesibilidad = Hecho 'si', sin llamar a Claude (pregunta cerrada)",
      any(r.especificacion_id == "usuarios.accesibilidad" and r.valor == "si" and r.naturaleza == "Hecho"
          for r in estado8.respuestas_interpretadas))
check("0 llamadas IA para una pregunta cerrada", estado8.llamadas_ia_consumidas == 0)
check("0 eventos de llamada IA", resultado8.eventos_llamadas_ia == [])


# =============================================================================
print()
print("=" * 70)
print("9. PREFERENCIAS DE CARÁCTER (identidad / referencias estéticas)")
print("=" * 70)

estado9 = motor.iniciar_entrevista()
fake9 = FakeInterprete()
fake9.programar_texto_libre("p11", [
    {"especificacion_id": "identidad.referencias_esteticas", "naturaleza": "Preferencia",
     "valor": "casas escandinavas con madera vista y mucha luz", "confianza": "Alta"},
])
texto_largo = "Me encantan las casas escandinavas con madera vista, muy luminosas y sencillas"
resultado9 = motor.responder(estado9, _ps_para("p11"), {"p11": texto_largo}, interprete=fake9)
check("texto largo (>4 palabras) SÍ necesita interpretación", len(fake9.llamadas) == 1)
check("el campo queda etiquetado como Preferencia, no como Hecho",
      estado9.respuestas_interpretadas[-1].naturaleza == "Preferencia")

# Referencia breve: no hace falta Claude.
estado9b = motor.iniciar_entrevista()
motor.responder(estado9b, _ps_para("p11"), {"p11": "Casas nórdicas de madera"})
check("referencia breve (<=4 palabras) NO necesita interpretación", estado9b.llamadas_ia_consumidas == 0)


# =============================================================================
print()
print("=" * 70)
print("10. PRIVACIDAD")
print("=" * 70)

estado10 = motor.iniciar_entrevista()
motor.responder(estado10, _ps_para("p12"), {"p12": "necesito mucha privacidad, tengo vecinos muy cerca"})
check("privacidad = Hecho 'mucha'",
      any(r.especificacion_id == "privacidad.necesidad" and r.valor == "mucha" for r in estado10.respuestas_interpretadas))


# =============================================================================
print()
print("=" * 70)
print("11. PRESUPUESTO")
print("=" * 70)

estado11a = motor.iniciar_entrevista()
motor.responder(estado11a, _ps_para("p9"), {"p9": "unos 150.000 euros"})
check("cifra clara -> determinista, 0 llamadas IA", estado11a.llamadas_ia_consumidas == 0)
check("presupuesto = Hecho con la cifra tal cual",
      any(r.especificacion_id == "presupuesto.cifra_horquilla" and r.naturaleza == "Hecho" for r in estado11a.respuestas_interpretadas))

estado11b = motor.iniciar_entrevista()
fake11b = FakeInterprete()
fake11b.programar_texto_libre("p9", [
    {"especificacion_id": "presupuesto.cifra_horquilla", "naturaleza": "Hipótesis", "valor": "ajustado",
     "confianza": "Baja", "motivo": "sin cifra concreta"},
])
motor.responder(estado11b, _ps_para("p9"), {"p9": "lo mínimo posible, soy muy justo de dinero"}, interprete=fake11b)
check("frase vaga -> necesita interpretación, 1 llamada IA", estado11b.llamadas_ia_consumidas == 1)


# =============================================================================
print()
print("=" * 70)
print("12. SOSTENIBILIDAD")
print("=" * 70)

estado12 = motor.iniciar_entrevista()
motor.responder(estado12, _ps_para("p10"), {"p10": "prefiero ahorrar en la factura energética a largo plazo"})
check("sostenibilidad = Hecho 'ahorro_energetico_largo_plazo'",
      any(r.especificacion_id == "sostenibilidad.prioridad" and r.valor == "ahorro_energetico_largo_plazo"
          for r in estado12.respuestas_interpretadas))


# =============================================================================
print()
print("=" * 70)
print("13. ORIENTACIÓN (real de la parcela, nunca preferencia solar)")
print("=" * 70)

estado13a = motor.iniciar_entrevista()
motor.responder(estado13a, _ps_para("p8"), {"p8": "la fachada da al sur"})
check("orientación por punto cardinal -> Hecho 'sur', determinista",
      any(r.especificacion_id == "orientacion.real_parcela" and r.valor == "sur" for r in estado13a.respuestas_interpretadas))
check("0 llamadas IA (pregunta condicional, pero no libre)", estado13a.llamadas_ia_consumidas == 0)

estado13b = motor.iniciar_entrevista()
motor.responder(estado13b, _ps_para("p8"), {"p8": "Calle Mayor 5, Sevilla"})
respuesta13b = next(r for r in estado13b.respuestas_interpretadas if r.especificacion_id == "orientacion.real_parcela")
check("dirección sin punto cardinal -> se guarda tal cual como Hecho (pendiente de mapa)",
      respuesta13b.naturaleza == "Hecho" and respuesta13b.valor == "Calle Mayor 5, Sevilla")
check("nunca se pregunta una preferencia solar interior en su lugar",
      "sol" not in preguntas_mod.PREGUNTAS_POR_ID["p8"].texto.lower()
      or "fachada" in preguntas_mod.PREGUNTAS_POR_ID["p8"].texto.lower())


# =============================================================================
print()
print("=" * 70)
print("14. MÁXIMO DE 20 TURNOS")
print("=" * 70)

estado14 = motor.iniciar_entrevista()
estado14.turnos_totales = motor.LIMITE_TURNOS - 1
ps14 = motor.siguiente_pregunta(estado14)
check("con 19 turnos todavía se puede preguntar", ps14 is not None)
motor.responder(estado14, ps14, {p.pregunta_id: "no lo sé" for p in ps14.preguntas})
check("tras el turno 20, siguiente_pregunta() ya no propone nada", motor.siguiente_pregunta(estado14) is None)
check("evaluar_cierre marca el límite de turnos alcanzado", motor.evaluar_cierre(estado14).limite_turnos_alcanzado)


# =============================================================================
print()
print("=" * 70)
print("15. MÁXIMO DE 5 LLAMADAS IA")
print("=" * 70)

estado15 = motor.iniciar_entrevista()
fake15_inicial = FakeInterprete()
_bloque_fijo_estandar(fake15_inicial)
motor.responder(estado15, motor.siguiente_pregunta(estado15),
                 {"p1": "algo", "p4": "algo", "p5": "algo"}, interprete=fake15_inicial)
# El bloque fijo (turno obligatorio inicial) SIEMPRE se propone aunque no
# quede presupuesto — degrada con gracia dentro de responder() (ver más
# abajo); lo que este escenario comprueba es la cola ADAPTATIVA una vez
# el presupuesto ya está agotado, que es el caso real (turno 1 siempre
# consume la primera llamada del presupuesto, nunca al revés).
estado15.llamadas_ia_consumidas = motor.LIMITE_LLAMADAS_IA
fake15 = FakeInterprete()  # no se le programa nada: si se le llama, el test debe fallar con AssertionError
candidatas15 = motor._candidatas_adaptativas(estado15)
ps15 = motor.siguiente_pregunta(estado15)
check("con el presupuesto agotado, solo se proponen preguntas deterministas",
      ps15 is None or all(p.requiere_ia == "nunca" for p in ps15.preguntas))
resultado15 = motor.responder(estado15, _ps_para("p11"), {"p11": "un texto largo que normalmente necesitaría IA de verdad"}, interprete=fake15)
check("con presupuesto agotado, una pregunta que normalmente pediría IA no llama a Claude", fake15.llamadas == [])
check("en su lugar queda como Hipótesis explícita por límite alcanzado",
      any(r.especificacion_id == "identidad.referencias_esteticas" and r.naturaleza == "Hipótesis"
          and "límite" in (r.motivo or "") for r in estado15.respuestas_interpretadas))
check("el contador de llamadas no sube por encima del límite", estado15.llamadas_ia_consumidas == motor.LIMITE_LLAMADAS_IA)


# =============================================================================
print()
print("=" * 70)
print("16. ENTREVISTA SUFICIENTE QUE TERMINA ANTES DE LOS LÍMITES")
print("=" * 70)

check("el escenario 1 (usuario que sabe lo que quiere) terminó antes de los límites, no al alcanzarlos",
      estado1.turnos_totales < motor.LIMITE_TURNOS and estado1.llamadas_ia_consumidas < motor.LIMITE_LLAMADAS_IA,
      "turnos=%d llamadas=%d" % (estado1.turnos_totales, estado1.llamadas_ia_consumidas))
check("el motivo de cierre es 'información suficiente', no un límite",
      "resueltos" in motor.evaluar_cierre(estado1).motivo)


# =============================================================================
print()
print("=" * 70)
print("17. IMPOSIBILIDAD DE COMPLETAR INFORMACIÓN SIN INVENTAR")
print("=" * 70)

estado17 = motor.iniciar_entrevista()
estado17.turnos_totales = motor.LIMITE_TURNOS  # ya en el límite, sin haber respondido nada
cierre17 = motor.evaluar_cierre(estado17)
check("con el límite alcanzado y nada respondido, puede cerrarse igualmente (nunca bloquea)", cierre17.puede_cerrar)
check("pero deja constancia explícita de qué falta, no lo inventa",
      set(cierre17.imprescindibles_pendientes) == set(preguntas_mod.IMPRESCINDIBLES))
motor.cerrar_entrevista(estado17)  # no debe lanzar (puede_cerrar ya era True)
check("cerrar_entrevista() no lanza cuando el cierre forzado ya es válido", estado17.estado == "cerrada")
check("ningún imprescindible tiene una RespuestaInterpretada inventada",
      all(not any(r.especificacion_id == i for r in estado17.respuestas_interpretadas)
          for i in preguntas_mod.IMPRESCINDIBLES))


# =============================================================================
print()
print("=" * 70)
print("18. REANUDACIÓN DE UNA ENTREVISTA EXISTENTE")
print("=" * 70)

from analyzer import storage  # noqa: E402

TMP = tempfile.mkdtemp(prefix="archmuse_test_interview_motor_")
os.environ["ARCHMUSE_DATA_DIR"] = TMP
storage.init_db()

estado18 = motor.iniciar_entrevista()
fake18 = FakeInterprete()
_bloque_fijo_estandar(fake18, ciudad="Zaragoza")
ps18 = motor.siguiente_pregunta(estado18)
motor.responder(estado18, ps18, {"p1": "Quiero construir en Zaragoza", "p4": "no sé", "p5": "no sé"}, interprete=fake18)
motor.responder(estado18, _ps_para("p13"), {"p13": "no"})

storage.guardar_entrevista(estado18)
turnos_antes = estado18.turnos_totales
llamadas_antes = estado18.llamadas_ia_consumidas

del sys.modules["analyzer.storage"]
from analyzer import storage as storage_reiniciado  # noqa: E402

recuperado18 = storage_reiniciado.obtener_entrevista(estado18.sesion_id)
check("la entrevista se recupera tras 'reiniciar' storage", recuperado18 is not None)
estado18_reanudado = recuperado18["estado"]
check("el estado reanudado conserva los turnos ya hechos", estado18_reanudado.turnos_totales == turnos_antes)
check("el estado reanudado conserva las llamadas ya consumidas", estado18_reanudado.llamadas_ia_consumidas == llamadas_antes)
check("contexto.ciudad sigue resuelto tras reanudar", motor.campo_tiene_respuesta(estado18_reanudado, "contexto.ciudad"))

candidatas_reanudado = motor._candidatas_adaptativas(estado18_reanudado)
check("p13 (ya respondida) no se vuelve a proponer tras reanudar",
      "p13" not in [p.pregunta_id for p in candidatas_reanudado])
motor.responder(estado18_reanudado, _ps_para("p12"), {"p12": "normal"})
check("la entrevista reanudada puede seguir avanzando con normalidad",
      any(r.especificacion_id == "privacidad.necesidad" for r in estado18_reanudado.respuestas_interpretadas))

import shutil  # noqa: E402
shutil.rmtree(TMP, ignore_errors=True)


# =============================================================================
print()
print("=" * 70)
print("19. CATÁLOGO CERRADO")
print("=" * 70)


def _rechaza(nombre, constructor):
    try:
        constructor()
        check(nombre, False, "no lanzó ValueError")
    except ValueError:
        check(nombre, True)


_rechaza("Pregunta.categoria fuera de las 15 categorías", lambda: preguntas_mod.Pregunta(
    pregunta_id="x", numero_prd=None, categoria="categoria_inventada", tipo="abierta", texto="x",
    que_pretende_obtener="x", especificacion_ids=("x.y",), bloque="adaptativo",
))
_rechaza("Pregunta.tipo fuera de catálogo", lambda: preguntas_mod.Pregunta(
    pregunta_id="x", numero_prd=None, categoria="parcela", tipo="mixta", texto="x",
    que_pretende_obtener="x", especificacion_ids=("x.y",), bloque="adaptativo",
))
_rechaza("Pregunta.requiere_ia fuera de catálogo", lambda: preguntas_mod.Pregunta(
    pregunta_id="x", numero_prd=None, categoria="parcela", tipo="abierta", texto="x",
    que_pretende_obtener="x", especificacion_ids=("x.y",), bloque="adaptativo", requiere_ia="a_veces",
))
_rechaza("Pregunta.bloque fuera de catálogo", lambda: preguntas_mod.Pregunta(
    pregunta_id="x", numero_prd=None, categoria="parcela", tipo="abierta", texto="x",
    que_pretende_obtener="x", especificacion_ids=("x.y",), bloque="intermedio",
))
_rechaza("CondicionActivacion.operador fuera de catálogo", lambda: preguntas_mod.CondicionActivacion(
    especificacion_id="x.y", operador="mas_o_menos",
))
check("PREGUNTAS_POR_ID no tiene ids duplicados",
      len(preguntas_mod.PREGUNTAS_POR_ID) == len(preguntas_mod.PREGUNTAS))
check("todas las categorías usadas están en el catálogo cerrado de Fase A",
      all(p.categoria in modelo.CATEGORIAS_ESPECIFICACION for p in preguntas_mod.PREGUNTAS))


# =============================================================================
print()
print("=" * 70)
print("20. DETERMINISMO DEL MOTOR CUANDO NO INTERVIENE CLAUDE")
print("=" * 70)

RESPUESTAS_CERRADAS = {
    "p1": "no sé", "p4": "no sé", "p5": "no sé",  # bloque fijo -> Hipótesis, 0 IA
    "p2": "vivir", "p3": "tengo la parcela", "p3_ciudad": "Toledo", "p3_superficie": "600",
    "p3_forma": "irregular", "p6": "más grandes y menos", "p7": "no sé", "p8": "este",
    "p9": "100000", "p10": "coste de construcción bajo", "p11": "casas de piedra tradicionales",
    "p12": "le da igual", "p13": "no lo sé", "p14": "aprovechar metros interiores", "p15": "cerrada",
    "p_tipologia_directa": "unifamiliar",
}


def _huella(estado):
    return [
        (r.especificacion_id, r.naturaleza, r.valor, r.confianza, r.motivo)
        for r in estado.respuestas_interpretadas
    ]


estado20a = motor.iniciar_entrevista()
motivos20a = _ejecutar(estado20a, RESPUESTAS_CERRADAS, interprete=None)
estado20b = motor.iniciar_entrevista()
motivos20b = _ejecutar(estado20b, RESPUESTAS_CERRADAS, interprete=None)

check("ninguna de las dos ejecuciones necesitó pasar un interprete (0 llamadas de verdad)",
      estado20a.llamadas_ia_consumidas == 0 and estado20b.llamadas_ia_consumidas == 0)
check("mismo orden de preguntas en las dos ejecuciones (cola priorizada determinista)", motivos20a == motivos20b)
check("misma huella de respuestas interpretadas, campo a campo", _huella(estado20a) == _huella(estado20b))
check("mismo número de turnos", estado20a.turnos_totales == estado20b.turnos_totales)
check("mismo resultado de cierre", motor.evaluar_cierre(estado20a).puede_cerrar == motor.evaluar_cierre(estado20b).puede_cerrar)

try:
    motor.responder(motor.iniciar_entrevista(), _ps_para("p11"), {"p11": "un texto muy largo que en teoría necesitaría interpretación real"})
    check("una pregunta que de verdad requiere IA sin interprete lanza InterpretacionRequeridaError", False)
except motor.InterpretacionRequeridaError:
    check("una pregunta que de verdad requiere IA sin interprete lanza InterpretacionRequeridaError", True)


# =============================================================================
print()
print("=" * 70)
print("INSTRUMENTACIÓN DE COSTE (número de llamadas, motivo, extracción, evitabilidad)")
print("=" * 70)

estado_i = motor.iniciar_entrevista()
fake_i = FakeInterprete()
_bloque_fijo_estandar(fake_i)
ps_i = motor.siguiente_pregunta(estado_i)
resultado_i = motor.responder(estado_i, ps_i, {"p1": "sí", "p4": "no", "p5": "ok"}, interprete=fake_i)

check("el evento de bloque fijo trae el paso, el motivo y los especificacion_id extraídos",
      len(resultado_i.eventos_llamadas_ia) == 1
      and resultado_i.eventos_llamadas_ia[0].paso == "bloque_fijo"
      and len(resultado_i.eventos_llamadas_ia[0].especificacion_ids_extraidos) >= 4)
check("respuestas de 1 palabra -> la llamada se marca como 'evitable' (heurística explícita, ver motor.py)",
      resultado_i.eventos_llamadas_ia[0].evitable is True)
check("número de llamadas reales == estado.llamadas_ia_consumidas",
      sum(1 for e in resultado_i.eventos_llamadas_ia if e.realizada) == estado_i.llamadas_ia_consumidas == 1)

# Un fallo de interpretación también cuenta para el presupuesto y queda instrumentado.
estado_f = motor.iniciar_entrevista()
fake_f = FakeInterprete()
fake_f.programar_fallo_bloque_fijo()
resultado_f = motor.responder(estado_f, motor.siguiente_pregunta(estado_f),
                               {"p1": "un proyecto interesante", "p4": "cosas", "p5": "otras cosas"}, interprete=fake_f)
check("un fallo de interpretación cuenta como llamada realizada (se intentó)",
      estado_f.llamadas_ia_consumidas == 1)
check("el campo afectado queda como Hipótesis con el motivo del fallo, nunca inventado",
      all(r.naturaleza == "Hipótesis" and "fallo de interpretación" in (r.motivo or "")
          for r in estado_f.respuestas_interpretadas))


# =============================================================================
print()
print("=" * 70)
print("%d comprobaciones" % comprobaciones)
if fallos:
    print("FALLOS (%d): %s" % (len(fallos), ", ".join(fallos)))
    sys.exit(1)
print("Todas las comprobaciones OK")
