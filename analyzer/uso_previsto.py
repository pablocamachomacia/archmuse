# -*- coding: utf-8 -*-
"""CAP-2 — `uso_previsto`, el eje por el que el DB-SI indexa cinco de sus tablas.

**Qué NO es.** No es `tipologia`. Son dos ejes distintos y hasta ahora estaban
fusionados de hecho, sin que nadie lo hubiera decidido:

| | `tipologia` | `uso_previsto` |
|---|---|---|
| Valores | plurifamiliar, unifamiliar, rehabilitacion | los 8 del Anejo SI A (+ otro / desconocido) |
| Qué describe | El tipo de encargo y su escala | La clave de entrada de las tablas del DB-SI |
| Quién lo usa | `UMBRALES_TIPOLOGIA` (umbrales propios) | Tablas 1.1, 2.1, 3.1, 5.1 de SI 3 y 1.1 de SI 4 |
| Tiene defecto | Sí (`DEFAULT_TIPOLOGIA`) | **No debe tenerlo** |

`rehabilitacion` es la prueba de que no son el mismo eje: es un tipo de
*intervención* y no dice absolutamente nada sobre el uso — se rehabilita un
edificio residencial, uno administrativo o uno hospitalario igual. Por eso
aquí no infiere ningún uso.

**La inferencia desde tipología existe, pero nunca se disfraza de declaración.**
El mapeo plurifamiliar/unifamiliar -> Residencial Vivienda es correcto y además
citable — Anejo SI A: *«Uso Residencial Vivienda: Edificio o zona destinada a
alojamiento permanente, cualquiera que sea el tipo de edificio: vivienda
unifamiliar, edificio de pisos o de apartamentos, etc.»*. Pero es una hipótesis
sobre la intención del proyecto, no un hecho declarado, así que el hecho sale
`ESTIMATED` y no `KNOWN`.

**Por qué `ESTIMATED` está justificado aquí y no lo estuvo en CAP-1.** En CAP-1
no había hipótesis posible: o se mide la geometría o no se mide. Aquí sí la hay,
y es explícita, acotada y citable. Es exactamente el caso que
`DB-SI_FACT_MODEL.md` §6 describe: *«valor obtenido por hipótesis explícita, la
hipótesis viaja con él»*. Y arrastra su consecuencia: un hecho `ESTIMATED` no
puede sostener por sí solo una afirmación de cumplimiento normativo; puede
sostener un aviso.

**Modelo de zonas.** El uso vive en la **zona**, no en la planta. No es
generalidad gratuita: con un uso por planta hay tres exigencias del texto
ingerido que no se pueden ni enunciar — Tabla 1.1 (*«toda zona cuyo uso previsto
sea diferente y subsidiario del principal…»*), Tabla 2.1 (*«en función de la
superficie útil de cada zona»*) y SI 3 §1 entera. Hoy cada vivienda constituye
una zona; el día que haya un local en planta baja, entra como otra zona sin
romper nada.

**Cobertura del catálogo.** El Anejo SI A define 8 usos. *Pública Concurrencia*
**no está entre ellos** pese a indexar varias tablas del propio DB-SI, así que
figura en el catálogo sin `concept_id`: es un valor que el documento usa y no
define, y eso se dice en vez de inventarle una cita.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Sequence, Tuple

from .hechos import ALTA, ESTIMATED, KNOWN, MEDIA, UNKNOWN, Hecho, Motivo

# --- Catálogo de usos ------------------------------------------------------
# Identificador interno estable + denominación normativa literal. Los dos, y
# separados: el identificador es nuestro y no debe cambiar nunca; la
# denominación es de la norma y se cita tal cual.

RESIDENCIAL_VIVIENDA = "RESIDENCIAL_VIVIENDA"
ADMINISTRATIVO = "ADMINISTRATIVO"
DOCENTE = "DOCENTE"
COMERCIAL = "COMERCIAL"
APARCAMIENTO = "APARCAMIENTO"
PUBLICA_CONCURRENCIA = "PUBLICA_CONCURRENCIA"
HOSPITALARIO = "HOSPITALARIO"
RESIDENCIAL_PUBLICO = "RESIDENCIAL_PUBLICO"
ALMACEN = "ALMACEN"
OTRO = "OTRO"
DESCONOCIDO = "UNKNOWN"


@dataclass(frozen=True)
class UsoPrevisto:
    """Un valor del catálogo. `concept_id` es `None` cuando el DB-SI usa el uso
    pero no lo define — no se le inventa una cita."""

    id: str
    denominacion_normativa: str
    concept_id: Optional[str]


_CATALOGO: Tuple[UsoPrevisto, ...] = (
    UsoPrevisto(RESIDENCIAL_VIVIENDA, "Uso Residencial Vivienda",
                "es.cte.db_si.anejo_a.uso_residencial_vivienda"),
    UsoPrevisto(ADMINISTRATIVO, "Uso Administrativo",
                "es.cte.db_si.anejo_a.uso_administrativo"),
    UsoPrevisto(DOCENTE, "Uso Docente", "es.cte.db_si.anejo_a.uso_docente"),
    UsoPrevisto(COMERCIAL, "Uso Comercial", "es.cte.db_si.anejo_a.uso_comercial"),
    UsoPrevisto(APARCAMIENTO, "Uso Aparcamiento",
                "es.cte.db_si.anejo_a.uso_aparcamiento"),
    UsoPrevisto(HOSPITALARIO, "Uso Hospitalario",
                "es.cte.db_si.anejo_a.uso_hospitalario"),
    UsoPrevisto(RESIDENCIAL_PUBLICO, "Uso Residencial Público",
                "es.cte.db_si.anejo_a.uso_residencial_publico"),
    UsoPrevisto(ALMACEN, "Uso Almacén", "es.cte.db_si.anejo_a.uso_almacen"),
    # El DB-SI lo usa en las tablas 1.1, 2.1, 3.1, 5.1 y 1.1 de SI 4, pero el
    # Anejo SI A no lo define. Sin `concept_id`: se dice, no se inventa.
    UsoPrevisto(PUBLICA_CONCURRENCIA, "Pública Concurrencia", None),
    UsoPrevisto(OTRO, "Otro uso no contemplado", None),
)

CATALOGO: Dict[str, UsoPrevisto] = {u.id: u for u in _CATALOGO}
VALORES_ADMITIDOS: Tuple[str, ...] = tuple(u.id for u in _CATALOGO)

# `concept_id` de la definición general del término, que NO vive en el Anejo
# SI A sino en el Anejo III de la Parte I del CTE. Lo dice el propio Anejo
# SI A: los términos de uso común en el conjunto del Código se toman de allí.
DEFINICION_USO_PREVISTO = "es.cte.parte_1.anejo_3.uso_previsto"

# --- Motivos ---------------------------------------------------------------

USO_NO_DECLARADO = "USE_NOT_DECLARED"
USO_NO_RECONOCIDO = "USE_NOT_IN_CATALOG"

# --- Inferencia desde tipología --------------------------------------------
# Sólo estas dos. `rehabilitacion` no aparece a propósito: es un tipo de
# intervención y no informa del uso. Añadir una fila aquí es una decisión de
# conocimiento, no un detalle de implementación.
_INFERENCIA_DESDE_TIPOLOGIA: Dict[str, str] = {
    "plurifamiliar": RESIDENCIAL_VIVIENDA,
    "unifamiliar": RESIDENCIAL_VIVIENDA,
}


@dataclass(frozen=True)
class ZonaDeUso:
    """Una zona del proyecto con su uso. Hoy, una vivienda; mañana, un local.

    `nombre` identifica el ámbito (p. ej. «vivienda VT3/3», «local planta
    baja»). `uso_declarado` es lo que el arquitecto ha dicho, o `None`.
    """

    nombre: str
    uso_declarado: Optional[str] = None


def _normalizar_uso(valor: Optional[str]) -> Optional[str]:
    """Acepta el identificador interno en cualquier caja. Devuelve `None` si no
    viene nada; el que no esté en el catálogo se devuelve tal cual para que
    quien construya el hecho pueda decir *qué* llegó."""
    if valor is None:
        return None
    limpio = str(valor).strip().upper().replace(" ", "_").replace("-", "_")
    return limpio or None


def uso_previsto(
    ambito: str,
    *,
    declarado: Optional[str] = None,
    tipologia: Optional[str] = None,
) -> Hecho:
    """El hecho `uso_previsto` de una zona.

    Tres caminos, y los tres dejan rastro distinto:

    - **Declarado** y en catálogo -> `KNOWN`, confianza Alta.
    - **No declarado**, pero la tipología permite inferirlo -> `ESTIMATED`,
      confianza Media, con la hipótesis escrita en la procedencia.
    - **Ni una cosa ni otra** -> `UNKNOWN` con motivo.
    """
    comun = dict(
        nombre="uso_previsto",
        ambito=ambito,
        tipo="declarado",
        unidad="",
        fuente="declaracion del arquitecto",
        referencia_normativa=DEFINICION_USO_PREVISTO,
        criterio_declarado=(
            "CTE Parte I Anejo III: uso especifico para el que se proyecta y "
            "realiza un edificio y que se debe reflejar documentalmente"
        ),
    )

    normalizado = _normalizar_uso(declarado)

    if normalizado is not None and normalizado not in CATALOGO:
        return Hecho(
            **comun, estado=UNKNOWN,
            motivos=(Motivo(
                USO_NO_RECONOCIDO,
                "El uso declarado «%s» no esta en el catalogo del DB-SI. "
                "Valores admitidos: %s." % (declarado, ", ".join(VALORES_ADMITIDOS)),
            ),),
            explicacion="Uso previsto no reconocido; no se asume ninguno.",
        )

    if normalizado is not None:
        uso = CATALOGO[normalizado]
        return Hecho(
            **comun, estado=KNOWN, valor=uso.id, confianza=ALTA,
            procedencia=("declarado por el arquitecto: %s" % uso.id,),
            explicacion="Uso previsto %s, declarado en el proyecto."
                        % uso.denominacion_normativa,
            diagnostico={
                "uso": uso.id,
                "denominacion_normativa": uso.denominacion_normativa,
                "concept_id_uso": uso.concept_id,
                "origen": "declarado",
            },
        )

    # No declarado: ¿puede la tipología sugerirlo?
    inferido = _INFERENCIA_DESDE_TIPOLOGIA.get((tipologia or "").strip().lower())
    if inferido:
        uso = CATALOGO[inferido]
        return Hecho(
            **{**comun, "fuente": "inferido de la tipologia declarada"},
            estado=ESTIMATED, valor=uso.id, confianza=MEDIA,
            procedencia=(
                "HIPOTESIS: tipologia=%s -> %s" % (tipologia, uso.id),
                "Anejo SI A: «cualquiera que sea el tipo de edificio: vivienda "
                "unifamiliar, edificio de pisos o de apartamentos»",
            ),
            explicacion=(
                "Uso previsto %s, NO declarado: se ha supuesto a partir de la "
                "tipologia «%s». Es una hipotesis, no una declaracion del "
                "proyecto." % (uso.denominacion_normativa, tipologia)
            ),
            diagnostico={
                "uso": uso.id,
                "denominacion_normativa": uso.denominacion_normativa,
                "concept_id_uso": uso.concept_id,
                "origen": "inferido_de_tipologia",
                "tipologia": tipologia,
            },
        )

    return Hecho(
        **comun, estado=UNKNOWN,
        motivos=(Motivo(
            USO_NO_DECLARADO,
            "No consta el uso previsto%s. El DB-SI indexa por uso cinco de sus "
            "tablas; sin el no hay fila aplicable."
            % (" y la tipologia «%s» no permite deducirlo" % tipologia
               if tipologia else ""),
        ),),
        explicacion="Uso previsto no declarado; no se asume Residencial Vivienda.",
        diagnostico={"origen": "no_declarado", "tipologia": tipologia},
    )


def uso_de(hecho: Hecho) -> str:
    """El identificador de uso que lleva un hecho, o `UNKNOWN`.

    Es el punto de consumo para las reglas futuras: preguntan por el uso, no
    por la tipología. Un hecho `UNKNOWN` devuelve `UNKNOWN`, nunca un valor
    por defecto.
    """
    return hecho.valor if hecho.valor is not None else DESCONOCIDO


def usos_por_zona(
    zonas: Sequence[ZonaDeUso],
    *,
    tipologia: Optional[str] = None,
    uso_principal: Optional[str] = None,
) -> List[Hecho]:
    """Un hecho por zona, en el mismo orden.

    Una zona sin uso propio hereda el `uso_principal` del edificio si lo hay,
    y esa herencia queda escrita en la procedencia: un uso heredado no es lo
    mismo que uno declarado, aunque el valor coincida.
    """
    hechos: List[Hecho] = []
    for zona in zonas:
        declarado = zona.uso_declarado
        heredado = declarado is None and uso_principal is not None
        hecho = uso_previsto(
            zona.nombre,
            declarado=declarado if declarado is not None else uso_principal,
            tipologia=tipologia,
        )
        if heredado and hecho.estado == KNOWN:
            hecho = replace(
                hecho,
                procedencia=hecho.procedencia + (
                    "heredado del uso principal del edificio, no declarado "
                    "para esta zona",),
                explicacion=hecho.explicacion + " Heredado del edificio.",
            )
        hechos.append(hecho)
    return hechos
