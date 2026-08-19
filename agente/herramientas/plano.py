# -*- coding: utf-8 -*-
"""Capacidades de geometría del primer vertical: el cuadro de superficies (`TL-1`).

**Qué se envuelve y qué no.** `analyzer/` tiene 22.031 líneas. Aquí entra
**solo** lo que el vertical usa: leer el plano y llevarlo a metros
(`parser.leer_plano` + `escala`), calcular el borrador del cuadro
(`cuadro_superficies` a través de `cuadro_superficies_export`) y la superficie
útil DB-SI (`superficie_util`). Nada más. La tentación de envolver «ya que
estamos» las 38 reglas de `evaluator` está registrada como `TL-5` y aplazada
con motivo: son cuatro jornadas que no acercan ni un día el primer entregable.

**Granularidad gruesa, a propósito.** Tres capacidades, no quince. Un
planificador que elige entre quince herramientas casi idénticas se degrada —el
mismo razonamiento por el que `TL-5` agrupa las 38 reglas en 4-6 capacidades y
no en 38—, y un arquitecto no piensa en «extraer polígonos» y «emparejar
etiquetas»: piensa en «lee este plano» y «rellena el cuadro».

**La propiedad que estas tres tienen que conservar por encima de todo: cuando
no se sabe, se pregunta.** `parser.leer_plano` se niega a seguir si no sabe en
qué unidad está dibujado el plano (`EscalaIndeterminada`) o de qué capa salen
las estancias (`CapaIndeterminada`), y las dos excepciones traen ya redactado
lo que hay que preguntar. Aquí eso se traduce a `ok: false` **con la pregunta
dentro**, nunca a una suposición: un DXF en milímetros interpretado como metros
cumple todas las superficies mínimas y sale con una puntuación alta y creíble,
que es el peor defecto que ha tenido este repositorio.

Las tres primeras **no escriben nada**, y separarlas de la que sí escribe es lo
que permite que un arquitecto recorra el cálculo entero antes de arriesgar su
fichero. La cuarta —`plano.escribir_cuadro`, tarea `TL-2`, PRD aprobado por
Pablo el 2026-08-19— es la única de naturaleza `io` del registro, y lleva el
patrón de protección que ese PRD fija como condición de su aprobación: el
original **siempre intacto y verificado por SHA-256**, el efecto
**explícitamente autorizado**, y **`N/D` nunca convertido en número**.
"""
from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, List, Optional

from ..capacidad import Capacidad
from ..efectos import ESCRIBE_FICHERO

#: Decimales con los que se publican las superficies. Dos: es la precisión con
#: la que un cuadro de superficies se firma, y publicar más dígitos sugiere una
#: exactitud que la geometría de un DXF no tiene.
DECIMALES = 2


def _falta_el_fichero(ruta: str) -> Optional[Dict[str, Any]]:
    if not ruta or not os.path.isfile(ruta):
        return {
            "ok": False,
            "error": "fichero_no_encontrado",
            "detalle": "No hay ningún fichero en «%s»." % ruta,
            "pregunta": "¿Puedes confirmar la ruta del DXF? No encuentro «%s»." % ruta,
        }
    return None


def _fallo_de_lectura(exc: Exception) -> Dict[str, Any]:
    """Traduce las dos negativas de `parser.leer_plano` a un `ok: false` útil.

    Las dos excepciones —`EscalaIndeterminada` y `CapaIndeterminada`— traen ya
    redactado lo que hay que preguntar, y por eso el mensaje se usa **tal
    cual** en vez de reescribirlo aquí: son el trabajo de alguien que sabía qué
    tenía que ver el arquitecto, y refrasearlo sólo puede empeorarlo.
    """
    from analyzer.parser import CapaIndeterminada, EscalaIndeterminada

    if isinstance(exc, EscalaIndeterminada):
        codigo = "escala_indeterminada"
    elif isinstance(exc, CapaIndeterminada):
        codigo = "capa_indeterminada"
    else:
        codigo = "dxf_ilegible"
    return {"ok": False, "error": codigo, "detalle": str(exc), "pregunta": str(exc)}


def _escala_a_dict(escala: Any) -> Dict[str, Any]:
    return {
        "factor": getattr(escala, "factor", None),
        "unidad": getattr(escala, "unidad", ""),
        "origen": getattr(escala, "origen", ""),
        "mensaje": getattr(escala, "mensaje", ""),
        "decidida": bool(getattr(escala, "decidida", False)),
    }


# ---------------------------------------------------------------------------
# 1. Leer el plano
# ---------------------------------------------------------------------------

def leer_dxf(ruta: str, capa: Optional[str] = None,
             factor_escala: Optional[float] = None) -> Dict[str, Any]:
    """Qué hay dibujado en un DXF, ya en metros, y con qué escala se ha leído."""
    fallo = _falta_el_fichero(ruta)
    if fallo:
        return fallo

    import ezdxf

    from analyzer import parser

    try:
        doc = ezdxf.readfile(ruta)
        plano = parser.leer_plano(doc, layer=capa, factor_escala=factor_escala)
    except Exception as exc:                      # noqa: BLE001 - se traduce, no se traga
        return _fallo_de_lectura(exc)

    recintos = [
        {
            "etiqueta": r.label,
            "area_m2": round(r.area_m2, DECIMALES),
            "capa": r.layer,
        }
        for r in plano.rooms
    ]
    return {
        "ok": True,
        "ruta": os.path.abspath(ruta),
        "capa_de_recintos": plano.layer,
        "escala": _escala_a_dict(plano.escala),
        "recintos": recintos,
        "superficie_util_total_m2": round(sum(r.area_m2 for r in plano.rooms), DECIMALES),
        "viviendas_rotuladas": [etiqueta for etiqueta, _x, _y in plano.unit_labels],
        "recintos_sin_etiqueta": sum(1 for r in plano.rooms if not r.label),
        # Lo que NO se ha leído se cuenta y se dice. Un descarte silencioso es
        # una superficie que falta sin que nadie lo sepa.
        "geometria_no_leida": [
            {"capa": d.capa, "tipo": d.tipo, "motivo": d.motivo}
            for d in plano.geometria_no_leida
        ],
    }


# ---------------------------------------------------------------------------
# 2. El cuadro de superficies
# ---------------------------------------------------------------------------

def cuadro_de_superficies(ruta: str,
                          respuestas: Optional[List[dict]] = None) -> Dict[str, Any]:
    """El borrador del cuadro de superficies: celda a celda, con su motivo.

    `respuestas` cierra el bucle. Sin ellas, la capacidad dice qué no puede
    calcular y por qué —y ahí se acaba: las celdas bloqueadas lo estarían para
    siempre, porque los datos que faltan (el espesor de muro, cuántas
    viviendas de este tipo hay, qué pieza del plano es cada espacio exterior)
    **no están en el dibujo**, están en la cabeza del arquitecto. Con ellas,
    el mismo cálculo se rehace incorporando lo que él declara, marcado como
    declarado por él y no como calculado por ArchMuse: en el acta esas dos
    cosas no valen lo mismo, y confundirlas sería atribuirse un dato ajeno.

    Sigue sin escribir nada. Esta capacidad **enseña** el cuadro completo; la
    que lo escribe en el DXF es `TL-2`, y separarlas es lo que permite que un
    arquitecto pruebe todo el recorrido sin arriesgar su fichero.
    """
    fallo = _falta_el_fichero(ruta)
    if fallo:
        return fallo

    from analyzer.cuadro_superficies_export import obtener_estado_cuadro

    try:
        celdas, solicitudes = obtener_estado_cuadro(ruta, respuestas=respuestas or None)
    except ValueError as exc:
        # Dos casos con la misma forma y motivos distintos: no hay ACAD_TABLE
        # reconocible, o el DXF trae más de una vivienda. Los dos son
        # preguntas al arquitecto, no fallos del sistema.
        return {
            "ok": False,
            "error": "cuadro_no_calculable",
            "detalle": str(exc),
            "pregunta": (
                "No puedo calcular el cuadro de este DXF: %s ¿Es el fichero correcto?"
                % str(exc)
            ),
        }
    except Exception as exc:                      # noqa: BLE001
        return _fallo_de_lectura(exc)

    filas = [
        {
            "campo": c.campo,
            # El rotulo tal cual esta escrito en el cuadro del arquitecto, con
            # sus tildes y su ñ. El `campo` es un identificador ASCII estable y
            # sirve para programar; derivar de el el titulo de una fila produjo
            # «Bano» y «Salon cocina» en el PDF que el arquitecto le enseña a su
            # cliente. Si el cuadro no trae la celda, no hay rotulo que copiar.
            "etiqueta": c.celda.etiqueta if c.celda is not None else None,
            "texto": c.texto,
            "estado": c.estado,
            "motivo": c.motivo,
            "preexistente": c.preexistente,
            "declarado_por_usuario": c.declarado_por_usuario,
            "se_escribiria": c.escribir and c.celda is not None,
        }
        for c in celdas
    ]
    preguntas = [
        {
            "id": s.id,
            "tipo": s.tipo,
            "campos": list(s.campos),
            "titulo": s.titulo,
            "ayuda": s.ayuda,
            "unidad": s.unidad,
            "candidatos": [
                {"id": c.id, "etiqueta": c.room_label,
                 "area_m2": round(c.area_m2, DECIMALES)}
                for c in (s.candidatos or ())
            ],
        }
        for s in solicitudes
    ]
    por_estado: Dict[str, int] = {}
    for fila in filas:
        por_estado[fila["estado"]] = por_estado.get(fila["estado"], 0) + 1

    return {
        "ok": True,
        "ruta": os.path.abspath(ruta),
        "celdas": filas,
        "recuento_por_estado": por_estado,
        "celdas_sin_resolver": [f["campo"] for f in filas
                                if f["estado"] in ("NO_DISPONIBLE", "BLOQUEADO")],
        "preguntas_pendientes": preguntas,
        "completo": not preguntas,
        "celdas_declaradas_por_el_arquitecto": [
            f["campo"] for f in filas if f["declarado_por_usuario"]
        ],
    }


# ---------------------------------------------------------------------------
# 3. La superficie útil, con su procedencia
# ---------------------------------------------------------------------------

def superficie_util(ruta: str, capa: Optional[str] = None) -> Dict[str, Any]:
    """Superficie útil DB-SI de cada vivienda del plano, con su estado."""
    fallo = _falta_el_fichero(ruta)
    if fallo:
        return fallo

    import ezdxf

    from analyzer import evaluator, parser
    from analyzer.superficie_util import superficie_util_db_si

    try:
        doc = ezdxf.readfile(ruta)
        plano = parser.leer_plano(doc, layer=capa)
    except Exception as exc:                      # noqa: BLE001
        return _fallo_de_lectura(exc)

    avanzado = evaluator.evaluate_advanced(plano.rooms, plano.unit_labels)
    viviendas: List[Dict[str, Any]] = []
    for unidad in avanzado.units:
        hecho = superficie_util_db_si(unidad)
        viviendas.append({
            "vivienda": unidad.name,
            "estado": hecho.estado,
            "valor_m2": (round(hecho.valor, DECIMALES)
                         if isinstance(hecho.valor, (int, float)) else hecho.valor),
            "unidad": hecho.unidad,
            # Un hecho que no es KNOWN trae SIEMPRE su motivo. Perderlo aquí
            # convertiría «no se puede medir» en «no hay superficie».
            "motivos": [{"codigo": m.codigo, "detalle": m.detalle} for m in hecho.motivos],
            "procedencia": list(hecho.procedencia),
            "explicacion": hecho.explicacion,
        })
    return {
        "ok": True,
        "ruta": os.path.abspath(ruta),
        "viviendas": viviendas,
        "viviendas_medidas": sum(1 for v in viviendas if v["valor_m2"] is not None),
        "viviendas_sin_medir": sum(1 for v in viviendas if v["valor_m2"] is None),
    }


# ---------------------------------------------------------------------------
# 4. La escritura, con su patrón de protección (`TL-2`)
# ---------------------------------------------------------------------------

def _sha256(ruta: str) -> str:
    with open(ruta, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _mismo_fichero(a: str, b: str) -> bool:
    """Si dos rutas apuntan al mismo fichero, por cualquiera de las vías.

    Se comprueban las cuatro que se dan de verdad, y no una:

    1. La misma cadena.
    2. La misma ruta absoluta tras normalizar.
    3. **Distinta capitalización** — en Windows `Plano.dxf` y `plano.dxf` son el
       mismo fichero, y comparar cadenas no lo detecta.
    4. **Un enlace o unión** que apunta al original. `realpath` lo resuelve.

    Y si las dos existen, `os.path.samefile` lo decide sin depender de ninguna
    heurística de rutas.
    """
    if os.path.exists(a) and os.path.exists(b):
        try:
            if os.path.samefile(a, b):
                return True
        except OSError:                          # pragma: no cover - unidades raras
            pass
    def normalizar(r: str) -> str:
        return os.path.normcase(os.path.realpath(os.path.abspath(r)))
    return normalizar(a) == normalizar(b)


def _destino_seguro(ruta_origen: str, ruta_destino: str) -> Optional[Dict[str, Any]]:
    """Comprueba el destino **antes de abrir nada**. `None` = se puede seguir.

    Dos negativas, las dos con motivo:

    - **El destino no puede ser el origen.** Es la garantía que sostiene toda la
      propuesta de valor de esta capacidad, y por eso se comprueba aquí y no se
      confía en que la función de exportación ya lo mire.
    - **El destino no puede existir ya.** Sobrescribir en silencio un entregable
      anterior es perder trabajo que el arquitecto puede haber revisado y
      anotado. Que cada ejecución produzca su propio fichero es lo que hace que
      la segunda pasada (CU-3 del PRD) no pise a la primera.
    """
    if not ruta_destino:
        return {"ok": False, "error": "destino_no_indicado",
                "detalle": "Hay que decir dónde se escribe la copia.",
                "pregunta": "¿En qué ruta quieres el DXF relleno?"}
    if _mismo_fichero(ruta_origen, ruta_destino):
        return {
            "ok": False,
            "error": "destino_es_el_origen",
            "detalle": ("«%s» y «%s» son el mismo fichero. El DXF original NUNCA se "
                        "sobrescribe: la copia va aparte." % (ruta_origen, ruta_destino)),
            "pregunta": "¿A qué ruta nueva quieres que escriba la copia rellena?",
        }
    if os.path.exists(ruta_destino):
        return {
            "ok": False,
            "error": "destino_ya_existe",
            "detalle": ("Ya hay un fichero en «%s». No se sobrescribe: podría ser un "
                        "entregable anterior ya revisado." % ruta_destino),
            "pregunta": "¿Con qué nombre quieres esta copia?",
        }
    return None


def _ficheros_de(carpeta: str) -> set:
    try:
        return set(os.listdir(carpeta))
    except OSError:                              # pragma: no cover
        return set()


def _con_sello_intacto(ruta_origen: str, sello_antes: str,
                       salida: Dict[str, Any]) -> Dict[str, Any]:
    """Vuelve a sellar el original y lo compara. Se ejecuta SIEMPRE, también
    cuando la escritura ha fallado.

    Un fallo a mitad es justo el momento en el que un original podría haberse
    tocado, así que comprobarlo sólo en el camino feliz sería comprobarlo donde
    no hace falta. Si el sello no coincide, el resultado se convierte en un
    fallo grave: no hay resultado bueno posible si el fichero del arquitecto ha
    cambiado.
    """
    sello_ahora = _sha256(ruta_origen)
    salida = dict(salida)
    salida["sello_origen_sha256"] = sello_antes
    salida["origen_intacto"] = sello_ahora == sello_antes
    if sello_ahora != sello_antes:
        return {
            "ok": False,
            "error": "el_original_ha_cambiado",
            "detalle": ("El sha256 de «%s» era %s y ahora es %s. Algo ha escrito en el "
                        "fichero original. Esto no debería poder ocurrir nunca."
                        % (ruta_origen, sello_antes[:12], sello_ahora[:12])),
            "sello_origen_sha256": sello_antes,
            "sello_origen_ahora": sello_ahora,
            "origen_intacto": False,
        }
    return salida


def escribir_cuadro(ruta_origen: str, ruta_destino: str,
                    respuestas: Optional[List[dict]] = None) -> Dict[str, Any]:
    """Escribe una COPIA del DXF con el cuadro relleno. El original no se toca."""
    fallo = _falta_el_fichero(ruta_origen)
    if fallo:
        return fallo
    fallo = _destino_seguro(ruta_origen, ruta_destino)
    if fallo:
        return fallo

    from analyzer.cuadro_superficies_export import exportar_cuadro_relleno

    # El sello del original, ANTES. Es la mitad de la garantía; la otra mitad es
    # volver a calcularlo al final y compararlos.
    sello_antes = _sha256(ruta_origen)
    carpeta_destino = os.path.dirname(os.path.abspath(ruta_destino)) or "."
    antes_en_carpeta = _ficheros_de(carpeta_destino)

    try:
        resultado = exportar_cuadro_relleno(ruta_origen, ruta_destino,
                                            respuestas=respuestas or None)
    except ValueError as exc:
        return _con_sello_intacto(ruta_origen, sello_antes, {
            "ok": False,
            "error": "cuadro_no_escribible",
            "detalle": str(exc),
            "pregunta": "No he podido rellenar este DXF: %s ¿Es el fichero correcto?" % exc,
        })
    except Exception as exc:                     # noqa: BLE001 - se traduce, no se traga
        return _con_sello_intacto(ruta_origen, sello_antes, _fallo_de_lectura(exc))

    sin_resolver = [
        {"campo": d.get("campo"), "estado": d.get("estado"), "motivo": d.get("motivo")}
        for d in resultado.detalles_sin_resolver
    ]
    nuevos = sorted(_ficheros_de(carpeta_destino) - antes_en_carpeta)

    return _con_sello_intacto(ruta_origen, sello_antes, {
        "ok": True,
        "ruta_origen": os.path.abspath(ruta_origen),
        "ruta_destino": os.path.abspath(ruta_destino),
        "sello_destino_sha256": _sha256(ruta_destino),
        "celdas_escritas": [
            {"campo": c.campo, "texto": c.texto} for c in resultado.celdas_escritas
        ],
        "celdas_omitidas": list(resultado.celdas_omitidas),
        # Lo que sigue sin resolverse va con su motivo, y en la copia esas celdas
        # llevan «N/D»: nunca un número. Es la tercera condición de la
        # aprobación del PRD.
        "celdas_sin_resolver": sin_resolver,
        "copia_reabierta_sin_errores": resultado.reabierta_sin_errores,
        "ficheros_nuevos_en_la_carpeta": nuevos,
    })


def cuadro_en_pdf(ruta: str, ruta_destino: str,
                  respuestas: Optional[List[dict]] = None) -> Dict[str, Any]:
    """El cuadro en PDF, con el porqué de cada celda. No toca el DXF."""
    fallo = _falta_el_fichero(ruta)
    if fallo:
        return fallo
    fallo = _destino_seguro(ruta, ruta_destino)
    if fallo:
        return fallo

    from analyzer.cuadro_pdf import escribir_cuadro_pdf

    sello_antes = _sha256(ruta)
    borrador = cuadro_de_superficies(ruta, respuestas=respuestas)
    if not borrador.get("ok"):
        return _con_sello_intacto(ruta, sello_antes, borrador)

    datos = dict(borrador)
    datos["plano"] = os.path.basename(ruta)
    datos["sello_origen_sha256"] = sello_antes
    # Lo que NO comprueba sale de los manifiestos de las capacidades que se han
    # ejecutado, no de una lista escrita a mano en la plantilla: si mañana esta
    # capacidad deja de usar una de ellas, la lista cambia sola.
    datos["no_comprobado"] = _limitaciones_de(
        "plano.leer_dxf", "plano.cuadro_de_superficies", "plano.superficie_util")

    escribir_cuadro_pdf(datos, ruta_destino)
    return _con_sello_intacto(ruta, sello_antes, {
        "ok": True,
        "ruta_origen": os.path.abspath(ruta),
        "ruta_destino": os.path.abspath(ruta_destino),
        "sello_destino_sha256": _sha256(ruta_destino),
        "celdas": borrador["celdas"],
        "celdas_sin_resolver": borrador["celdas_sin_resolver"],
        "preguntas_pendientes": borrador["preguntas_pendientes"],
    })


def _limitaciones_de(*ids: str) -> List[str]:
    """Las limitaciones declaradas por unas capacidades, sin repetir.

    Se leen del módulo y no del registro para no importar el registro desde una
    herramienta —sería una dependencia circular—, y en el mismo orden en que se
    declaran, que es estable.
    """
    fuera: List[str] = []
    for cap in CAPACIDADES:
        if cap.id not in ids:
            continue
        for limitacion in cap.limitaciones:
            if limitacion not in fuera:
                fuera.append(limitacion)
    return fuera


CAPACIDADES = (

    Capacidad(
        id="plano.leer_dxf",
        version="1.0.0",
        dominio="plano",
        naturaleza="determinista",
        descripcion=(
            "Lee un DXF y devuelve qué hay dibujado, ya convertido a metros: los recintos "
            "con su etiqueta y su superficie, las viviendas rotuladas, la escala con la que "
            "se ha leído y la geometría que NO se ha podido leer, con su motivo. Si no se "
            "puede saber en qué unidad está dibujado el plano, o de qué capa salen las "
            "estancias, devuelve ok=false con la pregunta concreta: en ese caso hay que "
            "preguntar al arquitecto, NUNCA suponer una unidad."
        ),
        parametros={
            "type": "object",
            "properties": {
                "ruta": {"type": "string",
                         "description": "Ruta del fichero .dxf en el sistema de ficheros."},
                "capa": {"type": ["string", "null"],
                         "description": "Capa de la que salen los recintos, si el arquitecto "
                                        "ya la ha confirmado. Sin ella se deduce."},
                "factor_escala": {"type": ["number", "null"],
                                  "description": "Multiplicador de longitud a metros, si el "
                                                 "arquitecto ya lo ha confirmado."},
            },
            "required": ["ruta"],
            "additionalProperties": False,
        },
        funcion=leer_dxf,
        efectos=(),
        limitaciones=(
            "no comprueba normativa de ningún tipo: dice qué hay dibujado, no si cumple",
            "no mide superficies construidas: sin los espesores de muro no se pueden "
            "deducir del dibujo",
            "la clasificación de un recinto sale de su etiqueta de texto, no de su "
            "geometría: un recinto mal rotulado se lee mal",
        ),
    ),
    Capacidad(
        id="plano.cuadro_de_superficies",
        version="1.0.0",
        dominio="plano",
        naturaleza="determinista",
        descripcion=(
            "Calcula el borrador del cuadro de superficies de una vivienda a partir de su "
            "DXF: qué texto llevaría cada celda y por qué. Cada celda vuelve con su estado "
            "— CALCULADO, CERO_REAL (se buscó y no hay ninguno), NO_DISPONIBLE (no se puede "
            "saber con lo que hay en el plano) o BLOQUEADO (hay ambigüedad real y no se "
            "elige por el arquitecto) — y con las preguntas que resolverían las pendientes. "
            "NO escribe nada en ningún fichero."
        ),
        parametros={
            "type": "object",
            "properties": {
                "ruta": {"type": "string",
                         "description": "Ruta del .dxf con el cuadro de superficies."},
                "respuestas": {
                    "type": ["array", "null"],
                    "description": (
                        "Lo que el arquitecto declara para resolver las preguntas "
                        "pendientes. Numérica: {\"tipo\": \"numerico\", \"campo\": "
                        "\"superficie_construida_cerrada\", \"valor\": 65.4}. Asignación: "
                        "{\"tipo\": \"asignacion\", \"solicitud_id\": \"...\", "
                        "\"asignaciones\": {\"terraza_1\": \"cand_0\"}}. Los ids salen de "
                        "`preguntas_pendientes`. NUNCA se inventan: si no los ha dicho el "
                        "arquitecto, la celda se queda como está."
                    ),
                    "items": {"type": "object"},
                },
            },
            "required": ["ruta"],
            "additionalProperties": False,
        },
        funcion=cuadro_de_superficies,
        efectos=(),
        limitaciones=(
            "no escribe el DXF: sólo calcula qué llevaría cada celda",
            "las superficies construidas y el número de unidades no se deducen de la "
            "geometría; salen como NO_DISPONIBLE hasta que el arquitecto los declare",
            "no comprueba lo que el arquitecto declara en `respuestas`: lo registra como "
            "declarado por él, con esa procedencia, y no lo contrasta contra el dibujo",
            "cuando el cuadro pide N piezas de una familia y la geometría no da N piezas "
            "inequívocas, la celda queda BLOQUEADA: no se reparte por orden de aparición",
            "sólo admite un DXF con una única vivienda detectada",
        ),
    ),
    Capacidad(
        id="plano.superficie_util",
        version="1.0.0",
        dominio="plano",
        naturaleza="determinista",
        descripcion=(
            "Superficie útil DB-SI de cada vivienda del plano, con su estado y su "
            "procedencia. Una vivienda cuya geometría no permite medir con seguridad "
            "(recintos solapados, piezas ambiguas) vuelve con valor null y su motivo "
            "estructurado: NUNCA con un número degradado."
        ),
        parametros={
            "type": "object",
            "properties": {
                "ruta": {"type": "string", "description": "Ruta del fichero .dxf."},
                "capa": {"type": ["string", "null"],
                         "description": "Capa de recintos, si ya está confirmada."},
            },
            "required": ["ruta"],
            "additionalProperties": False,
        },
        funcion=superficie_util,
        efectos=(),
        limitaciones=(
            "es superficie útil, no construida: no incluye espesores de muro",
            "no comprueba si la superficie cumple ningún mínimo normativo",
            "una vivienda con recintos solapados no se mide: se declara con su motivo",
        ),
    ),
    Capacidad(
        id="plano.escribir_cuadro",
        version="1.0.0",
        dominio="plano",
        naturaleza="io",
        descripcion=(
            "Escribe una COPIA NUEVA del DXF con el cuadro de superficies relleno. El "
            "fichero original NUNCA se toca: se comprueba su sha256 antes y después y se "
            "devuelve en el resultado. Las celdas que no se han podido resolver salen "
            "como «N/D» — nunca con un número inventado — y vuelven listadas con su "
            "motivo. Las celdas que el DXF ya traía escritas se conservan literales. "
            "Exige autorización explícita del efecto «escribe_fichero»: sin ella no se "
            "crea ningún fichero."
        ),
        parametros={
            "type": "object",
            "properties": {
                "ruta_origen": {"type": "string",
                                "description": "El .dxf del arquitecto. Sólo se lee."},
                "ruta_destino": {"type": "string",
                                 "description": ("Dónde se escribe la copia rellena. No "
                                                 "puede ser el origen ni un fichero que "
                                                 "ya exista.")},
                "respuestas": {
                    "type": ["array", "null"],
                    "description": ("Lo que el arquitecto declara para las celdas que no "
                                    "se pueden calcular. Mismo formato que en "
                                    "plano.cuadro_de_superficies."),
                    "items": {"type": "object"},
                },
            },
            "required": ["ruta_origen", "ruta_destino"],
            "additionalProperties": False,
        },
        funcion=escribir_cuadro,
        efectos=(ESCRIBE_FICHERO,),
        limitaciones=(
            "escribe una copia, nunca el original: el fichero de origen se abre sólo en "
            "lectura y su sha256 se verifica antes y después",
            "no comprueba normativa: rellena el cuadro, no dice si el proyecto cumple",
            "no resuelve las celdas bloqueadas ni las no disponibles; las escribe como "
            "«N/D» y las devuelve con su motivo",
            "no sobrescribe una celda que el DXF ya traía escrita, coincida o no con lo "
            "calculado",
            "sólo admite un DXF con una única vivienda detectada",
        ),
    ),
    Capacidad(
        id="plano.cuadro_en_pdf",
        version="1.0.0",
        dominio="plano",
        naturaleza="io",
        descripcion=(
            "Escribe el cuadro de superficies en un PDF legible, con el valor de cada "
            "celda, su estado y DE DÓNDE SALE — o por qué no se ha podido calcular. "
            "Incluye las preguntas que resolverían las celdas pendientes y la lista de "
            "lo que este trabajo NO comprueba, derivada de los manifiestos de lo que se "
            "ha ejecutado. El DXF no se toca. Exige autorización del efecto "
            "«escribe_fichero»."
        ),
        parametros={
            "type": "object",
            "properties": {
                "ruta": {"type": "string",
                         "description": "El .dxf del arquitecto. Sólo se lee."},
                "ruta_destino": {"type": "string",
                                 "description": ("Dónde se escribe el PDF. No puede ser "
                                                 "el DXF ni un fichero que ya exista.")},
                "respuestas": {
                    "type": ["array", "null"],
                    "description": ("Lo que el arquitecto declara para las celdas que no "
                                    "se pueden calcular del plano."),
                    "items": {"type": "object"},
                },
            },
            "required": ["ruta", "ruta_destino"],
            "additionalProperties": False,
        },
        funcion=cuadro_en_pdf,
        efectos=(ESCRIBE_FICHERO,),
        limitaciones=(
            "no calcula nada: presenta el cuadro tal como lo resolvió "
            "plano.cuadro_de_superficies",
            "no comprueba normativa ni si las superficies cumplen ningún mínimo",
            "sale marcado como borrador para revisión de un colegiado, sin opción de "
            "quitarlo",
        ),
    ),
)
