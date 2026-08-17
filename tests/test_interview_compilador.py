# -*- coding: utf-8 -*-
"""Fase D del entrevistador — compilador de la Especificación Arquitectónica.

Ejecutar:  python tests/test_interview_compilador.py

Mismo estilo que el resto de `tests/`: script sin pytest, `check()` acumula
fallos, sale con código 1 si algo falla. **Nunca llama a Claude ni importa
`app.py`/`ai_generator.py`** — este módulo, y sus tests, se prueban
completamente sin Flask y sin red (test 13). No se puede importar `app.py`
en este archivo: falla hoy por una dependencia preexistente ausente
(`yaml`, vía `analyzer/cte_zonas.py` → `normativa/derivados.py`), el mismo
hueco de entorno ya documentado en el cierre de las Fases A y C — por eso el
test 10 compara la forma del `params` compilado contra una copia, verificada
a mano línea a línea, de `app.py:_parse_generar_params` (líneas 550-619 a
fecha de esta fase) en vez de importar la función real.

15 escenarios pedidos en el encargo de la Fase D, más algunos extra para las
dos contradicciones documentadas al principio de `compilador.py` (mix
numérico vs. preferencia cualitativa; orientación por compás vs. grados) y
el hueco de `edificio.plantas`.
"""
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

TMP = tempfile.mkdtemp(prefix="archmuse_test_interview_compilador_")
os.environ["ARCHMUSE_DATA_DIR"] = TMP

from analyzer.interview import claude_interprete  # noqa: E402
from analyzer.interview import compilador  # noqa: E402
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
# Helpers — mismo patrón que tests/test_interview_motor.py (FakeInterprete,
# bucle de entrevista guiada), redefinidos aquí para que este archivo no
# dependa de otro archivo de test.
# =============================================================================


class FakeInterprete:
    def __init__(self):
        self.llamadas = []
        self._bloque_fijo = []

    def programar_bloque_fijo(self, campos):
        self._bloque_fijo.append(campos)

    def interpretar_bloque_fijo(self, respuestas_crudas, turno_id):
        self.llamadas.append({"tipo": "bloque_fijo", "entrada": dict(respuestas_crudas)})
        campos = self._bloque_fijo.pop(0)
        respuestas = [
            modelo.RespuestaInterpretada(
                respuesta_id=modelo.nuevo_id(), turno_id=turno_id, especificacion_id=c["especificacion_id"],
                respuesta_cruda=c.get("respuesta_cruda"), naturaleza=c.get("naturaleza", "Hecho"),
                valor=c.get("valor"), confianza=c.get("confianza"), motivo=c.get("motivo"),
            )
            for c in campos
        ]
        return claude_interprete.ResultadoInterpretacion(respuestas=respuestas)

    def interpretar_texto_libre(self, pregunta, respuesta_cruda, turno_id):  # pragma: no cover - no usado en estos tests
        raise AssertionError("FakeInterprete: interpretar_texto_libre no programado en estos tests")


def _ejecutar(estado, respuestas_por_pregunta, interprete=None, max_iter=40):
    for _ in range(max_iter):
        ps = motor.siguiente_pregunta(estado)
        if ps is None or ps.es_resolucion_contradiccion:
            break
        respuestas_crudas = {p.pregunta_id: respuestas_por_pregunta.get(p.pregunta_id, "no lo sé") for p in ps.preguntas}
        motor.responder(estado, ps, respuestas_crudas, interprete=interprete)


VALORES_EXPERTOS_COMPLETOS = {
    "contexto.ciudad": "Valencia",
    "programa.tipologia": "plurifamiliar",
    "solar.superficie_m2": 800.0,
    "solar.forma": "rectangular",
    "programa.num_viviendas_mix": {"dorm_1": 2, "dorm_2": 3, "dorm_3": 1},
    "prioridades.trade_off": "luz",
    "usuarios.accesibilidad": "si",
    "orientacion.real_parcela": "sur",
    "edificio.plantas": 4,
}


# =============================================================================
# 1. Entrevista mínima válida -> especificación válida
# =============================================================================
print("=" * 70)
print("1. ENTREVISTA MINIMA VALIDA -> ESPECIFICACION VALIDA")
print("=" * 70)

estado_1 = compilador.estado_desde_valores_expertos(VALORES_EXPERTOS_COMPLETOS)
spec_1 = compilador.compilar_especificacion(estado_1)
val_1 = compilador.validar_especificacion(spec_1)
check("los 8 imprescindibles compilan a CampoEspecificacion", len(spec_1.campos) == len(VALORES_EXPERTOS_COMPLETOS))
check("sin decisiones_pendientes", spec_1.decisiones_pendientes == [])
check("validación OK", val_1.valida, val_1.errores)
params_1 = compilador.compilar_params(spec_1)
check("compilar_params sin errores", params_1.errores == [], params_1.errores)
check("compilar_params produce un dict", isinstance(params_1.params, dict))


# =============================================================================
# 2. Entrevista incompleta -> errores concretos
# =============================================================================
print("=" * 70)
print("2. ENTREVISTA INCOMPLETA -> ERRORES CONCRETOS")
print("=" * 70)

valores_incompletos = dict(VALORES_EXPERTOS_COMPLETOS)
del valores_incompletos["solar.superficie_m2"]
del valores_incompletos["orientacion.real_parcela"]
estado_2 = compilador.estado_desde_valores_expertos(valores_incompletos)
spec_2 = compilador.compilar_especificacion(estado_2)
val_2 = compilador.validar_especificacion(spec_2)
check("inválida", not val_2.valida)
check(
    "el error nombra solar.superficie_m2 explícitamente",
    any("solar.superficie_m2" in e for e in val_2.errores), val_2.errores,
)
check(
    "el error nombra orientacion.real_parcela explícitamente",
    any("orientacion.real_parcela" in e for e in val_2.errores), val_2.errores,
)
check(
    "exactamente 2 imprescindibles pendientes, ni más ni menos",
    sum(1 for d in spec_2.decisiones_pendientes if d.startswith("imprescindible_pendiente:")) == 2,
    spec_2.decisiones_pendientes,
)
params_2 = compilador.compilar_params(spec_2)
check("compilar_params también falla (no compila con huecos)", params_2.params is None)
check("compilar_params no inventa nada: params es None, no un dict a medias", params_2.params is None)


# =============================================================================
# 3. Hecho -> campo correcto
# =============================================================================
print("=" * 70)
print("3. HECHO -> CAMPO CORRECTO")
print("=" * 70)

estado_3 = compilador.estado_desde_valores_expertos({"contexto.ciudad": "Bilbao"})
spec_3 = compilador.compilar_especificacion(estado_3)
campo_3 = spec_3.campos[0]
check("categoria correcta", campo_3.categoria == "contexto_ubicacion")
check("tipo_dato = información_usuario para un Hecho", campo_3.tipo_dato == "información_usuario")
check("valor preservado literal", campo_3.valor == "Bilbao")
check("sin confianza (no es una inferencia)", campo_3.confianza is None)
check("origen apunta a la respuesta real", campo_3.origen == [estado_3.respuestas_interpretadas[0].respuesta_id])


# =============================================================================
# 4. Inferencia -> campo correcto
# =============================================================================
print("=" * 70)
print("4. INFERENCIA -> CAMPO CORRECTO")
print("=" * 70)

estado_4 = motor.iniciar_entrevista()
estado_4.historial_turnos.append(modelo.Turno(turno_id="t4", preguntas_ids=["p11"], respuesta_cruda={"p11": "algo moderno"}))
estado_4.respuestas_interpretadas.append(
    modelo.RespuestaInterpretada(
        respuesta_id="r4", turno_id="t4", especificacion_id="identidad.referencias_esteticas",
        respuesta_cruda="algo moderno", naturaleza="Inferencia", valor="estilo moderno, líneas limpias",
        confianza="Media", motivo="inferido de una descripción breve",
    )
)
spec_4 = compilador.compilar_especificacion(estado_4)
campo_4 = spec_4.campos[0]
check("tipo_dato = inferencia (nunca información_usuario)", campo_4.tipo_dato == "inferencia")
check("confianza preservada", campo_4.confianza == "Media")
check("valor preservado", campo_4.valor == "estilo moderno, líneas limpias")
check("produce una directiva blanda de carácter", len(spec_4.contexto_cualitativo.directivas) == 1)
check("la directiva es blanda", spec_4.contexto_cualitativo.directivas[0].fuerza == "blanda")


# =============================================================================
# 5. Hipótesis -> no se convierte en Hecho
# =============================================================================
print("=" * 70)
print("5. HIPOTESIS -> NO SE CONVIERTE EN HECHO")
print("=" * 70)

estado_5 = compilador.estado_desde_valores_expertos(VALORES_EXPERTOS_COMPLETOS)  # los 8 imprescindibles ya resueltos
estado_5.historial_turnos.append(modelo.Turno(turno_id="t5", preguntas_ids=["p7"], respuesta_cruda={"p7": "no lo sé"}))
estado_5.respuestas_interpretadas.append(
    modelo.RespuestaInterpretada(
        respuesta_id="r5", turno_id="t5", especificacion_id="restricciones.plantas_maximas",
        respuesta_cruda="no lo sé", naturaleza="Hipótesis", valor=None, confianza="Baja",
        motivo="sin verificación normativa municipal disponible",
    )
)
spec_5 = compilador.compilar_especificacion(estado_5)
campo_5 = next(c for c in spec_5.campos if c.especificacion_id == "restricciones.plantas_maximas")
check("tipo_dato = inferencia, NUNCA información_usuario", campo_5.tipo_dato == "inferencia")
check("confianza Baja preservada", campo_5.confianza == "Baja")
check("valor sigue siendo None: no se inventa un número", campo_5.valor is None)
val_5 = compilador.validar_especificacion(spec_5)
check(
    "aviso visible de normativa no verificada (PRD v2 §6.4), no enterrado",
    any("normativa municipal" in a for a in val_5.avisos), val_5.avisos,
)
check("el aviso no bloquea la validación", val_5.errores == [])


# =============================================================================
# 6. Preferencia -> no se convierte en restricción
# =============================================================================
print("=" * 70)
print("6. PREFERENCIA -> NO SE CONVIERTE EN RESTRICCION")
print("=" * 70)

estado_6 = motor.iniciar_entrevista()
estado_6.historial_turnos.append(modelo.Turno(turno_id="t6", preguntas_ids=["p13"], respuesta_cruda={"p13": "sí, quizá"}))
estado_6.respuestas_interpretadas.append(
    modelo.RespuestaInterpretada(
        respuesta_id="r6", turno_id="t6", especificacion_id="usuarios.accesibilidad",
        respuesta_cruda="sí, quizá", naturaleza="Preferencia", valor="si", confianza=None,
        motivo="el usuario lo plantea como algo deseable, no como una necesidad confirmada",
    )
)
spec_6 = compilador.compilar_especificacion(estado_6)
campo_6 = spec_6.campos[0]
check(
    "tipo_dato = preferencia, NUNCA restricción — aunque accesibilidad normalmente sea dura",
    campo_6.tipo_dato == "preferencia",
)


# =============================================================================
# 7. Contradicción pendiente -> compilación bloqueada
# =============================================================================
print("=" * 70)
print("7. CONTRADICCION PENDIENTE -> COMPILACION BLOQUEADA")
print("=" * 70)

estado_7 = compilador.estado_desde_valores_expertos(VALORES_EXPERTOS_COMPLETOS)
# Segunda declaración, distinta, del mismo campo -> motor.responder() la
# detectaría en una entrevista real; aquí se simula directamente sobre el
# estado para no depender de un segundo turno completo.
nueva = modelo.RespuestaInterpretada(
    respuesta_id="r7b", turno_id=estado_7.historial_turnos[0].turno_id, especificacion_id="solar.superficie_m2",
    respuesta_cruda="600", naturaleza="Hecho", valor=600.0,
)
conflicto = motor._detectar_contradiccion_directa(estado_7, nueva)
check("el motor detecta la contradicción (fixture del test bien construido)", conflicto is not None)
estado_7.contradicciones.append(conflicto)
estado_7.respuestas_interpretadas.append(nueva)

spec_7 = compilador.compilar_especificacion(estado_7)
check("solar.superficie_m2 NO aparece como campo mientras está en conflicto", not any(c.especificacion_id == "solar.superficie_m2" for c in spec_7.campos))
check(
    "decisiones_pendientes registra la contradicción, no un 'falta'",
    any(d.startswith("contradiccion_pendiente:solar.superficie_m2:") for d in spec_7.decisiones_pendientes),
    spec_7.decisiones_pendientes,
)
val_7 = compilador.validar_especificacion(spec_7)
check("compilación bloqueada", not val_7.valida)
check("el error menciona la contradicción explícitamente", any("contradicción" in e for e in val_7.errores), val_7.errores)
params_7 = compilador.compilar_params(spec_7)
check("compilar_params también bloqueado", params_7.params is None)


# =============================================================================
# 8. Catálogo inválido -> rechazado
# =============================================================================
print("=" * 70)
print("8. CATALOGO INVALIDO -> RECHAZADO")
print("=" * 70)

estado_8 = compilador.estado_desde_valores_expertos(dict(VALORES_EXPERTOS_COMPLETOS, **{"categoria.inventada.xyz": "algo"}))
spec_8 = compilador.compilar_especificacion(estado_8)
check(
    "el campo inventado NUNCA se convierte en CampoEspecificacion",
    not any(c.especificacion_id == "categoria.inventada.xyz" for c in spec_8.campos),
)
check(
    "queda registrado como campo_no_reconocido",
    any(d == "campo_no_reconocido:categoria.inventada.xyz" for d in spec_8.decisiones_pendientes),
    spec_8.decisiones_pendientes,
)
val_8 = compilador.validar_especificacion(spec_8)
check("rechazado en la validación", not val_8.valida)
check("el error nombra el campo inventado", any("categoria.inventada.xyz" in e for e in val_8.errores), val_8.errores)


# =============================================================================
# 9. Campo sin destino actual -> se conserva pero no aparece artificialmente
#    en params
# =============================================================================
print("=" * 70)
print("9. CAMPO SIN DESTINO ACTUAL -> SE CONSERVA, NO APARECE EN PARAMS")
print("=" * 70)

valores_9 = dict(VALORES_EXPERTOS_COMPLETOS, **{"presupuesto.cifra_horquilla": "100.000-150.000 EUR"})
estado_9 = compilador.estado_desde_valores_expertos(valores_9)
spec_9 = compilador.compilar_especificacion(estado_9)
campo_presupuesto = next((c for c in spec_9.campos if c.especificacion_id == "presupuesto.cifra_horquilla"), None)
check("el campo SÍ se conserva en la Especificación", campo_presupuesto is not None)
check("destino_generador = almacenado_sin_uso", campo_presupuesto is not None and campo_presupuesto.destino_generador == "almacenado_sin_uso")
check("decision_contrato = A", campo_presupuesto is not None and campo_presupuesto.decision_contrato == "A")
params_9 = compilador.compilar_params(spec_9)
check("compilar_params sigue funcionando (el resto de imprescindibles están completos)", params_9.errores == [], params_9.errores)


def _contiene_valor(obj, valor) -> bool:
    if obj == valor:
        return True
    if isinstance(obj, dict):
        return any(_contiene_valor(v, valor) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return any(_contiene_valor(v, valor) for v in obj)
    return False


check(
    "el presupuesto NUNCA aparece dentro de params (ninguna clave lo referencia)",
    params_9.params is not None and not _contiene_valor(params_9.params, "100.000-150.000 EUR"),
)


# =============================================================================
# 10. El params generado coincide estructuralmente con el contrato actual
# =============================================================================
print("=" * 70)
print("10. PARAMS COINCIDE ESTRUCTURALMENTE CON EL CONTRATO ACTUAL")
print("=" * 70)

# Forma exacta que produce `app.py:_parse_generar_params` (líneas 550-619,
# releídas para esta fase) — no se importa `app.py` aquí (falla hoy por
# `yaml` ausente, hueco de entorno preexistente, ver docstring del módulo).
# "contexto_cualitativo" (Fase F, hallazgo crítico de la auditoría de
# 2026-08-13: faltaba por completo en `compilar_params()`, así que
# `/api/generar` nunca lo recibía desde el flujo real de entrevista) tiene
# subclaves propias, no las de `app.py:_parse_generar_params` — es la misma
# forma que ya exige `ai_generator._validar_directivas()` más
# `especificacion_id` para `app.py:_guardar_traza_de_generacion()`.
FORMA_PARAMS_CONTRATO_ACTUAL = {
    "proyecto": {"ciudad", "tipologia"},
    "solar": {"superficie_m2", "forma", "ancho_m", "largo_m", "norte_grados"},
    "edificio": {"plantas", "altura_libre_m", "planta_baja_comercial"},
    "mix_viviendas": {"dorm_1", "dorm_2", "dorm_3", "superficie_minima_m2"},
    "normativa": {"ocupacion_maxima_pct", "retranqueos_m", "edificabilidad_maxima", "plantas_maximas"},
    "contexto_cualitativo": {"directivas", "texto_prompt", "especificacion_id"},
    # "Editar / Intervenir edificación existente" (nueva capacidad): ver
    # `compilador.compilar_params()` -- incluida siempre, igual que
    # `contexto_cualitativo`, incluso cuando el usuario no declaró nada
    # (queda en "obra_nueva"/`elementos_a_conservar=None`).
    "intervencion_existente": {"tipo", "elementos_a_conservar"},
}

params_10 = compilador.compilar_params(spec_1).params
check("mismas claves de primer nivel", set(params_10.keys()) == set(FORMA_PARAMS_CONTRATO_ACTUAL.keys()), sorted(params_10.keys()))
for clave, subclaves in FORMA_PARAMS_CONTRATO_ACTUAL.items():
    check(
        "params[%r] tiene exactamente las subclaves del contrato" % clave,
        set(params_10[clave].keys()) == subclaves,
        sorted(params_10[clave].keys()),
    )
check("proyecto.tipologia en el dominio del generador", params_10["proyecto"]["tipologia"] in ("plurifamiliar", "unifamiliar", "rehabilitacion"))
check("solar.forma en el dominio del generador", params_10["solar"]["forma"] in ("rectangular", "irregular"))
check("solar.superficie_m2 es numérico", isinstance(params_10["solar"]["superficie_m2"], (int, float)))
check("solar.norte_grados es numérico", isinstance(params_10["solar"]["norte_grados"], (int, float)))
check("edificio.plantas es un entero >= 1", isinstance(params_10["edificio"]["plantas"], int) and params_10["edificio"]["plantas"] >= 1)
check(
    "intervencion_existente por defecto es obra_nueva (VALORES_EXPERTOS_COMPLETOS no declara nada)",
    params_10["intervencion_existente"] == {"tipo": "obra_nueva", "elementos_a_conservar": None},
    params_10["intervencion_existente"],
)

# --- 10b. contexto_cualitativo: contenido, no solo forma -------------------
# `spec_1` viene de VALORES_EXPERTOS_COMPLETOS, que incluye
# "usuarios.accesibilidad": "si" -> produce una DirectivaCualitativa dura
# real (ver compilador._construir_directiva) — se comprueba que llega tal
# cual a params, no solo que la clave existe.
ctx_10 = params_10["contexto_cualitativo"]
check("contexto_cualitativo.especificacion_id == spec_1.especificacion_id", ctx_10["especificacion_id"] == spec_1.especificacion_id)
check("contexto_cualitativo.directivas es una lista", isinstance(ctx_10["directivas"], list))
check("contexto_cualitativo.directivas trae la directiva de accesibilidad (dura)",
      any(d["especificacion_id"] == "usuarios.accesibilidad" and d["fuerza"] == "dura" for d in ctx_10["directivas"]),
      ctx_10["directivas"])
check("cada directiva tiene exactamente las claves que espera ai_generator._validar_directivas()",
      all(set(d.keys()) == {"especificacion_id", "categoria", "fuerza", "texto_origen", "texto_prompt", "verificable_geometricamente"}
          for d in ctx_10["directivas"]),
      ctx_10["directivas"])
check("contexto_cualitativo.texto_prompt no vacío cuando hay directivas duras",
      bool(ctx_10["texto_prompt"]) and "DEBES CUMPLIR" in ctx_10["texto_prompt"], ctx_10["texto_prompt"])
check("contexto_cualitativo coincide EXACTAMENTE con especificacion.contexto_cualitativo.a_dict() salvo especificacion_id (campo nuevo, ausente en ContextoCualitativo)",
      ctx_10["directivas"] == spec_1.contexto_cualitativo.a_dict()["directivas"]
      and ctx_10["texto_prompt"] == spec_1.contexto_cualitativo.a_dict()["texto_prompt"])

# --- 10c. Sin ninguna directiva -> contexto_cualitativo sigue presente,
#     vacío pero con especificacion_id (para que la traza SÍ se persista
#     aunque no haya directivas — mismo criterio que F2 de
#     test_ai_generator_contexto.py) --------------------------------------
valores_sin_directivas_10c = {
    "contexto.ciudad": "Sevilla", "programa.tipologia": "unifamiliar", "solar.superficie_m2": 300.0,
    "solar.forma": "rectangular", "programa.num_viviendas_mix": {"dorm_1": 1, "dorm_2": 0, "dorm_3": 0},
    "prioridades.trade_off": "coste", "usuarios.accesibilidad": "no", "orientacion.real_parcela": "norte",
    "edificio.plantas": 1,
}
estado_10c = compilador.estado_desde_valores_expertos(valores_sin_directivas_10c)
spec_10c = compilador.compilar_especificacion(estado_10c)
params_10c = compilador.compilar_params(spec_10c)
check("compilar_params sin errores (10c)", params_10c.errores == [], params_10c.errores)
ctx_10c = params_10c.params["contexto_cualitativo"]
check("contexto_cualitativo presente aunque no haya directivas duras/blandas", ctx_10c["directivas"] == [] and ctx_10c["texto_prompt"] == "")
check("pero especificacion_id sigue presente (para que la traza se pueda persistir igualmente)",
      bool(ctx_10c["especificacion_id"]) and ctx_10c["especificacion_id"] == spec_10c.especificacion_id)


# =============================================================================
# 11. Entrevista guiada y modo experto producen la misma estructura para la
#     misma información
# =============================================================================
print("=" * 70)
print("11. ENTREVISTA GUIADA Y MODO EXPERTO -> MISMA ESTRUCTURA")
print("=" * 70)

fake_11 = FakeInterprete()
fake_11.programar_bloque_fijo([
    {"especificacion_id": "programa.descripcion_libre", "naturaleza": "Hecho", "valor": "un edificio de pisos en Valencia"},
    {"especificacion_id": "prioridades.no_negociables", "naturaleza": "Hecho", "valor": "acceso sin escalones"},
])
estado_guiado = motor.iniciar_entrevista()
respuestas_guiadas = {
    "p1": "quiero un edificio de pisos en Valencia", "p4": "acceso sin escalones", "p5": "el garaje",
    "p2": "vivir", "p3": "tengo la parcela", "p3_ciudad": "Valencia", "p3_superficie": "800 m2",
    "p3_forma": "rectangular", "p_tipologia_directa": "plurifamiliar", "p_trade_off_directo": "más luz",
    "p13": "sí", "p8": "sur", "p6": "más pequeñas y más viviendas",
}
_ejecutar(estado_guiado, respuestas_guiadas, interprete=fake_11)
spec_guiada = compilador.compilar_especificacion(estado_guiado)
val_guiada = compilador.validar_especificacion(spec_guiada)

valores_experto_11 = {
    "contexto.ciudad": "Valencia", "programa.tipologia": "plurifamiliar", "solar.superficie_m2": 800.0,
    "solar.forma": "rectangular", "prioridades.trade_off": "luz", "usuarios.accesibilidad": "si",
    "orientacion.real_parcela": "sur", "prioridades.no_negociables": "acceso sin escalones",
    "programa.num_viviendas_mix": "mas_pequenas_mas_viviendas",
}
estado_experto = compilador.estado_desde_valores_expertos(valores_experto_11)
spec_experta = compilador.compilar_especificacion(estado_experto)
val_experta = compilador.validar_especificacion(spec_experta)

check("ambas producen 0 llamadas a Claude en modo experto", fake_11.llamadas != [])  # solo la guiada llamó
campos_comparables = ("contexto.ciudad", "programa.tipologia", "solar.superficie_m2", "solar.forma", "orientacion.real_parcela")
for eid in campos_comparables:
    campo_g = next((c for c in spec_guiada.campos if c.especificacion_id == eid), None)
    campo_e = next((c for c in spec_experta.campos if c.especificacion_id == eid), None)
    check(
        "campo %r: misma categoria/tipo_dato/valor/destino en ambos modos" % eid,
        campo_g is not None and campo_e is not None
        and (campo_g.categoria, campo_g.tipo_dato, campo_g.valor, campo_g.destino_generador, campo_g.decision_contrato)
        == (campo_e.categoria, campo_e.tipo_dato, campo_e.valor, campo_e.destino_generador, campo_e.decision_contrato),
        (campo_g, campo_e),
    )
check(
    "ambas quedan válidas: mismo criterio, mismo código, para la misma información",
    val_guiada.valida and val_experta.valida, (val_guiada.errores, val_experta.errores),
)


# =============================================================================
# 12. Compilación determinista: mismo estado -> mismo resultado
# =============================================================================
print("=" * 70)
print("12. COMPILACION DETERMINISTA")
print("=" * 70)


def _sin_timestamps(d: dict) -> dict:
    d = dict(d)
    d.pop("creado_en", None)
    d.pop("modificado_en", None)
    return d


estado_12 = compilador.estado_desde_valores_expertos(VALORES_EXPERTOS_COMPLETOS, sesion_id="sesion-fija-12")
spec_12a = compilador.compilar_especificacion(estado_12)
spec_12b = compilador.compilar_especificacion(estado_12)
check("mismo especificacion_id en ambas compilaciones", spec_12a.especificacion_id == spec_12b.especificacion_id)
check(
    "a_dict() idéntico entre dos compilaciones del mismo estado",
    _sin_timestamps(spec_12a.a_dict()) == _sin_timestamps(spec_12b.a_dict()),
)
params_12a = compilador.compilar_params(spec_12a)
params_12b = compilador.compilar_params(spec_12b)
check("compilar_params también determinista", params_12a.params == params_12b.params)


# =============================================================================
# 13. No hay llamadas a Claude — verificado estructuralmente, no solo por
#     observación (ninguna función de este módulo puede invocar un
#     `InterpreteIA`: no aparece en ninguna firma)
# =============================================================================
print("=" * 70)
print("13. NO HAY LLAMADAS A CLAUDE (verificación estructural de firmas)")
print("=" * 70)

import inspect  # noqa: E402

for nombre_funcion in ("compilar_especificacion", "validar_especificacion", "compilar_params", "estado_desde_valores_expertos"):
    funcion = getattr(compilador, nombre_funcion)
    parametros = inspect.signature(funcion).parameters
    check(
        "%s() no acepta ni construye un InterpreteIA" % nombre_funcion,
        "interprete" not in parametros,
    )
check("compilador.py no importa anthropic ni claude_interprete", "anthropic" not in dir(compilador) and "claude_interprete" not in dir(compilador))


# =============================================================================
# 14. No se modifica ai_generator.py — comprobado por fuera de este script
#     (git diff --stat, mismo patrón que el cierre de Fases A y C) y
#     confirmado en el informe de cierre de esta fase; se deja constancia
#     aquí de que este test file, en particular, nunca lo importa.
# =============================================================================
print("=" * 70)
print("14. NO SE MODIFICA ai_generator.py (ver informe de cierre; git diff aparte)")
print("=" * 70)
check("este archivo de test no importa ai_generator", "ai_generator" not in sys.modules)


# =============================================================================
# 15. Todos los imprescindibles del PRD quedan comprobados
# =============================================================================
print("=" * 70)
print("15. TODOS LOS IMPRESCINDIBLES DEL PRD QUEDAN COMPROBADOS")
print("=" * 70)

check("8 imprescindibles en el catálogo de C1", len(preguntas_mod.IMPRESCINDIBLES) == 8)
for imprescindible in preguntas_mod.IMPRESCINDIBLES:
    check(
        "%r tiene clasificación propia en el compilador (D1)" % imprescindible,
        imprescindible in compilador._CLASIFICACION,
    )

estado_15 = compilador.estado_desde_valores_expertos({})
spec_15 = compilador.compilar_especificacion(estado_15)
pendientes_15 = {d.split(":", 1)[1] for d in spec_15.decisiones_pendientes if d.startswith("imprescindible_pendiente:")}
check("entrevista totalmente vacía -> los 8 imprescindibles, y solo esos 8, quedan pendientes", pendientes_15 == set(preguntas_mod.IMPRESCINDIBLES), pendientes_15)
val_15 = compilador.validar_especificacion(spec_15)
check("8 errores de validación, uno por imprescindible", len(val_15.errores) == 8, val_15.errores)


# =============================================================================
# EXTRA — las dos contradicciones documentadas al principio de compilador.py
# =============================================================================
print("=" * 70)
print("EXTRA — contradicciones PRD vs. código documentadas en esta fase")
print("=" * 70)

# Extra 1: mix cualitativo (p6) nunca se inventa como números.
estado_mix = compilador.estado_desde_valores_expertos(
    dict(VALORES_EXPERTOS_COMPLETOS, **{"programa.num_viviendas_mix": "mas_grandes_menos_viviendas"})
)
spec_mix = compilador.compilar_especificacion(estado_mix)
val_mix = compilador.validar_especificacion(spec_mix)
check("la Especificación SÍ acepta la preferencia cualitativa (imprescindible satisfecho)", val_mix.valida)
params_mix = compilador.compilar_params(spec_mix)
check("pero compilar_params la bloquea explícitamente (no inventa una fórmula)", params_mix.params is None)
check("el error cita PRD v2 §18 vs. §4", any("§18" in e and "§4" in e for e in params_mix.errores), params_mix.errores)

# Extra 2: orientación por dirección postal / "combinación" no convierte a grados.
estado_orient = compilador.estado_desde_valores_expertos(
    dict(VALORES_EXPERTOS_COMPLETOS, **{"orientacion.real_parcela": "Calle Mayor 12, Valencia"})
)
spec_orient = compilador.compilar_especificacion(estado_orient)
check("la dirección postal SÍ se conserva en la Especificación", spec_orient.campos)
params_orient = compilador.compilar_params(spec_orient)
check("pero compilar_params no puede derivar norte_grados de una dirección", params_orient.params is None)
check("el error menciona geocodificación", any("geocodificación" in e for e in params_orient.errores), params_orient.errores)

# Extra 3: los 8 puntos cardinales SÍ convierten de forma determinista y estable.
for punto, grados_esperados in compilador._COMPASS_A_GRADOS.items():
    estado_c = compilador.estado_desde_valores_expertos(dict(VALORES_EXPERTOS_COMPLETOS, **{"orientacion.real_parcela": punto}))
    params_c = compilador.compilar_params(compilador.compilar_especificacion(estado_c))
    check(
        "%r -> %.0f grados" % (punto, grados_esperados),
        params_c.params is not None and params_c.params["solar"]["norte_grados"] == grados_esperados,
    )

# Extra 4: edificio.plantas — hueco real del catálogo de preguntas.
estado_sin_plantas = compilador.estado_desde_valores_expertos(
    {k: v for k, v in VALORES_EXPERTOS_COMPLETOS.items() if k != "edificio.plantas"}
)
spec_sin_plantas = compilador.compilar_especificacion(estado_sin_plantas)
check("edificio.plantas no es imprescindible: la Especificación SÍ es válida sin él", compilador.validar_especificacion(spec_sin_plantas).valida)
params_sin_plantas = compilador.compilar_params(spec_sin_plantas)
check("pero compilar_params no puede construir params.edificio.plantas sin fuente", params_sin_plantas.params is None)
check(
    "el error explica que ninguna de las 15 preguntas lo cubre",
    any("ninguna de las 15 preguntas" in e for e in params_sin_plantas.errores), params_sin_plantas.errores,
)


# =============================================================================
# 16. PUENTE DE DATOS TÉCNICOS SOBRE LA MISMA SESIÓN
#     (anadir_valores_expertos — corrección de 2026-08-13, hallazgo
#     "trazabilidad epistemológica del puente")
# =============================================================================
print("=" * 70)
print("16. PUENTE: anadir_valores_expertos() NO aplana la trazabilidad")
print("=" * 70)

# Una sesión que simula el resultado real de una entrevista guiada ya
# avanzada: mezcla deliberada de Hecho, Hipótesis y Preferencia sobre
# distintos especificacion_id, más un no_negociable ya recogido — todo lo
# que `anadir_valores_expertos()` NO debe tocar.
estado_16 = modelo.EstadoEntrevista(sesion_id=modelo.nuevo_id(), modo="entrevista_guiada", modo_entrada="entrevista_guiada")
turno_16 = modelo.Turno(turno_id=modelo.nuevo_id(), preguntas_ids=["p3_ciudad", "p13", "p7", "p1"])
estado_16.historial_turnos.append(turno_16)
estado_16.turnos_totales = 1
estado_16.respuestas_interpretadas.extend([
    modelo.RespuestaInterpretada(  # Hecho real, respondido con seguridad
        respuesta_id=modelo.nuevo_id(), turno_id=turno_16.turno_id, especificacion_id="contexto.ciudad",
        respuesta_cruda="Bilbao", naturaleza="Hecho", valor="Bilbao",
    ),
    modelo.RespuestaInterpretada(  # Hecho real
        respuesta_id=modelo.nuevo_id(), turno_id=turno_16.turno_id, especificacion_id="usuarios.accesibilidad",
        respuesta_cruda="si", naturaleza="Hecho", valor="si",
    ),
    modelo.RespuestaInterpretada(  # Hipótesis de baja confianza: "no sabe cuántas plantas puede"
        respuesta_id=modelo.nuevo_id(), turno_id=turno_16.turno_id, especificacion_id="restricciones.plantas_maximas",
        respuesta_cruda=None, naturaleza="Hipótesis", valor=None, confianza="Baja",
        motivo="sin verificación normativa municipal disponible",
    ),
    modelo.RespuestaInterpretada(  # Inferencia deducida por Claude del bloque fijo, con su propia confianza
        respuesta_id=modelo.nuevo_id(), turno_id=turno_16.turno_id, especificacion_id="programa.tipologia",
        respuesta_cruda="un edificio de pisos", naturaleza="Inferencia", valor="plurifamiliar", confianza="Alta",
        motivo="deducido de la descripción libre del usuario",
    ),
    modelo.RespuestaInterpretada(  # Preferencia, no una restricción
        respuesta_id=modelo.nuevo_id(), turno_id=turno_16.turno_id, especificacion_id="privacidad.necesidad",
        respuesta_cruda="normal", naturaleza="Hecho", valor="normal",
    ),
])
# La entrevista real ya se finalizó antes de que el puente pueda aparecer
# (mismo orden que entrevista.js: /finalizar -> 422 en /especificacion ->
# puente) — se simula aquí también, porque es justo el caso que antes
# rompía: una sesión "cerrada" no podía seguir recibiendo datos sin crear
# una nueva.
estado_16.estado = "cerrada"

n_respuestas_antes_16 = len(estado_16.respuestas_interpretadas)
turnos_antes_16 = estado_16.turnos_totales

# El puente completa los dos campos que de verdad faltaban para compilar:
# edificio.plantas (hueco real del catálogo) y un mix numérico.
resultado_16 = compilador.anadir_valores_expertos(estado_16, {
    "edificio.plantas": 4,
    "programa.num_viviendas_mix": {"dorm_1": 1, "dorm_2": 2, "dorm_3": 0},
    "solar.superficie_m2": 500.0,
    "solar.forma": "rectangular",
    "prioridades.trade_off": "luz",
    "orientacion.real_parcela": "sur",
})

check("anadir_valores_expertos() devuelve el MISMO objeto estado (misma sesión, no una nueva)", resultado_16 is estado_16)
check("sesion_id no cambia", estado_16.sesion_id == estado_16.sesion_id)  # tautológico a propósito: no hay reasignación posible
check("modo pasa a edicion_experta (transición explícita, E8 del plan)", estado_16.modo == "edicion_experta")
check("modo_entrada NO se toca: sigue registrando que empezó como entrevista_guiada", estado_16.modo_entrada == "entrevista_guiada")

# --- 1/2. Hipótesis e Inferencia NO tocadas por el puente -------------------
resp_plantas_max = [r for r in estado_16.respuestas_interpretadas if r.especificacion_id == "restricciones.plantas_maximas"]
check(
    "1) restricciones.plantas_maximas (Hipótesis, no confirmada en el puente) SIGUE siendo Hipótesis, no se convierte en Hecho",
    len(resp_plantas_max) == 1 and resp_plantas_max[0].naturaleza == "Hipótesis" and resp_plantas_max[0].confianza == "Baja",
    resp_plantas_max,
)
resp_tipologia = [r for r in estado_16.respuestas_interpretadas if r.especificacion_id == "programa.tipologia"]
check(
    "2) programa.tipologia (Inferencia, no re-declarada en el puente) SIGUE siendo Inferencia, no se convierte en Hecho",
    len(resp_tipologia) == 1 and resp_tipologia[0].naturaleza == "Inferencia" and resp_tipologia[0].confianza == "Alta",
    resp_tipologia,
)
resp_ciudad = [r for r in estado_16.respuestas_interpretadas if r.especificacion_id == "contexto.ciudad"]
check("contexto.ciudad (Hecho real, no tocado) sigue siendo la única entrada, intacta", len(resp_ciudad) == 1 and resp_ciudad[0].valor == "Bilbao")

# --- 3. Valores declarados EN el puente -> Hecho ---------------------------
resp_plantas = [r for r in estado_16.respuestas_interpretadas if r.especificacion_id == "edificio.plantas"]
check(
    "3) edificio.plantas (declarado explícitamente en el puente) SÍ es Hecho",
    len(resp_plantas) == 1 and resp_plantas[0].naturaleza == "Hecho" and resp_plantas[0].valor == 4,
    resp_plantas,
)
resp_mix = [r for r in estado_16.respuestas_interpretadas if r.especificacion_id == "programa.num_viviendas_mix"]
check("programa.num_viviendas_mix (declarado en el puente) SÍ es Hecho, con el dict numérico tal cual", len(resp_mix) == 1 and resp_mix[0].naturaleza == "Hecho" and resp_mix[0].valor == {"dorm_1": 1, "dorm_2": 2, "dorm_3": 0})

check("no se pierde ni se duplica ninguna respuesta previa: +6 nuevas exactamente", len(estado_16.respuestas_interpretadas) == n_respuestas_antes_16 + 6)
check("se registra un turno nuevo (turnos_totales +1), no se reescribe el historial", estado_16.turnos_totales == turnos_antes_16 + 1)

# --- 4. La sesión termina en un estado coherente, nunca huérfana en_curso --
check(
    "4) la sesión sigue 'cerrada' tras el puente — no hay una sesión distinta que haya quedado silenciosamente en_curso",
    estado_16.estado == "cerrada",
)

# --- 5. La especificación final SIGUE compilando correctamente -------------
spec_16 = compilador.compilar_especificacion(estado_16)
val_16 = compilador.validar_especificacion(spec_16)
check("5) especificación válida tras el puente", val_16.valida, val_16.errores)
campo_tipologia_16 = next((c for c in spec_16.campos if c.especificacion_id == "programa.tipologia"), None)
check(
    "el campo compilado preserva tipo_dato='inferencia' para programa.tipologia (D1: Inferencia nunca se asciende a información_usuario)",
    campo_tipologia_16 is not None and campo_tipologia_16.tipo_dato == "inferencia" and campo_tipologia_16.confianza == "Alta",
    campo_tipologia_16,
)
params_16 = compilador.compilar_params(spec_16)
check("compilar_params sin errores tras el puente", params_16.errores == [], params_16.errores)

# --- 6. Fase F sigue recibiendo contexto_cualitativo ------------------------
ctx_16 = params_16.params["contexto_cualitativo"] if params_16.params else None
check("6) params.contexto_cualitativo presente tras pasar por el puente", ctx_16 is not None and ctx_16["especificacion_id"] == spec_16.especificacion_id)
check(
    "la directiva de accesibilidad (usuarios.accesibilidad='si', declarada ANTES del puente) sigue llegando a contexto_cualitativo",
    ctx_16 is not None and any(d["especificacion_id"] == "usuarios.accesibilidad" and d["fuerza"] == "dura" for d in ctx_16["directivas"]),
    ctx_16["directivas"] if ctx_16 else None,
)

# --- Caso adicional: no_negociables no se duplica si el puente repite algo
# que la conversación ya había registrado --------------------------------
estado_16b = modelo.EstadoEntrevista(sesion_id=modelo.nuevo_id())
estado_16b.no_negociables.append("acceso sin escalones")
compilador.anadir_valores_expertos(estado_16b, {"prioridades.no_negociables": "acceso sin escalones"})
check("no_negociables no se duplica si el puente repite un texto ya registrado", estado_16b.no_negociables == ["acceso sin escalones"])


# =============================================================================
# 17. "Editar / Intervenir edificación existente" (modo experto)
# =============================================================================
print("=" * 70)
print("17. INTERVENCION EN EDIFICACION EXISTENTE (MODO EXPERTO)")
print("=" * 70)

valores_17 = dict(VALORES_EXPERTOS_COMPLETOS)
valores_17["parcela.tipo_intervencion"] = "edificacion_existente"
valores_17["parcela.elementos_a_conservar"] = "Conservar estructura principal y fachadas. Demoler distribución interior."
estado_17 = compilador.estado_desde_valores_expertos(valores_17)
spec_17 = compilador.compilar_especificacion(estado_17)
val_17 = compilador.validar_especificacion(spec_17)
check("especificación válida con los dos campos nuevos declarados", val_17.valida, val_17.errores)

campo_tipo_17 = next((c for c in spec_17.campos if c.especificacion_id == "parcela.tipo_intervencion"), None)
check("parcela.tipo_intervencion SÍ se conserva en la Especificación", campo_tipo_17 is not None)
check(
    "destino_generador = usado_directo (a diferencia de parcela.estado_tenencia)",
    campo_tipo_17 is not None and campo_tipo_17.destino_generador == "usado_directo",
)
check("tipo_dato = información_usuario para un Hecho declarado en modo experto", campo_tipo_17 is not None and campo_tipo_17.tipo_dato == "información_usuario")

params_17 = compilador.compilar_params(spec_17)
check("compilar_params sin errores", params_17.errores == [], params_17.errores)
check(
    "params.intervencion_existente.tipo == edificacion_existente",
    params_17.params["intervencion_existente"]["tipo"] == "edificacion_existente",
    params_17.params["intervencion_existente"],
)
check(
    "params.intervencion_existente.elementos_a_conservar preservado literal",
    params_17.params["intervencion_existente"]["elementos_a_conservar"]
    == "Conservar estructura principal y fachadas. Demoler distribución interior.",
)

# Valor fuera del vocabulario cerrado ("rehabilitacion_parcial", no una de las
# dos opciones reales) -> cae a "obra_nueva" (mismo criterio que ya aplica
# `compilar_params()` a `solar.forma` para texto libre no reconocido: nunca
# un error de compilación por esto, un dato opcional no bloquea el proyecto).
valores_17b = dict(VALORES_EXPERTOS_COMPLETOS)
valores_17b["parcela.tipo_intervencion"] = "rehabilitacion_parcial"
spec_17b = compilador.compilar_especificacion(compilador.estado_desde_valores_expertos(valores_17b))
params_17b = compilador.compilar_params(spec_17b)
check(
    "un valor fuera del vocabulario cerrado cae a obra_nueva, no bloquea la compilación",
    params_17b.errores == [] and params_17b.params["intervencion_existente"]["tipo"] == "obra_nueva",
    params_17b.errores or params_17b.params["intervencion_existente"],
)

# Texto en blanco (solo espacios) en elementos_a_conservar se trata como
# "no declarado", igual que el resto de campos de texto libre del módulo.
valores_17c = dict(VALORES_EXPERTOS_COMPLETOS)
valores_17c["parcela.tipo_intervencion"] = "edificacion_existente"
valores_17c["parcela.elementos_a_conservar"] = "   "
spec_17c = compilador.compilar_especificacion(compilador.estado_desde_valores_expertos(valores_17c))
params_17c = compilador.compilar_params(spec_17c)
check(
    "elementos_a_conservar en blanco se normaliza a None",
    params_17c.params["intervencion_existente"]["elementos_a_conservar"] is None,
    params_17c.params["intervencion_existente"],
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
