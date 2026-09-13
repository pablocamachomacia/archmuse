# -*- coding: utf-8 -*-
"""Un plano cuyos rótulos están movidos en bloque respecto de sus recintos.

**De dónde sale esto.** `plantasimple.dxf` mide 206 recintos y no pone nombre a
ninguno. La causa, medida el 2026-09-11: los textos del plano están **50,00
unidades de dibujo por debajo** de las polilíneas de «00 areas», con dx = 0
exacto — al aplicar (0, +50) encajan 152 de 152 de las cerradas, y el barrido de
dy da una meseta limpia de 49,50 a 50,25, que es la forma de un `DESPLAZA`
deliberado y no de una deriva.

**No es la convención del estudio.** Los otros cuatro planos del mismo
arquitecto (`v1plantas`, `v2s`, `v3s`, `V5`) y `ejemplo.dxf` rotulan al 100% sin
desplazar nada. Por eso esto **detecta y avisa, y no corrige**: un caso raro se
declara, no se normaliza en silencio.

La promesa que más importa de este fichero es la del último test: el detector
**no mueve nada**. Si algún día alguien aplica el desplazamiento «porque es
obvio», ese test se pone rojo, que es justo lo que tiene que pasar.
"""
from __future__ import annotations

import os

import pytest
from shapely.geometry import Polygon

from analyzer import coherencia
from analyzer import parser

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _rejilla(n=10, lado=4.0, paso=6.0):
    """`n` recintos cuadrados en fila, del tamaño de una estancia."""
    return [
        Polygon([(i * paso, 0), (i * paso + lado, 0),
                 (i * paso + lado, lado), (i * paso, lado)])
        for i in range(n)
    ]


def _rotulos_centrados(polygons, dx=0.0, dy=0.0):
    return [("Dormitorio %d" % i, p.centroid.x + dx, p.centroid.y + dy)
            for i, p in enumerate(polygons)]


# ---------------------------------------------------------------------------
# El caso normal: no se busca nada y no se dice nada
# ---------------------------------------------------------------------------

def test_un_plano_rotulado_no_produce_desplazamiento():
    polygons = _rejilla()
    labels = _rotulos_centrados(polygons)
    assert parser.detectar_desplazamiento_de_rotulos(polygons, labels) is None


def test_sin_recintos_o_sin_rotulos_no_se_inventa_nada():
    assert parser.detectar_desplazamiento_de_rotulos([], [("Salón", 0, 0)]) is None
    assert parser.detectar_desplazamiento_de_rotulos(_rejilla(), []) is None


def test_unos_pocos_recintos_sin_rotulo_no_son_un_desplazamiento():
    """Dos huecos sueltos en un plano rotulado son dos huecos sueltos. Tienen
    su propio hallazgo (`RECINTO_SIN_ETIQUETA`) y no se explican moviendo nada:
    por debajo del umbral, esto ni se molesta en mirar."""
    polygons = _rejilla(n=10)
    labels = _rotulos_centrados(polygons[:8])
    assert parser.detectar_desplazamiento_de_rotulos(polygons, labels) is None


# ---------------------------------------------------------------------------
# El caso de plantasimple, reproducido en pequeño
# ---------------------------------------------------------------------------

def test_se_detecta_una_traslacion_rigida_y_se_dice_cuanto():
    polygons = _rejilla()
    # Los rótulos, 50 unidades por debajo. Es lo que pasa en el plano real.
    labels = _rotulos_centrados(polygons, dy=-50.0)

    desplazamiento = parser.detectar_desplazamiento_de_rotulos(polygons, labels)

    assert desplazamiento is not None
    assert desplazamiento.dx == pytest.approx(0.0, abs=parser.PASO_DEL_VOTO)
    assert desplazamiento.dy == pytest.approx(50.0, abs=parser.PASO_DEL_VOTO)
    assert desplazamiento.sin_rotulo == 10
    assert desplazamiento.explicados == 10


def test_tambien_cuando_el_desplazamiento_es_en_las_dos_direcciones():
    polygons = _rejilla()
    labels = _rotulos_centrados(polygons, dx=12.0, dy=-30.0)

    desplazamiento = parser.detectar_desplazamiento_de_rotulos(polygons, labels)

    assert desplazamiento is not None
    assert desplazamiento.dx == pytest.approx(-12.0, abs=parser.PASO_DEL_VOTO)
    assert desplazamiento.dy == pytest.approx(30.0, abs=parser.PASO_DEL_VOTO)


def test_sin_rotular_pero_sin_traslacion_que_lo_explique_se_dice_que_no():
    """**El negativo que de verdad importa.** Un plano sin rotular cuyos textos
    están desperdigados no tiene desplazamiento, y la respuesta correcta es
    `None` — no la traslación menos mala. Devolver una cifra aquí sería mandar
    al arquitecto a mover su plano por nada."""
    polygons = _rejilla()
    labels = [("Nota %d" % i, i * 137.0, i * 91.0) for i in range(12)]
    assert parser.detectar_desplazamiento_de_rotulos(polygons, labels) is None


# ---------------------------------------------------------------------------
# Cómo se dice
# ---------------------------------------------------------------------------

def test_la_cifra_se_dice_con_coma_decimal():
    assert "50,00" in parser._distancia_legible(0.0, 50.0)
    assert "50.00" not in parser._distancia_legible(0.0, 50.0)


def test_un_residuo_de_una_casilla_no_se_nombra_como_direccion():
    """La votación tiene una rejilla de 0,25: un `dx` de exactamente una casilla
    no es una medida, es la rejilla. En el plano real la ganadora sale
    `(+0,25, +50,00)` y decir «y 0,25 a la izquierda» presumiría de una
    precisión que este método no tiene. Las dos cifras exactas siguen viajando
    en `dx`/`dy` para quien quiera comprobarlas."""
    frase = parser._distancia_legible(parser.PASO_DEL_VOTO, 50.0)
    assert "abajo" in frase
    assert "izquierda" not in frase


def test_se_dice_hacia_donde_estan_los_rotulos():
    assert "abajo" in parser._distancia_legible(0.0, 50.0)
    assert "arriba" in parser._distancia_legible(0.0, -50.0)


# ---------------------------------------------------------------------------
# Un hallazgo, no doscientos
# ---------------------------------------------------------------------------

class _PlanoFalso:
    def __init__(self, desplazamiento):
        self.layer = "00 areas"
        self.rotulos_desplazados = desplazamiento


def test_se_emite_un_solo_hallazgo_con_la_cifra_dentro():
    desplazamiento = parser.DesplazamientoDeRotulos(
        dx=0.0, dy=50.0, explicados=199, sin_rotulo=200, mirados=200)

    hallazgos = coherencia._rotulos_desplazados(_PlanoFalso(desplazamiento))

    assert len(hallazgos) == 1
    hallazgo = hallazgos[0]
    assert hallazgo.tipo == coherencia.ROTULOS_DESPLAZADOS
    assert "50,00" in hallazgo.descripcion
    assert hallazgo.detalle["dy"] == 50.0
    assert hallazgo.detalle["recintos_sin_rotulo"] == 200


def test_un_plano_sin_desplazamiento_no_emite_nada():
    assert coherencia._rotulos_desplazados(_PlanoFalso(None)) == []


def test_el_hallazgo_declara_que_NO_se_ha_aplicado():
    """`aplicado: False` viaja en el detalle a propósito. Quien lea esto por
    JSON tiene que poder saber, sin leer el código, que ArchMuse ha medido el
    desplazamiento y no lo ha tocado."""
    desplazamiento = parser.DesplazamientoDeRotulos(
        dx=0.0, dy=50.0, explicados=199, sin_rotulo=200, mirados=200)
    hallazgo = coherencia._rotulos_desplazados(_PlanoFalso(desplazamiento))[0]
    assert hallazgo.detalle["aplicado"] is False
    assert "NO los ha movido" in hallazgo.descripcion


# ---------------------------------------------------------------------------
# La promesa: detectar no es corregir
# ---------------------------------------------------------------------------

def test_el_detector_no_toca_los_poligonos():
    """**Si este test se pone rojo, alguien ha decidido mover el plano del
    arquitecto.** Es la línea entre diagnosticar y reescribir el dibujo de otro,
    y no se cruza sin que Pablo lo firme."""
    polygons = _rejilla()
    antes = [p.wkt for p in polygons]
    labels = _rotulos_centrados(polygons, dy=-50.0)

    parser.detectar_desplazamiento_de_rotulos(polygons, labels)

    assert [p.wkt for p in polygons] == antes


# ---------------------------------------------------------------------------
# Regresión sobre los planos reales, si están en esta máquina
# ---------------------------------------------------------------------------

def _ruta(nombre):
    candidatas = [
        os.path.join(os.path.dirname(RAIZ), "_material", nombre),
        os.path.join(os.path.dirname(RAIZ), nombre),
    ]
    return next((c for c in candidatas if os.path.isfile(c)), None)


def test_plantasimple_declara_los_50_00_y_no_los_aplica():
    ruta = _ruta("plantasimple.dxf")
    if ruta is None:
        pytest.skip("plantasimple.dxf no está en esta máquina (plano real de "
                    "cliente, no versionado)")

    plano = parser.leer_plano(parser.load_document(ruta), layer="00 areas")

    assert plano.rotulos_desplazados is not None
    assert plano.rotulos_desplazados.dy == pytest.approx(50.0, abs=0.5)
    assert plano.rotulos_desplazados.dx == pytest.approx(0.0, abs=0.5)
    # Y los recintos siguen donde estaban: medidos donde el arquitecto los
    # dibujó, no donde encajarían.
    assert all(r.polygon.bounds[1] < -280 for r in plano.rooms)


@pytest.mark.parametrize("nombre", ["v1plantas.dxf", "v2s.dxf", "v3s.dxf", "V5.dxf"])
def test_los_demas_planos_del_estudio_no_tienen_desplazamiento(nombre):
    """Lo que convierte los 50,00 en un caso raro y no en una convención. Si
    alguno de estos empieza a declarar desplazamiento, la conclusión de la que
    cuelga todo este módulo ha dejado de ser cierta."""
    ruta = _ruta(nombre)
    if ruta is None:
        pytest.skip("%s no está en esta máquina" % nombre)

    plano = parser.leer_plano(parser.load_document(ruta), layer="00 areas")

    assert plano.rotulos_desplazados is None
