# -*- coding: utf-8 -*-
"""Fase 2 del contrato de clasificación DXF: validador de conformidad de las
capas `AM_*` (`analyzer/validacion_capas.py`), no bloqueante.

Ejecutar:  python -m pytest tests/test_validacion_capas_am.py -v

Qué protege, por bloque:

A. Nombres de capa "casi correctos" (typo/espacio/mayúsculas), sin
   autocorregir nada -- la capa correcta sigue sin recibir su contenido.
B. Capas reservadas (`AM_UTIL_EXT`/`AM_CONS_EXT`/`AM_DESCUENTO`) con y sin
   contenido.
C. Los tres diagnósticos de `AM_CONS_CER` (ambigua, sin vivienda, vivienda
   sin envolvente), como partición exhaustiva y sin solape.
D. Geometría descartada de una capa `AM_*` envuelta como `Diagnostico`, con
   la severidad correcta según el motivo -- reutilizando
   `PlanoLeido.geometria_no_leida`, nunca recalculándolo.
E. Regresión: un DXF puramente heredado (sin ninguna capa `AM_*`) produce
   una lista de diagnósticos VACÍA -- el validador no genera ruido sobre un
   contrato que el plano nunca ha usado.
"""
from __future__ import annotations

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import ezdxf  # noqa: E402
from shapely.geometry import box  # noqa: E402

from analyzer import evaluator, parser, validacion_capas as vc  # noqa: E402


def _doc_vacio(*capas):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
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


def _recinto_base(msp, x0=100.0):
    """Un recinto valido en AM_UTIL_INT, lejos de cualquier otra geometria
    del test: basta para que `leer_plano` tenga algo que leer (sin el, un
    documento sin ninguna capa candidata dispara CapaIndeterminada, que no
    es lo que estos tests de nombre de capa/capas reservadas quieren
    ejercitar)."""
    _rect(msp, parser.CAPA_UTIL_INTERIOR, x0, 0, 4, 3, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location(
        (x0 - 3, 1.5)
    )


def _analizar(doc):
    """`leer_plano` + agrupación en viviendas, tal cual lo haría cualquier
    llamador real antes de pasarle el resultado al validador."""
    plano = parser.leer_plano(doc)
    unidades = evaluator.group_rooms_by_unit_label(plano.rooms, plano.unit_labels)
    return plano, unidades


def _por_codigo(diagnosticos, codigo):
    return [d for d in diagnosticos if d.codigo == codigo]


# ---------------------------------------------------------------------------
# A. Nombres de capa "casi correctos"
# ---------------------------------------------------------------------------


def test_nombre_casi_correcto_con_guion_bajo_de_mas():
    doc = _doc_vacio("AM_UTIL_INT_", parser.CAPA_UTIL_INTERIOR)  # el ejemplo exacto del encargo
    msp = doc.modelspace()
    _recinto_base(msp)

    plano, unidades = _analizar(doc)
    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    casi = _por_codigo(diagnosticos, vc.CAPA_CASI_CORRECTA)
    assert len(casi) == 1
    assert casi[0].severidad == vc.SEVERIDAD_WARNING
    assert casi[0].capa == "AM_UTIL_INT_"
    assert "AM_UTIL_INT" in casi[0].mensaje
    # La capa mal escrita esta vacia: nada suyo entra en plano.rooms (que
    # solo trae el recinto base, de la capa bien escrita).
    assert len(plano.rooms) == 1


def test_nombre_casi_correcto_con_letra_de_mas():
    doc = _doc_vacio("AM_CONS_CERR", parser.CAPA_UTIL_INTERIOR)  # el otro ejemplo del encargo
    msp = doc.modelspace()
    _recinto_base(msp)

    plano, unidades = _analizar(doc)
    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    casi = _por_codigo(diagnosticos, vc.CAPA_CASI_CORRECTA)
    assert len(casi) == 1
    assert "AM_CONS_CER" in casi[0].mensaje


def test_nombre_casi_correcto_solo_mayusculas():
    # ezdxf/DXF tratan el nombre de capa como insensible a mayusculas para
    # su UNICIDAD (no se pueden crear "am_util_int" y "AM_UTIL_INT" como dos
    # capas distintas): asi que este caso es una unica capa "am_util_int",
    # no dos capas coexistiendo. El contenido se pone ahi mismo -- basta
    # para que `leer_plano` tenga algo que leer via el modo heredado (que SI
    # hace busqueda insensible a mayusculas al elegir capa, a diferencia de
    # `_leer_capa_am`, que compara exacto) -- y es independiente de lo que
    # detecte el validador, que mira `doc.layers` directamente.
    doc = _doc_vacio("am_util_int")
    msp = doc.modelspace()
    for i, nombre in enumerate(["Salón/cocina", "Dormitorio 1", "Baño"]):
        _rect(msp, "am_util_int", i * 5.0, 0, 4, 3, nombre)

    plano, unidades = _analizar(doc)
    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    casi = _por_codigo(diagnosticos, vc.CAPA_CASI_CORRECTA)
    assert len(casi) == 1
    assert casi[0].capa == "am_util_int"
    assert "mayúsculas" in casi[0].detalle


def test_nombre_exacto_del_catalogo_no_es_casi_correcto():
    """Una capa que YA está exactamente en el catálogo (operativa o
    reservada) no se marca como 'casi correcta' de sí misma."""
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, parser.CAPA_CONSTRUIDA_CERRADA,
                      parser.CAPA_UTIL_EXTERIOR)
    msp = doc.modelspace()
    _recinto_base(msp)

    plano, unidades = _analizar(doc)
    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    assert _por_codigo(diagnosticos, vc.CAPA_CASI_CORRECTA) == []


def test_nombre_no_relacionado_no_se_marca():
    """Una capa completamente ajena ("MUROS") no genera ruido -- no empieza
    ni por 'AM' ni está a poca distancia de ningun nombre del catálogo."""
    doc = _doc_vacio("MUROS", "COTAS", parser.CAPA_UTIL_INTERIOR)
    msp = doc.modelspace()
    _recinto_base(msp)

    plano, unidades = _analizar(doc)
    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    assert _por_codigo(diagnosticos, vc.CAPA_CASI_CORRECTA) == []


def test_capa_casi_correcta_nunca_se_autocorrige():
    """La capa candidata (AM_UTIL_INT) sigue vacia: el validador NUNCA lee
    el contenido de la capa mal escrita como si fuera la buena."""
    doc = _doc_vacio("AM_UTIL_INT_", parser.CAPA_UTIL_INTERIOR)
    msp = doc.modelspace()
    _rect(msp, "AM_UTIL_INT_", 0, 0, 6, 4, "Salón/cocina mal clasificado")  # capa mal escrita
    _recinto_base(msp)  # la capa bien escrita, con SU PROPIO recinto

    plano, unidades = _analizar(doc)

    # Solo el recinto de la capa bien escrita entra en el resultado.
    assert len(plano.rooms) == 1
    assert plano.rooms[0].label != "Salón/cocina mal clasificado"
    diagnosticos = vc.validar_capas_am(doc, plano, unidades)
    assert len(_por_codigo(diagnosticos, vc.CAPA_CASI_CORRECTA)) == 1


# ---------------------------------------------------------------------------
# B. Capas reservadas
# ---------------------------------------------------------------------------


def test_capa_reservada_con_contenido_se_reporta_info():
    # Desde la Fase 3, AM_UTIL_EXT y AM_CONS_EXT son operativas: la unica
    # capa que sigue reservada es AM_DESCUENTO.
    doc = _doc_vacio(parser.CAPA_DESCUENTO, parser.CAPA_UTIL_INTERIOR)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_DESCUENTO, 0, 0, 3, 2, "Patio")
    _recinto_base(msp)

    plano, unidades = _analizar(doc)
    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    reservadas = _por_codigo(diagnosticos, vc.CAPA_RESERVADA_NO_OPERATIVA)
    assert len(reservadas) == 1
    assert reservadas[0].severidad == vc.SEVERIDAD_INFO
    assert reservadas[0].capa == parser.CAPA_DESCUENTO


def test_capa_reservada_vacia_no_se_reporta():
    """Una capa reservada creada pero sin ninguna entidad (p. ej. una
    plantilla que las trae todas de fábrica) no genera ruido."""
    doc = _doc_vacio(parser.CAPA_DESCUENTO, parser.CAPA_UTIL_INTERIOR)
    msp = doc.modelspace()
    _recinto_base(msp)

    plano, unidades = _analizar(doc)
    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    assert _por_codigo(diagnosticos, vc.CAPA_RESERVADA_NO_OPERATIVA) == []


def test_am_util_ext_y_am_cons_ext_ya_no_son_reservadas():
    """Regresión directa del cambio de catálogo de la Fase 3: contenido en
    AM_UTIL_EXT/AM_CONS_EXT ya NO genera RESERVADA_NO_OPERATIVA -- son
    operativas. Solo AM_DESCUENTO sigue en el catálogo de reservadas."""
    assert parser.CAPAS_AM_RESERVADAS == (parser.CAPA_DESCUENTO,)
    assert parser.CAPA_UTIL_EXTERIOR in parser.CAPAS_AM_OPERATIVAS
    assert parser.CAPA_CONSTRUIDA_EXTERIOR in parser.CAPAS_AM_OPERATIVAS

    doc = _doc_vacio(parser.CAPA_UTIL_EXTERIOR, parser.CAPA_CONSTRUIDA_EXTERIOR,
                      parser.CAPA_DESCUENTO, parser.CAPA_UTIL_INTERIOR)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_EXTERIOR, 0, 0, 3, 2)
    _rect(msp, parser.CAPA_CONSTRUIDA_EXTERIOR, 10, 0, 3, 2)
    _rect(msp, parser.CAPA_DESCUENTO, 20, 0, 3, 2)
    _recinto_base(msp)

    plano, unidades = _analizar(doc)
    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    reservadas = {d.capa for d in _por_codigo(diagnosticos, vc.CAPA_RESERVADA_NO_OPERATIVA)}
    assert reservadas == {parser.CAPA_DESCUENTO}


# ---------------------------------------------------------------------------
# C. Diagnósticos de AM_CONS_CER
# ---------------------------------------------------------------------------


def _plano_dos_viviendas(rotular_vt2=True):
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, parser.CAPA_CONSTRUIDA_CERRADA)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))
    if rotular_vt2:
        _rect(msp, parser.CAPA_UTIL_INTERIOR, 20, 0, 6, 4, "Salón/cocina")
        msp.add_mtext("VT2/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((17, 2))
    return doc, msp


def test_envolvente_ambigua_no_elige_ninguna_y_se_reporta():
    doc, msp = _plano_dos_viviendas()
    # DOS envolventes, las dos mas cerca de VT1/1 que de VT2/1.
    _rect(msp, parser.CAPA_CONSTRUIDA_CERRADA, -0.3, -0.3, 6.6, 4.6)
    _rect(msp, parser.CAPA_CONSTRUIDA_CERRADA, -0.5, -0.5, 7.0, 5.0)

    plano, unidades = _analizar(doc)
    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    ambiguas = _por_codigo(diagnosticos, vc.ENVOLVENTE_AMBIGUA)
    assert len(ambiguas) == 1
    assert ambiguas[0].vivienda == "VT1/1"
    assert ambiguas[0].severidad == vc.SEVERIDAD_WARNING

    # VT1/1 NO debe aparecer ademas como VIVIENDA_SIN_ENVOLVENTE: particion
    # exhaustiva y sin solape.
    sin_envolvente = _por_codigo(diagnosticos, vc.VIVIENDA_SIN_ENVOLVENTE)
    assert "VT1/1" not in {d.vivienda for d in sin_envolvente}

    # Y efectivamente ninguna de las dos se asigno.
    con_envolvente = evaluator.asignar_envolvente_cerrada(
        unidades, plano.envolventes_cerradas, plano.unit_labels)
    vt1 = next(u for u in con_envolvente if u.name == "VT1/1")
    assert vt1.envolvente_cerrada is None


def test_vivienda_sin_envolvente_valida_se_reporta():
    """AM_CONS_CER esta en uso (VT1/1 tiene su envolvente), pero VT2/1 no
    tiene ninguna: diagnostico explicito solo para VT2/1."""
    doc, msp = _plano_dos_viviendas()
    _rect(msp, parser.CAPA_CONSTRUIDA_CERRADA, -0.3, -0.3, 6.6, 4.6)  # solo para VT1/1

    plano, unidades = _analizar(doc)
    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    sin_envolvente = _por_codigo(diagnosticos, vc.VIVIENDA_SIN_ENVOLVENTE)
    assert {d.vivienda for d in sin_envolvente} == {"VT2/1"}
    assert sin_envolvente[0].severidad == vc.SEVERIDAD_WARNING
    # VT1/1 SI tiene envolvente: no debe reportarse.
    assert "VT1/1" not in {d.vivienda for d in sin_envolvente}


def test_envolvente_sin_vivienda_identificable_etiqueta_sin_habitaciones():
    """Hay una etiqueta VT en el plano (VT9/9) pero ninguna habitacion
    agrupada bajo ella -- la envolvente mas cercana a esa etiqueta no tiene
    Unit a la que asignarse."""
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, parser.CAPA_CONSTRUIDA_CERRADA)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))
    # Etiqueta VT9/9 sin ninguna habitacion cerca -- y una envolvente junto a ella.
    msp.add_mtext("VT9/9", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((50, 50))
    _rect(msp, parser.CAPA_CONSTRUIDA_CERRADA, 49, 49, 3, 3)  # cerca de VT9/9, no de VT1/1
    _rect(msp, parser.CAPA_CONSTRUIDA_CERRADA, -0.3, -0.3, 6.6, 4.6)  # la de VT1/1

    plano, unidades = _analizar(doc)
    assert {u.name for u in unidades} == {"VT1/1"}  # VT9/9 nunca se convierte en Unit

    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    huerfanas = _por_codigo(diagnosticos, vc.ENVOLVENTE_SIN_VIVIENDA)
    assert len(huerfanas) == 1
    assert huerfanas[0].vivienda == "VT9/9"
    # Y VT1/1 SI tiene la suya: no debe aparecer como sin envolvente.
    assert "VT1/1" not in {d.vivienda for d in _por_codigo(diagnosticos, vc.VIVIENDA_SIN_ENVOLVENTE)}


def test_envolvente_sin_ninguna_etiqueta_vt_en_el_plano():
    """Plano sin ninguna etiqueta VT en absoluto: cada envolvente se
    reporta como huerfana, sin intentar emparejarla por proximidad."""
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR, parser.CAPA_CONSTRUIDA_CERRADA)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")  # sin etiqueta VT
    _rect(msp, parser.CAPA_CONSTRUIDA_CERRADA, -0.3, -0.3, 6.6, 4.6)

    plano, unidades = _analizar(doc)
    assert plano.unit_labels == []

    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    huerfanas = _por_codigo(diagnosticos, vc.ENVOLVENTE_SIN_VIVIENDA)
    assert len(huerfanas) == 1
    assert huerfanas[0].vivienda == ""  # no hay ninguna etiqueta con la que nombrarla
    # Y no debe generarse un VIVIENDA_SIN_ENVOLVENTE por cada Unit sintetica
    # de group_rooms_by_proximity -- seria puro ruido del mismo problema.
    assert _por_codigo(diagnosticos, vc.VIVIENDA_SIN_ENVOLVENTE) == []


def test_am_cons_cer_no_usada_no_genera_diagnosticos():
    """Si AM_CONS_CER no aparece en el plano en absoluto (ni valida ni
    descartada), ningun diagnostico de envolvente se genera -- ni falsa
    'vivienda sin envolvente' para plano que nunca la uso."""
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR)
    msp = doc.modelspace()
    _rect(msp, parser.CAPA_UTIL_INTERIOR, 0, 0, 6, 4, "Salón/cocina")
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR}).set_location((-3, 2))

    plano, unidades = _analizar(doc)
    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    assert _por_codigo(diagnosticos, vc.ENVOLVENTE_AMBIGUA) == []
    assert _por_codigo(diagnosticos, vc.ENVOLVENTE_SIN_VIVIENDA) == []
    assert _por_codigo(diagnosticos, vc.VIVIENDA_SIN_ENVOLVENTE) == []


# ---------------------------------------------------------------------------
# D. Geometría descartada en capa AM_* -- reutilizada, no recalculada
# ---------------------------------------------------------------------------


def test_geometria_invalida_en_am_util_int_sube_a_error():
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR)
    msp = doc.modelspace()
    bowtie = [(0, 0), (4, 4), (4, 0), (0, 4)]
    msp.add_lwpolyline(bowtie, close=True, dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR})

    plano, unidades = _analizar(doc)
    assert len(plano.geometria_no_leida) == 1  # Fase 1, sin recalcular

    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    errores = _por_codigo(diagnosticos, parser.MOTIVO_GEOMETRIA_INVALIDA)
    assert len(errores) == 1
    assert errores[0].severidad == vc.SEVERIDAD_ERROR
    assert errores[0].capa == parser.CAPA_UTIL_INTERIOR
    # Mismo handle que el descarte original de Fase 1: no se recalcula nada.
    assert errores[0].handle == plano.geometria_no_leida[0].handle


def test_tipo_no_soportado_en_am_util_int_es_warning():
    doc = _doc_vacio(parser.CAPA_UTIL_INTERIOR)
    msp = doc.modelspace()
    msp.add_line((0, 0), (4, 0), dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR})

    plano, unidades = _analizar(doc)
    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    avisos = _por_codigo(diagnosticos, parser.MOTIVO_TIPO_NO_SOPORTADO)
    assert len(avisos) == 1
    assert avisos[0].severidad == vc.SEVERIDAD_WARNING


def test_geometria_descartada_en_modo_heredado_no_se_reporta():
    """La geometria descartada de la capa heredada ("00 areas") no forma
    parte del contrato AM_* -- Fase 1 ya la deja en geometria_no_leida, pero
    este validador solo envuelve las capas AM_* operativas."""
    doc = _doc_vacio(parser.AREA_LAYER)
    msp = doc.modelspace()
    msp.add_line((0, 0), (4, 0), dxfattribs={"layer": parser.AREA_LAYER})
    for i, nombre in enumerate(["Dormitorio 1", "Dormitorio 2", "Baño"]):
        _rect(msp, parser.AREA_LAYER, 10.0 + i * 5, 0, 3, 3, nombre)

    plano, unidades = _analizar(doc)
    assert len(plano.geometria_no_leida) == 1  # la LINE, en modo heredado

    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    assert diagnosticos == []  # nada que reportar: no es geometria de una capa AM_*


# ---------------------------------------------------------------------------
# E. Regresión: DXF puramente heredado -> lista vacía
# ---------------------------------------------------------------------------


def test_dxf_heredado_sin_ninguna_capa_am_no_genera_diagnosticos():
    doc = _doc_vacio(parser.AREA_LAYER)
    msp = doc.modelspace()
    for i, nombre in enumerate(["Salón/cocina", "Dormitorio 1", "Baño"]):
        _rect(msp, parser.AREA_LAYER, i * 5.0, 0, 4, 3, nombre)
    msp.add_mtext("VT1/1", dxfattribs={"layer": parser.AREA_LAYER}).set_location((-3, 1.5))

    plano, unidades = _analizar(doc)
    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    assert diagnosticos == []


def test_dxf_real_ejemplo_sin_capas_am_no_genera_diagnosticos():
    """Regresión sobre el DXF real de referencia, si está disponible en esta
    máquina (mismo patrón que tests/test_cierre_recuperado.py)."""
    import pytest

    candidatas = [
        os.path.join(os.path.dirname(RAIZ), "ejemplo.dxf"),
        os.path.join(os.path.expanduser("~"), "Desktop", "ejemplo.dxf"),
    ]
    ruta = next((c for c in candidatas if os.path.isfile(c)), None)
    if ruta is None:
        pytest.skip("ejemplo.dxf no esta disponible en esta maquina")

    doc = parser.load_document(ruta)
    plano, unidades = _analizar(doc)
    diagnosticos = vc.validar_capas_am(doc, plano, unidades)

    assert diagnosticos == []
