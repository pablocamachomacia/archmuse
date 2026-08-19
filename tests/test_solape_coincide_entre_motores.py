# -*- coding: utf-8 -*-
"""Los dos motores que miden un solape tienen que dar la misma cifra.

Ejecutar:  ARCHMUSE_DXF_V2S=<ruta> pytest tests/test_solape_coincide_entre_motores.py

**Por que existe este test, y por que va contra ficheros reales y no contra un
mock.** El repositorio calcula el solape entre recintos en DOS sitios
independientes:

- `analyzer/evaluator.py::evaluate_room_overlap`, con tolerancia
  `ROOM_OVERLAP_TOLERANCE_M2`. Es la que consume la revision de coherencia
  (`analyzer/coherencia.py`), y la que acaba en el informe que lee el arquitecto.
- `analyzer/superficie_util.py::_solapes`, con tolerancia
  `TOLERANCIA_SOLAPE_M2`. Es la que hace que la medicion de superficie util
  DB-SI se NIEGUE a publicar un total cuando la geometria es ambigua.

Son dos implementaciones del mismo hecho geometrico, cada una con su constante.
Mientras coincidan no pasa nada. **El dia que diverjan**, el informe de
coherencia dira que hay un solape de X m² y la medicion se negara --o no-- por
un criterio distinto, y el arquitecto vera dos cifras del mismo plano que no
cuadran. Eso no se manifiesta como una excepcion: se manifiesta como
desconfianza.

Un mock no serviria: lo que se quiere fijar es que **sobre la geometria real de
un cliente**, con sus polilineas mal cerradas y sus rotulos repetidos, las dos
rutas coinciden. Por eso el test se salta con motivo si no hay plano real, en
vez de inventarse uno.

**La cifra: 7,08 m²** en `v2s.dxf` -- dos solapes, `Tendedero`+`Tendedero`
(4,00) y `Terraza`+`Tendedero` (3,08). Si cambia, o ha cambiado el plano o ha
cambiado un criterio de calculo: hay que mirar cual de las dos cosas, no ajustar
el numero.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

DXF_V2S = os.environ.get("ARCHMUSE_DXF_V2S", "")

#: Solape total medido sobre `v2s.dxf` el 2026-08-19. No es una estimacion:
#: sale de ejecutar los dos motores sobre el fichero del cliente.
SOLAPE_TOTAL_V2S_M2 = 7.08
SOLAPES_V2S_M2 = (3.08, 4.00)

#: Tolerancia de la COMPARACION entre motores, no de la deteccion. Dos calculos
#: del mismo poligono con shapely no deberian diferir ni en el cuarto decimal;
#: se admite un centimetro cuadrado por si alguna ruta redondea antes.
TOLERANCIA_ENTRE_MOTORES_M2 = 0.01


def _solapes_via_coherencia(ruta: str):
    """Los que acaban en el informe que lee el arquitecto."""
    import ezdxf

    from analyzer import coherencia, evaluator

    doc = ezdxf.readfile(ruta)
    plano, _avisos = coherencia.leer_plano_capturando_avisos(doc)
    unidades = coherencia._agrupar_en_viviendas(plano)
    return sorted(round(s.overlap_m2, 2) for s in evaluator.evaluate_room_overlap(list(unidades)))


def _solapes_via_superficie_util(ruta: str):
    """Los que hacen que la medicion DB-SI se niegue a dar un total."""
    import ezdxf

    from analyzer import coherencia, superficie_util

    doc = ezdxf.readfile(ruta)
    plano, _avisos = coherencia.leer_plano_capturando_avisos(doc)
    revisados = superficie_util._revisar(plano.rooms)
    return sorted(round(area, 2) for _a, _b, area in superficie_util._solapes(revisados))


@pytest.mark.skipif(not DXF_V2S, reason="define ARCHMUSE_DXF_V2S: este test mide geometría real")
def test_los_dos_motores_miden_el_mismo_solape():
    """**El test de regresion permanente.** Si esto se pone rojo, dos partes del
    producto han dejado de estar de acuerdo sobre el mismo plano."""
    por_coherencia = _solapes_via_coherencia(DXF_V2S)
    por_superficie = _solapes_via_superficie_util(DXF_V2S)

    assert por_coherencia, "la revisión de coherencia no detecta ningún solape en v2s.dxf"
    assert por_superficie, "la medición de superficie útil no detecta ningún solape en v2s.dxf"
    assert len(por_coherencia) == len(por_superficie), (
        "un motor ve %d solape(s) y el otro %d: %s contra %s"
        % (len(por_coherencia), len(por_superficie), por_coherencia, por_superficie))

    for a, b in zip(por_coherencia, por_superficie, strict=True):
        assert abs(a - b) <= TOLERANCIA_ENTRE_MOTORES_M2, (
            "los dos motores miden el mismo solape distinto: %.2f m² contra %.2f m²" % (a, b))


@pytest.mark.skipif(not DXF_V2S, reason="define ARCHMUSE_DXF_V2S: este test mide geometría real")
def test_la_magnitud_del_solape_de_v2s_no_ha_cambiado():
    """Fija la cifra concreta. Es lo que convierte «coinciden» en «coinciden en
    lo correcto»: dos motores pueden estar de acuerdo y estar los dos mal."""
    por_coherencia = _solapes_via_coherencia(DXF_V2S)
    assert tuple(por_coherencia) == SOLAPES_V2S_M2, (
        "el solape de v2s.dxf ha cambiado: %s. O el plano es otro, o ha cambiado un "
        "criterio de cálculo — hay que mirar cuál, no ajustar el número." % (por_coherencia,))
    assert abs(sum(por_coherencia) - SOLAPE_TOTAL_V2S_M2) <= TOLERANCIA_ENTRE_MOTORES_M2


@pytest.mark.skipif(not DXF_V2S, reason="define ARCHMUSE_DXF_V2S: este test mide geometría real")
def test_donde_hay_solape_la_medicion_se_niega_a_dar_un_total():
    """Las dos mitades del criterio tienen que ir juntas: si un motor ve un
    solape, el otro no puede publicar una superficie útil como si nada.

    Es la coherencia que de verdad ve el arquitecto: el informe le dice que dos
    piezas se pisan, y el cuadro le deja esa celda en blanco con su motivo. Si
    un día el cuadro se rellenara igual, el producto estaría contando dos veces
    los mismos metros y diciendo que todo está bien.
    """
    from agente.herramientas.plano import superficie_util as capacidad_superficie

    assert _solapes_via_coherencia(DXF_V2S), "sin solape este test no comprueba nada"
    resultado = capacidad_superficie(ruta=DXF_V2S)
    assert resultado.get("ok") is True
    medidas = [v for v in resultado["viviendas"] if v.get("valor_m2") is not None]
    assert not medidas, (
        "hay solape y aun así se publica una superficie útil: %s" % medidas)
