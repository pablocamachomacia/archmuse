# -*- coding: utf-8 -*-
"""Infraestructura de los golden tests de E0.

Diseño de referencia: `docs/prd/2026-08-11-e0-modelo-arquitectonico.md`.

**Qué es un golden aquí.** Un fichero de test que construye un dato derivado
del pipeline actual sobre `ejemplo.dxf`, lo compara byte a byte contra un
fixture congelado en `tests/fixtures/golden/`, y falla si difiere. No juzga si
el resultado es bueno: sólo si ha cambiado. Es la red de seguridad de E1, que
va a mover el sustrato de datos por debajo de `circulation.py` sin que ningún
número deba moverse con él.

**Por qué no basta con los tests que ya hay.** Los 44 ficheros de `tests/`
comprueban propiedades (que un umbral se respete, que un motivo se emita), y
son buenos en eso. Ninguno congela la salida completa: un cambio de sustrato
puede seguir cumpliendo todas las propiedades y devolver otros números. Eso es
exactamente el riesgo que `docs/brain/KNOWLEDGE_GRAPH.md` §9.2 describe como
«sigue devolviendo números, y son otros».

Uso:

    python tests/golden.py                  # ejecuta los 8
    python tests/golden.py --capturar-todo  # (re)captura los 8 fixtures
    python tests/golden.py --recapturar G3  # recaptura uno; el diff se revisa a mano
    python tests/test_golden_plano.py       # uno suelto, como el resto de tests/

**Determinismo, y por qué cada regla está aquí y no en cada golden**
(PRD §6, caso límite por caso límite):

1. `ANTHROPIC_API_KEY` se borra del entorno **antes** de importar nada de
   `analyzer/`: `ai_analyst.analyze_with_ai` devuelve `None` sin red y sin
   coste. Un golden que dependa de una llamada a la IA no es un golden.
2. `ARCHMUSE_DATA_DIR` apunta a un temporal: `/api/analizar` guarda proyecto
   al terminar, y no puede tocar la base de desarrollo (mismo patrón que
   `tests/test_storage.py`).
3. Todo float se redondea a 3 decimales — el milímetro, y el mismo redondeo
   que ya aplica `api_serializer._polygon_points`.
4. Los ficheros se escriben con `newline="\\n"`: en Windows, el CRLF haría
   fallar la comparación byte a byte contra un fixture generado en otra
   máquina.
5. Ninguna lista se serializa sin ordenar por una clave explícita, y ningún
   conjunto se serializa nunca.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

# --- Entorno determinista, ANTES de importar analyzer/ o app --------------

os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.setdefault("ARCHMUSE_DATA_DIR", tempfile.mkdtemp(prefix="archmuse_golden_"))

DIR_GOLDEN = os.path.join(RAIZ, "tests", "fixtures", "golden")
DXF = os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf")

# En orden de dependencia (del lector hacia arriba). G9 lo añadió E1 y va
# ANTES que G8 a propósito: G8 sella el manifiesto de todos los demás, así que
# tiene que capturarse el último.
NOMBRES = (
    "G1_plano",
    "G2_unidades",
    "G3_adyacencia",
    "G4_circulacion",
    "G5_hechos_cap",
    "G6_api_analizar",
    "G7_grafo_experimento",
    "G9_modelo",
    "G8_determinismo",
)

MODULOS = {
    "G1_plano": "test_golden_plano",
    "G2_unidades": "test_golden_unidades",
    "G3_adyacencia": "test_golden_adyacencia",
    "G4_circulacion": "test_golden_circulacion",
    "G5_hechos_cap": "test_golden_hechos_cap",
    "G6_api_analizar": "test_golden_api_analizar",
    "G7_grafo_experimento": "test_golden_grafo_experimento",
    "G9_modelo": "test_golden_modelo",
    "G8_determinismo": "test_golden_determinismo",
}

DECIMALES = 3


def consola_utf8() -> None:
    """Mismo apaño que `experimentos/comparar_regla.py`: la consola de Windows
    llega en cp1252 y estos ficheros imprimen rótulos del plano con acentos."""
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            try:
                flujo.reconfigure(encoding="utf-8")
            except Exception:  # pragma: no cover - consola no reconfigurable
                pass


consola_utf8()


def hay_dxf() -> bool:
    return os.path.exists(DXF)


# --- Plano leído una sola vez por proceso ---------------------------------

_PLANO = None


def plano():
    """`leer_plano(ejemplo.dxf)`, cacheado. El DXF pesa 20 MB y todos los
    goldens parten de él; leerlo ocho veces multiplicaría por ocho el tiempo
    de la suite sin cambiar un solo resultado."""
    global _PLANO
    if _PLANO is None:
        from analyzer import parser
        _PLANO = parser.leer_plano(parser.load_document(DXF))
    return _PLANO


def limpiar_cache() -> None:
    """Olvida el plano leído. Lo necesita `tests/canario.py`: una mutación de
    escala (K3) tiene que volver a leer el plano para tener efecto."""
    global _PLANO
    _PLANO = None


# --- Forma canónica -------------------------------------------------------


def redondear(dato):
    """Redondeo recursivo a 3 decimales. Normaliza `-0.0` a `0.0`: son
    numéricamente iguales pero se serializan distinto, y eso bastaría para
    que un golden fallara al cambiar de máquina."""
    if isinstance(dato, float):
        valor = round(dato, DECIMALES)
        return 0.0 if valor == 0.0 else valor
    if isinstance(dato, dict):
        return {clave: redondear(valor) for clave, valor in dato.items()}
    if isinstance(dato, (list, tuple)):
        return [redondear(valor) for valor in dato]
    if isinstance(dato, (set, frozenset)):
        raise TypeError(
            "no se serializa un conjunto en un golden: su orden no es estable. "
            "Conviértelo en lista ordenada por una clave explícita."
        )
    return dato


def canonico(dato) -> str:
    """La única forma de texto admitida. `sort_keys` hace irrelevante el orden
    de inserción de los diccionarios; el resto lo ordena quien construye."""
    return json.dumps(
        redondear(dato), sort_keys=True, ensure_ascii=False, indent=2,
        separators=(",", ": "),
    ) + "\n"


def ruta_fixture(nombre: str) -> str:
    return os.path.join(DIR_GOLDEN, "%s.json" % nombre)


def escribir(nombre: str, dato) -> str:
    os.makedirs(DIR_GOLDEN, exist_ok=True)
    texto = canonico(dato)
    with open(ruta_fixture(nombre), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(texto)
    return texto


def leer(nombre: str) -> str:
    with open(ruta_fixture(nombre), "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def cargar(nombre: str):
    return json.loads(leer(nombre))


# --- Comparación ----------------------------------------------------------


def diferencias(esperado, obtenido, ruta="") -> list:
    """Lista de diferencias con su ruta dentro del JSON. Un `assert a == b`
    sobre un fixture de 3.000 líneas no dice dónde falla, y entonces nadie lo
    lee: dice «no son iguales» y se recaptura sin mirar."""
    salida = []
    if type(esperado) is not type(obtenido) and not (
        isinstance(esperado, (int, float)) and isinstance(obtenido, (int, float))
    ):
        return ["%s: tipo %s -> %s" % (ruta or ".", type(esperado).__name__,
                                       type(obtenido).__name__)]
    if isinstance(esperado, dict):
        for clave in sorted(set(esperado) | set(obtenido)):
            sub = "%s.%s" % (ruta, clave)
            if clave not in esperado:
                salida.append("%s: SOBRA (%r)" % (sub, obtenido[clave]))
            elif clave not in obtenido:
                salida.append("%s: FALTA (esperado %r)" % (sub, esperado[clave]))
            else:
                salida.extend(diferencias(esperado[clave], obtenido[clave], sub))
    elif isinstance(esperado, list):
        if len(esperado) != len(obtenido):
            salida.append("%s: longitud %d -> %d" % (ruta or ".", len(esperado), len(obtenido)))
        for indice in range(min(len(esperado), len(obtenido))):
            salida.extend(diferencias(esperado[indice], obtenido[indice],
                                      "%s[%d]" % (ruta, indice)))
    elif esperado != obtenido:
        salida.append("%s: %r -> %r" % (ruta or ".", esperado, obtenido))
    return salida


def comprobar(nombre: str, dato):
    """(ok, diferencias). En proceso, sin imprimir: lo usa `tests/canario.py`
    para medir qué goldens se rompen con cada mutación."""
    if not os.path.exists(ruta_fixture(nombre)):
        return False, ["no existe el fixture %s.json" % nombre]
    obtenido = json.loads(canonico(dato))
    esperado = cargar(nombre)
    if canonico(esperado) == canonico(obtenido):
        return True, []
    return False, diferencias(esperado, obtenido)


MAX_DIFERENCIAS = 12


def ejecutar(nombre: str, construir, descripcion: str = "") -> int:
    """Punto de entrada de cada `tests/test_golden_*.py`.

    Sale 0 si el golden coincide, 1 si difiere. Si no está `ejemplo.dxf`, sale
    0 con aviso — mismo criterio que `tests/test_analizar_planta.py`: la
    ausencia del plano no es un fallo del código.
    """
    print("=" * 74)
    print("%s  %s" % (nombre, descripcion))
    print("=" * 74)

    if not hay_dxf():
        print("[SALTA] no se encuentra %s" % DXF)
        return 0

    dato = construir()

    if "--capturar" in sys.argv or "--recapturar" in sys.argv:
        texto = escribir(nombre, dato)
        print("  [CAPTURADO] %s (%d bytes, %d lineas)"
              % (ruta_fixture(nombre), len(texto.encode("utf-8")), texto.count("\n")))
        return 0

    ok, difs = comprobar(nombre, dato)
    if ok:
        print("  [OK] identico al fixture congelado")
        return 0

    print("  [FALLO] %d diferencia(s) contra el fixture:" % len(difs))
    for linea in difs[:MAX_DIFERENCIAS]:
        print("    %s" % linea)
    if len(difs) > MAX_DIFERENCIAS:
        print("    ... y %d mas" % (len(difs) - MAX_DIFERENCIAS))
    print()
    print("  Si el cambio es DELIBERADO, documentalo y recaptura:")
    print("    python tests/golden.py --recapturar %s" % nombre)
    print("  Si no lo es, es una regresion. No recaptures.")
    return 1


# --- Runner de los ocho ---------------------------------------------------


def _importar(nombre: str):
    """Importa un golden por su nombre de módulo suelto.

    `tests/` no es un paquete (no hay `__init__.py`) y no se le añade uno:
    todos los ficheros de `tests/` se ejecutan hoy como scripts sueltos y
    convertirlo en paquete cambiaría cómo se importan los 44 que ya existen.
    """
    import importlib
    directorio = os.path.join(RAIZ, "tests")
    if directorio not in sys.path:
        sys.path.insert(0, directorio)
    return importlib.import_module(MODULOS[nombre])


def main() -> int:
    argumentos = sys.argv[1:]

    if "--capturar-todo" in argumentos:
        objetivo = list(NOMBRES)
        modo = "--capturar"
    elif "--recapturar" in argumentos:
        indice = argumentos.index("--recapturar")
        pedido = argumentos[indice + 1] if len(argumentos) > indice + 1 else ""
        objetivo = [n for n in NOMBRES if n == pedido or n.startswith(pedido + "_")
                    or n.split("_")[0] == pedido]
        if not objetivo:
            print("No conozco el golden %r. Los que hay: %s" % (pedido, ", ".join(NOMBRES)))
            return 2
        modo = "--capturar"
    else:
        objetivo = list(NOMBRES)
        modo = None

    if not hay_dxf():
        print("[SALTA] no se encuentra %s" % DXF)
        print("Todas las comprobaciones OK (0)")
        return 0

    guardado = list(sys.argv)
    if modo:
        sys.argv = [sys.argv[0], modo]
    else:
        sys.argv = [sys.argv[0]]

    fallos = []
    try:
        for nombre in objetivo:
            modulo = _importar(nombre)
            if modulo.ejecutar_golden() != 0:
                fallos.append(nombre)
            print()
    finally:
        sys.argv = guardado

    print("=" * 74)
    if modo:
        print("Capturados %d fixture(s): %s" % (len(objetivo), ", ".join(objetivo)))
        print("Revisa el diff a mano antes de darlo por bueno.")
        return 0
    if fallos:
        print("GOLDENS EN FALLO (%d de %d): %s" % (len(fallos), len(objetivo), ", ".join(fallos)))
        return 1
    print("Todos los goldens OK (%d de %d)" % (len(objetivo), len(objetivo)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
