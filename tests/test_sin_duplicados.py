# -*- coding: utf-8 -*-
"""Un defecto, una incidencia. Y ninguna regla penaliza en secreto.

Ejecutar:  python tests/test_sin_duplicados.py

Rapido (<1 s): geometria sintetica.

Tres duplicaciones distintas, corregidas el 2026-08-05:

  A) ACCESIBILIDAD DE BANO -- tres reglas sobre el mismo objeto fisico
     (Bloque 8: rectangulo 1.2x1.8; Bloque 18a: lado corto >= 1.50 por CADA
     bano; Bloque 21: >= 3.60 m2 con giro 1.50) emitian tres CRITICOS
     separados. En VT1/3 de `ejemplo.dxf` salian dos sobre el mismo bano, y
     `compute_puntos_ganados` prometia +2.3 puntos por arreglar cada uno: el
     mismo defecto penalizado dos veces y la misma recompensa ofrecida dos
     veces. Ahora se miden las tres y se presenta una.

  B) HUECO DE ILUMINACION -- el Bloque 15b ("factor de luz natural", umbral
     1.5%) y el Bloque 19 ("regla 1/8", umbral 12.5%) calculaban LA MISMA
     expresion. Con valores reales entre el 5% y el 17%, el primero no podia
     fallar nunca y el segundo fallaba casi siempre. El vacuo aportaba ademas
     16 aprobados gratis a la puntuacion de cada analisis. Retirado.

  C) SUPERFICIE DE DORMITORIO -- la tabla `RULES` (D1>10, D2>8, D3>6) bajaba
     la nota sin emitir ninguna incidencia, mientras el Bloque 20 (minimo
     legal 6/10) declaraba que la misma pieza cumplia. Caso real: el
     Dormitorio 2 de VT3/3, 7.17 m2, fallaba la invisible y cumplia la
     visible. `RULES` deja de puntuar.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from shapely.geometry import Polygon  # noqa: E402

from analyzer.evaluator import (  # noqa: E402
    Unit,
    classify_problems,
    evaluate_advanced_for_units,
    evaluate_natural_lighting,
    score_unit,
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


def incidencias(unit):
    adv = evaluate_advanced_for_units([unit], rooms=unit.rooms)
    return adv, classify_problems(adv, fire_compartmentation=adv.fire_compartmentation)


print()
print("A. Un bano no accesible produce UNA incidencia, no tres")
print("-" * 66)

# Bano de 1.10 x 1.60 = 1.76 m2: falla los tres criterios a la vez.
mala = Unit(name="VT-BANO", rooms=[
    rect(0, 0, 5, 5, "Salón/cocina"),
    rect(5, 0, 6.10, 1.60, "Baño"),
    rect(5, 2, 8, 5, "Dormitorio 1"),
])
adv, issues = incidencias(mala)
banos = [i for i in issues if "baño" in i.titulo.lower() or "bano" in i.titulo.lower()]
check(len(banos) == 1, "una sola incidencia de bano", "%d incidencias: %s"
      % (len(banos), [i.titulo for i in banos]))
if banos:
    i = banos[0]
    check(i.severity == "CRITICO", "sigue siendo CRITICO", i.severity)
    # La descripcion tiene que enumerar los criterios que han fallado: se
    # unifica la presentacion, no se pierde informacion.
    check(";" in i.descripcion,
          "y enumera los criterios incumplidos, sin perder detalle",
          i.descripcion[:90])

# Las tres reglas SIGUEN midiendose: unificar la presentacion no es dejar de
# comprobar. Si alguien las borra, esto lo caza.
us = adv.unit_scores[0]
check(us.bathroom_accessibility_result is not None, "el Bloque 8 sigue evaluandose")
check(us.accessible_bathroom_area_result is not None, "el Bloque 21 sigue evaluandose")
check(len(us.bathroom_turning_space_results) == 1, "el Bloque 18a sigue evaluandose")

# Un bano correcto no genera ninguna: 2.00 x 2.00 = 4.00 m2.
buena = Unit(name="VT-OK", rooms=[
    rect(0, 0, 5, 5, "Salón/cocina"),
    rect(5, 0, 7, 2, "Baño"),
    rect(5, 2, 8, 5, "Dormitorio 1"),
])
_adv, issues_ok = incidencias(buena)
check(not any("baño" in i.titulo.lower() for i in issues_ok),
      "un bano de 2.00x2.00 no genera ninguna incidencia de accesibilidad")


print()
print("B. El hueco de iluminacion se comprueba en un solo sitio")
print("-" * 66)

analisis = evaluate_natural_lighting(buena)
check(analisis.factor_results == [],
      "el 'factor de luz natural' ya no produce resultados",
      "%d resultados" % len(analisis.factor_results))
check(len(analisis.depth_results) > 0,
      "pero la profundidad de habitacion se sigue midiendo",
      "%d resultados" % len(analisis.depth_results))

# Ninguna incidencia con ese titulo puede volver a aparecer.
_adv, issues_luz = incidencias(mala)
check(not any("factor de luz" in i.titulo.lower() for i in issues_luz),
      "no se emite ninguna incidencia de 'factor de luz natural'")

# Y la regla que si mide el hueco sigue viva.
us_mala = _adv.unit_scores[0]
check(len(us_mala.window_opening_results) > 0,
      "la regla 1/8 (Bloque 19) sigue evaluandose",
      "%d piezas" % len(us_mala.window_opening_results))


print()
print("C. Ninguna regla baja la nota sin explicarse")
print("-" * 66)

# El caso real de VT3/3: Dormitorio 2 de 7.17 m2. Falla la tabla RULES
# (minimo 8) y cumple el Bloque 20 (minimo legal 6). Antes, la vivienda
# perdia un punto que ninguna incidencia justificaba.
vt33 = Unit(name="VT3/3", rooms=[
    rect(0, 0, 5, 5, "Salón/cocina"),
    rect(5, 0, 8, 4.18, "Dormitorio 1"),          # 12.53 m2
    rect(5, 4.18, 7.61, 6.93, "Dormitorio 2"),    # 7.17 m2
    rect(0, 5, 2, 7, "Baño"),
])
us = score_unit(vt33, [], [], [])
basic_fallidos = [b for b in us.basic_results if not b.passed]
check(any(b.room_label == "Dormitorio 2" for b in basic_fallidos),
      "la tabla RULES sigue viendo que el Dormitorio 2 se queda corto",
      "%d fallos basicos" % len(basic_fallidos))

# ...pero ya no puntua. Se compara contra una vivienda identica con ese
# dormitorio agrandado: si RULES puntuara, las notas serian distintas.
vt33_grande = Unit(name="VT3/3b", rooms=[
    rect(0, 0, 5, 5, "Salón/cocina"),
    rect(5, 0, 8, 4.18, "Dormitorio 1"),
    rect(5, 4.18, 7.61, 7.63, "Dormitorio 2"),    # 9.0 m2, ya cumple RULES
    rect(0, 5, 2, 7, "Baño"),
])
us_grande = score_unit(vt33_grande, [], [], [])
check(len(us.basic_results) == len(us_grande.basic_results),
      "las dos viviendas tienen las mismas reglas basicas aplicables")
check(us.total_checks == us_grande.total_checks,
      "y el mismo numero de comprobaciones puntuables",
      "%d vs %d" % (us.total_checks, us_grande.total_checks))

# Toda comprobacion que baje la nota tiene que poder explicarse. Se verifica
# que el numero de fallos puntuables coincide con lo que el arquitecto puede
# llegar a leer, sin penalizaciones invisibles de RULES por medio.
fallos_puntuables = us.total_checks - us.passed_checks
_adv33, issues33 = incidencias(vt33)
check(fallos_puntuables <= len(issues33) + len(us.limitaciones),
      "no hay mas fallos puntuados que hallazgos explicables",
      "%d fallos vs %d incidencias + %d limitaciones"
      % (fallos_puntuables, len(issues33), len(us.limitaciones)))


print()
print("=" * 66)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
