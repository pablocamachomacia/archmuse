# -*- coding: utf-8 -*-
"""Capacidades de medición de una planta entera: varias viviendas, no una.

**Por qué estas dos existen y no bastaba con quitar una limitación.** Las
capacidades del cuadro de superficies (`plano.cuadro_de_superficies`,
`plano.escribir_cuadro`) trabajan sobre **el cuadro que el plano ya trae
dibujado**: sus filas son las que puso el arquitecto en su `ACAD_TABLE` y su
trabajo es rellenarlas en el propio DXF. Eso exige dos cosas que el caso normal
no cumple: que haya una sola vivienda —para saber a qué vivienda pertenece la
tabla— y que la tabla exista. El segundo plano real del cliente tiene **tres
viviendas y cero `ACAD_TABLE`**, así que por ese camino no había nada que
entregar, y ninguna de las dos condiciones es un defecto del plano.

Estas dos capacidades resuelven el otro caso, que es el frecuente: **medir lo
que hay dibujado**. No necesitan tabla, no se niegan por el número de viviendas,
y no escriben en el DXF del arquitecto — el entregable es un documento aparte.
Las del cuadro siguen siendo las buenas cuando el plano trae su tabla: rellenar
la tabla del arquitecto vale más que darle una lista.

**La separación de siempre.** La primera **no escribe nada**, así que el
arquitecto puede ver la medición entera antes de que se cree un solo fichero;
la segunda es la única con efecto y lleva el mismo patrón de protección que el
resto: destino comprobado antes de abrir nada, sha256 del original verificado
antes y después, y `_destino_seguro` / `_con_sello_intacto` **importados** de
`plano.py` en vez de reimplementados. Reimplementar «algo parecido» a un
guardián es la forma más habitual de perder la garantía que protege.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..capacidad import Capacidad
from .plano import (
    _con_sello_intacto,
    _destino_seguro,
    _fallo_de_lectura,
    _falta_el_fichero,
    _sha256,
)


def _leer(ruta: str, capa: Optional[str], factor_escala: Optional[float]):
    """Abre el DXF y lo lleva a metros. Devuelve `(plano, None)` o `(None, fallo)`."""
    import ezdxf

    from analyzer import parser

    try:
        doc = ezdxf.readfile(ruta)
        return parser.leer_plano(doc, layer=capa, factor_escala=factor_escala), None
    except Exception as exc:                      # noqa: BLE001 - se traduce, no se traga
        return None, _fallo_de_lectura(exc)


def _medir(ruta: str, capa: Optional[str],
           factor_escala: Optional[float]) -> Dict[str, Any]:
    """El tramo común de las dos capacidades: leer, medir y serializar."""
    from analyzer.medicion import a_dict, medir_planta

    plano, fallo = _leer(ruta, capa, factor_escala)
    if fallo is not None:
        return fallo
    salida = a_dict(medir_planta(plano))
    salida["ok"] = True
    salida["ruta"] = os.path.abspath(ruta)
    salida["capa_de_recintos"] = plano.layer
    salida["escala"] = getattr(plano.escala, "unidad", "")
    return salida


# ---------------------------------------------------------------------------
# 1. Medir. No escribe nada.
# ---------------------------------------------------------------------------

def medicion_de_la_planta(ruta: str, capa: Optional[str] = None,
                          factor_escala: Optional[float] = None) -> Dict[str, Any]:
    """Superficie útil de cada vivienda de la planta, pieza a pieza."""
    fallo = _falta_el_fichero(ruta)
    if fallo:
        return fallo
    return _medir(ruta, capa, factor_escala)


# ---------------------------------------------------------------------------
# 2. El documento. Es la única con efecto.
# ---------------------------------------------------------------------------

def medicion_en_pdf(ruta: str, ruta_destino: str, capa: Optional[str] = None,
                    factor_escala: Optional[float] = None) -> Dict[str, Any]:
    """Escribe la medición en un PDF. El DXF de entrada sólo se lee."""
    fallo = _falta_el_fichero(ruta)
    if fallo:
        return fallo
    fallo = _destino_seguro(ruta, ruta_destino)
    if fallo:
        return fallo

    sello_antes = _sha256(ruta)
    medicion = _medir(ruta, capa, factor_escala)
    if not medicion.get("ok"):
        return _con_sello_intacto(ruta, sello_antes, medicion)

    from analyzer.medicion_pdf import escribir_medicion_pdf

    datos = dict(medicion)
    datos["plano"] = os.path.basename(ruta)
    datos["sello_origen_sha256"] = sello_antes
    # Lo que NO se comprueba sale de los manifiestos de las capacidades que se
    # han ejecutado, no de una lista escrita a mano ni de un argumento: si
    # mañana alguien añade una limitación a una de ellas, entra sola en el
    # documento, y nadie de fuera puede recortarla.
    datos["no_comprobado"] = _limitaciones_declaradas()
    try:
        escribir_medicion_pdf(datos, ruta_destino)
    except Exception as exc:                      # noqa: BLE001
        return _con_sello_intacto(ruta, sello_antes, {
            "ok": False,
            "error": "pdf_no_escrito",
            "detalle": "No se ha podido escribir el PDF en «%s»: %s" % (ruta_destino, exc),
            "pregunta": "¿La carpeta de destino existe y se puede escribir en ella?",
        })

    salida = dict(medicion)
    salida["ruta_destino"] = os.path.abspath(ruta_destino)
    salida["sello_destino_sha256"] = _sha256(ruta_destino)
    return _con_sello_intacto(ruta, sello_antes, salida)


# ---------------------------------------------------------------------------
# Los manifiestos
# ---------------------------------------------------------------------------

#: Lo que ninguna de las dos comprueba, y por tanto llega al acta por sí solo.
_LIMITACIONES_COMUNES = (
    "es superficie útil, no construida: no incluye espesores de muro",
    "no comprueba normativa ni ningún mínimo de superficie: mide, no dictamina",
    "el reparto de recintos entre viviendas sale de los rótulos «VT…» del plano; si el "
    "plano no los trae, se agrupa por proximidad geométrica y eso es una suposición de "
    "ArchMuse, no una declaración del arquitecto",
    "el ámbito interior o exterior de una pieza sale de su rótulo; una pieza rotulada de "
    "forma desconocida no se asigna a ninguno de los dos y bloquea el total de su vivienda",
    "una vivienda con piezas solapadas, con reparto dudoso o con piezas sin clasificar "
    "NO lleva total: las piezas se miden igual y el motivo va escrito",
    "no rellena el cuadro de superficies del DXF: para eso está "
    "superficies.cuadro_de_vivienda, que sí escribe en el plano",
)


def _limitaciones_declaradas() -> list:
    """Las limitaciones de estas dos capacidades, sin repetir y en orden estable.

    Se leen del módulo y no del registro para no importar el registro desde una
    herramienta: sería una dependencia circular. Es el mismo patrón que
    `plano._limitaciones_de`.
    """
    fuera: list = []
    for capacidad in CAPACIDADES:
        for limitacion in capacidad.limitaciones:
            if limitacion not in fuera:
                fuera.append(limitacion)
    return fuera


CAPACIDADES = (
    Capacidad(
        id="plano.medicion_de_la_planta",
        version="1.0.0",
        dominio="plano",
        naturaleza="determinista",
        descripcion=(
            "Mide la superficie útil de TODAS las viviendas de una planta, pieza a "
            "pieza, sin necesidad de que el plano traiga ningún cuadro de superficies "
            "dibujado. Devuelve cada recinto con su rótulo, su superficie, su capa y si "
            "cuenta como superficie interior o exterior; los subtotales por ámbito; y el "
            "total de cada vivienda SOLO cuando se puede afirmar. Una vivienda con "
            "piezas solapadas, con reparto dudoso entre viviendas o con piezas de rótulo "
            "desconocido vuelve SIN total y con el motivo y su magnitud. No escribe nada."
        ),
        parametros={
            "type": "object",
            "properties": {
                "ruta": {"type": "string", "description": "Ruta del fichero .dxf."},
                "capa": {"type": ["string", "null"],
                         "description": "Capa de recintos, si ya está confirmada."},
                "factor_escala": {"type": ["number", "null"],
                                  "description": ("Multiplicador a metros, si ya está "
                                                  "confirmado.")},
            },
            "required": ["ruta"],
            "additionalProperties": False,
        },
        funcion=medicion_de_la_planta,
        efectos=(),
        limitaciones=_LIMITACIONES_COMUNES,
    ),
    # `medicion_en_pdf` (la función, justo arriba) sigue aquí y se sigue
    # llamando igual. Lo que ya no está es su entrada de registro propia:
    # desde el cierre de C4 (Prompt 1.7, 2026-08-21) se invoca a través de
    # `plano.entregable_en_pdf` con `tipo="medicion"` —
    # docs/design/2026-08-21-fusion-capacidades-pdf-C4.md. Fusión de
    # manifiesto, no de código: esta función no se ha tocado.
)
