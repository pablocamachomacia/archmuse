# -*- coding: utf-8 -*-
"""Un total sólo puede sumar magnitudes que se acumulen entre sí.

**El bug que estos tests congelan.** `agente/skills/superficies.py::_suma_cuadra`
cruzaba la suma de las celdas del cuadro contra la superficie útil medida sobre
la geometría, y decidía qué celdas sumar por el nombre del campo: «si contiene
la palabra *total*, no lo sumes». Eso deja fuera los totales —correcto— y deja
dentro las dos celdas de **superficie construida** y el **número de unidades**:

- La superficie construida mide la misma vivienda con otro criterio (incluye el
  espesor de los muros; la útil va a cara interior). Sumarla a la útil no da una
  superficie mayor, da una cifra que no significa nada.
- `NUMERO UDS` no es una superficie: es cuántas viviendas iguales tiene el
  edificio. El cuadro de `ejemplo.dxf` lo trae escrito («8»), así que la
  comprobación sumaba ocho metros cuadrados que no existen en ningún sitio.

Los dos casos son los del flujo normal, no rarezas: las `Solicitud` numéricas de
`cuadro_superficies.py` le piden al arquitecto exactamente esos tres datos.

Estos tests están escritos contra el catálogo cerrado de campos
(`CAMPOS_SUMANDOS_UTIL` y compañía), no contra la implementación de la suma: si
mañana el cuadro gana una fila nueva, el primer test obliga a decir qué magnitud
es antes de que pueda colarse en ningún total.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agente.skills import superficies                       # noqa: E402
from agente.skill import ResultadoDeSkill                    # noqa: E402
from agente.verificacion import NoSeHaPodidoComprobar        # noqa: E402
from analyzer import cuadro_superficies as cs                # noqa: E402


# --- 1. El catálogo de magnitudes es exhaustivo y sin solapes --------------

def test_cada_campo_del_cuadro_esta_clasificado_en_una_sola_magnitud():
    grupos = (cs.CAMPOS_SUMANDOS_UTIL, cs.CAMPOS_TOTAL_UTIL,
              cs.CAMPOS_CONSTRUIDA, cs.CAMPOS_SIN_SUPERFICIE)
    todos = [campo for grupo in grupos for campo in grupo]
    assert len(todos) == len(set(todos)), "un campo está en dos magnitudes a la vez"
    assert set(todos) == set(cs.CAMPOS_DEL_CUADRO)


def test_el_catalogo_cubre_todos_los_campos_que_el_calculo_produce():
    """Si `calcular_relleno_cuadro` emite un campo que el catálogo no conoce,
    ese campo no tiene magnitud declarada y podría acabar en un total."""
    cuadro = cs.CuadroSuperficies(celdas=())
    resultados = cs.calcular_relleno_cuadro(_UnitFalsa("VT1/3"), cuadro, [])
    emitidos = {c.campo for c in resultados}
    assert emitidos == set(cs.CAMPOS_DEL_CUADRO), (
        "campos sin clasificar: %s" % (emitidos - set(cs.CAMPOS_DEL_CUADRO)))


def test_la_construida_y_el_numero_de_unidades_no_son_sumandos_de_la_util():
    for campo in cs.CAMPOS_CONSTRUIDA + cs.CAMPOS_SIN_SUPERFICIE:
        assert campo not in cs.CAMPOS_SUMANDOS_UTIL


# --- 2. La suma que se cruza contra la geometría --------------------------
#
# **Desde la plantilla fija (2026-09-13) la Skill suma las FILAS del cuerpo de
# la tabla**, y los totales, la construida, la vivienda tipo y el número de
# unidades no están entre ellas por construcción. Los cuatro tests que vigilaban
# que no se colaran por el nombre del campo se sustituyen por uno que lo mira
# sobre la tabla que produce la capacidad de verdad.

def _resultado(medida, filas):
    from agente.afirmacion import calculo

    return ResultadoDeSkill(afirmaciones=(
        calculo("plano.superficie_util_total_m2", medida, fuente="t", unidad="m2"),
        calculo("cuadro.celdas", filas, fuente="t"),
    ))


def _fila(rotulo, valor, ambito="interior", tiene_fila=True):
    return {"rotulo": rotulo, "valor": valor, "ambito": ambito, "tiene_fila": tiene_fila}


def _filas_completas(*extra):
    """Dos piezas con cifra: 32,00 m²."""
    return [_fila("Salón/cocina", "20,00 m²"), _fila("Dormitorio 1", "12,00 m²")] + list(extra)


def test_el_cierre_de_la_tabla_no_esta_entre_lo_que_se_suma(tmp_path):
    """Sobre la tabla real del piso sintético: 20 + 9 + 12 + 4 = 45 m², y ni un
    total, ni la construida, ni el número de unidades entre las filas."""
    from agente.herramientas import plano
    from analyzer import plantilla_cuadro as pc
    from tests.test_agente_goldens import construir_dxf

    borrador = plano.cuadro_de_superficies(construir_dxf(tmp_path))
    assert borrador["ok"], borrador
    rotulos = {f["rotulo"] for f in borrador["filas"]}
    cierre = {pc.TOTAL_INTERIOR, pc.TOTAL_EXTERIOR, pc.TOTAL_UTIL, pc.CONSTRUIDA,
              pc.VIVIENDA_TIPO, pc.NUMERO_UDS}
    assert not rotulos & cierre
    assert superficies._suma_cuadra(_resultado(45.0, borrador["filas"])) is True


def test_las_exteriores_si_se_suman():
    """La útil de `plano.superficie_util` incluye terraza y tendedero."""
    filas = _filas_completas(_fila("Terraza", "4,50 m²", ambito="exterior"))
    assert superficies._suma_cuadra(_resultado(36.5, filas)) is True


def test_una_pieza_sin_cifra_no_produce_un_descuadre_falso():
    """Si falta una terraza, la suma es menor que la medida SIEMPRE. Avisar de
    eso acusaría al plano de un descuadre que lo ha causado ArchMuse."""
    filas = _filas_completas(_fila("Terraza", "", ambito="exterior"))
    veredicto = superficies._suma_cuadra(_resultado(35.0, filas))
    assert isinstance(veredicto, NoSeHaPodidoComprobar)
    assert "Terraza" in str(veredicto.motivo)


def test_una_pieza_medida_sin_fila_tampoco():
    """Una familia sin contestar deja la pieza fuera de la tabla (`C-6`); la
    suma no puede fingir que no existe."""
    filas = _filas_completas(_fila("Trastero", "", ambito=None, tiene_fila=False))
    veredicto = superficies._suma_cuadra(_resultado(34.7, filas))
    assert isinstance(veredicto, NoSeHaPodidoComprobar)
    assert "Trastero" in str(veredicto.motivo)


def test_una_cifra_en_formato_ajeno_se_declara_en_vez_de_saltarse():
    """«21.90m2» no es el formato de ArchMuse. Un parseo laxo lo descartaba en
    silencio, dejando la suma corta sin decirlo."""
    filas = [_fila("Salón/cocina", "21.90m2"), _fila("Dormitorio 1", "12,00 m²")]
    veredicto = superficies._suma_cuadra(_resultado(33.9, filas))
    assert isinstance(veredicto, NoSeHaPodidoComprobar)
    assert "Salón/cocina" in str(veredicto.motivo)


def test_un_descuadre_de_verdad_se_sigue_avisando():
    """El arreglo no puede haber apagado la comprobación."""
    aviso = superficies._suma_cuadra(_resultado(100.0, _filas_completas()))
    assert isinstance(aviso, str)
    assert "32.00" in aviso and "100.00" in aviso


# --- 3. El total del plano no se publica dejándose una vivienda fuera ------

def test_el_total_del_plano_no_suma_solo_las_viviendas_medibles():
    """Sobre `ejemplo.dxf` esto publicaba 295,10 m² con VT6/2 fuera y callado."""
    ctx = _ContextoFalso({
        "plano.leer_dxf": {"ok": True, "escala": {"unidad": "metros"}},
        "plano.superficie_util": {"ok": True, "viviendas": [
            {"vivienda": "VT1/3", "valor_m2": 66.32},
            {"vivienda": "VT6/2", "valor_m2": None},
        ]},
        "plano.cuadro_de_superficies": {"ok": False, "error": "varias_viviendas",
                                        "detalle": "", "pregunta": ""},
    })
    resultado = superficies._ejecutar(ctx)
    hecho = next(a for a in resultado.afirmaciones
                 if a.nombre == "plano.superficie_util_total_m2")
    assert hecho.valor is None
    assert hecho.motivo is not None
    assert "VT6/2" in hecho.motivo.detalle


def test_el_total_del_plano_si_se_publica_cuando_todas_se_han_medido():
    ctx = _ContextoFalso({
        "plano.leer_dxf": {"ok": True, "escala": {"unidad": "metros"}},
        "plano.superficie_util": {"ok": True, "viviendas": [
            {"vivienda": "VT1/3", "valor_m2": 66.32},
            {"vivienda": "VT2/2", "valor_m2": 58.44},
        ]},
        "plano.cuadro_de_superficies": {"ok": False, "error": "varias_viviendas",
                                        "detalle": "", "pregunta": ""},
    })
    resultado = superficies._ejecutar(ctx)
    hecho = next(a for a in resultado.afirmaciones
                 if a.nombre == "plano.superficie_util_total_m2")
    assert hecho.valor == 124.76


# --- Dobles mínimos --------------------------------------------------------

class _UnitFalsa:
    def __init__(self, name):
        self.name = name
        self.rooms = []


class _ContextoFalso:
    """Lo mínimo que `superficies._ejecutar` usa de un `Contexto` real."""

    firma = "superficies.cuadro_de_vivienda@2.0.0"

    def __init__(self, respuestas):
        self._respuestas = respuestas
        self.invocaciones = []
        self.argumentos = {"ruta_dxf": "x.dxf", "ruta_destino": "y.dxf"}

    def invocar(self, capacidad, **argumentos):
        self.invocaciones.append({"capacidad": capacidad, "argumentos": argumentos})
        return self._respuestas[capacidad]
