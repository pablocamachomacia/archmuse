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
probado: nada de `autocad/archmuse.lsp`. Ese fichero ya existe y se ejecutó el
2026-09-09 en AutoCAD 2027, pero lo que corre aquí es el lado del servidor, que
es todo lo verificable sin una licencia delante.

**Y una advertencia sobre en qué datos corren.** Los dos fixtures reales no
tienen ni una polilínea con el flag de cerrada mal puesto —la anonimización lo
borra— así que la sección 1 en verde **no prueba** que el cliente y el servidor
seleccionen lo mismo en un plano de verdad. Eso lo mide la sección 8.
"""
from __future__ import annotations

import json
import tempfile
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


# --- 8. `ssget` no sabe recuperar cierres, y el simulador tampoco puede ----
#
# Hasta el 2026-09-10 `payload_desde_dxf` filtraba con `parser._esta_cerrada`
# **con la recuperación geométrica activada**, que es justo lo que `ssget` no
# sabe hacer: en AutoCAD sólo se puede filtrar por el bit del código 70. El
# simulador era más listo que lo simulado, así que los tests de la sección 1
# comparaban el camino nuevo contra el viejo sin la diferencia que separa a los
# dos.
#
# El error no lo detectó nadie porque **ningún fixture del repositorio tenía el
# defecto**: los dos derivados de planos reales los reconstruye
# `derivar_fixture_anonimo.py` con `close=True`, así que la anonimización lo
# borra sin querer (0 de 22 y 0 de 9, medido). Sobre los originales sí está: 3
# de 22 en `V5.dxf`, 2 de 10 en `v2s.dxf`, 9 de 53 en `ejemplo.dxf`.
#
# `14_flag_de_cerrada_mal_puesto.dxf` existe para que esa diferencia se pueda
# medir sin depender de un plano de cliente.
#
# **Actualizado el 2026-09-10, y el cambio es el que este fichero pedía.** El
# cliente ya no filtra: manda todas las polilíneas de la capa con su flag en
# `cerrada`, y decide `parser._esta_cerrada` en el servidor. La diferencia de
# 2 recintos que estos tests medían ya no existe, y los tests lo dicen ahora
# con las cifras nuevas — que es lo que su versión anterior mandaba hacer el
# día que la mejora se hiciera.

FLAG_MALO = Path(__file__).parent / "fixtures" / "dxf_tortura" / "14_flag_de_cerrada_mal_puesto.dxf"


def _polilineas_por_flag(ruta: Path):
    """(bien flagueadas, con el flag mal puesto) de la capa de recintos."""
    from analyzer import parser

    doc = parser.load_document(str(ruta))
    capa = parser._resolver_capa(doc, None)[0].nombre
    bien = con_flag_malo = 0
    for entidad in doc.modelspace():
        if entidad.dxftype() != "LWPOLYLINE" or entidad.dxf.layer != capa:
            continue
        if parser._esta_cerrada(entidad, recuperar_geometria=False):
            bien += 1
        elif parser._esta_cerrada(entidad):
            con_flag_malo += 1
    return bien, con_flag_malo


def test_el_fixture_del_flag_mal_puesto_reproduce_el_defecto():
    """Si esto falla, el fixture ha dejado de servir para lo que existe y los
    dos tests siguientes estarían midiendo cero contra cero."""
    bien, con_flag_malo = _polilineas_por_flag(FLAG_MALO)
    assert (bien, con_flag_malo) == (4, 2)


def test_el_payload_manda_tambien_las_que_el_flag_declara_abiertas():
    """El cliente **no filtra**: manda las 7 polilíneas con su flag.

    Filtrar por el flag en el cliente es lo que hacía desaparecer superficie:
    `ssget` sólo sabe mirar el bit del código 70, y ese bit está mal puesto en
    los planos reales. Lo que el cliente no manda, el servidor no puede
    recuperar.
    """
    payload = payload_desde_dxf(str(FLAG_MALO))
    assert len(payload["recintos"]) == 7

    cerradas = [r for r in payload["recintos"] if r["cerrada"]]
    abiertas = [r for r in payload["recintos"] if not r["cerrada"]]
    assert len(cerradas) == 4, "las 4 bien flagueadas"
    assert len(abiertas) == 3, "las 2 con el flag mal puesto y la abierta de verdad"


def test_el_servidor_recupera_las_que_el_flag_declara_mal():
    """Y esto es lo que se compra mandándolas: **6 recintos medidos, 6
    enviables**. Antes del 2026-09-10 eran 6 y 4, y los 2 que faltaban eran
    superficie que no llegaba a la tabla del arquitecto.

    La polilínea abierta de verdad sigue descartándose: mandar todo no es medir
    todo, es dejar que decida quien sabe (`parser._esta_cerrada`).
    """
    from analyzer.geometria_recibida import SubidaMaterializada, validar
    from analyzer import parser

    payload = payload_desde_dxf(str(FLAG_MALO))
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / "materializado.dxf"
        SubidaMaterializada(validar(payload)).save(str(ruta))
        plano = parser.leer_plano(parser.load_document(str(ruta)))

    assert len(plano.rooms) == 6, sorted((r.label or "") for r in plano.rooms)


def test_el_color_viaja_para_que_el_contorno_agrupador_se_reconozca():
    """Sin el color, el DXF materializado sale entero en BYLAYER y
    `_discard_container_candidates` deja de distinguir una habitación de un
    contorno. Medido sobre `v1plantas.dxf`: 8 piezas pasaban a 10 y aparecían
    7,08 m² dibujados dos veces."""
    payload = payload_desde_dxf(str(PLANTA))
    assert all("color" in r for r in payload["recintos"])


@pytest.mark.parametrize("ruta", [PLANTA, SOLAPES])
def test_sobre_los_fixtures_reales_la_diferencia_es_cero_y_por_eso_no_saltaba(ruta):
    """Por qué el error pudo vivir aquí sin poner nada rojo.

    Los dos fixtures derivados no tienen ni una polilínea con el flag mal
    puesto, así que filtrar con recuperación o sin ella da exactamente lo
    mismo. Dejar esto escrito como test evita que alguien concluya, viendo la
    sección 1 en verde, que el camino está probado: está probado sobre datos
    que no contienen el caso.
    """
    bien, con_flag_malo = _polilineas_por_flag(ruta)
    assert con_flag_malo == 0
    assert len(payload_desde_dxf(str(ruta))["recintos"]) == bien


# --- 9. El tipo de cada texto viaja, y el materializador lo respeta -------
#
# La tercera divergencia `C-9`, del 2026-09-11. `escribir_dxf` escribía **todos**
# los textos como MTEXT; `parser.extract_labels` da prioridad al MTEXT sobre el
# TEXT para desempatar dos rótulos dentro del mismo recinto, así que aplanar los
# dos tipos a uno le quita a esa regla el dato con el que decide. Medido sobre
# `plantasimple.dxf` —651 MTEXT y 136 TEXT en la misma capa—: 157 recintos y 16
# viviendas con superficie por la web, 169 y 3 por el comando.
#
# El arreglo no añade criterio: el payload declara lo que el arquitecto tiene
# dibujado y aquí se escribe eso. La prioridad sigue viviendo en
# `extract_labels`, que es donde está probada.

MEZCLA = (Path(__file__).parent / "fixtures" / "dxf_tortura"
          / "15_mtext_y_text_en_el_mismo_recinto.dxf")


def _etiquetas(ruta_dxf):
    from analyzer import parser

    plano = parser.leer_plano(parser.load_document(str(ruta_dxf)))
    return sorted((r.label or "").strip() for r in plano.rooms)


def _materializar(payload):
    from analyzer import parser
    from analyzer.geometria_recibida import SubidaMaterializada

    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / "materializado.dxf"
        SubidaMaterializada(validar(payload)).save(str(ruta))
        plano = parser.leer_plano(parser.load_document(str(ruta)))
    return sorted((r.label or "").strip() for r in plano.rooms)


def test_el_payload_declara_el_tipo_de_cada_texto():
    """Sin esto no hay nada que respetar: es el dato que faltaba."""
    payload = payload_desde_dxf(str(MEZCLA))
    assert {t["tipo"] for t in payload["textos"]} == {"MTEXT", "TEXT"}
    assert all(t["tipo"] in ("MTEXT", "TEXT") for t in payload["textos"])
    json.dumps(payload)


def test_el_dxf_materializado_conserva_el_censo_de_tipos():
    """Los mismos MTEXT y los mismos TEXT que había en el dibujo del arquitecto.

    Se comprueba el censo, no la entidad una a una: lo que el motor mira es
    cuántos de cada tipo caen dentro de cada recinto, y un materializador que
    conserve el censo y las coordenadas le da exactamente lo mismo que el DXF
    original.
    """
    import collections

    from analyzer import parser
    from analyzer.geometria_recibida import SubidaMaterializada

    original = collections.Counter(
        e.dxftype() for e in parser.load_document(str(MEZCLA)).modelspace()
        if e.dxftype() in ("TEXT", "MTEXT"))

    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / "materializado.dxf"
        SubidaMaterializada(validar(payload_desde_dxf(str(MEZCLA)))).save(str(ruta))
        materializado = collections.Counter(
            e.dxftype() for e in parser.load_document(str(ruta)).modelspace()
            if e.dxftype() in ("TEXT", "MTEXT"))

    assert materializado == original == {"MTEXT": 4, "TEXT": 4}


def test_con_el_tipo_las_estancias_se_llaman_igual_por_las_dos_vias():
    """El fixture está hecho para que esto falle si el tipo no viaja: el TEXT con
    la cifra se escribe ANTES que el MTEXT con el nombre, así que sin prioridad
    gana la cifra."""
    esperado = ["BANO", "DORMITORIO 1", "DORMITORIO 2", "SALON"]
    assert _etiquetas(MEZCLA) == esperado
    assert _materializar(payload_desde_dxf(str(MEZCLA))) == esperado


def test_un_payload_antiguo_sin_tipo_sigue_midiendo_y_se_comporta_como_antes():
    """El cliente que no declare el tipo **no se queda fuera**: se le escribe todo
    en MTEXT, que es lo que se hacía antes de que el tipo viajara.

    Y este test deja escrito **qué se pierde** cuando eso pasa, que es el motivo
    de que el `.lsp` suba a 2.4.0: las cuatro estancias pasan a llamarse por su
    cifra. Un comando antiguo contra un servidor nuevo mide, pero mide lo de
    antes —y eso hay que poder verlo aquí, no descubrirlo en el plano de alguien.
    """
    payload = payload_desde_dxf(str(MEZCLA))
    for texto in payload["textos"]:
        texto.pop("tipo")
    assert _materializar(payload) == ["12.00 m2", "12.00 m2", "12.00 m2", "6.00 m2"]


@pytest.mark.parametrize("bruto", [None, "", "LINE", 7, "mtext", "text"])
def test_un_tipo_raro_no_revienta_la_medicion(bruto):
    """Igual que un código de color inesperado cuenta como BYLAYER. Y las minúsculas
    valen: el tipo llega de un `assoc 0` de AutoLISP, no de una constante nuestra.
    """
    from analyzer.geometria_recibida import _tipo_de_texto

    esperado = bruto.upper() if isinstance(bruto, str) and bruto.upper() in (
        "MTEXT", "TEXT") else "MTEXT"
    assert _tipo_de_texto(bruto) == esperado


def test_el_lsp_manda_el_tipo_que_lee_del_dibujo():
    """Entre Python y LISP no hay forma de compartir una constante, así que el
    contrato se comprueba leyendo el fuente —igual que hace `C-9` con la capa de
    la marca de borrador."""
    fuente = (Path(__file__).parent.parent / "autocad" / "archmuse.lsp").read_text(
        encoding="utf-8")
    assert '",\\"tipo\\":"   (am:json-cad tipo)' in fuente
