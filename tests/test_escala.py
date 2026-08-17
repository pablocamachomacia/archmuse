# -*- coding: utf-8 -*-
"""Comprueba la deteccion de escala (tarea 3 del PRD de ingesta de DXF ajenos).

Ejecutar:  python tests/test_escala.py

Rapido (<1 s): `detectar_escala` es una funcion pura sobre numeros, asi que no
hay que fabricar ningun DXF salvo en el bloque E, que prueba la unica funcion
del modulo que toca ezdxf.

Lo que protege, por orden de gravedad si se rompiera:

  1. Que un plano en milimetros NUNCA se analice en silencio. Es el peor modo
     de fallo del proyecto: no revienta, devuelve una puntuacion alta y
     creible sobre areas multiplicadas por un millon.
  2. Que cuando la cabecera y el dibujo se contradicen, se PARE. Si en la duda
     se eligiera cualquiera de las dos, el modulo dejaria de servir para lo
     unico que lo justifica.
  3. Que dos hipotesis de unidad no puedan salir compatibles a la vez -- la
     garantia de separacion que hace que el rango de plausibilidad funcione.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import escala  # noqa: E402

fallos = []
comprobaciones = 0


def check(ok, etiqueta, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s%s" % ("OK  " if ok else "FALLO", etiqueta, ("  -> " + detalle) if detalle else ""))
    if not ok:
        fallos.append(etiqueta)


# Una vivienda verosimil, en metros: bano, cocina, dos dormitorios, salon.
VIVIENDA_M = [4.2, 8.5, 10.1, 12.4, 22.0, 6.3]
VIVIENDA_MM = [a * 1e6 for a in VIVIENDA_M]   # el mismo plano dibujado en mm
VIVIENDA_CM = [a * 1e4 for a in VIVIENDA_M]
VIVIENDA_DM = [a * 1e2 for a in VIVIENDA_M]

SIN_ESPECIFICAR, MM, CM, M, DM, PIES = 0, 4, 5, 6, 14, 2


# =======================================================================
print("A. Los seis desenlaces")
# =======================================================================

r = escala.detectar_escala(M, VIVIENDA_M)
check(r.origen == "acuerdo" and r.factor == 1.0, "cabecera y tamano coinciden -> acuerdo", r.origen)
check(r.decidida, "y se puede seguir sin preguntar")

r = escala.detectar_escala(SIN_ESPECIFICAR, VIVIENDA_MM)
check(r.origen == "plausibilidad" and r.unidad == "milímetros",
      "$INSUNITS=0 pero el tamano decide -> plausibilidad", "%s / %s" % (r.origen, r.unidad))
check(r.factor == 0.001, "con el factor correcto", str(r.factor))

r = escala.detectar_escala(M, [])
check(r.origen == "cabecera" and r.factor == 1.0, "sin estancias, manda la cabecera", r.origen)

r = escala.detectar_escala(SIN_ESPECIFICAR, [])
check(r.origen == "indecidible" and not r.decidida, "sin cabecera y sin estancias -> se para", r.origen)

r = escala.detectar_escala(PIES, VIVIENDA_M)
check(r.origen == "no_metrico" and not r.decidida, "unidades imperiales -> se para", r.origen)
check("CTE" in r.mensaje and "convier" in r.mensaje.lower(),
      "y se explica por que, con salida", r.mensaje[:60])

# =======================================================================
print()
print("B. El conflicto: la cabecera MIENTE (el caso que justifica el modulo)")
# =======================================================================

# Plantilla heredada que declara metros sobre un plano dibujado en milimetros.
# Hoy esto entraria como si nada y daria una puntuacion alta sobre areas
# multiplicadas por un millon.
r = escala.detectar_escala(M, VIVIENDA_MM)
check(r.origen == "conflicto", "cabecera dice metros, dibujo dice mm -> conflicto", r.origen)
check(not r.decidida, "NO se decide sola: hay que preguntar")
check(r.factor is None, "y no se filtra ningun factor utilizable", str(r.factor))
check(r.sugerencia == "milímetros", "la sugerencia sigue al DIBUJO, no a la cabecera", str(r.sugerencia))
check("imposible" in r.mensaje, "el mensaje dice por que es imposible", r.mensaje[:80])

# El conflicto simetrico: declara mm sobre un plano en metros.
r = escala.detectar_escala(MM, VIVIENDA_M)
check(r.origen == "conflicto" and r.sugerencia == "metros", "y tambien al reves", str(r.sugerencia))

# Centimetros y decimetros, que son los que se cuelan sin que nadie mire.
check(escala.detectar_escala(SIN_ESPECIFICAR, VIVIENDA_CM).unidad == "centímetros", "detecta centimetros")
check(escala.detectar_escala(SIN_ESPECIFICAR, VIVIENDA_DM).unidad == "decímetros", "detecta decimetros")

# =======================================================================
print()
print("C. Garantia de separacion: nunca dos hipotesis a la vez")
# =======================================================================

# Si dos unidades pudieran salir compatibles, `unidades_plausibles` no serviria
# para decidir nada y el bloque B se caeria entero. Barrido de 24 ordenes de
# magnitud, muy por encima de lo que cualquier DXF real puede producir.
peor = None
for exponente in range(-12, 13):
    for base in (1.0, 1.7, 2.5, 4.0, 6.3, 9.1):
        mediana = base * (10.0 ** exponente)
        n = len(escala.unidades_plausibles([mediana] * 5))
        if n > 1:
            peor = (mediana, n)
            break
check(peor is None, "ninguna mediana admite dos unidades a la vez", "peor caso: %s" % (peor,))
check(escala.AREA_PLAUSIBLE_MAX_M2 / escala.AREA_PLAUSIBLE_MIN_M2 < 100.0,
      "el rango se mantiene por debajo del factor 100 que lo garantiza",
      "%.0fx" % (escala.AREA_PLAUSIBLE_MAX_M2 / escala.AREA_PLAUSIBLE_MIN_M2))

# =======================================================================
print()
print("D. Casos limite")
# =======================================================================

check(escala.unidades_plausibles([12.0, 11.0]) == [],
      "con menos de 3 estancias no se deduce nada por tamano")
check(escala.unidades_plausibles([0.0, 0.0, 0.0, 12.0, 11.0, 10.0]) != [],
      "las areas nulas no cuentan pero no estorban")
check(escala.unidades_plausibles([-5.0, 12.0, 11.0, 10.0]) != [],
      "un area negativa tampoco rompe")

# La mediana aguanta un contorno agrupador enorme que aun no se ha descartado;
# la media no lo aguantaria.
con_contorno = VIVIENDA_M + [850.0]
check(escala.detectar_escala(M, con_contorno).origen == "acuerdo",
      "un contorno de planta enorme no desvia la mediana")

# Codigo metrico pero disparatado para un edificio: se ignora la cabecera.
KILOMETROS = 7
r = escala.detectar_escala(KILOMETROS, VIVIENDA_M)
check(r.origen == "plausibilidad" and r.unidad == "metros",
      "un $INSUNITS absurdo (km) se ignora y decide el tamano", "%s / %s" % (r.origen, r.unidad))

r = escala.detectar_escala(M, VIVIENDA_M)
check(r.factor_area == 1.0, "factor_area de metros es 1")
r = escala.detectar_escala(MM, VIVIENDA_MM)
check(abs(r.factor_area - 1e-6) < 1e-18, "factor_area de milimetros es el factor AL CUADRADO",
      str(r.factor_area))
check(escala.detectar_escala(M, VIVIENDA_MM).factor_area is None,
      "sin decision no hay factor_area")
check(escala.factor_de_unidad("varas") is None, "una unidad inventada no devuelve factor")
check(escala.factor_de_unidad("centímetros") == 0.01, "y una real si")

# =======================================================================
print()
print("E. Lectura de la cabecera (lo unico que toca ezdxf)")
# =======================================================================

import ezdxf  # noqa: E402

doc = ezdxf.new("R2010")
doc.header["$INSUNITS"] = MM
check(escala.leer_insunits(doc) == MM, "lee $INSUNITS de un documento real")


class CabeceraRota(object):
    class header(object):
        @staticmethod
        def get(*_args, **_kwargs):
            raise RuntimeError("cabecera corrupta")


check(escala.leer_insunits(CabeceraRota()) == 0, "una cabecera ilegible devuelve 0, no lanza")

# =======================================================================
print()
print("F. ejemplo.dxf y coherencia con el diagnostico")
# =======================================================================

# Mediana real de la capa "00 areas" de ejemplo.dxf, medida con
# `herramientas/diagnostico_dxf.py`. Se mete a mano para no parsear 19 MB.
r = escala.detectar_escala(M, [8.509] * 42)
check(r.origen == "acuerdo" and r.factor == 1.0,
      "ejemplo.dxf (mediana 8,509, $INSUNITS=6) -> acuerdo en metros", r.origen)

# El diagnostico duplica estos numeros a proposito (no importa de analyzer/),
# asi que hay que impedir que se separen: medir con una regla y publicar con
# otra seria una trampa.
from herramientas import diagnostico_dxf as diag  # noqa: E402

check(diag.AREA_PLAUSIBLE_MIN == escala.AREA_PLAUSIBLE_MIN_M2
      and diag.AREA_PLAUSIBLE_MAX == escala.AREA_PLAUSIBLE_MAX_M2,
      "el diagnostico usa el mismo rango de plausibilidad",
      "%s-%s vs %s-%s" % (diag.AREA_PLAUSIBLE_MIN, diag.AREA_PLAUSIBLE_MAX,
                          escala.AREA_PLAUSIBLE_MIN_M2, escala.AREA_PLAUSIBLE_MAX_M2))
check(diag.MINIMO_POLIGONOS == escala.MINIMO_ESTANCIAS_PARA_PLAUSIBILIDAD,
      "y el mismo minimo de estancias")
check(sorted(f for _n, f in diag.FACTORES_A_METRO)
      == sorted(f for _n, f in escala.UNIDADES_METRICAS.values()),
      "y los mismos factores de conversion")

# Mismo veredicto sobre los mismos numeros, pese a escribirse por separado.
for etiqueta, areas in (("metros", VIVIENDA_M), ("mm", VIVIENDA_MM), ("cm", VIVIENDA_CM)):
    mediana = sorted(areas)[len(areas) // 2 - 1:len(areas) // 2 + 1]
    mediana = sum(mediana) / 2.0
    del_diag = diag.hipotesis_de_escala(mediana, len(areas))
    del_modulo = escala.unidades_plausibles(areas)
    # El diagnostico escribe sin acentos (consola de Windows) y el modulo con
    # ellos (va a la interfaz): se comparan normalizados.
    normal = [u.replace("í", "i").replace("é", "e") for u in del_modulo]
    check(del_diag == normal, "coinciden en un plano en %s" % etiqueta,
          "%s vs %s" % (del_diag, normal))

print()
print("=" * 55)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
