"""Orquesta una fuente + el almacén. No conoce BOE ni ninguna fuente
concreta — recibe una `FuenteOficial` como parámetro, igual que
`normativa/resolucion.py` recibe una `CadenaAmbitos` ya resuelta sin saber
de dónde salió. Es lo que hace que añadir una fuente nueva no toque este
fichero.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional, Set

from . import almacen
from .errores import DocumentoIlegible, ErrorDeRed, ErrorIngesta
from .fuentes.base import FuenteOficial
from .modelo import EstadoDescarga, ItemSumario, ResultadoIngesta

# "I. Disposiciones generales" — donde viven leyes, reales decretos, decretos
# y órdenes. Las demás secciones del BOE (nombramientos, oposiciones,
# subvenciones, anuncios...) no son normativa y descargarlas por defecto
# sería justo el barrido masivo que esta fase no debe hacer. No es una
# clasificación por materia (eso es la Fase 3, y necesita leer el texto) —
# es un filtro mecánico y declarado sobre metadatos que el propio sumario
# ya trae, sin inventar ningún juicio sobre el contenido.
SECCION_DISPOSICIONES_GENERALES = "1"


def ingerir_fecha(
    fuente: FuenteOficial,
    fecha: date,
    solo_secciones: Optional[Set[str]] = frozenset({SECCION_DISPOSICIONES_GENERALES}),
    raiz_almacen: Optional[Path] = None,
) -> ResultadoIngesta:
    """Lista el sumario de `fecha`, descarga lo que pase el filtro de
    sección y registra cada descarga en el almacén.

    `solo_secciones=None` descarga TODO lo publicado ese día — úsese con
    conocimiento de causa, no es el valor por defecto precisamente para que
    un uso descuidado no dispare un barrido de cientos de documentos
    irrelevantes.
    """
    items = fuente.listar_sumario(fecha)
    if solo_secciones is not None:
        filtrados = [i for i in items if i.seccion_codigo in solo_secciones]
    else:
        filtrados = list(items)

    descargas = []
    avisos = []
    for item in filtrados:
        try:
            documento = fuente.descargar_documento(item)
        except (ErrorDeRed, DocumentoIlegible) as exc:
            avisos.append(f"{item.identificador}: no se pudo descargar — {exc}")
            continue
        descargas.append(almacen.registrar(documento, raiz_almacen))

    return ResultadoIngesta(
        items_vistos=tuple(items),
        items_filtrados=len(items) - len(filtrados),
        descargas=tuple(descargas),
        avisos=tuple(avisos),
    )


def ingerir_rango(
    fuente: FuenteOficial,
    desde: date,
    hasta: date,
    solo_secciones: Optional[Set[str]] = frozenset({SECCION_DISPOSICIONES_GENERALES}),
    raiz_almacen: Optional[Path] = None,
) -> ResultadoIngesta:
    """Varios días seguidos. Deliberadamente NO pensado para un histórico
    completo desde 1978: es para "los últimos N días desde la última
    ejecución", el uso real de un vigilante de fuentes. Un barrido histórico
    de toda España es explícitamente lo que esta fase no debe hacer."""
    if hasta < desde:
        raise ValueError(f"ingerir_rango: hasta ({hasta}) es anterior a desde ({desde})")

    items_totales: list[ItemSumario] = []
    descargas: list[EstadoDescarga] = []
    avisos: list[str] = []
    filtrados = 0
    dia = desde
    while dia <= hasta:
        resultado = ingerir_fecha(fuente, dia, solo_secciones, raiz_almacen)
        items_totales.extend(resultado.items_vistos)
        filtrados += resultado.items_filtrados
        descargas.extend(resultado.descargas)
        avisos.extend(resultado.avisos)
        dia = date.fromordinal(dia.toordinal() + 1)

    return ResultadoIngesta(
        items_vistos=tuple(items_totales),
        items_filtrados=filtrados,
        descargas=tuple(descargas),
        avisos=tuple(avisos),
    )


def ingerir_documento(
    fuente: FuenteOficial,
    identificador: str,
    raiz_almacen: Optional[Path] = None,
) -> EstadoDescarga:
    """Un documento concreto ya conocido por su identificador, sin escanear
    ningún sumario. Requiere que `fuente` sepa resolver un id directamente
    (`descargar_por_id`, hoy solo en `FuenteBOE`) — no forma parte del
    contrato mínimo `FuenteOficial` porque depende de cómo cada fuente
    nombra sus recursos."""
    resolver_por_id = getattr(fuente, "descargar_por_id", None)
    if resolver_por_id is None:
        raise ErrorIngesta(
            f"la fuente «{fuente.id}» no admite descarga directa por identificador"
        )
    documento = resolver_por_id(identificador)
    return almacen.registrar(documento, raiz_almacen)
