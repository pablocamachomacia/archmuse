# -*- coding: utf-8 -*-
"""Comprueba la lectura de rotulos MTEXT y TEXT (tarea 7 del PRD de ingesta).

Ejecutar:  python tests/test_etiquetas.py

Rapido (~2 s). El guardian sobre ejemplo.dxf va aparte y es lento.

Lo que protege, por orden de gravedad si se rompiera:

  1. Que un MTEXT gane a un TEXT dentro de la misma habitacion. Sin esa
     prioridad, ejemplo.dxf renombra dos estancias con marcas de carpinteria
     ('PE-01', 'VE-01') y el tipo de habitacion es de donde cuelga medio motor
     de reglas. No es hipotetico: esas cinco marcas estan en el archivo y dos
     caen dentro de una habitacion. Se comprobo antes de escribir el codigo.
  2. Que un TEXT alineado se situe por su align_point y no por su insert. Un
     rotulo centrado dentro de la estancia -que es como se rotula media
     Espana- aterriza si no en un sitio que no es, y se asocia a la
     habitacion equivocada sin dar ningun error.
  3. Que un plano rotulado SOLO con TEXT deje de salir con las habitaciones
     sin nombre, que es el objeto de la tarea.
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


def rect(msp, capa, x0, y0, ancho=4.0, alto=3.0):
    msp.add_lwpolyline(
        [(x0, y0), (x0 + ancho, y0), (x0 + ancho, y0 + alto), (x0, y0 + alto)],
        close=True, dxfattribs={"layer": capa})


def nuevo():
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    doc.layers.add(parser.AREA_LAYER)
    return doc, doc.modelspace()


def guardar(doc, tmp, nombre):
    ruta = os.path.join(tmp, nombre)
    doc.saveas(ruta)
    return parser.load_document(ruta)


tmp = tempfile.mkdtemp(prefix="archmuse_etiq_")
try:
    # =======================================================================
    print("A. Un plano rotulado SOLO con TEXT")
    # =======================================================================
    doc, msp = nuevo()
    for i in range(5):
        x0 = i * 5.0
        rect(msp, parser.AREA_LAYER, x0, 0)
        msp.add_text("Dormitorio %d" % (i + 1),
                     dxfattribs={"layer": parser.AREA_LAYER, "insert": (x0 + 2.0, 1.5)})
    msp.add_text("VT1/1", dxfattribs={"layer": parser.AREA_LAYER, "insert": (-3.0, 1.5)})
    d = guardar(doc, tmp, "solo_text.dxf")

    plano = parser.leer_plano(d)
    nombres = sorted(r.label or "" for r in plano.rooms)
    check(nombres == ["Dormitorio %d" % i for i in range(1, 6)],
          "las estancias salen con su nombre", str(nombres[:2]))
    check(plano.unit_labels == [("VT1/1", -3.0, 1.5)],
          "y la etiqueta de vivienda tambien vale como TEXT", str(plano.unit_labels))

    # Antes esta capa puntuaba como si no tuviera rotulos.
    cands = parser.capas_candidatas(d)
    check(cands and cands[0].proporcion_rotulada == 1.0,
          "la capa puntua como rotulada, no como mobiliario",
          "%.0f%%" % (cands[0].proporcion_rotulada * 100))

    # =======================================================================
    print()
    print("B. Prioridad: MTEXT gana a TEXT en la misma habitacion")
    # =======================================================================
    # Reproduce lo que pasa en ejemplo.dxf: el nombre en MTEXT y una marca de
    # carpinteria en TEXT, las dos dentro del mismo poligono.
    doc, msp = nuevo()
    for i in range(4):
        x0 = i * 5.0
        rect(msp, parser.AREA_LAYER, x0, 0)
        # La marca se anade PRIMERO, para que ganar no dependa del orden en
        # que esten escritas las entidades dentro del archivo.
        msp.add_text("PE-0%d" % (i + 1),
                     dxfattribs={"layer": parser.AREA_LAYER, "insert": (x0 + 1.0, 1.0)})
        msp.add_mtext("Salon %d" % (i + 1),
                      dxfattribs={"layer": parser.AREA_LAYER}).set_location((x0 + 2.0, 1.5))
    d = guardar(doc, tmp, "prioridad.dxf")

    plano = parser.leer_plano(d)
    nombres = sorted(r.label or "" for r in plano.rooms)
    check(all(n.startswith("Salon") for n in nombres),
          "ninguna estancia se llama como la marca de carpinteria", str(nombres))

    etiquetas = parser.extract_labels(d)
    corte = [i for i, e in enumerate(etiquetas) if e[0].startswith("PE-")]
    check(corte and min(corte) == 4, "extract_labels devuelve los MTEXT antes que los TEXT",
          "primer TEXT en la posicion %d de %d" % (min(corte), len(etiquetas)))

    # =======================================================================
    print()
    print("C. Un TEXT alineado se situa por align_point")
    # =======================================================================
    # Cuatro estancias: `MINIMO_POLIGONOS_CAPA` descarta una capa con menos,
    # asi que dos no bastan para que la capa se considere siquiera candidata.
    doc, msp = nuevo()
    for x0 in (0, 5, 20, 25):                   # dos cerca del origen, dos lejos
        rect(msp, parser.AREA_LAYER, x0, 0)
        if x0 != 20:
            # Las demas llevan su propio nombre dentro. Sin esto heredarian
            # todas el rotulo de la otra punta del plano, porque el repliegue
            # de `match_label_to_room` no tiene limite de distancia — defecto
            # real, verificado aqui, y objeto de la tarea 9 del PRD.
            msp.add_mtext("Otra %d" % x0,
                          dxfattribs={"layer": parser.AREA_LAYER}).set_location((x0 + 2.0, 1.5))

    # Rotulo centrado: AutoCAD deja el punto real en align_point y en insert
    # un valor que no sirve. Si se leyera `insert`, este texto caeria en la
    # PRIMERA habitacion en vez de en la segunda.
    t = msp.add_text("Cocina", dxfattribs={"layer": parser.AREA_LAYER})
    t.dxf.insert = (2.0, 1.5)
    t.dxf.align_point = (22.0, 1.5)
    t.dxf.halign = 1
    t.dxf.valign = 2
    d = guardar(doc, tmp, "alineado.dxf")

    punto = [e for e in parser.extract_labels(d) if e[0] == "Cocina"][0]
    check((round(punto[1], 3), round(punto[2], 3)) == (22.0, 1.5),
          "se usa align_point cuando halign/valign no son cero", str(punto[1:]))

    cocina = [r for r in parser.leer_plano(d).rooms if (r.label or "") == "Cocina"]
    check(len(cocina) == 1 and cocina[0].polygon.centroid.x > 20,
          "y el rotulo cae en la habitacion correcta",
          "" if not cocina else "centroide x=%.1f" % cocina[0].polygon.centroid.x)

    # Y al reves: con halign y valign a cero, align_point se ignora aunque este.
    doc, msp = nuevo()
    for x0 in (0, 5, 20, 25):
        rect(msp, parser.AREA_LAYER, x0, 0)
    t = msp.add_text("Bano", dxfattribs={"layer": parser.AREA_LAYER})
    t.dxf.insert = (2.0, 1.5)
    t.dxf.align_point = (22.0, 1.5)
    d = guardar(doc, tmp, "sin_alinear.dxf")
    punto = [e for e in parser.extract_labels(d) if e[0] == "Bano"][0]
    check((round(punto[1], 3), round(punto[2], 3)) == (2.0, 1.5),
          "sin alineacion manda insert, aunque align_point exista", str(punto[1:]))

    # =======================================================================
    print()
    print("D. Casos limite")
    # =======================================================================
    doc, msp = nuevo()
    for i in range(4):
        rect(msp, parser.AREA_LAYER, i * 5.0, 0)
    msp.add_text("   ", dxfattribs={"layer": parser.AREA_LAYER, "insert": (2.0, 1.5)})
    msp.add_text("Giro 90%%d", dxfattribs={"layer": parser.AREA_LAYER, "insert": (7.0, 1.5)})
    d = guardar(doc, tmp, "raros.dxf")
    etiquetas = parser.extract_labels(d)
    check(all(e[0].strip() for e in etiquetas), "un TEXT vacio no se cuela",
          "%d etiquetas" % len(etiquetas))
    grados = [e[0] for e in etiquetas if e[0].startswith("Giro")]
    check(grados and "%%d" not in grados[0], "los codigos de formato se resuelven",
          str(grados))

    # Sin ningun rotulo: las habitaciones se leen igual, sin nombre.
    doc, msp = nuevo()
    for i in range(4):
        rect(msp, parser.AREA_LAYER, i * 5.0, 0)
    d = guardar(doc, tmp, "sin_rotulos.dxf")
    check(parser.extract_labels(d) == [], "un plano sin rotulos devuelve lista vacia")
    check(len(parser.leer_plano(d).rooms) == 4, "y las habitaciones se leen igual")

    # =======================================================================
    print()
    print("E. El repliegue esta acotado (tarea 9)")
    # =======================================================================
    # Cuatro estancias y UN solo rotulo, dentro de la ultima. Antes las cuatro
    # se llamaban igual: la que lo tenia dentro, y las otras tres por el
    # repliegue sin limite. En un plano con varias viviendas eso significa
    # heredar el nombre de otra vivienda.
    doc, msp = nuevo()
    for x0 in (0, 5, 10, 60):
        rect(msp, parser.AREA_LAYER, x0, 0)
    msp.add_mtext("Cocina", dxfattribs={"layer": parser.AREA_LAYER}).set_location((62.0, 1.5))
    d = guardar(doc, tmp, "lejano.dxf")

    rooms = parser.leer_plano(d).rooms
    con_nombre = [r for r in rooms if r.label]
    check(len(con_nombre) == 1 and con_nombre[0].polygon.centroid.x > 60,
          "un rotulo lejano ya no contagia a las demas estancias",
          "%d de %d con nombre" % (len(con_nombre), len(rooms)))
    check(sum(1 for r in rooms if r.label is None) == 3,
          "las otras tres se quedan sin nombre, que es lo correcto")

    # Pero un rotulo sacado con directriz, justo al lado, SI se acepta: el
    # limite es "a las afueras de la estancia", no "dentro o nada".
    doc, msp = nuevo()
    for x0 in (0, 5, 10, 15):
        rect(msp, parser.AREA_LAYER, x0, 0)
    msp.add_mtext("Aseo", dxfattribs={"layer": parser.AREA_LAYER}).set_location((2.0, 4.0))
    d = guardar(doc, tmp, "directriz.dxf")
    aseos = [r for r in parser.leer_plano(d).rooms if r.label == "Aseo"]
    check(len(aseos) == 1, "un rotulo justo fuera de la estancia si se asocia",
          "%d estancias lo reciben" % len(aseos))
    # Con este fixture solo lo recibe una, pero por la geometria concreta: el
    # limite hace la busqueda LOCAL, no EXCLUSIVA (ver TOLERANCIA_ETIQUETA).
    # Con la tolerancia a 1.0 la estancia contigua tambien se lo quedaba, a
    # 3,16 de distancia. No se prueba como si estuviera resuelto.

    # El limite es RELATIVO, asi que el mismo plano en milimetros decide igual.
    # Un umbral absoluto en metros no valdria: match_label_to_room trabaja en
    # unidades de dibujo, antes de la conversion de escala.
    doc, msp = nuevo()
    doc.header["$INSUNITS"] = 4
    for x0 in (0, 5000, 10000, 60000):
        rect(msp, parser.AREA_LAYER, x0, 0, 4000, 3000)
    msp.add_mtext("Cocina", dxfattribs={"layer": parser.AREA_LAYER}).set_location((62000.0, 1500.0))
    d = guardar(doc, tmp, "lejano_mm.dxf")
    rooms = parser.leer_plano(d).rooms
    check(sum(1 for r in rooms if r.label) == 1,
          "y el mismo plano en milimetros decide exactamente igual",
          "%d de %d con nombre" % (sum(1 for r in rooms if r.label), len(rooms)))

    # =======================================================================
    print()
    print("F. Filtros de fundamento (capa, plausibilidad, ambiguedad)")
    # =======================================================================
    # Reproduce en miniatura el hallazgo del caso 11 del banco plausible:
    # una cota suelta ("7.00") mas cerca del borde que el propio rotulo de
    # la estancia ("SALON 12.00 m2"). Sin los filtros, la cota ganaba por
    # distancia y la estancia se quedaba con un nombre que no es el suyo.
    from shapely.geometry import box as _box  # noqa: E402

    salon = _box(0, 0, 4, 3)  # area 12, tolerancia = 0.5*sqrt(12) = 1.732

    # F1. Plausibilidad: una cifra suelta no gana aunque este mas cerca,
    # incluso en la MISMA capa que el rotulo real (aisla el filtro 2 del 1).
    candidatos = [
        ("SALON 12.00 m2", 2.0, -0.6, "V-04"),   # distancia al borde: 0.6
        ("7.00", 3.3, -0.4, "V-04"),              # distancia al borde: 0.4 (mas cerca)
    ]
    resultado = parser.match_label_to_room(salon, candidatos, capas_validas={"V-04"})
    check(resultado == "SALON 12.00 m2",
          "una cota mas cerca que el rotulo real no se adjudica (plausibilidad)",
          repr(resultado))

    # F2. Capa: un texto de una capa sin ningun rotulo confirmado no es
    # candidato aunque sea el mas cercano y no sea una cifra (aisla el
    # filtro 1 del 2). "TEXTOS" no esta en `capas_validas`: en un plano real
    # eso significa que ese texto nunca ha caido dentro de ningun recinto.
    candidatos = [
        ("SALON", 2.0, -0.6, "V-04"),                    # distancia: 0.6, capa valida
        ("PLANTA BAJA ESC 1:50", 2.1, -0.3, "TEXTOS"),    # distancia: 0.3, capa sin confirmar
    ]
    resultado = parser.match_label_to_room(salon, candidatos, capas_validas={"V-04"})
    check(resultado == "SALON",
          "un texto de una capa sin confirmar no se adjudica aunque este mas cerca",
          repr(resultado))
    # Sin `capas_validas` (llamador que no filtra), se mantiene el comportamiento
    # anterior: gana el mas cercano de cualquier capa.
    resultado_sin_filtro = parser.match_label_to_room(salon, candidatos, capas_validas=None)
    check(resultado_sin_filtro == "PLANTA BAJA ESC 1:50",
          "sin capas_validas no se filtra por capa (compatibilidad)",
          repr(resultado_sin_filtro))

    # F2b. Pero si esa misma capa "TEXTOS" ya ha puesto un nombre dentro de
    # OTRO recinto del plano, `_capas_de_rotulo` la confirma como capa de
    # rotulos real -convencion "recintos en una capa, nombres en otra"- y
    # entonces SI gana por cercania. Es la reproduccion exacta del caso real
    # (`ejemplo.dxf`: recintos en "00 areas", nombres en "00 TEXTO").
    otro_recinto = _box(20, 0, 24, 3)
    poligonos = [salon, otro_recinto]
    etiquetas_con_capa = [
        ("SALON", 2.0, -0.6, "V-04"),
        ("PLANTA BAJA ESC 1:50", 2.1, -0.3, "TEXTOS"),
        ("Cocina", 22.0, 1.5, "TEXTOS"),   # dentro de otro_recinto: confirma la capa
    ]
    capas_confirmadas = parser._capas_de_rotulo(poligonos, etiquetas_con_capa, "V-04")
    check("TEXTOS" in capas_confirmadas,
          "una capa con un nombre real dentro de OTRO recinto queda confirmada",
          repr(capas_confirmadas))
    resultado = parser.match_label_to_room(salon, candidatos, capas_validas=capas_confirmadas)
    check(resultado == "PLANTA BAJA ESC 1:50",
          "una vez confirmada, esa capa SI puede ganar por cercania",
          repr(resultado))

    # F3. Ambiguedad: dos candidatos casi empatados en distancia, mismA capa,
    # ninguno una cifra -> no se adjudica ninguno.
    candidatos = [
        ("SALON", 2.0, -0.6, "V-04"),     # distancia al borde inferior: 0.6
        ("ESTUDIO", 2.0, 3.6, "V-04"),    # distancia al borde superior: 0.6 (empate)
    ]
    resultado = parser.match_label_to_room(salon, candidatos, capas_validas={"V-04"})
    check(resultado is None,
          "un empate de distancia entre dos candidatos no se resuelve adivinando",
          repr(resultado))

    # Control: un margen claro SI decide -- el filtro de ambiguedad no debe
    # bloquear el caso normal, solo el empate.
    candidatos = [
        ("SALON", 2.0, -0.2, "V-04"),     # distancia: 0.2
        ("ESTUDIO", 2.0, 4.0, "V-04"),    # distancia: 1.0 (5x mas lejos)
    ]
    resultado = parser.match_label_to_room(salon, candidatos, capas_validas={"V-04"})
    check(resultado == "SALON",
          "un margen claro entre candidatos si decide (no sobre-bloquea)",
          repr(resultado))

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
