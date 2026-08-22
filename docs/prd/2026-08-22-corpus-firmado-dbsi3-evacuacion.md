# PRD — Corpus firmado: paquete DB-SI 3 evacuación (Residencial Vivienda)

**Estado:** Aprobado · **Fecha:** 2026-08-22 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-22, aprobación del plan `/ultraplan` en sesión; las tres decisiones de la §11.0 las tomó Pablo explícitamente vía pregunta directa)

---

## 1. Problema que resuelve

El corpus servible tiene hoy **una** regla (`normativa/es/estatal/seguridad_incendio.yaml`, DB-SI 3 tabla 3.1), sin firmar, gobernada por el tag `pendiente_firma_colegiado`. Consecuencia directa: la skill `revision.recorridos_de_evacuacion` funciona técnicamente de punta a punta pero cada respuesta declara «el resultado es un ejemplo trabajado, no una comprobación normativa validada». Toda la verificación de normativa de ArchMuse está bloqueada por contenido, no por código.

Origen: petición directa de Pablo (2026-08-22). Dato nuevo que lo desbloquea: **el lunes 25 un arquitecto colegiado con 25 años de ejercicio y una coordinadora del comité de Eurocódigos de AENOR pueden empezar a validar reglas** (calendario corregido por Pablo el 2026-08-22: sesión el lunes 25, no el domingo 24).

Hallazgo de la exploración previa que reencuadra el problema: **la fase de firma ya está implementada y nunca ejecutada.** `regla.schema.json` tiene `estado: [BORRADOR, VERIFICADA_AUTOMATICA, FIRMADA, null]` y el bloque `firma:{curador,fecha}`; la validación 19 existe; `scripts/curar_corpus.py` tiene `resolver`/`firmar` (PRD 2026-08-21, cerrado, verificado contra fixtures DB-SUA). No hay ninguna regla `FIRMADA` en disco y `extraccion/estado/curacion/` no existe. Este PRD no diseña la firma: **la ejecuta por primera vez, cierra sus huecos (integridad post-firma, conflicto Modelo A/B) y construye la pieza que falta (el artefacto de revisión en papel).**

## 2. Usuario afectado

- **Inmediato:** Pablo como curador del corpus, y los dos validadores externos de la sesión del domingo.
- **Final:** el arquitecto usuario de ArchMuse, que a partir del martes 26 recibe por primera vez una comprobación normativa afirmada con cita, no un ejemplo trabajado.

## 3. Objetivo de negocio

El corpus firmado es el foso real (`MOAT_ANALYSIS.md`): las reglas son copiables, un corpus **validado por un colegiado con registro nominal, acta firmada y trazabilidad criptográfica** no lo es. Además desbloquea `NOR-2` (backlog P0) y la cadena de skills bloqueadas por él (`SK-7`). Es el paso de «el estante» (PRD 2026-08-06) a «los primeros libros».

## 4. Objetivo técnico

Comportamiento observable tras implementar:

1. Existen 10-15 reglas de evacuación DB-SI 3 (uso Residencial Vivienda) con `estado: FIRMADA`, bloque `firma` completo y hash de contenido, visibles para el loader y afirmables por el motor.
2. La skill `revision.recorridos_de_evacuacion` responde umbral/holgura/cumple con cita BOE-A-2006-5515 **sin** el `no_hecho` de firma pendiente — **sin cambiar una línea de la skill ni de sus capacidades** (contrato G11 intacto).
3. Editar un solo valor de una regla firmada hace que el loader rechace el fichero en la siguiente carga (validación 20) y la materia caiga a `sin_cobertura` — fail-closed, nunca silencio.
4. Cada regla firmada es trazable: acta en papel escaneada → ledger append-only → YAML con hash → git.

## 5. Casos de uso

1. **Sesión de validación (lunes 25):** los validadores revisan una hoja impresa de una página por paquete (no YAML), marcan conforme (F/L/M), corrigen al margen o tachan, y firman de puño y letra.
2. **Volcado (martes 26):** Pablo transcribe el acta al ledger (`curacion/volcar_acta.py transcribir`) y firma (`… firmar --curador`), que escribe las reglas `FIRMADA` en `normativa/es/estatal/`.
3. **Consulta del arquitecto usuario:** pregunta por un recorrido medido; la skill afirma con cita y sin caveat.
4. **Auditoría posterior:** un tercero coteja acta escaneada ↔ ledger ↔ hash del YAML ↔ literal ↔ PDF oficial (`documento_sha256`).

## 6. Casos límite

- **El borrador cambió después de imprimir la hoja:** `firmar` recomputa la huella y la exige igual a la del ledger; si difiere, se niega — el papel manda (test T8).
- **Fila corregida al margen:** se firma el valor corregido (decisión de Pablo); el ledger conserva valor original y corrección.
- **Fila tachada:** vuelve a borrador `_paquete_*` invisible; el paquete cierra con menos reglas — mejor 6 honestas que 15 forzadas.
- **Regla firmada editada a mano después:** validación 20 rechaza el fichero → materia `sin_cobertura` (test T2). Quien altere regla+hash a la vez queda delatado por el acta y por git.
- **Destino ya existe al firmar:** conflicto y sigue, nunca sobrescribe (inmutabilidad, mismo contrato que `curar_corpus.py`) (test T9).
- **Regla FIRMADA sin hash (formato del PRD cerrado del 21-08):** tolerada esta semana (fase 1), rechazada desde el jueves (fase 2). No existirá nunca una así en producción — sin backfill.
- **`estado: None` sin tag (hueco del corpus ficticio):** lo cierra el test de política T7 sobre el corpus real, no el esquema (el `corpus_ficticio/` congelado depende de ese hueco).

## 7. Flujo del usuario

Viernes 22: transcripción de borradores `_paquete_dbsi3_*.yaml` desde `tests/fixtures/codigotecnico/DB-SI.pdf` con la ficha (que este PRD promueve a aprobada) + lista de dudas → Sábado 23: herramientas (`normativa/firma.py`, validación 20, paquete `curacion/`), hoja impresa → Domingo 24 (colchón): ensayo de lectura con la piloto, revisión final de la hoja → Lunes 25: sesión de validación en papel, firmas manuscritas, escaneo a `docs/curacion/actas/` → Martes 26: transcribir acta a ledger, firmar, supersede de la piloto, manifiesto a `parcial`, suite en verde → la skill afirma.

## 8. Criterios de aceptación

1. `python scripts/validar_corpus.py` limpio con las reglas firmadas cargadas (0 rechazos, 0 fallos `[14]`).
2. Demo de la skill con un recorrido medido: umbral con cita BOE-A-2006-5515, `pendiente_de_firma_colegiada: False`, sin el `no_hecho` de firma.
3. Prueba de manipulación en vivo: editar un valor firmado → `[20]` y materia caída (revertir con git).
4. Tests T1-T10 en verde; `test_corpus_sin_firmar.py:143` sustituido por su invariante permanente; suite completa en verde.
5. Acta escaneada comiteada y cada regla firmada enlazada a ella vía `firma.validado_por[].acta`.
6. Nada de `analyzer/`, `scripts/` ni `tests/fixtures/` modificado antes del jueves 28.

## 9. Riesgos

- **El camino crítico es humano:** si el domingo se valida menos de lo previsto, degrada con gracia (se firma lo conforme; basta 1 regla para promover a `parcial`). El único fallo irrecuperable es firmar deprisa algo mal transcrito — la ficha lo dice: «una regla mal transcrita es peor que una regla ausente».
- **Validación 14 es global:** un choque de aplicabilidad vacía TODO el corpus. Mitigación: aplicabilidad específica por regla (`usos`) + claves distintas por `norma.articulo`+`nombre` (resolución del 21-08) + `validar_corpus.py` antes de comitear.
- **Colisión con las firmas del PRD cerrado del 21-08:** el esquema se amplía de forma aditiva (hash y `validado_por` opcionales hasta el jueves) para que los 26+1 tests del script congelado sigan en verde.
- Compite por tiempo con el resto del backlog: sí, y es P0 (`NOR-2`) — nada en `REFACTOR_MASTERPLAN.md` está por delante de esto esta semana.

## 10. Impacto sobre módulos existentes

- **Modificados:** `normativa/esquema/regla.schema.json` (aditivo), `normativa/validacion.py` (validación 20), `normativa/cobertura/manifiesto.yaml` (lunes → `parcial`), `normativa/es/estatal/seguridad_incendio.yaml` (renombrado supersede `_superseded_*`, `registro_hasta`), `tests/test_corpus_sin_firmar.py` y `tests/test_normativa_aplicable.py` (lunes).
- **Nuevos:** `normativa/firma.py`; paquete `curacion/` (raíz, fuera del congelado `scripts/`); borradores y reglas firmadas en `normativa/es/estatal/`; `docs/curacion/` (hoja + actas); `extraccion/estado/curacion/actas_papel.jsonl`; 3 ficheros de test.
- **Cero cambios:** `agente/skills/evacuacion.py`, `agente/herramientas/reglas.py` (el flag `pendiente_de_firma_colegiada` cae solo al desaparecer el tag), todo `analyzer/`, todo `scripts/` (se ejecutan, no se tocan), `tests/fixtures/`.
- **Consumidores indirectos:** el manifiesto derivado y `resolucion._paso1_candidatas` ya contemplan `FIRMADA`; `test_normativa_manifiesto_deriva.py` sigue en verde sin tocar.

## 11. Plan de implementación dividido en pequeñas tareas

### 11.0 Decisiones ya tomadas por Pablo (2026-08-22)

1. **Semántica de la firma:** `firma.curador` = Pablo (compatible byte a byte con el PRD cerrado); nuevo campo opcional `firma.validado_por` (lista: nombre, rol del catálogo `arquitecto_colegiado|experto_normativo|curador_interno`, colegiatura opcional, fecha, ruta del acta). **No revierte la decisión del 21-08**: nadie externo opera herramientas ni firma digitalmente; se añade el registro nominal de la validación externa que el Modelo A pedía. El tag y la validación 18 no se derogan: siguen gobernando lo no firmado.
2. **Correcciones al margen:** una fila corregida y rubricada se firma directamente con el valor corregido; el ledger conserva ambos valores.
3. **Supersede de la piloto:** martes 26 (día del volcado), con renombrado a `_superseded_*` + `registro_hasta` (invisible, nunca borrado); la corrección de fondo (validación 14 bitemporal) el jueves.

### 11.1 Tareas (≤2h cada una)

| # | Día | Tarea |
|---|---|---|
| 1 | V | Este PRD + promover la ficha del 18-08 de «propuesta» a «aprobada» |
| 2 | V | Transcribir bloque 1: retranscripción tabla 3.1 (`@2`, mismo `concept_id`) + nº de salidas por planta |
| 3 | V | Transcribir bloque 2: definiciones Anejo A (origen de evacuación, espacio exterior seguro, altura de evacuación) como `tipo: definicion` |
| 4 | V | Transcribir bloque 3: tabla 4.1 dimensionado (puertas/pasos, pasillos, escaleras) + anchuras mínimas |
| 5 | V | Transcribir bloque 4: tabla 5.1 protección de escaleras + condiciones particulares Residencial Vivienda; lista de dudas |
| 6 | S | `normativa/firma.py` (`hash_de_contenido_firmado`, serialización canónica) + T1 |
| 7 | S | `regla.schema.json`: `firma.hash_contenido` + `firma.validado_por` opcionales; corregir comentario obsoleto de `FIRMADA` |
| 8 | S | `normativa/validacion.py`: validación 20 fase 1 en `VALIDACIONES_POR_FICHERO` + T2-T4 |
| 9 | S | `curacion/__init__.py` + `curacion/comprobar_borradores.py`; borradores validados |
| 10 | S | `curacion/hoja_de_revision.py` (HTML A4 imprimible: cabecera, tabla con F/L/M + huella + margen, pie con firmas, anexo de literales) + T10 |
| 11 | S | `curacion/volcar_acta.py` (`transcribir` y `firmar`) + T8-T9 |
| 12 | S | Suite completa en verde; imprimir hoja + anexo |
| 13 | D | Colchón: ensayo de lectura con la piloto; revisión final de hoja y lista de dudas |
| 14 | L 25 | Sesión de validación; escaneo del acta a `docs/curacion/actas/` |
| 15 | M 26 | `transcribir` → ledger; `firmar --curador` → reglas FIRMADAS |
| 16 | M 26 | Supersede de `seguridad_incendio.yaml`; manifiesto → `parcial` (en ese orden); T5-T7 |
| 17 | M 26 | Reescribir `test_corpus_sin_firmar.py:143` → `test_solo_es_afirmable_lo_firmado_con_firma_valida`; ampliar whitelist y retirar test del tag en `test_normativa_aplicable.py`; suite en verde; demo |
| 17b | X 27 | Golden set `tests/golden/dbsi3_preguntas.jsonl` (preguntas de Pablo) + runner; `PROGRESS.md`; medir tiempo de sesión |
| 18 | J+ | `curar_corpus.py`: emitir hash, generalizar prefijo, `validado_por`; validación 20 fase 2 + esquema required + invertir T4 |
| 19 | J+ | DB-SI en `FUENTES_OFICIALES_CONOCIDAS`; validación 14 bitemporal y restaurar `_superseded_*` a visible |

## 12. Plan de pruebas

Tests nuevos (`tests/test_firma_integridad.py`, `tests/test_curacion_hoja.py`, `tests/test_politica_corpus_produccion.py`), todos con corpus en `tmp_path` — cero ficheros nuevos en `tests/fixtures/`:

T1 hash canónico estable (fechas date/cadena, orden de claves) y sensible (un valor cambiado → hash distinto) · T2 manipulación tumba la carga con `[20]` · T3 hash válido carga limpio · T4 FIRMADA sin hash tolerada (invertir el jueves) · T5 skill no afirma con regla sin firmar (e2e) · T6 skill afirma limpio con regla firmada, mismas 3 afirmaciones con cita — G11 intacto (e2e) · T7 política: toda regla de `normativa/es/` real está (FIRMADA+firma+hash válido) o lleva el tag · T8 volcado rechaza borrador derivado · T9 volcado inmutable y reanudable · T10 hoja completa (filas, huellas, F/L/M).

Existentes: `:143` de `test_corpus_sin_firmar.py` se pone rojo **por diseño** y se sustituye por su invariante permanente (docstring con fecha y acta); whitelist y test del tag de `test_normativa_aplicable.py` se actualizan; `test_curar_corpus.py`, `test_normativa_borrador_no_afirma.py`, `test_normativa_manifiesto_deriva.py` verdes sin tocar.

## 13. Métricas para medir el éxito

- Nº de reglas FIRMADAS el lunes (objetivo 10-15; mínimo honesto: las conformes).
- Tiempo real de la sesión de validación por regla — primera medición de escalabilidad a DB-SUA (101 pendientes) y al resto del DB-SI (`NOR-2`).
- Nº de correcciones/tachaduras del colegiado — mide la calidad de la transcripción con ficha.
- Cero incidencias de la validación 20 en producción (toda incidencia = manipulación o bug, ambas críticas).

## 14. Posibles motivos para NO implementar la idea

- **«Esperar al jueves y hacerlo todo con `curar_corpus.py` mejorado»:** perdería la sesión del domingo con los dos validadores — la dependencia externa que lleva bloqueando la Fase 1 desde el 2026-08-06 (tarea 18). La disponibilidad de estos perfiles es el recurso escaso; el código no.
- **«El pipeline automático debería producir el paquete»:** verificado en código que no puede (fuentes solo-DB-SUA, prefijo hardcodeado, ambos congelados; tablas multi-eje inconvertibles por diseño). La transcripción manual con ficha es la vía prevista para exactamente este tipo de regla, no un apaño.
- **«La firma en papel es teatro»:** no — el hash de contenido impreso por fila ancla criptográficamente el acta escaneada a lo que entra en el corpus; es más verificable que un click en una herramienta.
- **Riesgo real asumido:** dos validadores en una sesión no equivalen a la «regla de dos personas» continua de `NORMATIVE_ENGINE.md` §12 para todo el corpus futuro — este PRD firma UN paquete, no instaura un proceso permanente. La cadencia sostenida (ficha §5) sigue pendiente de decidir.

---

## Adéndum (2026-08-22, tarde): la revisión se hace EN PANTALLA

Cambio de medio decidido por Pablo el mismo día: la hoja de revisión (§3.2) es una página interactiva que se revisa en pantalla, no en papel. La sesión sigue siendo el lunes 25 y el volcado el martes 26; la selección de la sesión p1 son 6 reglas (`curacion/paquete.py::SELECCION_P1`), no las 15 transcritas — fuera las definiciones no evaluables y lo que la skill no consume.

**Trazabilidad sin firma manuscrita (opción A, elegida por Pablo entre tres):** el acta escaneada se sustituye por el **JSON de revisión** que descarga el botón «Guardar revisión»: lleva las marcas F·L·M, las correcciones tecleadas, la identidad del validador (nombre, colegiatura, rol, fecha), la declaración aceptada, la huella de contenido de cada fila y un `hash_revision` (SHA-256 del contenido canónico, calculado en el navegador). La atestación de identidad es la declaración en pantalla + el reenvío del JSON **desde el correo del propio validador** citando el código de revisión (12 primeros hex del hash); la referencia queda en el ledger. `firma.curador` sigue siendo Pablo — la decisión del 21-08 no se reabre.

**Qué cambia en el flujo (§3.3):** `curacion/volcar_acta.py transcribir` ingiere el/los actas JSON (verifica `hash_revision` con la misma serialización canónica que el JS; un acta editada tras guardarse se rechaza) y el curador traduce cada corrección de texto libre a campo=valor (el ledger conserva el texto del validador, el valor original y el corregido). `firmar` fusiona las revisiones de varios validadores por regla (una exclusión veta; conforme exige serlo en todos; correcciones contradictorias o sin traducir bloquean la fila) y mantiene intactas las reglas de siempre: huella del borrador == huella del acta («el acta manda»), destino inmutable, validación previa, ledger append-only. Las cinco capas de «una regla sin firmar nunca se usa» no cambian.

**Decisión:** Aprobado por Pablo el 2026-08-22 (aprobación del plan en sesión, con las 3 decisiones de §11.0 respondidas explícitamente; adéndum de pantalla y opción A de trazabilidad aprobados el mismo día).
