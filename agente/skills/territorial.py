# -*- coding: utf-8 -*-
"""Skill: ficha normativa de una parcela.

Atiende el objetivo «comprueba esta parcela y su normativa» de la lista de
Pablo. Es la Skill más sencilla que ya hace trabajo real, y por eso es la
primera: encadena tres capacidades, no emite criterio, cita cada cifra y —lo
importante— **declara con nombre y apellidos las doce materias sobre las que no
puede afirmar nada**.

Esa última parte es la que la separa de un informe de cumplimiento al uso. Un
listado de normativa se lee como completo, siempre; entregar «esto es lo que
rige» sobre un corpus en transcripción sin decir qué falta sería el peor
resultado posible del producto, y está escrito así en el propio motor
normativo. La Skill hereda esa postura en vez de suavizarla.
"""
from __future__ import annotations

from typing import List

from analyzer.hechos import Motivo

from ..afirmacion import Afirmacion, calculo
from ..skill import Requisito, ResultadoDeSkill, Skill
from ..verificacion import Verificacion

CLAVE_MUNICIPIO = "territorial.municipio"
CLAVE_USO = "proyecto.uso"
CLAVE_TIPOLOGIA = "proyecto.tipologia"

PRODUCE = (
    "territorial.codigo_ine",
    "territorial.cadena_ambitos",
    "normativa.reglas_que_aplican",
    "normativa.materias_sin_cobertura",
)


def _ejecutar(ctx) -> ResultadoDeSkill:
    afirmaciones: List[Afirmacion] = []
    no_hecho: List[str] = []
    preguntas: List[str] = []

    municipio = ctx.valor(CLAVE_MUNICIPIO)
    ambito = ctx.invocar("territorial.resolver_ambito", municipio=municipio)

    if not ambito.get("ok"):
        # El municipio no se resuelve: no hay nada que preguntarle al motor
        # normativo, y fingir una cadena territorial sería inventar el trabajo.
        motivo = Motivo(codigo=ambito.get("error", "ambito_irresoluble"),
                        detalle=ambito.get("detalle", ""))
        for clave in PRODUCE:
            afirmaciones.append(
                Afirmacion(nombre=clave, naturaleza="hecho", valor=None,
                           estado="UNKNOWN", origen="observado", fuente=ctx.firma,
                           motivo=motivo)
            )
        if ambito.get("pregunta"):
            preguntas.append(ambito["pregunta"])
        no_hecho.append("no se ha podido resolver el ámbito territorial de «%s»" % municipio)
        return ResultadoDeSkill(afirmaciones=tuple(afirmaciones), preguntas=tuple(preguntas),
                                no_hecho=tuple(no_hecho))

    codigo = ambito["codigo_municipio"]
    afirmaciones.append(calculo("territorial.codigo_ine", codigo, fuente=ctx.firma))
    afirmaciones.append(
        calculo("territorial.cadena_ambitos", [a["id"] for a in ambito["cadena"]],
                fuente=ctx.firma)
    )

    aplicables = ctx.invocar(
        "normativa.reglas_aplicables",
        codigo_municipio=codigo,
        uso=ctx.valor(CLAVE_USO),
        tipologia=ctx.valor(CLAVE_TIPOLOGIA),
        **({"fecha_devengo": ctx.valor("proyecto.fecha_devengo")}
           if ctx.valor("proyecto.fecha_devengo") else {}),
    )

    if not aplicables.get("ok"):
        motivo = Motivo(codigo=aplicables.get("error", "normativa_irresoluble"),
                        detalle=aplicables.get("detalle", ""))
        for clave in ("normativa.reglas_que_aplican", "normativa.materias_sin_cobertura"):
            afirmaciones.append(
                Afirmacion(nombre=clave, naturaleza="hecho", valor=None, estado="UNKNOWN",
                           origen="observado", fuente=ctx.firma, motivo=motivo)
            )
        no_hecho.append("el motor normativo ha rechazado el perfil del proyecto")
        return ResultadoDeSkill(afirmaciones=tuple(afirmaciones), no_hecho=tuple(no_hecho))

    reglas = [
        {
            "concept_id": n["concept_id"],
            "nombre": n["nombre"],
            "materia": n["materia"],
            "estado": n["estado"],
            "motivo": n["motivo"],
            "cita": n["cita"],
            "valor": n["valor_parametro"],
            "unidad": n["unidad"],
        }
        for n in aplicables["normas"]
    ]
    afirmaciones.append(calculo("normativa.reglas_que_aplican", reglas, fuente=ctx.firma))

    sin_cobertura = list(aplicables["materias_sin_cobertura"])
    if sin_cobertura:
        # Se emite como dato conocido —sabemos perfectamente cuáles son— y
        # además como rama no hecha, porque son las dos cosas a la vez.
        afirmaciones.append(
            calculo("normativa.materias_sin_cobertura", sin_cobertura, fuente=ctx.firma)
        )
        no_hecho.append(
            "sin comprobar por falta de corpus transcrito: %s" % ", ".join(sin_cobertura)
        )
    else:
        afirmaciones.append(
            calculo("normativa.materias_sin_cobertura", [], fuente=ctx.firma)
        )

    preguntas.extend(aplicables.get("preguntas_pendientes") or ())
    for n in aplicables["normas"]:
        if n["estado"] == "aplica_no_evaluable":
            no_hecho.append(
                "«%s» aplica pero no se ha podido evaluar: %s" % (n["nombre"], n["motivo"])
            )

    return ResultadoDeSkill(
        afirmaciones=tuple(afirmaciones),
        preguntas=tuple(dict.fromkeys(preguntas)),
        no_hecho=tuple(no_hecho),
        notas=(
            "Corpus normativo en transcripción: lo que aparece en "
            "`normativa.materias_sin_cobertura` no se ha comprobado.",
        ),
    )


def _cada_regla_lleva_cita(resultado) -> object:
    """Verificación de dominio: una regla sin cita no se puede defender.

    Puede fallar de verdad —basta con que una entrada del corpus se transcriba
    sin boletín— y por eso está aquí y no es decorado.
    """
    for a in resultado.afirmaciones:
        if a.nombre != "normativa.reglas_que_aplican" or not a.valor:
            continue
        mudas = [r["concept_id"] for r in a.valor if not r.get("cita")]
        if mudas:
            return "reglas sin cita oficial: %s" % mudas
    return True


SKILLS = (
    Skill(
        id="territorial.ficha_normativa_de_parcela",
        version="1.0.0",
        dominio="territorial",
        objetivo=(
            "Determinar qué normativa rige un proyecto en un municipio concreto, con "
            "la cita oficial de cada regla y la lista explícita de materias que NO se "
            "han podido comprobar."
        ),
        cuando_usarla=(
            "Cuando el objetivo sea situar el proyecto normativamente: «comprueba esta "
            "parcela y su normativa», «qué me aplica aquí», «en qué ámbito estoy». NO "
            "usarla para evaluar si el proyecto cumple: esta Skill dice qué rige, no si "
            "se respeta."
        ),
        procedimiento=(
            "1. Resolver el municipio a su código INE y a la cadena de ámbitos.",
            "2. Pedir al motor normativo la normativa aplicable al perfil del proyecto.",
            "3. Recoger el estado y la cita de cada regla, sin reinterpretarlos.",
            "4. Declarar, con nombre, las materias sin cobertura en el corpus.",
            "5. Trasladar las preguntas pendientes del motor tal cual, sin resolverlas.",
        ),
        requiere=(
            Requisito(clave=CLAVE_MUNICIPIO,
                      pregunta="¿En qué municipio está la parcela?"),
            Requisito(clave=CLAVE_USO,
                      pregunta="¿Cuál es el uso principal del proyecto (residencial, "
                               "comercial, docente…)?"),
            Requisito(clave=CLAVE_TIPOLOGIA,
                      pregunta="¿Qué tipología es (plurifamiliar, unifamiliar aislada…)?"),
        ),
        capacidades=("territorial.resolver_ambito", "normativa.reglas_aplicables"),
        produce=PRODUCE,
        funcion=_ejecutar,
        verificaciones=(
            Verificacion(
                nombre="cada_regla_lleva_cita",
                descripcion="Toda regla devuelta trae su referencia oficial.",
                funcion=_cada_regla_lleva_cita,
            ),
        ),
        efectos=(),
        limitaciones=(
            "el corpus normativo está en transcripción y cubre una sola materia estatal",
            "el registro geográfico es una semilla manual, no el fichero oficial del INE",
            "no evalúa el proyecto: dice qué normativa rige, no si se cumple",
            "no consulta el Catastro ni el planeamiento municipal vigente",
        ),
    ),
)
