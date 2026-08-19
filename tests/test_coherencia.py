# -*- coding: utf-8 -*-
"""La revision de coherencia del plano (`analyzer/coherencia.py`, tareas CO-1..CO-3).

Ejecutar:  pytest tests/test_coherencia.py

PRD: `docs/prd/2026-08-19-revision-de-coherencia-del-plano.md`.

**Que se fija aqui.** Casi todo lo que este modulo hace ya se calculaba en el
repositorio y se tiraba: los solapes servian para negarse a medir, los avisos de
polilinea mal cerrada iban a `logging`, y la etiqueta repetida acababa en una
celda `BLOQUEADO`. Lo que es nuevo, y por tanto lo que hay que probar con mas
cuidado, es el contraste entre el cuadro y el dibujo — y ahi vive el unico
riesgo real de este modulo, que es el **falso positivo**: un aviso falso destruye
la confianza en los verdaderos (`DESTROY_ARCHMUSE.md` §5.1).

La seccion 4 es la que mas importa: fija que dos piezas contiguas no son un
solape, y que «Dormitorio 1» y el hueco `dormitorio_1` son la misma cosa. La
segunda la encontre probando contra el plano real: sin ella, un piso de tres
dormitorios perfectamente correcto producia **seis hallazgos falsos**.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from analyzer import coherencia  # noqa: E402

DXF_V2S = os.environ.get("ARCHMUSE_DXF_V2S", "")


#: Piezas de relleno que se anaden cuando el caso de prueba trae menos de las
#: que el parser necesita para reconocer una capa de estancias
#: (`parser.MINIMO_POLIGONOS_CAPA`). Van lejos de la zona de trabajo, rotuladas
#: con nombres que ningun caso usa, para que no contaminen ninguna asercion: sin
#: ellas, un caso de dos piezas no falla por lo que prueba sino por
#: `CapaIndeterminada`, que es ruido.
_RELLENO = (
    ("Distribuidor", (100.0, 100.0), (103.0, 103.0)),
    ("Trastero comun", (110.0, 100.0), (113.0, 103.0)),
    ("Armario comun", (120.0, 100.0), (123.0, 103.0)),
)


def construir(piezas, *, destino: Path, cerradas=None, unidad=6, etiquetas_vt=None):
    """Un DXF sintetico con las piezas que se le pidan.

    `piezas` son `(etiqueta, (x0, y0), (x1, y1))`. `cerradas` permite dejar una
    polilinea con el flag `closed` a False para provocar el caso de recuperacion.
    """
    import ezdxf

    from analyzer import parser

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = unidad
    doc.layers.add(parser.AREA_LAYER)
    msp = doc.modelspace()
    for i, (etiqueta, (x0, y0), (x1, y1)) in enumerate(piezas):
        cerrada = True if cerradas is None else cerradas[i]
        puntos = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        if not cerrada:
            puntos.append((x0, y0))       # extremos coincidentes: se recupera
        msp.add_lwpolyline(puntos, close=cerrada,
                           dxfattribs={"layer": parser.AREA_LAYER})
        if etiqueta:
            msp.add_mtext(etiqueta, dxfattribs={"layer": parser.AREA_LAYER}).set_location(
                ((x0 + x1) / 2.0, (y0 + y1) / 2.0))
    for etiqueta, (x0, y0), (x1, y1) in _RELLENO[:max(0, parser.MINIMO_POLIGONOS_CAPA - len(piezas))]:
        msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                           dxfattribs={"layer": parser.AREA_LAYER})
        msp.add_mtext(etiqueta, dxfattribs={"layer": parser.AREA_LAYER}).set_location(
            ((x0 + x1) / 2.0, (y0 + y1) / 2.0))
    # Una etiqueta `VT<n>` por vivienda, que es como vienen los planos reales:
    # `V5.dxf` trae VT1/3, VT2/2 y VT3/3. Sin ellas el motor se repliega a
    # agrupar por proximidad, que fusiona pisos vecinos y hace imposible probar
    # el caso de varias viviendas.
    for nombre, x, y in (etiquetas_vt or (("VT1/1", -9.0, -9.0),)):
        msp.add_mtext(nombre, dxfattribs={"layer": parser.AREA_LAYER}).set_location((x, y))
    ruta = destino / "plano.dxf"
    doc.saveas(str(ruta))
    return ruta


def revisar(piezas, tmp_path, **kwargs):
    import ezdxf

    ruta = construir(piezas, destino=tmp_path, **kwargs)
    return coherencia.revisar(ezdxf.readfile(str(ruta)))


def tipos(revision):
    return [h.tipo for h in revision.hallazgos]


# --- 1. El tipo `Hallazgo`: las dos reglas duras --------------------------

def test_un_hallazgo_sin_entidad_no_se_puede_construir():
    """Un aviso que no se puede localizar gasta tiempo en vez de ahorrarlo, y
    por eso no es un aviso mal formateado: es un objeto que no existe."""
    with pytest.raises(ValueError, match="entidad"):
        coherencia.Hallazgo(tipo=coherencia.SOLAPE, descripcion="x", entidad="")


def test_un_tipo_fuera_del_catalogo_se_rechaza():
    """El catalogo esta cerrado para que quien consume esto pueda agrupar por
    tipo sin adivinar. Una lista abierta son doce variantes de la misma frase
    en tres meses."""
    with pytest.raises(ValueError, match="catálogo"):
        coherencia.Hallazgo(tipo="inventado", descripcion="x", entidad="y")


def test_ningun_hallazgo_tiene_campo_de_gravedad():
    """La frontera con el criterio profesional, fijada en el propio tipo.

    `D-7` esta sin firmar: ArchMuse mide, no califica. Si alguien anade
    `severidad` al dataclass, esto se pone rojo."""
    campos = set(coherencia.Hallazgo.__dataclass_fields__)
    assert not (campos & {"severidad", "gravedad", "prioridad", "criticidad"})


# --- 2. Lo que ya se calculaba y se tiraba -------------------------------

def test_dos_piezas_que_se_solapan_se_dicen_con_sus_metros(tmp_path):
    revision = revisar([
        ("Salon", (0.0, 0.0), (4.0, 3.0)),
        ("Terraza", (3.0, 0.0), (6.0, 2.0)),        # 1 x 2 = 2 m2 de solape
    ], tmp_path)
    solapes = [h for h in revision.hallazgos if h.tipo == coherencia.SOLAPE]
    assert len(solapes) == 1
    assert solapes[0].magnitud == pytest.approx(2.0, abs=0.01)
    assert solapes[0].unidad == "m2"
    assert "Salon" in solapes[0].entidad and "Terraza" in solapes[0].entidad


def test_una_polilinea_cerrada_por_suposicion_llega_al_informe(tmp_path):
    """El aviso que hoy va a `logging` y no lee nadie.

    El propio parser documenta que «tiene que quedar visible para quien audite».
    Un `logging.warning` es visible para un programador con una terminal
    abierta, no para el arquitecto que va a entregar el plano.
    """
    # Tres piezas cerradas y una abierta: la capa necesita al menos
    # `parser.MINIMO_POLIGONOS_CAPA` poligonos CERRADOS para reconocerse como
    # capa de estancias, y la abierta no cuenta para ese minimo.
    revision = revisar([
        ("Salon", (0.0, 0.0), (4.0, 3.0)),
        ("Cocina", (5.0, 0.0), (8.0, 3.0)),
        ("Dormitorio 1", (0.0, 5.0), (4.0, 8.0)),
        ("Aseo", (6.0, 5.0), (8.0, 7.0)),
    ], tmp_path, cerradas=[True, True, True, False])
    avisos = [h for h in revision.hallazgos if h.tipo == coherencia.POLILINEA_MAL_CERRADA]
    assert len(avisos) == 1
    assert "handle" in avisos[0].entidad
    assert avisos[0].magnitud is not None


def test_un_rotulo_repetido_se_dice_con_las_dos_superficies(tmp_path):
    revision = revisar([
        ("Tendedero", (0.0, 0.0), (2.0, 2.0)),
        ("Tendedero", (5.0, 0.0), (8.0, 2.0)),
    ], tmp_path)
    dup = [h for h in revision.hallazgos if h.tipo == coherencia.ETIQUETA_DUPLICADA]
    assert len(dup) == 1
    assert dup[0].entidad == "Tendedero"
    assert dup[0].detalle["areas_m2"] == [4.0, 6.0]


def test_una_pieza_sin_rotular_se_dice(tmp_path):
    revision = revisar([
        ("Salon", (0.0, 0.0), (4.0, 3.0)),
        ("", (6.0, 0.0), (8.0, 2.0)),
    ], tmp_path)
    assert coherencia.RECINTO_SIN_ETIQUETA in tipos(revision)


# --- 3. El contraste entre el cuadro y el dibujo -------------------------
#
# Sin `ACAD_TABLE` no hay cuadro que contrastar, y un `ACAD_TABLE` no se
# sintetiza de forma realista. Asi que aqui se prueba la funcion contra un
# cuadro de mentira, y el caso completo va contra el plano real (§5).

class _Celda:
    def __init__(self, campo):
        self.campo = campo


class _Cuadro:
    def __init__(self, campos):
        self.celdas = [_Celda(c) for c in campos]


class _Room:
    def __init__(self, label, area=10.0):
        self.label = label
        self.area_m2 = area


def test_el_cuadro_pide_una_pieza_que_no_esta_dibujada():
    hallazgos = coherencia._cuadro_contra_dibujo(
        [_Room("Salon")], _Cuadro(["salon", "pasillo"]))
    assert [h.tipo for h in hallazgos] == [coherencia.CUADRO_PIDE_PIEZA_NO_DIBUJADA]
    assert hallazgos[0].entidad == "pasillo"
    # Discrepancia, NO defecto: un pasillo puede no dibujarse como recinto
    # propio. Llamarlo error seria inventar criterio profesional.
    assert "conviene mirarlo" in hallazgos[0].descripcion


def test_una_pieza_dibujada_que_el_cuadro_no_contempla():
    hallazgos = coherencia._cuadro_contra_dibujo(
        [_Room("Salon"), _Room("Trastero")], _Cuadro(["salon"]))
    assert [h.tipo for h in hallazgos] == [coherencia.PIEZA_DIBUJADA_FUERA_DEL_CUADRO]
    assert hallazgos[0].entidad == "Trastero"


def test_cuando_los_recuentos_no_coinciden_se_dice_cuantas_sobran():
    """El caso del plano real: el cuadro tiene un hueco de tendedero y el plano
    dibuja dos. Es la causa de que la celda salga BLOQUEADA, y hasta ahora el
    arquitecto veia el efecto y no la causa."""
    hallazgos = coherencia._cuadro_contra_dibujo(
        [_Room("Tendedero"), _Room("Tendedero")], _Cuadro(["tendedero"]))
    assert [h.tipo for h in hallazgos] == [coherencia.RECUENTO_NO_COINCIDE]
    assert hallazgos[0].magnitud == 1.0
    assert hallazgos[0].detalle == {"campos": ["tendedero"],
                                    "rotulos": ["Tendedero", "Tendedero"],
                                    "huecos": 1, "dibujadas": 2}


def test_los_totales_del_cuadro_no_se_confunden_con_piezas():
    """`total_util`, `superficie_construida_cerrada`, `numero_unidades` y
    `vivienda_tipo` no nombran ninguna pieza del plano. Compararlos contra los
    rotulos daria cuatro hallazgos falsos garantizados."""
    hallazgos = coherencia._cuadro_contra_dibujo(
        [_Room("Salon")],
        _Cuadro(["salon", "total_util", "superficie_construida_cerrada",
                 "numero_unidades", "vivienda_tipo"]))
    assert hallazgos == []


# --- 4. Los falsos positivos que NO se pueden producir -------------------
#
# La seccion que mas importa. Un hallazgo falso destruye la confianza en los
# verdaderos, y las dos trampas de abajo son las que este modulo tiene mas a
# mano.

def test_dos_piezas_que_comparten_borde_no_se_solapan(tmp_path):
    """Lo normal en un plano: habitaciones contiguas. Comparten linea, no area.
    Si esto fallara, todo plano correcto saldria lleno de hallazgos."""
    revision = revisar([
        ("Salon", (0.0, 0.0), (4.0, 3.0)),
        ("Cocina", (4.0, 0.0), (7.0, 3.0)),
    ], tmp_path)
    assert coherencia.SOLAPE not in tipos(revision)


def test_dormitorio_1_y_el_hueco_dormitorio_1_son_la_misma_pieza():
    """**El falso positivo que encontre probando contra el plano real.**

    El cuadro numera los huecos (`dormitorio_1`) y el arquitecto numera los
    rotulos («Dormitorio 1»). Sin normalizar los dos lados, un piso de tres
    dormitorios correcto producia seis hallazgos falsos: tres de «el cuadro
    pide» y tres de «el plano dibuja».
    """
    hallazgos = coherencia._cuadro_contra_dibujo(
        [_Room("Dormitorio 1"), _Room("Dormitorio 2"), _Room("Dormitorio 3")],
        _Cuadro(["dormitorio_1", "dormitorio_2", "dormitorio_3"]))
    assert hallazgos == []


def test_las_tildes_y_la_ene_no_producen_hallazgos_falsos():
    """«Salón/cocina» y `salon_cocina` son la misma pieza; «Baño» y `bano`
    tambien. Sin esto, cada habitacion con tilde daria dos hallazgos."""
    hallazgos = coherencia._cuadro_contra_dibujo(
        [_Room("Salón/cocina"), _Room("Baño")], _Cuadro(["salon_cocina", "bano"]))
    assert hallazgos == []


# --- 5. Un plano limpio, y uno sin cuadro -------------------------------

def test_un_plano_limpio_no_da_hallazgos_pero_dice_que_ha_mirado(tmp_path):
    """Un informe vacio se lee como «no ha funcionado», y ademas afirmaria mas
    de lo que este documento puede sostener."""
    revision = revisar([
        ("Salon", (0.0, 0.0), (4.0, 3.0)),
        ("Cocina", (4.0, 0.0), (7.0, 3.0)),
        ("Dormitorio 1", (0.0, 4.0), (4.0, 7.0)),
    ], tmp_path)
    assert revision.hallazgos == ()
    assert revision.limpio is True
    assert revision.comprobado, "un informe limpio tiene que enumerar que ha mirado"
    assert revision.recintos == 3
    assert revision.unidad_del_dibujo == "metros"


def test_sin_cuadro_el_contraste_no_se_da_por_hecho_ni_por_correcto(tmp_path):
    """El DXF sintetico no trae `ACAD_TABLE`. Eso NO es un hallazgo: es una
    comprobacion que no se ha podido hacer, y se dice con su motivo para que no
    se lea como comprobada y correcta."""
    revision = revisar([("Salon", (0.0, 0.0), (4.0, 3.0))], tmp_path)
    assert revision.no_comprobado
    assert "cuadro" in revision.no_comprobado[0]
    assert coherencia.CUADRO_PIDE_PIEZA_NO_DIBUJADA not in tipos(revision)


def test_el_diccionario_de_salida_lleva_todo_lo_que_el_informe_necesita(tmp_path):
    revision = revisar([("Salon", (0.0, 0.0), (4.0, 3.0))], tmp_path)
    d = revision.a_dict()
    assert set(d) >= {"hallazgos", "comprobado", "no_comprobado", "recuento_por_tipo",
                      "recintos", "capa_de_recintos", "unidad_del_dibujo", "limpio"}


# --- 6. El plano real del cliente ---------------------------------------

@pytest.mark.skipif(not DXF_V2S, reason="define ARCHMUSE_DXF_V2S para el plano real")
def test_los_nueve_hallazgos_del_plano_real():
    """**El test que define «hecho»** (criterio de aceptacion nº1 del PRD).

    Los nueve salen de ejecutar esto sobre el DXF del cliente, no de una
    estimacion. Si esta lista cambia, o el plano ha cambiado o alguien ha
    cambiado un criterio: hay que mirar cual de las dos cosas, no ajustar el
    numero.
    """
    import ezdxf

    revision = coherencia.revisar(ezdxf.readfile(DXF_V2S))
    recuento = revision.por_tipo()
    assert recuento == {
        coherencia.SOLAPE: 2,
        coherencia.POLILINEA_MAL_CERRADA: 2,
        coherencia.ETIQUETA_DUPLICADA: 1,
        coherencia.CUADRO_PIDE_PIEZA_NO_DIBUJADA: 2,
        coherencia.RECUENTO_NO_COINCIDE: 2,
    }, "hallazgos: %s" % [h.descripcion for h in revision.hallazgos]
    assert len(revision.hallazgos) == 9
    assert revision.recintos == 9
    assert revision.unidad_del_dibujo == "metros"

    # Las magnitudes concretas: son la mitad del valor del informe.
    solapes = sorted(h.magnitud for h in revision.hallazgos if h.tipo == coherencia.SOLAPE)
    assert solapes == [pytest.approx(3.08, abs=0.01), pytest.approx(4.00, abs=0.01)]

    # El hueco de 2,95 cm del contorno mal cerrado, que es el que de verdad
    # importa de los dos: una superficie calculada sobre una suposicion.
    huecos = sorted(h.magnitud for h in revision.hallazgos
                    if h.tipo == coherencia.POLILINEA_MAL_CERRADA)
    assert huecos[-1] == pytest.approx(0.02953, abs=0.0001)

    # Y ninguno se queda sin decir donde mirarlo.
    for h in revision.hallazgos:
        assert h.entidad.strip()


@pytest.mark.skipif(not DXF_V2S, reason="define ARCHMUSE_DXF_V2S para el plano real")
def test_los_tres_dormitorios_del_plano_real_no_dan_ningun_hallazgo():
    """La guardia del falso positivo, sobre el fichero donde aparecio.

    El plano tiene tres dormitorios y el cuadro tres huecos de dormitorio. Si
    esto vuelve a fallar, el informe habra ganado seis avisos falsos y nadie lo
    volvera a abrir.
    """
    import ezdxf

    revision = coherencia.revisar(ezdxf.readfile(DXF_V2S))
    for h in revision.hallazgos:
        assert "dormitorio" not in h.entidad.lower(), h.descripcion


# --- 7. Varias viviendas en un mismo fichero -----------------------------
#
# **Lo que enseño el SEGUNDO plano real, y es la razon por la que habia que
# medirlo antes de vender esto.** `V5.dxf` tiene tres viviendas completas y
# correctas en un fichero: tres «Salon/cocina», tres «Bano», tres «Dormitorio
# 1»... Contando los rotulos repetidos sobre el plano entero, la primera version
# producia **ocho hallazgos y los ocho eran falsos**, sobre un plano bien
# dibujado. Un rotulo solo se repite —en el sentido que importa— dentro de la
# misma vivienda, porque es ahi donde el cuadro tiene un unico hueco para el.

VIVIENDA_A = (
    ("Salon/cocina", (0.0, 0.0), (5.0, 4.0)),
    ("Bano", (6.0, 0.0), (8.0, 2.0)),
    ("Dormitorio 1", (0.0, 5.0), (4.0, 8.0)),
)
VIVIENDA_B = (
    ("Salon/cocina", (50.0, 0.0), (55.0, 4.0)),
    ("Bano", (56.0, 0.0), (58.0, 2.0)),
    ("Dormitorio 1", (50.0, 5.0), (54.0, 8.0)),
)


VT_DE_DOS = (("VT1/1", 2.0, -2.0), ("VT2/1", 52.0, -2.0))


def test_dos_viviendas_con_el_mismo_programa_no_dan_rotulos_duplicados(tmp_path):
    """Tres pisos iguales en un plano es lo normal en obra nueva, no un error."""
    revision = revisar(list(VIVIENDA_A) + list(VIVIENDA_B), tmp_path,
                       etiquetas_vt=VT_DE_DOS)
    assert revision.viviendas == 2
    assert coherencia.ETIQUETA_DUPLICADA not in tipos(revision), [
        h.descripcion for h in revision.hallazgos]


def test_un_rotulo_repetido_DENTRO_de_una_vivienda_si_se_dice(tmp_path):
    """La otra mitad: el chequeo tiene que seguir mordiendo donde importa."""
    revision = revisar(
        list(VIVIENDA_A) + list(VIVIENDA_B) + [("Bano", (6.0, 3.0), (8.0, 4.5))],
        tmp_path, etiquetas_vt=VT_DE_DOS)
    dup = [h for h in revision.hallazgos if h.tipo == coherencia.ETIQUETA_DUPLICADA]
    assert len(dup) == 1
    assert "Bano" in dup[0].entidad
    # Y dice en cual de las dos viviendas, que es lo que permite ir a mirarlo.
    assert dup[0].detalle.get("vivienda")
    assert "en «" in dup[0].entidad


def test_con_varias_viviendas_el_cuadro_no_se_cruza_y_se_dice_por_que(tmp_path, monkeypatch):
    """Un cuadro describe UNA vivienda. Cruzarlo contra los rotulos de tres
    daria discrepancias en todas las familias y ninguna seria cierta. Se declara
    no comprobado, con su motivo, en vez de comprobarlo mal.

    Hace falta el `monkeypatch` porque un `ACAD_TABLE` no se sintetiza de forma
    realista: sin el, este plano cae por la otra rama —«no trae cuadro»— y la
    que hay que probar no se ejecuta nunca.
    """
    import ezdxf

    from analyzer import cuadro_superficies as cs

    ruta = construir(list(VIVIENDA_A) + list(VIVIENDA_B), destino=tmp_path,
                     etiquetas_vt=VT_DE_DOS)
    monkeypatch.setattr(cs, "detectar_cuadro_superficies",
                        lambda doc: _Cuadro(["salon_cocina", "bano", "dormitorio_1"]))
    revision = coherencia.revisar(ezdxf.readfile(str(ruta)))

    assert revision.viviendas == 2
    motivos = " ".join(revision.no_comprobado)
    assert "2 viviendas" in motivos and "discrepancias falsas" in motivos
    # Y sobre todo: ni un solo hallazgo de contraste con el cuadro.
    for tipo in (coherencia.CUADRO_PIDE_PIEZA_NO_DIBUJADA,
                 coherencia.PIEZA_DIBUJADA_FUERA_DEL_CUADRO,
                 coherencia.RECUENTO_NO_COINCIDE):
        assert tipo not in tipos(revision)
