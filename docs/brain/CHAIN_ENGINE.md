# CHAIN_ENGINE.md

**Propósito:** rediseñar el mecanismo de propagación de `CHAIN_REASONING.md` con la profundidad operativa que ese documento, deliberadamente conceptual, no necesitaba tener — cómo se propaga un cambio en la práctica, en qué orden, cómo se agrupan miles de ellos, cómo se cancela trabajo que ya no hace falta, cómo se sabe que se ha terminado, cómo se detecta un conflicto mientras se propaga y no solo al final, y qué hace que todo esto siga siendo rápido con miles de cambios en juego. Sigue sin haber código — es el diseño del mecanismo, no su implementación — pero el nivel de detalle es deliberadamente mayor que en el resto de la serie, porque el encargo lo pide explícitamente.

**Qué no cambia de `CHAIN_REASONING.md`:** las 8 familias de cambio, las 3 clases de dependencia entre dominios (estructural/condicional/de referencia), los 6 niveles de impacto (Local→Urbanístico), el listado empírico de 20 efectos de cadena, y las reglas de confianza/explicabilidad (cadena completa, nunca colapsada; confianza = eslabón más débil) permanecen exactamente como están. Este documento no las redefine — diseña el motor que las ejecuta a la escala de miles de cambios.

**Referencias obligatorias, asumidas como ya decididas:**
- `CHAIN_REASONING.md` — el documento que este redisño profundiza en su totalidad.
- `REASONING_ENGINE_SPEC.md` — entidad 1 (ProjectState) y entidad 14 (ChainEffect), en particular su invariante ya fijada: "una cadena de ChainEffects que supere un número de saltos inusualmente alto sin alcanzar un punto fijo debe marcarse para revisión" — este documento la convierte en un mecanismo concreto (sección 6).
- `FACT_MODEL.md` — §11.4 (recálculo limitado por alcanzabilidad) y §8 (grafo de derivación de Facts), §5 (ingesta por lotes) y §11.3 (deduplicación por huella de contenido) — los cuatro se generalizan aquí a un único grafo de propagación (sección 1).
- `INFERENCE_ENGINE.md` — §3-4 (generación e invalidación de Inference por alcanzabilidad) y §6 (Verificador de Coherencia, la comprobación de fin de recorrido) — este documento especifica cómo se llega hasta ese punto, no lo sustituye.
- `CONFLICT_ENGINE.md` — §5, el protocolo de intervención de 7 pasos; en particular el paso 1 ("suspensión de composición corriente abajo"), que este documento convierte en un mecanismo que ocurre *durante* la propagación, no después de ella (sección 7).
- `PROJECT_MEMORY.md` — §2-3, la Sesión y la comprobación de efectos acumulativos tras cada Change — la unidad de agrupación de miles de cambios de la sección 4 se apoya directamente en ese marco.
- `BRAIN_ARCHITECTURE.md` — el grafo acíclico de 7 capas entre los 14 dominios, el techo de gobernanza sobre el que corre el grafo concreto de esta propuesta (sección 1).

---

## 1. El grafo real sobre el que se propaga

Los documentos anteriores hablan de "el grafo de derivación de Facts" (`FACT_MODEL.md` §8), "el grafo de dependencia entre Inferences" (`INFERENCE_ENGINE.md` §4) y "el grafo acíclico de 7 capas entre Domains" (`BRAIN_ARCHITECTURE.md`) como si fueran tres cosas separadas. A efectos de propagación, **son tres tipos de arista del mismo grafo**, y separarlos en la práctica es exactamente lo que impediría diseñar un mecanismo único capaz de recorrerlos todos con miles de cambios en juego.

**Nodos:** cada nodo es un concepto estable — un id de concepto de Fact (`FACT_MODEL.md` §7), un par (Constraint, ámbito) evaluado, un id de concepto de Inference, o una huella de Hallazgo (`OBSERVATION_MODEL.md` §5). Nunca un id de instancia — los ids de instancia cambian en cada versión de ProjectState; el grafo de propagación tiene que seguir siendo el mismo grafo a través de todas las versiones, o sería imposible reutilizar ningún trabajo de una versión a la siguiente (sección 8).

**Aristas**, de tres tipos, cada uno licenciado por una regla ya fijada en otro documento:

| Tipo de arista | Qué conecta | Quién la licencia |
|---|---|---|
| **Derivación de Fact** | Un Fact derivado y los Facts que lo componen | El catálogo único de composición (`FACT_MODEL.md` §4) |
| **Evaluación de Constraint** | Un Constraint y los Facts que consume | La dependencia de datos declarada (`CONSTRAINT_MODEL.md` §7) |
| **Composición de Inference** | Una Inference compuesta y las Inferences/Facts que consume, incluyendo los saltos entre Domains | Las 3 clases de dependencia entre Domains (`CHAIN_REASONING.md` §6) — cada salto entre Domains es, literalmente, un ChainEffect |

**El grafo entre Domains de `BRAIN_ARCHITECTURA.md` es el techo de gobernanza, no el grafo que se recorre.** Fija qué aristas del tercer tipo *pueden* existir (un Domain solo puede tener una arista de composición hacia otro si declaró la dependencia correspondiente) — pero el grafo que Motor de Propagación recorre en la práctica, para un proyecto concreto, es la instancia real de nodos y aristas de los tres tipos que existen en ese ProjectState, casi siempre muchísimo más pequeño que "todo lo que el catálogo de Domains permitiría". Esta distinción — techo de gobernanza vs. grafo instanciado — es la que hace posible que la sección 9 (rendimiento) tenga un argumento real: el coste de propagar depende del tamaño del grafo instanciado alcanzable, no del catálogo completo de 14 dominios y miles de Rules.

---

## 2. Propagación

El mecanismo es un recorrido por **cola de trabajo** (worklist), no una re-evaluación recursiva ingenua — la diferencia importa a la escala de miles de cambios porque una recursión ingenua repite trabajo cada vez que dos caminos distintos llegan al mismo nodo, mientras que una cola de trabajo con un conjunto de nodos ya procesados no:

1. Un Change aceptado invalida uno o más Facts (`FACT_MODEL.md` §6) — sus ids de concepto forman el **conjunto sucio inicial**.
2. El conjunto sucio inicial se carga en la cola de trabajo.
3. Se extrae un nodo de la cola; se identifican sus aristas salientes en el grafo instanciado (sección 1) — todo nodo que lo consume.
4. Cada nodo consumidor se re-evalúa (recomposición si es un Fact derivado, `CONSTRAINT_MODEL.md` §3.1 si es una evaluación de Constraint, `INFERENCE_ENGINE.md` §3 si es una Inference).
5. Si el resultado de la re-evaluación es distinto del que tenía antes, ese nodo se añade a la cola (todavía no procesado) y se marca como sucio; si el resultado es idéntico al que ya tenía, no se propaga más allá — es el punto donde la propagación se detiene por sí sola sin necesidad de alcanzar el final del grafo.
6. Se repite desde el paso 3 hasta que la cola queda vacía.

El paso 5 es la optimización más importante de todo el documento y merece nombrarse aquí, aunque se detalle en la sección 8: **un cambio que no cambia el resultado no se propaga**. Si un Fact se sustituye por una instancia nueva pero con el mismo valor (un caso raro pero real — una corrección de metadato que no afecta al cálculo), la propagación se detiene en el primer nodo que lo consume, no recorre el resto del grafo sin necesidad.

---

## 3. Prioridad

Con miles de cambios y un grafo instanciado potencialmente grande, el orden en que se procesa la cola de trabajo no es indiferente — determina cuándo el Arquitecto ve el primer resultado útil, y cuánto trabajo se hace antes de que un conflicto detenga una rama entera (sección 7). El orden combina dos criterios, aplicados en este orden:

1. **Tipo de efecto, primero** — reutiliza directamente la clasificación de tres valores ya fijada en `REASONING_ENGINE_SPEC.md` entidad 14: **inmediato** (un salto desde el Change) antes que **indirecto** (dos o más saltos) antes que **acumulativo** (evaluado a nivel de Sesión, `PROJECT_MEMORY.md` §3, no dentro de una sola pasada de la cola). Esto no es una preferencia arbitraria — un efecto inmediato es, por definición, más barato de calcular y más directamente accionable por el Arquitecto que uno lejano, así que procesarlo antes da la señal más útil primero sin coste adicional.
2. **Nivel de impacto, en caso de empate dentro del mismo tipo de efecto** — los 6 niveles de `CHAIN_REASONING.md` (Local→Urbanístico); dentro de "inmediato" o de "indirecto", se procesan primero los nodos de impacto Local, luego Planta, y así sucesivamente. Un efecto que solo afecta a una pieza concreta interesa antes, y es más barato de verificar, que uno que podría afectar a la edificabilidad completa de la parcela.

**Invariante de esta sección:** la prioridad decide *el orden*, nunca *si* algo se procesa — todo nodo de la cola se procesa exactamente una vez (o se cancela explícitamente, sección 5), nunca se descarta por tener baja prioridad. Confundir orden con descarte reintroduciría, por la puerta de atrás, el mismo patrón de silencio que el resto de la serie ya prohíbe repetidamente.

---

## 4. Agrupación

Cuando llegan varios Changes juntos — una importación masiva, una edición rápida en la que el Arquitecto encadena varias modificaciones antes de que la primera termine de propagarse — procesarlos uno a uno, con una pasada completa de cola de trabajo por cada uno, desperdicia trabajo: es frecuente que el Fact que el Change 1 produjo se vuelva a sustituir por el Change 3 antes de que nada corriente abajo necesitara verlo en su estado intermedio.

El mecanismo es una **ventana de coalescencia**: los Changes que llegan dentro de la misma Sesión activa (`PROJECT_MEMORY.md` §2), en una ventana de tiempo corta o como parte de una única operación por lotes declarada, se aplican todos antes de construir el conjunto sucio inicial — el conjunto sucio se construye sobre el **estado final** de todos los Changes de la ventana, nunca sobre cada estado intermedio. Una sola pasada de cola de trabajo procesa el efecto acumulado de todos ellos, en vez de N pasadas independientes que se pisarían entre sí.

Esto no sustituye la comprobación de efectos acumulativos de `PROJECT_MEMORY.md` §3 (que sigue evaluándose Change a Change, para que el Arquitecto tenga visibilidad continua) — es un mecanismo de propagación, no de memoria: la ventana de coalescencia decide cuántas veces corre la cola de trabajo, no cuántas veces se registra lo que pasó. Ambos pueden coexistir porque responden a preguntas distintas: "qué se le muestra al Arquitecto según ocurre" (`PROJECT_MEMORY.md`) frente a "cuánto trabajo de recálculo hace falta realmente" (aquí).

---

## 5. Cancelación

Dos escenarios distintos, cada uno con su propio mecanismo:

**Cancelación por modo especulativo.** Cuando el Motor de Decisión genera una Alternative (`REASONING_ENGINE_SPEC.md` entidad 16, "ninguna Alternative se presenta sin haber sido re-evaluada") o cuando `CONFLICT_ENGINE.md` §5 necesita comparar varias resoluciones posibles antes de presentar una Recommendation, la propagación corre en **modo especulativo**: construye su propio conjunto sucio y su propia cola de trabajo sobre una copia aislada del estado, nunca sobre el ProjectState real, y nunca escribe una versión nueva de Fact/Inference en el histórico permanente. Al terminar de comparar, el resultado especulativo se descarta por completo — no queda ningún rastro en la memoria del proyecto salvo el propio registro de la Alternative considerada (`PROJECT_MEMORY.md` §1.1). Cancelar una corrida especulativa es, literalmente, no confirmarla — no hace falta deshacer nada porque nunca llegó a escribir nada real.

**Cancelación por obsolescencia.** Dentro de una misma pasada de cola de trabajo (o de una ventana de coalescencia, sección 4), si un nodo todavía pendiente de procesar se vuelve a ensuciar — porque otro Change, procesado antes en la misma cola, ya invalidó de nuevo el valor que este nodo iba a usar — el nodo pendiente **no se procesa con el valor antiguo**; se cancela esa entrada concreta de la cola y se sustituye por la que resulte de re-evaluarlo con el valor ya actualizado. Sin esta regla, la cola podría producir un resultado transitorio correcto-mientras-se-calculó pero ya obsoleto en el momento de terminar de calcularse — trabajo gastado en un valor que nadie iba a ver.

---

## 6. Convergencia

La cola de trabajo converge cuando queda vacía (sección 2, paso 6) — es el caso normal y, en la enorme mayoría de los cambios reales, el que ocurre, porque el grafo entre Domains es acíclico por capas (`BRAIN_ARCHITECTURA.md`) salvo hacia el Dominio 12, que por diseño solo tiene dependencias de referencia (nunca estructurales) hacia el resto — así que un ciclo estructural genuino no debería poder formarse nunca por construcción del catálogo de dominios.

Dos salvaguardas cubren lo que la prevención estructural no puede cubrir del todo — un ciclo de *razonamiento*, no de estructura, donde dos conclusiones se empujan mutuamente sin que el grafo declarado sea, en sí mismo, cíclico (el caso que `CHAIN_REASONING.md` §8 ya nombraba sin mecanismo concreto):

- **Detección por estado visitado**: dentro de una misma pasada, se registra cada (nodo, valor) que la cola ya produjo. Si un nodo vuelve a la cola con exactamente el mismo valor que ya tuvo antes en esta pasada, es un ciclo genuino — no una cadena larga que converge lentamente — y se detiene inmediatamente, sin esperar a agotar ningún límite de saltos. Se materializa como un caso a exponer, con el mismo tratamiento que un Conflict sin resolución automática (`CONFLICT_ENGINE.md`) — nunca se elige arbitrariamente cuál de los dos nodos "gana" para romper el ciclo.
- **Límite de saltos como salvaguarda secundaria**: independiente de la detección de ciclos, un contador de saltos por rama de propagación marca para revisión cualquier cadena que lo supere sin haber convergido ni haber repetido un estado — la invariante ya fijada en `REASONING_ENGINE_SPEC.md` entidad 14 convertida en mecanismo concreto. No detiene la cola entera, solo la rama concreta que lo dispara, y la deja señalada para que el Curador de Conocimiento revise si esa cadena de dependencias es correcta o si esconde una dependencia mal declarada.

---

## 7. Conflictos

`CONFLICT_ENGINE.md` ya define el Verificador de Coherencia como el proceso que examina el conjunto de Inferences vigentes **una vez la cola de trabajo converge** (`INFERENCE_ENGINE.md` §6). Este documento añade una segunda capa de detección, más temprana, que ocurre *dentro* de la propagación misma:

**Colisión durante la propagación**: si, mientras la cola de trabajo está activa, dos ramas de procesamiento distintas producen resultados incompatibles para el mismo nodo dentro de la misma pasada (dos caminos del grafo llegan al mismo id de concepto con conclusiones que no pueden ser ambas ciertas), la propagación no continúa corriente abajo de ese nodo sin resolverlo — aplica de inmediato el paso 1 del protocolo de intervención de `CONFLICT_ENGINE.md` §5 (suspensión de composición corriente abajo), deteniendo esa rama concreta en el momento en que la colisión ocurre, en vez de dejar que el resto de la cola siga construyendo Inferences compuestas sobre una base que ya se sabe contradictoria.

Esto no sustituye al Verificador de Coherencia — lo complementa. Una colisión durante la propagación solo detecta conflictos donde dos caminos del grafo **se cruzan literalmente** en el mismo nodo dentro de la misma pasada; hay tipos de Conflict (una Preference contra un Problem, Tipo 3 de `DECISION_ENGINE.md` §2, por ejemplo) que no necesariamente aparecen como una colisión de rutas del grafo y que solo el barrido completo del Verificador de Coherencia, al final, puede capturar con seguridad. Las dos capas juntas son necesarias: la colisión en vuelo ahorra trabajo (detiene una rama que iba a construir conclusiones inútiles); el Verificador de Coherencia al final sigue siendo la garantía de completitud.

---

## 8. Optimización

Tres técnicas, cada una atacando un tipo de coste distinto:

- **Memoización por huella de entrada.** Si un nodo se re-evalúa dos veces con exactamente el mismo conjunto de valores de entrada (mismo mecanismo de huella que `FACT_MODEL.md` §11.3 ya define para deduplicar Facts), el resultado se reutiliza sin recalcular — situación frecuente cuando varias ramas de la cola convergen hacia el mismo nodo consumidor desde caminos distintos.
- **Poda por alcanzabilidad**, ya establecida en general por `FACT_MODEL.md` §11.4 y reafirmada aquí como el principio que hace posible todo lo demás: la cola de trabajo solo visita nodos alcanzables desde el conjunto sucio inicial — nunca recorre el grafo completo del proyecto. Es la razón estructural por la que "miles de cambios" es un objetivo alcanzable en vez de una aspiración: el coste de cada Change es proporcional al tamaño de su propio subgrafo alcanzable, no al tamaño del catálogo completo de 14 dominios.
- **Paralelización estructuralmente segura.** Dos nodos de la cola que no tienen ninguna arista entre sí (ni directa ni a través de un tercer nodo pendiente en la misma pasada) pueden procesarse en cualquier orden entre sí sin afectar al resultado — el orden solo importa a través de las aristas declaradas del grafo (sección 1). Esto es una propiedad estructural del diseño, no una decisión de implementación: cualquier futura implementación puede aprovecharla para paralelizar, sin que este documento tenga que prescribir cómo.

---

## 9. Rendimiento

El argumento de que este diseño soporta miles de cambios se apoya en tres piezas ya descritas, combinadas: la poda por alcanzabilidad (sección 8) acota el coste de cada Change al tamaño de su propio subgrafo, no al del proyecto entero; la agrupación por ventana de coalescencia (sección 4) evita pagar ese coste una vez por cada Change cuando llegan varios juntos, pagándolo una vez por el efecto neto del lote; y la cancelación por obsolescencia (sección 5) evita gastar ese coste en resultados que quedarán descartados antes de que nadie los vea. Ninguna de las tres, por separado, sería suficiente — es la combinación la que hace que el coste total de propagar miles de cambios en una sesión se parezca al coste de propagar el **efecto neto** de esa sesión, no a miles de recorridos independientes del grafo completo.

**El riesgo que puede romper este argumento no es técnico, es de gobernanza — y es el más importante de nombrar en todo este documento.** La poda por alcanzabilidad solo funciona si las dependencias declaradas (`CONSTRAINT_MODEL.md` §7, `CHAIN_REASONING.md` §6) son razonablemente específicas — un Domain o una Rule que declare una dependencia demasiado amplia ("depende de todos los Facts de superficie", en vez de un tipo concreto) convierte, sin ningún error visible, un subgrafo alcanzable pequeño en uno que efectivamente cubre todo el proyecto. Ese Domain no rompería nada de forma ruidosa — simplemente haría que cada Change, sin importar cuán local, disparara una propagación del tamaño del proyecto completo, y el sistema seguiría siendo "correcto" mientras dejaba de ser rápido. La defensa, otra vez, no es un mecanismo del motor — es la misma disciplina de especificidad en la declaración de dependencias que el Curador de Conocimiento ya tiene que sostener para cada catálogo cerrado de la serie, aplicada aquí a la pieza que, si se relaja, es la más costosa de las que se han relajado hasta ahora.

---

## Cierre

Este documento no introduce ninguna entidad de conocimiento nueva — no hay un Fact, Constraint o Inference distinto de los ya definidos. Lo que aporta es la respuesta a una pregunta que el resto de la serie daba por sentada sin especificarla del todo: cómo se recorre, en la práctica y a escala, el mismo grafo que `FACT_MODEL.md`, `CONSTRAINT_MODEL.md` e `INFERENCE_ENGINE.md` ya habían fijado por partes. La cola de trabajo, la ventana de coalescencia, la cancelación por obsolescencia y la colisión en vuelo no cambian ningún resultado que el motor pudiera producir ya — cambian cuánto cuesta producirlo, que es, precisamente, lo que separa un diseño correcto en el papel de uno que sigue siendo correcto con miles de cambios reales encima.
