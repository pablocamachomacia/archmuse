# -*- coding: utf-8 -*-
"""El cuadro de superficies en PDF, con el porqué de cada celda (tarea `DOC-2`).

**Qué añade sobre el DXF relleno,** que ya es el entregable principal. El DXF
lleva los números; este PDF lleva **de dónde sale cada uno y qué falta**. Son
dos documentos con dos usos distintos: el DXF vuelve al proyecto, y el PDF es
lo que el arquitecto lee para decidir si se fía —y lo que puede enseñar si
alguien le pregunta seis meses después.

Por eso la columna que de verdad importa no es la del número: es la última.
Una celda vacía sin motivo es indistinguible de un descuido; con motivo, es una
decisión que se puede discutir. Es `C2` —el trabajo hecho con el porqué a un
clic— en el formato más portátil que hay.

**Tres reglas de este módulo:**

1. **No calcula nada.** Recibe las celdas ya resueltas y las presenta. Si
   calculara, habría dos sitios donde se decide qué dice una celda, y el día
   que se separen nadie sabría cuál manda.
2. **No convierte un `N/D` en un número, ni al revés.** El texto de cada celda
   se imprime tal cual lo produjo el cálculo.
3. **Sale marcado como borrador**, en todas las páginas, sin forma de
   desactivarlo (`DOC-3`).
"""
from __future__ import annotations

import io
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from .marca_borrador import estampar

#: Cómo se lee cada estado del catálogo cerrado de `cuadro_superficies.py`. En
#: castellano de arquitecto, no en el vocabulario del motor: quien lee este PDF
#: no sabe —ni tiene por qué— qué es un `CERO_REAL`.
ESTADOS = {
    "CALCULADO": ("Calculado", colors.HexColor("#1B5E20")),
    "CERO_REAL": ("No existe en la vivienda", colors.HexColor("#37474F")),
    "NO_DISPONIBLE": ("No se puede saber del plano", colors.HexColor("#8A2A2A")),
    "BLOQUEADO": ("Ambiguo: hay que decidirlo", colors.HexColor("#8A2A2A")),
}


def _estilos():
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("CuadroH1", parent=base["Heading1"], spaceAfter=2),
        "h2": ParagraphStyle("CuadroH2", parent=base["Heading2"], spaceBefore=14,
                             spaceAfter=6),
        "meta": ParagraphStyle("CuadroMeta", parent=base["Normal"], fontSize=8.5,
                               textColor=colors.HexColor("#555555")),
        "celda": ParagraphStyle("CuadroCelda", parent=base["Normal"], fontSize=8,
                                leading=10),
        "cuerpo": base["Normal"],
    }


def _valor(celda: Dict[str, Any]) -> str:
    """Lo que ese hueco lleva **en el DXF entregado**.

    Este PDF explica ese DXF, así que la columna del valor tiene que decir lo
    mismo que el plano: una celda bloqueada se escribe allí como «N/D», y poner
    aquí la palabra interna `BLOQUEADO` obligaba al arquitecto a cotejar dos
    vocabularios para la misma celda. El porqué no se pierde: va entero en las
    columnas de estado y de procedencia.
    """
    texto = (celda.get("texto") or "").strip()
    return "N/D" if texto == "BLOQUEADO" else texto


def _rotulo(celda: Dict[str, Any]) -> str:
    """El nombre de la fila, tal como lo escribió el arquitecto en su cuadro.

    Con repliegue al identificador interno **sólo** si el cuadro no traía esa
    celda. El identificador es ASCII a propósito —es una clave de programa— y
    derivar de él el título de una fila producía «Bano», «Salon cocina» y
    «Vestibulo» en el documento que el arquitecto le enseña a su cliente. Se vio
    en el primer plano real; con los fixtures no se veía porque sus etiquetas no
    llevan tildes.
    """
    etiqueta = (celda.get("etiqueta") or "").strip()
    if etiqueta:
        return etiqueta
    return (celda.get("campo", "") or "").replace("_", " ").capitalize()


def _p(texto: Any, estilo) -> Paragraph:
    return Paragraph("" if texto is None else str(texto), estilo)


def _tabla_de_celdas(celdas: Sequence[dict], estilos) -> Table:
    filas: List[List[Any]] = [[
        _p("<b>Concepto</b>", estilos["celda"]),
        _p("<b>Valor</b>", estilos["celda"]),
        _p("<b>Estado</b>", estilos["celda"]),
        _p("<b>De dónde sale, o por qué no</b>", estilos["celda"]),
    ]]
    estilo_tabla = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BBBBBB")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for i, celda in enumerate(celdas, start=1):
        etiqueta, color = ESTADOS.get(celda.get("estado", ""),
                                      (celda.get("estado", "—"), colors.black))
        if celda.get("declarado_por_usuario"):
            # La distinción que no se puede perder: lo que declaró el
            # arquitecto no es lo que calculó ArchMuse, y en un acta esas dos
            # cosas no valen lo mismo.
            porque = "Declarado por el arquitecto, no calculado por ArchMuse."
        elif celda.get("preexistente"):
            porque = "Ya estaba escrito en el DXF. No se ha tocado."
        else:
            porque = celda.get("motivo") or "Calculado sobre la geometría del plano."
        filas.append([
            _p(_rotulo(celda), estilos["celda"]),
            _p(_valor(celda), estilos["celda"]),
            _p(etiqueta, estilos["celda"]),
            _p(porque, estilos["celda"]),
        ])
        estilo_tabla.append(("TEXTCOLOR", (2, i), (2, i), color))
    tabla = Table(filas, colWidths=[4.4 * cm, 2.4 * cm, 3.4 * cm, 6.8 * cm], repeatRows=1)
    tabla.setStyle(TableStyle(estilo_tabla))
    return tabla


def generar_cuadro_pdf(datos: Dict[str, Any]) -> bytes:
    """El PDF del cuadro. Devuelve los bytes; no escribe a disco.

    `datos` es lo que produce `plano.cuadro_de_superficies`, más el nombre del
    plano y —si lo hay— el sello del original. No se calcula nada aquí.
    """
    estilos = _estilos()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm,
        topMargin=1.6 * cm, bottomMargin=1.9 * cm,
        title="Cuadro de superficies — ArchMuse",
    )

    celdas = list(datos.get("celdas") or ())
    sin_resolver = [c for c in celdas
                    if c.get("estado") in ("NO_DISPONIBLE", "BLOQUEADO")]
    preguntas = list(datos.get("preguntas_pendientes") or ())

    story: List[Any] = [
        _p("Cuadro de superficies", estilos["h1"]),
        _p("Plano: %s" % (datos.get("plano") or "—"), estilos["meta"]),
        _p("Emitido el %s por ArchMuse." % date.today().isoformat(), estilos["meta"]),
    ]
    if datos.get("sello_origen_sha256"):
        story.append(_p(
            "El plano original no se ha modificado. Su huella SHA-256 antes y después "
            "de este trabajo es <font face='Courier'>%s</font>."
            % datos["sello_origen_sha256"], estilos["meta"]))
    story.append(Spacer(1, 0.5 * cm))

    if celdas:
        story.append(_tabla_de_celdas(celdas, estilos))
    else:
        story.append(_p("No se ha podido calcular ninguna celda de este plano.",
                        estilos["cuerpo"]))

    if sin_resolver:
        story.append(_p("Lo que no se ha podido calcular", estilos["h2"]))
        story.append(_p(
            "Estas celdas han quedado en blanco a propósito. ArchMuse no escribe una "
            "cifra que no pueda justificar.", estilos["cuerpo"]))
        story.append(Spacer(1, 0.2 * cm))
        for celda in sin_resolver:
            story.append(_p("• <b>%s</b>: %s" % (
                _rotulo(celda),
                celda.get("motivo") or "sin motivo declarado"), estilos["celda"]))

    if preguntas:
        story.append(_p("Qué haría falta para completarlo", estilos["h2"]))
        for pregunta in preguntas:
            story.append(_p("• <b>%s</b> %s" % (pregunta.get("titulo", ""),
                                                pregunta.get("ayuda", "")),
                            estilos["celda"]))

    limitaciones = list(datos.get("no_comprobado") or ())
    if limitaciones:
        story.append(_p("Lo que este documento NO comprueba", estilos["h2"]))
        story.append(_p(
            "Derivado de lo que se ha ejecutado, no redactado a mano.", estilos["meta"]))
        story.append(Spacer(1, 0.2 * cm))
        for limitacion in limitaciones:
            story.append(_p("• %s" % limitacion, estilos["celda"]))

    # C3: la marca va en todas las páginas y no hay forma de quitarla.
    doc.build(story, onFirstPage=estampar(), onLaterPages=estampar())
    return buffer.getvalue()


def escribir_cuadro_pdf(datos: Dict[str, Any], ruta_destino: str) -> Optional[str]:
    """Escribe el PDF. Devuelve la ruta, o `None` si no había nada que escribir."""
    contenido = generar_cuadro_pdf(datos)
    with open(ruta_destino, "wb") as fh:
        fh.write(contenido)
    return ruta_destino
