# -*- coding: utf-8 -*-
"""Construye la beta instalable (PRD 2026-09-11, T9 y T10).

    venv\\Scripts\\python.exe empaquetado\\construir.py            todo
    venv\\Scripts\\python.exe empaquetado\\construir.py --capa-b   sólo capa B y .archmuse, sin red

Qué sale, en `../_empaquetado/salida/` (fuera del repositorio):

- `runtime/`                       CAPA A: Python embebido + el perfil ligero.
- `app/<version>/`                 CAPA B: el servidor, el `.lsp`, lanzador y actualizador.
- `ArchMuse-<version>.archmuse`    la capa B en un fichero: la actualización.
- `ArchMuse-Beta-<version>.exe`    el instalador.

Antes de compilar el instalador se hace una **prueba de humo con el runtime
embebido**: mide una estancia sin tocar el `venv` y comprueba que no se ha
cargado ni un módulo de fuera de las dos capas. No sustituye a la máquina
limpia (§12.3.1: aquí hay un Python instalado), pero caza lo que falta en el
perfil antes de que lo cace el ordenador de otro.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.request
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
#: **Fuera del repositorio, a propósito** (junto a `_barrido/`). La capa B es una
#: copia de `analyzer/`, `ia/`…: dentro del árbol, cualquier test que recorra
#: todos los `.py` del repositorio la encuentra y falla por código duplicado
#: (pasó el 2026-09-13 con `test_nadie_construye_el_cliente_por_su_cuenta`).
SALIDA = RAIZ.parent / "_empaquetado" / "salida"
CACHE = RAIZ.parent / "_empaquetado" / "cache"

PYTHON_EMBEBIDO = "3.12.10"      # el mismo que el venv: las ruedas son cp312
URL_PYTHON = "https://www.python.org/ftp/python/{0}/python-{0}-embed-amd64.zip".format(
    PYTHON_EMBEBIDO)

#: Lo que el servidor importa de este repositorio. Medido el 2026-09-13:
#: `import app` carga analyzer, ia, modelo y normativa; `agente` y `bim` los
#: importa `app.py` dentro de funciones. Si falta algo, lo caza la prueba de humo.
PAQUETES_CAPA_B = ("analyzer", "agente", "bim", "ia", "modelo", "normativa")
FICHEROS_PROPIOS = ("lanzador.pyw", "actualizador.pyw", "archmuse_local.py")
_IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", "*.log", "*.sqlite", "estado",
                                  "*.dxf", "*.dwg", "*.tmp")


def version_del_producto() -> str:
    texto = (RAIZ / "analyzer" / "version.py").read_text(encoding="utf-8")
    return re.search(r'^VERSION_DEL_REPOSITORIO = "([^"]+)"', texto, re.M).group(1)


def version_del_lsp() -> str:
    texto = (RAIZ / "autocad" / "archmuse.lsp").read_text(encoding="utf-8")
    return re.search(r'\(setq \*am:version-corta\* "([^"]+)"\)', texto).group(1)


def megas(ruta: Path) -> float:
    if ruta.is_file():
        return ruta.stat().st_size / 1e6
    return sum(f.stat().st_size for f in ruta.rglob("*") if f.is_file()) / 1e6


# ── capa B ──────────────────────────────────────────────────────────────────

def capa_b(destino: Path, version: str | None = None) -> Path:
    """`destino/<version>/`. `version.json` declara también la del `.lsp` con la
    que se empaqueta: es lo que el servidor devuelve para el cotejo de D-2.

    `version` sólo para paquetes de PRUEBA (ensayar actualizar y volver atrás en
    la máquina limpia, criterios 8 y 9): el mismo código con otro número. Un
    paquete de verdad sale siempre con la versión del repositorio."""
    version = version or version_del_producto()
    carpeta = destino / version
    if carpeta.exists():
        shutil.rmtree(carpeta)
    carpeta.mkdir(parents=True)
    for paquete in PAQUETES_CAPA_B:
        shutil.copytree(RAIZ / paquete, carpeta / paquete, ignore=_IGNORAR)
    shutil.copy2(RAIZ / "app.py", carpeta / "app.py")
    shutil.copy2(RAIZ / "autocad" / "archmuse.lsp", carpeta / "archmuse.lsp")
    for nombre in FICHEROS_PROPIOS:
        shutil.copy2(AQUI / "capa_b" / nombre, carpeta / nombre)
    (carpeta / "version.json").write_text(json.dumps({
        "version": version,
        "lsp": version_del_lsp(),
        "construido": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, indent=2), encoding="utf-8")
    return carpeta


def paquete_archmuse(carpeta: Path) -> Path:
    destino = carpeta.parent.parent / ("ArchMuse-%s.archmuse" % carpeta.name)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for fichero in sorted(carpeta.rglob("*")):
            if fichero.is_file():
                z.write(fichero, fichero.relative_to(carpeta).as_posix())
    return destino


def bundle(destino: Path) -> Path:
    """El `PackageContents.xml` con la versión de este paquete dentro."""
    destino.mkdir(parents=True, exist_ok=True)
    xml = (AQUI / "bundle" / "PackageContents.xml").read_text(encoding="utf-8")
    xml = re.sub(r'AppVersion="[^"]*"', 'AppVersion="%s"' % version_del_producto(), xml)
    (destino / "PackageContents.xml").write_text(xml, encoding="utf-8")
    return destino


# ── capa A ──────────────────────────────────────────────────────────────────

def runtime(destino: Path) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    zip_python = CACHE / URL_PYTHON.rsplit("/", 1)[1]
    if not zip_python.exists():
        print("· descargando", URL_PYTHON)
        temporal = zip_python.with_suffix(".part")
        with urllib.request.urlopen(URL_PYTHON, timeout=120) as r, open(temporal, "wb") as f:
            shutil.copyfileobj(r, f)
        os.replace(temporal, zip_python)
    print("· python embebido %s  sha256 %s" % (
        PYTHON_EMBEBIDO, hashlib.sha256(zip_python.read_bytes()).hexdigest()))

    if destino.exists():
        shutil.rmtree(destino)
    with zipfile.ZipFile(zip_python) as z:
        z.extractall(destino)
    # Sin `import site`, a propósito: si el arquitecto tiene un Python suyo, sus
    # site-packages de usuario no se cuelan en el de ArchMuse.
    (destino / "python312._pth").write_text("python312.zip\n.\nLib\\site-packages\n",
                                            encoding="ascii")

    site_packages = destino / "Lib" / "site-packages"
    subprocess.run([
        sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-compile",
        "--target", str(site_packages),
        "--platform", "win_amd64", "--python-version", "3.12", "--implementation", "cp",
        "--only-binary=:all:",
        "-r", str(AQUI / "requisitos-beta.txt"),
        "-c", str(RAIZ / "requirements.lock.txt"),
    ], check=True)
    shutil.rmtree(site_packages / "bin", ignore_errors=True)
    subprocess.run([str(destino / "python.exe"), "-m", "compileall", "-q", "-j", "0",
                    str(site_packages)], check=True)
    return destino


_HUMO = textwrap.dedent("""
    import json, os, sys, time
    carpeta = sys.argv[1]
    sys.path.insert(0, carpeta)
    os.chdir(carpeta)
    t = time.time()
    import app
    t = time.time() - t
    cliente = app.app.test_client()
    salud = cliente.get("/api/salud")
    cuerpo = {
        "capa": "00 areas",
        "recintos": [{"handle": "1", "capa": "00 areas", "color": 256, "cerrada": True,
                      "vertices": [[0, 0], [5, 0], [5, 4], [0, 4]]}],
        "textos": [{"texto": "Salon", "x": 2.5, "y": 2.0}],
    }
    medicion = cliente.post("/api/medicion-geometria", data=json.dumps(cuerpo),
                            content_type="application/json")
    dentro = (os.path.normcase(sys.prefix), os.path.normcase(carpeta))
    de_fuera = sorted({
        nombre.split(".")[0] for nombre, m in list(sys.modules.items())
        if getattr(m, "__file__", None)
        and not os.path.normcase(os.path.abspath(m.__file__)).startswith(dentro)
    })
    print(json.dumps({"salud": salud.status_code, "medicion": medicion.status_code,
                      "version": (medicion.get_json() or {}).get("version"),
                      "import_s": round(t, 2), "de_fuera": de_fuera}))
""")


def prueba_de_humo(carpeta_runtime: Path, carpeta_b: Path) -> dict:
    entorno = {k: v for k, v in os.environ.items()
               if k not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")}
    entorno["ANTHROPIC_API_KEY"] = ""
    r = subprocess.run([str(carpeta_runtime / "python.exe"), "-c", _HUMO, str(carpeta_b)],
                       capture_output=True, text=True, timeout=600, env=entorno,
                       cwd=str(carpeta_b))
    if r.returncode != 0:
        raise SystemExit("PRUEBA DE HUMO: el runtime embebido no arranca el servidor.\n\n"
                         + r.stderr[-4000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


# ── instalador ──────────────────────────────────────────────────────────────

def iscc() -> str:
    en_path = shutil.which("iscc")
    if en_path:
        return en_path
    candidato = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe"
    if candidato.exists():
        return str(candidato)
    raise SystemExit("No encuentro Inno Setup 6 (ISCC.exe). "
                     "Instálalo: winget install JRSoftware.InnoSetup --scope user")


def instalador(version: str) -> Path:
    subprocess.run([iscc(), "/Q", "/DVersion=%s" % version, "/DSalida=%s" % SALIDA,
                    str(AQUI / "ArchMuse-Beta.iss")], check=True)
    return SALIDA / ("ArchMuse-Beta-%s.exe" % version)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--capa-b", action="store_true", help="sólo capa B y .archmuse")
    p.add_argument("--paquete-de-prueba", metavar="VERSION",
                   help="sólo un .archmuse con otra versión, para ensayar la actualización "
                        "en la máquina limpia (va a salida/prueba/)")
    a = p.parse_args(argv)

    if a.paquete_de_prueba:
        if not re.fullmatch(r"\d+\.\d+\.\d+", a.paquete_de_prueba):
            raise SystemExit("--paquete-de-prueba necesita una versión X.Y.Z")
        carpeta = capa_b(SALIDA / "prueba" / "app", a.paquete_de_prueba)
        paquete = paquete_archmuse(carpeta)
        print("· PAQUETE DE PRUEBA %s  %.1f MB  %s" % (a.paquete_de_prueba, megas(paquete), paquete))
        return 0

    version = version_del_producto()
    print("ArchMuse %s  (.lsp %s)" % (version, version_del_lsp()))
    SALIDA.mkdir(parents=True, exist_ok=True)
    carpeta = capa_b(SALIDA / "app")
    paquete = paquete_archmuse(carpeta)
    bundle(SALIDA / "bundle")
    print("· capa B       %6.1f MB   %s" % (megas(carpeta), carpeta))
    print("· .archmuse    %6.1f MB   %s" % (megas(paquete), paquete))
    if a.capa_b:
        return 0

    t0 = time.monotonic()
    carpeta_runtime = runtime(SALIDA / "runtime")
    print("· runtime      %6.1f MB   (%.0f s)" % (megas(carpeta_runtime), time.monotonic() - t0))

    humo = prueba_de_humo(carpeta_runtime, carpeta)
    print("· humo         %s" % json.dumps(humo))
    if humo["salud"] != 200 or humo["medicion"] != 200 or humo["version"] != version:
        raise SystemExit("PRUEBA DE HUMO FALLIDA")
    if humo["de_fuera"]:
        raise SystemExit("PRUEBA DE HUMO FALLIDA: se han cargado módulos de fuera de las dos "
                         "capas: %s" % humo["de_fuera"])

    exe = instalador(version)
    print("· instalador   %6.1f MB   %s" % (megas(exe), exe))
    return 0


if __name__ == "__main__":
    sys.exit(main())
