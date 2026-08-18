# -*- coding: utf-8 -*-
"""G3 — golden del GRAFO: `adyacencia.construir_grafo` con el criterio de hoy.

Ejecutar:  python tests/test_golden_adyacencia.py

Congela, vivienda a vivienda, qué pares de recintos son vecinos con
`WALL_GAP_TOLERANCE_M = 0.5`, con su separación real y la distancia entre
centroides que pesa cada arista.

**`tramo_m` se mide y se congela, pero no filtra.** Es la segunda condición de
contigüidad que `KNOWLEDGE_GRAPH.md` §4 pide y que el criterio de hoy no
aplica. Decisión cerrada de E0 (PRD, decisión 3): E1 conserva el criterio
actual y guarda `tramo_m` sin usarlo como filtro, porque el experimento
demostró que el umbral propuesto no está justificado — en VT3/3 hay un tramo
de 0,570 m, tres centímetros por debajo del 0,60 m que se había propuesto, y
de él depende que aparezca o no un hallazgo. Congelar la medida ahora es lo
que permitirá elegir el umbral con los proyectos reales en vez de a ojo.

**Y congela la evidencia que justifica el umbral que sí hay.** `adyacencia.py`
afirma en su cabecera que los huecos entre piezas contiguas llegan a 0,38 m y
que el primer par NO contiguo salta a 2,27 m. Esa medición es la única
justificación del 0,5 m y hasta hoy vivía en un comentario: aquí queda
comprobada en cada ejecución.
"""
import golden

from analyzer import adyacencia, evaluator


def _tramo_enfrentado(a, b, tolerancia):
    """Longitud del tramo en que dos contornos se miran de frente.

    Misma fórmula que `experimentos/grafo/constructor._tramo_enfrentado`,
    reimplementada aquí a propósito: un golden no debe depender de código
    desechable (`experimentos/`) ni de código que todavía no existe
    (`modelo/`), o dejaría de ser estable justo durante la migración que
    existe para vigilar.

    No se puede medir como borde compartido: en estos planos los polígonos
    casi nunca se tocan, que es por lo que el antiguo `evaluator._is_adjacent`
    (borde compartido, ya eliminado) no disparaba.
    """
    ab = b.polygon.boundary.intersection(a.polygon.buffer(tolerancia)).length
    ba = a.polygon.boundary.intersection(b.polygon.buffer(tolerancia)).length
    return float(min(ab, ba))


def construir():
    p = golden.plano()
    unidades = evaluator.group_rooms_by_unit_label(p.rooms, p.unit_labels)
    indice = {id(r): i for i, r in enumerate(p.rooms)}

    unidades_salida = []
    todas_contiguas = []
    todas_no_contiguas = []

    for u in unidades:
        grafo = adyacencia.construir_grafo(u.rooms)
        aristas = []
        vistos = set()
        for a in u.rooms:
            for b, distancia in grafo[id(a)]:
                clave = tuple(sorted((indice[id(a)], indice[id(b)])))
                if clave in vistos:
                    continue
                vistos.add(clave)
                separacion = float(a.polygon.distance(b.polygon))
                aristas.append({
                    "i": clave[0], "j": clave[1],
                    "rotulo_i": (a if indice[id(a)] == clave[0] else b).label,
                    "rotulo_j": (b if indice[id(b)] == clave[1] else a).label,
                    "separacion_m": separacion,
                    "distancia_m": float(distancia),
                    "tramo_m": _tramo_enfrentado(a, b, adyacencia.WALL_GAP_TOLERANCE_M),
                })
                todas_contiguas.append(separacion)

        # Todos los pares de la vivienda, para poder medir el margen entre lo
        # contiguo y lo que no lo es (la justificación del umbral).
        for x in range(len(u.rooms)):
            for y in range(x + 1, len(u.rooms)):
                a, b = u.rooms[x], u.rooms[y]
                separacion = float(a.polygon.distance(b.polygon))
                if separacion > adyacencia.WALL_GAP_TOLERANCE_M:
                    todas_no_contiguas.append(separacion)

        unidades_salida.append({
            "nombre": u.name,
            "n_recintos": len(u.rooms),
            "n_aristas": len(aristas),
            "aristas": sorted(aristas, key=lambda a: (a["i"], a["j"])),
        })

    return {
        "tolerancia_muro_m": adyacencia.WALL_GAP_TOLERANCE_M,
        "n_aristas_total": sum(u["n_aristas"] for u in unidades_salida),
        "unidades": unidades_salida,
        "margen_del_umbral": {
            "n_pares_contiguos": len(todas_contiguas),
            "n_pares_no_contiguos": len(todas_no_contiguas),
            "separacion_maxima_contigua_m": max(todas_contiguas) if todas_contiguas else None,
            "separacion_minima_no_contigua_m": min(todas_no_contiguas) if todas_no_contiguas else None,
        },
    }


def ejecutar_golden() -> int:
    return golden.ejecutar("G3_adyacencia", construir,
                           "grafo de contiguidad (tolerancia 0,5 m)")


if __name__ == "__main__":
    raise SystemExit(ejecutar_golden())
