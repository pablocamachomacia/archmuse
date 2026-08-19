# -*- coding: utf-8 -*-
"""Contexto largo: recortar lo que ve el modelo sin abrir un hueco que rellene.

Ejecutar:  pytest tests/test_agente_recorte.py

Un resultado de herramienta grande —un DXF de cuarenta recintos leído entero—
se come el contexto de la conversación y hace fallar a las herramientas
siguientes por una razón que no tiene que ver con lo que se pidió. Es el fallo
más caro de un agente porque no se ve venir y aparece con el plano del cliente.

Lo que este fichero fija son las cuatro cosas que hacen que recortar sea
seguro, no que sea eficaz:

1. **Lo que cabe no se toca.** El camino normal devuelve el valor idéntico y
   sin ninguna nota.
2. **Lo recortado sigue siendo JSON válido y no pierde ninguna clave.** Cortar
   la cadena por el carácter N produce un JSON roto, y un modelo que recibe un
   JSON roto improvisa.
3. **El recorte se declara donde el modelo lo lee**, y también viaja a la
   `Respuesta`. Un recorte silencioso no se distingue de un dato inexistente.
4. **El original no se toca.** `PasoEjecutado.resultado` guarda el resultado
   íntegro, y es contra él contra lo que `respaldo.py` comprueba las cifras.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agente import nucleo, recorte  # noqa: E402
from agente.capacidad import Capacidad  # noqa: E402
from agente.registro import Registro  # noqa: E402


# --- 1. Lo que cabe no se toca ---------------------------------------------

def test_lo_que_cabe_vuelve_identico_y_sin_notas():
    valor = {"ok": True, "superficie_m2": 87.4, "recintos": ["salón", "baño"]}
    salida, notas = recorte.recortar(valor)
    assert salida is valor
    assert notas == ()


def test_el_camino_normal_no_anade_la_clave_de_recorte():
    salida, _ = recorte.recortar({"ok": True, "valor": 25})
    assert recorte.CLAVE_RECORTE not in salida


# --- 2. Sigue siendo JSON válido y no pierde claves ------------------------

def test_una_lista_enorme_se_acorta_y_el_resultado_sigue_siendo_json():
    valor = {"ok": True, "fuente": "BOE-A-2006-11637",
             "recintos": [{"id": i, "area": i * 1.5} for i in range(5000)]}
    salida, notas = recorte.recortar(valor, limite=2_000)

    crudo = json.dumps(salida, ensure_ascii=False)
    assert json.loads(crudo) == salida          # válido de ida y vuelta
    assert len(crudo) <= 2_000 or notas         # cabe, o se dice que no
    assert salida["ok"] is True                 # `ok` intacto
    assert salida["fuente"] == "BOE-A-2006-11637"
    assert set(valor) <= set(salida)            # ninguna clave desaparecida
    assert notas


def test_una_cadena_enorme_se_corta_con_la_marca_puesta():
    valor = {"ok": True, "literal": "x" * 50_000}
    salida, notas = recorte.recortar(valor, limite=3_000)
    assert salida["literal"].endswith(")")
    assert "recortado" in salida["literal"]
    assert len(salida["literal"]) < 50_000
    assert notas


def test_ninguna_clave_desaparece_ni_en_lo_anidado():
    valor = {"ok": False, "error": "sin_cobertura",
             "detalle": {"materia": "acústica", "notas": ["n"] * 3_000}}
    salida, _ = recorte.recortar(valor, limite=1_000)
    assert salida["ok"] is False
    assert salida["error"] == "sin_cobertura"
    assert salida["detalle"]["materia"] == "acústica"


# --- 3. El recorte se declara donde el modelo lo lee -----------------------

def test_el_resultado_recortado_lleva_el_aviso_dentro():
    """Ponerlo sólo en la traza no serviría: quien tiene que no rellenar el
    hueco es el modelo, y el modelo lee el resultado."""
    valor = {"ok": True, "filas": list(range(10_000))}
    salida, notas = recorte.recortar(valor, limite=1_500)
    assert recorte.CLAVE_RECORTE in salida
    assert "No supongas" in salida[recorte.CLAVE_RECORTE]["aviso"]
    assert salida[recorte.CLAVE_RECORTE]["cortes"] == list(notas)


def test_las_notas_dicen_donde_se_corto():
    valor = {"ok": True, "recintos": [{"nombre": "n%d" % i} for i in range(9_000)]}
    _, notas = recorte.recortar(valor, limite=1_500)
    assert any("recintos" in n for n in notas)


def test_un_valor_que_no_es_un_dict_tambien_se_marca():
    salida, notas = recorte.recortar(["y" * 400] * 500, limite=1_000)
    assert recorte.CLAVE_RECORTE in salida
    assert notas


# --- 4. El original no se toca ---------------------------------------------

def _capacidad_grande():
    def _leer(**_kwargs):
        return {"ok": True, "recintos": [{"id": i, "area_m2": 10.5}
                                         for i in range(4_000)]}

    return Capacidad(
        id="prueba.leer_muchos_recintos",
        version="1.0.0",
        dominio="prueba",
        naturaleza="determinista",
        descripcion="Devuelve muchos recintos, para probar el recorte.",
        parametros={"type": "object", "properties": {}, "required": []},
        funcion=_leer,
    )


class BloqueHerramienta:
    type = "tool_use"

    def __init__(self, nombre):
        self.name = nombre
        self.input = {}
        self.id = "tu_1"


class BloqueTexto:
    type = "text"

    def __init__(self, texto):
        self.text = texto


class RespuestaFalsa:
    def __init__(self, *bloques):
        self.content = list(bloques)


class ClienteGuionizado:
    def __init__(self, *respuestas):
        self._respuestas = list(respuestas)
        self.llamadas = []
        self.messages = self

    def create(self, **kwargs):
        self.llamadas.append(kwargs)
        return self._respuestas.pop(0) if self._respuestas else RespuestaFalsa(
            BloqueTexto("hecho"))


def test_el_modelo_ve_el_recorte_y_la_traza_guarda_el_original():
    capacidad = _capacidad_grande()
    reg = Registro((capacidad,))
    cliente = ClienteGuionizado(
        RespuestaFalsa(BloqueHerramienta("prueba.leer_muchos_recintos")),
        RespuestaFalsa(BloqueTexto("Listo.")),
    )

    respuesta = nucleo.ejecutar("dame los recintos", cliente, reg=reg,
                                max_caracteres_por_resultado=2_000)

    # Lo que se le mandó al modelo cabe en el tope.
    resultado_enviado = cliente.llamadas[1]["messages"][2]["content"][0]["content"]
    assert len(resultado_enviado) <= 2_000
    assert recorte.CLAVE_RECORTE in resultado_enviado

    # Y el original está entero en la traza: 4.000 recintos, no 40.
    assert len(respuesta.pasos) == 1
    assert len(respuesta.pasos[0].resultado["recintos"]) == 4_000
    assert respuesta.recortes


def test_sin_resultados_grandes_no_hay_recortes():
    def _pequeno(**_kwargs):
        return {"ok": True, "valor": 25}

    capacidad = Capacidad(
        id="prueba.pequena", version="1.0.0", dominio="prueba",
        naturaleza="determinista", descripcion="Devuelve poco.",
        parametros={"type": "object", "properties": {}, "required": []},
        funcion=_pequeno,
    )
    cliente = ClienteGuionizado(
        RespuestaFalsa(BloqueHerramienta("prueba.pequena")),
        RespuestaFalsa(BloqueTexto("El valor es 25.")),
    )
    respuesta = nucleo.ejecutar("dame el valor", cliente,
                                reg=Registro((capacidad,)))
    assert respuesta.recortes == ()
    assert respuesta.fundamentada


# --- 5. Cuando ya no cabe la conversación entera ---------------------------

def test_si_el_historial_no_cabe_se_para_antes_de_llamar():
    """Pagar una llamada para enterarse de que no cabía es la peor forma de
    enterarse; y lo hecho hasta ahí se conserva."""
    capacidad = _capacidad_grande()
    cliente = ClienteGuionizado(
        RespuestaFalsa(BloqueHerramienta("prueba.leer_muchos_recintos")),
        RespuestaFalsa(BloqueTexto("no debería llegarse aquí")),
    )
    respuesta = nucleo.ejecutar(
        "dame los recintos", cliente, reg=Registro((capacidad,)),
        max_caracteres_por_resultado=50_000, max_contexto=1_000,
    )

    # La primera llamada cabe (el historial sólo trae la intención); la segunda
    # ya no, así que no se hace.
    assert len(cliente.llamadas) == 1
    assert respuesta.parada == "contexto_agotado"
    assert any("se paró antes" in r for r in respuesta.recortes)
    # Y el trabajo hecho no se tira.
    assert len(respuesta.pasos) == 1
    assert respuesta.pasos[0].ok


def test_cabe_el_historial_es_un_si_o_un_no_sin_efectos():
    assert recorte.cabe_el_historial([{"role": "user", "content": "hola"}])
    assert not recorte.cabe_el_historial(
        [{"role": "user", "content": "x" * 500}], limite=100)
