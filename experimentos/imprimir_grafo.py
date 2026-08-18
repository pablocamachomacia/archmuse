"""Imprime el grafo de conocimiento construido a partir de un DXF.

    python -m experimentos.imprimir_grafo [ruta.dxf] [--estricto] [--unidad VT1/3]

No evalúa nada: solo enseña qué hay dentro del grafo, incluido lo que no se
sabe. Ver lo que NO tiene es la mitad del valor de imprimirlo.
"""
from __future__ import annotations

import sys
from pathlib import Path

from analyzer.parser import CapaIndeterminada, EscalaIndeterminada, leer_plano, load_document

from .grafo.constructor import CRITERIO_ACTUAL, CRITERIO_ESTRICTO, construir_grafo
from .grafo.modelo import CONECTA_CON, ES_CONTIGUO_A

#: `ejemplo.dxf` es un plano real y vive JUNTO al repositorio, no dentro. Se
#: deriva de la ubicación de este fichero y nunca de una ruta personal: misma
#: convención que `main.py` y que los tests.
DXF_POR_DEFECTO = str(Path(__file__).resolve().parents[2] / "ejemplo.dxf")


def _consola_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def imprimir(grafo, solo_unidad=None) -> None:
    p = grafo.proyecto
    print("=" * 78)
    print("PROYECTO")
    print("=" * 78)
    print(f"  origen        : {p.origen}")
    print(f"  capa          : {p.capa}")
    print(f"  escala        : factor {p.escala}")
    print(f"  tipología     : {p.tipologia}")
    print(f"  ciudad        : {p.ciudad}")
    print(f"  norte         : {p.norte_grados}")
    print()
    print("  presencia por tipo de nodo:")
    for nodo, estado in p.presencia.items():
        marca = {"observado": "OK ", "inferido": "~  ", "no_observable": "-- "}.get(estado, "?  ")
        print(f"    {marca} {nodo:<12} {estado}")

    for unidad in grafo.unidades():
        if solo_unidad and unidad.id != solo_unidad:
            continue
        vista = grafo.unidad(unidad.id)
        espacios = vista.get_spaces()
        print()
        print("=" * 78)
        print(f"UNIDAD {unidad.id}   etiqueta: {unidad.etiqueta}   {len(espacios)} espacios")
        print("=" * 78)
        for e in espacios:
            print(f"  {e.id}  {str(e.tipo):<26} {e.area_m2:7.2f} m²  "
                  f"alarg. {e.alargamiento:4.2f}  rótulo {e.rotulo!r}")

        print()
        print("  relaciones:")
        for e in espacios:
            contiguos = vista.contiguous_spaces(e)
            conectados = vista.connected_spaces(e)
            print(f"    {e.id} ({e.tipo.valor})")
            print(f"        es contiguo a : {', '.join(x.id for x in contiguos) or '—'}")
            print(f"        conecta con   : {', '.join(x.id for x in conectados) or '—'}")

        muros = [
            a for a in grafo._aristas
            if a.tipo == ES_CONTIGUO_A and a.a.startswith(unidad.id + "::")
        ]
        if muros:
            espesores = sorted(a.separacion_m for a in muros)
            print()
            print(f"  muros inferidos: {len(muros)}  "
                  f"espesor {espesores[0]:.3f}–{espesores[-1]:.3f} m")

    print()
    print("=" * 78)
    print("LO QUE ESTE GRAFO NO SABE")
    print("=" * 78)
    for falta in grafo.desconocidos():
        print(f"  - {falta}")

    n_cont = sum(1 for a in grafo._aristas if a.tipo == ES_CONTIGUO_A)
    n_con = sum(1 for a in grafo._aristas if a.tipo == CONECTA_CON)
    print()
    print(f"TOTAL: {len(grafo.get_spaces())} espacios, {len(grafo.unidades())} unidades, "
          f"{n_cont} aristas 'es contiguo a', {n_con} aristas 'conecta con'")


def main() -> int:
    _consola_utf8()
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    ruta = argumentos[0] if argumentos else DXF_POR_DEFECTO
    criterio = CRITERIO_ESTRICTO if "--estricto" in sys.argv else CRITERIO_ACTUAL
    unidad = None
    if "--unidad" in sys.argv:
        unidad = sys.argv[sys.argv.index("--unidad") + 1]

    try:
        plano = leer_plano(load_document(ruta))
    except (FileNotFoundError, ValueError, CapaIndeterminada, EscalaIndeterminada) as exc:
        print(f"Error: {exc}")
        return 1

    print(f"[criterio de adyacencia: {criterio.nombre}]")
    imprimir(construir_grafo(plano, criterio=criterio), solo_unidad=unidad)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
