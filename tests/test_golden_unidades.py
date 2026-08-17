# -*- coding: utf-8 -*-
"""G2 — golden de la AGRUPACIÓN: `evaluator.group_rooms_by_unit_label`.

Ejecutar:  python tests/test_golden_unidades.py

Congela qué habitación pertenece a qué vivienda, en qué orden salen las
viviendas y cuánta superficie suma cada una.

**Es el golden que el adaptador de E1 tiene que reproducir clavado.** El
contrato C8.1 del PRD dice que `modelo/compat.py` produce `List[Unit]` con el
mismo orden y la misma composición que esta función; este fixture es la
definición operativa de «el mismo». Si el adaptador agrupa igual pero ordena
distinto, CAP-1…CAP-5 seguirán dando los mismos hechos y `circulation.py`
resolverá otros empates: es exactamente la clase de diferencia que no se ve
hasta que alguien la busca.

La llamada se hace por atributo de módulo (`evaluator.group_rooms_by_unit_label`)
y no con `from ... import`, para que `tests/canario.py` pueda sustituirla en
memoria (mutación K2).
"""
import golden

from analyzer import evaluator


def construir():
    p = golden.plano()
    unidades = evaluator.group_rooms_by_unit_label(p.rooms, p.unit_labels)
    # Índice del recinto en el orden de lectura del parser (G1): identifica
    # cada habitación sin depender de un rótulo que se repite entre viviendas.
    indice = {id(r): i for i, r in enumerate(p.rooms)}
    return {
        "n_unidades": len(unidades),
        "unidades": [
            {
                "orden": orden,
                "nombre": u.name,
                "n_recintos": len(u.rooms),
                "superficie_total_m2": float(u.total_area_m2),
                "recintos": [
                    {"i": indice.get(id(r)), "rotulo": r.label, "area_m2": float(r.polygon.area)}
                    for r in u.rooms
                ],
            }
            for orden, u in enumerate(unidades)
        ],
        # Un recinto que no acaba en ninguna vivienda es un dato del sistema,
        # no una casualidad: hoy debe ser 0 y el golden lo vigila.
        "recintos_huerfanos": len(p.rooms) - sum(len(u.rooms) for u in unidades),
    }


def ejecutar_golden() -> int:
    return golden.ejecutar("G2_unidades", construir,
                           "agrupacion de recintos en viviendas")


if __name__ == "__main__":
    raise SystemExit(ejecutar_golden())
