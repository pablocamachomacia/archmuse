"""Frontera de `ingesta/`, mismo patrón de vigilancia que
`test_normativa_fronteras.py`.

`ingesta/` produce documentos oficiales en bruto, no reglas: no tiene ningún
motivo para conocer el motor de resolución territorial ni el evaluador de
planos, y ninguno de los dos debe depender de un pipeline de descarga para
funcionar. Las cuatro direcciones se prohíben — no hay ningún acoplamiento
autorizado hoy, a diferencia de `normativa`/`analyzer` (que sí tienen la
fachada de `cte_zonas.py`).
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


def _imports(ruta: Path, paquete_propio: str):
    """`paquete_propio` es el paquete al que pertenece `ruta` (`"ingesta"`,
    `"normativa"`, `"analyzer"`) — un import relativo (`from . import red`)
    solo puede referirse a MÓDULOS DEL MISMO PAQUETE, nunca a otro; resolverlo
    siempre contra un nombre fijo fue un bug real de este test la primera vez
    que se escribió (`from . import parser` en `analyzer/` se leía como
    "importa ingesta.parser")."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for a in nodo.names:
                yield a.name
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level == 0 and nodo.module:
                yield nodo.module
            elif nodo.level and nodo.module:
                yield paquete_propio + "." + nodo.module


def _paquete_no_importa(paquete: str, prohibidos: set) -> list:
    fallos = []
    for py in sorted((RAIZ / paquete).rglob("*.py")):
        for mod in _imports(py, paquete):
            raiz_mod = mod.split(".")[0]
            if raiz_mod in prohibidos:
                fallos.append(f"{py.relative_to(RAIZ)} importa {mod}")
    return fallos


def test_ingesta_no_importa_normativa_ni_analyzer():
    """`ingesta/` se prueba entero contra fixtures grabados: no necesita
    saber resolver ámbitos ni evaluar un DXF para descargar un documento y
    detectar si cambió."""
    fallos = _paquete_no_importa("ingesta", {"normativa", "analyzer"})
    assert not fallos, "ingesta/ no puede depender de normativa/ ni analyzer/:\n  " + "\n  ".join(fallos)


def test_normativa_no_importa_ingesta():
    """La prohibición dura ya existente (`normativa/` no importa `analyzer/`)
    se extiende a `ingesta/`: el motor de resolución no sabe nada de cómo
    llegó un documento al disco, solo lee YAML ya curado."""
    fallos = _paquete_no_importa("normativa", {"ingesta"})
    assert not fallos, "normativa/ no puede depender de ingesta/:\n  " + "\n  ".join(fallos)


def test_analyzer_no_importa_ingesta():
    """Tampoco `analyzer/`: el evaluador de planos no descarga nada."""
    fallos = _paquete_no_importa("analyzer", {"ingesta"})
    assert not fallos, "analyzer/ no puede depender de ingesta/:\n  " + "\n  ".join(fallos)


def test_ingesta_nunca_escribe_dentro_de_normativa():
    """No es un test de imports (ya cubierto arriba): es un test de que
    ningún módulo de `ingesta/` construye, en CÓDIGO, una ruta hacia
    `normativa/`. Se mira solo literales de cadena que no sean docstrings
    (mismo criterio que `test_normativa_fronteras.test_f1_...`) — mencionar
    "normativa" en un comentario explicando por qué NO se escribe ahí (como
    hacen varios docstrings de este mismo paquete) es honesto y no debe
    contar como violación; construir la ruta de verdad sí."""
    fallos = []
    for py in sorted((RAIZ / "ingesta").rglob("*.py")):
        arbol = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        docstrings = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(nodo, clean=False)
                if doc:
                    docstrings.add(doc)
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                if nodo.value in docstrings:
                    continue
                if "normativa" in nodo.value.lower():
                    fallos.append(f"{py.relative_to(RAIZ)}: {nodo.value.strip()[:60]!r}")
    assert not fallos, "ingesta/ referencia «normativa» fuera de un docstring:\n  " + "\n  ".join(fallos)


if __name__ == "__main__":
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print(f"OK  {nombre}")
    print("\nFronteras de ingesta/ respetadas.")
