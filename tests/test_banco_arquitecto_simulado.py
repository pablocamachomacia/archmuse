# -*- coding: utf-8 -*-
"""El arquitecto simulado del banco (`benchmark/ejecutar.py`, modo preguntar).

Contesta con su propio cuadro y, cuando su cuadro no basta, no contesta. Lo que se
vigila aquí es que **nunca contesta por adivinar**: una pieza de una familia en la que su
cuadro tiene otra cifra libre queda sin respuesta, no con un «No».

Plano sintético de `tests/test_modo_preguntar.py`.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass
from typing import Optional

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import plantilla_cuadro as pc  # noqa: E402
from analyzer import respuestas_del_arquitecto as rda  # noqa: E402
from tests import test_modo_preguntar as sintetico  # noqa: E402


def _cargar():
    ruta = os.path.join(RAIZ, "benchmark", "ejecutar.py")
    spec = importlib.util.spec_from_file_location("benchmark_ejecutar_simulado", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


banco = _cargar()


@dataclass
class Celda:
    campo: str
    texto_actual: Optional[str]


def _cuadro(**cifras):
    return [Celda(campo, texto) for campo, texto in cifras.items()]


def _pregunta(doc, plano):
    p = pc.construir(doc, plano, "VT1/1", preguntar=True)
    (pregunta,) = p.preguntas_al_arquitecto
    return p, pregunta


def test_si_cuando_su_cuadro_tiene_esa_cifra_libre():
    doc, plano = sintetico._plano()
    p, pregunta = _pregunta(doc, plano)
    arquitecto = banco.ArquitectoSimulado(doc, plano, _cuadro(dormitorio_1="16,00 m²"))
    assert arquitecto.contestar(pregunta, p) == {"id": pregunta.id, "valor": "Si"}


def test_no_cuando_su_cuadro_no_tiene_ninguna_cifra_libre_de_esa_familia():
    doc, plano = sintetico._plano()
    p, pregunta = _pregunta(doc, plano)
    arquitecto = banco.ArquitectoSimulado(doc, plano, _cuadro(dormitorio_1=None, bano="4,00"))
    assert arquitecto.contestar(pregunta, p) == {"id": pregunta.id, "valor": "No"}


def test_con_otra_cifra_de_esa_familia_no_contesta():
    doc, plano = sintetico._plano()
    p, pregunta = _pregunta(doc, plano)
    arquitecto = banco.ArquitectoSimulado(doc, plano, _cuadro(dormitorio_1="15,00 m²"))
    assert arquitecto.contestar(pregunta, p) is None


def test_la_construida_es_la_unica_polilinea_con_su_cifra():
    doc, plano = sintetico._plano()
    h = sintetico._handle(doc, x0=10, y0=0)
    p = pc.construir(doc, plano, "VT1/1", preguntar=True, respuestas=rda.Respuestas(
        (sintetico._si(h),), preguntas_hechas=1,
        respondidas=frozenset([rda.id_pertenencia(h, sintetico._vivienda())])))
    (pregunta,) = p.preguntas_al_arquitecto
    arquitecto = banco.ArquitectoSimulado(doc, plano, _cuadro(superficie_construida_cerrada="225,20"))
    assert arquitecto.contestar(pregunta, p) == {
        "id": pregunta.id, "valor": sintetico._handle(doc, capa="00 CONSTRUIDA")}
    sin_cifra = banco.ArquitectoSimulado(doc, plano, _cuadro(superficie_construida_cerrada="99,99"))
    assert sin_cifra.contestar(pregunta, p) is None


def test_el_turno_completo_deja_la_tabla_completa_con_dos_preguntas():
    doc, plano = sintetico._plano()
    celdas = _cuadro(salon_cocina="30,00", bano="4,00", dormitorio_1="16,00", terraza_1="18,00",
                     total_util_interior="50,00", total_util_exterior="18,00",
                     superficie_construida_cerrada="225,20")
    from analyzer import medicion

    plantilla, hechas = banco.preguntar_y_responder(doc, plano, "VT1/1",
                                                    medicion.medir_planta(plano), None, celdas)
    assert [t for t, _v in hechas] == [rda.PERTENENCIA, rda.CONSTRUIDA]
    assert all(v for _t, v in hechas)
    assert plantilla.cierre[2][1] == "225,20 m²"
    assert plantilla.cierre[0][1] == "50,00 m²"
