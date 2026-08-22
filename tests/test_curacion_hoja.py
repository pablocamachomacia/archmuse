# -*- coding: utf-8 -*-
"""El flujo papel → ledger → YAML de `curacion/`: hoja, huellas y volcado.

Ejecutar:  pytest tests/test_curacion_hoja.py

PRD: `docs/prd/2026-08-22-corpus-firmado-dbsi3-evacuacion.md` §3 y §4
(T8, T9, T10). Corpus de prueba en tmp_path — nada nuevo en `tests/fixtures/`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from curacion import paquete as _paquete  # noqa: E402
from curacion.volcar_acta import firmar_desde_ledger  # noqa: E402
from normativa.firma import hash_de_contenido_firmado  # noqa: E402


def _doc_borrador() -> dict:
    return {
        "version": 1,
        "norma": {
            "concept_id": "es.prueba.dbsi.norma",
            "instance_id": "es.prueba.dbsi.norma@1",
            "ambito": "es",
            "literal": "La longitud no excede de 25 m.",
            "fuente": {
                "rango": "Real Decreto",
                "organismo": "Ministerio de Vivienda",
                "identificador_oficial": "RD 314/2006",
                "titulo": "Código Técnico de la Edificación",
                "boletin": "BOE-A-2006-5515",
            },
            "articulo": {"documento_basico": "DB-SI", "seccion": "SI 3",
                         "apartado": "3", "tabla": "3.1"},
            "vigencia": {"vigencia_desde": "2006-03-29"},
        },
        "reglas": [{
            "concept_id": "es.prueba.seguridad_incendio.longitud",
            "instance_id": "es.prueba.seguridad_incendio.longitud@1",
            "nombre": "Longitud máxima del recorrido",
            "estado": "BORRADOR",
            "materia": "seguridad_incendio",
            "tipo": "exigencia_cuantitativa",
            "patron": "UMBRAL_SIMPLE",
            "prioridad": "bloqueante",
            "nivel_de_conocimiento": 2,
            "aplicabilidad": {"ambito": "es", "usos": ["residencial"]},
            "parametro": {"ejes": ["caso"], "unidad": "m",
                          "repliegue": ["todos", "ninguno"],
                          "valores": [{"valor": 25, "caso": "general"}]},
            "vigencia": {"vigencia_desde": "2006-03-29"},
        }],
    }


def _montar(tmp_path: Path) -> tuple:
    """Un paquete de un borrador + su ledger con la decisión conforme."""
    carpeta = tmp_path / "estatal"
    carpeta.mkdir()
    (carpeta / "_paquete_dbsi3_prueba.yaml").write_text(
        yaml.safe_dump(_doc_borrador(), allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    filas = _paquete.cargar_paquete("_paquete_dbsi3_", carpeta)
    assert len(filas) == 1
    ledger = tmp_path / "actas_papel.jsonl"
    ledger.write_text(json.dumps({
        "tipo": "decision", "acta": "docs/curacion/actas/prueba.pdf",
        "paquete": "_paquete_dbsi3_", "regla_id": "R-01",
        "concept_id": filas[0].concept_id,
        "fichero": "_paquete_dbsi3_prueba.yaml",
        "huella_fila": filas[0].huella, "decision": "conforme",
        "correcciones": [],
        "validadores": [{"nombre": "V. Prueba", "rol": "arquitecto_colegiado",
                         "fecha": "2026-08-25",
                         "acta": "docs/curacion/actas/prueba.pdf"}],
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    return carpeta, ledger, filas


# --- El camino feliz: se firma, con hash y validado_por ----------------------

def test_volcar_firma_con_hash_y_validadores(tmp_path):
    carpeta, ledger, filas = _montar(tmp_path)
    resultado = firmar_desde_ledger("Pablo Camacho", "_paquete_dbsi3_",
                                    ledger, carpeta, fecha="2026-08-26")
    assert resultado["firmadas"] == ["dbsi3_evacuacion_prueba.yaml"]
    doc = yaml.safe_load((carpeta / "dbsi3_evacuacion_prueba.yaml")
                         .read_text(encoding="utf-8"))
    regla = doc["reglas"][0]
    assert regla["estado"] == "FIRMADA"
    firma = regla["firma"]
    assert firma["curador"] == "Pablo Camacho"
    assert firma["validado_por"][0]["rol"] == "arquitecto_colegiado"
    # La huella firmada coincide con la del borrador impreso: los metadatos de
    # flujo (estado, firma, tags) no entran en el hash, así que el papel y el
    # corpus hablan del mismo contenido.
    assert firma["hash_contenido"] == filas[0].huella
    assert firma["hash_contenido"] == hash_de_contenido_firmado(doc["norma"], regla)


# --- T8: si el borrador cambió tras imprimir, el volcado se niega ------------

def test_volcar_acta_rechaza_borrador_derivado(tmp_path):
    carpeta, ledger, _ = _montar(tmp_path)
    ruta = carpeta / "_paquete_dbsi3_prueba.yaml"
    doc = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    doc["reglas"][0]["parametro"]["valores"][0]["valor"] = 26  # tras imprimir
    ruta.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")

    resultado = firmar_desde_ledger("Pablo Camacho", "_paquete_dbsi3_",
                                    ledger, carpeta, fecha="2026-08-26")
    assert resultado["firmadas"] == []
    assert resultado["derivadas"], "el borrador derivado tenía que detectarse"
    assert "el papel manda" in resultado["derivadas"][0]
    assert not list(carpeta.glob("dbsi3_evacuacion_*.yaml")), \
        "no puede haberse escrito nada"


# --- T9: inmutable y reanudable ----------------------------------------------

def test_volcar_acta_es_inmutable_y_reanudable(tmp_path):
    carpeta, ledger, _ = _montar(tmp_path)
    primero = firmar_desde_ledger("Pablo Camacho", "_paquete_dbsi3_",
                                  ledger, carpeta, fecha="2026-08-26")
    assert primero["firmadas"] == ["dbsi3_evacuacion_prueba.yaml"]
    contenido = (carpeta / "dbsi3_evacuacion_prueba.yaml").read_bytes()

    segundo = firmar_desde_ledger("Pablo Camacho", "_paquete_dbsi3_",
                                  ledger, carpeta, fecha="2026-08-26")
    assert segundo["firmadas"] == []
    assert segundo["conflictos"] and "inmutable" in segundo["conflictos"][0]
    assert (carpeta / "dbsi3_evacuacion_prueba.yaml").read_bytes() == contenido, \
        "el fichero firmado no puede cambiar ni un byte"


# --- Corrección al margen: se firma el valor corregido, ledger con ambos -----

def test_correccion_al_margen_firma_el_valor_corregido(tmp_path):
    carpeta, ledger, filas = _montar(tmp_path)
    entrada = json.loads(ledger.read_text(encoding="utf-8"))
    entrada["decision"] = "corregida"
    entrada["correcciones"] = [{"campo": "parametro.valores[0].valor", "despues": 30}]
    ledger.write_text(json.dumps(entrada, ensure_ascii=False) + "\n", encoding="utf-8")

    resultado = firmar_desde_ledger("Pablo Camacho", "_paquete_dbsi3_",
                                    ledger, carpeta, fecha="2026-08-26")
    assert resultado["firmadas"] == ["dbsi3_evacuacion_prueba.yaml"]
    doc = yaml.safe_load((carpeta / "dbsi3_evacuacion_prueba.yaml")
                         .read_text(encoding="utf-8"))
    regla = doc["reglas"][0]
    assert regla["parametro"]["valores"][0]["valor"] == 30
    # El hash firmado es el del contenido CORREGIDO (ya no el del borrador)...
    assert regla["firma"]["hash_contenido"] == hash_de_contenido_firmado(
        doc["norma"], regla)
    assert regla["firma"]["hash_contenido"] != filas[0].huella
    # ...y el ledger conserva ambos valores (decisión de Pablo, 2026-08-22).
    lineas = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()]
    aplicadas = [l for l in lineas if l.get("tipo") == "correccion_aplicada"]
    assert aplicadas and aplicadas[0]["antes"] == 25 and aplicadas[0]["despues"] == 30


# --- T10: la hoja contiene todas las filas, con huella y F/L/M ---------------

def test_hoja_contiene_todas_las_filas_y_huellas(tmp_path, monkeypatch):
    carpeta, _, filas = _montar(tmp_path)
    from curacion import hoja_de_revision

    monkeypatch.setattr(_paquete, "CARPETA_CORPUS", carpeta)
    monkeypatch.setattr(hoja_de_revision, "cargar_paquete",
                        lambda prefijo=_paquete.PREFIJO_POR_DEFECTO:
                        _paquete.cargar_paquete(prefijo, carpeta))
    html = hoja_de_revision.generar_hoja("_paquete_dbsi3_")

    for fila in filas:
        assert fila.numero in html
        assert fila.huella_corta in html
    assert "DB-SI, SI 3, §3, tabla 3.1" in html
    assert html.count('class="checkbox"') == 3 * len(filas)  # F · L · M por fila
    assert "Anexo de literales" in html
    assert "La longitud no excede de 25 m." in html
    assert _paquete.huella_del_paquete(filas) in html
    assert "BORRADOR" in html
