# -*- coding: utf-8 -*-
"""La marca de borrador que llevan TODOS los documentos de ArchMuse (`DOC-3`).

**Qué es esto y por qué no es decorativo.** La consecuencia vinculante C3 del
paso 0 de alineación dice que todo entregable sale marcado como borrador para
la revisión de un colegiado. No es una cortesía ni una descarga de
responsabilidad de las que nadie lee: delimita lo que ArchMuse es. ArchMuse
**asesora**; el proyecto lo firma el arquitecto que lo redacta. Un PDF de
ArchMuse que no lo diga es un documento que puede acabar en manos de un cliente
final, o de un ayuntamiento, pareciendo lo que no es.

**Sin interruptor, y eso es el diseño entero.** No hay parámetro, ni variable
de entorno, ni argumento opcional para quitarla. Un parámetro `con_marca=False`
—por muy bien intencionado que naciera, «sólo para las pruebas», «sólo para el
cliente que la pidió sin ella»— se usa el primer martes con prisa y, a partir
de ese día, existe un camino por el que sale un documento sin marcar. Por eso
la firma de `estampar()` no admite ninguna forma de desactivarla, y por eso
`tests/test_marca_borrador.py` recorre `analyzer/` y falla si aparece un
generador de PDF que no pase por aquí.

**Dónde vive la leyenda.** Aquí, y `agente/acta.py` la importa. La dirección
importa: el agente puede depender del dominio, nunca al revés. Tenerla escrita
dos veces garantizaría que un día digan cosas distintas.

Uso:

    doc.build(story, onFirstPage=estampar(), onLaterPages=estampar())

o, si el documento ya tenía su propio pie o cabecero:

    doc.build(story, onFirstPage=estampar(_cabecero), onLaterPages=estampar(_cabecero))
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from reportlab.lib import colors
from reportlab.lib.units import cm

#: El texto exacto. Se lee en el pie de **todas** las páginas.
LEYENDA = (
    "BORRADOR PARA REVISIÓN DE UN COLEGIADO. ArchMuse asesora; el proyecto lo "
    "firma el arquitecto que lo redacta."
)

#: Capa propia para la marca en un DXF. Propia y no la del cuadro, por dos
#: motivos: el arquitecto puede apagarla para imprimir sin que eso borre nada de
#: su trabajo, y las consultas que ya hace el producto sobre `00 CUADROS`
#: siguen viendo exactamente lo que veían.
CAPA_DXF = "00 ARCHMUSE BORRADOR"

#: Altura del texto en el DXF, en unidades de dibujo (metros, tras la
#: conversión). 0,25 m se lee en una impresión a 1:100 sin taparlo todo.
ALTURA_DXF = 0.25

#: Tamaño y color: legible sin competir con el contenido. Un gris demasiado
#: claro sería una marca que técnicamente está y nadie lee, que es lo mismo que
#: no ponerla.
_TAMANO_PT = 6.8
_COLOR = colors.HexColor("#8A2A2A")
_GRIS_PIE = colors.HexColor("#555555")
_MARGEN_INFERIOR_CM = 0.45

#: Geometría compartida del pie técnico (rediseño 2026-08-22): la marca es la
#: última línea de un pie ordenado, no un párrafo suelto. Las cotas viven aquí
#: para que los dos PDF y la numeración de páginas dibujen sobre la misma
#: retícula sin duplicar números mágicos.
Y_FILETE_CM = 1.42
Y_REFERENCIA_CM = 1.08
Y_HUELLA_CM = 0.76


def _pintar(lienzo: Any, documento: Any) -> None:
    ancho, _alto = documento.pagesize
    lienzo.saveState()
    lienzo.setFont("Helvetica-Bold", _TAMANO_PT)
    lienzo.setFillColor(_COLOR)
    lienzo.drawCentredString(ancho / 2.0, _MARGEN_INFERIOR_CM * cm, LEYENDA)
    lienzo.restoreState()


def chip_borrador(lienzo: Any, documento: Any) -> None:
    """La franja de borrador de cabecera: discreta pero inequívoca.

    Un recuadro pequeño arriba a la derecha en TODAS las páginas. No sustituye
    a la leyenda del pie (esa es la marca vinculante de `DOC-3` y no se toca):
    la duplica donde el ojo entra en la página.
    """
    ancho, alto = documento.pagesize
    caja_ancho, caja_alto = 2.35 * cm, 0.52 * cm
    x = ancho - 1.6 * cm - caja_ancho
    y = alto - 1.12 * cm
    lienzo.saveState()
    lienzo.setStrokeColor(_COLOR)
    lienzo.setLineWidth(0.9)
    lienzo.rect(x, y, caja_ancho, caja_alto, stroke=1, fill=0)
    lienzo.setFont("Helvetica-Bold", 8)
    lienzo.setFillColor(_COLOR)
    lienzo.drawCentredString(x + caja_ancho / 2.0, y + 0.15 * cm, "BORRADOR")
    lienzo.restoreState()


def pie_tecnico(referencia: str, huella: Any = None) -> Callable[[Any, Any], None]:
    """El pie fijo de un documento técnico: filete, referencia y huella.

    `referencia` identifica el documento («Medición · v2s.dxf · 22/08/2026»);
    `huella` es el SHA-256 del plano de origen, si lo hay — va aquí, al pie y
    en cuerpo pequeño, no en la cabecera. La numeración «Página X de Y» la
    añade `lienzo_numerado()` en la misma retícula, porque el total de páginas
    no se conoce hasta el final.
    """
    def pintar(lienzo: Any, documento: Any) -> None:
        ancho, _alto = documento.pagesize
        izquierda, derecha = 1.9 * cm, ancho - 1.6 * cm
        lienzo.saveState()
        lienzo.setStrokeColor(colors.HexColor("#999999"))
        lienzo.setLineWidth(0.5)
        lienzo.line(izquierda, Y_FILETE_CM * cm, derecha, Y_FILETE_CM * cm)
        lienzo.setFont("Helvetica", 7)
        lienzo.setFillColor(_GRIS_PIE)
        lienzo.drawString(izquierda, Y_REFERENCIA_CM * cm, referencia)
        if huella:
            lienzo.setFont("Helvetica", 6)
            lienzo.drawString(
                izquierda, Y_HUELLA_CM * cm,
                "Huella de integridad del plano de origen (SHA-256): %s" % huella)
        lienzo.restoreState()
        chip_borrador(lienzo, documento)

    return pintar


def lienzo_numerado():
    """Un lienzo que escribe «Página X de Y» en el pie de cada página.

    El total de páginas solo se conoce al terminar, así que el lienzo guarda el
    estado de cada página y numera al guardar. Se usa como
    `doc.build(..., canvasmaker=lienzo_numerado())`.
    """
    from reportlab.pdfgen import canvas as _canvas

    class _LienzoNumerado(_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            _canvas.Canvas.__init__(self, *args, **kwargs)
            self._estados = []

        def showPage(self):
            self._estados.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._estados)
            for estado in self._estados:
                self.__dict__.update(estado)
                ancho = self._pagesize[0]
                self.saveState()
                self.setFont("Helvetica", 7)
                self.setFillColor(_GRIS_PIE)
                self.drawRightString(ancho - 1.6 * cm, Y_REFERENCIA_CM * cm,
                                     "Página %d de %d" % (self._pageNumber, total))
                self.restoreState()
                _canvas.Canvas.showPage(self)
            _canvas.Canvas.save(self)

    return _LienzoNumerado


def estampar(previo: Optional[Callable[[Any, Any], None]] = None) -> Callable[[Any, Any], None]:
    """Devuelve el callback de página que estampa la marca.

    `previo` es el pie o cabecero que el documento ya tuviera; se ejecuta
    primero y **su fallo no impide la marca**: si el cabecero decorativo de un
    dossier revienta, el documento puede salir feo, pero no puede salir sin
    decir que es un borrador.
    """
    def dibujar(lienzo: Any, documento: Any) -> None:
        if previo is not None:
            try:
                previo(lienzo, documento)
            except Exception:            # noqa: BLE001 - la marca es lo prioritario
                pass
        _pintar(lienzo, documento)

    return dibujar


# ---------------------------------------------------------------------------
# La misma marca, en un DXF
# ---------------------------------------------------------------------------

def estampar_dxf(doc: Any) -> None:
    """Añade la leyenda al modelspace de un DXF, en su propia capa.

    Se llama **antes de guardar la copia**, nunca sobre el fichero del
    arquitecto: quien escribe es `analyzer/cuadro_superficies_export.py`, que
    trabaja siempre sobre una copia en memoria del original.

    **Por qué en una capa propia.** El arquitecto puede apagarla para imprimir
    —es su plano— sin que eso borre nada de su trabajo, y las consultas que el
    producto ya hace sobre `00 CUADROS` siguen viendo exactamente lo mismo. Una
    marca en la capa del cuadro habría cambiado en silencio lo que ven esas
    consultas, que es cómo se rompe un test que sí importaba.

    **Dónde se coloca.** Justo debajo de la esquina inferior izquierda de lo
    dibujado (`$EXTMIN`), para no taparlo. Si el fichero no declara extensión
    —posible en un DXF recién creado— va al origen: preferimos una marca en un
    sitio raro a un documento sin marca.
    """
    try:
        extmin = doc.header.get("$EXTMIN", (0.0, 0.0, 0.0))
        x, y = float(extmin[0]), float(extmin[1])
    except Exception:                            # noqa: BLE001 - cabecera de terceros
        x, y = 0.0, 0.0
    if not doc.layers.has_entry(CAPA_DXF):
        doc.layers.add(CAPA_DXF)
    doc.modelspace().add_mtext(LEYENDA, dxfattribs={
        "layer": CAPA_DXF,
        "char_height": ALTURA_DXF,
        "insert": (x, y - ALTURA_DXF * 4, 0.0),
    })
