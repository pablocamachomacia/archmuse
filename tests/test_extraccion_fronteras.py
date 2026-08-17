"""Frontera de `extraccion/`, mismo patrón de vigilancia que
`test_normativa_fronteras.py` y `test_ingesta_fronteras.py`.

A diferencia de `ingesta/`, `extraccion/` SÍ está autorizado a importar de
`normativa/` — pero solo tres módulos de vocabulario cerrado
(`normativa.modelo`, `normativa.catalogos`, `normativa.condiciones`), nunca
el loader, el validador, el registro ni el resolver. Es la misma clase de
excepción que ya tiene `analyzer/cte_zonas.py`, con su propia lista acotada
en vez de la de aquél.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# Único vocabulario que `extraccion/` puede leer de `normativa/` — nunca
# `.loader`, `.validacion`, `.registro`, `.resolucion`, `.manifiesto`,
# `.ambito`, `.api`: ninguno de ellos es catálogo cerrado, todos son lógica
# de resolución o carga que este paquete no necesita y no debe acoplar.
NORMATIVA_AUTORIZADO = {"normativa.modelo", "normativa.catalogos", "normativa.condiciones"}

# Único módulo de `ingesta/` que `extraccion/` puede leer — la forma de su
# resultado (`DocumentoOficial`), nunca cómo se obtuvo.
INGESTA_AUTORIZADO = {"ingesta.modelo"}


def _imports(ruta: Path, paquete_propio: str):
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


def test_extraccion_no_importa_analyzer():
    fallos = []
    for py in sorted((RAIZ / "extraccion").rglob("*.py")):
        for mod in _imports(py, "extraccion"):
            if mod.split(".")[0] == "analyzer":
                fallos.append(f"{py.relative_to(RAIZ)} importa {mod}")
    assert not fallos, "extraccion/ no puede depender de analyzer/:\n  " + "\n  ".join(fallos)


def test_extraccion_solo_usa_el_vocabulario_cerrado_de_normativa():
    fallos = []
    for py in sorted((RAIZ / "extraccion").rglob("*.py")):
        for mod in _imports(py, "extraccion"):
            if mod == "normativa" or mod.startswith("normativa."):
                if mod not in NORMATIVA_AUTORIZADO:
                    fallos.append(f"{py.relative_to(RAIZ)} importa {mod}, fuera del vocabulario autorizado")
    assert not fallos, "\n  ".join([""] + fallos)


def test_extraccion_solo_usa_el_tipo_de_dato_de_ingesta():
    fallos = []
    for py in sorted((RAIZ / "extraccion").rglob("*.py")):
        for mod in _imports(py, "extraccion"):
            if mod == "ingesta" or mod.startswith("ingesta."):
                if mod not in INGESTA_AUTORIZADO:
                    fallos.append(f"{py.relative_to(RAIZ)} importa {mod}, fuera de lo autorizado")
    assert not fallos, "\n  ".join([""] + fallos)


def test_nadie_importa_extraccion():
    """Ni `normativa/`, ni `ingesta/`, ni `analyzer/` dependen de
    `extraccion/` — es la hoja del árbol, no un módulo que otros consuman
    todavía. El día que la Fase 5 (promoción) exista, ese acoplamiento se
    autorizará explícitamente aquí, no aparecerá sin que este test lo note."""
    fallos = []
    for paquete in ("normativa", "ingesta", "analyzer"):
        for py in sorted((RAIZ / paquete).rglob("*.py")):
            for mod in _imports(py, paquete):
                if mod == "extraccion" or mod.startswith("extraccion."):
                    fallos.append(f"{py.relative_to(RAIZ)} importa {mod}")
    assert not fallos, "\n  ".join([""] + fallos)


# Única excepción a "extraccion/ no escribe": `almacen.py`, y por una única
# razón declarada — persistir las candidatas pendientes de revisión en
# `extraccion/estado/` (nunca en `normativa/es/`, ver su propio docstring).
# Todo lo demás en el paquete (segmentación, interpretación, verificación,
# confianza) sigue prohibido de escribir, sin excepción.
_AUTORIZADO_A_ESCRIBIR = {"almacen.py"}


def test_extraccion_nunca_escribe_ficheros():
    """`extraccion/` (salvo `almacen.py`, ver `_AUTORIZADO_A_ESCRIBIR`)
    devuelve objetos Python (`ReglaCandidata`); no persiste nada por su
    cuenta. Es una comprobación estructural, no solo de intención: si algún
    día alguien añade una escritura a disco en la lógica de extracción en
    sí, es justo el punto en el que un candidato de IA podría acabar
    escrito donde `normativa/loader.py` lo descubriera — la promoción tiene
    que seguir siendo un paso humano y explícito."""
    fallos = []
    llamadas_de_escritura = {"write_text", "write_bytes", "write", "dump", "safe_dump"}
    for py in sorted((RAIZ / "extraccion").rglob("*.py")):
        if py.name in _AUTORIZADO_A_ESCRIBIR:
            continue
        arbol = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Attribute) and nodo.attr in llamadas_de_escritura:
                fallos.append(f"{py.relative_to(RAIZ)}: llamada a .{nodo.attr}(...)")
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id == "open":
                args_texto = [a.value for a in nodo.args if isinstance(a, ast.Constant)]
                if "w" in args_texto or any(isinstance(a, ast.Constant) and "w" in str(a.value) for a in nodo.keywords):
                    fallos.append(f"{py.relative_to(RAIZ)}: open(..., modo de escritura)")
    assert not fallos, "extraccion/ no debería escribir ficheros:\n  " + "\n  ".join(fallos)


def test_almacen_nunca_escribe_en_normativa_ni_en_ingesta():
    """La única excepción a "extraccion/ no escribe" (`almacen.py`) tiene su
    propia frontera: solo escribe bajo su propio `estado/`. El propio
    docstring del módulo evita a propósito la cadena literal "normativa/es"
    (la nombra con un espacio de por medio) para que esta comprobación de
    texto simple no confunda la prosa que explica la frontera con una ruta
    real construida en el código."""
    texto = (RAIZ / "extraccion" / "almacen.py").read_text(encoding="utf-8")
    assert "normativa/es" not in texto and "normativa\\es" not in texto, (
        "almacen.py no debería mencionar normativa/es/ — ver su docstring de frontera"
    )


if __name__ == "__main__":
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print(f"OK  {nombre}")
    print("\nFronteras de extraccion/ respetadas.")
