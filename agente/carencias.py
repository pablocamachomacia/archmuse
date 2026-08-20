# -*- coding: utf-8 -*-
"""Cuando falta una Skill: detectarlo, proponerla, y NO instalarla.

**La regla que gobierna este módulo entera está en el encargo de Pablo:** «el
agente puede detectar necesidades de nuevas Skills y proponerlas, pero no debe
modificar silenciosamente sus propias capacidades». Aquí eso no es una
convención: no hay ni una línea que escriba en `agente/skills/`, y hay un test
que lo comprueba recorriendo el paquete entero en busca de escrituras a esa
ruta.

**Por qué importa tanto.** Un sistema que se amplía a sí mismo pierde en un mes
la propiedad que hace defendible todo lo demás: que alguien pueda decir qué sabe
hacer ArchMuse y con qué criterio. Una Skill es procedimiento profesional; una
Skill escrita por el propio sistema y aplicada a un proyecto real es criterio
profesional sin autor, y eso no es un problema técnico sino de responsabilidad
civil (D-7 en `docs/design/decisiones-pendientes.md`).

**Qué sí hace, y es útil.** Registra qué le han pedido y no ha sabido hacer,
cuántas veces, y redacta un **borrador de declaración** —qué requeriría, qué
capacidades usaría de las que ya existen, qué debería verificar— para que un
humano lo lea en cinco minutos en vez de partir de cero. El umbral de madurez
evita el ruido: una petición suelta no justifica una Skill; dos peticiones
distintas del mismo objetivo, sí (D-8).
"""
from __future__ import annotations

import json
import re
import threading
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Tuple

#: Cuántas peticiones distintas hacen falta para que una carencia se considere
#: madura. Parámetro, no constante escondida: se ajusta sin tocar la lógica.
UMBRAL_DE_MADUREZ = 2

_PALABRAS_VACIAS = {
    "el", "la", "los", "las", "un", "una", "de", "del", "y", "o", "que", "para",
    "por", "con", "en", "me", "mi", "este", "esta", "esto", "dime", "hazme",
    "prepara", "preparame", "necesito", "quiero", "puedes", "por favor",
}


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalizar(objetivo: str) -> str:
    """Reduce un objetivo a su forma comparable.

    Sin esto, «hazme los planos de carpintería» y «prepárame planos de
    carpinterías» serían dos carencias distintas y ninguna llegaría nunca al
    umbral. Es intencionadamente tosco —minúsculas, sin tildes, sin palabras
    vacías, ordenado— porque una agrupación lista para el 80 % de los casos y
    explicable en tres líneas vale más aquí que una perfecta y opaca.
    """
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", objetivo.lower())
        if unicodedata.category(c) != "Mn"
    )
    palabras = [p for p in re.findall(r"[a-z0-9]+", sin_tildes) if p not in _PALABRAS_VACIAS]
    # Se recortan los plurales más comunes antes de ordenar; «planos» y «plano»
    # tienen que caer en el mismo saco.
    raices = [p[:-1] if len(p) > 4 and p.endswith("s") else p for p in palabras]
    return " ".join(sorted(dict.fromkeys(raices)))


@dataclass(frozen=True)
class Carencia:
    """Algo que se pidió y no se supo hacer."""

    objetivo_normalizado: str
    peticiones: Tuple[str, ...] = field(default_factory=tuple)
    primera_vez: str = ""
    ultima_vez: str = ""

    @property
    def veces(self) -> int:
        return len(self.peticiones)

    @property
    def madura(self) -> bool:
        """Si ya merece que un humano la mire.

        Cuenta peticiones **distintas**, no repeticiones literales: alguien que
        insiste tres veces con la misma frase no ha demostrado nada más que
        impaciencia.
        """
        return len(set(self.peticiones)) >= UMBRAL_DE_MADUREZ

    def a_dict(self) -> dict:
        return {
            "objetivo_normalizado": self.objetivo_normalizado,
            "peticiones": list(self.peticiones),
            "veces": self.veces,
            "madura": self.madura,
            "primera_vez": self.primera_vez,
            "ultima_vez": self.ultima_vez,
        }


class SustratoDeCarencias(Protocol):
    def anadir(self, objetivo: str, momento: str) -> None: ...

    def leer(self) -> List[Tuple[str, str]]: ...


class CarenciasEnMemoria:
    def __init__(self) -> None:
        self._filas: List[Tuple[str, str]] = []
        self._cerrojo = threading.Lock()

    def anadir(self, objetivo: str, momento: str) -> None:
        with self._cerrojo:
            self._filas.append((objetivo, momento))

    def leer(self) -> List[Tuple[str, str]]:
        with self._cerrojo:
            return list(self._filas)


class CarenciasEnFicheros:
    """Un JSONL global. No va por proyecto: la señal es de producto, no de obra."""

    def __init__(self, ruta: Optional[Path] = None) -> None:
        if ruta is None:
            from analyzer import storage

            ruta = Path(storage.data_dir()) / "carencias.jsonl"
        self.ruta = Path(ruta)
        self._cerrojo = threading.Lock()

    def anadir(self, objetivo: str, momento: str) -> None:
        with self._cerrojo:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            with open(self.ruta, "a", encoding="utf-8") as f:
                f.write(json.dumps({"objetivo": objetivo, "momento": momento},
                                   ensure_ascii=False))
                f.write("\n")

    def leer(self) -> List[Tuple[str, str]]:
        if not self.ruta.exists():
            return []
        fuera: List[Tuple[str, str]] = []
        with self._cerrojo, open(self.ruta, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    d = json.loads(linea)
                    fuera.append((d["objetivo"], d.get("momento", "")))
                except (ValueError, KeyError):
                    continue
        return fuera


class RegistroDeCarencias:
    """Lo que se ha pedido y no se ha sabido hacer, agrupado."""

    def __init__(self, sustrato: Optional[SustratoDeCarencias] = None) -> None:
        self._sustrato: SustratoDeCarencias = (
            sustrato if sustrato is not None else CarenciasEnFicheros()
        )

    def anotar(self, objetivo: str) -> Carencia:
        self._sustrato.anadir(objetivo, _ahora())
        return self.de(objetivo)

    def todas(self) -> Tuple[Carencia, ...]:
        por_clave: Dict[str, List[Tuple[str, str]]] = {}
        for objetivo, momento in self._sustrato.leer():
            por_clave.setdefault(normalizar(objetivo), []).append((objetivo, momento))
        fuera = []
        for clave in sorted(por_clave):
            filas = por_clave[clave]
            fuera.append(Carencia(
                objetivo_normalizado=clave,
                peticiones=tuple(o for o, _ in filas),
                primera_vez=filas[0][1],
                ultima_vez=filas[-1][1],
            ))
        return tuple(fuera)

    def de(self, objetivo: str) -> Carencia:
        clave = normalizar(objetivo)
        for c in self.todas():
            if c.objetivo_normalizado == clave:
                return c
        return Carencia(objetivo_normalizado=clave)

    def maduras(self) -> Tuple[Carencia, ...]:
        return tuple(c for c in self.todas() if c.madura)


def proponer(objetivo: str, *, capacidades_disponibles: Tuple[str, ...] = (),
             skills_existentes: Tuple[str, ...] = ()) -> dict:
    """Un borrador de declaración de Skill. **Texto, no instalación.**

    Deja a propósito casi todo sin rellenar y lo dice: lo que un humano tiene
    que aportar es exactamente lo que el sistema no puede saber —el
    procedimiento profesional, qué se verifica y qué no cubre—. Un borrador que
    se inventara esos tres campos sería peor que ninguno, porque parecería
    revisable.
    """
    return {
        "estado": "PROPUESTA — requiere revisión y aprobación humana",
        "objetivo_solicitado": objetivo,
        "id_sugerido": "pendiente.%s" % (normalizar(objetivo).replace(" ", "_") or "sin_nombre"),
        "version_inicial": "0.1.0",
        "por_rellenar_por_un_humano": [
            "procedimiento: qué mira un arquitecto, en qué orden, y qué entrega",
            "requiere: qué datos del proyecto son imprescindibles, con su pregunta",
            "verificaciones: qué comprobación tiene que poder FALLAR",
            "limitaciones: qué NO va a comprobar esta Skill",
        ],
        "capacidades_ya_disponibles": list(capacidades_disponibles),
        "skills_existentes_a_revisar": list(skills_existentes),
        "aviso": (
            "ArchMuse no instala Skills por su cuenta. Este borrador es un punto de "
            "partida para una persona; el procedimiento profesional que contenga tiene "
            "que validarlo un colegiado antes de aplicarse a un proyecto real."
        ),
    }
