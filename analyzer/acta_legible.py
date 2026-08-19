# -*- coding: utf-8 -*-
"""Traduce un `agente.acta.Acta` en una página que un arquitecto pueda leer.

**`DOC-1`, sesión del 2026-08-19 (noche). Alcance de ESTA sesión, no del hito
completo.** El objetivo de hoy es una vista que muestre el acta con cada
limitación acompañada de su porqué en un desplegable — no el criterio de
aceptación final de `DOC-1` (que exige la voz del arquitecto veterano dando el
visto bueno al lenguaje, con cabeza fresca, no esta noche). Ver
`docs/AGENTE_BACKLOG.md` §10 y `PROGRESS.md`.

**Lo que este módulo NO hace, a propósito:** no vuelve a calcular nada. Todo
número que aparece viene ya calculado en el `dict` de `Acta.a_dict()` — este
fichero sólo decide cómo se presenta y, para las limitaciones de las que
ArchMuse tiene un caso real probado, añade la explicación en lenguaje llano.
Para las que no, lo dice: **pendiente**, con un TODO visible en la propia
página, no con una frase genérica de relleno. Inventar un «porqué» para una
limitación que nunca se ha visto disparar sería exactamente lo que el acta
existe para evitar: una afirmación sin procedencia.

**Los dos casos reales que hay hoy, y una corrección sobre uno de ellos.**
`superficies.medicion_de_planta`, ejecutada contra el DXF real del cliente
(`v2s.dxf`, fuera del repositorio — ver `ARCHMUSE_DXF_V2S`), produce una única
línea de "no comprobado" que es en realidad los DOS casos que se pidieron
tratar por separado:

    «VT1/3» no lleva superficie útil total: hay 7,08 m² dibujados dos veces:
    la suma de las piezas da 74,95 m² y la superficie que ocupan realmente es
    67,87 m²

Es el mismo defecto —dos piezas contadas dos veces— visto por el motor de
medición (aquí: "no hay total") y por el de coherencia
(`tests/test_solape_coincide_entre_motores.py`: "hay un solape de 7,08 m²").
**No es un caso distinto en `V5.dxf`**: ejecutado hoy contra el `V5.dxf` real,
`superficies.medicion_de_planta` da total en las tres viviendas y cero
impedimentos — el «sin total por impedimento» de `V5.dxf` no existe todavía
como caso probado. La explicación de abajo cubre el caso real tal como es: una
sola línea que dice las dos cosas.

**Por qué la página y el test usan un DXF sintético, no `v2s.dxf`.** El
repositorio es público y la auditoría de publicación del 2026-08-19 fue
explícita: ni un DXF de cliente real, ni las superficies de un proyecto real.
El sintético reutiliza `SOLAPE`/`SOLAPE_ETIQUETAS`, ya en
`tests/test_medicion_de_planta.py` desde antes de esta sesión — mismo patrón
de defecto, cifras redondas y de mentira (2,00 m², no 7,08 m²). Ver
`scripts/generar_acta_legible_demo.py`.
"""
from __future__ import annotations

import html
import os
import re
from dataclasses import dataclass
from typing import Optional

#: TODO(DOC-1): en cuanto aparezca un caso real probado de una limitación
#: distinta —normativa fuera de corpus, ordenanza sin validar, lo que sea—,
#: su explicación se añade aquí con el mismo formato. No antes: sin caso real,
#: no hay porqué que escribir sin inventarlo.


@dataclass(frozen=True)
class Explicacion:
    """El porqué en lenguaje llano y la cifra que lo sostiene, extraída del
    propio texto del acta — nunca recalculada."""

    porque: str
    cifra: str


_PATRON_SIN_TOTAL = re.compile(r"«([^»]+)» no lleva superficie útil total: (.+)")
_PATRON_CIFRA_M2 = re.compile(r"(\d+[.,]\d+)\s*m²")


def _explicacion_vivienda_sin_total(vivienda: str, motivo: str) -> Optional[Explicacion]:
    cifra_match = _PATRON_CIFRA_M2.search(motivo)
    if not cifra_match:
        # Sin cifra en el propio motivo no hay nada que mostrar como «cifra»
        # sin inventarla: se trata como pendiente, no como caso conocido a
        # medias.
        return None
    cifra = "%s m²" % cifra_match.group(1)
    porque = (
        "La vivienda «%s» no lleva un número de superficie útil total, y no es una "
        "casilla vacía por descuido. ArchMuse ha medido cada pieza de esta vivienda "
        "una a una —esas cifras están arriba, en «Qué se ha establecido»— y al sumarlas "
        "el resultado no coincide con la superficie que esas piezas ocupan realmente "
        "sobre el plano: %s Esos %s de diferencia son metros que dos recintos se "
        "disputan sobre el mismo suelo, así que sumarlos tal cual los contaría dos "
        "veces. ArchMuse podría dar un total igualmente y dejarlo con un asterisco, "
        "pero un total que puede estar mal es el que se copia a la memoria del "
        "proyecto y acaba firmado; la ausencia de total, en cambio, se pregunta. Por "
        "eso esta vivienda no tiene número aquí, aunque cada una de sus piezas sí lo "
        "tenga." % (vivienda, motivo, cifra)
    )
    return Explicacion(porque=porque, cifra=cifra)


def _vivienda_en_datos(nombre_vivienda: str, datos) -> Optional[dict]:
    """Busca `nombre_vivienda` dentro de `medicion.viviendas` en los datos
    del acta y devuelve su dict tal cual lo produjo el motor de medición
    (piezas, solapes...). `None` si el acta no trae ese dato o esa vivienda
    -- nunca se inventa una entidad a partir de sólo el texto del motivo."""
    for d in datos or ():
        if d.get("nombre") != "medicion.viviendas":
            continue
        for v in d.get("valor") or ():
            if v.get("vivienda") == nombre_vivienda:
                return v
    return None


def _capa_de_pieza(vivienda: dict, rotulo: str) -> Optional[str]:
    for p in vivienda.get("piezas") or ():
        if p.get("rotulo") == rotulo:
            return p.get("capa")
    return None


def _entidades_del_solape(vivienda: dict) -> Optional[list]:
    """Las piezas concretas del DXF -- rótulo y capa, tal cual vienen del
    motor de medición -- responsables de que esta vivienda se quede sin
    total: las dos partes de cada solape registrado. `None` si el propio
    acta no trae ningún `solape` que señalar (no se inventa una entidad que
    el motor no ha dado); DXF no tiene un identificador tipo GUID, así que
    rótulo + capa es la referencia más concreta que hay."""
    solapes = vivienda.get("solapes") or ()
    if not solapes:
        return None
    vistos: list = []
    lineas: list = []
    for s in solapes:
        for rotulo in (s.get("una"), s.get("otra")):
            if not rotulo or rotulo in vistos:
                continue
            vistos.append(rotulo)
            capa = _capa_de_pieza(vivienda, rotulo)
            lineas.append("Pieza: %s · Capa: %s" % (rotulo, capa or "sin capa registrada"))
    return lineas or None


def clasificar(texto: str, datos=()) -> dict:
    """Una limitación del acta -> qué mostrar debajo de su desplegable.

    Devuelve siempre `tipo`: `"caso_conocido"` (con `porque` y `cifra`, los
    dos no vacíos, y `entidades` -- lista de líneas "Pieza: ... · Capa: ..."
    o `None` si el acta no trae con qué señalarlas) o `"pendiente"`
    (`porque`/`cifra`/`entidades` los tres `None`: sin caso real, tampoco hay
    entidad que señalar).

    `datos` es la sección "Qué se ha establecido" del propio acta
    (`Acta.a_dict()["datos"]`) -- de ahí, y sólo de ahí, sale la entidad del
    DXF. Se puede omitir (por compatibilidad con quien sólo quiera
    porqué/cifra), y entonces `entidades` sale siempre `None`.
    """
    coincide = _PATRON_SIN_TOTAL.match(texto)
    if coincide:
        nombre_vivienda = coincide.group(1)
        explicacion = _explicacion_vivienda_sin_total(nombre_vivienda, coincide.group(2))
        if explicacion:
            vivienda = _vivienda_en_datos(nombre_vivienda, datos)
            entidades = _entidades_del_solape(vivienda) if vivienda else None
            return {"tipo": "caso_conocido", "porque": explicacion.porque,
                    "cifra": explicacion.cifra, "entidades": entidades}
    return {"tipo": "pendiente", "porque": None, "cifra": None, "entidades": None}


# --- «Qué se ha establecido» en español llano ---------------------------------
#
# **El bug que corrige este bloque** (encontrado por Pablo mirando la página,
# no en un test): antes de esto, `_seccion_datos` mostraba `str(valor)` sin
# más para cualquier dato que no fuera texto/número. Para `medicion.viviendas`
# y `medicion.sin_total` —cuyo valor es una lista de dicts— eso imprimía la
# sintaxis cruda de Python (`[{'exterior_m2': 9.0, ...}]`). Para
# `medicion.informe` —cuyo valor es la ruta absoluta del PDF temporal—
# imprimía la ruta del sistema operativo tal cual, con la cuenta de usuario
# incluida (`C:\\Users\\...\\Temp\\...`). Ninguna de las dos cosas es
# aceptable en una vista para un arquitecto.


def _m2_texto(valor) -> str:
    """Una magnitud en m² con coma decimal (convención española) -- un guion
    si no hay valor. `None` es "sin dato", nunca se convierte en cero."""
    if valor is None:
        return "—"
    return ("%.2f m²" % float(valor)).replace(".", ",")


#: Cualquier string que EMPIECE como una ruta absoluta (unidad de Windows o
#: raíz de Unix). Es la red de seguridad genérica: cubre cualquier dato
#: futuro sin traductor propio en `_FORMATEADORES_DE_DATO`, no sólo
#: `medicion.informe`.
_PATRON_RUTA_ABSOLUTA = re.compile(r"^[A-Za-z]:[\\/]|^/")


def _dato_medicion_viviendas(valor) -> str:
    viviendas = valor or []
    if not viviendas:
        return "No se ha medido ninguna vivienda en este plano."
    frases = []
    for v in viviendas:
        piezas = v.get("piezas") or []
        total = v.get("total_util_m2")
        resumen_total = (
            "total útil %s" % _m2_texto(total) if total is not None
            else "sin total útil (el motivo está más abajo, en «Qué no se ha comprobado»)"
        )
        frases.append(
            "«%s»: %d pieza(s) medidas, %s interior y %s exterior, %s."
            % (v.get("vivienda", "?"), len(piezas), _m2_texto(v.get("interior_m2")),
               _m2_texto(v.get("exterior_m2")), resumen_total)
        )
    return " ".join(frases)


def _dato_medicion_piezas(valor) -> str:
    return "%s pieza(s) identificadas en el plano." % valor


def _dato_medicion_viviendas_con_total(valor) -> str:
    return "%s vivienda(s) con un total de superficie útil sin impedimentos." % valor


def _dato_medicion_sin_total(valor) -> str:
    viviendas = valor or []
    if not viviendas:
        return "Ninguna vivienda se ha quedado sin total."
    nombres = ", ".join("«%s»" % v.get("vivienda", "?") for v in viviendas)
    return "%d vivienda(s) sin total: %s." % (len(viviendas), nombres)


def _dato_medicion_informe(valor) -> str:
    # Sólo el nombre de fichero -- nunca la ruta completa, que revelaría la
    # cuenta de usuario y la estructura de directorios de quien ejecutó la
    # medición.
    base = os.path.basename(str(valor)) if valor else None
    return "Informe de medición generado en PDF (%s)." % base if base else "Informe de medición generado en PDF."


_FORMATEADORES_DE_DATO = {
    "medicion.viviendas": _dato_medicion_viviendas,
    "medicion.piezas": _dato_medicion_piezas,
    "medicion.viviendas_con_total": _dato_medicion_viviendas_con_total,
    "medicion.sin_total": _dato_medicion_sin_total,
    "medicion.informe": _dato_medicion_informe,
}


def _formatear_dato(nombre: str, valor) -> str:
    """El valor de un dato establecido -> una frase en español llano.

    Con `nombre` reconocido, hay una frase específica arriba. Sin él (dato
    futuro todavía sin traductor propio), cae aquí -- y aquí NUNCA se
    imprime un dict/list de Python en crudo ni una ruta absoluta, aunque no
    haya frase específica para ese dato todavía."""
    formateador = _FORMATEADORES_DE_DATO.get(nombre)
    if formateador is not None:
        return formateador(valor)
    if isinstance(valor, str) and _PATRON_RUTA_ABSOLUTA.match(valor):
        return os.path.basename(valor)
    if isinstance(valor, (list, tuple)):
        return "%d elemento(s) (sin traducción específica todavía para «%s»)." % (len(valor), nombre)
    if isinstance(valor, dict):
        return "dato estructurado (sin traducción específica todavía para «%s»)." % nombre
    return str(valor)


# --- El HTML -----------------------------------------------------------------

_ESTILO = """
:root {
  --fondo: #14161a; --panel: #1c1f26; --panel-alto: #22262f;
  --borde: #2e333d; --texto: #e6e8ec; --tenue: #9aa2b1;
  --acento: #d97757; --aviso: #d6a635; --ok: #4ea172;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 32px 20px 60px; font: 14px/1.6 -apple-system, "Segoe UI", Roboto, sans-serif;
  background: var(--fondo); color: var(--texto);
}
main { max-width: 760px; margin: 0 auto; }
h1 { font-size: 19px; margin: 0 0 4px; }
.meta { font-size: 12.5px; color: var(--tenue); margin-bottom: 16px; }
.leyenda {
  font-size: 12px; color: var(--aviso); border: 1px solid var(--aviso);
  border-radius: 6px; padding: 8px 12px; margin-bottom: 26px; background: rgba(214,166,53,.08);
}
h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .8px; color: var(--tenue);
     margin: 30px 0 10px; font-weight: 600; border-bottom: 1px solid var(--borde); padding-bottom: 6px; }
.dato { background: var(--panel); border: 1px solid var(--borde); border-radius: 7px;
        padding: 10px 13px; margin-bottom: 8px; font-size: 13px; }
.etiqueta { display: inline-block; font-family: var(--mono); font-size: 10px; font-weight: 600;
            letter-spacing: .4px; text-transform: uppercase; border-radius: 4px;
            padding: 1px 6px; margin-right: 8px; vertical-align: middle; }
.etiqueta-comprobado { color: var(--ok); border: 1px solid var(--ok); background: rgba(78,161,114,.12); }
.etiqueta-todo { color: var(--aviso); border: 1px solid var(--aviso); background: rgba(214,166,53,.10); }
details.limitacion {
  background: var(--panel); border: 1px solid var(--borde); border-radius: 7px;
  margin-bottom: 8px; padding: 10px 13px;
}
details.limitacion[open] { border-color: var(--acento); }
details.limitacion summary { cursor: pointer; font-size: 13px; list-style: none; }
details.limitacion summary::-webkit-details-marker { display: none; }
details.limitacion summary::before { content: "▸ "; color: var(--tenue); }
details.limitacion[open] summary::before { content: "▾ "; color: var(--acento); }
.porque { margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--borde); font-size: 13px; }
.cifra { display: inline-block; font-family: var(--mono); font-size: 12px; color: var(--acento);
         background: var(--panel-alto); border-radius: 4px; padding: 1px 7px; margin-top: 8px; }
.pendiente { margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--borde);
             font-size: 12.5px; color: var(--tenue); }
.entidad { margin-top: 8px; font-family: var(--mono); font-size: 11.5px; color: var(--texto); }
.entidad-vacia { font-family: inherit; font-style: italic; color: var(--tenue); }
.todo { font-family: var(--mono); font-size: 10.5px; color: var(--aviso);
        border: 1px solid var(--aviso); border-radius: 4px; padding: 0 5px; margin-right: 6px; }
.sello { margin-top: 34px; font-family: var(--mono); font-size: 11px; color: var(--tenue);
         word-break: break-all; }
"""


def _e(valor) -> str:
    return html.escape("" if valor is None else str(valor), quote=True)


def _seccion_datos(datos) -> str:
    if not datos:
        return "<p class='meta'>(nada establecido en esta ejecución)</p>"
    filas = []
    for d in datos:
        valor = d.get("valor")
        if valor is None:
            motivo = (d.get("motivo") or {}).get("detalle", "sin motivo")
            frase = "No determinado — %s" % motivo
        else:
            frase = _formatear_dato(d.get("nombre") or "", valor)
        filas.append("<div class='dato'>%s</div>" % _e(frase))
    return "\n".join(filas)


def _bloque_entidad(entidades: Optional[list], *, hay_caso_real: bool) -> str:
    """El último eslabón de la trazabilidad: la pieza y capa concretas del
    DXF, o -- si no hay -- por qué no las hay, nunca en silencio."""
    if entidades:
        lineas = "<br>".join(_e(linea) for linea in entidades)
        return "<div class='entidad'>%s</div>" % lineas
    if hay_caso_real:
        motivo = "el acta de esta ejecución no trae los solapes con los que señalarlas"
    else:
        motivo = "no hay un caso real todavía del que señalar una entidad concreta"
    return "<div class='entidad entidad-vacia'>Pieza del DXF: %s.</div>" % _e(motivo)


def _seccion_limitaciones(no_comprobado, datos=()) -> str:
    if not no_comprobado:
        return "<p class='meta'>(nada que declarar)</p>"
    bloques = []
    for texto in no_comprobado:
        ficha = clasificar(texto, datos)
        if ficha["tipo"] == "caso_conocido":
            # Etiqueta visible en el `<summary>`, no sólo dentro del
            # desplegable: tiene que distinguirse de un caso pendiente sin
            # necesidad de abrirlo -- "de un vistazo".
            etiqueta = "<span class='etiqueta etiqueta-comprobado'>Caso comprobado</span>"
            cuerpo = (
                "<div class='porque'>%s</div>"
                "<div class='cifra'>%s</div>"
                "%s"
                % (_e(ficha["porque"]), _e(ficha["cifra"]),
                   _bloque_entidad(ficha["entidades"], hay_caso_real=True))
            )
        else:
            etiqueta = "<span class='etiqueta etiqueta-todo'>TODO · sin caso real</span>"
            cuerpo = (
                "<div class='pendiente'><span class='todo'>TODO</span>"
                "Todavía no hay un caso real probado de esta limitación con el que "
                "escribir su explicación en lenguaje llano sin inventarla. Se "
                "muestra el texto técnico del acta tal cual, sin traducir.</div>"
                "%s" % _bloque_entidad(None, hay_caso_real=False)
            )
        bloques.append(
            "<details class='limitacion'><summary>%s%s</summary>%s</details>"
            % (etiqueta, _e(texto), cuerpo)
        )
    return "\n".join(bloques)


def render(acta: dict) -> str:
    """El `dict` de `Acta.a_dict()` -> una página HTML autocontenida.

    Una sola vista, sin pestañas: el acta cabe en un scroll. Cada limitación es
    un `<details>` — cerrado por defecto, para que la vista general no se
    convierta en un muro de texto, y con el porqué a un clic, que es
    literalmente lo que pide C2 del documento de alineación estratégica.
    """
    titulo = _e(acta.get("objetivo") or "Acta de procedencia")
    meta = "Proyecto %s · ejecución %s · %s" % (
        _e(acta.get("proyecto_id")), _e(acta.get("ejecucion_id")), _e(acta.get("emitida_en")))
    leyenda = _e(acta.get("leyenda") or "")
    sello = _e(acta.get("sello") or "(sin sellar)")
    datos = acta.get("datos") or ()

    return """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>%s — acta de procedencia</title>
<style>%s</style></head><body><main>
<h1>%s</h1>
<div class="meta">%s</div>
<div class="leyenda">%s</div>

<h2>Qué se ha establecido</h2>
%s

<h2>Qué no se ha comprobado</h2>
%s

<div class="sello">Sello: %s</div>
</main></body></html>""" % (
        titulo, _ESTILO, titulo, meta, leyenda,
        _seccion_datos(datos),
        _seccion_limitaciones(acta.get("no_comprobado") or (), datos),
        sello,
    )
