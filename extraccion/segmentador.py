"""Segmentación determinista del XML crudo del BOE en `Segmento`s.

Cero IA. Cero red. Reutiliza directamente `DocumentoOficial.texto_crudo`
—el mismo XML que la Fase 1 ya descarga y guarda— sin pedir nada nuevo a
`ingesta/`.

Las marcas de clase que sigue este módulo están **verificadas contra el CTE
real** (`tests/fixtures/boe/BOE-A-2006-5515.xml`), no supuestas de memoria —
ver `docs/design/2026-08-06-extraccion-cte.md` §0:

    p.articulo      -> arranca un artículo O una disposición (se distingue
                        por el texto: "Artículo…" vs "Disposición…")
    p.anexo_num  +
    p.anexo_tit     -> arrancan un anejo, siempre en ese orden y pegados
    p.capitulo_num +
    p.capitulo_tit  -> NO son segmentos propios: son el contexto ("capítulo
                        de qué") que se adjunta a los artículos siguientes
    p.parrafo,
    p.parrafo_2,
    (sin clase),
    table           -> cuerpo del segmento abierto en ese momento
    p.firma_rey,
    p.firma_ministro,
    p.subseccion,
    p.capitulo (suelto, "PARTE I"),
    p.anexo (suelto, encabezado)
                    -> marcadores estructurales que NO son cuerpo de nada;
                       se ignoran a propósito, nunca se cuelan en un segmento
"""
from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from typing import List, Optional

from ingesta.modelo import DocumentoOficial

from .modelo import Segmento

# Clases que nunca son cuerpo de un segmento — todo lo demás sí lo es
# mientras haya un segmento abierto. Lista cerrada y corta a propósito: es
# más seguro enumerar lo que se descarta que enumerar lo que se acepta,
# porque el BOE tipografía distinto según el tipo de documento y una lista
# de "aceptados" incompleta perdería contenido en silencio.
_MARCADORES_ESTRUCTURALES = {
    "articulo", "anexo_num", "anexo_tit", "capitulo_num", "capitulo_tit",
    "firma_rey", "firma_ministro", "subseccion", "capitulo", "anexo",
}


def _texto_plano(nodo: ET.Element) -> str:
    """Todo el texto de un nodo, incluidos hijos (p.ej. un `<a>` de
    referencia dentro de un párrafo) — perder el texto de un hijo sería
    exactamente el tipo de pérdida silenciosa que este módulo existe para
    evitar."""
    return "".join(nodo.itertext()).strip()


def _slug(titulo: str) -> str:
    """`"Artículo 11. Exigencias básicas..."` -> `"articulo_11"`. Solo se usa
    para el `id` del segmento (una etiqueta interna, no un concept_id — esos
    no existen hasta que algo se promueve)."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", titulo) if unicodedata.category(c) != "Mn"
    )
    cabeza = sin_acentos.split(".")[0].strip().lower()
    cabeza = re.sub(r"[^a-z0-9]+", "_", cabeza).strip("_")
    return cabeza or "segmento"


def _tipo_de_titulo(titulo: str) -> str:
    if titulo.lower().startswith("disposici"):
        return "disposicion"
    return "articulo"


def segmentar(documento: DocumentoOficial) -> List[Segmento]:
    """El documento oficial completo -> sus artículos/disposiciones/anejos,
    en el orden en que aparecen. Un documento sin ningún `p.articulo` ni
    `p.anexo_num` (p. ej. porque no es un XML de cuerpo normativo, o porque
    vino vacío) devuelve una lista vacía — no es un error, es un documento
    sin estructura reconocible, y quien llame decide qué hacer con eso."""
    try:
        raiz = ET.fromstring(documento.texto_crudo)
    except ET.ParseError:
        return []

    contenedor = raiz.find("texto")
    if contenedor is None:
        return []

    segmentos: List[Segmento] = []
    capitulo_actual: Optional[str] = None
    capitulo_num_pendiente: Optional[str] = None
    anexo_num_pendiente: Optional[str] = None
    pendiente: Optional[dict] = None
    orden = 0

    def cerrar_pendiente() -> None:
        nonlocal pendiente
        if pendiente is not None and pendiente["texto"].strip():
            segmentos.append(
                Segmento(
                    id=pendiente["id"],
                    tipo_segmento=pendiente["tipo_segmento"],
                    titulo=pendiente["titulo"],
                    capitulo=pendiente["capitulo"],
                    texto=pendiente["texto"].strip(),
                    documento_identificador=documento.identificador,
                    orden=pendiente["orden"],
                )
            )
        pendiente = None

    for nodo in contenedor:
        clase = nodo.get("class")
        texto = _texto_plano(nodo)

        if clase == "capitulo_num":
            capitulo_num_pendiente = texto
            continue
        if clase == "capitulo_tit":
            capitulo_actual = f"{capitulo_num_pendiente}. {texto}" if capitulo_num_pendiente else texto
            capitulo_num_pendiente = None
            continue

        if clase == "articulo":
            cerrar_pendiente()
            orden += 1
            pendiente = {
                "id": _slug(texto), "tipo_segmento": _tipo_de_titulo(texto),
                "titulo": texto, "capitulo": capitulo_actual, "texto": "", "orden": orden,
            }
            continue

        if clase == "anexo_num":
            cerrar_pendiente()
            anexo_num_pendiente = texto
            continue
        if clase == "anexo_tit":
            orden += 1
            titulo = f"{anexo_num_pendiente}. {texto}" if anexo_num_pendiente else texto
            pendiente = {
                "id": _slug(anexo_num_pendiente or texto), "tipo_segmento": "anejo",
                "titulo": titulo, "capitulo": None, "texto": "", "orden": orden,
            }
            anexo_num_pendiente = None
            continue

        if clase in _MARCADORES_ESTRUCTURALES:
            # firma_rey/firma_ministro cierran lo que hubiera quedado abierto;
            # subseccion/capitulo/anexo (sueltos) son ruido tipográfico, se
            # ignoran sin cerrar nada.
            if clase in ("firma_rey", "firma_ministro"):
                cerrar_pendiente()
            continue

        # Cuerpo: solo se acumula si hay un segmento abierto. Un párrafo
        # suelto antes del primer artículo (p. ej. el preámbulo) no es cuerpo
        # de ningún segmento — se descarta a propósito, no por descuido.
        if pendiente is not None and texto:
            pendiente["texto"] += texto + "\n\n"

    cerrar_pendiente()
    return segmentos
