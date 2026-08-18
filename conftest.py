# -*- coding: utf-8 -*-
"""Configuración de pytest para todo el repositorio.

Este fichero existe por dos motivos concretos, y no hace nada más.

1. **`sys.path`.** Los tests importan `analyzer`, `modelo`, `normativa`,
   `ingesta` y `app` como paquetes de primer nivel. Con un `conftest.py` en la
   raíz, pytest (modo de import `prepend`) inserta esta carpeta en `sys.path`
   antes de importar nada — que es exactamente lo que los scripts de `tests/`
   ya hacían a mano con `sys.path.insert(0, RAIZ)`. Se hace además explícito
   abajo para que un cambio futuro del modo de import no lo rompa en silencio.

2. **Los ficheros de `tests/` que no son tests de pytest.** La mayor parte de
   `tests/` se escribió como scripts: ejecutan sus comprobaciones a nivel de
   módulo (nada dentro de funciones `test_*`) y comunican el resultado con
   `sys.exit(0|1)`. Recolectarlos es importarlos, importarlos es ejecutarlos, y
   su `sys.exit(1)` aborta la recolección entera de pytest con un
   `INTERNALERROR` — que es exactamente el estado del que parte esta fase.

   Aquí se detectan **por su forma** (con `ast`, sin importarlos: importar es
   justo lo que todavía no se puede hacer) y se apartan de la recolección
   normal. `tests/test_scripts_legacy.py` los ejecuta después uno a uno como el
   proceso independiente que siempre fueron, y traduce su código de salida a un
   resultado de pytest.

   Ninguno de esos scripts se modifica. Su lógica de comprobación es la que
   es; lo único que cambia es que ahora alguien los ejecuta todos y suma.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

DIR_TESTS = RAIZ / "tests"


def _declara_tests_de_pytest(ruta: Path) -> bool:
    """¿Declara este fichero algo que pytest pueda recolectar — una función
    `test*` o una clase `Test*` de primer nivel?

    Se responde leyendo el AST, nunca importando el módulo. Un fichero que no
    se deja parsear se declara recolectable a propósito: así su error real
    (`SyntaxError`) aparece en la recolección de pytest en vez de quedar
    escondido detrás de esta heurística.
    """
    try:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return True
    for nodo in arbol.body:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) and nodo.name.startswith("test"):
            return True
        if isinstance(nodo, ast.ClassDef) and nodo.name.startswith("Test"):
            return True
    return False


def _scripts_legacy() -> list[Path]:
    if not DIR_TESTS.is_dir():
        return []
    return sorted(
        ruta
        for ruta in DIR_TESTS.glob("test_*.py")
        if not _declara_tests_de_pytest(ruta)
    )


SCRIPTS_LEGACY = _scripts_legacy()

# Se apartan de la recolección normal (importarlos = ejecutarlos). Los ejecuta
# `tests/test_scripts_legacy.py`, que sí es un test de pytest de verdad.
collect_ignore = [str(ruta) for ruta in SCRIPTS_LEGACY]


def pytest_generate_tests(metafunc):
    """Da a `test_script_legacy` un caso por script, con el nombre del fichero
    como id — para que el informe de pytest se lea como una lista de ficheros y
    no como un test opaco que agrupa setenta y tantos."""
    if "script_legacy" in metafunc.fixturenames:
        metafunc.parametrize(
            "script_legacy",
            SCRIPTS_LEGACY,
            ids=[ruta.name for ruta in SCRIPTS_LEGACY],
        )
