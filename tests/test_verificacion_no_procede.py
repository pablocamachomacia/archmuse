# -*- coding: utf-8 -*-
"""El tercer estado de una verificación: la que **no ha podido ejecutarse**.

Ejecutar:  pytest tests/test_verificacion_no_procede.py

Esto sale del primer plano real (`v2s.dxf`, 2026-08-19). Su geometría tiene
recintos solapados, así que `plano.superficie_util` se negó —bien— a publicar
un total, y la comprobación «la suma del cuadro cuadra con la superficie
medida» se quedó sin nada contra qué cruzar. El acta la imprimía como:

    [FALLA] la_suma_cuadra_con_la_superficie_medida

Un arquitecto lee eso como «tu cuadro no cuadra». Es una acusación sobre su
trabajo por algo que nadie ha llegado a mirar, y es peor que callarse: gasta la
credibilidad que hace falta el día que la comprobación falle de verdad
(`DESTROY_ARCHMUSE.md` §5.1).

Lo que se fija aquí es la distinción, en las dos direcciones:

1. No comprobar **no es** comprobar: sigue sin contar como superada, y una
   bloqueante en este estado deja el resultado sin verificar.
2. No comprobar **no es** fallar: no entra en los avisos, y el acta lo dice con
   otras palabras y en la sección que le corresponde.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agente.verificacion import (  # noqa: E402
    NoSeHaPodidoComprobar, Verificacion, dictaminar,
)


def _verificacion(salida, bloqueante=True, nombre="la_prueba"):
    return Verificacion(nombre=nombre, descripcion="Una comprobación.",
                        funcion=lambda _r: salida, bloqueante=bloqueante)


# --- 1. No comprobar no es comprobar --------------------------------------

def test_no_haber_podido_comprobar_no_cuenta_como_superada():
    r = _verificacion(NoSeHaPodidoComprobar("falta el dato de entrada")).ejecutar(None)
    assert r.ok is False
    assert r.no_procede is True


def test_una_bloqueante_que_no_pudo_correr_deja_el_resultado_sin_verificar():
    """La tentación sería tratarla como aprobada para que el acta salga limpia.
    Sería exactamente el teatro que este módulo existe para evitar."""
    d = dictaminar([_verificacion(NoSeHaPodidoComprobar("no hay contra qué cruzar"))], None)
    assert d.verificado is False


def test_el_motivo_por_el_que_no_se_pudo_llega_intacto():
    d = dictaminar([_verificacion(NoSeHaPodidoComprobar("la geometría tiene solapes"))], None)
    assert "la geometría tiene solapes" in d.no_comprobadas[0]
    assert "la_prueba" in d.no_comprobadas[0]


# --- 2. No comprobar no es fallar ------------------------------------------

def test_no_entra_en_los_avisos():
    """`avisos` es lo que obliga al arquitecto a mirar su plano. Meter ahí «me
    falta un dato» diluye lo que sí lo obliga."""
    d = dictaminar([_verificacion(NoSeHaPodidoComprobar("falta un dato"))], None)
    assert d.avisos == ()
    assert len(d.no_comprobadas) == 1


def test_un_fallo_de_verdad_sigue_siendo_un_fallo():
    d = dictaminar([_verificacion("la suma difiere un 30 %")], None)
    assert d.avisos == ("la suma difiere un 30 %",)
    assert d.no_comprobadas == ()
    assert d.verificado is False


def test_los_dos_estados_conviven_sin_mezclarse():
    d = dictaminar([
        _verificacion("no cuadra", nombre="la_que_falla"),
        _verificacion(NoSeHaPodidoComprobar("falta el dato"), nombre="la_que_no_corrio"),
    ], None)
    assert d.avisos == ("no cuadra",)
    assert len(d.no_comprobadas) == 1 and "la_que_no_corrio" in d.no_comprobadas[0]


def test_una_no_bloqueante_que_no_pudo_correr_no_impide_entregar():
    """El caso real: la comprobación de la suma es informativa por decisión de
    Pablo, así que el trabajo se entrega igual — diciendo qué no se miró."""
    d = dictaminar([
        _verificacion(True, nombre="la_que_pasa"),
        _verificacion(NoSeHaPodidoComprobar("falta la medida"), bloqueante=False,
                      nombre="la_suma"),
    ], None)
    assert d.verificado is True
    assert d.avisos == ()
    assert len(d.no_comprobadas) == 1


# --- 3. Viaja serializado, porque el acta se relee sin las funciones -------

def test_el_estado_sobrevive_a_la_serializacion():
    d = dictaminar([_verificacion(NoSeHaPodidoComprobar("falta un dato"))], None)
    comprobacion = d.a_dict()["comprobaciones"][0]
    assert comprobacion["no_procede"] is True
    assert comprobacion["ok"] is False
    assert d.a_dict()["no_comprobadas"]


def test_una_comprobacion_normal_no_se_marca_por_accidente():
    for salida in (True, False, None, "un motivo"):
        r = _verificacion(salida).ejecutar(None)
        assert r.no_procede is False, salida


def test_una_verificacion_que_revienta_es_un_fallo_no_un_no_procede():
    """Que la comprobación tenga un bug NO es «no se ha podido comprobar por
    falta de datos»: es un defecto de ArchMuse, y disfrazarlo de dato ausente lo
    escondería justo donde nadie lo mira."""
    def _revienta(_r):
        raise RuntimeError("bug en la comprobación")
    v = Verificacion(nombre="rota", descripcion="", funcion=_revienta)
    r = v.ejecutar(None)
    assert r.ok is False and r.no_procede is False
    assert "RuntimeError" in r.detalle
