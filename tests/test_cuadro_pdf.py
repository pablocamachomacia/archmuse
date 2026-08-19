# -*- coding: utf-8 -*-
"""DOC-2 — el cuadro en PDF, y por qué la última columna es la que importa.

Ejecutar:  pytest tests/test_cuadro_pdf.py

El DXF relleno lleva los números y vuelve al proyecto. Este PDF lleva **de
dónde sale cada uno y qué falta**: es lo que el arquitecto lee para decidir si
se fía, y lo que puede enseñar seis meses después si alguien le pregunta.

Lo que se fija aquí:

1. **Cada celda dice de dónde sale.** Una celda vacía sin motivo es
   indistinguible de un descuido; con motivo, es una decisión discutible.
2. **Lo declarado por el arquitecto no se presenta como calculado por
   ArchMuse.** En un acta esas dos cosas no valen lo mismo, y atribuirse la
   primera sería apropiarse de un dato ajeno.
3. **El PDF no calcula nada** ni convierte un `N/D` en número: presenta lo que
   le dan, tal cual.
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
from tests.test_agente_goldens import construir_dxf  # noqa: E402

PERMISO = Autorizaciones.de([ESCRIBE_FICHERO], por="test")

DATOS = {
    "plano": "v2s.dxf",
    "sello_origen_sha256": "abc123def456",
    "celdas": [
        {"campo": "salon_cocina", "texto": "21,90 m²", "estado": "CALCULADO",
         "motivo": None},
        {"campo": "dormitorio_2", "texto": "0,00 m²", "estado": "CERO_REAL",
         "motivo": "se ha buscado y la vivienda no tiene ninguno"},
        {"campo": "superficie_construida_cerrada", "texto": "N/D",
         "estado": "NO_DISPONIBLE",
         "motivo": "no se puede medir sin los espesores de muro"},
        {"campo": "terraza_1", "texto": "N/D", "estado": "BLOQUEADO",
         "motivo": "hay dos piezas con esa etiqueta y no se puede saber cuál es"},
        {"campo": "numero_unidades", "texto": "8", "estado": "CALCULADO",
         "declarado_por_usuario": True},
        {"campo": "vivienda_tipo", "texto": "VT1 /3", "estado": "CALCULADO",
         "preexistente": True},
    ],
    "preguntas_pendientes": [
        {"titulo": "¿Qué pieza del plano es cada espacio exterior?",
         "ayuda": "Asigna cada pieza real al hueco que le corresponda."},
    ],
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


# --- 1. Cada celda dice de dónde sale -------------------------------------

def test_cada_celda_lleva_su_valor_y_su_porque():
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    assert "21,90 m²" in contenido
    assert "no se puede medir sin los espesores de muro" in contenido
    assert "hay dos piezas con esa etiqueta" in contenido


def test_los_estados_se_leen_en_castellano_de_arquitecto():
    """Quien lee este PDF no sabe —ni tiene por qué— qué es un `CERO_REAL`."""
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    assert "No existe en la vivienda" in contenido
    assert "No se puede saber del plano" in contenido
    assert "CERO_REAL" not in contenido


def test_lo_que_no_se_ha_podido_calcular_tiene_su_propia_seccion():
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    assert "Lo que no se ha podido calcular" in contenido
    assert "ArchMuse no escribe una cifra que no pueda justificar" in contenido


def test_las_preguntas_pendientes_estan_para_poder_contestarlas():
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    assert "Qué haría falta para completarlo" in contenido
    assert "¿Qué pieza del plano es cada espacio exterior?" in contenido


def test_lo_que_no_se_comprueba_va_dicho():
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    assert "NO comprueba" in contenido
    assert "no comprueba normativa de ningún tipo" in contenido


# --- 2. La procedencia no se confunde -------------------------------------

def test_lo_declarado_por_el_arquitecto_no_se_presenta_como_calculado():
    """Atribuirse un dato ajeno es lo contrario de lo que hace un acta."""
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    assert "Declarado por el arquitecto, no calculado por ArchMuse" in contenido


def test_lo_que_ya_estaba_en_el_dxf_se_dice_que_ya_estaba():
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    assert "Ya estaba escrito en el DXF" in contenido


def test_la_huella_del_original_va_en_el_documento():
    """«Tu plano no se ha tocado» sólo vale si se puede comprobar."""
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    assert "abc123def456" in contenido


# --- 3. No calcula nada ----------------------------------------------------

def test_un_ND_sigue_siendo_un_ND():
    contenido = texto_de(generar_cuadro_pdf(DATOS))
    assert "N/D" in contenido


def test_un_cuadro_vacio_lo_dice_en_vez_de_salir_en_blanco():
    contenido = texto_de(generar_cuadro_pdf({"plano": "x.dxf", "celdas": []}))
    assert "No se ha podido calcular ninguna celda" in contenido


# --- 4. La marca de borrador ----------------------------------------------

def test_todas_las_paginas_dicen_que_es_un_borrador():
    paginas = [(p.extract_text() or "")
               for p in PdfReader(io.BytesIO(generar_cuadro_pdf(DATOS))).pages]
    assert paginas
    for i, pagina in enumerate(paginas, 1):
        assert "BORRADOR PARA REVISIÓN DE UN COLEGIADO" in pagina, "página %d" % i


# --- 5. La capacidad -------------------------------------------------------

def test_la_capacidad_esta_declarada_como_io_con_su_efecto():
    cap = registro(recargar=True).buscar("plano.cuadro_en_pdf")
    assert cap.naturaleza == "io"
    assert cap.efectos == (ESCRIBE_FICHERO,)


def test_sin_autorizacion_no_escribe_el_pdf(tmp_path):
    cap = registro(recargar=True).buscar("plano.cuadro_en_pdf")
    with pytest.raises(EfectoNoAutorizado):
        cap.invocar({"ruta": "x.dxf", "ruta_destino": str(tmp_path / "x.pdf")})
    assert not (tmp_path / "x.pdf").exists()


def test_un_dxf_sin_cuadro_no_produce_un_pdf_vacio(tmp_path):
    """Un PDF con una tabla en blanco se lee como «no hay superficies», que es
    justo la lectura contraria a «no he podido calcularlas»."""
    origen = construir_dxf(tmp_path)
    destino = tmp_path / "cuadro.pdf"
    resultado = plano.cuadro_en_pdf(origen, str(destino))
    assert resultado["ok"] is False
    assert not destino.exists()


def test_el_pdf_no_puede_sobrescribir_el_dxf(tmp_path):
    origen = construir_dxf(tmp_path)
    resultado = plano.cuadro_en_pdf(origen, origen)
    assert resultado["ok"] is False
    assert resultado["error"] == "destino_es_el_origen"


def test_escribir_el_pdf_deja_el_fichero_en_su_sitio(tmp_path):
    destino = tmp_path / "cuadro.pdf"
    escribir_cuadro_pdf(DATOS, str(destino))
    assert destino.exists() and destino.read_bytes().startswith(b"%PDF")


# --- 6. Lo que enseñó el primer plano real --------------------------------
#
# Estos tres se escriben después de pasar `v2s.dxf` por el flujo completo. Los
# fixtures no podían destaparlos: sus etiquetas no llevan tildes y su geometría
# no tiene solapes.

def test_la_fila_se_rotula_como_la_escribio_el_arquitecto():
    """«Bano» no es una palabra, y este PDF se le enseña a un cliente.

    El `campo` es un identificador ASCII y sirve para programar; el rótulo sale
    de la etiqueta del propio cuadro del DXF, que es donde están las tildes.
    """
    datos = dict(DATOS)
    datos["celdas"] = [
        {"campo": "bano", "etiqueta": "BAÑO", "texto": "4,01 m²",
         "estado": "CALCULADO", "motivo": None},
        {"campo": "salon_cocina", "etiqueta": "SALÓN/COCINA", "texto": "21,90 m²",
         "estado": "CALCULADO", "motivo": None},
    ]
    contenido = texto_de(generar_cuadro_pdf(datos))
    assert "BAÑO" in contenido
    assert "SALÓN/COCINA" in contenido
    assert "Bano" not in contenido


def test_sin_etiqueta_se_repliega_al_identificador_en_vez_de_quedarse_en_blanco():
    """Una fila sin nombre es peor que una fila con un nombre feo."""
    datos = dict(DATOS)
    datos["celdas"] = [{"campo": "dormitorio_1", "texto": "12,72 m²",
                        "estado": "CALCULADO", "motivo": None}]
    assert "Dormitorio 1" in texto_de(generar_cuadro_pdf(datos))


def test_una_celda_bloqueada_se_lee_igual_en_el_pdf_que_en_el_dxf():
    """El DXF escribe «N/D» en ese hueco; el PDF que lo explica decía
    «BLOQUEADO». Dos vocabularios para la misma celda obligan al arquitecto a
    cotejarlos. El porqué sigue entero en las otras dos columnas."""
    datos = dict(DATOS)
    datos["celdas"] = [{"campo": "terraza_1", "etiqueta": "TERRAZA 1",
                        "texto": "BLOQUEADO", "estado": "BLOQUEADO",
                        "motivo": "hay dos piezas con esa etiqueta"}]
    contenido = texto_de(generar_cuadro_pdf(datos))
    assert "BLOQUEADO" not in contenido
    assert "N/D" in contenido
    assert "Ambiguo: hay que decidirlo" in contenido
    assert "hay dos piezas con esa etiqueta" in contenido
