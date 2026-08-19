# -*- coding: utf-8 -*-
"""El endpoint del copiloto (`CP-2`, pieza 5 del MVP).

Ejecutar:  pytest tests/test_copiloto_endpoint.py

PRD: `docs/prd/2026-08-19-copiloto-que-modifica-el-proyecto.md`. Aqui se fijan
sus criterios de aceptacion, y el que mas importa es el nº2:

**Una pregunta no modifica nada.** «Cual tiene mejor rentabilidad?» es una
pregunta; «elimina una vivienda» es una orden. Confundirlas --modificar el
proyecto porque alguien pregunto-- es el peor fallo posible de esta pieza, y no
se comprueba leyendo la respuesta del modelo sino **contando invocaciones**: lo
unico que demuestra que un cambio ocurrio es que la herramienta se invoco.

Con cliente guionizado: sin red, sin clave y sin gastar un token.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from tests.test_agente_nucleo import (  # noqa: E402
    BloqueHerramienta, BloqueTexto, ClienteGuionizado, RespuestaFalsa,
)

PARAMS = {
    "proyecto": {"ciudad": "Madrid", "tipologia": "plurifamiliar"},
    "solar": {"superficie_m2": 600.0, "forma": "rectangular"},
    "edificio": {"plantas": 4, "altura_libre_m": 2.8},
    "mix_viviendas": {"dorm_1": 2, "dorm_2": 6, "dorm_3": 2, "superficie_minima_m2": 45.0},
    "normativa": {"ocupacion_maxima_pct": 70.0, "retranqueos_m": 3.0},
    "superficie_objetivo_m2": 900.0,
}

ALTERNATIVAS = [
    {"etiqueta": "A", "metricas": {"repercusion_zonas_comunes_pct": 12.5,
                                   "pct_fachada_aprovechada": 78.0,
                                   "margen_estimado": {"margen_pct": 18.2}}},
    {"etiqueta": "B", "metricas": {"repercusion_zonas_comunes_pct": 9.8,
                                   "pct_fachada_aprovechada": 71.0,
                                   "margen_estimado": {"margen_pct": 21.4}}},
]

NOMBRE_HERRAMIENTA = "proyecto__ajustar_programa"


@pytest.fixture()
def cliente_http(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-no-es-una-clave-real")
    import app as modulo_app

    modulo_app.app.config["TESTING"] = True
    return modulo_app, modulo_app.app.test_client()


def _guionizar(monkeypatch, modulo_app, *turnos):
    """Sustituye el cliente real por uno guionizado, y lo devuelve."""
    doble = ClienteGuionizado(*turnos)
    monkeypatch.setattr("ia.cliente.crear_cliente", lambda *a, **k: doble)
    return doble


def _pedir(http, peticion, parametros=None, alternativas=None):
    return http.post("/api/copiloto", json={
        "peticion": peticion,
        "parametros": copy.deepcopy(PARAMS if parametros is None else parametros),
        "alternativas": ALTERNATIVAS if alternativas is None else alternativas,
    })


# --- 1. El criterio nº2: una pregunta no toca nada ------------------------

def test_una_pregunta_no_invoca_ninguna_herramienta(cliente_http, monkeypatch):
    """CU-3 del PRD. Se comprueba contando invocaciones, no leyendo el texto."""
    modulo_app, http = cliente_http
    _guionizar(monkeypatch, modulo_app, RespuestaFalsa(
        BloqueTexto("La alternativa B: 21.4 % de margen frente a 18.2 % de la A.")))

    datos = _pedir(http, "¿Cuál tiene mejor rentabilidad?").get_json()

    assert datos["pasos"] == [], "una pregunta ha invocado una herramienta"
    assert datos["hubo_cambio"] is False
    # Y no devuelve parametros: es lo que el cliente usa para saber si regenerar.
    assert "parametros" not in datos


def test_una_pregunta_puede_citar_las_cifras_del_estado_sin_inventarlas(cliente_http, monkeypatch):
    """El estado viaja en la peticion a proposito: asi `respaldo.py` reconoce
    como respaldada una cifra que el copiloto repite de ahi. Si el estado
    hubiera ido en el prompt de sistema, cada cifra del proyecto se marcaria
    como inventada."""
    modulo_app, http = cliente_http
    _guionizar(monkeypatch, modulo_app, RespuestaFalsa(
        BloqueTexto("La B, con 21.4 % de margen.")))

    datos = _pedir(http, "¿Cuál tiene mejor rentabilidad?").get_json()
    assert datos["cifras_sin_respaldo"] == []


# --- 2. Una orden sí modifica --------------------------------------------

def test_una_orden_invoca_la_herramienta_y_devuelve_los_parametros_nuevos(cliente_http, monkeypatch):
    modulo_app, http = cliente_http
    _guionizar(
        monkeypatch, modulo_app,
        RespuestaFalsa(BloqueHerramienta(NOMBRE_HERRAMIENTA, {
            "parametros": copy.deepcopy(PARAMS),
            "operacion": "cambiar_mix",
            "argumentos": {"dorm_2": "-1"},
        })),
        RespuestaFalsa(BloqueTexto("Quitada una vivienda de 2 dormitorios: de 6 a 5.")),
    )

    datos = _pedir(http, "Elimina una vivienda de dos dormitorios").get_json()

    assert datos["hubo_cambio"] is True
    assert datos["parametros"]["mix_viviendas"]["dorm_2"] == 5
    assert datos["antes"]["dorm_2"] == 6 and datos["despues"]["dorm_2"] == 5
    assert datos["hay_que_regenerar"] is True
    assert [p["capacidad"] for p in datos["pasos"]] == ["proyecto.ajustar_programa"]


def test_un_ajuste_imposible_no_deja_el_proyecto_a_medias(cliente_http, monkeypatch):
    """Criterio nº5: si el ajuste no se puede aplicar, no hay parametros nuevos
    y el proyecto anterior sigue siendo el bueno."""
    modulo_app, http = cliente_http
    _guionizar(
        monkeypatch, modulo_app,
        RespuestaFalsa(BloqueHerramienta(NOMBRE_HERRAMIENTA, {
            "parametros": copy.deepcopy(PARAMS),
            "operacion": "cambiar_mix",
            "argumentos": {"dorm_1": "-9"},
        })),
        RespuestaFalsa(BloqueTexto("No puedo: sólo hay 2 viviendas de un dormitorio.")),
    )

    datos = _pedir(http, "Quita nueve viviendas de un dormitorio").get_json()

    assert datos["hubo_cambio"] is False
    assert "parametros" not in datos
    assert datos["pasos"] and datos["pasos"][0]["ok"] is False


# --- 3. El registro estrecho ---------------------------------------------

def test_el_copiloto_solo_ve_una_herramienta(cliente_http, monkeypatch):
    """**La regla fundamental del informe, hecha cumplir por construccion.**

    El copiloto no puede leer un DXF ni escribir un fichero, y no porque se le
    pida que no: porque esas herramientas no estan en la lista que recibe. Se
    comprueba sobre lo que de verdad se le mando a la API.
    """
    modulo_app, http = cliente_http
    doble = _guionizar(monkeypatch, modulo_app, RespuestaFalsa(BloqueTexto("Hecho.")))

    _pedir(http, "¿Cuántas viviendas hay?")

    herramientas = {h["name"] for h in doble.llamadas[0]["tools"]}
    assert herramientas == {NOMBRE_HERRAMIENTA}, herramientas
    assert not [h for h in herramientas if h.startswith("plano__")]
    assert not [h for h in herramientas if h.startswith("normativa__")]


def test_el_estado_del_proyecto_llega_al_modelo(cliente_http, monkeypatch):
    modulo_app, http = cliente_http
    doble = _guionizar(monkeypatch, modulo_app, RespuestaFalsa(BloqueTexto("Vale.")))

    _pedir(http, "¿Cuántas plantas tiene?")

    enviado = str(doble.llamadas[0]["messages"])
    assert "Madrid" in enviado and "6 de 2" in enviado
    assert "¿Cuántas plantas tiene?" in enviado


# --- 4. Las negativas ----------------------------------------------------

def test_sin_peticion_no_se_llama_al_modelo(cliente_http, monkeypatch):
    modulo_app, http = cliente_http
    doble = _guionizar(monkeypatch, modulo_app, RespuestaFalsa(BloqueTexto("x")))
    assert http.post("/api/copiloto", json={"peticion": "   "}).status_code == 400
    assert doble.llamadas == [], "se ha gastado una llamada con una peticion vacia"


def test_sin_clave_el_copiloto_se_desactiva_y_lo_dice(monkeypatch):
    """Criterio nº6: sin clave, las piezas 1 a 4 siguen funcionando enteras."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import app as modulo_app

    respuesta = modulo_app.app.test_client().post(
        "/api/copiloto", json={"peticion": "quita una vivienda"})
    assert respuesta.status_code == 503
    datos = respuesta.get_json()
    assert datos["codigo"] == "ia_no_disponible"
    # Y dice que lo demas sigue funcionando, que es la diferencia entre un aviso
    # util y un callejon.
    assert "funciona sin ella" in datos["error"]
