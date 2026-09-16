# -*- coding: utf-8 -*-
"""Qué versión de ArchMuse está midiendo.

**Por qué esto existe y no es un detalle de empaquetado.** A partir de la beta
(`docs/prd/2026-09-11-beta-instalable-en-el-ordenador-del-arquitecto.md`, D-2) el
servidor deja de estar en esta máquina: vive en el ordenador del arquitecto, y
cada corrección hay que llevarla allí. Durante un rato habrá **dos ArchMuse
midiendo la misma planta con criterios distintos**, y eso produce cifras que
nadie puede reproducir después — ni él, ni nosotros con su informe delante.

Lo único que impide eso es que la versión viaje con cada medición y quede
escrita en cada línea del log. De ahí que esto sea un módulo del producto y no
una constante del instalador.

**Dos fuentes, y en este orden.** `version.json` junto a la raíz del repositorio
es lo que el paquete de la capa B trae consigo; si no está —que es el caso
cuando se trabaja sobre el repositorio— vale `VERSION_DEL_REPOSITORIO`. Nunca se
deduce de git: un servidor instalado no tiene repositorio, y una versión que
sólo se sabe calcular aquí no sirve para lo que esto existe.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

#: La versión cuando se ejecuta sobre el repositorio, sin paquete. **La pone
#: `empaquetado/construir.py`** al construir (desde el 2026-09-15): la siguiente
#: a la mayor de `empaquetado/versiones_usadas.txt`. A mano ya no.
#:
#: **Regla (Pablo, 2026-09-14): cada build que sale de esta máquina lleva un
#: número que ningún otro build ha tenido.** Hasta ese día hubo tres 0.3.1
#: distintos (commits 10a4c8b, c5dd444 y el de los reintentos); el día que haya
#: que diagnosticar algo en el ordenador de un arquitecto, la versión tiene que
#: identificar el build sin ambigüedad.
#: 0.3.4 no existe como instalador: ese número lo usó el paquete de ensayo de la
#: actualización en la VM, así que el build siguiente a 0.3.3 es 0.3.5.
#: 0.3.5 salió dos veces distinto (el del 14/09 sin C-15 y el de las capturas
#: del 15/09 con el símbolo) y 0.3.6 lo usó el paquete de ensayo: sigue 0.3.7.
#: 0.3.7 es el instalador del primer usuario (cb1cf11, `.lsp` 3.7.0). Con el
#: `.lsp` 3.7.1 ya no es ese build, así que el repositorio pasa a 0.3.8.
VERSION_DEL_REPOSITORIO = "0.3.21"

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FICHERO = os.path.join(_RAIZ, "version.json")


def _leida_del_paquete() -> Optional[str]:
    """La versión que declara el paquete instalado, o `None`.

    Cualquier fallo devuelve `None` y **no revienta la medición**: un servidor
    que no sabe decir su versión sigue sabiendo medir, y quedarse sin medir por
    un fichero de metadatos ilegible sería cambiar un problema pequeño por uno
    grande. Quien necesite distinguir «no lo sé» de una versión concreta tiene
    el `None`.
    """
    try:
        with open(_FICHERO, "r", encoding="utf-8") as fichero:
            declarada = json.load(fichero).get("version")
    except (OSError, ValueError, AttributeError):
        return None
    return declarada.strip() if isinstance(declarada, str) and declarada.strip() else None


def version() -> str:
    return _leida_del_paquete() or VERSION_DEL_REPOSITORIO


#: Dónde está el `.lsp` que acompaña a este servidor: en la capa B, junto a
#: `app.py`; en el repositorio, en `autocad/`.
_LSP_CANDIDATOS = (
    os.path.join(_RAIZ, "archmuse.lsp"),
    os.path.join(_RAIZ, "autocad", "archmuse.lsp"),
)
_VERSION_CORTA_LSP = re.compile(r'\(setq \*am:version-corta\* "([^"]+)"\)')


def lsp() -> Optional[str]:
    """La versión del `.lsp` que va con ESTE servidor, o `None`.

    **Es lo que coteja el comando antes de escribir (D-2).** El servidor va por
    la 0.3.x y el `.lsp` por la 3.x: son dos numeraciones, y comparar la parte
    mayor de una con la de la otra no casaría nunca. Lo que se compara es otra
    cosa, más fuerte: **que el `.lsp` cargado en AutoCAD sea exactamente el que
    se empaquetó con este servidor**. Actualizar con AutoCAD abierto deja el
    viejo en memoria contra el servidor nuevo, y eso es lo que tiene que cazar.

    Primero `version.json` (lo escribe `empaquetado/construir.py`); si no lo
    declara, se lee del propio fichero — en el repositorio eso hace que editar
    el `.lsp` sin volver a cargarlo en AutoCAD también se detecte.
    """
    try:
        with open(_FICHERO, "r", encoding="utf-8") as fichero:
            declarada = json.load(fichero).get("lsp")
    except (OSError, ValueError, AttributeError):
        declarada = None
    if isinstance(declarada, str) and declarada.strip():
        return declarada.strip()
    for ruta in _LSP_CANDIDATOS:
        try:
            with open(ruta, "r", encoding="utf-8") as fichero:
                encontrada = _VERSION_CORTA_LSP.search(fichero.read())
        except (OSError, UnicodeDecodeError):
            continue
        if encontrada:
            return encontrada.group(1)
    return None
