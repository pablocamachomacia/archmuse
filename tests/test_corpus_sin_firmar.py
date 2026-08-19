# -*- coding: utf-8 -*-
"""El estado en el que vive toda regla entre transcribirla y firmarla (`NOR-1`).

Ejecutar:  pytest tests/test_corpus_sin_firmar.py

**El agujero que esto cierra.** El manifiesto de cobertura tenía cuatro estados
y ninguno decía la verdad sobre una regla recién transcrita: `ausente` niega un
trabajo que está hecho y en disco, y `parcial` es **afirmable**, de modo que
ArchMuse pasaría a evaluar seguridad contra incendios con una regla que ningún
colegiado ha revisado. Al declarar la primera regla real (2026-08-19) hubo que
elegir entre las dos mentiras, y por eso existe `transcrito_sin_firmar`.

Ese estado, solo, no protege de nada: es una cadena en un YAML y basta
cambiarla. Lo que lo hace exigible es la **validación 18**, que rechaza al
cargar cualquier promoción a `completo` o `parcial` mientras alguna regla de esa
materia conserve `pendiente_firma_colegiado`. El orden queda escrito como
código: transcribir → declarar sin firmar → firmar → retirar la etiqueta de la
regla → promover el manifiesto. Ningún paso se puede adelantar en silencio.

Y la **validación 17**, que ya existía, no veía el caso en el que se equivoca
justamente quien empieza a transcribir: su segundo recorrido vivía dentro del
bucle sobre lo declarado, así que un ámbito con reglas en disco y sin entrada en
el manifiesto no lo miraba nadie. El corpus de producción estaba en ese caso.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from normativa import validacion  # noqa: E402
from normativa.loader import cargar  # noqa: E402
from normativa.manifiesto import (  # noqa: E402
    ESTADOS, ESTADOS_CON_REGLAS, EntradaCobertura, InformeCobertura, _manifiesto,
)

TAG = validacion.TAG_SIN_FIRMAR


def _reglas_por_ambito_y_materia(carga):
    fuera = {}
    for fichero in carga.ficheros:
        for regla in (fichero.doc.get("reglas") or []):
            fuera.setdefault((fichero.ambito, regla.get("materia")), []).append(regla)
    return fuera


# --- 1. Lo transcrito y sin firmar no es cobertura ------------------------

def test_transcrito_sin_firmar_no_es_afirmable():
    """Todo el sentido del estado. Si fuera afirmable no haría falta: ya
    existía `parcial`."""
    e = EntradaCobertura(ambito="es", materia="seguridad_incendio",
                         estado="transcrito_sin_firmar")
    assert e.afirmable is False
    assert e.transcrito_sin_firmar is True


def test_los_dos_estados_afirmables_siguen_siendo_dos():
    """Una guardia contra el descuido de añadir el estado nuevo a la lista de
    afirmables «para que salga cobertura»."""
    for estado in ("completo", "parcial"):
        assert EntradaCobertura("es", "m", estado).afirmable is True
    for estado in ("transcrito_sin_firmar", "ausente", "no_competente"):
        assert EntradaCobertura("es", "m", estado).afirmable is False


def test_el_estado_esta_en_el_catalogo_y_cuenta_como_reglas_en_disco():
    assert "transcrito_sin_firmar" in ESTADOS
    assert "transcrito_sin_firmar" in ESTADOS_CON_REGLAS
    assert "ausente" not in ESTADOS_CON_REGLAS


def test_el_resumen_no_lo_presenta_junto_a_la_cobertura():
    """Quien lee el resumen tiene que poder distinguir «lo tenemos y vale» de
    «lo tenemos y no lo hemos revisado» sin conocer el vocabulario interno."""
    informe = InformeCobertura(entradas=[
        EntradaCobertura("es", "seguridad_incendio", "transcrito_sin_firmar"),
    ])
    resumen = informe.resumen()
    assert "sin firma de colegiado" in resumen
    assert "no se afirma sobre ello" in resumen
    assert not resumen.startswith("Cobertura:")


# --- 2. La validación 18: el manifiesto no puede afirmar de más -----------

def test_promover_a_parcial_con_reglas_sin_firmar_se_rechaza():
    fallos = validacion.validar_firma_de_lo_declarado(
        {"cobertura": [{"ambito": "es",
                        "materias": {"seguridad_incendio": {"estado": "parcial"}}}]},
        {("es", "seguridad_incendio"): [{"concept_id": "r1", "tags": [TAG]}]})
    assert len(fallos) == 1
    assert "r1" in fallos[0]
    assert "transcrito_sin_firmar" in fallos[0]


def test_declararlo_sin_firmar_es_lo_correcto_y_no_falla():
    fallos = validacion.validar_firma_de_lo_declarado(
        {"cobertura": [{"ambito": "es",
                        "materias": {"seguridad_incendio":
                                     {"estado": "transcrito_sin_firmar"}}}]},
        {("es", "seguridad_incendio"): [{"concept_id": "r1", "tags": [TAG]}]})
    assert fallos == []


def test_una_vez_retirada_la_etiqueta_se_puede_promover():
    """El final del recorrido: firmada la regla y quitada la etiqueta, el
    manifiesto puede declarar cobertura de verdad."""
    fallos = validacion.validar_firma_de_lo_declarado(
        {"cobertura": [{"ambito": "es",
                        "materias": {"seguridad_incendio": {"estado": "parcial"}}}]},
        {("es", "seguridad_incendio"): [{"concept_id": "r1", "tags": ["dbsi3"]}]})
    assert fallos == []


def test_basta_una_regla_sin_firmar_para_rechazar_la_promocion():
    """No se promedia: la materia entera se declara afirmable o no, y una sola
    regla sin revisar contamina lo que se afirme sobre esa materia."""
    fallos = validacion.validar_firma_de_lo_declarado(
        {"cobertura": [{"ambito": "es", "materias": {"m": {"estado": "completo"}}}]},
        {("es", "m"): [{"concept_id": "es.ya_firmada", "tags": []},
                       {"concept_id": "es.sin_firmar", "tags": [TAG]}]})
    # Sólo se nombra la que falta: enumerar también las firmadas convertiría el
    # mensaje en una lista donde el curador tendría que buscar el problema.
    assert len(fallos) == 1
    assert "es.sin_firmar" in fallos[0]
    assert "es.ya_firmada" not in fallos[0]


# --- 3. Sobre el corpus de producción, que es el que se vende ------------

def test_el_corpus_de_produccion_pasa_las_dos_validaciones_del_manifiesto():
    carga = cargar(["es"])
    manifiesto = _manifiesto()
    assert not validacion.validar_cobertura(manifiesto, carga.materias_por_ambito)
    assert not validacion.validar_firma_de_lo_declarado(
        manifiesto, _reglas_por_ambito_y_materia(carga))


def test_ninguna_materia_del_corpus_de_produccion_es_afirmable_todavia():
    """La frase que ArchMuse **no** puede decir hoy: «comprobamos esto».

    Ninguna regla está firmada, así que ninguna materia es afirmable y el motor
    sigue bloqueando por cobertura insuficiente. Este test deja de pasar el día
    que llegue la primera firma — y ese día hay que mirarlo, no ajustarlo.
    """
    for entrada in _manifiesto().get("cobertura") or []:
        for materia, estado in (entrada.get("materias") or {}).items():
            e = estado.get("estado") if isinstance(estado, dict) else estado
            assert EntradaCobertura(entrada["ambito"], materia, e).afirmable is False, (
                "«%s» se declara afirmable: comprueba que un colegiado la ha firmado "
                "de verdad antes de tocar este test" % materia)
