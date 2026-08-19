# -*- coding: utf-8 -*-
"""Lectura de un IFC: qué contiene el modelo, y qué NO dice de sí mismo.

Es la pieza mínima que hace alcanzable «revisa este modelo BIM» sin prometer
más de lo que se puede sostener hoy. Responde tres preguntas y ninguna más:
qué esquema es, qué hay dentro, y qué superficies están **declaradas**.

**La decisión de diseño que gobierna el módulo: no se calcula lo que el fichero
no dice.** `ifcopenshell` permite teselar la geometría de un `IfcSpace` y
obtener su superficie. Sería fácil, sería impresionante, y sería una superficie
*calculada por ArchMuse a partir de una representación geométrica cuya calidad
no ha verificado nadie* presentada junto a otras que sí venían declaradas por el
autor del modelo. Dos cosas distintas con la misma pinta. Aquí, una superficie
no declarada sale como `None` con motivo, y quien quiera calcularla tendrá que
pedir una capacidad que diga que la calcula.

Esa es la misma postura que `normativa/` toma con el repliegue silencioso y que
`modelo/` toma con el dato plausible. No es purismo: es la única razón por la
que el acta de procedencia significa algo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import ifcopenshell
    import ifcopenshell.util.element as _elemento
except ImportError:  # pragma: no cover - mismo patrón que el resto del repositorio
    ifcopenshell = None  # type: ignore[assignment]
    _elemento = None  # type: ignore[assignment]

#: Dónde declara IFC la superficie útil de un espacio. Si no está ahí, no está.
CONJUNTO_DE_CANTIDADES = "Qto_SpaceBaseQuantities"
CANTIDAD_SUPERFICIE = "NetFloorArea"

#: Las clases cuyo recuento le dice algo a un arquitecto de un vistazo. El
#: inventario completo por clase también se devuelve; esto es el titular.
CLASES_DE_INTERES = (
    "IfcSpace", "IfcBuildingStorey", "IfcWall", "IfcSlab", "IfcDoor",
    "IfcWindow", "IfcColumn", "IfcBeam", "IfcStair",
)


class IFCIlegible(Exception):
    """El fichero no se puede abrir como IFC. Nunca se devuelve un inventario a medias."""


@dataclass(frozen=True)
class EspacioIFC:
    """Un `IfcSpace` tal como el fichero lo declara."""

    nombre: str
    identificador: str                  # GlobalId: la identidad estable en IFC
    planta: Optional[str] = None
    uso: Optional[str] = None           # LongName; vacío si el modelo no lo trae
    superficie_m2: Optional[float] = None
    motivo_sin_superficie: str = ""

    def a_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "identificador": self.identificador,
            "planta": self.planta,
            "uso": self.uso,
            "superficie_m2": self.superficie_m2,
            "motivo_sin_superficie": self.motivo_sin_superficie,
        }


@dataclass(frozen=True)
class InventarioIFC:
    """Lo que hay en el fichero, y lo que el fichero no dice."""

    esquema: str
    proyecto: Optional[str] = None
    plantas: Tuple[str, ...] = field(default_factory=tuple)
    espacios: Tuple[EspacioIFC, ...] = field(default_factory=tuple)
    conteo_por_clase: Dict[str, int] = field(default_factory=dict)
    avisos: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def superficie_declarada_m2(self) -> Optional[float]:
        """Suma de las superficies **declaradas**. `None` si no hay ninguna.

        Devolver 0.0 cuando no hay ninguna sería el error clásico: un cuadro de
        superficies con un cero se lee como «mide cero», no como «no lo sé».
        """
        declaradas = [e.superficie_m2 for e in self.espacios if e.superficie_m2 is not None]
        return round(sum(declaradas), 3) if declaradas else None

    @property
    def espacios_sin_superficie(self) -> Tuple[str, ...]:
        return tuple(e.nombre for e in self.espacios if e.superficie_m2 is None)

    def a_dict(self) -> dict:
        return {
            "esquema": self.esquema,
            "proyecto": self.proyecto,
            "plantas": list(self.plantas),
            "espacios": [e.a_dict() for e in self.espacios],
            "conteo_por_clase": dict(self.conteo_por_clase),
            "superficie_declarada_m2": self.superficie_declarada_m2,
            "espacios_sin_superficie": list(self.espacios_sin_superficie),
            "avisos": list(self.avisos),
        }


def inventariar(fichero) -> InventarioIFC:
    """Inventario de un IFC. Acepta una ruta o un `ifcopenshell.file` ya abierto.

    Que acepte las dos cosas no es comodidad: `analyzer/ifc_export.py` produce
    un `ifcopenshell.file` en memoria, y poder inventariarlo sin escribirlo a
    disco es lo que permite probar la ida y la vuelta en un test.
    """
    if ifcopenshell is None:  # pragma: no cover - se avisa igual que en el resto
        raise IFCIlegible(
            "ifcopenshell no está instalado. `pip install -r requirements.txt`."
        )

    modelo = _abrir(fichero)
    avisos: List[str] = []

    proyectos = modelo.by_type("IfcProject")
    proyecto = proyectos[0].Name if proyectos else None
    if not proyectos:
        avisos.append(
            "el fichero no declara IfcProject: no es un modelo IFC completo, aunque "
            "se haya podido abrir"
        )

    plantas = tuple(
        (p.Name or "(planta sin nombre)") for p in modelo.by_type("IfcBuildingStorey")
    )
    espacios = tuple(_leer_espacio(e, avisos) for e in modelo.by_type("IfcSpace"))
    if not espacios:
        avisos.append(
            "el modelo no contiene ningún IfcSpace: no se puede decir nada de sus "
            "superficies ni de su programa"
        )

    conteo = {}
    for clase in CLASES_DE_INTERES:
        try:
            n = len(modelo.by_type(clase))
        except Exception:  # noqa: BLE001 - una clase ausente del esquema no es un error
            n = 0
        if n:
            conteo[clase] = n

    return InventarioIFC(
        esquema=getattr(modelo, "schema", "desconocido"),
        proyecto=proyecto,
        plantas=plantas,
        espacios=espacios,
        conteo_por_clase=conteo,
        avisos=tuple(dict.fromkeys(avisos)),
    )


def _abrir(fichero):
    if hasattr(fichero, "by_type"):
        return fichero
    ruta = Path(fichero)
    if not ruta.exists():
        raise IFCIlegible("no existe el fichero «%s»" % ruta)
    try:
        return ifcopenshell.open(str(ruta))
    except Exception as exc:  # noqa: BLE001 - el motivo real le sirve al usuario
        raise IFCIlegible("«%s» no se ha podido abrir como IFC: %s" % (ruta.name, exc)) from exc


def _leer_espacio(espacio, avisos: List[str]) -> EspacioIFC:
    nombre = (getattr(espacio, "Name", None) or "(espacio sin nombre)").strip()
    superficie, motivo = _superficie_declarada(espacio)
    if superficie is None and motivo:
        avisos.append("«%s»: %s" % (nombre, motivo))
    return EspacioIFC(
        nombre=nombre,
        identificador=getattr(espacio, "GlobalId", "") or "",
        planta=_planta_de(espacio),
        uso=(getattr(espacio, "LongName", None) or None),
        superficie_m2=superficie,
        motivo_sin_superficie=motivo,
    )


def _superficie_declarada(espacio) -> Tuple[Optional[float], str]:
    """La superficie que el modelo declara, o el motivo de que no haya.

    Nunca se calcula a partir de la geometría: ver el docstring del módulo.
    """
    try:
        cantidades = _elemento.get_psets(espacio, qtos_only=True) or {}
    except Exception as exc:  # noqa: BLE001 - un pset roto no tumba el inventario
        return None, "no se han podido leer sus cantidades (%s)" % type(exc).__name__

    conjunto = cantidades.get(CONJUNTO_DE_CANTIDADES) or {}
    valor = conjunto.get(CANTIDAD_SUPERFICIE)
    if valor is None:
        return None, (
            "el modelo no declara %s en %s; ArchMuse no la calcula a partir de la "
            "geometría para no mezclar superficies declaradas con superficies deducidas"
            % (CANTIDAD_SUPERFICIE, CONJUNTO_DE_CANTIDADES)
        )
    try:
        return float(valor), ""
    except (TypeError, ValueError):
        return None, "la superficie declarada no es un número: %r" % (valor,)


def _planta_de(espacio) -> Optional[str]:
    """La planta que contiene el espacio, por cualquiera de las dos vías de IFC.

    IFC4 admite dos formas de colgar un `IfcSpace` de una planta y las dos se
    usan en la práctica: agregación (`IfcRelAggregates`, que es la que exige el
    esquema para espacios y la que usa `analyzer/ifc_export.py`) y contención
    espacial (`IfcRelContainedInSpatialStructure`, frecuente en modelos
    exportados por herramientas comerciales). Mirar solo una deja media
    industria fuera, así que se miran las dos y se devuelve `None` si ninguna
    dice nada — que es distinto de decir que el espacio no tiene planta.
    """
    for relacion in getattr(espacio, "Decomposes", ()) or ():
        contenedor = getattr(relacion, "RelatingObject", None)
        if contenedor is not None and contenedor.is_a("IfcBuildingStorey"):
            return contenedor.Name or "(planta sin nombre)"
    for relacion in getattr(espacio, "ContainedInStructure", ()) or ():
        contenedor = getattr(relacion, "RelatingStructure", None)
        if contenedor is not None and contenedor.is_a("IfcBuildingStorey"):
            return contenedor.Name or "(planta sin nombre)"
    return None
