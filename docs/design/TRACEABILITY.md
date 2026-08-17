# TRACEABILITY.md — Trazabilidad de un resultado de análisis

**Fecha:** 2026-08-05 · **Estado:** diseño, sin implementar
**Objetivo:** que cualquier resultado del análisis pueda responder, sin ambigüedad, a cinco preguntas: qué regla disparó, qué datos del plano usó, qué cálculo hizo, qué artículo aplica y qué evidencia encontró.

---

## 0. Qué añade este documento, y qué no

Esto es lo primero que hay que dejar claro, porque la serie `docs/brain/` ya cubre buena parte del encargo y repetirlo sería peor que no escribirlo.

**Ya está resuelto y este documento lo reutiliza sin tocarlo:**

| Cubierto por | Qué resuelve |
|---|---|
| `EVIDENCE_MODEL.md` §1-§2 | Estructura de un tramo de Evidence y sus 6 tipos cerrados |
| `EVIDENCE_MODEL.md` §4 | Trazabilidad transitiva: todo tramo resuelve en un puntero final |
| `EVIDENCE_MODEL.md` §6-§7 | Puntero geométrico y traza de cálculo como campos de primera clase |
| `EVIDENCE_MODEL.md` §3, §9 | Fuerza por tramo y confianza como mínimo simple |
| `EXPLANATION_ENGINE.md` §3-§6 | Profundidad, 3 niveles de explicación, citas inline |
| `FACT_MODEL.md` §9 | Esquema canónico de puntero de origen |
| `NORMATIVE_ENGINE.md` §3.2 | Localizador jerárquico de artículo |

**Lo que ninguno de ellos resuelve, y es lo que este documento añade:**

1. **La traza como artefacto persistido e inmutable**, no como propiedad recalculable. `EVIDENCE_MODEL.md` describe la Evidence como algo que una Inference *tiene*; no dice qué pasa con ella cuando el informe se entrega y el código cambia (§1).
2. **El contrato de reproducibilidad**: qué hay que anclar para que la misma traza vuelva a salir idéntica, y qué elementos del sistema actual son estructuralmente no reproducibles (§10).
3. **El puntero al DXF como problema de ingeniería real**, no como esquema abstracto: los handles no sobreviven a un re-guardado, y hoy `Room` no guarda ninguno (§5).
4. **Los cuatro desenlaces**, no uno. Hoy solo el incumplimiento deja rastro; "cumple", "no evaluable" y "no considerada" no dejan ninguno, y son tres cuartas partes de lo que hace defendible un informe (§9).
5. **El presupuesto de coste**: cuántos registros genera esto de verdad, medido sobre `ejemplo.dxf` (§11).
6. **La distancia exacta al código actual**, medida, no estimada (§14).

En una frase: la serie `brain/` diseñó **qué es** una traza; este documento diseña **cómo se produce, se guarda, se vuelve a leer tres años después y cuánto cuesta**.

---

## 1. Principio rector: la traza es un artefacto, no un cálculo

**Una traza que se recalcula no es una traza.**

Si dentro de tres años alguien cuestiona un informe y el sistema regenera la explicación con el código y el corpus normativo de ese momento, la respuesta que obtiene no es *por qué ArchMuse dijo aquello*, sino *qué diría ArchMuse hoy*. Son dos preguntas distintas y solo la primera tiene valor probatorio.

De ahí la decisión estructural de todo el documento:

> Cada análisis emitido produce una **Traza de Análisis** completa, inmutable y almacenada junto al resultado. Nunca se regenera. Nunca se edita. Si el código o la normativa cambian, se emite un análisis nuevo con su propia traza; el anterior permanece intacto.

Esto es la aplicación directa del argumento de `NORMATIVE_ENGINE.md` §4.1: el versionado append-only es negociable en casi todo el sistema, y no lo es aquí, porque aquí es donde vive la defensa profesional que `MOAT_ANALYSIS.md` §1 pone como razón principal para pagar una suscripción.

**Corolario incómodo:** la narrativa de IA (`ai_analyst.py`) **no puede formar parte de la traza**. Un modelo generativo no es reproducible ni siquiera con la misma entrada y la misma versión. Debe quedar explícitamente fuera del artefacto trazable, marcada como comentario interpretativo, no como fundamento. Mezclarla con la traza contamina lo único del informe que puede sostenerse. Es una separación que hoy no existe.

---

## 2. Las cinco preguntas y dónde se responde cada una

| Pregunta del encargo | Se responde con | Sección |
|---|---|---|
| ¿Qué regla disparó? | `regla` — concept_id + instance_id de la ReglaNormativa | §4 |
| ¿Qué datos del plano utilizó? | `entradas` — Facts con puntero resuelto al DXF | §5 |
| ¿Qué cálculo hizo? | `derivacion` — cadena de funciones de composición + resolución del parámetro | §6 |
| ¿Qué artículo aplica? | `norma` — localizador jerárquico + literal + vigencia en la fecha de devengo | §7 |
| ¿Qué evidencia encontró? | `evidencia` — tramos de `EVIDENCE_MODEL.md`, con su fuerza | §8 |

Las cinco son campos de un único registro. No están repartidas por el sistema: se escriben juntas en el momento de la evaluación, porque reconstruirlas después es exactamente el fallo del §1.

---

## 3. La unidad de registro: Traza de Evaluación

La unidad no es "el hallazgo". Es **una evaluación de una regla sobre un ámbito concreto** — y existe aunque el resultado sea "cumple".

```
TrazaDeEvaluacion
├── id_evaluacion            identificador único, estable
├── analisis_id              a qué análisis pertenece
├── regla                    §4  qué se aplicó
├── ambito                   sobre qué (pieza / vivienda / planta / edificio)
├── entradas          [ ]    §5  qué datos y de dónde salieron
├── derivacion        [ ]    §6  qué cálculo se hizo
├── parametro_resuelto       §6  el umbral y por qué nivel se resolvió
├── norma                    §7  el artículo, en su versión vigente entonces
├── condiciones_evaluadas [] qué activó o desactivó la regla
├── excepciones_comprobadas[]qué excepciones se miraron y si aplicaron
├── desenlace                §9  cumple / no cumple / no evaluable / no considerada
├── evidencia         [ ]    §8  tramos, con fuerza
└── confianza                mínimo de las fuerzas (EVIDENCE_MODEL §9)
```

Y por encima, el contenedor que hace posible la reproducción:

```
TrazaDeAnalisis
├── analisis_id
├── anclajes                 §10 versiones fijadas
├── fecha_devengo            qué normativa aplicaba (NORMATIVE_ENGINE §4.2)
├── evaluaciones      [ ]    todas las TrazaDeEvaluacion
├── cobertura               §9.2 qué materias no se comprobaron
└── hash_traza               huella del conjunto completo
```

`hash_traza` cumple una función concreta: permite demostrar que el informe que alguien enseña es el que se emitió, sin haber sido editado después.

---

## 4. Pregunta 1 — qué regla disparó

```
regla:
  concept_id:   cam.habitabilidad.superficie.dormitorio_minimo
  instance_id:  cam.habitabilidad.superficie.dormitorio_minimo@v3
  nombre:       "Superficie mínima de dormitorio según ocupación"
  tipo:         exigencia_cuantitativa
  patron:       UMBRAL_SIMPLE
  prioridad:    bloqueante
  nivel:        2
```

Los dos ids son obligatorios y hacen cosas distintas (`FACT_MODEL.md` §7, reutilizado en `NORMATIVE_ENGINE.md` §5.1):

- **`instance_id`** es lo que hace defendible el informe: dice qué versión exacta de la regla se aplicó.
- **`concept_id`** es lo que hace útil el producto: permite decir *"este hallazgo es el mismo que el de enero, ahora agravado"* aunque la regla se haya versionado tres veces en medio. Es la huella de `OBSERVATION_MODEL.md`, que depende de `concept_id` y nunca de `instance_id`.

**Diferencia con hoy:** `IssueReport` (`evaluator.py:1924-1940`) identifica la regla con dos campos, `bloque: int` (1-11) y `codigo: str`. `bloque` es un número de sección de un archivo, no un identificador estable; `codigo` contiene etiquetas de agrupación (`HABITABILIDAD`, `EFICIENCIA`) y **se repite entre reglas distintas** — la auditoría documentó que `CTE-DB-SI-3` identifica a la vez la distancia de evacuación y la sectorización de incendios. Con ese par no se puede saber qué regla disparó: solo aproximadamente de qué familia era.

---

## 5. Pregunta 2 — qué datos del plano utilizó

Es la pregunta más difícil de las cinco y la única con un problema de ingeniería sin resolver en toda la serie.

### 5.1 El estado actual, medido

`Room` (`analyzer/parser.py:50-56`) tiene exactamente tres campos: `label`, `polygon`, `layer`. **El handle de la entidad DXF se descarta en el momento de parsear y no se guarda en ningún sitio.**

Peor: la única identidad de habitación que existe hoy en el motor es `id(r)` — la dirección de memoria del objeto Python (`evaluator.py:2353-2354`). Es válida dentro de un proceso y carece de sentido fuera de él.

Consecuencia: hoy es **estructuralmente imposible** responder a esta pregunta. Lo máximo que el sistema puede decir es "una pieza etiquetada *Dormitorio 2* en la capa *00 areas*", que no identifica nada — puede haber seis.

### 5.2 El problema que un esquema abstracto no ve

`FACT_MODEL.md` §9 fija el esquema canónico como "tipo de fuente + localizador", y es correcto. Pero aplicado al DXF choca con tres hechos:

1. **Los handles no son estables.** Al reabrir y guardar el archivo en AutoCAD, los handles pueden reasignarse. Un puntero por handle sobrevive a la sesión, no necesariamente al ciclo de trabajo real del arquitecto.
2. **El arquitecto vuelve a subir el plano modificado.** La pregunta relevante no es solo "qué polígono usé", sino "¿es esta pieza la misma que la del análisis anterior?". Sin eso, todo hallazgo aparece como nuevo en cada iteración y la funcionalidad de comparación se cae.
3. **La geometría se transforma antes de evaluarse.** Se escala a metros (`escala.py`), se descartan contenedores (`_discard_container_candidates`), se puede entrar en bloques. El polígono evaluado no es el dibujado. La traza tiene que apuntar al original, no al transformado.

### 5.3 Diseño: localizador compuesto con degradación registrada

```
entrada:
  fact:        superficie_util(pieza)
  valor:       8.52 m²
  origen:      observado
  localizador:
    archivo:      { nombre, hash_sha256, insunits_declarado }
    handle_dxf:   "1A4F"
    capa:         "00 areas"
    huella_geom:  "a3f9c2…"
    ruta_semantica: "VT1/3 › Dormitorio 2 › #1"
    resuelto_por: handle          ← obligatorio
  transformaciones: [ escala_a_metros(×0.001), sin_descarte_contenedor ]
```

Tres niveles de resolución, en orden, y **queda registrado cuál funcionó**:

| Nivel | Qué es | Sobrevive a | Falla ante |
|---|---|---|---|
| `handle` | Handle de la entidad DXF | La sesión | Re-guardado, exportación |
| `huella_geom` | Hash de (área, nº vértices, centroide relativo al contorno de la vivienda), redondeados a tolerancia | Re-guardado, traslación del dibujo | Modificación real de la pieza |
| `ruta_semantica` | vivienda › etiqueta › ordinal | Casi todo | Renombrado, reordenación |

El campo `resuelto_por` es obligatorio y es el punto importante del diseño: **es el mismo principio que `CONSTRAINT_MODEL.md` §9 impone a la resolución de parámetros** — se puede usar un nivel de repliegue, pero nunca sin decirlo. Una traza que resolvió por `ruta_semantica` es más débil que una que resolvió por `handle`, y eso debe verse.

Y se conecta con `EVIDENCE_MODEL.md` §6, que ya fija el invariante correspondiente: un tramo geométrico cuyo puntero no resuelve **cae automáticamente a fuerza Baja**. Aquí se añade el escalón intermedio: resolver por repliegue no invalida el tramo, pero lo degrada de forma visible.

`transformaciones` cierra el punto 3: la traza registra qué le pasó a la geometría entre el DXF y la evaluación. Sin ese campo, un arquitecto que compare el área del informe con la de su AutoCAD y no coincida no tiene forma de saber por qué.

---

## 6. Pregunta 3 — qué cálculo hizo

Dos partes, y hoy no existe ninguna de las dos.

### 6.1 Derivación del dato

```
derivacion:
  - funcion: area_poligono@v1
    entrada: polígono (localizador §5)
    salida:  8.52 m²
  - funcion: lado_menor_rect_minimo@v1
    entrada: polígono
    salida:  2.31 m
```

Cada paso es una **función del catálogo cerrado de composición** (`FACT_MODEL.md` §4), con versión. Nunca una fórmula libre. `EVIDENCE_MODEL.md` §7 ya lo prohíbe explícitamente; aquí solo se concreta el formato.

**Por qué la versión de la función importa**: la auditoría encontró en `evaluator.py:1337` un cálculo que multiplica metros por un ratio adimensional y llama al resultado `window_area_m2`. Cuando eso se corrija, todos los informes anteriores habrán usado la versión antigua. Con la función versionada en la traza, se puede saber exactamente qué informes están afectados. Sin ella, no.

### 6.2 Resolución del parámetro

```
parametro_resuelto:
  buscado:      superficie_minima_dormitorio
  contexto:     { comunidad: pais_vasco, tipologia: plurifamiliar, ocupacion: individual }
  niveles:
    - { nivel: municipio+comunidad+tipologia, resultado: sin_valor }
    - { nivel: comunidad+tipologia,           resultado: sin_valor }
    - { nivel: comunidad,                     resultado: 6.0 m²  ✓ }
  resuelto_por: comunidad
  fue_repliegue: true
```

`fue_repliegue: true` es la corrección estructural directa del Bug #1 de `TECH_REVIEW.md`, tal como la prescribe `CONSTRAINT_MODEL.md` §9. No es que el sistema no pueda tener valores por defecto: es que no puede usarlos sin decirlo.

---

## 7. Pregunta 4 — qué artículo aplica

```
norma:
  norma_concept_id: pais_vasco.vivienda.diseno
  norma_instance_id: pais_vasco.vivienda.diseno@2022-03
  localizador:  { seccion: "…", apartado: "…", punto: "…" }
  literal:      "«…»"                    ← transcripción exacta
  resumen:      "…"                      ← reformulación nuestra
  boletin:      { nombre, fecha, numero }
  vigencia:     { desde: …, hasta: null }
  vigente_en_fecha_devengo: true
  ambito:       autonomico
  competencia:  autonomica_exclusiva
```

Cuatro decisiones heredadas de `NORMATIVE_ENGINE.md`:

- **`literal` y `resumen` separados** (§3.4): el arquitecto ve el texto legal y la explicación, y sabe cuál es cuál.
- **`vigente_en_fecha_devengo`** (§4.2): no basta con que la norma esté vigente hoy; la traza afirma que lo estaba cuando correspondía.
- **`competencia`** (§10): si son dos capas territoriales, `EVIDENCE_MODEL.md` §5 obliga a conservar **ambas** citas, no solo la que prevaleció.
- Sin `boletin` la regla no puede activarse en producción — invariante de `CONSTRAINT_MODEL.md` §8.

**Diferencia con hoy:** de 41 reglas con juicio visible, ninguna cita un artículo. Esta sección es lo que convierte el argumento de venta de `MOAT_ANALYSIS.md` §1 —*"cada aviso cita el artículo CTE real"*— en una afirmación cierta.

---

## 8. Pregunta 5 — qué evidencia encontró

Esta sección **no diseña nada nuevo**. Los tramos son los seis tipos cerrados de `EVIDENCE_MODEL.md` §2, su fuerza se calcula con la tabla de techos de §3, y la confianza es el mínimo simple de §9.

Lo único que este documento añade es la exigencia de que ese cálculo quede **escrito en la traza, no recalculado al mostrarlo**:

```
evidencia:
  - { tipo: Fact,       origen: superficie_util(…),  fuerza: Alta,  resuelto_por: handle }
  - { tipo: Constraint, origen: …@v3,                fuerza: Alta,  norma: §7 }
  - { tipo: Assumption, origen: ocupacion=individual,fuerza: Baja,  motivo: "etiqueta sin «Doble»" }
confianza: Baja        ← mínimo, por el tramo de Assumption
```

El ejemplo es real y merece señalarse: `evaluate_bedroom_minimum_area` (`evaluator.py:1810`) asume ocupación individual cuando la etiqueta no dice "Doble". Hoy esa suposición es invisible y el hallazgo se presenta como CRÍTICO sin matiz. Con la traza, el mismo hallazgo sigue siendo bloqueante **y a la vez** de confianza Baja — que es exactamente la combinación que `INFERENCE_ENGINE.md` obliga a mostrar junta y que hoy no se muestra nunca.

---

## 9. Los cuatro desenlaces

El error de fondo del sistema actual: **solo el incumplimiento deja rastro.**

### 9.1 Desenlaces por evaluación

| Desenlace | Se registra traza | Se muestra por defecto | Por qué importa |
|---|---|---|---|
| `no_cumple` | Sí | Sí | Es lo único que existe hoy |
| `cumple` | **Sí** | No, bajo demanda | *"Enséñame qué comprobaste y salió bien"* es la mitad del valor de un informe de revisión |
| `no_evaluable` | **Sí** | Sí, agrupado | Falta el dato. Es lo que separa "cumple" de "no lo he mirado" |
| `no_aplica` | Sí, ligera | No | La regla existe pero sus condiciones la excluyen — con el motivo |

Registrar `cumple` es lo que permite emitir la frase que hace vendible el producto: *"se comprobaron 340 reglas; 12 fallan, 6 no son evaluables por falta de datos, 322 se cumplen"*. Sin ese registro, un informe solo puede enumerar defectos, y un arquitecto no puede usarlo como prueba de que revisó nada.

### 9.2 Cobertura: lo que ni siquiera se consideró

```
cobertura:
  materias_evaluadas:    [ accesibilidad, evacuacion, habitabilidad, … ]
  materias_sin_cobertura: [ { materia: patrimonio, motivo: sin_corpus_para_municipio } ]
  datos_ausentes:         [ altura_libre, carpinteria, espesores_muro, … ]
```

`materias_sin_cobertura` implementa el estado `sin_cobertura` de `NORMATIVE_ENGINE.md` §13. `datos_ausentes` es, literalmente, lo que `get_missing_data_warnings` (`evaluator.py:116`) ya produce hoy — la mejor pieza de honestidad del repositorio, que la auditoría encontró infrautilizada. Aquí deja de ser un texto suelto y pasa a ser parte estructural de la traza.

**Es la diferencia entre "tu proyecto cumple" —insostenible— y "tu proyecto cumple lo que sé comprobar, y esto es lo que no sé comprobar" —defendible—.**

---

## 10. Reproducibilidad

Una traza es reproducible si, con las mismas entradas y los mismos anclajes, el sistema vuelve a producir exactamente la misma traza.

### 10.1 Anclajes obligatorios

```
anclajes:
  version_codigo:     git sha del motor
  version_corpus:     versión del corpus normativo (NORMATIVE_ENGINE §11)
  version_funciones:  versión del catálogo de composición
  hash_dxf:           sha256 del archivo subido
  parametros_usuario: { norte, tipologia, ciudad, escala, capa, fecha_devengo }
  entorno:            versiones de shapely / ezdxf / Python
```

`entorno` no es paranoia: la geometría en coma flotante puede variar entre versiones de librería y entre plataformas. Sin anclarlo, "reproducible" es una aspiración.

### 10.2 Los tres puntos no reproducibles de hoy

Identificados en el código actual:

| # | Punto | Archivo | Efecto |
|---|---|---|---|
| 1 | Identidad de habitación por `id()` | `evaluator.py:2353` | Dirección de memoria; distinta en cada ejecución |
| 2 | Elección de etiqueta por orden de aparición (`inside[0]`) | `parser.py` (documentado en el PRD de ingesta §1.f) | Determinista para un archivo dado, arbitraria entre archivos equivalentes |
| 3 | Narrativa de IA | `ai_analyst.py` | No reproducible por naturaleza |

Los puntos 1 y 2 se resuelven con las decisiones de §5.3. **El punto 3 no se resuelve: se separa.** La narrativa se guarda junto al informe, marcada como interpretación no trazable, y ninguna afirmación de cumplimiento puede apoyarse en ella.

### 10.3 Contrato

> Dados los mismos `anclajes` y el mismo `hash_dxf`, dos ejecuciones producen el mismo `hash_traza`.

Es verificable en CI: un test que analiza `ejemplo.dxf` dos veces y compara hashes. Barato de implementar y detecta cualquier regresión de determinismo el día que se introduce.

---

## 11. Presupuesto de coste

Medido sobre `ejemplo.dxf`, que es el único plano real disponible:

| Magnitud | Valor |
|---|---|
| Viviendas | 6 |
| Habitaciones | 34 |
| Comprobaciones por vivienda (`total_checks`) | ~30 |
| Evaluaciones por análisis | **~200** |
| Tramos por evaluación | 3-6 |
| **Tramos por análisis** | **600-1.200** |

Con el corpus completo de `NORMATIVE_ENGINE.md` (400-900 reglas), un edificio de 20 viviendas puede rondar las 5.000-10.000 evaluaciones.

Decisiones que se derivan de esto:

1. **La traza se guarda comprimida y aparte del payload principal.** El JSON que consume la SPA no la lleva entera; lleva un identificador y se pide bajo demanda.
2. **Las evaluaciones `cumple` se guardan en forma reducida** — regla, ámbito, desenlace, hash de entradas. La traza completa se puede reconstruir de forma determinista a partir de los anclajes (§10) precisamente porque el contrato de determinismo lo garantiza. Es la única excepción legítima al principio del §1, y solo aplica a lo que *no* falló.
3. **`no_cumple` y `no_evaluable` se guardan íntegras, siempre.** Son las que hay que defender.
4. **Índice por `(analisis_id, regla_concept_id, ambito)`**, que es la consulta del `diff_normativo` de `NORMATIVE_ENGINE.md` §4.3.

Sin este presupuesto, el diseño de §1 —guardarlo todo— parece razonable en abstracto y se vuelve inviable en cuanto entra un edificio grande.

---

## 12. Superficie de producto

La generación del texto es competencia de `EXPLANATION_ENGINE.md` (§3 profundidad, §4 los tres niveles, §6 citas inline) y no se rediseña aquí. Lo único propio de trazabilidad son tres afordancias:

1. **"¿De dónde sale esto?"** en cada hallazgo — abre la traza al nivel *Completa*.
2. **Resaltado sobre el plano** desde cualquier tramo geométrico — ya hay infraestructura (`plan_svg.room_problems`), pero hoy resalta por etiqueta, no por identidad. Con §5.3 pasaría a resaltar la pieza exacta.
3. **Sello de reproducibilidad** visible: versión de corpus, fecha de devengo, `hash_traza`. Es lo que convierte un PDF en un documento verificable.

Una nota de riesgo de producto: la traza completa es abrumadora si se muestra por defecto. El nivel *Estándar* de `EXPLANATION_ENGINE.md` §4 debe seguir siendo el predeterminado. La trazabilidad no es una funcionalidad que se enseñe: es una que está ahí cuando alguien la pide, y ese alguien suele ser un arquitecto que ya sospecha del resultado.

---

## 13. Exportación

El PDF debe llevar, además del informe:

- Anclajes y `hash_traza`.
- Fecha de devengo y versión de corpus.
- Cobertura declarada (§9.2) — **en el cuerpo, no en letra pequeña**.
- Por cada hallazgo: regla, artículo con literal, valor medido, umbral aplicado y confianza.
- La narrativa de IA, si se incluye, en sección aparte y marcada como no trazable.

La traza completa no va en el PDF: va como adjunto JSON o queda accesible por `analisis_id`.

---

## 14. Distancia al código actual

Medida, no estimada:

| Capacidad | Hoy | Dónde se rompe |
|---|---|---|
| Identificar la regla | ❌ Parcial | `bloque` + `codigo`, ambiguos y repetidos (`evaluator.py:1924-1927`) |
| Identificar la pieza del plano | ❌ No | `Room` sin handle (`parser.py:50-56`); identidad por `id()` (`evaluator.py:2353`) |
| Traza de cálculo | ❌ No | El cálculo es código inline en cada regla |
| Artículo | ❌ No | 0 de 41 reglas citan artículo |
| Evidencia con fuerza | ❌ No | La única traza es la cadena `.message` |
| Registrar `cumple` | ❌ No | `checks` guarda booleanos anónimos (`evaluator.py:2357`) |
| Registrar `no_evaluable` | 🟡 Parcial | `get_missing_data_warnings` existe pero está desconectado |
| Anclajes | 🟡 Parcial | Escala, capa y origen ya se guardan (`app.py:176-181`) — **buen precedente** |
| Determinismo | ❌ No | Los tres puntos de §10.2 |

Dos observaciones honestas sobre esta tabla.

La primera: la fila de anclajes ya está medio hecha. `app.py:176-181` guarda de qué capa salieron las superficies, en qué unidad y quién decidió la escala, con un comentario que dice *"un proyecto guardado tiene que poder explicar de dónde salieron sus superficies"*. Ese instinto es exactamente el de este documento. Lo que falta es extenderlo del proyecto a cada evaluación.

La segunda: el resto de la tabla está en rojo casi entero. No hay forma de llegar a esto de manera incremental sobre `evaluator.py` tal como está — la traza no se puede "añadir" a una función que calcula y compara en la misma línea. Requiere el motor declarativo de `CONSTRAINT_MODEL.md`, que es donde la traza se genera sola porque la evaluación ya es datos.

---

## 15. Secuencia

| Fase | Contenido | Valor entregado solo |
|---|---|---|
| **1** | Capturar el handle DXF y calcular `huella_geom` en el parser; dar identidad estable a `Room` | Resalte correcto sobre el plano; comparación entre versiones |
| **2** | Sello de anclajes por análisis + test de determinismo en CI | El informe deja de ser irreproducible |
| **3** | Registrar `no_evaluable` y cobertura como estructura | La frase defendible de §9.2 |
| **4** | Traza completa por evaluación, sobre el motor declarativo | Las cinco preguntas, contestadas |
| **5** | `diff_normativo` sobre trazas | La capacidad diferencial |

**La fase 1 es la más rentable y no depende de nada más.** Es una modificación acotada del parser que arregla, de paso, el resalte por etiqueta y habilita la comparación entre versiones de un mismo plano — que es funcionalidad vendible por sí sola, no solo infraestructura.

La fase 4 requiere el motor declarativo. No tiene sentido intentarla antes.

---

## 16. Riesgos y qué no resuelve

| # | Riesgo | Residual |
|---|---|---|
| 1 | **La traza da apariencia de rigor a un cálculo malo.** Trazar `ancho_fachada × 0.25` con todo detalle no lo hace correcto — lo hace *auditablemente* incorrecto | **Alto.** La trazabilidad expone errores, no los corrige. Es un argumento para arreglar §6.3 de la auditoría *antes* de trazarlo, no después |
| 2 | Coste de almacenamiento en edificios grandes | Medio — §11 lo acota |
| 3 | La huella geométrica falla ante modificación real de la pieza | Aceptado: es el comportamiento correcto, esa pieza *es* distinta |
| 4 | Nadie mira las trazas | Medio. Se usan cuando hay conflicto, que es raro y caro |
| 5 | Sobrediseño antes de tener usuarios | **Real.** Solo la fase 1 tiene valor autónomo hoy |

Sobre el riesgo 1, que es el que de verdad importa: este documento diseña un sistema que hace visible cómo se llegó a cada resultado. Aplicado al motor actual, lo primero que haría visible es que el 41 % de las incidencias del proyecto de ejemplo salen de una comparación entre magnitudes de distinta dimensión. **Esa es una razón para construirlo, pero también una advertencia sobre el orden:** trazar primero y corregir después significa emitir informes que documentan meticulosamente un error.

---

## 17. Resumen de decisiones

1. **La traza se persiste, no se recalcula.** Regenerar responde a otra pregunta.
2. **La unidad es la evaluación, no el hallazgo.** Existe también cuando cumple.
3. **Cuatro desenlaces**, no uno. `no_evaluable` es lo que separa un informe defendible de uno insostenible.
4. **Localizador compuesto de tres niveles con `resuelto_por` obligatorio.** Repliegue permitido, repliegue silencioso no.
5. **Funciones de composición versionadas**, para poder saber qué informes afecta la corrección de un cálculo.
6. **La narrativa de IA queda fuera de la traza**, marcada como no trazable.
7. **Contrato de determinismo verificable en CI**, con los tres puntos no reproducibles actuales identificados.
8. **Las evaluaciones `cumple` se guardan reducidas**; `no_cumple` y `no_evaluable`, íntegras.
9. **Nada de `EVIDENCE_MODEL.md` ni `EXPLANATION_ENGINE.md` se rediseña** — este documento los hace operativos.
10. **Corregir antes de trazar.** Un error trazado con detalle sigue siendo un error, y ahora documentado.

---

*Documento de diseño. Ninguna línea de código escrita ni modificada. Las mediciones de §11 y §14 proceden de `ejemplo.dxf` y del código en el commit `7a908e4`.*
