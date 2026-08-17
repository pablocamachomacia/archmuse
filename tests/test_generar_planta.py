# -*- coding: utf-8 -*-
"""CAP-4, tarea 6: `planta` en `POST /api/generar`.

Ejecutar:  python tests/test_generar_planta.py

Rapido (<5 s): geometria sintetica, sin DXF. `generate_project` (la llamada
real a la IA) se sustituye por un doble de prueba determinista — nunca se
llama a la API de Anthropic desde este test, tenga o no tenga la maquina
`ANTHROPIC_API_KEY` configurada.

Que protege:

1. `_planta_desde_nombre_unidad` lee "Planta <n> - <nombre>" reutilizando
   `evaluator._PLANTA_NAME_PATTERN` (mismo objeto, no una copia), y produce
   SIEMPRE `ESTIMATED`, nunca `KNOWN` — es una convencion, no una
   declaracion.
2. "Planta baja - ..." (texto, sin digitos) NO casa el patron existente:
   UNKNOWN, no "planta 0". Se documenta la respuesta honesta a "si la
   convencion existente lo permite": no lo permite.
3. Nombre sin el prefijo -> UNKNOWN.
4. Ningun `VT<n>/<n>` se lee como planta, en el adaptador de /api/generar
   tampoco (mismo backstop que ya prueba tests/test_analizar_planta.py para
   /api/analizar).
5. `sobre_rasante` sigue la misma regla que `analyzer/planta.py`
   (numero > 0), aplicada de forma identica aqui.
6. `proyecto.planta` en el payload real de /api/generar tiene la MISMA forma
   que en /api/analizar (mismo serializador, `_serializar_planta_hechos`).
7. Regresion: /api/generar sigue devolviendo 200 con su forma habitual
   (edificio, advertencias, etc.) - CAP-4 no ha roto nada del flujo urbanistico.
"""
import os
import sys
import tempfile
from unittest.mock import patch

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

TMP = tempfile.mkdtemp(prefix="archmuse_test_")
os.environ["ARCHMUSE_DATA_DIR"] = TMP

from analyzer import storage  # noqa: E402

# `app.py` solo llama a `init_db()` una vez, como efecto lateral de
# importarlo (linea ~56) — y Python cachea el modulo, asi que si OTRO
# fichero de test ya importo `app` antes que este en el mismo proceso de
# pytest (p. ej. tests/test_analizar_planta.py, que tambien golpea
# /api/analizar), ese `init_db()` no se repite contra el `ARCHMUSE_DATA_DIR`
# de ESTE fichero, y `POST /api/generar` revienta con 500 al intentar
# guardar en una tabla que no existe. Se inicializa aqui explicitamente,
# igual que ya hace tests/test_storage.py, para no depender del orden de
# recoleccion de pytest.
storage.init_db()

from shapely.geometry import Polygon  # noqa: E402

import app as app_module  # noqa: E402
from analyzer.ai_generator import GeneratedProject  # noqa: E402
from analyzer.evaluator import Unit  # noqa: E402
from analyzer.hechos import ESTIMATED, KNOWN, UNKNOWN  # noqa: E402
from analyzer.parser import Room  # noqa: E402
from app import _planta_desde_nombre_unidad  # noqa: E402

fallos = []
comprobaciones = 0


def check(condicion, titulo, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s" % ("OK  " if condicion else "FALLO", titulo))
    if detalle:
        print("         %s" % detalle)
    if not condicion:
        fallos.append(titulo)


def rect(x0, y0, ancho, alto, etiqueta):
    return Room(label=etiqueta, layer="00 areas",
                polygon=Polygon([(x0, y0), (x0 + ancho, y0),
                                 (x0 + ancho, y0 + alto), (x0, y0 + alto)]))


print("A. _planta_desde_nombre_unidad -- funcion pura, sin Flask ni IA")

h1 = _planta_desde_nombre_unidad("Planta 3 · Vivienda X", "vivienda Planta 3 · Vivienda X")
check(h1.estado == ESTIMATED, "'Planta 3 · Vivienda X' -> ESTIMATED, nunca KNOWN", h1.estado)
check(h1.valor == 3, "numero de planta correcto (3)", h1.valor)
check(h1.confianza == "Media", "confianza Media (convencion, no declaracion)", h1.confianza)
check(h1.diagnostico.get("sobre_rasante") is True,
      "sobre_rasante=True para planta 3 (numero > 0, regla de planta.py)")
# Tarea 7: resto del contrato (origen, motivo, explicacion, ambito).
check(h1.diagnostico.get("origen") == "convencion_nombre",
      "origen='convencion_nombre' en el propio Hecho, no solo en el payload",
      h1.diagnostico.get("origen"))
check(h1.motivo_principal is None,
      "ESTIMATED no lleva motivo de ausencia (solo UNKNOWN)")
check(bool(h1.explicacion), "explicacion no viene vacia", h1.explicacion)
check(h1.ambito == "vivienda Planta 3 · Vivienda X",
      "ambito del hecho es el que se paso, sin transformar", h1.ambito)

h2 = _planta_desde_nombre_unidad("Planta 1 · Vivienda Y", "vivienda Planta 1 · Vivienda Y")
check(h2.estado == ESTIMATED and h2.valor == 1, "'Planta 1 · ...' -> ESTIMATED, numero=1")

print("\nB. 'Planta baja · ...' -- responde con honestidad si la convencion lo permite")

h_baja = _planta_desde_nombre_unidad("Planta baja · Vivienda Z", "vivienda Planta baja · Vivienda Z")
check(h_baja.estado == UNKNOWN,
      "'Planta baja · ...' NO casa _PLANTA_NAME_PATTERN (exige digitos): UNKNOWN, "
      "NO 'planta 0'. La convencion existente NO admite esta forma de texto",
      h_baja.estado)
check(h_baja.valor is None, "sin numero inventado", h_baja.valor)
check(h_baja.confianza is None, "UNKNOWN: sin confianza")
check(h_baja.diagnostico.get("origen") is None, "UNKNOWN: sin origen")
check(h_baja.motivo_principal is not None and bool(h_baja.motivo_principal.detalle),
      "UNKNOWN: lleva motivo con detalle, no viene vacio")
check(bool(h_baja.explicacion), "UNKNOWN: explicacion no viene vacia", h_baja.explicacion)

print("\nC. Nombre sin prefijo 'Planta <n> · ' -> UNKNOWN")

for nombre in ("Local comercial", "Vivienda suelta", "1ºA", ""):
    h = _planta_desde_nombre_unidad(nombre, "vivienda %s" % nombre)
    check(h.estado == UNKNOWN, "%r sin prefijo -> UNKNOWN" % nombre, h.estado)

print("\nD. Ningun VT<n>/<n> se interpreta como planta, tampoco aqui")

for nombre_vt in ("VT1/3", "VT2/2", "VT9/9", "vt1"):
    h = _planta_desde_nombre_unidad(nombre_vt, "vivienda %s" % nombre_vt)
    check(h.estado == UNKNOWN, "%r -> UNKNOWN, nunca una planta" % nombre_vt, h.estado)
    check(h.valor is None, "%r -> numero None, nunca 1/2/9" % nombre_vt)


print("\nE. Regresion e integracion HTTP de /api/generar, con generate_project simulado")

unidades_generadas = [
    Unit(name="Planta 1 · 1ºA", rooms=[rect(0, 0, 8, 5, "Salon")]),
    Unit(name="Planta 1 · 1ºB", rooms=[rect(10, 0, 8, 5, "Salon")]),
    Unit(name="Planta 3 · 3ºA", rooms=[rect(0, 20, 8, 5, "Salon")]),
    # Nombre defensivo (ai_generator no produce esta convencion en la
    # practica) para probar la prohibicion VT<n>/<n> tambien a traves del
    # endpoint HTTP real, no solo llamando a _planta_desde_nombre_unidad
    # directamente (bloque D, mas arriba).
    Unit(name="VT9/9", rooms=[rect(0, 40, 8, 5, "Salon")]),
]
todas_las_habitaciones = [r for u in unidades_generadas for r in u.rooms]

proyecto_simulado = GeneratedProject(
    units=unidades_generadas,
    rooms=todas_las_habitaciones,
    justificacion="Distribucion de prueba, generada sin llamar a la IA.",
    advertencias=[],
)

client = app_module.app.test_client()

with patch("app.generate_project", return_value=proyecto_simulado):
    resp = client.post("/api/generar", json={
        "solar": {"superficie_m2": 500, "forma": "rectangular",
                   "ancho_m": 20, "largo_m": 25, "norte_grados": 0},
        "edificio": {"plantas": 3, "altura_libre_m": 2.8,
                      "planta_baja_comercial": False},
        "mix_viviendas": {"dorm_1": 0, "dorm_2": 3, "dorm_3": 0,
                            "superficie_minima_m2": 40},
        "normativa": {"ocupacion_maxima_pct": 70, "retranqueos_m": 3},
        "proyecto": {"ciudad": "", "tipologia": "plurifamiliar"},
    })

check(resp.status_code == 200,
      "POST /api/generar (con generate_project simulado) -> 200",
      "obtenido %d: %s" % (resp.status_code, resp.get_data(as_text=True)[:300]))

if resp.status_code == 200:
    data = resp.get_json()
    check("edificio" in data, "regresion: el payload conserva 'edificio' (urbanismo)")
    check("advertencias" in data, "regresion: el payload conserva 'advertencias'")
    proy = data["proyecto"]
    check("planta" in proy, "proyecto.planta existe en /api/generar")
    # Tarea 13: C01 NO se cablea en /api/generar — ese flujo nunca calcula
    # superficie_util_db_si (CAP-1 no esta wireado ahi, solo CAP-4/planta lo
    # esta desde la tarea 6), asi que anadir C01 aqui exigiria una plomeria
    # nueva no pedida por ninguna tarea. No es simetria artificial evitada:
    # es que la necesidad real no existe todavia con lo que este endpoint
    # ya calcula.
    check("sectorizacion" not in proy,
          "proyecto.sectorizacion NO existe en /api/generar (sin necesidad "
          "real definida por el contrato todavia)", proy.keys())
    # Tarea 7: `planta_declarada` es exclusivo de /api/analizar (campo de
    # formulario que aqui no existe) - no debe aparecer, ni con valor null,
    # para no sugerir que /api/generar tiene una declaracion que no tiene.
    check("planta_declarada" not in proy,
          "proyecto.planta_declarada NO existe en /api/generar (no hay campo "
          "de formulario en este flujo; no se duplica ni se inventa)",
          proy.keys())

    por_ambito = {p["ambito"]: p for p in proy["planta"]}
    check(len(proy["planta"]) == 4, "un hecho planta por vivienda generada (4)",
          len(proy["planta"]))

    p_vt = por_ambito.get("vivienda VT9/9")
    check(p_vt is not None and p_vt["estado"] == "UNKNOWN" and p_vt["numero"] is None,
          "'VT9/9' a traves del endpoint HTTP real -> UNKNOWN, numero=None "
          "(prohibicion probada de extremo a extremo, no solo en la funcion)",
          p_vt)

    p_1a = por_ambito.get("vivienda Planta 1 · 1ºA")
    check(p_1a is not None and p_1a["estado"] == "ESTIMATED" and p_1a["numero"] == 1,
          "1ºA (Planta 1 · ...) -> planta 1, ESTIMATED", p_1a)
    check(p_1a is not None and p_1a["origen"] == "convencion_nombre",
          "origen trazable: 'convencion_nombre'", p_1a and p_1a.get("origen"))

    p_3a = por_ambito.get("vivienda Planta 3 · 3ºA")
    check(p_3a is not None and p_3a["numero"] == 3,
          "3ºA (Planta 3 · ...) -> planta 3", p_3a)

    # Misma forma exacta que /api/analizar (mismo serializador reutilizado,
    # no un contrato nuevo).
    campos_esperados = {"ambito", "numero", "sobre_rasante", "estado",
                          "confianza", "origen", "motivo", "explicacion"}
    check(set(proy["planta"][0].keys()) == campos_esperados,
          "proyecto.planta en /api/generar tiene los MISMOS campos que en "
          "/api/analizar (mismo _serializar_planta_hechos)",
          sorted(proy["planta"][0].keys()))
    check(all(p["estado"] != "KNOWN" for p in proy["planta"]),
          "ninguna planta de /api/generar es KNOWN (es siempre convencion, "
          "nunca declaracion)")

print("\n" + "=" * 60)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
