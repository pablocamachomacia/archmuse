# -*- coding: utf-8 -*-
"""CAP-2: el uso previsto es un eje propio, no un alias de la tipologia.

Ejecutar:  python tests/test_uso_previsto.py

Rapido (<1 s): no toca disco ni red salvo el bloque final de compatibilidad.

Que protege:

1. Que `tipologia` y `uso_previsto` NO se confundan. Hoy la equivalencia
   plurifamiliar -> Residencial Vivienda es correcta y por eso nadie la nota;
   el dia que entre un local en planta baja, cinco tablas del DB-SI se
   indexarian mal en silencio.
2. Que una inferencia NUNCA se disfrace de declaracion: sale ESTIMATED, con la
   hipotesis escrita, no KNOWN.
3. Que `rehabilitacion` no infiera uso: es un tipo de intervencion.
4. Que una regla futura pueda consumir el uso SIN preguntar por la tipologia.
5. Que el analisis residencial actual siga dando exactamente lo mismo.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer.hechos import ESTIMATED, KNOWN, UNKNOWN  # noqa: E402
from analyzer.uso_previsto import (  # noqa: E402
    ALMACEN,
    CATALOGO,
    COMERCIAL,
    DESCONOCIDO,
    PUBLICA_CONCURRENCIA,
    RESIDENCIAL_VIVIENDA,
    USO_NO_DECLARADO,
    USO_NO_RECONOCIDO,
    ZonaDeUso,
    uso_de,
    uso_previsto,
    usos_por_zona,
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


def codigos(h):
    return [m.codigo for m in h.motivos]


print("A. Casos 1 y 2 - unifamiliar y plurifamiliar con uso residencial")

for tip in ("unifamiliar", "plurifamiliar"):
    h = uso_previsto("vivienda", declarado=RESIDENCIAL_VIVIENDA, tipologia=tip)
    check(h.estado == KNOWN and h.valor == RESIDENCIAL_VIVIENDA,
          "%s + uso declarado -> KNOWN" % tip, "%s / %s" % (h.estado, h.valor))
    check(h.confianza == "Alta", "y confianza Alta (lo dijo el arquitecto)")

    inf = uso_previsto("vivienda", tipologia=tip)
    check(inf.estado == ESTIMATED and inf.valor == RESIDENCIAL_VIVIENDA,
          "%s SIN declarar -> ESTIMATED, no KNOWN" % tip,
          "%s / %s / conf=%s" % (inf.estado, inf.valor, inf.confianza))
    check(any("HIPOTESIS" in p for p in inf.procedencia),
          "y la hipotesis viaja escrita en la procedencia",
          inf.procedencia[0])

print("\nB. Caso 3 - una zona con uso distinto")

h = uso_previsto("local planta baja", declarado=COMERCIAL, tipologia="plurifamiliar")
check(h.estado == KNOWN and h.valor == COMERCIAL,
      "local COMERCIAL en un edificio plurifamiliar", h.valor)
check(h.diagnostico["denominacion_normativa"] == "Uso Comercial",
      "conserva la denominacion normativa junto al id interno",
      h.diagnostico["denominacion_normativa"])
check(h.diagnostico["concept_id_uso"] == "es.cte.db_si.anejo_a.uso_comercial",
      "y cita la definicion del Anejo SI A")

print("\nC. Caso 4 - uso desconocido / no reconocido")

h = uso_previsto("zona rara", declarado="CASINO_FLOTANTE")
check(h.estado == UNKNOWN and USO_NO_RECONOCIDO in codigos(h),
      "un uso fuera del catalogo -> UNKNOWN", str(codigos(h)))
check("CASINO_FLOTANTE" in h.motivos[0].detalle,
      "y el motivo dice QUE llego, no solo que fallo")
check(uso_de(h) == DESCONOCIDO, "uso_de() devuelve UNKNOWN, no un valor por defecto")

print("\nD. Caso 5 - ausencia de uso")

h = uso_previsto("vivienda")
check(h.estado == UNKNOWN and USO_NO_DECLARADO in codigos(h),
      "sin uso ni tipologia -> UNKNOWN", str(codigos(h)))
check("no se asume Residencial Vivienda" in h.explicacion,
      "y se dice explicitamente que no se asume vivienda", h.explicacion)

h = uso_previsto("vivienda", tipologia="rehabilitacion")
check(h.estado == UNKNOWN,
      "«rehabilitacion» NO infiere uso -> UNKNOWN",
      "es un tipo de intervencion; se rehabilita un hospital igual que un piso")

print("\nE. Caso 6 - multiples zonas con usos diferentes")

zonas = [
    ZonaDeUso("vivienda VT1/3"),
    ZonaDeUso("vivienda VT2/2"),
    ZonaDeUso("local planta baja", uso_declarado=COMERCIAL),
    ZonaDeUso("garaje", uso_declarado="APARCAMIENTO"),
]
hechos = usos_por_zona(zonas, tipologia="plurifamiliar",
                       uso_principal=RESIDENCIAL_VIVIENDA)
check(len(hechos) == 4, "un hecho por zona, en el mismo orden")
check(hechos[2].valor == COMERCIAL and hechos[3].valor == "APARCAMIENTO",
      "cada zona conserva SU uso, no el del edificio",
      "%s / %s" % (hechos[2].valor, hechos[3].valor))
check(hechos[0].valor == RESIDENCIAL_VIVIENDA and hechos[0].estado == KNOWN,
      "las zonas sin uso propio heredan el principal")
check(any("heredado" in p for p in hechos[0].procedencia),
      "pero la herencia queda registrada como tal",
      hechos[0].procedencia[-1])
check(not any("heredado" in p for p in hechos[2].procedencia),
      "y la zona que SI declaro uso no aparece como heredada")

sin_principal = usos_por_zona([ZonaDeUso("vivienda VT1/3")], tipologia="plurifamiliar")
check(sin_principal[0].estado == ESTIMATED,
      "sin uso principal declarado, la zona cae a ESTIMATED por tipologia")

print("\nF. Caso 7 - separacion tipologia / uso")

a = uso_previsto("z", declarado=RESIDENCIAL_VIVIENDA, tipologia="plurifamiliar")
b = uso_previsto("z", declarado=COMERCIAL, tipologia="plurifamiliar")
check(a.valor != b.valor,
      "MISMA tipologia + uso distinto -> hecho distinto",
      "%s vs %s con tipologia=plurifamiliar en ambos" % (a.valor, b.valor))
check(uso_de(a) == RESIDENCIAL_VIVIENDA and uso_de(b) == COMERCIAL,
      "una regla futura puede consumir el uso sin mirar la tipologia",
      "uso_de() no recibe ni consulta la tipologia")

c = uso_previsto("z", declarado=RESIDENCIAL_VIVIENDA, tipologia="unifamiliar")
check(a.valor == c.valor,
      "y tipologia distinta + mismo uso -> mismo uso",
      "la tipologia no contamina el valor del hecho")

check("tipologia" not in (a.diagnostico or {}),
      "un uso declarado ni siquiera registra la tipologia",
      "solo la inferencia la necesita, para poder explicarse")

print("\nG. Catalogo")

check(len(CATALOGO) == 10, "10 valores en el catalogo", str(len(CATALOGO)))
check(CATALOGO[PUBLICA_CONCURRENCIA].concept_id is None,
      "«Publica Concurrencia» no lleva concept_id",
      "el DB-SI la usa en sus tablas pero el Anejo SI A no la define")
check(CATALOGO[ALMACEN].concept_id is not None,
      "pero «Almacen» si, porque el Anejo SI A si la define")

print("\nH. Caso 8 - compatibilidad con el analisis actual")

DXF = os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf")
if not os.path.exists(DXF):
    print("  [SALTA] no se encuentra %s" % DXF)
else:
    from analyzer import parser  # noqa: E402
    from analyzer.evaluator import (  # noqa: E402
        evaluate_unit_efficiency, evaluate_unit_minimum_area,
        group_rooms_by_unit_label,
    )

    plano = parser.leer_plano(parser.load_document(DXF))
    unidades = group_rooms_by_unit_label(plano.rooms, plano.unit_labels)

    # Recalculado el 2026-08-13 tras la correccion de cierre geometrico
    # (analyzer/parser.py::_esta_cerrada, ver tests/test_cierre_recuperado.py):
    # VT1/3, VT3/3, VT4/2, VT5/1 y VT6/2 cambian de ratio porque ganan
    # recintos que antes no se leian (closed=False mal puesto). VT2/2 no
    # tiene ningun recinto afectado y se mantiene igual.
    R03 = {"VT1/3": "0.8862489408444045", "VT2/2": "0.8722520478815108",
           "VT3/3": "0.8880697613574597", "VT4/2": "0.8707562503816217",
           "VT5/1": "0.9058127313769088", "VT6/2": "0.6215614081192977"}
    for r in evaluate_unit_efficiency(unidades):
        check(repr(r.ratio) == R03[r.unit_name], "R03 %s intacta" % r.unit_name)
    check(all(repr(evaluate_unit_minimum_area(u, "plurifamiliar").useful_area_m2)
              != "" for u in unidades), "R07 sigue evaluandose igual")

    # El flujo real sin declarar uso: 6 zonas, todas ESTIMATED por tipologia.
    hechos = usos_por_zona([ZonaDeUso("vivienda %s" % u.name) for u in unidades],
                           tipologia="plurifamiliar", uso_principal=None)
    check(len(hechos) == 6 and all(h.estado == ESTIMATED for h in hechos),
          "sin declarar uso, las 6 viviendas salen ESTIMATED",
          "el analisis sigue funcionando, pero ya no finge que es un hecho")
    check(all(uso_de(h) == RESIDENCIAL_VIVIENDA for h in hechos),
          "y el uso inferido sigue siendo Residencial Vivienda",
          "compatibilidad preservada")

print("\n" + "=" * 60)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
