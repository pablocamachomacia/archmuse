# -*- coding: utf-8 -*-
"""`C-19`: los totales se calculan con las áreas **sin redondear** y sólo se
redondea el resultado final a dos decimales.

Firmado por Pablo el 2026-09-16, siguiendo al arquitecto: total interior, total
exterior, el 50 %/10 % de `C-14` y el total útil. **Aunque a mano la tabla no
cuadre por un céntimo, así lo hace el arquitecto.**

Plano sintético (generador del fixture del cuadro) en el que cada pieza redondea
hacia abajo, así que sumar redondeado y sin redondear da distinto:

    Salón/cocina 5,001 × 4     = 20,004   → 20,00
    Dormitorio 1 3 × 4,001     = 12,003   → 12,00
    Dormitorio 2 3 × 3,0013    =  9,0039  →  9,00
    interior sin redondear       41,0109  → 41,01   (redondeado sumaría 41,00)
    Terraza      3,0029 × 1,5  =  4,50435 →  4,50
    Tendedero    2,0029 × 1,5  =  3,00435 →  3,00
    exterior sin redondear        7,5087  →  7,51   (redondeado sumaría 7,50)
    útil = 41,0109 + min(7,5087 / 2 ; 4,10109) = 44,76525 → 44,77   (redondeado: 44,75)

Nunca contra un plano real.
"""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import cuadro_superficies as cs  # noqa: E402
from analyzer import evaluator, medicion, parser  # noqa: E402
from analyzer import plantilla_cuadro as pc  # noqa: E402

GENERADOR = os.path.join(RAIZ, "tests", "fixtures", "cuadro_sintetico", "generar.py")

RECINTOS = (
    ("Salón/cocina", 0.0, 0.0, 5.001, 4.0),
    ("Dormitorio 1", 5.1, 0.0, 8.1, 4.001),
    ("Dormitorio 2", 8.2, 0.0, 11.2, 3.0013),
    ("Terraza", 0.0, -1.6, 3.0029, -0.1),
    ("Tendedero", 3.1, -1.6, 5.1029, -0.1),
)
CUADRO = (
    (0, 0, "CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA"),
    (1, 0, "ESPACIOS INTERIORES"), (1, 1, "SUPERFICIES UTILES"),
    (2, 0, "salón + cocina"),
    (3, 0, "dormitorio 1"),
    (4, 0, "dormitorio 2"),
    (5, 0, "TOTAL SUP. INTERIOR (m2)"),
    (6, 0, "VIVIENDA TIPO"), (6, 1, "VT1 /3"),
)


@pytest.fixture(scope="module")
def plano_sintetico(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("generar_cuadro_c19", GENERADOR)
    generador = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generador)
    generador.RECINTOS = RECINTOS
    generador.CUADRO = CUADRO
    ruta = generador.guardar(str(tmp_path_factory.mktemp("c19") / "c19.dxf"))
    doc = parser.load_document(ruta)
    return doc, parser.leer_plano(doc)


def test_el_plano_de_verdad_distingue_las_dos_formas_de_sumar(plano_sintetico):
    """Si esto deja de cumplirse, los demás tests pasarían con cualquiera de las dos."""
    _doc, plano = plano_sintetico
    areas = {r.label: r.polygon.area for r in plano.rooms}
    interiores = [areas[n] for n in ("Salón/cocina", "Dormitorio 1", "Dormitorio 2")]
    exteriores = [areas[n] for n in ("Terraza", "Tendedero")]
    assert round(sum(round(a, 2) for a in interiores), 2) == 41.00
    assert round(sum(interiores), 2) == 41.01
    assert round(sum(round(a, 2) for a in exteriores), 2) == 7.50
    assert round(sum(exteriores), 2) == 7.51


def test_la_medicion_suma_sin_redondear(plano_sintetico):
    _doc, plano = plano_sintetico
    [vivienda] = medicion.medir_planta(plano).viviendas
    assert not vivienda.impedimentos, vivienda.impedimentos
    assert vivienda.util_interior_m2 == 41.01
    assert vivienda.util_exterior_m2 == 7.51
    # Cada pieza se sigue publicando redondeada.
    assert sorted(p.area_m2 for p in vivienda.piezas) == [3.00, 4.50, 9.00, 12.00, 20.00]


def test_la_tabla_de_archmuse_suma_sin_redondear_y_el_total_util_tambien(plano_sintetico):
    doc, plano = plano_sintetico
    p = pc.construir(doc, plano, "VT1/3")
    fila = next(f for f in p.cierre if f[0] == pc.TOTAL_INTERIOR)
    assert (fila[1], fila[3]) == ("41,01 m²", "7,51 m²")
    assert next(f for f in p.cierre if f[0] == pc.TOTAL_UTIL)[1] == "44,77 m²"
    # Las filas siguen redondeadas: a mano la columna suma 41,00, y así lo hace el arquitecto.
    assert sorted(f.valor for f in p.interiores) == ["12,00 m²", "20,00 m²", "9,00 m²"]


def test_el_50_y_el_10_por_ciento_no_redondean_antes_de_sumar():
    """`superficie_util_total` recibe las cifras sin redondear y sólo redondea el
    final: 41,0149 + 7,5049 / 2 = 44,76735 → 44,77. Si redondeara la interior, la
    exterior o su mitad antes de sumar (41,01 + 3,75) saldría 44,76."""
    assert pc.superficie_util_total(41.0149, 7.5049) == pc.Decimal("44.77")


def test_el_reparto_sobre_el_cuadro_suma_sin_redondear(plano_sintetico):
    doc, plano = plano_sintetico
    [cuadro] = cs.detectar_cuadros_superficies(doc)
    [unidad] = evaluator.group_rooms_by_unit_label(list(plano.rooms), list(plano.unit_labels))
    por_campo = {c.campo: c for c in cs.calcular_relleno_cuadro(unidad, cuadro.como_plantilla(),
                                                                  unidad.rooms)}
    assert por_campo["salon_cocina"].texto == "20,00 m²"
    assert por_campo["total_util_interior"].texto == "41,01 m²"
