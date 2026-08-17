# -*- coding: utf-8 -*-
"""CAP-5 — `altura_evacuacion`, el dato que activa (o no) `C11`, `C15` y `C18`.

Diseño de referencia: `docs/prd/2026-08-10-cap5-altura-de-evacuacion.md` §4,
§4bis, §4ter, §4quater, §4quinquies.

**Qué es.** Anejo SI A del DB-SI, `concept_id`
`es.cte.db_si.anejo_a.altura_de_evacuacion`, ya ingerido en
`normativa/terminologia/dbsi_anejo_a.yaml`:

    «Máxima diferencia de cotas entre un origen de evacuación y la salida de
    edificio que le corresponda. A efectos de determinar la altura de
    evacuación de un edificio no se consideran las plantas más altas del
    edificio en las que únicamente existan zonas de ocupación nula.»

**Ámbito: el edificio, no la vivienda ni la planta.** Un análisis produce un
único hecho, a diferencia de `planta`/`ocupacion`/`limite_superficie_sector`
(uno por unidad). La norma define la magnitud sobre el edificio entero — la
máxima diferencia de cotas del conjunto—, así que replicarla por vivienda
sugeriría que cada vivienda tiene la suya, que es falso.

### Las dos fuentes, sin una tercera (PRD §4ter)

- **Declarada** (`ORIGEN_DECLARADO`): el arquitecto la escribe. `KNOWN`,
  confianza Alta. Es el único camino a `KNOWN` que existe.
- **Hipótesis** (`ORIGEN_HIPOTESIS_PLANTAS`): `(plantas - 1) × altura_libre_m`,
  sólo en `/api/generar`, donde esos dos datos existen. `ESTIMATED`,
  confianza **Baja**.
- **Desconocida**: ninguna de las dos. `UNKNOWN` con motivo.

`NO_APLICABLE` **no se usa**: todo edificio tiene una altura de evacuación
real, aunque ArchMuse no la conozca. La pregunta nunca deja de tener sentido.

### Por qué ArchMuse no puede calcular la magnitud real (PRD §4bis)

La definición exige **origen de evacuación**, **salida de edificio** (ambos
conceptos de `CAP-6`, bloqueado por el hallazgo §1.1 del plan) y **cota real**
(que ni el DXF ni `/api/generar` modelan: `altura_libre_m` es altura libre
suelo-techo, no una cota). Por eso la prohibición de un `KNOWN` derivado está
en la forma de la interfaz —no hay ningún parámetro por el que entre una
geometría o una cota— y no sólo en cómo se usa, igual que `planta.py` con la
inferencia geométrica.

### Por qué confianza Baja, y no Media como las hipótesis de CAP-2/CAP-4

La convención de nombre de CAP-4 y el mapeo de tipología de CAP-2 sólo fallan
en casos límite. Esta fórmula **siempre** se desvía, con sesgo conocido y en
dos direcciones distintas:

1. **Ignora el canto de forjado** → subestima (≈15 % medido en la ficha CAP-5
   del plan), justo sobre los saltos de 9/14/28 m.
2. **No sabe excluir las plantas altas de ocupación nula** que la propia
   definición manda descontar (trasteros, cuartos de instalaciones) → puede
   sobreestimar. ArchMuse no tiene ese dato y **no lo aproxima** (P5.4): se
   advierte, no se inventa un descuento.

Se usa el eje `confianza`, que el contrato ya tiene, en vez de inventar un
quinto estado o una bandera nueva en `Hecho`.

### La fórmula, y por qué `plantas - 1` (P5.1, resuelta con evidencia)

`edificio.plantas` **cuenta la planta baja**. No es una interpretación
cómoda; es lo que hace el resto del flujo `/api/generar`:

- `ai_generator._build_user_message` calcula
  `plantas_residenciales = edificio["plantas"] - (1 if planta_baja_comercial)`,
  es decir, resta *del total* la planta baja cuando es comercial.
- El prompt numera las plantas desde `"planta": 1`, y
  `evaluator.compute_floor_areas` + `app.py` leen `floor_areas.get(1, 0.0)`
  literalmente como `superficie_planta_baja`.

Luego, en un edificio de N plantas sobre rasante numeradas 1..N con la 1 a
cota de rasante, el origen de evacuación más alto está en la planta N, cuyo
suelo queda a `(N - 1) × altura_libre_m` sobre la salida de edificio:

    altura_evacuacion ≈ (plantas - 1) × altura_libre_m

Un edificio de una sola planta da 0,00 m — que es el valor correcto, no un
fallo: origen y salida están al mismo nivel.

**Advertencia registrada, no resuelta aquí:** la SPA rotula ese campo como
«Plantas sobre rasante» (`static/app.js`), lo que contradice la semántica
real del pipeline. Es la misma familia que la deuda de numeración que CAP-4
dejó anotada; corregirla exige tocar `evaluator.py`/`ai_generator.py`, ajenos
a CAP-5.

**Sólo plantas sobre rasante.** La hipótesis no modela evacuación ascendente
ni sótanos: `edificio.plantas` no los cuenta en ningún flujo, así que no hay
nada que excluir — pero tampoco se inventa una altura ascendente (los
umbrales de 2,80/6,00 m de `C11` ascendente quedan fuera de CAP-5).

### Lo que este módulo NO hace

No emite juicio: no hay `passed` ni veredicto (eso vive, y sólo como aviso, en
`avisos_altura_evacuacion.py`). No importa `evaluator.py` ni `normativa/`
—cita el `concept_id`, no la definición—, ni `planta.py`: `sobre_rasante` de
CAP-4 es un booleano sin magnitud y no aporta nada sumable (PRD §4ter).
"""
from __future__ import annotations

import re
from typing import Optional

from .hechos import ALTA, BAJA, ESTIMATED, KNOWN, UNKNOWN, Hecho, Motivo

# --- Orígenes admitidos -----------------------------------------------------
# Catálogo cerrado, mismo criterio que `planta.py`: una fuente nueva (p. ej.
# CAP-6, cuando exista) obliga a decidirlo aquí explícitamente, no a colarse
# por un `str` libre.

ORIGEN_DECLARADO = "declarado"
ORIGEN_HIPOTESIS_PLANTAS = "hipotesis_plantas_altura_libre"
_ORIGENES_VALIDOS = (ORIGEN_DECLARADO, ORIGEN_HIPOTESIS_PLANTAS)

# --- Motivos (`DB-SI_FACT_MODEL.md` §8) -------------------------------------

ALTURA_NO_DISPONIBLE = "EVAC_HEIGHT_NOT_AVAILABLE"

# --- Localizador normativo ---------------------------------------------------
# El `concept_id` del Anejo SI A, ya presente en el corpus ingerido — no el
# literal (que se resuelve con `normativa.definiciones.buscar`, fuera de
# `analyzer/`). Es el primero de los cinco hechos de CAP-1..CAP-5 que puede
# citar el Anejo SI A por su nombre exacto de concepto sin ingesta adicional.
CONCEPT_ID_ALTURA_EVACUACION = "es.cte.db_si.anejo_a.altura_de_evacuacion"

_CRITERIO_DECLARADO = (
    "CTE DB-SI, Anejo SI A: altura de evacuacion = maxima diferencia de cotas "
    "entre un origen de evacuacion y la salida de edificio que le corresponda; "
    "no se computan las plantas mas altas con unicamente zonas de ocupacion "
    "nula. ArchMuse no puede medir esa magnitud (exige origen de evacuacion, "
    "salida de edificio y cota real, ninguno modelado hoy): solo la admite "
    "declarada, o estimada por hipotesis explicita."
)

# Advertencia que viaja con TODA hipótesis, en el propio texto del hecho: es
# lo que separa "estimado" de "medido" para quien lee el informe y no el JSON.
_ADVERTENCIA_HIPOTESIS = (
    "No es la altura de evacuacion normativa: ignora el canto de forjado "
    "(subestima) y no descuenta las plantas altas de ocupacion nula que el "
    "Anejo SI A excluye (puede sobreestimar). Sirve para avisar, nunca para "
    "afirmar cumplimiento."
)

_FORMULA = "(plantas - 1) x altura_libre_m"


def _comun(ambito: str, tipo: str) -> dict:
    return dict(
        nombre="altura_evacuacion",
        ambito=ambito,
        tipo=tipo,
        unidad="m",
        referencia_normativa=CONCEPT_ID_ALTURA_EVACUACION,
        criterio_declarado=_CRITERIO_DECLARADO,
    )


def altura_evacuacion(
    ambito: str,
    *,
    valor_m: Optional[float] = None,
    origen: Optional[str] = None,
    plantas: Optional[int] = None,
    altura_libre_m: Optional[float] = None,
    motivo_no_disponible: Optional[str] = None,
    diagnostico_extra: Optional[dict] = None,
) -> Hecho:
    """El hecho `altura_evacuacion` del edificio.

    `valor_m=None` produce siempre `UNKNOWN`, sea cual sea `origen` — no hay
    fuente parcial que sostenga un valor. `motivo_no_disponible` deja que
    quien llama distinga "no se ha declarado" de "se ha declarado algo no
    interpretable": este modulo no ve el texto original, asi que no puede
    saberlo por si mismo (mismo contrato que `planta()`).

    `valor_m` distinto de `None` exige `origen` en `_ORIGENES_VALIDOS`. Con
    `ORIGEN_HIPOTESIS_PLANTAS` exige ademas los dos factores brutos: la
    trazabilidad hasta el dato de formulario no es opcional en una hipotesis.

    **No hay ningun camino de codigo que devuelva `KNOWN` con un `origen`
    distinto de `ORIGEN_DECLARADO`.** Es la prohibicion central de CAP-5
    (PRD §4, criterio de aceptacion 6).
    """
    extra = dict(diagnostico_extra or {})

    if valor_m is None:
        return Hecho(
            **_comun(ambito, "declarado"), estado=UNKNOWN,
            motivos=(Motivo(
                ALTURA_NO_DISPONIBLE,
                motivo_no_disponible
                or "No se ha declarado la altura de evacuacion del edificio, y "
                   "no hay datos suficientes para estimarla.",
            ),),
            explicacion=(
                "Altura de evacuacion no determinable: ni declarada por el "
                "arquitecto, ni estimable con los datos de este flujo. "
                "ArchMuse no la calcula a partir de la geometria."
            ),
            diagnostico=dict(
                {"origen": None, "plantas": plantas,
                 "altura_libre_m": altura_libre_m, "formula": None},
                **extra
            ),
        )

    if origen not in _ORIGENES_VALIDOS:
        raise ValueError(
            "altura_evacuacion(): valor_m=%r exige origen en %r, recibido %r"
            % (valor_m, _ORIGENES_VALIDOS, origen)
        )

    valor = float(valor_m)

    if origen == ORIGEN_DECLARADO:
        return Hecho(
            **_comun(ambito, "declarado"), estado=KNOWN, valor=valor,
            confianza=ALTA,
            fuente="declaracion del arquitecto",
            procedencia=("declarada por el arquitecto: %.2f m" % valor,),
            explicacion=(
                "Altura de evacuacion %.2f m, declarada para este proyecto "
                "(Anejo SI A). ArchMuse no la ha medido ni la ha estimado: la "
                "aporta el arquitecto, que si conoce la cota real." % valor
            ),
            diagnostico=dict(
                {"origen": ORIGEN_DECLARADO, "plantas": plantas,
                 "altura_libre_m": altura_libre_m, "formula": None},
                **extra
            ),
        )

    # origen == ORIGEN_HIPOTESIS_PLANTAS
    if plantas is None or altura_libre_m is None:
        raise ValueError(
            "altura_evacuacion(): la hipotesis exige los dos factores brutos "
            "(plantas=%r, altura_libre_m=%r) para poder trazarla"
            % (plantas, altura_libre_m)
        )
    return Hecho(
        **_comun(ambito, "derivado"), estado=ESTIMATED, valor=valor,
        confianza=BAJA,
        fuente="hipotesis sobre edificio.plantas y edificio.altura_libre_m (/api/generar)",
        procedencia=(
            "HIPOTESIS: %s = (%d - 1) x %.2f = %.2f m. %s"
            % (_FORMULA, plantas, float(altura_libre_m), valor,
               _ADVERTENCIA_HIPOTESIS),
        ),
        explicacion=(
            "Altura de evacuacion ESTIMADA en %.2f m a partir de %d plantas de "
            "%.2f m de altura libre. NO esta declarada ni medida. %s"
            % (valor, plantas, float(altura_libre_m), _ADVERTENCIA_HIPOTESIS)
        ),
        diagnostico=dict(
            {"origen": ORIGEN_HIPOTESIS_PLANTAS, "plantas": plantas,
             "altura_libre_m": float(altura_libre_m), "formula": _FORMULA},
            **extra
        ),
    )


# ---------------------------------------------------------------------------
# La fórmula de la hipótesis, aislada y pura.
# ---------------------------------------------------------------------------


def estimar_por_plantas(
    plantas: Optional[int],
    altura_libre_m: Optional[float],
) -> Optional[float]:
    """`(plantas - 1) × altura_libre_m`, o `None` si no es calculable.

    Devuelve `None` —nunca una estimacion parcial— si falta cualquiera de los
    dos factores, si `plantas < 1` o si `altura_libre_m <= 0` (PRD §4quater:
    no hay hipotesis con un solo factor). `plantas == 1` da `0.0`, que es el
    valor correcto para un edificio de una sola planta, no una ausencia.
    """
    if plantas is None or altura_libre_m is None:
        return None
    try:
        n = int(plantas)
        libre = float(altura_libre_m)
    except (TypeError, ValueError):
        return None
    if n < 1 or libre <= 0:
        return None
    return (n - 1) * libre


# ---------------------------------------------------------------------------
# Normalizador de la declaración del formulario.
# ---------------------------------------------------------------------------

_NUMERO = re.compile(r"^\d+(?:[.,]\d+)?$")


def normalizar_declaracion_altura(valor) -> Optional[float]:
    """Interpreta el campo "Altura de evacuacion (m)".

    Funcion pura, texto/numero -> `float` estrictamente positivo o `None`.
    **No construye ningun `Hecho`**: quien llame decide, con el `None`, que
    motivo de `UNKNOWN` usar — mismo contrato que
    `planta.normalizar_declaracion_planta`.

    Acepta coma o punto decimal ("17,5" y "17.5" son el mismo numero: el
    formulario es espanol, el JSON es ingles, y los dos llegan aqui).
    Rechaza —devolviendo `None`, nunca un `KNOWN` forzado— el vacio, el texto
    no numerico, el cero y los negativos: 0 m no es una altura de evacuacion
    fisicamente admisible para un edificio que se declara (PRD §6).
    """
    if valor is None:
        return None
    if isinstance(valor, bool):
        # `bool` es subclase de `int` en Python: True daria 1.0 m sin esto.
        return None
    if isinstance(valor, (int, float)):
        numero = float(valor)
        return numero if numero > 0 else None

    texto = str(valor).strip()
    if not texto:
        return None
    texto = re.sub(r"\s+", "", texto)
    # Sufijo de unidad tolerado ("17,5 m"), porque es lo que un arquitecto
    # escribe; cualquier otro texto ("planta 6", "alta") no se interpreta.
    if texto.lower().endswith("m"):
        texto = texto[:-1]
    if not _NUMERO.match(texto):
        return None
    numero = float(texto.replace(",", "."))
    return numero if numero > 0 else None


# ---------------------------------------------------------------------------
# Resolución de fuentes — el único sitio donde vive la precedencia.
# ---------------------------------------------------------------------------


def resolver_altura_evacuacion(
    ambito: str,
    *,
    valor_declarado_m: Optional[float] = None,
    motivo_no_disponible: Optional[str] = None,
    plantas: Optional[int] = None,
    altura_libre_m: Optional[float] = None,
) -> Hecho:
    """El hecho `altura_evacuacion` a partir de las fuentes disponibles.

    Precedencia, en un unico sitio para que los dos endpoints no la
    reimplementen cada uno a su manera:

    1. **Declaracion directa** -> `KNOWN`. Prevalece siempre. Si ademas
       habia factores para la hipotesis, se registran en `diagnostico`
       (`hipotesis_descartada`) por si algun dia interesa auditar la
       discrepancia — pero no se muestra como conflicto: una declaracion y
       una hipotesis debil no son dos fuentes del mismo rango (PRD CU7).
    2. **Hipotesis** `(plantas - 1) x altura_libre_m` -> `ESTIMATED`.
    3. Nada -> `UNKNOWN`.

    `/api/analizar` llama sin `plantas`/`altura_libre_m` porque ese flujo no
    tiene ningun equivalente a esos datos: la ausencia de hipotesis en el
    flujo DXF es estructural, no una comprobacion en tiempo de ejecucion
    (criterio de aceptacion 5).
    """
    estimada = estimar_por_plantas(plantas, altura_libre_m)

    if valor_declarado_m is not None:
        extra = {}
        if estimada is not None:
            extra["hipotesis_descartada"] = {
                "plantas": int(plantas),
                "altura_libre_m": float(altura_libre_m),
                "valor_m": estimada,
                "formula": _FORMULA,
            }
        return altura_evacuacion(
            ambito, valor_m=valor_declarado_m, origen=ORIGEN_DECLARADO,
            plantas=plantas, altura_libre_m=altura_libre_m,
            diagnostico_extra=extra,
        )

    if estimada is not None:
        return altura_evacuacion(
            ambito, valor_m=estimada, origen=ORIGEN_HIPOTESIS_PLANTAS,
            plantas=int(plantas), altura_libre_m=float(altura_libre_m),
        )

    return altura_evacuacion(
        ambito, motivo_no_disponible=motivo_no_disponible,
        plantas=plantas, altura_libre_m=altura_libre_m,
    )
