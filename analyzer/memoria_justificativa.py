# -*- coding: utf-8 -*-
"""Memoria justificativa automática — apartado de superficies (MJ-2).

PRD: `docs/prd/2026-08-19-memoria-justificativa-automatica.md`. Paso 2 del
roadmap (`docs/design/2026-08-19-roadmap-bim-carpinteria-detalles-memoria.md`).

Construye un PDF a partir de un `Acta` ya levantada (`agente/acta.py`) — el
mismo patrón de `reportlab` que `analyzer/pdf_report.py`, pero con una fuente
distinta y una regla distinta: **nunca recalcula nada** (cada cifra que
aparece ya estaba en `acta["datos"]`/`acta["no_comprobado"]`) y **nunca
menciona normativa ni cumplimiento** — a diferencia de `pdf_report.py`, que
sale de `evaluator.py` y ya carga con el problema documentado de umbrales sin
corpus citado (`docs/AGENTE_BACKLOG.md` §13.7). Este documento no tiene ese
problema porque no tiene ninguna afirmación normativa que pueda tenerlo.

Título y subtítulo dicen "apartado de superficies" y "borrador de apoyo" a
propósito, nunca "memoria justificativa" a secas en la portada (R-1 del PRD:
ese nombre solo, sin matizar, invita a leerlo como la memoria legal completa
que no es).
"""
from __future__ import annotations

import io
from typing import Any, Dict, List
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .marca_borrador import estampar


class ActaSinDatos(ValueError):
    """El acta no tiene ningún dato que documentar (p. ej. una pregunta que
    no llegó a ejecutar ninguna Skill) -- no hay memoria que generar, y
    generar un documento vacío sería peor que negarse (criterio de
    aceptación nº5 del PRD)."""


def _m2(valor: Any) -> str:
    """Magnitud en m² con coma decimal, mismo criterio que
    `analyzer/medicion.py::_formatear_area` y `analyzer/acta_legible.py::_m2_texto`
    -- nunca se inventa un cero cuando el valor es `None`."""
    if valor is None:
        return "—"
    try:
        return ("%.2f m²" % float(valor)).replace(".", ",")
    except (TypeError, ValueError):
        return xml_escape(str(valor))


def _tabla(filas: List[List[str]], anchos: List[float]) -> Table:
    tabla = Table(filas, colWidths=[a * cm for a in anchos], repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tabla


def _seccion_vivienda(v: Dict[str, Any], h3, body, story: List[Any]) -> None:
    """Una vivienda de `medicion.viviendas` -> su tabla de piezas + total.

    Cada campo leído aquí (`piezas`, `interior_m2`, `exterior_m2`,
    `total_util_m2`, `impedimentos`, `solapes`) ya existe tal cual en
    `analyzer/medicion.py::a_dict()` -- no se deriva nada nuevo."""
    nombre = str(v.get("vivienda") or "?")
    story.append(Paragraph(xml_escape(nombre), h3))

    filas = [["Pieza", "Ámbito", "Superficie"]]
    for p in v.get("piezas") or []:
        filas.append([
            xml_escape(str(p.get("rotulo") or "(sin rótulo)")),
            xml_escape(str(p.get("ambito") or "—")),
            _m2(p.get("area_m2")),
        ])
    story.append(_tabla(filas, [8.0, 4.0, 4.0]))
    story.append(Spacer(1, 0.2 * cm))

    resumen = [
        ["Superficie interior", _m2(v.get("interior_m2"))],
        ["Superficie exterior", _m2(v.get("exterior_m2"))],
    ]
    total = v.get("total_util_m2")
    if total is not None:
        resumen.append(["Superficie útil total", _m2(total)])
    story.append(_tabla(resumen, [8.0, 8.0]))

    if total is None:
        impedimentos = v.get("impedimentos") or []
        story.append(Paragraph(
            "Sin superficie útil total" +
            (" — %s" % xml_escape("; ".join(str(i) for i in impedimentos)) if impedimentos else "") +
            ". Las piezas están medidas; el total es una decisión pendiente, no un cálculo que falte.",
            body,
        ))

    solapes = v.get("solapes") or []
    if solapes:
        story.append(Paragraph(
            "Solapes detectados en esta vivienda (superficie contada dos veces, "
            "no incluida en el total anterior):", body,
        ))
        for s in solapes:
            story.append(Paragraph(
                "• %s / %s: %s" % (
                    xml_escape(str(s.get("una", "?"))), xml_escape(str(s.get("otra", "?"))),
                    _m2(s.get("area_m2")),
                ),
                body,
            ))

    story.append(Spacer(1, 0.5 * cm))


def generar_memoria_pdf(acta: Dict[str, Any]) -> bytes:
    """`Acta.a_dict()` -> PDF del apartado de superficies. Devuelve los bytes
    del PDF, no escribe a disco (mismo contrato que `pdf_report.generate_pdf`).

    Levanta `ActaSinDatos` si `acta["datos"]` está vacío -- nunca genera un
    documento sin nada que documentar."""
    datos = acta.get("datos") or []
    if not datos:
        raise ActaSinDatos(
            "Esta ejecución no produjo ningún dato que documentar -- no hay "
            "memoria que generar."
        )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2.5 * cm,
        title="Apartado de superficies — ArchMuse",
    )
    styles = getSampleStyleSheet()
    h2 = ParagraphStyle("MemH2", parent=styles["Heading2"], spaceBefore=14, spaceAfter=6)
    h3 = ParagraphStyle("MemH3", parent=styles["Heading3"], spaceBefore=10, spaceAfter=4)
    meta_style = ParagraphStyle("MemMeta", parent=styles["Normal"], textColor=colors.HexColor("#555555"))
    sello_style = ParagraphStyle("MemSello", parent=styles["Normal"], fontSize=7,
                                 textColor=colors.HexColor("#888888"))
    body = styles["Normal"]

    story: List[Any] = []

    # --- Portada ------------------------------------------------------------
    story.append(Paragraph(
        "APARTADO DE SUPERFICIES",
        ParagraphStyle("MemTitle", parent=styles["Title"], fontSize=18,
                       alignment=TA_CENTER, spaceAfter=4),
    ))
    story.append(Paragraph(
        "Borrador de apoyo generado a partir de una medición real — no sustituye "
        "el criterio ni la firma del arquitecto colegiado.",
        ParagraphStyle("MemSub", parent=styles["Normal"], alignment=TA_CENTER,
                       textColor=colors.HexColor("#555555"), spaceAfter=16),
    ))
    story.append(Paragraph(xml_escape(str(acta.get("objetivo") or "")), styles["Heading1"]))
    story.append(Paragraph(
        "Proyecto %s &nbsp;&nbsp;·&nbsp;&nbsp; Ejecución %s &nbsp;&nbsp;·&nbsp;&nbsp; %s"
        % (xml_escape(str(acta.get("proyecto_id") or "—")),
           xml_escape(str(acta.get("ejecucion_id") or "—")),
           xml_escape(str(acta.get("emitida_en") or "—"))),
        meta_style,
    ))
    story.append(Spacer(1, 0.6 * cm))

    # --- Superficies medidas --------------------------------------------------
    story.append(Paragraph("Superficies medidas", h2))
    por_nombre = {d.get("nombre"): d for d in datos}
    viviendas_dato = por_nombre.get("medicion.viviendas")
    viviendas = viviendas_dato.get("valor") if viviendas_dato else None

    if viviendas:
        for v in viviendas:
            _seccion_vivienda(v, h3, body, story)
    else:
        # Genérico, para cualquier otra Skill futura que no mida viviendas:
        # se lista cada afirmación con valor tal cual, sin inventar una
        # estructura de vivienda/pieza que esa Skill no declaró.
        hubo_alguna = False
        for d in datos:
            if d.get("valor") is None:
                continue
            hubo_alguna = True
            story.append(Paragraph(
                "%s: <b>%s</b> %s" % (
                    xml_escape(str(d.get("nombre") or "")),
                    xml_escape(str(d.get("valor"))),
                    xml_escape(str(d.get("unidad") or "")),
                ),
                body,
            ))
        if not hubo_alguna:
            story.append(Paragraph("(sin superficies medidas en esta ejecución)", body))

    # --- Qué no se ha comprobado ----------------------------------------------
    story.append(Paragraph("Qué no se ha comprobado", h2))
    no_comprobado = acta.get("no_comprobado") or []
    if not no_comprobado:
        story.append(Paragraph("(nada que declarar)", body))
    else:
        for n in no_comprobado:
            story.append(Paragraph("• " + xml_escape(str(n)), body))

    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph("Sello: %s" % xml_escape(str(acta.get("sello") or "(sin sellar)")), sello_style))

    # La leyenda de borrador se estampa en TODAS las páginas, sin excepción y
    # sin forma de desactivarla -- mismo mecanismo que ya usa `pdf_report.py`
    # (`analyzer/marca_borrador.py`), no una copia del texto.
    doc.build(story, onFirstPage=estampar(), onLaterPages=estampar())
    return buffer.getvalue()
