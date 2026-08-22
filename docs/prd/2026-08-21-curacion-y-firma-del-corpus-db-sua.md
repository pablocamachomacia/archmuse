# PRD — Curación y firma humana del corpus DB-SUA

**Estado:** Cerrado · **Fecha:** 2026-08-21 · **Fecha de cierre:** 2026-08-21 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-21)

**Resoluciones de Pablo a los tres puntos abiertos:**

1. **§9.1 (ubicación):** `scripts/curar_corpus.py`, extendiendo `revisar_pendientes.py` en vez de partir de cero. `test_extraccion_fronteras.py` no se toca.
2. **§9.2 (fusión de actos):** dos actos separados, nunca fusionados en una tecla — `resolver` (decide campo a campo, ledger append-only, reanudable, NUNCA escribe en `normativa/es/`) y `firmar` (subcomando explícito, `--curador` obligatorio, la ÚNICA acción que escribe en `normativa/es/`, con estado `FIRMADA`, hash del documento, versión, fecha; regla firmada = inmutable).
3. **§9.3 (golden set):** no se escribe en esta tarea. Queda pendiente, posterior a la sesión de curación real; las preguntas las aporta Pablo.

---

## 1. Problema que resuelve

El Prompt 2 (`docs/prd/2026-08-21-verificacion-doble-del-corpus.md`, Aprobado e Implementado hoy mismo) cerró con
101 pendientes en `extraccion/estado/pendientes/codigotecnico__DB-SUA__3cfb5bbb135e.verificacion_doble.jsonl` y
solo 3 reglas `VERIFICADA_AUTOMATICA` — todavía invisibles al loader por un problema de `aplicabilidad`
genérica documentado aparte (`docs/design/2026-08-21-limite-aplicabilidad-generica-verificada-automatica.md`).
En la práctica, `normativa/es/` solo sirve una regla real hoy (`seguridad_incendio.yaml`, anterior al propio
campo `estado`). Sin corpus servible no hay nada que verificar contra normativa, y sin eso no hay producto
vendible — mismo diagnóstico que motivó el Prompt 1.

**Esto no es una reversión de la decisión de las 11:00 de hoy.** `docs/prd/2026-08-21-pipeline-borradores-corpus-db-sua.md`
§1 registra que Pablo decidió no contratar un **curador colegiado externo**, sustituyendo la firma de un
tercero por transcripción doble + cita literal verificable por el propio usuario. Esa decisión sigue en pie:
nadie ajeno va a firmar nada. Lo que este PRD propone es distinto — que **Pablo mismo**, como responsable del
producto, apruebe o rechace explícitamente cada una de las 101 entradas antes de que cuenten como corpus
servible, dejando un registro nominal y fechado de esa decisión. El propio esquema ya lo anticipaba: `FIRMADA`
está en el `enum` de `estado` desde el cierre del Prompt 2 (§5.4), "reservado, sin lógica todavía" — este PRD
es el que le da lógica.

Origen: petición directa de Pablo (esta sesión), formulada como continuación de la secuencia de Fable 5 —
"convierte candidatas verificadas en reglas firmadas… es la ruta crítica del producto: sin corpus firmado no
hay nada que vender".

**Corrección de partida, importante para el diseño:** el enunciado original de la tarea distingue entradas
donde las rutas "COINCIDEN" (a presentar como "propuesta de firma") de entradas donde "DISCREPAN". Comprobado
contra el fichero real: **`verificacion_doble.jsonl` no contiene ningún caso de coincidencia.** Cuando ambas
rutas coinciden en valor y unidad, `scripts/verificar_doble_ruta.py` las promueve directamente a
`VERIFICADA_AUTOMATICA` sin pasar por este fichero — eso ya ocurrió para las 3 reglas que existen hoy. Las 101
líneas de este fichero son, sin excepción, casos que necesitan decisión humana campo a campo (una única ruta
ancló el valor, las dos rutas discreparon, la ruta B no segmentó el artículo, o no reconoció ningún patrón).
El diseño de este PRD trata las 101 de forma uniforme con el flujo del punto 3 de la tarea original — no hay
un "camino rápido" de aprobación automática que construir.

## 2. Usuario afectado

Pablo, como curador/firmante único por ahora. El parámetro `--curador` es obligatorio desde el primer día
aunque hoy solo tome un valor — deja la puerta abierta a un segundo firmante sin rediseñar el esquema ni la
herramienta. Indirectamente, el arquitecto usuario de la futura Skill `revision_normativa` (Prompt 3), que
hereda un corpus con más reglas evaluables y, si se decide exponerlo, la distinción entre "verificado por dos
rutas automáticas" y "revisado y firmado por un humano" (ver riesgo §9.5 — no doy por hecho que esa distinción
importe de cara al producto, lo dejo como pregunta abierta).

## 3. Objetivo de negocio

Mismo argumento que el Prompt 1 (`AGENTE_BACKLOG.md` §0.3): sin corpus servible no hay verificación normativa,
sin verificación normativa no hay OP-3/OP-4, sin eso no hay "50€/mes defendible". La firma humana explícita
añade un argumento de confianza adicional frente al arquitecto que paga — sin el coste de un curador
colegiado externo — coherente con la regla de oro de `CLAUDE.md` §1 (ningún número sin procedencia) llevada
al límite: no solo procedencia algorítmica, también responsabilidad nominal de quién lo aprobó.

## 4. Objetivo técnico

Dada una entrada de `verificacion_doble.jsonl`, la herramienta la presenta con: `candidata_padre`,
`parametro_nombre`, `motivo`, `lectura_a` (o "sin lectura de esta ruta"), `lectura_b` (o lo mismo), y las
cláusulas no reconocidas de la ruta B si las hay. El curador responde:

- **[a]probar** — cuando solo hay una lectura, la usa; cuando hay dos y no coinciden, exige elegir
  explícitamente cuál (nunca implícito).
- **[r]echazar con motivo** — motivo en texto libre **obligatorio**, la entrada queda sin regla.
- **[e]ditar campos y aprobar** — corrige valor/unidad/contexto_citado a mano y aprueba lo corregido.
- **[s]altar** — no se registra nada; vuelve a salir la próxima ejecución.

Al aprobar (con o sin edición) se escribe una regla `estado: FIRMADA` en `normativa/es/estatal/`, válida
contra `regla.schema.json`, con: `documento_sha256` del PDF fuente, `vigencia`/versión del documento heredada
de la candidata origen, el bloque nuevo `firma: {curador, fecha}`, y `literal` copiado tal cual del PDF (nunca
resumido). El proceso es reanudable y cada decisión queda en un ledger append-only con timestamp.

## 5. Casos de uso

1. Pablo ejecuta la herramienta con `--curador Pablo --sha256-pdf 3cfb5bbb...` sobre las 101 entradas. Para
   cada una, la ve, decide, y (si aprueba/edita) la regla `FIRMADA` se escribe inmediatamente — no al final de
   la sesión, para no perder trabajo si se interrumpe.
2. Entrada con `lectura_a: null` (97 de las 101, motivo "solo la ruta B ancló este valor"): se presenta con
   claridad que es un hallazgo de una sola ruta, no una confirmación — el curador decide si la cita basta para
   firmarla igual, o si prefiere rechazarla hasta tener una segunda confirmación.
3. Entrada con `no_reconocidas_b_del_articulo` poblado (la discrepancia real de `diametro_maximo_perforacion`,
   y el caso `patron_no_reconocido_ruta_b`): se muestran íntegras las cláusulas que la ruta B no reconoció,
   para que el curador vea el contexto completo del artículo, no solo el fragmento que sí se ancló.
4. Sesión interrumpida a mitad de las 101 → al relanzar, continúa exactamente en la primera entrada sin
   decisión registrada — ninguna ya resuelta se vuelve a preguntar.
5. Comando lanzado sin `--curador` → falla explícito antes de procesar nada.

## 6. Casos límite

- **Rechazo sin motivo** → error explícito y se vuelve a pedir; motivo es obligatorio (a diferencia de la
  opción "d" de `scripts/revisar_pendientes.py`, que hoy descarta sin pedir razón).
- **`--sha256-pdf` ausente** → falla; nunca se firma una regla sin hash del documento origen.
- **Entrada ya resuelta en `extraccion/estado/resoluciones.jsonl`** (por una sesión previa de
  `revisar_pendientes.py`, que ya existe y ya se usó — ver §9.2): decisión de diseño que necesito que
  confirmes — ¿la nueva herramienta debe leer ese ledger para no re-preguntar lo que ya se resolvió, o son
  flujos deliberadamente independientes? Recomiendo que lo lea (mismo criterio de dedup
  `candidata_padre::parametro_nombre`) para no descartar trabajo ya hecho, pero no lo asumo.
- **Candidata donde el curador querría añadir una regla que la herramienta no propuso** (por ejemplo, a partir
  de una cláusula de `no_reconocidas_b_del_articulo`) → explícitamente fuera de alcance: esta herramienta
  aprueba o rechaza propuestas existentes, no genera candidatas nuevas. Eso vuelve al pipeline de extracción.
- **Edición que cambia la unidad a algo no normalizable** (fuera de la tabla cerrada m/cm/mm/%/N/lux/m²/etc.
  ya usada en `scripts/verificar_doble_ruta.py`) → rechazada por la validación de esquema al escribir, con el
  motivo exacto en pantalla, nunca escrita a medias.

## 7. Flujo del usuario

Pablo ejecuta la herramienta sobre `verificacion_doble.jsonl` → para cada una de las 101 entradas ve las
lecturas disponibles y decide → cada aprobación/edición genera inmediatamente una regla `FIRMADA` en
`normativa/es/estatal/` y una línea en el ledger → al terminar (o al interrumpir y relanzar hasta terminar),
`normativa/es/` tiene el corpus DB-SUA real → se escriben las 30 preguntas del golden set sobre lo que
realmente quedó firmado → se ejecuta el test contra `normativa/api.py`.

## 8. Criterios de aceptación

- La herramienta procesa las 101 entradas de principio a fin sin excepción, incluidos relanzamientos
  parciales tras interrupción.
- Toda aprobación/edición produce un YAML válido contra `regla.schema.json` ampliado (`estado: FIRMADA` +
  bloque `firma` obligatorio cuando ese es el estado).
- Todo rechazo lleva motivo obligatorio; toda decisión (aprobar/rechazar/editar) queda en un ledger
  append-only con timestamp — ninguna línea se sobreescribe jamás.
- Tras una sesión de curación completa (la hace Pablo), `normativa/es/` contiene reglas DB-SUA reales y el
  loader las carga sin rechazos (`ResultadoCarga.hay_rechazos is False`). **Nota:** no existe en `normativa/`
  ningún canal de "warnings" separado de los rechazos (cero usos de `warnings.warn` en todo el paquete,
  confirmado) — "sin errores ni warnings" se verifica como "sin rechazos", no hay un segundo estado que
  comprobar.
- `tests/golden/dbsua_preguntas.jsonl` (30 preguntas) pasa 30/30 contra el corpus firmado, vía
  `normativa/api.py`.
- Suite completa en verde. Entrada en `PROGRESS.md`.

## 9. Riesgos

### 9.1 Riesgo de arquitectura — el más importante, bloqueante hasta que lo decidas

`python -m extraccion.curar`, tal como pide la tarea, situaría el módulo **dentro** de `extraccion/`. Pero
`test_extraccion_fronteras.py` ya prueba, y hace cumplir, que `extraccion/` **nunca** escribe en `normativa/es/`
ni importa `normativa.loader`/`.validacion`/`.registro`/`.resolucion` — exactamente lo que esta herramienta
necesita para validar y escribir una regla `FIRMADA`. Es la misma razón por la que `generar_borrador_corpus.py`,
`verificar_doble_ruta.py` y `revisar_pendientes.py` viven los tres en `scripts/`, no dentro de `extraccion/`.

**Recomiendo `scripts/curar_corpus.py`** (invocado `python scripts/curar_corpus.py`), mismo sitio y misma
convención que sus tres predecesoras, sin tocar ni debilitar el test de fronteras. Si de verdad quieres el
punto de entrada literal `python -m extraccion.curar`, la alternativa es debilitar esa regla arquitectónica
explícitamente — es una decisión tuya, no la tomo por inercia.

### 9.2 Solapamiento con `scripts/revisar_pendientes.py`

Ya existe, ya se usó en el cierre del Prompt 2, y cubre buena parte de lo pedido: presenta lectura A/lectura B
en terminal, opciones interactivas, ledger append-only reanudable en `resoluciones.jsonl`, generación de la
regla resultante. Las diferencias reales con lo que pide esta tarea:

| | `revisar_pendientes.py` (hoy) | Esta tarea |
|---|---|---|
| Opciones | a / b / m / d / s | a / r / e / s |
| Motivo de rechazo | no se pide | obligatorio |
| Curador | hardcodeado `"Pablo"` | `--curador` explícito |
| Estado que escribe | `VERIFICADA_AUTOMATICA` + tag | `FIRMADA` + bloque `firma` |
| Fichero fuente | el mismo `verificacion_doble.jsonl` | el mismo |

**Recomiendo extender `revisar_pendientes.py`** (reusar `procesar()`/`resolver_uno()`/`_generar_regla()`) en
vez de construir una herramienta nueva desde cero — mantener dos scripts casi idénticos sobre el mismo fichero
es coste de mantenimiento sin beneficio. Si prefieres una herramienta separada por claridad conceptual
(verificación automática vs. firma humana son decisiones de naturaleza distinta), dilo explícitamente al
aprobar este PRD — lo implemento como script nuevo que **importa**, no duplica, las piezas compartidas.

### 9.3 El 30/30 del golden set depende del resultado real de la curación, no solo del código

De las 101 pendientes, 97 son "solo ruta B" — buena parte proviene de la sobre-segmentación de DB-SUA 1.4
(Escaleras y rampas) documentada en el cierre del Prompt 2. No hay garantía de que, tras curar, queden
suficientes reglas firmadas sobre los 5 temas pedidos (barandillas, escaleras, mesetas, resbaladicidad,
huecos) para escribir 30 preguntas reales sin inventar ninguna. Si la cobertura real no llega, el criterio
"30/30" presiona a aprobar entradas de baja confianza solo para completar el cupo — exactamente el incentivo
que el Prompt 1 §6 prohibía ("no medir reglas-por-semana: incentiva transcripción rápida y descuidada").

**Recomiendo escribir las 30 preguntas después de la sesión real de curación**, sobre lo que de verdad quedó
firmado — no antes, como plantilla a rellenar a la fuerza. Si al terminar la curación no hay 30 preguntas
reales y honestas posibles, ese número baja y se dice explícitamente en el cierre, no se rellena.

### 9.4 `FIRMADA` ya estaba reservado — riesgo técnico bajo en ese punto concreto

El Prompt 2 dejó `"FIRMADA"` en el `enum` de `estado` explícitamente para esto ("reservado, sin lógica
todavía"), y `normativa/manifiesto.py::_regla_confirmada()` ya trata `VERIFICADA_AUTOMATICA` y `FIRMADA` como
igualmente confirmadas. Activar ese estado no rompe nada del diseño ya aprobado hoy — es el único punto donde
"revertir" no aplica en absoluto: no hay nada que deshacer, solo algo que completar.

### 9.5 Pregunta de producto abierta, no resuelta en este PRD

¿Debe el arquitecto usuario final ver, en algún informe o respuesta, la diferencia entre una regla
`VERIFICADA_AUTOMATICA` y una `FIRMADA`? Si la respuesta es no, la distinción es puramente interna
(trazabilidad de quién aprobó qué) y no hace falta ningún cambio en `api.py`/reporting para este PRD. Si la
respuesta es sí, es una capacidad nueva aparte (probablemente del Prompt 3, la Skill `revision_normativa`) que
no cubro aquí. Lo dejo explícito para que no se dé por hecho en ninguna dirección.

### No compite con `REFACTOR_MASTERPLAN.md`

Es corpus, no endurecimiento de producto existente.

## 10. Impacto sobre módulos existentes

- `normativa/esquema/regla.schema.json`: nuevo bloque `firma` (`curador`: string, `fecha`: date), aditivo;
  nueva validación semántica (en `normativa/validacion.py`) que lo exige cuando `estado == "FIRMADA"`.
- `scripts/revisar_pendientes.py` (si se extiende, opción recomendada) o `scripts/curar_corpus.py` (si se
  separa) — ver §9.1/§9.2, pendiente de tu decisión.
- `extraccion/estado/resoluciones.jsonl` (si se extiende) o un ledger nuevo — mismo punto pendiente.
- `tests/golden/` — **no existe hoy ningún golden test fuera de `tests/golden.py`/`tests/test_golden_*.py`,
  que son de la línea DXF/analyzer y no aplican aquí.** `tests/golden/dbsua_preguntas.jsonl` + su runner son
  100% nuevos, sin infraestructura previa que reutilizar directamente (aunque el patrón de `tests/golden.py` —
  JSON canónico, `--recapturar`, diff por campo — es una referencia razonable de estilo).
- `PROGRESS.md`: entrada de cierre, siguiendo la convención ya usada por los Prompts 1 y 2.

## 11. Plan de implementación dividido en pequeñas tareas

0. **Conversación previa contigo**: confirmar §9.1 (ubicación del script) y §9.2 (extender
   `revisar_pendientes.py` vs. herramienta separada) antes de escribir una línea — son decisiones de
   arquitectura, no de implementación.
1. `firma` en `regla.schema.json` + validación semántica que lo exige cuando `estado == FIRMADA`. Test de
   esquema + no-regresión sobre los ficheros existentes. (≤1h)
2. Presentación campo a campo de cada entrada (reusa `_formatear_lectura`/`presentar` si se extiende
   `revisar_pendientes.py`) + las 4 opciones a/r/e/s, motivo de rechazo obligatorio. (≤2h)
3. Ledger append-only con motivo/curador/timestamp por decisión — extiende `resoluciones.jsonl` o crea uno
   nuevo, según la decisión de la tarea 0. (≤1h)
4. Generación de la regla `FIRMADA` (reusa `_construir_documento`/`_generar_regla` con `estado="FIRMADA"` y el
   nuevo bloque `firma`). (≤1h)
5. Reanudabilidad: dedup contra el ledger, con la decisión explícita de si incluye lo ya resuelto por
   `revisar_pendientes.py` (caso límite §6). (≤1h)
6. Golden tests de la propia herramienta + test de política ("ninguna regla con `estado: FIRMADA` carece de
   `firma`"). (≤1h)
7. **Ejecución real: sesión de curación de Pablo sobre las 101 entradas.** (sesión de Pablo, no de desarrollo)
8. `tests/golden/dbsua_preguntas.jsonl` (30 preguntas, o el número real honesto — ver §9.3) escritas después de
   la tarea 7, + runner contra `normativa/api.py`. Si `api.py` no expone hoy una consulta directa
   "regla → valor + cita" (su superficie pública actual es `normativa_aplicable`/`cobertura`, no una búsqueda
   puntual), puede hacer falta una función nueva de solo lectura — se decide en implementación, no lo asumo
   aquí. (≤2h, revisar al llegar)
9. Suite completa + cierre del PRD con la tabla de resultados real + `PROGRESS.md`.

## 12. Plan de pruebas

- Test de esquema: toda regla `FIRMADA` generada valida contra `regla.schema.json` ampliado, con `firma`
  presente.
- Test de política: ninguna regla llega a `estado: FIRMADA` sin `firma.curador` y `firma.fecha`.
- Test de reanudabilidad: dos ejecuciones sobre el mismo `verificacion_doble.jsonl` no repiten preguntas ya
  resueltas ni duplican ficheros.
- Test de rechazo: rechazar sin motivo falla explícito; rechazar con motivo no genera regla pero sí ledger.
- Golden: `tests/golden/dbsua_preguntas.jsonl`, 30/30 (o el número real honesto, documentado si es menor) vía
  `normativa/api.py`.
- Suite completa (`pytest`), porque toca `normativa/esquema/` y `normativa/validacion.py`, ficheros
  compartidos.

## 13. Métricas para medir el éxito

- De las 101 entradas: cuántas aprobadas (con y sin edición), cuántas rechazadas y motivo dominante, cuántas
  saltadas al cierre de la sesión.
- Cobertura real por tema (barandillas/escaleras/mesetas/resbaladicidad/huecos) — cuántas reglas firmadas caen
  en cada uno, honestamente, no forzado.
- 30/30 en el golden set (o el número real si es menor, con la razón documentada).
- Tiempo real que le toma a Pablo curar las 101 — dato para saber si este flujo es practicable a la escala de
  las siguientes DB (SI, HS3, HE1) o si hace falta repensarlo antes de escalarlo.

## 14. Posibles motivos para NO implementar la idea (así, ahora)

- **El riesgo §9.1 es real y no debe resolverse por inercia.** Implementar literalmente
  `python -m extraccion.curar` sin abordarlo antes rompe un test que protege una decisión de arquitectura ya
  tomada y probada, o la debilita en silencio. Ninguna de las dos es aceptable sin tu decisión explícita.
- **El argumento más fuerte contra construir algo nuevo es el propio §9.2:** `scripts/revisar_pendientes.py`
  ya resuelve la mayor parte de esto. La diferencia real cabe en una extensión de pocas horas, no en un módulo
  nuevo — construir desde cero sin señalar esto sería repetir trabajo ya hecho.
- **Alternativa honesta a considerar:** dado que hace unas horas decidiste explícitamente no depender de firma
  humana, ¿la reintroduces porque el producto la necesita (§9.5, aún sin resolver), o porque quieres avanzar
  el corpus con las 101 pendientes ya resueltas y el vehículo natural es simplemente terminar de usar
  `revisar_pendientes.py` tal cual existe, sin diferenciar un estado `FIRMADA` nuevo? Si la respuesta es la
  segunda, este PRD es innecesario: basta con ejecutar la herramienta que ya tienes. Te pido que la decisión
  de si `FIRMADA` aporta algo real más allá de "resuelto manualmente" quede explícita en la aprobación, no
  implícita.
- No veo motivo para bloquear el trabajo de fondo (avanzar las 101 pendientes hacia reglas evaluables): el
  corpus vacío sigue siendo el cuello de botella diagnosticado tres veces ya en este proyecto. El motivo para
  no implementar es de **forma**, no de fondo — los tres puntos de arriba son decisiones tuyas pendientes, no
  razones para no avanzar en absoluto.

---

**Decisión:** Aprobado por Pablo, 2026-08-21, con las tres resoluciones registradas en la cabecera. Golden set (§9.3) explícitamente excluido de este alcance.

## Cierre (2026-08-21)

Implementado con las tres resoluciones aplicadas tal cual, sin desviación:

1. **`scripts/curar_corpus.py`** (nuevo), dos subcomandos:
   - `python scripts/curar_corpus.py resolver <verificacion_doble.jsonl>` — presenta cada entrada (candidata_padre, parametro_nombre, motivo, lectura_a/b, cláusulas no reconocidas de la ruta B) y pide `[a]probar / [r]echazar con motivo / [e]ditar y aprobar / [s]altar`. Registra cada decisión en `extraccion/estado/curacion/resoluciones.jsonl` (append-only, con timestamp). No importa `normativa.loader`/`.validacion`/`.registro`/`.resolucion` para escribir nada — de hecho no recibe ni un directorio de salida (verificado por test, no solo por revisión).
   - `python scripts/curar_corpus.py firmar --curador NOMBRE --sha256-pdf HASH <candidatas_a.jsonl>` — lee las resoluciones «aprobada» del ledger, y para cada una sin firmar todavía genera su regla `estado: FIRMADA` (bloque `firma: {curador, fecha}`, `documento_sha256`, `literal` heredado tal cual del PDF), la valida contra el esquema, y la escribe SIN prefijo `_` (descubrible por el loader — a diferencia de `BORRADOR`/`VERIFICADA_AUTOMATICA`, que son deliberadamente invisibles). Registra cada firma en `extraccion/estado/curacion/firmas.jsonl`. Si el fichero de destino ya existe, no lo sobreescribe — lo reporta como conflicto y sigue con las demás (inmutabilidad verificada por test).
2. **`normativa/esquema/regla.schema.json`**: nuevo bloque `firma` (`curador`, `fecha`), aditivo.
3. **`normativa/validacion.py`**: nueva validación 19 (`validar_firma_de_regla_firmada`) — toda regla `estado: FIRMADA` sin `firma` completa (curador no vacío, fecha ISO real) falla la carga. Defensa en profundidad: protege incluso un YAML escrito a mano fuera de la herramienta.
4. **`scripts/generar_borrador_corpus.py::_construir_documento`**: extendido (no duplicado) con el parámetro opcional `firma`, reusado tanto por `curar_corpus.py` como, potencialmente, por cualquier futuro llamante — mismo patrón que ya usaban `estado`/`documento_sha256` para `VERIFICADA_AUTOMATICA`.
5. **`tests/test_curar_corpus.py`** (nuevo, 26 tests): las cuatro opciones de `resolver_uno` (incluido rechazo sin motivo y edición con valor inválido, ambos sin registrar nada); `procesar_resolver` reanudable y sin escribir reglas nunca; `procesar_firmar` exige `--curador`, genera regla válida, ignora rechazadas, es reanudable, y no sobreescribe una regla firmada preexistente; los dos actos verificados como separados por test explícito; validación 19 (4 casos); integración completa contra el loader real (`tests/fixtures/corpus_ficticio`, mismo patrón que `tests/test_normativa_borrador_no_afirma.py`) confirmando carga sin rechazos tras firmar una regla de prueba; y dos tests contra el fichero REAL de 101 entradas (saltar las 101 sin excepción, aprobar las 101 sin excepción).

**Verificado con datos reales:** las 101 entradas de `extraccion/estado/pendientes/codigotecnico__DB-SUA__3cfb5bbb135e.verificacion_doble.jsonl` se recorren de principio a fin sin ninguna excepción, tanto saltándolas todas como aprobándolas todas. Hallazgo no anticipado en el diseño: **ninguna de las 101 tiene simultáneamente `lectura_a` y `lectura_b` pobladas** — cada una trae exactamente una lectura (nunca las dos a la vez, confirmado leyendo `scripts/verificar_doble_ruta.py::comparar_padre`, que las genera en dos bucles disjuntos). El camino de "elegir entre A y B" que pide la tarea original sigue implementado y probado (`test_resolver_uno_aprueba_elige_entre_dos_lecturas`), pero no lo ejerce ninguna de las 101 reales — solo importaría si una futura DB produce un verdadero doble anclaje.

**Limitación conocida, documentada, no resuelta aquí (fuera de alcance):** firmar más de una regla de la misma `materia`+`patron` sin `usos`/`tipologias` propios choca con la validación 14 (aplicabilidad genérica) y tumba la carga del corpus completo — mismo límite ya documentado para `VERIFICADA_AUTOMATICA` en `docs/design/2026-08-21-limite-aplicabilidad-generica-verificada-automatica.md`. El criterio de aceptación de este PRD (una regla de prueba carga limpio) está cumplido; una sesión de firma real sobre las 101 tendrá que resolver esto antes o firmar como mucho una regla por materia hasta entonces.

**Suite completa:** `pytest -q`: **1263 passed, 18 skipped, 1 xfailed, 0 failed** (574s). Arrancado desde el verde declarado al cierre del Prompt 2 (1237 passed) — las 26 pruebas de más son las de este PRD. Los 2 warnings del resumen (`PytestUnraisableExceptionWarning` en `tests/test_bim_lector.py`, deallocator de `ifcopenshell`) son preexistentes y ajenos a este PRD.

**Golden set (§9.3):** no escrito, tal como resolvió Pablo. Queda como tarea posterior a una sesión real de curación (`python scripts/curar_corpus.py resolver` + `firmar` sobre las 101), con las preguntas aportadas por Pablo — no una plantilla rellenada a la fuerza.

## Adenda (2026-08-21, misma sesión): límite de aplicabilidad genérica, resuelto

Pablo preguntó, antes de dar la tarea por cerrada, el alcance real de la limitación
documentada arriba ("firmar más de una regla de la misma materia+patrón... choca
con la validación 14"). Verificado con datos reales, no con estimación:

**1. Número exacto donde empezaba a fallar: 2, no un volumen.** La clave de
`validar_sin_contradiccion` (validación 14) era `(materia, ámbito, usos, tipologías,
tipos_de_intervención, patrón)` — nada que identificara DE QUÉ EXIGENCIA se trataba.
Cualquier dos reglas que compartieran esa tupla colisionaban, sin importar que fueran
exigencias completamente distintas. Demostrado firmando 4 reglas reales de 4 artículos
distintos de DB-SUA (2.2, 1.2, 1.5, 3.1): 0 fallos con 1-3 reglas, **1 fallo `[14]` en
cuanto la 4ª compartió `materia=seguridad_utilizacion` + `patron=COMBINACION_LOGICA`
con una de las 3 anteriores** — la colisión no dependía del volumen total, dependía
solo de que dos reglas cualesquiera compartieran materia+patrón+aplicabilidad genérica,
que es el caso normal (no el raro) al firmar DB-SUA.

**2. Con el volumen real de esta semana (~90-100 reglas de DB-SUA, mayoritariamente
`seguridad_utilizacion`/`UMBRAL_SIMPLE`, todas con `aplicabilidad` genérica): sí,
chocabas seguro**, no en el peor caso — al firmar la segunda o tercera regla, no la
100ª.

**3. Arreglado en esta misma sesión, no dejado pendiente:**
- `normativa/validacion.py::validar_sin_contradiccion` — la clave ahora incluye
  también la cita del artículo (`norma.articulo`: documento básico, sección,
  apartado, punto, tabla) y `nombre` de la regla. Ninguno de los dos campos es
  inventado: ya estaban en el documento. Dos artículos distintos ya no compiten
  aunque compartan materia/patrón; dos transcripciones del MISMO artículo con el
  MISMO nombre (el error real que la validación 14 existe para atrapar) siguen
  colisionando — `test_14_dos_reglas_compitiendo_fallan_en_carga` (preexistente)
  lo sigue comprobando sin cambios.
- `scripts/curar_corpus.py::_generar_regla_firmada` — dos bugs relacionados
  encontrados auditando esto, corregidos de paso: (a) heredaba el `patron` del
  artículo padre en vez del de la cláusula atómica concreta (`_descomponer`'s
  `patron_override`, el mismo mecanismo que ya usa `verificar_doble_ruta.py`);
  (b) no aplicaba `sufijo_desambiguador`, así que firmar varias sub-candidatas
  del mismo artículo (p. ej. DB-SUA 1.4, ~15-40 exigencias bajo un único
  apartado) habría producido el mismo `concept_id` para todas. Ahora siempre
  se deriva de `parametro_nombre`.
- `docs/design/2026-08-21-limite-aplicabilidad-generica-verificada-automatica.md`
  marcado como resuelto (ver ese fichero), explicando por qué la solución elegida
  (ampliar la clave de contradicción) es preferible a la que el documento original
  anticipaba (derivar `usos`/`tipologias` reales por regla, que sí habría exigido
  criterio/interpretación no disponible sin curador).

**Verificación final, con datos reales:** las 20 candidatas reales de DB-SUA (40
parámetros) producen 39 reglas `FIRMADA` reales — escritas de verdad en disco,
cargadas de verdad por `normativa/loader.py` contra el corpus de fixtures —
**`hay_rechazos == False`**, 0 fallos `[14]`. Test permanente:
`tests/test_curar_corpus.py::test_loader_carga_sin_colision_al_firmar_todo_el_corpus_real_de_db_sua`.
Suite completa tras el arreglo: **1264 passed, 18 skipped, 1 xfailed, 0 failed**
(575s; la prueba nueva es la única añadida sobre el cierre anterior de este PRD).

**Alcance de la limitación tras el arreglo, para que quede honesto:** sigue siendo
posible, en teoría, que DOS reglas del MISMO artículo terminen con el MISMO `nombre`
si dos sub-candidatas distintas comparten `parametro_nombre` textualmente — no
observado en los datos reales de DB-SUA (cada `parametro_nombre` de la extracción es
descriptivo y distinto), pero no imposible por construcción. Si eso ocurriera, la
validación 14 lo bloquearía correctamente como conflicto real a resolver a mano — no
es una regresión del arreglo, es el comportamiento correcto ante una colisión de
nombre genuina.
