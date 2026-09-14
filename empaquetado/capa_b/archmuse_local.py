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


#: Cuánto se espera a que el servidor conteste después de lanzarlo.
#:
#: **Hasta el 2026-09-14 eran 60 s, y no salían de ninguna medida**: la única
#: que había era `import app` en 2,75 s en la máquina de desarrollo. Medido ese
#: día en la VM de Windows 11 limpia: `import app` en 15,6 s en caliente y
#: **21,5 s al iniciar sesión tras reiniciar**, la peor medida que hay. **El
#: arranque en frío no se ha medido**, y el primero tras instalar es el más frío
#: que hay (primera lectura del runtime, `.pyc` de la capa B sin compilar).
#: 180 s son unas ocho veces la peor medida. Esperar tanto no cuesta nada cuando
#: el servidor falla: quien lo lanza vigila el proceso y deja de esperar en
#: cuanto muere.
PLAZO_ARRANQUE_S = 180

#: El código con el que sale Python cuando no puede abrir el script que se le
#: pasa: «can't open file '…': [Errno N] …», tanto si no existe como si otro
#: proceso lo tiene bloqueado (medido el 2026-09-14 con el `pythonw.exe`
#: embebido). En la VM limpia pasó **sólo durante la instalación**, con los
#: ficheros recién extraídos; minutos después el mismo arranque tardaba 0,8 s.
NO_PUEDE_ABRIR_EL_SCRIPT = 2


def fichero_de_errores_del_lanzador() -> str:
    """Lo que Python escribe antes de que el lanzador tome el control de su
    salida (p. ej. «can't open file»). Como `servidor-*.log`, no entra en
    `ARCHMUSE-INFORME`: lleva rutas con el nombre de usuario dentro."""
    return os.path.join(carpeta_registro(), "lanzador-errores.txt")


def arrancar_lanzador() -> subprocess.Popen:
    """Lanza el servidor de `app\\actual`, desacoplado de quien lo lanza.

    Devuelve el proceso para que quien espera sepa si ha muerto. **Su salida de
    errores va a `fichero_de_errores_del_lanzador()`**, con una línea de
    cabecera por lanzamiento: hasta el 2026-09-14 iba a DEVNULL, y en la VM
    limpia `pythonw` murió con código 2 sin que nadie pudiera leer por qué."""
    carpeta = carpeta_actual()
    pythonw = os.path.join(base(), "runtime", "pythonw.exe")
    if not os.path.isfile(pythonw):
        pythonw = sys.executable
    script = os.path.join(carpeta, "lanzador.pyw")
    os.makedirs(carpeta_registro(), exist_ok=True)
    with open(fichero_de_errores_del_lanzador(), "ab") as errores:
        errores.write(("%s | lanzando %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), script)).encode("utf-8"))
        errores.flush()
        return subprocess.Popen([pythonw, script], cwd=carpeta,
                                creationflags=DESACOPLADO, close_fds=True,
                                stdin=subprocess.DEVNULL, stdout=errores, stderr=errores)


def esperar_servidor(version: Optional[str] = None, segundos: float = PLAZO_ARRANQUE_S,
                     proceso: Optional[subprocess.Popen] = None) -> Optional[dict]:
    """El servidor vivo de `version`, o None. Con el `proceso` del lanzador, deja
    de esperar en cuanto ese proceso termina sin que el servidor conteste."""
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        datos = servidor_vivo()
        if datos and (version is None or datos.get("version_que_responde") == version):
            return datos
        if proceso is not None and proceso.poll() is not None:
            return None
        time.sleep(0.5)
    return None


def fichero_del_registro() -> str:
    return os.path.join(carpeta_registro(), "servidor-%s.log" % time.strftime("%Y-%m"))


def tamano_de(fichero: str) -> int:
    try:
        return os.path.getsize(fichero)
    except OSError:
        return 0


def tamano_del_registro() -> int:
    """Hasta dónde llega el registro ahora: se anota antes de lanzar el servidor
    para leer después sólo lo que ha escrito desde entonces."""
    return tamano_de(fichero_del_registro())


def lineas_escritas_desde(fichero: str, desde: int) -> list[str]:
    """Las líneas no vacías escritas en `fichero` a partir del byte `desde`."""
    try:
        with open(fichero, "rb") as f:
            f.seek(desde)
            nuevo = f.read()
    except OSError:
        return []
    return [linea for linea in nuevo.decode("utf-8", errors="replace").splitlines() if linea.strip()]


def lo_ultimo_escrito_desde(desde: int) -> Optional[str]:
    """La última línea escrita en el registro a partir del byte `desde`, sin la
    fecha. None si desde entonces no se ha escrito nada.

    **Por posición y no por PID**, a propósito: un intérprete puede arrancar el
    de verdad como proceso hijo (el `python.exe` de un venv lo hace), y entonces
    el PID que escribe no es el del proceso que se lanzó."""
    lineas = lineas_escritas_desde(fichero_del_registro(), desde)
    if not lineas:
        return None
    ultima = lineas[-1]
    return ultima.split(" | ", 1)[1] if " | " in ultima else ultima.strip()


def por_que_no_contesta(version: str, proceso: subprocess.Popen, segundos: float,
                        desde: int = 0, desde_errores: int = 0, intentos: int = 1) -> str:
    """El mensaje cuando el servidor recién lanzado no contesta: lo que se sabe
    (si el proceso vive o con qué código murió, lo que dijo Python y lo último
    que escribió el servidor), sin suponer la causa y sin mandar a AutoCAD."""
    codigo = proceso.poll()
    if codigo is None:
        que = "el servidor no ha contestado en %d s y sigue arrancando" % segundos
    elif codigo == NO_PUEDE_ABRIR_EL_SCRIPT:
        que = "Python no ha podido abrir el programa del servidor (código %d)" % codigo
    else:
        que = "el servidor se ha cerrado al arrancar (código %d)" % codigo
    if intentos > 1:
        que += ", en %d intentos" % intentos
    rastro = []
    python = [linea for linea in lineas_escritas_desde(fichero_de_errores_del_lanzador(), desde_errores)
              if " | lanzando " not in linea]
    if python:
        rastro.append("Python dijo: «%s»." % " ".join(python[-3:]))
    ultimo = lo_ultimo_escrito_desde(desde)
    if ultimo is None:
        rastro.append("No ha llegado a escribir nada en el registro.")
    else:
        rastro.append("Lo último que ha escrito: «%s»." % ultimo)
    return ("ArchMuse %s está instalado, pero %s. %s Al iniciar sesión en Windows ArchMuse "
            "se pone en marcha solo; si después sigue sin funcionar, mándanos la carpeta %s."
            % (version, que, " ".join(rastro), carpeta_registro()))


def escribir_resultado(fichero: str, correcto: bool, texto: str) -> None:
    """Lo que lee el instalador (`empaquetado/esperar_actualizador.iss`): `OK` o
    `ERROR` en la primera línea y el mensaje debajo. UTF-8 con marca, y de un
    golpe (temporal + `os.replace`): el instalador lo lee en cualquier instante."""
    temporal = fichero + ".tmp"
    with open(temporal, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write("%s\n%s\n" % ("OK" if correcto else "ERROR", texto))
    os.replace(temporal, fichero)


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


def copiar_lsp_al_bundle(version: str) -> None:
    """Deja el `.lsp` de la versión activa dentro del paquete de AutoCAD.

    **Si no puede, lanza `RuntimeError` con el motivo** (2026-09-14). Hasta
    entonces devolvía `False` y nadie lo miraba: el instalador decía «Listo» y
    AutoCAD contestaba «comando desconocido» sin que nada explicara por qué.

    **Por qué una copia y no un cargador que haga `load` de `app\\actual`**
    (desviación declarada del §4.3 del PRD): un `load` a una carpeta de
    `%LOCALAPPDATA%` fuera de `TRUSTEDPATHS` enseña el aviso de `SECURELOAD`.
    La fuente sigue siendo una sola (`app\\<version>\\archmuse.lsp`): esto la
    copia al activar.

    **Lo que esta copia NO consigue, y aquí se dio por hecho (corregido el
    2026-09-14):** se escribió que «AutoCAD confía en lo que carga desde
    `ApplicationPlugins`». Es falso para la carpeta que usamos. Desde AutoCAD
    2016 sólo `%PROGRAMFILES%\\Autodesk\\ApplicationPlugins` es de confianza
    por defecto; `%APPDATA%\\Autodesk\\ApplicationPlugins` lo fue en 2014 y
    2015 y dejó de serlo. Fuentes: Autodesk Developer Blog, «AutoCAD 2016:
    Trusted paths and AutoLoader»
    (https://blog.autodesk.io/autocad-2016-trusted-paths-and-autoloader/), y la
    ayuda de AutoCAD 2027, «About Installing and Uninstalling Plug-In
    Applications»: «All other ApplicationPlugins folders must be trusted as
    part of the application's preferences and should be digitally signed».
    **Medido el 2026-09-14 en AutoCAD 2027**: con el bundle en `%APPDATA%` sale
    «Seguridad - Archivo ejecutable no firmado» y el `.lsp` no carga hasta que
    él responde. La tabla completa está en el §4.3 del PRD de la beta.
    """
    bundle = carpeta_bundle()
    if not os.path.isdir(bundle):
        raise RuntimeError("no existe el paquete de AutoCAD (%s)" % bundle)
    contenido = os.path.join(bundle, "Contents")
    temporal = os.path.join(contenido, "archmuse.lsp.tmp")
    try:
        os.makedirs(contenido, exist_ok=True)
        shutil.copyfile(os.path.join(carpeta_app(), version, "archmuse.lsp"), temporal)
        os.replace(temporal, os.path.join(contenido, "archmuse.lsp"))
    except OSError as e:
        raise RuntimeError("no se ha podido copiar el comando al paquete de AutoCAD: %s" % e)


# ── la confianza de AutoCAD (enmienda del PRD, 2026-09-14) ──────────────────
#
# AutoCAD 2027 no confía en `%APPDATA%\Autodesk\ApplicationPlugins`: sin más,
# enseña «Seguridad - Archivo ejecutable no firmado» (medido, §4.3 del PRD). La
# vía B, decidida por Pablo: añadir la carpeta del `.lsp` a `TRUSTEDPATHS` de
# cada perfil, y al desinstalar quitar **esa entrada y ninguna otra**.

SERIE_MINIMA = (24, 0)          # el SeriesMin="R24.0" de PackageContents.xml


def ruta_de_confianza() -> str:
    """La carpeta donde está el `.lsp`, sin `\\...`: ni una subcarpeta más."""
    return os.path.join(carpeta_bundle(), "Contents")


def _misma_ruta(entrada: str, ruta: str) -> bool:
    limpia = entrada.strip().strip('"').rstrip("\\/")
    return bool(limpia) and os.path.normcase(limpia) == os.path.normcase(ruta.rstrip("\\/"))


def con_nuestra_ruta(valor: str, ruta: str) -> str:
    """`valor` con `ruta` añadida al final. Si ya estaba, `valor` tal cual."""
    if any(_misma_ruta(e, ruta) for e in valor.split(";")):
        return valor
    if not valor.strip():
        return ruta
    return valor + ("" if valor.endswith(";") else ";") + ruta


def sin_nuestra_ruta(valor: str, ruta: str) -> str:
    """`valor` sin las entradas que son `ruta`. Lo demás, carácter a carácter:
    ni se reordena, ni se limpia, ni se quita un `;;` que ya estuviera."""
    entradas = valor.split(";")
    quedan = [e for e in entradas if not _misma_ruta(e, ruta)]
    return valor if len(quedan) == len(entradas) else ";".join(quedan)


def raiz_autocad() -> str:
    """Bajo `HKEY_CURRENT_USER`. `ARCHMUSE_RAIZ_AUTOCAD` la cambia (tests)."""
    return os.environ.get("ARCHMUSE_RAIZ_AUTOCAD") or r"Software\Autodesk\AutoCAD"


def _subclaves(clave) -> list[str]:
    import winreg
    nombres = []
    while True:
        try:
            nombres.append(winreg.EnumKey(clave, len(nombres)))
        except OSError:
            return nombres


def perfiles_de_autocad() -> list[str]:
    """La clave `Variables` de cada perfil de cada AutoCAD desde R24.0.

    `<raíz>\\R<nn.n>\\<producto>\\Profiles\\<perfil>\\Variables`. AutoCAD LT vive en
    otra raíz y no se toca: no carga LISP. Un perfil sin `Variables` no se crea.
    """
    import winreg
    hkcu, raiz = winreg.HKEY_CURRENT_USER, raiz_autocad()
    try:
        with winreg.OpenKey(hkcu, raiz) as k:
            versiones = _subclaves(k)
    except OSError:
        return []
    encontradas = []
    for version in versiones:
        m = re.fullmatch(r"R(\d+)\.(\d+)", version)
        if not m or (int(m.group(1)), int(m.group(2))) < SERIE_MINIMA:
            continue
        try:
            with winreg.OpenKey(hkcu, "%s\\%s" % (raiz, version)) as k:
                productos = _subclaves(k)
        except OSError:
            continue
        for producto in productos:
            base = "%s\\%s\\%s\\Profiles" % (raiz, version, producto)
            try:
                with winreg.OpenKey(hkcu, base) as k:
                    perfiles = _subclaves(k)
            except OSError:
                continue
            for perfil in perfiles:
                variables = "%s\\%s\\Variables" % (base, perfil)
                try:
                    winreg.OpenKey(hkcu, variables).Close()
                except OSError:
                    continue
                encontradas.append(variables)
    return sorted(encontradas)


def _cambiar_trustedpaths(transformar, escribir: bool = True) -> list[tuple[str, bool]]:
    """Aplica `transformar(valor, ruta)` en cada perfil y escribe sólo lo que
    cambia (nada, si `escribir` es False). Devuelve `(clave, si cambia)`."""
    import winreg
    ruta = ruta_de_confianza()
    hechos = []
    for variables in perfiles_de_autocad():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, variables, 0,
                                winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as k:
                try:
                    valor, tipo = winreg.QueryValueEx(k, "TRUSTEDPATHS")
                except FileNotFoundError:
                    valor, tipo = "", winreg.REG_SZ
                if tipo not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                    raise RuntimeError("TRUSTEDPATHS de %s no es texto: no lo toco" % variables)
                nuevo = transformar(valor, ruta)
                if escribir and nuevo != valor:
                    winreg.SetValueEx(k, "TRUSTEDPATHS", 0, tipo, nuevo)
                hechos.append((variables, nuevo != valor))
        except OSError as e:
            raise RuntimeError("no se han podido cambiar las rutas de confianza de AutoCAD "
                               "(%s): %s" % (variables, e))
    return hechos


def anadir_confianza(escribir: bool = True) -> list[tuple[str, bool]]:
    return _cambiar_trustedpaths(con_nuestra_ruta, escribir)


def quitar_confianza(escribir: bool = True) -> list[tuple[str, bool]]:
    return _cambiar_trustedpaths(sin_nuestra_ruta, escribir)


def autocad_abierto() -> bool:
    """Si hay algún `acad.exe` en marcha.

    **`TRUSTEDPATHS` no se escribe nunca con AutoCAD abierto.** El riesgo (Pablo,
    2026-09-14): que AutoCAD reescriba sus variables al cerrarse y pise lo
    escrito mientras estaba abierto. *No se ha podido medir* (M2 de la
    enmienda: en esta máquina una ventana de `AdskLicensingAgent` bloquea
    AutoCAD y no se deja cerrar con normalidad desde la automatización). Con
    esta regla no hace falta saberlo."""
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq acad.exe", "/FO", "CSV", "/NH"],
                       capture_output=True, creationflags=SIN_VENTANA)
    if r.returncode != 0:
        raise RuntimeError("no he podido comprobar si AutoCAD está abierto")
    return b'"acad.exe"' in r.stdout.lower()


def cambiar_confianza_con_autocad_cerrado(quitar: bool = False) -> int:
    """Añade (o quita) nuestra ruta en los perfiles que lo necesiten y devuelve
    cuántos han cambiado. **Si alguno lo necesita y AutoCAD está abierto, no
    escribe en ninguno y lanza `RuntimeError`.** Si no hay nada que cambiar, no
    pregunta por AutoCAD: una actualización con AutoCAD abierto sigue siendo
    posible cuando la ruta ya estaba puesta."""
    cambiar = quitar_confianza if quitar else anadir_confianza
    if not any(cambia for _, cambia in cambiar(escribir=False)):
        return 0
    if autocad_abierto():
        raise RuntimeError("AutoCAD está abierto. Ciérralo y vuelve a intentarlo: ArchMuse "
                           "no toca las rutas de confianza de AutoCAD con AutoCAD abierto")
    return sum(1 for _, cambia in cambiar() if cambia)


def reponer_confianza() -> None:
    """Al iniciar sesión: nuestra ruta en los perfiles que no la tengan (uno
    creado después de instalar, o un AutoCAD abierto por primera vez). Sólo con
    AutoCAD cerrado. **Nunca lanza**: el lanzador tiene que arrancar igual, y lo
    que no haya podido hacer queda en el registro. *[Decisión mía, enmienda del
    PRD; dicha en la página previa del instalador.]*"""
    try:
        cambiados = cambiar_confianza_con_autocad_cerrado()
    except RuntimeError as e:
        registrar("rutas de confianza sin reponer: %s" % e)
        return
    if cambiados:
        registrar("ruta de confianza repuesta en %d perfil(es) de AutoCAD" % cambiados)
