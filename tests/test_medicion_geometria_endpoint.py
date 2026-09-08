# -*- coding: utf-8 -*-
"""`/api/medicion-geometria` — la puerta para un cliente CAD.

**Qué vigila este fichero, y es una sola cosa por encima de todas.** Que la
medición que sale por esta ruta sea **exactamente** la misma que sale por
`/api/medicion` con el mismo plano. Si divergen aunque sea en un céntimo, el
modo de entrada nuevo está midiendo por su cuenta, y eso es un fallo, no una
tolerancia: sería el segundo motor de medición que todo el PRD existe para no
construir.

**Los payloads no están escritos a mano.** Se derivan de los dos fixtures reales
anonimizados con `geometria_recibida.payload_desde_dxf()`, que simula lo que hace
`ssget` en el cliente: coge las polilíneas cerradas de la capa de recintos y
todos los textos, sin emparejar nada. Un payload inventado probaría lo que el
autor del test cree que manda AutoCAD.

**Lo que estos tests NO prueban**, y está escrito aquí para que nadie lo dé por
probado: nada de `autocad/archmuse.lsp`, que no existe todavía y no se podrá
ejecutar hasta que haya una licencia de AutoCAD. Lo que se comprueba aquí es el
lado del servidor, que es todo lo verificable sin ella.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from analyzer.geometria_recibida import (
    PayloadInvalido, a_sexpresion, payload_desde_dxf, validar,
)

FIXTURES = Path(__file__).parent / "fixtures" / "reales"
PLANTA = FIXTURES / "planta_tres_viviendas.dxf"
SOLAPES = FIXTURES / "vivienda_con_solapes.dxf"


@pytest.fixture
def client():
    import app as modulo

    modulo.app.config["TESTING"] = True
    with modulo.app.test_client() as cliente:
        yield cliente


def _por_geometria(client, ruta: Path, **extra):
    cuerpo = payload_desde_dxf(str(ruta))
    cuerpo.update(extra)
    return client.post("/api/medicion-geometria", json=cuerpo)


def _por_fichero(client, ruta: Path):
    return client.post(
        "/api/medicion",
        data={"dxf": (ruta.open("rb"), ruta.name)},
        content_type="multipart/form-data")


# --- 1. La comprobación que importa: las dos rutas dan lo mismo -------------

@pytest.mark.parametrize("ruta", [PLANTA, SOLAPES], ids=["planta", "solapes"])
def test_la_geometria_da_exactamente_la_misma_medicion_que_el_fichero(client, ruta):
    """Al céntimo, vivienda a vivienda y pieza a pieza.

    Es el guardián de que no hay un segundo motor de medición. Si esto se pone
    rojo, no se ajusta la tolerancia: se busca por qué el camino nuevo mide
    distinto.
    """
    por_geometria = _por_geometria(client, ruta).get_json()
    por_fichero = _por_fichero(client, ruta).get_json()

    assert por_geometria["viviendas"] == por_fichero["viviendas"]
    assert por_geometria["superficies_del_plano"] == por_fichero["superficies_del_plano"]
    assert por_geometria["piezas"] == por_fichero["piezas"]
    assert por_geometria["hallazgos_del_plano"] == por_fichero["hallazgos_del_plano"]


def test_las_cifras_conocidas_de_la_planta_real_llegan_por_esta_ruta(client):
    """Las mismas que `tests/test_fixtures_reales.py`, ahora por HTTP y JSON."""
    cuerpo = _por_geometria(client, PLANTA).get_json()
    medidas = {v["vivienda"]: (v["util_interior_m2"], v["util_exterior_m2"])
               for v in cuerpo["viviendas"]}
    assert medidas == {
        "VT1/3": (58.78, 7.54),
        "VT2/2": (50.97, 7.47),
        "VT3/3": (59.11, 7.45),
    }
    assert cuerpo["superficies_del_plano"]["util_interior_m2"] == 168.86
    assert cuerpo["superficies_del_plano"]["util_exterior_m2"] == 22.46


def test_la_vivienda_con_solapes_llega_bloqueada_y_con_el_motivo(client):
    """La rama que no publica cifra tiene que atravesar la ruta nueva igual."""
    cuerpo = _por_geometria(client, SOLAPES).get_json()
    vivienda = cuerpo["viviendas"][0]
    assert vivienda["util_interior_m2"] is None
    assert vivienda["util_exterior_m2"] is None
    assert any("dos veces" in m for m in vivienda["impedimentos"])
    assert len(vivienda["piezas"]) == 9, "las piezas se miden aunque no haya cifra"


# --- 2. El acta y el PDF siguen saliendo por el camino de siempre ----------

def test_la_ruta_nueva_no_se_salta_el_acta_ni_el_pdf(client):
    """La costura es real: si esta ruta hubiera esquivado la Skill, aquí no
    habría ni acta de procedencia ni documento."""
    cuerpo = _por_geometria(client, PLANTA).get_json()
    assert cuerpo["informe_pdf_base64"], "el PDF se genera por el mismo camino"
    assert cuerpo["sello"], "el acta viaja sellada"
    assert cuerpo["limites_de_la_herramienta"], "la cobertura declarada también"


def test_las_entidades_de_origen_vuelven_para_poder_ir_a_mirarlas(client):
    """El handle de AutoCAD no se puede conservar dentro del DXF materializado,
    así que vuelve aparte: es el inventario de qué entidades del dibujo del
    arquitecto han producido esta medición."""
    cuerpo = _por_geometria(client, PLANTA).get_json()
    assert len(cuerpo["entidades_de_origen"]) == 22
    assert all(h for h in cuerpo["entidades_de_origen"])


# --- 3. Nada se cae en silencio -------------------------------------------

def test_una_polilinea_que_no_encierra_superficie_se_declara_no_se_tira(client):
    """Dos vértices no encierran nada. Descartarlo callando sería superficie que
    falta sin que nadie lo sepa."""
    cuerpo = payload_desde_dxf(str(PLANTA))
    cuerpo["recintos"].append(
        {"handle": "DEADBEEF", "capa": "00 areas", "vertices": [[0.0, 0.0], [1.0, 0.0]]})
    respuesta = client.post("/api/medicion-geometria", json=cuerpo).get_json()

    descartada = respuesta["geometria_descartada"]
    assert len(descartada) == 1
    assert descartada[0]["handle"] == "DEADBEEF"
    assert "vértice" in descartada[0]["motivo"]
    # Y la medición del resto no se ha movido ni un céntimo.
    assert respuesta["superficies_del_plano"]["util_interior_m2"] == 168.86


def test_el_campo_de_descartes_viaja_siempre_aunque_este_vacio(client):
    cuerpo = _por_geometria(client, PLANTA).get_json()
    assert cuerpo["geometria_descartada"] == []


# --- 4. Los errores del cliente son del cliente ----------------------------

def test_sin_cuerpo_json_da_400_con_mensaje(client):
    respuesta = client.post("/api/medicion-geometria",
                            data="no soy json", content_type="text/plain")
    assert respuesta.status_code == 400
    assert "JSON" in respuesta.get_json()["error"]


def test_sin_recintos_da_400_y_dice_que_mandar(client):
    respuesta = client.post("/api/medicion-geometria", json={"textos": []})
    assert respuesta.status_code == 400
    assert "recintos" in respuesta.get_json()["error"]


def test_un_vertice_no_numerico_da_400_antes_de_escribir_nada(client):
    respuesta = client.post("/api/medicion-geometria", json={
        "insunits": 6,
        "recintos": [{"handle": "1", "capa": "00 areas",
                      "vertices": [[0, 0], [1, "eñe"], [1, 1]]}],
    })
    assert respuesta.status_code == 400
    assert "número" in respuesta.get_json()["error"]


def test_ningun_recinto_medible_da_400_y_no_una_medicion_vacia(client):
    """Cero metros cuadrados es una cifra, y la cifra sería falsa."""
    respuesta = client.post("/api/medicion-geometria", json={
        "insunits": 6,
        "recintos": [{"handle": "1", "vertices": [[0, 0], [1, 0]]}],
    })
    assert respuesta.status_code == 400
    assert "superficie" in respuesta.get_json()["error"]


def test_la_validacion_no_escribe_nada_cuando_falla():
    """Se valida todo antes de materializar: un DXF a medio escribir con la
    mitad de los recintos produciría una medición que parece buena y le falta
    media vivienda."""
    with pytest.raises(PayloadInvalido):
        validar({"insunits": 6, "recintos": [
            {"vertices": [[0, 0], [1, 0], [1, 1]]},
            {"vertices": "esto no es una lista"},
        ]})


# --- 5. La escala la sigue decidiendo el motor -----------------------------

def test_el_insunits_del_cliente_llega_al_detector_de_escala(client):
    """El cliente manda lo que dice su dibujo; quien decide sigue siendo
    `analyzer/escala.py`. Con la cabecera en milímetros sobre una geometría que
    está en metros, la medición no puede salir igual."""
    cuerpo = payload_desde_dxf(str(PLANTA))
    cuerpo["insunits"] = 4                     # milímetros: mentira sobre este plano
    respuesta = client.post("/api/medicion-geometria", json=cuerpo).get_json()

    interior = respuesta["superficies_del_plano"]["util_interior_m2"]
    assert interior != 168.86, (
        "con la cabecera cambiada la medición tiene que cambiar o negarse; si sale "
        "igual, el $INSUNITS del cliente no se está usando")


# --- 6. La s-expresión para AutoLISP --------------------------------------

def test_la_sexpresion_es_leible_por_autolisp(client):
    """AutoLISP no tiene parser JSON. Diez líneas de Python aquí, con tests,
    sustituyen a ~150 de LISP que no se podrían probar sin AutoCAD."""
    cuerpo = payload_desde_dxf(str(PLANTA))
    respuesta = client.post("/api/medicion-geometria?formato=lisp", json=cuerpo)

    assert respuesta.status_code == 200
    texto = respuesta.get_data(as_text=True)
    assert texto.startswith("((")
    assert '("util_interior_m2" . 168.86)' in texto
    assert '("vivienda" . "VT1/3")' in texto
    # El PDF no viaja por aquí, y se declara en vez de mandarse troceado.
    assert '("informe_pdf_base64" . nil)' in texto


def test_una_superficie_que_no_se_publica_sale_como_nil(client):
    """`nil` es exactamente lo que significa en LISP una cifra que no está, y es
    lo que la tabla tiene que poder distinguir de un cero."""
    cuerpo = payload_desde_dxf(str(SOLAPES))
    texto = client.post("/api/medicion-geometria?formato=lisp",
                        json=cuerpo).get_data(as_text=True)
    assert '("util_interior_m2" . nil)' in texto
    assert '("util_exterior_m2" . nil)' in texto


@pytest.mark.parametrize("valor,esperado", [
    (None, "nil"),
    (True, "T"),
    (False, "nil"),
    (45.0, "45.0"),
    ("Salón", '"Salón"'),
    ('con "comillas"', '"con \\"comillas\\""'),
    ([1, 2], "(1 2)"),
    ({"a": 1}, '(("a" . 1))'),
    ({"a": None}, '(("a" . nil))'),
    ([], "()"),
])
def test_el_serializador_de_sexpresion(valor, esperado):
    assert a_sexpresion(valor) == esperado


def test_la_sexpresion_escapa_lo_que_romperia_el_read():
    """Un rótulo con comillas o con una barra invertida no puede partir la
    lectura en el cliente: sería un fallo que sólo aparecería con el plano de
    alguien y sin AutoCAD no se podría depurar."""
    texto = a_sexpresion({"rotulo": 'Salón "grande"\\anexo'})
    assert texto == '(("rotulo" . "Salón \\"grande\\"\\\\anexo"))'


# --- 7. El payload derivado es el que mandaría el cliente -----------------

def test_el_payload_derivado_trae_todo_lo_que_ssget_cogeria():
    """22 polilíneas cerradas de la capa de recintos y los 26 textos del plano —
    los 22 rótulos de estancia más las 4 etiquetas de vivienda. El cliente NO
    empareja: manda las dos cosas sueltas y el emparejamiento lo hace el motor.
    """
    payload = payload_desde_dxf(str(PLANTA))
    assert payload["insunits"] == 6
    assert payload["capa_de_recintos"] == "00 areas"
    assert len(payload["recintos"]) == 22
    assert len(payload["textos"]) == 26
    assert all(r["handle"] for r in payload["recintos"])
    assert all(len(r["vertices"]) >= 3 for r in payload["recintos"])
    # Y es JSON de verdad: si algo no fuera serializable, el cliente no podría
    # mandarlo y este test es el sitio donde se ve, no en AutoCAD.
    json.dumps(payload)
