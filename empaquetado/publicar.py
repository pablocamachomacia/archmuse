# -*- coding: utf-8 -*-
"""Publica una versión en GitHub Releases, o la promueve de «prueba» a «estable».

    venv\\Scripts\\python.exe empaquetado\\publicar.py 0.3.9              canal prueba (prerelease)
    venv\\Scripts\\python.exe empaquetado\\publicar.py --promover 0.3.9   de prueba a estable
    venv\\Scripts\\python.exe empaquetado\\publicar.py 0.3.9 --mostrar    la orden, sin ejecutarla

PRD `docs/prd/2026-09-15-actualizaciones-automaticas.md`.

**Lo ejecuta Pablo, nunca una sesión automática.** El repositorio es público, y
lo que se publica lo descargan las instalaciones de ese canal en su próxima
sesión.

**Antes de publicar, `git push`:** la etiqueta `vX.Y.Z` se crea sobre el commit
actual, y GitHub tiene que conocerlo.

Qué comprueba antes de publicar: que el `.archmuse` está en la salida de
`construir.py`, que lo firmó ArchMuse y que es la versión pedida. Si no, no
publica.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
SALIDA = RAIZ.parent / "_empaquetado" / "salida"
REPO = "pablocamachomacia/archmuse"


def _firma():
    spec = importlib.util.spec_from_file_location("firma_publicar", AQUI / "capa_b" / "firma.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _version_valida(version: str) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version or ""):
        raise SystemExit("la versión tiene que ser X.Y.Z, no «%s»" % version)
    return version


def paquete_de(version: str, salida: Path = SALIDA) -> Path:
    return Path(salida) / ("ArchMuse-%s.archmuse" % version)


def commit_actual() -> str:
    return subprocess.run(["git", "-C", str(RAIZ), "rev-parse", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()


def orden_publicar(version: str, salida: Path = SALIDA, commit: str | None = None) -> list:
    version = _version_valida(version)
    ruta = paquete_de(version, salida)
    if not ruta.is_file():
        raise SystemExit("No está %s. Constrúyelo antes con empaquetado\\construir.py." % ruta)
    try:
        firmada = _firma().verificar_paquete(str(ruta))
    except ValueError as e:
        raise SystemExit("No se publica %s: %s" % (ruta.name, e))
    if firmada != version:
        raise SystemExit("No se publica: %s es la %s, no la %s" % (ruta.name, firmada, version))
    return ["gh", "release", "create", "v" + version, str(ruta),
            "--repo", REPO, "--target", commit or commit_actual(), "--prerelease",
            "--title", "ArchMuse %s" % version,
            "--notes", "ArchMuse %s, canal prueba. Se instala desde ArchMuse: al abrir AutoCAD "
                       "pregunta si instalarla." % version]


def orden_promover(version: str) -> list:
    version = _version_valida(version)
    return ["gh", "release", "edit", "v" + version, "--repo", REPO,
            "--prerelease=false", "--latest"]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("version")
    p.add_argument("--promover", action="store_true", help="de prueba a estable")
    p.add_argument("--mostrar", action="store_true", help="enseña la orden y no la ejecuta")
    a = p.parse_args(argv)
    orden = orden_promover(a.version) if a.promover else orden_publicar(a.version)
    print(subprocess.list2cmdline(orden))
    if a.mostrar:
        return 0
    return subprocess.run(orden).returncode


if __name__ == "__main__":
    sys.exit(main())
