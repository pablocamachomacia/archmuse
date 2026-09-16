# -*- coding: utf-8 -*-
"""Guardián del registro de AutoCAD para lo que pasa FUERA de AutoCAD (`C-16`, 2026-09-16).

    venv\\Scripts\\python.exe -m herramientas.guardian_autocad.guardian_registro foto
    (instalar, actualizar, ARCHMUSE-ACTUALIZAR, cerrar y abrir AutoCAD…)
    venv\\Scripts\\python.exe -m herramientas.guardian_autocad.guardian_registro comparar

**Por qué.** FILEDIA apareció a 0 dos veces, las dos justo después de instalar una
versión, y el guardián de AutoCAD (`guardian.lsp`) sólo miraba el comando. La
instalación y la actualización corren fuera de AutoCAD: esto hace la foto de TODO
el registro de AutoCAD del usuario antes y después, y dice qué ha cambiado.

**Lo único que puede cambiar** es `TRUSTEDPATHS`, y sólo para añadir o quitar la
carpeta de ArchMuse (lo dice el instalador). Cualquier otra diferencia es
«AutoCAD NO está como estaba». AutoCAD abierto escribe su perfil por su cuenta al
cerrarse: la foto de después se hace con AutoCAD en el mismo estado que la de antes.

Sólo lee el registro. La foto se guarda en `%TEMP%`; nunca en el repositorio.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import winreg
from typing import Dict, List, Optional, Tuple

FOTO = os.path.join(tempfile.gettempdir(), "archmuse-guardian-registro.json")


def raiz_autocad() -> str:
    return os.environ.get("ARCHMUSE_RAIZ_AUTOCAD") or r"Software\Autodesk\AutoCAD"


def foto(raiz: Optional[str] = None) -> Dict[str, object]:
    """`{"<ruta relativa> : <nombre>": valor}` de todo lo que cuelga de `raiz`."""
    raiz = raiz or raiz_autocad()
    valores: Dict[str, object] = {}

    def recorrer(ruta: str) -> None:
        try:
            clave = winreg.OpenKey(winreg.HKEY_CURRENT_USER, ruta)
        except OSError:
            return
        with clave:
            i = 0
            while True:
                try:
                    nombre, valor, _tipo = winreg.EnumValue(clave, i)
                except OSError:
                    break
                relativa = ruta[len(raiz) + 1:]
                valores["%s : %s" % (relativa, nombre)] = (
                    valor.hex() if isinstance(valor, bytes) else valor)
                i += 1
            hijas = []
            while True:
                try:
                    hijas.append(winreg.EnumKey(clave, len(hijas)))
                except OSError:
                    break
        for hija in hijas:
            recorrer(ruta + "\\" + hija)

    recorrer(raiz)
    return valores


def diferencias(antes: Dict[str, object], despues: Dict[str, object]) -> List[Tuple[str, object, object]]:
    return [(k, antes.get(k), despues.get(k)) for k in sorted(set(antes) | set(despues))
            if antes.get(k) != despues.get(k)]


def _entradas(valor) -> List[str]:
    return [e.strip().strip('"').rstrip("\\/").lower()
            for e in str(valor or "").split(";") if e.strip()]


def inesperadas(cambios, ruta_de_confianza: str):
    """Los cambios que no son añadir o quitar SÓLO nuestra ruta de `TRUSTEDPATHS`."""
    nuestra = ruta_de_confianza.strip().rstrip("\\/").lower()
    malas = []
    for cambio in cambios:
        clave, antes, despues = cambio
        if clave.endswith(" : TRUSTEDPATHS"):
            quitadas = [e for e in _entradas(antes) if e not in _entradas(despues)]
            puestas = [e for e in _entradas(despues) if e not in _entradas(antes)]
            if set(quitadas + puestas) <= {nuestra}:
                continue
        malas.append(cambio)
    return malas


def _ruta_de_confianza() -> str:
    base = os.environ.get("APPDATA", "")
    return os.path.join(base, "Autodesk", "ApplicationPlugins", "ArchMuse.bundle", "Contents")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    orden = argv[0] if argv else ""
    if orden == "foto":
        with open(FOTO, "w", encoding="utf-8") as f:
            json.dump({"hecha": time.strftime("%Y-%m-%d %H:%M:%S"), "valores": foto()}, f,
                      ensure_ascii=False)
        print("Foto de antes del registro de AutoCAD hecha (%s)." % FOTO)
        return 0
    if orden == "comparar":
        try:
            with open(FOTO, encoding="utf-8") as f:
                guardada = json.load(f)
        except (OSError, ValueError):
            print("No hay foto de antes: ejecuta primero «foto».")
            return 2
        malas = inesperadas(diferencias(guardada["valores"], foto()), _ruta_de_confianza())
        print("Comparando con la foto de %s." % guardada["hecha"])
        if not malas:
            print("RESULTADO: el registro de AutoCAD está exactamente como estaba.")
            os.remove(FOTO)
            return 0
        print("RESULTADO: el registro de AutoCAD NO está como estaba:")
        for clave, antes, despues in malas:
            print("  %s: %r -> %r" % (clave, antes, despues))
        return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
