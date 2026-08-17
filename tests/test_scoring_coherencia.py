# -*- coding: utf-8 -*-
"""ArchMuse puntua el mismo proyecto con tres escalas que no coinciden.

Tarea 1 del PRD `docs/prd/2026-08-02-desglose-de-puntuacion-desplegable.md`.

Ejecutar como parte de la suite:  pytest tests/test_scoring_coherencia.py -s
Ejecutar suelto (igual que antes):  python tests/test_scoring_coherencia.py

ESTE TEST DEBE FALLAR HOY. Esta escrito para que la contradiccion deje de ser
una afirmacion mia en una conversacion y pase a ser un artefacto reproducible,
con numeros, que cualquiera puede ejecutar. Cuando pase, la tarea 3 del PRD
estara hecha y no antes.

Los tres sistemas:

  1. `UnitScore.score_pct` (evaluator.py:2387) = comprobaciones superadas /
     comprobaciones aplicables x 100. SIN PONDERAR: un fallo critico de
     sectorizacion de incendios pesa igual que una recomendacion sobre el
     fondo de una habitacion. Y el denominador cambia de una vivienda a otra
     segun cuantas reglas le apliquen, asi que dos viviendas con el mismo
     numero no han superado lo mismo. Es el numero que se ve en pantalla.
     Umbrales 85/70.

  2. `scoring.compute_scoring_breakdown` = cada categoria arranca en 100 y
     resta por severidad (15/7/2), con media ponderada por categoria. Si
     esta ponderado por gravedad, que es mas defendible, pero su agregacion
     a nivel de proyecto esta rota (ver comprobacion 4). Hoy no se enseña en
     ninguna parte: el popover que lo mostraba desaparecio con el rediseño
     del Shell. Solo sobrevive colgando de el `percentil_estimado`.

  3. `pdf_report._score_color` (pdf_report.py:30) = umbrales 80/60, propios.
     El mismo proyecto puede salir verde en la aplicacion y naranja en el PDF
     que descarga la propia aplicacion.

LENTO (~2 min): parsea ejemplo.dxf. No llama a la IA.

Nota de 2026-08-12: este archivo se ejecutaba como script suelto, con
`sys.exit(1)` a nivel de modulo. Bajo pytest eso no cuenta como un test que
falla: aborta la RECOLECCION de toda la suite con un INTERNALERROR, y
`tests/` entero deja de ejecutarse (falso verde si nadie revisa el código de
salida con atención). La logica de las comprobaciones no cambia: solo se ha
movido dentro de una funcion `test_*` y los `sys.exit` se han sustituido por
`pytest.skip` / `pytest.fail` / `pytest.xfail`, que es como pytest espera que
un test señale "no aplica" / "esto es un fallo real" / "esto falla a
propósito, hay una decisión de diseño pendiente" sin tirar abajo la sesión
de recoleccion completa.
"""
import inspect
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import api_serializer, pdf_report, scoring  # noqa: E402
from analyzer.evaluator import (  # noqa: E402
    SCORE_GREEN_THRESHOLD, SCORE_YELLOW_THRESHOLD, classify_problems, evaluate_advanced,
    score_rating)
from analyzer.parser import AREA_LAYER, leer_plano, load_document  # noqa: E402

DXF = os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf")

# Estas dos comprobaciones no se pueden arreglar sin decidir cual de los dos
# sistemas de puntuacion es LA puntuacion, y eso cambia todos los numeros de
# un proyecto ya guardado. Ver docs/design/2026-08-02-dos-sistemas-de-puntuacion.md.
PENDIENTES_DE_DECISION = {
    "los dos sistemas dan la misma puntuacion de proyecto",
    "y la misma valoracion",
}


def test_scoring_coherencia():
    fallos = []
    comprobaciones = 0

    def check(ok, etiqueta, detalle=""):
        nonlocal comprobaciones
        comprobaciones += 1
        print("  [%s] %s%s" % ("OK  " if ok else "FALLO", etiqueta, ("\n         " + detalle) if detalle else ""))
        if not ok:
            fallos.append(etiqueta)

    # ===================================================================
    # Comprobacion 3: no hace falta el DXF, son dos constantes.
    # ===================================================================
    print("A. Los umbrales de la aplicacion y del PDF")
    print()
    check(
        (pdf_report.SCORE_GOOD_MIN, pdf_report.SCORE_ACCEPTABLE_MIN)
        == (SCORE_GREEN_THRESHOLD, SCORE_YELLOW_THRESHOLD),
        "la aplicacion y el PDF usan los mismos umbrales",
        "app %.0f/%.0f  vs  PDF %.0f/%.0f" % (
            SCORE_GREEN_THRESHOLD, SCORE_YELLOW_THRESHOLD,
            pdf_report.SCORE_GOOD_MIN, pdf_report.SCORE_ACCEPTABLE_MIN),
    )

    if not os.path.exists(DXF):
        pytest.skip("no se encuentra %s: el resto necesita un proyecto real" % DXF)

    # ===================================================================
    print()
    print("B. El mismo proyecto por los dos sistemas (LENTO)")
    # ===================================================================
    print("  parseando %s ..." % DXF)
    plano = leer_plano(load_document(DXF), layer=AREA_LAYER)
    advanced = evaluate_advanced(plano.rooms, unit_labels=plano.unit_labels, norte_grados=0.0)
    issues = classify_problems(advanced, fire_compartmentation=advanced.fire_compartmentation)
    print()

    # Sistema 1, tal y como lo calcula `api_serializer.serialize_analysis`.
    unidades = advanced.unit_scores
    media_score_pct = sum(u.score_pct for u in unidades) / len(unidades)
    valoracion_1 = score_rating(media_score_pct)

    # Sistema 2, tal y como lo calcula `api_serializer.serialize_analysis`: agregado
    # POR VIVIENDA. `compute_scoring_breakdown(issues)` a secas -que es lo que se
    # hacia antes- se conserva abajo solo para medir cuanto desviaba.
    nombres = [u.unit.name for u in unidades]
    desglose = scoring.compute_project_breakdown(issues, nombres)
    desglose_crudo = scoring.compute_scoring_breakdown(issues)

    print("  vivienda        sistema 1 (pantalla)   sistema 2 (desglose, por vivienda)")
    for u in unidades:
        propios = [i for i in issues if i.unit_name == u.unit.name]
        d = scoring.compute_scoring_breakdown(propios)
        print("    %-10s   %5.1f  %-9s      %5.1f  %s" % (
            u.unit.name, u.score_pct, score_rating(u.score_pct), d.puntuacion_total, d.valoracion))
    print()
    print("  PROYECTO       %6.1f  %-9s      %5.1f  %s" % (
        media_score_pct, valoracion_1, desglose.puntuacion_total, desglose.valoracion))
    print()

    check(
        abs(media_score_pct - desglose.puntuacion_total) <= 1.0,
        "los dos sistemas dan la misma puntuacion de proyecto",
        "pantalla %.1f  vs  desglose %.1f  (diferencia de %.1f puntos)" % (
            media_score_pct, desglose.puntuacion_total,
            abs(media_score_pct - desglose.puntuacion_total)),
    )

    check(
        valoracion_1 == desglose.valoracion,
        "y la misma valoracion",
        "pantalla '%s'  vs  desglose '%s' sobre el MISMO proyecto" % (valoracion_1, desglose.valoracion),
    )

    # ===================================================================
    print()
    print("C. La agregacion del desglose a nivel de proyecto")
    # ===================================================================
    # `compute_scoring_breakdown` arranca cada categoria en 100 y va restando. Al
    # pasarle los issues de las SEIS viviendas de golpe, se aplica un unico techo
    # de 100 puntos a los problemas de todas: seis viviendas con dos incidencias
    # de la misma categoria cada una hunden esa categoria como si fuera una sola
    # vivienda con doce. Cuantas mas viviendas tenga el proyecto, peor puntua,
    # aunque cada vivienda por separado este bien.
    por_vivienda = [
        scoring.compute_scoring_breakdown([i for i in issues if i.unit_name == u.unit.name]).puntuacion_total
        for u in unidades
    ]
    media_por_vivienda = sum(por_vivienda) / len(por_vivienda)

    check(
        abs(desglose.puntuacion_total - media_por_vivienda) <= 1.0,
        "el desglose del proyecto es la media de los desgloses de sus viviendas",
        "proyecto %.1f  vs  media de las %d viviendas %.1f" % (
            desglose.puntuacion_total, len(unidades), media_por_vivienda),
    )
    print("         (agregando de golpe, como se hacia antes: %.1f '%s' -- %.1f puntos"
          " de desvio por el techo unico de 100 por categoria)" % (
              desglose_crudo.puntuacion_total, desglose_crudo.valoracion,
              abs(desglose_crudo.puntuacion_total - media_por_vivienda)))

    saturadas = [c.nombre for c in desglose.categorias if c.puntuacion <= 0.0]
    check(
        not saturadas,
        "ninguna categoria toca fondo por acumulacion entre viviendas",
        "a 0,0: %s" % ", ".join(saturadas) if saturadas else "",
    )

    # ===================================================================
    print()
    print("D. El percentil inventado no viaja en el payload")
    # ===================================================================
    # Colgaba de la puntuacion perdedora -daba percentil 45 en vez de 79 sobre el
    # mismo proyecto- y no lo consumia nadie: se retiro de la interfaz por ser una
    # tabla de tres puntos escrita a mano presentada como comparacion de mercado.
    # Dejarlo en el JSON solo servia para que volviera a colarse.
    check(
        "percentil" not in inspect.getsource(api_serializer),
        "api_serializer ya no calcula ni publica ningun percentil",
    )

    print()
    print("=" * 60)
    # La ultima comprobacion del bloque B -que los dos sistemas den la misma
    # puntuacion- NO se puede arreglar sin decidir cual de los dos es LA puntuacion,
    # y eso cambia todos los numeros de un proyecto ya guardado. Ver
    # docs/design/2026-08-02-dos-sistemas-de-puntuacion.md.
    defectos = [f for f in fallos if f not in PENDIENTES_DE_DECISION]
    pendientes = [f for f in fallos if f in PENDIENTES_DE_DECISION]

    if defectos:
        print("FALLOS (%d de %d):" % (len(defectos), comprobaciones))
        for f in defectos:
            print("  - %s" % f)
        pytest.fail("%d de %d comprobaciones en fallo: %s" % (len(defectos), comprobaciones, ", ".join(defectos)))

    print("Defectos corregidos: %d de %d comprobaciones en verde." % (
        comprobaciones - len(pendientes), comprobaciones))
    if pendientes:
        print()
        print("PENDIENTE DE DECISION (no es un fallo del codigo):")
        for f in pendientes:
            print("  - %s" % f)
        print()
        print("  Los dos sistemas miden cosas distintas y no van a coincidir hasta")
        print("  que se decida cual es LA puntuacion. Eso cambia todos los numeros")
        print("  de un proyecto ya guardado, asi que no se hace por iniciativa")
        print("  propia. Razonamiento y recomendacion en:")
        print("  docs/design/2026-08-02-dos-sistemas-de-puntuacion.md")
        pytest.xfail("pendiente de decision de diseño: %s" % ", ".join(pendientes))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-s", "-v"]))
