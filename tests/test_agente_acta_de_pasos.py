# -*- coding: utf-8 -*-
"""`agente.acta.levantar_de_pasos()` -- el acta del bucle de capacidades
sueltas (sesión 2026-08-19, noche 8), sin Skill ni `Ejecutor` de por medio.

Ejecutar:  pytest tests/test_agente_acta_de_pasos.py

Cubre lo que `tests/test_copiloto_endpoint.py::test_toda_modificacion_queda_en_el_acta`
no puede probar sin levantar todo el endpoint HTTP: un paso fallido, las
limitaciones de la capacidad, y la propiedad de idempotencia que exige
`CLAUDE.md` §5 para cualquier cosa que produzca procedencia (mismos inputs ->
mismo sello).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from agente import acta as _acta  # noqa: E402
from agente.capacidad import Capacidad  # noqa: E402
from agente.registro import Registro  # noqa: E402


@dataclass(frozen=True)
class _PasoDePrueba:
    """Mismo duck-type que `agente.nucleo.PasoEjecutado` -- `levantar_de_pasos`
    no importa ese tipo (evita el ciclo acta -> nucleo), así que este doble
    basta para probarla aislada."""
    capacidad: str
    version: str
    argumentos: Dict[str, Any]
    resultado: Dict[str, Any]
    ok: bool


def _capacidad_de_prueba(**kw) -> Capacidad:
    base = dict(
        id="dominio.probar", version="1.0.0", dominio="dominio", naturaleza="determinista",
        descripcion="capacidad de prueba", parametros={"type": "object"},
        funcion=lambda **_: {"ok": True},
    )
    base.update(kw)
    return Capacidad(**base)


REGISTRO = Registro((_capacidad_de_prueba(limitaciones=("no comprueba X",)),))


def test_un_paso_con_exito_deja_su_cifra_trazable():
    paso = _PasoDePrueba(
        capacidad="dominio.probar", version="1.0.0",
        argumentos={"x": 1},
        resultado={"ok": True, "despues": {"y": 42}},
        ok=True,
    )
    acta = _acta.levantar_de_pasos(
        "hacer algo", [paso], capacidades=REGISTRO,
        proyecto_id="p1", ejecucion_id="e1",
    )

    assert acta.objetivo == "hacer algo"
    assert acta.completa is True
    (dato,) = acta.datos
    assert dato["nombre"] == "dominio.probar.y"
    assert dato["valor"] == 42
    assert dato["fuente"] == "dominio.probar@1.0.0"
    # La limitación declarada de la capacidad viaja al acta sin que nadie la
    # copie a mano -- se DERIVA, como el resto del acta (ver docstring de
    # agente/acta.py).
    assert any("no comprueba X" in n for n in acta.no_comprobado)


def test_un_paso_fallido_no_aporta_ningun_dato():
    paso = _PasoDePrueba(
        capacidad="dominio.probar", version="1.0.0",
        argumentos={"x": 1},
        resultado={"ok": False, "error": "fuera_de_rango", "detalle": "x es negativo"},
        ok=False,
    )
    acta = _acta.levantar_de_pasos(
        "hacer algo", [paso], capacidades=REGISTRO,
        proyecto_id="p1", ejecucion_id="e1",
    )

    assert acta.datos == ()
    assert acta.completa is False
    assert any("x es negativo" in n for n in acta.no_comprobado)
    assert acta.pasos[0]["verificado"] is False


def test_sin_pasos_el_acta_no_finge_haber_hecho_algo():
    acta = _acta.levantar_de_pasos(
        "sólo una pregunta", [], capacidades=REGISTRO,
        proyecto_id="p1", ejecucion_id="e1",
    )
    assert acta.pasos == ()
    assert acta.datos == ()
    assert acta.completa is False


def test_mismos_inputs_mismo_sello():
    """Idempotencia: el requisito de `CLAUDE.md` §5 para toda Tool aplicado
    al acta que las traza -- si esto se rompe, dos actas del mismo cambio
    dejarían de demostrar que fue el mismo cambio."""
    paso = _PasoDePrueba(
        capacidad="dominio.probar", version="1.0.0",
        argumentos={"x": 1}, resultado={"ok": True, "despues": {"y": 42}}, ok=True,
    )
    hacer = lambda: _acta.levantar_de_pasos(  # noqa: E731
        "hacer algo", [paso], capacidades=REGISTRO,
        proyecto_id="p1", ejecucion_id="e1", emitida_en="2026-08-19T00:00:00+00:00",
    )
    assert hacer().sello == hacer().sello


if __name__ == "__main__":  # pragma: no cover
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
