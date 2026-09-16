# -*- coding: utf-8 -*-
"""La única puerta a AutoCAD Core Console en este repositorio (`C-16`, 2026-09-16).

    venv\\Scripts\\python.exe -m herramientas.core_console --script s.scr [--dibujo p.dwg]
        [--salida consola.txt] [--plazo 600] [--solo-lectura] [--consola ruta]

**Por qué existe. Medido el 2026-09-16 en el ordenador de Pablo, con su AutoCAD
abierto:** Core Console escribe `FileDialog = 0` en
`HKCU\\Software\\Autodesk\\AutoCAD\\<versión>\\<producto>\\FixedProfile\\General
Configuration` **al arrancar**, y lo devuelve **sólo si sale limpio**. Matado a
mitad —por un plazo, a mano, o con un script que no llega a su `QUIT`— el 0 se
queda, y el siguiente AutoCAD que se abra lo lee: el explorador de Abrir
desaparece. Así quedó FILEDIA a 0 el 14-sep y el 15-sep, y cada reinicio de
AutoCAD tras una instalación lo volvía a leer.

Dos defensas, y las dos siempre:

1. **`/isolate`**, que aparta a Core Console del perfil del usuario. Medido el
   mismo día: con él, ni a mitad ni matado cambia nada del registro.
2. **Devolver lo que haya cambiado** en `FixedProfile\\General Configuration`
   al terminar, pase lo que pase: por si una versión de AutoCAD no respetara el
   aislamiento. Sólo lo que cambió; lo demás no se escribe.

Sólo biblioteca estándar. No va en el instalador: la usan el banco de
compatibilidad y las herramientas de desarrollo.
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import winreg
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: Las rutas donde se busca Core Console, de la versión más nueva a la más vieja.
PATRON_CONSOLA = r"C:\Program Files\Autodesk\AutoCAD *\accoreconsole.exe"
#: El usuario con el que se aísla. No es una cuenta: es el nombre de la clave aislada.
USUARIO_AISLADO = "archmuse"
GENERAL = r"FixedProfile\General Configuration"


def raiz_autocad() -> str:
    """Bajo `HKEY_CURRENT_USER`. `ARCHMUSE_RAIZ_AUTOCAD` la cambia (tests), igual
    que en `empaquetado/capa_b/archmuse_local.py`."""
    return os.environ.get("ARCHMUSE_RAIZ_AUTOCAD") or r"Software\Autodesk\AutoCAD"


def buscar_consola() -> Optional[str]:
    ruta = os.environ.get("ARCHMUSE_ACCORECONSOLE")
    if ruta and os.path.isfile(ruta):
        return ruta
    encontradas = sorted(glob.glob(PATRON_CONSOLA))
    return encontradas[-1] if encontradas else None


def argumentos(script: str, dibujo: Optional[str] = None, carpeta_aislada: str = "",
               solo_lectura: bool = False) -> List[str]:
    args: List[str] = []
    if dibujo:
        args += ["/i", dibujo]
    args += ["/s", script, "/isolate", USUARIO_AISLADO, carpeta_aislada]
    if solo_lectura:
        args.append("/readonly")
    return args


# ── el perfil de AutoCAD ────────────────────────────────────────────────────

def _subclaves(ruta: str) -> List[str]:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ruta) as k:
            nombres = []
            while True:
                try:
                    nombres.append(winreg.EnumKey(k, len(nombres)))
                except OSError:
                    return nombres
    except OSError:
        return []


def _claves_generales() -> List[str]:
    """`<raíz>\\<versión>\\<producto>\\FixedProfile\\General Configuration` de cada
    AutoCAD que tenga una."""
    raiz = raiz_autocad()
    claves = []
    for version in _subclaves(raiz):
        for producto in _subclaves("%s\\%s" % (raiz, version)):
            clave = "%s\\%s\\%s\\%s" % (raiz, version, producto, GENERAL)
            try:
                winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave).Close()
            except OSError:
                continue
            claves.append(clave)
    return claves


def _valores(clave: str) -> Dict[str, Tuple[Any, int]]:
    valores: Dict[str, Tuple[Any, int]] = {}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave) as k:
            i = 0
            while True:
                try:
                    nombre, valor, tipo = winreg.EnumValue(k, i)
                except OSError:
                    break
                valores[nombre] = (valor, tipo)
                i += 1
    except OSError:
        pass
    return valores


def foto_de_dialogos() -> Dict[str, Dict[str, Tuple[Any, int]]]:
    """Todos los valores de cada `FixedProfile\\General Configuration`, que es
    donde vive `FileDialog`."""
    return {clave: _valores(clave) for clave in _claves_generales()}


def devolver(antes: Dict[str, Dict[str, Tuple[Any, int]]]) -> List[str]:
    """Pone otra vez lo que haya cambiado respecto a `antes`. Devuelve qué."""
    devueltos = []
    for clave, valores in antes.items():
        ahora = _valores(clave)
        cambiados = {n: vt for n, vt in valores.items() if ahora.get(n) != vt}
        if not cambiados:
            continue
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave, 0, winreg.KEY_SET_VALUE) as k:
                for nombre, (valor, tipo) in cambiados.items():
                    winreg.SetValueEx(k, nombre, 0, tipo, valor)
                    devueltos.append("%s : %s = %r (estaba %r)"
                                     % (clave, nombre, valor, (ahora.get(nombre) or (None,))[0]))
        except OSError as e:
            devueltos.append("%s: no se ha podido devolver (%s)" % (clave, e))
    return devueltos


# ── ejecutar ────────────────────────────────────────────────────────────────

@dataclass
class Resultado:
    codigo: Optional[int]
    agotado: bool
    #: Lo que Core Console dejó cambiado en el perfil y se ha devuelto. Vacío es lo
    #: normal con `/isolate`; si no lo está, conviene decirlo.
    restaurado: List[str] = field(default_factory=list)
    salida: bytes = b""


def ejecutar(script: str, dibujo: Optional[str] = None, consola: Optional[str] = None,
             cwd: Optional[str] = None, plazo_s: float = 600, solo_lectura: bool = False,
             salida: Optional[str] = None, orden: Optional[Sequence[str]] = None,
             carpeta_aislada: Optional[str] = None) -> Resultado:
    """Ejecuta Core Console aislado y devuelve lo que haya dejado cambiado.

    `orden` sustituye al ejecutable (los tests pasan una consola falsa). Si se
    agota `plazo_s`, se mata: y aun así el perfil queda como estaba.

    `carpeta_aislada` reutiliza la misma carpeta de datos aislados en varias
    sesiones y no se borra: la prueba del guardián compara dos sesiones, y con una
    carpeta nueva cada vez todas las rutas de AutoCAD cambiarían (medido)."""
    if orden is None:
        consola = consola or buscar_consola()
        if not consola:
            raise FileNotFoundError("no hay AutoCAD Core Console en este ordenador")
        orden = [consola]
    propia = carpeta_aislada is None
    if propia:
        aislada = tempfile.mkdtemp(prefix="archmuse_core_console_")
    else:
        aislada = carpeta_aislada
        os.makedirs(aislada, exist_ok=True)
    antes = foto_de_dialogos()
    agotado, codigo, bytes_salida = False, None, b""
    try:
        try:
            r = subprocess.run(list(orden) + argumentos(script, dibujo, aislada, solo_lectura),
                               cwd=cwd, capture_output=True, timeout=plazo_s,
                               stdin=subprocess.DEVNULL)
            codigo, bytes_salida = r.returncode, r.stdout
        except subprocess.TimeoutExpired as e:
            # `subprocess.run` ya lo ha matado: esto es justo lo que dejaba FILEDIA a 0.
            agotado, bytes_salida = True, e.stdout or b""
    finally:
        restaurado = devolver(antes)
        if propia:
            shutil.rmtree(aislada, ignore_errors=True)
        if salida:
            with open(salida, "wb") as f:
                f.write(bytes_salida)
    return Resultado(codigo, agotado, restaurado, bytes_salida)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="core_console", description="Core Console, aislado.")
    p.add_argument("--script", required=True)
    p.add_argument("--dibujo")
    p.add_argument("--salida")
    p.add_argument("--plazo", type=float, default=600)
    p.add_argument("--solo-lectura", action="store_true")
    p.add_argument("--consola")
    p.add_argument("--carpeta")
    p.add_argument("--aislada", help="carpeta de datos aislados a reutilizar (no se borra)")
    a = p.parse_args(argv)
    try:
        r = ejecutar(a.script, a.dibujo, a.consola, a.carpeta, a.plazo, a.solo_lectura, a.salida,
                     carpeta_aislada=a.aislada)
    except FileNotFoundError as e:
        print("CORE_CONSOLE_NO_ENCONTRADA: %s" % e)
        return 3
    for linea in r.restaurado:
        print("DEVUELTO AL PERFIL DE AUTOCAD: %s" % linea)
    if r.agotado:
        print("TIMEOUT")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
