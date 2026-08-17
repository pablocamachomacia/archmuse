# -*- coding: utf-8 -*-
"""E3.1/E3.3 — paridad de clasificación entre `circulation.py` y el modelo.

Ejecutar:  python tests/test_e3_paridad_clasificacion.py

**Historia de este fichero, para que no se lea como si siempre hubiera sido
así.** Se escribió en E3.1 para medir, ANTES de tocar producción, si los 5
patrones regex que usaba entonces `analyzer/circulation.py` coincidían con
`modelo.constructor.clasificar()`. Resultado: paridad 34/34 sobre
`ejemplo.dxf`, cero divergencias, para 4 de los 5 patrones — el quinto
(`_CIRCULATION_ROOM_PATTERN`) quedó sin poder medirse porque `ejemplo.dxf` no
tiene ningún recinto de esa familia (`docs/prd/2026-08-11-e3-clasificacion-circulation.md`
§1.4). Con esa medición, E3.2 aprobó migrar los 4 con paridad demostrada, y
E3.3 lo ejecutó: **esos 4 patrones ya no existen como regex en
`circulation.py`** (el PRD, §6, dice explícitamente que dejan de definirse).

Este fichero se actualizó en E3.3, mecánicamente, para seguir siendo capaz de
comparar algo real: ya no hay un regex vivo con el que comparar los 4
migrados, así que lo que se comprueba ahora para ellos es la **fontanería**
que `circulation.py` ejecuta de verdad (`modelo_compat.tipos_de_unidad` +
`circulation._tiene_tipo`) contra una fuente independiente
(`clasificar()` llamado aquí mismo, sin pasar por `compat.py`) — sigue siendo
una comprobación real (detecta un `id(Room)` mal indexado, una caché
corrupta, un conjunto mal copiado), sólo que ya no es "¿coincidían?" sino
"¿la migración se conectó bien?". Para el quinto patrón, sin migrar, la
comprobación es exactamente la misma que en E3.1: regex vivo contra modelo.

**Los 5, con su estado real, tras E3.3:**

    _DORMITORIO_ANY_PATTERN    MIGRADO  -> circulation._TIPOS_DORMITORIO   {"dormitorio"}
    _SALON_PATTERN              MIGRADO  -> circulation._TIPOS_SALON        {"salon","cocina"}
    _BANO_OR_ASEO_PATTERN       MIGRADO  -> circulation._TIPOS_BANO_O_ASEO  {"bano","aseo"}
    _DESTINATION_PATTERN        MIGRADO  -> circulation._TIPOS_DESTINO      {"salon","cocina","dormitorio","bano","aseo"}
    _CIRCULATION_ROOM_PATTERN   SIN MIGRAR (regex tal cual)                 {"circulacion"}

**"¿Afecta a una decisión real?"** se sigue contestando empíricamente: se
ejecuta `circulation.evaluate_circulation()` de verdad sobre `ejemplo.dxf` y
se comprueba si la habitación divergente aparece en el `path` de alguna
`CirculationRoute` producida para su vivienda.

Si no está `ejemplo.dxf`, se salta con aviso — mismo criterio que el resto de
`tests/`.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import circulation, evaluator, parser  # noqa: E402
from modelo import compat as modelo_compat  # noqa: E402
from modelo.constructor import clasificar  # noqa: E402

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

# --- Los 4 migrados (E3.3): ya no son regex, son conjuntos de tipos que
#     circulation._tiene_tipo compara contra modelo_compat.tipos_de_unidad.
PATRONES_MIGRADOS = (
    ("_DORMITORIO_ANY_PATTERN (migrado E3.3)", circulation._TIPOS_DORMITORIO),
    ("_SALON_PATTERN (migrado E3.3)", circulation._TIPOS_SALON),
    ("_BANO_OR_ASEO_PATTERN (migrado E3.3)", circulation._TIPOS_BANO_O_ASEO),
    ("_DESTINATION_PATTERN (migrado E3.3)", circulation._TIPOS_DESTINO),
)

# --- El quinto, sin migrar a proposito: sigue siendo un regex de verdad,
#     importado en vivo, comparado contra el modelo exactamente como en E3.1.
NOMBRE_SIN_MIGRAR = "_CIRCULATION_ROOM_PATTERN (SIN migrar)"
PATRON_SIN_MIGRAR = circulation._CIRCULATION_ROOM_PATTERN
CONJUNTO_SIN_MIGRAR = frozenset({"circulacion"})

print("=" * 78)
print("0. LOS 5 PATRONES, CON SU ESTADO REAL TRAS E3.3")
print("=" * 78)
for nombre, conjunto in PATRONES_MIGRADOS:
    print("  %-42s -> %s  (ya no es regex; ver modelo_compat.tipos_de_unidad)"
          % (nombre, sorted(conjunto)))
print("  %-42s -> %s  (regex vivo: %r)"
      % (NOMBRE_SIN_MIGRAR, sorted(CONJUNTO_SIN_MIGRAR), PATRON_SIN_MIGRAR.pattern))

# --- Lectura real de ejemplo.dxf, misma agrupacion que usa produccion. -----

plano = parser.leer_plano(parser.load_document(DXF))
unidades = evaluator.group_rooms_by_unit_label(plano.rooms, plano.unit_labels)
check(len(unidades) == 6, "6 viviendas leidas", len(unidades))
n_rooms = sum(len(u.rooms) for u in unidades)
# Eran 34 hasta la correccion de cierre geometrico de 2026-08-13
# (analyzer/parser.py::_esta_cerrada, ver tests/test_cierre_recuperado.py):
# recupera 8 recintos con closed=False mal puesto en el DXF de origen.
check(n_rooms == 40, "40 recintos leidos en total", n_rooms)

# --- Para cada recinto: tipo del modelo (fuente independiente, vía
#     clasificar() llamado aquí) vs. lo que circulation.py obtiene de verdad
#     (vía modelo_compat.tipos_de_unidad, para los 4 migrados; vía su regex
#     vivo, para el quinto). ---------------------------------------------

filas = []
for unidad in unidades:
    tipos_wiring = modelo_compat.tipos_de_unidad(unidad)  # lo que circulation.py usa de verdad
    for room in unidad.rooms:
        atributo, ambiguos = clasificar(room.label)  # fuente independiente
        tipos_modelo = frozenset({atributo.valor} | set(ambiguos)) if atributo.valor else frozenset()

        resultados = {}
        for nombre, conjunto in PATRONES_MIGRADOS:
            dice_circulation = circulation._tiene_tipo(room, tipos_wiring, conjunto)
            dice_modelo = bool(tipos_modelo & conjunto)
            resultados[nombre] = (dice_circulation, dice_modelo)

        dice_patron_sm = bool(room.label and PATRON_SIN_MIGRAR.search(circulation._normalize(room.label)))
        dice_modelo_sm = bool(tipos_modelo & CONJUNTO_SIN_MIGRAR)
        resultados[NOMBRE_SIN_MIGRAR] = (dice_patron_sm, dice_modelo_sm)

        filas.append((unidad.name, room.label, atributo.valor, atributo.confianza, ambiguos, resultados))

check(len(filas) == 40, "40 filas de comparacion generadas", len(filas))
check(all(f[2] is not None for f in filas),
      "el modelo clasifica los 40 recintos (ninguno UNKNOWN) en ejemplo.dxf",
      [f[1] for f in filas if f[2] is None])

print()
print("=" * 78)
print("1. TODAS LAS FILAS (40 recintos x 5 comprobaciones) — para trazabilidad completa")
print("=" * 78)
print("%-8s %-16s %-12s %-6s %-14s  %s" % ("vivienda", "rotulo", "tipo_modelo", "conf.", "ambiguos", "circulation/modelo"))
for vivienda, rotulo, tipo, confianza, ambiguos, resultados in filas:
    resumen = " ".join(
        "%s=%s/%s" % (n.split(" ")[0].replace("_PATTERN", "").replace("_ANY", ""), int(p), int(m))
        for n, (p, m) in resultados.items()
    )
    print("%-8s %-16s %-12s %-6s %-14s  %s" % (
        vivienda, rotulo, tipo, confianza, ",".join(ambiguos) or "-", resumen))

# --- Inventario de divergencias. ------------------------------------------

print()
print("=" * 78)
print("2. INVENTARIO DE DIVERGENCIAS (lo que circulation.py obtiene != modelo)")
print("=" * 78)

divergencias = []
for vivienda, rotulo, tipo, confianza, ambiguos, resultados in filas:
    for nombre, (dice_circulation, dice_modelo) in resultados.items():
        if dice_circulation != dice_modelo:
            divergencias.append({
                "vivienda": vivienda, "rotulo": rotulo, "tipo_modelo": tipo,
                "ambiguos_modelo": ambiguos, "patron": nombre,
                "patron_dice": dice_circulation, "modelo_dice": dice_modelo,
            })

if not divergencias:
    print("  Ninguna. Los 4 patrones migrados están correctamente conectados al modelo "
          "(wiring == fuente independiente) y el patrón sin migrar sigue coincidiendo "
          "con el modelo en los 40 recintos de ejemplo.dxf.")
else:
    for d in divergencias:
        print("  - vivienda=%s  rotulo=%r" % (d["vivienda"], d["rotulo"]))
        print("      modelo:  tipo=%r  ambiguos=%r" % (d["tipo_modelo"], d["ambiguos_modelo"]))
        print("      %s:  circulation.py dice=%s   modelo (para su conjunto) dice=%s" % (
            d["patron"], d["patron_dice"], d["modelo_dice"]))

# --- Por cada divergencia: ¿aparece esa habitacion en algun recorrido real
#     que evaluate_circulation() produce hoy para su vivienda? -------------

print()
print("=" * 78)
print("3. ¿CADA DIVERGENCIA AFECTA UNA DECISION REAL DE evaluate_circulation()?")
print("=" * 78)

if not divergencias:
    print("  N/A: no hay divergencias que comprobar.")
else:
    advanced = evaluator.evaluate_advanced(
        plano.rooms, unit_labels=plano.unit_labels, norte_grados=0.0,
        tipologia="plurifamiliar", zona_cte="C", densidad_urbana="media")

    rutas_por_vivienda = {}
    for us in advanced.unit_scores:
        circ = circulation.evaluate_circulation(us)
        etiquetas_en_algun_path = set()
        for ruta in circ.routes:
            etiquetas_en_algun_path.update(r.label for r in ruta.path if r.label)
        rutas_por_vivienda[us.unit.name] = (circ, etiquetas_en_algun_path)

    for d in divergencias:
        circ, etiquetas = rutas_por_vivienda.get(d["vivienda"], (None, set()))
        aparece = d["rotulo"] in etiquetas
        veredicto = ("SI — aparece en un path real de %s" % d["vivienda"]) if aparece else \
                    ("NO — %r nunca aparece en ningun path de %s con las comprobaciones "
                     "actuales (vocabulario, sin ocurrencia observable en este DXF)"
                     % (d["rotulo"], d["vivienda"]))
        print("  - %s / %r [%s]: %s" % (d["vivienda"], d["rotulo"], d["patron"], veredicto))
        d["afecta_decision_real"] = aparece

n_afectan = sum(1 for d in divergencias if d.get("afecta_decision_real"))
print()
print("Resumen: %d divergencia(s), %d con efecto observable hoy sobre ejemplo.dxf, "
      "%d puramente de vocabulario." % (
          len(divergencias), n_afectan, len(divergencias) - n_afectan))

print()
print("=" * 78)
if fallos:
    print("FALLOS (%d de %d): %s" % (len(fallos), comprobaciones, ", ".join(fallos)))
    sys.exit(1)
print("Todas las comprobaciones estructurales OK (%d). "
      "Divergencias encontradas: %d (ver inventario arriba)." % (comprobaciones, len(divergencias)))
