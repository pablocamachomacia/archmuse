# PRD — Descomposición de candidatas compuestas en el pipeline de borradores

**Estado:** Implementado · **Fecha:** 2026-08-21 · **Fecha de cierre:** 2026-08-21 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-21, alcance completo del §11)

---

## 1. Problema que resuelve

El Prompt 1 (`docs/prd/2026-08-21-pipeline-borradores-corpus-db-sua.md`) convirtió 3 de 20 candidatas reales de DB-SUA. 8 de las 17 descartadas (el motivo dominante) lo fueron por `multiples_exigencias_agrupadas`: el artículo agrupa varias exigencias verificables bajo un único segmento, y ese PRD decidió explícitamente no auto-dividirlas, citando `extraccion/modelo.py::ReglaCandidata` ("exige criterio del Curador... a veces cruzar varios artículos").

Sin curador (decisión de Pablo, 2026-08-21), esa frontera deja el pipeline convergiendo permanentemente a una tasa de conversión baja: la mayoría del articulado real del CTE agrupa varias exigencias bajo un mismo epígrafe. Origen de esta petición: Pablo, directamente, con restricciones explícitas de seguridad ("no inventar fronteras") y criterio de terminado verificable.

## 2. Usuario afectado

El mismo que el Prompt 1: Pablo como operador del pipeline y revisor de pendientes; indirectamente, el arquitecto usuario de la futura Skill `revision_normativa`.

## 3. Objetivo de negocio

Subir la tasa de conversión del corpus sin bajar el nivel de exigencia sobre lo que se convierte — es la misma apuesta que sustituye al curador: procedencia verificable en vez de confianza en una firma.

## 4. Objetivo técnico

Dado un artículo compuesto, producir automáticamente las sub-exigencias que el propio texto ya distingue sin ambigüedad, y dejar en pendientes exactamente las que exigen resolver una condición entrelazada o una remisión — nunca las que "probablemente" se puedan separar.

## 5. Diseño (ya verificado contra las 8 candidatas reales, no hipotético)

Cada `parametros[i]` de una candidata ya viene con su propio `contexto_citado` (la cláusula exacta de la que se extrajo). El paso nuevo:

1. **Localizar** cada `contexto_citado` dentro de `texto_original` por subcadena, con normalización de espacios (el PDF trae saltos de línea y guionizado a media palabra: `"co n-\nsecuencia"`). Si no se localiza, esa candidata entera va a pendientes — no se decide nada sobre datos que no se pueden anclar.
2. **Agrupar** los parámetros cuyos `contexto_citado` caen en la misma cláusula/frase del texto (por solape o proximidad de posición, delimitada por los propios marcadores del CTE: punto y aparte, o el siguiente marcador de enumeración `a)/b)/c)…` o número de apartado `1 2 3…`).
3. Un grupo de **exactamente un parámetro**, sin marcador de remisión en su cláusula (regex sobre `apartado \d`, `sección SUA`, `anejo`, `según`, `conforme a`, `lo (dispuesto|establecido|especificado) en`, `párrafo \d`) → **sub-candidata atómica**, convertible por el pipeline existente del Prompt 1 sin tocarlo.
4. Un grupo de **dos o más parámetros en la misma cláusula**, o con marcador de remisión → **sigue en pendientes**, pero como sub-candidata más pequeña y mejor acotada que el artículo entero (ver §6, motivo `condicion_compuesta_no_atomica` o `remision_a_otro_apartado`, no ya el genérico `multiples_exigencias_agrupadas`).
5. Todo sub-candidata, convertida o pendiente, lleva `candidata_padre` (el `articulo` original) y `criterio_particion` (qué regla la generó) — trazabilidad bidireccional pedida.
6. La cita literal de cada sub-candidata es **siempre `texto_original` completo del padre**, nunca un recorte — la atomización es de la exigencia, no de la fuente. Ya es así en el Prompt 1 (`norma.literal`); este paso no lo cambia.

**Prueba de que la frontera "por letra" no basta** (razón de diseño, no hipótesis): en DB-SUA 1.2, el item `a)` agrupa 4 parámetros relacionados (resalto, saliente, ángulo) y el item `b)` agrupa 2 en una condición explícitamente enlazada ("desniveles ≤5cm se resuelven con pendiente ≤25%" es UNA exigencia con dos cifras, no dos). Partir por letra las trataría como atómicas y mentiría sobre la estructura real. Por eso el criterio de agrupación es por cláusula/solape de `contexto_citado`, no por el marcador de enumeración en sí — el marcador solo ayuda a poner límites entre cláusulas, nunca certifica atomicidad por sí solo.

## 6. Casos límite

- Cláusula con remisión pero un solo parámetro (DB-SUA 7.3, `desnivel_itinerario_peatonal`: "55 cm... se protegerá conforme a lo que se establece en el apartado 3.2 de la sección SUA 1") → a pendientes con motivo `remision_a_otro_apartado`, aunque numéricamente sea limpio: la obligación real depende de otro artículo que este pipeline no tiene todavía.
- `contexto_citado` no localizable en `texto_original` (no debería ocurrir tras `cifras_verificadas_en_texto`, pero esa señal solo verifica `valor_citado`, no `contexto_citado` completo) → motivo `contexto_no_localizable`, a pendientes.
- Candidatas con `parametros: []` (las 8 de motivo `sin_parametros_extraidos`) no tienen nada que agrupar — quedan exactamente igual que en el Prompt 1, este paso no las toca. Confirmado con el propio prompt de Pablo: pide "que ningún motivo de descarte restante sea «artículo compuesto»", no "cero pendientes".
- Tabla 2.1 de DB-SUA 8.2 (rayo): 4 parámetros, cada uno una fila de tabla con su propio rango — mismo criterio: si cada fila es su propia cláusula sin remisión cruzada entre filas, se separan; si las filas comparten fórmula/contexto (la nota (1) de la tabla condiciona la fila 4), esa fila concreta va a pendientes y las demás no.

## 7. Flujo del usuario

Sin cambios de interfaz: mismo `scripts/generar_borrador_corpus.py`, con el paso de descomposición insertado antes de la clasificación existente. Pablo sigue revisando pendientes igual que en el Prompt 1.

## 8. Criterios de aceptación

Los del encargo de Pablo, literalmente:
- Las 17 pendientes originales vuelven a pasar por el pipeline completo con el paso nuevo.
- Tabla con: sub-candidatas generadas, cuántas convierten a BORRADOR, cuántas siguen pendientes y por qué.
- Ningún motivo de descarte restante es "artículo compuesto" (el genérico `multiples_exigencias_agrupadas` desaparece; lo que quede tiene un motivo específico que sí exige juicio humano: remisión, condición entrelazada, o sin cifra localizable).
- Tasa de conversión sobre las 20 candidatas originales sube de forma medible.
- Golden: ≥2 descomposiciones reales (una enumeración, una tabla) + test de que la cita literal del padre está íntegra en cada hija.
- Suite completa verde.

## 9. Riesgos

**El riesgo central ya está mitigado por diseño, no es residual:** agrupar por solape de cláusula (no por marcador de enumeración) es precisamente lo que evita partir DB-SUA 1.2-b) en dos mentiras independientes. Sigue habiendo un riesgo de calibración: el regex de remisión (`apartado`, `conforme a`, etc.) puede tener falsos negativos sobre artículos de otros DB que este PRD no ha visto todavía — se acota explícitamente a DB-SUA por ahora, igual que el Prompt 1.

**Riesgo de falsos positivos "atómicos":** si dos parámetros de cláusulas distintas comparten en realidad una condición que el texto no expresa con un conector léxico reconocible (p. ej. dependencia implícita por contexto narrativo, no por "conforme a"), el heurístico no la detecta. Mitigación: cada sub-candidata convertida sigue siendo `BORRADOR` (una sola ruta, sin verificar) — el Prompt 2 (transcripción doble) es el que la promovería, y ahí es donde una descomposición mal hecha divergería entre las dos rutas y caería a pendientes-de-humano. La descomposición no se salta esa red.

**No compite con REFACTOR_MASTERPLAN.md:** es corpus, no endurecimiento de producto.

## 10. Impacto sobre módulos existentes

- `scripts/generar_borrador_corpus.py`: nueva función de descomposición antes de `_decidir()`; `_decidir()` y `_construir_documento()` no cambian de contrato, se les pasa una sub-candidata en vez de la candidata original.
- No toca `normativa/esquema/`, `normativa/resolucion.py` ni el esquema de `regla.schema.json` — las sub-candidatas convertidas son candidatas normales para el resto del pipeline ya construido.
- `extraccion/estado/pendientes/*.jsonl`: cambia de forma (sub-candidatas en vez de candidatas completas), con `candidata_padre` y `criterio_particion` añadidos — aditivo, no rompe el fichero de pendientes ya generado (se regenera).

## 11. Plan de implementación

1. Localización robusta de `contexto_citado` en `texto_original` (normalización de espacios/guionizado) + test unitario contra las 30 cláusulas reales de las 8 candidatas. (≤2h)
2. Agrupación por solape/proximidad de cláusula, delimitada por marcadores de enumeración y puntuación. (≤2h)
3. Detección de remisión (regex) + categorización de motivo específico por grupo no atómico. (≤1h)
4. `criterio_particion` + `candidata_padre` en cada sub-candidata; construcción de la sub-candidata reutilizando el resto de campos del padre (misma `documento_identificador`, `materia_sugerida`, etc., salvo `parametros` recortado al grupo). (≤2h)
5. Integración en `scripts/generar_borrador_corpus.py`: paso de descomposición antes de `_decidir()`, iterando sub-candidatas en vez de candidatas planas. (≤1h)
6. Re-ejecución sobre las 17 pendientes reales + tabla de resultados. (≤1h)
7. Golden tests (2 descomposiciones reales) + test de integridad de la cita literal. (≤2h)

## 12. Plan de pruebas

- Golden: DB-SUA 1.2 (enumeración a/b/c, con el caso adversarial de b) que NO debe partirse) y DB-SUA 8.2 (tabla 2.1).
- Test de integridad: cada sub-candidata generada, convertida o pendiente, tiene `texto_original` == literal completo del padre.
- Test de no regresión: las 3 conversiones del Prompt 1 (candidatas ya atómicas) no cambian con el paso nuevo.
- Suite completa.

## 13. Métricas de éxito

Tasa de conversión sobre las 20 candidatas de DB-SUA (antes: 3/20 = 15%); tabla de motivos restantes, ninguno genérico.

## 14. Posibles motivos para NO implementarlo

Podría posponerse hasta tener más DBs y calibrar el heurístico de remisión contra un corpus mayor, en vez de sobre-ajustarlo a las 8 candidatas de DB-SUA. No lo recomiendo: el criterio de agrupación por solape de cláusula no es específico de DB-SUA (es sintáctico, no de contenido), y esperar deja el pipeline del Prompt 1 con retorno bajo indefinidamente. Alternativa descartada: forzar la partición por letra a)/b)/c) sin comprobar solape — más simple, pero ya demostrado falso sobre datos reales (§5).

---

## Cierre (2026-08-21)

Las 7 tareas del §11 completas. Resultado sobre las 20 candidatas reales de
DB-SUA:

| Artículo | Convertidas | Pendientes (motivo × nº params) |
|---|---|---|
| 1.1 Resbaladicidad | 0 | sin_parametros_extraidos |
| 1.2 Discontinuidades en el pavimento | **2** | condicion_compuesta_no_atomica×2, contexto_no_localizable×4 |
| 1.3 Desniveles | 0 | sin_parametros_extraidos |
| 1.4 Escaleras y rampas | 0 | materia_ausente_o_fuera_de_catalogo |
| 1.5 Limpieza de acristalamientos | **1** | condicion_compuesta_no_atomica×2 |
| 2.1 Impacto | 0 | sin_parametros_extraidos |
| 2.2 Atrapamiento | **1** (Prompt 1) | — |
| 3.1 Aprisionamiento | 0 | remision_a_otro_apartado×2, contexto_no_localizable×1 |
| 4.1 Alumbrado normal | **1** | condicion_compuesta_no_atomica×2, contexto_no_localizable×1 |
| 4.2 Alumbrado de emergencia | 0 | materia_incoherente_con_documento |
| 5.1 Ámbito graderíos | **1** (Prompt 1) | — |
| 5.2 Condiciones graderíos | 0 | sin_parametros_extraidos |
| 7.1 Ámbito aparcamiento | **1** (Prompt 1) | — |
| 7.2 Características constructivas | 0 | posible_cifra_adicional_no_extraida×1, remision_a_otro_apartado×1, contexto_no_localizable×2 |
| 7.3 Protección recorridos peatonales | 0 | posible_cifra_adicional_no_extraida×1, contexto_no_localizable×4 |
| 7.4 Señalización | 0 | sin_patron_evaluable |
| 8.1 Procedimiento de verificación | 0 | sin_parametros_extraidos |
| 8.2 Tipo de instalación (tabla 2.1) | 0 | contexto_no_localizable×4 |
| 9.1 Condiciones de accesibilidad | 0 | sin_parametros_extraidos |
| 9.2 Señalización accesibilidad | 0 | remision_a_otro_apartado×1, contexto_no_localizable×5 |
| **Total** | **7 / 20 (35 %)** | 31 sub-candidatas generadas, 24 pendientes |

Tasa de conversión: **3/20 (15 %) → 7/20 (35 %)**, más del doble. Ningún
motivo restante es "artículo compuesto" — los 8 motivos que quedan
(`sin_parametros_extraidos`, `condicion_compuesta_no_atomica`,
`remision_a_otro_apartado`, `contexto_no_localizable`,
`posible_cifra_adicional_no_extraida`, `materia_ausente_o_fuera_de_catalogo`,
`materia_incoherente_con_documento`, `sin_patron_evaluable`) son todos
específicos y exigen mirar el PDF, no inferir.

**Hallazgo de la implementación que el PRD no anticipaba, y por qué importa
más que la cifra de conversión:** el diseño original (§5) agrupaba por
solape de cláusula y confiaba en que "un grupo de un solo parámetro" fuera
sinónimo de "cifra independiente". Al ejecutar contra las 20 candidatas
reales, DB-SUA 7.3 lo desmintió: cita «capacidad > 200 vehículos **o**
superficie > 5000 m²» — una disyunción real, confirmada por las propias
`excepciones` de la candidata — pero solo `capacidad_aparcamiento` se pudo
anclar en el texto (`superficie_aparcamiento` cae a «superficie m ayor»,
guionizado del PDF). Sin corrección, el pipeline habría convertido
`capacidad_aparcamiento` como umbral incondicional — exactamente el error
que el PRD existe para evitar, solo que producido por una cláusula rota en
vez de por partir mal una letra. Añadí `_contar_cifras_de_umbral`: cuenta
cifras de diseño en la cláusula de un grupo de un solo parámetro (excluyendo
referencias a figuras/tablas/apartados y marcadores de artículo tipo «5
Limpieza...»); si da más de 1, no se convierte sola. Esto bajó la cifra de
9 a 7 conversiones — el PRD pedía "sube de forma medible", no "maximiza",
y 7/20 sigue siendo más del doble del punto de partida sin el riesgo de
DB-SUA 7.3. Tests dedicados:
`test_no_convierte_capacidad_aparcamiento_sola_por_ser_mitad_de_una_disyuncion`
y `test_no_convierte_pendiente_sola_por_venir_con_profundidad_en_la_misma_frase`.

Suite completa: 1179 passed, 18 skipped, 1 xfailed. Mismos 2 fallos
preexistentes de la sesión anterior (registro de capacidades, techo C4),
no tocados.

**Decisión:** Aprobado por Pablo, 2026-08-21. Alcance: las 7 tareas del §11.
