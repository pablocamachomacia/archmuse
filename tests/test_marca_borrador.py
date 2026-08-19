# -*- coding: utf-8 -*-
"""DOC-3 — todo PDF de ArchMuse dice que es un borrador, y no hay forma de quitarlo.

Ejecutar:  pytest tests/test_marca_borrador.py

**Qué se está protegiendo.** La consecuencia vinculante C3 dice que todo
entregable sale marcado como borrador para la revisión de un colegiado. No es
una descarga de responsabilidad de las que nadie lee: delimita qué es
ArchMuse. Un informe suyo puede acabar en manos de un cliente final o de un
ayuntamiento; si no dice lo que es, parece otra cosa.

Tres propiedades, y la tercera es la que de verdad importa:

1. La leyenda aparece en **todas** las páginas de los dos PDF que el producto
   genera hoy — no sólo en la primera, que es la que nadie mira cuando el
   documento circula suelto.
2. La leyenda es **una sola**: el acta del agente y los PDF leen la misma
   constante. Dos textos que hoy dicen lo mismo dicen cosas distintas dentro de
   un año.
3. **No existe camino para generar un PDF sin ella.** Se comprueba recorriendo
   `analyzer/`: cualquier fichero que construya un `SimpleDocTemplate` tiene
   que pasar por `marca_borrador`. Un generador nuevo que se olvide pone la
   suite en rojo, sin que nadie tenga que acordarse de venir aquí.

Desde que `TL-2` está implementada (PRD aprobado el 2026-08-19), esto cubre
también **el DXF relleno**: la copia sale con la leyenda en su propia capa,
`00 ARCHMUSE BORRADOR`. Capa propia y no la del cuadro por dos motivos: el
arquitecto puede apagarla para imprimir sin borrar nada de su trabajo, y las
consultas que el producto ya hace sobre `00 CUADROS` siguen viendo lo mismo.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from pypdf import PdfReader  # noqa: E402

from analyzer.dossier_pdf import generar_dossier_pdf  # noqa: E402
from analyzer.marca_borrador import (CAPA_DXF, LEYENDA,  # noqa: E402
                                     estampar, estampar_dxf)
from analyzer.pdf_report import generate_pdf  # noqa: E402

#: Un trozo inconfundible de la leyenda. Se busca por fragmento y no entera
#: porque `pypdf` puede reordenar espacios al extraer el texto.
FRAGMENTO = "BORRADOR PARA REVISIÓN DE UN COLEGIADO"


def _paginas(pdf_bytes: bytes):
    return [(p.extract_text() or "") for p in PdfReader(__import__("io").BytesIO(pdf_bytes)).pages]


DATOS_INFORME = {
    "proyecto": {"nombre": "Proyecto de prueba", "municipio": "Madrid"},
    "edificio": {"plantas": 1},
    "puntuacion_global": 72,
    "problemas": [],
    "habitaciones": [{"nombre": "Salón", "superficie_m2": 20.0}],
}

DATOS_DOSSIER = {
    "proyecto": {"nombre": "Proyecto de prueba"},
    "ubicacion": {"lat": None, "lon": None},
    "plantas": [],
}


# --- 1. La marca está, y en todas las páginas ------------------------------

@pytest.mark.parametrize("generador,datos", [
    (generate_pdf, DATOS_INFORME),
    (generar_dossier_pdf, DATOS_DOSSIER),
])
def test_todas_las_paginas_dicen_que_es_un_borrador(generador, datos):
    paginas = _paginas(generador(datos))
    assert paginas, "el PDF salió sin páginas"
    sin_marca = [i for i, texto in enumerate(paginas, 1) if FRAGMENTO not in texto]
    assert sin_marca == [], (
        "estas páginas salen sin decir que son un borrador: %s. Un documento que "
        "circula suelto se lee por cualquier página, no por la primera." % sin_marca
    )


def test_la_leyenda_dice_quien_firma():
    """No basta con «borrador»: la frase tiene que decir de quién es la firma.

    Es la línea entre asesorar y firmar, y es lo que un juzgado leería.
    """
    assert "ArchMuse asesora" in LEYENDA
    assert "firma el arquitecto" in LEYENDA


# --- 2. Una sola leyenda ---------------------------------------------------

def test_el_acta_del_agente_usa_exactamente_la_misma_leyenda():
    from agente.acta import LEYENDA_BORRADOR

    assert LEYENDA_BORRADOR is LEYENDA


# --- 3. No hay forma de generar un PDF sin marca --------------------------

def test_ningun_generador_de_pdf_se_salta_la_marca():
    """LA PROPIEDAD QUE HACE QUE ESTO SIGA SIENDO CIERTO DENTRO DE UN AÑO.

    Recorre `analyzer/` en vez de comprobar una lista escrita a mano: el
    generador de PDF número tres lo escribirá alguien que no ha leído este
    fichero, y tiene que ponerse rojo igual.
    """
    culpables = []
    for fichero in sorted((RAIZ / "analyzer").rglob("*.py")):
        fuente = fichero.read_text(encoding="utf-8")
        if "SimpleDocTemplate(" not in fuente:
            continue
        if fichero.name == "marca_borrador.py":
            continue
        if "marca_borrador" not in fuente:
            culpables.append(fichero.name)
    assert culpables == [], (
        "estos módulos construyen un PDF sin pasar por `marca_borrador`: %s" % culpables)


def test_no_existe_ningun_interruptor_para_desactivarla():
    """Un `con_marca=False` —«sólo para las pruebas», «sólo para este
    cliente»— se usa el primer martes con prisa, y a partir de ahí existe un
    camino por el que sale un documento sin marcar."""
    import ast
    import inspect

    firma = inspect.signature(estampar)
    assert list(firma.parameters) == ["previo"]

    # Se mira el CÓDIGO, no la prosa: este mismo módulo explica en su docstring
    # por qué un `con_marca=False` sería un error, y esa explicación tiene que
    # poder escribirse sin que el test la confunda con la cosa prohibida.
    arbol = ast.parse((RAIZ / "analyzer" / "marca_borrador.py").read_text(encoding="utf-8"))
    sospechosos = ("con_marca", "sin_marca", "desactivar", "borrador_opcional")
    nombres = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.arg):
            nombres.add(nodo.arg)
        elif isinstance(nodo, ast.Name):
            nombres.add(nodo.id)
        elif isinstance(nodo, ast.keyword) and nodo.arg:
            nombres.add(nodo.arg)
        elif isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            # Una variable de entorno sólo puede llegar como literal.
            if nodo.value.startswith("ARCHMUSE_"):
                nombres.add(nodo.value)
    assert not (nombres & set(sospechosos)), sorted(nombres & set(sospechosos))
    assert not any(n.startswith("ARCHMUSE_") for n in nombres), sorted(nombres)
    # Y ninguna LLAMADA del producto le pasa nada raro: sólo un cabecero previo,
    # posicional. (Se excluye el propio módulo, donde `estampar` se define.)
    for fichero in sorted((RAIZ / "analyzer").rglob("*.py")):
        if fichero.name == "marca_borrador.py":
            continue
        for llamada in re.findall(r"estampar\(([^)]*)\)", fichero.read_text(encoding="utf-8")):
            assert "=" not in llamada, "%s: estampar(%s)" % (fichero.name, llamada)


def test_la_marca_se_pinta_aunque_el_cabecero_previo_falle():
    """Si el cabecero decorativo revienta, el documento puede salir feo; lo que
    no puede es salir sin decir que es un borrador."""
    pintados = []

    class LienzoFalso:
        def saveState(self): pass
        def restoreState(self): pass
        def setFont(self, *_a): pass
        def setFillColor(self, *_a): pass
        def drawCentredString(self, _x, _y, texto): pintados.append(texto)

    class DocFalso:
        pagesize = (595.0, 842.0)

    def cabecero_roto(_lienzo, _doc):
        raise RuntimeError("el logotipo no está")

    estampar(cabecero_roto)(LienzoFalso(), DocFalso())
    assert pintados == [LEYENDA]


# --- 4. La misma marca, en el DXF (TL-2 + DOC-3) --------------------------

def test_el_dxf_lleva_la_marca_en_su_propia_capa():
    import ezdxf

    doc = ezdxf.new("R2010")
    doc.modelspace().add_lwpolyline([(0, 0), (5, 0), (5, 4), (0, 4)], close=True)

    estampar_dxf(doc)

    marcas = doc.modelspace().query('MTEXT[layer=="%s"]' % CAPA_DXF)
    assert len(marcas) == 1
    assert marcas[0].text == LEYENDA
    assert CAPA_DXF in [c.dxf.name for c in doc.layers]


def test_la_marca_del_dxf_no_toca_la_capa_del_cuadro():
    """Las consultas que el producto ya hace sobre `00 CUADROS` tienen que ver
    exactamente lo que veían: una marca ahí habría cambiado sus resultados sin
    que nadie lo pidiera."""
    import ezdxf

    doc = ezdxf.new("R2010")
    estampar_dxf(doc)
    assert len(doc.modelspace().query('MTEXT[layer=="00 CUADROS"]')) == 0


def test_un_dxf_sin_extension_declarada_igual_lleva_marca():
    """Preferimos una marca en un sitio raro a un documento sin marca."""
    import ezdxf

    doc = ezdxf.new("R2010")
    estampar_dxf(doc)
    assert len(doc.modelspace().query('MTEXT[layer=="%s"]' % CAPA_DXF)) == 1


def test_ningun_modulo_guarda_un_dxf_sin_pasar_por_la_marca():
    """La misma política que para los PDF, para el otro formato que se entrega.

    El módulo que guarde el DXF número dos lo escribirá alguien que no ha leído
    este fichero.
    """
    culpables = []
    for fichero in sorted((RAIZ / "analyzer").rglob("*.py")):
        fuente = fichero.read_text(encoding="utf-8")
        # `.saveas(` dentro de una cadena de docstring no cuenta: se busca la
        # llamada real, que va sobre un identificador.
        if not re.search(r"^\s*\w+\.saveas\(", fuente, re.M):
            continue
        if fichero.name == "marca_borrador.py":
            continue
        if "marca_borrador" not in fuente:
            culpables.append(fichero.name)
    assert culpables == [], (
        "estos módulos guardan un DXF sin pasar por `marca_borrador`: %s" % culpables)
