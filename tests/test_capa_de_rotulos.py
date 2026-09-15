# -*- coding: utf-8 -*-
"""Qué capa puede dar nombre a una estancia: la que más nombra, gana.

PRD: `docs/prd/2026-09-11-que-capa-nombra-las-estancias.md` (aprobado por Pablo,
2026-09-11, opción 1 con condición dura).

**De dónde sale.** `_capas_de_rotulo` admite como capa de rótulos cualquiera que
ponga un texto dentro de un recinto. Eso separa una capa de nombres de una de
cotas, pero no de una de **anotaciones**. Al alinear los rótulos de
`plantasimple.dxf` aparecieron 46 recintos llamados «F», «FR» y «LD» — códigos
de electrodoméstico— y el salón de 21,90 m² entre ellos.

**La condición dura, y el test que la guarda:** si la segunda capa nombra una
proporción comparable a la primera, **no se elige en silencio**
(`test_dos_capas_parejas_no_se_eligen_y_se_declaran`). Se declara el reparto y
se deja todo como estaba, porque elegir sería adivinar y no nombrar nada
rompería planos que hoy funcionan.
"""
from __future__ import annotations

import os

import pytest
from shapely.geometry import Polygon

from analyzer import coherencia, parser

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _recintos(n):
    return [Polygon([(i * 10.0, 0), (i * 10.0 + 6, 0), (i * 10.0 + 6, 6), (i * 10.0, 6)])
            for i in range(n)]


def _en(polygons, capa, cuantos, texto="Dormitorio", desvio=0.0):
    """Un texto de `capa` dentro de cada uno de los `cuantos` primeros."""
    fuera = []
    for p in polygons[:cuantos]:
        c = p.centroid
        fuera.append((texto, c.x + desvio, c.y, capa))
    return fuera


# ---------------------------------------------------------------------------
# N1 · El recuento y la elección
# ---------------------------------------------------------------------------

def test_gana_la_capa_que_nombra_mas_recintos():
    polygons = _recintos(10)
    labels = _en(polygons, "TEXTOS", 10) + _en(polygons, "INSTALACIONES", 3, "F", 1.0)

    reparto = parser.elegir_capa_de_rotulos(
        polygons, labels, {"TEXTOS", "INSTALACIONES"})

    assert reparto.capa == "TEXTOS"
    assert reparto.ambiguo is False
    assert reparto.recuento[0] == ("TEXTOS", 10)


def test_se_cuenta_a_cuantas_estancias_pone_nombre_no_cuantos_textos_tiene():
    """Una capa con seis anotaciones en la misma estancia nombra **una**
    estancia, no seis. Sin esto, una capa de instalaciones densa ganaría por
    volumen de texto sin nombrar nada."""
    polygons = _recintos(4)
    labels = _en(polygons, "TEXTOS", 4)
    for desvio in (0.5, 1.0, 1.5, 2.0, 2.5, -0.5):
        labels += _en(polygons, "INSTALACIONES", 1, "F", desvio)

    reparto = parser.elegir_capa_de_rotulos(
        polygons, labels, {"TEXTOS", "INSTALACIONES"})

    assert reparto.recuento == (("TEXTOS", 4), ("INSTALACIONES", 1))


def test_dos_capas_parejas_no_se_eligen():
    """**La condición dura de Pablo.** 10 contra 9 no es «gana la primera»: son
    dos hipótesis, y elegir entre ellas sería adivinar."""
    polygons = _recintos(10)
    labels = _en(polygons, "TEXTOS", 10) + _en(polygons, "OTRA", 9, "X", 1.0)

    reparto = parser.elegir_capa_de_rotulos(polygons, labels, {"TEXTOS", "OTRA"})

    assert reparto.capa is None
    assert reparto.ambiguo is True
    assert reparto.proporcion == pytest.approx(0.9)


def test_el_umbral_es_mas_del_doble_y_esta_donde_dicen_los_datos():
    """0,5 = «la primera nombra más del doble que la segunda». El único plano
    real con varias capas está en 0,414 y el caso que Pablo puso como no holgado
    —111 contra 95— daría 0,856."""
    assert parser.UMBRAL_CAPA_DE_ROTULOS == 0.5
    assert 46 / 111 < parser.UMBRAL_CAPA_DE_ROTULOS < 95 / 111


def test_sin_recintos_nombrados_no_se_elige_ni_se_declara_ambiguo():
    """Un plano cuyos rótulos están a 50 m no tiene capa de rótulos que elegir,
    y tampoco es ambiguo: no hay nada. Ese plano ya tiene su propio hallazgo."""
    polygons = _recintos(5)
    labels = [("Nota", 500.0, 500.0, "TEXTOS")]

    reparto = parser.elegir_capa_de_rotulos(polygons, labels, {"TEXTOS"})

    assert reparto.capa is None
    assert reparto.ambiguo is False
    assert reparto.recuento == ()


# ---------------------------------------------------------------------------
# N2 · El estrechamiento
# ---------------------------------------------------------------------------

def test_la_capa_de_los_recintos_se_admite_siempre():
    """Hay planos que rotulan sobre la propia geometría (`v1plantas.dxf`).
    Quitarla del conjunto admitido los dejaría mudos."""
    polygons = _recintos(10)
    labels = _en(polygons, "TEXTOS", 10) + _en(polygons, "00 areas", 2, "Baño", 1.0)

    capas, reparto = parser._capas_que_nombran(polygons, labels, "00 areas")

    assert reparto.capa == "TEXTOS"
    assert capas == {"00 areas", "TEXTOS"}


def test_cuando_es_ambiguo_no_se_estrecha_nada():
    """No elegir **no** es dejar de nombrar: se admite lo mismo que se admitía
    antes y se declara el reparto. No nombrar nada rompería planos que hoy
    funcionan, que es peor que el problema."""
    polygons = _recintos(10)
    labels = _en(polygons, "TEXTOS", 10) + _en(polygons, "OTRA", 9, "X", 1.0)

    capas, reparto = parser._capas_que_nombran(polygons, labels, "00 areas")

    assert reparto.ambiguo is True
    assert "TEXTOS" in capas and "OTRA" in capas


# ---------------------------------------------------------------------------
# N3 · El hallazgo del caso ambiguo
# ---------------------------------------------------------------------------

class _PlanoFalso:
    def __init__(self, reparto):
        self.layer = "00 areas"
        self.reparto_de_rotulos = reparto


def test_el_caso_ambiguo_se_declara_con_cifras():
    reparto = parser.RepartoDeRotulos(
        recuento=(("00 TEXTO", 111), ("00-INST", 95)), ambiguo=True)

    hallazgos = coherencia._rotulos_de_varias_capas(_PlanoFalso(reparto))

    assert len(hallazgos) == 1
    assert hallazgos[0].tipo == coherencia.ROTULOS_DE_VARIAS_CAPAS
    assert "111" in hallazgos[0].descripcion and "95" in hallazgos[0].descripcion
    assert hallazgos[0].detalle["elegida"] is None


def test_el_caso_claro_no_declara_nada():
    reparto = parser.RepartoDeRotulos(capa="00 TEXTO", recuento=(("00 TEXTO", 111),))
    assert coherencia._rotulos_de_varias_capas(_PlanoFalso(reparto)) == []


# ---------------------------------------------------------------------------
# N4 · Regresión sobre los planos reales
# ---------------------------------------------------------------------------

def _ruta(nombre):
    ruta = os.path.join(os.path.dirname(RAIZ), "_material", nombre)
    return ruta if os.path.isfile(ruta) else None


#: Rótulo a rótulo, no por recuento: el criterio 1 del PRD dice «exactamente los
#: mismos rótulos que hoy», y dos errores que se compensan dan el mismo total.
@pytest.mark.parametrize("nombre,piezas,capa", [
    ("ejemplo.dxf", 40, "00 TEXTO"),
    ("v1plantas.dxf", 8, "00 areas"),
    ("v2s.dxf", 8, "00 areas"),
    ("v3s.dxf", 8, "00 areas"),
    ("V5.dxf", 22, "00 TEXTO"),
])
def test_los_planos_de_referencia_tienen_una_sola_capa_que_nombra(nombre, piezas, capa):
    ruta = _ruta(nombre)
    if ruta is None:
        pytest.skip("%s no está en esta máquina" % nombre)

    plano = parser.leer_plano(parser.load_document(ruta), layer="00 areas")

    assert len(plano.rooms) == piezas
    # Sin nombre sólo por `C-18` (firmado el 2026-09-15): dos nombres distintos
    # dentro no se eligen. Medido ese día en `ejemplo.dxf`: un recinto de 11,55 m²
    # con «Terraza» y «Tendedero» dentro, que hasta entonces se llamaba como el
    # primero que llegara.
    mudos = [r for r in plano.rooms if not r.label]
    assert all(len(r.rotulos_en_conflicto) >= 2 for r in mudos), (
        "esta regla no puede dejar mudo un plano: %s" % mudos)
    assert plano.reparto_de_rotulos.capa == capa
    assert plano.reparto_de_rotulos.ambiguo is False
    assert plano.reparto_de_rotulos.proporcion == 0.0


def test_plantasimple_alineado_ya_no_llama_F_a_su_salon():
    """El caso por el que existe este PRD. Antes: 46 recintos llamados «F»,
    «FR» o «LD», y el salón de 21,90 m² entre ellos."""
    ruta = _ruta("plantasimple.dxf")
    if ruta is None:
        pytest.skip("plantasimple.dxf no está en esta máquina")

    plano = parser.leer_plano(parser.load_document(ruta), layer="00 areas",
                              alinear_rotulos=True)

    nombres = {r.label for r in plano.rooms if r.label}
    assert not (nombres & {"F", "FR", "LV", "V", "LD", "H"})
    assert plano.reparto_de_rotulos.capa == "00 TEXTO"
    assert "Salón/cocina" in nombres
