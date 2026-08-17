"""`cte_zonas.py` sigue respondiendo exactamente igual tras la migración.

Las tablas se han movido a `normativa/geografia/es/derivados/`, indexadas por
código INE, para que exista UNA sola lista de municipios en el sistema en vez
de tres (`ZONAS_CTE`, `CIUDADES_DENSIDAD` y la `CIUDAD_A_CCAA` que vivía en
`static/app.js`). Lo que NO puede haber cambiado es el comportamiento
observable: `app.py` llama a estas dos funciones y su respuesta tiene que ser
idéntica a la de antes, ciudad por ciudad.

`tests/fixtures/cte_zonas_baseline.json` se generó ejecutando la versión
anterior del módulo (la de git HEAD antes de la migración) sobre las 30
ciudades de la tabla original más 10 casos límite. Es una línea base
congelada: si alguien cambia los datos migrados, este test lo dice.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from analyzer.cte_zonas import (  # noqa: E402
    DEFAULT_DENSIDAD_URBANA,
    DEFAULT_ZONA_CTE,
    get_densidad_urbana,
    get_zona_cte,
)

BASELINE = RAIZ / "tests" / "fixtures" / "cte_zonas_baseline.json"


def test_comportamiento_identico_al_anterior():
    """Ninguna de las 40 entradas cambia de respuesta."""
    esperado = json.loads(BASELINE.read_text(encoding="utf-8"))
    dif = []
    for ciudad, (zona, densidad) in esperado.items():
        real = (get_zona_cte(ciudad), get_densidad_urbana(ciudad))
        if real != (zona, densidad):
            dif.append(f"{ciudad!r}: antes {(zona, densidad)}, ahora {real}")
    assert not dif, "La fachada ha cambiado de comportamiento:\n  " + "\n  ".join(dif)


def test_el_repliegue_por_defecto_se_conserva():
    """El repliegue silencioso a "C"/"media" se mantiene A PROPÓSITO aquí,
    aunque contradiga el principio de "nunca silencio" del subsistema
    normativo: quitarlo ahora sería una regresión de comportamiento. Quien ya
    hace lo correcto es `normativa.api.contexto_territorial`, que devuelve
    None y declara la asunción."""
    assert get_zona_cte("Ciudad Que No Existe") == DEFAULT_ZONA_CTE
    assert get_densidad_urbana("") == DEFAULT_DENSIDAD_URBANA


def test_una_sola_lista_de_municipios():
    """La razón de ser de la migración: que no vuelva a haber dos tablas de
    ciudades divergiendo en paralelo."""
    import analyzer.cte_zonas as m

    assert not hasattr(m, "ZONAS_CTE"), "la tabla ha vuelto a cte_zonas.py"
    assert not hasattr(m, "CIUDADES_DENSIDAD"), "la tabla ha vuelto a cte_zonas.py"


def test_el_frontend_no_tiene_tablas_normativas():
    """La condición previa del encargo: el cliente es capa de presentación.

    Ningún juicio normativo se calcula en el navegador ni se lee de una tabla
    incrustada en JavaScript.
    Se busca CÓDIGO, no menciones: los comentarios que explican qué tabla
    vivía aquí y por qué se fue son documentación útil y deben poder quedarse.
    Lo prohibido es una declaración o una llamada.
    """
    import re

    js = (RAIZ / "static" / "app.js").read_text(encoding="utf-8")
    # Fuera comentarios de línea y de bloque antes de mirar.
    codigo = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    codigo = re.sub(r"^\s*//.*$", "", codigo, flags=re.M)

    prohibidos = {
        r"\bvar\s+SUPERFICIE_MIN_CCAA\b": "tabla de superficie mínima por CCAA sin fuente verificada",
        r"\bvar\s+CIUDAD_A_CCAA\b": "segunda lista de ciudades en el cliente",
        r"\bvar\s+NORMATIVA_REF\b": "tabla de referencias normativas en el cliente",
        r"\bgetSuperficieMinima\s*\(": "cálculo normativo en el navegador",
        r"\bgetCCAA\s*\(": "resolución territorial en el navegador",
    }
    encontrados = [motivo for patron, motivo in prohibidos.items() if re.search(patron, codigo)]
    assert not encontrados, "static/app.js vuelve a decidir normativa: " + "; ".join(encontrados)


if __name__ == "__main__":
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith("test_"):
            try:
                fn()
                print(f"OK   {nombre}")
            except AssertionError as exc:
                fallos += 1
                print(f"FALLO {nombre}: {str(exc)[:300]}")
    print(f"\n{'TODO OK' if not fallos else str(fallos) + ' FALLOS'}")
    sys.exit(1 if fallos else 0)
