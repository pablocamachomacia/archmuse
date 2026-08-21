"""Segmentación determinista, ruta B (`extraccion/segmentador_pdf_b.py`),
contra el PDF real de DB-SUA — mismo principio que
`test_extraccion_segmentador_pdf.py` para la ruta A: cero IA, cero red,
números verificados contra las 20 candidatas reales de la ruta A (el
Índice del propio documento), no un umbral ajustado a ojo.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from extraccion import segmentador_pdf_b  # noqa: E402
from ingesta.modelo import DocumentoOficial  # noqa: E402

FIXTURE = (RAIZ / "tests" / "fixtures" / "codigotecnico" / "DB-SUA.pdf").read_bytes()

#: Los 5 apartados que la ruta B no segmenta todavía — límite real, medido
#: y documentado en el docstring del módulo, no un fallo silencioso: el
#: mismo documento usa DOS órdenes distintos de número/título entre
#: apartados, y solo uno de los dos está reconocido.
APARTADOS_SIN_SEGMENTAR = {"1.5", "2.1", "2.2", "8.1", "8.2"}


def _documento() -> DocumentoOficial:
    return DocumentoOficial(
        identificador="DB-SUA",
        fuente="codigotecnico",
        titulo="Documento Básico SUA — Seguridad de Utilización y Accesibilidad",
        organismo="Ministerio de Transportes, Movilidad y Agenda Urbana",
        rango_codigo=None,
        rango_nombre="Documento Básico (texto consolidado vigente)",
        numero_oficial=None,
        fecha_publicacion="20220614",
        fecha_disposicion=None,
        fecha_actualizacion=None,
        url_oficial="https://www.codigotecnico.org/pdf/Documentos/SUA/DBSUA.pdf",
        url_xml="",
        texto_crudo="placeholder — la ruta B lo sustituye por su propia extracción",
        hash_texto="test",
        formato="pdf",
        bytes_crudos=FIXTURE,
    )


def _numeros_de(segmentos) -> set:
    numeros = set()
    for s in segmentos:
        m = re.search(r"DB-SUA (\d+\.\d+)", s.titulo)
        if m:
            numeros.add(m.group(1))
    return numeros


def test_exige_bytes_crudos_no_se_cae_de_vuelta_a_la_ruta_a():
    doc = DocumentoOficial(
        identificador="DB-SUA", fuente="codigotecnico", titulo="x", organismo="x",
        rango_codigo=None, rango_nombre=None, numero_oficial=None,
        fecha_publicacion=None, fecha_disposicion=None, fecha_actualizacion=None,
        url_oficial="x", url_xml="", texto_crudo="1 Resbaladicidad de los suelos\n1 Con el fin de…",
        hash_texto="x", formato="pdf", bytes_crudos=None,
    )
    import pytest
    with pytest.raises(ValueError, match="bytes_crudos"):
        segmentador_pdf_b.segmentar(doc)


def test_segmenta_15_de_los_20_apartados_reales_de_db_sua():
    """El número exacto (15/20, no 20/20) es el contrato — ver
    APARTADOS_SIN_SEGMENTAR y el docstring de segmentador_pdf_b.py. Si sube
    o baja, algo cambió en el reconocimiento y hay que mirar por qué antes
    de tocar este número."""
    segmentos = segmentador_pdf_b.segmentar(_documento())
    numeros = _numeros_de(segmentos)
    assert len(numeros) == 15
    assert numeros == {
        "1.1", "1.2", "1.3", "1.4",
        "3.1",
        "4.1", "4.2",
        "5.1", "5.2",
        "7.1", "7.2", "7.3", "7.4",
        "9.1", "9.2",
    }
    assert numeros.isdisjoint(APARTADOS_SIN_SEGMENTAR)


def test_golden_titulos_de_apartados_atomicos_del_prompt_1():
    """Dos de los tres apartados que el Prompt 1 convirtió a BORRADOR sin
    descomposición (5.1, 7.1 — el tercero, 2.2 Atrapamiento, cae dentro de
    APARTADOS_SIN_SEGMENTAR) — la ruta B tiene que reconocer el mismo
    artículo con el mismo título, no uno parecido. 3.1 (Aprisionamiento)
    añade un tercer punto de control fuera de esos dos."""
    segmentos = segmentador_pdf_b.segmentar(_documento())
    por_numero = {}
    for s in segmentos:
        m = re.search(r"DB-SUA (\d+\.\d+) (.+)", s.titulo)
        if m:
            por_numero[m.group(1)] = m.group(2)

    assert por_numero["3.1"] == "Aprisionamiento"
    assert por_numero["5.1"] == "Ámbito de aplicación"
    assert por_numero["7.1"] == "Ámbito de aplicación"


def test_reconstruir_numero_de_apartado_no_toca_una_cifra_normal():
    """Guardarraíl del propio heurístico: una línea que es solo un número
    pero seguida de solo blancos hasta el final de la página (un número de
    página suelto, no un marcador de apartado) no se fusiona con nada."""
    texto = "Un título cualquiera\n\n8\n\n\n\n"
    resultado = segmentador_pdf_b._reconstruir_numero_de_apartado(texto)
    assert resultado == texto  # nada cambia: no hay contenido real después del «8»
