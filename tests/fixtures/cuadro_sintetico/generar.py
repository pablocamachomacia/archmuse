# -*- coding: utf-8 -*-
"""Genera `cuadro_sintetico.dxf`: una vivienda inventada con un cuadro de verdad.

PRD `docs/prd/2026-09-13-cuadro-plantilla-fija.md`, T1.

**Por qué existe.** Hasta el 2026-09-13 **ningún DXF del repositorio tenía un
`ACAD_TABLE`**, y por eso 1.738 tests en verde no vieron `D-13`: toda la
capacidad del cuadro sólo se probaba con los planos del arquitecto, que no se
versionan porque son de sus clientes y el repositorio es público.

**Nada de aquí sale de un plano real**, y no puede: ya se coló una vez un
`$LASTSAVEDBY` con un nombre real. Todo se dibuja con coordenadas escritas a
mano, y la cabecera se fija explícitamente (`ezdxf` pone `'ezdxf'` por defecto).

**Qué reproduce a la vez:**

- **Las filas de la plantilla:** salón/cocina, dos dormitorios, una terraza y
  un trastero → cinco filas, ni una más.
- **`D-13`:** el cuadro del arquitecto pide `pasillo` y `vestibulo`, que este
  plano no dibuja. La vía antigua escribía `0,00 m²` en los dos.
- **`C-5`:** el cuadro pide `terraza 1` y `terraza 2` y el plano dibuja **una**
  terraza.
- **La clasificación dudosa:** «Trastero» no es de ninguna familia conocida.
- **`C-12` (firmado el 2026-09-13, por rótulo):** una envolvente con el flag de
  cerrada sin poner, que contiene las piezas interiores y ninguna exterior,
  rotulada «Superficie construida cerrada» a 0,23 m de su borde como en
  `v1plantas.dxf`. Es ACI 10 porque así estaba el plano; el color no cuenta, y
  `tests/test_c12_construida_por_rotulo.py` lo prueba quitándoselo.

### El `ACAD_TABLE`, a mano

`ezdxf` no sabe crear un `ACAD_TABLE` (`DXFTypeError`, medido el 2026-09-13).
Lo que el detector del servidor lee de una tabla no es su contenido interno
sino las `LINE` y `MTEXT` del bloque anónimo al que apunta
(`virtual_entities()`). Así que se dibuja ese bloque con `ezdxf` y se inserta en
el texto del DXF una entidad `ACAD_TABLE` mínima que lo referencia. **AutoCAD no
aceptaría esta tabla como editable**; el lector de ArchMuse, sí, que es lo que
se prueba.

    venv\\Scripts\\python.exe tests\\fixtures\\cuadro_sintetico\\generar.py
"""
from __future__ import annotations

import os
import sys

import ezdxf

AQUI = os.path.dirname(os.path.abspath(__file__))
DESTINO = os.path.join(AQUI, "cuadro_sintetico.dxf")

#: Lo único que se escribe en la cabecera y podría identificar a alguien.
AUTOR_DE_LA_CABECERA = "fixture-sintetico"

CAPA_RECINTOS = "00 areas"
CAPA_TEXTO = "00 TEXTO"
ALTURA_ROTULO = 0.125
ALTURA_CUADRO = 0.09

#: (rótulo, x0, y0, x1, y1). Separadas 0,10 m, como un muro.
RECINTOS = (
    ("Salón/cocina", 0.0, 0.0, 5.0, 4.0),     # 20,00 m²
    ("Dormitorio 1", 5.1, 0.0, 8.1, 4.0),     # 12,00 m²
    ("Dormitorio 2", 8.2, 0.0, 11.2, 3.0),    #  9,00 m²
    ("Trastero", 8.2, 3.1, 11.2, 4.0),        #  2,70 m²
    ("Terraza", 0.0, -1.6, 3.0, -0.1),        #  4,50 m²
)

#: La envolvente construida: rodea las cuatro piezas de arriba y deja fuera la
#: terraza. Flag de cerrada SIN poner y el último vértice repetido con un hueco
#: mínimo, como la de `v1plantas.dxf`.
ENVOLVENTE = ((-0.2, -0.05), (11.4, -0.05), (11.4, 4.2), (-0.2, 4.2), (-0.2, -0.049))

#: El cuadro del arquitecto: (fila, columna, texto). Cuatro columnas.
CUADRO = (
    (0, 0, "CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA"),
    (1, 0, "ESPACIOS INTERIORES"), (1, 1, "SUPERFICIES UTILES"),
    (1, 2, "ESPACIOS EXTERIORES"), (1, 3, "SUPERFICIES UTILES"),
    (2, 0, "salón + cocina"), (2, 2, "terraza 1"),
    (3, 0, "dormitorio 1"), (3, 2, "terraza 2"),
    (4, 0, "dormitorio 2"),
    (5, 0, "pasillo"),
    (6, 0, "vestibulo"),
    (7, 0, "TOTAL SUP. INTERIOR (m2)"), (7, 2, "TOTAL SUP. EXTERIOR (m2)"),
    (8, 0, "TOTAL S. UTIL(m2)"),
    (9, 0, "S. CONSTRUIDA C."),
    (10, 0, "VIVIENDA TIPO"), (10, 1, "VT1 /3"), (10, 2, "NUMERO UDS:"),
)
CUADRO_ORIGEN = (20.0, 6.0)
CUADRO_ANCHOS = (3.0, 2.0, 3.0, 2.0)
CUADRO_ALTO_FILA = 0.4


def _rectangulo(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def construir() -> ezdxf.document.Drawing:
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    doc.header["$LASTSAVEDBY"] = AUTOR_DE_LA_CABECERA
    for capa in (CAPA_RECINTOS, CAPA_TEXTO):
        doc.layers.add(capa)
    msp = doc.modelspace()

    for rotulo, x0, y0, x1, y1 in RECINTOS:
        msp.add_lwpolyline(_rectangulo(x0, y0, x1, y1), close=True,
                           dxfattribs={"layer": CAPA_RECINTOS})
        msp.add_mtext(rotulo, dxfattribs={
            "layer": CAPA_RECINTOS, "char_height": ALTURA_ROTULO,
            "insert": ((x0 + x1) / 2, (y0 + y1) / 2)})

    msp.add_lwpolyline(ENVOLVENTE, close=False,
                       dxfattribs={"layer": CAPA_RECINTOS, "color": 10})
    msp.add_mtext("Superficie construida cerrada", dxfattribs={
        "layer": CAPA_RECINTOS, "char_height": ALTURA_ROTULO, "insert": (0.0, 4.43)})
    msp.add_mtext("VT1/3", dxfattribs={
        "layer": CAPA_TEXTO, "char_height": 0.3, "insert": (6.6, 2.0)})

    bloque = doc.blocks.new_anonymous_block("T")
    # El contenido de un `*T` va relativo a su punto de inserción, como en
    # AutoCAD: `virtual_entities()` lo traslada a `CUADRO_ORIGEN`.
    x0, y0 = 0.0, 0.0
    xs = [x0]
    for ancho in CUADRO_ANCHOS:
        xs.append(xs[-1] + ancho)
    n_filas = 1 + max(f for f, _c, _t in CUADRO)
    ys = [y0 - i * CUADRO_ALTO_FILA for i in range(n_filas + 1)]
    for x in xs:
        bloque.add_line((x, ys[0]), (x, ys[-1]))
    for y in ys:
        bloque.add_line((xs[0], y), (xs[-1], y))
    for fila, columna, texto in CUADRO:
        bloque.add_mtext(texto, dxfattribs={
            "char_height": ALTURA_CUADRO,
            "insert": (xs[columna] + 0.05, ys[fila] - CUADRO_ALTO_FILA / 2)})

    return doc, bloque.name, doc.entitydb.next_handle()


def guardar(destino: str = DESTINO) -> str:
    doc, nombre_bloque, handle = construir()
    temporal = destino + ".tmp"
    doc.saveas(temporal)
    with open(temporal, encoding="utf-8") as f:
        texto = f.read()
    os.remove(temporal)

    tabla = "\n".join([
        "  0", "ACAD_TABLE", "  5", handle, "330", doc.modelspace().block_record_handle,
        "100", "AcDbEntity", "  8", CAPA_TEXTO,
        "100", "AcDbBlockReference", "  2", nombre_bloque,
        " 10", "%.1f" % CUADRO_ORIGEN[0], " 20", "%.1f" % CUADRO_ORIGEN[1], " 30", "0.0",
        "100", "AcDbTable",
    ]) + "\n"
    marca = "  0\nSECTION\n  2\nENTITIES\n"
    corte = texto.index(marca) + len(marca)
    with open(destino, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto[:corte] + tabla + texto[corte:])
    return destino


if __name__ == "__main__":
    print(guardar(sys.argv[1] if len(sys.argv) > 1 else DESTINO))
