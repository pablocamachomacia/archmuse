# -*- coding: utf-8 -*-
"""Genera la demo de `DOC-1`: un acta real, renderizada como página legible.

    python scripts/generar_acta_legible_demo.py

Ejecuta la Skill real `superficies.medicion_de_planta` — el mismo camino que
`scripts/medir_planta.py`, sin atajos ni lógica duplicada — contra un DXF
**sintético**, no contra el plano real del cliente: el repositorio es público
y la auditoría de publicación del 2026-08-19 excluyó explícitamente cualquier
DXF o superficie de un proyecto real. El sintético reutiliza `SOLAPE` /
`SOLAPE_ETIQUETAS`, ya en `tests/test_medicion_de_planta.py` desde antes de
esta sesión: la misma familia de defecto que el plano real —piezas que se
solapan, así que la vivienda se queda sin total—, con cifras redondas y de
mentira (2,00 m², no los 7,08 m² reales).

Escribe dos ficheros:

1. `tests/fixtures/acta_demo/acta_medicion_sintetica.json` — el
   `Acta.a_dict()` real, tal cual lo produce `agente/acta.py`. Es lo que
   `tests/test_acta_legible.py` carga para comprobar que ninguna limitación
   se muestra muda.
2. `docs/design/2026-08-19-doc1-acta-legible-demo.html` — la página, vía
   `analyzer/acta_legible.render()`. Ábrela en un navegador.

No toca `agente/acta.py` ni `analyzer/medicion.py`: sólo los invoca.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from agente import acta as _acta  # noqa: E402
from agente.efectos import ESCRIBE_FICHERO, Autorizaciones  # noqa: E402
from agente.ejecucion import Ejecutor, Paso, Plan  # noqa: E402
from agente.memoria import MemoriaDeProyecto, SustratoEnMemoria  # noqa: E402
from agente.registro import registro, registro_de_skills  # noqa: E402
from analyzer import acta_legible  # noqa: E402

SKILL = "superficies.medicion_de_planta"

#: La misma vivienda con un solape que ya vive en
#: `tests/test_medicion_de_planta.py` (SOLAPE / SOLAPE_ETIQUETAS): un salón de
#: 20 m² y un dormitorio de 6 m² que pisa 2 m² del salón, más un baño y una
#: terraza sin tocar nada. Cifras de mentira, misma forma de defecto real.
PIEZAS = (
    ("Salón/cocina", (0.0, 0.0), (5.0, 4.0)),      # 20
    ("Dormitorio 1", (4.0, 0.0), (7.0, 2.0)),      # 6, pisa 2 del salón
    ("Baño", (10.0, 0.0), (12.0, 2.0)),            # 4
    ("Terraza", (10.0, 3.0), (13.0, 6.0)),         # 9
)
ETIQUETAS_DE_VIVIENDA = (("VT1/1", 6.0, -3.0),)


def _construir_dxf_sintetico(destino: Path) -> str:
    import ezdxf

    from analyzer import parser

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6  # metros
    doc.layers.add(parser.AREA_LAYER)
    msp = doc.modelspace()
    for etiqueta, (x0, y0), (x1, y1) in PIEZAS:
        msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                           dxfattribs={"layer": parser.AREA_LAYER})
        msp.add_mtext(etiqueta, dxfattribs={"layer": parser.AREA_LAYER}).set_location(
            ((x0 + x1) / 2.0, (y0 + y1) / 2.0))
    for texto, x, y in ETIQUETAS_DE_VIVIENDA:
        msp.add_mtext(texto, dxfattribs={"layer": parser.AREA_LAYER}).set_location((x, y))
    ruta = destino / "planta_sintetica.dxf"
    doc.saveas(str(ruta))
    return str(ruta)


def generar_acta_demo() -> dict:
    """La Skill real, de punta a punta, contra el DXF sintético. Devuelve
    `Acta.a_dict()` — nada recalculado a mano."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ruta_dxf = _construir_dxf_sintetico(tmp_path)
        ruta_pdf = str(tmp_path / "medicion.pdf")

        memoria = MemoriaDeProyecto("proyecto-demo-doc1", SustratoEnMemoria())
        plan = Plan(
            objetivo="Medir una planta con una vivienda que tiene un solape (demo DOC-1)",
            proyecto_id="proyecto-demo-doc1",
            pasos=(Paso(id="medir", skill=SKILL,
                       argumentos={"ruta_dxf": ruta_dxf, "ruta_informe": ruta_pdf}),),
        )
        skills = registro_de_skills(recargar=True)
        autorizaciones = Autorizaciones.de((ESCRIBE_FICHERO,), por="demo-doc1")
        resultado = Ejecutor(capacidades=registro(recargar=True), skills=skills).ejecutar(
            plan, memoria, ejecucion_id="e-demo-doc1", autorizaciones=autorizaciones)

        documento = _acta.levantar(resultado, capacidades=registro(), skills=skills)
        return documento.a_dict()


def main() -> None:
    acta = generar_acta_demo()

    fixtures = RAIZ / "tests" / "fixtures" / "acta_demo"
    fixtures.mkdir(parents=True, exist_ok=True)
    ruta_json = fixtures / "acta_medicion_sintetica.json"
    ruta_json.write_text(json.dumps(acta, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")

    ruta_html = RAIZ / "docs" / "design" / "2026-08-19-doc1-acta-legible-demo.html"
    ruta_html.write_text(acta_legible.render(acta), encoding="utf-8")

    print("Acta JSON:  %s" % ruta_json)
    print("Página:     %s" % ruta_html)


if __name__ == "__main__":
    main()
