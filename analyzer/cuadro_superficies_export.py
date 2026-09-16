# -*- coding: utf-8 -*-
"""La vía web del cuadro: una COPIA del DXF con la tabla de ArchMuse dibujada.

PRD `docs/prd/2026-09-13-cuadro-plantilla-fija.md`, §4.7 (decisión 7 de Pablo).

### Qué cambió el 2026-09-13, y por qué

Hasta ese día esta vía **escribía `MTEXT` encima de las celdas del cuadro del
arquitecto**: `21,90 m²`, `N/D`… y `0,00 m²` en las filas que el plano no dibuja.
Y **nunca pasó por `C-4`** (`D-15`): escribía ceros incluso con la medición sucia.

Ahora usa **la misma plantilla que el comando** (`plantilla_cuadro.construir`):
si el comando generara plantilla y la web clonara el cuadro ajeno, las dos vías
dejarían de leer igual y `C-9` saltaría. El cuadro del arquitecto sólo sirve para
**no dibujar encima** y para **la altura de texto** (`D-14`).

### Por qué la tabla se dibuja con líneas y textos y no como `ACAD_TABLE`

`ezdxf` no sabe crear un `ACAD_TABLE` (`DXFTypeError`, medido el 2026-09-13). Se
dibuja la rejilla con `LINE` y cada celda con un `MTEXT`, en su propia capa
(`CAPA_CUADRO`). **Visualmente es la misma tabla; no es una tabla editable de
AutoCAD**, y eso hay que saberlo antes de prometer otra cosa.

### Dónde, sin ventana

La web no tiene ratón con el que marcar una ventana. Se deduce —y por eso es una
deducción, no una declaración—: a la derecha del cuadro del arquitecto si lo
hay, a la derecha de lo dibujado si no, con el texto a la altura mínima legible.

Este módulo es el único de todo el trabajo del cuadro que escribe en disco, y
nunca sobre el fichero de origen.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import ezdxf

from . import maquetacion_cuadro as mq
from . import plantilla_cuadro as pc
from .cuadro_superficies import cajas_y_alturas_de_los_cuadros
from .marca_borrador import estampar_dxf

#: La capa de la tabla de ArchMuse. Suya y distinta de las del arquitecto: la
#: apaga o la borra sin tocar nada de lo que él dibujó. Una sola definición, en
#: la maquetación, para que la web y el comando dibujen en la misma capa y color.
CAPA_CUADRO = mq.CAPA

#: Separación entre el cuadro del arquitecto (o lo dibujado) y la tabla, en
#: alturas de texto.
SEPARACION = 4.0


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
    celdas_omitidas: List[str]
    reabierta_sin_errores: bool
    n_entidades_modelspace_origen: int
    n_entidades_modelspace_destino: int
    #: Lo que falta para que la tabla esté completa: hoy, las preguntas de
    #: interior/exterior sin contestar. Vacía = no hay nada que preguntar.
    campos_sin_resolver: List[str] = field(default_factory=list)
    detalles_sin_resolver: List[dict] = field(default_factory=list)


def ambitos_de_respuestas(respuestas) -> Dict[str, str]:
    """Las respuestas de interior/exterior, vengan como vengan del formulario:
    `{"TRASTERO": "interior"}` o `[{"tipo": "ambito", "familia": "TRASTERO",
    "ambito": "interior"}]`. Lo que no sea una respuesta de ámbito se ignora."""
    if isinstance(respuestas, Mapping):
        return {str(k): str(v) for k, v in respuestas.items()}
    ambitos: Dict[str, str] = {}
    for r in respuestas or ():
        if isinstance(r, Mapping) and r.get("tipo") == "ambito" and r.get("familia"):
            ambitos[str(r["familia"])] = str(r.get("ambito") or "")
    return ambitos


def _analizar_para_cuadro(ruta_origen: str):
    """`(doc, plano, nombre_de_la_vivienda)`. Una sola vivienda, como hasta hoy."""
    from . import parser

    from .medicion import motivo_c13

    doc = ezdxf.readfile(ruta_origen)
    plano = parser.leer_plano(doc)
    viviendas = pc.viviendas(plano)
    repetidas = sorted({n for n in viviendas if viviendas.count(n) > 1})
    if repetidas:
        # `C-13` antes que «tiene 2 viviendas»: si se llaman igual, el motivo no
        # es que haya dos, es que no se distinguen.
        raise ValueError("; ".join(motivo_c13(n, viviendas.count(n)) for n in repetidas) + ".")
    if len(viviendas) != 1:
        raise ValueError(
            "esta función de momento solo admite un DXF con una única vivienda "
            "detectada; %s tiene %d." % (ruta_origen, len(viviendas)))
    return doc, plano, viviendas[0]


def obtener_plantilla_cuadro(ruta_origen: str, respuestas=None):
    """`(plantilla, preguntas)` sin escribir nada: lo que la SPA pinta."""
    doc, plano, vivienda = _analizar_para_cuadro(ruta_origen)
    plantilla = pc.construir(doc, plano, vivienda, ambitos=ambitos_de_respuestas(respuestas))
    return plantilla, list(plantilla.preguntas)


def obtener_solicitudes(ruta_origen: str):
    """Las preguntas de interior/exterior pendientes. Lista vacía = nada que preguntar."""
    _plantilla, preguntas = obtener_plantilla_cuadro(ruta_origen)
    return preguntas


# `obtener_estado_cuadro` —las 18 celdas clásicas del cuadro del arquitecto—
# vivía aquí para la capacidad del agente. Se retiró el 2026-09-13, cuando Pablo
# decidió que el agente también dibuja la plantilla: tres vías que calculan el
# cuadro de dos formas son un `C-9` roto por el tercer sitio.


def _extension_del_dibujo(msp) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    from ezdxf import bbox

    caja = bbox.extents(msp, fast=True)
    if not caja.has_data:
        return None
    return (caja.extmin.x, caja.extmin.y), (caja.extmax.x, caja.extmax.y)


def _ventana_deducida(doc, plantilla, altura, cajas):
    ancho, alto = mq.tamano_necesario(plantilla.celdas(), pc.notas_del_dibujo(plantilla), altura)
    referencia = None
    if cajas:
        referencia = ((min(c[0][0] for c in cajas), min(c[0][1] for c in cajas)),
                      (max(c[1][0] for c in cajas), max(c[1][1] for c in cajas)))
    else:
        referencia = _extension_del_dibujo(doc.modelspace())
    if referencia is None:
        x0, y0 = 0.0, 0.0
    else:
        x0, y0 = referencia[1][0] + SEPARACION * altura, referencia[1][1]
    return (x0, y0), (x0 + ancho, y0 - alto)


def _dibujar(doc, plantilla, m) -> List[CeldaEscrita]:
    """La rejilla con `LINE` y cada texto con un `MTEXT`, en `CAPA_CUADRO`."""
    if CAPA_CUADRO not in doc.layers:
        doc.layers.add(CAPA_CUADRO, color=m.color_capa)
    if m.estilo not in doc.styles:
        doc.styles.add(m.estilo, font=m.fuente)
    msp = doc.modelspace()
    x0, y0 = m.esquina
    xs = [x0]
    for ancho in m.anchos:
        xs.append(xs[-1] + ancho)
    # La fila del título es más alta que las demás, como en los cuadros del arquitecto.
    alturas_de_fila = [m.alto_fila_titulo] + [m.alto_fila] * (m.n_filas - 1)
    ys = [y0]
    for alto in alturas_de_fila:
        ys.append(ys[-1] - alto)
    atributos = {"layer": CAPA_CUADRO}

    for y in ys:
        msp.add_line((xs[0], y), (xs[-1], y), dxfattribs=atributos)
    for i, x in enumerate(xs):
        # La fila 0 es el título, fusionado: las verticales interiores no la cruzan.
        arriba = ys[0] if i in (0, len(xs) - 1) else ys[1]
        msp.add_line((x, arriba), (x, ys[-1]), dxfattribs=atributos)

    escritas: List[CeldaEscrita] = []
    for fila, columna, texto in plantilla.celdas():
        x = xs[columna] + m.margen
        y = ys[fila] - alturas_de_fila[fila] / 2
        msp.add_mtext(texto, dxfattribs=dict(
            atributos, style=m.estilo,
            char_height=m.altura_titulo if fila == 0 else m.altura_texto,
            attachment_point=4, insert=(x, y, 0.0)))
        escritas.append(CeldaEscrita("%d,%d" % (fila, columna), texto, x, y))
    for x, y, linea in m.notas:
        msp.add_mtext(linea, dxfattribs=dict(
            atributos, style=m.estilo, char_height=m.altura_texto,
            attachment_point=1, insert=(x, y, 0.0)))
        escritas.append(CeldaEscrita("nota", linea, x, y))
    return escritas


def exportar_cuadro_relleno(ruta_origen: str, ruta_destino: str,
                            respuestas=None) -> ResultadoExportacion:
    """Lee `ruta_origen` y escribe en `ruta_destino` una copia con la tabla de
    ArchMuse dibujada al lado. `ruta_origen` nunca se escribe."""
    ruta_origen = os.path.abspath(ruta_origen)
    ruta_destino = os.path.abspath(ruta_destino)
    if ruta_destino == ruta_origen:
        raise ValueError("ruta_destino no puede ser igual a ruta_origen -- nunca se "
                         "sobrescribe el DXF original")

    doc, plano, vivienda = _analizar_para_cuadro(ruta_origen)
    n_entidades_origen = len(doc.modelspace())
    plantilla = pc.construir(doc, plano, vivienda, ambitos=ambitos_de_respuestas(respuestas))

    cajas, alturas_cuadro = cajas_y_alturas_de_los_cuadros(doc)
    altura = mq.altura_minima(
        min(alturas_cuadro) if alturas_cuadro else None,
        mq.alturas_de_rotulos(doc, [r.label for r in plano.rooms if r.label]))
    if altura is None:
        raise ValueError("No sé con qué altura de texto dibujar la tabla: el plano no "
                         "tiene ni cuadro de superficies ni rótulos de estancia.")
    ventana = _ventana_deducida(doc, plantilla, altura, cajas)
    # En el plano, las notas cortas (Pablo, 2026-09-15); el detalle, en el acta.
    maquetacion = mq.maquetar(plantilla.celdas(), pc.notas_del_dibujo(plantilla), ventana,
                              altura, cajas)
    if isinstance(maquetacion, mq.NoCabe):
        raise ValueError(maquetacion.motivo)

    escritas = _dibujar(doc, plantilla, maquetacion)

    # C3: todo entregable sale marcado como borrador, en su propia capa.
    # Donde la maqueta la ha reservado, debajo de las notas, como el comando (`C-9`).
    estampar_dxf(doc, punto=maquetacion.marca[:2])
    doc.saveas(ruta_destino)

    verificacion = ezdxf.readfile(ruta_destino)
    auditor = verificacion.audit()
    if auditor.has_errors:
        raise ValueError(
            "la copia %s se reabre pero el audit de ezdxf encuentra %d error(es): %s" % (
                ruta_destino, len(auditor.errors),
                "; ".join(e.message for e in auditor.errors[:5])))

    return ResultadoExportacion(
        ruta_origen=ruta_origen,
        ruta_destino=ruta_destino,
        celdas_escritas=escritas,
        celdas_omitidas=[],
        reabierta_sin_errores=True,
        n_entidades_modelspace_origen=n_entidades_origen,
        n_entidades_modelspace_destino=len(verificacion.modelspace()),
        campos_sin_resolver=[p.familia for p in plantilla.preguntas],
        # Lo que falta por preguntar y, además, cada hueco que la tabla deja vacío
        # con su motivo: es lo que el acta de `TL-2` tiene que poder enseñar.
        detalles_sin_resolver=(
            [{"campo": p.familia, "estado": "PREGUNTA", "motivo": p.texto}
             for p in plantilla.preguntas]
            + [{"campo": ", ".join(etiquetas), "estado": "SIN_CIFRA", "motivo": motivo}
               for etiquetas, motivo in plantilla.notas_por_motivo]),
    )
