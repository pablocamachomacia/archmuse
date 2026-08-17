# -*- coding: utf-8 -*-
""""Cumplimiento correcto" y "2 criticos" no pueden convivir en la pantalla.

Ejecutar:  python tests/test_severidad_veta_color.py

Rapido (<1 s).

Que protege:

`score_pct` es el porcentaje de comprobaciones superadas. Dos fallos entre 45
dan 95,6 y el color salia verde -- aunque los dos fallos fueran criticos. En
`ejemplo.dxf`, VT1/3 se presentaba literalmente como **"92 / Cumplimiento
correcto"** junto a **"2 criticas"** de accesibilidad.

Ningun arquitecto que firme un proyecto acepta eso, y tiene razon: un critico
es, por definicion, algo que puede bloquear el visado. Promediarlo con
cuarenta aciertos no lo hace menos bloqueante. El problema no era el numero:
era el veredicto que lo acompanaba.

Lo que este test NO cubre, y sigue pendiente: unificar los dos sistemas de
puntuacion que conviven en el proyecto (`evaluator.score_pct` y
`scoring.compute_scoring_breakdown`). Eso cambia los numeros de todos los
proyectos ya guardados y es una decision de producto, no una correccion. Esta
razonada en `docs/design/2026-08-02-dos-sistemas-de-puntuacion.md` y su
guardian es `tests/test_scoring_coherencia.py`, que sigue fallando a
proposito.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from shapely.geometry import Polygon  # noqa: E402

from analyzer.api_serializer import serialize_analysis  # noqa: E402
from analyzer.evaluator import (  # noqa: E402
    SCORE_GREEN_THRESHOLD,
    SCORE_YELLOW_THRESHOLD,
    Unit,
    evaluate_advanced_for_units,
    rating_con_severidad,
    score_rating,
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


print()
print("A. Un solo critico veta el verde, con la nota que sea")
print("-" * 64)

check(rating_con_severidad(100.0, 0) == "verde", "100 sin criticos: verde")
check(rating_con_severidad(100.0, 1) == "rojo",
      "100 CON un critico: rojo", rating_con_severidad(100.0, 1))
check(rating_con_severidad(92.0, 2) == "rojo",
      "el caso real de VT1/3 (92 y 2 criticos): rojo", rating_con_severidad(92.0, 2))
check(rating_con_severidad(80.0, 1) == "rojo", "80 con un critico: rojo tambien")

# Sin criticos, el comportamiento anterior se conserva intacto.
for pct in (100.0, SCORE_GREEN_THRESHOLD, 84.9, SCORE_YELLOW_THRESHOLD, 69.9, 0.0):
    check(rating_con_severidad(pct, 0) == score_rating(pct),
          "sin criticos, %.1f mantiene el color de siempre (%s)" % (pct, score_rating(pct)))


print()
print("B. El veto llega al JSON que consume la interfaz")
print("-" * 64)

# Vivienda con un bano inaccesible (critico) pero pocas comprobaciones
# fallidas: la nota sale alta y el color tiene que salir rojo igualmente.
mala = Unit(name="VT-CRIT", rooms=[
    rect(0, 0, 5, 5, "Salón/cocina"),
    rect(5, 0, 6.10, 1.60, "Baño"),
    rect(5, 2, 8, 5, "Dormitorio 1"),
    rect(5, 5, 8, 7, "Dormitorio 2"),
])
adv = evaluate_advanced_for_units([mala], rooms=mala.rooms)
pay = serialize_analysis(filename="t.dxf", rooms=mala.rooms, advanced=adv,
                         norte_grados=0.0, ai_analysis=None,
                         proyecto={"tipologia": "plurifamiliar", "zona_cte": "C"})
viv = pay["viviendas"][0]
criticos = pay["issues_summary"]["criticos"]
check(criticos > 0, "el caso de prueba tiene al menos un critico", "%d criticos" % criticos)
check(viv["valoracion"] == "rojo",
      "la vivienda se presenta en rojo",
      "puntuacion=%s valoracion=%s" % (viv["puntuacion"], viv["valoracion"]))
check(pay["valoracion_global"] == "rojo",
      "y el proyecto entero tambien",
      "global=%s con %d criticos" % (pay["valoracion_global"], criticos))

# La puntuacion NO se toca: sigue midiendo lo que media, para no invalidar
# el historico de proyectos guardados. Lo que cambia es el veredicto.
check(isinstance(viv["puntuacion"], int) and viv["puntuacion"] > 0,
      "la puntuacion numerica se conserva, no se hunde artificialmente",
      "%s puntos" % viv["puntuacion"])


print()
print("C. Una vivienda limpia sigue saliendo en verde")
print("-" * 64)

buena = Unit(name="VT-OK", rooms=[
    rect(0, 0, 5, 5, "Salón/cocina"),
    rect(5, 0, 7, 2, "Baño"),
    rect(5, 2.4, 8, 5.4, "Dormitorio 1"),
    rect(0, 5.4, 3, 8, "Dormitorio 2"),
    rect(3.2, 5.4, 4.7, 8, "Pasillo"),
])
adv_ok = evaluate_advanced_for_units([buena], rooms=buena.rooms)
pay_ok = serialize_analysis(filename="t.dxf", rooms=buena.rooms, advanced=adv_ok,
                            norte_grados=0.0, ai_analysis=None,
                            proyecto={"tipologia": "plurifamiliar", "zona_cte": "C"})
crit_ok = pay_ok["issues_summary"]["criticos"]
check(crit_ok == 0, "la vivienda de control no tiene criticos", "%d criticos" % crit_ok)
check(pay_ok["viviendas"][0]["valoracion"] != "rojo",
      "y por tanto no se la penaliza con el veto",
      "valoracion=%s" % pay_ok["viviendas"][0]["valoracion"])


print()
print("=" * 64)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
