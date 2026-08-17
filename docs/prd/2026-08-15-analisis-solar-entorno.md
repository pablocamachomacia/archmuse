# PRD — Análisis solar y de entorno (sitio → generador/entrevistador)

**Estado:** Borrador · **Fecha:** 2026-08-15 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 0. Dependencias reales — hay que leerlas antes que el resto del PRD

Este encargo da por hecho que `analyzer/sitio.py` "del módulo anterior" ya existe. **No existe todavía**: `docs/prd/2026-08-15-analisis-de-sitio.md` sigue `Borrador`, sin tu aprobación ni una línea de código. Este PRD depende de él de dos formas distintas:

1. **De datos**: `analizar_orientacion_solar`/`resumir_entorno` reciben `sitio_data` como entrada — sin el módulo anterior, no hay nada que analizar.
2. **De diseño, no solo de datos**: el punto 3 del encargo ("integrar en el entrevistador... cuando hay análisis disponible") necesita la MISMA pieza de arquitectura que `docs/prd/2026-08-15-conector-pliego-generador.md` §10 ya identificó como "delicada" y dejó sin resolver: una vía para sembrar `EstadoEntrevista` con datos que no vienen de una pregunta. Ese PRD tampoco está aprobado. Construir aquí una segunda vía de siembra distinta (una para el pliego, otra para el sitio) sería exactamente el tipo de duplicación que este proyecto evita sistemáticamente en otros sitios (`analyzer/cte_zonas.py`, ver §4).

**Recomendación de secuencia, no una objeción de fondo**: aprobar primero (o en el mismo lote) `2026-08-15-analisis-de-sitio.md`, y diseñar el mecanismo de siembra del entrevistador UNA vez, compartido entre pliego y sitio, en vez de dos veces. El resto de este PRD asume que eso ya ocurrió.

Además, hoy mismo hay ya 4 PRDs de pliegos/sitio abiertos (1 implementado, 3 pendientes) antes de este quinto. Lo señalo aquí, no para frenar, sino para que la decisión de meter uno más en la cola sea explícita.

## 1. Problema que resuelve

`analyzer/sitio.py` (una vez exista) trae datos crudos del entorno; nada los convierte en algo que el generador o el entrevistador puedan usar — hoy `ai_generator.py` asume "sur es mejor" como regla fija, sin saber si ese solar concreto tiene un colindante de 9 plantas tapando el sur real. Encargo directo de Pablo (2026-08-15).

## 2. Usuario afectado

El mismo arquitecto de los PRDs anteriores, en el momento de generar o revisar un proyecto sobre un solar concreto, no sobre un solar abstracto.

## 3. Objetivo de negocio

Convierte datos de entorno en decisiones de diseño reales — es la diferencia entre "ArchMuse sabe que hay un colegio cerca" (dato) y "ArchMuse orienta los dormitorios sabiendo que el colindante de 9 plantas tapa el sur real" (decisión). Sin esto, `2026-08-15-analisis-de-sitio.md` es solo un visor de datos.

## 4. Objetivo técnico

- **Orientación y sol: 100% software, sin IA** — fórmulas de posición solar estándar (declinación, ángulo horario, altitud/azimut solar), deterministas, sin API de pago. Encaja directamente con la filosofía de Pablo del 2026-08-01.
- **Horas de sol por fachada es una ESTIMACIÓN, no una medición** — su precisión depende de la altura de los colindantes, que `analyzer/sitio.py` ya documentó como dato incompleto en OpenStreetMap (`building:levels` frecuentemente ausente). Se publica con el mismo modelo `Hecho` (KNOWN/ESTIMATED/UNKNOWN + confianza) que CAP-1..5 y el extractor de pliegos — nunca una cifra sin decir de dónde sale ni cuánto se puede confiar en ella.
- **Zona climática CTE: NO se recalcula desde coordenadas.** `analyzer/cte_zonas.py`/`normativa/derivados.py::zona_climatica(codigo_ine)` ya existen, ya son la única fuente de esta tabla en todo el proyecto (el propio docstring de `cte_zonas.py` cuenta que antes había tres copias divergentes y se unificaron), y `normativa/derivados.py` ya tiene el punto de extensión previsto: *"Cuando exista un Fact de altitud, esto pasará a ser el [mecanismo real]"* — literalmente esperando esta pieza. Este PRD debe alimentar ESE hueco (altitud de la parcela → refinamiento del código INE que ya sale de `sitio_data`), no construir una segunda tabla climática paralela desde lat/lon.
- **"Vista más valiosa"**: no es determinísticamente calculable con los datos previstos en `2026-08-15-analisis-de-sitio.md` (que solo trae tags de OSM en un radio, sin modelo de elevación ni línea de visión) — ver §6, se redefine el objetivo a lo que sí es honesto hacer.
- **Contexto de sitio en el generador**: entra en el `SYSTEM_PROMPT` con la precedencia que le corresponde de verdad, no la que el encargo asume por defecto — ver §9, es la corrección más importante de este PRD.

## 5. Casos de uso

1. **Generación con contexto solar real**: el arquitecto ya analizó el sitio; al generar, el `SYSTEM_PROMPT` recibe la orientación óptima real de esa parcela (no la asunción genérica "sur es mejor" que ya trae `ai_generator.py` hoy).
2. **Entrevista con contexto de sitio**: el entrevistador pregunta con contexto ("la parcela tiene mejor orientación al sur — ¿priorizamos dormitorios ahí?") en vez de en el vacío — depende del mecanismo de siembra de §0.
3. **Resumen de entorno en el informe**: conectividad y equipamientos cercanos, con lo que de verdad se puede calcular (distancias reales), no con "vista"/"clasificación del entorno" presentadas como hechos cuando son heurísticas.

## 6. Casos límite

- **Colindante sin altura conocida** (caso ya documentado como frecuente en `2026-08-15-analisis-de-sitio.md`): la sombra de ESE colindante concreto no se calcula — se excluye del cálculo de horas de sol y se dice explícitamente ("sombra de 2 de 3 colindantes calculada; 1 sin altura conocida en OSM"), nunca se asume una altura media para no dejar un hueco.
- **Sin ningún colindante con altura conocida**: horas de sol se calculan solo por orientación geométrica de la parcela (sin obstrucción), con `confianza=Baja` y motivo explícito — sigue siendo mejor que nada, pero no se presenta como si incluyera sombras que no pudo calcular.
- **Altitud de la parcela desconocida** (`analyzer/sitio.py` no la trae — el servicio Catastro/INSPIRE consultado en ese PRD no incluye elevación): la zona climática CTE cae al valor por municipio de `cte_zonas.py` de siempre, SIN intentar refinarla — nunca una zona climática inventada por estimación de altitud a ojo. Obtener la altitud real es, en sí, una integración nueva (ver Riesgos) — no asumida como ya resuelta por tener coordenadas.
- **"Vista más valiosa" sin modelo de elevación**: se sustituye por un proxy explícito y débil ("hay una zona verde a menos de 100 m en dirección X" — un hecho geométrico real, no una afirmación sobre lo que se ve de verdad desde la parcela) — etiquetado en el propio dato como aproximación, igual que el proxy de accesibilidad del PRD del verificador.
- **El entrevistador ya preguntó sobre orientación antes de que el análisis de sitio estuviera disponible**: el análisis de sitio no reescribe una respuesta ya dada por el arquitecto — como mucho, se ofrece como contraste ("dijiste que priorizas el norte; la parcela tiene mejor sol al sur — ¿lo mantienes?"), nunca la sobrescribe en silencio.

## 7. Flujo del usuario

1. (Depende de `2026-08-15-analisis-de-sitio.md`) El arquitecto ya tiene `sitio_data` de la parcela.
2. ArchMuse calcula orientación solar real, horas de sol por fachada (con su confianza), zona climática (municipio, refinada por altitud si se consigue) y el resumen de entorno honesto (§6).
3. Si continúa a una entrevista: las preguntas relacionadas con orientación/prioridades de fachada se formulan con este contexto, sin sobrescribir respuestas ya dadas.
4. Si genera directamente: el `SYSTEM_PROMPT` recibe la orientación real como refinamiento de la regla de organización por defecto (nivel 3 de precedencia, no nivel 1 — ver §9), y el generador la usa igual que hoy usa la asunción genérica, pero con datos reales de esta parcela.

## 8. Criterios de aceptación

- Con datos de sitio completos (colindantes con altura conocida), las horas de sol estimadas por fachada varían según la posición real de los colindantes — no es la misma cifra para cualquier parcela con la misma orientación de fachada.
- Un colindante sin altura conocida queda excluido del cálculo, no aproximado — verificable en el `Hecho` resultante (motivo explícito).
- La zona climática CTE de un proyecto con sitio analizado es idéntica a la que ya daría `cte_zonas.get_zona_cte(ciudad)` cuando no hay altitud disponible — cero regresión del comportamiento actual.
- "Vista más valiosa" nunca aparece en el resultado como un hecho observado — solo como proximidad geométrica etiquetada como tal.
- Un proyecto generado con contexto de sitio real produce una justificación (`GeneratedProject.justificacion`) que cita la orientación real de esa parcela, no la frase genérica de siempre.
- El `SYSTEM_PROMPT` actualizado no rompe `tests/test_ai_generator_contexto.py` de forma no anotada (ver el hallazgo ya conocido de hoy sobre ese test).

## 9. Riesgos

- **Precedencia incorrecta si se implementa "tal cual" el encargo.** El encargo pide integrar esto "con la misma jerarquía de precedencia ya existente" sin decir cuál nivel — a diferencia de los parámetros de un pliego (que SÍ son nivel 1, restricción contractual/legal real), la orientación solar **no es normativa**: es una recomendación de diseño basada en física real de esta parcela. El `SYSTEM_PROMPT` de `ai_generator.py` YA tiene una regla de nivel 3 ("el salón/cocina y el dormitorio principal deben mirar preferentemente a sur/sureste/este") — este PRD debe **refinar esa regla con el dato real de la parcela**, no inyectarla como nivel 1 o nivel 2. Tratarla como nivel 1 le daría a una estimación (con su propia incertidumbre, §4) la misma autoridad inapelable que a la edificabilidad legal — un error de diseño, no un detalle menor.
- **Obtener la altitud real de la parcela es, en la práctica, otra integración externa nueva** (IGN u otro servicio de elevación) — no está en el alcance de `2026-08-15-analisis-de-sitio.md` tal como está escrito. Si se quiere refinamiento real de zona climática por altitud, hay que decidir explícitamente si se añade esa integración aquí, se dejar el refinamiento sin implementar (cae al valor por municipio, sin regresión) por ahora.
- **La precisión del cálculo de sombras depende enteramente de datos que `2026-08-15-analisis-de-sitio.md` ya documentó como incompletos** (`building:levels` de OSM) — este PRD no puede arreglar esa cobertura de datos, solo ser honesto sobre sus límites (§6).
- **"Vista más valiosa" y "clasificación del entorno" (consolidado/en desarrollo/periférico) son juicios de valor disfrazados de dato** si no se define una regla determinista explícita y documentada para cada uno — riesgo de que ArchMuse le diga a un arquitecto "vista de parque" basándose en que hay un polígono `leisure=park` a 400 m sin línea de visión real verificada.
- **Depende de una pieza de arquitectura (siembra del entrevistador) que ni siquiera está diseñada todavía** en el PRD del conector — no solo sin aprobar, sin diseño. Implementar la integración del punto 3 antes de que esa pieza exista significaría construirla dos veces.
- **No compite con `REFACTOR_MASTERPLAN.md`** — pero si se suman los 5 PRDs de pliego/sitio de hoy, sí compite por el mismo tiempo de desarrollo entre sí, y con la deuda de seguridad ya detectada esta mañana (`debug=True`) que sigue sin resolverse mientras se abren frentes nuevos.

## 10. Impacto sobre módulos existentes

- **`analyzer/sitio.py`** (una vez exista): `analizar_orientacion_solar`, `resumir_entorno` — nuevas funciones, mismo módulo.
- **`analyzer/hechos.py`**: se reutiliza `Hecho` para las horas de sol estimadas (no un float suelto) — sin cambios al propio módulo, solo un consumidor más.
- **`normativa/derivados.py`**: punto de extensión YA PREVISTO para altitud — si se implementa el refinamiento, es la única pieza que cambia para la zona climática, `analyzer/cte_zonas.py` no se toca.
- **`analyzer/ai_generator.py`**: el párrafo de orientación del `SYSTEM_PROMPT` (nivel 3, no nivel 1) se parametriza con el dato real cuando existe, conservando el texto genérico actual cuando no hay análisis de sitio — cero regresión para proyectos sin sitio analizado. `tests/test_ai_generator_contexto.py` necesita actualizarse a la vez (mismo cuidado que se pidió en el PRD del conector).
- **`analyzer/interview/`**: depende del mecanismo de siembra todavía sin diseñar (§0/§9) — no se puede detallar el impacto exacto hasta que ese diseño exista.
- **No toca** `evaluator.py` ni `pliego_verificador.py`.

## 11. Plan de implementación dividido en pequeñas tareas

*(Solo tiene sentido secuenciar esto una vez aprobado `2026-08-15-analisis-de-sitio.md` — se deja el desglose para cuando exista esa base real.)*

1. `analizar_orientacion_solar`: posición solar (declinación/altitud/azimut) para lat/lon + fecha del solsticio de invierno — sin colindantes todavía, solo geometría solar pura.
2. Proyección de sombra de cada colindante con altura conocida sobre la parcela, por hora — horas de sol por fachada como `Hecho` con confianza.
3. Refinamiento de zona climática por altitud en `normativa/derivados.py` — SOLO si se decide añadir la integración de elevación (§9); si no, tarea omitida explícitamente, no implementada a medias.
4. `resumir_entorno`: conectividad (distancia real a transporte) y proximidad geométrica etiquetada (no "vista real") — clasificación de entorno con regla explícita y documentada.
5. Parametrización del párrafo de orientación del `SYSTEM_PROMPT` (nivel 3) + actualización de `tests/test_ai_generator_contexto.py`.
6. Integración con el entrevistador — bloqueada hasta que exista el mecanismo de siembra compartido (§0).

## 12. Plan de pruebas

- Tests deterministas de posición solar contra valores astronómicos conocidos (p. ej. azimut/altitud solar de un lugar y fecha reales, verificables contra una tabla de referencia pública).
- Test de que un colindante sin altura queda excluido del cálculo de sombra, no aproximado.
- Test de que sin altitud disponible, la zona climática es bit a bit idéntica a la de `cte_zonas.get_zona_cte()` hoy.
- Test de que el `SYSTEM_PROMPT` sin datos de sitio es idéntico al actual (cero regresión).
- Sin llamadas a IA en ningún test de este módulo — es 100% software.

## 13. Métricas para medir el éxito

- % de generaciones con sitio analizado cuya justificación cita datos reales de orientación (frente a la frase genérica).
- Confianza media (`Hecho.confianza`) de las horas de sol estimadas en parcelas reales — mide si la cobertura de `building:levels` de OSM es suficiente para que esto aporte valor real, o si en la práctica casi todo sale con confianza Baja.

## 14. Posibles motivos para NO implementar la idea (ahora, en este alcance)

- **Depende de dos piezas que hoy no existen ni están aprobadas** (`analyzer/sitio.py`, el mecanismo de siembra del entrevistador) — aprobar este PRD hoy no permite empezar a trabajar en él hoy. Tiene sentido como PRD de intención, no como siguiente tarea de la cola.
- **"Vista más valiosa" y "clasificación del entorno" tal como se pidieron no son honestamente implementables** con los datos previstos — si se aprueban en su forma literal, ArchMuse terminaría presentando heurísticas débiles como observaciones, exactamente lo que el resto del proyecto (`Hecho`, `no_encontrado`, `no_verificable`) se ha esforzado en evitar hoy mismo en los tres PRDs anteriores.
- **Alternativa más barata y con menos riesgo de dato inventado**: implementar solo el cálculo solar real (tareas 1-2, sin refinamiento de altitud ni "vista") y la conectividad (parte de la tarea 4) en una primera versión — deja fuera la integración del entrevistador (bloqueada de todos modos) y cualquier cosa que dependa de datos que ArchMuse no tiene todavía. Es la parte de este PRD con mayor valor real y menor riesgo de inventar algo.

---

**Decisión:** _pendiente de revisión por Pablo_
