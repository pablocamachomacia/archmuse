# PRD — Pipeline de borradores de corpus DB-SUA

**Estado:** Implementado · **Fecha:** 2026-08-21 · **Fecha de cierre:** 2026-08-21 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-21, alcance completo del §11)

---

## 1. Problema que resuelve

El corpus normativo (`normativa/es/`) tiene **una** regla real transcrita (DB-SI 3, tabla 3.1). El motor de resolución (`normativa/resolucion.py`, 3.777 líneas) está completo y probado pero prácticamente sin contenido que evaluar. Esto ya estaba diagnosticado en `docs/design/2026-08-18-encargo-curador-normativo.md`: "cada semana sin contenido es una semana en la que el producto no puede verificar normativa aunque todo lo demás funcione".

La vía prevista hasta hoy para llenar el corpus era un **curador colegiado humano** transcribiendo a mano, con firma antes de que una materia fuera afirmable (`normativa/manifiesto.py`, estado `transcrito_sin_firmar` → firma → `parcial`/`completo`). Pablo decide hoy (2026-08-21, este mismo prompt) **no contratar curador**: sustituir la firma humana por transcripción doble independiente + cita literal enlazada al PDF oficial, verificable por el propio arquitecto usuario. Es una decisión de producto ya tomada, no algo que este PRD deba justificar — este PRD cubre solo el primer tramo técnico: generar los borradores de la primera ruta de extracción sobre DB-SUA, que ya tiene candidatas extraídas sin usar (`extraccion/estado/candidatas/codigotecnico__DB-SUA__3cfb5bbb135e.jsonl`, 20 fragmentos).

Origen: petición directa de Pablo, trasladando una secuencia de prompts de Fable 5 para ArchMuse V1, Fase A / Prompt 1.

## 2. Usuario afectado

Ninguno todavía de forma directa — es infraestructura de corpus, no una Skill de cara al arquitecto. El beneficiario indirecto es Pablo como curador único (Prompt 2 le da la herramienta de resolución de discrepancias) y, más adelante, el arquitecto usuario de la Skill `revision_normativa` (Prompt 3) que consumirá las reglas que este pipeline produce.

## 3. Objetivo de negocio

Es el cuello de botella real del vertical vendible (`AGENTE_BACKLOG.md` §0.3: "normativa/ — motor completo · **una** regla real transcrita"). Sin corpus no hay verificación normativa, sin verificación normativa no hay OP-3/OP-4, y sin eso no hay argumento de "50€/mes defendible". Este prompt no vende nada por sí solo, pero desbloquea la cadena Prompt 2 → Prompt 3 → OP-3/OP-4.

## 4. Objetivo técnico

Dado un `.jsonl` de candidatas de `extraccion/estado/candidatas/`, un script offline produce ficheros YAML conformes a `normativa/esquema/regla.schema.json`, cada regla marcada con un nuevo estado `BORRADOR`, más un informe de conversión y un fichero de pendientes-de-humano para lo descartado. Ninguna regla `BORRADOR` es evaluable por el motor de resolución bajo ninguna circunstancia.

## 5. Casos de uso

1. Pablo ejecuta `python scripts/generar_borrador_corpus.py extraccion/estado/candidatas/codigotecnico__DB-SUA__3cfb5bbb135e.jsonl` offline. Recibe N ficheros/reglas `BORRADOR` en `normativa/es/estatal/` (o un fichero nuevo, a decidir en implementación — ver §9) y un informe en terminal: cuántas candidatas entraron, cuántas se convirtieron, cuántas se descartaron y por qué.
2. Una candidata con tabla no parseable (p. ej. la Tabla 1.2 de la muestra vista, con ejes cruzados de localización × pendiente) no se inventa como regla: cae en el fichero de pendientes-de-humano con el motivo exacto.
3. Un desarrollador corre la suite de tests y el test de política (`grep` del motor + test) confirma que no existe ningún camino desde `estado: BORRADOR` hasta una afirmación de cumplimiento.

## 6. Casos límite

- Candidata con parámetro numérico que no aparece en el texto literal (regla de oro de `CLAUDE.md`: ningún número sin procedencia) → descartada a pendientes, nunca inventada.
- Candidata que ya coincide (mismo `concept_id`) con la única regla real existente (`seguridad_incendio.yaml`, DB-SI) → no aplica aquí (candidatas son DB-SUA), pero el script debe detectar colisión de `concept_id` si se reusa sobre otro DB y no sobrescribir en silencio.
- Candidata con confianza `"Baja"` según `extraccion/confianza.py` (fallos graves) → ¿se genera igualmente como `BORRADOR` con la confianza anotada, o va directa a pendientes? Ver §9, es una decisión de producto pendiente de tu confirmación, no la asumo.
- El `.jsonl` de candidatas está vacío o el fichero no existe → error explícito, el script no genera nada.
- Dos candidatas del mismo `.jsonl` producen el mismo `concept_id`/`instance_id` → conflicto declarado en el informe, ninguna de las dos se escribe silenciosamente sobre la otra.

## 7. Flujo del usuario

Pablo (único operador de este script, no hay UI): ejecuta el comando desde terminal → lee el informe de conversión → revisa el fichero de pendientes-de-humano → decide manualmente qué hacer con lo descartado (este PRD no cubre esa resolución; es el Prompt 2).

## 8. Criterios de aceptación

Los del propio Prompt 1 de Fable, sin relajar ninguno:

- El script corre offline (sin red, sin LLM) sobre las candidatas reales de DB-SUA.
- Genera N reglas `BORRADOR` válidas contra `regla.schema.json` (ampliado con el nuevo estado).
- Cada regla `BORRADOR` lleva cita literal del artículo, referencia exacta (DB, sección, apartado, tabla si aplica) y los parámetros extraídos con su confianza de `extraccion/confianza.py`.
- Existe `normativa/pendientes/...` (o ruta equivalente) con las candidatas descartadas y el motivo — nunca inventadas.
- Test de política: ninguna regla `BORRADOR` puede llegar a una afirmación de cumplimiento (grep del motor de resolución + test que lo verifica en ejecución, no solo en texto).
- Golden test: al menos 3 reglas generadas comparadas contra su candidata origen.
- La suite completa pasa (afecta a `normativa/esquema/`, ficheros compartidos).

## 9. Riesgos

**Riesgo de arquitectura, el más importante — decisión de producto, no la tomo yo:** ya existe un estado de cobertura a nivel de *materia* en `normativa/manifiesto.py` (`ESTADOS = ("completo", "parcial", "transcrito_sin_firmar", "ausente", "no_competente")`), gobernado por la validación 18 y atado al concepto de firma colegiada que hoy se abandona. El nuevo estado `BORRADOR` que pide este prompt vive a nivel de *regla individual* en `regla.schema.json`, no de materia. Estos dos state machines van a coexistir y **hay que decidir cómo se relacionan**:

- ¿El manifiesto de cobertura por materia pasa a derivarse mecánicamente del estado de sus reglas (materia `parcial`/`completo` solo si todas sus reglas activas son `VERIFICADA_AUTOMATICA` o `FIRMADA`, nunca si hay `BORRADOR` de por medio), sustituyendo `transcrito_sin_firmar`/`pendiente_firma_colegiado`?
- ¿O se mantienen ambos vocabularios en paralelo, con el riesgo de que diverjan y uno diga "parcial" mientras el otro dice "BORRADOR"?

**Resuelto por Pablo (2026-08-21):** el manifiesto de cobertura por materia pasará a derivarse mecánicamente del estado de sus reglas — materia `parcial`/`completo` solo cuando todas sus reglas activas sean `VERIFICADA_AUTOMATICA` o superior — sustituyendo `transcrito_sin_firmar`/`pendiente_firma_colegiado`. Este PRD (Prompt 1) sigue sin tocar `manifiesto.py`: `BORRADOR` no es afirmable de todos modos, así que no hay nada que derivar todavía. El rewiring de `manifiesto.py` para leer estados de regla es tarea explícita del Prompt 2, no deuda ambigua.

**Riesgo de alcance:** `docs/design/2026-08-18-encargo-curador-normativo.md` queda obsoleto por la decisión de hoy (sin curador colegiado). No lo borro — igual que `CLAUDE.md` pide para el resto de piezas congeladas — pero hay que marcarlo explícitamente como superado, con fecha, para que ninguna sesión futura lo tome como plan vigente.

**Riesgo técnico menor:** las tablas con dos ejes cruzados (la Tabla 1.2 de la propia muestra de candidatas DB-SUA) son exactamente el caso "tabla no parseable" que el propio prompt anticipa como motivo de descarte. Esperable que buena parte de las 20 candidatas caigan en pendientes-de-humano en esta primera pasada — no es un fallo del script, es la realidad del contenido.

**No compite con `REFACTOR_MASTERPLAN.md`:** es corpus, no endurecimiento de producto existente.

## 10. Impacto sobre módulos existentes

- `normativa/esquema/regla.schema.json`: añade `"estado": {"enum": ["BORRADOR", ...]}` a cada regla. Cambio aditivo, pero toca el contrato que `normativa/validacion.py` (17 validaciones semánticas) y `normativa/resolucion.py` ya asumen — hay que auditar que ningún camino de `resolucion.py` itera reglas sin filtrar por estado.
- `normativa/es/estatal/`: nuevos ficheros YAML (o subcarpeta a decidir) conviven con `seguridad_incendio.yaml`, la única regla real hoy VERIFICADA/FIRMADA-equivalente.
- `extraccion/confianza.py`: se reusa, no se modifica.
- `normativa/manifiesto.py`: no se toca en este PRD (ver riesgo §9), pero queda como deuda declarada, no oculta.
- Nuevo: `scripts/generar_borrador_corpus.py`, y el fichero de pendientes-de-humano (ruta a definir, p. ej. `extraccion/estado/pendientes/`).

## 11. Plan de implementación dividido en pequeñas tareas

1. Añadir `estado` (enum `BORRADOR` por ahora, con hueco para los estados del Prompt 2) a `regla.schema.json` + actualizar `normativa/validacion.py` si alguna de las 17 validaciones asume su ausencia. (≤2h)
2. Auditar `normativa/resolucion.py`: confirmar (o añadir) el filtro que excluye toda regla no evaluable por estado; escribir el test de política que lo prueba en ejecución, no solo por grep. (≤2h)
3. Parser de candidatas `.jsonl` → estructura intermedia tipada, reusando `extraccion/modelo.py` si ya cubre la forma. (≤2h)
4. Extractor de parámetros + cita literal + referencia exacta (DB/sección/apartado/tabla) desde el texto de cada candidata, apoyado en `extraccion/confianza.py` para la confianza. (≤2h, probablemente 2 tareas si las tablas cruzadas dan trabajo aparte)
5. Detección y enrutado de descartes (ambigüedad, tabla no parseable, colisión de `concept_id`) al fichero de pendientes-de-humano, con motivo legible. (≤2h)
6. Escritura de los YAML `BORRADOR` conformes al esquema + informe de conversión en terminal. (≤2h)
7. Golden tests (≥3 reglas contra su candidata origen) + test de política del paso 2 + tests de forma contra el esquema. (≤2h)
8. Marcar `docs/design/2026-08-18-encargo-curador-normativo.md` como superado por la decisión de 2026-08-21, con una nota al principio (mismo patrón que el AVISO de `CLAUDE.md`), sin borrarlo. (≤30min)

## 12. Plan de pruebas

- Test de esquema: todo YAML generado valida contra `regla.schema.json` ampliado.
- Golden tests: 3+ reglas generadas, comparadas campo a campo contra su candidata origen (cita, referencia, parámetro, confianza).
- Test de política: ninguna regla `BORRADOR` alcanza una afirmación de cumplimiento — ejecutando el motor de resolución sobre un corpus de prueba que mezcle `BORRADOR` con una regla afirmable, y comprobando que la `BORRADOR` no aparece en el resultado.
- Test de informe: dado un `.jsonl` con una candidata sana y una con tabla cruzada, el informe cuenta 1 convertida / 1 descartada con el motivo correcto.
- Suite completa (`pytest`), porque toca `normativa/esquema/` y potencialmente `normativa/validacion.py`, ficheros compartidos.

## 13. Métricas para medir el éxito

- N reglas `BORRADOR` generadas sobre las 20 candidatas de DB-SUA (número real, no estimado).
- % de candidatas descartadas y motivo dominante (mide si el extractor necesita mejorar o si el contenido real es así de irregular).
- 0 afirmaciones de cumplimiento originadas en una regla `BORRADOR` — verificado por el test de política, no por inspección.

## 14. Posibles motivos para NO implementar la idea (ahora, así)

- **El riesgo de arquitectura de §9 es real y barato de resolver antes, caro de resolver después.** Si generamos borradores ahora y en el Prompt 2 resulta que el manifiesto de cobertura por materia necesita rediseñarse para leer estados de regla, parte de este trabajo se retoca. Alternativa: decidir la relación manifiesto-materia ↔ estado-regla *antes* de escribir el script, aunque sea en una conversación de 10 minutos, no en un PRD aparte — no lo bloqueo por esto, pero lo dejo explícito para que la decisión no se tome por inercia en el Prompt 2.
- **El corpus de candidatas de DB-SUA es pequeño (20 fragmentos) y probablemente con alta tasa de descarte** (tablas cruzadas). El retorno inmediato de este prompt puede ser bajo en reglas utilizables — sigue mereciendo la pena porque desbloquea el pipeline reutilizable para DB-SI y el resto de DBs, no por el rendimiento de esta primera pasada.
- No veo motivo para no implementarlo en absoluto: el corpus vacío es el cuello de botella ya diagnosticado en tres documentos distintos del proyecto (`encargo-curador-normativo.md`, `AGENTE_BACKLOG.md` §0.3, este mismo prompt de Fable), y la decisión de producto que lo desbloquea (sin curador colegiado) ya está tomada por Pablo.

---

**Decisión:** Aprobado por Pablo, 2026-08-21. Alcance: las 8 tareas del §11. Relación manifiesto-materia ↔ estado-regla resuelta en §9 (deriva del estado de regla; se implementa en el Prompt 2, no aquí).

## Cierre (2026-08-21)

Las 8 tareas del §11 completas:

1. `estado` añadido a `normativa/esquema/regla.schema.json` como campo opcional (`enum: ["BORRADOR", null]`), sin tocar `required` — `seguridad_incendio.yaml` (la única regla anterior a este campo) sigue válida sin cambios.
2. Guardarraíl explícito en `normativa/resolucion.py::_paso1_candidatas`: toda regla con `estado: BORRADOR` se descarta (`no_aplica`, motivo explícito) antes de cualquier otro paso del resolver. Grep literal: `regla.get("estado") == "BORRADOR"`.
3. `scripts/generar_borrador_corpus.py`: convierte candidatas cuyo `parametro` no exige elegir eje ni componer variables (UMBRAL_SIMPLE/UMBRAL_CON_EXCEPCION con un único parámetro citado, o PRESENCIA_OBLIGATORIA sin parámetro). Todo lo demás va a pendientes-de-humano con motivo categorizado — ver docstring del script para la frontera exacta y por qué (cita `extraccion/modelo.py::ReglaCandidata`).
4. Detección y enrutado de descartes: 6 categorías de motivo distintas, cada candidata descartada conserva su `texto_original` íntegro.
5. Escritura de YAML `BORRADOR` + informe de conversión en terminal.
6. Golden tests + test de política (`tests/test_generar_borrador_corpus.py`, `tests/test_normativa_borrador_no_afirma.py`).
7. `docs/design/2026-08-18-encargo-curador-normativo.md` marcado SUPERADO con fecha, sin borrar.
8. Suite completa verificada: 1169 passed, 18 skipped, 1 xfailed. Los únicos 2 fallos (`test_el_registro_se_puebla_por_descubrimiento`, `test_el_registro_sigue_dentro_del_tamano_que_C4_permite`) son preexistentes a esta sesión — confirmado con `git stash` antes de tocar nada — y no están en el alcance de este PRD: el registro de capacidades del agente ya estaba en 13 contra un techo C4 de 12 antes de empezar. Se los señalo a Pablo aparte; no los he tocado.

**Resultado real sobre las 20 candidatas de DB-SUA:** 3 convertidas a `BORRADOR`
(`es.rd_173_2010.seguridad_utilizacion.2_2_atrapamiento`,
`5_1_ambito_de_aplicacion`, `7_1_ambito_de_aplicacion`), 17 a pendientes
(`extraccion/estado/pendientes/codigotecnico__DB-SUA__3cfb5bbb135e.pendientes.jsonl`).
Tasa de conversión baja (15%) porque el contenido real de DB-SUA es
mayoritariamente artículos que agrupan varias exigencias bajo un mismo
segmento (8 de las 17 descartadas) — exactamente el caso que §9/§14
anticipaban, no un fallo del extractor.

**Nota no anticipada en el PRD original, resuelta durante la implementación:**
la extracción no captura boletín ni identificador oficial del RD que aprueba
cada Documento Básico (`documento_identificador`/`organismo`/`url_oficial` sí,
pero no `boletin`). Sin esos dos campos no se puede construir una
`NormaFuente` citable. El script añade una única cita verificada a mano (RD
173/2010, BOE-A-2010-3811, para DB-SUA) en una tabla propia, claramente
señalada como no-extraída en la cabecera de cada YAML generado — para
revisar contra el BOE antes de promover cualquiera de estas tres reglas en
el Prompt 2.
