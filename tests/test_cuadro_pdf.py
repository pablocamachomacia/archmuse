# -*- coding: utf-8 -*-
"""DOC-2 — el cuadro en PDF, y por qué lo que va debajo de la tabla es lo que importa.

Ejecutar:  pytest tests/test_cuadro_pdf.py

El DXF entregado lleva los números y vuelve al proyecto. Este PDF lleva **de
dónde sale cada uno y qué falta**: es lo que el arquitecto lee para decidir si
se fía, y lo que puede enseñar seis meses después si alguien le pregunta.

**Reescrito el 2026-09-13** con la plantilla fija (PRD
`docs/prd/2026-09-13-cuadro-plantilla-fija.md`): el PDF presenta la misma
rejilla que el comando, la web y el DXF, y ya no hay columna de estado ni
celdas «preexistentes» — la tabla de ArchMuse no copia nada del cuadro del
arquitecto. Lo que se fija aquí:

1. **Cada hueco vacío dice por qué.** Una celda vacía sin motivo es
   indistinguible de un descuido; con motivo, es una decisión discutible.
2. **Lo declarado por el arquitecto no se presenta como calculado por
   ArchMuse.** En un acta esas dos cosas no valen lo mismo.
3. **El PDF no calcula nada** ni inventa una cifra: presenta lo que le dan.
4. Lleva la marca de borrador en todas las páginas (`DOC-3`) y la huella del
   DXF original, para que «tu plano no se ha tocado» sea comprobable.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from pypdf import PdfReader  # noqa: E402

from agente.efectos import ESCRIBE_FICHERO, Autorizaciones, EfectoNoAutorizado  # noqa: E402
from agente.herramientas import plano  # noqa: E402
from agente.registro import registro  # noqa: E402
from analyzer.cuadro_pdf import escribir_cuadro_pdf, generar_cuadro_pdf  # noqa: E402
from tests.test_agente_goldens import construir_dxf, construir_dxf_de_planta  # noqa: E402

PERMISO = Autorizaciones.de([ESCRIBE_FICHERO], por="test")

TITULO = "CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA"


def _celda(fila, columna, texto):
    return {"fila": fila, "columna": columna, "texto": texto}


DATOS = {
    "plano": "piso.dxf",
    "vivienda": "VT1/1",
    "sello_origen_sha256": "abc123def456",
    "n_filas": 7,
    "n_columnas": 4,
    "celdas": [
        _celda(0, 0, TITULO),
        _celda(1, 0, "ESPACIOS INTERIORES"), _celda(1, 1, "SUPERFICIES UTILES INT."),
        _celda(1, 2, "ESPACIOS EXTERIORES"), _celda(1, 3, "SUPERFICIES UTILES EXT."),
        _celda(2, 0, "Salón/cocina"), _celda(2, 1, "21,90 m²"), _celda(2, 2, "Terraza"),
        _celda(3, 0, "TOTAL SUP. INTERIOR (m2)"), _celda(3, 1, "21,90 m²"),
        _celda(3, 2, "TOTAL SUP. EXTERIOR (m2)"),
        _celda(4, 0, "TOTAL S. UTIL(m2)"),
        _celda(5, 0, "S. CONSTRUIDA C."),
        _celda(6, 0, "VIVIENDA TIPO"), _celda(6, 1, "VT1/1"), _celda(6, 2, "NUMERO UDS:"),
    ],
    "celdas_sin_resolver": [
        {"etiqueta": "Terraza",
         "motivo": "se solapa con otra pieza dibujada: cuenta metros dos veces y no se "
                   "escribe su cifra."},
        {"etiqueta": "TOTAL S. UTIL(m2)",
         "motivo": "la superficie útil interior y la exterior no se suman en una sola "
                   "cifra: es criterio del técnico que firma (C-1)."},
    ],
    "preguntas_pendientes": [
        {"titulo": "ArchMuse no reconoce «Trastero» (Trastero (2,70 m²)). ¿Es un espacio "
                   "interior o exterior?",
         "ayuda": "Una respuesta vale para todas las piezas de esa familia."},
    ],
    "celdas_declaradas_por_el_arquitecto": ["LAVADERO"],
    "no_comprobado": ["no comprueba normativa de ningún tipo"],
}


def texto_de(pdf_bytes: bytes) -> str:
    """El texto del PDF con los espacios normalizados.

    Las celdas de una tabla estrecha se parten en varias líneas al componerse,
    así que buscar una frase literal en el texto extraído fallaría por un salto
    de línea que en el papel no existe. Lo que se comprueba es que la frase
    ESTÉ, no cómo se ha partido.
    """
    crudo = " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf_bytes)).pages)
    return re.sub(r"\s+", " ", crudo)


# --- 1. La tabla es la plantilla, y cada hueco dice por qué ---------------

def test_la_tabla_es_la_plantilla_de_archmuse():
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    assert TITULO in contenido
    assert "ESPACIOS INTERIORES" in contenido and "VIVIENDA TIPO" in contenido


def test_cada_cifra_y_cada_hueco_llevan_su_porque():
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    assert "21,90 m²" in contenido
    assert "cuenta metros dos veces" in contenido
    assert "no se suman en una sola cifra" in contenido


def test_el_vocabulario_del_motor_no_llega_al_papel():
    """Quien lee este PDF no sabe —ni tiene por qué— qué es un `SIN_CIFRA`."""
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    for interno in ("NO_DIBUJADA", "SIN_CIFRA", "tiene_fila", "BLOQUEADO"):
        assert interno not in contenido


def test_lo_que_no_se_ha_podido_calcular_tiene_su_propia_seccion():
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    assert "Lo que no se ha podido calcular" in contenido
    assert "ArchMuse no escribe una cifra que no pueda justificar" in contenido


def test_las_preguntas_pendientes_estan_para_poder_contestarlas():
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    assert "Qué haría falta para completarlo" in contenido
    assert "¿Es un espacio interior o exterior?" in contenido


def test_lo_que_no_se_comprueba_va_dicho():
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    assert "NO comprueba" in contenido
    assert "no comprueba normativa de ningún tipo" in contenido


# --- 2. La procedencia no se confunde -------------------------------------

def test_lo_declarado_por_el_arquitecto_no_se_presenta_como_calculado():
    """Atribuirse un dato ajeno es lo contrario de lo que hace un acta."""
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    assert "Declarado por el arquitecto, no calculado por ArchMuse" in contenido
    assert "LAVADERO" in contenido


def test_la_huella_del_original_va_en_el_documento():
    """«Tu plano no se ha tocado» sólo vale si se puede comprobar."""
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    assert "abc123def456" in contenido


# --- 3. No calcula nada ----------------------------------------------------

def test_el_pdf_no_inventa_ninguna_cifra():
    """`D-13`: ni un `0,00 m²` en un hueco vacío, ni una cifra que no le hayan dado."""
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    assert "0,00" not in contenido
    cifras = set(re.findall(r"\d+,\d{2} m²", contenido)) - {"2,70 m²"}   # la de la pregunta
    assert cifras == {"21,90 m²"}, cifras


def test_un_cuadro_vacio_lo_dice_en_vez_de_salir_en_blanco():
    contenido = texto_de(generar_cuadro_pdf({"plano": "x.dxf", "celdas": []}))
    assert "No se ha podido calcular ninguna celda" in contenido


def test_el_rotulo_sale_como_esta_en_el_plano():
    """«Bano» no es una palabra, y este PDF se le enseña a un cliente."""
    datos = dict(DATOS)
    datos["celdas"] = DATOS["celdas"] + [_celda(2, 3, ""), _celda(3, 3, "")]
    datos["celdas"] = [c for c in datos["celdas"] if c["texto"] != "Salón/cocina"] + [
        _celda(2, 0, "Baño")]
    contenido = texto_de(generar_cuadro_pdf(datos))
    assert "Baño" in contenido
    assert "Bano" not in contenido


def test_un_rotulo_con_marcado_no_rompe_el_documento():
    datos = dict(DATOS)
    datos["celdas"] = DATOS["celdas"] + [_celda(2, 3, "<b>&")]
    assert "<b>&" in texto_de(generar_cuadro_pdf(datos))


# --- 4. La marca de borrador ----------------------------------------------

def test_todas_las_paginas_dicen_que_es_un_borrador():
    paginas = [(p.extract_text() or "")
               for p in PdfReader(io.BytesIO(generar_cuadro_pdf(DATOS))).pages]
    assert paginas
    for i, pagina in enumerate(paginas, 1):
        assert "BORRADOR PARA REVISIÓN DE UN COLEGIADO" in pagina, "página %d" % i


# --- 5. La capacidad -------------------------------------------------------

def test_la_capacidad_esta_declarada_como_io_con_su_efecto():
    # plano.cuadro_en_pdf se fusionó en plano.entregable_en_pdf (Prompt 1.7,
    # cierre de C4, 2026-08-21) -- mismo comportamiento, tipo="cuadro".
    cap = registro(recargar=True).buscar("plano.entregable_en_pdf")
    assert cap.naturaleza == "io"
    assert cap.efectos == (ESCRIBE_FICHERO,)


def test_sin_autorizacion_no_escribe_el_pdf(tmp_path):
    cap = registro(recargar=True).buscar("plano.entregable_en_pdf")
    with pytest.raises(EfectoNoAutorizado):
        cap.invocar({"tipo": "cuadro", "ruta": "x.dxf",
                     "ruta_destino": str(tmp_path / "x.pdf")})
    assert not (tmp_path / "x.pdf").exists()


def test_un_dxf_que_no_se_puede_calcular_no_produce_un_pdf_vacio(tmp_path):
    """Un PDF con una tabla en blanco se lee como «no hay superficies», que es
    justo la lectura contraria a «no he podido calcularlas». Con la plantilla
    fija el caso ya no es «no trae cuadro» sino «trae dos viviendas»."""
    origen = construir_dxf_de_planta(tmp_path)
    destino = tmp_path / "cuadro.pdf"
    resultado = plano.cuadro_en_pdf(origen, str(destino))
    assert resultado["ok"] is False
    assert not destino.exists()


def test_un_dxf_sin_cuadro_del_arquitecto_si_tiene_su_pdf(tmp_path):
    """De punta a punta y sin el plano real: la plantilla no necesita el cuadro
    del arquitecto, así que el piso sintético produce su PDF entero."""
    origen = construir_dxf(tmp_path)
    destino = tmp_path / "cuadro.pdf"
    resultado = plano.cuadro_en_pdf(origen, str(destino))
    assert resultado["ok"] is True, resultado
    contenido = texto_de(destino.read_bytes())
    assert TITULO in contenido
    assert "Salón" in contenido and "Dormitorio 1" in contenido
    # Con el detector de D-13, no con la subcadena: «20,00 m²» contiene «0,00».
    assert not re.search(r"(?<![\d.,])0+(?:[.,]0+)?\s*m", contenido), contenido


def test_el_pdf_no_puede_sobrescribir_el_dxf(tmp_path):
    origen = construir_dxf(tmp_path)
    resultado = plano.cuadro_en_pdf(origen, origen)
    assert resultado["ok"] is False
    assert resultado["error"] == "destino_es_el_origen"


def test_escribir_el_pdf_deja_el_fichero_en_su_sitio(tmp_path):
    destino = tmp_path / "cuadro.pdf"
    escribir_cuadro_pdf(DATOS, str(destino))
    assert destino.exists() and destino.read_bytes().startswith(b"%PDF")
