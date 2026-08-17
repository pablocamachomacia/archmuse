# -*- coding: utf-8 -*-
"""CAP-4, tarea 5: integracion HTTP de `planta` en `POST /api/analizar`.

Ejecutar:  python tests/test_analizar_planta.py

Usa `ejemplo.dxf` real (el unico plano real disponible) contra un cliente de
pruebas de Flask, con `ARCHMUSE_DATA_DIR` apuntando a un directorio temporal
(mismo patron que `tests/test_storage.py`) para no tocar la base de datos de
desarrollo. Si `ejemplo.dxf` no esta disponible, se salta con aviso, igual
que el bloque L de `tests/test_ocupacion.py`.

Que protege:

1. Planta declarada valida ("Planta 3") -> KNOWN, se propaga a `ocupacion`
   (ambito real, agregado_no_normativo=False), y los NUMEROS de ocupacion
   (personas) no cambian ni un decimal respecto de no declarar planta.
2. Planta no declarada -> UNKNOWN, comportamiento IDENTICO a una linea base
   calculada directamente sobre el mismo `ejemplo.dxf`: 5 ESTIMATED +
   1 UNKNOWN (4 ESTIMATED + 2 UNKNOWN hasta la correccion de cierre
   geometrico de 2026-08-13, `analyzer/parser.py::_esta_cerrada` — ver
   `tests/test_cierre_recuperado.py`), mismos valores.
3. Declaracion ambigua ("entre planta y planta") -> UNKNOWN explicito, con
   motivo propio, nunca una planta inventada.
4. Prohibicion dura: declarar literalmente "VT1/3" como planta NO se
   interpreta como planta 1 (ni de ninguna otra forma) -> UNKNOWN.
5. Forma exacta del payload: `proyecto.planta_declarada`, `proyecto.planta`,
   y los campos nuevos de `proyecto.ocupacion` (`ambito_emitido`,
   `agregado_no_normativo`).

Tarea 13 (publicacion de C01) anade:

6. `proyecto.sectorizacion` publicado sobre `ejemplo.dxf`, con y sin planta
   declarada — siempre UNKNOWN sobre este DXF real (~295 m2 << 2500), nunca
   PASS.
7. Casos sinteticos de extremo a extremo via HTTP (con `leer_plano`/
   `load_document` sustituidos por un doble determinista, sin DXF real ni
   llamada a la IA): planta >= 2.500 m2 -> FAIL publicado; < 2.500 -> UNKNOWN;
   sin planta -> UNKNOWN. Nunca "PASS" en ningun caso.
8. Los valores de `ocupacion` (personas) siguen exactamente iguales a CAP-3
   con esta tarea — no se ha tocado `ocupacion()`.
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

# Ver la nota equivalente en tests/test_generar_planta.py: `app.py` solo
# llama a `init_db()` como efecto lateral de import, una vez por proceso.
# Si este fichero se recolecta DESPUES de otro que ya importo `app` con un
# `ARCHMUSE_DATA_DIR` distinto, ese `init_db()` no se repite aqui. Se llama
# explicitamente para no depender del orden de recoleccion de pytest.
storage.init_db()

import app as app_module  # noqa: E402
from analyzer.hechos import ESTIMATED, KNOWN, UNKNOWN  # noqa: E402

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


DXF = os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf")
if not os.path.exists(DXF):
    print("[SALTA] no se encuentra %s" % DXF)
    print("Todas las comprobaciones OK (0)")
    sys.exit(0)

with open(DXF, "rb") as fh:
    DXF_BYTES = fh.read()

client = app_module.app.test_client()

# Tarea 13: acumula proyecto.sectorizacion de TODAS las respuestas HTTP de
# este fichero, para el barrido final "nunca PASS" (seccion I).
TODAS_LAS_SECTORIZACIONES = []


def registrar_http(respuesta):
    TODAS_LAS_SECTORIZACIONES.extend(respuesta["proyecto"].get("sectorizacion") or [])
    return respuesta


def analizar(planta_texto=None, **extra_form):
    """POST a /api/analizar con ejemplo.dxf y, opcionalmente, el campo
    `planta`. Devuelve el JSON de respuesta."""
    data = {"dxf": (BytesIO(DXF_BYTES), "ejemplo.dxf")}
    if planta_texto is not None:
        data["planta"] = planta_texto
    data.update(extra_form)
    resp = client.post("/api/analizar", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200, "esperaba 200, obtuvo %d: %s" % (
        resp.status_code, resp.get_data(as_text=True)[:500])
    return resp.get_json()


print("Calculando la linea base directa (sin HTTP, sin planta) para comparar...")

# Mismo camino que el bloque L de tests/test_ocupacion.py: la referencia
# independiente contra la que se compara la respuesta HTTP.
from analyzer import parser  # noqa: E402
from analyzer.evaluator import evaluate_advanced  # noqa: E402
from analyzer.ocupacion import ocupacion as calcular_ocupacion_directo  # noqa: E402
from analyzer.superficie_util import superficie_util_ocupable_db_si  # noqa: E402
from analyzer.uso_previsto import ZonaDeUso, usos_por_zona  # noqa: E402

plano = parser.leer_plano(parser.load_document(DXF))
advanced_directo = evaluate_advanced(
    plano.rooms, unit_labels=plano.unit_labels, norte_grados=0,
    tipologia="plurifamiliar", zona_cte="C", densidad_urbana="media",
)
usos_directo = usos_por_zona(
    [ZonaDeUso(nombre="vivienda %s" % us.unit.name) for us in advanced_directo.unit_scores],
    tipologia="plurifamiliar", uso_principal=None,
)
BASELINE = {
    us.unit.name: calcular_ocupacion_directo(
        superficie_util_ocupable_db_si(us.unit), uso_hecho,
    )
    for us, uso_hecho in zip(advanced_directo.unit_scores, usos_directo)
}
n_estimated_baseline = sum(1 for h in BASELINE.values() if h.estado == ESTIMATED)
n_unknown_baseline = sum(1 for h in BASELINE.values() if h.estado == UNKNOWN)
# Eran 4 ESTIMATED + 2 UNKNOWN (VT5/1 y VT6/2) hasta la correccion de cierre
# geometrico de 2026-08-13 (analyzer/parser.py::_esta_cerrada, ver
# tests/test_cierre_recuperado.py): VT5/1 tenia un solape sin resolver por un
# contorno duplicado que la propia correccion elimina, y pasa a ESTIMATED.
# VT6/2 sigue UNKNOWN, ahora por una causa distinta y genuina del DXF
# (Dormitorio 2 recuperado es geometricamente invalido, mas un solape
# preexistente entre dos Terrazas) -- ver docs/audits/2026-08-13-hallazgos-cierre-geometrico.md.
check(n_estimated_baseline == 5 and n_unknown_baseline == 1,
      "linea base directa: 5 ESTIMATED + 1 UNKNOWN (CAP-3, ejemplo.dxf)",
      "%d ESTIMATED, %d UNKNOWN" % (n_estimated_baseline, n_unknown_baseline))


print("\nA. Planta NO declarada -> UNKNOWN, identico a CAP-3 (bd1a62f)")

resp_sin = registrar_http(analizar(planta_texto=None))
proy_sin = resp_sin["proyecto"]
check(proy_sin.get("planta_declarada") is None,
      "planta_declarada es null cuando no se envia el campo")
check(all(p["estado"] == UNKNOWN for p in proy_sin["planta"]),
      "todas las unidades: planta UNKNOWN")
check(all(p["numero"] is None for p in proy_sin["planta"]),
      "todas las unidades: sin numero de planta")
# Tarea 7: el contrato completo del hecho serializado, no solo estado/numero.
check(all(p["confianza"] is None for p in proy_sin["planta"]),
      "todas las unidades: sin planta, confianza=None (no hay insumo que valorar)")
check(all(p["origen"] is None for p in proy_sin["planta"]),
      "todas las unidades: sin planta, origen=None")
check(all(p["motivo"] and "no se ha declarado" in p["motivo"].lower()
          for p in proy_sin["planta"]),
      "todas las unidades: motivo explica la ausencia, no viene vacio",
      proy_sin["planta"][0]["motivo"])
check(all(p["explicacion"] for p in proy_sin["planta"]),
      "todas las unidades: explicacion no viene vacia",
      proy_sin["planta"][0]["explicacion"])
check(all(p["ambito"].startswith("vivienda ") for p in proy_sin["planta"]),
      "todas las unidades: ambito identifica la vivienda (sin planta resuelta)",
      proy_sin["planta"][0]["ambito"])

ocup_por_vivienda = {}
for o in proy_sin["ocupacion"]:
    nombre_vivienda = o["ambito"].replace("vivienda ", "", 1)
    ocup_por_vivienda[nombre_vivienda] = o

n_est_http = sum(1 for o in proy_sin["ocupacion"] if o["estado"] == "ESTIMATED")
n_unk_http = sum(1 for o in proy_sin["ocupacion"] if o["estado"] == "UNKNOWN")
check(n_est_http == 5 and n_unk_http == 1,
      "HTTP sin planta: 5 ESTIMATED + 1 UNKNOWN, igual que la linea base",
      "%d ESTIMATED, %d UNKNOWN" % (n_est_http, n_unk_http))

for nombre, esperado in BASELINE.items():
    obtenido = ocup_por_vivienda.get(nombre)
    check(obtenido is not None, "%s aparece en la respuesta HTTP" % nombre)
    if obtenido is None:
        continue
    check(obtenido["estado"] == esperado.estado,
          "%s: estado HTTP == estado directo (%s)" % (nombre, esperado.estado),
          obtenido["estado"])
    if esperado.estado != UNKNOWN:
        check(abs(obtenido["personas"] - esperado.valor) < 1e-9,
              "%s: personas HTTP == personas directo, sin redondear" % nombre,
              "http=%r directo=%r" % (obtenido["personas"], esperado.valor))
    check(obtenido["agregado_no_normativo"] is True,
          "%s: sin planta, sigue agregado_no_normativo=True" % nombre)
    check(obtenido["ambito_emitido"] == "vivienda",
          "%s: sin planta, ambito_emitido='vivienda'" % nombre)


print("\nB. Planta declarada valida (\"Planta 3\") -> KNOWN, se propaga a ocupacion")

resp_con = registrar_http(analizar(planta_texto="Planta 3"))
proy_con = resp_con["proyecto"]
check(proy_con.get("planta_declarada") == "Planta 3",
      "planta_declarada conserva el texto tal cual se envio")
check(all(p["estado"] == KNOWN and p["numero"] == 3 for p in proy_con["planta"]),
      "todas las unidades: planta KNOWN, numero=3")
check(all(p["confianza"] == "Alta" for p in proy_con["planta"]),
      "todas las unidades: confianza Alta (declaracion explicita)")
check(all(p["sobre_rasante"] is True for p in proy_con["planta"]),
      "todas las unidades: sobre_rasante=True (planta 3 > 0)")
# Tarea 7: campos restantes del contrato para el caso KNOWN/declarado.
check(all(p["origen"] == "declarado" for p in proy_con["planta"]),
      "todas las unidades: origen='declarado' (viene del formulario, no de "
      "una convencion de nombre)",
      proy_con["planta"][0]["origen"])
check(all(p["motivo"] is None for p in proy_con["planta"]),
      "todas las unidades: motivo=None (KNOWN no lleva motivo de ausencia)")
check(all(p["explicacion"] for p in proy_con["planta"]),
      "todas las unidades: explicacion no viene vacia",
      proy_con["planta"][0]["explicacion"])
check(all(p["ambito"].startswith("vivienda ") for p in proy_con["planta"]),
      "todas las unidades: ambito del hecho planta identifica la vivienda "
      "(distinto del ambito de ocupacion, que sí antepone la planta)",
      proy_con["planta"][0]["ambito"])

for o in proy_con["ocupacion"]:
    check(o["agregado_no_normativo"] is False,
          "%s: CON planta, agregado_no_normativo=False" % o["ambito"])
    check(o["ambito_emitido"] == "planta 3",
          "%s: CON planta, ambito_emitido='planta 3'" % o["ambito"],
          o["ambito_emitido"])
    check("planta 3" in o["ambito"],
          "%s: el ambito del hecho identifica la planta real" % o["ambito"])

ocup_con_por_vivienda = {
    o["ambito"].split(", ", 1)[1].replace("vivienda ", "", 1): o
    for o in proy_con["ocupacion"]
}
for nombre, esperado in BASELINE.items():
    obtenido = ocup_con_por_vivienda.get(nombre)
    check(obtenido is not None, "%s aparece en la respuesta HTTP (con planta)" % nombre)
    if obtenido is None:
        continue
    if esperado.estado != UNKNOWN:
        check(abs(obtenido["personas"] - esperado.valor) < 1e-9,
              "%s: CON planta declarada, personas SIGUE igual (planta no toca el "
              "calculo)" % nombre,
              "con_planta=%r sin_planta=%r" % (obtenido["personas"], esperado.valor))


print("\nC. Declaracion ambigua -> UNKNOWN explicito, con motivo propio")

resp_ambiguo = analizar(planta_texto="entre planta y planta")
proy_ambiguo = resp_ambiguo["proyecto"]
check(proy_ambiguo.get("planta_declarada") == "entre planta y planta",
      "planta_declarada conserva el texto ambiguo tal cual")
check(all(p["estado"] == UNKNOWN for p in proy_ambiguo["planta"]),
      "texto ambiguo -> UNKNOWN, nunca una planta inventada")
motivo_ambiguo = proy_ambiguo["planta"][0]["motivo"]
check(motivo_ambiguo is not None and "no se ha podido interpretar" in motivo_ambiguo.lower(),
      "el motivo distingue 'no interpretable' de 'no declarada'",
      motivo_ambiguo)
check(motivo_ambiguo != proy_sin["planta"][0]["motivo"],
      "el motivo de 'ambiguo' es distinto del motivo de 'no declarada'")


print("\nD. Prohibicion dura: 'VT1/3' como planta NO se interpreta como planta 1")

resp_vt = analizar(planta_texto="VT1/3")
proy_vt = resp_vt["proyecto"]
check(all(p["estado"] == UNKNOWN for p in proy_vt["planta"]),
      "'VT1/3' declarado como planta -> UNKNOWN, nunca planta 1 (ni ninguna)")
check(all(p["numero"] is None for p in proy_vt["planta"]),
      "'VT1/3' -> numero de planta es None, no 1")

for texto_vt in ("VT2/2", "VT9/9", "vt1"):
    resp_x = analizar(planta_texto=texto_vt)
    check(all(p["estado"] == UNKNOWN for p in resp_x["proyecto"]["planta"]),
          "%r declarado como planta -> UNKNOWN" % texto_vt)


print("\nE. Forma del payload")

check("planta_declarada" in proy_sin and "planta" in proy_sin,
      "proyecto.planta_declarada y proyecto.planta existen siempre")
campos_esperados = {"ambito", "numero", "sobre_rasante", "estado", "confianza",
                     "origen", "motivo", "explicacion"}
check(set(proy_sin["planta"][0].keys()) == campos_esperados,
      "cada entrada de proyecto.planta tiene exactamente los campos esperados",
      sorted(proy_sin["planta"][0].keys()))
campos_ocupacion_nuevos = {"ambito_emitido", "agregado_no_normativo"}
check(campos_ocupacion_nuevos.issubset(proy_sin["ocupacion"][0].keys()),
      "proyecto.ocupacion incluye los campos nuevos de ambito")

print("\nF. Tarea 13 — C01 publicado en /api/analizar sobre ejemplo.dxf (sin planta)")

check("sectorizacion" in proy_sin, "proyecto.sectorizacion existe (sin planta declarada)")
check(len(proy_sin["sectorizacion"]) == 6, "un elemento de C01 por cada una de las 6 unidades",
      len(proy_sin["sectorizacion"]))
check(all(s["estado"] == "UNKNOWN" for s in proy_sin["sectorizacion"]),
      "C01 = UNKNOWN para las 6, sin planta declarada")
check(all(s["veredicto"] != "PASS" for s in proy_sin["sectorizacion"]),
      "ningun PASS de C01 (sin planta)")
check(all(s["superficie_acumulada_m2"] is None for s in proy_sin["sectorizacion"]),
      "sin veredicto de FAIL, no se publica superficie_acumulada_m2 (P6)")
campos_sectorizacion_esperados = {
    "ambito", "planta_numero", "superficie_acumulada_m2", "limite_m2", "estado",
    "veredicto", "confianza", "codigo", "motivo", "explicacion",
    "unidades_computadas", "unidades_sin_superficie",
}
check(set(proy_sin["sectorizacion"][0].keys()) == campos_sectorizacion_esperados,
      "proyecto.sectorizacion tiene exactamente los campos esperados (trazabilidad completa)",
      sorted(proy_sin["sectorizacion"][0].keys()))
check(proy_sin["sectorizacion"][0]["codigo"] == "DB-SI-1-SECTOR-2500",
      "codigo estable de C01, distinto de CTE-DB-SI-3", proy_sin["sectorizacion"][0]["codigo"])
check(proy_sin["sectorizacion"][0]["limite_m2"] == 2500.0, "limite_m2 = 2500 publicado")

print("\nG. C01 publicado con planta declarada (\"Planta 3\") — semantica del PRD")

check("sectorizacion" in proy_con, "proyecto.sectorizacion existe (con planta declarada)")
check(all(s["estado"] == "UNKNOWN" for s in proy_con["sectorizacion"]),
      "C01 = UNKNOWN para las 6 (suma real ~295 m2, muy por debajo de 2500)")
check(all(s["veredicto"] != "PASS" for s in proy_con["sectorizacion"]),
      "ningun PASS de C01 (con planta declarada)")
check(all(s["ambito"] == "planta 3" for s in proy_con["sectorizacion"]),
      "las 6 unidades comparten el ambito de C01: 'planta 3'",
      proy_con["sectorizacion"][0]["ambito"])
check(all(s["planta_numero"] == 3 for s in proy_con["sectorizacion"]),
      "planta_numero = 3, trazado correctamente")
# Antes de la correccion de cierre geometrico de 2026-08-13, VT5/1 y VT6/2
# quedaban las dos sin superficie por el mismo contorno duplicado. VT5/1 ya
# se lee bien (esa correccion la resuelve); VT6/2 sigue sin superficie, pero
# ahora por una causa distinta y genuina del DXF (Dormitorio 2 recuperado es
# invalido, mas un solape preexistente entre dos Terrazas) -- ver
# docs/audits/2026-08-13-hallazgos-cierre-geometrico.md.
check(sorted(proy_con["sectorizacion"][0]["unidades_sin_superficie"]) ==
      ["vivienda VT6/2"],
      "trazabilidad: la unidad sin superficie queda listada",
      proy_con["sectorizacion"][0]["unidades_sin_superficie"])

print("\nH. Tarea 13 — casos sinteticos de extremo a extremo via HTTP (sin DXF real, sin IA)")

from shapely.geometry import Polygon  # noqa: E402
from analyzer.parser import PlanoLeido, Room  # noqa: E402
from analyzer.escala import EscalaDetectada  # noqa: E402


def _rect(x0, y0, ancho, alto, etiqueta):
    return Room(label=etiqueta, layer="00 areas",
                polygon=Polygon([(x0, y0), (x0 + ancho, y0),
                                 (x0 + ancho, y0 + alto), (x0, y0 + alto)]))


def analizar_sintetico(rooms, planta_texto=None):
    """POST a /api/analizar con `load_document`/`leer_plano` sustituidos por
    un doble determinista: nunca abre un DXF real, nunca llama a la IA.
    Permite construir, con control total, casos de superficie que `ejemplo.dxf`
    no tiene (una planta real y disponible mide apenas ~295 m2, muy lejos del
    limite de 2.500)."""
    plano_falso = PlanoLeido(
        rooms=rooms, unit_labels=[],
        escala=EscalaDetectada(factor=1.0, unidad="metros", origen="acuerdo",
                                mensaje="sintetico de test"),
        layer="00 areas",
    )
    data = {"dxf": (BytesIO(b"contenido irrelevante: leer_plano esta sustituido"),
                     "sintetico.dxf")}
    if planta_texto is not None:
        data["planta"] = planta_texto
    with patch("app.load_document", return_value=object()), \
         patch("app.leer_plano", return_value=plano_falso):
        resp = client.post("/api/analizar", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200, "esperaba 200, obtuvo %d: %s" % (
        resp.status_code, resp.get_data(as_text=True)[:500])
    return resp.get_json()


print("\nH.1 Superficie de planta >= 2.500 m2 -> C01 FAIL publicado")

# Dos "viviendas" bien separadas (proximidad -> unidades distintas) que
# suman 3040 m2 de superficie util, todas en la misma planta declarada.
rooms_fail = [
    _rect(0, 0, 60, 50, "Salon"),        # 3000 m2
    _rect(1000, 0, 8, 5, "Salon"),       # 40 m2, lejos de la primera
]
resp_fail = registrar_http(analizar_sintetico(rooms_fail, planta_texto="Planta 1"))
sect_fail = resp_fail["proyecto"]["sectorizacion"]
check(len(sect_fail) == 2, "dos unidades sinteticas -> dos entradas de C01")
check(all(s["estado"] == "KNOWN" for s in sect_fail),
      "suma 3040 >= 2500 -> C01 KNOWN (FAIL) publicado en la API", sect_fail[0]["estado"])
check(all(s["veredicto"] == "FAIL" for s in sect_fail),
      "veredicto publicado == 'FAIL'", sect_fail[0]["veredicto"])
check(all(abs(s["superficie_acumulada_m2"] - 3040.0) < 1e-6 for s in sect_fail),
      "superficie_acumulada_m2 publicada = 3040.0 (trazabilidad)",
      sect_fail[0]["superficie_acumulada_m2"])
check(all(s["veredicto"] != "PASS" for s in sect_fail), "ningun PASS (caso FAIL)")

print("\nH.2 Superficie de planta < 2.500 m2 -> C01 UNKNOWN publicado (nunca PASS)")

rooms_unknown = [
    _rect(0, 0, 10, 8, "Salon"),         # 80 m2
    _rect(1000, 0, 10, 8, "Salon"),      # 80 m2, muy por debajo de 2500
]
resp_unk = registrar_http(analizar_sintetico(rooms_unknown, planta_texto="Planta 1"))
sect_unk = resp_unk["proyecto"]["sectorizacion"]
check(all(s["estado"] == "UNKNOWN" for s in sect_unk),
      "suma 160 < 2500 -> C01 UNKNOWN publicado", sect_unk[0]["estado"])
check(all(s["veredicto"] != "PASS" for s in sect_unk),
      "NUNCA 'PASS', ni siquiera con superficie pequeña y clara", sect_unk[0]["veredicto"])
check(all(s["superficie_acumulada_m2"] is None for s in sect_unk),
      "UNKNOWN no publica superficie_acumulada_m2 (P6)")

print("\nH.3 Sin planta declarada (caso sintetico) -> C01 UNKNOWN publicado")

resp_sinplanta = registrar_http(analizar_sintetico(rooms_fail, planta_texto=None))
sect_sinplanta = resp_sinplanta["proyecto"]["sectorizacion"]
check(all(s["estado"] == "UNKNOWN" for s in sect_sinplanta),
      "sin planta, incluso con 3040 m2 de superficie -> C01 UNKNOWN (no se "
      "agrega sin saber la planta)", sect_sinplanta[0]["estado"])
check(all(s["veredicto"] != "PASS" for s in sect_sinplanta), "ningun PASS")
check(all(s["planta_numero"] is None for s in sect_sinplanta),
      "planta_numero no inventado")

print("\nI. Nunca PASS — barrido sobre TODO lo publicado en este fichero")

check(len(TODAS_LAS_SECTORIZACIONES) >= 10,
      "muestra amplia acumulada de entradas de C01 publicadas por HTTP",
      len(TODAS_LAS_SECTORIZACIONES))
check(all(s["veredicto"] != "PASS" for s in TODAS_LAS_SECTORIZACIONES),
      "en NINGUNA respuesta HTTP de este fichero aparece veredicto == 'PASS'")
check(all(s["estado"] in ("KNOWN", "UNKNOWN") for s in TODAS_LAS_SECTORIZACIONES),
      "estado publicado siempre KNOWN o UNKNOWN, nunca un tercero")

print("\nJ. Los valores de ocupacion (personas) siguen identicos a CAP-3 con esta tarea")

# Repite, sobre las respuestas ya capturadas en A/B, la comparacion exacta
# contra la linea base directa — no se ha tocado ocupacion() en la tarea 13.
for nombre, esperado in BASELINE.items():
    obtenido = ocup_por_vivienda.get(nombre)
    if esperado.estado != UNKNOWN:
        check(abs(obtenido["personas"] - esperado.valor) < 1e-9,
              "%s: personas sigue == baseline bd1a62f tras publicar C01" % nombre,
              "obtenido=%r esperado=%r" % (obtenido["personas"], esperado.valor))
    else:
        check(obtenido["personas"] is None,
              "%s: sigue UNKNOWN (sin personas) tras publicar C01" % nombre)

print("\n" + "=" * 60)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
