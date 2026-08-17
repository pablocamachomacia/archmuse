# PRD-001 — Core Reasoning Engine (MVP)

**Estado:** Borrador · **Fecha:** 2026-07-31 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

**Referencias obligatorias de este PRD** (se dan por conocidas y no se repiten aquí): `BRAIN_ARCHITECTURE.md`, `ARCHITECTURAL_KNOWLEDGE_MAP.md`, `CHAIN_REASONING.md`, `DECISION_ENGINE.md`, `REASONING_ENGINE_SPEC.md`, `TECH_REVIEW.md`, `REFACTOR_MASTERPLAN.md`.

**Problema que resuelve:** hasta ahora, todo el trabajo de los últimos cinco documentos ha sido diseño puro — cero líneas de código, cero riesgo. Este PRD es el primer paso que sí toca el proyecto real: construir la porción más pequeña posible del motor de razonamiento descrito en `REASONING_ENGINE_SPEC.md` que demuestre, con datos reales, que el modelo de entidades funciona — sin sustituir todavía nada de lo que ya está en producción.

**Usuario afectado:** en este MVP, ninguno directamente. No hay superficie de usuario final — el motor nuevo corre en paralelo, en modo sombra, sin conectarse a `app.py` ni a la SPA. El "usuario" de este PRD es, literalmente, el propio Pablo como CTO decidiendo si el diseño de `REASONING_ENGINE_SPEC.md` sobrevive el contacto con datos reales.

**Objetivo de negocio:** validar, con el menor coste posible, si el modelo de conocimiento de los cinco documentos anteriores es implementable de verdad o si es necesario revisarlo antes de comprometer meses de desarrollo — es la apuesta estratégica de `NORTH_STAR_2031.md` y `MOAT_ANALYSIS.md` puesta a prueba con el mínimo capital posible.

---

## Prerrequisito no negociable, anterior a la Fase 1

Antes de escribir una sola línea de este motor, debe ejecutarse la **Tarea 1 de `REFACTOR_MASTERPLAN.md`**: commitear `chain_effects.py`, `circulation.py`, `scoring.py`, `spatial_quality.py` y el resto de cambios sin trackear. Construir código nuevo sobre un `git status` sucio es innecesariamente arriesgado y no tiene ninguna dependencia técnica con este PRD — es simplemente higiene que debe resolverse antes, no en paralelo. No se cuenta como una fase de este PRD porque no es trabajo del motor de razonamiento.

---

## 1. Cuál es el alcance mínimo del MVP

El alcance mínimo son **dos dominios, deliberadamente elegidos por ser los de menor ambigüedad**, y solo la porción de `REASONING_ENGINE_SPEC.md` necesaria para producir un `Problem` con `Evidence` trazable — nada de propagación entre dominios, nada de conflictos, nada de decisiones.

- **Dominio 2 (Programa y Tipología), en su versión mínima:** solo lo necesario para que tipología y zona climática existan como `Fact` fiables, nunca por defecto silencioso. No es casualidad que sea el primero: es exactamente el dominio donde vive el Bug #1 de `TECH_REVIEW.md`, y demostrar que el nuevo modelo lo hace bien desde el diseño (un `Rule` sin `Fact` de tipología produce un `Unknown` explícito, nunca un valor por defecto) es la prueba más convincente posible de que el nuevo motor vale la pena.
- **Dominio 3 (Geometría y Dimensionado Habitable), con 3-5 `Constraint` concretos** ya existentes en `evaluator.py` (superficie mínima de dormitorio individual/doble, ancho mínimo de pieza, proporción máxima) portados como datos declarativos, no como lógica nueva inventada.

Explícitamente fuera del MVP: los otros 12 dominios, toda propagación cruzada, todo el motor de decisión.

## 2. Qué partes del evaluador actual NO se sustituyen todavía

Todas. `evaluator.py`, `app.py`, `api_serializer.py`, la SPA — ninguno se toca. El motor nuevo no escribe en ningún flujo que un usuario real pueda ver. Corre en **modo sombra**: se invoca desde un script de comparación aparte (Fase 5), nunca desde `/api/analizar`. Esta es la decisión de diseño que hace que este PRD tenga, en la práctica, riesgo de producción cero — si algo del motor nuevo está mal, ningún cliente lo nota nunca, porque ningún cliente lo toca todavía.

## 3. Qué entidades del modelo se implementarán primero y por qué

De las 20 entidades de `REASONING_ENGINE_SPEC.md`, este MVP implementa exactamente **8**: `ProjectState`, `Observation`, `Fact`, `Unknown`, `Domain`, `Constraint`, `Rule`, `Inference` (incluyendo su especialización `Problem`), y `Evidence`. Son, sin excepción, las entidades de las categorías A (marco), B (conocimiento base) y C (conocimiento normativo/lógico), más `Inference`/`Problem` de la categoría D y `Evidence` de la F.

Por qué exactamente estas y no más: son las únicas necesarias para responder a una sola pregunta de negocio — *"dado un proyecto real, ¿el motor nuevo detecta lo mismo que el motor actual, y puede explicar por qué?"* — sin necesitar todavía decidir nada entre alternativas ni gestionar conflictos. `Change`, `Assumption`, `ChainEffect`, `Conflict`, `Alternative`, `Recommendation`, `Preference`, `Decision`, `Explanation` y `Confidence` no aportan nada a esa pregunta concreta — se listan formalmente en la sección "NO IMPLEMENTAR TODAVÍA".

## 4. Qué flujo completo seguirá un proyecto desde el DXF hasta las recomendaciones

Con honestidad: **este MVP no llega a "recomendaciones".** Llegar hasta ahí requiere el motor de decisión completo (`DECISION_ENGINE.md`), explícitamente fuera de alcance. El flujo real de este MVP es:

```
DXF real (ejemplo.dxf u otro)
        │
        ▼
analyzer/parser.py (SIN TOCAR — se reutiliza tal cual)
        │
        ▼
Adaptador Room → Observation → Fact
(nuevo, en el paquete del motor; solo lee la salida de parser.py)
        │
        ▼
Dominio 2 (mínimo): Rule de tipología/zona_cte
   → Fact de tipología/zona_cte, o Unknown si falta el dato
        │
        ▼
Dominio 3: Rules evaluando Facts de geometría contra Constraints portados
        │
        ▼
Inference / Problem, cada uno con su Evidence
        │
        ▼
Script de comparación (Fase 5): mismo DXF, evaluator.py en paralelo
        │
        ▼
Informe de diffs (Fase 6) — punto de decisión de Pablo, no del motor
```

El punto final de este MVP es un `Problem` con `Evidence`, comparado offline contra `evaluator.py` — no una recomendación mostrada a nadie.

## 5. Qué APIs públicas tendrá el motor

Ninguna API HTTP. En este MVP, "pública" significa únicamente la interfaz del propio paquete Python, consumida por el script de comparación (Fase 5) y por los tests:

- Una función de entrada que recibe la salida ya parseada de `analyzer/parser.py` (los objetos `Room` existentes) más los mismos parámetros de formulario que hoy recibe `evaluator.evaluate_advanced()` (tipología, ciudad/zona, norte_grados) y devuelve el conjunto de `Problem` generados por los dos dominios del MVP.
- Ninguna otra función se considera "pública" todavía — todo lo demás (construcción interna de `Fact`, evaluación de `Rule`) es detalle de implementación no estable, sujeto a cambiar libremente mientras no haya un segundo consumidor real.

No se diseña una API más amplia porque no hay todavía un segundo caso de uso que la necesite — diseñarla ahora sería exactamente el tipo de sobreingeniería que la sección final de este documento existe para evitar.

## 6. Cómo convivirá con `evaluator.py` sin romper compatibilidad

Por aislamiento estructural, no por coordinación cuidadosa: el motor nuevo vive en un paquete propio (p. ej. `reasoning/`, al mismo nivel que `analyzer/`), **solo lee** la salida de `analyzer/parser.py` (nunca importa desde `evaluator.py`, nunca escribe en `analyzer/`), y no aparece en ningún `import` de `app.py`. Cero superficie compartida en escritura significa cero forma posible de que este trabajo rompa nada de lo que ya funciona. La única dependencia real es de lectura: los valores numéricos de los `Constraint` portados en la Fase 3 deben coincidir exactamente con las constantes ya definidas en `evaluator.py` (p. ej. `UMBRALES_TIPOLOGIA`), verificado por test, no por transcripción manual de confianza.

## 7. Cómo compararemos automáticamente los resultados del motor nuevo y del antiguo

Un script de comparación (Fase 5) que ejecuta ambos motores sobre el mismo corpus de DXFs reales disponibles (`ejemplo.dxf` como mínimo) y produce un informe categorizado por pieza y por regla: **coincide**, **solo detectado por el motor nuevo**, **solo detectado por el motor antiguo**, **misma infracción con severidad distinta**.

Un detalle de diseño importante: el script **invoca `evaluator.evaluate_advanced()` directamente con la tipología/zona correctas como parámetros**, sin pasar por `app.py`. Esto evita reproducir el Bug #1 documentado en `TECH_REVIEW.md` en la propia comparación — el motor antiguo se compara en su comportamiento *correcto* (tal como está pensado para funcionar), no en su comportamiento *actual en producción* (que hoy ignora la tipología real por el bug de `app.py`). Comparar contra el comportamiento buggy daría una falsa sensación de acuerdo que no reflejaría nada real.

Toda diferencia encontrada se clasifica explícitamente en el informe como "atribuible a un bug ya conocido de `evaluator.py`" (citando el bug de `TECH_REVIEW.md` que corresponda) o "a investigar" — nunca se deja una diferencia sin explicar.

## 8. Qué métricas determinarán que el MVP es un éxito

- **Cero `Unknown` convertido silenciosamente en valor por defecto** — verificable por test, es la métrica de mayor peso simbólico y técnico del documento, porque es exactamente el patrón del Bug #1.
- **100% de los `Problem` generados llevan `Evidence` no vacía** — invariante de `REASONING_ENGINE_SPEC.md`, verificable automáticamente.
- **Acuerdo total (no parcial) entre motor nuevo y `evaluator.py` correctamente invocado**, para el subconjunto de reglas portadas, sobre el corpus de prueba disponible — cualquier discrepancia debe quedar explicada, no simplemente tolerada como "ruido esperado".
- **Un desarrollador distinto de quien construyó el motor puede añadir un `Constraint` nuevo al Dominio 3 sin tocar el código del motor**, solo añadiendo un dato — valida en la práctica el principio de separación dato/lógica que es la razón de ser de todo este esfuerzo.
- **Las seis fases se completan dentro de su estimación de 1-3 días cada una** — una desviación grande en cualquier fase es, en sí misma, una señal de que el diseño de `REASONING_ENGINE_SPEC.md` era más complejo de lo estimado y debe revisarse antes de seguir invirtiendo.

## 9. Qué riesgos técnicos existen

- **Sobrealcance silencioso** — la tentación más real de todas: mientras se construye, es fácil empezar a implementar `Assumption` "ya que estamos" o adelantar `ChainEffect` porque "se ve venir". Mitigación: la sección "NO IMPLEMENTAR TODAVÍA" es una lista de control activa, no decorativa — cualquier fase que la toque se para.
- **El adaptador `Room → Fact` puede no cubrir todos los campos** que el motor necesitará en dominios futuros. Mitigación: limitar deliberadamente el adaptador a los campos que los dos dominios del MVP necesitan, sin intentar anticipar los otros 12.
- **Discrepancias con `evaluator.py` sin causa clara** — el motor antiguo tiene sus propios bugs conocidos (además del #1: adyacencia acústica con `_is_adjacent`, uso de `zip()` sin `strict=`, ver `TECH_REVIEW.md`) que pueden generar diferencias no atribuibles a ningún fallo del motor nuevo. Mitigación: la clasificación explícita de diferencias de la sección 7.
- **Corpus de prueba insuficiente** — hoy solo hay un DXF real de referencia (`ejemplo.dxf`) documentado en el proyecto; un acuerdo del 100% sobre un único archivo es una señal débil. Mitigación: tratar el resultado de la Fase 6 como una validación preliminar, no como cierre definitivo — señalarlo explícitamente en el informe de resultados.
- **Riesgo de construir sobre un `git status` no saneado** si el prerrequisito de esta PRD (commitear lo pendiente) no se ejecuta antes de empezar. Mitigación: bloqueante explícito, ya declarado arriba.

## 10. Qué plan de migración seguiremos durante los próximos meses

Este MVP no decide el plan completo — lo que sí puede decir hoy es la secuencia razonable **condicionada a que el MVP tenga éxito** (sección 8):

1. Ampliar la cobertura de `Constraint`/`Rule` dentro del Dominio 3 hasta portar el conjunto completo de reglas dimensionales de `evaluator.py`.
2. Portar el Dominio 4 (Iluminación y Ventilación), el siguiente más maduro y menos ambiguo según `ARCHITECTURAL_KNOWLEDGE_MAP.md`.
3. Solo cuando existan 3-4 dominios reales con `Problem`s propios, empezar a construir el modelo de propagación (`ChainEffect`, Dominio 12) — antes de eso no hay suficientes dominios para que una cadena cruzada tenga sentido real que verificar.
4. Introducir `Conflict`/`Alternative`/`Recommendation`/`Decision` del motor de decisión solo después de que la propagación esté validada con datos reales, no en paralelo.
5. Cutover gradual: `app.py` empieza a invocar el motor nuevo detrás de un flag interno, en modo sombra primero (se calcula pero no se muestra), después con resultados mostrados solo si coinciden con `evaluator.py`, y solo al final como fuente única — `evaluator.py` no se retira hasta que el acuerdo sostenido en uso real, no solo en el corpus de prueba, sea alto.
6. La Tarea 18 de `REFACTOR_MASTERPLAN.md` (suite de test golden-master) queda efectivamente **absorbida** por el arnés de comparación de la Fase 5 de este PRD — no debe duplicarse como esfuerzo aparte.

Este plan es intencionadamente una hipótesis a validar, no un compromiso — el primer punto de control real es el resultado de la Fase 6.

---

## NO IMPLEMENTAR TODAVÍA

Lista de control activa. Si cualquier fase de este PRD empieza a tocar algo de esta lista, es una señal de sobrealcance y debe detenerse:

- **Motor de decisión completo** (`Conflict`, `Alternative`, `Recommendation`, `Decision`, `Preference`) — todo `DECISION_ENGINE.md` queda fuera hasta que exista más de un dominio real generando hallazgos que puedan entrar en conflicto entre sí.
- **Propagación entre dominios** (`ChainEffect`, el motor de `CHAIN_REASONING.md`) — no tiene sentido con solo dos dominios, uno de ellos mínimo.
- **`Assumption`** — el MVP se limita a *detectar y mostrar* `Unknown`, nunca a rellenarlo con una hipótesis. Cubrir huecos de dato con una suposición razonada es una capacidad real pero posterior.
- **`Change` y el modelo de versionado append-only completo de `ProjectState`** — este MVP analiza un DXF de una sola vez (snapshot único), no una sesión de edición iterativa. El modelo de versiones solo tiene sentido cuando exista un flujo de edición real que lo dispare.
- **`Confidence` como cálculo explícito** — los dos dominios del MVP son enteramente Nivel 1-2 (hecho/normativa verificable), así que la confianza sería trivialmente "Alta" en todos los casos; construir el cálculo ahora no prueba nada que un dominio con heurísticas de Nivel 3-4 sí probaría más adelante.
- **`Explanation` (narrativa para el arquitecto)** — no hay usuario final todavía en este MVP; construir una capa de presentación sin audiencia real es trabajo especulativo.
- **Aprendizaje o memoria institucional acumulada** (el tipo de conocimiento que alimentaría el Dominio 12/13 a partir de `Decision`s reales) — no existe ninguna `Decision` real todavía de la que aprender.
- **Optimización de rendimiento** — con un corpus de prueba de un archivo, cualquier preocupación de rendimiento es prematura por definición.
- **Cualquier dominio más allá de los dos elegidos** (los otros 12 de `BRAIN_ARCHITECTURE.md`) — incluidos los tentadores por su valor estratégico ya señalado en documentos anteriores (Dominio 12, Dominio 9) — precisamente por ser más complejos o más subjetivos, son los peores candidatos para un MVP que busca certeza rápida, no ambición.
- **Cualquier cambio en `app.py`, `api_serializer.py` o `static/index.html`** — ninguna superficie de usuario se toca en este PRD, bajo ninguna circunstancia.
- **El dominio de coste/presupuesto** — sigue sin existir como dominio en `BRAIN_ARCHITECTURE.md` (gap ya señalado en `DECISION_ENGINE.md`); no se improvisa aquí como atajo.

---

## Fases de implementación

### Fase 1 — Andamiaje del paquete y entidades base de solo lectura

- **Objetivo:** crear la estructura del nuevo paquete del motor (sin lógica de dominio todavía) y un adaptador que convierte la salida de `analyzer/parser.py` en `Observation` y `Fact`.
- **Archivos afectados:** nuevo paquete (p. ej. `reasoning/`), sin tocar nada dentro de `analyzer/` ni `app.py` (solo lectura de `analyzer/parser.py`).
- **Entidades implicadas:** `ProjectState`, `Observation`, `Fact`, `Unknown`.
- **Riesgos:** el adaptador puede quedarse corto o largo de alcance; se limita deliberadamente a los campos que los Dominios 2 y 3 necesitan, nada más.
- **Criterios de aceptación:** al procesar `ejemplo.dxf`, se genera un `ProjectState` con un `Fact` de superficie, ancho y uso por cada pieza, sin excepciones; ningún campo ausente se rellena solo — se representa como `Unknown`.
- **Tests necesarios:** conteo de `Fact` generados contra el número de piezas conocido de `ejemplo.dxf`; test con un DXF/entrada deliberadamente incompleta que debe producir `Unknown`, nunca un valor supuesto.

### Fase 2 — Dominio 2 mínimo: tipología y zona climática como Facts fiables

- **Objetivo:** que la tipología y la zona climática existan como `Fact` reales, nunca por defecto silencioso — la prueba de fuego directa del Bug #1.
- **Archivos afectados:** nuevo módulo de dominio dentro del paquete del motor; sin tocar `evaluator.py`.
- **Entidades implicadas:** `Domain`, `Rule`, `Inference` (clasificación directa; `Constraint` no es necesario aquí de forma sustancial — se documenta como disponible pero no se fuerza su uso si no aporta nada en este dominio mínimo).
- **Riesgos:** la tentación de construir aquí toda la lógica de clasificación tipológica de `ARCHITECTURAL_KNOWLEDGE_MAP.md` (Dominio 2 completo) en vez del mínimo necesario — se limita expresamente a: tipología y ciudad declaradas por formulario → `Fact` de tipología/zona_cte, o `Unknown` si faltan.
- **Criterios de aceptación:** con los mismos inputs de formulario que hoy recibe `/api/analizar`, se genera el `Fact` correcto de tipología/zona; sin esos inputs, se genera `Unknown`, nunca un valor por defecto equivalente a `DEFAULT_TIPOLOGIA`/`DEFAULT_ZONA_CTE`.
- **Tests necesarios:** caso con tipología=unifamiliar produce `Fact` tipología=unifamiliar (no plurifamiliar); caso sin tipología declarada produce `Unknown` — este es, explícitamente, el test de regresión del Bug #1.

### Fase 3 — Dominio 3: Constraints reales portados desde `evaluator.py`

- **Objetivo:** portar 3-5 `Constraint` concretos (superficie mínima dormitorio individual/doble, ancho mínimo de pieza, proporción máxima) como datos declarativos con su referencia normativa.
- **Archivos afectados:** nuevo módulo de dominio y catálogo de `Constraint`; lee (no modifica) las constantes actuales de `analyzer/evaluator.py` como fuente de verdad de los valores.
- **Entidades implicadas:** `Constraint`, `Rule`.
- **Riesgos:** transcripción incorrecta de un umbral que varía por tipología/zona; mitigado por el test de igualdad directa contra las constantes de `evaluator.py`.
- **Criterios de aceptación:** cada `Constraint` portado coincide exactamente en valor con su equivalente en `evaluator.py` y declara su fuente normativa.
- **Tests necesarios:** test unitario por `Constraint` comparando el valor contra la constante correspondiente de `evaluator.py`; test funcional ejecutando las `Rule`s sobre `ejemplo.dxf` sin excepciones.

### Fase 4 — De `Rule` a `Problem` con `Evidence` completa

- **Objetivo:** cerrar el ciclo del dominio piloto: `Rule` evaluada sobre `Fact` y `Constraint` produce `Inference`, y cuando corresponde, `Problem`, siempre con `Evidence` trazable (Fact citado + Constraint citado + nivel de conocimiento).
- **Archivos afectados:** extensión de los módulos de dominio de las Fases 2-3.
- **Entidades implicadas:** `Inference`, `Problem`, `Evidence`.
- **Riesgos:** sobrediseñar `Evidence` anticipando cadenas multi-dominio que no existen todavía en el MVP; se limita a un único salto (Fact → Rule → Problem), sin `ChainEffect`.
- **Criterios de aceptación:** ningún `Problem` se genera sin `Evidence` no vacía; la `Evidence` de un caso conocido (p. ej. la unidad VT6/2 de `ejemplo.dxf`, ya usada como referencia en el proyecto) cita correctamente el `Fact` y `Constraint` reales que lo motivan.
- **Tests necesarios:** test de invariante "todo `Problem` tiene `Evidence`"; test de contenido de `Evidence` sobre el caso VT6/2.

### Fase 5 — Arnés de comparación automática motor nuevo vs. `evaluator.py`

- **Objetivo:** script que ejecuta ambos motores sobre el mismo corpus de DXFs reales disponibles e informa coincidencias, discrepancias y su causa.
- **Archivos afectados:** nuevo script de comparación (fuera de `analyzer/` y `app.py`); invoca `evaluator.evaluate_advanced()` directamente con los parámetros correctos, evitando la ruta buggy de `app.py`.
- **Entidades implicadas:** ninguna nueva — consume `Problem` (motor nuevo) e `IssueReport` (motor antiguo).
- **Riesgos:** diferencias reales atribuibles a otros bugs ya conocidos de `evaluator.py` (adyacencia acústica, `zip()` sin `strict=`) que no deben achacarse al motor nuevo; mitigado exigiendo que toda diferencia quede clasificada explícitamente en el informe.
- **Criterios de aceptación:** el informe se ejecuta sobre `ejemplo.dxf` sin fallar y clasifica el 100% de las diferencias encontradas.
- **Tests necesarios:** test del propio arnés sobre un caso sintético con diferencia esperada conocida de antemano.

### Fase 6 — Informe de resultados y checkpoint de decisión

- **Objetivo:** no es una fase de construcción — es el cierre formal del MVP: ejecutar el arnés sobre el corpus disponible, documentar el nivel de acuerdo real alcanzado, y decidir con Pablo si se amplía el alcance o se revisa el diseño antes de continuar.
- **Archivos afectados:** documento de resultados nuevo (p. ej. `reasoning/MVP_RESULTS.md`).
- **Entidades implicadas:** ninguna nueva.
- **Riesgos:** ninguno técnico — el riesgo es de proceso: avanzar a más dominios sin pasar por este checkpoint explícito.
- **Criterios de aceptación:** documento entregado con las métricas de la sección 8 medidas realmente sobre el corpus de prueba, no estimadas ni asumidas.
- **Tests necesarios:** no aplica — es una fase de documentación y decisión, no de código.

---

## Revisión de alcance aplicada (CTO)

Al revisar este PRD antes de darlo por cerrado, se eliminó explícitamente lo siguiente por no aportar valor al MVP tal como está definido en la sección 1:

- Una fase inicial de "diseño de la API pública completa del motor" — se sustituyó por la sección 5 tal cual, que deja explícito que no hay API pública real todavía, solo una función de entrada consumida por el propio arnés de comparación. Diseñar una API amplia sin un segundo consumidor real habría sido trabajo especulativo.
- Una fase de "modelo de confianza (`Confidence`)" que se había considerado inicialmente — eliminada porque, con dos dominios enteramente Nivel 1-2, el resultado sería trivial y no probaría nada; se traslada explícitamente a "NO IMPLEMENTAR TODAVÍA".
- Una fase de "adaptador genérico para los 14 dominios" — sustituida por un adaptador limitado a los campos que los dos dominios piloto necesitan; construir un adaptador genérico ahora sería diseñar para 12 dominios que todavía no existen.
- Una fase de "documentación exhaustiva del modelo de entidades para nuevos desarrolladores" — ya existe en `REASONING_ENGINE_SPEC.md`; repetirla aquí sería duplicar, no aportar.

Lo que queda son seis fases, cada una con un entregable verificable por test, y un único punto de decisión real al final (Fase 6) — no una promesa de que el motor "funcionará", sino la evidencia mínima necesaria para decidir si merece la pena seguir.

---

**Decisión:** _pendiente de revisión por Pablo_
