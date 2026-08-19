# -*- coding: utf-8 -*-
"""V0-3 — que cada llamada a un modelo quede medida, y que el gasto tenga techo.

Ejecutar:  pytest tests/test_ia_uso.py

Hasta esta tarea `response.usage` no se leía en ningún punto del repositorio,
así que la pregunta "cuánto cuesta un usuario" no tenía respuesta con datos.
Lo que estos tests fijan:

1. El coste se calcula con la tarifa publicada, y la caché cuenta a su precio.
2. Un modelo sin tarifa da `None`, nunca una cifra inventada con el precio de
   otro — misma regla que gobierna el resto del producto.
3. El envoltorio no cambia el cliente: `.timeout` y lo demás siguen llegando.
4. El registro no guarda ni un carácter de prompt ni de respuesta.
5. El techo corta **antes** de gastar, y una variable mal escrita no lo desactiva.

No hace falta clave ni red: el cliente se sustituye por un doble.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from ia import cliente as cliente_mod  # noqa: E402
from ia import uso  # noqa: E402


class UsoFalso:
    def __init__(self, entrada=0, salida=0, cache_escritura=0, cache_lectura=0):
        self.input_tokens = entrada
        self.output_tokens = salida
        self.cache_creation_input_tokens = cache_escritura
        self.cache_read_input_tokens = cache_lectura


class RespuestaFalsa:
    def __init__(self, uso_):
        self.usage = uso_
        self.model = "claude-sonnet-5"
        self.content = []


class MensajesFalsos:
    def __init__(self):
        self.ultima = None

    def create(self, **kwargs):
        self.ultima = kwargs
        return RespuestaFalsa(UsoFalso(entrada=1000, salida=500, cache_lectura=2000))


class ClienteFalso:
    def __init__(self):
        self.messages = MensajesFalsos()
        self.timeout = 120.0


@pytest.fixture(autouse=True)
def _limpio(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHMUSE_REGISTRO_USO", str(tmp_path / "uso_ia.jsonl"))
    monkeypatch.delenv("ARCHMUSE_TOPE_GASTO_USD", raising=False)
    uso.reiniciar()
    yield
    uso.reiniciar()


# --- 1 y 2. El cálculo del coste -------------------------------------------

def test_el_coste_usa_la_tarifa_y_cobra_la_cache_a_su_precio():
    # 1M de entrada, 1M de salida, 1M leído de caché, sobre Sonnet 5 ($3/$15).
    u = UsoFalso(entrada=1_000_000, salida=1_000_000, cache_lectura=1_000_000)
    esperado = 3.00 + 15.00 + 3.00 * uso.FACTOR_LECTURA_CACHE
    assert uso.coste_usd("claude-sonnet-5", u) == pytest.approx(esperado)


def test_escribir_en_cache_cuesta_mas_que_la_entrada_normal():
    normal = uso.coste_usd("claude-sonnet-5", UsoFalso(entrada=1_000_000))
    escrito = uso.coste_usd("claude-sonnet-5", UsoFalso(cache_escritura=1_000_000))
    assert escrito == pytest.approx(normal * uso.FACTOR_ESCRITURA_CACHE)


def test_un_modelo_sin_tarifa_no_inventa_una_cifra():
    assert uso.coste_usd("un-modelo-que-no-existe", UsoFalso(entrada=1_000)) is None


# --- 3. El envoltorio no estorba -------------------------------------------

def test_el_envoltorio_deja_pasar_el_resto_del_cliente():
    envuelto = cliente_mod._ClienteMedido(ClienteFalso(), llamante="tests/x.py")
    assert envuelto.timeout == 120.0


def test_los_argumentos_llegan_intactos_al_sdk():
    falso = ClienteFalso()
    envuelto = cliente_mod._ClienteMedido(falso, llamante="tests/x.py")
    envuelto.messages.create(model="claude-sonnet-5", max_tokens=1024, system="hola")
    assert falso.messages.ultima["max_tokens"] == 1024
    assert falso.messages.ultima["system"] == "hola"


# --- 4. Se registran métricas, nunca texto ---------------------------------

def test_el_registro_anota_la_llamada_y_no_guarda_ni_un_caracter_del_prompt():
    envuelto = cliente_mod._ClienteMedido(ClienteFalso(), llamante="analyzer/ai_analyst.py")
    envuelto.messages.create(
        model="claude-sonnet-5", max_tokens=1024,
        system="SECRETO DEL PROYECTO DEL CLIENTE",
        messages=[{"role": "user", "content": "OTRO SECRETO"}],
    )
    texto = io.open(uso.ruta_registro(), encoding="utf-8").read()
    assert "SECRETO" not in texto
    fila = json.loads(texto.strip())
    assert fila["llamante"] == "analyzer/ai_analyst.py"
    assert fila["modelo"] == "claude-sonnet-5"
    assert fila["input_tokens"] == 1000
    assert fila["output_tokens"] == 500
    assert fila["cache_read_input_tokens"] == 2000
    assert fila["coste_usd"] > 0
    assert set(fila) == {
        "ts", "llamante", "modelo", "input_tokens", "output_tokens",
        "cache_creation_input_tokens", "cache_read_input_tokens",
        "duracion_s", "coste_usd", "acumulado_usd",
    }


def test_el_acumulado_suma_entre_llamadas():
    envuelto = cliente_mod._ClienteMedido(ClienteFalso(), llamante="tests/x.py")
    envuelto.messages.create(model="claude-sonnet-5", max_tokens=10)
    envuelto.messages.create(model="claude-sonnet-5", max_tokens=10)
    assert uso.resumen()["llamadas"] == 2
    filas = [json.loads(l) for l in io.open(uso.ruta_registro(), encoding="utf-8")]
    assert filas[1]["acumulado_usd"] > filas[0]["acumulado_usd"]


# --- 5. El techo ------------------------------------------------------------

def test_el_techo_corta_antes_de_hacer_la_llamada(monkeypatch):
    """Lo importante es *antes*: pasarse por una llamada ya pagada no sirve."""
    monkeypatch.setenv("ARCHMUSE_TOPE_GASTO_USD", "0.001")
    falso = ClienteFalso()
    envuelto = cliente_mod._ClienteMedido(falso, llamante="tests/x.py")
    envuelto.messages.create(model="claude-sonnet-5", max_tokens=10)  # 1ª pasa
    llamadas_antes = falso.messages.ultima
    with pytest.raises(uso.TopeDeGastoSuperado):
        envuelto.messages.create(model="claude-opus-5", max_tokens=99999)
    # El SDK no llegó a verla: la última llamada registrada sigue siendo la 1ª.
    assert falso.messages.ultima is llamadas_antes


@pytest.mark.parametrize("bruto", ["", "basura", "0", "-3", "  "])
def test_una_variable_mal_escrita_no_deja_el_proceso_sin_techo(monkeypatch, bruto):
    monkeypatch.setenv("ARCHMUSE_TOPE_GASTO_USD", bruto)
    assert uso.tope_usd() == uso.TOPE_POR_DEFECTO_USD


def test_el_techo_se_respeta_cuando_es_valido(monkeypatch):
    monkeypatch.setenv("ARCHMUSE_TOPE_GASTO_USD", "12.5")
    assert uso.tope_usd() == 12.5


# --- 6. El desglose por punto de llamada (SEG-4) ----------------------------

def test_el_desglose_dice_en_que_modulo_se_fue_el_dinero():
    """SEG-4. El total suelto no permite decidir nada.

    Saber que un análisis cuesta 0,42 USD no dice qué recortar. Saber que 0,31
    los gastó `analyzer/ai_generator.py` sí, y es lo que hace posible `AG-3`
    (escalonar el modelo por perfil **midiendo**, no por intuición).
    """
    uso.registrar(modelo="claude-opus-5", llamante="analyzer/ai_generator.py",
                  uso=UsoFalso(entrada=100_000, salida=50_000), duracion_s=1.0)
    uso.registrar(modelo="claude-haiku-4-5", llamante="extraccion/interprete.py",
                  uso=UsoFalso(entrada=10_000, salida=1_000), duracion_s=0.2)
    uso.registrar(modelo="claude-haiku-4-5", llamante="extraccion/interprete.py",
                  uso=UsoFalso(entrada=10_000, salida=1_000), duracion_s=0.2)

    d = uso.desglose()
    assert d["llamadas"] == 3
    assert set(d["por_llamante"]) == {"analyzer/ai_generator.py", "extraccion/interprete.py"}
    assert d["por_llamante"]["extraccion/interprete.py"]["llamadas"] == 2
    assert set(d["por_modelo"]) == {"claude-opus-5", "claude-haiku-4-5"}
    # El generador con Opus tiene que dominar el gasto: es justo el hallazgo
    # que esta medición existe para producir.
    assert (d["por_llamante"]["analyzer/ai_generator.py"]["usd"]
            > 10 * d["por_llamante"]["extraccion/interprete.py"]["usd"])
    assert d["total_usd"] == pytest.approx(sum(f["usd"] for f in d["por_llamante"].values()), rel=1e-6)


def test_sin_tipo_de_cambio_declarado_no_se_inventan_euros(monkeypatch):
    """La tarifa está en dólares. Un cambio inventado o caducado produce una
    cifra que parece contable y no lo es."""
    monkeypatch.delenv("ARCHMUSE_EUR_POR_USD", raising=False)
    uso.registrar(modelo="claude-sonnet-5", llamante="x/y.py",
                  uso=UsoFalso(entrada=1_000_000), duracion_s=0.1)
    d = uso.desglose()
    assert d["total_usd"] > 0
    assert d["total_eur"] is None
    assert "USD" in uso.a_texto(d)


def test_con_el_cambio_declarado_el_desglose_da_euros(monkeypatch):
    monkeypatch.setenv("ARCHMUSE_EUR_POR_USD", "0.90")
    uso.registrar(modelo="claude-sonnet-5", llamante="x/y.py",
                  uso=UsoFalso(entrada=1_000_000), duracion_s=0.1)
    d = uso.desglose()
    assert d["total_eur"] == pytest.approx(d["total_usd"] * 0.90)
    assert d["por_llamante"]["x/y.py"]["eur"] == pytest.approx(3.00 * 0.90)
    assert "EUR" in uso.a_texto(d)


@pytest.mark.parametrize("bruto", ["", "gratis", "-1", "0"])
def test_un_cambio_mal_escrito_no_produce_una_cifra_en_euros(monkeypatch, bruto):
    monkeypatch.setenv("ARCHMUSE_EUR_POR_USD", bruto)
    assert uso.eur_por_usd() is None
    assert uso.en_euros(1.0) is None


def test_una_llamada_sin_tarifa_no_se_disuelve_en_el_total():
    """Un modelo sin precio no vale cero: vale desconocido, y el desglose lo
    dice para que nadie lea el total como si estuviera completo."""
    uso.registrar(modelo="modelo-que-no-existe", llamante="x/y.py",
                  uso=UsoFalso(entrada=1_000_000, salida=1_000_000), duracion_s=0.1)
    d = uso.desglose()
    assert d["sin_tarifar"] == 1
    assert d["por_llamante"]["x/y.py"]["usd"] == 0.0
    assert "AVISO" in uso.a_texto(d)


def test_el_desglose_se_reinicia_con_el_contador():
    uso.registrar(modelo="claude-sonnet-5", llamante="x/y.py",
                  uso=UsoFalso(entrada=1000), duracion_s=0.1)
    uso.reiniciar()
    assert uso.desglose()["por_llamante"] == {}


def test_el_coste_de_un_analisis_terminado_se_lee_del_registro(tmp_path, monkeypatch):
    """SEG-4, criterio de terminado: un análisis completo da su cifra
    desglosada por punto de llamada — incluso si lo ejecutó otro proceso.

    El servidor, un worker o la suite hacen las llamadas y se acaban; los
    contadores vivos se van con ellos. Lo que queda es el JSONL, y de ahí sale
    la cuenta.
    """
    ruta = tmp_path / "uso_ia.jsonl"
    monkeypatch.setenv("ARCHMUSE_REGISTRO_USO", str(ruta))
    monkeypatch.setenv("ARCHMUSE_EUR_POR_USD", "0.90")
    uso.registrar(modelo="claude-opus-5", llamante="analyzer/ai_generator.py",
                  uso=UsoFalso(entrada=1_000_000, salida=1_000_000), duracion_s=2.0)
    uso.registrar(modelo="claude-haiku-4-5", llamante="analyzer/ai_analyst.py",
                  uso=UsoFalso(entrada=1_000_000), duracion_s=0.5)

    d = uso.desglose_de_registro(str(ruta))
    assert d["llamadas"] == 2
    assert d["por_llamante"]["analyzer/ai_generator.py"]["usd"] == pytest.approx(30.0)
    assert d["por_llamante"]["analyzer/ai_analyst.py"]["usd"] == pytest.approx(1.0)
    assert d["total_eur"] == pytest.approx(31.0 * 0.90)
    assert "analyzer/ai_generator.py" in uso.a_texto(d)


def test_una_linea_corrupta_no_impide_contar_el_resto(tmp_path, monkeypatch):
    ruta = tmp_path / "uso_ia.jsonl"
    monkeypatch.setenv("ARCHMUSE_REGISTRO_USO", str(ruta))
    uso.registrar(modelo="claude-sonnet-5", llamante="x/y.py",
                  uso=UsoFalso(entrada=1_000_000), duracion_s=0.1)
    with io.open(ruta, "a", encoding="utf-8") as fh:
        fh.write("{esto no es json" + chr(10))
    assert uso.desglose_de_registro(str(ruta))["llamadas"] == 1


def test_un_registro_que_no_existe_no_revienta(tmp_path):
    assert uso.desglose_de_registro(str(tmp_path / "no_existe.jsonl"))["llamadas"] == 0
