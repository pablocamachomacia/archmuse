# -*- coding: utf-8 -*-
"""Dos textos dentro de un recinto: cuál es el nombre y cuál el título.

**El fallo, medido el 2026-09-11 en AutoCAD.** Los planos de este estudio rotulan
cada estancia con **dos MTEXT independientes**, uno encima del otro:

    superficie util          <- el título de campo (qué magnitud es)
    Dormitorio 1             <- el nombre de la estancia

No es un MTEXT de dos líneas: son dos entidades, con handles distintos, sin `\\P`
ni `\\n` en ninguna. Los **dos** caen dentro del polígono, y
`match_label_to_room` devolvía `inside[0]` — el primero que llegara. Así que el
rótulo de la estancia dependía del **orden en que el cliente mandara los
textos**, que no es el mismo en `doc.modelspace()` que en un `ssget` de AutoCAD.

Por eso el barrido del 2026-09-10 leyó los ocho nombres bien y el comando, en
AutoCAD, leyó los ocho como «superficie util». Mismo plano, mismo código, dos
resultados. Comprobado invirtiendo el orden: los 8 recintos pasan a llamarse
«superficie util».

**Y el título no es ruido: es dato del arquitecto.** «superficie util» va con los
seis interiores y «superficie util exterior» con los dos exteriores, sin una
excepción. Que se use como declaración de ámbito es otra decisión —propuesta como
`C-8`, sin firmar— y **este fichero no la prueba**: aquí sólo se vigila que un
título de campo nunca sea el nombre de una estancia, y que el resultado no
dependa del orden.
"""
from __future__ import annotations

import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import ezdxf  # noqa: E402

from analyzer import parser  # noqa: E402

CAPA = "00 areas"

#: Las ocho parejas reales de `v1plantas.dxf`, con su título de campo.
PAREJAS = [
    ("superficie util", "Salón/cocina"),
    ("superficie util", "Dormitorio 1"),
    ("superficie util", "Dormitorio 2"),
    ("superficie util", "Dormitorio 3"),
    ("superficie util", "Baño"),
    ("superficie util", "Aseo"),
    ("superficie util exterior", "Terraza"),
    ("superficie util exterior", "Tendedero"),
]


def _plano(orden="normal"):
    """Ocho recintos, cada uno con su título de campo y su nombre dentro.

    `orden` decide si los títulos se escriben antes o después de los nombres. Es
    el parámetro que importa: el resultado **no puede depender de él**.
    """
    doc = ezdxf.new("R2010")
    doc.units = 6
    msp = doc.modelspace()

    titulos, nombres = [], []
    for i, (titulo, nombre) in enumerate(PAREJAS):
        x0, y0 = (i % 4) * 6.0, (i // 4) * 6.0
        msp.add_lwpolyline([(x0, y0), (x0 + 5, y0), (x0 + 5, y0 + 5), (x0, y0 + 5)],
                           close=True, dxfattribs={"layer": CAPA})
        cx, cy = x0 + 2.5, y0 + 2.5
        # El título arriba y el nombre debajo, como en el plano real: separados
        # por algo menos de dos alturas de texto.
        titulos.append((titulo, cx, cy + 0.12))
        nombres.append((nombre, cx, cy - 0.12))

    escribir = titulos + nombres if orden == "titulos_primero" else nombres + titulos
    for texto, x, y in escribir:
        msp.add_mtext(texto, dxfattribs={
            "layer": CAPA, "char_height": 0.125, "insert": (x, y)})
    return doc


def _etiquetas(doc):
    return sorted((r.label or "(sin rótulo)") for r in parser.leer_plano(doc).rooms)


ESPERADAS = sorted(nombre for _t, nombre in PAREJAS)


# ---------------------------------------------------------------------------
# Lo que el arreglo tiene que conseguir
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("orden", ["nombres_primero", "titulos_primero"])
def test_el_nombre_gana_al_titulo_venga_en_el_orden_que_venga(orden):
    """El corazón del asunto: **el resultado no puede depender del orden**.

    Con `titulos_primero` este test fallaba devolviendo ocho «superficie util»,
    que es literalmente lo que se vio en AutoCAD.
    """
    assert _etiquetas(_plano(orden)) == ESPERADAS


@pytest.mark.parametrize("orden", ["nombres_primero", "titulos_primero"])
def test_ningun_recinto_se_llama_como_un_titulo_de_campo(orden):
    etiquetas = _etiquetas(_plano(orden))
    colados = [e for e in etiquetas if "superficie" in e.lower()]
    assert colados == [], (
        "estos recintos han cogido el título de campo como nombre: %s" % colados)


def test_las_dos_vias_leen_lo_mismo():
    """Directa contra la del cliente CAD. Si divergen, una de las dos miente y
    no se sabe cuál — que es exactamente lo que pasó."""
    import tempfile

    from analyzer.geometria_recibida import (
        SubidaMaterializada, escribir_dxf, validar,
    )

    doc = _plano("titulos_primero")
    with tempfile.TemporaryDirectory() as carpeta:
        origen = os.path.join(carpeta, "origen.dxf")
        doc.saveas(origen)
        directa = _etiquetas(parser.load_document(origen))

        from analyzer.geometria_recibida import payload_desde_dxf
        payload = payload_desde_dxf(origen)
        # **Al revés a propósito:** es lo que hace un `ssget` que no recorre en
        # el orden de creación, y lo que hizo el AutoCAD del arquitecto.
        payload["textos"] = list(reversed(payload["textos"]))
        materializado = os.path.join(carpeta, "m.dxf")
        SubidaMaterializada(validar(payload)).save(materializado)
        por_el_cliente = _etiquetas(parser.load_document(materializado))

    assert directa == por_el_cliente == ESPERADAS


# ---------------------------------------------------------------------------
# Lo que NO debe cambiar
# ---------------------------------------------------------------------------

def _plano_suelto(textos_por_recinto):
    """Tres recintos con los textos que se le digan a cada uno.

    Tres y no uno porque `MINIMO_POLIGONOS_CAPA` son 3: con menos, el detector
    de capa se rinde con `CapaIndeterminada` y el test mediría otra cosa.
    """
    doc = ezdxf.new("R2010")
    doc.units = 6
    msp = doc.modelspace()
    for i, textos in enumerate(textos_por_recinto):
        x0 = i * 6.0
        msp.add_lwpolyline([(x0, 0), (x0 + 5, 0), (x0 + 5, 5), (x0, 5)],
                           close=True, dxfattribs={"layer": CAPA})
        for j, texto in enumerate(textos):
            msp.add_mtext(texto, dxfattribs={
                "layer": CAPA, "char_height": 0.2,
                "insert": (x0 + 2.5, 2.5 + j * 0.25)})
    return doc


def test_un_recinto_con_un_solo_texto_sigue_igual():
    """El caso normal —un texto por estancia— no puede verse afectado."""
    doc = _plano_suelto([["Dormitorio 1"], ["Dormitorio 2"], ["Baño"]])
    assert _etiquetas(doc) == ["Baño", "Dormitorio 1", "Dormitorio 2"]


def test_una_estancia_cuyo_unico_texto_es_un_titulo_se_queda_sin_rotulo():
    """El límite del arreglo, y es deliberado: si el ÚNICO texto de un recinto es
    «superficie util», no hay nombre que preferir. Se queda **sin rótulo** —que
    es honesto y ya tiene su sitio en el informe, `recinto_sin_etiqueta`— en vez
    de publicarse con un nombre que no es el suyo.

    Cuesta un rótulo y compra que ninguna pieza se mida como si se llamara
    «superficie util», que es lo que hacía que el reparto la declarara sin fila."""
    doc = _plano_suelto([["superficie util"], ["Dormitorio 2"], ["Baño"]])
    etiquetas = _etiquetas(doc)
    assert "(sin rótulo)" in etiquetas, etiquetas
    assert not any("superficie" in e.lower() for e in etiquetas), etiquetas


# ---------------------------------------------------------------------------
# El plano real
# ---------------------------------------------------------------------------

def _ruta_v1plantas():
    ruta = os.path.join(os.path.dirname(RAIZ), "_material", "v1plantas.dxf")
    return ruta if os.path.isfile(ruta) else None


@pytest.fixture(scope="module")
def payload_real():
    ruta = _ruta_v1plantas()
    if ruta is None:
        pytest.skip("v1plantas.dxf no está en esta máquina")
    from analyzer.geometria_recibida import payload_desde_dxf
    return payload_desde_dxf(ruta)


@pytest.mark.parametrize("invertido", [False, True])
def test_v1plantas_da_los_ocho_nombres_en_cualquier_orden(payload_real, invertido):
    """La reproducción exacta del fallo, sobre el plano de verdad. Con
    `invertido=True` salían ocho «superficie util»."""
    import copy
    import tempfile

    from analyzer.geometria_recibida import SubidaMaterializada, validar

    payload = copy.deepcopy(payload_real)
    if invertido:
        payload["textos"] = list(reversed(payload["textos"]))

    with tempfile.TemporaryDirectory() as carpeta:
        ruta = os.path.join(carpeta, "m.dxf")
        SubidaMaterializada(validar(payload)).save(ruta)
        etiquetas = _etiquetas(parser.load_document(ruta))

    assert etiquetas == sorted([
        "Aseo", "Baño", "Dormitorio 1", "Dormitorio 2", "Dormitorio 3",
        "Salón/cocina", "Tendedero", "Terraza",
    ]), etiquetas
