# -*- coding: utf-8 -*-
"""La firma con hash de contenido: manipular una regla firmada tumba su carga.

Ejecutar:  pytest tests/test_firma_integridad.py

PRD: `docs/prd/2026-08-22-corpus-firmado-dbsi3-evacuacion.md` §2 y §4 (T1-T4).

Qué se protege: el bloque `firma:{curador,fecha}` del PRD del 21-08 dice quién
aprobó, no QUÉ aprobó. `firma.hash_contenido` (normativa/firma.py) ata la firma
al contenido; la validación 20 lo recomputa en cada carga y una discrepancia
rechaza el fichero — fail-closed, la materia cae en vez de servirse alterada.

Todo corpus de prueba se construye en tmp_path: cero ficheros nuevos en
`tests/fixtures/` (congelado hasta el 2026-08-28).
"""
from __future__ import annotations

import copy
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from normativa import loader, validacion  # noqa: E402
from normativa.firma import (  # noqa: E402
    CLAVES_DE_FLUJO, hash_de_contenido_firmado, serializacion_canonica,
)

BOLETIN = "BOE-A-2006-5515"


def _norma() -> dict:
    return {
        "concept_id": "es.prueba.dbsi.norma",
        "instance_id": "es.prueba.dbsi.norma@1",
        "ambito": "es",
        "literal": "La longitud no excede de 25 m.",
        "fuente": {
            "rango": "Real Decreto",
            "organismo": "Ministerio de Vivienda",
            "identificador_oficial": "RD 314/2006",
            "titulo": "Código Técnico de la Edificación",
            "boletin": BOLETIN,
        },
        "articulo": {"documento_basico": "DB-SI", "seccion": "SI 3",
                     "apartado": "3", "tabla": "3.1"},
        "vigencia": {"vigencia_desde": "2006-03-29"},
    }


def _regla(estado="FIRMADA", con_hash=True) -> dict:
    regla = {
        "concept_id": "es.prueba.seguridad_incendio.longitud",
        "instance_id": "es.prueba.seguridad_incendio.longitud@1",
        "nombre": "Longitud máxima del recorrido",
        "estado": estado,
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
    }
    if estado == "FIRMADA":
        regla["firma"] = {"curador": "Pablo Camacho", "fecha": "2026-08-26"}
        if con_hash:
            regla["firma"]["hash_contenido"] = hash_de_contenido_firmado(_norma(), regla)
    return regla


def _escribir_corpus(tmp_path: Path, doc: dict) -> Path:
    raiz = tmp_path / "corpus"
    carpeta = raiz / "es" / "estatal"
    carpeta.mkdir(parents=True)
    (carpeta / "seguridad_incendio.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return raiz


# --- T1: el hash es canónico y sensible --------------------------------------

def test_hash_contenido_estable_y_canonico():
    norma, regla = _norma(), _regla(con_hash=False)

    # Fecha como date de PyYAML vs cadena ISO: mismo hash (normalizar_fechas).
    con_date = copy.deepcopy(regla)
    con_date["vigencia"]["vigencia_desde"] = date(2006, 3, 29)
    assert (hash_de_contenido_firmado(norma, regla)
            == hash_de_contenido_firmado(norma, con_date))

    # El orden de claves del YAML no importa: la serialización ordena.
    desordenada = dict(reversed(list(regla.items())))
    assert (hash_de_contenido_firmado(norma, regla)
            == hash_de_contenido_firmado(norma, desordenada))

    # Los metadatos de flujo (firma, estado, tags) NO entran: la huella del
    # borrador impreso en la hoja es la misma que la de la regla firmada.
    como_borrador = copy.deepcopy(regla)
    como_borrador["estado"] = "BORRADOR"
    como_borrador["tags"] = ["cualquier_cosa"]
    assert (hash_de_contenido_firmado(norma, regla)
            == hash_de_contenido_firmado(norma, como_borrador))
    assert CLAVES_DE_FLUJO == {"firma", "estado", "tags"}

    # Y cambiar UN valor de la tabla cambia el hash.
    alterada = copy.deepcopy(regla)
    alterada["parametro"]["valores"][0]["valor"] = 26
    assert (hash_de_contenido_firmado(norma, regla)
            != hash_de_contenido_firmado(norma, alterada))

    # También cambia si cambia la NORMA (la firma avala la cita, no solo la tabla).
    otra_norma = copy.deepcopy(norma)
    otra_norma["literal"] = "Otro literal."
    assert (hash_de_contenido_firmado(norma, regla)
            != hash_de_contenido_firmado(otra_norma, regla))

    assert '"firma"' not in serializacion_canonica(norma, _regla(con_hash=True))


# --- T2: manipulación tumba la carga -----------------------------------------

def test_firma_manipulada_tumba_la_carga(tmp_path):
    doc = {"version": 1, "norma": _norma(), "reglas": [_regla()]}
    doc["reglas"][0]["parametro"]["valores"][0]["valor"] = 26  # tras firmar
    raiz = _escribir_corpus(tmp_path, doc)

    resultado = loader.cargar(["es"], raiz=raiz)
    assert resultado.rechazados, "la regla manipulada tendría que haberse rechazado"
    fallos = "\n".join(f for fallos in resultado.rechazados.values() for f in fallos)
    assert "[20]" in fallos
    assert not resultado.ficheros, "un fichero rechazado no puede quedar cargado"


# --- T3: la regla íntegra carga limpia ---------------------------------------

def test_hash_valido_carga_limpio(tmp_path):
    doc = {"version": 1, "norma": _norma(), "reglas": [_regla()]}
    raiz = _escribir_corpus(tmp_path, doc)

    resultado = loader.cargar(["es"], raiz=raiz)
    assert not resultado.rechazados, resultado.rechazados
    assert resultado.ficheros


# --- T4: fase 1 tolera la firma sin hash (formato del PRD cerrado) -----------

def test_firmada_sin_hash_se_tolera_esta_semana(tmp_path):
    """INVERTIR EL JUEVES 2026-08-28 (fase 2): entonces una FIRMADA sin
    `hash_contenido` debe FALLAR la validación 20 y el esquema hacer el campo
    obligatorio. Hoy se tolera por compatibilidad con las firmas del PRD
    cerrado del 21-08 y los tests del `scripts/curar_corpus.py` congelado."""
    doc = {"version": 1, "norma": _norma(), "reglas": [_regla(con_hash=False)]}
    raiz = _escribir_corpus(tmp_path, doc)

    resultado = loader.cargar(["es"], raiz=raiz)
    assert not resultado.rechazados, resultado.rechazados


# --- La validación 20 está registrada donde el loader la ejecuta -------------

def test_validacion_20_esta_en_las_validaciones_por_fichero():
    assert validacion.validar_integridad_de_firma in validacion.VALIDACIONES_POR_FICHERO
