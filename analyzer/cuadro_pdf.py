# -*- coding: utf-8 -*-
"""El cuadro de superficies en PDF, con el porqué de cada hueco (tarea `DOC-2`).

**Qué añade sobre el DXF entregado,** que ya es el entregable principal. El DXF
lleva los números; este PDF lleva **de dónde sale cada uno y qué falta**. Son
dos documentos con dos usos distintos: el DXF vuelve al proyecto, y el PDF es
lo que el arquitecto lee para decidir si se fía —y lo que puede enseñar si
alguien le pregunta seis meses después.

**Desde el 2026-09-13 presenta la plantilla fija** (PRD
`docs/prd/2026-09-13-cuadro-plantilla-fija.md`): la misma rejilla que dibujan
el comando de AutoCAD, la web y el DXF entregado, y debajo el motivo de cada
hueco vacío. Hasta ese día presentaba las 18 celdas del cuadro del arquitecto
con una columna de estado; esa columna se fue con ellas.

Una celda vacía sin motivo es indistinguible de un descuido; con motivo, es una
decisión que se puede discutir. Es `C2` —el trabajo hecho con el porqué a un
clic— en el formato más portátil que hay.

**Tres reglas de este módulo:**

1. **No calcula nada.** Recibe la tabla ya resuelta y la presenta. Si
   calculara, habría dos sitios donde se decide qué dice una celda, y el día
   que se separen nadie sabría cuál manda.
2. **No inventa ni transforma una cifra.** El texto de cada celda se imprime tal
   cual lo produjo el cálculo, y un hueco vacío sigue vacío.
3. **Sale marcado como borrador**, en todas las páginas, sin forma de
   desactivarlo (`DOC-3`).
"""
from __future__ import annotations

import io
from datetime import date
from typing import Any, Dict, List, Optional, Sequence
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from .marca_borrador import estampar

#: Anchos de las cuatro columnas de la plantilla, en el ancho útil de un A4 con
#: los márgenes de abajo (17,8 cm): los rótulos piden más que las cifras.
ANCHOS_CM = (5.2, 3.7, 5.2, 3.7)


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


def _p(texto: Any, estilo) -> Paragraph:
    return Paragraph("" if texto is None else str(texto), estilo)


def _texto(texto: Any) -> str:
    """El texto de una celda, a salvo del marcado de `Paragraph`: un rótulo con
    «&» o «<» no puede romper el documento ni cambiar lo que dice."""
    return escape("" if texto is None else str(texto))


def _tabla_de_la_plantilla(datos: Dict[str, Any], celdas: Sequence[dict], estilos) -> Table:
    n_columnas = int(datos.get("n_columnas") or 1 + max(int(c["columna"]) for c in celdas))
    n_filas = int(datos.get("n_filas") or 1 + max(int(c["fila"]) for c in celdas))
    rejilla: List[List[str]] = [["" for _ in range(n_columnas)] for _ in range(n_filas)]
    for celda in celdas:
        rejilla[int(celda["fila"])][int(celda["columna"])] = _texto(celda.get("texto"))

    filas: List[List[Any]] = []
    for i, fila in enumerate(rejilla):
        # Título (fila 0) y encabezados (fila 1) en negrita, como en el plano.
        plantilla = "<b>%s</b>" if i < 2 else "%s"
        filas.append([_p(plantilla % t if t else "", estilos["celda"]) for t in fila])

    anchos = ([a * cm for a in ANCHOS_CM] if n_columnas == len(ANCHOS_CM)
              else [sum(ANCHOS_CM) / n_columnas * cm] * n_columnas)
    tabla = Table(filas, colWidths=anchos, repeatRows=2)
    tabla.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BBBBBB")),
        ("SPAN", (0, 0), (-1, 0)),                       # el título, a lo ancho
        ("BACKGROUND", (0, 0), (-1, 1), colors.HexColor("#EEEEEE")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
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
    sin_resolver = list(datos.get("celdas_sin_resolver") or ())
    preguntas = list(datos.get("preguntas_pendientes") or ())
    declaradas = list(datos.get("celdas_declaradas_por_el_arquitecto") or ())

    story: List[Any] = [
        _p("Cuadro de superficies", estilos["h1"]),
        _p("Plano: %s" % _texto(datos.get("plano") or "—"), estilos["meta"]),
    ]
    if datos.get("vivienda"):
        story.append(_p("Vivienda: %s" % _texto(datos["vivienda"]), estilos["meta"]))
    story.append(_p("Emitido el %s por ArchMuse." % date.today().isoformat(), estilos["meta"]))
    if datos.get("sello_origen_sha256"):
        story.append(_p(
            "El plano original no se ha modificado. Su huella SHA-256 antes y después "
            "de este trabajo es <font face='Courier'>%s</font>."
            % _texto(datos["sello_origen_sha256"]), estilos["meta"]))
    story.append(Spacer(1, 0.5 * cm))

    if celdas:
        story.append(_tabla_de_la_plantilla(datos, celdas, estilos))
    else:
        story.append(_p("No se ha podido calcular ninguna celda de este plano.",
                        estilos["cuerpo"]))

    if declaradas:
        # La distinción que no se puede perder: lo que declaró el arquitecto no
        # es lo que calculó ArchMuse, y en un acta esas dos cosas no valen lo mismo.
        story.append(Spacer(1, 0.3 * cm))
        story.append(_p(
            "Declarado por el arquitecto, no calculado por ArchMuse: si es interior o "
            "exterior %s." % _texto(", ".join(declaradas)), estilos["cuerpo"]))

    if sin_resolver:
        story.append(_p("Lo que no se ha podido calcular", estilos["h2"]))
        story.append(_p(
            "Estos huecos han quedado en blanco a propósito. ArchMuse no escribe una "
            "cifra que no pueda justificar.", estilos["cuerpo"]))
        story.append(Spacer(1, 0.2 * cm))
        for hueco in sin_resolver:
            story.append(_p("• <b>%s</b>: %s" % (
                _texto(hueco.get("etiqueta") or "—"),
                _texto(hueco.get("motivo") or "sin motivo declarado")), estilos["celda"]))

    if preguntas:
        story.append(_p("Qué haría falta para completarlo", estilos["h2"]))
        for pregunta in preguntas:
            story.append(_p("• <b>%s</b> %s" % (_texto(pregunta.get("titulo", "")),
                                                _texto(pregunta.get("ayuda", ""))),
                            estilos["celda"]))

    limitaciones = list(datos.get("no_comprobado") or ())
    if limitaciones:
        story.append(_p("Lo que este documento NO comprueba", estilos["h2"]))
        story.append(_p(
            "Derivado de lo que se ha ejecutado, no redactado a mano.", estilos["meta"]))
        story.append(Spacer(1, 0.2 * cm))
        for limitacion in limitaciones:
            story.append(_p("• %s" % _texto(limitacion), estilos["celda"]))

    # C3: la marca va en todas las páginas y no hay forma de quitarla.
    doc.build(story, onFirstPage=estampar(), onLaterPages=estampar())
    return buffer.getvalue()


def escribir_cuadro_pdf(datos: Dict[str, Any], ruta_destino: str) -> Optional[str]:
    """Escribe el PDF. Devuelve la ruta, o `None` si no había nada que escribir."""
    contenido = generar_cuadro_pdf(datos)
    with open(ruta_destino, "wb") as fh:
        fh.write(contenido)
    return ruta_destino
