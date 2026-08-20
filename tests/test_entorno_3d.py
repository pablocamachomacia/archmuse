# -*- coding: utf-8 -*-
"""Contexto urbano real en el visor 3D (2026-08-16, a petición explícita):
- `analyzer/sitio.py`: `edificios_colindantes_geometria()` (huella real, no solo centroide) y
  `_estimar_altura_edificio()` (medida OSM / plantas×3.2m / 7m por defecto, en ese orden; 2026-08-17,
  antes 3.0m/9m).
- `app.py`: `GET /api/proyectos/<id>/entorno-3d` -- mismo criterio "no disponible, no error" que
  `/georreferencia`, con Overpass en modo best-effort (nunca hace fallar el endpoint).

Ejecutar:  python tests/test_entorno_3d.py

Mismo estilo que el resto de `tests/`: script sin pytest, `check()` acumula fallos, sale con código 1
si algo falla. La capa HTTP reutiliza el mismo patrón ya probado en `test_sitio_proyecto_link.py`
(`storage.guardar_sitio` + `/api/generar` con `referencia_catastral` -> enlace automático) -- nunca
llama a Overpass de verdad salvo que se indique `ARCHMUSE_TEST_RED=1`.
"""
import os
import sys
import tempfile
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.setdefault("ARCHMUSE_DATA_DIR", tempfile.mkdtemp(prefix="archmuse_test_entorno3d_"))

from analyzer import storage  # noqa: E402
from analyzer import sitio  # noqa: E402
import app as app_module  # noqa: E402

fallos = []
comprobaciones = 0


def check(nombre, cond, detalle=""):
    global comprobaciones
    comprobaciones += 1
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
client = app_module.app.test_client()

# =============================================================================
print("=" * 70)
print("1. _estimar_altura_edificio() -- medida OSM / plantas / por defecto, en ese orden")
print("=" * 70)

check("con 'height' en metros -> usa la medida directa", sitio._estimar_altura_edificio({"height": "12.5"}) == (12.5, "medida_osm"))
check("con 'building:height' si no hay 'height'", sitio._estimar_altura_edificio({"building:height": "8"}) == (8.0, "medida_osm"))
check("con 'building:levels' (sin medida) -> plantas × 3.2m (2026-08-17, antes 3.0m)",
      sitio._estimar_altura_edificio({"building:levels": "4"}) == (12.8, "estimada_por_plantas"))
check("'height' tiene prioridad sobre 'building:levels' si ambos están",
      sitio._estimar_altura_edificio({"height": "20", "building:levels": "4"}) == (20.0, "medida_osm"))
check("sin ningún dato -> 7m por defecto, nunca sin altura (2026-08-17, antes 9m)", sitio._estimar_altura_edificio({}) == (7.0, "estimada_por_defecto"))
check("'building:levels' no numérico -> cae al valor por defecto, no revienta",
      sitio._estimar_altura_edificio({"building:levels": "varios"}) == (7.0, "estimada_por_defecto"))


# =============================================================================
print()
print("=" * 70)
print("2. edificios_colindantes_geometria() -- geometría real, con datos de Overpass fabricados a mano")
print("=" * 70)

RESPUESTA_OVERPASS_FALSA = {
    "elements": [
        {
            "type": "way",
            "tags": {"building": "yes", "building:levels": "5"},
            # Anillo cerrado (el último nodo repite el primero, tal como lo manda Overpass de verdad).
            "geometry": [
                {"lat": 40.4200, "lon": -3.7000}, {"lat": 40.4201, "lon": -3.7000},
                {"lat": 40.4201, "lon": -3.6999}, {"lat": 40.4200, "lon": -3.6999},
                {"lat": 40.4200, "lon": -3.7000},
            ],
        },
        {
            "type": "way",
            "tags": {"building": "yes", "height": "15"},
            "geometry": [
                {"lat": 40.4210, "lon": -3.7010}, {"lat": 40.4211, "lon": -3.7010},
                {"lat": 40.4211, "lon": -3.7009},
            ],
        },
        # Elemento defectuoso (menos de 3 vértices tras quitar el cierre) -- se descarta, no revienta.
        {"type": "way", "tags": {"building": "yes"}, "geometry": [{"lat": 40.42, "lon": -3.70}]},
    ]
}

with mock.patch("analyzer.sitio._post_overpass", return_value=RESPUESTA_OVERPASS_FALSA) as m:
    edificios = sitio.edificios_colindantes_geometria(40.4205, -3.7005, radio_m=180)

check("devuelve 2 edificios (el defectuoso de menos de 3 vértices se descarta)", len(edificios) == 2, len(edificios))
check("el primero: anillo cerrado -> se quita el nodo de cierre duplicado (4 vértices, no 5)",
      len(edificios[0]["vertices"]) == 4, edificios[0]["vertices"])
check("el primero: altura estimada por plantas (5 × 3.2m)", edificios[0]["altura_m"] == 16.0 and edificios[0]["origen_altura"] == "estimada_por_plantas")
check("el segundo: altura medida real de OSM (15m), no estimada", edificios[1]["altura_m"] == 15.0 and edificios[1]["origen_altura"] == "medida_osm")
check("los vértices son [lat, lon] reales, no convertidos a metros aquí",
      edificios[0]["vertices"][0] == [40.4200, -3.7000])
check("la query a Overpass pide geometría completa ('out body geom;'), no solo el centroide",
      "out body geom;" in m.call_args[0][0])
check("la query usa el radio pedido (180m)", "around:180" in m.call_args[0][0])

# --- Fallo real de Overpass: se propaga como ErrorDeSitio, nunca se traga en silencio ------------------
with mock.patch("analyzer.sitio._post_overpass", side_effect=sitio.ErrorDeSitio("Overpass: caído")):
    try:
        sitio.edificios_colindantes_geometria(40.42, -3.70)
        check("un fallo real de Overpass se propaga como ErrorDeSitio", False)
    except sitio.ErrorDeSitio:
        check("un fallo real de Overpass se propaga como ErrorDeSitio", True)


# =============================================================================
print()
print("=" * 70)
print("3. GET /api/proyectos/<id>/entorno-3d -- capa HTTP")
print("=" * 70)

print("\n3.1 Proyecto SIN sitio enlazado -> disponible=False, nunca un error")
with mock.patch("app.generate_project", side_effect=_generacion_falsa):
    r_sin_sitio = client.post("/api/generar", json={"solar": {"superficie_m2": 500}, "mix_viviendas": {"dorm_1": 1}})
proyecto_sin_sitio = r_sin_sitio.get_json()["proyecto_id"]
r3_1 = client.get("/api/proyectos/%s/entorno-3d" % proyecto_sin_sitio)
check("200 OK (nunca un error por no tener sitio)", r3_1.status_code == 200, r3_1.status_code)
check("disponible: false", r3_1.get_json()["disponible"] is False)

print("\n3.2 Proyecto CON sitio enlazado, Overpass mockeado con éxito -> disponible=True + edificios reales")
storage.guardar_sitio("REF_ENTORNO3D_OK", {"coordenadas": {"lat": 40.4205, "lon": -3.7005}})
with mock.patch("app.generate_project", side_effect=_generacion_falsa):
    r_con_sitio = client.post("/api/generar", json={
        "solar": {"superficie_m2": 500}, "mix_viviendas": {"dorm_1": 1},
        "referencia_catastral": "REF_ENTORNO3D_OK",
    })
proyecto_con_sitio = r_con_sitio.get_json()["proyecto_id"]
check("el sitio quedó enlazado (mismo mecanismo ya probado en test_sitio_proyecto_link.py)",
      storage.obtener_sitio_de_proyecto(proyecto_con_sitio) is not None)

with mock.patch("app.edificios_colindantes_geometria", return_value=[
    {"vertices": [[40.4200, -3.7000], [40.4201, -3.7000], [40.4201, -3.6999]], "altura_m": 12.0, "origen_altura": "estimada_por_plantas"},
]) as m_edificios:
    r3_2 = client.get("/api/proyectos/%s/entorno-3d" % proyecto_con_sitio)
check("200 OK", r3_2.status_code == 200)
body3_2 = r3_2.get_json()
check("disponible: true", body3_2["disponible"] is True)
check("centro real de la parcela (el mismo lat/lon del sitio enlazado)",
      body3_2["centro"] == {"lat": 40.4205, "lon": -3.7005}, body3_2["centro"])
check("1 edificio colindante devuelto tal cual", len(body3_2["edificios_colindantes"]) == 1)
check("sin avisos cuando Overpass responde bien", body3_2["avisos"] == [])
check("radio_m presente y es el que usa el endpoint (180)", body3_2["radio_m"] == 180)
check("edificios_colindantes_geometria se llamó con el lat/lon real del sitio",
      m_edificios.call_args[0][:2] == (40.4205, -3.7005))

print("\n3.3 Proyecto CON sitio enlazado, pero Overpass falla -> sigue disponible=True, con aviso")
with mock.patch("app.edificios_colindantes_geometria", side_effect=sitio.ErrorDeSitio("Overpass caído (rate limit)")):
    r3_3 = client.get("/api/proyectos/%s/entorno-3d" % proyecto_con_sitio)
body3_3 = r3_3.get_json()
check("200 OK incluso si Overpass falla (best-effort, nunca hace fallar el endpoint entero)", r3_3.status_code == 200)
check("disponible sigue siendo true (el centro real de la parcela ya es útil por sí solo)", body3_3["disponible"] is True)
check("edificios_colindantes queda vacío, no inventado", body3_3["edificios_colindantes"] == [])
check("el aviso explica qué falló, no se traga en silencio", any("edificios colindantes" in a for a in body3_3["avisos"]), body3_3["avisos"])

print("\n3.4 Proyecto inexistente -> 404")
r3_4 = client.get("/api/proyectos/000000000000/entorno-3d")
check("404 para un proyecto que no existe", r3_4.status_code == 404, r3_4.status_code)


# =============================================================================
print()
print("=" * 70)
print("4. GET /api/entorno-3d-punto -- Modo Sandbox (2026-08-17): lat/lon directos, sin proyecto")
print("=" * 70)

# `geometria_parcela_por_coordenadas` no estaba mockeada aquí (hallazgo del PRD de procedencia de
# parcela, 2026-08-20-procedencia-y-fecha-de-datos-de-parcela.md, §auditoría de checklist_campo/
# viewer-sandbox): sin mock, esta llamada golpeaba Catastro de verdad -- justo la fuga de red que
# el propio docstring de este fichero dice evitar. `viewer-sandbox.js` lee `body.geometria_parcela`
# de esta misma respuesta y no tenía ningún test que lo protegiera.
_GEOMETRIA_PARCELA_MOCK = {
    "tipo": "Polygon", "coordenadas": [[-3.7006, 40.4204], [-3.7004, 40.4204], [-3.7004, 40.4206]],
    "superficie_m2": 350.0, "centro": {"lat": 40.4205, "lon": -3.7005},
}
with mock.patch("app.edificios_colindantes_geometria", return_value=[
    {"vertices": [[40.4200, -3.7000], [40.4201, -3.7000], [40.4201, -3.6999]], "altura_m": 9.0, "origen_altura": "estimada_por_defecto"},
]), mock.patch("app.geometria_parcela_por_coordenadas", return_value=_GEOMETRIA_PARCELA_MOCK):
    r4_1 = client.get("/api/entorno-3d-punto?lat=40.4205&lon=-3.7005")
check("200 OK", r4_1.status_code == 200, r4_1.status_code)
body4_1 = r4_1.get_json()
check("disponible: true (nunca hace falta ningún proyecto para esto)", body4_1["disponible"] is True)
check("centro = lat/lon pedidos, tal cual", body4_1["centro"] == {"lat": 40.4205, "lon": -3.7005})
check("heading_grados = 0.0 (sin ningún plano/proyecto todavía, no hay ningún norte del plano que aplicar)",
      body4_1["heading_grados"] == 0.0)
check("mismo radio que /georreferencia (180m)", body4_1["radio_m"] == 180)
check("1 edificio colindante devuelto", len(body4_1["edificios_colindantes"]) == 1)
check("geometria_parcela viaja en la respuesta -- lo que viewer-sandbox.js lee de verdad",
      body4_1.get("geometria_parcela") == _GEOMETRIA_PARCELA_MOCK, body4_1.get("geometria_parcela"))

print("\n4.1 Sin lat/lon -> 400, nunca un 500 ni datos inventados")
r4_2 = client.get("/api/entorno-3d-punto")
check("400 sin lat/lon", r4_2.status_code == 400, r4_2.status_code)
r4_3 = client.get("/api/entorno-3d-punto?lat=40.42")
check("400 con solo lat (falta lon)", r4_3.status_code == 400, r4_3.status_code)
r4_4 = client.get("/api/entorno-3d-punto?lat=no-es-un-numero&lon=-3.70")
check("400 con lat no numérico", r4_4.status_code == 400, r4_4.status_code)


# =============================================================================
print()
print("=" * 70)
if fallos:
    print("RESUMEN: %d comprobaciones, %d fallos" % (comprobaciones, len(fallos)))
    print("Fallaron:")
    for f in fallos:
        print("  - " + f)
    print("=" * 70)
    sys.exit(1)
else:
    print("RESUMEN: %d comprobaciones, 0 fallos" % comprobaciones)
    print("=" * 70)
    print("Todo OK.")
