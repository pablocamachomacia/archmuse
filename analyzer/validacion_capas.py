# -*- coding: utf-8 -*-
"""Fase 2 del contrato de clasificación DXF: validador de conformidad, NO
bloqueante, sobre el uso de las capas `AM_*`.

Diseño de referencia: informes de arquitectura y Fase 1 de esta misma sesión
("Nueva fase ArchMuse — contrato de clasificación de superficies DXF",
"ArchMuse Fase 1 — implementar Fase 1 del contrato de clasificación DXF").

**Qué es y qué no es.** `validar_capas_am()` audita lo que ya produjeron
`parser.leer_plano()` y `evaluator.group_rooms_by_unit_label()` y devuelve una
lista de `Diagnostico`, de solo lectura -- no cambia `PlanoLeido`, no cambia
`Unit`, no toca ningún cálculo de superficie, y no decide nada por sí mismo:
cuando hay ambigüedad, la reporta, nunca la resuelve adivinando (mismo
criterio que ya aplican `parser.CapaIndeterminada`, `EscalaIndeterminada` y
`evaluator.asignar_envolvente_cerrada`).

**Nunca se recalcula lo que ya calculó otro módulo.** La geometría descartada
sale tal cual de `PlanoLeido.geometria_no_leida` (Fase 1); el emparejamiento
envolvente-vivienda sale de `evaluator.agrupar_por_vivienda_mas_cercana`, la
misma función que usa `asignar_envolvente_cerrada` -- este módulo no
reimplementa ninguna de las dos cosas.

**Silencioso quiere decir silencioso.** Un DXF sin ninguna capa `AM_*` -- el
caso de todos los planos analizados hasta hoy -- produce una lista vacía.
Ningún plano heredado empieza a recibir avisos por no usar un contrato que
nunca ha usado.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from . import evaluator, parser

# --- Severidades, cerradas a propósito ---------------------------------

SEVERIDAD_ERROR = "ERROR"
SEVERIDAD_WARNING = "WARNING"
SEVERIDAD_INFO = "INFO"

SEVERIDADES = (SEVERIDAD_ERROR, SEVERIDAD_WARNING, SEVERIDAD_INFO)

# --- Códigos de diagnóstico propios de este módulo ----------------------
# Los códigos de geometría descartada NO se reinventan aquí: se reutilizan
# tal cual los `parser.MOTIVO_*` (ver `_diagnosticos_geometria_descartada`).

CAPA_CASI_CORRECTA = "CAPA_CASI_CORRECTA"
CAPA_RESERVADA_NO_OPERATIVA = "RESERVADA_NO_OPERATIVA"
ENVOLVENTE_AMBIGUA = "ENVOLVENTE_AMBIGUA"
ENVOLVENTE_SIN_VIVIENDA = "ENVOLVENTE_SIN_VIVIENDA"
VIVIENDA_SIN_ENVOLVENTE = "VIVIENDA_SIN_ENVOLVENTE"


@dataclass(frozen=True)
class Diagnostico:
    """Un hallazgo del validador. Igual que `parser.EntidadDescartada`, nunca
    se pierde en silencio y nunca repara nada: solo explica."""

    codigo: str
    severidad: str
    mensaje: str
    capa: str = ""
    vivienda: str = ""
    handle: str = ""
    detalle: str = ""


# ---------------------------------------------------------------------------
# 1. Nombre de capa "casi correcto" -- nunca autocorregido
# ---------------------------------------------------------------------------

# Cuántas ediciones (inserción/borrado/sustitución de un carácter) puede
# separar un nombre de capa del catálogo para seguir considerándose un
# "casi acierto" y no una capa sin ninguna relación. Calibrado sobre los
# propios ejemplos del encargo ("AM_UTIL_INT_", "AM_CONS_CERR"): los dos
# están a distancia 1. Con 2 hay margen sin acercarse a nombres realmente
# distintos ("AM_UTIL_EXT" está a distancia 3 de "AM_UTIL_INT", y por eso no
# se confunde consigo misma pese a compartir el mismo prefijo).
DISTANCIA_MAXIMA_CASI_CORRECTA = 2


def _distancia_edicion(a: str, b: str) -> int:
    """Distancia de Levenshtein clásica, sin dependencias externas: número
    mínimo de inserciones/borrados/sustituciones de un carácter para pasar
    de `a` a `b`."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    fila_anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        fila_actual = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            coste_sustitucion = 0 if ca == cb else 1
            fila_actual[j] = min(
                fila_anterior[j] + 1,               # borrar de `a`
                fila_actual[j - 1] + 1,              # insertar en `a`
                fila_anterior[j - 1] + coste_sustitucion,  # sustituir
            )
        fila_anterior = fila_actual
    return fila_anterior[len(b)]


def _nombres_de_capas(doc) -> List[str]:
    return [capa.dxf.name for capa in doc.layers]


def _capas_casi_correctas(doc) -> List[Diagnostico]:
    """Capas del DXF que NO están en el catálogo `AM_*` pero se parecen
    sospechosamente a una que sí lo está -- típicamente un espacio, un
    carácter de más o de menos, o una diferencia de mayúsculas/minúsculas.
    Nunca se interpreta como la capa del catálogo: se reporta, y el
    contenido de esa capa sigue sin leerse por nadie."""
    diagnosticos: List[Diagnostico] = []
    catalogo_exacto = set(parser.CATALOGO_CAPAS_AM)

    for nombre in _nombres_de_capas(doc):
        if nombre in catalogo_exacto:
            continue
        nombre_normalizado = nombre.strip().upper()
        if not nombre_normalizado.startswith("AM"):
            continue

        mejor_candidato = None
        mejor_distancia = None
        solo_mayusculas_o_espacios = False
        for candidato in parser.CATALOGO_CAPAS_AM:
            if nombre_normalizado == candidato:
                mejor_candidato = candidato
                mejor_distancia = 0
                solo_mayusculas_o_espacios = True
                break
            distancia = _distancia_edicion(nombre_normalizado, candidato)
            if distancia <= DISTANCIA_MAXIMA_CASI_CORRECTA and (
                mejor_distancia is None or distancia < mejor_distancia
            ):
                mejor_candidato, mejor_distancia = candidato, distancia

        if mejor_candidato is None:
            continue

        detalle = (
            "coincide salvo mayúsculas/minúsculas o espacios"
            if solo_mayusculas_o_espacios
            else "difiere en %d carácter(es)" % mejor_distancia
        )
        diagnosticos.append(Diagnostico(
            codigo=CAPA_CASI_CORRECTA, severidad=SEVERIDAD_WARNING, capa=nombre,
            mensaje=(
                "La capa '%s' se parece a '%s' del catálogo de clasificación pero no "
                "coincide exactamente (%s); no se ha leído nada de ella. No se corrige "
                "sola -- si la intención era esa, renombra la capa."
                % (nombre, mejor_candidato, detalle)
            ),
            detalle=detalle,
        ))
    return diagnosticos


# ---------------------------------------------------------------------------
# 2. Capas reservadas en uso (AM_UTIL_EXT / AM_CONS_EXT / AM_DESCUENTO)
# ---------------------------------------------------------------------------


def _capas_reservadas_en_uso(doc) -> List[Diagnostico]:
    """Capas reservadas que existen en el DXF y tienen contenido. Se
    reportan como INFO, no como aviso de error: no es una equivocación del
    arquitecto, es una capa del catálogo que todavía no es operativa en esta
    fase -- su contenido sencillamente no se lee ni se usa para nada."""
    diagnosticos: List[Diagnostico] = []
    nombres_presentes = set(_nombres_de_capas(doc))

    for reservada in parser.CAPAS_AM_RESERVADAS:
        if reservada not in nombres_presentes:
            continue
        tiene_contenido = any(
            capa_efectiva == reservada for _entidad, capa_efectiva in parser._recorrer_plano(doc)
        )
        if not tiene_contenido:
            continue
        diagnosticos.append(Diagnostico(
            codigo=CAPA_RESERVADA_NO_OPERATIVA, severidad=SEVERIDAD_INFO, capa=reservada,
            mensaje=(
                "La capa '%s' existe y tiene contenido, pero está reservada: todavía no es "
                "operativa en esta fase del contrato de clasificación. Su contenido no se "
                "lee ni participa en ningún cálculo." % reservada
            ),
        ))
    return diagnosticos


# ---------------------------------------------------------------------------
# 3-5. Envolvente cerrada: ambigua, sin vivienda identificable, o vivienda
#      sin envolvente válida
# ---------------------------------------------------------------------------


def _diagnosticos_envolvente(plano: "parser.PlanoLeido", unidades) -> List[Diagnostico]:
    """Los tres diagnósticos de `AM_CONS_CER` son, en realidad, las tres
    caras de una sola pregunta -- "¿a qué vivienda pertenece cada
    envolvente?" -- así que se calculan aquí juntos, sobre el mismo
    `evaluator.agrupar_por_vivienda_mas_cercana` que usa
    `asignar_envolvente_cerrada`, para no correr el riesgo de que un
    criterio de agrupación diverja del otro con el tiempo.

    Partición exhaustiva y sin solape, para no duplicar el mismo hallazgo
    dos veces: una vivienda con más de una candidata sale en
    `ENVOLVENTE_AMBIGUA`; una vivienda con cero candidatas sale en
    `VIVIENDA_SIN_ENVOLVENTE`. Nunca las dos a la vez para la misma
    vivienda, porque `len(candidatas)` no puede ser a la vez >1 y ==0.

    Nada de esto se calcula si `AM_CONS_CER` no está en uso en absoluto
    (ni una envolvente válida, ni una entidad descartada en esa capa): un
    plano que nunca ha tocado esta capa no recibe ningún diagnóstico sobre
    ella, exactamente como cualquier otro plano heredado.
    """
    diagnosticos: List[Diagnostico] = []

    capa_en_uso = bool(plano.envolventes_cerradas) or any(
        d.capa == parser.CAPA_CONSTRUIDA_CERRADA for d in plano.geometria_no_leida
    )
    if not capa_en_uso:
        return diagnosticos

    if not plano.unit_labels:
        # Sin ninguna etiqueta de vivienda el problema es global -- ninguna
        # envolvente puede emparejarse con nada -- así que se reporta una
        # vez por envolvente, no una vez por vivienda (que además aquí
        # vendrían de `group_rooms_by_proximity`, con nombres sintéticos que
        # no significan nada para un arquitecto).
        for _envolvente in plano.envolventes_cerradas:
            diagnosticos.append(Diagnostico(
                codigo=ENVOLVENTE_SIN_VIVIENDA, severidad=SEVERIDAD_WARNING,
                capa=parser.CAPA_CONSTRUIDA_CERRADA,
                mensaje=(
                    "Hay una envolvente en '%s' pero el plano no tiene ninguna etiqueta de "
                    "vivienda ('VT<n>/<m>'); no se puede saber a qué vivienda pertenece."
                    % parser.CAPA_CONSTRUIDA_CERRADA
                ),
            ))
        return diagnosticos

    asignadas = evaluator.agrupar_por_vivienda_mas_cercana(
        plano.envolventes_cerradas, plano.unit_labels)
    nombres_de_unidades = {u.name for u in unidades}

    for nombre, candidatas in asignadas.items():
        if nombre not in nombres_de_unidades:
            # La etiqueta VT existe en el plano, pero ninguna habitación
            # quedó agrupada bajo ella -- no hay Unit a la que asignar.
            for _candidata in candidatas:
                diagnosticos.append(Diagnostico(
                    codigo=ENVOLVENTE_SIN_VIVIENDA, severidad=SEVERIDAD_WARNING,
                    capa=parser.CAPA_CONSTRUIDA_CERRADA, vivienda=nombre,
                    mensaje=(
                        "Una envolvente en '%s' está más cerca de la etiqueta '%s' que de "
                        "cualquier otra, pero esa etiqueta no tiene ninguna vivienda con "
                        "habitaciones asociada." % (parser.CAPA_CONSTRUIDA_CERRADA, nombre)
                    ),
                ))
            continue
        if len(candidatas) > 1:
            diagnosticos.append(Diagnostico(
                codigo=ENVOLVENTE_AMBIGUA, severidad=SEVERIDAD_WARNING,
                capa=parser.CAPA_CONSTRUIDA_CERRADA, vivienda=nombre,
                mensaje=(
                    "%d envolventes en '%s' están todas más cerca de '%s' que de cualquier "
                    "otra vivienda; no se elige ninguna automáticamente."
                    % (len(candidatas), parser.CAPA_CONSTRUIDA_CERRADA, nombre)
                ),
            ))

    for unit in unidades:
        if not asignadas.get(unit.name):
            diagnosticos.append(Diagnostico(
                codigo=VIVIENDA_SIN_ENVOLVENTE, severidad=SEVERIDAD_WARNING,
                capa=parser.CAPA_CONSTRUIDA_CERRADA, vivienda=unit.name,
                mensaje=(
                    "'%s' está en uso en el plano, pero la vivienda '%s' no tiene ninguna "
                    "envolvente asignada." % (parser.CAPA_CONSTRUIDA_CERRADA, unit.name)
                ),
            ))

    return diagnosticos


# ---------------------------------------------------------------------------
# 6. Geometría descartada dentro de una capa AM_* -- se reutiliza
#    `PlanoLeido.geometria_no_leida`, nunca se recalcula
# ---------------------------------------------------------------------------

# GEOMETRIA_INVALIDA es la única de las cuatro que es un defecto real de la
# geometría en sí (autointersección) y no una convención de dibujo
# incumplida: por eso es la única que sube a ERROR.
_SEVERIDAD_POR_MOTIVO = {
    parser.MOTIVO_GEOMETRIA_INVALIDA: SEVERIDAD_ERROR,
    parser.MOTIVO_TIPO_NO_SOPORTADO: SEVERIDAD_WARNING,
    parser.MOTIVO_POLILINEA_ABIERTA: SEVERIDAD_WARNING,
    parser.MOTIVO_MENOS_DE_3_VERTICES: SEVERIDAD_WARNING,
}

_TEXTO_POR_MOTIVO = {
    parser.MOTIVO_GEOMETRIA_INVALIDA: "geometría inválida",
    parser.MOTIVO_TIPO_NO_SOPORTADO: "tipo de entidad no soportado",
    parser.MOTIVO_POLILINEA_ABIERTA: "polilínea abierta",
    parser.MOTIVO_MENOS_DE_3_VERTICES: "menos de 3 vértices",
}


def _diagnosticos_geometria_descartada(plano: "parser.PlanoLeido") -> List[Diagnostico]:
    """Envuelve `PlanoLeido.geometria_no_leida` como `Diagnostico`, solo para
    las capas `AM_*` operativas -- la geometría descartada del modo heredado
    ya tiene su propio significado (Fase 1) y no forma parte del contrato de
    clasificación que audita este validador."""
    diagnosticos: List[Diagnostico] = []
    for descarte in plano.geometria_no_leida:
        if descarte.capa not in parser.CAPAS_AM_OPERATIVAS:
            continue
        severidad = _SEVERIDAD_POR_MOTIVO.get(descarte.motivo, SEVERIDAD_WARNING)
        texto = _TEXTO_POR_MOTIVO.get(descarte.motivo, descarte.motivo)
        mensaje = "Entidad %s descartada en '%s': %s." % (descarte.tipo, descarte.capa, texto)
        if descarte.detalle:
            mensaje += " (%s)" % descarte.detalle
        diagnosticos.append(Diagnostico(
            codigo=descarte.motivo, severidad=severidad, capa=descarte.capa,
            handle=descarte.handle or "", mensaje=mensaje, detalle=descarte.detalle,
        ))
    return diagnosticos


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------


def validar_capas_am(doc, plano: "parser.PlanoLeido", unidades) -> List[Diagnostico]:
    """Diagnósticos NO bloqueantes sobre el uso del contrato de clasificación
    `AM_*` en este DXF. Nunca cambia `doc`, `plano` ni `unidades`: es de
    solo lectura, y no se llama desde ningún endpoint todavía (Fase 2 no
    toca `app.py`, `api_serializer.py` ni el visor).

    `doc` hace falta aparte de `plano` porque dos de las comprobaciones
    -capas casi correctas y capas reservadas en uso- necesitan el catálogo
    de capas del DXF completo, que `PlanoLeido` no lleva (solo lleva lo que
    ya se leyó de las capas concretas que sí importaban).
    """
    diagnosticos: List[Diagnostico] = []
    diagnosticos.extend(_capas_casi_correctas(doc))
    diagnosticos.extend(_capas_reservadas_en_uso(doc))
    diagnosticos.extend(_diagnosticos_geometria_descartada(plano))
    diagnosticos.extend(_diagnosticos_envolvente(plano, unidades))
    return diagnosticos
