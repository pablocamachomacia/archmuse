#!/usr/bin/env python3
"""Genera un banco de DXF *plausibles* para probar falsos rechazos.

Es el espejo de `generar_dxf_tortura.py`: en vez de atacar una suposición del
parser con un caso hostil, cada fichero dibuja la MISMA vivienda válida
(4 estancias, 36 m² útiles: SALON 12, COCINA 9, DORMITORIO 9, BANO 6) a la
manera de un estudio real distinto — un nombre de capa distinto, una
convención de rotulado distinta, unidades en mm bien declaradas, capas de
ruido normales de cualquier plano de obra, o muros de doble línea.

El criterio aquí es el contrario al banco de tortura: **todos deberían
medirse sin preguntar nada**. Cualquier AVISO en este banco es candidato a
falso rechazo — una convención real de dibujo que el parser no reconoce.

Uso:
    python generar_dxf_plausibles.py [directorio_salida]

Por defecto escribe en ./tests/fixtures/dxf_plausibles/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import ezdxf
from ezdxf import units

# La misma vivienda en los 10 casos: solo cambia CÓMO se dibuja, nunca la
# geometría de las estancias ni su superficie.
HABITACIONES = [
    ("SALON", [(0, 0), (4, 0), (4, 3), (0, 3)], 12.0),
    ("COCINA", [(4, 0), (7, 0), (7, 3), (4, 3)], 9.0),
    ("DORMITORIO", [(0, 3), (3, 3), (3, 6), (0, 6)], 9.0),
    ("BANO", [(3, 3), (5, 3), (5, 6), (3, 6)], 6.0),
]
SUPERFICIE_UTIL_TOTAL_M2 = 36.0


def _centroide(puntos):
    xs = [p[0] for p in puntos]
    ys = [p[1] for p in puntos]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _dibujar_recintos(msp, capa, factor=1.0, con_area=True):
    """Dibuja los 4 recintos en `capa`, con el rótulo dentro (convención
    estándar). `factor` escala las coordenadas (para el caso en mm)."""
    for nombre, puntos, area in HABITACIONES:
        pts = [(x * factor, y * factor) for x, y in puntos]
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": capa})
        cx, cy = _centroide(pts)
        etiqueta = "%s %.2f m2" % (nombre, area) if con_area else nombre
        msp.add_text(etiqueta, dxfattribs={"layer": capa, "height": 0.2 * factor,
                                            "insert": (cx, cy)})


# ---------------------------------------------------------------------------
# Casos. Cada funcion devuelve (doc, descripcion_de_la_convencion).
# ---------------------------------------------------------------------------

def caso_01_control_estancias():
    """Control: capa ESTANCIAS, rótulo dentro con área. Idéntico en espíritu
    al caso_01 del banco de tortura — si este falla, el problema es otro."""
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.M
    msp = doc.modelspace()
    _dibujar_recintos(msp, "ESTANCIAS")
    return doc, "Capa ESTANCIAS, rótulo dentro del recinto con área (control)"


def caso_02_capa_a_sup_util():
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.M
    msp = doc.modelspace()
    _dibujar_recintos(msp, "A-SUP-UTIL")
    return doc, "Capa «A-SUP-UTIL»: convención de capas por prefijo de disciplina (A-)"


def caso_03_capa_superficies():
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.M
    msp = doc.modelspace()
    _dibujar_recintos(msp, "SUPERFICIES")
    return doc, "Capa «SUPERFICIES»: nombre llano, sin prefijo ni numeración"


def caso_04_capa_03_recintos():
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.M
    msp = doc.modelspace()
    _dibujar_recintos(msp, "03_RECINTOS")
    return doc, "Capa «03_RECINTOS»: numeración de capas por índice de plano"


def caso_05_capa_areas():
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.M
    msp = doc.modelspace()
    _dibujar_recintos(msp, "AREAS")
    return doc, "Capa «AREAS»: nombre llano en plural, sin acento"


def caso_06_rotulo_fuera_con_directriz():
    """Rótulo fuera del recinto, con una línea directriz corta hasta su
    borde — convención habitual cuando la estancia es pequeña para el texto.
    La distancia se mantiene corta a propósito (realista, no de tortura)."""
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.M
    msp = doc.modelspace()
    capa = "ESTANCIAS"
    for nombre, puntos, area in HABITACIONES:
        msp.add_lwpolyline(puntos, close=True, dxfattribs={"layer": capa})
        cx, cy = _centroide(puntos)
        ys = [p[1] for p in puntos]
        # Ancla justo fuera del contorno, a 0.6 m del borde mas cercano, en la
        # direccion que aleja del resto de la vivienda (abajo para la fila
        # inferior, arriba para la superior).
        if cy < 3:
            ancla = (cx, min(ys) - 0.6)
            punto_directriz = (cx, min(ys))
        else:
            ancla = (cx, max(ys) + 0.6)
            punto_directriz = (cx, max(ys))
        etiqueta = "%s %.2f m2" % (nombre, area)
        msp.add_text(etiqueta, dxfattribs={"layer": capa, "height": 0.2, "insert": ancla})
        msp.add_line(ancla, punto_directriz, dxfattribs={"layer": capa})
    return doc, "Rótulo fuera de cada recinto (~0.6 m del borde) con línea directriz hasta el contorno"


def caso_07_rotulo_solo_nombre():
    """Rótulo dentro del recinto pero sin superficie: solo el nombre."""
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.M
    msp = doc.modelspace()
    _dibujar_recintos(msp, "ESTANCIAS", con_area=False)
    return doc, "Rótulo dentro del recinto pero solo el nombre, sin cifra de superficie"


def caso_08_mm_insunits_correcto():
    """Dibujado en milímetros con $INSUNITS=4 (mm) declarado correctamente
    -- al contrario que el caso 03 del banco de tortura, aquí la cabecera NO
    miente."""
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.MM
    msp = doc.modelspace()
    _dibujar_recintos(msp, "ESTANCIAS", factor=1000.0)
    return doc, "Geometría en mm con $INSUNITS=4 declarado correctamente (sin mentir)"


def caso_09_capas_de_ruido():
    """Las estancias reales conviven con capas de ruido normales de
    cualquier plano de obra: mobiliario, cotas, ejes, textos sueltos y
    cajetín. Ninguna de ellas debería competir con ESTANCIAS."""
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.M
    msp = doc.modelspace()
    _dibujar_recintos(msp, "ESTANCIAS")

    # MOBILIARIO: un par de piezas sin rotular, muy por debajo del recuento
    # de estancias reales (4) para no competir por volumen.
    msp.add_lwpolyline([(0.3, 0.3), (1.3, 0.3), (1.3, 1.3), (0.3, 1.3)], close=True,
                       dxfattribs={"layer": "MOBILIARIO"})
    msp.add_lwpolyline([(4.3, 0.3), (5.3, 0.3), (5.3, 1.8), (4.3, 1.8)], close=True,
                       dxfattribs={"layer": "MOBILIARIO"})

    # COTAS: lineas de cota y su texto, tipico de un plano acotado.
    msp.add_line((0, -0.5), (7, -0.5), dxfattribs={"layer": "COTAS"})
    msp.add_text("7.00", dxfattribs={"layer": "COTAS", "height": 0.15, "insert": (3.3, -0.4)})
    msp.add_line((-0.5, 0), (-0.5, 6), dxfattribs={"layer": "COTAS"})
    msp.add_text("6.00", dxfattribs={"layer": "COTAS", "height": 0.15, "insert": (-0.9, 2.9)})

    # EJES: rejilla de replanteo.
    for i in range(4):
        msp.add_line((i * 2.5, -1.5), (i * 2.5, 7.5), dxfattribs={"layer": "EJES"})

    # TEXTOS: rotulos sueltos que no son nombres de estancia.
    msp.add_text("PLANTA BAJA - ESC 1:50", dxfattribs={"layer": "TEXTOS", "height": 0.3,
                                                        "insert": (0, 8)})

    # CAJETIN: cuadro de titulo, aparte de la planta.
    msp.add_lwpolyline([(15, 0), (25, 0), (25, 5), (15, 5)], close=True,
                       dxfattribs={"layer": "CAJETIN"})
    msp.add_text("VIVIENDA UNIFAMILIAR - PLANTA BAJA", dxfattribs={"layer": "CAJETIN",
                                                                    "height": 0.3,
                                                                    "insert": (15.5, 2.5)})
    return doc, "Estancias reales + capas de ruido habituales: MOBILIARIO, COTAS, EJES, TEXTOS, CAJETIN"


def caso_10_muros_doble_linea():
    """Muros de doble linea alrededor de los recintos, en su propia capa
    MUROS -- la convencion mas habitual de dibujo en bruto (sin hatch)."""
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.M
    msp = doc.modelspace()
    _dibujar_recintos(msp, "ESTANCIAS")

    grosor = 0.15
    # Perimetro exterior de la vivienda (7 x 6) y las dos particiones
    # interiores, cada uno como un par de lineas paralelas separadas
    # `grosor` -- doble linea, sin cerrar el muro en un polígono relleno.
    segmentos = [
        # perimetro exterior
        ((0, 0), (7, 0)), ((7, 0), (7, 6)), ((7, 6), (0, 6)), ((0, 6), (0, 0)),
        # particion salon/cocina - dormitorio/bano
        ((0, 3), (7, 3)),
        # particion salon - cocina
        ((4, 0), (4, 3)),
        # particion dormitorio - bano
        ((3, 3), (3, 6)),
    ]
    for (x1, y1), (x2, y2) in segmentos:
        dx, dy = x2 - x1, y2 - y1
        largo = (dx ** 2 + dy ** 2) ** 0.5
        nx, ny = -dy / largo * grosor / 2, dx / largo * grosor / 2
        msp.add_line((x1 + nx, y1 + ny), (x2 + nx, y2 + ny), dxfattribs={"layer": "MUROS"})
        msp.add_line((x1 - nx, y1 - ny), (x2 - nx, y2 - ny), dxfattribs={"layer": "MUROS"})
    return doc, "Muros de doble línea (perímetro + particiones) en capa MUROS alrededor de las estancias"


def caso_11_capa_opaca_rotulos_fuera():
    """El suelo del heurístico `capas_candidatas`: capa sin ninguna pista de
    nombre (`V-04` no contiene "area", "superficie", "estancia", "recinto",
    "room", "sup" ni "local" — a diferencia de «A-SUP-UTIL», que sí llevaba
    "sup"), TODOS los rótulos fuera del recinto con directriz (rotulada=0,
    el término de mayor peso de la puntuación) y capas de ruido encima. Si
    algo hace preguntar al heurístico, es esta combinación."""
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.M
    msp = doc.modelspace()
    capa = "V-04"
    for nombre, puntos, area in HABITACIONES:
        msp.add_lwpolyline(puntos, close=True, dxfattribs={"layer": capa})
        cx, cy = _centroide(puntos)
        ys = [p[1] for p in puntos]
        if cy < 3:
            ancla = (cx, min(ys) - 0.6)
            punto_directriz = (cx, min(ys))
        else:
            ancla = (cx, max(ys) + 0.6)
            punto_directriz = (cx, max(ys))
        etiqueta = "%s %.2f m2" % (nombre, area)
        msp.add_text(etiqueta, dxfattribs={"layer": capa, "height": 0.2, "insert": ancla})
        msp.add_line(ancla, punto_directriz, dxfattribs={"layer": capa})

    # Mismas capas de ruido que el caso 09.
    msp.add_lwpolyline([(0.3, 0.3), (1.3, 0.3), (1.3, 1.3), (0.3, 1.3)], close=True,
                       dxfattribs={"layer": "MOBILIARIO"})
    msp.add_lwpolyline([(4.3, 0.3), (5.3, 0.3), (5.3, 1.8), (4.3, 1.8)], close=True,
                       dxfattribs={"layer": "MOBILIARIO"})
    msp.add_line((0, -0.5), (7, -0.5), dxfattribs={"layer": "COTAS"})
    msp.add_text("7.00", dxfattribs={"layer": "COTAS", "height": 0.15, "insert": (3.3, -0.4)})
    msp.add_line((-0.5, 0), (-0.5, 6), dxfattribs={"layer": "COTAS"})
    msp.add_text("6.00", dxfattribs={"layer": "COTAS", "height": 0.15, "insert": (-0.9, 2.9)})
    for i in range(4):
        msp.add_line((i * 2.5, -1.5), (i * 2.5, 7.5), dxfattribs={"layer": "EJES"})
    msp.add_text("PLANTA BAJA - ESC 1:50", dxfattribs={"layer": "TEXTOS", "height": 0.3,
                                                        "insert": (0, 8)})
    msp.add_lwpolyline([(15, 0), (25, 0), (25, 5), (15, 5)], close=True,
                       dxfattribs={"layer": "CAJETIN"})
    msp.add_text("VIVIENDA UNIFAMILIAR - PLANTA BAJA", dxfattribs={"layer": "CAJETIN",
                                                                    "height": 0.3,
                                                                    "insert": (15.5, 2.5)})
    return doc, ("Capa «V-04» (sin pista de nombre) + TODOS los rótulos fuera con directriz "
                 "+ capas de ruido: el suelo del heurístico de detección de capa")


CASOS = [
    caso_01_control_estancias,
    caso_02_capa_a_sup_util,
    caso_03_capa_superficies,
    caso_04_capa_03_recintos,
    caso_05_capa_areas,
    caso_06_rotulo_fuera_con_directriz,
    caso_07_rotulo_solo_nombre,
    caso_08_mm_insunits_correcto,
    caso_09_capas_de_ruido,
    caso_10_muros_doble_linea,
    caso_11_capa_opaca_rotulos_fuera,
]


def main() -> None:
    salida = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/fixtures/dxf_plausibles")
    salida.mkdir(parents=True, exist_ok=True)
    manifiesto = []
    for fn in CASOS:
        doc, descripcion = fn()
        nombre = fn.__name__.replace("caso_", "") + ".dxf"
        ruta = salida / nombre
        doc.saveas(ruta)
        manifiesto.append((nombre, descripcion))
        print(f"  {nombre:35s} {descripcion}")
    with open(salida / "MANIFIESTO.md", "w", encoding="utf-8") as f:
        f.write("# Banco de DXF plausibles\n\n")
        f.write(
            "La misma vivienda válida (4 estancias, 36 m² útiles) dibujada a la manera de "
            "11 estudios distintos. Criterio contrario al banco de tortura: **todos deberían "
            "medirse sin preguntar nada**. Un AVISO aquí es un falso rechazo a investigar, no "
            "un rechazo controlado correcto.\n\n"
        )
        f.write("| Fichero | Convención |\n|---|---|\n")
        for nombre, desc in manifiesto:
            f.write(f"| `{nombre}` | {desc} |\n")
    print(f"\n{len(manifiesto)} ficheros escritos en {salida.resolve()}/")


if __name__ == "__main__":
    main()
