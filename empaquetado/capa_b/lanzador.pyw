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
import faulthandler
import os
import sys
import time
import traceback

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

try:
    import archmuse_local as local  # noqa: E402
except BaseException:
    # Sin `archmuse_local` no hay `registrar`: se escribe a mano en el mismo
    # fichero, para que ni esto pase sin dejar rastro.
    try:
        _registro = os.path.join(os.environ.get("ARCHMUSE_BASE") or os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "ArchMuse"), "registro")
        os.makedirs(_registro, exist_ok=True)
        with open(os.path.join(_registro, "servidor-%s.log" % time.strftime("%Y-%m")),
                  "a", encoding="utf-8") as _f:
            _f.write("%s | NO ARRANCA (pid %d, sin archmuse_local):\n%s"
                     % (time.strftime("%Y-%m-%d %H:%M:%S"), os.getpid(), traceback.format_exc()))
    except OSError:
        pass
    raise


def main() -> int:
    t0 = time.monotonic()
    # Lo primero de todo (2026-09-14). En la VM limpia un lanzador murió sin
    # escribir ni una línea, porque la primera se escribía después de `import
    # app`. Ahora queda constancia de que empezó, y `faulthandler` escribe en el
    # registro si el proceso muere de golpe.
    local.registrar("arrancando (pid %d)" % os.getpid())
    os.makedirs(local.carpeta_registro(), exist_ok=True)
    salida = open(os.path.join(local.carpeta_registro(),
                               "servidor-%s.log" % time.strftime("%Y-%m")),
                  "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = salida
    faulthandler.enable(file=salida, all_threads=True)

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

    local.registrar("importando la aplicación")
    t_import = time.monotonic()
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
    # Las dos cifras, para que cada arranque en su máquina mida los plazos:
    # `PLAZO_ARRANQUE_S` (actualizador) y `*am:plazo-arranque-s*` (rama C).
    local.registrar("servidor %s en 127.0.0.1:%d (pid %d, import en %.1f s, listo %.1f s "
                    "después de arrancar)" % (version, puerto, os.getpid(),
                                               time.monotonic() - t_import, time.monotonic() - t0))

    # **Actualizaciones** (PRD 2026-09-15): en un hilo aparte, con plazo corto, y
    # nunca impiden servir. Lo que encuentre lo lee AutoCAD de un fichero local.
    try:
        import actualizaciones
        actualizaciones.comprobar_al_arrancar()
    except Exception:
        local.registrar("actualizaciones: no se ha podido lanzar la comprobación:\n"
                        + traceback.format_exc())

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
