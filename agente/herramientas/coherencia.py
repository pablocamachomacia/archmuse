# -*- coding: utf-8 -*-
"""La capacidad de revisar un plano contra sí mismo (`CO-4`).

PRD: `docs/prd/2026-08-19-revision-de-coherencia-del-plano.md`.

**Una capacidad, no cinco.** La tentación era registrar «detectar solapes»,
«comprobar rótulos», «contrastar el cuadro»... y son cinco herramientas casi
idénticas que degradan al planificador y que no se corresponden con nada que un
arquitecto piense. Un arquitecto piensa «repásame este plano», y eso es una
capacidad. Mismo criterio grueso que las de `plano.py`, y el mismo que `C4`
impone al tamaño del registro.

**Dos capacidades y no una, separadas por el efecto.** `plano.coherencia` sólo
lee: `efectos=()`, no pide autorización y no puede escribir nada.
`plano.informe_de_coherencia` escribe el PDF y por eso declara
`escribe_fichero`. Juntarlas obligaría a autorizar una escritura para mirar, y
un arquitecto al que se le piden autorizaciones que no hacen falta aprende a
concederlas sin leerlas — ese día la autorización deja de servir para nada. Es
el mismo criterio con el que `plano.py` separa las tres de lectura de
`plano.escribir_cuadro`.

**El DXF del arquitecto no se toca en ninguna de las dos.** Ni siquiera hay un
motivo para escribir en él; aun así su sha256 se comprueba antes y después de
generar el informe, porque eso convierte «no lo tocamos» en un hecho verificado
en vez de en una promesa.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..capacidad import Capacidad
from ..efectos import ESCRIBE_FICHERO
# Los tres guardianes de la escritura se IMPORTAN, no se reimplementan. Escribir
# aquí una versión «parecida» es exactamente el fallo que
# `tests/test_agente_escritura.py` vigila: el día que se endurezca la protección
# —porque un plano de un cliente se pierda— tiene que endurecerse en un sitio y
# no en tres, y una copia con la misma intención y distinto código es una copia
# que nadie recuerda actualizar.
from .plano import _con_sello_intacto, _destino_seguro, _falta_el_fichero, _sha256


def revisar_coherencia(ruta: str, capa: Optional[str] = None,
                       factor_escala: Optional[float] = None) -> Dict[str, Any]:
    """Qué no cuadra en este plano, con la entidad de cada hallazgo."""
    fallo = _falta_el_fichero(ruta)
    if fallo:
        return fallo

    import ezdxf

    from analyzer import coherencia

    try:
        doc = ezdxf.readfile(ruta)
        revision = coherencia.revisar(doc, layer=capa, factor_escala=factor_escala)
    except Exception as exc:                      # noqa: BLE001 - se traduce, no se traga
        # Las dos negativas del parser traen ya redactado lo que hay que
        # preguntar, y se usan tal cual: refrasearlas sólo puede empeorarlas.
        # Y son negativas legítimas, no fallos: sin saber la unidad del dibujo,
        # medir un solape en metros cuadrados daría una cifra de siete dígitos
        # presentada con toda seriedad.
        from analyzer.parser import CapaIndeterminada, EscalaIndeterminada

        if isinstance(exc, EscalaIndeterminada):
            codigo = "escala_indeterminada"
        elif isinstance(exc, CapaIndeterminada):
            codigo = "capa_indeterminada"
        else:
            codigo = "dxf_ilegible"
        return {"ok": False, "error": codigo, "detalle": str(exc), "pregunta": str(exc)}

    salida = revision.a_dict()
    salida["ok"] = True
    salida["ruta"] = os.path.abspath(ruta)
    return salida


def escribir_informe(ruta: str, ruta_destino: str, capa: Optional[str] = None,
                     factor_escala: Optional[float] = None) -> Dict[str, Any]:
    """Escribe el informe de coherencia en PDF. **El DXF se abre sólo para leer.**

    Mismo patrón de protección que `plano.escribir_cuadro` y `plano.cuadro_en_pdf`,
    y con los mismos guardianes —no con unos parecidos—: el destino se comprueba
    **antes de abrir nada** (`_destino_seguro`: ni el propio plano, ni un fichero
    que ya exista, para no pisar un entregable que el arquitecto ya haya
    revisado), y el sello del original se vuelve a calcular **siempre** al
    terminar, también cuando la revisión ha fallado (`_con_sello_intacto`), que
    es justo el momento en el que un original podría haberse tocado.

    Aquí no hay ni siquiera un motivo para escribir en el DXF. Comprobarlo de
    todas formas es lo que convierte «no lo tocamos» en un hecho verificado en
    vez de en una promesa.
    """
    fallo = _falta_el_fichero(ruta)
    if fallo:
        return fallo
    fallo = _destino_seguro(ruta, ruta_destino)
    if fallo:
        return fallo

    from analyzer.coherencia_pdf import escribir_informe_pdf

    sello_antes = _sha256(ruta)
    revision = revisar_coherencia(ruta, capa=capa, factor_escala=factor_escala)
    if not revision.get("ok"):
        return _con_sello_intacto(ruta, sello_antes, revision)

    datos = dict(revision)
    datos["plano"] = os.path.basename(ruta)
    datos["sello_origen_sha256"] = sello_antes
    try:
        escribir_informe_pdf(datos, ruta_destino)
    except OSError as exc:
        return _con_sello_intacto(ruta, sello_antes, {
            "ok": False,
            "error": "no_se_ha_podido_escribir",
            "detalle": "No se ha podido escribir «%s»: %s" % (ruta_destino, exc),
            "pregunta": "¿Puedo escribir en esa carpeta?",
        })

    salida = dict(revision)
    salida["ruta_origen"] = os.path.abspath(ruta)
    salida["ruta_destino"] = os.path.abspath(ruta_destino)
    salida["sello_destino_sha256"] = _sha256(ruta_destino)
    return _con_sello_intacto(ruta, sello_antes, salida)


CAPACIDADES = (
    Capacidad(
        id="plano.coherencia",
        version="1.0.0",
        dominio="plano",
        naturaleza="determinista",
        descripcion=(
            "Revisa si un DXF es coherente consigo mismo antes de entregarlo: recintos "
            "que se solapan (metros contados dos veces), contornos que el fichero declara "
            "abiertos y se han cerrado por suposición, rótulos repetidos o ausentes, "
            "geometría descartada con su motivo, y si el cuadro de superficies y el dibujo "
            "nombran y cuentan las mismas piezas. Cada hallazgo trae la entidad concreta "
            "—rótulo, superficie o handle del DXF— para poder ir a verlo. NO comprueba "
            "normativa y NO gradúa la gravedad: dice qué es y cuánto mide. No escribe nada."
        ),
        parametros={
            "type": "object",
            "properties": {
                "ruta": {"type": "string",
                         "description": "Ruta del fichero .dxf. Sólo se lee."},
                "capa": {"type": ["string", "null"],
                         "description": "Capa de la que salen los recintos, si el "
                                        "arquitecto ya la ha confirmado. Sin ella se "
                                        "deduce."},
                "factor_escala": {"type": ["number", "null"],
                                  "description": "Multiplicador de longitud a metros, si "
                                                 "el arquitecto ya lo ha confirmado."},
            },
            "required": ["ruta"],
            "additionalProperties": False,
        },
        funcion=revisar_coherencia,
        efectos=(),
        limitaciones=(
            "no comprueba normativa: dice si el plano es coherente consigo mismo, no si "
            "el proyecto cumple",
            "no gradúa la gravedad de lo que encuentra: eso es criterio profesional y lo "
            "pone el arquitecto",
            "una discrepancia entre el cuadro y el dibujo no es necesariamente un error: "
            "un pasillo puede no dibujarse como recinto propio",
            "no lee muros, huecos ni carpintería: sólo los recintos de la capa de áreas",
            "sólo admite un DXF con una única vivienda detectada",
        ),
    ),
    Capacidad(
        id="plano.informe_de_coherencia",
        version="1.0.0",
        dominio="plano",
        naturaleza="io",
        descripcion=(
            "Escribe en PDF la revisión de coherencia de un DXF: los hallazgos con su "
            "entidad y su magnitud, qué se ha comprobado, y qué no se ha podido "
            "comprobar y por qué. El plano de entrada se abre SÓLO PARA LEER y su "
            "sha256 se verifica antes y después. Sale marcado como borrador para "
            "revisión de un colegiado, sin opción de quitarlo."
        ),
        parametros={
            "type": "object",
            "properties": {
                "ruta": {"type": "string",
                         "description": "Ruta del .dxf que se revisa. Sólo se lee."},
                "ruta_destino": {"type": "string",
                                 "description": ("Dónde se escribe el informe PDF. No "
                                                 "puede ser el propio plano.")},
                "capa": {"type": ["string", "null"],
                         "description": "Capa de recintos, si ya está confirmada."},
                "factor_escala": {"type": ["number", "null"],
                                  "description": "Multiplicador a metros, si ya está "
                                                 "confirmado."},
            },
            "required": ["ruta", "ruta_destino"],
            "additionalProperties": False,
        },
        funcion=escribir_informe,
        efectos=(ESCRIBE_FICHERO,),
        limitaciones=(
            "no modifica el DXF del arquitecto: sólo lo lee, y lo comprueba con su "
            "sha256 antes y después",
            "no comprueba normativa: el informe dice si el plano es coherente consigo "
            "mismo, no si el proyecto cumple",
            "no gradúa la gravedad de los hallazgos: los agrupa por tipo y los mide",
            "no sobrescribe el plano ni ningún fichero que no sea el destino indicado",
        ),
    ),
)
