"""Exportación a IFC4 de los espacios (`IfcSpace`) de una planta ya
analizada o generada.

`docs/prd/2026-08-17-exportacion-bim-ifc.md` (aprobado 2026-08-17, opción A
de §14): exportación ESTRICTA de `IfcSpace` -- superficie y nombre reales,
nada más. Deliberadamente NO genera `IfcWall`, `IfcSlab`, `IfcDoor` ni
`IfcWindow`: el modelo de ArchMuse no tiene espesor de muro, geometría de
forjado ni huecos posicionados en ningún punto del pipeline (mismo hallazgo
ya documentado en `analyzer/dxf_export.py` y en `circulation.py`) -- generar
esos elementos exigiría inventar dimensiones que nadie ha diseñado, dentro
de un formato que herramientas profesionales (Revit, ArchiCAD, Solibri)
tratan como dato real. La acción en la interfaz se llama "Exportar Espacios
BIM (.IFC)", nunca "Modelo BIM", para no prometer más de lo que contiene
(criterio de aceptación §8.4 del PRD).

**Por qué cada `IfcSpace` solo lleva un contorno 2D (`FootPrint`), sin
extrusión 3D.** Un sólido extruido necesita una altura de planta -- dato
que tampoco existe de forma fiable y verificada para cualquier proyecto
(ver limitación ya documentada en varios PRD de 2026-08-17). Inventar una
altura por defecto para poder mostrar un volumen sería el mismo error que
inventar un espesor de muro: una dimensión que nadie ha medido, presentada
dentro de un IFC como si lo fuera. El contorno 2D es honesto porque es
exactamente el mismo dato (`poligono`) que ya usa `plan_svg.py`/
`dxf_export.py` -- ninguna dimensión nueva, solo un formato distinto.

Función pura, sin I/O: construye el `ifcopenshell.file` en memoria; quien
llame decide cómo servirlo (ver `app.py`, mismo patrón que
`exportar_planta_dxf`)."""
from __future__ import annotations

from typing import Any, Iterable

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.project
import ifcopenshell.api.root
import ifcopenshell.api.unit
import ifcopenshell.util.shape_builder

from .dxf_export import _puntos_validos

IFC_SCHEMA = "IFC4"


def exportar_espacios_ifc(
    habitaciones: Iterable[dict], nombre_planta: str = "Planta", nombre_proyecto: str = "Proyecto ArchMuse",
) -> ifcopenshell.file:
    """Construye un `ifcopenshell.file` IFC4 con un `IfcSpace` por estancia
    de `habitaciones` -- mismo dato de entrada (`poligono`, `nombre`, y
    opcionalmente `area_m2`/`tipo`) que ya recibe `exportar_planta_dxf`.

    Jerarquía espacial mínima válida (IfcProject > IfcSite > IfcBuilding >
    IfcBuildingStorey > IfcSpace) -- IFC4 exige esta cadena para que un
    visor/CAD externo sitúe los espacios; ninguno de esos contenedores
    lleva geometría propia, son solo la estructura obligatoria del formato.

    Cualquier entrada sin `poligono` válido (menos de 3 puntos utilizables)
    se omite en silencio, mismo criterio que `exportar_planta_dxf`."""
    f = ifcopenshell.api.project.create_file(version=IFC_SCHEMA)
    proyecto = ifcopenshell.api.root.create_entity(f, ifc_class="IfcProject", name=nombre_proyecto)
    ifcopenshell.api.unit.assign_unit(f)  # SI por defecto: metro, metro cuadrado.
    ctx_modelo = ifcopenshell.api.context.add_context(f, context_type="Model")
    ctx_footprint = ifcopenshell.api.context.add_context(
        f, context_type="Model", context_identifier="FootPrint", target_view="PLAN_VIEW", parent=ctx_modelo,
    )

    solar = ifcopenshell.api.root.create_entity(f, ifc_class="IfcSite", name="Solar")
    edificio = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuilding", name="Edificio")
    planta = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuildingStorey", name=nombre_planta)

    ifcopenshell.api.aggregate.assign_object(f, relating_object=proyecto, products=[solar])
    ifcopenshell.api.aggregate.assign_object(f, relating_object=solar, products=[edificio])
    ifcopenshell.api.aggregate.assign_object(f, relating_object=edificio, products=[planta])

    builder = ifcopenshell.util.shape_builder.ShapeBuilder(f)
    espacios = []

    for h in habitaciones:
        if not isinstance(h, dict):
            continue
        puntos = _puntos_validos(h.get("poligono"))
        if not puntos:
            continue
        nombre = str(h.get("nombre") or "").strip() or "Estancia"

        espacio = ifcopenshell.api.root.create_entity(f, ifc_class="IfcSpace", name=nombre)
        # `LongName`/uso: dato real (`tipo`, ya clasificado por `plan_svg.room_type`),
        # nunca una tipología adivinada aquí -- se deja vacío si no llega.
        tipo = h.get("tipo")
        if tipo:
            espacio.LongName = str(tipo)

        contorno = builder.polyline([(x, y) for x, y in puntos], closed=True)
        representacion = builder.get_representation(ctx_footprint, contorno, representation_type="Curve2D")
        f.create_entity(
            "IfcProductDefinitionShape", Representations=[representacion],
        )
        espacio.Representation = f.by_type("IfcProductDefinitionShape")[-1]

        area_m2 = h.get("area_m2")
        if isinstance(area_m2, (int, float)):
            qto = f.create_entity(
                "IfcElementQuantity",
                GlobalId=ifcopenshell.guid.new(),
                OwnerHistory=proyecto.OwnerHistory,
                Name="Qto_SpaceBaseQuantities",
                Quantities=[
                    f.create_entity(
                        "IfcQuantityArea", Name="NetFloorArea", AreaValue=float(area_m2),
                    )
                ],
            )
            f.create_entity(
                "IfcRelDefinesByProperties",
                GlobalId=ifcopenshell.guid.new(),
                OwnerHistory=proyecto.OwnerHistory,
                RelatedObjects=[espacio],
                RelatingPropertyDefinition=qto,
            )

        espacios.append(espacio)

    if espacios:
        # `IfcSpace` es a su vez un `IfcSpatialStructureElement` (como la
        # propia planta) -- se cuelga de la jerarquía con descomposición
        # (`IfcRelAggregates`, `aggregate.assign_object`), NO con
        # `spatial.assign_container`/`IfcRelContainedInSpatialStructure`,
        # que es para elementos físicos (`IfcElement`: muros, puertas...)
        # dentro de una estructura espacial. Confundir las dos relaciones
        # es un error real de esquema, no solo de estilo -- un visor IFC
        # no encontraría los espacios bajo la planta.
        ifcopenshell.api.aggregate.assign_object(f, relating_object=planta, products=espacios)

    return f
