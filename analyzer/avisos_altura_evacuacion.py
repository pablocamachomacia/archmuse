# -*- coding: utf-8 -*-
"""CAP-5 — avisos condicionales de `C11`, `C15` y `C18`. Avisos, nunca comprobaciones.

Diseño de referencia: `docs/prd/2026-08-10-cap5-altura-de-evacuacion.md` §4,
§6, §7; `docs/audits/DB-SI_REVIEW.md`, fichas `C11`, `C15`, `C18` (las tres
recomiendan explicitamente "valorar el aviso condicional", y las tres
mantienen la regla en `UNKNOWN`).

### Lo que estas tres funciones NO son

**No son reglas.** Ninguna devuelve un objeto con `passed`, ninguna produce
un `IssueReport`, ninguna se registra en `classify_problems`, y
`evaluator.py` no se modifica. Un aviso dice *"con esta altura, revisa esto"*;
una regla dice *"esto cumple"* o *"esto no cumple"*. `C11`, `C15` y `C18`
siguen en `UNKNOWN` despues de CAP-5, exactamente igual que antes:

- `C11` necesita ademas el **tipo de proteccion de la escalera** (dato
  constructivo, ningun flujo lo tiene).
- `C15` necesita ademas **salidas accesibles y zonas de refugio**.
- `C18` necesita ademas la **geometria del viario y del entorno**.

Lo unico que CAP-5 aporta es la *condicion de activacion* de los tres: la
altura de evacuacion. Convertir eso en un veredicto seria opinar sobre lo que
no se ha medido — y en `C15` el error seria simetrico: afirmar que no aplica
(h <= 28 m) es tan infundado como afirmar que se incumple.

### Un hecho `UNKNOWN` no dispara nada

D3 de `DB-SI_DECISIONS.md`: un insumo `UNKNOWN` no sostiene ninguna
afirmacion, **ni siquiera condicional**. No hay "aviso por defecto" ni "aviso
conservador ante la duda": silencio explicito, con el hecho disponible para
quien quiera saber por que no hay aviso. `NO_APLICABLE` tampoco dispara nada
(el hecho nunca lo produce, pero la comprobacion no depende de esa promesa).

### `>=` en los tres umbrales, y por que se documenta

El PRD (§6, criterio 9) fija `>=` para los tres. El literal de la norma es
estricto en los tres casos (`C11`: no protegida admisible **con h <= 14 m**;
`C15`: **superior a 28 m**; `C18`: espacio de maniobra **cuando h > 9 m**),
asi que en el punto exacto del umbral estas funciones avisan un caso antes de
lo que la norma exigiria. Es deliberado y es la direccion segura: un aviso de
mas hace revisar un proyecto que esta justo en el limite; un aviso de menos lo
deja pasar. Como ninguno de los tres produce veredicto, un `>=` no puede
generar un `FAIL` falso — a diferencia de lo que pasaria en una regla.

### El texto del aviso dice si la altura es estimada

Riesgo #3 de `DB-SI_IMPLEMENTATION_PLAN.md` §14, el mas citado del plan para
CAP-5: la hipotesis leida como un hecho. Marcarla solo en el JSON no basta
—el arquitecto lee el informe, no el JSON—, asi que **cada uno de los tres
mensajes lo repite por su cuenta**, sin depender de una advertencia global
que no se sabria a cual de los tres aplica.

### `C18` no se vincula a `evaluate_retranqueos` (R25)

`DB-SI_REVIEW.md` lo prohibe por escrito en la ficha `C18`: un retranqueo
insuficiente **no es** un espacio de maniobra insuficiente (el espacio de
maniobra puede resolverse en el viario publico). La correlacion es razonable
y probablemente cierta, pero convertirla en exigencia DB-SI seria fabricar
una norma. Este modulo no importa nada de `evaluator.py`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .hechos import ESTIMATED, KNOWN, Hecho

# --- Umbrales (m) ------------------------------------------------------------

UMBRAL_C11_M = 14.0   # DB-SI 3 ap. 5, Tabla 5.1 — escalera no protegida
UMBRAL_C15_M = 28.0   # DB-SI 3 ap. 9 — evacuacion de personas con discapacidad
UMBRAL_C18_M = 9.0    # DB-SI 5 ap. 1.2 — espacio de maniobra de bomberos

# --- Localizadores normativos ------------------------------------------------

LOCALIZADOR_C11 = "DB-SI / SI 3 / ap. 5 / Tabla 5.1"
LOCALIZADOR_C15 = "DB-SI / SI 3 / ap. 9"
LOCALIZADOR_C18 = "DB-SI / SI 5 / ap. 1.2"

# Codigos propios de aviso, deliberadamente distintos de cualquier codigo de
# `IssueReport`: quien los vea en el payload no debe poder confundirlos con
# una incidencia de cumplimiento.
CODIGO_C11 = "DB-SI-3-AVISO-ESCALERA-14M"
CODIGO_C15 = "DB-SI-3-AVISO-DISCAPACIDAD-28M"
CODIGO_C18 = "DB-SI-5-AVISO-BOMBEROS-9M"


@dataclass(frozen=True)
class AvisoAltura:
    """Un aviso informativo. **Sin `passed`, sin severidad, sin veredicto.**

    Lleva su cita porque el PRD §7 exige que cada aviso la muestre; devolver
    un `str` pelado obligaria a que `app.py` reconstruyera la cita por su
    cuenta y a que las tres quedaran duplicadas fuera de este modulo.
    Cualquier consumidor que busque un `passed` aqui no lo encontrara: no es
    un `Result` degradado, es otra cosa.
    """

    codigo: str
    regla: str            # C11 / C15 / C18, para trazar contra DB-SI_REVIEW.md
    titulo: str
    localizador: str
    umbral_m: float
    altura_m: float
    altura_estimada: bool
    mensaje: str


def _aplicable(hecho: Optional[Hecho], umbral_m: float) -> bool:
    """`True` solo si el hecho tiene valor utilizable y alcanza el umbral."""
    if hecho is None or hecho.estado not in (KNOWN, ESTIMATED):
        return False
    if hecho.valor is None:
        return False
    return float(hecho.valor) >= umbral_m


def _procedencia(hecho: Hecho) -> str:
    """La coletilla que distingue una altura declarada de una estimada, en el
    propio texto del aviso — no solo en el JSON (riesgo #3 del plan)."""
    if hecho.estado == ESTIMATED:
        return (
            "La altura es una ESTIMACION (%s), no una medicion: ignora el "
            "canto de forjado y no descuenta plantas de ocupacion nula. "
            "Verificala antes de tomar ninguna decision."
            % (hecho.diagnostico or {}).get("formula", "hipotesis")
        )
    return "Altura declarada por el arquitecto."


def aviso_c11(hecho: Optional[Hecho]) -> Optional[AvisoAltura]:
    """Proteccion de las escaleras (DB-SI 3, ap. 5, Tabla 5.1).

    Para uso Residencial Vivienda y evacuacion descendente, una escalera **no
    protegida** solo es admisible con altura de evacuacion <= 14 m; por encima
    exige escalera protegida (hasta 28 m) o especialmente protegida. ArchMuse
    no conoce el tipo de proteccion de ninguna escalera —ni siquiera si hay
    escalera modelada—, asi que esto es un aviso para que el arquitecto lo
    verifique, no una comprobacion.
    """
    if not _aplicable(hecho, UMBRAL_C11_M):
        return None
    altura = float(hecho.valor)
    return AvisoAltura(
        codigo=CODIGO_C11,
        regla="C11",
        titulo="Verificar la proteccion de la escalera",
        localizador=LOCALIZADOR_C11,
        umbral_m=UMBRAL_C11_M,
        altura_m=altura,
        altura_estimada=(hecho.estado == ESTIMATED),
        mensaje=(
            "Altura de evacuacion %.2f m (>= %.0f m): una escalera NO protegida "
            "deja de ser admisible para uso Residencial Vivienda en evacuacion "
            "descendente; DB-SI 3, Tabla 5.1 exige escalera protegida hasta "
            "28 m, o especialmente protegida. ArchMuse no conoce el tipo de "
            "escalera de este proyecto: esto es un aviso, no una comprobacion "
            "de cumplimiento. %s"
            % (altura, UMBRAL_C11_M, _procedencia(hecho))
        ),
    )


def aviso_c15(hecho: Optional[Hecho]) -> Optional[AvisoAltura]:
    """Evacuacion de personas con discapacidad (DB-SI 3, ap. 9).

    En uso Residencial Vivienda el articulo se activa con altura de evacuacion
    superior a 28 m: toda planta que no sea zona de ocupacion nula y sin
    salida de edificio accesible necesita paso a un sector alternativo o zona
    de refugio. ArchMuse no identifica salidas accesibles ni zonas de refugio,
    asi que aqui solo se avisa de que el articulo **entra en juego**.
    """
    if not _aplicable(hecho, UMBRAL_C15_M):
        return None
    altura = float(hecho.valor)
    return AvisoAltura(
        codigo=CODIGO_C15,
        regla="C15",
        titulo="Evacuacion de personas con discapacidad: el articulo aplica",
        localizador=LOCALIZADOR_C15,
        umbral_m=UMBRAL_C15_M,
        altura_m=altura,
        altura_estimada=(hecho.estado == ESTIMATED),
        mensaje=(
            "Altura de evacuacion %.2f m (>= %.0f m): DB-SI 3 ap. 9 pasa a ser "
            "exigible en uso Residencial Vivienda. Toda planta que no sea zona "
            "de ocupacion nula y que no tenga salida de edificio accesible "
            "necesita salida de planta accesible a un sector alternativo, o "
            "zona de refugio. ArchMuse no identifica salidas accesibles ni "
            "zonas de refugio: no puede decir si se cumple ni si se incumple. %s"
            % (altura, UMBRAL_C15_M, _procedencia(hecho))
        ),
    )


def aviso_c18(hecho: Optional[Hecho]) -> Optional[AvisoAltura]:
    """Aproximacion y entorno para bomberos (DB-SI 5, ap. 1.2).

    Con altura de evacuacion descendente mayor que 9 m es obligatorio un
    espacio de maniobra con anchura libre >= 5 m, separacion maxima a fachada
    segun altura, acceso a <= 30 m, pendiente <= 10 % y resistencia al
    punzonamiento. Nada de eso esta modelado (el DXF no contiene entorno
    urbano). **No se vincula al retranqueo (R25)**, por prohibicion expresa de
    `DB-SI_REVIEW.md`.
    """
    if not _aplicable(hecho, UMBRAL_C18_M):
        return None
    altura = float(hecho.valor)
    return AvisoAltura(
        codigo=CODIGO_C18,
        regla="C18",
        titulo="Espacio de maniobra para bomberos: exigible",
        localizador=LOCALIZADOR_C18,
        umbral_m=UMBRAL_C18_M,
        altura_m=altura,
        altura_estimada=(hecho.estado == ESTIMATED),
        mensaje=(
            "Altura de evacuacion %.2f m (>= %.0f m): DB-SI 5 ap. 1.2 exige "
            "espacio de maniobra para bomberos (anchura libre >= 5 m, "
            "separacion a fachada segun altura, distancia a los accesos "
            "<= 30 m, pendiente <= 10 %%). ArchMuse no modela el viario ni el "
            "entorno de la parcela, y el retranqueo urbanistico NO es "
            "equivalente a este espacio de maniobra: esto es un aviso, no una "
            "comprobacion. %s"
            % (altura, UMBRAL_C18_M, _procedencia(hecho))
        ),
    )


def avisos_altura_evacuacion(hecho: Optional[Hecho]) -> List[AvisoAltura]:
    """Los avisos que dispara un hecho, de umbral mas alto a mas bajo.

    Los tres son **independientes, no escalonados con exclusion mutua**: un
    edificio de mas de 28 m dispara los tres a la vez, cada uno con su cita y
    su propia advertencia de estimacion (PRD §6).
    """
    candidatos = (aviso_c15(hecho), aviso_c11(hecho), aviso_c18(hecho))
    return [a for a in candidatos if a is not None]
