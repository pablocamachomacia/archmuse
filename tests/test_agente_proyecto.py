# -*- coding: utf-8 -*-
"""Ajustar el encargo de un proyecto generado (`CP-1`, pieza 5 del MVP).

Ejecutar:  pytest tests/test_agente_proyecto.py

PRD: `docs/prd/2026-08-19-copiloto-que-modifica-el-proyecto.md`.

**Lo que se fija aqui, y por que esta capacidad es delicada pese a ser
aritmetica.** Es la primera que existe para que un modelo de lenguaje la invoque
con argumentos que se ha inventado a partir de una frase en castellano. Todo lo
demas del registro lo invoca codigo. Asi que lo que hay que probar no es solo
que la suma este bien: es que **una peticion mal entendida no destruya el
proyecto del arquitecto** ni produzca un encargo imposible en silencio.

Tres invariantes:

1. **Nunca muta lo que recibe.** Si la regeneracion falla despues, quien llamo
   conserva la alternativa anterior intacta.
2. **Se niega antes que aproximar.** Una operacion fuera del catalogo, un valor
   que deja el proyecto sin viviendas o un cambio que no cambia nada vuelven con
   `ok: false` y su pregunta.
3. **No decide nada.** Aplica el cambio y dice que cambio; no opina sobre si el
   proyecto resultante es mejor.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agente.herramientas.proyecto import (  # noqa: E402
    OPERACIONES, TIPOS_DE_VIVIENDA, ajustar_programa,
)
from agente.registro import registro  # noqa: E402

PARAMS = {
    "proyecto": {"ciudad": "Madrid", "tipologia": "plurifamiliar"},
    "solar": {"superficie_m2": 600.0, "forma": "rectangular"},
    "edificio": {"plantas": 4, "altura_libre_m": 2.8},
    "mix_viviendas": {"dorm_1": 2, "dorm_2": 6, "dorm_3": 2, "superficie_minima_m2": 45.0},
    "normativa": {"ocupacion_maxima_pct": 70.0, "retranqueos_m": 3.0},
    "superficie_objetivo_m2": 900.0,
}


def params():
    return copy.deepcopy(PARAMS)


# --- 1. Los tres ajustes ---------------------------------------------------

def test_un_valor_relativo_resta_sobre_lo_que_habia():
    """«Elimina una vivienda» es relativo. Obligar al copiloto a convertirlo en
    absoluto seria pedirle que haga aritmetica, que es justo lo que no debe."""
    r = ajustar_programa(params(), "cambiar_mix", {"dorm_2": "-1"})
    assert r["ok"] is True
    assert r["parametros"]["mix_viviendas"]["dorm_2"] == 5
    assert r["viviendas_antes"] == 10 and r["viviendas_despues"] == 9


def test_un_valor_absoluto_fija_el_numero():
    r = ajustar_programa(params(), "cambiar_mix", {"dorm_3": 4})
    assert r["ok"] is True
    assert r["parametros"]["mix_viviendas"]["dorm_3"] == 4
    assert r["antes"]["dorm_3"] == 2 and r["despues"]["dorm_3"] == 4


def test_se_pueden_cambiar_varios_tipos_a_la_vez():
    """«Quita una de dos y pon una de tres» es una sola intencion."""
    r = ajustar_programa(params(), "cambiar_mix", {"dorm_2": "-1", "dorm_3": "+1"})
    assert r["ok"] is True
    assert r["viviendas_antes"] == r["viviendas_despues"] == 10


def test_cambiar_plantas_y_superficie_objetivo():
    r = ajustar_programa(params(), "cambiar_plantas", {"plantas": 6})
    assert r["ok"] is True and r["parametros"]["edificio"]["plantas"] == 6

    r = ajustar_programa(params(), "cambiar_superficie_objetivo",
                         {"superficie_objetivo_m2": 1200})
    assert r["ok"] is True and r["parametros"]["superficie_objetivo_m2"] == 1200.0


def test_siempre_dice_si_hay_que_regenerar():
    """Quien llama no tiene que deducirlo del tipo de operacion."""
    for operacion, argumentos in (("cambiar_mix", {"dorm_1": 3}),
                                  ("cambiar_plantas", {"plantas": 5}),
                                  ("cambiar_superficie_objetivo",
                                   {"superficie_objetivo_m2": 1000})):
        assert ajustar_programa(params(), operacion, argumentos)["hay_que_regenerar"] is True


# --- 2. No muta lo que recibe ---------------------------------------------

def test_los_parametros_de_entrada_quedan_intactos():
    """**El invariante que evita perder el trabajo del arquitecto.** Si la
    regeneracion falla despues, la alternativa anterior sigue entera."""
    entrada = params()
    copia = copy.deepcopy(entrada)
    r = ajustar_programa(entrada, "cambiar_mix", {"dorm_2": "-3"})
    assert r["ok"] is True
    assert entrada == copia, "la capacidad ha mutado los parametros que recibio"
    # Y lo devuelto es otro objeto, no el mismo con otro nombre.
    assert r["parametros"] is not entrada
    assert r["parametros"]["mix_viviendas"] is not entrada["mix_viviendas"]


# --- 3. Se niega antes que aproximar --------------------------------------

def test_una_operacion_fuera_del_catalogo_se_declara_y_no_se_aproxima():
    """CU-4 del PRD: «ponme el salon al sur» no se parece lo bastante a nada
    como para intentarlo. La respuesta correcta es decir que no se sabe."""
    r = ajustar_programa(params(), "orientar_salon_al_sur", {})
    assert r["ok"] is False
    assert r["error"] == "operacion_no_soportada"
    # Y dice lo que SI puede hacer, que es lo que convierte una negativa en algo
    # util en vez de en un callejon.
    assert all(op in r["detalle"] for op in OPERACIONES)
    assert r["pregunta"]


def test_no_se_puede_dejar_el_proyecto_sin_viviendas():
    r = ajustar_programa(params(), "cambiar_mix",
                         dict.fromkeys(TIPOS_DE_VIVIENDA, 0))
    assert r["ok"] is False
    assert r["error"] == "proyecto_sin_viviendas"


def test_no_se_pueden_quitar_mas_viviendas_de_las_que_hay():
    r = ajustar_programa(params(), "cambiar_mix", {"dorm_1": "-5"})
    assert r["ok"] is False
    assert r["error"] == "no_quedan_viviendas_de_ese_tipo"
    # El mensaje dice cuantas hay: sin esa cifra el arquitecto no sabe que pedir.
    assert "2" in r["detalle"]


def test_un_cambio_que_no_cambia_nada_se_dice():
    """Regenerar --una llamada cara al generador-- para dejar el proyecto igual
    es gastar dinero y tiempo del arquitecto en nada."""
    r = ajustar_programa(params(), "cambiar_plantas", {"plantas": 4})
    assert r["ok"] is False
    assert r["error"] == "el_proyecto_ya_estaba_asi"


def test_un_valor_no_numerico_se_rechaza_con_su_pregunta():
    for operacion, argumentos in (("cambiar_mix", {"dorm_2": "unas cuantas"}),
                                  ("cambiar_plantas", {"plantas": "muchas"}),
                                  ("cambiar_superficie_objetivo",
                                   {"superficie_objetivo_m2": None})):
        r = ajustar_programa(params(), operacion, argumentos)
        assert r["ok"] is False, (operacion, argumentos)
        assert r["error"] in ("valor_no_numerico", "sin_cambio_indicado")
        assert r["pregunta"]


def test_sin_parametros_no_se_inventa_un_proyecto():
    r = ajustar_programa({}, "cambiar_mix", {"dorm_1": 1})
    assert r["ok"] is False and r["error"] == "sin_parametros"


def test_cambiar_mix_sin_decir_que_tipo_pregunta():
    r = ajustar_programa(params(), "cambiar_mix", {})
    assert r["ok"] is False and r["error"] == "sin_cambio_indicado"


# --- 4. El contrato del registro ------------------------------------------

def test_esta_registrada_no_tiene_efectos_y_dice_lo_que_no_hace():
    capacidad = registro(recargar=True).buscar("proyecto.ajustar_programa")
    # Sin efectos: transforma un diccionario, no toca el mundo exterior. Pedir
    # una autorizacion que no hace falta ensena a concederlas sin leerlas.
    assert capacidad.efectos == ()
    assert capacidad.naturaleza == "determinista"
    limitaciones = " ".join(capacidad.limitaciones).lower()
    assert "no regenera" in limitaciones
    assert "no decide" in limitaciones
    assert "no toca ningún fichero" in limitaciones


def test_el_catalogo_de_operaciones_del_manifiesto_y_del_codigo_coinciden():
    """Si divergen, el modelo recibe un enum que no existe --o le falta uno que
    si-- y la negativa de CU-4 deja de funcionar sin que nadie se entere."""
    capacidad = registro(recargar=True).buscar("proyecto.ajustar_programa")
    declaradas = capacidad.parametros["properties"]["operacion"]["enum"]
    assert tuple(declaradas) == OPERACIONES
