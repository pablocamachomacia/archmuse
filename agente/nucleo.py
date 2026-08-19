# -*- coding: utf-8 -*-
"""El bucle del agente: intención -> herramienta -> resultado -> respuesta.

**Por qué un orquestador propio y no un framework.** La decisión está tomada y
razonada en `docs/design/2026-08-18-auditoria-arquitectura-tecnologica.md`: ni
LangGraph ni el SDK de agentes de OpenAI. El bucle de un agente con
herramientas son las cuarenta líneas de `ejecutar()`; lo que sí es difícil —y
lo que ningún framework regala— es el contrato de las capacidades, la
procedencia de cada dato y el portero de invariantes. Adoptar un framework
costaría una dependencia grande, un modelo de ejecución ajeno y ninguna de las
tres cosas que importan.

**Qué es esto exactamente.** El bucle mínimo, completo y funcionando:

    usuario -> agente -> herramienta -> resultado -> agente -> ... -> respuesta

El agente decide si necesita una herramienta, se ejecuta la real, su resultado
estructurado vuelve al modelo, y el ciclo se repite mientras el modelo pida
más. Encadenar dos herramientas no necesita nada especial: el resultado de la
primera está en la conversación cuando el modelo pide la segunda.

**Qué NO es todavía**, para que nadie lo confunda con el orquestador del ADR:

- No hay plan tipado por adelantado. **Aquí** el modelo decide paso a paso; el
  DAG validado antes de ejecutar nada existe, pero vive en
  `agente/planificador.py` y se elige desde la fachada con
  `copiloto.atender(via=VIA_PLAN)`. Las dos vías conviven a propósito.
- No hay grafo portante, así que no hay `requiere` que comprobar contra
  `KNOWN`, ni `Atributo` con procedencia escrito por cada capacidad, ni sellado
  al final (V1-7 y V1-12).
- No hay presupuesto por ejecución ni replanificación. El único freno es
  `max_iteraciones`, y su papel es impedir un bucle infinito, no acotar gasto:
  eso lo mide `ia/uso.py`, que ya cuenta cada llamada porque el cliente pasa
  por `ia/cliente.py`.

Las tres ausencias son de alcance, no de diseño: este núcleo es la base sobre
la que esas piezas se montan.

**Sobre el contexto largo.** El historial crece con cada resultado y aquí no se
tira nada nunca: lo que sí se hace es recortar **lo que ve el modelo** cuando un
resultado no cabe (`agente/recorte.py`), con la marca puesta y el original
intacto en `PasoEjecutado.resultado`. Y si la conversación entera deja de caber,
el bucle **para antes de llamar** con `parada == "contexto_agotado"` en vez de
pagar una llamada para recibir un error. No hay resumen automático del
historial, y es deliberado: resumir un resultado de herramienta es inventar en
pequeño, y por ahí es por donde entra una cifra que nadie midió.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from . import efectos as _efectos
from .capacidad import ArgumentosInvalidos, ResultadoInvalido
from .ejecucion import Bitacora, Ejecutor, Paso, Plan, ResultadoDePaso
from .memoria import MemoriaDeProyecto
from .registro import (
    CapacidadDesconocida,
    Registro,
    RegistroDeSkills,
    registro as _registro,
    registro_de_skills as _registro_de_skills,
)
from . import recorte as _recorte
from .respaldo import sin_respaldo
from ia import modelos

#: Prefijo con el que una Skill se ofrece al modelo. Distinguirlas por el
#: nombre, y no por dos búsquedas en dos registros, mantiene el bucle simple.
PREFIJO_SKILL = "skill__"

#: El perfil de tarea, no el modelo: la elección concreta vive en
#: `ia/modelos.py`, que es el único sitio del repositorio donde se decide qué
#: modelo hace qué. Planificar —elegir capacidades y encadenarlas— es la tarea
#: donde un modelo mejor más se nota, porque un plan malo cuesta varias
#: ejecuciones; hoy apunta al mismo `claude-sonnet-5` que todo lo demás, y
#: cambiarlo es una línea cuando `ia/uso.py` tenga datos para justificarlo.
PERFIL = "planificacion"
MODELO = modelos.para(PERFIL)

MAX_TOKENS = 2048

#: Cuántas veces se le puede devolver el turno al modelo. Seis permite cadenas
#: de hasta cinco herramientas más la redacción final, que sobra para lo que
#: hoy hay en el registro. Es un freno contra el bucle infinito; el gasto lo
#: acota `ia/uso.py` con su tope, que corta ANTES de la llamada.
MAX_ITERACIONES = 6

SISTEMA = """\
Eres el asistente técnico de ArchMuse, una herramienta para arquitectos españoles.

Reglas, y no son negociables:

1. No inventes NUNCA el resultado de una herramienta. Si necesitas un dato que
   una herramienta puede darte, llámala. Si no la has llamado, no tienes el dato.
2. No escribas ninguna cifra que no venga de un resultado de herramienta o del
   propio usuario. Ni redondeada, ni «aproximadamente», ni «suele ser».
3. Si una herramienta devuelve `ok: false`, o devuelve un valor nulo con una
   pregunta, tu respuesta es esa pregunta. No rellenes el hueco.
4. Encadena herramientas cuando una necesite lo que produce otra: pasa el valor
   exacto que devolvió la primera, no uno equivalente que recuerdes.
5. Cita siempre la fuente oficial que la herramienta te haya devuelto, tal cual.
6. Di explícitamente qué NO se ha comprobado cuando el resultado lo declare
   (materias sin cobertura, reglas pendientes de firma colegiada). El arquitecto
   firma el proyecto; ArchMuse solo asesora.
7. Un resultado que traiga `__recorte__` viene incompleto **por tamaño**. Lo
   omitido existe y no lo estás viendo: no lo supongas, no lo cuentes, y dilo.
   Si hace falta lo que falta, pídelo con una herramienta más concreta.

Responde en castellano, breve y sin adornos."""

#: Se añade al sistema cuando hay Skills disponibles. Sin esto el modelo trata
#: una Skill como una herramienta más y la parte en trozos, que es justo lo que
#: la Skill existe para evitar: el procedimiento profesional entero.
SISTEMA_CON_SKILLS = """

Tienes dos clases de herramienta y NO son intercambiables:

- Las que empiezan por `skill__` son procedimientos profesionales completos.
  Cuando una cubra el objetivo, úsala ENTERA: ya sabe qué mirar, en qué orden y
  qué comprobar. No reconstruyas su trabajo a base de herramientas sueltas.
- Las demás son funciones sueltas. Úsalas para lo que ninguna Skill cubra.

Si una Skill devuelve preguntas, tu respuesta es esa pregunta. Si pide una
autorización, dilo y no sigas por ahí. Si ninguna Skill cubre lo que se pide,
dilo claramente: es mejor que hacerlo a medias con herramientas sueltas."""


@dataclass(frozen=True)
class PasoEjecutado:
    """Una invocación real de una capacidad, con lo que devolvió.

    Es la unidad de traza del bucle. Cuando el grafo sea portante, esto es lo
    que se convierte en `Atributo` con procedencia; hoy ya sirve para lo mismo
    en pequeño: saber de dónde salió cada dato de la respuesta.
    """

    capacidad: str
    version: str
    argumentos: Dict[str, Any]
    resultado: Dict[str, Any]
    ok: bool
    duracion_ms: int


@dataclass(frozen=True)
class Respuesta:
    """Lo que el bucle devuelve: el texto y todo lo que hay detrás de él."""

    texto: str
    pasos: Tuple[PasoEjecutado, ...] = ()
    iteraciones: int = 0
    #: "fin" | "limite_de_iteraciones" | "contexto_agotado", y por la vía del
    #: plan también "plan_vacio" | "plan_invalido" | "no_confirmado". Quien
    #: consuma la respuesta tiene que mirarlo: sólo "fin" significa que el
    #: agente terminó de decir lo que tenía que decir.
    parada: str = "fin"
    cifras_sin_respaldo: Tuple[str, ...] = ()
    limitaciones: Tuple[str, ...] = ()
    #: Lo que se recortó de los resultados antes de enseñárselos al modelo, por
    #: tamaño. Vacío en el caso normal. No es telemetría: es la lista de lo que
    #: el modelo NO llegó a ver, y por tanto lo que no puede haber tenido en
    #: cuenta al responder.
    recortes: Tuple[str, ...] = ()
    #: Skills ejecutadas, con su estado. Es lo que alimenta el acta.
    pasos_de_skill: Tuple[ResultadoDePaso, ...] = ()
    #: Lo que hace falta preguntar para poder terminar, sin repetir.
    preguntas: Tuple[str, ...] = ()
    #: Efectos que alguien tiene que autorizar antes de seguir.
    efectos_pendientes: Tuple[str, ...] = ()

    @property
    def fundamentada(self) -> bool:
        """Ninguna cifra de la respuesta sale de la nada.

        Falso NO significa «el agente ha mentido»: significa «hay una cifra que
        no he podido rastrear hasta una herramienta». Ver `respaldo.py` para lo
        que este criterio demuestra y lo que no.
        """
        return not self.cifras_sin_respaldo


# --- Ejecución de una herramienta -------------------------------------------

def _ejecutar_capacidad(reg: Registro, nombre: str, argumentos: Dict[str, Any]) -> PasoEjecutado:
    """Ejecuta una capacidad y devuelve SIEMPRE un paso con resultado estructurado.

    Los tres modos de fallo —no existe, argumentos que no admite, revienta al
    ejecutarse— se convierten en un `dict` con `ok: false` y motivo. Ninguno
    produce un valor: un fallo que devuelve algo plausible es peor que un fallo.
    """
    comienzo = time.monotonic()

    def _fallo(codigo: str, detalle: str, version: str = "?") -> PasoEjecutado:
        return PasoEjecutado(
            capacidad=nombre,
            version=version,
            argumentos=dict(argumentos),
            resultado={"ok": False, "error": codigo, "detalle": detalle},
            ok=False,
            duracion_ms=int((time.monotonic() - comienzo) * 1000),
        )

    try:
        capacidad = reg.buscar(nombre)
    except CapacidadDesconocida as exc:
        return _fallo("capacidad_desconocida", str(exc))

    try:
        resultado = capacidad.invocar(argumentos)
    except ArgumentosInvalidos as exc:
        return _fallo("argumentos_invalidos", str(exc), capacidad.version)
    except ResultadoInvalido as exc:
        return _fallo("resultado_invalido", str(exc), capacidad.version)
    except Exception as exc:  # noqa: BLE001 - una capacidad no puede tumbar el bucle
        return _fallo(
            "fallo_de_capacidad",
            "%s: %s" % (type(exc).__name__, exc),
            capacidad.version,
        )

    return PasoEjecutado(
        capacidad=capacidad.id,
        version=capacidad.version,
        argumentos=dict(argumentos),
        resultado=resultado,
        ok=bool(resultado.get("ok")),
        duracion_ms=int((time.monotonic() - comienzo) * 1000),
    )


# --- Lectura de la respuesta del modelo -------------------------------------

def _bloques(respuesta: Any) -> List[Any]:
    return list(getattr(respuesta, "content", None) or [])


def _como_dict(bloque: Any) -> Dict[str, Any]:
    """El bloque tal cual, en `dict`, para poder reenviarlo en el historial.

    El SDK devuelve objetos y los tests usan dobles; los dos se leen igual por
    atributo, así que no hace falta que el núcleo dependa del SDK para
    entenderlos — que es también lo que permite probar el bucle entero sin red.
    """
    if isinstance(bloque, dict):
        return bloque
    if hasattr(bloque, "model_dump"):
        return bloque.model_dump(exclude_none=True)
    tipo = getattr(bloque, "type", "")
    if tipo == "tool_use":
        return {
            "type": "tool_use",
            "id": getattr(bloque, "id", ""),
            "name": getattr(bloque, "name", ""),
            "input": getattr(bloque, "input", {}) or {},
        }
    return {"type": "text", "text": getattr(bloque, "text", "")}


def _texto_de(respuesta: Any) -> str:
    partes = [
        getattr(b, "text", "") or ""
        for b in _bloques(respuesta)
        if getattr(b, "type", "") == "text"
    ]
    return "\n".join(p for p in partes if p).strip()


# --- El cliente de produccion -----------------------------------------------

def cliente_por_defecto() -> Any:
    """El cliente real, con tiempo limite y contabilidad de coste.

    Pasa por `ia/cliente.py` y no por el SDK a pelo, que es lo que hace que
    cada llamada del agente cuente en `ia/uso.py` y respete el tope de gasto.
    Un cliente construido por su cuenta sería el séptimo punto de llamada sin
    medir, que es exactamente el patrón que ese módulo existe para prohibir.
    """
    import os

    from ia.cliente import crear_cliente

    clave = os.environ.get("ANTHROPIC_API_KEY")
    if not clave:
        raise RuntimeError(
            "Falta ANTHROPIC_API_KEY. El agente no funciona sin modelo; las "
            "capacidades, en cambio, se pueden invocar sueltas sin clave."
        )
    return crear_cliente(clave)


# --- El bucle ---------------------------------------------------------------

def ejecutar(
    intencion: str,
    cliente: Any,
    *,
    reg: Optional[Registro] = None,
    skills: Optional[RegistroDeSkills] = None,
    memoria: Optional[MemoriaDeProyecto] = None,
    autorizaciones: Optional[_efectos.Autorizaciones] = None,
    ejecucion_id: str = "",
    bitacora: Optional[Bitacora] = None,
    modelo: str = MODELO,
    max_iteraciones: int = MAX_ITERACIONES,
    max_tokens: int = MAX_TOKENS,
    sistema: str = SISTEMA,
    max_caracteres_por_resultado: int = _recorte.MAX_CARACTERES,
    max_contexto: int = _recorte.MAX_CONTEXTO,
) -> Respuesta:
    """Atiende una petición encadenando las capacidades que hagan falta.

    `cliente` se inyecta a propósito y no se construye aquí: en producción es
    el de `ia.cliente.crear_cliente()` —que trae tiempo límite y contabilidad
    de coste— y en los tests es un doble guionizado. Un núcleo que se fabrica su
    propio cliente es un núcleo que no se puede probar sin gastar dinero.
    """
    reg = reg if reg is not None else _registro()
    if memoria is not None and skills is None:
        skills = _registro_de_skills()
    # Sin memoria de proyecto no se ofrecen Skills: una Skill comprueba sus
    # requisitos contra la memoria, y sin memoria todas dirían que les falta
    # todo. Ofrecerlas rotas es peor que no ofrecerlas.
    con_skills = skills is not None and memoria is not None
    herramientas = reg.esquemas() + ([s.esquema() for s in skills] if con_skills else [])
    if con_skills:
        sistema = sistema + SISTEMA_CON_SKILLS
    ejecutor = (
        Ejecutor(capacidades=reg, skills=skills, bitacora=bitacora) if con_skills else None
    )
    ejecucion_id = ejecucion_id or ("bucle-%d" % abs(hash(intencion)))
    pasos_de_skill: List[ResultadoDePaso] = []
    mensajes: List[Dict[str, Any]] = [{"role": "user", "content": intencion}]
    pasos: List[PasoEjecutado] = []
    recortes: List[str] = []
    parada = "limite_de_iteraciones"
    texto = ""
    iteraciones = 0
    respuesta: Any = None

    for iteraciones in range(1, max_iteraciones + 1):
        # Se mira **antes** de llamar. Descubrir que la conversación no cabía
        # por el error del proveedor cuesta la llamada, no da un motivo legible
        # y tira lo que ya se había hecho: aquí se conserva.
        if not _recorte.cabe_el_historial(mensajes, limite=max_contexto):
            parada = "contexto_agotado"
            texto = _texto_de(respuesta) if respuesta is not None else ""
            recortes.append(
                "la conversación superó los %d caracteres y se paró antes de la "
                "iteración %d: lo hecho hasta aquí se conserva, lo que faltaba no "
                "se hizo" % (max_contexto, iteraciones)
            )
            break
        respuesta = cliente.messages.create(
            model=modelo,
            max_tokens=max_tokens,
            system=sistema,
            tools=herramientas,
            messages=mensajes,
        )
        mensajes.append(
            {"role": "assistant", "content": [_como_dict(b) for b in _bloques(respuesta)]}
        )

        peticiones = [b for b in _bloques(respuesta) if getattr(b, "type", "") == "tool_use"]
        if not peticiones:
            texto = _texto_de(respuesta)
            parada = "fin"
            break

        resultados: List[Dict[str, Any]] = []
        for peticion in peticiones:
            nombre = getattr(peticion, "name", "")
            argumentos = dict(getattr(peticion, "input", {}) or {})
            if nombre.startswith(PREFIJO_SKILL) and ejecutor is not None:
                paso_skill, cuerpo = _ejecutar_skill(
                    ejecutor, nombre, argumentos, memoria, autorizaciones,
                    ejecucion_id, len(pasos_de_skill),
                )
                pasos_de_skill.append(paso_skill)
                visible, cortes = _recorte.recortar(
                    cuerpo, limite=max_caracteres_por_resultado)
                recortes.extend("%s: %s" % (nombre, c) for c in cortes)
                resultados.append({
                    "type": "tool_result",
                    "tool_use_id": getattr(peticion, "id", ""),
                    "content": json.dumps(visible, ensure_ascii=False, sort_keys=True,
                                          default=str),
                    "is_error": not cuerpo["ok"],
                })
                continue
            paso = _ejecutar_capacidad(reg, nombre, argumentos)
            pasos.append(paso)
            # Lo que vuelve al modelo puede venir recortado por tamaño, pero
            # nunca resumido ni reinterpretado: `paso.resultado` conserva el
            # original íntegro, y es contra el original contra lo que se
            # comprueban después las cifras del texto final.
            visible, cortes = _recorte.recortar(
                paso.resultado, limite=max_caracteres_por_resultado)
            recortes.extend("%s: %s" % (nombre, c) for c in cortes)
            resultados.append(
                {
                    "type": "tool_result",
                    "tool_use_id": getattr(peticion, "id", ""),
                    # Lo único que vuelve al modelo es lo que devolvió la
                    # función. No hay ninguna rama por la que el texto del
                    # modelo se convierta en el resultado de su herramienta.
                    "content": json.dumps(
                        visible, ensure_ascii=False, sort_keys=True, default=str
                    ),
                    # `is_error` también para un `ok: false` legítimo (municipio
                    # desconocido, umbral sin valor): no es un fallo técnico,
                    # pero sí es «de aquí no ha salido un valor», y marcarlo es
                    # lo que impide que se lea por encima como si lo hubiera.
                    "is_error": not paso.ok,
                }
            )
        mensajes.append({"role": "user", "content": resultados})
    else:
        # Se agotaron las iteraciones con el modelo todavía pidiendo
        # herramientas: se conserva lo último que escribió, y `parada` dice por
        # qué se paró. Quien consuma la respuesta tiene que mirarlo: un texto
        # con `parada == "limite_de_iteraciones"` está a medias por definición.
        texto = _texto_de(respuesta) if respuesta is not None else ""

    piezas: List[Any] = [intencion]
    piezas.extend(p.resultado for p in pasos)
    piezas.extend(p.argumentos for p in pasos)
    piezas.extend(p.salida for p in pasos_de_skill if p.salida)

    limitaciones: List[str] = []
    for paso in pasos:
        try:
            limitaciones.extend(reg.buscar(paso.capacidad).limitaciones)
        except CapacidadDesconocida:
            continue
    preguntas: List[str] = []
    efectos_pendientes: List[str] = []
    for paso_skill in pasos_de_skill:
        preguntas.extend(paso_skill.preguntas)
        efectos_pendientes.extend(paso_skill.efectos_pendientes)
        if skills is None:
            continue
        try:
            limitaciones.extend(skills.buscar(paso_skill.skill).limitaciones)
        except Exception:  # noqa: BLE001 - una etiqueta no rompe una respuesta
            continue

    return Respuesta(
        texto=texto,
        pasos=tuple(pasos),
        iteraciones=iteraciones,
        parada=parada,
        cifras_sin_respaldo=sin_respaldo(texto, piezas),
        # Lo que no se ha comprobado se DERIVA de las capacidades y Skills que
        # se ejecutaron. No se redacta a mano: es el acta de procedencia en
        # pequeño, y `agente/acta.py` la levanta entera a partir de esto.
        limitaciones=tuple(dict.fromkeys(limitaciones)),
        pasos_de_skill=tuple(pasos_de_skill),
        preguntas=tuple(dict.fromkeys(preguntas)),
        efectos_pendientes=tuple(dict.fromkeys(efectos_pendientes)),
        recortes=tuple(dict.fromkeys(recortes)),
    )


def _ejecutar_skill(ejecutor: Ejecutor, nombre: str, argumentos: Dict[str, Any],
                    memoria: MemoriaDeProyecto,
                    autorizaciones: Optional[_efectos.Autorizaciones],
                    ejecucion_id: str, indice: int):
    """Ejecuta una Skill a través del ejecutor de planes, no por la vía corta.

    Podría llamarse a `skill.ejecutar()` directamente y serían seis líneas
    menos. No se hace: pasando por el ejecutor, una Skill invocada desde la
    conversación obtiene lo mismo que una invocada desde un plan —checkpoint en
    la bitácora, aislamiento del fallo, y el mismo `ResultadoDePaso` que el acta
    entiende—. Dos caminos distintos hacia el mismo trabajo es exactamente cómo
    se consiguen dos comportamientos distintos ante el mismo error.
    """
    skill_id = nombre[len(PREFIJO_SKILL):].replace("__", ".")
    plan = Plan(
        objetivo="invocación directa desde la conversación",
        proyecto_id=memoria.proyecto_id,
        pasos=(Paso(id="s%d" % indice, skill=skill_id, argumentos=argumentos),),
    )
    resultado = ejecutor.ejecutar(
        plan, memoria, ejecucion_id="%s-%d" % (ejecucion_id, indice),
        autorizaciones=autorizaciones,
    )
    paso = resultado.pasos[0]
    cuerpo: Dict[str, Any] = {
        "ok": paso.estado == "hecho",
        "estado": paso.estado,
        "skill": paso.skill,
    }
    if paso.motivo:
        cuerpo["motivo"] = paso.motivo
    if paso.preguntas:
        cuerpo["preguntas"] = list(paso.preguntas)
    if paso.efectos_pendientes:
        cuerpo["efectos_que_hay_que_autorizar"] = [
            {"efecto": e, "descripcion": _efectos.DESCRIPCIONES.get(e, e)}
            for e in paso.efectos_pendientes
        ]
    if paso.salida:
        cuerpo["resultado"] = paso.salida.get("resultado")
        cuerpo["verificado"] = (paso.salida.get("dictamen") or {}).get("verificado")
        cuerpo["avisos_de_verificacion"] = (paso.salida.get("dictamen") or {}).get("avisos") or []
    return paso, cuerpo
