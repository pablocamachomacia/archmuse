"""Segmentación determinista del PDF real de un DB (`codigotecnico.org`),
contra el fixture real de DB-SI — mismo principio que
`test_extraccion_segmentador.py` para el XML del BOE: cero IA, cero red,
números verificados a mano contra el Índice real del documento (92 páginas),
no un umbral ajustado a ojo.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from extraccion import segmentador_pdf  # noqa: E402
from ingesta.fuentes.codigotecnico import _texto_desde_pdf  # noqa: E402
from ingesta.modelo import DocumentoOficial  # noqa: E402

FIXTURE = (RAIZ / "tests" / "fixtures" / "codigotecnico" / "DB-SI.pdf").read_bytes()


def _documento() -> DocumentoOficial:
    return DocumentoOficial(
        identificador="DB-SI",
        fuente="codigotecnico",
        titulo="Documento Básico SI — Seguridad en caso de Incendio",
        organismo="Ministerio de Transportes, Movilidad y Agenda Urbana",
        rango_codigo=None,
        rango_nombre="Documento Básico (texto consolidado vigente)",
        numero_oficial=None,
        fecha_publicacion=None,
        fecha_disposicion=None,
        fecha_actualizacion=None,
        url_oficial="https://www.codigotecnico.org/pdf/Documentos/SI/DBSI.pdf",
        url_xml="https://www.codigotecnico.org/pdf/Documentos/SI/DBSI.pdf",
        texto_crudo=_texto_desde_pdf("DB-SI", FIXTURE),
        hash_texto="test",
        formato="pdf",
        bytes_crudos=FIXTURE,
    )


def test_segmenta_los_25_apartados_y_6_de_7_anejos_reales():
    """Verificado a mano contra el Índice real de DB-SI (6 Secciones, 25
    apartados numerados en total; 7 Anejos A-G). El Anejo C es una
    limitación real y documentada, no un fallo silencioso: su encabezado
    real en el cuerpo nunca aparece como línea propia (solo en la cabecera
    de página repetida) — ver docstring de `_RE_ANEJO_CUERPO`. Si estos
    números cambian, algo del parser dejó de reconocer una marca real del
    documento — no es un umbral a ajustar a ojo."""
    segmentos = segmentador_pdf.segmentar(_documento())
    apartados = [s for s in segmentos if s.tipo_segmento == "apartado"]
    anejos = [s for s in segmentos if s.tipo_segmento == "anejo"]
    assert len(apartados) == 25
    assert len(anejos) == 6
    assert {a.id for a in anejos} == {
        "dbsi_anejo_a", "dbsi_anejo_b", "dbsi_anejo_d",
        "dbsi_anejo_e", "dbsi_anejo_f", "dbsi_anejo_g",
    }
    assert "dbsi_anejo_c" not in {a.id for a in anejos}


def test_apartados_llevan_su_seccion_como_capitulo():
    segmentos = segmentador_pdf.segmentar(_documento())
    por_id = {s.id: s for s in segmentos}
    primero = por_id["dbsi_sec_1_pt_1"]
    assert primero.tipo_segmento == "apartado"
    assert "Sección DB-SI 1" in primero.capitulo
    assert "Propagación interior" in primero.capitulo
    assert "Compartimentación en sectores de incendio" in primero.titulo


def test_orden_es_creciente_y_sin_huecos_repetidos():
    segmentos = segmentador_pdf.segmentar(_documento())
    ordenes = [s.orden for s in segmentos]
    assert ordenes == sorted(ordenes)
    assert len(set(ordenes)) == len(ordenes)


def test_cada_segmento_trae_texto_no_vacio_y_su_documento():
    segmentos = segmentador_pdf.segmentar(_documento())
    assert len(segmentos) > 0
    for s in segmentos:
        assert s.texto.strip()
        assert s.documento_identificador == "DB-SI"


def test_normalizar_ignora_tildes_espacios_y_guiones_de_justificado():
    assert segmentador_pdf._normalizar("Compartimentación") == segmentador_pdf._normalizar("compartimentaci-\nón")
    assert segmentador_pdf._normalizar("Espacios ocultos") == "espaciosocultos"


def test_titulo_coincide_por_contencion_no_penaliza_texto_de_mas():
    candidato = "Espacios ocultos. Paso de instalaciones a través de elementos de compartimentación de incendios 1 La compartimentación contra incendios..."
    esperado = "Espacios ocultos. Paso de instalaciones a través de elementos de compartimentación de incendios"
    assert segmentador_pdf._titulo_coincide(candidato, esperado)


def test_documento_sin_indice_da_lista_vacia():
    """Un documento sin página `ÍNDICE` reconocible (p.ej. DB-HR/DB-SE, que
    usan otra convención de cabecera — ver limitaciones documentadas) no
    revienta: devuelve una lista vacía, no un error ni una excepción."""
    doc = _documento()
    sin_indice = DocumentoOficial(
        **{**doc.__dict__, "texto_crudo": doc.texto_crudo.replace("ÍNDICE", "nada aquí")}
    )
    assert segmentador_pdf.segmentar(sin_indice) == []
