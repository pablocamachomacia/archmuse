# -*- coding: utf-8 -*-
"""Prueba del enlace automático sitio→proyecto (Paso 3.2, punto 3):
"si existe un sitio analizado previamente... se invoque
vincular_sitio_proyecto() al generar el proyecto". Determinista, con
`generate_project` mockeado -- cero coste, cero red.

Ejecutar:  python tests/test_sitio_proyecto_link.py
"""
import os
import sys
import tempfile
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.setdefault("ARCHMUSE_DATA_DIR", tempfile.mkdtemp(prefix="archmuse_test_sitio_link_"))

from analyzer import storage  # noqa: E402
import app as app_module  # noqa: E402

fallos = []


def check(nombre, cond, detalle=""):
    estado = "OK  " if cond else "FALLO"
    print("  [%s] %s%s" % (estado, nombre, ("  -> " + str(detalle)) if detalle else ""))
    if not cond:
        fallos.append(nombre)


def _generacion_falsa(params, model=None):
    import shapely.geometry as sg

    from analyzer.ai_generator import GeneratedProject
    from analyzer.evaluator import Unit
    from analyzer.parser import Room

    poligono = sg.Polygon([(0, 0), (5, 0), (5, 5), (0, 5)])
    habitacion = Room(label="Salón/cocina", polygon=poligono, layer="x")
    vivienda = Unit(name="1ºA", rooms=[habitacion])
    return GeneratedProject(units=[vivienda], rooms=[habitacion], justificacion="Prueba mockeada.")


storage.init_db()
cliente = app_module.app.test_client()

print("1. /api/generar con «referencia_catastral» que coincide con un sitio ya en caché")
storage.guardar_sitio("1446401VK4714E", {"coordenadas": {"lat": 40.42, "lon": -3.69}})
with mock.patch("app.generate_project", side_effect=_generacion_falsa):
    r = cliente.post("/api/generar", json={
        "solar": {"superficie_m2": 500}, "mix_viviendas": {"dorm_1": 1},
        "referencia_catastral": "1446401VK4714E",
    })
check("200 OK", r.status_code == 200, r.status_code)
proyecto_id_1 = r.get_json()["proyecto_id"]
sitio_1 = storage.obtener_sitio_de_proyecto(proyecto_id_1)
check("el sitio quedó enlazado automáticamente al proyecto", sitio_1 is not None and sitio_1["clave_cache"] == "1446401VK4714E")

r_georef_1 = cliente.get("/api/proyectos/%s/georreferencia" % proyecto_id_1)
check("GET /georreferencia devuelve true automáticamente", r_georef_1.get_json()["georreferenciado"] is True)
check("con las coordenadas reales del sitio", r_georef_1.get_json()["lat"] == 40.42)

print("\n2. /api/generar SIN referencia_catastral -> sin enlace, sin error")
with mock.patch("app.generate_project", side_effect=_generacion_falsa):
    r2 = cliente.post("/api/generar", json={"solar": {"superficie_m2": 500}, "mix_viviendas": {"dorm_1": 1}})
check("200 OK igualmente", r2.status_code == 200)
check("sin sitio enlazado", storage.obtener_sitio_de_proyecto(r2.get_json()["proyecto_id"]) is None)

print("\n3. /api/generar con «referencia_catastral» que NO tiene sitio en caché -> sin enlace, sin error")
with mock.patch("app.generate_project", side_effect=_generacion_falsa):
    r3 = cliente.post("/api/generar", json={
        "solar": {"superficie_m2": 500}, "mix_viviendas": {"dorm_1": 1},
        "referencia_catastral": "NUNCA_ANALIZADA_123",
    })
check("200 OK, no bloquea la generación aunque el sitio no exista", r3.status_code == 200)
check("sin sitio enlazado (no existía)", storage.obtener_sitio_de_proyecto(r3.get_json()["proyecto_id"]) is None)

print("\n4. /api/generar con «sitio_lat»/«sitio_lon» (misma clave de caché que /api/analizar-sitio)")
storage.guardar_sitio("40.4200,-3.7000", {"coordenadas": {"lat": 40.42, "lon": -3.70}})
with mock.patch("app.generate_project", side_effect=_generacion_falsa):
    r4 = cliente.post("/api/generar", json={
        "solar": {"superficie_m2": 500}, "mix_viviendas": {"dorm_1": 1},
        "sitio_lat": 40.42, "sitio_lon": -3.70,
    })
check("200 OK", r4.status_code == 200)
check(
    "enlazado por lat/lon con el mismo formato de clave que /api/analizar-sitio",
    storage.obtener_sitio_de_proyecto(r4.get_json()["proyecto_id"]) is not None,
)

print("\n5. /api/generar-desde-pliego: la referencia catastral del PROPIO pliego enlaza sola, si es KNOWN")
storage.guardar_sitio("9999999XX9999X", {"coordenadas": {"lat": 41.0, "lon": -4.0}})
parametros_pliego = {
    "referencia_catastral": {"no_encontrado": False, "valor": "9999999XX9999X", "estado": "KNOWN"},
    "municipio": {"no_encontrado": True, "valor": None},
    "num_viviendas_minimo": {"no_encontrado": False, "valor": 10, "estado": "KNOWN"},
    "mix_tipologias": {
        "no_encontrado": False, "estado": "KNOWN", "confianza": "Alta",
        "valor": [{"tipo": "2 dormitorios", "porcentaje": 100, "sup_util_min": 50, "sup_util_max": 60}],
    },
}
meta_pliego = storage.guardar_pliego("test.pdf", b"%PDF-fake", parametros_pliego, es_pliego=True)
with mock.patch("app.generate_project", side_effect=_generacion_falsa):
    r5 = cliente.post("/api/generar-desde-pliego", json={
        "pliego_id": meta_pliego["id"], "superficie_solar_m2": 500,
    })
check("200 OK", r5.status_code == 200, r5.get_json() if r5.status_code != 200 else "")
check(
    "el sitio de la RC del pliego quedó enlazado sin que nadie lo pidiera explícitamente",
    storage.obtener_sitio_de_proyecto(r5.get_json()["proyecto_id"]) is not None,
)

print("\n6. /api/generar-desde-pliego: RC del pliego UNKNOWN (caso real de Berrocales) -> sin enlace, sin error")
parametros_pliego_sin_rc = {
    "referencia_catastral": {"no_encontrado": True, "valor": None},
    "num_viviendas_minimo": {"no_encontrado": False, "valor": 10, "estado": "KNOWN"},
    "mix_tipologias": {
        "no_encontrado": False, "estado": "KNOWN", "confianza": "Alta",
        "valor": [{"tipo": "2 dormitorios", "porcentaje": 100, "sup_util_min": 50, "sup_util_max": 60}],
    },
}
meta_pliego_2 = storage.guardar_pliego("berrocales.pdf", b"%PDF-fake", parametros_pliego_sin_rc, es_pliego=True)
with mock.patch("app.generate_project", side_effect=_generacion_falsa):
    r6 = cliente.post("/api/generar-desde-pliego", json={
        "pliego_id": meta_pliego_2["id"], "superficie_solar_m2": 500,
    })
check("200 OK, mismo caso que el pliego real de Berrocales de esta sesión", r6.status_code == 200)
check("sin sitio enlazado (el pliego no traía RC)", storage.obtener_sitio_de_proyecto(r6.get_json()["proyecto_id"]) is None)

print("\n" + "=" * 55)
if fallos:
    print("FALLOS (%d): %s" % (len(fallos), ", ".join(fallos)))
    sys.exit(1)
print("Todas las comprobaciones OK")
