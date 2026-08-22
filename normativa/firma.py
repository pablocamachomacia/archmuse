# -*- coding: utf-8 -*-
"""El hash de contenido de una regla firmada: qué se hashea, exactamente.

PRD: `docs/prd/2026-08-22-corpus-firmado-dbsi3-evacuacion.md` §2.2.

**Qué problema resuelve.** El bloque `firma: {curador, fecha}` del PRD del
21-08 es una declaración nominal: dice quién aprobó, no QUÉ aprobó. Sin un
ancla al contenido, una edición posterior del YAML dejaría la firma intacta
sobre una regla distinta — y la validación 19 seguiría pasando. Este módulo
define la única serialización canónica sobre la que se firma; la validación 20
(`normativa/validacion.py`) la recomputa en cada carga y rechaza el fichero si
no coincide (fail-closed: la materia cae a `sin_cobertura`).

**Qué se hashea.** `{"norma": <bloque norma completo>, "regla": <la regla SIN
la clave "firma">}`, tras `loader.normalizar_fechas` (para que dé igual si una
fecha viene como `date` de PyYAML o como cadena), serializado con
`json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)` y
hasheado en UTF-8 con SHA-256.

- **Se excluyen los metadatos de flujo — `firma`, `estado` y `tags` — y nada
  más.** `firma` es autorreferencial; `estado` cambia precisamente al firmar
  (BORRADOR → FIRMADA), y `tags` es donde el flujo del 21-08 apunta cosas como
  `firmado_por:...`. Si entraran en el hash, la huella impresa en la hoja de
  revisión (computada sobre el borrador) nunca coincidiría con la de la regla
  firmada, y el ancla papel→corpus se rompería. La firma avala el CONTENIDO
  normativo (cita, literal, aplicabilidad, parámetro, mensajes, vigencia), no
  el estado del expediente.
- **Se incluye la `norma` entera** (cita, literal, hashes de fuente): la firma
  avala también que la cita es esa, no solo la tabla de valores.
- Los comentarios y el formato del YAML no entran: se hashea el contenido
  parseado. El nivel de bytes lo cubre git (`NORMATIVE_ENGINE.md` §11).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from . import loader

#: Claves de la regla que NO entran en la serialización canónica. Son los
#: metadatos del expediente, que cambian al firmar; todo lo demás es contenido
#: normativo y sí se firma.
CLAVES_DE_FLUJO = frozenset({"firma", "estado", "tags"})


def serializacion_canonica(norma: Dict[str, Any], regla: Dict[str, Any]) -> str:
    """La forma exacta que se firma. Determinista: mismas claves y valores →
    misma cadena, da igual el orden del YAML, las comillas o los comentarios —
    y estable a través del acto de firmar (excluye `CLAVES_DE_FLUJO`)."""
    regla_contenido = {k: v for k, v in regla.items() if k not in CLAVES_DE_FLUJO}
    doc = loader.normalizar_fechas({"norma": norma, "regla": regla_contenido})
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_de_contenido_firmado(norma: Dict[str, Any], regla: Dict[str, Any]) -> str:
    """SHA-256 (64 hex) de la serialización canónica de `norma` + `regla`."""
    return hashlib.sha256(
        serializacion_canonica(norma, regla).encode("utf-8")).hexdigest()
