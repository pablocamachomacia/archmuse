# -*- coding: utf-8 -*-
"""CAP-4 — `planta`, el ámbito normativo que la Tabla 2.1 indexa y ArchMuse no modelaba.

Diseño de referencia: `docs/prd/2026-08-09-cap4-modelo-de-planta.md` §4, §4bis, §6.

**Qué es exactamente.** El DB-SI razona casi siempre por planta: *"salida de
planta"*, *"plantas de vivienda"*, *"toda planta que no sea zona de ocupación
nula"*, *"plantas sobre rasante"* (`docs/audits/DB-SI_IMPLEMENTATION_PLAN.md`,
ficha CAP-4). ArchMuse tiene `Room` -> `Unit`; no tiene planta. Este módulo
publica el hecho, con la misma disciplina que `uso_previsto.py`: **sin parseo
de texto dentro**. Recibe `numero`/`sobre_rasante` ya normalizados —el texto
libre del formulario se interpreta en la capa que lo recibe, no aquí— y
`origen` ya decidido por quien llama, nunca inferido de una geometría ni de un
nombre de vivienda.

**Las tres fuentes, sin una cuarta.** (PRD §4bis)

- **Declarada** (`ORIGEN_DECLARADO`): el arquitecto la escribe en el
  formulario de `/api/analizar`. `KNOWN`, confianza Alta.
- **Estimada por convención** (`ORIGEN_CONVENCION_NOMBRE`): el prefijo
  `Planta <n> · <nombre>` que ya usa `/api/generar`
  (`evaluator._PLANTA_NAME_PATTERN`, sin tocar ni duplicar ese módulo).
  `ESTIMATED`, confianza Media — es una inferencia mecánica sobre un patrón de
  texto determinista, no una declaración directa.
- **Desconocida**: ninguna de las dos anteriores. `UNKNOWN` con motivo.

**Lo que este módulo prohíbe por diseño, no sólo por omisión.** Ningún nombre
de vivienda (`VT1/3`, `VT2/2`...) se interpreta como planta: el número tras
`VT` es el tipo de vivienda de la convención de rotulado del DXF
(`group_rooms_by_unit_label`), sin relación semántica con la posición en el
edificio. Y ninguna geometría (solape de huellas, cota Z) se usa como fuente
— la propia ficha de CAP-4 lo advierte citando la lección que ya costó
`_discard_container_candidates`. No hay parámetro en esta función que acepte
ninguna de las dos cosas: la prohibición está en la forma de la interfaz, no
sólo en cómo se usa.

**`NO_APLICABLE` no se usa para este hecho.** A diferencia de la densidad de
ocupación (que sí tiene una categoría "zona de ocupación nula" propia de la
Tabla 2.1), toda unidad ocupable pertenece a alguna planta; no hay un análogo
normativo de "esto no tiene planta".

**`sobre_rasante` viaja en el mismo hecho, aunque CAP-4 v1 no tenga ningún
consumidor para él.** Lo pide CAP-5 (altura de evacuación, *"Fact derivado a
partir de CAP-4, o declarado"*); es más barato declararlo ahora que añadirlo
después. Es independiente del número: puede ser `None` (no declarado) aunque
`numero` sí lo esté.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional, Tuple

from .hechos import ALTA, ESTIMATED, KNOWN, MEDIA, UNKNOWN, Hecho, Motivo

# --- Orígenes admitidos -----------------------------------------------------
# Cerrado a propósito: cualquier fuente nueva (p. ej. geometría) exige decidir
# aquí, explícitamente, si se admite — no colarse por un `str` libre.

ORIGEN_DECLARADO = "declarado"
ORIGEN_CONVENCION_NOMBRE = "convencion_nombre"
_ORIGENES_VALIDOS = (ORIGEN_DECLARADO, ORIGEN_CONVENCION_NOMBRE)

# --- Motivos -----------------------------------------------------------------

PLANTA_NO_DISPONIBLE = "FLOOR_NOT_AVAILABLE"

# --- Localizador normativo ---------------------------------------------------
# No hay una definición de "planta" transcrita del Anejo SI A en el corpus
# ingerido (a diferencia de "uso previsto" u "ocupación"): se cita la lista de
# apartados que razonan por planta, no una definición inventada.
CITA_PLANTA = (
    "DB-SI: SI 1 ap. 1, SI 3 ap. 2/3/9, SI 6 ap. 3 (razonan por planta; "
    "ninguno define el término en el corpus ingerido)"
)


def planta(
    ambito: str,
    *,
    numero: Optional[int] = None,
    sobre_rasante: Optional[bool] = None,
    origen: Optional[str] = None,
    motivo_no_disponible: Optional[str] = None,
) -> Hecho:
    """El hecho `planta` de una unidad.

    `numero=None` produce siempre `UNKNOWN`, sea cual sea `origen`: no hay
    fuente parcial que sostenga un valor. `motivo_no_disponible` deja que
    quien llama (el normalizador del formulario, o el propio flujo) diga si
    fue "no declarada" o "declarada pero no interpretable" — este módulo no
    lee el texto original, así que no puede saberlo por sí mismo.

    `numero` distinto de `None` exige `origen` en `_ORIGENES_VALIDOS`: un
    valor sin fuente reconocida es exactamente el silencio que el contrato de
    hechos prohíbe.
    """
    comun = dict(
        nombre="planta",
        ambito=ambito,
        tipo="declarado",
        unidad="",
        criterio_declarado=CITA_PLANTA,
    )

    if numero is None:
        return Hecho(
            **comun, estado=UNKNOWN,
            fuente="",
            motivos=(Motivo(
                PLANTA_NO_DISPONIBLE,
                motivo_no_disponible
                or "No se ha declarado la planta de este análisis, ni consta "
                   "por convención de nombre.",
            ),),
            explicacion="Planta no determinable: ni declarada ni por convención.",
            diagnostico={"origen": None, "sobre_rasante": sobre_rasante},
        )

    if origen not in _ORIGENES_VALIDOS:
        raise ValueError(
            "planta(): numero=%r exige origen en %r, recibido %r"
            % (numero, _ORIGENES_VALIDOS, origen)
        )

    if origen == ORIGEN_DECLARADO:
        return Hecho(
            **comun, estado=KNOWN, valor=numero, confianza=ALTA,
            fuente="declaracion del arquitecto",
            procedencia=("declarada por el arquitecto: planta %d" % numero,),
            explicacion="Planta %d, declarada para este análisis." % numero,
            diagnostico={
                "origen": ORIGEN_DECLARADO,
                "sobre_rasante": sobre_rasante,
            },
        )

    # origen == ORIGEN_CONVENCION_NOMBRE
    return Hecho(
        **comun, estado=ESTIMATED, valor=numero, confianza=MEDIA,
        fuente="convencion de nombre de unidad ('Planta <n> - <nombre>')",
        procedencia=(
            "HIPOTESIS: nombre de unidad casa 'Planta %d - ...' -> planta %d"
            % (numero, numero),
        ),
        explicacion=(
            "Planta %d, NO declarada explícitamente: se ha leído del nombre "
            "de la unidad. Es una inferencia sobre un patrón de texto, no una "
            "declaración directa." % numero
        ),
        diagnostico={
            "origen": ORIGEN_CONVENCION_NOMBRE,
            "sobre_rasante": sobre_rasante,
        },
    )


# ---------------------------------------------------------------------------
# Normalizador de la declaración del formulario (`/api/analizar`).
# ---------------------------------------------------------------------------
#
# Función pura, texto -> (numero, sobre_rasante) o `None`. **No construye
# ningún `Hecho`**: quien llame decide, con el `None`, qué motivo de UNKNOWN
# usar (campo vacío vs. texto no interpretable son casos distintos para el
# arquitecto, aunque aquí produzcan la misma señal).
#
# `sobre_rasante` se deriva del propio número, con el significado
# arquitectónico real — no un simple "es distinto de cero" — porque es el que
# CAP-5 necesitará para no confundir un sótano con una planta elevada:
#
#     sobre_rasante = numero > 0
#
# Planta baja (numero=0) NO es "sobre rasante": está en la cota de rasante,
# ni por encima ni por debajo. Un sótano (numero<0) tampoco lo es, por
# definición. Sólo las plantas 1, 2, 3... lo son.

_NUMERO_ORDINAL = re.compile(r"^(-?\d+)\s*(?:ER|O|A|°|º|ª)?\.?$")


def _sin_acentos_mayusculas(texto: str) -> str:
    """Mayúsculas y sin acentos. Misma convención que `evaluator._normalize` /
    `superficie_util._normalizar`, reimplementada aquí para que este módulo
    (CAP-4) no dependa de `evaluator.py` — igual que ya decidió CAP-1."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return sin_tildes.upper().strip()


def normalizar_declaracion_planta(
    texto: Optional[str],
) -> Optional[Tuple[int, Optional[bool]]]:
    """Interpreta el campo de formulario "planta de este análisis".

    Devuelve `(numero, sobre_rasante)` si el texto es interpretable, o `None`
    si no lo es — vacío, ambiguo, o cualquier cosa que no case los patrones
    reconocidos. **Nunca inventa una planta**: ante la duda, `None`, para que
    quien llame construya un `planta()` `UNKNOWN` en vez de un `KNOWN` falso.

    Patrones reconocidos (case/acentos/espacios insensibles):

    - `"Planta baja"` -> `(0, False)`
    - `"Planta <n>"`, con `<n>` entero, con o sin sufijo ordinal
      (`"Planta 3ª"`, `"Planta 1º"`, `"Planta 1er"`) -> `(n, n > 0)`
    - `"Sótano <n>"`, con `<n>` entero positivo o ya negativo
      (`"Sótano 1"` y `"Sótano -1"` son la misma planta) -> `(-abs(n), False)`

    **No reconoce, a propósito:**

    - Ningún patrón `VT<n>/<n>` — no es una fuente admitida para planta bajo
      ninguna circunstancia (PRD §4, §6): ni siquiera como último recurso.
    - `"Sótano"` sin número — no se asume "sótano 1" por ser el caso más
      común; sería completar el vacío con un valor por defecto que pasa por
      dato real (`DECISION_ENGINE.md` §12).
    - Cualquier texto no numérico ("varias", "?", "varios pisos"...).
    """
    if not texto or not texto.strip():
        return None

    limpio = _sin_acentos_mayusculas(texto)
    limpio = re.sub(r"\s+", " ", limpio)

    if limpio == "PLANTA BAJA":
        return (0, False)

    if limpio.startswith("PLANTA "):
        resto = limpio[len("PLANTA "):].strip()
        match = _NUMERO_ORDINAL.match(resto)
        if not match:
            return None
        numero = int(match.group(1))
        return (numero, numero > 0)

    if limpio.startswith("SOTANO "):
        resto = limpio[len("SOTANO "):].strip()
        match = _NUMERO_ORDINAL.match(resto)
        if not match:
            return None
        numero = int(match.group(1))
        if numero == 0:
            # "Sotano 0" no es interpretable: un sótano es, por definición,
            # bajo rasante; 0 es la propia rasante (planta baja).
            return None
        return (-abs(numero), False)

    return None
