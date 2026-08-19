# -*- coding: utf-8 -*-
"""TL-1 — las capacidades de geometría del primer vertical, con su golden.

Ejecutar:  pytest tests/test_agente_plano.py

Estas tres capacidades son lo que convierte «rellena el cuadro de superficies
de este DXF» en trabajo real. Lo que se fija aquí:

1. **Determinismo.** Misma entrada, misma salida, siempre. La salida
   congelada vive en `G11_capacidades.json` con la de todas las demás
   capacidades (`tests/test_agente_goldens.py`, tarea TL-4); aquí se comprueba
   que dos ejecuciones seguidas coinciden, que es la mitad que un golden no
   puede ver.
2. **Cuando no se sabe, se pregunta.** Un DXF cuya unidad no se puede
   determinar devuelve `ok: false` **con la pregunta**, nunca una suposición.
   Un plano en milímetros leído como metros cumple todas las superficies
   mínimas y sale con una puntuación alta y creíble: es el peor defecto que ha
   tenido este repositorio y no puede volver por la puerta del agente.
3. **Nada se escribe.** Las tres son de sólo lectura; el DXF de entrada
   conserva su sha256 byte a byte. La escritura es `TL-2`, con su propio PRD.

El DXF de prueba se construye en memoria y se guarda en un temporal, así que
no hace falta ni red ni el `v2s.dxf` real. El cuadro de superficies completo
sí lo necesita —un `ACAD_TABLE` no se sintetiza de forma realista— y por eso
esa parte se salta con motivo si no está `ARCHMUSE_DXF_V2S`, mismo criterio
que `tests/test_cuadro_superficies.py`.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import ezdxf  # noqa: E402

from agente.herramientas import plano  # noqa: E402
from agente.registro import registro  # noqa: E402
from analyzer import parser  # noqa: E402

DXF_V2S = os.environ.get("ARCHMUSE_DXF_V2S", "")

#: Cuatro piezas con superficies redondas: 20, 9, 12 y 4 m². Si el golden
#: cambia, la diferencia se lee a simple vista.
PIEZAS = (
    ("Salón", (0.0, 0.0), (5.0, 4.0)),
    ("Cocina", (5.0, 0.0), (8.0, 3.0)),
    ("Dormitorio 1", (0.0, 4.0), (4.0, 7.0)),
    ("Baño", (5.0, 3.0), (7.0, 5.0)),
)


def _construir_dxf(ruta: Path, insunits: int = 6, escala: float = 1.0) -> Path:
    """Un piso mínimo, en la capa heredada, con su etiqueta de vivienda.

    `insunits=6` son metros; `escala` multiplica las coordenadas para poder
    fabricar el mismo piso dibujado en otra unidad sin declararla.
    """
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = insunits
    doc.layers.add(parser.AREA_LAYER)
    msp = doc.modelspace()
    for etiqueta, (x0, y0), (x1, y1) in PIEZAS:
        p = [(x0 * escala, y0 * escala), (x1 * escala, y0 * escala),
             (x1 * escala, y1 * escala), (x0 * escala, y1 * escala)]
        msp.add_lwpolyline(p, close=True, dxfattribs={"layer": parser.AREA_LAYER})
        msp.add_mtext(etiqueta, dxfattribs={"layer": parser.AREA_LAYER}).set_location(
            ((x0 + x1) / 2.0 * escala, (y0 + y1) / 2.0 * escala))
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.AREA_LAYER}).set_location(
        (-3.0 * escala, 2.0 * escala))
    doc.saveas(str(ruta))
    return ruta


@pytest.fixture(scope="module")
def dxf(tmp_path_factory) -> Path:
    return _construir_dxf(tmp_path_factory.mktemp("plano") / "piso.dxf")


# --- 1. Determinismo -------------------------------------------------------
#
# La salida congelada de estas tres capacidades vive en UN solo sitio,
# `tests/fixtures/golden/G11_capacidades.json`, junto con la de todas las
# demás y con el test de política que exige que ninguna determinista entre sin
# él (`tests/test_agente_goldens.py`, tarea TL-4). Duplicar aquí un segundo
# golden obligaría a recapturar dos ficheros por cada cambio, que es la forma
# más rápida de que uno de los dos deje de mirarse.

def test_dos_invocaciones_seguidas_dan_lo_mismo(dxf):
    """Determinismo, comprobado en el propio proceso: sin esto, el golden sólo
    diría que la primera ejecución fue igual a la de otro día."""
    for capacidad in (plano.leer_dxf, plano.superficie_util):
        assert capacidad(str(dxf)) == capacidad(str(dxf))


# --- 2. Lo que ve el arquitecto --------------------------------------------

def test_las_superficies_salen_en_metros_cuadrados(dxf):
    areas = {r["etiqueta"]: r["area_m2"] for r in plano.leer_dxf(str(dxf))["recintos"]}
    assert areas == {"Salón": 20.0, "Cocina": 9.0, "Dormitorio 1": 12.0, "Baño": 4.0}
    assert plano.leer_dxf(str(dxf))["superficie_util_total_m2"] == 45.0


def test_la_superficie_util_trae_de_que_recintos_sale(dxf):
    """Sin la procedencia, la cifra es un número que hay que creerse."""
    vivienda = plano.superficie_util(str(dxf))["viviendas"][0]
    assert vivienda["valor_m2"] == 45.0
    assert any("Salón" in p for p in vivienda["procedencia"])


# --- 3. Cuando no se sabe, se pregunta -------------------------------------

def test_sin_unidad_declarada_ni_deducible_se_pregunta(tmp_path):
    """EL PEOR DEFECTO QUE HA TENIDO ESTE REPOSITORIO, cerrado por la capacidad.

    Un plano sin `$INSUNITS` y con estancias de tamaño ambiguo no se lee «en
    metros por si acaso»: se devuelve `ok: false` con la pregunta. La
    alternativa —suponer— produce un análisis que cumple todos los mínimos y
    parece impecable.
    """
    # Escala 0,1: ninguna unidad métrica explica estancias de 0,2 m² a 0,45 m²,
    # así que el tamaño no decide y la cabecera no dice nada.
    ruta = _construir_dxf(tmp_path / "sin_unidad.dxf", insunits=0, escala=0.1)
    resultado = plano.leer_dxf(str(ruta))
    assert resultado["ok"] is False
    assert resultado["error"] == "escala_indeterminada"
    assert resultado["pregunta"].strip()


def test_una_unidad_deducible_sin_ambiguedad_no_interrumpe_al_arquitecto(tmp_path):
    """El reverso, y también importa: preguntar cuando NO hace falta es la
    forma de que el arquitecto deje de leer las preguntas.

    Un plano dibujado en milímetros y sin cabecera sólo admite una lectura por
    el tamaño de sus estancias, así que se sigue — y las superficies salen en
    metros, no multiplicadas por un millón.
    """
    ruta = _construir_dxf(tmp_path / "en_mm_deducible.dxf", insunits=0, escala=1000.0)
    resultado = plano.leer_dxf(str(ruta))
    assert resultado["ok"] is True
    assert resultado["escala"]["origen"] == "plausibilidad"
    assert resultado["superficie_util_total_m2"] == 45.0


def test_con_la_escala_confirmada_por_el_arquitecto_ya_se_puede_leer(tmp_path):
    """La pregunta tiene que servir para algo: contestarla desbloquea."""
    ruta = _construir_dxf(tmp_path / "ambiguo.dxf", insunits=0, escala=0.1)
    resultado = plano.leer_dxf(str(ruta), factor_escala=10.0)
    assert resultado["ok"] is True
    assert resultado["superficie_util_total_m2"] == 45.0


def test_un_fichero_que_no_existe_no_revienta_ni_miente():
    resultado = plano.leer_dxf("no_existe_en_ningun_disco.dxf")
    assert resultado["ok"] is False
    assert resultado["error"] == "fichero_no_encontrado"
    assert "pregunta" in resultado


def test_un_dxf_sin_cuadro_lo_dice_en_vez_de_inventarse_uno(dxf):
    resultado = plano.cuadro_de_superficies(str(dxf))
    assert resultado["ok"] is False
    assert resultado["error"] == "cuadro_no_calculable"
    assert "ACAD_TABLE" in resultado["detalle"] or "cuadro" in resultado["detalle"].lower()


# --- 3b. El bucle se cierra: la pregunta tiene respuesta -------------------

def test_lo_que_declara_el_arquitecto_llega_al_calculo(dxf, monkeypatch):
    """Sin esto, una celda BLOQUEADA lo estaría para siempre.

    Los datos que faltan —el espesor de muro, cuántas viviendas de este tipo
    hay, qué pieza es cada espacio exterior— **no están en el dibujo**: están
    en la cabeza del arquitecto. Una capacidad que sólo sabe decir «no puedo»
    deja el cuadro a medias para siempre.
    """
    vistas = {}

    def espia(ruta, respuestas=None):
        vistas["respuestas"] = respuestas
        return [], []

    monkeypatch.setattr("analyzer.cuadro_superficies_export.obtener_estado_cuadro", espia)
    declarado = [{"tipo": "numerico", "campo": "numero_unidades", "valor": 8}]
    plano.cuadro_de_superficies(str(dxf), respuestas=declarado)
    assert vistas["respuestas"] == declarado


def test_sin_respuestas_no_se_le_pasa_una_lista_vacia_como_si_fueran_respuestas(dxf, monkeypatch):
    """`[]` y `None` no significan lo mismo para `obtener_estado_cuadro`, y
    confundirlos cambiaría el camino que toma."""
    vistas = {}

    def espia(ruta, respuestas=None):
        vistas["respuestas"] = respuestas
        return [], []

    monkeypatch.setattr("analyzer.cuadro_superficies_export.obtener_estado_cuadro", espia)
    plano.cuadro_de_superficies(str(dxf))
    assert vistas["respuestas"] is None
    plano.cuadro_de_superficies(str(dxf), respuestas=[])
    assert vistas["respuestas"] is None


# --- 4. Ninguna de las tres escribe nada -----------------------------------

def test_el_dxf_de_entrada_conserva_su_sha256(dxf):
    """Es la frase que permite que un arquitecto pruebe esto la primera vez.

    Verificada byte a byte, no prometida en un docstring.
    """
    antes = hashlib.sha256(dxf.read_bytes()).hexdigest()
    plano.leer_dxf(str(dxf))
    plano.superficie_util(str(dxf))
    plano.cuadro_de_superficies(str(dxf))
    # Y la que sí escribe, escribe **aparte**: el original tampoco se mueve.
    plano.escribir_cuadro(str(dxf), str(dxf.parent / "copia_de_prueba.dxf"))
    assert hashlib.sha256(dxf.read_bytes()).hexdigest() == antes


def test_solo_declaran_efectos_las_que_escriben():
    """Declarar un efecto que no se tiene sería tan malo como lo contrario: el
    portero pediría una autorización que no hace falta, y el arquitecto
    aprendería a conceder autorizaciones sin leerlas.

    Las tres de lectura no tienen ninguno; las dos que entregan un fichero
    —el DXF relleno (`TL-2`) y el PDF que lo explica (`DOC-2`)— tienen
    exactamente uno cada una, y su test propio está en
    `tests/test_agente_escritura.py`.
    """
    con_efectos = {c.id: c.efectos for c in plano.CAPACIDADES if c.efectos}
    assert con_efectos == {
        "plano.escribir_cuadro": ("escribe_fichero",),
        "plano.cuadro_en_pdf": ("escribe_fichero",),
    }


# --- 5. Están en el registro y con el tamaño que C4 permite ---------------

def test_las_capacidades_del_vertical_estan_en_el_registro():
    ids = set(registro(recargar=True).ids())
    assert {"plano.leer_dxf", "plano.cuadro_de_superficies",
            "plano.superficie_util", "plano.escribir_cuadro"} <= ids


def test_el_registro_sigue_dentro_del_tamano_que_C4_permite():
    """C4: cobertura antes que catálogo. Entre 8 y 12 capacidades auditadas al
    cerrar el MVP, no cientos. Este test es el que hace que ese número sea una
    decisión y no una deriva."""
    # GUARDIAN DE DECISION: C4
    assert 6 <= len(registro(recargar=True)) <= 12


# --- 6. El cuadro completo, contra el DXF real ---------------------------

@pytest.mark.skipif(not DXF_V2S, reason="define ARCHMUSE_DXF_V2S para probar el cuadro real")
def test_el_cuadro_real_se_calcula_con_sus_celdas_y_sus_preguntas():
    """Un `ACAD_TABLE` no se sintetiza de forma realista, así que esta parte
    depende del plano de cliente. Sin él se salta con motivo, no falla."""
    resultado = plano.cuadro_de_superficies(DXF_V2S)
    assert resultado["ok"] is True
    assert len(resultado["celdas"]) == 18
    assert resultado["preguntas_pendientes"], "v2s.dxf tiene celdas que exigen preguntar"
    assert set(resultado["recuento_por_estado"]) <= {
        "CALCULADO", "CERO_REAL", "NO_DISPONIBLE", "BLOQUEADO"}


@pytest.mark.skipif(not DXF_V2S, reason="define ARCHMUSE_DXF_V2S para probar el cuadro real")
def test_contestar_una_pregunta_resuelve_su_celda_y_deja_dicho_quien_lo_dijo():
    """La procedencia es la mitad del valor: «lo calculó ArchMuse» y «lo
    declaró el arquitecto» no valen lo mismo en un acta, y atribuirse lo
    segundo sería apropiarse de un dato ajeno."""
    antes = plano.cuadro_de_superficies(DXF_V2S)
    numericas = [p for p in antes["preguntas_pendientes"] if p["tipo"] == "numerico"]
    assert numericas, "v2s.dxf tiene preguntas numéricas pendientes"

    campo = numericas[0]["campos"][0]
    despues = plano.cuadro_de_superficies(
        DXF_V2S, respuestas=[{"tipo": "numerico", "campo": campo, "valor": 65.4}])

    celda = next(c for c in despues["celdas"] if c["campo"] == campo)
    assert celda["estado"] == "CALCULADO"
    assert celda["declarado_por_usuario"] is True
    assert campo in despues["celdas_declaradas_por_el_arquitecto"]
    assert campo not in despues["celdas_sin_resolver"]
