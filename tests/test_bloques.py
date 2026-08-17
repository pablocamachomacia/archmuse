# -*- coding: utf-8 -*-
"""Comprueba que se atraviesan las referencias de bloque (tarea 8 del PRD).

Ejecutar:  python tests/test_bloques.py

Rapido (~3 s), y enteramente sintetico POR NECESIDAD: ejemplo.dxf no tiene ni
un solo INSERT, asi que no hay ningun plano real contra el que contrastar esto.
Es la tarea del PRD que mas depende de conseguir DXF ajenos (tarea 2) y la que
menos garantias tiene hasta entonces. Estas pruebas confirman la logica; no
confirman que los bloques de otros estudios se parezcan a los que fabrico yo.

Lo que protege, por orden de gravedad si se rompiera:

  1. La resolucion de la capa "0". Una entidad dibujada en la capa 0 dentro de
     un bloque toma la capa del INSERT que la inserta -convencion DXF de toda
     la vida-, y ezdxf NO la aplica: virtual_entities() devuelve la capa
     literal. Comprobado antes de escribir el codigo. Sin esto, atravesar los
     bloques serviria de poco, porque dibujar las habitaciones en la capa 0
     dentro del bloque es justo lo mas habitual.
  2. Que las coordenadas lleguen transformadas: traslacion, rotacion y escala
     del INSERT. Un bloque insertado girado que se leyera sin girar daria
     habitaciones con la superficie correcta en el sitio equivocado, y eso no
     lo detecta ninguna comprobacion de areas.
  3. Que no se entre en bucle con bloques anidados.
"""
import math
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


CAPA = parser.AREA_LAYER


def nuevo():
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    doc.layers.add(CAPA)
    return doc


def estancias_en(destino, capa, n=5, ancho=4.0, alto=3.0, rotular=True):
    for i in range(n):
        x0 = i * 5.0
        destino.add_lwpolyline(
            [(x0, 0), (x0 + ancho, 0), (x0 + ancho, alto), (x0, alto)],
            close=True, dxfattribs={"layer": capa})
        if rotular:
            destino.add_mtext("Estancia %d" % (i + 1),
                              dxfattribs={"layer": capa}).set_location((x0 + ancho / 2, alto / 2))


def guardar(doc, tmp, nombre):
    ruta = os.path.join(tmp, nombre)
    doc.saveas(ruta)
    return parser.load_document(ruta)


def areas(plano):
    return sorted(round(r.area_m2, 4) for r in plano.rooms)


tmp = tempfile.mkdtemp(prefix="archmuse_bloq_")
try:
    # =======================================================================
    print("A. Habitaciones dentro de un bloque, con su propia capa")
    # =======================================================================
    doc = nuevo()
    bloque = doc.blocks.new(name="VIVIENDA")
    estancias_en(bloque, CAPA)
    doc.modelspace().add_blockref("VIVIENDA", (0, 0), dxfattribs={"layer": CAPA})
    d = guardar(doc, tmp, "bloque_simple.dxf")

    plano = parser.leer_plano(d)
    check(len(plano.rooms) == 5, "se leen las 5 estancias del bloque",
          "%d habitaciones" % len(plano.rooms))
    check(areas(plano) == [12.0] * 5, "con su superficie correcta", str(areas(plano)[:2]))
    check(sorted(r.label or "" for r in plano.rooms) == ["Estancia %d" % i for i in range(1, 6)],
          "y con su nombre, que tambien estaba dentro del bloque")

    # =======================================================================
    print()
    print("B. Capa 0 dentro del bloque -> hereda la del INSERT")
    # =======================================================================
    # Lo mas habitual: el bloque se dibuja en capa 0 y la capa se decide al
    # insertarlo. ezdxf devuelve la capa literal "0"; la herencia la hace
    # `_capa_efectiva`.
    doc = nuevo()
    bloque = doc.blocks.new(name="VIV0")
    estancias_en(bloque, "0")
    doc.modelspace().add_blockref("VIV0", (0, 0), dxfattribs={"layer": CAPA})
    d = guardar(doc, tmp, "capa_cero.dxf")

    capas = {c.nombre: c.n_poligonos for c in parser.capas_candidatas(d)}
    check(capas.get(CAPA) == 5, "los poligonos se atribuyen a la capa del INSERT",
          str(capas))
    check("0" not in capas, "y no se quedan en la capa 0", str(list(capas)))
    plano = parser.leer_plano(d)
    check(len(plano.rooms) == 5 and areas(plano) == [12.0] * 5,
          "leer_plano las encuentra", "%d habitaciones" % len(plano.rooms))

    # Pero una entidad que SI tiene capa propia conserva la suya: la herencia
    # es solo para la capa 0.
    doc = nuevo()
    doc.layers.add("MOBILIARIO")
    bloque = doc.blocks.new(name="MIXTO")
    estancias_en(bloque, "0")
    bloque.add_lwpolyline([(0, 10), (1, 10), (1, 11), (0, 11)], close=True,
                          dxfattribs={"layer": "MOBILIARIO"})
    doc.modelspace().add_blockref("MIXTO", (0, 0), dxfattribs={"layer": CAPA})
    d = guardar(doc, tmp, "mixto.dxf")
    capas = {k: len(v) for k, v in parser._poligonos_cerrados_por_capa(d).items()}
    check(capas.get(CAPA) == 5 and capas.get("MOBILIARIO") == 1,
          "una entidad con capa propia no la pierde", str(capas))

    # =======================================================================
    print()
    print("C. El INSERT transforma: traslacion, giro y escala")
    # =======================================================================
    doc = nuevo()
    bloque = doc.blocks.new(name="VIVT")
    estancias_en(bloque, CAPA)
    doc.modelspace().add_blockref("VIVT", (100, 50), dxfattribs={
        "layer": CAPA, "xscale": 2.0, "yscale": 2.0, "rotation": 90})
    d = guardar(doc, tmp, "transformado.dxf")

    plano = parser.leer_plano(d)
    check(areas(plano) == [48.0] * 5, "la escala x2 cuadruplica la superficie",
          str(areas(plano)[:2]))
    xs = [r.polygon.centroid.x for r in plano.rooms]
    ys = [r.polygon.centroid.y for r in plano.rooms]
    check(all(x < 100.01 for x in xs) and all(y > 49.9 for y in ys),
          "y aterrizan trasladadas y giradas 90 grados",
          "x en [%.1f, %.1f], y en [%.1f, %.1f]" % (min(xs), max(xs), min(ys), max(ys)))
    # Girado 90 grados, la fila de estancias que iba en X pasa a ir en Y.
    check(max(ys) - min(ys) > max(xs) - min(xs),
          "la fila se despliega ahora en vertical",
          "dY=%.1f > dX=%.1f" % (max(ys) - min(ys), max(xs) - min(xs)))

    # =======================================================================
    print()
    print("D. Anidamiento y casos limite")
    # =======================================================================
    doc = nuevo()
    hijo = doc.blocks.new(name="HIJO")
    estancias_en(hijo, "0")
    padre = doc.blocks.new(name="PADRE")
    padre.add_blockref("HIJO", (0, 0))
    doc.modelspace().add_blockref("PADRE", (0, 0), dxfattribs={"layer": CAPA})
    d = guardar(doc, tmp, "anidado.dxf")
    plano = parser.leer_plano(d)
    check(len(plano.rooms) == 5, "dos niveles de anidamiento se atraviesan",
          "%d habitaciones" % len(plano.rooms))
    check(areas(plano) == [12.0] * 5, "y la capa 0 se hereda a traves de los dos niveles")

    # Mas anidamiento del permitido: se corta, no se cuelga.
    doc = nuevo()
    ultimo = doc.blocks.new(name="N0")
    estancias_en(ultimo, "0")
    for i in range(1, 6):
        b = doc.blocks.new(name="N%d" % i)
        b.add_blockref("N%d" % (i - 1), (0, 0))
    doc.modelspace().add_blockref("N5", (0, 0), dxfattribs={"layer": CAPA})
    d = guardar(doc, tmp, "muy_anidado.dxf")
    poligonos = parser._poligonos_cerrados_por_capa(d)
    check(sum(len(v) for v in poligonos.values()) == 0,
          "por debajo de PROFUNDIDAD_MAX_BLOQUES se deja de bajar, sin colgarse",
          "%d poligonos (tope %d niveles)" % (sum(len(v) for v in poligonos.values()),
                                              parser.PROFUNDIDAD_MAX_BLOQUES))

    # Mezcla: unas estancias sueltas y otras dentro de un bloque.
    doc = nuevo()
    msp = doc.modelspace()
    estancias_en(msp, CAPA, n=3)
    bloque = doc.blocks.new(name="ALA")
    estancias_en(bloque, "0", n=2)
    msp.add_blockref("ALA", (0, 40), dxfattribs={"layer": CAPA})
    d = guardar(doc, tmp, "mezcla.dxf")
    plano = parser.leer_plano(d)
    check(len(plano.rooms) == 5, "se suman las sueltas y las del bloque",
          "%d habitaciones" % len(plano.rooms))
    check(len(parser.extract_labels(d)) == 5, "y los rotulos de dentro del bloque tambien",
          "%d rotulos" % len(parser.extract_labels(d)))

    # Un bloque vacio no estorba.
    doc = nuevo()
    msp = doc.modelspace()
    estancias_en(msp, CAPA)
    doc.blocks.new(name="VACIO")
    msp.add_blockref("VACIO", (0, 0), dxfattribs={"layer": CAPA})
    d = guardar(doc, tmp, "vacio.dxf")
    check(len(parser.leer_plano(d).rooms) == 5, "un bloque vacio no altera nada")

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
