"""Análisis experto con IA (Claude) sobre las viviendas ya evaluadas.

Usa la API de Anthropic para que un "arquitecto experto" (el modelo) genere,
a partir de los datos técnicos ya calculados por `evaluator.py`:
- Un diagnóstico narrativo de cada vivienda (2-3 frases).
- Las 3 mejoras más importantes, priorizadas.
- Una comparativa entre viviendas: cuál es mejor y por qué.
- Una conclusión ejecutiva del proyecto completo.

La API key se lee de la variable de entorno ANTHROPIC_API_KEY. Si no está
configurada (o la llamada falla por cualquier motivo), `analyze_with_ai`
devuelve None y el resto del pipeline sigue funcionando con normalidad, sin
la sección de IA en el informe.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

from .evaluator import UnitScore

try:
    import anthropic
except ImportError:  # pragma: no cover - se avisa en tiempo de ejecución
    anthropic = None  # type: ignore[assignment]

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """Eres un arquitecto experto con décadas de experiencia revisando \
proyectos de vivienda residencial en España. Se te proporciona un análisis \
técnico ya calculado (áreas, proporciones, jerarquía de dormitorios, \
eficiencia y orientación solar) de varias viviendas de un mismo edificio.

Tu trabajo NO es repetir los datos que ya tienes, sino aportar criterio de \
arquitecto experto: qué implican esos datos para la calidad real de vida en \
la vivienda, qué prioridad tienen los problemas, y cómo se comparan las \
viviendas entre sí.

Ten en cuenta la zona climática CTE ("zona_cte") y la tipología del \
proyecto ("tipologia") indicadas en los datos: ajusta tu criterio a lo que \
es razonable exigir en cada caso.

Responde ÚNICAMENTE con un objeto JSON válido (sin texto adicional antes ni \
después, sin bloques de código markdown) con exactamente esta forma. Escapa \
correctamente cualquier salto de línea (\\n) o comilla doble (\\") que \
aparezca dentro de un texto:

{
  "diagnosticos": [
    {"vivienda": "<nombre de la vivienda>", "diagnostico": "<2-3 frases>"}
  ],
  "mejoras_prioritarias": ["<mejora 1>", "<mejora 2>", "<mejora 3>"],
  "comparativa": "<qué vivienda es mejor y por qué, en 2-4 frases>",
  "conclusion_ejecutiva": "<conclusión del proyecto completo, en 3-5 frases>"
}

"diagnosticos" debe incluir una entrada por cada vivienda de los datos. \
"mejoras_prioritarias" debe tener exactamente 3 elementos, ordenados por \
prioridad (la más importante primero), indicando a qué vivienda(s) afecta \
cada una."""


@dataclass
class ViviendaDiagnosis:
    vivienda: str
    diagnostico: str


@dataclass
class AIAnalysis:
    diagnosticos: List[ViviendaDiagnosis] = field(default_factory=list)
    mejoras_prioritarias: List[str] = field(default_factory=list)
    comparativa: str = ""
    conclusion_ejecutiva: str = ""


def build_viviendas_payload(
    unit_scores: List[UnitScore],
    zona_cte: str = "C",
    tipologia: str = "plurifamiliar",
    issues_criticos: Optional[List[str]] = None,
) -> dict:
    """Convierte los resultados del análisis técnico (evaluator.UnitScore) en
    un diccionario serializable a JSON con lo que necesita el arquitecto IA:
    habitaciones, áreas, puntuación y problemas detectados, por vivienda —
    más contexto de proyecto (`zona_cte`, `tipologia`) y los `issues`
    CRITICO ya clasificados por `evaluator.classify_problems`.
    """
    viviendas = []
    for u in unit_scores:
        problemas: List[str] = []
        problemas.extend(r.message for r in u.basic_results if not r.passed)
        problemas.extend(p.message for p in u.proportion_results if not p.passed)
        problemas.extend(h.message for h in u.hierarchy_results if not h.passed)
        if u.efficiency_result and not u.efficiency_result.passed:
            problemas.append(u.efficiency_result.message)
        problemas.extend(
            o.message for o in u.orientation_results if o.rating == "penalizada"
        )

        viviendas.append(
            {
                "nombre": u.unit.name,
                "puntuacion": round(u.score_pct),
                "superficie_total_m2": round(u.unit.total_area_m2, 2),
                "habitaciones": [
                    {"nombre": r.label or "(sin etiqueta)", "area_m2": round(r.area_m2, 2)}
                    for r in u.unit.rooms
                ],
                "problemas": problemas,
            }
        )
    return {
        "viviendas": viviendas,
        "zona_cte": zona_cte,
        "tipologia": tipologia,
        "issues_criticos": issues_criticos or [],
    }


def build_viviendas_payload_from_proyecto(proyecto: dict) -> dict:
    """Misma entrada para `analyze_with_ai` que `build_viviendas_payload`,
    pero reconstruida a partir de un proyecto YA analizado y serializado
    (`storage.obtener_proyecto` / la respuesta de `/api/analizar` o
    `/api/generar`), sin volver a tocar `UnitScore`.

    Existe para que el diagnóstico de IA se pueda pedir bajo demanda —
    justo al analizar, o más tarde reabriendo el proyecto — sin reevaluar
    nada ni depender de tener los objetos `UnitScore` en memoria de esa
    misma petición. No coincide byte a byte con `build_viviendas_payload`
    (los "problemas" aquí son la unión de `problemas_vivienda` + los
    `problemas` de cada habitación ya serializados, no los mensajes crudos
    de `evaluator.py`), pero es la misma información para el mismo
    propósito: que el arquitecto IA tenga los datos ya calculados.
    """
    viviendas = []
    for u in proyecto.get("viviendas") or []:
        habitaciones = u.get("habitaciones") or []
        problemas: List[str] = list(u.get("problemas_vivienda") or [])
        for h in habitaciones:
            problemas.extend(h.get("problemas") or [])
        viviendas.append(
            {
                "nombre": u.get("nombre", ""),
                "puntuacion": u.get("puntuacion", 0),
                "superficie_total_m2": u.get("superficie_total_m2", 0),
                "habitaciones": [
                    {"nombre": h.get("nombre") or "(sin etiqueta)", "area_m2": h.get("area_m2", 0)}
                    for h in habitaciones
                ],
                "problemas": problemas,
            }
        )

    proyecto_meta = proyecto.get("proyecto") or {}
    issues_criticos = [
        i.get("titulo", "") for i in proyecto.get("issues") or [] if i.get("severity") == "CRITICO"
    ]

    return {
        "viviendas": viviendas,
        "zona_cte": proyecto_meta.get("zona_cte", "C"),
        "tipologia": proyecto_meta.get("tipologia", "plurifamiliar"),
        "issues_criticos": issues_criticos,
    }


#: Fix 2026-08-16 (bug real reportado en producción: `json.JSONDecodeError: Unterminated string
#: starting at...`). Compartida por `ai_analyst.py`, `ai_generator.py` y
#: `interview/claude_interprete.py` (los tres importan esta misma función, nunca la duplican) --
#: arreglarla aquí arregla el fallo de parseo en cualquiera de los tres sitios donde de verdad
#: ocurría.
_RE_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_RE_COMA_FINAL = re.compile(r",(\s*[}\]])")


def _limpiar_bloque_json(text: str) -> str:
    """Aísla el objeto JSON de la respuesta cruda del modelo, tolerando los problemas de formato
    más comunes en JSON generado por un LLM:

    - Bloque de código markdown (```json ... ``` o ``` ... ```), incluso con texto de preámbulo o
      cierre alrededor (p. ej. "Aquí tienes el JSON:\\n```json\\n{...}\\n```\\n¿Necesitas algo más?"
      -- la instrucción del prompt pide que esto no ocurra, pero el modelo no siempre la respeta).
    - Sin bloque de código: preámbulo o cierre en texto plano alrededor del objeto -- se recorta al
      primer `{` y al último `}` del texto completo.
    - Comas finales antes de `}`/`]` (error de formato muy común en JSON generado por un LLM, que
      `json.loads` rechaza pero que no representa ninguna ambigüedad real de interpretación).

    Nunca intenta reparar un objeto genuinamente truncado (respuesta cortada a mitad de una cadena
    por haber alcanzado el límite de tokens) -- eso lo distingue `_extract_json` para dar un
    mensaje honesto en vez de fabricar un cierre inventado."""
    texto = text.strip()
    fence = _RE_JSON_FENCE.search(texto)
    if fence:
        texto = fence.group(1).strip()
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio != -1 and fin != -1 and fin > inicio:
        texto = texto[inicio:fin + 1]
    return _RE_COMA_FINAL.sub(r"\1", texto)


def _parece_truncado(exc: json.JSONDecodeError) -> bool:
    """`json.loads` solo produce el mensaje "Unterminated string starting at" cuando el escáner
    de cadenas llega al final de TODO el documento sin encontrar la comilla de cierre (ver
    `json.decoder.py_scanstring` en la librería estándar) -- por construcción, eso significa que
    el documento se acaba literalmente a mitad de una cadena, que es exactamente lo que produce
    una respuesta cortada por el límite de tokens. No es una heurística de distancia al final del
    texto (`exc.pos` en este mensaje concreto apunta al INICIO de la cadena sin cerrar, no al
    punto donde el documento se acabó, así que medir esa distancia no sirve) -- es una
    comprobación exacta de qué significa siempre ese mensaje en particular."""
    return exc.msg == "Unterminated string starting at"


def _extract_json(text: str) -> dict:
    """Extrae el objeto JSON de la respuesta del modelo -- ver `_limpiar_bloque_json` para qué
    problemas de formato tolera antes de intentar el parseo.

    `strict=False`: el JSON generado por un LLM a veces incluye un salto de línea SIN escapar
    dentro de una cadena (p. ej. una justificación en varios párrafos) -- JSON estricto lo rechaza
    como carácter de control inválido, y ese rechazo es precisamente lo que producía el
    `Unterminated string starting at...` reportado (el parser, al toparse con el carácter no
    válido, pierde la referencia de dónde termina la cadena). `strict=False` permite caracteres de
    control literales dentro de cadenas -- comportamiento documentado del propio módulo `json` de
    Python, no una reimplementación propia del parser.

    Si el JSON está genuinamente truncado (la respuesta se cortó a mitad de una cadena/objeto por
    haber alcanzado el límite de tokens), esto NUNCA lo repara con un cierre inventado -- eso
    fabricaría datos que el modelo no llegó a generar. En su lugar se relanza como
    `json.JSONDecodeError` con un mensaje explícito que distingue "la respuesta se cortó" de "el
    JSON tiene un problema de formato", para que quien llame pueda mostrar un error honesto en vez
    de uno genérico e ilegible."""
    candidato = _limpiar_bloque_json(text)
    try:
        return json.loads(candidato, strict=False)
    except json.JSONDecodeError as exc:
        if _parece_truncado(exc):
            raise json.JSONDecodeError(
                "la respuesta de la IA se cortó antes de terminar (probablemente por alcanzar el "
                "límite de tokens) -- inténtalo de nuevo",
                exc.doc, exc.pos,
            ) from exc
        raise


def analyze_with_ai(viviendas_data: dict, model: str = MODEL) -> Optional[AIAnalysis]:
    """Llama a la API de Anthropic para obtener un análisis experto de las
    viviendas descritas en `viviendas_data` (ver `build_viviendas_payload`).

    Devuelve None -sin lanzar excepción- si no hay ANTHROPIC_API_KEY
    configurada, si el paquete `anthropic` no está instalado, o si la
    llamada falla por cualquier motivo: el informe debe poder generarse
    igualmente sin la sección de IA.
    """
    if anthropic is None:
        print("Aviso: el paquete 'anthropic' no está instalado; se omite el análisis IA.")
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Aviso: configure ANTHROPIC_API_KEY para activar el análisis experto con IA.")
        return None

    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            # SYSTEM_PROMPT es idéntico en cada llamada -- cachearlo evita
            # pagar el precio completo por él cada vez (~90% más barato en
            # lecturas de caché).
            system=[
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
            ],
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Datos técnicos del proyecto (JSON):\n\n"
                        + json.dumps(viviendas_data, ensure_ascii=False, indent=2)
                    ),
                }
            ],
        )
    except anthropic.APIError as exc:
        print(f"Aviso: no se pudo obtener el análisis de IA ({exc}).")
        return None

    if response.stop_reason == "refusal":
        print("Aviso: el análisis de IA fue rechazado por los filtros de seguridad del modelo.")
        return None

    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        data = _extract_json(text)
    except (json.JSONDecodeError, AttributeError) as exc:
        print(f"Aviso: no se pudo interpretar la respuesta de IA como JSON ({exc}).")
        return None

    diagnosticos = [
        ViviendaDiagnosis(
            vivienda=d.get("vivienda", ""), diagnostico=d.get("diagnostico", "")
        )
        for d in data.get("diagnosticos", [])
    ]

    return AIAnalysis(
        diagnosticos=diagnosticos,
        mejoras_prioritarias=list(data.get("mejoras_prioritarias", [])),
        comparativa=data.get("comparativa", ""),
        conclusion_ejecutiva=data.get("conclusion_ejecutiva", ""),
    )
