# -*- coding: utf-8 -*-
"""Capacidad: inventario de un modelo IFC.

Es el primer paso alcanzable de «revisa este modelo BIM», y está deliberadamente
por debajo de lo que esa frase promete. Un inventario dice **qué hay** en el
modelo y **qué superficies declara**; no dice si el modelo está bien, si cumple
normativa, si la geometría es coherente ni si falta algo. Cada una de esas
cuatro cosas es una capacidad distinta con su propia forma de equivocarse, y
mezclarlas en una función llamada «revisar» es cómo se construye un producto que
suena capaz y no lo es.

Envuelve `bim/lector_ifc.py`, que es la frontera de dominio. La capacidad no
añade lógica: traduce a resultado estructurado y traduce el fallo a un `ok:
false` con motivo.
"""
from __future__ import annotations

from typing import Any, Dict

from bim import IFCIlegible, inventariar

from ..capacidad import Capacidad


def inventario_de_ifc(ruta: str) -> Dict[str, Any]:
    """Qué contiene un fichero IFC, y qué superficies declara."""
    try:
        inventario = inventariar(ruta)
    except IFCIlegible as exc:
        return {"ok": False, "error": "ifc_ilegible", "detalle": str(exc)}

    salida: Dict[str, Any] = {"ok": True}
    salida.update(inventario.a_dict())
    return salida


CAPACIDADES = (
    Capacidad(
        id="bim.inventario_de_ifc",
        version="1.0.0",
        dominio="bim",
        naturaleza="determinista",
        descripcion=(
            "Lee un fichero IFC y devuelve qué contiene: esquema, proyecto, plantas, "
            "espacios con su uso y su superficie DECLARADA, y el recuento por clase de "
            "elemento. Las superficies que el modelo no declara vuelven como null con "
            "motivo: no se calculan a partir de la geometría."
        ),
        parametros={
            "type": "object",
            "properties": {
                "ruta": {
                    "type": "string",
                    "description": "Ruta del fichero .ifc en el sistema de ficheros.",
                },
            },
            "required": ["ruta"],
            "additionalProperties": False,
        },
        funcion=inventario_de_ifc,
        efectos=(),
        limitaciones=(
            "no valida el modelo: no comprueba coherencia geométrica, duplicados ni "
            "elementos que falten",
            "no calcula superficies a partir de la geometría; solo lee las declaradas "
            "en Qto_SpaceBaseQuantities",
            "no interpreta la clasificación de usos del modelo ni la traduce al CTE",
            "no comprueba normativa de ningún tipo",
        ),
    ),
)
