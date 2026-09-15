# -*- coding: utf-8 -*-
"""Carpetas temporales de los tests que se borran solas.

**Por qué existe (2026-09-15).** Treinta y un ficheros de `tests/` creaban al
importarse una carpeta con `tempfile.mkdtemp(prefix="archmuse_test_…")` —para
apuntar `ARCHMUSE_DATA_DIR` antes de `import app`— y ninguno la borraba. En
`%TEMP%` había 6.009, desde el 2 de agosto. Ahora todos piden la carpeta aquí.

**Qué borra: sólo lo que ha creado ESTE proceso.** No se barre `%TEMP%` por
nombre al terminar: otra suite en marcha a la vez perdería su base de datos a
mitad de un test.

**Cuándo:** al acabar la sesión de pytest (`conftest.pytest_sessionfinish`), y
al salir el proceso (`atexit`) para los scripts de `tests/` que se ejecutan
aparte. Las dos cosas pasan también si un test falla. Un proceso que se mata
—el plazo de `test_scripts_legacy` agotado— no llega a `atexit` y deja su
carpeta: es el único caso.

`tests/test_no_deja_carpetas_temporales.py` lo vigila.
"""
from __future__ import annotations

import atexit
import gc
import os
import shutil
import tempfile
import time

PREFIJO = "archmuse_test_"

_creadas: list = []


def carpeta_temporal_de_test(prefijo: str = PREFIJO) -> str:
    """Como `tempfile.mkdtemp(prefix=prefijo)`, pero se borra al terminar."""
    if not prefijo.startswith(PREFIJO):
        raise ValueError("el prefijo tiene que empezar por %r: %r" % (PREFIJO, prefijo))
    ruta = tempfile.mkdtemp(prefix=prefijo)
    _creadas.append(ruta)
    return ruta


def _cerrar_sqlite_abiertas() -> None:
    """Cierra las conexiones SQLite que siguen vivas en este proceso.

    **Medido el 2026-09-15:** tras la suite quedó `archmuse_test_interview_api_*`.
    Ese script hace `with storage._connect() as _conn19:`, y en SQLite el `with`
    confirma la transacción pero **no cierra** la conexión: se queda abierta en
    una global, `archmuse.db` sigue abierto y Windows no lo deja borrar. `gc` no
    la cierra porque alguien la sigue apuntando. Sólo se llama al final, cuando ya
    no queda ningún test que la use."""
    import sqlite3

    for objeto in gc.get_objects():
        if isinstance(objeto, sqlite3.Connection):
            try:
                objeto.close()
            except Exception:  # noqa: BLE001 - al cerrar, cualquier fallo da igual
                pass


def borrar_carpetas_de_test() -> list:
    """Borra las carpetas que ha creado este proceso. Devuelve las que no se han
    dejado borrar (y siguen apuntadas, por si hay otro intento)."""
    # Una conexión SQLite sin cerrar mantiene `archmuse.db` abierto, y en Windows
    # un fichero abierto no se borra: `gc` cierra las que ya nadie usa, y las que
    # alguien sigue apuntando se cierran a mano si hace falta.
    gc.collect()
    quedan = []
    for ruta in list(_creadas):
        for intento in range(3):
            shutil.rmtree(ruta, ignore_errors=True)
            if not os.path.exists(ruta):
                break
            if intento == 0:
                _cerrar_sqlite_abiertas()
            time.sleep(0.2)
        if os.path.exists(ruta):
            quedan.append(ruta)
        else:
            _creadas.remove(ruta)
    return quedan


atexit.register(borrar_carpetas_de_test)
