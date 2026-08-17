"""Segmentación determinista, contra el CTE real. Cero IA, cero red — el
mismo fixture que ya usa `test_ingesta_boe.py` (`BOE-A-2006-5515.xml`, el
Real Decreto 314/2006 completo tal como lo sirve el BOE).
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from extraccion.segmentador import segmentar  # noqa: E402
from ingesta.fuentes.boe import FuenteBOE  # noqa: E402

FIXTURE = (RAIZ / "tests" / "fixtures" / "boe" / "BOE-A-2006-5515.xml").read_bytes()


def _documento():
    return FuenteBOE()._documento_desde_xml(
        "BOE-A-2006-5515", "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2006-5515", FIXTURE
    )


def test_segmenta_los_28_segmentos_reales():
    """Verificado a mano contra el XML real (ver
    docs/design/2026-08-06-extraccion-cte.md §0): 1 artículo único + 9
    disposiciones + 15 artículos numerados (Capítulos 1-3 del Anejo) + 3
    anejos = 28. Si este número cambia, algo del parser dejó de reconocer una
    marca real del BOE — no es un umbral a ajustar a ojo."""
    segmentos = segmentar(_documento())
    assert len(segmentos) == 28
    tipos = [s.tipo_segmento for s in segmentos]
    assert tipos.count("articulo") == 1 + 15  # el único + los 15 numerados
    assert tipos.count("disposicion") == 9
    assert tipos.count("anejo") == 3


def test_articulo_unico_es_el_primero():
    segmentos = segmentar(_documento())
    primero = segmentos[0]
    assert primero.id == "articulo_unico"
    assert primero.tipo_segmento == "articulo"
    assert primero.titulo.startswith("Artículo único")
    assert primero.capitulo is None  # está en el cuerpo del decreto, no en el Anejo
    assert primero.orden == 1


def test_articulos_numerados_llevan_su_capitulo():
    """Los 15 artículos numerados están DENTRO del Anejo, repartidos en 3
    capítulos — verificado contra el índice real del propio documento."""
    segmentos = segmentar(_documento())
    por_id = {s.id: s for s in segmentos}

    assert "Capítulo 1" in por_id["articulo_1"].capitulo
    assert "Disposiciones generales" in por_id["articulo_1"].capitulo
    assert "Capítulo 2" in por_id["articulo_5"].capitulo
    assert "Capítulo 3" in por_id["articulo_9"].capitulo
    assert "Capítulo 3" in por_id["articulo_15"].capitulo


def test_anejos_en_orden_con_titulo_completo():
    segmentos = segmentar(_documento())
    anejos = [s for s in segmentos if s.tipo_segmento == "anejo"]
    assert [a.titulo for a in anejos] == [
        "ANEJO I. Contenido del proyecto",
        "ANEJO II. Documentación del seguimiento de la obra",
        "ANEJO III. Terminología",
    ]
    assert all(len(a.texto) > 500 for a in anejos)  # cuerpo real, no vacío


def test_texto_es_literal_no_resumido():
    """El artículo 2 (Ámbito de aplicación) es uno de los más largos y con
    más matices del decreto — si el segmentador perdiera texto por el
    camino, sería aquí donde más se notaría."""
    segmentos = segmentar(_documento())
    articulo_2 = next(s for s in segmentos if s.id == "articulo_2")
    assert "ámbito de aplicación" in articulo_2.titulo.lower()
    assert len(articulo_2.texto) > 3000
    assert "edificaciones" in articulo_2.texto.lower() or "edificios" in articulo_2.texto.lower()


def test_preambulo_no_se_cuela_en_ningun_segmento():
    """El preámbulo (la exposición de motivos, ~15 párrafos antes de "D I S P
    O N G O :") no es cuerpo de ningún artículo — se descarta a propósito
    porque no está firmado como norma, es la justificación política."""
    segmentos = segmentar(_documento())
    primero = segmentos[0]
    assert "segunda mitad del siglo" not in primero.texto  # frase real del preámbulo


def test_documento_sin_estructura_reconocible_da_lista_vacia():
    """Fail-soft, no fail-closed con excepción: un documento sin `p.articulo`
    ni `p.anexo_num` no es un error del segmentador, es un documento sin
    estructura normativa reconocible — el pipeline decide qué hacer con una
    lista vacía, este módulo no decide por él lanzando una excepción."""
    from ingesta.modelo import DocumentoOficial

    doc = DocumentoOficial(
        identificador="X", fuente="boe", titulo="t", organismo="o",
        rango_codigo=None, rango_nombre=None, numero_oficial=None,
        fecha_publicacion=None, fecha_disposicion=None, fecha_actualizacion=None,
        url_oficial="https://ejemplo.invalid", url_xml="https://ejemplo.invalid/xml",
        texto_crudo="<documento><texto><p class='parrafo'>solo un párrafo suelto</p></texto></documento>",
        hash_texto="a" * 64,
    )
    assert segmentar(doc) == []


def test_xml_roto_da_lista_vacia_no_excepcion():
    from ingesta.modelo import DocumentoOficial

    doc = DocumentoOficial(
        identificador="X", fuente="boe", titulo="t", organismo="o",
        rango_codigo=None, rango_nombre=None, numero_oficial=None,
        fecha_publicacion=None, fecha_disposicion=None, fecha_actualizacion=None,
        url_oficial="https://ejemplo.invalid", url_xml="https://ejemplo.invalid/xml",
        texto_crudo="<no cierra", hash_texto="a" * 64,
    )
    assert segmentar(doc) == []


if __name__ == "__main__":
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith("test_"):
            try:
                fn()
                print(f"OK    {nombre}")
            except AssertionError as exc:
                fallos += 1
                print(f"FALLO {nombre}: {exc}")
    print(f"\n{'TODO OK' if not fallos else str(fallos) + ' FALLOS'}")
    sys.exit(1 if fallos else 0)
