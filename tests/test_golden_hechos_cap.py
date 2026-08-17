# -*- coding: utf-8 -*-
"""G5 — golden de CAP-1…CAP-5: los hechos publicados sobre `ejemplo.dxf`.

Ejecutar:  python tests/test_golden_hechos_cap.py

Congela el resultado de los ocho módulos cerrados —superficie útil DB-SI,
uso previsto, planta, ocupación, límite de sector (C01) y altura de
evacuación— reproduciendo el mismo encadenamiento que hace `/api/analizar`,
pero sin HTTP y sin IA.

**Es la prueba operativa del contrato C8 del PRD: «CAP-1…CAP-5 se preservan».**
E1 no toca esos módulos, pero sí cambia de dónde salen sus insumos (hoy
`Unit`, mañana una vista del modelo a través del adaptador). Si un hecho se
mueve un decimal, cambia de estado o pierde un motivo, aquí se ve.

Dos escenarios, porque CAP-4 tiene dos caminos y los dos importan:

- `sin_planta`: ninguna planta declarada -> `planta` UNKNOWN, y la ocupación
  se emite por vivienda marcada como agregado no normativo. Es lo que hace
  hoy `/api/analizar` con `ejemplo.dxf`, y la línea base de CAP-3 son
  4 ESTIMATED + 2 UNKNOWN.
- `planta_3`: planta declarada -> `planta` KNOWN y la ocupación pasa a ámbito
  de planta. Los NÚMEROS de personas no deben cambiar entre los dos
  escenarios; sólo el ámbito. Esa invariancia es lo que protege
  `tests/test_analizar_planta.py` y aquí queda congelada en cifras.
"""
import golden

from analyzer import evaluator
from analyzer.altura_evacuacion import resolver_altura_evacuacion
from analyzer.ocupacion import ocupacion as calcular_ocupacion
from analyzer.planta import ORIGEN_DECLARADO, planta as calcular_planta
from analyzer.sectorizacion import limite_superficie_sector
from analyzer.superficie_util import superficie_util_db_si, superficie_util_ocupable_db_si
from analyzer.uso_previsto import ZonaDeUso, usos_por_zona


def _hecho(h) -> dict:
    """Los campos del hecho que son contrato, y ninguno más.

    Fuera quedan `explicacion` y `procedencia`: son texto para el arquitecto,
    cambian con cualquier retoque de redacción y congelarlos convertiría el
    golden en un test de estilo. Lo que se congela es lo que el motor consume:
    valor, estado, confianza y el CÓDIGO del motivo (estable y agrupable, a
    diferencia de su `detalle`).
    """
    return {
        "nombre": h.nombre,
        "ambito": h.ambito,
        "tipo": h.tipo,
        "unidad": h.unidad,
        "estado": h.estado,
        "valor": h.valor,
        "confianza": h.confianza,
        "codigos_motivo": [m.codigo for m in h.motivos],
        "referencia_normativa": h.referencia_normativa,
    }


def _escenario(unidades, numero_planta):
    usos = usos_por_zona(
        [ZonaDeUso(nombre="vivienda %s" % u.name) for u in unidades],
        tipologia="plurifamiliar", uso_principal=None,
    )
    plantas = [
        calcular_planta(
            "vivienda %s" % u.name,
            numero=numero_planta,
            sobre_rasante=(numero_planta > 0) if numero_planta is not None else None,
            origen=ORIGEN_DECLARADO if numero_planta is not None else None,
        )
        for u in unidades
    ]
    sup_util = [superficie_util_db_si(u) for u in unidades]
    sup_ocupable = [superficie_util_ocupable_db_si(u) for u in unidades]
    ocupaciones = [
        calcular_ocupacion(s, uso, planta=pl)
        for s, uso, pl in zip(sup_ocupable, usos, plantas)
    ]
    sectores = limite_superficie_sector(sup_util, plantas)
    altura = resolver_altura_evacuacion("edificio", valor_declarado_m=None)

    return {
        "superficie_util_db_si": [_hecho(h) for h in sup_util],
        "superficie_util_ocupable_db_si": [_hecho(h) for h in sup_ocupable],
        "uso_previsto": [_hecho(h) for h in usos],
        "planta": [_hecho(h) for h in plantas],
        "ocupacion": [_hecho(h) for h in ocupaciones],
        "sectorizacion": [_hecho(h) for h in sectores],
        "altura_evacuacion": _hecho(altura),
        "resumen_estados_ocupacion": {
            estado: sum(1 for h in ocupaciones if h.estado == estado)
            for estado in ("KNOWN", "ESTIMATED", "UNKNOWN", "NO_APLICABLE")
        },
        # Ámbito con el que se emite cada ocupación: es lo ÚNICO que debe
        # cambiar entre los dos escenarios (ver docstring).
        "ambitos_emitidos_ocupacion": [
            (h.diagnostico or {}).get("ambito_emitido") for h in ocupaciones
        ],
    }


def construir():
    p = golden.plano()
    unidades = evaluator.group_rooms_by_unit_label(p.rooms, p.unit_labels)
    return {
        "n_unidades": len(unidades),
        "sin_planta": _escenario(unidades, None),
        "planta_3": _escenario(unidades, 3),
    }


def ejecutar_golden() -> int:
    return golden.ejecutar("G5_hechos_cap", construir,
                           "CAP-1..CAP-5: hechos publicados, dos escenarios")


if __name__ == "__main__":
    raise SystemExit(ejecutar_golden())
