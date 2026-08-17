# -*- coding: utf-8 -*-
"""C1 — Identidad en dos niveles.

    instance_id   identifica un nodo DENTRO de una versión del grafo.
                  Determinista, derivado del orden de lectura. Se regenera en
                  cada lectura y no significa nada fuera de ella.

    concept_id    identifica «esta habitación» a lo largo de la vida del
                  proyecto. Opaco. Se asigna en la primera lectura y se hereda
                  por emparejamiento en las siguientes.

**Por qué dos y no uno.** `OBSERVATION_MODEL.md` construye todo el ciclo de
vida de los hallazgos —que un problema persista, se agrave o se resuelva en vez
de desaparecer y reaparecer como nuevo— sobre una identidad de ámbito estable.
Y hoy no hay ninguna: `circulation.py` usaba `id()` de Python, la identidad
más efímera que existe. Sin esto no hay editor, ni histórico, ni comparación
entre versiones.

**Prohibido por contrato:** derivar `concept_id` de cualquier valor que pueda
cambiar —centroide, área, rótulo, índice, nombre de unidad—. Dos habitaciones
pueden tener por casualidad la misma superficie, que es el mismo motivo por el
que `FACT_MODEL.md` §11.3 prohibió deduplicar hechos por valor desnudo.

**La semilla, y por qué no es una trampa.** Un `uuid4` por nodo haría que dos
lecturas del mismo DXF produjeran JSON distintos, y entonces ni los goldens ni
la comprobación de determinismo serían posibles. Con `semilla`, el
`concept_id` es un `uuid5` sobre `(semilla, instance_id)`: sigue siendo opaco
—no se puede leer de él ni el área ni el rótulo— y es reproducible. Esto vale
**sólo para la primera lectura**, que es la única que asigna identidades
nuevas; a partir de la segunda las hereda `emparejar()`, y ahí el orden de
lectura ya no interviene. Sin `semilla` se usa `uuid4`, que es lo correcto en
producción cuando cada proyecto nace una vez.
"""
from __future__ import annotations

import uuid
from typing import Dict, Optional

# Espacio de nombres propio de ArchMuse para los `uuid5` reproducibles.
# Constante fija: cambiarla invalidaría todos los `concept_id` ya emitidos.
NAMESPACE_ARCHMUSE = uuid.UUID("6f1b0c62-4d1f-5a3e-9c77-4f5a2b1d8e30")

LONGITUD_CONCEPTO = 12  # hex, misma forma que los ids de `analyzer/storage.py`


class Identidades:
    """Asigna los dos niveles de identidad de una versión del grafo.

    Se instancia una vez por construcción. Los contadores por prefijo hacen
    que el `instance_id` dependa **sólo** del orden en que el constructor crea
    los nodos, que es el orden de lectura del parser — congelado en G1
    precisamente porque es contrato.
    """

    def __init__(self, semilla: Optional[str] = None) -> None:
        self.semilla = semilla
        self._contadores: Dict[str, int] = {}
        self._conceptos: Dict[str, str] = {}

    # --- instance_id ------------------------------------------------------

    def instancia(self, prefijo: str, ancho: int = 4) -> str:
        """Siguiente `instance_id` de un prefijo: `es-0001`, `un-0001`, `pl-01`…"""
        siguiente = self._contadores.get(prefijo, 0) + 1
        self._contadores[prefijo] = siguiente
        return "%s-%0*d" % (prefijo, ancho, siguiente)

    # --- concept_id -------------------------------------------------------

    def concepto(self, instance_id: str) -> str:
        """`concept_id` para un nodo recién creado.

        Idempotente dentro de una misma versión: pedir dos veces el concepto
        del mismo `instance_id` devuelve el mismo valor. Eso importa porque el
        constructor crea el nodo y luego lo referencia desde su contenedor.
        """
        if instance_id in self._conceptos:
            return self._conceptos[instance_id]
        if self.semilla is None:
            valor = uuid.uuid4().hex[:LONGITUD_CONCEPTO]
        else:
            clave = "%s|%s" % (self.semilla, instance_id)
            valor = uuid.uuid5(NAMESPACE_ARCHMUSE, clave).hex[:LONGITUD_CONCEPTO]
        self._conceptos[instance_id] = valor
        return valor


def emparejar(version_anterior, version_nueva) -> Dict[str, str]:
    """`instance_id` de la versión nueva -> `concept_id` heredado de la anterior.

    **No implementado en E1, y es deliberado.** El mecanismo que propone
    `KNOWLEDGE_GRAPH.md` §3 —emparejar por solapamiento geométrico, unidad de
    pertenencia y tipo resuelto— está propuesto, no demostrado: habitaciones
    fusionadas, partidas o renumeradas son casos genuinamente ambiguos, y un
    emparejamiento es una **inferencia**, no un hecho. Resolverlo exige dos
    versiones reales del mismo plano, que hoy no tenemos.

    Existe como función, y no como hueco, para que el vacío esté declarado: si
    alguien necesita identidad entre versiones antes de E2, se encuentra este
    error y una decisión que tomar, no un `dict` vacío que parece funcionar.
    """
    raise NotImplementedError(
        "El emparejamiento entre versiones se decide en E2 "
        "(docs/design/2026-08-11-modelo-arquitectonico-comun.md §17.4). "
        "Hasta entonces, cada lectura asigna concept_id nuevos."
    )
