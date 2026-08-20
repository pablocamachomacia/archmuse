# -*- coding: utf-8 -*-
"""Los inventarios de capacidades y el registro en codigo no pueden divergir.

Ejecutar:  pytest tests/test_inventarios_no_divergen.py

**El problema que esto cierra, y por que hacia falta un test mas.** El registro
se puebla por descubrimiento --dejar un fichero en `agente/herramientas/` basta--
y eso es bueno: anadir una capacidad no obliga a editar ninguna lista central.
Pero hay **cuatro inventarios** que si tienen que seguirle el paso:

1. `tests/test_agente_nucleo.py` — el conjunto esperado de ids.
2. `tests/test_agente_herramientas.py` — como se invoca cada una.
3. `tests/fixtures/golden/G11_capacidades.json` — la salida congelada.
4. `tests/fixtures/contratos_de_capacidad.json` — el contrato congelado.

Los cuatro ya fallan por separado cuando alguien anade una capacidad, y eso
funciona. Lo que NO funcionaba es el diagnostico: el 2026-08-19, con dos
sesiones trabajando en paralelo, aparecieron tres fallos en tres ficheros
distintos que eran **el mismo problema** --tres capacidades nuevas sin registrar
en los inventarios-- y hubo que abrir cada uno para entenderlo.

Este test los mira **todos a la vez** y dice, en un solo mensaje, que capacidad
falta en que inventario. No sustituye a los otros: llega antes y explica.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agente.registro import registro  # noqa: E402

GOLDEN = RAIZ / "tests" / "fixtures" / "golden" / "G11_capacidades.json"
CONTRATOS = RAIZ / "tests" / "fixtures" / "contratos_de_capacidad.json"


def _json(ruta: Path) -> dict:
    """El fichero congelado, sin sus claves de metadatos.

    Tanto el golden como los contratos llevan una `_nota` explicando como se
    regeneran. Es documentacion dentro del fichero, no una capacidad, y contarla
    haria que este test acusara a un id que no existe.
    """
    if not ruta.exists():
        return {}
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return {k: v for k, v in datos.items() if not k.startswith("_")}


def _ids_del_registro() -> set:
    return set(registro(recargar=True).ids())


def _deterministas() -> set:
    return {c.id for c in registro(recargar=True) if c.naturaleza == "determinista"}


def test_ningun_inventario_se_queda_atras_del_registro():
    """Un solo mensaje con todo lo que falta, en vez de tres fallos sueltos."""
    from tests.test_agente_goldens import CASOS

    # El inventario de invocaciones vive dentro de la funcion de test, asi que
    # se lee del fuente: es feo, y es preferible a duplicarlo aqui --que seria
    # crear un quinto inventario para vigilar los otros cuatro--.
    fuente = (RAIZ / "tests" / "test_agente_herramientas.py").read_text(encoding="utf-8")

    registro_ids = _ids_del_registro()
    faltan: list = []

    for identificador in sorted(registro_ids):
        if '"%s"' % identificador not in fuente:
            faltan.append("%s — sin caso de invocación en test_agente_herramientas.py"
                          % identificador)

    for identificador in sorted(_deterministas()):
        if identificador not in CASOS:
            faltan.append("%s — determinista sin caso golden en test_agente_goldens.py"
                          % identificador)
        elif identificador not in _json(GOLDEN):
            faltan.append("%s — declarado en CASOS pero sin congelar en G11" % identificador)

    congelados = set(_json(CONTRATOS))
    for identificador in sorted(registro_ids - congelados):
        faltan.append("%s — sin contrato congelado (ejecuta "
                      "`python tests/test_agente_compatibilidad.py --congelar`)" % identificador)

    assert not faltan, (
        "el registro tiene capacidades que los inventarios no conocen:\n  - %s\n\n"
        "Todas las capacidades del registro tienen que estar en los cuatro inventarios. "
        "Si acabas de añadir una, esto es la lista de lo que te queda."
        % "\n  - ".join(faltan))


def test_ningun_inventario_va_por_delante_del_registro():
    """El reverso: un inventario que menciona una capacidad borrada da falsa
    sensacion de cobertura y esconde que algo desaparecio."""
    from tests.test_agente_goldens import CASOS

    registro_ids = _ids_del_registro()
    sobran: list = []

    for identificador in sorted(set(CASOS) - registro_ids):
        sobran.append("%s — tiene caso golden y no está en el registro" % identificador)
    for identificador in sorted(set(_json(CONTRATOS)) - registro_ids):
        sobran.append("%s — tiene contrato congelado y no está en el registro" % identificador)

    assert not sobran, "inventarios que hablan de capacidades que ya no existen:\n  - %s" % (
        "\n  - ".join(sobran))


def test_toda_capacidad_del_registro_es_alcanzable_por_su_nombre():
    """Un id en el registro que no se puede buscar es un id que nadie puede
    invocar: el descubrimiento habria dejado de servir para nada."""
    reg = registro(recargar=True)
    for capacidad in reg:
        assert reg.buscar(capacidad.id) is capacidad
        assert reg.buscar(capacidad.nombre_de_herramienta) is capacidad
