# RECOMMENDATION_ENGINE.md

**Propósito:** diseñar el mecanismo completo por el que el sistema deja de limitarse a señalar qué está mal y empieza a proponer, de forma trazable y honesta, cómo podría corregirse — generación de Alternatives, su evaluación real (no supuesta), su comparación, los criterios de descarte, la justificación que las acompaña, y tres dimensiones que ningún documento anterior de la serie había desarrollado todavía: coste, impacto y reversibilidad. Recommendation y Alternative ya existen como entidades (`REASONING_ENGINE_SPEC.md` entidades 12 y 16) — este documento no las redefine, les da el mecanismo operativo que les faltaba, de la misma forma en que `CHAIN_ENGINE.md` le dio mecanismo a ChainEffect. Sin código, como el resto de la serie.

**Referencias obligatorias, asumidas como ya decididas:**
- `REASONING_ENGINE_SPEC.md` — entidad 12 (Recommendation) y entidad 16 (Alternative), con su invariante ya fijada: ninguna Alternative se presenta sin haber sido re-evaluada por el Motor de Propagación.
- `DECISION_ENGINE.md` — el flujo de 12 pasos completo, §7 (criterio binario de entrada: ¿resuelve la infracción bloqueante?), §3 (jerarquía de 5 criterios de prioridad), y su gap ya nombrado explícitamente: coste/presupuesto no tiene dominio propio, se trata como preferencia/restricción externa declarada, no como algo que el sistema evalúe — este documento respeta ese gap sin intentar cerrarlo (sección 6).
- `CHAIN_REASONING.md` — las 8 familias de cambio y los 6 niveles de impacto, reutilizados aquí como el vocabulario cerrado con el que se generan Alternatives (sección 1) y se clasifica su reversibilidad (sección 8).
- `CHAIN_ENGINE.md` — §5, el modo especulativo de propagación — el mecanismo exacto con el que se evalúa cada Alternative (sección 2) — y §1, el grafo instanciado, cuyo tamaño alcanzable se reutiliza aquí como proxy no fabricado de coste (sección 6).
- `CONFLICT_ENGINE.md` — §2 (la jerarquía de prioridad como filtro secuencial) y §4 (el mecanismo de huella y el Verificador de Precedente), ambos reutilizados sin cambios para comparar Alternatives entre sí (sección 3) y para deduplicarlas (sección 4).
- `ARCHITECTURAL_QUALITY.md` — §2 (los tres niveles A/B/C de aproximación) y §3 ("espejo, no juez") — la frontera que decide quién puede generar una Alternative para un problema dado (sección 0).

**Actor nuevo, añadido al glosario ya establecido:**
- **Generador de Alternativas** — el subproceso del Motor de Decisión que aplica el catálogo cerrado de patrones de transformación (sección 1) para producir candidatos de Alternative ante un Problem o Conflict de Nivel 1-2. Se nombra aparte porque su alcance está deliberadamente limitado — nunca opera sobre contenido de Nivel 3-4 (sección 0) — y esa limitación tiene que quedar tan visible como el propio mecanismo que sí tiene permitido usar.

---

## 0. El cambio de postura, y su límite honesto

Detectar un incumplimiento es una operación mecánica: una Rule compara un Fact contra un Constraint. Proponer una solución es otra cosa — implica generar una acción concreta que no estaba dada, evaluarla en sus consecuencias reales, y defenderla frente a alternativas. Este documento existe para que el sistema haga eso, no solo lo primero.

Pero el límite fijado en `ARCHITECTURAL_QUALITY.md` §3 ("espejo, no juez") no desaparece aquí — se traduce en una frontera concreta sobre **quién genera** la Alternative, no sobre si se genera:

- **Para un Problem o Conflict de Nivel 1-2** (una restricción geométrica o normativa incumplida), el Generador de Alternativas puede proponer candidatos activamente, aplicando el catálogo cerrado de la sección 1 — es terreno mecánico, con un espacio de soluciones acotado y verificable.
- **Para un asunto de Nivel 3-4** (un Hallazgo de calidad espacial, una tensión de intención de diseño), el sistema **no inventa** la solución — el mismo límite de `ARCHITECTURAL_QUALITY.md` §3 aplicado aquí a su consecuencia natural: un sistema que no tiene autoridad para juzgar si una solución es elegante tampoco la tiene para proponerla como si lo fuera. Lo que sí puede hacer es recibir una o más Alternatives que el propio Arquitecto proponga, y aplicarles exactamente el mismo mecanismo de evaluación, comparación, coste, impacto y reversibilidad de este documento (secciones 2-8) — la parte de "espejo" no es "no ayudar", es "no fingir criterio de diseño que no tiene".

---

## 1. Generación de alternativas

El Generador de Alternativas nunca inventa una transformación libre — aplica uno o más patrones de un **catálogo cerrado de patrones de transformación**, gobernado por el Curador de Conocimiento con la misma disciplina que el catálogo de patrones de evaluación (`CONSTRAINT_MODEL.md` §3.1) o el de composición de Facts (`FACT_MODEL.md` §4). El catálogo está organizado, precisamente, alrededor de las 8 familias de cambio ya fijadas en `CHAIN_REASONING.md` §1 — cada familia de cambio es, vista desde este documento, un tipo de transformación que un patrón de generación puede proponer: ajustar un límite geométrico, abrir o cerrar un hueco, reasignar una superficie/uso, desplazar un elemento vertical, etc.

Ante un Problem o Conflict concreto, el Generador:

1. Identifica qué familia(s) de cambio podrían, en principio, alterar el Fact que causa el incumplimiento.
2. Instancia uno o más candidatos concretos dentro de esa familia (p. ej., para un pasillo estrecho: ampliar el hueco desplazando el tabique adyacente, o reasignar la pieza colindante para ceder superficie — dos candidatos de la misma familia "límite geométrico").
3. **Siempre incluye, como candidato de referencia, la Alternative de no-acción** — aceptar el Problem con justificación (`REASONING_ENGINE_SPEC.md` entidad 11) — no como una opción menor, sino como el punto de comparación contra el que cualquier otra Alternative tiene que demostrar que compensa su propio coste (sección 6).

Ningún candidato entra en la comparación (sección 3) sin pasar antes por la evaluación completa (sección 2) — generar una Alternative nunca es, por sí solo, proponerla.

---

## 2. Evaluación

Cada candidato generado se evalúa ejecutando una propagación completa en **modo especulativo** (`CHAIN_ENGINE.md` §5) — la misma cola de trabajo que procesa un Change real, sobre una copia aislada del estado, sin escribir nunca en el histórico permanente. Esto no es una aproximación rápida del efecto de la Alternative — es la propagación real, completa, incluyendo los saltos entre Domains que le correspondan, exactamente como si el Change se hubiera aceptado de verdad.

De esa corrida especulativa se extrae:

- **¿Resuelve el Problem o Conflict original?** — criterio binario de entrada, ya fijado en `DECISION_ENGINE.md` §7; si no lo resuelve, el candidato no pasa de aquí (sección 4).
- **Qué Problems nuevos introduce**, con su severidad — el propio grafo de propagación especulativa los revela, no hace falta un análisis aparte.
- **Qué Hallazgos nuevos aparecen o cuáles desaparecen** (`OBSERVATION_MODEL.md`) — el efecto neto sobre lo que el Arquitecto vería si aceptara esta Alternative.
- **Qué Conflicts nuevos introduce**, incluyendo, si es el caso, un Conflict contra la propia intención de diseño declarada (`ARCHITECTURAL_QUALITY.md` §4) — una Alternative que resuelve un Problem normativo desplazando el tabique que sostenía la planta fluida que el Arquitecto declaró querer es, en sí misma, un Conflict Tipo 2 nuevo, y debe aparecer como tal en su evaluación, no descubrirse después de aceptarla.

Ninguna de estas cuatro comprobaciones es un mecanismo nuevo — todas ya existen en documentos anteriores. Lo que este documento fija es que las cuatro se ejecutan **siempre**, sobre **cada** candidato, antes de que ninguno llegue a la fase de comparación.

---

## 3. Comparación

Los candidatos que superan la evaluación (sección 2) se comparan entre sí con el mismo **filtro secuencial de 5 criterios** ya fijado en `CONFLICT_ENGINE.md` §2 (nivel de bloqueo > nivel de impacto > reversibilidad > confianza > preferencia) — no se reinventa un mecanismo de comparación distinto para N alternativas cuando ya existe uno correcto para dos lados de un Conflict; se aplica el mismo, extendido de forma natural: en cada nivel del filtro, se eliminan los candidatos que un competidor supera claramente, y se pasa al nivel siguiente solo con los que siguen empatados.

**Si más de un candidato sobrevive los cinco niveles, no se fuerza un ganador único** — se presentan todos como igualmente válidos, exactamente la misma invariante que `REASONING_ENGINE_SPEC.md` entidad 16 ya fija ("cuando un Conflict tiene varias soluciones igualmente válidas, deben existir como mínimo dos Alternatives registradas"). Elegir arbitrariamente uno de varios candidatos empatados para presentar como "la" recomendación sería el mismo desempate silencioso que `CONFLICT_ENGINE.md` §2 ya prohíbe para Conflicts, aplicado aquí a Alternatives — no hay ninguna razón para tratarlo de forma distinta solo porque el contexto es una recomendación en vez de un conflicto.

---

## 4. Descarte

Un candidato se descarta, **antes** de entrar en comparación, si cumple cualquiera de estos cuatro criterios cerrados:

| Criterio | Cuándo se aplica |
|---|---|
| **No resuelve el problema de entrada** | Falla el criterio binario de la sección 2 — nunca llega a compararse con nada |
| **Intercambio neto negativo** | Introduce uno o más Problems nuevos de severidad igual o peor que el que resuelve — cambiar un incumplimiento por otro no es una solución |
| **Viola un límite declarado como no negociable** | El Arquitecto marcó explícitamente, como parte de una Preference (`REASONING_ENGINE_SPEC.md` entidad 13), que cierto elemento no está sobre la mesa — un candidato que lo toca se descarta sin comparar, nunca se presenta "por si acaso" |
| **Duplicado** | Misma huella que otro candidato ya generado (mismo mecanismo de `OBSERVATION_MODEL.md` §5 / `CONFLICT_ENGINE.md` §4, aplicado aquí a Alternatives: mismo Change propuesto en esencia, aunque los ids de instancia difieran) |

Un candidato descartado **nunca se borra** — queda archivado con el motivo del descarte, mismo principio ya fijado en `REASONING_ENGINE_SPEC.md` entidad 16 ("queda archivada tanto si se elige como si se descarta") — la razón del descarte es, en sí misma, información útil si una situación parecida vuelve a aparecer (`CONFLICT_ENGINE.md` §4, el Verificador de Precedente consulta también candidatos descartados, no solo los elegidos).

---

## 5. Justificación

La Evidence de una Recommendation (`EVIDENCE_MODEL.md`) incluye, para cada Alternative que llegó a compararse (elegida o no) — nunca solo para la ganadora —, su propia Evidence completa de la evaluación especulativa (sección 2) más la **traza de comparación**: en qué nivel del filtro de 5 criterios (sección 3) quedó eliminada, o si sobrevivió los cinco. Es exactamente el mismo tipo de traza que `CONFLICT_ENGINE.md` §3 ya exige para el desempate entre dos lados de un Conflict, generalizada aquí a N candidatos.

La Explanation resultante (`EXPLANATION_ENGINE.md`) narra, con el mismo peso, no solo la Alternative recomendada sino por qué las demás no lo fueron — nunca presenta la elegida como si fuera la única opción considerada. Cuando varios candidatos sobreviven empatados (sección 3), la Explanation lo dice así explícitamente, con las mismas reglas ya fijadas para un Conflict Tipo 5 (`EXPLANATION_ENGINE.md` §7): una discrepancia real entre opciones igualmente válidas no se disfraza de una elección clara.

---

## 6. Coste

**Coste, en este documento, nunca es una cifra económica.** `DECISION_ENGINE.md` ya nombra explícitamente ese vacío — presupuesto y coste económico no tienen dominio propio, se tratan como restricción externa declarada por el Cliente a través del Arquitecto, nunca como algo que el sistema calcule — y este documento no lo cierra ni finge cerrarlo; inventar una cifra de coste económico sería, exactamente, repetir el error ya señalado de `TIPOLOGIA_BENCHMARKS`, ahora aplicado a euros en vez de a un percentil.

Lo que sí se puede medir, sin fabricar nada, es el **alcance de la modificación** — y aquí hay una señal real y no inventada disponible: el propio tamaño del subgrafo alcanzado durante la evaluación especulativa (`CHAIN_ENGINE.md` §1, §8) de cada candidato. Una Alternative cuya propagación especulativa toca tres nodos tiene, objetivamente, menor alcance que una que toca cuarenta — no es una estimación, es el resultado directo de un cálculo que ya se hizo por otro motivo (sección 2). Este alcance, combinado con la familia de cambio de `CHAIN_REASONING.md` §1 que la origina (un ajuste de "límite geométrico" es, por naturaleza, más contenido que una "agregación de unidades"), se traduce en una calificación cualitativa cerrada — Bajo / Medio / Alto — nunca un número que sugiera una precisión de coste que el sistema no tiene ni pretende tener.

---

## 7. Impacto

Reutiliza directamente los 6 niveles ya fijados en `CHAIN_REASONING.md` (Local→Urbanístico), aplicados al alcance real que la evaluación especulativa (sección 2) reveló para cada candidato — no una estimación previa, el resultado observado de la propia corrida. Se combina con el efecto neto sobre Hallazgos (cuántos se resuelven, cuántos nuevos aparecen, sección 2) para dar una imagen completa: dos Alternatives pueden tener el mismo nivel de impacto geométrico y, aun así, diferir mucho en cuántos Hallazgos de calidad (`OBSERVATION_MODEL.md`) desplazan a su paso — ambas dimensiones se muestran, nunca se colapsan en un único número de "impacto total".

---

## 8. Reversibilidad

Cada familia de cambio de `CHAIN_REASONING.md` §1 lleva asociado un **techo de reversibilidad**, cerrado y gobernado por el Curador de Conocimiento, igual que la tabla de techos de fuerza de `EVIDENCE_MODEL.md` §3: una apertura de hueco es, por naturaleza, de reversibilidad Alta (deshacer el Change es tan simple como no aplicarlo, mientras el proyecto siga en fase de diseño); una agregación de unidades o un cambio de volumen/emplazamiento son, por naturaleza, de reversibilidad Baja, porque alteran decisiones de las que dependen, a su vez, muchas otras. Este techo es el mismo dato que ya alimenta el tercer criterio de la jerarquía de prioridad de `DECISION_ENGINE.md` §3 — este documento no añade un criterio nuevo, precisa de dónde sale el valor que ese criterio ya usaba sin especificar su origen.

Una nota para el futuro, no resuelta aquí: la reversibilidad real depende también de la fase del proyecto — un Change es más reversible sobre un plano que sobre una obra ya iniciada. ArchMuse hoy solo razona sobre fase de diseño, así que esta distinción no tiene ningún efecto todavía — se deja anotada para que una futura extensión a fases posteriores del proyecto no tenga que redescubrir que la reversibilidad no es una propiedad fija de la familia de cambio sola, sino de la familia combinada con el momento en que se propone.

---

## Cierre

El riesgo central de este documento es una variante directa del ya nombrado en `ARCHITECTURAL_QUALITY.md`: el Generador de Alternativas, bajo la presión de "dar siempre una solución", extendiéndose silenciosamente hacia territorio de Nivel 3-4 que la sección 0 le prohíbe explícitamente — proponiendo, con la misma confianza mecánica con la que resuelve un pasillo estrecho, una solución a un problema de calidad espacial que en realidad no puede generar de forma responsable. Es "espejo, no juez" otra vez, ahora como "espejo, no diseñador": el sistema puede evaluar, comparar, costear y calificar la reversibilidad de cualquier Alternative que se le presente — la generase él mismo o la propusiera el Arquitecto — pero solo tiene autoridad para generarla activamente en el territorio mecánico donde el resto de la serie ya demostró que puede razonar sin fingir un criterio que no tiene.
