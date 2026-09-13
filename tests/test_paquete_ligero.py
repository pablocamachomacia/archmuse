# -*- coding: utf-8 -*-
"""El servidor tiene que arrancar sin las dependencias que el camino del comando
no usa. T2 del PRD de la beta.

**Por qué esto es un test y no una nota.** El instalador de la beta va a viajar
por WhatsApp al ordenador del primer usuario de la beta, y `ifcopenshell` son **94,5 MB** de
los 303,7 que ocupa `site-packages` — para una función, la exportación a IFC, que
esa beta ni siquiera ofrece. Sacarlo del paquete sólo es posible mientras nadie
vuelva a poner `import ifcopenshell` en la cabecera de un módulo que `app.py`
importe; y eso pasa sin querer, en un `import` añadido por costumbre, y no se
nota hasta que alguien instala en una máquina limpia — que es exactamente la
prueba que desde aquí no se puede hacer (§12.3 del PRD).

Este fichero convierte ese «no se puede probar desde aquí» en algo que sí se
puede: no comprueba que el paquete sea pequeño, comprueba **que nada obligatorio
depende de lo que se va a dejar fuera**.

Medido el 2026-09-11: quitando estos paquetes (y `pip`/`pytest`, que no se
empaquetan nunca) se pasa de 303,7 MB a **172,4 MB** antes de comprimir.
"""
from __future__ import annotations

import importlib.util
import importlib.abc
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

RAIZ = Path(__file__).parent.parent

#: Lo que el paquete de la beta NO va a llevar, con su peso medido. Si alguna
#: deja de poder quitarse, este fichero lo dice antes que una instalación
#: fallida en casa de otro.
FUERA_DEL_PAQUETE = {
    "ifcopenshell": 94.5,
    "trimesh": 4.0,
    "mapbox_earcut": 0.1,
    "pdfminer": 9.3,
    "pypdf": 3.7,
    "anthropic": 6.2,
}

#: Y lo que SÍ va, porque el camino del comando lo necesita de verdad. Está aquí
#: para que quede escrito por qué: `reportlab` produce el PDF de la medición, y
#: `PIL`/`fontTools` son suyos.
DENTRO_DEL_PAQUETE = ("ezdxf", "shapely", "numpy", "flask", "waitress",
                      "reportlab", "yaml", "jsonschema", "dotenv")


_GUION = textwrap.dedent(
    """
    import importlib.abc, json, sys
    BLOQUEADAS = set(json.loads(sys.argv[1]))
    pedidas = set()

    class Veto(importlib.abc.MetaPathFinder):
        def find_spec(self, nombre, ruta=None, destino=None):
            raiz = nombre.split(".")[0]
            if raiz in BLOQUEADAS:
                pedidas.add(raiz)
                raise ImportError("fuera del paquete de la beta: %s" % nombre)
            return None

    sys.meta_path.insert(0, Veto())
    sys.path.insert(0, sys.argv[2])
    import os
    os.environ["ANTHROPIC_API_KEY"] = ""
    import app
    cliente = app.app.test_client()
    salud = cliente.get("/api/salud")
    cuerpo = {
        "capa": "00 areas",
        "recintos": [{"handle": "1", "capa": "00 areas", "color": 256,
                      "cerrada": True,
                      "vertices": [[0, 0], [5, 0], [5, 4], [0, 4]]}],
        "textos": [{"texto": "Salon", "x": 2.5, "y": 2.0}],
    }
    medicion = cliente.post("/api/medicion-geometria", data=json.dumps(cuerpo),
                            content_type="application/json")
    print(json.dumps({
        "salud": salud.status_code,
        "medicion": medicion.status_code,
        "version": (medicion.get_json() or {}).get("version"),
        "pedidas": sorted(pedidas),
    }))
    """
)


def _arrancar_sin(paquetes):
    """Arranca el servidor en un proceso aparte con esos paquetes vetados.

    En un proceso aparte y no aquí porque `app.py` ya está importado en la
    sesión de pytest: vetar un import sobre un `sys.modules` caliente no prueba
    nada. Es la misma razón por la que esto no se puede hacer con `monkeypatch`.
    """
    completado = subprocess.run(
        [sys.executable, "-c", _GUION, json.dumps(sorted(paquetes)), str(RAIZ)],
        capture_output=True, text=True, cwd=str(RAIZ), timeout=600,
    )
    if completado.returncode != 0:
        pytest.fail(
            "el servidor NO arranca sin %s.\n\n%s"
            % (sorted(paquetes), completado.stderr[-3000:])
        )
    return json.loads(completado.stdout.strip().splitlines()[-1])


def test_el_servidor_arranca_sin_las_dependencias_pesadas():
    """**El test que vale por los seis.** Si esto se pone rojo, alguien ha
    añadido un import en la cabecera de un módulo que `app.py` carga, y el
    instalador de la beta acaba de engordar más de 100 MB sin que nadie lo
    pidiera."""
    resultado = _arrancar_sin(FUERA_DEL_PAQUETE)

    assert resultado["salud"] == 200
    assert resultado["medicion"] == 200
    assert resultado["version"]


@pytest.mark.parametrize("paquete", sorted(FUERA_DEL_PAQUETE))
def test_cada_paquete_pesado_se_puede_quitar_por_separado(paquete):
    """Uno a uno, para que el fallo diga cuál. Con los seis juntos, el mensaje
    sólo dice que algo se rompió."""
    resultado = _arrancar_sin({paquete})
    assert resultado["medicion"] == 200


def test_ifc_export_se_importa_sin_ifcopenshell():
    """El módulo de exportación IFC **se importa** sin el paquete; sólo lo
    necesita quien llame a la función. Es lo que permite que `app.py` lo siga
    importando en su cabecera sin arrastrar 94,5 MB."""
    resultado = _arrancar_sin({"ifcopenshell"})
    assert resultado["medicion"] == 200


def test_quien_exporte_un_ifc_recibe_un_motivo_y_no_un_modulenotfound():
    """Un `ModuleNotFoundError` desnudo en un servidor sin consola no le dice
    nada a nadie. El mensaje tiene que decir qué falta, por qué no estaba, y que
    lo demás sigue funcionando."""
    from analyzer import ifc_export

    fuente = Path(ifc_export.__file__).read_text(encoding="utf-8")
    assert "def _ifcopenshell" in fuente
    assert "93 MB" in fuente or "94" in fuente
    assert "pip install ifcopenshell" in fuente


@pytest.mark.parametrize("paquete", DENTRO_DEL_PAQUETE)
def test_lo_que_si_va_en_el_paquete_esta_instalado(paquete):
    """El reverso: la lista de lo que sí se empaqueta no puede quedarse
    desactualizada en silencio."""
    assert importlib.util.find_spec(paquete) is not None
