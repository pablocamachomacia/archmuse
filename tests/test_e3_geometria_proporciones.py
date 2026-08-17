# -*- coding: utf-8 -*-
"""E3.4 — `evaluate_proportions`/`evaluate_corridor_width` vs `AlmacenGeometria`.

Ejecutar:  python tests/test_e3_geometria_proporciones.py

Mide, no supone. Compara el "antes" (`evaluator._bounding_sides`, que sigue
existiendo intacto para `spatial_quality.py`) contra el "después" (la salida
real de `evaluate_proportions`/`evaluate_corridor_width`, que ahora piden los
lados a `AlmacenGeometria.lado_mayor_m/lado_menor_m/alargamiento`), sobre la
misma geometría exacta.

**El punto crítico que pidió el encargo, medido y no supuesto:** las dos
funciones migradas llaman a los métodos SIN redondear de `AlmacenGeometria`
(`lado_mayor_m`, `lado_menor_m`, `alargamiento`) — no a `derivados()`, que sí
redondea a 3 decimales. Así que el redondeo a milímetro NO es la fuente de
diferencia aquí; la única fuente posible es que el modelo calcula los lados
del rectángulo envolvente con una fórmula distinta
(`(dx*dx+dy*dy)**0.5` en `modelo/geometria._lados_del_rectangulo`) a la que
usa `_bounding_sides` (`shapely.Point.distance`) — mismo resultado
matemático, camino de cómputo distinto, y eso sí puede dejar ruido de punto
flotante de última cifra. Este test mide exactamente cuánto.

Dos bloques:

1. **Proporciones, sobre los 40 recintos reales de `ejemplo.dxf`.** Ninguno
   se llama "Pasillo" (censo ya conocido desde E0), así que los 40 entran.
   (Eran 34 hasta la corrección de cierre geométrico de 2026-08-13 —
   `analyzer/parser.py::_esta_cerrada` — que recuperó 8 recintos con
   `closed=False` mal puesto en el DXF de origen; ver
   `tests/test_cierre_recuperado.py`.)
2. **Ancho de pasillo, sobre recintos sintéticos.** `ejemplo.dxf` no tiene NI
   UN recinto "Pasillo" — `evaluate_corridor_width` devuelve `[]` sobre él, y
   sin datos sintéticos esta regla quedaría sin medir en absoluto, incluidos
   los casos pegados al umbral (0,90 m plurifamiliar / 0,80 m unifamiliar)
   que el encargo pide comprobar especialmente.

Si no está `ejemplo.dxf`, se salta con aviso — mismo criterio que el resto de
`tests/`.
"""
import os
import sys

from shapely.geometry import box

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import evaluator, parser  # noqa: E402
from analyzer.parser import Room  # noqa: E402

fallos = []
comprobaciones = 0
TOLERANCIA_M = 1e-6  # ver docstring: no hay redondeo de por medio, solo ruido de punto flotante


def check(cond, titulo, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s" % ("OK  " if cond else "FALLO", titulo))
    if detalle:
        print("         %s" % detalle)
    if not cond:
        fallos.append(titulo)


DXF = os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf")
if not os.path.exists(DXF):
    print("[SALTA] no se encuentra %s" % DXF)
    print("Todas las comprobaciones OK (0)")
    sys.exit(0)

print("=" * 78)
print("1. evaluate_proportions: antes (_bounding_sides) vs despues (AlmacenGeometria)")
print("=" * 78)

plano = parser.leer_plano(parser.load_document(DXF))
rooms = plano.rooms
check(len(rooms) == 40, "40 recintos leidos", len(rooms))
check(not any(r.label and "PASILLO" in evaluator._normalize(r.label) for r in rooms),
      "ningun recinto es Pasillo (evaluate_proportions no filtra ninguno)")

nuevos = evaluator.evaluate_proportions(rooms)
check(len(nuevos) == len(rooms), "evaluate_proportions devuelve una fila por recinto",
      "%d resultados, %d recintos" % (len(nuevos), len(rooms)))

diffs_long = []
diffs_short = []
diffs_ratio = []
cambios_de_juicio = []
cerca_del_umbral = []  # a menos de 0.01 del umbral 1:MAX_ASPECT_RATIO

for room, nuevo in zip(rooms, nuevos):
    long_old, short_old = evaluator._bounding_sides(room.polygon)
    ratio_old = long_old / short_old
    passed_old = ratio_old <= evaluator.MAX_ASPECT_RATIO

    diffs_long.append(abs(long_old - nuevo.long_side_m))
    diffs_short.append(abs(short_old - nuevo.short_side_m))
    diffs_ratio.append(abs(ratio_old - nuevo.ratio))

    if passed_old != nuevo.passed:
        cambios_de_juicio.append((room.label, ratio_old, nuevo.ratio, passed_old, nuevo.passed))

    if abs(ratio_old - evaluator.MAX_ASPECT_RATIO) < 0.01:
        cerca_del_umbral.append((room.label, ratio_old, nuevo.ratio, passed_old, nuevo.passed))

print("  Diferencia maxima  lado largo : %.3e m" % max(diffs_long))
print("  Diferencia maxima  lado corto : %.3e m" % max(diffs_short))
print("  Diferencia maxima  ratio      : %.3e" % max(diffs_ratio))
print("  Recintos con ratio a <0.01 del umbral 1:%.1f: %d" % (evaluator.MAX_ASPECT_RATIO, len(cerca_del_umbral)))
for label, r_old, r_new, p_old, p_new in cerca_del_umbral:
    print("    - %r: ratio_antes=%.6f ratio_despues=%.6f passed_antes=%s passed_despues=%s"
          % (label, r_old, r_new, p_old, p_new))

check(max(diffs_long) < TOLERANCIA_M, "lado largo: diferencia < %.0e m en los 40 recintos" % TOLERANCIA_M,
      "max=%.3e" % max(diffs_long))
check(max(diffs_short) < TOLERANCIA_M, "lado corto: diferencia < %.0e m en los 40 recintos" % TOLERANCIA_M,
      "max=%.3e" % max(diffs_short))
check(max(diffs_ratio) < TOLERANCIA_M, "ratio: diferencia < %.0e en los 40 recintos" % TOLERANCIA_M,
      "max=%.3e" % max(diffs_ratio))
check(not cambios_de_juicio, "ningun recinto cambia de veredicto (passed) al migrar",
      cambios_de_juicio if cambios_de_juicio else "ninguno")

print()
print("=" * 78)
print("2. evaluate_corridor_width: casos sinteticos pegados al umbral")
print("=" * 78)
print("  ejemplo.dxf no tiene NINGUN recinto 'Pasillo' (evaluate_corridor_width")
print("  devuelve [] sobre el) -- sin recintos sinteticos esta regla quedaria")
print("  sin medir. Umbrales reales: 0.90 m (plurifamiliar), 0.80 m (unifamiliar/rehabilitacion).")
print()


def _pasillo_de(ancho_m: float, largo_m: float = 4.0) -> Room:
    # box(minx, miny, maxx, maxy): un rectangulo limpio, sin ambiguedad de
    # cual lado es "corto" -- ancho_m siempre es el lado corto si largo_m > ancho_m.
    return Room(label="Pasillo", polygon=box(0.0, 0.0, largo_m, ancho_m), layer="00 areas")


CASOS = [
    ("ancho, claramente pasa (1.50m)", 1.50, "plurifamiliar"),
    ("estrecho, claramente falla (0.50m)", 0.50, "plurifamiliar"),
    ("exactamente en el umbral (0.90m, plurifamiliar)", 0.90, "plurifamiliar"),
    ("0.001m por debajo del umbral (0.899m)", 0.899, "plurifamiliar"),
    ("0.001m por encima del umbral (0.901m)", 0.901, "plurifamiliar"),
    ("exactamente en el umbral (0.80m, unifamiliar)", 0.80, "unifamiliar"),
    ("0.001m por debajo del umbral (0.799m, unifamiliar)", 0.799, "unifamiliar"),
]

for descripcion, ancho, tipologia in CASOS:
    room = _pasillo_de(ancho)
    unidad = evaluator.Unit(name="sintetica", rooms=[room])

    _, short_old = evaluator._bounding_sides(room.polygon)
    min_width_m = evaluator.UMBRALES_TIPOLOGIA[tipologia]["corridor_width_min"]
    passed_old = short_old >= min_width_m

    resultado_nuevo = evaluator.evaluate_corridor_width(unidad, tipologia=tipologia)
    check(len(resultado_nuevo) == 1, "  [%s] produce 1 resultado" % descripcion, len(resultado_nuevo))
    nuevo = resultado_nuevo[0]

    diff = abs(short_old - nuevo.short_side_m)
    cambia = passed_old != nuevo.passed
    print("  %-52s antes=%.6fm despues=%.6fm diff=%.3e passed_antes=%s passed_despues=%s"
          % (descripcion, short_old, nuevo.short_side_m, diff, passed_old, nuevo.passed))
    check(diff < TOLERANCIA_M, "  [%s] diferencia < %.0e m" % (descripcion, TOLERANCIA_M), "diff=%.3e" % diff)
    check(not cambia, "  [%s] mismo veredicto antes/despues" % descripcion,
          "antes=%s despues=%s" % (passed_old, nuevo.passed) if cambia else "")

print()
print("=" * 78)
if fallos:
    print("FALLOS (%d de %d): %s" % (len(fallos), comprobaciones, ", ".join(fallos)))
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
