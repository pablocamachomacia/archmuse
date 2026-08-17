"""La Graph API: el único punto por el que un motor puede leer el proyecto.

Regla del experimento, y lo que de verdad se está validando aquí: **ninguna
regla importa el parser, ni shapely, ni el evaluador**. Solo esto.

Métodos, tal y como se pidieron:

    grafo.get_spaces()
    grafo.get_space(id)
    grafo.neighbors(espacio)
    grafo.connected_spaces(espacio)
    grafo.contiguous_spaces(espacio)
    grafo.find(tipo="bano")

`find` recibe `tipo=` y no `type=` por dos motivos: `type` tapa un builtin de
Python, y los valores del vocabulario son los de `SPACE_TAXONOMY.md`, que están
en castellano ("bano", no "Bathroom") — mezclar los dos idiomas en la misma
llamada era peor que elegir uno.

`VistaUnidad` es el mismo API acotado a una vivienda. Casi toda regla razona
dentro de una unidad, y sin el acotado cada regla tendría que filtrar a mano,
que es exactamente el trabajo repetido que este experimento intenta eliminar.
"""
from __future__ import annotations

import heapq
from collections import deque
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .modelo import (
    CONECTA_CON,
    ES_CONTIGUO_A,
    Arista,
    Espacio,
    Proyecto,
    Unidad,
)

Tipos = Union[str, Sequence[str], None]


def _como_conjunto(tipo: Tipos) -> Optional[set]:
    if tipo is None:
        return None
    if isinstance(tipo, str):
        return {tipo}
    return set(tipo)


class Grafo:
    """Una versión sellada del grafo de un proyecto. No se modifica."""

    def __init__(
        self,
        proyecto: Proyecto,
        espacios: List[Espacio],
        unidades: List[Unidad],
        aristas: List[Arista],
    ) -> None:
        self.proyecto = proyecto
        self._espacios: Dict[str, Espacio] = {e.id: e for e in espacios}
        self._orden: List[str] = [e.id for e in espacios]
        self._unidades: Dict[str, Unidad] = {u.id: u for u in unidades}
        self._aristas = list(aristas)

        # Listas de adyacencia por tipo de relación. El orden de inserción se
        # conserva a propósito: los recorridos con empate dependen de él, y sin
        # esto el experimento no podría compararse con la implementación actual.
        self._vecinos: Dict[str, Dict[str, List[str]]] = {
            eid: {ES_CONTIGUO_A: [], CONECTA_CON: []} for eid in self._orden
        }
        self._peso: Dict[Tuple[str, str], float] = {}
        for arista in self._aristas:
            self._vecinos[arista.a][arista.tipo].append(arista.b)
            self._vecinos[arista.b][arista.tipo].append(arista.a)
            self._peso[(arista.a, arista.b)] = arista.distancia_m
            self._peso[(arista.b, arista.a)] = arista.distancia_m

    # --- Consultas básicas ------------------------------------------------

    def get_spaces(self) -> List[Espacio]:
        return [self._espacios[eid] for eid in self._orden]

    def get_space(self, espacio_id: str) -> Optional[Espacio]:
        return self._espacios.get(espacio_id)

    def neighbors(self, espacio: Espacio) -> List[Espacio]:
        """Vecinos por cualquier relación. Contiguos y conectados a la vez, sin
        duplicados y en orden de lectura."""
        vistos: List[str] = []
        for tipo in (CONECTA_CON, ES_CONTIGUO_A):
            for eid in self._vecinos[espacio.id][tipo]:
                if eid not in vistos:
                    vistos.append(eid)
        return [self._espacios[eid] for eid in vistos]

    def connected_spaces(self, espacio: Espacio) -> List[Espacio]:
        """Espacios a los que se puede pasar desde este (relación `conecta con`)."""
        return [self._espacios[eid] for eid in self._vecinos[espacio.id][CONECTA_CON]]

    def contiguous_spaces(self, espacio: Espacio) -> List[Espacio]:
        """Espacios que comparten separación física con este, se pase o no
        (relación `es contiguo a`). Es la que necesita la regla acústica."""
        return [self._espacios[eid] for eid in self._vecinos[espacio.id][ES_CONTIGUO_A]]

    def find(self, tipo: Tipos = None, unidad: Optional[str] = None) -> List[Espacio]:
        tipos = _como_conjunto(tipo)
        return [
            e
            for e in self.get_spaces()
            if (tipos is None or e.tipo.valor in tipos)
            and (unidad is None or e.unidad_id == unidad)
        ]

    # --- Ámbitos ----------------------------------------------------------

    def unidades(self) -> List[Unidad]:
        return list(self._unidades.values())

    def unidad(self, unidad_id: str) -> "VistaUnidad":
        return VistaUnidad(self, self._unidades[unidad_id])

    # --- Recorridos -------------------------------------------------------

    def camino(self, origen: Espacio, destino: Espacio) -> Optional[List[Espacio]]:
        """Camino con menos espacios intermedios (qué se cruza, no cuánto se anda)."""
        if origen.id == destino.id:
            return [origen]
        visitados = {origen.id}
        cola: deque = deque([[origen.id]])
        while cola:
            camino = cola.popleft()
            for vecino_id in self._vecinos[camino[-1]][CONECTA_CON]:
                if vecino_id in visitados:
                    continue
                if vecino_id == destino.id:
                    return [self._espacios[i] for i in camino + [vecino_id]]
                visitados.add(vecino_id)
                cola.append(camino + [vecino_id])
        return None

    def camino_mas_corto(
        self, origen: Espacio, destino: Espacio
    ) -> Tuple[Optional[List[Espacio]], float]:
        """Camino de menor distancia real (Dijkstra sobre los pesos de arista)."""
        if origen.id == destino.id:
            return [origen], 0.0
        dist: Dict[str, float] = {origen.id: 0.0}
        previo: Dict[str, str] = {}
        visitados: set = set()
        cola: List[Tuple[float, str]] = [(0.0, origen.id)]
        while cola:
            d, eid = heapq.heappop(cola)
            if eid in visitados:
                continue
            visitados.add(eid)
            if eid == destino.id:
                break
            for vecino_id in self._vecinos[eid][CONECTA_CON]:
                nd = d + self._peso[(eid, vecino_id)]
                if nd < dist.get(vecino_id, float("inf")):
                    dist[vecino_id] = nd
                    previo[vecino_id] = eid
                    heapq.heappush(cola, (nd, vecino_id))
        if destino.id not in dist:
            return None, float("inf")
        camino = [destino.id]
        while camino[-1] != origen.id:
            camino.append(previo[camino[-1]])
        camino.reverse()
        return [self._espacios[i] for i in camino], dist[destino.id]

    # --- Honestidad -------------------------------------------------------

    def presencia(self, tipo_de_nodo: str) -> str:
        """Estado de presencia de un tipo de nodo (§0.4). Sin esto, la ausencia
        de nodos no es interpretable."""
        return self.proyecto.presencia.get(tipo_de_nodo, "no_declarado")

    def desconocidos(self) -> List[str]:
        """Qué no se sabe de este proyecto. Alimenta el protocolo de datos
        insuficientes de `DECISION_ENGINE.md` §12."""
        faltas = []
        for nodo, estado in sorted(self.proyecto.presencia.items()):
            if estado != "observado":
                faltas.append(f"{nodo}: {estado}")
        for espacio in self.get_spaces():
            if not espacio.tipo.conocido:
                faltas.append(f"{espacio.id}: tipo desconocido (rótulo {espacio.rotulo!r})")
        return faltas


class VistaUnidad:
    """El mismo API, acotado a una vivienda."""

    def __init__(self, grafo: Grafo, unidad: Unidad) -> None:
        self._grafo = grafo
        self.unidad = unidad

    @property
    def nombre(self) -> str:
        return str(self.unidad.etiqueta.valor)

    def get_spaces(self) -> List[Espacio]:
        return [self._grafo.get_space(eid) for eid in self.unidad.espacios]

    def get_space(self, espacio_id: str) -> Optional[Espacio]:
        espacio = self._grafo.get_space(espacio_id)
        return espacio if espacio and espacio.unidad_id == self.unidad.id else None

    def _propios(self, espacios: Iterable[Espacio]) -> List[Espacio]:
        return [e for e in espacios if e.unidad_id == self.unidad.id]

    def neighbors(self, espacio: Espacio) -> List[Espacio]:
        return self._propios(self._grafo.neighbors(espacio))

    def connected_spaces(self, espacio: Espacio) -> List[Espacio]:
        return self._propios(self._grafo.connected_spaces(espacio))

    def contiguous_spaces(self, espacio: Espacio) -> List[Espacio]:
        return self._propios(self._grafo.contiguous_spaces(espacio))

    def find(self, tipo: Tipos = None) -> List[Espacio]:
        return self._grafo.find(tipo=tipo, unidad=self.unidad.id)

    def camino(self, origen: Espacio, destino: Espacio) -> Optional[List[Espacio]]:
        return self._grafo.camino(origen, destino)

    def camino_mas_corto(self, origen: Espacio, destino: Espacio):
        return self._grafo.camino_mas_corto(origen, destino)
