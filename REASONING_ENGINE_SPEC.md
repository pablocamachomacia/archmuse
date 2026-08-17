# REASONING_ENGINE_SPEC.md

**Propósito:** este documento traduce la arquitectura conceptual del cerebro de ArchMuse en un **modelo técnico de entidades** — qué objetos de información deben existir, qué contienen, cómo nacen, cambian y mueren, cómo se relacionan entre sí, y quién tiene permiso para tocarlos. No es una implementación. No hay clases, ni código, ni estructuras de datos concretas — es la especificación que cualquier implementación futura, en cualquier lenguaje o framework, debería respetar para que el motor de razonamiento pueda crecer durante años sin degradarse en un monolito incoherente, exactamente el riesgo que `BRAIN_ARCHITECTURE.md` (Parte 4) ya identificó como el principal enemigo de un sistema con 500+ reglas.

**Referencias obligatorias, todas asumidas como ya decididas y no vueltas a discutir aquí:**
- `BRAIN_ARCHITECTURE.md` — los 14 dominios, sus capas y su grafo de dependencias.
- `ARCHITECTURAL_KNOWLEDGE_MAP.md` — los 4 niveles de conocimiento (hechos objetivos / normativa verificable / buenas prácticas / criterio arquitectónico) por dominio.
- `CHAIN_REASONING.md` — el modelo de propagación de consecuencias, sus tipos de efecto (inmediato/indirecto/acumulativo) y sus niveles de impacto (Local→Urbanístico).
- `DECISION_ENGINE.md` — el modelo de decisión, la jerarquía de prioridad, el modelo de confianza cualitativo, y la taxonomía de cinco categorías de afirmación (hecho / inferencia / hipótesis / recomendación / preferencia).

---

## 0. Análisis del conjunto de entidades propuesto

El encargo pide evaluar, como mínimo, 16 entidades candidatas. No todas merecen el mismo estatus, y tratarlas como iguales sería el primer error de diseño de este documento. Antes de definir cada una en detalle, esta sección fija el criterio:

**Se mantienen como entidades de pleno derecho (identidad propia, ciclo de vida propio):** Fact, Observation, Constraint, Rule, Domain, Problem, Evidence, Conflict, Recommendation, Alternative, Decision, Assumption, Unknown, ChainEffect, Explanation. 15 de las 16 candidatas.

**Se reclasifica una:** **Confidence no es una entidad independiente.** No tiene identidad propia ni ciclo de vida propio — no "nace" ni se "edita", se **calcula** a partir de la cadena de conocimiento que sostiene a otra entidad (un Problem, un Conflict, una Recommendation, un Assumption, un ChainEffect), siguiendo la regla ya fijada en `DECISION_ENGINE.md` (sección 10): la confianza es la del eslabón más débil de esa cadena, nunca un promedio. Tratarla como entidad independiente crearía el riesgo de que quedara desincronizada de la cadena que la justifica — exactamente el tipo de inconsistencia que este documento existe para prevenir. Se define igualmente en detalle (sección F), pero como **valor derivado adjunto**, no como entidad con identidad.

**Se añaden cuatro entidades no incluidas en la lista original, porque los cuatro documentos de referencia las exigen aunque no se hayan nombrado explícitamente:**
- **ProjectState** — ninguna de las 16 entidades candidatas tiene dónde vivir sin un contenedor raíz versionado. Sin él, no hay forma de responder "¿el estado del proyecto en qué momento?", pregunta central para todo el modelo de propagación de `CHAIN_REASONING.md`.
- **Change** — `CHAIN_REASONING.md` (sección 1) define ocho familias de cambio como el disparador de toda propagación; sin una entidad que represente el cambio mismo, la propagación no tiene un origen que registrar ni auditar.
- **Preference** — `DECISION_ENGINE.md` (sección 11) exige distinguir "preferencia" como una de las cinco categorías de afirmación, con su propio tratamiento (nunca puede alterar un hecho, solo desempatar dentro de lo no bloqueante). No puede modelarse como una nota suelta dentro de Recommendation sin perder esa distinción.
- **Inference** — es la pieza que faltaba para que el modelo técnico refleje literalmente la taxonomía de cinco categorías de `DECISION_ENGINE.md`. **Problem no es una entidad aparte de Inference — es una especialización suya**: toda Inference es una conclusión derivada mecánicamente de Facts aplicando una Rule; un Problem es, específicamente, una Inference que representa un incumplimiento. Esta relación se explica en detalle en la sección D.

El resultado es un modelo de **19 entidades de pleno derecho** más **1 valor derivado (Confidence)**, organizado en siete categorías funcionales.

### Tabla de correspondencia con la taxonomía de cinco categorías de `DECISION_ENGINE.md`

| Categoría (`DECISION_ENGINE.md` §11) | Entidad técnica |
|---|---|
| Hecho | **Fact** |
| Inferencia | **Inference** (incluye **Problem** como especialización) |
| Hipótesis | **Assumption** |
| Recomendación | **Recommendation** |
| Preferencia | **Preference** |

Esta correspondencia no es un detalle — es la prueba de que el modelo técnico no es una reinterpretación libre del razonamiento conceptual, sino su traducción literal a entidades.

---

## Glosario de actores

Para no repetir explicaciones en cada entidad, se define aquí un elenco fijo de actores que se reutiliza en todo el documento:

- **Ingesta** — el proceso que interpreta los datos de entrada del proyecto (geometría, metadatos declarados) y produce observaciones crudas.
- **Motor de Dominio** — el proceso que ejecuta las Rules de un Domain concreto sobre los Facts disponibles.
- **Motor de Propagación** — el proceso que implementa el modelo de `CHAIN_REASONING.md` (la operativización del Dominio 12).
- **Motor de Decisión** — el proceso que implementa el modelo de `DECISION_ENGINE.md`.
- **Curador de Conocimiento** — el rol (humano o proceso editorial) responsable de mantener actualizado el catálogo de Domains, Rules y Constraints — el equivalente a un "dueño del contenido normativo".
- **Arquitecto** — el usuario humano final, autor de las Decisions.
- **Cliente** — nunca actúa directamente sobre el sistema; sus preferencias solo entran a través del Arquitecto (coherente con `DECISION_ENGINE.md` §9).

---

## A. Entidades de marco y disparo

### 1. ProjectState

- **Propósito:** representa el estado completo y versionado de un proyecto en un momento dado — el contenedor raíz del que cuelgan todos los Facts, Problems, Conflicts, etc. vigentes en ese momento.
- **Atributos:** identificador del proyecto, número de versión/snapshot, timestamp, referencia al Change que produjo esta versión (si aplica — la versión inicial no tiene Change de origen), estado de propagación (en curso / punto fijo alcanzado, ver `CHAIN_REASONING.md` sección 3).
- **Ciclo de vida:** nace con la primera ingesta de un proyecto. Cada Change aceptado genera una nueva versión de ProjectState — **nunca se sobrescribe una versión anterior**, se encadena una nueva. Nunca se elimina una versión histórica.
- **Relaciones:** contiene (referencia) el conjunto de Facts, Assumptions y Unknowns vigentes en esa versión; es el contexto de todos los Problems, Conflicts, Alternatives y Decisions asociados a esa versión.
- **Invariantes:** dos versiones consecutivas de ProjectState siempre están conectadas por exactamente un Change (salvo la primera); no puede existir un Fact, Problem o Conflict sin una versión de ProjectState a la que pertenezca.
- **Quién puede crearla:** Ingesta (versión inicial) o el Motor de Propagación (nueva versión tras aceptar un Change).
- **Quién puede modificarla:** nadie — es append-only por diseño; toda modificación real es una nueva versión, nunca una edición de la existente.
- **Quién solo puede consumirla:** todos los demás actores.

### 2. Domain

- **Propósito:** representa uno de los dominios de conocimiento de `BRAIN_ARCHITECTURE.md` (o uno futuro, si el catálogo crece más allá de los 14 actuales).
- **Atributos:** nombre, capa (0-6), tipo de dependencias declaradas hacia otros Domains (estructural / condicional / de referencia, ver `CHAIN_REASONING.md` sección 6), prioridad relativa, estado (activo / en construcción / obsoleto).
- **Ciclo de vida:** se crea cuando se decide formalmente incorporar un nuevo dominio de conocimiento (evento poco frecuente, de decisión de producto, no técnica). Puede pasar a "obsoleto" pero nunca se elimina, para no romper la trazabilidad histórica de Rules y Problems que lo referencian.
- **Relaciones:** agrupa Rules; declara dependencias hacia otros Domains; es referenciado por cada Problem/Inference que produce.
- **Invariantes:** toda Rule pertenece a exactamente un Domain (principio 1 de `BRAIN_ARCHITECTURE.md`, Parte 4); las dependencias declaradas de un Domain deben respetar el grafo acíclico por capas — no puede declarar una dependencia hacia un Domain de capa superior salvo el caso explícito del Domain 12.
- **Quién puede crearla:** Curador de Conocimiento.
- **Quién puede modificarla:** Curador de Conocimiento (solo sus metadatos — capa, dependencias, estado; nunca su identidad).
- **Quién solo puede consumirla:** Motor de Dominio, Motor de Propagación, Motor de Decisión, Arquitecto.

### 3. Change

- **Propósito:** representa una modificación introducida en el proyecto — el disparador de toda propagación, correspondiente a una de las ocho familias de cambio de `CHAIN_REASONING.md` (sección 1).
- **Atributos:** familia de cambio, descripción del hecho alterado (qué Fact(s) sustituye o añade), timestamp, autor (siempre el Arquitecto, directamente o transcribiendo una petición del Cliente), referencia a si forma parte de una sesión de edición más amplia (necesario para detectar efectos acumulativos).
- **Ciclo de vida:** se crea cuando el Arquitecto introduce una modificación; pasa por evaluación (Motor de Propagación) y termina en uno de dos estados: aceptado (genera nueva versión de ProjectState) o descartado (si, tras ver sus consecuencias, el Arquitecto decide no aplicarlo).
- **Relaciones:** referencia el/los Fact(s) que sustituye o añade; origina la ejecución del Motor de Propagación; puede agruparse con otros Changes de la misma sesión para el análisis de efectos acumulativos.
- **Invariantes:** un Change nunca modifica un Fact directamente — siempre lo hace produciendo una nueva versión gestionada por ProjectState; un Change descartado no genera nueva versión de ProjectState.
- **Quién puede crearla:** Arquitecto.
- **Quién puede modificarla:** nadie tras su creación — es un registro histórico; si el Arquitecto se retracta, se crea un nuevo Change de reversión, no se edita el original.
- **Quién solo puede consumirla:** Motor de Propagación, Motor de Decisión.

---

## B. Entidades de conocimiento base

### 4. Observation

- **Propósito:** representa una captura cruda de datos — lo que efectivamente "leyó" el sistema de una fuente (el parser de un DXF, un campo de formulario, una integración externa) antes de cualquier validación o normalización.
- **Atributos:** fuente (parser, formulario, integración), método de captura, valor crudo, timestamp, nivel de fiabilidad declarado por la propia fuente si aplica (p. ej. un parser puede marcar una lectura como ambigua).
- **Ciclo de vida:** se crea en el momento de la ingesta; nunca se modifica después — es un registro histórico de "esto es lo que se leyó". Puede ser sustituida por una Observation posterior (una nueva lectura, un DXF corregido), pero la anterior no se borra.
- **Relaciones:** una o más Observations respaldan un Fact (tras validación/normalización); pueden coexistir varias Observations en conflicto sobre el mismo dato, en cuyo caso la resolución de cuál prevalece como Fact es, en sí misma, una decisión trazable.
- **Invariantes:** toda Observation debe declarar su fuente; ninguna Observation se convierte en Fact automáticamente sin pasar por el proceso de aceptación (evita que un dato de baja fiabilidad se trate como hecho verificado sin más).
- **Quién puede crearla:** Ingesta.
- **Quién puede modificarla:** nadie — inmutable tras su creación.
- **Quién solo puede consumirla:** todos los demás actores, principalmente el proceso que construye Facts a partir de ellas.

### 5. Fact

- **Propósito:** el dato aceptado y canónico sobre el que razona el resto del sistema — la superficie de una pieza, su uso, su orientación. Es Nivel 1 de `ARCHITECTURAL_KNOWLEDGE_MAP.md` por definición.
- **Atributos:** tipo de dato (superficie, uso, geometría, tipología, etc.), valor, Observation(s) que lo respaldan, versión de ProjectState en la que es vigente.
- **Ciclo de vida:** se crea cuando una o más Observations se validan y aceptan. Un Fact nunca se edita in situ — un cambio en el dato produce un nuevo Fact en una nueva versión de ProjectState (mismo principio append-only que ProjectState y Change), preservando el historial completo requerido por el modelo de propagación.
- **Relaciones:** es consumido por Rules (vía Motor de Dominio) para producir Inferences; puede ser sustituido por un Change; puede coexistir con un Unknown para otro dato relacionado que no se conoce.
- **Invariantes:** todo Fact debe estar respaldado por al menos una Observation (no puede existir un Fact sin origen trazable) — con la única excepción de Facts derivados de una Assumption promovida (ver entidad 7), que deben quedar marcados como tales, nunca indistinguibles de un Fact observado.
- **Quién puede crearla:** el proceso de validación (parte de Ingesta) o el Motor de Propagación (cuando un Change lo introduce).
- **Quién puede modificarla:** nadie — solo se sustituye por una versión nueva, nunca se edita.
- **Quién solo puede consumirla:** Motor de Dominio, Motor de Propagación, Motor de Decisión, Curador de Conocimiento, Arquitecto.

### 6. Unknown

- **Propósito:** representa, de forma explícita, un dato que una o más Rules necesitan y que no existe como Fact ni ha sido cubierto por una Assumption. Es el mecanismo central del protocolo de información insuficiente de `DECISION_ENGINE.md` (sección 12) — su función es hacer visible el vacío, nunca dejarlo implícito.
- **Atributos:** qué tipo de dato falta, qué Rule(s)/Domain(s) lo requieren, "apalancamiento de decisión" (cuánto cambiaría la conclusión si este dato se conociera — determina si se pregunta activamente o se puede ignorar con una Assumption de bajo riesgo).
- **Ciclo de vida:** se crea cuando el Motor de Dominio detecta que una Rule no puede evaluarse por falta de un Fact. Se resuelve de dos formas posibles: llega una Observation/Fact real (el vacío se cierra con datos verdaderos), o se promueve a Assumption (el vacío se cubre con una hipótesis declarada). Nunca desaparece silenciosamente sin una de estas dos transiciones explícitas.
- **Relaciones:** referenciado por la(s) Rule(s) que no pudieron evaluarse; puede dar lugar a una Assumption; forma parte de la Evidence de cualquier Inference que dependa, aunque sea indirectamente, de él.
- **Invariantes:** ninguna Rule que dependa de un Unknown puede producir una Inference de confianza "Alta" (violaría el modelo de confianza de `DECISION_ENGINE.md` sección 10); un Unknown nunca se descarta sin dejar rastro de cómo se resolvió.
- **Quién puede crearla:** Motor de Dominio.
- **Quién puede modificarla:** Motor de Decisión (al promoverlo a Assumption) o Ingesta (al resolverlo con datos reales, lo que en la práctica lo cierra y da paso a un Fact nuevo).
- **Quién solo puede consumirla:** Arquitecto, Motor de Propagación.

### 7. Assumption

- **Propósito:** representa una hipótesis razonable adoptada para cubrir un Unknown, siempre marcada como tal, nunca confundible con un Fact. Es la entidad técnica de la categoría "Hipótesis" de `DECISION_ENGINE.md`.
- **Atributos:** el Unknown que cubre, el valor asumido, la justificación de por qué es razonable, el efecto que tiene sobre el nivel de confianza de cualquier Inference que dependa de ella (siempre rebaja a "Media" o "Baja", nunca deja pasar una confianza "Alta" río abajo).
- **Ciclo de vida:** se crea cuando el Motor de Decisión decide cubrir un Unknown de bajo apalancamiento de decisión sin interrumpir el flujo. Se retira (no se edita) en cuanto llega el Fact real que la sustituye — momento que dispara una nueva propagación, porque el valor pudo cambiar la conclusión.
- **Relaciones:** cubre exactamente un Unknown; es consumida por cualquier Rule/Inference que la necesitaba; queda registrada en la Evidence de todo lo que dependió de ella.
- **Invariantes:** una Assumption nunca puede sustituir un dato que sea de alto apalancamiento de decisión sin que el sistema lo haya señalado antes explícitamente al Arquitecto (viola, si no, el protocolo de `DECISION_ENGINE.md` sección 12); toda Inference que dependa de una Assumption debe heredar visiblemente esa dependencia, no solo la confianza rebajada.
- **Quién puede crearla:** Motor de Decisión.
- **Quién puede modificarla:** nadie — se retira y se sustituye por un Fact real, no se edita.
- **Quién solo puede consumirla:** Motor de Dominio, Motor de Propagación, Arquitecto.

---

## C. Entidades de conocimiento normativo y lógico

### 8. Constraint

- **Propósito:** representa un límite o umbral declarativo — un dato, no una lógica — como "ancho mínimo de itinerario accesible: 1,20 m". Separar Constraint de Rule es la pieza técnica que hace posible que `evaluator.py` deje de ser código imperativo y se convierta en una tabla de datos mantenible, exactamente la dirección ya marcada por las tareas 22-24 de `REFACTOR_MASTERPLAN.md`.
- **Atributos:** valor del umbral, unidad, ámbito de aplicación (tipología, comunidad autónoma, zona climática — los parámetros de los que depende), fuente normativa exacta (artículo/decreto), nivel de conocimiento (Nivel 2 normativa verificable, o Nivel 3 buena práctica), vigencia temporal.
- **Ciclo de vida:** se crea y se versiona por el Curador de Conocimiento a medida que se incorpora normativa nueva o cambia una existente. Un Constraint desactualizado no se borra — se marca con fecha de fin de vigencia, para que cualquier evaluación histórica pueda auditarse contra la norma vigente en su momento.
- **Relaciones:** una o más Rules referencian uno o más Constraints; un Constraint pertenece a un Domain.
- **Invariantes:** todo Constraint debe declarar su fuente normativa trazable (principio 4 de `BRAIN_ARCHITECTURE.md`, Parte 4) — un Constraint sin fuente citable no puede activarse en producción; dos Constraints vigentes simultáneamente para el mismo ámbito exacto es una contradicción que debe bloquearse en el momento de creación, no descubrirse en evaluación.
- **Quién puede crearla:** Curador de Conocimiento.
- **Quién puede modificarla:** Curador de Conocimiento (nueva versión con fecha de vigencia, mismo principio append-only).
- **Quién solo puede consumirla:** Motor de Dominio.

### 9. Rule

- **Propósito:** la lógica evaluativa que conecta Facts y Constraints dentro de un Domain y produce una Inference (potencialmente un Problem si detecta incumplimiento).
- **Atributos:** Domain al que pertenece, Constraint(s) que aplica, Facts que requiere como entrada, severidad que produce si se incumple (bloqueante / riesgo variable / recomendable / preferencial, jerarquía de `DECISION_ENGINE.md` sección 3), nivel de conocimiento (1-4).
- **Ciclo de vida:** se crea y versiona por el Curador de Conocimiento. Puede desactivarse (por ejemplo, si se demuestra que nunca se dispara sobre datos reales, como el caso ya documentado de `_is_adjacent` en `TECH_REVIEW.md`) sin eliminarse, para mantener trazabilidad de por qué existió.
- **Relaciones:** pertenece a exactamente un Domain; referencia uno o más Constraints; consume uno o más Facts (o genera un Unknown si falta alguno); produce cero o una Inference por evaluación.
- **Invariantes:** una Rule nunca puede leer Facts de fuera del ámbito declarado de su Domain sin pasar por una dependencia explícita (estructural/condicional/de referencia, ver `CHAIN_REASONING.md` sección 6) — evita el acoplamiento silencioso entre dominios que `BRAIN_ARCHITECTURE.md` prohíbe explícitamente.
- **Quién puede crearla:** Curador de Conocimiento.
- **Quién puede modificarla:** Curador de Conocimiento.
- **Quién solo puede consumirla:** Motor de Dominio.

---

## D. Entidades de conclusión derivada

### 10. Inference

- **Propósito:** la entidad técnica general para "una conclusión derivada mecánicamente de Facts aplicando una Rule" — la categoría "Inferencia" de `DECISION_ENGINE.md`. No toda Inference es un problema: puede ser una clasificación neutra (p. ej. "esta unidad tiene 6 piezas habitables") que otras Rules usan como entrada.
- **Atributos:** Rule que la produjo, Facts consumidos, valor/conclusión resultante, versión de ProjectState en la que es válida.
- **Ciclo de vida:** se genera en cada evaluación del Motor de Dominio; se invalida (no se edita) cuando cualquier Fact del que depende cambia, lo que fuerza su recálculo en la siguiente versión de ProjectState.
- **Relaciones:** puede ser consumida como entrada por otra Rule de un Domain distinto (vía dependencia de referencia); puede especializarse como Problem.
- **Invariantes:** una Inference siempre es reproducible determinísticamente a partir de los mismos Facts y la misma Rule — si no lo es, no es una Inference válida, es una Recommendation (que sí incorpora juicio, ver entidad 12).
- **Quién puede crearla:** Motor de Dominio.
- **Quién puede modificarla:** nadie — se recalcula, no se edita.
- **Quién solo puede consumirla:** Motor de Propagación, Motor de Decisión, Arquitecto.

### 11. Problem

- **Propósito:** especialización de Inference que representa específicamente un incumplimiento — el equivalente conceptual al `IssueReport` que ya existe en el sistema actual, pero ahora como conclusión formalmente derivada de una Rule y un Constraint, no de lógica imperativa dispersa.
- **Atributos:** todos los de Inference, más: severidad (heredada de la Rule), Confidence calculada, resumen explicable para el Arquitecto.
- **Ciclo de vida:** nace cuando una Rule detecta incumplimiento; se resuelve (deja de existir en la versión vigente) cuando un Change posterior corrige el Fact que lo causaba, o se marca como "aceptado con justificación" si el Arquitecto decide no corregirlo (una Decision explícita, no una desaparición silenciosa).
- **Relaciones:** referenciado por Conflict (cuando entra en tensión con otro Problem o una Preference); origen habitual de un ChainEffect cuando su aparición es consecuencia de un Change en otro dominio.
- **Invariantes:** todo Problem debe estar vinculado a exactamente una Rule y un Domain — nunca un Problem "suelto" sin lógica que lo sustente; un Problem bloqueante nunca puede quedar oculto o agregado en un promedio con Problems de menor severidad (principio de `BRAIN_ARCHITECTURE.md` Parte 1.8 de mantener capas separadas).
- **Quién puede crearla:** Motor de Dominio.
- **Quién puede modificarla:** nadie directamente — cambia de estado (activo/resuelto/aceptado) mediante Change o Decision, nunca por edición directa de su contenido.
- **Quién solo puede consumirla:** Motor de Propagación, Motor de Decisión, Arquitecto.

### 12. Recommendation

- **Propósito:** una propuesta de acción generada por el Motor de Decisión, no por una Rule — incorpora comparación entre Alternatives y juicio, no es determinística de la misma forma que una Inference.
- **Atributos:** Alternative(s) que propone, Conflict o Problem que atiende, Confidence calculada, Evidence completa, Explanation asociada.
- **Ciclo de vida:** se genera al final del flujo de decisión de `DECISION_ENGINE.md`; queda archivada (no se borra) tanto si el Arquitecto la acepta como si la descarta — ambos desenlaces son conocimiento útil a futuro.
- **Relaciones:** referencia una o más Alternatives comparadas; referencia el Conflict o Problem que motivó su generación; da lugar a una Decision cuando el Arquitecto responde.
- **Invariantes:** una Recommendation nunca se presenta sin Evidence adjunta — no puede existir una recomendación "porque sí"; una Recommendation nunca es obligatoria (el Arquitecto siempre puede elegir una Alternative distinta o ninguna).
- **Quién puede crearla:** Motor de Decisión.
- **Quién puede modificarla:** nadie — es un registro histórico de lo que se propuso en su momento.
- **Quién solo puede consumirla:** Arquitecto.

### 13. Preference

- **Propósito:** una elección declarada por el Arquitecto (en nombre propio o transmitiendo la del Cliente), no derivada de ningún análisis técnico — la categoría "Preferencia" de `DECISION_ENGINE.md`.
- **Atributos:** ámbito al que aplica (qué tipo de conflicto o dimensión afecta), dirección de la preferencia, si proviene del Cliente o del Arquitecto directamente, alcance temporal (¿aplica solo a esta decisión o a todo el proyecto?).
- **Ciclo de vida:** se crea cuando se declara explícitamente; puede revocarse o sustituirse por una nueva Preference en cualquier momento — nunca se infiere silenciosamente a partir del comportamiento pasado sin confirmación expresa.
- **Relaciones:** consumida por el Motor de Decisión únicamente como criterio de desempate dentro del espacio ya filtrado por lo bloqueante (nunca puede anular un Problem bloqueante, invariante compartida con la entidad Conflict).
- **Invariantes:** una Preference nunca puede alterar un Fact ni una Inference; si una Preference entra en conflicto directo con un Problem bloqueante, el sistema debe rechazarla explícitamente, nunca aplicarla silenciosamente relajando la restricción (invariante central de `DECISION_ENGINE.md` sección 9).
- **Quién puede crearla:** Arquitecto.
- **Quién puede modificarla:** Arquitecto (revocación/sustitución explícita).
- **Quién solo puede consumirla:** Motor de Decisión.

---

## E. Entidades de propagación y conflicto

### 14. ChainEffect

- **Propósito:** representa un salto (hop) de propagación tal como lo define `CHAIN_REASONING.md` — el vínculo entre un Change o Fact alterado en un Domain y la Inference/Problem nuevo que aparece en otro Domain como consecuencia.
- **Atributos:** Domain de origen, Domain de destino, tipo de efecto (inmediato / indirecto / acumulativo, `CHAIN_REASONING.md` sección 4), nivel de impacto (Local → Urbanístico, sección 9), Change o conjunto de Changes que lo originó.
- **Ciclo de vida:** se crea durante la ejecución del Motor de Propagación, en cada salto de la cadena; es inmutable una vez calculado — si el Fact de origen cambia de nuevo, se genera un nuevo ChainEffect, no se edita el anterior.
- **Relaciones:** encadena Inferences/Problems de distintos Domains; varios ChainEffects consecutivos componen la Evidence de propagación de un Conflict o Recommendation.
- **Invariantes:** un ChainEffect nunca puede apuntar de una capa superior a una inferior salvo hacia el Domain 12 (mismo principio del grafo acíclico de `BRAIN_ARCHITECTURE.md`); una cadena de ChainEffects que supere un número de saltos inusualmente alto sin alcanzar un punto fijo debe marcarse para revisión, no presentarse sin más (salvaguarda de `CHAIN_REASONING.md` sección 8).
- **Quién puede crearla:** Motor de Propagación.
- **Quién puede modificarla:** nadie — inmutable.
- **Quién solo puede consumirla:** Motor de Decisión, Arquitecto.

### 15. Conflict

- **Propósito:** representa la tensión entre dos o más Problems (o un Problem y una Preference) que no pueden resolverse simultáneamente al mismo nivel — la entidad técnica central de `DECISION_ENGINE.md`.
- **Atributos:** tipo de conflicto (los 5 tipos de `DECISION_ENGINE.md` sección 2), Problems/Preferences implicados, nivel de prioridad calculado (sección 3), estado (abierto / resuelto por Decision / expuesto sin resolución posible — caso del Tipo 5).
- **Ciclo de vida:** se crea cuando el Motor de Decisión detecta, vía propagación o escaneo proactivo del estado actual, que dos conclusiones están en tensión estructural; se cierra cuando una Decision lo resuelve, o queda permanentemente abierto y documentado si es de Tipo 5 (discrepancia legítima de criterio) sin forzar una resolución artificial.
- **Relaciones:** referencia los Problems/Preferences en tensión; da lugar a una o más Alternatives; su resolución genera una Decision.
- **Invariantes:** un Conflict nunca se resuelve automáticamente si involucra criterios de Nivel 4 en ambos lados — solo se expone (invariante compartida con el principio de `CHAIN_REASONING.md` sección 8 sobre no auto-resolver ciclos de razonamiento); un Conflict que involucra un Problem bloqueante nunca puede cerrarse aceptando una Preference que lo ignore.
- **Quién puede crearla:** Motor de Decisión.
- **Quién puede modificarla:** Motor de Decisión (cambio de estado únicamente, nunca de los Problems que contiene).
- **Quién solo puede consumirla:** Arquitecto.

### 16. Alternative

- **Propósito:** un candidato concreto de resolución para un Conflict (o para un Problem aislado sin conflicto, cuando existe más de una forma válida de corregirlo).
- **Atributos:** Change(s) que propondría, Problems nuevos que introduciría (calculado re-ejecutando el Motor de Propagación sobre el estado hipotético), nivel de reversibilidad, alineación con Preferences vigentes.
- **Ciclo de vida:** se genera durante la resolución de un Conflict; queda archivada tanto si se elige como si se descarta — el conjunto completo de alternativas consideradas es tan importante de conservar como la elegida, para que la comparación (sección 7 de `DECISION_ENGINE.md`) sea siempre auditable después.
- **Relaciones:** pertenece a un Conflict o Problem; puede ser referenciada por una Recommendation; si se acepta, da lugar a un Change real y a una Decision.
- **Invariantes:** ninguna Alternative se presenta sin haber sido re-evaluada por el Motor de Propagación — una alternativa no verificada no es una Alternative válida (principio 5 de `DECISION_ENGINE.md` sección 6); cuando un Conflict tiene varias soluciones igualmente válidas (`DECISION_ENGINE.md` sección 5), deben existir como mínimo dos Alternatives registradas, nunca solo una.
- **Quién puede crearla:** Motor de Decisión.
- **Quién puede modificarla:** nadie — inmutable una vez generada y evaluada.
- **Quién solo puede consumirla:** Arquitecto.

### 17. Decision

- **Propósito:** el registro final e histórico de qué Alternative aceptó el Arquitecto (o si introdujo una distinta de las propuestas) para resolver un Conflict o Problem — la memoria institucional de la que se alimentan, con el tiempo, los Dominios 12 y 13 de `BRAIN_ARCHITECTURE.md`.
- **Atributos:** Alternative elegida (o descripción de la elección propia si difiere de todas las propuestas), justificación del Arquitecto si la aportó, si coincidió o no con la Recommendation del sistema, timestamp.
- **Ciclo de vida:** se crea en el momento en que el Arquitecto resuelve un Conflict o Problem; es permanente e inmutable — es, literalmente, el historial profesional de decisiones del proyecto.
- **Relaciones:** cierra un Conflict; genera un nuevo Change (que reinicia el ciclo de propagación); es la fuente principal de conocimiento acumulado para futuras Recommendations sobre conflictos similares.
- **Invariantes:** toda Decision que se aparte de la Recommendation del sistema debe registrar la razón si el Arquitecto la proporciona — no es obligatorio que la dé, pero si no la da, debe quedar marcado como "elección sin justificación registrada", nunca inventarse una después.
- **Quién puede crearla:** Arquitecto.
- **Quién puede modificarla:** nadie — inmutable, es el equivalente a una firma profesional.
- **Quién solo puede consumirla:** todos los demás actores, especialmente el proceso que construye conocimiento acumulado para el Dominio 12/13.

---

## F. Entidades de justificación

### 18. Evidence

- **Propósito:** el paquete de razonamiento que sostiene cualquier Inference, Problem, Conflict, Recommendation o Decision — el conjunto trazable de Facts, Rules, Assumptions y ChainEffects que llevaron a una conclusión. Es la estructura de datos que hace posible cumplir, de forma verificable, el requisito de explicabilidad de `CHAIN_REASONING.md` (sección 10) y `DECISION_ENGINE.md` (sección 8).
- **Atributos:** lista ordenada de los elementos que la componen (Facts, Rules, Assumptions, ChainEffects intermedios), con el nivel de conocimiento (1-4) de cada tramo señalado individualmente.
- **Ciclo de vida:** se construye en el mismo momento en que se genera la entidad que justifica (Inference, Problem, Conflict, Recommendation, Decision); es inmutable — si la conclusión cambia, se genera una nueva Evidence junto con la nueva versión de la conclusión.
- **Relaciones:** pertenece siempre a exactamente una entidad de conclusión; da lugar a una o más Explanations (una misma Evidence puede narrarse de formas distintas para audiencias distintas).
- **Invariantes:** ninguna conclusión (Problem, Conflict, Recommendation) puede existir sin Evidence asociada — es la garantía estructural contra la "caja negra"; la Confidence de la conclusión debe ser recalculable exclusivamente a partir de su Evidence, nunca asignada de forma independiente.
- **Quién puede crearla:** el mismo actor que crea la entidad que justifica (Motor de Dominio, Motor de Propagación o Motor de Decisión, según el caso).
- **Quién puede modificarla:** nadie — inmutable.
- **Quién solo puede consumirla:** Arquitecto, y el proceso que genera Explanations.

### 19. Explanation

- **Propósito:** la narrativa en lenguaje comprensible, derivada de una Evidence, pensada para que el Arquitecto la lea y confíe en ella sin tener que reconstruir el razonamiento por su cuenta.
- **Atributos:** Evidence de la que deriva, texto narrativo, nivel de detalle (resumen / completo), tramos marcados por nivel de conocimiento (1-4) para que el Arquitecto sepa qué parte es hecho y qué parte es criterio.
- **Ciclo de vida:** se genera bajo demanda a partir de una Evidence existente; pueden coexistir varias Explanations de la misma Evidence (una versión resumida y otra detallada, por ejemplo) sin que eso implique ninguna inconsistencia, porque ambas derivan de la misma fuente verificable.
- **Relaciones:** deriva siempre de exactamente una Evidence; se adjunta a la Recommendation, Problem o Conflict que la Evidence sostiene.
- **Invariantes:** una Explanation nunca puede afirmar algo que su Evidence no contenga — no hay margen para narrativa "decorativa" que añada certeza no presente en los datos subyacentes; toda Explanation de una conclusión con tramos de Nivel 3-4 debe decirlo explícitamente, nunca presentar un juicio de criterio con el mismo tono de certeza que un hecho verificado.
- **Quién puede crearla:** el proceso de generación de explicaciones (parte del Motor de Decisión o del Motor de Propagación, según qué conclusión narre).
- **Quién puede modificarla:** nadie — se regenera si la Evidence cambia, no se edita.
- **Quién solo puede consumirla:** Arquitecto.

---

## G. Valor derivado

### 20. Confidence (valor derivado, no entidad de identidad propia)

- **Propósito:** expresar cuánto puede confiarse en una Inference, Problem, Conflict, Recommendation o Assumption — siempre como una de tres categorías cualitativas (Alta / Media / Baja), nunca como una cifra numérica que sugiera una precisión que el sistema no tiene (`DECISION_ENGINE.md` sección 10, y el mismo principio que corrigió el percentil fabricado señalado en `PROJECT_AUDIT.md`/`TECH_REVIEW.md`).
- **Atributos:** categoría (Alta/Media/Baja), el tramo específico de la Evidence que determina esa categoría (el eslabón más débil).
- **Ciclo de vida:** no tiene ciclo de vida propio — se recalcula automáticamente cada vez que se genera o invalida la Evidence a la que está adjunta; nunca se fija manualmente por ningún actor.
- **Relaciones:** siempre adjunta a exactamente una Inference, Problem, Conflict, Recommendation o Assumption; nunca existe de forma aislada.
- **Invariantes:** la Confidence de cualquier entidad no puede ser "Alta" si su Evidence incluye algún tramo de Nivel 3-4 o alguna Assumption; no puede calcularse manualmente ni sobrescribirse — es, por diseño, un espejo fiel de la Evidence subyacente.
- **Quién puede crearla:** nadie directamente — se deriva automáticamente al construirse la Evidence.
- **Quién puede modificarla:** nadie — solo cambia si cambia la Evidence de la que depende.
- **Quién solo puede consumirla:** todos los actores.

---

## Flujo completo de datos entre entidades

```
                          ARQUITECTO introduce
                                  │
                                  ▼
                              [Change]
                     (una de las 8 familias, CHAIN_REASONING §1)
                                  │
                                  ▼
              ¿sustituye/añade un dato ya observado?
                                  │
                     ┌────────────┴────────────┐
                     ▼                          ▼
              [Observation]               (dato ya existente
                     │                      se reutiliza)
                     ▼
                  [Fact]  ───────────────► nueva versión de [ProjectState]
                     │
                     ▼
       Motor de Dominio re-evalúa toda [Rule] que consume este Fact
                     │
        ¿faltan Facts que la Rule necesita?
             │                    │
             ▼ sí                 ▼ no
         [Unknown] ──┐            │
             │        │           │
   ¿alto apalancamiento?          │
     │           │                │
     ▼ sí         ▼ no            │
  se pregunta   [Assumption]      │
  al Arquitecto     │             │
                     └─────┬──────┘
                           ▼
                     [Inference]
                    (o, si incumple: [Problem])
                           │
                           ▼
         Motor de Propagación recorre el grafo de Domains
        (dependencias estructurales/condicionales/de referencia)
                           │
                           ▼
                    [ChainEffect]  (inmediato / indirecto / acumulativo)
                           │
                 ¿se repite hasta un punto fijo?
                           │
                           ▼
        ¿dos o más Problems/Preferences quedan en tensión?
                     │                    │
                     ▼ sí                 ▼ no
                [Conflict]        [Problem] queda disponible
                     │             para que el Arquitecto lo
                     ▼             corrija con un nuevo Change
      Motor de Decisión genera [Alternative] × N
      (re-evaluadas de nuevo por Motor de Propagación)
                     │
                     ▼
              se comparan y priorizan
          (jerarquía de 5 criterios, DECISION_ENGINE §3)
                     │
                     ▼
              [Recommendation]
           + [Evidence] + [Explanation] + [Confidence] (derivada)
                     │
                     ▼
       ¿el Arquitecto introduce una [Preference]?
       (solo actúa como desempate dentro de lo no bloqueante)
                     │
                     ▼
                 [Decision]
          (acepta una Alternative, o una propia)
                     │
                     ▼
         genera un nuevo [Change] ──────────────┐
                                                 │
                                    vuelve al principio del flujo
                                  (posibles conflictos de 2º orden)
```

Todo el flujo tiene una propiedad estructural deliberada: **cada flecha corresponde a la creación de una entidad nueva, nunca a la edición de una existente.** Es la misma disciplina append-only aplicada de forma consistente a las veinte entidades del documento, y es, en última instancia, la razón técnica por la que este motor puede crecer durante años sin perder coherencia: nada se sobrescribe, todo cambio deja un rastro verificable, y cualquier conclusión — por antigua que sea — sigue siendo auditable exactamente como se generó.

---

## Principios de coherencia a largo plazo

Cierre de este documento, no una sección nueva de contenido: los cuatro principios que sostienen todo lo anterior y que cualquier implementación futura debe preservar, aunque cambien los detalles concretos de cada entidad con el tiempo.

1. **Append-only en toda entidad con historia** (ProjectState, Fact, Change, Observation, Problem, Decision, Evidence...) — nada se edita in situ; todo cambio es una versión nueva. Es lo que hace posible auditar cualquier conclusión pasada exactamente como se produjo, y es la base técnica de la confianza institucional que persigue `NORTH_STAR_2031.md`.
2. **Separación estricta entre dato (Fact, Constraint) y lógica (Rule)** — es la traducción técnica directa del refactor ya planificado en `REFACTOR_MASTERPLAN.md` (tareas 22-24), y la que permite que el catálogo de Rules crezca a cientos sin que cada una exija tocar código imperativo.
3. **Ninguna entidad de conclusión (Inference, Problem, Conflict, Recommendation, Decision) existe sin Evidence trazable** — la garantía estructural contra la opacidad, y el requisito que convierte "el sistema lo dice" en "el sistema lo demuestra".
4. **La taxonomía de cinco categorías de `DECISION_ENGINE.md` (hecho / inferencia / hipótesis / recomendación / preferencia) está incrustada en el modelo de entidades, no es una convención de presentación** — Fact, Inference, Assumption, Recommendation y Preference son entidades distintas con reglas de creación y modificación distintas; es estructuralmente imposible confundir una con otra sin violar una invariante explícita.
