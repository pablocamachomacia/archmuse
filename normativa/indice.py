"""Índice SQLite derivado del corpus.

**Es caché, nunca fuente de verdad** (`NORMATIVE_ENGINE.md` §11). Se genera a
partir de los ficheros YAML, se sella con la huella del corpus y se puede
borrar y regenerar en cualquier momento sin pérdida. Si la huella no coincide,
se reconstruye solo.

Git es la base de datos append-only con revisión: historial inmutable, diff
legible por un curador no programador, autoría y revisión por PR. Construir un
CMS para conseguir eso sería reimplementar git peor. El índice existe solo
para no releer cientos de YAML en cada petición.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Optional

from .loader import RAIZ, cargar, huella_corpus

RUTA_INDICE = RAIZ / ".indice.sqlite"

ESQUEMA_SQL = """
CREATE TABLE IF NOT EXISTS sello (huella TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS regla (
    concept_id      TEXT NOT NULL,
    instance_id     TEXT NOT NULL,
    ambito          TEXT NOT NULL,
    materia         TEXT NOT NULL,
    tipo            TEXT NOT NULL,
    prioridad       TEXT NOT NULL,
    nivel           TEXT NOT NULL,
    vigencia_desde  TEXT NOT NULL,
    vigencia_hasta  TEXT,
    ruta            TEXT NOT NULL,
    PRIMARY KEY (concept_id, instance_id)
);

-- La clave de consulta del resolver: (ámbito, materia, vigencia).
CREATE INDEX IF NOT EXISTS ix_regla_ambito_materia ON regla (ambito, materia);
CREATE INDEX IF NOT EXISTS ix_regla_vigencia ON regla (vigencia_desde, vigencia_hasta);
"""


def _conectar(ruta: Optional[Path] = None) -> sqlite3.Connection:
    con = sqlite3.connect(ruta or RUTA_INDICE)
    con.row_factory = sqlite3.Row
    return con


def sellado(con: sqlite3.Connection) -> Optional[str]:
    try:
        fila = con.execute("SELECT huella FROM sello LIMIT 1").fetchone()
    except sqlite3.OperationalError:
        return None
    return fila["huella"] if fila else None


def reconstruir(ambitos: Optional[List[str]] = None, ruta: Optional[Path] = None) -> int:
    """Reconstruye el índice desde los ficheros. Devuelve nº de reglas.

    Solo entra al índice lo que ha pasado la validación: el índice nunca puede
    contener una regla que el loader haya rechazado, o el fail-closed se
    perdería en la siguiente consulta.
    """
    from . import catalogos

    ambitos = ambitos or _todos_los_ambitos()
    resultado = cargar(ambitos)

    con = _conectar(ruta)
    with con:
        con.executescript(ESQUEMA_SQL)
        con.execute("DELETE FROM regla")
        con.execute("DELETE FROM sello")
        n = 0
        for fichero in resultado.ficheros:
            for r in fichero.doc.get("reglas") or []:
                ap = r.get("aplicabilidad") or {}
                v = r.get("vigencia") or {}
                con.execute(
                    "INSERT OR REPLACE INTO regla VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        r["concept_id"], r["instance_id"], ap.get("ambito", "es"),
                        r["materia"], r["tipo"], r["prioridad"],
                        catalogos.nivel_de_ambito(ap.get("ambito", "es")),
                        str(v.get("vigencia_desde")),
                        str(v["vigencia_hasta"]) if v.get("vigencia_hasta") else None,
                        str(fichero.ruta.relative_to(RAIZ)),
                    ),
                )
                n += 1
        con.execute("INSERT INTO sello VALUES (?)", (huella_corpus(),))
    con.close()
    return n


def _todos_los_ambitos() -> List[str]:
    """Ámbitos presentes en disco. Solo para reconstruir el índice completo;
    la consulta normal nunca recorre el corpus entero."""
    ambitos = ["es"]
    base = RAIZ / "es"
    if not base.is_dir():
        return ambitos
    for com in sorted(base.iterdir()):
        if not com.is_dir() or com.name == "estatal":
            continue
        codigo = com.name.split("-")[0]
        ambitos.append(f"es.{codigo}")
        munis = com / "municipios"
        if munis.is_dir():
            for m in sorted(munis.iterdir()):
                if m.is_dir():
                    ambitos.append(f"es.{codigo}.{m.name.split('-')[0]}")
    return ambitos


def asegurar_indice(ruta: Optional[Path] = None) -> bool:
    """Reconstruye si el sello no coincide. Devuelve True si reconstruyó.

    Es lo que hace del índice un artefacto desechable: nadie tiene que
    acordarse de regenerarlo tras editar un YAML.
    """
    ruta = ruta or RUTA_INDICE
    if not Path(ruta).exists():
        reconstruir(ruta=ruta)
        return True
    con = _conectar(ruta)
    actual = sellado(con)
    con.close()
    if actual != huella_corpus():
        reconstruir(ruta=ruta)
        return True
    return False
