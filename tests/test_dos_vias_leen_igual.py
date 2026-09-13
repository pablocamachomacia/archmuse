# -*- coding: utf-8 -*-
"""`C-9` · Las dos vías de entrada tienen que leer lo mismo.

**Qué vigila, y por qué no lo vigilaba nadie.** ArchMuse recibe un plano por dos
caminos: el DXF que se sube por la web, y la geometría que manda el cliente CAD y
que `geometria_recibida` materializa en un DXF mínimo. Cada camino tenía sus
tests y los dos estaban en verde. **El hueco entre los dos no lo miraba nadie.**

Ahí se colaron tres fallos en dos días, los tres del mismo tipo —una vía
correcta, la otra rota, y ninguna forma de saber cuál:

1. **2026-09-10, el color y el flag de cerrada.** El payload no los llevaba, así
   que el DXF materializado salía entero en BYLAYER y con todo cerrado. Por la
   web el salón medía 21,90 m²; por la vía CAD el mismo plano lo perdía entero y
   escribía `0,00 m²` en el cuadro del arquitecto.
2. **2026-09-11, los títulos de campo.** `match_label_to_room` devolvía el primer
   texto que cayera dentro del recinto, y el orden de llegada no es el mismo
   leyendo un DXF que recibiendo un `ssget`. El mismo plano daba «Dormitorio 1»
   por una vía y «superficie util» por la otra.
3. **2026-09-11, el tipo de entidad de los rótulos.** El payload no lo llevaba y
   `geometria_recibida` escribía **todos** los textos como MTEXT, así que la
   prioridad MTEXT-sobre-TEXT de `extract_labels` se quedaba sin el dato con el
   que desempata. Sobre `plantasimple.dxf`: 157 recintos y **16 viviendas con
   superficie** por la web, 169 y **3** por el comando. Se cerró el 2026-09-12
   haciendo que el tipo viaje en el payload y el materializador lo respete.

**Este fichero no prueba que ArchMuse mida bien** — eso es de los tests de
medición. Prueba algo distinto y que ninguno de ellos puede probar: que **mide
igual mirando por donde mire**. Si divergen, es grave aunque las dos cifras
parezcan razonables, porque no se sabe cuál es la buena.

**El orden invertido no es un capricho.** Es lo único que el cliente no puede
garantizar: `ssget` no recorre en el orden de `doc.modelspace()`, y ésa fue
exactamente la diferencia entre el barrido que salió bien y el AutoCAD que salió
mal.

**Cada fallo deja un plano en el banco.** El tercero dejó dos: el fixture
sintético `15_mtext_y_text_en_el_mismo_recinto.dxf`, que es el único del
repositorio que mezcla los dos tipos dentro de un recinto y corre siempre; y
`plantasimple.dxf`, que es donde se midió y que se salta en CI. Un invariante que
sólo corre contra planos que ya pasaban no vigila nada.

**Cuando aparezca una tercera vía** —el plugin nativo, IFC, un DWG convertido—
entra aquí el mismo día que se escribe, no después.
"""
from __future__ import annotations

import os
import sys
import tempfile
from typing import NamedTuple, Optional

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer import parser  # noqa: E402
from analyzer.geometria_recibida import (  # noqa: E402
    SubidaMaterializada, payload_desde_dxf, validar,
)

FIXTURES = os.path.join(RAIZ, "tests", "fixtures")
MATERIAL = os.path.join(os.path.dirname(RAIZ), "_material")


class Plano(NamedTuple):
    """Un plano del banco y **lo que hace falta para poder leerlo**.

    Hasta el 2026-09-12 el banco era una lista de rutas, y eso dejaba fuera al
    único plano que importaba: `plantasimple.dxf` no resuelve su capa solo
    —tiene cuatro candidatas y ninguna destaca— ni se le entienden los rótulos
    sin alinearlos, así que entraba por el filtro de saltos, se saltaba en
    silencio y **el invariante quedaba en verde sin haber mirado nada**. Un
    plano que necesita que le digan la capa es un plano normal, no un plano
    excluido: lo que se le dice, se dice aquí, e idéntico por las dos vías.
    """

    ruta: str
    capa: Optional[str] = None
    alinear: bool = False

    @property
    def nombre(self) -> str:
        return os.path.basename(self.ruta)


#: Planos versionados: viajan con el repositorio y corren siempre.
DEL_REPO = [
    Plano(os.path.join(FIXTURES, "reales", "planta_tres_viviendas.dxf")),
    Plano(os.path.join(FIXTURES, "reales", "vivienda_con_solapes.dxf")),
    Plano(os.path.join(FIXTURES, "dxf_tortura", "14_flag_de_cerrada_mal_puesto.dxf")),
    # El único del repositorio que mezcla MTEXT y TEXT dentro del mismo recinto,
    # que es la forma de `plantasimple.dxf` y por donde se coló el tercero de
    # los fallos que lista el encabezado de este fichero (2026-09-11). Los otros seis son todo-MTEXT o todo-TEXT, así que ninguno
    # ejercitaba la prioridad de `extract_labels`.
    Plano(os.path.join(FIXTURES, "dxf_tortura",
                       "15_mtext_y_text_en_el_mismo_recinto.dxf")),
    Plano(os.path.join(FIXTURES, "dxf_plausibles", "01_control_estancias.dxf")),
    Plano(os.path.join(FIXTURES, "dxf_plausibles", "09_capas_de_ruido.dxf")),
    Plano(os.path.join(FIXTURES, "dxf_plausibles", "11_capa_opaca_rotulos_fuera.dxf")),
]

#: Planos reales del arquitecto. No se versionan —son de sus clientes y el
#: repositorio es público— así que se saltan si no están en esta máquina. Son los
#: que encontraron los tres fallos, y por eso están aquí pese a saltarse en CI.
DEL_ARQUITECTO = [
    Plano(os.path.join(MATERIAL, "v1plantas.dxf")),
    Plano(os.path.join(MATERIAL, "v2s.dxf")),
    Plano(os.path.join(MATERIAL, "v3s.dxf")),
    Plano(os.path.join(MATERIAL, "V5.dxf")),
    # Su capa hay que dársela (cuatro candidatas, ninguna destaca) y sus rótulos
    # están corridos 50,00 en bloque. Es el plano donde se midió la divergencia
    # del MTEXT: 16 viviendas con superficie por la web contra 3 por el comando.
    Plano(os.path.join(MATERIAL, "plantasimple.dxf"), capa="00 areas", alinear=True),
]

TODOS = DEL_REPO + DEL_ARQUITECTO


#: Planos en los que **el orden de los textos sí cambia lo que se lee**, con el
#: defecto abierto y sin tapar. Hoy hay uno.
#:
#: `plantasimple.dxf` rotula cada salón con **varios MTEXT de la misma capa**:
#: el nombre repetido dos o tres veces y la cifra de su superficie
#: («Salón/cocina», «Salón/cocina», «21.90m²», todos MTEXT en `00 TEXTO`).
#: Medido el 2026-09-12: 156 recintos tienen más de un texto dentro y **63 de
#: ellos tienen tres MTEXT compitiendo**.
#:
#: La prioridad MTEXT-sobre-TEXT de `extract_labels` no desempata eso —son del
#: mismo tipo— y la regla de la capa que nombra tampoco —son de la misma capa—.
#: Lo desempata **el orden del recorrido**, y `ssget` no garantiza ninguno: al
#: invertirlo, las 156 estancias pasan de llamarse «Salón/cocina» a llamarse
#: «21.90m²».
#:
#: **No se arregla aquí a propósito.** Cuál de dos textos de la misma capa y el
#: mismo tipo nombra una estancia es criterio profesional (`D-7`), y esto lo que
#: hace es medirlo y dejarlo a la vista mientras Pablo no lo firme. `strict=True`
#: para que el día que se arregle este xfail se ponga rojo y haya que venir a
#: borrarlo.
ORDEN_DE_LOS_TEXTOS_NO_GARANTIZADO = {"plantasimple.dxf"}

_XFAIL_ORDEN = pytest.mark.xfail(
    strict=True,
    reason="varios MTEXT de la misma capa dentro del recinto: el desempate lo "
           "decide el orden del recorrido y `ssget` no lo garantiza (D-7, sin firmar)")


def _params(con_xfail_de_orden=False):
    """El banco como parámetros, con el `id` puesto a mano.

    El `id` es el nombre del fichero **siempre**, tenga marca o no: si un plano
    cambia de identificador al ponerle un `xfail`, dejan de poder compararse dos
    ejecuciones de la suite, que es justo cuando hace falta.
    """
    marcados = ORDEN_DE_LOS_TEXTOS_NO_GARANTIZADO if con_xfail_de_orden else set()
    return [pytest.param(p, id=p.nombre,
                         marks=[_XFAIL_ORDEN] if p.nombre in marcados else [])
            for p in TODOS]


#: A cuántos decimales se comparan las superficies: **los dos con los que se
#: publican**, que son los que acaban en el cuadro del arquitecto.
#:
#: **No es una tolerancia de conveniencia, y conviene saber lo que tapa.** El
#: payload viaja con las coordenadas a seis decimales —y no por capricho:
#: `am:json-num` usa `(rtos x 2 6)`, así que seis es lo que el cliente sabe
#: mandar, y subir aquí la precisión haría al simulador más fino que lo
#: simulado—. Sobre un recinto de `plantasimple.dxf` con el perímetro a 300 m
#: del origen, ese micrómetro por vértice acumula **0,0001 m²**: el «Tendedero»
#: mide 4,1236 m² por la web y 4,1237 por el cliente. Es **1 cm² en 1 de 157
#: piezas**, y es el único resto que queda en todo el banco.
#:
#: Comparar más fino que eso sería comparar el ruido del transporte; comparar
#: más grueso empezaría a tapar diferencias que el arquitecto vería escritas.
DECIMALES_PUBLICADOS = 2


def _huella(plano):
    """Lo que tiene que coincidir: qué recintos, cómo se llaman y cuánto miden.

    Ordenado, porque el orden de los recintos sí puede cambiar legítimamente
    entre las dos vías — lo que no puede cambiar es el conjunto.
    """
    return sorted(((r.label or "").strip(),
                   round(r.polygon.area, DECIMALES_PUBLICADOS))
                  for r in plano.rooms)


def _por_la_web(plano):
    return parser.leer_plano(parser.load_document(plano.ruta), layer=plano.capa,
                             alinear_rotulos=plano.alinear)


def _por_el_cliente(plano, invertir_textos=False):
    """Como llega desde AutoCAD: payload, DXF materializado, y a leer."""
    payload = payload_desde_dxf(plano.ruta, plano.capa)
    if invertir_textos:
        payload["textos"] = list(reversed(payload["textos"]))
    with tempfile.TemporaryDirectory() as carpeta:
        destino = os.path.join(carpeta, "materializado.dxf")
        SubidaMaterializada(validar(payload)).save(destino)
        return parser.leer_plano(parser.load_document(destino), layer=plano.capa,
                                 alinear_rotulos=plano.alinear)


def _plano_o_skip(plano):
    """Sólo se salta lo que no está en esta máquina.

    **Antes se saltaba también lo que no resolvía su capa solo**, y eso
    convertía el caso más difícil del banco en silencio verde. Un plano que
    declara su capa en el banco ya no necesita el heurístico; y uno que no la
    declare y no resuelva tiene que **fallar**, no desaparecer: el invariante no
    puede elegir contra qué planos se comprueba.
    """
    if not os.path.isfile(plano.ruta):
        pytest.skip("%s no está en esta máquina" % plano.nombre)
    return plano


@pytest.mark.parametrize("plano", _params())
def test_las_dos_vias_leen_los_mismos_recintos(plano):
    """El invariante, en su forma más simple."""
    plano = _plano_o_skip(plano)
    web = _huella(_por_la_web(plano))
    cliente = _huella(_por_el_cliente(plano))
    assert web == cliente, (
        "el mismo plano se lee distinto según por dónde entre.\n"
        "  sólo por la web:     %s\n"
        "  sólo por el cliente: %s"
        % (sorted(set(web) - set(cliente)), sorted(set(cliente) - set(web))))


@pytest.mark.parametrize("plano", _params(con_xfail_de_orden=True))
def test_el_orden_de_los_textos_no_cambia_lo_que_se_lee(plano):
    """Lo único que el cliente no puede garantizar.

    `ssget` no recorre en el orden de `doc.modelspace()`, y ésa fue exactamente
    la diferencia entre el barrido que leyó bien los ocho rótulos de
    `v1plantas.dxf` y el AutoCAD que leyó ocho «superficie util».
    """
    plano = _plano_o_skip(plano)
    normal = _huella(_por_el_cliente(plano, invertir_textos=False))
    invertido = _huella(_por_el_cliente(plano, invertir_textos=True))
    assert normal == invertido, (
        "invertir el orden de los textos cambia lo que se lee.\n"
        "  con el orden normal:   %s\n"
        "  con el orden inverso:  %s"
        % (sorted(set(normal) - set(invertido)),
           sorted(set(invertido) - set(normal))))


@pytest.mark.parametrize("plano", _params())
def test_las_dos_vias_publican_las_mismas_superficies(plano):
    """Y hasta el final: no sólo los mismos recintos, las mismas cifras.

    Es lo que de verdad llega al cuadro del arquitecto. Dos vías que leen los
    mismos recintos y publican superficies distintas seguirían siendo un fallo
    grave, y el test anterior no lo cazaría.
    """
    plano = _plano_o_skip(plano)
    from analyzer import medicion

    def superficies(leido):
        m = medicion.medir_planta(leido)
        return sorted((v.nombre, v.util_interior_m2, v.util_exterior_m2)
                      for v in m.viviendas)

    assert superficies(_por_la_web(plano)) == superficies(_por_el_cliente(plano))


#: Para la tabla de ArchMuse: el banco de siempre más el fixture sintético, que
#: es el único con envolvente construida, familia desconocida y cuadro. Fuera
#: `plantasimple.dxf`: ya tiene declarada su divergencia de orden de textos
#: (`D-7`, xfail arriba), y medirlo dos veces más por vía son minutos.
BANCO_DE_LA_TABLA = [p for p in TODOS if p.nombre != "plantasimple.dxf"] + [
    Plano(os.path.join(FIXTURES, "cuadro_sintetico", "cuadro_sintetico.dxf")),
]


def _tablas(leido, doc, ambitos):
    from analyzer import medicion
    from analyzer import plantilla_cuadro as pc

    medida = medicion.medir_planta(leido)
    return {v.nombre: (pc.construir(doc, leido, v.nombre, ambitos=ambitos, medida=medida).celdas(),
                       pc.construir(doc, leido, v.nombre, ambitos=ambitos, medida=medida).notas)
            for v in medida.viviendas}


@pytest.mark.parametrize("ambitos", [None, {"TRASTERO": "interior"}],
                         ids=["sin_respuestas", "con_respuestas"])
@pytest.mark.parametrize("plano", [pytest.param(p, id=p.nombre) for p in BANCO_DE_LA_TABLA])
def test_las_dos_vias_dibujan_la_misma_tabla(plano, ambitos):
    """**`C-9` hasta la tabla** (PRD 2026-09-13, decisión 7 de Pablo).

    Leer los mismos recintos no basta: la web y el comando tienen que producir la
    MISMA plantilla —mismas filas, mismas cifras, mismas notas— para cada
    vivienda. Si una clonara el cuadro del arquitecto y la otra generara la
    plantilla, este test sería el que lo dijera.
    """
    plano = _plano_o_skip(plano)
    doc_web = parser.load_document(plano.ruta)
    web = _tablas(_por_la_web(plano), doc_web, ambitos)

    payload = payload_desde_dxf(plano.ruta, plano.capa)
    with tempfile.TemporaryDirectory() as carpeta:
        destino = os.path.join(carpeta, "materializado.dxf")
        SubidaMaterializada(validar(payload)).save(destino)
        doc_cliente = parser.load_document(destino)
        leido = parser.leer_plano(doc_cliente, layer=plano.capa, alinear_rotulos=plano.alinear)
        cliente = _tablas(leido, doc_cliente, ambitos)

    assert web == cliente, (
        "la misma planta dibuja una tabla distinta según por dónde entre:\n"
        "  viviendas sólo por la web:     %s\n"
        "  viviendas sólo por el cliente: %s\n"
        "  viviendas con tabla distinta:  %s"
        % (sorted(set(web) - set(cliente)), sorted(set(cliente) - set(web)),
           sorted(n for n in set(web) & set(cliente) if web[n] != cliente[n])))


def test_el_banco_de_planos_no_se_queda_vacio():
    """Si un día nadie corre —porque los ficheros cambiaron de sitio— este
    fichero pasaría entero sin comprobar nada, que es la peor forma de estar en
    verde. Los del repositorio tienen que estar siempre."""
    ausentes = [p.nombre for p in DEL_REPO if not os.path.isfile(p.ruta)]
    assert not ausentes, ausentes
