# -*- coding: utf-8 -*-
"""Motor de estilos arquitectónicos: catálogo determinista de 14 estilos
base + interpretación por IA de descripciones en lenguaje libre que no
encajan con ninguno.

**Biblioteca determinista primero, IA solo cuando hace falta** — mismo
principio que Pablo fijó el 2026-08-01 ("que use software al máximo y IA lo
mínimo"): `obtener_estilo()` resuelve por coincidencia de catálogo sin tocar
la red siempre que pueda; Claude entra solo para una descripción libre que
no encaja con ninguno de los 14 (p. ej. "brutalismo mediterráneo"). El valor
por defecto de los generadores (`app.py`, "racionalista") es una clave de
catálogo, así que ningún proyecto generado sin pedir estilo explícito
dispara jamás una llamada nueva a la IA.

**Sin referencias a edificios reales.** A diferencia de una primera versión
de este encargo (2026-08-15, sin aprobar), esta especificación no pide
`referencias`/`url_imagen_publica` — bien, porque una URL de imagen
generada por el modelo es uno de los patrones de alucinación mejor
documentados de los LLM. Los parámetros que sí se piden aquí (proporción de
huecos, ritmo, materiales, cubierta, vuelo, textura) son compositivos, no
afirmaciones sobre edificios ni normativa real — el mismo riesgo no aplica.

**El catálogo de 14 estilos es contenido, no un hecho verificable contra un
texto legal** (a diferencia del corpus normativo CTE) — son caracterizaciones
razonables, no revisadas por un arquitecto humano antes de este commit. Vale
la pena que alguien con criterio arquitectónico las revise antes de
presentarlas como autoritativas."""
from __future__ import annotations

import unicodedata
from typing import Any, Optional

from ia.cliente import crear_cliente

try:
    import anthropic
except ImportError:  # pragma: no cover - mismo patrón que ai_analyst.py
    anthropic = None

MODEL = "claude-sonnet-5"

NOMBRE_HERRAMIENTA = "registrar_estilo_arquitectonico"

ORIENTACIONES_HUECOS = ("vertical", "horizontal")
TIPOS_RITMO = ("regular", "irregular", "jerarquico")

#: 14 estilos base (encargo de Pablo, 2026-08-15). Clave = slug normalizado
#: (sin tildes, minúsculas, guion bajo); `nombre_estilo` conserva la
#: ortografía correcta para mostrarla en la SPA/el prompt.
CATALOGO_ESTILOS: dict[str, dict[str, Any]] = {
    "racionalista": {
        "nombre_estilo": "Racionalista",
        "proporcion_huecos": {"ratio_alto_ancho": 1.3, "orientacion": "horizontal"},
        "ritmo_fachada": {"modulo_m": 3.0, "tipo": "regular"},
        "materiales_compatibles": ["hormigón visto", "enlucido blanco", "vidrio"],
        "solucion_cubierta": "plana",
        "vuelo_maximo_m": 1.0,
        "textura": "lisa",
    },
    "brutalista": {
        "nombre_estilo": "Brutalista",
        "proporcion_huecos": {"ratio_alto_ancho": 0.8, "orientacion": "vertical"},
        "ritmo_fachada": {"modulo_m": 4.0, "tipo": "jerarquico"},
        "materiales_compatibles": ["hormigón visto (encofrado marcado)", "ladrillo caravista"],
        "solucion_cubierta": "plana",
        "vuelo_maximo_m": 2.5,
        "textura": "rugosa",
    },
    "mediterraneo": {
        "nombre_estilo": "Mediterráneo",
        "proporcion_huecos": {"ratio_alto_ancho": 1.8, "orientacion": "vertical"},
        "ritmo_fachada": {"modulo_m": 2.5, "tipo": "irregular"},
        "materiales_compatibles": ["enlucido/estuco blanco", "piedra local", "teja cerámica"],
        "solucion_cubierta": "inclinada (teja árabe)",
        "vuelo_maximo_m": 0.6,
        "textura": "rugosa",
    },
    "nordico": {
        "nombre_estilo": "Nórdico",
        "proporcion_huecos": {"ratio_alto_ancho": 1.2, "orientacion": "horizontal"},
        "ritmo_fachada": {"modulo_m": 3.0, "tipo": "regular"},
        "materiales_compatibles": ["madera (tablilla)", "vidrio", "metal oscuro"],
        "solucion_cubierta": "inclinada a dos aguas",
        "vuelo_maximo_m": 1.2,
        "textura": "mixta (madera natural)",
    },
    "industrial": {
        "nombre_estilo": "Industrial",
        "proporcion_huecos": {"ratio_alto_ancho": 1.6, "orientacion": "vertical"},
        "ritmo_fachada": {"modulo_m": 3.5, "tipo": "regular"},
        "materiales_compatibles": ["ladrillo visto", "acero", "vidrio armado"],
        "solucion_cubierta": "shed (diente de sierra)",
        "vuelo_maximo_m": 0.8,
        "textura": "rugosa",
    },
    "bioclimatico": {
        "nombre_estilo": "Bioclimático",
        "proporcion_huecos": {"ratio_alto_ancho": 1.4, "orientacion": "horizontal"},
        "ritmo_fachada": {"modulo_m": 2.5, "tipo": "irregular"},
        "materiales_compatibles": ["madera", "vegetación (fachada verde)", "vidrio baja emisividad"],
        "solucion_cubierta": "verde / inclinada con aleros de control solar",
        "vuelo_maximo_m": 1.5,
        "textura": "mixta",
    },
    "organico": {
        "nombre_estilo": "Orgánico",
        "proporcion_huecos": {"ratio_alto_ancho": 1.0, "orientacion": "vertical"},
        "ritmo_fachada": {"modulo_m": 2.0, "tipo": "irregular"},
        "materiales_compatibles": ["piedra natural", "madera curva", "hormigón moldeado"],
        "solucion_cubierta": "curva / orgánica",
        "vuelo_maximo_m": 1.5,
        "textura": "rugosa (natural)",
    },
    "minimalista": {
        "nombre_estilo": "Minimalista",
        "proporcion_huecos": {"ratio_alto_ancho": 1.5, "orientacion": "horizontal"},
        "ritmo_fachada": {"modulo_m": 3.5, "tipo": "regular"},
        "materiales_compatibles": ["hormigón pulido", "vidrio", "revestimiento liso monocromo"],
        "solucion_cubierta": "plana",
        "vuelo_maximo_m": 0.5,
        "textura": "lisa",
    },
    "clasico_contemporaneo": {
        "nombre_estilo": "Clásico contemporáneo",
        "proporcion_huecos": {"ratio_alto_ancho": 2.0, "orientacion": "vertical"},
        "ritmo_fachada": {"modulo_m": 3.0, "tipo": "jerarquico"},
        "materiales_compatibles": ["piedra natural", "estuco", "metal discreto"],
        "solucion_cubierta": "inclinada de baja pendiente con remate",
        "vuelo_maximo_m": 1.0,
        "textura": "lisa/pulida",
    },
    "deconstructivista": {
        "nombre_estilo": "Deconstructivista",
        "proporcion_huecos": {"ratio_alto_ancho": 1.0, "orientacion": "vertical"},
        "ritmo_fachada": {"modulo_m": 2.0, "tipo": "irregular"},
        "materiales_compatibles": ["metal", "vidrio", "hormigón (planos desalineados)"],
        "solucion_cubierta": "irregular / fragmentada",
        "vuelo_maximo_m": 2.0,
        "textura": "mixta (contrastada)",
    },
    "high_tech": {
        "nombre_estilo": "High-tech",
        "proporcion_huecos": {"ratio_alto_ancho": 1.4, "orientacion": "horizontal"},
        "ritmo_fachada": {"modulo_m": 4.0, "tipo": "regular"},
        "materiales_compatibles": ["acero", "vidrio", "aluminio", "elementos técnicos expuestos"],
        "solucion_cubierta": "plana / ligera (membrana tensada)",
        "vuelo_maximo_m": 1.8,
        "textura": "lisa/metálica",
    },
    "vernaculo": {
        "nombre_estilo": "Vernáculo",
        "proporcion_huecos": {"ratio_alto_ancho": 1.6, "orientacion": "vertical"},
        "ritmo_fachada": {"modulo_m": 2.5, "tipo": "irregular"},
        "materiales_compatibles": ["piedra local", "madera", "tapial/adobe", "teja tradicional"],
        "solucion_cubierta": "inclinada tradicional",
        "vuelo_maximo_m": 0.5,
        "textura": "rugosa (natural)",
    },
    "parametrico": {
        "nombre_estilo": "Paramétrico",
        "proporcion_huecos": {"ratio_alto_ancho": 1.0, "orientacion": "vertical"},
        "ritmo_fachada": {"modulo_m": 1.5, "tipo": "irregular"},
        "materiales_compatibles": ["paneles compuestos", "vidrio curvo", "fabricación digital"],
        "solucion_cubierta": "geometría compleja / curva",
        "vuelo_maximo_m": 2.0,
        "textura": "lisa con patrón geométrico",
    },
    "japandi": {
        "nombre_estilo": "Japandi",
        "proporcion_huecos": {"ratio_alto_ancho": 1.6, "orientacion": "horizontal"},
        "ritmo_fachada": {"modulo_m": 3.0, "tipo": "regular"},
        "materiales_compatibles": ["madera clara", "piedra", "vidrio/papel translúcido"],
        "solucion_cubierta": "plana / inclinada muy suave",
        "vuelo_maximo_m": 1.0,
        "textura": "lisa/natural mixta",
    },
}

DEFAULT_ESTILO = "racionalista"

SYSTEM_PROMPT = """Eres un arquitecto que traduce una descripción de estilo o carácter \
arquitectónico en lenguaje natural a parámetros compositivos concretos y evaluables.

Reglas estrictas:

1. Limítate a los parámetros compositivos pedidos por la herramienta (proporción de \
huecos, ritmo de fachada, materiales, solución de cubierta, vuelo máximo, textura). \
NUNCA inventes una referencia a un edificio real, un arquitecto, ni una norma o dato \
normativo — eso no es lo que se te pide y no puedes verificarlo.
2. Si la descripción combina varios estilos (p. ej. "brutalismo mediterráneo"), combina \
sus parámetros de forma coherente y razonada — no elijas uno solo arbitrariamente ni \
promedies sin criterio.
3. "vuelo_maximo_m" es un número realista en metros (entre 0.3 y 3.0 en la inmensa \
mayoría de los casos) — nunca un valor extremo sin que la descripción lo justifique \
explícitamente.
4. "nombre_estilo" debe describir con tus propias palabras el estilo interpretado, no \
copiar literalmente el texto de entrada.
"""


def _tool_schema() -> dict:
    return {
        "name": NOMBRE_HERRAMIENTA,
        "description": "Registra los parámetros compositivos de un estilo arquitectónico interpretado.",
        "input_schema": {
            "type": "object",
            "required": [
                "nombre_estilo", "proporcion_huecos", "ritmo_fachada",
                "materiales_compatibles", "solucion_cubierta", "vuelo_maximo_m", "textura",
            ],
            "properties": {
                "nombre_estilo": {"type": "string"},
                "proporcion_huecos": {
                    "type": "object",
                    "required": ["ratio_alto_ancho", "orientacion"],
                    "properties": {
                        "ratio_alto_ancho": {"type": "number"},
                        "orientacion": {"type": "string", "enum": list(ORIENTACIONES_HUECOS)},
                    },
                },
                "ritmo_fachada": {
                    "type": "object",
                    "required": ["modulo_m", "tipo"],
                    "properties": {
                        "modulo_m": {"type": "number"},
                        "tipo": {"type": "string", "enum": list(TIPOS_RITMO)},
                    },
                },
                "materiales_compatibles": {"type": "array", "items": {"type": "string"}},
                "solucion_cubierta": {"type": "string"},
                "vuelo_maximo_m": {"type": "number"},
                "textura": {"type": "string"},
            },
        },
    }


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return texto.lower().strip().replace("-", "_").replace(" ", "_")


class ErrorDeEstilo(Exception):
    """Fallo al interpretar una descripción libre por IA — sin API key, sin
    paquete `anthropic`, error de la API, rechazo del modelo, o una
    respuesta que no usa la herramienta forzada. Solo puede ocurrir en la
    rama de texto libre; una clave de catálogo nunca la levanta."""


def _buscar_en_catalogo(clave_o_descripcion: str) -> Optional[dict]:
    return CATALOGO_ESTILOS.get(_normalizar(clave_o_descripcion))


def obtener_estilo(clave_o_descripcion: str, client_anthropic=None) -> dict:
    """Resuelve un estilo por clave de catálogo (determinista, sin red) o,
    si no coincide con ninguno de los 14, interpreta la descripción libre
    con Claude. `client_anthropic` es un cliente `anthropic.Anthropic` ya
    inyectable (para tests, mockeado) — si no se da y hace falta llamar a
    la IA, se construye uno con `ANTHROPIC_API_KEY` del entorno.

    Levanta `ErrorDeEstilo` si la rama de IA falla — nunca en la rama de
    catálogo, que no puede fallar por definición (`CATALOGO_ESTILOS` es un
    dict fijo del propio módulo)."""
    de_catalogo = _buscar_en_catalogo(clave_o_descripcion)
    if de_catalogo is not None:
        return dict(de_catalogo)

    if anthropic is None:
        raise ErrorDeEstilo("el paquete «anthropic» no está instalado")

    cliente = client_anthropic
    if cliente is None:
        import os
        clave = os.environ.get("ANTHROPIC_API_KEY")
        if not clave:
            raise ErrorDeEstilo("falta ANTHROPIC_API_KEY")
        # Tarea 9: tiempo limite explicito. Ver analyzer/anthropic_cliente.py.
        cliente = crear_cliente(clave)

    herramienta = _tool_schema()
    try:
        respuesta = cliente.messages.create(
            model=MODEL,
            max_tokens=1024,
            # SYSTEM_PROMPT no cambia entre descripciones -- cachearlo no
            # cuesta nada, aunque (mismo caveat que pliego_extractor.py) no
            # hay que esperar ahorro real salvo reprocesar la misma
            # descripción dentro del TTL de caché: es una llamada por
            # descripción libre, no en bucle.
            system=[
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
            ],
            tools=[herramienta],
            tool_choice={"type": "tool", "name": NOMBRE_HERRAMIENTA},
            messages=[{
                "role": "user",
                "content": "Interpreta esta descripción de estilo/carácter arquitectónico: "
                            + clave_o_descripcion,
            }],
        )
    except anthropic.APIError as exc:
        raise ErrorDeEstilo("error de la API: %s" % exc) from exc

    if respuesta.stop_reason == "refusal":
        raise ErrorDeEstilo("el modelo rechazó la petición")

    bloque = next((b for b in respuesta.content if b.type == "tool_use"), None)
    if bloque is None:
        raise ErrorDeEstilo("el modelo no usó la herramienta forzada")

    return dict(bloque.input)


def aplicar_estilo_a_prompt(estilo_dict: dict, prompt_base: str) -> str:
    """Añade el bloque "DIRECTIVA DE ESTILO ARQUITECTÓNICO" al mensaje de
    usuario ya construido (`prompt_base`) — determinista, plantilla fija,
    sin IA. Se anexa al MENSAJE, nunca al `SYSTEM_PROMPT` de
    `ai_generator.py` (que sigue siendo la misma constante fija cacheada
    para todas las llamadas) — mismo criterio ya aplicado a "RESTRICCIONES
    DE CONCURSO" (`analyzer.pliego_conector`) y a "DIRECTIVAS ADICIONALES"
    (Fase F): tres bloques opcionales con el mismo mecanismo de inyección,
    nunca tres formas distintas de hacer lo mismo.

    `estilo_dict` vacío o `None` devuelve `prompt_base` sin cambios — un
    `generate_project()` sin estilo pedido queda exactamente igual que
    antes de que este módulo existiera."""
    if not estilo_dict:
        return prompt_base

    materiales = ", ".join(estilo_dict.get("materiales_compatibles") or []) or "sin especificar"
    huecos = estilo_dict.get("proporcion_huecos") or {}
    ritmo = estilo_dict.get("ritmo_fachada") or {}

    bloque = (
        "DIRECTIVA DE ESTILO ARQUITECTÓNICO: %s\n"
        "Aplica estos criterios compositivos SIEMPRE que sean compatibles con la normativa "
        "y las restricciones ya indicadas más arriba (nunca por encima de ellas):\n"
        "- Proporción de huecos: ratio alto/ancho %s, orientación predominante %s.\n"
        "- Ritmo de fachada: módulo de %s m, patrón %s.\n"
        "- Materiales compatibles: %s.\n"
        "- Solución de cubierta: %s.\n"
        "- Vuelo máximo de vuelos/balcones: %s m.\n"
        "- Textura de acabado: %s."
    ) % (
        estilo_dict.get("nombre_estilo", "(sin nombre)"),
        huecos.get("ratio_alto_ancho", "sin especificar"),
        huecos.get("orientacion", "sin especificar"),
        ritmo.get("modulo_m", "sin especificar"),
        ritmo.get("tipo", "sin especificar"),
        materiales,
        estilo_dict.get("solucion_cubierta", "sin especificar"),
        estilo_dict.get("vuelo_maximo_m", "sin especificar"),
        estilo_dict.get("textura", "sin especificar"),
    )
    return prompt_base + "\n\n" + bloque
