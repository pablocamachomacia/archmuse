# -*- coding: utf-8 -*-
"""La tabla en el plano: dónde va y qué dicen sus notas (Pablo, 2026-09-15, 0.3.12).

**Lo que vio en el maestro del estudio:**

1. **Colocación.** La tabla y sus notas se dibujaron encima del plano. «El clic es
   orientativo: si la tabla o sus notas iban a pisar geometría, ArchMuse la desplaza
   al hueco libre más cercano, al lado de la vivienda y sin tapar nada. Dice en la
   línea de comandos dónde la ha puesto y por qué la ha movido.»
2. **Notas.** «Demasiado texto y mal presentado. En el dibujo: como mucho 3-4 líneas,
   cortas y en lenguaje de arquitecto. Los motivos repetidos se agrupan en una línea
   ("8 piezas sin nombre reconocible"). El detalle completo va a la línea de comandos
   y al log, no al plano. Mismo ancho que la tabla, sin cortar palabras, tamaño de
   texto proporcionado y legible al imprimir. La marca de borrador se mantiene
   siempre.»

Planos y tablas **sintéticos**. Lo que el código calcula no es lo que se ve: el
resultado se ha revisado además renderizado a PNG (`docs/PROGRESS.md`).
"""
from __future__ import annotations

import pytest

from analyzer import maquetacion_cuadro as mq
from analyzer import plantilla_cuadro as pc

CELDAS = [(0, 0, pc.TITULO)] + [(1, c, t) for c, t in enumerate(pc.ENCABEZADOS)] + [
    (2, 0, "Salón/cocina"), (2, 1, "23,24 m²"), (2, 2, "Terraza"), (2, 3, "3,32 m²"),
    (3, 0, "Dormitorio 1"), (3, 1, "12,47 m²"),
]


def _plantilla(notas_por_motivo):
    lineas = tuple("%s: %s" % (", ".join(e), m) for e, m in notas_por_motivo)
    return pc.Plantilla(vivienda="VT1/3", interiores=(), exteriores=(), cierre=(), notas=lineas,
                        preguntas=(), sin_fila=(), impedimentos=(),
                        notas_por_motivo=tuple((tuple(e), m) for e, m in notas_por_motivo))


SIN_NOMBRE = ["Pieza %d (4,00 m²)" % i for i in range(1, 9)]
MUCHAS = [
    (SIN_NOMBRE, "no tiene rótulo: no se sabe qué estancia es ni en qué lado del cuadro va. "
                 "Está medida y no tiene fila (C-6)."),
    (["(sin rótulo) (8,63 m²)"], "tiene dos nombres dentro («Tendedero» y «Terraza»): no se "
                                 "elige ninguno. Está medida y no tiene fila (C-18)."),
    (["Baño", "Aseo"], "se solapa con otra pieza dibujada: cuenta metros dos veces y no se "
                       "escribe su cifra."),
    ([pc.TOTAL_INTERIOR, pc.TOTAL_EXTERIOR], "alguna fila de este lado no lleva cifra, y un "
                                             "total sin ella sería falso."),
    ([pc.TOTAL_UTIL], "ni la superficie útil interior ni la exterior se pueden afirmar (ver sus "
                      "notas), y el total no se calcula sobre una cifra bloqueada (C-14)."),
    ([pc.CONSTRUIDA], "el rótulo de la construida (A1) tiene 2 polilíneas a menos de 0,38 m de "
                      "su borde (A2, A3): no se elige ninguna (C-12)."),
    ([pc.NUMERO_UDS.rstrip(":")], pc.MOTIVO_NUMERO_UDS),
]


# --- 2. Notas ------------------------------------------------------------------------

def test_los_motivos_repetidos_se_agrupan_en_una_linea_con_su_cuenta():
    notas = pc.notas_del_dibujo(_plantilla(MUCHAS))
    assert "8 piezas sin nombre reconocible" in notas, notas


def test_en_el_dibujo_van_como_mucho_cuatro_lineas_cortas():
    notas = pc.notas_del_dibujo(_plantilla(MUCHAS))
    assert 1 <= len(notas) <= 4, notas
    assert all(len(n) <= 45 for n in notas), notas
    assert notas[-1].endswith("en la línea de comandos"), notas
    for jerga in ("C-6", "C-12", "C-14", "C-18", "D-13", "polilínea", "handle", "«"):
        assert all(jerga not in n for n in notas), (jerga, notas)


def test_una_sola_nota_sin_nada_mas_no_manda_a_la_linea_de_comandos():
    notas = pc.notas_del_dibujo(_plantilla([([pc.NUMERO_UDS.rstrip(":")], pc.MOTIVO_NUMERO_UDS)]))
    assert notas == ("Nº de unidades: a mano",), notas


def test_el_detalle_completo_sigue_viajando_para_la_linea_de_comandos():
    plantilla = _plantilla(MUCHAS)
    dibujo = pc.a_dict(plantilla)
    assert [n["texto"] for n in dibujo["notas"]] == list(plantilla.notas)
    assert dibujo["notas_del_dibujo"] == list(pc.notas_del_dibujo(plantilla))


def test_las_notas_caben_en_el_ancho_de_la_tabla_sin_partir_palabras_y_con_la_marca():
    notas = pc.notas_del_dibujo(_plantilla(MUCHAS))
    m = mq.maquetar_en_punto(CELDAS, notas, (0.0, 0.0), 0.125)
    assert isinstance(m, mq.Maquetacion)
    assert len(m.notas) <= 4, [linea for _x, _y, linea in m.notas]
    palabras = [p for n in notas for p in n.split()]
    assert sorted(p for _x, _y, linea in m.notas for p in linea.split()) == sorted(palabras)
    for _x, _y, linea in m.notas:
        assert mq.ancho_de_texto(linea, m.altura_texto) <= m.ancho_total + 1e-9, linea
    # Mismo tamaño de texto que el cuerpo de la tabla, y la marca de borrador debajo.
    assert m.marca[2] == pytest.approx(m.ancho_total)
    assert m.marca[1] < min(y for _x, y, _l in m.notas)


# --- 1. Colocación -----------------------------------------------------------------

VIVIENDA = ((0.0, 0.0), (12.0, 9.0))


def _huella(m):
    x, y = m.esquina
    return (x, y - m.alto_total), (x + m.ancho_total, y)


def _pisa(huella, obstaculos):
    (ax0, ay0), (ax1, ay1) = huella
    return [o for o in obstaculos if ax0 < o[2] and o[0] < ax1 and ay0 < o[3] and o[1] < ay1]


def test_si_el_punto_esta_libre_la_tabla_va_en_el_punto_y_no_se_mueve():
    obstaculos = [(0.0, 0.0, 12.0, 9.0)]
    m = mq.maquetar_en_punto(CELDAS, (), (20.0, 9.0), 0.125, obstaculos=obstaculos,
                             zona=(-30.0, -30.0, 42.0, 39.0))
    assert isinstance(m, mq.Maquetacion)
    assert m.esquina == (20.0, 9.0)
    assert m.colocacion is None


def test_si_la_tabla_pisaria_geometria_se_mueve_al_hueco_libre_mas_cercano_y_lo_dice():
    # El clic cae dentro de la vivienda: la tabla pisaría sus recintos y unos muebles.
    obstaculos = [(0.0, 0.0, 12.0, 9.0), (12.5, 0.0, 14.0, 9.0), (1.0, 1.0, 2.0, 2.0)]
    punto = (6.0, 6.0)
    m = mq.maquetar_en_punto(CELDAS, (), punto, 0.125, obstaculos=obstaculos,
                             zona=(-30.0, -30.0, 42.0, 39.0))
    assert isinstance(m, mq.Maquetacion)
    assert _pisa(_huella(m), obstaculos) == [], "la tabla movida sigue pisando el plano"
    assert m.esquina != punto
    assert m.colocacion and "movido" in m.colocacion and "pisaba" in m.colocacion, m.colocacion
    # El más cercano: ni un paso de rejilla más cerca hay hueco.
    (hx0, hy0), (hx1, hy1) = _huella(m)
    distancia = max(hx0 - punto[0], punto[0] - hx1, 0.0) ** 2 + max(hy0 - punto[1], punto[1] - hy1, 0.0) ** 2
    assert distancia ** 0.5 < 10.0, (m.esquina, distancia ** 0.5)


def test_las_notas_y_la_marca_tampoco_pisan_nada():
    notas = pc.notas_del_dibujo(_plantilla(MUCHAS))
    obstaculos = [(0.0, 0.0, 12.0, 9.0), (12.2, -3.0, 20.0, 9.5)]
    m = mq.maquetar_en_punto(CELDAS, notas, (12.5, 9.0), 0.125, obstaculos=obstaculos,
                             zona=(-30.0, -30.0, 42.0, 39.0))
    assert isinstance(m, mq.Maquetacion)
    assert _pisa(_huella(m), obstaculos) == []


def test_sin_hueco_libre_no_se_dibuja_y_se_dice():
    zona = (0.0, 0.0, 12.0, 9.0)
    m = mq.maquetar_en_punto(CELDAS, (), (6.0, 6.0), 0.125, obstaculos=[zona], zona=zona)
    assert isinstance(m, mq.NoCabe)
    assert "hueco" in m.motivo


# --- 3. El comando (leyendo el fuente; sin probar en la interfaz de AutoCAD) --------

from pathlib import Path  # noqa: E402

LSP = (Path(__file__).resolve().parent.parent / "autocad" / "archmuse.lsp").read_text(encoding="utf-8")


def _defun(nombre):
    ini = LSP.index("(defun %s " % nombre)
    fin = LSP.find("\n(defun ", ini + 1)
    return "\n".join(l.split(";")[0] for l in LSP[ini:fin if fin > 0 else len(LSP)].splitlines())


def test_el_comando_mira_lo_que_hay_alrededor_antes_de_colocar_la_tabla():
    comando = _defun("c:ARCHMUSE")
    zona = comando.index('(am:numeros-tras eleccion "zona_de_colocacion" 0)')
    obstaculos = comando.index("(am:obstaculos zona)")
    maquetar = comando.index("(am:maquetar bloque textos medidos punto cuadros estilo-texto obstaculos zona)")
    assert zona < obstaculos < maquetar
    cuerpo = _defun("am:maquetar")
    for clave in ('\\"obstaculos\\":', '\\"zona_de_colocacion\\":', '"notas_del_dibujo"'):
        assert clave in cuerpo, clave


def test_si_la_tabla_se_mueve_el_comando_lo_dice():
    comando = _defun("c:ARCHMUSE")
    assert '(am:valor-tras m "colocacion" 0)' in comando
    assert "(princ (strcat \"\\n  \" colocacion))" in comando


def test_el_detalle_de_las_notas_va_a_la_linea_de_comandos_y_al_registro_solo_recuentos():
    comando = _defun("c:ARCHMUSE")
    assert "(setq detalle (am:textos-de-notas bloque))" in comando
    assert '(foreach linea detalle (princ (strcat "\\n   - " linea)))' in comando
    registro = comando[comando.index('(am:log (strcat "notas: "'):]
    registro = registro[:registro.index("\n  (setq") if "\n  (setq" in registro else 400]
    assert "linea" not in registro and "detalle)" not in registro.replace("(length detalle)", "")


def test_leer_lo_que_hay_alrededor_no_escribe_nada_en_el_registro():
    for nombre in ("am:obstaculos", "am:caja-de-datos", "am:caja-de-insert", "am:mas-caja"):
        assert "(am:log" not in _defun(nombre), nombre


def test_la_primera_peticion_dice_donde_buscar_hueco(tmp_path):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _planta_de_varias_viviendas as planta
    from analyzer import vivienda_en_punto as vp
    from analyzer.geometria_recibida import payload_desde_dxf
    import app as modulo

    cuerpo = payload_desde_dxf(str(planta.generar(tmp_path / "p.dxf", n=2)), "00 areas")
    cuerpo.pop("otras_polilineas")
    uno = modulo.app.test_client().post("/api/vivienda-en-punto",
                                        json=dict(cuerpo, punto=[-1.0, 2.0])).get_json()
    x0, y0, x1, y1 = uno["zona_de_colocacion"]
    r = vp.RADIO_DE_COLOCACION_M
    assert (x0, y0) == pytest.approx((0.0 - r, 0.0 - r))
    assert (x1, y1) == pytest.approx((11.0 + r, 7.5 + r))


def test_la_colocacion_viaja_al_comando_antes_de_las_notas():
    obstaculos = [(0.0, 0.0, 12.0, 9.0)]
    m = mq.maquetar_en_punto(CELDAS, (), (6.0, 6.0), 0.125, obstaculos=obstaculos,
                             zona=(-30.0, -30.0, 42.0, 39.0))
    d = mq.a_dict(m)
    claves = list(d)
    assert claves.index("colocacion") < claves.index("notas")
    assert d["colocacion"] == m.colocacion
