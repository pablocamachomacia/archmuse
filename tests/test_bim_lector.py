# -*- coding: utf-8 -*-
"""La frontera BIM: leer un IFC y decir lo que NO dice.

**Por qué el test hace la ida y la vuelta.** `analyzer/ifc_export.py` escribe
IFC y `bim/lector_ifc.py` lo lee. Probar el lector contra un fichero fabricado a
mano comprobaría que el lector entiende lo que yo creo que dice un IFC; probarlo
contra lo que este mismo repositorio exporta comprueba que las dos mitades de la
frontera se entienden entre sí, que es la propiedad que hace falta el día que un
complemento de Revit escriba por un lado y ArchMuse lea por el otro.

**Y el caso que más importa** es el de un espacio sin superficie declarada: el
lector tiene que devolver `null` con motivo y no una superficie calculada de la
geometría. Es la diferencia entre «el modelo dice que mide 20 m²» y «he deducido
que mide 20 m²», y en un cuadro de superficies esas dos frases no valen lo mismo.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from agente.herramientas.bim import inventario_de_ifc  # noqa: E402
from analyzer.ifc_export import exportar_espacios_ifc  # noqa: E402
from bim import IFCIlegible, inventariar  # noqa: E402

HABITACIONES = [
    {"nombre": "Salón", "poligono": [[0, 0], [5, 0], [5, 4], [0, 4]],
     "area_m2": 20.0, "tipo": "salon"},
    {"nombre": "Dormitorio 1", "poligono": [[5, 0], [8, 0], [8, 4], [5, 4]],
     "area_m2": 12.0, "tipo": "dormitorio"},
]


def test_lo_que_exporta_archmuse_lo_lee_archmuse():
    inventario = inventariar(exportar_espacios_ifc(HABITACIONES, nombre_planta="Planta baja"))

    assert inventario.esquema == "IFC4"
    assert inventario.proyecto == "Proyecto ArchMuse"
    assert inventario.plantas == ("Planta baja",)
    assert {e.nombre for e in inventario.espacios} == {"Salón", "Dormitorio 1"}
    assert inventario.conteo_por_clase["IfcSpace"] == 2


def test_cada_espacio_conserva_su_planta_y_su_uso():
    inventario = inventariar(exportar_espacios_ifc(HABITACIONES, nombre_planta="Planta 2"))
    salon = next(e for e in inventario.espacios if e.nombre == "Salón")

    assert salon.planta == "Planta 2"
    assert salon.uso == "salon"
    assert salon.identificador, "sin GlobalId no hay identidad estable entre versiones"


def test_la_superficie_declarada_se_lee_y_se_suma():
    inventario = inventariar(exportar_espacios_ifc(HABITACIONES))

    assert inventario.superficie_declarada_m2 == pytest.approx(32.0)
    assert inventario.espacios_sin_superficie == ()


def test_una_superficie_no_declarada_no_se_calcula_de_la_geometria():
    """El caso central: el modelo no lo dice, así que ArchMuse no lo dice.

    El polígono está ahí y su área es trivial de calcular. No se calcula: una
    superficie deducida presentada junto a superficies declaradas es
    indistinguible de ellas, y esa mezcla es lo que hace que un acta de
    procedencia deje de significar algo.
    """
    sin_area = [{"nombre": "Trastero", "poligono": [[0, 0], [2, 0], [2, 2], [0, 2]]}]
    inventario = inventariar(exportar_espacios_ifc(sin_area))

    trastero = inventario.espacios[0]
    assert trastero.superficie_m2 is None
    assert "no declara" in trastero.motivo_sin_superficie
    assert "no la calcula" in trastero.motivo_sin_superficie
    assert inventario.espacios_sin_superficie == ("Trastero",)
    assert any("Trastero" in a for a in inventario.avisos)


def test_sin_superficies_declaradas_el_total_es_desconocido_y_no_cero():
    """Un cero en un cuadro de superficies se lee «mide cero», no «no lo sé»."""
    sin_area = [{"nombre": "Trastero", "poligono": [[0, 0], [2, 0], [2, 2], [0, 2]]}]
    inventario = inventariar(exportar_espacios_ifc(sin_area))

    assert inventario.superficie_declarada_m2 is None


def test_un_modelo_sin_espacios_lo_dice_en_vez_de_callarlo():
    inventario = inventariar(exportar_espacios_ifc([]))

    assert inventario.espacios == ()
    assert any("ningún IfcSpace" in a for a in inventario.avisos)


def test_un_fichero_que_no_es_ifc_se_rechaza_con_motivo(tmp_path):
    """Aviso conocido y ajeno al repositorio.

    Al abrir un fichero inválido, el destructor de ifcopenshell.file levanta un
    KeyError que pytest reporta como PytestUnraisableExceptionWarning. Es un
    defecto de la librería, ocurre DESPUÉS de que IFCIlegible se haya levantado
    correctamente, y no afecta al resultado. Queda anotado para que nadie lo
    persiga creyendo que es nuestro.
    """
    falso = tmp_path / "esto_no_es.ifc"
    falso.write_text("no soy un IFC", encoding="utf-8")

    with pytest.raises(IFCIlegible):
        inventariar(falso)


def test_un_fichero_que_no_existe_se_rechaza(tmp_path):
    with pytest.raises(IFCIlegible, match="no existe"):
        inventariar(tmp_path / "fantasma.ifc")


# --- La capacidad que lo envuelve -------------------------------------------

def test_la_capacidad_devuelve_un_resultado_estructurado(tmp_path):
    ruta = tmp_path / "modelo.ifc"
    exportar_espacios_ifc(HABITACIONES, nombre_planta="Planta baja").write(str(ruta))

    resultado = inventario_de_ifc(str(ruta))

    assert resultado["ok"] is True
    assert resultado["esquema"] == "IFC4"
    assert resultado["superficie_declarada_m2"] == pytest.approx(32.0)
    assert len(resultado["espacios"]) == 2


def test_la_capacidad_traduce_el_fallo_a_ok_false_sin_inventar_nada(tmp_path):
    falso = tmp_path / "roto.ifc"
    falso.write_text("basura", encoding="utf-8")

    resultado = inventario_de_ifc(str(falso))

    assert resultado["ok"] is False
    assert resultado["error"] == "ifc_ilegible"
    assert "espacios" not in resultado, "un fallo no devuelve un inventario a medias"


def test_la_capacidad_esta_en_el_registro():
    from agente.registro import registro

    capacidad = registro(recargar=True).buscar("bim.inventario_de_ifc")
    assert capacidad.naturaleza == "determinista"
    assert any("no calcula superficies" in l for l in capacidad.limitaciones)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
