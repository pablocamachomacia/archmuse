# -*- coding: utf-8 -*-
"""Lectura de un IFC: qué contiene el modelo, y qué NO dice de sí mismo.

Es la pieza mínima que hace alcanzable «revisa este modelo BIM» sin prometer
más de lo que se puede sostener hoy. Responde varias preguntas concretas y
ninguna más: qué esquema es, qué hay dentro (todo, no una lista fija de
clases), qué superficies/volúmenes están **declarados**, qué plantas y qué
sitio geográfico declara el proyecto, y qué huecos (puertas/ventanas) traen
sus dimensiones declaradas.

**La decisión de diseño que gobierna el módulo: no se calcula lo que el fichero
no dice.** `ifcopenshell` permite teselar la geometría de un `IfcSpace` y
obtener su superficie. Sería fácil, sería impresionante, y sería una superficie
*calculada por ArchMuse a partir de una representación geométrica cuya calidad
no ha verificado nadie* presentada junto a otras que sí venían declaradas por el
autor del modelo. Dos cosas distintas con la misma pinta. Aquí, una superficie
no declarada sale como `None` con motivo, y quien quiera calcularla tendrá que
pedir una capacidad que diga que la calcula. Lo mismo aplica a volúmenes,
elevaciones y anchos/altos de hueco: todo lo que este módulo devuelve es lo que
el fichero declara, nunca una medida deducida de su geometría.

Esa es la misma postura que `normativa/` toma con el repliegue silencioso y que
`modelo/` toma con el dato plausible. No es purismo: es la única razón por la
que el acta de procedencia significa algo.

**Ampliación 2026-08-20 (paso 3 del roadmap, "avanzar la lectura de modelo BIM
real"), verificada contra IFC reales de terceros, no solo contra el
round-trip sintético de `analyzer/ifc_export.py`:**

1. **Corrección de unidades, confirmada como un bug real, no hipotético --
   y con una segunda vuelta de tornillo que casi se pasa por alto.**
   `ifcopenshell.util.element.get_psets()` devuelve el valor **crudo** tal como
   está en el fichero STEP, sin convertir a metros -- verificado fabricando a
   propósito un IFC con unidades en milímetros y leyendo su cantidad de vuelta:
   el valor que sale es el que se escribió, sin escalar. Los cuatro IFC usados
   para verificar esta ampliación (los tres reales de terceros y el que
   produce `analyzer/ifc_export.py`) declaran la longitud en **milímetros**.
   La vuelta de tornillo: **la superficie y el volumen NO se derivan de esa
   escala de longitud al cuadrado/cubo** -- IFC las declara como unidades SI
   independientes (`AREAUNIT`/`VOLUMEUNIT`), y los cuatro ficheros las
   declaran ya en m²/m³ directamente, mezcladas con longitud en milímetros.
   Elevar la escala de longitud al cuadrado (el primer intento de esta misma
   sesión) habría dejado la superficie 1.000.000 de veces más pequeña de lo
   real -- se descubrió al verificar contra los ficheros reales, no por
   inspección de código. Se corrige con `ifcopenshell.util.unit.
   calculate_unit_scale()` llamado **tres veces, una por tipo de unidad**
   (`LENGTHUNIT`/`AREAUNIT`/`VOLUMEUNIT`, ver `_Escalas`/`_escalas_unidad`).
   Con las unidades por defecto de `analyzer/ifc_export.py`, las tres escalas
   ya eran (mm, m², m³) antes de esta ampliación -- el camino sintético
   existente **tenía el mismo bug latente**, solo que invisible porque nadie
   había leído `Elevation`/`OverallWidth` hasta ahora; los tests existentes
   pasaban porque solo ejercitaban superficie, y la escala de área para ese
   camino ya era 1.0.
2. **Inventario de clases, ahora completo, no una lista fija.** Antes solo se
   contaban 9 clases predefinidas (`IfcSpace`, `IfcWall`...); contra un IFC
   real de terceros (`Building-Structural.ifc`, exportado por software
   comercial) casi la mitad de sus elementos (`IfcBuildingElementProxy`,
   `IfcFooting`, `IfcRoof`, `IfcChimney`, `IfcDiscreteAccessory`) quedaban
   completamente invisibles -- ni siquiera aparecían como "0". Ahora se cuenta
   cada clase que existe de verdad en el modelo (`_conteo_por_clase`).
3. **Plantas con elevación declarada, sitio con coordenadas geográficas
   declaradas, puertas/ventanas con ancho y alto declarados.** Las tres son
   datos que IFC ya trae como atributos directos (no geometría a teselar): el
   mismo criterio de "declarado o `None` con motivo" que ya regía para
   superficies se extiende a estos tres.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import ifcopenshell
    import ifcopenshell.util.element as _elemento
    import ifcopenshell.util.unit as _unidad
except ImportError:  # pragma: no cover - mismo patrón que el resto del repositorio
    ifcopenshell = None  # type: ignore[assignment]
    _elemento = None  # type: ignore[assignment]
    _unidad = None  # type: ignore[assignment]

#: Dónde declara IFC la superficie/volumen útil de un espacio. Si no está ahí,
#: no está.
CONJUNTO_DE_CANTIDADES = "Qto_SpaceBaseQuantities"
CANTIDAD_SUPERFICIE = "NetFloorArea"
CANTIDAD_VOLUMEN = "NetVolume"

#: Las dos clases de hueco cuyo ancho/alto se lee como atributo directo del
#: propio elemento (`OverallWidth`/`OverallHeight`), no de una cantidad ni de
#: la geometría del hueco.
CLASES_ABERTURA: Tuple[str, ...] = ("IfcDoor", "IfcWindow")


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
    volumen_m3: Optional[float] = None
    motivo_sin_volumen: str = ""

    def a_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "identificador": self.identificador,
            "planta": self.planta,
            "uso": self.uso,
            "superficie_m2": self.superficie_m2,
            "motivo_sin_superficie": self.motivo_sin_superficie,
            "volumen_m3": self.volumen_m3,
            "motivo_sin_volumen": self.motivo_sin_volumen,
        }


@dataclass(frozen=True)
class PlantaIFC:
    """Un `IfcBuildingStorey`: su nombre y su elevación, si el fichero la declara."""

    nombre: str
    elevacion_m: Optional[float] = None

    def a_dict(self) -> dict:
        return {"nombre": self.nombre, "elevacion_m": self.elevacion_m}


@dataclass(frozen=True)
class AberturaIFC:
    """Una puerta o ventana tal como el fichero declara sus dimensiones.

    `OverallWidth`/`OverallHeight` son atributos directos del propio
    `IfcDoor`/`IfcWindow` en el esquema IFC -- no un Pset, no una cantidad, no
    algo medido de la geometría del hueco. Es el mismo tipo de dato que un
    fabricante de carpintería declararía en su ficha. Mismo criterio que el
    resto del módulo: si el fichero no lo declara (o no es numérico), `None`
    con motivo.
    """

    nombre: str
    identificador: str
    tipo: str                           # "IfcDoor" | "IfcWindow"
    planta: Optional[str] = None
    ancho_m: Optional[float] = None
    alto_m: Optional[float] = None
    motivo_sin_dimension: str = ""

    def a_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "identificador": self.identificador,
            "tipo": self.tipo,
            "planta": self.planta,
            "ancho_m": self.ancho_m,
            "alto_m": self.alto_m,
            "motivo_sin_dimension": self.motivo_sin_dimension,
        }


@dataclass(frozen=True)
class SitioIFC:
    """Un `IfcSite`: sus coordenadas geográficas y su cota, si el fichero las declara.

    Un proyecto puede declarar más de un `IfcSite` (visto en un IFC real de
    terceros: uno de "entorno" y uno del edificio propiamente dicho) -- este
    módulo no adivina cuál es "el" sitio, devuelve todos los que declara el
    fichero y quien lo consuma decide.
    """

    nombre: str
    identificador: str
    latitud_grados: Optional[float] = None
    longitud_grados: Optional[float] = None
    elevacion_m: Optional[float] = None

    def a_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "identificador": self.identificador,
            "latitud_grados": self.latitud_grados,
            "longitud_grados": self.longitud_grados,
            "elevacion_m": self.elevacion_m,
        }


@dataclass(frozen=True)
class InventarioIFC:
    """Lo que hay en el fichero, y lo que el fichero no dice."""

    esquema: str
    proyecto: Optional[str] = None
    plantas: Tuple[str, ...] = field(default_factory=tuple)
    plantas_detalle: Tuple[PlantaIFC, ...] = field(default_factory=tuple)
    espacios: Tuple[EspacioIFC, ...] = field(default_factory=tuple)
    aberturas: Tuple[AberturaIFC, ...] = field(default_factory=tuple)
    sitios: Tuple[SitioIFC, ...] = field(default_factory=tuple)
    conteo_por_clase: Dict[str, int] = field(default_factory=dict)
    escala_longitud: float = 1.0
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
    def volumen_declarado_m3(self) -> Optional[float]:
        """Suma de los volúmenes **declarados**. `None` si no hay ninguno. Mismo
        criterio que `superficie_declarada_m2`: nunca 0.0 por defecto."""
        declarados = [e.volumen_m3 for e in self.espacios if e.volumen_m3 is not None]
        return round(sum(declarados), 3) if declarados else None

    @property
    def espacios_sin_superficie(self) -> Tuple[str, ...]:
        return tuple(e.nombre for e in self.espacios if e.superficie_m2 is None)

    def a_dict(self) -> dict:
        return {
            "esquema": self.esquema,
            "proyecto": self.proyecto,
            "plantas": list(self.plantas),
            "plantas_detalle": [p.a_dict() for p in self.plantas_detalle],
            "espacios": [e.a_dict() for e in self.espacios],
            "aberturas": [a.a_dict() for a in self.aberturas],
            "sitios": [s.a_dict() for s in self.sitios],
            "conteo_por_clase": dict(self.conteo_por_clase),
            "escala_longitud": self.escala_longitud,
            "superficie_declarada_m2": self.superficie_declarada_m2,
            "volumen_declarado_m3": self.volumen_declarado_m3,
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

    escalas, aviso_escalas = _escalas_unidad(modelo)
    if aviso_escalas:
        avisos.append(aviso_escalas)
    elif escalas.longitud != 1.0 or escalas.area != 1.0 or escalas.volumen != 1.0:
        avisos.append(
            "el proyecto declara sus unidades a razón de %.6g m/unidad de longitud, "
            "%.6g m²/unidad de área y %.6g m³/unidad de volumen; todas las magnitudes "
            "de este inventario ya están convertidas a metros/m²/m³"
            % (escalas.longitud, escalas.area, escalas.volumen)
        )

    proyectos = modelo.by_type("IfcProject")
    proyecto = proyectos[0].Name if proyectos else None
    if not proyectos:
        avisos.append(
            "el fichero no declara IfcProject: no es un modelo IFC completo, aunque "
            "se haya podido abrir"
        )

    plantas_detalle = tuple(
        _leer_planta(p, escalas) for p in modelo.by_type("IfcBuildingStorey")
    )
    plantas = tuple(p.nombre for p in plantas_detalle)

    espacios = tuple(_leer_espacio(e, escalas, avisos) for e in modelo.by_type("IfcSpace"))
    if not espacios:
        avisos.append(
            "el modelo no contiene ningún IfcSpace: no se puede decir nada de sus "
            "superficies ni de su programa"
        )

    aberturas = tuple(
        _leer_abertura(a, escalas, avisos)
        for clase in CLASES_ABERTURA
        for a in modelo.by_type(clase)
    )

    sitios = tuple(_leer_sitio(s, escalas) for s in modelo.by_type("IfcSite"))

    return InventarioIFC(
        esquema=getattr(modelo, "schema", "desconocido"),
        proyecto=proyecto,
        plantas=plantas,
        plantas_detalle=plantas_detalle,
        espacios=espacios,
        aberturas=aberturas,
        sitios=sitios,
        conteo_por_clase=_conteo_por_clase(modelo, avisos),
        escala_longitud=escalas.longitud,
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


@dataclass(frozen=True)
class _Escalas:
    """Los tres factores de conversión a SI que este módulo necesita.

    **No son `longitud`, `longitud**2` y `longitud**3`.** Verificado contra
    los tres IFC reales de terceros usados para esta ampliación y contra el
    propio `analyzer/ifc_export.py`: los cuatro declaran la longitud en
    milímetros (`escala_longitud = 0.001`) pero el área y el volumen como
    unidades SI **independientes y ya en metros** (`escala_area =
    escala_volumen = 1`) -- no derivadas de la longitud al cuadrado/cubo. Es
    el uso estándar de IFC (`IfcUnitAssignment` declara `AREAUNIT`/
    `VOLUMEUNIT` aparte de `LENGTHUNIT`), no una rareza de un fichero
    concreto. Elevar la escala de longitud al cuadrado habría dado una
    superficie 1.000.000 de veces menor que la real en los cuatro ficheros
    probados -- se descubrió precisamente comparando esta ampliación contra
    ellos, no por inspección de código.
    """

    longitud: float = 1.0
    area: float = 1.0
    volumen: float = 1.0


def _escalas_unidad(modelo) -> Tuple[_Escalas, Optional[str]]:
    """Los tres factores de conversión a SI, y un aviso si alguno no se ha
    podido determinar con seguridad (nunca se asume una unidad rara: ante la
    duda, se asume metros/m²/m³ y se dice explícitamente que se ha asumido).

    Confirmado como una corrección real, no defensiva: `get_psets()` y los
    atributos de longitud del propio IFC (`Elevation`, `OverallWidth`...)
    vienen en la unidad que el proyecto declare para cada magnitud -- casi
    siempre milímetros para longitud en ficheros reales -- y sin este factor
    cualquier magnitud leída de un IFC no-métrico saldría equivocada por el
    factor de escala, silenciosamente.
    """
    if _unidad is None:  # pragma: no cover - mismo patrón que el resto del módulo
        return _Escalas(), (
            "no se pudo determinar las unidades del proyecto (ifcopenshell.util.unit "
            "no disponible); se asumen metros/m²/m³"
        )

    def _una(tipo: str) -> Tuple[float, bool]:
        try:
            valor = _unidad.calculate_unit_scale(modelo, tipo)
        except Exception:  # noqa: BLE001 - un proyecto sin esa unidad no tumba el inventario
            return 1.0, True
        if not valor or valor <= 0:
            return 1.0, True
        return float(valor), False

    l, l_fallo = _una("LENGTHUNIT")
    a, a_fallo = _una("AREAUNIT")
    v, v_fallo = _una("VOLUMEUNIT")

    if l_fallo or a_fallo or v_fallo:
        fallidas = [n for n, f in (("longitud", l_fallo), ("área", a_fallo), ("volumen", v_fallo)) if f]
        return _Escalas(l, a, v), (
            "no se pudo determinar con seguridad la unidad de %s del proyecto; se "
            "asume metros/m²/m³ para esa magnitud" % " y ".join(fallidas)
        )
    return _Escalas(l, a, v), None


def _longitud_o_none(valor_crudo, escala: float) -> Optional[float]:
    """Un atributo de longitud (`Elevation`, `OverallWidth`, `OverallHeight`)
    ya convertido a metros SI, o `None` si no está declarado o no es numérico.
    """
    if valor_crudo is None:
        return None
    try:
        # `or 0.0` normaliza el -0.0 que deja el redondeo de ruido de punto
        # flotante (visto de verdad en `Elevation` de un IFC real) -- un
        # arquitecto leyendo "-0.0" de elevación se preguntaría qué significa
        # el signo; no significa nada, es ruido, así que no se muestra.
        return round(float(valor_crudo) * escala, 6) or 0.0
    except (TypeError, ValueError):
        return None


def _grados_decimales(compuesto) -> Optional[float]:
    """`IfcCompoundPlaneAngleMeasure` (grados, minutos, segundos[, millonésimas
    de segundo]) a grados decimales. `None` si el fichero no lo declara.

    El signo lo lleva el primer componente no-cero, tal como define el
    esquema IFC -- no siempre son los grados (un punto justo en el ecuador o
    en el meridiano de referencia podría llevar el signo en los minutos).
    """
    if not compuesto:
        return None
    try:
        valores = [float(v) for v in compuesto]
    except (TypeError, ValueError):
        return None
    if not valores:
        return None

    signo = 1.0
    for v in valores:
        if v != 0:
            signo = -1.0 if v < 0 else 1.0
            break

    grados, minutos, segundos, milesimas = (valores + [0.0, 0.0, 0.0, 0.0])[:4]
    decimal = (
        abs(grados)
        + abs(minutos) / 60.0
        + abs(segundos) / 3600.0
        + abs(milesimas) / 3_600_000_000.0
    )
    return round(signo * decimal, 8)


def _conteo_por_clase(modelo, avisos: List[str]) -> Dict[str, int]:
    """Cuántas instancias hay de cada clase relevante -- todas las que existan
    de verdad en el modelo, no una lista fija predefinida.

    Antes esto contaba solo 9 clases elegidas a mano. Verificado contra un IFC
    real de terceros que casi la mitad de sus elementos vivían en clases fuera
    de esa lista (`IfcBuildingElementProxy`, `IfcFooting`, `IfcRoof`...) y
    quedaban invisibles en el inventario -- ni siquiera aparecían como "0",
    directamente no se sabía que existían. Ahora se cuenta cada `IfcSpace`,
    `IfcBuildingStorey` y `IfcSite` (estructura espacial) y cada subclase
    distinta de `IfcElement` presente de verdad en el modelo.
    """
    conteo: Dict[str, int] = {}
    for clase in ("IfcSpace", "IfcBuildingStorey", "IfcSite"):
        try:
            n = len(modelo.by_type(clase))
        except Exception:  # noqa: BLE001 - una clase ausente del esquema no es un error
            n = 0
        if n:
            conteo[clase] = n

    try:
        elementos = modelo.by_type("IfcElement")
    except Exception as exc:  # noqa: BLE001 - un esquema exótico no tumba el inventario
        avisos.append(
            "no se ha podido enumerar IfcElement en este modelo (%s); el "
            "inventario de elementos puede estar incompleto" % type(exc).__name__
        )
        elementos = ()
    for elemento in elementos:
        try:
            clase = elemento.is_a()
        except Exception:  # noqa: BLE001 - una instancia rota no tumba el resto del conteo
            clase = "(clase ilegible)"
        conteo[clase] = conteo.get(clase, 0) + 1

    return conteo


def _leer_espacio(espacio, escalas: "_Escalas", avisos: List[str]) -> EspacioIFC:
    nombre = (getattr(espacio, "Name", None) or "(espacio sin nombre)").strip()
    superficie, motivo_superficie = _cantidad_declarada(espacio, CANTIDAD_SUPERFICIE, escalas.area, "la")
    volumen, motivo_volumen = _cantidad_declarada(espacio, CANTIDAD_VOLUMEN, escalas.volumen, "lo")
    if superficie is None and motivo_superficie:
        avisos.append("«%s»: %s" % (nombre, motivo_superficie))
    return EspacioIFC(
        nombre=nombre,
        identificador=getattr(espacio, "GlobalId", "") or "",
        planta=_planta_de(espacio),
        uso=(getattr(espacio, "LongName", None) or None),
        superficie_m2=superficie,
        motivo_sin_superficie=motivo_superficie,
        volumen_m3=volumen,
        motivo_sin_volumen=motivo_volumen,
    )


def _cantidad_declarada(espacio, cantidad: str, factor: float, pronombre: str) -> Tuple[Optional[float], str]:
    """Una cantidad de `Qto_SpaceBaseQuantities` (superficie o volumen), ya
    convertida a unidades SI, o el motivo de que no esté declarada.

    Nunca se calcula a partir de la geometría: ver el docstring del módulo.
    `factor` es `escalas.area` o `escalas.volumen` -- **no** la escala de
    longitud al cuadrado/cubo, ver el docstring de `_Escalas` -- las
    cantidades vienen crudas en la unidad de proyecto para esa magnitud,
    igual que cualquier otro atributo (`_escalas_unidad`). `pronombre` es
    "la" (superficie) o "lo" (volumen), solo para que el motivo se lea en
    castellano correcto.
    """
    try:
        cantidades = _elemento.get_psets(espacio, qtos_only=True) or {}
    except Exception as exc:  # noqa: BLE001 - un pset roto no tumba el inventario
        return None, "no se han podido leer sus cantidades (%s)" % type(exc).__name__

    conjunto = cantidades.get(CONJUNTO_DE_CANTIDADES) or {}
    valor = conjunto.get(cantidad)
    if valor is None:
        return None, (
            "el modelo no declara %s en %s; ArchMuse no %s calcula a partir de "
            "la geometría para no mezclar valores declarados con deducidos"
            % (cantidad, CONJUNTO_DE_CANTIDADES, pronombre)
        )
    try:
        return round(float(valor) * factor, 6), ""
    except (TypeError, ValueError):
        return None, "el valor declarado de %s no es un número: %r" % (cantidad, valor)


def _planta_de(elemento) -> Optional[str]:
    """La planta que contiene el elemento, por cualquiera de las dos vías de IFC.

    IFC4 admite dos formas de colgar un elemento de una planta y las dos se
    usan en la práctica: agregación (`IfcRelAggregates`, que es la que exige el
    esquema para espacios y la que usa `analyzer/ifc_export.py`) y contención
    espacial (`IfcRelContainedInSpatialStructure`, frecuente en modelos
    exportados por herramientas comerciales -- es la única vía que usan
    puertas, ventanas y elementos estructurales). Mirar solo una deja media
    industria fuera, así que se miran las dos y se devuelve `None` si ninguna
    dice nada — que es distinto de decir que el elemento no tiene planta.

    Genérica a propósito: sirve igual para `IfcSpace` que para `IfcDoor`,
    `IfcWindow` o cualquier elemento estructural, porque las dos relaciones
    (`Decomposes`, `ContainedInStructure`) son atributos comunes a cualquier
    `IfcObjectDefinition`, no solo a los espacios.
    """
    for relacion in getattr(elemento, "Decomposes", ()) or ():
        contenedor = getattr(relacion, "RelatingObject", None)
        if contenedor is not None and contenedor.is_a("IfcBuildingStorey"):
            return contenedor.Name or "(planta sin nombre)"
    for relacion in getattr(elemento, "ContainedInStructure", ()) or ():
        contenedor = getattr(relacion, "RelatingStructure", None)
        if contenedor is not None and contenedor.is_a("IfcBuildingStorey"):
            return contenedor.Name or "(planta sin nombre)"
    return None


def _leer_planta(planta, escalas: "_Escalas") -> PlantaIFC:
    nombre = (getattr(planta, "Name", None) or "(planta sin nombre)").strip()
    return PlantaIFC(
        nombre=nombre,
        elevacion_m=_longitud_o_none(getattr(planta, "Elevation", None), escalas.longitud),
    )


def _leer_abertura(elemento, escalas: "_Escalas", avisos: List[str]) -> AberturaIFC:
    tipo = elemento.is_a()
    nombre = (getattr(elemento, "Name", None) or "(%s sin nombre)" % tipo).strip()
    ancho_m = _longitud_o_none(getattr(elemento, "OverallWidth", None), escalas.longitud)
    alto_m = _longitud_o_none(getattr(elemento, "OverallHeight", None), escalas.longitud)
    motivo = ""
    if ancho_m is None or alto_m is None:
        motivo = (
            "el modelo no declara OverallWidth/OverallHeight (o no son numéricos) "
            "en este elemento; ArchMuse no las calcula a partir de la geometría del hueco"
        )
        avisos.append("«%s» (%s): %s" % (nombre, tipo, motivo))
    return AberturaIFC(
        nombre=nombre,
        identificador=getattr(elemento, "GlobalId", "") or "",
        tipo=tipo,
        planta=_planta_de(elemento),
        ancho_m=ancho_m,
        alto_m=alto_m,
        motivo_sin_dimension=motivo,
    )


def _leer_sitio(sitio, escalas: "_Escalas") -> SitioIFC:
    nombre = (getattr(sitio, "Name", None) or "(sitio sin nombre)").strip()
    return SitioIFC(
        nombre=nombre,
        identificador=getattr(sitio, "GlobalId", "") or "",
        latitud_grados=_grados_decimales(getattr(sitio, "RefLatitude", None)),
        longitud_grados=_grados_decimales(getattr(sitio, "RefLongitude", None)),
        elevacion_m=_longitud_o_none(getattr(sitio, "RefElevation", None), escalas.longitud),
    )
