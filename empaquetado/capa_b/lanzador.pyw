# -*- coding: utf-8 -*-
"""ArchMuse — el servidor de la beta, sin consola (T3 del PRD de la beta, D-1).

Lo ejecuta el acceso directo de la carpeta Inicio al iniciar sesión, el
instalador al terminar, el actualizador tras activar una versión y —T5— el
propio comando `ARCHMUSE` cuando no encuentra servidor.

- **Una sola instancia:** mutex con nombre. Si ya hay uno vivo, se retira.
- **Escalera de puertos:** 5000, 5001… el primero libre, abierto en exclusiva
  y sólo en `127.0.0.1`.
- **`servidor.json`** (`puerto`, `version`, `pid`, `arrancado`) para que el
  `.lsp` no tenga que suponer el puerto.
- Sin ventana: la salida va a `registro\\servidor-AAAA-MM.log`.

`pythonw.exe` hace de `ArchMuse-Servidor.exe` del PRD: el mismo subsistema sin
consola, sin compilar un ejecutable propio que el antivirus aún no conoce.
"""
import atexit
import os
import sys
import time
import traceback

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import archmuse_local as local  # noqa: E402


def main() -> int:
    os.makedirs(local.carpeta_registro(), exist_ok=True)
    salida = open(os.path.join(local.carpeta_registro(),
                               "servidor-%s.log" % time.strftime("%Y-%m")),
                  "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = salida

    mutex = local.mutex_unico(local.nombre_de_mutex())
    if mutex is None:
        local.registrar("ya hay un servidor de ArchMuse en marcha: este lanzador se retira")
        return 0

    # Enmienda del PRD (2026-09-14): nuestra ruta de confianza en los perfiles de
    # AutoCAD que no la tengan. Sólo con AutoCAD cerrado, y nunca impide arrancar.
    local.reponer_confianza()

    try:
        sock, puerto = local.elegir_socket()
    except RuntimeError as e:
        local.registrar("NO ARRANCA: %s" % e)
        return 1

    t0 = time.monotonic()
    os.chdir(AQUI)
    import app as aplicacion
    version = local.leer_version(AQUI) or "desconocida"

    local.escribir_estado({
        "puerto": puerto,
        "version": version,
        "pid": os.getpid(),
        "arrancado": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })
    atexit.register(local.borrar_estado_si_es_de, os.getpid())
    local.registrar("servidor %s en 127.0.0.1:%d (pid %d, import en %.1f s)"
                    % (version, puerto, os.getpid(), time.monotonic() - t0))

    from waitress import serve
    serve(aplicacion.app, sockets=[sock], threads=aplicacion.HILOS_WAITRESS)
    return 0


if __name__ == "__main__":
    try:
        codigo = main()
    except Exception:
        local.registrar("NO ARRANCA:\n" + traceback.format_exc())
        codigo = 1
    sys.exit(codigo)
