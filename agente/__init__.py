# -*- coding: utf-8 -*-
"""El núcleo agéntico de ArchMuse: objetivo → Skills → Tools → trabajo con acta.

**Qué es esto.** El sistema que convierte «comprueba esta parcela y su
normativa» en trabajo entregable: entiende el objetivo, mira el contexto del
proyecto, elige qué procedimientos profesionales aplicar, ejecuta las
herramientas reales, comprueba su propio resultado y entrega el trabajo **más
el acta de dónde salió cada número**.

**El recorrido, y dónde vive cada tramo:**

    intención     `nucleo.py`      el bucle con el modelo
    contexto      `memoria.py`     lo que el arquitecto ya dijo del proyecto
    planificación `ejecucion.py`   `Plan`: un DAG de Skills, inspeccionable
    Skills        `skill.py`       procedimiento profesional declarado
    Tools         `capacidad.py`   saber hacer una cosa, con manifiesto
    ejecución     `ejecucion.py`   checkpoints, aislamiento de fallos, reanudar
    observación   `ejecucion.py`   la bitácora, append-only
    verificación  `verificacion.py` comprobaciones que pueden fallar
    resultado     `acta.py`        el trabajo, y qué NO se comprobó
    fachada       `copiloto.py`    lo único que hace falta conocer desde fuera

**Las cinco garantías del sistema**, y ninguna depende de que alguien se acuerde:

1. **No se inventa el resultado de una herramienta.** Lo que vuelve al modelo lo
   produjo el ejecutor; una capacidad inexistente se rechaza; toda capacidad
   devuelve un `dict` con `ok`; y `respaldo.py` rastrea cada cifra del texto
   final hasta un resultado real.
2. **No se ejecuta sin los datos.** Una Skill con un requisito insatisfecho
   devuelve **la pregunta concreta**, sin gastar un token ni tocar un fichero.
3. **No se toca el mundo sin permiso.** Los efectos se declaran, y el ejecutor
   se niega a ejecutar lo que nadie ha autorizado (`efectos.py`).
4. **No se entrega sin decir qué no se comprobó.** La lista se **deriva** de las
   limitaciones de lo que se ejecutó; nadie la redacta y nadie la olvida.
5. **No se dice un número sin decir de qué clase es.** Hecho, cálculo,
   inferencia o propuesta (`afirmacion.py`): es la frontera entre asesorar y
   firmar.

**Hay dos vías y se eligen desde la fachada** (`copiloto.atender(via=...)`):
`VIA_BUCLE`, donde el modelo encadena herramientas paso a paso, y `VIA_PLAN`,
donde `planificador.py` produce un DAG de **una** llamada, se audita sin gastar
un token y lo ejecuta el ejecutor. La segunda es la única que **se puede
enseñar antes de tocar nada** —`proponer()` devuelve el plan, las preguntas y
los efectos; `ejecutar_propuesta()` ejecuta ese plan y sólo ése—. El defecto
sigue siendo el bucle: cambiarlo es una decisión con datos (`AG-3`), no de golpe.

Por esa vía, los pasos independientes **se ejecutan a la vez** cuando es seguro
(`AG-8`: lista blanca de efectos, nivel entero, y la bitácora siempre en el
orden del plan), y si algo no sale se replanifica **una vez** —nunca dos, nunca
para esquivar una autorización— antes de parar y preguntar (`AG-4`).

**Lo que todavía no es.** El grafo de `modelo/` no es portante, así que
`requiere` se comprueba contra la memoria de proyecto y no contra el grafo; y
no hay presupuesto por ejecución (`AG-3`). Las ausencias son de alcance, no de
diseño.
"""
from .afirmacion import Afirmacion
from .capacidad import Capacidad
from .copiloto import (
    VIA_BUCLE,
    VIA_PLAN,
    Entrega,
    Propuesta,
    atender,
    ejecutar_propuesta,
    proponer,
)
from .memoria import MemoriaDeProyecto
from .nucleo import PasoEjecutado, Respuesta, cliente_por_defecto, ejecutar
from .registro import Registro, RegistroDeSkills, registro, registro_de_skills
from .skill import Skill

__all__ = [
    "VIA_BUCLE", "VIA_PLAN", "Afirmacion", "Capacidad", "Entrega",
    "MemoriaDeProyecto", "PasoEjecutado", "Propuesta", "Registro",
    "RegistroDeSkills", "Respuesta", "Skill", "atender", "cliente_por_defecto",
    "ejecutar", "ejecutar_propuesta", "proponer", "registro",
    "registro_de_skills",
]

# Uso, de punta a punta:
#
#     from agente import atender, cliente_por_defecto, MemoriaDeProyecto
#
#     memoria = MemoriaDeProyecto("proyecto-42")
#     memoria.declarar("territorial.municipio", "Madrid", registrado_por="usuario:pablo")
#     memoria.declarar("proyecto.uso", "residencial.vivienda_libre", registrado_por="usuario:pablo")
#     memoria.declarar("proyecto.tipologia", "plurifamiliar", registrado_por="usuario:pablo")
#
#     entrega = atender("Comprueba esta parcela y su normativa",
#                       cliente_por_defecto(), memoria)
#     print(entrega.texto)
#     print(entrega.acta.a_texto())      # de dónde salió cada número
#     print(entrega.preguntas)           # qué falta para poder terminar
#
# Y sin web, sin Flask y sin FastAPI — la prueba del plugin, tarea CAD-1:
#
#     python -m agente.invocar                                  # el catálogo
#     python -m agente.invocar plano.leer_dxf --ruta plan.dxf   # una capacidad
#     python -m agente.invocar --openapi                        # el contrato HTTP
#     python -m agente.invocar --comprobar                      # los tres consumidores casan
#
# Los tres consumidores de cada manifiesto (herramienta de Anthropic, operación
# OpenAPI y firma programática) los genera `agente/manifiesto.py` de una sola
# declaración, y `agente/contexto.py` acota lo que de todo esto llega al modelo.
