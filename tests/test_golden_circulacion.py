# -*- coding: utf-8 -*-
"""G4 — golden de CIRCULACIÓN: `circulation.evaluate_circulation`.

Ejecutar:  python tests/test_golden_circulacion.py

Congela las cinco comprobaciones de recorrido de cada vivienda: tipo, si pasa,
el mensaje literal, el camino de habitaciones y la métrica.

**Es el oráculo del primer paso de E1.** `circulation.py` es el único módulo
de producción que E1 toca (pasos E1.13 y E1.15 del PRD): deja de construir su
grafo privado y pasa a leer el del modelo. El experimento ya midió que el
resultado es idéntico —12 de 12 salidas— pero lo midió sobre dos reglas de las
cinco; este fixture cubre las cinco, en las seis viviendas.

**DEFECTO CONOCIDO CONGELADO A PROPÓSITO.** En VT6/2, el hallazgo «Baño:
acceso directo desde Salón/cocina, sin antesala» se apoya en un contacto de
0,000 m de tramo enfrentado: las dos piezas se tocan en una esquina, no a lo
largo de un muro. Es un falso positivo real, hoy visible en producción, y está
congelado aquí **tal y como está hoy**, no como debería estar. Cuando E1 lo
haga desaparecer, este golden fallará: ése es el mecanismo por el que la
diferencia llega a Pablo para su aprobación explícita (paso E1.14) en vez de
colarse. No recapturar sin esa aprobación.
"""
import golden

from analyzer import circulation, evaluator

NOTA_DEFECTO_CONOCIDO = (
    "VT6/2 'bano_sin_antesala' es un FALSO POSITIVO conocido (tramo enfrentado "
    "0,000 m: contacto en esquina). Congelado deliberadamente. Desaparece en "
    "E1; su diff exige aprobacion explicita (PRD paso E1.14)."
)


def construir():
    p = golden.plano()
    avanzado = evaluator.evaluate_advanced(
        p.rooms, unit_labels=p.unit_labels, norte_grados=0.0,
        tipologia="plurifamiliar", zona_cte="C", densidad_urbana="media",
    )

    unidades = []
    for us in avanzado.unit_scores:
        circ = circulation.evaluate_circulation(us)
        rutas = [
            {
                "tipo": r.tipo,
                "passed": bool(r.passed),
                "message": r.message,
                "camino": list(r.path_labels),
                "metrica": float(r.metric_value) if r.metric_value is not None else None,
            }
            for r in circ.routes
        ]
        unidades.append({
            "nombre": circ.unit_name,
            "score_pct": float(circ.score_pct),
            "n_rutas": len(rutas),
            "n_problemas": sum(1 for r in rutas if not r["passed"]),
            "rutas": sorted(rutas, key=lambda r: (r["tipo"], r["message"], r["camino"])),
        })

    return {
        "nota": NOTA_DEFECTO_CONOCIDO,
        "n_unidades": len(unidades),
        "n_problemas_total": sum(u["n_problemas"] for u in unidades),
        "unidades": unidades,
    }


def ejecutar_golden() -> int:
    return golden.ejecutar("G4_circulacion", construir,
                           "recorridos: las 5 comprobaciones por vivienda")


if __name__ == "__main__":
    raise SystemExit(ejecutar_golden())
