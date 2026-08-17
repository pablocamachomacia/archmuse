# -*- coding: utf-8 -*-
"""Prueba de `analyzer/pliego_conector.py` — determinista, sin IA.

Ejecutar:  python tests/test_pliego_conector.py

Usa el JSON REAL del pliego de Berrocales (`tests/fixtures/pliegos/
berrocales_extraccion_real.json`), capturado el 2026-08-15 con una llamada
real a Claude sobre el PDF real del concurso EMVS de 83 viviendas en
Berrocales, Madrid — no un caso sintético. `pliego_a_params()` en sí es
100% determinista (aritmética sobre el JSON ya extraído), así que este test
no necesita `ARCHMUSE_TEST_IA` ni red.
"""
import json
import os
import sys
import tempfile
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

os.environ.pop("ANTHROPIC_API_KEY", None)  # este test no debe poder llamar a la IA aunque quisiera
os.environ.setdefault("ARCHMUSE_DATA_DIR", tempfile.mkdtemp(prefix="archmuse_test_pliego_conector_"))

from analyzer.pliego_conector import pliego_a_params  # noqa: E402
from analyzer import storage  # noqa: E402

import app as app_module  # noqa: E402

fallos = []


def check(nombre, cond, detalle=""):
    estado = "OK  " if cond else "FALLO"
    print("  [%s] %s%s" % (estado, nombre, ("  -> " + str(detalle)) if detalle else ""))
    if not cond:
        fallos.append(nombre)


with open(os.path.join(RAIZ, "tests", "fixtures", "pliegos", "berrocales_extraccion_real.json"), encoding="utf-8") as fh:
    pliego = json.load(fh)["hechos"]

print("1. pliego_a_params() sin superficie de solar (el pliego no la trae)")
body = pliego_a_params(pliego)
check("proyecto.ciudad = Madrid", body["proyecto"]["ciudad"] == "Madrid")
check("proyecto.tipologia = plurifamiliar", body["proyecto"]["tipologia"] == "plurifamiliar")
check("edificio.plantas = 6 (de altura_maxima_plantas)", body["edificio"]["plantas"] == 6)
check("normativa.plantas_maximas = 6", body["normativa"]["plantas_maximas"] == 6)
check(
    "normativa.edificabilidad_maxima SIN mapear (no hay superficie de solar -- nunca inyecta un ratio con las unidades equivocadas)",
    "edificabilidad_maxima" not in body["normativa"],
)
check("mix_viviendas.dorm_1 (20% de 83, redondeado)", body["mix_viviendas"]["dorm_1"] == 17, body["mix_viviendas"])
check("mix_viviendas.dorm_2 (60% de 83, redondeado)", body["mix_viviendas"]["dorm_2"] == 50, body["mix_viviendas"])
check("mix_viviendas.dorm_3 (20% de 83, redondeado)", body["mix_viviendas"]["dorm_3"] == 17, body["mix_viviendas"])
suma = body["mix_viviendas"]["dorm_1"] + body["mix_viviendas"]["dorm_2"] + body["mix_viviendas"]["dorm_3"]
print("  [NOTA] suma de dorm_1+2+3 = %d (pliego pide mínimo 83) -- redondeo por fila, no ajustado al total; "
      "conocido, no corregido en esta versión mínima" % suma)
check("mix_viviendas.superficie_minima_m2 = 45 (el mínimo de las 3 filas)", body["mix_viviendas"]["superficie_minima_m2"] == 45)

print("\n2. Restricciones de concurso (solo confianza Alta/Media)")
restricciones = body["restricciones_concurso"]
check("hay 9 restricciones (6 campos sueltos + 3 filas de mix)", len(restricciones) == 9, len(restricciones))
check("régimen de protección presente", any("VPPA" in r for r in restricciones))
check("PEM máximo presente", any("11513729.7" in r for r in restricciones))
check("ratio construido/útil presente", any("1.45" in r for r in restricciones))
check("accesibilidad presente", any("accesibles" in r for r in restricciones))

print("\n3. pliego_a_params() CON superficie de solar -- conversión de edificabilidad")
body_con_solar = pliego_a_params(pliego, superficie_solar_m2=4310.0)
esperado = round(6250.0 / 4310.0, 4)
check(
    "normativa.edificabilidad_maxima = ratio correcto (6250 m² / 4310 m² solar), no el absoluto 6250",
    body_con_solar["normativa"]["edificabilidad_maxima"] == esperado,
    body_con_solar["normativa"]["edificabilidad_maxima"],
)

print("\n4. El resultado, con una superficie de solar añadida, es un `params` VÁLIDO para el generador")
body_completo = dict(body_con_solar)
body_completo["solar"] = {"superficie_m2": 4310.0, "forma": "irregular"}
try:
    params = app_module._parse_generar_params(body_completo)
    check("_parse_generar_params() no lanza", True)
    check("params trae los 5 bloques esperados", set(params.keys()) >= {"solar", "edificio", "mix_viviendas", "normativa", "proyecto"})
    check("solar.superficie_m2 llega intacta", params["solar"]["superficie_m2"] == 4310.0)
    check("edificio.plantas = 6 sobrevive el paso por _parse_generar_params", params["edificio"]["plantas"] == 6)
    check(
        "restricciones_concurso NO es una clave reconocida por _parse_generar_params "
        "(se pierde en el paso -- el endpoint la reinyecta a mano, ver app.py)",
        "restricciones_concurso" not in params,
    )
except ValueError as exc:
    check("_parse_generar_params() no lanza", False, str(exc))

print("\n5. Sin superficie de solar en absoluto -> el generador la rechaza igual que siempre (sin caso nuevo)")
try:
    app_module._parse_generar_params(body)  # el body de la sección 1, sin "solar"
    check("_parse_generar_params() rechaza sin superficie de solar", False)
except ValueError as exc:
    check("_parse_generar_params() rechaza sin superficie de solar", "solar" in str(exc).lower(), str(exc))

print("\n6. Ruta HTTP `POST /api/generar-desde-pliego` (Claude mockeado, cero coste)")
storage.init_db()
meta_pliego = storage.guardar_pliego("berrocales.pdf", b"%PDF-fake", pliego, es_pliego=True)
cliente = app_module.app.test_client()

r_sin_id = cliente.post("/api/generar-desde-pliego", json={})
check("sin pliego_id -> 400", r_sin_id.status_code == 400, r_sin_id.get_json())

r_inexistente = cliente.post("/api/generar-desde-pliego", json={"pliego_id": "0" * 12})
check("pliego inexistente -> 404", r_inexistente.status_code == 404, r_inexistente.get_json())

r_sin_solar = cliente.post("/api/generar-desde-pliego", json={"pliego_id": meta_pliego["id"]})
check(
    "sin superficie de solar -> 400, mismo error que /api/generar",
    r_sin_solar.status_code == 400 and "solar" in r_sin_solar.get_json().get("error", "").lower(),
    r_sin_solar.get_json(),
)


def _generacion_falsa(params, model=None):
    """Sustituye a `ai_generator.generate_project` -- NUNCA llama a Claude.
    Un edificio de 1 vivienda con 1 habitación basta para que el resto del
    pipeline (evaluación, serialización, guardado) tenga algo real que
    procesar."""
    import shapely.geometry as sg

    from analyzer.ai_generator import GeneratedProject
    from analyzer.evaluator import Unit
    from analyzer.parser import Room

    poligono = sg.Polygon([(0, 0), (5, 0), (5, 5), (0, 5)])
    habitacion = Room(label="Salón/cocina", polygon=poligono, layer="x")
    vivienda = Unit(name="1ºA", rooms=[habitacion])
    return GeneratedProject(
        units=[vivienda], rooms=[habitacion],
        justificacion="Generación de prueba, sin llamar a la IA real.",
    )


with mock.patch("app.generate_project", side_effect=_generacion_falsa):
    r_superficie_suelta = cliente.post(
        "/api/generar-desde-pliego",
        json={"pliego_id": meta_pliego["id"], "superficie_solar_m2": 4310},
    )
    check(
        "con «superficie_solar_m2» suelto (nombre pedido en esta especificación) -> 200",
        r_superficie_suelta.status_code == 200,
        r_superficie_suelta.status_code if r_superficie_suelta.status_code != 200 else "",
    )

    r_ok = cliente.post(
        "/api/generar-desde-pliego",
        json={"pliego_id": meta_pliego["id"], "solar": {"superficie_m2": 4310, "forma": "irregular"}},
    )
    check("con «solar» anidado -> 200 también", r_ok.status_code == 200)
    datos_ok = r_ok.get_json()
    check("devuelve un proyecto_id", bool(datos_ok.get("proyecto_id")))
    check("edificio.plantas = 6 (del pliego) llega hasta el payload final", (datos_ok.get("edificio") or {}).get("plantas") == 6)

    pliego_tras_generar = storage.obtener_pliego(meta_pliego["id"])
    check(
        "vincular_pliego_proyecto() enlazó el pliego con el proyecto generado",
        pliego_tras_generar["proyecto_id"] == datos_ok.get("proyecto_id"),
        pliego_tras_generar["proyecto_id"],
    )

print("\n" + "=" * 55)
if fallos:
    print("FALLOS (%d): %s" % (len(fallos), ", ".join(fallos)))
    sys.exit(1)
print("Todas las comprobaciones OK")
