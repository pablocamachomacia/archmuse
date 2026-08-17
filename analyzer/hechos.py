# -*- coding: utf-8 -*-
"""Modelo de Hecho — implementación de `docs/design/DB-SI_FACT_MODEL.md` §6 y §7.

Un Hecho es un dato del proyecto con su procedencia y su estado de
conocimiento pegados al valor. **No emite juicio**: no tiene `passed`. La
ocupación no se cumple ni se incumple; la superficie tampoco.

Tres propiedades que este módulo hace cumplir por construcción, y que son la
razón de que exista en vez de devolver un `float` suelto:

1. **El estado es inseparable del valor** (§P4). Quien lee el número lee
   también si es `KNOWN`, `ESTIMATED` o `UNKNOWN`. Es el arreglo estructural
   de la familia del Bug #1: un `None` desnudo o un 0.0 «provisional» son
   indistinguibles de un dato bueno una vez viajan tres capas más arriba.
2. **Un `UNKNOWN` lleva motivo estructurado**, nunca sólo ausencia de valor
   (§8). El motivo es el producto: es lo que se le enseña al arquitecto.
3. **La confianza es cualitativa** (§P5). Alta/Media/Baja, jamás un
   porcentaje — misma disciplina que impuso retirar `TIPOLOGIA_BENCHMARKS`.

**Por qué no importa `normativa/`.** `analyzer/` sólo puede consumir
`normativa/` desde `cte_zonas.py` y por su superficie pública
(`tests/test_normativa_fronteras.py`). Así que `referencia_normativa` guarda
el `concept_id` de la definición, no la definición: quien la muestre la
resuelve con `normativa.definiciones.buscar(...)`. El hecho queda citable sin
que el evaluador acople el corpus.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

# --- Estados de conocimiento (`DB-SI_FACT_MODEL.md` §6) ---------------------
# Nunca silencio, nunca un `None` desnudo.

KNOWN = "KNOWN"                  # medido o declarado, con base suficiente
ESTIMATED = "ESTIMATED"          # obtenido por hipótesis explícita, que viaja con él
UNKNOWN = "UNKNOWN"              # no se ha podido determinar; lleva motivo obligatorio
NO_APLICABLE = "NO_APLICABLE"    # la pregunta no tiene sentido en este ámbito

ESTADOS = (KNOWN, ESTIMATED, UNKNOWN, NO_APLICABLE)

# --- Confianza (`DB-SI_FACT_MODEL.md` §7.2) --------------------------------

ALTA = "Alta"
MEDIA = "Media"
BAJA = "Baja"

CONFIANZAS = (ALTA, MEDIA, BAJA)


@dataclass(frozen=True)
class Motivo:
    """Por qué un hecho no es `KNOWN`.

    `codigo` es para el motor (estable, comparable, agrupable); `detalle` es
    para el arquitecto. Los dos son obligatorios: un código sin frase no se
    puede enseñar, y una frase sin código no se puede agrupar ni contar.
    """

    codigo: str
    detalle: str

    def __str__(self) -> str:  # pragma: no cover - conveniencia de depuración
        return f"{self.codigo}: {self.detalle}"


@dataclass(frozen=True)
class Hecho:
    """Un dato del proyecto con su procedencia. Campos de §7.1, sin añadidos.

    `valor` es `None` siempre que el estado no sea `KNOWN`/`ESTIMATED`. No se
    publica un número degradado «mientras tanto»: es el principio P6, y nace
    de una medición concreta — un área calculada sobre polígonos que se
    solapan es indistinguible de una correcta salvo que alguien vuelva a
    mirar la geometría.
    """

    nombre: str
    ambito: str
    tipo: str                       # observado | derivado | declarado | normativo
    unidad: str
    estado: str
    # `valor` es «el número o categoría» (§7.1): numérico para superficie u
    # ocupación, categórico para uso previsto. Por eso no está tipado a float.
    valor: Optional[Any] = None
    motivos: Tuple[Motivo, ...] = ()
    fuente: str = ""
    procedencia: Tuple[str, ...] = ()
    referencia_normativa: Optional[str] = None   # concept_id, no el literal
    criterio_declarado: Optional[str] = None
    confianza: Optional[str] = None
    explicacion: str = ""
    diagnostico: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.estado not in ESTADOS:
            raise ValueError(f"estado desconocido: {self.estado!r}")
        if self.estado in (KNOWN, ESTIMATED) and self.valor is None:
            raise ValueError(f"{self.nombre}: estado {self.estado} exige un valor")
        if self.estado == UNKNOWN and self.valor is not None:
            raise ValueError(
                f"{self.nombre}: un hecho UNKNOWN no publica valor "
                "(DB-SI_FACT_MODEL.md P6)"
            )
        if self.estado == UNKNOWN and not self.motivos:
            raise ValueError(
                f"{self.nombre}: un hecho UNKNOWN necesita motivo estructurado "
                "(DB-SI_FACT_MODEL.md §8)"
            )

    @property
    def conocido(self) -> bool:
        return self.estado == KNOWN

    @property
    def motivo_principal(self) -> Optional[Motivo]:
        """El primero de la lista. Quien construye el hecho los ordena por
        gravedad, para que la ficha pueda enseñar uno solo sin mentir."""
        return self.motivos[0] if self.motivos else None


def hecho_a_dict(hecho: Hecho) -> dict:
    """Serialización JSON de un `Hecho`, para respuestas HTTP.

    No existía hasta ahora un serializador genérico — cada módulo (CAP-1..5)
    volcaba sus propios campos a mano dentro de `diagnostico`. Se añade aquí,
    no en `analyzer/api_serializer.py`, porque es la forma canónica del
    dataclass, no una decisión de qué muestra la SPA — `api_serializer.py` (u
    otro consumidor) puede envolver esto, no reimplementarlo.

    `no_encontrado` es una comodidad derivada de `estado` (nunca un campo
    aparte que pudiera desincronizarse): `True` solo cuando `estado ==
    UNKNOWN`. No hay `dict_a_hecho` correspondiente — nada reconstruye un
    `Hecho` desde JSON todavía; quien lo necesite serializado y guardado tal
    cual (p. ej. `analyzer/storage.py::guardar_pliego`) guarda este mismo
    dict, no reconstruye el dataclass al leerlo."""
    return {
        "nombre": hecho.nombre,
        "estado": hecho.estado,
        "valor": hecho.valor,
        "unidad": hecho.unidad,
        "confianza": hecho.confianza,
        "cita": hecho.criterio_declarado,
        "fuente": hecho.fuente,
        "no_encontrado": hecho.estado == UNKNOWN,
        "motivo": hecho.motivo_principal.detalle if hecho.motivo_principal else None,
    }
