# -*- coding: utf-8 -*-
"""Una polilínea rotulada como construida nunca es la superficie útil de una estancia.

**Error de cifra del 2026-09-16** (Pablo, en un plano del arquitecto): el
tendedero de una vivienda salía con la superficie de la **construida exterior**.
El plano dibuja dos contornos: el útil, rotulado con su nombre, y a su alrededor
la construida exterior, rotulada «S. construida ext.». Medido en ese plano, fuera
del repositorio:

1. **El útil no entraba.** Su polilínea tiene `closed=False` y no termina en su
   primer vértice sino **encima de su primer tramo** (a un 0,12 % de la diagonal),
   dejando una cola detrás: el hueco entre extremos es el 5,08 % de la diagonal,
   por encima del 1 % de `TOLERANCIA_CIERRE`, y se descartaba por abierta.
2. **La construida ocupaba su sitio.** Sin el útil, el contorno agrupador ya no
   contenía a nadie con su nombre y entraba como «Tendedero»: su superficie iba a
   la fila, al total exterior y al total útil.

Regla de Pablo (firmada, 2026-09-16): **una polilínea rotulada como construida
(cerrada o exterior) nunca puede usarse como superficie útil de una estancia. Si
hay duda sobre cuál es la útil, la celda queda vacía con motivo.**

Todo sobre un plano sintético dibujado aquí con coordenadas escritas a mano:
nada sale de un plano real.
"""
from __future__ import annotations

import os
import sys
import tempfile

import ezdxf
import pytest
from shapely.geometry import Polygon

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import medicion, parser  # noqa: E402
from analyzer import plantilla_cuadro as pc  # noqa: E402
from analyzer.geometria_recibida import SubidaMaterializada, payload_desde_dxf, validar  # noqa: E402

CAPA = "00 areas"
ALTURA = 0.125
VIVIENDA = "VT9/1"

INTERIORES = (
    ("Salón/cocina", 0.0, 0.0, 5.0, 4.0),     # 20,00 m²
    ("Dormitorio 1", 5.1, 0.0, 8.1, 4.0),     # 12,00 m²
    ("Baño", 8.2, 0.0, 10.2, 2.0),            #  4,00 m²
)
ENVOLVENTE = [(-0.2, -0.05), (10.4, -0.05), (10.4, 4.2), (-0.2, 4.2)]

#: El tendedero útil, como el del plano: abierto, empieza en una cola a la
#: izquierda de su esquina y termina 0,004 por encima de su primer tramo.
TENDEDERO_UTIL = [(0.0, -1.7), (2.5, -1.7), (2.5, -0.1), (0.2, -0.1), (0.2, -1.696)]
#: Lo que encierra de verdad: sin la cola.
ANILLO_UTIL = TENDEDERO_UTIL[1:]
#: La construida exterior alrededor, cerrada y con color propio.
CONSTRUIDA_EXTERIOR = [(-0.2, -1.9), (2.7, -1.9), (2.7, -0.05), (-0.2, -0.05)]
#: Su rótulo, debajo: a 0,30 de la construida y a 0,50 del útil (alcance 0,375).
ROTULO_EXTERIOR = (1.3, -2.2)


def _dibujar(tendedero_util=True, color_construida=150, rotulo_exterior="S. construida ext.",
             punto_rotulo=ROTULO_EXTERIOR, util_cerrado=False, extras=(),
             con_construida_exterior=True):
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    doc.header["$LASTSAVEDBY"] = "fixture-sintetico"
    doc.layers.add(CAPA)
    msp = doc.modelspace()

    def texto(t, x, y, altura=ALTURA):
        msp.add_mtext(t, dxfattribs={"layer": CAPA, "char_height": altura, "insert": (x, y)})

    for rotulo, x0, y0, x1, y1 in INTERIORES:
        msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                           dxfattribs={"layer": CAPA})
        texto(rotulo, (x0 + x1) / 2, (y0 + y1) / 2)
    msp.add_lwpolyline(ENVOLVENTE, close=True, dxfattribs={"layer": CAPA, "color": 10})
    texto("S. construida cerrada", 0.0, 4.43)
    texto(VIVIENDA, 6.6, 2.0, 0.3)

    if tendedero_util:
        puntos = ANILLO_UTIL if util_cerrado else TENDEDERO_UTIL
        msp.add_lwpolyline(puntos, close=util_cerrado, dxfattribs={"layer": CAPA})
    atributos = {"layer": CAPA}
    if color_construida is not None:
        atributos["color"] = color_construida
    if con_construida_exterior:
        msp.add_lwpolyline(CONSTRUIDA_EXTERIOR, close=True, dxfattribs=atributos)
    texto("Tendedero", 1.3, -0.9)
    if rotulo_exterior:
        texto(rotulo_exterior, *punto_rotulo)
    for puntos, rotulo, punto in extras:
        msp.add_lwpolyline(puntos, close=True, dxfattribs={"layer": CAPA})
        if rotulo:
            texto(rotulo, *punto)

    carpeta = tempfile.mkdtemp(prefix="am_construida_util_")
    ruta = os.path.join(carpeta, "sintetico.dxf")
    doc.saveas(ruta)
    return ruta


def _por_el_comando(ruta):
    """Por la misma costura que el `.lsp`: el payload y el DXF que materializa."""
    destino = os.path.join(os.path.dirname(ruta), "materializado.dxf")
    SubidaMaterializada(validar(payload_desde_dxf(ruta, CAPA))).save(destino)
    doc = parser.load_document(destino)
    return doc, parser.leer_plano(doc, layer=CAPA)


def _plantilla(ruta):
    doc, plano = _por_el_comando(ruta)
    return pc.construir(doc, plano, VIVIENDA)


def _fila(filas, rotulo):
    return next((f for f in filas if f.rotulo == rotulo), None)


def _total_exterior(p):
    return p.cierre[0][3]


def _total_util(p):
    return p.cierre[1][1]


def _notas_de(p, etiqueta):
    return [n for n in p.notas if etiqueta in n.split(":")[0]]


# --- El caso del plano ---------------------------------------------------------

def test_el_tendedero_mide_el_contorno_util_y_no_la_construida_exterior():
    p = _plantilla(_dibujar())
    util = Polygon(ANILLO_UTIL).area
    construida = Polygon(CONSTRUIDA_EXTERIOR).area
    assert pc._m2(util) != pc._m2(construida)

    tendedero = _fila(p.exteriores, "Tendedero")
    assert tendedero is not None, p.exteriores
    assert tendedero.valor == pc._m2(util)
    assert _total_exterior(p) == pc._m2(util)
    esperado = pc.superficie_util_total(20.0 + 12.0 + 4.0, util)
    assert _total_util(p) == pc._m2(esperado)
    # Nunca la de la construida, en ninguna celda.
    assert pc._m2(construida) not in {t for _f, _c, t in p.celdas()}


def test_el_cierre_montado_sobre_el_primer_tramo_se_recupera_sin_la_cola():
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    abierta = msp.add_lwpolyline(TENDEDERO_UTIL, close=False)
    assert not parser._extremos_coinciden(list(TENDEDERO_UTIL)), "el caso tiene que pasar del 1 %"
    assert parser._esta_cerrada(abierta)
    assert parser._puntos_del_anillo(abierta) == list(ANILLO_UTIL)
    anillo = Polygon(parser._puntos_del_anillo(abierta))
    assert anillo.is_valid
    assert anillo.area == pytest.approx(Polygon(ANILLO_UTIL).area, abs=1e-9)


def test_una_polilinea_bien_cerrada_conserva_todos_sus_vertices():
    msp = ezdxf.new("R2018").modelspace()
    cerrada = msp.add_lwpolyline(TENDEDERO_UTIL, close=True)
    assert parser._puntos_del_anillo(cerrada) == list(TENDEDERO_UTIL)


def test_el_cierre_montado_al_reves_tambien_se_recupera():
    """El primer vértice encima del último tramo: la cola está al final."""
    puntos = [(0.2, -1.696), (0.2, -0.1), (2.5, -0.1), (2.5, -1.7), (0.0, -1.7)]
    msp = ezdxf.new("R2018").modelspace()
    abierta = msp.add_lwpolyline(puntos, close=False)
    assert parser._esta_cerrada(abierta)
    assert Polygon(parser._puntos_del_anillo(abierta)).area == pytest.approx(
        Polygon(puntos[:-1]).area, abs=1e-9)


@pytest.mark.parametrize("primero, ultimo", [
    ((0.0, -1.7), (0.2, -1.5)),     # a 0,20 del primer tramo: abierta de verdad
    ((0.0, -1.7), (-0.3, -1.698)),  # a la altura del tramo, pero fuera de él
    ((-1.0, -1.7), (0.2, -1.696)),  # encima del tramo, con una cola de 1,20: mal dibujada
])
def test_una_polilinea_abierta_de_verdad_sigue_abierta(primero, ultimo):
    puntos = [primero] + TENDEDERO_UTIL[1:-1] + [ultimo]
    msp = ezdxf.new("R2018").modelspace()
    assert not parser._esta_cerrada(msp.add_lwpolyline(puntos, close=False))


# --- La regla: rotulada como construida, nunca útil -------------------------------

def test_sin_contorno_util_la_celda_queda_vacia_con_motivo_y_los_totales_tambien():
    p = _plantilla(_dibujar(tendedero_util=False))
    construida = pc._m2(Polygon(CONSTRUIDA_EXTERIOR).area)

    tendedero = _fila(p.exteriores, "Tendedero")
    assert tendedero is not None, "la estancia no desaparece: se enseña sin cifra"
    assert tendedero.valor == ""
    nota = " ".join(_notas_de(p, "Tendedero"))
    assert "construida" in nota and "S. construida ext." in nota, p.notas
    assert _total_exterior(p) == ""
    assert _total_util(p) == ""
    assert construida not in {t for _f, _c, t in p.celdas()}


def test_sin_contorno_util_la_medicion_tampoco_publica_totales():
    """La web y el agente leen `medicion`, no la plantilla: la misma regla."""
    _doc, plano = _por_el_comando(_dibujar(tendedero_util=False))
    vivienda = next(v for v in medicion.medir_planta(plano).viviendas if v.nombre == VIVIENDA)
    assert vivienda.util_exterior_m2 is None and vivienda.util_interior_m2 is None
    assert any("construida" in m for m in vivienda.impedimentos), vivienda.impedimentos


def test_la_construida_sin_color_propio_tampoco_se_cuela():
    """El descarte de agrupadores exige color propio; esta regla no mira el color."""
    p = _plantilla(_dibujar(color_construida=None))
    tendedero = _fila(p.exteriores, "Tendedero")
    assert tendedero is not None and tendedero.valor == pc._m2(Polygon(ANILLO_UTIL).area)
    assert _total_exterior(p) == pc._m2(Polygon(ANILLO_UTIL).area)


def test_la_forma_larga_del_rotulo_exterior_vale_igual():
    p = _plantilla(_dibujar(tendedero_util=False, rotulo_exterior="Superficie construida exterior"))
    assert _fila(p.exteriores, "Tendedero").valor == ""


def test_con_el_rotulo_al_alcance_de_los_dos_contornos_anidados_la_rotulada_es_la_de_fuera():
    """El caso de las demás viviendas del plano: el rótulo alcanza a los dos. La
    construida contiene a la útil, así que la rotulada es la de fuera y la útil
    se mide sin duda."""
    p = _plantilla(_dibujar(punto_rotulo=(1.3, -1.95), util_cerrado=True))
    assert _fila(p.exteriores, "Tendedero").valor == pc._m2(Polygon(ANILLO_UTIL).area)
    assert _total_exterior(p) == pc._m2(Polygon(ANILLO_UTIL).area)


def test_con_duda_entre_dos_contornos_que_no_se_contienen_las_celdas_quedan_vacias():
    """Rótulo de construida entre el tendedero útil y una terraza vecina, al
    alcance de los dos y sin que ninguno contenga al otro: no se sabe cuál
    rotula, y ninguno se escribe."""
    terraza = [(2.8, -1.9), (5.0, -1.9), (5.0, -0.1), (2.8, -0.1)]
    # Sin la construida exterior alrededor: sólo dos piezas y el rótulo entre ellas.
    ruta = _dibujar(util_cerrado=True, con_construida_exterior=False, punto_rotulo=(2.65, -1.0),
                    extras=[(terraza, "Terraza", (3.9, -1.0))])

    p = _plantilla(ruta)
    assert _fila(p.exteriores, "Tendedero").valor == ""
    assert _fila(p.exteriores, "Terraza").valor == ""
    assert "duda" in " ".join(_notas_de(p, "Tendedero")) or "no se sabe" in " ".join(
        _notas_de(p, "Tendedero")), p.notas
    assert _total_exterior(p) == ""


def test_un_rotulo_de_construida_lejos_no_toca_nada():
    p = _plantilla(_dibujar(punto_rotulo=(1.3, -3.5)))
    assert _fila(p.exteriores, "Tendedero").valor == pc._m2(Polygon(ANILLO_UTIL).area)


def test_el_codigo_de_la_regla_no_lee_el_color():
    import ast
    import inspect
    import textwrap

    from analyzer import construida_rotulada as cr

    arbol = ast.parse(textwrap.dedent(inspect.getsource(cr)))
    nombres = [getattr(n, "attr", None) or getattr(n, "id", None) for n in ast.walk(arbol)
               if isinstance(n, (ast.Attribute, ast.Name))]
    assert not [n for n in nombres if n and "color" in n.lower()]
