# NORMATIVE_ENGINE.md — Base normativa versionada

**Fecha:** 2026-08-05 · **Estado:** diseño, sin implementar · **Alcance territorial del diseño:** CTE (estatal) + Madrid, Barcelona, Valencia y Bilbao (y, por tanto, cuatro comunidades autónomas distintas).

**Qué es este documento:** el diseño del *corpus* normativo — de dónde sale una regla, cómo se versiona, cómo se sabe qué regía en una fecha dada y qué norma prevalece sobre cuál.

**Qué NO es:** un rediseño del motor de evaluación. `docs/brain/CONSTRAINT_MODEL.md` ya definió cómo se evalúa una restricción (5 patrones cerrados, vocabulario cerrado de comparadores, tablas de parámetros por contexto). Este documento **no toca nada de eso** y reutiliza su vocabulario sin ampliarlo. Añade la capa que aquel documento dejó fuera: el ciclo de vida de la norma como objeto legal.

**Relación con la auditoría:** `docs/audits/NORMATIVE_AUDIT.md` (2026-08-05) encontró 0 reglas con referencia a artículo, 5 citas de DB discrepantes, 41 umbrales sin eje de contexto y ningún eje de comunidad autónoma. Este diseño es la estructura donde esos defectos dejan de ser posibles por construcción.

---

## 1. Dónde este diseño se aparta de `CONSTRAINT_MODEL.md` §13, y por qué

`CONSTRAINT_MODEL.md` §13 resuelve el caso territorial español así:

> *"es, simplemente, dos Constraints con el mismo Fact de entrada y comparador, condiciones de activación mutuamente excluyentes por comunidad autónoma, y normativa asociada distinta cada uno […] el modelo no necesita crecer para cubrir este caso."*

**Para evaluar, eso es correcto y se mantiene íntegro.** Dos Constraints con condiciones excluyentes es, en efecto, todo lo que el Intérprete necesita.

Pero esa formulación deja cuatro preguntas sin respuesta, y las cuatro son de producto, no de motor:

1. **¿Cuál prevalece cuando las condiciones *no* son excluyentes?** Un umbral estatal y uno autonómico sobre la misma materia pueden aplicar los dos a la vez. Declararlos excluyentes a mano es, precisamente, incrustar la jerarquía normativa en cada par de registros en lugar de modelarla una vez.
2. **¿Qué regía en la fecha en que se solicitó la licencia?** Un Constraint con "vigencia de la norma" (§8) sabe si está vigente *hoy*. No sabe reconstruir el conjunto aplicable a una fecha pasada, que es la única pregunta legalmente relevante.
3. **¿Qué pasó cuando una norma derogó a otra?** §8 tiene un rango de fechas, no una relación entre normas. Sin esa arista no se puede explicar *por qué* una regla dejó de aplicar.
4. **¿Quién mantiene esto y con qué garantía?** 5 fuentes territoriales que cambian a ritmos distintos no son un detalle de operación: determinan si el producto puede afirmar cumplimiento con honestidad.

Este documento responde a esas cuatro y **no modifica ninguna decisión de `CONSTRAINT_MODEL.md`**. La frontera es limpia: aquel documento dice *cómo se evalúa una restricción*; éste dice *de dónde viene, desde cuándo, hasta cuándo y con qué autoridad*.

---

## 2. La decisión estructural: dos entidades, no una

Los 12 campos del encargo mezclan dos objetos con ciclos de vida incompatibles:

- **La norma es un hecho externo.** La escribe un legislador, se publica en un boletín, entra en vigor y se deroga. No la controlamos. Cambia cuando cambia.
- **La regla es nuestra interpretación.** La escribe un curador, se revisa, se corrige. La controlamos por completo. Puede cambiar sin que la norma haya cambiado — y debe poder hacerlo.

Meterlas en un solo registro con un solo contador de versión hace imposible responder a la pregunta que formula cualquier reclamación de responsabilidad profesional: **¿cambió la ley, o cambiamos nosotros de opinión?**

Por eso el modelo tiene dos entidades:

| | **NormaFuente** | **ReglaNormativa** |
|---|---|---|
| Qué es | El texto legal citable | Su traducción a algo evaluable |
| Quién la versiona | El legislador | El Curador de Conocimiento |
| Qué provoca una versión nueva | Modificación o derogación oficial | Corrección de transcripción, afinado de condiciones, cambio de interpretación |
| Cardinalidad | 1 | N (una norma da varias reglas evaluables) |
| Puede existir sin la otra | Sí (norma no traducida aún) | **No** — invariante heredado de `CONSTRAINT_MODEL.md` §8 |

Una `ReglaNormativa` es lo que se convierte en Constraint. Una `NormaFuente` nunca se evalúa: se cita.

### 2.1 Mapa de los 12 campos del encargo

| Campo pedido | Vive en | Nota de diseño |
|---|---|---|
| `id` | Ambas | Dos ids en cada una: `concept_id` estable de por vida + `instance_id` por versión (§5.1) |
| `fuente` | NormaFuente | Estructurada, no texto libre (§3.1) |
| `artículo` | NormaFuente | Localizador jerárquico, no string (§3.2) |
| `versión` | **Ambas, independientes** | Ésta es la decisión de §2 |
| `fecha de vigencia` | **Ambas, independientes** | Bitemporal (§4) |
| `municipio` | NormaFuente | Derivado del ámbito territorial, no campo libre (§3.3) |
| `comunidad` | NormaFuente | Ídem |
| `tipo` | ReglaNormativa | Catálogo cerrado de 7 (§6) |
| `prioridad` | ReglaNormativa | Reutiliza la escala existente, no una nueva (§7) |
| `texto` | NormaFuente | Literal transcrito + resumen operativo, separados (§3.4) |
| `condiciones` | ReglaNormativa | **Reutiliza `CONSTRAINT_MODEL.md` §3.1/§3.2/§4 sin ampliar** (§8) |
| `referencias` | Grafo entre ambas | Aristas tipadas, no lista de strings (§9) |

---

## 3. NormaFuente

### 3.1 `fuente` — estructurada

| Subcampo | Contenido | Ejemplo |
|---|---|---|
| `rango` | Ley / RD / Decreto / Orden / Ordenanza / Plan / Documento técnico | Real Decreto |
| `organismo` | Emisor | Ministerio de Vivienda |
| `identificador_oficial` | Número y año | 314/2006 |
| `titulo` | Título oficial completo | Código Técnico de la Edificación |
| `boletin` | BOE / BOCM / DOGC / DOGV / BOPV + fecha + número | BOE-A-2006-5515 |
| `url_oficial` | Enlace a la versión consolidada | — |
| `hash_texto` | Hash del literal transcrito | Detecta deriva silenciosa |

`identificador_oficial` + `boletin` son lo que convierte una cita en verificable. La auditoría encontró que hoy el campo `codigo` contiene etiquetas de agrupación (`HABITABILIDAD`, `EFICIENCIA`) presentadas como códigos normativos. Aquí eso es estructuralmente imposible: sin boletín no hay NormaFuente, y sin NormaFuente no hay ReglaNormativa activable.

### 3.2 `artículo` — localizador jerárquico

Un string como `"CTE DB-SUA-1"` no permite ni ordenar, ni comparar, ni detectar que dos reglas citan el mismo apartado. El localizador es una ruta:

```
documento_basico: "DB-SUA"
seccion:          "SUA 9"
apartado:         "1"
punto:            "2"
tabla:            null
```

Con este campo, las cinco discrepancias M1-M5 de la auditoría son detectables mecánicamente: un validador puede comprobar que la materia declarada por la regla pertenece al ámbito del documento básico citado. Hoy nada impide emitir `CTE-DB-HE` (Ahorro de energía) para una regla de superficie mínima de vivienda; con `documento_basico` como valor de catálogo y una tabla materia↔DB, esa combinación no pasa la validación de carga.

### 3.3 `municipio` y `comunidad` — derivados del ámbito territorial

No son campos libres. Son la proyección de un único campo `ambito_territorial`:

| Nivel | `comunidad` | `municipio` | Fuentes en el alcance de este diseño |
|---|---|---|---|
| **Estatal** | `*` | `*` | CTE (DB-SI, SUA, HS, HE, HR, SE), LOE, RD 173/2010 (accesibilidad), Orden VIV/561/2010 |
| **Autonómico** | 1 valor | `*` | Habitabilidad y diseño de vivienda de cada una de las 4 CCAA |
| **Municipal** | 1 valor | 1 valor | Ordenanzas y planeamiento general de las 4 ciudades |
| **Sectorial** | según | según | Patrimonio, protección civil, incendios autonómica |

**El alcance del encargo cubre cuatro comunidades distintas, que es exactamente el punto:**

| Ciudad | Comunidad | Capa autonómica | Capa municipal |
|---|---|---|---|
| Madrid | Comunidad de Madrid | Normativa autonómica de habitabilidad y diseño | Ordenanza municipal de edificación + planeamiento general |
| Barcelona | Cataluña | Decreto autonómico de habitabilidad | Ordenanzas metropolitanas + planeamiento |
| Valencia | Comunitat Valenciana | Normativa autonómica de diseño y calidad | Ordenanzas municipales + planeamiento |
| Bilbao | País Vasco | Normativa autonómica de vivienda | Ordenanzas municipales + planeamiento |

*(Los identificadores oficiales concretos de cada norma autonómica y municipal se dejan deliberadamente sin citar aquí: son el contenido que el Curador debe transcribir y verificar contra boletín, no algo que un documento de diseño deba fijar de memoria. §12 explica el procedimiento.)*

`municipio`/`comunidad` se resuelven a partir del Fact "ciudad" que el formulario ya recoge (`app.py:154`), por la misma vía de función de composición con la que `CONSTRAINT_MODEL.md` §11 resuelve la zona climática: **una única fuente de verdad, ninguna regla contiene su propio mapeo.**

### 3.4 `texto` — dos campos, nunca uno

| Subcampo | Contenido | Regla |
|---|---|---|
| `literal` | Transcripción exacta del artículo | Inmutable. Cambiarlo es una versión nueva de NormaFuente |
| `resumen_operativo` | Reformulación del Curador, en lenguaje llano | Mutable. Cambiarlo es una versión nueva de ReglaNormativa, no de la norma |

Separarlos es lo que permite mostrar al arquitecto el literal legal junto a la explicación, sin que un cambio de redacción nuestra parezca un cambio de ley. La ficha de incidencia debe poder enseñar los dos.

---

## 4. Tiempo: cuatro ejes, dos almacenados

Es el núcleo del diseño. Confundir estos ejes es el error clásico de toda base normativa.

| Eje | Pregunta que responde | ¿Se almacena? |
|---|---|---|
| **Vigencia legal** | ¿Desde y hasta cuándo estuvo la norma en vigor? | **Sí** |
| **Vigencia de registro** | ¿Qué sabía ArchMuse el día que emitió este informe? | **Sí** |
| **Aplicabilidad al proyecto** | ¿Qué normativa rige *este* proyecto? | **No — se calcula** |
| **Conocimiento** | ¿Cuándo nos enteramos de un cambio publicado antes? | Metadato de gobernanza |

### 4.1 Los dos ejes almacenados (bitemporal)

```
NormaFuente / ReglaNormativa
  vigencia_desde     ← entrada en vigor (dato legal)
  vigencia_hasta     ← derogación (null si sigue vigente)
  registro_desde     ← cuándo entró este registro en nuestra base
  registro_hasta     ← cuándo lo sustituimos (null si es el vigente)
```

Nada se edita ni se borra jamás: se cierra `registro_hasta` y se inserta una fila nueva. Es la disciplina append-only que ya gobierna toda la serie (`FACT_MODEL.md` §7, `REASONING_ENGINE_SPEC.md`).

**Por qué aquí el append-only no es negociable, a diferencia de otros sitios.** `BRAIN_REVIEW.md` señala, con razón, que el versionado append-only universal es una inversión que `PRD-001` decidió no pagar todavía. Esa objeción es válida para `ProjectState`. **No lo es para la base normativa**, por una razón concreta: un informe de ArchMuse es una afirmación sobre el cumplimiento legal de un proyecto en una fecha. Si dentro de tres años alguien cuestiona ese informe, la única defensa posible es reconstruir exactamente qué reglas estaban cargadas y qué decían ese día. Sin el eje de registro, esa reconstrucción es imposible y el informe es indefendible. **Es la diferencia entre una funcionalidad y un seguro.**

### 4.2 El eje calculado: aplicabilidad

La normativa aplicable a un proyecto **no es la vigente hoy**: es la vigente en su fecha de devengo — típicamente la de solicitud de licencia, a veces otra si un régimen transitorio lo desplaza.

```
conjunto_aplicable(municipio, fecha_devengo, contexto) → [ReglaNormativa]
```

Consecuencias de diseño que esto impone:

- **`fecha_devengo` es un dato del proyecto**, no del sistema. Hay que pedirlo. Si no se informa, se asume "hoy" — y esa asunción se marca como Assumption visible, nunca como Fact (`INFERENCE_ENGINE.md`: nunca convertir una suposición en hecho en silencio).
- **Un régimen transitorio es una ReglaNormativa más**, de tipo `procedimental`, cuya condición desplaza la fecha de devengo. No es un caso especial del motor.
- **Reanalizar un proyecto antiguo con normativa nueva es un error**, salvo que se pida explícitamente. Debe ser una acción consciente, no el comportamiento por defecto.

### 4.3 La consulta que justifica comercialmente todo esto

```
diff_normativo(proyecto, fecha_a, fecha_b) → [cambios que le afectan]
```

*"Este proyecto se analizó en enero. Desde entonces han cambiado 3 reglas que le afectan: 2 no alteran el resultado, 1 convierte un hallazgo recomendable en bloqueante."*

Ninguna herramienta puede dar esa respuesta sin un corpus versionado. Es, con diferencia, la capacidad de mayor valor defendible de este diseño: encaja con el argumento de suscripción de `MOAT_ANALYSIS.md` §1 (defensa profesional, no comodidad) y no es replicable sin haber acumulado historial. Conviene diseñar el corpus **desde el principio** con esta consulta como caso de uso de primera clase, porque es imposible añadirla retroactivamente sobre una base que sobrescribe.

---

## 5. Identidad y versión

### 5.1 Dos ids por entidad

Reutiliza sin cambios la separación de `FACT_MODEL.md` §7:

- **`concept_id`** — estable durante toda la vida del concepto. `cte.sua.itinerario_accesible_ancho` sigue siendo el mismo concepto aunque su umbral cambie tres veces.
- **`instance_id`** — una versión concreta. Es lo que cita una Evidence.

Sin esta separación no se puede responder "enséñame la historia de esta regla" sin recorrer todo el histórico, ni mantener estable la identidad de un hallazgo cuando la norma que lo generó se actualiza — el mecanismo de *huella* de `OBSERVATION_MODEL.md` depende de `concept_id`, nunca de `instance_id`.

### 5.2 Namespacing

```
<ambito>.<fuente>.<materia>.<concepto>

cte.db_sua.accesibilidad.itinerario_ancho_minimo
cam.habitabilidad.superficie.vivienda_minima
bcn.ordenanza.urbanismo.ocupacion_maxima
```

El prefijo de ámbito hace visible el nivel territorial en el propio id, que es lo que permite detectar de un vistazo que dos reglas compiten por la misma materia en niveles distintos.

### 5.3 Qué cuenta como versión nueva

| Cambio | Nueva versión de |
|---|---|
| Se publica una modificación oficial del artículo | NormaFuente **y** ReglaNormativa |
| Se deroga la norma | NormaFuente (cierra vigencia); ReglaNormativa hereda el cierre |
| Corregimos una errata de transcripción | **NormaFuente** (cambia el literal) |
| Afinamos el árbol de condiciones | ReglaNormativa |
| Cambiamos el resumen operativo o el texto de la solución | ReglaNormativa |
| Reclasificamos la prioridad | ReglaNormativa |
| Corregimos una cita de artículo equivocada | ReglaNormativa (la norma citada estaba mal, la norma no cambió) |

La última fila es exactamente el caso de las 5 discrepancias M1-M5 de la auditoría, y merece registrarse como lo que es: **un error nuestro, no un cambio legislativo.** Que el modelo pueda distinguirlo es parte del argumento de honestidad del producto.

---

## 6. `tipo` — catálogo cerrado de 7

| Tipo | Qué expresa | ¿Evaluable? | Patrón de `CONSTRAINT_MODEL.md` §3.1 |
|---|---|---|---|
| `exigencia_cuantitativa` | Un umbral numérico | Sí | UMBRAL_SIMPLE / UMBRAL_CON_EXCEPCION |
| `exigencia_de_presencia` | Algo debe existir | Sí | PRESENCIA_OBLIGATORIA |
| `exigencia_compuesta` | Varias condiciones a la vez | Sí | COMBINACION_LOGICA / AGREGACION_AMBITO |
| `exigencia_cualitativa` | Requiere juicio humano ("solución equivalente justificada") | **No** | Ninguno — se expone, no se evalúa |
| `definicion` | Define un término usado por otras reglas | **No** | Ninguno — se referencia |
| `remision` | No dice nada propio; remite a otra norma | **No** | Se resuelve siguiendo la arista `remite_a` |
| `procedimental` | Trámite, documentación, régimen transitorio | **No** | Informativa; puede desplazar `fecha_devengo` |

Tres decisiones que merecen justificación:

**`definicion` es un tipo de primera clase.** "Superficie útil", "pieza habitable", "altura libre" están definidos de forma distinta por el CTE, por catastro y por cada decreto autonómico. Buena parte de las discrepancias normativas reales no son de umbral sino de definición. La auditoría lo tocó sin nombrarlo: R03 y R07 calculan "superficie útil" excluyendo terraza y tendedero (`evaluator.py:423`) con un criterio propio, no con la definición de ninguna norma citada. Modelar las definiciones como registros referenciables es lo que permite que un umbral declare **contra qué definición** se mide.

**`exigencia_cualitativa` existe para no fingir.** Cuando una norma dice "salvo justificación de solución equivalente", el sistema no puede resolverlo. Tener un tipo para eso es mejor que forzarlo a un umbral o que omitirlo. Se conecta directamente con la *excepción sujeta a justificación humana* de `CONSTRAINT_MODEL.md` §5, que el Intérprete nunca aplica solo.

**Cuatro de siete tipos no son evaluables, y eso es correcto.** Un corpus normativo honesto contiene mucha norma que un motor geométrico no puede comprobar. Modelarla igualmente sirve para dos cosas: alimentar la lista de "no evaluable" (`get_missing_data_warnings`, hoy la mejor pieza de honestidad del repositorio) y sostener las remisiones entre normas evaluables.

---

## 7. `prioridad` — la escala existente, sin inventar una nueva

`prioridad` reutiliza sin cambios los 4 valores de `DECISION_ENGINE.md` §3: **bloqueante / riesgo variable / recomendable / preferencial**. Nunca un número (`REASONING_ENGINE_SPEC.md` entidad 20).

**Prioridad y jerarquía normativa son ejes distintos y no deben confundirse:**

- **Prioridad** = qué consecuencia tiene incumplir esta regla.
- **Jerarquía normativa** (§10) = qué norma prevalece cuando dos regulan lo mismo.

Una regla municipal puede prevalecer sobre una estatal en su materia y ser, a la vez, de prioridad menor. Fusionar ambos ejes en un solo campo es un error que se paga en cuanto entra la segunda comunidad autónoma.

`prioridad` es un valor declarado de la regla; **la severidad final de un hallazgo puede diferir**, porque el contexto la modula (hoy ya ocurre: `evaluator.py:1987` baja la accesibilidad de baño de CRÍTICO a IMPORTANTE en rehabilitación). Ese ajuste es una condición de la regla, no una edición de su prioridad.

---

## 8. `condiciones` — frontera dura

**El corpus normativo no define ningún lenguaje de condiciones propio.** Reutiliza íntegramente y sin ampliar:

- Los 5 patrones de `CONSTRAINT_MODEL.md` §3.1.
- El vocabulario de comparadores de §3.2.
- El árbol `AND`/`OR`/`NOT` sobre predicados de contexto de §4.
- Las tablas de parámetros multi-eje de §9, con cadena de repliegue explícita y registrada en la Evidence.

`CONSTRAINT_MODEL.md` §14 identifica como riesgo principal la tentación de añadir un sexto patrón bajo presión. Este documento es exactamente el sitio donde esa presión aparecería: llega una ordenanza municipal con una condición rara y resulta cómodo inventar un patrón para ella. **Está prohibido.** Si una norma no se puede expresar con los cinco patrones, la respuesta correcta es una de estas tres, en este orden:

1. Componerla con `COMBINACION_LOGICA` sobre reglas existentes.
2. Mover la aritmética a una función de composición de Fact derivado (`FACT_MODEL.md` §4).
3. Clasificarla como `exigencia_cualitativa` y no evaluarla.

Añadir un patrón es un evento de gobernanza del Curador, nunca la reacción a una norma concreta.

### 8.1 El eje que hoy no existe

La auditoría (§5.3) constató que ninguna regla conoce la comunidad autónoma, pese a que al menos 6 umbrales son competencia autonómica. En este modelo, `comunidad` y `municipio` son ejes de contexto ordinarios — automáticamente disponibles por ser Facts de naturaleza contextual-normativa (`CONSTRAINT_MODEL.md` §12), sin que el motor necesite saber de ellos. Una tabla de parámetros indexa por `comunidad × tipologia × zona_cte` igual que hoy indexa por tipología.

**La cadena de repliegue es obligatoria y auditable.** Si no hay valor para Bilbao, se declara explícitamente el orden (municipio → comunidad → estatal → ninguno) y **cada uso de un nivel de repliegue se escribe en la Evidence**. Un repliegue silencioso al valor estatal en una materia de competencia autonómica es el Bug #1 reencarnado en la capa normativa.

---

## 9. `referencias` — grafo tipado

Una lista de strings no sirve. Las referencias son aristas dirigidas, tipadas y con vigencia propia.

| Tipo de arista | Dirección | Efecto sobre la aplicabilidad |
|---|---|---|
| `deroga` | A → B | Cierra la vigencia de B en la fecha de A |
| `modifica` | A → B | Genera versión nueva de B; la anterior sigue siendo consultable |
| `desarrolla` | A → B | A concreta a B; ambas siguen vigentes |
| `endurece` | A → B | A fija un umbral más exigente en su ámbito territorial |
| `remite_a` | A → B | A no dice nada propio; se evalúa B |
| `exime_de` | A → B | A retira la aplicabilidad de B bajo condición |
| `se_mide_segun` | A → D | A usa la definición D (§6) |
| `corrige_erratum` | A → A′ | Corrección nuestra de transcripción, no cambio legal |

Dos invariantes:

- **El grafo de derogaciones no puede tener ciclos.** Si aparece uno, es un error de transcripción, no una situación legal — debe fallar la carga.
- **Ninguna arista se borra nunca.** Una derogación derogada (ocurre) se representa cerrando la vigencia de la arista, no eliminándola. Es lo que permite explicar por qué una regla volvió a aplicar.

`explicar_inaplicabilidad(regla, fecha)` recorre este grafo y devuelve la cadena causal: *"no aplica desde 2024-03-01 porque la norma X la derogó; X a su vez desarrolla Y, que sigue vigente"*. Es una capacidad que la interfaz debería mostrar y que hoy no tiene forma de existir.

---

## 10. Jerarquía territorial: qué prevalece

Aquí está la corrección conceptual más importante del documento.

**La regla más restrictiva NO gana automáticamente.** La prevalencia se resuelve por **materia y competencia**, no por severidad. Aplicar "gana la más estricta" produce resultados legalmente incorrectos con regularidad.

| Materia | Competencia | Puede la capa inferior… | Ejemplo |
|---|---|---|---|
| Seguridad estructural, incendios, salubridad | **Estatal (CTE)** | …endurecer, nunca relajar | DB-SI, DB-SE |
| Accesibilidad | Estatal (mínimos) + autonómica | …endurecer | RD 173/2010 + normativa autonómica |
| Habitabilidad, superficies mínimas, programa | **Autonómica** | El CTE **no regula** esta materia | Superficies mínimas de vivienda |
| Urbanismo: ocupación, edificabilidad, altura, retranqueos | **Municipal** (marco autonómico) | Sin equivalente estatal | Planeamiento de cada ciudad |
| Patrimonio | Sectorial | Puede eximir de otras | Catalogación |

**Esto corrige directamente el hallazgo M1 de la auditoría.** Hoy la superficie mínima de vivienda emite `CTE-DB-HE`. No es que la cita esté mal escrita: es que **el CTE no regula esa materia en absoluto**. No hay conflicto entre norma estatal y autonómica ahí — hay una única norma competente, la autonómica, y el código está citando una que no tiene nada que decir. Un modelo basado en "gana la más restrictiva" nunca habría detectado esto, porque presupone que las dos regulan lo mismo.

### 10.1 Algoritmo de resolución

```
1. Filtrar por vigencia en fecha_devengo          → conjunto temporal
2. Filtrar por ámbito territorial del proyecto    → conjunto territorial
3. Agrupar por materia
4. Por materia, aplicar la tabla de competencia:
   - competencia exclusiva → solo esa capa
   - mínimo estatal + desarrollo → estatal como suelo, superior si endurece
5. Resolver aristas `endurece` / `exime_de` / `remite_a`
6. Lo que quede en genuino conflicto NO se resuelve aquí:
   se materializa como Conflict (DECISION_ENGINE.md §3)
```

El paso 6 es deliberado. Existen discrepancias reales entre norma autonómica y ordenanza municipal que un motor no debe zanjar en silencio. Se muestran como conflicto abierto, con las dos fuentes citadas, y decide el arquitecto. Es la aplicación directa de `DECISION_ENGINE.md`: el sistema apoya el criterio, no lo sustituye.

### 10.2 El caso que este modelo *no* resuelve: parámetros por parcela

Sinceridad necesaria, porque es la trampa de toda la capa municipal.

Una ordenanza municipal **no dice** "ocupación máxima 60 %". Dice que la ocupación máxima es la que fije la norma zonal aplicable a la parcela, y esa norma zonal se lee en la ficha urbanística de esa parcela concreta. **Los parámetros urbanísticos no son una regla: son un dato por parcela.**

Consecuencia de diseño: la capa municipal se parte en dos.

| Parte | Naturaleza | Dónde vive |
|---|---|---|
| *"La ocupación no puede superar el máximo aplicable"* | ReglaNormativa | Esta base |
| *"El máximo aplicable a esta parcela es 60 %"* | **Fact declarado o integrado** | El proyecto, no el corpus |

Hoy el código ya funciona así por accidente: `evaluate_solar_occupation` (`evaluator.py:2609`) devuelve `None` si el arquitecto no informa `ocupacion_maxima_pct`. Ese comportamiento es **correcto** y debe preservarse: la regla existe siempre, el parámetro viene del proyecto. Cualquier diseño que intente meter los parámetros urbanísticos de 4 ciudades dentro del corpus normativo está mal planteado — es un problema de integración de datos catastrales y de planeamiento, no de autoría de reglas, y es de otro orden de magnitud.

---

## 11. Almacenamiento y formato

**Recomendación: ficheros versionados en git como fuente de verdad; base de datos como índice derivado.**

```
normativa/
  cte/db_sua/sua_09_accesibilidad.yaml
  cte/db_si/si_01_propagacion_interior.yaml
  autonomica/madrid/habitabilidad.yaml
  autonomica/cataluna/habitabilidad.yaml
  autonomica/valenciana/diseno_calidad.yaml
  autonomica/pais_vasco/vivienda.yaml
  municipal/madrid/ordenanza_edificacion.yaml
  municipal/barcelona/ordenanzas.yaml
  municipal/valencia/ordenanzas.yaml
  municipal/bilbao/ordenanzas.yaml
  definiciones/superficie_util.yaml
```

Razones, en orden de peso:

1. **Git ya es una base de datos append-only con revisión.** Historial inmutable, diff legible, autoría, revisión por PR y capacidad de reconstruir cualquier estado pasado — que es literalmente el eje de registro de §4.1. Construir un CMS para conseguir eso sería reimplementar git peor.
2. **El diff de una norma es revisable por un humano.** Un cambio normativo debe leerse antes de entrar. Un PR con el diff del YAML es la mejor herramienta que existe para eso.
3. **El tamaño lo permite.** Estimación honesta para el alcance de este documento: entre 400 y 900 reglas evaluables, más definiciones y procedimentales. Cientos de ficheros, no millones de filas.
4. **Los tests de regresión son triviales.** Un corpus en ficheros se carga en un test y se valida entero en CI.

La base de datos (SQLite, junto a la que ya existe) se genera al arrancar a partir de los ficheros, con índices por `(municipio, materia, vigencia)`. **Es un caché, nunca la fuente de verdad**: se puede borrar y regenerar.

### 11.1 Validaciones obligatorias en carga

Ninguna regla entra en producción sin pasar:

1. Tiene `NormaFuente` con boletín e identificador oficial (invariante de `CONSTRAINT_MODEL.md` §8).
2. El `documento_basico` citado es compatible con la `materia` declarada — **el validador que habría impedido M1-M5**.
3. Su tipo es evaluable ⟹ tiene patrón, comparador y parámetros; no lo es ⟹ no tiene ninguno de los tres.
4. Toda arista apunta a un `concept_id` existente.
5. El grafo de derogaciones es acíclico.
6. Toda regla evaluable declara su nivel de conocimiento (1-4).
7. Ningún parámetro es un escalar desnudo: siempre tabla con cadena de repliegue declarada.
8. `hash_texto` coincide con el literal transcrito.

---

## 12. Gobernanza: quién mantiene esto

Es el riesgo dominante del diseño, igual que en `FACT_MODEL.md` §12.1 y `CONSTRAINT_MODEL.md` §14: no es estructural, es de disciplina sostenida.

| Rol | Responsabilidad |
|---|---|
| **Curador de Conocimiento** | Transcribe del boletín, redacta condiciones, mantiene aristas |
| **Validador técnico** | Arquitecto colegiado que verifica la traducción norma → regla |
| **Vigilante de fuentes** | Detecta publicaciones nuevas en los 5 boletines |

**Regla de dos personas, no negociable:** ninguna regla evaluable entra en producción sin que un arquitecto colegiado haya validado que su condición representa lo que el artículo dice. La auditoría demostró por qué: 5 citas incorrectas escritas de buena fe por alguien sin ese perfil. Es la misma clase de error que volverá a ocurrir si el corpus se puebla sin ese filtro, solo que multiplicada por 900 reglas en vez de 41.

**Cadencia realista de mantenimiento.** El CTE se modifica con poca frecuencia y con aviso; los decretos autonómicos, algo más; las ordenanzas municipales y el planeamiento, de forma irregular y sin ningún canal cómodo. La conclusión honesta es que **la capa municipal es la más cara de mantener y la que más rápido se pudre**, y que el coste no baja con el número de clientes — es un coste fijo por ciudad. Eso tiene una consecuencia estratégica directa: **cada ciudad nueva es un compromiso de mantenimiento permanente, no una funcionalidad que se entrega una vez.** Es un argumento para entrar ciudad a ciudad y de forma deliberada, no para prometer cobertura nacional.

**Fecha de última verificación por fuente**, visible en producto. *"CTE: verificado 2026-08-01. Ordenanza de Bilbao: verificada 2026-02-14."* Un arquitecto que ve esa fecha sabe qué está comprando. Uno que no la ve, no puede confiar — y tiene razón.

---

## 13. Contrato de consulta

Cuatro estados posibles, **nunca silencio** — misma disciplina que `FACT_MODEL.md` §10:

| Estado | Significado |
|---|---|
| `aplica` | La regla rige y es evaluable |
| `no_aplica` | Vigente, pero sus condiciones excluyen este proyecto (con el motivo) |
| `aplica_no_evaluable` | Rige, pero es cualitativa o faltan datos — se informa, no se puntúa |
| `sin_cobertura` | **No tenemos esa materia cargada para este municipio** |

El cuarto estado es el más importante y el que hoy no existe en ninguna forma. Es la diferencia entre *"tu proyecto cumple"* y *"tu proyecto cumple las 340 reglas que tengo cargadas para Bilbao; no tengo cobertura de ordenanza de patrimonio"*. La primera afirmación es insostenible; la segunda es vendible.

---

## 14. Migración desde el estado actual

No es un salto. Es una secuencia en la que cada paso deja el producto en un estado mejor y publicable.

| Fase | Contenido | Resultado observable |
|---|---|---|
| **0** | Esquema, validadores y cargador. Corpus vacío | Nada visible. Infraestructura |
| **1** | Transcribir las 41 reglas actuales a NormaFuente + ReglaNormativa, con su cita real | Las 5 discrepancias M1-M5 mueren en el validador. Primeras citas de artículo del producto |
| **2** | Cablear el Intérprete al corpus; retirar los umbrales del código | Los 41 escalares hardcodeados desaparecen de `evaluator.py` |
| **3** | Añadir el eje `comunidad` y poblar las 4 autonómicas | El mismo plano da resultados distintos en Madrid y Bilbao — que es lo correcto |
| **4** | Capa municipal (reglas, no parámetros de parcela) | Cobertura urbanística real |
| **5** | Consulta `diff_normativo` | La capacidad diferencial de §4.3 |

**La fase 1 es la que más valor entrega por unidad de esfuerzo** y no requiere ninguna de las demás: solo con transcribir lo que ya existe, el producto pasa de "0 reglas citan un artículo" a "todas lo citan", que es exactamente la promesa que `MOAT_ANALYSIS.md` §1 ya está haciendo y que hoy no cumple.

Las fases 0-2 son refactorización de comportamiento existente. Las fases 3-5 son capacidad nueva y requieren PRD previo (`CLAUDE.md`).

---

## 15. Riesgos y qué no resuelve este diseño

| # | Riesgo | Mitigación | Residual |
|---|---|---|---|
| 1 | **Error de transcripción.** Un dígito mal copiado se propaga a cientos de informes | Regla de dos personas, `hash_texto`, tests de regresión | **Alto.** Ninguna estructura de datos protege de esto |
| 2 | **Interpretación de artículo ambiguo.** Muchas normas admiten más de una lectura razonable | Tipo `exigencia_cualitativa`, nivel de conocimiento visible | **Alto.** Es criterio profesional, no un problema técnico |
| 3 | **Deriva de la capa municipal** | Fecha de verificación visible, vigilante de fuentes | **Medio-alto.** Coste fijo por ciudad, permanente |
| 4 | **Parámetros de parcela** (§10.2) | Fuera del corpus por diseño | **Fuera de alcance.** Es integración de datos, no autoría |
| 5 | **Corpus incompleto presentado como completo** | Estado `sin_cobertura`, cobertura declarada por municipio | **Medio.** Depende de que el producto lo enseñe, no de que exista |
| 6 | **Explosión de gobernanza** cuando el corpus crece | Namespacing, catálogo cerrado de patrones, validadores en CI | **Medio.** El riesgo de `CONSTRAINT_MODEL.md` §14, ampliado |
| 7 | **Sobrediseñar antes de tener usuarios** | Fase 1 aporta valor sola | **Real y presente.** Ver abajo |

**Sobre el riesgo 7, con franqueza.** Este documento describe una infraestructura considerable para un producto que todavía no tiene usuarios externos. Ese desequilibrio es real y no lo disimulo. Lo que lo justifica es una asimetría concreta: **las decisiones de identidad y de tiempo (§4, §5) no se pueden añadir después.** Un corpus que sobrescribe no se convierte retroactivamente en uno versionado, y sin versionado no hay ni defensa ante una reclamación ni `diff_normativo`. El resto —capa municipal, cuatro comunidades, grafo completo de referencias— sí puede esperar, y **debería** esperar a que haya un arquitecto de pago que necesite Bilbao.

La lectura correcta de este documento no es "constrúyelo entero". Es: **acierta el esquema y el eje temporal desde la primera regla, y luego puebla el corpus al ritmo que los clientes lo pidan.**

---

## 16. Resumen de decisiones estructurales

1. **Dos entidades, no una.** NormaFuente (hecho externo) y ReglaNormativa (interpretación nuestra), versionadas por separado. Permite responder si cambió la ley o cambiamos nosotros.
2. **Bitemporal obligatorio.** Vigencia legal y vigencia de registro se almacenan; aplicabilidad se calcula desde una `fecha_devengo` que es dato del proyecto.
3. **`concept_id` / `instance_id`**, reutilizando `FACT_MODEL.md` §7 — sin esto no hay historial ni estabilidad de hallazgos.
4. **Cero vocabulario nuevo de condiciones.** Los 5 patrones de `CONSTRAINT_MODEL.md` §3.1 son frontera dura.
5. **La prevalencia se resuelve por materia y competencia, no por severidad.** "Gana la más restrictiva" es incorrecto y no habría detectado M1.
6. **7 tipos de regla, 4 de ellos no evaluables** — incluida `definicion`, de primera clase.
7. **`referencias` es un grafo tipado con vigencia**, no una lista de strings.
8. **Git como fuente de verdad, SQLite como índice derivado.**
9. **Los parámetros urbanísticos por parcela quedan fuera del corpus** — son Facts del proyecto.
10. **`sin_cobertura` es un estado de primera clase.** Es la diferencia entre una afirmación insostenible y una vendible.

---

*Documento de diseño. Ninguna línea de código escrita ni modificada. Los identificadores oficiales de las normas autonómicas y municipales de las cuatro ciudades se dejan expresamente sin fijar: son contenido a transcribir y validar contra boletín por el Curador y el validador técnico (§12), no algo que un documento de arquitectura deba dar por sabido.*
