"""Cobertura declarada por ámbito y materia.

**La cobertura no se infiere de la ausencia de reglas.** Que no haya reglas de
patrimonio cargadas para Pozuelo no significa que Pozuelo no tenga normativa
de patrimonio: significa que no la hemos transcrito. Confundir ambas cosas es
la inferencia negativa que `docs/brain/INFERENCE_ENGINE.md` §2.2 prohíbe — y
es la más peligrosa del sistema, porque falla como un tranquilizador "no hay
problemas".

Por eso la cobertura es un dato declarado (`normativa/cobertura/manifiesto.yaml`)
y no una consulta al corpus. La diferencia entre estas dos frases es la
diferencia entre un producto insostenible y uno vendible:

    "Tu proyecto cumple."
    "Tu proyecto cumple las 214 reglas cargadas para Pozuelo de Alarcón.
     No hay cobertura de patrimonio ni de medio ambiente."
"""
from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml

from . import catalogos
from .ambito import CadenaAmbitos

MANIFIESTO = Path(__file__).resolve().parent / "cobertura" / "manifiesto.yaml"

# `no_competente` es el tercer estado, y no es obvio: distingue "no lo tenemos"
# de "aquí no hay nada que tener porque la materia es de otro nivel". Sin él,
# todo municipio aparecería eternamente incompleto en materias que nunca le
# corresponden.
ESTADOS = ("completo", "parcial", "ausente", "no_competente")


@dataclass
class EntradaCobertura:
    ambito: str
    materia: str
    estado: str
    verificado: Optional[str] = None
    por: Optional[str] = None

    @property
    def afirmable(self) -> bool:
        """Si se puede afirmar algo sobre esta materia en este ámbito."""
        return self.estado in ("completo", "parcial")


@dataclass
class InformeCobertura:
    entradas: List[EntradaCobertura] = field(default_factory=list)
    # Materias que existen en disco pero cuyo fichero fue rechazado en carga:
    # hay corpus y está roto, que es peor que no tenerlo y se dice igual.
    rotas: List[str] = field(default_factory=list)

    def sin_cobertura(self) -> List[EntradaCobertura]:
        return [e for e in self.entradas if e.estado == "ausente"]

    def afirmables(self) -> List[EntradaCobertura]:
        return [e for e in self.entradas if e.afirmable]

    def resumen(self) -> str:
        """Frase que el producto debe mostrar. Nunca "cumple" a secas."""
        ok = self.afirmables()
        falta = self.sin_cobertura()
        partes = []
        if ok:
            partes.append("Cobertura: " + " · ".join(f"{e.materia} ({e.estado})" for e in ok))
        if falta:
            partes.append("Sin cobertura de " + ", ".join(e.materia for e in falta))
        if self.rotas:
            partes.append("Corpus no cargable en " + ", ".join(self.rotas))
        return ". ".join(partes) if partes else "Sin cobertura declarada para este ámbito."

    def a_dict(self) -> dict:
        return {
            "entradas": [
                {
                    "ambito": e.ambito,
                    "materia": e.materia,
                    "estado": e.estado,
                    "verificado": e.verificado,
                }
                for e in self.entradas
            ],
            "rotas": list(self.rotas),
            "resumen": self.resumen(),
        }


@functools.lru_cache(maxsize=4)
def _manifiesto(ruta: Optional[Path] = None) -> dict:
    """Cacheado POR RUTA, no globalmente. La lección es de la Fase 0: un
    `lru_cache(maxsize=1)` sobre una función con argumento opcional construyó
    dos registros geográficos porque `f()` y `f("es")` son claves distintas."""
    ruta = ruta or MANIFIESTO
    if not ruta.exists():
        return {"cobertura": []}
    with ruta.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {"cobertura": []}


def _declarado(ruta: Optional[Path] = None) -> Dict[str, Dict[str, dict]]:
    salida: Dict[str, Dict[str, dict]] = {}
    for e in _manifiesto(ruta).get("cobertura") or []:
        salida[e["ambito"]] = e.get("materias") or {}
    return salida


def cobertura(
    cadena: CadenaAmbitos,
    rotas: Optional[Set[str]] = None,
    ruta: Optional[Path] = None,
) -> InformeCobertura:
    """Informe de cobertura de una cadena territorial.

    Recorre TODAS las materias del catálogo, no solo las declaradas: una
    materia sobre la que el manifiesto calla es `ausente`, y eso hay que
    decirlo. El silencio no es cobertura.
    """
    declarado = _declarado(ruta)
    comps = catalogos.competencias()
    entradas: List[EntradaCobertura] = []

    for materia in catalogos.materias():
        comp = comps.get(materia, {})
        nivel_competente = comp.get("competencia")

        # ¿Qué ámbito de la cadena es el competente para esta materia?
        ambito_obj = None
        if nivel_competente == "sectorial":
            # Los sectoriales no son un nivel de la cadena: la atraviesan
            # (§3.3), así que ningún ámbito tiene nivel "sectorial" y buscarlo
            # por nivel no encontraría nunca nada — dejando patrimonio y medio
            # ambiente eternamente "ausentes" aunque estuvieran transcritos.
            # Su corpus vive, de hecho, en el ámbito territorial más concreto
            # con corpus (el esquema ni siquiera admite una ruta de ámbito
            # sectorial), y ahí es donde se declara su cobertura.
            ambito_obj = next(
                (a for a in reversed(cadena.ambitos) if a.tiene_corpus), None
            )
        else:
            for a in cadena.ambitos:
                if not a.tiene_corpus:
                    continue
                if catalogos.nivel_de_ambito(a.id) == nivel_competente:
                    ambito_obj = a
                    break

        if ambito_obj is None:
            # La cadena no llega al nivel competente (p. ej. no se declaró
            # municipio y la materia es municipal). No es "ausente": es que no
            # se ha preguntado por ese nivel.
            entradas.append(
                EntradaCobertura(
                    ambito=cadena.mas_especifico.id,
                    materia=materia,
                    estado="ausente" if nivel_competente else "no_competente",
                )
            )
            continue

        decl = declarado.get(ambito_obj.id, {}).get(materia)
        if decl is None:
            entradas.append(EntradaCobertura(ambito_obj.id, materia, "ausente"))
        else:
            estado = decl.get("estado") if isinstance(decl, dict) else str(decl)
            entradas.append(
                EntradaCobertura(
                    ambito=ambito_obj.id,
                    materia=materia,
                    estado=estado if estado in ESTADOS else "ausente",
                    verificado=(decl.get("verificado") if isinstance(decl, dict) else None),
                    por=(decl.get("por") if isinstance(decl, dict) else None),
                )
            )

    return InformeCobertura(entradas=entradas, rotas=sorted(rotas or set()))
