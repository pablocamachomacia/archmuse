# -*- coding: utf-8 -*-
"""`/api/generar-opciones` -- docs/prd/2026-08-17-optimizacion-generativa-
multi-opcion.md (aprobado 2026-08-17: 2 opciones, mix derivado del mismo
`superficie_objetivo_m2`).

Ejecutar:  python tests/test_generar_opciones_endpoint.py

Mismo patrón que `tests/test_interview_api.py` §16: `app.test_client()` +
`unittest.mock.patch("app.generate_project")` -- nunca llama a Anthropic de
verdad."""
import os
import sys
import tempfile
from unittest.mock import patch

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

os.environ.pop("ANTHROPIC_API_KEY", None)
TMP = tempfile.mkdtemp(prefix="archmuse_test_generar_opciones_")
os.environ["ARCHMUSE_DATA_DIR"] = TMP

from analyzer import storage  # noqa: E402
storage.init_db()

from shapely.geometry import Polygon  # noqa: E402

import app as app_module  # noqa: E402
from analyzer.ai_generator import GeneratedProject, GenerationError  # noqa: E402
from analyzer.evaluator import Unit  # noqa: E402
from analyzer.parser import Room  # noqa: E402

fallos = []
comprobaciones = 0


def check(nombre, cond, detalle=""):
    global comprobaciones
    comprobaciones += 1
    estado = "OK  " if cond else "FALLO"
    print("  [%s] %s%s" % (estado, nombre, ("  -> " + str(detalle)) if detalle else ""))
    if not cond:
        fallos.append(nombre)


client = app_module.app.test_client()


def _rect(x0, y0, ancho, alto, etiqueta):
    return Room(label=etiqueta, layer="00 areas", polygon=Polygon(
        [(x0, y0), (x0 + ancho, y0), (x0 + ancho, y0 + alto), (x0, y0 + alto)]
    ))


def _proyecto_de(mix):
    """Un `GeneratedProject` sintético cuyo tamaño depende del mix recibido
    -- así se puede distinguir en las aserciones qué opción generó cada
    llamada, sin tener que inspeccionar el prompt."""
    n = mix.get("dorm_1", 0) + mix.get("dorm_2", 0) + mix.get("dorm_3", 0)
    unidades = [
        Unit(name="Planta 1 · %d" % i, rooms=[_rect(0, 0, 8, 5, "Salón/cocina"), _rect(8, 0, 4, 4, "Dormitorio 1")])
        for i in range(max(1, n))
    ]
    return GeneratedProject(
        units=unidades, rooms=[r for u in unidades for r in u.rooms],
        justificacion="Prueba sin IA.", advertencias=[],
    )


PAYLOAD_BASE = {
    "solar": {"superficie_m2": 800, "forma": "rectangular", "ancho_m": 20, "largo_m": 40, "norte_grados": 0},
    "edificio": {"plantas": 4, "altura_libre_m": 2.8, "planta_baja_comercial": False},
    "mix_viviendas": {"dorm_1": 0, "dorm_2": 4, "dorm_3": 0, "superficie_minima_m2": 40},
    "normativa": {"ocupacion_maxima_pct": 70, "retranqueos_m": 3},
    "proyecto": {"ciudad": "", "tipologia": "plurifamiliar"},
}


# =============================================================================
# 1. Sin superficie_objetivo_m2 -> 400 claro, no genera nada
# =============================================================================
r1 = client.post("/api/generar-opciones", json=PAYLOAD_BASE)
check("sin superficie_objetivo_m2 -> 400", r1.status_code == 400, r1.status_code)


# =============================================================================
# 2. Con superficie_objetivo_m2 -> 2 opciones, 1 llamada a generate_project
#    por opción (nunca 2), cada una devuelve proyecto_id + métricas
# =============================================================================
payload_2 = dict(PAYLOAD_BASE, superficie_objetivo_m2=1000)

llamadas = []


def _fake_generate_project(params, model=None):
    llamadas.append(dict(params["mix_viviendas"]))
    return _proyecto_de(params["mix_viviendas"])


with patch("app.generate_project", side_effect=_fake_generate_project):
    r2 = client.post("/api/generar-opciones", json=payload_2)

check("200 OK", r2.status_code == 200, r2.get_data(as_text=True)[:300])
opciones = r2.get_json().get("opciones", {})
check("hay exactamente 2 opciones (A y B)", set(opciones.keys()) == {"A", "B"}, list(opciones.keys()))
check("1 llamada a generate_project por opción (2 en total, no 4)", len(llamadas) == 2, len(llamadas))
check(
    "las 2 opciones tienen mix_viviendas distinto",
    opciones.get("A", {}).get("mix_viviendas") != opciones.get("B", {}).get("mix_viviendas"),
)
for etiqueta in ("A", "B"):
    op = opciones.get(etiqueta, {})
    check("%s tiene proyecto_id" % etiqueta, bool(op.get("proyecto_id")), op)
    check("%s tiene métricas" % etiqueta, "metricas" in op and "repercusion_zonas_comunes_pct" in op["metricas"])


# =============================================================================
# 3. Fallo parcial: A falla, B se devuelve igualmente
# =============================================================================
def _fake_generate_project_falla_a(params, model=None):
    mix = params["mix_viviendas"]
    # La opción "compacta" (más dorm_1 que dorm_3) es la A -- se hace fallar
    # a propósito para comprobar que B sobrevive.
    if mix["dorm_1"] >= mix["dorm_3"]:
        raise GenerationError("fallo simulado de Claude")
    return _proyecto_de(mix)


with patch("app.generate_project", side_effect=_fake_generate_project_falla_a):
    r3 = client.post("/api/generar-opciones", json=payload_2)

check("200 OK incluso con fallo parcial", r3.status_code == 200, r3.status_code)
opciones_3 = r3.get_json().get("opciones", {})
check("A tiene error, no proyecto_id", "error" in opciones_3.get("A", {}) and not opciones_3.get("A", {}).get("proyecto_id"))
check("B se generó igualmente (proyecto_id presente)", bool(opciones_3.get("B", {}).get("proyecto_id")), opciones_3.get("B"))


# =============================================================================
# 4. Con ratioM2/costeSuelo/precioVenta -> margen_estimado calculado
# =============================================================================
payload_4 = dict(payload_2, ratioM2=1000, costeSuelo=50000, precioVenta=1200000)
with patch("app.generate_project", side_effect=_fake_generate_project):
    r4 = client.post("/api/generar-opciones", json=payload_4)
margen_a = r4.get_json()["opciones"]["A"]["metricas"]["margen_estimado"]
check("margen_estimado.margen_eur calculado (no None) con ratio/coste/precio", margen_a["margen_eur"] is not None, margen_a)


print()
print("=" * 70)
if fallos:
    print("FALLARON %d de %d comprobaciones:" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  -", f)
    sys.exit(1)
else:
    print("Todas las comprobaciones OK (%d)" % comprobaciones)
