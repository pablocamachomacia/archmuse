"""Acceso cacheado a los catálogos cerrados de `normativa/esquema/`.

Materias, competencias, usos, tipologías y tipos de intervención. Son datos,
no código: crecen editando YAML, y su crecimiento es un acto de gobernanza del
Curador de Conocimiento, no una reacción a un caso concreto.
"""
from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml

ESQUEMA = Path(__file__).resolve().parent / "esquema"


def _leer_yaml(nombre: str) -> dict:
    with (ESQUEMA / nombre).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@functools.lru_cache(maxsize=1)
def materias() -> Dict[str, dict]:
    return {m["id"]: m for m in _leer_yaml("materias.yaml")["materias"]}


@functools.lru_cache(maxsize=1)
def competencias() -> Dict[str, dict]:
    return {c["materia"]: c for c in _leer_yaml("competencias.yaml")["competencias"]}


@functools.lru_cache(maxsize=1)
def exigibilidad() -> Dict[str, dict]:
    """Cuándo se le exige cada materia a un proyecto (`esquema/exigibilidad.yaml`).

    Pregunta distinta de la de `competencias()`: aquella dice QUIÉN regula,
    esta A QUIÉN se le exige. Es lo que hace computable el fail-closed del
    resolver: sin ella, "falta una norma obligatoria" no se puede decidir.
    """
    return {e["materia"]: e for e in _leer_yaml("exigibilidad.yaml")["exigibilidad"]}


@functools.lru_cache(maxsize=1)
def _usos_raw() -> dict:
    return _leer_yaml("usos.yaml")


@functools.lru_cache(maxsize=1)
def esquema_regla() -> dict:
    with (ESQUEMA / "regla.schema.json").open(encoding="utf-8") as f:
        return json.load(f)


@functools.lru_cache(maxsize=1)
def usos() -> Dict[str, dict]:
    """Aplana el árbol de usos conservando la relación padre/hijo."""
    plano: Dict[str, dict] = {}

    def recorrer(nodos: List[dict], padre: Optional[str]) -> None:
        for n in nodos:
            plano[n["id"]] = {"id": n["id"], "nombre": n["nombre"], "padre": padre}
            recorrer(n.get("hijos") or [], n["id"])

    recorrer(_usos_raw()["usos"], None)
    return plano


def uso_cubre(declarado_en_regla: str, uso_del_proyecto: str) -> bool:
    """True si una regla que aplica a `declarado_en_regla` cubre
    `uso_del_proyecto`.

    Una regla declara el nodo más alto al que aplica y cubre todos sus
    descendientes: `residencial` cubre `residencial.vivienda_libre`. Sin esto,
    cada regla tendría que enumerar variantes de uso — la misma explosión
    combinatoria que este diseño existe para evitar, movida de sitio.
    """
    tabla = usos()
    actual: Optional[str] = uso_del_proyecto
    while actual:
        if actual == declarado_en_regla:
            return True
        actual = tabla.get(actual, {}).get("padre")
    return False


@functools.lru_cache(maxsize=1)
def tipos_de_intervencion() -> Set[str]:
    return {t["id"] for t in _usos_raw()["tipos_de_intervencion"]}


@functools.lru_cache(maxsize=1)
def tipologias() -> Set[str]:
    return {t["id"] for t in _usos_raw()["tipologias"]}


@functools.lru_cache(maxsize=1)
def equivalencias_heredadas() -> Dict[str, dict]:
    """Traducción de los 3 valores de `evaluator.UMBRALES_TIPOLOGIA`, que
    mezclan dos ejes ("rehabilitacion" es un tipo de intervención, no una
    tipología). La traducción nunca es silenciosa: lleva su asunción."""
    return _usos_raw().get("equivalencias_heredadas") or {}


def nivel_de_ambito(ambito: str) -> str:
    """Nivel territorial deducido de la ruta. `es`=estatal, `es.13`=autonómico,
    cualquier cosa más profunda con municipio = municipal."""
    partes = ambito.split(".")
    if len(partes) == 1:
        return "estatal"
    if len(partes) == 2:
        return "autonomico"
    return "municipal"
