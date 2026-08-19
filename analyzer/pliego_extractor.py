# -*- coding: utf-8 -*-
"""Extracción por IA de parámetros de un pliego de concurso, en PDF.

PRD: `docs/prd/2026-08-15-extractor-parametros-pliego.md`. Único punto de
contacto con Claude para esta capacidad — mismo principio que
`extraccion/interprete.py`/`analyzer/ai_analyst.py`: todo lo demás (guardar,
servir por HTTP, mostrar en la SPA) es determinista.

**Salida: `dict[str, Hecho]`** (`analyzer/hechos.py`), no un esquema de
confianza propio — es el mismo problema (¿qué tan seguro estoy de este dato,
y por qué?) que ya resolvieron CAP-1..5. `tipo` de cada `Hecho` es siempre
`"declarado"` (el pliego lo dice, no se deriva ni se observa) y
`criterio_declarado` guarda la cita literal del texto — mismo papel que
`valor_citado` en `extraccion/interprete.py`.

**PDF nativo, no texto pre-extraído.** Se manda el PDF entero a Claude como
bloque `document` en vez de pasarlo por `pypdf` (como hace
`ingesta/fuentes/codigotecnico.py`): la pieza más valiosa de un pliego para
esto —`mix_tipologias`— casi siempre vive en una tabla, y la extracción de
texto plano rompe el alineamiento de columnas. Es una llamada por pliego, no
en bucle, así que el coste mayor del PDF completo es aceptable (§9 del PRD).

**Determinismo del esquema**: `tool_choice` forzado contra un JSON Schema
cerrado (mismo mecanismo que `extraccion/interprete.py`). Los enums de
`tipologia_edificio`/`regimen_proteccion` son catálogos cerrados pequeños,
escritos aquí una vez — no existe un módulo `normativa.*` del que derivarlos
todavía (a diferencia de los enums de `extraccion/interprete.py`, construidos
desde `normativa.catalogos`/`normativa.condiciones`/`normativa.modelo`).

Este módulo NO decide si el proyecto cumple el pliego (verificación
determinista) ni empuja nada al generador — eso es un PRD aparte, todavía sin
aprobar.
"""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    import anthropic
except ImportError:  # pragma: no cover - mismo patrón que ai_analyst.py
    anthropic = None

from ia.cliente import crear_cliente

from .hechos import ALTA, BAJA, CONFIANZAS, KNOWN, MEDIA, UNKNOWN, Hecho, Motivo

from ia import modelos

# El modelo se resuelve en `ia/modelos.py` por perfil de tarea, y no se
# escribe aquí: era la misma constante repetida en seis módulos.
MODEL = modelos.para("interpretacion")

NOMBRE_HERRAMIENTA = "registrar_parametros_pliego"

# Catálogos cerrados. `tipologia_edificio` reutiliza tal cual las opciones ya
# existentes en `static/app.js::renderGenerarForm` (formSelect "Tipología")
# para que un valor extraído del pliego sea, sin conversión, un valor válido
# de ese mismo formulario.
TIPOLOGIAS_EDIFICIO = ("plurifamiliar", "unifamiliar", "rehabilitacion")
REGIMENES_PROTECCION = ("VPP", "VPPA", "libre")

#: (nombre, unidad, json-schema del valor) — campos de valor único.
_CAMPOS_ESCALARES: List[tuple] = [
    ("municipio", "", {"type": "string"}),
    ("parcela", "", {"type": "string"}),
    ("referencia_catastral", "", {"type": "string"}),
    ("num_viviendas_minimo", "viviendas", {"type": "integer"}),
    ("num_viviendas_maximo", "viviendas", {"type": "integer"}),
    ("edificabilidad_maxima_m2", "m²", {"type": "number"}),
    ("altura_maxima_plantas", "plantas", {"type": "integer"}),
    ("pem_maximo_euros", "€", {"type": "number"}),
    ("ratio_construido_util_max", "", {"type": "number"}),
    ("tipologia_edificio", "", {"type": "string", "enum": list(TIPOLOGIAS_EDIFICIO)}),
    ("regimen_proteccion", "", {"type": "string", "enum": list(REGIMENES_PROTECCION)}),
    ("parking_plazas_por_vivienda", "plazas/vivienda", {"type": "number"}),
    # Texto libre a propósito: un pliego expresa esto de formas demasiado
    # distintas ("obligatorio, 1 por vivienda", "opcional, mínimo 4 m²") para
    # forzarlo a un booleano sin perder la condición real.
    ("trasteros", "", {"type": "string"}),
    ("porcentaje_accesibilidad", "%", {"type": "number"}),
]

#: (nombre, unidad, json-schema de cada elemento) — campos de lista de texto.
_CAMPOS_LISTA: List[tuple] = [
    ("normativa_aplicable", "", {"type": "string"}),
    ("criterios_sostenibilidad", "", {"type": "string"}),
]

_NOMBRES_CAMPOS = (
    [n for n, _, _ in _CAMPOS_ESCALARES] + [n for n, _, _ in _CAMPOS_LISTA] + ["mix_tipologias"]
)

SYSTEM_PROMPT = """Eres un asistente que ayuda a un arquitecto a leer el pliego de \
condiciones de un concurso de vivienda (público o privado) y extraer los parámetros \
que fijará como restricciones de diseño. El texto del pliego es la única fuente de \
verdad: nunca completes un dato con lo que "suele" pedir un pliego de este tipo.

Reglas estrictas, sin excepción:

1. Un campo solo tiene "encontrado": true si el pliego lo declara literalmente. Si no \
   aparece, "encontrado": false y NUNCA rellenes "valor" — ni siquiera con un valor \
   típico o plausible.
2. "cita" debe ser un fragmento copiado literalmente del pliego, no un resumen ni una \
   paráfrasis — quien lo lea debe poder localizar la frase en el documento original.
3. Si el pliego da un rango (p. ej. "entre 20 y 30 viviendas"), usa los dos campos \
   mínimo/máximo que correspondan — nunca promedies ni elijas un punto intermedio \
   inventado.
4. Si tienes cualquier duda razonable sobre si un dato es el que se pide (unidades \
   ambiguas, cifra que podría referirse a otra cosa), baja "confianza" a "Media" o \
   "Baja" y explica la duda en "cita" — nunca subas la confianza para parecer más útil.
5. Si el documento que se te ha dado no parece el pliego de condiciones de un \
   concurso, marca "no_es_pliego": true y deja el resto de campos con \
   "encontrado": false — no fuerces una lectura sobre un documento equivocado.
6. "mix_tipologias" recoge solo las filas que el pliego declara explícitamente (p. ej. \
   una tabla de tipologías con porcentaje y superficie útil); una fila sin porcentaje \
   citado no se añade.
7. "regimen_proteccion" y "tipologia_edificio" solo se rellenan si el pliego encaja \
   con una de las opciones cerradas que se te dan — si no encaja con ninguna, \
   "encontrado": false.
"""


def _campo_valor(valor_schema: dict) -> dict:
    return {
        "type": "object",
        "required": ["encontrado"],
        "properties": {
            "encontrado": {
                "type": "boolean",
                "description": "false si el pliego no menciona este dato — en ese caso no rellenar «valor».",
            },
            "valor": valor_schema,
            "cita": {
                "type": "string",
                "description": "Fragmento copiado literalmente del pliego donde aparece este dato.",
            },
            "confianza": {"type": "string", "enum": [ALTA, MEDIA, BAJA]},
            "motivo_no_encontrado": {"type": "string"},
        },
    }


def _tool_schema() -> dict:
    props: Dict[str, Any] = {
        "no_es_pliego": {
            "type": "boolean",
            "description": "true si el documento no parece un pliego de condiciones de un concurso.",
        }
    }
    for nombre, _unidad, valor_schema in _CAMPOS_ESCALARES:
        props[nombre] = _campo_valor(valor_schema)
    for nombre, _unidad, item_schema in _CAMPOS_LISTA:
        props[nombre] = _campo_valor({"type": "array", "items": item_schema})
    props["mix_tipologias"] = _campo_valor({
        "type": "array",
        "items": {
            "type": "object",
            "required": ["tipo", "porcentaje"],
            "properties": {
                "tipo": {"type": "string", "description": "p.ej. «1 dormitorio», «2 dormitorios»"},
                "porcentaje": {"type": "number"},
                "sup_util_min": {"type": "number"},
                "sup_util_max": {"type": "number"},
            },
        },
    })
    return {
        "name": NOMBRE_HERRAMIENTA,
        "description": "Registra los parámetros extraídos de un pliego de condiciones de concurso.",
        "input_schema": {
            "type": "object",
            "required": ["no_es_pliego"] + _NOMBRES_CAMPOS,
            "properties": props,
        },
    }


class ErrorDeExtraccionPliego(Exception):
    """Fallo al extraer — sin API key, sin paquete `anthropic`, error de la
    API, rechazo del modelo, o una respuesta que no usa la herramienta
    forzada. Nunca se devuelve un resultado a medias fingiendo que se
    extrajo algo (mismo criterio que `ErrorDeInterpretacion`)."""


@dataclass
class ResultadoExtraccionPliego:
    """`hechos` trae SIEMPRE los `_NOMBRES_CAMPOS` completos, cada uno como
    `Hecho` (KNOWN si el pliego lo declaraba, UNKNOWN con motivo si no).
    `es_pliego=False` es la señal de que el PDF subido no parecía un pliego
    de condiciones — quien llame decide si aun así guarda algo (no lo hace,
    ver `app.py`)."""

    hechos: Dict[str, Hecho]
    es_pliego: bool


def _motivo(nombre: str, texto: Optional[str]) -> Motivo:
    return Motivo(
        codigo="NO_CITADO_EN_PLIEGO",
        detalle=texto or f"El pliego no declara «{nombre}» de forma citable.",
    )


def _confianza_valida(valor: Any) -> Optional[str]:
    return valor if valor in CONFIANZAS else None


def _hecho_desde_campo(nombre: str, unidad: str, campo: Any, nombre_archivo: str) -> Hecho:
    """Convierte el objeto crudo que Claude rellenó para un campo (la forma
    de `_campo_valor`) en un `Hecho`. Nunca confía ciegamente en
    `encontrado=true`: si no viene acompañado de un `valor` utilizable, se
    degrada a UNKNOWN en vez de dejar pasar un `Hecho` inconsistente —
    mismo espíritu que `_validar_y_convertir` en
    `analyzer/interview/claude_interprete.py`."""
    fuente = "pliego:%s" % nombre_archivo
    if not isinstance(campo, dict):
        return Hecho(
            nombre=nombre, ambito="concurso", tipo="declarado", unidad=unidad,
            estado=UNKNOWN, motivos=(_motivo(nombre, "respuesta del modelo con forma inesperada"),),
            fuente=fuente,
        )

    encontrado = campo.get("encontrado") is True
    valor = campo.get("valor")
    valor_vacio = valor is None or (isinstance(valor, (list, tuple)) and not valor)
    if not encontrado or valor_vacio:
        motivo_texto = campo.get("motivo_no_encontrado")
        if encontrado and valor_vacio:
            motivo_texto = motivo_texto or "el modelo marcó «encontrado» pero no incluyó ningún valor"
        return Hecho(
            nombre=nombre, ambito="concurso", tipo="declarado", unidad=unidad,
            estado=UNKNOWN, motivos=(_motivo(nombre, motivo_texto),), fuente=fuente,
        )

    return Hecho(
        nombre=nombre, ambito="concurso", tipo="declarado", unidad=unidad,
        estado=KNOWN, valor=valor,
        criterio_declarado=campo.get("cita") or None,
        confianza=_confianza_valida(campo.get("confianza")),
        fuente=fuente,
    )


def _convertir(bruto: dict, nombre_archivo: str) -> ResultadoExtraccionPliego:
    hechos: Dict[str, Hecho] = {}
    for nombre, unidad, _schema in _CAMPOS_ESCALARES:
        hechos[nombre] = _hecho_desde_campo(nombre, unidad, bruto.get(nombre), nombre_archivo)
    for nombre, unidad, _schema in _CAMPOS_LISTA:
        hechos[nombre] = _hecho_desde_campo(nombre, unidad, bruto.get(nombre), nombre_archivo)
    hechos["mix_tipologias"] = _hecho_desde_campo("mix_tipologias", "", bruto.get("mix_tipologias"), nombre_archivo)
    return ResultadoExtraccionPliego(hechos=hechos, es_pliego=bruto.get("no_es_pliego") is not True)


def extraer_parametros_pliego(
    pdf_bytes: bytes, nombre_archivo: str, *, model: str = MODEL, api_key: Optional[str] = None
) -> ResultadoExtraccionPliego:
    """Llama a Claude UNA vez sobre el PDF completo y devuelve los 17
    parámetros como `Hecho`. Levanta `ErrorDeExtraccionPliego` ante
    cualquier fallo — nunca un resultado parcial."""
    if anthropic is None:
        raise ErrorDeExtraccionPliego("el paquete «anthropic» no está instalado")

    clave = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not clave:
        raise ErrorDeExtraccionPliego("falta ANTHROPIC_API_KEY")

    # Tarea 9: tiempo limite explicito. Ver analyzer/anthropic_cliente.py.
    cliente = crear_cliente(clave)
    herramienta = _tool_schema()
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")

    try:
        respuesta = cliente.messages.create(
            model=model,
            max_tokens=4096,
            # SYSTEM_PROMPT no cambia entre pliegos, así que cachearlo no
            # cuesta nada -- pero a diferencia de extraccion/interprete.py
            # (decenas de llamadas por documento, mismo prompt) aquí es UNA
            # llamada por pliego: no hay que esperar ahorro real de esto
            # salvo que el mismo pliego se reprocese dentro del TTL de la
            # caché (§9 del PRD).
            system=[
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
            ],
            tools=[herramienta],
            tool_choice={"type": "tool", "name": NOMBRE_HERRAMIENTA},
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
                    },
                    {"type": "text", "text": "Extrae los parámetros de este pliego de condiciones de concurso."},
                ],
            }],
        )
    except anthropic.APIError as exc:
        raise ErrorDeExtraccionPliego("error de la API: %s" % exc) from exc

    if respuesta.stop_reason == "refusal":
        raise ErrorDeExtraccionPliego("el modelo rechazó la petición")

    bloque = next((b for b in respuesta.content if b.type == "tool_use"), None)
    if bloque is None:
        raise ErrorDeExtraccionPliego("el modelo no usó la herramienta forzada")

    return _convertir(dict(bloque.input), nombre_archivo)
