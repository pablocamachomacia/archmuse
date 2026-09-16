# -*- coding: utf-8 -*-
"""Una pieza cuyo reparto entre viviendas no es firme no escribe su cifra en la tabla.

**Medido el 2026-09-16** comparando todas las viviendas del plano maestro con el
cuadro del arquitecto (fuera del repositorio): en cuatro parejas de viviendas
vecinas, el reparto por cercanía al rótulo `VT…` mete un dormitorio o un aseo de
una en la tabla de la otra. Los totales ya salían vacíos (`C-2`), pero la fila
se escribía **con la cifra de una pieza de otra vivienda**, y a la vivienda de
verdad le faltaba esa fila.

Decisión propuesta, pendiente de firma, por la regla de Pablo del mismo día
(«con duda, celda vacía con motivo»): la fila de una pieza con reparto dudoso se
enseña **sin cifra**, y la nota dice entre qué viviendas duda.

Plano sintético, con coordenadas escritas a mano.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from analyzer import parser  # noqa: E402
from analyzer import plantilla_cuadro as pc  # noqa: E402
from tests.test_medicion_de_planta import construir  # noqa: E402

PIEZAS = (
    ("Salón/cocina", (0.0, 1.0), (5.0, 5.0)),     # 20
    ("Dormitorio 1", (0.0, 6.0), (4.0, 9.0)),     # 12
    ("Baño", (0.0, 10.0), (2.0, 12.0)),           # 4
    ("Terraza", (6.0, 1.0), (8.0, 3.0)),          # 4, firme: junto a VT1/1
    # Justo en medio de las dos viviendas: se asigna a la primera por un metro.
    ("Terraza", (28.0, 0.0), (31.0, 3.0)),        # 9, dudosa
)
ETIQUETAS = (("VT1/1", 0.0, 0.0), ("VT2/1", 60.0, 0.0))


def _plantilla(tmp_path):
    ruta = construir(tmp_path, PIEZAS, ETIQUETAS)
    doc = parser.load_document(ruta)
    return pc.construir(doc, parser.leer_plano(doc), "VT1/1")


def test_la_pieza_dudosa_se_ensena_sin_cifra_y_con_motivo(tmp_path):
    p = _plantilla(tmp_path)
    terrazas = [f for f in p.exteriores if f.rotulo == "Terraza"]
    assert sorted(f.valor for f in terrazas) == ["", "4,00 m²"], terrazas
    nota = " ".join(n for n in p.notas if n.startswith("Terraza"))
    assert "VT2/1" in nota, p.notas
    assert "9,00" not in " ".join(t for _f, _c, t in p.celdas())


def test_las_piezas_firmes_siguen_con_su_cifra(tmp_path):
    p = _plantilla(tmp_path)
    valores = {f.rotulo: f.valor for f in p.interiores}
    assert valores == {"Salón/cocina": "20,00 m²", "Dormitorio 1": "12,00 m²", "Baño": "4,00 m²"}


def test_y_los_totales_siguen_vacios(tmp_path):
    p = _plantilla(tmp_path)
    assert p.cierre[0][1] == "" and p.cierre[0][3] == "" and p.cierre[1][1] == ""
