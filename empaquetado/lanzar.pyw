# -*- coding: utf-8 -*-
"""ArchMuse — punto de entrada fijo: `{app}\\lanzar.pyw` (2026-09-14).

    pythonw.exe lanzar.pyw                              el servidor (acceso directo de Inicio, rama C)
    pythonw.exe lanzar.pyw actualizador --volver        «volver a la versión anterior»
    pythonw.exe lanzar.pyw actualizador --instalar F    doble clic en un .archmuse

Lee la versión activa de `app\\actual.txt` y ejecuta `app\\<versión>\\lanzador.pyw`
o `actualizador.pyw` en este mismo proceso.

**Por qué existe.** Hasta el 2026-09-14 la versión activa era una unión de
directorios, `app\\actual`. Inno Setup 6.7 activa en el instalador la protección
RedirectionGuard de Windows, que prohíbe atravesar uniones creadas sin
administrador, y la heredan los procesos que lanza: en la VM de Windows 11
limpia el servidor no arrancaba al instalar («can't open file …\\app\\actual\\
lanzador.pyw: [Errno 22] Invalid argument»). Un fichero con la versión no se
atraviesa: vale dentro del instalador y fuera de él, lo active quien lo active.

Viaja en la instalación, no en la capa B: tiene que funcionar con cualquier
versión, así que es pequeño a propósito y no importa nada de ArchMuse.
"""
import os
import re
import runpy
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
QUE_SE_PUEDE_LANZAR = ("lanzador", "actualizador")


def _registrar(texto: str) -> None:
    """Una línea en el registro del servidor. Nunca lanza."""
    try:
        carpeta = os.path.join(BASE, "registro")
        os.makedirs(carpeta, exist_ok=True)
        with open(os.path.join(carpeta, "servidor-%s.log" % time.strftime("%Y-%m")), "a",
                  encoding="utf-8") as f:
            f.write("%s | lanzar: %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), texto))
    except OSError:
        pass


def main() -> int:
    que = sys.argv[1] if len(sys.argv) > 1 else "lanzador"
    if que not in QUE_SE_PUEDE_LANZAR:
        _registrar("no sé lanzar «%s»" % que)
        return 1
    try:
        with open(os.path.join(BASE, "app", "actual.txt"), encoding="utf-8") as f:
            version = f.read().strip()
    except OSError as e:
        _registrar("no hay versión activa (app\\actual.txt): %s" % e)
        return 1
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        _registrar("app\\actual.txt no trae una versión válida: %r" % version)
        return 1
    script = os.path.join(BASE, "app", version, que + ".pyw")
    if not os.path.isfile(script):
        _registrar("la versión activa %s no tiene %s.pyw" % (version, que))
        return 1
    sys.argv = [script] + sys.argv[2:]
    runpy.run_path(script, run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
