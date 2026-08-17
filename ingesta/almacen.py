"""Versionado y detección de cambios — mismo principio que el índice SQLite
de `normativa/loader.py`, aplicado al revés.

Allí: los ficheros en disco son la fuente de verdad; el índice SQLite es un
caché derivado, gitignored, que se puede borrar y regenerar. Aquí: **la
fuente oficial (BOE) es la fuente de verdad**; lo que este módulo guarda es
un caché reproducible del texto crudo, más un registro pequeño y versionado
en git de qué se vio y cuándo. La asimetría entre los dos es deliberada:

- `estado/cache/` — **gitignored**. El texto crudo de cada versión distinta
  descargada, nunca sobrescrito (`{fuente}__{identificador}__{hash12}.xml`).
  Se puede borrar en cualquier momento: el BOE mantiene acceso permanente a
  sus documentos por identificador ELI, así que volver a descargar siempre
  es posible. No es un archivo histórico irremplazable, es un caché caro de
  red pero barato de reconstruir.
- `estado/ledger.jsonl` — **versionado en git**. Una línea JSON por cada
  descarga: identificador, hash nuevo, hash anterior, estado, fecha en que
  ArchMuse lo vio. Pequeño, legible en un diff de PR, y es lo único que hace
  falta para responder "¿cuándo nos enteramos de esto?" sin conservar los
  megabytes de texto — el eje de registro de `NORMATIVE_ENGINE.md` §4.1
  aplicado al propio pipeline, no al corpus.

Módulo `almacen.py`, directorio de datos `estado/`: nombres distintos a
propósito. `normativa/` ya tropezó una vez con un módulo y un directorio de
datos del mismo nombre colisionando por precedencia de importación (ver
memoria de la Fase 0) — aquí no se repite.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .modelo import DocumentoOficial, EstadoDescarga

RAIZ = Path(__file__).resolve().parent / "estado"


def _rutas(raiz: Optional[Path]) -> tuple[Path, Path]:
    base = raiz or RAIZ
    return base / "ledger.jsonl", base / "cache"


def _ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ultimo_hash_conocido(identificador: str, fuente: str, raiz: Optional[Path] = None) -> Optional[str]:
    """El hash de la última descarga registrada de este documento, o `None`
    si nunca se vio. Recorre el ledger entero porque es append-only y
    pequeño (cientos de líneas, no millones) — el mismo argumento de escala
    que `NORMATIVE_ENGINE.md` §11 usa para preferir ficheros a una base de
    datos en el corpus."""
    ledger, _ = _rutas(raiz)
    if not ledger.exists():
        return None
    ultimo: Optional[str] = None
    with ledger.open(encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            registro = json.loads(linea)
            if registro["identificador"] == identificador and registro["fuente"] == fuente:
                ultimo = registro["hash_nuevo"]
    return ultimo


def historial(identificador: str, fuente: str, raiz: Optional[Path] = None) -> List[dict]:
    """Todas las descargas registradas de un documento, en orden. Es la
    consulta que responde "¿cuántas veces ha cambiado esto y cuándo" —
    trivial sobre un ledger append-only, imposible sobre uno que sobrescribe."""
    ledger, _ = _rutas(raiz)
    if not ledger.exists():
        return []
    salida = []
    with ledger.open(encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            registro = json.loads(linea)
            if registro["identificador"] == identificador and registro["fuente"] == fuente:
                salida.append(registro)
    return salida


def registrar(doc: DocumentoOficial, raiz: Optional[Path] = None) -> EstadoDescarga:
    """Compara contra la última versión conocida, escribe la línea del
    ledger y, si hubo cambio real, guarda el crudo. Nunca sobrescribe una
    versión anterior — ver el docstring del módulo."""
    ledger, cache = _rutas(raiz)
    anterior = ultimo_hash_conocido(doc.identificador, doc.fuente, raiz)

    if anterior is None:
        estado = "nuevo"
    elif anterior == doc.hash_texto:
        estado = "sin_cambios"
    else:
        estado = "modificado"

    ruta_cache: Optional[str] = None
    if estado != "sin_cambios":
        cache.mkdir(parents=True, exist_ok=True)
        nombre = f"{doc.fuente}__{doc.identificador}__{doc.hash_texto[:12]}.{doc.formato}"
        destino = cache / nombre
        if not destino.exists():  # idempotente: reintentar no duplica
            # `bytes_crudos` (PDF) es el original real; sin él, `texto_crudo`
            # ya lo es (caso BOE/XML) — ver el docstring de `DocumentoOficial`.
            if doc.bytes_crudos is not None:
                destino.write_bytes(doc.bytes_crudos)
            else:
                destino.write_text(doc.texto_crudo, encoding="utf-8")
        # Relativa a `estado/` y en POSIX: el ledger se versiona en git y se
        # revisa entre plataformas — una ruta absoluta con backslashes de
        # Windows sería tanto inútil en otra máquina como un diff ilegible.
        ruta_cache = f"cache/{nombre}"

    registro = EstadoDescarga(
        identificador=doc.identificador,
        fuente=doc.fuente,
        hash_anterior=anterior,
        hash_nuevo=doc.hash_texto,
        estado=estado,
        fecha_descarga=_ahora_iso(),
        ruta_cache=ruta_cache,
        url_oficial=doc.url_oficial,
        fecha_publicacion=doc.fecha_publicacion,
        referencias_boe=doc.referencias_boe,
    )

    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro.a_dict(), ensure_ascii=False) + "\n")

    return registro
