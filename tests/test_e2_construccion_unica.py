# -*- coding: utf-8 -*-
"""E2 — el modelo se construye una sola vez por unidad, no dos (C-E2.3), y el
modelo del proyecto se construye una sola vez por análisis (C-E2.4).

Ejecutar:  python tests/test_e2_construccion_unica.py

**La metrica exacta, medida, no la que sugeria el borrador del PRD.** El PRD
decia "12 construcciones -> 1". Medido de verdad: `circulation.py` llama a
`evaluate_circulation()` DOS veces por vivienda (`api_serializer.py` y
`chain_effects.py`), y con las 6 viviendas de `ejemplo.dxf` eso son 12
llamadas. La memoizacion de `modelo/compat.py` (C-E2.3) colapsa las DOS
llamadas de cada vivienda en UNA construccion real -> 12 llamadas, 6
construcciones (una por vivienda, no una por analisis). Ademas, E2.4 anade
una construccion MAS, de un tipo distinto: el modelo del PROYECTO ENTERO,
una vez por analisis, en `app.py`, para poder persistirlo. Esa es la que de
verdad baja a "1" — pero es una construccion nueva que antes no existia, no
una que sustituya a las 6 de circulation (esas siguen siendo submodelos por
vivienda, y unificarlas queda fuera del cambio minimo que fija C-E2.3; ver
`docs/design/2026-08-11-e2-implementacion.md`, desviacion D-E2.1).

Dos bloques:

1. `grafo_de_adyacencia`: 12 llamadas a `evaluate_circulation` -> 6
   construcciones reales (una por vivienda), medido interceptando
   `modelo.compat.construir_de_unidad`.
2. `/api/analizar` de extremo a extremo: 1 llamada -> 1 construccion del
   modelo de proyecto, medido interceptando `app.modelo_constructor.construir`.
"""
import os
import sys
import tempfile
from io import BytesIO

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ["ARCHMUSE_DATA_DIR"] = tempfile.mkdtemp(prefix="archmuse_test_e2_construccion_")

from analyzer import circulation, evaluator, parser  # noqa: E402
from modelo import compat as modelo_compat  # noqa: E402

fallos = []
comprobaciones = 0


def check(nombre, cond, detalle=""):
    global comprobaciones
    comprobaciones += 1
    estado = "OK  " if cond else "FALLO"
    print("  [%s] %s%s" % (estado, nombre, ("  -> " + str(detalle)) if detalle else ""))
    if not cond:
        fallos.append(nombre)


DXF = os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf")
if not os.path.exists(DXF):
    print("[SALTA] no se encuentra %s" % DXF)
    print("Todas las comprobaciones OK (0)")
    sys.exit(0)

print("=" * 70)
print("1. UNA CONSTRUCCION POR VIVIENDA (no dos), a traves de circulation.py")
print("=" * 70)

plano = parser.leer_plano(parser.load_document(DXF))
unidades = evaluator.group_rooms_by_unit_label(plano.rooms, plano.unit_labels)
check("hay 6 viviendas en ejemplo.dxf", len(unidades) == 6, len(unidades))

# Cache limpia: ninguna de estas `Unit` se ha visto antes en este proceso.
modelo_compat._CACHE_ADYACENCIA.clear()
modelo_compat._CENTINELAS.clear()

llamadas = {"n": 0}
original = modelo_compat.construir_de_unidad


def _contador(*args, **kwargs):
    llamadas["n"] += 1
    return original(*args, **kwargs)


modelo_compat.construir_de_unidad = _contador
try:
    resultados = []
    for unidad in unidades:
        # Simula los dos sitios reales que llaman a evaluate_circulation:
        # api_serializer.py:330 y chain_effects.py:159 — mismo objeto Unit.
        us1 = evaluator.UnitScore(unit=unidad, total_checks=0, passed_checks=0, score_pct=100.0)
        r1 = circulation.evaluate_circulation(us1)
        r2 = circulation.evaluate_circulation(us1)
        resultados.append((r1, r2))
finally:
    modelo_compat.construir_de_unidad = original

check("12 llamadas a evaluate_circulation (2 x 6 viviendas)",
      sum(1 for _ in resultados for _ in _) == 12)
check("SOLO 6 construcciones reales del modelo (una por vivienda, no doce)",
      llamadas["n"] == 6, "construcciones=%d" % llamadas["n"])

iguales = all(
    [(rt.tipo, rt.passed, rt.message, tuple(rt.path_labels), rt.metric_value) for rt in r1.routes] ==
    [(rt.tipo, rt.passed, rt.message, tuple(rt.path_labels), rt.metric_value) for rt in r2.routes]
    for r1, r2 in resultados
)
check("la 2a llamada (cache) da EXACTAMENTE el mismo resultado que la 1a", iguales)

print()
print("2b. Aislamiento: una vivienda NUEVA (objeto Unit distinto) no reutiliza "
      "la cache de otra, aunque tenga el mismo contenido")
print("=" * 70)
otra_unidad = evaluator.Unit(name=unidades[0].name, rooms=list(unidades[0].rooms))
check("es un objeto Unit distinto al original", otra_unidad is not unidades[0])
llamadas["n"] = 0
modelo_compat.construir_de_unidad = _contador
try:
    circulation.evaluate_circulation(
        evaluator.UnitScore(unit=otra_unidad, total_checks=0, passed_checks=0, score_pct=100.0))
finally:
    modelo_compat.construir_de_unidad = original
check("construye de nuevo para el objeto nuevo (no hay colision de cache)",
      llamadas["n"] == 1)

print()
print("=" * 70)
print("2. UNA CONSTRUCCION DEL MODELO DE PROYECTO POR ANALISIS (E2.4, app.py)")
print("=" * 70)

from analyzer import storage  # noqa: E402

storage.init_db()
import app as app_module  # noqa: E402

cliente = app_module.app.test_client()
llamadas_proyecto = {"n": 0}
original_construir = app_module.modelo_constructor.construir


def _contador_proyecto(*args, **kwargs):
    llamadas_proyecto["n"] += 1
    return original_construir(*args, **kwargs)


app_module.modelo_constructor.construir = _contador_proyecto
try:
    with open(DXF, "rb") as fh:
        datos = {"dxf": (BytesIO(fh.read()), "ejemplo.dxf")}
    respuesta = cliente.post("/api/analizar", data=datos, content_type="multipart/form-data")
finally:
    app_module.modelo_constructor.construir = original_construir

check("POST /api/analizar responde 200", respuesta.status_code == 200, respuesta.status_code)
check("el modelo de proyecto se construye EXACTAMENTE una vez por analisis",
      llamadas_proyecto["n"] == 1, "construcciones=%d" % llamadas_proyecto["n"])

payload = respuesta.get_json()
pid = payload.get("proyecto_id")
check("el proyecto quedo guardado", pid is not None)
check("y con modelo (columna no nula) tras un analisis real",
      pid is not None and storage.obtener_modelo(pid) is not None)

print()
print("=" * 70)
if fallos:
    print("FALLOS (%d de %d): %s" % (len(fallos), comprobaciones, ", ".join(fallos)))
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
