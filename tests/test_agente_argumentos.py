# -*- coding: utf-8 -*-
"""Validación estructural de argumentos: la frontera del sistema.

Ejecutar:  pytest tests/test_agente_argumentos.py

`Capacidad.invocar` comprobaba dos cosas —que no sobrara ninguna clave y que no
faltara ninguna obligatoria— y nada más. Un `"25 m"` donde el manifiesto dice
`number`, o un `"nave industrial"` donde dice `enum: [vivienda, local]`, entraba
en la función y salía por el otro lado convertido en un resultado con pinta de
bueno.

**Por qué importa aquí más que en otro sitio.** Los argumentos no los escribe un
programador: los rellena un modelo de lenguaje leyendo un esquema. Que se
equivoque es lo normal, no lo excepcional. Rechazarlo aquí cuesta cero tokens y
produce un mensaje que el modelo sabe corregir; dejarlo pasar produce un número
que nadie midió y que ya no se distingue de uno medido.

Lo que se fija:

1. **Lo válido sigue pasando.** Ninguna llamada legítima se rompe.
2. **Tipos, enums, rangos, longitudes, patrones y objetos anidados** se
   rechazan, y **antes** de ejecutar la función.
3. **Todos los problemas a la vez**, no el primero, y **siempre los mismos**:
   dos llamadas iguales dan el mismo mensaje.
4. **El mensaje está en castellano y dice qué argumento y qué se esperaba.**
5. **Un esquema mal escrito revienta al declarar la capacidad**, no seis meses
   después cuando el modelo por fin use esa herramienta.
6. **El rechazo llega al bucle como `ok: false`**, no como una excepción que
   tumbe la conversación.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agente import nucleo  # noqa: E402
from agente.capacidad import ArgumentosInvalidos, Capacidad  # noqa: E402
from agente.registro import Registro, registro  # noqa: E402

ESQUEMA = {
    "type": "object",
    "properties": {
        "municipio": {"type": "string", "minLength": 2},
        "superficie_m2": {"type": "number", "minimum": 0, "maximum": 100_000},
        "uso": {"type": "string", "enum": ["vivienda", "local", "garaje"]},
        "plantas": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "altura_m": {"type": "number", "exclusiveMinimum": 0},
                },
                "required": ["nombre"],
                "additionalProperties": False,
            },
        },
        "referencia": {"type": "string", "pattern": "^[0-9]{7}[A-Z]{2}$"},
    },
    "required": ["municipio"],
    "additionalProperties": False,
}


@pytest.fixture
def llamadas():
    return []


@pytest.fixture
def capacidad(llamadas):
    def _funcion(**argumentos):
        llamadas.append(argumentos)
        return {"ok": True, "recibido": argumentos}

    return Capacidad(
        id="prueba.ficha", version="1.0.0", dominio="prueba",
        naturaleza="determinista",
        descripcion="Una capacidad de mentira con un esquema de verdad.",
        parametros=ESQUEMA, funcion=_funcion,
    )


# --- 1. Lo válido sigue pasando --------------------------------------------

def test_una_llamada_valida_se_ejecuta(capacidad, llamadas):
    resultado = capacidad.invocar({
        "municipio": "Madrid", "superficie_m2": 87.4, "uso": "vivienda",
        "plantas": [{"nombre": "baja", "altura_m": 2.7}],
        "referencia": "1234567AB",
    })
    assert resultado["ok"] is True
    assert len(llamadas) == 1


def test_los_opcionales_siguen_siendo_opcionales(capacidad, llamadas):
    assert capacidad.invocar({"municipio": "Ávila"})["ok"] is True
    assert llamadas == [{"municipio": "Ávila"}]


def test_las_nueve_capacidades_reales_siguen_declarando_un_esquema_valido():
    """Compilar el esquema al declarar la capacidad no puede romper el registro
    que ya existe."""
    assert len(registro(recargar=True)) >= 1


# --- 2. Lo inválido se rechaza, y sin ejecutar -----------------------------

@pytest.mark.parametrize("argumentos, fragmento", [
    ({"municipio": 42}, "tipo texto"),
    ({"municipio": "M"}, "al menos 2"),
    ({"municipio": "Madrid", "superficie_m2": "87,4"}, "tipo número"),
    ({"municipio": "Madrid", "superficie_m2": -3}, "menor que 0"),
    ({"municipio": "Madrid", "superficie_m2": 10 ** 6}, "mayor que 100000"),
    ({"municipio": "Madrid", "uso": "nave industrial"}, "sólo admite"),
    ({"municipio": "Madrid", "referencia": "no-es-una-referencia"}, "patrón"),
    ({"municipio": "Madrid", "plantas": "baja"}, "tipo lista"),
    ({"municipio": "Madrid", "plantas": [{}, {}, {}, {}]}, "como mucho 3"),
])
def test_lo_que_el_esquema_no_admite_se_rechaza(capacidad, llamadas,
                                                argumentos, fragmento):
    with pytest.raises(ArgumentosInvalidos) as fallo:
        capacidad.invocar(argumentos)
    assert fragmento in str(fallo.value), str(fallo.value)
    assert llamadas == [], "no se puede haber ejecutado la función"


def test_lo_anidado_tambien_se_valida(capacidad, llamadas):
    """Un objeto dentro de una lista es donde un modelo se equivoca de verdad."""
    with pytest.raises(ArgumentosInvalidos) as fallo:
        capacidad.invocar({"municipio": "Madrid",
                           "plantas": [{"nombre": "baja"},
                                       {"nombre": "primera", "altura_m": "dos setenta"}]})
    mensaje = str(fallo.value)
    assert "plantas[1].altura_m" in mensaje, mensaje
    assert llamadas == []


def test_un_campo_obligatorio_de_lo_anidado_se_exige(capacidad):
    with pytest.raises(ArgumentosInvalidos) as fallo:
        capacidad.invocar({"municipio": "Madrid", "plantas": [{"altura_m": 2.7}]})
    assert "plantas[0]" in str(fallo.value)


def test_una_clave_de_mas_en_lo_anidado_se_rechaza(capacidad):
    with pytest.raises(ArgumentosInvalidos) as fallo:
        capacidad.invocar({"municipio": "Madrid",
                           "plantas": [{"nombre": "baja", "color": "azul"}]})
    assert "plantas[0]" in str(fallo.value)


# --- 3. Todos los problemas, y siempre los mismos --------------------------

def test_se_dicen_todos_los_problemas_no_el_primero(capacidad):
    """Quien corrige una llamada prefiere ver los tres a la vez, y el modelo
    además sólo reintenta una vez."""
    with pytest.raises(ArgumentosInvalidos) as fallo:
        capacidad.invocar({"municipio": 42, "superficie_m2": -1, "uso": "chalet"})
    mensaje = str(fallo.value)
    assert "3 problema(s)" in mensaje, mensaje
    for esperado in ("municipio", "superficie_m2", "uso"):
        assert esperado in mensaje


def test_el_mensaje_es_estable_entre_llamadas(capacidad):
    """Un mensaje que cambia de orden entre ejecuciones no se puede fijar en un
    test, y por tanto no se puede defender."""
    argumentos = {"municipio": 42, "superficie_m2": -1, "uso": "chalet"}
    mensajes = set()
    for _ in range(8):
        with pytest.raises(ArgumentosInvalidos) as fallo:
            capacidad.invocar(dict(argumentos))
        mensajes.add(str(fallo.value))
    assert len(mensajes) == 1


def test_lo_que_falta_y_lo_que_sobra_conservan_su_mensaje(capacidad):
    """Los dos mensajes que ya existían son mejores que los del esquema: dicen
    qué se admite y qué falta. No se sustituyen ni se dicen dos veces."""
    with pytest.raises(ArgumentosInvalidos) as falta:
        capacidad.invocar({"uso": "vivienda"})
    assert "obligatorio" in str(falta.value)
    assert "problema(s)" not in str(falta.value)

    with pytest.raises(ArgumentosInvalidos) as sobra:
        capacidad.invocar({"municipio": "Madrid", "inventado": 1})
    assert "no declarado" in str(sobra.value)


# --- 4. El mensaje se puede corregir ---------------------------------------

def test_el_mensaje_dice_el_argumento_lo_esperado_y_lo_recibido(capacidad):
    with pytest.raises(ArgumentosInvalidos) as fallo:
        capacidad.invocar({"municipio": "Madrid", "uso": "chalet"})
    mensaje = str(fallo.value)
    assert "«uso»" in mensaje
    assert "'vivienda'" in mensaje and "'garaje'" in mensaje   # lo que sí admite
    assert "'chalet'" in mensaje                              # lo que llegó


def test_un_valor_larguisimo_no_se_cita_entero(capacidad):
    with pytest.raises(ArgumentosInvalidos) as fallo:
        capacidad.invocar({"municipio": "Madrid", "superficie_m2": "x" * 5_000})
    assert len(str(fallo.value)) < 1_000


# --- 5. Un esquema mal escrito revienta al declarar ------------------------

def test_un_esquema_invalido_no_llega_a_registrarse():
    with pytest.raises(Exception) as fallo:
        Capacidad(
            id="prueba.rota", version="1.0.0", dominio="prueba",
            naturaleza="determinista", descripcion="Esquema imposible.",
            parametros={"type": "object",
                        "properties": {"n": {"type": "no_existe_este_tipo"}}},
            funcion=lambda **_k: {"ok": True},
        )
    assert "no_existe_este_tipo" in str(fallo.value)


# --- 6. El bucle lo recibe como `ok: false`, no como una excepción --------

class BloqueHerramienta:
    type = "tool_use"

    def __init__(self, nombre, entrada):
        self.name = nombre
        self.input = entrada
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


def test_un_argumento_mal_tipado_vuelve_al_modelo_como_error_corregible(
        capacidad, llamadas):
    """Que el modelo se equivoque rellenando un esquema es normal. Lo que no
    puede pasar es que tumbe la conversación ni que el error se lea como dato."""
    cliente = ClienteGuionizado(
        RespuestaFalsa(BloqueHerramienta("prueba__ficha", {"municipio": 42})),
        RespuestaFalsa(BloqueTexto("No he podido: el municipio tiene que ser texto.")),
    )
    respuesta = nucleo.ejecutar("dame la ficha", cliente,
                                reg=Registro((capacidad,)))

    assert respuesta.parada == "fin"
    assert len(respuesta.pasos) == 1
    paso = respuesta.pasos[0]
    assert paso.ok is False
    assert paso.resultado["error"] == "argumentos_invalidos"
    assert "tipo texto" in paso.resultado["detalle"]
    assert llamadas == []

    # Y el modelo lo recibió marcado como error, no como un resultado más.
    devuelto = cliente.llamadas[1]["messages"][2]["content"][0]
    assert devuelto["is_error"] is True
