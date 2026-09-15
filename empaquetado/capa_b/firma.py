# -*- coding: utf-8 -*-
"""Firma de los paquetes de ArchMuse (PRD 2026-09-15, actualizaciones automáticas).

**Qué garantiza.** Un `.archmuse` sólo se instala si lo firmó quien tiene la clave
privada de ArchMuse. La clave pública va aquí dentro, en la capa B.

**Cómo va la firma: dentro del propio paquete.** El `.archmuse` lleva
`MANIFIESTO.json` —la versión y el SHA-256 de cada fichero— y
`MANIFIESTO.firma`, la firma Ed25519 de ese manifiesto en base64. Verificar es:
la firma cuadra con la clave pública, cada fichero del zip tiene el hash del
manifiesto, no sobra ni falta ninguno y la versión es la de `version.json`. Un
solo fichero que se reparte igual por GitHub que por WhatsApp.

**Ed25519 en Python puro, a propósito** (la implementación de referencia de la RFC
8032, §6). El runtime de la beta no trae `cryptography`, y añadirla obligaría a
reinstalar la capa A con un `.exe`, que es justo lo que las actualizaciones
automáticas vienen a evitar. Verificar un paquete cuesta unos milisegundos. Se
comprueba contra los vectores de la RFC y contra `cryptography`
(`tests/test_actualizaciones.py`).

Sólo biblioteca estándar.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import zipfile
from typing import Optional

#: La clave pública de ArchMuse (32 bytes en hexadecimal). La privada vive FUERA
#: del repositorio; ver `empaquetado/construir.py`.
CLAVE_PUBLICA_HEX = "02bf91bf6b58496ba5f89b6a9578bad8b368395b23c2d8691399ebb4dcf09b19"

NOMBRE_MANIFIESTO = "MANIFIESTO.json"
NOMBRE_FIRMA = "MANIFIESTO.firma"
FORMATO = 1

# ── Ed25519, RFC 8032 §6 ────────────────────────────────────────────────────

_p = 2 ** 255 - 19
_q = 2 ** 252 + 27742317777372353535851937790883648493
_d = -121665 * pow(121666, _p - 2, _p) % _p
_raiz_de_menos_uno = pow(2, (_p - 1) // 4, _p)


def _sha512(datos: bytes) -> bytes:
    return hashlib.sha512(datos).digest()


def _sumar(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % _p
    B = (P[1] + P[0]) * (Q[1] + Q[0]) % _p
    C = 2 * P[3] * Q[3] * _d % _p
    D = 2 * P[2] * Q[2] % _p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _p, G * H % _p, F * G % _p, E * H % _p)


def _multiplicar(s: int, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _sumar(Q, P)
        P = _sumar(P, P)
        s >>= 1
    return Q


def _iguales(P, Q) -> bool:
    if (P[0] * Q[2] - Q[0] * P[2]) % _p != 0:
        return False
    return (P[1] * Q[2] - Q[1] * P[2]) % _p == 0


def _recuperar_x(y: int, signo: int) -> Optional[int]:
    if y >= _p:
        return None
    x2 = (y * y - 1) * pow(_d * y * y + 1, _p - 2, _p)
    if x2 == 0:
        return None if signo else 0
    x = pow(x2, (_p + 3) // 8, _p)
    if (x * x - x2) % _p != 0:
        x = x * _raiz_de_menos_uno % _p
    if (x * x - x2) % _p != 0:
        return None
    if (x & 1) != signo:
        x = _p - x
    return x


_gy = 4 * pow(5, _p - 2, _p) % _p
_gx = _recuperar_x(_gy, 0)
_G = (_gx, _gy, 1, _gx * _gy % _p)


def _comprimir(P) -> bytes:
    zinv = pow(P[2], _p - 2, _p)
    x = P[0] * zinv % _p
    y = P[1] * zinv % _p
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _descomprimir(s: bytes):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    signo = y >> 255
    y &= (1 << 255) - 1
    x = _recuperar_x(y, signo)
    if x is None:
        return None
    return (x, y, 1, x * y % _p)


def _expandir(semilla: bytes):
    if len(semilla) != 32:
        raise ValueError("la clave privada tiene que ser de 32 bytes")
    h = _sha512(semilla)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def _sha512_modq(datos: bytes) -> int:
    return int.from_bytes(_sha512(datos), "little") % _q


def clave_publica_de(semilla: bytes) -> bytes:
    a, _prefijo = _expandir(semilla)
    return _comprimir(_multiplicar(a, _G))


def firmar(semilla: bytes, mensaje: bytes) -> bytes:
    a, prefijo = _expandir(semilla)
    A = _comprimir(_multiplicar(a, _G))
    r = _sha512_modq(prefijo + mensaje)
    Rs = _comprimir(_multiplicar(r, _G))
    h = _sha512_modq(Rs + A + mensaje)
    s = (r + h * a) % _q
    return Rs + int.to_bytes(s, 32, "little")


def verificar(publica: bytes, mensaje: bytes, firma: bytes) -> bool:
    if len(publica) != 32 or len(firma) != 64:
        return False
    A = _descomprimir(publica)
    if A is None:
        return False
    Rs = firma[:32]
    R = _descomprimir(Rs)
    if R is None:
        return False
    s = int.from_bytes(firma[32:], "little")
    if s >= _q:
        return False
    h = _sha512_modq(Rs + publica + mensaje)
    return _iguales(_multiplicar(s, _G), _sumar(R, _multiplicar(h, A)))


# ── el manifiesto del paquete ───────────────────────────────────────────────

def _sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _canonico(manifiesto: dict) -> bytes:
    return json.dumps(manifiesto, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def firmar_carpeta(carpeta: str, semilla: bytes) -> str:
    """Escribe `MANIFIESTO.json` y `MANIFIESTO.firma` en la capa B `carpeta`,
    antes de comprimirla. Devuelve la versión firmada."""
    with open(os.path.join(carpeta, "version.json"), encoding="utf-8") as f:
        version = json.load(f)["version"]
    ficheros = {}
    for raiz, _dirs, nombres in os.walk(carpeta):
        for nombre in nombres:
            ruta = os.path.join(raiz, nombre)
            relativa = os.path.relpath(ruta, carpeta).replace(os.sep, "/")
            if relativa in (NOMBRE_MANIFIESTO, NOMBRE_FIRMA):
                continue
            with open(ruta, "rb") as f:
                ficheros[relativa] = _sha256(f.read())
    datos = _canonico({"formato": FORMATO, "version": version, "ficheros": ficheros})
    with open(os.path.join(carpeta, NOMBRE_MANIFIESTO), "wb") as f:
        f.write(datos)
    with open(os.path.join(carpeta, NOMBRE_FIRMA), "wb") as f:
        f.write(base64.b64encode(firmar(semilla, datos)))
    return version


def clave_publica() -> bytes:
    try:
        clave = bytes.fromhex(CLAVE_PUBLICA_HEX)
    except ValueError:
        clave = b""
    if len(clave) != 32:
        raise ValueError("esta versión de ArchMuse no lleva una clave pública válida")
    return clave


def verificar_paquete(ruta: str, publica: Optional[bytes] = None) -> str:
    """La versión de un `.archmuse` firmado por ArchMuse, o ValueError con el
    motivo, redactado para el registro y para la ventana de aviso."""
    publica = clave_publica() if publica is None else publica
    try:
        paquete = zipfile.ZipFile(ruta)
    except (OSError, zipfile.BadZipFile):
        raise ValueError("el fichero no es un paquete de ArchMuse")
    with paquete:
        nombres = set(paquete.namelist())
        if NOMBRE_MANIFIESTO not in nombres or NOMBRE_FIRMA not in nombres:
            raise ValueError("el paquete no está firmado por ArchMuse: no se instala")
        datos = paquete.read(NOMBRE_MANIFIESTO)
        try:
            firma = base64.b64decode(paquete.read(NOMBRE_FIRMA), validate=True)
        except ValueError:
            firma = b""
        if not verificar(publica, datos, firma):
            raise ValueError("la firma del paquete no es la de ArchMuse: no se instala")
        try:
            manifiesto = json.loads(datos.decode("ascii"))
            ficheros = manifiesto["ficheros"]
            version = manifiesto["version"]
        except (ValueError, KeyError, TypeError):
            raise ValueError("el manifiesto firmado del paquete no se puede leer")
        contenido = nombres - {NOMBRE_MANIFIESTO, NOMBRE_FIRMA}
        contenido = {n for n in contenido if not n.endswith("/")}
        if contenido != set(ficheros):
            sobran = sorted(contenido - set(ficheros))
            faltan = sorted(set(ficheros) - contenido)
            raise ValueError("el paquete no es el que se firmó (sobran %s, faltan %s): no se "
                             "instala" % (sobran[:3] or "nada", faltan[:3] or "nada"))
        for nombre, huella in ficheros.items():
            if _sha256(paquete.read(nombre)) != huella:
                raise ValueError("el paquete se ha modificado después de firmarlo (%s): no se "
                                 "instala" % nombre)
        try:
            declarada = json.loads(paquete.read("version.json").decode("utf-8")).get("version")
        except (KeyError, ValueError, AttributeError):
            declarada = None
        if declarada != version:
            raise ValueError("el paquete dice ser la %s y su firma es de la %s: no se instala"
                             % (declarada, version))
    return version
