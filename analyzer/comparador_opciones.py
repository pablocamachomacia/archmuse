"""Métricas comparativas para las 2 alternativas de "Optimización
Generativa Multi-Opción" (`analyzer/ai_generator.py::generate_project_opciones`).

`docs/prd/2026-08-17-optimizacion-generativa-multi-opcion.md` (aprobado
2026-08-17: 2 opciones, no 3; interpretación FUERTE -- cada una con un
`mix_viviendas` distinto derivado del mismo total de superficie construida
objetivo). Este módulo NO genera nada nuevo con IA ni recalcula geometría:
agrega resultados que `evaluator.py` ya calcula (mismo criterio de no
divergencia que `analyzer/cte_checker.py`) y reutiliza la fórmula de margen
ya en producción (`analyzer/feasibility.py`).

Las 4 métricas del comparador:
- `repercusion_zonas_comunes_pct`: REAL -- superficie del núcleo de
  comunicación vertical (`_NUCLEO_ROOM_NAME`, ya modelado por el generador
  desde 2026-08-17) entre superficie construida total.
- `pct_fachada_aprovechada`: REAL -- reutiliza `evaluator.evaluate_natural_
  light` (ya calcula, por habitación habitable, si tiene fachada exterior).
- `margen_estimado`: ESTIMACIÓN DEL USUARIO -- reutiliza `feasibility.
  calcular_margen_promotor` con los mismos ratio/coste/precio que el
  usuario introduce en Viabilidad Económica, aplicados igual a las 2
  opciones (comparación entre ellas, no una validación de viabilidad real
  de ninguna).
- `balance_tipologias`: el propio `mix_viviendas` usado para generar esa
  opción -- no se recalcula, ya se conoce de antemano.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .ai_generator import GeneratedProject, _es_unidad_residencial, _NUCLEO_ROOM_NAME
from .evaluator import evaluate_natural_light
from .feasibility import CostesPromotor, MargenPromotor, calcular_margen_promotor


def repercusion_zonas_comunes_pct(project: GeneratedProject) -> Optional[float]:
    superficie_total = sum(u.total_area_m2 for u in project.units)
    if not superficie_total:
        return None
    superficie_nucleo = sum(
        u.total_area_m2 for u in project.units
        if any(r.label == _NUCLEO_ROOM_NAME for r in u.rooms)
    )
    return superficie_nucleo / superficie_total * 100.0


def pct_fachada_aprovechada(project: GeneratedProject) -> Optional[float]:
    """% de piezas habitables (Salón/Cocina, Dormitorio 1-3) con fachada
    exterior detectada, sobre el total de piezas habitables del proyecto.
    Solo cuenta viviendas residenciales -- el núcleo/local comercial no
    tienen piezas que coincidan con los patrones de `evaluate_natural_
    light`, así que ya quedan fuera sin necesidad de filtrarlos aparte."""
    resultados = []
    for u in project.units:
        if not _es_unidad_residencial(u):
            continue
        resultados.extend(evaluate_natural_light(u))
    if not resultados:
        return None
    con_fachada = sum(1 for r in resultados if r.has_exterior_facade)
    return con_fachada / len(resultados) * 100.0


def margen_estimado_opcion(
    project: GeneratedProject, ratio_m2: Optional[float],
    coste_suelo: Optional[float], precio_venta: Optional[float],
) -> MargenPromotor:
    """PEM de esta opción = su propia superficie construida × el ratio que
    el usuario ya introdujo (mismo ratio para las 2 opciones -- lo que
    cambia es la superficie/mix, no la estimación de coste unitario)."""
    superficie_total = sum(u.total_area_m2 for u in project.units)
    pem = superficie_total * ratio_m2 if ratio_m2 is not None else None
    costes = CostesPromotor(pem=pem, coste_suelo=coste_suelo)
    return calcular_margen_promotor(costes, precio_venta)


@dataclass
class MetricasOpcion:
    etiqueta: str
    mix_viviendas: dict
    repercusion_zonas_comunes_pct: Optional[float]
    pct_fachada_aprovechada: Optional[float]
    margen_estimado: MargenPromotor


def calcular_metricas_opcion(
    etiqueta: str, project: GeneratedProject, mix_viviendas: dict,
    ratio_m2: Optional[float] = None, coste_suelo: Optional[float] = None,
    precio_venta: Optional[float] = None,
) -> MetricasOpcion:
    return MetricasOpcion(
        etiqueta=etiqueta,
        mix_viviendas=mix_viviendas,
        repercusion_zonas_comunes_pct=repercusion_zonas_comunes_pct(project),
        pct_fachada_aprovechada=pct_fachada_aprovechada(project),
        margen_estimado=margen_estimado_opcion(project, ratio_m2, coste_suelo, precio_venta),
    )
