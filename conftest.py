# -*- coding: utf-8 -*-
"""Configuración de pytest para todo el repositorio.

Este fichero existe por tres motivos concretos, y no hace nada más.

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

3. **El `.env` local.** Se carga aquí para que `.env` signifique lo mismo
   bajo pytest que al arrancar `app.py` — la alternativa, que funcionara en
   la app pero no en la suite, convierte el bloque de tests de
   `.env.example` en una trampa silenciosa. Como entra en `os.environ`, los
   scripts del punto 2 lo heredan al lanzarse en subprocesos.

   Con una consecuencia que conviene tener presente: `ARCHMUSE_TEST_RED=1`
   o `ARCHMUSE_TEST_IA=1` en un `.env` olvidado hacen que la suite golpee
   boe.es, el Catastro y la API real de Anthropic. Son las dos únicas
   variables con las que un `.env` cambia lo que la suite hace, y las dos
   llevan el aviso al lado en `.env.example`.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Después de tocar sys.path, que es lo que hace importable `analyzer`.
from analyzer.entorno import cargar_dotenv  # noqa: E402

cargar_dotenv()

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


#: Scripts que fallan por un defecto **conocido, localizado y aceptado por
#: escrito**, no por una regresión. Se marcan `xfail(strict=True)`: mientras el
#: defecto siga ahí no ensucian el resultado, y **el día que se corrija pytest
#: falla con XPASS** y obliga a quitar la marca. Es la única forma de que un
#: rojo permanente no acabe normalizando todos los rojos.
#:
#: Requisito para entrar aquí: existir un documento que diga qué defecto es y
#: por qué se decidió no corregirlo. Una marca sin esa referencia es tapar.
#:
#: Coste, dicho claro: la marca es por FICHERO, no por comprobación. En
#: `test_e2_persistencia.py` fallan 3 de 35, y sus otras 32 dejan de avisar
#: mientras la marca esté puesta. Ese coste ya lo pagaba el fichero estando en
#: rojo permanente (un fallo nuevo tampoco se habría visto); la marca al menos
#: añade el aviso de cuándo se puede retirar.
#: **Vacío desde el 2026-08-18, y el mecanismo funcionó exactamente como se
#: diseñó.** Tenía dos entradas, `test_golden_modelo.py` y
#: `test_e2_persistencia.py`, las dos por el defecto H1. Al corregirlo (tarea
#: F0-1 del plan de migración: `modelo/geometria.py::_canonica`), pytest las
#: rompió con `XPASS(strict)` y obligó a retirarlas — que es justo el aviso
#: para el que existe esta tabla. Sus 35 y sus 9 comprobaciones vuelven a
#: avisar.
ROJOS_CONOCIDOS = {}


def pytest_generate_tests(metafunc):
    """Da a `test_script_legacy` un caso por script, con el nombre del fichero
    como id — para que el informe de pytest se lea como una lista de ficheros y
    no como un test opaco que agrupa setenta y tantos."""
    if "script_legacy" not in metafunc.fixturenames:
        return

    casos = []
    for ruta in SCRIPTS_LEGACY:
        motivo = ROJOS_CONOCIDOS.get(ruta.name)
        marcas = [pytest.mark.xfail(reason=motivo, strict=True)] if motivo else []
        casos.append(pytest.param(ruta, marks=marcas, id=ruta.name))

    metafunc.parametrize("script_legacy", casos)
