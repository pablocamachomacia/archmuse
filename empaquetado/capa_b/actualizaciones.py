# -*- coding: utf-8 -*-
"""Actualizaciones automáticas por canal (PRD 2026-09-15).

Al arrancar el servidor, **en un hilo aparte** (`comprobar_al_arrancar`):

1. Lee el canal de esta instalación: `canal.txt`, «estable» o «prueba». Sin
   fichero, «estable».
2. Pide a GitHub Releases la lista de versiones, con un plazo corto.
3. Elige la más alta de su canal que sea más nueva que la activa. «Estable» sólo
   ve releases; «prueba» ve también prereleases.
4. La descarga y **verifica la firma** (`firma.verificar_paquete`).
5. Si todo cuadra, deja `actualizacion.json` con la versión y el fichero. Si
   algo falla —sin red, GitHub caído, firma mala—, lo borra y apunta el motivo
   en el registro: **sin aviso**.

**El comando de AutoCAD sólo lee `actualizacion.json`.** Ahí no hay red, así que
sin internet AutoCAD no espera nada. Instalar es `actualizador
--instalar-pendiente`, que vuelve a verificar la firma antes de tocar nada.

Sólo biblioteca estándar.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import traceback
import urllib.request
from typing import Optional

import archmuse_local as local
import firma

URL_POR_DEFECTO = "https://api.github.com/repos/pablocamachomacia/archmuse/releases?per_page=30"
CANALES = ("estable", "prueba")
#: Para pedir la lista a GitHub. Corto: va en un hilo del servidor, pero tampoco
#: tiene sentido tener un hilo esperando a una red que no está.
PLAZO_S = 5.0
#: Cada cuánto vuelve a mirar un servidor en marcha. **Medido el 2026-09-15 en la
#: instalación de Pablo:** el servidor 0.3.9 comprobó al arrancar y no volvió a
#: mirar; la 0.3.12 se publicó horas después y no la vio nadie.
INTERVALO_S = 60 * 60.0
#: Para descargar un paquete (~1 MB).
PLAZO_DESCARGA_S = 60.0
MAX_BYTES_LISTA = 2_000_000
MAX_BYTES_PAQUETE = 50_000_000
_VERSION = re.compile(r"^v?(\d+\.\d+\.\d+)$")


def url_de_releases() -> str:
    """`ARCHMUSE_URL_ACTUALIZACIONES` la cambia: los tests simulan GitHub."""
    return os.environ.get("ARCHMUSE_URL_ACTUALIZACIONES") or URL_POR_DEFECTO


def fichero_canal() -> str:
    return os.path.join(local.base(), "canal.txt")


def fichero_pendiente() -> str:
    return os.path.join(local.base(), "actualizacion.json")


def carpeta_descargas() -> str:
    return os.path.join(local.base(), "descargas")


def fichero_comprobacion() -> str:
    """`comprobacion.json`: el resultado de la última comprobación, sea el que sea.
    Lo lee el `.lsp` al cargar para dejarlo en su registro (3.9.1)."""
    return os.path.join(local.base(), "comprobacion.json")


def _escribir_comprobacion(resultado: str, instalada: str, nombre_canal: str,
                           version: Optional[str] = None) -> None:
    """Un JSON plano y **sin nulos**: el `.lsp` lo lee buscando comillas, y un
    `null` le haría leer la clave siguiente como valor."""
    datos = {"resultado": resultado, "instalada": instalada, "canal": nombre_canal,
             "comprobado": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if version:
        datos["version"] = version
    try:
        temporal = fichero_comprobacion() + ".tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(datos, f)
        os.replace(temporal, fichero_comprobacion())
    except OSError as e:
        local.registrar("actualizaciones: no se ha podido escribir %s: %s" % (fichero_comprobacion(), e))


# ── canal ───────────────────────────────────────────────────────────────────

def canal() -> str:
    try:
        with open(fichero_canal(), encoding="utf-8") as f:
            nombre = f.read().strip().lower()
    except OSError:
        return "estable"
    return nombre if nombre in CANALES else "estable"


def fijar_canal(nombre: str) -> str:
    nombre = (nombre or "").strip().lower()
    if nombre not in CANALES:
        raise ValueError("el canal tiene que ser «estable» o «prueba», no «%s»" % nombre)
    os.makedirs(local.base(), exist_ok=True)
    temporal = fichero_canal() + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        f.write(nombre + "\n")
    os.replace(temporal, fichero_canal())
    local.registrar("actualizaciones: canal «%s»" % nombre)
    return nombre


# ── la actualización pendiente ──────────────────────────────────────────────

def leer_pendiente() -> Optional[dict]:
    try:
        with open(fichero_pendiente(), encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(datos, dict):
        return None
    version, fichero = datos.get("version"), datos.get("fichero")
    if not (isinstance(version, str) and _VERSION.match(version)
            and isinstance(fichero, str) and os.path.isfile(fichero)):
        return None
    return datos


def borrar_pendiente() -> None:
    try:
        os.remove(fichero_pendiente())
    except OSError:
        pass


def _escribir_pendiente(datos: dict) -> None:
    temporal = fichero_pendiente() + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2)
    os.replace(temporal, fichero_pendiente())


# ── GitHub ──────────────────────────────────────────────────────────────────

def _pedir(url: str, plazo: float, maximo: int) -> bytes:
    peticion = urllib.request.Request(url, headers={
        "User-Agent": "ArchMuse-actualizaciones",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(peticion, timeout=plazo) as respuesta:
        datos = respuesta.read(maximo + 1)
    if len(datos) > maximo:
        raise ValueError("la respuesta pasa de %d bytes" % maximo)
    return datos


def elegir(releases, nombre_canal: str, instalada: str) -> Optional[tuple]:
    """`(versión, url)` de la versión más alta del canal que sea más nueva que
    `instalada`, o None. Los borradores no cuentan, y una versión sin su
    `ArchMuse-x.y.z.archmuse` tampoco."""
    mejor = None
    for release in releases if isinstance(releases, list) else []:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        if nombre_canal == "estable" and release.get("prerelease"):
            continue
        m = _VERSION.match(str(release.get("tag_name") or ""))
        if not m:
            continue
        version = m.group(1)
        if local.clave_de_version(version) <= local.clave_de_version(instalada):
            continue
        esperado = "ArchMuse-%s.archmuse" % version
        url = next((a.get("browser_download_url") for a in (release.get("assets") or [])
                    if isinstance(a, dict) and a.get("name") == esperado), None)
        if not url:
            continue
        if mejor is None or local.clave_de_version(version) > local.clave_de_version(mejor[0]):
            mejor = (version, url)
    return mejor


def comprobar(plazo: float = PLAZO_S) -> Optional[dict]:
    """La actualización pendiente que deja escrita, o None. **Nunca lanza**:
    todo lo que falla va al registro con su motivo."""
    instalada = local.version_activa()
    if instalada is None:
        local.registrar("actualizaciones: no hay ninguna versión activa; no se comprueba")
        return None
    nombre_canal = canal()
    try:
        releases = json.loads(_pedir(url_de_releases(), plazo, MAX_BYTES_LISTA).decode("utf-8"))
        eleccion = elegir(releases, nombre_canal, instalada)
    except Exception as e:  # noqa: BLE001 - la red y GitHub fallan de mil formas
        borrar_pendiente()
        _escribir_comprobacion("error", instalada, nombre_canal)
        local.registrar("actualizaciones: no se ha podido comprobar el canal «%s» (%s: %s). "
                        "Sin aviso." % (nombre_canal, type(e).__name__, e))
        return None
    if eleccion is None:
        borrar_pendiente()
        _escribir_comprobacion("al_dia", instalada, nombre_canal)
        local.registrar("actualizaciones: la %s es la más reciente del canal «%s»"
                        % (instalada, nombre_canal))
        return None

    version, url = eleccion
    # **La misma versión ya descargada y verificada no se vuelve a bajar**: con una
    # comprobación cada hora sería un mega por hora, y un fallo de la descarga
    # borraría una actualización que ya estaba lista.
    ya = leer_pendiente()
    if ya and ya.get("version") == version:
        try:
            if firma.verificar_paquete(ya["fichero"]) == version:
                _escribir_comprobacion("actualizacion", instalada, nombre_canal, version)
                return ya
        except Exception:  # noqa: BLE001 - si ya no verifica, se vuelve a descargar
            pass
    os.makedirs(carpeta_descargas(), exist_ok=True)
    destino = os.path.join(carpeta_descargas(), "ArchMuse-%s.archmuse" % version)
    parte = destino + ".parte"
    try:
        with open(parte, "wb") as f:
            f.write(_pedir(url, PLAZO_DESCARGA_S, MAX_BYTES_PAQUETE))
        firmada = firma.verificar_paquete(parte)
        if firmada != version:
            raise ValueError("GitHub la publica como %s y el paquete firmado es la %s"
                             % (version, firmada))
        os.replace(parte, destino)
    except Exception as e:  # noqa: BLE001
        borrar_pendiente()
        _escribir_comprobacion("error", instalada, nombre_canal)
        for resto in (parte,):
            try:
                os.remove(resto)
            except OSError:
                pass
        local.registrar("actualizaciones: la %s del canal «%s» se descarta: %s"
                        % (version, nombre_canal, e))
        return None

    pendiente = {"version": version, "fichero": destino, "canal": nombre_canal,
                 "instalada": instalada, "comprobado": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _escribir_pendiente(pendiente)
    _escribir_comprobacion("actualizacion", instalada, nombre_canal, version)
    _limpiar_descargas(destino)
    local.registrar("actualizaciones: la %s del canal «%s» está descargada y verificada; "
                    "AutoCAD preguntará" % (version, nombre_canal))
    return pendiente


def _limpiar_descargas(conservar: str) -> None:
    try:
        nombres = os.listdir(carpeta_descargas())
    except OSError:
        return
    for nombre in nombres:
        ruta = os.path.join(carpeta_descargas(), nombre)
        if os.path.normcase(ruta) != os.path.normcase(conservar):
            try:
                os.remove(ruta)
            except OSError:
                pass


def comprobar_al_arrancar(parar: Optional[threading.Event] = None) -> Optional[threading.Thread]:
    """Lanza `comprobar` en un hilo que no retiene el proceso, **y la repite cada
    `INTERVALO_S`** mientras el servidor siga en marcha (2026-09-15: un servidor
    que sólo mira al arrancar no ve lo que se publica después). `parar` la corta.
    `ARCHMUSE_SIN_ACTUALIZACIONES` lo desactiva (los tests que arrancan un
    servidor de verdad no deben salir a internet)."""
    if os.environ.get("ARCHMUSE_SIN_ACTUALIZACIONES"):
        local.registrar("actualizaciones: desactivadas (ARCHMUSE_SIN_ACTUALIZACIONES)")
        return None
    parar = parar or threading.Event()

    def trabajo():
        while not parar.is_set():
            try:
                comprobar()
            except BaseException:  # noqa: BLE001 - un hilo que muere en silencio no se ve
                local.registrar("actualizaciones: error inesperado:\n" + traceback.format_exc())
            parar.wait(INTERVALO_S)

    hilo = threading.Thread(target=trabajo, name="archmuse-actualizaciones", daemon=True)
    hilo.start()
    return hilo
