# -*- coding: utf-8 -*-
"""La celda a rellenar es la de la derecha de su etiqueta. Sea cual sea.

**El supuesto que esto retira.** Hasta el 2026-09-11 el reparto daba por hecho un
cuadro de cuatro columnas con las etiquetas en las **pares** (0 y 2) y los
valores en las **impares** (1 y 3) — que es como son los tres cuadros de este
estudio, y nada más que eso lo garantizaba.

**Y es un fallo que no se manifiesta como error.** Un cuadro con las etiquetas en
otras columnas no produce una excepción ni una celda vacía: produce **cifras
correctas escritas en la columna equivocada**, dentro del documento que alguien
firma. Mismo patrón que `C-4` (un `0,00` sobre una lectura fallida) y `C-7` (una
medición limpia a la que le falta media vivienda): el resultado parece bueno.

Lo que se comprueba aquí es que la columna de valor **se deriva** de dónde estaba
la etiqueta que se emparejó, y que cuando no hay sitio a la derecha —o lo que hay
no es de ArchMuse— **no se escribe y se declara**.
"""
from __future__ import annotations

import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import cuadro_superficies as cs  # noqa: E402
from analyzer import reparto_cuadro as rc  # noqa: E402

TITULO = "CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA"

FILAS = [
    ("salón + cocina", "tendedero"),
    ("dormitorio 1", "terraza 1"),
    ("dormitorio 2", "terraza 2"),
    ("dormitorio 3", None),
    ("baño", None),
    ("aseo", None),
]


def _celdas(columna_izquierda=0, columna_derecha=2, ancho=4, sin_hueco=False):
    """Un cuadro con las etiquetas donde se le diga.

    `sin_hueco`: la etiqueta va en la última columna, así que **no hay celda a
    su derecha** donde escribir.
    """
    celdas = [[0, 0, TITULO]]
    for i, (izq, der) in enumerate(FILAS, start=1):
        celdas.append([i, columna_izquierda, izq])
        if der is not None and columna_derecha is not None:
            celdas.append([i, columna_derecha, der])
        # Las celdas de valor van vacías, como en un cuadro por rellenar.
        for c in range(ancho):
            if c not in (columna_izquierda, columna_derecha):
                celdas.append([i, c, ""])
    if sin_hueco:
        celdas = [c for c in celdas if c[1] < ancho]
    return celdas


class _Pieza:
    def __init__(self, label, area):
        self.label = label
        self.area_m2 = area


class _Unit:
    def __init__(self, nombre, piezas):
        self.name = nombre
        self.rooms = piezas


def _vivienda():
    return _Unit("VT1/3", [
        _Pieza("Salón/cocina", 21.90),
        _Pieza("Dormitorio 1", 12.72),
        _Pieza("Dormitorio 2", 8.48),
        _Pieza("Dormitorio 3", 8.53),
        _Pieza("Baño", 4.01),
        _Pieza("Aseo", 3.14),
        _Pieza("Tendedero", 4.22),
    ])


def _reparto(celdas):
    cuadro = cs.cuadro_desde_celdas(celdas)
    assert cuadro is not None, "el cuadro no se ha reconocido"
    unit = _vivienda()
    return cuadro, rc.calcular_reparto(unit, cuadro, unit.rooms)


# ---------------------------------------------------------------------------
# La columna de valor sale de la etiqueta, no de una constante
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("izq, der, ancho", [
    (0, 2, 4),    # el cuadro de este estudio: el caso que ya funcionaba
    (1, 3, 5),    # etiquetas en IMPARES, valores en pares
    (0, 3, 6),    # seis columnas, etiquetas en 0 y 3
    (2, 4, 6),    # etiquetas desplazadas: hay una columna muerta delante
])
def test_cada_valor_va_a_la_derecha_de_su_etiqueta(izq, der, ancho):
    """Con las etiquetas en (1,3) esto escribía en las columnas 1 y 3 — o sea,
    **encima de las propias etiquetas**."""
    cuadro, reparto = _reparto(_celdas(izq, der, ancho))

    for celda in cuadro.celdas:
        assert celda.columna_indice == celda.columna_etiqueta + 1, (
            "el campo %r se rellena en la columna %d y su etiqueta está en la %d"
            % (celda.campo, celda.columna_indice, celda.columna_etiqueta))

    porcampo = {c.campo: c for c in reparto.celdas}
    assert porcampo["salon_cocina"].columna == izq + 1
    assert porcampo["salon_cocina"].texto == "21,90 m²"
    assert porcampo["tendedero"].columna == der + 1
    assert porcampo["tendedero"].texto == "4,22 m²"


def test_un_cuadro_de_dos_columnas_funciona():
    """Etiqueta y valor, nada más. No hay columna «exterior»: las piezas
    exteriores no tienen fila, y eso se declara (`C-6`)."""
    celdas = [[0, 0, TITULO]]
    for i, (izq, _der) in enumerate(FILAS, start=1):
        celdas.append([i, 0, izq])
        celdas.append([i, 1, ""])

    cuadro, reparto = _reparto(celdas)
    porcampo = {c.campo: c for c in reparto.celdas}
    assert porcampo["salon_cocina"].columna == 1
    assert "tendedero" not in porcampo, "no hay fila de tendedero en este cuadro"
    sin_fila = [p.rotulo for p in reparto.piezas_sin_fila]
    assert "Tendedero" in sin_fila, sin_fila


# ---------------------------------------------------------------------------
# Cuando no hay dónde escribir: se declara, no se inventa
# ---------------------------------------------------------------------------

def test_una_etiqueta_en_la_ultima_columna_no_se_rellena():
    """No hay celda a su derecha. Escribir en otro sitio sería elegirlo, y
    escribir fuera de la tabla, peor."""
    celdas = [[0, 0, TITULO]]
    for i, (izq, _d) in enumerate(FILAS, start=1):
        celdas.append([i, 0, ""])
        celdas.append([i, 1, izq])   # etiqueta en la ÚLTIMA columna

    cuadro = cs.cuadro_desde_celdas(celdas)
    assert cuadro is not None
    unit = _vivienda()
    reparto = rc.calcular_reparto(unit, cuadro, unit.rooms)

    assert reparto.celdas == (), [
        (c.campo, c.fila, c.columna) for c in reparto.celdas]
    motivos = " ".join(n.motivo for n in reparto.no_escritas)
    assert "derecha" in motivos or "no tiene" in motivos, motivos


def test_una_celda_de_valor_que_ya_trae_texto_no_se_pisa():
    """Lo que el arquitecto ya escribió es suyo. Ya valía para `VIVIENDA TIPO`;
    aquí se comprueba sobre una fila de superficie cualquiera."""
    celdas = _celdas()
    for c in celdas:
        if c[0] == 1 and c[1] == 1:
            c[2] = "22,00 m²"      # una cifra que él puso a mano
    _cuadro, reparto = _reparto(celdas)

    porcampo = {c.campo: c.texto for c in reparto.celdas}
    assert "salon_cocina" not in porcampo, (
        "se ha sobrescrito una celda que el arquitecto ya tenía rellena")


# ---------------------------------------------------------------------------
# Lo que NO debe cambiar
# ---------------------------------------------------------------------------

def test_el_cuadro_real_del_estudio_sigue_igual():
    """El control: cuatro columnas, etiquetas en 0 y 2. Es el caso de siempre y
    tiene que seguir dando exactamente lo mismo."""
    _cuadro, reparto = _reparto(_celdas(0, 2, 4))
    porcampo = {c.campo: (c.columna, c.texto) for c in reparto.celdas}
    assert porcampo["salon_cocina"] == (1, "21,90 m²")
    assert porcampo["dormitorio_1"] == (1, "12,72 m²")
    assert porcampo["tendedero"] == (3, "4,22 m²")


def test_v1plantas_no_se_mueve():
    """Y sobre el plano real, por si acaso."""
    ruta = os.path.join(os.path.dirname(RAIZ), "_material", "v1plantas.dxf")
    if not os.path.isfile(ruta):
        pytest.skip("v1plantas.dxf no está en esta máquina")
    from analyzer import parser

    doc = parser.load_document(ruta)
    cuadro = cs.detectar_cuadro_superficies(doc)
    assert cuadro is not None
    for celda in cuadro.celdas:
        assert celda.columna_indice == celda.columna_etiqueta + 1, celda.campo
    assert {c.columna_indice for c in cuadro.celdas} == {1, 3}
