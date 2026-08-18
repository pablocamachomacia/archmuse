"""Motor de efectos en cadena: para un puñado de problemas ya detectados por
`evaluator`/`circulation`, describe las consecuencias secundarias que ese
problema suele arrastrar en la práctica (privacidad, acústica, evacuación,
eficiencia energética...) — es una capa de interpretación/priorización sobre
resultados que YA existen, no una regla de cumplimiento nueva: no calcula
ningún `passed` propio, solo envuelve los resultados de `UnitScore` (y de
`circulation.evaluate_circulation`) que ya los calculan.

Reutiliza la misma detección de adyacencia física que `circulation.py`
(distancia entre contornos con tolerancia — ver `WALL_GAP_TOLERANCE_M` y su
justificación allí) para la regla 3 (baño con acceso directo desde el
salón): en los DXF reales de Pablo los contornos de habitación no se tocan
literalmente, dejan un hueco de hasta 0.38m por el grosor del muro, así que
un `intersects()`/`touches()` geométrico directo nunca detectaría esa
adyacencia — `circulation._check_bathroom_access` ya resuelve esto, aquí
solo se reutiliza su resultado.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .circulation import evaluate_circulation
from .evaluator import (
    ACCESSIBLE_BATHROOM_MIN_AREA_M2,
    DEFAULT_TIPOLOGIA,
    MIN_BATHROOM_TURNING_SPACE_M,
    IssueReport,
    UnitScore,
    _DORMITORIO_ANY_PATTERN,
    _normalize,
    evaluate_itinerario_accesible,
)


@dataclass
class EfectoDerivado:
    titulo: str
    descripcion: str
    normativa_relacionada: str
    severidad: str  # "CRITICO" | "IMPORTANTE" | "RECOMENDACION"


@dataclass
class ChainEffect:
    problema_origen: IssueReport
    efectos_derivados: List[EfectoDerivado] = field(default_factory=list)
    impacto_coste_estimado: str = ""  # "Bajo <500€" | "Medio 500-3000€" | "Alto >3000€"
    urgencia: str = ""  # "INMEDIATA" | "ANTES_OBRA" | "EN_PROYECTO"


# `IssueReport.bloque` documenta el rango 1-11 que usa `evaluator.classify_problems`
# (resultados que vienen de un bloque numerado de evaluator.py). Las reglas 3
# y 5 de aquí abajo sintetizan su propio `IssueReport` a partir de un
# resultado que `classify_problems` deliberadamente NO clasifica como
# problema (circulación y orientación son datos informativos en el resto de
# la app) — se les asigna este valor fuera de ese rango para no aparentar
# que vienen de un bloque de evaluator.py que no existe.
_CHAIN_ONLY_BLOQUE = 12


def _regla_pasillo_estrecho(us: UnitScore, tipologia: str) -> List[ChainEffect]:
    """Regla 1: ningún Pasillo alcanza los 1.20m de itinerario accesible
    (`evaluator.evaluate_itinerario_accesible` — CTE DB-SUA-2, solo aplica a
    tipología plurifamiliar)."""
    # Se lee de `UnitScore` en vez de recalcularlo: `score_unit` ya lo evaluó
    # (antes se calculaba tres veces por análisis, aquí y en dos sitios más).
    result = us.itinerario_accesible_result
    if result is None:
        return []
    unit_name = us.unit.name
    origen = IssueReport(
        severity="IMPORTANTE", bloque=11, codigo="CTE-DB-SUA-2-ITIN",
        titulo="Sin itinerario accesible ≥1.20m", descripcion=result.message,
        impacto="Dificulta el desplazamiento de una silla de ruedas entre zonas de la vivienda; "
                "incumple el itinerario accesible exigido en edificios plurifamiliares.",
        solucion="Ampliar al menos un pasillo a ≥1.20m para garantizar itinerario accesible entre "
                 "zonas de la vivienda.",
        room_label=unit_name, unit_name=unit_name,
    )
    return [ChainEffect(
        problema_origen=origen,
        efectos_derivados=[
            EfectoDerivado(
                "Incumplimiento itinerario accesible",
                "Ningún pasillo de la vivienda alcanza los 1.20m exigidos para itinerario accesible.",
                "CTE-DB-SUA-2", "IMPORTANTE",
            ),
            EfectoDerivado(
                "Riesgo de evacuación reducida",
                "Un pasillo estrecho ralentiza la salida de la vivienda en caso de emergencia, "
                "especialmente para personas con movilidad reducida.",
                "CTE-DB-SI-3", "IMPORTANTE",
            ),
            EfectoDerivado(
                "Dificultad de paso de mobiliario",
                "Un pasillo por debajo de 1.20m dificulta mover mobiliario voluminoso (camas, sofás, "
                "electrodomésticos) durante la mudanza o una reforma.",
                "HABITABILIDAD", "RECOMENDACION",
            ),
        ],
        impacto_coste_estimado="Medio 500-3000€",
        urgencia="ANTES_OBRA",
    )]


def _regla_sin_ventilacion_cruzada(us: UnitScore) -> List[ChainEffect]:
    """Regla 2: vivienda sin fachadas opuestas/perpendiculares entre sus
    piezas habitables (`UnitScore.cross_ventilation_result`, ya calculado
    por `evaluator.evaluate_cross_ventilation`)."""
    r = us.cross_ventilation_result
    if r is None or r.passed:
        return []
    unit_name = us.unit.name
    origen = IssueReport(
        severity="IMPORTANTE", bloque=5, codigo="CTE-DB-HS3",
        titulo="Vivienda sin ventilación cruzada", descripcion=r.message,
        impacto="Sin fachadas opuestas o perpendiculares, la renovación de aire depende solo de "
                "ventilación forzada; peor calidad del aire interior.",
        solucion="Reorganizar las habitaciones habitables para que al menos dos den a fachadas "
                 "opuestas o perpendiculares.",
        room_label=unit_name, unit_name=unit_name,
    )
    return [ChainEffect(
        problema_origen=origen,
        efectos_derivados=[
            EfectoDerivado(
                "Riesgo de condensaciones",
                "Sin renovación de aire cruzada, la humedad interior se acumula más fácilmente sobre "
                "las superficies frías, favoreciendo la condensación.",
                "CTE-DB-HE", "IMPORTANTE",
            ),
            EfectoDerivado(
                "Calidad de aire interior deficiente",
                "La renovación de aire depende solo de ventilación forzada o de la apertura puntual "
                "de huecos, reduciendo el caudal de aire realmente renovado.",
                "CTE-DB-HS3", "IMPORTANTE",
            ),
            EfectoDerivado(
                "Penalización de eficiencia energética",
                "El sistema de climatización debe compensar una peor renovación de aire natural, "
                "aumentando el consumo energético de la vivienda.",
                "EFICIENCIA-ENE", "RECOMENDACION",
            ),
        ],
        impacto_coste_estimado="Medio 500-3000€",
        urgencia="EN_PROYECTO",
    )]


def _regla_bano_sin_antesala(us: UnitScore) -> List[ChainEffect]:
    """Regla 3: baño con adyacencia directa al Salón/Cocina, sin pasillo ni
    vestíbulo intermedio (`circulation._check_bathroom_access`, vía
    `evaluate_circulation`) — una vivienda puede tener más de un baño en
    esta situación, así que puede devolver varios `ChainEffect`."""
    unit_name = us.unit.name
    effects: List[ChainEffect] = []
    for route in evaluate_circulation(us).routes:
        if route.tipo != "bano_sin_antesala" or route.passed:
            continue
        bano = route.path[-1]
        origen = IssueReport(
            severity="IMPORTANTE", bloque=_CHAIN_ONLY_BLOQUE, codigo="HABITABILIDAD-CIRC",
            titulo="Baño con acceso directo desde el salón", descripcion=route.message,
            impacto="Reduce la privacidad y el confort del baño al no existir un espacio de "
                    "transición desde una pieza social.",
            solucion="Introducir un pasillo, vestíbulo o antesala entre el salón y el baño, o "
                     "reorganizar el acceso al baño desde otra zona de la vivienda.",
            room_label=bano.label or "", unit_name=unit_name,
        )
        effects.append(ChainEffect(
            problema_origen=origen,
            efectos_derivados=[
                EfectoDerivado(
                    "Problema de privacidad",
                    "El baño queda expuesto directamente a la zona social al carecer de un espacio "
                    "de transición, comprometiendo su privacidad ante invitados.",
                    "HABITABILIDAD", "RECOMENDACION",
                ),
                EfectoDerivado(
                    "Riesgo acústico en zona de día",
                    "Los ruidos de instalaciones y de uso del baño se transmiten directamente al "
                    "salón al no haber una antesala que actúe de amortiguador acústico.",
                    "CTE-DB-HR", "IMPORTANTE",
                ),
            ],
            impacto_coste_estimado="Bajo <500€",
            urgencia="EN_PROYECTO",
        ))
    return effects


def _regla_habitacion_tubo(us: UnitScore) -> List[ChainEffect]:
    """Regla 4: habitación con proporción largo/corto > 2.5
    (`UnitScore.proportion_results`, ya calculado por
    `evaluator.evaluate_proportions`; excluye Pasillo, ver esa función)."""
    unit_name = us.unit.name
    effects: List[ChainEffect] = []
    for r in us.proportion_results:
        if r.passed:
            continue
        origen = IssueReport(
            severity="IMPORTANTE", bloque=1, codigo="HABITABILIDAD",
            titulo="Habitación con proporción 'tubo'", descripcion=r.message,
            impacto="Dificulta amueblar la estancia con criterios funcionales; reduce el confort de uso.",
            solucion="Ajustar la geometría de la habitación para acercar la proporción largo/corto a "
                     "1:2.5 o menos.",
            room_label=r.room_label or "", unit_name=unit_name,
        )
        effects.append(ChainEffect(
            problema_origen=origen,
            efectos_derivados=[
                EfectoDerivado(
                    "Iluminación natural deficiente en zona profunda",
                    "La proporción alargada aleja buena parte de la superficie de la habitación de "
                    "la fachada, dejando su zona más profunda con menos luz natural directa.",
                    "CTE-DB-HS3", "RECOMENDACION",
                ),
                EfectoDerivado(
                    "Acústica pobre por geometría",
                    "Una planta muy alargada y estrecha favorece reflexiones y reverberación "
                    "indeseadas frente a proporciones más equilibradas.",
                    "CTE-DB-HR", "RECOMENDACION",
                ),
                EfectoDerivado(
                    "Dificultad de amueblamiento",
                    "La proporción 'tubo' deja poco margen para disponer mobiliario estándar sin "
                    "bloquear el paso o dejar zonas muertas.",
                    "HABITABILIDAD", "RECOMENDACION",
                ),
            ],
            impacto_coste_estimado="Bajo <500€",
            urgencia="EN_PROYECTO",
        ))
    return effects


def _regla_dormitorio_norte(us: UnitScore) -> List[ChainEffect]:
    """Regla 5: Dormitorio con fachada larga orientada a norte
    (`UnitScore.orientation_results`, rating "penalizada" — para un
    Dormitorio esa valoración solo se da con compass "N", ver
    `evaluator.ORIENTATION_RULES`)."""
    unit_name = us.unit.name
    effects: List[ChainEffect] = []
    for o in us.orientation_results:
        if o.rating != "penalizada":
            continue
        if not (o.room.label and _DORMITORIO_ANY_PATTERN.search(_normalize(o.room.label))):
            continue
        origen = IssueReport(
            severity="RECOMENDACION", bloque=_CHAIN_ONLY_BLOQUE, codigo="CTE-DB-HE-ORIENT",
            titulo="Dormitorio orientado a norte", descripcion=o.message,
            impacto="Menor aporte solar pasivo y mayor riesgo de sensación de frío en el dormitorio "
                    "durante el invierno.",
            solucion="Reorientar el dormitorio hacia este o sur si la distribución lo permite, o "
                     "reforzar el aislamiento térmico de su fachada norte.",
            room_label=o.room_label, unit_name=unit_name,
        )
        effects.append(ChainEffect(
            problema_origen=origen,
            efectos_derivados=[
                EfectoDerivado(
                    "Riesgo de condensaciones superficiales",
                    "Una fachada norte se enfría más y favorece la acumulación de humedad relativa "
                    "interior si el aislamiento o la barrera de vapor no están bien resueltos.",
                    "CTE-DB-HE", "RECOMENDACION",
                ),
                EfectoDerivado(
                    "Confort térmico reducido en invierno",
                    "Sin aporte solar directo, el dormitorio pierde calor más rápido y necesita más "
                    "calefacción para mantener una temperatura confortable.",
                    "EFICIENCIA-ENE", "RECOMENDACION",
                ),
            ],
            impacto_coste_estimado="Bajo <500€",
            urgencia="EN_PROYECTO",
        ))
    return effects


def _regla_sin_bano_adaptado(us: UnitScore, tipologia: str) -> List[ChainEffect]:
    """Regla 6: ningún baño de la vivienda alcanza superficie + espacio de
    giro de baño adaptado (`UnitScore.accessible_bathroom_area_result`, ya
    calculado por `evaluator.evaluate_accessible_bathroom_area`)."""
    r = us.accessible_bathroom_area_result
    if r is None or r.passed:
        return []
    unit_name = us.unit.name
    severity = "IMPORTANTE" if tipologia in ("unifamiliar", "rehabilitacion") else "CRITICO"
    origen = IssueReport(
        severity=severity, bloque=11, codigo="CTE-DB-SUA-1",
        titulo="Baño sin superficie ni giro de baño adaptado", descripcion=r.message,
        impacto="Ningún baño de la vivienda cumple el estándar de baño adaptado; incumple "
                "accesibilidad universal si se exige vivienda accesible.",
        solucion=f"Redimensionar un baño hasta alcanzar {ACCESSIBLE_BATHROOM_MIN_AREA_M2}m² de "
                 f"superficie con espacio libre de giro de ⌀{MIN_BATHROOM_TURNING_SPACE_M}m.",
        room_label=unit_name, unit_name=unit_name,
    )
    return [ChainEffect(
        problema_origen=origen,
        efectos_derivados=[
            EfectoDerivado(
                "Incumplimiento itinerario accesible completo",
                "Sin un baño con superficie y giro suficientes, ninguna zona de aseo de la vivienda "
                "resulta accesible para personas usuarias de silla de ruedas.",
                "CTE-DB-SUA-1", "CRITICO",
            ),
            EfectoDerivado(
                "Imposibilidad de uso por personas con movilidad reducida",
                "La vivienda no puede considerarse accesible ni adaptable para un residente con "
                "movilidad reducida, limitando su uso futuro y su valor de reventa o alquiler.",
                "HABITABILIDAD", "IMPORTANTE",
            ),
        ],
        impacto_coste_estimado="Alto >3000€",
        urgencia="INMEDIATA",
    )]


def compute_chain_effects_for_unit(us: UnitScore, tipologia: str = DEFAULT_TIPOLOGIA) -> List[ChainEffect]:
    """Ejecuta las 6 reglas de efectos en cadena sobre una única vivienda."""
    effects: List[ChainEffect] = []
    effects.extend(_regla_pasillo_estrecho(us, tipologia))
    effects.extend(_regla_sin_ventilacion_cruzada(us))
    effects.extend(_regla_bano_sin_antesala(us))
    effects.extend(_regla_habitacion_tubo(us))
    effects.extend(_regla_dormitorio_norte(us))
    effects.extend(_regla_sin_bano_adaptado(us, tipologia))
    return effects

