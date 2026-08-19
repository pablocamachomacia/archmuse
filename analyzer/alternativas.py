# -*- coding: utf-8 -*-
"""Las cuatro alternativas del MVP, derivadas de parámetros comprobables (`CP-5`).

Informe ejecutivo del 2026-08-19, pieza ③: «generar varias alternativas, no una
única respuesta — A máxima superficie, B máximo número de viviendas, C máxima
eficiencia, D mejor orientación».

**Lo que este módulo puede hacer y lo que no**, según el §8 corregido de
`ARCHMUSE_SPEC.md` (2026-08-19):

> Generación de alternativas: **permitida** cuando la geometría se deriva de
> parámetros comprobables — envolvente y volumen edificable a partir de
> retranqueos, ocupación, edificabilidad y alturas. Cada alternativa lleva la
> procedencia de los parámetros que la producen.
>
> Sigue fuera: **la distribución interior libre**. Repartir estancias dentro de
> una planta según criterio propio no se deriva de nada comprobable.

Aquí sólo hay **aritmética sobre los parámetros que introdujo el arquitecto**.
Ni una llamada a un modelo, ni una decisión de diseño, ni una constante sacada
de ninguna norma: la envolvente edificable sale de multiplicar y comparar lo que
el usuario declaró, y cada cifra vuelve con la fórmula que la produjo.

**Por qué eso no es poco.** Las cuatro alternativas se distinguen por *cómo
reparten la misma envolvente*, y ese reparto es la decisión que de verdad cambia
el proyecto: más viviendas pequeñas o menos y grandes, más plantas o más huella.
Un arquitecto compara eso en una tabla, no en un plano.

**Y por qué no añade una capacidad al registro.** El registro está en 14 y `C4`
lo fija entre 8 y 12: `D-12` está sin decidir. Esto es un módulo de `analyzer/`
que consume el endpoint existente, no una herramienta nueva.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

#: Superficie media que se asume por tipología para repartir la envolvente. Son
#: los mismos valores que ya usa `ai_generator.TAMANO_MEDIO_ASUMIDO_M2`, y se
#: importan de allí para que no haya dos verdades: si alguien los ajusta, se
#: ajustan en un sitio.
def _tamanos() -> Dict[str, float]:
    from analyzer.ai_generator import TAMANO_MEDIO_ASUMIDO_M2

    return dict(TAMANO_MEDIO_ASUMIDO_M2)


#: Los cuatro objetivos del informe. Catálogo cerrado: un objetivo que no esté
#: aquí no se aproxima con el más parecido.
MAXIMA_SUPERFICIE = "maxima_superficie"
MAXIMO_NUMERO_VIVIENDAS = "maximo_numero_viviendas"
MAXIMA_EFICIENCIA = "maxima_eficiencia"
MEJOR_ORIENTACION = "mejor_orientacion"

OBJETIVOS = (MAXIMA_SUPERFICIE, MAXIMO_NUMERO_VIVIENDAS, MAXIMA_EFICIENCIA, MEJOR_ORIENTACION)

TITULOS = {
    MAXIMA_SUPERFICIE: "Máxima superficie",
    MAXIMO_NUMERO_VIVIENDAS: "Máximo nº de viviendas",
    MAXIMA_EFICIENCIA: "Máxima eficiencia",
    MEJOR_ORIENTACION: "Mejor orientación",
}

#: Cómo reparte cada objetivo la envolvente entre tipologías. Son proporciones,
#: no superficies: la superficie sale de la envolvente comprobable.
#:
#: **De dónde salen estos números, dicho claro: de un criterio de reparto, no de
#: ninguna norma.** Son la traducción aritmética de cada objetivo —«máxima
#: superficie» reparte hacia viviendas grandes, «máximo número» hacia las
#: pequeñas— y por eso viajan en la procedencia de cada alternativa, para que el
#: arquitecto vea con qué supuesto se construyó y lo pueda discutir.
REPARTOS = {
    MAXIMA_SUPERFICIE: {"dorm_1": 0.10, "dorm_2": 0.35, "dorm_3": 0.55},
    MAXIMO_NUMERO_VIVIENDAS: {"dorm_1": 0.60, "dorm_2": 0.35, "dorm_3": 0.05},
    MAXIMA_EFICIENCIA: {"dorm_1": 0.25, "dorm_2": 0.55, "dorm_3": 0.20},
    MEJOR_ORIENTACION: {"dorm_1": 0.20, "dorm_2": 0.50, "dorm_3": 0.30},
}

ETIQUETAS = OrderedDict((
    ("A", MAXIMA_SUPERFICIE),
    ("B", MAXIMO_NUMERO_VIVIENDAS),
    ("C", MAXIMA_EFICIENCIA),
    ("D", MEJOR_ORIENTACION),
))


@dataclass(frozen=True)
class Envolvente:
    """El volumen edificable, derivado de los parámetros urbanísticos.

    Cada campo trae su fórmula en `procedencia`. No hay ni un valor por defecto
    que no venga del usuario: si falta un parámetro, el campo que dependía de él
    sale a `None` y se dice cuál faltaba — nunca se rellena con un supuesto.
    """

    superficie_solar_m2: Optional[float]
    superficie_ocupable_m2: Optional[float]
    superficie_edificable_m2: Optional[float]
    plantas_maximas: Optional[int]
    #: El techo real: lo menor entre lo que permite la edificabilidad y lo que
    #: cabe apilando la huella ocupable en las plantas permitidas.
    techo_construible_m2: Optional[float]
    procedencia: Tuple[str, ...] = ()
    faltan: Tuple[str, ...] = ()

    def a_dict(self) -> Dict[str, Any]:
        return {
            "superficie_solar_m2": self.superficie_solar_m2,
            "superficie_ocupable_m2": self.superficie_ocupable_m2,
            "superficie_edificable_m2": self.superficie_edificable_m2,
            "plantas_maximas": self.plantas_maximas,
            "techo_construible_m2": self.techo_construible_m2,
            "procedencia": list(self.procedencia),
            "faltan": list(self.faltan),
        }


def _redondear(valor: Optional[float], decimales: int = 2) -> Optional[float]:
    return None if valor is None else round(valor, decimales)


def envolvente_edificable(parametros: Dict[str, Any]) -> Envolvente:
    """El volumen edificable a partir de ocupación, edificabilidad y alturas.

    Es la única «geometría» que este módulo produce, y es aritmética pura sobre
    lo que declaró el arquitecto. Un parámetro ausente **no se sustituye por
    nada**: se anota en `faltan` y lo que dependía de él vuelve a `None`.
    """
    solar = (parametros or {}).get("solar") or {}
    normativa = (parametros or {}).get("normativa") or {}

    superficie = solar.get("superficie_m2") or None
    ocupacion_pct = normativa.get("ocupacion_maxima_pct")
    edificabilidad = normativa.get("edificabilidad_maxima")
    plantas_max = normativa.get("plantas_maximas")

    procedencia: List[str] = []
    faltan: List[str] = []

    if not superficie:
        faltan.append("superficie del solar")
        return Envolvente(None, None, None, None, None, (), tuple(faltan))
    procedencia.append("Superficie del solar: %s m², declarada por el arquitecto." % superficie)

    ocupable = None
    if ocupacion_pct:
        ocupable = superficie * float(ocupacion_pct) / 100.0
        procedencia.append(
            "Huella ocupable = %s m² × %s %% = %.2f m²." % (superficie, ocupacion_pct, ocupable))
    else:
        faltan.append("ocupación máxima")

    edificable = None
    if edificabilidad:
        edificable = superficie * float(edificabilidad)
        procedencia.append(
            "Techo por edificabilidad = %s m² × %s = %.2f m²."
            % (superficie, edificabilidad, edificable))
    else:
        faltan.append("edificabilidad máxima")

    plantas = int(plantas_max) if plantas_max else None
    if plantas is None:
        faltan.append("plantas máximas")

    # El techo real es el MENOR de los dos, y decirlo importa: un solar con
    # edificabilidad generosa y ocupación estrecha no puede construir lo que la
    # edificabilidad permite, y al revés. Quedarse con uno solo es el error de
    # cálculo urbanístico más común.
    techo = None
    apilable = ocupable * plantas if (ocupable is not None and plantas) else None
    candidatos = [c for c in (edificable, apilable) if c is not None]
    if candidatos:
        techo = min(candidatos)
        if apilable is not None and edificable is not None:
            procedencia.append(
                "Apilando la huella en %d plantas salen %.2f m². El techo construible es el "
                "MENOR de los dos: %.2f m²." % (plantas, apilable, techo))
        else:
            procedencia.append("Techo construible: %.2f m² (con un solo límite disponible)." % techo)

    return Envolvente(
        superficie_solar_m2=_redondear(superficie),
        superficie_ocupable_m2=_redondear(ocupable),
        superficie_edificable_m2=_redondear(edificable),
        plantas_maximas=plantas,
        techo_construible_m2=_redondear(techo),
        procedencia=tuple(procedencia),
        faltan=tuple(faltan),
    )


@dataclass(frozen=True)
class Alternativa:
    """Un reparto concreto de la envolvente, con la procedencia de cada cifra."""

    etiqueta: str
    objetivo: str
    titulo: str
    mix_viviendas: Dict[str, Any]
    viviendas: int
    superficie_repartida_m2: float
    procedencia: Tuple[str, ...] = field(default_factory=tuple)

    def a_dict(self) -> Dict[str, Any]:
        return {
            "etiqueta": self.etiqueta,
            "objetivo": self.objetivo,
            "titulo": self.titulo,
            "mix_viviendas": dict(self.mix_viviendas),
            "viviendas": self.viviendas,
            "superficie_repartida_m2": self.superficie_repartida_m2,
            "procedencia": list(self.procedencia),
        }


def _mix_para(objetivo: str, techo_m2: float, superficie_minima_m2: float,
              tamanos: Dict[str, float]) -> Tuple[Dict[str, Any], int, float, List[str]]:
    reparto = REPARTOS[objetivo]
    tamano_medio = sum(reparto[k] * tamanos[k] for k in reparto)
    total = max(1, int(round(techo_m2 / tamano_medio)))
    cuentas = {k: int(round(total * reparto[k])) for k in reparto}
    # El redondeo por tipología puede no sumar el total. Se ajusta en `dorm_2`
    # --la central-- y nunca en los extremos, que son los que definen el
    # carácter del objetivo: cuadrar por ahí desdibujaría la alternativa.
    cuentas["dorm_2"] = max(0, cuentas["dorm_2"] + (total - sum(cuentas.values())))
    repartida = sum(cuentas[k] * tamanos[k] for k in cuentas)
    procedencia = [
        "Reparto del objetivo «%s»: %s." % (
            TITULOS[objetivo],
            ", ".join("%s %.0f %%" % (k, v * 100) for k, v in reparto.items())),
        "Tamaño medio resultante %.1f m²; %.2f m² de techo dan %d viviendas."
        % (tamano_medio, techo_m2, total),
    ]

    # **El redondeo puede pasarse del techo, y pasarse no es una opción.** Una
    # alternativa que reparte 1.215 m² sobre una envolvente de 1.200 no se
    # deriva de los parámetros comprobables: los incumple. Se quitan viviendas
    # —empezando por la más grande, que es la que más techo libera por unidad—
    # hasta que quepa, y se dice cuántas se han quitado y por qué.
    quitadas = 0
    while repartida > techo_m2 and sum(cuentas.values()) > 1:
        for tipo in ("dorm_3", "dorm_2", "dorm_1"):
            if cuentas[tipo] > 0:
                cuentas[tipo] -= 1
                quitadas += 1
                break
        repartida = sum(cuentas[k] * tamanos[k] for k in cuentas)
    total = sum(cuentas.values())
    if quitadas:
        # La cifra FINAL tiene que estar aquí. Sin ella, la procedencia decía
        # «19 viviendas» y la alternativa entregaba 18: una cifra huérfana, que
        # es justo lo que el §13 de la especificación prohíbe. Lo cazó su propio
        # test la primera vez que se ejecutó.
        procedencia.append(
            "El redondeo por tipología se pasaba del techo construible, así que se han "
            "quitado %d vivienda(s) empezando por la mayor. Resultado: %d viviendas, "
            "%.2f m² repartidos sobre %.2f m² disponibles."
            % (quitadas, total, repartida, techo_m2))
    mix = dict(cuentas)
    mix["superficie_minima_m2"] = superficie_minima_m2
    return mix, total, round(repartida, 2), procedencia


def derivar_alternativas(parametros: Dict[str, Any],
                         objetivos: Optional[Tuple[str, ...]] = None
                         ) -> Tuple[Envolvente, "OrderedDict[str, Alternativa]"]:
    """Las cuatro alternativas del informe, o las que se pidan.

    Devuelve `(envolvente, alternativas)`. Si la envolvente no se puede calcular
    —porque falta un parámetro urbanístico— **no se devuelve ninguna
    alternativa**: repartir un techo que no se ha podido calcular sería inventar
    la cifra de la que cuelga todo lo demás.
    """
    envolvente = envolvente_edificable(parametros)
    alternativas: "OrderedDict[str, Alternativa]" = OrderedDict()
    if not envolvente.techo_construible_m2:
        return envolvente, alternativas

    minima = ((parametros or {}).get("mix_viviendas") or {}).get("superficie_minima_m2", 45.0)
    tamanos = _tamanos()
    pedidos = objetivos or OBJETIVOS

    for etiqueta, objetivo in ETIQUETAS.items():
        if objetivo not in pedidos:
            continue
        mix, total, repartida, procedencia = _mix_para(
            objetivo, envolvente.techo_construible_m2, minima, tamanos)
        alternativas[etiqueta] = Alternativa(
            etiqueta=etiqueta,
            objetivo=objetivo,
            titulo=TITULOS[objetivo],
            mix_viviendas=mix,
            viviendas=total,
            superficie_repartida_m2=repartida,
            # La procedencia de la alternativa incluye la de la envolvente: sin
            # ella, «12 viviendas» es una cifra huérfana, que es exactamente lo
            # que el §13 de la especificación prohíbe.
            procedencia=tuple(envolvente.procedencia) + tuple(procedencia),
        )
    return envolvente, alternativas
