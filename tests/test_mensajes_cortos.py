# -*- coding: utf-8 -*-
"""Lo que se reparó o se dejó fuera, en una frase corta para un arquitecto.

**Pablo, 2026-09-17:** «He reparado 10 contornos...» y «la polilínea llega con 2
vértices...» salían en la línea de comandos tal cual, largos y con detalle de
programa (uno por polilínea, con su handle). En la línea de comandos: una frase
corta y comprensible. El detalle, al registro y a la lista estructurada, que
sigue viajando entera para la web y el PDF.

Y ningún mensaje puede prometer lo que el programa no hace: «dilo: copiar tus
filas es mejor que inventarlas» invitaba a decir cómo se titula su cuadro, y la
tabla de ArchMuse ya no copia filas del cuadro del arquitecto (plantilla fija,
2026-09-13).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from analyzer.geometria_recibida import payload_desde_dxf

RAIZ = Path(__file__).resolve().parent.parent
PLANTA = RAIZ / "tests" / "fixtures" / "reales" / "planta_tres_viviendas.dxf"
LSP = (RAIZ / "autocad" / "archmuse.lsp").read_text(encoding="utf-8")
LARGO_MAXIMO = 160


@pytest.fixture
def client():
    import app as modulo

    modulo.app.config["TESTING"] = True
    with modulo.app.test_client() as cliente:
        yield cliente


def _una_frase_corta(texto):
    assert texto, "no hay aviso"
    assert len(texto) <= LARGO_MAXIMO, (len(texto), texto)
    assert texto.count(". ") == 0 and texto.endswith("."), texto
    assert not re.search(r"\b[CD]-\d+\b|handle|[0-9A-F]{5,}", texto), texto
    assert not re.search(r"\b[A-ZÁÉÍÓÚ]{2,}\b", texto), "sin mayúsculas de grito: %s" % texto


def test_lo_descartado_se_dice_en_una_frase_y_el_detalle_sigue_en_la_lista(client):
    cuerpo = payload_desde_dxf(str(PLANTA))
    for i in range(2):
        cuerpo["recintos"].append({"handle": "DEADBEE%d" % i, "capa": "00 areas",
                                   "vertices": [[0.0, 0.0], [1.0, 0.0]]})
    respuesta = client.post("/api/medicion-geometria", json=cuerpo).get_json()
    aviso = respuesta["geometria_descartada_aviso"]
    _una_frase_corta(aviso)
    assert aviso.startswith("2 ")
    assert len(respuesta["geometria_descartada"]) == 2


def test_sin_descartes_no_hay_aviso(client):
    respuesta = client.post("/api/medicion-geometria", json=payload_desde_dxf(str(PLANTA))).get_json()
    assert "geometria_descartada_aviso" not in respuesta


def test_lo_reparado_se_dice_en_una_frase(client):
    cuerpo = payload_desde_dxf(str(PLANTA))
    # Un pico de área cero: se repara sin que cambie la superficie (`C-10`).
    recinto = next(r for r in cuerpo["recintos"] if len(r["vertices"]) >= 4)
    v = recinto["vertices"]
    recinto["vertices"] = v[:2] + [v[1], [v[1][0] + 0.5, v[1][1]], v[1]] + v[2:]
    respuesta = client.post("/api/medicion-geometria", json=cuerpo).get_json()
    assert respuesta.get("geometria_reparada"), "el caso no ha producido ninguna reparación"
    _una_frase_corta(respuesta["geometria_reparada_aviso"])


def _sin_comentarios(texto):
    return "\n".join(l.split(";")[0] if not l.lstrip().startswith(";") else "" for l in texto.splitlines())


def test_el_comando_ensena_el_aviso_y_no_la_lista_de_motivos():
    codigo = " ".join(_sin_comentarios(LSP).split())
    assert '(am:valor-tras respuesta "geometria_descartada_aviso" 0)' in codigo
    assert '(am:lista-de-motivos respuesta "geometria_descartada" 0)' not in codigo
    assert "El servidor ha descartado" not in codigo
    assert "El servidor no ha descartado nada" not in codigo


def test_ningun_mensaje_invita_a_que_copie_sus_filas():
    codigo = _sin_comentarios(LSP)
    assert "copiar tus filas" not in codigo
    assert "se titula de otra forma, dilo" not in codigo
