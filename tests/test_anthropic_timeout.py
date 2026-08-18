# -*- coding: utf-8 -*-
"""Tarea 9 — ninguna llamada a Anthropic puede colgarse sin límite.

Ejecutar:  pytest tests/test_anthropic_timeout.py

El SDK trae 600 s de lectura y 2 reintentos: una llamada colgada retenía un
hilo del pool de `waitress` hasta 30 minutos. Ninguno de los cinco clientes
del producto pasaba `timeout`.

**El test que de verdad importa es el último.** Comprobar que los cinco tienen
timeout hoy no impide que mañana aparezca un sexto sin él — que es exactamente
lo que pasó entre que se escribió la ficha (2 clientes) y se ejecutó (5).
`test_nadie_construye_el_cliente_por_su_cuenta` prohíbe el patrón, no lo
corrige a posteriori.

No hace falta clave ni red: construir un cliente del SDK es local, no abre
ninguna conexión.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from ia.cliente import (  # noqa: E402
    TIMEOUT_ESTANDAR_S,
    TIMEOUT_GENERACION_S,
    crear_cliente,
    timeout_estandar,
    timeout_generacion,
)

CLAVE_FALSA = "sk-ant-no-es-una-clave-real"

# El módulo que sí puede nombrar el constructor: es el que lo envuelve.
FACHADA = "ia/cliente.py"

_CONSTRUCTOR = re.compile(r"anthropic\.Anthropic\s*\(")


def test_el_tramo_estandar_tiene_timeout():
    assert crear_cliente(CLAVE_FALSA).timeout == TIMEOUT_ESTANDAR_S


def test_el_tramo_de_generacion_es_mas_largo_pero_finito():
    """8.192 tokens de salida no caben en el tramo estándar; lo que no puede
    pasar es que "más largo" acabe significando "sin límite"."""
    assert TIMEOUT_GENERACION_S > TIMEOUT_ESTANDAR_S
    assert crear_cliente(CLAVE_FALSA, timeout_s=timeout_generacion()).timeout == TIMEOUT_GENERACION_S


def test_el_timeout_del_sdk_ya_no_es_el_que_manda():
    """El valor por defecto del SDK es 600 s de lectura. Si alguna vez un
    cliente vuelve a salir con ese número, es que no se le pasó nada."""
    for cliente in (crear_cliente(CLAVE_FALSA),
                    crear_cliente(CLAVE_FALSA, timeout_s=timeout_generacion())):
        assert cliente.timeout != 600
        assert cliente.timeout < 600


@pytest.mark.parametrize("bruto", ["", "basura", "0", "-30", "  "])
def test_una_variable_de_entorno_mal_escrita_no_deja_el_producto_sin_limite(monkeypatch, bruto):
    """El fallo peligroso no es el valor raro: es que un valor raro desactive
    el límite. Cualquier cosa que no sea un número positivo se ignora."""
    monkeypatch.setenv("ARCHMUSE_ANTHROPIC_TIMEOUT_S", bruto)
    assert timeout_estandar() == TIMEOUT_ESTANDAR_S


def test_la_variable_de_entorno_se_respeta_cuando_es_valida(monkeypatch):
    monkeypatch.setenv("ARCHMUSE_ANTHROPIC_TIMEOUT_S", "45")
    assert timeout_estandar() == 45.0
    assert crear_cliente(CLAVE_FALSA).timeout == 45.0


def test_nadie_construye_el_cliente_por_su_cuenta():
    """La red de verdad: `anthropic.Anthropic(...)` solo puede aparecer dentro
    de la fachada. Cualquier módulo nuevo que quiera hablar con Claude pasa por
    `crear_cliente` y hereda el timeout sin tener que acordarse de él."""
    culpables = []
    for ruta in sorted(RAIZ.glob("**/*.py")):
        relativa = ruta.relative_to(RAIZ).as_posix()
        if relativa.startswith(("venv/", "tests/")) or relativa == FACHADA:
            continue
        texto = ruta.read_text(encoding="utf-8", errors="replace")
        # Fuera los comentarios: explicar el patrón prohibido está permitido.
        codigo = re.sub(r"^\s*#.*$", "", texto, flags=re.M)
        if _CONSTRUCTOR.search(codigo):
            culpables.append(relativa)
    assert not culpables, (
        "estos modulos construyen el cliente sin pasar por analyzer/"
        "anthropic_cliente.py, asi que su llamada no tiene timeout: "
        + ", ".join(culpables)
    )
