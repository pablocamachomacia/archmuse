# INFERENCE_ENGINE.md

**Propósito:** diseñar el motor de inferencias — cómo, a partir de Facts evaluados contra Constraints, nacen las Inferences (`REASONING_ENGINE_SPEC.md` entidad 10) en sus distintas formas, cómo se invalidan, cómo se justifican, y — el punto más delicado — cómo el sistema evita, de forma estructural, producir dos inferencias que se contradigan sin que nadie se entere. Sin código ni implementación, como el resto de la serie: es el diseño del razonamiento, no del programa que lo ejecuta.

**Referencias obligatorias, asumidas como ya decididas:**
- `REASONING_ENGINE_SPEC.md` — entidad 10 (Inference) y entidad 11 (Problem, su especialización de incumplimiento), entidad 14 (ChainEffect), entidad 15 (Conflict), entidad 18 (Evidence), entidad 19 (Explanation), entidad 20 (Confidence, valor derivado, siempre cualitativo). Este documento no redefine ninguna — profundiza en cómo nace y se comporta la entidad 10 en sus distintas formas.
- `FACT_MODEL.md` — el contrato de lectura de cuatro estados (Fact/Unknown/Assumption/No aplicable, §10), que el motor de inferencias tiene que respetar al leer sus entradas, y el principio de invalidación limitada por alcanzabilidad (§6, §11.4), reutilizado aquí para el grafo de dependencia entre Inferences.
- `CONSTRAINT_MODEL.md` — el catálogo cerrado de 5 patrones de evaluación (§3.1) que sigue siendo la única forma en que una Inference se produce; este documento no añade un sexto patrón, clasifica lo que los cinco ya producen.
- `CHAIN_REASONING.md` — el modelo de propagación, las 3 clases de dependencia entre dominios (§6) y la regla de explicabilidad de mostrar la cadena causal completa, nunca un veredicto colapsado (§10).
- `DECISION_ENGINE.md` — la jerarquía de severidad de 4 valores (§3) y el modelo de confianza cualitativo (§10) — este documento, en la sección 2.3, resuelve explícitamente cómo "probabilístico" encaja sin romper esa regla.
- `BRAIN_ARCHITECTURE.md` — Parte 1.8, la invariante de que ninguna severidad bloqueante puede quedar oculta o agregada en un promedio; se reutiliza aquí por tercera vez en la serie (después de `CONSTRAINT_MODEL.md` §6 y `OBSERVATION_MODEL.md` §4).
- `OBSERVATION_MODEL.md` — el Hallazgo y su criterio de agrupación "Conflicto compartido" (§4), que en este documento se conecta explícitamente al mecanismo de detección de contradicciones (sección 6).

**Actor nuevo, añadido al glosario ya establecido:**
- **Verificador de Coherencia** — el proceso único y compartido entre los 14 dominios que, justo después de que el Motor de Propagación alcanza un punto fijo y justo antes de que el Motor de Síntesis de Hallazgos agrupe (`OBSERVATION_MODEL.md`), escanea el conjunto de Inferences vigentes en busca de contradicciones y las materializa como Conflict — nunca las resuelve, nunca las oculta. Mismo patrón de gobernanza que los tres actores nombrados en documentos anteriores: una pieza única y cerrada, no catorce implementaciones de "cómo comprobar coherencia" distintas.

---

## 1. Punto de partida: qué ya está decidido y qué añade este documento

`REASONING_ENGINE_SPEC.md` ya fijó lo esencial de Inference: nace de una Rule aplicando Facts (y Constraints), es determinística, se invalida (no se edita) cuando cambia algo de lo que depende, y Problem es su especialización de incumplimiento. Lo que ese documento no hizo — porque no le correspondía a ese nivel de detalle — es responder a cinco preguntas que se vuelven imposibles de ignorar en cuanto existen miles de Rules en 14 dominios: ¿de dónde viene estructuralmente una inferencia que depende de otras inferencias?, ¿cómo se representa con seguridad la conclusión de que algo *no* existe?, ¿qué significa "probabilístico" sin traicionar el principio de confianza cualitativa?, ¿qué pasa con el carácter bloqueante cuando una inferencia se compone de varias?, y — la más importante — ¿qué impide, estructuralmente, que dos inferencias válidas por separado se contradigan sin que el sistema lo perciba? Este documento responde a las cinco.

---

## 2. Cuatro ejes ortogonales, no cinco categorías planas

El encargo pide cinco tipos de inferencia (directa, compuesta, negativa, probabilística, bloqueante). Tratarlos como cinco casillas de una lista plana sería el mismo error que `FACT_MODEL.md` §2 ya evitó para Fact: una inferencia real casi siempre combina varios de estos rasgos a la vez (una inferencia puede ser compuesta, negativa y bloqueante simultáneamente), y una lista plana obligaría a inventar una casilla nueva por cada combinación. En su lugar, se definen **cuatro ejes ortogonales**, cada Inference se clasifica en los cuatro simultáneamente — la quinta categoría del encargo (bloqueante) se resuelve como valor de uno de esos ejes, no como una etiqueta aparte.

| Eje | Valores | Pregunta que responde |
|---|---|---|
| **A. Estructura de origen** | directa / compuesta | ¿de qué depende, solo Facts o también otras Inferences? |
| **B. Polaridad** | positiva / negativa | ¿afirma que algo se cumple/existe, o que no? |
| **C. Naturaleza de la confianza** | determinística / probabilística | ¿su Confidence se deriva de una cadena de Nivel 1-2 limpia, o incorpora incertidumbre? |
| **D. Severidad** | bloqueante / no bloqueante | ¿puede, por sí sola, impedir una conclusión de viabilidad? |

Esta forma de organizarlo no es solo estética: es lo que evita que el catálogo de "tipos de inferencia" crezca sin límite a medida que aparecen combinaciones nuevas — el mismo argumento anti-explosión-combinatoria que ya justificó los tres ejes de Fact.

### 2.1 Eje A — directa / compuesta

- **Directa**: producida por un único patrón de evaluación (`CONSTRAINT_MODEL.md` §3.1) sobre Facts directamente disponibles en su ámbito, sin consumir ninguna otra Inference. Es el caso base — "el pasillo mide 0,85m, el mínimo es 0,90m, incumple".
- **Compuesta**: consume, como parte de sus entradas, una o más Inferences ya producidas — no solo Facts. Corresponde al patrón COMBINACION_LOGICA de `CONSTRAINT_MODEL.md` cuando combina resultados de otros Constraints, y a cualquier Inference que consuma la conclusión de un Domain distinto por dependencia de referencia (`CHAIN_REASONING.md` §6). **Invariante:** la Confidence de una Inference compuesta nunca puede superar la del eslabón más débil entre todas las Inferences y Facts que consume — no es una regla nueva, es la aplicación literal de `DECISION_ENGINE.md` §10 al caso donde la cadena tiene más de un tramo, que es precisamente donde esta regla importa de verdad.

No confundir "compuesta" con "Fact derivado" (`FACT_MODEL.md` §4): un Fact derivado es aritmética pura sin juicio, sigue siendo Nivel 1. Una Inference compuesta consume **conclusiones** (Nivel 2 en adelante), nunca solo datos — es la frontera inversa y simétrica a la que `FACT_MODEL.md` §4 ya defendió, y se reafirma aquí por el mismo motivo: si se difumina, una composición de Facts empieza a colarse como si fuera juicio, o un juicio empieza a tratarse como si fuera solo aritmética.

### 2.2 Eje B — positiva / negativa

- **Positiva**: afirma que algo se cumple, existe, o tiene un valor determinado. Es el caso implícito por defecto y no requiere tratamiento especial.
- **Negativa**: afirma que algo **no** se cumple, **no** existe o **no** está presente — "esta vivienda no tiene ventilación cruzada", "no se detectan solapes de huella entre unidades".

El riesgo estructural de una inferencia negativa es específico y grave: confundir *ausencia de evidencia* con *evidencia de ausencia*. Por eso, este eje lleva su propia invariante, más estricta que la de cualquier otro: **una Inference negativa solo puede producirse a partir de un resultado `no_existe` explícito de una Constraint con patrón PRESENCIA_OBLIGATORIA (`CONSTRAINT_MODEL.md` §3.1), nunca de un Unknown ni de un Fact ausente.** Si el dato que determinaría presencia/ausencia es Unknown, el resultado correcto es "Constraint no evaluable" (`CONSTRAINT_MODEL.md` §4), nunca una Inference negativa disfrazada de conclusión. Esta es, otra vez, la misma familia de bug que el Bug #1 confirmado en `TECH_REVIEW.md` — aquí, en su forma más peligrosa, porque una inferencia negativa mal fundamentada no falla de forma ruidosa, falla como una afirmación tranquilizadora ("no hay problema") que nadie cuestiona.

Una inferencia negativa correctamente fundamentada puede alimentar tanto un Problem (incumplimiento: "no tiene ventilación cruzada" siendo obligatoria) como un Hallazgo positivo (`OBSERVATION_MODEL.md` §3: "no se detectan solapes de huella" es una ausencia deseable) — la polaridad de la Inference y la valoración de si esa ausencia es buena o mala son cosas distintas, la segunda depende del Constraint que la interpreta, no de la Inference en sí.

### 2.3 Eje C — determinística / probabilística

- **Determinística**: su Confidence se deriva de una cadena de Evidence compuesta enteramente por Facts observados/derivados y Rules de Nivel 1-2 — el caso más frecuente y el de mayor confianza posible.
- **Probabilística**: alguna parte de su cadena de Evidence incorpora incertidumbre real — una Observation que su propia fuente marcó como ambigua (`REASONING_ENGINE_SPEC.md` entidad 4), una Assumption todavía sin sustituir, o una cadena de propagación (`CHAIN_REASONING.md`) larga cuyos tramos intermedios ya son, de por sí, Nivel 3-4.

Esta es la resolución explícita del punto que motivó la pregunta antes de escribir este documento: **la probabilidad es una señal de cálculo interno, nunca un dato expuesto.** Su único destino es decidir, mediante una tabla de resolución cerrada y gobernada por el Curador de Conocimiento — la misma filosofía de tabla de resolución declarativa que `CONSTRAINT_MODEL.md` §9 ya usa para parámetros contextuales, reutilizada aquí para un propósito distinto — en cuál de las tres cubetas cualitativas ya fijadas (Alta/Media/Baja, `DECISION_ENGINE.md` §10) cae la Inference. Una vez asignada la cubeta, el valor numérico interno **no se serializa** en Evidence ni en Explanation ni en ningún campo visible para el Arquitecto — puede conservarse en un registro interno de calibración que solo consulta el Curador de Conocimiento para ajustar la tabla de resolución con el tiempo, nunca como parte del contrato de lectura de una Inference. Esto no reabre el principio de confianza cualitativa fijado en `DECISION_ENGINE.md` — lo respeta al pie de la letra, solo precisa qué significa "probabilística" sin traicionarlo: la incertidumbre es real y se modela, pero nunca se presenta con una falsa precisión que el sistema no tiene, exactamente la lección ya aprendida con `TIPOLOGIA_BENCHMARKS`.

**Invariante:** ninguna Inference cuya cadena de Evidence incluya un tramo Nivel 3-4 o una Assumption puede caer en la cubeta "Alta" — no es una regla nueva de este documento, es `REASONING_ENGINE_SPEC.md` entidad 20 aplicada explícitamente al mecanismo de bucketing que aquí se define.

### 2.4 Eje D — bloqueante / no bloqueante

Toma directamente la jerarquía de severidad ya fijada en `DECISION_ENGINE.md` §3 (bloqueante / riesgo variable / recomendable / preferencial) y la colapsa, para este eje, a una distinción binaria: bloqueante, o cualquiera de los otros tres. El motivo de tratarlo aparte, en vez de como un quinto valor suelto de severidad, es que el carácter bloqueante tiene una propiedad de propagación que los otros tres no necesitan tener con el mismo rigor: **si una Inference compuesta consume, entre sus entradas, al menos una Inference bloqueante, la Inference compuesta resultante es bloqueante también** — nunca se diluye combinándola con entradas no bloqueantes, tercera aparición en esta serie de la misma invariante de `BRAIN_ARCHITECTURE.md` Parte 1.8 (máximo, nunca promedio), aquí aplicada a la propagación estructural del carácter bloqueante a través del eje A.

Un matiz que hay que dejar explícito porque es fácil de asumir mal: **severidad bloqueante y Confidence alta no son la misma cosa, y una no implica la otra.** Una Inference puede ser bloqueante y, al mismo tiempo, probabilística con Confidence Media o Baja (p. ej., un incumplimiento bloqueante que depende de una Assumption todavía no confirmada). Esta combinación — la de mayor riesgo real del sistema entero, porque junta "esto podría impedir el proyecto" con "no estamos seguros" — nunca puede presentarse con menos prominencia que cualquier otra; se marca de forma explícita en Evidence y Explanation (sección 5), nunca se deja para que el Arquitecto la descubra leyendo con atención.

**Invariante heredada sin cambios de `DECISION_ENGINE.md` §9:** una Preference nunca puede suprimir ni relajar una Inference bloqueante.

---

## 3. Cómo se generan

La generación de cualquier Inference — sea cual sea su combinación de los cuatro ejes — sigue siendo, exclusivamente, uno de los cinco patrones cerrados de `CONSTRAINT_MODEL.md` §3.1, ejecutados por el Intérprete de Constraints bajo la orquestación del Motor de Dominio. Este documento no añade un mecanismo de generación nuevo — clasifica lo que esos cinco patrones ya producen, según los cuatro ejes de la sección 2.

El disparo sigue el mismo principio de alcanzabilidad ya fijado en `FACT_MODEL.md` §11.4: una Inference se (re)genera cuando cambia alguno de los Facts o Inferences de los que depende — nunca por una barrida global. Para Inferences compuestas cuya entrada cruza de un Domain a otro, el disparo lo produce el Motor de Propagación al recorrer las dependencias declaradas (estructural / condicional / de referencia, `CHAIN_REASONING.md` §6), y cada salto de ese recorrido es, literalmente, un ChainEffect (`REASONING_ENGINE_SPEC.md` entidad 14) — el grafo de dependencia entre Inferences no es una estructura nueva que este documento tenga que definir, ya existe como el propio registro de ChainEffects acumulado.

**Invariante de determinismo, reafirmada sin cambios:** los mismos Facts (e Inferences, para el caso compuesto) con la misma Rule producen siempre la misma Inference. Si dos ejecuciones sobre el mismo estado producen resultados distintos, no es una "inferencia probabilística" — es un defecto del patrón de evaluación o de la Constraint que lo alimenta, y se corrige ahí, nunca disfrazándolo de incertidumbre legítima.

---

## 4. Cómo se invalidan

Igual que Fact e Inference en general (`REASONING_ENGINE_SPEC.md` entidad 10): nunca se editan, se invalidan y se recalculan como una instancia nueva. Lo que este documento añade es cómo se decide el alcance de esa invalidación en cascada para cada eje:

- **Directa**: se invalida cuando cambia cualquier Fact que consume directamente — caso simple, ya cubierto por `FACT_MODEL.md` §6.
- **Compuesta**: se invalida también cuando cualquier Inference que consume se invalida — la cascada recorre el grafo de ChainEffects hacia adelante, limitada por alcanzabilidad, nunca una reevaluación global (mismo argumento de coste computacional que `FACT_MODEL.md` §11.4 ya hizo para Facts, aplicado ahora un nivel más arriba).
- **Negativa**: nunca se trata como "válida hasta que se demuestre lo contrario" — se recalcula exactamente con la misma disciplina que cualquier otra Inference cada vez que cambian sus Facts de entrada; no existe una variante de invalidación más perezosa para el caso negativo, precisamente porque "asumir que sigue siendo cierto que algo no existe" es la puerta de entrada al mismo riesgo ya señalado en la sección 2.2.
- **Probabilística**: se reevalúa no solo cuando cambia el Fact/Inference que consume, sino también cuando cambia la señal de incertidumbre que la sostiene — el caso típico es que una Assumption de la que dependía se sustituya por un Fact real (`REASONING_ENGINE_SPEC.md` entidad 7): eso puede mover la Inference de cubeta (de Media a Alta, por ejemplo) sin que ningún valor "de negocio" haya cambiado, solo la certeza sobre él. Este recálculo de cubeta debe dispararse con la misma prioridad que cualquier otra invalidación, nunca tratarse como una actualización de segunda clase.
- **Bloqueante**: se invalida igual que cualquier Inference, pero su resolución (dejar de ser bloqueante) exige que el propio Fact/Inference que la causaba cambie — nunca puede "dejar de ser bloqueante" por una Preference ni por una Decision que no haya corregido realmente la causa (una Decision puede marcarla como "aceptada con justificación", que es un estado distinto de "resuelta", mismo mecanismo ya fijado para Problem en `REASONING_ENGINE_SPEC.md` entidad 11).

---

## 5. Cómo se justifican

Toda Inference, sin excepción, lleva Evidence (`REASONING_ENGINE_SPEC.md` entidad 18) — invariante ya fijada, no se repite aquí más que para anclar lo que sigue: qué debe contener esa Evidence específicamente para cada eje.

| Eje / valor | Qué añade a la Evidence, más allá del contenido mínimo ya fijado |
|---|---|
| **Compuesta** | La cadena causal completa, tramo a tramo, citando Domain y criterio en cada salto — nunca un veredicto final colapsado (regla ya fijada en `CHAIN_REASONING.md` §10, reafirmada aquí como requisito de Evidence, no solo de Explanation) |
| **Negativa** | Qué Constraint y qué Fact(s) concretos establecieron el `no_existe` — la prueba positiva de ausencia, nunca "no se encontró nada relacionado" como única justificación |
| **Probabilística** | Qué cubeta se asignó y qué elemento de la cadena la determinó (Observation ambigua / Assumption pendiente / cadena larga de Nivel 3-4) — nunca el valor numérico interno que la produjo |
| **Bloqueante** | Se marca con máxima prominencia, y si además es probabilística con Confidence Media/Baja, ambas condiciones se muestran juntas, nunca una sin la otra |

La Explanation (`REASONING_ENGINE_SPEC.md` entidad 19) que se genera a partir de esta Evidence hereda las mismas obligaciones ya fijadas allí — nunca puede afirmar más certeza de la que su Evidence sostiene. Este documento no añade una obligación nueva a Explanation; confirma que las cuatro filas de la tabla anterior son, precisamente, lo que hace posible cumplirla en la práctica para cada tipo de Inference.

---

## 6. Cómo se evita generar inferencias contradictorias

Esta es la pregunta con más riesgo real del documento, y se responde en dos capas: qué previene contradicciones **antes** de que se generen, y qué hace el sistema con las que, legítimamente, no se pueden prevenir.

### 6.1 Prevención estructural (antes de generar)

Dos invariantes ya existentes hacen la mayor parte del trabajo, y vale la pena nombrarlas juntas aquí porque es donde su combinación importa:

1. **Determinismo** (`REASONING_ENGINE_SPEC.md` entidad 10) — elimina la contradicción-por-defecto: la misma Rule sobre los mismos Facts nunca puede producir dos conclusiones distintas. Si eso ocurre, no es una contradicción legítima del modelo, es un fallo del patrón de evaluación o de la Constraint, y se corrige ahí.
2. **Unicidad de Constraint por ámbito** (`REASONING_ENGINE_SPEC.md` entidad 8) — "dos Constraints vigentes simultáneamente para el mismo ámbito exacto es una contradicción que debe bloquearse en el momento de creación, no descubrirse en evaluación." Esto significa que, **dentro de un mismo Domain**, la contradicción ya está prevenida en el momento en que el Curador de Conocimiento da de alta el Constraint — el motor de inferencias puede asumir, como precondición, que el catálogo de un Domain es internamente consistente, y no tiene que re-verificarlo en cada evaluación.

Lo que estas dos invariantes **no** cubren, y no pueden cubrir por diseño, es la contradicción **entre dominios distintos** — y ahí es donde entra la segunda capa, porque prevenirla del todo sería, en la práctica, prohibir que dos especialistas legítimos puedan discrepar, que es exactamente el tipo de discrepancia real que `DECISION_ENGINE.md` (Tipo 5: discrepancia legítima de criterio) ya reconoce que puede no tener resolución automática.

### 6.2 Detección y exposición (cuando la prevención no basta)

El Verificador de Coherencia se ejecuta una vez que el Motor de Propagación alcanza un punto fijo, sobre el conjunto completo de Inferences vigentes, con un catálogo cerrado de tres criterios de contradicción — cerrado por el mismo motivo que todos los catálogos anteriores de esta serie: para que detectar contradicciones no dependa de que cada dominio implemente su propia noción de "esto no encaja":

| Criterio | Qué detecta |
|---|---|
| **Contradicción directa** | Dos Inferences vigentes sobre el mismo (ámbito, tipo namespaced) cuyas conclusiones son lógicamente incompatibles — una afirma, otra niega, el mismo predicado. Se detecta con el mismo mecanismo de huella que `OBSERVATION_MODEL.md` §5 usa para deduplicar, aplicado aquí al caso inverso: mismo (ámbito, tipo), conclusión incompatible en vez de repetida |
| **Contradicción por severidad oculta** | Una Inference compuesta cuya severidad de presentación no es el máximo de sus entradas (violación directa de la invariante de la sección 2.4) — se trata como un defecto de composición, nunca como una contradicción legítima a exponer |
| **Contradicción por composición sobre conflicto no resuelto** | Una Inference compuesta que se genera consumiendo Inferences que ya están en un Conflict abierto sin resolver — construirla igualmente "lavaría" la contradicción no resuelta dentro de una conclusión que parece limpia. Se bloquea: la Inference compuesta no se produce con Confidence normal, queda marcada como no evaluable hasta que el Conflict que la sostiene se resuelva |

**Ninguno de los tres criterios se resuelve automáticamente.** El primero materializa un Conflict nuevo (`REASONING_ENGINE_SPEC.md` entidad 15); el segundo es un defecto que se corrige en el patrón de composición, no una contradicción de conocimiento; el tercero bloquea la composición hasta que exista una Decision. En los tres casos, la disciplina es la misma que ya rige todo el modelo: **nunca silenciar, nunca promediar, nunca elegir un lado sin que quede registrado quién lo decidió** — un Conflict de Tipo 5 (discrepancia legítima, `DECISION_ENGINE.md` §2) puede quedar permanentemente abierto sin que eso sea un fallo del sistema, es, literalmente, el resultado correcto cuando dos criterios de Nivel 4 discrepan de forma genuina.

El orden de ejecución importa y queda fijado aquí: **Motor de Propagación (punto fijo) → Verificador de Coherencia (detecta y materializa Conflicts) → Motor de Síntesis de Hallazgos (`OBSERVATION_MODEL.md`, agrupa usando "Conflicto compartido" como uno de sus criterios, sección 4 de ese documento)**. Sin este orden, el Motor de Síntesis no tendría Conflicts materializados todavía sobre los que aplicar su criterio de agrupación — es la pieza que faltaba para que esa parte de `OBSERVATION_MODEL.md` funcionara tal como estaba descrita, y este documento la completa.

---

## 7. Cierre

Los cuatro ejes de la sección 2 no son un vocabulario nuevo de clasificación por clasificar — cada uno existe porque protege contra un riesgo concreto ya visto en este proyecto: el eje de polaridad (2.2) contra la confusión ausencia-de-evidencia/evidencia-de-ausencia; el eje de confianza (2.3) contra la recaída en precisión fabricada que ya costó el percentil de `TIPOLOGIA_BENCHMARKS`; el eje de severidad (2.4) contra la dilución de lo bloqueante que `BRAIN_ARCHITECTURE.md` Parte 1.8 lleva prohibiendo desde el primer documento de la serie. La sección 6 no resuelve contradicciones — las hace imposibles de ignorar, que es la única promesa que un motor de razonamiento honesto puede hacer cuando, por diseño, va a alojar catorce puntos de vista expertos distintos sobre el mismo edificio.
