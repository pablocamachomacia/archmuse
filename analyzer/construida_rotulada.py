# -*- coding: utf-8 -*-
"""Una polilínea rotulada como construida nunca es la superficie útil de una estancia.

**Regla de Pablo, firmada el 2026-09-16** tras un error de cifra en un plano del
arquitecto: el tendedero de una vivienda salía con la superficie de su
construida exterior. Texto de Pablo:

    Una polilínea rotulada como construida (interior o exterior) nunca puede
    usarse como superficie útil de una estancia. Si hay duda sobre cuál es la
    útil, la celda queda vacía con motivo.

**Qué es «rotulada».** La misma lectura que `C-12` (firmado el 2026-09-13): un
rótulo señala los contornos cuyo borde está a menos de **3 alturas de su texto**.
Aquí se miran los contornos de la **capa de recintos**, que es de donde salen
las estancias.

**Decisiones de este módulo, propuestas y pendientes de firma:**

1. **Las formas del rótulo.** Las dos firmadas de la construida cerrada y las de
   la exterior: «s. construida ext.» (medida el 2026-09-16 en el plano del
   error, 28 veces), «superficie construida exterior» y «s. construida
   exterior». «Sup. construida» a secas no dice cuál es y no se incluye.
2. **Contornos anidados al alcance del mismo rótulo.** La construida contiene a
   la útil: si de los contornos al alcance uno contiene a todos los demás, el
   rotulado es ése, y los de dentro no están en duda. Medido en el plano del
   error: 14 de sus 28 rótulos exteriores tienen dos o tres contornos a su
   alcance —el útil y la construida que lo rodea—.
3. **Si quedan dos o más contornos al alcance sin que uno contenga a los
   otros**, no se sabe cuál rotula: **duda**, y ninguno se escribe como útil.
4. **Un rótulo sin altura de texto** no señala nada: sin altura no hay alcance.

**No se mira el color**, ni para decidir ni para desempatar (lo vigila un test).
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from shapely.geometry import Point, Polygon

#: Las formas firmadas de la construida cerrada (`C-12`) y las de la exterior.
FORMAS_CERRADA = ("superficie construida cerrada", "s. construida cerrada")
FORMAS_EXTERIOR = ("s. construida ext.", "superficie construida exterior",
                   "s. construida exterior")
FORMAS = FORMAS_CERRADA + FORMAS_EXTERIOR

ALCANCE_EN_ALTURAS = 3

#: Cuánto de un contorno tiene que caer dentro de otro para decir que lo
#: contiene: el mismo 90 % del descarte de agrupadores del parser.
UMBRAL_CONTENCION = 0.9

ROTULADA = "rotulada"
DUDA = "duda"


@dataclass(frozen=True)
class RotuloDeConstruida:
    handle: str
    texto: str
    punto: Tuple[float, float]       # en unidades de dibujo
    alcance: Optional[float]         # en unidades de dibujo; `None` sin altura


@dataclass(frozen=True)
class Marca:
    """Por qué un contorno no puede ser superficie útil."""

    tipo: str                        # `ROTULADA` o `DUDA`
    rotulo: RotuloDeConstruida

    @property
    def motivo(self) -> str:
        if self.tipo == ROTULADA:
            return ("su contorno es el que el plano rotula «%s»: es superficie construida, no "
                    "útil, y no se escribe como su superficie. Falta el contorno de su "
                    "superficie útil." % self.rotulo.texto)
        return ("el rótulo «%s» está a menos de %d alturas de texto de este contorno y de otro, "
                "y no se sabe cuál de los dos es la construida: no se escribe su superficie "
                "útil." % (self.rotulo.texto, ALCANCE_EN_ALTURAS))


def _comparable(texto: Optional[str]) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto or "")
    sin_acentos = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(sin_acentos.lower().split())


def es_rotulo_de_construida(texto: Optional[str]) -> bool:
    return _comparable(texto) in FORMAS


def rotulos(doc) -> List[RotuloDeConstruida]:
    """Los rótulos de construida del espacio modelo, de cualquier capa, en
    unidades de dibujo. Lo que dibujó ArchMuse no rotula nada."""
    from . import parser
    from .geometria_recibida import altura_de_texto, handle_de_origen
    from .propio import es_de_archmuse

    salida: List[RotuloDeConstruida] = []
    for entidad in doc.modelspace().query("TEXT MTEXT"):
        if es_de_archmuse(entidad):
            continue
        texto = parser._texto_de(entidad)
        if not es_rotulo_de_construida(texto):
            continue
        punto = parser._punto_de_texto(entidad)
        if punto is None:
            continue
        altura = altura_de_texto(entidad)
        salida.append(RotuloDeConstruida(
            handle_de_origen(entidad), " ".join(texto.split()), (float(punto[0]), float(punto[1])),
            ALCANCE_EN_ALTURAS * altura if altura else None))
    return salida


def contiene(fuera: Polygon, dentro: Polygon) -> bool:
    try:
        return (fuera.area > dentro.area
                and fuera.intersection(dentro).area >= UMBRAL_CONTENCION * dentro.area)
    except Exception:  # noqa: BLE001 - geometría de un DXF ajeno
        return False


def marcar(poligonos: Sequence[Polygon],
           rotulos_del_plano: Sequence[RotuloDeConstruida]) -> Dict[int, Marca]:
    """`{índice en poligonos: Marca}` de los contornos que un rótulo de
    construida señala (`ROTULADA`) o deja en duda (`DUDA`).

    Una marca `ROTULADA` gana a una `DUDA` de otro rótulo: si un rótulo lo
    señala sin ambigüedad, eso es lo que es."""
    marcas: Dict[int, Marca] = {}
    if not poligonos or not rotulos_del_plano:
        return marcas
    import shapely

    arbol = shapely.STRtree(list(poligonos))
    for rotulo in rotulos_del_plano:
        if rotulo.alcance is None:
            continue
        punto = Point(rotulo.punto)
        cerca = arbol.query(punto.buffer(rotulo.alcance), predicate="intersects").tolist()
        al_alcance = [i for i in cerca
                      if poligonos[i].exterior.distance(punto) <= rotulo.alcance]
        if not al_alcance:
            continue
        exteriores = [i for i in al_alcance
                      if not any(j != i and contiene(poligonos[j], poligonos[i])
                                 for j in al_alcance)]
        tipo = ROTULADA if len(exteriores) == 1 else DUDA
        for i in exteriores:
            previa = marcas.get(i)
            if previa is None or (previa.tipo == DUDA and tipo == ROTULADA):
                marcas[i] = Marca(tipo, rotulo)
    return marcas
