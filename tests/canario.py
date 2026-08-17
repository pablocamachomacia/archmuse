# -*- coding: utf-8 -*-
"""Prueba del canario — criterio A4 de `docs/prd/2026-08-11-e0-modelo-arquitectonico.md`.

Ejecutar:  python tests/canario.py

**Un golden que nunca falla no protege nada.** Los ocho goldens de E0 pasan
hoy; eso, por sí solo, no demuestra que vayan a detectar una regresión mañana.
Este script lo demuestra: aplica cuatro mutaciones en memoria a constantes y
funciones reales de producción, y comprueba que cada una rompe exactamente los
goldens que debe romper.

**Todo ocurre en memoria.** `unittest.mock.patch` sobre atributos de módulo; ni
un fichero de producción tocado, ni un fixture reescrito. Al salir del `with`,
el proceso vuelve a su estado anterior.

Las cuatro mutaciones y qué camino del pipeline recorren:

- **K1** tolerancia de muro 0,5 -> 0,25 m. El grafo de contigüidad.
- **K2** agrupación forzada por proximidad a 3,0 m en vez de por etiqueta VT.
  La cascada agrupación -> superficie -> hechos -> API.
- **K3** escala x10 (el plano leído como si estuviera en otra unidad). La
  cascada geometría -> todo.
- **K4** «Terraza» reclasificada como zona de ocupación nula. La cascada
  clasificación de recintos -> superficie ocupable -> ocupación.

**Sobre K2 y una trampa que este script destapó.** La forma obvia de mutar la
agrupación —parchear `evaluator.MAX_GAP_BETWEEN_ROOMS_M`— **no tiene ningún
efecto**: la constante se enlaza como valor por defecto del parámetro
`max_gap_m` en el momento de definir `group_rooms_by_proximity`, así que
cambiar el nombre del módulo después no cambia nada. Se comprueba
explícitamente abajo (`_nota_constante_inerte`) porque es exactamente el tipo
de cosa que hace que una mutación parezca cubierta cuando no lo está.
"""
from __future__ import annotations

import sys
from contextlib import ExitStack
from unittest import mock

import golden

from analyzer import escala as escala_mod
from analyzer import evaluator, superficie_util

fallos = []
comprobaciones = 0


def check(condicion, titulo, detalle=""):
    global comprobaciones
    comprobaciones += 1
    print("  [%s] %s" % ("OK  " if condicion else "FALLO", titulo))
    if detalle:
        print("         %s" % detalle)
    if not condicion:
        fallos.append(titulo)


# --- Las cuatro mutaciones -------------------------------------------------


TOLERANCIA_MUTADA_M = 0.25


def _k1():
    """Tolerancia de muro 0,5 -> 0,25 m.

    **El PRD pedía 0,5 -> 0,6 y esa mutación es inerte**, medido: las 45
    aristas de `ejemplo.dxf` tienen separaciones de 0,000 a 0,380 m y el
    primer par no contiguo está a 2,27 m. Cualquier valor entre 0,39 y 2,26
    produce exactamente el mismo grafo — que es justamente lo que la cabecera
    de `adyacencia.py` afirma cuando dice que «el margen es enorme». Subir el
    umbral no prueba nada; bajarlo sí: con 0,25 m desaparecen 4 de las 45
    aristas (las de 0,261, 0,262, 0,350 y 0,380 m).

    `adyacencia.rooms_are_connected` lee la constante del módulo en cada
    llamada, así que el parche llega."""
    return [mock.patch("analyzer.adyacencia.WALL_GAP_TOLERANCE_M", TOLERANCIA_MUTADA_M)]


def _agrupar_por_proximidad(rooms, unit_labels):
    """Sustituta de `group_rooms_by_unit_label`: ignora las etiquetas VT y
    agrupa por cercanía con 3,0 m — la mutación que el PRD pide para K2, hecha
    de la única forma que surte efecto (ver docstring del módulo)."""
    return evaluator.group_rooms_by_proximity(rooms, max_gap_m=3.0)


def _k2():
    return [mock.patch("analyzer.evaluator.group_rooms_by_unit_label",
                       _agrupar_por_proximidad)]


def _k3():
    """Escala x10: el plano se lee como si estuviera dibujado en otra unidad.

    Se parchea la detección, no el resultado: `leer_plano` sigue decidiendo
    igual, sólo que la detección le devuelve otro factor. `escala_confirmada`
    existe justo para esto — es el desenlace «lo dijo el arquitecto»."""
    return [mock.patch("analyzer.parser.escala_mod.detectar_escala",
                       lambda insunits, areas: escala_mod.escala_confirmada(10.0))]


ETIQUETA_MUTADA = "TERRAZA"


def _clasificar_con_terraza_nula(etiqueta):
    """«Terraza» pasa a zona de ocupación nula.

    **El PRD proponía «Pasillo» y esa mutación es inerte**, medido: en
    `ejemplo.dxf` no hay ni un solo recinto rotulado «Pasillo» (los 34 son
    Terraza 8, Dormitorio 1 6, Salón/cocina 5, Tendedero 5, Baño 4,
    Dormitorio 2 4, Aseo 1, Dormitorio 3 1). Reclasificar un rótulo que no
    existe no cambia nada y habría dado por cubierta una cascada que no lo
    estaba.

    «Terraza» sí existe —ocho recintos— y es además el error plausible de
    verdad: `superficie_util.py` documenta que el DB-SI **no** excluye la
    terraza de la superficie útil, así que excluirla es exactamente la clase
    de cambio razonable-pero-equivocado que un golden tiene que atrapar. Es
    una exclusión de más en el cómputo de superficie ocupable: altera el
    número de ocupantes sin tocar ni un polígono."""
    if etiqueta and ETIQUETA_MUTADA in superficie_util._normalizar(etiqueta):
        return superficie_util.OCUPACION_NULA
    return _CLASIFICAR_ORIGINAL(etiqueta)


_CLASIFICAR_ORIGINAL = superficie_util.clasificar_recinto


def _k4():
    return [mock.patch("analyzer.superficie_util.clasificar_recinto",
                       _clasificar_con_terraza_nula)]


# Matriz esperada. **Medida, no supuesta**: la predicción del PRD se escribió
# sin ejecutar nada y se corrigió con lo que este script mide (ver el informe
# de E0). Cada desviación respecto de aquella predicción está anotada.
MUTACIONES = (
    ("K1", "tolerancia de muro 0,5 -> 0,25 m", _k1,
     ("G3_adyacencia", "G4_circulacion", "G6_api_analizar", "G9_modelo"),
     "Coincide con la prediccion del PRD en QUE cae, pero solo tras corregir el "
     "valor: 0,5->0,6 era inerte (ver _k1). "
     "E1: G9 tambien cae, y eso confirma que el modelo LEE el umbral de "
     "`adyacencia.WALL_GAP_TOLERANCE_M` en vez de tener su propia copia. "
     "Adyacencia acustica (docs/prd/2026-08-11-adyacencia-acustica-tramo-enfrentado.md): "
     "hasta ese cambio, G6 NO caia con K1 -- el unico consumidor de `adyacencia` "
     "dentro del evaluador era `evaluate_evacuation_distance`, ciego en este plano "
     "(ninguna vivienda tiene pieza de circulacion rotulada). Desde que "
     "`evaluate_acoustic_adjacency` tambien lee `WALL_GAP_TOLERANCE_M` (via "
     "`tramo_enfrentado_m`), G6 SI cae con K1: medido, de los 9 pares que "
     "disparan con la tolerancia real (0,5m), 3 dejan de disparar con 0,25m "
     "(los de gap 0,262/0,137/0,261m, por encima de la tolerancia mutada) y el "
     "recuento de incidencias CTE-DB-HR baja de 9 a 6. Ya no es cierto que G6 "
     "sea ciego a la topologia de este plano."),
    ("K2", "agrupacion por proximidad 3,0 m en vez de etiqueta VT", _k2,
     ("G2_unidades", "G3_adyacencia", "G4_circulacion", "G5_hechos_cap",
      "G6_api_analizar", "G9_modelo"),
     "El PRD predecia G2+G4+G5+G6. G3 tambien cae: las aristas se listan por "
     "vivienda, y si cambia el reparto de recintos cambia el listado aunque el "
     "criterio de contiguidad sea el mismo. "
     "E1: G9 tambien cae, por el mismo motivo: el modelo agrupa con la misma "
     "funcion."),
    ("K3", "escala x10", _k3,
     ("G1_plano", "G2_unidades", "G3_adyacencia", "G4_circulacion",
      "G5_hechos_cap", "G6_api_analizar", "G7_grafo_experimento", "G9_modelo"),
     "El PRD predecia G1+G2+G5+G6 y que G7 pasara. Caen los siete: la escala "
     "multiplica las separaciones entre poligonos, que cruzan la tolerancia de "
     "muro, y G7 parte del mismo plano leido. Es la mutacion mas transversal y "
     "demuestra que la cascada geometrica esta cubierta de extremo a extremo. "
     "E1: y G9, que parte del mismo plano leido."),
    ("K4", "'Terraza' reclasificada como zona de ocupacion nula", _k4,
     ("G5_hechos_cap", "G6_api_analizar"),
     "El PRD proponia 'Pasillo', rotulo que NO existe en ejemplo.dxf: mutacion "
     "inerte (ver _clasificar_con_terraza_nula). Con 'Terraza' caen los dos "
     "goldens previstos y ninguno mas: la cascada clasificacion -> superficie "
     "ocupable -> ocupacion queda demostrada, y no toca geometria ni topologia. "
     "E1: G9 NO cae, y es correcto: el modelo no calcula superficie util; eso es "
     "una regla del dominio, no un dato del proyecto (KNOWLEDGE_GRAPH.md §7)."),
)

# G8 no vigila comportamiento sino la integridad de los otros fixtures en
# disco, y las mutaciones son en memoria: es insensible **por diseño**. Se
# declara aquí para que su insensibilidad sea una decisión y no un descuido.
INSENSIBLES_POR_DISENO = ("G8_determinismo",)


# --- Motor -----------------------------------------------------------------


def _cargar_modulos():
    import importlib
    import os
    directorio = os.path.join(golden.RAIZ, "tests")
    if directorio not in sys.path:
        sys.path.insert(0, directorio)
    return {n: importlib.import_module(golden.MODULOS[n]) for n in golden.NOMBRES}


def _evaluar_todos(modulos):
    """Qué goldens fallan ahora mismo. Devuelve el conjunto de nombres."""
    golden.limpiar_cache()
    rotos = set()
    for nombre in golden.NOMBRES:
        try:
            ok, _difs = golden.comprobar(nombre, modulos[nombre].construir())
        except Exception as exc:  # noqa: BLE001 - una mutación puede romper el camino
            ok = False
            print("         (%s lanzo %s: %s)" % (nombre, type(exc).__name__, str(exc)[:90]))
        if not ok:
            rotos.add(nombre)
    golden.limpiar_cache()
    return rotos


def _nota_constante_inerte(modulos):
    """Demuestra que parchear `MAX_GAP_BETWEEN_ROOMS_M` no hace nada.

    No es una mutación de la matriz: es la comprobación de que la mutación
    ingenua habría dado un falso «cubierto»."""
    with mock.patch("analyzer.evaluator.MAX_GAP_BETWEEN_ROOMS_M", 3.0):
        rotos = _evaluar_todos(modulos)
    check(not rotos,
          "K2-nota: parchear MAX_GAP_BETWEEN_ROOMS_M no rompe ningun golden "
          "(la constante se enlaza como valor por defecto y el parche es inerte)",
          "rotos: %s" % (sorted(rotos) or "ninguno"))


def main() -> int:
    print("=" * 74)
    print("PRUEBA DEL CANARIO — criterio A4")
    print("=" * 74)

    if not golden.hay_dxf():
        print("[SALTA] no se encuentra %s" % golden.DXF)
        print("Todas las comprobaciones OK (0)")
        return 0

    modulos = _cargar_modulos()

    print("\n0. Linea base: sin mutar, los ocho goldens pasan")
    base = _evaluar_todos(modulos)
    check(not base, "sin mutacion, 0 goldens rotos",
          "rotos: %s" % (sorted(base) or "ninguno"))
    if base:
        print("\n  La linea base ya falla. Captura los fixtures antes de correr el canario:")
        print("    python tests/golden.py --capturar-todo")
        return 1

    for clave, descripcion, construir_parches, esperados, nota in MUTACIONES:
        print("\n%s. %s" % (clave, descripcion))
        with ExitStack() as pila:
            for parche in construir_parches():
                pila.enter_context(parche)
            rotos = _evaluar_todos(modulos)

        esperado = set(esperados)
        de_menos = sorted(esperado - rotos)   # goldens que NO son sensibles: el fallo grave
        de_mas = sorted(rotos - esperado)     # goldens que caen sin estar previstos

        check(not de_menos,
              "%s: todos los goldens previstos son sensibles" % clave,
              "insensibles (no deberian): %s" % (de_menos or "ninguno"))
        check(not de_mas,
              "%s: ningun golden adicional cae" % clave,
              "adicionales: %s" % (de_mas or "ninguno"))
        print("         rotos: %s" % ", ".join(sorted(rotos)))
        print("         nota : %s" % nota)

    print("\nNota metodologica")
    _nota_constante_inerte(modulos)

    for nombre in INSENSIBLES_POR_DISENO:
        check(True, "%s declarado insensible por diseno (vigila los fixtures, "
                    "no el pipeline)" % nombre)

    print()
    print("=" * 74)
    if fallos:
        print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
        for f in fallos:
            print("  - %s" % f)
        return 1
    print("Todas las comprobaciones OK (%d)" % comprobaciones)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
