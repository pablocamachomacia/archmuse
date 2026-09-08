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

def _resultado(medida, celdas):
    from agente.afirmacion import calculo

    return ResultadoDeSkill(afirmaciones=(
        calculo("plano.superficie_util_total_m2", medida, fuente="t", unidad="m2"),
        calculo("cuadro.celdas", celdas, fuente="t"),
    ))


def _cuadro_util_completo(**cambios):
    """Un cuadro con TODOS los sumandos de la útil resueltos: 32,00 m²."""
    celdas = [{"campo": c, "texto": "0,00 m²", "estado": "CERO_REAL"}
              for c in cs.CAMPOS_SUMANDOS_UTIL]
    por_campo = {c["campo"]: c for c in celdas}
    por_campo["salon_cocina"].update(texto="20,00 m²", estado="CALCULADO")
    por_campo["dormitorio_1"].update(texto="12,00 m²", estado="CALCULADO")
    for campo, celda in cambios.items():
        por_campo[campo] = dict(celda, campo=campo)
    return list(por_campo.values())


def test_la_superficie_construida_declarada_no_entra_en_la_suma_de_la_util():
    """El caso que rompía: el arquitecto declara la construida —que es lo que
    la `Solicitud` numérica le pide— y la comprobación se la sumaba a la útil."""
    celdas = _cuadro_util_completo() + [
        {"campo": "superficie_construida_cerrada", "texto": "95,20 m²", "estado": "CALCULADO"},
        {"campo": "superficie_construida_exterior", "texto": "12,00 m²", "estado": "CALCULADO"},
    ]
    assert superficies._suma_cuadra(_resultado(32.0, celdas)) is True


def test_el_numero_de_unidades_no_se_suma_como_metros_cuadrados():
    """`ejemplo.dxf` trae «NUMERO UDS: 8» escrito en el cuadro."""
    celdas = _cuadro_util_completo() + [
        {"campo": "numero_unidades", "texto": "8", "estado": "CALCULADO"},
    ]
    assert superficies._suma_cuadra(_resultado(32.0, celdas)) is True


def test_la_vivienda_tipo_no_se_suma():
    celdas = _cuadro_util_completo() + [
        {"campo": "vivienda_tipo", "texto": "VT1 /3", "estado": "CALCULADO"},
    ]
    assert superficies._suma_cuadra(_resultado(32.0, celdas)) is True


def test_los_totales_del_propio_cuadro_no_se_suman_con_sus_partes():
    celdas = _cuadro_util_completo() + [
        {"campo": "total_util_interior", "texto": "32,00 m²", "estado": "CALCULADO"},
        {"campo": "total_util", "texto": "32,00 m²", "estado": "CALCULADO"},
    ]
    assert superficies._suma_cuadra(_resultado(32.0, celdas)) is True


def test_un_sumando_sin_resolver_no_produce_un_descuadre_falso():
    """Si falta una terraza, la suma es menor que la medida SIEMPRE. Avisar de
    eso acusaría al plano de un descuadre que lo ha causado ArchMuse."""
    celdas = _cuadro_util_completo(
        terraza_1={"texto": "BLOQUEADO", "estado": "BLOQUEADO"})
    veredicto = superficies._suma_cuadra(_resultado(35.0, celdas))
    assert isinstance(veredicto, NoSeHaPodidoComprobar)
    assert "terraza_1" in str(veredicto.motivo)


def test_una_celda_en_formato_ajeno_se_declara_en_vez_de_saltarse():
    """`ejemplo.dxf` escribe «21.90m2». El parseo viejo no lo entendía y lo
    descartaba en silencio, dejando la suma corta sin decirlo."""
    celdas = _cuadro_util_completo(
        salon_cocina={"texto": "21.90m2", "estado": "CALCULADO"})
    veredicto = superficies._suma_cuadra(_resultado(33.9, celdas))
    assert isinstance(veredicto, NoSeHaPodidoComprobar)
    assert "salon_cocina" in str(veredicto.motivo)


def test_un_descuadre_de_verdad_se_sigue_avisando():
    """El arreglo no puede haber apagado la comprobación."""
    aviso = superficies._suma_cuadra(_resultado(100.0, _cuadro_util_completo()))
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

    firma = "superficies.cuadro_de_vivienda@1.0.0"

    def __init__(self, respuestas):
        self._respuestas = respuestas
        self.invocaciones = []
        self.argumentos = {"ruta_dxf": "x.dxf", "ruta_destino": "y.dxf"}

    def invocar(self, capacidad, **argumentos):
        self.invocaciones.append({"capacidad": capacidad, "argumentos": argumentos})
        return self._respuestas[capacidad]
