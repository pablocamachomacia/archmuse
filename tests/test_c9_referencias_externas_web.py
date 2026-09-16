# -*- coding: utf-8 -*-
"""`C-9` punto 5: la web tiene que saber de referencias externas como el comando.

Con `C-15` el comando se para si los recintos están en una referencia externa y
dice qué fichero abrir. La web seguía buscando capa por parecido en lo que queda
en el dibujo: en el mejor caso preguntaba por capas que no tienen nada que ver, y
en el peor elegía una y medía otra cosa.

**Lo que un DXF deja ver, y lo que no.** La definición de la referencia llega sin
entidades, pero sí llegan su ruta y sus capas, con el prefijo `referencia|capa`.
Así que la web sabe que la referencia **tiene** la capa de recintos, no cuántas
polilíneas hay dentro. Se para cuando el dibujo no tiene ninguna polilínea en esa
capa y una referencia sí la tiene: ahí los recintos no pueden estar en otro sitio.
Si hay polilíneas en los dos, no se puede saber desde el DXF y se mide el dibujo.

Plano sintético, con coordenadas y nombres inventados.
"""
from __future__ import annotations

import io

import ezdxf
import pytest

from analyzer import parser

CAPA = parser.AREA_LAYER
FICHERO = "maestro_sintetico.dwg"


def _dibujo(con_recintos_propios=False, con_capa_en_la_referencia=True):
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    doc.add_xref_def(FICHERO, "MAESTRO")
    doc.modelspace().add_blockref("MAESTRO", (0, 0))
    if con_capa_en_la_referencia:
        doc.layers.add("MAESTRO|%s" % CAPA)
    doc.layers.add("00 MARCO")
    msp = doc.modelspace()
    # Lo que queda en la hoja: rectángulos de marco y viñetas, que por parecido
    # podrían pasar por recintos.
    for i in range(6):
        x = i * 6.0
        msp.add_lwpolyline([(x, 0), (x + 4, 0), (x + 4, 3), (x, 3)], close=True,
                           dxfattribs={"layer": "00 MARCO"})
        msp.add_mtext("Salón/cocina" if i % 2 else "Dormitorio 1",
                      dxfattribs={"layer": "00 MARCO", "insert": (x + 2, 1.5)})
    if con_recintos_propios:
        doc.layers.add(CAPA)
        for i in range(4):
            x = 100 + i * 6.0
            msp.add_lwpolyline([(x, 0), (x + 4, 0), (x + 4, 3), (x, 3)], close=True,
                               dxfattribs={"layer": CAPA})
            msp.add_mtext("Dormitorio %d" % (i + 1), dxfattribs={"layer": CAPA, "insert": (x + 2, 1.5)})
    return doc


def test_si_los_recintos_solo_pueden_estar_en_la_referencia_se_para_y_dice_el_fichero():
    with pytest.raises(parser.RecintosEnReferenciaExterna) as error:
        parser.leer_plano(_dibujo())
    assert FICHERO in str(error.value)
    assert error.value.candidatas == []


def test_tambien_si_el_arquitecto_nombra_la_capa():
    with pytest.raises(parser.RecintosEnReferenciaExterna):
        parser.leer_plano(_dibujo(), layer=CAPA)


def test_con_recintos_en_el_propio_dibujo_se_miden_los_suyos():
    plano = parser.leer_plano(_dibujo(con_recintos_propios=True))
    assert len(plano.rooms) == 4


def test_una_referencia_sin_la_capa_de_recintos_no_para_nada():
    with pytest.raises(parser.CapaIndeterminada) as error:
        parser.leer_plano(_dibujo(con_capa_en_la_referencia=False), layer=CAPA)
    assert not isinstance(error.value, parser.RecintosEnReferenciaExterna)


def test_la_web_lo_devuelve_como_pregunta_de_capa_sin_candidatas(tmp_path):
    import app as modulo

    ruta = tmp_path / "hoja.dxf"
    _dibujo().saveas(str(ruta))
    modulo.app.config["TESTING"] = True
    with modulo.app.test_client() as cliente:
        respuesta = cliente.post("/api/analizar", data={"dxf": (io.BytesIO(ruta.read_bytes()), "hoja.dxf")},
                                 content_type="multipart/form-data")
    assert respuesta.status_code == 400
    cuerpo = respuesta.get_json()
    assert FICHERO in cuerpo["error"]
    assert cuerpo["capa"]["candidatas"] == []
