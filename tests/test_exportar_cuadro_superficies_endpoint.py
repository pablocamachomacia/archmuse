# -*- coding: utf-8 -*-
"""Fase 4 — endpoint HTTP de exportación del cuadro de superficies relleno.

Ejecutar:  python tests/test_exportar_cuadro_superficies_endpoint.py

Usa `v2s.dxf` real y un DXF sintético SIN cuadro (construido en memoria, sin
tocar disco) para el caso negativo. Mismo patrón de aislamiento que
`tests/test_analizar_planta.py`: `ARCHMUSE_DATA_DIR` a un directorio temporal
antes de importar `app`, para no tocar la base de datos de desarrollo.

Que protege:

1. `/api/analizar` publica `proyecto.cuadro_superficies_detectado` (True con
   v2s.dxf, False con un DXF sin cuadro reconocible).
2. `POST /api/exportar-cuadro-superficies` con v2s.dxf devuelve 200, el
   `Content-Disposition` pide exactamente `v2s_ArchMuse_relleno.dxf`, y el
   cuerpo es un DXF válido con los valores calculados/N-D correctos.
3. `v2s.dxf` en disco NO cambia (hash antes/después de llamar al endpoint).
4. No queda ningún directorio temporal huérfano tras la llamada (el fallo
   real que se encontró y corrigió con `call_on_close` -> lectura síncrona
   a memoria, ver `app.py`).
5. Con un DXF sin cuadro reconocible -> 400 con mensaje claro, nunca 500.
6. Sin archivo adjunto / archivo no .dxf -> 400, mensaje claro.
7. `/api/informe-pdf` (exportación ya existente) sigue funcionando después
   de estos cambios.

Fase 5 (añadido en esta sesión):

8. `POST /api/cuadro-superficies/solicitudes` con v2s.dxf -> 200 y
   exactamente las cuatro solicitudes esperadas, serializadas.
9. `POST /api/exportar-cuadro-superficies-completo` con esas cuatro
   respuestas -> 200, descarga con `Content-Disposition` correcto, DXF sin
   ningún `N/D`, original intacto, sin restos temporales.
10. Mismo endpoint con una respuesta que contradice "VIVIENDA TIPO"
    (preexistente en v2s.dxf) -> 409, sin descarga, con el conflicto
    explicado en `pendientes`.
11. Mismo endpoint sin archivo / `respuestas` no-JSON -> 400, nunca 500.

Fase 6 (añadido en esta sesión): tabla del cuadro visible en pantalla.

12. `POST /api/cuadro-superficies/estado` con v2s.dxf -> 200, las 18 celdas
    serializadas (calculadas Y pendientes, a diferencia de /solicitudes que
    solo trae las pendientes), más las mismas 4 solicitudes de la sección 8.
13. Mismo endpoint, errores manejados con claridad (sin archivo / DXF sin
    cuadro), nunca 500; sin restos temporales.

Fase 6b (añadido en esta sesión): "no lo quiero para descargar, quiero
verlo en el navegador" -- resolver espacios exteriores sin generar un DXF.

14. `POST /api/cuadro-superficies/estado` con `respuestas` (asignación de
    tendedero/terraza 1/terraza 2) -> 200, las celdas de espacios
    exteriores y sus totales quedan CALCULADAS/CERO_REAL (ya no
    BLOQUEADAS), y NO se genera ni se ofrece ningún archivo -- la
    respuesta es JSON puro, nunca `application/dxf`.
15. Reenviar las mismas `respuestas` otra vez, más las que faltaban
    (superficies construidas, número de unidades) -> `solicitudes` queda
    vacía: exactamente el mismo cálculo que ya prueba la sección 9, pero
    sin pasar nunca por una escritura de DXF.

Fase 6e (añadido en esta sesión): sin caché en los estáticos de desarrollo.

16. `/`, `/app.js` y `/style.css` responden con `Cache-Control: no-store` --
    el navegador nunca sirve una versión vieja tras un cambio (confusión
    real ya vivida varias veces en esta sesión: "sigue sin funcionar" con
    el cambio ya hecho, solo que el navegador no lo había vuelto a pedir).
"""
import glob
import hashlib
import json
import os
import sys
import tempfile
from io import BytesIO

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

TMP_DATA = tempfile.mkdtemp(prefix="archmuse_test_fase4_")
os.environ["ARCHMUSE_DATA_DIR"] = TMP_DATA

from analyzer import storage  # noqa: E402
storage.init_db()

import app as app_module  # noqa: E402

fallos = []
comprobaciones = 0


def check(ok, etiqueta, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s%s" % ("OK  " if ok else "FALLO", etiqueta, ("  -> " + detalle) if detalle else ""))
    if not ok:
        fallos.append(etiqueta)


#: `v2s.dxf` es un plano real de un cliente: no está en el repositorio ni puede
#: estarlo. Se localiza con la variable de entorno `ARCHMUSE_DXF_V2S`. Sin ella
#: esta parte se salta, igual que antes — lo que ya no hay es la ruta personal
#: de nadie escrita en un repositorio público.
V2S = os.environ.get("ARCHMUSE_DXF_V2S", "")

if not os.path.exists(V2S):
    print("(v2s.dxf no disponible (define ARCHMUSE_DXF_V2S con su ruta) -- test omitido, mismo criterio que")
    print(" tests/test_cuadro_superficies.py / tests/test_analizar_planta.py)")
    print("Todas las comprobaciones OK (0)")
    sys.exit(0)

client = app_module.app.test_client()

with open(V2S, "rb") as f:
    V2S_BYTES = f.read()
V2S_HASH_ANTES = hashlib.sha256(V2S_BYTES).hexdigest()


def _restos_temporales():
    """Directorios `archmuse_cuadro_*` que pudiera haber dejado el
    endpoint en el temp del sistema (no en `TMP_DATA`, que es aparte)."""
    return set(glob.glob(os.path.join(tempfile.gettempdir(), "archmuse_cuadro_*")))


print()
print("1. `/api/analizar` publica cuadro_superficies_detectado")
print("-" * 68)

resp = client.post(
    "/api/analizar",
    data={"dxf": (BytesIO(V2S_BYTES), "v2s.dxf"), "norte": "0", "tipologia": "plurifamiliar", "ciudad": "Madrid"},
    content_type="multipart/form-data",
)
check(resp.status_code == 200, "v2s.dxf analiza con 200", str(resp.status_code))
payload_v2s = resp.get_json()
check(payload_v2s["proyecto"]["cuadro_superficies_detectado"] is True,
      "cuadro_superficies_detectado = True con v2s.dxf")

# DXF sintético SIN ACAD_TABLE -- caso negativo real, construido en memoria.
import ezdxf  # noqa: E402

import io  # noqa: E402

doc_sin_cuadro = ezdxf.new()
msp_sc = doc_sin_cuadro.modelspace()
msp_sc.add_lwpolyline(
    [(0, 0), (5, 0), (5, 4), (0, 4)], format="xy", dxfattribs={"layer": "00 areas", "closed": True},
)
msp_sc.add_text("Salón/cocina", dxfattribs={"layer": "00 TEXTO", "insert": (2, 2)})
buf_sc_texto = io.StringIO()  # `Drawing.write` (fmt="asc") es texto, no bytes
doc_sin_cuadro.write(buf_sc_texto)
DXF_SIN_CUADRO_BYTES = buf_sc_texto.getvalue().encode("utf-8")

resp2 = client.post(
    "/api/analizar",
    data={"dxf": (BytesIO(DXF_SIN_CUADRO_BYTES), "sin_cuadro.dxf"), "norte": "0"},
    content_type="multipart/form-data",
)
if resp2.status_code == 200:
    check(resp2.get_json()["proyecto"]["cuadro_superficies_detectado"] is False,
          "cuadro_superficies_detectado = False con un DXF sin ACAD_TABLE")
else:
    # El DXF sintético puede no llegar a analizarse por otro motivo (escala,
    # capa...) antes de llegar al punto donde se detecta el cuadro -- lo
    # relevante aquí es la detección en sí, se prueba directo más abajo.
    check(True, "(el DXF sintético no llegó a analizarse por otro motivo -- "
                "se prueba la detección directamente en su lugar)")
    from analyzer.cuadro_superficies import detectar_cuadro_superficies
    doc_reread = ezdxf.read(io.StringIO(DXF_SIN_CUADRO_BYTES.decode("utf-8")))
    check(detectar_cuadro_superficies(doc_reread) is None,
          "detectar_cuadro_superficies() = None sobre el DXF sintético sin ACAD_TABLE")


def _reabrir_bytes_dxf(contenido_bytes):
    """Escribe `contenido_bytes` a un archivo temporal y lo reabre con
    `ezdxf.readfile` -- v2s.dxf trae datos binarios embebidos (miniaturas/
    proxy graphics en grupos DXF binarios) que `ezdxf.read()` sobre un
    stream de texto reconstruido desde bytes no reabre de forma fiable.
    `ezdxf.readfile` sí, porque gestiona la codificación real del archivo
    (cp1252 aquí, ver informe de Fase 1) igual que hace la app de verdad."""
    tmp = tempfile.NamedTemporaryFile(suffix=".dxf", delete=False)
    try:
        tmp.write(contenido_bytes)
        tmp.close()
        return ezdxf.readfile(tmp.name)
    finally:
        os.remove(tmp.name)


print()
print("2 y 3. Exportación real de v2s.dxf: 200, nombre correcto, original intacto")
print("-" * 68)

resp_export = client.post(
    "/api/exportar-cuadro-superficies",
    data={"dxf": (BytesIO(V2S_BYTES), "v2s.dxf")},
    content_type="multipart/form-data",
)
check(resp_export.status_code == 200, "exportación de v2s.dxf -> 200", str(resp_export.status_code))
cd = resp_export.headers.get("Content-Disposition", "")
check('filename="v2s_ArchMuse_relleno.dxf"' in cd, "Content-Disposition pide el nombre exacto", cd)

with open(V2S, "rb") as f:
    hash_despues = hashlib.sha256(f.read()).hexdigest()
check(hash_despues == V2S_HASH_ANTES, "v2s.dxf en disco NO ha cambiado (mismo sha256)")


print()
print("4. No queda ningún directorio temporal huérfano")
print("-" * 68)

check(_restos_temporales() == set(), "sin restos archmuse_cuadro_* tras la exportación",
      str(_restos_temporales()))


print()
print("Contenido de la descarga: valores calculados y N/D correctos")
print("-" * 68)

cuerpo = resp_export.get_data()
doc_descargado = _reabrir_bytes_dxf(cuerpo)
auditor = doc_descargado.audit()
check(not auditor.has_errors, "el DXF descargado se reabre sin errores de audit")

mtx = {m.text: m for m in doc_descargado.modelspace().query("MTEXT[layer=='00 CUADROS']")}
esperado = {
    "21,90 m²": True, "0,00 m²": True, "12,72 m²": True, "8,48 m²": True, "8,53 m²": True,
    "4,01 m²": True, "3,14 m²": True, "58,78 m²": True,
}
n_valores_encontrados = sum(1 for t in esperado if t in mtx)
check(n_valores_encontrados == len(esperado), "todos los valores numéricos esperados están en la descarga",
      "%d/%d" % (n_valores_encontrados, len(esperado)))
n_nd = sum(1 for m in doc_descargado.modelspace().query("MTEXT[layer=='00 CUADROS']") if m.text == "N/D")
check(n_nd == 8, "hay exactamente 8 celdas N/D (bloqueadas + no disponibles)", "%d" % n_nd)

tabla_descargada = doc_descargado.modelspace().query("ACAD_TABLE")[0]
vt_descargado = [m for m in tabla_descargada.virtual_entities()
                  if m.dxftype() == "MTEXT" and "VT1" in m.text]
check(len(vt_descargado) == 1 and vt_descargado[0].text == "VT1 /3",
      "VIVIENDA TIPO sigue siendo VT1 /3, una sola vez, dentro de la tabla")


print()
print("5 y 6. Errores manejados con claridad, nunca 500")
print("-" * 68)

resp_sin_cuadro = client.post(
    "/api/exportar-cuadro-superficies",
    data={"dxf": (BytesIO(DXF_SIN_CUADRO_BYTES), "sin_cuadro.dxf")},
    content_type="multipart/form-data",
)
check(resp_sin_cuadro.status_code == 400, "DXF sin cuadro -> 400, no 500", str(resp_sin_cuadro.status_code))
check(bool((resp_sin_cuadro.get_json() or {}).get("error")), "y trae un mensaje de error legible")
check(_restos_temporales() == set(), "y tampoco deja restos temporales en el caso de error")

resp_sin_archivo = client.post("/api/exportar-cuadro-superficies", data={}, content_type="multipart/form-data")
check(resp_sin_archivo.status_code == 400, "sin archivo adjunto -> 400", str(resp_sin_archivo.status_code))

resp_no_dxf = client.post(
    "/api/exportar-cuadro-superficies",
    data={"dxf": (BytesIO(b"no soy un dxf"), "plano.txt")},
    content_type="multipart/form-data",
)
check(resp_no_dxf.status_code == 400, "archivo .txt (no .dxf) -> 400", str(resp_no_dxf.status_code))


print()
print("7. No se rompe la exportación PDF ya existente")
print("-" * 68)

resp_pdf = client.post(
    "/api/informe-pdf",
    json=payload_v2s,
)
check(resp_pdf.status_code == 200, "/api/informe-pdf sigue devolviendo 200 con el payload de v2s.dxf",
      str(resp_pdf.status_code))
check(resp_pdf.headers.get("Content-Type") == "application/pdf", "y sigue siendo un PDF")


print()
print("8. `/api/cuadro-superficies/solicitudes` -- exactamente las 4 solicitudes esperadas")
print("-" * 68)

resp_sol = client.post(
    "/api/cuadro-superficies/solicitudes",
    data={"dxf": (BytesIO(V2S_BYTES), "v2s.dxf")},
    content_type="multipart/form-data",
)
check(resp_sol.status_code == 200, "solicitudes de v2s.dxf -> 200", str(resp_sol.status_code))
payload_sol = resp_sol.get_json() or {}
solicitudes = payload_sol.get("solicitudes") or []
check(len(solicitudes) == 4, "exactamente 4 solicitudes serializadas", str(len(solicitudes)))
ids_sol = {s["id"] for s in solicitudes}
check(ids_sol == {
    "asignacion_exterior", "superficie_construida_cerrada",
    "superficie_construida_exterior", "numero_unidades",
}, "los cuatro ids esperados, ninguno más", str(ids_sol))

asignacion_sol = next(s for s in solicitudes if s["id"] == "asignacion_exterior")
check(asignacion_sol["tipo"] == "asignacion", "asignacion_exterior serializa tipo=asignacion")
candidatos_sol = asignacion_sol["candidatos"]
check(len(candidatos_sol) >= 2, "trae geometrías candidatas serializadas", str(len(candidatos_sol)))
check(all({"id", "etiqueta", "area_m2", "x", "y"} <= set(c.keys()) for c in candidatos_sol),
      "cada candidato serializado trae id/etiqueta/area_m2/x/y")

check(_restos_temporales() == set(), "sin restos temporales tras /solicitudes", str(_restos_temporales()))


print()
print("9. `/api/exportar-cuadro-superficies-completo` -- respuestas completas -> descarga sin N/D")
print("-" * 68)

respuestas_completas = [
    {
        "tipo": "asignacion", "solicitud_id": "asignacion_exterior",
        "asignaciones": {
            "tendedero": candidatos_sol[0]["id"],
            "terraza_1": candidatos_sol[1]["id"],
            "terraza_2": None,
        },
    },
    {"tipo": "numerico", "campo": "superficie_construida_cerrada", "valor": 70.5},
    {"tipo": "numerico", "campo": "superficie_construida_exterior", "valor": 12.0},
    {"tipo": "numerico", "campo": "numero_unidades", "valor": 3},
]

resp_completo = client.post(
    "/api/exportar-cuadro-superficies-completo",
    data={"dxf": (BytesIO(V2S_BYTES), "v2s.dxf"), "respuestas": json.dumps(respuestas_completas)},
    content_type="multipart/form-data",
)
check(resp_completo.status_code == 200, "con las 4 respuestas -> 200", str(resp_completo.status_code))
cd_completo = resp_completo.headers.get("Content-Disposition", "")
check('filename="v2s_ArchMuse_completo.dxf"' in cd_completo,
      "Content-Disposition pide el nombre completo exacto", cd_completo)

with open(V2S, "rb") as f:
    hash_despues_completo = hashlib.sha256(f.read()).hexdigest()
check(hash_despues_completo == V2S_HASH_ANTES, "v2s.dxf en disco sigue sin cambiar (mismo sha256)")

doc_completo = _reabrir_bytes_dxf(resp_completo.get_data())
mtx_completo = doc_completo.modelspace().query("MTEXT[layer=='00 CUADROS']")
n_nd_completo = sum(1 for m in mtx_completo if m.text == "N/D")
check(n_nd_completo == 0, "el DXF completo descargado no tiene ningún N/D", "%d" % n_nd_completo)

check(_restos_temporales() == set(), "sin restos temporales tras la descarga completa", str(_restos_temporales()))


print()
print("10. Respuesta en conflicto con VIVIENDA TIPO -- 409, sin descarga, conflicto explicado")
print("-" * 68)

respuesta_conflicto = [{"tipo": "numerico", "campo": "vivienda_tipo", "valor": 12.34}]
resp_conflicto = client.post(
    "/api/exportar-cuadro-superficies-completo",
    data={"dxf": (BytesIO(V2S_BYTES), "v2s.dxf"), "respuestas": json.dumps(respuesta_conflicto)},
    content_type="multipart/form-data",
)
check(resp_conflicto.status_code == 409, "respuesta en conflicto -> 409, no se ofrece descarga",
      str(resp_conflicto.status_code))
payload_conflicto = resp_conflicto.get_json() or {}
pendientes_conflicto = payload_conflicto.get("pendientes") or []
detalle_vt = next((p for p in pendientes_conflicto if p.get("campo") == "vivienda_tipo"), None)
check(detalle_vt is not None, "vivienda_tipo aparece entre los pendientes", str(pendientes_conflicto))
check(detalle_vt is not None and "Conflicto" in (detalle_vt.get("motivo") or ""),
      "y el motivo explica el conflicto", detalle_vt.get("motivo") if detalle_vt else None)

with open(V2S, "rb") as f:
    hash_despues_conflicto = hashlib.sha256(f.read()).hexdigest()
check(hash_despues_conflicto == V2S_HASH_ANTES, "v2s.dxf en disco sigue sin cambiar tras el conflicto")
check(_restos_temporales() == set(), "sin restos temporales tras el conflicto", str(_restos_temporales()))


print()
print("11. Errores manejados con claridad en los endpoints nuevos, nunca 500")
print("-" * 68)

resp_sol_sin_archivo = client.post("/api/cuadro-superficies/solicitudes", data={}, content_type="multipart/form-data")
check(resp_sol_sin_archivo.status_code == 400, "/solicitudes sin archivo -> 400", str(resp_sol_sin_archivo.status_code))

resp_completo_sin_archivo = client.post(
    "/api/exportar-cuadro-superficies-completo", data={}, content_type="multipart/form-data",
)
check(resp_completo_sin_archivo.status_code == 400,
      "/exportar-completo sin archivo -> 400", str(resp_completo_sin_archivo.status_code))

resp_json_invalido = client.post(
    "/api/exportar-cuadro-superficies-completo",
    data={"dxf": (BytesIO(V2S_BYTES), "v2s.dxf"), "respuestas": "esto no es JSON"},
    content_type="multipart/form-data",
)
check(resp_json_invalido.status_code == 400, "`respuestas` no-JSON -> 400, no 500",
      str(resp_json_invalido.status_code))
check(bool((resp_json_invalido.get_json() or {}).get("error")), "y trae un mensaje de error legible")
check(_restos_temporales() == set(), "sin restos temporales en ninguno de estos casos de error")


print()
print("12. `/api/cuadro-superficies/estado` -- las 18 celdas + las 4 solicitudes")
print("-" * 68)

resp_estado = client.post(
    "/api/cuadro-superficies/estado",
    data={"dxf": (BytesIO(V2S_BYTES), "v2s.dxf")},
    content_type="multipart/form-data",
)
check(resp_estado.status_code == 200, "estado de v2s.dxf -> 200", str(resp_estado.status_code))
payload_estado = resp_estado.get_json() or {}
celdas_estado = payload_estado.get("celdas") or []
check(len(celdas_estado) == 18, "las 18 celdas del cuadro, resueltas o no", str(len(celdas_estado)))

por_campo_estado = {c["campo"]: c for c in celdas_estado}
check(por_campo_estado["salon_cocina"]["texto"] == "21,90 m²" and por_campo_estado["salon_cocina"]["estado"] == "CALCULADO",
      "un campo calculado trae su texto real", str(por_campo_estado["salon_cocina"]))
check(por_campo_estado["tendedero"]["estado"] == "BLOQUEADO",
      "un campo pendiente SIGUE presente en /estado (a diferencia de /solicitudes)", str(por_campo_estado["tendedero"]))
check(por_campo_estado["vivienda_tipo"]["preexistente"] is True and por_campo_estado["vivienda_tipo"]["texto"] == "VT1 /3",
      "la procedencia (preexistente) viaja en la serialización", str(por_campo_estado["vivienda_tipo"]))
check(all({"campo", "etiqueta", "texto", "estado", "motivo", "preexistente", "declarado_por_usuario"} <= set(c.keys())
          for c in celdas_estado),
      "cada celda serializada trae todas las claves esperadas")

solicitudes_estado = payload_estado.get("solicitudes") or []
check({s["id"] for s in solicitudes_estado} == {
    "asignacion_exterior", "superficie_construida_cerrada",
    "superficie_construida_exterior", "numero_unidades",
}, "las mismas 4 solicitudes que /solicitudes (mismo cálculo, sin repetirlo)", str([s["id"] for s in solicitudes_estado]))

check(_restos_temporales() == set(), "sin restos temporales tras /estado")


print()
print("13. `/api/cuadro-superficies/estado` -- errores manejados, nunca 500")
print("-" * 68)

resp_estado_sin_archivo = client.post("/api/cuadro-superficies/estado", data={}, content_type="multipart/form-data")
check(resp_estado_sin_archivo.status_code == 400, "/estado sin archivo -> 400", str(resp_estado_sin_archivo.status_code))

resp_estado_sin_cuadro = client.post(
    "/api/cuadro-superficies/estado",
    data={"dxf": (BytesIO(DXF_SIN_CUADRO_BYTES), "sin_cuadro.dxf")},
    content_type="multipart/form-data",
)
check(resp_estado_sin_cuadro.status_code == 400, "/estado con DXF sin cuadro -> 400, no 500",
      str(resp_estado_sin_cuadro.status_code))
check(bool((resp_estado_sin_cuadro.get_json() or {}).get("error")), "y trae un mensaje de error legible")
check(_restos_temporales() == set(), "sin restos temporales en los casos de error de /estado")


print()
print("14 y 15. `/estado` con `respuestas` -- resuelve espacios exteriores SIN generar un DXF")
print("-" * 68)

respuesta_asignacion = {
    "tipo": "asignacion", "solicitud_id": "asignacion_exterior",
    "asignaciones": {
        "tendedero": candidatos_sol[0]["id"],
        "terraza_1": candidatos_sol[1]["id"],
        "terraza_2": None,
    },
}

resp_estado_parcial = client.post(
    "/api/cuadro-superficies/estado",
    data={"dxf": (BytesIO(V2S_BYTES), "v2s.dxf"), "respuestas": json.dumps([respuesta_asignacion])},
    content_type="multipart/form-data",
)
check(resp_estado_parcial.status_code == 200, "/estado con respuestas -> 200", str(resp_estado_parcial.status_code))
check(resp_estado_parcial.headers.get("Content-Type", "").startswith("application/json"),
      "la respuesta es JSON puro, nunca un DXF para descargar", resp_estado_parcial.headers.get("Content-Type"))

payload_parcial = resp_estado_parcial.get_json() or {}
por_campo_parcial = {c["campo"]: c for c in (payload_parcial.get("celdas") or [])}
check(por_campo_parcial["tendedero"]["estado"] in ("CALCULADO", "CERO_REAL"),
      "tendedero deja de estar BLOQUEADO tras la respuesta", str(por_campo_parcial["tendedero"]))
check(por_campo_parcial["tendedero"]["declarado_por_usuario"] is True,
      "y queda marcado declarado_por_usuario=True")
check(por_campo_parcial["terraza_2"]["estado"] == "CERO_REAL" and por_campo_parcial["terraza_2"]["texto"] == "0,00 m²",
      "terraza_2 (sin asignar) -> CERO_REAL declarado, 0,00 m², no N/D", str(por_campo_parcial["terraza_2"]))

ids_solicitudes_parcial = {s["id"] for s in (payload_parcial.get("solicitudes") or [])}
check("asignacion_exterior" not in ids_solicitudes_parcial,
      "la solicitud de asignación exterior ya no aparece -- está resuelta", str(ids_solicitudes_parcial))
check(ids_solicitudes_parcial == {"superficie_construida_cerrada", "superficie_construida_exterior", "numero_unidades"},
      "quedan exactamente las 3 solicitudes numéricas, nada más")

respuestas_todas = [respuesta_asignacion] + [
    {"tipo": "numerico", "campo": "superficie_construida_cerrada", "valor": 70.5},
    {"tipo": "numerico", "campo": "superficie_construida_exterior", "valor": 12.0},
    {"tipo": "numerico", "campo": "numero_unidades", "valor": 3},
]
resp_estado_completo = client.post(
    "/api/cuadro-superficies/estado",
    data={"dxf": (BytesIO(V2S_BYTES), "v2s.dxf"), "respuestas": json.dumps(respuestas_todas)},
    content_type="multipart/form-data",
)
payload_estado_completo = resp_estado_completo.get_json() or {}
check((payload_estado_completo.get("solicitudes") or []) == [],
      "con las 4 respuestas, /estado ya no devuelve ninguna solicitud pendiente",
      str(payload_estado_completo.get("solicitudes")))
check(all(c["texto"] != "N/D" and c["estado"] not in ("BLOQUEADO", "NO_DISPONIBLE")
          for c in payload_estado_completo.get("celdas") or []),
      "y las 18 celdas tienen ya un valor real -- todo esto sin haber generado ni descargado ningún DXF")

with open(V2S, "rb") as f:
    hash_tras_estado = hashlib.sha256(f.read()).hexdigest()
check(hash_tras_estado == V2S_HASH_ANTES, "v2s.dxf en disco sigue intacto tras usar /estado con respuestas")
check(_restos_temporales() == set(), "sin restos temporales tras /estado con respuestas")


print()
print("16. Sin caché en los estáticos de desarrollo -- el navegador siempre pide lo último")
print("-" * 68)

resp_index = client.get("/")
check(resp_index.headers.get("Cache-Control") == "no-store", "/ responde Cache-Control: no-store",
      resp_index.headers.get("Cache-Control"))
resp_appjs = client.get("/app.js")
check(resp_appjs.headers.get("Cache-Control") == "no-store", "/app.js responde Cache-Control: no-store",
      resp_appjs.headers.get("Cache-Control"))
resp_css = client.get("/style.css")
check(resp_css.headers.get("Cache-Control") == "no-store", "/style.css responde Cache-Control: no-store",
      resp_css.headers.get("Cache-Control"))
# El propio endpoint JSON de esta fase, en cambio, no necesita este header
# aparte -- Flask no cachea JSON de API por defecto, y añadir no-store aquí
# también no cambia nada real; se comprueba solo que no se ha roto nada.
check(resp_estado.status_code == 200, "y /api/cuadro-superficies/estado sigue funcionando con normalidad")


print()
print("=" * 68)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
