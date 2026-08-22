# -*- coding: utf-8 -*-
"""El informe de coherencia del plano, en PDF (tarea `CO-6`).

PRD: `docs/prd/2026-08-19-revision-de-coherencia-del-plano.md`.

**Qué es este documento y qué no es.** Es lo que un arquitecto mira antes de que
un plano salga del estudio: qué no cuadra, dónde exactamente, y cuánto mide. No
es una revisión de proyecto — no dice si el plano cumple normativa, y la primera
página lo dice para que nadie lo confunda. Un informe limpio significa que el
plano no se contradice a sí mismo, no que esté bien.

**Las tres reglas, heredadas de `cuadro_pdf.py` y con una cuarta propia:**

1. **No calcula nada.** Recibe los hallazgos ya producidos por
   `analyzer/coherencia.py` y los presenta. La única traducción que hace es de
   presentación: una magnitud con su unidad interna («-1 piezas de diferencia»)
   se dice en el idioma de quien lee («falta 1 pieza»), sin tocar el dato.
2. **No gradúa la gravedad.** No hay colores de semáforo, ni «crítico», ni un
   orden que sugiera prioridad: los hallazgos van agrupados por tipo, y dentro
   de cada tipo en el orden en que se encontraron. Pintar de rojo el solape y de
   amarillo el rótulo repetido sería emitir criterio profesional con la paleta.
3. **Sale marcado como borrador** en todas las páginas, sin forma de quitarlo.
4. **Un informe sin hallazgos enumera lo que se ha comprobado.** Una hoja que
   sólo diga «todo correcto» se lee como que el programa no ha hecho nada; y
   además sería una afirmación mucho más fuerte de la que este documento puede
   sostener.

**Maquetación (rediseño 2026-08-22, encargo directo de Pablo).** La misma
retícula de documento técnico que `medicion_pdf.py`: cajetín en cabecera,
magnitudes con coma decimal y «m²» (sin repetir la cifra cuando la descripción
ya la dice), pie fijo con «Página X de Y», referencia del documento y huella
SHA-256 del plano de origen.
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
    KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from .marca_borrador import estampar, lienzo_numerado, pie_tecnico

#: Cómo se titula cada tipo de hallazgo en castellano de arquitecto. El
#: identificador interno (`solape_entre_recintos`) sirve para programar; a quien
#: lee el informe hay que decírselo en su idioma.
TITULOS = {
    "solape_entre_recintos": "Recintos que se solapan",
    "polilinea_mal_cerrada": "Contornos cerrados por suposición",
    "geometria_descartada": "Geometría que no ha entrado en el análisis",
    "etiqueta_duplicada": "Rótulos repetidos",
    "recinto_sin_etiqueta": "Piezas sin rotular",
    "el_cuadro_pide_una_pieza_que_no_esta_dibujada":
        "El cuadro pide piezas que no están dibujadas",
    "pieza_dibujada_que_el_cuadro_no_contempla":
        "Piezas dibujadas que el cuadro no contempla",
    "el_cuadro_y_el_plano_no_cuentan_lo_mismo":
        "El cuadro y el plano no cuentan lo mismo",
    "no_se_ha_leido_ningun_recinto": "No se ha leído ningún recinto",
}

AVISO_DE_ALCANCE = (
    "Este informe dice si el plano es <b>coherente consigo mismo</b>: si el dibujo y el "
    "cuadro de superficies hablan del mismo piso y si la geometría está bien construida. "
    "<b>No comprueba normativa</b> y no dice si el proyecto cumple. Tampoco gradúa la "
    "gravedad de lo que encuentra: dice qué es y cuánto mide, y el criterio lo pone el "
    "arquitecto."
)

_GRIS = colors.HexColor("#BBBBBB")
_GRIS_TEXTO = colors.HexColor("#555555")


def _estilos() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("CoherenciaTitulo", parent=base["Heading1"],
                                 fontName="Helvetica-Bold", fontSize=15,
                                 spaceAfter=0),
        "h2": ParagraphStyle("CoherenciaH2", parent=base["Heading2"],
                             fontName="Helvetica-Bold", fontSize=11,
                             spaceBefore=14, spaceAfter=5),
        "etiqueta": ParagraphStyle("CoherenciaEtiqueta", parent=base["Normal"],
                                   fontName="Helvetica-Bold", fontSize=6.8,
                                   textColor=_GRIS_TEXTO),
        "meta": ParagraphStyle("CoherenciaMeta", parent=base["Normal"], fontSize=8,
                               textColor=_GRIS_TEXTO, spaceAfter=2),
        "cuerpo": ParagraphStyle("CoherenciaCuerpo", parent=base["Normal"], fontSize=9.5,
                                 leading=13, spaceAfter=4),
        "grupo": ParagraphStyle("CoherenciaGrupo", parent=base["Normal"],
                                fontName="Helvetica-Bold", fontSize=9.5,
                                leading=12, spaceBefore=8, spaceAfter=3),
        "item": ParagraphStyle("CoherenciaItem", parent=base["Normal"], fontSize=9,
                               leading=12, spaceAfter=5, leftIndent=10),
    }


def _p(texto: Any, estilo) -> Paragraph:
    return Paragraph("" if texto is None else str(texto), estilo)


def _coma(texto: str) -> str:
    return texto.replace(".", ",")


def _magnitud(hallazgo: Dict[str, Any]) -> str:
    """La cifra que dimensiona el hallazgo, en el formato de la medición, o nada.

    Tres reglas de presentación (encargo de Pablo, 2026-08-22), sobre el dato
    intacto que produce `coherencia.py`:

    - Coma decimal y «m²», el mismo formato que `medicion_pdf.py`.
    - «piezas de diferencia» se dice en legible: la magnitud es
      dibujadas − huecos, así que negativa = «falta», positiva = «sobra».
    - Si la descripción ya contiene la cifra, no se repite la magnitud cruda
      detrás («4 m2» detrás de un texto que ya dice «4,00 m²»).

    Un hallazgo sin magnitud imprime la cadena vacía y **no un cero**: un cero
    se leería como «medido y da cero», que es una afirmación distinta.
    """
    valor = hallazgo.get("magnitud")
    if valor is None:
        return ""
    unidad = (hallazgo.get("unidad") or "").strip()

    if unidad == "piezas de diferencia":
        n = int(round(float(valor)))
        if n == 0:
            return ""
        if n < 0:
            texto = "falta 1 pieza" if n == -1 else "faltan %d piezas" % -n
        else:
            texto = "sobra 1 pieza" if n == 1 else "sobran %d piezas" % n
        return " — <b>%s</b>" % texto

    if unidad in ("m2", "m²"):
        cifra, unidad = _coma("%.2f" % float(valor)), "m²"
    elif isinstance(valor, (int, float)) and float(valor) == int(float(valor)):
        cifra = "%d" % int(float(valor))
    else:
        cifra = _coma("%g" % valor) if isinstance(valor, (int, float)) else str(valor)

    descripcion = hallazgo.get("descripcion") or ""
    ya_dicha = any(forma in descripcion for forma in
                   {cifra, cifra.replace(",", "."),
                    ("%g" % valor) if isinstance(valor, (int, float)) else cifra})
    if ya_dicha:
        return ""
    return (" — <b>%s %s</b>" % (cifra, unidad)).rstrip()


def _cajetin(datos: Dict[str, Any], estilos) -> Table:
    """La cabecera en bloque, como el cajetín de un plano. La huella SHA-256
    NO va aquí: va al pie, en cuerpo pequeño, en todas las páginas."""
    herramienta = datos.get("herramienta") or "ArchMuse"
    filas = [
        [_p("DOCUMENTO", estilos["etiqueta"]),
         _p("<b>Revisión de coherencia del plano</b>", estilos["cuerpo"])],
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


def generar_informe_pdf(datos: Dict[str, Any]) -> bytes:
    """Los bytes del informe. No escribe a disco.

    `datos` es lo que produce `plano.coherencia`, más el nombre del plano y —si
    lo hay— el sello del original.
    """
    estilos = _estilos()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.9 * cm, rightMargin=1.6 * cm,
        topMargin=1.8 * cm, bottomMargin=2.3 * cm,
        title="Revisión de coherencia del plano — ArchMuse",
    )

    hallazgos: Sequence[dict] = list(datos.get("hallazgos") or ())
    story: List[Any] = [
        _p("Revisión de coherencia del plano", estilos["titulo"]),
        Spacer(1, 0.25 * cm),
        _cajetin(datos, estilos),
        Spacer(1, 0.3 * cm),
    ]
    if datos.get("capa_de_recintos"):
        # Cuántas viviendas se han detectado va en cabecera y no escondido:
        # cambia lo que significa cada comprobación de abajo, y si ArchMuse ha
        # agrupado mal el arquitecto lo ve en la primera línea en vez de
        # deducirlo de unos hallazgos raros.
        viviendas = datos.get("viviendas") or 0
        story.append(_p(
            "Leído de la capa «%s», en %s. %d recinto(s)%s."
            % (datos["capa_de_recintos"],
               datos.get("unidad_del_dibujo") or "unidad no declarada",
               datos.get("recintos") or 0,
               " en %d vivienda(s)" % viviendas if viviendas else ""),
            estilos["meta"]))

    story.append(Spacer(1, 0.15 * cm))
    story.append(_p(AVISO_DE_ALCANCE, estilos["cuerpo"]))
    story.append(Spacer(1, 0.3 * cm))

    if hallazgos:
        story.append(_p("%d cosa(s) que conviene mirar" % len(hallazgos), estilos["h2"]))
        # Agrupados por tipo, y los tipos en el orden en que aparecen. Ordenar
        # por «importancia» exigiría decidir cuál es más importante, que es
        # justo lo que este documento no hace.
        por_tipo: Dict[str, List[dict]] = {}
        for h in hallazgos:
            por_tipo.setdefault(h.get("tipo", ""), []).append(h)
        for tipo, grupo in por_tipo.items():
            bloque: List[Any] = [
                _p("%s (%d)" % (TITULOS.get(tipo, tipo), len(grupo)), estilos["grupo"])]
            for h in grupo:
                bloque.append(_p(
                    "— %s<br/><font size='7.5' color='#555555'>Dónde: %s%s</font>"
                    % (h.get("descripcion", ""), h.get("entidad", ""), _magnitud(h)),
                    estilos["item"]))
            # El encabezado del grupo no se queda huérfano a final de página;
            # si el grupo entero no cabe, platypus lo parte igualmente.
            story.append(KeepTogether(bloque[:2]))
            story.extend(bloque[2:])
    else:
        story.append(_p("No se ha encontrado nada", estilos["h2"]))
        story.append(_p(
            "Ninguna de las comprobaciones de abajo ha dado resultado. Eso quiere decir "
            "que el plano no se contradice a sí mismo en lo que ArchMuse sabe mirar; no "
            "quiere decir que el proyecto esté correcto.", estilos["cuerpo"]))

    story.append(_p("Qué se ha comprobado", estilos["h2"]))
    for comprobacion in (datos.get("comprobado") or ()):
        # Llega como dict cuando viene de la capacidad (que serializa a JSON) y
        # como par cuando se llama a este módulo directamente. Aceptar las dos
        # formas evita que el informe se rompa según por dónde entre el dato,
        # que es un fallo que sólo aparece en producción.
        if isinstance(comprobacion, dict):
            que, para = comprobacion.get("que", ""), comprobacion.get("para", "")
        else:
            que, para = comprobacion
        story.append(_p("— <b>%s</b>: %s" % (que, para), estilos["item"]))

    no_comprobado = list(datos.get("no_comprobado") or ())
    if no_comprobado:
        story.append(_p("Qué NO se ha podido comprobar", estilos["h2"]))
        story.append(_p("Con su motivo, para que no se lea como comprobado y correcto.",
                        estilos["meta"]))
        story.append(Spacer(1, 0.15 * cm))
        for pendiente in no_comprobado:
            story.append(_p("— %s" % pendiente, estilos["item"]))

    # C3: la marca va en todas las páginas y no hay forma de quitarla. El pie
    # técnico se pinta ANTES que la marca, que es la prioritaria si algo falla.
    referencia = "Revisión de coherencia · %s · %s" % (
        datos.get("plano") or "—", date.today().strftime("%d/%m/%Y"))
    pie = pie_tecnico(referencia, datos.get("sello_origen_sha256"))
    doc.build(story, onFirstPage=estampar(pie), onLaterPages=estampar(pie),
              canvasmaker=lienzo_numerado())
    return buffer.getvalue()


def escribir_informe_pdf(datos: Dict[str, Any], ruta_destino: str) -> Optional[str]:
    """Escribe el informe. Devuelve la ruta."""
    contenido = generar_informe_pdf(datos)
    with open(ruta_destino, "wb") as fh:
        fh.write(contenido)
    return ruta_destino
