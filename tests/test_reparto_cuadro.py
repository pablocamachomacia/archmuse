# -*- coding: utf-8 -*-
"""El reparto: qué celda del cuadro del arquitecto lleva qué texto.

Es la frontera entre lo que decide ArchMuse y lo que escribe AutoCAD. Lo que
sale de aquí lo escribe el cliente CAD con `vla-SetText` **sin interpretar
nada**, así que un error aquí se escribe tal cual dentro del plano de alguien.

Vigila los tres criterios firmados que gobiernan el reparto:

- `C-4` — un `0,00 m²` sólo sobre una medición limpia.
- `C-5` — una ambigüedad de reparto no se reparte ni se suma.
- `C-6` — toda pieza medida acaba en exactamente uno de tres sitios, y si hay
  una pieza sin fila, el total no se rellena.
"""
from __future__ import annotations

import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import cuadro_superficies as cs  # noqa: E402
from analyzer import reparto_cuadro as rc  # noqa: E402


class _Pieza:
    def __init__(self, label, area):
        self.label = label
        self.area_m2 = area


class _Unit:
    def __init__(self, nombre, piezas):
        self.name = nombre
        self.rooms = piezas


def _cuadro(campos):
    """Un cuadro con las filas que se le pidan, en filas consecutivas."""
    celdas = []
    for i, campo in enumerate(campos):
        columna = (rc.COLUMNA_EXTERIOR
                   if campo in cs.CAMPOS_UTIL_EXTERIOR or campo == "total_util_exterior"
                   else rc.COLUMNA_INTERIOR)
        celdas.append(cs.CeldaCuadro(
            campo=campo, etiqueta=campo, columna="D" if columna == 3 else "B",
            x=0.0, y=float(-i), fila=i + 2, columna_indice=columna))
    return cs.CuadroSuperficies(celdas=tuple(celdas))


CAMPOS_TIPICOS = [
    "salon_cocina", "pasillo", "dormitorio_1", "dormitorio_2", "dormitorio_3",
    "bano", "aseo", "vestibulo", "tendedero", "terraza_1", "terraza_2",
    "total_util_interior", "total_util_exterior",
]


def _vivienda_completa():
    return _Unit("VT1/3", [
        _Pieza("Salón/cocina", 21.90),
        _Pieza("Dormitorio 1", 12.72),
        _Pieza("Dormitorio 2", 8.48),
        _Pieza("Dormitorio 3", 8.53),
        _Pieza("Baño", 4.01),
        _Pieza("Aseo", 3.14),
        _Pieza("Tendedero", 4.22),
    ])


# ---------------------------------------------------------------------------
# Lo que se escribe
# ---------------------------------------------------------------------------

def test_cada_celda_lleva_fila_y_columna_de_la_tabla():
    """Es el contrato con el cliente CAD: `vla-SetText` pide fila y columna."""
    unit = _vivienda_completa()
    reparto = rc.calcular_reparto(unit, _cuadro(CAMPOS_TIPICOS), unit.rooms)

    assert reparto.celdas
    for c in reparto.celdas:
        assert c.fila >= 0 and c.columna in (rc.COLUMNA_INTERIOR, rc.COLUMNA_EXTERIOR), c
        assert c.texto.strip()


def test_las_superficies_medidas_van_a_su_fila():
    unit = _vivienda_completa()
    reparto = rc.calcular_reparto(unit, _cuadro(CAMPOS_TIPICOS), unit.rooms)
    porcampo = {c.campo: c.texto for c in reparto.celdas}
    assert porcampo["salon_cocina"] == "21,90 m²"
    assert porcampo["dormitorio_1"] == "12,72 m²"
    assert porcampo["bano"] == "4,01 m²"
    assert porcampo["tendedero"] == "4,22 m²"


# ---------------------------------------------------------------------------
# `C-5` · una ambigüedad no se reparte ni se suma
# ---------------------------------------------------------------------------

def test_una_terraza_para_dos_filas_deja_las_dos_en_blanco():
    """El caso de `v1plantas.dxf`. Ninguna de las dos recibe la cifra."""
    unit = _vivienda_completa()
    unit.rooms.append(_Pieza("Terraza", 3.32))
    reparto = rc.calcular_reparto(unit, _cuadro(CAMPOS_TIPICOS), unit.rooms)

    escritos = {c.campo for c in reparto.celdas}
    assert "terraza_1" not in escritos
    assert "terraza_2" not in escritos
    bloqueados = {n.campo for n in reparto.no_escritas}
    assert {"terraza_1", "terraza_2"} <= bloqueados


def test_dos_tendederos_no_se_suman_en_la_unica_fila():
    unit = _vivienda_completa()
    unit.rooms.append(_Pieza("Tendedero", 8.63))
    reparto = rc.calcular_reparto(unit, _cuadro(CAMPOS_TIPICOS), unit.rooms)

    escritos = {c.campo: c.texto for c in reparto.celdas}
    assert "tendedero" not in escritos, escritos.get("tendedero")
    motivo = next(n.motivo for n in reparto.no_escritas if n.campo == "tendedero")
    assert "No se reparte ni se suma" in motivo


# ---------------------------------------------------------------------------
# `C-4` · el 0,00 sólo sobre una medición limpia
# ---------------------------------------------------------------------------

def test_d13_con_la_medicion_limpia_lo_que_no_existe_no_va_a_cero():
    """`D-13` (Pablo, 2026-09-13), que deroga `C-4`.

    **Hasta ese día este test se llamaba `..._lo_que_no_existe_va_a_cero` y
    afirmaba lo contrario**: con la medición limpia, `pasillo` y `vestibulo`
    inexistentes iban a `0,00 m²`. Es exactamente el fallo que Pablo vio en
    AutoCAD 2027: el estudio mete el pasillo en el salón y ArchMuse escribió dos
    ceros en un cuadro. Ninguna habitación mide cero: no se escriben, y su motivo
    lo dice.
    """
    unit = _vivienda_completa()
    reparto = rc.calcular_reparto(unit, _cuadro(CAMPOS_TIPICOS), unit.rooms,
                                  medicion_limpia=True)
    porcampo = {c.campo: c.texto for c in reparto.celdas}
    assert "pasillo" not in porcampo and "vestibulo" not in porcampo
    motivos = {n.campo: n.motivo for n in reparto.no_escritas}
    assert "D-13" in motivos["pasillo"] and "D-13" in motivos["vestibulo"]


def test_d13_con_impedimentos_abiertos_tampoco_se_escribe_ningun_cero():
    """Lo que `C-4` protegía sigue protegido, y más: con la medición sucia
    tampoco sale un cero, porque ya no sale en ningún caso."""
    unit = _vivienda_completa()
    reparto = rc.calcular_reparto(
        unit, _cuadro(CAMPOS_TIPICOS), unit.rooms,
        medicion_limpia=False,
        impedimentos=("hay 7,08 m² dibujados dos veces",))

    ceros = [c for c in reparto.celdas if c.texto.startswith("0,00")]
    assert ceros == [], [(c.campo, c.texto) for c in ceros]


def test_los_impedimentos_viajan_en_el_reparto():
    unit = _vivienda_completa()
    reparto = rc.calcular_reparto(unit, _cuadro(CAMPOS_TIPICOS), unit.rooms,
                                  medicion_limpia=False,
                                  impedimentos=("un impedimento",))
    assert reparto.medicion_limpia is False
    assert reparto.impedimentos == ("un impedimento",)


# ---------------------------------------------------------------------------
# `C-6` · conservación de la medida
# ---------------------------------------------------------------------------

def test_una_pieza_que_el_cuadro_no_contempla_se_declara():
    """Un trastero medido en un cuadro que no tiene fila de trastero."""
    unit = _vivienda_completa()
    unit.rooms.append(_Pieza("Trastero", 5.5))
    reparto = rc.calcular_reparto(unit, _cuadro(CAMPOS_TIPICOS), unit.rooms)

    sin_fila = [p.rotulo for p in reparto.piezas_sin_fila]
    assert sin_fila == ["Trastero"], sin_fila
    assert reparto.piezas_sin_fila[0].area_m2 == 5.5


def test_si_hay_una_pieza_sin_fila_el_total_no_se_rellena():
    """La consecuencia firmada de `C-6`: un total que no incluye una superficie
    medida es un total falso."""
    unit = _vivienda_completa()
    unit.rooms.append(_Pieza("Trastero", 5.5))
    reparto = rc.calcular_reparto(unit, _cuadro(CAMPOS_TIPICOS), unit.rooms)

    escritos = {c.campo for c in reparto.celdas}
    assert not (escritos & set(cs.CAMPOS_TOTAL_UTIL)), escritos

    motivo = next(n.motivo for n in reparto.no_escritas
                  if n.campo == "total_util_interior")
    assert "Trastero" in motivo and "sería falso" in motivo


def test_sin_piezas_sueltas_el_total_si_se_rellena():
    """El control del test anterior: la regla se dispara por la pieza suelta, no
    por cualquier cosa."""
    unit = _vivienda_completa()
    reparto = rc.calcular_reparto(unit, _cuadro(CAMPOS_TIPICOS), unit.rooms)
    escritos = {c.campo for c in reparto.celdas}
    assert "total_util_interior" in escritos


@pytest.mark.parametrize("extra", [
    None,
    _Pieza("Trastero", 5.5),
    _Pieza("Terraza", 3.32),
    _Pieza("Tendedero", 8.63),
])
def test_toda_pieza_medida_esta_en_exactamente_un_sitio(extra):
    """El invariante de `C-6`, con y sin los casos que lo estresan."""
    unit = _vivienda_completa()
    if extra is not None:
        unit.rooms.append(extra)
    reparto = rc.calcular_reparto(unit, _cuadro(CAMPOS_TIPICOS), unit.rooms)
    assert rc.verificar_conservacion(reparto, unit.rooms) == []


# ---------------------------------------------------------------------------
# Regla de parada: o se escribe algo, o no se toca el plano
# ---------------------------------------------------------------------------

def test_si_no_se_puede_escribir_ninguna_celda_se_dice():
    """Un cuadro cuyas únicas filas están todas bloqueadas."""
    unit = _Unit("VT1/3", [_Pieza("Terraza", 3.32)])
    reparto = rc.calcular_reparto(unit, _cuadro(["terraza_1", "terraza_2"]),
                                  unit.rooms)
    assert reparto.celdas == ()
    assert reparto.se_puede_escribir is False


def test_con_al_menos_una_celda_se_puede_escribir():
    unit = _vivienda_completa()
    reparto = rc.calcular_reparto(unit, _cuadro(CAMPOS_TIPICOS), unit.rooms)
    assert reparto.se_puede_escribir is True


# ---------------------------------------------------------------------------
# El plano real
# ---------------------------------------------------------------------------

def _ruta_v1plantas():
    candidata = os.path.join(os.path.dirname(RAIZ), "_material", "v1plantas.dxf")
    return candidata if os.path.isfile(candidata) else None


@pytest.fixture(scope="module")
def reparto_real():
    ruta = _ruta_v1plantas()
    if ruta is None:
        pytest.skip("v1plantas.dxf no está en esta máquina")
    from analyzer import evaluator, medicion, parser

    doc = parser.load_document(ruta)
    plano = parser.leer_plano(doc)
    cuadro = cs.detectar_cuadro_superficies(doc)
    unit = evaluator.evaluate_advanced(plano.rooms, plano.unit_labels).units[0]
    vivienda = next(v for v in medicion.medir_planta(plano).viviendas
                    if v.nombre == unit.name)
    return rc.calcular_reparto(unit, cuadro, unit.rooms,
                               medicion_limpia=not vivienda.impedimentos,
                               impedimentos=vivienda.impedimentos), unit


def test_v1plantas_reparte_como_se_aprobo(reparto_real):
    """La verdad conocida del plano, celda a celda."""
    reparto, _unit = reparto_real
    porcampo = {c.campo: c.texto for c in reparto.celdas}

    assert porcampo["salon_cocina"] == "21,90 m²"
    assert porcampo["dormitorio_1"] == "12,72 m²"
    assert porcampo["dormitorio_2"] == "8,48 m²"
    assert porcampo["dormitorio_3"] == "8,53 m²"
    assert porcampo["bano"] == "4,01 m²"
    assert porcampo["aseo"] == "3,14 m²"
    assert porcampo["tendedero"] == "4,22 m²"
    assert porcampo["total_util_interior"] == "58,78 m²"
    # Las dos terrazas, en blanco. Y el total exterior, que depende de ellas.
    assert "terraza_1" not in porcampo
    assert "terraza_2" not in porcampo
    assert "total_util_exterior" not in porcampo
    # `C-1`: la suma de interior y exterior no la decide ArchMuse.
    assert "total_util" not in porcampo
    # Celda que el arquitecto ya rellenó: no se toca.
    assert "vivienda_tipo" not in porcampo


def test_v1plantas_cumple_la_conservacion(reparto_real):
    reparto, unit = reparto_real
    assert rc.verificar_conservacion(reparto, unit.rooms) == []


def test_v1plantas_no_deja_ninguna_fila_sin_entender(reparto_real):
    """Las 17 filas del cuadro se identifican; si alguna dejara de hacerlo,
    saldría aquí con su motivo en vez de desaparecer."""
    reparto, _unit = reparto_real
    assert reparto.filas_no_entendidas == (), reparto.filas_no_entendidas


# ---------------------------------------------------------------------------
# Qué vivienda corresponde a este cuadro
# ---------------------------------------------------------------------------

def _cuadro_con_tipo(texto):
    cuadro = _cuadro(CAMPOS_TIPICOS)
    celdas = list(cuadro.celdas) + [cs.CeldaCuadro(
        campo="vivienda_tipo", etiqueta="VIVIENDA TIPO", columna="B",
        x=0.0, y=-99.0, fila=13, columna_indice=1, texto_actual=texto)]
    return cs.CuadroSuperficies(celdas=tuple(celdas))


def test_el_cuadro_encuentra_su_vivienda_aunque_el_espacio_no_coincida():
    """El arquitecto escribe «VT1 /3» en el cuadro y «VT1/3» en el plano."""
    unidades = [_Unit("VT1/3", []), _Unit("VT2/2", [])]
    elegida, motivo = rc.elegir_vivienda(unidades, _cuadro_con_tipo("VT1 /3"))
    assert elegida is not None and elegida.name == "VT1/3", motivo


def test_con_varias_viviendas_y_sin_tipo_declarado_no_se_elige_ninguna():
    """Elegir «la primera» rellenaría el cuadro de una con las cifras de otra, y
    el resultado parecería correcto."""
    unidades = [_Unit("VT1/3", []), _Unit("VT2/2", [])]
    elegida, motivo = rc.elegir_vivienda(unidades, _cuadro(CAMPOS_TIPICOS))
    assert elegida is None
    assert "elegir una al azar" in motivo


def test_con_una_sola_vivienda_no_hace_falta_que_el_cuadro_lo_diga():
    unidades = [_Unit("VT1/3", [])]
    elegida, motivo = rc.elegir_vivienda(unidades, _cuadro(CAMPOS_TIPICOS))
    assert elegida is unidades[0], motivo


def test_si_el_cuadro_dice_una_vivienda_que_no_esta_en_el_plano_se_dice():
    unidades = [_Unit("VT2/2", [])]
    elegida, motivo = rc.elegir_vivienda(unidades, _cuadro_con_tipo("VT9 /9"))
    assert elegida is None
    assert "VT9" in motivo and "VT2/2" in motivo
