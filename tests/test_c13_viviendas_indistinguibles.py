# -*- coding: utf-8 -*-
"""`C-13` · Dos viviendas que no se pueden distinguir no se fusionan.

**Firmado por Pablo el 2026-09-13**: «Si dos viviendas no se pueden distinguir,
no se fusionan: se declara y se deja sin escribir.»

**El fallo, medido ese día.** `evaluator.group_rooms_by_unit_label` agrupaba las
habitaciones por el TEXTO del rótulo más cercano. Dos viviendas rotuladas
`VT1/3` —tipo 1, tres unidades: lo normal en un bloque— salían como UNA, con las
filas repetidas y **TOTAL SUP. INTERIOR 87,40 m²**, la suma de las dos,
presentado como la de una vivienda, con la medición limpia y sin ninguna nota.
Peor que un `0,00`, porque no se ve. Y no era teórico: `plantasimple.dxf` rotula
`VT22/1` dos veces, a 1.385 m una de otra, y el agrupador las fundía.

**El guardián que se pidió:** ninguna cifra puede salir de sumar dos viviendas
distintas. Se comprueba de dos formas, y la que manda es la estructural: cada
vivienda que devuelve el agrupador es la de UN solo rótulo. La comprobación por
valor (que no aparezca 87,40) es un centinela añadido, no la prueba.

Todo contra el fixture sintético duplicado: nada de planos de nadie.
"""
from __future__ import annotations

import copy
import os
import sys
import tempfile

import pytest
from shapely.geometry import Point

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import evaluator, medicion, parser  # noqa: E402
from analyzer.geometria_recibida import SubidaMaterializada, payload_desde_dxf, validar  # noqa: E402

FIXTURE = os.path.join(RAIZ, "tests", "fixtures", "cuadro_sintetico", "cuadro_sintetico.dxf")
ROTULO = "VT1/3"
PIEZAS_POR_VIVIENDA = 5          # salón/cocina, dos dormitorios, trastero, terraza


def _dos_viviendas(segundo_rotulo=ROTULO, desplazamiento=40.0):
    """El fixture y una copia 40 m a la derecha, con el rótulo que se diga."""
    payload = payload_desde_dxf(FIXTURE)
    recintos, textos = [], []
    for r in payload["recintos"]:
        copia = copy.deepcopy(r)
        copia["handle"] = "B%s" % r["handle"]
        copia["vertices"] = [[x + desplazamiento, y] for x, y in r["vertices"]]
        recintos.append(copia)
    for t in payload["textos"]:
        copia = copy.deepcopy(t)
        copia["handle"] = "B%s" % t["handle"]
        copia["x"] = t["x"] + desplazamiento
        if t["texto"] == ROTULO:
            copia["texto"] = segundo_rotulo
        textos.append(copia)
    payload["recintos"] += recintos
    payload["textos"] += textos
    return payload


def _materializar(payload):
    carpeta = tempfile.mkdtemp(prefix="am_c13_")
    ruta = os.path.join(carpeta, "dos_viviendas.dxf")
    SubidaMaterializada(validar(payload)).save(ruta)
    return ruta


def _plano(payload):
    return parser.leer_plano(parser.load_document(_materializar(payload)))


@pytest.fixture(scope="module")
def cliente():
    import app as srv

    return srv.app.test_client()


# --- 1. El agrupador no funde ---------------------------------------------

def test_dos_rotulos_iguales_son_dos_viviendas_y_no_una():
    plano = _plano(_dos_viviendas())
    assert [e for e, _x, _y in plano.unit_labels].count(ROTULO) == 2, "el caso no se ha construido"

    unidades = evaluator.group_rooms_by_unit_label(list(plano.rooms), list(plano.unit_labels))

    assert [u.name for u in unidades] == [ROTULO, ROTULO]
    assert [len(u.rooms) for u in unidades] == [PIEZAS_POR_VIVIENDA, PIEZAS_POR_VIVIENDA]
    assert not ({id(r) for r in unidades[0].rooms} & {id(r) for r in unidades[1].rooms})


def test_ninguna_vivienda_tiene_recintos_de_dos_rotulos():
    """**EL GUARDIÁN.** Estructural, no por valor: si una vivienda del agrupador
    contiene recintos cuyo rótulo más cercano no es el mismo, cualquier total
    suyo suma dos viviendas distintas — se llamen como se llamen."""
    plano = _plano(_dos_viviendas())
    rotulos = list(plano.unit_labels)

    def rotulo_mas_cercano(room):
        c = room.polygon.centroid
        return min(range(len(rotulos)), key=lambda i: c.distance(Point(rotulos[i][1], rotulos[i][2])))

    for unidad in evaluator.group_rooms_by_unit_label(list(plano.rooms), rotulos):
        de_quien = {rotulo_mas_cercano(r) for r in unidad.rooms}
        assert len(de_quien) == 1, (
            "la vivienda «%s» junta recintos de %d rótulos distintos: sus totales "
            "sumarían viviendas distintas" % (unidad.name, len(de_quien)))


# --- 2. Se declara y no se escribe ninguna cifra suya ----------------------

def test_la_medicion_declara_c13_y_no_publica_ningun_total():
    m = medicion.medir_planta(_plano(_dos_viviendas()))
    assert [v.nombre for v in m.viviendas] == [ROTULO, ROTULO]
    for v in m.viviendas:
        assert len(v.piezas) == PIEZAS_POR_VIVIENDA        # las piezas sí se enseñan
        assert v.util_interior_m2 is None and v.util_exterior_m2 is None
        assert "C-13" in v.impedimentos[0] and "2 viviendas" in v.impedimentos[0]
    assert m.util_interior_m2 is None and m.util_exterior_m2 is None


def test_el_comando_no_recibe_tabla_de_las_indistinguibles(cliente):
    payload = _dos_viviendas()
    datos = cliente.post("/api/medicion-geometria", json=payload).get_json()
    repartos = datos["repartos"]
    assert len(repartos) == 1, "una sola entrada por rótulo, no una opción por vivienda"
    assert repartos[0]["ok"] is False and repartos[0]["indistinguible"] is True
    assert "C-13" in repartos[0]["motivo"]
    assert "cuadro_a_dibujar" not in repartos[0]

    texto = cliente.post("/api/medicion-geometria?formato=lisp", json=payload).get_data(as_text=True)
    assert texto.count('("cuadro_a_dibujar"') == 0


def test_ninguna_cifra_sale_de_sumar_dos_viviendas(cliente):
    """Centinela por valor, sobre TODA la respuesta: ni el 87,40 del día que se
    vio, ni ninguna otra suma de las dos viviendas, en ningún campo."""
    datos = cliente.post("/api/medicion-geometria",
                         json=dict(_dos_viviendas(), ambitos={"TRASTERO": "interior"})).get_json()
    sumas_de_dos = {"87,40", "87.4", "96,40", "96.4", "9,00 m²"}   # interior, todo, terrazas

    def recorrer(valor, ruta="respuesta"):
        if isinstance(valor, dict):
            for k, v in valor.items():
                yield from recorrer(v, "%s.%s" % (ruta, k))
        elif isinstance(valor, list):
            for i, v in enumerate(valor):
                yield from recorrer(v, "%s[%d]" % (ruta, i))
        else:
            yield ruta, valor

    encontradas = [(ruta, v) for ruta, v in recorrer(datos)
                   if (isinstance(v, (int, float)) and round(float(v), 2) in (87.4, 96.4))
                   or (isinstance(v, str) and any(s in v for s in sumas_de_dos))]
    assert not encontradas, encontradas


def test_la_web_y_el_agente_se_niegan_con_el_mismo_motivo(tmp_path):
    from agente.herramientas import plano as capacidades
    from analyzer.cuadro_superficies_export import exportar_cuadro_relleno

    ruta = _materializar(_dos_viviendas())

    with pytest.raises(ValueError, match="C-13"):
        exportar_cuadro_relleno(ruta, str(tmp_path / "copia.dxf"))
    assert not (tmp_path / "copia.dxf").exists()

    cuadro = capacidades.cuadro_de_superficies(ruta)
    assert cuadro["ok"] is False and "C-13" in cuadro["detalle"]

    util = capacidades.superficie_util(ruta)
    assert util["ok"] is True
    de_la_vt = [v for v in util["viviendas"] if v["vivienda"] == ROTULO]
    assert len(de_la_vt) == 2
    for v in de_la_vt:
        assert v["valor_m2"] is None
        assert v["motivos"][0]["codigo"] == "vivienda_indistinguible"


# --- 3. El control: con rótulos distintos, todo se mide ---------------------

def test_dos_viviendas_con_rotulos_distintos_si_se_miden(cliente):
    """C-13 no puede convertirse en «dos viviendas = nada»: separadas por su
    rótulo, cada una lleva su tabla y su total, el de ella sola."""
    payload = dict(_dos_viviendas(segundo_rotulo="VT2/3"), ambitos={"TRASTERO": "interior"})
    m = medicion.medir_planta(_plano(payload))
    assert sorted(v.nombre for v in m.viviendas) == ["VT1/3", "VT2/3"]
    assert not [v for v in m.viviendas if any("C-13" in i for i in v.impedimentos)]

    repartos = cliente.post("/api/medicion-geometria", json=payload).get_json()["repartos"]
    assert [r["ok"] for r in repartos] == [True, True]
    for r in repartos:
        rejilla = {(c["fila"], c["columna"]): c["texto"] for c in r["cuadro_a_dibujar"]["celdas"]}
        fila_total = next(f for (f, c), t in rejilla.items() if t == "TOTAL SUP. INTERIOR (m2)")
        assert rejilla[(fila_total, 1)] == "43,70 m²", r["vivienda"]
