# -*- coding: utf-8 -*-
"""La fachada: un objetivo entra, trabajo con acta sale.

Es el único módulo que un llamador externo —la API, un `python -c`, un servidor
MCP, un complemento de Revit— necesita conocer. Todo lo demás (`nucleo`,
`planificador`, `ejecucion`, `skill`, `acta`) es maquinaria interna, y tenerla
detrás de una fachada estrecha es lo que permite cambiarla sin romper a nadie.

**El recorrido completo, que es el que Pablo describió:**

    intención → contexto → planificación → Skills → Tools → ejecución
              → observación → verificación → resultado

- **contexto**: la memoria del proyecto, que se consulta antes de nada.
- **planificación**: hay **dos vías**, y no son intercambiables (ver abajo).
- **verificación**: cada Skill dictamina su propio resultado antes de entregarlo.
- **observación**: la bitácora, que además permite reanudar.
- **resultado**: texto **más** acta. Nunca solo texto.

**Las dos vías, y por qué conviven.**

- `VIA_BUCLE` — el modelo decide paso a paso dentro de `nucleo.ejecutar`. Es lo
  que había, sigue probado, y sigue siendo el que mejor se defiende cuando la
  petición es una conversación («apunta que quieren cuatro dormitorios»).
- `VIA_PLAN` — `planificador.planificar` produce un DAG de una sola llamada,
  `planificador.revisar` lo audita **sin gastar un token ni tocar un fichero**,
  y `ejecucion.Ejecutor` lo ejecuta. Es la única de las dos que **se puede
  enseñar antes de tocar nada**: un bucle no tiene forma hasta que ha
  terminado, así que no se puede parar; un plan sí.

El defecto por defecto es `VIA_BUCLE`, y es una decisión conservadora, no una
preferencia: cambiar el defecto cambia el comportamiento de todo llamador
existente, y esa decisión se toma con datos de uso (`AG-3`), no de golpe. Lo
que sí cambia hoy es que la vía del plan **existe desde la fachada**, que es lo
que faltaba: estaba construida, probada y no la alcanzaba nadie.

**Enseñar el plan antes de ejecutar efectos** es lo que hacen `proponer()` y
`ejecutar_propuesta()`, que son la misma vía partida en dos. `proponer()` no
ejecuta, no escribe y no autoriza nada: devuelve el plan, las preguntas que le
faltan y **qué efectos habrá que autorizar**. Enterarse de que algo escribe un
fichero después de que lo haya escrito no sirve de nada.

**Un solo reintento, y el segundo fallo es una pregunta** (`AG-4`). Si tras
ejecutar hay algo que otro plan podría arreglar, se replanifica **una vez** con
lo observado a la vista y se vuelve a ejecutar reutilizando el mismo
`ejecucion_id`, así que lo que ya salió bien no se repite. Nunca un tercer
intento, nunca para esquivar una autorización, y nunca un plan idéntico al que
acaba de no funcionar.

**Dos cosas que esta fachada no deja hacer, a propósito.** No se puede pedir
trabajo sin proyecto —sin memoria no hay contexto y las Skills no sabrían contra
qué comprobar sus requisitos— y no se puede obtener un resultado sin acta.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from typing import Any, Callable, List, Optional, Tuple

from . import acta as _acta
from . import efectos as _efectos
from . import planificador as _planificador
from .carencias import RegistroDeCarencias
from .ejecucion import (
    Bitacora,
    Ejecutor,
    FALLIDO,
    HECHO,
    NO_EJECUTADO,
    PENDIENTE_DE_AUTORIZACION,
    PENDIENTE_DE_DATOS,
    Plan,
    ResultadoDeEjecucion,
)
from .memoria import MemoriaDeProyecto
from .nucleo import Respuesta, ejecutar
from .registro import Registro, RegistroDeSkills, registro as _registro
from .registro import registro_de_skills as _registro_de_skills
from .respaldo import sin_respaldo

#: Las dos vías. Cadenas y no un `Enum` porque viajan a un JSON de la API sin
#: traducción, y porque el valor es lo que se lee en una traza.
VIA_BUCLE = "bucle"
VIA_PLAN = "plan"
VIAS = (VIA_BUCLE, VIA_PLAN)

#: Cuántas veces se replanifica como mucho (`AG-4`). **Uno, y el techo es
#: duro**: `atender` lo recorta a este valor aunque le pidan cinco. No es
#: cautela, es el diseño de la tarea — «si tras replanificar sigue faltando, se
#: para y se pregunta; nunca un tercer intento». Un parámetro que admitiera
#: cinco es cómo se consigue un agente que se come el presupuesto dando vueltas
#: y entrega media respuesta como si fuera entera.
MAX_REPLANIFICACIONES = 1

#: Estados de paso que **otro plan podría arreglar**: un fallo técnico o un dato
#: que quizá otra Skill sepa conseguir (consultar Catastro en vez de preguntar
#: el municipio). `NO_EJECUTADO` entra porque su causa está aguas arriba.
ARREGLABLES_REPLANIFICANDO = (FALLIDO, PENDIENTE_DE_DATOS, NO_EJECUTADO)


class ViaDesconocida(ValueError):
    """Se pidió una vía que no existe. Se rechaza antes de gastar nada."""


@dataclass(frozen=True)
class Propuesta:
    """Lo que ArchMuse **va a hacer**, antes de haber hecho nada.

    Es la razón de ser de la vía del plan: lo que no se puede enseñar no se
    puede parar. Contiene las tres cosas que hay que saber antes de decir que
    sí —qué pasos, qué falta por contestar, y qué efectos habrá que autorizar—
    y ninguna de las tres exige haber ejecutado nada para conocerse.

    Lleva dentro los registros con los que se planificó, y no es un detalle:
    ejecutar la propuesta contra un catálogo distinto del que se le enseñó al
    arquitecto sería enseñar una cosa y hacer otra.
    """

    objetivo: str
    ejecucion_id: str
    planificacion: _planificador.Planificacion
    revision: _planificador.Revision
    capacidades: Registro = field(repr=False, compare=False, default=None)  # type: ignore[assignment]
    skills: RegistroDeSkills = field(repr=False, compare=False, default=None)  # type: ignore[assignment]

    @property
    def plan(self) -> Optional[Plan]:
        return self.planificacion.plan

    @property
    def ejecutable(self) -> bool:
        """Hay algo que ejecutar y nada que lo impida.

        **Las preguntas no lo impiden**: cada Skill se detiene sola en su paso y
        devuelve la suya, y los pasos que sí tienen sus datos se hacen igual.
        Negarse a empezar convierte un informe parcial —útil— en ningún informe.
        """
        return self.planificacion.ejecutable and self.revision.ejecutable

    @property
    def motivos(self) -> Tuple[str, ...]:
        """Por qué este plan no se puede ejecutar. No se arregla contestando."""
        return tuple(dict.fromkeys(
            tuple(self.planificacion.motivos) + tuple(self.revision.motivos)))

    @property
    def preguntas(self) -> Tuple[str, ...]:
        return self.revision.preguntas

    @property
    def efectos_a_autorizar(self) -> Tuple[str, ...]:
        return self.revision.efectos_a_autorizar

    def falta_autorizar(
        self, autorizaciones: Optional[_efectos.Autorizaciones] = None
    ) -> Tuple[str, ...]:
        """De los efectos del plan, los que **nadie ha autorizado todavía**.

        Es lo que hay que enseñar en la pantalla de confirmación: la lista
        entera de efectos incluye los ya concedidos, y mezclarlas haría que el
        arquitecto autorizara dos veces lo mismo o dejara de mirar la lista.
        """
        autorizaciones = autorizaciones if autorizaciones is not None else _efectos.NINGUNA
        return tuple(autorizaciones.faltan(self.efectos_a_autorizar))

    def texto(self, autorizaciones: Optional[_efectos.Autorizaciones] = None) -> str:
        """El plan como se le enseña al arquitecto **antes** de ejecutarlo."""
        # La lista de efectos la escribe esta clase y no el planificador: aquí
        # se sabe además cuáles ya están autorizados, y allí no.
        cuerpo = _planificador.a_texto(self.planificacion, self.skills,
                                       con_efectos=False)
        lineas: List[str] = [cuerpo]
        if self.revision.motivos and self.planificacion.ejecutable:
            # `a_texto` sólo conoce los motivos del planificador; los de la
            # revisión (capacidad retirada, versión incompatible) son otros.
            lineas += ["", "NO SE PUEDE EJECUTAR ESTE PLAN:"]
            lineas += ["  · %s" % m for m in self.revision.motivos]
        if self.preguntas:
            lineas += ["", "PARA PODER TERMINARLO HAY QUE CONTESTAR:"]
            lineas += ["  · %s" % p for p in self.preguntas]
        pendientes = self.falta_autorizar(autorizaciones)
        if pendientes:
            lineas += ["", "HAY QUE AUTORIZAR ANTES DE SEGUIR:"]
            lineas += [
                "  · %s — %s" % (e, _efectos.DESCRIPCIONES.get(e, e)) for e in pendientes
            ]
        # Un efecto ya concedido se sigue diciendo. Que desaparezca de la
        # pantalla en cuanto se autoriza es cómo el arquitecto acaba sin saber
        # qué va a tocar su ordenador: lo autorizó una vez, hace tres pasos.
        concedidos = [e for e in self.efectos_a_autorizar if e not in pendientes]
        if concedidos:
            lineas += ["", "YA AUTORIZADO, Y AUN ASÍ VA A PASAR:"]
            lineas += [
                "  · %s — %s" % (e, _efectos.DESCRIPCIONES.get(e, e)) for e in concedidos
            ]
        return "\n".join(lineas)

    def a_dict(self) -> dict:
        return {
            "objetivo": self.objetivo,
            "ejecucion_id": self.ejecucion_id,
            "planificacion": self.planificacion.a_dict(),
            "revision": self.revision.a_dict(),
            "ejecutable": self.ejecutable,
            "motivos": list(self.motivos),
            "preguntas": list(self.preguntas),
            "efectos_a_autorizar": list(self.efectos_a_autorizar),
            "texto": self.texto(),
        }


@dataclass(frozen=True)
class Entrega:
    """Lo que se le devuelve a quien pidió el trabajo."""

    respuesta: Respuesta
    acta: _acta.Acta
    #: El plan que se enseñó antes de ejecutar, si se fue por la vía del plan.
    #: `None` por la vía del bucle: allí no hay plan que enseñar, y decir que
    #: sí lo hay sería exactamente la ilusión que la vía del plan existe para
    #: no dar.
    propuesta: Optional[Propuesta] = None
    #: Todos los planes que se propusieron, en orden, siendo el último el que
    #: se ejecutó. Con un solo elemento salvo que haya habido replanificación
    #: (`AG-4`). Se guardan los dos porque «lo intentó de otra forma» es
    #: información del arquitecto, no traza interna: explica por qué la
    #: respuesta tardó el doble y por qué el plan que ve no es el que se
    #: enseñó primero.
    intentos: Tuple[Propuesta, ...] = field(default_factory=tuple)

    @property
    def replanificado(self) -> bool:
        return len(self.intentos) > 1

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
            "plan": self.propuesta.a_dict() if self.propuesta is not None else None,
            # Lo que el modelo NO llegó a ver por tamaño. Vacío en el caso
            # normal; cuando no lo está, es la primera cosa que hay que mirar
            # antes de creerse una respuesta corta.
            "recortes": list(self.respuesta.recortes),
            "parada": self.respuesta.parada,
            "replanificado": self.replanificado,
            "planes_propuestos": [p.a_dict() for p in self.intentos],
        }


# --- Fase 1: proponer, sin tocar nada ---------------------------------------

def proponer(objetivo: str, cliente: Any, memoria: MemoriaDeProyecto, *,
             capacidades: Optional[Registro] = None,
             skills: Optional[RegistroDeSkills] = None,
             carencias: Optional[RegistroDeCarencias] = None,
             ejecucion_id: str = "",
             **opciones) -> Propuesta:
    """Planifica y audita **sin ejecutar nada**. Una llamada al modelo y ni una
    escritura.

    Es la mitad que hace posible la confirmación: el arquitecto ve el plan, las
    preguntas y los efectos, y decide. Lo que devuelve es lo que se ejecutará
    después *exactamente*, porque `ejecutar_propuesta` no vuelve a planificar.

    `opciones` se le pasan a `planificador.planificar` (`modelo`, `max_pasos`,
    `max_tokens`, `sistema`, y `observacion` cuando se replanifica). No hay
    ninguna que active la ejecución: para eso está la otra función, y que sean
    dos es la garantía.
    """
    capacidades = capacidades if capacidades is not None else _registro()
    skills = skills if skills is not None else _registro_de_skills()
    ejecucion_id = ejecucion_id or _nuevo_id()

    planificacion = _planificador.planificar(
        objetivo, cliente, memoria=memoria, capacidades=capacidades,
        skills=skills, carencias=carencias, **opciones,
    )
    plan = planificacion.plan
    if plan is None or not plan.pasos:
        revision = _planificador.Revision()
    else:
        revision = _planificador.revisar(
            plan, skills=skills, capacidades=capacidades, memoria=memoria)

    return Propuesta(
        objetivo=objetivo, ejecucion_id=ejecucion_id,
        planificacion=planificacion, revision=revision,
        capacidades=capacidades, skills=skills,
    )


# --- Fase 2: ejecutar lo que se enseñó --------------------------------------

def ejecutar_propuesta(propuesta: Propuesta, memoria: MemoriaDeProyecto, *,
                       autorizaciones: Optional[_efectos.Autorizaciones] = None,
                       bitacora: Optional[Bitacora] = None,
                       confirmar: Optional[Callable[[Propuesta], bool]] = None,
                       ) -> Entrega:
    """Ejecuta el plan que ya se enseñó, y **sólo** ese.

    No replanifica, no reinterpreta el objetivo y no toca el catálogo: usa los
    registros que viajan dentro de la propuesta. Un segundo camino hacia el
    mismo trabajo es exactamente cómo se consiguen dos comportamientos
    distintos ante el mismo error.

    `confirmar`, si se pasa, recibe la propuesta y decide. Devolver algo falso
    **no ejecuta nada**: ni un paso, ni el primero, ni el que no tiene efectos.
    Es el gancho por el que una pantalla —o un `input()`— se enchufa sin que
    esta fachada sepa que existe una pantalla.
    """
    capacidades = propuesta.capacidades or _registro()
    skills = propuesta.skills or _registro_de_skills()
    plan = propuesta.plan

    if plan is None or propuesta.motivos:
        return _entrega_sin_ejecutar(propuesta, memoria, capacidades, skills,
                                     parada="plan_invalido")
    if not plan.pasos:
        return _entrega_sin_ejecutar(propuesta, memoria, capacidades, skills,
                                     parada="plan_vacio")
    if confirmar is not None and not confirmar(propuesta):
        return _entrega_sin_ejecutar(propuesta, memoria, capacidades, skills,
                                     parada="no_confirmado")

    resultado = Ejecutor(
        capacidades=capacidades, skills=skills, bitacora=bitacora,
    ).ejecutar(plan, memoria, ejecucion_id=propuesta.ejecucion_id,
               autorizaciones=autorizaciones)

    respuesta = _respuesta_de(resultado, skills)
    documento = _acta.levantar(resultado, capacidades=capacidades, skills=skills)
    return Entrega(respuesta=respuesta, acta=documento, propuesta=propuesta,
                   intentos=(propuesta,))


# --- La fachada de siempre --------------------------------------------------

def atender(objetivo: str, cliente: Any, memoria: MemoriaDeProyecto, *,
            autorizaciones: Optional[_efectos.Autorizaciones] = None,
            capacidades: Optional[Registro] = None,
            skills: Optional[RegistroDeSkills] = None,
            carencias: Optional[RegistroDeCarencias] = None,
            ejecucion_id: str = "",
            via: str = VIA_BUCLE,
            bitacora: Optional[Bitacora] = None,
            confirmar: Optional[Callable[[Propuesta], bool]] = None,
            max_replanificaciones: int = MAX_REPLANIFICACIONES,
            **opciones) -> Entrega:
    """Atiende un objetivo profesional y devuelve el trabajo con su acta.

    `via` elige entre las dos formas de decidir qué hacer (ver el docstring del
    módulo). `VIA_PLAN` es `proponer()` seguido de `ejecutar_propuesta()` en un
    solo paso; si hay que enseñar el plan y esperar, se llaman las dos por
    separado, o se pasa `confirmar`.

    `carencias`, si se pasa, registra los objetivos que no se han sabido
    atender. Por la vía del bucle la señal se anota **solo cuando no se ejecutó
    ninguna Skill**: si alguna se ejecutó, el objetivo estaba cubierto aunque el
    resultado fuera parcial, y contarlo como carencia produciría ruido en vez de
    señal. Por la vía del plan lo anota el propio planificador cuando el plan
    sale vacío, y por eso aquí no se anota otra vez.

    `opciones` van a la vía elegida y no son las mismas: `max_iteraciones` sólo
    existe en el bucle, `max_pasos` sólo en el plan.

    `max_replanificaciones` sólo cuenta por la vía del plan, y su techo es duro
    (`MAX_REPLANIFICACIONES`): pedir cinco da uno. Ver `_atender_con_plan`.
    """
    if via not in VIAS:
        raise ViaDesconocida(
            "vía «%s» desconocida; las que hay son %s" % (via, list(VIAS)))

    capacidades = capacidades if capacidades is not None else _registro()
    skills = skills if skills is not None else _registro_de_skills()
    ejecucion_id = ejecucion_id or _nuevo_id()

    if via == VIA_PLAN:
        return _atender_con_plan(
            objetivo, cliente, memoria, autorizaciones=autorizaciones,
            capacidades=capacidades, skills=skills, carencias=carencias,
            ejecucion_id=ejecucion_id, bitacora=bitacora, confirmar=confirmar,
            max_replanificaciones=max_replanificaciones, **opciones,
        )

    respuesta = ejecutar(
        objetivo, cliente,
        reg=capacidades, skills=skills, memoria=memoria,
        autorizaciones=autorizaciones, ejecucion_id=ejecucion_id,
        bitacora=bitacora, **opciones,
    )

    if carencias is not None and not respuesta.pasos_de_skill:
        carencias.anotar(objetivo)

    documento = _acta.levantar(
        _resultado_sintetico(objetivo, memoria, ejecucion_id, respuesta),
        capacidades=capacidades, skills=skills,
    )
    return Entrega(respuesta=respuesta, acta=documento)


# --- La vía del plan, con su único reintento (AG-4) -------------------------

def _atender_con_plan(objetivo: str, cliente: Any, memoria: MemoriaDeProyecto, *,
                      autorizaciones: Optional[_efectos.Autorizaciones],
                      capacidades: Registro, skills: RegistroDeSkills,
                      carencias: Optional[RegistroDeCarencias],
                      ejecucion_id: str, bitacora: Optional[Bitacora],
                      confirmar: Optional[Callable[[Propuesta], bool]],
                      max_replanificaciones: int,
                      **opciones) -> Entrega:
    """Planifica, ejecuta y —si otro plan pudiera arreglarlo— replanifica **una vez**.

    **El segundo fallo es una pregunta, no un tercer intento.** El techo está
    en `MAX_REPLANIFICACIONES` y se recorta aquí aunque pidan más: un agente que
    puede dar cinco vueltas se come el presupuesto y entrega media respuesta
    como si fuera entera.

    **Nunca se replanifica para esquivar una autorización.** Si algún paso quedó
    `PENDIENTE_DE_AUTORIZACION`, se para y se pide el permiso. Buscar otra ruta
    que no necesite el permiso que acaban de no darte es la única cosa que este
    sistema no puede hacer nunca, y es una regla, no una heurística.

    **La segunda ejecución reutiliza el mismo `ejecucion_id`**, así que la
    reanudación de `Ejecutor` no repite lo que ya salió bien — ni lo recalcula,
    ni lo vuelve a cobrar, ni vuelve a escribir un fichero. Que eso sea seguro
    depende de que un paso se reconozca por su Skill y sus argumentos y no sólo
    por su id (`ejecucion._es_el_mismo_paso`); sin eso, un segundo plan que
    reutilizara el id «ficha» para otra cosa se habría llevado el resultado viejo.
    """
    techo = max(0, min(int(max_replanificaciones), MAX_REPLANIFICACIONES))

    propuesta = proponer(objetivo, cliente, memoria, capacidades=capacidades,
                         skills=skills, carencias=carencias,
                         ejecucion_id=ejecucion_id, **opciones)
    entrega = ejecutar_propuesta(propuesta, memoria, autorizaciones=autorizaciones,
                                 bitacora=bitacora, confirmar=confirmar)
    intentos: List[Propuesta] = [propuesta]

    for _ in range(techo):
        if not _replanificar_ayudaria(entrega):
            break
        otra = proponer(objetivo, cliente, memoria, capacidades=capacidades,
                        skills=skills, carencias=carencias,
                        ejecucion_id=ejecucion_id,
                        observacion=_lo_que_paso(entrega), **opciones)
        # Un plan idéntico al que acaba de no funcionar no se ejecuta: no hay
        # nada nuevo que pueda salir de él, y sí una factura. Se conserva la
        # entrega anterior, que ya trae las preguntas concretas.
        if _mismo_plan(propuesta, otra):
            break
        intentos.append(otra)
        entrega = ejecutar_propuesta(otra, memoria, autorizaciones=autorizaciones,
                                     bitacora=bitacora, confirmar=confirmar)
        propuesta = otra

    return replace(entrega, intentos=tuple(intentos))


def _replanificar_ayudaria(entrega: Entrega) -> bool:
    """Si un plan distinto tendría alguna posibilidad de arreglar esto.

    Tres noes, y los tres son de no gastar por gastar: si salió todo, si el
    plan ni siquiera llegó a ejecutarse (vacío, rechazado, no confirmado), o si
    lo que falta es un permiso.
    """
    if entrega.respuesta.parada != "fin":
        return False
    pasos = entrega.respuesta.pasos_de_skill
    if not pasos:
        return False
    if any(p.estado == PENDIENTE_DE_AUTORIZACION for p in pasos):
        return False
    return any(p.estado in ARREGLABLES_REPLANIFICANDO for p in pasos)


def _mismo_plan(uno: Propuesta, otro: Propuesta) -> bool:
    """Dos propuestas con los mismos pasos, los mismos argumentos y el mismo orden."""
    a = uno.plan.a_dict()["pasos"] if uno.plan is not None else None
    b = otro.plan.a_dict()["pasos"] if otro.plan is not None else None
    return a == b


def _lo_que_paso(entrega: Entrega) -> str:
    """Lo observado al ejecutar, para que el planificador pueda rodearlo.

    **Se deriva de los pasos, no lo redacta un modelo.** Si esto lo escribiera
    una llamada intermedia, el segundo plan se estaría construyendo sobre un
    resumen y no sobre lo que pasó, que es exactamente el hueco por el que
    entra un dato que nadie midió.
    """
    pasos = entrega.respuesta.pasos_de_skill
    lineas: List[str] = ["ESTO YA SE HA INTENTADO. Lo que pasó al ejecutarlo:", ""]

    hechos = [p for p in pasos if p.estado == HECHO]
    if hechos:
        lineas.append("YA HECHO — consérvalo con el MISMO id de paso y los mismos "
                      "argumentos, o se repetirá el trabajo:")
        lineas += ["  · [%s] %s" % (p.paso_id, p.skill) for p in hechos]
        lineas.append("")

    fallidos = [p for p in pasos if p.estado != HECHO]
    if fallidos:
        lineas.append("NO HA SALIDO, Y POR QUÉ:")
        lineas += ["  · [%s] %s — %s: %s" % (p.paso_id, p.skill, p.estado,
                                             p.motivo or "sin motivo")
                   for p in fallidos]
        lineas.append("")

    if entrega.preguntas:
        lineas.append("LO QUE HARÍA FALTA SABER:")
        lineas += ["  · %s" % q for q in entrega.preguntas]
        lineas.append("")

    lineas.append(
        "Propón un plan que consiga esto por OTRA vía, si existe: otra Skill que "
        "obtenga el dato que falta, u otro orden. Si no existe otra vía, devuelve "
        "un plan VACÍO con el motivo — repetir el mismo plan sólo gasta dinero y "
        "devuelve el mismo resultado."
    )
    return "\n".join(lineas)


# --- Auxiliares -------------------------------------------------------------

def _nuevo_id() -> str:
    return "ej-%s" % uuid.uuid4().hex[:12]


def _resultado_sintetico(objetivo: str, memoria: MemoriaDeProyecto,
                         ejecucion_id: str, respuesta: Respuesta):
    """Envuelve lo que hizo el bucle en la forma que el acta sabe leer.

    El acta se escribió contra `ResultadoDeEjecucion` —lo que produce un plan— y
    aquí lo que hay son Skills invocadas sobre la marcha. En vez de darle al
    acta un segundo camino de entrada (que es como acaban divergiendo las dos
    formas de contar lo mismo), se reconstruye el plan equivalente a lo que
    acabó ejecutándose.
    """
    from .ejecucion import Paso, Plan as _Plan

    pasos_del_plan = tuple(
        Paso(id=p.paso_id, skill=p.skill) for p in respuesta.pasos_de_skill
    )
    plan = _Plan(objetivo=objetivo, proyecto_id=memoria.proyecto_id,
                 pasos=pasos_del_plan)
    return ResultadoDeEjecucion(
        ejecucion_id=ejecucion_id, plan=plan, pasos=respuesta.pasos_de_skill
    )


def _entrega_sin_ejecutar(propuesta: Propuesta, memoria: MemoriaDeProyecto,
                          capacidades: Registro, skills: RegistroDeSkills,
                          *, parada: str) -> Entrega:
    """La entrega de un plan que no se llegó a ejecutar. **También lleva acta.**

    Un plan vacío, uno rechazado y uno que el arquitecto no confirmó son tres
    cosas distintas, y las tres son resultados legítimos: ninguna es un fallo
    del que se pueda salir devolviendo `None`. El acta de las tres dice lo
    mismo con exactitud —no se ejecutó nada— y por eso `completa` es falso.
    """
    plan = propuesta.plan or Plan(objetivo=propuesta.objetivo,
                                  proyecto_id=memoria.proyecto_id)
    resultado = ResultadoDeEjecucion(
        ejecucion_id=propuesta.ejecucion_id, plan=plan, pasos=())
    respuesta = Respuesta(
        texto=propuesta.texto(),
        iteraciones=1,
        parada=parada,
        preguntas=propuesta.preguntas,
        efectos_pendientes=propuesta.efectos_a_autorizar,
    )
    documento = _acta.levantar(resultado, capacidades=capacidades, skills=skills)
    return Entrega(respuesta=respuesta, acta=documento, propuesta=propuesta,
                   intentos=(propuesta,))


def _respuesta_de(resultado: ResultadoDeEjecucion,
                  skills: RegistroDeSkills) -> Respuesta:
    """Convierte lo ejecutado en la `Respuesta` que la fachada devuelve.

    **El texto no lo escribe un modelo: se deriva de lo que pasó.** Por la vía
    del plan no hay una llamada de redacción al final, y no hacerla es lo que
    hace imposible que aparezca una cifra que ninguna herramienta produjo. El
    detector de `respaldo.py` se ejecuta igual —no porque haga falta, sino
    porque el día que alguien meta prosa generada aquí, saltará.
    """
    lineas: List[str] = ["OBJETIVO: %s" % resultado.plan.objetivo, ""]
    lineas.append("LO QUE SE HA HECHO")
    hechos = [p for p in resultado.pasos if p.estado == HECHO]
    if not hechos:
        lineas.append("  · nada")
    for paso in hechos:
        aviso = (" — %s" % paso.motivo) if paso.motivo else ""
        lineas.append("  · [%s] %s%s" % (paso.paso_id, paso.skill, aviso))

    if resultado.no_hecho:
        lineas += ["", "LO QUE NO SE HA HECHO"]
        lineas += ["  · %s" % n for n in resultado.no_hecho]
    if resultado.preguntas:
        lineas += ["", "PARA PODER TERMINARLO HAY QUE CONTESTAR"]
        lineas += ["  · %s" % p for p in resultado.preguntas]
    if resultado.efectos_pendientes:
        lineas += ["", "HAY QUE AUTORIZAR ANTES DE SEGUIR"]
        lineas += [
            "  · %s — %s" % (e, _efectos.DESCRIPCIONES.get(e, e))
            for e in resultado.efectos_pendientes
        ]
    texto = "\n".join(lineas)

    limitaciones: List[str] = []
    for paso in resultado.pasos:
        try:
            limitaciones.extend(skills.buscar(paso.skill).limitaciones)
        except Exception:  # noqa: BLE001 - una etiqueta no rompe una respuesta
            continue

    # El respaldo es lo que realmente ocurrió: el plan y cada paso tal como
    # quedó sellado en la bitácora. Comparar contra otra cosa haría que el
    # resultado no significara nada.
    piezas: List[Any] = [resultado.plan.a_dict()]
    piezas.extend(p.a_dict() for p in resultado.pasos)

    return Respuesta(
        texto=texto,
        iteraciones=1,
        parada="fin",
        cifras_sin_respaldo=sin_respaldo(texto, piezas),
        limitaciones=tuple(dict.fromkeys(limitaciones)),
        pasos_de_skill=resultado.pasos,
        preguntas=resultado.preguntas,
        efectos_pendientes=resultado.efectos_pendientes,
    )
