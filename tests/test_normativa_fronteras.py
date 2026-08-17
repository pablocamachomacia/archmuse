"""Las tres fronteras de `docs/design/NORMATIVE_RESOLUTION.md` §2.

Una arquitectura desacoplada que no tiene quien la vigile deja de estarlo en
tres commits. Estos tests son esa vigilancia.

    F1  La capa de ejecución no conoce territorio.
    F2  La capa de datos no contiene lógica.
    F3  (se comprueba en test_normativa_validacion.py: la jerarquía no se
        inventa, se declara en competencias.yaml)

CORRECCIÓN AL CRITERIO DE ACEPTACIÓN 4 DEL PRD. El PRD pedía un test que
fallara si `analyzer/` importaba `normativa/` Y otro que fallara si
`normativa/` importaba `analyzer/`. Es contradictorio con la tarea 12 del
propio PRD, que manda dejar `cte_zonas.py` como fachada sobre los datos
migrados — eso exige que `analyzer/` importe `normativa/`. La regla
arquitectónicamente significativa, y la que dice el documento de diseño §11,
es de UN SOLO SENTIDO:

    normativa/ NUNCA importa analyzer/        <- prohibición dura
    analyzer/  puede importar normativa/      <- solo por su superficie pública

Lo segundo se vigila con una lista explícita de quién importa qué, para que el
acoplamiento crezca a propósito y no por descuido.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# Superficie pública de `normativa/` que `analyzer/` puede consumir.
SUPERFICIE_PUBLICA = {"normativa.api", "normativa.derivados", "normativa.registro", "normativa.errores"}

# Módulos de `analyzer/` autorizados a importar `normativa/`, y por qué.
# Ampliar esta lista es una decisión de arquitectura, no un detalle.
ACOPLAMIENTO_AUTORIZADO = {
    "cte_zonas.py": "fachada sobre los derivados migrados (tarea 12 del PRD)",
}


def _imports(ruta: Path):
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for a in nodo.names:
                yield a.name
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level == 0 and nodo.module:
                yield nodo.module


def test_normativa_no_importa_analyzer():
    """Prohibición dura. `normativa/` se prueba entero sin un DXF: si un día
    importa el parser, deja de ser cierto y el subsistema deja de ser
    reutilizable fuera de este pipeline."""
    fallos = []
    for py in sorted((RAIZ / "normativa").rglob("*.py")):
        for mod in _imports(py):
            if mod.split(".")[0] == "analyzer":
                fallos.append(f"{py.relative_to(RAIZ)} importa {mod}")
    assert not fallos, "normativa/ no puede depender de analyzer/:\n  " + "\n  ".join(fallos)


def test_analyzer_solo_usa_la_superficie_publica():
    """`analyzer/` puede consumir `normativa/`, pero solo por su superficie
    pública y solo desde módulos autorizados. Importar `normativa.loader` o
    `normativa.validacion` desde el evaluador sería saltarse la frontera."""
    fallos = []
    for py in sorted((RAIZ / "analyzer").rglob("*.py")):
        usados = [m for m in _imports(py) if m.split(".")[0] == "normativa"]
        if not usados:
            continue
        if py.name not in ACOPLAMIENTO_AUTORIZADO:
            fallos.append(f"{py.name} importa normativa/ sin estar autorizado: {usados}")
            continue
        for mod in usados:
            if mod not in SUPERFICIE_PUBLICA:
                fallos.append(f"{py.name} importa {mod}, que no es superficie pública")
    assert not fallos, "\n  ".join([""] + fallos)


def test_f2_la_capa_de_datos_no_contiene_logica():
    """F2: ningún `.py` dentro de los subárboles de datos.

    El día que aparezca un `.py` en `normativa/es/`, la promesa de "añadir un
    municipio no toca código" habrá dejado de ser cierta sin que nadie lo
    anuncie.
    """
    from normativa.loader import DIRECTORIOS_DE_DATOS

    fallos = []
    for sub in DIRECTORIOS_DE_DATOS:
        d = RAIZ / "normativa" / sub
        if d.is_dir():
            fallos += [str(p.relative_to(RAIZ)) for p in d.rglob("*.py")]
    assert not fallos, "La capa de datos no puede contener lógica:\n  " + "\n  ".join(fallos)


def test_f1_el_evaluador_no_conoce_territorio():
    """F1: `evaluator.py` no razona sobre territorio.

    Es la frontera que el encargo pide literalmente: "todo ello sin que
    evaluator.py conozca nada sobre municipios concretos".

    Se mira el CÓDIGO, no los comentarios: que un docstring explique que un
    umbral varía según el municipio es información honesta y debe poder
    escribirse. Lo prohibido es un identificador o un literal que haga al
    evaluador depender de un territorio concreto.
    """
    from normativa.registro import registro

    arbol = ast.parse((RAIZ / "analyzer" / "evaluator.py").read_text(encoding="utf-8"))

    identificadores = set()
    literales = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Name):
            identificadores.add(nodo.id.lower())
        elif isinstance(nodo, ast.arg):
            identificadores.add(nodo.arg.lower())
        elif isinstance(nodo, ast.Attribute):
            identificadores.add(nodo.attr.lower())
        elif isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            literales.add(nodo.value.lower())

    # Los docstrings son constantes de cadena: se descartan explícitamente.
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(nodo, clean=False)
            if doc:
                literales.discard(doc.lower())

    prohibidos = {"municipio", "municipios", "comunidad", "comunidad_autonoma", "ccaa", "codigo_ine"}
    en_codigo = prohibidos & identificadores
    assert not en_codigo, f"evaluator.py tiene identificadores territoriales: {sorted(en_codigo)}"

    nombres_municipio = {m["nombre"].lower() for m in registro().municipios.values()}
    citados = {lit for lit in literales if lit in nombres_municipio}
    assert not citados, f"evaluator.py cita municipios concretos: {sorted(citados)}"


if __name__ == "__main__":
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith("test_"):
            fn()
            print(f"OK  {nombre}")
    print("\nFronteras respetadas.")
