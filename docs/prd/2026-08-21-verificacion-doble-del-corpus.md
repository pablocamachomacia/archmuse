# PRD — Verificación doble del corpus (Prompt 2)

**Estado:** Aprobado · **Fecha:** 2026-08-21 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-21, alcance completo del §11)

---

## 1. Problema que resuelve

El Prompt 1.5 dejó el pipeline de borradores en 7/20 conversiones (35%) y 24 sub-candidatas en pendientes-de-humano, cada una con un motivo específico. Sin curador colegiado (decisión de Pablo, 2026-08-21), la confianza del corpus depende de que exista una segunda verificación mecánica antes de que una regla se pueda evaluar de verdad — hoy `BORRADOR` es el techo, y ninguna regla `BORRADOR` es evaluable (`normativa/resolucion.py::_paso1_candidatas`). Sin una vía de promoción, el corpus se queda permanentemente en borrador.

Origen: la secuencia original de Fable 5 (Prompt 2) más el addendum de Pablo del 2026-08-21 tras cerrar el Prompt 1.5, que añade tres exigencias concretas no anticipadas en el prompt original:

1. La doble ruta opera sobre las **sub-candidatas atómicas** de la descomposición (Prompt 1.5), nunca sobre artículos padre.
2. La segunda ruta usa un **motor de texto PDF distinto**, con tratamiento explícito del guionizado de fin de línea — el límite conocido del Prompt 1.5 (~7 de las 24 pendientes por `contexto_no_localizable`/`posible_cifra_adicional_no_extraida`) tiene que aflorar como discrepancia **resoluble**, no quedar invisible por compartir el mismo defecto de lectura.
3. Objetivo medible: de las 24 pendientes actuales, las de esos dos motivos deben o bien convertir por la segunda ruta, o bien llegar a `revisar_pendientes.py` con las dos lecturas lado a lado.

## 2. Usuario afectado

Pablo, como único resolutor de discrepancias (sin curador colegiado, es el humano del bucle). Indirectamente, el arquitecto usuario de la futura Skill `revision_normativa`, que solo podrá evaluar contra reglas `VERIFICADA_AUTOMATICA` o superiores.

## 3. Objetivo de negocio

Es el paso que convierte "hay borradores" en "hay reglas evaluables". Sin él, todo el trabajo del Prompt 1/1.5 sigue sin poder usarse en un informe real.

## 4. Objetivo técnico

Dada una sub-candidata `BORRADOR`, una segunda ruta de extracción —independiente en el motor de texto, no solo en el nombre— produce su propia lectura del mismo artículo. Si ambas rutas coinciden en valor y unidad para el mismo parámetro, la regla se promueve a `VERIFICADA_AUTOMATICA` con el SHA-256 del PDF oficial. Si no coinciden, o la segunda ruta tampoco puede anclar la cifra, la discrepancia queda en pendientes con las dos lecturas, resoluble por `scripts/revisar_pendientes.py`.

## 5. Diseño — decisiones ya verificadas contra datos reales, no hipotéticas

### 5.1 Motor de la segunda ruta: `pdfminer.six`, ya en el árbol de dependencias

La ruta A extrae texto con `pypdf` (`ingesta/fuentes/codigotecnico.py::_texto_desde_pdf`). `pdfminer.six==20260107` **ya está instalado** (`requirements.lock.txt`), como dependencia transitiva no declarada directamente — cero coste de instalación nueva, y ya está vetted en el árbol.

**Medido contra el PDF real** (`ingesta/estado/cache/codigotecnico__DB-SUA__3cfb5bbb135e.pdf`, los 40 `parametro.contexto_citado` de las 20 candidatas de DB-SUA):

| Motor | Localizables | Nota |
|---|---|---|
| `pypdf` (ruta A, tal cual hoy) | 18/40 (45%) | Sin mejora con des-guionizado: la corrupción de `pypdf` inserta espacios a media palabra (`"p avimen-\nto"`, `"resolv erán"`), no es guionizado limpio |
| `pdfminer.six`, sin tratar | 34/40 (85%) | |
| `pdfminer.six` + des-guionizado simple (`r'(\w)-\s+(\w)'` → unir) | **35/40 (87.5%)** | El guionizado de `pdfminer.six` SÍ es guionizado real de fin de línea (`"pavimen- to"`), no corrupción — por eso el tratamiento simple funciona aquí y no en `pypdf` |

**Decisión: `pdfminer.six` + des-guionizado simple.** Casi el doble de localización que la ruta A, con una técnica (join en `-\s+`) que ya se descartó para la ruta A en el Prompt 1.5 precisamente porque su corrupción no es guionizado limpio — la propia comparación es la prueba de que las dos rutas fallan de formas *distintas*, que es el punto del addendum: si compartieran el mismo motor, compartirían el mismo punto ciego.

### 5.2 Cómo se conecta sin reescribir nada de `extraccion/`

`extraccion/pipeline.py::extraer(documento, segmentador=...)` **ya acepta un segmentador inyectable** (`DocumentoOficial -> List[Segmento]`) — es exactamente el punto de extensión que `segmentador_pdf.segmentar` ya usa. La segunda ruta no reescribe segmentación, interpretación, verificación ni confianza: solo aporta un `Segmento` distinto de partida.

Nuevo módulo `extraccion/segmentador_pdf_b.py`:

```python
def segmentar(documento: DocumentoOficial) -> List[Segmento]:
    texto = _extraer_con_pdfminer(documento.bytes_crudos)   # pdfminer.six + des-guionizado
    documento_b = dataclasses.replace(documento, texto_crudo=texto)
    return segmentador_pdf.segmentar(documento_b)           # reutiliza TODO el resto: índice, secciones, apartados
```

`documento.bytes_crudos` ya guarda el PDF original tal cual se descargó (`ingesta/modelo.py::DocumentoOficial`, comentario propio: "para que `almacen.py` archive el original real"). Nada en `extraccion/` se reescribe; se compone.

**Hallazgo real durante la implementación, no anticipado al escribir este PRD: la reutilización de `segmentador_pdf.segmentar` no es gratis.** Su detección de apartados exige que «número + título» aparezcan concatenados en una sola línea — lo que `pypdf` hace, y lo que `pdfminer.six` NO hace siempre: en el cuerpo de este PDF separa a veces el número de su título en dos líneas (a veces título-antes-que-número, a veces al revés). Sin tratarlo, la ruta B reconocía **0 apartados**. Con un tratamiento adicional (`_reconstruir_numero_de_apartado`, ver `extraccion/segmentador_pdf_b.py`) que repara el caso título-antes-que-número, la ruta B reconoce **15 de los 20 apartados reales de DB-SUA (75%)** — los 5 restantes (1.5, 2.1, 2.2, 8.1, 8.2) usan el orden inverso, sin reparar en este PRD para no seguir persiguiendo casos particulares de un solo documento. Para esos 5, la ruta B simplemente no aporta lectura — ni convierte ni compite con la ruta A, sigue exactamente donde estaba.

### 5.3 Comparación y promoción — a nivel de sub-candidata, no de artículo

Ambas rutas producen sus propias `ReglaCandidata` para el mismo documento. **Ambas pasan por la MISMA descomposición** (`scripts/generar_borrador_corpus.py::_descomponer`/`_unidades`, reutilizada sin cambios) y el **mismo guardián `_contar_cifras_de_umbral`**, de forma independiente — el addendum lo pide explícito: el guardián protege igual venga la lectura de la ruta que venga.

Dos sub-candidatas (una por ruta) del mismo `candidata_padre` + mismo `parametro.nombre` **coinciden** si:
- `_numero(valor_citado)` es igual en ambas (mismo valor numérico), y
- `unidad` es igual (normalizada: minúsculas, sin espacios).

Coincide → `estado: VERIFICADA_AUTOMATICA`, con `sha256_documento` (§5.4) y ambas trazas (`ruta_a`/`ruta_b`) en los metadatos. No coincide, o solo una ruta la ancla → pendientes, con las DOS lecturas (o la única) adjuntas — nunca se elige una por defecto.

### 5.4 Esquema: `VERIFICADA_AUTOMATICA` + hash del PDF oficial

- `regla.schema.json`: `estado.enum` pasa de `["BORRADOR", null]` a `["BORRADOR", "VERIFICADA_AUTOMATICA", "FIRMADA", null]` — `FIRMADA` reservado tal como pedía el prompt original, sin lógica todavía.
- `normativa/resolucion.py::_paso1_candidatas`: el guardarraíl deja de descartar solo `BORRADOR`; pasa a descartar todo lo que **no** sea `VERIFICADA_AUTOMATICA` o `FIRMADA` (afirmable). Sigue siendo un `if` explícito, greppable.
- **Campo nuevo** `norma.fuente.documento_sha256`: SHA-256 del PDF oficial completo (`hashlib.sha256(bytes_crudos).hexdigest()`), **distinto** del `hash_texto` que ya existe (ese verifica que el `literal` citado coincide con el texto — sirve para detectar deriva de la cita, no para identificar qué versión del PDF se usó). Los dos hashes responden preguntas distintas y ninguno sustituye al otro.

### 5.5 `scripts/revisar_pendientes.py`

Presenta cada discrepancia en terminal: `candidata_padre`, `parametro.nombre`, lectura A (valor+unidad+`contexto_citado`+extracto de `texto_original` de esa ruta), lectura B (lo mismo), y las opciones **A** / **B** / **corregir a mano** / **descartar**. La resolución:

1. Se escribe en `extraccion/estado/resoluciones.jsonl` (nuevo, append-only): `{candidata_padre, parametro_nombre, lectura_a, lectura_b, resolucion, valor_final, unidad_final, resuelto_por: "Pablo", fecha}` — el registro de auditoría, nunca se reescribe una línea ya escrita.
2. Si la resolución es A/B/manual (no descartar), genera la sub-candidata `VERIFICADA_AUTOMATICA` correspondiente y la añade al corpus, exactamente igual que una coincidencia automática — la firma de Pablo sustituye a la segunda ruta cuando las dos rutas no bastaron, con la fecha de la resolución en sus propios metadatos (`tags: ["resuelto_manualmente:2026-08-21"]`), tal como pedía el prompt original.
3. "Descartar" dejA la sub-candidata en pendientes, con la resolución registrada igualmente (para no volver a preguntar dos veces por lo mismo).

### 5.6 `normativa/manifiesto.py` — la derivación ya acordada en el Prompt 1

El Prompt 1 (§9 de su PRD) resolvió, con aprobación de Pablo, que el manifiesto de cobertura por materia se derive del estado de sus reglas, sustituyendo `transcrito_sin_firmar`/`pendiente_firma_colegiado`. Se implementa aquí: una materia es `parcial`/`completo` solo cuando **todas** sus reglas activas son `VERIFICADA_AUTOMATICA` o `FIRMADA` — nunca si queda alguna `BORRADOR` o sin resolver.

`normativa/manifiesto.py::estado_derivado()` es el mecanismo: recibe lo declarado en `manifiesto.yaml` (si algo) y las reglas reales de esa materia+ámbito (`normativa/loader.py::ResultadoCarga.reglas_por_materia()`, nuevo). Una regla cuenta como confirmada con el mismo criterio, palabra por palabra, que `resolucion.py::_paso1_candidatas` (`_regla_confirmada()`, duplicado a propósito para evitar un ciclo de imports — `tests/test_normativa_manifiesto_deriva.py` es lo que impide que diverjan). Caso encontrado escribiendo los tests, no anticipado al diseñar: una materia declarada `completo`/`parcial` en `manifiesto.yaml` sin NINGUNA regla real detrás (p. ej. se borró el fichero y nadie tocó el manifiesto) no se puede tomar como cierta solo porque lo declare — es la misma mentira que la validación 17 rechaza al cargar, pero en tiempo de ejecución no hay corpus con que contrastarla, así que se fuerza a `ausente` en vez de confiar a ciegas.

### 5.7 Por qué determinista, no LLM — redecisión de Pablo (2026-08-21)

El diseño original de este PRD (aprobado en §11 completo) proponía una ruta B basada en una segunda llamada al LLM con un prompt distinto, sobre el texto de `pdfminer.six`. Al llegar a la tarea 8 (ejecución real), la cuenta de la API Anthropic no tenía saldo — bloqueante, externo, no corregible desde el código. Pablo decidió no aplazar la tarea sino **rediseñarla**: sustituir la interpretación por API por un extractor determinista de patrones (`extraccion/interprete_b_determinista.py`), sin ningún LLM de por medio.

**No es solo un parche por el bloqueo de facturación — es una independencia más fuerte que la alternativa descartada en el §14 original ("variar también el prompt de la IA"):**

- **Determinista↔LLM no comparte sesgo de lectura.** Dos LLMs (aunque con prompts distintos) comparten el mismo tipo de fallo: ambos pueden "entender" mal la misma frase ambigua de la misma manera, porque los dos razonan sobre el mismo texto con el mismo tipo de modelo. Un extractor de patrones cerrado no "entiende" nada — reconoce una forma sintáctica exacta o no reconoce nada, y cuando no reconoce, va a pendientes con la cláusula íntegra en vez de arriesgar una interpretación. Es un tipo de fallo estructuralmente distinto al de la ruta A, que es justo lo que una segunda verificación necesita para valer como verificación y no como repetición.
- **Dos motores de texto PDF distintos + dos paradigmas de lectura distintos** (interpretación libre vs. patrón cerrado) es una independencia mayor que dos motores de texto con el mismo paradigma de lectura (dos LLMs). El §5.1 ya medía que los dos motores de texto fallan de formas distintas (`pypdf` corrompe a media palabra, `pdfminer.six` guioniza limpio); esto añade una segunda capa de independencia sobre la interpretación misma.
- **Dejar el pipeline entero ejecutable offline y a coste cero.** Ni la ruta A (ya usaba IA solo en `extraccion/interprete.py`, y solo se ejecuta una vez por documento, cacheada) ni la ruta B necesitan ya la API en el camino de re-verificación: `scripts/verificar_doble_ruta.py` corre sin red y sin coste marginal por ejecución. Coherente con la política de scripts offline ya vigente en el repositorio (`scripts/generar_borrador_corpus.py`, `scripts/revisar_pendientes.py`).

**Coste de la decisión, dicho sin suavizarlo:** un extractor de patrones cerrado tiene un techo de cobertura que un LLM no tiene — cualquier redacción normativa que no encaje en el catálogo de patrones (`no será/serán inferior(es) a`, `como mínimo/máximo`, `al menos`, `más de`/`menos de`, porcentajes, filas de tabla) no se lee, punto. El diseño no intenta disimular ese techo con heurística difusa: cuando no reconoce, no adivina — manda a pendientes con la cláusula íntegra (motivo `patron_no_reconocido_ruta_b`) para que un humano decida si hace falta un patrón nuevo. La tabla de resultados del Cierre cuantifica cuántas cláusulas reales de DB-SUA caen en ese caso.

## 6. Casos límite

- Las dos rutas coinciden en valor pero difieren en unidad declarada de forma trivial (`"m"` vs `"metros"`) → normalización de unidad antes de comparar (tabla cerrada pequeña: m/cm/mm/%/N/lux/m²/vehículos/espectadores — las mismas unidades ya vistas en el corpus real).
- La ruta B ancla una cifra que la ruta A no había extraído en absoluto (parametro nuevo, no solo confirmación) → no se inventa una "coincidencia": va a pendientes como hallazgo nuevo de la ruta B, con su propio motivo.
- El PDF cacheado no existe (se purgó `ingesta/estado/cache/`) → error explícito pidiendo re-descarga, nunca continuar con solo la ruta A y fingir que hubo verificación doble.
- Una sub-candidata ya `VERIFICADA_AUTOMATICA` se vuelve a procesar (re-ejecución) → idempotente: mismo resultado, no duplica ficheros (mismo patrón que `scripts/generar_borrador_corpus.py`).

## 7. Flujo del usuario

Pablo ejecuta el pipeline de doble ruta sobre las candidatas de DB-SUA → revisa el informe (N verificadas automáticas, M pendientes con dos lecturas, K sin cambios) → ejecuta `revisar_pendientes.py` para las M → el corpus queda con las reglas `VERIFICADA_AUTOMATICA` listas para el Prompt 3.

## 8. Criterios de aceptación

- Las 24 pendientes actuales del Prompt 1.5 pasan por la ruta B.
- Las que caían por `contexto_no_localizable`/`posible_cifra_adicional_no_extraida` (10 de las 24): cada una o convierte a `VERIFICADA_AUTOMATICA`, o llega a `revisar_pendientes.py` con las dos lecturas — ninguna se queda invisible por compartir el defecto de lectura de la ruta A.
- Al menos N reglas `VERIFICADA_AUTOMATICA` reales, con cita+`documento_sha256`.
- `_contar_cifras_de_umbral` (o su equivalente) activo y probado en ambas rutas.
- `normativa/manifiesto.py` deriva del estado de regla; tests de la nueva lógica.
- Suite completa verde — se arranca desde verde (Prompt 1.7 cerrado, 2026-08-21, 1181 passed / 0 failed): cualquier rojo nuevo es de este PRD.

## 9. Riesgos

**Tamaño.** Este PRD cubre más terreno que los tres anteriores juntos: segunda ruta de extracción, comparación, promoción, esquema, `revisar_pendientes.py`, y la derivación del manifiesto. Se divide en tareas de ≤2h en el §11, pero si a mitad de sesión resulta ser más de una jornada, se corta ahí (regla del propio `AGENTE_BACKLOG.md` §0.1) y se cierra lo que esté verde — no se fuerza todo en una sentada.

**El hash del PDF depende de que `bytes_crudos` siga disponible.** Si el pipeline de ingesta no conserva los bytes originales más allá de la primera descarga, `documento_sha256` no se puede calcular retroactivamente sobre candidatas ya extraídas — mitigado porque el PDF real está cacheado en disco (`ingesta/estado/cache/`) y se puede recalcular desde ahí sin volver a descargar.

**Falso positivo de "coincidencia".** Dos rutas podrían coincidir en valor+unidad por casualidad si ambas heredan el mismo error de OCR/interpretación (p. ej. un patrón de tabla mal leído igual en los dos motores). No es un riesgo nuevo de este diseño — es el riesgo residual que la propia decisión de "sin curador" acepta explícitamente (Prompt 1, §14): la doble ruta reduce el riesgo, no lo elimina, y por eso cada regla sigue llevando cita+hash enlazados para que el arquitecto usuario compruebe la fuente él mismo.

## 10. Impacto sobre módulos existentes

- `extraccion/segmentador_pdf_b.py` (nuevo): reutiliza `segmentador_pdf.segmentar` vía `dataclasses.replace`.
- `normativa/esquema/regla.schema.json`: `estado` ampliado, `documento_sha256` nuevo (aditivo).
- `normativa/resolucion.py::_paso1_candidatas`: el `if` cambia de "≠ BORRADOR pasa" a "afirmable (VERIFICADA_AUTOMATICA/FIRMADA) pasa" — un cambio de condición, no de estructura.
- `normativa/manifiesto.py`: la función que calcula el estado de una materia pasa a mirar las reglas, no una etiqueta declarada a mano.
- `scripts/generar_borrador_corpus.py`: `_descomponer`/`_unidades`/`_contar_cifras_de_umbral` se **importan**, no se duplican, desde el nuevo orquestador de doble ruta.
- `scripts/verificar_doble_ruta.py` (nuevo) + `scripts/revisar_pendientes.py` (nuevo).
- `extraccion/estado/resoluciones.jsonl` (nuevo, append-only).

## 11. Plan de implementación

1. `extraccion/segmentador_pdf_b.py`: extracción con `pdfminer.six` + des-guionizado + delegación a `segmentador_pdf.segmentar`. Test contra el PDF real: confirma la tasa de localización medida en §5.1. (≤2h)
2. `regla.schema.json`: `estado` ampliado + `documento_sha256`. Test de esquema + no-regresión sobre `seguridad_incendio.yaml` y los 7 `_borrador_*.yaml` existentes. (≤1h)
3. `normativa/resolucion.py`: guardarraíl actualizado a "afirmable = VERIFICADA_AUTOMATICA/FIRMADA". Test de política actualizado (BORRADOR sigue sin afirmar; VERIFICADA_AUTOMATICA sí). (≤1h)
4. `scripts/verificar_doble_ruta.py`: orquesta ruta A (ya existente) + ruta B (paso 1), descompone ambas, compara, promueve o manda a pendientes con las dos lecturas. (≤2h, probablemente 2 tareas)
5. Cálculo y escritura de `documento_sha256` en las reglas promovidas. (≤1h)
6. `scripts/revisar_pendientes.py`: presentación en terminal + registro en `resoluciones.jsonl` + generación de la regla resuelta. (≤2h)
7. `normativa/manifiesto.py`: derivación del estado de materia desde el estado de sus reglas. Test contra el corpus ficticio de pruebas. (≤2h)
8. Ejecución real sobre las 24 pendientes de DB-SUA + informe de resultados. (≤1h)
9. Suite completa + cierre del PRD con la tabla de resultados real.

## 12. Plan de pruebas

- Golden: al menos 2 promociones reales a `VERIFICADA_AUTOMATICA` con las dos lecturas coincidentes, sobre candidatas reales de DB-SUA.
- Test de discrepancia real: al menos 1 caso donde las dos rutas NO coinciden (o solo una ancla), verificando que va a pendientes con ambas lecturas, nunca eligiendo una.
- Test de política: ninguna regla `VERIFICADA_AUTOMATICA` llega a serlo sin `documento_sha256` ni cita literal (extiende el test de política del Prompt 1).
- Test de `revisar_pendientes.py`: resolución simulada (sin terminal interactivo real) que verifica que `resoluciones.jsonl` se escribe y que la regla resultante lleva la fecha.
- Suite completa.

## 13. Métricas de éxito

De las 24 pendientes de DB-SUA: cuántas convierten por la ruta B, cuántas llegan a `revisar_pendientes.py` con dos lecturas, cuántas siguen sin poder resolverse (y por qué). Objetivo explícito del addendum: cero de las 10 candidatas de `contexto_no_localizable`/`posible_cifra_adicional_no_extraida` se quedan invisibles.

## 14. Posibles motivos para NO implementarlo así

- **Alternativa descartada: variar también el prompt de interpretación de la IA, no solo el motor de texto.** Sería una verificación más rigurosa (protege contra sesgos sistemáticos del modelo, no solo del extractor de texto), pero dobla el coste de tokens de esta tarea y el addendum de Pablo pide específicamente "motor de texto PDF distinto", no "prompt distinto". Se deja para una iteración futura si la tasa de falsos positivos de "coincidencia" resulta alta en la práctica.
- **Alternativa descartada: no crear `resoluciones.jsonl` y registrar solo en los metadatos de la regla.** Más simple, pero pierde el histórico de discrepancias descartadas (que no generan regla) y hace imposible auditar cuántas veces Pablo tuvo que intervenir — un dato que el propio Prompt 2 original pide poder medir ("tasa de rechazo en validación automática", ficha de transcripción §…).
- El tamaño del PRD (§9) es el argumento más fuerte para partirlo en dos sesiones si hiciera falta: §11 tareas 1-5 (segunda ruta + promoción automática) como una entrega cerrada y verificable por sí sola, y tareas 6-7 (`revisar_pendientes.py` + manifiesto) como la siguiente. No lo recomiendo partir de entrada porque las piezas están acopladas (sin promoción automática, `revisar_pendientes.py` no tiene nada que hacer), pero lo dejo explícito por si a mitad de sesión conviene cortar ahí.

---

**Decisión:** Aprobado por Pablo, 2026-08-21. Alcance: completo (§11), incluido el rediseño de la tarea 8 sin LLM (§5.7, decisión del mismo día tras el bloqueo de saldo de la API).

## Cierre (2026-08-21)

Las 9 tareas del §11 completas, con un rediseño a mitad de camino (tarea 8, §5.7): la ruta B dejó de usar el LLM y pasó a un extractor determinista de patrones, decisión de Pablo tras el bloqueo de saldo de la API Anthropic.

1. `extraccion/segmentador_pdf_b.py`: `pdfminer.six` + des-guionizado + `_reconstruir_numero_de_apartado`, delegando en `segmentador_pdf.segmentar`. 15/20 apartados de DB-SUA (75%) — ver §5.2 para los 5 restantes y por qué no se persiguen aquí.
2. `regla.schema.json`: `estado.enum` ampliado a `["BORRADOR", "VERIFICADA_AUTOMATICA", "FIRMADA", null]`; `norma.fuente.documento_sha256` nuevo (aditivo, patrón `^[0-9a-f]{64}$`).
3. `normativa/resolucion.py::_paso1_candidatas`: guardarraíl cambiado de "≠ BORRADOR pasa" a "afirmable (`VERIFICADA_AUTOMATICA`/`FIRMADA`, o histórica sin campo `estado`) pasa".
4. `extraccion/interprete_b_determinista.py` (nuevo, sin LLM): catálogo cerrado de patrones normativos del CTE — `no será/serán inferior(es) a`, `como mínimo/máximo`, `al menos`, `más de`/`menos de`, porcentajes, filas de tabla. No reconocido → `pendientes` con motivo `patron_no_reconocido_ruta_b` y la cláusula íntegra, nunca una heurística que adivine.
5. `scripts/verificar_doble_ruta.py` (reescrito tras el rediseño): orquesta ruta A + ruta B determinista, reutiliza `_descomponer`/`_contar_cifras_de_umbral` de `scripts/generar_borrador_corpus.py` sin duplicarlos, compara por valor+unidad normalizada, promueve o manda a pendientes con las dos lecturas.
6. `documento_sha256` calculado sobre `bytes_crudos` del PDF cacheado y escrito en toda regla `VERIFICADA_AUTOMATICA`.
7. `scripts/revisar_pendientes.py` (nuevo): presentación en terminal (`a`/`b`/`m`/`d`/`s`), registro append-only en `extraccion/estado/resoluciones.jsonl`, generación de la regla resuelta con `tags: ["resuelto_manualmente:AAAA-MM-DD"]`. Reanudable: una discrepancia ya resuelta no se vuelve a preguntar.
8. `normativa/manifiesto.py::estado_derivado()` + `_regla_confirmada()` (nuevo): el estado de cobertura de una materia se deriva del estado real de sus reglas, no de una cadena escrita a mano — ver §5.6. `normativa/loader.py::ResultadoCarga.reglas_por_materia()` nuevo, para agrupar las reglas cargadas por (ámbito, materia). Corrección encontrada escribiendo los tests: una materia declarada `completo`/`parcial` sin ninguna regla real detrás ya no se toma como cierta — se fuerza a `ausente`.
9. Ejecución real sobre las 20 candidatas de DB-SUA (tabla abajo) + suite completa.

### Resultado real sobre las 20 candidatas de DB-SUA

Ejecutado con `python scripts/verificar_doble_ruta.py extraccion/estado/candidatas/codigotecnico__DB-SUA__3cfb5bbb135e.jsonl ingesta/estado/cache/codigotecnico__DB-SUA__3cfb5bbb135e.pdf`, SHA-256 del PDF `3cfb5bbb135e8f02faebd8b844e03e8947994c18d4c9e675a7d2aa37d1cd5958`:

| Métrica | Valor |
|---|---|
| Candidatas ruta A leídas | 20 |
| Artículos segmentados por la ruta B | 15/20 (75%) |
| **`VERIFICADA_AUTOMATICA` generadas** | **3** |
| Pendientes (doble lectura o hallazgo nuevo) | 101 |

Las 3 promovidas: resalto máximo de junta en el pavimento (1.2), factor de uniformidad del alumbrado normal en zonas de circulación (4.1), ámbito de aplicación de graderíos (5.1) — las tres con cita literal, `contexto_citado` de ambas rutas y `documento_sha256` enlazado.

**Pendientes por motivo:**

| Motivo | N |
|---|---|
| Solo la ruta B ancló este valor (hallazgo nuevo, no confirmado por la ruta A) | 97 |
| La ruta B no segmentó ese artículo (límite conocido, §5.2) | 2 |
| La ruta B no produjo el mismo valor/unidad que la ruta A (discrepancia real) | 1 |
| `patron_no_reconocido_ruta_b` (cláusula numérica sin patrón reconocido) | 1 |

**El motivo dominante (97/101) merece explicación, no solo la cifra.** No es ruido: 43 de esos 97 vienen de un solo artículo, DB-SUA 1.4 (Escaleras y rampas), que en el CTE real es una tabla densa de cotas dimensionales — la ruta A la descompuso en pocas sub-candidatas compuestas (Prompt 1.5), mientras que el extractor determinista de la ruta B ancla cada cota de cada cláusula por separado. La asimetría es esperable y no invalida el diseño: cada "hallazgo nuevo" queda en pendientes con su cláusula citada, nunca se auto-promueve sin la confirmación de la ruta A, y `scripts/revisar_pendientes.py` ya soporta resolverlos uno a uno (incluida la opción "descartar" para los que no aporten una sub-candidata real). Si el volumen resulta impracticable de revisar a mano, la mejora natural para una iteración futura es enriquecer la descomposición de la ruta A (Prompt 1.5) para que produzca sub-candidatas al mismo nivel de atomicidad que la ruta B, no recortar la ruta B.

**Golden case confirmado en datos reales, no solo en el test:** la disyunción de DB-SUA 7.3 (aforo > 200 vehículos o superficie > 5.000 m²) aparece en pendientes con **ambas** cifras (`200 vehículos` y `5000 m²`, más otro par de la misma cláusula) — nunca solo una, tal como exigía el addendum de Pablo.

**Objetivo del addendum original (cero de las 10 candidatas de `contexto_no_localizable`/`posible_cifra_adicional_no_extraida` invisibles):** las 24 pendientes del Prompt 1.5 quedaron subsumidas por la re-ejecución completa de la ruta B sobre las 20 candidatas de origen (el fichero de pendientes de este PRD es nuevo, `*.verificacion_doble.jsonl`, y sustituye al de detección de las 24 como superficie de revisión); todas las candidatas de esos dos motivos pasan ahora por la ruta B determinista y salen con su propia lectura (confirmada, discrepante, o `patron_no_reconocido_ruta_b`) — ninguna se queda invisible por compartir el defecto de lectura original de la ruta A.

### Limitación real encontrada, documentada aparte, no bloqueante para este PRD

Al quitar el prefijo `_` a las 3 reglas `VERIFICADA_AUTOMATICA` para que el loader las descubriera —el punto entero de "promoción"—, la carga del corpus completo se rompió: las tres comparten `aplicabilidad: {ambito: es}` genérica (`_construir_documento` nunca deriva `usos`/`tipologías` por regla) y la validación 14 (contradicción) las trata como indistinguibles. Se revirtió antes de comprometerlo — las 3 siguen en fichero `_verificada_db_sua_*.yaml`, invisibles al loader, igual que `BORRADOR`. Documentado en `docs/design/2026-08-21-limite-aplicabilidad-generica-verificada-automatica.md`, marcado explícitamente como bloqueante para el Prompt 3, no para este. El criterio de aceptación de este PRD ("dos rutas independientes coinciden en valor y unidad") ya está cumplido y registrado — que el corpus las sirva en producción es un problema distinto, de derivación de alcance, no de verificación.

### Suite completa

`pytest -q`: **1237 passed, 18 skipped, 1 xfailed, 0 failed** (749.59s). Se arrancó desde el verde declarado por Pablo al aprobar (Prompt 1.7 cerrado, 2026-08-21, 1181 passed / 0 failed) — las 56 pruebas de más son las añadidas por este PRD. Los 2 warnings del resumen (`PytestUnraisableExceptionWarning` en `tests/test_bim_lector.py`, deallocator de `ifcopenshell`) son preexistentes y ajenos a este PRD, no tocan nada de lo escrito aquí. Dos regresiones reales encontradas y corregidas durante esta sesión, ambas en `tests/test_normativa_aplicable.py`: `test_falta_una_sola_materia_y_tambien_bloquea` y `test_estricto_false_devuelve_el_hueco_en_vez_de_levantarlo` asumían que "sin `manifiesto.yaml` declarado, no hay cobertura" — una asunción que la Tarea 7 vuelve falsa a propósito (la cobertura ya no depende solo de la declaración). Se reescribieron para construir el hueco quitando las reglas reales de disco (una copia del fixture sin `urbanismo.yaml`), que es la forma correcta de probar fail-closed bajo el nuevo mecanismo.
