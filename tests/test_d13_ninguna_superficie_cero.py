# -*- coding: utf-8 -*-
"""`D-13` · Un `0,00 m²` no es nunca una superficie válida de estancia.

**Decisión firmada por Pablo el 2026-09-13**, que deroga `C-4`. Ninguna
habitación mide cero, así que un cero escrito en un cuadro es siempre una cifra
que ArchMuse no ha medido — `C-4` y `C-11` a la vez.

**El fallo, verificado en AutoCAD 2027 el 2026-09-13.** El cuadro del
arquitecto tenía filas `pasillo` y `vestibulo`; ese estudio mete el pasillo en
el salón y el plano no dibuja ninguno. ArchMuse escribió `0,00 m²` en las dos.
Origen medido: los tres constructores de `CERO_REAL` de `cuadro_superficies.py`
y `condicionar_ceros`, que sobre una medición limpia los dejaba pasar.

**`D-15` va aquí porque es el mismo invariante por la otra puerta.** La web
nunca pasó por `condicionar_ceros`: escribía ceros incluso con la medición
sucia.

Todo contra `tests/fixtures/cuadro_sintetico/`, que no es de nadie y corre en CI.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sys

import pytest
from shapely.geometry import Point, Polygon

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import cuadro_superficies as cs  # noqa: E402
from analyzer import evaluator, parser  # noqa: E402
from analyzer.geometria_recibida import payload_desde_dxf  # noqa: E402

CARPETA = os.path.join(RAIZ, "tests", "fixtures", "cuadro_sintetico")
FIXTURE = os.path.join(CARPETA, "cuadro_sintetico.dxf")

#: Un cero con forma de superficie: `0,00 m²`, `0.00m2`, `0 m²`. No casa con
#: `10,00 m²` ni con `20,05 m²`.
_CERO = re.compile(r"(?<![\d.,])0+(?:[.,]0+)?\s*m", re.IGNORECASE)


def _es_cero(texto: str) -> bool:
    return bool(_CERO.search(texto or ""))


def _generador():
    spec = importlib.util.spec_from_file_location(
        "generar_cuadro_sintetico", os.path.join(CARPETA, "generar.py"))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _celdas_del_cuadro_del_arquitecto():
    """Las celdas tal como las manda el `.lsp`: la rejilla entera, vacías incluidas."""
    gen = _generador()
    textos = {(f, c): t for f, c, t in gen.CUADRO}
    n_filas = 1 + max(f for f, _c, _t in gen.CUADRO)
    return [[f, c, textos.get((f, c), "")] for f in range(n_filas) for c in range(4)]


def _payload_sin_trastero():
    """El fixture sin el trastero: **medición limpia**, que es exactamente cuando
    `C-4` dejaba pasar el cero. Con el trastero la medición está sucia y `C-4`
    lo habría tapado por casualidad."""
    payload = payload_desde_dxf(FIXTURE)
    donde = next(t for t in payload["textos"] if t["texto"] == "Trastero")
    punto = Point(donde["x"], donde["y"])
    payload["textos"] = [t for t in payload["textos"] if t is not donde]
    payload["recintos"] = [r for r in payload["recintos"]
                           if not Polygon(r["vertices"]).contains(punto)]
    return payload


@pytest.fixture(scope="module")
def cliente():
    import app as srv

    return srv.app.test_client()


def test_d13_por_el_comando_ninguna_celda_del_cuadro_dice_cero(cliente):
    cuerpo = _payload_sin_trastero()
    cuerpo["cuadros"] = [{"celdas": _celdas_del_cuadro_del_arquitecto()}]

    respuesta = cliente.post("/api/medicion-geometria", json=cuerpo)

    assert respuesta.status_code == 200, respuesta.get_data(as_text=True)[:500]
    reparto = respuesta.get_json()["repartos"][0]
    assert reparto.get("ok", True), reparto
    assert reparto["medicion_limpia"], "el test ha dejado de reproducir el caso limpio"
    celdas = reparto["cuadro_a_dibujar"]["celdas"]
    con_cero = [(c["fila"], c["columna"], c["texto"]) for c in celdas if _es_cero(c["texto"])]
    assert not con_cero, "el cuadro de ArchMuse escribe superficies cero: %s" % con_cero


def test_d15_por_la_web_no_se_escribe_ningun_cero_ni_con_la_medicion_sucia(tmp_path):
    from analyzer.cuadro_superficies_export import exportar_cuadro_relleno

    destino = tmp_path / "exportado.dxf"
    exportar_cuadro_relleno(FIXTURE, str(destino))

    def textos(ruta):
        doc = parser.load_document(ruta)
        return [(e.dxf.layer, e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text)
                for e in doc.modelspace().query("MTEXT TEXT")]

    anadidos = [t for t in textos(str(destino)) if t not in textos(FIXTURE)]
    assert anadidos, "la exportación no ha escrito nada: el test no prueba nada"
    con_cero = [t for t in anadidos if _es_cero(t[1])]
    assert not con_cero, "la vía web escribe superficies cero: %s" % con_cero


def test_d13_el_calculo_del_cuadro_no_produce_ningun_cero():
    """El invariante en la fuente, sin pasar por ninguna de las dos vías: lo que
    cualquier consumidor futuro reciba ya viene sin ceros."""
    doc = parser.load_document(FIXTURE)
    plano = parser.leer_plano(doc)
    unidad = evaluator.evaluate_advanced(plano.rooms, plano.unit_labels).units[0]
    cuadro = cs.detectar_cuadros_superficies(doc)[0]

    resultado = cs.calcular_relleno_cuadro(unidad, cuadro, unidad.rooms)

    con_cero = [(r.campo, r.texto) for r in resultado if _es_cero(r.texto)]
    assert not con_cero, con_cero


def test_el_detector_de_ceros_no_confunde_cifras_reales():
    assert _es_cero("0,00 m²") and _es_cero("0.00m2") and _es_cero("0 m²")
    assert not _es_cero("10,00 m²") and not _es_cero("20,05 m²") and not _es_cero("")


def test_c5_sigue_en_pie_una_terraza_para_dos_huecos_deja_los_dos_sin_cifra():
    """**`C-5` no se rompe con `D-13`: se reutiliza** (orden de Pablo, 2026-09-13).

    El cuadro del fixture pide `terraza 1` y `terraza 2` y el plano dibuja una
    sola terraza. Las dos celdas se quedan sin cifra, con el MISMO motivo, y
    ninguna dice cero: ni se reparte por orden, ni una va a 4,50 y la otra a 0,00.
    """
    doc = parser.load_document(FIXTURE)
    plano = parser.leer_plano(doc)
    unidad = evaluator.evaluate_advanced(plano.rooms, plano.unit_labels).units[0]
    cuadro = cs.detectar_cuadros_superficies(doc)[0]

    por_campo = {r.campo: r for r in cs.calcular_relleno_cuadro(unidad, cuadro, unidad.rooms)}

    t1, t2 = por_campo["terraza_1"], por_campo["terraza_2"]
    assert t1.estado == t2.estado == cs.BLOQUEADO
    assert not t1.escribir and not t2.escribir
    assert t1.motivo == t2.motivo and "terraza" in (t1.motivo or "").lower()
    assert not _es_cero(t1.texto) and not _es_cero(t2.texto)
    assert cs.MOTIVO_GUARDIAN_D13 not in (t1.motivo, t2.motivo)


def test_el_guardian_de_d8_no_ha_tenido_que_actuar_en_el_fixture():
    """El guardián no calla: si alguna vez tapa un cero, lo dice su motivo. Que
    no aparezca en ninguna celda es la prueba de que ningún cálculo lo produce."""
    doc = parser.load_document(FIXTURE)
    plano = parser.leer_plano(doc)
    unidad = evaluator.evaluate_advanced(plano.rooms, plano.unit_labels).units[0]
    cuadro = cs.detectar_cuadros_superficies(doc)[0]
    resultado = cs.calcular_relleno_cuadro(unidad, cuadro, unidad.rooms)
    assert not [r.campo for r in resultado if r.motivo == cs.MOTIVO_GUARDIAN_D13]
