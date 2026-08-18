# -*- coding: utf-8 -*-
"""CAP-3 — `ocupacion`, la primera magnitud del DB-SI que ArchMuse calcula con su tabla real.

**Es un hecho, no una regla.** No tiene `passed`. La ocupación no se cumple ni
se incumple: es el insumo de `C09`, `C10`, `C15` y `C16`, todas ellas
bloqueadas además por capacidades que no existen (CAP-5/6/7). Lo que este
módulo aporta hoy no es una comprobación nueva, es convertir cuatro silencios
en cuatro `UNKNOWN` explicados.

---

### La fórmula, y la trampa dimensional

DB-SI, Sección SI 3, apartado 2, **Tabla 2.1 «Densidades de ocupación»**,
literal del corpus ingerido
(`extraccion/estado/candidatas/codigotecnico__DB-SI__0a2e78cd6247.jsonl`,
registro 7):

    «Para calcular la ocupación deben tomarse los valores de densidad de
    ocupación que se indican en la tabla 2.1 en función de la superficie útil
    de cada zona […]»

    Residencial Vivienda · Plantas de vivienda · 20

```
ocupacion(zona) [personas] = superficie_util(zona) [m2] / densidad [m2/persona]
```

La densidad se expresa en **m²/persona: es un divisor, no un multiplicador**.
Se dice aquí porque es la inversión mental fácil y produce un error de ×400 en
el caso residencial, y porque el motor ya tiene el precedente exacto de un
error dimensional silencioso: `window_area_m2 = long_side × 0.25`
(`evaluator.py`), metros presentados como m², responsable del 41 % de las
incidencias del proyecto de ejemplo (`NORMATIVE_AUDIT.md` §6.3).

### No se redondea. Nunca

`DB-SI_DECISIONS.md` **D2**, tras búsqueda exhaustiva sobre las 92 páginas del
DB-SI: `redonde…` aparece una vez (aristas de madera, Anejo E), `por exceso`
cero, `número entero` cero. Y *«o fracción»* aparece **trece veces, todas en
magnitudes derivadas de la ocupación** (plazas de silla de ruedas por cada 100
ocupantes, hidrantes por cada 10.000 m²…), **ninguna en la ocupación misma**.

La conclusión no es «la norma no lo dice»: es que la norma **demuestra saber
decirlo cuando quiere, y no lo dice aquí**. Por tanto `valor` es fraccionario y
viaja sin redondear; el *«o fracción»* lo aplicará cada regla que lo cite, con
su apartado. El `ceil` que `DB-SI_FACT_MODEL.md` §5.2 proponía como *inferencia
técnica* quedó **retirado** por D2 — si alguna vez reaparece en este módulo,
es una regresión, no una mejora.

`diagnostico["presentacion_personas"]` sí lleva el entero superior, y se llama
así a propósito: es formato para enseñar a una persona, no viaja a ninguna
regla (D2.3).

### La superficie que entra no es la que publica CAP-1

CAP-1 (`superficie_util.py`) incluye las zonas de ocupación nula en la
superficie útil, y hace bien: el Anejo SI A las excluye del *«número de
ocupantes»*, no de la superficie. Aquí se descuentan, porque aquí se cuentan
ocupantes. Por eso este módulo consume
`superficie_util_ocupable_db_si`, no `superficie_util_db_si`.

### Selección de fila: sólo automática cuando no hay elección

La Tabla 2.1 indexa por **dos** ejes: uso previsto × zona/tipo de actividad.
CAP-2 aporta el primero; el segundo **no existe en ArchMuse**. Regla adoptada:
la fila se selecciona sola únicamente cuando el uso tiene **una sola fila** en
la tabla. Residencial Vivienda la tiene (*«Plantas de vivienda»*), y por eso el
caso que ArchMuse analiza hoy funciona sin declarar nada más. Administrativo
tiene dos, Comercial siete, Pública concurrencia dieciocho: ahí la fila la
elige el técnico, no el motor, y sin esa elección el hecho es `UNKNOWN`.

No se transcriben las filas que nadie puede seleccionar todavía. Transcribir
una tabla de 40 filas heterogéneas (hay valores en m²/persona, uno en
`1 pers/asiento` y una categoría no numérica) para no usar ninguna sería
introducir riesgo de transcripción sin ganancia — y el criterio de *«los
valores más asimilables»* del propio apartado 2 es **criterio profesional
puro**, que nunca debe automatizarse (`DB-SI_FACT_MODEL.md` §5.3.3).

### Ámbito: vivienda por defecto, planta cuando CAP-4 la conoce

La tabla dice *«Plantas de vivienda»*. El ámbito normativo es la **planta**.
Antes de CAP-4, ArchMuse no tenía forma de saberla y agregaba siempre por
vivienda, marcado como agregado no normativo. Con CAP-4
(`docs/prd/2026-08-09-cap4-modelo-de-planta.md`), `ocupacion()` acepta el
hecho `planta` (`analyzer/planta.py`) como insumo opcional:

- **Sin `planta`, o con `planta.estado == UNKNOWN`**: el comportamiento es
  exactamente el de antes de CAP-4 — ámbito vivienda, marcado explícitamente
  como agregado no normativo (`DB-SI_FACT_MODEL.md` §9). Se prefiere un
  ámbito declarado provisional a uno silenciosamente equivocado.
- **Con `planta.estado in (KNOWN, ESTIMATED)`**: el ámbito emitido pasa a ser
  la planta real, `agregado_no_normativo` pasa a `False`, y la confianza de
  `planta` entra en el eslabón más débil junto a la de superficie/uso/densidad.

`diagnostico["ambito_normativo"]`/`["ambito_emitido"]` lo dicen en el propio
dato en los dos casos, no sólo en este comentario.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .hechos import (
    ALTA,
    BAJA,
    ESTIMATED,
    KNOWN,
    MEDIA,
    NO_APLICABLE,
    UNKNOWN,
    Hecho,
    Motivo,
)
from .uso_previsto import (
    ADMINISTRATIVO,
    ALMACEN,
    APARCAMIENTO,
    COMERCIAL,
    DOCENTE,
    HOSPITALARIO,
    PUBLICA_CONCURRENCIA,
    RESIDENCIAL_PUBLICO,
    RESIDENCIAL_VIVIENDA,
)

# --- Localizadores normativos ----------------------------------------------
# La Tabla 2.1 es una exigencia, no un término del glosario, así que su
# referencia es un localizador jerárquico (`DB-SI_FACT_MODEL.md` §7.1) y no un
# `concept_id`. Los `concept_id` de los términos que sí están definidos viajan
# en `diagnostico`, igual que hace `uso_previsto.py`.
LOCALIZADOR_TABLA_2_1 = "DB-SI / SI 3 / ap. 2 / Tabla 2.1"
LOCALIZADOR_CALCULO = "DB-SI / SI 3 / ap. 2"
CONCEPT_ID_OCUPACION_NULA = "es.cte.db_si.anejo_a.zona_de_ocupacion_nula"
CONCEPT_ID_SUPERFICIE_UTIL = "es.cte.db_si.anejo_a.superficie_util"

# --- Códigos de motivo (`DB-SI_FACT_MODEL.md` §8) --------------------------

USO_NO_DISPONIBLE = "USE_NOT_AVAILABLE"            # U5: sin uso no hay fila
USO_FUERA_DE_TABLA = "USE_NOT_IN_TABLE_2_1"        # U6: «más asimilables» es criterio del técnico
ZONA_NO_DECLARADA = "TABLE_ROW_NOT_DETERMINED"     # el uso tiene varias filas
SUPERFICIE_NO_DISPONIBLE = "AREA_NOT_AVAILABLE"    # U8: propagación de U1
DENSIDAD_NO_DISPONIBLE = "DENSITY_NOT_AVAILABLE"   # propagación de las tres anteriores


@dataclass(frozen=True)
class FilaTabla21:
    """Una fila transcrita de la Tabla 2.1.

    `densidad_m2_por_persona` es `None` cuando la fila no da un número sino la
    categoría *«Ocupación nula»* — que **no es cero** (`DB-SI_FACT_MODEL.md`
    §4.3): cero sería «no hay nadie y lo sé», y la categoría es «la norma exime
    de contar aquí». Modelarla como 0.0 borraría la distinción que `C15`
    necesita para decidir.
    """

    uso: str
    zona_literal: str
    densidad_m2_por_persona: Optional[float]
    ocupacion_nula: bool = False


# Filas transcritas literalmente. Sólo las seleccionables hoy: ver docstring.
FILA_PLANTAS_DE_VIVIENDA = FilaTabla21(
    uso=RESIDENCIAL_VIVIENDA,
    zona_literal="Plantas de vivienda",
    densidad_m2_por_persona=20.0,
)

FILA_OCUPACION_NULA = FilaTabla21(
    uso="CUALQUIERA",
    zona_literal=(
        "Zonas de ocupacion ocasional y accesibles unicamente a efectos de "
        "mantenimiento: salas de maquinas, locales para material de limpieza, etc."
    ),
    densidad_m2_por_persona=None,
    ocupacion_nula=True,
)

# Uso -> filas transcritas. Un uso ausente de este mapa no está ausente de la
# Tabla 2.1: significa que tiene más de una fila y que ArchMuse no sabe cuál
# toca, que es una situación distinta y produce otro motivo.
_FILAS_POR_USO: Dict[str, Tuple[FilaTabla21, ...]] = {
    RESIDENCIAL_VIVIENDA: (FILA_PLANTAS_DE_VIVIENDA,),
}

# Usos que la Tabla 2.1 sí contempla, con más de una fila. Se listan para poder
# decir «la tabla te cubre, falta declarar la zona» en vez del genérico «no
# figuras en la tabla», que sería falso.
USOS_EN_TABLA_CON_VARIAS_FILAS: Tuple[str, ...] = (
    RESIDENCIAL_PUBLICO,
    APARCAMIENTO,
    ADMINISTRATIVO,
    DOCENTE,
    HOSPITALARIO,
    COMERCIAL,
    PUBLICA_CONCURRENCIA,
    ALMACEN,
)


def _ambito_emitido(superficie_ambito: str, planta: Optional[Hecho]) -> str:
    """El `Hecho.ambito` que publica `ocupacion()`.

    Sin planta resuelta (`None` o `UNKNOWN`), es el de siempre
    (`superficie.ambito`, p. ej. "vivienda VT3/3") — byte a byte igual que
    antes de CAP-4. Con planta resuelta, antepone la planta real sin perder
    la identidad de la vivienda: sigue habiendo un hecho por vivienda, no uno
    por planta (eso es agregación de `C01`, no de este módulo)."""
    if planta is not None and planta.estado in (KNOWN, ESTIMATED):
        return "planta %d, %s" % (planta.valor, superficie_ambito)
    return superficie_ambito


def _info_ambito(planta: Optional[Hecho]) -> dict:
    """El bloque de `diagnostico` que declara el ámbito, condicionado a
    `planta` (CAP-4). Ver docstring del módulo.

    El motivo de desvío es, a propósito, el texto EXACTO de antes de CAP-4
    (`"ArchMuse no modela plantas hasta CAP-4"`) cuando `planta` no se pasa en
    absoluto — es el caso que tiene que seguir siendo indistinguible de
    `bd1a62f`. Sólo cuando se pasa un hecho `planta` explícito y resulta
    `UNKNOWN` se usa su propio motivo, más específico: ahí sí hay información
    nueva que antes no existía como insumo.
    """
    if planta is not None and planta.estado in (KNOWN, ESTIMATED):
        return {
            "ambito_normativo": "planta (Tabla 2.1: «Plantas de vivienda»)",
            "ambito_emitido": "planta %d" % planta.valor,
            "agregado_no_normativo": False,
            "planta_numero": planta.valor,
            "planta_estado": planta.estado,
            "planta_confianza": planta.confianza,
        }
    if planta is not None and planta.estado == UNKNOWN and planta.motivo_principal:
        motivo_del_desvio = planta.motivo_principal.detalle
    else:
        motivo_del_desvio = "ArchMuse no modela plantas hasta CAP-4"
    return {
        "ambito_normativo": "planta (Tabla 2.1: «Plantas de vivienda»)",
        "ambito_emitido": "vivienda",
        "agregado_no_normativo": True,
        "motivo_del_desvio": motivo_del_desvio,
    }


def _peor_confianza(*valores: Optional[str]) -> Optional[str]:
    """Eslabón más débil (`EVIDENCE_MODEL.md`), nunca una media.

    Promediar confianzas es exactamente cómo un dato flojo se vuelve
    presentable: la ocupación es tan buena como la superficie de la que sale, y
    tiene que decirlo.
    """
    orden = {ALTA: 3, MEDIA: 2, BAJA: 1}
    presentes = [v for v in valores if v in orden]
    if not presentes:
        return None
    return min(presentes, key=lambda v: orden[v])


def densidad_ocupacion(
    ambito: str,
    *,
    uso: Optional[str],
    ocupacion_nula: bool = False,
) -> Hecho:
    """El hecho `densidad_ocupacion` de una zona, leído de la Tabla 2.1.

    `ocupacion_nula=True` lo fuerza a `NO_APLICABLE` sin mirar el uso: la fila
    *«Cualquiera»* de la tabla es transversal, y el Anejo SI A dice que esos
    puntos *«no es preciso tomarlos en consideración a efectos de determinar
    […] el número de ocupantes»*.
    """
    comun = dict(
        nombre="densidad_ocupacion",
        ambito=ambito,
        tipo="normativo",
        unidad="m2/persona",
        fuente="DB-SI 3 ap. 2, Tabla 2.1 (corpus ingerido)",
        referencia_normativa=LOCALIZADOR_TABLA_2_1,
        criterio_declarado=(
            "DB-SI 3 ap. 2: «deben tomarse los valores de densidad de ocupacion "
            "que se indican en la tabla 2.1 en funcion de la superficie util de "
            "cada zona»"
        ),
    )

    if ocupacion_nula:
        return Hecho(
            **comun,
            estado=NO_APLICABLE,
            explicacion=(
                "Zona de ocupacion nula: la Tabla 2.1 no le asigna densidad, la "
                "clasifica aparte. No es una densidad de 0."
            ),
            diagnostico={
                "fila": FILA_OCUPACION_NULA.zona_literal,
                "concept_id_zona_ocupacion_nula": CONCEPT_ID_OCUPACION_NULA,
                "ocupacion_nula": True,
            },
        )

    if not uso or uso == "UNKNOWN":
        return Hecho(
            **comun, estado=UNKNOWN,
            motivos=(Motivo(
                USO_NO_DISPONIBLE,
                "No consta el uso previsto. La Tabla 2.1 se indexa por uso: sin "
                "el no hay fila aplicable, y no se asume ninguna.",
            ),),
            explicacion="Densidad de ocupacion no determinable sin uso previsto.",
        )

    filas = _FILAS_POR_USO.get(uso)
    if filas and len(filas) == 1:
        fila = filas[0]
        return Hecho(
            **comun, estado=KNOWN, valor=fila.densidad_m2_por_persona,
            # Alta: es un valor de tabla normativa verificado contra el texto
            # ingerido (`DB-SI_FACT_MODEL.md` §7.2). Que el uso que lo indexa
            # sea una hipotesis no degrada la densidad; degrada la ocupacion,
            # y alli se aplica el eslabon mas debil.
            confianza=ALTA,
            procedencia=(
                "Tabla 2.1, fila «%s» del uso %s" % (fila.zona_literal, uso),
            ),
            explicacion=(
                "Densidad de %g m2/persona (Tabla 2.1, «%s»). Es un divisor: "
                "mas superficie, mas ocupantes."
                % (fila.densidad_m2_por_persona, fila.zona_literal)
            ),
            diagnostico={
                "fila": fila.zona_literal,
                "uso": uso,
                "filas_del_uso": 1,
                "localizador": LOCALIZADOR_TABLA_2_1,
            },
        )

    if uso in USOS_EN_TABLA_CON_VARIAS_FILAS:
        return Hecho(
            **comun, estado=UNKNOWN,
            motivos=(Motivo(
                ZONA_NO_DECLARADA,
                "El uso «%s» figura en la Tabla 2.1, pero con varias filas segun "
                "la zona o el tipo de actividad, y no consta cual corresponde. "
                "Elegirla es criterio del tecnico, no del motor." % uso,
            ),),
            explicacion=(
                "La Tabla 2.1 cubre el uso «%s», pero hace falta declarar la "
                "zona o tipo de actividad para saber que fila aplica." % uso
            ),
            diagnostico={"uso": uso, "en_tabla": True, "filas_del_uso": "varias"},
        )

    return Hecho(
        **comun, estado=UNKNOWN,
        motivos=(Motivo(
            USO_FUERA_DE_TABLA,
            "El uso «%s» no figura en la Tabla 2.1. El apartado 2 remite a «los "
            "valores correspondientes a los que sean mas asimilables», que es "
            "criterio profesional y no se automatiza." % uso,
        ),),
        explicacion=(
            "Uso no contemplado por la Tabla 2.1; la asimilacion a otro uso "
            "requiere criterio del tecnico."
        ),
        diagnostico={"uso": uso, "en_tabla": False},
    )


def ocupacion(
    superficie: Hecho,
    uso: Hecho,
    *,
    densidad: Optional[Hecho] = None,
    declarada: Optional[float] = None,
    planta: Optional[Hecho] = None,
) -> Hecho:
    """El hecho `ocupacion` de una zona, en personas.

    `superficie` debe ser el hecho de superficie útil **ocupable**
    (`superficie_util.superficie_util_ocupable_db_si`): las zonas de ocupación
    nula ya vienen descontadas de él.

    `declarada` es la primera salvedad del apartado 2 —*«salvo cuando sea
    previsible una ocupación mayor»*—. Una ocupación declarada **mayor**
    prevalece sobre el cálculo. Una **menor** corresponde a la segunda
    salvedad (*«exigible […] en aplicación de alguna disposición legal»*), que
    es una excepción sujeta a justificación humana (`CONSTRAINT_MODEL.md` §5):
    se registra y se expone, **no se aplica sola**.

    `planta` (CAP-4, `analyzer/planta.py`) es opcional y **no cambia nunca el
    cálculo** — sólo el ámbito que se declara y, cuando está resuelta, la
    confianza. Ver docstring del módulo.
    """
    ambito_provisional = _info_ambito(planta)
    comun = dict(
        nombre="ocupacion",
        ambito=_ambito_emitido(superficie.ambito, planta),
        tipo="derivado",
        unidad="personas",
        fuente="calculada: superficie util ocupable / densidad de la Tabla 2.1",
        referencia_normativa=LOCALIZADOR_CALCULO,
        criterio_declarado=(
            "DB-SI 3 ap. 2: ocupacion = superficie util de la zona / densidad de "
            "ocupacion de la Tabla 2.1"
        ),
    )

    if densidad is None:
        densidad = densidad_ocupacion(superficie.ambito, uso=uso.valor)

    # 1. Ocupación nula: respuesta legítima, no una carencia. Va primero
    #    porque no depende de que la superficie se haya podido medir.
    if densidad.estado == NO_APLICABLE:
        return Hecho(
            **comun, estado=NO_APLICABLE,
            procedencia=("densidad_ocupacion -> NO_APLICABLE (zona de ocupacion nula)",),
            explicacion=(
                "Zona de ocupacion nula: el Anejo SI A exime de tomarla en "
                "consideracion a efectos del numero de ocupantes."
            ),
            diagnostico={**ambito_provisional,
                         "concept_id_zona_ocupacion_nula": CONCEPT_ID_OCUPACION_NULA},
        )

    # 2. Propagación. Un insumo UNKNOWN produce un derivado UNKNOWN, con la
    #    cadena causal entera y no colapsada (`DB-SI_DECISIONS.md` D3.b).
    motivos: List[Motivo] = []
    cadena: List[str] = []
    if uso.estado == UNKNOWN:
        motivos.append(Motivo(
            USO_NO_DISPONIBLE,
            "No se puede contar ocupantes sin uso previsto: %s"
            % (uso.motivo_principal.detalle if uso.motivo_principal else "no consta"),
        ))
        cadena.append("uso_previsto -> UNKNOWN")
    if superficie.estado == UNKNOWN:
        motivos.append(Motivo(
            SUPERFICIE_NO_DISPONIBLE,
            "No se puede contar ocupantes sin superficie util: %s"
            % (superficie.motivo_principal.detalle
               if superficie.motivo_principal else "no consta"),
        ))
        cadena.append("superficie_util_ocupable_db_si -> UNKNOWN")
    if densidad.estado == UNKNOWN and not motivos:
        # Sólo si la densidad falla por sí misma: si falla arrastrada por el
        # uso, repetir el motivo duplicaría la misma causa con dos etiquetas.
        motivos.append(Motivo(
            DENSIDAD_NO_DISPONIBLE,
            densidad.motivo_principal.detalle if densidad.motivo_principal
            else "No se ha podido determinar la densidad de la Tabla 2.1.",
        ))
    if densidad.estado == UNKNOWN:
        cadena.append("densidad_ocupacion -> UNKNOWN")

    if motivos:
        return Hecho(
            **comun, estado=UNKNOWN, motivos=tuple(motivos),
            procedencia=tuple(cadena),
            explicacion="Ocupacion no determinable: %s" % motivos[0].detalle,
            diagnostico={**ambito_provisional, "cadena_causal": cadena},
        )

    # 3. Cálculo. División, jamás producto (ver docstring del módulo).
    superficie_m2 = float(superficie.valor)
    densidad_m2 = float(densidad.valor)
    if densidad_m2 <= 0:
        # Defensa de la trampa dimensional: una densidad no positiva sería un
        # error de transcripción de la tabla, no un caso de negocio.
        return Hecho(
            **comun, estado=UNKNOWN,
            motivos=(Motivo(
                DENSIDAD_NO_DISPONIBLE,
                "Densidad no positiva (%r): la Tabla 2.1 se expresa en "
                "m2/persona y es un divisor." % densidad.valor,
            ),),
            explicacion="Densidad invalida; no se calcula ocupacion.",
            diagnostico={**ambito_provisional},
        )

    calculada = superficie_m2 / densidad_m2

    # 4. Confianza: el eslabón más débil de los insumos. Con la superficie
    #    en Media (CAP-1 clasifica por rótulo), la ocupación no puede ser Alta.
    #    `planta.confianza` entra en la misma mezcla (CAP-4): si `planta` es
    #    `None` o `UNKNOWN`, vale `None` y `_peor_confianza` lo ignora — es lo
    #    que mantiene esta línea equivalente a bd1a62f en ambos casos.
    confianza = _peor_confianza(
        superficie.confianza, uso.confianza, densidad.confianza,
        planta.confianza if planta is not None else None,
    )

    # 5. Un uso ESTIMATED contagia el estado: la hipótesis viaja con el valor y
    #    un hecho ESTIMATED no puede sostener por sí solo una afirmación de
    #    cumplimiento (`DB-SI_FACT_MODEL.md` §6).
    estado = ESTIMATED if ESTIMATED in (superficie.estado, uso.estado) else KNOWN

    procedencia = [
        "superficie util ocupable = %.4f m2 (%s)" % (superficie_m2, superficie.estado),
        "densidad = %g m2/persona (%s)" % (densidad_m2, LOCALIZADOR_TABLA_2_1),
        "ocupacion = %.4f / %g = %.4f personas" % (superficie_m2, densidad_m2, calculada),
    ]
    procedencia.extend(uso.procedencia)

    diagnostico = {
        **ambito_provisional,
        "superficie_util_ocupable_m2": superficie_m2,
        "densidad_m2_por_persona": densidad_m2,
        "ocupacion_exacta": calculada,
        # Formato para enseñar a una persona, no cálculo: D2.3. No viaja a
        # ninguna regla — el «o fraccion» lo aplica cada regla que lo cita.
        "presentacion_personas": int(math.ceil(calculada)),
        "redondeo_normativo": UNKNOWN,
        "concept_id_superficie_util": CONCEPT_ID_SUPERFICIE_UTIL,
        "uso": uso.valor,
    }

    valor = calculada
    if declarada is not None:
        diagnostico["ocupacion_declarada"] = float(declarada)
        if float(declarada) > calculada:
            # Salvedad 1 del apartado 2: prevalece.
            valor = float(declarada)
            estado = KNOWN
            confianza = _peor_confianza(confianza, ALTA)
            procedencia.append(
                "el arquitecto declara una ocupacion mayor (%g personas), que "
                "prevalece: DB-SI 3 ap. 2, «salvo cuando sea previsible una "
                "ocupacion mayor»" % float(declarada)
            )
            diagnostico["origen_del_valor"] = "declarado_mayor"
        else:
            # Salvedad 2: exigible una ocupación MENOR por disposición legal.
            # Se expone, no se aplica: `CONSTRAINT_MODEL.md` §5.
            procedencia.append(
                "el arquitecto declara una ocupacion menor (%g personas); no se "
                "aplica sola: DB-SI 3 ap. 2 la admite solo «cuando sea exigible "
                "[…] en aplicacion de alguna disposicion legal de obligado "
                "cumplimiento», que debe justificarse" % float(declarada)
            )
            diagnostico["origen_del_valor"] = "calculado"
            diagnostico["excepcion_pendiente_de_justificacion"] = True

    if planta is not None and planta.estado in (KNOWN, ESTIMATED):
        nota_ambito = "Vivienda de la planta %d." % planta.valor
    else:
        nota_ambito = "Agregado por vivienda; la tabla indexa por planta."
    return Hecho(
        **comun, estado=estado, valor=valor, confianza=confianza,
        procedencia=tuple(procedencia),
        explicacion=(
            "Ocupacion de %.2f personas: %.2f m2 utiles ocupables entre %g "
            "m2/persona (DB-SI 3 ap. 2, Tabla 2.1). %s"
            % (valor, superficie_m2, densidad_m2, nota_ambito)
        ),
        diagnostico=diagnostico,
    )


def ocupacion_por_zona(
    superficies: Sequence[Hecho],
    usos: Sequence[Hecho],
    *,
    declaradas: Optional[Sequence[Optional[float]]] = None,
) -> List[Hecho]:
    """Un hecho de ocupación por zona, en el mismo orden que las entradas.

    Sin filtrar los `UNKNOWN`: una vivienda que no se puede contar tiene que
    seguir apareciendo con su motivo. Desaparecer sería el silencio que
    `DB-SI_FACT_MODEL.md` §6 prohíbe, y el `UNKNOWN` explicado es justamente
    lo que este capítulo aporta.
    """
    if len(superficies) != len(usos):
        raise ValueError(
            "superficies (%d) y usos (%d) deben venir emparejados por zona"
            % (len(superficies), len(usos))
        )
    return [
        ocupacion(
            s, u,
            declarada=(declaradas[i] if declaradas is not None else None),
        )
        # zip-sin-strict: la funcion ya valida los largos arriba y levanta un
        # ValueError que dice cuantos hay de cada. `strict=True` daria el mismo
        # error con peor mensaje.
        for i, (s, u) in enumerate(zip(superficies, usos))
    ]
