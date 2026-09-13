# -*- coding: utf-8 -*-
"""La tabla de ArchMuse es una plantilla fija: la define ArchMuse, las filas las
pone el plano.

PRD `docs/prd/2026-09-13-cuadro-plantilla-fija.md`, §4.1-§4.5. Hasta el
2026-09-13 ArchMuse clonaba las filas del cuadro del arquitecto y heredaba sus
huecos: filas `pasillo` que el plano no dibuja (y que acababan en `0,00 m²`,
`D-13`) y `terraza 2` para una sola terraza (`C-5`).

Todo contra `tests/fixtures/cuadro_sintetico/`: salón/cocina, dos dormitorios,
un trastero (familia desconocida) y una terraza, con una envolvente construida
ACI 10.
"""
from __future__ import annotations

import copy
import importlib.util
import os
import re
import sys
import tempfile

import pytest
from shapely.geometry import Point, Polygon

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import medicion, parser  # noqa: E402
from analyzer.geometria_recibida import (  # noqa: E402
    SubidaMaterializada, payload_desde_dxf, validar,
)

CARPETA = os.path.join(RAIZ, "tests", "fixtures", "cuadro_sintetico")
FIXTURE = os.path.join(CARPETA, "cuadro_sintetico.dxf")

TITULO = "CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA"
ENCABEZADOS = ("ESPACIOS INTERIORES", "SUPERFICIES UTILES INT.",
               "ESPACIOS EXTERIORES", "SUPERFICIES UTILES EXT.")
_CERO = re.compile(r"(?<![\d.,])0+(?:[.,]0+)?\s*m", re.IGNORECASE)
_SUPERFICIE = re.compile(r"^\d+,\d{2} m²$")


def _generador():
    spec = importlib.util.spec_from_file_location(
        "generar_cuadro_sintetico", os.path.join(CARPETA, "generar.py"))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _pc():
    from analyzer import plantilla_cuadro
    return plantilla_cuadro


def _m2(valor):
    return ("%.2f m²" % valor).replace(".", ",")


def _leer(payload):
    """Un payload, materializado y leído como lo lee el servidor."""
    carpeta = tempfile.mkdtemp(prefix="am_plantilla_")
    destino = os.path.join(carpeta, "m.dxf")
    SubidaMaterializada(validar(payload)).save(destino)
    doc = parser.load_document(destino)
    return doc, parser.leer_plano(doc, layer="00 areas")


def _plantilla(payload=None, ambitos=None, invertir=False):
    if payload is None:
        doc = parser.load_document(FIXTURE)
        plano = parser.leer_plano(doc)
    else:
        doc, plano = _leer(payload)
    if invertir:
        plano.rooms = list(reversed(plano.rooms))
    return _pc().construir(doc, plano, "VT1/3", ambitos=ambitos)


CON_RESPUESTA = {"TRASTERO": "interior"}


# --- Las filas las pone el plano -------------------------------------------

def test_una_fila_por_estancia_medida_y_ninguna_mas():
    p = _plantilla(ambitos=CON_RESPUESTA)
    assert p.titulo == TITULO
    assert tuple(p.encabezados) == ENCABEZADOS
    assert [f.rotulo for f in p.interiores] == [
        "Salón/cocina", "Dormitorio 1", "Dormitorio 2", "Trastero"]
    assert [f.rotulo for f in p.exteriores] == ["Terraza"]


def test_no_hay_fila_para_lo_que_el_plano_no_dibuja():
    """El caso de `D-13`: su cuadro pide pasillo y vestíbulo; el plano no los tiene."""
    textos = " ".join(t.lower() for _f, _c, t in _plantilla(ambitos=CON_RESPUESTA).celdas())
    assert "pasillo" not in textos and "vestibulo" not in textos and "terraza 2" not in textos


def test_cada_fila_lleva_la_superficie_medida_de_su_estancia():
    p = _plantilla(ambitos=CON_RESPUESTA)
    assert {f.rotulo: f.valor for f in p.interiores + p.exteriores} == {
        "Salón/cocina": "20,00 m²", "Dormitorio 1": "12,00 m²",
        "Dormitorio 2": "9,00 m²", "Trastero": "2,70 m²", "Terraza": "4,50 m²"}


def test_el_orden_es_el_de_la_familia_nunca_el_del_plano():
    normal = _plantilla(ambitos=CON_RESPUESTA)
    invertido = _plantilla(ambitos=CON_RESPUESTA, invertir=True)
    assert [f.rotulo for f in invertido.interiores] == [f.rotulo for f in normal.interiores]
    assert invertido.celdas() == normal.celdas()


def test_la_desconocida_va_al_final_de_su_bloque():
    p = _plantilla(ambitos=CON_RESPUESTA)
    assert p.interiores[-1].rotulo == "Trastero"
    exterior = _plantilla(ambitos={"TRASTERO": "exterior"})
    assert [f.rotulo for f in exterior.exteriores] == ["Terraza", "Trastero"]


# --- Interior o exterior: lo decide el arquitecto ---------------------------

def test_sin_respuesta_hay_una_pregunta_y_la_pieza_no_tiene_fila():
    p = _plantilla()
    assert [q.familia for q in p.preguntas] == ["TRASTERO"]
    assert "Trastero" not in [f.rotulo for f in p.interiores + p.exteriores]
    assert any("Trastero" in n for n in p.notas), "la pieza sin fila desaparece (C-6)"


def test_una_pregunta_por_familia_no_por_estancia():
    payload = payload_desde_dxf(FIXTURE)
    for i, (x0, y0) in enumerate(((30.0, 0.0), (34.0, 0.0))):
        payload["recintos"].append({
            "handle": "X%d" % i, "capa": "00 areas", "color": 256, "cerrada": True,
            "vertices": [[x0, y0], [x0 + 2, y0], [x0 + 2, y0 + 1.5], [x0, y0 + 1.5]]})
        payload["textos"].append({"handle": "T%d" % i, "capa": "00 areas", "tipo": "MTEXT",
                                  "texto": "Trastero %d" % (i + 2), "x": x0 + 1, "y": y0 + 0.75})
    p = _plantilla(payload=payload)
    trasteros = [q for q in p.preguntas if q.familia == "TRASTERO"]
    assert len(trasteros) == 1
    assert len(trasteros[0].piezas) >= 2


# --- El cierre --------------------------------------------------------------

def test_el_cierre_de_la_plantilla():
    p = _plantilla(ambitos=CON_RESPUESTA)
    assert [tuple(f) for f in p.cierre] == [
        ("TOTAL SUP. INTERIOR (m2)", "43,70 m²", "TOTAL SUP. EXTERIOR (m2)", "4,50 m²"),
        # C-14: 43,70 + min(4,50 / 2 ; 10 % de 43,70) = 43,70 + 2,25.
        ("TOTAL S. UTIL(m2)", "45,95 m²", "", ""),
        # C-12 firmado: la envolvente rotulada del fixture.
        ("S. CONSTRUIDA C.", _m2(Polygon(_generador().ENVOLVENTE).area), "", ""),
        ("VIVIENDA TIPO", "VT1/3", "NUMERO UDS:", ""),
    ]


def test_c12_esta_firmado():
    """Estuvo a `False` hasta el 2026-09-13 («que lo confirme un arquitecto»).
    Firmado ese día, por rótulo y nunca por color: los casos, en
    `tests/test_c12_construida_por_rotulo.py`."""
    pc = _pc()
    assert pc.C12_FIRMADO is True
    p = _plantilla(ambitos=CON_RESPUESTA)
    assert p.construida_handle
    assert not any(n.startswith("S. CONSTRUIDA C.") for n in p.notas)


def test_c12_mide_la_envolvente_rotulada():
    gen = _generador()
    p = _plantilla(ambitos=CON_RESPUESTA)
    assert p.cierre[2] == ("S. CONSTRUIDA C.", _m2(Polygon(gen.ENVOLVENTE).area), "", "")
    assert p.construida_handle


@pytest.mark.parametrize("ambitos", [None, CON_RESPUESTA], ids=["sin_respuesta", "con_respuesta"])
def test_toda_celda_vacia_de_cierre_tiene_su_nota(ambitos):
    """Hasta `C-14` esto miraba dos etiquetas fijas; ahora qué celda está vacía
    depende de la medición, así que se mira cada una."""
    p = _plantilla(ambitos=ambitos)
    # Por `notas_por_motivo` y no por el principio del texto: dos celdas con el
    # mismo motivo comparten nota, y la nota sólo empieza por la primera.
    etiquetadas = {e for etiquetas, _m in p.notas_por_motivo for e in etiquetas}
    for fila in p.cierre:
        for i in (1, 3):
            etiqueta = fila[i - 1]
            if etiqueta and not fila[i]:
                assert etiqueta.rstrip(":") in etiquetadas, etiqueta


def test_sin_respuesta_los_totales_quedan_vacios_con_motivo():
    """`C-2`: una pieza sin clasificar bloquea las dos superficies."""
    p = _plantilla()
    total = p.cierre[0]
    assert total[1] == "" and total[3] == ""
    assert any(n.startswith("TOTAL SUP. INTERIOR") for n in p.notas)


def test_c12_con_dos_envolventes_al_alcance_del_rotulo_la_construida_queda_vacia():
    payload = payload_desde_dxf(FIXTURE)
    otra = copy.deepcopy(next(r for r in payload["recintos"] if r["color"] == 10))
    otra["handle"] = "ENV2"
    otra["vertices"] = [[-0.3, -0.06], [11.5, -0.06], [11.5, 4.3], [-0.3, 4.3]]
    otra["cerrada"] = True
    payload["recintos"].append(otra)
    p = _plantilla(payload=payload, ambitos=CON_RESPUESTA)
    assert p.cierre[2][1] == ""
    nota = next(n for n in p.notas if n.startswith("S. CONSTRUIDA C."))
    assert "polilíneas" in nota, "tiene que ser el motivo de las dos candidatas, no el de sin firmar"


# --- Invariantes ------------------------------------------------------------

@pytest.mark.parametrize("ambitos", [None, CON_RESPUESTA], ids=["sin_respuesta", "con_respuesta"])
def test_d13_ninguna_celda_de_la_plantilla_es_cero(ambitos):
    celdas = _plantilla(ambitos=ambitos).celdas()
    assert not [t for _f, _c, t in celdas if _CERO.search(t)]


def _payload_sin_terraza():
    """El fixture sin su única estancia exterior: el lado derecho de la tabla
    queda vacío, que es cuando sale la nota de «no hay ningún espacio de este lado»."""
    payload = payload_desde_dxf(FIXTURE)
    donde = next(t for t in payload["textos"] if t["texto"] == "Terraza")
    punto = Point(donde["x"], donde["y"])
    payload["textos"] = [t for t in payload["textos"] if t is not donde]
    payload["recintos"] = [r for r in payload["recintos"]
                           if not Polygon(r["vertices"]).contains(punto)]
    return payload


@pytest.mark.parametrize("payload, ambitos", [
    (None, None), (None, CON_RESPUESTA), (_payload_sin_terraza, CON_RESPUESTA),
], ids=["sin_respuesta", "con_respuesta", "sin_exteriores"])
def test_d13_tampoco_una_nota_escribe_una_superficie_cero(payload, ambitos):
    """Las notas van al plano, debajo de la tabla. Una nota que dijera «un total de
    0,00 m² no es una superficie» pone en el dibujo el mismo «0,00 m²» que `D-13`
    prohíbe en las celdas — y así salió la primera versión, el 2026-09-13.

    **El caso `sin_exteriores` no es de relleno.** Con sólo los dos primeros, este
    test pasaba con esa nota rota: la del lado vacío no sale mientras haya una
    terraza, y sin respuesta la tapa la de `C-2`. Se vio reintroduciendo el fallo
    a propósito: no se puso rojo.
    """
    p = _plantilla(payload=payload() if payload else None, ambitos=ambitos)
    if payload:
        assert any(n.startswith("TOTAL SUP. EXTERIOR") for n in p.notas), (
            "el caso ha dejado de producir la nota del lado vacío: ya no prueba nada")
    assert not [n for n in p.notas if _CERO.search(n)]


@pytest.mark.parametrize("ambitos", [None, CON_RESPUESTA], ids=["sin_respuesta", "con_respuesta"])
def test_c6_toda_pieza_medida_tiene_fila_o_nota(ambitos):
    doc = parser.load_document(FIXTURE)
    plano = parser.leer_plano(doc)
    p = _pc().construir(doc, plano, "VT1/3", ambitos=ambitos)
    con_fila = {f.rotulo for f in p.interiores + p.exteriores}
    for pieza in medicion.medir_planta(plano).viviendas[0].piezas:
        assert pieza.nombre in con_fila or any(pieza.nombre in n for n in p.notas), pieza.nombre


def test_c11_toda_cifra_de_la_plantilla_es_una_medicion():
    gen = _generador()
    p = _plantilla(ambitos=CON_RESPUESTA)
    # 45,95 no es una medida: es `C-14` aplicado a 43,70 y 4,50, las dos de la
    # tabla. Es la única cifra derivada que se admite, y su regla la guarda
    # `test_c14_total_util.py`.
    medidas = {"20,00 m²", "12,00 m²", "9,00 m²", "2,70 m²", "4,50 m²",
               "43,70 m²", "45,95 m²", _m2(Polygon(gen.ENVOLVENTE).area)}
    cifras = {t for _f, _c, t in p.celdas() if _SUPERFICIE.match(t)}
    assert cifras <= medidas, cifras - medidas


# --- Familias (decisión 3 de Pablo) -----------------------------------------

@pytest.mark.parametrize("rotulo, familia, ambito", [
    ("Salón/cocina", "salón + cocina", medicion.AMBITO_INTERIOR),
    ("Salón", "salón", medicion.AMBITO_INTERIOR),
    ("Cocina", "cocina", medicion.AMBITO_INTERIOR),
    ("Pasillo", "pasillo", medicion.AMBITO_INTERIOR),
    ("Distribuidor", "distribuidor", medicion.AMBITO_INTERIOR),
    ("Recibidor", "vestíbulo", medicion.AMBITO_INTERIOR),
    ("Hall", "vestíbulo", medicion.AMBITO_INTERIOR),
    ("Balcón", "balcón", medicion.AMBITO_EXTERIOR),
    ("Porche", "porche", medicion.AMBITO_EXTERIOR),
    ("Tendedero", "tendedero", medicion.AMBITO_EXTERIOR),
])
def test_familias(rotulo, familia, ambito):
    assert medicion.clasificar(rotulo) == (familia, ambito)


def test_el_trastero_de_la_prueba_esta_donde_se_cree():
    doc = parser.load_document(FIXTURE)
    plano = parser.leer_plano(doc)
    trastero = next(r for r in plano.rooms if r.label == "Trastero")
    assert trastero.polygon.contains(Point(9.7, 3.55))
