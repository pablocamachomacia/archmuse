"""Único sitio donde se construye un cliente de Anthropic.

**Qué problema resuelve** (tarea 9 del `REFACTOR_MASTERPLAN.md`). El SDK trae
un tiempo límite de lectura de **600 s** y **2 reintentos**: una llamada que se
queda colgada bloquea el hilo que la hizo hasta **30 minutos**. Con `waitress`
sirviendo el producto eso no tumba el servidor entero como lo habría hecho el
servidor de desarrollo monoproceso de Flask, pero sigue siendo un hilo del pool
retenido media hora por una petición que nadie va a leer.

Cuando se escribió la ficha había **dos** clientes. El apéndice del masterplan
contó **cinco** en agosto. Al escribir el test de guardia aparecieron **seis**:
`analyzer/ai_analyst.py`, `analyzer/ai_generator.py`, `analyzer/estilos.py`,
`analyzer/interview/claude_interprete.py`, `analyzer/pliego_extractor.py` y
`extraccion/interprete.py` — que ni la ficha ni el apéndice mencionaban.
Ninguno de los seis pasaba `timeout`.

Esa progresión (2 → 5 → 6) es la razón de que esto sea un módulo y no seis
literales repetidos, y de que exista
`tests/test_anthropic_timeout.py::test_nadie_construye_el_cliente_por_su_cuenta`:
arreglar los seis de hoy no impide que aparezca un séptimo mañana. Prohibir el
patrón, sí.

**Desviación deliberada de la ficha.** Pedía "un timeout explícito y corto
(p. ej. 30-45 s)". No se puede: `ai_generator` pide 8.192 tokens de salida en
una sola llamada, y eso no cabe en 45 s a ninguna velocidad de generación
realista — el timeout "corto" no acotaría el peor caso, convertiría el caso
normal en un fallo. Se usan dos tramos calibrados por `max_tokens` de cada
llamada, con margen suficiente para que un caso legítimo nunca los alcance:

| Tramo | Segundos | Quién | `max_tokens` |
|---|---:|---|---:|
| `TIMEOUT_ESTANDAR_S` | 120 | `ai_analyst`, `pliego_extractor`, `claude_interprete`, `estilos`, `extraccion/interprete` | 1.024 - 4.096 |
| `TIMEOUT_GENERACION_S` | 300 | `ai_generator` | 8.192 |

**El peor caso sigue sin ser el timeout, y conviene decirlo.** Los 2 reintentos
del SDK se conservan (quitarlos cambiaría la fiabilidad frente a un 429 o un
529, que es un problema distinto del que resuelve esta tarea), así que el techo
real es `timeout x 3`: 6 minutos en el tramo estándar y 15 en generación. Frente
a los 30 minutos de antes es una mejora de 5x, no una garantía de respuesta
rápida. Quien necesite lo segundo necesita una cola de trabajos en segundo
plano, que está fuera del alcance del masterplan a propósito.

Ambos valores se pueden ajustar sin tocar código con
`ARCHMUSE_ANTHROPIC_TIMEOUT_S` y `ARCHMUSE_ANTHROPIC_TIMEOUT_GENERACION_S`
(ver `.env.example`). Un valor no numérico o <= 0 se ignora y se usa el de
aquí: una variable mal escrita no puede dejar el producto sin límite.
"""
from __future__ import annotations

import os
from typing import Any, Optional

try:
    import anthropic
except ImportError:  # pragma: no cover - mismo patrón que ai_analyst.py
    anthropic = None  # type: ignore[assignment]

TIMEOUT_ESTANDAR_S = 120.0
TIMEOUT_GENERACION_S = 300.0

_VAR_ESTANDAR = "ARCHMUSE_ANTHROPIC_TIMEOUT_S"
_VAR_GENERACION = "ARCHMUSE_ANTHROPIC_TIMEOUT_GENERACION_S"


def _segundos(nombre_var: str, por_defecto: float) -> float:
    bruto = os.environ.get(nombre_var)
    if not bruto:
        return por_defecto
    try:
        valor = float(bruto)
    except ValueError:
        return por_defecto
    return valor if valor > 0 else por_defecto


def timeout_estandar() -> float:
    return _segundos(_VAR_ESTANDAR, TIMEOUT_ESTANDAR_S)


def timeout_generacion() -> float:
    return _segundos(_VAR_GENERACION, TIMEOUT_GENERACION_S)


def crear_cliente(api_key: str, *, timeout_s: Optional[float] = None) -> Any:
    """Cliente de Anthropic con tiempo límite explícito.

    `timeout_s` solo lo pasa quien no está en el tramo estándar — hoy, solo
    `ai_generator`. Se lee del entorno en cada llamada y no en el import para
    que un cambio de `.env` no exija reiniciar el proceso para probarlo.

    Devuelve `Any` y no `anthropic.Anthropic` a propósito: el SDK es opcional
    (los cinco módulos que lo usan degradan si no está instalado) y anotar el
    tipo real obligaría a importarlo sin guardia.
    """
    if anthropic is None:  # pragma: no cover - mismo aviso que en cada llamador
        raise RuntimeError(
            "El SDK de Anthropic no está instalado. `pip install -r requirements.txt`."
        )
    return anthropic.Anthropic(
        api_key=api_key,
        timeout=timeout_s if timeout_s and timeout_s > 0 else timeout_estandar(),
    )
