# -*- coding: utf-8 -*-
"""Capacidades normativas: qué rige el proyecto, y con qué número exacto.

Dos capacidades, y están separadas por un motivo que no es de tamaño:

- `normativa.reglas_aplicables` responde **qué** normativa rige y en qué
  estado queda cada regla para este proyecto. Puede decir «aplica pero no la
  puedo evaluar», y ese estado es información, no un fallo.
- `normativa.umbral_de_regla` responde **cuánto**: resuelve el número de una
  tabla de parámetros para unos ejes declarados, siguiendo la cadena de
  repliegue que la propia regla trae escrita.

Separarlas es lo que permite que la segunda solo se ejecute cuando la primera
ha dicho qué falta. Fundidas en una, el agente tendría que adivinar los ejes
antes de saber cuáles son — y adivinar un eje es adivinar el número.

**Las dos envuelven `normativa/`, que ya está construido y probado, y no
añaden ni una regla de decisión.** El corpus, en cambio, tiene hoy **una**
entrada: el piloto de DB-SI 3 tabla 3.1, pendiente de firma colegiada. Eso no
es un defecto de estas capacidades: es el estado real del producto, y aquí se
declara en cada respuesta en vez de disimularse.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from normativa import api, catalogos
from normativa.errores import ErrorNormativa
from normativa.loader import cargar
from normativa.modelo import Parametro
from normativa.registro import registro as _registro_geografico

from ..capacidad import Capacidad


def _cita(norma: dict) -> str:
    """La referencia oficial en una línea, tal cual la trae el corpus."""
    fuente = norma.get("fuente") or {}
    articulo = norma.get("articulo") or {}
    apartado = articulo.get("apartado")
    tabla = articulo.get("tabla")
    partes = [
        fuente.get("identificador_oficial") or "",
        articulo.get("documento_basico") or "",
        articulo.get("seccion") or "",
        "apartado %s" % apartado if apartado else "",
        "tabla %s" % tabla if tabla else "",
    ]
    cita = ", ".join(p for p in partes if p)
    boletin = fuente.get("boletin")
    return "%s (%s)" % (cita, boletin) if boletin else cita


# --- Capacidad 1: qué normativa rige ----------------------------------------

def reglas_aplicables(
    codigo_municipio: str,
    uso: str,
    tipologia: str,
    fecha_devengo: Optional[str] = None,
) -> Dict[str, Any]:
    """Normativa aplicable al proyecto, con el estado y el motivo de cada regla.

    `codigo_municipio` es el código INE que devuelve
    `territorial.resolver_ambito`: la identidad de un municipio es su código, no
    su nombre, y encadenar por el código es lo que hace que renombrar el
    municipio no cambie el resultado.

    Se resuelve en modo **no estricto** a propósito. En modo estricto el motor
    levanta `CoberturaInsuficiente` y no devuelve nada, que es lo correcto para
    emitir un informe y lo peor posible para una conversación: aquí interesa
    poder decir «esto es lo que hay y esto es exactamente lo que falta».
    """
    reg = _registro_geografico()
    if codigo_municipio not in reg.municipios:
        return {
            "ok": False,
            "error": "codigo_municipio_desconocido",
            "detalle": (
                "«%s» no es un código INE del registro. Resuelve antes el municipio "
                "con territorial.resolver_ambito." % codigo_municipio
            ),
        }
    try:
        perfil = api.perfil_proyecto(uso=uso, tipologia=tipologia)
    except ValueError as exc:
        return {
            "ok": False,
            "error": "perfil_invalido",
            "detalle": str(exc),
            "usos_admitidos": sorted(catalogos.usos()),
            "tipologias_admitidas": sorted(catalogos.tipologias()),
        }

    try:
        devengo = date.fromisoformat(fecha_devengo) if fecha_devengo else None
    except ValueError as exc:
        return {"ok": False, "error": "fecha_devengo_invalida", "detalle": str(exc)}

    try:
        conjunto = api.normativa_aplicable(
            reg.cadena_de_municipio(codigo_municipio),
            perfil=perfil,
            fecha_devengo=devengo,
            estricto=False,
        )
    except ErrorNormativa as exc:
        return {"ok": False, "error": "fallo_del_motor_normativo", "detalle": str(exc)}

    return {
        "ok": True,
        "completo": conjunto.completo,
        "fecha_devengo": conjunto.fecha_devengo.isoformat(),
        "normas": [
            {
                "concept_id": n.id,
                "nombre": n.nombre,
                "materia": n.materia,
                "ambito_id": n.ambito,
                "estado": n.estado,
                "motivo": n.motivo,
                "valor_parametro": n.valor_parametro,
                "unidad": n.unidad,
                "cita": str(n.fuente),
                "preguntas_pendientes": list(n.preguntas_pendientes),
            }
            for n in conjunto.normas
        ],
        "materias_sin_cobertura": [f.materia for f in conjunto.faltantes],
        "preguntas_pendientes": list(conjunto.preguntas_pendientes),
        "asunciones": list(conjunto.asunciones),
        "aviso_de_corpus": (
            "El corpus normativo de ArchMuse está en transcripción. Las materias "
            "listadas en `materias_sin_cobertura` NO se han comprobado: sobre ellas "
            "no se puede afirmar ni cumplimiento ni incumplimiento."
        ),
    }


# --- Capacidad 2: cuánto dice esa regla -------------------------------------

def umbral_de_regla(
    concept_id: str, ambito_id: str, ejes: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Resuelve el valor de la tabla de parámetros de una regla para unos ejes.

    Devuelve además la **traza** del motor: qué nivel de la cadena de repliegue
    se usó. Un repliegue silencioso en un umbral es el bug nº1 de este
    repositorio reencarnado, y por eso viaja escrito en la respuesta.

    Si la cadena de repliegue se agota, el valor es `null` **con motivo**, y con
    la lista de valores que cada eje admite, para que la pregunta al usuario sea
    concreta. Nunca devuelve un valor por defecto.
    """
    carga = cargar([ambito_id])
    for fichero in carga.ficheros:
        for regla in fichero.doc.get("reglas") or []:
            if regla.get("concept_id") == concept_id:
                return _resolver(regla, fichero.doc.get("norma") or {}, ejes or {})

    return {
        "ok": False,
        "error": "regla_no_encontrada",
        "detalle": (
            "«%s» no está en el corpus cargado para el ámbito «%s». Puede que la "
            "regla exista y no esté transcrita: el corpus de ArchMuse está en "
            "transcripción." % (concept_id, ambito_id)
        ),
        "reglas_disponibles": sorted(r.get("concept_id", "") for r in carga.reglas),
    }


def _resolver(regla: dict, norma: dict, ejes: Dict[str, str]) -> Dict[str, Any]:
    p = regla.get("parametro") or {}
    parametro = Parametro(
        ejes=tuple(p.get("ejes") or ()),
        valores=tuple(p.get("valores") or ()),
        repliegue=tuple(p.get("repliegue") or ()),
        unidad=p.get("unidad"),
    )
    valor, traza = parametro.resolver(dict(ejes))

    admitidos: Dict[str, List[str]] = {}
    for eje in parametro.ejes:
        vistos = [str(v[eje]) for v in parametro.valores if eje in v]
        admitidos[eje] = sorted(dict.fromkeys(vistos))

    respuesta: Dict[str, Any] = {
        "ok": True,
        "concept_id": regla.get("concept_id"),
        "nombre": regla.get("nombre"),
        "valor": valor,
        "unidad": parametro.unidad,
        "ejes_declarados": dict(ejes),
        "ejes_de_la_regla": list(parametro.ejes),
        "valores_admitidos_por_eje": admitidos,
        "traza": list(traza),
        "cita": _cita(norma),
        "pendiente_de_firma_colegiada": (
            "pendiente_firma_colegiado" in (regla.get("tags") or [])
        ),
    }
    if valor is None:
        respuesta["motivo"] = (
            "La cadena de repliegue de la regla se agotó sin valor aplicable. No hay "
            "número para estos ejes, y no se coge uno por defecto."
        )
        respuesta["pregunta"] = (
            "Para resolver «%s» hacen falta los ejes %s. Valores admitidos: %s."
            % (regla.get("nombre"), list(parametro.ejes), admitidos)
        )
    return respuesta


_ESQUEMA_EJES = {
    "type": "object",
    "description": (
        "Ejes de contexto declarados, como pares nombre->valor. Usa exactamente los "
        "nombres de `ejes_de_la_regla` y los valores de `valores_admitidos_por_eje`."
    ),
    "additionalProperties": {"type": "string"},
}


CAPACIDADES = (
    Capacidad(
        id="normativa.reglas_aplicables",
        version="1.0.0",
        dominio="territorial",
        naturaleza="determinista",
        descripcion=(
            "Dado el código INE de un municipio y el perfil del proyecto (uso y "
            "tipología), devuelve qué normativa del corpus de ArchMuse rige, el "
            "estado de cada regla (aplica, no_aplica, aplica_no_evaluable, "
            "sin_cobertura) con su motivo y su cita oficial, y la lista de materias "
            "SIN cobertura. Necesita el código INE, que da territorial.resolver_ambito."
        ),
        parametros={
            "type": "object",
            "properties": {
                "codigo_municipio": {
                    "type": "string",
                    "description": (
                        "Código INE de 5 dígitos, tal como lo devuelve "
                        "territorial.resolver_ambito."
                    ),
                },
                "uso": {"type": "string", "enum": sorted(catalogos.usos())},
                "tipologia": {"type": "string", "enum": sorted(catalogos.tipologias())},
                "fecha_devengo": {
                    "type": "string",
                    "description": (
                        "Fecha de devengo en ISO (AAAA-MM-DD): la normativa aplicable "
                        "es la vigente entonces, no la de hoy. Si se omite se usa hoy "
                        "y se declara como asunción."
                    ),
                },
            },
            "required": ["codigo_municipio", "uso", "tipologia"],
            "additionalProperties": False,
        },
        funcion=reglas_aplicables,
        efectos=(),
        limitaciones=(
            "el corpus normativo está en transcripción: solo cubre las materias que "
            "no aparecen en `materias_sin_cobertura`",
            "no evalúa el proyecto contra las reglas: dice qué rige, no si se cumple",
        ),
    ),
    Capacidad(
        id="normativa.umbral_de_regla",
        version="1.0.0",
        dominio="territorial",
        naturaleza="determinista",
        descripcion=(
            "Resuelve el valor numérico de la tabla de parámetros de una regla para "
            "unos ejes de contexto declarados (por ejemplo: número de salidas de "
            "planta y condición del recinto), devolviendo la traza del repliegue y la "
            "cita oficial. Si no hay valor para esos ejes devuelve valor=null con la "
            "pregunta concreta: en ese caso NO se puede dar un número."
        ),
        parametros={
            "type": "object",
            "properties": {
                "concept_id": {
                    "type": "string",
                    "description": (
                        "Identificador de la regla, tal como lo devuelve "
                        "normativa.reglas_aplicables."
                    ),
                },
                "ambito_id": {
                    "type": "string",
                    "description": "Ámbito de la regla, p. ej. «es» para normativa estatal.",
                },
                "ejes": _ESQUEMA_EJES,
            },
            "required": ["concept_id", "ambito_id"],
            "additionalProperties": False,
        },
        funcion=umbral_de_regla,
        efectos=(),
        limitaciones=(
            "no comprueba si el proyecto respeta el umbral: devuelve el umbral",
            "una regla marcada `pendiente_de_firma_colegiada` es un ejemplo trabajado, "
            "no corpus de producción validado",
        ),
        referencia_normativa="según la regla consultada; viaja en el campo `cita`",
    ),
)
