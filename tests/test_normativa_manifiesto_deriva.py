# -*- coding: utf-8 -*-
"""Tarea 7 del Prompt 2 (docs/prd/2026-08-21-verificacion-doble-del-corpus.md
§5.6, decidido en docs/prd/2026-08-21-pipeline-borradores-corpus-db-sua.md
§9): el manifiesto de cobertura por materia deja de ser una cadena que
alguien escribe a mano y pasa a derivarse mecánicamente del estado real de
las reglas en disco.

`normativa.resolucion` duplica el criterio de "regla confirmada" en
`_paso1_candidatas` (afirmable = `VERIFICADA_AUTOMATICA`/`FIRMADA`, o
histórica sin el tag `pendiente_firma_colegiado`). `_regla_confirmada` de
este módulo lo repite a propósito (ver su docstring, evita un ciclo de
imports) — este fichero es lo que impide que los dos criterios diverjan en
silencio.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from normativa import validacion  # noqa: E402
from normativa.manifiesto import _regla_confirmada, estado_derivado  # noqa: E402

TAG = validacion.TAG_SIN_FIRMAR


def _r(estado=None, tags=None):
    return {"concept_id": "x", "estado": estado, "tags": tags or []}


# --- _regla_confirmada: el criterio de UNA regla ----------------------------

def test_verificada_automatica_confirma():
    assert _regla_confirmada(_r(estado="VERIFICADA_AUTOMATICA")) is True


def test_firmada_confirma():
    assert _regla_confirmada(_r(estado="FIRMADA")) is True


def test_borrador_no_confirma():
    assert _regla_confirmada(_r(estado="BORRADOR")) is False


def test_historica_sin_estado_y_sin_tag_confirma():
    """seguridad_incendio.yaml, el día que se le retire el tag."""
    assert _regla_confirmada(_r(estado=None, tags=["dbsi3"])) is True


def test_historica_sin_estado_y_con_tag_no_confirma():
    """seguridad_incendio.yaml, hoy."""
    assert _regla_confirmada(_r(estado=None, tags=["dbsi3", TAG])) is False


def test_mismo_criterio_que_resolucion_paso1_candidatas():
    """Guardián contra la divergencia: `resolucion.py` línea a línea dice
    `estado_regla is not None and estado_regla not in (VERIFICADA_AUTOMATICA,
    FIRMADA)` para descartar. Aquí se prueba la misma tabla de verdad."""
    for estado in ("VERIFICADA_AUTOMATICA", "FIRMADA"):
        assert _regla_confirmada(_r(estado=estado)) is True
    for estado in ("BORRADOR", "algo_futuro_no_afirmable"):
        assert _regla_confirmada(_r(estado=estado)) is False


# --- estado_derivado: el estado de UNA materia ------------------------------

def test_sin_reglas_respeta_lo_declarado_si_no_promete_reglas():
    assert estado_derivado("no_competente", []) == "no_competente"
    assert estado_derivado("ausente", []) == "ausente"


def test_sin_reglas_y_sin_declarar_es_ausente():
    assert estado_derivado(None, []) == "ausente"


def test_sin_reglas_no_se_confia_en_un_completo_o_parcial_declarado():
    """El agujero real que abrió la primera versión de esta función: un
    manifiesto que declara `parcial` sin que quede ninguna regla en disco
    (p. ej. se borró el fichero de reglas y nadie tocó el manifiesto) no
    puede seguir leyéndose como cobertura — es la misma mentira que la
    validación 17 rechaza al cargar, aquí sin corpus detrás para pillarla."""
    assert estado_derivado("completo", []) == "ausente"
    assert estado_derivado("parcial", []) == "ausente"
    assert estado_derivado("transcrito_sin_firmar", []) == "ausente"


def test_una_borrador_fuerza_transcrito_sin_firmar_aunque_declare_completo():
    reglas = [_r(estado="BORRADOR")]
    assert estado_derivado("completo", reglas) == "transcrito_sin_firmar"


def test_basta_una_sin_confirmar_entre_varias_confirmadas():
    """No se promedia: una sola regla sin confirmar contamina la materia
    entera, igual que la validación 18 hacía con el tag."""
    reglas = [_r(estado="VERIFICADA_AUTOMATICA"), _r(estado="BORRADOR"), _r(estado="FIRMADA")]
    assert estado_derivado("parcial", reglas) == "transcrito_sin_firmar"


def test_historica_con_tag_tambien_fuerza_transcrito_sin_firmar():
    reglas = [_r(estado=None, tags=[TAG])]
    assert estado_derivado("parcial", reglas) == "transcrito_sin_firmar"


def test_todas_confirmadas_respeta_completo_declarado():
    reglas = [_r(estado="FIRMADA"), _r(estado="VERIFICADA_AUTOMATICA")]
    assert estado_derivado("completo", reglas) == "completo"


def test_todas_confirmadas_respeta_parcial_declarado():
    reglas = [_r(estado="VERIFICADA_AUTOMATICA")]
    assert estado_derivado("parcial", reglas) == "parcial"


def test_todas_confirmadas_sin_declarar_completo_ni_parcial_sube_a_parcial():
    """Sin `completo`/`parcial` ya declarado no se inventa `completo`: la
    extensión real de la materia no se puede derivar del estado de la
    regla. Se sube a `parcial`, nunca más allá."""
    reglas = [_r(estado="VERIFICADA_AUTOMATICA")]
    assert estado_derivado(None, reglas) == "parcial"
    assert estado_derivado("transcrito_sin_firmar", reglas) == "parcial"


def test_historica_sin_tag_confirma_igual_que_estado_explicito():
    reglas = [_r(estado=None, tags=["dbsi3"])]
    assert estado_derivado(None, reglas) == "parcial"
