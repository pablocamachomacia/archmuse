#!/usr/bin/env python3
"""Genera un banco de DXF hostiles para estresar el pipeline de ArchMuse.

Cada fichero ataca UNA suposicion del parser. El objetivo no es que los
scripts "funcionen" con ellos, sino que NUNCA revienten con un traceback:
deben preguntar, descartar con motivo, o degradarse con elegancia.

Uso:
    python generar_dxf_tortura.py [directorio_salida]

Por defecto escribe en ./dxf_tortura/. Los ficheros son sinteticos y libres
de derechos: pueden commitearse al repo como fixtures de test.
"""
from __future__ import annotations

import sys
from pathlib import Path

import ezdxf
from ezdxf import units


def _habitacion(msp, puntos, capa, etiqueta=None, cerrada=True):
    """Dibuja una polilinea de estancia y, opcionalmente, su etiqueta."""
    msp.add_lwpolyline(puntos, close=cerrada, dxfattribs={"layer": capa})
    if etiqueta:
        xs = [p[0] for p in puntos]
        ys = [p[1] for p in puntos]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        msp.add_text(
            etiqueta,
            dxfattribs={"layer": capa, "height": 0.2, "insert": (cx, cy)},
        )


# ---------------------------------------------------------------------------
# Casos. Cada funcion devuelve (doc, descripcion_del_ataque).
# ---------------------------------------------------------------------------

def caso_01_limpio():
    """Control: vivienda correcta en metros. Si este falla, el problema es otro."""
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.M
    msp = doc.modelspace()
    _habitacion(msp, [(0, 0), (4, 0), (4, 3), (0, 3)], "ESTANCIAS", "SALON 12.00 m2")
    _habitacion(msp, [(4, 0), (7, 0), (7, 3), (4, 3)], "ESTANCIAS", "COCINA 9.00 m2")
    _habitacion(msp, [(0, 3), (3, 3), (3, 6), (0, 6)], "ESTANCIAS", "DORMITORIO 9.00 m2")
    _habitacion(msp, [(3, 3), (5, 3), (5, 6), (3, 6)], "ESTANCIAS", "BANO 6.00 m2")
    return doc, "Vivienda valida en metros con capa y etiquetas claras (control)"


def caso_02_sin_unidades():
    """$INSUNITS = 0 (sin unidad). El parser debe deducir o preguntar."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 0
    msp = doc.modelspace()
    _habitacion(msp, [(0, 0), (4, 0), (4, 3), (0, 3)], "ESTANCIAS", "SALON")
    return doc, "Sin $INSUNITS: unidad indeterminada, geometria ambigua (4x3 podria ser m o... nada)"


def caso_03_milimetros_mentirosos():
    """Dibujado en mm pero $INSUNITS declara metros. La trampa clasica."""
    doc = ezdxf.new("R2010")
    doc.units = units.M  # MIENTE: la geometria esta en mm
    msp = doc.modelspace()
    _habitacion(msp, [(0, 0), (4000, 0), (4000, 3000), (0, 3000)], "ESTANCIAS", "SALON")
    _habitacion(msp, [(4000, 0), (7000, 0), (7000, 3000), (4000, 3000)], "ESTANCIAS", "COCINA")
    return doc, "Geometria en mm con cabecera que declara metros: un salon de 12 millones de m2"


def caso_04_polilinea_abierta():
    """Estancias sin cerrar. Cerrarlas seria una suposicion; hay que declararla."""
    doc = ezdxf.new("R2010")
    doc.units = units.M
    msp = doc.modelspace()
    _habitacion(msp, [(0, 0), (4, 0), (4, 3), (0, 3)], "ESTANCIAS", "SALON", cerrada=False)
    # Peor: abierta Y con el ultimo vertice lejos del primero (hueco real)
    msp.add_lwpolyline([(5, 0), (9, 0), (9, 3), (5.8, 3.1)], close=False,
                       dxfattribs={"layer": "ESTANCIAS"})
    msp.add_text("COCINA", dxfattribs={"layer": "ESTANCIAS", "height": 0.2, "insert": (7, 1.5)})
    return doc, "Polilineas abiertas: una casi cerrada y otra con hueco de 80 cm"


def caso_05_estancias_solapadas():
    """Dos recintos que se pisan 2 m2. El area total no puede ser la suma ciega."""
    doc = ezdxf.new("R2010")
    doc.units = units.M
    msp = doc.modelspace()
    _habitacion(msp, [(0, 0), (4, 0), (4, 3), (0, 3)], "ESTANCIAS", "SALON")
    _habitacion(msp, [(3, 0), (7, 0), (7, 3), (3, 3)], "ESTANCIAS", "COCINA")  # solapa 1x3
    return doc, "Solape de 3 m2 entre SALON y COCINA: sumar areas a ciegas infla la superficie"


def caso_06_etiquetas_duplicadas_y_huerfanas():
    """Dos DORMITORIO 1, un texto sin recinto y un recinto sin texto."""
    doc = ezdxf.new("R2010")
    doc.units = units.M
    msp = doc.modelspace()
    _habitacion(msp, [(0, 0), (3, 0), (3, 3), (0, 3)], "ESTANCIAS", "DORMITORIO 1")
    _habitacion(msp, [(4, 0), (7, 0), (7, 3), (4, 3)], "ESTANCIAS", "DORMITORIO 1")  # repetida
    _habitacion(msp, [(0, 4), (3, 4), (3, 7), (0, 7)], "ESTANCIAS")  # sin etiqueta
    msp.add_text("VESTIDOR", dxfattribs={"layer": "ESTANCIAS", "height": 0.2,
                                          "insert": (10, 10)})  # huerfana, en el vacio
    return doc, "Etiqueta duplicada + recinto mudo + texto huerfano flotando en el vacio"


def caso_07_capas_enganosas():
    """Las estancias NO estan en una capa obvia; hay capas señuelo."""
    doc = ezdxf.new("R2010")
    doc.units = units.M
    msp = doc.modelspace()
    # Capa con nombre prometedor pero vacia de estancias (solo una linea suelta)
    msp.add_line((0, -2), (1, -2), dxfattribs={"layer": "HABITACIONES"})
    # Las estancias reales, en una capa con nombre criptico de estudio veterano
    _habitacion(msp, [(0, 0), (4, 0), (4, 3), (0, 3)], "A-07-SUP_UTIL", "SALON")
    _habitacion(msp, [(4, 0), (7, 0), (7, 3), (4, 3)], "A-07-SUP_UTIL", "COCINA")
    # Ruido: muebles en su capa
    msp.add_lwpolyline([(1, 1), (2, 1), (2, 2), (1, 2)], close=True,
                       dxfattribs={"layer": "MOBILIARIO"})
    return doc, "Capa señuelo 'HABITACIONES' vacia; estancias reales en 'A-07-SUP_UTIL'"


def caso_08_bloques_anidados():
    """Vivienda dentro de bloque dentro de bloque, con capas heredadas (capa 0)."""
    doc = ezdxf.new("R2010")
    doc.units = units.M
    # Bloque interior: una estancia dibujada en capa 0 (hereda del insert)
    blk_room = doc.blocks.new(name="ROOM")
    blk_room.add_lwpolyline([(0, 0), (3, 0), (3, 3), (0, 3)], close=True,
                            dxfattribs={"layer": "0"})
    blk_room.add_text("DORMITORIO", dxfattribs={"layer": "0", "height": 0.2,
                                                 "insert": (1.5, 1.5)})
    # Bloque intermedio que inserta el interior dos veces
    blk_flat = doc.blocks.new(name="FLAT")
    blk_flat.add_blockref("ROOM", (0, 0), dxfattribs={"layer": "ESTANCIAS"})
    blk_flat.add_blockref("ROOM", (4, 0), dxfattribs={"layer": "ESTANCIAS"})
    # El modelo inserta el intermedio, escalado x2
    msp = doc.modelspace()
    msp.add_blockref("FLAT", (0, 0), dxfattribs={"layer": "PLANTA",
                                                  "xscale": 2, "yscale": 2})
    return doc, "Bloques anidados 2 niveles, geometria en capa 0 heredando, insert escalado x2"


def caso_09_geometria_basura():
    """Recintos degenerados: area cero, autointerseccion, vertices duplicados."""
    doc = ezdxf.new("R2010")
    doc.units = units.M
    msp = doc.modelspace()
    # Area cero (todos los puntos colineales)
    msp.add_lwpolyline([(0, 0), (2, 0), (4, 0)], close=True,
                       dxfattribs={"layer": "ESTANCIAS"})
    # Pajarita (autointerseccion): el area con formula del zapatero sale enganosa
    msp.add_lwpolyline([(0, 2), (3, 5), (3, 2), (0, 5)], close=True,
                       dxfattribs={"layer": "ESTANCIAS"})
    msp.add_text("SALON", dxfattribs={"layer": "ESTANCIAS", "height": 0.2,
                                       "insert": (1.5, 3.5)})
    # Vertices duplicados consecutivos
    msp.add_lwpolyline([(5, 0), (5, 0), (8, 0), (8, 3), (8, 3), (5, 3)], close=True,
                       dxfattribs={"layer": "ESTANCIAS"})
    msp.add_text("COCINA", dxfattribs={"layer": "ESTANCIAS", "height": 0.2,
                                        "insert": (6.5, 1.5)})
    return doc, "Area cero + polilinea en pajarita (autointerseccion) + vertices duplicados"


def caso_10_coordenadas_lejanas():
    """Plano georreferenciado: la vivienda esta a ~440 km del origen (UTM)."""
    doc = ezdxf.new("R2010")
    doc.units = units.M
    msp = doc.modelspace()
    ox, oy = 440_000.0, 4_474_000.0  # UTM 30N aprox Madrid
    _habitacion(msp, [(ox, oy), (ox + 4, oy), (ox + 4, oy + 3), (ox, oy + 3)],
                "ESTANCIAS", "SALON")
    _habitacion(msp, [(ox + 4, oy), (ox + 7, oy), (ox + 7, oy + 3), (ox + 4, oy + 3)],
                "ESTANCIAS", "COCINA")
    return doc, "Coordenadas UTM enormes: estresa deduccion de unidad por plausibilidad y precision float"


def caso_11_vacio_y_ruido():
    """Un DXF sin ninguna estancia: solo ejes, cotas y un cajetin."""
    doc = ezdxf.new("R2010")
    doc.units = units.M
    msp = doc.modelspace()
    for i in range(5):
        msp.add_line((i * 3, -1), (i * 3, 10), dxfattribs={"layer": "EJES"})
    msp.add_lwpolyline([(20, 0), (30, 0), (30, 5), (20, 5)], close=True,
                       dxfattribs={"layer": "CAJETIN"})
    msp.add_text("PROYECTO DE VIVIENDA - PLANO 03", dxfattribs={"layer": "CAJETIN",
                                                                 "height": 0.4,
                                                                 "insert": (20.5, 2.5)})
    return doc, "Sin estancias: solo ejes y cajetin. Debe decir 'no encuentro recintos' y que necesita"


def caso_12_texto_hostil():
    """Etiquetas con acentos, saltos, MTEXT con formato y numeros trampa."""
    doc = ezdxf.new("R2010")
    doc.units = units.M
    msp = doc.modelspace()
    _habitacion(msp, [(0, 0), (4, 0), (4, 3), (0, 3)], "ESTANCIAS")
    msp.add_mtext("SAL\u00d3N-\\P COMEDOR\\P12,50 m\u00b2",
                  dxfattribs={"layer": "ESTANCIAS", "insert": (2, 1.5),
                              "char_height": 0.2})
    _habitacion(msp, [(4, 0), (7, 0), (7, 3), (4, 3)], "ESTANCIAS")
    msp.add_text("Ba\u00f1o  9.00m2 (aprox)", dxfattribs={"layer": "ESTANCIAS",
                                                           "height": 0.2,
                                                           "insert": (5.5, 1.5)})
    # Un area declarada que NO coincide con la medida (4x3=12, dice 9)
    return doc, "MTEXT multilinea con formato, acentos, coma decimal y area declarada que no cuadra con la medida"


def caso_13_r12_antiguo():
    """DXF R12 (1992): sin LWPOLYLINE, con POLYLINE clasica. Estudios veteranos los tienen."""
    doc = ezdxf.new("R12")
    msp = doc.modelspace()
    # En R12 no hay lwpolyline: polyline 2D clasica
    p = msp.add_polyline2d([(0, 0), (4, 0), (4, 3), (0, 3)], close=True,
                           dxfattribs={"layer": "ESTANCIAS"})
    msp.add_text("SALON", dxfattribs={"layer": "ESTANCIAS", "height": 0.2,
                                       "insert": (2, 1.5)})
    return doc, "Formato R12 de 1992: POLYLINE clasica en vez de LWPOLYLINE, cabecera minima"


CASOS = [
    caso_01_limpio,
    caso_02_sin_unidades,
    caso_03_milimetros_mentirosos,
    caso_04_polilinea_abierta,
    caso_05_estancias_solapadas,
    caso_06_etiquetas_duplicadas_y_huerfanas,
    caso_07_capas_enganosas,
    caso_08_bloques_anidados,
    caso_09_geometria_basura,
    caso_10_coordenadas_lejanas,
    caso_11_vacio_y_ruido,
    caso_12_texto_hostil,
    caso_13_r12_antiguo,
]


def main() -> None:
    salida = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dxf_tortura")
    salida.mkdir(parents=True, exist_ok=True)
    manifiesto = []
    for fn in CASOS:
        doc, descripcion = fn()
        nombre = fn.__name__.replace("caso_", "") + ".dxf"
        ruta = salida / nombre
        doc.saveas(ruta)
        manifiesto.append((nombre, descripcion))
        print(f"  {nombre:45s} {descripcion}")
    # Manifiesto legible junto a los ficheros
    with open(salida / "MANIFIESTO.md", "w", encoding="utf-8") as f:
        f.write("# Banco de DXF de tortura\n\n")
        f.write("Ficheros sinteticos, libres de derechos. Cada uno ataca una "
                "suposicion del parser.\nExito = ninguno produce traceback: "
                "preguntan, descartan con motivo o se degradan.\n\n")
        f.write("| Fichero | Ataque |\n|---|---|\n")
        for nombre, desc in manifiesto:
            f.write(f"| `{nombre}` | {desc} |\n")
    print(f"\n{len(manifiesto)} ficheros escritos en {salida.resolve()}/")


if __name__ == "__main__":
    main()
