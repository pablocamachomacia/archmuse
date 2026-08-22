# -*- coding: utf-8 -*-
"""Banco de DXF plausibles: la misma vivienda válida (4 estancias, 36 m²
útiles) dibujada a la manera de varios estudios distintos —
`tests/fixtures/dxf_plausibles/`, generado por `generar_dxf_plausibles.py`.

**Criterio INVERSO al de `test_banco_tortura_dxf.py`.** Allí, éxito era no
reventar ante un DXF hostil: OK y AVISO valían igual, solo el traceback
importaba. Aquí cada fixture es, por construcción, un plano real y correcto
dibujado con una convención distinta — así que éxito es medir **sin
preguntar nada**: la Skill `superficies.medicion_de_planta` debe entregar
exactamente una vivienda con 36,00 m² de superficie útil total e
`impedimentos` vacío.

Cualquier fixture que en vez de eso publique «sin total», reparta mal una
pieza, o se niegue a medir, es un **falso rechazo** — una convención real de
dibujo que el parser no reconoce — y este test tiene que fallar para que no
pase desapercibido. `correr_banco.py` no basta para esto: solo distingue
OK/AVISO/CRASH por código de salida y por si hay traceback, y una vivienda
que sale «sin total» con su PDF escrito cuenta como OK ahí (es la
degradación elegante correcta cuando de verdad hace falta) — pero en este
banco, donde el plano no tiene ninguna razón real para no cuadrar, esa misma
degradación es la señal de que algo se leyó mal.

Invoca la Skill en proceso, igual que `scripts/medir_planta.py::main` y
`tests/test_medicion_de_planta.py` — no por subproceso: lo que importa aquí
es el valor medido, no el texto de consola, y parsear «36,00 m²» de una
tabla impresa sería más frágil que leer el dict real.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from agente.efectos import ESCRIBE_FICHERO, Autorizacion, Autorizaciones  # noqa: E402
from agente.ejecucion import BitacoraEnMemoria, Ejecutor, Paso, Plan  # noqa: E402
from agente.memoria import MemoriaDeProyecto, SustratoEnMemoria  # noqa: E402
from agente.registro import registro, registro_de_skills  # noqa: E402

SKILL = "superficies.medicion_de_planta"
BANCO = RAIZ / "tests" / "fixtures" / "dxf_plausibles"
SUPERFICIE_UTIL_ESPERADA_M2 = 36.0


def _dxfs() -> list[Path]:
    if not BANCO.is_dir():
        return []
    return sorted(BANCO.glob("*.dxf"))


def pytest_generate_tests(metafunc):
    if "dxf" not in metafunc.fixturenames:
        return
    casos = [pytest.param(ruta, id=ruta.stem) for ruta in _dxfs()]
    metafunc.parametrize("dxf", casos)


def _valor(salida: dict, nombre: str):
    for a in ((salida or {}).get("resultado") or {}).get("afirmaciones") or ():
        if a.get("nombre") == nombre:
            return a.get("valor")
    return None


def _medir(dxf: Path, tmp_path: Path) -> dict:
    """Invoca la Skill de medición sobre `dxf`, igual que hace
    `scripts/medir_planta.py::main`. Devuelve la `salida` cruda del paso (el
    dict con las afirmaciones serializadas)."""
    destino = tmp_path / (dxf.stem + "_medicion.pdf")
    skills = registro_de_skills(recargar=True)
    capacidades = registro(recargar=True)
    memoria = MemoriaDeProyecto("plausible-%s" % dxf.stem, SustratoEnMemoria())
    permisos = Autorizaciones((
        Autorizacion(efecto=ESCRIBE_FICHERO, alcance="ejecucion", autorizada_por="test"),
    ))
    plan = Plan(
        objetivo="Mide %s" % dxf.name,
        proyecto_id=memoria.proyecto_id,
        pasos=(Paso(id="medir", skill=SKILL, argumentos={
            "ruta_dxf": str(dxf.resolve()),
            "ruta_informe": str(destino.resolve()),
        }),),
    )
    ejecutor = Ejecutor(capacidades=capacidades, skills=skills, bitacora=BitacoraEnMemoria())
    resultado = ejecutor.ejecutar(plan, memoria, autorizaciones=permisos,
                                 ejecucion_id="test-%s" % dxf.stem)
    salida = resultado.pasos[0].salida if resultado.pasos else None
    if salida is None:
        motivo = "; ".join(p.motivo for p in resultado.pasos if p.motivo) or "sin motivo registrado"
        pytest.fail(
            "%s: la Skill se ha negado a medir directamente, sin producir ni "
            "una vivienda -- esto es peor que un falso rechazo parcial, es un "
            "rechazo total de un DXF que debería medirse sin preguntar nada. "
            "Motivo: %s" % (dxf.name, motivo)
        )
    assert salida is not None  # para el análisis estático: pytest.fail no vuelve
    return salida


def test_fixture_plausible_mide_36_m2_sin_falso_rechazo(dxf: Path, tmp_path):
    salida = _medir(dxf, tmp_path)
    viviendas = _valor(salida, "medicion.viviendas") or []
    assert len(viviendas) == 1, (
        "%s: se esperaba exactamente 1 vivienda, salieron %d"
        % (dxf.name, len(viviendas))
    )
    vivienda = viviendas[0]

    assert vivienda.get("impedimentos") == [], (
        "%s: la vivienda tiene impedimentos y no debería (falso rechazo): %r"
        % (dxf.name, vivienda.get("impedimentos"))
    )

    total = vivienda.get("total_util_m2")
    assert total is not None, (
        "%s: no se ha publicado total -- degradó a «sin total» en vez de "
        "medir. Esto es exactamente el falso rechazo que este banco existe "
        "para atrapar." % dxf.name
    )
    assert total == pytest.approx(SUPERFICIE_UTIL_ESPERADA_M2, abs=0.01), (
        "%s: total_util_m2 = %.2f, se esperaban %.2f m²"
        % (dxf.name, total, SUPERFICIE_UTIL_ESPERADA_M2)
    )
