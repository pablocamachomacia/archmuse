# -*- coding: utf-8 -*-
"""PoC DESECHABLE — cuanto conocimiento arquitectonico hay dentro de las
definiciones BLOCK de `ejemplo.dxf` (VT01..VT25), que el parser de
produccion (`analyzer/parser.py`) nunca lee porque solo recorre el
modelspace y en este DXF hay 0 entidades INSERT en el modelspace.

NO es parte del importador. NO se llama desde app.py ni desde ningun test.
Vive en experimentos/ para poder borrarse sin dejar rastro, igual que
imprimir_grafo.py/comparar_regla.py (ver experimentos/README.md).

Ejecutar:
    python -m experimentos.poc_bloques_vt [ruta.dxf]

Por defecto usa el mismo `ejemplo.dxf` fuera-de-repo que imprimir_grafo.py,
derivado de la ubicacion de este fichero (ver DXF_POR_DEFECTO).

Respalda el informe docs/design/2026-08-11-poc-bloques-vt.md — los numeros
de ese informe salen de correr este script, no estan inventados.
"""
from __future__ import annotations

import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import ezdxf
import ezdxf.bbox as bbox

#: `ejemplo.dxf` es un plano real y vive JUNTO al repositorio, no dentro. Se
#: deriva de la ubicación de este fichero y nunca de una ruta personal: misma
#: convención que `main.py` y que los tests.
DXF_POR_DEFECTO = str(Path(__file__).resolve().parents[2] / "ejemplo.dxf")


def full_expand(block):
    """Entidades directas del bloque + un nivel de INSERT anidado resuelto
    (mobiliario, puertas, ventanas), ya con su transformacion aplicada."""
    for e in block:
        if e.dxftype() == "INSERT":
            yield from e.virtual_entities()
        else:
            yield e


def seccion(titulo):
    print("\n" + "=" * 70)
    print(titulo)
    print("=" * 70)


def main(ruta=DXF_POR_DEFECTO):
    doc = ezdxf.readfile(ruta)
    msp = doc.modelspace()

    # ---- 1. Modelspace: lo que YA lee el parser de produccion ----------
    seccion("1. MODELSPACE (lo que ya extrae analyzer/parser.py)")
    tipos_ms = Counter(e.dxftype() for e in msp)
    print("Entidades por tipo:", dict(tipos_ms.most_common()))
    inserts_ms = [e for e in msp if e.dxftype() == "INSERT"]
    print("INSERT en modelspace (confirmando el hallazgo del informe "
          "2026-08-10):", len(inserts_ms))

    import re
    pat = re.compile(r"\bVT\d{1,2}(/\d+)?\b", re.IGNORECASE)
    etiquetas_vt = [
        (e.text if e.dxftype() == "MTEXT" else e.dxf.text).strip()
        for e in msp
        if e.dxftype() in ("MTEXT", "TEXT")
        and pat.search(e.text if e.dxftype() == "MTEXT" else e.dxf.text or "")
    ]
    print("Etiquetas 'VTn/m' encontradas en el cuadro del modelspace:",
          sorted(set(etiquetas_vt)))

    areas_ms = [e for e in msp if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "00 areas"]
    print("Poligonos de superficie ('00 areas') en modelspace:", len(areas_ms))

    # ---- 2. Definiciones BLOCK VT01..VT25 -------------------------------
    seccion("2. DEFINICIONES BLOCK VT01..VT25 (lo que NUNCA se lee hoy)")
    resumen = []
    total_entidades_directas = 0
    total_entidades_expandidas = 0
    layer_totales = Counter()
    total_puertas = 0
    total_ventanas = 0
    total_muro_len = 0.0

    for i in range(1, 26):
        nombre = f"VT{i:02d}"
        blk = doc.blocks.get(nombre)
        if blk is None:
            print(f"{nombre}: NO EXISTE")
            continue

        directas = list(blk)
        expandidas = list(full_expand(blk))
        total_entidades_directas += len(directas)
        total_entidades_expandidas += len(expandidas)

        bb = bbox.extents(expandidas)
        size = None
        if bb.has_data:
            w = bb.extmax.x - bb.extmin.x
            h = bb.extmax.y - bb.extmin.y
            size = (round(w, 2), round(h, 2), round(w * h, 1))

        for e in directas:
            layer_totales[e.dxf.layer] += 1
            if e.dxftype() == "LINE" and e.dxf.layer == "00 MURO":
                p1, p2 = e.dxf.start, e.dxf.end
                total_muro_len += math.dist((p1.x, p1.y), (p2.x, p2.y))
            if e.dxftype() == "INSERT":
                n = e.dxf.name.lower()
                if "puerta" in n:
                    total_puertas += 1
                elif "vdntestre" in n:
                    total_ventanas += 1

        resumen.append((nombre, len(directas), len(expandidas), size))

    print(f"\n{'bloque':7s} {'ent.directas':>13s} {'ent.expandidas':>15s}  bbox (m)")
    for nombre, nd, ne, size in resumen:
        size_str = f"{size[0]:6.2f} x {size[1]:6.2f} = {size[2]:7.1f} m2" if size else "sin geometria"
        print(f"{nombre:7s} {nd:13d} {ne:15d}  {size_str}")

    seccion("3. AGREGADOS (25 bloques VT, solo entidades directas)")
    print("Total entidades directas:", total_entidades_directas)
    print("Total entidades tras expandir 1 nivel de INSERT anidado:",
          total_entidades_expandidas)
    print("Capas usadas (top 15):", dict(layer_totales.most_common(15)))
    print("Instancias de puerta (INSERT cuyo nombre contiene 'puerta'):",
          total_puertas)
    print("Instancias de ventana (INSERT 'vdntestre', simbolo unico "
          "reutilizado con distinta escala/rotacion):", total_ventanas)
    print("Longitud total de muro (solo LINE en capa '00 MURO', excluye "
          "LWPOLYLINE — es un MINIMO, no el total real):",
          round(total_muro_len, 1), "m")

    ratio = total_entidades_directas / max(1, sum(tipos_ms.values()))
    print(f"\nGeometria en bloques VT vs geometria total en modelspace: "
          f"{total_entidades_directas} vs {sum(tipos_ms.values())} "
          f"-> factor x{ratio:.1f}")

    # ---- 4. Contenido semantico dentro de un bloque VT ------------------
    seccion("4. UN BLOQUE EN DETALLE (VT01) — que hay y que NO hay")
    blk = doc.blocks.get("VT01")
    mtext_vt01 = [(e.text, e.dxf.layer) for e in blk if e.dxftype() == "MTEXT"]
    print("MTEXT dentro de VT01 (etiquetas de instalaciones, NO nombres de "
          "estancia):", mtext_vt01)
    closed = sum(1 for e in blk if e.dxftype() == "LWPOLYLINE" and e.closed)
    open_ = sum(1 for e in blk if e.dxftype() == "LWPOLYLINE" and not e.closed)
    print(f"LWPOLYLINE cerradas: {closed} | abiertas: {open_} "
          "(ninguna etiquetada como recinto/habitacion individual)")

    print("\nEsta PoC no imprime mas: ver docs/design/2026-08-11-poc-bloques-vt.md "
          "para la interpretacion completa.")


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else DXF_POR_DEFECTO
    main(ruta)
