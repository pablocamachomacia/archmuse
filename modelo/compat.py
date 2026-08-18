# -*- coding: utf-8 -*-
"""E1.11 — La capa de compatibilidad: del modelo a lo que el motor ya sabe leer.

**Por qué existe.** `evaluator.py` son ~3.000 líneas y cuarenta reglas
validadas contra un plano real, sin cobertura de comportamiento completo.
Cambiarle el sustrato de datos de un solo salto es el escenario clásico de
regresión silenciosa: sigue devolviendo números, y son otros
(`KNOWLEDGE_GRAPH.md` §9.2). El modelo se construye **al lado**, y esta capa
traduce, para que las cuarenta reglas sigan funcionando sin tocarse.

Tres traducciones, y ninguna más:

1. `a_unidades(grafo)` -> `List[evaluator.Unit]`. La vista de compatibilidad
   completa. Congelada contra G2, que es la definición operativa de «el mismo
   orden y la misma composición».
2. `grafo_de_adyacencia(unidad)` -> el `dict` con la forma exacta de
   `analyzer/adyacencia.py`. Es lo que consume `circulation.py`.
3. `tipos_de_unidad(unidad)` -> `Dict[id(Room), frozenset[str]]` (E3,
   `docs/prd/2026-08-11-e3-clasificacion-circulation.md`). El tipo (y los
   ambiguos) que el modelo asigna a cada `Room`, para que `circulation.py`
   pregunte «¿el tipo de esta habitación cae en este conjunto?» en vez de
   averiguarlo con su propio regex.

**Sobre el `id()` de Python que aparece aquí.** La forma de `adyacencia.Grafo`
es `Dict[int, List[Tuple[Room, float]]]` con `id(Room)` como clave. Eso es
precisamente lo que el modelo elimina — y por eso vive **sólo aquí**, en el
adaptador, que es el sitio cuyo trabajo es hablar el idioma viejo. Ni un nodo
ni una arista del modelo usan identidad de objeto: usan `instance_id`
determinista. Cuando `circulation.py` deje de necesitar esta forma, la función
desaparece con ella.

**E2 (C-E2.3) — memoización de `grafo_de_adyacencia`, por identidad de
objeto.** Antes de E2, cada llamada reconstruía el modelo de la vivienda desde
cero: con `ejemplo.dxf`, `evaluate_circulation()` se llama dos veces por
vivienda (`api_serializer.py` y `chain_effects.py`), así que un único análisis
de 6 viviendas construía el modelo **12 veces**. Las dos llamadas comparten
siempre el mismo objeto `Unit` (viene de `advanced.unit_scores`, no se
reconstruye entre medias), así que cachear por `id(unidad)` colapsa las dos en
una sin cambiar la firma de `evaluate_circulation`, `api_serializer.py` ni
`chain_effects.py` — el cambio mínimo que pedía el PRD de E2, ninguno más.

**Por qué NO es un `id()` ingenuo.** Un `dict` cacheado por `id(unidad)` sin
más, en un proceso Flask de vida larga, arriesga que un `Unit` se recolecte y
otro objeto reciba el mismo `id()` más tarde — devolvería el grafo de una
vivienda que ya no existe para una que sí. Por eso cada entrada lleva un
`weakref.ref` sobre el propio `Unit`, con un callback que borra la entrada en
cuanto el objeto se recolecta: la caché nunca sobrevive al objeto que la
originó, así que no hay ventana en la que un `id()` reciclado pueda leer una
entrada ajena. El `semilla` no participa en la clave a propósito: no cambia ni
una arista ni una distancia de la topología (sólo `concept_id`, que esta
función ni siquiera expone), así que dos llamadas con distinta semilla sobre
el mismo `Unit` deben compartir caché, no duplicarla.
"""
from __future__ import annotations

import weakref
from typing import Dict, FrozenSet, List, Optional, Tuple

from analyzer import evaluator, parser  # frontera declarada (junto a constructor.py)

from .aristas import CONECTA_CON
from .constructor import clasificar, construir_de_unidad
from .geometria import HUELLA_2D
from .grafo import Grafo

# id(Unit) -> grafo de adyacencia ya calculado para ese objeto exacto.
# Limpiada por los callbacks de `weakref.ref` en `_CENTINELAS`, nunca a mano.
_CACHE_ADYACENCIA: Dict[int, Dict[int, List[Tuple]]] = {}
# Mantiene vivas las weakrefs (si no se guardan en algún sitio, Python las
# recolecta de inmediato y el callback nunca llegaría a dispararse).
_CENTINELAS: Dict[int, "weakref.ref"] = {}


def _olvidar(clave: int) -> None:
    _CACHE_ADYACENCIA.pop(clave, None)
    _CENTINELAS.pop(clave, None)


def a_rooms(grafo: Grafo, unidad_id: str) -> List[parser.Room]:
    """Los espacios de una unidad como `parser.Room`, en orden del modelo.

    El rótulo literal, la geometría y la capa de procedencia son exactamente
    los que entraron: la vuelta es sin pérdida para lo que `evaluator` mira.
    """
    rooms = []
    for espacio in grafo.espacios_de(unidad_id):
        rooms.append(parser.Room(
            label=espacio.rotulo,
            polygon=grafo.almacen.bruta(espacio.geometrias[HUELLA_2D]),
            layer=espacio.procedencia.capa or "",
        ))
    return rooms


def a_unidades(grafo: Grafo) -> List[evaluator.Unit]:
    """`List[Unit]` equivalente al que produce `group_rooms_by_unit_label`.

    Mismo orden de viviendas, misma composición, mismos rótulos, misma
    geometría. Lo comprueba G2 y lo comprueba `test_modelo_compat.py`
    directamente contra la salida del evaluador sobre `ejemplo.dxf`.
    """
    return [
        evaluator.Unit(name=str(unidad.etiqueta.valor), rooms=a_rooms(grafo, unidad.id))
        for unidad in grafo.unidades()
    ]


def tipos_de_unidad(unidad: evaluator.Unit) -> Dict[int, FrozenSet[str]]:
    """Para cada `Room` de la unidad, el conjunto de tipos que le asigna el
    modelo — el tipo principal MAS sus `tipos_ambiguos` (E3, PRD
    `docs/prd/2026-08-11-e3-clasificacion-circulation.md` §5, misma
    equivalencia por conjunto que validó `tests/test_e3_paridad_clasificacion.py`).

    No construye el grafo ni la geometría: `clasificar()` es una función pura
    del rótulo, así que no hace falta pasar por `construir_de_unidad` para
    esto. Un recinto sin rótulo o sin tipo reconocido devuelve un conjunto
    vacío — no cae dentro de ningún conjunto que compare `circulation.py`,
    el mismo comportamiento que tenía un regex que no casaba con nada.

    Misma clave (`id(Room)`) que `grafo_de_adyacencia`: es la forma que
    `circulation.py` ya sabe consumir.
    """
    resultado: Dict[int, FrozenSet[str]] = {}
    for room in unidad.rooms:
        atributo, ambiguos = clasificar(room.label)
        resultado[id(room)] = (
            frozenset({atributo.valor} | set(ambiguos)) if atributo.valor else frozenset()
        )
    return resultado


def grafo_de_adyacencia(unidad: evaluator.Unit,
                        semilla: Optional[str] = None) -> Dict[int, List[Tuple]]:
    """El grafo de adyacencias de una vivienda, calculado por el modelo.

    Devuelve la forma que `analyzer/adyacencia.py` publica —`id(Room)` ->
    `[(Room, distancia)]`— con **los mismos objetos `Room`** que trae la
    unidad, para que `circulation.py` pueda seguir buscando caminos entre las
    habitaciones que ya tiene en la mano.

    **Neutralidad, y de dónde sale.** Las aristas se recorren en su orden de
    creación, que es el doble bucle `i<j` sobre los espacios de la unidad — el
    mismo que usa `adyacencia.construir_grafo`. El orden de la lista de
    vecinos decide qué camino gana cuando dos empatan, así que reproducirlo no
    es cosmética: es la diferencia entre migrar la arquitectura y migrar el
    desempate.

    **E2 — memoizado por identidad del objeto `unidad`** (ver cabecera del
    módulo): la segunda llamada sobre el mismo `Unit` no reconstruye nada.
    """
    clave = id(unidad)
    if clave in _CACHE_ADYACENCIA:
        return _CACHE_ADYACENCIA[clave]

    modelo = construir_de_unidad(unidad, semilla=semilla)
    espacios = modelo.get_spaces()
    # El constructor crea un espacio por `Room` en el mismo orden de entrada.
    # `strict=True` (tarea 7) lo exige en vez de confiarlo: si el constructor
    # dejara de emitir un espacio por Room, el diccionario saldria corto y las
    # aristas de las Rooms que faltan desaparecerian del grafo en silencio.
    room_de: Dict[str, parser.Room] = {
        espacio.id: room for espacio, room in zip(espacios, unidad.rooms, strict=True)
    }

    grafo: Dict[int, List[Tuple]] = {id(room): [] for room in unidad.rooms}
    for arista in modelo.aristas(CONECTA_CON):
        a, b = room_de[arista.a], room_de[arista.b]
        grafo[id(a)].append((b, arista.distancia_m))
        grafo[id(b)].append((a, arista.distancia_m))

    try:
        _CENTINELAS[clave] = weakref.ref(unidad, lambda _ref, clave=clave: _olvidar(clave))
        _CACHE_ADYACENCIA[clave] = grafo
    except TypeError:
        # `unidad` no admite weakref (no ocurre con un `Unit` normal, pero si
        # pasara algún día es más seguro no cachear que arriesgar una entrada
        # que nadie limpia).
        pass
    return grafo
