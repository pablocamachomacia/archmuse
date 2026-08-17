# -*- coding: utf-8 -*-
"""Fase 1 del contrato de clasificación DXF: capas `AM_UTIL_INT`/`AM_CONS_CER`
operativas, inventario de geometría no leída, y `Unit.envolvente_cerrada`.

Ejecutar:  python -m pytest tests/test_capas_am.py -v

Diseño de referencia: informe de arquitectura de esta misma sesión
("Nueva fase ArchMuse — contrato de clasificación de superficies DXF") y su
Fase 1 ("implementar Fase 1 del contrato de clasificación DXF").

Qué protege, en el orden en que aparecen los tests:

1. Un DXF sin ninguna capa `AM_*` se comporta exactamente igual que antes de
   esta fase (modo heredado intacto).
2. `AM_UTIL_INT` con una polilínea válida se lee como recinto, SIN pasar por
   `_resolver_capa`/modo heredado en absoluto.
3. `AM_CONS_CER` se lee como envolvente, nunca como `Room` -- ni cuenta en
   `n_habitaciones`/`total_area_m2`, ni aparece en `Unit.rooms`.
4. Geometría inválida (autointersección) en una capa `AM_*` no entra en el
   resultado y queda en el inventario, con `GEOMETRIA_INVALIDA` y el detalle
   de `explain_validity`.
5. Una entidad de tipo no soportado (aquí, LINE) en una capa `AM_*` se
   inventaría con `TIPO_NO_SOPORTADO`.
6. Una polilínea genuinamente abierta en una capa `AM_*` se inventaría con
   `POLILINEA_ABIERTA` -- y NO se recupera (a diferencia del caso 7).
7. Una polilínea con `closed=False` pero extremos coincidentes SÍ se
   recupera en una capa `AM_*`, reutilizando `_esta_cerrada`/
   `_extremos_coinciden` de `tests/test_cierre_recuperado.py` sin
   reimplementar nada.
8. Un recinto dentro de un bloque, en capa "0", con el INSERT en `AM_UTIL_INT`,
   se lee correctamente -- se conserva `_capa_efectiva` sin tocarla.
9. Capas parcialmente presentes: solo `AM_CONS_CER` (recintos de "00 areas",
   envolvente de la capa AM) y solo `AM_UTIL_INT` (recintos de la capa AM,
   sin envolvente) se comportan cada una de forma definida y distinta.

Al final, dos bloques más:

- El inventario de descartes también funciona en modo heredado (parte
  explícita del alcance de la Fase 1: "incluso en modo heredado"), sin que
  eso excluya del resultado nada que hoy SÍ se acepta como `Room` -- el modo
  heredado no valida `is_valid`, a propósito (ver docstring de
  `_closed_polygons_with_color`).
- `asignar_envolvente_cerrada` (evaluator.py): emparejamiento por etiqueta
  VT, y los dos casos que se dejan sin resolver a propósito (sin
  `unit_labels`; más de una envolvente para la misma vivienda).
"""
from __future__ import annotations

import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import ezdxf  # noqa: E402
from shapely.geometry import Polygon, box  # noqa: E402

from analyzer import evaluator, parser  # noqa: E402

LOGGER = "analyzer.parser"


# ---------------------------------------------------------------------------
# Helpers de construcción, mismo estilo que tests/test_bloques.py y
# tests/test_capas.py: ezdxf.new() en memoria, sin guardar a disco salvo
# donde hace falta (bloques, que sí se prueban ya guardados en otros tests).
# ---------------------------------------------------------------------------


def _doc_vacio(*capas):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6  # metros
    for capa in capas:
        doc.layers.add(capa)
    return doc


def _rect(msp, capa, x0, y0, ancho, alto, etiqueta=None, closed=True):
    pts = [(x0, y0), (x0 + ancho, y0), (x0 + ancho, y0 + alto), (x0, y0 + alto)]
    msp.add_lwpolyline(pts, close=closed, dxfattribs={"layer": capa})
    if etiqueta:
        msp.add_mtext(etiqueta, dxfattribs={"layer": capa}).set_location(
            (x0 + ancho / 2, y0 + alto / 2)
        )


# ---------------------------------------------------------------------------
# 1. Sin capas AM_*: modo heredado intacto
# ---------------------------------------------------------------------------


def test_sin_capas_am_comportamiento_heredado():
    doc = _doc_vacio(parser.AREA_LAYER)
    msp = doc.modelspace()
    # >= MINIMO_POLIGONOS_CAPA (3): para que "00 areas" sea reconocible como
    # capa candidata por `capas_candidatas` y no dispare CapaIndeterminada.
    _rect(msp, parser.AREA_LAYER, 0, 0, 6, 4, "Salón/cocina")
    _rect(msp, parser.AREA_LAYER, 7, 0, 4, 3, "Dormitorio 1")
    _rect(msp, parser.AREA_LAYER, 12, 0, 3, 3, "Baño")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.AREA_LAYER}).set_location((-3, 2))

    plano = parser.leer_plano(doc)

    assert plano.layer == parser.AREA_LAYER
    assert len(plano.rooms) == 3
    assert {r.label for r in plano.rooms} == {"Salón/cocina", "Dormitorio 1", "Baño"}
    assert plano.envolventes_cerradas == []
    assert plano.geometria_no_leida == []
    assert plano.capa is not None and plano.capa.nombre == parser.AREA_LAYER


# ---------------------------------------------------------------------------
# 2. AM_UTIL_INT con polilínea válida -> recinto leído
# ---------------------------------------------------------------------------


def test_am_util_int_valida_se_lee_como_recinto():
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))

    plano = parser.leer_plano(doc)

    assert plano.layer == parser.CAPA_UTIL_INTERIOR
    assert len(plano.rooms) == 1
    assert plano.rooms[0].label == "Salón/cocina"
    assert round(plano.rooms[0].area_m2, 2) == 24.0
    # No se ha pasado por _resolver_capa/modo heredado: no hay CapaCandidata.
    assert plano.capa is None


# ---------------------------------------------------------------------------
# 3. AM_CONS_CER con polilínea válida -> envolvente separada de rooms
# ---------------------------------------------------------------------------


def test_am_cons_cer_valida_es_envolvente_no_room():
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, parser.CAPA_CONSTRUIDA_CERRADA)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))
    _rect(msp, parser.CAPA_CONSTRUIDA_CERRADA, -0.3, -0.3, 6.6, 4.6)  # envolvente, algo mayor

    plano = parser.leer_plano(doc)

    # La envolvente NO es un Room: sigue habiendo exactamente 1 recinto.
    assert len(plano.rooms) == 1
    assert len(plano.envolventes_cerradas) == 1
    envolvente = plano.envolventes_cerradas[0]
    assert isinstance(envolvente, Polygon)
    assert round(envolvente.area, 2) == round(6.6 * 4.6, 2)

    # Y no participa en total_area_m2 al construir la Unit.
    unidades = evaluator.group_rooms_by_unit_label(plano.rooms, plano.unit_labels)
    assert len(unidades) == 1
    assert round(unidades[0].total_area_m2, 2) == 24.0  # solo el Salón/cocina, no la envolvente
    assert unidades[0].envolvente_cerrada is None  # todavía no asignada

    con_envolvente = evaluator.asignar_envolvente_cerrada(
        unidades, plano.envolventes_cerradas, plano.unit_labels
    )
    assert con_envolvente[0].envolvente_cerrada is not None
    assert round(con_envolvente[0].envolvente_cerrada.area, 2) == round(6.6 * 4.6, 2)
    assert round(con_envolvente[0].total_area_m2, 2) == 24.0  # sigue sin cambiar


# ---------------------------------------------------------------------------
# 4. Geometría inválida en capa AM_* -> descartada e inventariada
# ---------------------------------------------------------------------------


def test_geometria_invalida_no_entra_y_se_inventaria():
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR)
    msp = doc.modelspace()
    # Poligono "pajarita" (bowtie): autointersecante, is_valid == False.
    bowtie = [(0, 0), (4, 4), (4, 0), (0, 4)]
    msp.add_lwpolyline(bowtie, close=True, dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR})

    plano = parser.leer_plano(doc)

    assert plano.rooms == []
    assert len(plano.geometria_no_leida) == 1
    descarte = plano.geometria_no_leida[0]
    assert descarte.motivo == parser.MOTIVO_GEOMETRIA_INVALIDA
    assert descarte.capa == parser.CAPA_UTIL_INTERIOR
    assert descarte.tipo == "LWPOLYLINE"
    assert descarte.detalle != ""  # explain_validity(), nunca vacio


# ---------------------------------------------------------------------------
# 5. Entidad no soportada en capa AM_* -> inventariada
# ---------------------------------------------------------------------------


def test_entidad_no_soportada_se_inventaria():
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR)
    msp = doc.modelspace()
    msp.add_line((0, 0), (4, 0), dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR})

    plano = parser.leer_plano(doc)

    assert plano.rooms == []
    assert len(plano.geometria_no_leida) == 1
    descarte = plano.geometria_no_leida[0]
    assert descarte.motivo == parser.MOTIVO_TIPO_NO_SOPORTADO
    assert descarte.tipo == "LINE"
    assert descarte.capa == parser.CAPA_UTIL_INTERIOR


# ---------------------------------------------------------------------------
# 6. Polilínea genuinamente abierta en capa AM_* -> inventariada, no recuperada
# ---------------------------------------------------------------------------


def test_polilinea_abierta_de_verdad_se_inventaria():
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR)
    msp = doc.modelspace()
    pts = [(0, 0), (4, 0), (4, 3), (0, 3), (2, 1.5)]  # ultimo vertice lejos del primero
    msp.add_lwpolyline(pts, close=False, dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR})

    plano = parser.leer_plano(doc)

    assert plano.rooms == []
    assert len(plano.geometria_no_leida) == 1
    descarte = plano.geometria_no_leida[0]
    assert descarte.motivo == parser.MOTIVO_POLILINEA_ABIERTA
    assert descarte.tipo == "LWPOLYLINE"


# ---------------------------------------------------------------------------
# 7. closed=False con extremos coincidentes -> SE RECUPERA (reutiliza el fix)
# ---------------------------------------------------------------------------


def test_cierre_recuperado_tambien_funciona_en_capa_am(caplog):
    import logging

    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR)
    msp = doc.modelspace()
    pts = [(0, 0), (6, 0), (6, 4), (0, 4), (0, 0)]  # ultimo == primero, closed=False
    msp.add_lwpolyline(pts, close=False, dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR})
    msp.add_mtext("Salón/cocina", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((3, 2))

    with caplog.at_level(logging.WARNING, logger=LOGGER):
        plano = parser.leer_plano(doc)

    assert len(plano.rooms) == 1
    assert plano.rooms[0].label == "Salón/cocina"
    assert plano.geometria_no_leida == []
    assert any("tratada como cerrada" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# 8. Bloque con herencia de capa (_capa_efectiva) hacia una capa AM_*
# ---------------------------------------------------------------------------


def test_bloque_con_herencia_de_capa_hacia_am_util_int(tmp_path):
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR)
    bloque = doc.blocks.new(name="VIVIENDA")
    # Dibujado en capa "0" DENTRO del bloque: hereda la capa del INSERT.
    _rect(bloque, "0", 0, 0, 6, 4, "Salón/cocina")
    doc.modelspace().add_blockref(
        "VIVIENDA", (0, 0), dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}
    )

    ruta = os.path.join(str(tmp_path), "bloque_am.dxf")
    doc.saveas(ruta)
    doc_cargado = parser.load_document(ruta)

    plano = parser.leer_plano(doc_cargado)

    assert len(plano.rooms) == 1
    assert plano.rooms[0].label == "Salón/cocina"
    assert round(plano.rooms[0].area_m2, 2) == 24.0


# ---------------------------------------------------------------------------
# 9. Capas parcialmente presentes
# ---------------------------------------------------------------------------


def test_solo_am_cons_cer_presente_recintos_de_heredado():
    """Sin AM_UTIL_INT: los recintos siguen viniendo del modo heredado
    ("00 areas"), y la envolvente sí sale de AM_CONS_CER."""
    doc = _doc_vacio(parser.AREA_LAYER, parser.CAPA_CONSTRUIDA_CERRADA)
    msp = doc.modelspace()
    _rect(msp, parser.AREA_LAYER, 0, 0, 6, 4, "Salón/cocina")
    _rect(msp, parser.AREA_LAYER, 7, 0, 4, 3, "Dormitorio 1")
    _rect(msp, parser.AREA_LAYER, 12, 0, 3, 3, "Baño")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.AREA_LAYER}).set_location((-3, 2))
    _rect(msp, parser.CAPA_CONSTRUIDA_CERRADA, -0.3, -0.3, 6.6, 4.6)

    plano = parser.leer_plano(doc)

    assert plano.layer == parser.AREA_LAYER  # heredado, no AM_UTIL_INT
    assert len(plano.rooms) == 3
    assert any(r.label == "Salón/cocina" for r in plano.rooms)
    assert len(plano.envolventes_cerradas) == 1


def test_solo_am_util_int_presente_sin_envolvente():
    """Sin AM_CONS_CER: hay recintos clasificados, pero ninguna envolvente."""
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))

    plano = parser.leer_plano(doc)

    assert plano.layer == parser.CAPA_UTIL_INTERIOR
    assert len(plano.rooms) == 1
    assert plano.envolventes_cerradas == []


# ---------------------------------------------------------------------------
# Inventario también en modo heredado (alcance explícito de la Fase 1),
# sin excluir del resultado lo que hoy SÍ se acepta como Room.
# ---------------------------------------------------------------------------


def test_inventario_en_modo_heredado_no_excluye_geometria_invalida():
    """El modo heredado NO valida is_valid (a proposito, ver docstring de
    `_closed_polygons_with_color`): un poligono invalido en "00 areas" sigue
    convirtiendose en Room, exactamente igual que antes de la Fase 1 -- solo
    que ahora, ademas, el tipo-no-soportado y la polilinea abierta de esa
    misma capa SI quedan inventariados."""
    doc = _doc_vacio(parser.AREA_LAYER)
    msp = doc.modelspace()
    bowtie = [(0, 0), (4, 4), (4, 0), (0, 4)]
    msp.add_lwpolyline(bowtie, close=True, dxfattribs={"layer": parser.AREA_LAYER})
    msp.add_line((10, 0), (14, 0), dxfattribs={"layer": parser.AREA_LAYER})
    pts_abierta = [(20, 0), (24, 0), (24, 3), (20, 3), (22, 1.5)]
    msp.add_lwpolyline(pts_abierta, close=False, dxfattribs={"layer": parser.AREA_LAYER})
    # Tres recintos normales, para que la capa "00 areas" sea reconocible
    # como candidata (MINIMO_POLIGONOS_CAPA = 3) y no dispare CapaIndeterminada.
    for i, nombre in enumerate(["Dormitorio 1", "Dormitorio 2", "Baño"]):
        x0 = 30.0 + i * 5
        _rect(msp, parser.AREA_LAYER, x0, 0, 3, 3, nombre)

    plano = parser.leer_plano(doc)

    # El poligono invalido SIGUE leyendose como Room: comportamiento heredado
    # intacto, no una exclusion nueva.
    assert len(plano.rooms) == 4  # bowtie + Dormitorio 1 + Dormitorio 2 + Baño
    motivos = sorted(d.motivo for d in plano.geometria_no_leida)
    assert motivos == sorted([parser.MOTIVO_TIPO_NO_SOPORTADO, parser.MOTIVO_POLILINEA_ABIERTA])
    assert all(not d.detalle or d.motivo != parser.MOTIVO_GEOMETRIA_INVALIDA
               for d in plano.geometria_no_leida)


# ---------------------------------------------------------------------------
# asignar_envolvente_cerrada: casos que se dejan sin resolver a propósito
# ---------------------------------------------------------------------------


def test_asignar_envolvente_sin_unit_labels_no_asigna_nada():
    room = parser.Room(label="Salón/cocina", polygon=box(0, 0, 6, 4), layer="AM_UTIL_INT")
    unidades = evaluator.group_rooms_by_proximity([room])  # sin etiquetas VT
    envolvente = box(-0.3, -0.3, 6.3, 4.3)

    resultado = evaluator.asignar_envolvente_cerrada(unidades, [envolvente], unit_labels=[])

    assert resultado is unidades  # se devuelve tal cual, sin tocar
    assert resultado[0].envolvente_cerrada is None


def test_asignar_envolvente_ambigua_no_elige_ninguna():
    """Dos envolventes cuyo centroide cae mas cerca de la misma etiqueta VT:
    ambigüedad real, ninguna se elige por descarte."""
    room = parser.Room(label="Salón/cocina", polygon=box(0, 0, 6, 4), layer="AM_UTIL_INT")
    unit_labels = [("VT1/1", -3.0, 2.0)]
    unidades = evaluator.group_rooms_by_unit_label([room], unit_labels)
    assert len(unidades) == 1

    envolvente_a = box(-0.3, -0.3, 6.3, 4.3)
    envolvente_b = box(-0.5, -0.5, 6.5, 4.5)  # centroide tambien mas cerca de VT1/1

    resultado = evaluator.asignar_envolvente_cerrada(
        unidades, [envolvente_a, envolvente_b], unit_labels
    )

    assert resultado[0].envolvente_cerrada is None


def test_asignar_envolvente_dos_viviendas_cada_una_la_suya():
    salon_a = parser.Room(label="Salón/cocina", polygon=box(0, 0, 6, 4), layer="AM_UTIL_INT")
    salon_b = parser.Room(label="Salón/cocina", polygon=box(20, 0, 26, 4), layer="AM_UTIL_INT")
    unit_labels = [("VT1/1", -3.0, 2.0), ("VT2/1", 17.0, 2.0)]
    unidades = evaluator.group_rooms_by_unit_label([salon_a, salon_b], unit_labels)
    assert {u.name for u in unidades} == {"VT1/1", "VT2/1"}

    envolvente_a = box(-0.3, -0.3, 6.3, 4.3)
    envolvente_b = box(19.7, -0.3, 26.3, 4.3)

    resultado = evaluator.asignar_envolvente_cerrada(
        unidades, [envolvente_a, envolvente_b], unit_labels
    )
    por_nombre = {u.name: u for u in resultado}
    assert por_nombre["VT1/1"].envolvente_cerrada is not None
    assert round(por_nombre["VT1/1"].envolvente_cerrada.area, 2) == round(6.6 * 4.6, 2)
    assert por_nombre["VT2/1"].envolvente_cerrada is not None
    assert round(por_nombre["VT2/1"].envolvente_cerrada.area, 2) == round(6.6 * 4.6, 2)


# ---------------------------------------------------------------------------
# Fase 3: AM_UTIL_EXT (superficie útil exterior) y AM_CONS_EXT (superficie
# construida exterior), operativas con el mismo patrón que AM_UTIL_INT y
# AM_CONS_CER -- nunca Room, nunca mezcladas entre categorías.
# ---------------------------------------------------------------------------


def test_am_util_ext_valida_no_es_room():
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, parser.CAPA_UTIL_EXTERIOR)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))
    _rect(msp, parser.CAPA_UTIL_EXTERIOR, 7, 0, 3, 2, "Terraza")

    plano = parser.leer_plano(doc)

    assert len(plano.rooms) == 1  # la terraza NO es un Room
    assert len(plano.superficies_utiles_exteriores) == 1
    assert round(plano.superficies_utiles_exteriores[0].area, 2) == 6.0
    assert plano.envolventes_cerradas == []
    assert plano.envolventes_exteriores == []


def test_am_cons_ext_valida_no_es_room():
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, parser.CAPA_CONSTRUIDA_EXTERIOR)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))
    _rect(msp, parser.CAPA_CONSTRUIDA_EXTERIOR, 6.9, -0.3, 3.2, 2.6)

    plano = parser.leer_plano(doc)

    assert len(plano.rooms) == 1
    assert len(plano.envolventes_exteriores) == 1
    assert round(plano.envolventes_exteriores[0].area, 2) == round(3.2 * 2.6, 2)
    assert plano.superficies_utiles_exteriores == []
    assert plano.envolventes_cerradas == []


def test_am_util_ext_y_am_cons_ext_simultaneas_no_se_mezclan():
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, parser.CAPA_UTIL_EXTERIOR,
                      parser.CAPA_CONSTRUIDA_EXTERIOR)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))
    _rect(msp, parser.CAPA_UTIL_EXTERIOR, 7, 0, 3, 2, "Terraza")  # 6 m2
    _rect(msp, parser.CAPA_CONSTRUIDA_EXTERIOR, 6.9, -0.3, 3.2, 2.6)  # 8.32 m2

    plano = parser.leer_plano(doc)

    assert len(plano.rooms) == 1
    assert len(plano.superficies_utiles_exteriores) == 1
    assert len(plano.envolventes_exteriores) == 1
    # Cada lista tiene el area que le corresponde -- no hay contaminacion
    # cruzada entre AM_UTIL_EXT y AM_CONS_EXT.
    assert round(plano.superficies_utiles_exteriores[0].area, 2) == 6.0
    assert round(plano.envolventes_exteriores[0].area, 2) == round(3.2 * 2.6, 2)


def test_geometria_invalida_en_am_util_ext_se_inventaria():
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, parser.CAPA_UTIL_EXTERIOR)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))
    bowtie = [(10, 0), (14, 4), (14, 0), (10, 4)]
    msp.add_lwpolyline(bowtie, close=True, dxfattribs={"layer": parser.CAPA_UTIL_EXTERIOR})

    plano = parser.leer_plano(doc)

    assert plano.superficies_utiles_exteriores == []
    descartes = [d for d in plano.geometria_no_leida if d.capa == parser.CAPA_UTIL_EXTERIOR]
    assert len(descartes) == 1
    assert descartes[0].motivo == parser.MOTIVO_GEOMETRIA_INVALIDA


def test_entidad_no_soportada_en_am_cons_ext_se_inventaria():
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, parser.CAPA_CONSTRUIDA_EXTERIOR)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))
    msp.add_line((10, 0), (14, 0), dxfattribs={"layer": parser.CAPA_CONSTRUIDA_EXTERIOR})

    plano = parser.leer_plano(doc)

    assert plano.envolventes_exteriores == []
    descartes = [d for d in plano.geometria_no_leida if d.capa == parser.CAPA_CONSTRUIDA_EXTERIOR]
    assert len(descartes) == 1
    assert descartes[0].motivo == parser.MOTIVO_TIPO_NO_SOPORTADO
    assert descartes[0].tipo == "LINE"


def test_coexistencia_de_las_cuatro_categorias():
    doc = _doc_vacio(
        parser.CAPA_UTIL_INTERIOR, parser.CAPA_CONSTRUIDA_CERRADA,
        parser.CAPA_UTIL_EXTERIOR, parser.CAPA_CONSTRUIDA_EXTERIOR,
    )
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))
    _rect(msp, parser.CAPA_CONSTRUIDA_CERRADA, -0.3, -0.3, 6.6, 4.6)
    _rect(msp, parser.CAPA_UTIL_EXTERIOR, 7, 0, 3, 2, "Terraza")
    _rect(msp, parser.CAPA_CONSTRUIDA_EXTERIOR, 6.9, -0.3, 3.2, 2.6)

    plano = parser.leer_plano(doc)

    assert len(plano.rooms) == 1
    assert len(plano.envolventes_cerradas) == 1
    assert len(plano.superficies_utiles_exteriores) == 1
    assert len(plano.envolventes_exteriores) == 1
    # Ninguna de las tres listas de "no-Room" se ha mezclado con otra.
    assert round(plano.envolventes_cerradas[0].area, 2) == round(6.6 * 4.6, 2)
    assert round(plano.superficies_utiles_exteriores[0].area, 2) == 6.0
    assert round(plano.envolventes_exteriores[0].area, 2) == round(3.2 * 2.6, 2)

    unidades = evaluator.group_rooms_by_unit_label(plano.rooms, plano.unit_labels)
    # Encadenadas en un orden...
    con_todo_a = evaluator.asignar_envolvente_cerrada(
        unidades, plano.envolventes_cerradas, plano.unit_labels)
    con_todo_a = evaluator.asignar_superficies_exteriores(
        con_todo_a, plano.superficies_utiles_exteriores, plano.envolventes_exteriores,
        plano.unit_labels)
    # ...y en el orden inverso: el resultado tiene que ser el mismo (ninguna
    # de las dos funciones debe borrar lo que asigno la otra).
    con_todo_b = evaluator.asignar_superficies_exteriores(
        unidades, plano.superficies_utiles_exteriores, plano.envolventes_exteriores,
        plano.unit_labels)
    con_todo_b = evaluator.asignar_envolvente_cerrada(
        con_todo_b, plano.envolventes_cerradas, plano.unit_labels)

    for resultado in (con_todo_a, con_todo_b):
        vt1 = resultado[0]
        assert vt1.envolvente_cerrada is not None
        assert len(vt1.superficies_utiles_exteriores) == 1
        assert len(vt1.envolventes_exteriores) == 1
        assert round(vt1.total_area_m2, 2) == 24.0  # solo el Salón/cocina


def test_ausencia_parcial_de_categorias_solo_am_util_ext():
    """Solo AM_UTIL_EXT presente: los recintos siguen viniendo del modo
    heredado, y las otras dos listas "no-Room" quedan vacias."""
    doc = _doc_vacio(parser.AREA_LAYER, parser.CAPA_UTIL_EXTERIOR)
    msp = doc.modelspace()
    _rect(msp, parser.AREA_LAYER, 0, 0, 6, 4, "Salón/cocina")
    _rect(msp, parser.AREA_LAYER, 7, 0, 4, 3, "Dormitorio 1")
    _rect(msp, parser.AREA_LAYER, 12, 0, 3, 3, "Baño")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.AREA_LAYER}).set_location((-3, 2))
    _rect(msp, parser.CAPA_UTIL_EXTERIOR, 20, 0, 3, 2, "Terraza")

    plano = parser.leer_plano(doc)

    assert plano.layer == parser.AREA_LAYER  # heredado, sin AM_UTIL_INT
    assert len(plano.rooms) == 3
    assert len(plano.superficies_utiles_exteriores) == 1
    assert plano.envolventes_cerradas == []
    assert plano.envolventes_exteriores == []


def test_dos_terrazas_en_la_misma_vivienda_no_es_ambiguedad():
    """A diferencia de envolvente_cerrada, dos (o mas) superficies utiles
    exteriores para la misma vivienda no se descartan por ambigüedad: se
    asignan las dos."""
    room = parser.Room(label="Salón/cocina", polygon=box(0, 0, 6, 4), layer="AM_UTIL_INT")
    unit_labels = [("VT1/1", -3.0, 2.0)]
    unidades = evaluator.group_rooms_by_unit_label([room], unit_labels)

    terraza_a = box(7, 0, 10, 2)
    terraza_b = box(7, 3, 10, 5)

    resultado = evaluator.asignar_superficies_exteriores(
        unidades, [terraza_a, terraza_b], [], unit_labels)

    assert len(resultado[0].superficies_utiles_exteriores) == 2
    assert resultado[0].envolvente_cerrada is None  # no se ha tocado
    assert round(resultado[0].total_area_m2, 2) == 24.0  # las terrazas no suman aqui


# ---------------------------------------------------------------------------
# Regresión sobre proyectos reales, si están disponibles (mismo patrón que
# tests/test_cierre_recuperado.py: no se versionan, se saltan si no están).
# ---------------------------------------------------------------------------


def _ruta_proyecto_real(nombre: str):
    candidatas = [
        os.path.join(os.path.dirname(RAIZ), nombre),
        os.path.join(os.path.expanduser("~"), "Desktop", nombre),
    ]
    return next((c for c in candidatas if os.path.isfile(c)), None)


@pytest.mark.parametrize("nombre", ["ejemplo.dxf"])
def test_regresion_dxf_real_sin_capas_am_no_cambia(nombre):
    """ejemplo.dxf no tiene ninguna capa AM_*: debe seguir leyendo
    exactamente los mismos 40 recintos de siempre (ver
    tests/test_ingesta_regresion.py), sin envolventes ni descartes AM_*."""
    ruta = _ruta_proyecto_real(nombre)
    if ruta is None:
        pytest.skip("%s no esta disponible en esta maquina" % nombre)

    plano = parser.leer_plano(parser.load_document(ruta))

    assert plano.layer == parser.AREA_LAYER
    assert len(plano.rooms) == 40
    assert plano.envolventes_cerradas == []
    assert plano.superficies_utiles_exteriores == []
    assert plano.envolventes_exteriores == []
