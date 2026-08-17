"""Compilador Especificación Arquitectónica — Fase D, tareas D1-D7.

Traduce el `EstadoEntrevista` que produce el motor (Fase C, `motor.py`) —
o una edición directa de modo experto, vía `estado_desde_valores_expertos()`
— en una `EspecificacionArquitectonica` (PRD v2 §22) y, a partir de esta, en
el `params` dict 1:1 con el que hoy trabaja `analyzer/ai_generator.py`
(contrato §5-§8). **Un único camino de compilación para ambos orígenes**
(Decisión Pablo #6, D7 del plan) — `compilar_especificacion()` y
`validar_especificacion()` no saben ni les importa si el `EstadoEntrevista`
que reciben vino de una conversación real o de un editor estructurado.

Principio de aislamiento (igual que Fases A y C): este módulo no importa
`analyzer.ai_generator`, no construye nada Flask, no llama a Claude. Depende
de A (`modelo.py`) y de C (`preguntas.py`, y `motor.campo_tiene_respuesta`,
la única función de motor.py que reutiliza — sin duplicar la lógica de "¿este
campo ya está resuelto?").

Grounding de esta fase, releído contra el código real antes de escribir una
sola línea: `app.py:550-619` (`_parse_generar_params`, la forma EXACTA del
`params` dict y sus valores por defecto ya existentes hoy) y
`analyzer/ai_generator.py` completo (qué claves de `params` usa de verdad
`_build_user_message`/`generate_project`).

**Dos contradicciones reales, encontradas por este grounding y documentadas
aquí antes de resolverlas** (ninguna se oculta ni se "arregla" silenciosamente):

1. **PRD v2 §18 vs. PRD v2 §4.** §18 exige traducir la preferencia cualitativa
   de la pregunta 6 ("más grandes y menos" / "más pequeñas y más") a números
   concretos de `dorm_1/dorm_2/dorm_3` mediante "una interpolación acotada...
   ya calculada por aritmética simple determinista (nº de viviendas × tamaño
   medio del solar)". Pero §4 del mismo documento confirma, por separado y
   explícitamente, que esa aritmética **no existe en el código hoy**
   ("no está implementada; no se presenta como 'ArchMuse lo calcula' hasta
   que lo esté"). Este compilador sigue la instrucción más restrictiva
   (nunca inventar): `_interpolar_mix_viviendas()` solo acepta un mix YA
   numérico (p. ej. declarado en modo experto); una preferencia cualitativa
   sin más se queda sin poder compilar a `params.mix_viviendas`, con un
   error de compilación explícito, nunca con una fórmula inventada aquí.
2. **PRD v2 §6.3 vs. el `params` real.** §6.3 prohíbe explícitamente pedir la
   orientación "en grados" — la pregunta 8 solo admite un punto cardinal o
   una dirección. Pero `ai_generator.py`/`app.py` necesitan
   `params.solar.norte_grados` como número. No hay ningún documento que
   diga cómo convertir uno en el otro. Este compilador introduce la
   conversión mínima defendible (los 8 puntos cardinales → grados, 0=Norte,
   sentido horario — la misma convención que ya describe
   `ai_generator.SYSTEM_PROMPT`) y trata **cualquier otra respuesta**
   (dirección postal, "combinación") como no derivable sin geocodificación
   — error de compilación explícito, nunca un valor inventado.

Un tercer hueco, no una contradicción sino una ausencia real en el catálogo
de C1: **ninguna de las 15 preguntas pregunta cuántas plantas se van a
construir** (`edificio.plantas`) — la pregunta 7 solo pregunta el máximo
NORMATIVO permitido (`restricciones.plantas_maximas`), un dato distinto.
`compilar_params()` lo trata como error de compilación explícito en toda
entrevista guiada de hoy — ver el informe de cierre de esta fase.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .modelo import (
    CampoEspecificacion,
    ContextoCualitativo,
    DirectivaCualitativa,
    EspecificacionArquitectonica,
    EstadoEntrevista,
    RespuestaInterpretada,
    Turno,
    _ahora,
    nuevo_id,
)
from .motor import campo_tiene_respuesta
from .preguntas import IMPRESCINDIBLES, PREGUNTAS

# --- Clasificación por especificacion_id — fuente única para D1/D4 ---------
#
# Una sola tabla, no dos catálogos paralelos: de aquí sale tanto
# `CampoEspecificacion.categoria/tipo_dato/destino_generador/decision_contrato`
# (D1, D3, D5) como qué campos producen una `DirectivaCualitativa` y con qué
# `fuerza` (D4, contrato §8.3). `categoria` se define aquí con criterio
# propio (PRD v2 §1), no heredada mecánicamente de `Pregunta.categoria`:
# `Pregunta` tiene una única categoría por pregunta, pero la 1 alimenta dos
# especificacion_id que el PRD sitúa en categorías distintas
# (`programa.descripcion_libre` → categoría 3; `programa.sensacion_buscada`
# → categoría 12) — una aproximación de Fase C que no vale la pena arrastrar
# a Fase D cuando compilador.py puede ser más preciso sin tocar `preguntas.py`.


@dataclass(frozen=True)
class _Clasificacion:
    categoria: str
    tipo_dato_base: str  # tipo_dato cuando naturaleza=Hecho (ver `_tipo_dato_para`)
    destino_generador: str
    decision_contrato: Optional[str]
    categoria_directiva: Optional[str] = None
    fuerza_directiva: Optional[str] = None


_CLASIFICACION: dict[str, _Clasificacion] = {
    # --- usado_directo / N/A: alimentan params_generador sin pasar por
    # ContextoCualitativo (contrato §17, filas "N/A, ya integrado") --------
    "contexto.ciudad": _Clasificacion("contexto_ubicacion", "información_usuario", "usado_directo", None),
    "programa.tipologia": _Clasificacion("programa_necesidades", "información_usuario", "usado_directo", None),
    "solar.superficie_m2": _Clasificacion("parcela", "información_usuario", "usado_directo", None),
    "solar.forma": _Clasificacion("parcela", "información_usuario", "usado_directo", None),
    "orientacion.real_parcela": _Clasificacion("orientacion_clima", "información_usuario", "usado_directo", None),
    "restricciones.plantas_maximas": _Clasificacion("restricciones_normativas", "información_usuario", "usado_directo", None),
    "programa.num_viviendas_mix": _Clasificacion("programa_necesidades", "preferencia", "usado_directo", None),
    # Campos de edificio/normativa que la entrevista guiada NUNCA pregunta
    # hoy (ver contradicción #3 del docstring del módulo) pero que modo
    # experto sí puede declarar directamente — mismo compilador, D7.
    "edificio.plantas": _Clasificacion("restricciones_normativas", "información_usuario", "usado_directo", None),
    "edificio.altura_libre_m": _Clasificacion("restricciones_normativas", "información_usuario", "usado_directo", None),
    "edificio.planta_baja_comercial": _Clasificacion("restricciones_normativas", "información_usuario", "usado_directo", None),
    "programa.superficie_minima_m2": _Clasificacion("programa_necesidades", "información_usuario", "usado_directo", None),
    "restricciones.ocupacion_maxima_pct": _Clasificacion("restricciones_normativas", "información_usuario", "usado_directo", None),
    "restricciones.retranqueos_m": _Clasificacion("restricciones_normativas", "información_usuario", "usado_directo", None),
    "restricciones.edificabilidad_maxima": _Clasificacion("restricciones_normativas", "información_usuario", "usado_directo", None),
    # "Editar / Intervenir edificación existente" -- nueva capacidad, sin decisión de contrato
    # asociada (por eso `None`, igual que el resto de "usado_directo" de arriba): alimenta
    # `params["intervencion_existente"]` (`compilar_params()`) y de ahí
    # `ai_generator._compilar_bloque_intervencion()`, así que es "usado_directo" de verdad, no
    # "almacenado_sin_uso" como `parcela.estado_tenencia` (que hoy no tiene ningún efecto en el
    # generador).
    "parcela.tipo_intervencion": _Clasificacion("parcela", "información_usuario", "usado_directo", None),
    "parcela.elementos_a_conservar": _Clasificacion("parcela", "información_usuario", "usado_directo", None),
    # --- usado_via_extension_minima / B: las 5 categorías del contrato §8.3 -
    "usuarios.accesibilidad": _Clasificacion(
        "usuarios_forma_vida", "restricción", "usado_via_extension_minima", "B", "accesibilidad", "dura"
    ),
    "prioridades.no_negociables": _Clasificacion(
        "prioridades_trade_offs", "restricción", "usado_via_extension_minima", "B", "no_negociable", "dura"
    ),
    "privacidad.necesidad": _Clasificacion(
        "entorno_privacidad", "preferencia", "usado_via_extension_minima", "B", "privacidad", "blanda"
    ),
    "relaciones_espaciales.cocina": _Clasificacion(
        "relaciones_espaciales_circulacion", "preferencia", "usado_via_extension_minima", "B", "relacion_espacial", "blanda"
    ),
    "identidad.referencias_esteticas": _Clasificacion(
        "identidad_arquitectonica", "preferencia", "usado_via_extension_minima", "B", "caracter", "blanda"
    ),
    # "Materiales y Calidades" (2026-08-15, a petición explícita): las 4 preguntas nuevas de
    # `preguntas.py` (p_fachada/p_paleta_colores/p_pavimento/p_nivel_calidades) -- ninguna es
    # imprescindible, todas son preferencias (chip elegido o texto libre), y las 4 deben condicionar
    # el prompt de generación -- mismo tratamiento "usado_via_extension_minima"/B/"caracter"/"blanda"
    # que ya usa `identidad.referencias_esteticas`, la pregunta más parecida que ya existía.
    "materiales.tipo_fachada": _Clasificacion(
        "identidad_arquitectonica", "preferencia", "usado_via_extension_minima", "B", "caracter", "blanda"
    ),
    "materiales.paleta_colores": _Clasificacion(
        "identidad_arquitectonica", "preferencia", "usado_via_extension_minima", "B", "caracter", "blanda"
    ),
    "materiales.pavimento": _Clasificacion(
        "estructura_sistema_constructivo", "preferencia", "usado_via_extension_minima", "B", "caracter", "blanda"
    ),
    "materiales.nivel_calidades": _Clasificacion(
        "estructura_sistema_constructivo", "preferencia", "usado_via_extension_minima", "B", "caracter", "blanda"
    ),
    # --- almacenado_sin_uso / A: decisión A del contrato §17 ---------------
    "usuarios.destino": _Clasificacion("usuarios_forma_vida", "información_usuario", "almacenado_sin_uso", "A"),
    "prioridades.lo_de_menos_importa": _Clasificacion("prioridades_trade_offs", "preferencia", "almacenado_sin_uso", "A"),
    "presupuesto.cifra_horquilla": _Clasificacion("presupuesto", "información_usuario", "almacenado_sin_uso", "A"),
    "sostenibilidad.prioridad": _Clasificacion("sostenibilidad_eficiencia", "preferencia", "almacenado_sin_uso", "A"),
    "exteriores.preferencia": _Clasificacion("espacios_exteriores", "preferencia", "almacenado_sin_uso", "A"),
    "programa.descripcion_libre": _Clasificacion("programa_necesidades", "información_usuario", "almacenado_sin_uso", "A"),
    "programa.sensacion_buscada": _Clasificacion("identidad_arquitectonica", "preferencia", "almacenado_sin_uso", "A"),
    # Imprescindible sin fila propia en la tabla del contrato §17 — mismo
    # tratamiento honesto que el resto de "A": se guarda, no tiene efecto
    # todavía (ver informe de cierre de esta fase).
    "prioridades.trade_off": _Clasificacion("prioridades_trade_offs", "preferencia", "almacenado_sin_uso", "A"),
    "parcela.estado_tenencia": _Clasificacion("parcela", "información_usuario", "almacenado_sin_uso", "A"),
    # --- no_aplica / C: categoría 15, exclusiva de modo experto (§29.3) ----
    "estructura.sistema_constructivo": _Clasificacion("estructura_sistema_constructivo", "información_usuario", "no_aplica", "C"),
}

_ETIQUETAS: dict[str, str] = {
    "contexto.ciudad": "Ciudad / municipio",
    "programa.tipologia": "Tipología del edificio",
    "solar.superficie_m2": "Superficie del solar",
    "solar.forma": "Forma del solar",
    "orientacion.real_parcela": "Orientación real de la parcela",
    "restricciones.plantas_maximas": "Plantas máximas (normativa)",
    "programa.num_viviendas_mix": "Mix de viviendas",
    "edificio.plantas": "Plantas a construir",
    "edificio.altura_libre_m": "Altura libre por planta",
    "edificio.planta_baja_comercial": "Planta baja comercial",
    "programa.superficie_minima_m2": "Superficie mínima por vivienda",
    "restricciones.ocupacion_maxima_pct": "Ocupación máxima del solar",
    "restricciones.retranqueos_m": "Retranqueos",
    "restricciones.edificabilidad_maxima": "Edificabilidad máxima",
    "usuarios.accesibilidad": "Accesibilidad requerida",
    "prioridades.no_negociables": "No negociables",
    "privacidad.necesidad": "Necesidad de privacidad",
    "relaciones_espaciales.cocina": "Cocina abierta o cerrada",
    "identidad.referencias_esteticas": "Referencias estéticas / carácter",
    "usuarios.destino": "Para quién es el proyecto",
    "prioridades.lo_de_menos_importa": "Lo que menos importa",
    "presupuesto.cifra_horquilla": "Presupuesto",
    "sostenibilidad.prioridad": "Prioridad de sostenibilidad",
    "exteriores.preferencia": "Preferencia de espacios exteriores",
    "programa.descripcion_libre": "Descripción libre del proyecto",
    "programa.sensacion_buscada": "Sensación buscada",
    "prioridades.trade_off": "Prioridad ante conflicto",
    "parcela.estado_tenencia": "Estado de tenencia de la parcela",
    "estructura.sistema_constructivo": "Estructura / sistema constructivo",
    "parcela.tipo_intervencion": "¿La parcela está vacía o ya hay una edificación?",
    "parcela.elementos_a_conservar": "Qué conservar o demoler de lo existente",
    "materiales.tipo_fachada": "Tipo de fachada",
    "materiales.paleta_colores": "Paleta de colores",
    "materiales.pavimento": "Pavimento interior",
    "materiales.nivel_calidades": "Nivel de calidades",
}

#: Vocabulario cerrado reutilizado directamente del catálogo de preguntas
#: (C1) — no se duplica una segunda lista de opciones por campo. Solo
#: preguntas `tipo == "opcion"`: las `condicional` (p3, p8) admiten
#: legítimamente texto libre fuera de sus opciones (motor.py, C4), así que
#: quedan fuera de esta validación de dominio a propósito. `p6` también se
#: excluye a propósito: su especificacion_id (`programa.num_viviendas_mix`)
#: es el único que además de la preferencia cerrada de p6 puede llegar como
#: un dict numérico ya interpolado (D2, modo experto) — forzarlo al
#: catálogo de p6 rechazaría precisamente el único caso "bueno" (D3).
_OPCIONES_POR_CAMPO: dict[str, tuple[str, ...]] = {
    p.especificacion_ids[0]: p.opciones
    for p in PREGUNTAS
    if p.tipo == "opcion" and p.opciones and len(p.especificacion_ids) == 1
    and p.especificacion_ids[0] != "programa.num_viviendas_mix"
}

#: Conversión mínima defendible para la contradicción #2 del docstring del
#: módulo — 0=Norte, sentido horario, misma convención que ya describe
#: `ai_generator.SYSTEM_PROMPT` ("azimut en grados, sentido horario, 0 =
#: arriba del plano = Norte"). Solo cubre los 8 puntos cardinales que p8
#: ofrece como opción cerrada; "combinacion" y cualquier dirección postal en
#: texto libre quedan fuera a propósito — no hay forma determinista de
#: convertirlos sin geocodificación, que no existe en el código.
_COMPASS_A_GRADOS: dict[str, float] = {
    "norte": 0.0, "noreste": 45.0, "este": 90.0, "sureste": 135.0,
    "sur": 180.0, "suroeste": 225.0, "oeste": 270.0, "noroeste": 315.0,
}


# --- D1/D5: compilar_especificacion() ---------------------------------------


def _ultima_respuesta(estado: EstadoEntrevista, especificacion_id: str) -> Optional[RespuestaInterpretada]:
    for r in reversed(estado.respuestas_interpretadas):
        if r.especificacion_id == especificacion_id:
            return r
    return None


def _tipo_dato_para(especificacion_id: str, respuesta: RespuestaInterpretada, base: str) -> str:
    """Regla fundamental de esta fase, aplicada aquí en un único sitio:
    Preferencia se conserva como preferencia; Inferencia/Hipótesis se
    conservan como `tipo_dato="inferencia"` (nunca se ascienden a
    `información_usuario`, que es lo que `Hecho` significaría) — la
    distinción exacta entre Inferencia e Hipótesis, que `CampoEspecificacion`
    no tiene un campo propio para guardar, sigue siendo recuperable via
    `origen` → la `RespuestaInterpretada` original todavía la tiene."""
    if respuesta.naturaleza == "Preferencia":
        return "preferencia"
    if respuesta.naturaleza in ("Inferencia", "Hipótesis"):
        return "inferencia"
    # naturaleza == "Hecho": accesibilidad es el único campo cuya condición
    # de "restricción real" depende del propio valor (solo si de verdad hace
    # falta), no solo de su categoría — todo lo demás usa la tabla estática.
    if especificacion_id == "usuarios.accesibilidad":
        return "restricción" if respuesta.valor == "si" else "información_usuario"
    return base


def _construir_campo(especificacion_id: str, respuesta: RespuestaInterpretada, clasificacion: _Clasificacion) -> CampoEspecificacion:
    tipo_dato = _tipo_dato_para(especificacion_id, respuesta, clasificacion.tipo_dato_base)
    return CampoEspecificacion(
        especificacion_id=especificacion_id,
        categoria=clasificacion.categoria,
        etiqueta=_ETIQUETAS.get(especificacion_id, especificacion_id),
        tipo_dato=tipo_dato,
        valor=respuesta.valor,
        origen=[respuesta.respuesta_id],
        confianza=respuesta.confianza if tipo_dato == "inferencia" else None,
        destino_generador=clasificacion.destino_generador,
        decision_contrato=clasificacion.decision_contrato,
    )


#: Etiquetas legibles de las opciones cerradas de "Materiales y Calidades" (2026-08-15, a petición
#: explícita) -- solo para componer `texto_origen`/`texto_prompt` en `_construir_directiva`. Si el usuario
#: escribió texto libre fuera de estas opciones (`tipo="condicional"` lo admite, ver `preguntas.py`),
#: `.get(valor, valor)` usa ese texto tal cual -- nunca se inventa una etiqueta para algo que el usuario no
#: dijo.
_ETIQUETA_OPCION_FACHADA: dict[str, str] = {
    "sate_aislamiento_continuo": "SATE / aislamiento térmico continuo",
    "fachada_ventilada_piedra_ceramica": "fachada ventilada de piedra o cerámica",
    "hormigon_visto": "hormigón visto",
    "ladrillo_visto_clasico_moderno": "ladrillo visto (clásico-moderno)",
    "madera_exterior_composite": "madera de exterior / composite",
}
_ETIQUETA_OPCION_PALETA: dict[str, str] = {
    "tonos_neutros_blanco_arena": "tonos neutros (blanco/arena)",
    "tonos_oscuros_gris_antracita_negro": "tonos oscuros (gris antracita/negro)",
    "acabados_calidos_madera_piedra": "acabados cálidos (madera y piedra)",
    "colores_vivos_contrastes": "colores vivos con contrastes",
}
_ETIQUETA_OPCION_PAVIMENTO: dict[str, str] = {
    "parquet_madera_natural": "parquet de madera natural",
    "gres_porcelanico_gran_formato": "gres porcelánico de gran formato",
    "microcemento": "microcemento",
    "suelo_radiante_acabado_ceramico": "suelo radiante con acabado cerámico",
}
_ETIQUETA_OPCION_CALIDADES: dict[str, str] = {
    "estandar_funcional": "estándar / funcional",
    "alta_calidad_premium": "alta calidad / premium",
    "lujo_a_medida": "lujo / acabados a medida",
}


def _construir_directiva(
    especificacion_id: str, respuesta: RespuestaInterpretada, clasificacion: _Clasificacion
) -> Optional[DirectivaCualitativa]:
    """D4 — solo los 5 campos con `categoria_directiva` definida (contrato
    §8.3) pueden llegar a producir una `DirectivaCualitativa`; el resto
    (incluida cualquier categoría futura) nunca produce una, aunque se
    marque `usado_via_extension_minima` a mano por error — el catálogo
    cerrado de `DirectivaCualitativa.categoria` (`modelo.CATEGORIAS_DIRECTIVA`,
    Decisión Pablo #3) haría fallar la construcción igualmente."""
    if clasificacion.categoria_directiva is None or respuesta.valor is None:
        return None
    if especificacion_id == "usuarios.accesibilidad":
        if respuesta.valor != "si":
            return None
        texto_origen = "el usuario declaró que sí, o podría, vivir alguien con movilidad reducida"
        texto_prompt = "Garantiza un itinerario accesible sin escalones y al menos un baño accesible en cada vivienda."
        verificable = True
    elif especificacion_id == "prioridades.no_negociables":
        return None  # gestionado aparte en compilar_especificacion — puede haber más de uno
    elif especificacion_id == "privacidad.necesidad":
        if respuesta.valor != "mucha":
            return None  # "normal"/"le_da_igual" no aportan nada distinto del comportamiento por defecto
        texto_origen = "el usuario pidió mucha privacidad frente a calle/vecinos"
        texto_prompt = "Prioriza la privacidad frente a calle y vecinos: minimiza huecos directos hacia zonas expuestas donde sea razonable."
        verificable = False
    elif especificacion_id == "relaciones_espaciales.cocina":
        if respuesta.valor == "abierta":
            texto_origen = "el usuario prefiere la cocina integrada con el salón"
            texto_prompt = "El usuario prefiere la cocina integrada (abierta) con el salón."
        elif respuesta.valor == "cerrada":
            texto_origen = "el usuario prefiere la cocina separada del salón"
            texto_prompt = "El usuario prefiere la cocina separada (cerrada) del salón."
        else:
            return None
        verificable = False
    elif especificacion_id == "identidad.referencias_esteticas":
        texto_origen = "referencias del usuario: %s" % respuesta.valor
        texto_prompt = "Ten en cuenta estas referencias/carácter deseado por el usuario: \"%s\"." % respuesta.valor
        verificable = False
    elif especificacion_id == "materiales.tipo_fachada":
        etiqueta = _ETIQUETA_OPCION_FACHADA.get(respuesta.valor, respuesta.valor)
        texto_origen = "el usuario prefiere una fachada de %s" % etiqueta
        texto_prompt = "Diseña la fachada con %s como sistema/material principal." % etiqueta
        verificable = False
    elif especificacion_id == "materiales.paleta_colores":
        etiqueta = _ETIQUETA_OPCION_PALETA.get(respuesta.valor, respuesta.valor)
        texto_origen = "el usuario prefiere una paleta de %s" % etiqueta
        texto_prompt = "Usa una paleta de colores de %s, tanto en interiores como en el acabado exterior." % etiqueta
        verificable = False
    elif especificacion_id == "materiales.pavimento":
        etiqueta = _ETIQUETA_OPCION_PAVIMENTO.get(respuesta.valor, respuesta.valor)
        texto_origen = "el usuario prefiere el pavimento interior en %s" % etiqueta
        texto_prompt = "Especifica el pavimento interior en %s." % etiqueta
        verificable = False
    elif especificacion_id == "materiales.nivel_calidades":
        etiqueta = _ETIQUETA_OPCION_CALIDADES.get(respuesta.valor, respuesta.valor)
        texto_origen = "el usuario quiere un nivel de calidades %s" % etiqueta
        texto_prompt = "El nivel de calidades y acabados de todo el proyecto debe ser %s." % etiqueta
        verificable = False
    else:  # pragma: no cover - _CLASIFICACION no tiene hoy ningún otro caso con categoria_directiva
        return None
    return DirectivaCualitativa(
        especificacion_id=especificacion_id, categoria=clasificacion.categoria_directiva,
        fuerza=clasificacion.fuerza_directiva, texto_origen=texto_origen, texto_prompt=texto_prompt,
        verificable_geometricamente=verificable,
    )


def _compilar_texto_prompt(directivas: list[DirectivaCualitativa]) -> str:
    """Contrato §8.2 — plantilla determinista, sin Claude. Una subsección
    vacía nunca se imprime."""
    duras = [d.texto_prompt for d in directivas if d.fuerza == "dura"]
    blandas = [d.texto_prompt for d in directivas if d.fuerza == "blanda"]
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


def compilar_especificacion(estado: EstadoEntrevista, especificacion_id: Optional[str] = None) -> EspecificacionArquitectonica:
    """D1/D5/D7 — el único punto de entrada, para entrevista guiada y para
    modo experto (que primero pasa por `estado_desde_valores_expertos()`).

    No llama a `compilar_params()` — deliberadamente: una entrevista a
    medias debe poder producir una `EspecificacionArquitectonica` parcial y
    navegable (el resumen de §27, la corrección de §28) sin que un dato de
    `params` todavía sin resolver bloquee eso. `params_generador` queda
    vacío (`{}` es el propio default de `EspecificacionArquitectonica`);
    quien orqueste esto (Fase B/F, todavía no implementadas) decide cuándo
    invocar `compilar_params()` por separado y, si tiene éxito, dónde
    guardarlo.

    `especificacion_id` es estable si no se pasa uno explícito
    (`"spec-" + sesion_id`) — nunca aleatorio: compilar dos veces el mismo
    estado debe producir la misma Especificación (criterio D2/determinismo).
    """
    especificacion_id = especificacion_id or ("spec-%s" % estado.sesion_id)
    ids_presentes = sorted({r.especificacion_id for r in estado.respuestas_interpretadas})

    campos: list[CampoEspecificacion] = []
    decisiones_pendientes: list[str] = []
    directivas: list[DirectivaCualitativa] = []

    for especificacion_id_campo in ids_presentes:
        clasificacion = _CLASIFICACION.get(especificacion_id_campo)
        if clasificacion is None:
            # Test 8 / D1: catálogo cerrado — un especificacion_id que no
            # pertenece a la clasificación conocida nunca se convierte en un
            # CampoEspecificacion inventado; se descarta y se deja constancia.
            decisiones_pendientes.append("campo_no_reconocido:%s" % especificacion_id_campo)
            continue
        if not campo_tiene_respuesta(estado, especificacion_id_campo):
            # Solo puede ser por una contradicción pendiente: `ids_presentes`
            # ya garantiza que existe al menos una RespuestaInterpretada.
            contradiccion = next(
                (c for c in estado.contradicciones if c.especificacion_id == especificacion_id_campo and not c.resuelta),
                None,
            )
            if contradiccion is not None:
                decisiones_pendientes.append(
                    "contradiccion_pendiente:%s:%s" % (especificacion_id_campo, contradiccion.contradiccion_id)
                )
            continue
        respuesta = _ultima_respuesta(estado, especificacion_id_campo)
        assert respuesta is not None  # garantizado por ids_presentes + campo_tiene_respuesta
        campos.append(_construir_campo(especificacion_id_campo, respuesta, clasificacion))
        directiva = _construir_directiva(especificacion_id_campo, respuesta, clasificacion)
        if directiva is not None:
            directivas.append(directiva)

    # No-negociables: uno por frase ya deduplicada por el motor
    # (`estado.no_negociables`), solo si el campo no está bloqueado por una
    # contradicción pendiente sobre sí mismo.
    if campo_tiene_respuesta(estado, "prioridades.no_negociables"):
        for texto in estado.no_negociables:
            directivas.append(
                DirectivaCualitativa(
                    especificacion_id="prioridades.no_negociables", categoria="no_negociable", fuerza="dura",
                    texto_origen=texto,
                    texto_prompt="Debes respetar este requisito no negociable del usuario: \"%s\"." % texto,
                    verificable_geometricamente=False,
                )
            )

    ids_con_campo = {c.especificacion_id for c in campos}
    ids_con_contradiccion = {
        entrada.split(":", 2)[1] for entrada in decisiones_pendientes if entrada.startswith("contradiccion_pendiente:")
    }
    for imprescindible in IMPRESCINDIBLES:
        if imprescindible in ids_con_campo or imprescindible in ids_con_contradiccion:
            continue
        decisiones_pendientes.append("imprescindible_pendiente:%s" % imprescindible)

    contexto = ContextoCualitativo(directivas=directivas, texto_prompt=_compilar_texto_prompt(directivas))

    return EspecificacionArquitectonica(
        especificacion_id=especificacion_id,
        sesion_entrevista_id=estado.sesion_id,
        modo_origen=estado.modo_entrada,
        campos=campos,
        contexto_cualitativo=contexto,
        decisiones_pendientes=decisiones_pendientes,
    )


# --- D6: validar_especificacion() -------------------------------------------


@dataclass
class ResultadoValidacion:
    valida: bool
    errores: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def validar_especificacion(especificacion: EspecificacionArquitectonica) -> ResultadoValidacion:
    """D6 — determinista, un único argumento (la propia Especificación ya
    compilada): toda la información de "qué falta y por qué" que hace falta
    para validar ya vive en `especificacion.decisiones_pendientes` (lo
    escribió `compilar_especificacion()`) y en `especificacion.campos` — no
    hace falta volver a mirar el `EstadoEntrevista` original."""
    errores: list[str] = []
    avisos: list[str] = []

    for entrada in especificacion.decisiones_pendientes:
        if entrada.startswith("imprescindible_pendiente:"):
            especificacion_id = entrada.split(":", 1)[1]
            errores.append(
                "Falta el dato imprescindible %r: el usuario todavía no lo ha respondido "
                "(ni siquiera como Hipótesis explícita, PRD v2 §2)." % especificacion_id
            )
        elif entrada.startswith("contradiccion_pendiente:"):
            _, especificacion_id, contradiccion_id = entrada.split(":", 2)
            errores.append(
                "Hay una contradicción sin resolver en %r (contradiccion_id=%s): no se puede "
                "compilar hasta que el usuario elija un valor (PRD v2 §26: nunca se sobrescribe "
                "en silencio)." % (especificacion_id, contradiccion_id)
            )
        elif entrada.startswith("campo_no_reconocido:"):
            especificacion_id = entrada.split(":", 1)[1]
            errores.append(
                "%r no pertenece al catálogo cerrado de especificacion_id conocidos; se ha "
                "descartado, nunca compilado como si fuera válido." % especificacion_id
            )

    campos_por_id = {c.especificacion_id: c for c in especificacion.campos}

    for especificacion_id, opciones in _OPCIONES_POR_CAMPO.items():
        campo = campos_por_id.get(especificacion_id)
        if campo is None or campo.valor is None or campo.tipo_dato == "inferencia":
            continue  # una Hipótesis/Inferencia ya viene marcada como incierta; no se fuerza al catálogo
        if campo.valor not in opciones:
            errores.append(
                "%r tiene un valor %r fuera del catálogo cerrado %s." % (especificacion_id, campo.valor, opciones)
            )

    campo_superficie = campos_por_id.get("solar.superficie_m2")
    if campo_superficie is not None and campo_superficie.valor is not None:
        try:
            if float(campo_superficie.valor) <= 0:
                errores.append(
                    "solar.superficie_m2 debe ser mayor que 0 (valor recibido: %r)." % campo_superficie.valor
                )
        except (TypeError, ValueError):
            errores.append("solar.superficie_m2 no es un número válido: %r." % campo_superficie.valor)

    campo_plantas = campos_por_id.get("restricciones.plantas_maximas")
    if campo_plantas is not None:
        if campo_plantas.tipo_dato == "inferencia" and campo_plantas.confianza == "Baja":
            # PRD v2 §6.4: el aviso debe quedar visible, no enterrado — no
            # bloquea la validación (es opcional en el generador), pero
            # `validar_especificacion` lo hace explícito para quien renderice
            # el resumen (Fase F/E, todavía no implementadas).
            avisos.append(
                "restricciones.plantas_maximas queda como Hipótesis de confianza Baja: sin "
                "verificación normativa municipal disponible (PRD v2 §6.4) — debe mostrarse "
                "visible en el resumen, no ocultarse."
            )
        elif campo_plantas.valor is not None:
            try:
                if int(campo_plantas.valor) <= 0:
                    errores.append(
                        "restricciones.plantas_maximas debe ser mayor que 0 si se declara "
                        "(valor recibido: %r)." % campo_plantas.valor
                    )
            except (TypeError, ValueError):
                errores.append(
                    "restricciones.plantas_maximas no es un número entero válido: %r." % campo_plantas.valor
                )

    return ResultadoValidacion(valida=not errores, errores=errores, avisos=avisos)


# --- D2/D3: compilar_params() -----------------------------------------------


@dataclass
class ResultadoCompilacionParams:
    params: Optional[dict]
    errores: list[str] = field(default_factory=list)


def _interpolar_mix_viviendas(valor: Any) -> Optional[dict]:
    """D2 — ver la contradicción #1 documentada al principio del módulo:
    PRD v2 §18 pide una interpolación determinista que PRD v2 §4 confirma
    que no tiene ninguna base de cálculo real en el código hoy (no existe
    ninguna función que estime nº de viviendas o tamaño medio a partir del
    solar). Este compilador NO inventa esa fórmula. Solo acepta un mix que
    ya viene expresado como números concretos (p. ej. declarado en modo
    experto, o si en el futuro `claude_interprete.py` llegara a devolver
    una estructura así) — cualquier preferencia cualitativa sin más
    (`"mas_grandes_menos_viviendas"` / `"mas_pequenas_mas_viviendas"`, o
    cualquier texto libre) se queda sin poder compilar, con el motivo
    explicado en `compilar_params()`."""
    if not isinstance(valor, dict):
        return None
    try:
        dorm_1 = int(valor.get("dorm_1", 0))
        dorm_2 = int(valor.get("dorm_2", 0))
        dorm_3 = int(valor.get("dorm_3", 0))
    except (TypeError, ValueError):
        return None
    if dorm_1 < 0 or dorm_2 < 0 or dorm_3 < 0 or (dorm_1 + dorm_2 + dorm_3) <= 0:
        return None
    return {"dorm_1": dorm_1, "dorm_2": dorm_2, "dorm_3": dorm_3}


def _num_opcional(campos: dict[str, CampoEspecificacion], especificacion_id: str, cast, default):
    campo = campos.get(especificacion_id)
    if campo is None or campo.valor is None:
        return default
    try:
        return cast(campo.valor)
    except (TypeError, ValueError):
        return default


def _contexto_cualitativo_dict(especificacion: EspecificacionArquitectonica) -> dict:
    """Fase F (integración con el generador): la forma EXACTA que ya esperan
    `ai_generator._validar_directivas()` (contrato §5-§6.2 — `directivas`
    como lista de dicts con `especificacion_id`/`categoria`/`fuerza`/
    `texto_origen`/`texto_prompt`/`verificable_geometricamente`, la misma
    que produce `DirectivaCualitativa.a_dict()`) y `app.py:
    _guardar_traza_de_generacion()` (que además necesita `especificacion_id`
    en este mismo dict para saber de qué Especificación viene la traza —
    ver su docstring). No se inventa un contrato nuevo: se reutiliza tal
    cual el que ya validan `test_ai_generator_contexto.py` (bloque F) y
    `test_interview_api.py` (test 18).

    Se incluye siempre, incluso sin ninguna directiva (`directivas=[]`,
    `texto_prompt=""`) — mismo criterio que ya prueba F2 de
    `test_ai_generator_contexto.py`: una entrevista sin directivas
    cualitativas sigue identificando de qué Especificación salió la
    generación, para que la traza se persista igual."""
    contexto = especificacion.contexto_cualitativo
    return {
        "directivas": [d.a_dict() for d in contexto.directivas] if contexto is not None else [],
        "texto_prompt": contexto.texto_prompt if contexto is not None else "",
        "especificacion_id": especificacion.especificacion_id,
    }


def compilar_params(especificacion: EspecificacionArquitectonica) -> ResultadoCompilacionParams:
    """D3 — 1:1 con la forma real que produce `app.py:_parse_generar_params`
    (releída para esta fase, líneas 550-619) y que `ai_generator.py` consume.
    Nunca inventa: cada valor obligatorio sin fuente legítima se convierte en
    una entrada de `errores`, `params` queda `None` — no hay compilación
    parcial ni un valor por defecto silencioso salvo los que **ya existen
    hoy, explícitamente, en `_parse_generar_params`** (superficie_minima_m2,
    ocupacion_maxima_pct, retranqueos_m, altura_libre_m — se citan uno a uno
    donde se aplican, para que quede claro cuál es cada excepción)."""
    validacion = validar_especificacion(especificacion)
    if not validacion.valida:
        return ResultadoCompilacionParams(params=None, errores=list(validacion.errores))

    campos = {c.especificacion_id: c for c in especificacion.campos}
    errores: list[str] = []

    def _valor(especificacion_id: str) -> Any:
        campo = campos.get(especificacion_id)
        return campo.valor if campo is not None else None

    ciudad = _valor("contexto.ciudad")
    if not ciudad:
        errores.append("params.proyecto.ciudad: falta contexto.ciudad.")

    tipologia_cruda = _valor("programa.tipologia")
    tipologia = tipologia_cruda if tipologia_cruda in ("unifamiliar", "plurifamiliar") else None
    if tipologia is None:
        errores.append(
            "params.proyecto.tipologia: %r no se puede traducir a 'unifamiliar'/'plurifamiliar' "
            "(el params actual no admite 'rehabilitacion' ni 'otra' sin una decisión explícita "
            "de producto)." % tipologia_cruda
        )

    superficie_m2 = _valor("solar.superficie_m2")
    try:
        superficie_m2 = float(superficie_m2) if superficie_m2 is not None else None
    except (TypeError, ValueError):
        superficie_m2 = None
    if not superficie_m2 or superficie_m2 <= 0:
        errores.append(
            "params.solar.superficie_m2: falta o no es un número válido (solar.superficie_m2=%r)."
            % _valor("solar.superficie_m2")
        )

    forma_cruda = _valor("solar.forma")
    forma = "rectangular"
    if isinstance(forma_cruda, str):
        texto = forma_cruda.strip().lower()
        if "irregular" in texto:
            forma = "irregular"
        elif "rectangular" in texto:
            forma = "rectangular"
        # Cualquier otro texto ("en esquina", una descripción libre...) cae
        # en "rectangular" — el mismo fallback que YA aplica hoy
        # `app.py:_parse_generar_params` líneas 560-562 para cualquier valor
        # fuera de {"rectangular","irregular"}; no es un valor inventado
        # nuevo de este compilador.

    orientacion_cruda = _valor("orientacion.real_parcela")
    norte_grados = _COMPASS_A_GRADOS.get(orientacion_cruda) if isinstance(orientacion_cruda, str) else None
    if norte_grados is None:
        errores.append(
            "params.solar.norte_grados: no se puede derivar un ángulo numérico de "
            "orientacion.real_parcela=%r — solo los 8 puntos cardinales de la pregunta 8 tienen "
            "una conversión determinista definida (ver contradicción #2 documentada al principio "
            "de compilador.py); una dirección postal o 'combinacion' exigiría geocodificación, que "
            "no existe en el código." % orientacion_cruda
        )

    plantas_maximas = _num_opcional(campos, "restricciones.plantas_maximas", int, None)

    campo_plantas = campos.get("edificio.plantas")
    if campo_plantas is None or campo_plantas.valor is None:
        errores.append(
            "params.edificio.plantas: ninguna de las 15 preguntas del catálogo actual pregunta "
            "cuántas plantas se van a construir — la pregunta 7 solo pregunta el máximo NORMATIVO "
            "permitido (restricciones.plantas_maximas), que es un dato distinto. Hueco real del "
            "catálogo de preguntas (Fase C), no un fallo de este compilador; ver informe de cierre "
            "de Fase D. Compilable solo si se declara explícitamente (p. ej. en modo experto)."
        )
    else:
        try:
            plantas_valor = max(1, int(campo_plantas.valor))
        except (TypeError, ValueError):
            errores.append("params.edificio.plantas: valor no numérico (%r)." % campo_plantas.valor)
            plantas_valor = None

    altura_libre_m = _num_opcional(campos, "edificio.altura_libre_m", float, 2.8)  # default ya existente hoy
    planta_baja_comercial = bool(_valor("edificio.planta_baja_comercial") or False)

    mix = _interpolar_mix_viviendas(_valor("programa.num_viviendas_mix"))
    if mix is None:
        errores.append(
            "params.mix_viviendas: programa.num_viviendas_mix=%r no se puede convertir en "
            "dorm_1/dorm_2/dorm_3 concretos — ver contradicción #1 documentada al principio de "
            "compilador.py (PRD v2 §18 vs. §4). Solo se acepta un mix ya numérico." % _valor("programa.num_viviendas_mix")
        )

    superficie_minima_m2 = _num_opcional(campos, "programa.superficie_minima_m2", float, 45.0)  # default ya existente hoy
    ocupacion_maxima_pct = _num_opcional(campos, "restricciones.ocupacion_maxima_pct", float, 70.0)  # ídem
    retranqueos_m = _num_opcional(campos, "restricciones.retranqueos_m", float, 3.0)  # ídem
    edificabilidad_maxima = _valor("restricciones.edificabilidad_maxima")  # opcional, None si no hay dato

    # "Editar / Intervenir edificación existente": campos nuevos y
    # OPCIONALES (modo experto, categoría "parcela"). Nunca invalidan la
    # compilación -- ausencia de dato o cualquier valor que no sea
    # exactamente "edificacion_existente" se trata como "obra_nueva", el
    # mismo comportamiento de siempre para toda entrevista anterior a esta
    # capacidad. `ai_generator._compilar_bloque_intervencion()` es quien
    # de verdad decide si esto produce texto en el prompt -- este
    # compilador solo transcribe lo que declaró el usuario.
    tipo_intervencion_crudo = _valor("parcela.tipo_intervencion")
    tipo_intervencion = tipo_intervencion_crudo if tipo_intervencion_crudo == "edificacion_existente" else "obra_nueva"
    elementos_a_conservar = _valor("parcela.elementos_a_conservar")
    elementos_a_conservar = (
        elementos_a_conservar.strip() if isinstance(elementos_a_conservar, str) and elementos_a_conservar.strip() else None
    )

    if errores:
        return ResultadoCompilacionParams(params=None, errores=errores)

    return ResultadoCompilacionParams(
        params={
            "proyecto": {"ciudad": ciudad, "tipologia": tipologia},
            "solar": {
                "superficie_m2": superficie_m2, "forma": forma,
                "ancho_m": None, "largo_m": None, "norte_grados": float(norte_grados),
            },
            "edificio": {
                "plantas": plantas_valor, "altura_libre_m": altura_libre_m,
                "planta_baja_comercial": planta_baja_comercial,
            },
            "mix_viviendas": {**mix, "superficie_minima_m2": superficie_minima_m2},
            "normativa": {
                "ocupacion_maxima_pct": ocupacion_maxima_pct, "retranqueos_m": retranqueos_m,
                "edificabilidad_maxima": edificabilidad_maxima, "plantas_maximas": plantas_maximas,
            },
            # Fase F (integración con el generador) — clave nueva y opcional
            # del contrato §5-§6.2, ausente hasta ahora (hallazgo crítico de
            # la auditoría de 2026-08-13): sin esto, `ai_generator.py` nunca
            # recibía las directivas aunque supiera aplicarlas. Ver
            # `_contexto_cualitativo_dict()`.
            "contexto_cualitativo": _contexto_cualitativo_dict(especificacion),
            # "Editar / Intervenir edificación existente" -- ver comentario
            # de arriba. Igual que `contexto_cualitativo`, se incluye
            # siempre (incluso en "obra_nueva"/sin dato) para que
            # `app.py:_parse_generar_params` la reenvíe tal cual sin tener
            # que distinguir "no vino" de "vino en obra_nueva".
            "intervencion_existente": {"tipo": tipo_intervencion, "elementos_a_conservar": elementos_a_conservar},
        },
        errores=[],
    )


# --- D7: modo experto — mismo compilador, sin duplicar lógica --------------


def _declarar_valores_directos(
    estado: EstadoEntrevista, valores: dict[str, Any], turno_id: str, evitar_no_negociables_duplicados: bool = False
) -> None:
    """Construye, para cada `especificacion_id -> valor` de `valores`, una
    `RespuestaInterpretada` naturaleza=Hecho (siempre — quien llama declaró
    el valor directamente, sin pasar por ninguna pregunta ni por Claude:
    D7/PRD v2 §29.5) y la añade a `estado.respuestas_interpretadas`.
    Factorizado de `estado_desde_valores_expertos()` para que
    `anadir_valores_expertos()` (corrección de 2026-08-13, ver su docstring)
    use exactamente la misma semántica de "esto es un Hecho declarado
    directamente" sin duplicar la construcción del objeto.

    No toca ninguna `RespuestaInterpretada` YA existente en `estado` para
    otro `especificacion_id`: si `especificacion_id` ya tenía una entrada
    previa (p. ej. una Hipótesis de baja confianza de la entrevista
    guiada), esa entrada anterior sigue en la lista tal cual — nunca se
    borra ni se reescribe. `campo_tiene_respuesta()`/`_ultima_respuesta()`
    miran siempre la última entrada, así que la nueva declaración solo
    "gana" para ese campo si de verdad se repite aquí (corrección/
    confirmación explícita del usuario, comportamiento correcto pedido por
    la auditoría: "los valores introducidos/modificados explícitamente en
    modo experto sí pueden convertirse en hechos")."""
    for especificacion_id, valor in valores.items():
        estado.respuestas_interpretadas.append(
            RespuestaInterpretada(
                respuesta_id=nuevo_id(), turno_id=turno_id, especificacion_id=especificacion_id,
                respuesta_cruda=valor, naturaleza="Hecho", valor=valor, confianza=None,
                motivo="declarado directamente en modo experto",
            )
        )
        if especificacion_id == "prioridades.no_negociables" and isinstance(valor, str) and valor.strip():
            texto = valor.strip()
            if not evitar_no_negociables_duplicados or texto not in estado.no_negociables:
                estado.no_negociables.append(texto)


def estado_desde_valores_expertos(valores: dict[str, Any], sesion_id: Optional[str] = None) -> EstadoEntrevista:
    """Decisión Pablo #6 / D7: fabrica un `EstadoEntrevista` sintético (un
    único turno, una `RespuestaInterpretada` naturaleza=Hecho por cada valor
    declarado directamente) para que `compilar_especificacion()` y
    `validar_especificacion()` sean literalmente el mismo código para modo
    experto que para la entrevista guiada — no hay una segunda rama de
    lógica de compilación en ningún sitio de este módulo.

    `valores` es un dict `especificacion_id -> valor` — el arquitecto declara
    el valor final directamente, sin pasar por ninguna pregunta; por eso la
    naturaleza es siempre `Hecho` (PRD v2 §29.5: las mismas reglas de
    validación aplican igual, ser experto no exime de completar lo
    imprescindible).

    Uso: cuando NO hay una entrevista guiada previa real detrás (modo
    experto elegido desde el principio en `vistaEleccion`). Si SÍ la hay y
    solo falta completar un puñado de campos técnicos, usar
    `anadir_valores_expertos()` en su lugar — ver su docstring para por qué
    esta función no sirve para ese caso (aplanaría a Hecho toda la
    trazabilidad epistémica ya recogida)."""
    estado = EstadoEntrevista(sesion_id=sesion_id or nuevo_id(), modo="edicion_experta", modo_entrada="edicion_experta")
    turno_id = nuevo_id()
    estado.historial_turnos.append(Turno(turno_id=turno_id, preguntas_ids=[], respuesta_cruda=dict(valores)))
    estado.turnos_totales = 1
    _declarar_valores_directos(estado, valores, turno_id)
    estado.modificado_en = _ahora()
    return estado


def anadir_valores_expertos(estado: EstadoEntrevista, valores: dict[str, Any]) -> EstadoEntrevista:
    """Puente de datos técnicos — corrección del hallazgo "trazabilidad
    epistemológica del puente" de la auditoría de 2026-08-13.

    A diferencia de `estado_desde_valores_expertos()` (que fabrica una
    sesión sintética nueva desde cero), esta función opera **sobre una
    sesión ya existente**, mutándola in-place: añade un turno nuevo con los
    `valores` declarados directamente (mismo criterio D7 — naturaleza
    siempre Hecho, vía `_declarar_valores_directos()`) sin tocar ni
    reinterpretar ninguna `RespuestaInterpretada` ya presente en `estado`
    para otro campo. Toda Hipótesis, Inferencia o Preferencia que la
    entrevista guiada ya hubiera recogido de verdad sigue siéndolo — nunca
    se convierte en Hecho por el mero hecho de pasar por el puente.

    Cambia `estado.modo` a `"edicion_experta"` (el modo *activo*: PRD v2
    §24/§29 y el propio docstring de `EstadoEntrevista` ya preveían que
    "puede cambiar a mitad de camino, E8 del plan" — esta función es esa
    transición, implementada). `estado.modo_entrada` NO se toca: sigue
    registrando fielmente cómo EMPEZÓ la sesión (p. ej.
    `"entrevista_guiada"`), que es justo el dato que se perdía antes al
    crear una sesión nueva y descartar la original.

    Deliberadamente NO exige `estado.estado == "en_curso"`: en el flujo real
    de `entrevista.js`, `/finalizar` ya se ha llamado antes de que el
    puente pueda aparecer (solo tras finalizar se sabe, vía 422, que faltan
    datos técnicos) — la sesión ya está `"cerrada"` en este punto, y sigue
    estándolo después de esto. No es reabrir la conversación: el ciclo de
    preguntas del motor (`motor.responder()`, que sí exige `en_curso`) no
    interviene aquí en absoluto; esto es una declaración técnica explícita
    sobre el mismo expediente, no un turno de entrevista. Por eso, además,
    la sesión original nunca queda huérfana ni silenciosamente `en_curso`:
    no existe una "sesión original" distinta de esta — es la misma."""
    turno_id = nuevo_id()
    estado.historial_turnos.append(Turno(turno_id=turno_id, preguntas_ids=[], respuesta_cruda=dict(valores)))
    estado.turnos_totales += 1
    estado.modo = "edicion_experta"
    _declarar_valores_directos(estado, valores, turno_id, evitar_no_negociables_duplicados=True)
    estado.modificado_en = _ahora()
    return estado
