# -*- coding: utf-8 -*-
"""La herramienta mínima: `POST /api/medicion` y la página `/medir`.

Ejecutar:  pytest tests/test_medicion_endpoint.py

Encargo de Pablo del 2026-09-03 — el experimento de una semana: un arquitecto
sube un DXF, ve superficies fiables, se descarga el PDF. Lo que este fichero
fija es exactamente eso, de punta a punta y por HTTP:

1. Sale la medición **y** el PDF en la misma llamada (una sola ejecución de la
   Skill; el documento se perdía en un temporal hasta hoy).
2. **El total de cada vivienda es útil interior + útil exterior, y nada más.**
   Es la regla que da nombre a la iteración: no se acumulan magnitudes que no
   son acumulables. Aquí se comprueba sobre cifras reales medidas del DXF.
3. Una vivienda con un impedimento **no lleva total** aunque sus piezas estén
   medidas — la regla dura de `analyzer/medicion.py`, comprobada también a
   través del endpoint, que es donde la ve el arquitecto.
4. **La superficie construida se declara como no disponible, con motivo.** Un
   hueco mudo en un cuadro de superficies se lee como cero, y un cero ahí es
   una cifra falsa.
5. Los errores y las preguntas del plano llegan al cliente; no se tragan.

No se duplica geometría: los dos DXF sintéticos se construyen aquí porque
hacen falta dos casos distintos (uno limpio con total, otro con solape) y el de
`scripts/generar_acta_legible_demo.py` sólo cubre el segundo.
"""
from __future__ import annotations

import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# `app.py` llama a `init_db()` al importarse: `ARCHMUSE_DATA_DIR` tiene que
# apuntar a un temporal ANTES del import (mismo patrón que
# `tests/test_acta_legible_endpoint.py`).
from _carpetas_temporales import carpeta_temporal_de_test  # noqa: E402
_TMP_DATA = carpeta_temporal_de_test("archmuse_test_medicion_endpoint_")
os.environ.setdefault("ARCHMUSE_DATA_DIR", _TMP_DATA)

from analyzer import storage  # noqa: E402
storage.init_db()

import app as app_module  # noqa: E402


#: Una vivienda que se puede totalizar: cuatro piezas que no se pisan, todas
#: con rótulo conocido. Interior 20+12+4 = 36; exterior (terraza) 9. Total 45.
PIEZAS_LIMPIAS = (
    ("Salón/cocina", (0.0, 0.0), (5.0, 4.0)),      # 20 interior
    ("Dormitorio 1", (6.0, 0.0), (9.0, 4.0)),      # 12 interior
    ("Baño", (10.0, 0.0), (12.0, 2.0)),            #  4 interior
    ("Terraza", (10.0, 3.0), (13.0, 6.0)),         #  9 exterior
)

#: La misma vivienda con el dormitorio pisando 2 m² del salón: sin total.
PIEZAS_CON_SOLAPE = (
    ("Salón/cocina", (0.0, 0.0), (5.0, 4.0)),
    ("Dormitorio 1", (4.0, 0.0), (7.0, 2.0)),      # pisa 2 m² del salón
    ("Baño", (10.0, 0.0), (12.0, 2.0)),
    ("Terraza", (10.0, 3.0), (13.0, 6.0)),
)

#: Una segunda vivienda limpia, desplazada 40 m en X: 20+12+4 interior, 9
#: exterior, total 45. Se usa para las dos ramas del total de PLANTA — con
#: `PIEZAS_LIMPIAS` da una planta completa (90 m²), y con `PIEZAS_CON_SOLAPE`
#: da una planta a la que le falta una vivienda.
DESPLAZAMIENTO_SEGUNDA = 40.0


def _desplazadas(piezas, dx: float):
    return tuple((et, (x0 + dx, y0), (x1 + dx, y1)) for et, (x0, y0), (x1, y1) in piezas)


def _dxf(piezas, destino: Path, *, segunda=None) -> bytes:
    """Un DXF con una vivienda «VT1/1», y con «VT2/1» si se pasa `segunda`."""
    import ezdxf

    from analyzer import parser

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6  # metros
    doc.layers.add(parser.AREA_LAYER)
    msp = doc.modelspace()

    def _dibujar(conjunto, etiqueta_vivienda, x_etiqueta):
        for etiqueta, (x0, y0), (x1, y1) in conjunto:
            msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                               dxfattribs={"layer": parser.AREA_LAYER})
            msp.add_mtext(etiqueta, dxfattribs={"layer": parser.AREA_LAYER}).set_location(
                ((x0 + x1) / 2.0, (y0 + y1) / 2.0))
        msp.add_mtext(etiqueta_vivienda,
                      dxfattribs={"layer": parser.AREA_LAYER}).set_location((x_etiqueta, -3.0))

    _dibujar(piezas, "VT1/1", 6.0)
    if segunda is not None:
        _dibujar(_desplazadas(segunda, DESPLAZAMIENTO_SEGUNDA), "VT2/1",
                 6.0 + DESPLAZAMIENTO_SEGUNDA)

    ruta = destino / "planta.dxf"
    doc.saveas(str(ruta))
    return ruta.read_bytes()


@pytest.fixture(scope="module")
def dxf_limpio() -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        return _dxf(PIEZAS_LIMPIAS, Path(tmp))


@pytest.fixture(scope="module")
def dxf_con_solape() -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        return _dxf(PIEZAS_CON_SOLAPE, Path(tmp))


@pytest.fixture(scope="module")
def dxf_planta_completa() -> bytes:
    """Dos viviendas, las dos medibles: la planta SÍ lleva total (90,00 m²)."""
    with tempfile.TemporaryDirectory() as tmp:
        return _dxf(PIEZAS_LIMPIAS, Path(tmp), segunda=PIEZAS_LIMPIAS)


@pytest.fixture(scope="module")
def dxf_planta_incompleta() -> bytes:
    """Dos viviendas, una con solape: la planta NO lleva total, y se sabe cuál
    la bloquea."""
    with tempfile.TemporaryDirectory() as tmp:
        return _dxf(PIEZAS_LIMPIAS, Path(tmp), segunda=PIEZAS_CON_SOLAPE)


@pytest.fixture(scope="module")
def client():
    return app_module.app.test_client()


def _medir(client, contenido: bytes, **extra):
    datos = {"dxf": (BytesIO(contenido), "planta.dxf")}
    datos.update(extra)
    return client.post("/api/medicion", data=datos, content_type="multipart/form-data")


# --- 1. La página existe y no depende de la SPA ---------------------------

def test_la_pagina_se_sirve(client):
    resp = client.get("/medir")
    assert resp.status_code == 200
    cuerpo = resp.get_data(as_text=True)
    assert "Medición de superficies" in cuerpo
    # Una herramienta, no la SPA: no arrastra `app.js` ni sus 350 KB.
    assert "app.js" not in cuerpo


# --- 2. El camino completo: DXF -> superficies -> PDF ---------------------

def test_el_dxf_devuelve_superficies_y_el_pdf_en_la_misma_llamada(client, dxf_limpio):
    resp = _medir(client, dxf_limpio)
    assert resp.status_code == 200
    cuerpo = resp.get_json()

    assert len(cuerpo["viviendas"]) == 1
    assert cuerpo["piezas"] == 4
    assert cuerpo["viviendas_con_total"] == 1

    # El PDF viaja en la misma respuesta: una sola ejecución de la Skill y
    # ningún fichero que quede en el servidor entre dos llamadas.
    import base64
    pdf = base64.b64decode(cuerpo["informe_pdf_base64"])
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2000


# --- 3. LA REGLA DE LA ITERACIÓN: qué suma un total ----------------------

def test_el_util_interior_y_el_exterior_llegan_separados_y_sin_sumarse(client, dxf_limpio):
    """El criterio del arquitecto (2026-09-07), comprobado donde él lo ve.

    36 m² de piezas interiores y 9 m² de terraza, en dos cifras. Ni un metro
    más: no hay superficie construida en ninguna de las dos (no se calcula), ni
    contadores, ni ningún subtotal contado dos veces. Y **ninguna cifra que las
    sume**: el `total_util_m2` que valía 45,00 se ha retirado del contrato.
    """
    vivienda = _medir(client, dxf_limpio).get_json()["viviendas"][0]
    assert vivienda["util_interior_m2"] == pytest.approx(36.0)
    assert vivienda["util_exterior_m2"] == pytest.approx(9.0)
    assert "total_util_m2" not in vivienda


def test_entre_las_dos_cifras_no_se_pierde_ninguna_pieza(client, dxf_limpio):
    """Un arquitecto suma la columna a mano. Si las dos cifras no dan la suma de
    las filas que ve, lee un error de cálculo aunque no lo haya.

    Esto NO reintroduce el total: comprueba el invariante de que ninguna pieza
    se ha quedado fuera de las dos.
    """
    vivienda = _medir(client, dxf_limpio).get_json()["viviendas"][0]
    suma = round(sum(p["area_m2"] for p in vivienda["piezas"]), 2)
    assert vivienda["util_interior_m2"] + vivienda["util_exterior_m2"] == pytest.approx(suma)


def test_la_superficie_construida_se_declara_no_disponible_con_motivo(client, dxf_limpio):
    """Y NUNCA como 0,00 m² ni como un campo ausente: las dos cosas se leen
    como una cifra. ArchMuse no conoce los espesores de muro."""
    cuerpo = _medir(client, dxf_limpio).get_json()
    construida = cuerpo["superficie_construida"]
    assert construida["disponible"] is False
    assert "espesor" in construida["motivo"]
    # Y no se ha colado en ninguna cifra de vivienda.
    for vivienda in cuerpo["viviendas"]:
        assert "construida_m2" not in vivienda


# --- 4. Una vivienda que no cuadra no lleva total ------------------------

def test_una_vivienda_con_solape_llega_sin_total_y_con_el_motivo(client, dxf_con_solape):
    """Las piezas se miden igual: lo que falta es una decisión del arquitecto,
    no un cálculo. Un total que puede estar mal se copia a la memoria del
    proyecto y acaba firmado."""
    cuerpo = _medir(client, dxf_con_solape).get_json()
    vivienda = cuerpo["viviendas"][0]
    assert vivienda["util_interior_m2"] is None
    assert vivienda["util_exterior_m2"] is None, (
        "un solape puede caer a caballo entre lo interior y lo exterior: bloquea las dos")
    assert vivienda["impedimentos"], "sin cifra y sin motivo es indistinguible de un fallo"
    assert "dos veces" in " ".join(vivienda["impedimentos"])
    assert len(vivienda["piezas"]) == 4, "las piezas se miden aunque no haya total"
    assert cuerpo["viviendas_con_total"] == 0


# --- 5. Los errores llegan al arquitecto, no se tragan -------------------

def test_sin_archivo_da_400_con_mensaje(client):
    resp = client.post("/api/medicion", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert resp.get_json().get("error")


def test_un_fichero_que_no_es_dxf_da_400_con_mensaje(client):
    resp = client.post(
        "/api/medicion",
        data={"dxf": (BytesIO(b"no soy un dxf"), "plano.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert resp.get_json().get("error")


def test_un_plano_sin_unidad_deducible_devuelve_la_pregunta_no_un_numero(client, tmp_path):
    """El peor defecto posible: un plano en milímetros leído como metros
    cumple todos los mínimos y sale impecable. Aquí tiene que preguntar."""
    import ezdxf

    from analyzer import parser

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 0
    doc.layers.add(parser.AREA_LAYER)
    msp = doc.modelspace()
    # Estancias de 0,2 m²: ninguna unidad métrica las explica. Van rotuladas
    # para que la capa NO sea también ambigua y la pregunta que salga sea la de
    # la unidad, que es la que este test vigila.
    for i, rotulo in enumerate(("Salón", "Dormitorio 1", "Baño")):
        msp.add_lwpolyline([(0, i), (0.5, i), (0.5, i + 0.4), (0, i + 0.4)], close=True,
                           dxfattribs={"layer": parser.AREA_LAYER})
        msp.add_mtext(rotulo, dxfattribs={"layer": parser.AREA_LAYER}).set_location(
            (0.25, i + 0.2))
    ruta = tmp_path / "ambiguo.dxf"
    doc.saveas(str(ruta))

    cuerpo = _medir(client, ruta.read_bytes()).get_json()
    assert not cuerpo["viviendas"], "no se ha inventado ninguna superficie"
    assert cuerpo["preguntas_abiertas"], "una pregunta contestable no puede quedarse dentro"
    assert "unidad" in " ".join(cuerpo["preguntas_abiertas"]).lower()


def test_lo_que_no_se_ha_comprobado_viaja_con_el_resultado(client, dxf_limpio):
    """La cobertura declarada es parte del producto: en un cuadro de
    superficies, lo que falta importa tanto como lo que hay."""
    cuerpo = _medir(client, dxf_limpio).get_json()
    limites = " ".join(cuerpo["limites_de_la_herramienta"])
    assert "no construida" in limites
    assert "normativa" in limites


def test_los_limites_genericos_no_entierran_los_hallazgos_del_plano(client, dxf_con_solape):
    """Las dos listas van separadas porque son dos cosas.

    Con las dieciséis limitaciones genéricas mezcladas, «VT1/1 no lleva total
    porque hay metros dibujados dos veces» —lo único de ESTE plano, y la razón
    por la que alguien paga— quedaba en la línea 9 de un muro."""
    cuerpo = _medir(client, dxf_con_solape).get_json()

    hallazgos = cuerpo["hallazgos_del_plano"]
    assert hallazgos, "el defecto de este plano tiene que estar declarado"
    assert any("dos veces" in h for h in hallazgos)
    # Ninguna limitación genérica se ha colado entre los hallazgos...
    assert not any(" no comprueba: " in h for h in hallazgos)
    # ...ni al revés, y sin el prefijo con el id de la capacidad, que a un
    # arquitecto no le dice nada.
    limites = cuerpo["limites_de_la_herramienta"]
    assert limites
    assert not any(" no comprueba: " in l for l in limites)
    assert len(limites) == len(set(limites)), "la Skill y su capacidad repiten limitaciones"


# --- 6. El total de la PLANTA: las dos ramas -----------------------------
#
# Encargo de Pablo del 2026-09-03, segunda vuelta: un cuadro de superficies sin
# total de planta obliga al arquitecto a sumar la columna a mano, que es
# precisamente el trabajo que viene a delegar. Con dos condiciones, y cada una
# tiene su test aquí: cuando hay total va con el recuento al lado; cuando no lo
# hay, el hueco dice **en la cabecera** qué vivienda lo bloquea.

def test_planta_completa_lleva_total_con_el_recuento_al_lado(client, dxf_planta_completa):
    cuerpo = _medir(client, dxf_planta_completa).get_json()
    total = cuerpo["superficies_del_plano"]

    assert total["util_interior_m2"] == pytest.approx(72.0)  # 36 + 36
    assert total["util_exterior_m2"] == pytest.approx(18.0)  # 9 + 9
    assert total["motivo"] is None
    # El recuento viaja con la cifra: un total sin saber sobre cuántas
    # viviendas se ha calculado no se puede juzgar.
    assert total["viviendas"] == 2
    assert total["viviendas_con_total"] == 2


def test_cada_superficie_de_planta_es_la_suma_de_su_columna(client, dxf_planta_completa):
    """El arquitecto suma la columna a mano. Cada cifra de planta tiene que ser
    la suma de esa misma cifra en las viviendas que ve -- y la interior nunca
    lleva nada de la columna exterior."""
    cuerpo = _medir(client, dxf_planta_completa).get_json()
    for campo in ("util_interior_m2", "util_exterior_m2"):
        suma = round(sum(v[campo] for v in cuerpo["viviendas"]), 2)
        assert cuerpo["superficies_del_plano"][campo] == pytest.approx(suma)


def test_planta_con_una_vivienda_sin_medir_no_lleva_total_y_dice_cual(
        client, dxf_planta_incompleta):
    """La regla del 295,11: sumar sólo las medibles publicaría una superficie a
    la que le falta una vivienda entera. El motivo va CON el hueco, en la
    cabecera, no sólo abajo en la lista de hallazgos."""
    cuerpo = _medir(client, dxf_planta_incompleta).get_json()
    total = cuerpo["superficies_del_plano"]

    assert total["util_interior_m2"] is None
    assert total["util_exterior_m2"] is None
    assert total["motivo"], "un hueco sin motivo es indistinguible de un fallo"
    # El nombre de la bloqueante, en el propio motivo de la cabecera.
    bloqueante = next(v["vivienda"] for v in cuerpo["viviendas"]
                      if v["util_interior_m2"] is None)
    assert bloqueante in total["motivo"]
    # Y el recuento sigue estando: 1 de 2 se midió.
    assert (total["viviendas"], total["viviendas_con_total"]) == (2, 1)


def test_el_total_de_planta_nunca_suma_solo_las_medibles(client, dxf_planta_incompleta):
    """El bug exacto, un nivel por encima del de la vivienda: la vivienda buena
    mide 45 m² y ese número NO puede aparecer como total de la planta."""
    cuerpo = _medir(client, dxf_planta_incompleta).get_json()
    assert cuerpo["superficies_del_plano"]["util_interior_m2"] is None
    medibles = [v["util_interior_m2"] for v in cuerpo["viviendas"]
                if v["util_interior_m2"] is not None]
    assert medibles == [pytest.approx(36.0)], "la vivienda buena sí se mide"


def test_un_rotulo_de_vivienda_sin_recintos_advierte_junto_al_total(client, tmp_path):
    """No bloquea el total —podría ser una etiqueta de otra planta o de una
    leyenda— pero es la cifra del total la que podría estar corta, así que el
    aviso viaja con ella y no en una nota al pie."""
    import ezdxf

    from analyzer import parser

    contenido = _dxf(PIEZAS_LIMPIAS, tmp_path)
    ruta = tmp_path / "con_huerfano.dxf"
    ruta.write_bytes(contenido)
    doc = ezdxf.readfile(str(ruta))
    # Un «VT9/1» lejos de todo: ningún recinto va a parar ahí.
    doc.modelspace().add_mtext(
        "VT9/1", dxfattribs={"layer": parser.AREA_LAYER}).set_location((500.0, 500.0))
    doc.saveas(str(ruta))

    total = _medir(client, ruta.read_bytes()).get_json()["superficies_del_plano"]
    assert total["util_interior_m2"] == pytest.approx(36.0), "las cifras se publican igual"
    assert total["advertencias"], "y el rótulo huérfano viaja con él"
    assert "VT9/1" in " ".join(total["advertencias"])


def test_un_plano_sin_viviendas_no_inventa_un_total_de_cero(client, tmp_path):
    """Cero metros cuadrados es una cifra, y la cifra sería falsa."""
    import ezdxf

    from analyzer import parser

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    doc.layers.add(parser.AREA_LAYER)
    ruta = tmp_path / "vacio.dxf"
    doc.saveas(str(ruta))

    cuerpo = _medir(client, ruta.read_bytes()).get_json()
    assert not cuerpo["viviendas"]
    assert cuerpo["superficies_del_plano"]["util_interior_m2"] is None
    assert cuerpo["superficies_del_plano"]["util_exterior_m2"] is None


# --- 7. Los cuatro arreglos de la auditoría de demo (2026-09-04) ----------
#
# Cada uno cierra algo que se reprodujo delante de la pantalla, no algo que se
# temía. Los números y los textos de los docstrings salen de esa sesión.

def test_un_plano_por_encima_del_limite_responde_json_y_no_html(client):
    """ARREGLO 1. Sin `errorhandler(413)`, Werkzeug devolvía su página HTML,
    `medir.html` hacía `r.json()` y el arquitecto leía «No se ha podido
    contactar con ArchMuse: SyntaxError: Unexpected token '<'…» — que además es
    falso, porque el servidor había contestado."""
    limite = app_module.app.config["MAX_CONTENT_LENGTH"]
    resp = _medir(client, b"0" * (limite + 1024))

    assert resp.status_code == 413
    assert "json" in resp.headers.get("Content-Type", ""), "el cliente espera JSON"
    cuerpo = resp.get_json()
    assert cuerpo and cuerpo.get("error")
    assert "MB" in cuerpo["error"]
    # En castellano y diciendo las dos cifras: lo que pesa y lo que cabe.
    assert "límite" in cuerpo["error"]
    assert "<!doctype" not in resp.get_data(as_text=True).lower()


def test_el_limite_de_subida_deja_sitio_a_los_planos_reales(client):
    """Los tres planos del cliente pesan 18,2 / 18,6 / 19,2 MB. Con el límite
    anterior (25 MB) iban al 75 % del tope: un plano con mobiliario o con una
    hoja más lo cruzaba."""
    limite_mb = app_module.app.config["MAX_CONTENT_LENGTH"] / (1024 * 1024)
    assert limite_mb >= 60, "un DXF de proyecto real pasa de 25 MB con facilidad"


def test_la_pagina_cancela_el_arrastre_fuera_del_recuadro():
    """ARREGLO 2. Sin `preventDefault` a nivel de documento, soltar el DXF
    fuera de la zona hace que el navegador NAVEGUE al fichero y la página
    desaparezca. Comprobación estructural; el comportamiento real se verificó
    en Chrome (`drop_fuera_de_zona_prevenido` pasó de `false` a `true`)."""
    pagina = (RAIZ / "static" / "medir.html").read_text(encoding="utf-8")
    assert 'document.addEventListener(evento' in pagina
    assert '["dragover", "drop"].forEach' in pagina
    assert "elZona.contains(ev.target)" in pagina, "la zona gestiona lo suyo"


def test_un_fichero_ilegible_no_filtra_la_ruta_del_servidor(client):
    r"""ARREGLO 3. En pantalla salía, literal:

        File 'C:\Users\<usuario>\AppData\Local\Temp\archmuse_acta_9mpdjj7m\
        plano_del_cliente.dxf' is not a DXF file.

    Inglés, mensaje crudo de `ezdxf`, y la ruta del temporal del servidor
    delante del cliente."""
    cuerpo = _medir(client, b"esto no es un dxf" * 400).get_json()
    texto = " ".join(cuerpo.get("preguntas_abiertas") or [])

    assert texto, "un fichero ilegible tiene que decir algo"
    for prohibido in ("C:\\", "/tmp", "Temp\\", "archmuse_acta", ".dxf'"):
        assert prohibido not in texto, "se filtra una ruta interna: %r" % texto
    for ingles in ("is not a DXF file", "DXFStructureError", "Error", "File '"):
        assert ingles not in texto, "mensaje crudo de librería: %r" % texto
    assert "fichero" in texto.lower() or "DXF" in texto


def test_un_fichero_ilegible_se_marca_como_error_y_no_como_pregunta(client):
    """ARREGLO 3, la otra mitad. Un fichero corrupto salía bajo el titular
    «ArchMuse necesita que decidas una cosa antes de medir», invitando a
    rellenar capa y unidad — dos campos que no lo pueden arreglar."""
    cuerpo = _medir(client, b"esto no es un dxf" * 400).get_json()
    assert cuerpo["lectura_fallida"] is True


def test_un_plano_que_solo_necesita_una_decision_no_se_marca_como_ilegible(
        client, tmp_path):
    """El reverso, y es el que importa no romper: una capa que hay que elegir
    SÍ es una pregunta contestable, y tiene que seguir saliendo como tal."""
    contenido = _dxf(PIEZAS_LIMPIAS, tmp_path)
    cuerpo = _medir(client, contenido, capa="NO_EXISTE_ESTA_CAPA").get_json()

    assert cuerpo["lectura_fallida"] is False
    assert cuerpo["preguntas_abiertas"], "tiene que seguir preguntando"
    # Y la pregunta buena de `parser` se conserva íntegra, con sus candidatas.
    assert "00 areas" in " ".join(cuerpo["preguntas_abiertas"])


def test_el_pdf_no_afirma_que_dos_cifras_distintas_coinciden(client, dxf_limpio):
    """ARREGLO 5. El PDF decía «El total coincide con la superficie que ocupan
    realmente las piezas (66,33 m²)» junto a un TOTAL de 66,32 — dos números
    distintos en líneas contiguas, en una frase que afirma que coinciden. En
    `ejemplo.dxf` pasaba en 3 de las 5 viviendas con total."""
    import base64
    import io as _io

    from pypdf import PdfReader

    cuerpo = _medir(client, dxf_limpio).get_json()
    pdf = base64.b64decode(cuerpo["informe_pdf_base64"])
    texto = PdfReader(_io.BytesIO(pdf)).pages[0].extract_text()

    assert "no se pisan entre sí" in texto
    assert "coincide con la superficie" not in texto
