# -*- coding: utf-8 -*-
"""CAP-5, tareas 5/6/7: `altura_evacuacion` y sus avisos en los dos endpoints.

Ejecutar:  python tests/test_endpoints_altura_evacuacion.py

`/api/analizar` usa `ejemplo.dxf` real (el unico plano disponible); si no
esta, ese bloque se salta con aviso, igual que `tests/test_analizar_planta.py`.
`/api/generar` usa un doble de prueba determinista: **nunca** se llama a la
API de Anthropic desde este fichero, tenga o no tenga la maquina
`ANTHROPIC_API_KEY` configurada.

Que protege:

1. **Regresion de `ejemplo.dxf`** (criterio de aceptacion 10): no declara
   ninguna altura -> `UNKNOWN` y CERO avisos. Es el caso por defecto de todo
   proyecto DXF, y CAP-5 no debe cambiarlo.
2. **`/api/analizar` no tiene ninguna via de hipotesis** (criterio 5): sin
   declaracion, `UNKNOWN` siempre, se pasen los parametros que se pasen.
3. Una declaracion directa SI funciona en el flujo DXF (P5.3) y dispara los
   avisos que corresponda.
4. `/api/generar` estima `(plantas - 1) x altura_libre_m` -> `ESTIMATED`,
   confianza Baja, y la declaracion directa prevalece sobre la hipotesis.
5. Los dos endpoints publican `proyecto.altura_evacuacion` con **la misma
   forma exacta** (un unico contrato, no dos parecidos), y como OBJETO, no
   como lista: el hecho es de ambito edificio.
6. `proyecto.avisos_evacuacion` nunca se cuela entre las incidencias: los
   avisos no aparecen en `issues` ni llevan `passed`/`severity`.
7. Regresion: ninguno de los dos endpoints ha perdido nada de lo que ya
   publicaba (CAP-1..CAP-4 intactos).
"""
import os
import sys
import tempfile
from io import BytesIO
from unittest.mock import patch

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

TMP = tempfile.mkdtemp(prefix="archmuse_test_")
os.environ["ARCHMUSE_DATA_DIR"] = TMP

from analyzer import storage  # noqa: E402

# Mismo motivo que en tests/test_generar_planta.py: `init_db()` solo corre al
# importar `app`, y si otro fichero ya lo importo en el mismo proceso de
# pytest, no se repite contra el ARCHMUSE_DATA_DIR de este.
storage.init_db()

from shapely.geometry import Polygon  # noqa: E402

import app as app_module  # noqa: E402
from analyzer.ai_analyst import AIAnalysis  # noqa: E402
from analyzer.ai_generator import GeneratedProject  # noqa: E402
from analyzer.evaluator import Unit  # noqa: E402
from analyzer.parser import Room  # noqa: E402

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


CAMPOS_ALTURA = {
    "ambito", "altura_m", "estado", "confianza", "origen", "formula",
    "plantas", "altura_libre_m", "hipotesis_descartada",
    "referencia_normativa", "motivo", "explicacion", "procedencia",
}
CAMPOS_AVISO = {
    "es_aviso", "codigo", "regla", "titulo", "localizador", "umbral_m",
    "altura_m", "altura_estimada", "mensaje",
}

client = app_module.app.test_client()

# ---------------------------------------------------------------------------
# /api/analizar
# ---------------------------------------------------------------------------

DXF = os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf")
FORMA_ANALIZAR = None

if not os.path.exists(DXF):
    print("[SALTA] no se encuentra %s -- no se prueba /api/analizar" % DXF)
else:
    with open(DXF, "rb") as fh:
        DXF_BYTES = fh.read()

    def analizar(**extra_form):
        data = {"dxf": (BytesIO(DXF_BYTES), "ejemplo.dxf")}
        data.update(extra_form)
        # La IA no aporta nada a CAP-5 y encarece/ralentiza el test.
        with patch("app.analyze_with_ai",
                   return_value=AIAnalysis(conclusion_ejecutiva="(test)")):
            resp = client.post("/api/analizar", data=data,
                               content_type="multipart/form-data")
        assert resp.status_code == 200, "esperaba 200, obtuvo %d: %s" % (
            resp.status_code, resp.get_data(as_text=True)[:500])
        return resp.get_json()

    print("A. REGRESION ejemplo.dxf -- UNKNOWN y cero avisos (criterio 10)")

    base = analizar()
    proy = base["proyecto"]
    check("altura_evacuacion" in proy, "proyecto.altura_evacuacion existe")
    alt = proy["altura_evacuacion"]
    FORMA_ANALIZAR = set(alt.keys())
    check(isinstance(alt, dict),
          "es un OBJETO, no una lista: el hecho es de ambito edificio, hay "
          "exactamente uno por analisis", type(alt).__name__)
    check(alt["estado"] == "UNKNOWN",
          "ejemplo.dxf no declara altura -> UNKNOWN", alt["estado"])
    check(alt["altura_m"] is None, "UNKNOWN no publica valor", alt["altura_m"])
    check(alt["confianza"] is None, "UNKNOWN sin confianza")
    check(alt["origen"] is None, "UNKNOWN sin origen")
    check(bool(alt["motivo"]), "UNKNOWN lleva motivo legible", alt["motivo"])
    check(alt["referencia_normativa"] == "es.cte.db_si.anejo_a.altura_de_evacuacion",
          "cita el concept_id del Anejo SI A", alt["referencia_normativa"])
    check(proy.get("avisos_evacuacion") == [],
          "CERO avisos sobre ejemplo.dxf: silencio explicito",
          proy.get("avisos_evacuacion"))
    check(proy.get("altura_evacuacion_declarada") is None,
          "altura_evacuacion_declarada = None cuando no se escribio nada")

    # Regresion de lo que ya existia (CAP-1..CAP-4 intactos).
    for clave in ("planta", "usos", "ocupacion", "sectorizacion", "tipologia"):
        check(clave in proy, "regresion: proyecto.%s sigue publicandose" % clave)

    print("\nB. /api/analizar NO tiene ninguna via de hipotesis (criterio 5)")

    # Se empujan a proposito los nombres de campo que SI producen hipotesis en
    # /api/generar: en este flujo no deben producir nada.
    sin_declarar = analizar(plantas="8", altura_libre_m="3.0",
                            planta="Planta 8")
    alt_sd = sin_declarar["proyecto"]["altura_evacuacion"]
    check(alt_sd["estado"] == "UNKNOWN",
          "ni 'plantas' ni 'altura_libre_m' en el formulario producen una "
          "hipotesis en el flujo DXF: UNKNOWN", alt_sd["estado"])
    check(sin_declarar["proyecto"]["avisos_evacuacion"] == [],
          "y por tanto tampoco avisos")

    print("\nC. Declaracion directa en el flujo DXF (P5.3)")

    declarado = analizar(altura_evacuacion_m="17,5")
    alt_d = declarado["proyecto"]["altura_evacuacion"]
    check(alt_d["estado"] == "KNOWN", "declarada -> KNOWN", alt_d["estado"])
    check(alt_d["altura_m"] == 17.5, "coma decimal interpretada (17,5 -> 17.5)",
          alt_d["altura_m"])
    check(alt_d["confianza"] == "Alta", "confianza Alta", alt_d["confianza"])
    check(alt_d["origen"] == "declarado", "origen trazable", alt_d["origen"])
    check(declarado["proyecto"]["altura_evacuacion_declarada"] == "17,5",
          "se guarda el texto tal cual lo escribio el arquitecto")

    avisos_d = declarado["proyecto"]["avisos_evacuacion"]
    reglas = sorted(a["regla"] for a in avisos_d)
    check(reglas == ["C11", "C18"],
          "17,5 m dispara C11 (14 m) y C18 (9 m), no C15 (28 m)", reglas)
    check(all(a["altura_estimada"] is False for a in avisos_d),
          "avisos sobre una altura declarada: altura_estimada=False")
    check(all(set(a.keys()) == CAMPOS_AVISO for a in avisos_d),
          "forma del aviso en el payload",
          sorted(avisos_d[0].keys()) if avisos_d else None)
    check(all(a["es_aviso"] is True for a in avisos_d),
          "es_aviso=True: ningun consumidor debe pintarlos como IssueReport")
    check(all("passed" not in a and "severity" not in a for a in avisos_d),
          "ningun aviso lleva passed ni severity en el payload")

    # Los avisos NO se cuelan entre las incidencias de cumplimiento.
    codigos_issues = {i.get("codigo") for i in (declarado.get("issues") or [])}
    codigos_aviso = {a["codigo"] for a in avisos_d}
    check(not (codigos_issues & codigos_aviso),
          "ningun codigo de aviso aparece en `issues`: no entran en "
          "classify_problems", codigos_issues & codigos_aviso)

    print("\nD. Declaracion no interpretable -> UNKNOWN con su propio motivo")

    malo = analizar(altura_evacuacion_m="alta")
    alt_m = malo["proyecto"]["altura_evacuacion"]
    check(alt_m["estado"] == "UNKNOWN",
          "texto no numerico -> UNKNOWN, nunca un KNOWN forzado", alt_m["estado"])
    check("alta" in (alt_m["motivo"] or ""),
          "el motivo cita el texto que no se pudo interpretar", alt_m["motivo"])
    check(malo["proyecto"]["avisos_evacuacion"] == [], "y cero avisos")

    for valor in ("0", "-3", "  "):
        r = analizar(altura_evacuacion_m=valor)
        a = r["proyecto"]["altura_evacuacion"]
        check(a["estado"] == "UNKNOWN",
              "%r no es una altura admisible -> UNKNOWN" % valor, a["estado"])

# ---------------------------------------------------------------------------
# /api/generar
# ---------------------------------------------------------------------------

print("\nE. /api/generar -- hipotesis (plantas - 1) x altura_libre_m")


def rect(x0, y0, ancho, alto, etiqueta):
    return Room(label=etiqueta, layer="00 areas",
                polygon=Polygon([(x0, y0), (x0 + ancho, y0),
                                 (x0 + ancho, y0 + alto), (x0, y0 + alto)]))


unidades = [
    Unit(name="Planta 1 · 1ºA", rooms=[rect(0, 0, 8, 5, "Salon")]),
    Unit(name="Planta 2 · 2ºA", rooms=[rect(0, 20, 8, 5, "Salon")]),
]
proyecto_simulado = GeneratedProject(
    units=unidades,
    rooms=[r for u in unidades for r in u.rooms],
    justificacion="Distribucion de prueba, generada sin llamar a la IA.",
    advertencias=[],
)


def generar(edificio_extra=None):
    edificio = {"plantas": 6, "altura_libre_m": 2.8, "planta_baja_comercial": False}
    edificio.update(edificio_extra or {})
    with patch("app.generate_project", return_value=proyecto_simulado):
        resp = client.post("/api/generar", json={
            "solar": {"superficie_m2": 500, "forma": "rectangular",
                      "ancho_m": 20, "largo_m": 25, "norte_grados": 0},
            "edificio": edificio,
            "mix_viviendas": {"dorm_1": 0, "dorm_2": 2, "dorm_3": 0,
                              "superficie_minima_m2": 40},
            "normativa": {"ocupacion_maxima_pct": 70, "retranqueos_m": 3},
            "proyecto": {"ciudad": "", "tipologia": "plurifamiliar"},
        })
    assert resp.status_code == 200, "esperaba 200, obtuvo %d: %s" % (
        resp.status_code, resp.get_data(as_text=True)[:500])
    return resp.get_json()


g = generar()
gp = g["proyecto"]
alt_g = gp["altura_evacuacion"]
check(alt_g["estado"] == "ESTIMATED",
      "6 plantas sin declarar -> ESTIMATED, nunca KNOWN", alt_g["estado"])
check(alt_g["altura_m"] == 14.0,
      "(6 - 1) x 2,80 = 14,00 m -- `plantas` INCLUYE la planta baja (P5.1: "
      "ai_generator numera desde 'planta': 1 y floor_areas.get(1) es la baja)",
      alt_g["altura_m"])
check(alt_g["confianza"] == "Baja",
      "confianza BAJA, no Media: la formula siempre se desvia", alt_g["confianza"])
check(alt_g["origen"] == "hipotesis_plantas_altura_libre", "origen trazable",
      alt_g["origen"])
check(alt_g["formula"] == "(plantas - 1) x altura_libre_m",
      "la formula viaja en el payload, revisable por el arquitecto",
      alt_g["formula"])
check(alt_g["plantas"] == 6 and alt_g["altura_libre_m"] == 2.8,
      "los dos factores brutos viajan con el hecho")
check(any(p.startswith("HIPOTESIS:") for p in alt_g["procedencia"]),
      "procedencia con prefijo 'HIPOTESIS:'", alt_g["procedencia"])

avisos_g = gp["avisos_evacuacion"]
check(sorted(a["regla"] for a in avisos_g) == ["C11", "C18"],
      "14,00 m dispara C11 y C18", sorted(a["regla"] for a in avisos_g))
check(all(a["altura_estimada"] is True for a in avisos_g),
      "los avisos marcan que la altura es estimada")
check(all("ESTIMACION" in a["mensaje"].upper() for a in avisos_g),
      "y lo dicen en el MENSAJE, no solo en un booleano del JSON")

print("\nF. /api/generar -- edificio bajo, y declaracion que prevalece")

g_bajo = generar({"plantas": 3})
alt_b = g_bajo["proyecto"]["altura_evacuacion"]
check(abs(alt_b["altura_m"] - 5.6) < 1e-9,
      "CU4: 3 plantas -> 5,60 m", alt_b["altura_m"])
check(g_bajo["proyecto"]["avisos_evacuacion"] == [],
      "CU4: por debajo de los tres umbrales -> cero avisos")

g_una = generar({"plantas": 1})
check(g_una["proyecto"]["altura_evacuacion"]["altura_m"] == 0.0,
      "1 planta -> 0,00 m ESTIMATED (correcto, no una ausencia)",
      g_una["proyecto"]["altura_evacuacion"]["altura_m"])
check(g_una["proyecto"]["avisos_evacuacion"] == [], "y cero avisos")

g_dec = generar({"altura_evacuacion_m": 31.0})
alt_gd = g_dec["proyecto"]["altura_evacuacion"]
check(alt_gd["estado"] == "KNOWN",
      "CU7: la declaracion prevalece sobre la hipotesis", alt_gd["estado"])
check(alt_gd["altura_m"] == 31.0, "gana el valor declarado, no los 14,00 m",
      alt_gd["altura_m"])
check(alt_gd["hipotesis_descartada"] is not None
      and alt_gd["hipotesis_descartada"]["valor_m"] == 14.0,
      "la hipotesis descartada queda registrada, auditable",
      alt_gd["hipotesis_descartada"])
check(sorted(a["regla"] for a in g_dec["proyecto"]["avisos_evacuacion"])
      == ["C11", "C15", "C18"],
      "31 m dispara los tres avisos a la vez")

g_malo = generar({"altura_evacuacion_m": "no se"})
check(g_malo["proyecto"]["altura_evacuacion"]["estado"] == "ESTIMATED",
      "declaracion no interpretable en JSON -> se ignora y queda la hipotesis, "
      "nunca un KNOWN forzado",
      g_malo["proyecto"]["altura_evacuacion"]["estado"])

print("\nG. Un unico contrato: misma forma en los dos endpoints")

check(set(alt_g.keys()) == CAMPOS_ALTURA,
      "proyecto.altura_evacuacion de /api/generar tiene los campos esperados",
      sorted(alt_g.keys()))
if FORMA_ANALIZAR is not None:
    check(FORMA_ANALIZAR == set(alt_g.keys()),
          "MISMA forma exacta en /api/analizar y /api/generar (mismo "
          "serializador, no dos contratos parecidos)",
          sorted(FORMA_ANALIZAR ^ set(alt_g.keys())))
check(all(set(a.keys()) == CAMPOS_AVISO for a in avisos_g),
      "y la misma forma de aviso")
check("altura_evacuacion_declarada" not in gp,
      "altura_evacuacion_declarada es exclusivo de /api/analizar (texto de "
      "formulario); en /api/generar la entrada ya es numerica y el propio "
      "hecho dice si es declarada -- mismo criterio que planta_declarada",
      sorted(gp.keys()))

print("\nH. Regresion de /api/generar")

for clave in ("edificio", "advertencias"):
    check(clave in g, "regresion: el payload conserva %r" % clave)
check("planta" in gp, "regresion: proyecto.planta (CAP-4) sigue publicandose")
check(g["edificio"]["plantas"] == 6,
      "el bloque `edificio` del payload no ha cambiado", g["edificio"]["plantas"])
check("altura_evacuacion_m" not in g["edificio"],
      "el campo de entrada no se cuela en el `edificio` del payload (que "
      "alimenta el visor 3D): CAP-5 no altera ese contrato")

print("\n" + "=" * 60)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
