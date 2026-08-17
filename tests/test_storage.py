# -*- coding: utf-8 -*-
"""Prueba de analyzer/storage.py contra el fixture real de ejemplo.dxf.

Ejecutar:  python tests/test_storage.py

Sin dependencias: el proyecto no tiene pytest ni ningun runner, asi que
esto es un script que sale con codigo 1 si algo falla. El fixture
(tests/fixtures/ejemplo-dxf-analisis.json) es la respuesta REAL de
/api/analizar sobre ejemplo.dxf, capturada el 2026-08-02: permite probar
la persistencia sin resubir 20 MB de DXF ni pagar otra llamada a la IA.
"""
import json
import os
import shutil
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

TMP = tempfile.mkdtemp(prefix="archmuse_test_")
os.environ["ARCHMUSE_DATA_DIR"] = TMP

from analyzer import storage  # noqa: E402

fallos = []


def check(nombre, cond, detalle=""):
    estado = "OK  " if cond else "FALLO"
    print("  [%s] %s%s" % (estado, nombre, ("  -> " + str(detalle)) if detalle else ""))
    if not cond:
        fallos.append(nombre)


with open(os.path.join(RAIZ, "tests", "fixtures", "ejemplo-dxf-analisis.json"), encoding="utf-8") as fh:
    fixture = json.load(fh)

print("Base de datos de prueba en:", TMP)
print()

print("1. Base vacia")
storage.init_db()
check("listar_proyectos() devuelve lista vacia", storage.listar_proyectos() == [])
check("init_db() es idempotente", (storage.init_db(), True)[1])

print("\n2. Guardar")
original = json.loads(json.dumps(fixture))  # copia intacta para comparar
meta = storage.guardar_proyecto(fixture, origen="dxf")
pid = meta["id"]
check("devuelve un id de 12 hex", len(pid) == 12 and all(c in "0123456789abcdef" for c in pid), pid)
check("nombre = nombre del DXF", meta["nombre"] == "ejemplo.dxf", meta["nombre"])
check("puntuacion extraida", meta["puntuacion"] == original["puntuacion_global"], meta["puntuacion"])
check("num_viviendas extraido", meta["num_viviendas"] == 6, meta["num_viviendas"])
check("ciudad extraida", meta["ciudad"] == original["proyecto"]["ciudad"], meta["ciudad"])
check("miniatura presente y es SVG", bool(meta["miniatura"]) and meta["miniatura"].startswith("<svg"))
check("miniatura ~5KB, no el payload entero", len(meta["miniatura"]) < 20000, "%d chars" % len(meta["miniatura"]))
check("metadatos NO incluyen el payload", "payload" not in meta)

print("\n3. Listar")
lista = storage.listar_proyectos()
check("hay 1 proyecto", len(lista) == 1)
check("el id coincide", lista[0]["id"] == pid)

print("\n4. Recuperar (el criterio que mas importa)")
recuperado = storage.obtener_proyecto(pid)
check("devuelve algo", recuperado is not None)
check("lleva proyecto_id inyectado", recuperado.get("proyecto_id") == pid)
esperado = json.loads(json.dumps(original))
esperado["proyecto_id"] = pid
check(
    "payload IDENTICO al analizado (salvo proyecto_id)",
    json.dumps(recuperado, sort_keys=True, ensure_ascii=False)
    == json.dumps(esperado, sort_keys=True, ensure_ascii=False),
)
check("6 viviendas intactas", len(recuperado["viviendas"]) == 6)
check("SVG de vivienda intacto", recuperado["viviendas"][0]["svg"] == original["viviendas"][0]["svg"])

print("\n5. Ids hostiles (path traversal)")
for malo in ["../../etc/passwd", "..\\..\\windows\\system32", "'; DROP TABLE proyectos; --",
             "", None, "ABCDEF123456", pid + "x"]:
    check("rechaza %r" % (malo,), storage.obtener_proyecto(malo) is None)
check("la tabla sigue viva tras el intento de SQL injection", len(storage.listar_proyectos()) == 1)

print("\n6. Persistencia real entre 'procesos'")
del sys.modules["analyzer.storage"]
from analyzer import storage as storage2  # noqa: E402

check("otro import ve el proyecto", len(storage2.listar_proyectos()) == 1)

print("\n7. Borrar")
check("borra y devuelve True", storage2.borrar_proyecto(pid) is True)
check("ya no esta", storage2.obtener_proyecto(pid) is None)
check("lista vacia", storage2.listar_proyectos() == [])
check("borrar dos veces devuelve False", storage2.borrar_proyecto(pid) is False)

print("\n8. Base corrupta")
import sqlite3  # noqa: E402

meta2 = storage2.guardar_proyecto(json.loads(json.dumps(original)), origen="dxf")
con = sqlite3.connect(storage2.db_path())
con.execute("UPDATE proyectos SET payload = ? WHERE id = ?", ("{esto no es json", meta2["id"]))
con.commit()
con.close()
check("payload ilegible devuelve None, no excepcion", storage2.obtener_proyecto(meta2["id"]) is None)
check("pero el proyecto sigue en la lista (borrable)", len(storage2.listar_proyectos()) == 1)

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 55)
if fallos:
    print("FALLOS (%d): %s" % (len(fallos), ", ".join(fallos)))
    sys.exit(1)
print("Todas las comprobaciones OK")
