# -*- coding: utf-8 -*-
"""La medición de una planta en PDF: una tabla por vivienda, con su procedencia.

**Qué documento es éste y en qué se diferencia del cuadro de superficies.**
`cuadro_pdf.py` explica **un cuadro que el plano ya trae dibujado**: sus filas
son las que el arquitecto puso en su `ACAD_TABLE`, y su trabajo es rellenarlas.
Éste no necesita que el plano traiga ninguna tabla: sus filas **son las piezas
que hay dibujadas**, una por una, en todas las viviendas de la planta. Es el
documento que hace falta cuando el cuadro todavía no existe —que es el caso del
segundo plano real del cliente, con tres viviendas y ningún `ACAD_TABLE`— y el
que permite medir una planta entera en vez de un piso recortado.

**Tres reglas, las mismas que el resto de entregables de ArchMuse:**

1. **No calcula nada.** Recibe la medición ya hecha por `analyzer/medicion.py`
   y la presenta. Dos sitios donde se decide cuánto mide una pieza es un sitio
   de más.
2. **La procedencia no se pierde, cambia de forma.** Cada fila lleva su
   referencia (rótulo y capa del DXF, lo que hace falta para ir a verla en
   AutoCAD); el criterio de medición se dice UNA vez como criterio general, y
   el reparto por ámbito una vez por familia, en nota. Repetir la misma frase
   en cada fila era lo que hacía este documento parecer salida de herramienta.
3. **Sale marcado como borrador**, en todas las páginas y sin forma de
   desactivarlo (`DOC-3`).

**Y una cuarta que es de este documento.** Una vivienda sin total **no se
maquilla**: donde iría el total va el motivo, con su magnitud. Es lo contrario
de lo que hace una hoja de cálculo, que suma siempre aunque la suma no
signifique nada.

**Maquetación (rediseño 2026-08-22, encargo directo de Pablo).** Documento
técnico A4 para la carpeta del proyecto, siguiendo la convención del cuadro de
superficies de un proyecto de ejecución español: cajetín en cabecera, cifras a
la derecha con coma decimal y la unidad declarada una vez en la cabecera de
columna, filas alternas, total con filete superior, pie fijo con «Página X de
Y», referencia del documento y huella SHA-256 del plano de origen.
"""
from __future__ import annotations

import io
from datetime import date
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from .marca_borrador import estampar, lienzo_numerado, pie_tecnico
from .medicion import AMBITO_EXTERIOR, AMBITO_INTERIOR, AMBITO_SIN_CLASIFICAR

#: Cómo se lee cada ámbito. En castellano de arquitecto: quien lee esto no
#: tiene por qué saber que dentro se llama `sin_clasificar`.
AMBITOS = {
    AMBITO_INTERIOR: ("Interior", colors.HexColor("#1B5E20")),
    AMBITO_EXTERIOR: ("Exterior", colors.HexColor("#37474F")),
    AMBITO_SIN_CLASIFICAR: ("Sin clasificar", colors.HexColor("#8A2A2A")),
}

_GRIS = colors.HexColor("#BBBBBB")
_GRIS_TEXTO = colors.HexColor("#555555")
_ZEBRA = colors.HexColor("#F6F6F6")
_FONDO_CABECERA = colors.HexColor("#E9E9E9")
_FONDO_SUMAS = colors.HexColor("#EFEFEF")

#: El criterio que antes se repetía en cada fila. Se dice una vez, aquí.
CRITERIO_GENERAL = (
    "Criterio de medición: cada pieza se mide sobre su propio contorno cerrado, "
    "tal como está dibujado en la capa que indica su columna «Referencia». El "
    "reparto entre superficie interior y exterior lo decide la familia de "
    "estancia reconocida en el rótulo, y se detalla en la nota de cada cuadro."
)


def _estilos():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("MedTitulo", parent=base["Heading1"],
                                 fontName="Helvetica-Bold", fontSize=15,
                                 spaceAfter=0),
        "h2": ParagraphStyle("MedH2", parent=base["Heading2"],
                             fontName="Helvetica-Bold", fontSize=11,
                             spaceBefore=14, spaceAfter=5),
        "h3": ParagraphStyle("MedH3", parent=base["Heading3"],
                             fontName="Helvetica-Bold", fontSize=9.5,
                             spaceBefore=12, spaceAfter=4),
        "etiqueta": ParagraphStyle("MedEtiqueta", parent=base["Normal"],
                                   fontName="Helvetica-Bold", fontSize=6.8,
                                   textColor=_GRIS_TEXTO),
        "meta": ParagraphStyle("MedMeta", parent=base["Normal"], fontSize=8.5,
                               textColor=_GRIS_TEXTO),
        "cuerpo": ParagraphStyle("MedCuerpo", parent=base["Normal"],
                                 fontSize=9, leading=12.5, spaceAfter=4),
        "celda": ParagraphStyle("MedCelda", parent=base["Normal"], fontSize=8,
                                leading=10),
        "celda_num": ParagraphStyle("MedCeldaNum", parent=base["Normal"],
                                    fontSize=8.5, leading=10, alignment=2),
        "celda_ref": ParagraphStyle("MedCeldaRef", parent=base["Normal"],
                                    fontSize=7.5, leading=9.5,
                                    textColor=_GRIS_TEXTO),
        "nota": ParagraphStyle("MedNota", parent=base["Normal"], fontSize=7.5,
                               leading=10, textColor=_GRIS_TEXTO, spaceAfter=2),
    }


def _p(texto: Any, estilo) -> Paragraph:
    return Paragraph("" if texto is None else str(texto), estilo)


def _cifra(valor: Any) -> str:
    """La cifra sola, con coma decimal: «24,10». La unidad va en la cabecera de
    la columna, como en un cuadro de superficies de proyecto de ejecución."""
    if valor is None:
        return "—"
    return ("%.2f" % float(valor)).replace(".", ",")


def _m2(valor: Any) -> str:
    """Una superficie en texto corrido: coma decimal y unidad («24,10 m²»)."""
    if valor is None:
        return "—"
    return _cifra(valor) + " m²"


def _referencia(pieza: Dict[str, Any]) -> str:
    """La columna estrecha que sustituye a la antigua frase de procedencia:
    rótulo y capa, que es lo que hace falta para seleccionar el recinto en
    AutoCAD sin buscar a ojo."""
    return "«%s» · %s" % (pieza.get("rotulo") or "(sin rótulo)",
                          pieza.get("capa") or "—")


def _nombre_pieza(pieza: Dict[str, Any]) -> str:
    """El nombre de la columna «Pieza»: el tipo de estancia, normalizado y en
    mayúsculas -«SALÓN + COCINA», «DORMITORIO», «BAÑO»-, no el rótulo bruto
    del DXF. El rótulo tal cual lo escribió el arquitecto aparece en
    «Referencia», que es su sitio.

    Sin familia reconocida no hay nombre normalizado que mostrar -mostrar uno
    inventado sería asumir un tipo de estancia que ArchMuse no ha podido
    establecer-, así que se dice que no se sabe en vez de dejar la celda muda.
    """
    familia = (pieza.get("familia") or "").strip()
    return familia.upper() if familia else "(sin clasificar)"


def _nota_de_familias(vivienda: Dict[str, Any]) -> List[str]:
    """El reparto por ámbito, dicho una vez por cuadro y no una vez por fila."""
    por_ambito: Dict[str, List[str]] = {}
    sin_familia: List[str] = []
    for pieza in vivienda.get("piezas") or ():
        familia = (pieza.get("familia") or "").strip()
        if familia:
            etiqueta = AMBITOS.get(pieza.get("ambito", ""), ("—",))[0]
            destino = por_ambito.setdefault(etiqueta, [])
            if familia.upper() not in destino:
                destino.append(familia.upper())
        else:
            sin_familia.append("«%s»" % (pieza.get("rotulo") or "(sin rótulo)"))
    notas = []
    for etiqueta in ("Interior", "Exterior"):
        if por_ambito.get(etiqueta):
            notas.append("%s: %s." % (etiqueta, ", ".join(por_ambito[etiqueta])))
    if sin_familia:
        notas.append(
            "Sin clasificar: %s — el rótulo no corresponde a ninguna estancia "
            "conocida, así que ArchMuse no decide si es superficie interior o "
            "exterior." % ", ".join(sin_familia))
    return notas


def _tabla_de_piezas(vivienda: Dict[str, Any], estilos) -> Table:
    filas: List[List[Any]] = [[
        _p("<b>PIEZA</b>", estilos["celda"]),
        _p("<b>REFERENCIA (rótulo · capa)</b>", estilos["celda"]),
        _p("<b>ÁMBITO</b>", estilos["celda"]),
        _p("<b>SUPERFICIE (m²)</b>", estilos["celda_num"]),
    ]]
    estilo = [
        ("GRID", (0, 0), (-1, -1), 0.4, _GRIS),
        ("BACKGROUND", (0, 0), (-1, 0), _FONDO_CABECERA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    piezas = list(vivienda.get("piezas") or ())
    for i, pieza in enumerate(piezas, start=1):
        etiqueta, color = AMBITOS.get(pieza.get("ambito", ""),
                                      (pieza.get("ambito", "—"), colors.black))
        filas.append([
            _p(_nombre_pieza(pieza), estilos["celda"]),
            _p(_referencia(pieza), estilos["celda_ref"]),
            _p(etiqueta, estilos["celda"]),
            _p(_cifra(pieza.get("area_m2")), estilos["celda_num"]),
        ])
        estilo.append(("TEXTCOLOR", (2, i), (2, i), color))
        if i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), _ZEBRA))

    # Los totales van en la misma tabla y no en un párrafo aparte: un total que
    # no está en la columna que se suma es un total que nadie comprueba.
    primera_suma = len(filas)
    filas.append([_p("Superficie útil interior", estilos["celda"]),
                  _p("Suma de las piezas interiores.", estilos["celda_ref"]),
                  _p("", estilos["celda"]),
                  _p(_cifra(vivienda.get("interior_m2")), estilos["celda_num"])])
    filas.append([_p("Superficie útil exterior", estilos["celda"]),
                  _p("Suma de las piezas exteriores.", estilos["celda_ref"]),
                  _p("", estilos["celda"]),
                  _p(_cifra(vivienda.get("exterior_m2")), estilos["celda_num"])])
    total = vivienda.get("total_util_m2")
    if total is None:
        motivos = " ".join("%s%s." % (motivo[:1].upper(), motivo[1:])
                           for motivo in (vivienda.get("impedimentos") or ()))
        filas.append([_p("<b>TOTAL SUPERFICIE ÚTIL</b>", estilos["celda"]),
                      _p("<b>No se totaliza.</b> %s" % motivos, estilos["celda_ref"]),
                      _p("", estilos["celda"]),
                      _p("<b>—</b>", estilos["celda_num"])])
    else:
        filas.append([_p("<b>TOTAL SUPERFICIE ÚTIL</b>", estilos["celda"]),
                      _p("Superficie útil interior más exterior.", estilos["celda_ref"]),
                      _p("", estilos["celda"]),
                      _p("<b>%s</b>" % _cifra(total), estilos["celda_num"])])
    ultima = len(filas) - 1
    estilo += [
        ("BACKGROUND", (0, primera_suma), (-1, -1), _FONDO_SUMAS),
        ("LINEABOVE", (0, primera_suma), (-1, primera_suma), 0.6, colors.black),
        ("LINEABOVE", (0, ultima), (-1, ultima), 1.0, colors.black),
    ]
    tabla = Table(filas, colWidths=[4.6 * cm, 7.4 * cm, 2.2 * cm, 3.0 * cm],
                  repeatRows=1)
    tabla.setStyle(TableStyle(estilo))
    return tabla


def _seccion_de_vivienda(vivienda: Dict[str, Any], estilos) -> List[Any]:
    bloque: List[Any] = [
        _p("Vivienda %s" % vivienda.get("vivienda", "—"), estilos["h3"]),
        _tabla_de_piezas(vivienda, estilos),
        Spacer(1, 0.12 * cm),
    ]
    for nota in _nota_de_familias(vivienda):
        bloque.append(_p(nota, estilos["nota"]))
    total = vivienda.get("total_util_m2")
    if total is not None and vivienda.get("superficie_por_union_m2") is not None:
        bloque.append(_p(
            "El total coincide con la superficie que ocupan realmente las "
            "piezas (%s): no hay nada dibujado dos veces."
            % _m2(vivienda.get("superficie_por_union_m2")), estilos["nota"]))
    solapes = vivienda.get("solapes") or ()
    if solapes:
        bloque.append(_p("Piezas que se pisan entre sí, y cuánto:", estilos["nota"]))
        for solape in solapes:
            bloque.append(_p("— «%s» y «%s» comparten %s."
                             % (solape.get("una"), solape.get("otra"),
                                _m2(solape.get("area_m2"))), estilos["nota"]))
    dudosos = vivienda.get("repartos_dudosos") or ()
    if dudosos:
        bloque.append(_p("Piezas cuyo reparto entre viviendas no es firme:",
                         estilos["nota"]))
        for duda in dudosos:
            bloque.append(_p(
                "— «%s» se ha contado en %s, pero está casi igual de cerca de %s "
                "(%s m frente a %s m)."
                % (duda.get("pieza"), duda.get("asignada_a"), duda.get("siguiente"),
                   _cifra(duda.get("distancia_m")),
                   _cifra(duda.get("distancia_siguiente_m"))), estilos["nota"]))
    return bloque


def _cajetin(datos: Dict[str, Any], estilos) -> Table:
    """La cabecera en bloque, como el cajetín de un plano: qué documento es, de
    qué plano sale, cuándo se emite y con qué herramienta. La huella SHA-256
    NO va aquí: va al pie, en cuerpo pequeño, en todas las páginas."""
    herramienta = datos.get("herramienta") or "ArchMuse"
    filas = [
        [_p("DOCUMENTO", estilos["etiqueta"]),
         _p("<b>Medición de superficies útiles</b>", estilos["cuerpo"])],
        [_p("PLANO DE ORIGEN", estilos["etiqueta"]),
         _p(datos.get("plano") or "—", estilos["cuerpo"])],
        [_p("FECHA DE EMISIÓN", estilos["etiqueta"]),
         _p(date.today().strftime("%d/%m/%Y"), estilos["cuerpo"])],
        [_p("HERRAMIENTA", estilos["etiqueta"]),
         _p(herramienta, estilos["cuerpo"])],
    ]
    tabla = Table(filas, colWidths=[3.4 * cm, 13.8 * cm])
    tabla.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, _GRIS),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return tabla


def generar_medicion_pdf(datos: Dict[str, Any]) -> bytes:
    """El PDF de la medición. Devuelve los bytes; no escribe a disco.

    `datos` es lo que produce `medicion.a_dict()`, más el nombre del plano, el
    sello del original y la lista de lo que no se comprueba.
    """
    estilos = _estilos()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.9 * cm, rightMargin=1.6 * cm,
        topMargin=1.8 * cm, bottomMargin=2.3 * cm,
        title="Medición de superficies útiles — ArchMuse",
    )

    viviendas = list(datos.get("viviendas") or ())
    story: List[Any] = [
        _p("Medición de superficies útiles", estilos["titulo"]),
        Spacer(1, 0.25 * cm),
        _cajetin(datos, estilos),
        Spacer(1, 0.3 * cm),
        _p(CRITERIO_GENERAL, estilos["nota"]),
    ]
    # Una capa elegida por parecido entre varias candidatas es una inferencia,
    # no un hecho -y una inferencia declara su hipótesis, no se presenta como
    # si el plano la hubiera dicho por sí mismo (ver `capa_elegida_por_heuristico`
    # en `analyzer/parser.py`).
    if datos.get("capa_criterio"):
        story.append(_p(datos["capa_criterio"], estilos["nota"]))
    story.append(Spacer(1, 0.3 * cm))

    if not viviendas:
        story.append(_p(
            "No se ha podido separar ninguna vivienda en este plano, así que no hay "
            "nada que medir. ArchMuse no inventa una agrupación.", estilos["cuerpo"]))
    else:
        con_total = sum(1 for v in viviendas if v.get("total_util_m2") is not None)
        story.append(_p(
            "%d vivienda(s) medida(s) en esta planta, separadas por %s. "
            "%d con superficie útil total; %d sin total, y en su cuadro va el motivo."
            % (len(viviendas), datos.get("agrupacion") or "—", con_total,
               len(viviendas) - con_total),
            estilos["cuerpo"]))
        for vivienda in viviendas:
            story.append(KeepTogether(_seccion_de_vivienda(vivienda, estilos)))

    sueltos = list(datos.get("rotulos_sin_piezas") or ())
    if sueltos:
        story.append(_p("Rótulos de vivienda sin ninguna pieza asignada", estilos["h2"]))
        story.append(_p(
            "El plano rotula estas viviendas y no se ha podido asignarles ningún "
            "recinto: %s. Puede ser una etiqueta de otra planta o de una leyenda, o "
            "puede ser una vivienda que no se ha medido. ArchMuse no decide cuál de las "
            "dos cosas es." % ", ".join("«%s»" % r for r in sueltos), estilos["cuerpo"]))

    descartes = list(datos.get("geometria_no_leida") or ())
    capas_ignoradas = list(datos.get("capas_ignoradas") or ())
    if descartes or capas_ignoradas:
        story.append(_p("Qué se ha descartado y por qué", estilos["h2"]))
        story.append(_p(
            "Un descarte silencioso es superficie que falta sin que nadie lo sepa. "
            "Cada motivo encabeza su grupo; debajo, solo la capa y lo descartado.",
            estilos["nota"]))
        story.append(Spacer(1, 0.15 * cm))
        # El motivo se dice una vez como encabezado del grupo, no repetido en
        # cada línea (encargo de formato de Pablo, 2026-08-22).
        grupos: Dict[str, List[str]] = {}
        for descarte in descartes:
            motivo = descarte.get("motivo") or "sin motivo declarado"
            grupos.setdefault(motivo, []).append(
                "— capa «%s», entidad %s (%s)"
                % (descarte.get("capa") or "—",
                   descarte.get("entidad") or "sin handle",
                   descarte.get("tipo") or "—"))
        for capa in capas_ignoradas:
            motivo = capa.get("motivo") or "sin motivo declarado"
            grupos.setdefault(motivo, []).append(
                "— capa «%s»: %d entidad(es)"
                % (capa.get("capa") or "—", capa.get("entidades") or 0))
        for motivo, lineas in grupos.items():
            bloque: List[Any] = [_p("%s%s." % (motivo[:1].upper(), motivo[1:].rstrip(".")),
                                    estilos["cuerpo"])]
            bloque += [_p(linea + ".", estilos["nota"]) for linea in lineas]
            story.append(KeepTogether(bloque))

    limitaciones = list(datos.get("no_comprobado") or ())
    if limitaciones:
        story.append(_p("Lo que este documento NO comprueba", estilos["h2"]))
        story.append(_p("Derivado de lo que se ha ejecutado, no redactado a mano.",
                        estilos["nota"]))
        story.append(Spacer(1, 0.15 * cm))
        for limitacion in limitaciones:
            story.append(_p("— %s" % limitacion, estilos["celda"]))

    # C3: la marca va en todas las páginas y no hay forma de quitarla. El pie
    # técnico (referencia, huella, franja) se pinta ANTES que la marca, que es
    # la prioritaria si algo revienta.
    referencia = "Medición de superficies útiles · %s · %s" % (
        datos.get("plano") or "—", date.today().strftime("%d/%m/%Y"))
    pie = pie_tecnico(referencia, datos.get("sello_origen_sha256"))
    doc.build(story, onFirstPage=estampar(pie), onLaterPages=estampar(pie),
              canvasmaker=lienzo_numerado())
    return buffer.getvalue()


def escribir_medicion_pdf(datos: Dict[str, Any], ruta_destino: str) -> Optional[str]:
    """Escribe el PDF. Devuelve la ruta."""
    contenido = generar_medicion_pdf(datos)
    with open(ruta_destino, "wb") as fh:
        fh.write(contenido)
    return ruta_destino
