# -*- coding: utf-8 -*-
"""Guardian de regresion de la ingesta (§12 del PRD de DXF ajenos).

Ejecutar:  python tests/test_ingesta_regresion.py
Congelar:  python tests/test_ingesta_regresion.py --congelar

ArchMuse tiene hoy exactamente un usuario compatible, y `parser.py` es el
archivo con mas consecuencias por linea del repositorio. Cualquier cambio ahi
puede romper el unico caso que funciona sin que nadie se entere, porque el
sintoma no seria una excepcion: seria una superficie distinta.

Asi que antes de tocar `parser.py` se congela lo que produce HOY con
`ejemplo.dxf` -habitaciones, etiquetas, areas, centroides y agrupacion en
viviendas- y a partir de ahi cada tarea del PRD tiene que reproducirlo clavado.

Los centroides estan a proposito: una conversion de escala mal aplicada puede
conservar las areas y mover la geometria, o al reves. Comparar solo areas
dejaria pasar la mitad de los errores posibles.

LENTO (~1-2 min): parsea los 19 MB de ejemplo.dxf.
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer.evaluator import group_rooms_by_unit_label  # noqa: E402
from analyzer.parser import AREA_LAYER, leer_plano, load_document  # noqa: E402

DXF = os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf")
REFERENCIA = os.path.join(RAIZ, "tests", "fixtures", "ejemplo-ingesta-referencia.json")

fallos = []
comprobaciones = 0


def check(ok, etiqueta, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s%s" % ("OK  " if ok else "FALLO", etiqueta, ("  -> " + detalle) if detalle else ""))
    if not ok:
        fallos.append(etiqueta)


def instantanea():
    """Todo lo que la ingesta produce a partir de ejemplo.dxf, en una forma
    estable y comparable: ordenada, redondeada y sin objetos."""
    # A proposito por el camino de producto (`leer_plano`) y no por el de bajo
    # nivel: lo que hay que vigilar es lo que ve el arquitecto. La referencia
    # se congelo antes de que existiera la conversion de escala, asi que si
    # `leer_plano` reproduce esos numeros clavados es que sobre ejemplo.dxf la
    # conversion es la identidad, que es lo que debe ser.
    plano = leer_plano(load_document(DXF), layer=AREA_LAYER)
    rooms = plano.rooms
    unit_labels = plano.unit_labels

    habitaciones = []
    for room in rooms:
        centroide = room.polygon.centroid
        habitaciones.append({
            "etiqueta": room.label or "",
            "area": round(room.area_m2, 4),
            "cx": round(centroide.x, 4),
            "cy": round(centroide.y, 4),
        })
    # El orden de las entidades dentro del DXF no es un contrato: se ordena
    # para que la comparacion no dependa de el.
    habitaciones.sort(key=lambda h: (h["etiqueta"], h["area"], h["cx"], h["cy"]))

    viviendas = []
    for unit in group_rooms_by_unit_label(rooms, unit_labels):
        viviendas.append({
            "nombre": unit.name,
            "habitaciones": sorted((r.label or "") for r in unit.rooms),
            "area_total": round(sum(r.area_m2 for r in unit.rooms), 4),
        })
    viviendas.sort(key=lambda v: v["nombre"])

    return {
        "escala_unidad": plano.escala.unidad,
        "escala_origen": plano.escala.origen,
        "n_habitaciones": len(rooms),
        "n_etiquetas_vt": len(unit_labels),
        "etiquetas_vt": sorted(t for t, _x, _y in unit_labels),
        "habitaciones": habitaciones,
        "viviendas": viviendas,
    }


def congelar():
    if not os.path.exists(DXF):
        print("No se encuentra %s" % DXF)
        return 1
    print("Parseando %s ... (lento)" % DXF)
    datos = instantanea()
    os.makedirs(os.path.dirname(REFERENCIA), exist_ok=True)
    with open(REFERENCIA, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=2, sort_keys=True)
    print("Congelado en %s" % REFERENCIA)
    print("  %d habitaciones, %d viviendas, %d etiquetas VT" % (
        datos["n_habitaciones"], len(datos["viviendas"]), datos["n_etiquetas_vt"]))
    return 0


def comparar():
    if not os.path.exists(REFERENCIA):
        print("No hay referencia congelada. Ejecuta primero:")
        print("  python tests/test_ingesta_regresion.py --congelar")
        return 1
    if not os.path.exists(DXF):
        print("  [SALTA] no se encuentra %s" % DXF)
        return 0

    with open(REFERENCIA, encoding="utf-8") as fh:
        esperado = json.load(fh)

    print("Parseando %s ... (lento)" % DXF)
    actual = instantanea()
    print()

    # La referencia se congelo SIN estos dos campos (la escala aun no existia).
    # Que aparezcan ahora en metros y por acuerdo es la comprobacion de que la
    # conversion no ha movido nada sobre el unico DXF que funciona hoy.
    check(actual["escala_unidad"] == "metros" and actual["escala_origen"] == "acuerdo",
          "ejemplo.dxf se resuelve en metros por acuerdo de cabecera y tamano",
          "%s / %s" % (actual["escala_unidad"], actual["escala_origen"]))

    check(actual["n_habitaciones"] == esperado["n_habitaciones"],
          "mismo numero de habitaciones",
          "%d (esperado %d)" % (actual["n_habitaciones"], esperado["n_habitaciones"]))
    check(actual["etiquetas_vt"] == esperado["etiquetas_vt"],
          "mismas etiquetas de vivienda en el plano")
    check([v["nombre"] for v in actual["viviendas"]] == [v["nombre"] for v in esperado["viviendas"]],
          "mismas viviendas",
          ", ".join(v["nombre"] for v in actual["viviendas"]))

    # Habitacion a habitacion: etiqueta, area y posicion.
    if len(actual["habitaciones"]) == len(esperado["habitaciones"]):
        distintas = [
            (a, e) for a, e in zip(actual["habitaciones"], esperado["habitaciones"]) if a != e
        ]
        check(not distintas, "todas las habitaciones identicas (etiqueta, area y centroide)",
              "" if not distintas else "%d distintas, p.ej. %s vs %s" % (
                  len(distintas), distintas[0][0], distintas[0][1]))
    else:
        check(False, "todas las habitaciones identicas (etiqueta, area y centroide)",
              "no se pueden comparar: distinto numero")

    for viv_a, viv_e in zip(actual["viviendas"], esperado["viviendas"]):
        if viv_a["nombre"] != viv_e["nombre"]:
            continue
        check(viv_a["habitaciones"] == viv_e["habitaciones"],
              "%s: mismas habitaciones" % viv_a["nombre"],
              "%d vs %d" % (len(viv_a["habitaciones"]), len(viv_e["habitaciones"])))
        check(abs(viv_a["area_total"] - viv_e["area_total"]) < 0.0001,
              "%s: misma superficie total" % viv_a["nombre"],
              "%.2f vs %.2f m2" % (viv_a["area_total"], viv_e["area_total"]))

    print()
    print("=" * 55)
    if fallos:
        print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
        for f in fallos:
            print("  - %s" % f)
        print()
        print("La ingesta ha cambiado el resultado sobre el unico DXF que")
        print("funciona hoy. Si el cambio es DELIBERADO, vuelve a congelar")
        print("la referencia a mano y explica por que en el commit.")
        return 1
    print("Todas las comprobaciones OK (%d)" % comprobaciones)
    return 0


if __name__ == "__main__":
    sys.exit(congelar() if "--congelar" in sys.argv else comparar())
