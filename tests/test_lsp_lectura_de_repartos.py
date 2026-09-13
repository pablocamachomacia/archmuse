# -*- coding: utf-8 -*-
"""Lo que el `.lsp` hace con la respuesta, reproducido sobre la respuesta real.

**Por qué existe** (criterios, «C-7, otra vez», 2026-09-13): los tests del
servidor comprueban lo que calcula el servidor, no lo que hace AutoCAD con ello.
El servidor devolvía UNA vivienda y su test pasaba; pero la respuesta LISP
llevaba el mismo bloque dos veces (`repartos` y una copia en `reparto`), y el
`.lsp`, que cuenta apariciones de `("cuadro_a_dibujar"` en el texto, ofreció
«2 viviendas VT1/3» sobre `v1plantas.dxf`.

El `.lsp` no se puede ejecutar en CI. Así que aquí se reproduce **su misma
lectura** —buscar marcas de texto con `am:pos` y leer el átomo que sigue con
`am:valor-tras`— sobre la respuesta real del servidor, y se comprueba además que
el fuente del `.lsp` busca de esa manera. Si alguien cambia una de las dos
mitades, uno de los dos tests se pone rojo.
"""
from __future__ import annotations

import os
import re
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from analyzer.geometria_recibida import payload_desde_dxf  # noqa: E402

LSP = open(os.path.join(RAIZ, "autocad", "archmuse.lsp"), encoding="utf-8").read()
FIXTURE = os.path.join(RAIZ, "tests", "fixtures", "cuadro_sintetico", "cuadro_sintetico.dxf")


def _funcion(nombre):
    ini = LSP.index("(defun %s " % nombre)
    fin = LSP.find("\n(defun ", ini + 1)
    return LSP[ini:fin if fin > 0 else len(LSP)]


# --- La misma lectura que el `.lsp`, en Python -------------------------------

def _pos(s, marca, desde):
    i = s.find(marca, desde)
    return None if i < 0 else i


def _valor_tras(s, clave, desde):
    """`am:valor-tras`: el átomo que sigue a `("clave" . `, cadena o no."""
    marca = '("%s" . ' % clave
    p = _pos(s, marca, desde)
    if p is None:
        return None
    ini = p + len(marca)
    if s[ini] == '"':
        texto, i = [], ini + 1
        while s[i] != '"':
            if s[i] == "\\":
                i += 1
            texto.append(s[i])
            i += 1
        return "".join(texto)
    fin = ini
    while fin < len(s) and s[fin] not in ") ":
        fin += 1
    return s[ini:fin]


def _zona_de_repartos(respuesta):
    ini = _pos(respuesta, '("repartos"', 0)
    if ini is None:
        return ""
    fin = _pos(respuesta, '("reparto" . ', ini)
    return respuesta[ini:fin] if fin is not None else respuesta[ini:]


def _viviendas_de(respuesta):
    zona, p, res = _zona_de_repartos(respuesta), 0, []
    while (p := _pos(zona, '("cuadro_a_dibujar"', p)) is not None:
        res.append(_valor_tras(zona, "vivienda", p) or "?")
        p += 1
    return res


def _motivos_indistinguibles(respuesta):
    zona, p, res = _zona_de_repartos(respuesta), 0, []
    while (p := _pos(zona, '("indistinguible" . T)', p)) is not None:
        motivo = _valor_tras(zona, "motivo", p)
        if motivo:
            res.append(motivo)
        p += 1
    return res


@pytest.fixture(scope="module")
def cliente():
    import app as srv

    return srv.app.test_client()


def _lisp(cliente, payload):
    return cliente.post("/api/medicion-geometria?formato=lisp", json=payload).get_data(as_text=True)


# --- 1. El fuente del `.lsp` lee así ------------------------------------------

def test_el_lsp_busca_las_tablas_solo_dentro_de_repartos():
    zona = _funcion("am:zona-de-repartos")
    assert '"(\\"repartos\\""' in zona and '"(\\"reparto\\" . "' in zona
    for nombre in ("am:viviendas-de", "am:bloque-de-vivienda", "am:motivos-indistinguibles"):
        assert "(am:zona-de-repartos respuesta)" in _funcion(nombre), nombre
    # Y el comando mira la zona, no la respuesta entera, para decidir si hay tabla.
    assert '(am:pos "(\\"cuadro_a_dibujar\\"" (am:zona-de-repartos respuesta) 0)' in _funcion("c:ARCHMUSE")


# --- 2. Una vivienda es una opción, no dos ------------------------------------

def test_una_vivienda_se_ofrece_una_sola_vez(cliente):
    """El caso de `v1plantas.dxf`, reproducido con el fixture sintético."""
    respuesta = _lisp(cliente, payload_desde_dxf(FIXTURE))
    assert _viviendas_de(respuesta) == ["VT1/3"]
    # Y el servidor ya no manda la copia: en toda la respuesta, un solo bloque.
    assert respuesta.count('("cuadro_a_dibujar"') == 1


def test_con_un_servidor_que_aun_mande_la_copia_tampoco_se_duplica(cliente):
    """La defensa del `.lsp` no depende de que el servidor se porte bien."""
    respuesta = _lisp(cliente, payload_desde_dxf(FIXTURE))
    ini = respuesta.index('("repartos"')
    bloque = respuesta[ini:]
    antigua = respuesta[:-1] + ' ("reparto" . ' + bloque[len('("repartos" . ('):] + ")"
    assert antigua.count('("cuadro_a_dibujar"') == 2, "la simulación del servidor antiguo no vale"
    assert _viviendas_de(antigua) == ["VT1/3"]


# --- 3. C-13: lo que no se ofrece, se dice ------------------------------------

def test_las_viviendas_indistinguibles_no_se_ofrecen_y_se_dice_por_que(cliente):
    from tests.test_c13_viviendas_indistinguibles import _dos_viviendas

    respuesta = _lisp(cliente, _dos_viviendas())
    assert _viviendas_de(respuesta) == []
    motivos = _motivos_indistinguibles(respuesta)
    assert len(motivos) == 1 and "C-13" in motivos[0] and "VT1/3" in motivos[0]


def test_el_comando_no_llama_fallo_a_un_criterio_firmado():
    """Sin tabla porque son indistinguibles no es «un fallo suyo»: el comando
    tiene que mirar C-13 antes de decir eso."""
    cuerpo = _funcion("c:ARCHMUSE")
    rama = cuerpo[cuerpo.index("(cond", cuerpo.index("2b.")):]
    assert rama.index("am:motivos-indistinguibles") < rama.index("fallo suyo")
    assert re.search(r"No te ofrezco estas viviendas", cuerpo)
