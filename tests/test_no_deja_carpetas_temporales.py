# -*- coding: utf-8 -*-
"""Guardián: la suite no deja carpetas `archmuse_test_*` en `%TEMP%`.

**Por qué (2026-09-15).** Había 6.009, desde el 2 de agosto: treinta y un
ficheros de tests creaban una al importarse y ninguno la borraba. Ahora las pide
`tests/_carpetas_temporales.py`, que borra las suyas al terminar.

Tres comprobaciones, de la más barata a la más real:

1. Ningún fichero de `tests/` crea una carpeta `archmuse_test_*` por su cuenta.
2. Un proceso que crea carpetas **y revienta** no deja ninguna.
3. Una sesión de pytest **con un test en rojo** no deja ninguna.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TESTS = RAIZ / "tests"
DIRECTA = re.compile(r"""mkdtemp\(\s*prefix\s*=\s*["']archmuse_test_""")


def test_ningun_test_crea_una_carpeta_archmuse_test_por_su_cuenta():
    culpables = [r.name for r in sorted(TESTS.glob("*.py"))
                 if r.name != "_carpetas_temporales.py"
                 and DIRECTA.search(r.read_text(encoding="utf-8"))]
    assert culpables == [], (
        "crean carpetas archmuse_test_* sin borrarlas: %s. Usa "
        "`_carpetas_temporales.carpeta_temporal_de_test`" % culpables)


def _entorno():
    entorno = dict(os.environ)
    entorno["PYTHONPATH"] = os.pathsep.join([str(TESTS), str(RAIZ)])
    return entorno


def test_un_proceso_que_revienta_no_deja_sus_carpetas(tmp_path):
    guion = tmp_path / "revienta.py"
    guion.write_text(
        "import sqlite3\n"
        "from _carpetas_temporales import carpeta_temporal_de_test\n"
        "for n in range(2):\n"
        "    d = carpeta_temporal_de_test('archmuse_test_guardian_')\n"
        "    print(d, flush=True)\n"
        "    sqlite3.connect(d + '/archmuse.db').execute('create table t (x)')\n"
        "raise SystemExit('el script falla a propósito')\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(guion)], capture_output=True, text=True,
                       env=_entorno(), timeout=120)
    carpetas = [l.strip() for l in r.stdout.splitlines() if "archmuse_test_guardian_" in l]
    assert r.returncode != 0 and len(carpetas) == 2, (r.returncode, r.stdout, r.stderr)
    assert [c for c in carpetas if os.path.exists(c)] == []


def test_una_conexion_sqlite_que_se_queda_abierta_no_impide_borrar(tmp_path):
    """Medido el 2026-09-15: tras la suite quedó `archmuse_test_interview_api_*`
    con su `archmuse.db`. Ese script hace `with storage._connect() as _conn19:`,
    y en SQLite el `with` no cierra la conexión: se queda abierta en una global,
    y en Windows un fichero abierto no se borra. `gc.collect` no la cierra porque
    alguien la sigue apuntando."""
    guion = tmp_path / "conexion_abierta.py"
    guion.write_text(
        "import sqlite3\n"
        "from _carpetas_temporales import carpeta_temporal_de_test\n"
        "d = carpeta_temporal_de_test('archmuse_test_guardian_sqlite_')\n"
        "print(d, flush=True)\n"
        "with sqlite3.connect(d + '/archmuse.db') as _conn:\n"
        "    _conn.execute('create table t (x)')\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(guion)], capture_output=True, text=True,
                       env=_entorno(), timeout=120)
    carpetas = [l.strip() for l in r.stdout.splitlines() if "archmuse_test_guardian_sqlite_" in l]
    assert r.returncode == 0 and carpetas, (r.returncode, r.stdout, r.stderr)
    assert [c for c in carpetas if os.path.exists(c)] == []


def test_una_sesion_de_pytest_con_un_test_en_rojo_no_deja_sus_carpetas(tmp_path):
    prueba = tmp_path / "test_en_rojo.py"
    prueba.write_text(
        "from _carpetas_temporales import carpeta_temporal_de_test\n"
        "CARPETA = carpeta_temporal_de_test('archmuse_test_guardian_pytest_')\n"
        "print('CARPETA=' + CARPETA)\n"
        "def test_falla():\n"
        "    assert False, 'en rojo a propósito'\n", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-s", "-p", "no:cacheprovider",
         "--rootdir", str(tmp_path), str(prueba)],
        capture_output=True, text=True, env=_entorno(), cwd=str(tmp_path), timeout=180)
    carpetas = [l.split("=", 1)[1].strip() for l in r.stdout.splitlines() if l.startswith("CARPETA=")]
    assert r.returncode == 1 and carpetas, (r.returncode, r.stdout[-800:], r.stderr[-800:])
    assert [c for c in carpetas if os.path.exists(c)] == []
