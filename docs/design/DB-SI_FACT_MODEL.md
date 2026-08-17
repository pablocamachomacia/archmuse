# DB-SI_FACT_MODEL.md — Contrato de hechos para CAP-1, CAP-2 y CAP-3

**Fecha:** 2026-08-08 · **Estado:** diseño, sin implementar · **Documentos de entrada:** `docs/audits/DB-SI_REVIEW.md`,
`docs/audits/DB-SI_IMPLEMENTATION_PLAN.md`
**Restricción cumplida:** cero cambios de código. `evaluator.py` y `parser.py` intactos. Ninguna regla creada. Sin commits.

**Qué es este documento:** el contrato de datos de los tres hechos del Bloque A. Define qué significa cada uno, de dónde sale, con qué
precisión, y qué pasa cuando no se puede saber.

**Qué NO es:** un rediseño del motor de evaluación (`docs/brain/CONSTRAINT_MODEL.md` ya lo hizo) ni una redefinición del modelo
general de Fact (`docs/brain/FACT_MODEL.md` ya lo hizo). Este documento **aplica** ambos a un caso concreto y pequeño, y su único
aporte propio es decidir dónde está la frontera entre lo que ArchMuse mide y lo que la norma nombra.

---

## 1. Principios del modelo de hechos

Siete principios. Los cinco primeros son herencia directa de la serie `docs/brain/`; los dos últimos son específicos de este
contrato y nacen de lo medido en §3.

**P1 — Un hecho se calcula una vez.** La aritmética vive en una función de composición compartida, aguas arriba de cualquier regla.
Ninguna regla contiene una suma de áreas, del mismo modo que ninguna contiene el mapeo ciudad→zona climática. (`FACT_MODEL.md` §4.)

**P2 — El nombre del hecho es una afirmación, y debe ser cierta.** Llamar `superficie_util` a una suma de polígonos no la convierte en
superficie útil normativa. Si lo que se mide es una aproximación geométrica, el nombre debe decirlo. Éste es el principio que gobierna
todo el §3 y la razón de que CAP-1 no se llame como se esperaba.

**P3 — Un hecho nunca emite juicio.** No tiene `passed`. La ocupación no se cumple ni se incumple.

**P4 — El estado de conocimiento es inseparable del valor.** Un consumidor no puede leer el número sin leer si es `KNOWN`,
`ESTIMATED` o `UNKNOWN`. No es un campo opcional de metadatos: es parte del contrato de lectura. (`FACT_MODEL.md` §10 — el fix
estructural del Bug #1.)

**P5 — La confianza es cualitativa y es el eslabón más débil.** Alta/Media/Baja, nunca un porcentaje. Un hecho derivado no puede
tener más confianza que su insumo más flojo. (`EVIDENCE_MODEL.md` §9.)

**P6 — Ante geometría incoherente, el hecho no se emite degradado: se emite `UNKNOWN`.** Un número plausible calculado sobre polígonos
solapados es peor que la ausencia de número, porque no se puede distinguir del correcto. Este principio existe por lo medido en §3.4.

**P7 — El ámbito lo fija la norma, no la comodidad.** Donde el DB-SI dice *planta*, el hecho es de planta, aunque ArchMuse agrupe por
vivienda.

---

## 2. Definiciones

### 2.1 Catálogo de hechos: ahora, después, nunca desde DXF

| Hecho | Grupo | Comentario |
|---|---|---|
| `superficie_recinto_dibujada` | **1. Ahora** | El hecho geométrico primitivo. Hoy es `Room.area_m2` |
| `superficie_suelo_agregada` | **1. Ahora** | Unión (no suma) de los recintos de un ámbito. Es lo que hoy se llama mal "superficie útil" |
| `uso_previsto` (por zona) | **3. Usuario** | No está en el DXF. Cinco tablas del DB-SI lo indexan |
| `ocupacion` | **1. Ahora** | Derivado de los dos anteriores |
| `tipologia_arquitectonica` | **1. Ahora** | Ya existe. **No es `uso_previsto`** (§4.1) |
| `superficie_util` | **2. Después** | Reservado. No emitir hasta tener definición declarada y base geométrica validada (§3.5) |
| `superficie_construida` | **2. Después** | **No obtenible del DXF actual** (§3.3). Necesario para el límite de 2.500 m² de `C01` |
| `planta` | **2. Después** | CAP-4. Ámbito normativo de la Tabla 2.1 |
| `altura_evacuacion` | **3. Usuario** | CAP-5. Estimarla por `plantas × altura_libre` es una hipótesis, no un hecho |
| `numero_salidas_planta` | **3. Usuario** | Decide si el límite de `C09` es 25 o 50 m |
| `instalacion_automatica_extincion` | **3. Usuario** | No es geométrico y no lo será. Decide el +25 % de la nota (1) |
| `resistencia_al_fuego` (EI/REI/R) | **Nunca desde DXF** | Frontera del formato (CAP-8) |

### 2.2 Tabla de fuentes

| Hecho | Fuente | Normativo | DXF | Usuario | Estado posible |
|---|---|---|---|---|---|
| `superficie_recinto_dibujada` | Polígono cerrado de la capa de áreas | No | **Sí** | No | `KNOWN` / `UNKNOWN` |
| `superficie_suelo_agregada` | Unión de recintos del ámbito | No | **Sí** | No | `KNOWN` / `UNKNOWN` |
| `tipologia_arquitectonica` | Formulario | No | No | **Sí** | `KNOWN` (tiene defecto declarado) |
| `uso_previsto` | Declaración por zona | **Sí** (define el eje de 5 tablas) | No | **Sí** | `KNOWN` / `ESTIMATED` / `UNKNOWN` |
| `densidad_ocupacion` | DB-SI 3 §2 Tabla 2.1 | **Sí** | No | No | `KNOWN` / `UNKNOWN` / `NO_APLICABLE` |
| `ocupacion` | Derivado | **Sí** (la fórmula es de la norma) | Indirecto | Indirecto | `KNOWN` / `ESTIMATED` / `UNKNOWN` |
| `superficie_util` | Reservado | **Sí** (pendiente de definición) | Parcial | Parcial | — |
| `superficie_construida` | **No disponible** | Sí | **No** | Posible | `UNKNOWN` |
| `planta` | Declaración o convención | Sí | Parcial | Sí | `KNOWN` / `UNKNOWN` |
| `altura_evacuacion` | Declaración | Sí | No | **Sí** | `KNOWN` / `ESTIMATED` / `UNKNOWN` |

---

## 3. CAP-1 — La superficie

Ésta es la sección larga, porque es donde el encargo pide no engañarse.

### 3.1 Qué mide hoy exactamente `evaluator.py`

Las tres implementaciones (`:452`, `:824`, `:1230`) son literalmente la misma expresión:

```python
useful_area = sum(
    r.area_m2 for r in unit.rooms
    if not (r.label and NON_USEFUL_PATTERN.search(_normalize(r.label)))   # NON_USEFUL_PATTERN = TERRAZA|TENDEDERO
)
```

Traducido sin eufemismos: **la suma aritmética de las áreas de los polígonos cerrados dibujados en la capa de áreas, cuya etiqueta de
texto más cercana no contiene "TERRAZA" ni "TENDEDERO".**

Cinco propiedades de esa magnitud que conviene tener delante antes de decidir cómo llamarla:

1. **Mide caras interiores.** En `ejemplo.dxf` los recintos se dibujan a cara interior de muro y **nunca se tocan** (huecos de
   0,03-0,38 m que representan el espesor del muro). El espesor de la tabiquería queda enteramente fuera.
2. **Depende de un rótulo de texto**, no de una propiedad del recinto. Un tendedero rotulado "Lavadero" computa como útil.
3. **Es una suma, no una unión.** Si dos polígonos se solapan, los metros compartidos se cuentan dos veces (§3.4).
4. **La exclusión terraza/tendedero es criterio de ArchMuse.** Es defendible, pero no procede de ninguna norma citada.
5. **No hay comprobación de altura libre.** Cualquier definición normativa de superficie útil descuenta las zonas con altura inferior
   a un mínimo; el modelo no tiene sección vertical.

### 3.2 Qué mide `Unit.total_area_m2` — el hallazgo colateral

`total_area_m2` es `sum(r.area_m2 for r in self.rooms)`: **los mismos polígonos, sin excluir nada**.

Es decir, el "total" contra el que R03 calcula el ratio útil/total **no es superficie construida**. Es superficie de recinto más
terrazas y tendederos. La diferencia entre "útil" y "total" en el motor actual **es exactamente las terrazas y los tendederos, y nada
más** — no incluye muros, ni tabiquería, ni zonas comunes.

Consecuencia medida en `ejemplo.dxf`: las cuatro viviendas sin anomalía geométrica dan ratios del 84-88 %, y VT6/2 baja al 69 % porque
tiene 28 m² de terrazas. El umbral del 80 % de `MIN_USEFUL_RATIO` está, en la práctica, midiendo **cuánta terraza tiene la vivienda**,
no su eficiencia constructiva. R03 no forma parte del Bloque A y este documento no propone tocarla, pero la observación pertenece al
contrato: **`superficie_construida` no existe hoy en ningún flujo**, y cualquier hecho futuro que la necesite (el límite de 2.500 m²
de `C01`) parte de cero, no de `total_area_m2`.

### 3.3 Por qué la superficie construida no es obtenible del DXF actual

Superficie construida incluye el espesor de cerramientos y la parte proporcional de elementos comunes. El DXF entrega recintos a cara
interior: **la geometría de los muros está fuera de los polígonos leídos**, en capas (`00 MURO`) cuya geometría, en `ejemplo.dxf`, vive
en bloques no insertados (hallazgo §1.1 de `DB-SI_IMPLEMENTATION_PLAN.md`).

Reconstruirla desde la envolvente de los recintos no funciona: se midió el casco convexo por vivienda y da errores del −24 % al +49 %
según la forma en planta. **No es una aproximación con margen: es ruido.** `superficie_construida` queda en el grupo 2, sin fuente
disponible, y su estado por defecto es `UNKNOWN`.

### 3.4 El problema que obliga al principio P6: los polígonos se solapan

Medido sobre `ejemplo.dxf` para este documento, comparando suma contra unión por vivienda:

| Vivienda | Σ áreas | Área de la unión | Metros contados dos veces |
|---|---|---|---|
| VT1/3 | 44,43 | 44,43 | 0,00 |
| VT2/2 | 58,44 | 58,44 | 0,00 |
| VT3/3 | 55,05 | 55,05 | 0,00 |
| VT4/2 | 54,36 | 54,36 | 0,00 |
| **VT5/1** | 68,49 | 56,06 | **12,43 (22 %)** |
| **VT6/2** | 103,76 | 76,44 | **27,32 (36 %)** |

El motor **ya sabe esto**: `evaluate_room_overlap` (`evaluator.py:3075`) lo detecta, con estas mismas cifras anotadas en su comentario
de cabecera (`:3038-3040`), y su docstring lo explica con precisión — un contorno agrupador conservado por
`_discard_container_candidates` entra como si fuera una habitación más. El propio comentario dice: *«ESTO DETECTA, NO CURA»*.

Y ahí está el problema de contrato. Hoy conviven, en el mismo informe, una incidencia que dice *«las superficies de esta vivienda
están contadas más de una vez»* y un conjunto de reglas que siguen consumiendo esas superficies como si fueran válidas. La incidencia
avisa; el número sigue circulando. **Ese acoplamiento es exactamente lo que un contrato de hechos debe romper**: si la geometría no es
coherente, el hecho no vale, y quien lo lea debe enterarse por el propio hecho, no por una incidencia que viaja aparte.

De ahí P6: `superficie_suelo_agregada` **no se emite degradada; se emite `UNKNOWN`** cuando hay solape por encima de tolerancia.

### 3.5 Decisión de CAP-1: tres hechos, y `superficie_util` no es ninguno de ellos

**Decisión: no se emite ningún hecho llamado `superficie_util` en el Bloque A.**

El encargo pedía decidir esto explícitamente, y la respuesta es que la magnitud actual no puede llevar ese nombre. Le faltan tres
cosas para merecerlo: una definición normativa declarada de referencia, la comprobación de altura libre, y una base geométrica libre
de solapes. Ponerle el nombre sería precisamente el error de P2 — y tendría una consecuencia práctica desagradable, porque la Tabla 2.1
del DB-SI indexa *"en función de la superficie útil de cada zona"*: bautizar el proxy sería introducir la aproximación en la cadena de
cálculo de una magnitud de seguridad contra incendios por la puerta de atrás.

En su lugar, tres hechos con nombres que dicen la verdad:

| Hecho | Qué es exactamente | Ámbito |
|---|---|---|
| **`superficie_recinto_dibujada`** | Área del polígono cerrado que representa el recinto, en m², tal como está dibujado | Recinto (pieza) |
| **`superficie_suelo_agregada`** | Área de la **unión geométrica** de los recintos de un ámbito, con el criterio de inclusión declarado | Vivienda / planta |
| **`superficie_util`** | **Reservado.** No se emite hasta cerrar §12.1 | — |

Diferencias con lo actual, que son el contenido real de CAP-1:

1. **Unión, no suma.** Elimina el doble cómputo por construcción.
2. **Criterio de inclusión declarado y adjunto al valor**, en vez de un regex incrustado en tres sitios: qué se excluyó, por qué
   regla, y que ese criterio es de ArchMuse y no de una norma.
3. **Un solo punto de cálculo**, consumido por R03, R07, R14 y CAP-3.
4. **Estado explícito**, con `UNKNOWN` ante geometría incoherente.

**Qué geometría la origina:** polígonos cerrados de la capa de áreas resuelta por `parser.elegir_capa`, ya convertidos a metros por
`leer_plano` (que se niega a continuar si no puede determinar la escala — `EscalaIndeterminada`). Es la única de las tres capacidades
cuya unidad está blindada aguas arriba.

**Qué se excluye:** recintos cuya etiqueta case el criterio declarado (hoy `TERRAZA|TENDEDERO`). **La exclusión se declara junto al
valor, no se aplica en silencio.**

**Qué precisión tiene:** la del dibujo. No hay tolerancia normativa asociada; sí un umbral de ruido geométrico. Un valor con 2
decimales sugiere una precisión que el origen no garantiza — **redondear a 0,1 m² en presentación** y conservar la precisión completa
internamente.

**Cómo se expresa la incertidumbre:** por estado (§6) y confianza (§7), nunca por un margen numérico. Un "±5 %" sería precisión
fabricada, el error que `TIPOLOGIA_BENCHMARKS` ya costó una vez.

**Qué ocurre si el DXF no permite determinarla con fiabilidad:** §8.

---

## 4. CAP-2 — El uso

### 4.1 Tipología arquitectónica ≠ uso previsto

Son dos ejes distintos y hoy están fusionados de hecho, aunque nadie lo haya decidido.

| | `tipologia_arquitectonica` | `uso_previsto` |
|---|---|---|
| Valores | plurifamiliar, unifamiliar, rehabilitacion | Residencial Vivienda, Residencial Público, Administrativo, Comercial, Docente, Hospitalario, Pública Concurrencia, Aparcamiento, Almacén |
| Qué describe | El tipo de encargo y su escala | La clave de entrada de las tablas del DB-SI |
| Quién lo usa | `UMBRALES_TIPOLOGIA` (umbrales propios de ArchMuse) | Tablas 1.1, 2.1, 3.1, 5.1 de SI 3 y 1.1 de SI 4 |
| Origen | Formulario | **No existe hoy** |
| Tiene defecto | Sí (`DEFAULT_TIPOLOGIA = "plurifamiliar"`) | **No debe tenerlo** |

"Rehabilitación" ilustra por qué no son el mismo eje: es un tipo de intervención, y no dice absolutamente nada sobre el uso previsto —
se puede rehabilitar un edificio residencial, uno administrativo o uno hospitalario. Ninguna tabla del DB-SI sabe qué hacer con él.

La equivalencia *plurifamiliar → Residencial Vivienda* es hoy correcta y por eso nadie la nota. El problema es que está implícita: el
día que entre un proyecto con local comercial en planta baja, cinco tablas se indexarán mal en silencio. Declararlo cuesta un campo
ahora; no declararlo cuesta una auditoría después.

### 4.2 ¿Un uso por planta, o varias zonas con usos distintos?

**Decisión: `planta → múltiples zonas, cada una con su uso previsto`.** No por generalidad abstracta: porque el modelo de un solo uso
por planta hace literalmente inexpresables tres exigencias del texto ingerido.

**Evidencia 1 — Tabla 1.1, condición "En general" (segmento 1):**

> *«Toda zona cuyo uso previsto sea diferente y subsidiario del principal del edificio o establecimiento en el que esté integrada debe
> constituir un sector de incendio diferente cuando supere los siguientes límites […] Zona de uso Aparcamiento cuya superficie
> construida exceda de 100 m².»*

El artículo **está construido sobre la existencia de zonas con uso distinto dentro de un mismo edificio**. Con un uso por planta, la
regla no tiene sujeto sobre el que operar.

**Evidencia 2 — Tabla 2.1 (segmento 8):** *«en función de la superficie útil de cada zona»*, y la tabla asigna densidades distintas a
zonas distintas del mismo uso previsto (en Residencial Público: alojamiento 20, salones de uso múltiple 1, vestíbulos generales 2).
**La zona, no la planta, es el ámbito de la densidad.**

**Evidencia 3 — SI 3 §1 (segmento 7):** regula precisamente los establecimientos de un uso *«integrados en un edificio cuyo uso
previsto principal sea distinto del suyo»*. Es un artículo entero cuyo supuesto de hecho es la coexistencia de usos.

**Diseño resultante:**

```
edificio
  └── uso_previsto_principal            (1, obligatorio)
       └── planta                        (CAP-4)
            └── zona                     (1..n)
                 ├── uso_previsto        (heredado del principal, o declarado distinto)
                 ├── recintos            (los Room que la componen)
                 └── es_subsidiaria      (relevante para Tabla 1.1)
```

Tres reglas del modelo:

1. **`uso_previsto_principal` del edificio es obligatorio y sin defecto.** Si no se declara, `UNKNOWN`, y todo lo que dependa de él
   hereda `UNKNOWN`.
2. **Una zona sin uso declarado hereda el principal**, y esa herencia se registra en la procedencia como tal. No es lo mismo un uso
   declarado que uno heredado, aunque el valor coincida.
3. **La ausencia de zonas de otro uso NO demuestra que no las haya.** Es el punto que `C07` y `C14` necesitan: sin declaración
   explícita del arquitecto de que no existen usos secundarios, el estado es `UNKNOWN`, no "no hay". Es la aplicación literal de
   `INFERENCE_ENGINE.md` §2.2: absence of evidence ≠ evidence of absence.

**Nota de alcance:** el modelo de zonas se **diseña** ahora y se **implementa** con el mínimo viable — una zona por vivienda,
heredando el uso principal — porque sin CAP-4 no hay planta a la que colgarlas. Lo que importa es que el hueco esté previsto y que
nadie tenga que romper el contrato para meter la segunda zona.

### 4.3 Sobre "zona de ocupación nula"

La Tabla 2.1 incluye el valor **"Ocupación nula"** para zonas de ocupación ocasional accesibles sólo a efectos de mantenimiento (salas
de máquinas, locales de limpieza). Y SI 3 §9 (segmento 15) condiciona su exigencia a las plantas *«que no sean zona de ocupación
nula»*.

Es decir: **"ocupación nula" es una categoría de la tabla, no el número 0.** Si se modela como `0.0`, se pierde la distinción entre
"zona que la norma declara de ocupación nula" y "zona cuya ocupación no se ha podido calcular", y `C15` deja de poder decidir. En el
contrato es un estado propio: `NO_APLICABLE` (§6).

---

## 5. CAP-3 — La ocupación

### 5.1 La cadena completa

```
superficie_suelo_agregada(zona)  [m²]        ← CAP-1, estado KNOWN
                │
                ├── uso_previsto(zona)                      ← CAP-2, estado KNOWN
                │        │
                │        ▼
                │   densidad_ocupacion(uso, tipo de zona)    ← DB-SI 3 §2, Tabla 2.1  [m²/persona]
                │        │
                ▼        ▼
        ocupacion(zona) = superficie / densidad   → redondeo → [personas]
```

**Tabla normativa que proporciona la densidad:** DB-SI, Sección SI 3, apartado 2, **Tabla 2.1 "Densidades de ocupación"**. Verificada
literalmente en el corpus ingerido (`codigotecnico__DB-SI__0a2e78cd6247.jsonl`, registro 8). Valor aplicable al caso de ArchMuse:

> Residencial Vivienda · **Plantas de vivienda · 20 m²/persona**

**Unidad: m²/persona. Es un divisor.** Se dice explícitamente porque es la inversión mental fácil y produce un error de ×400 en el
caso residencial, y porque el motor ya tiene un precedente exacto de error dimensional silencioso: `window_area_m2 = long_side × 0.25`
(`evaluator.py:1253`), metros presentados como m², responsable del 41 % de las incidencias del proyecto de ejemplo. El resultado de
CAP-3 es **personas**: magnitud adimensional y entera.

### 5.2 Redondeo y ocupación fraccionaria — **decisión abierta, marcada como tal**

**El segmento ingerido no establece ninguna regla de redondeo.** No la hay en el texto de SI 3 §2 ni en la Tabla 2.1. Por tanto este
documento **no puede afirmar** cuál es la regla normativa.

Lo que sí puede hacer es proponer un criterio y etiquetarlo honestamente:

| | |
|---|---|
| **Propuesta** | Redondeo **por exceso** al entero superior (`ceil`) |
| **Naturaleza** | **INFERENCIA TÉCNICA**, no NORMA CONFIRMADA |
| **Razonamiento** | Las personas son enteras; en materia de evacuación el sentido conservador es sobreestimar la ocupación, nunca subestimarla. Una ocupación redondeada a la baja produce medios de evacuación infradimensionados |
| **Riesgo** | Los umbrales de la Tabla 3.1 (100, 500, 50 personas) son de igualdad estricta; en el borde, el redondeo cambia el resultado |
| **Cómo debe presentarse** | El valor fraccionario se **conserva internamente**; el entero es una presentación. La Evidence registra ambos y que el redondeo es criterio nuestro |
| **Cierre** | §12.2 — requiere validación de arquitecto colegiado antes de implementarse |

Que este punto quede abierto no bloquea el Bloque A: la ocupación se publica como dato con su fraccionario visible, y la regla de
redondeo sólo se vuelve crítica cuando `C09`/`C10` la comparen contra un umbral — que es Bloque C/D.

### 5.3 Las tres excepciones del propio texto

El apartado 2 contiene tres salvedades que no son opcionales:

1. *«salvo cuando sea previsible una ocupación mayor»* → el arquitecto puede declarar una ocupación superior, que **prevalece**. Es una
   entrada del usuario, no un cálculo.
2. *«o bien cuando sea exigible una ocupación menor en aplicación de alguna disposición legal»* → **excepción sujeta a justificación
   humana** (`CONSTRAINT_MODEL.md` §5). El motor la expone como disponible; **nunca la aplica solo**.
3. *«En aquellos recintos o zonas no incluidos en la tabla se deben aplicar los valores correspondientes a los que sean más
   asimilables»* → **criterio profesional puro**. Un uso no presente en la tabla produce `UNKNOWN`, jamás una asimilación automática.

Y la nota (1) obliga a considerar utilizaciones especiales o circunstanciales que aumenten la ocupación. También declaración, no
cálculo.

### 5.4 Qué ocurre si falta un insumo

| Situación | Estado de `ocupacion` | Por qué |
|---|---|---|
| Superficie `KNOWN` + uso `KNOWN` + densidad en tabla | `KNOWN` | Caso nominal |
| Falta el **uso** (no declarado) | **`UNKNOWN`** | Sin uso no hay fila de tabla. No se asume Residencial Vivienda |
| Uso **heredado** del principal, no declarado en la zona | `ESTIMATED` | Herencia registrada en procedencia |
| Falta la **superficie** (`UNKNOWN` por solape, §3.4) | **`UNKNOWN`** | P6: propaga, no degrada |
| Uso declarado **no presente en la tabla** | **`UNKNOWN`** | "Más asimilable" es criterio profesional (§5.3) |
| Zona de mantenimiento / ocupación nula | **`NO_APLICABLE`** | Categoría de la tabla, distinta de 0 (§4.3) |
| El arquitecto declara una ocupación mayor | `KNOWN`, origen declarado | Prevalece sobre el cálculo (§5.3) |

**Regla de propagación, sin excepciones:** un insumo `UNKNOWN` produce un derivado `UNKNOWN`. Nunca un valor "aproximado mientras
tanto". Es la diferencia entre un sistema que no sabe y un sistema que no sabe que no sabe.

---

## 6. Estados de conocimiento

Cuatro estados. Nunca silencio, nunca `None` desnudo. (Contrato de lectura de `FACT_MODEL.md` §10.)

| Estado | Significado | Consumo permitido |
|---|---|---|
| **`KNOWN`** | Valor medido o declarado, con base suficiente | Sí, con su confianza |
| **`ESTIMATED`** | Valor obtenido por hipótesis explícita (herencia de uso, futura estimación de altura) | Sí, **la hipótesis viaja con él** y debe ser visible al arquitecto |
| **`UNKNOWN`** | No se ha podido determinar. **Lleva motivo obligatorio** | **No.** El consumidor propaga `UNKNOWN` |
| **`NO_APLICABLE`** | La pregunta no tiene sentido en este ámbito (p. ej. ocupación nula) | Sí, como respuesta legítima |

El cuarto estado no es decorativo: sin él, `C15` no puede distinguir "planta de ocupación nula" (donde la norma la exime) de "planta
cuya ocupación no sé calcular" (donde no puede afirmar nada). Con miles de reglas y ámbitos, sin `NO_APLICABLE` los `UNKNOWN`
legítimos quedarían ahogados en ruido.

**`ESTIMATED` no es un `KNOWN` con asterisco.** Un hecho `ESTIMATED` nunca puede sostener una afirmación de cumplimiento normativo por
sí solo. Puede sostener un aviso.

---

## 7. Procedencia y confianza

### 7.1 Esquema conceptual del hecho

Propuesta de contrato. **No es un esquema de implementación** — sin tipos de lenguaje, sin decisiones de almacenamiento.

| Campo | Contenido | Nota |
|---|---|---|
| `nombre` | Identificador estable del concepto | Namespacing de `NORMATIVE_ENGINE.md` §5.2 |
| `ambito` | A qué se refiere: recinto / vivienda / zona / planta / edificio | Dimensión física; P7 |
| `tipo` | `observado` \| `derivado` \| `declarado` \| `normativo` | Eje de origen epistémico de `FACT_MODEL.md` §2.1 |
| `valor` | El número o categoría | — |
| `unidad` | `m²`, `m²/persona`, `personas`, `—` | **Obligatoria y explícita.** §5.1 |
| `estado` | `KNOWN` \| `ESTIMATED` \| `UNKNOWN` \| `NO_APLICABLE` | §6. Inseparable del valor (P4) |
| `motivo_estado` | Obligatorio si no es `KNOWN` | Es lo que se le enseña al arquitecto |
| `fuente` | De dónde sale: capa DXF, formulario, tabla normativa | — |
| `procedencia` | Cadena de insumos y función de composición aplicada | Permite reconstruir el número |
| `referencia_normativa` | Localizador jerárquico, si aplica | `DB-SI / SI 3 / ap. 2 / Tabla 2.1` |
| `criterio_declarado` | La definición usada, cuando el hecho depende de una | **El campo que impide repetir el error de P2** |
| `confianza` | `Alta` \| `Media` \| `Baja` | Cualitativa. Nunca porcentaje |
| `explicacion` | Frase en lenguaje llano | Lo que se muestra en la ficha |

### 7.2 Cómo se asigna la confianza

Derivada, nunca escrita a mano (`EVIDENCE_MODEL.md` §9):

| Origen del hecho | Techo de confianza |
|---|---|
| Medido sobre geometría coherente del DXF | **Alta** |
| Declarado por el arquitecto | **Alta** |
| Valor de tabla normativa verificado contra texto ingerido | **Alta** |
| Derivado | **El mínimo de sus insumos** |
| Heredado / estimado (`ESTIMATED`) | **Media**, nunca más |
| Apoyado en un criterio propio no normativo | **Media**, nunca más |

Aplicación a los tres hechos del Bloque A:

- `superficie_suelo_agregada` con exclusión terraza/tendedero → **Media**, porque el criterio de exclusión es de ArchMuse. Esto es
  importante: significa que ninguna regla que la consuma puede presentarse como comprobación normativa de confianza Alta hasta que
  §12.1 se cierre.
- `densidad_ocupacion` (20 m²/persona, uso declarado) → **Alta**.
- `ocupacion` → **Media**, por eslabón más débil. Correcto y honesto: la ocupación es tan buena como la superficie de la que sale.

---

## 8. Casos UNKNOWN

Catálogo cerrado para el Bloque A. Cada entrada define su motivo, porque el motivo es el producto.

| # | Situación | Hecho afectado | Motivo mostrado |
|---|---|---|---|
| U1 | Solape entre recintos > tolerancia | `superficie_suelo_agregada` | *"Las piezas de esta vivienda se solapan N m²: la superficie no puede determinarse sin contar metros dos veces"* |
| U2 | Escala del dibujo indeterminada | Todos los geométricos | Ya resuelto aguas arriba por `EscalaIndeterminada` — el análisis no llega a empezar |
| U3 | Capa de áreas no determinable | Todos los geométricos | Ya resuelto por `CapaIndeterminada` |
| U4 | Recinto sin etiqueta | `superficie_recinto_dibujada` es `KNOWN`; la clasificación no | *"Pieza sin rótulo: no se puede saber si computa"* |
| U5 | Uso previsto no declarado | `uso_previsto`, y en cascada `ocupacion` | *"No consta el uso previsto del edificio"* |
| U6 | Uso declarado ausente de la Tabla 2.1 | `densidad_ocupacion` | *"El uso declarado no figura en la Tabla 2.1; la asimilación a otro uso requiere criterio del técnico"* |
| U7 | Existencia de usos secundarios no declarada | `uso_previsto` de zonas | *"No consta si el edificio tiene locales o aparcamiento"* — **nunca "no los tiene"** |
| U8 | Superficie agregada `UNKNOWN` | `ocupacion` | Propagación de U1 |

**U1 es el caso que cambia el comportamiento actual**, y conviene ser explícito sobre su efecto: hoy VT5/1 y VT6/2 producen números de
superficie que alimentan puntuación e incidencias mientras una incidencia paralela avisa de que están mal. Con este contrato, esas dos
viviendas dejarían de producir superficie agregada y ocupación, y dirían por qué.

Eso es un cambio visible y probablemente incómodo: **dos de las seis viviendas del proyecto de ejemplo pasarían de tener números a no
tenerlos.** Se documenta aquí, antes de aprobar, porque es el tipo de consecuencia que no debe descubrirse durante la implementación.
La alternativa —seguir publicando números que el propio motor sabe erróneos— es peor, pero la decisión es de Pablo (§12.3).

---

## 9. Dependencias

```
parser.leer_plano  (escala y capa ya resueltas, o el análisis no arranca)
        │
        ▼
superficie_recinto_dibujada  ──┐
        │                      │
        ▼                      │
[comprobación de solape]  ─────┤  U1 ⇒ UNKNOWN
        │                      │
        ▼                      │
superficie_suelo_agregada  ◄───┘
        │
        │        formulario ──► uso_previsto ──► densidad_ocupacion (Tabla 2.1)
        │                            │                    │
        └────────────┬───────────────┴────────────────────┘
                     ▼
                 ocupacion
                     │
     ┌───────────────┼──────────────┬──────────────┐
     ▼               ▼              ▼              ▼
   C09*            C10*           C15*           C16*
                                          (*) todas bloqueadas
                                          además por CAP-5/6/7
```

**Consumidores existentes que pasan a leer el hecho en vez de recalcularlo:** R03 (`:452`), R07 (`:824`), R14 (`:1230`).

**Dependencia con CAP-4 (planta):** la Tabla 2.1 indexa "Plantas de vivienda". Sin CAP-4 el ámbito correcto no existe. **Decisión:** en
el Bloque A la ocupación se emite con ámbito **vivienda**, marcada explícitamente como agregado no normativo, y el ámbito planta se
añade con CAP-4 sin romper el contrato. Se prefiere un ámbito declarado como provisional a un ámbito silenciosamente equivocado.

---

## 10. Ejemplos de datos

Ilustrativos del contrato, no un formato de serialización.

**E1 — Caso nominal (VT3/3, geometría coherente)**

```
nombre:               superficie_suelo_agregada
ambito:               vivienda VT3/3
tipo:                 derivado
valor:                47.6
unidad:               m²
estado:               KNOWN
fuente:               capa "00 areas" del DXF
procedencia:          unión geométrica de 5 recintos; excluidos 1 (Terraza)
criterio_declarado:   "excluye recintos rotulados Terraza o Tendedero
                       — criterio de ArchMuse, no definición normativa"
confianza:            Media          ← techo por criterio propio
explicacion:          "47,6 m² de suelo, sin contar terraza ni tendedero."
```

**E2 — Ocupación derivada de E1**

```
nombre:               ocupacion
ambito:               vivienda VT3/3  (agregado no normativo; el ámbito de
                                       la Tabla 2.1 es la planta)
tipo:                 derivado
valor:                2.38  → presentado como 3
unidad:               personas
estado:               KNOWN
referencia_normativa: DB-SI / SI 3 / ap. 2 / Tabla 2.1
procedencia:          47.6 m² ÷ 20 m²/persona (Residencial Vivienda,
                       "Plantas de vivienda")
confianza:            Media          ← eslabón más débil (E1)
explicacion:          "Ocupación estimada 3 personas, según la densidad de
                       20 m²/persona de la Tabla 2.1 del DB-SI."
```

**E3 — U1: geometría incoherente (VT6/2)**

```
nombre:               superficie_suelo_agregada
ambito:               vivienda VT6/2
estado:               UNKNOWN
motivo_estado:        "Las piezas se solapan 27,32 m² (36% de la vivienda):
                       'Salón/cocina' contiene a las 4 terrazas. La superficie
                       no puede determinarse sin contar metros dos veces."
valor:                —              ← no se emite un número degradado (P6)
confianza:            —
```

**E4 — U5: uso no declarado**

```
nombre:               ocupacion
ambito:               vivienda VT3/3
estado:               UNKNOWN
motivo_estado:        "No consta el uso previsto del edificio. La Tabla 2.1
                       asigna densidades por uso; sin él no hay fila aplicable."
procedencia:          superficie_suelo_agregada = KNOWN (47.6 m²);
                       uso_previsto = UNKNOWN
```

Obsérvese E4: la superficie está bien y aun así la ocupación es `UNKNOWN`. **No se asume Residencial Vivienda por ser el caso
habitual.** Es exactamente el reflejo inverso del Bug #1.

---

## 11. Migración conceptual desde `evaluator.py`

| Hecho actual | Dónde se calcula | ¿Debe convertirse en hecho? | Nuevo nombre |
|---|---|---|---|
| Suma de áreas excluyendo Terraza/Tendedero | `:452` (R03), `:824` (R07), `:1230` (R14) | **Sí — es CAP-1** | `superficie_suelo_agregada` (unión, criterio declarado) |
| `Unit.total_area_m2` (suma de todos los recintos) | `parser`/`evaluator`, propiedad de `Unit` | **Sí, renombrado** — no es superficie construida (§3.2) | `superficie_suelo_agregada` con criterio de inclusión "todos" |
| `Room.area_m2` | `parser.py:59` | **Sí** — es el primitivo | `superficie_recinto_dibujada` |
| Área de pasillo | `:1224` (R14) | Sí, mismo patrón | `superficie_suelo_agregada` con criterio "sólo circulación" |
| `NON_USEFUL_PATTERN` | `:424` | **No es un hecho: es un criterio** | Pasa a `criterio_declarado` del hecho |
| Solape entre piezas | `evaluate_room_overlap:3075` | **No como hecho** — pasa a ser **condición de estado** de CAP-1 (§3.4) | Se conserva la detección; cambia su efecto |
| `tipologia` | formulario, `UMBRALES_TIPOLOGIA` | Ya es un hecho declarado | `tipologia_arquitectonica` (sin cambios) |
| — (no existe) | — | **Sí, nuevo** | `uso_previsto` |
| — (no existe) | — | **Sí, nuevo** | `ocupacion` |
| — (no obtenible, §3.3) | — | Reservado | `superficie_construida` |

**Sobre `evaluate_room_overlap`:** no desaparece ni se duplica. Su cálculo se convierte en la comprobación previa que decide el estado
de `superficie_suelo_agregada`. Lo que cambia no es la detección —que ya funciona— sino que su resultado deje de viajar en paralelo al
número que invalida.

**Orden conceptual de la migración**, cada paso publicable por separado:

1. Extraer el cálculo a una función de composición única, **conservando la semántica actual** (suma, mismo regex). Cambio interno
   puro: R03/R07/R14 dan exactamente los mismos números. Verificable con un test de equivalencia sobre `ejemplo.dxf`.
2. Cambiar suma → unión. **Aquí cambian números** en VT5/1 y VT6/2. Cambio de comportamiento, medible y explicable.
3. Añadir estado y `UNKNOWN` por solape (U1). Aquí es donde esas dos viviendas dejan de tener número (§8, §12.3).
4. Añadir `uso_previsto` como campo declarado.
5. Añadir `ocupacion` como hecho derivado, expuesto sin juicio.

El paso 1 es el que hace desaparecer conceptualmente la triplicación que motivó este encargo, y no cambia ni un decimal — buen sitio
para empezar.

---

## 12. Decisiones abiertas

Cinco. Las tres primeras deben cerrarse antes de implementar; las dos últimas pueden esperar.

### 12.1 ¿Contra qué definición se mide la superficie? — **bloqueante**

`superficie_util` queda reservado hasta que exista una definición declarada de referencia. Las opciones no son equivalentes y la
elección **no es técnica**:

| Opción | Consecuencia |
|---|---|
| (a) Definición del decreto autonómico de habitabilidad aplicable | Correcta para R07 (superficie mínima de vivienda, materia autonómica), pero introduce el eje CCAA que hoy no existe (`NORMATIVE_AUDIT.md` §5.3) |
| (b) Definición usada por el DB-SI para la Tabla 2.1 | Correcta para CAP-3. **Requiere verificar si el Anejo SI A la define** (§13) |
| (c) Mantener el criterio propio, declarado como tal | Honesto y disponible hoy. Techo de confianza Media permanente |

**Recomendación:** (c) para el Bloque A, con (b) verificado en el Bloque 0. No bloquea CAP-3 si el hecho no se llama `superficie_util`
— que es precisamente por lo que §3.5 decidió no llamarlo así.

### 12.2 Regla de redondeo de la ocupación — **bloqueante para Bloque C**

§5.2. El texto ingerido no la establece. La propuesta (`ceil`) es inferencia técnica y **requiere validación de arquitecto
colegiado** (regla de dos personas, `NORMATIVE_ENGINE.md` §12). No bloquea el Bloque A porque el fraccionario se conserva.

### 12.3 ¿Qué se muestra cuando una vivienda pasa a `UNKNOWN` por solape? — **bloqueante, decisión de producto**

Con este contrato, VT5/1 y VT6/2 de `ejemplo.dxf` dejarían de tener superficie y ocupación. Tres caminos:

| Opción | Valoración |
|---|---|
| (a) `UNKNOWN` con motivo, sin número | **Recomendada.** Coherente con P6 y con el aviso que el motor ya emite |
| (b) Publicar la unión y avisar del solape | Tentador, pero la unión tampoco es correcta: no se sabe cuál de los dos polígonos es la pieza real |
| (c) Arreglar el parser primero | Es la cura, no el contrato. Y cambia las superficies de todos los proyectos ya guardados — el propio comentario de `evaluate_room_overlap:3042` lo señala como decisión aparte |

(b) merece un matiz que conviene no perder: la unión elimina el doble cómputo pero no resuelve la ambigüedad de fondo. Si "Salón/cocina"
contiene a las terrazas, no sabemos si el salón mide 58 m² o si ese polígono es un contorno agrupador y el salón real es otro. La unión
da un número plausible sobre una interpretación no verificada.

### 12.4 Granularidad de zona en la primera implementación — no bloqueante

§4.2 decide el modelo (varias zonas por planta) pero la primera implementación tendrá una zona por vivienda. Confirmar que el hueco
queda previsto y que añadir la segunda zona no rompa el contrato.

### 12.5 ¿La ocupación se muestra al arquitecto desde el primer día? — no bloqueante

Argumento a favor: es la primera magnitud del DB-SI calculada con su tabla real. En contra: es un dato sin juicio, y la interfaz hoy
está organizada por incidencias. Podría vivir primero como campo del JSON y aparecer en interfaz con el Bloque C.

---

## 13. Anejo SI A: qué hace falta para CAP-1/2/3

**El Anejo SI A (Terminología) no está ingerido** — el corpus cubre SI 1 a SI 6 (31 segmentos → 25 candidatas). Este documento **no
inventa ninguna definición**: lista qué términos hay que ir a buscar y para qué se necesita cada uno.

### 13.1 Necesarias para el Bloque A

| Término | Para qué | Criticidad |
|---|---|---|
| **Uso previsto** | Fijar el catálogo cerrado de valores de CAP-2 y su criterio de asignación | **Alta** — sin él, los valores de `uso_previsto` los estaríamos eligiendo nosotros |
| **Ocupación** | Confirmar que la magnitud de CAP-3 es la que el DB-SI llama así | **Alta** |
| **Zona de ocupación nula** | Distinguir `NO_APLICABLE` de 0 (§4.3) | Media — la Tabla 2.1 y SI 3 §9 la usan pero no la definen |
| **Superficie útil** | Cerrar §12.1 opción (b). **Verificar primero si el Anejo la define o remite a otra fuente** | Media — condiciona si `superficie_util` puede existir algún día |
| **Superficie construida** | Confirmar el ámbito del límite de 2.500 m² (`C01`) | Baja para el Bloque A |

Un matiz de honestidad sobre "superficie útil": aparece **una sola vez** en todo el corpus DB-SI ingerido — en el propio apartado 2 de
SI 3 (segmento 8), usada pero no definida. Es perfectamente posible que el DB-SI no la defina y remita a otra norma. **Este documento
no lo afirma ni lo niega**; es lo primero que el Bloque 0 debe resolver, y de la respuesta depende §12.1.

### 13.2 Necesarias para capacidades futuras

| Término | Capacidad / regla | Por qué es determinante |
|---|---|---|
| **Origen de evacuación** | CAP-6, `C09`, `C10` | Decide si los 25 m se miden desde una habitación o desde la puerta de la vivienda. **Es la definición que invalida el ámbito actual de R17** |
| **Altura de evacuación** | CAP-5, `C11`, `C15`, `C18`, `C22` | Define el hecho y los umbrales de 9 / 14 / 28 m |
| **Salida de planta / de edificio / de recinto** | CAP-6, `C09`, `C11` | Define qué cuenta como salida |
| **Sector de incendio** | `C01`, `C22` | Ámbito de agregación del límite de 2.500 m² |
| **Sector de riesgo mínimo** | `C01`, `C21` | Condición de excepción en varias tablas |
| **Espacio exterior seguro** | `C09` | Extremo del recorrido |
| **Aparcamiento abierto** | `C14` | Condición de activación |

**Recomendación operativa:** el Bloque 0 debe ingerir el Anejo SI A completo, no sólo los cinco términos de §13.1. El pipeline ya
existe y funciona; el coste marginal de traer los doce es prácticamente nulo, y evita una segunda ingesta cuando llegue el Bloque C.

---

## 14. Resumen de decisiones

1. **No se emite ningún hecho llamado `superficie_util` en el Bloque A.** Lo que hoy se calcula es una suma de polígonos con un
   criterio propio: se llama `superficie_suelo_agregada` y lo dice.
2. **Unión geométrica, no suma aritmética.** Elimina por construcción el doble cómputo medido en VT5/1 (22 %) y VT6/2 (36 %).
3. **El solape de recintos pasa de incidencia paralela a estado del hecho.** Si la geometría no es coherente, el número no se emite.
4. **`superficie_construida` no es obtenible del DXF actual** y queda reservada, con estado `UNKNOWN`. No se deriva de
   `total_area_m2`, que no es lo que su nombre sugiere.
5. **`uso_previsto` es un eje nuevo, distinto de `tipologia_arquitectonica`, obligatorio y sin valor por defecto.**
6. **El modelo es `planta → múltiples zonas con usos distintos`**, porque tres exigencias del texto ingerido son inexpresables de otro
   modo. Se diseña ahora; se implementa con una zona por vivienda.
7. **La ocupación es un Fact derivado sin juicio**, unidad `personas`, calculado dividiendo por m²/persona.
8. **Cuatro estados**, con `NO_APLICABLE` como estado propio para la ocupación nula de la Tabla 2.1.
9. **Un insumo `UNKNOWN` produce un derivado `UNKNOWN`.** Nunca un valor provisional.
10. **La confianza de la ocupación será Media**, no Alta, porque hereda el criterio propio de la superficie. Es el precio honesto de
    §12.1 y no debe maquillarse.

---

*Documento de diseño. Ninguna línea de código escrita ni modificada. CAP-1, CAP-2 y CAP-3 no implementadas. `evaluator.py` y
`parser.py` intactos. Ninguna regla creada. Sin commits. Las cifras de §3.2, §3.3 y §3.4 se midieron sobre `ejemplo.dxf` en modo
lectura para este documento y coinciden con las ya anotadas en `evaluator.py:3038-3040`. Las decisiones §12.1, §12.2 y §12.3 deben
cerrarse antes de implementar; §12.2 requiere además validación de un técnico competente.*
