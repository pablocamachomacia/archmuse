# -*- coding: utf-8 -*-
"""Modo preguntar: tablas completas sin inventar ninguna cifra.

PRD `docs/prd/2026-09-17-modo-preguntar.md`. Pablo: «Cuando ArchMuse no pueda
determinar un dato con suficiente certeza, no lo inventa ni deja la celda vacía
automáticamente»; «Como máximo 3 preguntas por vivienda»; «Todo dato obtenido mediante
interacción del arquitecto debe quedar identificado como "Confirmado por el
arquitecto"»; «La prioridad es: 0 cifras inventadas».

Las decisiones de cómo se lee cada respuesta (D-1 a D-12) son propuestas, pendientes de
firma. Planos sintéticos con coordenadas escritas a mano.
"""
from __future__ import annotations

import json
import os
import sys

import ezdxf
import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import parser  # noqa: E402
from analyzer import plantilla_cuadro as pc  # noqa: E402
from analyzer import respuestas_del_arquitecto as rda  # noqa: E402
from tests._carpetas_temporales import carpeta_temporal_de_test  # noqa: E402

CAPA = "00 areas"
V1 = ("VT1/1", (3.0, 2.5))
V2 = ("VT2/1", (23.0, 2.5))
#: Firmes: el rótulo de su vivienda dentro o muy cerca.
FIRMES = (("Salón/cocina", 0, 0, 6, 5), ("Baño", 6, 0, 8, 2), ("Terraza", 0, -3, 6, 0),
          ("Salón/cocina", 20, 0, 26, 5), ("Baño", 26, 0, 28, 2))
#: A 9,0 m del rótulo de VT1/1 y a 11,0 del de VT2/1: reparto dudoso, agrupado con VT1/1.
DORMITORIOS = (("Dormitorio 1", 10, 0, 14, 4), ("Dormitorio 2", 10, 4.1, 14, 8),
               ("Dormitorio 3", 10, 8.1, 14, 12), ("Dormitorio 4", 10, 12.1, 14, 16))
#: Contiene las piezas interiores de VT1/1 (con los dormitorios) y no su terraza.
CONSTRUIDA_V1 = [(-0.02, -0.02), (14.02, -0.02), (14.02, 16.02), (-0.02, 16.02)]


#: Rotulada «S. construida cerrada»: contiene las piezas de VT2/1 y el Dormitorio 1.
CONSTRUIDA_V2 = [(9.98, -0.02), (28.02, -0.02), (28.02, 5.02), (9.98, 5.02)]


def _plano(dormitorios=1, construida=True, extras=(), construida_v2=False):
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    doc.layers.add(CAPA)
    doc.layers.add("00 CONSTRUIDA")
    msp = doc.modelspace()
    for nombre, x0, y0, x1, y1 in FIRMES + DORMITORIOS[:dormitorios] + tuple(extras):
        msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                           dxfattribs={"layer": CAPA})
        for texto in (nombre if isinstance(nombre, tuple) else (nombre,)):
            msp.add_mtext(texto, dxfattribs={"layer": CAPA, "char_height": 0.125,
                                             "insert": ((x0 + x1) / 2, (y0 + y1) / 2)})
    for nombre, (x, y) in (V1, V2):
        msp.add_mtext(nombre, dxfattribs={"layer": CAPA, "char_height": 0.3, "insert": (x, y)})
    if construida:
        msp.add_lwpolyline(CONSTRUIDA_V1, close=True, dxfattribs={"layer": "00 CONSTRUIDA"})
    if construida_v2:
        msp.add_lwpolyline(CONSTRUIDA_V2, close=True, dxfattribs={"layer": "00 CONSTRUIDA"})
        msp.add_mtext("S. construida cerrada", dxfattribs={"layer": CAPA, "char_height": 0.125,
                                                           "insert": (18.0, 5.2)})
    ruta = os.path.join(carpeta_temporal_de_test("archmuse_test_preguntar_"), "p.dxf")
    doc.saveas(ruta)
    doc = parser.load_document(ruta)
    return doc, parser.leer_plano(doc, layer=CAPA)


def _handle(doc, capa=CAPA, x0=None, y0=None):
    for e in doc.modelspace().query("LWPOLYLINE"):
        puntos = [tuple(p[:2]) for p in e.get_points()]
        if e.dxf.layer == capa and (x0 is None or (x0, y0) in puntos):
            return e.dxf.handle
    raise AssertionError("no está")


def _vivienda(nombre=V1[0]):
    return rda.Vivienda(nombre, dict((V1, V2))[nombre])


def _respuestas(*registros, **kw):
    return rda.Respuestas(registros=tuple(registros), **kw)


def _si(handle, vivienda=V1[0], suya=True):
    return {"tipo": rda.PERTENENCIA, "pieza": handle, "vivienda": _vivienda(vivienda).a_dict(),
            "es_suya": suya}


def _fila(p, rotulo):
    return next((f for f in list(p.interiores) + list(p.exteriores) if f.rotulo == rotulo), None)


def _notas(p, etiqueta):
    return [m for etiquetas, m in p.notas_por_motivo if etiqueta in etiquetas]


# --- 1. Qué se pregunta ---------------------------------------------------------------

def test_sin_modo_preguntar_nada_cambia():
    """La web y el agente no preguntan: ni preguntas ni nota de lo que falta."""
    doc, plano = _plano()
    p = pc.construir(doc, plano, "VT1/1")
    assert p.preguntas_al_arquitecto == ()
    assert _fila(p, "Dormitorio 1").valor == ""
    assert not _notas(p, "Preguntas")


def test_la_pieza_que_puede_ser_de_dos_viviendas_se_pregunta_resaltada():
    doc, plano = _plano()
    p = pc.construir(doc, plano, "VT1/1", preguntar=True)
    (pregunta,) = p.preguntas_al_arquitecto
    assert pregunta.tipo == rda.PERTENENCIA
    assert pregunta.texto == "¿Esta pieza es de VT1/1?"
    assert pregunta.opciones == ("Si", "No")
    assert pregunta.resaltar == (_handle(doc, x0=10, y0=0),)
    assert "Dormitorio 1" in pregunta.contexto and "VT2/1" in pregunta.contexto


def test_la_construida_se_pregunta_despues_de_las_piezas():
    """D-8: la comprobación de `C-12` depende de qué piezas son suyas."""
    doc, plano = _plano()
    p = pc.construir(doc, plano, "VT1/1", preguntar=True)
    assert [q.tipo for q in p.preguntas_al_arquitecto] == [rda.PERTENENCIA]
    h = _handle(doc, x0=10, y0=0)
    despues = pc.construir(doc, plano, "VT1/1", preguntar=True, respuestas=_respuestas(
        _si(h), preguntas_hechas=1, respondidas=frozenset([rda.id_pertenencia(h, _vivienda())])))
    (pregunta,) = despues.preguntas_al_arquitecto
    assert pregunta.tipo == rda.CONSTRUIDA
    assert pregunta.texto == "Haz clic en la polilínea de superficie construida de VT1/1"


def test_como_maximo_tres_preguntas_y_la_nota_dice_cuantas_celdas_quedan():
    doc, plano = _plano(dormitorios=4)
    p = pc.construir(doc, plano, "VT1/1", preguntar=True)
    assert len(p.preguntas_al_arquitecto) == 3
    assert {q.tipo for q in p.preguntas_al_arquitecto} == {rda.PERTENENCIA}
    ids = [q.id for q in p.preguntas_al_arquitecto]
    registros = [_si(q.resaltar[0]) for q in p.preguntas_al_arquitecto]
    final = pc.construir(doc, plano, "VT1/1", preguntar=True, respuestas=_respuestas(
        *registros, preguntas_hechas=3, respondidas=frozenset(ids)))
    assert final.preguntas_al_arquitecto == ()
    (nota,) = _notas(final, "Preguntas")
    assert "harían falta 2 respuesta(s) más" in nota, nota   # el dormitorio y la construida
    # Una celda de pieza, tres totales y la construida y el número de unidades.
    assert "quedan 6 celda(s) vacía(s)" in nota, nota


def test_no_se_pregunta_lo_que_ninguna_respuesta_arregla():
    """D-12: una pieza dibujada dos veces no se pregunta."""
    doc, plano = _plano(dormitorios=0, construida=False,
                        extras=(("Aseo", 5.5, 3, 7.5, 6),))   # pisa 1 m² del salón de VT1/1
    p = pc.construir(doc, plano, "VT1/1", preguntar=True)
    assert _notas(p, "Aseo") and "se solapa" in _notas(p, "Aseo")[0]
    assert all(q.tipo == rda.CONSTRUIDA for q in p.preguntas_al_arquitecto)


def test_elegir_un_nombre_no_salta_el_solape():
    """El salón con el rótulo del aseo encima tiene dos nombres; elegido uno, sigue
    solapado y sin cifra."""
    doc, plano = _plano(dormitorios=0, construida=False, extras=(("Aseo", 1, 1, 3, 3),))
    p = pc.construir(doc, plano, "VT1/1", preguntar=True)
    (nombre,) = [q for q in p.preguntas_al_arquitecto if q.tipo == rda.NOMBRE]
    elegido = pc.construir(doc, plano, "VT1/1", respuestas=_respuestas(
        {"tipo": rda.NOMBRE, "pieza": nombre.resaltar[0], "opcion": 2}))
    assert _fila(elegido, "Salón/cocina").valor == ""


# --- 2. Qué hace cada respuesta ---------------------------------------------------------

def test_si_la_celda_lleva_su_cifra_medida_y_confirmado_por_el_arquitecto():
    doc, plano = _plano()
    h = _handle(doc, x0=10, y0=0)
    p = pc.construir(doc, plano, "VT1/1", respuestas=_respuestas(_si(h)))
    assert _fila(p, "Dormitorio 1").valor == "16,00 m²"
    assert _notas(p, "Dormitorio 1") == [rda.CONFIRMADO]
    assert p.cierre[0][1] == "50,00 m²", "30 + 4 + 16, calculado sobre cifras medidas"
    assert "Confirmado por el arquitecto: 1 dato" in pc.notas_del_dibujo(p)
    assert pc.a_dict(p)["confirmadas_por_el_arquitecto"] == ["Dormitorio 1"]
    assert {"tipo": rda.PERTENENCIA, "pieza": h, "vivienda": _vivienda().a_dict(),
            "es_suya": True} in p.registros_aplicados


def test_no_la_pieza_sale_de_la_tabla_con_nota_y_los_totales_se_cierran_sin_ella():
    doc, plano = _plano()
    h = _handle(doc, x0=10, y0=0)
    p = pc.construir(doc, plano, "VT1/1", respuestas=_respuestas(_si(h, suya=False)))
    assert _fila(p, "Dormitorio 1") is None
    (nota,) = _notas(p, "Dormitorio 1")
    assert "no es de esta vivienda" in nota and nota.endswith(rda.CONFIRMADO)
    assert p.cierre[0][1] == "34,00 m²"


def test_si_a_otra_vivienda_es_no_para_esta_y_la_otra_la_recibe():
    """D-4 y D-11."""
    doc, plano = _plano()
    h = _handle(doc, x0=10, y0=0)
    respuestas = _respuestas(_si(h, vivienda="VT2/1"))
    v1 = pc.construir(doc, plano, "VT1/1", respuestas=respuestas)
    assert _fila(v1, "Dormitorio 1") is None
    assert "es de VT2/1" in _notas(v1, "Dormitorio 1")[0]
    v2 = pc.construir(doc, plano, "VT2/1", respuestas=respuestas)
    assert _fila(v2, "Dormitorio 1").valor == "16,00 m²"
    assert _notas(v2, "Dormitorio 1") == [rda.CONFIRMADO]


def test_la_pieza_de_la_vecina_que_duda_bloquea_los_totales_y_se_pregunta():
    """D-11 y D-13, medido en el banco: sin este bloqueo, contestar a la única pieza dudosa
    de una vivienda escribía sus totales sin las piezas que se habían medido con la vecina."""
    doc, plano = _plano()
    p = pc.construir(doc, plano, "VT2/1")
    assert p.cierre[0][1] == "" and p.cierre[1][1] == ""
    assert any("puede ser de esta vivienda" in m for _e, m in p.notas_por_motivo)
    con_preguntas = pc.construir(doc, plano, "VT2/1", preguntar=True)
    (pertenencia,) = [q for q in con_preguntas.preguntas_al_arquitecto if q.tipo == rda.PERTENENCIA]
    assert pertenencia.resaltar == (_handle(doc, x0=10, y0=0),)
    assert pertenencia.texto == "¿Esta pieza es de VT2/1?"
    h = _handle(doc, x0=10, y0=0)
    resuelta = pc.construir(doc, plano, "VT2/1", respuestas=_respuestas(_si(h, "VT2/1", suya=False)))
    assert resuelta.cierre[0][1] == "34,00 m²", "con su «No», el total se demuestra y se escribe"


def test_la_vecina_pregunta_por_la_pieza_que_el_plano_mete_en_su_construida():
    doc, plano = _plano(construida=False, construida_v2=True)
    p = pc.construir(doc, plano, "VT2/1", preguntar=True)
    (pertenencia,) = [q for q in p.preguntas_al_arquitecto if q.tipo == rda.PERTENENCIA]
    assert pertenencia.resaltar == (_handle(doc, x0=10, y0=0),)
    assert pertenencia.texto == "¿Esta pieza es de VT2/1?"


def test_sin_respuesta_la_celda_queda_vacia_con_el_motivo_y_no_se_repite_en_la_pasada():
    doc, plano = _plano()
    h = _handle(doc, x0=10, y0=0)
    ident = rda.id_pertenencia(h, _vivienda())
    p = pc.construir(doc, plano, "VT1/1", preguntar=True, respuestas=_respuestas(
        preguntas_hechas=1, sin_respuesta=frozenset([ident])))
    assert _fila(p, "Dormitorio 1").valor == ""
    assert _notas(p, "Dormitorio 1")[0].endswith(rda.SIN_RESPUESTA)
    assert ident not in [q.id for q in p.preguntas_al_arquitecto]
    assert not p.registros_aplicados


def test_la_construida_marcada_se_mide_y_se_confirma():
    doc, plano = _plano()
    h = _handle(doc, x0=10, y0=0)
    marcada = _handle(doc, capa="00 CONSTRUIDA")
    p = pc.construir(doc, plano, "VT1/1", respuestas=_respuestas(_si(h), {
        "tipo": rda.CONSTRUIDA, "vivienda": _vivienda().a_dict(), "polilinea": marcada}))
    assert p.cierre[2][1] == "225,20 m²"     # 14,04 × 16,04 medido, no escrito por nadie
    assert _notas(p, pc.CONSTRUIDA) == [rda.CONFIRMADO]
    assert any(r["tipo"] == rda.CONSTRUIDA for r in p.registros_aplicados)


def test_una_construida_marcada_que_no_contiene_la_vivienda_no_se_escribe_ni_se_guarda():
    doc, plano = _plano()
    h = _handle(doc, x0=10, y0=0)
    bano = _handle(doc, x0=6, y0=0)
    p = pc.construir(doc, plano, "VT1/1", respuestas=_respuestas(_si(h), {
        "tipo": rda.CONSTRUIDA, "vivienda": _vivienda().a_dict(), "polilinea": bano}))
    assert p.cierre[2][1] == ""
    assert "que has marcado" in _notas(p, pc.CONSTRUIDA)[0]
    assert not any(r["tipo"] == rda.CONSTRUIDA for r in p.registros_aplicados)


def test_el_nombre_dudoso_se_elige_entre_los_suyos():
    extras = ((("Tendedero", "Terraza"), 6, -3, 8, 0),)
    doc, plano = _plano(extras=extras)
    p = pc.construir(doc, plano, "VT1/1", preguntar=True)
    (nombre,) = [q for q in p.preguntas_al_arquitecto if q.tipo == rda.NOMBRE]
    assert nombre.opciones == ("Tendedero", "Terraza")
    h = nombre.resaltar[0]
    elegido = pc.construir(doc, plano, "VT1/1", respuestas=_respuestas(
        {"tipo": rda.NOMBRE, "pieza": h, "opcion": 1}))
    assert _fila(elegido, "Tendedero").valor == "6,00 m²"
    assert _notas(elegido, "Tendedero") == [rda.CONFIRMADO]
    assert {"tipo": rda.NOMBRE, "pieza": h, "nombre": "Tendedero"} in elegido.registros_aplicados


def test_interior_o_exterior_entra_en_el_mismo_turno_y_se_confirma():
    doc, plano = _plano(extras=(("Trastero", 6, 2, 8, 5),))
    p = pc.construir(doc, plano, "VT1/1", preguntar=True)
    (ambito,) = [q for q in p.preguntas_al_arquitecto if q.tipo == rda.AMBITO]
    assert ambito.opciones == ("Interior", "Exterior")
    respondida = pc.construir(doc, plano, "VT1/1", respuestas=_respuestas(
        {"tipo": rda.AMBITO, "familia": ambito.id.split("|", 1)[1], "ambito": "interior"}))
    assert _fila(respondida, "Trastero").valor == "6,00 m²"
    assert _notas(respondida, "Trastero") == [rda.CONFIRMADO]


def test_ninguna_respuesta_escribe_una_cifra_que_no_se_haya_medido():
    """Con todas las respuestas, cada cifra de la tabla es una medida del plano."""
    doc, plano = _plano()
    h = _handle(doc, x0=10, y0=0)
    p = pc.construir(doc, plano, "VT1/1", respuestas=_respuestas(_si(h), {
        "tipo": rda.CONSTRUIDA, "vivienda": _vivienda().a_dict(),
        "polilinea": _handle(doc, capa="00 CONSTRUIDA")}))
    medidas = {"30,00 m²", "4,00 m²", "16,00 m²", "18,00 m²", "50,00 m²", "225,20 m²", "55,00 m²"}
    cifras = {t for _f, _c, t in p.celdas() if t.endswith("m²")}
    assert cifras <= medidas, cifras - medidas


# --- 3. Guardar y no volver a preguntar ---------------------------------------------------

def test_la_segunda_vez_no_pregunta_y_da_la_misma_tabla():
    doc, plano = _plano()
    almacen = rda.Almacen(carpeta_temporal_de_test("archmuse_test_respuestas_"))
    ruta = r"C:\Proyectos\Bloque\plantas base.dwg"
    h = _handle(doc, x0=10, y0=0)
    marcada = _handle(doc, capa="00 CONSTRUIDA")
    primera = pc.construir(doc, plano, "VT1/1", preguntar=True, respuestas=_respuestas(_si(h), {
        "tipo": rda.CONSTRUIDA, "vivienda": _vivienda().a_dict(), "polilinea": marcada}))
    assert almacen.guardar(ruta, primera.registros_aplicados) == 2
    respuestas, _nuevas = rda.desde_peticion({}, almacen.cargar(ruta))
    segunda = pc.construir(doc, plano, "VT1/1", preguntar=True, respuestas=respuestas)
    assert segunda.preguntas_al_arquitecto == ()
    assert segunda.celdas() == primera.celdas()
    assert almacen.guardar(ruta, segunda.registros_aplicados) == 0, "nada nuevo que guardar"


def test_el_almacen_nunca_guarda_una_cifra():
    almacen = rda.Almacen(carpeta_temporal_de_test("archmuse_test_respuestas_"))
    ruta = "C:/plano.dwg"
    con_cifra = {"tipo": rda.CONSTRUIDA, "vivienda": _vivienda().a_dict(), "polilinea": "A1",
                 "area_m2": 58.3}
    assert almacen.guardar(ruta, [con_cifra]) == 0
    assert almacen.cargar(ruta) == []
    assert not rda.es_registro_valido({"tipo": rda.NOMBRE, "pieza": "A1", "opcion": 2})


def test_la_ultima_respuesta_manda_y_el_fichero_es_por_plano():
    almacen = rda.Almacen(carpeta_temporal_de_test("archmuse_test_respuestas_"))
    almacen.guardar("C:/a.dwg", [_si("A1")])
    almacen.guardar("C:/a.dwg", [_si("A1", suya=False)])
    almacen.guardar("C:/b.dwg", [_si("A1")])
    assert rda.Respuestas(tuple(almacen.cargar("C:/a.dwg"))).pertenencia("A1", _vivienda()) is False
    assert rda.Respuestas(tuple(almacen.cargar("C:/b.dwg"))).pertenencia("A1", _vivienda()) is True
    assert len(os.listdir(almacen.carpeta)) == 2
    with open(os.path.join(almacen.carpeta, os.listdir(almacen.carpeta)[0]), encoding="utf-8") as f:
        assert json.load(f)["version"] == 1


def test_un_fichero_roto_solo_hace_que_se_vuelva_a_preguntar():
    carpeta = carpeta_temporal_de_test("archmuse_test_respuestas_")
    almacen = rda.Almacen(carpeta)
    with open(os.path.join(carpeta, rda.huella_del_plano("C:/a.dwg") + ".json"), "w") as f:
        f.write("{roto")
    assert almacen.cargar("C:/a.dwg") == []


@pytest.mark.parametrize("respuesta, esperado", [
    ({"id": "pertenencia|A1|3.0000|2.5000|VT1/1", "valor": "Si"},
     {"tipo": "pertenencia", "pieza": "A1", "vivienda": {"nombre": "VT1/1", "rotulo": [3.0, 2.5]},
      "es_suya": True}),
    ({"id": "pertenencia|A1|-|-|VT1/1", "valor": "No"},
     {"tipo": "pertenencia", "pieza": "A1", "vivienda": {"nombre": "VT1/1", "rotulo": None},
      "es_suya": False}),
    ({"id": "construida|3.0000|2.5000|VT1/1", "valor": "B2"},
     {"tipo": "construida", "vivienda": {"nombre": "VT1/1", "rotulo": [3.0, 2.5]},
      "polilinea": "B2"}),
    ({"id": "nombre|C3", "valor": "2"}, {"tipo": "nombre", "pieza": "C3", "opcion": 2}),
    ({"id": "ambito|trastero", "valor": "Exterior"},
     {"tipo": "ambito", "familia": "trastero", "ambito": "exterior"}),
    ({"id": "pertenencia|A1|3.0000|2.5000|VT1/1", "valor": "quizá"}, None),
    ({"id": "otra|cosa", "valor": "Si"}, None),
])
def test_las_respuestas_del_comando_se_leen_sin_adivinar(respuesta, esperado):
    _respuestas_leidas, nuevas = rda.desde_peticion({"respuestas_del_arquitecto": [respuesta]})
    assert nuevas == ([esperado] if esperado else [])


def test_la_vivienda_se_reconoce_por_su_rotulo_con_la_tolerancia_del_clic():
    a = rda.Vivienda("VT1/1", (3.0, 2.5))
    assert a.es(rda.Vivienda("VT1/1", (3.005, 2.495)))
    assert not a.es(rda.Vivienda("VT1/1", (3.5, 2.5))), "otra vivienda con el mismo rótulo (C-13)"
    assert not a.es(rda.Vivienda("VT2/1", (3.0, 2.5)))


def test_con_una_sola_pregunta_de_cupo_va_la_pieza_propia_antes_que_la_de_la_vecina():
    """Medido en el banco: una pieza propia que está dentro de la construida de la vecina y
    además duda por cercanía no contaba como bloqueo de los totales, y la prioridad
    prefería preguntar por una pieza de la vecina que no rellenaba nada de esta tabla."""
    doc, plano = _plano(construida=False, construida_v2=True,
                        extras=(("Aseo", 15, 0, 16.5, 2),))   # de VT2/1, duda hacia VT1/1
    p = pc.construir(doc, plano, "VT1/1", preguntar=True,
                     respuestas=_respuestas(preguntas_hechas=2))
    (pregunta,) = p.preguntas_al_arquitecto
    assert pregunta.resaltar == (_handle(doc, x0=10, y0=0),)
