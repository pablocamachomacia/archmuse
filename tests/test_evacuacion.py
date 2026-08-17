# -*- coding: utf-8 -*-
"""El recorrido de evacuacion tiene que ser un recorrido.

Ejecutar:  python tests/test_evacuacion.py

Rapido (<1 s): geometria sintetica.

Que protege:

Hasta 2026-08-05, R17 media `unit_boundary.distance(room.centroid)`: la
distancia del centroide de la pieza al punto MAS CERCANO del contorno de su
propia vivienda. Eso es aproximadamente medio ancho de la habitacion, no un
recorrido. Medido sobre `ejemplo.dxf`: maximo 2.88 m contra un umbral de
25 m -- un margen de 22 m que ninguna vivienda puede salvar.

La regla se presentaba como CRITICO citando el CTE DB-SI y era, en la
practica, un `False` constante. Es el peor modo de fallo posible en materia
de incendios: el informe no decia "no evaluable", decia implicitamente
"cumple".

La comprobacion clave es la B2: una vivienda en L larga tiene que dar un
recorrido MAYOR que la distancia en linea recta. Si alguien vuelve a medir en
linea recta, esa comprobacion cae aunque los umbrales se hayan tocado.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from shapely.geometry import Polygon  # noqa: E402

from analyzer.evaluator import (  # noqa: E402
    MAX_EVACUATION_DISTANCE_M,
    Unit,
    evaluate_evacuation_distance,
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


print()
print("A. Sin pieza de circulacion: NO EVALUABLE, nunca un aprobado")
print("-" * 64)

# Es el caso de las 6 viviendas de `ejemplo.dxf`: ninguna pieza etiquetada
# como circulacion. Sin puerta y sin pasillo no se sabe por donde se sale.
sin_pasillo = Unit(name="VT-SIN", rooms=[
    rect(0, 0, 4, 5, "Salón/cocina"),
    rect(4, 0, 7, 3, "Dormitorio 1"),
])
res, motivo = evaluate_evacuation_distance(sin_pasillo)
check(res == [], "no devuelve ningun resultado", "%d resultados" % len(res))
check(motivo is not None, "declara por que no ha podido comprobarlo")
check(motivo and "no evaluable" in motivo, "y lo dice con esas palabras")
check(motivo and "VT-SIN" in motivo, "identificando la vivienda", motivo[:60] if motivo else "")

# Lo que de verdad importa: una regla no comprobada no puede sumar aprobados
# a la puntuacion. Antes sumaba uno por pieza habitable.
us = score_unit(sin_pasillo, [], [], [])
check(any("evacuación" in lim for lim in us.limitaciones),
      "la limitacion llega hasta UnitScore, visible para el arquitecto")


print()
print("B. Con pieza de circulacion: recorrido real por el grafo")
print("-" * 64)

# Vivienda en linea: dormitorio -- pasillo -- salon. El recorrido del
# dormitorio a la salida pasa por el pasillo.
en_linea = Unit(name="VT-LINEA", rooms=[
    rect(0, 0, 4, 4, "Dormitorio 1"),
    rect(4, 1, 6, 3, "Pasillo"),
    rect(6, 0, 10, 4, "Salón/cocina"),
])
res, motivo = evaluate_evacuation_distance(en_linea)
check(motivo is None, "es evaluable")
check(len(res) == 2, "mide las dos piezas habitables", "%d resultados" % len(res))
dist = {r.room_label: r.distance_m for r in res}
check(abs(dist.get("Dormitorio 1", 0) - 3.0) < 0.01,
      "distancia dormitorio -> pasillo por centroides", "%.2f m" % dist.get("Dormitorio 1", 0))

# B2. LA COMPROBACION QUE DISTINGUE UN RECORRIDO DE UNA LINEA RECTA.
# Vivienda en L: la salida esta en un extremo y el dormitorio en el otro.
# Andando hay que rodear el codo; en linea recta se atraviesa la pared.
en_ele = Unit(name="VT-L", rooms=[
    rect(0, 0, 3, 3, "Pasillo"),          # centro (1.5, 1.5)
    rect(3, 0, 12, 3, "Salón/cocina"),    # centro (7.5, 1.5)
    rect(9, 3, 12, 12, "Dormitorio 1"),   # centro (10.5, 7.5)
])
res, _ = evaluate_evacuation_distance(en_ele)
recorrido = next(r.distance_m for r in res if r.room_label == "Dormitorio 1")
import math  # noqa: E402
recta = math.hypot(10.5 - 1.5, 7.5 - 1.5)
check(recorrido > recta,
      "el recorrido por el grafo es MAYOR que la linea recta",
      "%.2f m andando vs %.2f m en recta" % (recorrido, recta))

# Y mayor todavia que la medida vieja (centroide -> contorno mas cercano),
# que para esta misma vivienda daba poco mas de un metro.
from shapely.ops import unary_union  # noqa: E402
dormitorio = next(r for r in en_ele.rooms if r.label == "Dormitorio 1")
vieja = unary_union([r.polygon for r in en_ele.rooms]).boundary.distance(dormitorio.polygon.centroid)
check(recorrido > vieja * 5,
      "y mucho mayor que la medida anterior, que era medio ancho de la pieza",
      "%.2f m recorrido vs %.2f m de la formula vieja" % (recorrido, vieja))


print()
print("C. Un recorrido largo de verdad sigue disparando")
print("-" * 64)

# Cadena de piezas contiguas hasta superar los 25 m. Arquitectonicamente es
# absurda -- nadie encadena seis distribuidores -- pero aqui se prueba el
# umbral, no el proyecto: si la regla no puede fallar NUNCA, no es una regla.
# Piezas de 4 m pegadas: centros en x = 2, 6, 10 ... 30. Del extremo al
# pasillo hay 28 m de recorrido.
piezas = [rect(0, 0, 4, 4, "Pasillo")]
for i in range(1, 7):
    piezas.append(rect(i * 4, 0, i * 4 + 4, 4, "Distribuidor %d" % i))
piezas.append(rect(28, 0, 32, 4, "Dormitorio 3"))
larga = Unit(name="VT-LARGA", rooms=piezas)
res, motivo = evaluate_evacuation_distance(larga)
check(motivo is None, "vivienda larga: evaluable")
peor = max((r.distance_m for r in res), default=0)
check(peor > MAX_EVACUATION_DISTANCE_M,
      "el peor recorrido supera el maximo del CTE",
      "%.1f m > %.1f m" % (peor, MAX_EVACUATION_DISTANCE_M))
check(any(not r.passed for r in res),
      "y al menos una pieza se marca como incumplimiento")


print()
print("D. Vocabulario de circulacion, no solo 'Pasillo'")
print("-" * 64)

# Que la regla funcione depende de como llame el dibujante a la pieza, no del
# proyecto. Reconocer solo "Pasillo" convierte una convencion ajena en un
# incumplimiento.
for nombre in ("Pasillo", "Vestíbulo", "Distribuidor", "Recibidor", "Hall"):
    u = Unit(name="VT-" + nombre, rooms=[
        rect(0, 0, 4, 4, "Dormitorio 1"),
        rect(4, 1, 6, 3, nombre),
    ])
    _res, motivo = evaluate_evacuation_distance(u)
    check(motivo is None, "'%s' se reconoce como pieza de circulacion" % nombre)


print()
print("=" * 64)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
