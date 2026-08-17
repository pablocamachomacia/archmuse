# PRD — CAP-5: Altura de evacuación

**Estado:** Borrador · **Fecha:** 2026-08-10 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

**Diseño de referencia:** `docs/audits/DB-SI_IMPLEMENTATION_PLAN.md` §2 (ficha `CAP-5`), §3 (grafo de dependencias), §6 (qué
desbloquea), §7 (qué sigue en `UNKNOWN`), §12 (Bloque C), §14 (riesgo #3); `docs/design/DB-SI_DECISIONS.md` §5.4 (cita literal del
Anejo SI A); `docs/design/DB-SI_FACT_MODEL.md` §2.1 (catálogo, fila `altura_evacuacion`); `docs/audits/DB-SI_REVIEW.md` fichas `C11`,
`C15`, `C18`; `normativa/terminologia/dbsi_anejo_a.yaml` (concept_id ya ingerido); `analyzer/planta.py` y
`docs/prd/2026-08-09-cap4-modelo-de-planta.md` (CAP-4, cerrado, `8bd8f94`) como precedente directo de diseño y como dependencia dura.

**Alcance de este PRD:** el hecho `altura_evacuacion` a nivel de edificio/proyecto (un valor por análisis, no por vivienda ni por
planta — ver §4bis), sus dos únicas fuentes admitidas (declaración directa; hipótesis `plantas × altura_libre_m` sólo en
`/api/generar`), y tres avisos condicionales, no vinculantes, que lo consumen para `C11`, `C15` y `C18`. **No incluye**: ningún
cálculo de una altura de evacuación real (exige `CAP-6`, ver §4bis), ninguna regla con veredicto `PASS`/`FAIL` para `C11`/`C15`/`C18`
(siguen `UNKNOWN`, sin cambios, según `DB-SI_REVIEW.md`), la corrección de la convención de numeración de planta que CAP-4 dejó
registrada como deuda (`docs/prd/2026-08-09-cap4-modelo-de-planta.md`, sección final), ni `CAP-6`/`CAP-7`/`CAP-8`.

---

## 1. Problema que resuelve

`C11` (protección de escaleras), `C15` (evacuación de personas con discapacidad) y `C18` (aproximación de bomberos) son hoy tres
avisos genéricos de "no evaluable" sin ningún dato de altura detrás — `get_missing_data_warnings` ya dice, correctamente, que no hay
elementos de escalera ni entorno urbano modelados. Pero ninguno de los tres avisos le dice al arquitecto **cuándo debería
preocuparse**: el umbral de 14 m (`C11`) es, según la propia revisión normativa, un límite que "muchos proyectos plurifamiliares
reales rozan" (`DB-SI_REVIEW.md`, ficha `C11`), y hoy ArchMuse no distingue un edificio de 3 plantas de uno de 8 al emitir ese aviso.

Origen: `DB-SI_IMPLEMENTATION_PLAN.md` ficha `CAP-5` y `DB-SI_REVIEW.md`, que en las tres fichas (`C11`, `C15`, `C18`) recomiendan
explícitamente "valorar el aviso condicional", nunca una comprobación. No es una idea nueva de este PRD: es completar una
recomendación ya escrita y verificada por dos documentos de auditoría independientes.

## 2. Usuario afectado

El mismo perfil que CAP-4: el arquitecto que decide confiar su firma a ArchMuse porque cita el artículo real
(`NORTH_STAR_2031.md`, vía `MOAT_ANALYSIS.md` §1). Aquí el matiz es distinto al de CAP-4: no se trata de corregir un ámbito citado
incorrectamente, sino de dar al arquitecto una señal de alerta temprana y honesta —"con esta altura estimada, revisa esto"— en vez de
un silencio o un aviso genérico idéntico para un edificio de 2 plantas y uno de 9.

## 3. Objetivo de negocio

1. **Convertir tres avisos genéricos en tres avisos accionables**, sin fabricar ninguna comprobación de cumplimiento que ArchMuse no
   puede sostener — la misma disciplina de honestidad que ya justificó CAP-1→CAP-4.
2. **Es la pieza que `DB-SI_IMPLEMENTATION_PLAN.md` §12 agrupa junto a CAP-4 en "Bloque C"** — con CAP-4 ya cerrado, CAP-5 es la
   mitad pendiente de ese bloque, no una iniciativa nueva sin relación con lo ya aprobado.
3. **No desbloquea ninguna regla con veredicto.** Hay que decirlo aquí, sin rodeos, porque cambia la proporción de valor frente a
   CAP-4: aquella cerró con `C01` parcial (un `FAIL`/`UNKNOWN` real). Ésta no cierra ninguna regla — ver §14.

## 4. Objetivo técnico

Una vez implementado, debe ser observable que:

- Existe un hecho `altura_evacuacion` (`analyzer/altura_evacuacion.py`), con las mismas cuatro propiedades del contrato
  (`hechos.py`): estado, confianza, procedencia, motivo si es `UNKNOWN`.
- El hecho cita `referencia_normativa = "es.cte.db_si.anejo_a.altura_de_evacuacion"` — concept_id ya presente en
  `normativa/terminologia/dbsi_anejo_a.yaml`, verificado en §5.4 de `DB-SI_DECISIONS.md`. Es el único de los cinco hechos de
  CAP-1→CAP-5 que puede citar el Anejo SI A por su nombre exacto de concepto desde el primer commit, sin ingesta adicional.
- El hecho **nunca** alcanza `KNOWN` por cálculo interno de ArchMuse. Sólo dos caminos producen un valor: declaración directa
  (`KNOWN`) o la hipótesis `plantas × altura_libre_m` en `/api/generar` (`ESTIMATED`, confianza **Baja**). Todo lo demás es
  `UNKNOWN` — nunca `NO_APLICABLE` (todo edificio tiene una altura de evacuación real, aunque ArchMuse no la conozca).
- Existen tres funciones de aviso condicional (`analyzer/avisos_altura_evacuacion.py`), una por regla (`C11`, `C15`, `C18`), que
  consumen el hecho y devuelven **un mensaje informativo o nada — nunca un `Result` con `passed`, nunca una entrada de
  `classify_problems`/`IssueReport`.** `evaluator.py` no se modifica.
- Un hecho `UNKNOWN` no dispara ningún aviso (D3 de `DB-SI_DECISIONS.md`: un insumo `UNKNOWN` no sostiene ninguna afirmación, ni
  siquiera condicional).

### 4bis. Qué es exactamente la altura de evacuación, y por qué ArchMuse no puede calcularla hoy

Cita literal, Anejo SI A (`normativa/terminologia/dbsi_anejo_a.yaml`, concept_id `es.cte.db_si.anejo_a.altura_de_evacuacion`):

> *«Máxima diferencia de cotas entre un origen de evacuación y la salida de edificio que le corresponda. A efectos de determinar la
> altura de evacuación de un edificio no se consideran las plantas más altas del edificio en las que únicamente existan zonas de
> ocupación nula.»*

Dos datos que esta definición exige y que ArchMuse **no tiene en ningún flujo**:

1. **Origen de evacuación** y **salida de edificio**, ambos conceptos de `CAP-6` (núcleo de comunicación y salidas), bloqueado por
   el hallazgo §1.1 de `DB-SI_IMPLEMENTATION_PLAN.md` (bloques del DXF sin insertar en modelspace).
2. **Cota real** (diferencia de nivel), que ni el flujo DXF ni `/api/generar` modelan — `/api/generar` sólo tiene
   `edificio.altura_libre_m` (altura libre entre suelo y techo de una planta tipo) y `edificio.plantas` (recuento), ninguno de los
   dos es una cota.

`plantas × altura_libre_m` **no es la magnitud que la norma define**, por dos motivos verificables, no uno:

- Ignora el canto de forjado: un edificio de 8 plantas con 2,80 m libres da 22,4 m por esa fórmula y unos 26 m reales
  (`DB-SI_IMPLEMENTATION_PLAN.md`, ficha `CAP-5`) — error ≈15 %, que cae exactamente sobre los saltos de 14/28 m de la tabla.
- La propia definición **excluye del cómputo las plantas más altas que sean sólo zona de ocupación nula** (trasteros, cuartos de
  instalaciones). `plantas × altura_libre_m` no sabe distinguir esas plantas — no tiene el dato (depende de la taxonomía de locales
  no habitables, fuera de alcance de `CAP-2`/`CAP-3`) — así que **la fórmula puede sobreestimar**, no sólo por el forjado.

**Consecuencia que se fija aquí y gobierna todo lo demás:** `CAP-5` no calcula una altura de evacuación derivada `KNOWN`. La única
vía a `KNOWN` es que el arquitecto la declare directamente (él sí conoce, o puede calcular, la cota real de su propio proyecto).

### 4ter. Las dos fuentes de `altura_evacuacion`, sin ambigüedad entre ellas

| | Altura **declarada** | Altura **estimada** (`plantas × altura_libre_m`) | Altura **desconocida** |
|---|---|---|---|
| Estado del hecho | `KNOWN` | `ESTIMATED` | `UNKNOWN` |
| Fuente | Campo de formulario nuevo, en `/api/analizar` **y** en `/api/generar` (§7, §10) | `edificio.plantas` × `edificio.altura_libre_m`, sólo en `/api/generar` — sin equivalente en `/api/analizar` (§4quater) | Ninguna de las dos anteriores está presente |
| Confianza | Alta | **Baja** — no Media (§4quinquies) | — |
| Naturaleza (`DECISION_ENGINE.md` §11) | Hecho | Hipótesis explícita, con sesgo conocido y en la dirección insegura (§4bis) | — |
| Prevalece sobre | La estimada, si ambas existen y difieren — mismo principio que ya usa CAP-4 (declarada > convención de nombre) | Nada — es la fuente más débil que aun así se emite | — |
| ¿Se usa para plantas bajo rasante / evacuación ascendente? | Si el arquitecto la declara así, sí (es su dato) | **No.** La hipótesis sólo cubre plantas sobre rasante y evacuación descendente (§4quater, §6 "qué NO debe hacer") | — |
| ¿Puede alimentar un `PASS`/`FAIL` de `C11`/`C15`/`C18`? | **No, ninguna de las dos.** Sólo alimentan avisos informativos (§4, §6) | **No** | — |

**Por qué no hay una tercera fuente "derivada de CAP-4":** `sobre_rasante` (CAP-4, por unidad) es un booleano sin magnitud — dice si
una planta está por encima de rasante, no cuántos metros. No aporta ningún dato que `CAP-5` pueda sumar. Se usa únicamente como
filtro (§4quater), nunca como insumo numérico.

### 4quater. Qué ocurre con combinaciones parciales de `sobre_rasante`, `plantas` y `altura_libre_m`

| Datos disponibles | Resultado |
|---|---|
| Sólo `sobre_rasante` (CAP-4, por vivienda) | `UNKNOWN`. Un booleano no es una magnitud; no sostiene ninguna hipótesis por sí solo |
| Sólo `plantas`, sin `altura_libre_m` | `UNKNOWN`. No hay hipótesis parcial — la fórmula exige los dos factores |
| Sólo `altura_libre_m`, sin `plantas` | `UNKNOWN`, mismo motivo |
| `plantas` + `altura_libre_m`, en `/api/generar` | `ESTIMATED` (§4ter). La hipótesis usa el número de plantas **sobre rasante únicamente** — ver nota siguiente |
| `plantas` + `altura_libre_m`, pero **el proyecto tiene declarada `altura_evacuacion_m` directamente** | El valor declarado prevalece (`KNOWN`); la hipótesis no se calcula ni se muestra como alternativa descartada |
| Cualquier combinación en `/api/analizar` sin declaración directa | `UNKNOWN` siempre. `/api/analizar` **no tiene** ningún equivalente a `edificio.plantas`/`altura_libre_m` — no existe una vía de hipótesis en ese flujo, no es una omisión de este PRD (§4bis, §10) |

**Nota sobre "plantas sobre rasante únicamente":** ver **P5.1** en §14/decisiones pendientes — el propio número de `edificio.plantas`
tiene hoy una ambigüedad de convención sin resolver en el código (¿incluye la planta baja o no?), documentada por CAP-4 como deuda
conocida. Este PRD no puede fijar la fórmula exacta (`plantas × altura_libre_m` vs. `(plantas - 1) × altura_libre_m`) sin resolver
antes esa ambigüedad — se marca como decisión pendiente, no se elige una de las dos por comodidad.

### 4quinquies. Representación en `Hecho`, y por qué no degrada la semántica de `ESTIMATED`

`hechos.py` ya define `ESTIMATED` como *"obtenido por hipótesis explícita, que viaja con él"* — no es un estado nuevo que este PRD
necesite inventar; es exactamente el estado que ya usan CAP-2 (`uso_previsto` inferido de `tipologia`) y CAP-4 (`planta` inferida de
la convención de nombre). Los tres casos son, con propiedad, "una hipótesis explícita, no una declaración directa": eso es lo que
`ESTIMATED` significa en este modelo desde que se definió, no algo que CAP-5 le añada.

Lo que sí distingue a la hipótesis de CAP-5 de las de CAP-2/CAP-4, y **la razón concreta por la que este PRD fija su confianza en
Baja y no en Media** (a diferencia de la convención de nombre de CAP-4, que es Media):

| | CAP-4 (`planta` por convención de nombre) | CAP-2 (`uso_previsto` por tipología) | CAP-5 (`altura_evacuacion` por `plantas×altura_libre`) |
|---|---|---|---|
| Tipo de inferencia | Patrón de texto determinista | Mapeo declarado y citable (`plurifamiliar → Residencial Vivienda`) | Fórmula física con sesgo **conocido, medido y en dirección insegura** (§4bis) |
| ¿Puede estar simplemente equivocada por azar? | Sólo si el nombre miente | Sólo en casos límite (uso mixto no declarado) | **Siempre** se desvía, y la propia norma advierte que además puede sobreestimar por la exclusión de plantas de ocupación nula |
| Confianza fijada | Media | Media | **Baja** |

Esto usa un eje que el modelo ya tiene (`confianza`, independiente de `estado`, `EVIDENCE_MODEL.md`/`DB-SI_FACT_MODEL.md` P5) para
expresar una diferencia real de fiabilidad, en vez de inventar un quinto estado o una bandera nueva en el `Hecho`. Es la misma regla
de disciplina que ya impidió inventar una definición de superficie construida en CAP-4: usar el mecanismo que el contrato ya
ofrece, no ampliarlo por conveniencia (`CONSTRAINT_MODEL.md` §14, "nunca ampliar el catálogo").

`procedencia` debe empezar por `"HIPOTESIS:"`, igual que ya hace `planta()` en su rama `ORIGEN_CONVENCION_NOMBRE` — mismo patrón
textual, para que cualquier consumidor futuro que ya sepa reconocer ese prefijo en `planta` lo reconozca también aquí sin aprender
una convención nueva. `diagnostico` debe guardar los dos factores brutos usados (`plantas`, `altura_libre_m`), igual que `planta()`
guarda `sobre_rasante` — trazabilidad completa hasta el dato de formulario original.

**Sobre la advertencia general que ya rige todo `ESTIMATED` en este motor:** `uso_previsto.py` ya deja escrito, como principio
general y no específico de CAP-2, que *"un hecho `ESTIMATED` no puede sostener por sí solo una afirmación de cumplimiento normativo;
puede sostener un aviso"*. `CAP-5` no necesita una regla nueva para esto — hereda una que ya existe y que sus dos avisos (`C11`,
`C15`) cumplen por construcción, al no producir nunca un `Result` con `passed` (§4, §6).

## 5. Casos de uso

**CU1 — Arquitecto declara la altura de evacuación directamente, en cualquiera de los dos flujos.** `altura_evacuacion` sale
`KNOWN`, confianza Alta, con la cita del Anejo SI A. Si supera 14 m, se emite el aviso de `C11`; si se acerca o supera 28 m, el de
`C15`; si supera 9 m, el de `C18` — los tres pueden coexistir.

**CU2 — Proyecto generado (`/api/generar`) sin declaración directa, con `edificio.plantas`/`altura_libre_m` ya informados (siempre
lo están: tienen valor por defecto, `1` y `2,8` respectivamente).** `altura_evacuacion` sale `ESTIMATED`, confianza Baja, con
`procedencia` marcada `"HIPOTESIS: ..."`. Los avisos de `C11`/`C15`/`C18` pueden dispararse igual que en CU1, pero su texto debe
dejar explícito que la altura es una estimación, no una medición.

**CU3 — Proyecto analizado por DXF (`/api/analizar`) sin declarar altura de evacuación (el caso de `ejemplo.dxf`, y el caso por
defecto de todo proyecto DXF hasta que se rellene el nuevo campo).** `altura_evacuacion` sale `UNKNOWN`. Ninguno de los tres avisos
se dispara — no hay "aviso por defecto" ni "aviso conservador ante la duda": silencio explícito, con el hecho disponible para quien
inspeccione el proyecto y quiera saber por qué no hay aviso.

**CU4 — Edificio de 3 plantas, `altura_libre_m` = 2,8 m (`/api/generar`, valores por defecto).** Estimación ≈ 8,4 m (según se
resuelva P5.1). Ningún aviso se dispara — está por debajo de los tres umbrales.

**CU5 — Edificio de 6 plantas sobre rasante, valores por defecto.** Estimación ≈ 16,8 m (según P5.1) — cruza el umbral de 14 m.
Se dispara el aviso de `C11` ("verificar protección de escalera, DB-SI 3 §5 Tabla 5.1"); no se disparan `C15` (28 m) ni `C18` (9 m
ya lo supera, así que si el umbral es 9 m, **sí se dispara** — ver CU6 para el caso límite exacto).

**CU6 — Cualquier edificio con altura de evacuación (declarada o estimada) superior a 9 m pero muy por debajo de 14 m.** Se dispara
únicamente el aviso de `C18` (espacio de maniobra de bomberos) — es el umbral más bajo de los tres, y los tres son independientes
entre sí, no escalonados exclusión mutua.

**CU7 — Declaración directa que contradice la hipótesis calculable (`/api/generar`, ambos datos presentes y distintos).** La
declaración prevalece (`KNOWN`), la hipótesis no se calcula. Se registra en `diagnostico` que existían `plantas`/`altura_libre_m`
disponibles, por si algún día interesa auditar la discrepancia — no se muestra como conflicto al arquitecto, a diferencia del caso
de planta de CAP-4 (aquí no hay dos fuentes con estado de "declaración" cada una; una es declaración y la otra es hipótesis débil,
así que no hay conflicto real que mostrar, sólo una fuente que se descarta por ser más débil).

## 6. Casos límite

| Caso | Comportamiento exigido |
|---|---|
| Altura exactamente en un umbral (14,00 / 28,00 / 9,00 m) | Se dispara el aviso (`>=`, no `>` — ante la duda de redondeo, avisar es la dirección segura; sin cita normativa exacta de "estrictamente mayor" verificada para ninguno de los tres, se documenta la elección) |
| `altura_evacuacion` `UNKNOWN` | Ningún aviso se dispara, sin excepción — un insumo `UNKNOWN` no sostiene ni siquiera un aviso condicional (D3 de `DB-SI_DECISIONS.md`) |
| Plantas bajo rasante (`sobre_rasante=False`, número negativo, CAP-4) | Excluidas de la hipótesis (§4quater). No se calcula una "altura de evacuación ascendente" — fuera de alcance (§4bis, §7 de `DB-SI_REVIEW.md` para los umbrales 2,80/6,00 m de evacuación ascendente de `C11`, que este PRD no cubre) |
| Campo de declaración con texto no numérico o negativo | `UNKNOWN` con motivo "declaración no interpretable", nunca un `KNOWN` forzado — mismo criterio que `normalizar_declaracion_planta` |
| `/api/generar` con `edificio.plantas = 1` (valor por defecto, edificio de una planta) | `ESTIMATED` con un valor bajo (≈ altura libre de una planta); no se dispara ningún aviso salvo que además supere 9 m, lo cual con una planta y valores por defecto no ocurre |
| Proyecto con `altura_evacuacion` `ESTIMATED` que cruza 28 m | Se disparan `C11` y `C15` a la vez (y `C18`, que tiene el umbral más bajo) — los tres textos deben decir, cada uno, que la altura es una estimación, no repetir la advertencia una sola vez de forma ambigua sobre a cuál de los tres aplica |
| Arquitecto declara `altura_evacuacion_m` = 0 o negativa | `UNKNOWN` — no es un valor físicamente admisible para esta magnitud; se trata igual que un texto no interpretable |

## 7. Flujo del usuario

1. En `/api/analizar`, junto a "Planta de este análisis" (CAP-4), aparece un nuevo campo opcional: **"Altura de evacuación (m)"** —
   numérico, sin valor por defecto, con ayuda que remite a la definición del Anejo SI A en una frase.
2. En `/api/generar`, el mismo campo aparece en la sección de datos de edificio, junto a `plantas`/`altura_libre_m`, también
   opcional. Si se rellena, prevalece sobre la hipótesis (CU7). Si no, ArchMuse calcula la hipótesis automáticamente a partir de los
   datos que el arquitecto ya introduce para generar el proyecto — sin pedir un dato nuevo obligatorio.
3. El informe (JSON) expone `proyecto.altura_evacuacion` con la misma forma que `proyecto.planta`/`proyecto.usos`: estado,
   confianza, valor si lo hay, motivo si es `UNKNOWN`.
4. Si el hecho es `KNOWN` o `ESTIMATED` y cruza alguno de los tres umbrales, el informe muestra hasta tres avisos informativos
   (`proyecto.avisos_evacuacion`, nuevo), cada uno con su cita DB-SI, nunca como "incidencia" ni con severidad de cumplimiento —
   visualmente distintos de los `IssueReport` existentes, para no confundir a un aviso con un `FAIL`.

## 8. Criterios de aceptación

1. `analyzer/altura_evacuacion.py` existe, expone una función que devuelve un `Hecho` con las cuatro propiedades del contrato, sin
   importar `evaluator.py` ni `normativa/` más allá de citar el `concept_id` — mismo aislamiento que `planta.py`.
2. El hecho cita `referencia_normativa = "es.cte.db_si.anejo_a.altura_de_evacuacion"`.
3. Declaración directa presente (en cualquiera de los dos flujos) → `KNOWN`, confianza Alta, prevalece sobre cualquier hipótesis
   calculable.
4. `/api/generar` sin declaración, con `plantas` y `altura_libre_m` presentes → `ESTIMATED`, confianza **Baja** (no Media),
   `procedencia` con prefijo `"HIPOTESIS:"`, `diagnostico` con los dos factores brutos.
5. `/api/analizar` sin declaración → `UNKNOWN` siempre, sin excepción — ningún camino de código produce una hipótesis en ese flujo.
6. Ningún test ni código de producción calcula una "altura de evacuación real" (derivada, `KNOWN` sin declaración) — no existe
   porque no puede existir con los datos de hoy (§4bis); es una prohibición de diseño, igual que CAP-4 con la inferencia geométrica.
7. `analyzer/avisos_altura_evacuacion.py` existe y expone tres funciones (`C11`, `C15`, `C18`), cada una devuelve un mensaje o
   `None`, **nunca** un objeto con `passed`. Ninguna de las tres se registra en `classify_problems`. `evaluator.py` no se modifica.
8. Un hecho `UNKNOWN` no produce ningún aviso de las tres funciones — test explícito para cada una.
9. Los tres avisos usan `>=` en su umbral respectivo (14, 28, 9 m) y lo declaran en su propio texto/cita.
10. `ejemplo.dxf` (única muestra real, no declara ninguna altura) produce `altura_evacuacion = UNKNOWN` y cero avisos — regresión
    explícita, mismo espíritu que el criterio 14 de CAP-4 sobre `C01`.
11. El payload de ambos endpoints expone `proyecto.altura_evacuacion` y `proyecto.avisos_evacuacion` con la forma descrita en §7.

## 9. Riesgos

| Riesgo | Comentario |
|---|---|
| **La hipótesis se lee como un hecho pese a las etiquetas** | Es el riesgo #3 de `DB-SI_IMPLEMENTATION_PLAN.md` §14, el más citado de todo el plan para CAP-5. Mitigación: confianza Baja (no Media), prefijo `"HIPOTESIS:"` en `procedencia`, y el propio texto del aviso debe repetir "estimado", no sólo el JSON interno — un arquitecto que sólo lee el informe, no el JSON, también tiene que verlo |
| **Valor casi nulo para la única muestra real** | Igual que CAP-4: `ejemplo.dxf` no declara nada, así que sale `UNKNOWN` sin avisos. Hay que decirlo antes de aprobar |
| **Ningún consumidor con veredicto** | A diferencia de CAP-4 (que cerró con `C01` parcial), CAP-5 no activa ninguna regla `PASS`/`FAIL`/`UNKNOWN` normativa nueva — sólo tres avisos informativos. Es una diferencia de naturaleza frente al precedente inmediato, y se dice explícitamente en §14 |
| **Fórmula de hipótesis con convención de "plantas" sin resolver (P5.1)** | Bloqueante parcial: la implementación no puede fijar la fórmula exacta hasta resolver si `edificio.plantas` incluye la planta baja. Ver §14/pendientes |
| **Compite por el mismo desarrollador con B1/B2/B3** | Igual que CAP-4: el árbol de trabajo tiene iniciativas abiertas sin cerrar (motor normativa territorial, fix de scoring, experimento de grafo). CAP-5 es una cuarta rama de trabajo más, no una continuación de ninguna de las tres |
| **Tentación de vincular `C18` a `evaluate_retranqueos` (R25)** | `DB-SI_REVIEW.md` lo prohíbe explícitamente para la ficha `C18`: un retranqueo insuficiente no es lo mismo que un espacio de maniobra de bomberos insuficiente. El aviso de `C18` en este PRD sólo depende de `altura_evacuacion`, nunca de R25 |
| **Umbral `>=` sin cita normativa verificada de "estrictamente mayor"** | Riesgo menor, documentado en §6. Si en el futuro se ingiere el Anejo SI A con precisión suficiente para resolver la ambigüedad, corregir entonces; no bloquea este PRD |

## 10. Impacto sobre módulos existentes

| Módulo | Cambio |
|---|---|
| `analyzer/altura_evacuacion.py` | **Nuevo.** Hecho `altura_evacuacion`, mismo patrón que `planta.py`. Sin dependencias de `evaluator.py` |
| `analyzer/avisos_altura_evacuacion.py` | **Nuevo.** Tres funciones de aviso condicional (`C11`, `C15`, `C18`), consumen el `Hecho` anterior, nunca producen `Result` con `passed`. Sin dependencias de `evaluator.py` |
| `analyzer/hechos.py` | Sin cambios — se reutiliza tal cual (§4quinquies) |
| `analyzer/planta.py` | Sin cambios de código. Se referencia `sobre_rasante` sólo como filtro (§4quater), no se modifica su contrato |
| `app.py` | Nuevo campo de formulario en `/api/analizar`; nuevo campo opcional en el JSON de `/api/generar`; construcción del hecho en ambos flujos; llamada a las tres funciones de aviso; nuevos bloques `proyecto.altura_evacuacion`/`proyecto.avisos_evacuacion` en el payload de ambos endpoints |
| `analyzer/evaluator.py` | **Sin cambios.** No se toca `get_missing_data_warnings`, ni `MIN_STAIR_WIDTH_M`, ni ningún otro punto |
| `analyzer/ocupacion.py`, `analyzer/sectorizacion.py` | **Ninguno.** CAP-5 no depende de `ocupacion`/`C01` ni al revés |
| `tests/test_altura_evacuacion.py` | **Nuevo** |
| `tests/test_avisos_altura_evacuacion.py` | **Nuevo** |
| B1/B2/B3 (`normativa/`, `extraccion/`, resto de `evaluator.py`, `experimentos/`) | **Ninguno**, igual que CAP-4 |

## 11. Plan de implementación dividido en pequeñas tareas

Mismo formato que CAP-4/`REFACTOR_MASTERPLAN.md`, tareas de máximo 2 horas. **Todas después de resolver P5.1** (tarea 0).

0. **Resolver P5.1** (fuera de este PRD en sentido estricto — es un prerrequisito, no una tarea de CAP-5). Sin esto, las tareas 3 y
   6 no se pueden escribir con la fórmula correcta.
1. **`analyzer/altura_evacuacion.py` — el hecho, fuente declarada.** Función `altura_evacuacion(ambito, *, valor_m, origen, ...)` →
   `Hecho`, `KNOWN` si `valor_m` es un número positivo con `origen="declarado"`, `UNKNOWN` si no hay valor.
2. **Normalizador de la declaración del formulario.** Función pura texto/número → `float` positivo o `None`, mismo patrón que
   `normalizar_declaracion_planta`.
3. **Rama `ESTIMATED` — la hipótesis.** Requiere P5.1 resuelto. Construye el hecho a partir de `plantas`/`altura_libre_m`,
   confianza Baja, `procedencia` con prefijo `"HIPOTESIS:"`.
4. **`analyzer/avisos_altura_evacuacion.py` — las tres funciones.** `C11(hecho) -> Optional[str]`, `C15(...)`, `C18(...)`, cada una
   con su umbral, su cita y su verificación de que el hecho no es `UNKNOWN`.
5. **`app.py` — flujo `/api/analizar`.** Campo de formulario, normalizador, construcción del hecho, llamada a los tres avisos.
6. **`app.py` — flujo `/api/generar`.** Campo opcional en el JSON de entrada; si ausente, hipótesis a partir de
   `edificio.plantas`/`altura_libre_m` (requiere tarea 3); llamada a los tres avisos.
7. **Payload `proyecto.altura_evacuacion` / `proyecto.avisos_evacuacion`.** Serialización en ambos flujos, mismo estilo que
   `proyecto.planta`.
8. **Test de prohibición de cálculo `KNOWN` derivado.** Ningún camino de código debe producir `KNOWN` sin `origen="declarado"`.
9. **Tests de los tres avisos**, umbral exacto, `UNKNOWN` no dispara nada, mensaje distinto para `KNOWN` vs. `ESTIMATED`.
10. **Test de regresión `ejemplo.dxf`.** `altura_evacuacion = UNKNOWN`, cero avisos.

## 12. Plan de pruebas

- `tests/test_altura_evacuacion.py`: estados `KNOWN`/`ESTIMATED`/`UNKNOWN`, las dos fuentes, prevalencia de la declaración sobre la
  hipótesis (CU7), combinaciones parciales de §4quater, valores no admisibles (0, negativo, texto no numérico).
- `tests/test_avisos_altura_evacuacion.py`: umbral exacto (`>=`) para cada uno de los tres avisos, `UNKNOWN` no dispara nada,
  coexistencia de los tres a la vez (CU5/CU6), texto distinto para `KNOWN` vs. `ESTIMATED`, verificación de que ninguno produce un
  objeto con `passed` ni entra en `classify_problems`.
- `tests/test_planta.py`, `tests/test_ocupacion.py`, `tests/test_sectorizacion.py`: sin cambios — regresión de que CAP-4 no se
  altera.
- Suite completa debe seguir en verde, sin tocar B1/B2/B3, igual criterio que CAP-4 §12.

## 13. Métricas para medir el éxito

- **% de proyectos con `altura_evacuacion` `KNOWN` o `ESTIMATED`** — métrica de adopción, se espera baja al principio en
  `/api/analizar` (campo nuevo, opcional) y más alta en `/api/generar` (la hipótesis se calcula sola si hay plantas/altura libre).
- **Nº de avisos de `C11`/`C15`/`C18` mostrados**, desglosado por si vienen de un valor `KNOWN` o `ESTIMATED` — si casi todos vienen
  de `ESTIMATED`, es una señal de que pocos arquitectos declaran la altura directamente, información útil para decidir si vale la
  pena insistir en el campo o priorizar `CAP-6` en su lugar.
- **No hay métrica de "aciertos"**: a diferencia de `C01` (CAP-4), que sí puede marcar un `FAIL` verificable, los avisos de CAP-5 no
  tienen un resultado "correcto" medible sin una fuente externa — es coherente con que no es una regla, es un aviso.

## 14. Posibles motivos para NO implementar la idea

Cuatro argumentos honestos.

**1. No cierra ninguna regla con veredicto — a diferencia de CAP-4.** El objetivo de negocio de CAP-4 incluyó, por decisión expresa
de Pablo, un criterio de cierre obligatorio (`C01` parcial, `FAIL`/`UNKNOWN` real). CAP-5, tal como está definida en
`DB-SI_IMPLEMENTATION_PLAN.md` §6, **no tiene una regla equivalente que activar** — su techo son tres avisos informativos. Si el
criterio que hizo aprobar CAP-4 (una capacidad normativa real, no sólo mejor explicada) se aplica igual aquí, **CAP-5 no lo alcanza
por diseño**, no por implementación incompleta. Ésta es la diferencia más importante que hay que decidir antes de aprobar.

**2. El valor depende de que el arquitecto rellene un campo que no tiene ninguna otra utilidad hoy.** A diferencia de `plantas`/
`altura_libre_m` en `/api/generar` (que ya existen porque el visor 3D los necesita), el campo nuevo de "altura de evacuación
declarada" no sirve a ningún otro propósito del producto. El riesgo de "formulario nuevo que casi nadie rellena" (ya señalado en
CAP-4 §9) es más agudo aquí, porque no hay una razón secundaria para rellenarlo.

**3. La alternativa más barata — no implementar CAP-5 todavía, y esperar a `CAP-6`** — es defendible. Sin `CAP-6` (núcleo, salidas,
origen de evacuación), ArchMuse nunca podrá calcular una altura de evacuación real ni la comprobación completa de `C09`/`C10`/`C11`/
`C15` que de verdad movería la aguja. CAP-5 en solitario mejora tres avisos informativos; `CAP-6`, cuando sea viable (bloqueado por
el hallazgo §1.1, no por falta de plan), desbloquearía regla real. Podría argumentarse que el esfuerzo de CAP-5 se invierte mejor
investigando la muestra de DXF reales que `DB-SI_IMPLEMENTATION_PLAN.md` §12 (Bloque D) pide antes de tocar `CAP-6`/`CAP-7`.

**4. Compite por el mismo desarrollador con tres iniciativas ya abiertas y sin cerrar** (B1 motor normativa territorial, B2 fix de
scoring/severidad, B3 experimento de grafo). Igual que CAP-4, sigue en pie.

### Recomendación

**No forzar una recomendación positiva por inercia, como pide la plantilla.** El caso a favor es real (dos documentos de auditoría
independientes lo recomiendan) pero es más débil que el de CAP-4: no hay ningún veredicto normativo nuevo detrás, sólo tres avisos.
Antes de aprobar, conviene que Pablo decida explícitamente entre dos caminos, porque cambian el alcance de este mismo PRD:

- **(a) Aprobar CAP-5 tal como está descrita** — el hecho declarado/estimado más los tres avisos, sin ninguna regla con veredicto,
  aceptando que su valor es menor que el de CAP-4.
- **(b) Reducir el alcance a sólo la declaración directa** (eliminar la rama `ESTIMATED`/hipótesis por completo, no sólo marcarla
  como débil) — más barato, cero riesgo de que una estimación con sesgo conocido se lea como dato real, pero también con adopción
  probablemente más baja todavía, porque en `/api/generar` ya no habría ningún aviso "gratis" a partir de los datos que el
  arquitecto ya introduce.

Este PRD está redactado para la opción (a), por ser la que `DB-SI_IMPLEMENTATION_PLAN.md` recomienda explícitamente, pero la opción
(b) es una alternativa legítima que conviene que Pablo descarte o elija con conocimiento, no por defecto.

---

## Decisión arquitectónica vs. orden de implementación vs. dependencias

**Decisión arquitectónica — la hipótesis usa el eje `confianza`, no un estado nuevo.** Ver §4quinquies. Coste marginal: cero campos
nuevos en `Hecho`. Beneficio: `CAP-5` no reabre `hechos.py`, igual que CAP-4 no lo reabrió.

**Orden de implementación — después de CAP-4, con su propio commit.** CAP-5 depende de CAP-4 sólo para el filtro `sobre_rasante`
(§4quater), una dependencia débil — no para el número de planta en sí (`altura_evacuacion` es de ámbito edificio, no de planta).

**Dependencias — asimétricas:**

- **CAP-5 depende de CAP-4 débilmente** (sólo el booleano `sobre_rasante`, no el número). Podría implementarse sin CAP-4, con un
  coste: la hipótesis incluiría plantas bajo rasante en el cómputo sin poder excluirlas. No es el caso: CAP-4 ya está cerrado.
- **CAP-5 no depende de CAP-3 ni de `sectorizacion.py` (`C01`).** Son ramas independientes del mismo Bloque C/A.
- **`CAP-6` no depende de CAP-5.** Su bloqueo es el hallazgo §1.1, igual que ya fijó el PRD de CAP-4. Aprobar o posponer CAP-5 no
  adelanta ni retrasa CAP-6.
- **Cuando `CAP-6` exista, `altura_evacuacion` ganará una tercera fuente (`KNOWN` derivada de origen de evacuación + salida de
  edificio + cota real)**, sin que este PRD necesite reabrirse: el `concept_id` y el contrato del `Hecho` ya están preparados para
  ese momento — mismo razonamiento de "diseñar conociendo la siguiente capacidad" que ya aplicó CAP-4 con `sobre_rasante`.

---

## Decisiones pendientes — no resueltas por este PRD, marcadas explícitamente

**P5.1 — Convención de "plantas" para la fórmula de la hipótesis. Bloqueante para las tareas 3 y 6 de §11.** `edificio.plantas` en
`/api/generar` tiene una ambigüedad de convención ya documentada por CAP-4 como deuda conocida (`docs/prd/2026-08-09-cap4-modelo-de-
planta.md`, sección final): el urbanismo existente (`compute_floor_areas`, `floor_areas.get(1, ...)`) trata la planta "1" como
planta baja, mientras que el hecho `planta` de CAP-4 usa `sobre_rasante = numero > 0` (planta 0 = planta baja, no sobre rasante). La
fórmula de CAP-5 (`plantas × altura_libre_m` vs. `(plantas - 1) × altura_libre_m`, según si `plantas` cuenta o no la planta baja)
depende de resolver esta ambigüedad primero. **No se elige una de las dos por comodidad** — requiere decidir la convención real de
`edificio.plantas` en `ai_generator`, fuera del alcance de este PRD tal como CAP-4 ya lo dejó fuera del suyo.

**P5.2 — Nombre y forma exacta del campo de declaración directa.** Se propone `altura_evacuacion_m` (numérico, metros) como campo
en `edificio` (`/api/generar`) y como campo de formulario homónimo en `/api/analizar`. Es una propuesta razonable por simetría con
`altura_libre_m`, no una decisión cerrada — ajustable en revisión sin afectar al resto del PRD.

**P5.3 — ¿El aviso condicional debe aparecer también en `/api/analizar` cuando el arquitecto declara la altura directamente?**
`DB-SI_REVIEW.md` sólo menciona explícitamente el aviso condicional "en `/api/generar`" en las fichas `C11`/`C15`, porque hoy sólo
ahí existe una fuente de altura (la hipótesis). Este PRD **propone** extenderlo también a `/api/analizar` cuando hay declaración
directa (§4, §7), por simetría y porque un valor `KNOWN` es al menos tan fiable como uno `ESTIMATED` — pero es una extensión de lo
que el material de origen dice literalmente, no una repetición de él, y se señala así para que Pablo la confirme o la descarte en la
aprobación.

**P5.4 — Plantas de "ocupación nula" en la parte alta del edificio, que el Anejo SI A excluye del cómputo de altura de evacuación
(§4bis).** ArchMuse no tiene ese dato (depende de una taxonomía de locales no habitables que ni CAP-2 ni CAP-3 producen). Este PRD
**no intenta aproximarlo** — se limita a advertir de la limitación en la explicación del hecho `ESTIMATED`, sin ningún intento de
descontarlo numéricamente. No se ha encontrado ninguna base en la arquitectura existente para estimarlo sin inventar un dato.

**P5.5 (la más importante, ver §14 "Recomendación") — ¿Se aprueba CAP-5 con la rama `ESTIMATED` incluida (opción a), o reducida a
sólo declaración directa (opción b)?** No es una decisión técnica: es una decisión de producto sobre cuánto vale un aviso basado en
una hipótesis con sesgo conocido frente al riesgo de que se lea como más fiable de lo que es. Este PRD no la da por resuelta.

---

## Registro de implementación (2026-08-10) — decisiones tomadas y qué sigue abierto

**P5.1 — RESUELTA, con evidencia, no por comodidad.** `edificio.plantas` **incluye la planta baja**, y por tanto la fórmula es
**`(plantas - 1) × altura_libre_m`**. Tres pruebas concurrentes en el propio código, todas en el mismo endpoint:

- `ai_generator._build_user_message` calcula `plantas_residenciales = edificio["plantas"] - (1 if planta_baja_comercial)` — resta
  *del total* la planta baja, luego el total la contenía.
- El prompt de `ai_generator` numera las plantas desde `"planta": 1`.
- `evaluator.compute_floor_areas` + `app.py` leen `floor_areas.get(1, 0.0)` literalmente como `superficie_planta_baja`.

Con la planta 1 a cota de rasante, el origen de evacuación más alto (planta N) queda a `(N-1)` alturas libres sobre la salida de
edificio. Un edificio de 1 planta da 0,00 m, que es el valor correcto, no una ausencia. **Efecto sobre los casos de uso del PRD:**
CU4 (3 plantas) pasa de ≈8,4 m a **5,60 m**; CU5 (6 plantas) da **14,00 m exactos** — cruza el umbral de `C11` justo en el punto,
que con `>=` sí dispara.

**Hallazgo colateral, no corregido (fuera de alcance):** la SPA rotula ese campo como **«Plantas sobre rasante»**
(`static/app.js`), lo que contradice la semántica real del pipeline (donde la planta 1 es la baja). Es la misma familia de deuda de
numeración que CAP-4 dejó registrada; corregirla exige tocar `evaluator.py`/`ai_generator.py`/la SPA. Queda anotado aquí y en el
comentario de `app.py` junto al cableado de `/api/generar`.

**P5.3 — implementada la extensión propuesta**: la declaración directa se admite también en `/api/analizar`, y allí dispara los
avisos igual que en `/api/generar`. Sigue siendo una extensión de lo que `DB-SI_REVIEW.md` dice literalmente; confirmar o descartar
en revisión.

**P5.4 — sin cambios**: no se aproxima el descuento de plantas de ocupación nula. Se advierte, en el propio texto del hecho y de los
tres avisos, que la hipótesis puede sobreestimar por ese motivo.

**P5.5 — implementada la opción (a)** (con rama `ESTIMATED`), por instrucción de continuar el desarrollo. La rama es un bloque
aislado (`estimar_por_plantas` + una condición en `resolver_altura_evacuacion`): pasar a la opción (b) es borrar esas dos piezas,
sin tocar nada más. **La decisión de producto sigue abierta.**

**Desviación consciente del criterio de aceptación 7.** Las tres funciones de aviso devuelven un `AvisoAltura` (dataclass congelada:
`codigo`, `regla`, `titulo`, `localizador`, `umbral_m`, `altura_m`, `altura_estimada`, `mensaje`) en vez de un `str` pelado. El
motivo es §7 del propio PRD, que exige que cada aviso muestre su cita DB-SI: con un `str`, `app.py` tendría que reconstruir las tres
citas por su cuenta, duplicándolas fuera del módulo que las conoce. Se mantiene íntegro lo que el criterio protegía —**sin `passed`,
sin severidad, sin veredicto**— y hay un test por AST que lo comprueba, además de verificar que el módulo no importa `evaluator`,
no usa `IssueReport`/`classify_problems` y no toca `evaluate_retranqueos` (R25).

**Umbral `>=` en los tres, con el matiz normativo anotado en el código**: el literal es estricto en los tres casos (`C11` admite no
protegida *con h ≤ 14 m*; `C15` aplica *superior a 28 m*; `C18` exige maniobra *cuando h > 9 m*), así que en el punto exacto del
umbral se avisa un caso antes de lo que la norma exigiría. Es la dirección segura y sólo es admisible porque **no hay veredicto
detrás**: un `>=` aquí no puede producir un `FAIL` falso.

**Pendiente, fuera de esta entrega: el campo en la interfaz.** `static/app.js` no envía `altura_evacuacion_m` (igual que tampoco
envía el `planta` de CAP-4, que `app.py` lee desde 8bd8f94 sin que la SPA lo ofrezca). El backend y el contrato JSON están
completos y probados; el formulario de §7 es un paso de UI aparte, para no arrastrar cambios de SPA dentro de un PRD de motor.

**Estado de `C11`/`C15`/`C18`: siguen en `UNKNOWN`, sin cambios**, como fijaba el alcance. `evaluator.py` no se ha modificado.

**Ficheros:** `analyzer/altura_evacuacion.py` (nuevo), `analyzer/avisos_altura_evacuacion.py` (nuevo), `app.py` (cableado en ambos
endpoints + dos serializadores), `tests/test_altura_evacuacion.py` (88), `tests/test_avisos_altura_evacuacion.py` (68),
`tests/test_endpoints_altura_evacuacion.py` (62, incluida la regresión de `ejemplo.dxf`). Suite completa en verde salvo
`tests/test_scoring_coherencia.py`, que ya fallaba antes de CAP-5 (marcador de la decisión pendiente sobre los dos sistemas de
puntuación, `docs/design/2026-08-02-dos-sistemas-de-puntuacion.md`) — verificado con `git stash`.

---

## Cierre — decisiones tomadas por Pablo (2026-08-10)

Las cinco decisiones pendientes quedan resueltas así, y el PRD se cierra con ellas:

| Pendiente | Decisión |
|---|---|
| **P5.5** — ¿opción (a) con rama `ESTIMATED`, u (b) sólo declaración? | **(a).** Se mantiene la rama `ESTIMATED` |
| **P5.3** — ¿aviso también en `/api/analizar` con declaración directa? | **Sí.** Se mantiene la declaración directa en los dos flujos |
| **P5.1** — convención de `plantas` para la fórmula | **`(plantas - 1) × altura_libre_m`**, con la evidencia registrada arriba |
| Etiqueta «Plantas sobre rasante» de la SPA | **No se toca ahora.** Queda como deuda técnica documentada (aquí y en `app.py`) |
| Forma del aviso (`AvisoAltura` vs. `str`) | **Se mantiene la dataclass**, para transportar la evidencia normativa (localizador + código + umbral) |
| UI del campo de declaración | **Fuera de este CAP.** Backend + contrato JSON se consideran suficientes por ahora |

**P5.4** (plantas de ocupación nula) se mantiene tal cual: no se aproxima, sólo se advierte — sigue siendo una limitación real, no una
decisión pendiente.

---

**Decisión:** **Aprobado y cerrado por Pablo (2026-08-10).** Implementado y commiteado en la misma fecha.
