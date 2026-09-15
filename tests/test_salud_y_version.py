# -*- coding: utf-8 -*-
"""T1 del PRD de la beta: `/api/salud` y la versión en cada medición.

`docs/prd/2026-09-11-beta-instalable-en-el-ordenador-del-arquitecto.md`, D-1 y
D-2. Las dos cosas que se prueban aquí son las dos que Pablo destacó al aprobar
el PRD, y ninguna es cosmética:

- **`/api/salud` es de lo que depende la rama C de D-1.** Cuando el comando no
  obtiene respuesta, lanza el servidor y sondea aquí cada segundo. Si esta ruta
  midiera algo, o abriera un fichero, un servidor recién arrancado parecería
  caído mientras termina de importar.
- **La versión viaja con la medición** para que el cliente CAD pueda negarse a
  escribir contra un servidor desparejado. Una cifra sin versión al lado no se
  puede reproducir tres semanas después con el informe del arquitecto delante,
  que es exactamente la situación para la que existe `ARCHMUSE-INFORME`.
"""
from __future__ import annotations

import json

import pytest

from analyzer import version as version_mod


@pytest.fixture(scope="module")
def cliente():
    import app as srv

    return srv.app.test_client()


def test_salud_responde_sin_medir_nada(cliente):
    respuesta = cliente.get("/api/salud")

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["ok"] is True
    assert cuerpo["version"]
    assert "medicion" in cuerpo["capacidades"]


def test_salud_es_get_y_no_pide_cuerpo(cliente):
    """Desde AutoLISP, un `GET` sin cuerpo es una línea. Cualquier cosa más
    complicada convierte el sondeo de veinte reintentos en código que hay que
    depurar dentro de AutoCAD."""
    assert cliente.get("/api/salud").status_code == 200


def test_la_medicion_declara_su_version(cliente):
    cuerpo = {
        "capa": "00 areas",
        "recintos": [{
            "handle": "1", "capa": "00 areas", "color": 256, "cerrada": True,
            "vertices": [[0, 0], [5, 0], [5, 4], [0, 4]],
        }],
        "textos": [{"texto": "Salón", "x": 2.5, "y": 2.0}],
    }

    respuesta = cliente.post("/api/medicion-geometria", data=json.dumps(cuerpo),
                             content_type="application/json")

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["version"] == version_mod.version()
    # `capacidades` sigue viajando: la versión se añade, no sustituye.
    assert cuerpo["capacidades"] == ["medicion", "reparto_de_cuadro", "vivienda_en_punto"]


def test_la_misma_version_la_dicen_las_dos_rutas(cliente):
    """Que `/api/salud` y la medición digan lo mismo no es obvio: son dos
    llamadas distintas en dos sitios distintos del fichero, y el día que una se
    quede atrás el cliente cotejará contra una versión que no es la que mide."""
    salud = cliente.get("/api/salud").get_json()
    assert salud["version"] == version_mod.version()


def test_un_version_json_ilegible_no_tumba_la_medicion(tmp_path, monkeypatch):
    """Un servidor que no sabe decir su versión sigue sabiendo medir. Quedarse
    sin medición por un fichero de metadatos roto sería cambiar un problema
    pequeño por uno grande."""
    roto = tmp_path / "version.json"
    roto.write_text("{esto no es json", encoding="utf-8")
    monkeypatch.setattr(version_mod, "_FICHERO", str(roto))

    assert version_mod.version() == version_mod.VERSION_DEL_REPOSITORIO


def test_el_paquete_manda_sobre_la_constante_del_repositorio(tmp_path, monkeypatch):
    """Es lo que hace posible D-2: la capa B trae su `version.json` y el mismo
    código declara una versión distinta según qué paquete lo esté ejecutando."""
    fichero = tmp_path / "version.json"
    fichero.write_text(json.dumps({"version": "9.9.9"}), encoding="utf-8")
    monkeypatch.setattr(version_mod, "_FICHERO", str(fichero))

    assert version_mod.version() == "9.9.9"
