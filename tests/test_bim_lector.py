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

#: Tres IFC reales de terceros (no escritos por ArchMuse), ver
#: `tests/fixtures/ifc_real/README.md` para su procedencia y por qué se
#: eligió cada uno. Añadidos 2026-08-20 (paso 3 del roadmap) para que esta
#: suite deje de probar solo el round-trip sintético de `exportar_espacios_ifc`.
FIXTURES_IFC_REAL = RAIZ / "tests" / "fixtures" / "ifc_real"
IFC_ARQUITECTURA = FIXTURES_IFC_REAL / "Building-Architecture.ifc"
IFC_ESTRUCTURA = FIXTURES_IFC_REAL / "Building-Structural.ifc"
IFC_VENTANA = FIXTURES_IFC_REAL / "wall-with-opening-and-window.ifc"

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


def test_la_capacidad_sigue_retirada_del_registro():
    """Retirada el 2026-08-19 (D-12, aprobado por Pablo) y **no por estar rota**.

    Este test es el que evita que la retirada se deshaga sin querer. El dia que
    exista la Skill que la use (`OP-5`, contraste IFC-DXF), lo que hay que hacer
    es restaurar la tupla `CAPACIDADES` de `agente/herramientas/bim.py` y
    cambiar este test **en el mismo cambio que esa Skill** -- no antes.
    """
    from agente.registro import registro

    assert "bim.inventario_de_ifc" not in registro(recargar=True).ids(), (
        "bim.inventario_de_ifc ha vuelto al registro. Si es a proposito, tiene "
        "que venir con la Skill que la invoca y el entregable que la consume "
        "(criterio de la auditoria del 2026-08-19); si no, es una regresion.")


def test_la_funcion_sigue_viva_aunque_no_este_registrada(tmp_path):
    """Lo retirado es la entrada del catalogo, no el codigo: `bim/` entero sigue
    en pie y esta funcion se puede invocar desde Python. Si esto se rompiera, la
    retirada habria sido un borrado disfrazado."""
    ruta = tmp_path / "modelo.ifc"
    exportar_espacios_ifc(HABITACIONES, nombre_planta="Planta baja").write(str(ruta))

    assert inventario_de_ifc(str(ruta))["ok"] is True


# --- Contra IFC reales de terceros, no solo el round-trip sintético --------
#
# BIM-4 del backlog ("Robustez contra IFC de software real") pide justo esto:
# que el lector funcione o falle con motivo contra ficheros que ArchMuse no
# ha escrito. Ver `tests/fixtures/ifc_real/README.md` para la procedencia.

def test_lee_un_ifc_real_exportado_por_software_de_terceros_sin_romper():
    """SketchUp, no ArchMuse. Si esto falla, el PoC ya no aguanta el mundo real."""
    inventario = inventariar(IFC_ARQUITECTURA)

    assert inventario.esquema == "IFC4"
    assert inventario.plantas == ("00 groundfloor",)
    assert {e.nombre for e in inventario.espacios} == {"living room", "entry hall"}
    assert inventario.conteo_por_clase["IfcWall"] == 4
    assert inventario.conteo_por_clase["IfcSlab"] == 3


def test_el_inventario_de_clases_no_deja_invisible_lo_que_no_estaba_en_la_lista_fija():
    """El hallazgo central de esta ampliación: antes, solo 9 clases contaban.

    Contra este fichero real, `IfcBuildingElementProxy`, `IfcFooting`,
    `IfcRoof`, `IfcChimney` y `IfcDiscreteAccessory` no estaban en la lista
    fija anterior -- con el inventario dinámico, aparecen todas.
    """
    inventario = inventariar(IFC_ESTRUCTURA)

    assert inventario.conteo_por_clase["IfcBeam"] == 6
    assert inventario.conteo_por_clase["IfcBuildingElementProxy"] == 3
    assert inventario.conteo_por_clase["IfcFooting"] == 1
    assert inventario.conteo_por_clase["IfcRoof"] == 1
    assert inventario.conteo_por_clase["IfcChimney"] == 1
    assert inventario.conteo_por_clase["IfcDiscreteAccessory"] == 2
    # Este fichero no tiene ningún IfcSpace: el aviso lo dice, no se calla.
    assert any("ningún IfcSpace" in a for a in inventario.avisos)


def test_las_unidades_de_un_ifc_real_en_milimetros_se_convierten_a_metros():
    """El bug real que motivó esta ampliación: sin corregir, esto saldría
    1000 (longitud) o 1.000.000 (superficie, si se hubiera elevado al
    cuadrado la escala de longitud en vez de leer AREAUNIT aparte) veces
    distinto de lo real."""
    inventario = inventariar(IFC_ARQUITECTURA)

    assert inventario.escala_longitud == pytest.approx(0.001)
    assert any("0.001 m/unidad de longitud" in a for a in inventario.avisos)


def test_lee_una_ventana_real_con_ancho_y_alto_declarados():
    """`OverallWidth`/`OverallHeight` son atributos directos del `IfcWindow`,
    no una cantidad ni geometría teselada -- 1000mm declarados en el fichero,
    deben leerse como 1.0 m, no como 1000 (bug de unidades) ni como `None`
    (el fichero SÍ los declara)."""
    inventario = inventariar(IFC_VENTANA)

    assert len(inventario.aberturas) == 1
    ventana = inventario.aberturas[0]
    assert ventana.tipo == "IfcWindow"
    assert ventana.ancho_m == pytest.approx(1.0)
    assert ventana.alto_m == pytest.approx(1.0)
    assert ventana.motivo_sin_dimension == ""
    assert ventana.planta == "Default Building Storey"


def test_lee_el_sitio_real_con_coordenadas_geograficas_declaradas():
    """`RefLatitude`/`RefLongitude` son `IfcCompoundPlaneAngleMeasure`
    (grados, minutos, segundos) -- (24, 28, 0) tiene que dar 24 + 28/60,
    no 24.28 ni 24.0."""
    inventario = inventariar(IFC_VENTANA)

    assert len(inventario.sitios) == 1
    sitio = inventario.sitios[0]
    assert sitio.latitud_grados == pytest.approx(24 + 28 / 60)
    assert sitio.longitud_grados == pytest.approx(54 + 25 / 60)
    assert sitio.elevacion_m is not None


def test_un_sitio_sin_coordenadas_declaradas_no_inventa_ninguna():
    """`Building-Architecture.ifc` tiene dos `IfcSite` (uno de "entorno", uno
    del edificio) y ninguno declara lat/lon -- los dos deben salir `None`,
    nunca 0.0 (0°,0° es un punto real del planeta, no "sin dato")."""
    inventario = inventariar(IFC_ARQUITECTURA)

    assert len(inventario.sitios) == 2
    for sitio in inventario.sitios:
        assert sitio.latitud_grados is None
        assert sitio.longitud_grados is None


def test_una_planta_real_declara_su_elevacion_sin_ruido_de_punto_flotante():
    """El ruido de punto flotante de un IFC real (`Elevation` casi-cero pero
    no exactamente 0.0) no debe colarse como "-0.0" -- se normaliza a 0.0."""
    inventario = inventariar(IFC_ARQUITECTURA)

    assert len(inventario.plantas_detalle) == 1
    elevacion = inventario.plantas_detalle[0].elevacion_m
    assert elevacion == 0.0
    assert str(elevacion) != "-0.0"


def test_tres_ifc_de_origen_distinto_se_leen_o_fallan_con_motivo_nunca_con_un_numero_inventado():
    """BIM-4, criterio de terminado literal: tres IFC de origen distinto se
    leen o fallan con `ok=False` y motivo -- nunca con un número inventado."""
    for ruta in (IFC_ARQUITECTURA, IFC_ESTRUCTURA, IFC_VENTANA):
        resultado = inventario_de_ifc(str(ruta))
        assert resultado["ok"] is True
        assert resultado["esquema"] == "IFC4"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
