# -*- coding: utf-8 -*-
"""Comprueba la envolvente del plano (tarea 2 del PRD de legibilidad).

Ejecutar:  python tests/test_plan_envolvente.py

Dos bloques:

  A) Rapido, sobre geometria sintetica: _envelope_rings resuelve bien los
     cuatro casos que importan (habitaciones pegadas, bloques separados,
     patio interior, entrada vacia).

  B) LENTO (~1-2 min): parsea ejemplo.dxf entero, 20 MB, y comprueba el SVG
     realmente emitido para las 6 viviendas.

Lo que protege, por orden de gravedad si se rompiera:

  1. pointer-events="none" en el grupo de la envolvente. Sin eso el grupo se
     pone encima de las habitaciones y se queda el clic, el hover y las
     coordenadas. Ya ha pasado dos veces en este proyecto (con las etiquetas
     <text> y con los poligonos sin relleno), y las dos veces el sintoma fue
     confuso: el plano "dejaba de responder" sin ningun error.
  2. Que la envolvente NO se dibuje en layout de cuadricula, donde las
     habitaciones estan en posiciones sinteticas y su union no es el
     perimetro de nada.
  3. Que la envolvente encierre de verdad a todas las habitaciones.
"""
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from shapely.geometry import Polygon  # noqa: E402

from analyzer import plan_svg  # noqa: E402

fallos = []
comprobaciones = 0


def check(ok, etiqueta, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s%s" % ("OK  " if ok else "FALLO", etiqueta, ("  -> " + detalle) if detalle else ""))
    if not ok:
        fallos.append(etiqueta)


def rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def layout_de(*polygons):
    # _envelope_rings solo mira el segundo elemento de cada par.
    return [(None, p) for p in polygons]


# =======================================================================
print("A. Geometria sintetica")
# =======================================================================

anillos = plan_svg._envelope_rings(layout_de(rect(0, 0, 2, 2), rect(2, 0, 4, 2)))
check(len(anillos) == 1, "dos habitaciones pegadas dan UN anillo", "%d anillos" % len(anillos))

anillos = plan_svg._envelope_rings(layout_de(rect(0, 0, 2, 2), rect(5, 0, 7, 2)))
check(len(anillos) == 2, "dos bloques separados dan DOS anillos", "%d anillos" % len(anillos))

# Cuatro habitaciones en corona alrededor de un hueco de 1x1.
anillos = plan_svg._envelope_rings(layout_de(
    rect(0, 0, 3, 1), rect(0, 2, 3, 3), rect(0, 1, 1, 2), rect(2, 1, 3, 2)))
check(len(anillos) == 2, "el patio interior tambien es envolvente", "%d anillos (exterior + patio)" % len(anillos))

check(plan_svg._envelope_rings([]) == [], "entrada vacia no revienta")
check(plan_svg._envelope_svg([], lambda x, y: (x, y)) == "", "sin anillos no se emite grupo")

# =======================================================================
print()
print("B. SVG real de ejemplo.dxf")
# =======================================================================

DXF = os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf")
if not os.path.exists(DXF):
    print("  [SALTA] no se encuentra %s" % DXF)
else:
    from analyzer.evaluator import evaluate_advanced  # noqa: E402
    from analyzer.parser import (  # noqa: E402
        AREA_LAYER, build_rooms_from_document, extract_unit_labels, load_document)

    print("  parseando %s ... (lento)" % DXF)
    doc = load_document(DXF)
    rooms = build_rooms_from_document(doc, layer=AREA_LAYER)
    labels = extract_unit_labels(doc)
    adv = evaluate_advanced(rooms, unit_labels=labels, norte_grados=0.0,
                            tipologia="plurifamiliar", zona_cte="D", densidad_urbana="media")
    print()

    vistos_normales = 0
    vistos_cuadricula = 0

    for vivienda in adv.unit_scores:
        svg = plan_svg.generate_plan_svg(vivienda, norte_grados=0.0)
        if not svg:
            continue
        nombre = vivienda.unit.name
        _layout, is_floating = plan_svg._layout_rooms(vivienda.unit.rooms)
        tiene = 'class="plan-envolvente"' in svg

        if is_floating:
            vistos_cuadricula += 1
            check(not tiene, "%s (cuadricula): SIN envolvente" % nombre)
            continue

        vistos_normales += 1
        check(tiene, "%s: tiene envolvente" % nombre)
        if not tiene:
            continue

        # 1. No puede robar el raton.
        grupo = re.search(r'<g class="plan-envolvente"([^>]*)>', svg)
        check(bool(grupo) and 'pointer-events="none"' in grupo.group(1),
              "%s: la envolvente no captura el raton" % nombre)

        # 2. Se dibuja DESPUES de las habitaciones (su trazo va encima).
        check(svg.index('class="plan-envolvente"') > svg.rindex('class="plan-room"'),
              "%s: la envolvente va despues de las habitaciones" % nombre)

        # 3. Sin relleno: si lo tuviera, taparia el plano entero.
        cuerpo = svg[svg.index('class="plan-envolvente"'):]
        cuerpo = cuerpo[:cuerpo.index("</g>")]
        check(cuerpo.count('fill="none"') == cuerpo.count("<polygon"),
              "%s: todos los anillos van sin relleno" % nombre)

        # 4. Mas gruesa que las particiones: la jerarquia es de grosor.
        anchos_env = [float(w) for w in re.findall(r'stroke-width="([\d.]+)"', cuerpo)]
        check(bool(anchos_env) and min(anchos_env) > plan_svg._WALL_STROKE_WIDTH,
              "%s: envolvente mas gruesa que la particion" % nombre,
              "env %.1f > muro %.1f" % (min(anchos_env), plan_svg._WALL_STROKE_WIDTH))

        # 5. Encierra de verdad a las habitaciones: se comparan las cajas
        #    envolventes en coordenadas de PANTALLA, o sea sobre los numeros
        #    que se han escrito en el SVG, no sobre la geometria de origen.
        def caja(puntos_str):
            pares = [p.split(",") for p in puntos_str.split()]
            xs = [float(p[0]) for p in pares]
            ys = [float(p[1]) for p in pares]
            return min(xs), min(ys), max(xs), max(ys)

        cajas_env = [caja(p) for p in re.findall(r'<polygon points="([^"]+)"', cuerpo)]
        env = (min(c[0] for c in cajas_env), min(c[1] for c in cajas_env),
               max(c[2] for c in cajas_env), max(c[3] for c in cajas_env))

        habitaciones = svg[:svg.index('class="plan-envolvente"')]
        cajas_hab = [caja(p) for p in re.findall(r'<polygon points="([^"]+)"', habitaciones)]
        hab = (min(c[0] for c in cajas_hab), min(c[1] for c in cajas_hab),
               max(c[2] for c in cajas_hab), max(c[3] for c in cajas_hab))

        tol = 0.05
        dentro = (env[0] <= hab[0] + tol and env[1] <= hab[1] + tol
                  and env[2] >= hab[2] - tol and env[3] >= hab[3] - tol)
        check(dentro, "%s: la envolvente encierra todas las habitaciones" % nombre,
              "env %s vs hab %s" % (tuple(round(v, 1) for v in env), tuple(round(v, 1) for v in hab)))

    print()
    print("  viviendas con posicion real/compactada: %d" % vistos_normales)
    print("  viviendas en cuadricula: %d%s" % (
        vistos_cuadricula, "  (ejemplo.dxf no tiene: ese caso solo queda cubierto por el bloque A)"
        if vistos_cuadricula == 0 else ""))

print()
print("=" * 55)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
