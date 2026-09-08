# -*- coding: utf-8 -*-
"""Regresión permanente contra dos planos reales, ya anonimizados.

**Qué añaden estos dos ficheros que no diera ningún test anterior.** La
medición de un plano real sólo se comprobaba con la variable de entorno
`ARCHMUSE_DXF_PLANTA` apuntando a un fichero de fuera del repositorio: en
cualquier máquina que no fuera la de Pablo esos tests **se saltaban en
silencio**. Desde el 2026-09-08 la geometría real viaja con el repositorio
—derivada y auditada, ver `tests/fixtures/reales/MANIFIESTO.md`— y la regresión
corre siempre, también en CI.

**Las cifras van escritas a mano y a propósito.** Un test que sólo comprobara
«hay tres viviendas» seguiría pasando el día que el reparto asignara una
habitación a la vivienda de al lado. Estas son las que dan los planos originales,
verificadas contra ellos al derivar los fixtures.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from analyzer import medicion, parser

FIXTURES = Path(__file__).parent / "fixtures" / "reales"
PLANTA = FIXTURES / "planta_tres_viviendas.dxf"
SOLAPES = FIXTURES / "vivienda_con_solapes.dxf"


def _medir(ruta: Path) -> medicion.Medicion:
    return medicion.medir_planta(parser.leer_plano(parser.load_document(str(ruta))))


# --- La planta que sí se mide entera ----------------------------------------

def test_la_planta_real_se_mide_entera_con_las_dos_superficies():
    """Las dos magnitudes del criterio del arquitecto, vivienda a vivienda."""
    med = _medir(PLANTA)
    assert med.agrupacion == medicion.POR_ROTULOS
    assert med.piezas == 22
    medidas = {v.nombre: (v.util_interior_m2, v.util_exterior_m2)
               for v in med.viviendas}
    assert medidas == {
        "VT1/3": (58.78, 7.54),
        "VT2/2": (50.97, 7.47),
        "VT3/3": (59.11, 7.45),
    }


def test_la_planta_real_publica_sus_dos_superficies_y_ninguna_suma():
    med = _medir(PLANTA)
    assert med.util_interior_m2 == 168.86     # 58,78 + 50,97 + 59,11
    assert med.util_exterior_m2 == 22.46      # 7,54 + 7,47 + 7,45
    assert med.impedimentos == ()
    # El campo retirado el 2026-09-08 no ha vuelto por ninguna puerta.
    assert not hasattr(med, "total_util_m2")


def test_un_rotulo_sin_recintos_advierte_pero_no_bloquea():
    """El plano trae un «VT22/1» al que no va a parar ningún recinto. Podría ser
    una vivienda sin medir o una etiqueta de otra planta: no se decide, se dice
    — y las cifras se publican igual."""
    med = _medir(PLANTA)
    assert med.rotulos_sin_piezas == ("VT22/1",)
    assert med.advertencias and "VT22/1" in med.advertencias[0]
    assert med.util_interior_m2 is not None


def test_ninguna_pieza_del_plano_real_se_queda_sin_clasificar():
    """Si un rótulo real dejara de reconocerse, la vivienda entera se quedaría
    sin cifras. Este test es el que avisaría."""
    for vivienda in _medir(PLANTA).viviendas:
        assert vivienda.sin_clasificar == (), (
            "%s: %r" % (vivienda.nombre,
                        [p.nombre for p in vivienda.sin_clasificar]))


# --- La rama bloqueada ------------------------------------------------------

def test_la_vivienda_real_con_solapes_no_publica_ninguna_superficie():
    """Los 7,08 m² duplicados del plano real. Bloquean **las dos** cifras: un
    solape puede caer dentro de lo interior, dentro de lo exterior o a caballo,
    así que publicar una de las dos sería publicar algo que puede estar mal."""
    vivienda = _medir(SOLAPES).viviendas[0]
    assert vivienda.util_interior_m2 is None
    assert vivienda.util_exterior_m2 is None
    assert vivienda.diferencia_con_la_union_m2 == 7.08
    assert sorted(s.area_m2 for s in vivienda.solapes) == [3.08, 4.0]


def test_bloquear_las_cifras_no_borra_el_trabajo():
    """Las nueve piezas se siguen midiendo: es donde está casi todo el valor."""
    vivienda = _medir(SOLAPES).viviendas[0]
    assert len(vivienda.piezas) == 9
    assert vivienda.suma_interior_m2 == 58.78
    assert vivienda.suma_exterior_m2 == 16.17
    assert vivienda.impedimentos and "dos veces" in vivienda.impedimentos[0]


# --- El fixture sigue siendo anónimo ---------------------------------------

@pytest.mark.parametrize("ruta", [PLANTA, SOLAPES], ids=["planta", "solapes"])
def test_el_fixture_no_lleva_ningun_rastro_del_cliente(ruta):
    """El guardián de la fuga, no de la medición.

    Estos ficheros viven en un repositorio **público**. Si alguien regenera un
    fixture desde un plano de cliente sin pasarlo por
    `scripts/derivar_fixture_anonimo.py`, esto se pone rojo antes del commit.
    Comprueba las tres vías por las que se ha colado siempre: la cabecera (el
    original traía el nombre de pila de quien lo guardó), las definiciones de
    bloque (venían de un export de Revit, con códigos de vivienda del proyecto)
    y las capas del estudio.
    """
    import ezdxf

    doc = ezdxf.readfile(str(ruta))

    assert doc.header.get("$LASTSAVEDBY", "") in ("", "ezdxf"), (
        "la cabecera lleva el nombre de quien guardó el plano original")
    assert not [b.name for b in doc.blocks if not b.name.startswith("*")], (
        "hay definiciones de bloque: en los planos originales llevan códigos "
        "de vivienda del proyecto en el nombre")
    assert sorted(c.dxf.name for c in doc.layers) == ["0", "00 areas", "Defpoints"], (
        "hay capas que no son la de recintos: son las del estudio")

    textos = [e.plain_text().strip() for e in doc.modelspace()
              if e.dxftype() == "MTEXT"]
    assert textos, "sin rótulos el fixture no prueba nada"
    for texto in textos:
        assert len(texto) <= 32, "un texto largo no es un rótulo de estancia: %r" % texto
