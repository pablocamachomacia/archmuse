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

El repliegue a "C"/"media" se mantiene DELIBERADAMENTE aquí: cambiar el valor
devuelto sería una regresión de comportamiento. Lo que ha dejado de ser
silencioso, desde la tarea 6 del `REFACTOR_MASTERPLAN.md` (2026-08-18), es que
haya repliegue: `resolver_zona_cte()` devuelve, junto a la zona, si sale de la
tabla o de la suposición, y `evaluator.get_missing_data_warnings` lo publica en
`limitaciones`. El camino que además pregunta al usuario sigue siendo
`normativa.api`, donde `contexto_territorial` devuelve `None` y declara la
asunción en vez de replegar.

Sigue siendo orientativo por municipio: la zona real depende de la altitud
exacta de la parcela, no solo del término municipal.
"""
from __future__ import annotations

import unicodedata
from typing import Optional, Tuple

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


def resolver_zona_cte(ciudad: str) -> Tuple[str, bool]:
    """`(zona, resuelta)` para `ciudad`.

    `resuelta` es `False` cuando la zona devuelta es `DEFAULT_ZONA_CTE` porque
    no se ha podido averiguar la real: no se indicó ciudad, el nombre no se
    reconoce (o es ambiguo), o el municipio existe pero la tabla no le asigna
    zona. En los tres casos el análisis sigue adelante con "C" — lo que cambia
    es que ahora se puede decir que es una **suposición**.

    No basta con comparar el resultado contra "C" para saberlo: Barcelona,
    Badajoz o Santander SON zona C por dato, y avisar ahí de una suposición
    inexistente destruiría la señal. Por eso la resolución tiene que informar
    de sí misma, y esta función es el único sitio donde consta.
    """
    codigo = _codigo_de_ciudad(ciudad)
    if codigo is None:
        return DEFAULT_ZONA_CTE, False
    zona = _zona_por_codigo(codigo)
    if not zona:
        return DEFAULT_ZONA_CTE, False
    return zona, True


def get_zona_cte(ciudad: str) -> str:
    """Zona climática CTE DB-HE para `ciudad` (case/tildes-insensitive).
    Si no se reconoce la ciudad, devuelve `DEFAULT_ZONA_CTE`.

    Se conserva con su firma exacta: la usan `app.py` y varios tests. Quien
    necesite saber si el valor es dato o suposición usa `resolver_zona_cte`."""
    return resolver_zona_cte(ciudad)[0]


def get_densidad_urbana(ciudad: str) -> str:
    """Densidad urbana ("alta"/"media"/"baja") para `ciudad`
    (case/tildes-insensitive). Si no se reconoce, devuelve
    `DEFAULT_DENSIDAD_URBANA`."""
    codigo = _codigo_de_ciudad(ciudad)
    if codigo is None:
        return DEFAULT_DENSIDAD_URBANA
    return _densidad_por_codigo(codigo) or DEFAULT_DENSIDAD_URBANA
