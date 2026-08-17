# -*- coding: utf-8 -*-
"""Comprueba la deteccion de capas candidatas (tarea 5 del PRD de ingesta).

Ejecutar:  python tests/test_capas.py

Bloque A rapido sobre DXF sinteticos (~3 s). Bloque B LENTO (~1-2 min) sobre
ejemplo.dxf, que es la unica planta real disponible.

AVISO SOBRE LO QUE ESTAS PRUEBAS PUEDEN Y NO PUEDEN GARANTIZAR
--------------------------------------------------------------
`capas_candidatas` es una heuristica calibrada contra UN solo DXF real. Estas
pruebas comprueban que se comporta como se dice que se comporta -- no que
acierte con planos que nadie ha visto todavia. Los planos sinteticos los he
fabricado yo, asi que confirman la logica y no la realidad. La comprobacion de
verdad es la tarea 2 del PRD, con archivos ajenos.

Por eso lo que mas se prueba aqui no es que acierte, sino que SEPA CALLARSE:
que cuando dos capas se parecen no elija ninguna. Una heuristica poco afinada
que pregunta es util; una poco afinada que decide sola es una trampa.
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


def rect(msp, capa, x0, y0, ancho, alto):
    msp.add_lwpolyline(
        [(x0, y0), (x0 + ancho, y0), (x0 + ancho, y0 + alto), (x0, y0 + alto)],
        close=True, dxfattribs={"layer": capa})


def planta(msp, capa, n=6, ancho=4.0, alto=3.0, paso=5.0, y=0.0, rotular=True):
    """`n` estancias en fila sobre `capa`, cada una con su nombre dentro."""
    for i in range(n):
        x0 = i * paso
        rect(msp, capa, x0, y, ancho, alto)
        if rotular:
            msp.add_mtext("Estancia %d" % (i + 1), dxfattribs={"layer": capa}).set_location(
                (x0 + ancho / 2, y + alto / 2))


def mobiliario(msp, capa, n=20):
    """Muebles: muchos, pequenos y sin rotulo dentro. Es el senuelo que una
    heuristica basada solo en 'la capa con mas poligonos' se tragaria."""
    for i in range(n):
        rect(msp, capa, (i % 10) * 1.2, (i // 10) * 1.2, 0.6, 0.6)


def guardar(doc, tmp, nombre):
    ruta = os.path.join(tmp, nombre)
    doc.saveas(ruta)
    return parser.load_document(ruta)


tmp = tempfile.mkdtemp(prefix="archmuse_capas_")
try:
    # =======================================================================
    print("A. Distinguir habitaciones de todo lo demas")
    # =======================================================================
    doc = ezdxf.new("R2010")
    for capa in ("SUPERFICIES", "MOBILIARIO", "COTAS"):
        doc.layers.add(capa)
    msp = doc.modelspace()
    planta(msp, "SUPERFICIES")
    mobiliario(msp, "MOBILIARIO")
    mobiliario(msp, "COTAS", n=40)
    d = guardar(doc, tmp, "estudio_ajeno.dxf")

    cands = parser.capas_candidatas(d)
    check(cands[0].nombre == "SUPERFICIES", "gana la capa de areas, no la mas poblada",
          " > ".join("%s(%d p, %.2f)" % (c.nombre, c.n_poligonos, c.puntuacion) for c in cands))
    check(cands[0].n_poligonos < max(c.n_poligonos for c in cands),
          "y eso que MOBILIARIO/COTAS tienen mas poligonos")

    elegida, _ = parser.elegir_capa(d)
    check(elegida is not None and elegida.nombre == "SUPERFICIES",
          "se elige sola: la ventaja es clara", getattr(elegida, "nombre", None))
    check("rótulo dentro" in elegida.motivo and "tamaño de estancia" in elegida.motivo,
          "y explica por que", elegida.motivo)

    # =======================================================================
    print()
    print("B. Saber callarse")
    # =======================================================================
    # Dos plantas identicas en dos capas: no hay forma honesta de elegir.
    doc = ezdxf.new("R2010")
    for capa in ("PLANTA BAJA", "PLANTA PRIMERA"):
        doc.layers.add(capa)
    msp = doc.modelspace()
    planta(msp, "PLANTA BAJA", y=0.0)
    planta(msp, "PLANTA PRIMERA", y=20.0)
    d = guardar(doc, tmp, "dos_plantas.dxf")

    elegida, cands = parser.elegir_capa(d)
    check(elegida is None, "dos capas equivalentes -> no elige ninguna",
          "" if elegida is None else elegida.nombre)
    check(len(cands) == 2, "pero devuelve las dos para preguntar",
          " / ".join(c.nombre for c in cands))

    # Un archivo donde nada se parece a una planta.
    doc = ezdxf.new("R2010")
    doc.layers.add("MOBILIARIO")
    mobiliario(doc.modelspace(), "MOBILIARIO", n=30)
    d = guardar(doc, tmp, "solo_muebles.dxf")
    elegida, cands = parser.elegir_capa(d)
    check(elegida is None, "solo mobiliario -> no elige nada",
          "" if elegida is None else "%s (%.2f)" % (elegida.nombre, elegida.puntuacion))
    check(cands and cands[0].puntuacion < parser.UMBRAL_CAPA_ACEPTABLE,
          "por debajo del umbral aceptable",
          "%.2f < %.2f" % (cands[0].puntuacion, parser.UMBRAL_CAPA_ACEPTABLE))

    # =======================================================================
    print()
    print("C. Casos limite")
    # =======================================================================
    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0), (10, 0))
    d = guardar(doc, tmp, "sin_nada.dxf")
    check(parser.capas_candidatas(d) == [], "un DXF sin polilineas cerradas no da candidatas")
    check(parser.elegir_capa(d) == (None, []), "y elegir_capa no revienta")

    # Menos de MINIMO_POLIGONOS_CAPA: no es una planta.
    doc = ezdxf.new("R2010")
    doc.layers.add("AREAS")
    planta(doc.modelspace(), "AREAS", n=2)
    d = guardar(doc, tmp, "dos_poligonos.dxf")
    check(parser.capas_candidatas(d) == [], "dos poligonos no son una planta")

    # Sin rotulos: baja la puntuacion pero el tamano aun la sostiene. Es un
    # plano peor, no un plano imposible.
    doc = ezdxf.new("R2010")
    doc.layers.add("AREAS")
    planta(doc.modelspace(), "AREAS", rotular=False)
    d = guardar(doc, tmp, "sin_rotulos.dxf")
    cands = parser.capas_candidatas(d)
    check(cands and cands[0].proporcion_rotulada == 0.0, "detecta que no hay rotulos dentro")
    check(cands and "ninguno lleva rótulo" in cands[0].motivo, "y lo dice", cands[0].motivo)

    # La escala no altera el ranking: la plausibilidad de tamano es relativa a
    # la unidad, no absoluta. El mismo plano en mm debe puntuar igual.
    doc = ezdxf.new("R2010")
    for capa in ("SUPERFICIES", "MOBILIARIO"):
        doc.layers.add(capa)
    msp = doc.modelspace()
    for i in range(6):
        rect(msp, "SUPERFICIES", i * 5000.0, 0, 4000.0, 3000.0)
        msp.add_mtext("Estancia %d" % i, dxfattribs={"layer": "SUPERFICIES"}).set_location(
            (i * 5000.0 + 2000.0, 1500.0))
    for i in range(20):
        rect(msp, "MOBILIARIO", (i % 10) * 1200.0, (i // 10) * 1200.0, 600.0, 600.0)
    d = guardar(doc, tmp, "mm.dxf")
    elegida, _ = parser.elegir_capa(d)
    check(elegida is not None and elegida.nombre == "SUPERFICIES",
          "el mismo plano en milimetros da la misma capa", getattr(elegida, "nombre", None))

    # =======================================================================
    print()
    print("D. La respuesta del arquitecto manda")
    # =======================================================================
    elegida, _ = parser.elegir_capa(d, preferida="MOBILIARIO")
    check(elegida is not None and elegida.nombre == "MOBILIARIO",
          "si el arquitecto elige MOBILIARIO, se respeta", getattr(elegida, "nombre", None))
    elegida, _ = parser.elegir_capa(d, preferida="superficies")
    check(elegida is not None and elegida.nombre == "SUPERFICIES",
          "y la mayuscula no importa: '00 Areas' es '00 areas'")
    elegida, cands = parser.elegir_capa(d, preferida="NO EXISTE")
    check(elegida is None and len(cands) > 0,
          "una capa inexistente devuelve None y las candidatas, no un error")

    # =======================================================================
    print()
    print("E. Enchufado a leer_plano (tarea 6)")
    # =======================================================================
    # Un plano de otro estudio, con la capa llamada de otra forma, que hasta
    # ahora daba cero habitaciones sin ninguna explicacion.
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    for capa in ("SUPERFICIES", "MOBILIARIO"):
        doc.layers.add(capa)
    msp = doc.modelspace()
    planta(msp, "SUPERFICIES")
    mobiliario(msp, "MOBILIARIO", n=30)
    d = guardar(doc, tmp, "ajeno.dxf")

    plano = parser.leer_plano(d)
    check(len(plano.rooms) == 6, "leer_plano encuentra las estancias sin que le den la capa",
          "%d habitaciones" % len(plano.rooms))
    check(plano.layer == "SUPERFICIES", "y deja constancia de cual uso", plano.layer)

    # La eleccion del arquitecto manda, aunque sea peor que la deducida.
    plano = parser.leer_plano(d, layer="MOBILIARIO")
    check(plano.layer == "MOBILIARIO" and len(plano.rooms) == 30,
          "si el arquitecto pide otra capa, se usa esa", plano.layer)

    # Una capa que no existe no se resuelve por su cuenta: se pregunta.
    try:
        parser.leer_plano(d, layer="NO EXISTE")
        check(False, "una capa inexistente -> CapaIndeterminada", "no lanzo nada")
    except parser.CapaIndeterminada as exc:
        check(True, "una capa inexistente -> CapaIndeterminada")
        check(exc.pedida == "NO EXISTE" and len(exc.candidatas) >= 1,
              "con lo pedido y las candidatas dentro", str(exc.pedida))
        check("SUPERFICIES" in str(exc), "y un mensaje que propone alternativas", str(exc)[:90])
        check(isinstance(exc, ValueError), "es un ValueError, como EscalaIndeterminada")

    # Un DXF sin nada que parezca una planta.
    doc = ezdxf.new("R2010")
    doc.layers.add("MOBILIARIO")
    mobiliario(doc.modelspace(), "MOBILIARIO", n=30)
    d = guardar(doc, tmp, "nada_legible.dxf")
    try:
        parser.leer_plano(d)
        check(False, "sin capa de estancias -> CapaIndeterminada", "no lanzo nada")
    except parser.CapaIndeterminada as exc:
        check(True, "sin capa de estancias -> CapaIndeterminada")
        check("polilínea cerrada" in str(exc) or "ninguna destaca" in str(exc),
              "explicando que necesita ArchMuse", str(exc)[:90])

finally:
    shutil.rmtree(tmp, ignore_errors=True)

# =======================================================================
print()
print("F. ejemplo.dxf (LENTO)")
# =======================================================================
DXF = os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf")
if not os.path.exists(DXF):
    print("  [SALTA] no se encuentra %s" % DXF)
else:
    print("  parseando ... (lento)")
    d = parser.load_document(DXF)
    cands = parser.capas_candidatas(d)
    print()
    for c in cands:
        print("    %-14s %.4f  %s" % (c.nombre, c.puntuacion, c.motivo))
    print()
    elegida, _ = parser.elegir_capa(d)
    check(elegida is not None and elegida.nombre == parser.AREA_LAYER,
          "elige '%s' sin que nadie se lo diga" % parser.AREA_LAYER,
          getattr(elegida, "nombre", None))
    check(elegida.n_poligonos == 42, "con las 42 polilineas cerradas de esa capa",
          str(elegida.n_poligonos))
    check(elegida.proporcion_rotulada > 0.9, "casi todas rotuladas por dentro",
          "%.0f%%" % (elegida.proporcion_rotulada * 100))

print()
print("=" * 55)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
