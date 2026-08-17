# EXPLANATION_ENGINE.md

**Propósito:** diseñar cómo Evidence (`EVIDENCE_MODEL.md`) se convierte en texto que un Arquitecto puede leer y entender sin reconstruir el razonamiento por su cuenta — la especificación completa de la entidad 19 de `REASONING_ENGINE_SPEC.md` (Explanation), que hasta ahora solo estaba esbozada. El objetivo explícito del encargo, "que cualquier arquitecto pueda entender exactamente por qué el motor llega a una conclusión", y su restricción explícita, "nunca inventar razonamientos", son la misma exigencia vista desde dos lados — y ambas se resuelven con la misma decisión de diseño que atraviesa todo este documento (sección 0). Sin código, como el resto de la serie.

**Referencias obligatorias, asumidas como ya decididas:**
- `REASONING_ENGINE_SPEC.md` — entidad 19 (Explanation): deriva de Evidence, nunca afirma algo que su Evidence no contenga, marca los tramos de Nivel 3-4 explícitamente. Este documento no la redefine, la completa.
- `EVIDENCE_MODEL.md` — la estructura de tramo (origen, fuerza, normativa, puntero geométrico, traza de cálculo, sección 1), la tabla de techos que califica cada tramo (§3), y la Confidence como mínimo simple (§9). Explanation no vuelve a decidir nada de esto — lo narra.
- `CHAIN_REASONING.md` — §10, la cadena causal se muestra paso a paso, nunca colapsada; regla ya convertida en estructura de Evidence (`EVIDENCE_MODEL.md` §8) y aquí convertida, además, en regla de redacción.
- `INFERENCE_ENGINE.md` — los cuatro ejes de clasificación de Inference (directa/compuesta, positiva/negativa, determinística/probabilística, bloqueante/no bloqueante), que determinan qué patrón narrativo aplica a cada conclusión (sección 1).
- `DECISION_ENGINE.md` — §2 (los 5 tipos de Conflict, en particular el Tipo 5, discrepancia legítima de criterio) y §12 (protocolo de información insuficiente, recomendación condicional en vez de default silencioso) — ambos se narran explícitamente en las secciones 7 y 8.
- Grounding real: `analyzer/ai_analyst.py` ya genera hoy una narrativa ("análisis experto IA") con una llamada a Claude sobre los resultados de `evaluator.py`. Es el precedente real más cercano a lo que Explanation tendrá que hacer — y también el ejemplo más concreto del riesgo que la sección 0 existe para prevenir: una narrativa generada con un modelo de lenguaje, sin la separación estructural que este documento exige, puede fluir con naturalidad hacia afirmar algo que los datos no sostienen. Este documento no rediseña `ai_analyst.py` (fuera de alcance, shadow-mode per `PRD-001-Core-Reasoning-Engine.md`) — establece la regla que cualquier implementación futura de Explanation, use o no un modelo de lenguaje para la redacción, tiene que respetar.

**Actor nuevo, añadido al glosario ya establecido:**
- **Narrador** — el proceso único y compartido entre los 14 dominios que convierte una Evidence en texto, usando exclusivamente los patrones narrativos cerrados de este documento (sección 1) y el diccionario canónico de términos (sección 2) — nunca prosa libre por dominio. Mismo patrón de gobernanza que el Compositor de Hechos, el Intérprete de Constraints, el Motor de Síntesis de Hallazgos y el Verificador de Coherencia de los documentos anteriores.

---

## 0. El principio que resuelve las dos exigencias del encargo a la vez

"Que cualquier arquitecto entienda exactamente por qué" y "nunca inventar razonamientos" no son dos requisitos distintos que este documento tenga que equilibrar — son la misma exigencia. Un texto que explica de más (razonamiento no presente en la Evidence) y un texto que explica de menos (omite un tramo relevante) fallan por el mismo motivo: dejan de ser un reflejo fiel de lo que el motor realmente hizo.

La decisión de diseño que hace esto posible es una separación estricta de responsabilidades:

- **Qué se dice** — el contenido, la selección de qué tramos de Evidence aparecen y en qué orden — es **enteramente determinista**, decidido por los patrones narrativos cerrados de la sección 1 aplicados mecánicamente sobre la estructura ya fijada de Evidence. Cero libertad aquí, cero margen para "redondear" un dato o añadir un matiz que suene razonable pero que ningún tramo sostenga.
- **Cómo se dice** — la redacción en español fluido, con el registro y vocabulario de la sección 2 — puede apoyarse en generación de lenguaje natural (incluido un modelo como el que ya usa `ai_analyst.py`), pero **su única función es traducir contenido ya decidido a prosa, nunca decidir qué contenido incluir**. El Narrador nunca tiene la opción de añadir una frase que no corresponda a un tramo de Evidence existente, por bien que suene o por útil que parezca — igual que ningún dominio puede inventar un Constraint sin fuente citable (`CONSTRAINT_MODEL.md` §8), ningún Narrador puede inventar una frase sin un tramo que la respalde.

Esta separación es la respuesta estructural a "nunca inventar razonamientos": no depende de que la redacción sea "cuidadosa" — depende de que la redacción físicamente no tenga acceso a decidir contenido, solo a fraseartlo.

---

## 1. Estructura

Una Explanation nunca es texto libre — es la instancia de uno de estos **cinco bloques narrativos cerrados**, en orden fijo, con cada bloque presente u omitido según lo que la Evidence realmente contenga (nunca relleno cuando no hay nada que decir en ese bloque):

| Bloque | Contenido | Presente cuando |
|---|---|---|
| **1. Afirmación** | La conclusión, en una frase, en lenguaje llano — qué se cumple, qué no, qué se recomienda | Siempre |
| **2. Fundamento** | Qué Facts y Constraints la sostienen, con su normativa asociada citada inline (sección 6) | Siempre que la Evidence tenga al menos un tramo de tipo Fact/Constraint |
| **3. Cadena** | Cada salto causal, en orden, si la conclusión es compuesta (`INFERENCE_ENGINE.md` §2.1) | Solo si la Evidence incluye tramos ChainEffect o Inference (sección 5 de este documento y `EVIDENCE_MODEL.md` §8) |
| **4. Confianza** | Por qué la Confidence no es Alta, si no lo es — nunca aparece si la Confidence es Alta y no hace falta justificar nada más allá del Fundamento | Solo si Confidence es Media, Baja, o no evaluable (sección 8) |
| **5. Excepciones y alternativas** | Si se evaluó una Excepción, aplicara o no; si hay una alternativa condicional cuando falta un dato (`DECISION_ENGINE.md` §12) | Solo si la Evidence incluye un tramo de tipo Excepción evaluada, o si hay un Unknown de alto apalancamiento sin resolver |

Cada bloque, atributo mínimo de Explanation:

| Atributo | Descripción |
|---|---|
| **Evidence de la que deriva** | Referencia obligatoria, nunca texto sin Evidence asociada |
| **nivel** | Uno de los tres de la sección 4 |
| **texto narrativo** | El resultado, compuesto de los bloques 1-5 aplicables |
| **mapa de trazabilidad** | Por cada afirmación del texto, el tramo de Evidence exacto que la sostiene (sección 5) |
| **versión de ProjectState** | En la que se generó — igual que Evidence, es reproducible pero no se edita; si la Evidence cambia, se regenera, no se corrige a mano |

---

## 2. Lenguaje

Dos reglas de registro, no negociables, y un mecanismo de vocabulario compartido:

**Registro proporcional a la fuerza del tramo que se está narrando.** El vocabulario de certeza está atado, palabra por palabra, a la fuerza calculada en `EVIDENCE_MODEL.md` §3 — nunca a discreción del Narrador ni del modelo de lenguaje que redacte:

| Fuerza del tramo | Vocabulario permitido | Vocabulario prohibido |
|---|---|---|
| **Alta** | "incumple", "se confirma", "la superficie es de..." | — |
| **Media** | "según el criterio profesional de...", "es probable que", "salvo mejor dato disponible" | "sin duda", "se confirma", cualquier verbo que afirme sin matiz |
| **Baja** | "bajo el supuesto de que...", "de forma provisional, hasta confirmar..." | cualquier frase que no deje explícito que se trata de una hipótesis |
| **No evaluable** | "no se puede determinar con los datos actuales", seguido de qué dato falta | cualquier valor concreto — si no es evaluable, no se afirma un valor, se explica por qué no |

**Vocabulario canónico único.** El mismo concepto se nombra siempre igual, en cualquier Explanation de cualquier dominio — un diccionario cerrado, mantenido por el Curador de Conocimiento junto con el resto de catálogos ya gobernados en la serie (tipos de Fact namespaced, `FACT_MODEL.md` §12.2; catálogo de patrones, `CONSTRAINT_MODEL.md` §14). Sin este diccionario, 14 dominios describiendo el mismo Fact ("superficie útil", "área habitable neta", "superficie interior") con sinónimos distintos rompería, en la práctica, la promesa de que cualquier arquitecto entienda el texto sin tener que aprender el vocabulario particular de cada dominio.

---

## 3. Profundidad

Profundidad es un eje continuo, no un valor cerrado: cuántos tramos de la Evidence se expanden en el texto final. En un extremo, solo el bloque 1 (Afirmación); en el otro, los cinco bloques completos con cada salto de la Cadena narrado por separado. No es una propiedad que se declare directamente — es una consecuencia de qué **nivel** (sección 4) se pide, y existe como eje separado de nivel porque dos Explanations del mismo nivel pueden necesitar distinta profundidad según la Evidence real: una conclusión directa (`INFERENCE_ENGINE.md` §2.1) a profundidad "completa" no es más larga que a profundidad "estándar", porque no hay cadena que expandir — mientras que una conclusión compuesta de seis saltos sí lo es. La profundidad se adapta a lo que la Evidence contiene, nunca se infla para parecer más completa de lo que la conclusión requiere.

---

## 4. Niveles

Tres niveles cerrados, cada uno una combinación fija de profundidad y registro — nunca un cuarto nivel ad hoc por dominio:

| Nivel | Profundidad | Uso previsto |
|---|---|---|
| **Resumen** | Solo bloque 1, una frase | Listas y paneles con muchos Hallazgos (`OBSERVATION_MODEL.md`) a la vez |
| **Estándar** | Bloques 1, 2, y 4 si aplica — sin expandir la Cadena completa, solo su primer y último salto | Lectura junto a un Hallazgo concreto — el caso por defecto |
| **Completa** | Los cinco bloques, Cadena expandida tramo a tramo | Auditoría, revisión de un hallazgo bloqueante, o cualquier caso en que el Arquitecto pida "por qué" explícitamente |

Pueden coexistir varias Explanations de niveles distintos sobre la misma Evidence sin inconsistencia — ya lo fija `REASONING_ENGINE_SPEC.md` entidad 19 — porque las tres derivan, mecánicamente, de la misma fuente y del mismo conjunto cerrado de bloques; ninguna añade información que las otras no tengan disponible, solo varía cuánta se expone.

---

## 5. Trazabilidad

Cada afirmación del texto final lleva, sin excepción, un enlace implícito a un tramo concreto de Evidence — nunca una frase "suelta". Esto no es una aspiración de calidad, es una condición de generación: el Narrador construye el texto **recorriendo la Evidence tramo a tramo** (mismo recorrido, mismo orden, que `EVIDENCE_MODEL.md` §8 ya fija para la cadena causal) y produciendo una frase por tramo relevante — nunca al revés, nunca redactando primero y buscando después qué tramo la justifica. Si un tramo no tiene nada que aportar al nivel solicitado (sección 4), simplemente no genera frase — no se resume ni se aproxima, se omite.

El mapa de trazabilidad (atributo de la sección 1) es lo que permite, en la práctica, que un Arquitecto pida "muéstrame de dónde sale esto" sobre cualquier frase concreta y llegue, en última instancia, al puntero geométrico o al puntero de origen final (`EVIDENCE_MODEL.md` §4, `FACT_MODEL.md` §9) — la promesa de "entender exactamente por qué" del encargo se cumple aquí, en el sentido más literal: cada frase es clicable hasta el dato real, no una paráfrasis de él.

---

## 6. Referencias normativas

Toda cita normativa aparece **inline, junto a la afirmación que sostiene**, nunca en una lista de fuentes separada al final del texto — un formato de "fuentes" desconectado de las afirmaciones concretas invita a leer el texto como una opinión con bibliografía de apoyo, cuando en realidad cada norma sostiene una frase específica y solo esa. El formato hereda, sin reinterpretarla, la estructura ya fijada en `CONSTRAINT_MODEL.md` §8: fuente exacta, ámbito territorial cuando sea relevante (sección 5 de `EVIDENCE_MODEL.md` — normativa autonómica junto a la estatal si ambas participaron), y si el tramo es Nivel 3 (buena práctica), la cita "criterio profesional: [documento/guía]" aparece con el mismo tratamiento visual que una cita legal — nunca oculta ni en letra más pequeña, precisamente porque distinguir Nivel 2 de Nivel 3 es información que el Arquitecto necesita, no un detalle a minimizar.

---

## 7. Explicación de conflictos

Cuando la conclusión que se narra es, o incluye, un Conflict (`REASONING_ENGINE_SPEC.md` entidad 15), la Explanation sigue una regla adicional, no un bloque nuevo: **se narran los dos lados por separado, con el mismo nivel de detalle cada uno**, nunca un lado como "la conclusión" y el otro como "una objeción menor". El texto cita explícitamente qué criterio de la jerarquía de prioridad (`DECISION_ENGINE.md` §3) se está aplicando, si se aplica alguno — y si el Conflict es de Tipo 5 (discrepancia legítima de criterio, dos posiciones de Nivel 4 igualmente válidas), el texto **lo dice así, explícitamente**, en vez de fingir que el sistema "no sabe" o de elegir un lado sin decir que lo está haciendo. Un Conflict Tipo 5 expuesto con claridad no es una limitación del sistema que haya que disculpar — es, literalmente, el resultado correcto cuando dos criterios expertos discrepan de verdad (`DECISION_ENGINE.md` §2), y la Explanation tiene que transmitir esa distinción, no ocultarla detrás de un tono de incertidumbre genérica que confundiría "discrepancia legítima" con "dato insuficiente" (ver sección 8, que sí es el caso correcto para esa incertidumbre).

Si el Conflict ya tiene una Decision que lo cierra (`REASONING_ENGINE_SPEC.md` entidad 17), la Explanation lo narra como tal — qué Alternative se eligió, si coincidió o no con la Recommendation del sistema, y la justificación del Arquitecto si la dio, exactamente con la misma fidelidad de "nunca inventar" que rige el resto del documento: si el Arquitecto no dio justificación, el texto dice "elección sin justificación registrada" (ya invariante en `REASONING_ENGINE_SPEC.md` entidad 17), nunca se inventa una razón plausible en su lugar.

---

## 8. Explicación de incertidumbre

Dos casos distintos, que la Explanation no puede tratar igual porque el Arquitecto necesita hacer cosas distintas con cada uno:

**Confidence Media o Baja** (bloque 4, sección 1) — el texto narra **qué tramo concreto** de la Evidence causó que la Confidence no fuera Alta (una Assumption, un tramo de Nivel 3-4, un dato promovido desde Assumption — `EVIDENCE_MODEL.md` §3), nunca un genérico "confianza media" sin más. Coherente con `INFERENCE_ENGINE.md` §2.3: el número interno que en algún momento pudo haber informado esa cubeta **nunca aparece en el texto** — la explicación de por qué la confianza no es Alta se da siempre señalando el tramo débil, nunca citando un porcentaje.

**Unknown sin resolver** — no es "confianza Baja", es una categoría distinta y así se narra: la conclusión no está disponible, y el texto dice explícitamente qué dato falta y, cuando el apalancamiento de decisión lo justifica (`REASONING_ENGINE_SPEC.md` entidad 6), ofrece la recomendación condicional que ya exige `DECISION_ENGINE.md` §12 ("si la superficie declarada es X, se cumple; si es Y, no") en vez de silenciar la pregunta o rellenarla con un valor por defecto sin decirlo — el mismo protocolo de información insuficiente, ahora expresado como regla de redacción, no solo de comportamiento del motor.

Ninguno de los dos casos se disculpa ni se minimiza con un tono vago ("podría haber alguna incertidumbre") — se nombra con precisión, porque un Arquitecto que sabe exactamente qué falta puede ir a buscarlo; uno al que se le dice "hay algo de incertidumbre" sin más, no.

---

## Cierre

El riesgo real de este documento no es distinto del de los cinco anteriores, y merece nombrarse una vez más porque aquí es donde más fácilmente se materializa: en el momento en que la redacción se apoye en generación de lenguaje natural — como ya hace `ai_analyst.py` hoy — la línea entre "fraseó bien un contenido ya decidido" y "decidió, de hecho, qué decir" es fácil de cruzar sin que nadie lo note, porque el texto resultante suena igual de fluido en ambos casos. La separación de la sección 0 (contenido determinista, fraseo libre) es la única defensa, y depende de que se implemente como una restricción real sobre lo que el Narrador puede tocar — nunca como una instrucción de estilo ("no inventes") dada a un generador con acceso de todas formas a decidir el contenido. Es la misma disciplina que ya sostiene los cinco documentos anteriores, aplicada aquí al punto exacto donde el motor de razonamiento deja de hablarle a otro proceso y empieza a hablarle a una persona.
