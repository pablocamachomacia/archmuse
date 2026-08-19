"""Interpretación por IA de un `Segmento` → borrador crudo, antes de verificar.

Un único punto de contacto con un modelo en todo `extraccion/`. Todo lo que
puede hacerse sin IA (segmentar, verificar, calcular confianza) vive en otros
módulos precisamente para que esta sea la única pieza no determinista del
paquete, la única que hace falta mockear o saltarse para probar el resto sin
gastar un token.

**Salida forzada a un esquema cerrado** (mecanismo 1 de §3 del diseño): se
usa `tool_choice` forzado de la API de Anthropic, con un JSON Schema cuyos
enums (`tipo`, `patron`, `materia_sugerida`, `severidad_sugerida`,
`comparador`) se construyen en tiempo de importación a partir de
`normativa.modelo`/`normativa.catalogos`/`normativa.condiciones` — nunca
escritos a mano en el prompt, para que no puedan desincronizarse del
catálogo real si éste cambia.

Este módulo NO verifica nada del contenido (eso es `verificacion.py`, sin
IA) ni calcula la confianza (`confianza.py`, tampoco). Devuelve el diccionario
crudo que el modelo rellenó, tal cual — la frontera entre "lo que dijo la IA"
y "lo que hemos comprobado de ello" tiene que verse en el código, no solo en
la cabeza de quien lo escribió.
"""
from __future__ import annotations

import os
from typing import Optional

try:
    import anthropic
except ImportError:  # pragma: no cover - mismo patrón que analyzer/ai_analyst.py
    anthropic = None

from ia.cliente import crear_cliente
from normativa.catalogos import materias
from normativa.condiciones import COMPARADORES, COMPARADORES_DE_PRESENCIA
from normativa.modelo import PATRONES, PRIORIDADES, TIPOS_REGLA

from .errores import ErrorDeInterpretacion
from .modelo import Segmento

from ia import modelos

# Mismo perfil que `analyzer/ai_analyst.py`, por consistencia: las dos leen un
# documento y sacan datos estructurados de él. El modelo concreto lo decide
# `ia/modelos.py`, para que la elección se tome en un sitio y no en seis.
MODEL = modelos.para("interpretacion")

NOMBRE_HERRAMIENTA = "registrar_interpretacion"

SYSTEM_PROMPT = """Eres un asistente que ayuda a un Curador de Conocimiento normativo a \
transcribir un artículo del Código Técnico de la Edificación (CTE) español a una \
estructura de datos. NO eres tú quien decide qué exige la norma: el texto que se te \
pasa es la única fuente de verdad, y tu trabajo es interpretarlo con la máxima fidelidad \
posible, nunca completarlo con lo que "sueles saber" del CTE de otras fuentes.

Reglas estrictas, sin excepción:

1. Cualquier cifra, umbral o valor que declares en "parametros" debe aparecer \
   literalmente en el texto que se te ha dado — copiado, no recordado ni normalizado. \
   Si el artículo no cita ningún valor numérico, no rellenes "parametros": no inventes \
   uno "típico" del CTE aunque lo conozcas de otro contexto.
2. Si el artículo es una definición, un trámite, una remisión a otra norma, o exige \
   "solución equivalente justificada" (juicio humano), su "tipo" debe ser \
   "definicion", "procedimental", "remision" o "exigencia_cualitativa" respectivamente \
   — y en ese caso NUNCA rellenes "patron" ni "parametros": esos cuatro tipos no son \
   evaluables por un motor geométrico y forzar un patrón sería fingir una precisión \
   que el artículo no tiene.
3. "segmento_id" en tu respuesta debe ser EXACTAMENTE el id del segmento que se te ha \
   pasado — es la comprobación de que interpretas éste y no otro artículo.
4. Si tienes cualquier duda razonable sobre si tu interpretación representa fielmente \
   el artículo — ambigüedad, remisión a un anexo que no se te ha mostrado, terminología \
   técnica que admite más de una lectura — marca "necesita_revision_humana": true y \
   explica por qué en "motivo_necesita_revision". Marcarlo no es un fallo tuyo: es \
   exactamente lo que se espera cuando corresponde.
5. "explicacion_interpretacion" debe describir CÓMO llegaste de las palabras del \
   artículo a la estructura que propones, no repetir el texto ni resumir "de qué trata".
6. No propongas "materia_sugerida" ni "severidad_sugerida" si el artículo no da pie \
   claro a decidirlas — es preferible omitirlas a adivinar.
"""


def _tool_schema() -> dict:
    """Construido en tiempo de importación, no escrito a mano, para que los
    enums nunca se desincronicen del catálogo cerrado real."""
    comparadores = sorted(set(COMPARADORES) | set(COMPARADORES_DE_PRESENCIA))
    return {
        "name": NOMBRE_HERRAMIENTA,
        "description": "Registra la interpretación estructurada de un artículo del CTE.",
        "input_schema": {
            "type": "object",
            "required": [
                "segmento_id", "tipo", "necesita_revision_humana",
                "explicacion_tecnica", "explicacion_interpretacion",
            ],
            "properties": {
                "segmento_id": {
                    "type": "string",
                    "description": "El id exacto del segmento recibido, sin modificar.",
                },
                "tipo": {"type": "string", "enum": sorted(TIPOS_REGLA)},
                "patron": {
                    "type": "string", "enum": sorted(PATRONES),
                    "description": "Solo si «tipo» es evaluable (regla 2 del system prompt).",
                },
                "materia_sugerida": {"type": "string", "enum": sorted(materias())},
                "severidad_sugerida": {"type": "string", "enum": sorted(PRIORIDADES)},
                "condicion_aplicacion": {
                    "type": "string",
                    "description": "En qué casos aplica el artículo, en tus palabras, citando el texto.",
                },
                "parametros": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["nombre", "valor_citado"],
                        "properties": {
                            "nombre": {"type": "string"},
                            "valor_citado": {
                                "type": "string",
                                "description": "Copiado literalmente del texto — regla 1.",
                            },
                            "unidad": {"type": "string"},
                            "comparador": {"type": "string", "enum": comparadores},
                            "contexto_citado": {"type": "string"},
                        },
                    },
                },
                "excepciones": {"type": "array", "items": {"type": "string"}},
                "referencias_internas": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Menciones a otros artículos/anejos del MISMO documento.",
                },
                "explicacion_tecnica": {"type": "string"},
                "explicacion_interpretacion": {"type": "string"},
                "necesita_revision_humana": {"type": "boolean"},
                "motivo_necesita_revision": {"type": "string"},
            },
        },
    }


def interpretar(segmento: Segmento, *, model: str = MODEL, api_key: Optional[str] = None) -> dict:
    """Llama al modelo sobre UN segmento y devuelve el diccionario crudo que
    rellenó — sin verificar, sin calcular confianza. `pipeline.py` hace
    ambas cosas después, con las funciones de `verificacion.py`/`confianza.py`.

    Levanta `ErrorDeInterpretacion` ante cualquier fallo (sin API key, sin
    paquete `anthropic`, error de la API, rechazo del modelo, o una
    respuesta que no usa la herramienta forzada) — nunca devuelve una
    candidata a medias fingiendo que se interpretó algo.
    """
    if anthropic is None:
        raise ErrorDeInterpretacion(segmento.id, "el paquete «anthropic» no está instalado")

    clave = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not clave:
        raise ErrorDeInterpretacion(segmento.id, "falta ANTHROPIC_API_KEY")

    # Tarea 9: tiempo limite explicito. Ver ia/cliente.py.
    cliente = crear_cliente(clave)
    herramienta = _tool_schema()

    mensaje = (
        f"Segmento a interpretar (id: {segmento.id}, tipo: {segmento.tipo_segmento}"
        + (f", capítulo: {segmento.capitulo}" if segmento.capitulo else "")
        + f"):\n\n{segmento.titulo}\n\n{segmento.texto}"
    )

    try:
        respuesta = cliente.messages.create(
            model=model,
            max_tokens=2048,
            # `temperature=0` (mecanismo 6 de §3) se retira: claude-sonnet-5
            # rechaza con 400 cualquier valor de `temperature`/`top_p`/`top_k`
            # distinto del por defecto, y nunca garantizó de todos modos una
            # salida idéntica. El `tool_choice` forzado de abajo, contra un
            # JSON Schema cerrado, es el mecanismo de determinismo real aquí.
            # SYSTEM_PROMPT no cambia entre segmentos -- cachearlo evita
            # pagar el precio completo por él en cada interpretación.
            system=[
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
            ],
            tools=[herramienta],
            tool_choice={"type": "tool", "name": NOMBRE_HERRAMIENTA},
            messages=[{"role": "user", "content": mensaje}],
        )
    except anthropic.APIError as exc:
        raise ErrorDeInterpretacion(segmento.id, f"error de la API: {exc}") from exc

    if respuesta.stop_reason == "refusal":
        raise ErrorDeInterpretacion(segmento.id, "el modelo rechazó la petición")

    bloque = next((b for b in respuesta.content if b.type == "tool_use"), None)
    if bloque is None:
        raise ErrorDeInterpretacion(segmento.id, "el modelo no usó la herramienta forzada")

    return dict(bloque.input)
