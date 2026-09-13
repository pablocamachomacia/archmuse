"""Arranque de un clic del servidor de ArchMuse, para desarrollar en ESTA máquina.

**No es el lanzador de la beta.** Ése es la T3 del PRD
`docs/prd/2026-09-11-beta-instalable-en-el-ordenador-del-arquitecto.md`, con su
`servidor.json`, su escalera de puertos y su mutex. Esto es para trabajar aquí:

- Se ejecuta con `pythonw` (sin consola): no hay ventana negra que cerrar.
- **Un solo lanzador por sesión.** El puerto de control `127.0.0.1:5099`, abierto
  en exclusiva, hace de cerrojo: si ya hay uno, éste le pasa la orden y se va.
- Levanta `python app.py` —waitress, el mismo camino que usa el `.lsp`— sin
  ventana y con la salida a `%LOCALAPPDATA%\\ArchMuse-dev\\servidor.log`.
- **Vigila los `.py` del repositorio** y reinicia al guardar, pero sólo si lo
  guardado compila: con un error de sintaxis NO reinicia y el servidor que
  funcionaba sigue vivo.
- Avisa con notificaciones de Windows; un clic en el aviso abre la web.

Órdenes: `arrancar` (por defecto) · `reiniciar` · `parar`.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

RAIZ = Path(__file__).resolve().parent.parent
PYTHON = RAIZ / "venv" / "Scripts" / "python.exe"
PUERTO = int(os.environ.get("PORT", "5000"))
PUERTO_CONTROL = 5099
URL = "http://127.0.0.1:%d" % PUERTO

DIR_DATOS = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ArchMuse-dev"
LOG_SERVIDOR = DIR_DATOS / "servidor.log"
LOG_LANZADOR = DIR_DATOS / "lanzador.log"
LOG_MAX_BYTES = 5 * 1024 * 1024

#: Lo que el servidor no importa nunca. `tests/` fuera a propósito: guardar un
#: test no tiene por qué tirar el servidor con el que se está probando AutoCAD.
NO_VIGILAR = {"venv", "tests", "experimentos", "node_modules", "static", "docs",
              "__pycache__", "empaquetado", "build", "dist"}

SEGUNDOS_MAX_ARRANQUE = 60
SIN_VENTANA = subprocess.CREATE_NO_WINDOW
APP_ID_AVISOS = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

_sin_proxy = urllib.request.build_opener(urllib.request.ProxyHandler({}))


# ── utilidades ──────────────────────────────────────────────────────────────

def anotar(texto: str) -> None:
    try:
        with open(LOG_LANZADOR, "a", encoding="utf-8") as f:
            f.write("%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), texto))
    except OSError:
        pass


def avisar(titulo: str, texto: str = "", abrir: str = URL) -> None:
    """Notificación de Windows, sin ventana. Un clic abre `abrir`."""
    anotar("AVISO  %s · %s" % (titulo, texto))
    xml = ('<toast activationType="protocol" launch="%s"><visual>'
           '<binding template="ToastGeneric"><text>%s</text><text>%s</text>'
           '</binding></visual></toast>') % (escape(abrir, {'"': "&quot;"}),
                                             escape(titulo), escape(texto))
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
        "ContentType = WindowsRuntime] | Out-Null;"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, "
        "ContentType = WindowsRuntime] | Out-Null;"
        "$x = New-Object Windows.Data.Xml.Dom.XmlDocument;"
        "$x.LoadXml('%s');"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('%s')"
        ".Show([Windows.UI.Notifications.ToastNotification]::new($x))"
    ) % (xml.replace("'", "''"), APP_ID_AVISOS)
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand",
             base64.b64encode(ps.encode("utf-16-le")).decode("ascii")],
            creationflags=SIN_VENTANA, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def salud(timeout: float = 1.0) -> dict | None:
    try:
        with _sin_proxy.open(URL + "/api/salud", timeout=timeout) as r:
            datos = json.load(r)
        return datos if datos.get("ok") else None
    except Exception:
        return None


def puerto_ocupado() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PUERTO), timeout=0.5):
            return True
    except OSError:
        return False


def _salida(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, creationflags=SIN_VENTANA)
    return r.stdout.decode("latin-1", errors="replace")


def pids_escuchando() -> set[int]:
    """PIDs que escuchan en el puerto. Sin mirar la columna de estado, que
    `netstat` traduce («ESCUCHANDO» en un Windows en castellano)."""
    pids = set()
    for linea in _salida(["netstat", "-ano", "-p", "TCP"]).splitlines():
        p = linea.split()
        if (len(p) >= 5 and p[0] == "TCP" and p[1].endswith(":%d" % PUERTO)
                and p[2] in ("0.0.0.0:0", "[::]:0") and p[-1].isdigit()):
            pids.add(int(p[-1]))
    return pids


def es_python(pid: int) -> bool:
    return _salida(["tasklist", "/FI", "PID eq %d" % pid, "/FO", "CSV", "/NH"]
                   ).strip().lower().startswith('"python')


def ultima_linea_de_error() -> str:
    try:
        with open(LOG_SERVIDOR, "rb") as f:
            f.seek(max(0, f.seek(0, 2) - 8192))
            cola = f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    cola = cola.rsplit("=====", 1)[-1]
    lineas = [x.strip() for x in cola.splitlines() if x.strip()]
    return lineas[-1][:200] if lineas else ""


def _rel(p: str) -> str:
    return os.path.relpath(p, RAIZ).replace("\\", "/")


# ── el supervisor ───────────────────────────────────────────────────────────

class Supervisor:
    def __init__(self, control: socket.socket):
        self.control = control
        self.proc: subprocess.Popen | None = None
        self.parada_esperada = False
        self.cerrojo = threading.RLock()
        self.salir = threading.Event()

    # arrancar / parar ------------------------------------------------------

    def _parar_servidor(self) -> None:
        """Mata el árbol, no el proceso: el `python.exe` del venv es un
        redirector que lanza el intérprete de verdad como hijo, y matar sólo
        el redirector deja el servidor huérfano con el puerto cogido."""
        if self.proc and self.proc.poll() is None:
            self.parada_esperada = True
            subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                           capture_output=True, creationflags=SIN_VENTANA)
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                pass
        self.proc = None

    def _liberar_puerto(self) -> bool:
        """Deja el puerto libre. Sólo mata procesos Python (un ArchMuse
        levantado a mano); si lo tiene otro programa, no toca nada."""
        if not puerto_ocupado():
            return True
        for pid in pids_escuchando():
            if not es_python(pid):
                avisar("ArchMuse no arranca",
                       "El puerto %d lo usa otro programa (PID %d). No lo toco." % (PUERTO, pid))
                return False
            anotar("mato el python que ocupaba el puerto (PID %d)" % pid)
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, creationflags=SIN_VENTANA)
        for _ in range(50):
            if not puerto_ocupado():
                return True
            time.sleep(0.1)
        avisar("ArchMuse no arranca", "El puerto %d no se ha liberado." % PUERTO)
        return False

    def arrancar_servidor(self, motivo: str, abrir_log_si_falla: bool = False) -> bool:
        with self.cerrojo:
            self._parar_servidor()
            if not self._liberar_puerto():
                self.salir.set()
                return False
            try:
                if LOG_SERVIDOR.exists() and LOG_SERVIDOR.stat().st_size > LOG_MAX_BYTES:
                    LOG_SERVIDOR.replace(LOG_SERVIDOR.with_suffix(".log.1"))
            except OSError:
                pass
            anotar("arranco el servidor: %s" % motivo)
            t0 = time.monotonic()
            with open(LOG_SERVIDOR, "ab") as log:
                log.write(("\n===== %s · %s =====\n" % (
                    time.strftime("%Y-%m-%d %H:%M:%S"), motivo)).encode("utf-8"))
                log.flush()
                entorno = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
                entorno.pop("FLASK_DEBUG", None)
                self.proc = subprocess.Popen(
                    [str(PYTHON), "app.py"], cwd=RAIZ, env=entorno,
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=SIN_VENTANA)
            self.parada_esperada = False

            while time.monotonic() - t0 < SEGUNDOS_MAX_ARRANQUE:
                if self.proc.poll() is not None:
                    break
                datos = salud()
                if datos:
                    avisar("ArchMuse en marcha · %s" % datos.get("version", "?"),
                           "%s · %s · %.1f s" % (motivo, URL, time.monotonic() - t0))
                    return True
                time.sleep(0.3)

            self._parar_servidor()
            avisar("ArchMuse no arranca (%s)" % motivo,
                   ultima_linea_de_error() or "Sin respuesta en %d s." % SEGUNDOS_MAX_ARRANQUE,
                   abrir=LOG_SERVIDOR.as_uri())
            if abrir_log_si_falla:
                subprocess.Popen(["notepad.exe", str(LOG_SERVIDOR)])
            return False

    def parar_todo(self) -> None:
        with self.cerrojo:
            self._parar_servidor()
            self.salir.set()
        avisar("ArchMuse parado", "Servidor y lanzador cerrados.")

    # hilos -----------------------------------------------------------------

    def atender(self) -> None:
        """Órdenes de un segundo clic en los accesos directos."""
        self.control.listen(4)
        self.control.settimeout(1.0)
        while not self.salir.is_set():
            try:
                conn, _ = self.control.accept()
            except (TimeoutError, socket.timeout):
                continue
            except OSError:
                return
            with conn:
                try:
                    conn.settimeout(2)
                    orden = conn.recv(64).decode("ascii", errors="replace").strip()
                    conn.sendall(b"ok")
                except OSError:
                    continue
            anotar("orden recibida: %s" % orden)
            if orden == "parar":
                self.parar_todo()
            elif orden == "reiniciar":
                threading.Thread(target=self.arrancar_servidor,
                                 args=("reinicio manual", True), daemon=True).start()
            elif orden == "arrancar":
                datos = salud()
                if datos:
                    avisar("ArchMuse ya está en marcha · %s" % datos.get("version", "?"),
                           "No levanto otro. %s" % URL)
                else:
                    threading.Thread(target=self.arrancar_servidor,
                                     args=("arranque", True), daemon=True).start()

    def _instantanea(self) -> dict[str, int]:
        marcas = {}
        for carpeta, subcarpetas, ficheros in os.walk(RAIZ):
            subcarpetas[:] = [d for d in subcarpetas
                              if d not in NO_VIGILAR and not d.startswith(".")]
            for nombre in ficheros:
                if nombre.endswith(".py") or (nombre == ".env" and carpeta == str(RAIZ)):
                    ruta = os.path.join(carpeta, nombre)
                    try:
                        marcas[ruta] = os.stat(ruta).st_mtime_ns
                    except OSError:
                        pass
        return marcas

    def vigilar(self) -> None:
        """Reinicia al guardar. Espera a que dejen de cambiar ficheros (un
        `git checkout` toca cientos) y comprueba que compilan antes de tirar
        el servidor que funciona."""
        previo = self._instantanea()
        while not self.salir.is_set():
            time.sleep(1)
            actual = self._instantanea()
            if actual == previo:
                continue
            while True:
                time.sleep(1)
                nuevo = self._instantanea()
                if nuevo == actual:
                    break
                actual = nuevo
            cambiados = sorted(p for p in actual if actual[p] != previo.get(p))
            borrados = sorted(p for p in previo if p not in actual)
            previo = actual
            if self.salir.is_set():
                return

            errores = []
            for ruta in cambiados:
                if not ruta.endswith(".py"):
                    continue
                try:
                    compile(Path(ruta).read_bytes(), ruta, "exec")
                except SyntaxError as e:
                    errores.append("%s, línea %s: %s" % (_rel(ruta), e.lineno, e.msg))
                except (OSError, ValueError):
                    pass
            if errores:
                avisar("No reinicio: error de sintaxis",
                       "%s. Sigue el servidor anterior." % errores[0])
                continue

            nombres = [_rel(p) for p in cambiados + borrados]
            resumen = ", ".join(nombres[:2]) + (" y %d más" % (len(nombres) - 2)
                                                if len(nombres) > 2 else "")
            self.arrancar_servidor("cambio en " + resumen)

    def bucle(self) -> None:
        """Hilo principal: se entera de si el servidor se cae solo. No lo
        relanza en bucle (un fallo al importar se repetiría sin fin): lo
        relanza el siguiente guardado o «reiniciar»."""
        while not self.salir.is_set():
            time.sleep(1)
            with self.cerrojo:
                if (self.proc and self.proc.poll() is not None
                        and not self.parada_esperada):
                    anotar("el servidor se ha caído (código %s)" % self.proc.returncode)
                    avisar("ArchMuse se ha caído",
                           ultima_linea_de_error() or "código %s" % self.proc.returncode,
                           abrir=LOG_SERVIDOR.as_uri())
                    self.proc = None
        try:
            self.control.close()
        except OSError:
            pass


# ── entrada ─────────────────────────────────────────────────────────────────

def main() -> None:
    orden = sys.argv[1] if len(sys.argv) > 1 else "arrancar"
    if orden not in ("arrancar", "reiniciar", "parar"):
        avisar("ArchMuse (desarrollo)", "Orden desconocida: %s" % orden)
        return
    DIR_DATOS.mkdir(parents=True, exist_ok=True)

    control = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    control.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        control.bind(("127.0.0.1", PUERTO_CONTROL))
    except OSError:
        control.close()
        try:
            with socket.create_connection(("127.0.0.1", PUERTO_CONTROL), timeout=3) as s:
                s.sendall(orden.encode("ascii"))
                s.recv(16)
        except OSError:
            avisar("ArchMuse (desarrollo)",
                   "Hay un lanzador en marcha pero no contesta (puerto %d)." % PUERTO_CONTROL,
                   abrir=LOG_LANZADOR.as_uri())
        return

    # A partir de aquí, éste es el único lanzador.
    if orden == "parar":
        if puerto_ocupado():
            Supervisor(control)._liberar_puerto()
            avisar("ArchMuse parado", "Estaba levantado fuera del lanzador.")
        else:
            avisar("ArchMuse no estaba en marcha")
        control.close()
        return

    if orden == "arrancar" and salud():
        avisar("Ya hay un ArchMuse en marcha",
               "Levantado fuera del lanzador: no levanto otro. "
               "«ArchMuse · reiniciar» lo pone bajo el lanzador.")
        control.close()
        return

    sup = Supervisor(control)
    threading.Thread(target=sup.atender, daemon=True).start()
    sup.arrancar_servidor("arranque" if orden == "arrancar" else "reinicio manual",
                          abrir_log_si_falla=True)
    threading.Thread(target=sup.vigilar, daemon=True).start()
    sup.bucle()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        DIR_DATOS.mkdir(parents=True, exist_ok=True)
        anotar("FALLO DEL LANZADOR\n" + traceback.format_exc())
        avisar("El lanzador de ArchMuse ha fallado", "Detalle en " + str(LOG_LANZADOR),
               abrir=LOG_LANZADOR.as_uri())
