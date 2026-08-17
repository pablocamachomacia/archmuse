"""Entidades de la Fase 1: qué se lista, qué se descarga, qué se registró.

Deliberadamente NO son `NormaFuente`/`ReglaNormativa` de `normativa/modelo.py`
— esas son el formato de destino, curado y validado; estas son su materia
prima, tal cual la sirve la fuente oficial, antes de que nadie la interprete.
Confundir ambos niveles sería exactamente el error que la "regla de dos
personas" (`NORMATIVE_ENGINE.md` §12) existe para impedir: un documento
descargado no es una regla, por bien formado que venga.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

# Formatos que `almacen.py` sabe versionar tal cual. Cerrado a propósito: un
# formato nuevo (p.ej. HTML) es una decisión de diseño en `almacen.py`
# (¿cómo se cachea, con qué extensión?), no algo que una fuente deba poder
# inventar pasando cualquier string.
FORMATOS_SOPORTADOS = frozenset({"xml", "pdf"})


def como_lista(valor):
    """Normaliza el patrón dict-o-list de un JSON generado desde XML por PHP:
    un campo que podría repetirse sale como `dict` cuando hay uno solo y como
    `list` cuando hay varios. Verificado contra una respuesta real del BOE
    (ver `docs/design/2026-08-06-ingesta-normativa.md` §3.1) en cinco niveles
    distintos de un mismo sumario. Un parser que asuma una sola forma pierde
    publicaciones en silencio — exactamente el tipo de fallo silencioso que
    todo este subsistema existe para no cometer."""
    if valor is None:
        return []
    if isinstance(valor, list):
        return valor
    return [valor]


@dataclass(frozen=True)
class ItemSumario:
    """Una publicación tal como aparece listada en el sumario del día. Trae
    lo justo para decidir si merece la pena descargarla entera y de dónde."""

    identificador: str
    titulo: str
    fuente: str
    fecha_publicacion: str  # AAAAMMDD, tal como la declara el sumario
    seccion_codigo: str
    seccion_nombre: str
    departamento_codigo: str
    departamento_nombre: str
    epigrafe: Optional[str]
    url_html: Optional[str]
    url_pdf: Optional[str]
    url_xml: Optional[str]


@dataclass(frozen=True)
class DocumentoOficial:
    """El documento completo: metadatos oficiales + el texto crudo tal cual
    se descargó, sin interpretar. `texto_crudo` es intencionadamente el XML
    entero devuelto por la fuente, no un resumen — la Fase 2 (extracción de
    artículos) necesita el original completo, y una traza que solo guardara
    un extracto ya habría perdido información antes de la primera pregunta.

    `formato`/`bytes_crudos` son la extensión que necesita una fuente en PDF
    (`fuentes/codigotecnico.py`): `texto_crudo` sigue siendo obligatorio
    (texto ya extraído, lo que consume `extraccion/`), pero para un PDF eso
    es una *derivación*, no el original — así que `bytes_crudos` guarda el
    PDF tal cual se descargó, para que `almacen.py` archive el original real,
    no solo su texto extraído. `None` para fuentes ya basadas en texto (BOE):
    ahí `texto_crudo` YA ES el original, no hace falta duplicarlo en bytes."""

    identificador: str
    fuente: str
    titulo: str
    organismo: str
    rango_codigo: Optional[str]
    rango_nombre: Optional[str]
    numero_oficial: Optional[str]
    fecha_publicacion: Optional[str]
    fecha_disposicion: Optional[str]
    fecha_actualizacion: Optional[str]
    url_oficial: str
    url_xml: str
    texto_crudo: str
    hash_texto: str
    formato: str = "xml"
    bytes_crudos: Optional[bytes] = None
    # Condición de Pablo (2026-08-06, aprobación del diseño de
    # `docs/design/2026-08-06-auditoria-fuentes-cte.md`): "nunca dependas de
    # una única fuente". Para un documento de `codigotecnico.org`, esto
    # declara qué instrumento(s) del BOE constituyen su texto vigente —
    # curado a mano en `ingesta/fuentes/codigotecnico.py`, NUNCA reconstruido
    # ni inferido por ArchMuse (ver §4 de ese diseño: reconstruir consolidación
    # legal por fusión sería el motor nuevo que Pablo pidió no construir).
    # Vacío para BOE mismo: un documento del BOE ya ES el instrumento legal,
    # no necesita citarse a sí mismo.
    referencias_boe: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.formato not in FORMATOS_SOPORTADOS:
            raise ValueError(f"formato «{self.formato}» no soportado (esperaba uno de {sorted(FORMATOS_SOPORTADOS)})")


@dataclass(frozen=True)
class EstadoDescarga:
    """Lo que se escribe en el ledger: no el documento, sino el HECHO de
    haberlo visto en un momento dado, con qué hash, y si cambió respecto a
    la última vez. Es el registro de "qué sabía ArchMuse y cuándo"
    (`NORMATIVE_ENGINE.md` §4.1, eje de registro) aplicado al pipeline.

    `url_oficial`/`fecha_publicacion`/`referencias_boe` son la condición de
    doble fuente que Pablo pidió al aprobar
    `docs/design/2026-08-06-auditoria-fuentes-cte.md`: cada documento debe
    quedar trazable incluso si `codigotecnico.org` cambia o desaparece
    mañana. `fecha_descarga` (ya existía) hace de "fecha de última
    comprobación" — no hace falta un campo nuevo para eso."""

    identificador: str
    fuente: str
    hash_anterior: Optional[str]
    hash_nuevo: str
    estado: str  # "nuevo" | "sin_cambios" | "modificado"
    fecha_descarga: str  # ISO 8601 UTC — también "fecha de última comprobación"
    ruta_cache: Optional[str]  # None si "sin_cambios": no se duplica el crudo
    url_oficial: str = ""
    fecha_publicacion: Optional[str] = None
    referencias_boe: Tuple[str, ...] = ()

    def a_dict(self) -> dict:
        return {
            "identificador": self.identificador,
            "fuente": self.fuente,
            "hash_anterior": self.hash_anterior,
            "hash_nuevo": self.hash_nuevo,
            "estado": self.estado,
            "fecha_descarga": self.fecha_descarga,
            "ruta_cache": self.ruta_cache,
            "url_oficial": self.url_oficial,
            "fecha_publicacion": self.fecha_publicacion,
            "referencias_boe": list(self.referencias_boe),
        }


@dataclass(frozen=True)
class ResultadoIngesta:
    """Lo que devuelve una corrida del pipeline: no solo lo descargado, sino
    también lo que se supo que existía y se descartó, y por qué. Un resultado
    que solo contara éxitos escondería justo lo que un vigilante de fuentes
    necesita ver — cuántos días con boletín se han recorrido y cuántos items
    se han filtrado antes de descargar nada."""

    items_vistos: Tuple[ItemSumario, ...]
    items_filtrados: int
    descargas: Tuple[EstadoDescarga, ...]
    avisos: Tuple[str, ...] = field(default_factory=tuple)

    def a_dict(self) -> dict:
        return {
            "items_vistos": len(self.items_vistos),
            "items_filtrados": self.items_filtrados,
            "descargas": [d.a_dict() for d in self.descargas],
            "avisos": list(self.avisos),
        }
