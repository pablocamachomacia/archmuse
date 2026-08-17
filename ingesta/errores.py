"""Errores del pipeline de ingesta. Mismo principio que `normativa/errores.py`:
nunca silencio — un documento que no se pudo traer se reporta con su motivo,
nunca se omite sin más de un resultado que parecería completo."""
from __future__ import annotations


class ErrorIngesta(Exception):
    """Raíz de todos los errores de este paquete."""


class ErrorDeRed(ErrorIngesta):
    """La fuente oficial no respondió o respondió con un error de transporte.

    Distinto de "no hay publicación ese día" (que no es un error, ver
    `fuentes/boe.py`): esto es la red o el servidor fallando de verdad.
    """

    def __init__(self, url: str, causa: Exception):
        self.url = url
        self.causa = causa
        super().__init__(f"No se pudo obtener {url}: {causa}")


class DocumentoIlegible(ErrorIngesta):
    """La fuente respondió, pero el contenido no se pudo interpretar como el
    documento esperado (XML roto, JSON con forma inesperada). Fail-closed:
    no se guarda un documento a medias en el almacén."""

    def __init__(self, identificador: str, motivo: str):
        self.identificador = identificador
        self.motivo = motivo
        super().__init__(f"{identificador}: {motivo}")
