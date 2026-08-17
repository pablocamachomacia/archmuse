# -*- coding: utf-8 -*-
"""CAP-5: el hecho `altura_evacuacion`, su normalizador y su formula.

Ejecutar:  python tests/test_altura_evacuacion.py

Rapido (<1 s): funciones puras, sin DXF, sin Flask, sin IA.

Que protege:

1. **La prohibicion central de CAP-5**: ningun camino de codigo produce
   `KNOWN` sin `origen="declarado"`. La altura de evacuacion normativa exige
   origen de evacuacion, salida de edificio y cota real — ninguno modelado
   (PRD §4bis, criterio de aceptacion 6).
2. Las dos unicas fuentes: declarada (`KNOWN`/Alta) e hipotesis
   `(plantas - 1) x altura_libre_m` (`ESTIMATED`/**Baja**, no Media).
3. La precedencia declaracion > hipotesis, con la hipotesis descartada
   registrada en `diagnostico` (CU7).
4. Las combinaciones parciales de §4quater: un solo factor nunca sostiene
   una hipotesis.
5. El normalizador no convierte en altura ni el 0, ni un negativo, ni un
   texto no numerico.
6. `NO_APLICABLE` no se usa para este hecho: todo edificio tiene una altura
   de evacuacion real, aunque ArchMuse no la conozca.
7. La cita: `referencia_normativa` es el `concept_id` del Anejo SI A ya
   ingerido, no una definicion inventada.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer.altura_evacuacion import (  # noqa: E402
    ALTURA_NO_DISPONIBLE,
    CONCEPT_ID_ALTURA_EVACUACION,
    ORIGEN_DECLARADO,
    ORIGEN_HIPOTESIS_PLANTAS,
    altura_evacuacion,
    estimar_por_plantas,
    normalizar_declaracion_altura,
    resolver_altura_evacuacion,
)
from analyzer.hechos import ALTA, BAJA, ESTIMATED, KNOWN, MEDIA, UNKNOWN  # noqa: E402

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


print("A. Normalizador -- lo que si es una altura declarada")

CASOS_VALIDOS = [
    ("17.5", 17.5),
    ("17,5", 17.5),          # coma decimal: el formulario es espanol
    ("  17,5  ", 17.5),
    ("17,5 m", 17.5),        # sufijo de unidad, que es lo que se escribe
    ("28", 28.0),
    ("0,5", 0.5),
    (14, 14.0),              # numero, no texto (JSON de /api/generar)
    (14.0, 14.0),
]
for entrada, esperado in CASOS_VALIDOS:
    got = normalizar_declaracion_altura(entrada)
    check(got == esperado, "%r -> %r" % (entrada, esperado), "obtenido %r" % (got,))

print("\nB. Normalizador -- nunca inventa una altura")

CASOS_INVALIDOS = [
    None, "", "   ", "alta", "planta 6", "?", "seis metros",
    "0", "0,0", 0, 0.0,          # 0 m no es admisible para un edificio declarado
    "-3", "-3,5", -3, -3.5,      # negativo tampoco
    True, False,                 # bool es subclase de int: no debe dar 1.0 m
    "17,5,2", "1e3",
]
for entrada in CASOS_INVALIDOS:
    got = normalizar_declaracion_altura(entrada)
    check(got is None, "%r no se interpreta como altura" % (entrada,),
          "obtenido %r" % (got,))

print("\nC. La formula -- (plantas - 1) x altura_libre_m, y sus limites")

check(estimar_por_plantas(6, 2.8) == 14.0,
      "6 plantas x 2,80 m -> 14,00 m (cruza justo el umbral de C11)",
      estimar_por_plantas(6, 2.8))
check(abs(estimar_por_plantas(3, 2.8) - 5.6) < 1e-9,
      "3 plantas x 2,80 m -> 5,60 m", estimar_por_plantas(3, 2.8))
check(estimar_por_plantas(1, 2.8) == 0.0,
      "1 planta -> 0,00 m: origen y salida al mismo nivel, no es una ausencia",
      estimar_por_plantas(1, 2.8))
check(estimar_por_plantas(11, 3.0) == 30.0,
      "11 plantas x 3,00 m -> 30,00 m (supera los tres umbrales)")

# §4quater: no hay hipotesis parcial. La formula exige los DOS factores.
for plantas, libre, motivo in [
    (None, 2.8, "sin plantas"),
    (6, None, "sin altura libre"),
    (None, None, "sin ninguno de los dos"),
    (0, 2.8, "plantas = 0 (no es un edificio)"),
    (-2, 2.8, "plantas negativas"),
    (6, 0, "altura libre 0"),
    (6, -2.8, "altura libre negativa"),
    ("seis", 2.8, "plantas no numerico"),
]:
    check(estimar_por_plantas(plantas, libre) is None,
          "sin hipotesis %s" % motivo,
          "obtenido %r" % (estimar_por_plantas(plantas, libre),))

print("\nD. El hecho -- declarada: KNOWN, confianza Alta, y nada mas llega ahi")

h_dec = altura_evacuacion("edificio", valor_m=17.5, origen=ORIGEN_DECLARADO)
check(h_dec.estado == KNOWN, "declarada -> KNOWN", h_dec.estado)
check(h_dec.valor == 17.5, "conserva el valor declarado", h_dec.valor)
check(h_dec.confianza == ALTA, "declarada -> confianza Alta", h_dec.confianza)
check(h_dec.nombre == "altura_evacuacion", "nombre del hecho", h_dec.nombre)
check(h_dec.ambito == "edificio",
      "ambito EDIFICIO, no vivienda ni planta (PRD §4)", h_dec.ambito)
check(h_dec.unidad == "m", "unidad en metros", h_dec.unidad)
check(h_dec.referencia_normativa == CONCEPT_ID_ALTURA_EVACUACION,
      "cita el concept_id del Anejo SI A ya ingerido",
      h_dec.referencia_normativa)
check(h_dec.diagnostico.get("origen") == ORIGEN_DECLARADO,
      "origen trazable en el propio Hecho")
check(h_dec.motivo_principal is None, "KNOWN no lleva motivo de ausencia")
check(bool(h_dec.explicacion), "explicacion no vacia")

print("\nE. El hecho -- hipotesis: ESTIMATED, confianza BAJA (no Media)")

h_est = altura_evacuacion("edificio", valor_m=14.0,
                          origen=ORIGEN_HIPOTESIS_PLANTAS,
                          plantas=6, altura_libre_m=2.8)
check(h_est.estado == ESTIMATED, "hipotesis -> ESTIMATED, nunca KNOWN", h_est.estado)
check(h_est.confianza == BAJA,
      "hipotesis -> confianza BAJA, no Media como CAP-2/CAP-4: la formula "
      "SIEMPRE se desvia, con sesgo conocido y en dos direcciones (PRD §4quinquies)",
      h_est.confianza)
check(h_est.confianza != MEDIA, "explicitamente NO es Media")
check(h_est.procedencia and h_est.procedencia[0].startswith("HIPOTESIS:"),
      "procedencia con el prefijo 'HIPOTESIS:', mismo patron que planta()",
      h_est.procedencia)
check(h_est.diagnostico.get("plantas") == 6
      and h_est.diagnostico.get("altura_libre_m") == 2.8,
      "diagnostico guarda los DOS factores brutos: trazabilidad hasta el "
      "dato de formulario", h_est.diagnostico)
check("forjado" in h_est.explicacion.lower(),
      "la explicacion advierte del canto de forjado (subestima)")
check("ocupacion nula" in h_est.explicacion.lower(),
      "la explicacion advierte de las plantas de ocupacion nula (P5.4: se "
      "advierte, no se aproxima)")
check(h_est.tipo == "derivado", "la hipotesis es un hecho derivado", h_est.tipo)

print("\nF. El hecho -- desconocida: UNKNOWN con motivo, nunca NO_APLICABLE")

h_unk = altura_evacuacion("edificio")
check(h_unk.estado == UNKNOWN, "sin fuente -> UNKNOWN", h_unk.estado)
check(h_unk.valor is None, "UNKNOWN no publica valor")
check(h_unk.confianza is None, "UNKNOWN sin confianza")
check(h_unk.motivo_principal is not None
      and h_unk.motivo_principal.codigo == ALTURA_NO_DISPONIBLE,
      "UNKNOWN lleva motivo estructurado con codigo estable",
      h_unk.motivo_principal)
check(h_unk.diagnostico.get("origen") is None, "UNKNOWN sin origen")

h_unk_motivo = altura_evacuacion(
    "edificio", motivo_no_disponible="texto raro no interpretable")
check(h_unk_motivo.motivo_principal.detalle == "texto raro no interpretable",
      "quien llama puede distinguir 'no declarada' de 'no interpretable'")

check("NO_APLICABLE" not in (h_dec.estado, h_est.estado, h_unk.estado),
      "NO_APLICABLE no se usa: todo edificio tiene altura de evacuacion real")

print("\nG. PROHIBICION CENTRAL -- ningun KNOWN sin origen='declarado'")

try:
    altura_evacuacion("edificio", valor_m=20.0, origen="geometria")
    check(False, "origen no reconocido debe levantar ValueError")
except ValueError:
    check(True, "origen 'geometria' levanta ValueError -- la prohibicion esta "
                "en la forma de la interfaz, no en como se use")

try:
    altura_evacuacion("edificio", valor_m=20.0, origen=None)
    check(False, "valor sin origen debe levantar ValueError")
except ValueError:
    check(True, "valor sin origen levanta ValueError: no hay fuente implicita")

try:
    altura_evacuacion("edificio", valor_m=14.0, origen=ORIGEN_HIPOTESIS_PLANTAS)
    check(False, "hipotesis sin factores brutos debe levantar ValueError")
except ValueError:
    check(True, "hipotesis sin los factores brutos levanta ValueError: la "
                "trazabilidad no es opcional")

# Barrido exhaustivo sobre `resolver_altura_evacuacion`, que es la puerta que
# usan los dos endpoints: ninguna combinacion de entradas SIN declaracion
# puede salir KNOWN.
combinaciones_sin_declaracion = [
    (None, None), (6, None), (None, 2.8), (6, 2.8), (1, 2.8),
    (99, 3.5), (0, 2.8), (6, 0),
]
for plantas, libre in combinaciones_sin_declaracion:
    h = resolver_altura_evacuacion("edificio", plantas=plantas, altura_libre_m=libre)
    check(h.estado != KNOWN,
          "sin declaracion (plantas=%r, libre=%r) -> nunca KNOWN" % (plantas, libre),
          h.estado)
    if h.estado == ESTIMATED:
        check(h.diagnostico.get("origen") == ORIGEN_HIPOTESIS_PLANTAS,
              "  ...y si hay valor, el origen es la hipotesis, no 'declarado'")

print("\nH. Precedencia -- la declaracion gana, la hipotesis queda registrada (CU7)")

h_ambas = resolver_altura_evacuacion(
    "edificio", valor_declarado_m=22.0, plantas=6, altura_libre_m=2.8)
check(h_ambas.estado == KNOWN, "con ambas fuentes -> KNOWN (la declarada)",
      h_ambas.estado)
check(h_ambas.valor == 22.0, "prevalece el valor declarado, no el estimado (14,0)",
      h_ambas.valor)
check(h_ambas.confianza == ALTA, "confianza Alta, no la Baja de la hipotesis")
descartada = h_ambas.diagnostico.get("hipotesis_descartada")
check(descartada is not None and descartada.get("valor_m") == 14.0,
      "la hipotesis descartada queda registrada en diagnostico, auditable, "
      "pero no se presenta como conflicto (no son dos fuentes del mismo rango)",
      descartada)

h_solo_dec = resolver_altura_evacuacion("edificio", valor_declarado_m=22.0)
check(h_solo_dec.diagnostico.get("hipotesis_descartada") is None,
      "sin factores no hay hipotesis descartada que registrar")

print("\nI. /api/analizar -- la ausencia de hipotesis es estructural")

# El flujo DXF llama SIN plantas/altura_libre_m porque no tiene equivalente.
h_dxf = resolver_altura_evacuacion("edificio")
check(h_dxf.estado == UNKNOWN,
      "sin declaracion y sin factores -> UNKNOWN (caso por defecto de todo "
      "proyecto DXF, incluido ejemplo.dxf)", h_dxf.estado)

h_dxf_dec = resolver_altura_evacuacion("edificio", valor_declarado_m=17.5)
check(h_dxf_dec.estado == KNOWN,
      "P5.3: una declaracion directa SI se admite tambien en el flujo DXF")

print("\nJ. Hipotesis a traves del resolutor, extremo a extremo")

h_gen = resolver_altura_evacuacion("edificio", plantas=6, altura_libre_m=2.8)
check(h_gen.estado == ESTIMATED and h_gen.valor == 14.0,
      "6 plantas / 2,80 m sin declarar -> ESTIMATED 14,00 m", h_gen.valor)
check(h_gen.diagnostico.get("formula") == "(plantas - 1) x altura_libre_m",
      "la formula viaja en el diagnostico, citable y revisable",
      h_gen.diagnostico.get("formula"))

h_gen_1 = resolver_altura_evacuacion("edificio", plantas=1, altura_libre_m=2.8)
check(h_gen_1.estado == ESTIMATED and h_gen_1.valor == 0.0,
      "1 planta -> ESTIMATED 0,00 m (valor correcto, no UNKNOWN)", h_gen_1.valor)

print("\n" + "=" * 60)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
