# -*- coding: utf-8 -*-
"""Un plano del tamaño de un maestro de estudio se mide en menos de 30 segundos.

**El caso (Pablo, 2026-09-15, AutoCAD).** Sobre un plano maestro real —677
polilíneas en «00 areas», 55 sin el flag de cerrada— ARCHMUSE estuvo más de
cinco minutos colgado. Medido ese día, fuera del repositorio, sobre una copia en
AutoCAD Core Console: el plano tiene además 9.220 polilíneas en otras capas,
6.280 textos y 25 tablas, y el envío del `.lsp` pesa 2,6 MB. El `.lsp` lo arma
en 6-8 s; el resto era del servidor.

**El plano de este test es sintético** —ni un dato de aquel plano— y del mismo
tamaño: 96 viviendas de 7 piezas más 5 trasteros (677 recintos, 55 sin el flag),
9.220 polilíneas de muros y mobiliario y 6.280 textos. Lo que no reproduce: las
25 tablas (ezdxf no crea `ACAD_TABLE`).

El servidor se mide en un proceso aparte con un plazo: si se cuelga, el test
falla en vez de colgar la suite.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
#: El objetivo es menos de 30 s en total, y el `.lsp` se lleva unos 8 s del
#: plano real armando el envío. Al servidor le quedan 20.
PLAZO_SERVIDOR_S = 20.0

VIVIENDAS = 96
SIN_FLAG = 55
OTRAS_POLILINEAS = 9220
TEXTOS = 6280
PIEZAS = (  # rótulo, x0, y0, x1, y1 — dentro de una vivienda de 12 x 9
    ("Salón", 0.0, 0.0, 5.0, 4.0), ("Cocina", 5.1, 0.0, 8.1, 3.0),
    ("Dormitorio 1", 0.0, 4.1, 3.5, 7.5), ("Dormitorio 2", 3.6, 4.1, 6.6, 7.5),
    ("Baño", 8.2, 0.0, 10.2, 2.0), ("Pasillo", 6.7, 3.1, 8.1, 7.5),
    ("Terraza", 0.0, 7.6, 4.0, 8.9),
)


def generar_plano_grande(ruta: Path) -> dict:
    import ezdxf

    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    for capa in ("00 areas", "00 TEXTO", "01 muros", "02 mobiliario", "03 cotas"):
        doc.layers.add(capa)
    msp = doc.modelspace()
    recintos = textos = otras = sin_flag = 0
    columnas = 12
    for v in range(VIVIENDAS):
        ox, oy = (v % columnas) * 14.0, (v // columnas) * 11.0
        piezas = list(PIEZAS) + ([("Trastero", 10.3, 0.0, 11.8, 2.0)] if v < 5 else [])
        for rotulo, x0, y0, x1, y1 in piezas:
            puntos = [(ox + x0, oy + y0), (ox + x1, oy + y0), (ox + x1, oy + y1), (ox + x0, oy + y1)]
            abierta = sin_flag < SIN_FLAG and recintos % 11 == 3
            if abierta:
                msp.add_lwpolyline(puntos + [puntos[0]], close=False, dxfattribs={"layer": "00 areas"})
                sin_flag += 1
            else:
                msp.add_lwpolyline(puntos, close=True, dxfattribs={"layer": "00 areas"})
            msp.add_mtext(rotulo, dxfattribs={"layer": "00 areas", "char_height": 0.15,
                                              "insert": (ox + (x0 + x1) / 2, oy + (y0 + y1) / 2)})
            recintos += 1
            textos += 1
        msp.add_mtext("VT%d/%d" % (v + 1, v % 4 + 1), dxfattribs={
            "layer": "00 TEXTO", "char_height": 0.3, "insert": (ox + 6.0, oy + 9.5)})
        textos += 1
    i = 0
    while otras < OTRAS_POLILINEAS:
        v = i % VIVIENDAS
        ox, oy = (v % columnas) * 14.0, (v // columnas) * 11.0
        dx, dy = (i * 0.37) % 11.0, (i * 0.53) % 8.0
        capa = "01 muros" if i % 3 else "02 mobiliario"
        msp.add_lwpolyline([(ox + dx, oy + dy), (ox + dx + 0.6, oy + dy),
                            (ox + dx + 0.6, oy + dy + 0.4)], close=bool(i % 2),
                           dxfattribs={"layer": capa})
        otras += 1
        i += 1
    i = 0
    while textos < TEXTOS:
        v = i % VIVIENDAS
        ox, oy = (v % columnas) * 14.0, (v // columnas) * 11.0
        msp.add_text("%d,%02d" % (i % 9 + 1, i % 100), dxfattribs={
            "layer": "03 cotas", "height": 0.1, "insert": (ox + (i * 0.29) % 12.0, oy - 0.3)})
        textos += 1
        i += 1
    doc.saveas(str(ruta))
    return {"recintos": recintos, "sin_flag": sin_flag, "otras": otras, "textos": textos}


_MEDIR = r"""
import json, os, sys, tempfile, time
sys.path.insert(0, sys.argv[1])
os.chdir(sys.argv[1])
os.environ.pop("ANTHROPIC_API_KEY", None)
from analyzer.geometria_recibida import payload_desde_dxf
cuerpo = payload_desde_dxf(sys.argv[2], "00 areas")
cuerpo["punto"] = [200.0, 100.0]
datos = json.dumps(cuerpo)
import app
cliente = app.app.test_client()
t = time.perf_counter()
r = cliente.post("/api/medicion-geometria?formato=lisp", data=datos, content_type="application/json")
print(json.dumps({"segundos": time.perf_counter() - t, "estado": r.status_code,
                  "bytes_envio": len(datos), "repartos": r.data.count(b'"vivienda"')}))
"""


@pytest.fixture(scope="module")
def plano_grande(tmp_path_factory):
    ruta = tmp_path_factory.mktemp("plano_grande") / "plano_grande.dxf"
    tamano = generar_plano_grande(ruta)
    return ruta, tamano


def test_el_plano_sintetico_tiene_el_tamano_del_maestro(plano_grande):
    _, tamano = plano_grande
    assert tamano == {"recintos": 677, "sin_flag": 55, "otras": 9220, "textos": 6280}


def test_el_servidor_mide_el_plano_grande_en_menos_de_20_segundos(plano_grande, tmp_path):
    ruta, _ = plano_grande
    entorno = dict(os.environ, ARCHMUSE_DATA_DIR=str(tmp_path / "datos"))
    t = time.monotonic()
    try:
        r = subprocess.run([sys.executable, "-c", _MEDIR, str(RAIZ), str(ruta)],
                           capture_output=True, text=True, env=entorno,
                           timeout=PLAZO_SERVIDOR_S * 6)
    except subprocess.TimeoutExpired:
        pytest.fail("el servidor no ha contestado en %.0f s con el plano grande"
                    % (time.monotonic() - t))
    assert r.returncode == 0, r.stderr[-2000:]
    medida = json.loads(r.stdout.strip().splitlines()[-1])
    assert medida["estado"] == 200, medida
    assert medida["segundos"] < PLAZO_SERVIDOR_S, (
        "el servidor tarda %.1f s con el plano grande (%d bytes de envío)"
        % (medida["segundos"], medida["bytes_envio"]))
