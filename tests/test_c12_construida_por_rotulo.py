# -*- coding: utf-8 -*-
"""`C-12`, firmado el 2026-09-13: la superficie construida cerrada es la
polilínea que el arquitecto ROTULA, no la que ArchMuse deduce por su color.

Visto bueno de Pablo, con tres condiciones que son las tres secciones de abajo:

1. «Si hay más de una polilínea candidata para el mismo rótulo, no elijas:
   declara y deja la fila vacía. Nunca la más grande ni la primera.»
2. «Nunca por color. Ni como respaldo.»
3. «Guardián: la fila de S. CONSTRUIDA C. solo puede llevar cifra si hay
   exactamente una polilínea rotulada.»

Parámetros firmados: las formas «superficie construida cerrada» y «s.
construida cerrada», y 3 alturas de texto de distancia máxima al borde.

Todo sobre el fixture sintético (`tests/fixtures/cuadro_sintetico/`): una
vivienda, su envolvente ACI 10 con el flag de cerrada sin poner y el rótulo
«Superficie construida cerrada» a 0,23 m de su borde superior, en texto de
0,125 (alcance 0,375). Los escenarios se construyen sobre el payload que
mandaría el `.lsp`, así que pasan por la misma costura que el comando.
"""
from __future__ import annotations

import ast
import copy
import inspect
import os
import re
import sys
import tempfile
import textwrap

import pytest
from shapely.geometry import Polygon

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import parser  # noqa: E402
from analyzer import plantilla_cuadro as pc  # noqa: E402
from analyzer.geometria_recibida import (  # noqa: E402
    PayloadInvalido, SubidaMaterializada, payload_desde_dxf, validar,
)

CARPETA = os.path.join(RAIZ, "tests", "fixtures", "cuadro_sintetico")
FIXTURE = os.path.join(CARPETA, "cuadro_sintetico.dxf")
LSP = os.path.join(RAIZ, "autocad", "archmuse.lsp")
CON_RESPUESTA = {"TRASTERO": "interior"}
ROTULO = "Superficie construida cerrada"


def _area_envolvente():
    import importlib.util

    spec = importlib.util.spec_from_file_location("gen", os.path.join(CARPETA, "generar.py"))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return Polygon(modulo.ENVOLVENTE).area


def _leer(payload):
    carpeta = tempfile.mkdtemp(prefix="am_c12_")
    destino = os.path.join(carpeta, "m.dxf")
    SubidaMaterializada(validar(payload)).save(destino)
    doc = parser.load_document(destino)
    return doc, parser.leer_plano(doc, layer="00 areas")


def _plantilla(payload=None):
    if payload is None:
        doc = parser.load_document(FIXTURE)
        plano = parser.leer_plano(doc)
    else:
        doc, plano = _leer(payload)
    return pc.construir(doc, plano, "VT1/3", ambitos=CON_RESPUESTA)


def _construida(p):
    return p.cierre[2][1]


def _nota(p):
    return next((n for n in p.notas if n.startswith(pc.CONSTRUIDA)), None)


# --- Escenarios, cada uno sobre el payload del fixture ------------------------

def _base():
    return payload_desde_dxf(FIXTURE)


def _rotulo(payload):
    return next(t for t in payload["textos"] if t["texto"] == ROTULO)


def _envolvente(payload):
    return next(r for r in payload["recintos"] if r["color"] == 10)


def _sin_rotulo():
    payload = _base()
    payload["textos"].remove(_rotulo(payload))
    return payload


def _rotulo_abreviado():
    payload = _base()
    _rotulo(payload)["texto"] = "S. construida cerrada"
    return payload


def _rotulo_con_mayusculas_y_acentos():
    payload = _base()
    _rotulo(payload)["texto"] = "SUPERFICIE  CONSTRUÍDA CERRADA"
    return payload


def _rotulo_de_la_exterior():
    payload = _base()
    _rotulo(payload)["texto"] = "Superficie construida exterior"
    return payload


def _envolvente_en_otra_capa_y_sin_color():
    """La envolvente sale de la capa de recintos y viaja como las demás capas:
    sin color. Es el caso que el arquitecto describió al firmar."""
    payload = _base()
    envolvente = _envolvente(payload)
    payload["recintos"].remove(envolvente)
    payload["otras_polilineas"].append({
        "handle": envolvente["handle"], "capa": "00 CONSTRUIDA",
        "cerrada": envolvente["cerrada"], "vertices": envolvente["vertices"]})
    return payload


def _otra_polilinea_mayor_al_alcance():
    """Un contorno de parcela en otra capa, MÁS GRANDE que la envolvente, cuyo
    borde superior pasa a 0,07 m del rótulo: el rótulo tiene dos candidatas."""
    payload = _base()
    payload["otras_polilineas"].append({
        "handle": "PARCELA", "capa": "00 PARCELA", "cerrada": True,
        "vertices": [[-1.0, -3.0], [13.0, -3.0], [13.0, 4.5], [-1.0, 4.5]]})
    return payload


def _dos_polilineas_rotuladas():
    """Una segunda envolvente que también contiene la vivienda, fuera del
    alcance del primer rótulo, con su propio rótulo a 0,2 m de su borde."""
    payload = _base()
    payload["otras_polilineas"].append({
        "handle": "ENV2", "capa": "00 CONSTRUIDA", "cerrada": True,
        "vertices": [[-0.6, -0.08], [12.0, -0.08], [12.0, 5.0], [-0.6, 5.0]]})
    otro = copy.deepcopy(_rotulo(payload))
    otro.update({"handle": "ROT2", "texto": "S. construida cerrada", "x": 6.0, "y": 5.2})
    payload["textos"].append(otro)
    return payload


def _rotulo_sin_altura():
    payload = _base()
    _rotulo(payload)["altura"] = None
    return payload


def _rotulo_lejos():
    payload = _base()
    _rotulo(payload)["y"] = 6.0
    return payload


def _rotulo_junto_a_una_pieza():
    """Dentro del salón, a 0,30 m de su borde y a 0,50 de la envolvente: señala
    una sola polilínea, y es una pieza, no la construida."""
    payload = _base()
    rotulo = _rotulo(payload)
    rotulo["x"], rotulo["y"] = 2.5, 3.7
    return payload


#: (escenario, ¿lleva cifra?, texto que tiene que estar en la nota si no)
ESCENARIOS = [
    (None, True, None),
    (_base, True, None),
    (_rotulo_abreviado, True, None),
    (_rotulo_con_mayusculas_y_acentos, True, None),
    (_envolvente_en_otra_capa_y_sin_color, True, None),
    (_sin_rotulo, False, "no rotula"),
    (_rotulo_de_la_exterior, False, "no rotula"),
    (_otra_polilinea_mayor_al_alcance, False, "no se elige ninguna"),
    (_dos_polilineas_rotuladas, False, "no se elige ninguna"),
    (_rotulo_sin_altura, False, "altura"),
    (_rotulo_lejos, False, "alturas de texto"),
    (_rotulo_junto_a_una_pieza, False, "no contiene"),
]
IDS = ["fixture_web", "payload_comando", "abreviado", "mayusculas_acentos",
       "otra_capa_sin_color", "sin_rotulo", "rotulo_de_la_exterior",
       "otra_mayor_al_alcance", "dos_rotuladas", "sin_altura", "lejos", "junto_a_pieza"]


@pytest.mark.parametrize("escenario, con_cifra, en_la_nota", ESCENARIOS, ids=IDS)
def test_c12_escenarios(escenario, con_cifra, en_la_nota):
    p = _plantilla(escenario() if escenario else None)
    if con_cifra:
        assert _construida(p) == pc._m2(_area_envolvente())
        assert _nota(p) is None
    else:
        assert _construida(p) == ""
        nota = _nota(p)
        assert nota and "C-12" in nota and en_la_nota in nota, nota


# --- Condición 1: más de una candidata, no se elige ---------------------------

def test_c12_con_dos_candidatas_para_el_rotulo_no_se_elige_ni_la_mayor_ni_la_primera():
    p = _plantilla(_otra_polilinea_mayor_al_alcance())
    assert _construida(p) == ""
    assert p.construida_handle is None
    nota = _nota(p)
    # Declara cuáles eran, las dos, con el handle del dibujo del arquitecto y no
    # con el del DXF que el servidor materializa (`APPID_HANDLE`).
    envolvente = _envolvente(_base())["handle"]
    assert "2 polilíneas" in nota and "PARCELA" in nota and envolvente in nota, nota


def test_c12_con_dos_polilineas_rotuladas_se_nombran_las_dos():
    p = _plantilla(_dos_polilineas_rotuladas())
    assert _construida(p) == ""
    assert len(p.construida_rotuladas) == 2
    assert "2 polilíneas rotuladas" in _nota(p)


# --- Condición 2: nunca por color ----------------------------------------------

def test_c12_una_polilinea_roja_sin_rotulo_no_es_la_construida():
    """El fixture conserva su envolvente ACI 10; sólo le falta el rótulo."""
    payload = _sin_rotulo()
    assert _envolvente(payload)["color"] == 10
    assert _construida(_plantilla(payload)) == ""


def test_c12_la_rotulada_cuenta_aunque_no_tenga_color_propio():
    payload = _envolvente_en_otra_capa_y_sin_color()
    assert not any(r["color"] == 10 for r in payload["recintos"])
    assert _construida(_plantilla(payload)) == pc._m2(_area_envolvente())


def _nombres_que_tocan_color(funcion):
    arbol = ast.parse(textwrap.dedent(inspect.getsource(funcion)))
    tocan = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Attribute) and "color" in nodo.attr.lower():
            tocan.append(nodo.attr)
        elif isinstance(nodo, ast.Name) and "color" in nodo.id.lower():
            tocan.append(nodo.id)
        elif isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) \
                and nodo.value.strip().lower() in ("color", "62"):
            tocan.append(nodo.value)
    return tocan


@pytest.mark.parametrize("funcion", [pc.medir_construida, pc.polilineas_del_plano,
                                     pc.rotulos_de_construida])
def test_c12_el_codigo_de_la_construida_no_lee_el_color(funcion):
    """Ni como respaldo: si alguien añade un `dxf.color` o un `get("color")` a
    estas funciones, esto se pone rojo antes de que llegue a un plano."""
    assert _nombres_que_tocan_color(funcion) == []


def _funcion_lsp(nombre):
    with open(LSP, encoding="utf-8") as fichero:
        codigo = fichero.read()
    ini = codigo.index("(defun %s " % nombre)
    fin = codigo.index("\n(defun ", ini + 10)
    return "\n".join(l.split(";")[0] for l in codigo[ini:fin].splitlines())


def test_c12_el_lsp_manda_las_otras_capas_sin_color_y_sin_decidir():
    cuerpo = _funcion_lsp("am:otras-polilineas")
    assert "62" not in cuerpo and "color" not in cuerpo.lower()
    assert "construida" not in cuerpo.lower(), "el .lsp no busca el rótulo: eso es del servidor"
    seleccion = re.search(r"\(ssget[^\n]*", cuerpo).group(0)
    assert "(0 . \\\"LWPOLYLINE\\\")" in seleccion.replace('"', '\\"')
    assert "(410 . \\\"Model\\\")" in seleccion.replace('"', '\\"')
    assert "(8 " not in seleccion, "no filtra por capa en el ssget: salta la de recintos en el bucle"
    recolectar = _funcion_lsp("am:recolectar")
    assert "(am:otras-polilineas capa)" in recolectar
    assert '\\"otras_polilineas\\":[' in recolectar


def test_c12_el_payload_de_otras_capas_no_trae_color():
    payload = _envolvente_en_otra_capa_y_sin_color()
    assert all("color" not in p for p in payload["otras_polilineas"])
    geometria = validar(payload)
    assert all("color" not in p for p in geometria.otras_polilineas)


# --- Condición 3: el guardián --------------------------------------------------

@pytest.mark.parametrize("escenario, _con_cifra, _nota_esperada", ESCENARIOS, ids=IDS)
def test_c12_guardian_cifra_solo_con_exactamente_una_polilinea_rotulada(
        escenario, _con_cifra, _nota_esperada):
    """La fila S. CONSTRUIDA C. sólo lleva cifra si hay exactamente una
    polilínea rotulada, y entonces esa cifra es su superficie y su handle es el
    que se publica. En todos los escenarios, los que la llevan y los que no."""
    p = _plantilla(escenario() if escenario else None)
    if _construida(p):
        assert len(p.construida_rotuladas) == 1, p.construida_rotuladas
        assert p.construida_handle == p.construida_rotuladas[0]
    else:
        assert p.construida_handle is None or not _construida(p)


def test_c12_guardian_directo_sobre_medir_construida():
    """Lo mismo sin pasar por la plantilla: `Construida.valor` no vacío implica
    una sola rotulada, en los dos escenarios que tienen más de una candidata."""
    for escenario in (_dos_polilineas_rotuladas, _otra_polilinea_mayor_al_alcance):
        doc, plano = _leer(escenario())
        p = pc.construir(doc, plano, "VT1/3", ambitos=CON_RESPUESTA)
        assert not _construida(p)
        assert p.construida_handle is None


# --- El camino del comando y el de la web leen igual (C-9) ---------------------

def _dxf_del_arquitecto(payload, ruta):
    """Un DXF «del arquitecto» hecho con un payload, **sin la marca de handle de
    origen**: un plano de AutoCAD no la lleva, y con ella la web leería los
    handles del payload y el simulador del `.lsp` los del fichero."""
    from analyzer.geometria_recibida import APPID_HANDLE

    SubidaMaterializada(validar(payload)).save(str(ruta))
    doc = parser.load_document(str(ruta))
    for entidad in doc.modelspace():
        if entidad.has_xdata(APPID_HANDLE):
            entidad.discard_xdata(APPID_HANDLE)
    doc.saveas(str(ruta))
    return ruta


def test_c12_una_construida_en_otra_capa_la_ven_igual_el_comando_y_la_web(tmp_path):
    """El «DXF del arquitecto» tiene la envolvente en otra capa. La web lo lee
    entero; el comando manda lo que `am:otras-polilineas` mandaría
    (`payload_desde_dxf`). Las dos vías tienen que escribir la misma cifra."""
    original = _dxf_del_arquitecto(_envolvente_en_otra_capa_y_sin_color(),
                                   tmp_path / "arquitecto.dxf")

    doc = parser.load_document(str(original))
    web = pc.construir(doc, parser.leer_plano(doc, layer="00 areas"), "VT1/3",
                       ambitos=CON_RESPUESTA)
    payload = payload_desde_dxf(str(original), capa="00 areas")
    assert any(p["capa"] == "00 CONSTRUIDA" for p in payload["otras_polilineas"])
    comando = _plantilla(payload)
    assert _construida(web) == _construida(comando) == pc._m2(_area_envolvente())
    # Y el mismo handle: el de SU dibujo, no el del DXF materializado.
    assert comando.construida_handle == web.construida_handle


def test_c12_la_nota_nombra_igual_por_las_dos_vias(tmp_path):
    """Medido el 2026-09-13 sobre `ejemplo.dxf`: la nota de VT6/2 decía «(A61863,
    CA4293)» por la web y «(31, 32)» por el comando. Una nota que se dibuja en su
    plano no puede nombrar polilíneas que no existen en él."""
    original = _dxf_del_arquitecto(_otra_polilinea_mayor_al_alcance(),
                                   tmp_path / "arquitecto.dxf")
    doc = parser.load_document(str(original))
    web = pc.construir(doc, parser.leer_plano(doc, layer="00 areas"), "VT1/3",
                       ambitos=CON_RESPUESTA)
    comando = _plantilla(payload_desde_dxf(str(original), capa="00 areas"))
    assert _nota(web) == _nota(comando), (_nota(web), _nota(comando))


def test_c12_las_otras_capas_no_cambian_la_medicion():
    """Mandar las polilíneas de las demás capas no puede tocar lo que se mide:
    las piezas, sus superficies y los totales salen iguales con y sin ellas."""
    con = _plantilla(_otra_polilinea_mayor_al_alcance())
    sin = _plantilla(_base())
    assert con.interiores == sin.interiores and con.exteriores == sin.exteriores
    assert con.cierre[0] == sin.cierre[0] and con.cierre[1] == sin.cierre[1]


def test_un_texto_que_llega_sin_altura_no_recibe_la_de_ezdxf():
    """ezdxf escribe 40 = 2,5 en un texto sin altura (y también si se le da 0).
    Medido el 2026-09-13 al ver rojo `test_c12_escenarios[sin_altura]`, y con él
    salió el mismo fallo en `D-14`: `alturas_de_rotulos` devolvía [2.5, …] con un
    payload sin alturas. Las dos lecturas pasan ahora por `altura_de_texto`."""
    from analyzer import maquetacion_cuadro as mq

    payload = _base()
    for texto in payload["textos"]:
        texto["altura"] = None
    doc, plano = _leer(payload)
    assert mq.alturas_de_rotulos(doc, [r.label for r in plano.rooms if r.label]) == []
    assert all(r.alcance_m is None for r in pc.rotulos_de_construida(doc, 1.0))

    # Y con altura, la de verdad: nada de esto toca un texto que sí la trae.
    doc, plano = _leer(_base())
    assert mq.alturas_de_rotulos(doc, [r.label for r in plano.rooms if r.label])
    assert [round(r.alcance_m, 3) for r in pc.rotulos_de_construida(doc, 1.0)] == [0.375]


@pytest.mark.parametrize("otra, motivo", [
    ({"handle": "X", "vertices": [[0, 0], [1, 0], [1, 1]]}, "sin capa"),
    ({"handle": "X", "capa": "00 AREAS", "vertices": [[0, 0], [1, 0], [1, 1]]}, "capa de recintos"),
])
def test_c12_una_otra_polilinea_mal_formada_se_rechaza_con_motivo(otra, motivo):
    payload = _base()
    payload["otras_polilineas"].append(otra)
    with pytest.raises(PayloadInvalido, match=motivo):
        validar(payload)
