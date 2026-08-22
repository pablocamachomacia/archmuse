# -*- coding: utf-8 -*-
"""Regresión: los 13 DXF de tortura de `tests/fixtures/dxf_tortura/` nunca
deben producir un traceback contra los scripts que analizan un DXF de golpe.

**Qué son los ficheros de tortura.** Cada uno ataca una suposición del parser
(sin unidades, mm declarados como m, estancias solapadas, bloques anidados,
geometría degenerada, coordenadas UTM, texto hostil, formato R12...). Se
generan con `generar_dxf_tortura.py` (raíz del repo) y su ataque está descrito
en `tests/fixtures/dxf_tortura/MANIFIESTO.md`.

**Qué es éxito y qué no.** La regla de oro del proyecto (README, "DXF y IFC")
es que el parser **se niega en vez de asumir**. Frente a un DXF hostil, un
script puede:

  a) preguntar, con motivo (código de salida ≠ 0, sin traceback), o
  b) descartar la entidad problemática, inventariada con su razón, o
  c) degradarse a un informe parcial.

Lo único que NUNCA es aceptable es un traceback de Python o un cuelgue: eso
es un bug, no un rechazo controlado. Este test reproduce exactamente el
criterio de `correr_banco.py` (CRASH = traceback o timeout) para que una
regresión footprint quede atrapada en CI, no solo al correr el banco a mano.

Uso manual: `python correr_banco.py scripts/revisar_plano.py
tests/fixtures/dxf_tortura/` sigue funcionando igual para inspección humana
con resumen OK/AVISO/CRASH; este fichero es su versión automatizada.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).parent.parent
BANCO = RAIZ / "tests" / "fixtures" / "dxf_tortura"
SCRIPTS = [
    RAIZ / "scripts" / "revisar_plano.py",
    RAIZ / "scripts" / "cuadro_de_superficies.py",
    RAIZ / "scripts" / "medir_planta.py",
]

TIMEOUT_S = int(os.environ.get("ARCHMUSE_TEST_TIMEOUT", "120"))


def _entorno_hijo() -> dict:
    """Fuerza UTF-8 en el subproceso: estos scripts imprimen '≥', 'ñ' y 'á';
    con la página de códigos heredada de Windows (cp1252) `print` moriría por
    `UnicodeEncodeError` y ese fallo se leería como un CRASH que no lo es.
    Mismo motivo que `tests/test_scripts_legacy.py::_entorno_hijo`."""
    entorno = dict(os.environ)
    entorno["PYTHONIOENCODING"] = "utf-8"
    entorno["PYTHONUTF8"] = "1"
    return entorno


def _dxfs() -> list[Path]:
    if not BANCO.is_dir():
        return []
    return sorted(BANCO.glob("*.dxf"))


def pytest_generate_tests(metafunc):
    if "script" not in metafunc.fixturenames or "dxf" not in metafunc.fixturenames:
        return
    dxfs = _dxfs()
    casos = [
        pytest.param(script, dxf, id="%s-%s" % (script.name, dxf.stem))
        for script in SCRIPTS
        for dxf in dxfs
    ]
    metafunc.parametrize("script,dxf", casos)


def test_banco_tortura_no_produce_traceback(script: Path, dxf: Path):
    if not dxf.exists():
        pytest.skip("fixture no encontrada: %s" % dxf)
    if not script.exists():
        pytest.skip("script no encontrado: %s" % script)

    try:
        proceso = subprocess.run(
            [sys.executable, str(script), str(dxf)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_S,
            env=_entorno_hijo(),
            cwd=str(RAIZ),
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            "%s no terminó en %ds contra %s: esto cuenta como CRASH (posible "
            "bucle o cuelgue esperando algo que nunca llega)."
            % (script.name, TIMEOUT_S, dxf.name)
        )
        return

    salida = (proceso.stdout or "") + (proceso.stderr or "")
    assert "Traceback (most recent call last)" not in salida, (
        "%s revienta con un traceback contra %s (esto contradice la regla de "
        "oro del proyecto: nunca inventa ni asume, y tampoco revienta — debe "
        "preguntar, descartar con motivo o degradarse).\n\n"
        "--- salida del proceso ---\n%s" % (script.name, dxf.name, salida[-4000:])
    )
