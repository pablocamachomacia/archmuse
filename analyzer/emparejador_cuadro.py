# -*- coding: utf-8 -*-
"""Qué campo del cuadro es cada etiqueta, sin un diccionario de cadenas exactas.

**El problema que resuelve, medido.** Hasta el 2026-09-10 esto era un
diccionario de cadenas literales copiadas de un solo plano (`v2s.dxf`). Sobre
`v1plantas.dxf` —el mismo arquitecto, el mismo estudio, el mismo modelo de
cuadro— reconocía **13 de 17** campos. Los cuatro que fallaban no eran otro
cuadro: era el mismo señor escribiendo dos veces:

| En `v2s.dxf` | En `v1plantas.dxf` |
|---|---|
| `TOTAL SUP.UTIL INTERIOR (M2)` | `TOTAL SUP. INTERIOR (m2)` |
| `TOTAL SUP.UTIL EXTERIOR (M2)` | `TOTAL SUP. EXTERIOR (m2)` |
| `TOTAL S. UTIL (M2)` | `TOTAL S. UTIL(m2)` |
| `S. CONSTRUIDA CERRADA` | `S. CONSTRUIDA C.` |

Un espacio, un punto y una abreviatura. Con cadenas exactas, **el siguiente
plano vuelve a romperlo**, y la capacidad se convierte en una que hay que
parchear cliente a cliente.

### Cómo empareja, y por qué así

Por **palabras presentes**, no por la cadena entera. Cada campo declara qué
palabras necesita —y cuáles no puede llevar—, y una etiqueta le corresponde
cuando las cumple todas. `TOTAL SUP. INTERIOR (M2)` y
`TOTAL SUP.UTIL INTERIOR (M2)` se reducen las dos a «lleva TOTAL y lleva
INTERIOR», que es lo que las hace la misma fila; la palabra `UTIL` que las
separa deja de importar porque nunca importó.

Las palabras prohibidas hacen el trabajo fino, y es donde está la precisión:
`TOTAL S. UTIL(M2)` es el total de todo **porque no dice ni INTERIOR ni
EXTERIOR**, y `S. CONSTRUIDA C.` es la cerrada **porque no dice EXTERIOR**.

### La regla que impide que esto invente correspondencias

**Una etiqueta que encaja en dos campos no encaja en ninguno, y un campo
reclamado por dos etiquetas se queda sin ninguna.** En los dos casos se devuelve
`None` con el motivo escrito, y la celda queda sin rellenar.

Es deliberadamente estricto. Un emparejador tolerante que acierta el 95% de las
veces escribe una cifra en la fila equivocada del cuadro que alguien firma una
de cada veinte, y ese error no se ve leyendo el resultado: se ve cuando el
visado lo devuelve. Preferimos dejar una celda en blanco, que el arquitecto ve
al instante.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

from .texto_dxf import decodificar_escapes

#: Palabras que no distinguen nada y sólo hacen ruido al comparar. `M2` y `SUP`
#: aparecen o no según el día en que el arquitecto escribiera la fila, y `S` es
#: la abreviatura de «superficie» que unas veces está y otras no.
_RUIDO = frozenset({"DE", "DEL", "LA", "EL", "LOS", "LAS", "POR", "Y",
                    "M2", "M²", "SUP", "S", "N", "Nº", "NUM"})


def _tokenizar(etiqueta: str) -> FrozenSet[str]:
    """`"TOTAL SUP. INTERIOR (m2)"` -> `{"TOTAL", "INTERIOR"}`.

    Decodifica los escapes del DXF, quita los acentos, parte por todo lo que no
    sea letra o dígito, y tira el ruido. Lo que queda son las palabras que de
    verdad dicen de qué fila se trata.
    """
    texto = decodificar_escapes(etiqueta)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    piezas = re.split(r"[^0-9A-Za-z]+", texto.upper())
    return frozenset(p for p in piezas if p and p not in _RUIDO)


@dataclass(frozen=True)
class Requisito:
    """Qué tiene que decir una etiqueta para ser de este campo.

    `necesita`: una lista de grupos; la etiqueta tiene que traer **al menos una
    palabra de cada grupo**. Los grupos son alternativas de la misma idea
    («CERRADA» o su abreviatura «C»), no sinónimos sueltos.

    `prohibe`: palabras que descartan el campo aunque cumpla lo anterior.
    """

    necesita: Tuple[FrozenSet[str], ...]
    prohibe: FrozenSet[str] = frozenset()

    def casa(self, palabras: FrozenSet[str]) -> bool:
        if palabras & self.prohibe:
            return False
        return all(palabras & grupo for grupo in self.necesita)


def _req(*grupos, prohibe=()) -> Requisito:
    return Requisito(
        necesita=tuple(frozenset(g if isinstance(g, (set, frozenset, tuple, list))
                                 else (g,)) for g in grupos),
        prohibe=frozenset(prohibe),
    )


_INTERIOR = {"INTERIOR", "INTERIORES"}
_EXTERIOR = {"EXTERIOR", "EXTERIORES"}
_CONSTRUIDA = {"CONSTRUIDA", "CONSTRUIDAS"}

#: El catálogo. Es una tabla de **palabras**, no de cadenas: por eso absorbe que
#: el mismo arquitecto escriba la misma fila de dos maneras. Añadir una familia
#: nueva es añadir una fila aquí, y el test de ambigüedad de
#: `tests/test_emparejador_cuadro.py` avisa si la nueva pisa a otra.
REQUISITOS: Dict[str, Requisito] = {
    # --- piezas interiores ---
    # `salón + cocina` es una unión declarada por el propio cuadro: la fila la
    # reclama tanto quien diga SALON como quien diga COCINA. Si un cuadro
    # trajera las dos por separado, las dos reclamarían este campo y la regla de
    # ambigüedad lo dejaría sin rellenar, que es lo correcto: ese cuadro pide
    # otra cosa y hay que mirarlo.
    "salon_cocina": _req({"SALON", "COCINA"}),
    "pasillo": _req({"PASILLO", "DISTRIBUIDOR"}),
    "dormitorio_1": _req({"DORMITORIO", "DORM"}, "1"),
    "dormitorio_2": _req({"DORMITORIO", "DORM"}, "2"),
    "dormitorio_3": _req({"DORMITORIO", "DORM"}, "3"),
    "bano": _req("BANO"),
    "aseo": _req("ASEO"),
    "vestibulo": _req({"VESTIBULO", "RECIBIDOR", "HALL"}),
    # --- piezas exteriores ---
    "tendedero": _req("TENDEDERO"),
    "terraza_1": _req("TERRAZA", "1"),
    "terraza_2": _req("TERRAZA", "2"),
    # --- totales ---
    # El total de una de las dos magnitudes lleva su palabra; el total de todo
    # es el que NO lleva ninguna de las dos. Ésa es toda la diferencia entre
    # `TOTAL SUP. INTERIOR (M2)` y `TOTAL S. UTIL(M2)`.
    "total_util_interior": _req("TOTAL", _INTERIOR, prohibe=_CONSTRUIDA),
    "total_util_exterior": _req("TOTAL", _EXTERIOR, prohibe=_CONSTRUIDA),
    "total_util": _req("TOTAL", {"UTIL", "UTILES"},
                       prohibe=set(_INTERIOR) | set(_EXTERIOR) | set(_CONSTRUIDA)),
    # --- superficie construida: otra magnitud, no suma con la útil ---
    "superficie_construida_cerrada": _req(_CONSTRUIDA, {"CERRADA", "C"},
                                          prohibe=_EXTERIOR),
    "superficie_construida_exterior": _req(_CONSTRUIDA, _EXTERIOR),
    # --- lo que no es una superficie ---
    # `prohibe` CUADRO y SUPERFICIES para no reclamar el título del propio
    # cuadro, «CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA», que lleva las dos
    # palabras que este campo necesita.
    "vivienda_tipo": _req("VIVIENDA", "TIPO", prohibe={"CUADRO", "SUPERFICIES"}),
    "numero_unidades": _req({"UDS", "UD", "UNIDADES", "VIVIENDAS"}),
}

#: Todos los campos que un cuadro puede pedir. Mismo contenido que
#: `cuadro_superficies.CAMPOS_DEL_CUADRO`; se comprueba en los tests que no se
#: separen.
CAMPOS = tuple(REQUISITOS)


@dataclass(frozen=True)
class Emparejamiento:
    """Qué campo es una etiqueta, o por qué no se sabe."""

    etiqueta: str
    campo: Optional[str]
    motivo: Optional[str] = None

    @property
    def resuelto(self) -> bool:
        return self.campo is not None


def campos_que_reclama(etiqueta: str) -> List[str]:
    """Los campos cuyos requisitos cumple `etiqueta`. Normalmente cero o uno."""
    palabras = _tokenizar(etiqueta)
    if not palabras:
        return []
    return [campo for campo, req in REQUISITOS.items() if req.casa(palabras)]


def emparejar(etiquetas: Sequence[str]) -> List[Emparejamiento]:
    """Empareja **todas las etiquetas del cuadro a la vez**, no una a una.

    De una en una no se puede detectar que dos filas distintas reclamen el mismo
    campo, que es la ambigüedad que de verdad hace daño: dos filas «tendedero»
    en el mismo cuadro y ArchMuse escribiendo la superficie en la primera que
    encuentra.
    """
    reclamos = [(e, campos_que_reclama(e)) for e in etiquetas]

    cuantos_reclaman: Dict[str, int] = {}
    for _etiqueta, campos in reclamos:
        if len(campos) == 1:
            cuantos_reclaman[campos[0]] = cuantos_reclaman.get(campos[0], 0) + 1

    resultado: List[Emparejamiento] = []
    for etiqueta, campos in reclamos:
        if not campos:
            resultado.append(Emparejamiento(etiqueta, None, None))
        elif len(campos) > 1:
            resultado.append(Emparejamiento(
                etiqueta, None,
                "«%s» encaja en %d campos a la vez (%s): no se rellena, porque "
                "elegir uno sería adivinar" % (etiqueta, len(campos),
                                               ", ".join(sorted(campos)))))
        elif cuantos_reclaman.get(campos[0], 0) > 1:
            resultado.append(Emparejamiento(
                etiqueta, None,
                "hay %d filas del cuadro que piden «%s»: ninguna se rellena, "
                "porque no se sabe cuál es cuál"
                % (cuantos_reclaman[campos[0]], campos[0])))
        else:
            resultado.append(Emparejamiento(etiqueta, campos[0], None))
    return resultado
