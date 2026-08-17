# -*- coding: utf-8 -*-
"""Dos piezas de la misma vivienda no pueden ocupar los mismos metros.

Ejecutar:  python tests/test_solape_interno.py

Rapido (<1 s): geometria sintetica, no toca ezdxf ni ejemplo.dxf.

Que protege:

`evaluate_fire_compartmentation` comparaba vivienda contra vivienda desde el
principio. Nadie comprobaba lo de DENTRO de una vivienda, y ahi estaba el
fallo mas caro del motor: cuando `_discard_container_candidates` conserva el
contorno agrupador de una vivienda -- porque ninguna pieza interior comparte
su etiqueta -- ese contorno entra en el analisis como una habitacion mas.

Medido en `ejemplo.dxf` el 2026-08-05, antes de esta regla:

  VT5/1  "Salon/cocina" de 52.13 m2 = 76% de la vivienda, con el Dormitorio 1
         entero dentro.  12.43 m2 contados dos veces (18%).
  VT6/2  "Salon/cocina" de 58.58 m2 = 56% de la vivienda, con el Dormitorio 1
         y el Bano enteros dentro.  27.32 m2 contados dos veces (26%).

Las dos viviendas se analizaron, se puntuaron y se presentaron como si nada.
VT6/2 llego a usarse en cinco documentos de diseno como ejemplo de "vivienda
con exceso de terrazas" cuando en realidad tenia la geometria rota.

ESTA REGLA DETECTA, NO CURA. La causa esta en el parser y arreglarla ahi
cambia las superficies de todos los proyectos guardados. Lo que se garantiza
aqui es que el analisis deje de ser silenciosamente falso.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from shapely.geometry import Polygon  # noqa: E402

from analyzer.evaluator import (  # noqa: E402
    ROOM_OVERLAP_TOLERANCE_M2,
    Unit,
    classify_problems,
    evaluate_advanced_for_units,
    evaluate_room_overlap,
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
print("A. Una vivienda bien dibujada no dispara nada")
print("-" * 62)

# Piezas contiguas: comparten borde, no area. Es el caso normal y no puede
# generar ni un hallazgo, o la regla seria inservible por ruidosa.
sana = Unit(name="VT-SANA", rooms=[
    rect(0, 0, 4, 5, "Salón/cocina"),
    rect(4, 0, 7, 3, "Dormitorio 1"),
    rect(4, 3, 7, 5, "Dormitorio 2"),
])
check(evaluate_room_overlap([sana]) == [], "piezas contiguas: cero hallazgos")

# Piezas separadas por el hueco del muro (0.03-0.38 m en planos reales).
separada = Unit(name="VT-MURO", rooms=[
    rect(0, 0, 4, 5, "Salón/cocina"),
    rect(4.38, 0, 7, 3, "Dormitorio 1"),
])
check(evaluate_room_overlap([separada]) == [], "piezas separadas por el muro: cero hallazgos")


print()
print("B. El caso real: contorno agrupador colado como habitacion")
print("-" * 62)

# Reproduccion de VT5/1: un "Salon/cocina" que en realidad es el perimetro de
# la vivienda y contiene entero al Dormitorio 1.
contorno = rect(0, 0, 10, 5.213, "Salón/cocina")          # 52.13 m2
dormitorio = rect(0.5, 0.5, 4.5, 3.5, "Dormitorio 1")     # 12.00 m2, dentro
vt51 = Unit(name="VT5/1", rooms=[contorno, dormitorio])

res = evaluate_room_overlap([vt51])
check(len(res) == 1, "detecta exactamente un par solapado", "%d hallazgos" % len(res))
if res:
    r = res[0]
    check(abs(r.overlap_m2 - 12.0) < 0.01, "mide el area solapada", "%.2f m2" % r.overlap_m2)
    check(r.overlap_pct_menor > 99.9,
          "reconoce que la pieza menor esta ENTERA dentro",
          "%.0f%% de la pieza menor" % r.overlap_pct_menor)
    check(r.passed is False, "el resultado es un fallo, no un aviso")
    check(r.unit_name == "VT5/1", "atribuye el hallazgo a su vivienda")

# El 100% de cobertura de la pieza menor es la firma que distingue un
# contorno agrupador de un simple error de dibujo de 20 cm. Se comprueba que
# los dos casos se distinguen, porque la solucion que hay que proponerle al
# arquitecto no es la misma.
solape_leve = Unit(name="VT-ROCE", rooms=[
    rect(0, 0, 4, 5, "Salón/cocina"),
    rect(3.8, 0, 7, 3, "Dormitorio 1"),   # 0.20 m de invasion
])
leve = evaluate_room_overlap([solape_leve])
check(len(leve) == 1 and leve[0].overlap_pct_menor < 20,
      "un roce de 20 cm se detecta pero NO como pieza contenida",
      "%.1f%% de la pieza menor" % (leve[0].overlap_pct_menor if leve else -1))


print()
print("C. Tolerancia: el ruido de dibujo no genera hallazgos")
print("-" * 62)

# Un solape por debajo de la tolerancia es imprecision de dibujo, no un error
# de lectura del plano.
ruido = Unit(name="VT-RUIDO", rooms=[
    rect(0, 0, 4, 5, "Salón/cocina"),
    rect(3.99, 0, 7, 3, "Dormitorio 1"),   # 0.01 x 3 = 0.03 m2
])
check(evaluate_room_overlap([ruido]) == [],
      "solape de 0.03 m2 (< tolerancia %.2f) se ignora" % ROOM_OVERLAP_TOLERANCE_M2)


print()
print("D. Llega hasta la lista de incidencias como CRITICO")
print("-" * 62)

# La deteccion no sirve de nada si se queda dentro del motor: tiene que
# aparecerle al arquitecto.
adv = evaluate_advanced_for_units([vt51, sana], rooms=vt51.rooms + sana.rooms)
check(len(adv.room_overlap) == 1, "evaluate_advanced_for_units lo propaga",
      "%d en AdvancedAnalysis" % len(adv.room_overlap))

issues = classify_problems(adv, fire_compartmentation=adv.fire_compartmentation)
solapes = [i for i in issues if i.codigo == "GEOMETRIA-SOLAPE"]
check(len(solapes) == 1, "classify_problems emite la incidencia", "%d incidencias" % len(solapes))
if solapes:
    i = solapes[0]
    check(i.severity == "CRITICO", "con severidad CRITICO", i.severity)
    check(i.unit_name == "VT5/1", "atribuida a la vivienda afectada", i.unit_name)
    # No es una regla del CTE: es un problema del dato. Emitir un codigo CTE
    # falso aqui seria repetir el error que la auditoria normativa ya senalo.
    check(not i.codigo.startswith("CTE"),
          "y sin fingir que es un incumplimiento del CTE", i.codigo)
    # El texto puede reescribirse, pero tiene que seguir advirtiendo de que
    # las cifras no valen: es la unica parte del mensaje que cambia lo que el
    # arquitecto hace a continuacion.
    check("fiable" in i.impacto and "puntuación" in i.impacto,
          "el impacto advierte de que las superficies y la puntuacion no valen")

# La vivienda sana del mismo analisis no puede haberse contaminado.
check(all(i.unit_name != "VT-SANA" for i in solapes),
      "la vivienda bien dibujada no recibe ninguna incidencia de solape")


print()
print("=" * 62)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
