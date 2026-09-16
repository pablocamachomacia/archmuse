# -*- coding: utf-8 -*-
"""Sin estilo de texto propio: la tabla se dibuja con un estilo del plano y los
anchos los mide AutoCAD (`.lsp` 3.5.0).

**El caso, en AutoCAD, 2026-09-13, `.lsp` 3.4.1 sobre `v1plantas.dxf`:** «No he
podido dibujar la tabla al crear el estilo de texto «ARCHMUSE» con arial.ttf:
Error de automatización. Error de archivador.» El estilo existía para que lo
dibujado midiera lo mismo que el servidor medía con Arial. Pablo: depender de un
`.ttf` concreto es frágil. Decisión: no crear estilo; medir en AutoCAD.

**Y lo que no se sabe:** la 3.2.0 creó ese mismo estilo sin fallar. No se sabe
por qué la 3.4.1 no. Queda escrito en el `.lsp`, en PROGRESS y en el checklist.

Lo que se fija aquí:

1. El estilo de la tabla es uno del plano: el de su cuadro, si no el de sus
   rótulos, y si no hay ninguno **no se dibuja** (Pablo: «no inventes fuente:
   declara y no dibujes»).
2. Qué se mide lo decide el servidor; el servidor maqueta con esas medidas y no
   con Arial; una medida que falta no se sustituye a ojo.
3. El `.lsp` no crea estilos ni nombra una fuente, mide con `textbox` y dice por
   qué si no puede, y su lectura de la respuesta se reproduce sobre la real.
"""
from __future__ import annotations

import copy
import os
import re
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer.geometria_recibida import payload_desde_dxf  # noqa: E402

FIXTURE = os.path.join(RAIZ, "tests", "fixtures", "cuadro_sintetico", "cuadro_sintetico.dxf")
LSP = open(os.path.join(RAIZ, "autocad", "archmuse.lsp"), encoding="utf-8").read()


def _mq():
    from analyzer import maquetacion_cuadro
    return maquetacion_cuadro


@pytest.fixture(scope="module")
def cliente():
    import app as srv

    return srv.app.test_client()


def _medicion(cliente, **extra):
    cuerpo = dict(payload_desde_dxf(FIXTURE), punto=[40.0, 10.0],
                  ambitos={"TRASTERO": "interior"}, **extra)
    return cliente.post("/api/medicion-geometria", json=cuerpo).get_json()


def _cuadro(datos):
    return datos["repartos"][0]["cuadro_a_dibujar"]


def _medidas_falsas(textos, ancho_de=lambda t: 0.6 * len(t)):
    return [ancho_de(t) for t in textos]


# --- 1. El estilo sale del plano, o no se dibuja ----------------------------

def test_el_estilo_es_el_del_cuadro_si_no_el_de_los_rotulos_y_si_no_ninguno():
    mq = _mq()
    assert mq.estilo_de_texto(["CUADRO", "CUADRO", "OTRO"], ["ROTULOS"]) == "CUADRO"
    assert mq.estilo_de_texto([], ["ROT", "ROT", "X"]) == "ROT"
    assert mq.estilo_de_texto(["", " "], []) is None
    assert mq.estilo_de_texto([], []) is None


def test_la_medicion_dice_con_que_estilo_de_su_plano_se_dibuja(cliente):
    sin_cuadro = _cuadro(_medicion(cliente))
    assert sin_cuadro["estilo_texto"] == "Standard"        # el de sus rótulos
    con_cuadro = _cuadro(_medicion(cliente, estilos_de_cuadro=["cma medio", "cma medio"]))
    assert con_cuadro["estilo_texto"] == "cma medio"
    assert "motivo_sin_estilo" not in con_cuadro


def test_sin_cuadro_ni_rotulos_no_se_inventa_una_fuente(cliente):
    """La condición de Pablo: «si el plano no tiene ni cuadro ni rótulos de
    estancia de los que sacar el estilo, no inventes fuente: declara y no
    dibujes». Sin ningún texto no hay ni lo uno ni lo otro."""
    payload = payload_desde_dxf(FIXTURE)
    payload["textos"] = []
    datos = cliente.post("/api/medicion-geometria",
                         json=dict(payload, punto=[40.0, 10.0])).get_json()
    cuadros = [r["cuadro_a_dibujar"] for r in datos["repartos"] if r.get("cuadro_a_dibujar")]
    assert cuadros, "el caso ya no produce ninguna tabla: no prueba nada"
    for cuadro in cuadros:
        assert cuadro["estilo_texto"] is None
        assert "no inventa una fuente" in cuadro["motivo_sin_estilo"]


# --- 2. Qué se mide lo decide el servidor, y maqueta con eso ------------------

def test_se_pide_medir_cada_casilla_cada_palabra_y_el_espacio(cliente):
    mq = _mq()
    cuadro = _cuadro(_medicion(cliente))
    textos = cuadro["textos_a_medir"]
    assert len(textos) == len(set(textos))
    for celda in cuadro["celdas"]:
        assert celda["texto"] in textos
    # En el plano van las notas cortas (2026-09-15); son las que se miden.
    for nota in cuadro["notas_del_dibujo"]:
        assert all(p in textos for p in nota.split())
    assert all(t in textos for t in mq.TEXTOS_PARA_EL_ESPACIO)


def test_una_medida_que_falta_no_se_sustituye_a_ojo():
    mq = _mq()
    medir = mq.medidor_de_medidas(["Salón", "xx", "x x"], [2.0, 1.0, 1.5])
    assert medir("Salón") == pytest.approx(2.0 * mq.HOLGURA_DE_MEDIDA)
    with pytest.raises(mq.MedidaIncompleta):
        medir("Salón comedor")
    with pytest.raises(mq.MedidaIncompleta):
        mq.medidor_de_medidas(["Salón"], [2.0])          # sin la medida del espacio


def test_se_maqueta_con_lo_que_ha_medido_autocad_y_no_con_arial(cliente):
    """Si AutoCAD dice que un texto es muy ancho, su columna lo es. Con Arial
    saldría estrecha: es justo lo que haría partir palabras con otra fuente."""
    mq = _mq()
    cuadro = _cuadro(_medicion(cliente))
    textos = cuadro["textos_a_medir"]
    anchos = _medidas_falsas(textos, lambda t: 40.0 if t == "Dormitorio 1" else 0.6 * len(t))
    cuerpo = {
        "estilo_texto": cuadro["estilo_texto"], "punto": [40.0, 10.0],
        "altura_minima": cuadro["altura_minima"],
        "celdas": [[c["fila"], c["columna"], c["texto"]] for c in cuadro["celdas"]],
        "notas": cuadro["notas_del_dibujo"],
        "textos_medidos": textos, "anchos_medidos": anchos,
    }
    m = cliente.post("/api/maquetar-cuadro", json=cuerpo).get_json()
    assert m["cabe"] is True and m["estilo"] == cuadro["estilo_texto"]
    assert (m["x"], m["y"]) == (40.0, 10.0)
    h = m["altura_texto"]
    minimo = (40.0 * mq.HOLGURA_DE_MEDIDA + 2 * mq.MARGEN) * h
    assert all(a >= minimo - 1e-9 for a in m["anchos"]), (m["anchos"], minimo)


def test_el_servidor_se_niega_sin_estilo_o_con_medidas_incompletas(cliente):
    cuadro = _cuadro(_medicion(cliente))
    base = {
        "estilo_texto": cuadro["estilo_texto"], "punto": [40.0, 10.0],
        "altura_minima": cuadro["altura_minima"],
        "celdas": [[c["fila"], c["columna"], c["texto"]] for c in cuadro["celdas"]],
        "notas": cuadro["notas_del_dibujo"],
        "textos_medidos": cuadro["textos_a_medir"],
        "anchos_medidos": _medidas_falsas(cuadro["textos_a_medir"]),
    }
    sin_estilo = cliente.post("/api/maquetar-cuadro", json=dict(base, estilo_texto=""))
    assert sin_estilo.status_code == 422
    assert sin_estilo.get_json()["sin_estilo"] is True

    incompleto = copy.deepcopy(base)
    incompleto["textos_medidos"] = incompleto["textos_medidos"][:-3]
    incompleto["anchos_medidos"] = incompleto["anchos_medidos"][:-3]
    respuesta = cliente.post("/api/maquetar-cuadro", json=incompleto)
    assert respuesta.status_code == 400 and respuesta.get_json()["cabe"] is False

    # Dos clics (2026-09-16): sobre su cuadro se coloca igualmente, en el punto, y se avisa.
    encima = cliente.post("/api/maquetar-cuadro", json=dict(
        base, cajas_de_cuadros=[[[40.1, 9.9], [40.2, 9.95]]])).get_json()
    assert encima["cabe"] is True and (encima["x"], encima["y"]) == (40.0, 10.0)
    assert "tu cuadro de superficies" in encima["tapa"]


# --- 3. El `.lsp`: ni estilo propio ni fuente; mide y dice por qué ------------

def _funcion(nombre):
    ini = LSP.index("(defun %s " % nombre)
    fin = LSP.find("\n(defun ", ini + 1)
    return LSP[ini:fin if fin > 0 else len(LSP)]


def _sin_comentarios(texto):
    return "\n".join(linea.split(";;")[0] for linea in texto.splitlines())


def test_el_lsp_no_crea_estilos_de_texto_ni_nombra_una_fuente():
    codigo = _sin_comentarios(LSP)
    dibujar = _sin_comentarios(_funcion("am:dibujar-cuadro"))
    assert "vla-put-FontFile" not in codigo
    assert "(vla-Add estilos" not in codigo
    assert "(vla-Item estilos estilo)" in dibujar
    assert not re.search(r"\.(ttf|shx)\b", codigo, re.IGNORECASE)


def test_el_lsp_mide_con_textbox_en_el_estilo_del_plano_y_a_altura_uno():
    medir = _sin_comentarios(_funcion("am:medir-textos"))
    assert "'textbox" in medir
    assert "(cons 7 estilo)" in medir and "(cons 40 1.0)" in medir
    assert "(vl-catch-all-error-message caja)" in medir
    assert "*am:fallo-de-la-medida*" in medir


def test_el_lsp_manda_los_estilos_que_ya_estan_en_el_plano():
    assert '",\\"estilo\\":"' in _funcion("am:recolectar")
    assert '"\\"estilos_de_cuadro\\":["' in _funcion("am:con-dibujo")
    assert "'vla-GetCellTextStyle" in _funcion("am:estilos-de-cuadro")


def test_el_comando_sin_estilo_lo_dice_y_no_dibuja_ni_mide():
    comando = _sin_comentarios(_funcion("c:ARCHMUSE"))
    sin_estilo = comando.index('"motivo_sin_estilo"')
    assert sin_estilo < comando.index("(am:medir-textos textos estilo-texto)")
    assert comando.index("(am:medir-textos textos estilo-texto)") < comando.index(
        "(am:maquetar bloque textos medidos punto nil estilo-texto nil)")
    assert comando.index("(am:maquetar bloque") < comando.index("(am:dibujar-cuadro m celdas)")
    assert "*am:fallo-de-la-medida*" in comando


def test_la_lectura_del_lsp_sobre_la_respuesta_real_da_lo_que_mando_el_servidor(cliente):
    """«C-7, otra vez»: lo que el `.lsp` hace con la respuesta, reproducido sobre
    la respuesta LISP real —la lista de textos a medir y el texto de las notas."""
    cuerpo = dict(payload_desde_dxf(FIXTURE), punto=[40.0, 10.0], ambitos={"TRASTERO": "interior"})
    json_ = cliente.post("/api/medicion-geometria", json=cuerpo).get_json()
    lisp = cliente.post("/api/medicion-geometria?formato=lisp", json=cuerpo).get_data(as_text=True)
    cuadro = _cuadro(json_)

    def lee_cadena(s, i):
        res, i = [], i + 1
        while s[i] != '"':
            if s[i] == "\\":
                i += 1
            res.append(s[i])
            i += 1
        return "".join(res), i + 1

    def cadenas_tras(s, clave):
        marca = '("%s" . (' % clave
        p = s.index(marca) + len(marca)
        res = []
        while s[p] == '"':
            texto, p = lee_cadena(s, p)
            res.append(texto)
            if s[p] == " ":
                p += 1
        return res

    def textos_de_notas(s):
        ini = s.index('("notas" . (')
        fin = s.index('("preguntas_de_ambito"', ini)
        zona, res, p = s[ini:fin], [], 0
        while (p := zona.find('("texto" . ', p)) >= 0:
            texto, _ = lee_cadena(zona, p + len('("texto" . '))
            res.append(texto)
            p += 1
        return res

    bloque = lisp[lisp.index('("cuadro_a_dibujar"'):]
    assert cadenas_tras(bloque, "textos_a_medir") == cuadro["textos_a_medir"]
    # Los mismos textos, sin la cita del criterio: el comando los recibe sin códigos
    # internos (Pablo, 2026-09-16) y la web con ellos.
    from analyzer.texto_para_el_arquitecto import sin_codigos
    assert textos_de_notas(bloque) == [sin_codigos(n["texto"]) for n in cuadro["notas"]]
    # Y el fuente del `.lsp` lee con esas mismas marcas.
    assert '"(\\"notas\\" . ("' in _funcion("am:textos-de-notas")
    assert '"(\\"preguntas_de_ambito\\""' in _funcion("am:textos-de-notas")
