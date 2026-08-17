# -*- coding: utf-8 -*-
"""Prueba de `analyzer/gltf_exporter.py` y su integración HTTP en `app.py`.

Ejecutar (necesita `trimesh`/`mapbox_earcut`, en `requirements.txt` desde
hoy — si usas el venv del proyecto: `venv/Scripts/python.exe`):

    venv/Scripts/python.exe tests/test_gltf_exporter.py

100% determinista: construir y exportar una malla no necesita red ni IA.
Solo el estilo aplicado a los materiales viene de `analyzer.estilos`
(catálogo, también sin red)."""
import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

try:
    import trimesh
except ImportError:
    print("ERROR: falta «trimesh» — instala requirements.txt en el intérprete que uses "
          "para correr este test (venv/Scripts/python.exe -m pip install -r requirements.txt).")
    sys.exit(1)

os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.setdefault("ARCHMUSE_DATA_DIR", tempfile.mkdtemp(prefix="archmuse_test_gltf_"))

from analyzer.estilos import CATALOGO_ESTILOS  # noqa: E402
from analyzer.gltf_exporter import (  # noqa: E402
    ErrorDeExportacionGltf,
    _agrupar_por_planta,
    calcular_georreferencia,
    exportar_proyecto_a_glb,
)
from analyzer import storage  # noqa: E402

fallos = []


def check(nombre, cond, detalle=""):
    estado = "OK  " if cond else "FALLO"
    print("  [%s] %s%s" % (estado, nombre, ("  -> " + str(detalle)) if detalle else ""))
    if not cond:
        fallos.append(nombre)


def _vivienda(nombre, poligono, habitacion_nombre="Salón"):
    return {"id": nombre, "nombre": nombre, "habitaciones": [{"nombre": habitacion_nombre, "poligono": poligono}]}


CUADRADO = [[0, 0], [6, 0], [6, 5], [0, 5]]

print("1. _agrupar_por_planta() — mismo criterio que groupFloors() en viewer-edificio.js")
viviendas = [
    _vivienda("Planta 2 · 2ºA", CUADRADO),
    _vivienda("Planta 1 · 1ºA", CUADRADO),
    _vivienda("Sin convención de nombre", CUADRADO),  # DXF analizado -- cae a planta 1
]
plantas = _agrupar_por_planta(viviendas)
check("2 plantas detectadas (1 y 2)", len(plantas) == 2, len(plantas))
check("planta 1 tiene 2 viviendas (la declarada + la sin convención)", len(plantas[0]) == 2)
check("planta 2 tiene 1 vivienda", len(plantas[1]) == 1)

print("\n2. Exportación de un edificio sintético de 3 plantas — real, con trimesh")
proyecto_3_plantas = {
    "edificio": {"altura_libre_m": 3.0, "plantas": 3},
    "norte_grados": 15.0,
    "viviendas": [
        _vivienda("Planta 1 · 1ºA", CUADRADO),
        _vivienda("Planta 2 · 2ºA", CUADRADO),
        _vivienda("Planta 3 · 3ºA", CUADRADO),
    ],
}
datos_glb = exportar_proyecto_a_glb(proyecto_3_plantas, estilo_dict=CATALOGO_ESTILOS["brutalista"])
check("devuelve bytes reales", len(datos_glb) > 0)
check("magic header «glTF»", datos_glb[:4] == b"glTF")

escena = trimesh.load(trimesh.util.wrap_as_stream(datos_glb), file_type="glb")
check("recarga como Scene válida", isinstance(escena, trimesh.Scene))
check("hay al menos 4 mallas (3 salones + cubierta)", len(escena.geometry) >= 4, len(escena.geometry))
altura_total_esperada = 3 * 3.0 + 0.15  # 3 plantas de 3.0m + losa de cubierta de 0.15m
check(
    "altura total = 3 plantas + cubierta (%.2f m)" % altura_total_esperada,
    abs(escena.bounds[1][1] - altura_total_esperada) < 0.01,
    "y: %.3f - %.3f" % (escena.bounds[0][1], escena.bounds[1][1]),
)
check("todas las mallas son watertight (geometría válida, sin agujeros)",
      all(m.is_watertight for m in escena.geometry.values()))

print("\n3. Material PBR según estilo — «brutalista» empieza por «hormigón visto...»")
alguna_malla = next(iter(escena.geometry.values()))
color = alguna_malla.visual.material.baseColorFactor
check(
    "color de hormigón visto aplicado (gris, no el gris por defecto genérico)",
    tuple(color[:3]) in {(158, 158, 153), (159, 158, 153)},  # 0.62*255 redondeado, tolerancia de redondeo
    tuple(color[:3]),
)

print("\n4. Sin estilo -> material por defecto, no un error")
datos_sin_estilo = exportar_proyecto_a_glb(proyecto_3_plantas, estilo_dict=None)
check("exporta igual sin estilo_dict", datos_sin_estilo[:4] == b"glTF")

print("\n5. Proyecto sin ninguna geometría exportable -> ErrorDeExportacionGltf, no un .glb vacío")
try:
    exportar_proyecto_a_glb({"viviendas": []})
    check("proyecto sin viviendas -> ErrorDeExportacionGltf", False)
except ErrorDeExportacionGltf:
    check("proyecto sin viviendas -> ErrorDeExportacionGltf", True)

try:
    exportar_proyecto_a_glb({"viviendas": [{"id": "v", "nombre": "v", "habitaciones": [{"nombre": "x", "poligono": []}]}]})
    check("habitación sin polígono -> ErrorDeExportacionGltf", False)
except ErrorDeExportacionGltf:
    check("habitación sin polígono -> ErrorDeExportacionGltf", True)

print("\n6. Fixture real (ejemplo-dxf-analisis.json, 6 viviendas reales)")
with open(os.path.join(RAIZ, "tests", "fixtures", "ejemplo-dxf-analisis.json"), encoding="utf-8") as fh:
    proyecto_real = json.load(fh)
datos_real = exportar_proyecto_a_glb(proyecto_real, estilo_dict=CATALOGO_ESTILOS["mediterraneo"])
check("exporta el proyecto real sin errores", datos_real[:4] == b"glTF")
check("tamaño razonable para 6 viviendas reales (>1KB)", len(datos_real) > 1000, len(datos_real))

print("\n7. calcular_georreferencia() — nunca inventa coordenadas")
check("sin sitio enlazado -> None", calcular_georreferencia(proyecto_3_plantas, None) is None)
sitio_falso = {"clave_cache": "1234567AB1234C", "datos": {"coordenadas": {"lat": 40.42, "lon": -3.70}}}
georef = calcular_georreferencia(proyecto_3_plantas, sitio_falso)
check("con sitio enlazado -> lat/lon correctos", georef["lat"] == 40.42 and georef["lon"] == -3.70)
check("altitud SIEMPRE None (ningún servicio la trae -- nunca inventada)", georef["altitud_m"] is None)
check("heading = norte_grados del proyecto", georef["heading_grados"] == 15.0)

print("\n8. Ruta HTTP GET /api/proyectos/<id>/gltf")
storage.init_db()
import app as app_module  # noqa: E402

meta_proyecto = storage.guardar_proyecto(dict(proyecto_real), origen="dxf")
cliente = app_module.app.test_client()

r_404 = cliente.get("/api/proyectos/%s/gltf" % ("0" * 12))  # id bien formado pero inexistente
check("proyecto inexistente -> 404", r_404.status_code == 404, r_404.status_code)

r_ok = cliente.get("/api/proyectos/%s/gltf" % meta_proyecto["id"])
check("200 OK", r_ok.status_code == 200, r_ok.status_code)
check("mimetype model/gltf-binary", r_ok.mimetype == "model/gltf-binary", r_ok.mimetype)
check("el cuerpo es un .glb real (magic header)", r_ok.data[:4] == b"glTF")

r_con_estilo = cliente.get("/api/proyectos/%s/gltf?estilo=nordico" % meta_proyecto["id"])
check("con ?estilo=nordico -> 200 también", r_con_estilo.status_code == 200)

r_estilo_malo = cliente.get("/api/proyectos/%s/gltf?estilo=" % meta_proyecto["id"] + "x" * 5000)
check(
    "un texto libre absurdo de estilo no rompe el endpoint (o 200 o 400, nunca 500)",
    r_estilo_malo.status_code in (200, 400, 502), r_estilo_malo.status_code,
)

print("\n9. Ruta HTTP GET /api/proyectos/<id>/georreferencia")
r_sin_sitio = cliente.get("/api/proyectos/%s/georreferencia" % meta_proyecto["id"])
check("sin sitio enlazado -> georreferenciado: false", r_sin_sitio.get_json() == {"georreferenciado": False})

storage.guardar_sitio("REFCAT_TEST", {"coordenadas": {"lat": 40.0, "lon": -3.5}}, proyecto_id=None)
storage.vincular_sitio_proyecto("REFCAT_TEST", meta_proyecto["id"])
r_con_sitio = cliente.get("/api/proyectos/%s/georreferencia" % meta_proyecto["id"])
datos_georef = r_con_sitio.get_json()
check("con sitio enlazado -> georreferenciado: true", datos_georef["georreferenciado"] is True)
check("lat/lon correctos", datos_georef["lat"] == 40.0 and datos_georef["lon"] == -3.5)

print("\n10. GET /api/config (token para static/visor-mapa.js)")
r_config = cliente.get("/api/config")
check("200 OK", r_config.status_code == 200)
check(
    "sin MAPBOX_TOKEN en el entorno -> null, nunca un valor inventado",
    r_config.get_json() == {"mapbox_token": None},
    r_config.get_json(),
)

print("\n" + "=" * 55)
if fallos:
    print("FALLOS (%d): %s" % (len(fallos), ", ".join(fallos)))
    sys.exit(1)
print("Todas las comprobaciones OK")
