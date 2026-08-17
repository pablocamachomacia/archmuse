# -*- coding: utf-8 -*-
"""Comprueba `parser.leer_plano` (tarea 4 del PRD de ingesta de DXF ajenos).

Ejecutar:  python tests/test_leer_plano.py

Rapido (~2 s): fabrica DXF sinteticos con ezdxf. El guardian sobre el archivo
real es `tests/test_ingesta_regresion.py`, que es lento y va aparte.

Lo que protege, por orden de gravedad si se rompiera:

  1. Que un plano en milimetros se convierta de verdad a metros. Es el defecto
     que justifica el modulo entero.
  2. Que la escala se aplique a las etiquetas de vivienda ADEMAS de a las
     habitaciones. Escalar solo la mitad agrupa mal las viviendas y no da
     ningun error: el informe sale entero y equivocado.
  3. Que el escalado sea desde el origen y no desde el centro de cada
     poligono. Con `origin='center'` -el valor por defecto de shapely- las
     areas saldrian correctas y el plano quedaria despedazado, cada habitacion
     encogida sobre si misma en su sitio original.
  4. Que un plano indecidible se NIEGUE a analizarse en vez de suponer metros.
"""
import os
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import ezdxf  # noqa: E402

from analyzer import parser  # noqa: E402

fallos = []
comprobaciones = 0


def check(ok, etiqueta, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s%s" % ("OK  " if ok else "FALLO", etiqueta, ("  -> " + detalle) if detalle else ""))
    if not ok:
        fallos.append(etiqueta)


# Vivienda de referencia EN METROS: cinco estancias en fila, cada una de
# 4 x 3 m = 12 m², separadas 1 m, con la etiqueta de vivienda a la izquierda.
ESTANCIAS = [("Dormitorio 1", 0.0), ("Dormitorio 2", 5.0), ("Salon", 10.0),
             ("Cocina", 15.0), ("Bano", 20.0)]
ANCHO, FONDO = 4.0, 3.0
VT_X, VT_Y = -3.0, 1.5


def construir(ruta, escala=1.0, insunits=6):
    """El mismo plano dibujado en la unidad que se pida. Con escala=1000 e
    insunits=4 es exactamente el mismo edificio, en milimetros."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = insunits
    doc.layers.add(parser.AREA_LAYER)
    msp = doc.modelspace()

    for nombre, x0 in ESTANCIAS:
        puntos = [((x0 + dx) * escala, dy * escala) for dx, dy in
                  ((0, 0), (ANCHO, 0), (ANCHO, FONDO), (0, FONDO))]
        msp.add_lwpolyline(puntos, close=True, dxfattribs={"layer": parser.AREA_LAYER})
        msp.add_mtext(nombre, dxfattribs={"layer": parser.AREA_LAYER}).set_location(
            ((x0 + ANCHO / 2) * escala, (FONDO / 2) * escala))

    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.AREA_LAYER}).set_location(
        (VT_X * escala, VT_Y * escala))
    doc.saveas(ruta)
    return ruta


def areas(plano):
    return sorted(round(r.area_m2, 6) for r in plano.rooms)


tmp = tempfile.mkdtemp(prefix="archmuse_plano_")
try:
    # =======================================================================
    print("A. El plano en metros no se toca")
    # =======================================================================
    en_m = parser.leer_plano(parser.load_document(construir(os.path.join(tmp, "m.dxf"))))
    check(len(en_m.rooms) == 5, "5 estancias", str(len(en_m.rooms)))
    check(areas(en_m) == [12.0] * 5, "de 12 m2 cada una", str(areas(en_m)[:2]))
    check(en_m.escala.factor == 1.0 and en_m.escala.origen == "acuerdo",
          "escala 1.0 por acuerdo", en_m.escala.origen)
    check(en_m.unit_labels == [("VT1/1", VT_X, VT_Y)], "etiqueta VT intacta", str(en_m.unit_labels))

    # =======================================================================
    print()
    print("B. El mismo plano en milimetros da EXACTAMENTE lo mismo")
    # =======================================================================
    # Sin la conversion, cada estancia entraria como 12.000.000 m2.
    en_mm = parser.leer_plano(parser.load_document(
        construir(os.path.join(tmp, "mm.dxf"), escala=1000.0, insunits=4)))
    check(en_mm.escala.factor == 0.001, "detecta milimetros", str(en_mm.escala.factor))
    check(areas(en_mm) == [12.0] * 5, "las areas salen en m2, no en mm2", str(areas(en_mm)[:2]))
    check(areas(en_mm) == areas(en_m), "identicas a las del plano en metros")

    # (3) Escalado desde el ORIGEN, no desde el centro de cada poligono. Con
    # `origin='center'` las areas serian correctas y el plano quedaria
    # despedazado: cada habitacion encogida en su sitio original, a kilometros
    # de las demas. Comparar posiciones es lo unico que lo detecta.
    pos_m = sorted((round(r.polygon.centroid.x, 6), round(r.polygon.centroid.y, 6))
                   for r in en_m.rooms)
    pos_mm = sorted((round(r.polygon.centroid.x, 6), round(r.polygon.centroid.y, 6))
                    for r in en_mm.rooms)
    check(pos_m == pos_mm, "y cada estancia cae en el mismo sitio",
          "%s vs %s" % (pos_mm[0], pos_m[0]))

    # (2) La escala tiene que llegar tambien a las etiquetas de vivienda. Si no,
    # la etiqueta se queda en (-3000, 1500) mientras las habitaciones estan
    # alrededor del origen: `group_rooms_by_unit_label` mide distancias entre
    # unas y otras y agruparia mal, sin dar ningun error.
    check(en_mm.unit_labels == en_m.unit_labels,
          "la etiqueta VT se escala igual que la geometria", str(en_mm.unit_labels))

    # Y las habitaciones conservan su nombre: la escala no toca el rotulado.
    check(sorted(r.label for r in en_mm.rooms) == sorted(r.label for r in en_m.rooms),
          "los nombres de estancia no cambian")

    # Centimetros, por si el factor estuviera escrito a mano en algun sitio.
    en_cm = parser.leer_plano(parser.load_document(
        construir(os.path.join(tmp, "cm.dxf"), escala=100.0, insunits=5)))
    check(areas(en_cm) == [12.0] * 5, "y lo mismo en centimetros", str(areas(en_cm)[:1]))

    # =======================================================================
    print()
    print("C. Cuando no se sabe, se para")
    # =======================================================================
    # Plantilla que declara metros sobre un dibujo en milimetros.
    ruta_mentira = construir(os.path.join(tmp, "mentira.dxf"), escala=1000.0, insunits=6)
    try:
        parser.leer_plano(parser.load_document(ruta_mentira))
        check(False, "cabecera que miente -> EscalaIndeterminada", "no lanzo nada")
    except parser.EscalaIndeterminada as exc:
        check(True, "cabecera que miente -> EscalaIndeterminada")
        check(exc.deteccion.sugerencia == "milímetros", "con la sugerencia correcta",
              str(exc.deteccion.sugerencia))
        check("imposible" in str(exc), "y un mensaje que explica por que", str(exc)[:70])
        check(isinstance(exc, ValueError), "es un ValueError: los callers antiguos lo cazan")

    # Y con la unidad confirmada por el arquitecto, el mismo archivo entra bien.
    confirmado = parser.leer_plano(parser.load_document(ruta_mentira), factor_escala=0.001)
    check(areas(confirmado) == [12.0] * 5, "confirmando la unidad, ese archivo se analiza",
          str(areas(confirmado)[:1]))
    check(confirmado.escala.origen == "confirmada", "y queda registrado quien lo decidio",
          confirmado.escala.origen)

    # =======================================================================
    print()
    print("D. La lectura en crudo sigue siendo en crudo")
    # =======================================================================
    # `build_rooms_from_document` NO debe convertir: es el escalon de abajo, y
    # el guardian de regresion se apoya en que no cambie.
    doc_mm = parser.load_document(os.path.join(tmp, "mm.dxf"))
    crudas = parser.build_rooms_from_document(doc_mm)
    check(round(crudas[0].area_m2) == 12000000,
          "build_rooms_from_document devuelve unidades de dibujo",
          "%.0f" % crudas[0].area_m2)
    check(parser.extract_unit_labels(doc_mm)[0][1] == VT_X * 1000.0,
          "extract_unit_labels tambien")

finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
print("=" * 55)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
