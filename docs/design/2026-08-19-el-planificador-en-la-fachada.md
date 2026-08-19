# El planificador enchufado a la fachada, y el contexto largo

**Fecha:** 2026-08-19
**Estado:** implementado, pendiente de revisión de Pablo
**Ámbito:** `agente/copiloto.py`, `agente/nucleo.py`, `agente/recorte.py`,
`agente/ejecucion.py`, `agente/planificador.py`, `scripts/demo_agente.py`
**Encargo:** «Integrar el planificador con `copiloto.atender()`. Hacer que el
agente pueda mostrar el plan antes de ejecutar efectos. Mejorar la gestión de
contexto largo. Corregir cualquier defecto real del bucle. Mantener
estrictamente las garantías actuales.» (Pablo, 2026-08-19)

---

## 0. Por qué esto no es un PRD

La regla de `CLAUDE.md` es PRD antes de código para **capacidad nueva**. Aquí no
hay capacidad nueva: `AG-1` (el planificador tipado) y `AG-2` (el validador
determinista) tienen PRD aprobado por Pablo el 2026-08-19 y están marcados
`HECHO` en el backlog. Lo que faltaba era que alguien pudiera llegar a ellos.

El PRD de `AG-1` §10 dice literalmente: *«El planificador es un camino nuevo, no
una sustitución; decidir cuál manda es una decisión posterior con datos.»* Este
documento es esa decisión posterior, y la toma **sin** cambiar cuál manda.

## 1. El problema, medido

El 2026-08-19, `agente/` tenía 5.082 líneas con la suite en verde y **nada de
ello alcanzable**: `planificar()` sólo lo llamaban los tests y
`scripts/demo_agente.py`, y `agente` no aparecía en `app.py`. El motor crecía
más deprisa que la superficie por la que alguien puede usarlo. Es exactamente lo
que la regla 3 de Pablo prohíbe seguir haciendo.

Y el valor que se perdía no era teórico. El bucle **no se puede enseñar**: no
tiene forma hasta que ha terminado, así que el arquitecto no puede verlo antes,
no puede pararlo y no hay forma de sumar su coste por adelantado. Un plan sí.

## 2. Lo que se ha hecho

### 2.1 Dos vías, elegidas desde la fachada

`copiloto.atender(objetivo, cliente, memoria, via=...)`:

| Vía | Qué hace | Cuándo se defiende sola |
|---|---|---|
| `VIA_BUCLE` (**defecto**) | El modelo encadena herramientas paso a paso dentro de `nucleo.ejecutar` | Conversación: «apunta que quieren cuatro dormitorios» |
| `VIA_PLAN` | Una llamada → DAG → auditoría sin coste → ejecución | Trabajo: se puede enseñar, parar y presupuestar |

### 2.2 Enseñar el plan antes de ejecutar efectos

La misma vía, partida en dos, que es lo que permite que entre las dos haya un
sitio donde decir que no:

```python
propuesta = copiloto.proponer(objetivo, cliente, memoria)   # no ejecuta nada
print(propuesta.texto())                                     # pasos, preguntas, efectos
entrega  = copiloto.ejecutar_propuesta(propuesta, memoria,   # ejecuta ESE plan
                                       autorizaciones=...)
```

`Propuesta` responde a las tres preguntas que hay que contestar antes de decir
que sí, y ninguna exige haber ejecutado nada: `motivos` (el plan está mal y no
se arregla contestando), `preguntas` (le faltan datos del proyecto, y la salida
es la pregunta concreta) y `efectos_a_autorizar` / `falta_autorizar(...)`.

`ejecutar_propuesta(..., confirmar=...)` es el gancho para una pantalla o un
`input()`. Devolver falso **no ejecuta ni el primer paso**, ni siquiera el que
no tenía efectos: no se llega a construir el contexto de ninguna Skill.

**La propuesta lleva dentro los registros con los que se planificó.** Ejecutar
contra un catálogo distinto del que se le enseñó al arquitecto sería enseñar una
cosa y hacer otra.

### 2.3 El texto de la vía del plan no lo escribe un modelo

Por la vía del plan hay **una** llamada en total: la de planificar. No hay
llamada de redacción al final, y no haberla es lo que hace estructuralmente
imposible que aparezca una cifra que ninguna herramienta produjo. El texto se
deriva de `ResultadoDeEjecucion`. `respaldo.sin_respaldo()` se ejecuta igual —no
porque haga falta, sino para que salte el día que alguien meta prosa generada
ahí—, y hay un test que fija que la vía entera siga costando una sola llamada.

### 2.4 Contexto largo (`agente/recorte.py`)

El bucle añadía cada resultado de herramienta al historial entero y literal, sin
quitar nada nunca. Con un DXF de cuarenta recintos, un solo resultado se come el
contexto y las herramientas siguientes fallan por una razón que no tiene nada
que ver con lo que se pidió — o sea, justo con el plano del cliente.

Tres reglas, y las tres son de no-invención antes que de eficiencia:

1. **Se recorta con la estructura, no con la cadena.** Las claves se conservan
   todas, las listas se acortan y las cadenas largas se cortan. Lo que sale
   sigue siendo JSON válido: un modelo que recibe un JSON roto improvisa.
2. **El recorte se declara donde el modelo lo lee** (clave `__recorte__` con
   aviso explícito) y también viaja a `Respuesta.recortes`. Un recorte
   silencioso no se distingue de un dato que no existía. Hay una regla nueva en
   el prompt del sistema para el caso.
3. **No se resume.** Resumir un resultado de herramienta es inventar en pequeño,
   y es por donde entra una cifra que nadie midió.

El original queda **íntegro** en `PasoEjecutado.resultado`, y es contra el
original —no contra el recorte— contra lo que se comprueban las cifras del texto
final. Un modelo que ve menos puede citar menos, nunca más.

Y si la conversación entera deja de caber, el bucle **para antes de llamar**
(`parada == "contexto_agotado"`), conservando lo hecho, en vez de pagar una
llamada para recibir un error del proveedor.

Topes por defecto: 20.000 caracteres por resultado (~5k tokens) y 300.000 de
historial. Que no salten nunca en uso normal es el diseño.

### 2.5 Un defecto real, corregido

`ResultadoDeEjecucion.completa` era `all(p.estado == HECHO for p in self.pasos)`.
`all()` de nada es cierto, así que **una ejecución sin un solo paso se declaraba
completa**. Esa bandera viaja al acta. Con las vías nuevas el caso deja de ser
teórico —plan vacío, plan rechazado, plan no confirmado son tres resultados
legítimos con cero pasos— pero el defecto ya existía por la vía del bucle: una
respuesta en prosa sin ninguna Skill ejecutada emitía un acta que decía
`completa: true`. Un acta que afirma eso sobre un trabajo que nadie hizo es
exactamente la clase de afirmación que este sistema existe para no emitir.

## 3. Decisiones tomadas, y por qué la conservadora

| Decisión | Qué se eligió | Por qué |
|---|---|---|
| Cuál manda | **`VIA_BUCLE` sigue siendo el defecto** | Cambiar el defecto cambia el comportamiento de todo llamador existente. Se decide con datos de uso (`AG-3`), no de golpe. Hay un test que lo fija, para que el cambio sea deliberado |
| Plan no confirmado | **No se ejecuta nada**, ni el paso sin efectos | Es lo que el arquitecto entiende por «no». Ejecutar «lo inofensivo» es lo que enseña a no leer la pantalla |
| Requisito que falta | **No impide ejecutar** el resto del plan | Es la garantía nº1 de `ejecucion.py`: un ejecutor que aborta convierte un informe parcial —útil— en ningún informe. Cada Skill se detiene sola en su paso |
| Contexto agotado | **Parar y decirlo** | Alternativa descartada: resumir el historial. Resumir es inventar en pequeño |
| Efecto ya autorizado | **Se sigue diciendo** en el plan | Que desaparezca en cuanto se autoriza es cómo el arquitecto acaba sin saber qué va a tocar su ordenador: lo autorizó una vez, hace tres pasos |

## 4. Lo que NO se ha hecho, y por qué

- **No se ha migrado a ningún framework.** Ni LangGraph, ni Deep Agents, ni
  Agno, ni PydanticAI. Instrucción explícita, y coincide con lo que ya decidió
  `docs/design/2026-08-19-auditoria-comparativa-frameworks-agenticos.md`.
- **No se ha tocado `app.py`.** La pantalla es `INF-7`; construir interfaz hoy
  estaba excluido del encargo.
- ~~**No se ejecutan en paralelo los pasos independientes** (`AG-8`)~~ —
  **hecho el mismo día, en el bloque siguiente.** Ver `AG-8` en el backlog: el
  prompt del planificador prometía al modelo que declarar independencia «es lo
  que permite ejecutarlos a la vez» y no lo permitía. Ahora sí, con lista
  blanca cerrada de efectos y la bitácora siempre en el orden de `Plan.orden()`.
- ~~**No se valida el tipo de los argumentos** de una capacidad~~ — **hecho el
  mismo día.** Ver `TL-10`: `Draft202012Validator` compilado al declarar la
  capacidad, todos los problemas a la vez y en castellano. Sin dependencias
  nuevas, como decía aquí.
- **No hay presupuesto por ejecución** (`AG-3`) ni replanificación (`AG-4`).

## 5. Qué recibe el arquitecto gracias a esto

Que pueda decir «rellena el cuadro de superficies de este plano», **ver en una
pantalla lo que ArchMuse va a hacer y qué va a escribir en su disco antes de
que lo escriba**, y decir que no sin que haya pasado nada. Es la regla 3 de
Pablo aplicada: no es infraestructura acumulada, es la única forma que hay de
enseñar el trabajo antes de hacerlo.

## 6. Cómo se comprueba

```
pytest tests/test_agente_copiloto_plan.py tests/test_agente_recorte.py
python scripts/demo_agente.py        # sección 6, sin clave y sin coste
```

18 + 12 tests nuevos. `tests/test_agente_*.py` completo: **292 pasados, 8
saltados**, excluyendo `test_agente_skill_superficies.py`, que en ese momento
lo estaba editando otra sesión (3 fallos suyos, mitad de un renombrado de
`_pregunta_legible` a `pregunta_legible`; ninguno tiene que ver con este
trabajo).

## 7. Anotado en `docs/AGENTE_BACKLOG.md`

El backlog se dejó intacto mientras la otra sesión trabajaba en `agente/skills/`
—reescribir un documento compartido a la vez es cómo se pierde el trabajo de
alguien— y se actualizó después, con su §13.5 ya escrita:

- `AG-1` y `AG-2`: alcanzables desde la fachada, con el defecto todavía en
  `VIA_BUCLE` y un test que lo fija.
- `AG-8` → `HECHO`, con qué es «seguro» y por qué la lista es blanca.
- `AG-9` (contexto largo) y `TL-10` (validación estructural de argumentos),
  entradas nuevas.
- `§13.6`, con los dos defectos menores del día: `completa` y la lista de
  efectos duplicada.
- `AG-3` sube de prioridad: con el planificador alcanzable, un plan se puede
  lanzar sin que nadie sepa lo que va a costar.
