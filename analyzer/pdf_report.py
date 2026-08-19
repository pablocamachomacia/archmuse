"""Informe PDF descargable del análisis de calidad arquitectónica.

Construye un PDF a partir del mismo JSON que devuelven `/api/analizar` y
`/api/generar` (ver `analyzer/api_serializer.serialize_analysis`) — no
recalcula nada, solo formatea los datos ya calculados.
"""
from __future__ import annotations

import io
from datetime import datetime
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .marca_borrador import estampar

from .evaluator import SCORE_GREEN_THRESHOLD, SCORE_YELLOW_THRESHOLD

_SEVERITY_ORDER = ["CRITICO", "IMPORTANTE", "RECOMENDACION"]
_SEVERITY_LABEL = {"CRITICO": "Crítico", "IMPORTANTE": "Importante", "RECOMENDACION": "Recomendación"}
_SEVERITY_COLOR = {
    "CRITICO": colors.HexColor("#c0392b"),
    "IMPORTANTE": colors.HexColor("#e67e22"),
    "RECOMENDACION": colors.HexColor("#2980b9"),
}

# Umbrales de color de la puntuación global. Se importan de `evaluator` en vez
# de escribirse aquí: este informe tenía los suyos propios (80/60) frente a los
# 85/70 de la aplicación, así que un proyecto de 82 salía verde en pantalla y
# naranja en el PDF que descargaba esa misma pantalla. No hay ninguna lectura
# de eso que no sea "el programa se contradice".
SCORE_GOOD_MIN = SCORE_GREEN_THRESHOLD
SCORE_ACCEPTABLE_MIN = SCORE_YELLOW_THRESHOLD


def _score_color(score: float) -> colors.Color:
    if score >= SCORE_GOOD_MIN:
        return colors.HexColor("#27ae60")
    if score >= SCORE_ACCEPTABLE_MIN:
        return colors.HexColor("#e67e22")
    return colors.HexColor("#c0392b")


def _truncate(text: str, max_len: int = 80) -> str:
    text = text or ""
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "…"


def generate_pdf(data: dict) -> bytes:
    """Genera el informe PDF completo a partir del JSON de
    `/api/analizar`/`/api/generar`. Devuelve los bytes del PDF (no escribe
    a disco)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Informe Archmuse",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("ArchmuseH1", parent=styles["Heading1"], spaceAfter=4)
    h2 = ParagraphStyle("ArchmuseH2", parent=styles["Heading2"], spaceBefore=14, spaceAfter=6)
    meta_style = ParagraphStyle("ArchmuseMeta", parent=styles["Normal"], textColor=colors.HexColor("#555555"))
    body = styles["Normal"]

    story = []

    # =========================================================================
    # Página 1: resumen ejecutivo
    # =========================================================================
    proyecto_cover = data.get("proyecto") or {}
    edificio_cover = data.get("edificio") or {}
    score_cover = data.get("puntuacion_global", 0)
    valoracion_cover = data.get("valoracion_global", "")

    cover_title_style = ParagraphStyle(
        "ArchmuseCoverTitle", parent=styles["Title"], fontSize=20, alignment=TA_CENTER, spaceAfter=6
    )
    cover_subtitle_style = ParagraphStyle(
        "ArchmuseCoverSubtitle", parent=styles["Normal"], alignment=TA_CENTER,
        textColor=colors.HexColor("#555555"), spaceAfter=18,
    )
    story.append(Paragraph("INFORME DE ANÁLISIS ARQUITECTÓNICO", cover_title_style))
    story.append(Paragraph(
        f"{xml_escape(data.get('archivo') or 'Proyecto Archmuse')} &nbsp;&nbsp;·&nbsp;&nbsp; "
        f"{datetime.today().strftime('%d/%m/%Y')}",
        cover_subtitle_style,
    ))

    # --- Bloque de contexto ---
    plantas_actual = edificio_cover.get("plantas")
    plantas_maximas = edificio_cover.get("plantas_maximas")
    plantas_text = str(plantas_actual) if plantas_actual is not None else "—"
    if plantas_maximas is not None:
        plantas_text += f" (máx. {plantas_maximas})"

    edificabilidad_maxima = edificio_cover.get("edificabilidad_maxima")
    edificabilidad_text = (
        f"{edificabilidad_maxima:.2f} m²/m²" if edificabilidad_maxima is not None else "—"
    )

    context_rows = [
        ["Ciudad", xml_escape(proyecto_cover.get("ciudad") or "—")],
        ["Tipología", xml_escape(proyecto_cover.get("tipologia") or "—")],
        ["Zona CTE", xml_escape(proyecto_cover.get("zona_cte") or "—")],
        ["Plantas", plantas_text],
        ["Edificabilidad", edificabilidad_text],
    ]
    context_table = Table(context_rows, colWidths=[5 * cm, 9 * cm])
    context_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f5f5")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(context_table)
    story.append(Spacer(1, 0.8 * cm))

    # --- Puntuación global ---
    cover_score_style = ParagraphStyle(
        "ArchmuseCoverScore", parent=styles["Heading1"], fontSize=48, alignment=TA_CENTER,
        textColor=_score_color(score_cover), spaceAfter=2,
    )
    cover_valoracion_style = ParagraphStyle(
        "ArchmuseCoverValoracion", parent=styles["Normal"], alignment=TA_CENTER, fontSize=13,
        textColor=_score_color(score_cover), spaceAfter=16,
    )
    story.append(Paragraph(f"{score_cover}%", cover_score_style))
    if valoracion_cover:
        story.append(Paragraph(xml_escape(str(valoracion_cover).upper()), cover_valoracion_style))

    # --- Top 3 issues críticos ---
    story.append(Paragraph("Incidencias críticas principales", h2))
    criticos_cover = [i for i in (data.get("issues") or []) if i.get("severity") == "CRITICO"]
    if not criticos_cover:
        no_criticos_style = ParagraphStyle(
            "ArchmuseNoCriticos", parent=body, textColor=colors.HexColor("#27ae60")
        )
        story.append(Paragraph("Sin issues críticos detectados.", no_criticos_style))
    else:
        for issue in criticos_cover[:3]:
            titulo = xml_escape(issue.get("titulo", ""))
            solucion = xml_escape(_truncate(issue.get("solucion", ""), 100))
            story.append(Paragraph(f"• <b>{titulo}</b> — {solucion}", body))

    # --- Conclusión ejecutiva IA ---
    conclusion_cover = (data.get("analisis_ia") or {}).get("conclusion_ejecutiva")
    if conclusion_cover:
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph("Conclusión ejecutiva", h2))
        story.append(Paragraph(xml_escape(_truncate(conclusion_cover, 800)), body))

    story.append(PageBreak())

    # --- Cabecera -----------------------------------------------------------
    proyecto = data.get("proyecto") or {}
    archivo = xml_escape(data.get("archivo") or "Proyecto Archmuse")
    ciudad = xml_escape(proyecto.get("ciudad") or "—")
    tipologia = xml_escape(proyecto.get("tipologia") or "—")
    zona_cte = xml_escape(proyecto.get("zona_cte") or "—")

    story.append(Paragraph(archivo, h1))
    story.append(Paragraph(
        f"Ciudad: {ciudad} &nbsp;&nbsp;·&nbsp;&nbsp; "
        f"Tipología: {tipologia} &nbsp;&nbsp;·&nbsp;&nbsp; "
        f"Zona climática CTE: {zona_cte}",
        meta_style,
    ))
    story.append(Spacer(1, 0.5 * cm))

    # --- Puntuación global ----------------------------------------------------
    score = data.get("puntuacion_global", 0)
    score_style = ParagraphStyle(
        "ArchmuseScore", parent=styles["Heading1"], fontSize=32, textColor=_score_color(score), spaceAfter=2
    )
    story.append(Paragraph(f"{score}%", score_style))
    story.append(Paragraph("Puntuación global del proyecto", meta_style))
    story.append(Spacer(1, 0.7 * cm))

    # --- Issues por severidad --------------------------------------------------
    issues = data.get("issues") or []
    story.append(Paragraph("Incidencias detectadas", h2))
    if not issues:
        story.append(Paragraph("Sin incidencias detectadas.", body))
    else:
        grouped: dict = {}
        for issue in issues:
            grouped.setdefault(issue.get("severity"), []).append(issue)
        for severity in _SEVERITY_ORDER:
            group = grouped.get(severity)
            if not group:
                continue
            severity_style = ParagraphStyle(
                "ArchmuseSeverity" + severity, parent=styles["Heading3"],
                textColor=_SEVERITY_COLOR[severity], spaceBefore=10, spaceAfter=4,
            )
            story.append(Paragraph(f"{_SEVERITY_LABEL[severity]} ({len(group)})", severity_style))
            rows = [["Título", "Código", "Habitación/Vivienda", "Solución"]]
            for issue in group:
                rows.append([
                    issue.get("titulo", ""),
                    issue.get("codigo", ""),
                    issue.get("room_label") or "—",
                    _truncate(issue.get("solucion", "")),
                ])
            table = Table(rows, colWidths=[4.2 * cm, 2.6 * cm, 3.2 * cm, 6.5 * cm], repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(table)
            story.append(Spacer(1, 0.3 * cm))

    # --- Resumen por vivienda ---------------------------------------------------
    viviendas = data.get("viviendas") or []
    if viviendas:
        story.append(Paragraph("Resumen por vivienda", h2))
        rows = [["Vivienda", "Puntuación", "Incidencias"]]
        for v in viviendas:
            nombre = v.get("nombre", "")
            n_issues = sum(1 for i in issues if i.get("unit_name") == nombre)
            rows.append([nombre, f"{v.get('puntuacion', 0)}%", str(n_issues)])
        table = Table(rows, colWidths=[8 * cm, 3 * cm, 3 * cm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ]))
        story.append(table)

    # --- Conclusión ejecutiva IA -------------------------------------------------
    analisis_ia = data.get("analisis_ia") or {}
    conclusion = analisis_ia.get("conclusion_ejecutiva")
    if conclusion:
        story.append(Paragraph("Conclusión ejecutiva", h2))
        story.append(Paragraph(xml_escape(conclusion), body))

    # C3: todo entregable sale marcado como borrador para revisión de un
    # colegiado, en todas las páginas y sin forma de desactivarlo.
    doc.build(story, onFirstPage=estampar(), onLaterPages=estampar())
    return buffer.getvalue()
