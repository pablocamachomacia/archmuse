# -*- coding: utf-8 -*-
"""El fixture sintético con cuadro: que existe, que no lleva a nadie dentro y
que reproduce lo que promete.

PRD `docs/prd/2026-09-13-cuadro-plantilla-fija.md`, T1. Hasta este fixture,
**ningún DXF del repositorio tenía un `ACAD_TABLE`**, y por eso 1.738 tests en
verde no vieron `D-13`. Estos tests no prueban el producto: prueban que el banco
contra el que se prueba sigue diciendo lo que dice. Un fixture que deja de
reproducir su caso convierte en verdes, sin avisar, a todos los tests que se
apoyan en él.
"""
from __future__ import annotations

import getpass
import importlib.util
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import cuadro_superficies as cs  # noqa: E402
from analyzer import medicion, parser  # noqa: E402

CARPETA = os.path.join(RAIZ, "tests", "fixtures", "cuadro_sintetico")
FIXTURE = os.path.join(CARPETA, "cuadro_sintetico.dxf")


def _generador():
    spec = importlib.util.spec_from_file_location(
        "generar_cuadro_sintetico", os.path.join(CARPETA, "generar.py"))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def leido():
    doc = parser.load_document(FIXTURE)
    return doc, parser.leer_plano(doc)


def test_la_cabecera_no_lleva_el_nombre_de_nadie(leido):
    """**Ya se coló una vez un `$LASTSAVEDBY` con un nombre real**, y el
    repositorio es público. `ezdxf` escribe `'ezdxf'` por defecto; el generador
    lo fija, y aquí se comprueba que ningún valor de la cabecera lleva el usuario
    de la máquina que lo generó."""
    doc, _plano = leido
    assert doc.header.get("$LASTSAVEDBY") == _generador().AUTOR_DE_LA_CABECERA
    usuario = getpass.getuser().lower()
    delatores = [(k, v) for k in doc.header.varnames()
                 for v in [doc.header.get(k)]
                 if isinstance(v, str) and usuario and usuario in v.lower()]
    assert not delatores, delatores


def test_el_cuadro_del_arquitecto_pide_filas_que_el_plano_no_dibuja(leido):
    doc, _plano = leido
    cuadros = cs.detectar_cuadros_superficies(doc)
    assert len(cuadros) == 1, "el ACAD_TABLE inyectado ha dejado de leerse"
    campos = {c.campo for c in cuadros[0].celdas}
    assert {"pasillo", "vestibulo"} <= campos, "sin esto el fixture no reproduce D-13"
    assert {"terraza_1", "terraza_2"} <= campos, "sin esto el fixture no reproduce C-5"


def test_el_plano_dibuja_cinco_estancias_y_una_es_dudosa(leido):
    _doc, plano = leido
    assert sorted(r.label for r in plano.rooms) == [
        "Dormitorio 1", "Dormitorio 2", "Salón/cocina", "Terraza", "Trastero"]
    vivienda = medicion.medir_planta(plano).viviendas[0]
    assert vivienda.nombre == "VT1/3"
    assert [p.nombre for p in vivienda.sin_clasificar] == ["Trastero"]
    terrazas = [p for p in vivienda.piezas if p.familia == "terraza"]
    assert len(terrazas) == 1, "sin una sola terraza el fixture no reproduce C-5"


def test_la_envolvente_no_entra_como_estancia(leido):
    """La polilínea ACI 10 es la superficie construida (`C-12`), no una pieza."""
    doc, plano = leido
    envolventes = [e for e in doc.modelspace().query("LWPOLYLINE")
                   if e.dxf.get("color", 256) == 10]
    assert len(envolventes) == 1 and not envolventes[0].closed
    assert all(round(r.polygon.area, 2) < 40 for r in plano.rooms)


def test_el_generador_reproduce_el_mismo_fixture(tmp_path):
    """Si alguien toca el generador y no regenera, o al revés, esto lo dice."""
    nuevo = _generador().guardar(str(tmp_path / "otra_vez.dxf"))
    a, b = parser.load_document(FIXTURE), parser.load_document(nuevo)
    def huella(doc):
        return sorted((e.dxftype(), e.dxf.layer) for e in doc.modelspace())
    assert huella(a) == huella(b)
    assert ([c.campo for c in cs.detectar_cuadros_superficies(a)[0].celdas]
            == [c.campo for c in cs.detectar_cuadros_superficies(b)[0].celdas])
