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

---

**Qué exige C8, y qué NO** (revisado el 2026-08-18, tarea F0-1 del plan de
migración). Hasta hoy los bloques 1, 2 y 3 comparaban magnitudes al nanómetro:
áreas con `< 1e-9` m² y distancias con `round(d, 9)`. Eso no es C8 — es un
*proxy* de C8, y era más estricto que el contrato que representa.

C8 exige **identidad estructural y de composición**: las mismas viviendas en el
mismo orden, los mismos recintos en el mismo orden dentro de cada una, los
mismos rótulos, las mismas capas, las mismas claves del grafo, los mismos
vecinos y **el mismo orden de vecinos**. Todo eso se sigue comparando por
igualdad exacta y ninguna tolerancia lo toca.

Lo que C8 **no** exige es paridad numérica al nanómetro, y no puede exigirla:
`modelo/geometria.py::_canonica` garantiza geometría canónica al milímetro
—elimina los vértices que se repiten al redondear a `DECIMALES`— mientras que
`analyzer/` conserva el contorno crudo del DXF, vértices redundantes incluidos.
Son dos precisiones distintas a propósito, así que la paridad sólo se puede
pedir a la más gruesa de las dos: el milímetro.

Por qué esto no afloja la red de seguridad:

- **La cota es física, no empírica.** Quitar un vértice que está a menos de un
  milímetro de su vecino desplaza el contorno como mucho un milímetro. Las
  tolerancias de abajo se derivan de ahí y dejan margen sobre lo medido
  (máximos observados sobre `ejemplo.dxf`: 2,9e-4 m² en superficie y 5,5e-5 m
  en distancia).
- **Lo que el bloque 3 protege sigue comprobándose exactamente.** Su razón de
  ser es que migrar `circulation.py` no mida el desempate: el orden de vecinos
  se compara sin tolerancia, y el bloque 4 verifica el resultado final de la
  circulación por igualdad estricta.
- **Exigir el nanómetro exigía reproducir un defecto.** Uno de los contornos
  de `ejemplo.dxf` (VT6/2, "Dormitorio 2") es inválido por autointersección —
  el hallazgo H2 de `docs/audits/2026-08-13-hallazgos-cierre-geometrico.md` §3.
  `_canonica` lo repara de paso, así que paridad exacta contra `analyzer/`
  significaba pedirle al modelo que reprodujera la autointersección.

Las dos precisiones convergerán en F1-6, cuando el analizador pase a leer del
grafo. Hasta entonces esta asimetría es deliberada y está acotada aquí.
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

# Tolerancias derivadas del milimetro que garantiza `_canonica` (ver cabecera).
# No son un margen elegido a ojo: quitar un vertice a menos de 1 mm de su
# vecino desplaza el contorno como mucho 1 mm, y de ahi salen las dos cotas.
TOL_AREA_M2 = 1e-3   # observado como maximo: 2,9e-4 m2 (VT3/3)
TOL_DIST_M = 1e-3    # observado como maximo: 5,5e-5 m (VT3/3)

iguales_areas = all(
    abs(a.total_area_m2 - b.total_area_m2) < TOL_AREA_M2
    for a, b in zip(unidades_evaluador, unidades_modelo))
check(iguales_areas,
      "misma superficie total por vivienda, al milimetro cuadrado (%.0e m2)" % TOL_AREA_M2,
      "max delta: %.3e m2" % max(abs(a.total_area_m2 - b.total_area_m2)
                                 for a, b in zip(unidades_evaluador, unidades_modelo)))

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


# Unico motivo que al modelo se le permite NO emitir, y por que.
#
# `analyzer/superficie_util.py::_revisar` emite GEOMETRY_INVALID si y solo si
# `polygon.is_valid` es falso. En `ejemplo.dxf` hay exactamente un contorno
# invalido: "Dormitorio 2" de VT6/2, con una autointerseccion causada por un
# vertice a ~8e-5 unidades de su vecino -- el hallazgo H2 de
# `docs/audits/2026-08-13-hallazgos-cierre-geometrico.md` §3, preexistente en
# el DXF de origen y ajeno a este modelo.
#
# `modelo/geometria.py::_canonica` descarta ese vertice redundante (el area no
# cambia: delta medido 0,000e+00), el contorno pasa a valido y el motivo deja
# de aplicar. Es una reparacion, no un enmascaramiento, y no queda en silencio:
# `_canonica` lo registra con `logging.warning` diciendo que el contorno de
# origen era invalido.
#
# La conclusion del hecho NO cambia: VT6/2 sigue UNKNOWN, con la misma
# confianza, y GEOMETRY_OVERLAP_UNRESOLVED --el solape de sus dos Terrazas, que
# `_canonica` no toca-- sigue explicando por que. Por eso se admite que falte
# este motivo y solo este; que aparezca o desaparezca cualquier otro sigue
# siendo un fallo, igual que un cambio de estado o de confianza.
#
# Desaparece en F1-6, cuando el analizador lea del grafo y las dos rutas
# compartan geometria.
MOTIVO_REPARADO_POR_CANONICA = "GEOMETRY_INVALID"


def _mismo_hecho(a, b):
    """Igualdad de un hecho: exacta salvo dos excepciones documentadas.

    `nombre`, `ambito`, `estado` y `confianza` se comparan sin tolerancia
    ninguna — son lo que C8 llama identidad, y un cambio ahi es una regresion,
    no ruido de precision.

    Las dos excepciones: `valor`, cuando es un numero, admite el milimetro
    cuadrado de `TOL_AREA_M2` (hereda las areas del bloque 1); y los motivos
    admiten que al modelo le falte `MOTIVO_REPARADO_POR_CANONICA`, por lo
    explicado justo arriba. Un valor no numerico sigue exigiendo igualdad.
    """
    if len(a) != len(b):
        return False
    for i, (x, y) in enumerate(zip(a, b)):
        if i == 3 and isinstance(x, float) and isinstance(y, float):
            if abs(x - y) >= TOL_AREA_M2:
                return False
        elif i == 5:
            # Motivos: mismo orden y mismo contenido, salvo el unico que
            # `_canonica` puede hacer desaparecer al reparar el contorno.
            if tuple(x) != tuple(y) and tuple(
                    m for m in x if m != MOTIVO_REPARADO_POR_CANONICA) != tuple(y):
                return False
        elif x != y:
            return False
    return True


hechos_evaluador = _hechos_de(unidades_evaluador)
hechos_modelo = _hechos_de(unidades_modelo)
iguales_hechos = (len(hechos_evaluador) == len(hechos_modelo) and
                  all(_mismo_hecho(a, b)
                      for a, b in zip(hechos_evaluador, hechos_modelo)))
check(iguales_hechos,
      "los %d hechos de CAP-1..CAP-5 son identicos con y sin modelo "
      "(valor al mm2; solo %s puede faltar, por H2)"
      % (len(hechos_modelo), MOTIVO_REPARADO_POR_CANONICA))
if not iguales_hechos:
    for a, b in zip(hechos_evaluador, hechos_modelo):
        if not _mismo_hecho(a, b):
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
        a = [(id(r), d) for r, d in viejo[clave]]
        b = [(id(r), d) for r, d in nuevo[clave]]
        total_aristas += len(a)
        # El vecino y su POSICION se comparan exactos: es lo que este bloque
        # existe para proteger (el orden decide el desempate de caminos, y sin
        # el migrar `circulation.py` mediria el desempate). El peso admite el
        # milimetro, la precision que garantiza `_canonica`.
        mismos_vecinos = [i for i, _ in a] == [i for i, _ in b]
        mismos_pesos = len(a) == len(b) and all(
            abs(da - db) < TOL_DIST_M for (_, da), (_, db) in zip(a, b))
        if not (mismos_vecinos and mismos_pesos):
            todas_iguales = False
            print("         %s: %s" % (unidad.name,
                  "vecinos u orden distintos" if not mismos_vecinos
                  else "pesos fuera de tolerancia"))
check(todas_iguales,
      "mismo grafo, MISMO ORDEN de vecinos y pesos al milimetro "
      "(%d medio-aristas)" % total_aristas)

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
