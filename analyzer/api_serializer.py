"""Serialización JSON del análisis, para la API REST que consume la SPA
(`static/index.html`).

Convierte los resultados de `evaluator.evaluate_advanced` (+ el análisis IA
opcional de `ai_analyst.analyze_with_ai`) en un único diccionario
serializable a JSON: viviendas con sus habitaciones (área + problemas
detectados por habitación) y el SVG del plano ya renderizado
(`plan_svg.generate_plan_svg`), listo para insertarse en el DOM por la SPA.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import List, Optional

from shapely.geometry.base import BaseGeometry

from .ai_analyst import AIAnalysis
from .referencias_normativas import AVISO as NORMATIVA_AVISO
from .referencias_normativas import referencia as referencia_normativa
from .chain_effects import ChainEffect, compute_chain_effects_for_unit
from .cte_checker import generar_checklist_cte
from .evaluator import (
    AdvancedAnalysis,
    BuildabilityResult,
    BuildingCompactnessResult,
    BuildingOrientationResult,
    CeilingHeightResult,
    DEFAULT_TIPOLOGIA,
    DEFAULT_ZONA_CTE,
    IssueReport,
    MaxFloorsResult,
    RetranqueosResult,
    SolarOccupationResult,
    UnitScore,
    classify_problems,
    get_missing_data_warnings,
    rating_con_severidad,
)
from .circulation import evaluate_circulation, serialize_unit_circulation
from .parser import CAPA_UTIL_INTERIOR, EntidadDescartada, Room
from .plan_svg import generate_plan_svg, layout_room_polygons, room_problems, room_type
from .scoring import (
    compute_project_breakdown, compute_puntos_ganados, compute_scoring_breakdown,
    serialize_breakdown)
from .spatial_quality import evaluate_spatial_quality, serialize_unit_quality
from .validacion_capas import Diagnostico


def _polygon_points(polygon: BaseGeometry) -> List[List[float]]:
    """Anillo exterior de `polygon` como lista de [x, y] en metros, sin el
    punto de cierre duplicado. Para el (raro) caso de un MultiPolygon usa
    solo el sub-polígono de mayor área — el visor 3D dibuja una habitación
    como un único volumen, no varios."""
    geom = polygon
    if geom.geom_type == "MultiPolygon":
        geom = max(geom.geoms, key=lambda g: g.area, default=None)
        if geom is None:
            return []
    if geom.geom_type != "Polygon":
        return []
    coords = list(geom.exterior.coords)
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return [[round(x, 3), round(y, 3)] for x, y in coords]


def _serialize_room(room: Room, unit_score: UnitScore, polygon: BaseGeometry) -> dict:
    solar = next((sh for sh in unit_score.solar_hours_results if sh.room is room), None)
    orientation = next((o for o in unit_score.orientation_results if o.room is room), None)
    light_factor = next(
        (nf for nf in unit_score.natural_light_factor_results if nf.room is room), None
    )
    return {
        "nombre": room.label or "(sin etiqueta)",
        "area_m2": round(room.area_m2, 2),
        "tipo": room_type(room),
        "problemas": room_problems(room, unit_score),
        # Estimación de horas de sol (Bloque 3) — null para habitaciones sin
        # regla de orientación (Baño, Aseo, Pasillo, Terraza/Tendedero...).
        # No se muestra todavía en la SPA, solo disponible en el JSON.
        "horas_sol_verano": solar.hours_summer if solar else None,
        "horas_sol_invierno": solar.hours_winter if solar else None,
        # Orientación de la fachada larga (Bloque 4, `evaluate_orientation`):
        # null si la habitación no tiene fachada exterior detectable.
        # "orientacion_valoracion" es "óptima"/"aceptable"/"penalizada"/
        # "sin regla" (esta última para tipos sin regla definida, p. ej.
        # Pasillo o Terraza) — misma valoración que ya usa `room_problems`
        # para decidir si la orientación entra como problema.
        "orientacion_cardinal": orientation.compass if orientation else None,
        "orientacion_valoracion": orientation.rating if orientation else None,
        # Factor de luz natural estimado (Bloque 15, `evaluate_natural_lighting`),
        # en % — null para habitaciones sin regla de iluminación natural
        # (solo se calcula para Salón/Cocina y Dormitorios con fachada
        # exterior) o sin fachada exterior detectable.
        "factor_luz_natural_pct": round(light_factor.fln_pct, 1) if light_factor else None,
        # Polígono en metros reales, con el mismo layout (real/compactado/
        # cuadrícula) que el plano SVG — lo consume el visor 3D para
        # extrudir la habitación sin tener que recalcular su disposición.
        "poligono": _polygon_points(polygon),
    }


def _clasificacion_capas(unit) -> str:
    """'am' si esta vivienda tiene alguna habitación leída del contrato de
    clasificación DXF (`AM_UTIL_INT`, `Room.layer`), 'heredado' en caso
    contrario -- incluida una vivienda sin ninguna habitación. `leer_plano`
    decide la fuente una vez para todo el plano (Fase 1: si `AM_UTIL_INT`
    tiene contenido, TODAS las rooms vienen de ahí; si no, ninguna), así que
    basta con mirar una habitación cualquiera de la vivienda."""
    return "am" if any(r.layer == CAPA_UTIL_INTERIOR for r in unit.rooms) else "heredado"


def _serialize_entidad_descartada(entidad: EntidadDescartada) -> dict:
    return {
        "motivo": entidad.motivo,
        "capa": entidad.capa,
        "tipo": entidad.tipo,
        "handle": entidad.handle,
        "detalle": entidad.detalle,
    }


def _serialize_diagnostico(diagnostico: Diagnostico) -> dict:
    return {
        "codigo": diagnostico.codigo,
        "severidad": diagnostico.severidad,
        "mensaje": diagnostico.mensaje,
        "capa": diagnostico.capa,
        "vivienda": diagnostico.vivienda,
        "handle": diagnostico.handle,
        "detalle": diagnostico.detalle,
    }


def _serialize_chain_effect(effect: ChainEffect) -> dict:
    return {
        "problema_origen": _serialize_issue(effect.problema_origen),
        "efectos_derivados": [asdict(e) for e in effect.efectos_derivados],
        "impacto_coste_estimado": effect.impacto_coste_estimado,
        "urgencia": effect.urgencia,
    }


def _serialize_unit(
    unit_score: UnitScore, unit_id: str, norte_grados: float, tipologia: str, issues: List[IssueReport]
) -> dict:
    u = unit_score
    problemas_vivienda: List[str] = []
    if not u.unit_minimum_area_result.passed:
        problemas_vivienda.append(u.unit_minimum_area_result.message)
    if u.bathroom_accessibility_result and not u.bathroom_accessibility_result.passed:
        problemas_vivienda.append(u.bathroom_accessibility_result.message)
    if u.bathroom_ratio_result and not u.bathroom_ratio_result.passed:
        problemas_vivienda.append(u.bathroom_ratio_result.message)
    if u.cross_ventilation_result and not u.cross_ventilation_result.passed:
        problemas_vivienda.append(u.cross_ventilation_result.message)
    if u.spatial_hierarchy_result and not u.spatial_hierarchy_result.passed:
        problemas_vivienda.append(u.spatial_hierarchy_result.message)
    if u.circulation_efficiency_result and not u.circulation_efficiency_result.passed:
        problemas_vivienda.append(u.circulation_efficiency_result.message)

    layout = layout_room_polygons(u)
    polygon_by_room = {id(room): polygon for room, polygon in layout}

    # Un solo CRÍTICO veta el verde y el amarillo (ver
    # `evaluator.rating_con_severidad`). Antes, VT1/3 de `ejemplo.dxf` salía
    # como "92, Cumplimiento correcto" junto a 2 críticos de accesibilidad:
    # la puntuación es un porcentaje de comprobaciones superadas y 2 fallos
    # entre 45 dan 95, aunque los dos sean bloqueantes.
    criticos_vivienda = sum(
        1 for i in (issues or []) if i.severity == "CRITICO" and i.unit_name == u.unit.name
    )

    # Reglas normativas que `evaluator.py` ha aplicado REALMENTE a esta
    # vivienda, con el umbral que ha usado. El frontend las pinta tal cual:
    # antes recalculaba la superficie mínima contra una tabla propia por
    # comunidad autónoma que contradecía a esta (30 m² aquí, 40 m² allí para
    # una plurifamiliar en Madrid). `evaluator.py` es la única fuente de
    # verdad durante la transición al corpus territorial.
    normativa_aplicada = {
        "reglas": [
            {
                "nombre": "Superficie útil mínima de vivienda",
                "valor": (
                    f"{u.unit_minimum_area_result.useful_area_m2:.1f} m² "
                    f"(mínimo {u.unit_minimum_area_result.min_area_m2:.0f} m²)"
                ),
                "cumple": u.unit_minimum_area_result.passed,
                "base": f"Umbral por tipología: {tipologia}.",
            }
        ],
        "aviso": (
            "Umbral resuelto por tipología, no por comunidad autónoma. La "
            "superficie mínima de vivienda es competencia autonómica: hasta "
            "que el corpus territorial esté poblado, esta comprobación no "
            "distingue entre comunidades."
        ),
    }

    return {
        "id": unit_id,
        "nombre": u.unit.name,
        "normativa_aplicada": normativa_aplicada,
        "puntuacion": round(u.score_pct),
        "valoracion": rating_con_severidad(u.score_pct, criticos_vivienda),
        "superficie_total_m2": round(u.unit.total_area_m2, 2),
        # Superficie útil real de la vivienda (DB-SI Anejo A), ya calculada por
        # `evaluate_unit_minimum_area` -- antes solo vivía embebida como texto
        # formateado dentro de `normativa_aplicada.reglas[0].valor` ("42.3 m²
        # (mínimo 30 m²)"), sin ningún campo numérico que un consumidor pudiera
        # leer sin parsear una frase. La necesita el Ratio de Eficiencia de
        # Superficie (Útil/Construida) de Viabilidad Financiera
        # (docs/prd/2026-08-17-analisis-de-viabilidad-financiera.md) -- mismo
        # dato, expuesto también como número.
        "superficie_util_m2": round(u.unit_minimum_area_result.useful_area_m2, 2),
        # Contrato de clasificación DXF (`AM_*`, Fases 1-3 en `evaluator.py`).
        # NUNCA suman a "superficie_total_m2" -- esa cifra sigue siendo,
        # exactamente igual que antes, solo la suma de `habitaciones`
        # (`AM_UTIL_INT`/modo heredado). `envolvente_cerrada_m2` es `None`
        # cuando el plano no declara `AM_CONS_CER`, o cuando la asignación a
        # esta vivienda fue ambigua (`asignar_envolvente_cerrada`) -- las dos
        # situaciones se ven igual aquí a propósito, el detalle de cuál de
        # las dos ha ocurrido vive en "diagnosticos_clasificacion".
        "envolvente_cerrada_m2": (
            round(u.unit.envolvente_cerrada.area, 2)
            if u.unit.envolvente_cerrada is not None else None
        ),
        "superficie_util_exterior_m2": round(
            sum(p.area for p in u.unit.superficies_utiles_exteriores), 2
        ),
        "envolvente_exterior_m2": round(
            sum(p.area for p in u.unit.envolventes_exteriores), 2
        ),
        # 'am' si esta vivienda viene del contrato de capas AM_*, 'heredado'
        # si viene de la capa de estancias clásica (`00 areas` u otra).
        "clasificacion_capas": _clasificacion_capas(u.unit),
        # Estructurado para que un consumidor (p. ej. `analyzer.pliego_
        # verificador`) pueda saber si la vivienda cumple accesibilidad sin
        # tener que reconocer el mensaje de `problemas_vivienda` por texto.
        # `evaluable=False` cuando `bathroom_accessibility_result` es `None`
        # (la comprobación no aplicaba a esta vivienda) -- distinto de
        # `cumple=False`, que es un incumplimiento real.
        "accesibilidad": {
            "evaluable": u.bathroom_accessibility_result is not None,
            "cumple": (
                u.bathroom_accessibility_result.passed
                if u.bathroom_accessibility_result is not None else None
            ),
        },
        "habitaciones": [
            _serialize_room(r, u, polygon_by_room.get(id(r), r.polygon)) for r in u.unit.rooms
        ],
        # Problemas que son de la vivienda completa (no de una habitación
        # concreta). La eficiencia útil/total ya no se añade aquí como
        # string (Bloque 12): va clasificada con severidad en "issues".
        "problemas_vivienda": problemas_vivienda,
        "svg": generate_plan_svg(u, norte_grados=norte_grados),
        # Efectos en cadena (`analyzer/chain_effects.py`): consecuencias
        # secundarias que ciertos problemas ya detectados suelen arrastrar
        # en la práctica — no son problemas nuevos, solo una capa de
        # interpretación/priorización sobre los ya existentes.
        "efectos_cadena": [
            _serialize_chain_effect(e) for e in compute_chain_effects_for_unit(u, tipologia)
        ],
        # Checklist de Cumplimiento CTE (docs/prd/2026-08-17-checklist-
        # cumplimiento-cte.md, aprobado 2026-08-17) -- agregación de reglas ya
        # calculadas por `evaluator.py`, nunca un recálculo paralelo. Se
        # genera aquí con `dos_salidas_confirmado=False` por defecto: el
        # ítem de evacuación nunca cambia de estado con esa casilla (sigue
        # `no_evaluable` siempre, ver `cte_checker.py`), así que el frontend
        # puede recomponer el texto del umbral con `datos` sin volver a
        # pedir el checklist al servidor.
        "checklist_cte": [
            {
                "codigo": it.codigo, "titulo": it.titulo, "estado": it.estado,
                "detalle": it.detalle, "referencia": it.referencia, "datos": it.datos,
            }
            for it in generar_checklist_cte(u, tipologia)
        ],
        # Puntuación desglosada por categoría (`analyzer/scoring.py`,
        # ADITIVA a "puntuacion"/"valoracion" de arriba, que siguen viniendo
        # de `UnitScore.score_pct`/`.rating` sin tocar) — solo con los
        # issues de ESTA vivienda (`unit_name` o issues de edificio sin
        # vivienda propia, "").
        "desglose_puntuacion": serialize_breakdown(
            compute_scoring_breakdown(
                [i for i in issues if i.unit_name == u.unit.name or i.unit_name == ""]
            )
        ),
    }


def serialize_ai_analysis(ai_analysis: Optional[AIAnalysis]) -> Optional[dict]:
    """Pública (sin `_`) porque, a diferencia del resto de `_serialize_*` de
    este módulo, `app.py` la necesita también fuera de `serialize_analysis`
    -- para el endpoint bajo demanda que llama a `analyze_with_ai` después
    de analizar, no solo durante."""
    if ai_analysis is None:
        return None
    return {
        "diagnosticos": [
            {"vivienda": d.vivienda, "diagnostico": d.diagnostico}
            for d in ai_analysis.diagnosticos
        ],
        "mejoras_prioritarias": list(ai_analysis.mejoras_prioritarias),
        "comparativa": ai_analysis.comparativa,
        "conclusion_ejecutiva": ai_analysis.conclusion_ejecutiva,
    }


def _serialize_issue(issue: IssueReport) -> dict:
    d = asdict(issue)
    # La referencia normativa la decide el servidor, no el navegador: esta
    # tabla vivía en `static/app.js` y el cliente afirmaba a qué norma
    # pertenecía cada incidencia sin que nadie se lo hubiera dicho. Es
    # orientativa y va siempre acompañada de `normativa_aviso` (ver
    # `analyzer/referencias_normativas.py`).
    d["referencia_normativa"] = referencia_normativa(d.get("codigo", ""))
    return d


def serialize_analysis(
    filename: str,
    rooms: List[Room],
    advanced: AdvancedAnalysis,
    norte_grados: float,
    ai_analysis: Optional[AIAnalysis],
    edificio: Optional[dict] = None,
    advertencias: Optional[List[str]] = None,
    problemas_edificio: Optional[List[str]] = None,
    superficie_solar_m2: Optional[float] = None,
    superficie_total_construida_m2: Optional[float] = None,
    normativa: Optional[dict] = None,
    solar_occupation: Optional[SolarOccupationResult] = None,
    buildability: Optional[BuildabilityResult] = None,
    max_floors: Optional[MaxFloorsResult] = None,
    compactness: Optional[BuildingCompactnessResult] = None,
    building_orientation: Optional[BuildingOrientationResult] = None,
    retranqueos: Optional[RetranqueosResult] = None,
    ceiling_height: Optional[CeilingHeightResult] = None,
    proyecto: Optional[dict] = None,
    solar: Optional[dict] = None,
    capas_am_detectadas: Optional[List[str]] = None,
    geometria_no_leida: Optional[List[EntidadDescartada]] = None,
    diagnosticos_clasificacion: Optional[List[Diagnostico]] = None,
) -> dict:
    """Construye el payload JSON completo devuelto por `POST /api/analizar`
    (y, con `edificio` informado, por `POST /api/generar`). `edificio` solo
    se pasa para proyectos generados con IA — su sola presencia (no-`None`)
    en el JSON es lo que la SPA usa para decidir si mostrar el botón "Ver en
    3D": un DXF analizado no tiene un número de plantas ni una altura libre
    conocidos, así que ese botón no tiene sentido ahí. `advertencias` (solo
    en proyectos generados) son viviendas cuya geometría no pasó la
    validación de `ai_generator._validate_unit` tras el reintento — ver
    `ai_generator.generate_project`. `problemas_edificio`, `superficie_solar_m2`
    y `normativa` (solo en proyectos generados) alimentan las reglas de
    urbanismo básico de `evaluator` (ocupación, edificabilidad, plantas
    máximas) — ver `app.py:generar`. `superficie_total_construida_m2` es la
    misma cifra que ya calcula `evaluate_buildability` (Bloque 6) para
    `problemas_edificio`, expuesta aquí también sin redondear a texto, en
    `"urbanismo"` — para `analyzer.pliego_verificador`, que necesita comparar
    contra `edificabilidad_maxima_m2` de un pliego (una cota absoluta en m²,
    no el ratio m²techo/m²suelo de `edificabilidad_real`) sin reimplementar
    el cálculo. `solar_occupation`, `buildability`,
    `max_floors`, `compactness`, `building_orientation` y `ceiling_height`
    son los mismos resultados estructurados (no solo su `.message`) que
    alimentan `problemas_edificio`, pasados aparte porque `classify_problems`
    (Bloque 12) los necesita para construir `IssueReport` con severidad — no
    viven dentro de `AdvancedAnalysis`, que no conoce datos de solar/normativa
    ni de altura libre. `advanced.fire_compartmentation` sí vive dentro de
    `AdvancedAnalysis` (se calcula a partir de `units`, disponible en ambos
    flujos) y se pasa directamente a `classify_problems` sin necesitar un
    parámetro propio aquí.

    `capas_am_detectadas`, `geometria_no_leida` y `diagnosticos_clasificacion`
    (cierre de la integración del contrato de clasificación DXF `AM_*`) solo
    los informa `/api/analizar` (ver `app.py`): un proyecto generado con IA
    no tiene DXF ni capas que detectar. Los tres son `None`/vacíos por
    defecto -- un llamador que no los pasa (incluido `/api/generar`, sin
    tocar) obtiene listas vacías en el JSON, nunca la clave ausente."""
    unit_scores = advanced.unit_scores
    global_score = (
        sum(u.score_pct for u in unit_scores) / len(unit_scores) if unit_scores else 0.0
    )

    total_problemas = sum(
        len(room_problems(r, u)) for u in unit_scores for r in u.unit.rooms
    ) + sum(1 for u in unit_scores if u.efficiency_result and not u.efficiency_result.passed)

    tipologia = (proyecto or {}).get("tipologia", DEFAULT_TIPOLOGIA)
    zona_cte = (proyecto or {}).get("zona_cte", DEFAULT_ZONA_CTE)
    issues = classify_problems(
        advanced,
        solar_occupation=solar_occupation,
        buildability=buildability,
        max_floors=max_floors,
        compactness=compactness,
        building_orientation=building_orientation,
        retranqueos=retranqueos,
        ceiling_height=ceiling_height,
        fire_compartmentation=advanced.fire_compartmentation,
        tipologia=tipologia,
        zona_cte=zona_cte,
    )
    issues_summary = {
        "criticos": sum(1 for i in issues if i.severity == "CRITICO"),
        "importantes": sum(1 for i in issues if i.severity == "IMPORTANTE"),
        "recomendaciones": sum(1 for i in issues if i.severity == "RECOMENDACION"),
        "total": len(issues),
    }

    # Sistema de puntuación desglosado por categoría (`analyzer/scoring.py`).
    # Convive con `puntuacion_global`/`valoracion_global` (media de
    # `UnitScore.score_pct`), que se mantiene sin tocar: son dos sistemas
    # distintos y cuál debe ser LA puntuación sigue sin decidirse — ver
    # `docs/design/2026-08-02-dos-sistemas-de-puntuacion.md`.
    #
    # `compute_puntos_ganados` rellena `IssueReport.puntos_ganados` in place
    # sobre `issues`, así que tiene que ejecutarse ANTES de serializar
    # "issues"/"viviendas" más abajo.
    compute_puntos_ganados(issues)
    # Agregado por vivienda y no de golpe: pasarle los issues de todas las
    # viviendas a `compute_scoring_breakdown` aplica un único techo de 100
    # puntos por categoría a los problemas de todas, y el proyecto puntúa peor
    # cuantas más viviendas tiene. Sobre `ejemplo.dxf` la diferencia era de
    # 69,7 («rojo») frente a 93,8 («verde»).
    desglose_global = compute_project_breakdown(issues, [u.unit.name for u in unit_scores])
    issues_por_impacto = sorted(issues, key=lambda i: -i.puntos_ganados)

    # Calidad espacial (Bloque aparte, heurísticas de diseño — no CTE): ver
    # `analyzer/spatial_quality.py`. `altura_libre_m` solo está informado en
    # proyectos generados (`edificio`); en un DXF analizado el módulo cae a
    # su propio valor de referencia por defecto.
    altura_libre_m = (edificio or {}).get("altura_libre_m")
    calidad_espacial = [
        serialize_unit_quality(u, evaluate_spatial_quality(u, altura_libre_m=altura_libre_m))
        for u in unit_scores
    ]

    # Recorridos y circulaciones (heurísticas de diseño, no CTE — igual que
    # calidad_espacial): ver `analyzer/circulation.py`.
    circulacion = [serialize_unit_circulation(u, evaluate_circulation(u)) for u in unit_scores]

    return {
        "archivo": filename,
        "norte_grados": norte_grados,
        "puntuacion_global": round(global_score),
        # Mismo veto a nivel de proyecto: si alguna vivienda tiene un
        # crítico, el proyecto no puede presentarse en verde.
        "valoracion_global": rating_con_severidad(global_score, issues_summary["criticos"]),
        "total_habitaciones": len(rooms),
        "total_problemas": total_problemas,
        "viviendas": [
            _serialize_unit(u, f"u{i}", norte_grados, tipologia, issues) for i, u in enumerate(unit_scores)
        ],
        "analisis_ia": serialize_ai_analysis(ai_analysis),
        "edificio": edificio,
        "advertencias": advertencias,
        # Números crudos de urbanismo, no solo el mensaje de "problemas_
        # edificio" -- `None` cuando no hay solar (todo DXF analizado hoy,
        # ver docstring). Añadido para `analyzer.pliego_verificador`; ningún
        # consumidor existente lo necesitaba, así que no se ha rellenado
        # nunca hasta ahora.
        "urbanismo": (
            {
                "superficie_solar_m2": superficie_solar_m2,
                "superficie_total_construida_m2": superficie_total_construida_m2,
                "edificabilidad_real": buildability.edificabilidad_real if buildability else None,
                "edificabilidad_maxima": buildability.maximo if buildability else None,
            }
            if superficie_solar_m2 else None
        ),
        # Problemas de urbanismo a nivel de edificio (ocupación, edificabilidad,
        # plantas máximas) — no de vivienda ni habitación, no penalizan score_pct.
        "problemas_edificio": problemas_edificio or [],
        # Avisos de transparencia sobre comprobaciones que el modelo actual no
        # puede evaluar por falta de datos (altura libre, escalera, retranqueos,
        # y ocupación/edificabilidad si faltan sus parámetros de entrada).
        # A nivel de proyecto, no de vivienda ni habitación — no penalizan.
        #
        # Desde 2026-08-05 se suman las limitaciones POR VIVIENDA que declara
        # cada `UnitScore`: reglas que le aplicaban y no se han podido
        # comprobar. Antes, una regla sin datos devolvía un aprobado
        # silencioso; ahora dice que no ha comprobado nada, que es la
        # diferencia entre "tu proyecto cumple" y "tu proyecto cumple lo que
        # sé comprobar".
        # `zona_cte_supuesta` lo pone quien construye `proyecto` (`app.py`,
        # con `cte_zonas.resolver_zona_cte`). Si no viene, no hay aviso: se
        # prefiere callar a afirmar que un dato es supuesto sin saberlo.
        "limitaciones": (
            get_missing_data_warnings(
                superficie_solar_m2, normativa, solar,
                zona_cte=(proyecto or {}).get("zona_cte"),
                zona_cte_supuesta=bool((proyecto or {}).get("zona_cte_supuesta")),
                ciudad=(proyecto or {}).get("ciudad"),
            )
            + [lim for u in unit_scores for lim in u.limitaciones]
        ),
        "proyecto": proyecto,
        # Bloque 12: mismos problemas que "problemas"/"problemas_vivienda"/
        # "problemas_edificio" de arriba, pero normalizados en una única
        # lista plana con severidad (CRITICO/IMPORTANTE/RECOMENDACION),
        # código normativo, impacto y solución.
        "issues": [_serialize_issue(i) for i in issues],
        # Acompaña siempre a `issue.referencia_normativa`: recuerda que es
        # orientativa y no una cita legal certificada.
        "normativa_aviso": NORMATIVA_AVISO,
        "issues_summary": issues_summary,
        "calidad_espacial": calidad_espacial,
        "circulacion": circulacion,
        # Sistema de puntuación desglosado (`analyzer/scoring.py`), a nivel
        # de proyecto completo (todas las viviendas + issues de edificio) —
        # ADITIVO a "puntuacion_global"/"valoracion_global" de arriba.
        "desglose_puntuacion": serialize_breakdown(desglose_global),
        # Mismos issues que "issues" de arriba, pero con `puntos_ganados`
        # relleno y reordenados de mayor a menor impacto en la puntuación
        # total — para el panel "Plan de acción" del frontend.
        "issues_por_impacto": [_serialize_issue(i) for i in issues_por_impacto],
        # Cierre de la integración del contrato de clasificación DXF `AM_*`
        # (Fases 1-3 + este cierre): qué capas operativas están en uso en
        # este plano, el inventario de geometría descartada de esas capas
        # (`parser.EntidadDescartada`), y los diagnósticos de conformidad NO
        # bloqueantes (`validacion_capas.validar_capas_am`) -- capa casi
        # correcta, capa reservada en uso, envolvente ambigua/huérfana. Las
        # tres listas están vacías en cualquier plano sin capas `AM_*` (modo
        # heredado) y en todo proyecto generado con IA (`/api/generar`).
        "capas_am_detectadas": capas_am_detectadas or [],
        "geometria_no_leida": [_serialize_entidad_descartada(e) for e in (geometria_no_leida or [])],
        "diagnosticos_clasificacion": [
            _serialize_diagnostico(d) for d in (diagnosticos_clasificacion or [])
        ],
    }
