# -*- coding: utf-8 -*-
"""Detector de cifras sin respaldo en la respuesta final.

**El problema, dicho sin adornos.** Los tres primeros mecanismos anti-invención
del núcleo son estructurales y no se pueden burlar: el resultado de una
herramienta lo produce el ejecutor, una capacidad inexistente se rechaza, y
toda capacidad devuelve un `dict` con `ok`. Ninguno de los tres impide lo
único que queda: que el modelo escriba en su prosa final un número que no
estaba en ningún resultado. Un «el límite es de 30 m» donde la herramienta dijo
25 pasa los tres filtros anteriores.

**Qué hace esto.** Recoge todas las cifras de la respuesta y comprueba que cada
una aparece en el respaldo: los resultados de las herramientas ejecutadas y lo
que escribió el propio usuario. Es exactamente el criterio que el encargo del
curador normativo impone a una ficha —«cada número de una ficha aparece en el
literal citado»— aplicado a la salida del agente.

**Qué NO hace, y conviene decirlo.** No es una demostración de veracidad: una
cifra puede estar respaldada y usarse mal (leer 35 de la fila equivocada de una
tabla la deja «respaldada»). Y puede dar falsos positivos, de tres clases
conocidas: una enumeración («1.»), una cantidad escrita en cifra que nadie
midió («tres opciones»), y —la más frecuente— un **recuento** de algo que sí
está: si la herramienta devuelve la lista de doce materias sin cobertura, el
doce no aparece en ninguna parte y «quedan 12 materias» se marca. Por eso esto
**marca** la respuesta en vez de bloquearla: quien la consume decide. Su valor
es convertir «se lo ha inventado» en algo que sale en un test.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable, Tuple

# Un número tal como se escribe en castellano o en JSON. Deliberadamente
# simple: el separador de miles no se contempla porque las herramientas no lo
# emiten, y contemplarlo aquí crearía la ilusión de que sí.
_NUMERO = re.compile(r"\d+(?:[.,]\d+)?")


def _canonico(bruto: str) -> str:
    """«25», «25.0» y «25,00» son la misma cifra y tienen que comparar igual."""
    try:
        valor = float(bruto.replace(",", "."))
    except ValueError:  # pragma: no cover - el patrón ya garantiza el formato
        return bruto
    texto = "%.6f" % valor
    return texto.rstrip("0").rstrip(".") or "0"


def cifras(texto: str) -> Tuple[str, ...]:
    """Las cifras de un texto, canonizadas y sin repetir, en orden de aparición."""
    vistas = dict.fromkeys(_canonico(m.group()) for m in _NUMERO.finditer(texto))
    return tuple(vistas)


def _texto_de(valor: Any) -> str:
    if isinstance(valor, str):
        return valor
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, default=str)


def sin_respaldo(respuesta: str, respaldo: Iterable[Any]) -> Tuple[str, ...]:
    """Cifras de `respuesta` que no aparecen en ninguna pieza del respaldo.

    `respaldo` admite cadenas y estructuras: las estructuras se serializan a
    JSON, que es exactamente la forma en la que el resultado de la herramienta
    viajó hasta el modelo. Comparar contra lo que el modelo llegó a ver es lo
    que hace que el resultado signifique algo.
    """
    respaldadas = set()
    for pieza in respaldo:
        respaldadas.update(cifras(_texto_de(pieza)))
    return tuple(c for c in cifras(respuesta) if c not in respaldadas)
