# -*- coding: utf-8 -*-
"""E2 — persistencia del modelo arquitectónico común.

Ejecutar:  python tests/test_e2_persistencia.py

Contra `analyzer/storage.py` real (SQLite en un directorio temporal, mismo
patrón que `tests/test_storage.py`), con grafos reales construidos sobre
`ejemplo.dxf` — no se inventa un modelo de juguete: lo mismo que se guarda en
producción es lo que se guarda aquí.

Ocho bloques, en el orden de los criterios de aceptación del PRD
(`docs/prd/2026-08-11-e2-persistencia-modelo.md`):

1. Persistencia y recuperación (B2, B3) — round-trip exacto.
2. `obtener_modelo()` en `None`: id inválido, proyecto sin modelo (B1, caso límite).
3. Compatibilidad hacia atrás (B1, caso límite): fila de antes de E2 migrada.
4. Aislamiento entre proyectos: dos análisis no comparten nada.
5. Determinismo estructural (C-E2.2): mismos nodos y aristas, `concept_id` distinto.
6. El payload público no cambia (C-E2.4, B5).
7. Modelo corrupto en disco -> `None`, nunca una excepción.
8. Sellado manipulado -> `None` (I8, comprobado también al leer, no sólo al escribir).
"""
import json
import os
import sqlite3
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

TMP = tempfile.mkdtemp(prefix="archmuse_test_e2_")
os.environ["ARCHMUSE_DATA_DIR"] = TMP

from analyzer import parser, storage  # noqa: E402
from modelo import constructor  # noqa: E402

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

storage.init_db()
plano = parser.leer_plano(parser.load_document(DXF))


def _payload_minimo(nombre="ejemplo.dxf"):
    return {"archivo": nombre, "puntuacion_global": 90, "valoracion_global": "Notable",
            "viviendas": [{"nombre": "VT1/1", "svg": "<svg></svg>"}],
            "proyecto": {"ciudad": "Sevilla", "tipologia": "plurifamiliar"}}


def _estructura(grafo):
    """Todo lo que debe coincidir entre dos construcciones del mismo DXF,
    excepto identidad opaca (`concepto`) y el sellado que depende de ella.

    La geometria se compara redondeada a 3 decimales (milimetro) — la misma
    precision que persiste el formato de C7 — para que comparar un grafo
    recien construido contra uno reconstruido desde JSON (round-trip) sea una
    comprobacion real y no una que exige mas precision de la que el propio
    formato promete (ver cabecera de `modelo/serializacion.py`)."""
    espacios = [
        (e.id, e.rotulo, e.tipo.valor, e.tipo.estado, e.tipos_ambiguos,
         tuple((round(x, 3), round(y, 3))
               for x, y in grafo.almacen.bruta(e.geometrias["huella_2d"]).exterior.coords))
        for e in sorted(grafo.get_spaces(), key=lambda e: e.id)
    ]
    unidades = [
        (u.id, u.etiqueta.valor, u.espacios)
        for u in sorted(grafo.unidades(), key=lambda u: u.id)
    ]
    aristas = sorted(
        (a.tipo, a.a, a.b, round(a.separacion_m, 3), round(a.tramo_m, 3), round(a.distancia_m, 3))
        for a in grafo.aristas()
    )
    return espacios, unidades, aristas


print("=" * 70)
print("1. PERSISTENCIA Y RECUPERACION")
print("=" * 70)

grafo1 = constructor.construir(plano, fichero="ejemplo.dxf")
meta1 = storage.guardar_proyecto(_payload_minimo(), origen="dxf", grafo=grafo1)
pid1 = meta1["id"]

recuperado1 = storage.obtener_modelo(pid1)
check("obtener_modelo devuelve un grafo", recuperado1 is not None)
check("mismo sellado que el original (round-trip sin perdida)",
      recuperado1 is not None and recuperado1.sellado == grafo1.sellado)
# 40 y no 34 desde la correccion de cierre geometrico del 2026-08-13: seis
# polilineas de `ejemplo.dxf` traian el flag `closed` mal puesto y se
# descartaban enteras (ver `docs/audits/2026-08-13-hallazgos-cierre-
# geometrico.md` §0). El resto de la suite ya cuenta 40 -- este fichero se
# quedo con la cifra vieja porque se dejo en rojo a proposito.
check("mismo numero de espacios", recuperado1 is not None and
      len(recuperado1.get_spaces()) == len(grafo1.get_spaces()) == 40)
check("mismo numero de aristas", recuperado1 is not None and
      len(recuperado1.aristas()) == len(grafo1.aristas()))
check("mismo numero de unidades", recuperado1 is not None and
      len(recuperado1.unidades()) == len(grafo1.unidades()) == 6)
check("estructura identica (espacios/unidades/aristas)",
      recuperado1 is not None and _estructura(recuperado1) == _estructura(grafo1))

print()
print("=" * 70)
print("2. obtener_modelo() EN None")
print("=" * 70)

for malo in ["../../etc/passwd", "'; DROP TABLE proyectos; --", "", None,
             "ABCDEF123456", pid1 + "x"]:
    check("id invalido %r -> None" % (malo,), storage.obtener_modelo(malo) is None)

meta_sin_modelo = storage.guardar_proyecto(_payload_minimo("generado"), origen="generado", grafo=None)
check("proyecto sin grafo (origen=generado) -> obtener_modelo None",
      storage.obtener_modelo(meta_sin_modelo["id"]) is None)
check("pero obtener_proyecto SI funciona para ese mismo proyecto",
      storage.obtener_proyecto(meta_sin_modelo["id"]) is not None)

print()
print("=" * 70)
print("3. COMPATIBILIDAD HACIA ATRAS: fila de antes de E2")
print("=" * 70)

TMP_VIEJO = tempfile.mkdtemp(prefix="archmuse_test_e2_viejo_")
os.environ["ARCHMUSE_DATA_DIR"] = TMP_VIEJO
con = sqlite3.connect(storage.db_path())
con.execute(
    """
    CREATE TABLE proyectos (
        id TEXT PRIMARY KEY, nombre TEXT NOT NULL, origen TEXT NOT NULL,
        creado_en TEXT NOT NULL, modificado_en TEXT NOT NULL,
        puntuacion INTEGER, valoracion TEXT, num_viviendas INTEGER,
        ciudad TEXT, tipologia TEXT, miniatura TEXT, payload TEXT NOT NULL
    )
    """
)
payload_viejo = _payload_minimo("proyecto-antes-de-e2.dxf")
con.execute(
    "INSERT INTO proyectos (id, nombre, origen, creado_en, modificado_en, "
    "puntuacion, valoracion, num_viviendas, ciudad, tipologia, miniatura, payload) "
    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
    ("abc123abc123", "proyecto-antes-de-e2.dxf", "dxf", "2026-08-01T00:00:00+00:00",
     "2026-08-01T00:00:00+00:00", 80, "Notable", 1, "Sevilla", "plurifamiliar", None,
     json.dumps(payload_viejo, ensure_ascii=False)),
)
con.commit()
con.close()

columnas_antes = {f[1] for f in sqlite3.connect(storage.db_path())
                  .execute("PRAGMA table_info(proyectos)").fetchall()}
check("la base vieja NO tiene columna modelo (montaje del test)", "modelo" not in columnas_antes)

storage.init_db()  # aqui migra
columnas_despues = {f[1] for f in sqlite3.connect(storage.db_path())
                    .execute("PRAGMA table_info(proyectos)").fetchall()}
check("init_db() anade la columna modelo", "modelo" in columnas_despues)
check("la fila vieja sigue ahi", len(storage.listar_proyectos()) == 1)
recuperado_viejo = storage.obtener_proyecto("abc123abc123")
check("obtener_proyecto de la fila vieja funciona igual que siempre",
      recuperado_viejo is not None and recuperado_viejo.get("proyecto_id") is None)
check("obtener_modelo de la fila vieja -> None (columna NULL tras migrar)",
      storage.obtener_modelo("abc123abc123") is None)
check("init_db() otra vez es idempotente (no rompe la fila)",
      (storage.init_db(), len(storage.listar_proyectos()) == 1)[1])

os.environ["ARCHMUSE_DATA_DIR"] = TMP  # vuelve a la base de este test

print()
print("=" * 70)
print("4. AISLAMIENTO ENTRE PROYECTOS")
print("=" * 70)

grafo2 = constructor.construir(plano, fichero="ejemplo.dxf")  # segundo analisis, mismo DXF
meta2 = storage.guardar_proyecto(_payload_minimo(), origen="dxf", grafo=grafo2)
pid2 = meta2["id"]

check("dos filas distintas", pid1 != pid2)
recuperado2 = storage.obtener_modelo(pid2)
check("el segundo se recupera tambien", recuperado2 is not None)
check("misma estructura que el primero (mismo DXF)",
      recuperado2 is not None and _estructura(recuperado2) == _estructura(grafo1))
check("pero concept_id distinto (sin semilla, cada analisis es una version nueva)",
      recuperado2 is not None and recuperado2.proyecto.concepto != recuperado1.proyecto.concepto)
check("y por tanto sellado distinto",
      recuperado2 is not None and recuperado2.sellado != recuperado1.sellado)

check("borrar el primero no toca el segundo",
      storage.borrar_proyecto(pid1) is True and storage.obtener_modelo(pid2) is not None)
check("el primero ya no esta", storage.obtener_modelo(pid1) is None)

print()
print("=" * 70)
print("5. DETERMINISMO ESTRUCTURAL (C-E2.2)")
print("=" * 70)

grafo3 = constructor.construir(plano, fichero="ejemplo.dxf")
grafo4 = constructor.construir(plano, fichero="ejemplo.dxf")
check("misma estructura entre dos construcciones sucesivas",
      _estructura(grafo3) == _estructura(grafo4))
check("concept_id distinto entre las dos (C-E2.2: sin semilla, no se siembra "
      "con el id de storage)", grafo3.proyecto.concepto != grafo4.proyecto.concepto)
check("y por tanto el sellado tambien difiere (esperado, no un bug)",
      grafo3.sellado != grafo4.sellado)

print()
print("=" * 70)
print("6. EL PAYLOAD PUBLICO NO CAMBIA (C-E2.4)")
print("=" * 70)

payload_a = _payload_minimo()
payload_b = json.loads(json.dumps(payload_a))  # copia independiente
meta_a = storage.guardar_proyecto(payload_a, origen="dxf", grafo=constructor.construir(plano, fichero="x"))
meta_b = storage.guardar_proyecto(payload_b, origen="dxf", grafo=None)
recuperado_a = storage.obtener_proyecto(meta_a["id"])
recuperado_b = storage.obtener_proyecto(meta_b["id"])
del recuperado_a["proyecto_id"]
del recuperado_b["proyecto_id"]
check("el payload guardado CON grafo es identico al guardado SIN grafo",
      json.dumps(recuperado_a, sort_keys=True) == json.dumps(recuperado_b, sort_keys=True))
check("'modelo' no aparece dentro del payload (vive en su propia columna)",
      "modelo" not in recuperado_a and "modelo" not in recuperado_b)

print()
print("=" * 70)
print("7. MODELO CORRUPTO EN DISCO")
print("=" * 70)

grafo5 = constructor.construir(plano, fichero="ejemplo.dxf")
meta5 = storage.guardar_proyecto(_payload_minimo(), origen="dxf", grafo=grafo5)
con = sqlite3.connect(storage.db_path())
con.execute("UPDATE proyectos SET modelo = ? WHERE id = ?", ("{esto no es json", meta5["id"]))
con.commit()
con.close()
check("modelo ilegible -> None, no excepcion", storage.obtener_modelo(meta5["id"]) is None)
check("pero el proyecto sigue en la lista", meta5["id"] in [p["id"] for p in storage.listar_proyectos()])

print()
print("=" * 70)
print("8. SELLADO MANIPULADO (I8 tambien se comprueba al leer)")
print("=" * 70)

grafo6 = constructor.construir(plano, fichero="ejemplo.dxf")
meta6 = storage.guardar_proyecto(_payload_minimo(), origen="dxf", grafo=grafo6)
con = sqlite3.connect(storage.db_path())
fila = con.execute("SELECT modelo FROM proyectos WHERE id = ?", (meta6["id"],)).fetchone()
datos = json.loads(fila[0])
datos["proyecto"]["escala"]["valor"] = 999.0  # cambia contenido, NO el sellado
con.execute("UPDATE proyectos SET modelo = ? WHERE id = ?",
            (json.dumps(datos, ensure_ascii=False), meta6["id"]))
con.commit()
con.close()
check("sellado ya no describe el contenido -> obtener_modelo devuelve None",
      storage.obtener_modelo(meta6["id"]) is None)

print()
print("=" * 70)
if fallos:
    print("FALLOS (%d de %d): %s" % (len(fallos), comprobaciones, ", ".join(fallos)))
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
