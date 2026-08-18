"""Compara la regla 1 de circulación en sus dos implementaciones.

    python -m experimentos.comparar_regla [ruta.dxf]

A: `analyzer.circulation._check_absurd_routes` — la de producción, sobre Room,
   regex y un grafo de adyacencias privado.
B: `experimentos.grafo.regla_recorridos` — la misma regla escrita solo contra
   la Graph API.

Mide tres cosas, en este orden de importancia:

1. **¿Dan el mismo resultado?** Si no, la arquitectura todavía no está
   validada, por muy bonita que quede la API.
2. **¿Es más simple?** Líneas de la regla y de qué depende cada una.
3. **¿Qué cambia con el criterio estricto de §4?** El grafo permite cambiar la
   definición de adyacencia en un sitio y ver el efecto; hoy eso exige tocar
   cuatro módulos.
"""
from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path
from typing import List, Tuple

from analyzer.circulation import (
    _build_adjacency_graph,
    _check_absurd_routes,
    _check_bathroom_access,
)
from analyzer.evaluator import group_rooms_by_unit_label
from analyzer.parser import CapaIndeterminada, EscalaIndeterminada, leer_plano, load_document

from .grafo import regla_recorridos
from .grafo.constructor import CRITERIO_ACTUAL, CRITERIO_ESTRICTO, construir_grafo

#: `ejemplo.dxf` es un plano real y vive JUNTO al repositorio, no dentro. Se
#: deriva de la ubicación de este fichero y nunca de una ruta personal: misma
#: convención que `main.py` y que los tests.
DXF_POR_DEFECTO = str(Path(__file__).resolve().parents[2] / "ejemplo.dxf")

Fila = Tuple[str, bool, str, Tuple[str, ...]]


def _consola_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


REGLAS = [
    ("1 · recorrido dormitorio→baño", _check_absurd_routes,
     regla_recorridos.recorridos_dormitorio_bano),
    ("4 · baño sin antesala", _check_bathroom_access,
     regla_recorridos.banos_sin_antesala),
]


def _filas_produccion(unidad, funcion) -> List[Fila]:
    grafo = _build_adjacency_graph(unidad)
    filas = []
    for ruta in funcion(unidad, grafo):
        etiquetas = tuple(r.label or "(sin etiqueta)" for r in ruta.path)
        filas.append((unidad.name, ruta.passed, ruta.message, etiquetas))
    return sorted(filas)


def _filas_grafo(vista, funcion) -> List[Fila]:
    filas = []
    for recorrido in funcion(vista):
        filas.append((vista.unidad.id, recorrido.correcto, recorrido.mensaje,
                      tuple(recorrido.etiquetas)))
    return sorted(filas)


def _lineas_de_codigo(funcion) -> int:
    """Líneas con contenido real: sin blancos, sin comentarios, sin docstring."""
    fuente = inspect.getsource(funcion)
    arbol = ast.parse(fuente)
    cuerpo = arbol.body[0].body
    if (cuerpo and isinstance(cuerpo[0], ast.Expr)
            and isinstance(getattr(cuerpo[0], "value", None), ast.Constant)
            and isinstance(cuerpo[0].value.value, str)):
        cuerpo = cuerpo[1:]  # fuera el docstring
    if not cuerpo:
        return 0
    lineas = fuente.splitlines()
    desde = cuerpo[0].lineno - 1
    hasta = max(getattr(n, "end_lineno", n.lineno) for n in cuerpo)
    return sum(
        1 for linea in lineas[desde:hasta]
        if linea.strip() and not linea.strip().startswith("#")
    )


def _importaciones(modulo) -> List[str]:
    arbol = ast.parse(inspect.getsource(modulo))
    nombres = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres.update(a.name.split(".")[0] for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            nombres.add(("." * nodo.level) + nodo.module)
        elif isinstance(nodo, ast.ImportFrom):
            nombres.add("." * nodo.level)
    return sorted(nombres)


def main() -> int:
    _consola_utf8()
    ruta = sys.argv[1] if len(sys.argv) > 1 else DXF_POR_DEFECTO
    try:
        plano = leer_plano(load_document(ruta))
    except (FileNotFoundError, ValueError, CapaIndeterminada, EscalaIndeterminada) as exc:
        print(f"Error: {exc}")
        return 1

    unidades = group_rooms_by_unit_label(plano.rooms, plano.unit_labels)
    grafo = construir_grafo(plano, criterio=CRITERIO_ACTUAL)

    print("=" * 78)
    print("1. ¿MISMO RESULTADO?   (criterio de adyacencia idéntico al actual)")
    print("=" * 78)

    total_a = total_b = total_problemas = 0
    discrepancias = 0
    for titulo, funcion_a, funcion_b in REGLAS:
        print(f"\n  Regla {titulo}")
        for unidad in unidades:
            filas_a = _filas_produccion(unidad, funcion_a)
            filas_b = _filas_grafo(grafo.unidad(unidad.name), funcion_b)
            total_a += len(filas_a)
            total_b += len(filas_b)
            problemas_a = sum(1 for f in filas_a if not f[1])
            total_problemas += problemas_a
            iguales = filas_a == filas_b
            marca = "IGUAL" if iguales else "DISTINTO"
            print(f"    {unidad.name:<8} {len(filas_a):>3} salidas "
                  f"({problemas_a} problemáticas)   {marca}")
            if not iguales:
                discrepancias += 1
                for fila in [f for f in filas_a if f not in filas_b]:
                    print(f"        solo en producción: {fila[2]}  camino={list(fila[3])}")
                for fila in [f for f in filas_b if f not in filas_a]:
                    print(f"        solo en el grafo  : {fila[2]}  camino={list(fila[3])}")

    print()
    print(f"  Total: {total_a} salidas en producción, {total_b} sobre el grafo, "
          f"{total_problemas} problemas detectados, {discrepancias} casos con diferencias")

    print()
    print("=" * 78)
    print("2. ¿ES MÁS SIMPLE?")
    print("=" * 78)
    for titulo, funcion_a, funcion_b in REGLAS:
        print(f"  Regla {titulo}: "
              f"{_lineas_de_codigo(funcion_a)} líneas en producción → "
              f"{_lineas_de_codigo(funcion_b)} sobre el grafo")
    infra_a = sum(_lineas_de_codigo(f) for f in (
        _build_adjacency_graph, sys.modules["analyzer.circulation"]._bfs_path))
    print(f"  (+ la infraestructura que cada regla arrastra: {infra_a} líneas de grafo "
          "privado dentro de circulation.py, 0 en la versión sobre el API)")
    print()
    print("  de qué depende cada módulo de regla:")
    print(f"    circulation.py            : {', '.join(_importaciones(sys.modules['analyzer.circulation']))}")
    print(f"    regla_recorridos.py       : {', '.join(_importaciones(regla_recorridos))}")
    # Comprobación mecánica sobre los imports reales (AST), no sobre el texto:
    # buscar las palabras en el fuente daba falsos positivos con el docstring.
    importados = set(_importaciones(regla_recorridos))
    prohibidos = {"shapely", "analyzer", "re", ".parser", ".evaluator", ".constructor"}
    colados = sorted(importados & prohibidos)
    print(f"    imports prohibidos en la regla: {', '.join(colados) if colados else 'ninguno'}")
    cuerpo = inspect.getsource(regla_recorridos.recorridos_dormitorio_bano)
    for prohibido in ("id(", "_normalize", "re.compile", ".polygon"):
        estado = "no" if prohibido not in cuerpo else "SÍ (!)"
        print(f"    ¿usa «{prohibido}»?: {estado}")

    print()
    print("=" * 78)
    print("3. ¿QUÉ CAMBIA CON EL CRITERIO ESTRICTO DE §4?")
    print("=" * 78)
    grafo_estricto = construir_grafo(plano, criterio=CRITERIO_ESTRICTO)
    for titulo, _funcion_a, funcion_b in REGLAS:
        print(f"\n  Regla {titulo}")
        for unidad in unidades:
            filas_actual = _filas_grafo(grafo.unidad(unidad.name), funcion_b)
            filas_estricto = _filas_grafo(grafo_estricto.unidad(unidad.name), funcion_b)
            p_actual = sum(1 for f in filas_actual if not f[1])
            p_estricto = sum(1 for f in filas_estricto if not f[1])
            aviso = "" if filas_actual == filas_estricto else "   <-- cambia"
            print(f"    {unidad.name:<8} actual: {len(filas_actual):>3} salidas / {p_actual} problemas"
                  f"    estricto: {len(filas_estricto):>3} / {p_estricto}{aviso}")

    return 0 if discrepancias == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
