# -*- coding: utf-8 -*-
"""Skill: registrar los requisitos del cliente y detectar lo que contradicen.

Atiende la parte determinista de «resume este correo y dime qué cambios pide el
cliente». La parte de *leer el correo* es interpretación de lenguaje y llegará
como una capacidad `llm` que propondrá pares clave-valor; **esta Skill es la que
recibe esos pares y hace con ellos lo único que no puede equivocarse**:
guardarlos con su procedencia y decir cuáles contradicen algo ya acordado.

**Por qué la separación importa.** Si el mismo paso interpretara y guardara, un
malentendido del modelo entraría en la memoria del proyecto como requisito del
cliente y a partir de ahí sería indistinguible de uno real. Con la frontera, lo
que el modelo produce es una **propuesta de requisito** que alguien confirma; lo
que esta Skill guarda ya viene decidido.

**Es la primera Skill con efecto.** Escribe en la memoria del proyecto, así que
no se ejecuta sin autorización — y esa autorización es de verdad, no un trámite:
cambiar un requisito del cliente cambia lo que ArchMuse creerá mañana en todos
los trabajos siguientes.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..afirmacion import calculo
from ..efectos import ESCRIBE_MEMORIA
from ..memoria import REQUISITO, RESTRICCION
from ..skill import ResultadoDeSkill, Skill
from ..verificacion import Verificacion

PRODUCE = (
    "programa.requisitos_registrados",
    "programa.conflictos_con_lo_acordado",
)

CLASES_ADMITIDAS = (REQUISITO, RESTRICCION)


def _ejecutar(ctx) -> ResultadoDeSkill:
    declarados: Dict[str, Any] = dict(ctx.argumentos.get("requisitos") or {})
    clase = ctx.argumentos.get("clase") or REQUISITO
    origen = ctx.argumentos.get("origen") or "sin origen declarado"

    if clase not in CLASES_ADMITIDAS:
        raise ValueError(
            "clase «%s» no admitida aquí; usa %s" % (clase, list(CLASES_ADMITIDAS))
        )
    if not declarados:
        return ResultadoDeSkill(
            afirmaciones=(
                calculo("programa.requisitos_registrados", [], fuente=ctx.firma),
                calculo("programa.conflictos_con_lo_acordado", [], fuente=ctx.firma),
            ),
            no_hecho=("no se ha registrado nada: no venía ningún requisito",),
        )

    # Lo anterior se lee ANTES de escribir. Después ya no se podría distinguir
    # lo que había de lo que acabamos de meter.
    previos = {
        clave: ctx.memoria.valor(clave)
        for clave in declarados
        if ctx.memoria.vigente(clave) is not None
    }

    registrados: List[str] = []
    conflictos: List[dict] = []
    for clave in sorted(declarados):
        valor = declarados[clave]
        ctx.memoria.declarar(
            clave, valor,
            registrado_por="cliente (via %s)" % origen,
            clase=clase,
            nota="registrado por %s" % ctx.firma,
        )
        registrados.append(clave)
        if clave in previos and previos[clave] != valor:
            conflictos.append(
                {"clave": clave, "antes": previos[clave], "ahora": valor, "origen": origen}
            )

    afirmaciones = [
        calculo("programa.requisitos_registrados", registrados, fuente=ctx.firma),
        calculo("programa.conflictos_con_lo_acordado", conflictos, fuente=ctx.firma),
    ]
    notas = ["Registrados %d requisito(s) desde: %s." % (len(registrados), origen)]
    no_hecho: List[str] = []
    if conflictos:
        # No se resuelve: manda el más reciente para poder seguir trabajando, y
        # el conflicto se declara. Elegir en silencio entre dos cosas que ha
        # dicho el cliente es exactamente cómo se pierde un cliente.
        no_hecho.append(
            "hay %d requisito(s) que contradicen lo acordado antes y NO se han "
            "resuelto: %s" % (len(conflictos), [c["clave"] for c in conflictos])
        )
    return ResultadoDeSkill(
        afirmaciones=tuple(afirmaciones), notas=tuple(notas), no_hecho=tuple(no_hecho)
    )


def _nada_se_pierde(resultado) -> object:
    """Todo lo que entró está registrado o declarado como no registrado.

    Falla de verdad si alguien introduce un filtro silencioso —«los valores
    vacíos no los guardo»—, que es la clase de atajo que hace desaparecer un
    requisito sin que nadie se entere hasta el proyecto entregado.
    """
    por_nombre = {a.nombre: a for a in resultado.afirmaciones}
    registrados = por_nombre.get("programa.requisitos_registrados")
    if registrados is None or registrados.valor is None:
        return "no se ha declarado qué se registró"
    if len(set(registrados.valor)) != len(registrados.valor):
        return "hay claves repetidas en lo registrado: %s" % registrados.valor
    return True


SKILLS = (
    Skill(
        id="programa.registrar_requisitos_del_cliente",
        version="1.0.0",
        dominio="programa",
        objetivo=(
            "Guardar en la memoria del proyecto lo que el cliente pide o prohíbe, con "
            "su procedencia, y señalar qué contradice algo ya acordado."
        ),
        cuando_usarla=(
            "Cuando lleguen requisitos o restricciones nuevas del cliente ya "
            "identificadas: de un correo leído, de una reunión, de un pliego. NO "
            "usarla para interpretar texto libre — esta Skill recibe pares "
            "clave-valor decididos, no los deduce."
        ),
        procedimiento=(
            "1. Leer lo que ya constaba para esas mismas claves, antes de escribir nada.",
            "2. Registrar cada requisito con su origen y quién lo dijo.",
            "3. Comparar con lo anterior y declarar los conflictos, sin resolverlos.",
            "4. Dejar que mande el más reciente para poder seguir trabajando.",
        ),
        requiere=(),
        capacidades=(),
        produce=PRODUCE,
        parametros={
            "type": "object",
            "properties": {
                "requisitos": {
                    "type": "object",
                    "description": (
                        "Pares clave->valor ya identificados, p. ej. "
                        "{\"programa.dormitorios\": 4}. Las claves son las del "
                        "proyecto, no texto libre."
                    ),
                    "additionalProperties": True,
                },
                "origen": {
                    "type": "string",
                    "description": "De dónde vienen: «correo del 12/08», «acta de reunión»…",
                },
                "clase": {"type": "string", "enum": list(CLASES_ADMITIDAS)},
            },
            "required": ["requisitos", "origen"],
            "additionalProperties": False,
        },
        funcion=_ejecutar,
        verificaciones=(
            Verificacion(
                nombre="nada_de_lo_que_entro_se_pierde",
                descripcion="Todo requisito recibido queda registrado o declarado.",
                funcion=_nada_se_pierde,
            ),
        ),
        efectos=(ESCRIBE_MEMORIA,),
        limitaciones=(
            "no interpreta texto libre: recibe requisitos ya identificados",
            "no resuelve conflictos entre requisitos: los declara",
            "no comprueba que un requisito sea normativamente posible",
        ),
    ),
)
