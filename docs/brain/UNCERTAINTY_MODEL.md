# UNCERTAINTY_MODEL.md

**Propósito:** diseñar el modelo completo de incertidumbre — distinguir con precisión cuatro conceptos que, sin esta separación, tienden a colapsarse entre sí en cualquier sistema que crece rápido: Missing Data, Unknown, Assumption y Estimation. La exigencia del encargo, "nunca convertir Unknown en un valor por defecto", es el motivo de ser de todo el documento, no una restricción añadida al final — es, literalmente, el Bug #1 ya confirmado en `TECH_REVIEW.md` (tipología/zona_cte cayendo a un valor por defecto sin que nadie lo supiera), y este documento existe para que ese patrón de fallo deje de tener dónde esconderse, en ninguna de sus cuatro formas posibles. Sin código, como el resto de la serie.

**Referencias obligatorias, asumidas como ya decididas:**
- `REASONING_ENGINE_SPEC.md` — entidad 4 (Observation), entidad 6 (Unknown) y entidad 7 (Assumption). Este documento amplía la entidad 6 en un punto concreto y lo señala explícitamente en la sección 3.
- `FACT_MODEL.md` — el eje de origen epistémico de Fact (§2.1: observado/derivado/promovido). Este documento le añade un cuarto valor, **estimado**, y lo señala explícitamente en la sección 4 — misma disciplina de extensión declarada que `CONSTRAINT_MODEL.md` ya aplicó al ampliar el reparto Constraint/Rule original.
- `EVIDENCE_MODEL.md` — la tabla de techos que califica la fuerza de un tramo (§3). Este documento añade la fila correspondiente a Fact estimado (sección 7).
- `CONSTRAINT_MODEL.md` — §4, el estado "Constraint no evaluable" que resulta de un Unknown sin resolver; §9, la filosofía de tabla de resolución cerrada y gobernada, reutilizada aquí para el catálogo de métodos de estimación.
- `DECISION_ENGINE.md` — §12, el protocolo de información insuficiente completo (apalancamiento de decisión, recomendación condicional en vez de default silencioso) — es el mecanismo de triaje que decide qué hacer con un Unknown, y este documento no lo repite, lo aplica a los cuatro conceptos.
- `EXPLANATION_ENGINE.md` — §8, la distinción ya fijada entre "Confidence Media/Baja" y "Unknown sin resolver" como dos narrativas distintas — este documento añade una tercera narrativa obligatoria para Estimation (sección 8).
- Grounding real: `analyzer/evaluator.py`, el proxy de superficie de ventana (`facade_width × 0.25`, reutilizado deliberadamente por los bloques 15 y 19 según `archmuse-project` — memoria de proyecto) es, hoy, una Estimation real sin ese nombre — el ejemplo concreto que ancla la sección 5.

**Actor nuevo, añadido al glosario ya establecido:**
- **Estimador** — el proceso único y compartido entre los 14 dominios que aplica métodos de aproximación del catálogo cerrado (sección 5) para producir un Fact de origen "estimado". Se nombra deliberadamente distinto del Compositor de Hechos (`FACT_MODEL.md` §4): el Compositor solo hace composición exacta sobre datos ya conocidos con certeza; el Estimador siempre introduce una aproximación declarada. Confundirlos permitiría que una aproximación se disfrazara de cálculo exacto — la misma frontera que `FACT_MODEL.md` §4 ya defendió entre Fact derivado e Inference, aplicada aquí a un tercer caso que ese documento no cubría.

---

## 0. Principio rector

Un Unknown nunca se convierte en un valor por defecto — ni de forma directa (asignarle un valor "razonable" sin decirlo) ni de forma indirecta (convertirlo silenciosamente en una Estimation o una Assumption sin que quede marcado como tal, o generalizar un método de estimación a casos para los que no fue validado). Las cuatro entidades de este documento existen, precisamente, para que el sistema nunca tenga que "elegir algo y seguir" sin dejar rastro de que lo hizo: siempre hay una vía disciplinada — quedarse en Unknown y detener la evaluación que lo necesita, aplicar una Estimation de un catálogo gobernado y decirlo, o adoptar una Assumption declarada y decirlo. Ninguna de las tres es un default silencioso. El riesgo real de este documento, nombrado aquí para que gobierne cada sección que sigue, es que Estimation se convierta con el tiempo en una forma más sofisticada de hacer exactamente lo que Bug #1 hizo — la defensa no es una propiedad del modelo de datos, es la disciplina de que el catálogo de métodos de estimación (sección 5) nunca se aplique fuera de lo que cubre explícitamente.

---

## 1. Los cuatro conceptos y cómo se distinguen

No son sinónimos ni grados de lo mismo — cada uno responde a una pregunta distinta:

| Concepto | Qué es | Cuándo nace | ¿Tiene un valor asignado? | ¿Bloquea una evaluación? |
|---|---|---|---|---|
| **Missing Data** | Un hueco conocido en los datos capturados, exista o no, hoy, una Rule que lo necesite | En Ingesta, tan pronto se reconoce el hueco — **proactivo** | No | No, por sí solo — es inventario, no un bloqueo activo |
| **Unknown** | La manifestación concreta de que una Rule necesita un dato y no existe como Fact, Estimation ni Assumption | En evaluación, cuando una Rule lo pide — **reactivo, bajo demanda** | No | Sí — el Constraint/Rule que lo requiere queda "no evaluable" (`CONSTRAINT_MODEL.md` §4) |
| **Estimation** | Un valor calculado por un método de aproximación declarado y gobernado, cuando no hay Fact real pero sí un proxy fiable para ese tipo de dato | Cuando el Estimador aplica un método del catálogo cerrado a un Unknown concreto | Sí, con techo de confianza Media (nunca Alta) | No — permite evaluar, con confianza limitada y marcada como tal |
| **Assumption** | Una hipótesis declarada explícitamente para cubrir un Unknown cuando no hay ni Fact ni método de Estimation aplicable | Cuando el Motor de Decisión decide cubrir un Unknown de bajo apalancamiento sin proxy disponible | Sí, con techo de confianza Media/Baja | No — permite evaluar, con confianza limitada y marcada como tal |

La relación entre los cuatro no es una cadena lineal única — es un árbol de decisión: Missing Data es la capa de inventario que existe siempre que hay un hueco, lo necesite alguien o no; en el momento en que una Rule sí lo necesita, ese hueco (o uno detectado en el mismo instante, sin haber pasado antes por Missing Data si nadie lo había inventariado todavía) se manifiesta como Unknown; y un Unknown se resuelve por exactamente una de tres vías — llega un Fact real, se aplica una Estimation del catálogo, o se declara una Assumption — nunca por una cuarta vía silenciosa.

---

## 2. Missing Data en detalle

Missing Data es la única de las cuatro entidades que **no bloquea nada por sí sola** — es una capa de visibilidad temprana, no un obstáculo. Se detecta en Ingesta comparando lo que el proyecto declara contra el catálogo de "datos mínimos necesarios" que `ARCHITECTURAL_KNOWLEDGE_MAP.md` ya exige documentar por dominio (§9 de cada dominio) — incluidos los dominios que todavía no están activos en la fase actual del motor (`PRD-001-Core-Reasoning-Engine.md` solo activa 2 de 14).

Este último punto es su valor real: Missing Data permite saber, **antes** de que un dominio nuevo se active, qué huecos de datos van a convertirse en Unknowns en cuanto ese dominio empiece a evaluar — un inventario de fricción futura, no una alarma presente. No genera ningún efecto sobre Confidence (sección 7) ni aparece en la lista de Hallazgos activos (`OBSERVATION_MODEL.md`) — se muestra al Arquitecto en un espacio propio, de menor urgencia (sección 8), precisamente para no mezclar "esto podría hacer falta algún día" con "esto está bloqueando una evaluación ahora mismo".

---

## 3. Unknown en detalle

Reafirma, sin cambios, la entidad 6 de `REASONING_ENGINE_SPEC.md`: nace cuando el Motor de Dominio detecta que una Rule no puede evaluarse por falta de un Fact, lleva su apalancamiento de decisión declarado, y nunca desaparece sin una transición explícita.

**Extensión declarada respecto al documento original:** `REASONING_ENGINE_SPEC.md` entidad 6 fijaba dos vías de resolución ("llega una Observation/Fact real, o se promueve a Assumption"). Este documento añade una tercera, intermedia entre ambas: **la Estimation** (sección 5). Las tres vías, ahora completas:

1. Llega un Fact real (Observation validada) — la resolución más fuerte, cierra el Unknown con datos verdaderos.
2. Se aplica una Estimation de un método catalogado — cierra el Unknown con un proxy declarado, confianza limitada a Media.
3. Se adopta una Assumption declarada — cierra el Unknown con una hipótesis de juicio, confianza limitada a Media/Baja.

Un Unknown nunca queda "abandonado": mientras no se cierre por una de las tres vías, la Rule que lo necesita permanece en estado no evaluable, visible, y sujeta al protocolo de triaje de `DECISION_ENGINE.md` §12 (¿el apalancamiento justifica preguntar activamente al Arquitecto, o es lo bastante bajo como para cubrirlo con Estimation/Assumption sin interrumpir el flujo?).

---

## 4. Estimation en detalle

Una Estimation es un Fact con un cuarto valor de origen epistémico, añadido aquí al eje ya fijado en `FACT_MODEL.md` §2.1 (que hasta ahora tenía tres: observado / derivado / promovido). El cuarto valor:

| Origen | Techo de fuerza (`EVIDENCE_MODEL.md` §3) | Se distingue de... |
|---|---|---|
| **Estimado** | Media, siempre — nunca Alta, sin importar el nivel de conocimiento del método que lo produjo | **Derivado** (`FACT_MODEL.md` §4), porque un Fact derivado es composición exacta sin pérdida de certeza sobre datos ya conocidos; una Estimation, por definición, sustituye un dato que no se conoce por un proxy con error inherente. **Promovido**, porque una Assumption es juicio declarado sin cálculo; una Estimation siempre es el resultado de aplicar un método concreto, repetible y catalogado sobre Facts que sí existen |

**Estructura de una Estimation:**

| Atributo | Contenido |
|---|---|
| **tipo de dato que estima** | El mismo espacio de nombres que cualquier tipo de Fact (`FACT_MODEL.md` §3) |
| **método aplicado** | Uno del catálogo cerrado de métodos de aproximación (ver abajo), nunca una fórmula libre inventada para el caso |
| **Facts de entrada** | Los Facts reales sobre los que el método calcula el proxy |
| **caracterización del error** | Cualitativa, no un número que sugiera una precisión que el método no tiene realmente (mismo principio anti-precisión-fabricada de toda la serie) — p. ej. "proxy geométrico aproximado, validado orientativamente, no sustituye una medición real de hueco" |

El **catálogo de métodos de estimación** es cerrado y gobernado por el Curador de Conocimiento, con la misma disciplina que el catálogo de patrones de evaluación (`CONSTRAINT_MODEL.md` §3.1) y el catálogo de composición de Facts derivados (`FACT_MODEL.md` §4): un método nuevo es un evento de gobernanza raro, nunca una respuesta automática a un Unknown concreto que "sería cómodo estimar". El ejemplo real ya existente en el producto — la superficie de ventana estimada como 25% del ancho de fachada, reutilizada deliberadamente por los bloques 15 y 19 de `evaluator.py` — es exactamente la forma que debería tener una entrada de este catálogo: un método con nombre, con los Facts que consume declarados, y con su error caracterizado, no una constante suelta dentro del código de una regla concreta.

**La salvaguarda central de esta sección, directamente ligada al principio rector (sección 0):** aplicar una Estimation a un Unknown nunca es automático. Pasa por el mismo triaje de apalancamiento de `DECISION_ENGINE.md` §12 que ya rige Assumption — un Unknown de alto apalancamiento de decisión no se cubre con una Estimation sin más solo porque existe un método catalogado que técnicamente podría aplicarse; se pregunta activamente al Arquitecto, igual que ya exige el protocolo para Assumption. Sin esta salvaguarda, Estimation sería, literalmente, una forma más elaborada de convertir un Unknown en un valor por defecto — el mismo Bug #1, con un catálogo respetable delante para que pareciera otra cosa.

---

## 5. Assumption en detalle

Reafirma, sin cambios, la entidad 7 de `REASONING_ENGINE_SPEC.md`: una hipótesis declarada, marcada como tal, que nunca deja pasar Confidence Alta río abajo, retirada (no editada) cuando llega el dato real que la sustituye.

Lo que este documento añade es su lugar exacto en el árbol de decisión de la sección 1: **Assumption es la vía de cierre cuando no existe un método de Estimation catalogado para ese tipo de dato**, o cuando el dato en cuestión es, por su naturaleza, de juicio y no de aproximación geométrica/numérica (p. ej., "esta comunidad autónoma probablemente aplicará el criterio X" es una Assumption, nunca una Estimation, porque no hay ningún Fact del que "calcular" esa hipótesis por aproximación — es una declaración de expectativa, no un proxy). La frontera entre ambas no es de grado de incertidumbre, es de naturaleza: Estimation calcula, Assumption declara.

---

## 6. Cómo afectan al razonamiento

| Concepto | Efecto sobre la Rule que lo necesita |
|---|---|
| **Missing Data** | Ninguno directo — todavía no hay Rule pidiendo ese dato en la evaluación actual |
| **Unknown** | El Constraint/Rule queda "no evaluable" (`CONSTRAINT_MODEL.md` §4) — no produce Inference, ni positiva ni negativa, hasta que se cierre |
| **Estimation** | La Rule se evalúa con normalidad, usando el valor estimado como si fuera el Fact — pero cualquier Inference resultante hereda el techo de confianza Media, y cualquier Inference compuesta que la consuma no puede superar ese techo (`INFERENCE_ENGINE.md` §2.1, regla del eslabón más débil) |
| **Assumption** | Igual que Estimation en mecánica, con techo de confianza más bajo (Media/Baja según el caso) y la misma propagación obligatoria hacia cualquier Inference compuesta que dependa de ella |

Ninguno de los cuatro puede producir, en ningún caso, una **Inference negativa** válida (`INFERENCE_ENGINE.md` §2.2) — recordatorio directo de la invariante ya fijada allí: una conclusión de "no existe/no se cumple" solo puede venir de un resultado `no_existe` explícito y comprobado, nunca de que el dato correspondiente esté en estado Missing Data, Unknown, Estimation o Assumption. Los cuatro son, precisamente, formas de *no saber* con distinto grado de mitigación — ausencia de evidencia, en cualquiera de sus variantes, sigue sin ser evidencia de ausencia.

---

## 7. Cómo afectan a la confianza

Extiende, con una fila nueva, la tabla de techos ya fijada en `EVIDENCE_MODEL.md` §3:

| Origen del tramo | Techo de fuerza |
|---|---|
| Fact observado | Alta |
| Fact derivado (composición exacta) | Igual que su fuente de menor fuerza |
| **Fact estimado (nuevo)** | **Media, siempre** |
| Fact promovido desde Assumption | Media |
| Assumption sin promover | Baja |

Una precisión que evita una lectura errónea: Estimation y Assumption-promovida-a-Fact comparten el mismo techo (Media) pero no son intercambiables — comparten techo porque ambas introducen la misma magnitud de incertidumbre estructural (un dato que no es observación directa), no porque sean la misma cosa. La distinción de naturaleza (cálculo vs. juicio, sección 5) se conserva siempre en el origen del tramo, visible en Evidence, aunque el techo numérico de fuerza coincida.

**Missing Data no tiene fila en esta tabla** — no es un tramo de Evidence de ninguna conclusión todavía, porque nada se ha evaluado con ese dato. Solo empieza a tener efecto sobre la confianza en el momento en que se manifiesta como Unknown y, eventualmente, se cierra por una de las tres vías de la sección 3.

---

## 8. Cómo deben mostrarse al arquitecto

Cuatro tratamientos distintos, ninguno intercambiable con otro — extiende directamente la distinción de dos casos ya fijada en `EXPLANATION_ENGINE.md` §8 a los cuatro conceptos completos de este documento:

- **Missing Data** — se muestra en un espacio propio de menor urgencia, separado de la lista de Hallazgos activos (`OBSERVATION_MODEL.md`) — un panel de "esto no está declarado" orientado a preparar al Arquitecto para cuando active dominios que sí lo necesiten, nunca mezclado con hallazgos que exigen atención ahora.
- **Unknown** — se narra exactamente como ya fija `EXPLANATION_ENGINE.md` §8: qué dato falta, por qué importa, y — cuando el apalancamiento lo justifica — la recomendación condicional de `DECISION_ENGINE.md` §12 ("si X, entonces A; si Y, entonces B"). Nunca un valor, nunca un silencio.
- **Estimation** — se muestra **siempre** marcada como estimación, con el método citado por su nombre (nunca "aproximadamente 12m²" sin decir que es un proxy) — esta marca es independiente de qué cubeta de confianza resulte: incluso si el método está bien calibrado y la Confidence resultante es aceptable, la naturaleza de "esto es un proxy, no una medición" nunca se omite ni se disuelve dentro de un tono de normalidad. Es la aplicación directa, a un cuarto caso, de la misma invariante que `FACT_MODEL.md` ya exige para Facts promovidos desde Assumption: nunca indistinguible de un dato observado.
- **Assumption** — se muestra exactamente como ya fija `REASONING_ENGINE_SPEC.md` entidad 7 y `EXPLANATION_ENGINE.md` §2 (registro de vocabulario ligado a fuerza Baja/Media): "bajo el supuesto de que...", nunca como una afirmación sin matiz.

---

## Cierre

El árbol de decisión de la sección 1 — Missing Data como inventario proactivo, Unknown como bloqueo activo, y dos vías disciplinadas de cierre (Estimation para lo que se puede aproximar con un método declarado, Assumption para lo que solo se puede declarar como juicio) — no añade complejidad por completitud académica: cada rama existe porque, sin ella, la presión de "hay que dar una respuesta" encontraría un atajo hacia el default silencioso que `TECH_REVIEW.md` ya confirmó una vez. El punto de mayor vigilancia, nombrado en la sección 0 y otra vez en la sección 4, es Estimation — es la única de las cuatro entidades que produce un valor con apariencia de dato normal, y es exactamente por eso que su catálogo de métodos tiene que permanecer cerrado, su aplicación tiene que pasar siempre por el mismo triaje de apalancamiento que Assumption, y su origen tiene que quedar visible en cada capa de la serie — Fact, Evidence y Explanation — sin excepción.
