"""Conector de codigotecnico.org — contra un PDF real (DB-SI), no un mock.
Cero red: se construye el `DocumentoOficial` con los mismos bytes que
`descargar_por_id` produciría, pasando `bytes_crudos` a mano en vez de
llamar a `red.obtener_con_cabeceras`.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from ingesta.fuentes.codigotecnico import FuenteCodigoTecnico, _texto_desde_pdf  # noqa: E402
from ingesta.modelo import FORMATOS_SOPORTADOS  # noqa: E402

FIXTURE = (RAIZ / "tests" / "fixtures" / "codigotecnico" / "DB-SI.pdf").read_bytes()


def test_catalogo_trae_los_11_documentos():
    f = FuenteCodigoTecnico()
    import datetime
    items = f.listar_sumario(datetime.date.today())
    ids = {i.identificador for i in items}
    assert ids == {
        "DB-SE", "DB-SE-AE", "DB-SE-C", "DB-SE-A", "DB-SE-F", "DB-SE-M",
        "DB-SI", "DB-SUA", "DB-HS", "DB-HE", "DB-HR",
    }


def test_listar_sumario_ignora_la_fecha():
    """No es un boletín diario — pedir dos fechas distintas da el mismo
    catálogo completo, no listas distintas o vacías según el día."""
    import datetime
    f = FuenteCodigoTecnico()
    a = f.listar_sumario(datetime.date(2020, 1, 1))
    b = f.listar_sumario(datetime.date.today())
    assert [i.identificador for i in a] == [i.identificador for i in b]


def test_texto_desde_pdf_real_no_esta_vacio_ni_corrupto():
    """Regresión directa del hallazgo de la sesión: lo que parecía una PDF
    con acentos rotos (`�`) era en realidad una visualización de terminal
    equivocada — el texto extraído SÍ trae los acentos correctos cuando se
    lee como UTF-8, no como bytes crudos."""
    texto = _texto_desde_pdf("DB-SI", FIXTURE)
    assert "Seguridad en caso de Incendio" in texto
    assert "Documento Básico" in texto  # con tilde real, no "B�sico"
    assert "\f" in texto  # separador de página que espera segmentador_pdf


def test_formato_pdf_esta_en_el_catalogo_cerrado():
    assert "pdf" in FORMATOS_SOPORTADOS


def test_cada_entrada_del_catalogo_declara_su_proveniencia_boe():
    """Condición de Pablo al aprobar el diseño de doble fuente: cada DB
    debe declarar de qué instrumento(s) BOE viene su texto vigente. Ninguna
    entrada del catálogo puede quedarse con la lista vacía por descuido."""
    from ingesta.fuentes.codigotecnico import _CATALOGO
    for entrada in _CATALOGO:
        assert entrada.boe_identificadores, f"{entrada.identificador} no declara ningún BOE que lo modifique"
        assert all(bid.startswith("BOE-A-") for bid in entrada.boe_identificadores)
        assert entrada.fecha_publicacion  # AAAA-MM-DD, no vacío


def test_db_si_referencia_el_rd_164_2025():
    """El caso verificado con más detalle en la auditoría: la fecha de
    portada de DB-SI ("4 marzo 2025") es literalmente la del RD 164/2025."""
    from ingesta.fuentes.codigotecnico import _POR_ID
    entrada = _POR_ID["DB-SI"]
    assert entrada.fecha_publicacion == "2025-03-04"
    assert "BOE-A-2025-7190" in entrada.boe_identificadores


def test_db_hr_no_hereda_el_rd_314_2006():
    """DB-HR no existía en el CTE original de 2006 — se aprobó en 2007 por
    su propio Real Decreto. Citarlo como si viniera de RD 314/2006 sería
    una cita legal incorrecta."""
    from ingesta.fuentes.codigotecnico import _POR_ID
    entrada = _POR_ID["DB-HR"]
    assert "BOE-A-2006-5515" not in entrada.boe_identificadores
    assert "BOE-A-2007-18400" in entrada.boe_identificadores
