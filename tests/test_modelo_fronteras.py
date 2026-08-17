# -*- coding: utf-8 -*-
"""E1.1 — Las fronteras de `modelo/`, comprobadas sobre los imports reales.

Ejecutar:  python tests/test_modelo_fronteras.py

Mismo patrón que `tests/test_normativa_fronteras.py`,
`test_ingesta_fronteras.py` y `test_extraccion_fronteras.py`, que ya vigilan
las tres fronteras existentes del repositorio. Se analiza el AST, no el texto:
buscar palabras en el fuente daba falsos positivos con los docstrings, y estos
módulos hablan mucho de lo que no hacen.

Seis fronteras, y cada una tiene un motivo concreto:

1. **Ningún módulo de `modelo/` importa `ezdxf`.** El modelo no sabe que
   existe un DXF. Es lo que permitirá que un IFC entre por otro lector sin que
   ninguna regla se entere (principio P6).
2. **`shapely` sólo en `geometria.py`.** Es el único punto autorizado a tocar
   geometría bruta; los nodos exponen derivados, no polígonos.
3. **`analyzer.parser`/`evaluator`/`adyacencia` sólo en `constructor.py` y
   `compat.py`.** Son las dos aduanas con el sustrato actual, declaradas y
   temporales.
4. **CAP-1…CAP-5 no se importan desde `modelo/`.** La dependencia va del
   modelo al hecho y nunca al revés: el puente es `Atributo.a_hecho()`.
5. **`experimentos/` no se importa desde producción.** El experimento se
   conserva como evidencia (G7), no como dependencia accidental.
6. **Ningún campo con nombre de formato fuera de `Procedencia`, y ningún
   campo evaluativo en ningún nodo.** Es la §0.1 de `KNOWLEDGE_GRAPH.md`
   hecha comprobación en vez de recomendación.
"""
import ast
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

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


DIR_MODELO = os.path.join(RAIZ, "modelo")
MODULOS = sorted(f for f in os.listdir(DIR_MODELO) if f.endswith(".py"))

# Aduanas con el sustrato actual (frontera 3).
ADUANAS = {"constructor.py", "compat.py"}
# Único módulo autorizado a tocar geometría bruta (frontera 2).
GEOMETRIA = {"geometria.py"}

CAP_CERRADOS = {
    "superficie_util", "uso_previsto", "ocupacion", "planta", "sectorizacion",
    "altura_evacuacion", "avisos_altura_evacuacion",
}


def importaciones(ruta):
    """(modulo_raiz, nombre_completo) de cada import del fichero."""
    with open(ruta, encoding="utf-8") as fh:
        arbol = ast.parse(fh.read(), filename=ruta)
    nombres = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                nombres.add((alias.name.split(".")[0], alias.name))
        elif isinstance(nodo, ast.ImportFrom):
            modulo = nodo.module or ""
            raiz = modulo.split(".")[0] if nodo.level == 0 else ""
            nombres.add((raiz, modulo))
    return nombres


print("=" * 74)
print("FRONTERAS DE modelo/  (%d modulos)" % len(MODULOS))
print("=" * 74)

print("\n1. Ningun modulo de modelo/ importa ezdxf")
for nombre in MODULOS:
    imports = importaciones(os.path.join(DIR_MODELO, nombre))
    check(not any(r == "ezdxf" for r, _ in imports),
          "modelo/%s no importa ezdxf" % nombre)

print("\n2. shapely solo en geometria.py")
for nombre in MODULOS:
    imports = importaciones(os.path.join(DIR_MODELO, nombre))
    usa = any(r == "shapely" for r, _ in imports)
    check(usa == (nombre in GEOMETRIA) or (not usa and nombre not in GEOMETRIA),
          "modelo/%s %s shapely" % (nombre, "puede usar" if nombre in GEOMETRIA
                                    else "no usa"))

print("\n3. analyzer.parser / evaluator / adyacencia solo en las aduanas")
SUSTRATO = {"parser", "evaluator", "adyacencia"}
for nombre in MODULOS:
    imports = importaciones(os.path.join(DIR_MODELO, nombre))
    tocados = set()
    for raiz, completo in imports:
        if raiz != "analyzer":
            continue
        partes = completo.split(".")
        # `from analyzer import evaluator, parser` -> el modulo va en names,
        # que `importaciones` no distingue; se cubre con el fuente mas abajo.
        tocados |= SUSTRATO & set(partes)
    if nombre not in ADUANAS:
        check(not tocados, "modelo/%s no importa el sustrato actual" % nombre,
              "toca: %s" % sorted(tocados) if tocados else "")

# `from analyzer import evaluator` no deja el nombre en `nodo.module`, asi que
# se comprueba tambien sobre los alias importados.
print("\n3bis. Idem, mirando los nombres importados (from analyzer import X)")
for nombre in MODULOS:
    if nombre in ADUANAS:
        continue
    with open(os.path.join(DIR_MODELO, nombre), encoding="utf-8") as fh:
        arbol = ast.parse(fh.read())
    colados = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and (nodo.module or "") == "analyzer":
            colados |= SUSTRATO & {a.name for a in nodo.names}
    check(not colados, "modelo/%s no trae parser/evaluator/adyacencia" % nombre,
          "colados: %s" % sorted(colados) if colados else "")

print("\n4. CAP-1..CAP-5 no se importan desde modelo/ (solo hechos.py)")
for nombre in MODULOS:
    with open(os.path.join(DIR_MODELO, nombre), encoding="utf-8") as fh:
        arbol = ast.parse(fh.read())
    colados = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom):
            modulo = nodo.module or ""
            colados |= CAP_CERRADOS & set(modulo.split("."))
            if modulo == "analyzer":
                colados |= CAP_CERRADOS & {a.name for a in nodo.names}
        elif isinstance(nodo, ast.Import):
            for alias in nodo.names:
                colados |= CAP_CERRADOS & set(alias.name.split("."))
    check(not colados, "modelo/%s no importa CAP-1..CAP-5" % nombre,
          "colados: %s" % sorted(colados) if colados else "")

print("\n5. experimentos/ no se importa desde produccion")
PRODUCCION = []
for carpeta in ("modelo", "analyzer", "normativa", "ingesta", "extraccion", "herramientas"):
    base = os.path.join(RAIZ, carpeta)
    if not os.path.isdir(base):
        continue
    for actual, _dirs, ficheros in os.walk(base):
        if "__pycache__" in actual:
            continue
        PRODUCCION += [os.path.join(actual, f) for f in ficheros if f.endswith(".py")]
PRODUCCION.append(os.path.join(RAIZ, "app.py"))
PRODUCCION.append(os.path.join(RAIZ, "main.py"))

culpables = []
for ruta in PRODUCCION:
    if not os.path.exists(ruta):
        continue
    if any(r == "experimentos" for r, _ in importaciones(ruta)):
        culpables.append(os.path.relpath(ruta, RAIZ))
check(not culpables, "ningun modulo de produccion importa experimentos/",
      "culpables: %s" % culpables if culpables else "%d ficheros revisados" % len(PRODUCCION))

print("\n6. Nodos: ni campos evaluativos ni nombres de formato")
from modelo import nodos  # noqa: E402

import dataclasses  # noqa: E402

CLASES = [nodos.Proyecto, nodos.Edificio, nodos.Planta, nodos.Unidad, nodos.Espacio]
for clase in CLASES:
    campos = {f.name for f in dataclasses.fields(clase)}
    evaluativos = sorted(campos & set(nodos.LISTA_NEGRA))
    check(not evaluativos, "%s sin campos evaluativos" % clase.__name__,
          "prohibidos presentes: %s" % evaluativos if evaluativos else "")
    formato = sorted(campos & set(nodos.NOMBRES_DE_FORMATO))
    check(not formato, "%s sin campos con nombre de formato" % clase.__name__,
          "presentes: %s" % formato if formato else "")

campos_proc = {f.name for f in dataclasses.fields(nodos.Procedencia)}
check("capa" in campos_proc,
      "Procedencia es quien lleva 'capa' (el unico sitio admitido)")

print("\n7. El catalogo de presencia cubre los once tipos")
check(len(nodos.CATALOGO) == 11, "el catalogo tiene 11 tipos",
      "tiene %d" % len(nodos.CATALOGO))
check(len(nodos.MATERIALIZADOS) == 5, "5 tipos materializados en E1",
      "%s" % (nodos.MATERIALIZADOS,))

print()
print("=" * 74)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
