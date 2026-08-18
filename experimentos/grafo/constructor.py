"""El Constructor del Grafo (§5 de `docs/brain/KNOWLEDGE_GRAPH.md`).

Único sitio de todo el experimento autorizado a leer el parser. Convierte un
`PlanoLeido` en una versión sellada del grafo.

Dos decisiones tomadas para que el experimento sea comparable y no un
espejismo:

1. **El orden importa y se conserva.** Los espacios se crean en el mismo orden
   en que el parser devuelve las habitaciones, y las aristas en el mismo doble
   bucle i<j que usa `circulation._build_adjacency_graph`. Sin esto, un empate
   entre dos caminos igual de cortos podría resolverse distinto en cada
   implementación y la comparación mediría el desempate, no la arquitectura.
2. **El criterio de adyacencia es un parámetro, no una constante.**
   `CRITERIO_ACTUAL` reproduce exactamente lo que hoy hace `circulation.py`
   (distancia entre contornos <= 0.5 m). `CRITERIO_ESTRICTO` aplica además la
   segunda condición que pide §4 del documento (un tramo enfrentado de longitud
   mínima). Ejecutar los dos y ver qué cambia es la mitad del experimento.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from analyzer.evaluator import _normalize, group_rooms_by_unit_label
from analyzer.parser import PlanoLeido, Room

from .api import Grafo
from .modelo import (
    CONECTA_CON,
    PIEZA_HUMEDA,  # noqa: F401 - reexportado por comodidad de las reglas
    PIEZA_SOCIAL,  # noqa: F401
    DERIVADO,
    DESCONOCIDO,
    DESCONOCIDO_VALOR,
    ES_CONTIGUO_A,
    OBSERVADO,
    PRESENCIA_INFERIDO,
    PRESENCIA_NO_OBSERVABLE,
    PRESENCIA_OBSERVADO,
    SUPUESTO,
    Arista,
    Espacio,
    Proyecto,
    Unidad,
    Valor,
)


@dataclass(frozen=True)
class Criterio:
    """Cómo se decide que dos espacios son contiguos o están conectados."""

    nombre: str
    tolerancia_muro_m: float = 0.5  # hueco máximo entre contornos = espesor de muro plausible
    tramo_minimo_conexion_m: float = 0.0  # 0.0 = solo distancia, como hoy
    tramo_minimo_contiguidad_m: float = 0.6  # las dos condiciones de §4


CRITERIO_ACTUAL = Criterio(nombre="actual (= circulation.py)")
CRITERIO_ESTRICTO = Criterio(nombre="estricto (§4 del documento)", tramo_minimo_conexion_m=0.6)


# --- Clasificación: rótulo -> tipo canónico (§2.6, vocabulario de SPACE_TAXONOMY) ---
#
# Primer patrón que casa, gana. El orden no es arbitrario: "TENDEDERO" antes
# que "TERRAZA" y los dormitorios antes que nada porque un rótulo como
# "DORMITORIO 1 (con baño)" es un dormitorio, no un baño.
_CLASIFICACION: List[Tuple[str, str]] = [
    ("TENDEDERO", "tendedero"),
    ("TERRAZA", "terraza"),
    ("DORMITORIO", "dormitorio"),
    ("ASEO", "aseo"),
    ("BANO", "bano"),
    ("COCINA", "cocina"),
    ("SALON", "salon"),
    ("PASILLO", "circulacion"),
    ("VESTIBULO", "circulacion"),
    ("DISTRIBUIDOR", "circulacion"),
    ("RECIBIDOR", "circulacion"),
    ("TRASTERO", "trastero"),
    ("GARAJE", "garaje"),
    ("PORTAL", "zona_comun"),
]

def clasificar(rotulo: Optional[str]) -> Tuple[Valor, List[str]]:
    """Devuelve (tipo con origen, lista de tipos que también casaban).

    La segunda mitad es la que hoy no existe en ninguna parte: si un rótulo
    casa con dos tipos ("SALÓN-COCINA"), eso es una ambigüedad real del plano
    y el grafo la registra en vez de quedarse callado con el primero."""
    if not rotulo:
        return DESCONOCIDO_VALOR, []
    texto = _normalize(rotulo)
    casan = [tipo for patron, tipo in _CLASIFICACION if patron in texto]
    if not casan:
        return DESCONOCIDO_VALOR, []
    return Valor(casan[0], OBSERVADO), casan[1:]


def _separacion(a: Room, b: Room) -> float:
    return float(a.polygon.distance(b.polygon))


def _tramo_enfrentado(a: Room, b: Room, tolerancia: float) -> float:
    """Longitud del tramo en que los dos contornos se miran de frente.

    No se puede medir como borde compartido —en estos planos los polígonos no
    se tocan nunca, que es justamente por lo que el antiguo
    `evaluator._is_adjacent` (borde compartido, ya eliminado) no se disparaba
    jamás— así que se mide cuánto del contorno de cada uno cae dentro
    del espesor de muro plausible del otro, y se toma el menor de los dos."""
    ab = b.polygon.boundary.intersection(a.polygon.buffer(tolerancia)).length
    ba = a.polygon.boundary.intersection(b.polygon.buffer(tolerancia)).length
    return float(min(ab, ba))


def _huella(room: Room, unidad: str) -> str:
    """concept_id provisional. §3 propone emparejar por solapamiento entre
    versiones; para este experimento basta una huella estable dentro de una
    misma lectura. NO es la solución de §3, y no debe leerse como tal."""
    x, y = room.polygon.centroid.x, room.polygon.centroid.y
    return f"{unidad}#{x:.1f},{y:.1f}"


def construir_grafo(
    plano: PlanoLeido,
    criterio: Criterio = CRITERIO_ACTUAL,
    tipologia: Optional[str] = None,
    ciudad: Optional[str] = None,
    norte_grados: Optional[float] = None,
) -> Grafo:
    # Fase 3 — agrupación. Se reutiliza la del evaluador para no introducir una
    # diferencia de agrupamiento que contaminaría la comparación. En una
    # implementación real esta función se muda aquí: agrupar es construir el
    # grafo, no evaluarlo.
    unidades_parser = group_rooms_by_unit_label(plano.rooms, plano.unit_labels)
    etiquetas_observadas = bool(plano.unit_labels)

    espacios: List[Espacio] = []
    unidades: List[Unidad] = []
    aristas: List[Arista] = []
    poligonos: dict = {}

    for unidad in unidades_parser:
        unidad_id = unidad.name
        ids_unidad: List[str] = []

        # Fases 1 y 2 — espacios y clasificación.
        for indice, room in enumerate(unidad.rooms):
            espacio_id = f"{unidad_id}::E{indice:02d}"
            tipo, ambiguos = clasificar(room.label)
            espacio = Espacio(
                id=espacio_id,
                concepto=_huella(room, unidad_id),
                unidad_id=unidad_id,
                rotulo=room.label,
                tipo=tipo,
                _poligono=room.polygon,
                procedencia=f"dxf:capa={room.layer}",
            )
            if ambiguos:
                # Se registra, no se resuelve en silencio.
                espacio.procedencia += f" ambiguo_con={','.join(ambiguos)}"
            espacios.append(espacio)
            poligonos[espacio_id] = room
            ids_unidad.append(espacio_id)

        unidades.append(
            Unidad(
                id=unidad_id,
                etiqueta=Valor(unidad_id, OBSERVADO if etiquetas_observadas else DERIVADO),
                espacios=ids_unidad,
            )
        )

        # Fase 5 — topología. Mismo doble bucle que `circulation.py`, a
        # propósito (ver cabecera).
        for i in range(len(ids_unidad)):
            for j in range(i + 1, len(ids_unidad)):
                a_id, b_id = ids_unidad[i], ids_unidad[j]
                a, b = poligonos[a_id], poligonos[b_id]
                separacion = _separacion(a, b)
                if separacion > criterio.tolerancia_muro_m:
                    continue
                tramo = _tramo_enfrentado(a, b, criterio.tolerancia_muro_m)
                distancia = float(a.polygon.centroid.distance(b.polygon.centroid))

                if tramo >= criterio.tramo_minimo_contiguidad_m:
                    aristas.append(Arista(
                        tipo=ES_CONTIGUO_A, a=a_id, b=b_id, origen=OBSERVADO,
                        separacion_m=separacion, tramo_m=tramo, distancia_m=distancia,
                    ))
                if tramo >= criterio.tramo_minimo_conexion_m:
                    # SUPUESTO, no observado: sin datos de puertas, tratar la
                    # contigüidad como paso es una hipótesis, y aquí queda
                    # escrita en la propia arista en vez de en un comentario.
                    aristas.append(Arista(
                        tipo=CONECTA_CON, a=a_id, b=b_id, origen=SUPUESTO,
                        separacion_m=separacion, tramo_m=tramo, distancia_m=distancia,
                    ))

    proyecto = Proyecto(
        origen="dxf",
        escala=Valor(getattr(plano.escala, "factor", None), DERIVADO),
        capa=Valor(plano.layer, OBSERVADO),
        tipologia=Valor(tipologia, "declarado") if tipologia else DESCONOCIDO_VALOR,
        ciudad=Valor(ciudad, "declarado") if ciudad else DESCONOCIDO_VALOR,
        norte_grados=Valor(norte_grados, "declarado") if norte_grados is not None else DESCONOCIDO_VALOR,
        presencia={
            "proyecto": PRESENCIA_OBSERVADO,
            "espacio": PRESENCIA_OBSERVADO,
            "unidad": PRESENCIA_OBSERVADO if etiquetas_observadas else PRESENCIA_INFERIDO,
            "edificio": PRESENCIA_INFERIDO,
            "muro": PRESENCIA_INFERIDO,  # solo espesor, y solo entre espacios contiguos
            "planta": PRESENCIA_NO_OBSERVABLE,
            "parcela": PRESENCIA_NO_OBSERVABLE,
            "hueco": PRESENCIA_NO_OBSERVABLE,
            "pilar": PRESENCIA_NO_OBSERVABLE,
            "instalacion": PRESENCIA_NO_OBSERVABLE,
        },
    )

    return Grafo(proyecto=proyecto, espacios=espacios, unidades=unidades, aristas=aristas)
