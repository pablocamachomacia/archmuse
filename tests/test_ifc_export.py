import tempfile
import os

import ifcopenshell

from analyzer.ifc_export import exportar_espacios_ifc

HABITACIONES = [
    {"nombre": "Salón", "poligono": [[0, 0], [5, 0], [5, 4], [0, 4]], "area_m2": 20.0, "tipo": "salon"},
    {"nombre": "Dormitorio 1", "poligono": [[5, 0], [8, 0], [8, 4], [5, 4]], "area_m2": 12.0, "tipo": "dormitorio"},
]


def test_genera_un_ifcspace_por_habitacion():
    f = exportar_espacios_ifc(HABITACIONES, nombre_planta="Planta baja")
    espacios = f.by_type("IfcSpace")
    assert len(espacios) == 2
    assert {e.Name for e in espacios} == {"Salón", "Dormitorio 1"}


def test_ningun_ifcwall_ifcdoor_ifcwindow_ifcslab():
    """Criterio de aceptación central del PRD: exportación ESTRICTA de
    IfcSpace, nunca elementos ficticios."""
    f = exportar_espacios_ifc(HABITACIONES)
    for clase in ("IfcWall", "IfcSlab", "IfcDoor", "IfcWindow"):
        assert f.by_type(clase) == []


def test_superficie_real_en_quantities():
    f = exportar_espacios_ifc(HABITACIONES)
    salon = next(e for e in f.by_type("IfcSpace") if e.Name == "Salón")
    import ifcopenshell.util.element as ue
    qtos = ue.get_psets(salon, qtos_only=True)
    assert qtos["Qto_SpaceBaseQuantities"]["NetFloorArea"] == 20.0


def test_habitacion_sin_poligono_se_omite():
    f = exportar_espacios_ifc([{"nombre": "Sin geometría", "poligono": []}])
    assert f.by_type("IfcSpace") == []


def test_jerarquia_espacial_minima():
    f = exportar_espacios_ifc(HABITACIONES, nombre_planta="Planta 2")
    assert len(f.by_type("IfcProject")) == 1
    assert len(f.by_type("IfcSite")) == 1
    assert len(f.by_type("IfcBuilding")) == 1
    planta = f.by_type("IfcBuildingStorey")[0]
    assert planta.Name == "Planta 2"


def test_round_trip_lectura_con_ifcopenshell():
    f = exportar_espacios_ifc(HABITACIONES)
    tmp = tempfile.NamedTemporaryFile(suffix=".ifc", delete=False)
    tmp.close()
    try:
        f.write(tmp.name)
        f2 = ifcopenshell.open(tmp.name)
        assert len(f2.by_type("IfcSpace")) == 2
    finally:
        os.unlink(tmp.name)
