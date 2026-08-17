"""Persistencia de proyectos analizados.

Hasta 2026-08-02 Archmuse no recordaba nada: `POST /api/analizar` guardaba el
DXF en un `TemporaryDirectory` que se destruía al terminar la petición y
devolvía el JSON sin dejar rastro. Este módulo es la capa que convierte "el
análisis que estoy mirando ahora" en "un proyecto al que puedo volver mañana",
que es la precondición del Inicio con parrilla de proyectos
(`docs/prd/2026-08-02-shell-lateral-e-inicio-de-proyectos.md`).

Decisiones de diseño, tomadas del PRD `2026-08-01-gestor-de-proyectos-y-persistencia.md`:

- **SQLite de la stdlib**, no un directorio de JSON: no añade dependencia y
  evita la migración que un formato más simple obligaría a hacer después.
- **El payload se guarda tal cual**, como blob JSON. Lo que se devuelve al
  reabrir un proyecto es byte a byte lo que se devolvió al crearlo: reabrir
  no vuelve a parsear el DXF, no reevalúa reglas y **no llama a la IA**.
- **Los identificadores se generan aquí, nunca se derivan de la entrada del
  usuario.** Es la defensa contra el path traversal que el PRD señala como la
  superficie de ataque nueva que introduce la persistencia.
- **Ningún módulo de `analyzer/` importa este archivo.** El analizador no sabe
  que existe una base de datos; el sentido de la flecha es siempre app.py →
  storage, nunca evaluator → storage.

Lo que este módulo deliberadamente NO hace todavía (tareas 3, 4, 6, 12-16 del
PRD de persistencia, aún sin implementar): caché por hash de contenido,
versión del motor de análisis, versiones sucesivas de un mismo plano, estado
de sesión (vivienda/modo/encuadre) y control del espacio en disco. Guardar y
recuperar sí; reutilizar un análisis previo para ahorrarse la llamada a la IA,
todavía no.

**E2 — el modelo arquitectónico común se persiste**
(`docs/prd/2026-08-11-e2-persistencia-modelo.md`). `guardar_proyecto()` acepta
ahora un `grafo` opcional (`modelo.Grafo`, E1) y lo guarda serializado (C7) en
su propia columna, `modelo` — nunca dentro de `payload`. `obtener_modelo()` lo
reconstruye. Decisión C-E2.1 del PRD: una columna nueva en la tabla que ya
existe, no una tabla nueva — esa necesita el emparejamiento entre versiones
(`modelo.identidad.emparejar()`), que sigue sin implementarse. Una fila sin
modelo (creada antes de E2, o de un proyecto `origen="generado"`, que E2 no
migra) tiene la columna a `NULL`; `obtener_modelo()` devuelve `None`, nunca un
error.

**Fase A del entrevistador — estado de entrevista y traza de generación**
(`docs/design/2026-08-12-plan-implementacion-entrevistador.md`). Dos
extensiones aditivas, ninguna toca `proyectos.payload` ni cambia el
comportamiento de nada de lo anterior:

- **Tabla nueva `entrevistas`**: una fila por sesión de entrevista, con
  `estado` (JSON de `interview.modelo.EstadoEntrevista`) y `especificacion`
  (JSON de `interview.modelo.EspecificacionArquitectonica`, nullable hasta
  que se compile — Fase D, todavía sin implementar). Tabla nueva y no columna
  en `proyectos` porque una entrevista no tiene por qué terminar nunca en un
  proyecto generado (se puede abandonar, PRD v2 §28).
- **Columna nueva `traza_generacion` en `proyectos`**: JSON de
  `interview.modelo.TrazaDeGeneracion`, mismo patrón que la columna `modelo`
  de E2 (migración idempotente, `NULL` en filas antiguas o sin entrevista
  detrás). Persistida desde la primera implementación, no cuando exista la
  Fase F que la rellene de verdad (Decisión Pablo #2) — hoy la escribe
  únicamente quien llame a `guardar_traza_generacion()` a mano, porque
  `app.py:generar()` todavía no lo hace.

**Extractor de pliegos** (`docs/prd/2026-08-15-extractor-parametros-pliego.md`).
Tabla nueva `pliegos`: un pliego se sube y se extrae ANTES de que exista un
proyecto (el botón vive en la pantalla de "nuevo proyecto"), así que
`proyecto_id` nace `NULL` — se enlaza después con `vincular_pliego_proyecto`
si el arquitecto llega a generar un proyecto a partir de él; hasta entonces
es un borrador standalone, igual de recuperable. Guarda el PDF original
(columna `pdf`, BLOB) junto al JSON ya extraído (columna `parametros`):
reabrir un pliego nunca vuelve a llamar a la IA, mismo invariante que
`proyectos.payload`.

**Sólido Capaz persistente** (`docs/prd/2026-08-17-solido-capaz-persistente-
visor-edificio.md`). Columna nueva `solido_capaz` en `proyectos`, mismo
patrón exacto que `modelo`/`traza_generacion`: JSON, nullable, migración
idempotente, nunca dentro de `payload`. Es un snapshot (polígono final en
metros locales, altura máxima, plantas estimadas, superficie ocupada) del
Sólido Capaz calculado en el Sandbox en el momento de generar — no se
recalcula al reabrir el proyecto (Decisión del PRD, §6: snapshot con fecha,
no recálculo bajo demanda). A diferencia de `modelo`/`traza_generacion`, que
son internos, `GET /api/proyectos/<id>` sí lo expone en la respuesta cuando
existe: es el visor 3D quien lo consume directamente.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from modelo import Grafo
from modelo import cargar as _cargar_modelo
from modelo import volcar as _volcar_modelo
from modelo.serializacion import verificar_sellado as _verificar_sellado_modelo

from .interview import modelo as _interview_modelo

# Versión del esquema. Se guarda en `PRAGMA user_version` para que una
# migración futura pueda distinguir una base antigua de una recién creada sin
# tener que inspeccionar las columnas.
# 2 (E2): +columna `modelo` en `proyectos`.
# 3 (Fase A entrevistador): +tabla `entrevistas`, +columna `traza_generacion`
#   en `proyectos`.
# 4 (extractor de pliegos): +tabla `pliegos`.
# 5 (análisis de sitio): +tabla `sitios`.
# 6 (Sólido Capaz persistente): +columna `solido_capaz` en `proyectos`.
SCHEMA_VERSION = 6

# Los ids se generan con uuid4 y son hexadecimales de 12 caracteres. La
# validación no es decorativa: es lo que impide que un id llegado por la URL
# se use como si fuera una ruta.
_ID_RE = re.compile(r"^[0-9a-f]{12}$")


def data_dir() -> str:
    """Directorio de datos. `ARCHMUSE_DATA_DIR` permite apuntarlo a otro sitio
    (pruebas, o un usuario que quiera sus proyectos en otro disco)."""
    override = os.environ.get("ARCHMUSE_DATA_DIR")
    if override:
        return os.path.abspath(override)
    return os.path.join(os.path.expanduser("~"), ".archmuse")


def db_path() -> str:
    return os.path.join(data_dir(), "archmuse.db")


def _connect() -> sqlite3.Connection:
    os.makedirs(data_dir(), exist_ok=True)
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Crea el esquema si no existe. Idempotente: se puede llamar en cada
    arranque del servidor sin comprobar nada antes."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS proyectos (
                id             TEXT PRIMARY KEY,
                nombre         TEXT NOT NULL,
                origen         TEXT NOT NULL,
                creado_en      TEXT NOT NULL,
                modificado_en  TEXT NOT NULL,
                puntuacion     INTEGER,
                valoracion     TEXT,
                num_viviendas  INTEGER,
                ciudad         TEXT,
                tipologia      TEXT,
                miniatura      TEXT,
                payload        TEXT NOT NULL,
                modelo         TEXT,
                solido_capaz   TEXT
            )
            """
        )
        _migrar_columna_modelo(conn)
        _migrar_columna_traza_generacion(conn)
        _migrar_columna_solido_capaz(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS entrevistas (
                id             TEXT PRIMARY KEY,
                estado         TEXT NOT NULL,
                especificacion TEXT,
                creado_en      TEXT NOT NULL,
                modificado_en  TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pliegos (
                id             TEXT PRIMARY KEY,
                proyecto_id    TEXT,
                nombre_archivo TEXT NOT NULL,
                pdf            BLOB NOT NULL,
                parametros     TEXT NOT NULL,
                es_pliego      INTEGER NOT NULL,
                creado_en      TEXT NOT NULL,
                modificado_en  TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sitios (
                id             TEXT PRIMARY KEY,
                clave_cache    TEXT NOT NULL UNIQUE,
                proyecto_id    TEXT,
                datos          TEXT NOT NULL,
                creado_en      TEXT NOT NULL,
                modificado_en  TEXT NOT NULL
            )
            """
        )
        # Orden por defecto de la parrilla del Inicio: última modificación.
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_proyectos_modificado "
            "ON proyectos (modificado_en DESC)"
        )
        conn.execute("PRAGMA user_version = %d" % SCHEMA_VERSION)


def _migrar_columna_modelo(conn: sqlite3.Connection) -> None:
    """E2 (SCHEMA_VERSION 1 -> 2). Una base creada por E0/E1 no tiene la
    columna `modelo`: `CREATE TABLE IF NOT EXISTS` no la añade a una tabla que
    ya existe. Se comprueba con `PRAGMA table_info` y se añade si falta —
    idempotente, no toca ninguna fila existente. Sobre una base ya al día
    (incluida una recién creada, que ya nace con la columna) es un no-op."""
    columnas = {fila["name"] for fila in conn.execute("PRAGMA table_info(proyectos)").fetchall()}
    if "modelo" not in columnas:
        conn.execute("ALTER TABLE proyectos ADD COLUMN modelo TEXT")


def _migrar_columna_traza_generacion(conn: sqlite3.Connection) -> None:
    """Fase A del entrevistador (SCHEMA_VERSION 2 -> 3). Mismo criterio
    exacto que `_migrar_columna_modelo`: `PRAGMA table_info` + `ALTER TABLE`
    si falta, idempotente, no toca ninguna fila existente."""
    columnas = {fila["name"] for fila in conn.execute("PRAGMA table_info(proyectos)").fetchall()}
    if "traza_generacion" not in columnas:
        conn.execute("ALTER TABLE proyectos ADD COLUMN traza_generacion TEXT")


def _migrar_columna_solido_capaz(conn: sqlite3.Connection) -> None:
    """Sólido Capaz persistente (SCHEMA_VERSION 5 -> 6). Mismo criterio exacto
    que `_migrar_columna_modelo`/`_migrar_columna_traza_generacion`."""
    columnas = {fila["name"] for fila in conn.execute("PRAGMA table_info(proyectos)").fetchall()}
    if "solido_capaz" not in columnas:
        conn.execute("ALTER TABLE proyectos ADD COLUMN solido_capaz TEXT")


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _miniatura_de(payload: dict) -> Optional[str]:
    """Miniatura = el SVG de la primera vivienda, que `plan_svg.py` ya generó.

    No se dibuja nada nuevo ni se toca `plan_svg`: se reutiliza un SVG que ya
    viaja en el payload (~5 KB). Si el proyecto no tiene ninguna vivienda
    dibujable, se devuelve `None` y la tarjeta va sin miniatura — nunca con un
    icono de relleno (§6 del PRD)."""
    for vivienda in payload.get("viviendas") or []:
        svg = vivienda.get("svg")
        if svg:
            return svg
    return None


def _nombre_de(payload: dict, origen: str) -> str:
    archivo = (payload.get("archivo") or "").strip()
    if archivo:
        return archivo
    return "Proyecto generado" if origen == "generado" else "Proyecto sin nombre"


def _metadatos(row: sqlite3.Row) -> dict[str, Any]:
    """Fila → dict para la parrilla. Incluye la miniatura pero **no** el
    payload: la lista del Inicio no necesita 288 KB por proyecto."""
    return {
        "id": row["id"],
        "nombre": row["nombre"],
        "origen": row["origen"],
        "creado_en": row["creado_en"],
        "modificado_en": row["modificado_en"],
        "puntuacion": row["puntuacion"],
        "valoracion": row["valoracion"],
        "num_viviendas": row["num_viviendas"],
        "ciudad": row["ciudad"],
        "tipologia": row["tipologia"],
        "miniatura": row["miniatura"],
    }


def guardar_proyecto(
    payload: dict,
    origen: str = "dxf",
    grafo: Optional[Grafo] = None,
    solido_capaz: Optional[dict] = None,
) -> dict[str, Any]:
    """Guarda un análisis recién hecho y devuelve sus metadatos (con el id).

    **Muta `payload`** para escribirle `proyecto_id` *antes* de serializarlo.
    Es deliberado: así lo que se guarda en disco y lo que se devuelve por HTTP
    son el mismo objeto, y el criterio "el payload de un proyecto recién
    analizado y el de ese mismo proyecto reabierto son idénticos" se cumple
    por construcción y no por disciplina de quien llame.

    `origen` es `"dxf"` (analizado) o `"generado"` (creado por IA sin DXF de
    partida).

    `grafo` (E2) es el modelo arquitectónico común de este análisis, si
    existe. Se serializa (C7) y se guarda en su propia columna, **nunca**
    dentro de `payload`: el payload público de `/api/analizar` no cambia ni un
    byte por que exista un modelo detrás (decisión C-E2.4 del PRD de E2).
    `None` dejar la columna vacía — hoy es siempre el caso de
    `origen="generado"`, que E2 no migra.

    `solido_capaz` (Sólido Capaz persistente) es el snapshot ya calculado en
    el Sandbox al momento de generar (polígono final en metros locales,
    altura máxima, plantas estimadas, superficie ocupada), o `None` si el
    proyecto se generó sin pasar antes por el Sandbox — el caso mayoritario
    hoy. Igual que `grafo`, se guarda en su propia columna, nunca dentro de
    `payload`."""
    proyecto_id = uuid.uuid4().hex[:12]
    ahora = _ahora()
    proyecto = payload.get("proyecto") or {}
    payload["proyecto_id"] = proyecto_id
    modelo_json = _volcar_modelo(grafo) if grafo is not None else None
    solido_capaz_json = (
        json.dumps(solido_capaz, ensure_ascii=False) if solido_capaz is not None else None
    )

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO proyectos (
                id, nombre, origen, creado_en, modificado_en,
                puntuacion, valoracion, num_viviendas, ciudad, tipologia,
                miniatura, payload, modelo, solido_capaz
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proyecto_id,
                _nombre_de(payload, origen),
                origen,
                ahora,
                ahora,
                payload.get("puntuacion_global"),
                payload.get("valoracion_global"),
                len(payload.get("viviendas") or []),
                proyecto.get("ciudad"),
                proyecto.get("tipologia"),
                _miniatura_de(payload),
                json.dumps(payload, ensure_ascii=False),
                modelo_json,
                solido_capaz_json,
            ),
        )
        row = conn.execute(
            "SELECT * FROM proyectos WHERE id = ?", (proyecto_id,)
        ).fetchone()

    return _metadatos(row)


def listar_proyectos() -> list[dict[str, Any]]:
    """Todos los proyectos, del más recientemente modificado al más antiguo.

    Una base de datos ausente o vacía devuelve una lista vacía, no un error:
    el Inicio de un usuario nuevo tiene que poder pintarse igual."""
    init_db()
    with _connect() as conn:
        filas = conn.execute(
            "SELECT * FROM proyectos ORDER BY modificado_en DESC"
        ).fetchall()
    return [_metadatos(f) for f in filas]


def obtener_proyecto(proyecto_id: str) -> Optional[dict]:
    """Payload completo de un proyecto, idéntico al que devolvió `/api/analizar`
    al crearlo. Devuelve `None` si el id no existe o no tiene forma válida.

    Un payload ilegible (base manipulada a mano, esquema antiguo) devuelve
    `None` en vez de propagar el `JSONDecodeError`: un registro corrupto no
    debe impedir que el resto de la aplicación funcione."""
    if not _ID_RE.match(proyecto_id or ""):
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT payload FROM proyectos WHERE id = ?", (proyecto_id,)
        ).fetchone()
    if row is None:
        return None
    try:
        return json.loads(row["payload"])
    except (ValueError, TypeError):
        return None


def obtener_modelo(proyecto_id: str) -> Optional[Grafo]:
    """El modelo arquitectónico común (E2) de un proyecto, reconstruido desde
    su columna `modelo`. `None` si el id no tiene forma válida, el proyecto no
    existe, no tiene modelo guardado (columna `NULL` — proyectos de antes de
    E2, o `origen="generado"`, que E2 no migra) o el JSON guardado no
    reconstruye un modelo válido.

    Mismo criterio que `obtener_proyecto`: un registro corrupto (base
    manipulada a mano) devuelve `None` en vez de propagar la excepción — y
    además se verifica el sellado (I8) antes de devolverlo, porque un modelo
    cuyo hash ya no describe su contenido es tan inválido como uno
    ilegible."""
    if not _ID_RE.match(proyecto_id or ""):
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT modelo FROM proyectos WHERE id = ?", (proyecto_id,)
        ).fetchone()
    if row is None or row["modelo"] is None:
        return None
    try:
        grafo = _cargar_modelo(row["modelo"])
    except (ValueError, TypeError, KeyError):
        return None
    if not _verificar_sellado_modelo(grafo):
        return None
    return grafo


def obtener_solido_capaz(proyecto_id: str) -> Optional[dict]:
    """El snapshot del Sólido Capaz guardado junto a este proyecto, si existe
    (Sólido Capaz persistente). `None` si el id no tiene forma válida, el
    proyecto no existe, no tiene Sólido Capaz guardado (columna `NULL` — el
    caso mayoritario hoy: cualquier proyecto generado sin pasar antes por el
    Sandbox, o analizado desde un DXF) o el JSON guardado no es legible
    (misma resiliencia que `obtener_proyecto`: un registro corrupto no debe
    propagar la excepción)."""
    if not _ID_RE.match(proyecto_id or ""):
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT solido_capaz FROM proyectos WHERE id = ?", (proyecto_id,)
        ).fetchone()
    if row is None or row["solido_capaz"] is None:
        return None
    try:
        return json.loads(row["solido_capaz"])
    except (ValueError, TypeError):
        return None


def borrar_proyecto(proyecto_id: str) -> bool:
    """Borra un proyecto. Devuelve `True` si existía."""
    if not _ID_RE.match(proyecto_id or ""):
        return False
    with _connect() as conn:
        cur = conn.execute("DELETE FROM proyectos WHERE id = ?", (proyecto_id,))
    return cur.rowcount > 0


# --- Entrevista (Fase A del entrevistador) --------------------------------


def guardar_entrevista(
    estado: _interview_modelo.EstadoEntrevista,
    especificacion: Optional[_interview_modelo.EspecificacionArquitectonica] = None,
) -> dict[str, Any]:
    """Guarda (o actualiza, si `estado.sesion_id` ya existe) el estado de una
    sesión de entrevista. Se llama tras cada turno (criterio de B3 del plan:
    "estado persistido tras cada turno — sobrevive un reinicio del
    proceso") — de ahí el upsert en vez de un `INSERT` que fallaría en el
    segundo turno.

    `especificacion` es opcional y normalmente `None` hasta que la Fase D
    (compilador, todavía sin implementar) produzca una. `creado_en` se
    conserva del primer guardado; `modificado_en` se actualiza siempre.

    El id se valida con el mismo patrón `_ID_RE` que `proyecto_id` — mismo
    motivo: es responsabilidad de quien llama generarlo con
    `interview.modelo.nuevo_id()`, nunca aceptarlo de una URL sin validar."""
    if not _ID_RE.match(estado.sesion_id or ""):
        raise ValueError("EstadoEntrevista.sesion_id con formato inválido: %r" % (estado.sesion_id,))
    ahora = _ahora()
    estado_json = _interview_modelo.volcar_estado(estado)
    especificacion_json = (
        _interview_modelo.volcar_especificacion(especificacion) if especificacion is not None else None
    )
    with _connect() as conn:
        existente = conn.execute(
            "SELECT creado_en FROM entrevistas WHERE id = ?", (estado.sesion_id,)
        ).fetchone()
        creado_en = existente["creado_en"] if existente is not None else ahora
        conn.execute(
            """
            INSERT INTO entrevistas (id, estado, especificacion, creado_en, modificado_en)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                estado = excluded.estado,
                especificacion = excluded.especificacion,
                modificado_en = excluded.modificado_en
            """,
            (estado.sesion_id, estado_json, especificacion_json, creado_en, ahora),
        )
        row = conn.execute(
            "SELECT id, creado_en, modificado_en FROM entrevistas WHERE id = ?", (estado.sesion_id,)
        ).fetchone()
    return {"sesion_id": row["id"], "creado_en": row["creado_en"], "modificado_en": row["modificado_en"]}


def obtener_entrevista(sesion_id: str) -> Optional[dict[str, Any]]:
    """Recupera una sesión de entrevista. Devuelve `None` si el id no tiene
    forma válida, no existe, o el JSON guardado no reconstruye un estado
    válido (misma resiliencia que `obtener_proyecto`: un registro corrupto
    no debe propagar la excepción).

    Devuelve `{"estado": EstadoEntrevista, "especificacion":
    EspecificacionArquitectonica | None}` — nunca el `EstadoEntrevista` solo,
    para que quien llame no tenga que adivinar si la especificación existe
    todavía."""
    if not _ID_RE.match(sesion_id or ""):
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT estado, especificacion FROM entrevistas WHERE id = ?", (sesion_id,)
        ).fetchone()
    if row is None:
        return None
    try:
        estado = _interview_modelo.cargar_estado(row["estado"])
    except (ValueError, TypeError, KeyError):
        return None
    especificacion = None
    if row["especificacion"] is not None:
        try:
            especificacion = _interview_modelo.cargar_especificacion(row["especificacion"])
        except (ValueError, TypeError, KeyError):
            especificacion = None
    return {"estado": estado, "especificacion": especificacion}


def guardar_traza_generacion(traza: _interview_modelo.TrazaDeGeneracion) -> bool:
    """Persiste una `TrazaDeGeneracion` en la fila de `proyectos` a la que
    pertenece (`traza.proyecto_id`) — Decisión Pablo #2: se persiste desde
    la primera implementación, no cuando exista la Fase F que la construya
    a partir de una generación real.

    Devuelve `True` si el proyecto existía y se actualizó; `False` si
    `proyecto_id` no tiene forma válida o no corresponde a ningún proyecto
    — nunca lanza, mismo criterio que `borrar_proyecto`."""
    if not _ID_RE.match(traza.proyecto_id or ""):
        return False
    traza_json = _interview_modelo.volcar_traza(traza)
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE proyectos SET traza_generacion = ?, modificado_en = ? WHERE id = ?",
            (traza_json, _ahora(), traza.proyecto_id),
        )
    return cur.rowcount > 0


def obtener_traza_generacion(proyecto_id: str) -> Optional[_interview_modelo.TrazaDeGeneracion]:
    """La `TrazaDeGeneracion` de un proyecto, si existe. `None` si el id no
    tiene forma válida, el proyecto no existe, no tiene traza (columna
    `NULL` — todo proyecto de antes de la Fase A, o generado sin
    `contexto_cualitativo`) o el JSON guardado no reconstruye una traza
    válida."""
    if not _ID_RE.match(proyecto_id or ""):
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT traza_generacion FROM proyectos WHERE id = ?", (proyecto_id,)
        ).fetchone()
    if row is None or row["traza_generacion"] is None:
        return None
    try:
        return _interview_modelo.cargar_traza(row["traza_generacion"])
    except (ValueError, TypeError, KeyError):
        return None


# --- Pliegos (extractor de parámetros de concurso) -------------------------


def guardar_pliego(nombre_archivo: str, pdf_bytes: bytes, parametros: dict, es_pliego: bool = True) -> dict[str, Any]:
    """Guarda un pliego recién extraído. `parametros` es el dict ya
    serializado (nombre de campo -> `hechos.hecho_a_dict(...)`) que produce
    `analyzer.pliego_extractor` — se guarda tal cual, no se reinterpreta.

    `proyecto_id` nace `NULL`: el botón de importar vive en la pantalla de
    "nuevo proyecto", antes de que exista ninguna fila en `proyectos`. Se
    enlaza después con `vincular_pliego_proyecto`, si llega a usarse."""
    init_db()
    pliego_id = uuid.uuid4().hex[:12]
    ahora = _ahora()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO pliegos (
                id, proyecto_id, nombre_archivo, pdf, parametros, es_pliego, creado_en, modificado_en
            ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?)
            """,
            (
                pliego_id, nombre_archivo, pdf_bytes,
                json.dumps(parametros, ensure_ascii=False), 1 if es_pliego else 0,
                ahora, ahora,
            ),
        )
    return {
        "id": pliego_id, "proyecto_id": None, "nombre_archivo": nombre_archivo,
        "parametros": parametros, "es_pliego": es_pliego,
        "creado_en": ahora, "modificado_en": ahora,
    }


def obtener_pliego(pliego_id: str) -> Optional[dict[str, Any]]:
    """Los parámetros de un pliego ya extraído — nunca vuelve a llamar a la
    IA. No incluye el PDF binario (no hace falta para la tabla de revisión
    en pantalla). `None` si el id no tiene forma válida, no existe, o el
    JSON guardado no es legible (misma resiliencia que `obtener_proyecto`)."""
    if not _ID_RE.match(pliego_id or ""):
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, proyecto_id, nombre_archivo, parametros, es_pliego, creado_en, modificado_en "
            "FROM pliegos WHERE id = ?",
            (pliego_id,),
        ).fetchone()
    if row is None:
        return None
    try:
        parametros = json.loads(row["parametros"])
    except (ValueError, TypeError):
        return None
    return {
        "id": row["id"], "proyecto_id": row["proyecto_id"], "nombre_archivo": row["nombre_archivo"],
        "parametros": parametros, "es_pliego": bool(row["es_pliego"]),
        "creado_en": row["creado_en"], "modificado_en": row["modificado_en"],
    }


def listar_pliegos() -> list[dict[str, Any]]:
    """Metadatos de todos los pliegos guardados (sin `parametros` completos
    ni el PDF) — para el selector "verificar contra un pliego" del panel de
    proyecto. Añadido con el verificador de cumplimiento
    (`docs/prd/2026-08-15-verificador-cumplimiento-pliego.md`); el extractor
    solo necesitaba `obtener_pliego` uno a uno, no un listado."""
    init_db()
    with _connect() as conn:
        filas = conn.execute(
            "SELECT id, proyecto_id, nombre_archivo, es_pliego, creado_en, modificado_en "
            "FROM pliegos ORDER BY modificado_en DESC"
        ).fetchall()
    return [
        {
            "id": f["id"], "proyecto_id": f["proyecto_id"], "nombre_archivo": f["nombre_archivo"],
            "es_pliego": bool(f["es_pliego"]), "creado_en": f["creado_en"], "modificado_en": f["modificado_en"],
        }
        for f in filas
    ]


def guardar_sitio(clave_cache: str, datos: dict, proyecto_id: Optional[str] = None) -> dict[str, Any]:
    """Guarda (o actualiza, si `clave_cache` ya existía -- upsert) el
    resultado de `analyzer.sitio.obtener_datos_parcela`. `clave_cache` es la
    referencia catastral, o `"lat,lon"` redondeado si no había RC -- se
    cachea POR PARCELA, no por proyecto (PRD §4): dos proyectos sobre el
    mismo solar no deberían disparar una segunda consulta a Catastro/
    Overpass. `proyecto_id` es opcional y nace `NULL` si se llama antes de
    que exista un proyecto (mismo patrón que `guardar_pliego`)."""
    init_db()
    ahora = _ahora()
    datos_json = json.dumps(datos, ensure_ascii=False)
    with _connect() as conn:
        existente = conn.execute(
            "SELECT id, creado_en FROM sitios WHERE clave_cache = ?", (clave_cache,)
        ).fetchone()
        sitio_id = existente["id"] if existente is not None else uuid.uuid4().hex[:12]
        creado_en = existente["creado_en"] if existente is not None else ahora
        conn.execute(
            """
            INSERT INTO sitios (id, clave_cache, proyecto_id, datos, creado_en, modificado_en)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(clave_cache) DO UPDATE SET
                datos = excluded.datos,
                proyecto_id = COALESCE(excluded.proyecto_id, sitios.proyecto_id),
                modificado_en = excluded.modificado_en
            """,
            (sitio_id, clave_cache, proyecto_id, datos_json, creado_en, ahora),
        )
    return {"id": sitio_id, "clave_cache": clave_cache, "proyecto_id": proyecto_id, "datos": datos}


def obtener_sitio_por_clave(clave_cache: str) -> Optional[dict[str, Any]]:
    """El sitio ya cacheado para esta parcela, si existe -- consultarlo
    nunca vuelve a llamar a Catastro/Overpass. `None` si no está en caché
    o el JSON guardado no es legible (misma resiliencia que `obtener_
    proyecto`)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, proyecto_id, datos, creado_en, modificado_en FROM sitios WHERE clave_cache = ?",
            (clave_cache,),
        ).fetchone()
    if row is None:
        return None
    try:
        datos = json.loads(row["datos"])
    except (ValueError, TypeError):
        return None
    return {
        "id": row["id"], "clave_cache": clave_cache, "proyecto_id": row["proyecto_id"],
        "datos": datos, "creado_en": row["creado_en"], "modificado_en": row["modificado_en"],
    }


def obtener_sitio_de_proyecto(proyecto_id: str) -> Optional[dict[str, Any]]:
    """El sitio enlazado a este proyecto, si alguno lo está -- vía
    `guardar_sitio(..., proyecto_id=...)` o `vincular_sitio_proyecto`.
    `None` si el proyecto no tiene ningún sitio enlazado (el caso normal
    hoy: nada enlaza un sitio a un proyecto salvo que se pida
    explícitamente) o el id no tiene forma válida. Añadido para el
    georreferenciado del visor Mapbox (2026-08-15) -- primer consumidor
    real de este enlace por el lado de `sitios` (el lado de `pliegos` ya
    lo usa `pliego_conector.py` desde la Pieza 1)."""
    if not _ID_RE.match(proyecto_id or ""):
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, clave_cache, datos, creado_en, modificado_en FROM sitios WHERE proyecto_id = ? "
            "ORDER BY modificado_en DESC LIMIT 1",
            (proyecto_id,),
        ).fetchone()
    if row is None:
        return None
    try:
        datos = json.loads(row["datos"])
    except (ValueError, TypeError):
        return None
    return {
        "id": row["id"], "clave_cache": row["clave_cache"], "proyecto_id": proyecto_id,
        "datos": datos, "creado_en": row["creado_en"], "modificado_en": row["modificado_en"],
    }


def vincular_sitio_proyecto(clave_cache: str, proyecto_id: str) -> bool:
    """Enlaza un sitio ya analizado con un proyecto -- mismo criterio que
    `vincular_pliego_proyecto`: `True` solo si AMBAS filas existen (ninguna
    FK real hacia `proyectos` en SQLite)."""
    if not _ID_RE.match(proyecto_id or ""):
        return False
    with _connect() as conn:
        existe_proyecto = conn.execute("SELECT 1 FROM proyectos WHERE id = ?", (proyecto_id,)).fetchone()
        if existe_proyecto is None:
            return False
        cur = conn.execute(
            "UPDATE sitios SET proyecto_id = ?, modificado_en = ? WHERE clave_cache = ?",
            (proyecto_id, _ahora(), clave_cache),
        )
    return cur.rowcount > 0


def vincular_pliego_proyecto(pliego_id: str, proyecto_id: str) -> bool:
    """Enlaza un pliego ya extraído con el proyecto generado a partir de él
    -- usado desde la Pieza 1 (`analyzer.pliego_conector`). Devuelve `True`
    solo si AMBAS filas existen
    (`pliegos` no tiene una FK real hacia `proyectos` -- sin esta
    comprobación, `proyecto_id` podría apuntar a un proyecto que nunca
    existió, un enlace roto y silencioso)."""
    if not _ID_RE.match(pliego_id or "") or not _ID_RE.match(proyecto_id or ""):
        return False
    with _connect() as conn:
        existe_proyecto = conn.execute(
            "SELECT 1 FROM proyectos WHERE id = ?", (proyecto_id,)
        ).fetchone()
        if existe_proyecto is None:
            return False
        cur = conn.execute(
            "UPDATE pliegos SET proyecto_id = ?, modificado_en = ? WHERE id = ?",
            (proyecto_id, _ahora(), pliego_id),
        )
    return cur.rowcount > 0
