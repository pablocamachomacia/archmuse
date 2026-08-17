# GLOBAL_ASSESSMENT.md

**Propósito:** diseñar cómo el sistema sintetiza todo lo que sabe sobre un proyecto — potencialmente cientos de Hallazgos, decenas de Conflicts, Assumptions activas, Recommendations pendientes — en un juicio que un arquitecto senior reconocería como el suyo propio: profesional, matizado, capaz de decir "esto es viable pero fràgil" o "esto es sólido pero mejorable" sin colapsar nunca esas dos ideas en un solo número. `BRAIN_ARCHITECTURE.md` ya fijó el principio fundacional del que este documento parte: **el veredicto global de tres capas (viabilidad binaria / riesgo de visado ponderado / calidad no bloqueante) debe permanecer separado durante todo el pipeline y solo colapsar a una presentación única al final — nunca fusionarse en una puntuación intermedia**, el antídoto directo al problema de `classify_problems` como función-dios que `TECH_REVIEW.md` ya diagnosticó. Este documento extiende esas tres capas a seis dimensiones y diseña, con precisión operativa, cómo se sintetizan sin ocultar nada. Sin código, como el resto de la serie.

**Referencias obligatorias, asumidas como ya decididas:**
- `BRAIN_ARCHITECTURE.md` — el principio de las tres capas separadas, citado arriba, que gobierna todo este documento.
- `ARCHITECTURAL_QUALITY.md` — §3 ("espejo, no juez"), que determina la forma narrativa de la dimensión de calidad (sección 1).
- `OBSERVATION_MODEL.md` — §4, el roll-up de severidad (máximo, nunca promedio) — el mecanismo de selección que este documento reutiliza para decidir qué Hallazgos aparecen citados explícitamente en la síntesis (sección 2).
- `UNCERTAINTY_MODEL.md` — las cuatro entidades de incertidumbre, el sustrato directo de la dimensión de robustez (sección 1).
- `CHAIN_ENGINE.md` — §1, el grafo instanciado de propagación, reutilizado aquí con un propósito nuevo: como señal diagnóstica sobre el propio proyecto, no solo sobre el rendimiento del motor (sustrato de mantenibilidad, sección 1).
- `RECOMMENDATION_ENGINE.md` y `CONFLICT_ENGINE.md` — sustrato de potencial de mejora y de riesgo, respectivamente (sección 1).
- `PROJECT_MEMORY.md` — §5, la consulta derivada de Hallazgos reabiertos más de una vez, reutilizada como uno de los focos de riesgo.
- `EXPLANATION_ENGINE.md` — §4, los tres niveles cerrados, reutilizados como el mecanismo de profundidad progresiva de la síntesis (sección 2).

**Entidad nueva, ligera, añadida al modelo:**
- **Juicio Global** — la síntesis completa de las seis dimensiones para una versión concreta de ProjectState, con su propia Evidence agregada y su propia Explanation. No es una Inference ni un Hallazgo — es un tipo de entidad distinto, cuyo único contenido es la organización y presentación de conclusiones que ya existen, nunca un cálculo nuevo sobre Facts.

**Actor nuevo, añadido al glosario ya establecido:**
- **Sintetizador** — el proceso que construye el Juicio Global aplicando, sección a sección, el mecanismo de síntesis sin pérdida de la sección 2. Se ejecuta al cierre de cada Sesión (`PROJECT_MEMORY.md` §4), después del Consolidador de Sesión, sobre el estado ya consolidado.

---

## 0. Principio rector

Ninguna de las seis dimensiones se combina con otra en un número, un color, una letra ni una etiqueta compuesta — ni siquiera internamente, como paso intermedio antes de "traducirlo" a texto. La razón no es estética: `BRAIN_ARCHITECTURE.md` ya identificó que fusionar capas de naturaleza distinta en una sola puntuación es, exactamente, el patrón que convirtió `classify_problems` en una función-dios difícil de auditar — un juicio profesional que dice "72/100" no es más informativo que uno que dice "viable, con dos riesgos concretos y una fragilidad identificada" — es menos informativo, porque el número esconde precisamente la estructura que hace el juicio útil.

Cada una de las seis dimensiones tiene, además, una naturaleza epistémica distinta (algunas son casi binarias y Nivel 1-2; otras son irreduciblemente Nivel 4) — y por eso cada una recibe la **forma narrativa que le corresponde**, no una plantilla uniforme aplicada a las seis por igual. Forzarlas a un mismo formato (seis etiquetas Alta/Media/Baja, por ejemplo) sería una puntuación disfrazada de cualitativa — la misma trampa que `ARCHITECTURAL_QUALITY.md` ya nombró para la cuantificación del gusto, aplicada aquí a la síntesis completa del proyecto.

---

## 1. Las seis dimensiones

| Dimensión | Sustrato (de qué se construye) | Naturaleza | Forma narrativa |
|---|---|---|---|
| **Viabilidad** | Problems bloqueantes sin resolver ni aceptar; Unknowns de alto apalancamiento sin resolver | Nivel 1-2, casi binaria | Veredicto de tres estados con sus condiciones citadas (ver abajo) |
| **Riesgo** | Conflicts abiertos (especialmente Tipo 5); Assumptions activas de alto apalancamiento; Hallazgos reabiertos más de una vez (`PROJECT_MEMORY.md` §5) | Mixta — depende de qué lo compone | Lista de focos concretos, priorizada, nunca una etiqueta única |
| **Calidad** | Hallazgos de recomendación de calidad y positivos (`OBSERVATION_MODEL.md` §3), Nivel 3-4 | Nivel 4, criterio arquitectónico | Descriptiva, modo "espejo" (`ARCHITECTURAL_QUALITY.md` §3) — nunca un veredicto |
| **Robustez** | Proporción y apalancamiento de las Assumptions/Estimations que sostienen la viabilidad actual | Meta — sobre la confianza del propio juicio, no sobre el proyecto directamente | Declaración explícita de qué tan sólida es la propia Viabilidad reportada |
| **Mantenibilidad** | Forma del grafo instanciado de propagación (`CHAIN_ENGINE.md` §1) — cuán contenidos son los subgrafos alcanzables por concepto | Estructural, sobre el propio diseño del proyecto | Descriptiva, con ejemplos concretos de zonas de alto acoplamiento si existen |
| **Potencial de mejora** | Hallazgos de calidad abiertos; Recommendations generadas y no aceptadas (`RECOMMENDATION_ENGINE.md`) | Nivel 3-4 en su mayoría | Lista de oportunidades concretas, nunca "el proyecto podría mejorar en general" |

### Viabilidad

Tres estados, no dos, porque un binario estricto ocultaría información real: **Viable** (ningún Problem bloqueante activo, ningún Unknown de alto apalancamiento sin resolver), **No viable** (al menos un Problem bloqueante activo sin Decision de aceptación), y **Viable condicionada** (no hay Problems bloqueantes, pero la conclusión depende de uno o más Unknowns de alto apalancamiento todavía sin resolver — el caso en que el sistema honestamente no puede decir "sí" sin más). El tercer estado nunca se colapsa en "Viable" por comodidad — es, precisamente, la información que un arquitecto necesita para saber qué preguntar antes de dar por buena la conclusión.

### Riesgo

Nunca "Alto/Medio/Bajo" como etiqueta aislada — una etiqueta así, sin sus focos nombrados, sería la puntuación que este documento existe para evitar. Se presenta como una **lista priorizada de focos concretos de riesgo**, cada uno con su propia naturaleza (un Conflict Tipo 5 sin resolver, una Assumption de alto apalancamiento todavía activa, un patrón de Hallazgo reabierto repetidamente) — priorizada con el mismo filtro secuencial de 5 criterios ya fijado en `CONFLICT_ENGINE.md` §2, nunca con un peso numérico inventado para la ocasión (que es, precisamente, lo que "riesgo de visado ponderado" podría malinterpretarse como pidiendo — aquí "ponderado" significa "ordenado por el mismo criterio de prioridad cualitativo ya existente en toda la serie", no "puntuado con un peso numérico").

### Calidad

Se narra exactamente con el mismo registro "espejo, no juez" ya fijado en `ARCHITECTURAL_QUALITY.md` §3 — una descripción organizada de los Hallazgos de calidad vigentes (qué dimensiones de excelencia del Dominio 9 están bien resueltas, cuáles no, dónde hay tensión con otros dominios ya materializada como Conflict Tipo 2, `CONFLICT_ENGINE.md` §1) — nunca un veredicto de "buena/mala arquitectura", porque ese veredicto excede lo que el sistema tiene autoridad de afirmar, exactamente como ya se fijó en el documento que define este dominio.

### Robustez

La dimensión que responde a una pregunta distinta de las tres anteriores: no "¿es viable?" sino "¿cuánto se sostiene esa conclusión sobre terreno firme?". Se construye examinando, para la Viabilidad reportada, cuántos de los Facts y Constraints que la sostienen tienen fuerza Alta (`EVIDENCE_MODEL.md` §3) frente a cuántos dependen de una Estimation o una Assumption (`UNCERTAINTY_MODEL.md`) todavía activa. Un proyecto puede ser "Viable" y, al mismo tiempo, poco robusto — su viabilidad depende de tres Assumptions de apalancamiento medio que todavía no se han confirmado con datos reales — y esa combinación es exactamente la que este documento existe para hacer visible en vez de que ambas cosas se mezclen en un genérico "viable, con matices".

### Mantenibilidad

Reutiliza el grafo instanciado de propagación (`CHAIN_ENGINE.md` §1) con un propósito nuevo, no solo de rendimiento sino de **diagnóstico sobre el propio proyecto**: si los subgrafos alcanzables desde los Facts principales del proyecto son pequeños y contenidos, un cambio futuro será barato y localizado; si hay zonas donde un Fact tiene un subgrafo alcanzable inusualmente grande — muchos Domains y muchas piezas dependiendo, directa o indirectamente, del mismo dato — esa zona es, estructuralmente, frágil ante cambios futuros, independientemente de si hoy cumple todo. Es una propiedad del diseño del proyecto, no del motor, y se nombra con ejemplos concretos ("la geometría del núcleo de escaleras afecta, directa o indirectamente, a siete de las diez viviendas — cualquier cambio ahí tendrá un coste de revisión alto") en vez de una cifra de "acoplamiento: 7/10".

### Potencial de mejora

La única de las seis dimensiones que mira hacia adelante en vez de describir el estado actual — una lista concreta de oportunidades: Hallazgos de calidad todavía abiertos, Recommendations ya generadas por el sistema (`RECOMMENDATION_ENGINE.md`) que el Arquitecto no ha aceptado ni descartado explícitamente. Nunca una frase genérica ("el proyecto tiene margen de mejora") — cada entrada de esta lista es un Hallazgo o Recommendation concreto y trazable, exactamente igual que cualquier otra afirmación del sistema.

---

## 2. Cómo se sintetizan cientos de Hallazgos sin ocultar información relevante

El mecanismo tiene tres reglas, aplicadas por igual a las seis dimensiones, y ninguna es nueva — todas reutilizan disciplina ya fijada en documentos anteriores:

1. **Selección de lo que se cita explícitamente, nunca por muestreo aleatorio ni por orden de aparición** — se usa el mismo criterio de máximo-nunca-promedio ya fijado en `OBSERVATION_MODEL.md` §4 (severidad) y `CONFLICT_ENGINE.md` §2 (prioridad): dentro de cada dimensión, los elementos que se nombran explícitamente en la síntesis son los de mayor severidad/prioridad/apalancamiento — nunca una muestra representativa que podría, por azar, omitir el hallazgo más grave.
2. **Lo que no se cita explícitamente se agrega por conteo, nunca se descarta** — "y catorce Hallazgos adicionales de severidad recomendable, no citados aquí individualmente" es una frase obligatoria cuando aplica, nunca un silencio. El conteo total de cada dimensión (cuántos Hallazgos, cuántos Conflicts, cuántas Assumptions activas) aparece siempre, se expliquen o no uno a uno.
3. **Todo lo agregado es navegable hasta el detalle completo, usando los mismos tres niveles ya cerrados en `EXPLANATION_ENGINE.md` §4** — el Juicio Global se presenta, por defecto, a nivel Estándar, pero cada dimensión puede expandirse a nivel Completo sin perder nada: la síntesis nunca es la única forma de acceder a la información, es la puerta de entrada a ella. "Sin ocultar información relevante" no significa "mostrar todo siempre" — significa que nada queda inalcanzable detrás de la síntesis.

La combinación de las tres reglas es lo que distingue esta síntesis de un resumen con pérdida: nunca se pierde un Hallazgo grave por selección aleatoria (regla 1), nunca desaparece un Hallazgo menor sin dejar constancia de que existe (regla 2), y nunca hay un límite real de profundidad para quien quiera ver el detalle completo (regla 3).

---

## 3. Cómo se relacionan las seis dimensiones entre sí

**Nunca se combinan en una síntesis compuesta, ni siquiera como comparación entre proyectos.** Esto es deliberado y coherente con el límite ya trazado para el Dominio 14 en documentos anteriores (`CONFLICT_ENGINE.md` §4, `UNCERTAINTY_MODEL.md`): comparar dos proyectos por su Juicio Global exigiría, en algún punto, reducir seis dimensiones heterogéneas a algo ordenable — exactamente la puntuación que este documento existe para no producir.

**Viabilidad domina la lectura, sin que las otras cinco puedan suavizarla.** Un proyecto "No viable" con una Calidad excelente y un Potencial de mejora bajo (porque ya está casi todo bien resuelto) sigue siendo, en la primera línea del Juicio Global, "No viable" — las otras cinco dimensiones aportan contexto útil, nunca atenúan la lectura de la primera. Es la misma disciplina de "lo bloqueante nunca se diluye" que `BRAIN_ARCHITECTURA.md` Parte 1.8 fija desde el primer documento de la serie, aplicada aquí al nivel más alto de síntesis que existe en todo el modelo.

Las otras cinco, entre sí, son genuinamente independientes — un proyecto puede ser Viable, de Riesgo bajo, Calidad discutible, Robustez alta, Mantenibilidad frágil y Potencial de mejora considerable, las seis afirmaciones simultáneamente ciertas y ninguna contradice a otra. Presentarlas por separado es, precisamente, lo que permite que esa combinación completa —realista, no simplificada— llegue intacta al Arquitecto.

---

## 4. Juicio Global como entidad

Se genera al cierre de cada Sesión (`PROJECT_MEMORY.md` §4), inmediatamente después de que el Consolidador de Sesión termina su propio resumen — el Sintetizador toma ese estado ya consolidado y produce las seis narrativas de la sección 1 siguiendo el mecanismo de la sección 2. Es append-only como cualquier otra entidad de conclusión de la serie: un Juicio Global no se edita, una Sesión nueva produce uno nuevo que sustituye al anterior como "el vigente", sin borrar el histórico — de modo que un Arquitecto puede, si quiere, comparar el Juicio Global de hoy con el de la semana pasada y ver, con precisión, qué dimensión cambió y por qué, con la misma trazabilidad que cualquier otra entidad del modelo.

Lleva su propia Evidence — la unión de las Evidence de cada Hallazgo/Conflict/Assumption citado explícitamente en las seis narrativas — y su propia Explanation, generada por el Narrador (`EXPLANATION_ENGINE.md`) con las mismas reglas de vocabulario y trazabilidad ya fijadas para cualquier otra Explanation del sistema. No hay ningún mecanismo nuevo de justificación aquí — el Juicio Global se justifica exactamente igual que cualquier afirmación del sistema, a pesar de ser, con diferencia, la de mayor alcance.

---

## Cierre

La presión más probable sobre este documento, con el tiempo, no vendrá de dentro del motor — vendrá de fuera, de la tentación comercial obvia de añadir un séptimo elemento al final del Juicio Global: un resumen ejecutivo de una cifra, "para que el cliente lo vea de un vistazo", que colapse las seis dimensiones en algo que quepa en una insignia verde/amarilla/roja. Es, textualmente, la misma tentación que ya produjo `TIPOLOGIA_BENCHMARKS` y que `MOAT_ANALYSIS.md`/`NORTH_STAR_2031.md` ya identificaron como el principio no negociable de todo el producto: nunca mostrar datos fabricados como reales. Un juicio profesional de seis dimensiones separadas, cada una con sus focos nombrados y su detalle navegable, es más difícil de vender en una diapositiva que una insignia de color — y es, precisamente por eso, lo único que un arquitecto senior reconocería como su propio criterio reflejado con honestidad, en vez de simplificado hasta perder lo que lo hacía útil.
