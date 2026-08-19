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


# --- Retirada del registro (D-12, 2026-08-19) --------------------------------
#
# `CAPACIDADES` vacia A PROPOSITO. La funcion de arriba sigue viva, `bim/` sigue
# entero y sus tests siguen pasando: lo unico que se ha retirado es la ENTRADA EN
# EL REGISTRO.
#
# Motivo, medido en la auditoria de `docs/design/2026-08-19-auditoria-del-
# registro-de-capacidades.md`: no la invocaba ninguna Skill y no la consumia
# ningun entregable. Sus unicas menciones fuera de este modulo estaban en tests.
# Una capacidad registrada que no lleva a ningun entregable no es gratis: ocupa
# una plaza del catalogo que `C4` limita, viaja en el manifiesto que ve el
# planificador y le ofrece al modelo una herramienta que no termina en nada.
#
# Como volver a registrarla, cuando exista la Skill que la use (`OP-5`, contraste
# IFC-DXF): restaurar la tupla de abajo en el MISMO cambio que esa Skill. Son
# cinco lineas y el `Capacidad(...)` completo esta en el historial de git
# (`git log -p -- agente/herramientas/bim.py`). Aprobado por Pablo el 2026-08-19.
CAPACIDADES = ()
