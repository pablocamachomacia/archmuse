# -*- coding: utf-8 -*-
"""Prueba de `analyzer/pliego_verificador.py` — 100% determinista, sin IA.

Ejecutar:  python tests/test_pliego_verificador.py

Mismo runner que el resto de `tests/`: sale con código 1 si algo falla.
Proyecto y pliego son diccionarios sintéticos, con la misma forma que
producen `api_serializer.serialize_analysis`/`hechos.hecho_a_dict` — no hace
falta un DXF real ni una llamada a Claude para probar comparación pura.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer.pliego_verificador import verificar_cumplimiento  # noqa: E402

fallos = []


def check(nombre, cond, detalle=""):
    estado = "OK  " if cond else "FALLO"
    print("  [%s] %s%s" % (estado, nombre, ("  -> " + str(detalle)) if detalle else ""))
    if not cond:
        fallos.append(nombre)


def _hecho(valor, confianza="Alta"):
    return {"no_encontrado": False, "valor": valor, "confianza": confianza, "cita": "", "motivo": None}


def _no_encontrado():
    return {"no_encontrado": True, "valor": None, "motivo": "no citado"}


def _vivienda(n_dorm, superficie, envolvente=None, accesible=True):
    habitaciones = [{"nombre": "Salón/cocina", "area_m2": 20.0}]
    habitaciones += [{"nombre": "Dormitorio %d" % (i + 1), "area_m2": 10.0} for i in range(n_dorm)]
    return {
        "nombre": "V%d" % n_dorm,
        "superficie_total_m2": superficie,
        "envolvente_cerrada_m2": envolvente,
        "habitaciones": habitaciones,
        "accesibilidad": {"evaluable": True, "cumple": accesible},
    }


print("1. Todo cumple")
proyecto_ok = {
    "viviendas": [_vivienda(2, 65.0, envolvente=80.0) for _ in range(15)]
    + [_vivienda(3, 90.0, envolvente=110.0) for _ in range(10)],
    "urbanismo": {"superficie_solar_m2": 1000, "superficie_total_construida_m2": 2400, "edificabilidad_real": 2.4, "edificabilidad_maxima": 2.5},
}
pliego_ok = {
    "num_viviendas_minimo": _hecho(20),
    "edificabilidad_maxima_m2": _hecho(2500),
    "ratio_construido_util_max": _hecho(1.3),
    "porcentaje_accesibilidad": _hecho(90),
    "pem_maximo_euros": _hecho(3_000_000),
    "mix_tipologias": _hecho([
        {"tipo": "2 dormitorios", "porcentaje": 60, "sup_util_min": 60, "sup_util_max": 70},
        {"tipo": "3 dormitorios", "porcentaje": 40, "sup_util_min": 85, "sup_util_max": 95},
    ]),
}
v = verificar_cumplimiento(proyecto_ok, pliego_ok)
check("num_viviendas cumple", next(c for c in v.checks if c.parametro == "num_viviendas_minimo").cumple is True)
check("edificabilidad cumple (2400 <= 2500)", next(c for c in v.checks if c.parametro == "edificabilidad_maxima_m2").cumple is True)
check("ratio construido/util calculado y cumple", next(c for c in v.checks if c.parametro == "ratio_construido_util_max").cumple is True)
check("accesibilidad cumple (100% >= 90%)", next(c for c in v.checks if c.parametro == "porcentaje_accesibilidad").cumple is True)
check("pem SIEMPRE no_verificable", next(c for c in v.checks if c.parametro == "pem_maximo_euros").cumple is None)
check("mix 2 dorm cumple (60% exacto)", next(c for c in v.checks if c.parametro == "mix_tipologias:2 dormitorios").cumple is True)
check("mix 3 dorm cumple (40% exacto)", next(c for c in v.checks if c.parametro == "mix_tipologias:3 dormitorios").cumple is True)
check("superficie util 2 dorm cumple", next(c for c in v.checks if c.parametro == "superficie_util:2 dormitorios").cumple is True)
check("sin blockers", v.blockers == [])
check("score alto sin blockers", v.score_cumplimiento is not None and v.score_cumplimiento >= 80, v.score_cumplimiento)
print("  resumen:", v.resumen_ejecutivo)

print("\n2. Blocker real (num_viviendas por debajo del mínimo)")
proyecto_pocas = {"viviendas": [_vivienda(2, 65.0) for _ in range(5)], "urbanismo": None}
v2 = verificar_cumplimiento(proyecto_pocas, pliego_ok)
check("num_viviendas incumple", next(c for c in v2.checks if c.parametro == "num_viviendas_minimo").cumple is False)
check("es blocker (crítico)", any(c.parametro == "num_viviendas_minimo" for c in v2.blockers))
check("score capado a <=40 con blocker", v2.score_cumplimiento is not None and v2.score_cumplimiento <= 40, v2.score_cumplimiento)

print("\n3. Tolerancia ±5% en el mix — límite exacto")
proyecto_65pct = {
    "viviendas": [_vivienda(2, 65.0) for _ in range(13)] + [_vivienda(3, 90.0) for _ in range(7)],
    "urbanismo": None,
}
pliego_60 = {**pliego_ok, "mix_tipologias": _hecho([{"tipo": "2 dormitorios", "porcentaje": 60}])}
v3 = verificar_cumplimiento(proyecto_65pct, pliego_60)
check("13/20 = 65% está en el límite (60+5) -> cumple", next(c for c in v3.checks if c.parametro == "mix_tipologias:2 dormitorios").cumple is True)

proyecto_70pct = {
    "viviendas": [_vivienda(2, 65.0) for _ in range(14)] + [_vivienda(3, 90.0) for _ in range(6)],
    "urbanismo": None,
}
v3b = verificar_cumplimiento(proyecto_70pct, pliego_60)
check("14/20 = 70% claramente fuera del límite (60+5) -> no cumple",
      next(c for c in v3b.checks if c.parametro == "mix_tipologias:2 dormitorios").cumple is False)

print("\n4. Campos no citados por el pliego -> no_verificable, nunca inventado")
pliego_vacio = {n: _no_encontrado() for n in pliego_ok}
v4 = verificar_cumplimiento(proyecto_ok, pliego_vacio)
check("todos los checks base son no_verificable", all(
    c.cumple is None for c in v4.checks
    if c.parametro in ("num_viviendas_minimo", "edificabilidad_maxima_m2", "porcentaje_accesibilidad")
))
check("sin blockers ni warnings cuando nada es verificable", v4.blockers == [] and v4.warnings == [])
check("score None cuando nada es verificable", v4.score_cumplimiento is None)

print("\n5. Proyecto sin datos de solar (DXF analizado típico)")
v5 = verificar_cumplimiento({"viviendas": [_vivienda(2, 65.0)], "urbanismo": None}, pliego_ok)
check("edificabilidad no_verificable sin datos de solar", next(c for c in v5.checks if c.parametro == "edificabilidad_maxima_m2").cumple is None)

print("\n6. Ratio construido/útil sin envolvente (proyecto generado con IA)")
proyecto_generado = {"viviendas": [_vivienda(2, 65.0, envolvente=None)], "urbanismo": None}
v6 = verificar_cumplimiento(proyecto_generado, pliego_ok)
check("ratio no_verificable sin envolvente_cerrada_m2", next(c for c in v6.checks if c.parametro == "ratio_construido_util_max").cumple is None)

print("\n" + "=" * 55)
if fallos:
    print("FALLOS (%d): %s" % (len(fallos), ", ".join(fallos)))
    sys.exit(1)
print("Todas las comprobaciones OK")
