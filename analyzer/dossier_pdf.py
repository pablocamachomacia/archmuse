"""Dossier de Inversión en PDF: portada, ficha técnica urbanística, planos
2D por planta y cuadro de viabilidad económica.

`docs/prd/2026-08-17-dossier-inversion-pdf.md` (aprobado 2026-08-17): usa
`reportlab` (ya dependencia, `analyzer/pdf_report.py`) -- sin dependencias
nuevas. Tres puntos de honestidad, todos ya decididos en el PRD:

1. **El render 3D es una imagen que el CLIENTE ya capturó** de su propio
   `<canvas>` (`render_3d_base64`, opción A de §14) -- este módulo nunca
   renderiza 3D por su cuenta. Si no llega, la portada se compone sin esa
   imagen (mapa + planta baja más grande), nunca con un placeholder que
   aparente ser un render real.
2. **El mapa de ubicación se pide a Mapbox Static Images API** con las
   coordenadas reales ya geocodificadas del proyecto -- si no hay
   coordenadas, o si la petición falla por cualquier motivo (sin token, sin
   red...), la portada se compone sin mapa. Nunca falla la generación
   entera del PDF por esto.
3. **El cuadro de viabilidad económica es exactamente lo que el usuario ya
   rellenó** en la pestaña de Viabilidad Económica/Análisis Avanzado -- se
   recibe ya calculado (mismo número que el usuario ve en pantalla, nunca
   recalculado aquí con una fórmula paralela) y conserva el mismo badge de
   "estimación tuya" que ya usa esa pestaña.

Función principal pura respecto a red: `_mapa_estatico_bytes` es la única
llamada de red, aislada y con fallo silencioso (nunca levanta excepción) --
el resto del módulo es formateo puro sobre los datos ya recibidos."""
from __future__ import annotations

import base64
import io
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from reportlab.graphics.shapes import Drawing, Polygon as ShapePolygon, String

from .marca_borrador import estampar

logger = logging.getLogger(__name__)

_ESTILOS = getSampleStyleSheet()
_TITULO = ParagraphStyle("DossierTitulo", parent=_ESTILOS["Title"], fontSize=26, spaceAfter=6, alignment=TA_CENTER)
_SUBTITULO = ParagraphStyle("DossierSubtitulo", parent=_ESTILOS["Normal"], fontSize=13, textColor=colors.HexColor("#555555"), alignment=TA_CENTER, spaceAfter=18)
_SECCION = ParagraphStyle("DossierSeccion", parent=_ESTILOS["Heading2"], fontSize=15, spaceBefore=14, spaceAfter=8)
_TEXTO = ParagraphStyle("DossierTexto", parent=_ESTILOS["Normal"], fontSize=10, leading=14)
_BADGE = ParagraphStyle("DossierBadge", parent=_ESTILOS["Normal"], fontSize=8, textColor=colors.HexColor("#8a5a00"), spaceAfter=8)
_PIE_FICHA = ParagraphStyle("DossierNoDisponible", parent=_ESTILOS["Normal"], fontSize=9, textColor=colors.HexColor("#888888"))


def _mapa_estatico_bytes(lat: float, lon: float, mapbox_token: Optional[str]) -> Optional[bytes]:
    """Imagen PNG de la ubicación real (Mapbox Static Images API). `None`
    ante cualquier fallo (sin token, sin red, respuesta no-200, timeout) --
    nunca levanta, nunca bloquea la generación del resto del dossier."""
    if not mapbox_token or lat is None or lon is None:
        return None
    url = (
        "https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v12/static/"
        f"{lon},{lat},17,0/640x420@2x?access_token={urllib.parse.quote(mapbox_token)}"
    )
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            if resp.status != 200:
                return None
            return resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("No se pudo obtener el mapa estático de Mapbox para el dossier: %s", exc)
        return None


def _decodificar_imagen_base64(data: Any) -> Optional[bytes]:
    """`data` puede venir como data-URL completa (`data:image/png;base64,...`)
    o como base64 puro. `None` (nunca una excepción) si no es decodificable
    -- una imagen de cliente mal formada no debe tumbar el dossier."""
    if not isinstance(data, str) or not data.strip():
        return None
    contenido = data.split(",", 1)[1] if data.startswith("data:") else data
    try:
        return base64.b64decode(contenido)
    except Exception:  # noqa: BLE001 - dato arbitrario de cliente
        return None


def _imagen_flowable(contenido: Optional[bytes], ancho_cm: float, alto_cm: float) -> Optional[Image]:
    if not contenido:
        return None
    try:
        img = Image(io.BytesIO(contenido), width=ancho_cm * cm, height=alto_cm * cm)
        img.hAlign = "CENTER"
        return img
    except Exception:  # noqa: BLE001 - imagen de origen externo (Mapbox) o de cliente, formato no garantizado
        return None


def _fila(etiqueta: str, valor: Any, formato=None) -> list:
    texto = "No disponible" if valor is None else (formato(valor) if formato else str(valor))
    return [Paragraph(etiqueta, _TEXTO), Paragraph(texto, _TEXTO)]


def _euros(v: float) -> str:
    return "{:,.0f} €".format(v).replace(",", ".")


def _m2(v: float) -> str:
    return "{:,.0f} m²".format(v).replace(",", ".")


def _pct(v: float) -> str:
    return "{:.1f}%".format(v)


def _tabla_datos(filas: list) -> Table:
    t = Table(filas, colWidths=[7 * cm, 9 * cm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555")),
    ]))
    return t


def _dibujar_planta(nombre: str, habitaciones: list) -> Optional[Drawing]:
    """Plano 2D de una planta: mismo dato (`poligono`/`nombre` por
    habitación) que ya usa `analyzer/plan_svg.py`/`analyzer/dxf_export.py`,
    dibujado aquí con primitivas de `reportlab.graphics` en vez de
    convertir el SVG (evita añadir `svglib` solo para esto). `None` si
    ninguna habitación tiene un polígono válido."""
    puntos_totales = []
    piezas = []
    for h in habitaciones or []:
        poligono = h.get("poligono") if isinstance(h, dict) else None
        if not isinstance(poligono, list) or len(poligono) < 3:
            continue
        pts = []
        for p in poligono:
            if not isinstance(p, (list, tuple)) or len(p) < 2:
                continue
            try:
                pts.append((float(p[0]), float(p[1])))
            except (TypeError, ValueError):
                continue
        if len(pts) < 3:
            continue
        piezas.append((h.get("nombre") or "", pts))
        puntos_totales.extend(pts)

    if not puntos_totales:
        return None

    xs = [p[0] for p in puntos_totales]
    ys = [p[1] for p in puntos_totales]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    ancho_real = max(max_x - min_x, 0.1)
    alto_real = max(max_y - min_y, 0.1)

    ancho_dibujo, alto_dibujo = 460.0, 300.0
    margen = 20.0
    escala = min((ancho_dibujo - 2 * margen) / ancho_real, (alto_dibujo - 2 * margen) / alto_real)

    def transformar(x, y):
        return (margen + (x - min_x) * escala, margen + (y - min_y) * escala)

    d = Drawing(ancho_dibujo, alto_dibujo + 24)
    d.add(String(ancho_dibujo / 2, alto_dibujo + 6, nombre, textAnchor="middle", fontSize=12, fontName="Helvetica-Bold"))
    for etiqueta, pts in piezas:
        coords = []
        for x, y in pts:
            tx, ty = transformar(x, y)
            coords.extend([tx, ty])
        poly = ShapePolygon(coords, strokeColor=colors.HexColor("#333333"), strokeWidth=1, fillColor=colors.HexColor("#f0ede6"))
        d.add(poly)
        cx = sum(coords[0::2]) / (len(coords) // 2)
        cy = sum(coords[1::2]) / (len(coords) // 2)
        d.add(String(cx, cy, etiqueta, textAnchor="middle", fontSize=7, fillColor=colors.HexColor("#333333")))
    return d


def generar_dossier_pdf(datos: dict) -> bytes:
    """`datos`: ver docstring de cabecera y `app.py::dossier_pdf` para el
    contrato exacto del body HTTP. Ninguna clave es obligatoria salvo
    `nombre_proyecto` -- todo lo demás ausente se traduce en "No disponible"
    o en la sección correspondiente omitida, nunca en un dato inventado."""
    nombre_proyecto = str(datos.get("nombre_proyecto") or "Proyecto ArchMuse")
    nombre_promotora = datos.get("nombre_promotora")
    logo_bytes = _decodificar_imagen_base64(datos.get("logo_base64"))

    def _cabecero(canvas, doc):
        canvas.saveState()
        y = A4[1] - 1.3 * cm
        if logo_bytes:
            try:
                from reportlab.lib.utils import ImageReader
                img = ImageReader(io.BytesIO(logo_bytes))
                canvas.drawImage(img, 1.5 * cm, y - 0.4 * cm, width=1.6 * cm, height=1.6 * cm,
                                  preserveAspectRatio=True, mask="auto")
            except Exception:  # noqa: BLE001 - logo de cliente, formato no garantizado
                pass
        if nombre_promotora:
            canvas.setFont("Helvetica", 9)
            canvas.setFillColor(colors.HexColor("#666666"))
            canvas.drawRightString(A4[0] - 1.5 * cm, y, str(nombre_promotora))
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#aaaaaa"))
        canvas.drawCentredString(A4[0] / 2, 1 * cm, "%d" % doc.page)
        canvas.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2.2 * cm, bottomMargin=1.8 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )
    story: list = []

    # --- Portada -----------------------------------------------------------
    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph(nombre_proyecto, _TITULO))
    story.append(Paragraph("Dossier de Inversión", _SUBTITULO))

    ubicacion = datos.get("ubicacion") or {}
    mapa_bytes = None
    if ubicacion.get("lat") is not None and ubicacion.get("lon") is not None:
        mapa_bytes = _mapa_estatico_bytes(ubicacion["lat"], ubicacion["lon"], datos.get("mapbox_token"))
    render_3d_bytes = _decodificar_imagen_base64(datos.get("render_3d_base64"))

    imagenes_portada = [
        img for img in (
            _imagen_flowable(render_3d_bytes, 16, 10),
            _imagen_flowable(mapa_bytes, 16, 9),
        ) if img is not None
    ]
    if imagenes_portada:
        for img in imagenes_portada:
            story.append(img)
            story.append(Spacer(1, 0.4 * cm))
    else:
        story.append(Paragraph(
            "Sin render 3D ni mapa de ubicación disponibles para esta portada.", _PIE_FICHA,
        ))
    story.append(PageBreak())

    # --- Ficha técnica urbanística ------------------------------------------
    story.append(Paragraph("Ficha técnica urbanística", _SECCION))
    solido = datos.get("solido_capaz") or {}
    superficie_solar = datos.get("superficie_solar_m2")
    superficie_construida = datos.get("superficie_total_construida_m2")
    edificabilidad = (
        superficie_construida / superficie_solar
        if superficie_construida and superficie_solar else None
    )
    ocupacion_pct = (
        solido.get("superficie_ocupada_m2") / superficie_solar * 100
        if solido.get("superficie_ocupada_m2") and superficie_solar else None
    )
    filas_urbanismo = [
        _fila("Superficie del solar", superficie_solar, _m2),
        _fila("Superficie construida total", superficie_construida, _m2),
        _fila("Superficie ocupada (Sólido Capaz)", solido.get("superficie_ocupada_m2"), _m2),
        _fila("Ocupación", ocupacion_pct, _pct),
        _fila("Edificabilidad (construida / solar)", edificabilidad, lambda v: "{:.2f}".format(v)),
        _fila("Plantas", solido.get("plantas_estimadas")),
        _fila("Altura máxima", solido.get("altura_max_m"), lambda v: "{:.1f} m".format(v)),
    ]
    story.append(_tabla_datos(filas_urbanismo))
    story.append(PageBreak())

    # --- Planos 2D por planta ------------------------------------------------
    viviendas = datos.get("viviendas") or []
    if viviendas:
        story.append(Paragraph("Planos de distribución", _SECCION))
        for v in viviendas:
            nombre_v = (v.get("nombre") or v.get("id") or "Planta") if isinstance(v, dict) else "Planta"
            dibujo = _dibujar_planta(nombre_v, v.get("habitaciones") if isinstance(v, dict) else None)
            if dibujo is not None:
                story.append(dibujo)
                story.append(Spacer(1, 0.6 * cm))
        story.append(PageBreak())

    # --- Viabilidad económica -------------------------------------------------
    story.append(Paragraph("Viabilidad económica", _SECCION))
    viabilidad = datos.get("viabilidad") or {}
    if viabilidad:
        story.append(Paragraph(
            "Estimación introducida por el propio usuario -- no es un dato de mercado de ArchMuse.", _BADGE,
        ))
        filas_viabilidad = [
            _fila("Superficie construida total", viabilidad.get("superficie"), _m2),
            _fila("Ratio de coste de construcción", viabilidad.get("ratioM2"), lambda v: _euros(v) + "/m²"),
            _fila("Coste de suelo estimado", viabilidad.get("costeSuelo"), _euros),
            _fila("Precio de venta estimado", viabilidad.get("precioVenta"), _euros),
            _fila("PEM orientativo", viabilidad.get("pem"), _euros),
            _fila("Repercusión de suelo", viabilidad.get("repercusionSuelo"), lambda v: _euros(v) + "/m²"),
            _fila("Margen bruto orientativo", viabilidad.get("margenBruto"), _euros),
        ]
        if viabilidad.get("margenPromotorPct") is not None:
            filas_viabilidad.append(_fila("Margen Promotor (%)", viabilidad.get("margenPromotorPct"), _pct))
        if viabilidad.get("ratioEficienciaSuperficie") is not None:
            filas_viabilidad.append(
                _fila("Ratio de eficiencia (útil/construida)", viabilidad.get("ratioEficienciaSuperficie") * 100, _pct)
            )
        story.append(_tabla_datos(filas_viabilidad))
    else:
        story.append(Paragraph(
            "El usuario todavía no ha rellenado la pestaña de Viabilidad Económica para este proyecto.",
            _PIE_FICHA,
        ))

    # C3: la marca de borrador se compone CON el cabecero propio del
    # dossier, no lo sustituye -- y se pinta aunque el cabecero falle.
    doc.build(story, onFirstPage=estampar(_cabecero), onLaterPages=estampar(_cabecero))
    return buffer.getvalue()
