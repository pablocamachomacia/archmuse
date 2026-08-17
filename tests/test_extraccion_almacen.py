"""Persistencia de candidatas (`extraccion/almacen.py`) — sin IA, sin red:
`ReglaCandidata`/`Señales` construidas a mano, como haría cualquier corrida
real después de `extraccion.pipeline.extraer()`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from extraccion import almacen  # noqa: E402
from extraccion.modelo import ReglaCandidata, Señales  # noqa: E402
from extraccion.pipeline import ResultadoExtraccion  # noqa: E402
from ingesta.modelo import DocumentoOficial  # noqa: E402


def _documento(hash_texto="hash-de-prueba"):
    return DocumentoOficial(
        identificador="DB-TEST", fuente="codigotecnico", titulo="Documento de prueba",
        organismo="Test", rango_codigo=None, rango_nombre=None, numero_oficial=None,
        fecha_publicacion=None, fecha_disposicion=None, fecha_actualizacion=None,
        url_oficial="https://example.invalid/db-test.pdf", url_xml="https://example.invalid/db-test.pdf",
        texto_crudo="texto", hash_texto=hash_texto, formato="pdf", bytes_crudos=b"pdf-bytes",
    )


def _candidata(confianza="Baja", revisar=True):
    señales = Señales(
        patron_en_catalogo_cerrado=True, materia_en_catalogo_cerrado=True,
        tipo_en_catalogo_cerrado=True, severidad_en_catalogo_cerrado=True,
        tipo_coherente_con_patron=True, cifras_verificadas_en_texto=True,
        segmento_correcto=True, pide_revision_la_propia_ia=revisar,
    )
    return ReglaCandidata(
        texto_original="El pasillo debe tener al menos 1.20 m de anchura.",
        documento="Documento de prueba", documento_identificador="DB-TEST",
        articulo="DB-TEST 1.1 Anchura de pasillos", apartado=None, version="hash-de-prueba",
        fecha=None, url_oficial="https://example.invalid/db-test.pdf", organismo="Test",
        tipo="exigencia_cuantitativa", patron="UMBRAL_SIMPLE", materia_sugerida="accesibilidad",
        severidad_sugerida="bloqueante", condicion_aplicacion=None, parametros=(),
        excepciones=(), referencias_internas=(), explicacion_tecnica="x", explicacion_interpretacion="y",
        nivel_confianza=confianza, revisar_manualmente=revisar,
        motivos_revision=("motivo de prueba",) if revisar else (), señales=señales,
    )


def test_guardar_escribe_un_jsonl_con_una_linea_por_candidata(tmp_path):
    doc = _documento()
    resultado = ResultadoExtraccion(segmentos_totales=2, candidatas=(_candidata(), _candidata("Alta", False)), avisos=())
    ruta = almacen.guardar(resultado, doc, raiz=tmp_path)
    assert ruta.exists()
    lineas = ruta.read_text(encoding="utf-8").strip().splitlines()
    assert len(lineas) == 2
    primero = json.loads(lineas[0])
    assert primero["documento_identificador"] == "DB-TEST"
    assert primero["nivel_confianza"] == "Baja"
    assert primero["lista_para_promocion"] is False


def test_guardar_es_idempotente_para_la_misma_version(tmp_path):
    doc = _documento()
    resultado = ResultadoExtraccion(segmentos_totales=1, candidatas=(_candidata(),), avisos=())
    ruta1 = almacen.guardar(resultado, doc, raiz=tmp_path)
    contenido1 = ruta1.read_text(encoding="utf-8")
    # Segunda corrida "distinta" (más candidatas) sobre la MISMA versión del
    # documento: no debe pisar el fichero ya guardado.
    resultado2 = ResultadoExtraccion(segmentos_totales=5, candidatas=(_candidata(), _candidata(), _candidata()), avisos=())
    ruta2 = almacen.guardar(resultado2, doc, raiz=tmp_path)
    assert ruta1 == ruta2
    assert ruta2.read_text(encoding="utf-8") == contenido1


def test_ledger_nunca_miente_cuando_el_fichero_ya_existia(tmp_path):
    """Regresión directa de un bug real encontrado en la corrida sobre
    DB-SI: una corrida pequeña (2 candidatas) seguida de la corrida real
    completa (25) sobre la MISMA versión del documento dejaba el `.jsonl`
    con solo 2 líneas, pero el ledger afirmaba 25 — porque tomaba las
    cifras de `resultado`, no del fichero. El ledger tiene que reflejar
    siempre lo que hay de verdad en disco."""
    doc = _documento()
    pequena = ResultadoExtraccion(segmentos_totales=1, candidatas=(_candidata(),), avisos=())
    almacen.guardar(pequena, doc, raiz=tmp_path)

    grande = ResultadoExtraccion(
        segmentos_totales=25,
        candidatas=tuple(_candidata() for _ in range(25)),
        avisos=(),
    )
    ruta = almacen.guardar(grande, doc, raiz=tmp_path)

    # El fichero sigue teniendo solo la candidata de la corrida pequeña...
    assert len(ruta.read_text(encoding="utf-8").strip().splitlines()) == 1
    # ...y el ledger tiene que decir exactamente eso, no 25.
    ledger, _ = almacen._rutas(tmp_path)
    ultimo_registro = json.loads(ledger.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert ultimo_registro["candidatas_generadas"] == 1
    assert ultimo_registro["ya_existia"] is True


def test_guardar_distinta_version_dan_ficheros_distintos(tmp_path):
    resultado = ResultadoExtraccion(segmentos_totales=1, candidatas=(_candidata(),), avisos=())
    ruta1 = almacen.guardar(resultado, _documento("hash-uno"), raiz=tmp_path)
    ruta2 = almacen.guardar(resultado, _documento("hash-dos"), raiz=tmp_path)
    assert ruta1 != ruta2


def test_guardar_registra_en_el_ledger(tmp_path):
    doc = _documento()
    resultado = ResultadoExtraccion(segmentos_totales=3, candidatas=(_candidata(), _candidata("Alta", False)), avisos=("un aviso",))
    almacen.guardar(resultado, doc, raiz=tmp_path)
    ledger, _ = almacen._rutas(tmp_path)
    registros = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()]
    assert len(registros) == 1
    r = registros[0]
    assert r["documento_identificador"] == "DB-TEST"
    assert r["candidatas_generadas"] == 2
    assert r["pendientes_revision"] == 1
    assert r["avisos"] == 1


def test_leer_devuelve_lista_vacia_si_no_existe(tmp_path):
    assert almacen.leer(tmp_path / "no-existe.jsonl") == []


def test_listar_ordenado(tmp_path):
    resultado = ResultadoExtraccion(segmentos_totales=1, candidatas=(_candidata(),), avisos=())
    almacen.guardar(resultado, _documento("hash-a"), raiz=tmp_path)
    almacen.guardar(resultado, _documento("hash-b"), raiz=tmp_path)
    assert len(almacen.listar(tmp_path)) == 2
