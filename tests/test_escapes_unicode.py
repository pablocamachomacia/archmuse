# -*- coding: utf-8 -*-
"""`\\U+00F1` no es una eñe hasta que alguien la decodifica, y nadie lo hacía.

**Esto es un fallo de producción, no una mejora del cuadro de superficies.**
AutoCAD guarda las tildes y las eñes de un TEXT o un MTEXT como una secuencia de
escape —`ba\\U+00F1o`, `sal\\U+00F3n`— y `plain_text()` de ezdxf 1.4.4 **no la
decodifica** (comprobado con la propia librería). Nada en `analyzer/` lo hacía
tampoco. Consecuencia, medida en `v1plantas.dxf` el 2026-09-10:

- el rótulo `Ba\\U+00F1o` normaliza a `BA\\U+00F1O`, que **no casa** con el
  patrón `\\bBANO\\b`;
- así que la pieza no entra ni en superficie interior ni en exterior, y
  `medir_planta` la declara «no se sabe si es interior o exterior por su
  rótulo»;
- y esa sola pieza **bloquea la publicación de las superficies de la vivienda
  entera**.

Dicho en corto: **hasta hoy ArchMuse no medía el baño de ningún plano que
guardara sus eñes así**. No es un caso raro: es cómo AutoCAD guarda un DXF ANSI
con acentos, y el castellano tiene eñes en «baño» — la pieza que aparece en
todas las viviendas.

El arreglo vive en `analyzer/texto_dxf.py`, en un solo sitio, y lo usan los dos
lados: `parser._texto_de` (el rótulo del plano) y `cuadro_superficies._normalizar`
(la etiqueta del cuadro). Arreglar sólo uno de los dos dejaría el otro roto.
"""
from __future__ import annotations

import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import ezdxf  # noqa: E402

from analyzer import cuadro_superficies as cs, medicion, parser  # noqa: E402
from analyzer.texto_dxf import decodificar_escapes  # noqa: E402

#: Los dos escapes reales del plano del arquitecto. En crudo, tal cual están en
#: el DXF: barra invertida, U, signo más, cuatro dígitos hexadecimales.
BANO_CRUDO = r"Ba\U+00F1o"
SALON_CRUDO = r"sal\U+00F3n + cocina"


# ---------------------------------------------------------------------------
# El decodificador
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("crudo, esperado", [
    (BANO_CRUDO, "Baño"),
    (SALON_CRUDO, "salón + cocina"),
    (r"Sal\U+00F3n/cocina", "Salón/cocina"),
    # Varios en la misma cadena, que es lo que pasa en un rótulo largo.
    (r"Ba\U+00F1o y sal\U+00F3n", "Baño y salón"),
    # Hexadecimal en minúscula: AutoCAD escribe mayúsculas, pero un DXF ajeno
    # puede traerlo de cualquier forma y no cuesta nada admitirlo.
    (r"ba\U+00f1o", "baño"),
])
def test_decodifica_los_escapes(crudo, esperado):
    assert decodificar_escapes(crudo) == esperado


@pytest.mark.parametrize("texto", [
    "Baño",                 # ya decodificado: no se toca (es idempotente)
    "Dormitorio 1",
    "",
    r"C:\Users\plano",      # una barra invertida que no abre un escape
    r"100\U+ mal formado",  # `\U+` sin cuatro dígitos: se deja como está
    r"\U+ZZZZ",             # no es hexadecimal
])
def test_lo_que_no_es_un_escape_se_deja_igual(texto):
    assert decodificar_escapes(texto) == texto


def test_es_idempotente():
    """Se puede llamar dos veces sin estropear nada, que es lo que permite
    ponerlo en los dos sitios sin coordinarlos."""
    una = decodificar_escapes(BANO_CRUDO)
    assert decodificar_escapes(una) == una


def test_admite_none_y_no_revienta():
    assert decodificar_escapes(None) == ""


# ---------------------------------------------------------------------------
# El lado del plano: `parser._texto_de`
# ---------------------------------------------------------------------------

def _plano_con_bano(tipo="TEXT"):
    """Una vivienda mínima cuyo baño lleva la eñe escapada, como en el plano
    real. Sintético: no depende de ningún fichero de nadie."""
    doc = ezdxf.new("R2010")
    doc.units = 6
    msp = doc.modelspace()
    piezas = [
        ([(0, 0), (5, 0), (5, 4), (0, 4)], "Sal" + chr(92) + "U+00F3n/cocina"),
        ([(0, 4), (3, 4), (3, 7), (0, 7)], "Dormitorio 1"),
        ([(3, 4), (5, 4), (5, 7), (3, 7)], "Dormitorio 2"),
        ([(0, 7), (2, 7), (2, 9), (0, 9)], BANO_CRUDO),
    ]
    for puntos, etiqueta in piezas:
        msp.add_lwpolyline(puntos, close=True, dxfattribs={"layer": "00 areas"})
        cx = sum(p[0] for p in puntos) / len(puntos)
        cy = sum(p[1] for p in puntos) / len(puntos)
        if tipo == "MTEXT":
            msp.add_mtext(etiqueta, dxfattribs={
                "layer": "00 areas", "char_height": 0.2, "insert": (cx, cy)})
        else:
            msp.add_text(etiqueta, dxfattribs={
                "layer": "00 areas", "height": 0.2, "insert": (cx, cy)})
    return doc


@pytest.mark.parametrize("tipo", ["TEXT", "MTEXT"])
def test_el_rotulo_del_plano_llega_con_la_ene_puesta(tipo):
    doc = _plano_con_bano(tipo)
    plano = parser.leer_plano(doc)
    etiquetas = sorted((r.label or "") for r in plano.rooms)
    assert "Baño" in etiquetas, etiquetas
    assert not any(chr(92) + "U+" in e for e in etiquetas), etiquetas


@pytest.mark.parametrize("tipo", ["TEXT", "MTEXT"])
def test_el_bano_se_clasifica_como_interior(tipo):
    """La consecuencia de producción: sin esto, el baño no es ni interior ni
    exterior y bloquea la vivienda entera."""
    plano = parser.leer_plano(_plano_con_bano(tipo))
    m = medicion.medir_planta(plano)
    vivienda = m.viviendas[0]

    banos = [p for p in vivienda.piezas if p.familia == "baño"]
    assert len(banos) == 1, [(p.rotulo, p.familia, p.ambito) for p in vivienda.piezas]
    assert banos[0].ambito == medicion.AMBITO_INTERIOR

    sin_clasificar = [p for p in vivienda.piezas
                      if p.ambito == medicion.AMBITO_SIN_CLASIFICAR]
    assert sin_clasificar == [], [p.rotulo for p in sin_clasificar]
    assert vivienda.util_interior_m2 is not None, vivienda.impedimentos


# ---------------------------------------------------------------------------
# El lado del cuadro: `cuadro_superficies._normalizar`
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("crudo, esperado", [
    (SALON_CRUDO, "SALON + COCINA"),
    (BANO_CRUDO, "BANO"),
])
def test_la_etiqueta_del_cuadro_normaliza_al_campo(crudo, esperado):
    """Las dos etiquetas del cuadro del arquitecto que no se reconocían."""
    assert cs._normalizar(crudo) == esperado


def test_el_campo_del_cuadro_se_identifica():
    """Y con eso, las dos filas que faltaban tienen campo."""
    from analyzer.emparejador_cuadro import campos_que_reclama

    assert campos_que_reclama(SALON_CRUDO) == ["salon_cocina"]
    assert campos_que_reclama(BANO_CRUDO) == ["bano"]


# ---------------------------------------------------------------------------
# Regresión sobre el plano real, si está en esta máquina
# ---------------------------------------------------------------------------

def _ruta_v1plantas():
    candidata = os.path.join(os.path.dirname(RAIZ), "_material", "v1plantas.dxf")
    return candidata if os.path.isfile(candidata) else None


@pytest.fixture(scope="module")
def documento_real():
    ruta = _ruta_v1plantas()
    if ruta is None:
        pytest.skip("v1plantas.dxf no está en esta máquina (plano real de "
                    "cliente, no versionado)")
    return parser.load_document(ruta)


def test_v1plantas_mide_su_bano(documento_real):
    plano = parser.leer_plano(documento_real)
    banos = [r for r in plano.rooms if (r.label or "") == "Baño"]
    assert len(banos) == 1, sorted((r.label or "") for r in plano.rooms)
    assert round(banos[0].polygon.area, 2) == 4.01


def test_v1plantas_ya_no_tiene_piezas_sin_clasificar(documento_real):
    plano = parser.leer_plano(documento_real)
    m = medicion.medir_planta(plano)
    vt1 = next(v for v in m.viviendas if v.nombre == "VT1/3")
    sin_clasificar = [p.rotulo for p in vt1.piezas
                      if p.ambito == medicion.AMBITO_SIN_CLASIFICAR]
    assert sin_clasificar == [], sin_clasificar


def test_v1plantas_publica_por_fin_sus_superficies(documento_real):
    """Las dos correcciones juntas —el contorno agrupador y los escapes— son lo
    que hace que esta vivienda tenga superficies publicables. Sin las dos, el
    cuadro del arquitecto saldría entero en blanco."""
    plano = parser.leer_plano(documento_real)
    m = medicion.medir_planta(plano)
    vt1 = next(v for v in m.viviendas if v.nombre == "VT1/3")
    assert vt1.impedimentos == (), vt1.impedimentos
    assert vt1.util_interior_m2 is not None
    assert vt1.util_exterior_m2 is not None


def test_v1plantas_detecta_las_filas_del_salon_y_del_bano(documento_real):
    """Y en el cuadro, las dos etiquetas con escape ya tienen campo."""
    cuadro = cs.detectar_cuadro_superficies(documento_real)
    assert cuadro is not None
    campos = {c.campo for c in cuadro.celdas}
    assert "salon_cocina" in campos, sorted(campos)
    assert "bano" in campos, sorted(campos)
