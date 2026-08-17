# DB-SI_IMPLEMENTATION_PLAN.md — Plan técnico de capacidades previas a reimplementar DB-SI

**Fecha:** 2026-08-08 · **Documento de entrada:** `docs/audits/DB-SI_REVIEW.md` (2026-08-08)
**Estado:** plan, sin implementar. **Ninguna línea de código modificada. Ninguna regla creada. Sin commits.**

---

## 1. Resumen ejecutivo

`DB-SI_REVIEW.md` dejó un resultado incómodo: de 24 exigencias del DB-SI, **1 es plenamente verificable**, 4 lo son parcialmente y 19
no lo son. La reacción instintiva sería abrir 12 tareas, una por regla. Este plan sostiene lo contrario.

**Las 12 reglas que requieren cambio no dependen de 12 problemas: dependen de 8 capacidades.** Y esas 8 capacidades no se distribuyen
de forma uniforme — tres de ellas (`CAP-1` superficie útil normativa, `CAP-2` uso previsto declarado, `CAP-3` ocupación) desbloquean
por sí solas todo lo que hoy es alcanzable, y las cinco restantes están gobernadas por una sola pregunta que no es de software.

### 1.1 El hallazgo que reordena el plan

Al preparar este documento se inspeccionó `ejemplo.dxf` entidad a entidad. El resultado cambia la prioridad de todo lo relacionado
con carpintería, muros y núcleo de comunicación:

> El fichero **sí contiene** bloques con puertas (`00 PUERTA`, 140 líneas sólo en `VT01`), muros (`00 MURO`), vidrio (`00 vidrio`),
> estructura (`estructuras`, 329 entidades) y **núcleo de comunicación** (`nucleo`, 147 entidades, con capa `00 ascensor`).
> **Pero el modelspace tiene 0 INSERT.** Esos bloques están definidos y nunca insertados.

Las consecuencias son concretas y verificables:

1. **ArchMuse no los ignora por un defecto del parser.** `parser._recorrer_plano` (`parser.py:209`) recorre modelspace y desciende
   por INSERTs hasta 3 niveles — está bien construido. Simplemente no hay ningún INSERT desde el que descender.
2. **Un bloque no insertado no tiene posición en el plano.** No es que falte leerlo: es que sus coordenadas no están en el sistema
   de referencia del dibujo. No se puede saber dónde cae esa puerta.
3. Por tanto **"añadir carpintería al parser" no es una tarea de parser.** Es un problema de convención de entrada del DXF, de la
   misma familia que `CapaIndeterminada` ya resuelve preguntando al arquitecto qué capa contiene las estancias.

Esto degrada de golpe la prioridad de `CAP-6`, `CAP-7` y `CAP-8`, que son justamente las que desbloquean el grueso de las 19 reglas
no verificables. Y confirma que el camino corto —ocupación— es el único camino corto que existe.

*(Salvedad honesta: es un solo fichero. Otros DXF de Pablo pueden insertar sus bloques con normalidad. El plan trata esto como
hipótesis a validar sobre una muestra, no como ley — misma cautela que ya se documentó para las convenciones de color de
`_discard_container_candidates`.)*

### 1.2 Segundo hallazgo: la superficie útil ya se recalcula tres veces

`evaluator.py` calcula "superficie útil" con la misma expresión —suma de áreas excluyendo `TERRAZA|TENDEDERO` (`NON_USEFUL_PATTERN`,
`:424`)— en **tres sitios independientes**: `:452` (R03 eficiencia), `:824` (R07 superficie mínima) y `:1230` (R14 circulación).

No es un defecto cosmético. La ocupación (`CAP-3`) sería el cuarto consumidor del mismo cálculo, y el DB-SI la indexa explícitamente
"en función de la superficie útil". Añadir un cuarto duplicado incrustaría una definición no normativa en materia de incendios. Es
exactamente el caso de uso del *Compositor de Hechos* y su catálogo de funciones de composición de `docs/brain/FACT_MODEL.md` §4: la
aritmética ocurre una vez, aguas arriba, y ninguna regla la contiene.

### 1.3 Lo que este plan propone

| | |
|---|---|
| Capacidades nuevas identificadas | **8** |
| Reglas que se activan con las 3 primeras | 1 plena (`C08`) + 2 correcciones honestas (`C01`, `C09`) |
| Reglas que seguirán siendo UNKNOWN aun con las 8 | **7** |
| Reglas descartadas definitivamente | **13** |
| Bloque recomendado para empezar | **Bloque A — CAP-1 + CAP-2 + CAP-3** |

El criterio que gobierna cada ficha es la cadena que pidió el encargo: **norma → hecho necesario → fuente del hecho → cálculo →
juicio.** Si alguno de esos cinco eslabones no se puede demostrar desde el DXF, la salida es `UNKNOWN` y la regla no se implementa.

---

## 2. Capacidades / Facts que faltan

Ocho capacidades. Las tres primeras son Facts; las cinco restantes son, en su mayoría, adquisición de datos de entrada.

---

### CAP-1 — Superficie útil con definición declarada

**Naturaleza:** Fact derivado (función de composición pura). **No es una regla:** no tiene `passed`.

**Por qué es una capacidad y no un detalle:** hoy existen tres implementaciones idénticas y ninguna declara contra qué definición
mide. `NORMATIVE_ENGINE.md` §6 ya defendió `definicion` como tipo de primera clase precisamente por esto: *«buena parte de las
discrepancias normativas reales no son de umbral sino de definición»*. La exclusión de terraza y tendedero es un criterio de ArchMuse,
razonable, pero no es la definición de ninguna norma citada.

**Qué debe producir:** un valor de superficie útil por ámbito (pieza / vivienda / planta), con la definición usada adjunta e
inseparable del valor — no como metadato opcional, sino como parte del contrato de lectura (`FACT_MODEL.md` §10).

**Datos que necesita:** los que ya hay (`Room.area_m2`, `Room.label`, agrupación en `Unit`).

**Unidades:** m². Sin ambigüedad — `parser.leer_plano` ya se niega a continuar si no sabe la escala del dibujo (`EscalaIndeterminada`),
así que la conversión a metros está garantizada aguas arriba. Este punto importa: es la única de las 8 capacidades cuya unidad está
blindada por construcción.

**Cadena:** norma (DB-SI 3 §2 indexa "superficie útil") → hecho (superficie útil por ámbito) → fuente (polígonos del DXF, ya leídos)
→ cálculo (suma con exclusiones declaradas) → juicio (**ninguno** — es insumo).

---

### CAP-2 — Uso previsto declarado

**Naturaleza:** Fact declarado (dato del proyecto, no del DXF).

**El problema exacto:** ArchMuse conoce `tipologia` ∈ {plurifamiliar, unifamiliar, rehabilitacion}. El DB-SI indexa por **uso
previsto** ∈ {Residencial Vivienda, Residencial Público, Administrativo, Comercial, Docente, Hospitalario, Pública Concurrencia,
Aparcamiento, Almacén}. **No son el mismo eje.** `tipologia` describe el tipo de encargo; `uso previsto` es la clave de entrada de las
Tablas 1.1, 2.1, 3.1, 5.1 y 1.1 de SI 4 — cinco tablas del documento.

Hoy la equivalencia "plurifamiliar → Residencial Vivienda" es correcta y se puede sostener, pero **está implícita**. Toda regla DB-SI
que se implemente sin declararla estará repitiendo la estructura del Bug #1 (`TECH_REVIEW.md`): un valor por defecto que nadie eligió,
que funciona hasta que deja de funcionar en silencio.

**Qué debe producir:** el uso previsto del edificio, declarado, más la posibilidad de declarar usos secundarios por zona (local
comercial en planta baja, aparcamiento). Mientras no se declare, el uso secundario es `UNKNOWN`, **nunca "no hay"** — es la
distinción que `C07` y `C14` necesitan para no resolverse por silencio.

**Datos que necesita:** un campo nuevo en el formulario (`/api/analizar` y `/api/generar`). Cero cambios en el parser.

**Cadena:** norma (5 tablas indexadas por uso) → hecho (uso previsto) → fuente (**declaración del arquitecto**, no el DXF) → cálculo
(ninguno) → juicio (ninguno — es eje de contexto).

---

### CAP-3 — Ocupación calculada

**Naturaleza:** Fact derivado. La capacidad central de este plan.

**Fuente normativa:** DB-SI 3, apartado 2, **Tabla 2.1 (Densidades de ocupación)**. Verificado literalmente contra el segmento
ingerido (`extraccion/estado/candidatas/codigotecnico__DB-SI__0a2e78cd6247.jsonl`, registro 8):

> *«Para calcular la ocupación deben tomarse los valores de densidad de ocupación que se indican en la tabla 2.1 **en función de la
> superficie útil de cada zona**»*
>
> Residencial Vivienda · **Plantas de vivienda · 20 m²/persona**

**Fórmula:**

```
ocupación(zona) = superficie_útil(zona) [m²] / densidad(uso, tipo de zona) [m²/persona]
```

**Unidades — y la trampa que hay que evitar.** La tabla se expresa en **m²/persona**, es decir, es un *divisor*, no un multiplicador.
Es la inversión mental fácil y produce un resultado 400 veces equivocado en el caso residencial. Conviene decirlo aquí porque el motor
ya tiene un precedente exacto de error dimensional silencioso: `window_area_m2 = long_side × 0.25` (`evaluator.py:1253`), metros
presentados como m², responsable del 41 % de las incidencias del proyecto de ejemplo (`NORMATIVE_AUDIT.md` §6.3). El resultado de
CAP-3 es **personas**, adimensional y entero por exceso.

Tres reglas de la propia tabla que no son opcionales:

- La tabla admite **"Ocupación nula"** para zonas de mantenimiento — no es 0 personas, es una categoría distinta, y `C15` depende de
  ella ("plantas que no sean zona de ocupación nula").
- El texto obliga a usar una **ocupación mayor cuando sea previsible**, y una menor si una disposición legal lo exige. Es una
  *excepción sujeta a justificación humana* (`CONSTRAINT_MODEL.md` §5): el motor la expone, nunca la aplica solo.
- Zonas no incluidas en la tabla toman "los valores más asimilables" — **criterio profesional**, no automatizable. Debe producir
  `UNKNOWN`, no una asimilación inventada.

**Relación con superficie útil:** dependencia dura de `CAP-1`. Y aquí hay una decisión de ámbito que no debe resolverse por comodidad:
la tabla dice **"Plantas de vivienda"**. El ámbito normativo es la **planta**, no la vivienda. Calcular "la ocupación de VT3/3" es una
extrapolación cómoda pero no es lo que la tabla indexa. Como ArchMuse agrupa por vivienda (`group_rooms_by_unit_label`) y no tiene
concepto de planta, esto obliga a `CAP-4`.

**Cómo debe representarse como hecho del modelo** — cinco propiedades, todas heredadas de `FACT_MODEL.md`:

| Propiedad | Valor |
|---|---|
| Naturaleza | **Fact derivado**, producido por función de composición del catálogo compartido — nunca dentro de una regla |
| Ámbito | Planta (dimensión física). Vivienda sólo como agregado informativo, marcado como tal |
| Origen epistémico | `derivado`; hereda la fuerza del más débil de sus insumos (`EVIDENCE_MODEL.md`) |
| Trazabilidad | Debe citar qué densidad de tabla se aplicó y por qué uso — si el uso vino por defecto y no declarado, **eso se escribe en la Evidence** (§8 de `CONSTRAINT_MODEL.md`: todo repliegue se registra) |
| Juicio | **Ninguno.** La ocupación no se cumple ni se incumple. Es el insumo de las que sí |

**Cadena:** norma (DB-SI 3 §2 Tabla 2.1, literal) → hecho (ocupación en personas por planta) → fuente (CAP-1 + CAP-2, ambos
disponibles tras el Bloque A) → cálculo (división, redondeo por exceso) → juicio (ninguno; alimenta `C09`, `C10`, `C15`, `C16`).

---

### CAP-4 — Modelo de planta

**Naturaleza:** dimensión de ámbito ausente en el modelo de datos.

**El problema:** ArchMuse tiene `Room` → `Unit`. **No tiene planta.** `PlanoLeido` (`parser.py:131`) devuelve `rooms` y
`unit_labels`, nada más. Pero el DB-SI razona casi siempre por planta: "salida de planta", "plantas de vivienda", "la longitud de los
recorridos hasta una salida de planta", "toda planta que no sea zona de ocupación nula", "plantas sobre rasante".

En `/api/generar` existe `edificio.plantas` (`app.py:253`), pero es un número, no una geometría: no dice qué habitaciones están en qué
planta. En el flujo DXF no existe ni el número.

**Qué debe producir:** asignación de cada `Unit`/`Room` a una planta, y la distinción sobre/bajo rasante.

**Por qué no es trivial:** un DXF de una planta no dice qué planta es. Requiere declaración del arquitecto o convención de capas.
La detección automática por solape de huellas es tentadora y engañosa — el propio motor ya aprendió esa lección con
`_discard_container_candidates`.

**Cadena:** norma (SI 1 §1, SI 3 §2/§3/§9, SI 6 §3 indexan por planta) → hecho (planta de cada pieza + posición respecto a rasante) →
fuente (**declaración**, o convención documentada; no inferible con fiabilidad) → cálculo (agregación) → juicio (ninguno).

---

### CAP-5 — Altura de evacuación

**Naturaleza:** Fact derivado a partir de `CAP-4`, o declarado.

**El problema y la tentación:** en `/api/generar` sería inmediato escribir `h = plantas × altura_libre_m`. **Sería incorrecto.** La
altura de evacuación se mide desde el origen de evacuación hasta la salida del edificio, y la suma de alturas libres ignora los cantos
de forjado — un edificio de 8 plantas con 2,80 m libres da 22,4 m por esa fórmula y unos 26 m reales. Con umbrales normativos en 9 m
(`C18`), 14 m y 28 m (`C11`, `C15`), un error del 15 % cae exactamente sobre los saltos de la tabla.

**Qué debe producir:** altura de evacuación, o `UNKNOWN`. Si se estima, **marcada como hipótesis, nunca como hecho** — es la
distinción hecho/hipótesis de `DECISION_ENGINE.md` §11, y el punto donde es más fácil violarla sin darse cuenta.

**Cadena:** norma (SI 3 §5 y §9, SI 5 §1, SI 6 §3) → hecho (altura de evacuación en m) → fuente (CAP-4 + canto de forjado, **que no
existe en ningún flujo**) → cálculo (suma) → juicio (ninguno) → **salida honesta: UNKNOWN salvo declaración explícita.**

---

### CAP-6 — Geometría de zonas comunes y salidas

**Naturaleza:** adquisición de datos de entrada. **Bloqueada por el hallazgo §1.1.**

**Qué falta:** el núcleo de comunicación (portal, escalera, ascensor), la posición de las salidas de planta y de edificio, y su
número. Sin esto, ninguna regla de recorrido de evacuación del DB-SI es evaluable: el recorrido normativo va de la puerta de la
vivienda a la salida de planta, y ArchMuse sólo ve el interior de las viviendas.

**Estado real del dato:** `ejemplo.dxf` **contiene** un bloque `nucleo` con 147 entidades (muros, `00 ascensor`, escalera) — y **no
está insertado**. El dato existe en el fichero y no existe en el dibujo. Resolverlo no es programar un lector: es acordar una
convención de entrega del DXF, o resolver bloques no insertados asumiendo una posición que nadie ha declarado (inaceptable).

**Cadena:** norma (SI 3 §3, §4, §5) → hecho (grafo de recorrido hasta salida de planta) → fuente (**no disponible**) → cálculo
(Dijkstra, ya implementado en `adyacencia.py`) → juicio → **UNKNOWN**.

Nótese que el cálculo es la única parte ya resuelta. Es un buen recordatorio de que el cuello de botella de ArchMuse no es
algorítmico.

---

### CAP-7 — Carpintería: huecos y puertas

**Naturaleza:** adquisición de datos de entrada. **Bloqueada por el hallazgo §1.1.**

**Qué falta:** posición, dimensión, altura de alféizar y sentido de apertura de huecos y puertas.

**Estado real del dato:** las capas `00 CAPINTERIAS`, `00 PUERTA`, `00 PUERTAS`, `00 vidrio` **existen en la tabla de capas** de
`ejemplo.dxf`, y los bloques `VT01`…`VT19` contienen 140 líneas en `00 PUERTA` y 22 en `00 vidrio` cada uno. Ninguno está insertado en
modelspace.

**Advertencia que debe sobrevivir a este plan:** mientras `CAP-7` no exista, sigue **prohibido** derivar cualquier regla de DB-SI del
proxy `long_side × WINDOW_TO_FACADE_RATIO`. Es el punto explícito de `DB-SI_REVIEW.md` para `C05` y `C19`, y la razón es que el proxy
no da ni posición, ni altura de alféizar, ni separación entre ejes — que es literalmente todo lo que esas reglas miden. Un proxy
dimensionalmente incoherente en salubridad es un defecto; el mismo proxy en incendios es un falso cumplimiento en materia de
seguridad.

Un matiz operativo: incluso resuelto el INSERT, un conjunto de LINEs en capa `00 PUERTA` no es una puerta tipada. Reconstruir hueco y
sentido de apertura desde líneas sueltas es un problema de interpretación geométrica considerable, no una lectura.

**Cadena:** norma (SI 2 §1, SI 3 §4/§6, SI 5 §2) → hecho (huecos y puertas tipados) → fuente (**no disponible**) → **UNKNOWN**.

---

### CAP-8 — Datos constructivos: resistencia y reacción al fuego

**Naturaleza:** frontera del modelo. No es una capacidad a planificar: es un límite a declarar.

**Qué falta:** resistencia al fuego (EI/REI/R) de muros, forjados y puertas; reacción al fuego de revestimientos; composición
constructiva.

**Por qué no se planifica:** un DXF de distribución no contiene, ni contendrá, la clasificación al fuego de un cerramiento. Es la
laguna transversal nº 1 de `ARCHITECTURAL_KNOWLEDGE_MAP.md`, la misma que limita simultáneamente los Dominios 7 (Acústica), 8
(Térmica) y 11 (Estructura). Su solución no es un parser mejor: es otra fuente de datos (memoria constructiva, BIM/IFC — el horizonte
de `NORTH_STAR_2031.md`).

**Qué sí corresponde hacer ahora:** que `get_missing_data_warnings` lo siga diciendo, y que ninguna regla lo contradiga. Hoy R26 lo
contradice (ver `C01`).

**Cadena:** norma (SI 1 §1/§2/§3/§4, SI 2, SI 6 completo) → hecho (clasificación al fuego) → fuente (**inexistente por naturaleza
del formato**) → **UNKNOWN permanente**.

---

## 3. Dependencias entre capacidades y reglas

```
                       ┌──────────────────────────┐
                       │ CAP-2  Uso previsto      │  (declaración; sin dependencias)
                       └────────────┬─────────────┘
                                    │
  ┌──────────────────────┐          │
  │ CAP-1 Superficie útil│──────────┤
  │       (definición)   │          │
  └──────────┬───────────┘          │
             │                      │
             └──────────┬───────────┘
                        ▼
             ┌─────────────────────┐
             │ CAP-3  OCUPACIÓN    │◄──── CAP-4 (ámbito correcto: planta)
             └──────────┬──────────┘
                        │
        ┌───────────────┼─────────────────┬──────────────┐
        ▼               ▼                 ▼              ▼
   C09 recorridos   C10 dimens.       C15 discapac.   C16 dotación
        │               │                 │              │
        ▼               ▼                 ▼              ▼
    + CAP-6         + CAP-7           + CAP-5        + CAP-7
    (salidas)      (carpintería)      (altura)      (equipos PCI)
        │               │                 │              │
        └───────────────┴─────────────────┴──────────────┘
                        │
                  todas BLOQUEADAS por §1.1


   CAP-4 planta ──► C01 (sector ≤ 2.500 m²)  ──► + CAP-8 para el EI 60 ──► UNKNOWN permanente
   CAP-5 altura ──► C11, C15, C18 (condiciones de activación)
   CAP-8        ──► C01, C02(T2.2), C03, C04, C05, C06, C21, C22, C23  ──► UNKNOWN permanente
```

**Lectura del grafo, en una frase:** `CAP-3` es el único nodo con cuatro consumidores, pero **los cuatro necesitan además una capacidad
bloqueada**. Es decir: la ocupación es necesaria para todas y suficiente para ninguna.

Esa asimetría es la decisión más importante del plan y merece decirse sin rodeos. Podría interpretarse como argumento para no hacer
`CAP-3`. Es lo contrario, por tres razones:

1. **Convierte cuatro silencios en cuatro `UNKNOWN` explicados.** Hoy `C09` afirma cumplimiento; con `CAP-3` puede decir exactamente
   qué le falta ("ocupación 47 personas; no consta el número de salidas de planta"). Eso es producto, no infraestructura.
2. **Es la única capacidad de las 8 que es puramente interna.** No depende de que cambie el DXF de entrada ni de que el arquitecto
   aprenda una convención nueva.
3. **`CAP-1` paga su coste sola**, eliminando la triplicación de §1.2 y dando a R03, R07 y R14 una definición declarada — tres reglas
   ya existentes que mejoran sin tocar su lógica.

---

## 4. Datos que debe proporcionar el parser

Tabla honesta sobre quién debe producir cada dato. **Nada de esto se implementa en este plan.**

| Dato | ¿Lo puede dar el parser? | Estado en `ejemplo.dxf` | Comentario |
|---|---|---|---|
| Polígonos de estancia + etiqueta | **Ya lo da** | 53 LWPOLYLINE en `00 areas` | Base de todo el motor |
| Agrupación en vivienda | **Ya lo da** | 23 MTEXT tipo `VT…` | `group_rooms_by_unit_label` |
| Escala / unidades | **Ya lo da** | Resuelta | `EscalaIndeterminada` impide el fallo silencioso |
| Taxonomía tipada de locales (trastero, contadores, calderas) | Sí, con trabajo | No hay locales rotulados | Necesario para `C02`. **Ausencia de rótulo ⇒ `UNKNOWN`**, nunca "no hay" (lección de R18c) |
| Planta de cada pieza (`CAP-4`) | **No con fiabilidad** | No consta | Requiere declaración o convención de capas |
| Núcleo de comunicación y salidas (`CAP-6`) | **No hoy** | Bloque `nucleo` (147 ent.) **sin insertar** | No es leer: es acordar la entrega del DXF |
| Huecos y puertas (`CAP-7`) | **No hoy** | Bloques `VT01`-`VT19` con `00 PUERTA`/`00 vidrio` **sin insertar** | Y, aun insertados, LINEs sueltas ≠ puerta tipada |
| Resistencia/reacción al fuego (`CAP-8`) | **No, nunca** | No existe | Frontera del formato, no del parser |
| Uso previsto (`CAP-2`) | **No — no es del parser** | — | Campo de formulario |
| Altura de evacuación (`CAP-5`) | **No — no es del parser** | — | Declarada, o hipótesis marcada |

**La conclusión que conviene retener:** de los 5 datos que faltan, **sólo 1 es realmente trabajo de parser** (taxonomía de locales).
Dos son declaraciones del arquitecto y dos son un problema de convención de entrega. Ninguno se resuelve leyendo mejor el DXF actual.

---

## 5. Datos que ya existen

Inventario de lo aprovechable, con su ubicación. Es más de lo que parece.

| Dato | Dónde | Uso en este plan |
|---|---|---|
| Áreas de estancia en m² | `parser.Room.area_m2` | Insumo de `CAP-1` |
| Etiquetas de estancia | `parser.Room.label` | Clasificación de zona |
| Viviendas | `evaluator.Unit`, `group_rooms_by_unit_label` | Ámbito de agregación intermedio |
| Superficie útil (3 copias) | `evaluator.py:452`, `:824`, `:1230` | **A unificar en `CAP-1`** |
| Grafo de adyacencia entre piezas | `analyzer/adyacencia.py` | Ya resuelve el *cálculo* de `CAP-6` |
| Dijkstra y recorrido más largo | `adyacencia.weighted_shortest_path`, `recorrido_mas_largo` | Reutilizable sin cambios |
| Vocabulario de piezas de circulación | `evaluator._CIRCULACION_PATTERN:1564` | Ya corrige el fallo de rótulo de R17/R18c |
| Patrón de no-útil | `evaluator.NON_USEFUL_PATTERN:424` | Definición actual, a declarar en `CAP-1` |
| Tipología | formulario + `UMBRALES_TIPOLOGIA` | Punto de partida —**no equivalente**— de `CAP-2` |
| Zona climática | `analyzer/cte_zonas.py` | Precedente de resolución ciudad→valor |
| Nº de plantas y altura libre (sólo `/api/generar`) | `app.py:253-254` | Insumo parcial y **peligroso** de `CAP-5` |
| Avisos de no evaluable | `evaluator.get_missing_data_warnings:117` | La pieza sobre la que se apoya todo el plan |
| Corpus DB-SI ingerido | `extraccion/estado/candidatas/…DB-SI…jsonl` | Texto literal citable, 25 registros |
| Catálogo de materias y validador | `normativa/esquema/materias.yaml` | `seguridad_incendio → [DB-SI]`; impediría M3 |

---

## 6. Reglas que podrán activarse después de cada capacidad

| Tras completar | Se activa | Naturaleza del resultado |
|---|---|---|
| **CAP-1** | Ninguna regla nueva | Mejora R03, R07, R14: definición declarada, cálculo único |
| **CAP-2** | Ninguna regla nueva | Elimina el defaulting implícito; habilita `C07`/`C14` para resolver `no_aplica` con motivo |
| **CAP-1+2+3** | **`C08` (ocupación) — dato publicable, sin juicio** | Y convierte `C09`, `C10`, `C15` de silencio a `UNKNOWN` explicado |
| **CAP-4** | `C01` parcial: sector ≤ 2.500 m² por planta | Sólo el límite de superficie. El EI 60 sigue en UNKNOWN |
| **CAP-5** | Ninguna regla plena | Habilita **avisos condicionales** en `C11`, `C15`, `C18` — aviso, no comprobación |
| **CAP-6** | `C09` plena (recorridos 25/50/35 m + 25 % rociadores) | Requiere además nº de salidas y presencia de rociadores, ambos declarados |
| **CAP-7** | `C10` (anchura de puertas), `C19` (huecos de bomberos) | Sólo si la carpintería llega tipada, no como LINEs |
| **CAP-8** | Nada — y ése es el punto | Se declara frontera permanente |

**Sobre las alternativas 25/50/35 m y el 25 % (el detalle que el encargo pide analizar).** Aun con `CAP-3` y `CAP-6` completas, `C09`
sigue necesitando tres datos que **ninguna capacidad geométrica produce**:

| Dato | Origen posible | Sin él |
|---|---|---|
| Nº de salidas de planta (1 vs. >1) | Declarado o de `CAP-6` | No se sabe si el límite es 25 o 50 m |
| "Ocupantes que duermen" | Derivable del uso previsto (`CAP-2`): en Residencial Vivienda, sí | Determina 35 m frente a 50 m |
| Instalación automática de extinción | **Declaración del arquitecto, siempre** | No se puede aplicar el +25 % de la nota (1) |

El tercero es interesante: la presencia de rociadores no es geométrica ni lo será nunca. Debe ser un dato declarado, y su ausencia
debe producir el cálculo **sin** el 25 % (el caso más restrictivo), marcando que se ha asumido la ausencia. Nunca al revés.

---

## 7. Reglas que seguirán siendo UNKNOWN incluso después

Siete reglas quedan en `UNKNOWN` aunque se completen las ocho capacidades. Se separan por *motivo*, porque el motivo determina si
algún día dejarán de serlo.

| Regla | Motivo | ¿Reversible? |
|---|---|---|
| `C01` (EI 60 entre viviendas) | Depende de `CAP-8` — dato constructivo | Sólo con otra fuente de datos (BIM/memoria) |
| `C02` (Tabla 2.2: R/EI/vestíbulos/puertas) | Ídem | Ídem. La clasificación de riesgo (Tabla 2.1) sí es alcanzable |
| `C07` (compatibilidad de evacuación) | Requiere declarar todos los usos del edificio | Sí, con `CAP-2` extendido a usos secundarios |
| `C11` (protección de escaleras) | El **tipo** de escalera (protegida / especialmente protegida) es dato constructivo | No desde DXF |
| `C15` (evacuación de personas con discapacidad) | `CAP-5` + identificación de salidas accesibles y zonas de refugio | Parcial |
| `C18` (aproximación de bomberos) | Geometría del viario y del entorno urbano, ajena al DXF de planta | No sin fuente cartográfica |
| `C16` (dotación de PCI) | Posición de equipos proyectados | Sí, si se modelan — el criterio de 15 m sería evaluable con `adyacencia.py` |

**Advertencia sobre `C18`,** repetida del review porque es donde más fácil sería recaer: un retranqueo insuficiente *sugiere* que no
cabe el espacio de maniobra de 5 m. Es una inferencia razonable y probablemente cierta, pero DB-SI 5 regula el espacio de maniobra, no
el retranqueo, y ese espacio puede resolverse en viario público. Si algún día interesa, su sitio es `chain_effects.py` con la cadena
causal visible — nunca una incidencia con código DB-SI.

---

## 8. Reglas descartadas definitivamente

Trece reglas se descartan de forma permanente para el modelo DXF de planta. **Descartar no significa borrar del corpus**: significa
que nunca serán evaluables y que su sitio es el estado `aplica_no_evaluable` de `NORMATIVE_ENGINE.md` §13, alimentando la lista de "no
evaluable" en lugar de una comprobación.

| Regla | Materia | Razón del descarte definitivo |
|---|---|---|
| `C03` | Espacios ocultos, paso de instalaciones | No hay sección vertical ni instalaciones |
| `C04` | Reacción al fuego de revestimientos | Materiales (`CAP-8`). **Nota (4): excluye el interior de viviendas** ⇒ registrar `no_aplica` razonado |
| `C05` | Medianerías y fachadas | Geometría 3D + huecos + EI. Prohibido el proxy de huecos |
| `C06` | Cubiertas | ArchMuse no modela cubierta en ningún flujo |
| `C12` | Puertas en recorridos de evacuación | Sentido de apertura y herrajes: fuera del alcance incluso con `CAP-7` |
| `C13` | Señalización | **Exención expresa de Residencial Vivienda** ⇒ registrar `no_aplica`, no silencio |
| `C14` | Control de humo | Supuestos de activación ajenos a vivienda; requiere declarar aparcamiento |
| `C19` | Accesibilidad por fachada | Alféizar y separación entre ejes de huecos. **Riesgo máximo de recaída en el proxy** |
| `C20` | Generalidades (estructura) | Descriptivo/procedimental. Además: severidad `procedimental` fuera de la escala de 4 |
| `C21` | Resistencia al fuego (criterio) | Método de cálculo; condiciones cualitativas Nivel 4 |
| `C22` | Elementos estructurales principales | Tabla formalizable, dato inexistente. Ejemplo puro de "corpus sí, evaluación no" |
| `C23` | Elementos estructurales secundarios | Clasificación principal/secundario es juicio técnico |
| `C24`, `C25` | Acciones y determinación de resistencia | Procedimental; remiten a DB-SE y Anejos C-F no ingeridos |

*(`C24` y `C25` se cuentan como una entrada conjunta en la tabla; el total sigue siendo 13 reglas.)*

---

## 9. Terminología: el Anejo SI A

El encargo pide identificar qué reglas dependen del Anejo SI A y qué definiciones habría que incorporar. Es un bloqueo transversal y
barato de resolver, lo que lo convierte en la anomalía útil de este plan.

**Estado:** el corpus ingerido cubre las secciones SI 1 a SI 6 (31 segmentos → 25 candidatas). **El Anejo SI A (Terminología) no está
ingerido.** Dos candidatas lo referencian (`C13`, `C25`) sin que su texto exista en el corpus.

**Reglas que dependen de él:**

| Definición | Reglas afectadas | Por qué es determinante |
|---|---|---|
| **Origen de evacuación** | `C09`, `C10`, `C16` | Decide si los 25 m se miden desde dentro de una habitación o desde la puerta de la vivienda. **Es la definición que invalida el ámbito actual de R17** |
| **Altura de evacuación** | `C11`, `C15`, `C18`, `C22` | Define `CAP-5` y los umbrales de 9 / 14 / 28 m |
| **Salida de planta / de edificio / de recinto** | `C09`, `C10`, `C11` | Define qué cuenta como salida en `CAP-6` |
| **Sector de incendio** | `C01`, `C22` | Define el ámbito de agregación del límite de 2.500 m² |
| **Sector de riesgo mínimo** | `C01`, `C21` | Condición de excepción en varias tablas |
| **Espacio exterior seguro** | `C09` | Extremo del recorrido de evacuación |
| **Zona de ocupación nula** | `C03`, `C15`, y **`CAP-3`** | La Tabla 2.1 la usa como categoría, no como cero |
| **Aparcamiento abierto** | `C14` | Condición de activación |
| **Superficie útil / construida** | `CAP-1`, `C01` | Distinción que hoy ArchMuse no hace |

**Recomendación:** ingerir el Anejo SI A **antes** de tocar ninguna regla de evacuación. Es la tarea de mejor relación
valor/esfuerzo del plan: el pipeline de extracción ya existe y funciona, y sin ella cualquier reimplementación de `C09` se apoyaría en
memoria en vez de en texto — exactamente lo que la regla de dos personas de `NORMATIVE_ENGINE.md` §12 existe para impedir. Este
documento ha marcado como *pendiente de ingesta* toda afirmación que dependa del Anejo, y esa marca debería desaparecer por ingesta,
no por costumbre.

---

## 10. Matriz de capacidades

| Capacidad | Reglas dependientes | Datos actuales | Datos faltantes | Prioridad |
|---|---|---|---|---|
| **CAP-1** Superficie útil con definición declarada | `C08`, y mejora R03/R07/R14 | Áreas y etiquetas de estancia; 3 implementaciones duplicadas | Definición normativa declarada; ámbito explícito | **1** |
| **CAP-2** Uso previsto declarado | `C08`, `C01`, `C07`, `C14`, y 5 tablas del DB-SI | `tipologia` (eje distinto) | Campo de formulario; usos secundarios por zona | **2** |
| **CAP-3** Ocupación calculada | `C09`, `C10`, `C15`, `C16` | Superficie útil (vía CAP-1); Tabla 2.1 ingerida y verificada | CAP-1 + CAP-2; decisión de ámbito (planta) | **3** |
| **CAP-4** Modelo de planta | `C01`, `C08` (ámbito), `C09`, `C15`, `C22` | `edificio.plantas` sólo en `/api/generar` | Asignación pieza→planta; sobre/bajo rasante | **4** |
| **CAP-5** Altura de evacuación | `C11`, `C15`, `C18`, `C22` | `plantas × altura_libre_m` (estimación peligrosa) | Canto de forjado; o declaración directa | **5** |
| **CAP-6** Zonas comunes y salidas | `C09`, `C10`, `C11` | `adyacencia.py` resuelve ya el cálculo | Núcleo y salidas en el DXF **entregado** (bloques sin insertar) | 6 |
| **CAP-7** Carpintería (huecos y puertas) | `C10`, `C19`, `C05`, `C12` | Capas presentes, geometría en bloques sin insertar | INSERT + tipado de puerta/hueco | 7 |
| **CAP-8** Datos constructivos al fuego | `C01`, `C02`, `C03`, `C04`, `C05`, `C06`, `C21`, `C22`, `C23` | Ninguno | Fuera del alcance del formato DXF | **No planificable** |

---

## 11. Matriz de reglas

| Regla | Capacidad necesaria | ¿Implementable tras esa capacidad? | Resultado esperado |
|---|---|---|---|
| `C08` Ocupación | CAP-1 + CAP-2 (+ CAP-4 para el ámbito) | **Sí** | Fact publicable: "planta 3ª: 47 personas (DB-SI 3 §2, Tabla 2.1, 20 m²/pers.)". Sin juicio |
| `C01` Sectorización | CAP-4 (2.500 m²) + CAP-8 (EI 60) | **Parcial** | Límite de superficie evaluable; EI 60 `UNKNOWN`. Corregir cita SI-3 → SI-1 |
| `C02` Riesgo especial | Taxonomía de locales (parser) + CAP-8 | **Parcial** | Clasificación del grado de riesgo; Tabla 2.2 `UNKNOWN`. Sin rótulo ⇒ `UNKNOWN` |
| `C09` Recorridos | CAP-3 + CAP-6 + nº salidas + rociadores | **Sí, con 3 declaraciones** | Recorrido normativo real, con umbral 25/50/35 m elegido y +25 % si procede |
| `C10` Dimensionado | CAP-3 + CAP-7 | **Parcial** | Anchura de pasillo común contra P/200. **No aplica al pasillo interior** |
| `C11` Escaleras | CAP-5 + tipo de escalera (constructivo) | **No** | `UNKNOWN` + aviso condicional al superar 14 m |
| `C15` Discapacidad | CAP-5 + salidas accesibles + zonas de refugio | **No** | `UNKNOWN` + aviso condicional al acercarse a 28 m |
| `C16` Dotación PCI | CAP-3 + posiciones de equipos | **No** | `UNKNOWN`. El criterio de 15 m sería evaluable si se modelaran |
| `C18` Bomberos | Cartografía del entorno | **No** | `UNKNOWN`. No vincular a R25 |
| `C07`, `C14` | CAP-2 con usos secundarios | **No como regla** | `no_aplica` **con motivo**, nunca por silencio |
| `C03`-`C06`, `C12`, `C13`, `C19`-`C25` | CAP-8 / fuera de alcance | **No** | `aplica_no_evaluable` en el corpus. `C04` y `C13`: registrar la exención expresa |

---

## 12. Orden recomendado de implementación

Cuatro bloques. Cada uno deja el producto en un estado publicable y más honesto que el anterior — mismo criterio de secuencia que
`NORMATIVE_ENGINE.md` §14.

### Bloque 0 — Ingesta del Anejo SI A *(prerrequisito, coste bajo)*
Ingerir el Anejo de Terminología con el pipeline existente. Sin él, los bloques siguientes se apoyarían en memoria. **No es
capacidad nueva: es completar una ingesta ya iniciada.**

### Bloque A — Los tres Facts *(CAP-1 → CAP-2 → CAP-3)*
El único bloque enteramente interno: no depende de que cambie el DXF de entrada ni de que el arquitecto cambie de hábitos.

1. `CAP-1`: unificar las tres implementaciones de superficie útil en una función de composición con definición declarada.
2. `CAP-2`: añadir uso previsto como campo declarado; dejar de inferirlo de `tipologia`.
3. `CAP-3`: ocupación como Fact derivado, expuesta como dato, sin veredicto.

**Resultado observable:** ArchMuse publica por primera vez una magnitud del DB-SI calculada con su tabla real, y `C09`/`C10`/`C15`
pasan de silencio a `UNKNOWN` explicado.

### Bloque B — Las correcciones de veracidad *(no requieren capacidad nueva)*
Ejecutables en paralelo al Bloque A; son las 6 correcciones de `DB-SI_REVIEW.md` §3.2. Bug fixes, no capacidad nueva: exentas de PRD
según `CLAUDE.md`.

- `C01`: corregir `CTE-DB-SI-3` → DB-SI 1 §1 y reclasificar el solape de huellas como integridad geométrica.
- `C09`: retirar el veredicto de cumplimiento contra 25 m; unificar con la medición duplicada de `circulation.py` (D4).
- `C10`: documentar que DB-SI 3 §4 no respalda el ancho de pasillo interior.
- `C12`: atribuir los 0,80 m a SI 3 §4.
- `C20`, `C25`: corregir los dos defectos de los registros extraídos.

### Bloque C — Ámbito y altura *(CAP-4 → CAP-5)*
Modelo de planta y altura de evacuación. Habilita el límite de 2.500 m² de `C01` y los avisos condicionales de `C11`/`C15`/`C18`.
**`CAP-5` debe entregar `UNKNOWN` por defecto**; la estimación por `plantas × altura_libre` sólo como hipótesis marcada.

### Bloque D — Adquisición de datos *(CAP-6, CAP-7)* — **decisión de producto, no de ingeniería**
No debe abordarse como tarea técnica hasta responder una pregunta previa: **¿qué DXF va a recibir ArchMuse realmente?** El hallazgo
§1.1 sugiere que los planos reales pueden llegar con la arquitectura en bloques no insertados, en cuyo caso ninguna cantidad de
esfuerzo de parser resuelve nada. Antes de programar: inspeccionar una muestra de 5-10 DXF reales y comprobar si `ejemplo.dxf` es
representativo o excepcional.

---

## 13. Por qué el Bloque A va primero

Cuatro razones, en orden de peso:

1. **Es el único bloque que no depende de terceros.** Los bloques C y D dependen de que el arquitecto declare datos o de que el DXF
   llegue de otra forma. El A se puede completar sin salir del repositorio.
2. **Paga su coste aunque nada más se haga.** `CAP-1` elimina la triplicación de §1.2 y da definición declarada a tres reglas
   existentes (R03, R07, R14). Ese beneficio no depende de que DB-SI se reimplemente nunca.
3. **Convierte silencios en `UNKNOWN` explicados**, que es la promesa vendible de `NORMATIVE_ENGINE.md` §13: *"tu proyecto cumple las
   N reglas que tengo cargadas"* en lugar de *"tu proyecto cumple"*.
4. **`CAP-2` desarma un Bug #1 antes de que nazca.** Hoy la equivalencia plurifamiliar → Residencial Vivienda es correcta, así que
   nadie la nota. En el momento en que entre un proyecto con local comercial en planta baja, cinco tablas del DB-SI se indexarán mal
   en silencio. Declararlo cuesta un campo de formulario ahora y una auditoría entera después.

---

## 14. Riesgos y decisiones arquitectónicas

| # | Riesgo | Por qué es real aquí | Mitigación |
|---|---|---|---|
| 1 | **Inversión de la densidad de ocupación** | La Tabla 2.1 es m²/persona (divisor). Multiplicar da un error ×400 en residencial. El motor ya tiene el precedente exacto: `window_area_m2` en metros (H3) | Test de regresión con caso conocido; unidad en el nombre del Fact |
| 2 | **`CAP-3` sin `CAP-4`: ocupación por vivienda en vez de por planta** | La tabla dice "Plantas de vivienda". Agregar por vivienda es cómodo y no es lo que la norma indexa | No publicar ocupación sin ámbito explícito; vivienda sólo como agregado marcado |
| 3 | **`CAP-5` estimada presentada como hecho** | `plantas × altura_libre` ignora cantos de forjado; ~15 % de error sobre umbrales de 9/14/28 m | `UNKNOWN` por defecto; si se estima, Assumption visible (`DECISION_ENGINE.md` §11) |
| 4 | **Recaída en el proxy de huecos** | `C05` y `C19` piden huecos; ArchMuse "tiene" una superficie de hueco. Es la tentación mejor documentada del repositorio | Prohibición explícita en review y plan. No implementar hasta `CAP-7` real |
| 5 | **Ausencia interpretada como cumplimiento** | Sin trasteros rotulados ⇒ "no hay locales de riesgo especial". Es el fallo de R18c reencarnado | `UNKNOWN` obligatorio ante ausencia de rótulo (`INFERENCE_ENGINE.md` §2.2) |
| 6 | **Aritmética dentro de una regla** | Si la ocupación se calcula dentro de un check en vez de aguas arriba, nace el cuarto duplicado de superficie útil | Función de composición en catálogo compartido (`FACT_MODEL.md` §4) |
| 7 | **Un sexto patrón de evaluación** | Las tablas del DB-SI (1.1, 2.1, 3.1, 5.1) son matriciales y no encajan en los 5 patrones cerrados | Componer con `COMBINACION_LOGICA` o clasificar no evaluable. **Nunca ampliar el catálogo** (`CONSTRAINT_MODEL.md` §14) |
| 8 | **Sobre-inversión en `CAP-6`/`CAP-7`** | Son las que más reglas desbloquean y las que más fácil es empezar sin saber si el dato llegará | Bloque D gobernado por una muestra de DXF reales, no por el atractivo técnico |

### 14.1 Decisiones arquitectónicas que este plan fija

1. **La ocupación es un Fact, no una regla.** No tiene `passed`. Un Fact no se cumple ni se incumple.
2. **La aritmética vive aguas arriba de los Constraints.** Ninguna regla DB-SI contendrá una división por densidad, del mismo modo que
   ninguna contiene el mapeo ciudad→zona climática.
3. **El ámbito normativo manda sobre el ámbito cómodo.** Donde la norma dice planta, el Fact es de planta, aunque ArchMuse agrupe por
   vivienda.
4. **Toda condición de activación no medida produce `UNKNOWN`**, no `no_aplica`. `no_aplica` exige una razón positiva (la exención de
   Residencial Vivienda de `C13`, por ejemplo), nunca la ausencia de datos.
5. **Ningún dato declarado se sustituye por un valor por defecto en silencio.** Si el uso previsto no se declara y se asume
   Residencial Vivienda, esa asunción se escribe en la Evidence.
6. **`CAP-8` se declara frontera permanente, no deuda.** No es una tarea pendiente: es un límite del formato de entrada. Tratarlo como
   deuda invita a inventar proxies, que es cómo nació H3.

---

## 15. Cierre

`DB-SI_REVIEW.md` estableció que ArchMuse no puede afirmar que un edificio cumple el DB-SI. Este plan añade la parte constructiva:
**puede llegar a afirmar, con precisión, qué ha comprobado y qué no** — y el camino más corto hasta ahí no pasa por 12 parches, sino
por tres Facts que hoy no existen y por dejar de contradecir, en dos reglas, los avisos de "no evaluable" que el propio motor ya
emite correctamente.

La proporción sigue siendo incómoda: aun completadas las ocho capacidades, 7 reglas permanecen en `UNKNOWN` y 13 quedan descartadas.
Eso no es un fracaso del plan. Es el resultado de medir DB-SI —que regula sectores, materiales, estructura, instalaciones y accesos de
bomberos— contra un modelo compuesto por polígonos de estancia en planta. Lo que cambia tras este plan no es cuántas reglas se
cumplen: es que **ArchMuse sabrá decir cuáles no ha comprobado, y por qué**, en lugar de dejar que el silencio parezca un aprobado.

---

*Plan técnico. Ninguna línea de código escrita ni modificada. Ninguna regla creada. `evaluator.py` y `parser.py` intactos. Sin
commits. Las capacidades `CAP-2` a `CAP-8` son capacidad nueva de producto y requieren PRD previo conforme a `CLAUDE.md`; las 6
correcciones del Bloque B son arreglos sobre comportamiento existente y no lo requieren.*
