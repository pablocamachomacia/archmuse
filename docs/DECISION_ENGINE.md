# DECISION_ENGINE.md

**Propósito:** los tres documentos anteriores definieron qué sabe ArchMuse (`BRAIN_ARCHITECTURE.md`, `ARCHITECTURAL_KNOWLEDGE_MAP.md`) y cómo se propagan las consecuencias de un cambio (`CHAIN_REASONING.md`). Ninguno de los tres decide nada — detectan, clasifican, explican. Este documento diseña la pieza que falta: **cómo elige ArchMuse entre varias alternativas cuando no hay una única respuesta correcta**, y cómo lo justifica de forma que un arquitecto pueda confiar en la elección sin tener que repetir el análisis por su cuenta.

El modelo de referencia no es un algoritmo de optimización. Es el comportamiento del mejor arquitecto sénior: alguien que, ante un conflicto, no ofrece "la solución" — ofrece un conjunto de opciones razonadas, dice con qué grado de certeza defiende cada una, distingue lo que sabe de lo que está asumiendo, y sabe exactamente en qué punto la decisión deja de ser suya y pasa a ser del cliente. Ese comportamiento, y no un optimizador, es lo que este documento intenta reproducir.

---

## 1. Cómo identifica que existe un conflicto entre objetivos

Un conflicto se identifica de dos formas distintas, no una sola:

**Reactiva** — al proponer o evaluar un cambio, el modelo de propagación de `CHAIN_REASONING.md` produce, en algún punto de la cadena, un hallazgo nuevo en un dominio distinto al que motivó el cambio. Esa aparición de un efecto no deseado en otro dominio **es**, por definición, la señal de conflicto: resolver A ha creado o agravado B.

**Proactiva** — sin que haya ningún cambio en curso, el estado actual del proyecto ya presenta dos conclusiones de dominio en tensión estructural conocida (los pares de la sección 5 de `CHAIN_REASONING.md`: accesibilidad vs. superficie, iluminación vs. térmica, etc.), cada una parcialmente resuelta pero ninguna de forma óptima. Un arquitecto sénior detecta esto sin necesidad de tocar nada — reconoce el patrón porque ya lo ha visto antes. El motor de decisión debe poder hacer lo mismo: escanear el estado actual contra el catálogo de tensiones conocidas, no esperar siempre a que un cambio lo dispare.

En ambos casos, la condición formal de conflicto es la misma: **existe conflicto cuando no hay ningún estado del proyecto que satisfaga simultáneamente, al mismo nivel de cumplimiento, todas las conclusiones de dominio implicadas** — mejorar una implica necesariamente empeorar otra.

---

## 2. Qué tipos de conflictos existen

No todos los conflictos son de la misma naturaleza, y tratarlos igual es un error. Se distinguen cinco tipos:

**Tipo 1 — Normativo vs. normativo.** Dos dominios normativos (Capas 1-4 de `BRAIN_ARCHITECTURE.md`) exigen cosas incompatibles en la misma decisión de diseño. Ejemplo: accesibilidad vs. evacuación cuando ambos itinerarios compiten por el mismo ancho disponible. Ambos lados son obligatorios — no hay lado "más legal" que el otro.

**Tipo 2 — Normativa vs. diseño/calidad.** Cumplir el mínimo exigido por la norma vs. lograr la mejor solución posible más allá del mínimo (Dominio 9). Ejemplo: una escalera que cumple la pendiente máxima permitida pero que un arquitecto sénior nunca proyectaría así por incomodidad real de uso.

**Tipo 3 — Objetivos de negocio/cliente vs. técnica.** Coste vs. calidad, eficiencia vs. presupuesto, superficie vendible vs. confort. Este tipo introduce un elemento que **no es un dominio del cerebro** definido en `BRAIN_ARCHITECTURE.md` — coste y presupuesto no tienen hoy ningún dominio de conocimiento propio en el sistema. Es una laguna real: el motor de decisión necesita poder razonar sobre restricciones de negocio sin tener, todavía, un dominio experto que las modele con el mismo rigor que accesibilidad o térmica. Hasta que exista, estas restricciones se tratan como **preferencias/restricciones externas declaradas** (ver sección 9), no como conclusiones de un dominio evaluado.

**Tipo 4 — Aprovechamiento vs. bienestar.** Accesibilidad vs. aprovechamiento de superficie, superficie vs. confort. Suele ser, en la práctica, una combinación de Tipo 1 y Tipo 3: parte normativa, parte objetivo económico del promotor.

**Tipo 5 — Discrepancia legítima de criterio.** Dos soluciones ambas de Nivel 4 (criterio arquitectónico puro, sin respaldo normativo en ninguna de las dos) entre las que dos arquitectos sénior distintos podrían discrepar sin que ninguno esté equivocado. Este tipo no se "resuelve" en el sentido de los anteriores — se expone, y la elección final es inherentemente subjetiva.

La clasificación importa porque determina qué puede hacer el motor con cada conflicto: los Tipo 1 se priorizan con la jerarquía normativa (sección 3); los Tipo 3 dependen de una preferencia declarada que el sistema no puede inventar por su cuenta; los Tipo 5 no tienen resolución automática posible, solo presentación honesta de las opciones.

---

## 3. Cómo prioriza esos conflictos

La priorización sigue cinco criterios aplicados en este orden, heredando y extendiendo la jerarquía ya definida en `BRAIN_ARCHITECTURE.md` (Parte 1.7):

1. **Nivel de bloqueo** — lo que impide la licencia, el visado o compromete la seguridad de personas siempre gana sobre lo que no lo hace. No es negociable en ningún caso, ni siquiera por preferencia expresa del cliente (ver sección 9).
2. **Nivel de impacto** — usando la escala de `CHAIN_REASONING.md` (Local → Planta → Vivienda → Edificio → Parcela → Urbanístico): en igualdad de nivel de bloqueo, el conflicto de mayor alcance se atiende primero.
3. **Reversibilidad** — cuánto cuesta deshacer la decisión más adelante si resulta equivocada. Una decisión geométrica en fase de anteproyecto es barata de revisar; la misma decisión una vez iniciada la obra no lo es. A igualdad de los dos criterios anteriores, se prioriza resolver primero lo que será más caro corregir después.
4. **Confianza del conocimiento en juego** — un hallazgo de Nivel 1-2 (hecho/normativa verificable) pesa más en la decisión que uno de Nivel 3-4 (heurística/criterio) del lado opuesto del conflicto, en igualdad de lo anterior.
5. **Preferencia explícita del cliente o del arquitecto** — el único criterio que solo entra a decidir **dentro** del espacio ya filtrado por los cuatro anteriores, nunca por encima de ellos.

Este orden no es arbitrario: reproduce exactamente cómo un arquitecto sénior explica sus propias decisiones cuando se le pregunta por qué priorizó una cosa sobre otra — primero lo que no se puede negociar, después lo que más pesa si sale mal, y solo al final el gusto de quien encarga el proyecto.

---

## 4. Cuándo existe una única solución objetiva

Existe una única solución objetiva cuando se cumplen dos condiciones a la vez: **(a)** todos los criterios implicados en el conflicto son de Nivel 1-2 (hecho objetivo o normativa verificable, sin margen de interpretación), y **(b)** la intersección de todas las restricciones aplicables se reduce a un único estado de diseño posible (o a una familia de estados que no difieren en ninguna dimensión evaluada por el sistema).

Esto ocurre con más frecuencia de lo que parece en problemas puramente dimensionales: si un pasillo necesita un ancho mínimo exacto y solo hay una forma geométrica de conseguirlo sin generar una nueva infracción en otro dominio, no hay "alternativas" que generar — hay una solución, y presentarla como si hubiera varias sería fingir una elección que no existe.

---

## 5. Cuándo existen varias soluciones igualmente válidas

Es el caso más frecuente en la práctica real, y ocurre cuando varios estados de diseño distintos satisfacen igualmente todas las restricciones bloqueantes, y la diferencia entre ellos vive únicamente en dimensiones de Nivel 3-4 (buenas prácticas o criterio arquitectónico) — el terreno donde, como ya se estableció en `ARCHITECTURAL_KNOWLEDGE_MAP.md` (Dominio 9) y en `CHAIN_REASONING.md` (Tipo 5 de conflicto), dos profesionales expertos pueden discrepar legítimamente sin que ninguno esté equivocado. También ocurre cuando lo que distingue a las alternativas es, simplemente, una preferencia todavía no declarada por el cliente (estética, presupuesto, prioridades de uso).

---

## 6. Cómo debe generar alternativas

La generación de alternativas sigue cinco principios:

1. **Atacar la causa raíz, no el síntoma.** Usando el modelo de propagación de `CHAIN_REASONING.md`, cada alternativa debe originarse en el hecho que causó el conflicto, no en un parche local sobre su consecuencia visible.
2. **Al menos una alternativa por lado del conflicto.** Si el conflicto enfrenta al Criterio A con el Criterio B, se genera como mínimo una alternativa que prioriza A, otra que prioriza B, y — si existe — una intermedia de compromiso parcial entre ambos.
3. **Nunca una única alternativa cuando el conflicto es del tipo de la sección 5.** Presentar solo una opción en un caso de "varias soluciones igualmente válidas" equivale a ocultar que había una elección real que hacer, y traslada al arquitecto una falsa sensación de que el sistema decidió por él sin que fuera cierto.
4. **Reutilizar patrones ya resueltos.** Si un conflicto del mismo tipo ya se presentó y se resolvió (y se registró, ver sección 12 del flujo final) en un proyecto anterior, esa resolución histórica es la primera fuente de alternativas a considerar, no un punto de partida en blanco cada vez.
5. **Cada alternativa debe ser re-evaluable por los mismos dominios que detectaron el conflicto original**, no aceptarse por "sentido común" sin pasar de nuevo por el motor de propagación — una alternativa no verificada no es una alternativa, es una suposición.

---

## 7. Cómo compara alternativas

Cada alternativa generada se evalúa según el mismo marco, nunca con criterios distintos entre sí (de lo contrario la comparación no sería honesta):

- **¿Resuelve la infracción bloqueante que motivó el conflicto?** — filtro binario de entrada; una alternativa que no lo resuelve se descarta antes de comparar nada más.
- **¿Qué hallazgos nuevos introduce, y de qué severidad?** — usando la misma jerarquía de la sección 3 (bloqueante / riesgo variable / recomendable / preferencial).
- **¿Con qué nivel de impacto?** — la escala Local → Urbanístico de `CHAIN_REASONING.md`.
- **¿Qué tan reversible es?** — si más adelante resulta ser la elección equivocada, ¿cuesta poco o mucho corregirla?
- **¿Se alinea con alguna preferencia ya declarada?** — se aplica solo como último criterio de desempate, nunca como criterio principal de comparación (ver sección 9).

El resultado de la comparación se presenta siempre como **tabla de alternativas con su trade-off explícito**, no como un ranking de una sola cifra — salvo en el caso poco frecuente de que una alternativa domine estrictamente a otra (resuelve al menos lo mismo, sin introducir ningún coste adicional), en cuyo caso sí es honesto decir que una es simplemente mejor que la otra.

---

## 8. Cómo explica por qué recomienda una y no otra

La explicación de una recomendación nunca es una frase — es una cadena verificable, siguiendo directamente los principios de justificación ya definidos en `CHAIN_REASONING.md` (sección 10), aplicados aquí a la comparación entre alternativas:

- Se muestra la tabla completa de alternativas evaluadas, no solo la elegida.
- Se cita explícitamente qué criterio de la sección 3 rompió el empate ("se recomienda la alternativa B porque, aunque ambas resuelven el conflicto de accesibilidad, la alternativa A introduce un hallazgo bloqueante nuevo en evacuación, mientras que B solo introduce una recomendación no bloqueante en calidad espacial").
- Si el desempate lo decidió una preferencia del cliente y no un criterio objetivo, **se dice explícitamente así** — nunca se disfraza una elección de preferencia como si fuera una conclusión técnica forzada por la norma.
- Se distingue, en cada tramo de la justificación, si se apoya en un hecho, una inferencia, una hipótesis o una recomendación (sección 11) — para que el arquitecto sepa exactamente cuánto puede confiar en cada parte del argumento.

---

## 9. Cómo incorpora las preferencias del arquitecto o del cliente sin romper la normativa

Las preferencias actúan **exclusivamente como criterio de desempate dentro del espacio de soluciones ya filtrado por lo bloqueante** — nunca por encima de él. Concretamente:

- Una preferencia puede reordenar cómo se resuelven empates dentro de las capas recomendable/preferencial (Nivel 3-4) — por ejemplo, un cliente que valora explícitamente la luz natural por encima de la eficiencia energética desplaza cómo el motor prioriza esa tensión concreta en adelante.
- Una preferencia **nunca** puede alterar una conclusión de Nivel 1-2 (hecho o normativa verificable). Si una preferencia declarada entra en conflicto directo con una restricción bloqueante, el sistema no la relaja silenciosamente — la rechaza explícitamente, explica por qué, y ofrece la alternativa factible más cercana a lo que el cliente pedía.
- Cada vez que se honra una preferencia a costa de sacrificar una recomendación no bloqueante, **el sistema lo dice de forma explícita** — para que sea una decisión informada del cliente/arquitecto, no una concesión silenciosa que después parezca un error del sistema.

Este es, en el fondo, el mismo principio que separa a un arquitecto profesional de un simple ejecutor de encargos: escucha y prioriza al cliente en todo lo que es elección legítima, pero no cede en lo que compromete su responsabilidad profesional — coherente con el Dominio 13 (Riesgo de Visado y Responsabilidad Profesional) de `BRAIN_ARCHITECTURE.md`.

---

## 10. Modelo de nivel de confianza para cada recomendación

El nivel de confianza de una recomendación **no debe expresarse como un porcentaje numérico preciso** — hacerlo transmitiría una falsa precisión que el sistema no tiene, exactamente el mismo error ya señalado y corregido en `PROJECT_AUDIT.md`/`TECH_REVIEW.md` respecto al percentil de mercado fabricado. En su lugar, se propone una escala cualitativa de tres niveles, cada uno definido por criterios explícitos, no por una cifra:

- **Confianza alta** — todos los pasos de la cadena que sostiene la recomendación son Nivel 1-2 (hechos y normativa verificable), sin hipótesis intermedias, y no dependen de datos ausentes.
- **Confianza media** — la cadena incluye al menos un tramo de Nivel 3 (buena práctica) o una hipótesis razonable (sección 11) usada para suplir un dato ausente, declarada como tal.
- **Confianza baja** — la recomendación depende sustancialmente de criterio de Nivel 4, de varias hipótesis encadenadas, o de datos que el sistema no posee y ha tenido que asumir.

La confianza de una recomendación es, siempre, **la del eslabón más débil de su cadena de justificación** (mismo principio ya fijado en `CHAIN_REASONING.md`, sección 10.3) — nunca un promedio que diluya un tramo débil entre varios fuertes.

---

## 11. Sistema para distinguir hechos, inferencias, hipótesis, recomendaciones y preferencias

Toda afirmación que produzca ArchMuse debe estar etiquetada, de forma visible, con exactamente una de estas cinco categorías — es el mecanismo de transparencia que sostiene todo lo demás en este documento:

- **Hecho** — dato medido u observado directamente del proyecto (una superficie, una posición, una orientación). No es discutible; si está mal, es un error de lectura del dato de entrada, no de razonamiento.
- **Inferencia** — conclusión derivada mecánicamente de uno o más hechos aplicando una regla normativa verificable o un cálculo determinista (Nivel 1-2). Es tan fiable como los hechos y la regla que la sostienen.
- **Hipótesis** — una suposición razonable adoptada en ausencia de un dato que el sistema no tiene (por ejemplo, asumir una composición constructiva estándar para estimar aislamiento acústico ante la falta de ese dato real, ver Dominio 7 de `ARCHITECTURAL_KNOWLEDGE_MAP.md`). Debe marcarse siempre como tal, de forma que nunca se confunda con un hecho.
- **Recomendación** — una propuesta de acción generada por el motor de decisión a partir de hechos, inferencias e hipótesis, siempre acompañada de su nivel de confianza (sección 10). Es accionable, nunca obligatoria.
- **Preferencia** — una elección declarada por el cliente o el arquitecto, no derivada de ningún análisis técnico. Puede influir en cómo se priorizan recomendaciones (sección 9), pero jamás en los hechos ni en las inferencias.

Un arquitecto experto nunca confunde estas cinco categorías al hablar de un proyecto — sabe distinguir "esto mide 3,20 m" (hecho) de "por tanto no cumple el mínimo de 3,50 m" (inferencia) de "asumiendo un muro de partición estándar" (hipótesis) de "recomendaría ensancharlo aquí" (recomendación) de "aunque el cliente prefiere mantenerlo así" (preferencia). Que ArchMuse mantenga esa misma distinción visible en todo momento es, probablemente, el requisito individual más importante de todo este documento para que un arquitecto profesional llegue a confiar en él.

---

## 12. Cómo debe actuar cuando no existe suficiente información para decidir

Nunca completando el vacío en silencio con un valor por defecto que pueda pasar por dato real — es, exactamente, el patrón que causó el bug más grave documentado en `TECH_REVIEW.md` (tipología y zona climática sustituidas silenciosamente por valores por defecto). El protocolo correcto:

1. **Declarar explícitamente qué dato falta** y qué decisión concreta no puede tomarse sin él.
2. **Si existe una hipótesis razonable para suplirlo** (sección 11), usarla, pero marcada sin ambigüedad como hipótesis, con el nivel de confianza correspondientemente rebajado (sección 10) — nunca disfrazada de hecho.
3. **Presentar la decisión como condicional cuando sea posible**: "si la composición del muro es X, la recomendación es A; si es Y, la recomendación es B" — en lugar de elegir una silenciosamente y ocultar que dependía de un dato no confirmado.
4. **Nunca fabricar un número para rellenar el hueco** — mismo principio ya fijado para el Dominio 14 (Benchmark de Mercado) en `ARCHITECTURAL_KNOWLEDGE_MAP.md`: ausencia de dato real significa ausencia de conclusión, no una conclusión aproximada presentada como firme.
5. **Priorizar qué falta de información merece preguntarse activamente** frente a qué puede asumirse con nota al pie sin más: un dato que cambiaría sustancialmente la recomendación final ("dato de alto impacto en la decisión") debe solicitarse de forma proactiva al arquitecto; un dato de bajo impacto puede asumirse razonablemente con una hipótesis declarada, sin interrumpir el flujo por algo que apenas altera el resultado.

---

## Flujo completo de decisión

Desde que aparece un problema hasta que el arquitecto acepta una solución, el recorrido completo integra los tres documentos anteriores y este:

1. **Detección** — un cambio, o el estado ya existente del proyecto, dispara un conflicto entre dos o más conclusiones de dominio, por vía reactiva o proactiva (sección 1).
2. **Clasificación** — se identifica el tipo de conflicto (sección 2) y su posición en la jerarquía de prioridad (sección 3).
3. **Comprobación de suficiencia de datos** — si en cualquier punto de este recorrido falta información necesaria, se activa el protocolo de la sección 12 antes de continuar; el flujo no avanza fingiendo tener datos que no tiene.
4. **Comprobación de unicidad** — se determina si existe una única solución objetiva (sección 4) o un espacio de varias soluciones válidas (sección 5).
5. **Generación de alternativas** — si no hay solución única, se generan varias siguiendo los cinco principios de la sección 6, cada una re-evaluada por el mismo motor de propagación de `CHAIN_REASONING.md` que detectó el conflicto original.
6. **Comparación** — las alternativas se comparan con el marco común de la sección 7 (bloqueo resuelto, hallazgos nuevos, nivel de impacto, reversibilidad, alineación con preferencia).
7. **Priorización y recomendación provisional** — se aplica la jerarquía de la sección 3, se asigna un nivel de confianza cualitativo (sección 10), y cada elemento del razonamiento queda etiquetado como hecho, inferencia, hipótesis o recomendación (sección 11).
8. **Presentación al arquitecto** — se muestra la cadena de causalidad completa (heredada del modelo de explicabilidad de `CHAIN_REASONING.md`), la tabla de alternativas con su trade-off, y la justificación explícita de la recomendación (sección 8).
9. **Incorporación de preferencia** — el arquitecto, o el cliente a través de él, puede introducir una preferencia, que el motor aplica únicamente dentro del espacio ya filtrado por lo bloqueante (sección 9), nunca por encima de él.
10. **Decisión** — el arquitecto acepta una alternativa, que puede o no coincidir con la recomendada por el sistema; el motor no fuerza ninguna elección dentro del espacio de soluciones válidas.
11. **Registro** — la decisión tomada y su justificación quedan registradas como conocimiento, especialmente si difiere de la recomendación del sistema — esta es la forma en la que el motor de decisión aprende con el tiempo, y la misma memoria institucional que alimenta al Dominio 12 y al Dominio 13 de `BRAIN_ARCHITECTURE.md`.
12. **Re-propagación** — la decisión aceptada se incorpora al proyecto como un nuevo cambio, que vuelve a atravesar el modelo de propagación de `CHAIN_REASONING.md`; si genera un conflicto de segundo orden, el flujo completo vuelve a empezar desde el paso 1.

Este ciclo — detectar, clasificar, comparar, explicar, decidir, registrar, propagar de nuevo — es, en esencia, la definición operativa de lo que significa que ArchMuse "razone como un arquitecto sénior" en lugar de simplemente "verificar reglas": no elige por el arquitecto, elige **con** él, y cada vez que lo hace, deja un rastro verificable de por qué.
