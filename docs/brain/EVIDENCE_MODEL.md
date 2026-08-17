# EVIDENCE_MODEL.md

**Propósito:** diseñar el modelo de Evidence — cómo se construye el paquete de razonamiento que justifica cualquier afirmación del sistema, de forma que el principio ya fijado en `REASONING_ENGINE_SPEC.md` ("ninguna conclusión existe sin Evidence") deje de ser una declaración de intenciones y se convierta en una estructura concreta: qué contiene un tramo de Evidence, cómo se le asigna una fuerza sin inventar precisión que no existe, y cómo esa fuerza se convierte, mecánicamente, en la Confidence que el Arquitecto finalmente ve. Sin código, como el resto de la serie.

**Referencias obligatorias, asumidas como ya decididas:**
- `REASONING_ENGINE_SPEC.md` — entidad 18 (Evidence), entidad 19 (Explanation), entidad 20 (Confidence, valor derivado y siempre cualitativo). Este documento no las redefine — especifica, con el detalle que faltaba, cómo se construye la primera y cómo se calcula mecánicamente la tercera a partir de ella.
- `FACT_MODEL.md` — el eje de origen epistémico de Fact (§2.1, observado/derivado/promovido), el esquema canónico de puntero de origen hasta el DXF (§9), y el contrato de lectura donde el origen de un Fact es inseparable de su valor (§10, riesgo 12.4) — esta última regla se hereda aquí sin excepción para Evidence.
- `CONSTRAINT_MODEL.md` — la estructura de normativa asociada (§8), la tabla de resolución de parámetros (§9) y los cuatro niveles de conocimiento (`ARCHITECTURAL_KNOWLEDGE_MAP.md`), reutilizados aquí como el eje que, junto al origen epistémico, determina la fuerza de un tramo (sección 3).
- `CHAIN_REASONING.md` — §10: la cadena causal completa se muestra paso a paso, nunca colapsada en un veredicto final. Este documento formaliza esa regla como una obligación estructural de Evidence, no solo de la narrativa que se construye a partir de ella.
- `INFERENCE_ENGINE.md` — §5, la tabla de qué debe añadir cada eje de Inference a su Evidence; este documento generaliza esas cuatro filas a la estructura completa de un tramo, válida para cualquier entidad de conclusión, no solo Inference.
- `DECISION_ENGINE.md` — §10, la regla del eslabón más débil, que este documento convierte en una operación concreta y determinista (sección 9), no solo en un principio.

---

## 0. Principio rector

Ya fijado, se reafirma aquí porque todo el documento existe para hacerlo operativo: **ninguna Inference, Problem, Conflict, Recommendation o Decision puede existir sin Evidence** (`REASONING_ENGINE_SPEC.md` entidad 18), y esa Evidence tiene que ser **completa** — cada elemento que la compone debe, a su vez, resolver en algo trazable (otro tramo de Evidence, o un puntero de origen final), nunca en un salto de fe. Una Evidence con un tramo opaco ("esto se calculó así, confía") no es Evidence — es una afirmación sin justificar disfrazada de una que sí lo está, exactamente lo que este modelo existe para impedir.

---

## 1. Estructura de un tramo de Evidence

Evidence, per `REASONING_ENGINE_SPEC.md` entidad 18, es "una lista ordenada de los elementos que la componen". Este documento define qué es, exactamente, un elemento de esa lista — un **tramo** — y qué debe llevar siempre:

| Atributo | Contenido |
|---|---|
| **tipo de tramo** | Uno de los seis tipos cerrados de la sección 2 |
| **origen** | El identificador del Fact/Constraint/Rule/Assumption/ChainEffect/Inference concreto que este tramo representa |
| **fuerza** | Alta/Media/Baja, calculada mecánicamente (sección 3) — nunca asignada a mano |
| **normativa asociada** | Presente si el tramo proviene de un Constraint (sección 5); ausente en tramos puramente geométricos o de cálculo |
| **puntero geométrico o traza de cálculo** | Presente según el tipo de tramo (secciones 6 y 7) |
| **posición en la cadena** | Su lugar en el orden causal, si el tramo participa de una cadena de más de un salto (sección 8) |

Ningún tramo puede omitir su origen ni su fuerza — son los dos atributos que hacen posible, respectivamente, la trazabilidad (sección 4) y la Confidence derivada (sección 9).

---

## 2. Origen: los seis tipos cerrados de tramo

Cerrado, como todos los catálogos de esta serie — un tramo de Evidence solo puede ser uno de estos seis, nunca una estructura libre inventada para un caso concreto:

| Tipo de tramo | Qué representa | Documento que lo define |
|---|---|---|
| **Fact** | Un dato aceptado, con su eje de origen epistémico visible (observado/derivado/promovido) | `FACT_MODEL.md` §2.1 |
| **Constraint** | El umbral/condición aplicado, con su normativa asociada | `CONSTRAINT_MODEL.md` §8 |
| **Assumption** | Una hipótesis que cubrió un Unknown | `REASONING_ENGINE_SPEC.md` entidad 7 |
| **ChainEffect** | Un salto de propagación entre dominios | `REASONING_ENGINE_SPEC.md` entidad 14 |
| **Inference** | Una conclusión ya producida, consumida como entrada de otra (caso compuesto) | `INFERENCE_ENGINE.md` §2.1 |
| **Excepción evaluada** | El registro de que una Excepción (`CONSTRAINT_MODEL.md` §5) se comprobó, aplicara o no | `CONSTRAINT_MODEL.md` §5 |

El origen de un tramo nunca es opcional ni un metadato aparte que un consumidor pueda ignorar — es, literalmente, lo que distingue un tramo válido de una afirmación sin respaldo. Esto no es una regla nueva: es la misma invariante que `FACT_MODEL.md` §12.4 ya defendió para el eje de origen epistémico de un Fact, extendida aquí a los seis tipos de tramo por igual.

---

## 3. Fuerza: cómo se califica cada tramo sin inventar precisión

Este es el vacío concreto que los documentos anteriores dejaban abierto: todos citan "el eslabón más débil" como regla de Confidence, pero ninguno definía, hasta ahora, cómo se califica la fuerza de un eslabón individual. Se resuelve con una **tabla de techos**, cerrada y gobernada por el Curador de Conocimiento — misma disciplina que la tabla de resolución de parámetros de `CONSTRAINT_MODEL.md` §9 — nunca un número calculado libremente por cada dominio.

Cada tramo tiene dos techos independientes, y su fuerza final es **el menor de los dos**:

**Techo por nivel de conocimiento** (`ARCHITECTURAL_KNOWLEDGE_MAP.md`):

| Nivel | Techo de fuerza |
|---|---|
| 1 — Hechos objetivos | Alta |
| 2 — Normativa verificable | Alta |
| 3 — Buenas prácticas | Media |
| 4 — Criterio arquitectónico | Baja |

**Techo por origen epistémico** (para tramos de tipo Fact, `FACT_MODEL.md` §2.1) o por naturaleza (para Assumption):

| Origen | Techo de fuerza |
|---|---|
| Fact observado | Alta |
| Fact derivado (composición pura, `FACT_MODEL.md` §4) | Igual que el techo del tramo de menor fuerza que compone — nunca superior a sus propias fuentes |
| Fact promovido desde Assumption | Media (nunca Alta, aunque su nivel de conocimiento fuera 1 — invariante ya fijada en `FACT_MODEL.md` entidad 5) |
| Assumption sin promover | Baja |

**Fuerza final del tramo = mínimo de los dos techos aplicables.** Un Fact observado que respalda un Constraint de Nivel 3 (buena práctica) tiene fuerza Media, no Alta — el dato es sólido, pero el criterio que lo interpreta no lo es. Un Fact derivado de una Assumption, aplicado a un Constraint de Nivel 1, tiene fuerza Media — el criterio es objetivo, pero el dato de entrada no lo es. Ninguno de los dos casos se puede resolver "promediando" — se resuelve tomando siempre el menor, la misma disciplina de `BRAIN_ARCHITECTURA.md` Parte 1.8 aplicada ahora a la calificación de un tramo individual, no solo al roll-up de severidad.

---

## 4. Trazabilidad

Una Evidence es trazable cuando **todo tramo resuelve, siguiendo la cadena hacia atrás, en un puntero de origen final** — el esquema canónico de tipo-de-fuente + localizador ya fijado en `FACT_MODEL.md` §9 (identificador del DXF con su versión/hash, handle de entidad, capa; o el campo de formulario y su timestamp). Esto no es una propiedad deseable de Evidence, es una condición de existencia: una Evidence con un tramo que no resuelve en ningún puntero final — un valor que "aparece" sin que se pueda seguir su procedencia — no es una Evidence válida, es exactamente el tipo de caja negra que toda la serie existe para impedir.

La trazabilidad es **transitiva y nunca se duplica**: un tramo de tipo Fact derivado no lleva su propio puntero al DXF — lleva la referencia a los Facts que compone (`FACT_MODEL.md` §8, relación 3, el grafo de derivación), y son esos Facts fuente los que, en última instancia, resuelven en un puntero real. Un tramo de tipo Inference (caso compuesto) no repite la Evidence completa de la Inference que consume — la referencia y la deja expandible, nunca la copia; si se duplicara, dos Evidence del mismo hecho podrían divergir con el tiempo sin que nadie lo notara, precisamente el riesgo que `FACT_MODEL.md` §12.7 ya señaló para los punteros de origen y que aquí se repite un nivel más arriba, para toda la cadena de razonamiento, no solo para el dato geométrico.

---

## 5. Normativa

Cuando un tramo es de tipo Constraint, su normativa asociada se hereda **sin reinterpretarla** de la estructura ya definida en `CONSTRAINT_MODEL.md` §8: fuente exacta, ámbito territorial, nivel de conocimiento, vigencia de la norma citada. Evidence no vuelve a decidir nada aquí — simplemente la transporta hasta la conclusión final, para que cualquier Explanation generada a partir de ella pueda citar el artículo/decreto exacto sin tener que ir a buscarlo en otro sitio.

Dos matices que sí son responsabilidad de Evidence, no de Constraint:

- Cuando la conclusión combina Constraints de varios niveles territoriales (el caso de la sección 13 de `CONSTRAINT_MODEL.md`, normativa autonómica sobre CTE estatal), Evidence conserva **ambas** citas si ambas participaron en la resolución de una condición de activación — nunca solo la que finalmente "ganó", porque el hecho de que existiera una alternativa autonómica es, en sí mismo, parte de por qué la conclusión es la que es.
- Cuando un tramo es de Nivel 3 (buena práctica, sin cita legal), su normativa asociada sigue siendo obligatoria como "criterio profesional: [documento/guía]" — nunca se deja vacía, mismo invariante ya fijado en `CONSTRAINT_MODEL.md` §8.

---

## 6. Geometría

Un tramo con contenido geométrico — la superficie medida, la forma de una pieza, la distancia de un recorrido — no se limita a citar "el Fact de superficie". Lleva, además, el **puntero geométrico resuelto**: qué entidad concreta del DXF (o de la fuente que corresponda) se usó, para que el propio tramo se pueda mostrar visualmente sobre el plano, no solo describirse en texto. Esto no introduce un mecanismo nuevo — es el mismo esquema canónico de `FACT_MODEL.md` §9 (tipo de fuente + localizador), simplemente elevado a un campo de primera clase del tramo en vez de quedar enterrado dentro del Fact que lo respalda, porque la Evidence de una conclusión geométrica sin la geometría visible a mano es, en la práctica, mucho menos verificable para un Arquitecto que la misma Evidence con el polígono señalado.

**Invariante:** un tramo de naturaleza geométrica (`FACT_MODEL.md` §2.2) nunca puede tener fuerza Alta si su puntero geométrico no resuelve en una entidad real y localizable — si el puntero está roto o ausente, el tramo cae automáticamente a fuerza Baja, nunca se asume que el dato es correcto solo porque el valor numérico está presente. Es la misma disciplina de "nunca silencio" aplicada aquí a la integridad del propio puntero, no solo a la existencia del dato.

---

## 7. Cálculo

Un tramo que representa un valor calculado — un Fact derivado (`FACT_MODEL.md` §4) o el parámetro resuelto de una tabla contextual (`CONSTRAINT_MODEL.md` §9) — lleva su **traza de cálculo**: qué función de composición (del catálogo único, `FACT_MODEL.md` §4) o qué nivel de la cadena de resolución de parámetros (`CONSTRAINT_MODEL.md` §9) se usó, y el valor concreto que produjo cada paso, no solo el resultado final. Esto tiene una consecuencia directa ya anticipada en `CONSTRAINT_MODEL.md` §9: **si la resolución de un parámetro tuvo que recurrir a un nivel de fallback en vez de una coincidencia exacta, ese hecho es parte obligatoria de la traza de cálculo** — nunca se muestra el valor final sin decir que vino de un fallback, otra vez la corrección estructural directa al patrón del Bug #1.

Un tramo de cálculo nunca lleva una fórmula libre ni un paso no perteneciente al catálogo cerrado de composición (`FACT_MODEL.md` §4) o al patrón de evaluación cerrado (`CONSTRAINT_MODEL.md` §3.1) — si un cálculo no se puede describir con esos vocabularios ya cerrados, no pertenece a Evidence como tramo de cálculo, pertenece a una Recommendation con juicio explícito (`REASONING_ENGINE_SPEC.md` entidad 12), que es una categoría distinta y ya se justifica de otra forma.

---

## 8. Cadena causal

Cuando una conclusión depende de más de un salto de propagación (`CHAIN_REASONING.md`), su Evidence incluye **cada ChainEffect como su propio tramo**, en el orden en que ocurrió, nunca colapsados en uno solo. Cada tramo de tipo ChainEffect cita el Domain de origen, el Domain de destino, y el tipo de efecto (inmediato/indirecto/acumulativo) — exactamente la regla de explicabilidad ya fijada en `CHAIN_REASONING.md` §10, aquí convertida en la forma concreta que adopta dentro de la estructura de Evidence en vez de quedar como una obligación solo de la narrativa.

La fuerza de la cadena completa nunca se calcula "sobre la cadena" como si fuera un tramo agregado — se calcula tramo a tramo (sección 9), y el tramo de menor fuerza de toda la cadena, sea un ChainEffect intermedio o el Fact original en el extremo, determina la Confidence final. Una cadena de seis saltos, cinco de ellos de Nivel 1-2 impecables y uno solo de Nivel 4, tiene la misma Confidence que si el salto débil fuera el único que existiera — la longitud de la cadena no diluye su punto más débil, lo hace más fácil de perder de vista si Evidence no lo mostrara explícitamente, que es exactamente lo que esta estructura evita.

---

## 9. Confianza derivada

Con la fuerza de cada tramo ya definida (sección 3) de forma determinista, la Confidence de la conclusión completa (`REASONING_ENGINE_SPEC.md` entidad 20) deja de ser un principio abstracto y se convierte en una operación concreta:

**Confidence de la conclusión = la fuerza más baja entre todos los tramos de su Evidence, sin excepción.**

No es un promedio, no es una mayoría, no es una fórmula ponderada — es un mínimo simple sobre un conjunto ya calificado con la tabla de techos de la sección 3. Esta simplicidad es deliberada: cualquier fórmula más elaborada (ponderar por número de tramos Altos, por ejemplo) reintroduciría precisión fabricada por la puerta de atrás — exactamente el mismo riesgo ya identificado y cerrado en `INFERENCE_ENGINE.md` §2.3 para el eje probabilístico, aquí aplicado a la operación de agregación en sí.

Dos casos de borde que hay que resolver explícitamente para que la operación esté completa:

- **Evidence con un tramo "no evaluable"** (un Unknown sin resolver, `CONSTRAINT_MODEL.md` §4) — la conclusión completa no tiene Confidence calculable en absoluto, no cae a "Baja": queda marcada como no evaluable hasta que ese tramo se resuelva (Fact real o Assumption), mismo estado que ya existe para Constraint y se hereda aquí sin cambios.
- **Evidence con un tramo de Excepción aplicada** (`CONSTRAINT_MODEL.md` §5) — no participa en el cálculo del mínimo, porque no es una afirmación de valor sino el registro de que el Constraint se retiró de la evaluación; se conserva en la Evidence por trazabilidad (para que quede constancia de que se comprobó), pero no puede rebajar ni la fuerza de otros tramos ni la Confidence resultante.

---

## Cierre

Los ocho conceptos pedidos no son ocho piezas independientes de este documento — son, todos, consecuencias de una sola decisión de diseño: que un tramo de Evidence tenga siempre origen (sección 2) y fuerza (sección 3) como atributos obligatorios e inseparables del valor que representa. La trazabilidad (sección 4), la normativa (sección 5), la geometría (sección 6) y el cálculo (sección 7) son, cada una, una forma concreta que el origen puede tomar; la cadena causal (sección 8) es lo que pasa cuando varios tramos se encadenan; la confianza derivada (sección 9) es, literalmente, la función que resulta de haber calificado bien cada tramo por separado. La tabla de techos de la sección 3 es, como todas las tablas cerradas de esta serie, responsabilidad exclusiva del Curador de Conocimiento — el único punto donde este documento podría degradarse con el tiempo es que alguien, bajo presión, calificara un tramo "a ojo" en vez de con la tabla. Contra eso, igual que en los cuatro documentos anteriores, no hay una defensa técnica — solo la disciplina de no hacerlo.
