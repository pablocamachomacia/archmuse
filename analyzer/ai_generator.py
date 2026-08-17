"""Generación de un proyecto residencial completo con IA ("Generar
proyecto"), a partir de parámetros de solar, edificio, mix de viviendas y
normativa — sin ningún DXF de partida.

Claude actúa como arquitecto generador: propone una distribución en planta
(qué viviendas hay en cada planta, qué habitaciones tiene cada una, sus
dimensiones y su posición) que se convierte en los mismos `Room`/`Unit` que
produce `parser.py` a partir de un DXF real. Gracias a eso, el resto del
pipeline (`evaluator.evaluate_advanced_for_units`, `plan_svg.generate_plan_svg`,
`api_serializer.serialize_analysis`) puntúa y dibuja el proyecto generado
exactamente igual que un plano analizado — sin ningún camino de código
paralelo.
"""
from __future__ import annotations

import json
import logging
import os
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from shapely.geometry import Polygon

from .ai_analyst import _extract_json
from .estilos import aplicar_estilo_a_prompt
from .evaluator import (
    Unit,
    _normalize,
    evaluate_accessible_bathroom_area,
    evaluate_bathroom_accessibility,
    evaluate_natural_light,
)
from .parser import AREA_LAYER, Room

try:
    import anthropic
except ImportError:  # pragma: no cover - se avisa en tiempo de ejecución
    anthropic = None  # type: ignore[assignment]

MODEL = "claude-sonnet-5"

logger = logging.getLogger(__name__)

# Separación (en metros) entre los sistemas de coordenadas locales de cada
# vivienda generada: cada vivienda se traslada a su propio "carril" en X muy
# alejado de las demás, para que `evaluate_orientation`/`evaluate_proportions`
# (que miran habitaciones vecinas en todo el listado plano de `rooms`) nunca
# confundan una habitación de otra vivienda con una pared medianera real. El
# plano de cada vivienda se dibuja por separado (`generate_plan_svg`), así
# que este desplazamiento no afecta en nada a la visualización.
UNIT_OFFSET_M = 500.0

SYSTEM_PROMPT = """Eres un arquitecto experto en diseño de promociones residenciales en \
España. Se te dan los parámetros de un solar y un programa de necesidades \
(mix de viviendas, número de plantas, normativa urbanística), y debes \
proponer una distribución en planta completa y razonada.

Nomenclatura OBLIGATORIA de las habitaciones (escríbelas EXACTAMENTE así, \
con esas mayúsculas y acentos, para que el sistema de reglas automático del \
resto de la aplicación las reconozca):
- "Salón/cocina" (mínimo 20 m²)
- "Dormitorio 1", "Dormitorio 2", "Dormitorio 3" (usa tantos como \
dormitorios tenga esa vivienda; "Dormitorio 1" debe ser siempre el más \
grande, luego "Dormitorio 2", luego "Dormitorio 3" — mínimo 10 m² el \
primero, 8 m² el segundo y 6 m² el tercero)
- "Baño" (mínimo 3 m²); en viviendas de 3 dormitorios añade también un \
"Aseo" adicional
- "Terraza" y/o "Tendedero" cuando el diseño lo permita
- "Pasillo" (mínimo 1.0m de ancho, longitud según necesidad) como \
pieza opcional pero recomendada en viviendas de 2+ dormitorios

Cada vivienda debe tener exactamente tantos dormitorios como le corresponda \
según el mix de viviendas solicitado (viviendas de 1, 2 o 3 dormitorios).

Reglas de organización funcional dentro de cada vivienda:

- ZONA HÚMEDA (baño/aseo): debe estar adyacente a al menos un dormitorio. \
Nunca adyacente al salón/cocina directamente sin un pasillo de por medio. \
Agrúpalos en el mismo lado de la vivienda para compartir instalaciones.
- SALÓN/COCINA: debe ocupar la fachada con mejor orientación (sur/sureste \
según el azimut dado). Es la pieza de mayor tamaño — colócala primero y \
organiza el resto alrededor.
- DORMITORIOS: el Dormitorio 1 debe tener fachada exterior. Los demás \
pueden ser interiores. Deben ser accesibles desde una zona de circulación \
(pasillo o distribuidor), nunca atravesando el salón o la cocina.
- CIRCULACIÓN: en viviendas de 2 o más dormitorios, añade una \
habitación de tipo "Pasillo" (ancho mínimo 1.0m) que conecte la entrada \
con dormitorios y baños. En viviendas de 1 dormitorio es opcional. La \
entrada debe estar en el lado opuesto a la fachada principal (sur).

Ten en cuenta la orientación norte indicada (azimut en grados, sentido \
horario, 0 = "arriba" del plano = Norte) al orientar cada vivienda: el \
salón/cocina y el dormitorio principal deben mirar preferentemente a \
sur/sureste/este, evita orientarlos a norte. Respeta la superficie mínima \
por vivienda indicada y la ocupación máxima del solar. Si la planta baja es \
comercial, no le asignes viviendas residenciales: indícalo con \
"uso": "comercial" y una única habitación tipo "Local comercial" por local \
(o una lista de viviendas vacía).

PRECEDENCIA ENTRE REGLAS, si además se te proporcionan "DIRECTIVAS \
ADICIONALES" en este mensaje (ver más abajo, después de los datos del \
proyecto) — en este orden estricto, de mayor a menor autoridad:
1. La normativa urbanística indicada (ocupación, edificabilidad, \
retranqueos, plantas máximas) y la nomenclatura obligatoria de \
habitaciones de arriba SIEMPRE prevalecen sobre cualquier otra instrucción \
de este mensaje, sin excepción.
2. Una directiva marcada "DEBES CUMPLIR" tiene prioridad sobre las reglas \
de organización por defecto de este documento (p. ej. la orientación \
preferente sur/sureste del salón) — pero nunca puede anular ni contradecir \
el punto 1.
3. Si no hay ninguna directiva "DEBES CUMPLIR" que la sustituya, se aplica \
la regla de organización por defecto de este documento.
4. Una directiva marcada como preferencia ("intenta") se aplica solo si es \
compatible con todo lo anterior — nunca puede contradecir la normativa ni \
una directiva "DEBES CUMPLIR".

Responde ÚNICAMENTE con un objeto JSON válido (sin texto adicional antes ni \
después, sin bloques de código markdown) con exactamente esta forma. Escapa \
correctamente cualquier salto de línea (\\n) o comilla doble (\\") que \
aparezca dentro de un texto, especialmente en "justificacion":

{
  "justificacion": "<descripción de la distribución elegida: por qué esa \
organización por plantas, cómo se ajusta a la normativa y al solar>",
  "plantas": [
    {
      "planta": 1,
      "uso": "residencial",
      "viviendas": [
        {
          "nombre": "1ºA",
          "habitaciones": [
            {"nombre": "Salón/cocina", "ancho": 5.5, "largo": 4.2},
            {"nombre": "Dormitorio 1", "ancho": 4.0, "largo": 3.5},
            {"nombre": "Baño",         "ancho": 2.0, "largo": 1.8},
            {"nombre": "Pasillo",      "ancho": 1.2, "largo": 3.0}
          ]
        }
      ]
    }
  ]
}

"ancho" y "largo" son las dimensiones en metros del rectángulo de esa \
habitación."""


class GenerationError(Exception):
    """Fallo al generar el proyecto (sin API key, error de red, respuesta
    no interpretable como JSON, o sin ninguna vivienda válida). Se atrapa en
    `app.py` y se convierte en una respuesta JSON de error para la SPA."""


@dataclass
class GeneratedProject:
    units: List[Unit] = field(default_factory=list)
    rooms: List[Room] = field(default_factory=list)
    justificacion: str = ""
    # Viviendas cuya geometría no pasó `_validate_unit` tras el reintento —
    # el proyecto se acepta igualmente, pero el arquitecto debe revisarlas
    # a mano. Lista de strings "nombre vivienda: error1; error2".
    advertencias: List[str] = field(default_factory=list)
    # --- Fase F (integración con el generador) --------------------------
    # Nada de esto se usa si `params` no trae `contexto_cualitativo` — en
    # ese caso quedan todos en su valor por defecto (lista vacía / None /
    # False), exactamente como antes de esta fase.
    #
    # Directivas ya validadas (`_validar_directivas`) que de verdad se
    # anexaron al prompt — plano de dicts, no dataclasses de
    # `analyzer.interview.modelo`: este módulo sigue sin importar ese
    # paquete (aislamiento de una sola dirección, ver docstring del
    # módulo). Quien construya una `TrazaDeGeneracion` a partir de esto
    # (app.py) es responsable de convertir la forma.
    directivas_aplicadas: List[dict] = field(default_factory=list)
    # Resultado de `verificar_directivas_duras()` — una entrada por cada
    # directiva `fuerza="dura"` recibida (verificable o no), nunca solo las
    # incumplidas: la trazabilidad (Fase F, tarea D) necesita también las
    # que sí cumplieron y las que no se pudieron comprobar.
    verificaciones_directivas: List[dict] = field(default_factory=list)
    # None si no hubo reintento; si lo hubo, por qué motivo(s) lo disparó
    # — "geometria" (el mecanismo ya existente), "directiva_dura" (nuevo en
    # esta fase), o "geometria+directiva_dura" si ambos a la vez.
    reintento_disparado_por: Optional[str] = None
    # Contrato §9: lista opcional de `especificacion_id` que Claude declara
    # haber tenido en cuenta — `None` si Claude no la incluyó (la mayoría
    # de las veces, incluida siempre que no haya `contexto_cualitativo`).
    # Autoinforme del LLM, nunca una prueba determinista de cumplimiento
    # (ver `verificar_directivas_duras` para la única fuente fiable).
    referencias_especificacion: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Fase F — Directivas cualitativas del entrevistador (contrato §5-§8)
# ---------------------------------------------------------------------------
# `params["contexto_cualitativo"]` es la ÚNICA clave nueva y opcional que
# gana `params` en esta fase (contrato §5-§6.2, PRD v2 §30). Deliberadamente
# NO se importa `analyzer.interview.modelo` aquí: el catálogo cerrado de
# categorías/fuerzas se duplica como dos tuplas literales (mismo criterio
# que cualquier otro catálogo cerrado del proyecto) para que este módulo
# siga sin depender del paquete `interview` — el plan de implementación fija
# expresamente que la Fase F es la única que conoce `ai_generator.py`, no al
# revés.
#
# Principio de seguridad de esta sección (regla explícita de la Fase F: "no
# pasar al prompt categorías desconocidas ni texto arbitrario sin haber
# pasado por el compilador"): `/api/generar` es un endpoint HTTP público, no
# solo alcanzable desde el entrevistador — cualquier cliente podría mandar un
# `contexto_cualitativo` a mano. Por eso este módulo NUNCA reenvía tal cual
# el `texto_prompt` que llegue del cliente (aunque `contexto_cualitativo`
# transporte uno, calculado por `analyzer.interview.compilador` para el
# resumen de la Fase E): reconstruye el bloque de prompt él mismo, de forma
# determinista, a partir únicamente de las directivas individuales que pasen
# la validación de catálogo cerrado — la misma plantilla del contrato §8.2,
# reimplementada aquí en vez de confiar en un string ya compuesto.

CATEGORIAS_DIRECTIVA_VALIDAS = ("no_negociable", "privacidad", "accesibilidad", "caracter", "relacion_espacial")
FUERZAS_DIRECTIVA_VALIDAS = ("dura", "blanda")


def _validar_directivas(contexto_cualitativo) -> List[dict]:
    """Filtra `contexto_cualitativo.get("directivas")` a una lista de dicts
    bien formados: `categoria` y `fuerza` dentro del catálogo cerrado de
    arriba, `especificacion_id`/`texto_prompt` no vacíos. Cualquier entrada
    que no sea un dict, con una categoría/fuerza fuera de catálogo, o sin
    `texto_prompt` legible, se descarta en silencio — nunca llega al prompt.
    `contexto_cualitativo` ausente, `None`, o de forma inesperada -> lista
    vacía, nunca un error (mismo criterio tolerante que el resto de
    `_parse_generar_params`/`ai_generator.py` con datos de entrada)."""
    if not isinstance(contexto_cualitativo, dict):
        return []
    crudas = contexto_cualitativo.get("directivas")
    if not isinstance(crudas, list):
        return []
    validas: List[dict] = []
    for d in crudas:
        if not isinstance(d, dict):
            continue
        categoria = d.get("categoria")
        fuerza = d.get("fuerza")
        texto_prompt = d.get("texto_prompt")
        especificacion_id = d.get("especificacion_id")
        if categoria not in CATEGORIAS_DIRECTIVA_VALIDAS:
            continue
        if fuerza not in FUERZAS_DIRECTIVA_VALIDAS:
            continue
        if not isinstance(texto_prompt, str) or not texto_prompt.strip():
            continue
        if not isinstance(especificacion_id, str) or not especificacion_id.strip():
            continue
        texto_origen = d.get("texto_origen")
        validas.append({
            "especificacion_id": especificacion_id.strip(),
            "categoria": categoria,
            "fuerza": fuerza,
            "texto_origen": texto_origen.strip() if isinstance(texto_origen, str) and texto_origen.strip() else "(sin texto de origen)",
            "texto_prompt": texto_prompt.strip(),
            "verificable_geometricamente": bool(d.get("verificable_geometricamente", False)),
        })
    return validas


def _compilar_bloque_directivas(directivas: List[dict]) -> str:
    """Plantilla determinista del contrato §8.2 — misma forma exacta que
    `analyzer.interview.compilador._compilar_texto_prompt()` produce para el
    resumen de la Fase E, pero calculada aquí de forma independiente a
    partir de la lista ya validada (nunca a partir de un `texto_prompt` que
    llegara ya compuesto del cliente — ver docstring de la sección). Una
    subsección vacía nunca se imprime; sin directivas duras ni blandas,
    devuelve `""` (nada que anexar al mensaje)."""
    duras = [d["texto_prompt"] for d in directivas if d["fuerza"] == "dura"]
    blandas = [d["texto_prompt"] for d in directivas if d["fuerza"] == "blanda"]
    if not duras and not blandas:
        return ""
    bloques = ["DIRECTIVAS ADICIONALES DEL ARQUITECTO QUE ENCARGA EL PROYECTO:"]
    if duras:
        bloques.append("\nDEBES CUMPLIR:\n" + "\n".join("- %s" % t for t in duras))
    if blandas:
        bloques.append(
            "\nPREFERENCIAS DE DISEÑO (aplícalas si son compatibles con lo anterior):\n"
            + "\n".join("- %s" % t for t in blandas)
        )
    return "\n".join(bloques)


def _compilar_bloque_restricciones_concurso(restricciones: List[str]) -> str:
    """Plantilla determinista, sin IA — mismo criterio que
    `_compilar_bloque_directivas`. `params["restricciones_concurso"]` es la
    clave nueva y opcional que añade `analyzer.pliego_conector.
    pliego_a_params()`: una lista de strings ya filtrados por confianza
    Alta/Media (ese módulo decide qué entra, no éste). Vacía o ausente ->
    `""` (nada que anexar) — un `generate_project()` sin pliego de por
    medio queda exactamente igual que siempre.

    Se anexa al MENSAJE DE USUARIO, no al `SYSTEM_PROMPT` (que sigue siendo
    la misma constante fija para todas las llamadas, cacheada) — mismo
    mecanismo que ya usa `_compilar_bloque_directivas`/`contexto_
    cualitativo` desde la Fase F. El `SYSTEM_PROMPT` ya anticipa un bloque
    así en el mensaje ("si además se te proporcionan..."), así que no hace
    falta tocar su texto para que esto tenga efecto."""
    if not restricciones:
        return ""
    return (
        "RESTRICCIONES DE CONCURSO (extraídas del pliego de condiciones del concurso):\n"
        "Tienen la MISMA autoridad que la normativa urbanística del punto 1 de "
        "\"PRECEDENCIA ENTRE REGLAS\" de arriba — son requisitos del pliego al que se "
        "concursa, no preferencias de diseño ni directivas del arquitecto.\n"
        + "\n".join("- %s" % r for r in restricciones)
    )


def _compilar_bloque_intervencion(intervencion) -> str:
    """Plantilla determinista, sin IA — mismo criterio que
    `_compilar_bloque_directivas`/`_compilar_bloque_restricciones_concurso`.
    `params["intervencion_existente"]` es la clave nueva y opcional que
    añade `analyzer.interview.compilador.compilar_params()` (a partir de
    `parcela.tipo_intervencion`/`parcela.elementos_a_conservar`, modo
    experto) y que `app.py:_parse_generar_params` reenvía tal cual si el
    body la trae. Forma esperada: `{"tipo": "obra_nueva" | "edificacion_
    existente", "elementos_a_conservar": str | None}`.

    Cualquier entrada que no sea exactamente `tipo == "edificacion_
    existente"` (ausente, `None`, dict sin esa clave, `tipo` con basura,
    o el propio "obra_nueva") se trata como "no hay intervención sobre
    edificación existente" y no añade nada al mensaje — mismo
    comportamiento byte a byte de siempre para el 100% de las llamadas
    anteriores a esta capacidad."""
    if not isinstance(intervencion, dict) or intervencion.get("tipo") != "edificacion_existente":
        return ""
    conservar = intervencion.get("elementos_a_conservar")
    conservar = conservar.strip() if isinstance(conservar, str) and conservar.strip() else None
    lineas = [
        "INTERVENCIÓN EN EDIFICACIÓN EXISTENTE:",
        "Esta parcela NO está vacía: ya existe una edificación construida sobre ella. "
        "No generes el proyecto como una obra nueva partiendo de un solar libre — respeta "
        "la huella y la envolvente de la edificación existente (superficie ocupada, forma "
        "general en planta, número de plantas ya construido) y plantea el proyecto como una "
        "intervención de rehabilitación, reforma o ampliación sobre esa base.",
    ]
    if conservar:
        lineas.append("Lo que el usuario indica que debe conservarse o demolerse: \"%s\"." % conservar)
    else:
        lineas.append(
            "El usuario no ha especificado qué elementos conservar o demoler; plantea tú una "
            "estrategia de intervención razonable (p. ej. conservar estructura y fachadas, "
            "reorganizar la distribución interior) y hazla explícita en la justificación del proyecto."
        )
    return "\n".join(lineas)


def _build_user_message(params: dict) -> str:
    solar = params["solar"]
    edificio = params["edificio"]
    mix = params["mix_viviendas"]
    normativa = params["normativa"]
    proyecto = params["proyecto"]

    plantas_residenciales = edificio["plantas"] - (1 if edificio["planta_baja_comercial"] else 0)
    total_viviendas = mix["dorm_1"] + mix["dorm_2"] + mix["dorm_3"]

    datos = {
        "proyecto": proyecto,
        "solar": solar,
        "edificio": edificio,
        "mix_viviendas": mix,
        "normativa": normativa,
        "plantas_residenciales_a_repartir": max(plantas_residenciales, 0),
        "total_viviendas_a_distribuir": total_viviendas,
    }
    ciudad = proyecto.get("ciudad") or "(sin especificar)"
    tipologia = proyecto.get("tipologia") or "plurifamiliar"
    zona_cte = proyecto.get("zona_cte") or "C"
    mensaje = (
        f"Genera la propuesta de distribución para este proyecto "
        f"{tipologia} en {ciudad} (zona climática CTE {zona_cte}).\n"
        f"Adapta las decisiones de diseño al clima de la zona {zona_cte}: "
        f"{'prioriza protección solar y ventilación cruzada' if zona_cte in ('A', 'B') else 'prioriza inercia térmica y orientación sur'}.\n\n"
        "Datos del proyecto (JSON):\n\n" + json.dumps(datos, ensure_ascii=False, indent=2)
    )
    # Contrato §8.2: la sección de directivas va DESPUÉS del bloque JSON de
    # datos, nunca mezclada dentro de él — así un parser (o un lector
    # humano) nunca confunde prosa con datos estructurados. Si no hay
    # ninguna directiva válida (incluido el caso `contexto_cualitativo`
    # ausente, que es el 100% de las llamadas de antes de esta fase), el
    # mensaje queda exactamente igual que siempre.
    bloque_restricciones = _compilar_bloque_restricciones_concurso(params.get("restricciones_concurso") or [])
    if bloque_restricciones:
        mensaje += "\n\n" + bloque_restricciones

    bloque_directivas = _compilar_bloque_directivas(_validar_directivas(params.get("contexto_cualitativo")))
    if bloque_directivas:
        mensaje += "\n\n" + bloque_directivas

    bloque_intervencion = _compilar_bloque_intervencion(params.get("intervencion_existente"))
    if bloque_intervencion:
        mensaje += "\n\n" + bloque_intervencion

    # Núcleo de comunicación vertical (docs/prd/2026-08-17-nucleo-comunicacion-fachada-generador.md):
    # estimación de viviendas/planta a partir de los mismos totales que ya calcula este mensaje más
    # arriba -- el reparto real por planta lo decide Claude, así que esto es una orientación, no una
    # instrucción que se vaya a verificar geométricamente tal cual (la pieza que sí se verifica/impone
    # es `_construir_unidad_nucleo`, en `_parse_generated_units`, con el recuento real de cada planta).
    if plantas_residenciales > 0:
        viviendas_por_planta_estimado = round(total_viviendas / plantas_residenciales)
        bloque_nucleo = _compilar_bloque_nucleo(_dimensionar_nucleo_comunicacion(viviendas_por_planta_estimado))
        if bloque_nucleo:
            mensaje += "\n\n" + bloque_nucleo

    # Motor de estilos (`analyzer.estilos`): `params["estilo_dict"]` lo
    # resuelve `app.py` ANTES de llamar a `generate_project` (por clave de
    # catálogo, determinista, o por IA si es texto libre que no encaja con
    # ninguna) -- este módulo solo aplica la plantilla fija, nunca decide
    # ni llama a Claude por su cuenta. Ausente -> el mensaje no cambia ni
    # un carácter (mismo criterio que los dos bloques de arriba).
    mensaje = aplicar_estilo_a_prompt(params.get("estilo_dict"), mensaje)
    return mensaje


def _room_from_dict(d: dict, offset_x: float) -> Optional[Room]:
    if not isinstance(d, dict):
        return None
    nombre = str(d.get("nombre") or "").strip()
    try:
        ancho = float(d.get("ancho", 0))
        largo = float(d.get("largo", 0))
        x = float(d.get("x", 0)) + offset_x
        y = float(d.get("y", 0))
    except (TypeError, ValueError):
        return None
    if not nombre or ancho <= 0 or largo <= 0:
        return None

    polygon = Polygon([(x, y), (x + ancho, y), (x + ancho, y + largo), (x, y + largo)])
    return Room(label=nombre, polygon=polygon, layer=AREA_LAYER)


_SUR_NAMES = {"Salón/cocina", "Dormitorio 1", "Terraza"}
_NORTE_ORDER = ["Dormitorio 2", "Dormitorio 3", "Baño", "Aseo", "Tendedero"]
_NORTE_ORDER_INDEX = {name: i for i, name in enumerate(_NORTE_ORDER)}
_PASILLO_NAME = "Pasillo"
_COMERCIAL_NAME = "Local comercial"

_MIN_UNIT_WIDTH_M = 6.0
# Tope al factor de estiramiento (ver `_stretch_row`): mejor dejar un
# margen vacío al final de una zona que una habitación con proporciones
# imposibles (p. ej. un salón único forzado a cubrir él solo el ancho de
# una zona norte con tres dormitorios).
_MAX_STRETCH_FACTOR = 2.0
# Área máxima "objetivo" del pasillo (ancho ya fijado = ancho total de la
# vivienda, así que esto limita su "largo") — pero nunca por debajo de
# _MIN_PASILLO_DEPTH_M: en viviendas muy anchas (>8m) el pasillo supera
# los 8m², es el coste inevitable de que siga siendo transitable.
_PASILLO_MAX_AREA_M2 = 8.0
_MIN_PASILLO_DEPTH_M = 1.0
# Ninguna habitación (salvo Pasillo y Local comercial, que tienen sus
# propias reglas) puede tener un lado más de 2x el otro.
_MAX_ROOM_ASPECT_RATIO = 2.0

# ---------------------------------------------------------------------------
# Núcleo de comunicación vertical (docs/prd/2026-08-17-nucleo-comunicacion-
# fachada-generador.md, aprobado)
# ---------------------------------------------------------------------------
# Ascensor + hueco de escalera + distribuidor común, obligatorio en toda
# planta con 2 o más viviendas (sin él, un edificio plurifamiliar generado no
# tiene forma física de subir de planta ni de dar acceso desde zona común a
# cada vivienda — ver §1 del PRD). El tamaño es una ESTIMACIÓN RAZONADA, no
# una cifra normativa verificada: este proyecto no tiene hoy un corpus CTE
# DB-SUA (accesibilidad, dimensiones mínimas de escalera protegida/foso de
# ascensor) confirmado como fuente de verdad — mismo criterio que la
# superficie mínima de vivienda "por tipología, no por comunidad autónoma"
# del Programa de Necesidades (PRD §9/§14: fijar una cifra sin esa base sería
# fabricar precisión que no existe). Escalona en 3 tramos según el nº de
# viviendas de la planta -- más viviendas, distribuidor más largo -- sin
# pretender más precisión de la que este dato soporta.
_NUCLEO_ANCHO_M = 2.4  # ascensor + hueco de escalera compacta -- mismo ancho en los 3 tramos
_NUCLEO_TRAMOS_LARGO = (
    (2, 3.3),  # hasta 2 viviendas/planta -> ~8 m²
    (4, 5.0),  # 3-4 viviendas/planta -> ~12 m²
)
_NUCLEO_LARGO_MAX_M = 6.7  # 5+ viviendas/planta -> ~16 m²
_NUCLEO_ROOM_NAME = "Núcleo de comunicación"


def _dimensionar_nucleo_comunicacion(num_viviendas: int) -> Optional[dict]:
    """Determinista, NUNCA decidido por Claude (objetivo técnico §4.1 del
    PRD): el tamaño lo fija este código antes y después de la llamada a la
    IA, siempre a partir únicamente de `num_viviendas`. `None` si la planta
    tiene menos de 2 viviendas -- no hace falta compartir núcleo (PRD §5,
    caso de uso 2), y no se inventa uno donde no hace falta."""
    if num_viviendas < 2:
        return None
    largo = _NUCLEO_LARGO_MAX_M
    for umbral, largo_tramo in _NUCLEO_TRAMOS_LARGO:
        if num_viviendas <= umbral:
            largo = largo_tramo
            break
    return {
        "ancho_m": _NUCLEO_ANCHO_M,
        "largo_m": largo,
        "area_m2": _NUCLEO_ANCHO_M * largo,
    }


def _construir_unidad_nucleo(nucleo: dict, unit_index: int, floor_label: str) -> Unit:
    """Vivienda "vacía" que representa el núcleo de comunicación de una
    planta -- misma convención que `_COMERCIAL_NAME` ("Local comercial") para
    dar de alta una unidad no residencial dentro de `project.units`: así
    aparece como estancia propia en el plano 2D (criterio de aceptación §8.1
    del PRD) sin que ninguna regla de vivienda residencial (superficie
    mínima, nomenclatura de dormitorios/salón) la evalúe -- su único room no
    coincide con ninguno de esos patrones, así que ni `evaluate_natural_
    light` ni el resto de `evaluator.py` la tratan como una pieza que deba
    cumplir esas reglas.

    Nunca la genera Claude: se construye aquí, en `_parse_generated_units`,
    después de conocer el número REAL de viviendas que la IA puso en esa
    planta -- más preciso que la estimación previa a la llamada (ver
    `_compilar_bloque_nucleo`), y sigue siendo 100% código, nunca criterio
    del LLM."""
    offset_x = unit_index * UNIT_OFFSET_M
    ancho, largo = nucleo["ancho_m"], nucleo["largo_m"]
    polygon = Polygon([(offset_x, 0), (offset_x + ancho, 0), (offset_x + ancho, largo), (offset_x, largo)])
    room = Room(label=_NUCLEO_ROOM_NAME, polygon=polygon, layer=AREA_LAYER)
    return Unit(name=f"{floor_label} · Núcleo de comunicación", rooms=[room])


def _compilar_bloque_nucleo(nucleo: Optional[dict]) -> str:
    """Instrucción determinista (sin IA), mismo criterio que `_compilar_
    bloque_directivas`: comunica a Claude un tamaño YA FIJADO por código
    (`_dimensionar_nucleo_comunicacion`), nunca le pide que lo invente ni que
    decida su superficie. `nucleo` es la estimación previa a la llamada,
    calculada en `_build_user_message` a partir de `total_viviendas /
    plantas_residenciales` -- una aproximación, porque el reparto real por
    planta lo decide Claude en su respuesta; el núcleo que de verdad se
    añade al resultado (`_construir_unidad_nucleo`) se redimensiona después
    con el recuento real de cada planta, así que un desajuste aquí no deja
    ninguna planta sin núcleo ni con uno mal dimensionado en el resultado
    final -- esta instrucción solo orienta a Claude para que dimensione bien
    sus viviendas, no determina la geometría final."""
    if not nucleo:
        return ""
    return (
        "NÚCLEO DE COMUNICACIÓN VERTICAL (obligatorio en TODA planta residencial con 2 o más "
        "viviendas):\n"
        f"Reserva en cada una de esas plantas un núcleo de ascensor + escalera + distribuidor común "
        f"de aproximadamente {nucleo['ancho_m']:.1f} x {nucleo['largo_m']:.1f} m "
        f"({nucleo['area_m2']:.0f} m²). NO lo dibujes como habitación de ninguna vivienda ni le "
        "asignes superficie de ninguna vivienda -- es una superficie COMÚN que el sistema añade "
        "aparte, fuera de esta lista de habitaciones. La superficie útil que repartas entre las "
        "viviendas de esa planta debe quedar reducida en esa misma cantidad respecto al total "
        "disponible -- diseña viviendas más compactas si hace falta, nunca ignores esta reserva."
    )


def _stretch_row(rooms: List[dict], total_width: float, y: float) -> List[dict]:
    """Coloca `rooms` en fila (izquierda a derecha, a la altura `y`)
    estirando el "ancho" de cada una proporcionalmente para acercarse a
    `total_width`, sin superar `_MAX_STRETCH_FACTOR` el ancho original de
    ninguna pieza — si el tope no llega a cubrir `total_width`, la fila
    simplemente queda más corta (el margen sobrante queda vacío a la
    derecha, no se rellena con nada). El "largo" (profundidad) no se toca."""
    sum_ancho = sum(float(r.get("ancho", 0)) for r in rooms)
    if sum_ancho <= 0:
        return []
    scale = min(total_width / sum_ancho, _MAX_STRETCH_FACTOR)
    placed = []
    cursor_x = 0.0
    for r in rooms:
        ancho = float(r.get("ancho", 0)) * scale
        placed.append({**r, "ancho": ancho, "x": cursor_x, "y": y})
        cursor_x += ancho
    return placed


def _clamp_room_proportions(habitaciones: list[dict]) -> list[dict]:
    """Ajusta ancho/largo de cada habitación (excepto Pasillo y Local
    comercial, que tienen sus propias reglas de proporciones) para que
    ningún lado supere `_MAX_ROOM_ASPECT_RATIO` veces el otro — antes de
    clasificarlas en zonas o colocarlas."""
    adjusted = []
    for h in habitaciones:
        if h.get("nombre") in (_PASILLO_NAME, _COMERCIAL_NAME):
            adjusted.append(h)
            continue
        ancho = float(h.get("ancho", 0))
        largo = float(h.get("largo", 0))
        if largo > 0 and ancho / largo > _MAX_ROOM_ASPECT_RATIO:
            largo = ancho / _MAX_ROOM_ASPECT_RATIO
        elif ancho > 0 and largo / ancho > _MAX_ROOM_ASPECT_RATIO:
            ancho = largo / _MAX_ROOM_ASPECT_RATIO
        adjusted.append({**h, "ancho": ancho, "largo": largo})
    return adjusted


def place_rooms(habitaciones: list[dict]) -> list[dict]:
    """Layout geométrico en Python (Camino B) por zonas funcionales: zona
    sur (salón/cocina + terraza/tendedero, fachada principal), zona central
    (pasillo, franja horizontal completa entre sur y norte) y zona norte
    (dormitorios + baño/aseo). El ancho total de la vivienda es el máximo
    de lo que pida cada zona; las piezas de cada zona se estiran en ancho
    para acercarse a ese total sin huecos horizontales entre zonas, pero
    nunca más de `_MAX_STRETCH_FACTOR` (2x) su ancho original — ver
    `_stretch_row`. Un "Local comercial" no tiene zonas: ocupa la parcela
    completa él solo, sin estirarse.
    """
    habitaciones = [h for h in habitaciones if isinstance(h, dict)]
    if not habitaciones:
        return []

    habitaciones = _clamp_room_proportions(habitaciones)

    if any(h.get("nombre") == _COMERCIAL_NAME for h in habitaciones):
        placed = []
        cursor_x = 0.0
        for h in habitaciones:
            placed.append({**h, "x": cursor_x, "y": 0.0})
            cursor_x += float(h.get("ancho", 0))
        return placed

    sur, pasillo, norte = [], [], []
    for h in habitaciones:
        nombre = h.get("nombre")
        if nombre in _SUR_NAMES:
            sur.append(h)
        elif nombre == _PASILLO_NAME:
            pasillo.append(h)
        else:
            norte.append(h)
    norte.sort(key=lambda h: _NORTE_ORDER_INDEX.get(h.get("nombre"), len(_NORTE_ORDER)))

    # Dormitorio 1 vive en zona sur (junto al salón) para tener fachada sur.
    # Se ajusta AQUÍ, antes de calcular total_width, no después de
    # `_stretch_row`: si se hiciera después, el ancho ya lo habría fijado
    # `_stretch_row` reescalando la fila para encajar en un total_width que
    # no contaba con este ajuste, y el ensanche posterior invadiría a la
    # siguiente pieza de la fila (solape real). Aplicándolo aquí, el ancho
    # ya corregido entra en el cálculo de `total_width` — que por ser un
    # `max(...)` nunca puede quedar por debajo del ancho de zona sur, así
    # que el factor de reescalado de esa fila nunca es < 1 y el margen
    # nunca se deshace.
    altura_sur = max((float(h.get("largo", 0)) for h in sur), default=0.0)

    def _fix_dormitorio1(h: dict) -> dict:
        if h.get("nombre") != "Dormitorio 1":
            return h
        h = {**h, "largo": altura_sur}
        if h["largo"] >= float(h.get("ancho", 0)):
            h = {**h, "ancho": h["largo"] + 0.1}
        return h

    sur = [_fix_dormitorio1(h) for h in sur]

    sur_width = sum(float(h.get("ancho", 0)) for h in sur)
    pasillo_width = max((float(h.get("ancho", 0)) for h in pasillo), default=0.0)
    norte_width = sum(float(h.get("ancho", 0)) for h in norte)
    total_width = max(sur_width, pasillo_width, norte_width, _MIN_UNIT_WIDTH_M)

    placed = _stretch_row(sur, total_width, y=0.0)

    altura_pasillo = 0.0
    if pasillo:
        # Sin tope de estiramiento en ancho a propósito: el pasillo es una
        # franja de circulación, no una habitación — que cubra siempre el
        # ancho total de la vivienda es correcto arquitectónicamente (a
        # diferencia de un salón o dormitorio, para los que sí aplica
        # `_MAX_STRETCH_FACTOR` en `_stretch_row`). En "largo" hay un tope
        # de área objetivo, pero nunca por debajo de `_MIN_PASILLO_DEPTH_M`
        # — mejor superar el área que un pasillo intransitable.
        largo_claude = max(float(h.get("largo", 0)) for h in pasillo)
        largo_pasillo = max(min(largo_claude, _PASILLO_MAX_AREA_M2 / total_width), _MIN_PASILLO_DEPTH_M)
        altura_pasillo = largo_pasillo
        placed.append(
            {**pasillo[0], "ancho": total_width, "largo": largo_pasillo, "x": 0.0, "y": altura_sur}
        )

    placed.extend(_stretch_row(norte, total_width, y=altura_sur + altura_pasillo))

    return placed


def _unit_from_dict(d: dict, unit_index: int, floor_label: str) -> Optional[Unit]:
    if not isinstance(d, dict):
        return None
    nombre = str(d.get("nombre") or f"Vivienda {unit_index + 1}").strip()
    offset_x = unit_index * UNIT_OFFSET_M

    habitaciones = place_rooms(d.get("habitaciones") or [])
    rooms = [
        room
        for room_dict in habitaciones
        if (room := _room_from_dict(room_dict, offset_x)) is not None
    ]
    if not rooms:
        return None
    return Unit(name=f"{floor_label} · {nombre}", rooms=rooms)


def _parse_generated_units(data: dict) -> List[Unit]:
    units: List[Unit] = []
    for planta in data.get("plantas") or []:
        if not isinstance(planta, dict):
            continue
        floor_label = f"Planta {planta.get('planta', '?')}"
        floor_start = len(units)
        for vivienda_dict in planta.get("viviendas") or []:
            unit = _unit_from_dict(vivienda_dict, len(units), floor_label)
            if unit is not None:
                units.append(unit)

        # Núcleo de comunicación vertical (docs/prd/2026-08-17-nucleo-comunicacion-fachada-
        # generador.md, objetivo técnico §4.1/§4.2): determinista, se añade AQUÍ -- después de conocer
        # el número REAL de viviendas que Claude puso en esta planta, nunca a partir de lo que Claude
        # diga en su JSON (esa clave no existe en el esquema de respuesta, ver SYSTEM_PROMPT). Un
        # "Local comercial" (`_COMERCIAL_NAME`) no cuenta como vivienda -- una planta comercial no
        # reserva núcleo por este motivo (sigue subiendo por el núcleo de las plantas residenciales
        # de encima, que si las hay, sí lo reservan).
        viviendas_en_planta = sum(
            1 for u in units[floor_start:] if not any(r.label == _COMERCIAL_NAME for r in u.rooms)
        )
        nucleo = _dimensionar_nucleo_comunicacion(viviendas_en_planta)
        if nucleo is not None:
            units.append(_construir_unidad_nucleo(nucleo, len(units), floor_label))
    return units


# ---------------------------------------------------------------------------
# Validación geométrica del resultado de Claude
# ---------------------------------------------------------------------------
# Claude puede describir en la "justificacion" una organización funcional
# correcta y aun así devolver coordenadas que no la cumplen (solapes,
# adyacencias incorrectas) — un LLM razona en lenguaje natural sobre
# números, no puede garantizar geometría válida. Esto valida en código,
# con Shapely, lo que el prompt solo puede pedir.

_OVERLAP_MIN_AREA_M2 = 0.05
_ADJACENCY_MIN_LENGTH_M = 0.3

_BANO_PATTERN = re.compile(r"BANO|ASEO")
_SALON_PATTERN = re.compile(r"SALON|COCINA")
_PASILLO_PATTERN = re.compile(r"PASILLO")
_DORMITORIO_PATTERN = re.compile(r"DORMITORIO")


def _shared_edge_length(a: Polygon, b: Polygon) -> float:
    """Longitud del tramo de borde que comparten dos polígonos (0 si no se
    tocan o solo se tocan en un punto/esquina)."""
    return a.boundary.intersection(b.boundary).length


def _is_adjacent(a: Polygon, b: Polygon) -> bool:
    return _shared_edge_length(a, b) > _ADJACENCY_MIN_LENGTH_M


def _validate_unit(unit: Unit) -> List[str]:
    """Comprueba la geometría de una vivienda generada contra las reglas
    del prompt (sin solapes; zona húmeda no directa al salón; dormitorios
    accesibles desde el pasillo). Devuelve la lista de errores encontrados
    (vacía si la vivienda es válida)."""
    errors: List[str] = []
    rooms = unit.rooms

    # a) Solapes entre cualquier par de habitaciones
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            room_a, room_b = rooms[i], rooms[j]
            overlap_area = room_a.polygon.intersection(room_b.polygon).area
            if overlap_area > _OVERLAP_MIN_AREA_M2:
                label_a = room_a.label or "(sin etiqueta)"
                label_b = room_b.label or "(sin etiqueta)"
                errors.append(f"Solape entre {label_a} y {label_b}: {overlap_area:.2f}m²")

    banos = [r for r in rooms if r.label and _BANO_PATTERN.search(_normalize(r.label))]
    salones = [r for r in rooms if r.label and _SALON_PATTERN.search(_normalize(r.label))]
    pasillos = [r for r in rooms if r.label and _PASILLO_PATTERN.search(_normalize(r.label))]
    dormitorios = [r for r in rooms if r.label and _DORMITORIO_PATTERN.search(_normalize(r.label))]

    # b) Baño/Aseo adyacente directo al salón, sin pasillo de por medio
    for bano in banos:
        adjacent_to_salon = any(_is_adjacent(bano.polygon, s.polygon) for s in salones)
        adjacent_to_pasillo = any(_is_adjacent(bano.polygon, p.polygon) for p in pasillos)
        if adjacent_to_salon and not adjacent_to_pasillo:
            errors.append("Baño/Aseo adyacente directo a Salón/cocina")

    # c) Dormitorios sin acceso desde el pasillo (solo si la vivienda tiene uno)
    if pasillos:
        for dorm in dormitorios:
            if not any(_is_adjacent(dorm.polygon, p.polygon) for p in pasillos):
                errors.append(f"Dormitorio {dorm.label or '(sin etiqueta)'} sin acceso desde Pasillo")

    return errors


def _log_validation_errors(units: List[Unit]) -> Dict[str, List[str]]:
    """Valida cada vivienda con `_validate_unit` y registra (logging.warning)
    las que fallen. Devuelve {nombre_vivienda: [errores]} solo para las que
    tuvieron algún error."""
    unit_errors: Dict[str, List[str]] = {}
    for unit in units:
        errors = _validate_unit(unit)
        if errors:
            unit_errors[unit.name] = errors
            for error in errors:
                logger.warning("Vivienda %s: %s", unit.name, error)
    return unit_errors


def _call_claude(client, params: dict, model: str) -> tuple[List[Unit], str, Optional[List[str]]]:
    """Una llamada a Claude + parseo a Unit/Room. Factorizado de
    `generate_project` para poder repetir la llamada completa (prompt +
    parseo) en el reintento por geometría inválida o por directiva dura
    incumplida (Fase F), sin duplicar código."""
    try:
        response = client.messages.create(
            model=model,
            max_tokens=8192,
            # SYSTEM_PROMPT no cambia entre llamadas (ni entre el intento y
            # el reintento de la misma generación) -- cachearlo evita pagar
            # el precio completo por él cada vez.
            system=[
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
            ],
            messages=[{"role": "user", "content": _build_user_message(params)}],
        )
    except anthropic.APIError as exc:
        raise GenerationError(f"No se pudo generar el proyecto ({exc}).") from exc

    if response.stop_reason == "refusal":
        raise GenerationError("La generación fue rechazada por los filtros de seguridad del modelo.")

    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        data = _extract_json(text)
    except (json.JSONDecodeError, AttributeError) as exc:
        raise GenerationError(f"No se pudo interpretar la respuesta de IA como JSON ({exc}).") from exc

    units = _parse_generated_units(data)
    if not units:
        raise GenerationError("La IA no ha generado ninguna vivienda válida; inténtalo de nuevo.")

    justificacion = str(data.get("justificacion", "")).strip()
    # Contrato §9: extensión aditiva y opcional del esquema de respuesta —
    # `.get()` con default, un JSON sin este campo (el 100% de las
    # respuestas de antes de esta fase) se parsea exactamente igual que
    # siempre. Autoinforme del LLM, nunca verificado aquí (eso lo hace
    # `verificar_directivas_duras`, determinista, más abajo).
    referencias = data.get("referencias_especificacion")
    if not isinstance(referencias, list) or not all(isinstance(x, str) for x in referencias):
        referencias = None
    return units, justificacion, referencias


# ---------------------------------------------------------------------------
# Fase F — Verificación determinista de directivas duras (contrato §12)
# ---------------------------------------------------------------------------

_COMERCIAL_ROOM_NAMES = {_COMERCIAL_NAME}
# Núcleo de comunicación vertical (2026-08-17): mismo motivo exacto que
# `_COMERCIAL_ROOM_NAMES` de abajo -- una unidad "vacía" (`_construir_unidad_
# nucleo`) no es una vivienda, así que tampoco debe entrar en ninguna
# comprobación pensada para viviendas (accesibilidad, umbral de fallo
# geométrico >50% de `generate_project`, etc.).
_NO_RESIDENCIAL_ROOM_NAMES = _COMERCIAL_ROOM_NAMES | {_NUCLEO_ROOM_NAME}


def _es_unidad_residencial(unit: Unit) -> bool:
    """Una unidad "Local comercial" (planta baja comercial, ver
    `place_rooms`) o "Núcleo de comunicación" (ver `_construir_unidad_
    nucleo`) no es una vivienda — exigirle "un baño accesible", o contarla
    en el umbral de fallo geométrico de `generate_project`, produciría un
    falso incumplimiento/una dilución artificial del ratio. Se excluye de
    esas comprobaciones por ese motivo, no porque no importen."""
    return not any(r.label in _NO_RESIDENCIAL_ROOM_NAMES for r in unit.rooms)


def verificar_directivas_duras(units: List[Unit], directivas: List[dict]) -> List[dict]:
    """Contrato §12 — determinista, reutiliza `evaluate_bathroom_
    accessibility()`/`evaluate_accessible_bathroom_area()` (ya existentes en
    `evaluator.py`, Bloques 8 y 21) sin duplicar esa lógica; no llama a
    Claude. Procesa TODAS las directivas `fuerza="dura"` (verificables o
    no) porque la trazabilidad (Fase F, tarea D) necesita constancia de las
    tres categorías de resultado, no solo de las incumplidas:

    - `"cumple"` / `"no_cumple"`: solo para accesibilidad
      (`verificable_geometricamente=True`, el único caso con método
      determinista hoy) — el texto de la propia directiva pide "al menos un
      baño accesible en cada vivienda" (ver
      `analyzer/interview/compilador.py:_construir_directiva`), así que se
      exige por vivienda, no que baste una sola en todo el proyecto. Un
      baño cuenta como accesible solo si pasa AMBOS chequeos de
      `evaluator.py` (dimensión mínima de giro Y superficie mínima) —
      son complementarios, no alternativos, y el contrato nombra los dos.
      Las unidades "Local comercial" quedan excluidas (`_es_unidad_
      residencial`).
    - `"no_verificable"`: cualquier otra directiva dura (p. ej. un
      no-negociable de texto libre) — nunca se presenta como cumplida ni
      como incumplida sin comprobación real (regla explícita de esta
      fase)."""
    resultados: List[dict] = []
    for d in directivas:
        if d["fuerza"] != "dura":
            continue
        if not (d.get("verificable_geometricamente") and d["categoria"] == "accesibilidad"):
            resultados.append({
                "especificacion_id": d["especificacion_id"],
                "metodo": "sin verificación determinista disponible para esta categoría todavía",
                "resultado": "no_verificable",
                "viviendas_incumplidoras": [],
            })
            continue

        viviendas_incumplidoras: List[str] = []
        for unit in units:
            if not _es_unidad_residencial(unit):
                continue
            dimension = evaluate_bathroom_accessibility(unit)
            area = evaluate_accessible_bathroom_area(unit)
            cumple_dimension = dimension is not None and dimension.has_accessible_bathroom
            cumple_area = area is not None and area.has_accessible_bathroom
            if not (cumple_dimension and cumple_area):
                viviendas_incumplidoras.append(unit.name)

        resultados.append({
            "especificacion_id": d["especificacion_id"],
            "metodo": "evaluate_bathroom_accessibility + evaluate_accessible_bathroom_area (CTE DB-SUA) en cada vivienda",
            "resultado": "no_cumple" if viviendas_incumplidoras else "cumple",
            "viviendas_incumplidoras": viviendas_incumplidoras,
        })
    return resultados


def generate_project(params: dict, model: str = MODEL) -> GeneratedProject:
    """Llama a Claude para generar la distribución y la convierte en
    `Room`/`Unit` reales. Lanza `GenerationError` (con un mensaje apto para
    mostrar al usuario) si no se puede generar por cualquier motivo.

    Tras generar, valida la geometría de cada vivienda (`_validate_unit`) y,
    si `params` trae `contexto_cualitativo` (Fase F), verifica también sus
    directivas duras (`verificar_directivas_duras`). Repite la llamada
    completa a Claude una única vez si se da CUALQUIERA de las dos
    condiciones — más de la mitad de las viviendas con errores geométricos
    (mecanismo ya existente, sin cambios), o alguna directiva dura
    incumplida (nuevo en esta fase, PRD v2 plan de implementación, tarea
    F6/Decisión Pablo #1) — nunca las combina en un único umbral: cualquiera
    de las dos, por separado, ya dispara el mismo reintento único. Si tras
    el reintento persiste cualquier problema, se acepta el resultado
    igualmente — nunca un error 5xx por esto — y se listan en
    `advertencias`.
    """
    if anthropic is None:
        raise GenerationError("El paquete 'anthropic' no está instalado en el servidor.")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise GenerationError("Configura ANTHROPIC_API_KEY para generar proyectos con IA.")

    client = anthropic.Anthropic(api_key=api_key)

    # Validada UNA vez, reutilizada en las dos pasadas posibles (la llamada
    # y el reintento) — nunca se revalida contra una segunda fuente.
    directivas = _validar_directivas(params.get("contexto_cualitativo"))

    units, justificacion, referencias = _call_claude(client, params, model)
    unit_errors = _log_validation_errors(units)
    verificaciones = verificar_directivas_duras(units, directivas)

    # Núcleo de comunicación vertical (2026-08-17): el umbral es sobre VIVIENDAS, igual que antes de
    # esta pieza -- las unidades "vacías" que añade `_parse_generated_units` (núcleo, y ya antes "Local
    # comercial") nunca tienen errores de `_validate_unit` (un único room, sin pares que solapar ni
    # baño/dormitorio que comprobar), así que dejarlas en el denominador diluiría el ratio de forma
    # artificial -- un proyecto con núcleo podría dejar de reintentar exactamente cuando más lo necesita.
    unidades_residenciales = [u for u in units if _es_unidad_residencial(u)]
    geometria_falla = len(unit_errors) / len(unidades_residenciales) > 0.5 if unidades_residenciales else False
    directiva_dura_incumplida = any(v["resultado"] == "no_cumple" for v in verificaciones)

    motivo_reintento: Optional[str] = None
    if geometria_falla or directiva_dura_incumplida:
        motivos = []
        if geometria_falla:
            motivos.append("geometria")
        if directiva_dura_incumplida:
            motivos.append("directiva_dura")
        motivo_reintento = "+".join(motivos)
        logger.warning(
            "Regenerando proyecto (motivo=%s): %d/%d viviendas con problemas geométricos, "
            "directiva dura incumplida=%s.",
            motivo_reintento, len(unit_errors), len(units), directiva_dura_incumplida,
        )
        units, justificacion, referencias = _call_claude(client, params, model)
        unit_errors = _log_validation_errors(units)
        verificaciones = verificar_directivas_duras(units, directivas)

    advertencias = [f"{name}: {'; '.join(errors)}" for name, errors in unit_errors.items()]
    for v in verificaciones:
        if v["resultado"] != "no_cumple":
            continue
        for nombre in v["viviendas_incumplidoras"]:
            advertencias.append(
                f"{nombre}: directiva de accesibilidad incumplida — sin baño accesible con las "
                "dimensiones/superficie mínimas CTE DB-SUA"
            )

    # Validación de fachada exterior (docs/prd/2026-08-17-nucleo-comunicacion-fachada-generador.md,
    # objetivo técnico §4.3): reutiliza `evaluate_natural_light`, YA existente y ya aplicada a todo
    # proyecto (analizado o generado) para puntuar `calidad_espacial` -- no se duplica ninguna regla
    # nueva, solo se refleja también aquí el mismo resultado determinista para que un salón/dormitorio
    # sin fachada quede listado en `advertencias` (visible de inmediato al generar), no solo dentro del
    # detalle de calidad espacial. Nunca bloquea la generación -- mismo criterio que el resto de esta
    # lista: se acepta el proyecto igual y se avisa. Las unidades "Local comercial"/núcleo de
    # comunicación no tienen ninguna estancia que coincida con los patrones de `evaluate_natural_light`
    # (Salón/cocina, Dormitorio 1-3), así que no producen ningún resultado -- no hace falta excluirlas
    # a mano.
    for unit in units:
        for resultado in evaluate_natural_light(unit):
            if not resultado.passed:
                advertencias.append(f"{unit.name}: {resultado.message}")

    rooms = [room for unit in units for room in unit.rooms]

    return GeneratedProject(
        units=units, rooms=rooms, justificacion=justificacion, advertencias=advertencias,
        directivas_aplicadas=directivas, verificaciones_directivas=verificaciones,
        reintento_disparado_por=motivo_reintento, referencias_especificacion=referencias,
    )


# ---------------------------------------------------------------------------
# Optimización Generativa Multi-Opción (docs/prd/2026-08-17-optimizacion-
# generativa-multi-opcion.md, aprobado 2026-08-17: 2 opciones -- no 3--,
# interpretación FUERTE: cada opción deriva un `mix_viviendas` distinto del
# MISMO total de superficie construida objetivo, no solo un estilo distinto
# sobre el mismo mix. Sin esto, las 2 llamadas a Claude tienden a producir
# geometría demasiado parecida para justificar el coste de generarlas por
# separado (riesgo ya señalado en el PRD §14).
# ---------------------------------------------------------------------------

# Tamaño medio ASUMIDO por tipología -- heurística INTERNA de reparto para
# decidir cuántas viviendas de cada tamaño caben en una superficie objetivo,
# no un dato de mercado ni una superficie mínima legal (esas ya existen en
# `evaluator.py` y no se tocan aquí). Nunca se muestra al usuario como si
# fuera un dato real -- solo determina la ARITMÉTICA de cuántas unidades de
# cada tipo proponer, igual de "interno" que cualquier otra constante de
# este módulo (p. ej. `_MIN_PASILLO_DEPTH_M`).
TAMANO_MEDIO_ASUMIDO_M2 = {"dorm_1": 45.0, "dorm_2": 65.0, "dorm_3": 85.0}

# Reparto (fracción del total de viviendas) de cada opción. A: compacta,
# más unidades pequeñas -- fusiona el "maximizar viviendas pequeñas" del
# encargo original. B: amplia, menos unidades más grandes -- fusiona
# "maximizar m² útiles" (una vivienda más grande tiene, en general, más m²
# útiles por unidad). "Equilibrada" queda fuera de las 2 opciones aprobadas
# por ser el punto medio entre A y B, el eje menos diferenciado para una
# comparación de solo 2 alternativas (PRD §0/§14).
_REPARTO_OPCION_A = {"dorm_1": 0.55, "dorm_2": 0.35, "dorm_3": 0.10}
_REPARTO_OPCION_B = {"dorm_1": 0.10, "dorm_2": 0.35, "dorm_3": 0.55}


def _mix_desde_reparto(superficie_objetivo_m2: float, reparto: dict, superficie_minima_m2: float) -> dict:
    tamano_medio = sum(reparto[k] * TAMANO_MEDIO_ASUMIDO_M2[k] for k in reparto)
    total_viviendas = max(1, round(superficie_objetivo_m2 / tamano_medio))
    counts = {k: round(total_viviendas * reparto[k]) for k in reparto}
    # El redondeo por tipología puede no sumar exactamente `total_viviendas`
    # -- se ajusta en dorm_2 (la tipología central, nunca en los extremos
    # que definen el carácter de la opción) para no perder ni inventar una
    # vivienda de más.
    diferencia = total_viviendas - sum(counts.values())
    counts["dorm_2"] = max(0, counts["dorm_2"] + diferencia)
    return {
        "dorm_1": counts["dorm_1"], "dorm_2": counts["dorm_2"], "dorm_3": counts["dorm_3"],
        "superficie_minima_m2": superficie_minima_m2,
    }


def derivar_mixes_alternativos(
    superficie_objetivo_m2: float, superficie_minima_m2: float = 45.0,
) -> "OrderedDict[str, dict]":
    """2 `mix_viviendas` derivados del mismo total de superficie construida
    objetivo -- "A" (compacta) y "B" (amplia). Devuelve un dict vacío si
    `superficie_objetivo_m2` no es positiva -- nunca se inventa un reparto
    sobre una superficie que no existe."""
    if superficie_objetivo_m2 <= 0:
        return OrderedDict()
    return OrderedDict((
        ("A", _mix_desde_reparto(superficie_objetivo_m2, _REPARTO_OPCION_A, superficie_minima_m2)),
        ("B", _mix_desde_reparto(superficie_objetivo_m2, _REPARTO_OPCION_B, superficie_minima_m2)),
    ))


def generate_project_opciones(
    params_base: dict, superficie_objetivo_m2: float, model: str = MODEL,
) -> "OrderedDict[str, object]":
    """Genera las 2 opciones -- 2 llamadas reales e independientes a Claude
    (cada una con su propio reintento posible de `generate_project`, hasta
    4 llamadas en total, ver PRD §9). Cada valor del dict devuelto es un
    `GeneratedProject` si esa opción se generó bien, o un `GenerationError`
    si falló -- el llamador (`app.py`) decide cómo representar un fallo
    parcial sin descartar la opción que sí funcionó (criterio de aceptación
    §8.6 del PRD)."""
    mixes = derivar_mixes_alternativos(
        superficie_objetivo_m2,
        params_base.get("mix_viviendas", {}).get("superficie_minima_m2", 45.0),
    )
    resultados: "OrderedDict[str, object]" = OrderedDict()
    for etiqueta, mix in mixes.items():
        params_opcion = dict(params_base)
        params_opcion["mix_viviendas"] = mix
        try:
            resultados[etiqueta] = generate_project(params_opcion, model=model)
        except GenerationError as exc:
            resultados[etiqueta] = exc
    return resultados
