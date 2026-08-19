"""Integración con Claude — Fase C, tareas C7-C9.

**El único módulo de la Fase C que puede llegar a llamar a Claude de
verdad.** `motor.py` nunca importa `anthropic` directamente ni construye un
cliente — recibe un objeto que cumple `InterpreteIA` (duck typing, sin
`Protocol` runtime-checked para no forzar una dependencia de tipado) y lo
usa a través de dos métodos. En los tests (`tests/test_interview_motor.py`)
ese objeto es un `FakeInterprete` que nunca toca la red — la suite normal no
hace ninguna llamada real, tal como pide la validación de esta fase.

Reutiliza `_extract_json` de `ai_analyst.py`, mismo patrón que
`ai_generator.py` ya usa (`from .ai_analyst import _extract_json`) — no se
duplica el parseo de JSON envuelto en bloque markdown.

Presupuesto de esta fase (PRD v2 §21, Decisión Pablo #4): máximo 5 llamadas
por entrevista, objetivo 3-5, **ninguna llamada de auditoría añadida**
(Decisión Pablo #5) — la detección de contradicción semántica del bloque
adaptativo abierto viaja en la MISMA llamada que ya interpreta ese bloque
(`contradiccion_detectada` en la misma respuesta JSON), nunca en una llamada
aparte.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from ia.cliente import crear_cliente

from ..ai_analyst import _extract_json
from .modelo import CONFIANZAS, NATURALEZAS_RESPUESTA, RespuestaInterpretada, nuevo_id
from .preguntas import CAMPOS_OPORTUNISTAS_BLOQUE_FIJO, Pregunta

try:
    import anthropic
except ImportError:  # pragma: no cover - mismo patrón que ai_analyst.py
    anthropic = None  # type: ignore[assignment]

from ia import modelos

# El modelo se resuelve en `ia/modelos.py` por perfil de tarea, y no se
# escribe aquí: era la misma constante repetida en seis módulos.
MODEL = modelos.para("interpretacion")

#: Nunca se promete a Claude que puede inventar un hecho normativo. Este
#: párrafo es fijo, no depende del proyecto — regla explícita del encargo de
#: esta fase ("no permitas que Claude invente valores normativos").
SYSTEM_PROMPT = """Eres el entrevistador de ArchMuse: interpretas lo que una persona sin
vocabulario técnico dice sobre el proyecto de vivienda que quiere construir,
y lo conviertes en datos estructurados.

Reglas que no puedes romper:

1. Nunca inventes un dato normativo (plantas máximas, edificabilidad,
   ocupación, retranqueos). Si el usuario no lo sabe con certeza, tu
   `naturaleza` para ese campo es "Hipótesis" y tu `confianza` es "Baja" —
   nunca lo completes con un valor plausible.
2. Distingue siempre entre Hecho (el usuario lo afirmó con seguridad),
   Inferencia (lo dedujiste tú de lo que dijo, con tu propio razonamiento),
   Hipótesis (ni el usuario ni tú lo sabéis con certeza; es la mejor
   suposición razonable) y Preferencia (una preferencia de diseño, no un
   hecho ni una restricción).
3. Nunca conviertas una preferencia en una restricción dura. Si el usuario
   dice "me gustaría mucha luz" eso es una Preferencia, no un Hecho ni algo
   obligatorio.
4. Nunca decidas un número exacto de viviendas a partir de una preferencia
   vaga ("quiero muchas viviendas pequeñas"). Registra la preferencia tal
   cual, en el vocabulario cerrado que se te indica — la conversión a un
   número concreto no es tu trabajo.
5. Usa únicamente los `especificacion_id` de la lista permitida que se te
   da en cada petición. No inventes identificadores nuevos.
6. Cuando un campo de vocabulario cerrado (p. ej. "mix de viviendas") tenga
   opciones definidas, tu `valor` debe ser exactamente una de esas opciones
   — nunca texto libre nuevo para un campo que ya tiene vocabulario cerrado.

Respondes siempre con un único objeto JSON, sin texto fuera de él. Escapa
correctamente cualquier salto de línea (\\n) o comilla doble (\\") que
aparezca dentro de un texto."""


class InterpretacionError(Exception):
    """La llamada se intentó (cuenta para el presupuesto de 5) pero no
    produjo una interpretación utilizable — red, parseo, o rechazo del
    modelo. `motor.py` la captura y nunca la deja propagar hasta el
    usuario: el campo afectado queda como Hipótesis de confianza Baja con
    motivo explícito, nunca inventado."""


@dataclass
class ResultadoInterpretacion:
    """Lo que produce una llamada de interpretación, ya convertido a
    `RespuestaInterpretada` — `motor.py` solo añade `turno_id`/`respuesta_id`
    y decide qué hacer con la contradicción, no vuelve a tocar el JSON."""

    respuestas: list[RespuestaInterpretada] = field(default_factory=list)
    #: (especificacion_id, valor_conflictivo) si Claude señaló una tensión
    #: semántica en la misma llamada (C8) — `None` si no detectó ninguna.
    contradiccion_detectada: Optional[tuple[str, Any]] = None


class InterpreteIA(Protocol):
    """La interfaz que `motor.py` consume. `FakeInterprete` (tests) y
    `ClienteAnthropicInterprete` (real) implementan exactamente esto — duck
    typing, no hace falta heredar de esta clase."""

    def interpretar_bloque_fijo(
        self, respuestas_crudas: dict[str, str], turno_id: str
    ) -> ResultadoInterpretacion: ...

    def interpretar_texto_libre(
        self, pregunta: Pregunta, respuesta_cruda: str, turno_id: str
    ) -> ResultadoInterpretacion: ...


def _validar_y_convertir(
    campos_json: list[dict], campos_permitidos: frozenset[str], turno_id: str
) -> list[RespuestaInterpretada]:
    """Filtra cualquier `especificacion_id` que Claude haya podido inventar
    fuera de la lista permitida (regla 5 del SYSTEM_PROMPT, comprobada aquí
    en código, nunca solo confiada al prompt) y valida los catálogos
    cerrados de `naturaleza`/`confianza` — un valor fuera de catálogo aquí
    se descarta en vez de romper la entrevista completa por un campo."""
    resultado = []
    for campo in campos_json:
        especificacion_id = campo.get("especificacion_id")
        if especificacion_id not in campos_permitidos:
            continue
        naturaleza = campo.get("naturaleza")
        if naturaleza not in NATURALEZAS_RESPUESTA:
            continue
        confianza = campo.get("confianza")
        if confianza not in CONFIANZAS:
            confianza = None
        resultado.append(
            RespuestaInterpretada(
                respuesta_id=nuevo_id(),
                turno_id=turno_id,
                especificacion_id=especificacion_id,
                respuesta_cruda=campo.get("respuesta_cruda_citada"),
                naturaleza=naturaleza,
                valor=campo.get("valor"),
                confianza=confianza,
                motivo=campo.get("motivo"),
            )
        )
    return resultado


class ClienteAnthropicInterprete:
    """Implementación real, mismo patrón que `_call_claude` de
    `ai_generator.py`: cliente construido una vez, `api_key` de entorno,
    nunca instanciada por los tests (que usan `FakeInterprete`)."""

    def __init__(self, api_key: Optional[str] = None, model: str = MODEL) -> None:
        if anthropic is None:
            raise InterpretacionError("El paquete 'anthropic' no está instalado.")
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise InterpretacionError("Configura ANTHROPIC_API_KEY para usar el entrevistador con IA.")
        # Tarea 9: tiempo limite explicito. Ver analyzer/anthropic_cliente.py.
        self._client = crear_cliente(key)
        self._model = model

    def _llamar(self, mensaje_usuario: str, campos_permitidos: frozenset[str], turno_id: str) -> ResultadoInterpretacion:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                # SYSTEM_PROMPT es idéntico en las (hasta 5) llamadas de una
                # misma entrevista -- cachearlo evita pagar el precio
                # completo por él en cada una.
                system=[
                    {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
                ],
                messages=[{"role": "user", "content": mensaje_usuario}],
            )
        except anthropic.APIError as exc:  # pragma: no cover - requiere red real
            raise InterpretacionError("Fallo de red/API llamando a Claude: %s" % exc) from exc

        if response.stop_reason == "refusal":  # pragma: no cover - requiere red real
            raise InterpretacionError("Claude rechazó la interpretación por filtros de seguridad.")

        texto = next((b.text for b in response.content if b.type == "text"), "")
        try:
            datos = _extract_json(texto)
        except (json.JSONDecodeError, AttributeError) as exc:  # pragma: no cover - requiere red real
            raise InterpretacionError("Respuesta de Claude no es JSON válido: %s" % exc) from exc

        respuestas = _validar_y_convertir(datos.get("campos") or [], campos_permitidos, turno_id)
        contradiccion = datos.get("contradiccion_detectada")
        contradiccion_tupla = None
        if contradiccion and contradiccion.get("especificacion_id") in campos_permitidos:
            contradiccion_tupla = (contradiccion["especificacion_id"], contradiccion.get("valor"))
        return ResultadoInterpretacion(respuestas=respuestas, contradiccion_detectada=contradiccion_tupla)

    def interpretar_bloque_fijo(self, respuestas_crudas: dict[str, str], turno_id: str) -> ResultadoInterpretacion:
        permitidos = frozenset(
            ("programa.descripcion_libre", "programa.sensacion_buscada",
             "prioridades.no_negociables", "prioridades.lo_de_menos_importa")
            + CAMPOS_OPORTUNISTAS_BLOQUE_FIJO
        )
        mensaje = (
            "especificacion_id permitidos: " + json.dumps(sorted(permitidos), ensure_ascii=False) + "\n\n"
            "Respuestas del usuario a tres preguntas presentadas juntas:\n"
            + json.dumps(respuestas_crudas, ensure_ascii=False, indent=2)
            + "\n\nDevuelve JSON: {\"campos\": [{\"especificacion_id\":.., \"valor\":.., "
              "\"naturaleza\":.., \"confianza\":.., \"motivo\":.., \"respuesta_cruda_citada\":..}], "
              "\"contradiccion_detectada\": {\"especificacion_id\":.., \"valor\":..} | null}"
        )
        return self._llamar(mensaje, permitidos, turno_id=turno_id)

    def interpretar_texto_libre(self, pregunta: Pregunta, respuesta_cruda: str, turno_id: str) -> ResultadoInterpretacion:
        permitidos = frozenset(pregunta.especificacion_ids)
        mensaje = (
            "especificacion_id permitidos: " + json.dumps(sorted(permitidos), ensure_ascii=False) + "\n\n"
            "Pregunta: " + pregunta.texto + "\nRespuesta del usuario: " + respuesta_cruda
            + "\n\nDevuelve el mismo formato JSON de siempre."
        )
        return self._llamar(mensaje, permitidos, turno_id=turno_id)
