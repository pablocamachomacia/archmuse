# -*- coding: utf-8 -*-
"""CAP-4: el hecho `planta` y el normalizador del campo de formulario.

Ejecutar:  python tests/test_planta.py

Rapido (<1 s): funciones puras, sin DXF.

Que protege:

1. El normalizador interpreta "Planta baja/N" y "Sotano N" (case/acentos/
   espacios insensible) y nada mas — nunca un patron VT<n>/<n>, nunca
   geometria, nunca un texto ambiguo convertido en numero por comodidad.
2. `sobre_rasante` tiene el significado arquitectonico real: numero > 0.
   Planta baja (0) y sotano (negativo) NO son sobre rasante.
3. El hecho `planta()` produce KNOWN (declarada), ESTIMATED (convencion de
   nombre) o UNKNOWN (ninguna de las dos) — nunca silencio, nunca un origen
   sin reconocer.
4. `NO_APLICABLE` no se usa para este hecho.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer.hechos import ALTA, ESTIMATED, KNOWN, MEDIA, UNKNOWN  # noqa: E402
from analyzer.planta import (  # noqa: E402
    ORIGEN_CONVENCION_NOMBRE,
    ORIGEN_DECLARADO,
    PLANTA_NO_DISPONIBLE,
    normalizar_declaracion_planta,
    planta,
)

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


print("A. Normalizador — casos interpretables, con su sobre_rasante correcto")

CASOS_VALIDOS = [
    ("Planta baja", (0, False)),
    ("PLANTA BAJA", (0, False)),
    ("  planta   baja  ", (0, False)),
    ("Planta 0", (0, False)),
    ("Sótano 1", (-1, False)),
    ("Sótano -1", (-1, False)),
    ("Sotano 1", (-1, False)),          # sin tilde
    ("SOTANO 2", (-2, False)),
    ("Planta 1", (1, True)),
    ("planta 1", (1, True)),            # minusculas
    ("Planta 2", (2, True)),
    ("Planta 3ª", (3, True)),           # ordinal femenino
    ("Planta 1º", (1, True)),           # ordinal masculino
    ("planta 1er", (1, True)),          # "1er"
    ("Planta  5", (5, True)),           # espacio doble
]
for texto, esperado in CASOS_VALIDOS:
    got = normalizar_declaracion_planta(texto)
    check(got == esperado, "%r -> %r" % (texto, esperado), "obtenido %r" % (got,))

print("\nB. Normalizador — nunca infiere planta de VT<n>/<n>")

for texto in ("VT1/3", "VT2/2", "VT9/9", "VT1", "vt3/3"):
    got = normalizar_declaracion_planta(texto)
    check(got is None, "%r no se interpreta como planta" % texto, "obtenido %r" % (got,))

print("\nC. Normalizador — ambiguo o vacio no inventa una planta")

for texto in (None, "", "   ", "varias", "?", "Sótano", "Sotano 0", "Planta",
              "Planta X", "entreplanta", "1", "planta uno"):
    got = normalizar_declaracion_planta(texto)
    check(got is None, "%r -> None (no interpretable)" % (texto,), "obtenido %r" % (got,))

print("\nD. El hecho `planta()` — declarada, estimada, desconocida")

h_unknown = planta("vivienda V1", numero=None)
check(h_unknown.estado == UNKNOWN, "sin numero -> UNKNOWN")
check(h_unknown.valor is None, "UNKNOWN no publica valor (P6)")
check(len(h_unknown.motivos) == 1 and h_unknown.motivos[0].codigo == PLANTA_NO_DISPONIBLE,
      "UNKNOWN lleva motivo estructurado",
      "codigos: %s" % [m.codigo for m in h_unknown.motivos])

h_unknown_motivo = planta("vivienda V1", numero=None,
                           motivo_no_disponible="declaracion de planta no interpretable")
check(h_unknown_motivo.motivos[0].detalle == "declaracion de planta no interpretable",
      "el motivo de UNKNOWN es el que pasa quien llama, no uno generico fijo")

h_declarada = planta("vivienda V1", numero=1, sobre_rasante=True, origen=ORIGEN_DECLARADO)
check(h_declarada.estado == KNOWN, "declarada -> KNOWN")
check(h_declarada.valor == 1, "declarada conserva el numero")
check(h_declarada.confianza == ALTA, "declarada -> confianza Alta")
check(h_declarada.diagnostico.get("sobre_rasante") is True, "sobre_rasante viaja en diagnostico")

h_estimada = planta("vivienda V2", numero=3, sobre_rasante=True, origen=ORIGEN_CONVENCION_NOMBRE)
check(h_estimada.estado == ESTIMATED, "convencion de nombre -> ESTIMATED, nunca KNOWN")
check(h_estimada.confianza == MEDIA, "convencion de nombre -> confianza Media")

h_sotano = planta("vivienda V3", numero=-1, sobre_rasante=False, origen=ORIGEN_DECLARADO)
check(h_sotano.estado == KNOWN, "sotano declarado -> KNOWN igualmente")
check(h_sotano.valor == -1, "sotano conserva el numero negativo")

try:
    planta("vivienda V4", numero=2, origen="geometria")
    check(False, "origen no reconocido debe levantar ValueError")
except ValueError:
    check(True, "origen no reconocido (p. ej. 'geometria') levanta ValueError")

try:
    planta("vivienda V5", numero=2, origen=None)
    check(False, "numero sin origen debe levantar ValueError")
except ValueError:
    check(True, "numero sin origen levanta ValueError — no hay fuente implicita")

check("NO_APLICABLE" not in (h_unknown.estado, h_declarada.estado, h_estimada.estado),
      "NO_APLICABLE no se usa para el hecho planta")

print("\n" + "=" * 60)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
