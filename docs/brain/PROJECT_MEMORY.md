# PROJECT_MEMORY.md

**Propósito:** diseñar la memoria del proyecto como sistema — no una entidad nueva por descubrir, sino la organización, indexación y dinámica temporal de seis categorías que, examinadas una por una, ya están modeladas en documentos anteriores. Lo que falta, y lo que aporta este documento, es la pieza que las une: una unidad de tiempo intermedia entre "una versión" y "todo el proyecto" — la **sesión** — y la explicación de cómo la memoria se acumula mientras una sesión está activa y qué ocurre con ella cuando se cierra. Sin código, como el resto de la serie.

**Referencias obligatorias, asumidas como ya decididas:**
- `REASONING_ENGINE_SPEC.md` — entidad 1 (ProjectState, el contenedor raíz versionado), entidad 3 (Change, con su atributo ya existente "referencia a si forma parte de una sesión de edición más amplia" — este documento formaliza qué es esa sesión), entidad 7 (Assumption), entidad 13 (Preference), entidad 16 (Alternative), entidad 17 (Decision, "memoria institucional").
- `CHAIN_REASONING.md` — §1, el registro corriente ("running log") de cambios de una sesión de edición que alimenta la detección de efectos acumulativos. Este documento no redefine ese mecanismo, precisa cuándo se ejecuta dentro del ciclo de vida de una sesión (sección 3).
- `FACT_MODEL.md` — §11.1, la separación entre histórico append-only y proyección de estado vigente. Este documento reutiliza el mismo principio un nivel más arriba, para la memoria del proyecto en su conjunto, y añade una tercera granularidad de consulta: el resumen de sesión (sección 4).
- `OBSERVATION_MODEL.md` — §6, el ciclo de vida de Hallazgo (nuevo/persistente/agravado/mejorado/resuelto/reabierto/aceptado), reutilizado en la sección 1 para "problemas resueltos".
- `CONFLICT_ENGINE.md` — §4, el Verificador de Precedente, que consume directamente la memoria de Decisions que este documento organiza.
- `EXPLANATION_ENGINE.md` — §4, los tres niveles cerrados (Resumen/Estándar/Completa), reutilizados en la sección 4 para el resumen de sesión.

**Entidad nueva, ligera, añadida al modelo:**
- **Sesión** — una ventana de tiempo acotada sobre la cadena de versiones de ProjectState, dentro de la cual ocurren uno o más Changes propuestos por el Arquitecto. No es una entidad de conocimiento (no razona, no tiene Evidence propia) — es la unidad organizativa que le faltaba a la memoria del proyecto para responder, con sentido, a la pregunta "qué pasó mientras trabajaba hoy" sin obligar al Arquitecto a pensar en términos de números de versión.

**Actor nuevo, añadido al glosario ya establecido:**
- **Consolidador de Sesión** — el proceso que, al cerrarse una Sesión, ejecuta la comprobación final de efectos acumulativos sobre el registro completo de esa sesión (`CHAIN_REASONING.md` §1) y genera su resumen (sección 4) — nunca colapsa ni sustituye el detalle completo, que permanece accesible sin cambios. Mismo patrón de gobernanza que los siete actores ya nombrados en la serie: una pieza única, no una implementación distinta por sesión o por dominio.

---

## 0. Principio rector

La memoria del proyecto nunca pierde detalle al consolidarse. Un resumen de sesión, un índice de vigencia actual, una lista de "problemas resueltos" — todos son **proyecciones adicionales** sobre el histórico append-only que cada documento anterior de la serie ya garantiza, nunca sustitutos de él. Esto no es una preferencia de diseño, es una consecuencia directa del principio que sostiene toda la serie desde `REASONING_ENGINE_SPEC.md`: nada se edita, nada se sobrescribe, todo cambio deja un rastro verificable. Este documento no reintroduce esa garantía — la extiende hasta el nivel en que el Arquitecto realmente interactúa con la memoria: no versión a versión, sino sesión a sesión y proyecto a proyecto.

---

## 1. Las seis categorías — y qué añade este documento a cada una

Las seis ya tienen una entidad que las modela. Este documento no las redefine — organiza cómo se acumulan y se consultan:

| Categoría pedida | Entidad que ya la modela | Qué añade este documento |
|---|---|---|
| **Cambios** | Change (`REASONING_ENGINE_SPEC.md` entidad 3) | Cómo se agrupan en Sesiones (sección 2) |
| **Versiones** | ProjectState (entidad 1) | Una tercera granularidad de consulta, intermedia entre versión individual e histórico completo (sección 4) |
| **Decisiones** | Decision (entidad 17) | Cómo alimentan al Verificador de Precedente (`CONFLICT_ENGINE.md` §4) y quedan disponibles para consulta por tema, no solo por orden cronológico (sección 5) |
| **Preferencias** | Preference (entidad 13) | Cómo se conserva su alcance temporal declarado — "solo esta decisión" o "todo el proyecto" — a través de sesiones sucesivas (sección 5) |
| **Hipótesis descartadas** | Assumption retirada (entidad 7) + Alternative no elegida (entidad 16) | Por qué ambas son, a efectos de memoria, la misma categoría (sección 1.1) |
| **Problemas resueltos** | Problem resuelto (entidad 11) + Hallazgo resuelto/reabierto (`OBSERVATION_MODEL.md` §6) | Cómo se distingue, en la memoria a largo plazo, "resuelto una vez" de "resuelto y reabierto varias veces" (sección 5) |

### 1.1 Por qué Assumption retirada y Alternative no elegida son una sola categoría de memoria

Una Assumption retirada (sustituida por un Fact real) y una Alternative no elegida (`REASONING_ENGINE_SPEC.md` entidad 16, "queda archivada tanto si se elige como si se descarta") describen, en apariencia, dos cosas distintas — una es una hipótesis sobre un dato, la otra es un camino de acción no tomado. Pero ambas responden a la misma necesidad de memoria: **un camino que se consideró razonable en su momento y que el proyecto terminó no siguiendo**, conservado precisamente para que una sesión futura no vuelva a evaluarlo desde cero sin saber que ya se consideró. Tratarlas como una sola categoría a efectos de consulta ("¿qué se descartó, y por qué?") es lo que permite, por ejemplo, que el Verificador de Precedente (`CONFLICT_ENGINE.md` §4) responda no solo "qué se decidió" sino "qué alternativas se compararon antes de decidir eso" — el contexto completo, no solo el resultado final.

---

## 2. Sesión: la unidad de tiempo que faltaba

Una Sesión agrupa una secuencia contigua de Changes propuestos por el Arquitecto, junto con todo lo que ocurre como consecuencia directa de ellos dentro de esa ventana: nuevas versiones de ProjectState, Conflicts abiertos o cerrados, Decisions tomadas, Hallazgos que cambian de estado.

**Atributos:** identificador, timestamp de inicio, timestamp de fin (abierto mientras la sesión está activa), el rango de versiones de ProjectState que abarca, y la lista de Changes que contiene, en el orden en que se propusieron — aceptados o descartados, ambos se conservan (mismo principio ya fijado para Change en `REASONING_ENGINE_SPEC.md` entidad 3: un Change descartado no genera nueva versión, pero sigue siendo un registro histórico).

**Ciclo de vida:** una Sesión empieza con el primer Change que el Arquitecto propone tras un periodo sin actividad (o de forma explícita, si el Arquitecto la abre deliberadamente) y se cierra de dos formas — explícitamente, cuando el Arquitecto termina de trabajar, o por un periodo de inactividad suficientemente largo como para asumir que la sesión de trabajo terminó. Una vez cerrada, es append-only como cualquier otra entidad de la serie: no se reabre, no se edita — si el Arquitecto vuelve más tarde, empieza una Sesión nueva, que puede perfectamente continuar exactamente donde la anterior lo dejó, sin que eso implique fusionar los dos registros en uno.

---

## 3. Cómo evoluciona la memoria durante una sesión

Dentro de una sesión activa, cada Change aceptado extiende la cadena de versiones de ProjectState exactamente como ya describe `REASONING_ENGINE_SPEC.md` — este documento no cambia ese mecanismo. Lo que añade es la forma en que esa acumulación se hace útil **mientras la sesión sigue abierta**, no solo al final:

- **La comprobación de efectos acumulativos (`CHAIN_REASONING.md` §1) se re-ejecuta después de cada Change dentro de la sesión activa**, sobre el registro corriente acumulado hasta ese momento — nunca se aplaza hasta el cierre de la sesión. Esto es una precisión necesaria sobre el mecanismo ya existente: un registro corriente que solo se consultara al final llegaría demasiado tarde para que el Arquitecto pudiera actuar sobre un efecto acumulativo mientras todavía está trabajando activamente en la zona del proyecto donde ese efecto importa.
- **Cualquier consulta de memoria hecha a mitad de sesión refleja "todo lo ocurrido hasta ahora en esta sesión"**, no solo el estado final — el Arquitecto puede pedir, en cualquier momento, un resumen de lo que ha cambiado desde que empezó a trabajar hoy (sección 4), sin tener que esperar a cerrar la sesión para obtenerlo.
- **Los Hallazgos (`OBSERVATION_MODEL.md`) transicionan de estado en tiempo real dentro de la sesión**, no en un lote al final — cada Change que resuelve o agrava un Hallazgo produce esa transición inmediatamente, visible antes de que la sesión se cierre.

La sesión, mientras está abierta, no es una unidad de consolidación — es, simplemente, el marco que permite responder "qué ha pasado hasta ahora" sin recorrer manualmente la cadena completa de versiones desde el origen del proyecto.

---

## 4. Cómo se cierra una sesión y qué se consolida

Al cerrarse, el Consolidador de Sesión hace dos cosas, ninguna de las cuales sustituye el registro detallado que ya existe:

1. **Un último pase de efectos acumulativos**, sobre el registro completo de la sesión ya cerrada — la comprobación final, después de que ya no puede haber más Changes que añadir a esa ventana concreta.
2. **Un resumen de sesión**, generado con el mismo mecanismo de niveles ya fijado en `EXPLANATION_ENGINE.md` §4 (Resumen/Estándar/Completa) aplicado aquí no a una única conclusión sino al conjunto de la sesión: qué Changes se propusieron y cuáles se aceptaron, qué Conflicts se abrieron y cómo se cerraron (o si quedaron abiertos, `CONFLICT_ENGINE.md`), qué Hallazgos cambiaron de estado, qué Decisions se tomaron.

El resumen es una **proyección adicional**, no un reemplazo — el registro Change a Change de la sesión permanece disponible con el mismo detalle que tenía mientras la sesión estaba activa. Esto reproduce, un nivel por encima, exactamente la misma separación que `FACT_MODEL.md` §11.1 ya estableció entre histórico append-only y proyección de lectura: el resumen de sesión es a la sesión lo que la "vista vigente" es a un Fact — una forma más rápida de consultar lo mismo, nunca una versión con menos información que la fuente.

---

## 5. Cómo se consulta la memoria más allá de la sesión activa

A escala de todo el proyecto, la memoria deja de organizarse por sesión y se organiza por tema — el Verificador de Precedente (`CONFLICT_ENGINE.md` §4) ya depende de poder preguntar "¿hubo antes una Decision sobre este tipo de tensión?" sin que importe en qué sesión ocurrió. Este documento generaliza esa capacidad de consulta a las seis categorías:

- **Decisions por tema** — no solo orden cronológico, también agrupables por el tipo de Conflict que resolvieron o el Domain implicado, que es exactamente lo que el Verificador de Precedente necesita.
- **Assumptions todavía sin resolver** — una vista directa de qué hipótesis siguen activas en el proyecto en un momento dado, útil para que el Arquitecto sepa, sin tener que recorrer Hallazgos uno a uno, cuánta de la evaluación actual del proyecto descansa sobre supuestos en vez de datos confirmados.
- **Hallazgos reabiertos más de una vez** — una consulta derivada, no una entidad nueva: un Hallazgo cuyo historial de transiciones (`OBSERVATION_MODEL.md` §6) contiene más de un ciclo Resuelto→Reabierto es, en la práctica, una señal de problema recurrente o mal corregido de raíz, y vale la pena que sea visible como tal en vez de aparecer solo como "un hallazgo más" en la lista activa. Es el mismo tipo de conocimiento acumulado que `BRAIN_ARCHITECTURE.md` ya anticipa como insumo futuro de los Dominios 12 y 13 — aquí, simplemente, se hace consultable desde el primer día en vez de esperar a que esos dominios existan para empezar a registrarlo.

---

## 6. Qué no hace esta memoria, todavía

Dos límites deliberados, coherentes con los ya fijados en documentos anteriores:

- **No hay memoria entre proyectos.** Todo lo descrito aquí — sesiones, resúmenes, consultas por tema — vive dentro de un único proyecto. Extenderlo entre proyectos es, otra vez, territorio de los Dominios 13/14 (`BRAIN_ARCHITECTURE.md`), gated hasta que exista un dataset real acumulado — mismo límite ya trazado en `CONFLICT_ENGINE.md` §4 y `UNCERTAINTY_MODEL.md`, no una omisión de este documento.
- **La memoria no ajusta nada por sí sola.** Que un patrón se repita en la memoria del proyecto (un Hallazgo reabierto varias veces, una Assumption que siempre termina confirmándose) no mueve ningún umbral, no relaja ningún Constraint, no cambia ningún comportamiento del motor automáticamente. Es información que se muestra al Arquitecto y al Curador de Conocimiento — cualquier ajuste real de umbrales o catálogos, si algún día se justifica por estos patrones, pasa por el mismo proceso de gobernanza deliberada que ya rige cada catálogo cerrado de la serie, nunca por un mecanismo de autoaprendizaje silencioso.

---

## Cierre

El riesgo real de este documento, si algo falla, no es que se pierda memoria — el append-only ya lo impide estructuralmente en cada entidad individual desde el primer documento de la serie. El riesgo es de **oportunidad**: que la comprobación de efectos acumulativos se implemente, por comodidad, solo al cierre de la sesión en vez de tras cada Change, dejando al Arquitecto sin la posibilidad real de actuar mientras todavía está trabajando en la zona del proyecto donde ese efecto importa. Es un fallo silencioso en el mismo sentido que los ya nombrados en documentos anteriores: nada se rompe de forma visible, el sistema simplemente llega tarde con información que, a tiempo, habría cambiado una decisión.
