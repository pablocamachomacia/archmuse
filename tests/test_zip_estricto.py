# -*- coding: utf-8 -*-
"""Tarea 7 — ningún `zip()` puede truncar en silencio sin haberlo decidido.

Ejecutar:  pytest tests/test_zip_estricto.py

`zip(a, b)` con listas de distinto largo no falla: devuelve el mínimo de los
dos y descarta el resto. Cuando las dos listas son "la misma cosa vista de dos
maneras" —una vivienda y su hecho, un espacio y su `Room`— ese descarte no es
una lista más corta, es un resultado **emparejado con el elemento equivocado**,
y no deja ni un rastro.

**Por qué esto es un test y no una revisión de una tarde.** El sweep de la
tarea 7 arregla los `zip()` de hoy. Un `zip()` nuevo mañana vuelve a entrar sin
que nadie lo note — que es exactamente lo que pasó con los clientes de
Anthropic de la tarea 9 (2 en la ficha, 5 en la auditoría, 6 de verdad).

**La regla.** Todo `zip()` en código de producto lleva `strict=`, o lleva un
comentario `zip-sin-strict:` en la línea de arriba explicando por qué no. Las
dos salidas son válidas; lo que no vale es no haberlo pensado.

Hay dos razones legítimas para no llevarlo, y las dos están hoy en el
repositorio:

1. **El emparejado desigual es el objetivo.** `zip(dorms, dorms[1:])` recorre
   pares consecutivos: sus largos difieren en 1 por definición y `strict=True`
   levantaría siempre.
2. **Ya se valida antes, y mejor.** `ocupacion_por_zona` y
   `limite_superficie_sector` comprueban los largos al entrar y levantan un
   `ValueError` que dice cuántos hay de cada uno. `strict=True` daría el mismo
   error con peor mensaje.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# Código de producto. `tests/` y `experimentos/` quedan fuera a propósito: el
# primero puede querer construir un desajuste para probarlo, y el segundo es
# desechable por diseño.
AMBITO = ("analyzer", "modelo", "normativa", "extraccion", "ingesta", "ia")
SUELTOS = ("app.py", "main.py")

MARCA = "zip-sin-strict:"


def _ficheros():
    for paquete in AMBITO:
        yield from sorted((RAIZ / paquete).rglob("*.py"))
    for nombre in SUELTOS:
        ruta = RAIZ / nombre
        if ruta.is_file():
            yield ruta


def _zips_sin_strict(ruta: Path):
    """(línea, fuente) de cada `zip()` sin `strict=` y sin su justificación."""
    texto = ruta.read_text(encoding="utf-8")
    lineas = texto.split("\n")
    try:
        arbol = ast.parse(texto, filename=str(ruta))
    except SyntaxError:  # lo reporta la recolección de pytest, no este test
        return []

    salida = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        if not (isinstance(nodo.func, ast.Name) and nodo.func.id == "zip"):
            continue
        if any(kw.arg == "strict" for kw in nodo.keywords):
            continue
        # La justificación va en las tres líneas anteriores: caben un
        # comentario de varias líneas y el propio `for`.
        contexto = lineas[max(0, nodo.lineno - 4):nodo.lineno]
        if any(MARCA in linea for linea in contexto):
            continue
        salida.append((nodo.lineno, lineas[nodo.lineno - 1].strip()))
    return salida


def test_todo_zip_de_produccion_decide_sobre_strict():
    culpables = []
    for ruta in _ficheros():
        for linea, fuente in _zips_sin_strict(ruta):
            culpables.append("%s:%d  %s" % (ruta.relative_to(RAIZ).as_posix(), linea, fuente))

    assert not culpables, (
        "estos `zip()` truncan en silencio si los largos no coinciden. Anade "
        "`strict=True`, o un comentario `%s <motivo>` en la linea de arriba si "
        "el desajuste es deliberado:\n  " % MARCA + "\n  ".join(culpables)
    )


def test_la_marca_de_excepcion_no_se_reparte_sola():
    """La válvula de escape tiene que seguir siendo rara. Si crece, es que se
    está usando para saltarse la regla en vez de para documentar una
    excepción real."""
    con_marca = sum(
        ruta.read_text(encoding="utf-8").count(MARCA) for ruta in _ficheros()
    )
    assert con_marca <= 5, (
        "hay %d usos de `%s` en produccion. Eran 3 cuando se escribio la regla "
        "(zip por pares consecutivos en evaluator, y los dos que ya validan "
        "largos al entrar). Revisa si los nuevos son excepciones de verdad."
        % (con_marca, MARCA)
    )


def test_strict_true_hace_lo_que_se_espera_de_el():
    """Que la herramienta que estamos exigiendo levante de verdad. Barato, y
    evita que la regla entera descanse sobre una suposición."""
    import pytest

    assert list(zip([1, 2], "ab", strict=True)) == [(1, "a"), (2, "b")]
    with pytest.raises(ValueError):
        list(zip([1, 2, 3], "ab", strict=True))
    # Y que sin él, efectivamente, se pierde el tercero sin decir nada.
    assert list(zip([1, 2, 3], "ab")) == [(1, "a"), (2, "b")]
