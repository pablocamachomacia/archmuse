# -*- coding: utf-8 -*-
"""`D-14` · La tabla se maqueta en el servidor, dentro de la ventana que marca el
arquitecto, y ninguna palabra se parte.

**El fallo, verificado en AutoCAD 2027 el 2026-09-13.** La tabla salió con el
texto varias veces más grande que el edificio y columnas tan estrechas que
partían las palabras letra a letra. `am:dibujar-cuadro` creaba la tabla con
fila 1,0 y columna 14,0 fijas y sin fijar la altura de texto: **el tamaño era
criterio y vivía en LISP**.

**Decisión firmada por Pablo:** el comando pide una ventana de dos esquinas
—declaración explícita, manda sobre cualquier deducción— y el servidor devuelve
la tabla resuelta. Si con una altura legible no cabe, no se encoge ni se
desborda: se niega y pide una ventana mayor. La altura mínima sale del cuadro
del arquitecto o, si no hay, de los rótulos de estancia del plano.
"""
from __future__ import annotations

import os
import re
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

LSP = open(os.path.join(RAIZ, "autocad", "archmuse.lsp"), encoding="utf-8").read()

#: Una tabla con la forma de la plantilla: título, encabezados, cuerpo y cierre.
CELDAS = [
    (0, 0, "CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA"),
    (1, 0, "ESPACIOS INTERIORES"), (1, 1, "SUPERFICIES UTILES INT."),
    (1, 2, "ESPACIOS EXTERIORES"), (1, 3, "SUPERFICIES UTILES EXT."),
    (2, 0, "Salón/cocina"), (2, 1, "20,00 m²"), (2, 2, "Terraza"), (2, 3, "4,50 m²"),
    (3, 0, "Dormitorio 1"), (3, 1, "12,00 m²"),
    (4, 0, "TOTAL SUP. INTERIOR (m2)"), (4, 1, "43,70 m²"),
    (4, 2, "TOTAL SUP. EXTERIOR (m2)"), (4, 3, "4,50 m²"),
    (5, 0, "TOTAL S. UTIL(m2)"),
    (6, 0, "VIVIENDA TIPO"), (6, 1, "VT1/3"), (6, 2, "NUMERO UDS:"),
]
NOTAS = [
    "TOTAL S. UTIL(m2): la superficie útil interior y la exterior no se suman en "
    "una sola cifra; es criterio del técnico que firma (C-1).",
    "NUMERO UDS: el plano lo declara, pero leer declaraciones del plano (C-8) no "
    "está implementado todavía.",
]
ALTURA_MINIMA = 0.125
GRANDE = ((100.0, 50.0), (160.0, 20.0))


def _mq():
    from analyzer import maquetacion_cuadro
    return maquetacion_cuadro


def test_ninguna_palabra_es_mas_ancha_que_su_columna():
    mq = _mq()
    m = mq.maquetar(CELDAS, NOTAS, GRANDE, ALTURA_MINIMA)
    assert isinstance(m, mq.Maquetacion), m
    for fila, columna, texto in CELDAS:
        altura = m.altura_titulo if fila == 0 else m.altura_texto
        ancho = mq.ancho_de_texto(texto, altura) + 2 * m.margen
        disponible = sum(m.anchos) if fila == 0 else m.anchos[columna]
        assert ancho <= disponible + 1e-9, (texto, ancho, disponible)


def test_las_notas_van_debajo_fuera_del_marco_y_sin_salirse_de_ancho():
    mq = _mq()
    m = mq.maquetar(CELDAS, NOTAS, GRANDE, ALTURA_MINIMA)
    # El borde de la tabla con la fila del título, que es más alta: calcularlo con
    # todas las filas iguales es lo que habría puesto las notas dentro.
    assert m.alto_tabla == pytest.approx(m.alto_fila_titulo + (m.n_filas - 1) * m.alto_fila)
    base_de_la_tabla = m.esquina[1] - m.alto_tabla
    assert m.notas, "las notas se han perdido"
    for x, y, linea in m.notas:
        assert y < base_de_la_tabla
        assert mq.ancho_de_texto(linea, m.altura_texto) <= m.ancho_total + 1e-9


# --- Estilo, capa y color propios (3.3.0) -----------------------------------
#
# **Lo que estos tests NO prueban, y es lo que falló** («C-7, otra vez» en los
# criterios): que AutoCAD dibuje las filas del alto que se le pide. Aquí se
# prueba que lo que se le pide no le da motivo para crecer, y que el `.lsp` se lo
# pide; que lo haga, sólo se ve en AutoCAD (checklist, casillas 13 a 16).

def test_las_proporciones_son_las_de_los_cuadros_del_arquitecto():
    """Medidas el 2026-09-13 en `ejemplo`, `v1plantas`, `v2s` y `v3s`: fila 0,18,
    título 0,12 en fila de 0,22, texto 0,09, cuatro columnas de 1,27."""
    mq = _mq()
    m = mq.maquetar(CELDAS, NOTAS, GRANDE, ALTURA_MINIMA)
    h = m.altura_texto
    assert m.alto_fila / h == pytest.approx(0.18 / 0.09)
    assert m.altura_titulo / h == pytest.approx(0.12 / 0.09)
    assert m.alto_fila_titulo / h == pytest.approx(0.22 / 0.09)
    assert len(set(round(a, 9) for a in m.anchos)) == 1, "columnas desiguales: %s" % (m.anchos,)


def test_ninguna_fila_tiene_motivo_para_crecer_en_autocad():
    """Una fila de tabla no mide menos que su texto y sus dos márgenes. Si lo que
    se pide cumple eso, AutoCAD no tiene por qué agrandarla — que es lo que pasó
    con el margen vertical 1,5 heredado de `Standard`."""
    mq = _mq()
    m = mq.maquetar(CELDAS, NOTAS, GRANDE, ALTURA_MINIMA)
    assert m.margen_vertical > 0
    assert m.altura_texto + 2 * m.margen_vertical <= m.alto_fila + 1e-9
    assert m.altura_titulo + 2 * m.margen_vertical <= m.alto_fila_titulo + 1e-9


def test_la_capa_el_color_y_el_estilo_los_decide_el_servidor_y_llegan_antes_que_las_notas():
    mq = _mq()
    d = mq.a_dict(mq.maquetar(CELDAS, NOTAS, GRANDE, ALTURA_MINIMA))
    assert d["capa"] == "ARCHMUSE - CUADRO" and d["color_capa"] == 7
    assert d["estilo_tabla"] == "ARCHMUSE"
    claves = list(d)
    for clave in ("altura_titulo", "alto_fila_titulo", "margen_vertical",
                  "estilo_tabla", "capa", "color_capa"):
        assert claves.index(clave) < claves.index("notas"), clave


def _cuerpo_del_lsp(nombre):
    cuerpo = LSP[LSP.index("(defun %s " % nombre):]
    return cuerpo[:cuerpo.find("\n(defun ", 1)]


def test_el_lsp_no_hereda_nada_del_plano():
    """Estilo de tabla propio, capa propia, PorCapa, margen vertical, fila del
    título y altura en TODAS las celdas —la vacía también—, todo leído del
    servidor."""
    dibujar = _cuerpo_del_lsp("am:dibujar-cuadro")
    for clave in ("altura_titulo", "alto_fila_titulo", "margen_vertical",
                  "estilo_tabla", "capa", "color_capa"):
        assert '"%s"' % clave in dibujar, clave
    assert "(am:estilo-de-tabla doc estilo-tabla" in dibujar
    # Desde la 3.4.1 van por `am:intentar`: si fallan, lo dicen (test_lsp_fallos_con_causa).
    assert "'vla-put-Layer (list tabla capa)" in dibujar
    assert "'vla-put-Color (list tabla 256)" in dibujar
    assert "'vla-put-VertCellMargin (list tabla margen-v)" in dibujar
    assert "(vla-SetRowHeight tabla 0 alto-t)" in dibujar
    # Las celdas se recorren enteras (fila × columna), no sólo las que traen texto.
    assert re.search(r"\(while \(< c cols\)\s+\(am:intentar [^']*'vla-SetCellTextStyle", dibujar)
    assert "'vla-put-Layer (list mt capa)" in dibujar and "'vla-put-Color (list mt 256)" in dibujar
    estilo = _cuerpo_del_lsp("am:estilo-de-tabla")
    assert '"AcDbTableStyle"' in estilo and "(vla-put-VertCellMargin ts margen-v)" in estilo


def test_la_web_dibuja_en_la_misma_capa_color_y_proporciones(tmp_path, monkeypatch):
    """**Con un color que no es el de por defecto.** La primera versión de este
    test comprobaba el 7 y pasaba igual con la capa creada sin color: `ezdxf`
    pone 7 por defecto. Se vio reintroduciendo el fallo a propósito — no se puso
    rojo. Ahora la maquetación pide el 3, y sólo pasa si la web usa ese color."""
    import dataclasses

    import ezdxf

    from analyzer import maquetacion_cuadro as mq
    from analyzer.cuadro_superficies_export import exportar_cuadro_relleno

    assert mq.COLOR_DE_CAPA == 7
    original = mq.maquetar
    monkeypatch.setattr(mq, "maquetar", lambda *a, **k: dataclasses.replace(
        original(*a, **k), color_capa=3))

    fixture = os.path.join(RAIZ, "tests", "fixtures", "cuadro_sintetico", "cuadro_sintetico.dxf")
    destino = tmp_path / "web.dxf"
    exportar_cuadro_relleno(fixture, str(destino))
    doc = ezdxf.readfile(str(destino))
    assert doc.layers.get("ARCHMUSE - CUADRO").dxf.color == 3
    textos = {e.plain_text(): e.dxf.char_height
              for e in doc.modelspace().query('MTEXT[layer=="ARCHMUSE - CUADRO"]')}
    titulo = textos["CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA"]
    cuerpo = textos["ESPACIOS INTERIORES"]
    assert titulo / cuerpo == pytest.approx(0.12 / 0.09)


def test_una_ventana_pequena_no_se_encoge_se_niega_y_dice_cuanto_hace_falta():
    mq = _mq()
    resultado = mq.maquetar(CELDAS, NOTAS, ((0.0, 0.0), (1.0, 1.0)), ALTURA_MINIMA)
    assert isinstance(resultado, mq.NoCabe), resultado
    assert resultado.ancho_necesario > 1.0 or resultado.alto_necesario > 1.0
    assert "ventana" in resultado.motivo.lower()


def test_la_ventana_manda_y_todo_cabe_dentro():
    mq = _mq()
    pequena = mq.maquetar(CELDAS, NOTAS, ((0.0, 30.0), (12.0, 0.0)), ALTURA_MINIMA)
    grande = mq.maquetar(CELDAS, NOTAS, ((0.0, 60.0), (24.0, 0.0)), ALTURA_MINIMA)
    assert isinstance(pequena, mq.Maquetacion) and isinstance(grande, mq.Maquetacion)
    assert grande.altura_texto > pequena.altura_texto
    for m, (ancho, alto) in ((pequena, (12.0, 30.0)), (grande, (24.0, 60.0))):
        assert m.altura_texto >= ALTURA_MINIMA
        assert m.ancho_total <= ancho + 1e-9 and m.alto_total <= alto + 1e-9


def test_las_esquinas_valen_en_cualquier_orden():
    mq = _mq()
    a = mq.maquetar(CELDAS, NOTAS, ((100.0, 50.0), (160.0, 20.0)), ALTURA_MINIMA)
    b = mq.maquetar(CELDAS, NOTAS, ((160.0, 20.0), (100.0, 50.0)), ALTURA_MINIMA)
    assert a == b


def test_no_se_dibuja_encima_del_cuadro_del_arquitecto():
    mq = _mq()
    resultado = mq.maquetar(CELDAS, NOTAS, GRANDE, ALTURA_MINIMA,
                            cajas_prohibidas=[((120.0, 30.0), (130.0, 40.0))])
    assert isinstance(resultado, mq.NoCabe)
    assert "cuadro" in resultado.motivo.lower()


def test_la_altura_minima_sale_del_cuadro_y_si_no_de_los_rotulos():
    mq = _mq()
    assert mq.altura_minima(0.09, [0.125, 0.125, 0.3]) == 0.09
    assert mq.altura_minima(None, [0.1, 0.125, 0.125, 0.3]) == 0.125
    assert mq.altura_minima(None, []) is None


def test_el_lsp_no_lleva_medidas_de_tabla_escritas_a_mano():
    """El tamaño era criterio y vivía en LISP. Ya no."""
    cuerpo = LSP[LSP.index("(defun am:dibujar-cuadro "):]
    cuerpo = cuerpo[:cuerpo.find("\n(defun ", 1)]
    assert not re.search(r"\(\*\s*\d+(\.\d+)?\s+k\)", cuerpo), (
        "am:dibujar-cuadro sigue calculando medidas de la tabla con constantes")
    # Y ninguna medida literal pasada directamente: `(vla-SetRowHeight tabla f 1.0)`
    # es el mismo fallo sin la multiplicación.
    literales = re.findall(
        r"\(vla-(?:SetColumnWidth|SetRowHeight|SetCellTextHeight|SetTextHeight|"
        r"put-HorzCellMargin|put-VertCellMargin)"
        r"(?:\s+[^\s()]+)*?\s+(-?\d+(?:\.\d+)?)\s*\)", cuerpo)
    assert not literales, "am:dibujar-cuadro pasa medidas escritas a mano: %s" % literales
    anadir = re.search(r"\(vla-AddTable\s+ms\s+\(vlax-3d-point\s+\(list[^)]*\)\)"
                       r"\s+([^\s()]+)\s+([^\s()]+)\s+([^\s()]+)\s+(\([^)]*\)|[^\s()]+)\)",
                       cuerpo)
    assert anadir, "no se encuentra la llamada a vla-AddTable"
    assert not [a for a in anadir.groups() if re.fullmatch(r"-?\d+(\.\d+)?", a)], (
        "vla-AddTable recibe filas, columnas o medidas escritas a mano: %s" % (anadir.groups(),))


def test_el_comando_pide_un_punto_y_el_tamano_lo_pone_el_servidor():
    """**Invertido el 2026-09-13 (3.4.0), por petición de Pablo.** Hasta ese día se
    llamaba `test_el_comando_pide_una_ventana_y_no_un_punto` y exigía dos esquinas
    con `getcorner`: «la ventana manda». Pablo lo cambió tras probarlo en AutoCAD:
    «el arquitecto no debe adivinar cuánto mide la tabla ni recibir "marca una
    ventana mayor"».

    Lo que no vuelve es el punto de ANTES de la plantilla fija: aquel lo seguía
    un tamaño escrito en este fichero (`am:punto-a-la-derecha`). Éste lo sigue un
    tamaño que decide el servidor."""
    comando = LSP[LSP.index("(defun c:ARCHMUSE "):]
    pedir = LSP[LSP.index("(defun am:pedir-punto "):]
    pedir = pedir[:pedir.find("\n(defun ", 1)]
    assert "(am:pedir-punto)" in comando
    assert "getpoint" in pedir and "getcorner" not in LSP
    assert "am:pedir-ventana" not in LSP
    assert '"\\"punto\\":["' in _cuerpo_del_lsp("am:con-dibujo")
    assert "Pincha donde quieres el cuadro" not in LSP
    assert "am:punto-a-la-derecha" not in LSP
    assert "ventana mayor" not in LSP.lower()


# --- El punto único (3.4.0) --------------------------------------------------

def test_con_un_punto_la_tabla_sale_a_la_altura_legible_colgada_de_el():
    mq = _mq()
    m = mq.maquetar_en_punto(CELDAS, NOTAS, (100.0, 50.0), ALTURA_MINIMA)
    assert isinstance(m, mq.Maquetacion), m
    assert m.esquina == (100.0, 50.0)
    assert m.altura_texto == pytest.approx(ALTURA_MINIMA)


@pytest.mark.parametrize("altura", [0.05, 0.09, 0.125, 2.5, 250.0])
def test_con_un_punto_nunca_falta_sitio_se_mida_en_lo_que_se_mida(altura):
    """Metros, centímetros o milímetros: el tamaño sale del texto, así que no hay
    ninguna escala a la que el arquitecto tenga que buscar más hueco."""
    mq = _mq()
    m = mq.maquetar_en_punto(CELDAS, NOTAS, (0.0, 0.0), altura)
    assert isinstance(m, mq.Maquetacion), m


def test_con_un_punto_solo_se_niega_si_pisaria_su_cuadro_y_pide_otro_punto():
    mq = _mq()
    encima = mq.maquetar_en_punto(CELDAS, NOTAS, (100.0, 50.0), ALTURA_MINIMA,
                                  cajas_prohibidas=[((100.5, 49.5), (101.0, 49.9))])
    assert isinstance(encima, mq.NoCabe)
    assert "otro punto" in encima.motivo and "ventana" not in encima.motivo.lower()
    lejos = mq.maquetar_en_punto(CELDAS, NOTAS, (100.0, 50.0), ALTURA_MINIMA,
                                 cajas_prohibidas=[((0.0, 0.0), (1.0, 1.0))])
    assert isinstance(lejos, mq.Maquetacion)


def test_el_servidor_acepta_el_punto_y_devuelve_la_tabla_resuelta():
    import app as srv
    from analyzer.geometria_recibida import payload_desde_dxf

    fixture = os.path.join(RAIZ, "tests", "fixtures", "cuadro_sintetico", "cuadro_sintetico.dxf")
    cuerpo = dict(payload_desde_dxf(fixture), punto=[40.0, 10.0],
                  ambitos={"TRASTERO": "interior"})
    datos = srv.app.test_client().post("/api/medicion-geometria", json=cuerpo).get_json()
    maquetacion = datos["repartos"][0]["cuadro_a_dibujar"]["maquetacion"]
    assert maquetacion["cabe"] is True
    assert (maquetacion["x"], maquetacion["y"]) == (40.0, 10.0)
