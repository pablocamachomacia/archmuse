# -*- coding: utf-8 -*-
"""`evaluate_acoustic_adjacency()` — cobertura dedicada.

Ejecutar:  python tests/test_acoustic_adjacency.py

Hasta este cambio (`docs/prd/2026-08-11-adyacencia-acustica-tramo-enfrentado.md`)
esta regla no tenía ni un test propio — se comprobó por búsqueda antes de
escribir este fichero. Dos bloques:

1. **`ejemplo.dxf` real**: los 19 pares Dormitorio×Baño/Aseo del plano, con el
   veredicto exacto medido en E3.5 y confirmado al implementar — 15 disparan,
   4 no. Es el golden de esta regla: si algún día cambia, este test debe
   fallar primero y decir exactamente qué par cambió.

   (Eran 11 pares, 9 disparan, hasta la corrección de cierre geométrico de
   2026-08-13 — `analyzer/parser.py::_esta_cerrada`, ver
   `tests/test_cierre_recuperado.py`. Esa corrección recupera 8 pares nuevos,
   repartidos en Dormitorio1/2×Aseo y Dormitorio3×Aseo/Baño de VT3/3 —nuevo
   Aseo y Dormitorio 3—, Dormitorio1/2×Baño de VT4/2 —nuevo Baño—,
   Dormitorio1×Baño de VT5/1 —nuevo Baño— y Dormitorio2×Baño de VT6/2 —nuevo
   Dormitorio 2—; los 11 pares y sus 9 veredictos originales no cambian.)
2. **Casos sintéticos del espesor de muro** — la prueba directa de qué se
   arregló: con el criterio antiguo (`_is_adjacent`, exige contacto) un gap
   de 0,10-0,20m (tabique/muro típico) no disparaba nunca; con
   `tramo_enfrentado_m` sí. El caso de gap=0,60m confirma que el criterio
   nuevo no dispara porque sí — sigue respetando `WALL_GAP_TOLERANCE_M`.
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
print("1. ejemplo.dxf real — 19 pares, veredicto exacto")
print("=" * 78)

# (vivienda, dormitorio, húmeda, dispara) — medido en E3.5, confirmado al
# implementar. Los 2 que no disparan (VT1/3 Dormitorio 3) están genuinamente
# lejos (gap 3,84m y 2,33m): la prueba de que el criterio nuevo no dispara
# porque sí.
ESPERADO = {
    ("VT1/3", "Dormitorio 1", "Aseo"): True,
    ("VT1/3", "Dormitorio 1", "Baño"): True,
    ("VT1/3", "Dormitorio 2", "Aseo"): True,
    ("VT1/3", "Dormitorio 2", "Baño"): True,
    ("VT1/3", "Dormitorio 3", "Aseo"): False,
    ("VT1/3", "Dormitorio 3", "Baño"): False,
    ("VT2/2", "Dormitorio 1", "Baño"): True,
    ("VT2/2", "Dormitorio 2", "Baño"): True,
    ("VT3/3", "Dormitorio 1", "Baño"): True,
    ("VT3/3", "Dormitorio 2", "Baño"): True,
    ("VT6/2", "Dormitorio 1", "Baño"): True,
    # Los 8 pares siguientes solo existen desde la correccion de cierre
    # geometrico de 2026-08-13: antes, "Aseo"/"Dormitorio 3" de VT3/3,
    # "Baño" de VT4/2 y VT5/1, y "Dormitorio 2" de VT6/2 no se leian
    # (closed=False mal puesto). Dormitorio 3 sigue lejos de las zonas
    # humedas en VT3/3, igual que ya media en VT1/3.
    ("VT3/3", "Dormitorio 1", "Aseo"): True,
    ("VT3/3", "Dormitorio 2", "Aseo"): True,
    ("VT3/3", "Dormitorio 3", "Aseo"): False,
    ("VT3/3", "Dormitorio 3", "Baño"): False,
    ("VT4/2", "Dormitorio 1", "Baño"): True,
    ("VT4/2", "Dormitorio 2", "Baño"): True,
    ("VT5/1", "Dormitorio 1", "Baño"): True,
    ("VT6/2", "Dormitorio 2", "Baño"): True,
}

plano = parser.leer_plano(parser.load_document(DXF))
unidades = evaluator.group_rooms_by_unit_label(plano.rooms, plano.unit_labels)

medido = {}
for unidad in unidades:
    for r in evaluator.evaluate_acoustic_adjacency(unidad):
        medido[(unidad.name, r.room_label, r.noisy_label)] = not r.passed  # "dispara" = passed False

check(len(medido) == 19, "19 pares Dormitorio x Baño/Aseo evaluados", len(medido))
check(sum(medido.values()) == 15, "15 de 19 disparan con el criterio nuevo", sum(medido.values()))

for clave, dispara_esperado in sorted(ESPERADO.items()):
    dispara_real = medido.get(clave)
    check(dispara_real == dispara_esperado,
          "%s: %s -> dispara=%s" % (clave[0], "%s/%s" % (clave[1], clave[2]), dispara_esperado),
          "medido=%s" % dispara_real)

print()
print("=" * 78)
print("2. Casos sinteticos: el espesor de muro (la prueba directa del arreglo)")
print("=" * 78)


def _unidad_con(gap_m: float) -> evaluator.Unit:
    dorm = Room(label="Dormitorio 1", polygon=box(0.0, 0.0, 3.0, 3.0), layer="00 areas")
    bano = Room(label="Baño", polygon=box(3.0 + gap_m, 0.0, 3.0 + gap_m + 2.0, 2.0), layer="00 areas")
    return evaluator.Unit(name="sintetica", rooms=[dorm, bano])


CASOS = (
    ("tocan literalmente (gap=0.000m)", 0.000, True),
    ("tabique tipico (gap=0.10m) — ANTES no disparaba, es el defecto que se corrige", 0.10, True),
    ("muro de carga (gap=0.20m) — mismo defecto", 0.20, True),
    ("gap grande (gap=0.60m), no deberia disparar", 0.60, False),
)

for descripcion, gap, dispara_esperado in CASOS:
    unidad = _unidad_con(gap)
    resultado = evaluator.evaluate_acoustic_adjacency(unidad)
    check(len(resultado) == 1, "  [%s] produce 1 resultado" % descripcion, len(resultado))
    dispara_real = not resultado[0].passed
    check(dispara_real == dispara_esperado,
          "  [%s] dispara=%s" % (descripcion, dispara_esperado), "medido=%s" % dispara_real)

print()
print("=" * 78)
if fallos:
    print("FALLOS (%d de %d): %s" % (len(fallos), comprobaciones, ", ".join(fallos)))
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
