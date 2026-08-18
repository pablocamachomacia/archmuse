# -*- coding: utf-8 -*-
"""Tarea 6 — el aviso de zona climática supuesta en `limitaciones`.

Ejecutar:  pytest tests/test_aviso_zona_climatica.py

**Qué problema resuelve la tarea.** `cte_zonas` repliega a la zona "C" cuando
no sabe el municipio, y ese repliegue era indistinguible de un dato real: el
JSON decía `"zona_cte": "C"` tanto para Barcelona (donde es cierto) como para
Cuenca (donde es una suposición). De la zona dependen el riesgo de
condensaciones, las horas de sol y el umbral de compacidad, así que el
arquitecto estaba leyendo tres comprobaciones calculadas sobre un dato
inventado sin ninguna forma de saberlo.

**Qué NO hace la tarea.** No cambia ni un valor devuelto. El análisis sigue
haciéndose en zona C; lo único que cambia es que ahora lo dice. Eso es
deliberado: cambiar el repliegue sería una regresión de comportamiento y
tiene su propio sitio (`normativa.api`, que devuelve `None` y pregunta).

La cobertura de extremo a extremo — que el aviso llega de verdad al JSON de
`POST /api/analizar` — está en el golden G6 (`tests/test_golden_api_analizar.py`),
escenario `ciudad_no_reconocida`. Aquí se comprueba la unidad.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from analyzer.evaluator import get_missing_data_warnings  # noqa: E402

ETIQUETA = "Zona climática:"


def _avisos_de_zona(**kwargs):
    return [w for w in get_missing_data_warnings(**kwargs) if w.startswith(ETIQUETA)]


def test_sin_informar_no_hay_aviso():
    """Compatibilidad hacia atrás: quien llame como antes de la tarea 6 recibe
    exactamente lo de antes. Es lo que permite que la firma cambie sin tocar a
    los llamadores que no saben nada de zonas climáticas."""
    assert _avisos_de_zona() == []


def test_zona_resuelta_no_avisa():
    """Barcelona es zona C por dato. Avisar aquí sería el peor fallo posible
    de esta tarea: un aviso que salta cuando no debe se deja de leer."""
    assert _avisos_de_zona(zona_cte="C", zona_cte_supuesta=False, ciudad="Barcelona") == []


def test_ciudad_no_reconocida_avisa_y_la_nombra():
    """El arquitecto tiene que poder ver QUÉ escribió que no se reconoció; si
    no, el aviso no le dice qué corregir."""
    avisos = _avisos_de_zona(zona_cte="C", zona_cte_supuesta=True, ciudad="Cuenca")
    assert len(avisos) == 1
    assert "Cuenca" in avisos[0]
    assert "no está en la tabla" in avisos[0]


def test_sin_ciudad_avisa_con_otro_motivo():
    """No indicar ciudad y escribir una que no existe son dos errores
    distintos y se arreglan de forma distinta."""
    avisos = _avisos_de_zona(zona_cte="C", zona_cte_supuesta=True, ciudad="")
    assert len(avisos) == 1
    assert "no se ha indicado la ciudad" in avisos[0]


def test_el_aviso_dice_que_comprobaciones_dependen_de_la_zona():
    """El valor de la transparencia no está en decir "es supuesto", sino en
    decir qué queda tocado por esa suposición."""
    aviso = _avisos_de_zona(zona_cte="C", zona_cte_supuesta=True, ciudad="Cuenca")[0]
    for termino in ("condensaciones", "horas de sol", "compacidad", "CTE DB-HE"):
        assert termino in aviso, termino


def test_el_aviso_no_sustituye_a_ninguno_de_los_de_siempre():
    """Se AÑADE a la lista existente, no la reemplaza — la tarea 6 dice
    explícitamente que no rompe compatibilidad de forma."""
    antes = get_missing_data_warnings()
    despues = get_missing_data_warnings(zona_cte="C", zona_cte_supuesta=True, ciudad="Cuenca")
    assert len(despues) == len(antes) + 1
    assert set(antes).issubset(set(despues))


if __name__ == "__main__":
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith("test_"):
            try:
                fn()
                print("OK   %s" % nombre)
            except AssertionError as exc:
                fallos += 1
                print("FALLO %s: %s" % (nombre, str(exc)[:300]))
    print("\n%s" % ("TODO OK" if not fallos else "%d FALLOS" % fallos))
    sys.exit(1 if fallos else 0)
