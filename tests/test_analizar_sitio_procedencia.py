# -*- coding: utf-8 -*-
"""`/api/analizar-sitio` -- procedencia estructurada y fecha (Fase A,
`docs/prd/2026-08-20-procedencia-y-fecha-de-datos-de-parcela.md`).

Ejecutar:  python tests/test_analizar_sitio_procedencia.py

Cubre exactamente el criterio de aceptación §8.3 del PRD: una segunda
consulta a la misma parcela, servida desde caché, muestra la fecha de la
consulta ORIGINAL (no la de hoy) y lo dice explícitamente (`de_cache: true`).
No había ningún test HTTP de este endpoint antes de esta tarea -- ni
siquiera de su comportamiento de caché en general, sin contar procedencia.

Determinista: `analyzer.sitio.obtener_datos_parcela` mockeado, cero red."""
import os
import sys
import tempfile
import time
from unittest import mock

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.setdefault("ARCHMUSE_DATA_DIR", tempfile.mkdtemp(prefix="archmuse_test_analizar_sitio_"))

import app as app_module  # noqa: E402

fallos = []


def check(nombre, cond, detalle=""):
    estado = "OK  " if cond else "FALLO"
    print("  [%s] %s%s" % (estado, nombre, ("  -> " + str(detalle)) if detalle else ""))
    if not cond:
        fallos.append(nombre)


app_module.app.config["TESTING"] = True
client = app_module.app.test_client()

# Referencia catastral propia de este test (no la usa ningún otro fichero) -- evita colisionar
# con la fila que otro test haya podido guardar en el mismo ARCHMUSE_DATA_DIR de esta sesión.
RC = "TESTPROCEDENCIA001"

_DATOS_FALSOS = {
    "referencia_catastral": RC,
    "direccion_catastro": "CL DE PRUEBA 1 MADRID (MADRID)",
    "coordenadas": {"lat": 40.42, "lon": -3.70},
    "geometria_parcela": {
        "tipo": "Polygon", "coordenadas": [[-3.701, 40.419], [-3.699, 40.419], [-3.699, 40.421]],
        "superficie_m2": 500.0, "centro": {"lat": 40.42, "lon": -3.70},
    },
    "procedencia": {
        "fuente": "Catastro (Sede Electrónica, WFS/INSPIRE — GetParcel por referencia catastral)",
        "consultado_en": "2026-08-20T10:00:00+00:00",
        "de_cache": False,
    },
    "colindantes": [], "viales": [], "zonas_verdes": [], "equipamientos": [],
    "errores": [], "entorno_consultado": False,
}

print("1. Primera consulta (sin caché): de_cache queda tal cual lo devuelve analyzer.sitio")
with mock.patch("app.obtener_datos_parcela", return_value=_DATOS_FALSOS) as mock_obtener:
    r1 = client.post("/api/analizar-sitio", json={"referencia_catastral": RC})
check("200 OK", r1.status_code == 200, r1.status_code)
body1 = r1.get_json()
check("cache: false en la primera consulta", body1["cache"] is False, body1)
proc1 = body1["sitio"]["datos"]["procedencia"]
check("procedencia viaja en la respuesta", proc1 is not None, body1)
check("fuente nombra el servicio real, no un texto genérico", "WFS/INSPIRE" in proc1["fuente"], proc1)
check("de_cache es False en la primera consulta", proc1["de_cache"] is False, proc1)
check("consultado_en es el que devolvió analyzer.sitio (no se reescribe en app.py)",
      proc1["consultado_en"] == "2026-08-20T10:00:00+00:00", proc1)
check("analyzer.sitio.obtener_datos_parcela se llamó una vez", mock_obtener.call_count == 1)

# Pausa real, aunque sea corta: si `de_cache`/`consultado_en` se recalcularan en cada respuesta
# (el bug que este test existe para impedir), un segundo real de diferencia ya lo delataría.
time.sleep(1.1)

print("\n2. Segunda consulta (misma RC): sirve de caché -- fecha ORIGINAL, de_cache=true")
with mock.patch("app.obtener_datos_parcela") as mock_obtener_2:
    r2 = client.post("/api/analizar-sitio", json={"referencia_catastral": RC})
check("200 OK", r2.status_code == 200, r2.status_code)
body2 = r2.get_json()
check("cache: true en la segunda consulta", body2["cache"] is True, body2)
check("analyzer.sitio.obtener_datos_parcela NO se vuelve a llamar (criterio de caché por parcela)",
      mock_obtener_2.call_count == 0)
proc2 = body2["sitio"]["datos"]["procedencia"]
check("procedencia sigue presente en la respuesta de caché", proc2 is not None, body2)
check("§8.3 del PRD: consultado_en es la fecha ORIGINAL, no la de esta segunda petición",
      proc2["consultado_en"] == proc1["consultado_en"] == "2026-08-20T10:00:00+00:00", (proc1, proc2))
check("§8.3 del PRD: de_cache pasa a True -- app.py lo marca porque analyzer.sitio no puede saberlo",
      proc2["de_cache"] is True, proc2)
# El resto del dato (superficie, RC, geometría) no cambia por el hecho de venir de caché.
check("el resto de datos_parcela no cambia entre la respuesta fresca y la de caché",
      {k: v for k, v in body1["sitio"]["datos"].items() if k != "procedencia"} ==
      {k: v for k, v in body2["sitio"]["datos"].items() if k != "procedencia"})

print("\n3. Fila de caché SIN procedencia (guardada antes de esta tarea): no se rellena a posteriori")
RC_VIEJA = "TESTPROCEDENCIA002_SINPROCEDENCIA"
from analyzer.storage import guardar_sitio  # noqa: E402

datos_sin_procedencia = dict(_DATOS_FALSOS)
datos_sin_procedencia["referencia_catastral"] = RC_VIEJA
datos_sin_procedencia.pop("procedencia")  # como quedaría una fila real anterior a esta tarea
guardar_sitio(RC_VIEJA, datos_sin_procedencia)

r3 = client.post("/api/analizar-sitio", json={"referencia_catastral": RC_VIEJA})
check("200 OK", r3.status_code == 200, r3.status_code)
body3 = r3.get_json()
check("cache: true", body3["cache"] is True, body3)
check("procedencia ausente se queda ausente -- nunca se inventa un dato que no se comprobó de verdad",
      body3["sitio"]["datos"].get("procedencia") is None, body3["sitio"]["datos"].get("procedencia"))
check("el endpoint no lanza al intentar marcar de_cache sobre una fila sin procedencia",
      r3.status_code == 200)

print("\n" + "=" * 60)
if fallos:
    print("FALLOS (%d): %s" % (len(fallos), ", ".join(fallos)))
    sys.exit(1)
print("Todas las comprobaciones OK")


if __name__ == "__main__":  # pragma: no cover
    pass
