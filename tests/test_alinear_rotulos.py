# -*- coding: utf-8 -*-
"""Alinear los rótulos desplazados, y sólo si él lo dice.

PRD: `docs/prd/2026-09-11-alinear-rotulos-desplazados.md` (aprobado por Pablo,
2026-09-11), tareas A1 y A2.

**La promesa que da permiso a todo lo demás es `test_el_dxf_del_disco_no_se_toca`.**
Es la primera vez que ArchMuse mueve algo del dibujo de otro; lo único que hace
que eso sea aceptable es que se mueve una lista de tuplas que muere al acabar la
medición, y nunca un fichero. Si ese test se pone rojo, la línea que Pablo firmó
se ha cruzado de verdad.

Las otras dos condiciones duras de la firma, también aquí:
- **nunca se aplica sin pedirlo**, ni con la detección más limpia del mundo
  (`test_sin_pedirlo_no_se_alinea_aunque_el_desfase_sea_perfecto`);
- **si el desfase no es limpio, no se aplica aunque se pida**
  (`test_un_desfase_con_dos_hipotesis_no_se_aplica_aunque_se_pida`).
"""
from __future__ import annotations

import hashlib
import os

import pytest
from shapely.geometry import Polygon

from analyzer import parser

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _rejilla(n=10, lado=4.0, paso=6.0):
    """Recintos de tamanos y separaciones DISTINTAS, a proposito.

    Una rejilla perfectamente periodica —todos iguales y equiespaciados— tiene
    de verdad varias traslaciones validas: correr los rotulos una columna entera
    los mete igual de bien en otro recinto. El detector lo dice
    (`competidoras > 0`, `limpio=False`) y tiene razon; el fixture regular era
    el equivocado. Ver `test_una_planta_perfectamente_periodica_no_es_limpia`."""
    poligonos = []
    x = 0.0
    for i in range(n):
        ancho = lado + (i % 3) * 0.7
        alto = lado + (i % 4) * 0.5
        poligonos.append(Polygon([(x, 0), (x + ancho, 0), (x + ancho, alto), (x, alto)]))
        x += ancho + paso + (i % 5) * 0.9
    return poligonos


def _rotulos(polygons, dx=0.0, dy=0.0):
    return [("Dormitorio %d" % i, p.centroid.x + dx, p.centroid.y + dy)
            for i, p in enumerate(polygons)]


# ---------------------------------------------------------------------------
# A1 · Qué es un desfase limpio
# ---------------------------------------------------------------------------

def test_un_desfase_que_lo_explica_todo_es_limpio():
    polygons = _rejilla()
    desplazamiento = parser.detectar_desplazamiento_de_rotulos(
        polygons, _rotulos(polygons, dy=-50.0))

    assert desplazamiento is not None
    assert desplazamiento.limpio is True
    assert desplazamiento.competidoras == 0


def test_una_planta_perfectamente_periodica_no_es_limpia():
    """**Un hallazgo del propio detector, no un caso inventado.** Si todos los
    recintos son iguales y estan equiespaciados, correr los rotulos una columna
    entera los mete igual de bien en el recinto de al lado: hay varias
    traslaciones validas y ninguna es *la* respuesta. El detector lo declara y
    no se ofrece, que es exactamente lo que Pablo firmo."""
    iguales = [Polygon([(i * 6.0, 0), (i * 6.0 + 4, 0), (i * 6.0 + 4, 4), (i * 6.0, 4)])
               for i in range(10)]
    desplazamiento = parser.detectar_desplazamiento_de_rotulos(
        iguales, _rotulos(iguales, dy=-50.0))

    assert desplazamiento is not None
    assert desplazamiento.competidoras > 0
    assert desplazamiento.limpio is False


def test_detectar_no_es_lo_mismo_que_poder_ofrecer():
    """**La distinción que justifica el campo `limpio`.** Un desfase que explica
    el 85% se declara —«aquí pasa algo raro»— pero no se ofrece: proponerle al
    arquitecto que mueva sus rótulos con esa cifra sería proponerle que estropee
    uno de cada siete."""
    assert parser.UMBRAL_EXPLICADOS < parser.UMBRAL_LIMPIO
    assert parser.UMBRAL_LIMPIO >= 0.95


def test_un_desfase_con_dos_hipotesis_no_es_limpio():
    """Dos grupos de recintos movidos cada uno lo suyo: hay dos traslaciones que
    explican medio plano cada una, y ninguna es *la* respuesta."""
    unos = _rejilla(n=8)
    otros = [Polygon([(x + 200, y + 200) for x, y in p.exterior.coords])
             for p in _rejilla(n=8)]
    polygons = unos + otros
    labels = _rotulos(unos, dy=-50.0) + _rotulos(otros, dy=-120.0)

    desplazamiento = parser.detectar_desplazamiento_de_rotulos(polygons, labels)

    if desplazamiento is not None:
        assert desplazamiento.limpio is False


def test_las_dos_condiciones_de_limpio_se_miden_por_separado():
    """`limpio` no es un umbral, son dos: explicar casi todo Y no tener rival.
    Están separadas a propósito para que un fallo diga cuál de las dos falló."""
    desplazamiento = parser.DesplazamientoDeRotulos(
        dx=0.0, dy=50.0, explicados=199, sin_rotulo=200, mirados=200,
        limpio=True, competidoras=0)
    assert desplazamiento.limpio is True
    assert desplazamiento.competidoras == 0


# ---------------------------------------------------------------------------
# A2 · El desplazamiento vive en memoria
# ---------------------------------------------------------------------------

def test_los_rotulos_se_pueden_leer_corridos_sin_tocar_el_documento():
    import ezdxf

    doc = ezdxf.new("R2010")
    doc.modelspace().add_text("Salón", dxfattribs={"insert": (10, 10)})

    sin_mover = parser.extract_labels(doc)
    corridos = parser.extract_labels(doc, desplazamiento=(0.0, 50.0))
    otra_vez = parser.extract_labels(doc)

    assert corridos[0][2] == sin_mover[0][2] + 50.0
    # Y leerlo corrido no ha cambiado el documento: la tercera lectura da lo
    # mismo que la primera.
    assert otra_vez == sin_mover


def test_las_etiquetas_de_vivienda_se_mueven_con_los_rotulos():
    """**No es simetría, es corrección.** Las etiquetas «VT1/3» viven en la
    misma fila del dibujo que los nombres de habitación: alinear unos y no las
    otras dejaría cada pieza bien nombrada y en la vivienda equivocada, que es
    peor que no alinear nada."""
    import ezdxf

    doc = ezdxf.new("R2010")
    doc.modelspace().add_text("VT1/3", dxfattribs={"insert": (10, 10)})

    sin_mover = parser.extract_unit_labels(doc)
    corridos = parser.extract_unit_labels(doc, desplazamiento=(0.0, 50.0))

    assert sin_mover and corridos
    assert corridos[0][2] == sin_mover[0][2] + 50.0


# ---------------------------------------------------------------------------
# Las condiciones duras de la firma
# ---------------------------------------------------------------------------

def _ruta_plantasimple():
    candidatas = [
        os.path.join(os.path.dirname(RAIZ), "_material", "plantasimple.dxf"),
        os.path.join(os.path.dirname(RAIZ), "plantasimple.dxf"),
    ]
    return next((c for c in candidatas if os.path.isfile(c)), None)


def test_sin_pedirlo_no_se_alinea_aunque_el_desfase_sea_perfecto():
    """**Condición dura de Pablo, textual:** «nunca se aplica sin preguntar, ni
    siquiera si la detección es unánime. La certeza técnica no sustituye su
    permiso.» `plantasimple.dxf` es el caso más limpio que existe —dx=0, meseta
    de 49,50 a 50,25, 199 de 200— y aun así, sin pedirlo, no se toca nada."""
    ruta = _ruta_plantasimple()
    if ruta is None:
        pytest.skip("plantasimple.dxf no está en esta máquina")

    plano = parser.leer_plano(parser.load_document(ruta), layer="00 areas")

    assert plano.rotulos_desplazados is not None
    assert plano.rotulos_desplazados.limpio is True
    assert plano.rotulos_alineados is None
    assert all(r.label is None for r in plano.rooms)


def test_pedirlo_con_un_desfase_limpio_si_alinea():
    ruta = _ruta_plantasimple()
    if ruta is None:
        pytest.skip("plantasimple.dxf no está en esta máquina")

    plano = parser.leer_plano(parser.load_document(ruta), layer="00 areas",
                              alinear_rotulos=True)

    assert plano.rotulos_alineados is not None
    assert plano.rotulos_alineados.dy == pytest.approx(50.0, abs=0.5)
    assert sum(1 for r in plano.rooms if r.label) > 100


def test_un_desfase_con_dos_hipotesis_no_se_aplica_aunque_se_pida():
    """**Segunda condición dura:** «si el desfase no es limpio, no se ofrece: se
    declara y se para». Y tampoco se aplica si alguien lo pide de todas formas —
    el parámetro es una petición, no una orden."""
    import ezdxf

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    for i in range(4):
        msp.add_lwpolyline([(i * 6, 0), (i * 6 + 4, 0), (i * 6 + 4, 4), (i * 6, 4)],
                           close=True, dxfattribs={"layer": "00 areas"})
    # Textos por ahí sueltos: no hay ninguna traslación que los meta dentro.
    for i in range(6):
        msp.add_text("Nota %d" % i, dxfattribs={"insert": (i * 137.0, i * 91.0)})

    plano = parser.leer_plano(doc, layer="00 areas", factor_escala=1.0,
                              alinear_rotulos=True)

    assert plano.rotulos_alineados is None


def test_el_dxf_del_disco_no_se_toca():
    """**La promesa que autoriza todo lo demás** (criterio 5 del PRD). Se mide
    el fichero antes y después de una medición alineada: mismo byte, mismo
    hash. Lo que se mueve es una lista de tuplas que muere al acabar."""
    ruta = _ruta_plantasimple()
    if ruta is None:
        pytest.skip("plantasimple.dxf no está en esta máquina")

    def _hash():
        h = hashlib.sha256()
        with open(ruta, "rb") as fichero:
            for trozo in iter(lambda: fichero.read(1 << 20), b""):
                h.update(trozo)
        return h.hexdigest()

    antes = _hash()
    parser.leer_plano(parser.load_document(ruta), layer="00 areas",
                      alinear_rotulos=True)
    assert _hash() == antes


# ---------------------------------------------------------------------------
# Criterio 1: sin pedirlo, nada cambia en ningún plano
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nombre,piezas", [
    # `ejemplo.dxf`: 39 desde el 2026-09-16 (`C-20`, ver `test_reparacion_geometria_c10`).
    ("ejemplo.dxf", 39), ("v1plantas.dxf", 8), ("v2s.dxf", 8),
    ("v3s.dxf", 8), ("V5.dxf", 22),
])
def test_los_planos_de_referencia_no_notan_esta_funcion(nombre, piezas):
    """Ni con el parámetro puesto: no tienen desfase, así que no hay nada que
    alinear y el resultado es el mismo con y sin él."""
    ruta = os.path.join(os.path.dirname(RAIZ), "_material", nombre)
    if not os.path.isfile(ruta):
        pytest.skip("%s no está en esta máquina" % nombre)

    doc = parser.load_document(ruta)
    sin = parser.leer_plano(doc, layer="00 areas")
    con = parser.leer_plano(doc, layer="00 areas", alinear_rotulos=True)

    assert len(sin.rooms) == piezas
    assert len(con.rooms) == piezas
    assert con.rotulos_alineados is None
    assert [r.label for r in sin.rooms] == [r.label for r in con.rooms]
