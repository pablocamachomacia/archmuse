# PRD — Conector pliego → generador y entrevistador

**Estado:** Caso de uso 1 (generación directa, §14 "alternativa más barata") implementado y con test de ruta HTTP en la suite de regresión — `analyzer/pliego_conector.py`, `POST /api/generar-desde-pliego`, `tests/test_pliego_conector.py` (26 comprobaciones, incluida la ruta HTTP completa con Claude mockeado). Probado con el JSON real de un pliego real (EMVS Berrocales). El resto de este PRD (§4.2-§11 completos: entrevistador, informe de cumplimiento) sigue sin aprobar. · **Fecha:** 2026-08-15 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-15, alcance reducido)

---

## 1. Problema que resuelve

`docs/prd/2026-08-15-extractor-parametros-pliego.md` (aprobado e implementado hoy mismo) extrae los parámetros de un pliego a un JSON revisable, pero se queda ahí: hoy nadie los usa. El arquitecto sigue teniendo que releer su propia tabla de revisión y volver a teclear cada cifra en el formulario de "Generar proyecto" o en la entrevista — el extractor evita el error de transcripción del pliego, pero no evita la transcripción en sí. Encargo directo de Pablo (2026-08-15), inmediatamente después de aprobar el extractor.

## 2. Usuario afectado

El mismo de `2026-08-15-extractor-parametros-pliego.md` §2: el arquitecto que participa en concursos con pliego formal — en el momento de pasar de "ya tengo el pliego leído por ArchMuse" a "quiero generar/entrevistar sobre este proyecto".

## 3. Objetivo de negocio

Cierra el círculo que el PRD del extractor dejó a medias: sin este conector, el extractor es una utilidad de lectura aislada, no una reducción real de fricción de entrada al generador (Pilar 4 de `MOAT_ANALYSIS.md`, línea 136 — la pieza que el PRD anterior identificó como el objetivo de negocio real). Sin este PRD, `2026-08-15-extractor-parametros-pliego.md` no termina de pagar la inversión que ya se hizo.

## 4. Objetivo técnico

1. Los parámetros del pliego que tienen equivalente directo en `params["normativa"]` (edificabilidad, altura máxima, retranqueos si el pliego los fija) entran ahí, ganando la precedencia de nivel 1 del `SYSTEM_PROMPT` de `ai_generator.py` ("la normativa urbanística indicada... SIEMPRE prevalecen") **sin tocar el texto del prompt** — es la vía de máxima precedencia que ya existe, no una nueva.
2. Los parámetros del pliego que NO tienen equivalente en `params["normativa"]` hoy (mix de tipologías por %, PEM máximo, régimen de protección, trasteros, accesibilidad, parking) se incorporan como una extensión nueva y explícita de ese mismo diccionario — no como directivas `fuerza="dura"` del canal `contexto_cualitativo` (Fase F): ese canal es precedencia de **nivel 2** ("DEBES CUMPLIR"), un escalón por debajo de "normativa", y el encargo original es explícito en que el pliego debe tratarse como máxima precedencia. Ver Riesgos, es la decisión de diseño más importante de este PRD.
3. Ningún parámetro de pliego llega a Claude en texto libre sin pasar antes por conversión determinista: `mix_tipologias` (porcentajes) se convierte en conteos absolutos de `mix_viviendas` (dorm_1/dorm_2/dorm_3) **en código, no en el prompt** — mismo principio ya fijado por Pablo el 2026-08-01: "que use software al máximo y IA lo mínimo".
4. El entrevistador (`analyzer/interview/`), cuando hay un pliego importado en la sesión, nunca vuelve a preguntar un campo cuyo `especificacion_id` ya tiene valor desde el pliego — reutiliza el mecanismo YA EXISTENTE `campo_tiene_respuesta()` (`motor.py`), no uno nuevo.
5. El informe final incluye una sección "Cumplimiento del pliego" que compara, campo a campo, lo pedido por el pliego contra lo generado — con la misma disciplina que `verificar_directivas_duras()`: `"cumple"` / `"no_cumple"` solo donde hay una comprobación geométrica real, `"no_verificable"` en el resto, nunca una casilla verde sin comprobación.

## 5. Casos de uso

1. **Generación directa desde pliego** (sin entrevista): el arquitecto importa el pliego en "Generar proyecto", revisa/corrige el JSON (ya implementado), pulsa "Generar con IA" — los campos del formulario que el pliego ya resolvió aparecen prellenados y bloqueados o marcados como "del pliego"; los que no, en blanco como hoy.
2. **Entrevista con pliego de fondo**: el arquitecto arranca una entrevista con un pliego ya importado. Preguntas como "¿cuántas viviendas?" o "¿qué plantas máximas permite la normativa?" no se hacen si el pliego ya las fija — el entrevistador avanza directo a lo que el pliego deja abierto (preferencias de diseño, relaciones espaciales, lo que un pliego nunca especifica).
3. **Informe con verificación de pliego**: tras generar, el informe muestra una tabla "Cumplimiento del pliego" — p. ej. "Nº de viviendas: pedía 20-30 → se generaron 24 → cumple", "Régimen de protección VPP → no verificable geométricamente, declarado por el arquitecto".

## 6. Casos límite

- **El pliego y una directiva del entrevistador se contradicen** (p. ej. el pliego fija régimen VPP, pero el arquitecto responde "sin restricción de protección" en la entrevista): el pliego gana siempre — es precedencia de nivel 1, la entrevista es como mucho nivel 2/4. Debe **mostrarse** el conflicto, no resolverse en silencio a favor de uno u otro (mismo criterio que `docs/prd/2026-08-14-cuadro-de-superficies-autocompletar.md` §6 con datos preexistentes del DXF).
- **Un campo del pliego llegó `UNKNOWN`** (no encontrado): se comporta exactamente como si no hubiera pliego para ese campo — el entrevistador sigue preguntándolo, el generador no recibe ninguna restricción de él.
- **El arquitecto corrigió a mano un valor en la tabla de revisión** (ya posible hoy, PRD del extractor): la corrección manual viaja igual que un valor `KNOWN` del pliego — no hay una tercera categoría "corregido por humano" con precedencia distinta.
- **`mix_tipologias` no cuadra al 100%** (porcentajes que no suman 100, o que no dividen exacto sobre `num_viviendas_minimo`/`maximo`): la conversión determinista debe declarar el redondeo que aplica (p. ej. "60% de 24 = 14,4 → 14") de forma trazable, no silenciosa — entra en el criterio de aceptación §8.
- **Se genera sin pliego** (flujo de hoy, sin cambios): cero diferencia de comportamiento — todo lo de este PRD es aditivo y condicionado a que exista un pliego importado en la sesión.

## 7. Flujo del usuario

1. (Ya implementado) Importa el pliego, revisa/corrige el JSON en la pantalla de "Generar proyecto".
2. Si continúa directo a "Generar con IA": los campos ya resueltos por el pliego se muestran prellenados con una marca "del pliego"; el resto, en blanco.
3. Si en cambio inicia una entrevista: el motor salta cualquier pregunta cuyo `especificacion_id` ya venga resuelto por el pliego, y se lo indica al arquitecto ("Esto ya lo fija el pliego: mix de tipologías — 60% de 2 dorm., 40% de 3 dorm.").
4. Genera el proyecto — el `SYSTEM_PROMPT` recibe los parámetros del pliego dentro de `params["normativa"]`, con la misma autoridad que hoy tienen edificabilidad/retranqueos.
5. En el informe generado, una sección nueva "Cumplimiento del pliego" lista cada parámetro, el valor generado, y si cumple / no cumple / no es verificable geométricamente.

## 8. Criterios de aceptación

- Con un pliego que fija `edificabilidad_maxima_m2` y `altura_maxima_plantas`, generar un proyecto produce un `params["normativa"]` con esos valores exactos, sin que el arquitecto los haya tecleado en el formulario.
- `mix_tipologias` (porcentajes) se convierte a conteos concretos de `mix_viviendas` de forma determinista y trazable (sin llamada a Claude para esta conversión), y la suma de la conversión nunca excede `num_viviendas_maximo` del pliego si éste existe.
- Con un pliego importado, iniciar una entrevista nunca vuelve a preguntar por un campo que el pliego ya resolvió con estado `KNOWN` — comprobable contando cuántas preguntas del catálogo se saltan frente a una entrevista sin pliego sobre el mismo proyecto.
- El informe final de un proyecto generado con pliego incluye "Cumplimiento del pliego"; uno generado sin pliego no muestra esa sección en absoluto (no una tabla vacía).
- Ningún parámetro de pliego con estado `UNKNOWN` llega nunca a `params["normativa"]` ni bloquea ninguna pregunta del entrevistador.
- Un conflicto entre el pliego y una respuesta posterior del arquitecto se muestra explícitamente en pantalla antes de generar, nunca se resuelve en silencio.

## 9. Riesgos

- **La decisión de precedencia del §4.2 es la pieza más delicada de este PRD.** Extender `params["normativa"]` con campos nuevos obliga a tocar el texto del `SYSTEM_PROMPT` (añadir esos campos a la lista de "normativa urbanística" del punto 1 de PRECEDENCIA ENTRE REGLAS) — un cambio de prompt en un módulo que ya tiene un test (`tests/test_ai_generator_contexto.py`) comparando el `SYSTEM_PROMPT` contra el commit anterior; ese test es autodocumentadamente frágil durante esta fase (ver hallazgo de la auditoría de hoy) y hay que actualizarlo a la vez, no dejarlo roto.
- **`verificar_directivas_duras()` hoy solo sabe comprobar accesibilidad** (Fase F). "Cumplimiento del pliego" necesita comprobaciones nuevas (nº de viviendas generadas, edificabilidad realmente consumida, superficies por tipología) — son geométricamente triviales de calcular (software puro, no IA, coherente con la filosofía de Pablo), pero es trabajo real de `evaluator.py`/`ai_generator.py`, no una reutilización directa de lo que ya existe.
- **Compite con la Fase F ya en curso** (`GeneratedProject.directivas_aplicadas`/`verificaciones_directivas`, `contexto_cualitativo`): este PRD añade una SEGUNDA vía de entrada de restricciones a `ai_generator.py` (pliego, además de las directivas del entrevistador). Hay que dejar clara la relación entre ambas (§4.2 ya lo intenta) para no terminar con dos mecanismos de "restricción externa" que se pisan.
- **Alcance no trivial para "un PRD más"**: toca `ai_generator.py` (SYSTEM_PROMPT + `params`), `analyzer/interview/motor.py` y `preguntas.py` (o el mecanismo de seed de `EstadoEntrevista`), `analyzer/interview/compilador.py` (`compilar_params`), `pdf_report.py`/`api_serializer.py` (sección nueva del informe) y `evaluator.py` (comprobaciones de cumplimiento nuevas) — cinco módulos, no uno. Vale la pena partirlo en sub-fases (ver §11) en vez de aprobarlo como un bloque monolítico.

## 10. Impacto sobre módulos existentes

- **`analyzer/ai_generator.py`**: `params["normativa"]` gana campos opcionales nuevos (`mix_tipologias_convertido`, `pem_maximo_euros`, `regimen_proteccion`, etc. — nombres exactos a definir en implementación); el párrafo 1 de "PRECEDENCIA ENTRE REGLAS" del `SYSTEM_PROMPT` se actualiza para nombrarlos. `verificar_directivas_duras()` (o una función hermana `verificar_cumplimiento_pliego()`) gana comprobaciones nuevas.
- **`analyzer/interview/motor.py`/`preguntas.py`**: necesita una vía para "sembrar" `EstadoEntrevista` con respuestas que no vinieron de una pregunta (vienen del pliego) — hoy toda `RespuestaInterpretada` nace de `siguiente_pregunta()`/`interpretar_*`; esto es una tercera vía de entrada que no existe todavía y hay que diseñarla con cuidado para no romper el invariante de que cada entrada queda con procedencia trazable (Hecho/Inferencia/Hipótesis/Preferencia, `claude_interprete.py` regla 2) — un valor del pliego es más parecido a un Hecho declarado por escrito que a nada de lo que el catálogo actual distingue.
- **`analyzer/interview/compilador.py`**: `compilar_params()` tiene que saber fusionar lo que viene del pliego con lo que viene de la entrevista, respetando la precedencia del §4.
- **`analyzer/pdf_report.py`/`analyzer/api_serializer.py`**: sección nueva "Cumplimiento del pliego", condicionada a que el proyecto tenga un `pliego_id` enlazado (`storage.vincular_pliego_proyecto`, ya implementado hoy pero sin ningún llamador todavía — este PRD sería el primero en usarlo).
- **`analyzer/storage.py`**: no necesita esquema nuevo — `pliegos.proyecto_id` y `vincular_pliego_proyecto()` ya existen, a la espera de que algo los use.
- **No toca** `analyzer/pliego_extractor.py` ni el endpoint `/api/extraer-pliego` — el extractor queda tal cual, este PRD solo consume su salida.

## 11. Plan de implementación dividido en pequeñas tareas

1. Definir la forma exacta de los campos nuevos en `params["normativa"]` (nombres, unidades) y actualizar el `SYSTEM_PROMPT` + `tests/test_ai_generator_contexto.py` a la vez.
2. Función determinista `convertir_mix_tipologias(mix_tipologias, num_viviendas) -> dict` (redondeo trazable, sin IA) en un módulo nuevo o en `ai_generator.py`.
3. `app.py`: al pulsar "Generar con IA" con un pliego importado en la sesión, construir `params["normativa"]` fusionando formulario + pliego (pliego gana en conflicto).
4. Mecanismo de "siembra" de `EstadoEntrevista` desde un pliego (diseño en `analyzer/interview/modelo.py`/`motor.py`).
5. `siguiente_pregunta()`: verificar que `campo_tiene_respuesta()` ya basta para saltar preguntas sembradas — si no, extender.
6. `compilar_params()`: fusión pliego + entrevista con precedencia correcta.
7. Comprobaciones deterministas de cumplimiento nuevas en `evaluator.py` (nº viviendas, edificabilidad consumida, superficies por tipología).
8. Sección "Cumplimiento del pliego" en `api_serializer.py` + `pdf_report.py`.
9. Primer uso real de `vincular_pliego_proyecto()`, al generar un proyecto desde un pliego.
10. Tests de extremo a extremo: generación con pliego, entrevista con pliego, informe con sección de cumplimiento.

## 12. Plan de pruebas

- Tests deterministas para `convertir_mix_tipologias` (redondeos, casos borde de porcentajes que no suman 100).
- Test de que `params["normativa"]` fusionado prevalece sobre el formulario cuando hay conflicto.
- Test de que una entrevista con pliego sembrado salta las preguntas correctas (comparando el nº de turnos con/sin pliego sobre el mismo `EspecificacionArquitectonica` objetivo).
- Test de la sección "Cumplimiento del pliego": un proyecto generado a propósito para incumplir un límite del pliego debe mostrar `"no_cumple"`, no `"cumple"` ni ausencia de la fila.
- Ninguno de estos tests llama a la IA real salvo los ya gated tras `ARCHMUSE_TEST_IA=1` de `ai_generator.py`.

## 13. Métricas para medir el éxito

- % de campos de `params["normativa"]` que llegan prellenados desde el pliego en generaciones reales con pliego importado.
- Nº de preguntas de entrevista saltadas por sesión con pliego, frente a sin pliego, para el mismo tipo de proyecto.
- % de proyectos generados con pliego cuya sección "Cumplimiento" no muestra ningún `"no_cumple"` (proxy de si el generador respeta de verdad la restricción de nivel 1).

## 14. Posibles motivos para NO implementar la idea (ahora, en este alcance)

- **Alcance real más grande que "conectar dos piezas ya hechas".** Toca cinco módulos y añade una tercera vía de entrada al entrevistador (pliego, junto a pregunta-guiada y texto-libre-interpretado) que no existía en su diseño original — no es un cableado trivial entre el extractor y el generador, aunque el encargo lo describa en esos términos.
- **Depende de que el extractor de pliegos demuestre valor real primero.** Si, tras usar el extractor unos días, resulta que pocos pliegos reales llegan a `KNOWN` en los campos que de verdad importan (ver métricas del PRD anterior, §13), este conector estaría construyendo una integración cara sobre una fuente de datos que en la práctica sigue exigiendo revisión manual casi completa — en ese caso el valor real está en mejorar la extracción, no en conectarla antes de tiempo.
- **Alternativa más barata**: empezar solo por el caso de uso 1 (generación directa, sin entrevista) — tareas 1-3 de §11 — y dejar el entrevistador (tareas 4-6) y el informe de cumplimiento (tareas 7-8) para una segunda aprobación, una vez visto si el primer tramo se usa de verdad. Se deja como alternativa explícita, no como recomendación por defecto, porque Pablo pidió las tres piezas juntas — mi recomendación si hay que elegir una secuencia es esta partición, no bloquear el conjunto.

---

**Decisión:** _pendiente de revisión por Pablo_
