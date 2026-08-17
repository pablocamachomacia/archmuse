"""Evaluación de condiciones declarativas con lógica TERNARIA.

Paso 4 del algoritmo de `NORMATIVE_RESOLUTION.md` §7.3, y el único sitio del
resolver donde se decide qué hacer con lo que no se sabe.

**Por qué ternaria y no booleana.** Una condición que necesita un hecho que el
proyecto no declara NO descarta la regla. Un motor booleano solo tiene dos
salidas, así que un hecho ausente se convierte inevitablemente en `False` y la
regla desaparece del informe — que es la inferencia negativa que
`docs/brain/INFERENCE_ENGINE.md` §2.2 prohíbe, y la variante más peligrosa del
Bug #1 de `TECH_REVIEW.md`, porque falla como un tranquilizador "aquí no hay
nada que cumplir".

Con tres valores, un hecho desconocido propaga `DESCONOCIDO` y la regla acaba
en `aplica_no_evaluable` con la pregunta pendiente escrita al lado. Se informa,
no se puntúa, y nunca se calla.

La lógica es la de Kleene, que no es una elección estética: `NO ∧ DESCONOCIDO`
es `NO` porque una condición ya falsa lo es sin necesidad del dato que falta,
y `SI ∨ DESCONOCIDO` es `SI` por lo mismo. Preguntar por un hecho que no puede
cambiar el resultado sería ruido, y el ruido en la lista de preguntas
pendientes es lo que hace que se dejen de leer.

El vocabulario de comparadores es el catálogo CERRADO de
`docs/brain/CONSTRAINT_MODEL.md` §3.1. Ampliarlo es un acto de gobernanza del
Curador, no la reacción a una norma que no encaja.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, List, Mapping, Optional, Tuple


class Ternario(Enum):
    SI = "si"
    NO = "no"
    DESCONOCIDO = "desconocido"


# Nodos combinatorios. CATÁLOGO CERRADO, igual que los comparadores: un nodo
# no reconocido no se ignora ni se asume cierto, se marca DESCONOCIDO (ver
# `_evaluar`), que es la única salida que no miente en ninguna dirección.
NODOS = ("todas", "alguna", "no")


def _cmp_entre(valor: Any, referencia: Any) -> bool:
    lim = list(referencia)
    return lim[0] <= valor <= lim[1]


def _cmp_patron(valor: Any, referencia: Any) -> bool:
    return re.fullmatch(str(referencia), str(valor)) is not None


# Vocabulario cerrado de CONSTRAINT_MODEL.md §3.1. `existe`/`no_existe` se
# tratan aparte en `_evaluar_hoja`: son los dos únicos que preguntan POR la
# presencia del hecho, así que un hecho ausente no los deja indecidibles.
COMPARADORES = {
    ">=": lambda v, r: v >= r,
    "<=": lambda v, r: v <= r,
    ">": lambda v, r: v > r,
    "<": lambda v, r: v < r,
    "igual": lambda v, r: v == r,
    "distinto": lambda v, r: v != r,
    "entre": _cmp_entre,
    "pertenece_a": lambda v, r: v in r,
    "coincide_con_patron": _cmp_patron,
}

COMPARADORES_DE_PRESENCIA = ("existe", "no_existe")


@dataclass(frozen=True)
class ResultadoCondicion:
    """El veredicto, más lo que hizo falta y no había.

    `hechos_desconocidos` no es diagnóstico interno: es la lista de preguntas
    que el producto tiene que hacerle al arquitecto para poder pasar de
    `aplica_no_evaluable` a un veredicto. Sin ella, "no evaluable" sería una
    excusa en vez de una petición concreta.
    """

    valor: Ternario
    hechos_desconocidos: Tuple[str, ...] = ()
    traza: Tuple[str, ...] = ()

    @property
    def decidible(self) -> bool:
        return self.valor is not Ternario.DESCONOCIDO


def evaluar(condiciones: Optional[dict], hechos: Mapping[str, Any]) -> ResultadoCondicion:
    """Evalúa el árbol de condiciones de una regla sobre los hechos conocidos.

    `condiciones=None` significa "sin condiciones", es decir SI: una regla que
    no condiciona su aplicación aplica a todo su ámbito y perfil. No es un
    caso especial, es el caso normal.
    """
    if not condiciones:
        return ResultadoCondicion(Ternario.SI, (), ("sin condiciones declaradas",))
    desconocidos: List[str] = []
    traza: List[str] = []
    valor = _evaluar(condiciones, hechos, desconocidos, traza)
    # Orden estable: la traza y las preguntas viajan a un informe que tiene que
    # ser idéntico byte a byte entre dos ejecuciones (`TRACEABILITY.md` §10).
    return ResultadoCondicion(valor, tuple(sorted(set(desconocidos))), tuple(traza))


def _evaluar(
    nodo: Any, hechos: Mapping[str, Any], desconocidos: List[str], traza: List[str]
) -> Ternario:
    if not isinstance(nodo, dict):
        traza.append(f"nodo de condición mal formado ({type(nodo).__name__}): indecidible")
        return Ternario.DESCONOCIDO

    if "todas" in nodo:
        return _conjuncion(nodo["todas"] or [], hechos, desconocidos, traza)
    if "alguna" in nodo:
        return _disyuncion(nodo["alguna"] or [], hechos, desconocidos, traza)
    if "no" in nodo:
        return _negar(_evaluar(nodo["no"], hechos, desconocidos, traza))
    if "hecho" in nodo:
        return _evaluar_hoja(nodo, hechos, desconocidos, traza)

    # Un nodo desconocido NO se ignora. Ignorarlo dejaría la regla aplicando
    # incondicionalmente, que es afirmar más de lo que el corpus dice.
    traza.append(f"nodo de condición no reconocido {sorted(nodo)}: indecidible")
    return Ternario.DESCONOCIDO


def _conjuncion(
    hijos: Iterable[dict], hechos: Mapping[str, Any], desconocidos: List[str], traza: List[str]
) -> Ternario:
    valores = [_evaluar(h, hechos, desconocidos, traza) for h in hijos]
    if any(v is Ternario.NO for v in valores):
        return Ternario.NO
    if any(v is Ternario.DESCONOCIDO for v in valores):
        return Ternario.DESCONOCIDO
    return Ternario.SI


def _disyuncion(
    hijos: Iterable[dict], hechos: Mapping[str, Any], desconocidos: List[str], traza: List[str]
) -> Ternario:
    valores = [_evaluar(h, hechos, desconocidos, traza) for h in hijos]
    if any(v is Ternario.SI for v in valores):
        return Ternario.SI
    if any(v is Ternario.DESCONOCIDO for v in valores):
        return Ternario.DESCONOCIDO
    return Ternario.NO


def _negar(valor: Ternario) -> Ternario:
    if valor is Ternario.SI:
        return Ternario.NO
    if valor is Ternario.NO:
        return Ternario.SI
    return Ternario.DESCONOCIDO


def _evaluar_hoja(
    nodo: dict, hechos: Mapping[str, Any], desconocidos: List[str], traza: List[str]
) -> Ternario:
    hecho = nodo["hecho"]
    comparador = nodo.get("comparador", "igual")
    referencia = nodo.get("valor")
    presente = hecho in hechos and hechos[hecho] is not None

    if comparador in COMPARADORES_DE_PRESENCIA:
        # Estos dos SÍ son decidibles con el hecho ausente: preguntan
        # exactamente por eso. Ojo con la asimetría — `no_existe` aquí
        # significa "el proyecto no declara este hecho", nunca "el hecho no se
        # da en la realidad"; una regla que dependa de lo segundo está mal
        # escrita y el Curador tiene que rechazarla.
        resultado = presente if comparador == "existe" else not presente
        traza.append(f"{hecho} {comparador} -> {resultado}")
        return Ternario.SI if resultado else Ternario.NO

    if not presente:
        desconocidos.append(hecho)
        traza.append(f"{hecho}: no declarado -> indecidible")
        return Ternario.DESCONOCIDO

    fn = COMPARADORES.get(comparador)
    if fn is None:
        traza.append(f"comparador «{comparador}» fuera del catálogo cerrado: indecidible")
        return Ternario.DESCONOCIDO

    try:
        resultado = bool(fn(hechos[hecho], referencia))
    except (TypeError, ValueError, IndexError) as exc:
        # Comparar un texto con un número es un error de corpus. Se marca
        # indecidible en vez de reventar: la regla se informa y el fallo se ve.
        traza.append(f"{hecho} {comparador} {referencia!r}: comparación imposible ({exc})")
        return Ternario.DESCONOCIDO

    traza.append(f"{hecho}={hechos[hecho]!r} {comparador} {referencia!r} -> {resultado}")
    return Ternario.SI if resultado else Ternario.NO
