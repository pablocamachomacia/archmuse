# -*- coding: utf-8 -*-
"""Fase 3 — escribe una COPIA del DXF con el cuadro de superficies relleno.

Diseño de referencia: informe de Fase 2 (`analyzer/cuadro_superficies.py`).
Este módulo es el único punto de todo el trabajo de "cuadro de superficies"
que escribe algo en disco -- ni `cuadro_superficies.py` (cálculo puro +
detección de solo lectura) ni `parser.py`/`evaluator.py` tocan un DXF de
salida.

### Por qué se escribe MTEXT nuevo en modelspace, no dentro del `ACAD_TABLE`

`ezdxf` no soporta editar el contenido interno de un `ACAD_TABLE` (es una
entidad compleja, en buena parte propietaria de Autodesk; `virtual_entities()`
solo la **lee**, no expone una forma de reescribir sus celdas). La solución
que usa este módulo -- y que hay que decir con toda claridad, no ocultarla --
es dibujar un `MTEXT` real en `modelspace()`, con las mismas coordenadas,
capa, altura, estilo y alineación que ya usa la celda vacía. Visualmente
queda idéntico a "la celda rellena" porque ocupa exactamente su hueco; no es
una edición interna de la tabla, es un texto superpuesto en el sitio exacto.
Cualquier consumidor futuro que necesite editar el `ACAD_TABLE` de verdad
(por ejemplo si algún día se reconstruye la tabla entera) debe saber que este
método no lo hace.

### Regla de escritura (fijada explícitamente para esta fase, distinta de
### `escribir` en `cuadro_superficies.CeldaRelleno`)

`CeldaRelleno.escribir` (Fase 2) decía "sáltate esta celda" para
`BLOQUEADO`/`NO_DISPONIBLE`. Para la Fase 3 el encargo cambia esa regla a
propósito: el cuadro debe quedar **entero** -- ninguna celda vacía sin
explicación --, así que:

- `CALCULADO` / `CERO_REAL` -> se escribe el valor (`21,90 m²`, `0,00 m²`).
- `BLOQUEADO` / `NO_DISPONIBLE` -> se escribe literalmente `N/D`. Nunca una
  cifra.
- Celda **preexistente** (ya tenía texto en el DXF, p. ej. `VIVIENDA TIPO`)
  -> no se toca en absoluto, bajo ningún estado. Es la única celda que se
  salta de verdad.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import ezdxf

from .marca_borrador import estampar_dxf
from .cuadro_superficies import (
    BLOQUEADO,
    CALCULADO,
    CERO_REAL,
    NO_DISPONIBLE,
    CeldaRelleno,
    aplicar_respuestas,
    calcular_relleno_cuadro,
    celdas_sin_resolver,
    detectar_cuadro_superficies,
)

CAPA_CUADRO = "00 CUADROS"
ESTILO_TEXTO = "Standard"
ALTURA_TEXTO = 0.09
PUNTO_INSERCION = 2  # attachment_point: top-center, mismo que ya usa el cuadro original
TEXTO_NO_DISPONIBLE = "N/D"


@dataclass(frozen=True)
class CeldaEscrita:
    campo: str
    texto: str
    x: float
    y: float


@dataclass(frozen=True)
class ResultadoExportacion:
    ruta_origen: str
    ruta_destino: str
    celdas_escritas: List[CeldaEscrita]
    celdas_omitidas: List[str]     # campos que no se tocaron (preexistentes) + sin celda destino
    reabierta_sin_errores: bool
    n_entidades_modelspace_origen: int
    n_entidades_modelspace_destino: int
    # Fase 5: campos que siguen BLOQUEADO/NO_DISPONIBLE en el resultado
    # final (tras aplicar `respuestas`, si las hubo). Vacía = el cuadro ha
    # quedado completo de verdad, no solo "sin celdas vacías" (con `N/D`
    # también queda "completo" en ese sentido más débil de la Fase 3/4).
    campos_sin_resolver: List[str] = field(default_factory=list)
    # Mismo conjunto que `campos_sin_resolver`, con el motivo de cada uno
    # (por qué sigue pendiente, o el texto exacto del conflicto si una
    # respuesta contradice una celda preexistente) -- para que el endpoint
    # HTTP pueda devolver algo útil al formulario sin adivinar nada nuevo.
    detalles_sin_resolver: List[dict] = field(default_factory=list)


def _texto_para_celda(r: CeldaRelleno) -> str:
    if r.estado in (CALCULADO, CERO_REAL):
        return r.texto
    if r.estado in (BLOQUEADO, NO_DISPONIBLE):
        return TEXTO_NO_DISPONIBLE
    raise AssertionError("estado no contemplado: %r" % r.estado)  # catálogo cerrado, ver cuadro_superficies.py


def _analizar_para_cuadro(ruta_origen: str):
    """Abre `ruta_origen` (solo lectura), analiza la vivienda y detecta el
    cuadro -- el mismo primer tramo que necesitan tanto `obtener_solicitudes`
    como `exportar_cuadro_relleno`, factorizado para no duplicarlo. Devuelve
    `(doc, unit, cuadro)`; lanza `ValueError` con el mismo mensaje que antes
    si no hay una única vivienda o no se encuentra el cuadro."""
    # Import perezoso: `parser`/`evaluator` no son dependencias de
    # `cuadro_superficies.py` (módulo puro), pero SÍ hacen falta aquí para
    # poder analizar la vivienda antes de calcular el relleno.
    from . import evaluator, parser

    doc = ezdxf.readfile(ruta_origen)
    plano = parser.leer_plano(doc)
    advanced = evaluator.evaluate_advanced(plano.rooms, plano.unit_labels)
    if len(advanced.units) != 1:
        raise ValueError(
            "esta función de momento solo admite un DXF con una única vivienda "
            "detectada (caso de v2s.dxf); %s tiene %d." % (ruta_origen, len(advanced.units))
        )
    unit = advanced.units[0]

    cuadro = detectar_cuadro_superficies(doc)
    if cuadro is None:
        raise ValueError("no se ha encontrado ningún ACAD_TABLE «CUADRO DE SUPERFICIES...» en %s" % ruta_origen)

    return doc, unit, cuadro


def obtener_estado_cuadro(ruta_origen: str, respuestas: Optional[Sequence[dict]] = None):
    """Fase 6 (visualización en pantalla, sin descargar ni escribir nada):
    calcula el borrador COMPLETO del cuadro de `ruta_origen` -- las 18
    `CeldaRelleno` tal como quedan hoy -- y las solicitudes pendientes sobre
    ESE resultado. Solo lectura. Devuelve
    `(resultado: List[CeldaRelleno], solicitudes: List[Solicitud])`.

    `respuestas` (Fase 6b, opcional): si se pasa, se aplica con
    `cuadro_superficies.aplicar_respuestas` ANTES de calcular las
    solicitudes -- así la tabla en pantalla puede reflejar lo que el
    arquitecto acaba de contestar (p. ej. qué pieza es cada espacio
    exterior) sin necesidad de generar ni descargar ningún DXF. Sin
    `respuestas` (o `None`), el comportamiento es EXACTAMENTE el de antes.

    Factoriza el primer tramo que ya usaba `obtener_solicitudes` (Fase 5b)
    para no analizar el DXF dos veces cuando hace falta lo mismo dos formas
    (la tabla en pantalla Y las preguntas del formulario vienen del MISMO
    cálculo, nunca de dos lecturas separadas del plano)."""
    from .cuadro_superficies import aplicar_respuestas, detectar_solicitudes

    _doc, unit, cuadro = _analizar_para_cuadro(ruta_origen)
    resultado = calcular_relleno_cuadro(unit, cuadro, unit.rooms)
    if respuestas:
        resultado = aplicar_respuestas(resultado, unit.rooms, respuestas)
    solicitudes = detectar_solicitudes(resultado, unit.rooms)
    return resultado, solicitudes


def obtener_solicitudes(ruta_origen: str):
    """Fase 5: qué hay que preguntarle al arquitecto para poder completar el
    cuadro de `ruta_origen` -- lista vacía si ya se puede descargar
    directamente. Solo lectura, no escribe nada. Devuelve
    `List[cuadro_superficies.Solicitud]`."""
    _resultado, solicitudes = obtener_estado_cuadro(ruta_origen)
    return solicitudes


def exportar_cuadro_relleno(
    ruta_origen: str, ruta_destino: str, respuestas: Optional[Sequence[dict]] = None,
) -> ResultadoExportacion:
    """Lee `ruta_origen` en memoria, calcula el borrador de relleno
    (`cuadro_superficies.calcular_relleno_cuadro`) y escribe una COPIA nueva
    en `ruta_destino` con las celdas de valor completadas. `ruta_origen`
    nunca se abre en modo escritura ni se le llama `.save()`/`.saveas()`.

    `respuestas` (Fase 5, opcional): si se pasa, se aplica con
    `cuadro_superficies.aplicar_respuestas` ANTES de escribir -- las celdas
    que las respuestas resuelven salen con su valor real (marcado
    `declarado_por_usuario`) en vez de `N/D`. Sin `respuestas` (o con
    `None`, el valor por defecto), el comportamiento es EXACTAMENTE el de
    la Fase 3/4: sin cambios.

    Vuelve a abrir `ruta_destino` con `ezdxf.readfile` antes de devolver el
    resultado, para confirmar que la copia no quedó corrupta -- si falla,
    la excepción de `ezdxf` se propaga tal cual, no se silencia.
    """
    ruta_origen = os.path.abspath(ruta_origen)
    ruta_destino = os.path.abspath(ruta_destino)
    if ruta_destino == ruta_origen:
        raise ValueError("ruta_destino no puede ser igual a ruta_origen -- nunca se sobrescribe el DXF original")

    doc, unit, cuadro = _analizar_para_cuadro(ruta_origen)
    n_entidades_origen = len(doc.modelspace())

    resultado = calcular_relleno_cuadro(unit, cuadro, unit.rooms)
    if respuestas:
        resultado = aplicar_respuestas(resultado, unit.rooms, respuestas)

    msp = doc.modelspace()
    celdas_escritas: List[CeldaEscrita] = []
    celdas_omitidas: List[str] = []

    for r in resultado:
        if r.preexistente:
            # "VIVIENDA TIPO" (o cualquier otra celda que ya trajera texto):
            # nunca se toca, coincida o no con lo calculado -- regla fija del
            # encargo, no una interpretación de este módulo.
            celdas_omitidas.append(r.campo)
            continue
        if r.celda is None:
            # El cuadro detectado no trae celda destino para este campo
            # (no debería pasar con el cuadro real de v2s.dxf, con sus 18
            # celdas, pero un cuadro más pequeño de otro DXF sí podría
            # carecer de alguna) -- no se inventa dónde escribir.
            celdas_omitidas.append(r.campo)
            continue

        texto = _texto_para_celda(r)
        msp.add_mtext(texto, dxfattribs={
            "layer": CAPA_CUADRO,
            "style": ESTILO_TEXTO,
            "char_height": ALTURA_TEXTO,
            "attachment_point": PUNTO_INSERCION,
            "insert": (r.celda.x, r.celda.y, 0.0),
        })
        celdas_escritas.append(CeldaEscrita(r.campo, texto, r.celda.x, r.celda.y))

    # C3 (tarea DOC-3): todo entregable sale marcado como borrador para la
    # revisión de un colegiado. Va en su propia capa, así que no cambia nada de
    # lo que el arquitecto dibujó ni de lo que este módulo escribe en
    # `00 CUADROS`. Se estampa aquí, en el único sitio que guarda un DXF, para
    # que no exista ningún camino que produzca una copia sin ella.
    estampar_dxf(doc)

    doc.saveas(ruta_destino)

    doc_verificacion = ezdxf.readfile(ruta_destino)
    n_entidades_destino = len(doc_verificacion.modelspace())
    # `Drawing.audit()` NO lanza por sí solo (corrige lo que puede y deja el
    # resto en `.errors`) -- se comprueba aquí explícitamente para que
    # "reabrir y verificar que no está corrupta" sea una garantía real, no
    # solo que `ezdxf.readfile` no reventara al parsear.
    auditor = doc_verificacion.audit()
    if auditor.has_errors:
        raise ValueError(
            "la copia %s se reabre pero el audit de ezdxf encuentra %d error(es): %s" % (
                ruta_destino, len(auditor.errors),
                "; ".join(e.message for e in auditor.errors[:5]),
            )
        )

    pendientes = celdas_sin_resolver(resultado)
    return ResultadoExportacion(
        ruta_origen=ruta_origen,
        ruta_destino=ruta_destino,
        celdas_escritas=celdas_escritas,
        celdas_omitidas=celdas_omitidas,
        reabierta_sin_errores=True,
        n_entidades_modelspace_origen=n_entidades_origen,
        n_entidades_modelspace_destino=n_entidades_destino,
        campos_sin_resolver=[r.campo for r in pendientes],
        detalles_sin_resolver=[
            {"campo": r.campo, "estado": r.estado, "motivo": r.motivo}
            for r in pendientes
        ],
    )
