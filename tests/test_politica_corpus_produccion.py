# -*- coding: utf-8 -*-
"""Política del corpus de producción: firmado con hash válido, o marcado.

Ejecutar:  pytest tests/test_politica_corpus_produccion.py

PRD: `docs/prd/2026-08-22-corpus-firmado-dbsi3-evacuacion.md` §2.3 (capa 5) y
§4 (T5-T7).

T7 es la capa que tapa el hueco que el esquema no puede cerrar: `estado` no es
obligatorio (el corpus ficticio de fixtures —congelado— depende de que
`None` + sin tag = confirmada), así que nada estructural impide que una regla
de PRODUCCIÓN entre sin estado y sin tag y se sirva como validada. Este test
lo impide donde importa: sobre `normativa/es/` real.

T5/T6 prueban la propagación al agente: el flag `pendiente_de_firma_colegiada`
de `agente/herramientas/reglas.py` cae solo cuando la regla firmada no lleva
el tag — cero cambios en la skill ni en el contrato G11.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from normativa import loader  # noqa: E402
from normativa.firma import hash_de_contenido_firmado  # noqa: E402
from normativa.validacion import TAG_SIN_FIRMAR  # noqa: E402

from tests.test_firma_integridad import _norma, _regla  # noqa: E402


# --- T7: toda regla de producción está firmada (con hash válido) o marcada ---

def test_toda_regla_de_produccion_esta_firmada_o_marcada():
    """La capa 5. Una regla del corpus real solo puede estar en dos estados
    honestos: FIRMADA con su bloque de firma y su hash de contenido verificado,
    o marcada con `pendiente_firma_colegiado` (y por tanto no afirmable).
    Cualquier tercera cosa es una regla presentándose como lo que no es.

    Nota fase 1: una FIRMADA sin `hash_contenido` se tolera aquí igual que en
    la validación 20 (compatibilidad con el formato del PRD del 21-08) —
    INVERTIR EL JUEVES 2026-08-28 junto con `test_firmada_sin_hash_se_tolera`.
    """
    resultado = loader.cargar(["es"])
    assert resultado.reglas, "el corpus de producción está vacío; revisa V0-5"
    impostoras = []
    for fichero in resultado.ficheros:
        norma = fichero.doc.get("norma") or {}
        for regla in fichero.doc.get("reglas") or []:
            cid = regla.get("concept_id")
            estado = regla.get("estado")
            tiene_tag = TAG_SIN_FIRMAR in (regla.get("tags") or [])
            if estado == "FIRMADA":
                firma = regla.get("firma") or {}
                declarado = firma.get("hash_contenido")
                if not firma.get("curador") or not firma.get("fecha"):
                    impostoras.append("%s: FIRMADA con firma incompleta" % cid)
                elif declarado and declarado != hash_de_contenido_firmado(norma, regla):
                    impostoras.append("%s: FIRMADA con hash que no coincide" % cid)
                elif tiene_tag:
                    impostoras.append("%s: FIRMADA y a la vez pendiente de firma" % cid)
            elif estado == "VERIFICADA_AUTOMATICA":
                continue  # afirmable por diseño del PRD del 21-08
            elif not tiene_tag:
                impostoras.append(
                    "%s: ni FIRMADA ni marcada con «%s»" % (cid, TAG_SIN_FIRMAR))
    assert not impostoras, impostoras


# --- T5/T6: el flag del agente sigue al tag, sin tocar skill ni contrato -----

def _corpus_tmp(tmp_path: Path, regla: dict) -> Path:
    carpeta = tmp_path / "es" / "estatal"
    carpeta.mkdir(parents=True)
    (carpeta / "seguridad_incendio.yaml").write_text(
        yaml.safe_dump({"version": 1, "norma": _norma(), "reglas": [regla]},
                       allow_unicode=True, sort_keys=False), encoding="utf-8")
    return tmp_path


def test_capacidad_declara_pendiente_con_regla_sin_firmar(tmp_path, monkeypatch):
    from agente.herramientas import reglas as capacidad

    regla = _regla(estado=None, con_hash=False)
    regla.pop("firma", None)
    regla["tags"] = ["evacuacion", TAG_SIN_FIRMAR]
    monkeypatch.setattr(loader, "RAIZ", _corpus_tmp(tmp_path, regla))

    salida = capacidad.umbral_de_regla(regla["concept_id"], "es", {"caso": "general"})
    assert salida["ok"] and salida["valor"] == 25
    assert salida["pendiente_de_firma_colegiada"] is True


def test_capacidad_no_declara_pendiente_con_regla_firmada(tmp_path, monkeypatch):
    """T6 en su núcleo: la MISMA capacidad, la MISMA respuesta (valor, unidad,
    cita), y el flag cae solo porque la regla firmada ya no lleva el tag.
    Ni la skill ni el contrato de la capacidad han cambiado (G11 intacto)."""
    from agente.herramientas import reglas as capacidad

    monkeypatch.setattr(loader, "RAIZ", _corpus_tmp(tmp_path, _regla()))

    salida = capacidad.umbral_de_regla(
        "es.prueba.seguridad_incendio.longitud", "es", {"caso": "general"})
    assert salida["ok"] and salida["valor"] == 25
    assert salida["unidad"] == "m"
    assert "BOE-A-2006-5515" in salida["cita"]
    assert salida["pendiente_de_firma_colegiada"] is False
