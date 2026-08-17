# -*- coding: utf-8 -*-
"""CAP-5: los tres avisos condicionales de `C11`, `C15` y `C18`.

Ejecutar:  python tests/test_avisos_altura_evacuacion.py

Rapido (<1 s): funciones puras sobre un `Hecho`, sin DXF ni Flask.

Que protege:

1. **Son avisos, no reglas.** Ninguno lleva `passed` ni severidad, ninguno
   entra en `classify_problems`, y `evaluator.py` no se toca. `C11`, `C15` y
   `C18` siguen en `UNKNOWN` despues de CAP-5.
2. Un hecho `UNKNOWN` no dispara NINGUNO de los tres — ni siquiera un aviso
   condicional (D3 de `DB-SI_DECISIONS.md`). No hay aviso "por defecto".
3. El umbral es `>=` en los tres (14 / 28 / 9 m), documentado: la norma es
   estricta en los tres casos, asi que se avisa un caso antes, en direccion
   segura, cosa que solo es admisible porque no hay veredicto detras.
4. Los tres son INDEPENDIENTES, no escalonados con exclusion mutua: un
   edificio de mas de 28 m dispara los tres a la vez.
5. **Cada uno de los tres textos dice por su cuenta si la altura es
   estimada** (riesgo #3 del plan, el mas citado para CAP-5): no vale una
   advertencia global de la que no se sepa a cual de los tres aplica.
6. `C18` no depende de `evaluate_retranqueos` (R25) — prohibido por escrito
   en `DB-SI_REVIEW.md`.
"""
import ast
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import analyzer.avisos_altura_evacuacion as mod_avisos  # noqa: E402
from analyzer.altura_evacuacion import resolver_altura_evacuacion  # noqa: E402
from analyzer.avisos_altura_evacuacion import (  # noqa: E402
    UMBRAL_C11_M,
    UMBRAL_C15_M,
    UMBRAL_C18_M,
    avisos_altura_evacuacion,
    aviso_c11,
    aviso_c15,
    aviso_c18,
)
from analyzer.hechos import ESTIMATED, KNOWN, UNKNOWN  # noqa: E402

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


def declarada(metros):
    return resolver_altura_evacuacion("edificio", valor_declarado_m=metros)


def estimada(plantas, libre):
    return resolver_altura_evacuacion("edificio", plantas=plantas, altura_libre_m=libre)


DESCONOCIDA = resolver_altura_evacuacion("edificio")

print("A. Umbrales -- los tres son los de la norma, no otros")

check(UMBRAL_C11_M == 14.0, "C11: 14 m (DB-SI 3 ap. 5, Tabla 5.1)", UMBRAL_C11_M)
check(UMBRAL_C15_M == 28.0, "C15: 28 m (DB-SI 3 ap. 9)", UMBRAL_C15_M)
check(UMBRAL_C18_M == 9.0, "C18: 9 m (DB-SI 5 ap. 1.2)", UMBRAL_C18_M)

print("\nB. Umbral exacto -- `>=`, no `>` (criterio de aceptacion 9)")

for fn, umbral, nombre in [(aviso_c11, UMBRAL_C11_M, "C11"),
                           (aviso_c15, UMBRAL_C15_M, "C15"),
                           (aviso_c18, UMBRAL_C18_M, "C18")]:
    justo = fn(declarada(umbral))
    check(justo is not None,
          "%s: exactamente %.0f m SI dispara el aviso (>=)" % (nombre, umbral))
    justo_debajo = fn(declarada(umbral - 0.01))
    check(justo_debajo is None,
          "%s: %.2f m (un cm por debajo) NO dispara" % (nombre, umbral - 0.01))
    encima = fn(declarada(umbral + 5))
    check(encima is not None, "%s: por encima del umbral dispara" % nombre)

print("\nC. UNKNOWN no dispara nada -- ni siquiera un aviso condicional (D3)")

check(DESCONOCIDA.estado == UNKNOWN, "el hecho de partida es UNKNOWN")
check(aviso_c11(DESCONOCIDA) is None, "C11: UNKNOWN -> ningun aviso")
check(aviso_c15(DESCONOCIDA) is None, "C15: UNKNOWN -> ningun aviso")
check(aviso_c18(DESCONOCIDA) is None, "C18: UNKNOWN -> ningun aviso")
check(avisos_altura_evacuacion(DESCONOCIDA) == [],
      "la lista completa sale vacia: silencio explicito, no aviso conservador")
check(avisos_altura_evacuacion(None) == [],
      "un hecho ausente tampoco dispara nada (defensivo)")

print("\nD. Los tres son independientes, no escalonados")

# CU4: 3 plantas, valores por defecto -> 5,60 m. Ninguno de los tres.
h_bajo = estimada(3, 2.8)
check(h_bajo.valor == 5.6 or abs(h_bajo.valor - 5.6) < 1e-9,
      "CU4: 3 plantas x 2,80 m -> 5,60 m", h_bajo.valor)
check(avisos_altura_evacuacion(h_bajo) == [],
      "CU4: por debajo de los tres umbrales -> cero avisos")

# CU6: entre 9 y 14 m -> solo C18.
h_medio = declarada(11.0)
reglas_medio = [a.regla for a in avisos_altura_evacuacion(h_medio)]
check(reglas_medio == ["C18"],
      "CU6: 11 m dispara SOLO C18 (el umbral mas bajo)", reglas_medio)

# CU5: 6 plantas x 2,80 -> 14,00 m -> C11 y C18, no C15.
h_c11 = estimada(6, 2.8)
reglas_c11 = sorted(a.regla for a in avisos_altura_evacuacion(h_c11))
check(h_c11.valor == 14.0, "CU5: 6 plantas x 2,80 m -> 14,00 m exactos", h_c11.valor)
check(reglas_c11 == ["C11", "C18"],
      "CU5: 14 m dispara C11 y C18, no C15 (28 m)", reglas_c11)

# Mas de 28 m -> los tres a la vez.
h_alto = declarada(31.0)
todos = avisos_altura_evacuacion(h_alto)
reglas_alto = sorted(a.regla for a in todos)
check(reglas_alto == ["C11", "C15", "C18"],
      "31 m dispara los TRES a la vez: son independientes, no exclusion mutua",
      reglas_alto)
check([a.regla for a in todos] == ["C15", "C11", "C18"],
      "orden de la lista: de umbral mas alto a mas bajo",
      [a.regla for a in todos])

print("\nE. Cada aviso dice por su cuenta si la altura es estimada (riesgo #3)")

avisos_estimados = avisos_altura_evacuacion(estimada(12, 2.9))   # 31,90 m
check(len(avisos_estimados) == 3, "3 avisos sobre una altura estimada",
      len(avisos_estimados))
for a in avisos_estimados:
    check(a.altura_estimada is True,
          "%s: marcado altura_estimada=True en el objeto" % a.regla)
    check("ESTIMACION" in a.mensaje.upper(),
          "%s: el MENSAJE (no solo el JSON) dice que es una estimacion" % a.regla,
          a.mensaje[:120])

avisos_declarados = avisos_altura_evacuacion(declarada(31.9))
for a in avisos_declarados:
    check(a.altura_estimada is False,
          "%s: altura declarada -> altura_estimada=False" % a.regla)
    check("ESTIMACION" not in a.mensaje.upper(),
          "%s: el mensaje de una altura declarada NO la llama estimacion" % a.regla)
    check("declarada" in a.mensaje.lower(),
          "%s: dice explicitamente que la declaro el arquitecto" % a.regla)

# El texto debe ser DISTINTO entre KNOWN y ESTIMATED para la misma altura.
for reg in ("C11", "C15", "C18"):
    m_est = next(a.mensaje for a in avisos_estimados if a.regla == reg)
    m_dec = next(a.mensaje for a in avisos_declarados if a.regla == reg)
    check(m_est != m_dec,
          "%s: el texto de KNOWN y el de ESTIMATED no son el mismo" % reg)

print("\nF. Son avisos, NO reglas -- ningun veredicto por ninguna via")

for a in avisos_altura_evacuacion(declarada(31.0)):
    check(not hasattr(a, "passed"),
          "%s: el aviso no tiene `passed`" % a.regla)
    check(not hasattr(a, "severity") and not hasattr(a, "severidad"),
          "%s: el aviso no tiene severidad" % a.regla)
    check(not hasattr(a, "veredicto"), "%s: el aviso no tiene veredicto" % a.regla)
    check(bool(a.localizador) and a.localizador.startswith("DB-SI"),
          "%s: lleva su localizador normativo real" % a.regla, a.localizador)
    check(bool(a.codigo) and a.codigo.startswith("DB-SI-"),
          "%s: codigo propio de aviso, distinto de cualquier IssueReport" % a.regla,
          a.codigo)

# El modulo no debe acoplarse a `evaluator.py` por ninguna via: ni reglas, ni
# `IssueReport`, ni R25 (`evaluate_retranqueos`), prohibido por escrito en la
# ficha C18 de `DB-SI_REVIEW.md`.
#
# Se inspecciona el AST, no el texto: las docstrings del modulo NOMBRAN esas
# tres cosas justamente para explicar por que no se usan, y un grep sobre el
# fichero no sabria distinguir "lo explica" de "lo usa".
arbol = ast.parse(open(mod_avisos.__file__, encoding="utf-8").read())

modulos_importados = set()
for nodo in ast.walk(arbol):
    if isinstance(nodo, ast.Import):
        modulos_importados.update(a.name for a in nodo.names)
    elif isinstance(nodo, ast.ImportFrom):
        modulos_importados.add(nodo.module or "")
check(not any("evaluator" in m for m in modulos_importados),
      "no importa `evaluator` por ninguna via", sorted(modulos_importados))
check(modulos_importados <= {"__future__", "dataclasses", "typing", "hechos"},
      "solo depende de la stdlib y de `hechos.py` (mismo aislamiento que "
      "planta.py/sectorizacion.py)", sorted(modulos_importados))

nombres_usados = {
    n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)
} | {
    n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)
}
for prohibido in ("IssueReport", "classify_problems", "evaluate_retranqueos",
                  "passed"):
    check(prohibido not in nombres_usados,
          "no usa %r en ningun sitio del codigo (solo lo nombra la docstring "
          "para explicar por que no se usa)" % prohibido)

print("\nG. Trazabilidad del aviso hasta el numero que lo disparo")

a_c11 = aviso_c11(declarada(17.5))
check(a_c11.altura_m == 17.5, "el aviso guarda la altura que lo disparo", a_c11.altura_m)
check(a_c11.umbral_m == 14.0, "y el umbral contra el que se comparo", a_c11.umbral_m)
check("17.50" in a_c11.mensaje or "17,50" in a_c11.mensaje,
      "el mensaje cita la altura concreta, no una frase generica", a_c11.mensaje[:100])

print("\n" + "=" * 60)
if fallos:
    print("FALLOS (%d de %d):" % (len(fallos), comprobaciones))
    for f in fallos:
        print("  - %s" % f)
    sys.exit(1)
print("Todas las comprobaciones OK (%d)" % comprobaciones)
