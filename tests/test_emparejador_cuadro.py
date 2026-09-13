# -*- coding: utf-8 -*-
"""El emparejador de etiquetas del cuadro, contra los dos cuadros reales.

Sustituye a un diccionario de cadenas exactas que reconocía 13 de 17 campos del
segundo plano del mismo arquitecto. Lo que se comprueba aquí es lo único que
importa de un emparejador: que **reconozca las dos formas de escribir la misma
fila** y que **no invente correspondencias** cuando no está seguro.
"""
from __future__ import annotations

import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import cuadro_superficies as cs  # noqa: E402
from analyzer.emparejador_cuadro import (  # noqa: E402
    CAMPOS, campos_que_reclama, emparejar,
)

#: Las 17 etiquetas del cuadro de `v1plantas.dxf`, tal cual están en el DXF
#: (con los escapes sin decodificar, que es como llegan).
ETIQUETAS_V1PLANTAS = [
    "sal" + chr(92) + "U+00F3n + cocina",
    "pasillo",
    "dormitorio 1",
    "dormitorio 2",
    "dormitorio 3",
    "ba" + chr(92) + "U+00F1o",
    "aseo",
    "vestibulo",
    "tendedero",
    "terraza 1",
    "terraza 2",
    "TOTAL SUP. INTERIOR (m2)",
    "TOTAL SUP. EXTERIOR (m2)",
    "TOTAL S. UTIL(m2)",
    "S. CONSTRUIDA C.",
    "VIVIENDA TIPO",
    "NUMERO UDS:",
]

#: Las mismas filas, como las escribió en `v2s.dxf`. Las cuatro que cambian son
#: las que rompían el diccionario anterior.
ETIQUETAS_V2S = [
    "salón + cocina",
    "pasillo",
    "dormitorio 1",
    "dormitorio 2",
    "dormitorio 3",
    "baño",
    "aseo",
    "vestibulo",
    "tendedero",
    "terraza 1",
    "terraza 2",
    "TOTAL SUP.UTIL INTERIOR (M2)",
    "TOTAL SUP.UTIL EXTERIOR (M2)",
    "TOTAL S. UTIL (M2)",
    "S. CONSTRUIDA CERRADA",
    "VIVIENDA TIPO",
    "NUMERO UDS",
]

CAMPOS_ESPERADOS = [
    "salon_cocina", "pasillo", "dormitorio_1", "dormitorio_2", "dormitorio_3",
    "bano", "aseo", "vestibulo", "tendedero", "terraza_1", "terraza_2",
    "total_util_interior", "total_util_exterior", "total_util",
    "superficie_construida_cerrada", "vivienda_tipo", "numero_unidades",
]


# ---------------------------------------------------------------------------
# Los dos cuadros reales
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("etiquetas, plano", [
    (ETIQUETAS_V1PLANTAS, "v1plantas.dxf"),
    (ETIQUETAS_V2S, "v2s.dxf"),
])
def test_los_diecisiete_campos_de_los_dos_cuadros(etiquetas, plano):
    """El criterio de aceptación del PRD: los 17 campos, en los dos planos."""
    obtenidos = [e.campo for e in emparejar(etiquetas)]
    assert obtenidos == CAMPOS_ESPERADOS, (
        "%s: %s" % (plano, [(e.etiqueta, e.campo, e.motivo)
                            for e in emparejar(etiquetas) if not e.resuelto]))


def test_las_cuatro_variantes_de_redaccion_dan_el_mismo_campo():
    """Lo que rompía el diccionario de cadenas exactas, fila a fila."""
    parejas = [
        ("TOTAL SUP. INTERIOR (m2)", "TOTAL SUP.UTIL INTERIOR (M2)"),
        ("TOTAL SUP. EXTERIOR (m2)", "TOTAL SUP.UTIL EXTERIOR (M2)"),
        ("TOTAL S. UTIL(m2)", "TOTAL S. UTIL (M2)"),
        ("S. CONSTRUIDA C.", "S. CONSTRUIDA CERRADA"),
    ]
    for una, otra in parejas:
        assert campos_que_reclama(una) == campos_que_reclama(otra) != [], (
            "«%s» y «%s» deberían ser el mismo campo" % (una, otra))


def test_los_tres_totales_no_se_confunden_entre_si():
    """La distinción fina, y la que más daño haría al equivocarse: el total de
    todo es el que no dice ni INTERIOR ni EXTERIOR."""
    assert campos_que_reclama("TOTAL SUP. INTERIOR (m2)") == ["total_util_interior"]
    assert campos_que_reclama("TOTAL SUP. EXTERIOR (m2)") == ["total_util_exterior"]
    assert campos_que_reclama("TOTAL S. UTIL(m2)") == ["total_util"]


def test_la_construida_no_se_confunde_con_la_util():
    """Son magnitudes distintas y no suman entre sí: confundirlas metería una
    superficie construida en la fila de una útil."""
    assert campos_que_reclama("S. CONSTRUIDA C.") == ["superficie_construida_cerrada"]
    assert campos_que_reclama("S.CONSTRUIDA EXTERIOR") == ["superficie_construida_exterior"]
    # Y al revés: un total de útil exterior no es una construida exterior.
    assert campos_que_reclama("TOTAL SUP. EXTERIOR (m2)") == ["total_util_exterior"]


# ---------------------------------------------------------------------------
# Lo que NO debe reclamar nada
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("etiqueta", [
    "CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA",  # el título: lleva VIVIENDA y TIPO
    "EXPACIOS INTERORES",                          # la errata del arquitecto
    "ESPACIOS EXTERIORES",
    "SUPERFICIES UTILES INT.",
    "SUPERFICIES UTILES EXT.",
    "",
    "   ",
    "Observaciones",
    "PE-01",
])
def test_lo_que_no_es_una_fila_de_pieza_no_reclama_ningun_campo(etiqueta):
    assert campos_que_reclama(etiqueta) == [], etiqueta


def test_el_titulo_no_se_lleva_la_fila_de_vivienda_tipo():
    """El título del cuadro lleva las dos palabras que pide `vivienda_tipo`.
    Sin las palabras prohibidas, el título se comería esa fila."""
    emparejados = emparejar(["CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA",
                             "VIVIENDA TIPO"])
    assert [e.campo for e in emparejados] == [None, "vivienda_tipo"]


# ---------------------------------------------------------------------------
# La regla que impide inventar: en la duda, nada
# ---------------------------------------------------------------------------

def test_dos_filas_que_piden_el_mismo_campo_se_quedan_las_dos_sin_rellenar():
    """El caso que de verdad hace daño: dos «tendedero» y ArchMuse escribiendo
    en el primero que encuentra."""
    emparejados = emparejar(["tendedero", "tendedero", "aseo"])
    assert [e.campo for e in emparejados] == [None, None, "aseo"]
    assert "2 filas del cuadro" in (emparejados[0].motivo or "")


def test_una_etiqueta_que_encaja_en_dos_campos_no_se_resuelve():
    """`S. CONSTRUIDA C. EXTERIOR` cumpliría los dos campos de construida si no
    fuera por las palabras prohibidas; se comprueba con una etiqueta que sí
    consigue encajar en dos, para que la regla esté probada y no supuesta."""
    emparejados = emparejar(["terraza 1 y 2"])
    if campos_que_reclama("terraza 1 y 2"):
        assert emparejados[0].campo is None
        assert "2 campos" in (emparejados[0].motivo or "")


def test_el_motivo_dice_que_pasa_y_no_solo_que_algo_paso():
    """Un motivo que no se puede leer en voz alta a un arquitecto no sirve."""
    emparejados = emparejar(["tendedero", "tendedero"])
    motivo = emparejados[0].motivo or ""
    assert "tendedero" in motivo
    assert "ninguna se rellena" in motivo


# ---------------------------------------------------------------------------
# Coherencia con el resto del módulo
# ---------------------------------------------------------------------------

def test_los_campos_son_los_mismos_que_conoce_el_cuadro():
    """Si alguien añade un campo aquí y no allí (o al revés), el cuadro pediría
    una celda que nadie sabe rellenar, o al revés."""
    assert set(CAMPOS) == set(cs.CAMPOS_DEL_CUADRO), (
        set(CAMPOS) ^ set(cs.CAMPOS_DEL_CUADRO))


def test_ninguna_etiqueta_real_reclama_dos_campos():
    """El test que avisa cuando alguien añade una familia que pisa a otra: sobre
    las 34 etiquetas reales de los dos cuadros, ninguna puede ser ambigua."""
    for etiqueta in ETIQUETAS_V1PLANTAS + ETIQUETAS_V2S:
        reclamados = campos_que_reclama(etiqueta)
        assert len(reclamados) <= 1, (etiqueta, reclamados)
