"""Cliente HTTP mínimo, sin dependencias nuevas.

`requirements.txt` no trae `requests` y no hace falta añadirlo por esto: es
una petición GET con cabeceras, que `urllib.request` de la librería estándar
cubre entero. Identificarse con un User-Agent propio (no el de un navegador)
es la práctica correcta contra un servicio de datos abiertos gubernamental:
dice honestamente quién y qué está pidiendo.
"""
from __future__ import annotations

import urllib.error
import urllib.request
from email.utils import parsedate_to_datetime
from typing import Optional, Tuple

from .errores import ErrorDeRed

USER_AGENT = "ArchMuse-Ingesta/1.0 (uso interno; herramienta de arquitectura)"


def obtener(url: str, accept: str = "application/json", timeout: float = 20.0, reintentos: int = 2) -> bytes:
    """GET con reintentos simples. Devuelve los bytes crudos: decidir cómo
    interpretarlos (JSON, XML) es responsabilidad de quien llama, no de este
    módulo, que no sabe nada de BOE ni de ninguna fuente en particular."""
    return obtener_con_cabeceras(url, accept=accept, timeout=timeout, reintentos=reintentos)[0]


def obtener_con_cabeceras(
    url: str, accept: str = "application/json", timeout: float = 20.0, reintentos: int = 2
) -> Tuple[bytes, Optional[str]]:
    """Igual que `obtener`, pero además devuelve `Last-Modified` (ISO 8601,
    `None` si el servidor no lo declara). Separado de `obtener` en vez de
    cambiar su firma: casi ningún llamante (BOE) necesita la cabecera, y
    `fuentes/codigotecnico.py` sí — un PDF sin fecha propia de "publicación"
    en el cuerpo del documento, a diferencia del XML del BOE."""
    ultimo_error: Exception = RuntimeError("sin intentos")
    for _ in range(reintentos + 1):
        peticion = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
                cuerpo = respuesta.read()
                crudo_last_modified = respuesta.headers.get("Last-Modified")
                last_modified = None
                if crudo_last_modified:
                    try:
                        last_modified = parsedate_to_datetime(crudo_last_modified).isoformat()
                    except (TypeError, ValueError):
                        last_modified = None  # cabecera presente pero no parseable: no inventar una fecha
                return cuerpo, last_modified
        except urllib.error.HTTPError as exc:
            # Un 4xx no se soluciona reintentando: es la fuente diciendo que
            # la petición está mal formada o el recurso no existe.
            raise ErrorDeRed(url, exc) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            ultimo_error = exc
    raise ErrorDeRed(url, ultimo_error)
