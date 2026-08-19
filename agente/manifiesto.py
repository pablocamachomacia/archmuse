# -*- coding: utf-8 -*-
"""Un manifiesto, tres consumidores generados (tarea `TL-3`).

**Qué compra esta tarea, y por qué antes que casi todo lo demás.** La
consecuencia vinculante C1 del paso 0 de alineación dice que ninguna capacidad
puede quedar acoplada a la web: el día que ArchMuse viva dentro de Revit, de un
servidor MCP o de un `python -m`, el motor no puede reescribirse. Esa promesa
es hoy una frase en un documento. Aquí se convierte en algo que una prueba
puede romper.

De **una sola** declaración de `Capacidad` salen los tres artefactos que
necesita cada superficie por la que ArchMuse puede ser invocado:

| Consumidor | Función | Quién lo usa |
|---|---|---|
| Herramienta de Anthropic | `esquema_anthropic` | el planificador (`AG-1`) y el bucle actual |
| Operación OpenAPI | `operacion_openapi`, `documento_openapi` | la API (`INF-5`) y el cliente TypeScript generado (`INF-6`) |
| Firma programática | `firma`, `invocar` | el CLI (`CAD-1`), el plugin de Revit (`CAD-3`), MCP (`TL-7`) |

**La verificación es el producto, no los generadores.** Escribir tres
generadores es fácil; lo difícil es que no se separen. `comprobar_coherencia`
compara los tres contra la **función Python real** y falla si alguno se
desvía. Hoy nada impide declarar un parámetro `municipio` en el esquema y que
la función lo llame `nombre_municipio`: el modelo rellenaría el esquema
declarado y la llamada moriría con un `TypeError` delante de un cliente. Eso
deja de ser posible con `tests/test_agente_manifiesto.py`, que recorre el
registro entero — de modo que la garantía cubre también las capacidades que
todavía no existen.

**Lo que este módulo NO hace, a propósito:** no importa `fastapi`, ni `flask`,
ni ningún transporte. Genera *documentos*. Quien los sirva es asunto de la capa
de API, y esa frontera la vigila
`tests/test_agente_nucleo.py::test_ninguna_capacidad_sabe_de_transporte`.
"""
from __future__ import annotations

import inspect
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .capacidad import Capacidad

#: JSON Schema -> anotación de Python. Deliberadamente pequeño: el esquema de
#: una capacidad describe argumentos de una llamada, no un modelo de dominio.
TIPOS = {
    "string": str,
    "number": float,
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}

#: Prefijo de las extensiones OpenAPI que llevan lo que el estándar no tiene
#: sitio para expresar y este producto no puede perder: qué naturaleza tiene la
#: capacidad, qué efectos declara y qué NO comprueba.
EXT = "x-archmuse-"


class ManifiestoIncoherente(Exception):
    """El esquema declarado y la función real no dicen lo mismo.

    Se levanta al comprobar, no al ejecutar: el objetivo es que esto lo
    encuentre CI y no un arquitecto con un plano a medias.
    """


# ---------------------------------------------------------------------------
# 1. Herramienta de Anthropic
# ---------------------------------------------------------------------------

def esquema_anthropic(cap: Capacidad) -> Dict[str, Any]:
    """El manifiesto como herramienta de la API de Anthropic.

    Delega en `Capacidad.esquema()` en vez de duplicarlo: si el día de mañana
    la descripción incorpora algo más (las limitaciones ya van dentro), este
    módulo no puede quedarse atrás sin que nadie se entere.
    """
    return cap.esquema()


# ---------------------------------------------------------------------------
# 2. Operación OpenAPI
# ---------------------------------------------------------------------------

def ruta_http(cap: Capacidad) -> str:
    """La ruta bajo la que se sirve la capacidad. Un solo sitio que lo decide."""
    return "/capacidades/" + cap.id


def operacion_openapi(cap: Capacidad) -> Dict[str, Any]:
    """La capacidad como operación `POST` de OpenAPI 3.1.

    El cuerpo de la petición **es** `cap.parametros`, sin copiar ni traducir:
    cualquier traducción es un sitio donde los nombres pueden separarse.

    `operationId` es el nombre traducido para herramienta, no el `id` con
    puntos, porque los generadores de cliente lo convierten en identificador de
    función y un punto ahí no es válido en ningún lenguaje.
    """
    descripcion = cap.descripcion.strip()
    if cap.limitaciones:
        descripcion += "\n\nNO comprueba: " + "; ".join(cap.limitaciones) + "."
    operacion: Dict[str, Any] = {
        "operationId": cap.nombre_de_herramienta,
        "summary": descripcion.split("\n")[0].strip(),
        "description": descripcion,
        "tags": [cap.dominio],
        EXT + "version": cap.version,
        EXT + "naturaleza": cap.naturaleza,
        EXT + "efectos": list(cap.efectos),
        EXT + "limitaciones": list(cap.limitaciones),
        "requestBody": {
            "required": bool(cap.parametros.get("required")),
            "content": {"application/json": {"schema": cap.parametros}},
        },
        "responses": {
            "200": {
                "description": (
                    "Resultado estructurado. `ok: false` NO es un error de "
                    "transporte: es una respuesta legítima que dice qué falta "
                    "o qué no se ha podido determinar."
                ),
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["ok"],
                            "properties": {"ok": {"type": "boolean"}},
                        }
                    }
                },
            },
            "400": {"description": "Argumentos que el manifiesto no declara."},
        },
    }
    if cap.referencia_normativa:
        operacion[EXT + "referencia_normativa"] = cap.referencia_normativa
    return operacion


def documento_openapi(capacidades, *, titulo: str = "ArchMuse — capacidades",
                      version: str = "0.1.0") -> Dict[str, Any]:
    """El documento OpenAPI completo del registro, en orden estable.

    Orden estable porque de aquí sale el cliente TypeScript (`INF-6`) y un
    documento que cambia de orden entre procesos produce un diff en cada
    ejecución de CI, que es la forma más rápida de que nadie mire los diffs.
    """
    paths: Dict[str, Any] = {}
    for cap in sorted(capacidades, key=lambda c: c.id):
        paths[ruta_http(cap)] = {"post": operacion_openapi(cap)}
    return {
        "openapi": "3.1.0",
        "info": {
            "title": titulo,
            "version": version,
            "description": (
                "Generado de los manifiestos de `agente/herramientas/`. No se "
                "edita a mano: la fuente es la declaración de cada `Capacidad`."
            ),
        },
        "paths": paths,
    }


# ---------------------------------------------------------------------------
# 3. Firma programática
# ---------------------------------------------------------------------------

def _anotacion(esquema: Mapping[str, Any], *, opcional: bool = False) -> Any:
    """Tipo Python de una propiedad del esquema, o `Any` si no se sabe.

    `Any` es una respuesta legítima: un esquema con `anyOf` o sin `type` no se
    fuerza a un tipo inventado — es la misma regla que rige el corpus.

    `opcional` marca los parámetros que el esquema no exige: se anotan como
    `Optional[...]` porque su valor por defecto es `None`, y una firma que
    promete `str` y admite `None` miente a quien la lee para generar un
    plugin.
    """
    tipo = esquema.get("type")
    if isinstance(tipo, list):
        sin_null = [t for t in tipo if t != "null"]
        base = TIPOS.get(sin_null[0], Any) if len(sin_null) == 1 else Any
    elif isinstance(tipo, str):
        base = TIPOS.get(tipo, Any)
    else:
        base = Any
    if base is Any:
        return Any
    if opcional or (isinstance(tipo, list) and "null" in tipo):
        return Optional[base]
    return base


def firma(cap: Capacidad) -> inspect.Signature:
    """La firma de invocación programática, derivada del **esquema**.

    Es lo que hace que un CLI, un plugin o un servidor MCP puedan invocar la
    capacidad sin conocer su código: preguntan por la firma y rellenan.
    Obligatorios primero y sin valor por defecto; opcionales después, con el
    `default` del esquema si lo declara y `None` si no.
    """
    propiedades: Dict[str, Any] = dict(cap.parametros.get("properties") or {})
    obligatorios: List[str] = list(cap.parametros.get("required") or [])
    parametros: List[inspect.Parameter] = []
    for nombre in obligatorios:
        parametros.append(inspect.Parameter(
            nombre, inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=_anotacion(propiedades.get(nombre) or {}),
        ))
    for nombre, esquema in propiedades.items():
        if nombre in obligatorios:
            continue
        parametros.append(inspect.Parameter(
            nombre, inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=esquema.get("default", None),
            annotation=_anotacion(esquema, opcional="default" not in esquema),
        ))
    return inspect.Signature(parametros, return_annotation=Dict[str, Any])


def invocar(cap: Capacidad, *args: Any, autorizaciones: Any = None,
            **kwargs: Any) -> Dict[str, Any]:
    """Invocación programática por firma: `invocar(cap, "Madrid")`.

    Liga los posicionales a los nombres del **manifiesto** y delega en
    `Capacidad.invocar`, de modo que la validación de argumentos y el contrato
    de resultado (`dict` con `ok`) son exactamente los mismos que por la web o
    por la API de herramientas. Tres puertas, un solo portero.

    Los argumentos opcionales que el llamante no pasa **no se envían**: pasarlos
    como `None` obligaría a cada función a distinguir "no me lo han dicho" de
    "me han dicho None", que es una distinción que nadie mantiene bien. Por eso
    no se llama a `apply_defaults()`.

    `autorizaciones` es **de palabra clave y no forma parte del manifiesto**:
    no es un argumento de la capacidad, es quién permite sus efectos. Sin ellas,
    una capacidad con efectos declarados se rechaza — fail-closed, igual que por
    cualquier otra puerta.
    """
    ligado = firma(cap).bind(*args, **kwargs)
    return cap.invocar(dict(ligado.arguments), autorizaciones)


# ---------------------------------------------------------------------------
# La verificación: que los tres digan lo mismo que la función real
# ---------------------------------------------------------------------------

def _parametros_de_la_funcion(cap: Capacidad) -> Tuple[List[str], List[str]]:
    """(todos, obligatorios) de la función Python, ignorando `*args`/`**kwargs`."""
    sig = inspect.signature(cap.funcion)
    todos, obligatorios = [], []
    for nombre, p in sig.parameters.items():
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        todos.append(nombre)
        if p.default is inspect.Parameter.empty:
            obligatorios.append(nombre)
    return todos, obligatorios


def comprobar_coherencia(cap: Capacidad) -> List[str]:
    """Devuelve los desacuerdos entre esquema, OpenAPI, firma y función real.

    Lista vacía = los cuatro dicen lo mismo. Se devuelven todos los fallos y no
    el primero: quien arregla un manifiesto quiere la lista, no un juego de las
    veinte preguntas.
    """
    fallos: List[str] = []
    del_esquema = list((cap.parametros.get("properties") or {}))
    obligatorios_esquema = list(cap.parametros.get("required") or [])

    de_la_funcion, obligatorios_funcion = _parametros_de_la_funcion(cap)

    sobran = sorted(set(del_esquema) - set(de_la_funcion))
    if sobran:
        fallos.append(
            "%s: el manifiesto declara %s, que la función %s no acepta. El modelo "
            "rellenaría un argumento que revienta la llamada con TypeError."
            % (cap.id, sobran, cap.funcion.__name__)
        )
    faltan = sorted(set(de_la_funcion) - set(del_esquema))
    if faltan:
        fallos.append(
            "%s: la función acepta %s y el manifiesto no lo declara: nadie puede "
            "pedirlo, ni el modelo ni un plugin." % (cap.id, faltan)
        )
    sin_defecto = sorted(set(obligatorios_funcion) - set(obligatorios_esquema)
                         - set(faltan) - set(sobran))
    if sin_defecto:
        fallos.append(
            "%s: %s no tiene valor por defecto en la función pero el manifiesto no "
            "lo marca como obligatorio: una llamada válida según el esquema fallaría."
            % (cap.id, sin_defecto)
        )

    if "autorizaciones" in del_esquema:
        fallos.append(
            "%s: declara un parámetro llamado «autorizaciones», que choca con el "
            "argumento de palabra clave con el que se conceden los efectos en "
            "`manifiesto.invocar`. Renómbralo." % cap.id)

    # Los tres consumidores, contra el esquema.
    de_anthropic = list((esquema_anthropic(cap)["input_schema"].get("properties") or {}))
    cuerpo = operacion_openapi(cap)["requestBody"]["content"]["application/json"]["schema"]
    de_openapi = list(cuerpo.get("properties") or {})
    de_la_firma = list(firma(cap).parameters)
    for nombre, vistos in (("herramienta de Anthropic", de_anthropic),
                           ("operación OpenAPI", de_openapi),
                           ("firma programática", de_la_firma)):
        if sorted(vistos) != sorted(del_esquema):
            fallos.append(
                "%s: la %s expone %s y el manifiesto declara %s. Los consumidores se "
                "han separado: es exactamente lo que C1 prohíbe."
                % (cap.id, nombre, sorted(vistos), sorted(del_esquema))
            )
    return fallos


def comprobar_registro(capacidades) -> List[str]:
    """`comprobar_coherencia` sobre el registro entero, en orden estable."""
    fallos: List[str] = []
    for cap in sorted(capacidades, key=lambda c: c.id):
        fallos.extend(comprobar_coherencia(cap))
    return fallos


def exigir_coherencia(capacidades) -> None:
    """Lo mismo, pero lanzando. Para arrancar un proceso fail-closed."""
    fallos = comprobar_registro(capacidades)
    if fallos:
        raise ManifiestoIncoherente("\n".join(fallos))
