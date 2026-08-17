# -*- coding: utf-8 -*-
"""Bloque B -- las 6 correcciones de veracidad de `docs/audits/DB-SI_REVIEW.md` §3.2.

Ejecutar:  python tests/test_bloque_b_veracidad.py

Rapido (<1 s): geometria sintetica y lectura directa del corpus, sin ejemplo.dxf.

Que protege, una seccion por correccion:

A. C01/R26 -- `evaluate_fire_compartmentation` deja de citar CTE-DB-SI-3 y de
   hablar de "sectorizacion de incendio": es integridad geometrica, no una
   comprobacion normativa (mismo principio que ya prueba
   `test_solape_interno.py` para el solape DENTRO de una vivienda).
B. C09/R17 -- `evaluate_evacuation_distance` deja de alimentar `classify_problems`,
   el `score_pct` de la vivienda (`score_unit`) y el resaltado de
   `plan_svg.room_problems`. El campo `passed` y el calculo de `distance_m` NO
   cambian (compatibilidad) -- solo dejan de leerse como veredicto en esos tres
   sitios.
C. C20/C25 -- el registro de la candidata en el corpus de extraccion queda
   corregido: `tipo`/`severidad_sugerida` dentro de sus catalogos cerrados
   (C20), y `parametros` vacio para un coeficiente de calculo que no es un
   umbral de proyecto (C25).

C10 y C12 no tienen seccion aqui: C10 es solo documentacion (nada que probar
en tiempo de ejecucion) y C12 es un cambio de texto en un aviso ya cubierto
por los tests existentes de `get_missing_data_warnings` si los hay -- no se
duplican aqui.
"""
import inspect
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from shapely.geometry import Polygon  # noqa: E402

from analyzer.evaluator import (  # noqa: E402
    MAX_EVACUATION_DISTANCE_M,
    Unit,
    classify_problems,
    evaluate_advanced_for_units,
    evaluate_evacuation_distance,
    evaluate_fire_compartmentation,
    score_unit,
)
from analyzer.parser import Room  # noqa: E402
from analyzer.plan_svg import room_problems  # noqa: E402

fallos = []
comprobaciones = 0


def check(ok, etiqueta, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s%s" % ("OK  " if ok else "FALLO", etiqueta, ("  -> " + detalle) if detalle else ""))
    if not ok:
        fallos.append(etiqueta)


def rect(x0, y0, x1, y1, label):
    return Room(label=label, polygon=Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]), layer="00 areas")


print()
print("A. C01/R26 -- solape entre viviendas, sin cita CTE")
print("-" * 64)

# Dos viviendas que comparten huella por completo (mismo patron de
# `test_solape_interno.py`, pero aqui SI son unidades distintas).
vt_a = Unit(name="VT-A", rooms=[rect(0, 0, 5, 5, "Salón/cocina")])
vt_b = Unit(name="VT-B", rooms=[rect(1, 1, 4, 4, "Salón/cocina")])

fc = evaluate_fire_compartmentation([vt_a, vt_b])
check(len(fc) == 1, "detecta el solape entre las dos viviendas", "%d hallazgos" % len(fc))
if fc:
    r = fc[0]
    check("CTE" not in r.message and "sectorizaci" not in r.message.lower(),
          "el mensaje del resultado no cita el CTE ni habla de sectorizacion", r.message)

adv_fc = evaluate_advanced_for_units([vt_a, vt_b], rooms=vt_a.rooms + vt_b.rooms)
issues_fc = classify_problems(adv_fc, fire_compartmentation=adv_fc.fire_compartmentation)
solapes = [i for i in issues_fc if "VT-A" in i.unit_name and "VT-B" in i.unit_name]
check(len(solapes) == 1, "classify_problems emite exactamente una incidencia", "%d" % len(solapes))
if solapes:
    i = solapes[0]
    check(i.codigo == "GEOMETRIA-SOLAPE-VIVIENDAS",
          "codigo GEOMETRIA-SOLAPE-VIVIENDAS, no CTE-DB-SI-3", i.codigo)
    check(not i.codigo.startswith("CTE"), "y no empieza por CTE", i.codigo)
    check("sectorizaci" not in i.titulo.lower(), "el titulo ya no habla de sectorizacion", i.titulo)
    check("sectorizaci" not in i.impacto.lower(), "el impacto ya no habla de sectorizacion", i.impacto)
    check(i.severity == "CRITICO", "conserva la severidad CRITICO", i.severity)


print()
print("B. C09/R17 -- recorrido interior sin veredicto")
print("-" * 64)

# Misma cadena que tests/test_evacuacion.py seccion C: recorrido > 25 m.
piezas = [rect(0, 0, 4, 4, "Pasillo")]
for i in range(1, 7):
    piezas.append(rect(i * 4, 0, i * 4 + 4, 4, "Distribuidor %d" % i))
piezas.append(rect(28, 0, 32, 4, "Dormitorio 3"))
larga = Unit(name="VT-LARGA", rooms=piezas)

res, motivo = evaluate_evacuation_distance(larga)
check(motivo is None, "sigue siendo evaluable")
peor = max((r.distance_m for r in res), default=0)
check(peor > MAX_EVACUATION_DISTANCE_M,
      "distance_m se sigue calculando igual que antes", "%.1f m" % peor)
check(any(not r.passed for r in res),
      "el campo passed se conserva por compatibilidad, con el mismo valor")
if res:
    m = res[0].message
    check("CTE" not in m, "el mensaje ya no cita el CTE", m)

check("ev.passed for ev in evacuation_distance_results" not in inspect.getsource(score_unit),
      "score_unit ya no mete ev.passed en la lista de checks (no entra en el score)")
check("for ev in unit_score.evacuation_distance_results" not in inspect.getsource(room_problems),
      "plan_svg.room_problems ya no itera evacuation_distance_results (no resalta el plano)")

adv_ev = evaluate_advanced_for_units([larga], rooms=larga.rooms)
issues_ev = classify_problems(adv_ev)
evac_issues = [i for i in issues_ev if i.unit_name == "VT-LARGA" and "vacuaci" in i.titulo.lower()]
check(evac_issues == [], "classify_problems ya no genera incidencia por el recorrido interior",
      "%d incidencias" % len(evac_issues))

us_larga = adv_ev.unit_scores[0]
problems = [p for room in larga.rooms for p in room_problems(room, us_larga)]
check(not any("recorrido" in p.lower() and "evacuaci" in p.lower() for p in problems),
      "plan_svg.room_problems ya no resalta ninguna pieza por el recorrido")


print()
print("C. C20/C25 -- registro del corpus, catalogos cerrados")
print("-" * 64)

_RUTA_CANDIDATAS = os.path.join(
    RAIZ, "extraccion", "estado", "candidatas",
    "codigotecnico__DB-SI__0a2e78cd6247.jsonl",
)
with open(_RUTA_CANDIDATAS, encoding="utf-8") as f:
    _lineas = f.readlines()

_TIPOS_CERRADOS = {
    "exigencia_cuantitativa", "exigencia_de_presencia", "exigencia_compuesta",
    "exigencia_cualitativa", "definicion", "remision", "procedimental",
}
_SEVERIDADES_CERRADAS = {"bloqueante", "riesgo_variable", "recomendable", "preferencial"}

c20 = json.loads(_lineas[19])
check(c20["articulo"] == "DB-SI 6.1 Generalidades", "linea 20 sigue siendo C20", c20["articulo"])
check(c20["tipo"] == "procedimental", "C20: tipo = procedimental", c20["tipo"])
check(c20["severidad_sugerida"] == "preferencial",
      "C20: severidad_sugerida = preferencial", c20["severidad_sugerida"])
check(c20["tipo"] in _TIPOS_CERRADOS, "C20: tipo dentro del catalogo cerrado de 7")
check(c20["severidad_sugerida"] in _SEVERIDADES_CERRADAS,
      "C20: severidad_sugerida dentro del catalogo cerrado de 4")

c25 = json.loads(_lineas[24])
check(c25["articulo"] == "DB-SI 6.6 Determinación de la resistencia al fuego",
      "linea 25 sigue siendo C25", c25["articulo"])
check(c25["parametros"] == [], "C25: parametros vacio (gamma_M,fi retirado)", c25["parametros"])
check(c25["tipo"] == "exigencia_compuesta", "C25: tipo NO se toca", c25["tipo"])


print()
print("=" * 64)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
