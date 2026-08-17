# -*- coding: utf-8 -*-
"""CAP-3: la ocupacion se calcula con la Tabla 2.1, se divide (nunca se
multiplica), y nunca se redondea.

Ejecutar:  python tests/test_ocupacion.py

Rapido (<3 s): geometria sintetica + ejemplo.dxf si esta disponible.

Que protege:

1. La trampa dimensional invertida (`/` no `*`): un error de x400 posible en
   residencial si se confunde divisor con multiplicador.
2. Que NO se redondee el valor del hecho (DB-SI_DECISIONS.md D2): la
   ocupacion es fraccionaria, y el "o fraccion" es cosa de cada regla.
3. Que "ocupacion nula" sea NO_APLICABLE, nunca 0.0.
4. Que un insumo UNKNOWN (superficie o uso) propague UNKNOWN con motivo, no
   un valor a medias.
5. Que la fila de la Tabla 2.1 sea literal (20 m2/persona, Residencial
   Vivienda, "Plantas de vivienda"), y que un uso con varias filas produzca
   UNKNOWN por falta de zona, no una fila adivinada.
6. Que la ocupacion declarada mayor prevalezca, y una declarada menor se
   exponga sin aplicarse sola.
7. Que R03/R07/R14 y CAP-1/CAP-2 sigan intactos: CAP-3 anade, no toca.
"""
import math
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from shapely.geometry import Polygon  # noqa: E402

from analyzer.evaluator import Unit  # noqa: E402
from analyzer.hechos import ALTA, ESTIMATED, KNOWN, MEDIA, NO_APLICABLE, UNKNOWN, Hecho  # noqa: E402
from analyzer.parser import Room  # noqa: E402
from analyzer.planta import (  # noqa: E402
    ORIGEN_CONVENCION_NOMBRE,
    ORIGEN_DECLARADO,
    planta as hecho_planta,
)
from analyzer.ocupacion import (  # noqa: E402
    DENSIDAD_NO_DISPONIBLE,
    FILA_PLANTAS_DE_VIVIENDA,
    SUPERFICIE_NO_DISPONIBLE,
    USO_FUERA_DE_TABLA,
    USO_NO_DISPONIBLE,
    ZONA_NO_DECLARADA,
    densidad_ocupacion,
    ocupacion,
    ocupacion_por_zona,
)
from analyzer.superficie_util import (  # noqa: E402
    superficie_util_db_si,
    superficie_util_ocupable_db_si,
)
from analyzer.uso_previsto import (  # noqa: E402
    ADMINISTRATIVO,
    COMERCIAL,
    RESIDENCIAL_VIVIENDA,
    uso_previsto,
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


def rect(x0, y0, ancho, alto, etiqueta):
    return Room(label=etiqueta, layer="00 areas",
                polygon=Polygon([(x0, y0), (x0 + ancho, y0),
                                 (x0 + ancho, y0 + alto), (x0, y0 + alto)]))


print("A. Caso nominal - Residencial Vivienda, 20 m2/persona")

vivienda_40m2 = Unit(name="V1", rooms=[rect(0, 0, 8, 5, "Salon")])
sup = superficie_util_ocupable_db_si(vivienda_40m2)
check(sup.estado == KNOWN and abs(sup.valor - 40.0) < 1e-9,
      "superficie ocupable = 40 m2", repr(sup.valor))

uso = uso_previsto(sup.ambito, declarado=RESIDENCIAL_VIVIENDA)
h = ocupacion(sup, uso)
check(h.estado == KNOWN, "ocupacion KNOWN", h.estado)
check(abs(h.valor - 2.0) < 1e-9,
      "40 m2 / 20 m2/persona = 2.0 personas (DIVISION, no producto)",
      repr(h.valor))
check(h.unidad == "personas", "unidad = personas")
check(h.diagnostico["densidad_m2_por_persona"] == 20.0,
      "densidad correcta en diagnostico")

print("\nB. La trampa dimensional - dividir, no multiplicar")

vivienda_grande = Unit(name="V2", rooms=[rect(0, 0, 100, 4, "Salon")])
sup2 = superficie_util_ocupable_db_si(vivienda_grande)
uso2 = uso_previsto(sup2.ambito, declarado=RESIDENCIAL_VIVIENDA)
h2 = ocupacion(sup2, uso2)
esperado = 400.0 / 20.0
check(abs(h2.valor - esperado) < 1e-9,
      "400 m2 / 20 = 20 personas, NUNCA 400*20=8000",
      "valor=%r (multiplicar daria %r, x400 el error)" % (h2.valor, 400.0 * 20.0))

print("\nC. Nunca se redondea")

vivienda_fraccionaria = Unit(name="V3", rooms=[rect(0, 0, 5, 5, "Salon")])
sup3 = superficie_util_ocupable_db_si(vivienda_fraccionaria)
uso3 = uso_previsto(sup3.ambito, declarado=RESIDENCIAL_VIVIENDA)
h3 = ocupacion(sup3, uso3)
check(abs(h3.valor - 1.25) < 1e-9,
      "25 m2 / 20 = 1.25, fraccionario, SIN redondear", repr(h3.valor))
check(h3.diagnostico["presentacion_personas"] == 2,
      "presentacion_personas SI redondea por exceso (ceil), pero es solo formato",
      h3.diagnostico["presentacion_personas"])
check(h3.diagnostico["redondeo_normativo"] == UNKNOWN,
      "redondeo_normativo declarado UNKNOWN: el DB-SI no lo establece (D2)")
check(math.isclose(h3.diagnostico["ocupacion_exacta"], 1.25),
      "ocupacion_exacta conserva el fraccionario en diagnostico")

print("\nD. Zona de ocupacion nula - NO_APLICABLE, nunca 0.0")

d_nula = densidad_ocupacion("trastero", uso=RESIDENCIAL_VIVIENDA, ocupacion_nula=True)
check(d_nula.estado == NO_APLICABLE, "densidad NO_APLICABLE para ocupacion nula",
      d_nula.estado)
check(d_nula.valor is None, "y NO publica 0.0 como valor", repr(d_nula.valor))

sup_trastero = Hecho(nombre="superficie_util_ocupable_db_si", ambito="trastero",
                     tipo="derivado", unidad="m2", estado=KNOWN, valor=8.0,
                     confianza=MEDIA)
uso_trastero = uso_previsto("trastero", declarado=RESIDENCIAL_VIVIENDA)
h_nula = ocupacion(sup_trastero, uso_trastero, densidad=d_nula)
check(h_nula.estado == NO_APLICABLE,
      "ocupacion de una zona de ocupacion nula -> NO_APLICABLE, no 0", h_nula.estado)
check(h_nula.valor is None,
      "sin valor numerico: 0 seria indistinguible de 'no hay nadie'")

print("\nE. Propagacion UNKNOWN - superficie o uso ausentes")

sup_unknown = Hecho(nombre="superficie_util_ocupable_db_si", ambito="vivienda rota",
                    tipo="derivado", unidad="m2", estado=UNKNOWN,
                    motivos=(__import__("analyzer.hechos", fromlist=["Motivo"]).Motivo(
                        "GEOMETRY_OVERLAP_UNRESOLVED", "solape de prueba"),))
uso_ok = uso_previsto("vivienda rota", declarado=RESIDENCIAL_VIVIENDA)
h_sup_unknown = ocupacion(sup_unknown, uso_ok)
check(h_sup_unknown.estado == UNKNOWN, "superficie UNKNOWN -> ocupacion UNKNOWN")
check(SUPERFICIE_NO_DISPONIBLE in codigos(h_sup_unknown),
      "motivo AREA_NOT_AVAILABLE, con la causa original visible",
      h_sup_unknown.motivo_principal.detalle)
check("solape de prueba" in h_sup_unknown.motivo_principal.detalle,
      "la cadena causal original no se pierde (D3.b)")

uso_unknown = uso_previsto("vivienda sin uso")  # sin declarar, sin tipologia
sup_ok = Hecho(nombre="superficie_util_ocupable_db_si", ambito="vivienda sin uso",
              tipo="derivado", unidad="m2", estado=KNOWN, valor=40.0, confianza=MEDIA)
h_uso_unknown = ocupacion(sup_ok, uso_unknown)
check(h_uso_unknown.estado == UNKNOWN, "uso UNKNOWN -> ocupacion UNKNOWN")
check(USO_NO_DISPONIBLE in codigos(h_uso_unknown),
      "motivo USE_NOT_AVAILABLE", codigos(h_uso_unknown))
check(h_uso_unknown.valor is None, "y no publica valor pese a tener superficie")

print("\nF. Uso ESTIMATED contagia el estado del hecho derivado")

uso_estimado = uso_previsto("v4", tipologia="plurifamiliar")  # sin declarar -> ESTIMATED
check(uso_estimado.estado == ESTIMATED, "sanity: el uso es ESTIMATED", uso_estimado.estado)
sup4 = Hecho(nombre="superficie_util_ocupable_db_si", ambito="v4", tipo="derivado",
            unidad="m2", estado=KNOWN, valor=40.0, confianza=MEDIA)
h4 = ocupacion(sup4, uso_estimado)
check(h4.estado == ESTIMATED,
      "ocupacion sobre uso ESTIMATED sale ESTIMADA, no KNOWN",
      "un hecho ESTIMATED nunca sostiene un KNOWN por si solo (FACT_MODEL §6)")
check(h4.valor is not None, "pero SI publica valor (es hipotesis, no ausencia)")

print("\nG. Selector de fila de la Tabla 2.1")

d = densidad_ocupacion("v", uso=RESIDENCIAL_VIVIENDA)
check(d.estado == KNOWN and d.valor == 20.0,
      "Residencial Vivienda -> 20 m2/persona, unica fila", d.valor)
check(d.referencia_normativa == "DB-SI / SI 3 / ap. 2 / Tabla 2.1",
      "cita la Tabla 2.1", d.referencia_normativa)
check(d.confianza == ALTA,
      "confianza Alta: valor de tabla verificado contra el texto ingerido")

d_admin = densidad_ocupacion("v", uso=ADMINISTRATIVO)
check(d_admin.estado == UNKNOWN and ZONA_NO_DECLARADA in codigos(d_admin),
      "Administrativo tiene VARIAS filas -> UNKNOWN, no una fila adivinada",
      codigos(d_admin))

d_comercial = densidad_ocupacion("v", uso=COMERCIAL)
check(d_comercial.estado == UNKNOWN and ZONA_NO_DECLARADA in codigos(d_comercial),
      "Comercial (7 filas) -> UNKNOWN por la misma razon")

d_inventado = densidad_ocupacion("v", uso="CASINO_FLOTANTE")
check(d_inventado.estado == UNKNOWN and USO_FUERA_DE_TABLA in codigos(d_inventado),
      "un uso fuera de catalogo -> UNKNOWN, 'mas asimilable' es criterio del tecnico",
      codigos(d_inventado))

d_sin_uso = densidad_ocupacion("v", uso=None)
check(d_sin_uso.estado == UNKNOWN and USO_NO_DISPONIBLE in codigos(d_sin_uso),
      "sin uso -> UNKNOWN", codigos(d_sin_uso))

print("\nH. Ocupacion declarada")

sup5 = Hecho(nombre="superficie_util_ocupable_db_si", ambito="v5", tipo="derivado",
            unidad="m2", estado=KNOWN, valor=40.0, confianza=MEDIA)
uso5 = uso_previsto("v5", declarado=RESIDENCIAL_VIVIENDA)
h_mayor = ocupacion(sup5, uso5, declarada=10.0)  # calculado=2.0, declarado=10.0
check(h_mayor.valor == 10.0,
      "una ocupacion declarada MAYOR prevalece sobre el calculo (ap.2, salvedad 1)",
      "calculado=2.0, declarado=10.0 -> %r" % h_mayor.valor)
check(h_mayor.diagnostico["origen_del_valor"] == "declarado_mayor",
      "y queda registrado que el origen es 'declarado_mayor'")

h_menor = ocupacion(sup5, uso5, declarada=1.0)  # calculado=2.0, declarado=1.0
check(h_menor.valor == 2.0,
      "una ocupacion declarada MENOR NO se aplica sola (excepcion sujeta a "
      "justificacion, CONSTRAINT_MODEL.md §5)",
      "calculado=2.0 se mantiene pese a declarar 1.0 -> %r" % h_menor.valor)
check(h_menor.diagnostico.get("excepcion_pendiente_de_justificacion") is True,
      "pero queda registrada como excepcion pendiente, no descartada en silencio")

print("\nI. Ambito declarado como provisional (CAP-4 pendiente)")

check(h.diagnostico["ambito_normativo"] == "planta (Tabla 2.1: «Plantas de vivienda»)",
      "el hecho dice cual es el ambito NORMATIVO")
check(h.diagnostico["ambito_emitido"] == "vivienda",
      "y cual es el ambito EMITIDO, sin confundirlos")
check(h.diagnostico["agregado_no_normativo"] is True,
      "marcado explicitamente como agregado no normativo")

print("\nJ. Confianza: el eslabon mas debil, nunca una media")

check(h.confianza == MEDIA,
      "superficie Media + uso Alta + densidad Alta -> ocupacion Media (el minimo)",
      h.confianza)

print("\nK. ocupacion_por_zona - varias viviendas, sin filtrar UNKNOWN")

zonas_superficie = [sup, sup2, sup_unknown]
zonas_uso = [uso, uso2, uso_ok]
lote = ocupacion_por_zona(zonas_superficie, zonas_uso)
check(len(lote) == 3, "un hecho por zona, mismo orden y longitud")
check(lote[0].estado == KNOWN and lote[2].estado == UNKNOWN,
      "las UNKNOWN se conservan en la lista, no desaparecen")

try:
    ocupacion_por_zona([sup], [uso, uso2])
    check(False, "listas de distinta longitud deben fallar")
except ValueError:
    check(True, "listas de distinta longitud -> ValueError, no un emparejado silencioso")

print("\nL. Compatibilidad con CAP-1/CAP-2 y el analisis actual (ejemplo.dxf)")

DXF = os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf")
if not os.path.exists(DXF):
    print("  [SALTA] no se encuentra %s" % DXF)
else:
    from analyzer import parser  # noqa: E402
    from analyzer.evaluator import (  # noqa: E402
        evaluate_unit_efficiency, group_rooms_by_unit_label,
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

    conocidas = 0
    for u in unidades:
        sup_u = superficie_util_ocupable_db_si(u)
        uso_u = uso_previsto("vivienda %s" % u.name, tipologia="plurifamiliar")
        h_u = ocupacion(sup_u, uso_u)
        check(h_u.estado in (KNOWN, ESTIMATED, UNKNOWN),
              "%s: ocupacion en un estado valido del contrato (%s)" % (u.name, h_u.estado))
        if h_u.estado != UNKNOWN:
            check(h_u.valor >= 0, "%s: ocupacion no negativa" % u.name)
            conocidas += 1
    check(conocidas >= 4,
          "al menos las viviendas sin solape producen ocupacion (D6: terrazas computan)",
          "%d de %d" % (conocidas, len(unidades)))

print("\nM. CAP-4: parametro `planta` en `ocupacion()`")
print("M.1 Equivalencia con bd1a62f cuando no hay planta (o esta UNKNOWN)")

# Snapshot exacto del comportamiento de bd1a62f (commit CAP-3), capturado
# ANTES de tocar analyzer/ocupacion.py. Estas comprobaciones deben pasar
# tanto con el ocupacion.py de bd1a62f (sin parametro `planta`) como despues
# de anadirselo, mientras `planta` no se declare o su hecho sea UNKNOWN.
h_equiv = ocupacion(sup, uso)
check(h_equiv.ambito == "vivienda V1",
      "sin planta: ambito identico a bd1a62f", h_equiv.ambito)
check(h_equiv.estado == KNOWN and abs(h_equiv.valor - 2.0) < 1e-9,
      "sin planta: estado/valor identicos a bd1a62f")
check(h_equiv.confianza == MEDIA,
      "sin planta: confianza identica a bd1a62f (Media)", h_equiv.confianza)
DIAG_EQUIV_ESPERADO = {
    "ambito_normativo": "planta (Tabla 2.1: «Plantas de vivienda»)",
    "ambito_emitido": "vivienda",
    "agregado_no_normativo": True,
    "motivo_del_desvio": "ArchMuse no modela plantas hasta CAP-4",
    "concept_id_superficie_util": "es.cte.db_si.anejo_a.superficie_util",
    "densidad_m2_por_persona": 20.0,
    "ocupacion_exacta": 2.0,
    "presentacion_personas": 2,
    "redondeo_normativo": UNKNOWN,
    "superficie_util_ocupable_m2": 40.0,
    "uso": "RESIDENCIAL_VIVIENDA",
}
check(h_equiv.diagnostico == DIAG_EQUIV_ESPERADO,
      "sin planta: diagnostico byte a byte identico a bd1a62f",
      h_equiv.diagnostico)
check(h_equiv.explicacion ==
      "Ocupacion de 2.00 personas: 40.00 m2 utiles ocupables entre 20 "
      "m2/persona (DB-SI 3 ap. 2, Tabla 2.1). Agregado por vivienda; la "
      "tabla indexa por planta.",
      "sin planta: explicacion identica a bd1a62f", h_equiv.explicacion)

h_nula_equiv = ocupacion(sup_trastero, uso_trastero, densidad=d_nula)
check(h_nula_equiv.ambito == "trastero",
      "sin planta, NO_APLICABLE: ambito identico a bd1a62f", h_nula_equiv.ambito)
check(h_nula_equiv.diagnostico.get("motivo_del_desvio") ==
      "ArchMuse no modela plantas hasta CAP-4",
      "sin planta, NO_APLICABLE: motivo_del_desvio identico a bd1a62f")
check(h_nula_equiv.diagnostico.get("agregado_no_normativo") is True,
      "sin planta, NO_APLICABLE: sigue agregado_no_normativo=True")

h_unk_equiv = ocupacion(sup_unknown, uso_ok)
check(h_unk_equiv.ambito == "vivienda rota",
      "sin planta, UNKNOWN: ambito identico a bd1a62f", h_unk_equiv.ambito)
check(h_unk_equiv.diagnostico.get("motivo_del_desvio") ==
      "ArchMuse no modela plantas hasta CAP-4",
      "sin planta, UNKNOWN: motivo_del_desvio identico a bd1a62f")

print("\nM.2 planta=Hecho UNKNOWN (explicito): mismo comportamiento, motivo propio")

planta_unk_explicita = hecho_planta("vivienda V1", numero=None)
h_planta_unk = ocupacion(sup, uso, planta=planta_unk_explicita)
check(h_planta_unk.ambito == "vivienda V1",
      "planta UNKNOWN explicita: ambito sigue siendo el de la vivienda")
check(h_planta_unk.estado == KNOWN and abs(h_planta_unk.valor - 2.0) < 1e-9,
      "planta UNKNOWN explicita: calculo de ocupacion sin cambios")
check(h_planta_unk.diagnostico["agregado_no_normativo"] is True,
      "planta UNKNOWN explicita: sigue agregado_no_normativo=True")
check(h_planta_unk.diagnostico["motivo_del_desvio"] !=
      "ArchMuse no modela plantas hasta CAP-4",
      "planta UNKNOWN explicita: motivo propio de planta, mas especifico",
      h_planta_unk.diagnostico["motivo_del_desvio"])
check("no se ha declarado" in h_planta_unk.diagnostico["motivo_del_desvio"].lower(),
      "el motivo especifico es el que emite planta.py",
      h_planta_unk.diagnostico["motivo_del_desvio"])

print("\nM.3 planta=Hecho KNOWN (declarada): ambito real, sin agregado")

planta_known = hecho_planta("vivienda V1", numero=3, sobre_rasante=True,
                             origen=ORIGEN_DECLARADO)
h_planta_known = ocupacion(sup, uso, planta=planta_known)
check(h_planta_known.ambito == "planta 3, vivienda V1",
      "planta KNOWN: ambito identifica la planta real, sin perder la vivienda",
      h_planta_known.ambito)
check(abs(h_planta_known.valor - 2.0) < 1e-9,
      "planta KNOWN: el valor de ocupacion NO cambia (2.0 personas)",
      repr(h_planta_known.valor))
check(h_planta_known.diagnostico["agregado_no_normativo"] is False,
      "planta KNOWN: agregado_no_normativo pasa a False")
check(h_planta_known.diagnostico["ambito_emitido"] == "planta 3",
      "planta KNOWN: ambito_emitido = 'planta 3'",
      h_planta_known.diagnostico["ambito_emitido"])
check(h_planta_known.diagnostico["planta_numero"] == 3,
      "planta KNOWN: numero de planta trazable en diagnostico")
check("motivo_del_desvio" not in h_planta_known.diagnostico,
      "planta KNOWN: ya no hay 'motivo_del_desvio' (no hay desvio)")
check(h_planta_known.confianza == MEDIA,
      "planta KNOWN (confianza Alta) no sube la confianza de ocupacion "
      "por encima de la de superficie (Media, el eslabon mas debil)",
      h_planta_known.confianza)

print("\nM.4 planta=Hecho ESTIMATED (convencion de nombre): igual que KNOWN en ambito")

planta_estimada = hecho_planta("vivienda V2", numero=2, sobre_rasante=True,
                                origen=ORIGEN_CONVENCION_NOMBRE)
h_planta_estimada = ocupacion(sup2, uso2, planta=planta_estimada)
check(h_planta_estimada.diagnostico["agregado_no_normativo"] is False,
      "planta ESTIMATED: tambien corrige el ambito, no solo KNOWN")
check(h_planta_estimada.diagnostico["planta_estado"] == ESTIMATED,
      "planta ESTIMATED: el estado de planta queda trazado en diagnostico",
      h_planta_estimada.diagnostico["planta_estado"])
check(h_planta_estimada.estado == KNOWN,
      "el estado de ocupacion (KNOWN/ESTIMATED/UNKNOWN) sigue dependiendo solo "
      "de superficie/uso, NUNCA se ve forzado a ESTIMATED solo porque la "
      "planta lo sea: son dos ejes distintos (estado del valor vs. certeza "
      "del ambito)", h_planta_estimada.estado)
check(h_planta_estimada.confianza == MEDIA,
      "pero la confianza SI baja si planta es ESTIMATED y hace de eslabon "
      "mas debil", h_planta_estimada.confianza)

print("\nM.5 La confianza de planta SI es el eslabon mas debil cuando el resto es Alta")

# sup2/uso2 no discriminan esto: superficie_util_ocupable_db_si() ya limita a
# Media por criterio propio (D1.b), asi que la confianza final seria Media
# con o sin planta. Se construye un caso sintetico enteramente Alta para
# demostrar que es planta, y no otra cosa, la que arrastra la confianza.
sup_alta = Hecho(nombre="superficie_util_ocupable_db_si", ambito="vivienda ALTA",
                  tipo="derivado", unidad="m2", estado=KNOWN, valor=40.0,
                  confianza=ALTA)
uso_alta = uso_previsto("vivienda ALTA", declarado=RESIDENCIAL_VIVIENDA)
h_sin_planta_alta = ocupacion(sup_alta, uso_alta)
check(h_sin_planta_alta.confianza == ALTA,
      "sin planta, con todos los insumos Alta -> ocupacion Alta",
      h_sin_planta_alta.confianza)

planta_estimada_alta = hecho_planta("vivienda ALTA", numero=1, sobre_rasante=True,
                                     origen=ORIGEN_CONVENCION_NOMBRE)
h_con_planta_estimada = ocupacion(sup_alta, uso_alta, planta=planta_estimada_alta)
check(h_con_planta_estimada.confianza == MEDIA,
      "con planta ESTIMATED (Media) sobre el mismo caso, la confianza SI baja "
      "a Media: planta participa realmente en el eslabon mas debil",
      h_con_planta_estimada.confianza)

print("\n" + "=" * 60)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
