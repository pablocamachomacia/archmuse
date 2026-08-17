"""Viabilidad financiera de un proyecto: Margen Promotor (%), Cash Flow
estático y Ratio de Eficiencia de Superficie.

`docs/prd/2026-08-17-analisis-de-viabilidad-financiera.md` (aprobado
2026-08-17, alcance recortado): extiende la pestaña de Viabilidad Económica
ya existente (`static/app.js`, PEM/repercusión de suelo/margen bruto) con un
bloque "Análisis Avanzado". Mismo criterio de honestidad que el resto del
proyecto: TODOS los valores de coste/precio/porcentaje son estimaciones que
introduce el propio usuario, nunca un dato de mercado que ArchMuse conozca
-- ninguna función de aquí tiene un valor por defecto no nulo.

**Por qué no hay TIR.** Decisión ya tomada en el PRD (§0/§14): una TIR
exige un calendario real de obra/ventas (en qué mes se paga cada cosa) que
ArchMuse no tiene en ningún punto del modelo -- inventar esa estructura
temporal para dar un número que *suena* a cálculo financiero riguroso sería
el mismo error que este proyecto ya se ha negado a cometer con los ratios
de coste. El "Cash Flow" de este módulo es ESTÁTICO: dos totales (inversión,
ingresos), sin fases en el tiempo.

Módulo puro, sin I/O -- lo consume tanto el endpoint HTTP
(`app.py::viabilidad_financiera`) como `analyzer/dossier_pdf.py`, para que
las dos superficies de la aplicación nunca puedan mostrar un número
distinto para el mismo proyecto (mismo riesgo de divergencia ya señalado
en `docs/prd/2026-08-17-checklist-cumplimiento-cte.md`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


def ratio_eficiencia_superficie(
    superficie_util_m2: Optional[float], superficie_construida_m2: Optional[float]
) -> Optional[float]:
    """Fracción (0-1) de superficie útil sobre construida. El único de los
    resultados de este módulo que NO es una estimación del usuario -- ambos
    datos ya existen y son reales (`api_serializer.py::superficie_util_m2`
    / `superficie_total_construida_m2`), así que se devuelve sin badge de
    estimación en el frontend.

    `None` si falta cualquiera de los dos datos o si la construida es 0 --
    nunca se fuerza un ratio con un denominador inválido."""
    if superficie_util_m2 is None or not superficie_construida_m2:
        return None
    return superficie_util_m2 / superficie_construida_m2


@dataclass
class CostesPromotor:
    """Desglose de costes de la promoción. Cada campo es `None` mientras el
    usuario no lo ha introducido -- nunca se asume un valor por defecto.

    `costes_indirectos_pct`/`licencias_pct`/`honorarios_pct`/
    `coste_financiero_pct` son porcentajes SOBRE EL PEM (convención habitual
    de promoción inmobiliaria: honorarios técnicos y licencias se calculan
    como % del presupuesto de ejecución material) -- introducidos por el
    usuario, igual que el resto de campos de Viabilidad Económica."""

    pem: Optional[float] = None
    coste_suelo: Optional[float] = None
    costes_indirectos_pct: Optional[float] = None
    licencias_pct: Optional[float] = None
    honorarios_pct: Optional[float] = None
    coste_financiero_pct: Optional[float] = None


def _pct_de_pem(pem: Optional[float], pct: Optional[float]) -> Optional[float]:
    if pem is None or pct is None:
        return None
    return pem * (pct / 100.0)


def calcular_inversion_total(costes: CostesPromotor) -> Optional[float]:
    """Suma PEM + coste de suelo + los 4 costes en % de PEM ya rellenados.
    `None` si falta el PEM o el coste de suelo -- son la base sobre la que
    se calculan los porcentajes y sin ellos no hay inversión que sumar. Los
    4 costes en % son opcionales: los que no se han rellenado se tratan
    como 0, no como "dato ausente que invalida todo el cálculo" -- el
    usuario puede querer ver un margen preliminar sin haber decidido aún
    su honorario técnico."""
    if costes.pem is None or costes.coste_suelo is None:
        return None
    total = costes.pem + costes.coste_suelo
    for pct in (
        costes.costes_indirectos_pct,
        costes.licencias_pct,
        costes.honorarios_pct,
        costes.coste_financiero_pct,
    ):
        extra = _pct_de_pem(costes.pem, pct)
        if extra is not None:
            total += extra
    return total


@dataclass
class MargenPromotor:
    inversion_total: Optional[float]
    ingresos_venta: Optional[float]
    margen_eur: Optional[float]
    margen_pct: Optional[float]  # margen / inversión total, en %


def calcular_margen_promotor(costes: CostesPromotor, ingresos_venta: Optional[float]) -> MargenPromotor:
    """Margen Promotor (%): margen sobre la inversión total, no sobre el
    precio de venta -- es la lectura habitual en promoción ("cuánto gano
    por cada euro que pongo"), distinta del margen bruto sobre ventas que
    ya muestra la pestaña de Viabilidad Económica base."""
    inversion_total = calcular_inversion_total(costes)
    if inversion_total is None or ingresos_venta is None:
        return MargenPromotor(inversion_total=inversion_total, ingresos_venta=ingresos_venta,
                               margen_eur=None, margen_pct=None)
    margen_eur = ingresos_venta - inversion_total
    margen_pct = (margen_eur / inversion_total * 100.0) if inversion_total else None
    return MargenPromotor(
        inversion_total=inversion_total, ingresos_venta=ingresos_venta,
        margen_eur=margen_eur, margen_pct=margen_pct,
    )


@dataclass
class FilaCashFlow:
    concepto: str
    importe: float  # negativo = salida de caja, positivo = entrada


def calcular_cash_flow_estatico(costes: CostesPromotor, ingresos_venta: Optional[float]) -> List[FilaCashFlow]:
    """Cash Flow SIN fases temporales (ver docstring del módulo): una fila
    de salida por cada coste ya rellenado y una fila de entrada por los
    ingresos de venta. Lista vacía si no hay ningún dato -- nunca una fila
    con importe 0 que aparente ser un cálculo real."""
    filas: List[FilaCashFlow] = []
    if costes.pem is not None:
        filas.append(FilaCashFlow("PEM (coste de construcción)", -costes.pem))
    if costes.coste_suelo is not None:
        filas.append(FilaCashFlow("Coste de suelo", -costes.coste_suelo))
    for etiqueta, pct in (
        ("Costes indirectos", costes.costes_indirectos_pct),
        ("Licencias", costes.licencias_pct),
        ("Honorarios técnicos", costes.honorarios_pct),
        ("Coste financiero", costes.coste_financiero_pct),
    ):
        importe = _pct_de_pem(costes.pem, pct)
        if importe is not None:
            filas.append(FilaCashFlow(etiqueta, -importe))
    if ingresos_venta is not None:
        filas.append(FilaCashFlow("Ingresos por venta", ingresos_venta))
    return filas


@dataclass
class EscenarioSensibilidad:
    variacion_coste_pct: float  # -10, 0, 10 ...
    margen: MargenPromotor


def analisis_sensibilidad(
    costes: CostesPromotor, ingresos_venta: Optional[float],
    variaciones_pct: tuple = (-10.0, 0.0, 10.0),
) -> List[EscenarioSensibilidad]:
    """Recalcula el Margen Promotor variando el PEM (coste de construcción)
    en cada porcentaje de `variaciones_pct` mientras el resto de costes se
    mantiene igual -- el escenario pedido en el PRD (±10% coste de
    construcción). Si `costes.pem` es `None`, cada escenario devuelve el
    mismo resultado vacío que `calcular_margen_promotor` (nunca se inventa
    un PEM base para poder variar algo)."""
    escenarios: List[EscenarioSensibilidad] = []
    for variacion in variaciones_pct:
        pem_variado = (
            costes.pem * (1.0 + variacion / 100.0) if costes.pem is not None else None
        )
        costes_variados = CostesPromotor(
            pem=pem_variado, coste_suelo=costes.coste_suelo,
            costes_indirectos_pct=costes.costes_indirectos_pct,
            licencias_pct=costes.licencias_pct, honorarios_pct=costes.honorarios_pct,
            coste_financiero_pct=costes.coste_financiero_pct,
        )
        escenarios.append(EscenarioSensibilidad(
            variacion_coste_pct=variacion,
            margen=calcular_margen_promotor(costes_variados, ingresos_venta),
        ))
    return escenarios
