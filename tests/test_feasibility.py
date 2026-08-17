from analyzer.feasibility import (
    CostesPromotor,
    analisis_sensibilidad,
    calcular_cash_flow_estatico,
    calcular_inversion_total,
    calcular_margen_promotor,
    ratio_eficiencia_superficie,
)


def test_ratio_eficiencia_superficie_real():
    assert ratio_eficiencia_superficie(80.0, 100.0) == 0.8


def test_ratio_eficiencia_superficie_sin_datos():
    assert ratio_eficiencia_superficie(None, 100.0) is None
    assert ratio_eficiencia_superficie(80.0, None) is None
    assert ratio_eficiencia_superficie(80.0, 0.0) is None


def test_inversion_total_solo_pem_y_suelo():
    costes = CostesPromotor(pem=100_000, coste_suelo=50_000)
    assert calcular_inversion_total(costes) == 150_000


def test_inversion_total_con_porcentajes():
    costes = CostesPromotor(
        pem=100_000, coste_suelo=50_000,
        costes_indirectos_pct=5, licencias_pct=2, honorarios_pct=8, coste_financiero_pct=3,
    )
    # 150_000 base + 18% de 100_000 = 150_000 + 18_000
    assert calcular_inversion_total(costes) == 168_000


def test_inversion_total_sin_pem_no_evaluable():
    assert calcular_inversion_total(CostesPromotor(coste_suelo=50_000)) is None


def test_margen_promotor_completo():
    costes = CostesPromotor(pem=100_000, coste_suelo=50_000)
    margen = calcular_margen_promotor(costes, ingresos_venta=200_000)
    assert margen.inversion_total == 150_000
    assert margen.margen_eur == 50_000
    assert round(margen.margen_pct, 2) == round(50_000 / 150_000 * 100, 2)


def test_margen_promotor_sin_ingresos_no_evaluable():
    costes = CostesPromotor(pem=100_000, coste_suelo=50_000)
    margen = calcular_margen_promotor(costes, ingresos_venta=None)
    assert margen.margen_eur is None
    assert margen.margen_pct is None


def test_cash_flow_estatico_filas_reales():
    costes = CostesPromotor(pem=100_000, coste_suelo=50_000, honorarios_pct=10)
    filas = calcular_cash_flow_estatico(costes, ingresos_venta=200_000)
    conceptos = [f.concepto for f in filas]
    assert "PEM (coste de construcción)" in conceptos
    assert "Coste de suelo" in conceptos
    assert "Honorarios técnicos" in conceptos
    assert "Costes indirectos" not in conceptos  # no rellenado, no aparece
    assert "Ingresos por venta" in conceptos
    salida_pem = next(f for f in filas if f.concepto == "PEM (coste de construcción)")
    assert salida_pem.importe == -100_000


def test_cash_flow_estatico_vacio_sin_datos():
    assert calcular_cash_flow_estatico(CostesPromotor(), None) == []


def test_analisis_sensibilidad_tres_escenarios():
    costes = CostesPromotor(pem=100_000, coste_suelo=50_000)
    escenarios = analisis_sensibilidad(costes, ingresos_venta=200_000)
    assert [e.variacion_coste_pct for e in escenarios] == [-10.0, 0.0, 10.0]
    base = next(e for e in escenarios if e.variacion_coste_pct == 0.0).margen
    mas_caro = next(e for e in escenarios if e.variacion_coste_pct == 10.0).margen
    assert mas_caro.margen_eur < base.margen_eur


def test_analisis_sensibilidad_sin_pem_no_inventa_base():
    costes = CostesPromotor(coste_suelo=50_000)
    escenarios = analisis_sensibilidad(costes, ingresos_venta=200_000)
    assert all(e.margen.margen_eur is None for e in escenarios)
