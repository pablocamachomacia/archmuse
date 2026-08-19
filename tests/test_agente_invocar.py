# -*- coding: utf-8 -*-
"""CAD-1 — la prueba del plugin, ejecutada de verdad.

Ejecutar:  pytest tests/test_agente_invocar.py

`CAD-3`, el complemento real de Revit, está aplazado con motivo. El
aplazamiento sólo es reversible si la arquitectura no se cierra mientras tanto,
y eso no se garantiza con un documento: se garantiza con un ejecutable que
invoca el motor **sin HTTP, sin Flask y sin FastAPI**, y con tests que lo
vigilan.

Lo que se fija aquí:

1. Una capacidad real responde por la línea de órdenes con el mismo resultado
   que por cualquier otra puerta — mismo manifiesto, mismo portero.
2. Los argumentos del CLI se **derivan** del esquema: añadir una capacidad no
   obliga a tocar `agente/invocar.py`. Si algún día hubiera que tocarlo, la
   propiedad que compra `TL-3` se habría perdido.
3. `ok: false` sale con código 1 y **conserva la pregunta**. Un guion que lo
   tratara como excepción perdería justo lo que hace útil la respuesta.
4. El CLI no importa transporte, y `--comprobar` deja la coherencia de los
   manifiestos al alcance de un solo comando.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agente import invocar as cli  # noqa: E402
from agente.manifiesto import invocar as invocar_por_firma  # noqa: E402
from agente.registro import registro  # noqa: E402


def correr(capsys, *argv):
    codigo = cli.ejecutar(list(argv))
    return codigo, capsys.readouterr()


# --- 1. La misma respuesta que por cualquier otra puerta -------------------

def test_una_capacidad_real_responde_desde_la_linea_de_ordenes(capsys):
    codigo, salida = correr(capsys, "territorial.resolver_ambito", "--municipio", "Madrid")
    resultado = json.loads(salida.out)
    assert codigo == 0
    assert resultado["ok"] is True
    assert resultado["codigo_municipio"] == "28079"


def test_el_cli_devuelve_exactamente_lo_mismo_que_la_invocacion_programatica(capsys):
    """Si las dos puertas divergieran, una de ellas estaría traduciendo — y una
    traducción es el sitio donde los contratos se separan."""
    cap = registro(recargar=True).buscar("territorial.resolver_ambito")
    directo = invocar_por_firma(cap, "Madrid")
    _, salida = correr(capsys, "territorial.resolver_ambito", "--municipio", "Madrid")
    assert json.loads(salida.out) == json.loads(json.dumps(directo, default=str))


# --- 2. Nada se escribe a mano --------------------------------------------

def test_los_argumentos_salen_del_esquema_y_no_de_una_lista_escrita():
    """El parser de una capacidad se genera de su firma.

    La prueba: una capacidad inventada, que este fichero no conoce, obtiene sus
    opciones sin que nadie las declare.
    """
    from agente.capacidad import Capacidad

    cap = Capacidad(
        id="inventada.medir", version="1.0.0", dominio="inventada",
        naturaleza="determinista", descripcion="Mide algo.",
        parametros={
            "type": "object",
            "properties": {"largo": {"type": "number"}, "unidad": {"type": "string"}},
            "required": ["largo"],
        },
        funcion=lambda largo, unidad="m": {"ok": True, "valor": largo, "unidad": unidad},
    )
    args = cli._parser_de(cap).parse_args(["--largo", "3.5"])
    assert args.largo == "3.5" and args.unidad is None


def test_el_texto_de_la_consola_se_convierte_al_tipo_del_manifiesto():
    assert cli._convertir("3.5", float) == 3.5
    assert cli._convertir("7", int) == 7
    assert cli._convertir("si", bool) is True
    assert cli._convertir('{"a": 1}', dict) == {"a": 1}


def test_un_numero_que_no_lo_es_llega_como_texto_y_decide_la_capacidad():
    """Forzarlo aquí a un número inventado sería el repliegue silencioso que
    este producto persigue en todas partes."""
    assert cli._convertir("veinte", float) == "veinte"


def test_un_opcional_no_pasado_no_pisa_el_defecto_de_la_funcion(capsys):
    codigo, salida = correr(capsys, "territorial.resolver_ambito", "--municipio", "Madrid")
    assert codigo == 0 and json.loads(salida.out)["ok"] is True


# --- 3. `ok: false` no es una excepción -----------------------------------

def test_ok_false_sale_con_codigo_1_y_conserva_la_pregunta(capsys):
    codigo, salida = correr(capsys, "territorial.resolver_ambito",
                            "--municipio", "Municipio-Que-No-Existe")
    resultado = json.loads(salida.out)
    assert codigo == 1
    assert resultado["ok"] is False
    assert "pregunta" in resultado and resultado["pregunta"]


def test_una_capacidad_desconocida_se_rechaza_con_la_lista_de_las_que_hay(capsys):
    codigo, salida = correr(capsys, "no.existe")
    assert codigo == 2
    assert "territorial.resolver_ambito" in salida.err


def test_un_argumento_obligatorio_que_falta_no_ejecuta_nada(capsys):
    with pytest.raises(SystemExit):
        cli.ejecutar(["territorial.resolver_ambito"])


# --- 4. El catálogo, el contrato y la coherencia, a un comando ------------

def test_sin_argumentos_enseña_lo_que_archmuse_sabe_hacer(capsys):
    codigo, salida = correr(capsys)
    assert codigo == 0
    assert "territorial.resolver_ambito@1.0.0" in salida.out
    assert "NO comprueba" in salida.out       # lo que no hace viaja con lo que hace


def test_openapi_sale_del_mismo_registro(capsys):
    codigo, salida = correr(capsys, "--openapi")
    doc = json.loads(salida.out)
    assert codigo == 0
    assert len(doc["paths"]) == len(registro(recargar=True))


def test_comprobar_confirma_que_los_tres_consumidores_casan(capsys):
    codigo, salida = correr(capsys, "--comprobar")
    assert codigo == 0
    assert "coinciden" in salida.out


def test_el_cli_no_importa_ningun_transporte():
    fuente = (RAIZ / "agente" / "invocar.py").read_text(encoding="utf-8")
    for prohibido in ("import flask", "import fastapi", "from flask", "from fastapi",
                      "import requests", "import http.client"):
        assert prohibido not in fuente
