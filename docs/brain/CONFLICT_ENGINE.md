# CONFLICT_ENGINE.md

**Propósito:** consolidar y completar el modelo de resolución de conflictos — cómo se detectan con precisión los cinco tipos ya tipificados en `DECISION_ENGINE.md`, cómo la jerarquía de prioridad ya fijada se aplica como un procedimiento concreto (no solo como principio), cómo se justifica cada resolución, cómo el sistema evita contradecirse a sí mismo a lo largo del tiempo, y qué hace exactamente en el instante en que dos dominios expertos discrepan. Gran parte del vocabulario ya existe repartido en documentos anteriores — este documento no lo repite, lo une en un solo procedimiento operable. Sin código, como el resto de la serie.

**Referencias obligatorias, asumidas como ya decididas:**
- `DECISION_ENGINE.md` — §2 (los 5 tipos de conflicto), §3 (jerarquía de prioridad de 5 criterios), §9 (una Preference nunca puede anular un Problem bloqueante), §12 (protocolo de información insuficiente). Este documento no redefine ninguno — los convierte en procedimiento.
- `REASONING_ENGINE_SPEC.md` — entidad 13 (Preference), entidad 14 (ChainEffect), entidad 15 (Conflict), entidad 16 (Alternative), entidad 17 (Decision, "memoria institucional").
- `INFERENCE_ENGINE.md` — §6, el Verificador de Coherencia y sus tres criterios de detección de contradicción. Este documento no sustituye ese mecanismo, lo extiende: allí se detecta que algo no encaja; aquí se clasifica en cuál de los cinco tipos de `DECISION_ENGINE.md` §2 encaja, y qué hacer con cada tipo.
- `OBSERVATION_MODEL.md` — §4 ("Conflicto compartido" como criterio de agrupación de Hallazgo) y §5 (el mecanismo de huella basado en identificadores estables), reutilizado aquí en la sección 4 para reconocer conflictos estructuralmente iguales a lo largo del tiempo.
- `EVIDENCE_MODEL.md` y `EXPLANATION_ENGINE.md` §7 — la estructura de Evidence y la regla de narrar ambos lados con el mismo peso; este documento especifica qué contiene, exactamente, la Evidence propia de un Conflict.
- `CHAIN_REASONING.md` — el listado empírico de los 20 efectos de cadena más frecuentes en vivienda residencial, reutilizado en la sección 1 como semilla real del catálogo de tensiones estructurales conocidas entre dominios.

**Actor nuevo, añadido al glosario ya establecido:**
- **Verificador de Precedente** — el proceso que, antes de que una Decision cierre un Conflict, comprueba si ya existe una Decision anterior sobre un Conflict estructuralmente equivalente en el mismo proyecto, y la expone al Arquitecto — nunca la aplica automáticamente. Mismo patrón de gobernanza que el resto de actores de la serie (Compositor de Hechos, Intérprete de Constraints, Motor de Síntesis de Hallazgos, Verificador de Coherencia, Narrador, Estimador): una pieza única, cerrada, compartida entre los 14 dominios.

---

## 0. Principio rector

Dos garantías de "nunca en silencio", una a cada lado del proceso, sostienen todo este documento: **en la detección**, un Conflict de Nivel 4 en ambos lados nunca se resuelve automáticamente, se expone (invariante ya fijada en `REASONING_ENGINE_SPEC.md` entidad 15); **en la resolución**, una Decision nueva nunca contradice tácitamente una Decision anterior sobre el mismo tipo de tensión sin que quede constancia de que se sabía y se decidió distinto de todas formas. La primera evita que el sistema finja certeza donde hay discrepancia legítima; la segunda evita que el sistema, con el tiempo, se convierta en una colección de decisiones que se llevan la contraria entre sí sin que nadie lo note — el mismo riesgo de coherencia a largo plazo que `BRAIN_ARCHITECTURE.md` identificó desde el primer documento de la serie, aplicado aquí al historial de decisiones humanas, no solo al motor.

---

## 1. Cómo se detectan conflictos

El Verificador de Coherencia (`INFERENCE_ENGINE.md` §6) ya hace el primer barrido — detecta que dos Inferences vigentes no encajan. Lo que este documento añade es la **clasificación**: en cuál de los cinco tipos de `DECISION_ENGINE.md` §2 encaja la tensión detectada, porque cada tipo exige un tratamiento distinto y ninguno se puede tratar como "conflicto genérico":

| Tipo (`DECISION_ENGINE.md` §2) | Qué dispara su detección |
|---|---|
| **1. Normativo-normativo** | Dos Problems bloqueantes, mismo ámbito, cuya satisfacción simultánea es geométrica o lógicamente imposible — es, literalmente, el criterio "contradicción directa" ya definido en `INFERENCE_ENGINE.md` §6, clasificado como Tipo 1 cuando ambos lados son Nivel 1-2 |
| **2. Normativa-vs-diseño** | Un Problem (incumplimiento Nivel 1-2) y un Hallazgo de recomendación de calidad (Nivel 3-4, `OBSERVATION_MODEL.md` §3) sobre el mismo ámbito, cuyas correcciones son mutuamente excluyentes |
| **3. Negocio/cliente-vs-técnica** | Una Preference cuya dirección declarada se opone a un Problem o Constraint activo — se detecta por comparación directa entre la dirección de la Preference y la condición del Constraint, sin necesidad de propagación |
| **4. Aprovechamiento-vs-bienestar** | Dos Inferences (no necesariamente Problems) de una pareja de dominios ya catalogada como de **tensión estructural conocida** — catálogo cerrado, gobernado por el Curador de Conocimiento, con el listado empírico de 20 efectos de cadena de `CHAIN_REASONING.md` como semilla real, no un ejercicio teórico — que apuntan en direcciones opuestas sobre la misma variable de diseño |
| **5. Discrepancia legítima de criterio** | Dos Inferences de Nivel 4, dominios distintos, mismo ámbito, conclusiones incompatibles, que **sobreviven completos los cinco criterios de la jerarquía de prioridad** (sección 2) sin que ninguno las desempate |

El Tipo 5 no se detecta de forma independiente — es lo que queda cuando una "contradicción directa" del Verificador de Coherencia atraviesa la jerarquía de prioridad entera sin resolverse. Los Tipos 1-4 sí se pueden detectar de forma más temprana y específica, cada uno con su propio disparador, precisamente para que el sistema pueda tratarlos de forma distinta desde el principio en vez de esperar a que los cinco criterios de prioridad los agoten a todos por igual.

---

## 2. Cómo se priorizan

La jerarquía de 5 criterios de `DECISION_ENGINE.md` §3 (nivel de bloqueo > nivel de impacto > reversibilidad > confianza del conocimiento > preferencia) se aplica como un **filtro secuencial**, no como una fórmula que combina los cinco a la vez — en cada nivel, se comprueba si ya hay un lado que gana; si hay empate, se pasa al criterio siguiente; solo si los cinco criterios empatan, el Conflict pasa a ser, formalmente, Tipo 5:

1. **Nivel de bloqueo** — ¿algún lado es bloqueante y el otro no? Gana el bloqueante, sin pasar a los criterios siguientes. Si ambos son bloqueantes (o ninguno lo es), empate, se pasa al siguiente criterio.
2. **Nivel de impacto** (Local→Urbanístico, `CHAIN_REASONING.md`) — ¿algún lado tiene un impacto de escala mayor? Gana el de mayor escala. Empate si son iguales.
3. **Reversibilidad** — ¿corregir un lado es más difícil de deshacer que corregir el otro? Gana el criterio que preserva la opción más reversible. Empate si ambos son igual de (ir)reversibles.
4. **Confianza del conocimiento** — ¿un lado tiene fuerza de Evidence (`EVIDENCE_MODEL.md` §3) mayor que el otro? Gana el de mayor fuerza. Empate si ambos tienen la misma fuerza.
5. **Preferencia** — solo entra aquí, y solo si los cuatro criterios anteriores empataron; nunca antes, nunca por encima de un empate real en los niveles 1-4 (invariante ya fijada en `DECISION_ENGINE.md` §9).

**Si los cinco criterios empatan, el Conflict es Tipo 5 y se expone tal cual — nunca se rompe el empate por un sexto criterio no declarado.** Esta última frase es la salvaguarda central de esta sección: el riesgo real, bajo presión de que "el sistema dé una respuesta", es que una implementación futura rompa un empate genuino con algo que parezca neutral pero no lo es — el orden en que se registraron las Rules, el número de Domain, el orden alfabético del id — cualquiera de esos sería un desempate silencioso disfrazado de determinismo técnico, exactamente el mismo patrón de default oculto que el resto de la serie ya ha nombrado varias veces bajo otras formas. Un empate en los cinco criterios se queda en Tipo 5, sin excepción.

---

## 3. Cómo se justifican

La Evidence de un Conflict (`EVIDENCE_MODEL.md`) no es una Evidence nueva construida desde cero — es la **unión de la Evidence completa de ambos lados**, más un elemento que solo un Conflict necesita: la **traza de desempate**, el registro explícito de qué ocurrió en cada uno de los cinco niveles de la sección 2 — no solo cuál criterio ganó al final, sino si cada nivel anterior empató o no. Sin este registro completo, una Explanation no podría cumplir la regla ya fijada en `EXPLANATION_ENGINE.md` §7 de citar "qué criterio de la jerarquía se está aplicando" con precisión — citar solo el criterio ganador, sin mostrar que los anteriores empataron de verdad, dejaría al Arquitecto sin forma de verificar que el desempate fue legítimo y no arbitrario.

Para un Conflict de Tipo 5, la traza de desempate es, en sí misma, la prueba de que la discrepancia es legítima: muestra, nivel por nivel, que ningún criterio objetivo pudo decidir — es la Evidence de por qué el sistema no eligió, no una Evidence incompleta de una elección que falta.

---

## 4. Cómo se evitan decisiones inconsistentes

Esta es la pieza que ningún documento anterior de la serie cubría todavía: qué pasa cuando un Conflict estructuralmente igual a uno ya decidido vuelve a aparecer — en otra unidad del mismo proyecto, o en una revisión posterior tras un Change.

El Verificador de Precedente reconoce esa igualdad estructural con el mismo mecanismo de **huella** ya definido en `OBSERVATION_MODEL.md` §5 para Hallazgo, aplicado aquí a Conflict: una huella construida a partir de identificadores estables — el tipo de conflicto (sección 1), los Domains en tensión, y el tipo de Constraint/criterio concreto que se enfrentó — nunca de los ids de instancia de los Problems/Inferences que lo originaron en cada ocasión.

Antes de que una Decision cierre un Conflict, el Verificador de Precedente busca, dentro del mismo proyecto, si existe una Decision anterior sobre un Conflict con la misma huella. Si la encuentra:

- La expone al Arquitecto como contexto — "la última vez que esta tensión apareció en este proyecto (unidad X), se decidió Y" — nunca la aplica automáticamente ni la sugiere como la única opción válida.
- Si la Decision nueva **coincide** con el precedente, no hace falta nada más — es consistencia confirmada.
- Si la Decision nueva **diverge** del precedente, esa divergencia se registra explícitamente como tal — no se bloquea (el Arquitecto siempre puede decidir distinto, cada situación puede tener matices reales que la huella no captura), pero la Decision queda marcada como "diverge de precedente" junto con la justificación si el Arquitecto la da, o como "diverge sin justificación registrada" si no la da — mismo tratamiento, extendido a este caso nuevo, que `REASONING_ENGINE_SPEC.md` entidad 17 ya exige cuando una Decision se aparta de la Recommendation del sistema.

**Este mecanismo se limita, deliberadamente, al proyecto actual.** Extenderlo a un histórico de decisiones a través de múltiples proyectos repetiría exactamente el error ya señalado en `PROJECT_AUDIT.md`/`TECH_REVIEW.md` con `TIPOLOGIA_BENCHMARKS`: presentar un patrón agregado como si fuera conocimiento fiable antes de que exista un dataset real que lo respalde. El precedente entre proyectos es, precisamente, el tipo de conocimiento que `BRAIN_ARCHITECTURE.md` reserva para el Dominio 13 (Riesgo de Visado) y el Dominio 14 (Benchmark de Mercado) una vez existan datos acumulados reales — no algo que este mecanismo deba adelantar por su cuenta.

---

## 5. Cómo intervenir cuando dos dominios llegan a conclusiones incompatibles

El procedimiento completo, en el momento exacto en que ocurre, consolidando lo ya fijado en documentos anteriores en una sola secuencia operable:

1. **Suspensión de composición corriente abajo.** En cuanto el Verificador de Coherencia detecta la incompatibilidad, cualquier Inference compuesta que consumiera alguno de los dos lados en tensión deja de producirse con normalidad — pasa a "no evaluable hasta que el Conflict se resuelva" (regla ya fijada en `INFERENCE_ENGINE.md` §6, "contradicción por composición sobre conflicto no resuelto"). Nunca se sigue construyendo sobre una base que ya se sabe inconsistente.
2. **Clasificación.** Se determina cuál de los cinco tipos de la sección 1 corresponde, y se materializa el Conflict con esa clasificación explícita — nunca como "conflicto genérico" sin tipo.
3. **Aplicación de la jerarquía de prioridad.** Se ejecuta el filtro secuencial de la sección 2 hasta que un criterio decida, o hasta agotar los cinco (Tipo 5).
4. **Generación de Alternatives**, si el Conflict no es de Tipo 5 o si, aun siéndolo, existen formas distintas de proceder — cada Alternative re-verificada por el Motor de Propagación antes de presentarse (invariante ya fijada en `REASONING_ENGINE_SPEC.md` entidad 16: ninguna Alternative se presenta sin haber sido re-evaluada).
5. **Verificación de precedente** (sección 4) sobre el conjunto de Alternatives y la resolución que se perfila.
6. **Presentación al Arquitecto** vía Explanation, narrando ambos lados con el mismo peso y citando el criterio de desempate exacto (`EXPLANATION_ENGINE.md` §7).
7. **Cierre.** El Arquitecto emite una Decision — que puede coincidir con la Recommendation del sistema, apartarse de ella con justificación, apartarse sin justificación (registrado como tal), o, si el Conflict es Tipo 5 sin que ninguna Alternative resuelva la discrepancia de fondo, dejarlo explícitamente abierto y documentado, sin forzar un cierre artificial.

Ningún paso de esta secuencia es nuevo — cada uno ya estaba fijado en algún documento anterior de la serie. Lo que faltaba, y es lo que aporta esta sección, es el orden concreto en que ocurren y la certeza de que ninguno se salta bajo presión de "resolver rápido": en particular, el paso 1 (suspender composición corriente abajo) es el que con más facilidad se omitiría en una implementación apurada, porque su ausencia no produce un error visible — produce, silenciosamente, conclusiones construidas sobre una contradicción no resuelta, exactamente el resultado que todo este documento existe para impedir.

---

## Cierre

Dos atajos son, con diferencia, los más fáciles de tomar bajo presión de plazo, y ambos están nombrados explícitamente en este documento para que no se tomen sin que quede constancia: romper un empate de los cinco criterios de prioridad con un criterio no declarado (sección 2), y dejar que una Decision nueva contradiga una anterior sin registrar que se sabía y se decidió distinto (sección 4). Ninguno de los dos rompe nada de forma visible en el momento en que ocurre — los dos degradan, silenciosamente, la coherencia de largo plazo que toda la serie ha defendido desde `BRAIN_ARCHITECTURE.md`. La defensa, como en cada documento anterior, no es una propiedad automática del modelo — es la disciplina de nunca tomarlos.
