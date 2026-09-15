# -*- coding: utf-8 -*-
"""Construye la beta instalable (PRD 2026-09-11, T9 y T10).

    venv\\Scripts\\python.exe empaquetado\\construir.py            todo
    venv\\Scripts\\python.exe empaquetado\\construir.py --capa-b   sólo capa B y .archmuse, sin red

**El número lo pone solo** (PRD 2026-09-15): el siguiente al mayor de
`versiones_usadas.txt`, que se escribe en `analyzer/version.py`, en el bundle y
en esa lista. Cada build lleva un número que ningún otro ha tenido.

**Y firma el `.archmuse`** con la clave privada de ArchMuse, que vive fuera del
repositorio: `~/.archmuse/firma/archmuse-ed25519.semilla`, o donde diga
`ARCHMUSE_CLAVE_FIRMA`. Sin la clave no se construye, y no se gasta el número.

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
import importlib.util
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
FICHEROS_PROPIOS = ("lanzador.pyw", "actualizador.pyw", "archmuse_local.py",
                    "firma.py", "actualizaciones.py")
VERSIONES_USADAS = AQUI / "versiones_usadas.txt"
#: Fuera del repositorio, siempre. `leer_clave` se niega si está dentro.
CLAVE_POR_DEFECTO = Path.home() / ".archmuse" / "firma" / "archmuse-ed25519.semilla"
_IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", "*.log", "*.sqlite", "estado",
                                  "*.dxf", "*.dwg", "*.tmp")


def version_del_producto() -> str:
    texto = (RAIZ / "analyzer" / "version.py").read_text(encoding="utf-8")
    return re.search(r'^VERSION_DEL_REPOSITORIO = "([^"]+)"', texto, re.M).group(1)


def version_del_lsp() -> str:
    texto = (RAIZ / "autocad" / "archmuse.lsp").read_text(encoding="utf-8")
    return re.search(r'\(setq \*am:version-corta\* "([^"]+)"\)', texto).group(1)


# ── el número y la firma ────────────────────────────────────────────────────

def versiones_usadas(ruta: Path = VERSIONES_USADAS) -> list:
    usadas = []
    for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(\d+\.\d+\.\d+)(?:\s|$)", linea.strip())
        if m:
            usadas.append(m.group(1))
    return usadas


def siguiente_version(usadas, actual: str) -> str:
    """La siguiente al mayor número usado, contando también el del repositorio."""
    mayor = max(tuple(int(x) for x in v.split(".")) for v in list(usadas) + [actual])
    return "%d.%d.%d" % (mayor[0], mayor[1], mayor[2] + 1)


def fijar_version(version: str, raiz: Path = RAIZ, usadas: Path = VERSIONES_USADAS,
                  nota: str = "") -> None:
    """Escribe `version` en `analyzer/version.py` y en el bundle, y la anota como usada."""
    ruta_version = Path(raiz) / "analyzer" / "version.py"
    texto, n = re.subn(r'^VERSION_DEL_REPOSITORIO = "[^"]+"',
                       'VERSION_DEL_REPOSITORIO = "%s"' % version,
                       ruta_version.read_text(encoding="utf-8"), flags=re.M)
    if n != 1:
        raise SystemExit("No encuentro VERSION_DEL_REPOSITORIO en %s" % ruta_version)
    ruta_version.write_text(texto, encoding="utf-8", newline="\n")
    ruta_bundle = Path(raiz) / "empaquetado" / "bundle" / "PackageContents.xml"
    ruta_bundle.write_text(re.sub(r'AppVersion="[^"]*"', 'AppVersion="%s"' % version,
                                  ruta_bundle.read_text(encoding="utf-8"), count=1),
                           encoding="utf-8", newline="\n")
    if version not in versiones_usadas(usadas):
        with open(usadas, "a", encoding="utf-8", newline="\n") as f:
            f.write("%-7s %s\n" % (version, nota or "construida el %s" % time.strftime("%Y-%m-%d")))


def _modulo_firma():
    spec = importlib.util.spec_from_file_location("firma_construir", AQUI / "capa_b" / "firma.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def leer_clave(ruta=None) -> bytes:
    """La clave privada de ArchMuse. Se niega si no está, si está dentro del
    repositorio o si no es la que corresponde a la pública de `firma.py`."""
    ruta = Path(os.environ.get("ARCHMUSE_CLAVE_FIRMA") or ruta or CLAVE_POR_DEFECTO)
    if not ruta.is_file():
        raise SystemExit("No encuentro la clave de firma en %s. Sin ella no se construye: un "
                         ".archmuse sin firmar no lo instala ninguna versión de ArchMuse." % ruta)
    if Path(RAIZ).resolve() in ruta.resolve().parents:
        raise SystemExit("La clave de firma está DENTRO del repositorio (%s). Sácala de ahí antes "
                         "de construir: el repositorio es público." % ruta)
    try:
        semilla = bytes.fromhex(ruta.read_text(encoding="ascii").strip())
    except ValueError:
        semilla = b""
    firma = _modulo_firma()
    if len(semilla) != 32 or firma.clave_publica_de(semilla) != firma.clave_publica():
        raise SystemExit("La clave de %s no es la de ArchMuse: su pública no es la de "
                         "empaquetado/capa_b/firma.py." % ruta)
    return semilla


def megas(ruta: Path) -> float:
    if ruta.is_file():
        return ruta.stat().st_size / 1e6
    return sum(f.stat().st_size for f in ruta.rglob("*") if f.is_file()) / 1e6


# ── capa B ──────────────────────────────────────────────────────────────────

def capa_b(destino: Path, version: str | None = None, semilla: bytes | None = None) -> Path:
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
    # Lo último: el manifiesto firmado cubre todo lo que hay en la carpeta.
    if semilla is not None:
        _modulo_firma().firmar_carpeta(str(carpeta), semilla)
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
    p.add_argument("--misma-version", action="store_true",
                   help="no sube el número: sólo para repetir un build que no ha salido de "
                        "esta máquina")
    a = p.parse_args(argv)

    # La clave, lo primero: sin ella no se construye y no se gasta ningún número.
    semilla = leer_clave()

    if a.paquete_de_prueba:
        if not re.fullmatch(r"\d+\.\d+\.\d+", a.paquete_de_prueba):
            raise SystemExit("--paquete-de-prueba necesita una versión X.Y.Z")
        if a.paquete_de_prueba not in versiones_usadas():
            with open(VERSIONES_USADAS, "a", encoding="utf-8", newline="\n") as f:
                f.write("%-7s paquete de prueba, %s\n" % (a.paquete_de_prueba, time.strftime("%Y-%m-%d")))
        carpeta = capa_b(SALIDA / "prueba" / "app", a.paquete_de_prueba, semilla=semilla)
        paquete = paquete_archmuse(carpeta)
        print("· PAQUETE DE PRUEBA %s  %.1f MB  %s" % (a.paquete_de_prueba, megas(paquete), paquete))
        return 0

    if a.misma_version:
        version = version_del_producto()
    else:
        version = siguiente_version(versiones_usadas(), version_del_producto())
        fijar_version(version)
    print("ArchMuse %s  (.lsp %s)" % (version, version_del_lsp()))
    SALIDA.mkdir(parents=True, exist_ok=True)
    carpeta = capa_b(SALIDA / "app", semilla=semilla)
    paquete = paquete_archmuse(carpeta)
    bundle(SALIDA / "bundle")
    print("· capa B       %6.1f MB   %s" % (megas(carpeta), carpeta))
    print("· .archmuse    %6.1f MB   %s   (firmado)" % (megas(paquete), paquete))
    print("· sha256       %s" % hashlib.sha256(paquete.read_bytes()).hexdigest())
    if a.capa_b:
        _como_publicar(version)
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
    _como_publicar(version)
    return 0


def _como_publicar(version: str) -> None:
    print("\nPara publicarla (NO se ha publicado nada):")
    print("  1. commit de analyzer/version.py, empaquetado/bundle/PackageContents.xml y "
          "empaquetado/versiones_usadas.txt, y git push")
    print("  2. canal prueba:  venv\\Scripts\\python.exe empaquetado\\publicar.py %s" % version)
    print("  3. a estable:     venv\\Scripts\\python.exe empaquetado\\publicar.py --promover %s" % version)


if __name__ == "__main__":
    sys.exit(main())
