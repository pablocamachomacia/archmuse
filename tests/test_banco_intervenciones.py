# -*- coding: utf-8 -*-
"""El banco clasifica cada celda: AUTOMÁTICO, UN CLIC o VACÍO (Pablo, 2026-09-17).

- **AUTOMÁTICO:** ArchMuse lo resolvió solo (coincide con el cuadro, o la diferencia
  está clasificada como redondeo o cuadro desactualizado).
- **UN CLIC:** se resolvería con una pregunta simple al arquitecto: una pieza entre
  dos viviendas, un rótulo de construida que alcanza dos polilíneas, cuál de dos
  nombres, interior o exterior.
- **VACÍO:** no se resuelve con un clic y debe quedar vacío con motivo: una
  estancia dibujada dos veces, un contorno que no existe.

**Sólo se mide.** El «modo preguntar» no existe: «completas si se respondieran los
UN CLIC» supone que la respuesta basta, y el resumen lo dice.

Todo sobre planos sintéticos: nada sale de un plano real.
"""
from __future__ import annotations

import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import medicion  # noqa: E402
from analyzer import plantilla_cuadro as pc  # noqa: E402
from tests.test_benchmark_compatibilidad import (  # noqa: E402
    CABECERA, CIFRAS_BUENAS, GENERADOR, RECINTOS, _cargar, _uno, banco,
)


def _dibujar(destino, cifras=None, cabecera=CABECERA, recintos=RECINTOS, extra=None):
    generador = _cargar("generar_cuadro_sintetico_intervenciones", GENERADOR)
    generador.RECINTOS = recintos
    generador.CUADRO = tuple(list(cabecera) + [(f, c, t) for (f, c), t in (cifras or {}).items()])
    if extra is not None:
        original = generador.construir

        def construir():
            doc, bloque, _handle = original()
            extra(doc.modelspace())
            return doc, bloque, doc.entitydb.next_handle()

        generador.construir = construir
    return generador.guardar(str(destino))


@pytest.fixture
def carpetas(tmp_path):
    planos, salida = tmp_path / "planos", tmp_path / "resultados"
    planos.mkdir()
    return planos, salida


def _parcela(msp):
    """Un contorno en otra capa cuyo borde pasa a 0,07 del rótulo de la construida:
    el rótulo alcanza dos polilíneas y no se elige ninguna (`C-12`)."""
    msp.add_lwpolyline([(-1.0, -3.0), (13.0, -3.0), (13.0, 4.5), (-1.0, 4.5)], close=True,
                       dxfattribs={"layer": "00 PARCELA"})


# -- La clasificación de un motivo -------------------------------------------------

@pytest.mark.parametrize("motivo, categoria", [
    ("no se sabe si es de esta vivienda o de VT2/1: está a 10,00 m de su rótulo y a "
     "11,00 m del de VT2/1. No se escribe su superficie.", "UN CLIC"),
    ("el rótulo de la construida (A1) tiene 2 polilíneas a menos de 0,38 m de su borde "
     "(B, C): no se elige ninguna (C-12).", "UN CLIC"),
    ("tiene dos nombres dentro («Tendedero» y «Terraza»): no se elige ninguno. Está medida "
     "y no tiene fila (C-18).", "UN CLIC"),
    ("se solapa con otra pieza dibujada: cuenta metros dos veces y no se escribe su cifra.",
     "VACÍO"),
    ("su contorno es el que el plano rotula «S. construida ext.»: es superficie construida, "
     "no útil, y no se escribe como su superficie. Falta el contorno de su superficie útil.",
     "VACÍO"),
    ("algo que nadie ha escrito todavía", "VACÍO"),
])
def test_cada_motivo_tiene_su_categoria(motivo, categoria):
    assert banco.categoria_de_motivo(motivo) == categoria


def test_un_total_bloqueado_por_varias_causas_toma_la_peor():
    reparto = "el reparto de 1 pieza(s) entre viviendas no es firme: «X» está a 1 m"
    solape = "hay 2,00 m² dibujados dos veces: la suma de las piezas da 3 y la superficie es 1"
    assert banco.categoria_de_motivo("no se escribe: %s (C-2)." % reparto) == "UN CLIC"
    assert banco.categoria_de_motivo("no se escribe: %s; %s (C-2)." % (reparto, solape)) == "VACÍO"


def test_un_motivo_derivado_toma_la_categoria_de_lo_que_lo_bloquea():
    derivado = ("ni la superficie útil interior ni la exterior se pueden afirmar (ver sus "
                "notas), y el total no se calcula sobre una cifra bloqueada (C-14).")
    assert banco.categoria_de_motivo(derivado) == banco.DERIVADO
    assert banco.resolver_derivadas(["UN CLIC", banco.DERIVADO]) == ["UN CLIC", "UN CLIC"]
    assert banco.resolver_derivadas(["UN CLIC", "VACÍO", banco.DERIVADO]) == ["UN CLIC", "VACÍO", "VACÍO"]
    assert banco.resolver_derivadas([banco.DERIVADO]) == ["VACÍO"]


def test_la_fila_que_falta_porque_la_pieza_duda_en_la_vivienda_de_al_lado_es_un_clic():
    """Medido en el plano maestro: la pieza está en la tabla de la vecina, sin cifra y
    con reparto dudoso hacia ésta. Una respuesta la trae aquí."""
    assert banco.motivo_de_fila_que_falta("aseo", "VT2/1") and \
        banco.categoria_de_motivo(banco.motivo_de_fila_que_falta("aseo", "VT2/1")) == "UN CLIC"
    assert banco.categoria_de_motivo(banco.motivo_de_fila_que_falta("aseo", None)) == "VACÍO"


def test_el_util_total_depende_de_sus_dos_totales_y_no_de_la_construida():
    campos = ["dormitorio_1", "total_util_interior", "total_util_exterior", "total_util",
              "superficie_construida_cerrada"]
    categorias = ["UN CLIC", "UN CLIC", "UN CLIC", banco.DERIVADO, "VACÍO"]
    assert banco.resolver_derivadas(categorias, campos) == [
        "UN CLIC", "UN CLIC", "UN CLIC", "UN CLIC", "VACÍO"]
    # La construida que no contiene la vivienda depende de las piezas.
    categorias = ["UN CLIC", "UN CLIC", "UN CLIC", banco.DERIVADO, banco.DERIVADO]
    assert banco.resolver_derivadas(categorias, campos)[-1] == "UN CLIC"


def test_cada_patron_sale_de_un_texto_que_existe_en_el_codigo():
    """Si alguien cambia la redacción de un motivo, esto se pone rojo antes de que
    el banco empiece a clasificarlo como VACÍO sin avisar."""
    fuentes = ""
    for carpeta in ("analyzer", "benchmark"):
        for nombre in os.listdir(os.path.join(RAIZ, carpeta)):
            if nombre.endswith(".py"):
                with open(os.path.join(RAIZ, carpeta, nombre), encoding="utf-8") as f:
                    fuentes += f.read()
    for patron, _categoria in banco.PATRONES_DE_MOTIVO:
        assert patron in fuentes, patron


def test_los_motivos_reales_de_la_medicion_caen_donde_deben():
    assert banco.categoria_de_motivo(medicion.motivo_c13("VT1/1", 2)) == "UN CLIC"
    assert banco.categoria_de_motivo(pc.MOTIVO_SIN_ROTULO_DE_CONSTRUIDA) == "VACÍO"


# -- El banco entero, sobre planos sintéticos --------------------------------------

def test_todo_coincide_es_automatico_y_sin_intervenciones(carpetas):
    planos, salida = carpetas
    _dibujar(planos / "a.dxf", CIFRAS_BUENAS)
    fila, _detalle = _uno(banco.ejecutar(str(planos), str(salida)))
    assert (fila["automatico"], fila["un_clic"], fila["vacio"]) == (5, 0, 0)
    assert fila["intervenciones_por_vivienda"] == "0.00"
    assert fila["viviendas_sin_intervencion_pct"] == "100.0"
    assert fila["viviendas_completas_con_un_clic_pct"] == "100.0"


def test_la_construida_con_dos_polilineas_al_alcance_es_un_clic(carpetas):
    planos, salida = carpetas
    _dibujar(planos / "a.dxf", CIFRAS_BUENAS, extra=_parcela)
    fila, detalle = _uno(banco.ejecutar(str(planos), str(salida)))
    [construida] = [c for c in detalle["comparaciones"] if c["campo"] == "superficie_construida_cerrada"]
    assert construida["estado"] == banco.VACIO_CON_MOTIVO and construida["categoria"] == "UN CLIC"
    assert (fila["automatico"], fila["un_clic"], fila["vacio"]) == (4, 1, 0)
    assert fila["intervenciones_por_vivienda"] == "1.00"
    assert fila["viviendas_sin_intervencion_pct"] == "0.0"
    assert fila["viviendas_completas_con_un_clic_pct"] == "100.0"


def test_una_estancia_dibujada_dos_veces_es_vacio(carpetas):
    """El dormitorio 2 pisa 2 m² del salón: los dos totales quedan vacíos (`C-2`)."""
    planos, salida = carpetas
    solapados = (("Salón/cocina", 0.0, 0.0, 5.0, 4.0), ("Dormitorio 1", 5.1, 0.0, 8.1, 4.0),
                 ("Dormitorio 2", 4.0, 0.0, 7.0, 3.0))
    _dibujar(planos / "a.dxf", CIFRAS_BUENAS, recintos=solapados)
    fila, detalle = _uno(banco.ejecutar(str(planos), str(salida)))
    [total] = [c for c in detalle["comparaciones"] if c["campo"] == "total_util_interior"]
    assert total["estado"] == banco.VACIO_CON_MOTIVO and total["categoria"] == "VACÍO"
    assert fila["viviendas_sin_intervencion_pct"] == "0.0"
    assert fila["viviendas_completas_con_un_clic_pct"] == "0.0"


def test_se_compara_con_la_tabla_que_dibuja_archmuse_y_el_util_lleva_c14(carpetas):
    """Hasta hoy el banco comparaba con el reparto sobre el cuadro del arquitecto, un
    camino que el producto ya no usa (la tabla es la plantilla fija desde el
    2026-09-13): el total útil salía siempre vacío. Ahora se compara lo que se dibuja."""
    planos, salida = carpetas
    _dibujar(planos / "a.dxf", {**CIFRAS_BUENAS, (6, 1): "41,00"})
    fila, detalle = _uno(banco.ejecutar(str(planos), str(salida)))
    [util] = [c for c in detalle["comparaciones"] if c["campo"] == "total_util"]
    assert util["estado"] == banco.COINCIDENCIA and util["categoria"] == "AUTOMÁTICO"


def test_dos_filas_iguales_se_emparejan_por_su_cifra(carpetas):
    """Dos «Terraza» sin número en la tabla y «terraza 1» y «terraza 2» en su cuadro:
    se comparan por cifra, sin inventar cuál es cuál por el orden."""
    planos, salida = carpetas
    recintos = RECINTOS + (("Terraza", 0.0, -1.6, 3.0, -0.1), ("Terraza", 3.1, -2.1, 5.1, -0.1))
    cabecera = list(CABECERA) + [(2, 2, "terraza 1"), (3, 2, "terraza 2")]
    cifras = {**CIFRAS_BUENAS, (2, 3): "4,00", (3, 3): "4,50", (5, 3): "8,50"}
    _dibujar(planos / "a.dxf", cifras, cabecera=cabecera, recintos=recintos)
    _fila, detalle = _uno(banco.ejecutar(str(planos), str(salida)))
    terrazas = {c["campo"]: c["estado"] for c in detalle["comparaciones"] if c["campo"].startswith("terraza")}
    assert terrazas == {"terraza_1": banco.COINCIDENCIA, "terraza_2": banco.COINCIDENCIA}


def test_el_resumen_trae_las_intervenciones_por_plano_y_en_total(carpetas):
    planos, salida = carpetas
    _dibujar(planos / "a.dxf", CIFRAS_BUENAS)
    _dibujar(planos / "b.dxf", CIFRAS_BUENAS, extra=_parcela)
    hecho = banco.ejecutar(str(planos), str(salida))
    with open(hecho["resumen"], encoding="utf-8") as f:
        resumen = f.read()
    seccion = resumen.split("## Intervenciones")[1].split("\n## ")[0]
    assert "| Total | 2 | 9 | 1 | 0 | 0 | 0,50 | 50,0 % | 100,0 % |" in seccion, seccion
    assert "supone que la respuesta basta" in seccion
