# PRD — Motor de normativa territorial

**Estado:** Aprobado con condiciones · **Fecha:** 2026-08-06 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-06)

> **FASE 0 ENTREGADA** (2026-08-06). Condición previa cumplida (frontend limpio) y tareas 1-12 completas. Fases 1-3 no iniciadas: la 1 está bloqueada por la tarea 18 (validador colegiado). Ver §15.

**Diseño de referencia:** `docs/design/NORMATIVE_RESOLUTION.md` (arquitectura completa) sobre `docs/design/NORMATIVE_ENGINE.md` (corpus y versionado) y `docs/brain/CONSTRAINT_MODEL.md` (evaluación).

**Alcance de este PRD:** **Fases 0-3** del plan del diseño. Las fases 4-6 (transcripción masiva, capa municipal real, `diff_normativo`) quedan fuera y necesitarán su propio PRD cuando haya un cliente que las pida.

---

## 1. Problema que resuelve

No es un problema futuro. Es una contradicción visible hoy, verificada en código el 2026-08-06:

**ArchMuse da dos respuestas distintas a la misma pregunta legal en la misma pantalla.**

- `analyzer/evaluator.py:783` — superficie mínima de vivienda por **tipología**: 30 / 40 / 24 m².
- `static/app.js:120-140` — superficie mínima de vivienda por **comunidad autónoma**: 40 / 36 / 30 / 24…

Para una vivienda plurifamiliar en Madrid, el backend exige 30 m² y el frontend 40 m². Ambas cifras se muestran juntas.

Agravantes, todos comprobados:

1. La tabla del frontend declara en su propio comentario que sus cifras vienen de *"prensa/portales inmobiliarios"*, **sin verificar contra el texto de ningún decreto**, y con ellas `app.js:1929` emite un veredicto literal de "cumple" / "no cumple" desde el navegador, sin traza ni cita.
2. La superficie mínima de vivienda es **competencia autonómica**. El backend la resuelve por un eje que no es el competente; el frontend por el correcto pero con datos sin fuente. Es el hallazgo M1 de `docs/audits/NORMATIVE_AUDIT.md`, visto por sus dos caras.
3. `NORMATIVE_AUDIT.md` §5.3: **ninguna regla del motor conoce la comunidad autónoma**, pese a que al menos 6 umbrales son competencia autonómica. ArchMuse emite hoy un juicio de cumplimiento calibrado para una región implícita sobre proyectos de toda España, sin decirlo.
4. `NORMATIVE_AUDIT.md` §6.1: **0 reglas citan un artículo**, mientras `MOAT_ANALYSIS.md` §1 ya posiciona el producto como defensa profesional.

Origen: petición directa de Pablo (2026-08-06), auditoría normativa del 2026-08-05, y hallazgo nuevo de esta sesión (el punto 1, que ninguna auditoría previa había registrado).

## 2. Usuario afectado

**Hoy:** el arquitecto que analiza un proyecto fuera de la región implícita para la que el motor está calibrado — es decir, casi cualquiera. Recibe un juicio legal que no le corresponde y no tiene forma de saberlo.

**Objetivo (`NORTH_STAR_2031.md`):** el estudio que necesita defender un informe ante un colegio o una aseguradora, y el colegio/aseguradora que lo audita. Ninguno de los dos puede usar un informe que no cita artículo ni declara su cobertura.

## 3. Objetivo de negocio

Tres, en orden de solidez:

1. **Retirar una afirmación insostenible.** Un producto que dice "cumple" con datos de prensa es un riesgo de reputación y de responsabilidad, no una funcionalidad. Esto es defensivo y no admite discusión de prioridad.
2. **Convertir la cobertura en algo vendible.** *"Cumple las 214 reglas cargadas para Pozuelo; sin cobertura de patrimonio"* es una afirmación que un profesional puede usar. *"Cumple"* no lo es. Encaja con la identidad de `MOAT_ANALYSIS.md`: infraestructura de riesgo, no novedad con IA.
3. **Habilitar la única capacidad realmente no replicable**: `diff_normativo` (`NORMATIVE_ENGINE.md` §4.3), que exige historial acumulado y no se puede añadir retroactivamente sobre un corpus que sobrescribe. Fuera de este PRD, pero imposible sin su esquema.

## 4. Objetivo técnico

Una vez implementado, debe ser observable que:

- Dado país/comunidad/provincia/municipio/tipo/uso/tipología/fecha, el sistema devuelve el conjunto de reglas aplicables **sin que ningún módulo consulte un nombre de municipio**.
- Añadir un municipio con corpus consiste en **crear un directorio y sus ficheros**. Cero cambios de código, cero despliegue de lógica.
- `analyzer/evaluator.py` **no importa nada de `normativa/`** y no sabe qué es una comunidad autónoma. La dependencia va en un solo sentido.
- Toda regla devuelta lleva uno de cuatro estados (`aplica` / `no_aplica` con motivo / `aplica_no_evaluable` / `sin_cobertura`). **Nunca silencio.**
- Todo resultado va acompañado de un informe de cobertura declarada.
- Ningún umbral es un escalar sin ejes ni cadena de repliegue declarada.

## 5. Casos de uso

**CU1 — Vivienda unifamiliar en Pozuelo de Alarcón.** El arquitecto declara los siete campos. El sistema resuelve `es → es.13 → es.13.28 → es.13.28.28115`, compone por materia y competencia, y devuelve el conjunto aplicable más su cobertura. Detalle completo en `NORMATIVE_RESOLUTION.md` §13.

**CU2 — El mismo plano en Sevilla.** Cambia la capa autonómica de habitabilidad; el resultado de superficie mínima cambia. Hoy no cambia, y ese es el defecto.

**CU3 — Municipio sin corpus.** El arquitecto escribe un municipio de los 8.131 del registro para el que no hay reglas municipales. El sistema aplica CTE + capa autonómica y declara `sin_cobertura` en las materias municipales. **No falla, y no finge.**

**CU4 — Nombre ambiguo.** "Villanueva" devuelve `AmbitoAmbiguo` con los candidatos. El sistema pregunta; no elige el más poblado.

**CU5 — Proyecto con fecha pasada.** Licencia solicitada en 2025. Se resuelve la normativa vigente **en esa fecha**, no la de hoy.

**CU6 — Curador añade un municipio.** Crea `normativa/es/13-madrid/municipios/28092-leganes/`, escribe `_ambito.yaml` y sus reglas, declara cobertura. CI valida. Sin tocar código.

## 6. Casos límite

| Caso | Comportamiento exigido |
|---|---|
| Municipio no reconocido | `AmbitoAmbiguo` o error explícito. **Nunca** repliegue silencioso a Madrid ni al default |
| `fecha_devengo` no informada | Se usa hoy **y se marca como asunción visible**, nunca como hecho (`UNCERTAINTY_MODEL.md`) |
| Fichero de corpus inválido | Esa materia de ese ámbito → `sin_cobertura`. **Nunca carga parcial** (§8.1 del diseño) |
| Ámbito sectorial no declarado | `desconocido` con pregunta pendiente. **No** equivale a "no aplica" (`INFERENCE_ENGINE.md` §2.2) |
| Dos reglas de igual materia/ámbito/perfil en contradicción | **Falla la validación en CI.** Nunca desempate por orden de carga ni alfabético |
| Contradicción real entre capas | Se expone como Conflict con las dos citas. **No se resuelve automáticamente** |
| Municipio fusionado/desaparecido | Sigue existiendo con su vigencia, para poder analizar proyectos anteriores |
| Parámetro urbanístico no informado | La regla existe, el parámetro no. `aplica_no_evaluable`. Es el comportamiento **actual y correcto** de `evaluator.py:2609`; se preserva |
| `tipologia="rehabilitacion"` (valor heredado) | Se traduce a `tipo_intervencion=rehabilitacion` **marcándolo como asunción**, nunca en silencio |

## 7. Flujo del usuario

1. Al crear el análisis, el formulario sustituye el campo libre "Ciudad" por: País (fijo: España) → Comunidad → Provincia → Municipio (autocompletado sobre los 8.131), más tipo de intervención, uso y tipología, más fecha de devengo (opcional, con su asunción visible si se omite).
2. Al elegir municipio, la interfaz muestra **antes de analizar** qué cobertura hay: *"CTE completo · habitabilidad Comunidad de Madrid completa · urbanismo municipal parcial · sin cobertura de patrimonio"*.
3. Si hay ámbitos sectoriales posibles, se pregunta por ellos (¿parcela catalogada?), indicando a cuántas reglas afecta la respuesta.
4. Se analiza. El informe incluye reglas aplicadas, no aplicadas con motivo, no evaluables y materias sin cobertura.
5. Cada incidencia puede abrir su regla: artículo, literal legal, fuente oficial, fecha de verificación.

## 8. Criterios de aceptación

1. `resolver_ambito("España", municipio="Pozuelo de Alarcón")` devuelve la cadena `es / es.13 / es.13.28 / es.13.28.28115`.
2. El registro geográfico contiene los 8.131 municipios y resuelve alias con y sin tildes y denominaciones cooficiales.
3. `normativa_aplicable(...)` devuelve, para toda regla candidata, uno de los cuatro estados. **Ninguna regla se omite sin estado.**
4. ~~Existe un test que **falla** si algún módulo de `analyzer/` importa `normativa/`, y otro que falla si `normativa/` importa `analyzer/`.~~ **CORREGIDO durante la implementación** — era contradictorio con la tarea 12 de este mismo PRD, que manda dejar `cte_zonas.py` como fachada sobre los datos migrados y por tanto exige que `analyzer/` importe `normativa/`. El criterio real, que es el que dice el documento de diseño §11, es de un solo sentido: **`normativa/` nunca importa `analyzer/`** (prohibición dura), y **`analyzer/` solo consume la superficie pública de `normativa/`, desde módulos de una lista explícita**. Ambos se comprueban en `tests/test_normativa_fronteras.py`.
5. Un municipio nuevo con corpus se añade en un commit **sin ficheros `.py` modificados** — verificado por test en CI.
6. Las 17 validaciones de `NORMATIVE_RESOLUTION.md` §9 se ejecutan en CI. Un corpus que declare superficie mínima de vivienda a nivel municipal **no pasa** (validación 11).
7. `SUPERFICIE_MIN_CCAA` y `CIUDAD_A_CCAA` han desaparecido de `static/app.js`; el dato se sirve desde la API con fuente y fecha de verificación.
8. Tras la Fase 3, el mismo `ejemplo.dxf` analizado en Madrid y en Sevilla da resultados distintos en superficie mínima, y ambos citan su decreto.
9. La suite de salida congelada existente sobre `ejemplo.dxf` **sigue pasando sin cambios** en las fases 0-2.
10. `normativa/` se prueba entero sin ningún DXF.
11. Ninguna cifra normativa entra al corpus sin `fuente` con boletín, `articulo` y `nivel_de_conocimiento`.

## 9. Riesgos

Los siete de `NORMATIVE_RESOLUTION.md` §16 aplican íntegros. Los específicos de ejecutar **este** PRD:

| Riesgo | Comentario |
|---|---|
| **Compite con `REFACTOR_MASTERPLAN.md`** | Sí, y no lo disimulo. Compite directamente con las tareas 22-24 (refactor declarativo de `classify_problems`) — pero **converge** con ellas: ambas terminan en el mismo modelo declarativo, y hacerlas por separado sería trabajo duplicado. En cambio compite de frente, sin sinergia, con las tareas de duplicación de reglas (D1-D4 de la auditoría), que arreglan un daño visible en la primera pantalla. **Recomendación: D1-D4 antes que este PRD** — son horas, no semanas, y su beneficio es inmediato |
| **La Fase 1 exige contenido normativo verificado** | El cuello de botella no es programar: es que un arquitecto colegiado valide 17 cifras autonómicas contra su decreto. **Sin ese perfil disponible, la Fase 1 no se puede cerrar con honestidad**, solo se puede mover la tabla de prensa de sitio. Es la dependencia crítica de todo el PRD |
| **Sobrediseño para un producto sin usuarios de pago** | Real. Mitigado porque la Fase 1 corrige una contradicción existente hoy, no prepara un futuro hipotético |
| **Regresión en `evaluator.py`** | Solo la Fase 3 lo toca, una función, con test de salida congelada delante |
| **Cambiar el formulario reduce conversión** | Cuatro desplegables piden más que un campo libre. Mitigable con "España + municipio" y derivando comunidad y provincia del código INE — se recomienda esa variante |

## 10. Impacto sobre módulos existentes

| Módulo | Fase | Impacto |
|---|---|---|
| `normativa/` (nuevo) | 0-3 | Paquete nuevo, aislado. Se puede borrar entero sin romper el análisis |
| `analyzer/cte_zonas.py` | 0 | Sus datos pasan a `normativa/geografia/derivados/`. **La función pública se mantiene como fachada** — `app.py` y `app.js` la consumen |
| `app.py` | 1 | Punto de sutura: construir la cadena territorial y el perfil, pasarlos. Es donde ya se resuelve zona y densidad |
| `static/app.js` | 1 | Se eliminan `SUPERFICIE_MIN_CCAA`, `CIUDAD_A_CCAA`, `getSuperficieMinima`; `toolNormativaHtml` pasa a leer del payload |
| `analyzer/api_serializer.py` | 2 | Campo nuevo `cobertura` en el payload |
| `analyzer/evaluator.py` | **3** | **Una función**: `evaluate_unit_minimum_area`. Nada más |
| `analyzer/storage.py` | 2 | Los proyectos guardados deben conservar la cadena y la fecha de devengo |
| `parser.py`, `escala.py`, `plan_svg.py`, `circulation.py`, `spatial_quality.py`, `scoring.py`, `chain_effects.py` | — | **Intactos** |

Consumidores indirectos a vigilar: `pdf_report.py` y `ai_analyst.py` leen el payload serializado; ganan el campo de cobertura y **deben mostrarlo**, no ignorarlo — un PDF que omite la cobertura reintroduce la afirmación insostenible por la puerta de atrás.

## 11. Plan de implementación

Tareas independientes de ≤2 h, formato de `REFACTOR_MASTERPLAN.md`.

### Fase 0 — Cimientos (sin nada visible)

| # | Tarea | Dep. |
|---|---|---|
| 1 | Paquete `normativa/` vacío + test que falla si importa `analyzer/` | — |
| 2 | `esquema/regla.schema.json`: NormaFuente + ReglaNormativa + aplicabilidad | — |
| 3 | `esquema/materias.yaml` (14) y `esquema/usos.yaml` (árbol) | — |
| 4 | `esquema/competencias.yaml`: matriz materia × nivel × modo | 3 |
| 5 | Importar el registro INE completo → `geografia/es/*.yaml` + script de actualización | — |
| 6 | `alias.yaml` + normalización (tildes, artículos, cooficiales) | 5 |
| 7 | `resolver_ambito()` + `AmbitoAmbiguo`; tests con Pozuelo, homónimos y municipio fusionado | 5,6 |
| 8 | Loader: descubrir + parsear. Fail-closed | 2 |
| 9 | Validaciones 1-8 (heredadas de `NORMATIVE_ENGINE.md` §11.1) | 8 |
| 10 | Validaciones 9-17 (nuevas), con la 11 y la 17 como test propio | 4,9 |
| 11 | Índice SQLite derivado + sellado por hash + regeneración | 8 |
| 12 | Migrar los datos de `cte_zonas.py` a `geografia/derivados/`, dejando fachada | 5 |

### Fase 1 — Resolver y primera regla real

| # | Tarea | Dep. |
|---|---|---|
| 13 | `perfil_proyecto()` + árbol de usos + traducción del `tipologia` heredado con asunción visible | 3 |
| 14 | Resolver, pasos 1-4 (candidatas, temporal, perfil, condiciones) | 7,8,13 |
| 15 | Resolver, pasos 5-6: agrupación por materia + los 4 modos de composición | 4,14 |
| 16 | Resolver, pasos 7-8: aristas y materialización de conflicto | 15 |
| 17 | `ConjuntoAplicable` con los 4 estados y motivo obligatorio en `no_aplica` | 14 |
| 18 | **Contenido: transcribir la superficie mínima autonómica de 4 CCAA** contra boletín. **Requiere validador colegiado** | 2 |
| 19 | `normativa_aplicable()` público + tests de extremo a extremo del CU1 | 15,17,18 |
| 20 | Endpoint que sirve el dato normativo al frontend | 19 |
| 21 | Eliminar `SUPERFICIE_MIN_CCAA`/`CIUDAD_A_CCAA` de `app.js`; `toolNormativaHtml` lee del payload | 20 |
| 22 | Formulario: municipio con autocompletado + fecha de devengo opcional | 7 |

### Fase 2 — Cobertura

| # | Tarea | Dep. |
|---|---|---|
| 23 | `cobertura/manifiesto.yaml` + 3 estados (`parcial`/`ausente`/`no_competente`) | 10 |
| 24 | `cobertura()` + validación 17 (manifiesto vs. disco) | 23 |
| 25 | Campo `cobertura` en `api_serializer.py` | 24 |
| 26 | Cobertura en la interfaz, antes y después del análisis | 25 |
| 27 | Cobertura en `pdf_report.py` | 25 |
| 28 | Persistir cadena y fecha de devengo en `storage.py` | 22 |

### Fase 3 — Primer estrangulamiento

| # | Tarea | Dep. |
|---|---|---|
| 29 | Test de salida congelada de `evaluate_unit_minimum_area` sobre `ejemplo.dxf`, **antes de tocarla** | — |
| 30 | Adaptador que traduce una `ReglaNormativa` al resultado que `score_unit` ya espera | 19 |
| 31 | `evaluate_unit_minimum_area` consume el corpus; el umbral sale de `UMBRALES_TIPOLOGIA` | 29,30 |
| 32 | Verificar Madrid ≠ Sevilla sobre el mismo plano, con cita en ambos | 31 |
| 33 | `explicar_aplicabilidad()` para esa regla | 16 |

**Dependencia externa y bloqueante: la tarea 18.** Sin arquitecto colegiado que valide las cifras, la Fase 1 no se cierra. Se puede llegar hasta la 17 y parar.

## 12. Plan de pruebas

| Nivel | Qué |
|---|---|
| **Regresión** | La suite congelada sobre `ejemplo.dxf` pasa sin cambios en fases 0-2. En la 3, solo cambia lo que la tarea 29 congeló, y el cambio se revisa a mano |
| **Aislamiento** | Test que falla si `analyzer/` importa `normativa/` o al revés (criterio 4) |
| **Sin código** | Test que añade un municipio de prueba y falla si el diff toca algún `.py` (criterio 5) |
| **Corpus** | Las 17 validaciones en CI sobre el corpus completo. Un corpus con superficie mínima a nivel municipal debe fallar |
| **Resolución** | Pozuelo, Barcelona, homónimos, municipio sin corpus, municipio fusionado, fecha pasada, sectorial no declarado |
| **Nunca silencio** | Ninguna regla candidata sale sin estado; ningún `no_aplica` sin motivo |
| **Sin repliegue silencioso** | Municipio desconocido **no** produce el conjunto de Madrid |
| **Determinismo** | Mismas entradas → mismo `ConjuntoAplicable`, byte a byte (requisito de `TRACEABILITY.md` §10) |

`pytest` no está instalado ni en `venv/` ni en el Python del sistema (verificado el 2026-08-05). Instalarlo es prerrequisito de la tarea 1.

## 13. Métricas de éxito

| Métrica | Hoy | Objetivo |
|---|---|---|
| Respuestas contradictorias a la misma pregunta legal | **1 (visible)** | 0 |
| Reglas con cita de artículo verificable | 0 de 41 | ≥1 tras la Fase 1; todas tras la Fase 4 |
| Ejes de contexto disponibles | 2 | 5 (+ comunidad, municipio, uso) |
| Municipios resolubles | 30 (tabla cerrada) | 8.131 |
| Informes que declaran su cobertura | 0 % | 100 % |
| Ficheros `.py` tocados al añadir un municipio | n/a | **0**, medido en CI |
| Cifras normativas sin fuente verificada mostradas al usuario | **16** (`SUPERFICIE_MIN_CCAA`) | 0 |

La última es la que de verdad mide si esto funcionó.

## 14. Posibles motivos para NO implementarlo

Cinco argumentos honestos en contra. Los tres primeros son de peso.

**1. Hay una solución de 30 minutos para el 80 % del daño real.** Borrar `SUPERFICIE_MIN_CCAA` y `toolNormativaHtml` de `app.js` elimina hoy mismo la contradicción y la afirmación sin fuente. No requiere esta infraestructura. Un CTO honesto tiene que decir que **ese borrado debería ocurrir tanto si este PRD se aprueba como si no, y antes que él.** Todo lo demás de este documento es construir la capacidad de dar la respuesta *correcta*; borrar es dejar de dar una incorrecta, y es estrictamente más urgente.

**2. El cuello de botella no es el que este PRD resuelve.** La arquitectura permite 8.131 municipios; el contenido exige un arquitecto colegiado validando cifras contra boletín, materia a materia. 8.131 × 14 = 113.834 casillas que nunca se llenarán. **Este PRD construye el estante, no los libros**, y el estante vacío no vale nada. Si no hay compromiso real de curación, el resultado es infraestructura elegante sirviendo el mismo corpus de hoy.

**3. `BRAIN_REVIEW.md` ya advirtió exactamente de esto.** Su hallazgo central es que la serie de diseño va muy por delante del único plan de implementación real, y recomienda aprobar y construir `PRD-001` (2 dominios, 8 entidades) **antes de ensanchar el alcance**. Este PRD lo ensancha. La objeción es legítima y hay que responderla, no esquivarla: la diferencia es que `PRD-001` es una reescritura del motor sin efecto visible para el usuario, y este arregla una incorrección que el usuario ve. Pero **si el equipo es una persona, hacer los dos a la vez es garantía de no terminar ninguno.**

**4. Compite con arreglos más baratos y más visibles.** D1-D4 de `NORMATIVE_AUDIT.md` — el peor caso genera **dos CRÍTICOS sobre el mismo baño**, en la primera pantalla que ve un cliente. Se arregla en horas. Este PRD son semanas. La secuencia por retorno es: D1-D4 → borrar la tabla de `app.js` → este PRD.

**5. Sin usuarios de pago, la cobertura declarada no tiene a quién convencer.** Su valor comercial es real pero diferido.

### Recomendación

**Aprobar el diseño; aprobar el PRD con dos condiciones y una reordenación.**

1. **Antes de la tarea 1:** borrar `SUPERFICIE_MIN_CCAA` y su veredicto de `app.js` (motivo 1), y cerrar D1-D4 de la auditoría (motivo 4). Días, no semanas, y son el mayor retorno disponible ahora mismo.
2. **La Fase 1 no arranca sin validador colegiado comprometido** (motivo 2). Fase 0 sí puede arrancar: es esquema, registro geográfico y validadores, todo verificable sin conocimiento legal, y no caduca.
3. **Parar en la Fase 2** y revisar con datos reales antes de la 3. La 3 toca `evaluator.py` y es la primera decisión irreversible.

Lo que **no** recomiendo es aprobar el plan entero de una vez. La parte que hay que acertar ahora —identidad territorial por código INE y eje temporal— no se puede añadir después. El resto puede, y debería, esperar a que un cliente pida Bilbao.

---

**Decisión:** _pendiente de revisión por Pablo_

---

## 15. Estado de entrega — Fase 0 (2026-08-06)

### Condición previa (exigida antes de cualquier implementación)

| Condición | Estado |
|---|---|
| Eliminar la tabla normativa de `static/app.js` | **Hecho.** `SUPERFICIE_MIN_CCAA`, `CIUDAD_A_CCAA`, `getCCAA`, `getSuperficieMinima` borrados |
| Eliminar toda lógica que emita juicios normativos en el cliente | **Hecho.** `toolNormativaHtml` ya no calcula: pinta `normativa_aplicada`, que decide `evaluator.py` |
| Frontend como capa de presentación | **Hecho.** `NORMATIVA_REF` (20 códigos → texto normativo, afirmado por el navegador) movido a `analyzer/referencias_normativas.py` y servido en `issue.referencia_normativa` |
| `evaluator.py` única fuente de verdad en la transición | **Hecho.** No se ha tocado. El umbral que se muestra es el que él aplica |

Efecto observable: la contradicción de §1 ha desaparecido. En `ejemplo.dxf`, VT1/3 tiene 36,9 m² útiles — el backend dice *cumple* (mínimo 30 por tipología) y la tabla borrada decía *no cumple* (40 por Madrid). Ahora hay una sola respuesta, y va acompañada del aviso de que el umbral se resuelve por tipología y no por comunidad autónoma, que es la limitación real.

### Tareas 1-12

Todas completas. `normativa/` contiene: esquema (`regla.schema.json`, `materias.yaml` 14 materias, `competencias.yaml`, `usos.yaml`), registro geográfico, cargador fail-closed con carga perezosa, las 17 validaciones, índice SQLite sellado por hash, y la API pública de 6 funciones.

**Desviación declarada — tarea 5.** El registro contiene **19 comunidades y 52 provincias completas y verificadas**, pero solo **31 de los 8.131 municipios**: los 30 que reconocía `cte_zonas.py` más Pozuelo de Alarcón. Los códigos de esa semilla se han escrito a mano y **no están verificados contra el fichero oficial del INE**. Escribir 8.131 códigos de memoria habría sido cometer, en el registro, el mismo error que este subsistema existe para impedir.

Consecuencias, todas explícitas y probadas:

- `_registro.yaml` declara `estado: parcial`, `verificado: false`, y esa procedencia **viaja pegada a cada cadena resuelta** (`CadenaAmbitos.procedencia`) hasta convertirse en una asunción visible.
- Un municipio ausente levanta `AmbitoDesconocido`. **Nunca repliega** a otro municipio ni al ámbito estatal (`test_municipio_desconocido_no_repliega`).
- `scripts/actualizar_registro_ine.py` completa el registro desde el CSV oficial. Es un paso manual pendiente, no código por escribir.

**El criterio de aceptación 2 (8.131 municipios) NO está cumplido**, y la infraestructura que lo hace posible sí.

### Criterios de aceptación

| # | Criterio | Estado |
|---|---|---|
| 1 | `resolver_ambito` devuelve la cadena de Pozuelo | ✅ |
| 2 | Registro con 8.131 municipios y alias | ⚠️ **Alias sí; 31 de 8.131 municipios.** Ver desviación |
| 3 | Cuatro estados, ninguna regla sin estado | ⏸ Fase 1 (`normativa_aplicable` levanta `NotImplementedError` en vez de devolver vacío, que se leería como "nada que incumplir") |
| 4 | Tests de frontera | ✅ **con el criterio corregido** (ver §8) |
| 5 | Añadir municipio sin tocar `.py` | ✅ `test_normativa_municipio_nuevo.py` lo hace de verdad sobre el árbol real |
| 6 | 17 validaciones en CI; superficie mínima municipal no pasa | ✅ 29 tests, uno por defecto real de la auditoría |
| 7 | `SUPERFICIE_MIN_CCAA` fuera de `app.js` | ✅ |
| 8 | Madrid ≠ Sevilla en superficie mínima | ⏸ Fase 3 |
| 9 | Suite congelada sigue pasando | ✅ 21/22; el único fallo (`test_scoring_coherencia.py`) ya fallaba antes de tocar nada |
| 10 | `normativa/` se prueba sin DXF | ✅ |
| 11 | Ninguna cifra sin fuente + artículo + nivel | ✅ por construcción (validaciones 1b, 12, 16) |

### Dos bugs reales encontrados por los tests

1. **`lru_cache` construía dos registros geográficos.** `registro()` y `registro("es")` son claves de caché distintas: dos instancias independientes que divergen en cuanto una se toca. Corregido resolviendo el argumento por defecto fuera de la función cacheada.
2. **PyYAML convierte `2000-01-01` en `datetime.date`** y el esquema esperaba cadena. Los fixtures en Python usaban cadenas y lo ocultaban; el primer fichero YAML real lo destapó. Se normaliza al cargar (`loader.normalizar_fechas`) en vez de obligar al curador a entrecomillar fechas.

### Qué NO se ha hecho, y por qué

- **Fase 1** — bloqueada por la tarea 18: transcribir superficie mínima de 4 comunidades exige un arquitecto colegiado que valide contra boletín. Sin él, esto solo movería de sitio la tabla de prensa.
- **Fases 2-3** — dependen de la 1.
- **Formulario territorial** (tarea 22) — cambiar el formulario sin corpus detrás pediría cuatro datos para no hacer nada con ellos.
- **Sin scraping, sin OCR, sin importación masiva de normativa**, según la condición. El único importador es el del registro geográfico, que es dato administrativo público y se ejecuta a mano.

### Siguiente decisión (Fase 0)

No es técnica: **conseguir el validador colegiado**. La infraestructura está y no caduca; el contenido no se puede fabricar.

## 16. Estado de entrega — Fase 1 (2026-08-06)

Implementado el motor de resolución completo (tareas 13-17, 19; 18 y 20-22
siguen bloqueadas, ver más abajo). Dos módulos nuevos: `normativa/resolucion.py`
(los ocho pasos de `NORMATIVE_RESOLUTION.md` §7.3) y `normativa/condiciones.py`
(evaluador de condiciones con lógica ternaria de Kleene — SI/NO/DESCONOCIDO,
no booleana, para que un hecho ausente nunca se lea como "no aplica"). Nuevo
catálogo de datos, `esquema/exigibilidad.yaml`, que declara qué materias son
exigibles a qué perfil de proyecto — es lo que hace computable el fail-closed:
sin él, "falta una norma obligatoria" no se podía decidir. `evaluator.py` sigue
sin tocarse.

### `normativa_aplicable()` — contrato final

```
normativa_aplicable(contexto, perfil=None, fecha_devengo=None, hechos=None,
                     fecha_de_registro=None, estricto=True) -> ConjuntoAplicable
```

`contexto` acepta un `ContextoTerritorial` (forma recomendada) o una
`CadenaAmbitos` + `perfil` sueltos — ambos caminos derivan zona climática,
densidad y asunciones por la misma función, verificado con test propio.
`estricto=True` (por defecto) levanta `CoberturaInsuficiente` con la lista
exacta de materias exigibles sin cobertura si falta una sola; `estricto=False`
devuelve el `ConjuntoAplicable` con `.completo=False` para una interfaz que
quiera pintar el hueco explícitamente, nunca para seguir calculando como si
no existiera.

Cada `NormaAplicable` trae los 8+ campos que pedía la tarea original: id,
nombre, ámbito, organismo, versión, fecha (+ fecha_hasta), prioridad, motivo,
cobertura y fuente oficial completa (rango, identificador, título, boletín,
artículo, url). Ordenadas estatal → autonómico → municipal → sectorial y,
dentro de cada nivel, por prioridad (bloqueante primero) — el orden en que un
arquitecto lee la normativa de un proyecto.

### Los cuatro estados, con cierre añadido no descrito en el diseño original

`aplica` / `no_aplica` (siempre con motivo) / `aplica_no_evaluable` (falta un
dato, o el tipo de regla no es evaluable — ver abajo) / `sin_cobertura`.
Añadido durante la implementación: **una regla de tipo no evaluable
(`exigencia_cualitativa`, `definicion`, `remision`, `procedimental`) nunca sale
como `aplica`**, aunque su perfil y condiciones encajen — sale
`aplica_no_evaluable` con el motivo "rige, pero es cualitativa: se informa, no
se puntúa". El diseño (§6 de `NORMATIVE_ENGINE.md`) decía que estos 4 tipos no
son evaluables; faltaba conectar esa propiedad con el estado final, y sin
conectarla el motor habría prometido una comprobación geométrica que 4 de cada
7 tipos de regla no pueden tener.

### Composición: limitación real declarada, no oculta

El modo `suelo` (CTE como mínimo, autonómica/municipal puede endurecer) NO
sustituye la regla base cuando la inferior endurece: **las conserva ambas**, y
solo anota la relación `endurece` si la propia regla lo declara con una arista.
El diseño de §7.3 preveía sustitución automática, pero decidir si una regla
"endurece" a otra exige conocer la DIRECCIÓN de la comparación (mínimo vs.
máximo), y el esquema del corpus no tiene hoy ningún campo que la declare.
Deducirlo de la magnitud del número sería exactamente el "gana la más
restrictiva" que el propio §7.1 llama incorrecto. Conservar ambas nunca
produce una respuesta falsa — solo una lista un campo más larga, con un aviso
si el Curador no declaró la arista — así que se prefirió eso a inventar una
regla de comparación no pedida. Si se quiere sustitución automática, hace
falta antes un campo `direccion: minimo|maximo` en `parametro`, no está aquí.

### Conflictos: paso 8 implementado con detección real, no solo el contrato

Dos reglas de la misma materia, ámbito y patrón que se solapan sin ser
idénticas (la validación 14 de la Fase 0 solo prohíbe en carga las que
compiten con clave de perfil IDÉNTICA) se exponen como `Conflicto` con ambas
citas — el motor no desempata. Si el corpus declara una relación entre ellas
(cualquier arista, en cualquier dirección), no se reporta conflicto: hay
jerarquía escrita, que es lo que se le pide al Curador.

### Tareas 13-19: estado

| # | Tarea | Estado |
|---|---|---|
| 13 | `perfil_proyecto()` + traducción con asunción | ✅ Fase 0 (ya entregado) |
| 14 | Resolver, pasos 1-4 | ✅ |
| 15 | Resolver, pasos 5-6 (agrupación + 4 modos) | ✅ (ver limitación de `suelo` arriba) |
| 16 | Resolver, pasos 7-8 (aristas + conflicto) | ✅ |
| 17 | `ConjuntoAplicable`, 4 estados, motivo obligatorio | ✅ |
| 18 | Transcribir superficie mínima de 4 CCAA, validado por colegiado | ⏸ **Sigue bloqueada.** Dependencia externa, no técnica |
| 19 | `normativa_aplicable()` público + tests E2E | ✅ 34 tests nuevos en `tests/test_normativa_aplicable.py`, contra un corpus **ficticio** (`tests/fixtures/corpus_ficticio/`, ver su `LEEME.md`) — el algoritmo se verifica sin esperar a la 18 |
| 20-22 | Endpoint, borrar tablas de `app.js`, formulario | ⏸ Sin sentido con el corpus real vacío: expondrían una API que solo puede fallar |

### Por qué un corpus ficticio y no esperar a la tarea 18

La tarea 18 sigue bloqueada por la misma razón que en la Fase 0: transcribir
una cifra autonómica exige validación colegiada contra boletín, y ese cuello
de botella no tiene por qué bloquear la verificación del ALGORITMO. El
corpus de `tests/fixtures/corpus_ficticio/` es inventado a propósito, vive
fuera de `normativa/` (nunca lo alcanza una ruta de producción — hay test
propio, `test_el_corpus_de_produccion_sigue_vacio`) y pasa las 17
validaciones reales de la Fase 0. Contra el corpus de PRODUCCIÓN, que sigue
vacío, `normativa_aplicable()` sigue bloqueando cualquier proyecto — es el
primer test del archivo (`test_corpus_real_vacio_bloquea`) y es el
comportamiento correcto, no un fallo.

### Regresión

34/34 en `test_normativa_aplicable.py`. Los 21 ficheros de test restantes:
sin cambios respecto a la Fase 0 — el único fallo preexistente
(`test_scoring_coherencia.py`) sigue siendo la misma decisión abierta y
documentada, no un efecto de este trabajo. `evaluator.py` no aparece en el
diff de esta sesión.

### Siguiente decisión (Fase 1)

Sigue siendo la misma: **conseguir el validador colegiado** para la tarea 18.
Con eso resuelto, las tareas 20-22 (endpoint, integración con `app.js`,
formulario territorial) son mecánicas sobre lo ya construido.
