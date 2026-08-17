# CONSTRAINT_MODEL.md

**Propósito:** diseñar el modelo declarativo de **Constraint** — la unidad que expresa una restricción arquitectónica completa (umbral, condiciones de aplicación, excepciones, prioridad, normativa) sin una sola línea de lógica imperativa propia. El encargo es explícito: nada de reglas escritas en `if`, y el modelo tiene que poder representar miles de restricciones — el horizonte de los 14 dominios de `BRAIN_ARCHITECTURE.md` — **sin modificar el motor** cada vez que se añade una. Como en el resto de la serie, no hay clases ni código: es la especificación que cualquier implementación futura debe respetar.

**Referencias obligatorias, asumidas como ya decididas:**
- `REASONING_ENGINE_SPEC.md` — entidad 8 (Constraint) y entidad 9 (Rule), y el principio de coherencia "separación estricta entre dato y lógica" de su cierre, que este documento lleva hasta su consecuencia final.
- `FACT_MODEL.md` — el modelo de Fact que todo Constraint consume: sus tres ejes de tipificación, el catálogo único de composición para Facts derivados (sección 4, reutilizado aquí como frontera de qué NO debe vivir dentro de un Constraint), y el contrato de lectura de cuatro estados (Fact / Unknown / Assumption / No aplicable, sección 10) que todo Constraint debe respetar al leer sus datos de entrada.
- `BRAIN_ARCHITECTURE.md` — el principio 4 (trazabilidad normativa obligatoria) y el principio 1 (toda Rule pertenece a un Domain).
- `ARCHITECTURAL_KNOWLEDGE_MAP.md` — la clasificación de 4 niveles de conocimiento y la estructura de 10 secciones por dominio, en particular "Normativa relacionada" (§3) y "Excepciones" (§7), que este documento traduce a estructura de datos.
- `DECISION_ENGINE.md` — la jerarquía de severidad de 4 valores (bloqueante / riesgo variable / recomendable / preferencial) y el modelo de confianza cualitativo, reutilizados aquí sin redefinirlos.
- `REFACTOR_MASTERPLAN.md` (tareas 22-24) — el precedente real y ya priorizado de convertir `classify_problems` de código imperativo a tabla declarativa; este documento es el diseño al que ese refactor debería converger, no un ejercicio independiente.

**Alcance:** este documento no redefine Fact, Domain, Rule, Inference ni Evidence — los trata como ya fijados y describe cómo un Constraint los usa. Reutiliza y amplía el glosario de actores ya establecido, añadiendo uno:

- **Intérprete de Constraints** — el proceso único y compartido entre los 14 dominios que sabe evaluar cualquier Constraint, sea del dominio que sea, siguiendo el catálogo cerrado de patrones de la sección 3. Es la pieza concreta que hace cierta la promesa de "miles de restricciones sin tocar el motor" (sección 14): el Motor de Dominio de cada dominio no contiene lógica de evaluación propia, delega en este intérprete único. Sin nombrarlo aparte, la tentación de que cada dominio implemente "su propia forma de evaluar" sería casi automática — mismo tipo de riesgo de gobernanza que `FACT_MODEL.md` ya señaló para el Compositor de Hechos.

---

## 1. El problema que este modelo tiene que resolver

Hoy, cada restricción en `analyzer/evaluator.py` es una función Python: lee uno o más valores, compara contra un umbral que puede depender de `UMBRALES_TIPOLOGIA` o `UMBRALES_ZONA`, y construye un resultado. Con ~23 bloques ya es difícil de auditar de un vistazo (`classify_problems` sola tiene 327 líneas y complejidad ciclomática 49, según `TECH_REVIEW.md`); con 14 dominios y miles de restricciones, ese patrón deja de ser sostenible por una razón estructural, no solo de volumen: **cada restricción nueva es una oportunidad de reintroducir el Bug #1** (tipología/zona no propagada, `TECH_REVIEW.md`) porque cada función decide por su cuenta cómo leer sus umbrales contextuales. Un modelo declarativo elimina esa clase de bug por diseño: si resolver el umbral correcto para un contexto dado es una única función genérica que lee una tabla de datos, no hay 2.000 sitios donde se pueda olvidar pasar el parámetro correcto — hay uno.

El criterio de éxito de este documento es literal: **añadir una restricción nueva debe significar escribir un registro de datos, nunca una línea de código nueva en el motor.**

---

## 2. Qué es un Constraint en este modelo

Un Constraint es una unidad declarativa autocontenida que expresa, íntegramente como datos, una restricción evaluable: qué Fact mira, en qué ámbito, bajo qué condiciones aplica, contra qué la compara, qué excepciones la desactivan, qué severidad produce si se incumple, y con qué normativa se justifica.

Esto es una ampliación deliberada de la entidad 8 de `REASONING_ENGINE_SPEC.md`, no una contradicción. Allí, Constraint era solo el umbral (el dato) y Rule llevaba "la lógica evaluativa" (entidad 9). Ese reparto es correcto en principio pero, aplicado literalmente, dejaría la lógica de condiciones/excepciones/combinación como código bespoke dentro de cada Rule — exactamente el "if" que el encargo prohíbe. Este documento cierra esa grieta: **toda la lógica evaluable de una restricción — condiciones incluidas — se expresa dentro del Constraint como datos**, usando únicamente el vocabulario cerrado de las secciones 3-5. Rule, en este modelo, deja de portar lógica propia: pasa a ser el vínculo formal entre un Domain y el conjunto de Constraints que le pertenecen, y el que recibe la Inference/Problem que produce el Intérprete de Constraints. Sigue existiendo como entidad — sigue siendo cierto que "toda Rule pertenece a exactamente un Domain" — pero su contenido es, en el caso general, casi enteramente delegado.

---

## 3. Estructura de un Constraint

| Campo | Contenido | Seguir en |
|---|---|---|
| **id** | Namespaced (`dominio.codigo`), nunca un string libre — mismo problema de colisión que `FACT_MODEL.md` §12.2 para tipos de Fact | — |
| **nombre** | Título humano, para mostrar en Evidence/Explanation | — |
| **dominio** | El Domain propietario (entidad 2 del spec) | — |
| **patrón de evaluación** | Uno de los 5 patrones cerrados del catálogo | §3.1 |
| **ámbito de aplicación** | Nodo/dimensión de ámbito sobre el que se evalúa (reutiliza `FACT_MODEL.md` §2.3 — pieza, unidad, elemento constructivo...) | — |
| **condiciones de activación** | Árbol lógico de predicados que decide si el Constraint aplica a una instancia concreta de ese ámbito | §4 |
| **Fact(s) de entrada** | Tipo(s) namespaced de Fact que el patrón necesita leer | §7 |
| **parámetros** | Umbral(es), como tabla de resolución contextual, no como valor fijo | §9 |
| **comparador** | Operador declarativo cerrado (§3.2) | §3.2 |
| **excepciones** | Lista de Excepcion adjuntas | §5 |
| **severidad** | Uno de los 4 valores de `DECISION_ENGINE.md` §3 | §6 |
| **nivel de conocimiento** | 1-4, de `ARCHITECTURAL_KNOWLEDGE_MAP.md` | §8 |
| **normativa asociada** | Fuente exacta + ámbito territorial + vigencia | §8 |
| **dependencias** | Otros Constraints/Domains de los que depende | §7 |
| **vigencia del registro** | Versión desde/hasta, append-only, mismo mecanismo que `FACT_MODEL.md` §7 aplicado aquí a Constraint | — |

Un Constraint nunca contiene una expresión de propósito general (una fórmula arbitraria, una condición "libre"). Todo lo que puede decir está limitado a los vocabularios cerrados que siguen — esa limitación *es* la garantía de que el motor no necesita crecer para soportarlo.

### 3.1 Catálogo cerrado de patrones de evaluación

Este catálogo es, literalmente, el motor. Es pequeño a propósito y crece con la misma disciplina de gobernanza que el catálogo de Domains — un evento raro y deliberado del Curador de Conocimiento, nunca una consecuencia de añadir una restricción concreta (ver riesgo en sección 14).

| Patrón | Qué expresa | Ejemplo real de `evaluator.py` que sustituye |
|---|---|---|
| **UMBRAL_SIMPLE** | Compara un Fact (observado o derivado) contra un parámetro resuelto por contexto | Ancho mínimo de itinerario accesible |
| **UMBRAL_CON_EXCEPCION** | Igual, pero evalúa primero la lista de Excepciones; si alguna aplica, el resultado es "no aplicable", nunca "cumple" | Superficie mínima de vivienda, salvo rehabilitación catalogada |
| **PRESENCIA_OBLIGATORIA** | Exige que exista al menos un Fact de un tipo dado dentro del ámbito — sin comparación numérica | Todo baño interior debe tener una pieza de ventilación asociada |
| **COMBINACION_LOGICA** | Combina el resultado de dos o más Constraints ya evaluados con AND/OR/NOT | "Cumple accesibilidad" solo si pasan a la vez itinerario Y espacio de giro |
| **AGREGACION_AMBITO** | Aplica un patrón de los anteriores a cada nodo hijo de un ámbito y agrega el resultado con un cuantificador declarativo (`todos` / `alguno` / `ninguno`) | "Todas las piezas de dormitorio cumplen superficie mínima" |

Nótese que **ninguno de los cinco patrones hace aritmética**. Sumar, promediar o calcular una ratio ya ocurrió, si hacía falta, en la capa de Fact derivado (`FACT_MODEL.md` §4, catálogo único de composición). Un Constraint nunca calcula — solo compara y combina. Esta frontera es la razón por la que el catálogo de patrones puede quedarse en cinco durante años: cualquier necesidad de "más matemática" pertenece al Compositor de Hechos, no a un patrón nuevo aquí.

### 3.2 Vocabulario cerrado de comparadores

`>=`, `>`, `<=`, `<`, `==`, `!=`, `entre` (rango con límites inclusivos/exclusivos declarados), `pertenece_a` (el valor está en un conjunto declarado — útil para Facts categóricos), `coincide_con_patrón` (para Facts de texto/etiqueta), `existe` / `no_existe` (para el patrón PRESENCIA_OBLIGATORIA). Cerrado igual que el catálogo de patrones — añadir un comparador nuevo es un evento de gobernanza, no una necesidad de cada restricción.

---

## 4. Condiciones de activación

Toda restricción real aplica solo bajo ciertas circunstancias ("este umbral solo rige en vivienda plurifamiliar"; "esta regla de evacuación solo aplica a partir de tres plantas"). Ese "solo si" se expresa como un **árbol lógico** construido con tres combinadores cerrados — `AND`, `OR`, `NOT` — sobre **predicados de contexto**.

Un predicado de contexto es, en sí mismo, una comparación del vocabulario de la sección 3.2 aplicada a un Fact de naturaleza declarada o contextual-normativa (`FACT_MODEL.md` §2.2) — tipología, zona climática, comunidad autónoma, número de plantas, uso del edificio, catalogación patrimonial, lo que sea que exista como Fact. No hay diferencia estructural entre "una condición de activación" y "un predicado de excepción" (sección 5) ni entre estos y el propio comparador principal del Constraint (sección 3.2) — es el mismo vocabulario cerrado reutilizado en los tres sitios, deliberadamente, para que el Intérprete de Constraints solo necesite implementarlo una vez.

**Invariante:** si una condición de activación referencia un Fact que resulta ser Unknown (no No aplicable — la distinción de `FACT_MODEL.md` §10 importa aquí exactamente igual que para Facts), el Constraint completo pasa a estado "no evaluable" y así debe registrarse en la Evidence (sección 8) — nunca se asume tácitamente que la condición es falsa ni que es verdadera. Es la misma disciplina de "nunca silencio" que gobierna todo el modelo desde `FACT_MODEL.md` §1.

---

## 5. Excepciones

Una Excepción es una estructura declarativa adjunta a un Constraint, con su propia identidad y su propio ciclo append-only — nunca una rama de código dentro de la evaluación:

| Campo | Contenido |
|---|---|
| **condición** | Mismo árbol lógico AND/OR/NOT sobre predicados que la sección 4 |
| **efecto** | Siempre "no aplicable" — nunca "cumple silenciosamente"; una excepción retira el Constraint de la evaluación, no falsea su resultado |
| **normativa propia** | Su propia fuente citable, que puede ser distinta de la del Constraint principal (p. ej. "exención por edificio catalogado, art. X de la norma de patrimonio", distinta del CTE que motiva el Constraint base) |
| **vigencia** | Igual que cualquier otro registro append-only |

**Caso especial, y el más importante:** hay excepciones cuya condición no es evaluable mecánicamente porque depende de un juicio de Nivel 4 (`ARCHITECTURAL_KNOWLEDGE_MAP.md`, "criterio arquitectónico") — el caso típico es "salvo que el arquitecto justifique una solución alternativa equivalente". Este tipo de excepción se marca explícitamente como **excepción sujeta a justificación humana** y el Intérprete de Constraints nunca la aplica por sí solo: la superficie como una excepción *candidata*, disponible para que el Arquitecto la invoque explícitamente — un flujo de Decision/Preference (`DECISION_ENGINE.md`), no una supresión automática del Problem. Tratarla igual que una excepción mecánica sería, en la práctica, dejar que el sistema tome una decisión de criterio que `DECISION_ENGINE.md` reserva expresamente al Arquitecto.

---

## 6. Prioridad

Un Constraint declara un único campo de severidad, tomado sin modificación de la jerarquía de 4 valores ya fijada en `DECISION_ENGINE.md` §3: **bloqueante / riesgo variable / recomendable / preferencial**. Nunca un número — la misma disciplina anti-precisión-fabricada que ya rige Confidence en `REASONING_ENGINE_SPEC.md` entidad 20.

Este modelo no reimplementa la resolución de prioridad entre restricciones en conflicto — esa lógica ya vive, correctamente, en `DECISION_ENGINE.md` §3 (jerarquía de 5 criterios) y es responsabilidad de Conflict/Domain 12, no de Constraint. El único deber de un Constraint aquí es **suministrar con honestidad los dos insumos que esa jerarquía necesita**: su severidad declarada y su nivel de conocimiento (sección 8) — nunca inflar una hacia "bloqueante" ni el otro hacia "Nivel 1" para que una restricción "gane" comparaciones más a menudo. Mantener esta frontera es lo que evita que Constraint duplique, mal, una lógica que ya está bien resuelta en otro documento de la serie.

---

## 7. Dependencia

Dos clases distintas, que no deben confundirse:

**(a) Dependencia de datos** — qué Fact(s) necesita el patrón de evaluación para funcionar. Se declara explícitamente por tipo namespaced. Si el Fact requerido no está disponible, el contrato de lectura de cuatro estados de `FACT_MODEL.md` §10 decide el resultado (Unknown → Constraint no evaluable; No aplicable → Constraint retirado sin más; Assumption → evaluable, pero el resultado nunca puede alcanzar Confidence "Alta").

**(b) Dependencia entre Constraints** — necesaria solo para el patrón COMBINACION_LOGICA, que por definición consume el resultado de otros Constraints ya evaluados. Estas dependencias forman un **grafo acíclico dirigido**, mismo principio que el grafo de capas de `BRAIN_ARCHITECTURE.md` y el grafo de derivación de Facts (`FACT_MODEL.md` §8): un Constraint no puede depender, ni siquiera transitivamente, de un Constraint que dependa de él. Cuando la dependencia cruza de un Domain a otro, se declara usando exactamente las tres clases ya fijadas en `CHAIN_REASONING.md` §6 (estructural / condicional / de referencia) — no se inventa una taxonomía nueva de dependencia entre dominios solo para Constraint.

---

## 8. Evidencia y normativa asociada

**Evidencia:** cada evaluación de un Constraint — produzca o no un Problem — genera un tramo de Evidence (`REASONING_ENGINE_SPEC.md` entidad 18) construido de forma genérica por el Intérprete de Constraints, nunca por código específico de la restricción: qué Fact(s) se leyeron (con su eje de origen epistémico, sección 4 de `FACT_MODEL.md`, visible), qué patrón se usó, qué condiciones de activación se evaluaron y con qué resultado, qué excepciones se comprobaron y si alguna aplicó, qué parámetro concreto resultó de resolver la tabla contextual (sección 9) — el valor final, no solo la fórmula — y la cita normativa. Que esta construcción sea genérica es, de nuevo, una consecuencia directa de que la evaluación entera es declarativa: no hay 2.000 formas distintas de construir Evidence porque no hay 2.000 formas distintas de evaluar.

**Normativa asociada**, como estructura propia dentro de cada Constraint:

| Campo | Contenido |
|---|---|
| **fuente exacta** | Artículo/decreto/DB del CTE/norma UNE — el identificador citable concreto |
| **ámbito territorial** | Estatal, autonómico o municipal — relevante en España, donde varias comunidades autónomas tienen normativa propia sobre lo mismo que el CTE (ver sección 13) |
| **nivel de conocimiento** | Nivel 2 (normativa verificable) o Nivel 3 (buena práctica) de `ARCHITECTURAL_KNOWLEDGE_MAP.md` — un Constraint de Nivel 3 cita su fuente igualmente ("criterio profesional: [documento/guía]"), nunca la deja en blanco |
| **vigencia de la norma** | Rango de fechas en que la norma citada estuvo vigente — distinto de la vigencia del propio registro de Constraint (que puede versionarse por otras razones, p. ej. corregir una transcripción) |

**Invariante heredado sin cambios de `REASONING_ENGINE_SPEC.md` entidad 8:** ningún Constraint sin fuente citable puede activarse en producción.

---

## 9. Parámetros

El campo de parámetros de un Constraint nunca es un valor escalar fijo — es una **tabla de resolución** indexada por los mismos predicados de contexto que las condiciones de activación (sección 4). Esto generaliza directamente los `UMBRALES_TIPOLOGIA`/`UMBRALES_ZONA` que hoy existen como diccionarios Python en `evaluator.py`: en este modelo son datos declarativos con la misma forma conceptual, pero con dos propiedades que el código actual no tiene:

1. **La tabla puede indexar por más de un eje a la vez** (tipología × zona climática × comunidad autónoma simultáneamente), no solo por uno.
2. **La cadena de resolución en caso de combinación no cubierta es explícita y auditable**, nunca un `.get(clave, valor_por_defecto)` silencioso. Se declara como una secuencia ordenada de niveles de fallback (p. ej.: valor específico de comunidad autónoma → valor de zona climática genérico → valor de tipología genérico → valor nacional por defecto), y **cada vez que se usa un nivel de fallback en vez de una coincidencia exacta, ese hecho se registra en la Evidence de la evaluación** — es la corrección estructural directa al patrón que causó el Bug #1: no es que el sistema no pueda tener un valor por defecto, es que nunca puede usarlo sin decirlo.

---

## 10. Tipología

La tipología (hoy: plurifamiliar / unifamiliar / rehabilitación, `UMBRALES_TIPOLOGIA` en `evaluator.py`) no es un caso especial del motor — es uno más de los ejes contextuales sobre los que una tabla de parámetros o una condición de activación puede indexar, definido como un Fact de naturaleza declarada (`FACT_MODEL.md` §2.2). El catálogo de tipologías válidas es, como el catálogo de Domains, abierto y mantenido por el Curador de Conocimiento — añadir una tipología nueva (vivienda dotacional, coliving) es añadir un valor al catálogo y filas nuevas a las tablas de parámetros que la necesiten, nunca una rama nueva en el motor.

---

## 11. Zona climática

Misma lógica que la tipología, con un matiz adicional: la zona climática CTE (A-E) no es un dato declarado directamente por el Arquitecto — es un **Fact derivado**, de naturaleza contextual-normativa, calculado a partir del Fact "ciudad" mediante una función de composición de tabla de referencia (la que hoy vive en `analyzer/cte_zonas.py`, `get_zona_cte`). Que sea un Fact derivado y no un valor que cada Constraint calcule por su cuenta importa por la misma razón que en `FACT_MODEL.md` §9: **un único lugar de verdad**. Ningún Constraint contiene su propia copia del mapeo ciudad→zona; todos leen el mismo Fact ya resuelto. Si el CTE revisa algún día esa tabla, cambia una función de composición — cero Constraints se tocan.

---

## 12. Contexto

Generaliza tipología y zona climática al conjunto abierto de ejes contextuales que cualquier dominio, presente o futuro, pueda necesitar: comunidad autónoma, densidad urbana (ya existe como dato de referencia en `cte_zonas.py`), uso del edificio, número de plantas, catalogación patrimonial, riesgo sísmico de la parcela — la lista no está fijada en el motor a propósito. El principio de diseño es: **cualquier Fact de naturaleza "declarado" o "contextual-normativo" (`FACT_MODEL.md` §2.2) es, automáticamente, un eje de contexto disponible** para condiciones de activación y tablas de parámetros, sin que el Intérprete de Constraints necesite saber de antemano qué ejes existen. Añadir una dimensión de contexto completamente nueva (p. ej. cuando un futuro Dominio de riesgo sísmico lo necesite) es: definir el nuevo tipo de Fact, poblarlo, y empezar a referenciarlo desde Constraints nuevos — cero cambios en el motor, exactamente el mismo argumento que ya sostiene `FACT_MODEL.md` para el ámbito (sección 2.3 de ese documento).

---

## 13. Nota específica: normativa territorial española

Vale la pena nombrarlo aparte porque es una fuente real de complejidad que un modelo ingenuo subestima: en España, una misma restricción puede tener un umbral estatal (CTE) y un umbral autonómico más estricto que lo sustituye en su ámbito territorial (habitabilidad, superficies mínimas — remiten a menudo a decreto autonómico, no al CTE, ya señalado en `ARCHITECTURAL_KNOWLEDGE_MAP.md` como fuente de "Domain 2"). Este modelo no necesita un mecanismo especial para esto: es, simplemente, dos Constraints con el mismo Fact de entrada y comparador, condiciones de activación mutuamente excluyentes por comunidad autónoma (sección 4), y normativa asociada distinta cada uno (sección 8) — el mismo patrón UMBRAL_SIMPLE, dos registros de datos. Señalarlo aquí sirve para confirmar que el modelo no necesita crecer para cubrir este caso, que es habitual, no una excepción rara.

---

## 14. Cómo este diseño soporta miles de Constraints sin tocar el motor

1. El motor es, literalmente, el Intérprete de Constraints implementando un catálogo cerrado de 5 patrones de evaluación (§3.1) y un vocabulario cerrado de comparadores (§3.2) y combinadores lógicos (§4) — ninguno de los tres crece por añadir una restricción, solo por una decisión de gobernanza deliberada y poco frecuente, igual que el catálogo de Domains.
2. Toda restricción nueva es un registro de Constraint (y, si hace falta, de Excepcion) — nunca código.
3. Toda variación por tipología, zona climática o cualquier otro eje de contexto es una fila más en una tabla de resolución de parámetros (§9-12) — nunca una rama `if` nueva.
4. Toda restricción compuesta se expresa combinando Constraints ya existentes con el patrón COMBINACION_LOGICA — nunca lógica ad hoc de un dominio concreto.
5. El namespacing de ids (dominio.código) y la gobernanza centralizada del Curador de Conocimiento evitan colisiones cuando 14 dominios contribuyen al mismo catálogo compartido — mismo mecanismo, mismo motivo, que `FACT_MODEL.md` §12.2 aplicó a los tipos de Fact.

El riesgo real de este diseño no es de estructura de datos, es de gobernanza — igual que el riesgo más grave identificado en `FACT_MODEL.md` §12.1: la tentación, bajo presión de un caso "que no encaja bien" en los cinco patrones, de añadir un sexto patrón a medida en vez de forzar el caso a componerse con los cinco existentes. Cada patrón nuevo añadido sin disciplina es, potencialmente, un `if` reintroducido por la puerta de atrás. La defensa no es técnica: es que el Curador de Conocimiento trate el catálogo de patrones con la misma seriedad que el catálogo de Domains — un cambio raro, deliberado, y revisado, nunca una respuesta automática a "esta restricción concreta lo necesita".
