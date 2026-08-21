# -*- coding: utf-8 -*-
"""`POST /api/coherencia-datos` -- el contrato de coherencia como JSON.

Ejecutar:  pytest tests/test_coherencia_datos_endpoint.py

PRD: `docs/prd/2026-08-21-ubicacion-hallazgos-visor2d.md`, addendum Fase 2
("Prompt 2"). No añade ningún endpoint de negocio nuevo: reexpone como JSON
el mismo acta que `/api/preguntar` ya devuelve como HTML para
`revision.coherencia_del_plano` -- ver `app.py:_coherencia_a_json` y
`app.py:coherencia_datos_endpoint`.

Lo que este fichero fija, uno por criterio de aceptación del addendum:
1. La forma exacta del JSON, con un hallazgo con `ubicacion` y otro con
   `ubicacion: null` en la misma respuesta.
2. Que el camino HTML de siempre no ha cambiado ni un carácter.
3. Que este endpoint no necesita `ANTHROPIC_API_KEY` ni toca el LLM --
   a diferencia de `/api/preguntar`, no hay ninguna intención que clasificar.
4. Que el mapeo a JSON es una función pura sobre el acta ya calculada: no
   reconstruye nada llamando otra vez a `coherencia.revisar()` por su cuenta.
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

_TMP_DATA = tempfile.mkdtemp(prefix="archmuse_test_coherencia_datos_")
os.environ.setdefault("ARCHMUSE_DATA_DIR", _TMP_DATA)

from analyzer import storage  # noqa: E402
storage.init_db()

import app as app_module  # noqa: E402
from analyzer import parser  # noqa: E402
from scripts.generar_acta_legible_demo import _construir_dxf_sintetico  # noqa: E402

ENDPOINT = "/api/coherencia-datos"


@pytest.fixture(scope="module")
def dxf_con_solape() -> bytes:
    """El mismo sintético que `test_preguntar_coherencia.py`: un solape real
    (Salón/cocina + Dormitorio 1), así que trae un hallazgo CON `ubicacion`."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta = _construir_dxf_sintetico(Path(tmp))
        return Path(ruta).read_bytes()


@pytest.fixture()
def dxf_sin_recintos_validos(tmp_path) -> bytes:
    """`AM_UTIL_INT` con una única polilínea autointersecante: `SIN_RECINTOS`
    (sin `ubicacion` -- no hay nada que encuadrar) + `GEOMETRIA_DESCARTADA`
    (con `ubicacion`, resuelta por `handle` aunque Shapely rechace el
    polígono) EN LA MISMA revisión -- da los dos casos del criterio de
    aceptación nº1 en una sola petición."""
    import ezdxf

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (4, 4), (4, 0), (0, 4)], close=True,
                       dxfattribs={"layer": parser.CAPA_UTIL_INTERIOR})
    ruta = tmp_path / "plano.dxf"
    doc.saveas(str(ruta))
    return ruta.read_bytes()


@pytest.fixture()
def cliente_http():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def _pedir(http, dxf_bytes, *, nombre="plano.dxf", autorizar_efectos=True, escala=None):
    data = {"dxf": (BytesIO(dxf_bytes), nombre)}
    if autorizar_efectos:
        data["autorizar_efectos"] = "1"
    if escala:
        data["escala"] = escala
    return http.post(ENDPOINT, data=data, content_type="multipart/form-data")


# --- 1. La forma del JSON, con y sin ubicación ---------------------------

def test_la_forma_del_json_trae_ubicacion_y_null_en_la_misma_respuesta(
        cliente_http, dxf_sin_recintos_validos):
    resp = _pedir(cliente_http, dxf_sin_recintos_validos, escala="metros")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
    cuerpo = resp.get_json()

    assert set(cuerpo) == {"recintos_geometria", "hallazgos"}
    assert cuerpo["recintos_geometria"] == []
    assert len(cuerpo["hallazgos"]) == 2

    sin_recintos = next(h for h in cuerpo["hallazgos"] if h["tipo"] == "no_se_ha_leido_ningun_recinto")
    assert sin_recintos["ubicacion"] is None
    assert set(sin_recintos) == {"tipo", "descripcion", "ubicacion"}

    descartada = next(h for h in cuerpo["hallazgos"] if h["tipo"] == "geometria_descartada")
    assert descartada["ubicacion"] == {"bbox": [0.0, 0.0, 4.0, 4.0]}


def test_recintos_geometria_con_al_menos_dos_recintos(cliente_http, dxf_con_solape):
    resp = _pedir(cliente_http, dxf_con_solape)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
    cuerpo = resp.get_json()

    assert len(cuerpo["recintos_geometria"]) >= 2
    for r in cuerpo["recintos_geometria"]:
        assert set(r) == {"label", "layer", "puntos"}
        assert len(r["puntos"]) >= 4

    solape = next(h for h in cuerpo["hallazgos"] if h["tipo"] == "solape_entre_recintos")
    assert solape["ubicacion"]["bbox"] == pytest.approx([0.0, 0.0, 7.0, 4.0], abs=0.01)


def test_sin_autorizar_efectos_pide_confirmacion(cliente_http, dxf_con_solape):
    """`SEG-1` sigue vigente: este endpoint escribe el PDF de coherencia de
    camino (misma función que el HTML), así que sigue pidiendo autorización."""
    resp = _pedir(cliente_http, dxf_con_solape, autorizar_efectos=False)
    assert resp.status_code == 428, resp.get_data(as_text=True)[:500]
    cuerpo = resp.get_json()
    assert cuerpo["confirmacion_requerida"] is True
    assert cuerpo["solicitud"]["quien"] == "api:coherencia-datos"


# --- 2. El camino HTML de siempre no cambia -------------------------------

def test_el_camino_html_de_preguntar_sigue_igual(dxf_con_solape):
    """Regresión explícita (criterio de aceptación nº2 del addendum): la
    función que produce el HTML de `/api/preguntar` para esta Skill no se ha
    tocado -- llamada directamente, sigue devolviendo la misma página de
    siempre, no un JSON ni nada envuelto."""
    from werkzeug.datastructures import FileStorage

    pagina = app_module._revisar_coherencia_y_renderizar_acta(
        FileStorage(BytesIO(dxf_con_solape), filename="plano.dxf"), "plano.dxf", None, None,
        quien="test-html-sin-cambios", autorizar_efectos=True)

    assert isinstance(pagina, str)
    assert not pagina.strip().startswith("{")
    assert "acta de procedencia" in pagina
    assert "hallazgo(s):" in pagina


# --- 3. No necesita LLM ni clave de API -----------------------------------

def test_no_hace_falta_clave_de_api(cliente_http, dxf_con_solape, monkeypatch):
    """A diferencia de `/api/preguntar`, aquí no hay ninguna intención que
    clasificar: se sabe de antemano qué capacidad se quiere."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resp = _pedir(cliente_http, dxf_con_solape)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]


# --- 4. El mapeo es puro: no reconstruye nada -----------------------------

def test_coherencia_a_json_es_una_funcion_pura_sobre_el_acta():
    """No necesita Flask, ni un DXF, ni ejecutar la Skill: sólo lee la forma
    que ya produce `Acta.a_dict()` -- exactamente el contrato del PRD (§10):
    'esto es serializar lo que ya sale del acta, no reconstruir nada'."""
    documento = {
        "datos": [
            {"nombre": "revision.recintos_geometria",
             "valor": [{"label": "Salon", "layer": "00 areas", "puntos": [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]}]},
            {"nombre": "revision.hallazgos",
             "valor": [
                 {"tipo": "solape_entre_recintos", "entidad": "a + b", "descripcion": "x",
                  "magnitud": 2.0, "unidad": "m2", "detalle": {}, "ubicacion": {"bbox": [0, 0, 1, 1]}},
                 {"tipo": "no_se_ha_leido_ningun_recinto", "entidad": "capa «X»", "descripcion": "y",
                  "magnitud": None, "unidad": "", "detalle": {}, "ubicacion": None},
             ]},
            {"nombre": "revision.recintos", "valor": 1},
        ],
    }
    salida = app_module._coherencia_a_json(documento)
    assert salida == {
        "recintos_geometria": documento["datos"][0]["valor"],
        "hallazgos": [
            {"tipo": "solape_entre_recintos", "descripcion": "x", "ubicacion": {"bbox": [0, 0, 1, 1]}},
            {"tipo": "no_se_ha_leido_ningun_recinto", "descripcion": "y", "ubicacion": None},
        ],
    }


def test_coherencia_a_json_no_revienta_si_faltan_los_datos():
    """Si el procedimiento se cortó antes de producir estas dos Afirmaciones
    (`agente/skills/coherencia.py:_sin_hacer`), sale lista vacía -- nunca una
    excepción por una clave que no está."""
    assert app_module._coherencia_a_json({"datos": []}) == {
        "recintos_geometria": [], "hallazgos": [],
    }


def test_el_endpoint_delega_una_sola_vez_en_la_misma_funcion_que_el_html(
        cliente_http, monkeypatch):
    """Ambos caminos leen el mismo cálculo: el endpoint JSON llama a
    `_revisar_coherencia_y_levantar_acta` -- la MISMA función de la que
    depende `_revisar_coherencia_y_renderizar_acta` -- exactamente una vez
    por petición, no reimplementa la ejecución de la Skill por su cuenta."""
    documento_falso = {"datos": [
        {"nombre": "revision.recintos_geometria", "valor": []},
        {"nombre": "revision.hallazgos", "valor": []},
    ]}
    llamadas = []

    def _falsa(file, filename, capa, factor_escala, *, quien, autorizar_efectos=False):
        llamadas.append((filename, quien, autorizar_efectos))
        return documento_falso

    monkeypatch.setattr(app_module, "_revisar_coherencia_y_levantar_acta", _falsa)
    resp = cliente_http.post(ENDPOINT, data={
        "dxf": (BytesIO(b"contenido cualquiera"), "plano.dxf"), "autorizar_efectos": "1",
    }, content_type="multipart/form-data")

    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
    assert resp.get_json() == {"recintos_geometria": [], "hallazgos": []}
    assert len(llamadas) == 1
    assert llamadas[0][1] == "api:coherencia-datos"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
