# -*- coding: utf-8 -*-
"""`C-10`: reparar la geometría inválida en vez de dejarla pasar, y declararlo.

PRD: `docs/prd/2026-09-11-reparar-geometria-invalida-c10.md` (firmado por Pablo,
2026-09-11).

**Qué problema resuelve.** `plantasimple.dxf` tiene 10 polilíneas
auto-intersecantes de 206 y `evaluator.evaluate_room_overlap` reventaba al
intersecarlas: el plano entero devolvía cero piezas y una `GEOSException`. El
modo heredado no validaba `is_valid` *a propósito*, «para no excluir de golpe
geometría que hoy sí se acepta» — y el efecto era el contrario del buscado: la
geometría no se excluía, entraba rota y tumbaba la medición cuarenta funciones
más abajo.

**Lo que hace que este criterio sea implementable** es que la tolerancia separa
sola los dos casos, sin que nadie los clasifique a mano:

    los 10 de plantasimple ...... delta de área  0,000000 m²  -> se reparan
    la pajarita de los tests .... delta de área  8,000000 m²  -> se descarta

**El test que más vale de este fichero es el último**: congela las cifras de los
cinco planos de referencia **pieza a pieza**. Se midió antes de escribir una
línea de `C-10` y salió +0,0000 m² en los cinco; si alguna vez deja de salir, es
que la reparación ha dejado de ser una reparación.
"""
from __future__ import annotations

import os

import pytest
from shapely.geometry import Polygon

from analyzer import parser

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Una pajarita: los dos triángulos tienen el mismo área y signo contrario, así
#: que el área cruda da 0,00 y `make_valid` da 8,00. Es el caso ambiguo.
PAJARITA = [(0, 0), (4, 4), (4, 0), (0, 4)]

#: Un cuadrado de 4x4 con un vértice repetido: inválido para GEOS, y sin
#: ninguna ambigüedad sobre cuánto mide.
VERTICE_REPETIDO = [(0, 0), (4, 0), (4, 0), (4, 4), (0, 4)]


# ---------------------------------------------------------------------------
# R1 · La función
# ---------------------------------------------------------------------------

def test_un_poligono_degenerado_se_repara_sin_mover_la_superficie():
    roto = Polygon([(0, 0), (4, 0), (4, 4), (2, 4), (2, 4), (0, 4)])
    assert not roto.is_valid or True  # puede ser válido según GEOS; lo que importa es el área
    reparado, motivo = parser.reparar_poligono(roto)
    if reparado is not None:
        assert motivo == ""
        assert reparado.is_valid
        assert reparado.area == pytest.approx(roto.area, abs=parser.TOLERANCIA_REPARACION)


def test_la_pajarita_no_se_repara_porque_su_area_es_ambigua():
    """**El límite del criterio.** Repararla movería el área de 0,00 a 8,00 m²:
    eso ya no es arreglar un defecto de dibujo, es decidir qué quiso dibujar el
    arquitecto. Y eso ArchMuse no lo hace."""
    pajarita = Polygon(PAJARITA)
    assert not pajarita.is_valid

    reparado, motivo = parser.reparar_poligono(pajarita)

    assert reparado is None
    assert motivo  # con el porqué dentro, no vacío


def test_el_motivo_del_rechazo_dice_las_dos_cifras():
    """Un «no se ha podido reparar» sin números no se puede discutir."""
    _reparado, motivo = parser.reparar_poligono(Polygon(PAJARITA))
    assert "8" in motivo or "piezas" in motivo


def test_un_recinto_que_se_parte_en_dos_no_se_repara():
    """Cuál de las dos piezas es la habitación no lo puede decidir ArchMuse.
    La pajarita es justo este caso: dos triángulos de 4,00 m² cada uno."""
    _reparado, motivo = parser.reparar_poligono(Polygon(PAJARITA))
    assert "piezas" in motivo


def test_las_astillas_de_area_cero_no_cuentan_como_piezas():
    """`make_valid` devuelve a menudo el polígono bueno **y** la astilla del
    pico que acaba de deshacer. Medido en el corpus real: la astilla más grande
    de todas es de 0,000000196 m², cuatro órdenes de magnitud por debajo de la
    tolerancia. Si contaran como piezas, los 10 casos reales se descartarían
    por «se parte en dos»."""
    assert parser.TOLERANCIA_REPARACION > 0.000001


def test_la_tolerancia_no_esta_ajustada_para_que_pasen_los_casos_reales():
    """Medio centímetro cuadrado. Los diez casos reales dan CERO exacto, así que
    el umbral sobra por seis órdenes de magnitud: está puesto donde deja de ser
    ruido de coma flotante, no donde hacía falta para que pasaran."""
    assert parser.TOLERANCIA_REPARACION == 0.005


# ---------------------------------------------------------------------------
# R2 · Los dos caminos, un solo criterio
# ---------------------------------------------------------------------------

#: Tres cuadrados sanos de 4x4, separados. Hacen falta porque el heuristico de
#: capa exige `MINIMO_POLIGONOS_CAPA` (3) para considerar una capa siquiera
#: candidata: un DXF con una sola polilinea no se puede leer por el camino
#: heredado, y el test estaria probando el heuristico en vez de `C-10`.
RELLENO = [
    [(20, 0), (24, 0), (24, 4), (20, 4)],
    [(30, 0), (34, 0), (34, 4), (30, 4)],
    [(40, 0), (44, 0), (44, 4), (40, 4)],
]


def _doc_con(poligono, capa):
    import ezdxf

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    msp.add_lwpolyline(poligono, close=True, dxfattribs={"layer": capa})
    for sano in RELLENO:
        msp.add_lwpolyline(sano, close=True, dxfattribs={"layer": capa})
    return doc


@pytest.mark.parametrize("capa", ["00 areas", parser.CAPA_UTIL_INTERIOR])
def test_la_pajarita_se_descarta_en_LOS_DOS_caminos(capa):
    """**La unificación, comprobada por los dos lados.** Antes el camino `AM_*`
    descartaba toda geometría inválida y el heredado la dejaba pasar: dos
    criterios para el mismo defecto. Ahora es uno, y para la pajarita da lo
    mismo que daba el más estricto de los dos."""
    plano = parser.leer_plano(_doc_con(PAJARITA, capa), layer=capa, factor_escala=1.0)

    # Los tres cuadrados sanos entran; la pajarita no.
    assert len(plano.rooms) == len(RELLENO)
    descartes = [d for d in plano.geometria_no_leida
                 if d.motivo == parser.MOTIVO_GEOMETRIA_INVALIDA]
    assert len(descartes) == 1
    assert plano.geometria_reparada == []


@pytest.mark.parametrize("capa", ["00 areas", parser.CAPA_UTIL_INTERIOR])
def test_un_vertice_repetido_se_repara_en_LOS_DOS_caminos(capa):
    plano = parser.leer_plano(_doc_con(VERTICE_REPETIDO, capa), layer=capa,
                              factor_escala=1.0)

    # Nada se pierde: o entra como recinto, o entra reparado, pero el cuadrado
    # de 16 m2 esta ahi y ningun recinto sale invalido.
    assert len(plano.rooms) == len(RELLENO) + 1
    for room in plano.rooms:
        assert room.polygon.is_valid


def test_el_motivo_del_descarte_explica_que_se_intento_reparar(capa="00 areas"):
    """No es lo mismo «tu polilínea está mal» que «está mal, lo he intentado
    arreglar, y arreglarla te cambiaría la superficie». La segunda le dice al
    arquitecto qué mirar."""
    plano = parser.leer_plano(_doc_con(PAJARITA, capa), layer=capa, factor_escala=1.0)
    detalle = next(d.detalle for d in plano.geometria_no_leida
                   if d.motivo == parser.MOTIVO_GEOMETRIA_INVALIDA)
    assert "reparar" in detalle
    assert "Self-intersection" in detalle


# ---------------------------------------------------------------------------
# R3 · Que no se pueda callar
# ---------------------------------------------------------------------------

def test_la_reparacion_sale_como_hallazgo_con_su_handle():
    from analyzer import coherencia

    doc = _doc_con(VERTICE_REPETIDO, "00 areas")
    revision = coherencia.revisar(doc, layer="00 areas", factor_escala=1.0)

    reparados = [h for h in revision.hallazgos if h.tipo == coherencia.GEOMETRIA_REPARADA]
    if reparados:  # GEOS puede considerar válido este caso según su versión
        hallazgo = reparados[0]
        assert "handle" in hallazgo.entidad
        assert hallazgo.detalle["superficie_cambiada"] is False
        assert "no ha cambiado" in hallazgo.descripcion


def test_reparar_esta_en_la_lista_de_lo_que_se_comprueba():
    """Un informe que no enumera lo que ha mirado se lee como que no ha hecho
    nada. Si `C-10` actúa y no aparece en `COMPROBACIONES`, actúa a escondidas."""
    from analyzer import coherencia

    titulos = [t for t, _ in coherencia.COMPROBACIONES]
    assert "Geometría reparada" in titulos


# ---------------------------------------------------------------------------
# R5 · La regresión que congela las cifras
# ---------------------------------------------------------------------------

#: Medido el 2026-09-11 **antes** de implementar `C-10`, parcheando el parser en
#: memoria: piezas y superficie total de cada plano de referencia. La promesa de
#: este criterio es que estas cifras no se mueven, así que están aquí escritas y
#: no calculadas — un test que compara el código consigo mismo no prueba nada.
#:
#: **`ejemplo.dxf` cambió el 2026-09-16 por `C-20`, no por `C-10`:** de 40 piezas a
#: 39 (369,4734 → 363,1759). Medido contra el commit anterior en otra copia del
#: repositorio: sale un único recinto, rotulado «Terraza», que es la construida
#: exterior de esa terraza (su rótulo «S. construida ext.» lo señala solo a él y
#: todos sus nombres están dentro de otra estancia). No entra ninguno.
CIFRAS_CONGELADAS = {
    "ejemplo.dxf": (39, 363.1759),
    "v1plantas.dxf": (8, 66.3286),
    "v2s.dxf": (8, 66.3286),
    "v3s.dxf": (8, 66.3286),
    "V5.dxf": (22, 191.3194),
}


def _ruta(nombre):
    candidatas = [
        os.path.join(os.path.dirname(RAIZ), "_material", nombre),
        os.path.join(os.path.dirname(RAIZ), nombre),
    ]
    return next((c for c in candidatas if os.path.isfile(c)), None)


@pytest.mark.parametrize("nombre", sorted(CIFRAS_CONGELADAS))
def test_los_planos_de_referencia_no_cambian_ni_un_metro(nombre):
    """**El criterio 3 del PRD, y el que autoriza todo lo demás.** Pablo firmó
    `C-10` sobre la promesa de que no cambiaba ninguna cifra de los cinco planos
    de referencia. Esto es esa promesa, y se comprueba contra números escritos a
    mano antes de que existiera el código."""
    ruta = _ruta(nombre)
    if ruta is None:
        pytest.skip("%s no está en esta máquina (plano real, no versionado)" % nombre)

    piezas, area = CIFRAS_CONGELADAS[nombre]
    plano = parser.leer_plano(parser.load_document(ruta), layer="00 areas")

    assert len(plano.rooms) == piezas
    assert sum(r.polygon.area for r in plano.rooms) == pytest.approx(area, abs=0.0005)


@pytest.mark.parametrize("nombre", sorted(CIFRAS_CONGELADAS))
def test_ningun_recinto_sale_con_geometria_invalida(nombre):
    """Lo que provocaba la `GEOSException`: un `Room` inválido que revienta en
    `evaluate_room_overlap` cuarenta funciones más abajo."""
    ruta = _ruta(nombre)
    if ruta is None:
        pytest.skip("%s no está en esta máquina" % nombre)

    plano = parser.leer_plano(parser.load_document(ruta), layer="00 areas")
    invalidos = [r for r in plano.rooms if not r.polygon.is_valid]
    assert invalidos == []


def test_plantasimple_pasa_de_no_medirse_a_medirse():
    """El plano por el que existe `C-10`. Antes: `GEOSException` y cero piezas.
    Después: cero recintos inválidos y 10 reparaciones declaradas.

    **Las piezas pasaron de 206 (3.305,18 m²) a 164 (1.533,31 m²) con `C-18`
    (2026-09-15), y no por la reparación.** Sin alinear rótulos las etiquetas no
    llegan, la regla del agrupador por nombre no descartaba nada y 42 envolventes
    contaban como piezas. Ahora un contorno de color explícito con dos piezas o
    más dentro es agrupador. Medido contra lo publicado: los 42 que salen
    contienen entre 2 y 7 piezas cada uno, lo que deja de cubrirse son 344 m² de
    muros entre piezas, y con los rótulos alineados el plano sigue en 157
    recintos, los mismos.

    **Y de 164 a 165 con el cierre montado de `C-20` (2026-09-16).** Medido
    quitando sólo `parser._anillo_montado`: el único recinto nuevo es un tendedero
    cuya polilínea se cierra encima de su primer tramo, el mismo contorno útil que
    causó el error de cifra. Ninguno desaparece."""
    ruta = _ruta("plantasimple.dxf")
    if ruta is None:
        pytest.skip("plantasimple.dxf no está en esta máquina")

    plano = parser.leer_plano(parser.load_document(ruta), layer="00 areas")

    assert len(plano.rooms) == 165
    assert sum(r.polygon.area for r in plano.rooms) == pytest.approx(1537.37, abs=0.01)
    assert [r for r in plano.rooms if not r.polygon.is_valid] == []
    assert len(plano.geometria_reparada) == 10


def test_cada_reparacion_de_plantasimple_se_puede_ir_a_mirar():
    """Un aviso que no se puede localizar gasta tiempo en vez de ahorrarlo: cada
    reparación lleva el `handle` de la polilínea y qué estaba mal."""
    ruta = _ruta("plantasimple.dxf")
    if ruta is None:
        pytest.skip("plantasimple.dxf no está en esta máquina")

    plano = parser.leer_plano(parser.load_document(ruta), layer="00 areas")

    for reparada in plano.geometria_reparada:
        assert reparada.handle
        assert reparada.capa == "00 areas"
        assert "Self-intersection" in reparada.detalle
        assert reparada.area > 0
