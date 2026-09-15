# -*- coding: utf-8 -*-
"""Plano SINTÉTICO de varias viviendas, para el clic (`C-17`, propuesto).

Ni un dato de un plano real. Una fila de viviendas de 12 × 9 m, separadas por
`separacion` metros, cada una con sus piezas en «00 areas», su rótulo `VT`, su
envolvente construida en otra capa y el rótulo «Superficie construida cerrada» a
0,2 m de su borde. Lo que hace falta para poner a prueba que medir por clic da lo
mismo que medir la planta entera:

- **muebles y muros** en otras capas (lo que el clic deja de mandar);
- con `dudoso=True`, un **contorno de parcela** en otra capa que pasa a 0,1 m del
  rótulo de construida de la primera vivienda pero **lejos de ella**: ese rótulo
  tiene dos candidatas y la fila de construida tiene que salir vacía también por
  clic;
- con `repetida=True`, la última vivienda lleva el mismo rótulo que la primera
  (`C-13`).
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence

ANCHO, FONDO = 12.0, 9.0
PIEZAS = (  # rótulo, x0, y0, x1, y1 — dentro de la vivienda
    ("Salón/cocina", 0.0, 0.0, 5.0, 4.0),
    ("Dormitorio 1", 0.0, 4.1, 3.5, 7.5),
    ("Dormitorio 2", 3.6, 4.1, 6.6, 7.5),
    ("Baño", 5.1, 0.0, 7.1, 2.0),
    ("Terraza", 7.2, 0.0, 11.0, 3.0),
)


def origenes(n: int, separacion: float) -> List[tuple]:
    return [(i * (ANCHO + separacion), 0.0) for i in range(n)]


def nombres(n: int, repetida: bool = False) -> List[str]:
    salida = ["VT%d/1" % (i + 1) for i in range(n)]
    if repetida and n > 1:
        salida[-1] = salida[0]
    return salida


def generar(ruta: Path, n: int = 4, separacion: float = 6.0, dudoso: bool = False,
            repetida: bool = False, solo: Optional[Sequence[int]] = None) -> Path:
    """Escribe el DXF. `solo` deja únicamente esas viviendas (por índice), con
    todo lo suyo y en el mismo sitio: es «medirla sola».

    Con `repetida=True` la última vivienda se llama como la primera **y no mide
    lo mismo**: su dormitorio 2 es 0,40 m más ancho. Así una tabla que las
    confundiera, o que las sumara, no podría salir igual que la buena."""
    import ezdxf

    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    for capa in ("00 areas", "00 TEXTO", "00 CONSTRUIDA", "01 muros", "02 mobiliario", "00 PARCELA"):
        doc.layers.add(capa)
    msp = doc.modelspace()
    rotulos = nombres(n, repetida)
    for i, (ox, oy) in enumerate(origenes(n, separacion)):
        if solo is not None and i not in solo:
            continue
        for rotulo, x0, y0, x1, y1 in PIEZAS:
            if repetida and i == n - 1 and rotulo == "Dormitorio 2":
                x1 += 0.4
            msp.add_lwpolyline([(ox + x0, oy + y0), (ox + x1, oy + y0), (ox + x1, oy + y1),
                                (ox + x0, oy + y1)], close=True, dxfattribs={"layer": "00 areas"})
            msp.add_mtext(rotulo, dxfattribs={"layer": "00 areas", "char_height": 0.15,
                                              "insert": (ox + (x0 + x1) / 2, oy + (y0 + y1) / 2)})
        msp.add_mtext(rotulos[i], dxfattribs={"layer": "00 TEXTO", "char_height": 0.3,
                                              "insert": (ox + 6.0, oy + 8.5)})
        # La envolvente construida, en otra capa, y su rótulo a 0,2 m de su borde de abajo.
        msp.add_lwpolyline([(ox - 0.1, oy - 0.1), (ox + 11.1, oy - 0.1), (ox + 11.1, oy + 7.6),
                            (ox - 0.1, oy + 7.6)], close=True, dxfattribs={"layer": "00 CONSTRUIDA"})
        msp.add_text("Superficie construida cerrada", dxfattribs={
            "layer": "00 TEXTO", "height": 0.125, "insert": (ox + 2.0, oy - 0.3)})
        for k in range(6):
            msp.add_lwpolyline([(ox + 1.0 + k, oy + 5.0), (ox + 1.5 + k, oy + 5.0),
                                (ox + 1.5 + k, oy + 5.4)], close=True,
                               dxfattribs={"layer": "02 mobiliario"})
            msp.add_lwpolyline([(ox + k * 2.0, oy + 7.55), (ox + k * 2.0 + 1.9, oy + 7.55),
                                (ox + k * 2.0 + 1.9, oy + 7.58), (ox + k * 2.0, oy + 7.58)],
                               close=True, dxfattribs={"layer": "01 muros"})
    if dudoso and (solo is None or 0 in solo):
        # Pasa a 0,1 m del rótulo de construida de la vivienda 0 (en y = -0,3) y se va
        # lejos: su caja no toca la vivienda, pero sí la zona de ese rótulo.
        msp.add_lwpolyline([(-40.0, -0.4), (2.5, -0.4), (2.5, -30.0), (-40.0, -30.0)],
                           close=True, dxfattribs={"layer": "00 PARCELA"})
    doc.saveas(str(ruta))
    return ruta
