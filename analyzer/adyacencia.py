# -*- coding: utf-8 -*-
"""Grafo de adyacencias físicas entre habitaciones. Única definición.

Extraído de `circulation.py` el 2026-08-05 sin cambiar su comportamiento, para
que `evaluator.py` pueda medir recorridos reales sin duplicar el grafo ni
crear un ciclo de importación (`circulation` importa `evaluator`, así que el
grafo no podía vivir allí).

Toma listas de `Room`, no `Unit`, precisamente para no depender de
`evaluator`: es el escalón de más abajo y no sabe nada de viviendas, reglas
ni normativa.

**Por qué existe este módulo y no dos criterios de adyacencia**

En los DXF reales los polígonos de habitación NO se tocan: cada uno se dibuja
en la cara interior de su propio muro, dejando un hueco que representa el
espesor del tabique. Medido sobre `ejemplo.dxf`: de 85 pares de piezas de una
misma vivienda, **1 solo comparte borde**, y los huecos entre piezas
realmente contiguas van de 0,000 a 0,380 m, mientras que el siguiente hueco
entre piezas NO contiguas salta a 2,27 m. El margen es enorme, así que un
umbral de distancia separa los dos casos con seguridad.

El criterio antiguo del Bloque 16 (`evaluator._is_adjacent`) exigía contacto
literal de contornos y por eso no disparaba nunca sobre datos reales. Este
módulo es el criterio bueno, y desde la tarea 10 del `REFACTOR_MASTERPLAN.md`
(2026-08-18) es el único que queda: aquel se eliminó por no tener ni un solo
llamador. La migración de la regla acústica ya la hizo el PRD de
`2026-08-11-adyacencia-acustica-tramo-enfrentado.md`.
"""
from __future__ import annotations

import heapq
from collections import deque
from typing import Dict, List, Optional, Tuple

from .parser import Room

# Grafo no dirigido: id(Room) -> [(habitación vecina, distancia entre centroides)]
Grafo = Dict[int, List[Tuple[Room, float]]]

# Hueco máximo entre contornos para considerar dos piezas contiguas. Validado
# empíricamente contra `ejemplo.dxf` (ver cabecera): los huecos reales llegan
# a 0,38 m y el primer falso positivo estaría a 2,27 m.
WALL_GAP_TOLERANCE_M = 0.5


def rooms_are_connected(a: Room, b: Room) -> bool:
    """True si dos piezas son físicamente contiguas (comunicables)."""
    return a.polygon.distance(b.polygon) <= WALL_GAP_TOLERANCE_M


def construir_grafo(rooms: List[Room]) -> Grafo:
    """Grafo no dirigido de piezas contiguas, con la distancia real entre
    centroides como peso de cada arista."""
    graph: Grafo = {id(r): [] for r in rooms}
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            a, b = rooms[i], rooms[j]
            if rooms_are_connected(a, b):
                distance = a.polygon.centroid.distance(b.polygon.centroid)
                graph[id(a)].append((b, distance))
                graph[id(b)].append((a, distance))
    return graph


def bfs_path(graph: Grafo, start: Room, end: Room) -> Optional[List[Room]]:
    """Camino con menos habitaciones intermedias entre `start` y `end` (sin
    ponderar por distancia): identifica QUÉ piezas se cruzan, no cuánto se
    anda — para eso está `weighted_shortest_path`."""
    if id(start) == id(end):
        return [start]
    visited = {id(start)}
    queue: deque = deque([[start]])
    while queue:
        path = queue.popleft()
        current = path[-1]
        for neighbor, _dist in graph.get(id(current), []):
            if id(neighbor) in visited:
                continue
            if id(neighbor) == id(end):
                return path + [neighbor]
            visited.add(id(neighbor))
            queue.append(path + [neighbor])
    return None


def weighted_shortest_path(
    graph: Grafo, start: Room, end: Room
) -> Tuple[Optional[List[Room]], float]:
    """Dijkstra estándar: camino de menor distancia real (suma de tramos
    centroide-a-centroide) entre `start` y `end`."""
    if id(start) == id(end):
        return [start], 0.0

    dist: Dict[int, float] = {id(start): 0.0}
    prev: Dict[int, Room] = {}
    visited: set = set()
    heap: List[Tuple[float, int, Room]] = [(0.0, id(start), start)]

    while heap:
        d, rid, room = heapq.heappop(heap)
        if rid in visited:
            continue
        visited.add(rid)
        if rid == id(end):
            break
        for neighbor, edge_dist in graph.get(rid, []):
            nid = id(neighbor)
            nd = d + edge_dist
            if nd < dist.get(nid, float("inf")):
                dist[nid] = nd
                prev[nid] = room
                heapq.heappush(heap, (nd, nid, neighbor))

    if id(end) not in dist:
        return None, float("inf")

    path = [end]
    current_id = id(end)
    while current_id != id(start):
        prev_room = prev[current_id]
        path.append(prev_room)
        current_id = id(prev_room)
    path.reverse()
    return path, dist[id(end)]


def recorrido_mas_largo(graph: Grafo, origenes: List[Room], destino: Room) -> Tuple[Optional[List[Room]], float]:
    """De todos los `origenes`, el que queda más lejos de `destino` por el
    camino más corto real. Es la definición de "punto más desfavorable" que
    necesita cualquier medida de recorrido de evacuación."""
    peor_camino: Optional[List[Room]] = None
    peor_distancia = -1.0
    for room in origenes:
        camino, distancia = weighted_shortest_path(graph, room, destino)
        if camino is None:
            continue
        if distancia > peor_distancia:
            peor_distancia = distancia
            peor_camino = camino
    if peor_camino is None:
        return None, 0.0
    return peor_camino, peor_distancia
