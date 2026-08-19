# -*- coding: utf-8 -*-
"""Las cuatro alternativas derivadas de parametros comprobables (`CP-5`).

Ejecutar:  pytest tests/test_alternativas.py

`ARCHMUSE_SPEC.md` §8, redaccion del 2026-08-19: la generacion de alternativas
esta permitida **cuando la geometria se deriva de parametros comprobables**, y
cada alternativa lleva la procedencia de los parametros que la producen. Lo que
sigue fuera es la distribucion interior libre.

Este fichero fija las dos mitades de esa frase:

1. **Se deriva de lo comprobable.** La envolvente sale de multiplicar y comparar
   lo que el arquitecto declaro. Si falta un parametro, **no hay alternativas**:
   repartir un techo que no se ha podido calcular seria inventar la cifra de la
   que cuelga todo lo demas.
2. **Nada sin procedencia.** Es el §13 de la especificacion --el test que nunca
   puede fallar-- aplicado aqui: ninguna cifra de una alternativa existe sin la
   cadena que la produjo.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from analyzer.alternativas import (  # noqa: E402
    ETIQUETAS, OBJETIVOS, REPARTOS, derivar_alternativas, envolvente_edificable,
)

COMPLETOS = {
    "solar": {"superficie_m2": 600.0},
    "normativa": {"ocupacion_maxima_pct": 70.0, "edificabilidad_maxima": 2.0,
                  "plantas_maximas": 5},
    "mix_viviendas": {"superficie_minima_m2": 45.0},
}


# --- 1. La envolvente sale de la aritmetica, no de un supuesto ------------

def test_el_techo_es_el_menor_de_los_dos_limites():
    """El error de calculo urbanistico mas comun: quedarse con uno solo.

    600 m² × 2,0 de edificabilidad = 1.200 m². La huella ocupable (420 m²)
    apilada en 5 plantas daria 2.100 m². Se construye lo MENOR.
    """
    e = envolvente_edificable(COMPLETOS)
    assert e.superficie_ocupable_m2 == 420.0
    assert e.superficie_edificable_m2 == 1200.0
    assert e.techo_construible_m2 == 1200.0


def test_cuando_manda_la_ocupacion_el_techo_baja():
    """El caso simetrico: edificabilidad generosa y ocupacion estrecha."""
    params = {"solar": {"superficie_m2": 600.0},
              "normativa": {"ocupacion_maxima_pct": 30.0, "edificabilidad_maxima": 5.0,
                            "plantas_maximas": 4}}
    e = envolvente_edificable(params)
    assert e.superficie_edificable_m2 == 3000.0
    assert e.techo_construible_m2 == 720.0     # 180 m² × 4 plantas


def test_cada_cifra_de_la_envolvente_trae_su_formula():
    e = envolvente_edificable(COMPLETOS)
    texto = " ".join(e.procedencia)
    assert "600" in texto and "70.0 %" in texto and "2.0" in texto
    assert "MENOR" in texto, "no dice cual de los dos limites ha mandado"


# --- 2. Falta un parametro: no se inventa -------------------------------

def test_sin_solar_no_hay_envolvente_ni_alternativas():
    e, alts = derivar_alternativas({"solar": {}, "normativa": {}})
    assert e.techo_construible_m2 is None
    assert alts == {}
    assert "superficie del solar" in e.faltan


def test_sin_edificabilidad_ni_plantas_no_se_reparte_nada():
    """**El invariante que mas importa de este modulo.** Repartir un techo que
    no se ha podido calcular seria inventar la cifra de la que cuelga todo lo
    demas: el numero de viviendas, la superficie y el margen."""
    e, alts = derivar_alternativas({"solar": {"superficie_m2": 600.0},
                                    "normativa": {"ocupacion_maxima_pct": 70.0}})
    assert e.techo_construible_m2 is None
    assert alts == {}
    assert "edificabilidad máxima" in e.faltan


def test_lo_que_falta_se_nombra_para_poder_preguntarlo():
    e = envolvente_edificable({"solar": {"superficie_m2": 600.0}, "normativa": {}})
    assert set(e.faltan) == {"ocupación máxima", "edificabilidad máxima", "plantas máximas"}


# --- 3. Las cuatro alternativas del informe -----------------------------

def test_salen_las_cuatro_del_informe_y_son_distintas():
    _e, alts = derivar_alternativas(COMPLETOS)
    assert list(alts) == ["A", "B", "C", "D"]
    assert [a.objetivo for a in alts.values()] == list(ETIQUETAS.values())
    # Si dos objetivos dieran el mismo mix, la comparacion no diria nada.
    mixes = {tuple(sorted((k, v) for k, v in a.mix_viviendas.items()
                          if k.startswith("dorm"))) for a in alts.values()}
    assert len(mixes) >= 3, "las alternativas no se diferencian lo suficiente"


def test_maximo_numero_de_viviendas_da_mas_viviendas_que_maxima_superficie():
    """Los objetivos tienen que hacer lo que dice su nombre. Si no, la tabla
    comparativa es decorativa."""
    _e, alts = derivar_alternativas(COMPLETOS)
    assert alts["B"].viviendas > alts["A"].viviendas


def test_ninguna_alternativa_se_pasa_del_techo_construible():
    """Una alternativa que reparte mas de lo edificable **no se deriva** de los
    parametros: los incumple. El redondeo por tipologia se pasaba, y por eso hay
    un ajuste que quita viviendas hasta que cabe."""
    e, alts = derivar_alternativas(COMPLETOS)
    for etiqueta, a in alts.items():
        assert a.superficie_repartida_m2 <= e.techo_construible_m2, (
            "%s reparte %s m² sobre un techo de %s m²"
            % (etiqueta, a.superficie_repartida_m2, e.techo_construible_m2))


def test_el_ajuste_por_exceso_se_declara():
    """Quitar una vivienda en silencio es cambiar el proyecto sin decirlo."""
    _e, alts = derivar_alternativas(COMPLETOS)
    ajustadas = [a for a in alts.values()
                 if any("se han quitado" in p for p in a.procedencia)]
    for a in ajustadas:
        assert any("disponibles" in p for p in a.procedencia)


# --- 4. Nada sin procedencia (§13 de la especificacion) -----------------

def test_ninguna_alternativa_existe_sin_la_cadena_que_la_produjo():
    """El §13 aplicado aqui: «ninguna magnitud del resultado puede existir sin
    procedencia». La de la alternativa incluye la de la envolvente, porque sin
    ella «16 viviendas» es una cifra huerfana."""
    e, alts = derivar_alternativas(COMPLETOS)
    for etiqueta, a in alts.items():
        assert a.procedencia, "%s no trae procedencia" % etiqueta
        # La cadena entera: de dónde sale el techo Y cómo se repartió.
        texto = " ".join(a.procedencia)
        assert "Superficie del solar" in texto
        assert "techo construible" in texto.lower()
        assert "Reparto del objetivo" in texto
        # Y la cifra de viviendas se puede rastrear hasta el techo.
        assert str(a.viviendas) in texto


def test_el_catalogo_de_objetivos_y_los_repartos_no_pueden_divergir():
    """Un objetivo sin reparto reventaria al derivarlo; un reparto sin objetivo
    es codigo muerto que alguien acabara creyendo que se usa."""
    assert set(OBJETIVOS) == set(REPARTOS)
    assert set(ETIQUETAS.values()) == set(OBJETIVOS)
    for objetivo, reparto in REPARTOS.items():
        assert abs(sum(reparto.values()) - 1.0) < 1e-9, objetivo


def test_se_pueden_pedir_solo_algunos_objetivos():
    _e, alts = derivar_alternativas(COMPLETOS, objetivos=("maxima_superficie",))
    assert list(alts) == ["A"]
