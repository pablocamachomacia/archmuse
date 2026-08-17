"""Regla 1 de circulación reescrita sobre la Graph API: recorrido
dormitorio -> baño que obliga a cruzar una pieza social.

Equivalente funcional de `analyzer.circulation._check_absurd_routes`.

**Este módulo no importa el parser, ni shapely, ni el evaluador, ni ninguna
expresión regular.** Solo el API y el vocabulario de tipos. Esa es la regla del
experimento y `comparar_regla.py` la comprueba de forma mecánica, no de
palabra.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .api import VistaUnidad
from .modelo import PIEZA_HUMEDA, PIEZA_SOCIAL, Espacio


@dataclass
class Recorrido:
    correcto: bool
    mensaje: str
    camino: List[Espacio] = field(default_factory=list)

    @property
    def etiquetas(self) -> List[str]:
        return [e.rotulo or "(sin etiqueta)" for e in self.camino]


def recorridos_dormitorio_bano(vista: VistaUnidad) -> List[Recorrido]:
    recorridos: List[Recorrido] = []
    for dormitorio in vista.find(tipo="dormitorio"):
        for bano in vista.find(tipo=PIEZA_HUMEDA):
            camino = vista.camino(dormitorio, bano)
            if camino is None:
                continue  # no conectados: dato insuficiente, no un hallazgo
            cruzadas = [e for e in camino[1:-1] if e.tipo.valor in PIEZA_SOCIAL]
            if cruzadas:
                recorridos.append(Recorrido(
                    correcto=False,
                    mensaje=(
                        f"{dormitorio.rotulo} → {bano.rotulo}: el recorrido cruza "
                        f"{cruzadas[0].rotulo} — hay que atravesar una pieza social "
                        "para llegar al baño"
                    ),
                    camino=camino,
                ))
            else:
                recorridos.append(Recorrido(
                    correcto=True,
                    mensaje=f"{dormitorio.rotulo} → {bano.rotulo}: recorrido directo, sin cruzar piezas sociales",
                    camino=camino,
                ))
    return recorridos


def banos_sin_antesala(vista: VistaUnidad) -> List[Recorrido]:
    """Regla 4 de circulación: baño con paso directo desde una pieza social.

    Equivalente de `analyzer.circulation._check_bathroom_access`. Se añade
    porque la regla 1 no encuentra ningún problema en `ejemplo.dxf`, y una
    equivalencia comprobada solo sobre casos que pasan demuestra la mitad.
    Esta sí falla en tres viviendas del plano real."""
    recorridos: List[Recorrido] = []
    for bano in vista.find(tipo=PIEZA_HUMEDA):
        sociales = [e for e in vista.connected_spaces(bano) if e.tipo.valor in PIEZA_SOCIAL]
        if sociales:
            recorridos.append(Recorrido(
                correcto=False,
                mensaje=(
                    f"{bano.rotulo}: acceso directo desde {sociales[0].rotulo}, "
                    "sin antesala/pasillo intermedio"
                ),
                camino=[sociales[0], bano],
            ))
    return recorridos
