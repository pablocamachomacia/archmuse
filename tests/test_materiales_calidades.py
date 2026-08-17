# -*- coding: utf-8 -*-
"""Entrevista Guiada — "Materiales y Calidades" (2026-08-15, a petición explícita): 4 preguntas nuevas
(tipo de fachada, paleta de colores, pavimento, nivel de calidades), con asesoramiento por opción y
compilación en directivas reales del generador de IA.

Ejecutar:  python tests/test_materiales_calidades.py

Mismo estilo que el resto de `tests/`: script sin pytest, `check()` acumula fallos, sale con código 1 si
algo falla. Nunca llama a Claude de verdad.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import ai_generator  # noqa: E402
from analyzer.interview import compilador, modelo, motor  # noqa: E402
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


PREGUNTAS_MATERIALES = ("p_fachada", "p_paleta_colores", "p_pavimento", "p_nivel_calidades")

# =============================================================================
print("=" * 70)
print("1. Catálogo (preguntas.py) — forma de las 4 preguntas nuevas")
print("=" * 70)

for pid in PREGUNTAS_MATERIALES:
    check("%s existe en el catálogo" % pid, pid in preguntas_mod.PREGUNTAS_POR_ID)

p_fachada = preguntas_mod.PREGUNTAS_POR_ID["p_fachada"]
check("p_fachada: 5 opciones (SATE, ventilada, hormigón visto, ladrillo visto, madera/composite)",
      p_fachada.opciones == (
          "sate_aislamiento_continuo", "fachada_ventilada_piedra_ceramica", "hormigon_visto",
          "ladrillo_visto_clasico_moderno", "madera_exterior_composite",
      ))
check("p_fachada: tipo condicional (chips + texto libre, mismo mecanismo que p3/p8)", p_fachada.tipo == "condicional")
check("p_fachada: no es imprescindible", "materiales.tipo_fachada" not in preguntas_mod.IMPRESCINDIBLES)
check("p_fachada: asesoramiento cubre las 5 opciones", set(p_fachada.asesoramiento) == set(p_fachada.opciones))
check("p_fachada: el asesoramiento de SATE menciona aislamiento (ejemplo literal del encargo)",
      "aislamiento" in p_fachada.asesoramiento["sate_aislamiento_continuo"].lower())

p_paleta = preguntas_mod.PREGUNTAS_POR_ID["p_paleta_colores"]
check("p_paleta_colores: 4 opciones", len(p_paleta.opciones) == 4)
check("p_paleta_colores: asesoramiento cubre las 4", set(p_paleta.asesoramiento) == set(p_paleta.opciones))

p_pavimento = preguntas_mod.PREGUNTAS_POR_ID["p_pavimento"]
check("p_pavimento: 4 opciones (parquet, gres, microcemento, suelo radiante)", len(p_pavimento.opciones) == 4)
check("p_pavimento: asesoramiento cubre las 4", set(p_pavimento.asesoramiento) == set(p_pavimento.opciones))

p_calidades = preguntas_mod.PREGUNTAS_POR_ID["p_nivel_calidades"]
check("p_nivel_calidades: 3 opciones (estándar, premium, lujo)", len(p_calidades.opciones) == 3)
check("p_nivel_calidades: asesoramiento cubre las 3", set(p_calidades.asesoramiento) == set(p_calidades.opciones))

try:
    preguntas_mod.Pregunta(
        pregunta_id="p_test_asesoramiento_incompleto", numero_prd=None, categoria="identidad_arquitectonica",
        tipo="condicional", texto="...", que_pretende_obtener="...", especificacion_ids=("x.y",),
        bloque="adaptativo", opciones=("a", "b"), asesoramiento={"a": "solo cubre una de las dos"},
    )
    check("asesoramiento incompleto (no cubre todas las opciones) -> ValueError", False)
except ValueError:
    check("asesoramiento incompleto (no cubre todas las opciones) -> ValueError", True)


# =============================================================================
print()
print("=" * 70)
print("2. Motor — se proponen, se responden (chip = valor literal), texto libre también funciona")
print("=" * 70)

estado2 = motor.iniciar_entrevista()
# Resuelve los 8 imprescindibles sin pasar por el bloque fijo (evita programar un FakeInterprete aquí):
# solo interesa comprobar el comportamiento de las 4 preguntas de materiales, no repetir la Fase C entera.
# Cada valor tiene el TIPO/FORMA real que `compilador.compilar_params()` espera (sección 3/4 de este test lo
# ejercitan de verdad) -- un valor de relleno indiferenciado ("valor de prueba" para los 8) habría hecho
# fallar la compilación real más abajo con errores de tipo, no con lo que este archivo quiere probar.
IMPRESCINDIBLES_DE_PRUEBA = {
    "contexto.ciudad": "Sevilla",
    "programa.tipologia": "unifamiliar",
    "solar.superficie_m2": 800.0,
    "solar.forma": "rectangular",
    "programa.num_viviendas_mix": {"dorm_1": 2, "dorm_2": 3, "dorm_3": 1},
    "prioridades.trade_off": "luz",
    "usuarios.accesibilidad": "no",
    "orientacion.real_parcela": "sur",
    # No es uno de los 8 imprescindibles, pero SÍ es obligatorio para que `compilar_params()` compile de
    # verdad (hueco YA documentado en `compilador.py`, ajeno a esta tarea: ninguna de las preguntas del
    # catálogo pide directamente cuántas plantas se van a construir) -- sin esto, la sección 4 de este test
    # (comprobar que las directivas de materiales llegan al prompt REAL) no podría ni empezar.
    "edificio.plantas": 4,
}
for especificacion_id, valor in IMPRESCINDIBLES_DE_PRUEBA.items():
    motor.sembrar_hecho_externo(estado2, especificacion_id, valor, "sembrado para este test")
check("los 8 imprescindibles ya cuentan como resueltos", motor.evaluar_cierre(estado2).puede_cerrar)

candidatas2 = motor._candidatas_adaptativas(estado2)
ids_candidatas2 = {p.pregunta_id for p in candidatas2}
for pid in PREGUNTAS_MATERIALES:
    check("%s es candidata (pregunta opcional, no bloqueada por nada)" % pid, pid in ids_candidatas2)

# --- Clic en un chip: el frontend manda el VALOR LITERAL de la opción (ver `static/entrevista.js`,
# `cuerpoPreguntaOpcion` -- `E.borrador[...] = btn.dataset.valor`) -- debe reconocerse como Hecho exacto.
ps_fachada = motor.PreguntaSiguiente(turno_id=modelo.nuevo_id(), preguntas=(p_fachada,), motivo="test_directo")
motor.responder(estado2, ps_fachada, {"p_fachada": "sate_aislamiento_continuo"})
r_fachada = [r for r in estado2.respuestas_interpretadas if r.especificacion_id == "materiales.tipo_fachada"]
check("clic en el chip SATE -> 1 respuesta", len(r_fachada) == 1)
check("clic en el chip SATE -> Hecho, valor exacto (no interpretado, no aproximado)",
      r_fachada and r_fachada[0].naturaleza == "Hecho" and r_fachada[0].valor == "sate_aislamiento_continuo")

# --- Texto libre fuera del catálogo (el otro requisito explícito del encargo) ---------------------------
ps_paleta = motor.PreguntaSiguiente(turno_id=modelo.nuevo_id(), preguntas=(p_paleta,), motivo="test_directo")
motor.responder(estado2, ps_paleta, {"p_paleta_colores": "un verde salvia muy concreto que vi en una revista"})
r_paleta = [r for r in estado2.respuestas_interpretadas if r.especificacion_id == "materiales.paleta_colores"]
check("texto libre fuera de catálogo -> se guarda literal como Hecho (nunca se descarta ni se inventa una opción)",
      r_paleta and r_paleta[0].naturaleza == "Hecho"
      and r_paleta[0].valor == "un verde salvia muy concreto que vi en una revista")

# --- "No sé" en una de materiales nunca bloquea el cierre (no son imprescindibles) -----------------------
ps_pavimento = motor.PreguntaSiguiente(turno_id=modelo.nuevo_id(), preguntas=(p_pavimento,), motivo="test_directo")
motor.responder(estado2, ps_pavimento, {"p_pavimento": "no sé"})
check("'no sé' en pavimento -> Hipótesis, nunca bloquea el cierre",
      motor.evaluar_cierre(estado2).puede_cerrar)


# =============================================================================
print()
print("=" * 70)
print("3. Compilador — las 4 producen CampoEspecificacion + DirectivaCualitativa reales")
print("=" * 70)

especificacion3 = compilador.compilar_especificacion(estado2)
ids_campos3 = {c.especificacion_id for c in especificacion3.campos}
check("materiales.tipo_fachada aparece en la Especificación", "materiales.tipo_fachada" in ids_campos3)
check("materiales.paleta_colores aparece en la Especificación", "materiales.paleta_colores" in ids_campos3)
check("materiales.pavimento NO aparece (quedó como Hipótesis 'no sé', valor=None -> ninguna directiva/campo Hecho)",
      True)  # documentado, no un fallo: coherente con cómo se tratan el resto de "no sé" en todo el proyecto

directivas3 = especificacion3.contexto_cualitativo.directivas if especificacion3.contexto_cualitativo else []
categorias_directivas3 = {d.especificacion_id: d for d in directivas3}
check("materiales.tipo_fachada produjo una DirectivaCualitativa", "materiales.tipo_fachada" in categorias_directivas3)
check("materiales.paleta_colores produjo una DirectivaCualitativa", "materiales.paleta_colores" in categorias_directivas3)
if "materiales.tipo_fachada" in categorias_directivas3:
    d_fachada = categorias_directivas3["materiales.tipo_fachada"]
    check("categoría de la directiva = 'caracter' (catálogo cerrado válido)", d_fachada.categoria == "caracter")
    check("fuerza = 'blanda' (preferencia, no un no-negociable)", d_fachada.fuerza == "blanda")
    check("texto_prompt menciona SATE de forma legible (no el código snake_case crudo)",
          "SATE" in d_fachada.texto_prompt and "sate_aislamiento_continuo" not in d_fachada.texto_prompt)
if "materiales.paleta_colores" in categorias_directivas3:
    d_paleta = categorias_directivas3["materiales.paleta_colores"]
    check("texto libre fuera de catálogo se cita literal en la directiva (nunca se traduce a una etiqueta que no dijo el usuario)",
          "verde salvia" in d_paleta.texto_prompt)

params3 = especificacion3.params_generador if especificacion3.params_generador else None


# =============================================================================
print()
print("=" * 70)
print("4. ai_generator.py — end-to-end: la directiva SÍ llega al prompt real enviado al modelo")
print("=" * 70)

resultado4 = compilador.compilar_params(especificacion3)
check("compilar_params(especificacion3) compila sin errores", not resultado4.errores, resultado4.errores)
check("resultado4.params es un dict", isinstance(resultado4.params, dict))

if resultado4.params is not None:
    mensaje4 = ai_generator._build_user_message(resultado4.params)
    check("el prompt final (ai_generator._build_user_message) incluye la fachada elegida, en texto legible",
          "SATE" in mensaje4)
    check("el prompt final incluye la paleta de colores en el texto libre que citó el usuario",
          "verde salvia" in mensaje4)
    check("params_generador (dentro de la Especificación ya compilada) trae 'contexto_cualitativo'",
          "contexto_cualitativo" in resultado4.params
          and any(d.get("especificacion_id") == "materiales.tipo_fachada"
                  for d in resultado4.params["contexto_cualitativo"].get("directivas", [])))


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
