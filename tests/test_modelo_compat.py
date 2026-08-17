# -*- coding: utf-8 -*-
"""E1.11 — La capa de compatibilidad, contra producción, sobre `ejemplo.dxf`.

Ejecutar:  python tests/test_modelo_compat.py

El contrato C8 del PRD dice que CAP-1…CAP-5 se preservan porque el adaptador
produce `List[Unit]` «con el mismo orden y la misma composición» que
`group_rooms_by_unit_label`. Esto es la definición operativa de *el mismo*, y
se comprueba contra la salida real del evaluador, no contra un fixture.

Cuatro equivalencias, en orden de exigencia:

1. **Agrupación**: mismas viviendas, mismo orden, mismos rótulos, mismas áreas.
2. **Hechos de CAP-1…CAP-5**: los ocho módulos cerrados, alimentados con las
   `Unit` del modelo, publican exactamente los mismos hechos que con las del
   evaluador. Es la prueba directa de que E1 no los toca.
3. **Grafo de adyacencia**: mismas aristas *y el mismo orden de vecinos*. El
   orden decide qué camino gana cuando dos empatan, así que sin esta condición
   migrar `circulation.py` mediría el desempate en vez de la arquitectura.
4. **Circulación**: las cinco comprobaciones de las seis viviendas, calculadas
   con el grafo del modelo, dan lo mismo que con el de `adyacencia.py`.

Si no está `ejemplo.dxf`, se salta con aviso — mismo criterio que el resto.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import adyacencia, circulation, evaluator, parser  # noqa: E402
from analyzer.altura_evacuacion import resolver_altura_evacuacion  # noqa: E402
from analyzer.ocupacion import ocupacion as calcular_ocupacion  # noqa: E402
from analyzer.planta import planta as calcular_planta  # noqa: E402
from analyzer.sectorizacion import limite_superficie_sector  # noqa: E402
from analyzer.superficie_util import (  # noqa: E402
    superficie_util_db_si, superficie_util_ocupable_db_si,
)
from analyzer.uso_previsto import ZonaDeUso, usos_por_zona  # noqa: E402
from modelo import compat, constructor  # noqa: E402

fallos = []
comprobaciones = 0


def check(condicion, titulo, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s" % ("OK  " if condicion else "FALLO", titulo))
    if detalle:
        print("         %s" % detalle)
    if not condicion:
        fallos.append(titulo)


DXF = os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf")
if not os.path.exists(DXF):
    print("[SALTA] no se encuentra %s" % DXF)
    print("Todas las comprobaciones OK (0)")
    sys.exit(0)

plano = parser.leer_plano(parser.load_document(DXF))
unidades_evaluador = evaluator.group_rooms_by_unit_label(plano.rooms, plano.unit_labels)
modelo = constructor.construir(plano, semilla="compat", fichero="ejemplo.dxf")
unidades_modelo = compat.a_unidades(modelo)

print("=" * 70)
print("1. AGRUPACION: adaptador vs group_rooms_by_unit_label")
print("=" * 70)

check([u.name for u in unidades_evaluador] == [u.name for u in unidades_modelo],
      "mismas viviendas y en el mismo orden",
      ", ".join(u.name for u in unidades_modelo))
check(len(unidades_modelo) == 6, "seis viviendas en ejemplo.dxf")

iguales_composicion = all(
    [r.label for r in a.rooms] == [r.label for r in b.rooms]
    for a, b in zip(unidades_evaluador, unidades_modelo))
check(iguales_composicion, "misma composicion y mismo orden de recintos por vivienda")

iguales_areas = all(
    abs(a.total_area_m2 - b.total_area_m2) < 1e-9
    for a, b in zip(unidades_evaluador, unidades_modelo))
check(iguales_areas, "misma superficie total por vivienda, al nanometro cuadrado")

iguales_capas = all(
    [r.layer for r in a.rooms] == [r.layer for r in b.rooms]
    for a, b in zip(unidades_evaluador, unidades_modelo))
check(iguales_capas, "la capa de procedencia vuelve intacta por el adaptador")

print()
print("=" * 70)
print("2. CAP-1..CAP-5 alimentados por el modelo")
print("=" * 70)


def _hechos_de(unidades):
    usos = usos_por_zona([ZonaDeUso(nombre="vivienda %s" % u.name) for u in unidades],
                         tipologia="plurifamiliar", uso_principal=None)
    plantas = [calcular_planta("vivienda %s" % u.name) for u in unidades]
    sup_util = [superficie_util_db_si(u) for u in unidades]
    sup_ocup = [superficie_util_ocupable_db_si(u) for u in unidades]
    ocupaciones = [calcular_ocupacion(s, uso, planta=pl)
                   for s, uso, pl in zip(sup_ocup, usos, plantas)]
    sectores = limite_superficie_sector(sup_util, plantas)
    altura = resolver_altura_evacuacion("edificio", valor_declarado_m=None)
    return [
        (h.nombre, h.ambito, h.estado, h.valor, h.confianza,
         tuple(m.codigo for m in h.motivos))
        for h in sup_util + sup_ocup + usos + plantas + ocupaciones + sectores + [altura]
    ]


hechos_evaluador = _hechos_de(unidades_evaluador)
hechos_modelo = _hechos_de(unidades_modelo)
check(hechos_evaluador == hechos_modelo,
      "los %d hechos de CAP-1..CAP-5 son identicos con y sin modelo" % len(hechos_modelo))
if hechos_evaluador != hechos_modelo:
    for a, b in zip(hechos_evaluador, hechos_modelo):
        if a != b:
            print("         %s\n         %s" % (a, b))
            break

print()
print("=" * 70)
print("3. GRAFO DE ADYACENCIA: modelo vs analyzer/adyacencia.py")
print("=" * 70)

todas_iguales = True
total_aristas = 0
for unidad in unidades_evaluador:
    viejo = adyacencia.construir_grafo(unidad.rooms)
    nuevo = compat.grafo_de_adyacencia(unidad)
    if set(viejo) != set(nuevo):
        todas_iguales = False
        print("         claves distintas en %s" % unidad.name)
        continue
    for clave in viejo:
        a = [(id(r), round(d, 9)) for r, d in viejo[clave]]
        b = [(id(r), round(d, 9)) for r, d in nuevo[clave]]
        total_aristas += len(a)
        if a != b:
            todas_iguales = False
            print("         %s: vecinos distintos" % unidad.name)
check(todas_iguales,
      "mismo grafo, mismos pesos y MISMO ORDEN de vecinos (%d medio-aristas)" % total_aristas)

print()
print("=" * 70)
print("4. CIRCULACION calculada sobre el grafo del modelo")
print("=" * 70)

avanzado = evaluator.evaluate_advanced(
    plano.rooms, unit_labels=plano.unit_labels, norte_grados=0.0,
    tipologia="plurifamiliar", zona_cte="C", densidad_urbana="media")


def _rutas(unit_score, constructor_grafo):
    original = circulation._build_adjacency_graph
    circulation._build_adjacency_graph = constructor_grafo
    try:
        circ = circulation.evaluate_circulation(unit_score)
    finally:
        circulation._build_adjacency_graph = original
    return sorted((r.tipo, r.passed, r.message, tuple(r.path_labels),
                   round(r.metric_value, 6) if r.metric_value is not None else None)
                  for r in circ.routes)


iguales = True
n_rutas = 0
for us in avanzado.unit_scores:
    con_adyacencia = _rutas(us, lambda u: adyacencia.construir_grafo(u.rooms))
    con_modelo = _rutas(us, compat.grafo_de_adyacencia)
    n_rutas += len(con_adyacencia)
    if con_adyacencia != con_modelo:
        iguales = False
        print("         %s difiere" % us.unit.name)
        for x, y in zip(con_adyacencia, con_modelo):
            if x != y:
                print("           adyacencia: %s\n           modelo    : %s" % (x, y))
check(iguales, "las %d comprobaciones de circulacion son identicas" % n_rutas)

print()
print("=" * 70)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
