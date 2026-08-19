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


def test_una_cifra_inventada_si_se_marca_como_sin_respaldo(cliente_http, monkeypatch):
    """Criterio nº4 del PRD, mitad sin cubrir hasta ahora (`CP-7`, sesión
    2026-08-19, noche 12): el test anterior sólo probaba que una cifra REAL
    no se marca. Eso no demuestra que `cifras_sin_respaldo` sepa detectar
    nada -- un mecanismo que nunca se dispara y uno que funciona se ven
    idénticos si sólo se le da a probar el caso positivo. Aquí el modelo
    (guionizado) cita un margen que no está en ninguna alternativa del
    estado (`ALTERNATIVAS` sólo trae 18.2 % y 21.4 %) y el endpoint tiene
    que devolverla en `cifras_sin_respaldo`, no dejarla pasar como si
    viniera de una herramienta."""
    modulo_app, http = cliente_http
    _guionizar(monkeypatch, modulo_app, RespuestaFalsa(
        BloqueTexto("La B, con 94.7 % de margen.")))

    datos = _pedir(http, "¿Cuál tiene mejor rentabilidad?").get_json()
    assert "94.7" in datos["cifras_sin_respaldo"]


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


def test_toda_modificacion_queda_en_el_acta(cliente_http, monkeypatch):
    """Criterio de aceptación nº7 del PRD, nunca comprobado hasta ahora
    (sesión 2026-08-19, noche 8): "Toda modificación queda en el acta:
    petición, herramienta, argumentos, resultado." No es un acta de Skill
    (el copiloto no invoca ninguna) -- `agente.acta.levantar_de_pasos()`,
    construida directamente desde los pasos del bucle."""
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

    acta = datos["acta"]
    assert acta["objetivo"] == "Elimina una vivienda de dos dormitorios"  # la petición
    assert acta["sello"]  # sellada, como cualquier acta

    (paso,) = acta["pasos"]
    assert paso["skill"] == "proyecto.ajustar_programa"  # la herramienta
    assert paso["argumentos"] == {"operacion": "cambiar_mix", "argumentos": {"dorm_2": "-1"},
                                   "parametros": PARAMS}  # los argumentos, tal cual se invocó
    assert paso["resultado"]["despues"]["dorm_2"] == 5  # el resultado
    assert paso["verificado"] is True

    # La cifra que de verdad importa (el mix nuevo) tiene que estar en "qué
    # se ha establecido", trazable a la capacidad que la produjo. `despues`
    # de `ajustar_programa()` ya es plano (`{"dorm_2": 5, ...}`, no anidado
    # bajo "mix_viviendas") -- una sola entrada por cifra, sin dict en
    # crudo (ver `_aplanar` en agente/acta.py, para cuando sí venga anidado).
    dato_dorm2 = next(d for d in acta["datos"] if d["nombre"].endswith(".dorm_2"))
    assert dato_dorm2["valor"] == 5
    assert dato_dorm2["fuente"] == "proyecto.ajustar_programa@1.0.0"


def test_una_pregunta_sin_cambios_tambien_lleva_acta_pero_vacia(cliente_http, monkeypatch):
    """Una pregunta no modifica nada (criterio nº2) -- el acta lo dice con
    hechos (cero pasos), no lo omite. Un acta ausente sería peor que una
    vacía: obligaría a adivinar si "no hay acta" significa "no se comprobó
    nada" o "no se ejecutó nada"."""
    modulo_app, http = cliente_http
    _guionizar(monkeypatch, modulo_app, RespuestaFalsa(
        BloqueTexto("La alternativa B: 21.4 % de margen frente a 18.2 % de la A.")))

    datos = _pedir(http, "¿Cuál tiene mejor rentabilidad?").get_json()

    assert datos["acta"]["pasos"] == []
    assert datos["acta"]["datos"] == []
    assert datos["acta"]["completa"] is False  # nada que ejecutar no es "completo"


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

def test_una_operacion_no_soportada_es_una_negativa_explicita_no_un_intento_aproximado(
        cliente_http, monkeypatch):
    """Criterio nº3 del PRD, sin cubrir hasta ahora (`CP-7`, sesión
    2026-08-19, noche 12): "una petición que ArchMuse no sabe atender produce
    una negativa explícita, no un intento aproximado". Existía el test de la
    capacidad suelta (`tests/test_agente_proyecto.py`), pero no a través del
    endpoint -- que es donde vive de verdad el criterio de aceptación, porque
    es lo que ve el arquitecto.

    Aquí el modelo (guionizado) pide una operación que
    `proyecto.ajustar_programa` no sabe hacer. Se rechaza en el primer punto
    posible -- la validación de argumentos contra el `enum` del esquema,
    antes de que la función llegue a ejecutarse -- en vez de aproximarla a la
    más parecida (p. ej. tratar "cambia el material" como si fuera "cambia
    la superficie"), y esa negativa explícita -- con el nombre de la
    operación pedida y las que sí admite -- tiene que llegar íntegra hasta
    la respuesta."""
    modulo_app, http = cliente_http
    _guionizar(
        monkeypatch, modulo_app,
        RespuestaFalsa(BloqueHerramienta(NOMBRE_HERRAMIENTA, {
            "parametros": copy.deepcopy(PARAMS),
            "operacion": "cambiar_material_fachada",
            "argumentos": {},
        })),
        RespuestaFalsa(BloqueTexto(
            "No puedo cambiar el material de fachada: puedo ajustar el mix "
            "de viviendas, las plantas o la superficie objetivo.")),
    )

    datos = _pedir(http, "Cambia el material de fachada a ladrillo").get_json()

    assert datos["hubo_cambio"] is False
    assert "parametros" not in datos
    assert datos["pasos"] and datos["pasos"][0]["ok"] is False
    # La negativa, íntegra y explícita, en "qué no se ha comprobado" del
    # acta -- no un "no se ha podido" genérico ni un ajuste silencioso.
    (motivo,) = [d for d in datos["acta"]["no_comprobado"] if "ajustar_programa" in d]
    assert "cambiar_material_fachada" in motivo
    assert "cambiar_mix" in motivo and "cambiar_plantas" in motivo


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
