# -*- coding: utf-8 -*-
"""La fachada: un objetivo entra, trabajo con acta sale.

Es el único módulo que un llamador externo —la API, un `python -c`, un servidor
MCP, un complemento de Revit— necesita conocer. Todo lo demás (`nucleo`,
`ejecucion`, `skill`, `acta`) es maquinaria interna, y tenerla detrás de una
fachada estrecha es lo que permite cambiarla sin romper a nadie.

**El recorrido completo, que es el que Pablo describió:**

    intención → contexto → planificación → Skills → Tools → ejecución
              → observación → verificación → resultado

- **contexto**: la memoria del proyecto, que se consulta antes de nada.
- **planificación**: hoy la hace el modelo paso a paso dentro del bucle. El
  plan tipado por adelantado (`Plan`, ya construido y probado) entra cuando el
  planificador de V1-10 lo produzca; el ejecutor ya lo espera.
- **verificación**: cada Skill dictamina su propio resultado antes de entregarlo.
- **observación**: la bitácora, que además permite reanudar.
- **resultado**: texto **más** acta. Nunca solo texto.

**Dos cosas que esta fachada no deja hacer, a propósito.** No se puede pedir
trabajo sin proyecto —sin memoria no hay contexto y las Skills no sabrían contra
qué comprobar sus requisitos— y no se puede obtener un resultado sin acta.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from . import acta as _acta
from . import efectos as _efectos
from .carencias import RegistroDeCarencias
from .memoria import MemoriaDeProyecto
from .nucleo import Respuesta, ejecutar
from .registro import Registro, RegistroDeSkills, registro as _registro
from .registro import registro_de_skills as _registro_de_skills


@dataclass(frozen=True)
class Entrega:
    """Lo que se le devuelve a quien pidió el trabajo."""

    respuesta: Respuesta
    acta: _acta.Acta

    @property
    def texto(self) -> str:
        return self.respuesta.texto

    @property
    def preguntas(self) -> Tuple[str, ...]:
        return self.respuesta.preguntas

    @property
    def efectos_pendientes(self) -> Tuple[str, ...]:
        return self.respuesta.efectos_pendientes

    @property
    def fundamentada(self) -> bool:
        """Ninguna cifra del texto sale de fuera de las herramientas."""
        return self.respuesta.fundamentada

    def a_dict(self) -> dict:
        return {
            "texto": self.texto,
            "acta": self.acta.a_dict(),
            "preguntas": list(self.preguntas),
            "efectos_pendientes": list(self.efectos_pendientes),
            "fundamentada": self.fundamentada,
            "cifras_sin_respaldo": list(self.respuesta.cifras_sin_respaldo),
        }


def atender(objetivo: str, cliente: Any, memoria: MemoriaDeProyecto, *,
            autorizaciones: Optional[_efectos.Autorizaciones] = None,
            capacidades: Optional[Registro] = None,
            skills: Optional[RegistroDeSkills] = None,
            carencias: Optional[RegistroDeCarencias] = None,
            ejecucion_id: str = "",
            **opciones) -> Entrega:
    """Atiende un objetivo profesional y devuelve el trabajo con su acta.

    `carencias`, si se pasa, registra los objetivos que no se han sabido
    atender. La señal se anota **solo cuando no se ejecutó ninguna Skill**: si
    alguna se ejecutó, el objetivo estaba cubierto aunque el resultado fuera
    parcial, y contarlo como carencia produciría ruido en vez de señal.
    """
    capacidades = capacidades if capacidades is not None else _registro()
    skills = skills if skills is not None else _registro_de_skills()
    ejecucion_id = ejecucion_id or ("ej-%s" % uuid.uuid4().hex[:12])

    respuesta = ejecutar(
        objetivo, cliente,
        reg=capacidades, skills=skills, memoria=memoria,
        autorizaciones=autorizaciones, ejecucion_id=ejecucion_id, **opciones,
    )

    if carencias is not None and not respuesta.pasos_de_skill:
        carencias.anotar(objetivo)

    documento = _acta.levantar(
        _resultado_sintetico(objetivo, memoria, ejecucion_id, respuesta),
        capacidades=capacidades, skills=skills,
    )
    return Entrega(respuesta=respuesta, acta=documento)


def _resultado_sintetico(objetivo: str, memoria: MemoriaDeProyecto,
                         ejecucion_id: str, respuesta: Respuesta):
    """Envuelve lo que hizo el bucle en la forma que el acta sabe leer.

    El acta se escribió contra `ResultadoDeEjecucion` —lo que produce un plan— y
    aquí lo que hay son Skills invocadas sobre la marcha. En vez de darle al
    acta un segundo camino de entrada (que es como acaban divergiendo las dos
    formas de contar lo mismo), se reconstruye el plan equivalente a lo que
    acabó ejecutándose.
    """
    from .ejecucion import Paso, Plan, ResultadoDeEjecucion

    pasos_del_plan = tuple(
        Paso(id=p.paso_id, skill=p.skill) for p in respuesta.pasos_de_skill
    )
    plan = Plan(objetivo=objetivo, proyecto_id=memoria.proyecto_id, pasos=pasos_del_plan)
    return ResultadoDeEjecucion(
        ejecucion_id=ejecucion_id, plan=plan, pasos=respuesta.pasos_de_skill
    )
