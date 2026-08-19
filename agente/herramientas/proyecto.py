# -*- coding: utf-8 -*-
"""Ajustar el programa de un proyecto generado (tarea `CP-1`, pieza ⑤ del MVP).

PRD: `docs/prd/2026-08-19-copiloto-que-modifica-el-proyecto.md`.

**Qué hace que esto NO sea `OP-8`.** `OP-8` —«modifica el proyecto y recalcula
lo que dependa»— está aplazado porque escribir en el fichero de un cliente es el
efecto más caro de equivocarse del producto. Aquí no hay ningún fichero de
nadie: se transforma el **diccionario de parámetros** con el que se generó una
alternativa, y quien regenera y persiste es la capa HTTP. Por eso
`efectos=()`: esta capacidad no toca el mundo exterior, y no pedir una
autorización que no hace falta es lo que mantiene la autorización creíble
cuando sí la pide.

**Una capacidad, no cinco.** Cambiar el mix, las plantas o la superficie
objetivo son la misma cosa —ajustar el encargo— y registrarlas por separado
llenaría el catálogo de herramientas casi idénticas, que es lo que degrada al
planificador. Con ésta el registro llega a **12**, que es el techo de `C4`: la
siguiente capacidad que alguien quiera añadir obliga a quitar otra o a mover el
techo, y las dos cosas son decisiones visibles. Eso es exactamente lo que `C4`
persigue.

**Es aritmética, no criterio.** Esta capacidad no sabe qué es un proyecto mejor.
Suma, resta y reparte viviendas entre tipos. El copiloto elige *cuál* invocar y
con qué argumentos; **cuánto vale el resultado lo dice el evaluador**, y si el
cambio empeora la métrica que se pedía mejorar, se entrega igual diciéndolo. Un
copiloto que ocultara eso estaría decidiendo qué es un buen proyecto, que es
criterio profesional y no está firmado (`D-7`).
"""
from __future__ import annotations

import copy
from typing import Any, Dict, Optional

from ..capacidad import Capacidad

#: Las tres cosas que se pueden ajustar. Catálogo cerrado a propósito: una
#: operación que no está aquí es una que el copiloto tiene que declarar que no
#: sabe hacer, en vez de aproximarla con las que sí tiene (CU-4 del PRD).
OPERACIONES = ("cambiar_mix", "cambiar_plantas", "cambiar_superficie_objetivo")

TIPOS_DE_VIVIENDA = ("dorm_1", "dorm_2", "dorm_3")


def _sin_parametros() -> Dict[str, Any]:
    return {
        "ok": False,
        "error": "sin_parametros",
        "detalle": "No he recibido los parámetros del proyecto que hay que ajustar.",
        "pregunta": "¿Sobre qué alternativa quieres el cambio?",
    }


def _viviendas(mix: Dict[str, Any]) -> int:
    return sum(int(mix.get(t) or 0) for t in TIPOS_DE_VIVIENDA)


def _cambiar_mix(mix: Dict[str, Any], argumentos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fija el número de viviendas de uno o más tipos.

    Se admiten valores absolutos (`dorm_2: 4`) y relativos (`dorm_2: "-1"`),
    porque «elimina una vivienda» es relativo y «que haya cuatro de dos
    dormitorios» es absoluto, y obligar al copiloto a convertir una en otra es
    pedirle que haga aritmética — justo lo que no debe hacer.
    """
    tocados = {}
    for tipo in TIPOS_DE_VIVIENDA:
        if tipo not in argumentos or argumentos[tipo] is None:
            continue
        crudo = argumentos[tipo]
        try:
            if isinstance(crudo, str) and crudo.strip()[:1] in ("+", "-"):
                nuevo = int(mix.get(tipo) or 0) + int(crudo)
            else:
                nuevo = int(crudo)
        except (TypeError, ValueError):
            return {
                "ok": False,
                "error": "valor_no_numerico",
                "detalle": "«%s» no es un número de viviendas válido para %s." % (crudo, tipo),
                "pregunta": "¿Cuántas viviendas de ese tipo quieres?",
            }
        if nuevo < 0:
            return {
                "ok": False,
                "error": "no_quedan_viviendas_de_ese_tipo",
                "detalle": ("El proyecto tiene %d vivienda(s) de tipo %s y se pide dejarlo "
                            "en %d." % (int(mix.get(tipo) or 0), tipo, nuevo)),
                "pregunta": "¿De qué tipo quieres quitar la vivienda?",
            }
        tocados[tipo] = nuevo

    if not tocados:
        return {
            "ok": False,
            "error": "sin_cambio_indicado",
            "detalle": "No se ha indicado ningún tipo de vivienda que cambiar.",
            "pregunta": "¿De cuántos dormitorios es la vivienda que quieres cambiar?",
        }
    mix.update(tocados)
    if _viviendas(mix) < 1:
        return {
            "ok": False,
            "error": "proyecto_sin_viviendas",
            "detalle": "El cambio dejaría el proyecto sin ninguna vivienda.",
            "pregunta": "¿Quieres reducir el número de viviendas de otro tipo en su lugar?",
        }
    return None


def ajustar_programa(parametros: Dict[str, Any], operacion: str,
                     argumentos: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Devuelve unos parámetros nuevos con el ajuste aplicado, y qué cambió.

    **Nunca muta lo que recibe.** Si la regeneración falla después, quien llamó
    conserva intactos los parámetros de la alternativa anterior — que es el
    criterio de aceptación nº5 del PRD, y la diferencia entre una modificación
    reversible y perder el trabajo del arquitecto.
    """
    if not isinstance(parametros, dict) or not parametros:
        return _sin_parametros()
    if operacion not in OPERACIONES:
        return {
            "ok": False,
            "error": "operacion_no_soportada",
            "detalle": ("«%s» no es algo que ArchMuse sepa ajustar. Sabe: %s."
                        % (operacion, ", ".join(OPERACIONES))),
            "pregunta": ("Puedo cambiar el número de viviendas por tipo, el número de "
                         "plantas o la superficie construida objetivo. ¿Cuál de las tres?"),
        }

    nuevos = copy.deepcopy(parametros)
    argumentos = dict(argumentos or {})
    antes: Dict[str, Any] = {}
    despues: Dict[str, Any] = {}

    if operacion == "cambiar_mix":
        mix = nuevos.setdefault("mix_viviendas", {})
        antes = {t: int(mix.get(t) or 0) for t in TIPOS_DE_VIVIENDA}
        fallo = _cambiar_mix(mix, argumentos)
        if fallo:
            return fallo
        despues = {t: int(mix.get(t) or 0) for t in TIPOS_DE_VIVIENDA}

    elif operacion == "cambiar_plantas":
        try:
            plantas = int(argumentos.get("plantas"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "valor_no_numerico",
                    "detalle": "«%s» no es un número de plantas." % argumentos.get("plantas"),
                    "pregunta": "¿Cuántas plantas quieres?"}
        if plantas < 1:
            return {"ok": False, "error": "plantas_fuera_de_rango",
                    "detalle": "Un edificio no puede tener menos de una planta.",
                    "pregunta": "¿Cuántas plantas quieres?"}
        edificio = nuevos.setdefault("edificio", {})
        antes = {"plantas": int(edificio.get("plantas") or 0)}
        edificio["plantas"] = plantas
        despues = {"plantas": plantas}

    else:  # cambiar_superficie_objetivo
        try:
            superficie = float(argumentos.get("superficie_objetivo_m2"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "valor_no_numerico",
                    "detalle": ("«%s» no es una superficie."
                                % argumentos.get("superficie_objetivo_m2")),
                    "pregunta": "¿Qué superficie construida objetivo quieres, en m²?"}
        if superficie <= 0:
            return {"ok": False, "error": "superficie_fuera_de_rango",
                    "detalle": "La superficie construida objetivo tiene que ser mayor que cero.",
                    "pregunta": "¿Qué superficie construida objetivo quieres, en m²?"}
        antes = {"superficie_objetivo_m2": parametros.get("superficie_objetivo_m2")}
        nuevos["superficie_objetivo_m2"] = superficie
        despues = {"superficie_objetivo_m2": superficie}

    if antes == despues:
        return {
            "ok": False,
            "error": "el_proyecto_ya_estaba_asi",
            "detalle": "El proyecto ya tiene esos valores: no hay nada que cambiar.",
            "pregunta": "¿Qué quieres que sea distinto?",
        }

    return {
        "ok": True,
        "operacion": operacion,
        "parametros": nuevos,
        "antes": antes,
        "despues": despues,
        # Lo que hay que regenerar. Se dice explícitamente para que la capa que
        # llama no tenga que deducirlo del tipo de operación: los tres ajustes
        # cambian la geometría, pero el día que haya uno que no, esto lo dirá.
        "hay_que_regenerar": True,
        "viviendas_antes": _viviendas(parametros.get("mix_viviendas") or {}),
        "viviendas_despues": _viviendas(nuevos.get("mix_viviendas") or {}),
    }


CAPACIDADES = (
    Capacidad(
        id="proyecto.ajustar_programa",
        version="1.0.0",
        dominio="proyecto",
        naturaleza="determinista",
        descripcion=(
            "Ajusta el encargo de una alternativa ya generada y devuelve los parámetros "
            "nuevos: el número de viviendas por tipo (cambiar_mix, con valores absolutos "
            "como 4 o relativos como \"-1\"), el número de plantas (cambiar_plantas) o la "
            "superficie construida objetivo (cambiar_superficie_objetivo). NO regenera ni "
            "evalúa: devuelve los parámetros para que quien llame regenere. NO decide qué "
            "es un proyecto mejor: sólo aplica el cambio pedido y dice qué cambió. Si la "
            "operación no está en el catálogo, lo dice en vez de aproximarla."
        ),
        parametros={
            "type": "object",
            "properties": {
                "parametros": {
                    "type": "object",
                    "description": ("Los parámetros con los que se generó la alternativa "
                                    "(proyecto, solar, edificio, mix_viviendas, normativa)."),
                },
                "operacion": {"type": "string", "enum": list(OPERACIONES)},
                "argumentos": {
                    "type": "object",
                    "description": (
                        "Lo que cambia. cambiar_mix: dorm_1/dorm_2/dorm_3, absolutos (4) o "
                        "relativos (\"-1\"). cambiar_plantas: plantas. "
                        "cambiar_superficie_objetivo: superficie_objetivo_m2."
                    ),
                },
            },
            "required": ["parametros", "operacion"],
            "additionalProperties": False,
        },
        funcion=ajustar_programa,
        efectos=(),
        limitaciones=(
            "no regenera ni evalúa el proyecto: devuelve los parámetros para que quien "
            "llame lo haga",
            "no decide qué es un proyecto mejor: aplica el cambio pedido y dice qué cambió",
            "no coloca estancias ni orienta piezas: el generador decide la distribución, "
            "así que no se puede pedir «el salón al sur» por esta vía",
            "no comprueba normativa: el evaluador lo hace después, sobre el proyecto "
            "regenerado",
            "no toca ningún fichero del arquitecto: trabaja sobre el encargo, no sobre un "
            "DXF",
        ),
    ),
)
