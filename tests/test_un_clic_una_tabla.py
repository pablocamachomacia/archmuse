# -*- coding: utf-8 -*-
"""Un clic, una tabla (PRD `docs/prd/2026-09-15-un-clic-una-tabla.md`).

`C-17`, **propuesto, pendiente de firma**: el clic elige la vivienda más cercana;
si hay duda, no mide y lo dice. Y la condición que no se negocia: **las cifras de
esa vivienda son idénticas** a las de la planta entera y a las de medirla sola.

Todo sobre planos **sintéticos** (`tests/_planta_de_varias_viviendas.py`). Las dos
peticiones del comando se reproducen aquí con el mismo filtro de zonas que aplica
el `.lsp` (`vivienda_en_punto.corta_alguna_zona`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

import _planta_de_varias_viviendas as planta  # noqa: E402

from analyzer import vivienda_en_punto as vp  # noqa: E402
from analyzer.geometria_recibida import payload_desde_dxf  # noqa: E402

SEPARACION = 6.0


@pytest.fixture(scope="module")
def client():
    import app as modulo

    modulo.app.config["TESTING"] = True
    with modulo.app.test_client() as cliente:
        yield cliente


def _payload(tmp_path, nombre="planta", **kw):
    ruta = planta.generar(tmp_path / ("%s.dxf" % nombre), separacion=SEPARACION, **kw)
    return payload_desde_dxf(str(ruta), "00 areas")


def _junto_a(i):
    """A 1 m a la izquierda del salón de la vivienda `i`; la de al lado, a 6 m."""
    ox, oy = planta.origenes(i + 1, SEPARACION)[i]
    return [ox - 1.0, oy + 2.0]


def _fase1(client, cuerpo, punto, **extra):
    datos = {k: v for k, v in cuerpo.items() if k != "otras_polilineas"}
    datos.update(punto=punto, **extra)
    return client.post("/api/vivienda-en-punto", json=datos).get_json()


def _otras_en_zonas(cuerpo, uno):
    zonas = [uno["zonas"][i:i + 4] for i in range(0, len(uno["zonas"]), 4)]
    return [o for o in cuerpo["otras_polilineas"] if vp.corta_alguna_zona(o["vertices"], zonas)]


def _fase2(client, cuerpo, punto, otras, vivienda):
    datos = dict(cuerpo, punto=punto, otras_polilineas=otras, vivienda=vivienda)
    r = client.post("/api/medicion-geometria", json=datos)
    assert r.status_code == 200, r.data[:800]
    return r.get_json()


def _por_clic(client, cuerpo, punto):
    uno = _fase1(client, cuerpo, punto)
    assert uno["ok"], uno
    otras = _otras_en_zonas(cuerpo, uno)
    return uno, otras, _fase2(client, cuerpo, punto, otras, json.loads(uno["vivienda_json"]))


def _entera(client, cuerpo, punto):
    r = client.post("/api/medicion-geometria", json=dict(cuerpo, punto=punto))
    assert r.status_code == 200, r.data[:800]
    return r.get_json()


def _reparto(respuesta, nombre):
    return [x for x in respuesta["repartos"] if x.get("vivienda") == nombre]


def _vivienda(respuesta, nombre):
    return [v for v in respuesta["viviendas"] if v["vivienda"] == nombre]


# --- 1. El clic elige ---------------------------------------------------------

def test_el_clic_junto_a_cada_vivienda_elige_esa(client, tmp_path):
    cuerpo = _payload(tmp_path, n=4)
    for i, nombre in enumerate(planta.nombres(4)):
        uno = _fase1(client, cuerpo, _junto_a(i))
        assert uno["ok"] is True and uno["vivienda"] == nombre, uno
        assert uno["aviso"].startswith("Mido %s:" % nombre), uno["aviso"]
        assert "1,00 m" in uno["aviso"]


def test_un_clic_entre_dos_viviendas_no_mide_y_dice_las_dos_distancias(client, tmp_path):
    cuerpo = _payload(tmp_path, n=4)
    # La terraza de VT1/1 acaba en x = 11 y el salón de VT2/1 empieza en x = 18.
    uno = _fase1(client, cuerpo, [14.5, 2.0])
    assert uno["ok"] is False and uno["vivienda"] is None
    assert uno["motivo"].startswith("No mido")
    assert "VT1/1" in uno["motivo"] and "VT2/1" in uno["motivo"] and "3,50 m" in uno["motivo"]
    assert "C-17" in uno["motivo"]
    assert "zonas" not in uno


def test_dentro_de_una_pieza_no_hay_duda_aunque_la_de_al_lado_este_a_un_palmo(client, tmp_path):
    """Medido el 2026-09-15 en el maestro: 7 de 52 clics dentro de la pieza mayor
    de una vivienda decían «No mido», porque la de al lado quedaba a menos de 1 m.
    Viviendas separadas 0,20 m: dentro de la terraza de VT1/1 se mide; en la junta
    entre las dos, a 0,10 m de cada una, sigue sin medirse."""
    ruta = planta.generar(tmp_path / "pegadas.dxf", n=2, separacion=-0.8)
    cuerpo = payload_desde_dxf(str(ruta), "00 areas")
    dentro = _fase1(client, cuerpo, [10.9, 1.5])
    assert dentro["ok"] is True and dentro["vivienda"] == "VT1/1", dentro
    junta = _fase1(client, cuerpo, [11.1, 1.5])
    assert junta["ok"] is False and "No mido" in junta["motivo"], junta


def test_un_clic_lejos_de_todo_no_mide(client, tmp_path):
    uno = _fase1(client, _payload(tmp_path, n=2), [-40.0, 2.0])
    assert uno["ok"] is False
    assert "40,00 m" in uno["motivo"] and "VT1/1" in uno["motivo"]


@pytest.mark.parametrize("i", [0, 2])
def test_el_clic_distingue_por_su_posicion_dos_viviendas_con_el_mismo_rotulo(client, tmp_path, i):
    """**Decisión de Pablo, 2026-09-15**: «el clic decide la vivienda aunque su
    rótulo se repita. Dos viviendas con el mismo nombre se distinguen por su
    posición; nunca se fusionan ni se suman». Enmienda de `C-13` para el clic.

    VT1/1 está dos veces (viviendas 0 y 2) y la segunda tiene el dormitorio 2 más
    ancho: cada clic tiene que dar la tabla de SU vivienda —la misma que midiéndola
    sola— y ninguna puede ser la suma de las dos."""
    punto = _junto_a(i)
    cuerpo = _payload(tmp_path, n=3, repetida=True)
    uno, _otras, clic = _por_clic(client, cuerpo, punto)
    assert uno["vivienda"] == "VT1/1" and "por su posición" in uno["aviso"], uno["aviso"]
    assert len(clic["repartos"]) == 1 and clic["repartos"][0]["ok"] is True, clic["repartos"]
    assert "C-13" not in " ".join(clic["repartos"][0]["impedimentos"])

    sola = _entera(client, _payload(tmp_path, "sola", n=3, repetida=True, solo=[i]), punto)
    assert [x["cuadro_a_dibujar"]["celdas"] for x in clic["repartos"]] == \
        [x["cuadro_a_dibujar"]["celdas"] for x in _reparto(sola, "VT1/1")]


def test_las_dos_viviendas_repetidas_dan_cada_una_su_tabla(client, tmp_path):
    cuerpo = _payload(tmp_path, n=3, repetida=True)
    primera = _por_clic(client, cuerpo, _junto_a(0))[2]["repartos"][0]["cuadro_a_dibujar"]["celdas"]
    tercera = _por_clic(client, cuerpo, _junto_a(2))[2]["repartos"][0]["cuadro_a_dibujar"]["celdas"]
    assert primera != tercera, "las dos VT1/1 han dado la misma tabla: no se distinguen"


def test_la_planta_entera_sigue_sin_publicar_las_viviendas_repetidas(client, tmp_path):
    """Sin clic no hay posición que las distinga: `C-13` sigue igual en la
    medición de la planta entera."""
    entera = _entera(client, _payload(tmp_path, n=3, repetida=True), _junto_a(0))
    repetidas = _reparto(entera, "VT1/1")
    assert repetidas and all(x.get("indistinguible") for x in repetidas)


def test_las_distancias_de_la_duda_son_las_de_c17():
    assert (vp.FACTOR_DE_DUDA, vp.MARGEN_DE_DUDA_M, vp.DISTANCIA_MAXIMA_M) == (2.0, 1.0, 30.0)


# --- 2. Las cifras son idénticas ------------------------------------------------

@pytest.mark.parametrize("i", range(4))
def test_la_tabla_por_clic_es_identica_a_la_de_la_planta_entera(client, tmp_path, i):
    cuerpo = _payload(tmp_path, n=4, dudoso=True)
    punto = _junto_a(i)
    nombre = planta.nombres(4)[i]
    entera = _entera(client, cuerpo, punto)
    uno, otras, clic = _por_clic(client, cuerpo, punto)

    assert len(_reparto(entera, nombre)) == 1
    assert clic["repartos"] == _reparto(entera, nombre)
    assert _vivienda(clic, nombre) == _vivienda(entera, nombre)
    assert clic["preguntas_de_ambito"] == _reparto(entera, nombre)[0]["preguntas_de_ambito"]
    # Y de verdad se ha mandado menos: ni muebles ni muros.
    assert len(otras) < len(cuerpo["otras_polilineas"])
    assert not any(o["capa"] in ("01 muros", "02 mobiliario") for o in otras)


@pytest.mark.parametrize("i", range(4))
def test_la_tabla_por_clic_es_identica_a_la_de_la_vivienda_sola(client, tmp_path, i):
    """«Medirla sola»: un plano con sólo esa vivienda y todo lo suyo. Se comparan
    las cifras y las casillas; las notas nombran polilíneas por su handle, que en
    otro fichero es otro."""
    punto = _junto_a(i)
    nombre = planta.nombres(4)[i]
    _uno, _otras, clic = _por_clic(client, _payload(tmp_path, n=4, dudoso=True), punto)
    sola = _entera(client, _payload(tmp_path, "sola", n=4, dudoso=True, solo=[i]), punto)

    assert [x["cuadro_a_dibujar"]["celdas"] for x in clic["repartos"]] == \
        [x["cuadro_a_dibujar"]["celdas"] for x in _reparto(sola, nombre)]
    claves = ("util_interior_m2", "util_exterior_m2")
    assert [{k: v[k] for k in claves} for v in _vivienda(clic, nombre)] == \
        [{k: v[k] for k in claves} for v in _vivienda(sola, nombre)]


def test_la_zona_de_un_rotulo_dudoso_manda_tambien_la_polilinea_lejana(client, tmp_path):
    """El rótulo de construida de VT1/1 tiene dos polilíneas a su alcance: su
    envolvente y un contorno de parcela que no toca la vivienda. Sin la lejana, el
    rótulo pasaría por inequívoco y saldría una cifra que la planta entera deja
    vacía: es lo que la zona evita, y este test lo demuestra quitándola."""
    cuerpo = _payload(tmp_path, n=4, dudoso=True)
    punto = _junto_a(0)
    uno, otras, clic = _por_clic(client, cuerpo, punto)
    assert any(o["capa"] == "00 PARCELA" for o in otras)

    sin_parcela = [o for o in otras if o["capa"] != "00 PARCELA"]
    trampa = _fase2(client, cuerpo, punto, sin_parcela, json.loads(uno["vivienda_json"]))
    assert trampa["repartos"] != clic["repartos"], (
        "sin la polilínea lejana la tabla sale igual: el plano de prueba ya no tiene "
        "un rótulo dudoso y este test no demuestra nada")


# --- 3. Los bordes ----------------------------------------------------------------

def test_las_capas_de_clasificacion_se_piden_enteras_antes_de_elegir(client, tmp_path):
    cuerpo = _payload(tmp_path, n=2)
    capas = ["0", "00 areas", "AM_UTIL_INT"]
    uno = _fase1(client, cuerpo, _junto_a(0), capas_del_dibujo=capas)
    assert uno["ok"] is False and uno["pide_capas_enteras"] == ["AM_UTIL_INT"]
    dos = _fase1(client, cuerpo, _junto_a(0), capas_del_dibujo=capas, capas_enteras_enviadas=True)
    assert dos["ok"] is True and dos["capas_enteras"] == ["AM_UTIL_INT"]


def test_si_la_vivienda_pedida_no_es_la_del_punto_no_se_dibuja_nada(client, tmp_path):
    cuerpo = _payload(tmp_path, n=3)
    otra = json.loads(_fase1(client, cuerpo, _junto_a(1))["vivienda_json"])
    respuesta = _fase2(client, cuerpo, _junto_a(0), cuerpo["otras_polilineas"], otra)
    assert len(respuesta["repartos"]) == 1 and respuesta["repartos"][0]["ok"] is False
    assert "no es la que sale" in respuesta["repartos"][0]["motivo"]


def test_sin_punto_no_se_elige(client, tmp_path):
    cuerpo = {k: v for k, v in _payload(tmp_path, n=2).items() if k != "otras_polilineas"}
    r = client.post("/api/vivienda-en-punto", json=cuerpo)
    assert r.status_code == 400 and "punto" in r.get_json()["motivo"]


# --- 4. El `.lsp` (leyendo el fuente; el clic no se ha probado en la interfaz) ------

LSP = (TESTS.parent / "autocad" / "archmuse.lsp").read_text(encoding="utf-8")


def _defun(nombre):
    ini = LSP.index("(defun %s " % nombre)
    fin = LSP.find("\n(defun ", ini + 1)
    return "\n".join(l.split(";")[0] for l in LSP[ini:fin if fin > 0 else len(LSP)].splitlines())


def test_el_comando_elige_antes_de_medir_y_sale_si_no_hay_vivienda():
    comando = _defun("c:ARCHMUSE")
    recolectar = comando.index("(am:recolectar capa cuadros)")
    elegir = comando.index("(am:elegir-por-clic capa geometria punto)")
    medir = comando.index("(am:post cuerpo)")
    assert comando.index("(am:pedir-punto)") < recolectar < elegir < medir
    rama = comando[elegir:comando.index("(am:otras-polilineas capa", elegir)]
    assert "(if (null eleccion)" in rama and "(exit)" in rama


def test_el_lsp_filtra_las_otras_capas_con_la_misma_prueba_que_el_servidor():
    """`am:caja-corta-zona-p` y `vivienda_en_punto.corta_alguna_zona` tienen que
    cortar lo mismo, o las cifras por clic dejan de ser las de la planta."""
    caja = " ".join(_defun("am:caja-corta-zona-p").split())
    for comparacion in ("(<= x0 (nth 2 z))", "(>= x1 (nth 0 z))",
                        "(<= y0 (nth 3 z))", "(>= y1 (nth 1 z))"):
        assert comparacion in caja, comparacion
    otras = _defun("am:otras-polilineas")
    assert "(am:caja-corta-zona-p datos zonas)" in otras
    assert "(am:en-la-lista-p (cdr (assoc 8 datos)) enteras)" in otras
    # Y el orden de las zonas es el del servidor: (x0 y0 x1 y1).
    assert vp.corta_alguna_zona([[0, 0], [1, 1]], [(0.5, 0.5, 2, 2)])
    assert not vp.corta_alguna_zona([[0, 0], [1, 1]], [(1.5, 0.5, 2, 2)])


def test_elegir_por_clic_dice_el_motivo_en_cada_salida_sin_vivienda():
    cuerpo = _defun("am:elegir-por-clic")
    assert "(am:post-a (am:url-vivienda)" in cuerpo
    assert '(am:valor-tras r \\"motivo\\" 0)'.replace('\\"', '"') in cuerpo
    assert "avisa con esta l" in cuerpo
    assert '"pide_capas_enteras"' in cuerpo


def test_un_servidor_sin_la_ruta_nueva_se_dice_asi():
    assert "(= (car r) 404)" in _defun("am:post-a")
    assert "versión anterior a este comando" in LSP


def test_la_respuesta_para_el_comando_lleva_lo_que_lee_el_lsp(client, tmp_path):
    cuerpo = {k: v for k, v in _payload(tmp_path, n=2).items() if k != "otras_polilineas"}
    cuerpo["punto"] = _junto_a(1)
    texto = client.post("/api/vivienda-en-punto?formato=lisp", json=cuerpo).data.decode("utf-8")
    for marca in ('("ok" . T)', '("aviso" . "Mido VT2/1:', '("vivienda_json" . "',
                  '("zonas" . (', '("lsp" . "'):
        assert marca in texto, (marca, texto[:600])
