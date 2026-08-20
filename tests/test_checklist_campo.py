# -*- coding: utf-8 -*-
"""`analyzer/checklist_campo.py` -- cero cobertura hasta hoy (2026-08-20).

Ejecutar:  pytest tests/test_checklist_campo.py

Encontrado sin querer al auditar los consumidores de `analyzer/sitio.py`
para el PRD de procedencia de parcela (`docs/prd/2026-08-20-procedencia-y-
fecha-de-datos-de-parcela.md`): ni `generar_checklist_campo` ni el endpoint
que lo expone (`/api/proyectos/<id>/checklist-campo`) tenían ningún test,
directo ni indirecto. Se añade aquí, no en el propio PRD -- es la red de
seguridad que el criterio de aceptación §8.4 exige antes de tocar el `dict`
que esta función consume.

Función pura, sin I/O (ver cabecera del propio módulo): un dict de entrada,
una lista de 4 bloques de salida, sin llamar a nada. Perfecta para testear
sin mocks."""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from analyzer.checklist_campo import generar_checklist_campo  # noqa: E402

IDS_DE_BLOQUE = (
    "topografia_suelo", "suministros_servidumbres", "bioclimatica_entorno", "potencial_valor_cultural",
)


def _items_planos(bloques):
    return [item for bloque in bloques for item in bloque["items"]]


def test_nunca_lanza_y_siempre_devuelve_los_cuatro_bloques_con_dict_vacio():
    bloques = generar_checklist_campo({})
    assert [b["id"] for b in bloques] == list(IDS_DE_BLOQUE)
    # Ningún ítem inventa una nota sin dato real detrás.
    assert all(item["nota"] is None for item in _items_planos(bloques))


def test_none_como_datos_parcela_se_trata_igual_que_un_dict_vacio():
    """`app.py` puede pasar `None` cuando el proyecto no tiene ningún sitio
    real enlazado todavía (ver docstring de la función) -- no debe lanzar."""
    bloques = generar_checklist_campo(None)
    assert [b["id"] for b in bloques] == list(IDS_DE_BLOQUE)


def test_referencia_catastral_alimenta_su_propio_item_de_confirmacion():
    bloques = generar_checklist_campo({"referencia_catastral": "1446401VK4714E"})
    items = {i["id"]: i for b in bloques for i in b["items"]}
    assert items["referencia_catastral_confirmar"]["nota"] == "Referencia catastral registrada: 1446401VK4714E."
    # Ningún otro ítem se contagia de un dato que no le corresponde.
    otros = [i for i_id, i in items.items() if i_id != "referencia_catastral_confirmar"]
    assert all(item["nota"] is None for item in otros)


def test_superficie_catastro_produce_la_nota_de_linderos():
    bloques = generar_checklist_campo({"superficie_m2": 412.5})
    item = next(i for b in bloques for i in b["items"] if i["id"] == "limites_fisicos_catastro")
    assert item["nota"] == "Superficie según Catastro: 412 m² — confirma que coincide con la medición en campo."


def test_colindantes_alimenta_servidumbres_y_alturas_dos_notas_distintas():
    datos = {"colindantes": [{"nombre": "Edificio A", "altura_plantas": 4}, {"nombre": "Edificio B"}]}
    bloques = generar_checklist_campo(datos)
    items = {i["id"]: i for b in bloques for i in b["items"]}
    assert items["servidumbres_paso"]["nota"] == "2 edificio(s) colindante(s) registrado(s) en Overpass (radio 80 m)."
    # Solo un colindante trae altura conocida -- la nota lo dice, no inventa la del segundo.
    assert items["sombras_colindantes"]["nota"] == (
        "Alturas conocidas de colindantes (plantas): 4 — el resto no tiene dato de altura en OSM."
    )


def test_viales_alimenta_dos_items_de_bloques_distintos_con_el_mismo_dato():
    datos = {"viales": [{"nombre": "Calle Mayor"}, {"nombre": "Calle Menor"}]}
    bloques = generar_checklist_campo(datos)
    items = {i["id"]: i for b in bloques for i in b["items"]}
    assert items["acceso_maquinaria"]["nota"] == items["impacto_acustico"]["nota"]
    assert "Calle Mayor" in items["acceso_maquinaria"]["nota"]


def test_lista_larga_se_recorta_con_el_recuento_del_resto():
    datos = {"viales": [{"nombre": n} for n in ("A", "B", "C", "D", "E")]}
    bloques = generar_checklist_campo(datos)
    item = next(i for b in bloques for i in b["items"] if i["id"] == "acceso_maquinaria")
    assert item["nota"].endswith("A, B, C y 2 más.")


if __name__ == "__main__":  # pragma: no cover
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
