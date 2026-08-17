# -*- coding: utf-8 -*-
"""Traduce el JSON de un pliego ya extraído (`analyzer.pliego_extractor`) al
`params`/`body` que ya acepta `analyzer.ai_generator.generate_project()`.

Alcance deliberadamente mínimo (encargo de Pablo, 2026-08-15): solo esta
traducción + el endpoint que la usa. Nada de entrevistador, nada de informe
de cumplimiento — eso es `docs/prd/2026-08-15-conector-pliego-generador.md`,
más amplio y todavía sin aprobar del todo; esto es su caso de uso 1
("generación directa, sin entrevista"), la alternativa más barata que ese
PRD ya proponía en su §14.

**Reutiliza `app._parse_generar_params()` para los valores por defecto** —
no los reimplementa aquí. `pliego_a_params()` deja SIN RELLENAR cualquier
campo que el pliego no traiga (`UNKNOWN`/`no_encontrado`); es
`_parse_generar_params()`, ya probado y usado por `/api/generar`, quien
decide el valor por defecto — exactamente el "usar el valor por defecto que
ya usaba el generador antes" del encargo, sin duplicar esa lógica.

**Dos huecos reales que la traducción campo-a-campo no puede resolver sola**
(documentados, no escondidos):

1. `edificabilidad_maxima_m2` del pliego es una cota ABSOLUTA en m² techo;
   `normativa.edificabilidad_maxima` del generador es un RATIO m²techo/
   m²suelo (`evaluator.evaluate_buildability`) — mismo hallazgo de unidades
   ya hecho para `pliego_verificador.py`. Sin la superficie del solar no
   hay forma de convertir uno en otro; por eso `pliego_a_params()` acepta
   `superficie_solar_m2` opcional — sin él, este campo se deja SIN mapear
   (nunca se inyecta un número con las unidades equivocadas).
2. `mix_tipologias` da PORCENTAJES; `mix_viviendas.dorm_1/2/3` que pide el
   generador son CONTEOS absolutos. Se convierten aquí con software puro
   (redondeo simple sobre `num_viviendas_minimo`) — no es una traducción
   1:1 literal, es la única forma de que el resultado sea un dict que el
   generador acepte de verdad (criterio de aceptación del encargo, punto 4).
"""
from __future__ import annotations

import re
from typing import Any, List, Optional

_RE_NUM_DORMITORIOS = re.compile(r"(\d+)")

#: Campos del pliego sin hueco estructural en `params` -- van como texto a
#: la sección "RESTRICCIONES DE CONCURSO" del mensaje al generador (punto 2
#: del encargo), solo si confianza Alta o Media.
_CAMPOS_A_TEXTO = (
    ("regimen_proteccion", "Régimen de protección de la promoción: %s."),
    ("pem_maximo_euros", "Presupuesto de ejecución material máximo: %s €."),
    ("ratio_construido_util_max", "Ratio máximo superficie construida/superficie útil: %s."),
    ("parking_plazas_por_vivienda", "Plazas de aparcamiento mínimas por vivienda: %s."),
    ("trasteros", "Trasteros exigidos: %s."),
    ("porcentaje_accesibilidad", "Porcentaje mínimo de viviendas accesibles: %s%%."),
)


def _numero_dormitorios(texto: str) -> Optional[int]:
    """«2 Dormitorios» -> 2. Duplica la misma heurística de
    `pliego_verificador._numero_dormitorios_de_texto` -- mantenida aparte a
    propósito, mismo criterio de independencia entre módulos que el resto
    del paquete (p. ej. `extraccion/interprete.py` construye sus propios
    enums en vez de importarlos de otro sitio con otro propósito)."""
    m = _RE_NUM_DORMITORIOS.search(texto or "")
    return int(m.group(1)) if m else None


def _campo(pliego_json: dict, nombre: str) -> dict:
    campo = pliego_json.get(nombre)
    return campo if isinstance(campo, dict) else {"no_encontrado": True, "valor": None}


def _valor(pliego_json: dict, nombre: str) -> Any:
    campo = _campo(pliego_json, nombre)
    return None if campo.get("no_encontrado") else campo.get("valor")


def _confianza_util(pliego_json: dict, nombre: str) -> bool:
    campo = _campo(pliego_json, nombre)
    return not campo.get("no_encontrado") and campo.get("confianza") in ("Alta", "Media")


def _mix_a_conteos(mix_filas: List[dict], num_viviendas: int) -> dict:
    """Porcentajes -> conteos absolutos, redondeo simple. Software puro, sin
    IA -- filosofía ya fijada por Pablo el 2026-08-01. Filas con un `tipo`
    que no menciona 1/2/3 dormitorios, o sin `porcentaje`, se ignoran (no
    hacen que la función falle, solo no aportan a la cuenta)."""
    conteos = {1: 0, 2: 0, 3: 0}
    for fila in mix_filas:
        n = _numero_dormitorios(str(fila.get("tipo") or ""))
        pct = fila.get("porcentaje")
        if n in conteos and pct is not None:
            conteos[n] += round(pct / 100.0 * num_viviendas)
    return conteos


def pliego_a_params(pliego_json: dict, superficie_solar_m2: Optional[float] = None) -> dict:
    """`pliego_json` es `obtener_pliego(id)["parametros"]` (dict de
    `hechos.hecho_a_dict(...)`). Devuelve un dict con la misma forma que el
    `body` que ya acepta `app._parse_generar_params()` — pásalo por esa
    función para obtener el `params` final con los valores por defecto de
    siempre ya aplicados a lo que el pliego no traiga.

    `superficie_solar_m2` es opcional: el pliego nunca la trae, así que sin
    ella `normativa.edificabilidad_maxima` se deja sin mapear (ver hueco 1
    del docstring del módulo) en vez de inyectar un número con las unidades
    equivocadas."""
    body: dict = {"proyecto": {}, "solar": {}, "edificio": {}, "mix_viviendas": {}, "normativa": {}}

    municipio = _valor(pliego_json, "municipio")
    if municipio:
        body["proyecto"]["ciudad"] = municipio

    tipologia = _valor(pliego_json, "tipologia_edificio")
    if tipologia:
        body["proyecto"]["tipologia"] = tipologia

    altura_plantas = _valor(pliego_json, "altura_maxima_plantas")
    if altura_plantas:
        body["normativa"]["plantas_maximas"] = altura_plantas
        # El pliego trata la altura como la que hay que construir, no solo
        # un tope que se puede quedar corto -- si nada más dice lo
        # contrario, se generan exactamente esas plantas.
        body["edificio"]["plantas"] = altura_plantas

    edificabilidad_m2 = _valor(pliego_json, "edificabilidad_maxima_m2")
    if edificabilidad_m2 and superficie_solar_m2:
        body["normativa"]["edificabilidad_maxima"] = round(edificabilidad_m2 / superficie_solar_m2, 4)

    num_min = _valor(pliego_json, "num_viviendas_minimo")
    mix_filas = _valor(pliego_json, "mix_tipologias") or []
    if mix_filas and num_min:
        conteos = _mix_a_conteos(mix_filas, num_min)
        if sum(conteos.values()) > 0:
            body["mix_viviendas"]["dorm_1"] = conteos[1]
            body["mix_viviendas"]["dorm_2"] = conteos[2]
            body["mix_viviendas"]["dorm_3"] = conteos[3]
        sup_mins = [f.get("sup_util_min") for f in mix_filas if f.get("sup_util_min") is not None]
        if sup_mins:
            body["mix_viviendas"]["superficie_minima_m2"] = min(sup_mins)

    restricciones: List[str] = []
    for nombre, plantilla in _CAMPOS_A_TEXTO:
        if _confianza_util(pliego_json, nombre):
            restricciones.append(plantilla % _valor(pliego_json, nombre))
    if mix_filas and _confianza_util(pliego_json, "mix_tipologias"):
        for fila in mix_filas:
            detalle = "%s: %s%%" % (fila.get("tipo"), fila.get("porcentaje"))
            if fila.get("sup_util_min") is not None or fila.get("sup_util_max") is not None:
                detalle += " (superficie útil %s-%s m²)" % (fila.get("sup_util_min"), fila.get("sup_util_max"))
            restricciones.append("Mix de tipologías del pliego — " + detalle)

    body["restricciones_concurso"] = restricciones
    return body
