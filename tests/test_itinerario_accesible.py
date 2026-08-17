# -*- coding: utf-8 -*-
"""Un plano que no rotula el distribuidor no incumple accesibilidad.

Ejecutar:  python tests/test_itinerario_accesible.py

Rapido (<1 s): geometria sintetica.

Que protege:

Hasta 2026-08-05, R18c buscaba literalmente la palabra "PASILLO" en la
etiqueta y, si no encontraba ninguna pieza asi rotulada, devolvia
INCUMPLIMIENTO. En `ejemplo.dxf` no hay una sola pieza etiquetada "Pasillo"
-- el vocabulario del plano son ocho etiquetas y esa no esta -- asi que la
regla fallaba en las 6 viviendas de 6.

Seis incidencias IMPORTANTE, el 16% de todas las del proyecto, y ninguna
correspondia a un defecto real: se estaba convirtiendo la convencion de
rotulacion de un estudio ajeno en un incumplimiento de accesibilidad.

Es el mismo error que tenia R17 con signo contrario, y los dos son lo que
`docs/brain/INFERENCE_ENGINE.md` prohibe: sacar una conclusion NEGATIVA de un
dato AUSENTE en vez de declarar que no se sabe.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from shapely.geometry import Polygon  # noqa: E402

from analyzer.evaluator import (  # noqa: E402
    MIN_ITINERARIO_ACCESIBLE_M,
    Unit,
    classify_problems,
    evaluate_advanced_for_units,
    evaluate_itinerario_accesible,
)
from analyzer.parser import Room  # noqa: E402

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


def vivienda(nombre, *piezas):
    return Unit(name=nombre, rooms=list(piezas))


print()
print("A. Sin pieza de circulacion: NO EVALUABLE, no incumplimiento")
print("-" * 64)

# El caso de las 6 viviendas de ejemplo.dxf.
abierta = vivienda("VT-ABIERTA",
                   rect(0, 0, 5, 5, "Salón/cocina"),
                   rect(5, 0, 8, 3, "Dormitorio 1"))
res, motivo = evaluate_itinerario_accesible(abierta, "plurifamiliar")
check(res is None, "no se emite incumplimiento")
check(motivo is not None, "se declara que no es evaluable")
check(motivo and "no evaluable" in motivo, "con esas palabras", (motivo or "")[:70])
check(motivo and "1.2" in motivo, "y diciendo cual seria el minimo aplicable")


print()
print("B. El vocabulario de rotulacion no decide el cumplimiento")
print("-" * 64)

# Un distribuidor estrecho es un incumplimiento se llame como se llame.
for nombre in ("Pasillo", "Vestíbulo", "Distribuidor", "Recibidor", "Hall"):
    u = vivienda("VT-" + nombre,
                 rect(0, 0, 5, 5, "Salón/cocina"),
                 rect(5, 2, 9, 2.9, nombre))          # 0.90 m de ancho
    res, motivo = evaluate_itinerario_accesible(u, "plurifamiliar")
    check(res is not None and motivo is None,
          "'%s' estrecho se detecta como incumplimiento" % nombre)

# Y uno ancho cumple, igualmente con cualquier nombre.
for nombre in ("Pasillo", "Distribuidor"):
    u = vivienda("VT-OK-" + nombre,
                 rect(0, 0, 5, 5, "Salón/cocina"),
                 rect(5, 1, 9, 2.5, nombre))          # 1.50 m de ancho
    res, motivo = evaluate_itinerario_accesible(u, "plurifamiliar")
    check(res is None and motivo is None, "'%s' de 1.50 m cumple" % nombre)


print()
print("C. El umbral sigue siendo el umbral")
print("-" * 64)

justo = vivienda("VT-JUSTO",
                 rect(0, 0, 5, 5, "Salón/cocina"),
                 rect(5, 2, 9, 2 + MIN_ITINERARIO_ACCESIBLE_M, "Distribuidor"))
res, _ = evaluate_itinerario_accesible(justo, "plurifamiliar")
check(res is None, "exactamente %.2f m cumple" % MIN_ITINERARIO_ACCESIBLE_M)

corto = vivienda("VT-CORTO",
                 rect(0, 0, 5, 5, "Salón/cocina"),
                 rect(5, 2, 9, 2 + MIN_ITINERARIO_ACCESIBLE_M - 0.05, "Distribuidor"))
res, _ = evaluate_itinerario_accesible(corto, "plurifamiliar")
check(res is not None, "5 cm menos no cumple")

# Basta con que UNA pieza de circulacion sea suficientemente ancha.
mixto = vivienda("VT-MIXTO",
                 rect(0, 0, 5, 5, "Salón/cocina"),
                 rect(5, 2, 9, 2.9, "Pasillo"),        # estrecho
                 rect(5, 3, 9, 4.5, "Distribuidor"))   # ancho
res, _ = evaluate_itinerario_accesible(mixto, "plurifamiliar")
check(res is None, "con una sola pieza de circulacion suficiente, cumple")


print()
print("D. Tipologia: solo aplica a plurifamiliar")
print("-" * 64)

for tip in ("unifamiliar", "rehabilitacion"):
    res, motivo = evaluate_itinerario_accesible(abierta, tip)
    check(res is None and motivo is None,
          "en %s no aplica y tampoco genera limitacion" % tip)


print()
print("E. Se calcula UNA vez y los consumidores lo leen")
print("-" * 64)

# Antes se evaluaba dentro de classify_problems y otra vez en chain_effects.
adv = evaluate_advanced_for_units([abierta], rooms=abierta.rooms)
us = adv.unit_scores[0]
check(us.itinerario_accesible_result is None, "UnitScore guarda el resultado")
check(any("Itinerario accesible" in lim for lim in us.limitaciones),
      "y la limitacion, que es lo que vera el arquitecto",
      "%d limitaciones" % len(us.limitaciones))

issues = classify_problems(adv, fire_compartmentation=adv.fire_compartmentation)
itinerarios = [i for i in issues if "itinerario" in i.titulo.lower()]
check(itinerarios == [], "una vivienda de planta abierta no recibe la incidencia",
      "%d incidencias de itinerario" % len(itinerarios))

# Y la que si incumple, la sigue recibiendo.
adv2 = evaluate_advanced_for_units([corto], rooms=corto.rooms)
issues2 = classify_problems(adv2, fire_compartmentation=adv2.fire_compartmentation)
check(any("itinerario" in i.titulo.lower() for i in issues2),
      "una vivienda con distribuidor estrecho si la recibe")


print()
print("=" * 64)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
