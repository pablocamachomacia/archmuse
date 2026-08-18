# -*- coding: utf-8 -*-
"""C3 — Las dos aristas, y el criterio que las decide una sola vez.

    es_contiguo_a   simetrica.  Espacio <-> Espacio.  Comparten separacion fisica.
    conecta_con     simetrica.  Espacio <-> Espacio.  Se puede pasar de uno a otro.

**El problema que esto cierra.** Había cinco implementaciones de «estas dos
habitaciones están juntas» con cuatro umbrales distintos, y ninguna sabía de
las otras (`KNOWLEDGE_GRAPH.md` §1): `evaluator._is_adjacent` (0,3 m de borde
compartido, eliminada en la tarea 10 del `REFACTOR_MASTERPLAN.md`),
`evaluator.group_rooms_by_proximity` (2,0 m), `adyacencia` (0,5 m),
`plan_svg._cluster_rooms` (2,0 m) y una copia literal en `ai_generator`. Las
dos que miden borde compartido no producen **ni un hallazgo** en un plano real:
de los 85 pares de `ejemplo.dxf`, uno solo supera los 0,3 m, y es Terraza
contra Terraza. Aquí la topología se decide en un sitio, se justifica en un
sitio y se corrige en un sitio.

**La pertenencia NO es una arista.** `Espacio.unidad_id` y `Espacio.planta_id`
son campos. Representarla dos veces —campo y arista— es la primera vía por la
que un modelo empieza a poder contradecirse consigo mismo.

**`conecta_con` lleva `supuesto` siempre, y eso es el producto.** Sin datos de
puertas no se puede saber si dos habitaciones contiguas comunican. Hoy
`circulation.py` toma esa decisión —trata la cercanía como paso— pero la toma
en silencio, dentro de una función privada. Aquí la hipótesis va escrita en la
propia arista, y todo lo que se apoye en ella hereda esa incertidumbre en vez
de heredar una falsa certeza.

**Por qué en E1 las dos relaciones coinciden exactamente.** El criterio por
defecto filtra sólo por distancia; `tramo_m` se mide y se guarda pero no
filtra. Es la decisión 3 cerrada por Pablo el 2026-08-11: el umbral de
contigüidad sigue abierto hasta tener 5–8 proyectos reales, porque el
experimento demostró que el 0,60 m propuesto no está justificado —en VT3/3 hay
un tramo enfrentado de 0,570 m del que depende que aparezca un hallazgo—. Que
`es_contiguo_a` y `conecta_con` tengan hoy los mismos 45 pares no es un
descuido: es la afirmación honesta de lo que un DXF de distribución sostiene.
Lo que ya las distingue es el `origen`, que es lo que un consumidor debe mirar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .atributo import OBSERVADO, SUPUESTO

ES_CONTIGUO_A = "es_contiguo_a"
CONECTA_CON = "conecta_con"

TIPOS = (ES_CONTIGUO_A, CONECTA_CON)


@dataclass(frozen=True)
class Criterio:
    """Cómo se decide que dos espacios son contiguos o están conectados.

    `tolerancia_muro_m` se deja a `None` a propósito: quien construye el
    modelo debe **decir** con qué tolerancia lo hace, y el constructor la toma
    del único sitio donde ese número vive hoy en el repositorio
    (`analyzer.adyacencia.WALL_GAP_TOLERANCE_M`). Poner aquí un 0,5 literal
    crearía una segunda definición del mismo umbral, que es exactamente lo que
    este módulo existe para eliminar.

    Los dos `tramo_minimo_*` valen 0,0: miden y no filtran (ver cabecera).
    """

    nombre: str = "actual"
    tolerancia_muro_m: Optional[float] = None
    tramo_minimo_contiguidad_m: float = 0.0
    tramo_minimo_conexion_m: float = 0.0

    def con_tolerancia(self, tolerancia: float) -> "Criterio":
        return Criterio(
            nombre=self.nombre,
            tolerancia_muro_m=tolerancia,
            tramo_minimo_contiguidad_m=self.tramo_minimo_contiguidad_m,
            tramo_minimo_conexion_m=self.tramo_minimo_conexion_m,
        )

    def a_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "tolerancia_muro_m": self.tolerancia_muro_m,
            "tramo_minimo_contiguidad_m": self.tramo_minimo_contiguidad_m,
            "tramo_minimo_conexion_m": self.tramo_minimo_conexion_m,
        }


CRITERIO_ACTUAL = Criterio(nombre="actual")

# El criterio de §4 de `KNOWLEDGE_GRAPH.md`, disponible y **no usado**. Está
# aquí para que la decisión abierta se pueda medir sin escribir código nuevo,
# igual que el experimento permitía compararlos.
CRITERIO_ESTRICTO = Criterio(nombre="estricto", tramo_minimo_contiguidad_m=0.6,
                             tramo_minimo_conexion_m=0.6)


@dataclass(frozen=True)
class Arista:
    """Una relación entre dos espacios, con su procedencia y sus medidas.

    `a` y `b` se guardan siempre ordenados (`a < b`) y la arista se almacena
    una sola vez: la simetría es una propiedad del tipo de relación
    (invariante I4), no algo que haya que duplicar en la lista.
    """

    tipo: str
    a: str
    b: str
    origen: str
    separacion_m: float = 0.0
    tramo_m: float = 0.0
    distancia_m: float = 0.0

    def __post_init__(self) -> None:
        if self.tipo not in TIPOS:
            raise ValueError("tipo de arista desconocido: %r" % (self.tipo,))
        if self.origen not in (OBSERVADO, SUPUESTO):
            raise ValueError(
                "una arista solo puede ser observada o supuesta, no %r" % (self.origen,))
        if self.a == self.b:
            raise ValueError("una arista no une un espacio consigo mismo: %r" % (self.a,))

    def a_dict(self) -> dict:
        return {
            "tipo": self.tipo, "a": self.a, "b": self.b, "origen": self.origen,
            "separacion_m": self.separacion_m, "tramo_m": self.tramo_m,
            "distancia_m": self.distancia_m,
        }
