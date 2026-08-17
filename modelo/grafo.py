# -*- coding: utf-8 -*-
"""E1.7 — La versión sellada del grafo y su API de lectura.

**El contrato del modelo son las consultas, no los campos.** Un motor no debe
saber si un espacio guarda su polígono o su `geom_id`; debe poder preguntar
qué espacios son contiguos a otro, qué camino hay entre dos, y —sobre todo—
qué no se sabe de este proyecto.

Portado de `experimentos/grafo/api.py`, que validó esta forma contra
producción: dos reglas reescritas sólo contra este API dieron **12 de 12
salidas idénticas**, con 30→24 y 14→13 líneas, y desaparecieron las regex,
`_normalize` y el `id()` como identidad de habitación. El experimento se
conserva intacto como evidencia (`tests/test_golden_grafo_experimento.py`); lo
que sigue no lo importa ni depende de él.

**Sellado.** Una versión se construye, se comprueba y se congela. A partir de
ahí no se modifica: cualquier cambio produce una versión nueva (invariante
I8). Es la disciplina *append-only* que `REASONING_ENGINE_SPEC.md` fijó, y
tiene un beneficio inmediato: comparar dos versiones es una operación sobre
datos, no una reconstrucción a posteriori.

**El orden de inserción se conserva.** Los recorridos con empate dependen de
él, y `adyacencia.py` resuelve los suyos por el orden del doble bucle `i<j`.
Sin esta propiedad, migrar `circulation.py` al modelo cambiaría qué camino se
elige entre dos igual de cortos, y la comparación mediría el desempate en vez
de la arquitectura.
"""
from __future__ import annotations

import heapq
from collections import deque
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .aristas import CONECTA_CON, ES_CONTIGUO_A, Arista, Criterio
from .geometria import AlmacenGeometria, HUELLA_2D
from .nodos import Edificio, Espacio, Planta, Proyecto, Unidad

Tipos = Union[str, Sequence[str], None]


def _como_conjunto(tipo: Tipos) -> Optional[set]:
    if tipo is None:
        return None
    if isinstance(tipo, str):
        return {tipo}
    return set(tipo)


class VersionSellada(RuntimeError):
    """Se ha intentado modificar una versión ya sellada."""


class Grafo:
    """Una versión del modelo de un proyecto. Inmutable una vez sellada."""

    def __init__(
        self,
        proyecto: Proyecto,
        edificios: Sequence[Edificio],
        plantas: Sequence[Planta],
        unidades: Sequence[Unidad],
        espacios: Sequence[Espacio],
        aristas: Sequence[Arista],
        almacen: AlmacenGeometria,
        criterio: Criterio,
    ) -> None:
        self.proyecto = proyecto
        self.criterio = criterio
        self.almacen = almacen

        self._edificios: Dict[str, Edificio] = {e.id: e for e in edificios}
        self._plantas: Dict[str, Planta] = {p.id: p for p in plantas}
        self._unidades: Dict[str, Unidad] = {u.id: u for u in unidades}
        self._espacios: Dict[str, Espacio] = {e.id: e for e in espacios}
        self._orden: List[str] = [e.id for e in espacios]
        self._orden_unidades: List[str] = [u.id for u in unidades]
        self._aristas: List[Arista] = list(aristas)

        # Listas de adyacencia por tipo de relación, en orden de inserción.
        self._vecinos: Dict[str, Dict[str, List[str]]] = {
            eid: {ES_CONTIGUO_A: [], CONECTA_CON: []} for eid in self._orden
        }
        self._peso: Dict[Tuple[str, str], float] = {}
        for arista in self._aristas:
            self._vecinos[arista.a][arista.tipo].append(arista.b)
            self._vecinos[arista.b][arista.tipo].append(arista.a)
            self._peso[(arista.a, arista.b)] = arista.distancia_m
            self._peso[(arista.b, arista.a)] = arista.distancia_m

        self._sellado: Optional[str] = None

    # --- Sellado ----------------------------------------------------------

    @property
    def sellado(self) -> Optional[str]:
        return self._sellado

    def sellar(self, huella: str) -> "Grafo":
        if self._sellado is not None:
            raise VersionSellada("esta version ya esta sellada: %s" % self._sellado)
        self._sellado = huella
        return self

    # --- Consultas básicas ------------------------------------------------

    def get_spaces(self) -> List[Espacio]:
        return [self._espacios[eid] for eid in self._orden]

    def get_space(self, espacio_id: str) -> Optional[Espacio]:
        return self._espacios.get(espacio_id)

    def neighbors(self, espacio: Espacio) -> List[Espacio]:
        """Vecinos por cualquier relación, sin duplicados y en orden de lectura."""
        vistos: List[str] = []
        for tipo in (CONECTA_CON, ES_CONTIGUO_A):
            for eid in self._vecinos[espacio.id][tipo]:
                if eid not in vistos:
                    vistos.append(eid)
        return [self._espacios[eid] for eid in vistos]

    def connected_spaces(self, espacio: Espacio) -> List[Espacio]:
        """Espacios a los que se puede pasar desde este (`conecta con`)."""
        return [self._espacios[eid] for eid in self._vecinos[espacio.id][CONECTA_CON]]

    def contiguous_spaces(self, espacio: Espacio) -> List[Espacio]:
        """Espacios que comparten separación física, se pase o no
        (`es contiguo a`). Es la que necesita la regla acústica, que hoy no
        dispara nunca porque mide borde compartido."""
        return [self._espacios[eid] for eid in self._vecinos[espacio.id][ES_CONTIGUO_A]]

    def find(self, tipo: Tipos = None, unidad: Optional[str] = None) -> List[Espacio]:
        tipos = _como_conjunto(tipo)
        return [
            e for e in self.get_spaces()
            if (tipos is None or e.tipo.valor in tipos)
            and (unidad is None or e.unidad_id == unidad)
        ]

    def arista(self, a: str, b: str, tipo: str) -> Optional[Arista]:
        clave = tuple(sorted((a, b)))
        for arista in self._aristas:
            if arista.tipo == tipo and (arista.a, arista.b) == clave:
                return arista
        return None

    def aristas(self, tipo: Optional[str] = None) -> List[Arista]:
        if tipo is None:
            return list(self._aristas)
        return [a for a in self._aristas if a.tipo == tipo]

    # --- Ámbitos ----------------------------------------------------------

    def edificios(self) -> List[Edificio]:
        return [self._edificios[i] for i in sorted(self._edificios)]

    def plantas(self) -> List[Planta]:
        return [self._plantas[i] for i in sorted(self._plantas)]

    def unidades(self) -> List[Unidad]:
        return [self._unidades[uid] for uid in self._orden_unidades]

    def unidad(self, unidad_id: str) -> "VistaUnidad":
        return VistaUnidad(self, self._unidades[unidad_id])

    def espacios_de(self, unidad_id: str) -> List[Espacio]:
        return [self._espacios[eid] for eid in self._unidades[unidad_id].espacios]

    # --- Geometría (derivados, nunca shapely) -----------------------------

    def derivados(self, espacio: Espacio, representacion: str = HUELLA_2D) -> dict:
        return self.almacen.derivados(espacio.geometrias[representacion])

    def area_m2(self, espacio: Espacio) -> float:
        return self.almacen.area_m2(espacio.geometrias[HUELLA_2D])

    # --- Recorridos -------------------------------------------------------

    def camino(self, origen: Espacio, destino: Espacio) -> Optional[List[Espacio]]:
        """Camino con menos espacios intermedios: qué se cruza, no cuánto se anda."""
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
        """Estado de presencia de un tipo de nodo. Sin esto, la ausencia de
        nodos no es interpretable y una inferencia negativa sobre datos que
        nunca existieron pasa por conclusión."""
        return self.proyecto.presencia.get(tipo_de_nodo, "no_declarado")

    def desconocidos(self) -> List[str]:
        """Qué no se sabe de este proyecto.

        Es la consulta que alimenta el protocolo de datos insuficientes de
        `DECISION_ENGINE.md` §12, y hoy no había nada capaz de responderla.
        """
        faltas = []
        for nodo, estado in sorted(self.proyecto.presencia.items()):
            if estado != "observado":
                faltas.append("%s: %s" % (nodo, estado))
        for espacio in self.get_spaces():
            if not espacio.tipo.resuelto:
                faltas.append("%s: tipo desconocido (rotulo %r)"
                              % (espacio.id, espacio.rotulo))
        return faltas


class VistaUnidad:
    """El mismo API, acotado a una vivienda.

    Casi toda regla razona dentro de una unidad; sin el acotado, cada una
    tendría que filtrar a mano, que es el trabajo repetido que el modelo
    existe para eliminar.
    """

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

    def area_m2(self, espacio: Espacio) -> float:
        return self._grafo.area_m2(espacio)
