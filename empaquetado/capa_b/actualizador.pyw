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
import threading
import time
import traceback
import zipfile
from typing import Optional

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


#: Tope duro de cada orden, en segundos. Si se pasa, el vigilante lo apunta,
#: deja el resultado para el instalador y termina el proceso. El instalador
#: espera un poco más que esto (`empaquetado/ArchMuse-Beta.iss`; un test lo
#: compara). `activar` incluye el plazo de arranque del servidor.
LIMITES_S = {
    "activar": local.PLAZO_ARRANQUE_S + 60,
    "instalar": local.PLAZO_ARRANQUE_S + 120,      # descomprimir el .archmuse, además
    "volver": local.PLAZO_ARRANQUE_S + 60,
    "parar": 60,
    "desinstalar": 60,
}

_paso_actual = "empezar"


def _paso(texto: str) -> None:
    """Dónde va la orden: lo que dirá el vigilante si se agota el tope."""
    global _paso_actual
    _paso_actual = texto


def vigilar(segundos: float, resultado: Optional[str]) -> threading.Timer:
    """Si la orden no ha terminado en `segundos`: lo apunta, deja el resultado
    para el instalador y termina el proceso. Sin esto, cualquier cosa que se
    quede esperando dentro deja al instalador esperando para siempre (en la VM
    limpia, el 2026-09-14, fue una ventana de mensaje que nadie veía)."""
    def vencido():
        texto = ("ArchMuse no ha terminado en %d s. Se había quedado en: %s. Mándanos la "
                 "carpeta %s." % (segundos, _paso_actual, local.carpeta_registro()))
        local.registrar("actualizador: " + texto)
        if resultado:
            try:
                local.escribir_resultado(resultado, False, texto)
            except OSError:
                pass
        os._exit(3)

    temporizador = threading.Timer(segundos, vencido)
    temporizador.daemon = True
    temporizador.start()
    return temporizador


def _parar_o_abortar() -> None:
    local.parar_servidor()
    if local.servidor_vivo() is not None:
        raise RuntimeError("El ArchMuse que está en marcha no se deja parar. "
                           "No se ha cambiado nada. Reinicia el ordenador y vuelve a probar.")


def activar(version: str, arrancar: bool = True):
    # Lo primero, antes de parar o mover nada (enmienda del PRD, 2026-09-14):
    # nuestra carpeta en las rutas de confianza de AutoCAD. Con AutoCAD abierto
    # y algo que escribir, se para aquí sin haber cambiado nada.
    _paso("añadir la carpeta a las rutas de confianza de AutoCAD")
    try:
        perfiles = local.cambiar_confianza_con_autocad_cerrado()
    except RuntimeError as e:
        raise RuntimeError("ArchMuse no ha podido añadir su carpeta a las rutas de confianza "
                           "de AutoCAD: %s. No se ha cambiado nada." % e)
    if perfiles:
        local.registrar("ruta de confianza añadida en %d perfil(es) de AutoCAD" % perfiles)
    _paso("parar el ArchMuse que estuviera en marcha")
    _parar_o_abortar()
    _paso("apuntar app\\actual a la versión %s" % version)
    previa = local.apuntar_actual(version)
    _paso("copiar el comando al paquete de AutoCAD")
    try:
        local.copiar_lsp_al_bundle(version)
    except RuntimeError as e:
        # Sin esto, lo siguiente que vería él es «comando desconocido» en AutoCAD.
        raise RuntimeError(
            "ArchMuse %s está instalado, pero AutoCAD no va a encontrar el comando "
            "ARCHMUSE: %s. Vuelve a ejecutar el instalador; si sigue igual, avísanos."
            % (version, e))
    if arrancar:
        _arrancar_con_reintentos(version)
    local.registrar("activada la versión %s (antes: %s)" % (version, previa))
    return previa


def _arrancar_con_reintentos(version: str) -> None:
    """Lanza el servidor y espera a que conteste, dentro de `PLAZO_ARRANQUE_S`.

    **Si Python no puede abrir el script (código 2), espera y vuelve a
    intentarlo** mientras quede plazo: 2, 4, 8 y luego 10 s entre intentos. En
    la VM limpia, el 2026-09-14, pasó sólo durante la instalación y minutos
    después el mismo arranque tardaba 0,8 s. **Cualquier otro código no se
    reintenta**: es un fallo que se repetiría igual, y se dice en el acto."""
    limite = time.monotonic() + local.PLAZO_ARRANQUE_S
    intento = 0
    while True:
        intento += 1
        _paso("arrancar el servidor (intento %d)" % intento)
        desde = local.tamano_del_registro()
        desde_errores = local.tamano_de(local.fichero_de_errores_del_lanzador())
        proceso = local.arrancar_lanzador()
        _paso("esperar a que el servidor conteste (intento %d)" % intento)
        restante = max(0.0, limite - time.monotonic())
        if local.esperar_servidor(version, restante, proceso) is not None:
            if intento > 1:
                local.registrar("el servidor ha arrancado al intento %d" % intento)
            return
        espera = min(2 ** intento, 10)
        if proceso.poll() == local.NO_PUEDE_ABRIR_EL_SCRIPT and time.monotonic() + espera < limite:
            local.registrar("Python no ha podido abrir el programa del servidor (código 2, intento %d): "
                            "reintento en %d s" % (intento, espera))
            time.sleep(espera)
            continue
        raise RuntimeError(local.por_que_no_contesta(version, proceso, local.PLAZO_ARRANQUE_S,
                                                     desde, desde_errores, intento))


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
    p.add_argument("--silencioso", action="store_true",
                   help="ninguna ventana: quien lo lanza es otro programa, que lee --resultado")
    p.add_argument("--resultado", metavar="FICHERO",
                   help="deja aquí OK o ERROR y el mensaje (lo lee el instalador)")
    p.add_argument("--sin-arrancar", action="store_true")
    a = p.parse_args(argv)
    arrancar = not a.sin_arrancar
    orden = next(o for o in LIMITES_S if getattr(a, o))
    vigilante = vigilar(LIMITES_S[orden], a.resultado)

    try:
        mensaje = ""
        try:
            if a.instalar:
                version = instalar(a.instalar, arrancar)
                mensaje = "ArchMuse %s instalado. %s" % (version, CERRAR_AUTOCAD)
            elif a.volver:
                anterior, activa = volver(arrancar)
                mensaje = ("ArchMuse ha vuelto a la versión %s (estaba en la %s). %s"
                           % (anterior, activa, CERRAR_AUTOCAD))
            elif a.activar:
                activar(a.activar, arrancar)
                mensaje = "ArchMuse %s está en marcha." % a.activar
            elif a.parar:
                _paso("parar el servidor")
                local.parar_servidor()
            elif a.desinstalar:
                _paso("quitar la ruta de confianza y parar el servidor")
                desinstalar()
        except (ValueError, RuntimeError, OSError) as e:
            return _fallo(a, str(e))
        except Exception as e:
            local.registrar("actualizador, error inesperado:\n" + traceback.format_exc())
            return _fallo(a, "ArchMuse ha tenido un error inesperado (%s). Los detalles están en "
                             "%s: mándanos esa carpeta." % (type(e).__name__, local.carpeta_registro()))
        if mensaje and not a.silencioso:
            local.avisar("ArchMuse", mensaje)
        if a.resultado:
            try:
                local.escribir_resultado(a.resultado, True, mensaje)
            except OSError as e:
                local.registrar("no se ha podido escribir el resultado: %s" % e)
        return 0
    finally:
        vigilante.cancel()


def _fallo(a, texto: str) -> int:
    """**Con `--silencioso`, ni una ventana.** Quien espera es otro programa: una
    ventana de mensaje dentro de un proceso que alguien espera lo deja colgado
    si nadie la ve (VM limpia, 2026-09-14: 14 minutos). Queda en el registro y en
    `--resultado`, y lo enseña quien lo lanzó."""
    if a.silencioso:
        local.registrar("ArchMuse: %s" % texto)
    else:
        local.avisar("ArchMuse", texto, error=True)
    if a.resultado:
        try:
            local.escribir_resultado(a.resultado, False, texto)
        except OSError as e:
            local.registrar("no se ha podido escribir el resultado: %s" % e)
    return 1


if __name__ == "__main__":
    sys.exit(main())
