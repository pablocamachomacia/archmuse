# -*- coding: utf-8 -*-
"""ArchMuse — versiones nuevas, vuelta atrás y activación (T9 del PRD de la beta, D-2).

    actualizador.pyw --instalar ArchMuse-0.3.2.archmuse   (doble clic en el fichero)
    actualizador.pyw --volver                              (menú Inicio)
    actualizador.pyw --activar 0.3.1 [--silencioso]        (lo usa el instalador)
    actualizador.pyw --parar                               (instalador, antes de copiar)
    actualizador.pyw --desinstalar                         (desinstalador)

Actualizar toca sólo la capa B: descomprime en `app\\<version>\\`, para el
servidor, mueve `app\\actual`, copia el `.lsp` al paquete de AutoCAD y arranca.
**La versión anterior no se borra nunca**: volver es mover el puntero.
"""
import argparse
import json
import os
import re
import shutil
import sys
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import archmuse_local as local  # noqa: E402

REQUERIDOS = ("version.json", "app.py", "archmuse.lsp", "lanzador.pyw",
              "actualizador.pyw", "archmuse_local.py")

#: Un paquete de actualización no lleva planos. Si lleva uno, alguien se ha
#: equivocado al construirlo, y lo que se instalaría es el proyecto de otro.
PROHIBIDAS = (".dxf", ".dwg", ".dwl", ".dwl2", ".bak")


def validar_paquete(ruta: str) -> str:
    """La versión que trae el `.archmuse`, o ValueError con el motivo."""
    try:
        paquete = zipfile.ZipFile(ruta)
    except (OSError, zipfile.BadZipFile):
        raise ValueError("el fichero no es un paquete de ArchMuse")
    with paquete:
        nombres = paquete.namelist()
        for nombre in nombres:
            normal = nombre.replace("\\", "/")
            if normal.startswith("/") or ":" in normal or ".." in normal.split("/"):
                raise ValueError("el paquete trae una ruta no permitida: %s" % nombre)
            if normal.lower().endswith(PROHIBIDAS):
                raise ValueError("el paquete trae un plano dentro (%s): no se instala" % nombre)
        falta = [r for r in REQUERIDOS if r not in nombres]
        if falta:
            raise ValueError("no es un paquete de ArchMuse: le falta %s" % ", ".join(falta))
        try:
            version = json.loads(paquete.read("version.json").decode("utf-8")).get("version")
        except (ValueError, AttributeError):
            version = None
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("el paquete no declara una versión válida")
    return version


def _parar_o_abortar() -> None:
    local.parar_servidor()
    if local.servidor_vivo() is not None:
        raise RuntimeError("El ArchMuse que está en marcha no se deja parar. "
                           "No se ha cambiado nada. Reinicia el ordenador y vuelve a probar.")


def activar(version: str, arrancar: bool = True):
    # Lo primero, antes de parar o mover nada (enmienda del PRD, 2026-09-14):
    # nuestra carpeta en las rutas de confianza de AutoCAD. Con AutoCAD abierto
    # y algo que escribir, se para aquí sin haber cambiado nada.
    try:
        perfiles = local.cambiar_confianza_con_autocad_cerrado()
    except RuntimeError as e:
        raise RuntimeError("ArchMuse no ha podido añadir su carpeta a las rutas de confianza "
                           "de AutoCAD: %s. No se ha cambiado nada." % e)
    if perfiles:
        local.registrar("ruta de confianza añadida en %d perfil(es) de AutoCAD" % perfiles)
    _parar_o_abortar()
    previa = local.apuntar_actual(version)
    try:
        local.copiar_lsp_al_bundle(version)
    except RuntimeError as e:
        # Sin esto, lo siguiente que vería él es «comando desconocido» en AutoCAD.
        raise RuntimeError(
            "ArchMuse %s está instalado, pero AutoCAD no va a encontrar el comando "
            "ARCHMUSE: %s. Vuelve a ejecutar el instalador; si sigue igual, avísanos."
            % (version, e))
    if arrancar:
        local.arrancar_lanzador()
        if local.esperar_servidor(version) is None:
            raise RuntimeError(
                "ArchMuse %s está instalado, pero el servidor no ha arrancado. "
                "Reinicia el ordenador; si sigue igual, abre AutoCAD y teclea "
                "ARCHMUSE-INFORME." % version)
    local.registrar("activada la versión %s (antes: %s)" % (version, previa))
    return previa


def instalar(ruta: str, arrancar: bool = True) -> str:
    version = validar_paquete(ruta)
    carpeta_app = local.carpeta_app()
    os.makedirs(carpeta_app, exist_ok=True)
    temporal = os.path.join(carpeta_app, ".%s.instalando" % version)
    shutil.rmtree(temporal, ignore_errors=True)
    with zipfile.ZipFile(ruta) as paquete:
        paquete.extractall(temporal)

    try:
        _parar_o_abortar()
    except RuntimeError:
        shutil.rmtree(temporal, ignore_errors=True)
        raise

    destino = os.path.join(carpeta_app, version)
    if os.path.isdir(destino):
        # La misma versión otra vez: se sustituye. Si es la activa, primero se
        # quita la unión, que si no el borrado dejaría `actual` apuntando a nada.
        if local.version_activa() == version:
            os.rmdir(local.carpeta_actual())
        shutil.rmtree(destino)
    os.replace(temporal, destino)
    activar(version, arrancar)
    return version


def volver(arrancar: bool = True) -> tuple:
    activa = local.version_activa()
    anterior = local.version_anterior()
    if anterior is None:
        raise RuntimeError("No hay ninguna versión anterior instalada a la que volver.")
    activar(anterior, arrancar)
    return anterior, activa


def desinstalar() -> None:
    # Condición 2 de la enmienda del PRD (2026-09-14): nuestra ruta de confianza
    # sale de cada perfil de AutoCAD, y las suyas se quedan como estaban. Con
    # AutoCAD abierto no se toca (el desinstalador ya exige cerrarlo antes).
    try:
        cambiados = local.cambiar_confianza_con_autocad_cerrado(quitar=True)
    except RuntimeError as e:
        raise RuntimeError("ArchMuse no ha podido quitar su carpeta de las rutas de confianza "
                           "de AutoCAD: %s" % e)
    local.registrar("ruta de confianza quitada de %d perfil(es) de AutoCAD" % cambiados)
    local.parar_servidor()
    if os.path.isjunction(local.carpeta_actual()):
        os.rmdir(local.carpeta_actual())


CERRAR_AUTOCAD = "Si tienes AutoCAD abierto, ciérralo y vuelve a abrirlo."


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="actualizador")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--instalar", metavar="FICHERO")
    g.add_argument("--volver", action="store_true")
    g.add_argument("--activar", metavar="VERSION")
    g.add_argument("--parar", action="store_true")
    g.add_argument("--desinstalar", action="store_true")
    p.add_argument("--silencioso", action="store_true")
    p.add_argument("--sin-arrancar", action="store_true")
    a = p.parse_args(argv)
    arrancar = not a.sin_arrancar

    try:
        if a.instalar:
            version = instalar(a.instalar, arrancar)
            if not a.silencioso:
                local.avisar("ArchMuse", "ArchMuse %s instalado. %s" % (version, CERRAR_AUTOCAD))
        elif a.volver:
            anterior, activa = volver(arrancar)
            if not a.silencioso:
                local.avisar("ArchMuse", "ArchMuse ha vuelto a la versión %s (estaba en la %s). %s"
                             % (anterior, activa, CERRAR_AUTOCAD))
        elif a.activar:
            activar(a.activar, arrancar)
        elif a.parar:
            local.parar_servidor()
        elif a.desinstalar:
            desinstalar()
    except (ValueError, RuntimeError, OSError) as e:
        local.avisar("ArchMuse", str(e), error=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
