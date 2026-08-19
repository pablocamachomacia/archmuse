# -*- coding: utf-8 -*-
"""TL-3 — un manifiesto, tres consumidores, y ninguna forma de que se separen.

Ejecutar:  pytest tests/test_agente_manifiesto.py

La consecuencia vinculante C1 dice que ninguna capacidad puede quedar acoplada
a la web. Un documento no puede garantizar eso; un test sí. Lo que se fija
aquí:

1. De una `Capacidad` salen los tres artefactos (herramienta de Anthropic,
   operación OpenAPI, firma programática) sin escribir su forma tres veces.
2. Los tres exponen **los mismos nombres de parámetro**, y los mismos que
   acepta la función Python real. Un manifiesto que declara `municipio` sobre
   una función que espera `nombre_municipio` no se carga en verde.
3. Esa comprobación recorre el **registro entero**, así que cubre también las
   capacidades que todavía no se han escrito.
4. La invocación programática pasa por el mismo portero que la web: valida los
   argumentos contra el manifiesto y exige un resultado con `ok`.

No hace falta red ni clave: las capacidades reales del registro son
deterministas o degradan solas.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agente import manifiesto  # noqa: E402
from agente.capacidad import Capacidad  # noqa: E402
from agente.registro import registro  # noqa: E402


def capacidad_de_prueba(**cambios):
    """Una capacidad coherente. Cada test la rompe de UNA manera."""
    def calcular(largo, ancho=1.0):
        return {"ok": True, "area": largo * ancho}

    base = dict(
        id="prueba.area",
        version="1.0.0",
        dominio="prueba",
        naturaleza="determinista",
        descripcion="Área de un rectángulo.\nSegunda línea de la descripción.",
        parametros={
            "type": "object",
            "properties": {
                "largo": {"type": "number", "description": "en metros"},
                "ancho": {"type": "number", "default": 1.0},
            },
            "required": ["largo"],
        },
        funcion=calcular,
        limitaciones=("no comprueba que el rectángulo exista en el plano",),
    )
    base.update(cambios)
    return Capacidad(**base)


# --- 1. Los tres consumidores salen de la misma declaración -----------------

def test_la_herramienta_de_anthropic_lleva_las_limitaciones_en_la_descripcion():
    """Lo que la capacidad NO comprueba viaja con ella al modelo.

    Es lo que impide que el planificador la elija creyendo que hace más de lo
    que hace, y es la materia prima del acta de procedencia.
    """
    esquema = manifiesto.esquema_anthropic(capacidad_de_prueba())
    assert esquema["name"] == "prueba__area"
    assert "NO comprueba" in esquema["description"]
    assert esquema["input_schema"]["properties"]["largo"]["type"] == "number"


def test_la_operacion_openapi_reutiliza_el_esquema_sin_traducirlo():
    """Copiar el esquema sería el sitio exacto donde los nombres se separan."""
    cap = capacidad_de_prueba()
    op = manifiesto.operacion_openapi(cap)
    cuerpo = op["requestBody"]["content"]["application/json"]["schema"]
    assert cuerpo is cap.parametros
    assert op["operationId"] == "prueba__area"      # sin puntos: es un identificador
    assert op["tags"] == ["prueba"]


def test_la_operacion_openapi_lleva_naturaleza_y_efectos():
    """OpenAPI no tiene sitio para «esto escribe un fichero», y este producto
    no puede perder ese dato al cruzar una frontera."""
    cap = capacidad_de_prueba(naturaleza="io", efectos=("escribe_fichero",))
    op = manifiesto.operacion_openapi(cap)
    assert op["x-archmuse-naturaleza"] == "io"
    assert op["x-archmuse-efectos"] == ["escribe_fichero"]
    assert op["x-archmuse-version"] == "1.0.0"


def test_la_firma_pone_los_obligatorios_primero_y_respeta_los_defectos():
    f = manifiesto.firma(capacidad_de_prueba())
    assert list(f.parameters) == ["largo", "ancho"]
    assert f.parameters["largo"].default is f.parameters["largo"].empty
    assert f.parameters["ancho"].default == 1.0


def test_un_opcional_sin_defecto_se_anota_como_opcional():
    """Una firma que promete `str` y admite `None` miente a quien la lee para
    generar un plugin."""
    from typing import Optional

    cap = capacidad_de_prueba(parametros={
        "type": "object",
        "properties": {"largo": {"type": "number"}, "nota": {"type": "string"}},
        "required": ["largo"],
    }, funcion=lambda largo, nota=None: {"ok": True})
    f = manifiesto.firma(cap)
    assert f.parameters["nota"].annotation == Optional[str]
    assert f.parameters["largo"].annotation is float


# --- 2. La invocación programática pasa por el mismo portero ---------------

def test_se_puede_invocar_por_posicion_como_una_funcion_normal():
    """Es la prueba del plugin: invocar sin HTTP, sin Flask, sin FastAPI."""
    assert manifiesto.invocar(capacidad_de_prueba(), 3.0, 2.0)["area"] == 6.0


def test_un_argumento_no_declarado_se_rechaza_igual_que_por_la_web():
    """Tres puertas, un solo portero. Si la invocación programática se saltara
    la validación, el plugin de Revit sería una vía sin control de argumentos.
    """
    with pytest.raises(TypeError):
        manifiesto.invocar(capacidad_de_prueba(), 3.0, color="rojo")


def test_un_opcional_no_pasado_no_llega_como_none():
    """Rellenar los opcionales con `None` obligaría a cada función a distinguir
    «no me lo han dicho» de «me han dicho None», que nadie mantiene bien."""
    vistos = {}

    def calcular(largo, ancho=7.0):
        vistos["ancho"] = ancho
        return {"ok": True, "area": largo * ancho}

    manifiesto.invocar(capacidad_de_prueba(funcion=calcular), 2.0)
    assert vistos["ancho"] == 7.0


def test_el_resultado_sigue_exigiendo_ok():
    cap = capacidad_de_prueba(funcion=lambda largo, ancho=1.0: "veinte metros")
    with pytest.raises(Exception):
        manifiesto.invocar(cap, 2.0)


# --- 3. La verificación, que es lo que de verdad se compra -----------------

def test_una_capacidad_coherente_no_produce_fallos():
    assert manifiesto.comprobar_coherencia(capacidad_de_prueba()) == []


def test_un_parametro_declarado_que_la_funcion_no_acepta_se_detecta():
    """EL DEFECTO QUE ESTO EXISTE PARA IMPEDIR.

    El modelo rellena el esquema declarado; la llamada muere con `TypeError`
    delante de un cliente. Sin esta comprobación, el manifiesto y la función
    pueden divergir sin que nada se ponga rojo.
    """
    cap = capacidad_de_prueba(parametros={
        "type": "object",
        "properties": {"largo": {"type": "number"}, "alto": {"type": "number"}},
        "required": ["largo"],
    })
    fallos = manifiesto.comprobar_coherencia(cap)
    assert any("alto" in f and "TypeError" in f for f in fallos), fallos


def test_un_parametro_de_la_funcion_que_el_manifiesto_calla_se_detecta():
    """Nadie puede pedirlo: ni el modelo, ni la API, ni un plugin."""
    cap = capacidad_de_prueba(parametros={
        "type": "object",
        "properties": {"largo": {"type": "number"}},
        "required": ["largo"],
    })
    fallos = manifiesto.comprobar_coherencia(cap)
    assert any("ancho" in f for f in fallos), fallos


def test_un_obligatorio_de_la_funcion_marcado_como_opcional_se_detecta():
    """Una llamada válida según el esquema fallaría al ejecutarse."""
    cap = capacidad_de_prueba(
        funcion=lambda largo, ancho: {"ok": True},
        parametros={
            "type": "object",
            "properties": {"largo": {"type": "number"}, "ancho": {"type": "number"}},
            "required": ["largo"],
        },
    )
    fallos = manifiesto.comprobar_coherencia(cap)
    assert any("ancho" in f and "obligatorio" in f for f in fallos), fallos


def test_exigir_coherencia_lanza_con_todos_los_fallos():
    cap = capacidad_de_prueba(parametros={
        "type": "object",
        "properties": {"inventado": {"type": "number"}},
        "required": ["inventado"],
    })
    with pytest.raises(manifiesto.ManifiestoIncoherente):
        manifiesto.exigir_coherencia([cap])


# --- 4. Sobre el registro real, que es lo que hace que cubra el futuro -----

def test_TODAS_las_capacidades_del_registro_son_coherentes():
    """La garantía de C1, aplicada a lo que hay y a lo que venga.

    Este test no mira una lista escrita a mano: recorre el registro, que se
    puebla por descubrimiento. Una capacidad nueva con el manifiesto torcido
    pone la suite en rojo sin que nadie tenga que acordarse de añadirla aquí.
    """
    fallos = manifiesto.comprobar_registro(registro(recargar=True))
    assert fallos == [], "\n".join(fallos)


def test_el_documento_openapi_tiene_una_ruta_por_capacidad_y_orden_estable():
    reg = registro(recargar=True)
    doc = manifiesto.documento_openapi(reg)
    assert doc["openapi"] == "3.1.0"
    assert len(doc["paths"]) == len(reg)
    rutas = list(doc["paths"])
    assert rutas == sorted(rutas), "el orden inestable rompe la caché y el diff de CI"
    assert manifiesto.documento_openapi(reg) == doc


def test_los_operationId_del_documento_son_unicos():
    """Chocan dos y el cliente TypeScript generado pierde una función."""
    doc = manifiesto.documento_openapi(registro(recargar=True))
    ids = [item["post"]["operationId"] for item in doc["paths"].values()]
    assert len(ids) == len(set(ids))


def test_una_capacidad_real_se_invoca_por_firma_sin_transporte():
    """CAD-1 en miniatura: el motor responde sin que exista una web."""
    cap = registro(recargar=True).buscar("territorial.resolver_ambito")
    assert manifiesto.invocar(cap, "Madrid")["ok"] is True
    ambiguo = manifiesto.invocar(cap, "municipio-que-no-existe-en-el-registro")
    assert ambiguo["ok"] is False and "pregunta" in ambiguo


def test_el_generador_de_openapi_no_importa_ningun_transporte():
    """Generar el documento no puede arrastrar el servidor que lo sirve."""
    fuente = (RAIZ / "agente" / "manifiesto.py").read_text(encoding="utf-8")
    for prohibido in ("import flask", "import fastapi", "from flask", "from fastapi"):
        assert prohibido not in fuente
