# -*- coding: utf-8 -*-
"""Una llamada, un DAG validado (tarea `AG-1`).

PRD aprobado por Pablo el 2026-08-19
(`docs/prd/2026-08-19-planificador-tipado.md`), con una condición textual:
**mantenerlo deliberadamente pequeño**. Ni framework de agentes, ni LangGraph,
ni otro orquestador. Este módulo hace tres cosas y ninguna más:

1. Compone el prompt: prefijo estable de manifiestos (`agente/contexto.py`) +
   estado del proyecto + intención. En ese orden y sin mezclar, que es lo que
   hace que la caché acierte.
2. Hace **una** llamada al modelo con la herramienta forzada.
3. Traduce la respuesta a un `Plan` y lo valida. Si no vale, lo rechaza con el
   motivo concreto y **sin ejecutar nada**.

**Lo que NO hace, y es la mitad del diseño.** No ejecuta —eso es
`agente/ejecucion.py`—, no reintenta salvo el caso único de §6 del PRD, no
observa resultados, no replanifica (eso es `AG-4`) y no decide autorizaciones.
Cualquier añadido que empiece a parecerse a un bucle de agente va en otro sitio
o no va.

**Por qué un plan y no el bucle que ya existe.** `agente/nucleo.py` funciona y
se queda. Lo que un bucle no puede hacer es enseñarse: no tiene forma hasta que
ha terminado, así que el arquitecto no puede verlo antes ni pararlo, y no hay
manera de sumar el coste por adelantado. Un plan sí. Ésa es toda la diferencia,
y es de producto, no de ingeniería.

**El plan vacío no es un error.** Es la respuesta correcta a «calcula la
estructura del forjado»: ArchMuse no sabe hacer eso. Se devuelve vacío con el
motivo y se anota como carencia — lo que falta se mide por uso real, no por
intuición de quien programa.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import contexto as _contexto
from .ejecucion import Paso, Plan
from .memoria import MemoriaDeProyecto
from .registro import Registro, RegistroDeSkills
from ia import modelos

#: El perfil de modelo. Planificar es elegir entre pocas opciones bien
#: descritas: no hace falta el modelo más caro, y `AG-3` lo decidirá midiendo.
PERFIL = "planificacion"

#: Techo de pasos. Un plan de cuarenta pasos no lo ha pedido nadie: es un
#: modelo perdido, y ejecutarlo cuesta dinero real.
MAX_PASOS = 12

MAX_TOKENS = 2048

NOMBRE_HERRAMIENTA = "proponer_plan"

SISTEMA = """\
Eres el planificador de ArchMuse, una herramienta para arquitectos españoles.

Tu ÚNICO trabajo es proponer un plan: qué procedimientos (Skills) hay que
ejecutar, en qué orden y con qué argumentos. NO ejecutas nada, no calculas
nada y no respondes al arquitecto: eso lo hace el ejecutor después.

Reglas, y no son negociables:

1. Usa SOLO las Skills del catálogo, por su identificador exacto. Si ninguna
   cubre lo que se pide, devuelve un plan VACÍO con el motivo. Un plan
   aproximado con las Skills que sí hay es peor que ninguno: produce trabajo
   que nadie pidió y respuestas que parecen ciertas.
2. Cada Skill trae escrito CUÁNDO NO usarla. Léelo: es más importante que su
   objetivo.
3. Si la petición es ambigua, devuelve un plan vacío con la pregunta que la
   desambigua. No elijas por el arquitecto.
4. El estado del proyecto te dice qué datos hay. Si a una Skill le falta un
   requisito, inclúyela igual: el ejecutor devolverá la pregunta concreta. Lo
   que no puedes es inventarte el dato en los argumentos.
5. Un paso depende de otro SOLO si necesita su resultado. Los pasos
   independientes se declaran independientes: es lo que permite ejecutarlos a
   la vez.
"""


class PlanificacionInvalida(Exception):
    """El modelo devolvió algo que no es un plan utilizable."""


def esquema_de_la_herramienta(max_pasos: int = MAX_PASOS) -> Dict[str, Any]:
    """La única herramienta que se le ofrece al planificador.

    Fija y no generada del registro: lo que varía entre ejecuciones son las
    Skills disponibles, y ésas van en el prefijo cacheado, no aquí. Si el
    esquema cambiara con cada catálogo, la caché no acertaría nunca.
    """
    return {
        "name": NOMBRE_HERRAMIENTA,
        "description": (
            "Propone el plan de trabajo. Devuelve `pasos` vacío y un `motivo` si "
            "ninguna Skill del catálogo cubre lo que se pide, o si la petición es "
            "ambigua."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pasos": {
                    "type": "array",
                    "maxItems": max_pasos,
                    "items": {
                        "type": "object",
                        "required": ["id", "skill"],
                        "additionalProperties": False,
                        "properties": {
                            "id": {"type": "string",
                                   "description": "Identificador corto y único dentro del plan."},
                            "skill": {"type": "string",
                                      "description": ("Identificador exacto de una Skill del "
                                                      "catálogo. Puede llevar @version.")},
                            "argumentos": {"type": "object",
                                           "description": "Los que declare el manifiesto de la Skill."},
                            "depende_de": {"type": "array", "items": {"type": "string"},
                                           "description": ("Ids de pasos cuyo resultado necesita "
                                                           "ESTE paso. Vacío si es independiente.")},
                        },
                    },
                },
                "motivo": {
                    "type": "string",
                    "description": ("Por qué el plan está vacío, o qué pregunta lo "
                                    "desbloquearía. Obligatorio si `pasos` está vacío."),
                },
            },
            "required": ["pasos"],
            "additionalProperties": False,
        },
    }


@dataclass(frozen=True)
class Planificacion:
    """El resultado de planificar. Nunca un `Plan` suelto.

    Las tres salidas posibles son distintas y ninguna puede confundirse con
    otra: un plan ejecutable, un plan vacío con motivo (ArchMuse no sabe hacer
    eso, o falta información), o un rechazo con los motivos de por qué lo que
    propuso el modelo no vale.
    """

    plan: Optional[Plan] = None
    motivos: Tuple[str, ...] = field(default_factory=tuple)
    motivo_del_vacio: str = ""
    uso: Dict[str, Any] = field(default_factory=dict)

    @property
    def ejecutable(self) -> bool:
        return self.plan is not None and bool(self.plan.pasos) and not self.motivos

    @property
    def vacio(self) -> bool:
        return self.plan is not None and not self.plan.pasos

    def a_dict(self) -> dict:
        return {
            "plan": self.plan.a_dict() if self.plan is not None else None,
            "motivos": list(self.motivos),
            "motivo_del_vacio": self.motivo_del_vacio,
            "uso": dict(self.uso),
            "ejecutable": self.ejecutable,
        }


def _bloques(respuesta: Any) -> List[Any]:
    return list(getattr(respuesta, "content", []) or [])


def _peticion_de_plan(respuesta: Any) -> Optional[Dict[str, Any]]:
    for bloque in _bloques(respuesta):
        if getattr(bloque, "type", "") == "tool_use" and \
                getattr(bloque, "name", "") == NOMBRE_HERRAMIENTA:
            return dict(getattr(bloque, "input", {}) or {})
    return None


def _uso_de(respuesta: Any) -> Dict[str, Any]:
    """Los contadores que hacen falta para saber si la caché acertó.

    Sin esto, `AG-1` no tendría forma de comprobar su criterio nº4, que es el
    que decide si el coste por plan se sostiene.
    """
    uso = getattr(respuesta, "usage", None)
    if uso is None:
        return {}
    return {
        campo: getattr(uso, campo, 0) or 0
        for campo in ("input_tokens", "output_tokens",
                      "cache_creation_input_tokens", "cache_read_input_tokens")
    }


def _mensaje(prefijo: str, estado: str, intencion: str) -> List[Dict[str, Any]]:
    """El prompt, en dos bloques y en este orden.

    El prefijo —los manifiestos— es idéntico entre ejecuciones del mismo
    despliegue y se marca para caché; el estado del proyecto y la intención van
    detrás porque cambian. Invertir el orden haría que la caché no acertara
    nunca y el planificador se encarecería **en silencio**, que es la peor
    forma de encarecerse.
    """
    return [{
        "role": "user",
        "content": [
            {"type": "text",
             "text": "CATÁLOGO DE LO QUE ARCHMUSE SABE HACER\n\n" + prefijo,
             "cache_control": {"type": "ephemeral"}},
            {"type": "text",
             "text": estado + "\n\nLO QUE PIDE EL ARQUITECTO:\n" + intencion},
        ],
    }]


def _a_plan(propuesta: Dict[str, Any], intencion: str, proyecto_id: str) -> Plan:
    pasos: List[Paso] = []
    for i, crudo in enumerate(propuesta.get("pasos") or ()):
        if not isinstance(crudo, dict):
            raise PlanificacionInvalida("el paso %d no es un objeto" % i)
        identificador = str(crudo.get("id") or "").strip()
        skill = str(crudo.get("skill") or "").strip()
        if not identificador or not skill:
            raise PlanificacionInvalida(
                "el paso %d no declara id o skill: %r" % (i, crudo))
        pasos.append(Paso(
            id=identificador,
            skill=skill,
            argumentos=dict(crudo.get("argumentos") or {}),
            depende_de=tuple(str(d) for d in (crudo.get("depende_de") or ())),
        ))
    return Plan(objetivo=intencion, proyecto_id=proyecto_id, pasos=tuple(pasos))


def planificar(intencion: str, cliente: Any, *,
               memoria: Optional[MemoriaDeProyecto] = None,
               capacidades: Optional[Registro] = None,
               skills: Optional[RegistroDeSkills] = None,
               modelo: Optional[str] = None,
               max_pasos: int = MAX_PASOS,
               max_tokens: int = MAX_TOKENS,
               sistema: str = SISTEMA,
               carencias: Any = None) -> Planificacion:
    """De una intención en castellano a un `Plan` validado. **Una llamada.**

    `cliente` se inyecta y no se construye aquí: en producción es el de
    `ia.cliente.crear_cliente()` —con tiempo límite y contabilidad de coste— y
    en los tests es un doble guionizado. Un planificador que se fabrica su
    propio cliente es uno que no se puede probar sin gastar dinero.

    `carencias`, si se pasa, recibe los objetivos que ninguna Skill cubre. Es
    cómo se entera ArchMuse de lo que le falta: por uso real, no por intuición.
    """
    from .registro import registro as _reg, registro_de_skills as _reg_skills

    capacidades = capacidades if capacidades is not None else _reg()
    skills = skills if skills is not None else _reg_skills()
    modelo = modelo or modelos.para(PERFIL)

    prefijo = _contexto.prefijo_cacheable(capacidades, skills)
    resumen = _contexto.resumen_del_proyecto(memoria, skills)
    mensajes = _mensaje(prefijo, _contexto.a_texto(resumen), intencion)
    herramienta = esquema_de_la_herramienta(max_pasos)

    propuesta = None
    uso: Dict[str, Any] = {}
    # Un solo reintento, y sólo para el caso de §6 del PRD: el modelo contesta
    # con texto en vez de llamar a la herramienta. No se interpreta ese texto —
    # leer un plan de la prosa es exactamente cómo se cuela un plan inventado.
    for intento in (1, 2):
        respuesta = cliente.messages.create(
            model=modelo,
            max_tokens=max_tokens,
            system=sistema,
            tools=[herramienta],
            tool_choice={"type": "tool", "name": NOMBRE_HERRAMIENTA},
            messages=mensajes,
        )
        uso = _uso_de(respuesta)
        propuesta = _peticion_de_plan(respuesta)
        if propuesta is not None:
            break
        if intento == 2:
            return Planificacion(
                motivos=("el planificador no ha devuelto un plan en dos intentos; no se "
                         "interpreta su texto como si lo fuera",),
                uso=uso,
            )

    proyecto_id = memoria.proyecto_id if memoria is not None else "sin-proyecto"
    try:
        plan = _a_plan(propuesta or {}, intencion, proyecto_id)
    except PlanificacionInvalida as exc:
        return Planificacion(motivos=(str(exc),), uso=uso)

    if not plan.pasos:
        motivo = str((propuesta or {}).get("motivo") or "").strip()
        if carencias is not None:
            carencias.anotar(intencion)
        return Planificacion(
            plan=plan, uso=uso,
            motivo_del_vacio=motivo or (
                "ninguna Skill del catálogo cubre lo que se pide, y el planificador no "
                "ha dicho por qué"),
        )

    if len(plan.pasos) > max_pasos:
        return Planificacion(
            plan=plan, uso=uso,
            motivos=("el plan tiene %d pasos y el techo es %d: eso no lo ha pedido "
                     "nadie" % (len(plan.pasos), max_pasos),),
        )

    motivos = plan.validar(skills)
    return Planificacion(plan=plan, motivos=motivos, uso=uso)


@dataclass(frozen=True)
class Revision:
    """Lo que se sabe de un plan **antes** de ejecutarlo (tarea `AG-2`).

    Las tres listas son cosas distintas y no pueden confundirse:

    - `motivos` — el plan está mal: nombra algo que no existe, tiene un ciclo,
      pide una versión incompatible. **No se arregla contestando nada.**
    - `preguntas` — el plan está bien y le faltan datos del proyecto. Se
      desbloquea contestando, y por eso la pregunta es la salida y no el fallo.
    - `efectos_a_autorizar` — lo que va a pasarle al ordenador del arquitecto.
      Se enseña antes, no después.
    """

    motivos: Tuple[str, ...] = field(default_factory=tuple)
    preguntas: Tuple[str, ...] = field(default_factory=tuple)
    efectos_a_autorizar: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def ejecutable(self) -> bool:
        """Sin motivos. **Las preguntas no impiden ejecutar**: cada Skill se
        detiene sola en su paso y devuelve la suya, que es más útil que negarse
        a empezar — los pasos que sí tienen sus datos se hacen igual."""
        return not self.motivos

    def a_dict(self) -> dict:
        return {
            "motivos": list(self.motivos),
            "preguntas": list(self.preguntas),
            "efectos_a_autorizar": list(self.efectos_a_autorizar),
            "ejecutable": self.ejecutable,
        }


def revisar(plan: Plan, *, skills: RegistroDeSkills,
            capacidades: Optional[Registro] = None,
            memoria: Optional[MemoriaDeProyecto] = None) -> Revision:
    """Todo lo que se puede saber de un plan **sin gastar un token ni tocar un
    fichero** (tarea `AG-2`).

    Cinco comprobaciones, todas deterministas y todas baratas:

    1. Que el plan sea un DAG con pasos únicos y dependencias existentes
       (`Plan.validar`).
    2. Que cada Skill exista, y en la versión pedida.
    3. Que las capacidades que cada Skill declara sigan en el registro y en una
       versión compatible — un plan guardado hace seis meses puede nombrar una
       que ya no está.
    4. Que los requisitos de cada Skill estén en la memoria del proyecto. Si
       falta alguno, la salida es **la pregunta concreta** que lo desbloquea, no
       un «faltan datos» genérico que nadie sabe contestar.
    5. Qué efectos habrá que autorizar, reunidos y sin repetir.

    **Por qué esto vive aparte del planificador.** Un plan puede llegar de
    tres sitios: del modelo, de un fichero guardado hace meses, o escrito a
    mano por una pantalla. Los tres tienen que pasar por el mismo portero, y
    ninguno tiene que pagar una llamada para que le digan que le falta el
    municipio.
    """
    motivos: List[str] = list(plan.validar(skills))
    preguntas: List[str] = []
    efectos: List[str] = []

    for paso in plan.pasos:
        try:
            skill = skills.buscar(paso.skill)
        except Exception:                # noqa: BLE001 - `validar` ya lo reportó
            continue

        for efecto in skill.efectos:
            if efecto not in efectos:
                efectos.append(efecto)

        if capacidades is not None:
            try:
                skill.comprobar_registro(capacidades)
            except Exception as exc:     # noqa: BLE001 - SkillInvalida y familia
                motivos.append("«%s» (paso %s): %s" % (skill.id, paso.id, exc))

        if memoria is not None:
            for requisito in skill.faltantes(memoria):
                if requisito.pregunta not in preguntas:
                    preguntas.append(requisito.pregunta)

    return Revision(motivos=tuple(motivos), preguntas=tuple(preguntas),
                    efectos_a_autorizar=tuple(efectos))


def a_texto(planificacion: Planificacion, skills: Optional[RegistroDeSkills] = None) -> str:
    """El plan como se le enseña al arquitecto **antes** de ejecutarlo.

    Es la razón de ser de esta tarea: lo que no se puede enseñar no se puede
    parar. Se dice qué se va a hacer, con qué procedimiento y **qué efectos
    habrá que autorizar** — porque enterarse de que algo escribe un fichero
    después de que lo haya escrito no sirve de nada.
    """
    if planificacion.motivos:
        return "NO SE PUEDE EJECUTAR ESTE PLAN:\n" + "\n".join(
            "  · %s" % m for m in planificacion.motivos)
    if planificacion.vacio:
        return ("ArchMuse no sabe hacer esto todavía.\n  %s"
                % planificacion.motivo_del_vacio)

    plan = planificacion.plan
    assert plan is not None
    lineas = ["PLAN: %s" % plan.objetivo, ""]
    efectos: List[str] = []
    for i, paso in enumerate(plan.orden(), start=1):
        detalle = ""
        if skills is not None:
            try:
                skill = skills.buscar(paso.skill)
                detalle = " — %s" % skill.objetivo
                for efecto in skill.efectos:
                    if efecto not in efectos:
                        efectos.append(efecto)
            except Exception:            # noqa: BLE001 - la validación ya lo dijo
                detalle = ""
        lineas.append("  %d. [%s] %s%s" % (i, paso.id, paso.skill, detalle))
        if paso.depende_de:
            lineas.append("       después de: %s" % ", ".join(paso.depende_de))
    if efectos:
        lineas.append("")
        lineas.append("Habrá que autorizar: %s" % ", ".join(efectos))
    return "\n".join(lineas)
