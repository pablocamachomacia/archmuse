# -*- coding: utf-8 -*-
"""CAP-4 — `C01`, límite de 2.500 m² de superficie por sector de incendio (DB-SI 1, ap. 1).

Diseño de referencia: `docs/prd/2026-08-09-cap4-modelo-de-planta.md` §4ter.

**Primera regla real que consume el hecho `planta` (CAP-4).** Hasta aquí, CAP-4
solo corregía el ámbito de `ocupacion`; `C01` es la primera capacidad
normativa que se activa gracias a `planta` — condición de cierre de CAP-4,
no una tarea opcional.

---

### Qué exige la norma, y qué compara este módulo en su lugar

DB-SI 1, apartado 1 (corregido de `"CTE-DB-SI-3"`, la cita que ya usa
`evaluator.evaluate_fire_compartmentation` para un proxy geométrico distinto
y no relacionado — ver `app.py`, nota de colisión junto al import de
`_PLANTA_NAME_PATTERN`): 2.500 m² como superficie máxima de un sector de
incendio, con el sector coincidiendo con la planta en el caso residencial sin
más declaración.

La norma mide **superficie construida**. `DB-SI_FACT_MODEL.md` §3.3 ya
estableció, con evidencia medida (reconstrucción por casco convexo: error del
−24 % al +49 % sobre `ejemplo.dxf`), que **`superficie_construida` no es
obtenible del DXF actual**. Este módulo no inventa esa fuente: compara la
**suma de `superficie_util_db_si`** (CAP-1, `analyzer/superficie_util.py` —
incluye terrazas y zonas de ocupación nula, D6 de `DB-SI_DECISIONS.md`) de
las unidades cuya `planta` resuelve al mismo número, declarada explícitamente
como proxy, nunca renombrada como superficie construida.

### La dirección del error, y por qué `C01` nunca puede dar `PASS`

`superficie_util_db_si` mide a cara interior de muro — es **sistemáticamente
menor o igual** que la construida real. Por tanto:

- **suma ≥ 2.500 m² → `FAIL`** (evidencia suficiente): si el proxy, que
  subestima, ya supera el límite, la construida real también lo supera.
  Dirección segura.
- **suma < 2.500 m² → `UNKNOWN`, nunca `PASS`**: el proxy subestima por un
  margen no acotado con fiabilidad (hasta +49 % medido). Que el proxy esté
  por debajo no prueba que la construida real lo esté.

Con los datos que el DXF puede dar hoy, este módulo **no tiene ningún camino
de código que produzca `PASS`** — no es una limitación de esta
implementación, es el techo real que impone no tener `superficie_construida`.

### Por qué esto se modela como un `Hecho`, no como un tercer tipo

No se inventa un modelo de estado PASS/FAIL/UNKNOWN paralelo al de
`hechos.py`. Se reutiliza `Hecho` para una pregunta que sí es binaria con
evidencia — *"¿hay evidencia suficiente, en dirección segura, de que la
superficie de esta planta alcanza o supera 2.500 m²?"*— y esa pregunta solo
tiene dos respuestas legítimas: `KNOWN` (sí, con el acumulado como `valor`) o
`UNKNOWN` (no se puede afirmar, con motivo). No existe un tercer estado
"`KNOWN`, no se supera": eso exigiría `superficie_construida`, que no existe.
Así, la imposibilidad de `PASS` no es una comprobación en tiempo de
ejecución: es que el contrato de `Hecho` no tiene ninguna forma de
expresarlo para esta pregunta.

### Agregación por planta, monotonía, y el caso de superficie `UNKNOWN`

Se agrupan las unidades por el **número** de `planta` (CAP-4) que comparten
— nunca por vivienda, y nunca asumiendo "misma planta por defecto" para una
unidad cuya `planta` es `UNKNOWN` (esa unidad recibe su propio resultado
`UNKNOWN`, sin agregarse con nadie).

Dentro de un grupo, se suman primero las superficies `KNOWN`. Si esa suma
parcial ya alcanza 2.500 m², el veredicto es `FAIL` **aunque falte alguna
unidad por medir**: añadir una superficie no negativa nunca puede hacer
bajar un acumulado que ya cruzó el umbral (razonamiento monótono,
`DB-SI_DECISIONS.md` D3). Si la suma parcial no alcanza 2.500 m², el
veredicto es `UNKNOWN` — falte o no falte alguna unidad por medir: el motivo
cambia (superficie insuficiente vs. superficie insuficiente *y además*
incompleta), pero el veredicto no.

### Lo que este módulo NO hace

No evalúa el EI 60 entre sectores (bloqueado por `CAP-8`, dato constructivo
fuera del alcance del DXF). No es una comprobación de evacuación ni de
sectorización física real (muros, puertas cortafuego) — solo el límite de
superficie que el propio apartado 1 fija como primer criterio, y nada más.
No toca `evaluator.py`, no reutiliza ni retagea `"CTE-DB-SI-3"`, y no importa
nada de `analyzer/planta.py` ni `analyzer/evaluator.py`: recibe los `Hecho`
ya calculados, como cualquier otro módulo de CAP-3/CAP-4.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from .hechos import ALTA, BAJA, ESTIMATED, KNOWN, MEDIA, UNKNOWN, Hecho, Motivo

# --- Umbral y localizador normativo -----------------------------------------

LIMITE_M2 = 2500.0
LOCALIZADOR_C01 = "DB-SI / SI 1 / ap. 1"

# Código propio de esta regla, estable y citable — deliberadamente distinto
# de "CTE-DB-SI-3" (el código que ya usa el proxy geométrico no relacionado
# de `evaluator.evaluate_fire_compartmentation`). Cualquier futuro
# `IssueReport`/serializador que exponga este veredicto debe usar este
# código, no inventar otro ni reutilizar el existente.
CODIGO_C01 = "DB-SI-1-SECTOR-2500"

# --- Motivos (`DB-SI_FACT_MODEL.md` §8) -------------------------------------

PLANTA_NO_DISPONIBLE = "FLOOR_NOT_AVAILABLE"
SUPERFICIE_INSUFICIENTE = "AREA_PROXY_BELOW_THRESHOLD"

_CRITERIO_DECLARADO = (
    "DB-SI 1 ap. 1: limite de 2.500 m2 de superficie construida por sector "
    "de incendio; el sector coincide con la planta en el caso residencial "
    "sin mas declaracion. Comparado aqui contra la suma de "
    "superficie_util_db_si (proxy a cara interior de muro, nunca superficie "
    "construida)."
)


def _peor_confianza(*valores: Optional[str]) -> Optional[str]:
    """Eslabón más débil. Reimplementada aquí (no importada de
    `ocupacion.py`) para que este módulo no dependa de otro módulo de
    CAP-3/CAP-4 más que de `hechos.py` — mismo criterio de aislamiento que ya
    usan `superficie_util.py` y `planta.py` para sus propias utilidades
    pequeñas."""
    orden = {ALTA: 3, MEDIA: 2, BAJA: 1}
    presentes = [v for v in valores if v in orden]
    if not presentes:
        return None
    return min(presentes, key=lambda v: orden[v])


def _comun(ambito: str) -> dict:
    return dict(
        nombre="limite_superficie_sector",
        ambito=ambito,
        tipo="derivado",
        unidad="m2",
        fuente="calculado: suma de superficie_util_db_si de las unidades de la planta",
        referencia_normativa=LOCALIZADOR_C01,
        criterio_declarado=_CRITERIO_DECLARADO,
    )


def _sin_planta(superficie: Hecho) -> Hecho:
    """El resultado de una unidad cuya `planta` es `UNKNOWN`: no se agrega
    con ninguna otra bajo el supuesto de "misma planta por defecto"."""
    return Hecho(
        **_comun(superficie.ambito), estado=UNKNOWN,
        motivos=(Motivo(
            PLANTA_NO_DISPONIBLE,
            "No se puede agregar por planta: la planta no esta declarada.",
        ),),
        procedencia=("planta -> UNKNOWN",),
        explicacion=(
            "Limite de superficie de sector no evaluable: la planta de esta "
            "unidad no esta determinada."
        ),
        diagnostico={
            "codigo_regla": CODIGO_C01,
            "limite_m2": LIMITE_M2,
            "planta_numero": None,
        },
    )


def _veredicto_planta(
    numero: int,
    superficies_planta: Sequence[Hecho],
    plantas_planta: Sequence[Hecho],
) -> Hecho:
    """El veredicto compartido por todas las unidades de una misma planta."""
    ambito = "planta %d" % numero
    conocidas = [s for s in superficies_planta if s.estado == KNOWN]
    desconocidas = [s for s in superficies_planta if s.estado == UNKNOWN]
    suma_parcial = sum(s.valor for s in conocidas)

    diagnostico = {
        "codigo_regla": CODIGO_C01,
        "limite_m2": LIMITE_M2,
        "planta_numero": numero,
        "suma_parcial_m2": suma_parcial,
        "unidades_computadas": [s.ambito for s in conocidas],
        "unidades_sin_superficie": [s.ambito for s in desconocidas],
        "proxy": "superficie_util_db_si (cara interior de muro; NO es superficie construida)",
    }
    procedencia = tuple(
        "%s: %.4f m2 (KNOWN)" % (s.ambito, s.valor) if s.estado == KNOWN
        else "%s: UNKNOWN" % s.ambito
        for s in superficies_planta
    )

    if suma_parcial >= LIMITE_M2:
        # FAIL con evidencia suficiente. Monotono: sobra con las unidades ya
        # medidas, aunque falten otras por medir (D3, DB-SI_DECISIONS.md).
        diagnostico["veredicto"] = "FAIL"
        confianza = _peor_confianza(
            *(s.confianza for s in conocidas),
            *(p.confianza for p in plantas_planta),
        )
        return Hecho(
            **_comun(ambito), estado=KNOWN, valor=suma_parcial, confianza=confianza,
            procedencia=procedencia,
            explicacion=(
                "Planta %d: %.2f m2 de superficie util (proxy, cara interior de "
                "muro) frente al limite de %.0f m2 de DB-SI 1 ap. 1. El proxy "
                "subestima la construida real, asi que superar el limite aqui "
                "demuestra que la construida tambien lo supera."
                % (numero, suma_parcial, LIMITE_M2)
            ),
            diagnostico=diagnostico,
        )

    # UNKNOWN. Nunca PASS: ni con datos completos ni con datos parciales.
    if desconocidas:
        detalle = (
            "No se puede confirmar el limite de la planta %d: %d de %d unidades "
            "no tienen superficie util determinada (%s), y la suma de las que "
            "si la tienen (%.2f m2) no basta por si sola para demostrar que se "
            "supera el limite de %.0f m2."
            % (numero, len(desconocidas), len(superficies_planta),
               ", ".join(s.ambito for s in desconocidas), suma_parcial, LIMITE_M2)
        )
    else:
        detalle = (
            "La suma de superficie util de la planta %d (%.2f m2) no alcanza el "
            "limite de %.0f m2, pero superficie_util_db_si mide a cara interior "
            "de muro y subestima la superficie construida real: no es posible "
            "descartar que la construida si lo supere."
            % (numero, suma_parcial, LIMITE_M2)
        )
    diagnostico["veredicto"] = None
    return Hecho(
        **_comun(ambito), estado=UNKNOWN,
        motivos=(Motivo(SUPERFICIE_INSUFICIENTE, detalle),),
        procedencia=procedencia,
        explicacion="Limite de superficie de sector no determinable con certeza: %s" % detalle,
        diagnostico=diagnostico,
    )


def limite_superficie_sector(
    superficies: Sequence[Hecho],
    plantas: Sequence[Hecho],
) -> List[Hecho]:
    """El hecho `limite_superficie_sector` (`C01`) de cada unidad, en el mismo
    orden que las entradas — un hecho por unidad, sin filtrar, igual que
    `ocupacion_por_zona`: una unidad que no se puede evaluar sigue
    apareciendo, con su motivo.

    `superficies` debe venir de `superficie_util.superficie_util_db_si` (NO
    `superficie_util_ocupable_db_si`, que es la que usa CAP-3/`ocupacion()` y
    excluye zonas de ocupacion nula: para un limite de sector no hay motivo
    para excluirlas). `plantas` debe venir de `analyzer.planta.planta`.
    Emparejadas por posicion, misma unidad en el mismo indice — mismo
    contrato que `ocupacion_por_zona`.

    Las unidades cuya `planta` resuelve al mismo numero comparten el mismo
    veredicto (mismo `ambito`, "planta N"): el limite es una magnitud de
    planta, no de vivienda, aunque se publique un hecho por vivienda para
    que el llamador pueda emparejarlo 1:1 con sus unidades sin tener que
    des-agrupar nada.
    """
    if len(superficies) != len(plantas):
        raise ValueError(
            "superficies (%d) y plantas (%d) deben venir emparejadas por unidad"
            % (len(superficies), len(plantas))
        )

    indices_por_planta: Dict[int, List[int]] = {}
    for i, p in enumerate(plantas):
        if p.estado in (KNOWN, ESTIMATED):
            indices_por_planta.setdefault(p.valor, []).append(i)

    veredicto_por_planta: Dict[int, Hecho] = {
        numero: _veredicto_planta(
            numero,
            [superficies[i] for i in indices],
            [plantas[i] for i in indices],
        )
        for numero, indices in indices_por_planta.items()
    }

    return [
        veredicto_por_planta[p.valor] if p.estado in (KNOWN, ESTIMATED)
        else _sin_planta(s)
        for s, p in zip(superficies, plantas)
    ]
