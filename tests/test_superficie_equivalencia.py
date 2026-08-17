# -*- coding: utf-8 -*-
"""La extraccion del calculo de superficie no cambio ni un decimal.

Ejecutar:  python tests/test_superficie_equivalencia.py

Rapido (<3 s): usa ejemplo.dxf si esta disponible, y ademas geometria
sintetica que no depende de ningun fichero externo.

Que protege:

Hasta 2026-08-08 esta expresion estaba escrita TRES veces, identica, en
evaluator.py (lineas 452, 824 y 1230 de entonces):

    sum(r.area_m2 for r in unit.rooms
        if not (r.label and NON_USEFUL_PATTERN.search(_normalize(r.label))))

Se unifico en `_superficie_suelo_agregada_m2` antes de que la ocupacion de
DB-SI (CAP-3) se convirtiera en el cuarto duplicado. La refactorizacion era
EXPLICITAMENTE sin cambio de semantica, asi que este test compara la funcion
nueva contra la expresion antigua reproducida aqui literalmente.

Por que se conserva la expresion vieja dentro del test: es el unico modo de
que "no cambia nada" sea comprobable y no una afirmacion. Si algun dia CAP-1
cambia la semantica a proposito (union en vez de suma, criterio del DB-SI en
vez del propio), este test DEBE fallar y hay que actualizarlo en el mismo
commit que lo cambie -- no antes, no despues.

Lo que este test NO dice: no dice que el calculo sea correcto ni que la
magnitud sea la superficie util del DB-SI. No lo es (ver el docstring de la
propia funcion). Dice unicamente que sigue siendo la de antes.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from shapely.geometry import Polygon  # noqa: E402

from analyzer.evaluator import (  # noqa: E402
    NON_USEFUL_PATTERN,
    Unit,
    _normalize,
    _superficie_suelo_agregada_m2,
    evaluate_circulation_efficiency,
    evaluate_unit_efficiency,
    evaluate_unit_minimum_area,
    group_rooms_by_unit_label,
)
from analyzer.parser import Room  # noqa: E402

fallos = []
comprobaciones = 0


def check(condicion, titulo, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s" % ("OK  " if condicion else "FALLO", titulo))
    if detalle:
        print("         %s" % detalle)
    if not condicion:
        fallos.append(titulo)


def calculo_antiguo(unit):
    """La expresion tal y como estaba, copiada literalmente. No tocar."""
    return sum(
        r.area_m2
        for r in unit.rooms
        if not (r.label and NON_USEFUL_PATTERN.search(_normalize(r.label)))
    )


def rect(x0, y0, ancho, alto, etiqueta):
    return Room(label=etiqueta, layer="00 areas",
                polygon=Polygon([(x0, y0), (x0 + ancho, y0),
                                 (x0 + ancho, y0 + alto), (x0, y0 + alto)]))


print("A. Equivalencia exacta sobre geometria sintetica")

CASOS = [
    ("vivienda normal", [rect(0, 0, 4, 5, "Salon"), rect(5, 0, 3, 4, "Dormitorio 1"),
                         rect(9, 0, 2, 2, "Bano")]),
    ("con terraza y tendedero", [rect(0, 0, 4, 5, "Salon"), rect(5, 0, 3, 3, "Terraza"),
                                 rect(9, 0, 2, 2, "Tendedero")]),
    ("solo excluidas", [rect(0, 0, 3, 3, "Terraza"), rect(4, 0, 2, 2, "Tendedero")]),
    ("piezas sin etiqueta", [rect(0, 0, 4, 5, None), rect(5, 0, 3, 3, "Terraza")]),
    ("minusculas y acentos", [rect(0, 0, 4, 5, "terraza"), rect(5, 0, 3, 3, "Salon/cocina")]),
    ("vivienda vacia", []),
    ("decimales largos", [rect(0, 0, 3.3333333, 7.7777777, "Salon"),
                          rect(9, 0, 1.1111111, 2.2222222, "Terraza")]),
]
for nombre, habitaciones in CASOS:
    u = Unit(name=nombre, rooms=habitaciones)
    nuevo, viejo = _superficie_suelo_agregada_m2(u), calculo_antiguo(u)
    check(repr(nuevo) == repr(viejo), "«%s»: identico bit a bit" % nombre,
          "%r" % nuevo)

print("\nB. Equivalencia sobre ejemplo.dxf (el plano real)")

DXF = os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf")
if not os.path.exists(DXF):
    print("  [SALTA] no se encuentra %s" % DXF)
    print("          las comprobaciones sinteticas de A y C siguen siendo validas")
else:
    from analyzer import parser  # noqa: E402

    plano = parser.leer_plano(parser.load_document(DXF))
    unidades = group_rooms_by_unit_label(plano.rooms, plano.unit_labels)
    check(len(unidades) == 6, "el plano da 6 viviendas", "%d" % len(unidades))

    for u in unidades:
        nuevo, viejo = _superficie_suelo_agregada_m2(u), calculo_antiguo(u)
        check(repr(nuevo) == repr(viejo), "%s: identico bit a bit" % u.name, "%r" % nuevo)

    print("\nC. Los tres consumidores (R03, R07, R14) dan lo mismo que antes")

    # Valores capturados ANTES de la refactorizacion, con repr() para no perder
    # ni un bit. Si alguno cambia (mas alla de la correccion de cierre
    # geometrico de abajo), la refactorizacion dejo de ser neutra.
    #
    # Recalculados el 2026-08-13 tras la correccion de cierre geometrico
    # (analyzer/parser.py::_esta_cerrada, ver tests/test_cierre_recuperado.py):
    # VT1/3, VT3/3, VT4/2, VT5/1 y VT6/2 ganan recintos que antes no se leian
    # (closed=False mal puesto), asi que su total/util/ratio cambia. VT2/2 no
    # tiene ningun recinto afectado y se mantiene igual.
    R03_ESPERADO = {
        "VT1/3": ("66.32868494064316", "58.7837267762472", "0.8862489408444045"),
        "VT2/2": ("58.4428405252531", "50.976887332164566", "0.8722520478815108"),
        "VT3/3": ("66.54792882307746", "59.099203268743615", "0.8880697613574597"),
        "VT4/2": ("58.469539265479256", "50.91271677234972", "0.8707562503816217"),
        "VT5/1": ("45.3148792953543", "41.04679458653981", "0.9058127313769088"),
        "VT6/2": ("74.36955530207942", "46.22524551476647", "0.6215614081192977"),
    }
    for r in evaluate_unit_efficiency(unidades):
        esperado = R03_ESPERADO.get(r.unit_name)
        real = (repr(r.total_area_m2), repr(r.useful_area_m2), repr(r.ratio))
        check(esperado == real, "R03 %s: total/util/ratio sin cambios" % r.unit_name,
              "util=%s ratio=%s" % (real[1], real[2]))

    R07_ESPERADO = {"VT1/3": "58.7837267762472", "VT2/2": "50.976887332164566",
                    "VT3/3": "59.099203268743615", "VT4/2": "50.91271677234972",
                    "VT5/1": "41.04679458653981", "VT6/2": "46.22524551476647"}
    for u in unidades:
        r = evaluate_unit_minimum_area(u, "plurifamiliar")
        check(repr(r.useful_area_m2) == R07_ESPERADO.get(u.name),
              "R07 %s: superficie sin cambios" % u.name, repr(r.useful_area_m2))

    # R14 solo devuelve resultado si la vivienda tiene Pasillo. Ninguna de las 6
    # de ejemplo.dxf lo tiene, asi que las 6 dan None -- y que sigan dando None
    # es exactamente lo que hay que proteger: la refactorizacion no debe haber
    # activado la regla donde antes no se evaluaba.
    for u in unidades:
        check(evaluate_circulation_efficiency(u) is None,
              "R14 %s: sigue sin evaluarse (no hay Pasillo)" % u.name)

print("\nD. R14 con Pasillo: la rama que ejemplo.dxf no ejerce")

con_pasillo = Unit(name="sintetica", rooms=[
    rect(0, 0, 4, 5, "Salon"), rect(5, 0, 1, 6, "Pasillo"),
    rect(7, 0, 3, 3, "Dormitorio 1"), rect(11, 0, 2, 2, "Terraza")])
r = evaluate_circulation_efficiency(con_pasillo)
check(r is not None, "la regla se evalua cuando hay Pasillo")
check(r is not None and repr(r.useful_area_m2) == repr(calculo_antiguo(con_pasillo)),
      "y su superficie coincide con el calculo antiguo",
      repr(r.useful_area_m2) if r else "")

print("\n" + "=" * 60)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
