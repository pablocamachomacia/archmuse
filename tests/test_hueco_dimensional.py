# -*- coding: utf-8 -*-
"""La superficie de hueco estimada tiene que ser una SUPERFICIE.

Ejecutar:  python tests/test_hueco_dimensional.py

Rapido (<1 s): todo son funciones puras sobre numeros, no hace falta DXF.

Que protege, y por que importa mas que la mayoria de los tests del repo:

Hasta 2026-08-05, los Bloques 15 y 19 calculaban el hueco como
`ancho_fachada * WINDOW_TO_FACADE_RATIO`. Metros por un numero adimensional
son metros, no metros cuadrados -- pero la variable se llamaba
`window_area_m2` y el resultado se dividia entre el area de la habitacion y
se comparaba contra 1/8, que es un porcentaje de SUPERFICIE. Se estaban
comparando magnitudes de dimension distinta.

El sintoma no era una excepcion. Era una regla que fallaba en el 93.8% de
las piezas de `ejemplo.dxf` citando el CTE DB-HS3 y mencionando la cedula de
habitabilidad, y que aportaba el 41% de todas las incidencias del proyecto.

La comprobacion 1 es la que de verdad importa: verifica la dimension por
ESCALADO, no comparando contra un numero fijo. Si alguien vuelve a quitar la
altura del hueco, el area dejara de escalar de forma cuadratica y este test
lo cazara aunque los umbrales se hayan recalibrado por otro motivo.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import evaluator as EV  # noqa: E402

fallos = []
comprobaciones = 0


def check(ok, etiqueta, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s%s" % ("OK  " if ok else "FALLO", etiqueta, ("  -> " + detalle) if detalle else ""))
    if not ok:
        fallos.append(etiqueta)


print()
print("A. La estimacion se comporta como una SUPERFICIE")
print("-" * 60)

# Una superficie escala con el CUADRADO de un factor lineal. Una longitud,
# solo linealmente. Duplicar la escala del dibujo (ancho x2, alto x2) tiene
# que multiplicar el hueco por 4, no por 2.
base = EV._superficie_hueco_estimada_m2(4.0)
doble_ancho = EV._superficie_hueco_estimada_m2(8.0)
check(abs(doble_ancho / base - 2.0) < 1e-9,
      "al doblar el ancho de fachada, el hueco se dobla",
      "%.4f -> %.4f" % (base, doble_ancho))

# La altura tiene que participar de verdad en el calculo: si no interviene,
# esto es una longitud disfrazada.
altura_original = EV.ALTURA_HUECO_ESTIMADA_M
try:
    EV.ALTURA_HUECO_ESTIMADA_M = altura_original * 2
    con_doble_altura = EV._superficie_hueco_estimada_m2(4.0)
finally:
    EV.ALTURA_HUECO_ESTIMADA_M = altura_original
check(abs(con_doble_altura / base - 2.0) < 1e-9,
      "al doblar la altura del hueco, el hueco se dobla",
      "si esto falla, la altura no interviene y el resultado son metros")

# Las dos juntas: escalado uniforme del plano -> area x4. Esta es la
# comprobacion que distingue una superficie de una longitud.
try:
    EV.ALTURA_HUECO_ESTIMADA_M = altura_original * 2
    escalado_uniforme = EV._superficie_hueco_estimada_m2(8.0)
finally:
    EV.ALTURA_HUECO_ESTIMADA_M = altura_original
check(abs(escalado_uniforme / base - 4.0) < 1e-9,
      "escalado uniforme x2 -> superficie x4 (dimension 2, no 1)",
      "ratio=%.4f, se esperaba 4.0" % (escalado_uniforme / base))

# Un valor concreto, para que el orden de magnitud sea legible: una fachada
# de 4 m con un cuarto acristalado y 1.30 m de altura de hueco son ~1.3 m2,
# que es una ventana de vivienda creible. Con la formula rota salian 1.0
# "m2" que en realidad era 1.0 m.
check(0.5 < base < 3.0,
      "el orden de magnitud es el de una ventana real",
      "fachada 4.00m -> %.2f m2" % base)


print()
print("B. El hueco se estima en UN solo sitio")
print("-" * 60)

# Cuando se escribio este test (tarea 1 del encargo de fiabilidad) habia dos
# reglas usando la estimacion: el Bloque 15 ("factor de luz natural", umbral
# 1.5%) y el Bloque 19 ("regla 1/8", 12.5%). La tarea 5 retiro el Bloque 15
# al comprobarse que, con valores reales entre el 5% y el 17%, su umbral no
# podia fallar nunca -- ver `tests/test_sin_duplicados.py`.
#
# Asi que el invariante ya no es "los dos comparten la funcion", sino el mas
# fuerte: SOLO UNO la usa, y nadie recalcula el hueco por su cuenta.
import inspect  # noqa: E402

src_b15 = inspect.getsource(EV.evaluate_natural_lighting)
src_b19 = inspect.getsource(EV.evaluate_window_opening_ratio)
check("_superficie_hueco_estimada_m2" in src_b19,
      "el Bloque 19 (regla 1/8) usa la funcion compartida")
check("_superficie_hueco_estimada_m2" not in src_b15,
      "el Bloque 15 ya no estima huecos: la regla se retiro por duplicada")
check("WINDOW_TO_FACADE_RATIO" not in src_b15 and "WINDOW_TO_FACADE_RATIO" not in src_b19,
      "ninguno recalcula el hueco por su cuenta",
      "si aparece la constante suelta en un bloque, la formula se ha vuelto a copiar")

# Y la constante solo puede consumirse desde la funcion compartida.
src_modulo = inspect.getsource(EV)
usos = src_modulo.count("WINDOW_TO_FACADE_RATIO")
check(usos == 2, "WINDOW_TO_FACADE_RATIO solo aparece al definirla y al usarla",
      "%d apariciones en evaluator.py" % usos)


print()
print("C. Regresion sobre geometria conocida")
print("-" * 60)

from shapely.geometry import Polygon  # noqa: E402

# Dormitorio rectangular de 3.20 x 2.65 m = 8.48 m2, el caso real de VT1/3.
# Fachada = lado largo = 3.20 m. Hueco = 3.20 * 0.25 * 1.30 = 1.04 m2.
# Ratio = 1.04 / 8.48 = 12.26% -> por debajo de 1/8 (12.5%), falla por poco.
dorm = Polygon([(0, 0), (3.20, 0), (3.20, 2.65), (0, 2.65)])
largo, corto = EV._bounding_sides(dorm)
hueco = EV._superficie_hueco_estimada_m2(largo)
ratio = hueco / dorm.area
check(abs(largo - 3.20) < 0.01, "lado largo detectado", "%.2f m" % largo)
check(abs(hueco - 1.04) < 0.01, "hueco estimado", "%.3f m2" % hueco)
check(ratio < EV.MIN_WINDOW_TO_FLOOR_RATIO,
      "un dormitorio de 8.48 m2 con 3.20 m de fachada no llega a 1/8",
      "%.2f%% < %.2f%%" % (ratio * 100, EV.MIN_WINDOW_TO_FLOOR_RATIO * 100))

# El margen es de 0.24 puntos porcentuales. Se deja escrito a proposito:
# cualquiera que retoque las dos constantes supuestas tiene que ver que hay
# hallazgos que se deciden por menos de medio punto.
check(EV.MIN_WINDOW_TO_FLOOR_RATIO - ratio < 0.005,
      "y lo hace por un margen inferior a medio punto porcentual",
      "margen=%.3f pp -- el resultado depende de dos constantes supuestas"
      % ((EV.MIN_WINDOW_TO_FLOOR_RATIO - ratio) * 100))

# Salon abierto: mas superficie por metro de fachada, falla con holgura.
salon = Polygon([(0, 0), (6.58, 0), (6.58, 3.55), (0, 3.55)])
ratio_salon = EV._superficie_hueco_estimada_m2(EV._bounding_sides(salon)[0]) / salon.area
check(ratio_salon < EV.MIN_WINDOW_TO_FLOOR_RATIO,
      "un salon-cocina de 23.4 m2 tampoco llega a 1/8",
      "%.2f%%" % (ratio_salon * 100))


print()
print("=" * 60)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
