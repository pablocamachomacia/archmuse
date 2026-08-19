# -*- coding: utf-8 -*-
"""Prueba de `analyzer/sitio.py`.

Ejecutar:  python tests/test_sitio.py

El parseo de GML se prueba contra un fixture REAL (`tests/fixtures/
catastro_wfs_getparcel_1446401VK4714E.xml`, la respuesta real del WFS del
Catastro para la parcela del Palacio de Cibeles, capturada en la PoC del
2026-08-15) — determinista, sin red. El mapeo de tags de Overpass se prueba
con diccionarios sintéticos, misma forma que el JSON real ya validado en esa
PoC. Ninguna llamada real de red en la suite normal.

Un test de humo contra los servicios reales existe al final, gated tras
`ARCHMUSE_TEST_RED=1` (mismo patrón que `ARCHMUSE_TEST_IA` para Claude) —
consultar Catastro/Overpass en cada `python -m pytest` sería exactamente el
tipo de llamada "porque sí" que este proyecto ha evitado todo el día."""
import json
import os
import ssl
import sys
import tempfile
import urllib.error
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

os.environ.setdefault("ARCHMUSE_DATA_DIR", tempfile.mkdtemp(prefix="archmuse_test_sitio_"))

from analyzer import storage  # noqa: E402
from analyzer import sitio as sitio_mod  # noqa: E402
from analyzer.sitio import (  # noqa: E402
    ErrorDeSitio,
    _centroide,
    _mapear_colindantes,
    _mapear_equipamientos,
    _mapear_viales,
    _mapear_zonas_verdes,
    _parsear_poligono_gml,
    _post_overpass,
    _referencia_desde_coordenadas,
    GeocodificacionNoConfigurada,
    geocodificar_direccion,
    obtener_datos_parcela,
)

fallos = []


def check(nombre, cond, detalle=""):
    estado = "OK  " if cond else "FALLO"
    print("  [%s] %s%s" % (estado, nombre, ("  -> " + str(detalle)) if detalle else ""))
    if not cond:
        fallos.append(nombre)


print("1. Parseo GML real (Palacio de Cibeles, 1446401VK4714E)")
fixture = open(
    os.path.join(RAIZ, "tests", "fixtures", "catastro_wfs_getparcel_1446401VK4714E.xml"), "rb"
).read()
anillo, superficie = _parsear_poligono_gml(fixture)
check("superficie real (11829 m², dato oficial del Catastro)", superficie == 11829.0, superficie)
check("anillo con más de 3 puntos", len(anillo) > 3, len(anillo))
lat, lon = _centroide(anillo)
check("centroide cae en Madrid (lat ~40.4, lon ~-3.69)", 40.3 < lat < 40.5 and -3.8 < lon < -3.6, (lat, lon))
# Hallazgo 2 del módulo: comprobación explícita de que el orden quedó
# corregido a (lon, lat) -- un polígono en Madrid tiene lon negativa y lat
# positiva; si el swap no se hiciera, sería al revés.
check("coordenadas en (lon, lat), no (lat, lon)", anillo[0][0] < 0 and anillo[0][1] > 0, anillo[0])

print("\n2. GML sin posList -> ErrorDeSitio, no una excepción cruda")
try:
    _parsear_poligono_gml(b"<FeatureCollection xmlns:cp='http://inspire.ec.europa.eu/schemas/cp/4.0'/>")
    check("lanza ErrorDeSitio", False)
except ErrorDeSitio:
    check("lanza ErrorDeSitio", True)
except Exception as exc:  # noqa: BLE001
    check("lanza ErrorDeSitio", False, "lanzó %s en su lugar" % type(exc).__name__)

print("\n3. GML no parseable (XML roto) -> ErrorDeSitio")
try:
    _parsear_poligono_gml(b"esto no es xml")
    check("lanza ErrorDeSitio ante XML roto", False)
except ErrorDeSitio:
    check("lanza ErrorDeSitio ante XML roto", True)

print("\n4. Mapeo de colindantes (forma real de Overpass, validada en la PoC)")
elements_edificios = [
    {"tags": {"name": "Palacio de Cibeles", "building": "public", "building:levels": "6"},
     "center": {"lat": 40.4188, "lon": -3.6919}},
    {"tags": {"addr:street": "Calle de Alcalá", "addr:housenumber": "55", "building": "apartments"},
     "center": {"lat": 40.4199, "lon": -3.6917}},
    {"tags": {"building": "yes"}, "center": {"lat": 40.42, "lon": -3.69}},  # sin nombre, sin altura, sin dirección
]
colindantes = _mapear_colindantes(elements_edificios)
check("3 colindantes mapeados", len(colindantes) == 3)
check("altura_plantas del primero = 6", colindantes[0]["altura_plantas"] == 6)
check("nombre construido de calle+número cuando no hay «name»", colindantes[1]["nombre"] == "Calle de Alcalá 55")
check("sin ningún dato -> altura_plantas None, nunca inventada", colindantes[2]["altura_plantas"] is None)
check("sin ningún dato -> nombre None, nunca inventado", colindantes[2]["nombre"] is None)

print("\n5. Mapeo de viales")
viales = _mapear_viales([
    {"tags": {"name": "Calle de Alcalá", "highway": "primary", "width": "20 m"}},
    {"tags": {"highway": "footway"}},
])
check("ancho_m parseado de «20 m» -> 20.0", viales[0]["ancho_m"] == 20.0, viales[0]["ancho_m"])
check("sin nombre -> None, no inventado", viales[1]["nombre"] is None)

print("\n6. Mapeo de zonas verdes y equipamientos")
verdes = _mapear_zonas_verdes([{"tags": {"name": "Parque del Retiro"}}, {"tags": {}}])
check("con nombre real", verdes[0]["nombre"] == "Parque del Retiro")
check("sin nombre -> etiqueta explícita, no vacío silencioso", verdes[1]["nombre"] == "(sin nombre en OSM)")

equip = _mapear_equipamientos([{"tags": {"amenity": "school", "name": "Colegio X"}}])
check("categoría = amenity", equip[0]["categoria"] == "school")

print("\n7. obtener_datos_parcela nunca lanza, incluso sin ningún dato")
r = obtener_datos_parcela()
check("no lanza sin ningún parámetro", isinstance(r, dict))
check("errores explica la ausencia de coordenadas", len(r["errores"]) > 0, r["errores"])
check("colindantes/viales/etc. quedan vacíos, no None", r["colindantes"] == [] and r["viales"] == [])

r2 = obtener_datos_parcela(municipio="Madrid", direccion="Calle Falsa 123")
check(
    "municipio/dirección sin resolver -> error explícito, no un intento silencioso",
    any("no implementada" in e for e in r2["errores"]),
    r2["errores"],
)

print("\n8. Caché por parcela (`storage.sitios`)")
storage.init_db()
meta = storage.guardar_sitio("1446401VK4714E", {"ejemplo": True})
check("devuelve un id de 12 hex", len(meta["id"]) == 12 and all(c in "0123456789abcdef" for c in meta["id"]))
cacheado = storage.obtener_sitio_por_clave("1446401VK4714E")
check("se recupera de caché", cacheado is not None)
check("mismos datos", cacheado["datos"] == {"ejemplo": True})
otra_clave = storage.obtener_sitio_por_clave("no-existe")
check("clave inexistente -> None", otra_clave is None)
meta2 = storage.guardar_sitio("1446401VK4714E", {"ejemplo": 2})
check("re-guardar la misma clave actualiza (upsert), mismo id", meta2["id"] == meta["id"])
check(
    "los datos se actualizaron",
    storage.obtener_sitio_por_clave("1446401VK4714E")["datos"] == {"ejemplo": 2},
)

print("\n9. Fix urgente: error de certificado SSL se reporta con claridad")
error_cert = urllib.error.URLError(ssl.SSLCertVerificationError("certificate verify failed"))
check("URLError con SSLError anidado se detecta como error de certificado",
      sitio_mod._es_error_de_certificado(error_cert))
check("ssl.SSLError directo también se detecta",
      sitio_mod._es_error_de_certificado(ssl.SSLError("boom")))
check("un URLError normal (sin SSL) NO se confunde con error de certificado",
      not sitio_mod._es_error_de_certificado(urllib.error.URLError("connection refused")))
mensaje_cert = sitio_mod._mensaje_error_certificado("https://x", error_cert)
check("el mensaje explica que probablemente es el almacén de certificados, no Catastro caído",
      "almacén de certificados" in mensaje_cert)

with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError(ssl.SSLError("boom"))):
    try:
        sitio_mod._get("https://ovc.catastro.meh.es/algo")
        check("_get propaga el error de certificado como ErrorDeSitio", False)
    except ErrorDeSitio as exc:
        check("_get propaga el error de certificado como ErrorDeSitio", "almacén de certificados" in str(exc), str(exc))

# Este bloque comprobaba el backoff exponencial 2/4/8s contra un mismo host.
# Esa política se retiró a propósito el 2026-08-17 por ser el bug que hacía que
# una consulta de sitio tardase 126s en fallar (medido en vivo; ver el
# comentario junto a `_URLS_OVERPASS` en `analyzer/sitio.py`). La política de
# hoy es la contraria: un intento por espejo, timeout corto y una espera fija y
# breve entre espejos — un backoff largo no tiene sentido cuando el siguiente
# intento va a OTRO host, no a repetir contra el mismo servicio saturado.
#
# Se actualiza el test, no el código: aquí manda el código, porque el cambio
# fue deliberado y está justificado. Los valores se fijan literales (3 espejos,
# 1,5s) y no se leen de `analyzer.sitio`, para que este test siga detectando
# que alguien los toca en vez de seguirlos en silencio.
print("\n10. Overpass: un intento por espejo, con espera corta y fija entre ellos")
llamadas = []


def _urlopen_falla_dos_veces_y_luego_ok(peticion, timeout=None):
    llamadas.append(1)
    if len(llamadas) <= 2:
        raise urllib.error.URLError("temporal")
    resp = mock.Mock()
    resp.read.return_value = json.dumps({"elements": []}).encode()
    resp.__enter__ = lambda self: resp
    resp.__exit__ = lambda self, *a: None
    return resp


llamadas.clear()
with mock.patch("urllib.request.urlopen", side_effect=_urlopen_falla_dos_veces_y_luego_ok), \
     mock.patch("time.sleep") as sleep_mock:
    resultado = _post_overpass("[out:json];")
    check("recupera tras 2 fallos, sin lanzar", resultado == {"elements": []})
    check("hizo exactamente 3 intentos (2 fallos + 1 éxito)", len(llamadas) == 3, len(llamadas))
    check("esperó 1,5s entre espejo y espejo (espera fija, no escalonada)",
          [c.args[0] for c in sleep_mock.call_args_list] == [1.5, 1.5], sleep_mock.call_args_list)

llamadas.clear()
with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("siempre falla")), \
     mock.patch("time.sleep") as sleep_mock2:
    try:
        _post_overpass("[out:json];")
        check("los 3 intentos fallan -> lanza ErrorDeSitio", False)
    except ErrorDeSitio as exc:
        check("los 3 espejos fallan -> lanza ErrorDeSitio", "los 3 espejos fallaron" in str(exc), str(exc))
    check("con los 3 fallando, esperó 1,5s dos veces (no espera tras el último espejo)",
          [c.args[0] for c in sleep_mock2.call_args_list] == [1.5, 1.5])

print("\n11. _referencia_desde_coordenadas: coords -> RC real (fixtures capturados en vivo para esta tarea)")
# Cuerpos EXACTOS devueltos por Consulta_RCCOOR para coordenadas reales de
# Madrid, capturados en vivo al escribir esta función (Gran Vía 31 y una
# coordenada sin parcela catastrada) -- no inventados, ver docstring de
# `_referencia_desde_coordenadas`.
CUERPO_RCCOOR_EXITO = json.dumps({
    "Consulta_RCCOORResult": {
        "control": {"cucoor": 1},
        "coordenadas": {"coord": [{
            "pc": {"pc1": "0347501", "pc2": "VK4704G"},
            "geo": {"xcen": "-3.703790", "ycen": "40.420000", "srs": "EPSG:4326"},
            "ldt": "CL GRAN VIA 31 MADRID (MADRID)",
        }]},
    }
}).encode("utf-8")
CUERPO_RCCOOR_SIN_PARCELA = json.dumps({
    "Consulta_RCCOORResult": {
        "control": {"cuerr": 1},
        "lerr": [{"cod": "16", "des": "PARA ESAS COORDENADAS NO HAY REFERENCIA DISPONIBLE"}],
    }
}).encode("utf-8")

with mock.patch("analyzer.sitio._get", return_value=CUERPO_RCCOOR_EXITO) as get_mock:
    rc_info = _referencia_desde_coordenadas(40.420000, -3.703790)
    check("RC = pc1+pc2 (14 caracteres)", rc_info["referencia_catastral"] == "0347501VK4704G", rc_info)
    check("dirección (ldt) preservada literal", rc_info["direccion"] == "CL GRAN VIA 31 MADRID (MADRID)")
    url_llamada = get_mock.call_args[0][0]
    check("usa CoorX/CoorY/SRS (hallazgo 1 del módulo), no Coordenada_X/Coordenada_Y",
          "CoorX=" in url_llamada and "CoorY=" in url_llamada and "Coordenada_X" not in url_llamada, url_llamada)

with mock.patch("analyzer.sitio._get", return_value=CUERPO_RCCOOR_SIN_PARCELA):
    try:
        _referencia_desde_coordenadas(0.0, 0.0)
        check("sin parcela en esas coordenadas -> ErrorDeSitio", False)
    except ErrorDeSitio as exc:
        check("sin parcela en esas coordenadas -> ErrorDeSitio", "NO HAY REFERENCIA DISPONIBLE" in str(exc), str(exc))

with mock.patch("analyzer.sitio._get", return_value=b"esto no es json"):
    try:
        _referencia_desde_coordenadas(1.0, 1.0)
        check("JSON roto -> ErrorDeSitio, no una excepción cruda", False)
    except ErrorDeSitio:
        check("JSON roto -> ErrorDeSitio, no una excepción cruda", True)

print("\n12. obtener_datos_parcela(lat=, lon=) encadena RC->geometría real (fixture GML de la sección 1)")
fixture_gml = open(
    os.path.join(RAIZ, "tests", "fixtures", "catastro_wfs_getparcel_1446401VK4714E.xml"), "rb"
).read()

with mock.patch("analyzer.sitio._get", side_effect=[CUERPO_RCCOOR_EXITO, fixture_gml]), \
     mock.patch("analyzer.sitio._colindantes_overpass", return_value=[]), \
     mock.patch("analyzer.sitio._viales_overpass", return_value=[]), \
     mock.patch("analyzer.sitio._zonas_verdes_overpass", return_value=[]), \
     mock.patch("analyzer.sitio._equipamientos_overpass", return_value=[]):
    r12 = obtener_datos_parcela(lat=40.420000, lon=-3.703790)
check("resuelve la RC real a partir de las coordenadas", r12["referencia_catastral"] == "0347501VK4704G", r12)
check("dirección de Catastro expuesta en el resultado", r12["direccion_catastro"] == "CL GRAN VIA 31 MADRID (MADRID)")
check("encadena la geometría/superficie real (misma fixture que la sección 1: 11829 m²)",
      r12["geometria_parcela"] is not None and r12["geometria_parcela"]["superficie_m2"] == 11829.0)
check("sin errores en el camino feliz", r12["errores"] == [], r12["errores"])

print("\n13. obtener_datos_parcela(lat=, lon=): Catastro sin parcela en el punto -> sigue con Overpass, no bloquea")
with mock.patch("analyzer.sitio._get", return_value=CUERPO_RCCOOR_SIN_PARCELA), \
     mock.patch("analyzer.sitio._colindantes_overpass", return_value=[{"nombre": "x"}]) as colind_mock, \
     mock.patch("analyzer.sitio._viales_overpass", return_value=[]), \
     mock.patch("analyzer.sitio._zonas_verdes_overpass", return_value=[]), \
     mock.patch("analyzer.sitio._equipamientos_overpass", return_value=[]):
    r13 = obtener_datos_parcela(lat=0.0, lon=0.0)
check("referencia_catastral queda como llegó (None): nunca se inventa", r13["referencia_catastral"] is None, r13["referencia_catastral"])
check("el fallo de Catastro SÍ se explica en errores", any("referencia catastral por coordenadas" in e for e in r13["errores"]), r13["errores"])
check("Overpass se sigue consultando con las coordenadas crudas (nunca bloquea el resto del flujo)",
      r13["colindantes"] == [{"nombre": "x"}])
check("colindantes_overpass se llamó con las coordenadas originales (0.0, 0.0)", colind_mock.call_args[0][:2] == (0.0, 0.0))

print("\n14. geocodificar_direccion: texto -> coords, ahora contra Mapbox (tarea TL-8)")
# Nominatim salió del producto: la política de uso de su instancia pública prohíbe
# el uso comercial, así que seguir llamándola en cuanto ArchMuse cobre es un
# incumplimiento con bloqueo por IP y sin aviso. Se sustituye ANTES de cobrar.
#: El token real del entorno, si lo hay. Se guarda para devolverlo al terminar:
#: la sección de red real de más abajo lo necesita DE VERDAD, y dejarle puesto
#: el token de mentira haría que fallara con un 401 que no dice nada.
_MAPBOX_REAL = os.environ.get("MAPBOX_TOKEN")
os.environ["MAPBOX_TOKEN"] = "pk.token-de-prueba"

# Forma v6 de la API (la que se pide hoy): coordenadas dentro de `properties`.
CUERPO_MAPBOX_V6 = json.dumps({
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-3.7037596, 40.4200034]},
        "properties": {
            "full_address": "Gran Vía 31, 28013 Madrid, España",
            "coordinates": {"longitude": -3.7037596, "latitude": 40.4200034},
        },
    }],
}).encode("utf-8")

with mock.patch("analyzer.sitio._get", return_value=CUERPO_MAPBOX_V6) as get_mock:
    resultados = geocodificar_direccion("Gran Vía 31 Madrid")
check("1 resultado", len(resultados) == 1, resultados)
check("lat/lon parseados como float", isinstance(resultados[0]["lat"], float) and resultados[0]["lat"] == 40.4200034)
check("display_name preservado literal", "Gran Vía" in resultados[0]["display_name"])
check("la llamada va a Mapbox y NO a Nominatim",
      "api.mapbox.com" in get_mock.call_args[0][0] and "nominatim" not in get_mock.call_args[0][0])
check("el token viaja en la petición y la búsqueda se acota a España",
      "access_token=pk.token-de-prueba" in get_mock.call_args[0][0] and "country=es" in get_mock.call_args[0][0])
check(
    "cae en el mismo punto real que la RC de la sección 11/12 (0347501VK4704G, Gran Vía 31): "
    "las dos mitades del flujo (buscar dirección / clic en el mapa) encajan",
    abs(resultados[0]["lat"] - 40.420000) < 0.001 and abs(resultados[0]["lon"] - (-3.703790)) < 0.001,
)

# Forma v5 clásica (`center` + `place_name`): qué versión responde lo decide la
# clave del despliegue, y una diferencia de versión no puede dejar el buscador mudo.
CUERPO_MAPBOX_V5 = json.dumps({
    "features": [{"center": [-3.7037596, 40.4200034],
                  "place_name": "Gran Vía 31, Madrid, España"}],
}).encode("utf-8")
with mock.patch("analyzer.sitio._get", return_value=CUERPO_MAPBOX_V5):
    r14b = geocodificar_direccion("Gran Vía 31 Madrid")
check("también se entiende la forma v5 (center + place_name)",
      len(r14b) == 1 and r14b[0]["lat"] == 40.4200034 and "Gran Vía" in r14b[0]["display_name"])

CUERPO_SIN_COORDS = json.dumps({"features": [{"properties": {"full_address": "algo"}}]}).encode("utf-8")
with mock.patch("analyzer.sitio._get", return_value=CUERPO_SIN_COORDS):
    check("una entrada sin coordenadas se descarta, NUNCA se inventan",
          geocodificar_direccion("algo") == [])

check("texto vacío -> [] sin llamar a la red", geocodificar_direccion("") == [] and geocodificar_direccion("   ") == [])

with mock.patch("analyzer.sitio._get", return_value=b'{"features": []}'):
    check("sin resultados -> lista vacía, NO es un ErrorDeSitio", geocodificar_direccion("xyzzy-no-existe") == [])

with mock.patch("analyzer.sitio._get", return_value=b"no es json"):
    try:
        geocodificar_direccion("algo")
        check("JSON roto -> ErrorDeSitio", False)
    except ErrorDeSitio:
        check("JSON roto -> ErrorDeSitio", True)

with mock.patch("analyzer.sitio._get", return_value=b'{"no_es_geojson": true}'):
    try:
        geocodificar_direccion("algo")
        check("respuesta con forma inesperada -> ErrorDeSitio", False)
    except ErrorDeSitio:
        check("respuesta con forma inesperada -> ErrorDeSitio", True)

# Sin token: NO hay repliegue a Nominatim. Un repliegue "temporal" a un servicio
# que no se puede usar comercialmente es la clase de atajo que dura tres años.
_token_guardado = os.environ.pop("MAPBOX_TOKEN")
with mock.patch("analyzer.sitio._get", side_effect=AssertionError("no debería llamarse a la red")):
    try:
        geocodificar_direccion("Gran Vía 31 Madrid")
        check("sin MAPBOX_TOKEN -> GeocodificacionNoConfigurada, y NO se llama a nadie", False)
    except GeocodificacionNoConfigurada:
        check("sin MAPBOX_TOKEN -> GeocodificacionNoConfigurada, y NO se llama a nadie", True)
os.environ["MAPBOX_TOKEN"] = _token_guardado

print("\n15. /api/geocodificar (HTTP, app.py) -- proxy fino, mockeando la capa de red")
import app as app_module  # noqa: E402  (después de los tests de sitio.py a propósito, mismo criterio que test_intervencion_existente.py)
cliente_http = app_module.app.test_client()

with mock.patch("analyzer.sitio._get", return_value=CUERPO_MAPBOX_V6):
    r15 = cliente_http.get("/api/geocodificar?q=Gran+Via+31+Madrid")
check("200 OK", r15.status_code == 200, r15.get_json())
check("devuelve 'resultados' con la misma forma que la función", r15.get_json()["resultados"][0]["lat"] == 40.4200034)

r15b = cliente_http.get("/api/geocodificar")  # sin ?q=
check("sin 'q' -> 200 con resultados=[] (no un error, no bloquea el MapPicker en blanco)", r15b.status_code == 200 and r15b.get_json()["resultados"] == [])

with mock.patch("analyzer.sitio._get", side_effect=ErrorDeSitio("Mapbox: boom")):
    r15c = cliente_http.get("/api/geocodificar?q=algo")
check("fallo real del geocodificador -> 502 con mensaje explícito, no un 500 genérico", r15c.status_code == 502 and "boom" in r15c.get_json()["error"])

_token_guardado = os.environ.pop("MAPBOX_TOKEN")
r15d = cliente_http.get("/api/geocodificar?q=algo")
check("sin MAPBOX_TOKEN -> 501 (no configurado), NUNCA 502: reintentar no lo arreglaría",
      r15d.status_code == 501 and r15d.get_json()["configurado"] is False)
# Se devuelve el entorno a como estaba: con el token real si lo había, y sin
# ninguno si no. La sección de red real de más abajo depende de esto.
if _MAPBOX_REAL is None:
    os.environ.pop("MAPBOX_TOKEN", None)
else:
    os.environ["MAPBOX_TOKEN"] = _MAPBOX_REAL

print("\n" + "=" * 55)
if fallos:
    print("FALLOS (%d): %s" % (len(fallos), ", ".join(fallos)))
    sys.exit(1)
print("Todas las comprobaciones OK")

# --- Test de humo contra los servicios reales (gated) ----------------------

if os.environ.get("ARCHMUSE_TEST_RED") == "1":
    print("\n8. [RED REAL] obtener_datos_parcela con RC real")
    real = obtener_datos_parcela(referencia_catastral="1446401VK4714E")
    ok_geometria = real["geometria_parcela"] is not None
    print("  geometria_parcela obtenida:", ok_geometria)
    print("  errores:", real["errores"])
    print("  colindantes encontrados:", len(real["colindantes"]))
    if not ok_geometria:
        print("FALLO: no se obtuvo geometría real de Catastro")
        sys.exit(1)

    print("\n9. [RED REAL] obtener_datos_parcela con lat/lon reales (Gran Vía 31, Madrid)")
    real_coords = obtener_datos_parcela(lat=40.420000, lon=-3.703790)
    print("  referencia_catastral resuelta:", real_coords["referencia_catastral"])
    print("  direccion_catastro:", real_coords["direccion_catastro"])
    print("  geometria_parcela obtenida:", real_coords["geometria_parcela"] is not None)
    print("  errores:", real_coords["errores"])
    if not real_coords["referencia_catastral"] or real_coords["geometria_parcela"] is None:
        print("FALLO: no se resolvió una RC real ni su geometría a partir de coordenadas")
        sys.exit(1)

    if not os.environ.get("MAPBOX_TOKEN"):
        print("\n10. [SALTADO] geocodificar_direccion real: define MAPBOX_TOKEN.")
        print("    Es la verificación que le falta a la tarea TL-8: el parser está probado")
        print("    contra las dos formas documentadas de respuesta, pero nadie ha hecho")
        print("    todavía una llamada real a Mapbox desde que se retiró Nominatim.")
    else:
        print("\n10. [RED REAL] geocodificar_direccion con texto real (Mapbox)")
        real_geo = geocodificar_direccion("Gran Vía 31 Madrid")
        print("  resultados:", real_geo)
        if not real_geo:
            print("FALLO: el geocodificador (Mapbox) no devolvió ningún resultado real")
            sys.exit(1)

    print("Test de red real OK")
else:
    print("\n  [SALTADO] test de red real: define ARCHMUSE_TEST_RED=1 para ejecutarlo")
