# -*- coding: utf-8 -*-
"""Comprueba que la transformacion publicada en el SVG invierte bien:
pixel del SVG -> metro real del DXF, contra room.polygon (verdad conocida).

Ejecutar:  python tests/test_plan_coords.py

LENTO (~1-2 min): parsea ejemplo.dxf entero, 20 MB. No usa el fixture
porque necesita los Room reales en metros, que el JSON no conserva con
la geometria de shapely.

Protege el crosshair y la lectura de coordenadas del workspace CAD: si
alguien cambia _compact_clusters, _grid_layout o el escalado al viewBox
sin actualizar los data-* publicados, las coordenadas empezarian a mentir
en silencio y solo se notaria midiendo a mano sobre el plano.
"""
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer.parser import AREA_LAYER, build_rooms_from_document, extract_unit_labels, load_document  # noqa: E402
from analyzer.evaluator import evaluate_advanced  # noqa: E402
from analyzer import plan_svg  # noqa: E402

DXF = os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf")

# `ejemplo.dxf` es un plano real de cliente: no esta -- ni puede estar -- en el
# repositorio, que es publico. Sin el, este script no comprueba nada, y decirlo
# es la unica salida honesta: reventar con `FileNotFoundError` presenta como
# fallo del producto lo que solo es un fichero que no se puede publicar, y es
# lo primero que le pasaria a cualquiera que clone el repositorio.
if not os.path.isfile(DXF):
    print("[SALTA] ejemplo.dxf no disponible en %s -- este script necesita un "
          "plano real, que no se versiona. Ninguna comprobacion ejecutada." % DXF)
    raise SystemExit(0)

print("parseando", DXF, "...")
doc = load_document(DXF)
rooms = build_rooms_from_document(doc, layer=AREA_LAYER)
labels = extract_unit_labels(doc)
adv = evaluate_advanced(rooms, unit_labels=labels, norte_grados=0.0,
                        tipologia="plurifamiliar", zona_cte="D", densidad_urbana="media")

fallos = []
print()
for vivienda in adv.unit_scores:
    svg = plan_svg.generate_plan_svg(vivienda, norte_grados=0.0)
    if not svg:
        continue
    m = re.search(
        r'data-escala="([\d.]+)" data-ox="([-\d.]+)" data-oy="([-\d.]+)"'
        r' data-minx="([-\d.]+)" data-maxy="([-\d.]+)" data-fiel="(\d)"', svg)
    if not m:
        fallos.append("%s: sin datos de transformacion" % vivienda.unit.name)
        continue
    escala, ox, oy, minx, maxy = (float(g) for g in m.groups()[:5])
    fiel = m.group(6) == "1"

    layout = plan_svg.layout_room_polygons(vivienda)
    grupos = re.findall(r'<g data-room="(\d+)" class="plan-room" data-dx="([-\d.]+)" data-dy="([-\d.]+)">'
                        r'\s*<polygon points="([^"]+)"', svg)
    if not grupos:
        fallos.append("%s: no se pudieron leer los grupos" % vivienda.unit.name)
        continue

    peor = 0.0
    for idx_s, dx_s, dy_s, puntos in grupos:
        idx = int(idx_s)
        dx, dy = float(dx_s), float(dy_s)
        room = vivienda.unit.rooms[idx]
        # primer vertice dibujado, en pixeles
        px, py = (float(v) for v in puntos.split()[0].split(","))
        # invertir: pixel -> metro dibujo -> metro real
        mx = (px - ox) / escala + minx + dx
        my = maxy - (py - oy) / escala + dy
        # verdad: ese vertice tiene que estar en el contorno real de la habitacion
        from shapely.geometry import Point
        d = room.polygon.exterior.distance(Point(mx, my))
        peor = max(peor, d)

    ok = peor < 0.02  # 2 cm de tolerancia (el SVG redondea a 2 decimales de pixel)
    estado = "OK  " if ok else "FALLO"
    print("  [%s] %-10s fiel=%s  error maximo = %.4f m  (%d habitaciones)"
          % (estado, vivienda.unit.name, "si" if fiel else "NO", peor, len(grupos)))
    if not ok:
        fallos.append("%s: error %.4f m" % (vivienda.unit.name, peor))

print()
print("=" * 60)
if fallos:
    print("FALLOS:", fallos)
    sys.exit(1)
print("La transformacion publicada invierte correctamente en todas las viviendas.")
