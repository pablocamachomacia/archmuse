"""Checklist de cumplimiento CTE: agrega en un único panel las reglas
DB-SI/DB-SUA/Habitabilidad que `evaluator.py`/`circulation.py` ya calculan.

`docs/prd/2026-08-17-checklist-cumplimiento-cte.md` (aprobado 2026-08-17):
capa de AGREGACIÓN, no un motor nuevo -- cada `ChecklistItem` envuelve un
resultado que `evaluator.score_unit` ya ha calculado. Ninguna regla de aquí
recalcula geometría; si `evaluator.py` corrige un umbral mañana, este
checklist lo hereda automáticamente en vez de poder divergir.

**Por qué la distancia de evacuación nunca es verde ni roja.** Al escribir
este módulo se encontró que `docs/audits/DB-SI_REVIEW.md` (ficha C09,
"Bloque B") ya había retirado el veredicto de cumplimiento de
`EvacuationDistanceResult` -- el propio `evaluator.py` (línea ~2463) dice
explícitamente que ese resultado "NO genera incidencia" desde esa auditoría,
precisamente porque los 25/50 m del DB-SI se miden hasta la salida del
EDIFICIO (con datos de ocupación y nº de salidas reales) y ArchMuse solo
tiene el recorrido interior hasta la puerta de la vivienda -- un proxy, no
la medida normativa. La casilla de "el edificio tiene dos salidas" que
introduce este PRD no arregla esa carencia de fondo (sigue faltando la
ocupación y la geometría de portal/escalera); por eso este checklist trata
la evacuación como **siempre no evaluable**, mostrando el recorrido medido y
el umbral que aplicaría (informativo) en vez de un veredicto que el propio
proyecto ya se negó a dar en otro sitio. Implementar aquí lo que el PRD
pedía literalmente (verde/rojo tras confirmar "dos salidas") habría
resucitado el mismo fallo que `DB-SI_REVIEW.md` ya corrigió."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .evaluator import UnitScore
from .referencias_normativas import referencia

ESTADO_CUMPLE = "cumple"
ESTADO_NO_CUMPLE = "no_cumple"
ESTADO_NO_EVALUABLE = "no_evaluable"


@dataclass
class ChecklistItem:
    codigo: str
    titulo: str
    estado: str  # ESTADO_CUMPLE / ESTADO_NO_CUMPLE / ESTADO_NO_EVALUABLE
    detalle: str
    referencia: str
    # Datos crudos opcionales para que el frontend pueda recomponer `detalle`
    # sin volver a pedir el checklist al servidor -- hoy solo lo usa el ítem
    # de evacuación, para que el checkbox "dos salidas" cambie el umbral
    # mostrado (25/50 m) al vuelo sin una petición nueva.
    datos: Optional[dict] = None


def _item_evacuacion(us: UnitScore, dos_salidas_confirmado: bool) -> ChecklistItem:
    umbral = 50.0 if dos_salidas_confirmado else 25.0
    resultados = us.evacuation_distance_results
    if not resultados:
        return ChecklistItem(
            codigo="CTE-DB-SI-3", titulo="Distancia de evacuación",
            estado=ESTADO_NO_EVALUABLE,
            detalle="No evaluable: la vivienda no tiene pieza de circulación identificable "
                     "por la que medir un recorrido.",
            referencia=referencia("CTE-DB-SI-3"),
        )
    peor = max(resultados, key=lambda r: r.distance_m)
    salidas_txt = "dos salidas (confirmado por el usuario)" if dos_salidas_confirmado else "una única salida"
    return ChecklistItem(
        codigo="CTE-DB-SI-3", titulo="Distancia de evacuación",
        estado=ESTADO_NO_EVALUABLE,
        detalle=(
            f"No evaluable contra la norma real: recorrido interior más largo hasta la puerta de "
            f"la vivienda {peor.distance_m:.1f} m (pieza '{peor.room_label}'). El umbral del DB-SI "
            f"para {salidas_txt} sería {umbral:.0f} m, pero ese límite se mide hasta la salida del "
            "EDIFICIO (con la ocupación real y la geometría de portal/escalera), datos que ArchMuse "
            "no tiene -- ver docs/audits/DB-SI_REVIEW.md. La cifra mostrada es solo el recorrido "
            "interior, no un veredicto de cumplimiento."
        ),
        referencia=referencia("CTE-DB-SI-3"),
        datos={
            "distancia_m": round(peor.distance_m, 1), "pieza": peor.room_label,
            "umbral_1_salida_m": 25.0, "umbral_2_salidas_m": 50.0,
        },
    )


def _item_itinerario_accesible(us: UnitScore, tipologia: str) -> ChecklistItem:
    if tipologia != "plurifamiliar":
        return ChecklistItem(
            codigo="CTE-DB-SUA-2-ITIN", titulo="Itinerario accesible (≥1.20 m)",
            estado=ESTADO_NO_EVALUABLE,
            detalle="No aplica: el itinerario accesible de DB-SUA-2 solo es exigible en "
                     f"tipología plurifamiliar (esta vivienda es '{tipologia}').",
            referencia=referencia("CTE-DB-SUA-2-ITIN"),
        )
    resultado = us.itinerario_accesible_result
    if resultado is not None:
        return ChecklistItem(
            codigo="CTE-DB-SUA-2-ITIN", titulo="Itinerario accesible (≥1.20 m)",
            estado=ESTADO_NO_CUMPLE, detalle=resultado.message,
            referencia=referencia("CTE-DB-SUA-2-ITIN"),
        )
    motivo = next((l for l in us.limitaciones if "Itinerario accesible" in l), None)
    if motivo:
        return ChecklistItem(
            codigo="CTE-DB-SUA-2-ITIN", titulo="Itinerario accesible (≥1.20 m)",
            estado=ESTADO_NO_EVALUABLE, detalle=motivo,
            referencia=referencia("CTE-DB-SUA-2-ITIN"),
        )
    return ChecklistItem(
        codigo="CTE-DB-SUA-2-ITIN", titulo="Itinerario accesible (≥1.20 m)",
        estado=ESTADO_CUMPLE,
        detalle="Al menos una pieza de circulación alcanza 1.20 m de anchura libre.",
        referencia=referencia("CTE-DB-SUA-2-ITIN"),
    )


def _items_ancho_pasillo(us: UnitScore) -> List[ChecklistItem]:
    """Ancho de paso general (`evaluator.evaluate_corridor_width`, CTE
    DB-SUA -- NUNCA DB-SI 3 §4, que dimensiona pasillos comunes de
    evacuación, no el interior de una vivienda; ver docstring de esa
    función). Umbral real por tipología (0.80-0.90 m), no el 1.10 m del
    encargo original -- ese valor no tiene fuente verificada en este
    proyecto (ver §6/§14 del PRD)."""
    items = []
    for r in us.corridor_width_results:
        items.append(ChecklistItem(
            codigo="CTE-DB-SUA-1",
            titulo=f"Ancho de paso — {r.room_label or 'pasillo'}",
            estado=ESTADO_CUMPLE if r.passed else ESTADO_NO_CUMPLE,
            detalle=r.message if not r.passed else (
                f"{r.room_label}: {r.short_side_m:.2f} m ≥ mínimo {r.min_width_m} m."
            ),
            referencia=referencia("CTE-DB-SUA-1"),
        ))
    return items


def _items_superficies_minimas(us: UnitScore) -> List[ChecklistItem]:
    """Superficies mínimas por pieza (`evaluator.RULES`, ya cubre Salón/
    Cocina, Dormitorio 1-3, Baño, Aseo) -- es la regla que el encargo
    original llamaba "superficies mínimas de estancias principales", ya
    implementada por completo, no una regla nueva."""
    items = []
    for r in us.basic_results:
        codigo = "HABITABILIDAD-SUP" if "Dormitorio" in r.rule_name else "HABITABILIDAD"
        items.append(ChecklistItem(
            codigo=codigo, titulo=f"Superficie mínima — {r.rule_name} ({r.room_label})",
            estado=ESTADO_CUMPLE if r.passed else ESTADO_NO_CUMPLE,
            detalle=r.message, referencia=referencia(codigo),
        ))
    return items


def _item_hueco_paso() -> ChecklistItem:
    """Anchura de hueco de paso (puertas). Siempre no evaluable hoy: el
    modelo de ArchMuse no tiene geometría de puertas en ningún punto del
    pipeline (mismo hallazgo ya documentado en `circulation.py` y en
    `docs/prd/2026-08-17-exportacion-bim-ifc.md`). Se deja como ítem real
    (no se omite) para que quede visible qué falta comprobar, en vez de
    desaparecer silenciosamente del checklist."""
    return ChecklistItem(
        codigo="CTE-DB-SUA", titulo="Anchura de hueco de paso (puertas)",
        estado=ESTADO_NO_EVALUABLE,
        detalle="No evaluable: el modelo no contiene geometría de puertas en ningún proyecto "
                 "(generado por IA o analizado desde DXF).",
        referencia=referencia("CTE-DB-SUA"),
    )


def generar_checklist_cte(
    unit_score: UnitScore, tipologia: str, dos_salidas_confirmado: bool = False,
) -> List[ChecklistItem]:
    """Checklist completo de una vivienda. `dos_salidas_confirmado` es una
    afirmación del USUARIO (checkbox en la UI, nunca autodetectada) sobre
    el edificio completo -- ver `_item_evacuacion` para por qué ni siquiera
    con esa confirmación se emite un veredicto verde/rojo."""
    items = [
        _item_evacuacion(unit_score, dos_salidas_confirmado),
        _item_itinerario_accesible(unit_score, tipologia),
    ]
    items.extend(_items_ancho_pasillo(unit_score))
    items.extend(_items_superficies_minimas(unit_score))
    items.append(_item_hueco_paso())
    return items
