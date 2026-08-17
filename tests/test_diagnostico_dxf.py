# -*- coding: utf-8 -*-
"""Calibra el diagnostico de ingesta (tarea 1 del PRD de DXF ajenos).

Ejecutar:  python tests/test_diagnostico_dxf.py

El diagnostico existe para MEDIR con que frecuencia ocurren los seis fallos de
ingesta de la seccion 1 del PRD. Una regla que se detecta sola no vale nada: si
el diagnostico no sabe reconocer un DXF en milimetros, el dia que aparezca uno
dira "SI" tan tranquilo y la medicion entera sera falsa -- y peor que no tener
medicion es tener una equivocada en la que se confia.

Asi que aqui se fabrica un DXF sintetico por cada fallo, con ezdxf, y se
comprueba que el diagnostico lo llama por su nombre. Es rapido (~2 s): no hay
ningun archivo real de por medio.

No cubre el fallo (e) -- la convencion de color ACI de
`_discard_container_candidates` -- porque el diagnostico no lo mide: es una
decision de `parser.py` posterior a la lectura, no una propiedad del archivo.
"""
import os
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import ezdxf  # noqa: E402

from herramientas import diagnostico_dxf as diag  # noqa: E402

fallos = []
comprobaciones = 0


def check(ok, etiqueta, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s%s" % ("OK  " if ok else "FALLO", etiqueta, ("  -> " + detalle) if detalle else ""))
    if not ok:
        fallos.append(etiqueta)


def cuadrado(cx, cy, lado):
    """Vertices de un cuadrado centrado en (cx, cy). Con lado=3.5 el area es
    12,25: una habitacion plausible."""
    h = lado / 2.0
    return [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]


def construir(ruta, capa="00 areas", escala=1.0, insunits=6, tipo_rotulo="MTEXT",
              dentro_de_bloque=False, con_vt=True, habitaciones=4):
    """Fabrica un DXF minimo pero completo: `habitaciones` cuadrados cerrados en
    `capa`, cada uno con su rotulo dentro, y una etiqueta de vivienda."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = insunits
    if capa not in doc.layers:
        doc.layers.add(capa)
    msp = doc.modelspace()

    destino = doc.blocks.new(name="VIVIENDA") if dentro_de_bloque else msp

    for i in range(habitaciones):
        cx, cy = (2.0 + i * 5.0) * escala, 2.0 * escala
        puntos = [(x * escala, y * escala) for x, y in cuadrado(cx / escala, cy / escala, 3.5)]
        destino.add_lwpolyline(puntos, close=True, dxfattribs={"layer": capa})

        texto = "Dormitorio %d" % (i + 1)
        if tipo_rotulo == "MTEXT":
            msp.add_mtext(texto, dxfattribs={"layer": capa}).set_location((cx, cy))
        elif tipo_rotulo == "TEXT":
            msp.add_text(texto, dxfattribs={"layer": capa}).set_placement((cx, cy))

    if dentro_de_bloque:
        msp.add_blockref("VIVIENDA", (0, 0))

    if con_vt:
        msp.add_mtext("VT1/3", dxfattribs={"layer": capa}).set_location((0, 20 * escala))

    doc.saveas(ruta)
    return ruta


tmp = tempfile.mkdtemp(prefix="archmuse_diag_")
try:
    # =======================================================================
    print("A. El caso que ya funciona (guardian de regresion)")
    # =======================================================================
    inf = diag.analizar_dxf(construir(os.path.join(tmp, "ok.dxf")))
    estado, motivo = diag.veredicto(inf)
    check(estado == "SI", "DXF compatible -> SI", "%s: %s" % (estado, motivo))
    check(inf["unidades"] == "metros", "lee $INSUNITS", inf["unidades"])
    check(inf["poligonos_modelspace"] == 4, "cuenta las 4 polilineas", str(inf["poligonos_modelspace"]))
    check(inf["etiquetas_vt"] == 1, "encuentra la etiqueta VT", str(inf["etiquetas_vt"]))
    check("metros" in inf["escalas_compatibles"], "deduce la escala en metros",
          str(inf["escalas_compatibles"]))

    # =======================================================================
    print()
    print("B. Fallo (a): unidades supuestas -- el mas grave")
    # =======================================================================
    # Mismo plano dibujado en milimetros: cada area x1.000.000. Hoy ArchMuse lo
    # analizaria en silencio y daria una puntuacion alta y creible.
    inf = diag.analizar_dxf(construir(os.path.join(tmp, "mm.dxf"), escala=1000.0, insunits=4))
    estado, motivo = diag.veredicto(inf)
    check(estado == "PARCIAL", "DXF en milimetros -> PARCIAL, no SI", "%s: %s" % (estado, motivo))
    check("milimetros" in motivo, "el motivo nombra los milimetros", motivo)
    check(inf["escalas_compatibles"] == ["milimetros"],
          "la plausibilidad por tamano acierta sola", str(inf["escalas_compatibles"]))

    # Y lo que de verdad importa: acierta AUNQUE $INSUNITS mienta o falte, que
    # es el caso frecuente. Es el nucleo de la tarea 3 del PRD.
    inf = diag.analizar_dxf(construir(os.path.join(tmp, "mm0.dxf"), escala=1000.0, insunits=0))
    check(inf["escalas_compatibles"] == ["milimetros"],
          "acierta con $INSUNITS=0 (sin especificar)", str(inf["escalas_compatibles"]))
    inf = diag.analizar_dxf(construir(os.path.join(tmp, "mmx.dxf"), escala=1000.0, insunits=6))
    check(inf["escalas_compatibles"] == ["milimetros"],
          "acierta aunque $INSUNITS mienta y diga metros", str(inf["escalas_compatibles"]))

    # =======================================================================
    print()
    print("C. Fallo (b): habitaciones dentro de un bloque -- YA RESUELTO")
    # =======================================================================
    # La tarea 8 hizo que `parser._recorrer_plano` atraviese los INSERT, asi
    # que estar dentro de un bloque dejo de ser un problema. El diagnostico
    # tiene que dejar de penalizarlo, por lo mismo que en el bloque E: una
    # herramienta de medicion que senala un problema ya arreglado envenena la
    # muestra. El recuento se sigue informando.
    inf = diag.analizar_dxf(construir(os.path.join(tmp, "bloque.dxf"), dentro_de_bloque=True))
    estado, motivo = diag.veredicto(inf)
    check(inf["poligonos_en_bloques"] == 4, "las ve al descender al bloque",
          str(inf["poligonos_en_bloques"]))
    check(inf["poligonos_modelspace"] == 0, "y confirma que en modelspace no hay ninguna",
          str(inf["poligonos_modelspace"]))
    check(estado == "SI", "estar dentro de un bloque ya no penaliza", "%s: %s" % (estado, motivo))
    check("dentro de bloques" in motivo, "pero se sigue informando de cuantas",
          motivo)
    check("invisibles" not in motivo and "se pierden" not in motivo,
          "y no queda ningun aviso de que se pierdan", motivo)

    # =======================================================================
    print()
    print("D. Fallo (c): otro nombre de capa")
    # =======================================================================
    inf = diag.analizar_dxf(construir(os.path.join(tmp, "capa.dxf"), capa="SUPERFICIES"))
    estado, motivo = diag.veredicto(inf)
    check(estado == "NO", "capa 'SUPERFICIES' -> NO", "%s: %s" % (estado, motivo))
    check("SUPERFICIES" in motivo, "y propone la capa candidata que si existe", motivo)

    # Mayuscula distinta: '00 Areas' es otra capa para el query de parser.py.
    inf = diag.analizar_dxf(construir(os.path.join(tmp, "mayus.dxf"), capa="00 Areas"))
    check(diag.veredicto(inf)[0] != "NO", "'00 Areas' con mayuscula no es un archivo perdido",
          "el diagnostico normaliza; parser.py NO lo hace")

    # =======================================================================
    print()
    print("E. Fallo (d): rotulos TEXT en vez de MTEXT -- YA RESUELTO")
    # =======================================================================
    # La tarea 7 hizo que `parser.extract_labels` lea TEXT igual que MTEXT, asi
    # que rotular con TEXT dejo de ser un defecto. El diagnostico tiene que
    # dejar de avisarlo: una herramienta de medicion que sigue senalando un
    # problema ya arreglado envenena la muestra entera.
    inf = diag.analizar_dxf(construir(os.path.join(tmp, "text.dxf"), tipo_rotulo="TEXT"))
    estado, motivo = diag.veredicto(inf)
    check(inf["text"] == 4 and inf["mtext"] == 1, "cuenta TEXT y MTEXT por separado",
          "%d TEXT, %d MTEXT (la etiqueta VT sigue siendo MTEXT)" % (inf["text"], inf["mtext"]))
    check(estado == "SI", "rotular con TEXT ya no penaliza", "%s: %s" % (estado, motivo))
    check("TEXT, no MTEXT" not in motivo, "y no queda ningun aviso al respecto", motivo)

    # Lo que si sigue siendo un problema es no tener NINGUN rotulo.
    inf = diag.analizar_dxf(construir(os.path.join(tmp, "mudo.dxf"), tipo_rotulo="NINGUNO", con_vt=False))
    estado, motivo = diag.veredicto(inf)
    check(estado == "PARCIAL" and "ningun rotulo" in motivo,
          "un plano sin rotulos sigue avisando", "%s: %s" % (estado, motivo))

    # =======================================================================
    print()
    print("F. Sin etiquetas de vivienda")
    # =======================================================================
    inf = diag.analizar_dxf(construir(os.path.join(tmp, "sinvt.dxf"), con_vt=False))
    check(inf["etiquetas_vt"] == 0, "cuenta 0 etiquetas VT")
    check("VT" in diag.veredicto(inf)[1], "avisa de la agrupacion por proximidad",
          diag.veredicto(inf)[1])

    # =======================================================================
    print()
    print("G. Archivos que no dan nada")
    # =======================================================================
    vacio = ezdxf.new("R2010")
    vacio.modelspace().add_line((0, 0), (10, 0))
    ruta_vacio = os.path.join(tmp, "vacio.dxf")
    vacio.saveas(ruta_vacio)
    inf = diag.analizar_dxf(ruta_vacio)
    estado, motivo = diag.veredicto(inf)
    check(estado == "NO", "DXF sin ninguna polilinea cerrada -> NO", motivo)

    # Un archivo ilegible NO puede tumbar un lote de 10.
    ruta_roto = os.path.join(tmp, "roto.dxf")
    with open(ruta_roto, "w") as fh:
        fh.write("esto no es un DXF\n")
    inf = diag.analizar_dxf(ruta_roto)
    check(inf["error"] != "", "un archivo ilegible devuelve error, no lanza", inf["error"][:50])
    check(diag.veredicto(inf)[0] == "NO ABRE", "y su veredicto es 'NO ABRE'")
    check(diag.fila_csv(inf)["veredicto"] == "NO ABRE", "la fila CSV tambien se puede construir")

    # =======================================================================
    print()
    print("H. Lote completo")
    # =======================================================================
    rutas = diag.rutas_dxf(tmp)
    check(len(rutas) == 12, "recorre la carpeta entera", "%d archivos" % len(rutas))
    informes = [diag.analizar_dxf(r) for r in rutas]
    check(all(isinstance(diag.fila_csv(i), dict) for i in informes),
          "todos los informes serializan a CSV")
    estados = [diag.veredicto(i)[0] for i in informes]
    # ok.dxf, mayus.dxf, text.dxf y bloque.dxf. Los tres ultimos empezaron
    # siendo defectos y han dejado de serlo: mayusculas del nombre de capa
    # (tarea 6), rotulos TEXT (tarea 7) y habitaciones dentro de bloques
    # (tarea 8). Este contador es, de hecho, el marcador del PRD.
    check(estados.count("SI") == 4, "solo los compatibles salen SI",
          "SI=%d de %d  (%s)" % (estados.count("SI"), len(estados), " ".join(sorted(set(estados)))))

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
