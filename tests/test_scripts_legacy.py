# -*- coding: utf-8 -*-
"""Ejecuta bajo pytest los ficheros de `tests/` que se escribieron como scripts.

**Qué son esos ficheros.** La mayoría de `tests/`: hacen sus comprobaciones a
nivel de módulo con un helper `check(cond, titulo)` que acumula en una lista
`fallos`, imprimen `[OK  ]`/`[FALLO]` por comprobación, y terminan con
`sys.exit(1)` si algo falló. Su forma de ejecutarse está escrita en su propio
docstring: `python tests/test_x.py`.

**Por qué se ejecutan en un subproceso y no se importan.** Dos razones, y las
dos son de fidelidad, no de comodidad:

1. Es el modo en que están escritos para funcionar. Importarlos dentro del
   proceso de pytest ejecuta su `sys.exit()` contra el propio pytest.
2. Varios fijan variables de entorno (`ARCHMUSE_DATA_DIR`, borrado de
   `ANTHROPIC_API_KEY`), importan `app` y tocan la base de datos. En un mismo
   intérprete se contaminarían entre ellos y el resultado dependería del orden
   de ejecución — lo contrario de una medición fiable.

**Qué se traduce y cómo:**

| Lo que hace el script                        | Resultado en pytest |
|----------------------------------------------|---------------------|
| termina con código 0                          | PASSED              |
| termina con código ≠ 0                        | FAILED, con su salida |
| dice que le falta un fichero y no comprueba nada | SKIPPED, con el motivo |
| no termina dentro del tiempo límite           | FAILED (por tiempo)  |

**Limitación conocida, y es real:** un script equivale aquí a **un** test de
pytest, no a sus N comprobaciones internas. Un fichero que declara "FALLOS (3
de 35)" aparece como un único FAILED; los tres fallos concretos están en la
salida capturada, no en el recuento de pytest. Convertir cada `check()` en un
test independiente exigiría reescribir los setenta y tantos ficheros, que es
precisamente lo que esta fase no debe hacer.

Tiempo límite por script: 900 s, ajustable con `ARCHMUSE_TEST_TIMEOUT`.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

TIMEOUT_S = int(os.environ.get("ARCHMUSE_TEST_TIMEOUT", "900"))

# Lo que estos scripts imprimen cuando renuncian a comprobar por falta de un
# fichero externo (`ejemplo.dxf`, `v2s.dxf`), antes de salir con código 0.
MARCAS_DE_SALTO = ("[SALTA]", "[SALTADO]", "no disponible en este entorno")

# Lo que imprime el helper `check()` de estos scripts por cada comprobación
# realizada. Si no aparece ni una vez, no se comprobó nada.
MARCA_DE_COMPROBACION = "[OK"


def _entorno_hijo() -> dict:
    """Entorno del subproceso: el mismo de pytest, con la salida forzada a
    UTF-8. Estos scripts imprimen '≥', 'ñ' y 'á'; con la página de códigos
    heredada de Windows (cp1252) el propio `print` muere por
    `UnicodeEncodeError` y el fallo se leería como un fallo de la prueba, que
    no lo es. No cambia nada de lo que el script comprueba."""
    entorno = dict(os.environ)
    entorno["PYTHONIOENCODING"] = "utf-8"
    entorno["PYTHONUTF8"] = "1"
    return entorno


def _recorte(texto: str, limite: int = 6000) -> str:
    if len(texto) <= limite:
        return texto
    return texto[:limite] + "\n[... salida recortada, %d caracteres más ...]" % (len(texto) - limite)


def test_script_legacy(script_legacy):
    raiz = script_legacy.parent.parent
    try:
        proceso = subprocess.run(
            [sys.executable, str(script_legacy)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_S,
            env=_entorno_hijo(),
            cwd=str(raiz),
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            "%s no terminó en %d s. No es un fallo de comprobación: o el script "
            "es más lento que el límite (súbelo con ARCHMUSE_TEST_TIMEOUT) o se "
            "ha quedado colgado esperando algo." % (script_legacy.name, TIMEOUT_S)
        ) from exc

    salida = (proceso.stdout or "") + (proceso.stderr or "")

    if proceso.returncode != 0:
        pytest.fail(
            "%s terminó con código %d.\n\n--- salida del script ---\n%s"
            % (script_legacy.name, proceso.returncode, _recorte(salida))
        )

    # Salió bien, pero ¿comprobó algo? Un script que anuncia que le falta un
    # fichero y no ejecuta ni una comprobación es un SKIP, no un PASS: darlo
    # por verde sería exactamente el maquillaje que esta fase evita.
    if any(marca in salida for marca in MARCAS_DE_SALTO) and MARCA_DE_COMPROBACION not in salida:
        motivo = next(
            (linea.strip() for linea in salida.splitlines()
             if any(marca in linea for marca in MARCAS_DE_SALTO)),
            "el script declaró que le falta un recurso externo",
        )
        pytest.skip("%s: %s" % (script_legacy.name, motivo))
