# -*- coding: utf-8 -*-
"""C5 — `Atributo`: el vocabulario de `analyzer/hechos.py`, sin tocarlo.

**El problema que este módulo cierra.** Hasta hoy había tres vocabularios de
incertidumbre en el repositorio y ninguno sabía de los otros:

1. `Hecho` en CAP-1…CAP-5 — estado + motivo + confianza + procedencia. Correcto.
2. `*Result` en `evaluator.py` (unas cuarenta dataclases) — `passed: bool` y
   floats desnudos. Es el patrón que `hechos.py` existe para corregir.
3. `Valor(valor, origen)` en `experimentos/grafo/modelo.py` — el segundo eje
   sin el primero.

`Atributo` **no añade un cuarto**: importa los estados, la confianza y el
`Motivo` de `hechos.py` y no redefine ninguno. Decisión cerrada por Pablo el
2026-08-11: en el modelo común no existe `Valor(valor, origen)`; se usa
únicamente el vocabulario ortogonal de `hechos.py`, estado × origen.

**Los dos ejes, y por qué son dos y no un `enum` largo.** No son la misma
pregunta:

    EJE 1 — ESTADO (¿qué sé?)          EJE 2 — ORIGEN (¿de dónde?)
    ────────────────────────           ───────────────────────────
    KNOWN                              observado    (leído del fichero)
    ESTIMATED                          declarado    (lo dijo el arquitecto)
    UNKNOWN      + motivo obligatorio  derivado     (composición pura)
    NO_APLICABLE                       supuesto     (hipótesis del sistema)

«Inferido», «detectado automáticamente» o «confirmado por el usuario» no
necesitan estado propio: son casillas de este producto cartesiano. Lo único
que el modelo de hecho no sabía sostener era **más de una evidencia para la
misma magnitud**, y eso es cardinalidad, no vocabulario — y es de E2 en
adelante.

**El puente, único.** `Atributo.a_hecho()` es el ÚNICO punto en el que el
modelo produce un `Hecho`. Nada dentro de `modelo/` importa CAP-1…CAP-5: la
dependencia va del modelo al hecho y nunca al revés.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

# El vocabulario NO se redefine: se importa. Si algún día `hechos.py` añade un
# estado, este módulo lo hereda sin tocar una línea — que es exactamente la
# propiedad que se busca.
from analyzer.hechos import (  # noqa: F401  (reexportados a propósito)
    ALTA,
    BAJA,
    ESTADOS,
    ESTIMATED,
    KNOWN,
    MEDIA,
    NO_APLICABLE,
    UNKNOWN,
    Hecho,
    Motivo,
)

# --- Eje 2: origen epistémico ----------------------------------------------
# Cerrado a propósito. `hechos.Hecho.tipo` lleva un vocabulario equivalente en
# un comentario ("observado | derivado | declarado | normativo") que nadie
# valida; aquí sí se valida, y sin tocar `hechos.py` (regla de E1).

OBSERVADO = "observado"
DECLARADO = "declarado"
DERIVADO = "derivado"
SUPUESTO = "supuesto"

ORIGENES = (OBSERVADO, DECLARADO, DERIVADO, SUPUESTO)

# Mapa origen -> `Hecho.tipo`. `supuesto` no tiene equivalente exacto en el
# vocabulario de `hechos.py` (que sólo distingue observado/derivado/declarado/
# normativo): se publica como `derivado`, porque una hipótesis del sistema es
# una composición del sistema, y el matiz no se pierde — viaja en `fuente` y en
# el estado `ESTIMATED`, que es donde el arquitecto lo lee.
_TIPO_DE_HECHO = {
    OBSERVADO: "observado",
    DECLARADO: "declarado",
    DERIVADO: "derivado",
    SUPUESTO: "derivado",
}


@dataclass(frozen=True)
class Atributo:
    """Un atributo resuelto de un nodo. Nunca un valor desnudo (invariante I5).

    Las reglas se hacen cumplir por construcción, calcadas de
    `Hecho.__post_init__`, porque un contrato que sólo está en la
    documentación es un contrato que se incumple el primer martes con prisa.
    """

    valor: Optional[Any]
    estado: str
    origen: Optional[str] = None
    confianza: Optional[str] = None
    motivos: Tuple[Motivo, ...] = ()
    fuente: str = ""
    procedencia: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.estado not in ESTADOS:
            raise ValueError("estado desconocido: %r" % (self.estado,))
        if self.estado in (KNOWN, ESTIMATED):
            if self.valor is None:
                raise ValueError("estado %s exige un valor" % self.estado)
            if self.origen not in ORIGENES:
                raise ValueError(
                    "estado %s exige origen en %r, recibido %r "
                    "(un valor sin origen es un modelo invalido: invariante I5)"
                    % (self.estado, ORIGENES, self.origen)
                )
        if self.estado == UNKNOWN:
            if self.valor is not None:
                raise ValueError("un atributo UNKNOWN no publica valor")
            if not self.motivos:
                raise ValueError(
                    "un atributo UNKNOWN necesita motivo estructurado "
                    "(DB-SI_FACT_MODEL.md §8)"
                )

    @property
    def conocido(self) -> bool:
        return self.estado == KNOWN

    @property
    def resuelto(self) -> bool:
        """KNOWN o ESTIMATED: hay valor, con la confianza que sea."""
        return self.estado in (KNOWN, ESTIMATED)

    def a_dict(self) -> dict:
        """Forma serializable (C7). Ordenada por el volcado, no por aquí."""
        return {
            "valor": self.valor,
            "estado": self.estado,
            "origen": self.origen,
            "confianza": self.confianza,
            "motivos": [{"codigo": m.codigo, "detalle": m.detalle} for m in self.motivos],
            "fuente": self.fuente,
        }

    def a_hecho(self, nombre: str, ambito: str, unidad: str = "", **extra) -> Hecho:
        """El único puente del modelo hacia `analyzer/hechos.py`.

        No se llama en ningún sitio de E1 —CAP-1…CAP-5 siguen recibiendo
        `Unit` a través del adaptador— y existe ya porque el contrato C5 lo
        fija: cuando una regla necesite citar un atributo del modelo como
        hecho, hay un camino y sólo uno.
        """
        comun = dict(
            nombre=nombre,
            ambito=ambito,
            tipo=_TIPO_DE_HECHO.get(self.origen or "", "derivado"),
            unidad=unidad,
            estado=self.estado,
            motivos=self.motivos,
            fuente=self.fuente or (self.origen or ""),
            procedencia=self.procedencia,
            confianza=self.confianza,
        )
        comun.update(extra)
        if self.estado in (KNOWN, ESTIMATED):
            comun["valor"] = self.valor
        return Hecho(**comun)


def observado(valor, confianza: Optional[str] = None, fuente: str = "") -> Atributo:
    return Atributo(valor=valor, estado=KNOWN, origen=OBSERVADO,
                    confianza=confianza, fuente=fuente)


def declarado(valor, confianza: Optional[str] = ALTA, fuente: str = "") -> Atributo:
    return Atributo(valor=valor, estado=KNOWN, origen=DECLARADO,
                    confianza=confianza, fuente=fuente)


def derivado(valor, confianza: Optional[str] = None, fuente: str = "") -> Atributo:
    return Atributo(valor=valor, estado=KNOWN, origen=DERIVADO,
                    confianza=confianza, fuente=fuente)


def supuesto(valor, confianza: Optional[str] = MEDIA, fuente: str = "") -> Atributo:
    """Hipótesis del sistema: `ESTIMATED`, nunca `KNOWN`. Un supuesto que se
    publica como conocido es la familia entera del Bug #1."""
    return Atributo(valor=valor, estado=ESTIMATED, origen=SUPUESTO,
                    confianza=confianza, fuente=fuente)


def desconocido(codigo: str, detalle: str) -> Atributo:
    """`UNKNOWN` con motivo obligatorio. No hay forma de construir un
    desconocido mudo, que es justamente el punto."""
    return Atributo(valor=None, estado=UNKNOWN,
                    motivos=(Motivo(codigo, detalle),))
