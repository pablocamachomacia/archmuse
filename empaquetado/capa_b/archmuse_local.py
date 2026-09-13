# -*- coding: utf-8 -*-
"""Lo que comparten el lanzador y el actualizador de la beta.

PRD: `docs/prd/2026-09-11-beta-instalable-en-el-ordenador-del-arquitecto.md`
(D-1, §4.1; D-2, §4.2). Viaja en la capa B (`app\\<version>\\`), junto a `app.py`.

**Sólo biblioteca estándar, a propósito.** El actualizador tiene que poder
ejecutarse aunque la capa B que va a activar venga rota, y el lanzador tiene que
poder escribir en el registro por qué no arranca aunque falle `import app`.

Todas las rutas cuelgan de `base()`: `%LOCALAPPDATA%\\ArchMuse`, o
`ARCHMUSE_BASE` si está definida (los tests montan un árbol de mentira).
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from typing import Optional

SIN_VENTANA = 0x08000000                     # CREATE_NO_WINDOW
DESACOPLADO = 0x00000008 | 0x00000200        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
ERROR_ALREADY_EXISTS = 183
_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


# ── rutas ───────────────────────────────────────────────────────────────────

def base() -> str:
    return os.environ.get("ARCHMUSE_BASE") or os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "ArchMuse")


def carpeta_app() -> str:
    return os.path.join(base(), "app")


def carpeta_actual() -> str:
    return os.path.join(carpeta_app(), "actual")


def carpeta_registro() -> str:
    return os.path.join(base(), "registro")


def fichero_estado() -> str:
    return os.path.join(base(), "servidor.json")


def carpeta_bundle() -> str:
    """El paquete de AutoCAD (§4.3). `ARCHMUSE_BUNDLE` lo cambia (tests)."""
    return os.environ.get("ARCHMUSE_BUNDLE") or os.path.join(
        os.environ.get("APPDATA", ""), "Autodesk", "ApplicationPlugins", "ArchMuse.bundle")


def puertos() -> list[int]:
    """La escalera de D-1: 5000, 5001… 5009. `ARCHMUSE_PUERTOS=a-b` la cambia."""
    a, b = (int(x) for x in os.environ.get("ARCHMUSE_PUERTOS", "5000-5009").split("-"))
    return list(range(a, b + 1))


# ── registro ────────────────────────────────────────────────────────────────

def registrar(texto: str) -> None:
    """Una línea en `registro\\servidor-AAAA-MM.log`. Nunca lanza.

    **`servidor-*` y no `archmuse-*`, y es deliberado:** `ARCHMUSE-INFORME`
    empaqueta `archmuse-*.log`, que escribe el `.lsp` con la lista cerrada de lo
    que puede contener (§4.4). Una traza del servidor puede llevar dentro el
    texto de una excepción, y ese texto puede ser un rótulo del proyecto. Que
    entre en el informe es una decisión, no un efecto de un comodín.
    """
    try:
        os.makedirs(carpeta_registro(), exist_ok=True)
        ruta = os.path.join(carpeta_registro(), "servidor-%s.log" % time.strftime("%Y-%m"))
        with open(ruta, "a", encoding="utf-8") as f:
            f.write("%s | %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), texto))
    except OSError:
        pass


def avisar(titulo: str, texto: str, error: bool = False) -> None:
    """Una ventana de una línea (§4.2). `ARCHMUSE_SIN_VENTANAS` la suprime."""
    registrar("%s: %s" % (titulo, texto))
    if os.environ.get("ARCHMUSE_SIN_VENTANAS"):
        return
    try:
        ctypes.windll.user32.MessageBoxW(None, texto, titulo, 0x10 if error else 0x40)
    except Exception:
        pass


# ── servidor.json ───────────────────────────────────────────────────────────

def leer_estado() -> Optional[dict]:
    try:
        with open(fichero_estado(), encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError):
        return None
    if (isinstance(datos, dict) and isinstance(datos.get("puerto"), int)
            and isinstance(datos.get("pid"), int)):
        return datos
    return None


def escribir_estado(datos: dict) -> None:
    """Atómico: el `.lsp` puede leerlo en cualquier instante."""
    os.makedirs(base(), exist_ok=True)
    temporal = fichero_estado() + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    os.replace(temporal, fichero_estado())


def borrar_estado_si_es_de(pid: int) -> None:
    datos = leer_estado()
    if datos is not None and datos.get("pid") == pid:
        try:
            os.remove(fichero_estado())
        except OSError:
            pass


# ── el servidor vivo ────────────────────────────────────────────────────────

_sin_proxy = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def salud(puerto: int, timeout: float = 1.0) -> Optional[dict]:
    try:
        with _sin_proxy.open("http://127.0.0.1:%d/api/salud" % puerto, timeout=timeout) as r:
            datos = json.load(r)
    except Exception:
        return None
    return datos if isinstance(datos, dict) and datos.get("ok") else None


def pid_escuchando(puerto: int) -> Optional[int]:
    """Quién escucha en `127.0.0.1:puerto`. Sin leer la columna de estado, que
    `netstat` traduce («ESCUCHANDO» en un Windows en castellano)."""
    r = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True,
                       creationflags=SIN_VENTANA)
    for linea in r.stdout.decode("latin-1", errors="replace").splitlines():
        p = linea.split()
        if (len(p) >= 5 and p[0] == "TCP" and p[1] == "127.0.0.1:%d" % puerto
                and p[2] == "0.0.0.0:0" and p[-1].isdigit()):
            return int(p[-1])
    return None


def servidor_vivo() -> Optional[dict]:
    """El servidor que declara `servidor.json`, **sólo si de verdad contesta**."""
    datos = leer_estado()
    if datos is None:
        return None
    respuesta = salud(datos["puerto"])
    if respuesta is None:
        return None
    return dict(datos, version_que_responde=respuesta.get("version"))


def elegir_socket(candidatos: Optional[list[int]] = None) -> tuple[socket.socket, int]:
    """El primer puerto libre de la escalera, **ya abierto**.

    Se le pasa a waitress el socket abierto, no el número: comprobar que un
    puerto está libre y abrirlo después deja un hueco en el que otro programa
    se lo puede quedar. En exclusiva (`SO_EXCLUSIVEADDRUSE`) y sólo en
    `127.0.0.1`: un bind a loopback no dispara el cortafuegos de Windows.
    """
    candidatos = candidatos or puertos()
    for puerto in candidatos:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            s.bind(("127.0.0.1", puerto))
        except OSError:
            s.close()
            continue
        return s, puerto
    raise RuntimeError("no hay ningún puerto libre entre %d y %d" % (candidatos[0], candidatos[-1]))


def matar_arbol(pid: int) -> None:
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                   creationflags=SIN_VENTANA)


def parar_servidor(espera: float = 15.0) -> bool:
    """Para el servidor de `servidor.json`. True si había uno y se ha parado.

    **Sólo se mata un PID si es el que escucha en el puerto declarado y ese
    puerto contesta como ArchMuse.** Un `servidor.json` que sobrevive a un
    apagón lleva un PID que Windows puede haber dado ya a cualquier otro
    programa suyo; matarlo por fiarse del fichero sería cerrarle el AutoCAD.
    """
    datos = leer_estado()
    if datos is None:
        return False
    if salud(datos["puerto"]) is None or pid_escuchando(datos["puerto"]) != datos["pid"]:
        registrar("servidor.json obsoleto (pid %d, puerto %d): se borra sin matar nada"
                  % (datos["pid"], datos["puerto"]))
        borrar_estado_si_es_de(datos["pid"])
        return False
    matar_arbol(datos["pid"])
    limite = time.monotonic() + espera
    while time.monotonic() < limite and salud(datos["puerto"], 0.5) is not None:
        time.sleep(0.2)
    borrar_estado_si_es_de(datos["pid"])
    registrar("servidor parado (pid %d)" % datos["pid"])
    return True


def nombre_de_mutex() -> str:
    """Uno por instalación: dos árboles distintos (los tests) no se pisan."""
    huella = hashlib.sha1(os.path.normcase(os.path.abspath(base())).encode("utf-8")).hexdigest()
    return "Local\\ArchMuse-Servidor-" + huella[:12]


def mutex_unico(nombre: str):
    """El mutex con nombre de D-1. None si ya lo tiene otro proceso vivo.

    Windows lo suelta solo cuando el proceso muere, también si lo matan: no
    hay un cerrojo huérfano que limpiar, a diferencia de un fichero.
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    manejador = kernel32.CreateMutexW(None, False, nombre)
    if not manejador or ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        return None
    return manejador


def arrancar_lanzador() -> None:
    """Lanza el servidor de `app\\actual`, desacoplado de quien lo lanza."""
    carpeta = carpeta_actual()
    pythonw = os.path.join(base(), "runtime", "pythonw.exe")
    if not os.path.isfile(pythonw):
        pythonw = sys.executable
    subprocess.Popen([pythonw, os.path.join(carpeta, "lanzador.pyw")], cwd=carpeta,
                     creationflags=DESACOPLADO, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)


def esperar_servidor(version: Optional[str] = None, segundos: float = 60.0) -> Optional[dict]:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        datos = servidor_vivo()
        if datos and (version is None or datos.get("version_que_responde") == version):
            return datos
        time.sleep(0.5)
    return None


# ── las dos capas y el puntero `actual` ─────────────────────────────────────

def leer_version(carpeta: str) -> Optional[str]:
    try:
        with open(os.path.join(carpeta, "version.json"), encoding="utf-8") as f:
            version = json.load(f).get("version")
    except (OSError, ValueError, AttributeError):
        return None
    return version if isinstance(version, str) and _VERSION.match(version) else None


def clave_de_version(version: str) -> tuple[int, ...]:
    return tuple(int(x) for x in version.split("."))


def versiones_instaladas() -> list[str]:
    try:
        nombres = os.listdir(carpeta_app())
    except OSError:
        return []
    validas = [n for n in nombres
               if n != "actual" and leer_version(os.path.join(carpeta_app(), n)) == n]
    return sorted(validas, key=clave_de_version)


def version_activa() -> Optional[str]:
    try:
        destino = os.readlink(carpeta_actual())
    except OSError:
        return None
    return os.path.basename(os.path.normpath(destino))


def _enlazar(enlace: str, destino: str) -> subprocess.CompletedProcess:
    # Una unión de directorios (junction) y no un enlace simbólico: los
    # simbólicos piden privilegio o modo desarrollador; las uniones no.
    return subprocess.run(["cmd", "/c", "mklink", "/J", enlace, destino],
                          capture_output=True, creationflags=SIN_VENTANA)


def apuntar_actual(version: str) -> Optional[str]:
    """Mueve `app\\actual` a `app\\<version>`. Devuelve la versión previa.

    Deja escrita la previa en `app\\anterior.txt`, que es lo que lee «volver a
    la anterior». Si el enlace nuevo no se puede crear, se restaura el viejo:
    lo único peor que no actualizar es quedarse sin ninguna versión activa.
    """
    destino = os.path.join(carpeta_app(), version)
    if leer_version(destino) != version:
        raise ValueError("app\\%s no es una versión de ArchMuse instalada" % version)
    enlace = carpeta_actual()
    previa = version_activa()
    if os.path.lexists(enlace):
        if not os.path.isjunction(enlace):
            raise RuntimeError("%s existe y no es un enlace: no lo toco" % enlace)
        os.rmdir(enlace)                 # quita la unión, no lo que contiene
    r = _enlazar(enlace, destino)
    if r.returncode != 0 or not os.path.isjunction(enlace):
        if previa:
            _enlazar(enlace, os.path.join(carpeta_app(), previa))
        raise RuntimeError("no se ha podido apuntar app\\actual a %s: %s"
                           % (version, r.stderr.decode("latin-1", errors="replace").strip()))
    if previa and previa != version:
        with open(os.path.join(carpeta_app(), "anterior.txt"), "w", encoding="utf-8") as f:
            f.write(previa)
    return previa


def version_anterior() -> Optional[str]:
    activa = version_activa()
    try:
        with open(os.path.join(carpeta_app(), "anterior.txt"), encoding="utf-8") as f:
            anotada = f.read().strip()
    except OSError:
        anotada = ""
    instaladas = versiones_instaladas()
    if anotada in instaladas and anotada != activa:
        return anotada
    otras = [v for v in instaladas if v != activa]
    return otras[-1] if otras else None


def copiar_lsp_al_bundle(version: str) -> bool:
    """Deja el `.lsp` de la versión activa dentro del paquete de AutoCAD.

    **Por qué una copia y no un cargador que haga `load` de `app\\actual`**
    (desviación declarada del §4.3 del PRD): AutoCAD confía en lo que carga
    desde `ApplicationPlugins`, pero un `load` a una carpeta de
    `%LOCALAPPDATA%` fuera de `TRUSTEDPATHS` enseña el aviso de `SECURELOAD`
    en cada dibujo — la primera pantalla que vería él. La fuente sigue siendo
    una sola (`app\\<version>\\archmuse.lsp`): esto la copia al activar.
    """
    bundle = carpeta_bundle()
    if not os.path.isdir(bundle):
        return False
    contenido = os.path.join(bundle, "Contents")
    os.makedirs(contenido, exist_ok=True)
    temporal = os.path.join(contenido, "archmuse.lsp.tmp")
    shutil.copyfile(os.path.join(carpeta_app(), version, "archmuse.lsp"), temporal)
    os.replace(temporal, os.path.join(contenido, "archmuse.lsp"))
    return True
