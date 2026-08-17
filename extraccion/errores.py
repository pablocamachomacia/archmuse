"""Errores de la Fase 2. Mismo principio que `ingesta/errores.py`: un
segmento que no se pudo interpretar se reporta con su motivo, nunca
desaparece sin más de un resultado que parecería completo."""
from __future__ import annotations


class ErrorExtraccion(Exception):
    """Raíz de todos los errores de este paquete."""


class ErrorDeInterpretacion(ErrorExtraccion):
    """La llamada al modelo falló, o su respuesta no se pudo interpretar
    como una `ReglaCandidata` — falta la API key, el paquete `anthropic` no
    está instalado, la API devolvió un error, o el modelo rechazó la
    petición. Nunca se convierte en una candidata "vacía" con confianza
    Baja: se levanta y quien orquesta decide qué hacer, igual que
    `ingesta.errores.ErrorDeRed` con un documento que no se pudo descargar.
    """

    def __init__(self, segmento_id: str, motivo: str):
        self.segmento_id = segmento_id
        self.motivo = motivo
        super().__init__(f"{segmento_id}: {motivo}")
