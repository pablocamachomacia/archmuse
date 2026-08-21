# -*- coding: utf-8 -*-
"""`plano.entregable_en_pdf`: fusión de manifiesto de las tres capacidades que
escribían un PDF (Prompt 1.7, cierre de C4 — ver
`docs/design/2026-08-21-fusion-capacidades-pdf-C4.md`).

**Fusión de manifiesto, no de código.** Las tres implementaciones —
`medicion.medicion_en_pdf`, `plano.cuadro_en_pdf`, `coherencia.escribir_informe`
— siguen exactamente donde estaban, sin tocar una línea de su lógica ni de
sus guardianes (`_destino_seguro`, `_sha256`, `_con_sello_intacto`, el sha256
antes/después). Esto sólo añade UNA entrada de registro que las despacha
según el parámetro `tipo`. Las tres siguen siendo capacidades Python
llamables directamente — lo que deja de existir es su entrada individual en
el registro de capacidades, no la función.

**Por qué aquí y no en uno de los tres módulos originales.** Poner el
despacho dentro de, por ejemplo, `plano.py` habría creado una dependencia
de `plano.py` hacia `coherencia.py` y `medicion.py` que hoy no existe y que
ninguno de los tres necesita para su propio trabajo — sólo la hace falta el
despacho. Un módulo nuevo, pequeño, que sólo orquesta, evita acoplar los
tres módulos de dominio entre sí por un motivo que es puramente de catálogo
(C4), no de dominio.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..capacidad import Capacidad
from ..efectos import ESCRIBE_FICHERO
from .coherencia import escribir_informe
from .medicion import medicion_en_pdf
from .plano import cuadro_en_pdf

TIPOS = ("medicion", "cuadro", "coherencia")


def entregable_en_pdf(tipo: str, ruta: str, ruta_destino: str,
                      capa: Optional[str] = None,
                      factor_escala: Optional[float] = None,
                      respuestas: Optional[List[dict]] = None) -> Dict[str, Any]:
    """Despacha al escritor de PDF correspondiente. `capa`/`factor_escala` los
    usan «medicion» y «coherencia»; `respuestas` lo usa «cuadro» — el que no
    aplique al `tipo` pedido simplemente se ignora, no es un error pedirlo de
    más (el esquema ya los declara todos como opcionales)."""
    if tipo == "medicion":
        return medicion_en_pdf(ruta, ruta_destino, capa=capa, factor_escala=factor_escala)
    if tipo == "cuadro":
        return cuadro_en_pdf(ruta, ruta_destino, respuestas=respuestas)
    if tipo == "coherencia":
        return escribir_informe(ruta, ruta_destino, capa=capa, factor_escala=factor_escala)
    # El esquema (`enum`) ya rechaza cualquier otro valor antes de invocar
    # esta función — `Capacidad.invocar` valida contra el JSON Schema entero
    # antes de llamar a `funcion`. Esto es sólo la defensa de quien llame a
    # `entregable_en_pdf(...)` directamente, sin pasar por el registro.
    raise ValueError(f"tipo desconocido: {tipo!r}; admitidos {TIPOS}")


CAPACIDADES = (
    Capacidad(
        id="plano.entregable_en_pdf",
        version="1.0.0",
        dominio="plano",
        naturaleza="io",
        descripcion=(
            "Escribe un entregable en PDF legible a partir del DXF del arquitecto, "
            "según «tipo»: «medicion» (la medición de superficie útil de cada "
            "vivienda, pieza a pieza, con subtotales y total cuando lo hay), "
            "«cuadro» (el cuadro de superficies, celda a celda, con el valor de "
            "cada una), o «coherencia» (los hallazgos de coherencia del plano "
            "consigo mismo, con su entidad y su magnitud). En los tres casos cada "
            "dato vuelve con DE DÓNDE SALE —qué recinto, celda o hallazgo, con qué "
            "rótulo y en qué capa del DXF— y con la lista de lo que este trabajo "
            "NO comprueba, derivada de los manifiestos de las capacidades que se "
            "han ejecutado. El DXF de entrada SÓLO SE LEE: se abre en modo lectura "
            "y su sha256 se verifica antes y después de escribir. Sale marcado "
            "como borrador para revisión de un colegiado, SIN OPCIÓN DE QUITAR esa "
            "marca. Exige autorización explícita del efecto «escribe_fichero»: sin "
            "ella no se crea ningún fichero."
        ),
        parametros={
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": list(TIPOS),
                    "description": (
                        "Qué entregable escribir: «medicion» (medición de la planta "
                        "en PDF), «cuadro» (cuadro de superficies en PDF), o "
                        "«coherencia» (informe de coherencia en PDF)."
                    ),
                },
                "ruta": {"type": "string",
                         "description": "El .dxf del arquitecto. Sólo se lee."},
                "ruta_destino": {"type": "string",
                                 "description": ("Dónde se escribe el PDF. No puede "
                                                 "ser el DXF ni un fichero que ya "
                                                 "exista.")},
                "capa": {"type": ["string", "null"],
                         "description": ("Capa de recintos, si ya está confirmada. "
                                         "Se usa en tipo=«medicion» y "
                                         "tipo=«coherencia»; se ignora en "
                                         "tipo=«cuadro».")},
                "factor_escala": {"type": ["number", "null"],
                                  "description": ("Multiplicador a metros, si ya "
                                                  "está confirmado. Se usa en "
                                                  "tipo=«medicion» y "
                                                  "tipo=«coherencia»; se ignora en "
                                                  "tipo=«cuadro».")},
                "respuestas": {
                    "type": ["array", "null"],
                    "description": ("Lo que el arquitecto declara para las celdas "
                                    "que no se pueden calcular. Sólo se usa en "
                                    "tipo=«cuadro»; se ignora en los demás. Mismo "
                                    "formato que plano.cuadro_de_superficies."),
                    "items": {"type": "object"},
                },
            },
            "required": ["tipo", "ruta", "ruta_destino"],
            "additionalProperties": False,
        },
        funcion=entregable_en_pdf,
        efectos=(ESCRIBE_FICHERO,),
        # Une las de las tres capacidades que sustituye, sin perder ninguna —
        # ver docs/design/2026-08-21-fusion-capacidades-pdf-C4.md §2. Las que
        # sólo valen para un `tipo` van marcadas «(tipo=…)»: la fusión es de
        # manifiesto, así que el acta las lista igual venga el tipo que venga
        # de esta invocación — marcarlas evita que se lean como si aplicaran
        # siempre. Sin ids de otras capacidades en el texto (nunca en
        # castellano llano: tests/test_acta_legible_coherencia.py lo vigila).
        limitaciones=(
            "no calcula nada: presenta el dato (la medición, el cuadro o la "
            "revisión de coherencia, según el tipo pedido) tal como lo resolvió "
            "la capacidad determinista que le corresponde, sin repetir el cálculo",
            "(tipo=cuadro) no comprueba normativa ni si las superficies cumplen "
            "ningún mínimo",
            "(tipo=coherencia) no comprueba normativa: el informe dice si el "
            "plano es coherente consigo mismo, no si el proyecto cumple",
            "(tipo=coherencia) no gradúa la gravedad de los hallazgos: los "
            "agrupa por tipo y los mide",
            "no modifica el DXF del arquitecto en ningún tipo: se abre sólo "
            "para leer, y su sha256 se verifica antes y después de escribir",
            "no sobrescribe ningún fichero que no sea el destino indicado, en "
            "ningún tipo",
            "sale marcado como borrador para revisión de un colegiado, sin "
            "opción de quitar esa marca, en los tres tipos",
        ),
    ),
)
