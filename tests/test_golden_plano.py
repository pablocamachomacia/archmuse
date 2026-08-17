# -*- coding: utf-8 -*-
"""G1 — golden del LECTOR: `parser.leer_plano(ejemplo.dxf)`.

Ejecutar:  python tests/test_golden_plano.py

Congela lo que ArchMuse consigue leer de un DXF antes de interpretar nada:
qué capa eligió, en qué unidad decidió que está dibujado, y la lista completa
de recintos con su rótulo literal y su geometría derivada.

**Por qué el orden de lectura se congela y no se ordena alfabéticamente.**
`group_rooms_by_unit_label` (G2), el grafo de `adyacencia.py` (G3) y los
recorridos de `circulation.py` (G4) resuelven sus empates por el orden en que
el parser devuelve las habitaciones — está dicho explícitamente en
`experimentos/grafo/constructor.py`. Ese orden es, por tanto, parte del
contrato: si cambiara, cambiarían resultados aguas arriba sin que ninguna
constante se hubiera tocado. Se congela con su índice.

**Qué NO congela:** los polígonos punto a punto. Área, perímetro, centroide y
envolvente son función pura de la geometría (los derivados admitidos de
`KNOWLEDGE_GRAPH.md` §0.2) y detectan cualquier cambio real de forma; volcar
las ~1.500 coordenadas haría el fixture ilegible y el diff inútil.
"""
import golden


def construir():
    p = golden.plano()
    escala = p.escala
    return {
        "escala": {
            "factor": escala.factor,
            "unidad": escala.unidad,
            "origen": escala.origen,
            "codigo_insunits": getattr(escala, "codigo_insunits", None),
        },
        "capa_elegida": p.layer,
        "n_recintos": len(p.rooms),
        "n_etiquetas_vivienda": len(p.unit_labels),
        # Orden de lectura del parser: es contrato (ver docstring), no ruido.
        "recintos": [
            {
                "i": i,
                "rotulo": r.label,
                "capa": r.layer,
                "area_m2": float(r.polygon.area),
                "perimetro_m": float(r.polygon.length),
                "centroide": [float(r.polygon.centroid.x), float(r.polygon.centroid.y)],
                "envolvente": [float(v) for v in r.polygon.bounds],
            }
            for i, r in enumerate(p.rooms)
        ],
        # Las etiquetas VT sí se ordenan: el parser no garantiza su orden y
        # `group_rooms_by_unit_label` sólo mide distancias, no posiciones.
        "etiquetas_vivienda": sorted(
            [{"texto": t, "x": float(x), "y": float(y)} for t, x, y in p.unit_labels],
            key=lambda e: (e["texto"], e["x"], e["y"]),
        ),
    }


def ejecutar_golden() -> int:
    return golden.ejecutar("G1_plano", construir,
                           "lector: escala, capa y recintos en crudo")


if __name__ == "__main__":
    raise SystemExit(ejecutar_golden())
