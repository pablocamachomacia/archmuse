# OBSERVATION_MODEL.md

**Propósito:** diseñar el modelo de **Hallazgo** — la entidad que agrupa, deduplica, clasifica y sigue en el tiempo lo que el motor detecta a partir de los Facts, para que el Arquitecto vea una lista estable de asuntos reales, no una lista de disparos individuales de Rules que cambia de forma en cada re-evaluación. Sin código — como el resto de la serie, es modelo, no implementación.

> **Nota terminológica, léase antes que el resto del documento:** este archivo se llama `OBSERVATION_MODEL.md` porque así se pidió, pero la entidad que define **no es** la Observation ya especificada en `REASONING_ENGINE_SPEC.md` (entidad 4) ni en `FACT_MODEL.md`. Esa Observation ya existente es la captura cruda que **precede** a un Fact (Ingesta → Observation → validación → Fact) — inmutable, sin agrupación, sin deduplicación, sin ciclo de vida propio. Lo que este documento pide diseñar va en la **dirección contraria**: algo que nace **después** de que existan Facts (y, en la práctica, después de que existan Inferences/Problems derivados de ellos), que sí se agrupa, se deduplica, se clasifica y evoluciona en el tiempo — propiedades que la Observation original nunca tuvo ni necesita. Reutilizar el mismo nombre para las dos cosas rompería la especificación ya escrita en tres documentos previos. Este documento define esa entidad nueva bajo el nombre **Hallazgo**, y usa "Hallazgo" en todo el texto — "observación", cuando aparece, se refiere siempre a la Observation original de `REASONING_ENGINE_SPEC.md`, nunca a esta entidad nueva.

**Referencias obligatorias, asumidas como ya decididas:**
- `REASONING_ENGINE_SPEC.md` — entidad 4 (Observation, para la distinción de arriba), entidad 10 (Inference) y entidad 11 (Problem, especialización de Inference), entidad 14 (ChainEffect), entidad 15 (Conflict), entidad 18 (Evidence), entidad 19 (Explanation) — Hallazgo se construye sobre estas seis, no las sustituye.
- `FACT_MODEL.md` — en particular el id de concepto estable (§7) y el hash de contenido para deduplicación (§11.3), cuyo mismo principio de diseño se reutiliza aquí para dar identidad estable a un Hallazgo.
- `CONSTRAINT_MODEL.md` — el principio de "vocabulario cerrado, nunca código ad hoc por caso", que este documento vuelve a aplicar al definir cómo se agrupan y deduplican los Hallazgos.
- `CHAIN_REASONING.md` — el modelo de propagación (ChainEffect) y los 6 niveles de impacto (Local→Urbanístico), reutilizados como uno de los criterios de agrupación y de clasificación.
- `BRAIN_ARCHITECTURE.md` — Parte 1.8: ninguna severidad bloqueante puede quedar oculta o agregada en un promedio; invariante que este documento extiende explícitamente al roll-up de severidad de un Hallazgo.
- `PROJECT_AUDIT.md` — el caso real de `ejemplo.dxf` (unidad VT6/2, roja por eficiencia útil/total en `evaluator.py` **y**, de forma independiente, la unidad peor puntuada por `spatial_quality.py`) se usa en la sección 3 como ejemplo concreto de por qué hace falta esta entidad.

**Actor nuevo, añadido al glosario ya establecido:**
- **Motor de Síntesis de Hallazgos** — el proceso único y compartido entre los 14 dominios que, tras cada punto fijo alcanzado por el Motor de Propagación, agrupa y deduplica el conjunto de Inferences/Problems vigentes en Hallazgos, siguiendo exclusivamente los criterios cerrados de las secciones 4 y 5 — nunca lógica específica de un dominio. Mismo patrón de gobernanza que el Compositor de Hechos (`FACT_MODEL.md`) y el Intérprete de Constraints (`CONSTRAINT_MODEL.md`): una pieza única, no catorce implementaciones distintas.

---

## 1. Qué es un Hallazgo

Un Hallazgo es la unidad estable, deduplicada y clasificada de lo que el sistema tiene que comunicarle al Arquitecto sobre su proyecto — un incumplimiento normativo, una recomendación de calidad, incluso un patrón positivo digno de mención. No es una entidad de conocimiento nueva en el sentido de `REASONING_ENGINE_SPEC.md`: no razona, no evalúa Facts, no aplica Constraints. Es una capa de **síntesis y presentación con memoria propia** sobre entidades que ya existen (Inference, Problem, ChainEffect, Conflict).

La necesidad no es cosmética. Con 2 dominios y un puñado de Rules, mostrar "una tarjeta por cada Problem que dispara" es razonable. Con 14 dominios y miles de Rules, tres problemas aparecen simultáneamente si no existe esta capa:

1. **Redundancia percibida:** el mismo defecto físico puede disparar Problems independientes en dos o más dominios (el caso real de VT6/2 en `ejemplo.dxf`: baja eficiencia útil/total en `evaluator.py` y, por separado, la puntuación más baja en `spatial_quality.py` — dos sistemas de puntuación distintos confirmando el mismo problema real desde ángulos distintos). Mostrado sin agrupar, el Arquitecto ve "dos problemas" donde hay uno.
2. **Inestabilidad entre versiones:** cada Change dispara una nueva ronda de evaluación; sin una identidad estable, "el mismo" problema de pasillo estrecho parecería un hallazgo distinto cada vez que se re-evalúa, aunque el Arquitecto no haya tocado nada relacionado con él.
3. **Ruido de repetición exacta:** una Rule de AGREGACION_AMBITO (`CONSTRAINT_MODEL.md` §3.1) puede producir un Problem por cada pieza que incumple el mismo Constraint — diez dormitorios estrechos no son diez hallazgos distintos para un humano, son un patrón repetido.

Un Hallazgo resuelve los tres a la vez: agrupa lo que es, en esencia, el mismo asunto (sección 4), deduplica lo que es literalmente la misma detección repetida (sección 5), y mantiene una identidad estable que sobrevive a la re-evaluación (sección 8).

---

## 2. Atributos mínimos

| Atributo | Descripción |
|---|---|
| **id de concepto** | Estable a través de todas las versiones de ProjectState en las que el Hallazgo existe — construido a partir de la huella de deduplicación (sección 5), nunca de los ids de instancia de sus Problems/Inferences miembros |
| **id de estado** | Identifica una transición concreta de su historial de vida (sección 6) — cada transición es un registro nuevo, nunca una edición |
| **naturaleza** | Incumplimiento normativo / recomendación de calidad / patrón positivo (sección 3) |
| **miembros** | Uno o más Problems/Inferences vigentes que lo componen, cada uno con su Domain de origen |
| **ámbito(s)** | Todo ámbito (`FACT_MODEL.md` §2.3) tocado por al menos uno de sus miembros — puede abarcar más de una pieza o unidad si es un Hallazgo agregado (sección 4) |
| **dominio(s) implicados** | Uno si es un Hallazgo simple; varios si agrupa Problems de dominios distintos (Hallazgo de cadena, sección 4) |
| **severidad de presentación** | El máximo de la severidad de sus miembros — nunca un promedio (invariante heredada de `BRAIN_ARCHITECTURE.md` Parte 1.8, ver sección 4) |
| **estado de vida** | Uno de los seis valores de la sección 6 |
| **huella de deduplicación** | La clave estable que decide si una detección nueva es "la misma" que un Hallazgo ya existente (sección 5) |
| **Evidence agregada** | Unión de la Evidence de todos sus miembros — nunca una Evidence nueva inventada, solo la composición de las ya existentes |
| **historial de transiciones** | Registro append-only de cada cambio de estado de vida, con la versión de ProjectState en que ocurrió |

No lleva Confidence propia como campo independiente, por el mismo motivo que ninguna otra entidad de la serie la lleva: se calcula, y aquí se calcula como la más baja entre las Confidence de sus miembros (mismo principio de eslabón más débil de `DECISION_ENGINE.md` §10, aplicado ahora a nivel de grupo en vez de a nivel de cadena de Evidence individual).

---

## 3. Naturaleza: qué puede ser un Hallazgo

Tres tipos, no jerárquicos entre sí:

- **Hallazgo de incumplimiento** — agrupa uno o más Problems. Es, en la práctica, el tipo más frecuente y el heredero directo de lo que hoy es un `IssueReport` en `evaluator.py`, pero deduplicado y con historia.
- **Hallazgo de recomendación de calidad** — agrupa Inferences que no son Problem (no incumplen ninguna normativa Nivel 1-2) pero sí indican una oportunidad de mejora Nivel 3-4 — el equivalente a lo que hoy produce `spatial_quality.py` o `circulation.py` de forma independiente de `evaluator.py`.
- **Hallazgo positivo** — agrupa Inferences neutras que, en conjunto, confirman una fortaleza digna de mencionar (p. ej. "las seis viviendas superan el 90% de eficiencia útil/construida"). No tiene equivalente hoy en el producto — se nombra aquí porque el modelo no tiene ninguna razón estructural para limitarse a lo negativo, y `NORTH_STAR_2031.md` ya apunta a un producto de "certeza", no solo de detección de fallos.

El ejemplo de VT6/2 (sección 1) sería, en este modelo, un único Hallazgo de incumplimiento cuyos miembros son el Problem de `evaluator.py` (bloque de eficiencia útil/total) y la Inference de baja puntuación de `spatial_quality.py` — agrupados porque comparten ámbito (la misma unidad) y porque, examinada su Evidence, ambos remontan a la misma causa raíz: la superficie de terraza desproporcionada de esa vivienda.

---

## 4. Cómo se agrupan

La agrupación combina Problems/Inferences que un humano percibiría como "el mismo asunto", aunque provengan de Rules, Domains o incluso patrones de evaluación distintos. Igual que en `CONSTRAINT_MODEL.md`, esto se hace con un **catálogo cerrado de criterios de agrupación** aplicado por el Motor de Síntesis de Hallazgos — nunca con lógica particular escrita para un dominio:

| Criterio | Cuándo agrupa |
|---|---|
| **Misma causa raíz** | Dos o más Problems/Inferences cuya Evidence remonta, transitivamente, al mismo Fact (o al mismo id de concepto de Fact) en su origen — el caso de VT6/2 |
| **Cadena causal** | Dos o más Problems conectados por uno o más ChainEffect (`CHAIN_REASONING.md`) — un Hallazgo puede narrar la cadena completa como un solo asunto ("mover este tabique afecta a superficie Y a ventilación cruzada") en vez de mostrarlos como hallazgos sueltos |
| **Mismo ámbito + mismo patrón semántico declarado** | Dos Constraints distintos (posiblemente de dominios distintos) etiquetados, en su definición (`CONSTRAINT_MODEL.md` §3), con la misma categoría semántica declarada (p. ej. "proporción de pieza") y aplicados al mismo nodo de ámbito |
| **Conflicto compartido** | Dos o más Problems que son, además, los dos lados de un mismo Conflict (`REASONING_ENGINE_SPEC.md` entidad 15) — se presentan agrupados como un único Hallazgo con dos caras, no como dos hallazgos contradictorios sin relación aparente |

La agrupación **nunca** mezcla miembros de naturaleza distinta (sección 3) en un mismo Hallazgo — un incumplimiento y una recomendación de calidad pueden compartir causa raíz y aun así generar dos Hallazgos distintos vinculados entre sí (no fusionados), precisamente para no diluir un hallazgo bloqueante dentro de uno no bloqueante, la misma invariante de `BRAIN_ARCHITECTURE.md` Parte 1.8 que ya protege a Problem.

**Roll-up de severidad:** cuando un Hallazgo agrupa miembros de severidades distintas, su severidad de presentación es siempre el máximo, nunca un promedio ni una severidad "intermedia" — exactamente la misma invariante que ya protege a Problem individual, extendida aquí al nivel de grupo porque, sin esta regla explícita, agrupar sería indistinguible de diluir.

---

## 5. Cómo se deduplican

Deduplicar no es lo mismo que agrupar: agrupar combina asuntos **distintos pero relacionados**; deduplicar reconoce que una detección nueva es, en realidad, **la continuación de un Hallazgo que ya existía**, no uno nuevo. Sin esto, cada re-evaluación tras un Change produciría instancias "nuevas" de Problems ya conocidos y el Arquitecto vería crecer una lista que en realidad no ha cambiado.

La clave de deduplicación — la **huella** — se construye, deliberadamente, a partir de identificadores **estables**, nunca de identificadores de instancia que cambian en cada versión:

- el id de concepto del Constraint/Rule que originó el Problem/Inference (`CONSTRAINT_MODEL.md` §3), no el id de instancia de la Inference concreta;
- el id de concepto del nodo de ámbito afectado (`FACT_MODEL.md` §7), no el id de instancia del Fact que lo respalda;
- el criterio de agrupación aplicado (sección 4), si el Hallazgo es de más de un miembro.

Dos detecciones con la misma huella son, por definición, el mismo Hallazgo — independientemente de que el valor exacto que las originó haya cambiado (un pasillo que mide 0,83m en una versión y 0,85m en la siguiente sigue incumpliendo el mismo Constraint en el mismo ámbito: es una continuación, no un hallazgo nuevo, aunque el Fact que lo respalda sí sea una instancia distinta según `FACT_MODEL.md` §6). Esto es exactamente la misma disciplina de deduplicación por huella de contenido que `FACT_MODEL.md` §11.3 ya fijó para Facts derivados, aplicada aquí a un nivel superior — mismo principio, reutilizado, no reinventado.

**Caso AGREGACION_AMBITO:** cuando un Constraint con este patrón (`CONSTRAINT_MODEL.md` §3.1) dispara sobre múltiples nodos hijos del mismo ámbito padre (diez dormitorios estrechos), la deduplicación no colapsa los diez en uno — cada nodo hijo conserva su propia huella (incluye el id de concepto del nodo concreto) — pero el criterio de agrupación "mismo ámbito + mismo patrón semántico" (sección 4) sí los agrupa como un Hallazgo único con diez miembros, presentado como un patrón repetido y no como diez tarjetas idénticas. La distinción entre deduplicar y agrupar es exactamente lo que permite este resultado: ni "diez hallazgos" ni "un hallazgo que oculta que son diez sitios distintos".

---

## 6. Cómo evolucionan

Un Hallazgo tiene identidad estable (sección 8) y, por tanto, un ciclo de vida de verdad — a diferencia de Fact e Inference, que no "evolucionan", solo se sustituyen por una instancia nueva. El estado de vida es uno de seis, y cada transición es un registro append-only nuevo, nunca una edición del anterior — mismo principio de todo el modelo, aplicado ahora a transiciones de estado en vez de a valores:

| Estado | Significado | Transición que lo produce |
|---|---|---|
| **Nuevo** | Primera vez que esta huella se detecta | Ninguna huella previa coincidente en la versión anterior de ProjectState |
| **Persistente** | Sigue detectándose, sin cambio relevante en su severidad ni en su alcance | Misma huella, severidad y ámbito que en la versión anterior |
| **Agravado** | Sigue detectándose y su severidad o su alcance ha aumentado (más miembros, o un miembro ha subido de severidad) | Misma huella, severidad de presentación mayor o más miembros que antes |
| **Mejorado** | Sigue detectándose pero su severidad o alcance ha disminuido, sin llegar a resolverse | Misma huella, severidad de presentación menor o menos miembros que antes, pero al menos un miembro sigue vigente |
| **Resuelto** | Ya no tiene ningún miembro vigente en la versión actual de ProjectState | Ningún Problem/Inference vigente comparte su huella |
| **Reabierto** | Había pasado a Resuelto y una detección nueva coincide otra vez con la misma huella | Huella coincidente con un Hallazgo previamente Resuelto |

Un séptimo estado, **Aceptado**, no es una transición automática — se hereda de una Decision explícita del Arquitecto sobre alguno de sus miembros (`REASONING_ENGINE_SPEC.md` entidad 17, "aceptado con justificación" ya definido para Problem): un Hallazgo pasa a Aceptado cuando el Arquitecto decide, con justificación registrada, no corregirlo, y permanece así aunque su detección subyacente siga presente — nunca desaparece silenciosamente de la lista, se muestra como una decisión consciente, no como un hallazgo resuelto ni como uno ignorado.

Este historial de transiciones no es solo un detalle de UX: es exactamente el tipo de conocimiento acumulado que `BRAIN_ARCHITECTURE.md` señala como insumo futuro del Dominio 13 (Riesgo de Visado) — "este tipo de hallazgo, en proyectos parecidos, tardó una media de N revisiones en resolverse" es una pregunta que solo se puede responder si el historial de estado existe desde el principio, no si se añade después.

---

## 7. Cómo desaparecen

Nunca por borrado. "Desaparecer" de la vista activa del Arquitecto es la transición a **Resuelto** (sección 6) — el Hallazgo, como registro, permanece para siempre en el historial del proyecto, exactamente igual que Decision es "permanente e inmutable... el historial profesional de decisiones del proyecto" en `REASONING_ENGINE_SPEC.md` entidad 17. Un Hallazgo Resuelto puede Reabrirse si su huella vuelve a coincidir con una detección nueva — lo que confirma, retrospectivamente, que nunca debió tratarse como si no hubiera existido.

Un caso particular merece nombrarse: un Hallazgo agrupado (sección 4) con varios miembros no pasa a Resuelto hasta que **todos** sus miembros vigentes desaparecen — mientras quede al menos uno, el Hallazgo persiste (probablemente con un cambio de estado a Mejorado, si el conjunto se ha reducido). Esto evita el efecto perverso de que corregir una sola de varias causas relacionadas haga "desaparecer" prematuramente un asunto que, en realidad, sigue parcialmente presente.

---

## 8. Cómo se mantienen estables aunque cambie el proyecto

Este es el requisito que hace que las secciones 5 y 6 funcionen, y depende directamente de una decisión de diseño ya tomada en `FACT_MODEL.md`, no de un mecanismo nuevo: **el id de concepto de un Fact, y el id de concepto de un nodo de ámbito, son estables a través de todas las versiones de ProjectState** (`FACT_MODEL.md` §7). La huella de un Hallazgo (sección 5) se construye exclusivamente a partir de esos identificadores estables — nunca de un id de instancia, que por diseño cambia en cada sustitución (`FACT_MODEL.md` §6).

La consecuencia directa: aunque el Fact que respalda un Problem se sustituya en cada Change (una nueva instancia, con un id de instancia distinto, cada vez que algo relacionado cambia — `FACT_MODEL.md` §6), su id de concepto no cambia, y por tanto la huella tampoco — el Hallazgo que depende de esa huella sigue siendo, literalmente, el mismo registro con una nueva transición de estado (sección 6), no un registro nuevo. La estabilidad de Hallazgo no es una propiedad que este documento tenga que inventar desde cero: es una consecuencia que se obtiene gratis de haber diseñado bien la identidad de Fact — la prueba, en la práctica, de que esa decisión de `FACT_MODEL.md` §7 estaba justificada más allá de la propia capa de Facts.

Dicho de otro modo: si `FACT_MODEL.md` no hubiera separado id de concepto e id de instancia, este documento no tendría ninguna forma limpia de responder a la pregunta que el encargo hace explícita — tendría que reconstruir esa estabilidad por su cuenta, probablemente comparando valores en vez de identidades, con el mismo riesgo de colisión falsa que `FACT_MODEL.md` §11.3 ya identificó y descartó para la deduplicación de Facts.

---

## 9. Relación con el resto del modelo — y dónde termina Hallazgo

Hallazgo no sustituye ni compite con ninguna entidad ya definida:

- **No sustituye a Problem.** Un Problem sigue siendo la conclusión mecánica de una Rule sobre Facts y Constraints, con su propia Evidence. Un Hallazgo es, como mucho, uno o varios Problems vistos con memoria e identidad propia.
- **No sustituye a Conflict.** Un Conflict es tensión estructural entre Problems que requiere una Decision para resolverse. Un Hallazgo puede envolver los dos lados de un Conflict como una sola narrativa (sección 4), pero la resolución del Conflict en sí sigue viviendo en `DECISION_ENGINE.md`, no aquí.
- **No sustituye a Explanation.** La narrativa en lenguaje natural para el Arquitecto se sigue generando a partir de Evidence (`REASONING_ENGINE_SPEC.md` entidad 19) — ahora, simplemente, puede generarse a partir de la Evidence agregada de un Hallazgo en vez de la de un Problem aislado, dando una explicación coherente de un asunto que abarca varios miembros en vez de varias explicaciones sueltas que el Arquitecto tendría que relacionar por su cuenta.
- **No decide nada.** El Motor de Síntesis de Hallazgos agrupa y deduplica según los criterios cerrados de las secciones 4 y 5 — no prioriza, no descarta, no resuelve conflictos. Esa responsabilidad sigue siendo, íntegramente, del Motor de Decisión.

El riesgo de gobernanza es el mismo que ya se nombró en `FACT_MODEL.md` §12.1 y `CONSTRAINT_MODEL.md` §14, y se repite aquí a propósito porque es el mismo patrón exacto: el catálogo cerrado de criterios de agrupación (sección 4) es lo único que impide que el Motor de Síntesis se convierta, con el tiempo, en un lugar donde cada dominio inyecta su propia lógica particular de "cuándo dos cosas son la misma". Mantenerlo cerrado y gobernado centralizadamente no es una preferencia de estilo — es, a estas alturas de la serie, la condición estructural que se repite en cada capa nueva para que el sistema entero siga siendo coherente a 14 dominios y miles de reglas.
