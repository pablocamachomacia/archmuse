# -*- coding: utf-8 -*-
"""El flujo de revisión EN PANTALLA de `curacion/`: hoja, acta JSON y volcado.

Ejecutar:  pytest tests/test_curacion_hoja.py

PRD: `docs/prd/2026-08-22-corpus-firmado-dbsi3-evacuacion.md` §3 y §4, con el
cambio de medio del 22-08 (revisión en pantalla, opción A de trazabilidad):
el acta es el JSON que descarga «Guardar revisión», su integridad la sella
`hash_revision` (SHA-256 del contenido canónico) y la regla «el acta manda»
se conserva: firmar exige que la huella del borrador coincida con la del acta.

Corpus de prueba en tmp_path — nada nuevo en `tests/fixtures/`.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from curacion import paquete as _paquete  # noqa: E402
from curacion.volcar_acta import (  # noqa: E402
    firmar_desde_ledger, ingerir_acta, serializacion_canonica_acta,
)
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
            "explicacion_tecnica": "La longitud no excede de 25 m.",
            "vigencia": {"vigencia_desde": "2006-03-29"},
        }],
    }


def _acta(filas, validador=None, con_hash=True) -> dict:
    carga = {
        "tipo": "revision_corpus",
        "paquete": "dbsi3_evacuacion_p1",
        "generada": "2026-08-23",
        "documento_sha256": None,
        "huella_paquete": "irrelevante-para-estas-pruebas",
        "validador": validador or {"nombre": "V. Prueba",
                                   "colegiatura": "COA 0000",
                                   "rol": "arquitecto_colegiado",
                                   "fecha": "2026-08-25"},
        "declaracion_aceptada": True,
        "filas": filas,
    }
    if con_hash:
        carga["hash_revision"] = hashlib.sha256(
            serializacion_canonica_acta(carga).encode("utf-8")).hexdigest()
    return carga


def _montar(tmp_path: Path, fila_extra=None):
    """Un paquete de un borrador + su acta JSON con la fila conforme."""
    carpeta = tmp_path / "estatal"
    carpeta.mkdir()
    (carpeta / "_paquete_dbsi3_prueba.yaml").write_text(
        yaml.safe_dump(_doc_borrador(), allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    filas = _paquete.cargar_paquete("_paquete_dbsi3_", carpeta)
    assert len(filas) == 1
    fila_acta = {"numero": "R-01", "concept_id": filas[0].concept_id,
                 "huella_fila": filas[0].huella, "f": True, "l": True,
                 "m": True, "conforme": True, "correccion": "",
                 "excluida": False}
    if fila_extra:
        fila_acta.update(fila_extra)
    ruta_acta = tmp_path / "dbsi3_evacuacion_p1.prueba.acta.json"
    ruta_acta.write_text(json.dumps(_acta([fila_acta]), ensure_ascii=False,
                                    indent=2), encoding="utf-8")
    ledger = tmp_path / "actas_papel.jsonl"
    return carpeta, ledger, filas, ruta_acta


# --- El camino feliz: acta JSON → ledger → firma con validado_por ------------

def test_flujo_completo_desde_acta_json(tmp_path):
    carpeta, ledger, filas, ruta_acta = _montar(tmp_path)
    recuento = ingerir_acta(ruta_acta, "_paquete_dbsi3_", ledger)
    assert recuento["conforme"] == 1

    resultado = firmar_desde_ledger("Pablo Camacho", "_paquete_dbsi3_",
                                    ledger, carpeta, fecha="2026-08-26")
    assert resultado["firmadas"] == ["dbsi3_evacuacion_prueba.yaml"]
    doc = yaml.safe_load((carpeta / "dbsi3_evacuacion_prueba.yaml")
                         .read_text(encoding="utf-8"))
    regla = doc["reglas"][0]
    assert regla["estado"] == "FIRMADA"
    firma = regla["firma"]
    assert firma["curador"] == "Pablo Camacho"
    assert firma["validado_por"][0]["nombre"] == "V. Prueba"
    assert firma["validado_por"][0]["acta"].endswith(".acta.json")
    # La huella firmada coincide con la del borrador que la hoja embebió: los
    # metadatos de flujo no entran en el hash, así que el acta y el corpus
    # hablan del mismo contenido.
    assert firma["hash_contenido"] == filas[0].huella
    assert firma["hash_contenido"] == hash_de_contenido_firmado(doc["norma"], regla)


# --- Un acta editada tras guardarse se rechaza -------------------------------

def test_acta_editada_se_rechaza(tmp_path):
    import pytest

    _carpeta, ledger, _filas, ruta_acta = _montar(tmp_path)
    carga = json.loads(ruta_acta.read_text(encoding="utf-8"))
    carga["filas"][0]["conforme"] = False  # edición posterior al guardado
    ruta_acta.write_text(json.dumps(carga, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(SystemExit, match="hash_revision no coincide"):
        ingerir_acta(ruta_acta, "_paquete_dbsi3_", ledger)


# --- T8: si el borrador cambió tras generar la hoja, firmar se niega ---------

def test_firmar_rechaza_borrador_derivado(tmp_path):
    carpeta, ledger, _filas, ruta_acta = _montar(tmp_path)
    ingerir_acta(ruta_acta, "_paquete_dbsi3_", ledger)

    ruta = carpeta / "_paquete_dbsi3_prueba.yaml"
    doc = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    doc["reglas"][0]["parametro"]["valores"][0]["valor"] = 26  # tras la hoja
    ruta.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")

    resultado = firmar_desde_ledger("Pablo Camacho", "_paquete_dbsi3_",
                                    ledger, carpeta, fecha="2026-08-26")
    assert resultado["firmadas"] == []
    assert resultado["derivadas"] and "el acta manda" in resultado["derivadas"][0]
    assert not list(carpeta.glob("dbsi3_evacuacion_*.yaml"))


# --- T9: inmutable y reanudable ----------------------------------------------

def test_volcado_inmutable_y_reanudable(tmp_path):
    carpeta, ledger, _filas, ruta_acta = _montar(tmp_path)
    assert ingerir_acta(ruta_acta, "_paquete_dbsi3_", ledger)["conforme"] == 1
    # Reingerir el mismo acta no duplica decisiones.
    assert ingerir_acta(ruta_acta, "_paquete_dbsi3_", ledger)["ya_ingeridas"] == 1

    primero = firmar_desde_ledger("Pablo Camacho", "_paquete_dbsi3_",
                                  ledger, carpeta, fecha="2026-08-26")
    assert primero["firmadas"] == ["dbsi3_evacuacion_prueba.yaml"]
    contenido = (carpeta / "dbsi3_evacuacion_prueba.yaml").read_bytes()

    segundo = firmar_desde_ledger("Pablo Camacho", "_paquete_dbsi3_",
                                  ledger, carpeta, fecha="2026-08-26")
    assert segundo["firmadas"] == []
    assert segundo["conflictos"] and "inmutable" in segundo["conflictos"][0]
    assert (carpeta / "dbsi3_evacuacion_prueba.yaml").read_bytes() == contenido


# --- Corrección en pantalla: texto libre → traducción → valor corregido ------

def test_correccion_en_pantalla_se_traduce_y_firma(tmp_path):
    carpeta, ledger, filas, ruta_acta = _montar(
        tmp_path, {"conforme": False, "f": True, "l": True, "m": False,
                   "correccion": "El valor general debe ser 30 m, no 25 m."})
    traducciones = []

    def traducir(concept_id, texto):
        traducciones.append((concept_id, texto))
        return [{"campo": "parametro.valores[0].valor", "despues": 30}]

    assert ingerir_acta(ruta_acta, "_paquete_dbsi3_", ledger,
                        traducir=traducir)["corregida"] == 1
    assert traducciones and "30 m" in traducciones[0][1]

    resultado = firmar_desde_ledger("Pablo Camacho", "_paquete_dbsi3_",
                                    ledger, carpeta, fecha="2026-08-26")
    assert resultado["firmadas"] == ["dbsi3_evacuacion_prueba.yaml"]
    doc = yaml.safe_load((carpeta / "dbsi3_evacuacion_prueba.yaml")
                         .read_text(encoding="utf-8"))
    regla = doc["reglas"][0]
    assert regla["parametro"]["valores"][0]["valor"] == 30
    assert regla["firma"]["hash_contenido"] == hash_de_contenido_firmado(
        doc["norma"], regla)
    assert regla["firma"]["hash_contenido"] != filas[0].huella
    # El ledger conserva el texto del validador Y ambos valores.
    lineas = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()]
    decision = next(l for l in lineas if l.get("tipo") == "decision")
    assert "30 m" in decision["correccion_texto"]
    aplicada = next(l for l in lineas if l.get("tipo") == "correccion_aplicada")
    assert aplicada["antes"] == 25 and aplicada["despues"] == 30


def test_correccion_sin_traducir_bloquea_la_firma(tmp_path):
    carpeta, ledger, _filas, ruta_acta = _montar(
        tmp_path, {"conforme": False, "correccion": "Revisar este valor."})
    ingerir_acta(ruta_acta, "_paquete_dbsi3_", ledger)  # sin traducir

    resultado = firmar_desde_ledger("Pablo Camacho", "_paquete_dbsi3_",
                                    ledger, carpeta, fecha="2026-08-26")
    assert resultado["firmadas"] == []
    assert resultado["bloqueadas"] and "sin traducir" in resultado["bloqueadas"][0]


# --- Fusión de dos validadores: una exclusión veta ---------------------------

def test_exclusion_de_un_validador_veta_la_firma(tmp_path):
    carpeta, ledger, filas, ruta_acta = _montar(tmp_path)
    ingerir_acta(ruta_acta, "_paquete_dbsi3_", ledger)

    segunda = _acta([{"numero": "R-01", "concept_id": filas[0].concept_id,
                      "huella_fila": filas[0].huella, "f": False, "l": False,
                      "m": False, "conforme": False, "correccion": "",
                      "excluida": True}],
                    validador={"nombre": "Otra Validadora",
                               "rol": "experto_normativo",
                               "fecha": "2026-08-25"})
    ruta2 = tmp_path / "dbsi3_evacuacion_p1.otra.acta.json"
    ruta2.write_text(json.dumps(segunda, ensure_ascii=False), encoding="utf-8")
    ingerir_acta(ruta2, "_paquete_dbsi3_", ledger)

    resultado = firmar_desde_ledger("Pablo Camacho", "_paquete_dbsi3_",
                                    ledger, carpeta, fecha="2026-08-26")
    assert resultado["firmadas"] == []
    assert resultado["bloqueadas"] and "excluida" in resultado["bloqueadas"][0]


# --- T10: la hoja en pantalla es interactiva y no enseña la maquinaria -------

def test_hoja_interactiva_completa(tmp_path, monkeypatch):
    carpeta, _ledger, filas, _acta_ = _montar(tmp_path)
    from curacion import hoja_de_revision

    monkeypatch.setattr(hoja_de_revision, "cargar_paquete",
                        lambda prefijo=_paquete.PREFIJO_POR_DEFECTO:
                        _paquete.cargar_paquete(prefijo, carpeta))
    html = hoja_de_revision.generar_hoja("_paquete_dbsi3_")

    assert html.count("<section") == len(filas)
    # 4 casillas por regla (F, L, M, excluir) + 1 de la declaración.
    assert html.count('type="checkbox"') == 4 * len(filas) + 1
    assert html.count("<textarea") == len(filas)
    assert 'id="guardar"' in html and "Guardar revisión" in html
    # La huella viaja en el bloque de datos, no en la vista.
    assert filas[0].huella in html
    import re
    visible = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    assert not re.search(r"[0-9a-f]{10}", visible), "hex en la vista"
    assert "el acta de esta sesión" in html


def test_hoja_p1_es_presentable():
    """Los criterios de Pablo del 22-08 siguen vigentes con el medio nuevo:
    6 reglas, español de arquitecto, casos tabulados, sin claves del YAML ni
    hex a la vista, F·L·M explicadas donde se marcan. Contra el paquete REAL."""
    import re

    from curacion import hoja_de_revision
    from curacion.paquete import SELECCION_P1

    html = hoja_de_revision.generar_hoja(seleccion=SELECCION_P1)

    assert html.count("<section") == 6
    assert "R-06" in html and "R-07" not in html
    assert html.index("Longitud máxima de los recorridos") < html.index("R-02")

    visible = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    for prohibida in ("condicion:", "por_ciento", "numero_salidas",
                      "magnitud:", "_paquete_", ".yaml", "m2_por_persona"):
        assert prohibida not in visible, prohibida
    assert not re.search(r"[0-9a-f]{10}", visible), "hex en la vista"

    for cifra in ("25 m", "35 m", "50 m", "75 m", "100 personas",
                  "500 personas", "0,80 m", "1,00 m", "0,60 m", "1,23 m",
                  "28 m", "10 m", "25%"):
        assert cifra in html, cifra

    # F · L · M explicadas junto a las casillas y en la leyenda.
    for explicacion in ("fiel al literal", "referencia exacta",
                        "se entiende y sirve"):
        assert explicacion in visible, explicacion
    # El texto oficial va por regla, como fragmento: los encabezados de
    # apartado del CTE no aparecen.
    assert "Ver el texto oficial" in html
    assert "Número de salidas y longitud de los recorridos" not in html
