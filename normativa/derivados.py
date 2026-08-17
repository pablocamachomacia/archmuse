"""Datos derivados del municipio: zona climática CTE y densidad urbana.

Migrados desde `analyzer/cte_zonas.py`, que era la única fuente de verdad
ciudad->zona del proyecto. Ahora están indexados por CÓDIGO INE en vez de por
nombre de ciudad, de modo que hay una sola lista de municipios en todo el
sistema en lugar de tres (`cte_zonas.ZONAS_CTE`, `cte_zonas.CIUDADES_DENSIDAD`
y la que había en `static/app.js`).

`analyzer/cte_zonas.py` mantiene sus funciones públicas como fachada: sigue
aceptando un nombre de ciudad, resuelve el código por el registro y pregunta
aquí. Ningún llamador existente cambia.

Sigue siendo orientativo por municipio: la zona real depende de la altitud
exacta de la parcela. Cuando exista un Fact de altitud, esto pasará a ser el
nivel de repliegue, no la respuesta.
"""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Dict, Optional

import yaml

DERIVADOS = Path(__file__).resolve().parent / "geografia" / "es" / "derivados"


@functools.lru_cache(maxsize=1)
def _zonas() -> Dict[str, str]:
    with (DERIVADOS / "zona_climatica.yaml").open(encoding="utf-8") as f:
        return yaml.safe_load(f)["zonas"] or {}


@functools.lru_cache(maxsize=1)
def _densidades() -> Dict[str, str]:
    with (DERIVADOS / "densidad_urbana.yaml").open(encoding="utf-8") as f:
        return yaml.safe_load(f)["densidades"] or {}


def zona_climatica(codigo_ine: str) -> Optional[str]:
    """Zona climática de invierno (A-E) del municipio, o None.

    Devuelve None —no un valor por defecto— cuando no se conoce. Quien llame
    decide qué hacer con el desconocimiento y está obligado a declararlo; un
    repliegue silencioso aquí sería el Bug #1 otra vez.
    """
    return _zonas().get(codigo_ine)


def densidad_urbana(codigo_ine: str) -> Optional[str]:
    """Densidad urbana ("alta"/"media"/"baja") del municipio, o None."""
    return _densidades().get(codigo_ine)
