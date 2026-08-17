"""Contrato que cualquier fuente oficial debe cumplir.

Es lo que hace el pipeline extensible sin rediseño: `pipeline.py` y
`almacen.py` reciben una `FuenteOficial`, nunca importan `boe.py` ni ninguna
fuente concreta. Añadir la Comunidad de Madrid o un ayuntamiento el día que
haga falta es escribir un módulo nuevo bajo `fuentes/` que implemente estos
dos métodos — nada fuera de `fuentes/` cambia. Mismo patrón de frontera que
`normativa/registro.py` ya usa para resolver ámbitos sin que el resolver
sepa de municipios concretos.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import List

from ..modelo import DocumentoOficial, ItemSumario


class FuenteOficial(ABC):
    """`id` identifica la fuente en el ledger (`"boe"`, futuro `"bocm"`...).
    Es texto plano, no un enum cerrado: añadir una fuente no es un evento de
    gobernanza como añadir una materia — es simplemente más cobertura."""

    id: str

    @abstractmethod
    def listar_sumario(self, fecha: date) -> List[ItemSumario]:
        """Todo lo publicado por esta fuente en `fecha`.

        Lista vacía si no hubo publicación ese día (fin de semana, festivo)
        — **eso no es un error**, es un hecho normal del calendario de
        boletines, y debe distinguirse de un fallo de red (que sí levanta
        `ErrorDeRed`). Confundir ambos convertiría cada festivo en una
        alarma falsa para quien vigile las fuentes.
        """

    @abstractmethod
    def descargar_documento(self, item: ItemSumario) -> DocumentoOficial:
        """El documento completo de un item ya listado.

        Separado de `listar_sumario` a propósito: permite decidir qué
        merece la pena descargar (por departamento, por sección) sin traerse
        el texto de los cientos de items por día que no son normativa de
        edificación — nombramientos, subvenciones, convocatorias.
        """
