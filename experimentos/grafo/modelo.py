"""Nodos y aristas del grafo de conocimiento (experimento de validación).

Aplica dos reglas de `docs/brain/KNOWLEDGE_GRAPH.md` y ninguna más, porque son
las dos que el experimento tiene que poder poner a prueba:

- §0.1 — el grafo describe, no juzga: aquí no hay ningún campo evaluativo
  (`iluminacion`, `cumple`, `puntuacion`). Solo geometría, identidad y
  relaciones.
- §0.3 — ningún atributo resuelto es un valor desnudo: el tipo de espacio es
  siempre un par (valor, origen) y `desconocido` es un valor legítimo.

La geometría shapely vive en `_poligono`, con guion bajo a propósito: las
reglas no deben tocarla. Lo que se les ofrece son los derivados admitidos por
§0.2 (función pura de la geometría del propio nodo, sin umbrales).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --- Orígenes epistémicos (§0.3) -------------------------------------------

OBSERVADO = "observado"
DECLARADO = "declarado"
DERIVADO = "derivado"
SUPUESTO = "supuesto"
DESCONOCIDO = "desconocido"

# --- Estados de presencia (§0.4) -------------------------------------------

PRESENCIA_OBSERVADO = "observado"
PRESENCIA_INFERIDO = "inferido"
PRESENCIA_NO_OBSERVABLE = "no_observable"
PRESENCIA_AUSENCIA_VERIFICADA = "ausencia_verificada"

# --- Tipos de relación (§0.5) ----------------------------------------------

ES_CONTIGUO_A = "es_contiguo_a"
CONECTA_CON = "conecta_con"

# --- Agrupaciones de tipo de espacio ---------------------------------------
#
# `evaluator.py` no puede distinguir Salón de Cocina: su patrón es literalmente
# `SALON|COCINA`, un solo umbral para dos tipos que `SPACE_TAXONOMY.md` define
# por separado. El grafo sí los separa; una regla que necesite "pieza social"
# pide los dos y lo dice.
PIEZA_SOCIAL = ("salon", "cocina")
PIEZA_HUMEDA = ("bano", "aseo")
CIRCULACION = ("circulacion",)


@dataclass(frozen=True)
class Valor:
    """Un atributo resuelto: nunca el valor a secas, siempre con su origen."""

    valor: Optional[object]
    origen: str

    @property
    def conocido(self) -> bool:
        return self.origen != DESCONOCIDO and self.valor is not None

    def __str__(self) -> str:
        if not self.conocido:
            return "desconocido"
        return f"{self.valor} ({self.origen})"


DESCONOCIDO_VALOR = Valor(None, DESCONOCIDO)


@dataclass
class Espacio:
    """Una estancia. El único nodo que hoy tiene datos observados de verdad."""

    id: str  # instance_id: identifica el nodo en esta versión del grafo
    concepto: str  # concept_id: identifica "esta habitación" entre versiones
    unidad_id: str
    rotulo: Optional[str]  # el texto literal leído del plano, sin interpretar
    tipo: Valor  # tipo canónico + origen (§0.3)
    _poligono: object = field(repr=False, default=None)  # shapely: no lo tocan las reglas
    procedencia: str = ""  # puntero al origen (capa del DXF), §2.6

    # --- Derivados admitidos (§0.2: función pura de la propia geometría) ---

    @property
    def area_m2(self) -> float:
        return float(self._poligono.area)

    @property
    def perimetro_m(self) -> float:
        return float(self._poligono.length)

    @property
    def centroide(self) -> Tuple[float, float]:
        c = self._poligono.centroid
        return float(c.x), float(c.y)

    @property
    def alargamiento(self) -> float:
        """Lado mayor / lado menor del rectángulo envolvente mínimo."""
        rect = self._poligono.minimum_rotated_rectangle
        xs, ys = rect.exterior.coords.xy
        lados = []
        for i in range(len(xs) - 1):
            dx, dy = xs[i + 1] - xs[i], ys[i + 1] - ys[i]
            lados.append((dx * dx + dy * dy) ** 0.5)
        if len(lados) < 2:
            return 1.0
        # Dos lados CONSECUTIVOS del rectángulo (largo y ancho). Coger los dos
        # mayores daría siempre 1.0: en un rectángulo los dos lados largos son
        # iguales.
        largo, ancho = lados[0], lados[1]
        menor = min(largo, ancho) or 1e-9
        return max(largo, ancho) / menor

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other) -> bool:
        return isinstance(other, Espacio) and other.id == self.id

    def __repr__(self) -> str:
        return f"<Espacio {self.id} {self.tipo.valor or '?'} {self.area_m2:.1f}m²>"


@dataclass
class Unidad:
    """Vivienda o local. Observada si el plano la etiqueta, inferida si no."""

    id: str
    etiqueta: Valor  # (nombre, observado) si venía del rótulo VT; (nombre, derivado) si se agrupó
    espacios: List[str] = field(default_factory=list)  # ids, en el orden de lectura del plano


@dataclass
class Arista:
    tipo: str  # ES_CONTIGUO_A | CONECTA_CON
    a: str
    b: str
    origen: str
    separacion_m: float = 0.0  # hueco entre contornos: el espesor del muro (§2.7)
    tramo_m: float = 0.0  # longitud del tramo enfrentado
    distancia_m: float = 0.0  # centroide a centroide: el peso para recorridos


@dataclass
class Proyecto:
    """Raíz del grafo. Lleva lo que se sabe del análisis y, sobre todo, lo que
    no se sabe: el mapa de presencia por tipo de nodo (§0.4)."""

    origen: str
    escala: Valor
    capa: Valor
    tipologia: Valor = DESCONOCIDO_VALOR
    ciudad: Valor = DESCONOCIDO_VALOR
    norte_grados: Valor = DESCONOCIDO_VALOR
    presencia: Dict[str, str] = field(default_factory=dict)
