# -*- coding: utf-8 -*-
"""Valida los borradores de un paquete de curación antes de imprimir la hoja.

    python -m curacion.comprobar_borradores [prefijo]

Pasa `normativa.validacion.validar_fichero` (las validaciones por fichero,
esquema incluido) sobre cada `normativa/es/estatal/<prefijo>*.yaml` y muestra
la huella de contenido de cada regla — la misma que la hoja imprimirá y el
volcado exigirá. Sale con código 1 si algo falla; un borrador que no valida
no se imprime, porque validaría en papel algo que el corpus va a rechazar.

No sustituye a `scripts/validar_corpus.py`: ese valida el corpus VISIBLE
(sin `_`); este mira precisamente lo que aún es invisible.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import yaml  # noqa: E402

from normativa import loader, validacion  # noqa: E402

from curacion.paquete import (  # noqa: E402
    CARPETA_CORPUS, PREFIJO_POR_DEFECTO, cargar_paquete, huella_del_paquete,
)


def main(argv: list) -> int:
    prefijo = argv[1] if len(argv) > 1 else PREFIJO_POR_DEFECTO
    rutas = sorted(CARPETA_CORPUS.glob(prefijo + "*.yaml"))
    if not rutas:
        print("No hay ningún fichero «%s*.yaml» en %s" % (prefijo, CARPETA_CORPUS))
        return 1

    fallos_totales = 0
    for ruta in rutas:
        doc = loader.normalizar_fechas(yaml.safe_load(ruta.read_text(encoding="utf-8")))
        fallos = validacion.validar_fichero(doc)
        print("%s -> %s" % (ruta.name, "OK" if not fallos else "FALLA"))
        for fallo in fallos:
            print("   %s" % fallo)
        fallos_totales += len(fallos)

    if fallos_totales:
        print("\n%d fallo(s). No imprimas la hoja hasta dejarlos a cero." % fallos_totales)
        return 1

    filas = cargar_paquete(prefijo)
    print("\n%d regla(s) en el paquete. Huellas (las de la hoja):" % len(filas))
    for fila in filas:
        print("  %s  %s  %s" % (fila.numero, fila.huella_corta, fila.concept_id))
    print("Huella del paquete: %s" % huella_del_paquete(filas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
