# -*- coding: utf-8 -*-
"""Capacidad territorial: de lo que el arquitecto dice al ámbito que le rige.

Es el primer eslabón de la cadena y el que hace posible el segundo: sin la
cadena de ámbitos no se puede saber qué normativa aplica, porque en España la
normativa de un proyecto es estatal **más** autonómica **más** municipal, y
cuál toca depende del código INE del municipio, no de su nombre.

Envuelve `normativa/registro.py`, que ya existe, está probado y es
determinista. La capacidad no añade lógica: añade un contrato de entrada y
salida estructurado, y traduce los dos errores del registro —desconocido y
ambiguo— en resultados que el agente puede leer sin adivinar.

**El caso ambiguo es el interesante.** Hay municipios homónimos en provincias
distintas. El registro se niega a elegir por el usuario, y esta capacidad
conserva esa negativa: devuelve `ok: false` con los candidatos y la pregunta
que los desambigua. Un agente que ante la ambigüedad escoge el más poblado no
está ayudando, está inventando.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from normativa.errores import AmbitoAmbiguo, AmbitoDesconocido
from normativa.registro import registro as _registro_geografico

from ..capacidad import Capacidad


def resolver_ambito(municipio: str, provincia: Optional[str] = None) -> Dict[str, Any]:
    """Nombre de municipio -> cadena territorial completa, con su código INE."""
    reg = _registro_geografico()
    try:
        codigos = reg.buscar_municipio(municipio, provincia)
        if not codigos:
            raise AmbitoDesconocido(municipio, "municipio")
        if len(codigos) > 1:
            raise AmbitoAmbiguo(
                municipio,
                [
                    {
                        "codigo": c,
                        "nombre": reg.municipios[c]["nombre"],
                        "provincia": reg.provincias[reg.municipios[c]["provincia"]]["nombre"],
                    }
                    for c in codigos
                ],
            )
    except AmbitoDesconocido as exc:
        return {
            "ok": False,
            "error": "municipio_desconocido",
            "detalle": str(exc),
            "pregunta": (
                f"«{municipio}» no está en el registro geográfico de ArchMuse. "
                f"¿Puedes confirmar el nombre o dar el municipio con su provincia?"
            ),
        }
    except AmbitoAmbiguo as exc:
        return {
            "ok": False,
            "error": "municipio_ambiguo",
            "detalle": str(exc),
            "candidatos": list(exc.candidatos),
            "pregunta": (
                f"Hay {len(exc.candidatos)} municipios llamados «{municipio}». "
                f"¿De qué provincia es el proyecto?"
            ),
        }

    codigo = codigos[0]
    cadena = reg.cadena_de_municipio(codigo)
    return {
        "ok": True,
        "codigo_municipio": codigo,
        "nombre_municipio": reg.municipios[codigo]["nombre"],
        "cadena": [
            {"id": a.id, "nivel": a.nivel, "nombre": a.nombre} for a in cadena.ambitos
        ],
        "aviso": (
            "El registro geográfico es una semilla manual sin verificar contra el "
            "fichero oficial del INE: que un municipio no aparezca no implica que "
            "no exista."
        ),
    }


CAPACIDADES = (
    Capacidad(
        id="territorial.resolver_ambito",
        version="1.0.0",
        dominio="territorial",
        naturaleza="determinista",
        descripcion=(
            "Resuelve un municipio español a su código INE y a la cadena completa de "
            "ámbitos que le rige (estatal, autonómico, provincial, municipal). Es el "
            "paso previo obligatorio para saber qué normativa aplica a un proyecto. "
            "Si el nombre es ambiguo o no está en el registro devuelve ok=false con "
            "la pregunta que lo desbloquea; en ese caso hay que preguntar al usuario, "
            "no elegir un municipio."
        ),
        parametros={
            "type": "object",
            "properties": {
                "municipio": {
                    "type": "string",
                    "description": "Nombre del municipio, con o sin tildes.",
                },
                "provincia": {
                    "type": "string",
                    "description": "Provincia, solo para desambiguar homónimos.",
                },
            },
            "required": ["municipio"],
            "additionalProperties": False,
        },
        funcion=resolver_ambito,
        efectos=(),
        limitaciones=(
            "el registro de municipios es una semilla manual, no el fichero oficial del INE",
            "no resuelve ámbitos sectoriales (costas, patrimonio, aeroportuario)",
        ),
    ),
)
