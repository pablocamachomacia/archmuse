# -*- coding: utf-8 -*-
"""ArchMuse no se lee a sí mismo: lo que dibuja no es un dato del plano.

**El aviso (Pablo, 2026-09-15, AutoCAD).** En una segunda ejecución sobre el
plano de referencia del estudio, el comando dijo «He encontrado 2 cuadro(s)»:
contó como cuadro del arquitecto la tabla que él mismo había dibujado, que lleva
el mismo título.

**Medido el 2026-09-15**, fuera del repositorio, sobre ese plano. La vía del
comando se simuló contra el servidor con lo que el `.lsp` leería de la tabla
anterior; la web, con dos exportaciones encadenadas:

- **Vía del comando.** Las celdas de la tabla propia no entran en el cálculo, y
  tres pasadas dan las mismas cifras. Pero su caja cuenta como «tu cuadro» (el
  mismo punto se rechaza por pisarlo) y sus alturas y estilo, como los del
  arquitecto.
- **Vía web: la segunda exportación deja de escribir las cifras.** El cuadro
  exportado son `LINE` y `MTEXT` sueltos, y su casilla «VT1/3» se lee como un
  segundo rótulo de vivienda: las piezas quedan entre dos «VT1/3» y el reparto se
  bloquea (`C-2`, `C-14`).

**Cómo se reconoce lo propio.** Por las dos marcas que ya lleva todo lo dibujado
desde la 3.3.0, sin escribir nada nuevo en AutoCAD: la **capa** (`ARCHMUSE -
CUADRO` y `ARCHMUSE - BORRADOR`) y, en la tabla del comando, el **estilo de tabla**
`ARCHMUSE`.

Todo contra `tests/fixtures/cuadro_sintetico/`, que no es de nadie.
"""
from __future__ import annotations

import collections
import os
import re
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import cuadro_superficies as cs  # noqa: E402
from analyzer import maquetacion_cuadro as mq  # noqa: E402
from analyzer import marca_borrador as mb  # noqa: E402
from analyzer import parser  # noqa: E402
from analyzer.geometria_recibida import payload_desde_dxf  # noqa: E402

FIXTURE = os.path.join(RAIZ, "tests", "fixtures", "cuadro_sintetico", "cuadro_sintetico.dxf")
LSP = open(os.path.join(RAIZ, "autocad", "archmuse.lsp"), encoding="utf-8").read()
#: **Justo debajo del plano sintético** (x de 0 a 11,4, y de −1,6 a 4,2) y lejos
#: de su cuadro (x de 20 a 30). Cerca a propósito: en el plano de referencia el
#: segundo «VT1/3» quedó a 17 m de las piezas y bastó para volver dudoso el
#: reparto; una tabla lejana no lo reproduce (medido: con el punto en x=40 este
#: test pasaba con el fallo dentro).
PUNTO = [0.0, -2.5]
#: Donde va la segunda tabla: lejos, para que no pise la primera.
PUNTO_LEJOS = [80.0, 6.0]


@pytest.fixture(scope="module")
def cliente():
    import app as srv

    return srv.app.test_client()


@pytest.fixture(scope="module")
def plano_limpio(tmp_path_factory):
    """El fixture sin el trastero: **medición limpia**. Con el trastero la primera
    pasada ya no escribe cifras, y dos cuadros sin cifras son iguales aunque la
    segunda haya leído la tabla de la primera — medido: así el test pasaba con
    el fallo dentro."""
    doc = parser.load_document(FIXTURE)
    msp = doc.modelspace()
    trastero = next(e for e in msp.query("MTEXT") if parser._texto_de(e) == "Trastero")
    x, y = parser._punto_de_texto(trastero)
    from shapely.geometry import Point, Polygon

    for e in list(msp.query("LWPOLYLINE")):
        puntos = parser._polyline_points(e)
        if len(puntos) >= 3 and Polygon(puntos).contains(Point(x, y)) and \
                Polygon(puntos).area < 5.0:
            msp.delete_entity(e)
    msp.delete_entity(trastero)
    ruta = tmp_path_factory.mktemp("limpio") / "sin_trastero.dxf"
    doc.saveas(str(ruta))
    return str(ruta)


def _medir(cliente, cuerpo):
    respuesta = cliente.post("/api/medicion-geometria", json=cuerpo)
    assert respuesta.status_code == 200, respuesta.get_data(as_text=True)[:500]
    repartos = respuesta.get_json()["repartos"]
    assert repartos and repartos[0].get("ok", True), repartos
    return repartos[0]


def _textos_de_archmuse(cuadro):
    """Lo que queda en el dibujo tras dibujar `cuadro`, como textos sueltos en las
    capas de ArchMuse: cada casilla (una tabla descompuesta, o la exportación
    web), cada nota al pie y la marca de borrador."""
    m = cuadro["maquetacion"]
    textos = []
    for celda in cuadro["celdas"]:
        f, c = celda["fila"], celda["columna"]
        x = m["x"] + sum(m["anchos"][:c]) + m["anchos"][c] / 2
        y = m["y"] - (m["alto_fila_titulo"] / 2 if f == 0
                      else m["alto_fila_titulo"] + (f - 1) * m["alto_fila"] + m["alto_fila"] / 2)
        textos.append({"handle": "C%d_%d" % (f, c), "capa": mq.CAPA, "texto": celda["texto"],
                       "tipo": "MTEXT", "x": x, "y": y, "altura": m["altura_texto"],
                       "estilo": "Standard"})
    for i, nota in enumerate(m["notas"]):
        textos.append({"handle": "N%d" % i, "capa": mq.CAPA, "texto": nota["linea"],
                       "tipo": "MTEXT", "x": nota["x"], "y": nota["y"],
                       "altura": m["altura_texto"], "estilo": "Standard"})
    textos.append({"handle": "M0", "capa": mb.CAPA_DXF, "texto": "BORRADOR", "tipo": "MTEXT",
                   "x": m["marca_x"], "y": m["marca_y"], "altura": m["altura_texto"],
                   "estilo": "Standard"})
    return textos


# --- 1. Vía del comando: los textos que dibujó ArchMuse -----------------------

def test_via_comando_lo_que_dibujo_archmuse_no_cambia_la_medicion(cliente, plano_limpio):
    primera = _medir(cliente, dict(payload_desde_dxf(plano_limpio), punto=PUNTO))
    assert primera["medicion_limpia"], "el test ha dejado de reproducir el caso limpio"
    cuadro = primera["cuadro_a_dibujar"]
    assert cuadro["maquetacion"]["cabe"], "el test no ha podido colocar la primera tabla"
    celdas = [c["texto"] for c in cuadro["celdas"]]
    assert any(c.startswith("VT1") for c in celdas), (
        "la tabla ya no lleva el nombre de la vivienda: este test ha dejado de reproducir el caso")

    segunda_cuerpo = payload_desde_dxf(plano_limpio)
    segunda_cuerpo["textos"] += _textos_de_archmuse(cuadro)
    segunda_cuerpo["punto"] = PUNTO_LEJOS
    segunda = _medir(cliente, segunda_cuerpo)

    assert [c["texto"] for c in segunda["cuadro_a_dibujar"]["celdas"]] == celdas, (
        "la segunda pasada escribe otras cifras: ArchMuse ha leído su propia tabla como "
        "rótulos del plano")
    assert segunda["no_escritas"] == primera["no_escritas"]


# --- 2. Vía web: exportar lo ya exportado --------------------------------------

def _textos_en_capa(ruta, capa):
    doc = parser.load_document(ruta)
    return collections.Counter(
        (round(e.dxf.insert.x, 3), round(e.dxf.insert.y, 3), e.plain_text())
        for e in doc.modelspace().query('MTEXT[layer=="%s"]' % capa))


def test_via_web_exportar_dos_veces_escribe_las_mismas_cifras(tmp_path, plano_limpio):
    from analyzer.cuadro_superficies_export import exportar_cuadro_relleno

    e1, movido, e2 = (str(tmp_path / n) for n in ("e1.dxf", "e1_movido.dxf", "e2.dxf"))
    exportar_cuadro_relleno(plano_limpio, e1)

    # El arquitecto recoloca el cuadro de ArchMuse junto a su planta: todo lo de
    # las capas de ArchMuse, con su esquina superior izquierda en `PUNTO`. Cerca,
    # por lo mismo que en el test del comando.
    doc = parser.load_document(e1)
    propias = [e for e in doc.modelspace() if e.dxf.layer in (mq.CAPA, mb.CAPA_DXF)]
    assert propias, "la exportación no ha dibujado nada en las capas de ArchMuse"
    # Sin las coordenadas absurdas: la marca de borrador del fixture sale en 1e+20
    # (medido el 2026-09-15; ver `docs/PROGRESS.md`), y con ella la caja era
    # infinita, la tabla se movía al infinito y el test pasaba con el fallo dentro.
    xs = [v for e in propias if e.dxftype() in ("MTEXT", "LINE")
          for v in ([e.dxf.insert.x] if e.dxftype() == "MTEXT" else [e.dxf.start.x, e.dxf.end.x])
          if abs(v) < 1e6]
    ys = [v for e in propias if e.dxftype() in ("MTEXT", "LINE")
          for v in ([e.dxf.insert.y] if e.dxftype() == "MTEXT" else [e.dxf.start.y, e.dxf.end.y])
          if abs(v) < 1e6]
    dx, dy = PUNTO[0] - min(xs), PUNTO[1] - max(ys)
    for e in propias:
        e.translate(dx, dy, 0)
    doc.saveas(movido)

    exportar_cuadro_relleno(movido, e2)

    primera = _textos_en_capa(movido, mq.CAPA)
    segunda = _textos_en_capa(e2, mq.CAPA) - primera
    assert primera, "la exportación no ha escrito nada: el test no prueba nada"
    assert sorted(t for _x, _y, t in primera.elements()) == \
        sorted(t for _x, _y, t in segunda.elements()), (
        "la segunda exportación escribe otra cosa: ArchMuse ha leído su propio cuadro")


def test_via_web_un_cuadro_en_la_capa_de_archmuse_no_es_un_cuadro_del_arquitecto(tmp_path):
    """Un DXF guardado desde AutoCAD después del comando lleva su `ACAD_TABLE`, con
    el mismo título, en `ARCHMUSE - CUADRO`."""
    texto = open(FIXTURE, encoding="utf-8").read()
    m = re.search(r"  0\nACAD_TABLE\n  5\n(\w+)\n(.*?)(?=  0\n)", texto, re.S)
    assert m, "el fixture ya no tiene su ACAD_TABLE"
    copia = m.group(0).replace("  5\n%s\n" % m.group(1), "  5\nFFFF0\n", 1)
    copia = re.sub(r"  8\n[^\n]+\n", "  8\n%s\n" % mq.CAPA, copia, count=1)
    copia = re.sub(r" 10\n[^\n]+\n", " 10\n60.0\n", copia, count=1)
    ruta = tmp_path / "con_tabla_de_archmuse.dxf"
    ruta.write_text(texto.replace(m.group(0), m.group(0) + copia, 1), encoding="utf-8")

    doc = parser.load_document(str(ruta))
    assert len(list(doc.modelspace().query("ACAD_TABLE"))) == 2, "la copia no ha entrado"
    assert len(cs.detectar_cuadros_superficies(doc)) == 1
    cajas, _alturas = cs.cajas_y_alturas_de_los_cuadros(doc)
    assert len(cajas) == 1


def test_las_capas_que_reconoce_son_las_que_dibuja():
    """Entre `propio`, `maquetacion_cuadro` y `marca_borrador` no se comparte la
    constante (`parser` no debe cargar reportlab): se comparan."""
    from analyzer import propio

    assert mq.CAPA in propio.CAPAS_DE_ARCHMUSE
    assert mb.CAPA_DXF in propio.CAPAS_DE_ARCHMUSE


# --- 3. El .lsp: su tabla no es un cuadro del arquitecto ------------------------

def test_el_comando_no_cuenta_su_propia_tabla_como_cuadro_del_arquitecto():
    capa = re.search(r'\(setq \*am:capa-del-cuadro\* "([^"]+)"\)', LSP)
    estilo = re.search(r'\(setq \*am:estilo-de-tabla-propio\* "([^"]+)"\)', LSP)
    assert capa and estilo, "el .lsp no declara la capa y el estilo de su tabla"
    assert capa.group(1) == mq.CAPA, "el .lsp reconoce su tabla por otra capa que la que dibuja"
    assert estilo.group(1) == mq.ESTILO_DE_TABLA

    ini = LSP.index("(defun am:tabla-de-archmuse-p ")
    cuerpo = LSP[ini:LSP.index("\n(defun ", ini + 10)]
    assert "vla-get-Layer" in cuerpo and "*am:capa-del-cuadro*" in cuerpo
    assert "vla-get-StyleName" in cuerpo and "*am:estilo-de-tabla-propio*" in cuerpo

    ini = LSP.index("(defun am:buscar-cuadros ")
    buscar = LSP[ini:LSP.index("\n(defun ", ini + 10)]
    assert "(am:tabla-de-archmuse-p obj)" in buscar, (
        "am:buscar-cuadros no descarta las tablas de ArchMuse: la segunda pasada las "
        "cuenta como cuadros del arquitecto")
