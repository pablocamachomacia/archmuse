"""Zona climática CTE DB-HE y densidad urbana por ciudad — FACHADA.

Las tablas ya no viven aquí. Se han migrado a
`normativa/geografia/es/derivados/`, indexadas por código INE en vez de por
nombre de ciudad, para que exista **una sola lista de municipios** en todo el
sistema. Antes había tres divergiendo en paralelo: `ZONAS_CTE`,
`CIUDADES_DENSIDAD` y `CIUDAD_A_CCAA` en `static/app.js`.

Este módulo se conserva porque `app.py` lo consume y su firma no cambia:
sigue aceptando un nombre de ciudad escrito a mano y sigue replegando al valor
por defecto cuando no lo reconoce. **El comportamiento observable es idéntico
al anterior**; lo único que ha cambiado es de dónde salen los datos.

El repliegue silencioso a "C"/"media" se mantiene DELIBERADAMENTE aquí, aunque
contradiga el principio de "nunca silencio" del subsistema normativo: cambiarlo
ahora sería una regresión de comportamiento. Corregirlo es trabajo de la Fase 1,
donde `normativa.api.contexto_territorial` ya devuelve `None` y declara la
asunción en vez de replegar.

Sigue siendo orientativo por municipio: la zona real depende de la altitud
exacta de la parcela, no solo del término municipal.
"""
from __future__ import annotations

import unicodedata
from typing import Optional

from normativa.derivados import densidad_urbana as _densidad_por_codigo
from normativa.derivados import zona_climatica as _zona_por_codigo
from normativa.registro import registro

DEFAULT_ZONA_CTE = "C"
DEFAULT_DENSIDAD_URBANA = "media"


def _normalize(text: str) -> str:
    """Se conserva por compatibilidad con quien lo importara."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower().strip()


def _codigo_de_ciudad(ciudad: str) -> Optional[str]:
    """Nombre escrito a mano -> código INE, o None si no se resuelve.

    Un nombre ambiguo cuenta aquí como no resuelto —y por tanto repliega al
    valor por defecto— para no cambiar el comportamiento de esta fachada. El
    camino que sí pregunta al usuario es `normativa.api.resolver_ambito`.
    """
    if not ciudad:
        return None
    try:
        codigos = registro().buscar_municipio(ciudad)
    except Exception:
        return None
    return codigos[0] if len(codigos) == 1 else None


def get_zona_cte(ciudad: str) -> str:
    """Zona climática CTE DB-HE para `ciudad` (case/tildes-insensitive).
    Si no se reconoce la ciudad, devuelve `DEFAULT_ZONA_CTE`."""
    codigo = _codigo_de_ciudad(ciudad)
    if codigo is None:
        return DEFAULT_ZONA_CTE
    return _zona_por_codigo(codigo) or DEFAULT_ZONA_CTE


def get_densidad_urbana(ciudad: str) -> str:
    """Densidad urbana ("alta"/"media"/"baja") para `ciudad`
    (case/tildes-insensitive). Si no se reconoce, devuelve
    `DEFAULT_DENSIDAD_URBANA`."""
    codigo = _codigo_de_ciudad(ciudad)
    if codigo is None:
        return DEFAULT_DENSIDAD_URBANA
    return _densidad_por_codigo(codigo) or DEFAULT_DENSIDAD_URBANA
