# FACT_MODEL.md

**Propósito:** este documento profundiza en una sola entidad de `REASONING_ENGINE_SPEC.md` — **Fact** — y sus dos satélites inmediatos, **Observation** y **Unknown**, porque son la base sobre la que razona literalmente todo lo demás. `REASONING_ENGINE_SPEC.md` las definió a nivel de especificación general (entidades 4, 5 y 6, sección B); este documento las lleva al nivel de detalle necesario para que un motor con 14 dominios y miles de reglas pueda apoyarse en ellas durante años sin que el propio modelo de datos se convierta en el cuello de botella. No hay clases, ni esquemas de base de datos, ni código — sigue siendo un documento de modelo, no de implementación.

**Referencias obligatorias, asumidas como ya decididas y no vueltas a discutir aquí:**
- `REASONING_ENGINE_SPEC.md` — especialmente las entidades 1 (ProjectState), 3 (Change), 4 (Observation), 5 (Fact), 6 (Unknown), 7 (Assumption), y los cuatro "Principios de coherencia a largo plazo" de su cierre.
- `BRAIN_ARCHITECTURE.md` — los 14 dominios y su grafo de capas, referenciados aquí para razonar sobre qué rompe el modelo de Facts cuando el número de dominios crece.
- `ARCHITECTURAL_KNOWLEDGE_MAP.md` — los 4 niveles de conocimiento; un Fact es, por definición, Nivel 1, y ese límite se defiende activamente en este documento (sección 4).
- `CHAIN_REASONING.md` — el modelo de propagación; el diseño de invalidación de este documento (sección 6) existe para que ese modelo sea computacionalmente viable, no solo conceptualmente correcto.
- `DECISION_ENGINE.md` — el protocolo de información insuficiente (sección 12), que fija por qué Unknown no puede ser un simple `null`.

**Alcance:** este documento no vuelve a definir Rule, Inference, Domain, Constraint ni ninguna otra entidad de `REASONING_ENGINE_SPEC.md` — las trata como ya fijadas y solo describe cómo consumen o producen Facts. Reutiliza el glosario de actores de ese documento (Ingesta, Motor de Dominio, Motor de Propagación, Motor de Decisión, Curador de Conocimiento, Arquitecto, Cliente) y añade uno nuevo, necesario para lo que sigue:

- **Compositor de Hechos** — el proceso, distinto del Motor de Dominio, responsable exclusivamente de generar Facts derivados mediante funciones de composición puras (sección 4). Se nombra aparte a propósito: si esta función se difumina dentro del Motor de Dominio, la frontera entre "dato" y "razonamiento" (el riesgo central de este documento, sección 12.1) se vuelve invisible en la práctica.

---

## 1. Qué es un Fact — y qué no es

Un **Fact** es el dato aceptado y canónico sobre el que razona el resto del sistema: la superficie de una pieza, la tipología declarada de un proyecto, la orientación de una fachada. Es, por definición, Nivel 1 de `ARCHITECTURAL_KNOWLEDGE_MAP.md` — un hecho, no una interpretación.

Dos fronteras lo delimitan, y ambas son más importantes que cualquier atributo concreto que se defina más abajo:

- **Fact no es Observation.** Una Observation es lo que el sistema *leyó* — un polígono crudo del parser, un valor de un campo de formulario — antes de validación. Un Fact es lo que el sistema *acepta* tras ese proceso. La distinción no es cosmética: permite que una lectura ambigua o contradictoria exista registrada (para auditoría) sin contaminar la capa sobre la que las Rules razonan.
- **Fact no es Inference.** Un Fact nunca incorpora una Rule, un Constraint, un umbral ni juicio alguno. En el momento en que un valor depende de una comparación normativa o de una decisión de qué umbral aplica, deja de ser Fact y pasa a ser Inference (o Problem). Esta frontera es la que la sección 12.1 identifica como la más fácil de erosionar a medida que crecen los dominios, y por eso el resto de este documento la trata como invariante estructural, no como convención de estilo.

**Principio rector de todo el documento:** ningún consumidor de Facts — ninguna Rule, en ningún dominio, presente o futuro — puede encontrarse nunca con *silencio*. Para cualquier par (ámbito, tipo de dato) que una Rule necesite, el sistema debe poder responder siempre con exactamente una de estas cuatro cosas: un Fact vigente, un Unknown vigente, una Assumption vigente que cubre ese Unknown, o una marca explícita de "no aplicable" (ver sección 10). Nunca un `null`, nunca una ausencia sin explicar. Este principio es la respuesta estructural directa al Bug #1 confirmado en `TECH_REVIEW.md` (tipología/zona_cte cayendo a un valor por defecto sin que nadie lo supiera) — ese bug fue posible precisamente porque el modelo de datos permitía el silencio. Este modelo lo prohíbe por diseño.

---

## 2. Tres ejes de tipificación, no una taxonomía plana

Un catálogo de "tipos de Fact" definido como una única lista plana (`superficie`, `tipología`, `orientación`...) funciona con 2 dominios y deja de funcionar con 14: cada dominio nuevo quiere clasificar los Facts según su propio criterio (¿es geométrico?, ¿es de qué tan fiable es su origen?, ¿a qué elemento físico pertenece?), y forzar todo eso en una sola lista produce categorías incoherentes o, peor, el mismo nombre de tipo usado con significados distintos por dominios distintos (ver riesgo 12.2). Este documento define en su lugar **tres ejes independientes**, cada Fact se clasifica en los tres simultáneamente:

### 2.1 Eje de origen epistémico

| Valor | Significado |
|---|---|
| **Observado** | Respaldado directamente por una o más Observations validadas. Es el caso por defecto y el de mayor confianza. |
| **Derivado** | Calculado por el Compositor de Hechos a partir de otros Facts mediante una función de composición pura (suma, diferencia, agregación geométrica) — nunca mediante una Rule. Ver frontera exacta en sección 4. |
| **Promovido desde Assumption** | Nace cuando una Assumption (`REASONING_ENGINE_SPEC.md`, entidad 7) se confirma formalmente por el Arquitecto como dato definitivo, sin que llegue nunca una Observation real que la sustituya. Sigue siendo, técnicamente, un Fact — pero permanentemente marcado como tal (ver invariante en sección 4), nunca indistinguible de un Fact observado, tal como exige la entidad 5 de `REASONING_ENGINE_SPEC.md`. |

### 2.2 Eje de naturaleza del dato

| Valor | Ejemplos | Perfil de mutabilidad típico |
|---|---|---|
| **Geométrico** | Superficie de una pieza, perímetro, forma, huecos | Casi-inmutable: solo cambia si hay una nueva ingesta (nuevo DXF/IFC) |
| **Declarado** | Tipología, ciudad, norte geográfico, normativa autonómica elegida | Mutable por declaración: cambia cuando el Arquitecto edita un campo (un Change) |
| **Contextual-normativo** | Zona climática CTE derivada de la ciudad, normativa vigente en la fecha del proyecto | Derivado de un Fact declarado vía una tabla de referencia — ver frontera de la sección 4 sobre si una tabla de referencia cuenta como composición pura |
| **Temporal** | Fecha de referencia normativa, fecha de la ingesta | Fijado en el momento de creación, no cambia salvo por corrección explícita |

Este eje no sustituye al de origen epistémico: son ortogonales. Una "zona climática" es contextual-normativa *y* derivada; una "superficie de pieza" es geométrica *y* observada.

### 2.3 Eje de ámbito (scope)

Deliberadamente **no** es un único árbol de contención. La tentación obvia es modelar el ámbito como `proyecto → parcela → edificio → planta → unidad → pieza` y asumir que todo Fact cuelga de un nodo de ese árbol. Eso funciona para geometría de piezas y viviendas, pero no para todos los dominios de `BRAIN_ARCHITECTURA.md`: un Fact de Dominio 11 (Estructura) puede referirse a un pilar o una viga, que no es "una pieza" ni "una planta", es un elemento constructivo que puede atravesar varias plantas; un Fact de Dominio 10 (Instalaciones) puede referirse a un recorrido de saneamiento que cruza varias piezas y no vive dentro de ninguna de ellas; un Fact urbanístico puede referirse a una parcela que contiene varios edificios, no al revés. Forzar todos estos casos dentro del árbol físico es exactamente el tipo de simplificación que la sección 12.3 identifica como rotura a 14 dominios.

El diseño correcto: el **árbol de contención física** (proyecto→parcela→edificio→planta→unidad→pieza) es una de varias **dimensiones de ámbito** posibles, no la única. Un Fact declara su ámbito como una referencia a un nodo en *alguna* de las dimensiones registradas — física, elemento constructivo, sistema/instalación, itinerario — y el catálogo de dimensiones de ámbito es abierto y mantenido por el Curador de Conocimiento, igual que el catálogo de Domains. La dimensión física seguirá siendo, en la práctica, la más usada — pero el modelo no puede asumir que es la única sin romperse en cuanto un dominio de capas superiores (Estructura, Instalaciones, Riesgo/Mercado) empiece a producir Facts en serio.

---

## 3. Atributos mínimos de un Fact

| Atributo | Descripción | Por qué es necesario |
|---|---|---|
| **id de instancia** | Identificador único de esta versión concreta del Fact | Cada sustitución (sección 6) crea una instancia nueva; sin id propio no se puede referenciar una versión exacta desde una Evidence histórica |
| **id de concepto** | Identificador estable que se mantiene igual a través de todas las sustituciones del "mismo dato" a lo largo del tiempo | Sin él no hay forma de responder "¿cuál es la historia completa del área útil de esta pieza?" sin recorrer todo el histórico buscando coincidencias por ámbito+tipo — inviable a escala de millones (sección 11) |
| **tipo de dato** | Con espacio de nombres (ver riesgo 12.2) — no un string libre | Evita colisión de nombres entre dominios (`altura` en Dominio 3 vs `altura` en Dominio 11) |
| **eje de naturaleza** | Uno de los valores de 2.2 | Determina el perfil de mutabilidad esperado y qué proceso puede modificarlo |
| **eje de origen epistémico** | Uno de los valores de 2.1, con su puntero correspondiente (Observation(s), función de composición + Facts fuente, o Assumption promovida) | Es el dato que el resto del sistema usa para saber si puede otorgar Confidence "Alta" río abajo (invariante compartida con `REASONING_ENGINE_SPEC.md` entidad 20) |
| **referencia(s) de ámbito** | Uno o más nodos, en una o más dimensiones de ámbito (sección 2.3) | Permite que un mismo Fact sea, cuando corresponda, relevante simultáneamente en más de una dimensión (p. ej. un pilar tiene ámbito físico de planta y ámbito de elemento constructivo) |
| **valor** | El dato en sí, con su unidad explícita cuando aplica | — |
| **proyecto (namespace)** | El ProjectState/proyecto al que pertenece | Necesario desde el día uno aunque hoy no se use — evita un rediseño cuando `BRAIN_ARCHITECTURE.md` Dominio 14 (Benchmark de Mercado) empiece a necesitar Facts a través de proyectos (ver sección 11.2) |
| **rango de vigencia** | Versión de ProjectState en la que nace y versión en la que fue sustituido (abierto si sigue vigente) | Base del versionado append-only (sección 7) |
| **hash de contenido** | Huella del valor + tipo + ámbito + función/versión que lo generó | Permite deduplicación segura (sección 11.3) sin colapsar Facts distintos que coinciden por casualidad en su valor |
| **puntero de origen trazable** | Para Facts observados: referencia canónica hasta la Observation y, transitivamente, hasta el archivo fuente (sección 9). Para Facts derivados: referencia a los Facts fuente en el grafo de derivación (sección 8) | Es la garantía de trazabilidad exigida por `BRAIN_ARCHITECTURE.md` (principio de fuente citable) aplicada a la capa de datos, no solo a Constraints |

No se incluye Confidence como atributo: igual que en `REASONING_ENGINE_SPEC.md`, no es un atributo propio de Fact — un Fact observado o derivado por composición pura no tiene "grado de confianza" variable, tiene el eje de origen epistémico, que es lo que otras entidades (Inference, Evidence) consultan para calcular *su propia* Confidence.

---

## 4. Inmutabilidad — y qué significa exactamente "derivado" aquí

Toda instancia de Fact es **inmutable desde el momento en que se crea**, sin excepción — mismo principio append-only que ProjectState y Change en `REASONING_ENGINE_SPEC.md`. "Invalidar" un Fact nunca significa editarlo; significa cerrar su rango de vigencia y crear una instancia nueva del mismo id de concepto (sección 6). Esto no es una peculiaridad de este documento, es una relectura directa de la entidad 5 del spec.

Lo que sí varía, y es lo que el usuario de este modelo necesita saber en la práctica, es el **perfil de mutabilidad esperado** según el eje de origen (sección 2.1):

- Un Fact **observado** de naturaleza geométrica solo cambia cuando hay una nueva ingesta completa (un DXF/IFC nuevo) — no cambia "poco a poco".
- Un Fact **declarado** cambia cada vez que el Arquitecto edita el dato correspondiente — es el más volátil de los tres, y el que genera Changes con más frecuencia.
- Un Fact **derivado** cambia automáticamente, sin intervención directa, cada vez que cualquiera de sus Facts fuente en el grafo de derivación cambia — su tasa de cambio es una función de la de sus fuentes.

### La frontera que hay que defender activamente: Fact derivado vs Inference

Un Fact derivado solo puede nacer de una **función de composición pura**: aritmética o geométrica, determinista, sin umbral, sin severidad, sin juicio normativo, sin conocimiento de a qué Domain pertenece el resultado. "Área útil total de una vivienda = suma de las áreas útiles de sus piezas" es una composición válida. "Área útil suficiente" no lo es — en el momento en que aparece una comparación contra un mínimo, dejó de ser Fact y es una Inference que debe producirse mediante una Rule con su Constraint correspondiente.

Esta frontera se nombra explícitamente porque es la más fácil de saltarse en la práctica y la de mayor impacto si se salta (desarrollada en detalle en el riesgo 12.1): es tentador, para cualquier Curador de Conocimiento de cualquiera de los 14 dominios, resolver un caso ambiguo "convirtiéndolo en Fact" para no tener que pasar por el aparato completo de Rule+Constraint+Evidence. El catálogo de funciones de composición es, por eso, **único y compartido** entre dominios — mantenido por el Curador de Conocimiento como un catálogo central, igual que el de Domains — nunca definido de forma local por un dominio para su propio uso exclusivo. Si una función de composición propuesta necesita conocer un umbral o el Domain que la consume, no pertenece a este catálogo.

La única excepción documentada a "todo Fact necesita una Observation" es el Fact promovido desde Assumption (eje 2.1). Su invariante correspondiente: **debe llevar la marca de origen epistémico de forma visible en el propio contrato de lectura** (no como metadato opcional que un consumidor puede ignorar) — ver riesgo 12.4 sobre por qué esto tiene que ser estructural y no una convención documental.

---

## 5. Cómo se crean

Cuatro vías, una por cada combinación relevante del eje de origen más la agrupación por lotes:

1. **Ingesta valida una Observation → Fact observado.** Camino por defecto para geometría y metadatos leídos de una fuente externa.
2. **El Arquitecto declara un dato vía Change → Fact declarado.** El Motor de Propagación produce el Fact nuevo como parte de la nueva versión de ProjectState que ese Change origina (mismo mecanismo que la entidad 3 del spec).
3. **El Compositor de Hechos ejecuta una función de composición sobre Facts ya vigentes → Fact derivado.** Se dispara automáticamente cada vez que cambia alguno de sus Facts fuente (no requiere una acción explícita del Arquitecto ni pasa por el Motor de Dominio).
4. **El Arquitecto confirma explícitamente una Assumption como dato definitivo → Fact promovido.** Requiere una acción explícita y registrada (no ocurre por defecto ni por inacción); la Assumption original queda cerrada y enlazada hacia el Fact que la sustituye.

**Ingesta por lotes:** cuando una sola ingesta produce muchos Facts a la vez (un DXF con decenas de piezas produce, típicamente, decenas de Facts geométricos en el mismo instante), esos Facts se crean como un **lote de ingesta** identificado, y el Motor de Propagación evalúa las Rules afectadas **una sola vez por lote**, no una vez por Fact individual creado. Sin esta agrupación, un proyecto de tamaño medio dispararía miles de re-evaluaciones redundantes en el mismo segundo — ver riesgo 12.8.

---

## 6. Cómo se invalidan

Nunca por edición ni por borrado. Invalidar un Fact es:

1. Cerrar su rango de vigencia (fijar la versión de ProjectState en la que deja de ser el vigente).
2. Crear la instancia nueva del mismo id de concepto, con su propio rango de vigencia abierto.
3. Propagar la invalidación a lo largo del **grafo de derivación** (sección 8): todo Fact derivado que tuviera el Fact invalidado entre sus fuentes se recalcula (nueva instancia, nunca edición) y, si su valor cambia, su propia invalidación se propaga a su vez.
4. Notificar al Motor de Dominio para que re-evalúe toda Rule que consumiera el Fact invalidado (mismo punto de entrada al flujo ya descrito en `REASONING_ENGINE_SPEC.md`).

El paso 3 tiene que ser **limitado por alcanzabilidad** en el grafo de derivación, no una re-evaluación global del ProjectState — desarrollado como riesgo 12.5, porque es el punto donde una implementación ingenua deja de ser viable en cuanto el número de Facts derivados crece.

Para no tener que recorrer el histórico completo cada vez que algo pregunta "¿cuál es el Fact vigente de este concepto ahora mismo?", el modelo mantiene un **índice de vigencia actual** (concept_id → id de instancia vigente) como una proyección derivada, no como una entidad nueva con reglas propias — es un mecanismo de lectura, no de conocimiento (ver sección 11.1).

---

## 7. Cómo se versionan

Cada Fact vive en dos coordenadas simultáneas:

- **id de concepto**, estable a través del tiempo — permite construir la línea temporal completa de "cómo ha cambiado el área útil de esta pieza a lo largo del proyecto", recorriendo únicamente las instancias que comparten ese id.
- **rango de vigencia**, expresado como versiones de ProjectState — cada instancia sabe en qué versión nació y (si ya fue sustituida) en qué versión dejó de ser vigente.

Esto reproduce, a nivel de Fact, el mismo principio que `REASONING_ENGINE_SPEC.md` ya fija para ProjectState: nunca se sobrescribe, siempre se encadena. La diferencia es que aquí se hace explícito el mecanismo (id de concepto + rango de vigencia) porque sin él, reconstruir esa línea temporal a partir de millones de instancias sin un id compartido sería, en la práctica, imposible de consultar con rendimiento aceptable — no es un detalle de implementación, es una propiedad que el modelo tiene que garantizar desde el diseño.

---

## 8. Cómo se relacionan entre sí

Cuatro tipos de relación, cada una con un propósito distinto — no se colapsan en una relación genérica "relacionado con":

1. **Contención física** (dimensión de la sección 2.3): pieza pertenece a unidad, unidad a planta, planta a edificio, edificio a parcela, parcela a proyecto. Es la relación que responde "¿qué Facts pertenecen a esta vivienda?".
2. **Referencia de ámbito cruzado**: un Fact puede referenciar un nodo en una dimensión no física (elemento constructivo, sistema/instalación, itinerario) simultáneamente a su ámbito físico. Responde a las necesidades de dominios cuyo objeto de estudio no es "una pieza" (sección 2.3).
3. **Grafo de derivación**: todo Fact derivado referencia los Facts fuente que lo componen, formando un grafo acíclico dirigido. Es la estructura que hace posible tanto la invalidación en cascada limitada por alcanzabilidad (sección 6) como la trazabilidad transitiva hasta el origen (sección 9).
4. **Agrupación por lote de ingesta**: Facts creados en la misma ingesta comparten un identificador de lote, útil tanto para trazabilidad ("estos 40 Facts vinieron del mismo DXF") como para la semántica de evaluación agrupada (sección 5).
5. **Enlace de promoción**: un Fact promovido desde Assumption referencia la Assumption (y, transitivamente, el Unknown) que sustituye — nunca se pierde ese enlace, es la única forma de que el sistema sepa, años después, que ese dato "definitivo" en realidad nunca fue observado.

---

## 9. Cómo se trazan hasta el DXF original

La trazabilidad nunca se duplica ni se re-apunta directamente desde un Fact derivado hacia el archivo fuente — siempre se recorre el grafo de derivación (relación 3 de la sección 8) hacia atrás hasta llegar a Facts observados, y desde ahí hacia sus Observations. Duplicar el puntero de origen en cada Fact derivado "por comodidad" es exactamente el tipo de atajo que produce inconsistencia silenciosa si el origen cambia (ver riesgo 12.7): un solo lugar de verdad, el resto es composición.

Cada Observation lleva un **puntero de origen canónico**, con un esquema fijo independientemente de qué parser lo produjo:

- **Tipo de fuente**: identifica el formato/origen (DXF, formulario, futura integración IFC/BIM — ver `NORTH_STAR_2031.md`).
- **Localizador**: dentro de ese tipo de fuente, la referencia exacta y reabrible — para un DXF, identificador del archivo (con su versión/hash) más el handle de entidad y capa dentro del propio DXF; para un formulario, el identificador del campo y el timestamp de envío.
- **Método de captura**: qué proceso produjo esta lectura (qué versión del parser, por ejemplo), necesario para poder reproducir exactamente el mismo resultado si se re-ingesta el mismo archivo más adelante.

El esquema de "tipo de fuente + localizador" es deliberadamente genérico en vez de específico de DXF: es lo que permite que, cuando `NORTH_STAR_2031.md` se cumpla y ArchMuse pase a ser IFC-nativo, la trazabilidad histórica de todos los proyectos ya evaluados en DXF siga siendo legible con el mismo esquema, sin una migración de formato de datos (riesgo 12.7 desarrolla qué pasa si no se hace así).

---

## 10. Cómo se representan los Unknown

Un Unknown (`REASONING_ENGINE_SPEC.md`, entidad 6) vive en el **mismo espacio de direccionamiento** que un Fact: mismo esquema de tipo namespaced, mismo esquema de ámbito. Esto no es casual — es lo que hace posible el principio rector de la sección 1: cualquier consumidor que pregunte por (ámbito, tipo) obtiene siempre una respuesta del mismo espacio de posibilidades, nunca un objeto de un tipo distinto que haya que tratar como caso especial.

El contrato de lectura para cualquier par (ámbito, tipo) devuelve exactamente uno de estos cuatro estados — nunca ausencia sin marcar:

| Estado | Significado |
|---|---|
| **Fact vigente** | El dato existe y está aceptado |
| **Unknown vigente** | El dato aplica a este ámbito, una o más Rules lo necesitan, y no se conoce — ni como Fact ni como Assumption |
| **Assumption vigente** | El dato no se conoce con certeza pero hay una hipótesis declarada cubriéndolo, con su rebaja de confianza asociada |
| **No aplicable** | El tipo de dato, por la naturaleza de este ámbito concreto, no tiene sentido — no es un vacío de información, es una pregunta que no corresponde hacer aquí |

El cuarto estado, **No aplicable**, no está en `REASONING_ENGINE_SPEC.md` de forma explícita y se añade aquí porque su ausencia es, por sí sola, uno de los riesgos de escala más serios del modelo (desarrollado en detalle en el riesgo 12.6): sin él, cada vez que una Rule de cualquiera de los 14 dominios pregunta por un dato que legítimamente no aplica a ese ámbito (orientación solar de un aseo interior sin fachada, por ejemplo), el sistema tendría que representarlo como Unknown — y con miles de Rules preguntando por miles de combinaciones (ámbito, tipo) mayormente no aplicables, el volumen de "Unknowns" ahogaría la señal real que el protocolo de información insuficiente de `DECISION_ENGINE.md` (sección 12) necesita para funcionar: distinguir qué vacío merece preguntarse activamente al Arquitecto de cuál no.

---

## 11. Diseño para soportar millones de Facts

Los principios anteriores son correctos pero no bastan por sí solos a gran escala sin estas cuatro decisiones explícitas de diseño:

### 11.1 Separar el histórico append-only de la proyección de estado vigente

El histórico completo (todas las instancias de todos los Facts, de todas las versiones, de todos los proyectos) es la fuente de verdad para auditoría y trazabilidad, pero **no** es la estructura que el Motor de Dominio debe consultar para evaluar Rules en tiempo real — recorrer todo el histórico para responder "¿cuál es el Fact vigente de X?" no escala. El modelo requiere una **proyección de estado vigente** por versión de ProjectState (concept_id → instancia vigente), mantenida como una vista derivada y reconstruible, nunca como una fuente de verdad independiente — si diverge del histórico, se regenera desde él, nunca se edita a mano. Es exactamente la misma separación log-de-eventos / modelo-de-lectura que ya sostiene sistemas append-only a gran escala en otros dominios, aplicada aquí sin necesidad de nombrar tecnología concreta.

### 11.2 Namespacing por proyecto desde el primer día

El id de concepto y el id de instancia incluyen el proyecto como parte de su espacio de nombres, aunque hoy (MVP de `PRD-001-Core-Reasoning-Engine.md`) solo exista un proyecto a la vez en juego. La razón no es especulativa: `ARCHITECTURAL_KNOWLEDGE_MAP.md` ya señala que el Dominio 14 (Benchmark de Mercado) necesitará, cuando exista un dataset real (no antes — ver la disciplina ya fijada contra el percentil fabricado), consultar Facts a través de muchos proyectos simultáneamente. Diseñar el namespacing ahora cuesta prácticamente nada; añadirlo después de que existan millones de Facts sin esa dimensión es una migración de datos completa.

### 11.3 Deduplicación segura, nunca por valor desnudo

Dos Facts con el mismo valor no son necesariamente el mismo dato: dos piezas distintas pueden coincidir en superficie por pura casualidad, y una misma función de composición puede cambiar de versión con el tiempo (una fórmula geométrica se refina) sin que el valor resultante cambie para un caso concreto. El hash de contenido usado para deduplicar (sección 3) se calcula sobre **tipo + ámbito + valor + identificador de la función/versión que lo generó**, nunca sobre el valor en solitario — deduplicar solo por valor colapsaría datos que son, epistémicamente, distintos, incluso si hoy coinciden.

### 11.4 Recalculo limitado por alcanzabilidad, no global

Ya introducido en la sección 6 como requisito, se reafirma aquí como propiedad de escala: cuando un Fact primario cambia, solo se recalculan los Facts derivados y solo se re-evalúan las Rules que son alcanzables desde él a través del grafo de derivación y de las dependencias declaradas entre Domains (`CHAIN_REASONING.md`, sección 6). Un modelo que, ante cualquier cambio, reevaluara "todo lo que exista" es correcto a la escala de un proyecto de prueba con 2 dominios y se vuelve computacionalmente inviable en cuanto hay 14 dominios y miles de Rules operando sobre millones de Facts acumulados — el grafo de alcanzabilidad es lo que mantiene el coste de cada Change proporcional a su impacto real, no al tamaño total del sistema.

---

## 12. Autorrevisión — simplificaciones que rompen el motor a 14 dominios y más de 2.000 reglas

Cada punto sigue el mismo formato: la simplificación que parece razonable a la escala actual (MVP de 2 dominios, `PRD-001`), por qué deja de sostenerse a 14 dominios / 2.000+ reglas, y la corrección ya incorporada (o pendiente de vigilar) en las secciones anteriores.

### 12.1 La frontera Fact-derivado / Inference se erosiona sin un guardián único

**Simplificación tentadora:** dejar que cada dominio defina sus propias "composiciones" de Facts según lo que le resulte cómodo en cada caso concreto.
**Por qué rompe a escala:** con 14 curadores de conocimiento trabajando en paralelo sobre 2.000+ reglas, es matemáticamente probable que varios resuelvan casos ambiguos "convirtiéndolos en Fact derivado" para evitarse el aparato de Rule+Constraint+Evidence — sobre todo bajo presión de tiempo. El resultado, acumulado, es una segunda capa de lógica de facto (funciones de composición con juicio normativo embebido) sin las garantías de Evidence, severidad ni Confidence que sí tiene una Rule — la misma opacidad que el modelo entero existe para prevenir, reintroducida por la puerta de atrás.
**Corrección:** el catálogo de funciones de composición es único, compartido entre dominios y mantenido por el Curador de Conocimiento (sección 4) — no un catálogo por dominio. Cualquier propuesta de composición que necesite un umbral o conocer su Domain consumidor se rechaza en el catálogo y se redirige a Rule. Esto requiere disciplina de gobernanza, no solo diseño de datos — se deja marcado aquí como el riesgo número uno a vigilar activamente, no como algo que el modelo de datos por sí solo pueda garantizar para siempre.

### 12.2 Un espacio de nombres plano de "tipo de Fact" colisiona entre dominios

**Simplificación tentadora:** usar strings libres como tipo de dato (`altura`, `superficie`, `capacidad`).
**Por qué rompe a escala:** con 14 dominios, es casi seguro que dos elijan el mismo nombre para conceptos distintos (`altura` de techo en Dominio 3 vs `altura` de un elemento estructural en Dominio 11) o nombres distintos para el mismo concepto, duplicando Facts que deberían ser uno solo.
**Corrección:** tipo namespaced (sección 3) sobre un glosario central único mantenido por el Curador de Conocimiento — mismo principio de gobernanza centralizada que 12.1, aplicado a nombres en vez de a funciones.

### 12.3 Un único árbol de contención física no representa todos los dominios

Ya desarrollado en detalle en la sección 2.3 — se referencia aquí como recordatorio de que es, en sí mismo, un riesgo de ruptura a escala, no solo una elección estética de modelado. Corrección ya incorporada: ámbito como conjunto de dimensiones abierto, no un único árbol.

### 12.4 La marca de origen epistémico se ignora si es opcional

**Simplificación tentadora:** guardar el eje de origen epistémico (sección 2.1) como un metadato adicional que un consumidor puede consultar si le interesa.
**Por qué rompe a escala:** con 2.000+ reglas implementadas por curadores distintos a lo largo de años, es prácticamente seguro que algunas implementaciones de Rule lean el valor de un Fact promovido desde Assumption sin comprobar su origen, tratándolo con la misma confianza que un dato observado — es exactamente la misma clase de fallo que el Bug #1 confirmado en `TECH_REVIEW.md`, solo que a nivel del modelo de Facts en vez de a nivel de parámetros de función.
**Corrección:** el contrato de lectura de un Fact (sección 10) no permite obtener el valor sin obtener también su eje de origen en la misma llamada — no es un campo adicional a comprobar por voluntad del consumidor, es parte indivisible de la respuesta.

### 12.5 Invalidación global en vez de limitada por alcanzabilidad

Ya desarrollado en las secciones 6 y 11.4. Se reafirma aquí porque es el riesgo con mayor impacto en coste computacional puro: a la escala de un proyecto de prueba, recalcular "todo" tras cada cambio es imperceptible; a la escala de un proyecto real con miles de Facts y 2.000+ Rules, es la diferencia entre una edición que responde en segundos y una que no responde en absoluto.

### 12.6 Unknown sin un estado "No aplicable" ahoga la señal real

Ya desarrollado en la sección 10. Se reafirma aquí porque el efecto solo se manifiesta a escala: con 2 dominios y un puñado de Rules, la diferencia entre "no aplica" y "no se sabe" apenas se nota; con 14 dominios preguntando por miles de combinaciones (ámbito, tipo) en cada evaluación, la mayoría de las cuales no aplican al ámbito concreto, el protocolo de información insuficiente de `DECISION_ENGINE.md` dejaría de ser útil si tuviera que distinguir señal real entre miles de falsos vacíos.

### 12.7 Punteros de origen específicos de formato en vez de un esquema canónico

Ya desarrollado en la sección 9. Se reafirma aquí porque el coste de no hacerlo bien ahora no se paga en el MVP (solo existe DXF como fuente) sino años después, cuando exista una segunda fuente (IFC, según `NORTH_STAR_2031.md`) y haya que decidir si se reescribe la trazabilidad histórica de todos los proyectos ya evaluados o si se vive con dos esquemas de trazabilidad incompatibles conviviendo indefinidamente. Ninguna de las dos opciones es aceptable; la corrección (esquema tipo-de-fuente + localizador, genérico desde el principio) evita tener que elegir.

### 12.8 Evaluación disparada por Fact individual en vez de por lote de ingesta

Ya desarrollado en la sección 5. Se reafirma aquí como riesgo de rendimiento puro: una ingesta que produce cientos de Facts geométricos de golpe (un proyecto grande con muchas plantas y unidades) dispararía, sin agrupación por lote, cientos de ciclos de re-evaluación redundantes del Motor de Dominio en el mismo instante — cada uno viendo un ProjectState ligeramente distinto del anterior, sin que ese detalle aporte ningún valor de razonamiento adicional, solo coste.

### 12.9 Deduplicación por valor desnudo colapsa datos distintos

Ya desarrollado en la sección 11.3. Se reafirma aquí porque el fallo es silencioso: dos Facts erróneamente tratados como "el mismo dato" no producen ningún error visible, solo pérdida silenciosa de precisión en la trazabilidad — el tipo de bug más difícil de detectar después de que ha ocurrido, precisamente el tipo que este modelo entero existe para prevenir en otras capas.

---

## Cierre

Los nueve riesgos de la sección 12 comparten una misma raíz: todos son simplificaciones que **no fallan de forma visible a la escala del MVP** (2 dominios, `PRD-001-Core-Reasoning-Engine.md`) y que **sí fallan, de formas costosas o silenciosas, en cuanto el sistema crece hacia los 14 dominios y miles de reglas** que es, explícitamente, el horizonte para el que se pidió diseñar este modelo. Ninguno de los nueve requiere revertir una decisión ya tomada en `REASONING_ENGINE_SPEC.md` — todos son refinamientos dentro del mismo marco (append-only, separación dato/lógica, trazabilidad obligatoria) aplicados con el nivel de detalle que ese marco todavía no había bajado a la entidad Fact en concreto. El de mayor riesgo real de los nueve, con diferencia, es el 12.1 (la frontera Fact-derivado/Inference): es el único que no se puede resolver solo con estructura de datos, depende de disciplina de gobernanza sostenida durante años por un Curador de Conocimiento — el mismo tipo de disciplina que `PROJECT_AUDIT.md` y `TECH_REVIEW.md` ya identificaron como el activo más difícil de replicar por un competidor, y el más fácil de perder por negligencia propia.
