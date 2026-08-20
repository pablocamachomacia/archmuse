# -*- coding: utf-8 -*-
"""Mide la cobertura real de la suite -- contando también los 72 scripts
heredados que `test_scripts_legacy.py` lanza como subprocesos.

    python scripts/medir_cobertura_real.py

**Por qué no basta `pytest --cov`.** `coverage` no instrumenta un subproceso
salvo que se le pida explícitamente, y `test_scripts_legacy.py` lanza cada
script heredado (`analyzer/pliego_conector.py`, `analyzer/sitio.py`,
`analyzer/interview/*`, ...) como un `subprocess.run` propio, no como una
llamada de función. Sin instrumentarlos, `pytest --cov` mide sólo el 47 % de
las líneas de test del repo y produce una lista de "peores módulos" que en
realidad es la lista de módulos con test heredado -- apunta al sitio
equivocado (informe de test, 2026-08-20, hallazgo 1).

**Qué hace, en orden:**

1. Instala un gancho de arranque de `coverage` (`coverage.process_startup()`)
   en el `site-packages` de este intérprete, vía un fichero `.pth` -- es el
   mecanismo que la propia librería documenta para instrumentar subprocesos, y
   no hay otro. Sólo afecta a este entorno virtual (`venv/`, ya en
   `.gitignore`); nunca se versiona y no toca ningún test.
2. Corre la suite completa con `COVERAGE_PROCESS_START` apuntando a
   `.coveragerc`, así que tanto el proceso de `pytest` como cada subproceso
   que lanza `test_scripts_legacy.py` quedan instrumentados y cada uno escribe
   su propio fichero de datos (`parallel = true` en `.coveragerc`).
3. Combina los ficheros de todos los procesos (`coverage combine`) y emite el
   informe (`coverage report`).

El código de salida es el de la propia suite (0 si todo pasa), no el de
`coverage`: un fallo de medición no debe leerse como un fallo de tests.
"""
from __future__ import annotations

import os
import subprocess
import sys
import sysconfig
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
COVERAGERC = RAIZ / ".coveragerc"
GANCHO = "import coverage; coverage.process_startup()\n"
NOMBRE_GANCHO = "zz_archmuse_coverage.pth"


def _instalar_gancho_de_subproceso() -> Path:
    """Escribe el `.pth` que arranca `coverage` en cada subproceso Python de
    este intérprete. Idempotente: si ya existe con este contenido exacto, no
    lo vuelve a tocar."""
    site_packages = Path(sysconfig.get_path("purelib"))
    ruta = site_packages / NOMBRE_GANCHO
    if not ruta.exists() or ruta.read_text(encoding="utf-8") != GANCHO:
        ruta.write_text(GANCHO, encoding="utf-8")
    return ruta


def main() -> int:
    if not COVERAGERC.exists():
        print("Error: falta %s" % COVERAGERC, file=sys.stderr)
        return 1

    _instalar_gancho_de_subproceso()

    entorno = dict(os.environ)
    entorno["COVERAGE_PROCESS_START"] = str(COVERAGERC)

    # Limpia datos de una medicion anterior para no mezclar corridas.
    subprocess.run(
        [sys.executable, "-m", "coverage", "erase", "--rcfile", str(COVERAGERC)],
        cwd=RAIZ, env=entorno, check=False,
    )

    corrida = subprocess.run(
        [sys.executable, "-m", "coverage", "run", "--rcfile", str(COVERAGERC),
         "-m", "pytest", "-q"],
        cwd=RAIZ, env=entorno,
    )

    subprocess.run(
        [sys.executable, "-m", "coverage", "combine", "--rcfile", str(COVERAGERC)],
        cwd=RAIZ, env=entorno, check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "coverage", "report", "--rcfile", str(COVERAGERC)],
        cwd=RAIZ, env=entorno, check=True,
    )

    return corrida.returncode


if __name__ == "__main__":
    sys.exit(main())
