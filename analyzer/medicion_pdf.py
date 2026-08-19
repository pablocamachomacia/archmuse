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
2. **La columna que importa es la última.** De dónde sale cada cifra: qué
   recinto, con qué rótulo y en qué capa del DXF. Un número sin procedencia en
   un documento que se firma no vale nada.
3. **Sale marcado como borrador**, en todas las páginas y sin forma de
   desactivarlo (`DOC-3`).

**Y una cuarta que es de este documento.** Una vivienda sin total **no se
maquilla**: donde iría el total va el motivo, con su magnitud. Es lo contrario
de lo que hace una hoja de cálculo, que suma siempre aunque la suma no
signifique nada.
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

from .marca_borrador import estampar
from .medicion import AMBITO_EXTERIOR, AMBITO_INTERIOR, AMBITO_SIN_CLASIFICAR

#: Cómo se lee cada ámbito. En castellano de arquitecto: quien lee esto no
#: tiene por qué saber que dentro se llama `sin_clasificar`.
AMBITOS = {
    AMBITO_INTERIOR: ("Interior", colors.HexColor("#1B5E20")),
    AMBITO_EXTERIOR: ("Exterior", colors.HexColor("#37474F")),
    AMBITO_SIN_CLASIFICAR: ("Sin clasificar", colors.HexColor("#8A2A2A")),
}

_GRIS = colors.HexColor("#BBBBBB")


def _estilos():
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("MedH1", parent=base["Heading1"], spaceAfter=2),
        "h2": ParagraphStyle("MedH2", parent=base["Heading2"], spaceBefore=14,
                             spaceAfter=6),
        "h3": ParagraphStyle("MedH3", parent=base["Heading3"], spaceBefore=12,
                             spaceAfter=4),
        "meta": ParagraphStyle("MedMeta", parent=base["Normal"], fontSize=8.5,
                               textColor=colors.HexColor("#555555")),
        "celda": ParagraphStyle("MedCelda", parent=base["Normal"], fontSize=8,
                                leading=10),
        "cuerpo": base["Normal"],
    }


def _p(texto: Any, estilo) -> Paragraph:
    return Paragraph("" if texto is None else str(texto), estilo)


def _m2(valor: Any) -> str:
    """Una superficie tal como se escribe en un cuadro: coma decimal y unidad."""
    if valor is None:
        return "—"
    return ("%.2f m²" % float(valor)).replace(".", ",")


def _procedencia(pieza: Dict[str, Any]) -> str:
    """De dónde sale la cifra de esta fila, con lo que hace falta para ir a verla.

    El rótulo y la capa son lo que permite seleccionar el recinto en AutoCAD sin
    buscar a ojo. La familia se dice también porque es lo que ha decidido el
    ámbito, y así el arquitecto puede discutirlo en vez de tener que deducirlo.
    """
    partes = ["Recinto rotulado «%s» en la capa «%s» del DXF."
              % (pieza.get("rotulo") or "(sin rótulo)", pieza.get("capa") or "—")]
    familia = (pieza.get("familia") or "").strip()
    if familia:
        partes.append("Se cuenta como «%s», y por eso va en %s."
                      % (familia, AMBITOS.get(pieza.get("ambito", ""), ("—",))[0].lower()))
    else:
        partes.append("Su rótulo no corresponde a ninguna estancia conocida, así que "
                      "ArchMuse no decide si es superficie interior o exterior.")
    partes.append("Superficie medida sobre su propio contorno cerrado.")
    return " ".join(partes)


def _tabla_de_piezas(vivienda: Dict[str, Any], estilos) -> Table:
    filas: List[List[Any]] = [[
        _p("<b>Pieza</b>", estilos["celda"]),
        _p("<b>Superficie</b>", estilos["celda"]),
        _p("<b>Ámbito</b>", estilos["celda"]),
        _p("<b>De dónde sale</b>", estilos["celda"]),
    ]]
    estilo = [
        ("GRID", (0, 0), (-1, -1), 0.4, _GRIS),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
    ]
    for i, pieza in enumerate(vivienda.get("piezas") or (), start=1):
        etiqueta, color = AMBITOS.get(pieza.get("ambito", ""),
                                      (pieza.get("ambito", "—"), colors.black))
        filas.append([
            _p(pieza.get("rotulo") or "(sin rótulo)", estilos["celda"]),
            _p(_m2(pieza.get("area_m2")), estilos["celda"]),
            _p(etiqueta, estilos["celda"]),
            _p(_procedencia(pieza), estilos["celda"]),
        ])
        estilo.append(("TEXTCOLOR", (2, i), (2, i), color))

    # Los totales van en la misma tabla y no en un párrafo aparte: un total que
    # no está en la columna que se suma es un total que nadie comprueba.
    primera_suma = len(filas)
    filas.append([_p("<b>Superficie útil interior</b>", estilos["celda"]),
                  _p("<b>%s</b>" % _m2(vivienda.get("interior_m2")), estilos["celda"]),
                  _p("", estilos["celda"]), _p("Suma de las piezas interiores.",
                                               estilos["celda"])])
    filas.append([_p("<b>Superficie útil exterior</b>", estilos["celda"]),
                  _p("<b>%s</b>" % _m2(vivienda.get("exterior_m2")), estilos["celda"]),
                  _p("", estilos["celda"]), _p("Suma de las piezas exteriores.",
                                               estilos["celda"])])
    total = vivienda.get("total_util_m2")
    if total is None:
        explicacion = ("<b>No se totaliza.</b> " + " ".join(
            "%s%s." % (motivo[:1].upper(), motivo[1:])
            for motivo in (vivienda.get("impedimentos") or ())))
    else:
        explicacion = ("Superficie útil interior más exterior. Coincide con la "
                       "superficie que ocupan realmente las piezas (%s), así que no hay "
                       "nada dibujado dos veces."
                       % _m2(vivienda.get("superficie_por_union_m2")))
    filas.append([_p("<b>TOTAL SUPERFICIE ÚTIL</b>", estilos["celda"]),
                  _p("<b>%s</b>" % _m2(total), estilos["celda"]),
                  _p("", estilos["celda"]), _p(explicacion, estilos["celda"])])
    estilo += [
        ("BACKGROUND", (0, primera_suma), (-1, -1), colors.HexColor("#F5F5F5")),
        ("LINEABOVE", (0, primera_suma), (-1, primera_suma), 0.9, colors.black),
    ]
    tabla = Table(filas, colWidths=[3.6 * cm, 2.3 * cm, 2.1 * cm, 9.0 * cm],
                  repeatRows=1)
    tabla.setStyle(TableStyle(estilo))
    return tabla


def _seccion_de_vivienda(vivienda: Dict[str, Any], estilos) -> List[Any]:
    bloque: List[Any] = [
        _p("Vivienda %s" % vivienda.get("vivienda", "—"), estilos["h3"]),
        _tabla_de_piezas(vivienda, estilos),
    ]
    solapes = vivienda.get("solapes") or ()
    if solapes:
        bloque.append(Spacer(1, 0.15 * cm))
        bloque.append(_p("Piezas que se pisan entre sí, y cuánto:", estilos["celda"]))
        for solape in solapes:
            bloque.append(_p("• «%s» y «%s» comparten %s."
                             % (solape.get("una"), solape.get("otra"),
                                _m2(solape.get("area_m2"))), estilos["celda"]))
    dudosos = vivienda.get("repartos_dudosos") or ()
    if dudosos:
        bloque.append(Spacer(1, 0.15 * cm))
        bloque.append(_p("Piezas cuyo reparto entre viviendas no es firme:",
                         estilos["celda"]))
        for duda in dudosos:
            bloque.append(_p(
                "• «%s» se ha contado en %s, pero está casi igual de cerca de %s "
                "(%.2f m frente a %.2f m)."
                % (duda.get("pieza"), duda.get("asignada_a"), duda.get("siguiente"),
                   float(duda.get("distancia_m") or 0.0),
                   float(duda.get("distancia_siguiente_m") or 0.0)), estilos["celda"]))
    return bloque


def generar_medicion_pdf(datos: Dict[str, Any]) -> bytes:
    """El PDF de la medición. Devuelve los bytes; no escribe a disco.

    `datos` es lo que produce `medicion.a_dict()`, más el nombre del plano, el
    sello del original y la lista de lo que no se comprueba.
    """
    estilos = _estilos()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm,
        topMargin=1.6 * cm, bottomMargin=1.9 * cm,
        title="Medición de superficies útiles — ArchMuse",
    )

    viviendas = list(datos.get("viviendas") or ())
    story: List[Any] = [
        _p("Medición de superficies útiles", estilos["h1"]),
        _p("Plano: %s" % (datos.get("plano") or "—"), estilos["meta"]),
        _p("Emitido el %s por ArchMuse." % date.today().isoformat(), estilos["meta"]),
    ]
    if datos.get("sello_origen_sha256"):
        story.append(_p(
            "El plano original no se ha modificado. Su huella SHA-256 antes y después "
            "de este trabajo es <font face='Courier'>%s</font>."
            % datos["sello_origen_sha256"], estilos["meta"]))
    story.append(Spacer(1, 0.4 * cm))

    if not viviendas:
        story.append(_p(
            "No se ha podido separar ninguna vivienda en este plano, así que no hay "
            "nada que medir. ArchMuse no inventa una agrupación.", estilos["cuerpo"]))
    else:
        con_total = sum(1 for v in viviendas if v.get("total_util_m2") is not None)
        story.append(_p(
            "%d vivienda(s) medida(s) en esta planta, separadas por %s. "
            "%d con superficie útil total; %d sin total, y debajo va el motivo de cada "
            "una." % (len(viviendas), datos.get("agrupacion") or "—", con_total,
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
    if descartes:
        story.append(_p("Geometría que no ha entrado en la medición", estilos["h2"]))
        story.append(_p(
            "Un descarte silencioso es superficie que falta sin que nadie lo sepa, así "
            "que va aquí con su motivo.", estilos["meta"]))
        story.append(Spacer(1, 0.2 * cm))
        for descarte in descartes:
            story.append(_p(
                "• %s — capa «%s», entidad %s (%s)."
                % (descarte.get("motivo") or "sin motivo declarado",
                   descarte.get("capa") or "—", descarte.get("entidad") or "sin handle",
                   descarte.get("tipo") or "—"), estilos["celda"]))

    limitaciones = list(datos.get("no_comprobado") or ())
    if limitaciones:
        story.append(_p("Lo que este documento NO comprueba", estilos["h2"]))
        story.append(_p("Derivado de lo que se ha ejecutado, no redactado a mano.",
                        estilos["meta"]))
        story.append(Spacer(1, 0.2 * cm))
        for limitacion in limitaciones:
            story.append(_p("• %s" % limitacion, estilos["celda"]))

    # C3: la marca va en todas las páginas y no hay forma de quitarla.
    doc.build(story, onFirstPage=estampar(), onLaterPages=estampar())
    return buffer.getvalue()


def escribir_medicion_pdf(datos: Dict[str, Any], ruta_destino: str) -> Optional[str]:
    """Escribe el PDF. Devuelve la ruta."""
    contenido = generar_medicion_pdf(datos)
    with open(ruta_destino, "wb") as fh:
        fh.write(contenido)
    return ruta_destino
