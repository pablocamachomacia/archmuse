# -*- coding: utf-8 -*-
"""`C-14`: TOTAL S. ÚTIL = útil interior + el MENOR entre el 50 % de la útil
exterior y el 10 % de la útil interior.

Firmado por un arquitecto colegiado el 2026-09-13, tras ver la tabla en AutoCAD.
Deroga la parte de `C-1` que dejaba esta fila vacía. Criterio en
`docs/design/2026-09-08-criterios-firmados-de-medicion.md`.

Los tres primeros casos son **los tres que exige el criterio**, con sus cifras.
El resto comprueba lo que el criterio dice que no puede pasar: calcular sobre
una cifra bloqueada.

Todo contra el fixture sintético (`tests/fixtures/cuadro_sintetico/`): salón/cocina
20,00, dormitorios 12,00 y 9,00, trastero 2,70 (familia desconocida) y terraza
4,50. Nunca contra un plano real.
"""
from __future__ import annotations

import os
import sys
import tempfile
from decimal import Decimal

import pytest
from shapely.geometry import Point, Polygon

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import parser  # noqa: E402
from analyzer import plantilla_cuadro as pc  # noqa: E402
from analyzer.geometria_recibida import (  # noqa: E402
    SubidaMaterializada, payload_desde_dxf, validar,
)

FIXTURE = os.path.join(RAIZ, "tests", "fixtures", "cuadro_sintetico", "cuadro_sintetico.dxf")
CON_RESPUESTA = {"TRASTERO": "interior"}


# --- Los tres casos del criterio, con sus cifras --------------------------------

def test_c14_tope_no_activo_el_ejemplo_de_v1plantas():
    """interior 58,78 · exterior 7,54 → 50 % = 3,77 < 10 % = 5,88 → **62,56**.

    Con `C-19` (2026-09-16) sobre las áreas sin redondear: 58,7837 + 7,5450 / 2 =
    62,5562. Al firmarse `C-14` se calculaba con 58,78 y 7,54 y daba 62,55."""
    assert pc.superficie_util_total(58.7837, 7.5450) == Decimal("62.56")


def test_c14_tope_activo_se_suma_el_10_por_ciento_no_la_mitad():
    """interior 100 · exterior 40 → 50 % = 20 > 10 % = 10 → 110, no 120."""
    assert pc.superficie_util_total(100, 40) == Decimal("110.00")


def test_c14_sin_exterior_el_total_es_la_interior():
    assert pc.superficie_util_total(100, 0) == Decimal("100.00")


def test_c14_el_redondeo_en_el_medio_es_hacia_arriba_y_no_depende_de_la_coma_flotante():
    """Decisión declarada, no del criterio: 7,55 / 2 = 3,775 → 62,56. Con
    `float` y `%.2f` saldría según cómo caiga 62.555 en binario."""
    assert pc.superficie_util_total(58.78, 7.55) == Decimal("62.56")


# --- Por la plantilla, que es lo que dibujan el comando, la web y el agente ------

def _leer(payload):
    carpeta = tempfile.mkdtemp(prefix="am_c14_")
    destino = os.path.join(carpeta, "m.dxf")
    SubidaMaterializada(validar(payload)).save(destino)
    doc = parser.load_document(destino)
    return doc, parser.leer_plano(doc, layer="00 areas")


def _plantilla(payload=None, ambitos=CON_RESPUESTA):
    if payload is None:
        doc = parser.load_document(FIXTURE)
        plano = parser.leer_plano(doc)
    else:
        doc, plano = _leer(payload)
    return pc.construir(doc, plano, "VT1/3", ambitos=ambitos)


def _recinto_del_rotulo(payload, rotulo):
    donde = next(t for t in payload["textos"] if t["texto"] == rotulo)
    punto = Point(donde["x"], donde["y"])
    return donde, next(r for r in payload["recintos"] if Polygon(r["vertices"]).contains(punto))


def _sin_terraza():
    payload = payload_desde_dxf(FIXTURE)
    texto, recinto = _recinto_del_rotulo(payload, "Terraza")
    payload["textos"].remove(texto)
    payload["recintos"].remove(recinto)
    return payload


def _terraza_de_20_m2():
    """4 × 5 m, colgada del mismo borde: no pisa ninguna pieza interior."""
    payload = payload_desde_dxf(FIXTURE)
    _texto, recinto = _recinto_del_rotulo(payload, "Terraza")
    recinto["vertices"] = [[0.0, -5.1], [4.0, -5.1], [4.0, -0.1], [0.0, -0.1]]
    return payload


def _fila(p, etiqueta):
    return next(f for f in p.cierre if f[0] == etiqueta)


def _nota(p, etiqueta):
    return next((n for n in p.notas if n.startswith(etiqueta)), None)


def test_c14_en_la_plantilla_tope_no_activo():
    """43,70 + min(4,50 / 2 = 2,25 ; 4,37) = 45,95, y sin nota."""
    p = _plantilla()
    assert _fila(p, pc.TOTAL_INTERIOR)[1] == "43,70 m²"
    assert _fila(p, pc.TOTAL_INTERIOR)[3] == "4,50 m²"
    assert _fila(p, pc.TOTAL_UTIL) == (pc.TOTAL_UTIL, "45,95 m²", "", "")
    assert _nota(p, pc.TOTAL_UTIL) is None, "una cifra escrita no lleva nota de por qué falta"


def test_c14_en_la_plantilla_tope_activo():
    """43,70 + min(20,00 / 2 = 10,00 ; 4,37) = 48,07."""
    p = _plantilla(_terraza_de_20_m2())
    assert _fila(p, pc.TOTAL_INTERIOR)[3] == "20,00 m²"
    assert _fila(p, pc.TOTAL_UTIL)[1] == "48,07 m²"


def test_c14_en_la_plantilla_sin_exterior():
    """El total exterior sigue vacío con su nota (`D-13`: un total vacío no se
    escribe como cero), pero el lado está afirmado: no hay terraza que sumar."""
    p = _plantilla(_sin_terraza())
    assert _fila(p, pc.TOTAL_INTERIOR)[3] == ""
    assert _nota(p, pc.TOTAL_EXTERIOR), "el caso ha dejado de ser «sin exterior»"
    assert _fila(p, pc.TOTAL_UTIL)[1] == "43,70 m²"


# --- No se calcula sobre una cifra bloqueada ------------------------------------

def test_c14_con_la_medicion_bloqueada_el_total_util_queda_vacio_con_motivo():
    """Sin contestar qué es el trastero, `C-2` bloquea interior y exterior."""
    p = _plantilla(ambitos=None)
    assert _fila(p, pc.TOTAL_INTERIOR)[1] == "" and _fila(p, pc.TOTAL_INTERIOR)[3] == ""
    assert _fila(p, pc.TOTAL_UTIL)[1] == ""
    nota = _nota(p, pc.TOTAL_UTIL)
    assert nota and "C-14" in nota and "bloqueada" in nota


@pytest.mark.parametrize("sumandos, bloqueada", [
    ({pc.INTERIOR: None, pc.EXTERIOR: 7.54}, "interior"),
    ({pc.INTERIOR: 58.78, pc.EXTERIOR: None}, "exterior"),
    ({pc.INTERIOR: None, pc.EXTERIOR: None}, "ni la"),
], ids=["interior", "exterior", "las_dos"])
def test_c14_una_sola_cifra_bloqueada_basta_para_no_escribir_el_total(sumandos, bloqueada):
    """Sobre todo el caso `exterior`: con la interior afirmada, calcular
    «58,78 + 0» escribiría una cifra limpia y falsa."""
    valor, motivo = pc._total_util(sumandos)
    assert valor == ""
    assert bloqueada in motivo and "C-14" in motivo


def test_c14_sin_ningun_espacio_interior_no_hay_total():
    valor, motivo = pc._total_util({pc.INTERIOR: 0.0, pc.EXTERIOR: 4.5})
    assert valor == "" and "interior" in motivo


@pytest.mark.parametrize("hacer_payload, ambitos", [
    (None, None), (None, CON_RESPUESTA), (_sin_terraza, CON_RESPUESTA),
    (_terraza_de_20_m2, CON_RESPUESTA), (_terraza_de_20_m2, None),
], ids=["sin_respuesta", "con_respuesta", "sin_exteriores", "tope_activo", "tope_activo_sin_respuesta"])
def test_c14_guardian_el_total_util_solo_existe_si_se_rehace_con_lo_escrito(hacer_payload, ambitos):
    """El guardián: toda cifra de TOTAL S. ÚTIL sale **exactamente** de aplicar
    `C-14` a las dos cifras de la fila de totales —o a un lado sin espacios—, y
    si alguno de los dos lados tiene nota de bloqueo, la celda está vacía."""
    p = _plantilla(hacer_payload() if hacer_payload else None, ambitos)
    fila = _fila(p, pc.TOTAL_INTERIOR)
    escrito = _fila(p, pc.TOTAL_UTIL)[1]

    def lado(texto, filas):
        if texto:
            return float(texto.replace(" m²", "").replace(",", "."))
        return 0.0 if not filas else None

    interior = lado(fila[1], p.interiores)
    exterior = lado(fila[3], p.exteriores)
    if p.impedimentos or interior is None or exterior is None:
        assert escrito == "", "total útil escrito sobre una cifra bloqueada: %r" % escrito
        return
    esperado = pc.superficie_util_total(interior, exterior)
    assert escrito == pc._m2(esperado)
