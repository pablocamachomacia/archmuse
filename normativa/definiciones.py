# -*- coding: utf-8 -*-
"""Consulta del corpus de terminología normativa.

Responde a "¿qué dice la norma que significa este término?" con el literal
transcrito y su cita. **No evalúa nada**: una definición no se cumple ni se
incumple, se usa (`NORMATIVE_ENGINE.md` §6).

**Por qué no lo carga `loader.py`.** Aquel descubre y valida el corpus de
*reglas* contra `regla.schema.json`, que exige `prioridad` y
`nivel_de_conocimiento` en toda entrada. Un glosario no tiene ninguno de los
dos, y rellenarlos con un valor plausible sería convertir la definición en una
regla evaluable de mentira — lo que `docs/design/DB-SI_DECISIONS.md` D5.b
prohíbe. Por eso `normativa/terminologia/` queda fuera del árbol de ámbitos
que `loader.descubrir` recorre, y esta carga es independiente.

**Por qué este módulo no importa `extraccion/`.** Transcribir es un paso de
curador, que ocurre una vez y deja un YAML revisable en un PR; consultar es
runtime. `tests/test_extraccion_fronteras.py::test_nadie_importa_extraccion`
vigila esa separación, y aquí se respeta sin excepción.

**Precedencia entre glosarios.** El Anejo SI A lo dice literalmente: sus
términos rigen para lo relacionado únicamente con seguridad en caso de
incendio, «o bien en el Anejo III de la Parte I de este CTE, cuando sean
términos de uso común en el conjunto del Código». `buscar` implementa esa
cadena leyendo el campo `precedencia` del propio fichero — no una prioridad
inventada aquí.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

RAIZ_TERMINOLOGIA = Path(__file__).resolve().parent / "terminologia"


@dataclass(frozen=True)
class Definicion:
    """Un término definido por una norma, con todo lo que hace falta para
    citarlo y para saber cuánto fiarse de la transcripción."""

    concept_id: str
    termino: str
    literal: str
    glosario: str
    documento_basico: str
    anejo: str
    url_oficial: str
    metodo_transcripcion: str
    verificada_por_humano: bool
    anomalias_conocidas: Tuple[str, ...] = ()
    notas_de_uso: Optional[str] = None

    @property
    def cita(self) -> str:
        """Localizador legible: «DB-SI, Anejo SI A, "Superficie útil"»."""
        return f'{self.documento_basico}, Anejo {self.anejo}, "{self.termino}"'


def _normalizar(termino: str) -> str:
    """Clave de búsqueda: sin mayúsculas ni acentos.

    Un término se escribe de varias formas según quién lo teclee
    («superficie util», «Superficie útil»); la identidad la lleva el
    `concept_id`, no la grafía.
    """
    tabla = str.maketrans("áéíóúü", "aeiouu")
    return " ".join(termino.lower().translate(tabla).split())


@functools.lru_cache(maxsize=1)
def _corpus() -> Tuple[Dict[str, Definicion], Tuple[str, ...]]:
    """Todos los glosarios en disco, indexados por término normalizado.

    Devuelve también el orden de precedencia declarado, para que `buscar`
    resuelva el término común por la cadena que la norma fija y no por el
    orden alfabético de los ficheros.
    """
    por_termino: Dict[str, Definicion] = {}
    precedencias: List[str] = []
    if not RAIZ_TERMINOLOGIA.is_dir():
        return {}, ()

    for ruta in sorted(RAIZ_TERMINOLOGIA.glob("*.yaml")):
        with ruta.open(encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        norma = doc.get("norma") or {}
        articulo = norma.get("articulo") or {}
        fuente = norma.get("fuente") or {}
        precedencias.extend(doc.get("precedencia") or ())
        for entrada in doc.get("definiciones") or ():
            transcripcion = entrada.get("transcripcion") or {}
            definicion = Definicion(
                concept_id=entrada["concept_id"],
                termino=entrada["termino"],
                literal=entrada["literal"],
                glosario=norma.get("concept_id", ""),
                documento_basico=articulo.get("documento_basico", ""),
                anejo=articulo.get("anejo", ""),
                url_oficial=fuente.get("url_oficial", ""),
                metodo_transcripcion=transcripcion.get("metodo", ""),
                verificada_por_humano=bool(transcripcion.get("verificada_por_humano", False)),
                anomalias_conocidas=tuple(transcripcion.get("anomalias_conocidas") or ()),
                notas_de_uso=entrada.get("notas_de_uso"),
            )
            # Un mismo término puede estar definido en dos glosarios; se guardan
            # ambos y `buscar` decide con la precedencia declarada.
            por_termino.setdefault(_normalizar(entrada["termino"]), definicion)
            por_termino[f'{definicion.glosario}#{_normalizar(entrada["termino"])}'] = definicion
    return por_termino, tuple(precedencias)


def buscar(termino: str, *, glosario: Optional[str] = None) -> Optional[Definicion]:
    """La definición de `termino`, o `None` si el corpus no la tiene.

    `None` significa "no tenemos esa definición cargada", nunca "el término no
    está definido en el CTE" — es el estado `sin_cobertura` de
    `NORMATIVE_ENGINE.md` §13, y quien llame debe tratarlo como tal en vez de
    dar el término por inexistente.

    `glosario` fuerza un corpus concreto (su `concept_id`) cuando el mismo
    término está definido en más de uno.
    """
    por_termino, _ = _corpus()
    clave = _normalizar(termino)
    if glosario:
        return por_termino.get(f"{glosario}#{clave}")
    return por_termino.get(clave)


def literal(termino: str, *, glosario: Optional[str] = None) -> Optional[str]:
    """Solo el texto de la definición. Atajo para mostrarlo en una ficha."""
    definicion = buscar(termino, glosario=glosario)
    return definicion.literal if definicion else None


def terminos() -> List[str]:
    """Términos disponibles, en orden alfabético. Para saber qué hay cargado
    sin tener que abrir los YAML."""
    por_termino, _ = _corpus()
    return sorted({d.termino for k, d in por_termino.items() if "#" not in k})
