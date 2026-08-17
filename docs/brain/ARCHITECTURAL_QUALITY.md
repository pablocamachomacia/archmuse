# ARCHITECTURAL_QUALITY.md

**Propósito:** profundizar en el Dominio 9 de `BRAIN_ARCHITECTURE.md` — "Calidad Espacial (habitabilidad subjetiva)", ya esbozado en `ARCHITECTURAL_KNOWLEDGE_MAP.md` con sus diez subsecciones estándar — con el contenido real que ese esbozo, por diseño, no desarrollaba: qué hace que un proyecto sea excelente, cómo se aproxima ese juicio con reglas, heurísticas y razonamiento sin fingir una precisión que no existe, y cómo se expresa la incertidumbre en el único dominio de los catorce donde el gusto y la intención de diseño son, legítimamente, parte del contenido. **No se habla de normativa** — no porque no exista ninguna referencia indirecta (`ARCHITECTURAL_KNOWLEDGE_MAP.md` §3 ya señala que apenas la hay), sino porque este documento existe precisamente para tratar el territorio que la normativa no cubre y no puede cubrir. Sin código, como el resto de la serie.

**Referencias obligatorias, asumidas como ya decididas:**
- `ARCHITECTURAL_KNOWLEDGE_MAP.md` — Dominio 9 completo (líneas 331-369), en particular su clasificación de 4 niveles ya fijada: la práctica totalidad del dominio es Nivel 4 (criterio arquitectónico), y su invariante ya escrita — "el sistema debe modelar esto como rango de valoración razonado, no como veredicto único". Este documento no la contradice, la desarrolla.
- `REASONING_ENGINE_SPEC.md` — entidad 12 (Recommendation, "incorpora juicio, no es determinística") y entidad 13 (Preference, "una elección declarada... no derivada de ningún análisis técnico") — ambas se reutilizan aquí con un papel central, no periférico (secciones 2 y 4).
- `CONSTRAINT_MODEL.md` — §3.1, el catálogo cerrado de 5 patrones de evaluación. Este documento traza, con precisión, dónde termina lo que ese catálogo puede representar honestamente y dónde empieza lo que no debe forzarse en él (sección 2).
- `EVIDENCE_MODEL.md` — §3, la tabla de techos (Nivel 4 → techo de fuerza Baja, siempre). Este documento no pide una excepción a esa regla para este dominio — la reafirma como la propiedad que hace que este dominio sea honesto (sección 5).
- `CONFLICT_ENGINE.md` — §1, el Tipo 5 (discrepancia legítima de criterio) — el tipo de conflicto que este dominio produce con más frecuencia que cualquier otro.
- Grounding real: `analyzer/spatial_quality.py`, las 5 heurísticas de calidad de diseño ya implementadas (proporción "tubo", profundidad de luz, escala humana, espacio muerto, jerarquía espacial) — el ejemplo concreto de lo que sí se puede aproximar con una regla, usado en la sección 2 para anclar la frontera con lo que no se puede.

---

## 1. ¿Qué hace que un proyecto sea excelente?

La respuesta honesta empieza por reconocer un límite real, no por esquivarlo: Christopher Alexander, en *The Timeless Way of Building*, dedicó un libro entero a nombrar lo que llamó "la cualidad sin nombre" — esa propiedad que un edificio, una calle o una habitación pueden tener o no tener, que cualquier persona reconoce con claridad al estar dentro, y que ningún checklist logra capturar del todo sin perder algo esencial en el intento. Este dominio no existe para resolver ese problema — existe para razonar con la máxima honestidad posible dentro de él, sin fingir que una lista de comprobaciones lo sustituye.

Dicho esto, la excelencia arquitectónica no es un misterio total ni un asunto de gusto puro sin ninguna estructura — hay dimensiones reconocibles, presentes en prácticamente cualquier discusión seria entre arquitectos sobre por qué un proyecto funciona y otro no, aunque ninguna de ellas, por sí sola ni todas juntas, produzca una fórmula:

- **Coherencia de intención (el "parti").** Un proyecto excelente tiene una idea organizadora reconocible que explica sus decisiones principales — no es la suma de soluciones correctas e independientes a cada requisito, es un conjunto de decisiones que se sostienen mutuamente porque responden a la misma intención. Un proyecto puede cumplir todo y no tener ninguna idea que lo sostenga; ese proyecto no es excelente, es correcto.
- **Respuesta al lugar.** Orientación, topografía, vistas, clima, contexto urbano inmediato — un proyecto excelente responde a las condiciones reales de su emplazamiento en vez de imponer una solución que sería idéntica en cualquier otro sitio.
- **Secuencia y experiencia espacial en el tiempo.** Lo que Le Corbusier llamó la *promenade architecturale* — cómo se recorre el proyecto, qué se revela y en qué orden, cómo cambia la percepción de escala y luz de una pieza a la siguiente. Un plano puede ser eficiente en superficie y, aun así, no ofrecer ninguna experiencia de recorrido — la eficiencia y la experiencia no son la misma dimensión.
- **Jerarquía servido/servidor.** La distinción que Louis Kahn hizo explícita: piezas principales y piezas que las sirven, y si esa jerarquía es legible tanto en el uso como en la propia organización espacial, o si se ha diluido.
- **Luz y vista como herramienta compositiva, no solo como cumplimiento.** Cumplir un mínimo de iluminación natural (Dominio 4) es una condición necesaria; usar la luz para dar carácter a un espacio concreto —una luz cenital sobre la pieza principal, una vista enmarcada deliberadamente— es una decisión de calidad que el cumplimiento normativo no exige ni mide.
- **Proporción y escala humana**, más allá del proxy geométrico que la sección 2 puede calcular — la sensación real de estar en un espacio, no solo la relación numérica entre sus dimensiones.
- **Economía de medios resuelta con elegancia.** Con frecuencia, la solución más admirada entre profesionales no es la que tiene más recursos, es la que logra más con menos — una vivienda de presupuesto ajustado bien resuelta puede ser, legítimamente, más excelente que una de gran presupuesto mal organizada.

Ninguna de estas siete dimensiones es una casilla que se marca. Son los ejes a lo largo de los cuales un arquitecto experto razona cuando emite un juicio de calidad — y es precisamente esa naturaleza de "eje de razonamiento" en vez de "criterio de verificación" lo que la sección 2 tiene que traducir con cuidado al resto del modelo, sin perder la distinción por el camino.

---

## 2. Tres niveles de aproximación: reglas, heurísticas y razonamiento

No las siete dimensiones de la sección 1 se aproximan igual — cada una cae, según el caso concreto, en uno de tres niveles bien distintos, y confundir uno con otro es el riesgo central de todo este documento (sección 6).

### Nivel A — Reglas (proxies geométricos calculables)

Un número reducido de aspectos de la calidad espacial admiten un proxy geométrico razonable: relación de aspecto de una pieza, profundidad respecto al hueco de luz principal, superficie/altura dentro de un rango de confort. Se expresan con el patrón UMBRAL_SIMPLE o AGREGACION_AMBITO ya cerrado en `CONSTRAINT_MODEL.md` §3.1, exactamente igual que cualquier otra Constraint del sistema — la única diferencia es su normativa asociada (`CONSTRAINT_MODEL.md` §8), que aquí no cita un artículo, cita "criterio profesional" con la fuente concreta (un tratado, una guía de diseño reconocida) de la que sale el rango. Las 5 heurísticas ya implementadas en `analyzer/spatial_quality.py` — proporción "tubo", profundidad de luz, escala humana, espacio muerto, jerarquía espacial — son, exactamente, este nivel: proxies calculables, catalogados, con su rango declarado, que producen una Inference con fuerza Nivel 3 (`EVIDENCE_MODEL.md` §3), nunca Nivel 1, por bien calibrado que esté el proxy.

### Nivel B — Heurísticas comparativas (razonamiento sobre relaciones, no sobre umbrales)

Un segundo grupo no se reduce a un único número contra un umbral, pero sí admite una comparación estructurada entre elementos del propio proyecto: ¿la pieza principal es, efectivamente, mayor y mejor orientada que las piezas servidoras? ¿la secuencia de acceso pasa primero por zonas públicas y solo después por privadas, o al revés? Esto no es un patrón UMBRAL_SIMPLE — es más cercano a COMBINACION_LOGICA (`CONSTRAINT_MODEL.md` §3.1) aplicado a relaciones entre piezas, no a valores absolutos. Sigue siendo Nivel 3: reconocible, enseñable, compartido entre profesionales, pero ya empieza a depender del programa concreto de cada proyecto en vez de un rango universal.

### Nivel C — Criterio arquitectónico propiamente dicho (irreducible)

El resto — coherencia de intención, respuesta al lugar, calidad de la experiencia espacial en el tiempo, si una solución de economía de medios resulta "elegante" — **no se debe forzar en ningún patrón del catálogo cerrado de `CONSTRAINT_MODEL.md` §3.1**, por sofisticado que parezca el intento. No hay un comparador, ni una combinación de comparadores, que capture honestamente si un proyecto "tiene una idea" o no. Este nivel no produce un Problem ni una Inference determinística — produce, cuando produce algo, una **Recommendation** (`REASONING_ENGINE_SPEC.md` entidad 12) construida por el Motor de Decisión a partir de una comparación razonada, nunca de una fórmula, o no produce nada automatizado en absoluto y queda como uno de los "casos sin respuesta correcta" que `ARCHITECTURAL_KNOWLEDGE_MAP.md` §8 ya nombra para este dominio.

La frontera entre el Nivel B y el Nivel C no siempre es cómoda, y es, precisamente por eso, la que hay que vigilar con más disciplina — se retoma en la sección 6.

---

## 3. Espejo, no juez

Para el Nivel C, el papel del sistema cambia de naturaleza, no solo de confianza. En los Niveles A y B, el sistema **verifica** — produce una conclusión que puede ser correcta o incorrecta respecto a un criterio declarado. En el Nivel C, la posición correcta del sistema es **describir**, no verificar: mostrar al Arquitecto los hechos relevantes (la jerarquía espacial real construida, la secuencia de acceso tal como resulta de la geometría, la relación entre pieza principal y servidoras) organizados de forma que el propio Arquitecto pueda emitir el juicio que solo un criterio experto puede emitir — nunca sustituyendo ese juicio por un veredicto del sistema disfrazado de observación neutral.

Esta distinción —espejo, no juez— es la aplicación, a su forma más extrema, del mismo principio que ya sostiene `EXPLANATION_ENGINE.md` §0 (nunca inventar razonamiento) y `EVIDENCE_MODEL.md` (nunca afirmar más de lo que la Evidence sostiene): en el Nivel C, la Evidence disponible casi nunca sostiene un veredicto, así que el sistema honesto no lo produce. Lo que sí puede producir con legitimidad es una descripción bien organizada de la situación — que es, en sí misma, valiosa para un arquitecto que revisa su propio proyecto con ojos frescos, sin necesidad de que el sistema le diga si está bien o mal.

---

## 4. Intención de diseño declarada

Hay una forma de hacer el Nivel C más tratable sin falsear su naturaleza: evaluar una decisión de diseño **contra la intención que el propio Arquitecto declaró**, en vez de contra un ideal externo de "buena arquitectura" sin más. "Dado que has dicho que buscabas una planta abierta y fluida, este tabique introduce una interrupción que va en contra de esa intención" es una afirmación mucho más defendible que "esta partición es mala arquitectura" — la primera compara el proyecto consigo mismo; la segunda compara el proyecto contra un canon que nadie ha declarado y que el sistema no tiene autoridad para imponer.

Esto no exige ninguna entidad nueva — una intención de diseño declarada es, estructuralmente, una **Preference** (`REASONING_ENGINE_SPEC.md` entidad 13: "una elección declarada... no derivada de ningún análisis técnico"), con un ámbito temporal que en este caso suele ser "todo el proyecto" en vez de "una decisión puntual". Declarar "quiero una planta fluida, sin distinción rígida entre estancias" al principio de un proyecto es exactamente el mismo tipo de afirmación, en la misma entidad, que preferir la luz natural sobre la eficiencia energética en un conflicto puntual (`DECISION_ENGINE.md` §9) — solo que aquí actúa como **criterio de coherencia interna** para el Nivel C de este dominio, no como desempate de un Conflict.

Cuando no hay intención declarada, el Nivel C se vuelve todavía más conservador: sin una vara de medir propia del proyecto, el sistema tiene aún menos base para evaluar y debe inclinarse con más fuerza hacia la sección 3 (describir, no juzgar) — nunca compensar la ausencia de intención declarada suponiendo una por defecto. Sería, otra vez, la misma familia de fallo que `UNCERTAINTY_MODEL.md` §0 ya nombra para Unknown, aplicada aquí a la intención de diseño en vez de a un dato geométrico: la ausencia de una intención declarada no autoriza al sistema a inventarse una razonable en su lugar.

---

## 5. Cómo se expresa la incertidumbre

Tres mecanismos ya existentes en la serie, ninguno inventado para este documento, que juntos son lo que hace posible que este dominio participe del motor sin comprometer su honestidad:

- **El techo de fuerza Nivel 4 → Baja es estructural, no una limitación temporal del sistema** (`EVIDENCE_MODEL.md` §3). Ningún refinamiento futuro de las heurísticas de este dominio debería aspirar a que un juicio de Nivel C alcance Confidence Alta — si algún día un dominio de este tipo la alcanzara, sería la señal de que, en realidad, se había encontrado una regla objetiva escondida (y entonces pertenecería al Nivel A), no de que el criterio arquitectónico se hubiera vuelto más preciso. La incertidumbre de este dominio no se reduce con mejor tecnología, se reduce dejando de ser Nivel 4.
- **Dos juicios de Nivel 4 en tensión, aunque provengan del mismo dominio (dos heurísticas de calidad distintas que apuntan en direcciones opuestas para el mismo espacio) o de dominios distintos, se exponen como Conflict Tipo 5** (`CONFLICT_ENGINE.md` §1) — discrepancia legítima de criterio, nunca resuelta automáticamente, nunca promediada. Es, con diferencia, el tipo de Conflict que este dominio genera con más frecuencia de los catorce, precisamente porque es el único cuyo contenido es, casi en su totalidad, Nivel 4.
- **El registro narrativo hedgeado ya fijado en `EXPLANATION_ENGINE.md` §2** ("según el criterio profesional de...", "es probable que...") es el único registro permitido para cualquier afirmación de este dominio que no sea puramente descriptiva (sección 3) — nunca el vocabulario de certeza reservado a fuerza Alta, ni siquiera cuando varias heurísticas de Nivel 3 coinciden en la misma dirección, porque coincidencia entre heurísticas de Nivel 3 sigue siendo, en conjunto, Nivel 3 — no se convierte en Nivel 1 por acumulación.

---

## 6. Este dominio frente a los otros trece

`ARCHITECTURAL_KNOWLEDGE_MAP.md` §6 ya lo dejó dicho con precisión: este dominio "absorbe" más tensión que casi cualquier otro, porque la solución normativamente correcta de otro dominio casi siempre tiene un coste espacial, y este es el que lo hace visible. Con `CONFLICT_ENGINE.md` ya diseñado, esa tensión tiene ahora un mecanismo concreto: es, en la mayoría de los casos, un **Conflict Tipo 2** (normativa-vs-diseño, `CONFLICT_ENGINE.md` §1) — un Problem de otro dominio (Nivel 1-2) contra un Hallazgo de recomendación de calidad de este dominio (Nivel 3-4, `OBSERVATION_MODEL.md` §3). La jerarquía de prioridad (`CONFLICT_ENGINE.md` §2) casi siempre falla a favor del Problem normativo en el primer criterio (nivel de bloqueo) — y eso es correcto, no una derrota de este dominio: su función no es ganar esos conflictos, es **asegurarse de que el coste en calidad quede registrado y visible**, incluso cuando la norma, con razón, se impone.

---

## Cierre

El riesgo real de este documento no es distinto, en su forma, del que ya se ha nombrado en cada documento anterior de la serie — es la misma tentación de fondo, aplicada aquí a su versión más peligrosa porque es la más difícil de resistir: forzar un juicio de Nivel C dentro de un patrón del catálogo cerrado solo porque hacerlo produce un número, y un número siempre parece más útil que una descripción honesta de que no hay una única respuesta correcta. Cuantificar el gusto no lo hace menos subjetivo, solo lo hace parecer objetivo — que es exactamente el tipo de precisión fabricada que toda la serie, desde `TIPOLOGIA_BENCHMARKS` en adelante, existe para no repetir. Este dominio es, de los catorce, el que más falla si se le exige que hable como el Dominio 1 en vez de como lo que realmente es.
