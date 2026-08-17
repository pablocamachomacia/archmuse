# -*- coding: utf-8 -*-
"""G7 — golden de la SEMILLA: `experimentos/grafo`.

Ejecutar:  python tests/test_golden_grafo_experimento.py

Congela la salida del constructor del experimento sobre `ejemplo.dxf`: nodos,
aristas por tipo, el mapa de presencia y la lista de lo que no se sabe.

**Por qué un golden sobre código desechable.** Porque el paso E1.7 del PRD lo
promociona: `experimentos/grafo/{modelo,api,constructor}.py` es lo más
parecido al futuro `modelo/` que existe hoy, y la promoción tiene que ser
demostrablemente equivalente. Sin este fixture, «hemos movido el experimento a
producción» es una afirmación sin comprobación.

**Se congelan las dos variantes de criterio**, la actual y la estricta, porque
la diferencia entre ambas es el dato que sostiene la decisión abierta del
umbral de contigüidad (decisión 3 de E0): con los proyectos reales habrá que
elegir, y esto deja medido qué cambia exactamente en `ejemplo.dxf`.

**Lo que este golden NO valida:** que el experimento sea correcto. Sólo que no
cambia sin que nadie se entere.
"""
import golden

from experimentos.grafo.constructor import (
    CRITERIO_ACTUAL,
    CRITERIO_ESTRICTO,
    construir_grafo,
)
from experimentos.grafo.modelo import CONECTA_CON, ES_CONTIGUO_A


def _resumen(grafo):
    espacios = grafo.get_spaces()
    # Grados por la superficie PÚBLICA del API, no por `grafo._aristas`: si el
    # golden mirase dentro, la promoción a `modelo/` (E1.7) podría cambiar la
    # estructura interna sin que nadie lo notara, que es justo lo contrario de
    # lo que este fixture existe para vigilar.
    contiguos = sum(len(grafo.contiguous_spaces(e)) for e in espacios)
    conectados = sum(len(grafo.connected_spaces(e)) for e in espacios)
    return {
        "n_espacios": len(espacios),
        "n_unidades": len(grafo.unidades()),
        "n_aristas": {
            ES_CONTIGUO_A: contiguos // 2,   # simétricas: cada arista se cuenta dos veces
            CONECTA_CON: conectados // 2,
        },
        "presencia": dict(grafo.proyecto.presencia),
        "tipos_resueltos": sorted(
            {(e.tipo.valor or "desconocido") for e in espacios}
        ),
        "n_tipo_desconocido": sum(1 for e in espacios if not e.tipo.conocido),
        "desconocidos": sorted(grafo.desconocidos()),
        "espacios": [
            {"id": e.id, "unidad": e.unidad_id, "rotulo": e.rotulo,
             "tipo": e.tipo.valor, "origen_tipo": e.tipo.origen,
             "area_m2": float(e.area_m2), "alargamiento": float(e.alargamiento)}
            for e in espacios
        ],
    }


def construir():
    p = golden.plano()
    return {
        "criterio_actual": _resumen(construir_grafo(p, criterio=CRITERIO_ACTUAL)),
        "criterio_estricto": _resumen(construir_grafo(p, criterio=CRITERIO_ESTRICTO)),
        "parametros": {
            "actual": {
                "tolerancia_muro_m": CRITERIO_ACTUAL.tolerancia_muro_m,
                "tramo_minimo_conexion_m": CRITERIO_ACTUAL.tramo_minimo_conexion_m,
                "tramo_minimo_contiguidad_m": CRITERIO_ACTUAL.tramo_minimo_contiguidad_m,
            },
            "estricto": {
                "tolerancia_muro_m": CRITERIO_ESTRICTO.tolerancia_muro_m,
                "tramo_minimo_conexion_m": CRITERIO_ESTRICTO.tramo_minimo_conexion_m,
                "tramo_minimo_contiguidad_m": CRITERIO_ESTRICTO.tramo_minimo_contiguidad_m,
            },
        },
    }


def ejecutar_golden() -> int:
    return golden.ejecutar("G7_grafo_experimento", construir,
                           "semilla del modelo: nodos, aristas y presencia")


if __name__ == "__main__":
    raise SystemExit(ejecutar_golden())
