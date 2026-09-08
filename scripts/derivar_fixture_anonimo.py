#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Deriva un fixture de regresión anónimo a partir de un plano real de cliente.

**Por qué existe y por qué no borra capas.** El repositorio es público y el
`.gitignore` lo dice con todas las letras: «un plano de cliente commiteado por
descuido es una fuga de datos que el historial no olvida». La forma intuitiva de
anonimizar —abrir el DXF del cliente y borrar lo que sobra— es la insegura: en
un DXF de AutoCAD sobrevive cualquier cosa que no se haya mirado (definiciones
de bloque sin insertar, diccionarios, `XRECORD`, propiedades del documento,
capas apagadas, el nombre de quien lo guardó). Un despiste ahí es irreversible.

**Así que esto no borra: reconstruye.** Se lee el plano con el mismo
`parser.leer_plano` que usa el producto, se toman **sólo** dos cosas —los
polígonos de los recintos y el texto de sus rótulos— y se escribe un DXF
**nuevo**, vacío al empezar. Todo lo que no se copia explícitamente aquí no
existe en la salida, porque nunca llegó a existir. La lista de lo que se copia
cabe en una pantalla, que es justo lo que se quería.

**Lo que sí viaja, y es lo único:**

- La geometría de cada recinto, ya en metros (vértices de su polígono).
- El rótulo de cada recinto («Salón/cocina», «Dormitorio 1», «Terraza»…), que es
  vocabulario común de cualquier vivienda y es lo que el motor clasifica.
- Las etiquetas de vivienda `VT<n>/<m>`, que son códigos de tipología y no
  nombres de promoción. Sin ellas el reparto por rótulos no se puede probar, que
  es la mitad de lo que el fixture existe para vigilar.

**Lo que no viaja:** cajetín, carátula, nombres de bloque (los de estos planos
vienen de un export de Revit y llevan códigos de vivienda del proyecto), capas
del estudio, cotas, mobiliario, carpintería, sombreados, `XDATA`, el histórico
del documento y el nombre del fichero.

Uso:

    python scripts/derivar_fixture_anonimo.py <origen.dxf> <destino.dxf>

Después, SIEMPRE, la auditoría del resultado:

    python scripts/auditar_fixture_anonimo.py <destino.dxf>
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ezdxf  # noqa: E402

from analyzer import parser  # noqa: E402

#: Capa única de la salida. El nombre por defecto del repositorio, no el del
#: estudio: qué capa usa cada despacho es una convención suya, y además es lo
#: que vigila el banco de tortura, no este fixture.
CAPA = parser.AREA_LAYER


def derivar(origen: str, destino: str) -> dict:
    doc_origen = parser.load_document(origen)
    plano = parser.leer_plano(doc_origen)
    etiquetas = parser.extract_unit_labels(doc_origen)

    # La escala se aplicó a `plano.rooms`; las etiquetas de vivienda salen del
    # documento en unidades de dibujo, así que hay que llevarlas al mismo sitio.
    factor = getattr(plano.escala, "factor", None) or 1.0

    salida = ezdxf.new("R2010")
    salida.header["$INSUNITS"] = 6           # metros, declarado y no deducido
    salida.layers.add(CAPA)
    msp = salida.modelspace()

    recintos = 0
    for room in plano.rooms:
        vertices = [(round(x, 4), round(y, 4))
                    for x, y in room.polygon.exterior.coords[:-1]]
        msp.add_lwpolyline(vertices, close=True, dxfattribs={"layer": CAPA})
        if room.label:
            centro = room.polygon.representative_point()
            msp.add_mtext(room.label, dxfattribs={"layer": CAPA}).set_location(
                (round(centro.x, 4), round(centro.y, 4)))
        recintos += 1

    for texto, x, y in etiquetas:
        msp.add_mtext(texto, dxfattribs={"layer": CAPA}).set_location(
            (round(x * factor, 4), round(y * factor, 4)))

    salida.saveas(destino)
    return {
        "recintos": recintos,
        "rotulos": sum(1 for r in plano.rooms if r.label),
        "etiquetas_de_vivienda": len(etiquetas),
        "capa": CAPA,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("origen")
    ap.add_argument("destino")
    args = ap.parse_args()

    resumen = derivar(args.origen, args.destino)
    print("Derivado %s -> %s" % (args.origen, args.destino))
    for clave, valor in resumen.items():
        print("  %-22s %s" % (clave, valor))
    print("\nAhora audítalo antes de commitearlo:")
    print("  python scripts/auditar_fixture_anonimo.py %s" % args.destino)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
