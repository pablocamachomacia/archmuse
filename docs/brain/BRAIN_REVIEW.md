# BRAIN_REVIEW.md

**Propósito:** revisión crítica de arquitecto jefe sobre los 15 documentos de `docs/brain/` — no un resumen de lo que dicen (ya está escrito, no hace falta repetirlo), sino un juicio sobre qué de todo eso sostiene el peso que le hemos puesto encima, qué es diseño prematuro, qué contradice o duplica a otra parte de la serie, y qué hacer primero. Se lee `BRAIN_ARCHITECTURE.md`, `ARCHITECTURAL_KNOWLEDGE_MAP.md`, `CHAIN_REASONING.md`, `DECISION_ENGINE.md`, `REASONING_ENGINE_SPEC.md`, los 15 de `docs/brain/`, `PRD-001-Core-Reasoning-Engine.md` y `REFACTOR_MASTERPLAN.md` como un solo cuerpo de trabajo, no como documentos aislados.

**Postura de este documento, dicha una sola vez para no repetirla en cada sección:** la serie de 15 documentos es, en su inmensa mayoría, diseño de altísima calidad — internamente coherente, autocrítico, con una disciplina de "nunca silencio" que rara vez se ve en documentos de arquitectura. Ese no es el problema. El problema es de **secuencia**: hemos diseñado, con un detalle asombroso, un sistema completo de 20+ entidades y 9 procesos de gobernanza, mientras el único plan de implementación que existe (`PRD-001`, todavía sin aprobar) cubre **2 de 14 dominios y 8 de 20 entidades**, y explícitamente pospone diez de ellas indefinidamente. La serie entera se lee, hoy, como los planos completos de un edificio de 14 plantas dibujados hasta el último detalle de instalaciones antes de haber vaciado los cimientos. Eso no invalida los planos — pero si alguien empieza a construir la planta 9 antes que la 1, el problema no serán los planos.

---

## 1. Contradicciones entre documentos

### 1.1 `REASONING_ENGINE_SPEC.md` ya no es la especificación canónica que dice ser

`REASONING_ENGINE_SPEC.md` fija, en su sección 0, "un modelo de **19 entidades de pleno derecho** más 1 valor derivado (Confidence)" y define Constraint (entidad 8) y Rule (entidad 9) con un reparto explícito: Constraint es el umbral (dato), Rule es "la lógica evaluativa". `CONSTRAINT_MODEL.md` §2 reescribe ese reparto sin ambigüedad: *"toda la lógica evaluable de una restricción — condiciones incluidas — se expresa dentro del Constraint como datos [...] Rule, en este modelo, deja de portar lógica propia: pasa a ser el vínculo formal entre un Domain y el conjunto de Constraints"*. Esto está bien argumentado y es, con toda probabilidad, la decisión correcta — pero `REASONING_ENGINE_SPEC.md` nunca se actualizó para reflejarlo. Un lector que abra hoy `REASONING_ENGINE_SPEC.md` (el documento que todos los demás citan como "ya decidido y no vuelto a discutir") se lleva un modelo de Rule que tres documentos después queda obsoleto sin ninguna nota que lo señale en el propio spec.

El mismo problema, más grave, con el recuento de entidades: `OBSERVATION_MODEL.md` añade Hallazgo, `PROJECT_MEMORY.md` añade Sesión, `GLOBAL_ASSESSMENT.md` añade Juicio Global. Ninguna de las tres está en las "19 entidades" que `REASONING_ENGINE_SPEC.md` declara como el modelo completo. Hoy no existe ningún documento único que liste el catálogo de entidades realmente vigente — solo se puede reconstruir leyendo los 15 documentos en orden y llevando la cuenta a mano. Para un sistema cuyo principio rector es "todo dato trazable hasta su origen", que la propia especificación de entidades no sea trazable hasta su estado actual es una grieta real, no cosmética.

**Corrección recomendada:** antes de escribir un solo PRD nuevo sobre esta serie, actualizar `REASONING_ENGINE_SPEC.md` con una fe de erratas fechada (mismo mecanismo append-only que el resto de la serie ya exige para todo lo demás) que reconcilie el reparto Constraint/Rule y añada Hallazgo, Sesión y Juicio Global a la tabla de entidades — o, más barato, un único documento índice (`ENTITY_INDEX.md`) que sí se mantenga actualizado y remita a cada documento fuente.

### 1.2 El "registro interno de calibración" de `INFERENCE_ENGINE.md` es una entidad no gobernada colándose por la puerta que el resto de la serie cierra

`INFERENCE_ENGINE.md` §2.3 introduce, para el eje "probabilística", un valor numérico interno que "puede conservarse en un registro interno de calibración que solo consulta el Curador de Conocimiento". En sí, la intención es correcta (nunca exponerlo). Pero ese registro es, de facto, una entidad con datos, con un propósito y con un consumidor — y no aparece en ningún catálogo cerrado de la serie, no tiene ciclo de vida definido, no tiene invariantes de creación/modificación como las otras 20+. Es exactamente el tipo de "cosa que existe pero no está gobernada" que `FACT_MODEL.md` §12.1 y `CONSTRAINT_MODEL.md` §14 nombran como el riesgo número uno de toda la serie — aquí, el propio documento que advierte del patrón lo comete en una frase.

### 1.3 `Explanation` (entidad 19) no reconoce que ahora también deriva de Hallazgo

`REASONING_ENGINE_SPEC.md` entidad 19 fija que una Explanation "se adjunta a la Recommendation, Problem o Conflict que la Evidence sostiene". `OBSERVATION_MODEL.md` §9 dice, correctamente, que una Explanation ahora también puede generarse "a partir de la Evidence agregada de un Hallazgo". Ninguno de los dos documentos se contradice de forma grave, pero la entidad 19 nunca se amplió para decirlo — otra vez el mismo patrón de 1.1: los documentos nuevos asumen una extensión que el documento fuente no refleja.

---

## 2. Conceptos duplicados

### 2.1 Nueve actores con un nombre propio distinto para el mismo patrón

Compositor de Hechos, Intérprete de Constraints, Motor de Síntesis de Hallazgos, Verificador de Coherencia, Narrador, Estimador, Verificador de Precedente, Consolidador de Sesión y Sintetizador. Cada uno se presenta con el mismo párrafo casi calcado: *"proceso único y compartido entre los 14 dominios [...] mismo patrón de gobernanza que los actores ya nombrados [...] nunca 14 implementaciones distintas"*. Son, en realidad, **una sola idea arquitectónica** — un intérprete central sobre un catálogo cerrado, gobernado, nunca extendido por dominio — aplicada nueve veces y bautizada nueve veces como si fueran piezas conceptualmente distintas. Nombrar el patrón una vez y decir "los siguientes ocho procesos son instancias de este mismo patrón" habría comunicado exactamente lo mismo con una novena parte del texto, y habría dejado más claro, no menos, que es un único principio de diseño y no nueve decisiones separadas que alguien podría relajar una por una.

### 2.2 "Máximo, nunca promedio" reescrito de cero seis veces

Aparece como invariante nueva, con su propia justificación narrada desde el principio, en `BRAIN_ARCHITECTURE.md` (Parte 1.8), `CONSTRAINT_MODEL.md` §6, `OBSERVATION_MODEL.md` §4, `INFERENCE_ENGINE.md` §2.4, `GLOBAL_ASSESSMENT.md` §2 y §3. Es la misma regla aplicada a: severidad de Problem, severidad de Hallazgo, carácter bloqueante de Inference compuesta, selección de qué citar en el Juicio Global. Repetirla como refuerzo retórico está bien; el problema real es que **no hay un único lugar de verdad para la regla** — si algún día cambia (por ejemplo, se decide que ciertas severidades sí pueden matizarse por contexto), hay que encontrar y editar seis sitios, cada uno con su propia redacción, en vez de una regla citada por referencia desde seis sitios.

### 2.3 "Nunca fabricar precisión / TIPOLOGIA_BENCHMARKS" contado de nuevo al menos ocho veces

El mismo relato de origen (el percentil fabricado, `PROJECT_AUDIT.md`/`TECH_REVIEW.md`) se usa como justificación completa en `DECISION_ENGINE.md` §10, `REASONING_ENGINE_SPEC.md` entidad 20, `FACT_MODEL.md`, `CONSTRAINT_MODEL.md` §6, `INFERENCE_ENGINE.md` §2.3 y cierre, `EVIDENCE_MODEL.md` §9, `UNCERTAINTY_MODEL.md` (todo el documento), `GLOBAL_ASSESSMENT.md` cierre. Mismo diagnóstico que 2.2: la historia es potente la primera vez, y a partir de la tercera repetición deja de añadir información — sustituirla por una referencia a un único documento (`BRAIN_PRINCIPLES.md` §10, que ya la cita formalmente) habría sido más disciplinado con el propio principio de "un solo lugar de verdad" que la serie predica en cada documento de datos.

---

## 3. Entidades redundantes

### 3.1 Hallazgo (`OBSERVATION_MODEL.md`) resuelve un problema que hoy no existe

El propio documento justifica Hallazgo con tres problemas de escala: redundancia percibida entre dominios, inestabilidad entre versiones, ruido de repetición exacta. Los tres son reales — **a la escala de 14 dominios y miles de reglas**. Hoy el sistema tiene, en el mejor de los casos, 2 dominios activos (`PRD-001`) y produce del orden de decenas de `IssueReport`, no miles. Construir el motor de síntesis, deduplicación por huella y ciclo de vida de 7 estados de Hallazgo antes de que exista el problema que resuelve es exactamente la definición de sobreingeniería. No es una entidad mal diseñada — es una entidad diseñada dos o tres años antes de que haga falta.

### 3.2 Sesión (`PROJECT_MEMORY.md`) depende de una capacidad que `PRD-001` excluye explícitamente

`PRD-001`, sección "NO IMPLEMENTAR TODAVÍA": *"Change y el modelo de versionado append-only completo de ProjectState [...] este MVP analiza un DXF de una sola vez (snapshot único), no una sesión de edición iterativa"*. Sesión es, literalmente, la unidad que agrupa Changes iterativos. El documento entero (`PROJECT_MEMORY.md`) diseña el comportamiento de una entidad cuyo prerrequisito (edición iterativa real) el propio plan de implementación aprobable pospone sin fecha. No hay nada que corregir en el diseño — hay que dejar de tratarlo como algo a construir pronto.

### 3.3 Juicio Global (`GLOBAL_ASSESSMENT.md`) diseñado para una escala dos órdenes de magnitud mayor que la actual

El documento se abre citando "potencialmente cientos de Hallazgos, decenas de Conflicts". El sistema real, hoy, sobre `ejemplo.dxf`, produce del orden de una a dos decenas de incidencias totales entre todos los bloques de `evaluator.py`. El mecanismo de síntesis con selección/agregación/navegación de tres niveles que este documento diseña es correcto para el problema que describe — pero ese problema no existe todavía y, con el ritmo real de expansión de dominios de `PRD-001` (2 dominios reales, ampliación gradual), tardará años en existir, si es que el producto llega a esa escala de hallazgos por proyecto.

### 3.4 Estimador vs. Compositor de Hechos: separación defendible pero de bajo ROI inmediato

`UNCERTAINTY_MODEL.md` justifica bien por qué Estimador tiene que ser un actor distinto del Compositor de Hechos (exacto vs. aproximado). El argumento es correcto en abstracto. En la práctica, hoy existe **un solo caso real de estimación en todo el código** (`facade_width × 0.25` para superficie de ventana). Mantener dos catálogos gobernados, dos actores con nombre propio y una tabla de techos ampliada para un catálogo de un elemento es más aparato del que ese único caso justifica — no está mal diseñado, está adelantado a su propio contenido.

---

## 4. Decisiones incompatibles

### 4.1 La incompatibilidad real de todo este análisis: la serie de diseño va muy por delante del único plan de implementación existente

`PRD-001-Core-Reasoning-Engine.md` (estado: **borrador, "Decisión: pendiente de revisión por Pablo"**) cubre exactamente 2 dominios y 8 de las 20 entidades de `REASONING_ENGINE_SPEC.md`. Su propia sección "NO IMPLEMENTAR TODAVÍA" excluye explícitamente: `Assumption`, `Change` y el versionado append-only completo, `Confidence` como cálculo, `Explanation`, aprendizaje/memoria institucional, optimización de rendimiento, y — la más importante — *"Motor de decisión completo (Conflict, Alternative, Recommendation, Decision, Preference) [...] hasta que exista más de un dominio real generando hallazgos que puedan entrar en conflicto entre sí"* y *"Propagación entre dominios (ChainEffect) [...] no tiene sentido con solo dos dominios"*.

La serie `docs/brain/` ha diseñado, con enorme profundidad, exactamente esas piezas excluidas: `CONFLICT_ENGINE.md`, `CHAIN_ENGINE.md`, `RECOMMENDATION_ENGINE.md`, `UNCERTAINTY_MODEL.md` (Assumption/Estimation), `EXPLANATION_ENGINE.md`, `PROJECT_MEMORY.md` (Change/Sesión), `GLOBAL_ASSESSMENT.md` y `VIRTUAL_ARCHITECT.md` — más tres entidades nuevas no previstas siquiera en el spec original. El propio `PRD-001` §10 dice, en su propia hoja de ruta condicional: propagación *"solo cuando existan 3-4 dominios reales"*, motor de decisión *"solo después de que la propagación esté validada con datos reales, no en paralelo"*. Bajo el propio criterio de éxito de `PRD-001`, eso está, de forma realista, a más de un año de distancia — condicionado, además, a que el MVP de 2 dominios tenga éxito, cosa que todavía no se ha verificado porque `PRD-001` ni siquiera está aprobado.

Esto no es una contradicción lógica entre dos documentos — es una incompatibilidad de secuencia entre el ritmo del diseño y el ritmo de la validación. No es dañino en sí mismo (el diseño no ha costado una sola línea de código de producto, y `CLAUDE.md` ya impone la regla de PRD antes de código). Pero si no se nombra explícitamente, el riesgo real es que la próxima vez que alguien pida "implementemos ya el motor de conflictos, si ya está diseñado", el diseño exista y la validación de la premisa en la que se apoya (2-3 dominios reales funcionando, con datos reales) no.

### 4.2 `BRAIN_PRINCIPLES.md` se declara constitución con prioridad sobre "cualquier documento futuro" — pero fue escrita después de `PRD-001`, no antes

`BRAIN_PRINCIPLES.md` §31 dice: *"Estos principios tienen prioridad sobre cualquier implementación futura [...] la revisión es el mecanismo permitido, el silencio no lo es."* Es una buena regla. Pero significa que `PRD-001`, ya escrito, nunca fue revisado explícitamente contra los 32 principios para confirmar que no los contradice (no parece contradecirlos — su disciplina de "nunca silencio", "Unknown nunca es un default" es, de hecho, muy fiel a los principios — pero esa verificación explícita no se ha hecho ni se ha registrado en ningún sitio, y el propio Título VIII exige que las revisiones queden documentadas, no asumidas).

---

## 5. Complejidad innecesaria (para la etapa actual)

- **Tres ejes de Fact, cuatro ejes de Inference, seis tipos de tramo de Evidence, cinco patrones de Constraint, seis criterios de agrupación de Hallazgo, cinco criterios secuenciales de Conflict.** Cada uno, leído por separado, está bien justificado. Sumados, son la carga cognitiva que un "Curador de Conocimiento" — rol que hoy no existe, porque hoy solo existe Pablo — tendría que dominar antes de añadir una sola regla nueva al dominio 4. El coste de gobernanza de este modelo es real y no es gratis, ni siquiera en un sistema de un solo desarrollador.
- **Disciplina append-only en absolutamente todo** (Fact, Inference, Hallazgo, Sesión, Constraint, Evidence, Decision, Juicio Global) implica, desde el día uno, infraestructura de event-sourcing completa (id de concepto vs. id de instancia, rangos de vigencia, proyecciones de estado vigente reconstruibles, índices de vigencia). Es la decisión arquitectónica correcta a largo plazo y, a la vez, exactamente el tipo de inversión que `PRD-001` ya decidió no pagar todavía (excluye el versionado completo de `ProjectState`). El diseño y el plan de implementación aprobado no están alineados en cuánto de esto hace falta ahora.
- **`CHAIN_ENGINE.md`** es, con diferencia, el documento con más maquinaria de ingeniería de toda la serie (cola de trabajo, ventana de coalescencia, cancelación por obsolescencia, modo especulativo, detección de ciclos por estado visitado) — diseñado explícitamente para "miles de cambios". El producto real, hoy, analiza un DXF una vez. No hay todavía ningún flujo de edición iterativa que produzca ni una fracción de esa carga.

---

## 6. Partes demasiado abstractas para implementarse tal cual

- **`ARCHITECTURAL_QUALITY.md`, Nivel C** — por diseño explícito, produce con frecuencia "nada automatizado". Es una decisión honesta, no un defecto, pero significa que buena parte del documento no es una especificación de sistema, es una política de cuándo el sistema debe abstenerse. Correcto como principio, no como backlog.
- **`VIRTUAL_ARCHITECT.md`** — especifica el comportamiento de una interfaz conversacional que hoy no existe en el producto (el producto actual es formulario + subida de DXF + informe, sin diálogo). Es, además, el propio documento el que se autodescribe como "el de mayor riesgo real de toda la serie" porque depende de disciplina de un LLM en tiempo real que ningún mecanismo técnico de los otros 14 documentos garantiza — se apoya en "la disciplina de sostenerla turno tras turno", que no es una propiedad verificable por test.
- **`GLOBAL_ASSESSMENT.md`, Juicio Global** — igual que 3.3: diseño maduro para un volumen de hallazgos que no existe.
- **`CHAIN_ENGINE.md`, secciones 4 (agrupación), 5 (cancelación) y 8 (optimización)** — algoritmos correctos para un grafo que hoy, con 2 dominios, es minúsculo. No hay forma de validar empíricamente ninguna de sus afirmaciones de rendimiento porque no hay carga real que las ponga a prueba.
- **El "catálogo de métodos de estimación" y el "catálogo de patrones de transformación" (`RECOMMENDATION_ENGINE.md`)** — catálogos gobernados que hoy tendrían un único miembro real cada uno.

---

## 7. Partes que pueden implementarse inmediatamente

- **`CONSTRAINT_MODEL.md`, secciones 2-3, 6-12** — el diseño más "listo para construir" de toda la serie. Coincide casi exactamente con las tareas 22-24 de `REFACTOR_MASTERPLAN.md`, ya priorizadas y ya planificadas independientemente de esta serie. Es el punto de mayor apalancamiento de todo `docs/brain/`.
- **`FACT_MODEL.md`, secciones 1, 3, 5, 6, 10** (sin el aparato de escala de §11, que puede esperar) — coincide con la Fase 1 de `PRD-001`.
- **El contrato de lectura de cuatro estados** (Fact/Unknown/Assumption/No aplicable de `FACT_MODEL.md` §10), reducido a tres (sin Assumption, que `PRD-001` pospone) — es, literalmente, el mecanismo que cierra el Bug #1, y es la Fase 2 de `PRD-001`.
- **`EVIDENCE_MODEL.md`, limitado a tramos de tipo Fact y Constraint** (2 de los 6 tipos) — coincide con la Fase 4 de `PRD-001` ("un único salto, sin ChainEffect").
- **`BRAIN_PRINCIPLES.md`** — es el único documento de toda la serie que se puede "implementar" hoy mismo sin escribir código: adoptarlo como checklist de revisión para cualquier código nuevo del motor de razonamiento cuesta cero y ya es aplicable desde ahora.
- **`ARCHITECTURAL_QUALITY.md`, Nivel A** — las 5 heurísticas de `spatial_quality.py` ya existen en código; portarlas como Constraint de Nivel 3 con el patrón ya cerrado es trabajo mecánico de bajo riesgo, no diseño nuevo.

---

## 8. Partes que deberían eliminarse (si hubiera que reducir el proyecto un 50%)

Un recorte del 50% no significa borrar la mitad de los documentos al azar — significa cortar por la línea que ya separa lo que `PRD-001` necesita de lo que no, y ser más agresivo de lo que la serie fue consigo misma:

1. **Eliminar como documentos de diseño activo (archivar, no borrar): `VIRTUAL_ARCHITECT.md`, `GLOBAL_ASSESSMENT.md`, `PROJECT_MEMORY.md`.** Ninguno de los tres tiene un prerrequisito construido ni planificado a corto plazo. Si dentro de un año hace falta diseñar la síntesis global o la interfaz conversacional, se rediseñan entonces, con datos reales de cómo se usa el sistema — que hoy no existen y que van a cambiar el diseño más que cualquier razonamiento a priori.
2. **Reducir `CHAIN_ENGINE.md` a su algoritmo básico** (cola de trabajo + poda por alcanzabilidad de `CHAIN_REASONING.md`), eliminando ventana de coalescencia, cancelación por obsolescencia y modo especulativo hasta que exista una sesión de edición iterativa real que los necesite.
3. **Colapsar los nueve actores con nombre propio en un único patrón documentado una vez** ("Intérprete Central sobre Catálogo Cerrado"), citado por cada dominio que lo necesite, en vez de nueve secciones de glosario casi idénticas.
4. **Reducir `RECOMMENDATION_ENGINE.md`** a la sección 0 (el límite "espejo, no diseñador") como principio, posponiendo el resto (generación activa de Alternatives, comparación de N candidatos) hasta que exista el motor de Conflict que lo justifica.
5. **Mantener sin recortar:** `BRAIN_ARCHITECTURE.md`, `ARCHITECTURAL_KNOWLEDGE_MAP.md` (mapa de referencia, coste de mantenimiento bajo, valor alto como documentación de dominio incluso sin motor), `FACT_MODEL.md`, `CONSTRAINT_MODEL.md`, `EVIDENCE_MODEL.md` (los tres directamente alineados con `PRD-001`), y `BRAIN_PRINCIPLES.md` (barato, ya aplicable).

Este recorte no descarta ningún conocimiento — todo queda escrito y archivado, disponible el día que su prerrequisito exista. Lo que evita es que la próxima persona que toque el proyecto (incluido Pablo dentro de seis meses) confunda "está diseñado" con "está listo para construirse ya".

---

## Tabla de madurez, riesgo y prioridad por documento

| Documento | Madurez de diseño (0-100) | Riesgo técnico | Riesgo de sobreingeniería | Prioridad de implementación |
|---|---|---|---|---|
| `BRAIN_ARCHITECTURE.md` | 90 | Bajo | Medio (14 dominios para 2 activos) | Referencia — ya en uso |
| `ARCHITECTURAL_KNOWLEDGE_MAP.md` | 85 | Bajo | Bajo | Referencia — ya en uso |
| `CHAIN_REASONING.md` | 85 | Bajo | Bajo-Medio | Espera (según su propio criterio: 3-4 dominios) |
| `DECISION_ENGINE.md` | 80 | Medio (no validado con datos reales) | Medio | Espera (excluido de `PRD-001`) |
| `REASONING_ENGINE_SPEC.md` | 70 (desactualizado, ver 1.1) | Medio | Bajo | **Corregir antes de reutilizar como referencia** |
| `FACT_MODEL.md` | 90 | Bajo (§1-10) / Medio (§11, no probado a escala) | Medio | **Alta — Fase 1-2 de `PRD-001`** |
| `CONSTRAINT_MODEL.md` | 92 | Bajo | Bajo | **Alta — Fase 3 de `PRD-001`, alineado con tareas 22-24** |
| `OBSERVATION_MODEL.md` (Hallazgo) | 82 | Bajo en diseño | Alto (resuelve un problema inexistente hoy) | Baja / Espera |
| `INFERENCE_ENGINE.md` | 85 | Medio (registro de calibración no gobernado, ver 1.2) | Medio-Alto | Media (básico ya en Fase 4; ejes avanzados esperan) |
| `EVIDENCE_MODEL.md` | 90 | Bajo | Bajo | **Alta — Fase 4 de `PRD-001` (2 de 6 tramos)** |
| `EXPLANATION_ENGINE.md` | 85 | Medio-Alto (disciplina difícil de verificar automáticamente) | Medio | Espera (excluido de `PRD-001`) |
| `UNCERTAINTY_MODEL.md` | 85 | Medio | Alto (4 conceptos + gobernanza para 1 caso real) | Media (Unknown ya en MVP; Estimation/Assumption esperan) |
| `CONFLICT_ENGINE.md` | 85 | Medio (no probado) | Alto para la etapa actual | Espera (condicionado a 3-4 dominios, `PRD-001` §10) |
| `PROJECT_MEMORY.md` | 75 | Bajo | Alto (depende de Change, excluido) | Baja |
| `CHAIN_ENGINE.md` | 90 (técnicamente el más sólido) | Alto si se construye antes de tiempo | Muy alto | Espera — la más pospuesta de las 15 |
| `ARCHITECTURAL_QUALITY.md` | 85 | Bajo | Bajo-Medio | Media (Nivel A ya portable desde `spatial_quality.py`) |
| `RECOMMENDATION_ENGINE.md` | 85 | Medio-Alto (depende de Chain+Conflict) | Alto | Espera (excluido de `PRD-001`) |
| `GLOBAL_ASSESSMENT.md` | 80 | Bajo en diseño | Muy alto (escala especulativa) | Muy baja |
| `VIRTUAL_ARCHITECT.md` | 80 | Alto en la práctica | Muy alto (sin superficie conversacional hoy) | Muy baja |
| `BRAIN_PRINCIPLES.md` | 90 | N/A (no es código) | Bajo | **Alta — adoptable hoy, coste cero** |

---

## Dependencias reales (no las declaradas, las que importan para secuenciar)

```
Capa 0 — Ya validable con PRD-001 tal como está escrito hoy
  FACT_MODEL.md ──► CONSTRAINT_MODEL.md ──► EVIDENCE_MODEL.md (2 de 6 tramos)
       │                                          │
       └──────────────► INFERENCE_ENGINE.md (solo eje directa/positiva/determinística) ──► Problem

Capa 1 — Requiere 3+ dominios reales funcionando (no antes)
  INFERENCE_ENGINE.md (ejes completos) ──► CONFLICT_ENGINE.md ──► CHAIN_REASONING.md/CHAIN_ENGINE.md
       │
  UNCERTAINTY_MODEL.md (Estimation/Assumption completos)
       │
  OBSERVATION_MODEL.md (Hallazgo) — solo tiene sentido con volumen real de detecciones

Capa 2 — Requiere Capa 1 validada con datos reales, no en paralelo (PRD-001 §10, punto 4)
  DECISION_ENGINE.md ──► RECOMMENDATION_ENGINE.md
  EXPLANATION_ENGINE.md — requiere audiencia real (usuario final, hoy no existe en el MVP)

Capa 3 — Requiere edición iterativa real (Change/ProjectState versionado, hoy excluido)
  PROJECT_MEMORY.md (Sesión) ──► GLOBAL_ASSESSMENT.md (Juicio Global)

Capa 4 — Requiere superficie de producto que hoy no existe
  VIRTUAL_ARCHITECT.md
```

La regla de secuenciación es simple y ya está, de hecho, en `PRD-001` §10: **no se empieza una capa hasta que la anterior está validada con datos reales**, no con diseño completo. Toda la serie `docs/brain/` ya diseñó las capas 1-4 — lo que falta no es más diseño, es dejar que la Capa 0 se construya, se use, y falle o funcione antes de tocar nada de lo demás.

---

## Qué debe implementarse primero

Exactamente el alcance de `PRD-001-Core-Reasoning-Engine.md`, sin ampliarlo — que es, además, la razón por la que ese PRD debería aprobarse antes de generar ningún documento de diseño nuevo en esta serie. En términos de `docs/brain/`, lo que hay que construir ya es: `FACT_MODEL.md` (§1-10), `CONSTRAINT_MODEL.md` (completo), `EVIDENCE_MODEL.md` (tramos Fact y Constraint), `INFERENCE_ENGINE.md` reducido a su caso base (directa, positiva, determinística — sin negativa/probabilística/compuesta todavía, porque los 2 dominios del MVP no los necesitan). Nada más de la serie.

## Qué debe esperar

Todo lo demás, explícitamente, hasta que se cumplan las condiciones que la propia serie ya se puso a sí misma: `CONFLICT_ENGINE.md` y `CHAIN_ENGINE.md` hasta 3-4 dominios reales; `RECOMMENDATION_ENGINE.md` y el resto de `DECISION_ENGINE.md` hasta que la propagación esté validada con datos reales; `EXPLANATION_ENGINE.md` hasta que exista un usuario final real del motor nuevo; `PROJECT_MEMORY.md` hasta que exista edición iterativa real; `GLOBAL_ASSESSMENT.md` hasta que el volumen de Hallazgos lo justifique; `VIRTUAL_ARCHITECT.md` hasta que exista, siquiera, una superficie conversacional en el producto.

## Qué eliminarías si tuvieras que reducir el proyecto un 50%

Ver sección 8 completa arriba — en síntesis: archivar `VIRTUAL_ARCHITECT.md`, `GLOBAL_ASSESSMENT.md` y `PROJECT_MEMORY.md`; reducir `CHAIN_ENGINE.md` a su algoritmo básico; colapsar los nueve actores con nombre propio en un único patrón documentado una vez; reducir `RECOMMENDATION_ENGINE.md` a su principio de límite (sección 0). Mantener intactos `BRAIN_ARCHITECTURE.md`, `ARCHITECTURAL_KNOWLEDGE_MAP.md`, `FACT_MODEL.md`, `CONSTRAINT_MODEL.md`, `EVIDENCE_MODEL.md` y `BRAIN_PRINCIPLES.md`.

---

## Roadmap técnico de 12 semanas — por entregables funcionales, no por documento

Cada entrega es algo que Pablo puede ver funcionar o fallar, no un documento leído. Semanas 8-12 están **condicionadas al resultado de la Semana 7** (el propio checkpoint que `PRD-001` ya exige) — si el resultado es "revisar el diseño", el roadmap de esas semanas cambia, y eso es correcto, no un fallo de planificación.

**Semana 1 — Higiene y cimentación.**
Commit de todo el trabajo pendiente (Tarea 1 de `REFACTOR_MASTERPLAN.md`, prerrequisito no negociable de `PRD-001`). Andamiaje del paquete `reasoning/` y adaptador `Room → Observation → Fact`.
*Entregable: un `ProjectState` real generado desde `ejemplo.dxf`, con un `Fact` de superficie/ancho/uso por cada pieza, y `Unknown` explícito donde falte un dato — verificado por test, no por inspección manual.*

**Semana 2 — El Bug #1, resuelto por diseño, no por parche.**
Dominio 2 mínimo: tipología y zona climática como `Fact` fiable o `Unknown` explícito, nunca un valor por defecto.
*Entregable: test de regresión que demuestra, con datos reales, que el motor nuevo no puede reproducir el Bug #1 — el mismo caso que hoy falla en `/api/analizar` produce `Unknown`, nunca un default silencioso.*

**Semanas 3-4 — Restricciones como datos, no como código.**
Portar 3-5 `Constraint` del Dominio 3 (superficie mínima de dormitorio, ancho mínimo de pieza, proporción máxima) como registros declarativos, con el catálogo de 5 patrones de `CONSTRAINT_MODEL.md`.
*Entregable demoable: añadir una restricción dimensional nueva (por ejemplo, un umbral de una comunidad autónoma distinta) editando solo una tabla de datos, sin tocar el motor — demostrado en vivo, no solo afirmado.*

**Semana 5 — De regla a hallazgo explicable.**
`Rule` evaluada sobre `Fact` y `Constraint` produce `Inference`/`Problem` con `Evidence` trazable de un solo salto (Fact → Rule → Problem, sin `ChainEffect`).
*Entregable: la `Evidence` del caso VT6/2 de `ejemplo.dxf` cita correctamente el `Fact` y el `Constraint` reales que lo motivan — verificado, no supuesto.*

**Semana 6 — El motor nuevo frente al espejo.**
Arnés de comparación automática motor nuevo vs. `evaluator.py` (invocado correctamente, sin el Bug #1 de `app.py` de por medio).
*Entregable: informe categorizado (coincide / solo motor nuevo / solo motor antiguo / severidad distinta) sobre `ejemplo.dxf`, con el 100% de las diferencias clasificadas, ninguna sin explicar.*

**Semana 7 — Checkpoint de decisión (Fase 6 de `PRD-001`).**
Sin código nuevo. Documento de resultados con las métricas de éxito de `PRD-001` §8 medidas de verdad.
*Entregable: decisión Go/No-Go de Pablo, documentada — determina si las semanas 8-12 amplían dominios o si primero hay que revisar el diseño.*

**Semanas 8-9 — Ampliar cobertura real (condicionado a Go).**
Portar el resto de reglas dimensionales de `evaluator.py` al Dominio 3; iniciar el Dominio 4 (Iluminación/Ventilación) con el mismo patrón ya validado — el siguiente dominio más maduro y menos ambiguo según `ARCHITECTURAL_KNOWLEDGE_MAP.md`.
*Entregable: paridad total (no parcial) frente a `evaluator.py` en las reglas ya portadas, sobre un corpus de más de un DXF real.*

**Semana 10 — Primera salida legible para un humano.**
`Explanation` mínima: solo bloques Afirmación + Fundamento, nivel Estándar, sin generación de lenguaje natural todavía (contenido determinista puro, sin Narrador/LLM).
*Entregable: Pablo puede leer, en español, por qué un `Problem` concreto existe — sin tener que leer JSON ni código.*

**Semana 11 — Segundo checkpoint: ¿hace falta ya el motor de cadena?**
Con 3 dominios reales activos, evaluar los pares de conflicto conocidos entre ellos (`CHAIN_REASONING.md` §5) contra datos reales — sin construir todavía `CHAIN_ENGINE.md` completo, solo verificar si aparecen de verdad.
*Entregable: informe honesto — "estos conflictos aparecen con esta frecuencia real" o "todavía no hay suficiente superficie para justificar el motor de propagación" — decisión de continuar o esperar, con datos, no con el diseño ya escrito como única entrada.*

**Semana 12 — Cerrar el círculo de gobernanza.**
Corregir `REASONING_ENGINE_SPEC.md` (sección 1.1 de este documento), confirmar o archivar Hallazgo/Sesión/Juicio Global según lo que las 11 semanas anteriores hayan demostrado que hace falta de verdad, y definir el alcance del siguiente PRD con datos reales de uso, no con proyección a 14 dominios.
*Entregable: `REASONING_ENGINE_SPEC.md` actualizado y consistente con el código real; PRD-002 esbozado solo si las semanas 1-11 lo justifican.*

---

## Cierre

Nada de lo señalado en este documento invalida el trabajo de los 15 documentos anteriores — la mayoría del contenido es correcto, y buena parte va a ser exactamente lo que ArchMuse necesite dentro de un año. El riesgo real que este documento existe para nombrar no es de calidad de diseño, es de **secuencia y disciplina de alcance**: la misma disciplina de "nunca silencio" que la serie exige del motor de razonamiento tiene que aplicarse también a cómo se construye el propio motor — nunca fingir que quince documentos de diseño son quince pasos de un roadmap, cuando en realidad son el mapa completo de un territorio del que, hoy, solo se ha caminado la primera manzana. La prueba de que esta serie ha valido la pena no va a ser cuántos documentos existen en `docs/brain/` — va a ser si, dentro de doce semanas, el motor nuevo detecta correctamente lo mismo que `evaluator.py` sobre un DXF real, con `Evidence` trazable y sin un solo valor por defecto silencioso. Todo lo demás puede, y debe, esperar a que eso esté demostrado.
