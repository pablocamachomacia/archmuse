# -*- coding: utf-8 -*-
"""Verificador de cumplimiento de un proyecto contra un pliego de concurso.

PRD: `docs/prd/2026-08-15-verificador-cumplimiento-pliego.md` (aprobado
2026-08-15, con la clasificación crítico/no-crítico y la decisión sobre PEM
propuestas en su §9 aceptadas tal cual). Compara CUALQUIER proyecto
(analizado desde un DXF real o generado con IA) contra CUALQUIER pliego ya
extraído (`analyzer.pliego_extractor`) — no depende de que el proyecto se
haya generado a partir de ese pliego (eso es un PRD aparte, todavía sin
aprobar: `docs/prd/2026-08-15-conector-pliego-generador.md`).

**100% determinista, cero llamadas a Claude.** Todos los datos ya existen
estructurados a ambos lados — el pliego como `Hecho` (`analyzer.hechos`), el
proyecto como el JSON que ya sirve `/api/analizar`/`/api/generar` — esto es
aritmética y comparación, no interpretación.

Cada comprobación (`CheckCumplimiento`) sale en exactamente uno de tres
estados: `cumple=True` / `cumple=False` / `cumple=None` ("no verificable" —
falta el dato del pliego, o falta el dato del proyecto). Nunca se inventa un
tercer valor con apariencia de los otros dos.

**Dos huecos de datos, documentados aquí para que no se lean como bugs:**

- `pem_maximo_euros` sale SIEMPRE `no_verificable`. El extractor no trae
  ningún €/m² de construcción (solo un tope total y un ratio de superficies
  no monetario), y ArchMuse no calcula coste de construcción en ningún sitio
  — inventar una tasa violaría la misma regla de "nunca inventar" que rige
  todo `pliego_extractor.py`.
- `porcentaje_accesibilidad` usa como proxy el % de viviendas cuyo baño pasa
  `evaluator.evaluate_bathroom_accessibility` — no mide si la vivienda
  entera está "adaptada" en el sentido que suele pedir un pliego de VPP.
  Etiquetado como aproximación en el propio `motivo` del check, nunca
  presentado como una medida exacta.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

#: Clasificación por defecto, propuesta en el PRD §9 y aceptada al aprobar.
#: Los "críticos" son los que típicamente excluyen de un concurso
#: (incumplimiento legal/administrativo duro); el resto penaliza en la
#: baremación sin excluir. No es una regla universal de ningún pliego real
#: -- es la mejor clasificación de partida disponible hoy.
PARAMETROS_CRITICOS = frozenset({
    "num_viviendas_minimo",
    "edificabilidad_maxima_m2",
    "porcentaje_accesibilidad",
})

TOLERANCIA_MIX_PCT = 5.0


@dataclass
class CheckCumplimiento:
    parametro: str
    valor_exigido: Any
    valor_proyecto: Any
    cumple: Optional[bool]  # None = no verificable
    critico: bool
    motivo: str = ""


@dataclass
class VerificacionPliego:
    checks: List[CheckCumplimiento] = field(default_factory=list)
    #: 0-100, o `None` si ningún check era verificable -- nunca un número
    #: calculado sobre comprobaciones que no se pudieron hacer.
    score_cumplimiento: Optional[int] = None
    blockers: List[CheckCumplimiento] = field(default_factory=list)
    warnings: List[CheckCumplimiento] = field(default_factory=list)
    resumen_ejecutivo: str = ""


def _campo_pliego(pliego_json: dict, nombre: str) -> dict:
    """Un campo del pliego ya serializado (`hechos.hecho_a_dict`), o un
    envoltorio `no_encontrado` sintético si el pliego ni siquiera trae esa
    clave -- para que el resto del módulo nunca tenga que comprobar
    `nombre in pliego_json` aparte de leer `no_encontrado`."""
    campo = pliego_json.get(nombre)
    if not isinstance(campo, dict):
        return {"no_encontrado": True, "valor": None, "motivo": "El pliego no trae este campo."}
    return campo


def _valor_pliego(pliego_json: dict, nombre: str) -> Any:
    campo = _campo_pliego(pliego_json, nombre)
    return None if campo.get("no_encontrado") else campo.get("valor")


_RE_NUM_DORMITORIOS = re.compile(r"(\d+)")


def _numero_dormitorios_de_texto(texto: str) -> Optional[int]:
    """«2 dormitorios» / «vivienda de 3 hab.» -> 2 / 3. El primer entero del
    texto -- heurística deliberadamente simple, documentada como tal (PRD
    §6): el pliego no tiene un vocabulario cerrado para esto."""
    m = _RE_NUM_DORMITORIOS.search(texto or "")
    return int(m.group(1)) if m else None


def _contar_dormitorios(vivienda: dict) -> int:
    return sum(
        1 for h in (vivienda.get("habitaciones") or [])
        if str(h.get("nombre") or "").strip().lower().startswith("dormitorio")
    )


def _bucketizar_por_dormitorios(viviendas: List[dict]) -> Dict[int, List[dict]]:
    bucket: Dict[int, List[dict]] = {}
    for v in viviendas:
        bucket.setdefault(_contar_dormitorios(v), []).append(v)
    return bucket


def _check_num_viviendas(proyecto: dict, pliego: dict) -> CheckCumplimiento:
    minimo = _valor_pliego(pliego, "num_viviendas_minimo")
    num_real = len(proyecto.get("viviendas") or [])
    if minimo is None:
        return CheckCumplimiento(
            "num_viviendas_minimo", None, num_real, None, True,
            "El pliego no cita un número mínimo de viviendas.",
        )
    return CheckCumplimiento(
        "num_viviendas_minimo", minimo, num_real, num_real >= minimo, True,
        "" if num_real >= minimo else "Por debajo del mínimo exigido por el pliego.",
    )


def _check_edificabilidad(proyecto: dict, pliego: dict) -> CheckCumplimiento:
    maximo = _valor_pliego(pliego, "edificabilidad_maxima_m2")
    urbanismo = proyecto.get("urbanismo") or {}
    real = urbanismo.get("superficie_total_construida_m2")
    if maximo is None or real is None:
        motivo = (
            "El pliego no cita una edificabilidad máxima." if maximo is None
            else "El proyecto no tiene datos de solar (habitual en un DXF analizado sin edificabilidad declarada)."
        )
        return CheckCumplimiento("edificabilidad_maxima_m2", maximo, real, None, True, motivo)
    return CheckCumplimiento(
        "edificabilidad_maxima_m2", maximo, round(real, 1), real <= maximo, True,
        "" if real <= maximo else "Superficie total construida por encima del máximo del pliego.",
    )


def _check_ratio_construido_util(proyecto: dict, pliego: dict) -> CheckCumplimiento:
    maximo = _valor_pliego(pliego, "ratio_construido_util_max")
    viviendas = proyecto.get("viviendas") or []
    # `envolvente_cerrada_m2` (superficie construida cerrada, contrato AM_*)
    # solo existe cuando el DXF traía la capa AM_CONS_CER -- ausente en todo
    # proyecto generado con IA y en cualquier DXF sin esas capas. Un
    # proyecto sin ningún dato de envolvente no permite calcular este ratio.
    construida = [v.get("envolvente_cerrada_m2") for v in viviendas if v.get("envolvente_cerrada_m2") is not None]
    util_total = sum(v.get("superficie_total_m2") or 0 for v in viviendas)
    if maximo is None or not construida or not util_total:
        motivo = (
            "El pliego no cita un ratio máximo construido/útil." if maximo is None
            else "El proyecto no declara superficie construida cerrada (capa AM_CONS_CER ausente)."
        )
        return CheckCumplimiento("ratio_construido_util_max", maximo, None, None, False, motivo)
    ratio_real = sum(construida) / util_total
    return CheckCumplimiento(
        "ratio_construido_util_max", maximo, round(ratio_real, 2), ratio_real <= maximo, False,
        "" if ratio_real <= maximo else "Ratio construido/útil por encima del máximo del pliego.",
    )


def _check_accesibilidad(proyecto: dict, pliego: dict) -> CheckCumplimiento:
    minimo = _valor_pliego(pliego, "porcentaje_accesibilidad")
    viviendas = proyecto.get("viviendas") or []
    evaluables = [v for v in viviendas if (v.get("accesibilidad") or {}).get("evaluable")]
    motivo_proxy = "Aproximación: % de viviendas con baño accesible, no una medida directa de vivienda adaptada."
    if minimo is None or not evaluables:
        motivo = (
            "El pliego no cita un porcentaje mínimo de accesibilidad." if minimo is None
            else "Ninguna vivienda del proyecto tiene la comprobación de accesibilidad de baño evaluada."
        )
        return CheckCumplimiento("porcentaje_accesibilidad", minimo, None, None, True, motivo)
    cumplen = sum(1 for v in evaluables if v["accesibilidad"].get("cumple"))
    pct_real = round(cumplen / len(evaluables) * 100, 1)
    return CheckCumplimiento(
        "porcentaje_accesibilidad", minimo, pct_real, pct_real >= minimo, True,
        motivo_proxy,
    )


def _check_pem(pliego: dict) -> CheckCumplimiento:
    maximo = _valor_pliego(pliego, "pem_maximo_euros")
    return CheckCumplimiento(
        "pem_maximo_euros", maximo, None, None, False,
        "No verificable: ArchMuse no tiene ningún dato real de coste de construcción (€/m²) hoy; "
        "el pliego tampoco extrae una tasa monetaria, solo un tope total. Nunca se inventa una cifra.",
    )


def _checks_mix_tipologias(proyecto: dict, pliego: dict) -> List[CheckCumplimiento]:
    filas = _valor_pliego(pliego, "mix_tipologias")
    viviendas = proyecto.get("viviendas") or []
    total = len(viviendas)
    if not filas:
        return [CheckCumplimiento(
            "mix_tipologias", None, None, None, False,
            "El pliego no declara ningún mix de tipologías.",
        )]
    bucket = _bucketizar_por_dormitorios(viviendas)
    checks: List[CheckCumplimiento] = []
    for fila in filas:
        tipo = str(fila.get("tipo") or "")
        n_dorm = _numero_dormitorios_de_texto(tipo)
        etiqueta = "mix_tipologias:%s" % (tipo or "?")
        if n_dorm is None or not total:
            checks.append(CheckCumplimiento(
                etiqueta, fila.get("porcentaje"), None, None, False,
                "No se pudo interpretar el nº de dormitorios de «%s»." % tipo if n_dorm is None
                else "El proyecto no tiene ninguna vivienda.",
            ))
            continue
        emparejadas = bucket.get(n_dorm, [])
        pct_real = round(len(emparejadas) / total * 100, 1)
        pct_exigido = fila.get("porcentaje")
        cumple_pct = (
            abs(pct_real - pct_exigido) <= TOLERANCIA_MIX_PCT if pct_exigido is not None else None
        )
        checks.append(CheckCumplimiento(
            etiqueta, pct_exigido, pct_real, cumple_pct, False,
            "%d vivienda(s) de %d dormitorio(s) encontradas (bucketización por nº de "
            "«Dormitorio N», heurística determinista)." % (len(emparejadas), n_dorm),
        ))
        sup_min, sup_max = fila.get("sup_util_min"), fila.get("sup_util_max")
        if emparejadas and (sup_min is not None or sup_max is not None):
            superficies = [v.get("superficie_total_m2") or 0 for v in emparejadas]
            en_rango = [
                (sup_min is None or s >= sup_min) and (sup_max is None or s <= sup_max)
                for s in superficies
            ]
            checks.append(CheckCumplimiento(
                "superficie_util:%s" % (tipo or "?"), [sup_min, sup_max], superficies,
                all(en_rango), False,
                "" if all(en_rango) else "Alguna vivienda de este tipo queda fuera del rango del pliego.",
            ))
    return checks


def verificar_cumplimiento(proyecto: dict, pliego_json: dict) -> VerificacionPliego:
    """`proyecto` es el payload ya serializado (`obtener_proyecto()`);
    `pliego_json` es `obtener_pliego(...)["parametros"]`. Ninguno de los dos
    se muta."""
    checks: List[CheckCumplimiento] = [
        _check_num_viviendas(proyecto, pliego_json),
        _check_edificabilidad(proyecto, pliego_json),
        _check_ratio_construido_util(proyecto, pliego_json),
        _check_accesibilidad(proyecto, pliego_json),
        _check_pem(pliego_json),
    ]
    checks.extend(_checks_mix_tipologias(proyecto, pliego_json))

    verificables = [c for c in checks if c.cumple is not None]
    blockers = [c for c in checks if c.cumple is False and c.critico]
    warnings = [c for c in checks if c.cumple is False and not c.critico]

    score = (
        round(100 * sum(1 for c in verificables if c.cumple) / len(verificables))
        if verificables else None
    )
    # Un blocker real nunca convive con una puntuación alta: capado, no
    # recalculado -- la proporción de aciertos sigue siendo la que es, pero
    # un incumplimiento que excluiría del concurso no puede maquillarse con
    # el resto de checks menores que sí cumplen.
    if blockers and score is not None:
        score = min(score, 40)

    n_no_verificables = len(checks) - len(verificables)
    partes = []
    if verificables:
        partes.append("%d de %d comprobaciones verificables cumplen." % (
            sum(1 for c in verificables if c.cumple), len(verificables)
        ))
    else:
        partes.append("Ninguna comprobación se pudo verificar con los datos disponibles.")
    if blockers:
        partes.append("%d incumplimiento(s) crítico(s), que normalmente excluirían del concurso: %s." % (
            len(blockers), ", ".join(c.parametro for c in blockers)
        ))
    if warnings:
        partes.append("%d advertencia(s) no crítica(s) (penalizan, no excluyen)." % len(warnings))
    if n_no_verificables:
        partes.append("%d comprobación(es) no verificable(s) por falta de datos." % n_no_verificables)
    resumen = " ".join(partes)

    return VerificacionPliego(
        checks=checks, score_cumplimiento=score, blockers=blockers, warnings=warnings,
        resumen_ejecutivo=resumen,
    )
