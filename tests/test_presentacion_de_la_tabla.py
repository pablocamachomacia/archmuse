# -*- coding: utf-8 -*-
"""La tabla en el plano: dónde va y qué dicen sus notas (Pablo, 2026-09-15, 0.3.12).

**Lo que vio en el maestro del estudio:**

1. **Colocación.** La tabla y sus notas se dibujaron encima del plano. Se resolvió
   moviéndola al hueco libre más cercano. **Retirado el 2026-09-16** por decisión de
   Pablo: dos clics, y la tabla va exactamente donde se hace el segundo; si tapa
   algo, sólo se avisa. Lo vigila `tests/test_dos_clics.py`.
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
from analyzer.unidades_declaradas import MOTIVO_NO_DECLARA as MOTIVO_NUMERO_UDS

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
    ([pc.NUMERO_UDS.rstrip(":")], MOTIVO_NUMERO_UDS),
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
    notas = pc.notas_del_dibujo(_plantilla([([pc.NUMERO_UDS.rstrip(":")], MOTIVO_NUMERO_UDS)]))
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
#
# Los tests del hueco libre (2026-09-15) se quitaron el 2026-09-16, con la decisión que
# los retiró: la tabla va donde se hace el segundo clic y sólo se avisa de lo que tapa.
# `tests/test_dos_clics.py`.


# --- 3. El comando (leyendo el fuente; sin probar en la interfaz de AutoCAD) --------

from pathlib import Path  # noqa: E402

LSP = (Path(__file__).resolve().parent.parent / "autocad" / "archmuse.lsp").read_text(encoding="utf-8")


def _defun(nombre):
    ini = LSP.index("(defun %s " % nombre)
    fin = LSP.find("\n(defun ", ini + 1)
    return "\n".join(l.split(";")[0] for l in LSP[ini:fin if fin > 0 else len(LSP)].splitlines())


def test_el_comando_manda_lo_que_hay_bajo_la_tabla_y_las_notas_cortas():
    cuerpo = _defun("am:maquetar")
    for clave in ('\\"obstaculos\\":', '"notas_del_dibujo"'):
        assert clave in cuerpo, clave
    assert "zona_de_colocacion" not in cuerpo


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


