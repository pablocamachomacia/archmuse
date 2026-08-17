# KNOWLEDGE_GRAPH.md

**Propósito:** definir el **modelo de datos de instancia** de ArchMuse — cómo se representa en memoria *un proyecto concreto* (este DXF, estas seis viviendas, estas ochenta y cuatro estancias) como un grafo de objetos con identidad, geometría y relaciones explícitas, en vez de como la lista plana de polígonos que hoy viaja del parser al evaluador. No hay código en este documento, ni clases, ni firmas de funciones: hay entidades, atributos, relaciones, invariantes y fronteras.

**Este documento no inventa vocabulario arquitectónico.** Ese trabajo ya está hecho: `ARCHITECTURAL_ONTOLOGY.md` fija los 42 conceptos del dominio y su vocabulario cerrado de relaciones, `SPACE_TAXONOMY.md` fija los 29 tipos concretos de espacio, `FUNCTIONAL_RELATIONS.md` fija cómo se relacionan por criterio profesional. Lo que **no** existe todavía, y es lo único que añade este documento, es la capa de **instancia**: qué objetos concretos existen mientras se analiza un proyecto, qué identidad tienen, quién los crea, cómo sobreviven a una segunda lectura del mismo plano modificado, y —sobre todo— **dónde está la frontera entre lo que el grafo guarda y lo que el motor de razonamiento concluye**.

**Grounding real (leído antes de escribir, no supuesto):** `analyzer/parser.py`, `analyzer/evaluator.py`, `analyzer/circulation.py`, `analyzer/plan_svg.py`, `analyzer/spatial_quality.py`, `analyzer/ai_generator.py` y `analyzer/storage.py`, en su estado del 2026-08-05. Todas las afirmaciones sobre "lo que hoy hace el código" de este documento están comprobadas contra esos archivos, con nombre de constante y valor cuando procede.

---

## 0. La decisión estructural del documento

Antes del catálogo de entidades hay que resolver una pregunta que, si se responde mal, hace inútil todo lo demás. El esquema de partida decía:

```
Space
  id, nombre, tipo, area, perimetro, altura
  muros, ventanas, puertas
  espacios_vecinos
  orientacion
  iluminacion
  ventilacion
```

Las tres últimas líneas no pueden estar ahí, y merecen la explicación completa porque es la decisión más importante de todo el modelo.

### 0.1 La regla de la frontera: el grafo describe, no juzga

`iluminacion` no es un dato de una habitación. Es una **conclusión** sobre una habitación, obtenida cruzando su geometría con la superficie de sus huecos, con un umbral normativo (CTE DB-HS3, 1/8 de la superficie útil), con una zona climática, y con una hipótesis sobre la altura del hueco que hoy vale 1.30 m fijos porque el DXF no da alturas. Esa conclusión tiene una fuerza de evidencia, una confianza, una procedencia y una fecha de caducidad —cambia en cuanto cambie cualquiera de sus insumos—. Todo eso ya tiene su sitio en el modelo: `FACT_MODEL.md` (Fact y su origen epistémico), `INFERENCE_ENGINE.md` (Inference y sus cuatro ejes), `EVIDENCE_MODEL.md` (tramos y fuerza), `UNCERTAINTY_MODEL.md`.

Si `iluminacion` se guarda como un campo del objeto Espacio, ese campo llega desnudo: sin evidencia, sin confianza, sin saber si viene de un hueco observado o de una suposición, y sin que nada obligue a recalcularlo cuando la ventana se mueva. **Es exactamente el patrón del Bug #1 de `TECH_REVIEW.md`** —tipología y zona climática que se sustituían por un valor por defecto sin dejar rastro— trasladado a un sitio nuevo y con mucha más superficie de contacto. Un modelo de datos con campos evaluativos es una fábrica de valores por defecto silenciosos.

**Regla, sin excepciones:**

> El grafo guarda **lo que el proyecto es**. El motor concluye **lo que el proyecto cumple, vale o arriesga**. Ninguna conclusión vive dentro de un nodo del grafo; toda conclusión referencia un nodo del grafo.

Esto no empobrece el grafo: lo hace consultable. Un nodo Espacio no responde "¿estás bien iluminado?" —responde "¿qué huecos tienes, a qué dan, qué superficie tienen, y qué de todo eso es desconocido?". La primera pregunta la responde el Dominio 5 con reglas, evidencia y confianza. La segunda es el sustrato sobre el que esa respuesta se puede construir, criticar y rehacer.

### 0.2 Qué atributos derivados sí se permiten (y por qué esos y no otros)

La frontera anterior sería impracticable si el grafo no pudiera calcular nada. Área y perímetro son derivados de la geometría, y nadie quiere que el área de una habitación sea un Fact que haya que ir a buscar a otro sitio.

**Criterio exacto de admisión:** un atributo derivado puede vivir en el nodo si y solo si cumple las tres condiciones:

1. Es función **pura de la geometría del propio nodo** — no necesita mirar ningún otro nodo del grafo.
2. No interviene **ningún umbral, ninguna tabla de parámetros, ningún juicio** — solo aritmética y geometría.
3. Es **estable**: dos ejecuciones sobre la misma geometría dan el mismo valor, siempre.

Pasan el filtro: área, perímetro, centroide, envolvente rectangular mínima, relación de alargamiento (lado mayor/lado menor), profundidad máxima desde el borde. No pasan: orientación (necesita el norte declarado *y* saber qué lados del polígono son exteriores, que hoy nadie sabe), superficie útil de la vivienda (necesita decidir qué espacios se excluyen — terrazas y tendederos — y eso es una regla, no una suma), vecindad (necesita otros nodos: es una arista, no un atributo), esbeltez "aceptable" (hay un umbral dentro).

Este criterio es el mismo que `FACT_MODEL.md` §4 impone al **Compositor de Hechos**: funciones de composición puras, catálogo compartido, nunca un umbral. El grafo aplica la versión local de esa misma disciplina.

### 0.3 Ningún atributo es un valor desnudo

La segunda regla estructural, y la que de verdad cierra la puerta al Bug #1:

> Todo atributo **resuelto** de un nodo —cualquiera que no sea geometría cruda ni un derivado del §0.2— es un par **(valor, origen)**, y admite explícitamente el valor **desconocido**. El origen no es un metadato opcional que se pueda ignorar al leer: es inseparable del valor.

Orígenes posibles, vocabulario cerrado (los cuatro primeros son los de `FACT_MODEL.md` §2.1, el quinto es específico de la capa de instancia):

| Origen | Significado | Ejemplo real hoy |
|---|---|---|
| **observado** | Leído directamente del DXF | La geometría del polígono de la estancia |
| **declarado** | Lo aportó el arquitecto por formulario | `tipologia`, `ciudad`, azimut del norte |
| **derivado** | Función de composición pura sobre otros valores observados | El área en m² tras aplicar el factor de escala |
| **supuesto** | Hipótesis del sistema, promovible o refutable | La altura de hueco de 1.30 m del Bloque 15 |
| **desconocido** | No hay dato, y eso es una respuesta legítima | La altura libre de cualquier planta leída de un DXF |

El caso que hace falta que esto sea una regla y no una recomendación: el tipo de espacio. Un nodo `Espacio` **nunca** lleva `tipo = "dormitorio"`. Lleva `tipo = (dormitorio, observado-por-rótulo)` o `(dormitorio, declarado)` o `(desconocido, —)`. Hoy `evaluator.py` clasifica por expresión regular sobre el rótulo del MTEXT/TEXT más cercano al polígono, con `TOLERANCIA_ETIQUETA = 0.5` m: un polígono sin rótulo dentro del margen entra en el motor como habitación sin tipo, y las reglas simplemente no le aplican, en silencio. Con esta regla, ese mismo caso produce un `(desconocido, —)` explícito que el `UNCERTAINTY_MODEL` puede convertir en un Unknown visible y `DECISION_ENGINE.md` §12 puede decidir si merece la pena preguntarle al arquitecto. La diferencia entre "no lo evalué" y "no lo evalué y no te lo dije" es todo el producto.

### 0.4 Estado de presencia: la diferencia entre "no hay" y "no lo veo"

El catálogo de nodos que viene incluye muros, huecos, pilares e instalaciones. Ninguno de los cuatro es hoy observable en el DXF que ArchMuse procesa. Si el grafo se limita a no crear esos nodos, el motor no puede distinguir dos situaciones opuestas: *esta vivienda no tiene ninguna ventana* y *este plano no dibuja ventanas*.

`INFERENCE_ENGINE.md` ya marcó esta confusión como la variante más peligrosa del Bug #1, porque falla en silencio y en la dirección tranquilizadora: una inferencia negativa ("no hay problema de ventilación, no hay huecos que evaluar") construida sobre una ausencia de datos. La defensa estructural es que la ausencia sea un estado del grafo, no un vacío del grafo.

**Cuatro estados de presencia, vocabulario cerrado**, aplicables a cada *tipo* de nodo dentro de un ámbito:

| Estado | Significado | Qué puede concluir el motor |
|---|---|---|
| **observado** | Existe en el origen y se ha leído | Todo |
| **inferido** | No está dibujado como tal, pero se deduce de otra geometría, con confianza declarada | Conclusiones con la confianza del nodo, nunca superior |
| **no observable** | El origen de datos es estructuralmente incapaz de contenerlo | **Nada** — solo Unknowns |
| **ausencia verificada** | El origen sí podría contenerlo, se ha buscado y no está | Inferencias negativas, y solo aquí |

La cuarta fila es la única que autoriza una inferencia negativa. Hoy, para huecos, el estado correcto en un DXF de distribución es *no observable*; para pilares podría llegar a ser *ausencia verificada* si algún día se busca en una capa de estructura y no aparece. Esa distinción no puede quedar al criterio de quien escriba cada regla: la lleva el grafo.

### 0.5 Vocabulario de relaciones: los siete de la ontología, más uno

`ARCHITECTURAL_ONTOLOGY.md` §0.1 cerró siete verbos de relación: *contiene/pertenece a*, *delimita*, *da a/se abre a*, *sirve a/servido por*, *conecta con*, *se apoya en*, *se ubica en*. El grafo de instancia usa esos siete y **añade uno solo**, con justificación:

- **es contiguo a** — dos espacios comparten una separación física, sin que exista paso entre ellos.

La adición no es cosmética: es la relación que hoy está mal representada en cuatro sitios del código a la vez (§1). *Conecta con* y *es contiguo a* son cosas distintas —un dormitorio y un baño de la vivienda de al lado son contiguos y no conectan; un dormitorio y el pasillo conectan y son contiguos— y confundirlas invalida a la vez el análisis acústico (que necesita contigüidad) y el de circulación (que necesita conexión). Cualquier ampliación futura de este vocabulario se gobierna como el catálogo de patrones de `CONSTRAINT_MODEL.md`: rara, deliberada y documentada, nunca como reacción a que una relación concreta no encaje.

---

## 1. El problema real que esto resuelve

La justificación de este trabajo no es estética. Es esta, comprobada en el código de hoy:

**Hay cuatro definiciones distintas de "dos habitaciones están juntas" repartidas en cinco implementaciones, y ninguna sabe de las otras.**

| Dónde | Criterio | Umbral | Para qué |
|---|---|---|---|
| `evaluator.py:1365` `_is_adjacent` | Longitud de borde compartido | `_ADJACENCY_MIN_LENGTH_M = 0.3` | Adyacencia acústica (Bloque 16) |
| `evaluator.py:333` `group_rooms_by_proximity` | Distancia entre contornos | `MAX_GAP_BETWEEN_ROOMS_M = 2.0` | Agrupar estancias en viviendas |
| `circulation.py:134` `_rooms_are_connected` | Distancia entre contornos | `WALL_GAP_TOLERANCE_M = 0.5` | Grafo de circulación |
| `plan_svg.py:337` `_cluster_rooms` | Distancia entre contornos | `_CLUSTER_GAP_THRESHOLD_M = 2.0` | Agrupar viviendas para dibujar |
| `ai_generator.py:392` `_is_adjacent` | Longitud de borde compartido | copia literal de la de `evaluator.py` | Validar plantas generadas por IA |

Las dos que miden borde compartido **no producen ni un solo hallazgo en un plano real**. Medido sobre `ejemplo.dxf` el 2026-08-05, par a par: de los 85 pares de habitaciones de sus seis viviendas, **exactamente uno** supera los 0,3 m de borde compartido que `_is_adjacent` exige — y es Terraza contra Terraza, un par que a la regla acústica no le interesa. El resto de estancias están dibujadas en la cara interior de su propio muro, dejando un hueco de 0,03 a 0,38 m que los contornos no cruzan. El Bloque 16 acústico (dormitorio junto a baño), por tanto, **no ha llegado nunca a marcar nada en producción**.

Matiz que conviene no perder, porque la versión corta de este hallazgo circula desde el 2026-07-30 en una forma más fuerte de lo que aguanta el dato: no es cierto que los contornos "nunca se toquen". En VT6/2 hay ocho pares con separación exactamente 0,000 m. Lo que ocurre es que casi todos se tocan en un punto o en un tramo irrelevante, no a lo largo de un muro — la diferencia entre tocarse y ser contiguo, que es justamente lo que el vocabulario de la §0.5 separa.

Ese hallazgo es la prueba del problema completo. Cuando la topología del proyecto no existe como dato, cada módulo la vuelve a inventar, con un criterio distinto, sin poder comparar con los demás, y un error en uno de ellos es indetectable desde los otros. **Un grafo no es un lujo arquitectónico: es el sitio donde "estas dos habitaciones son contiguas" se decide una vez, se justifica una vez y se corrige una vez.**

Corolario menos obvio, y el segundo argumento fuerte: el hueco de 0,03–0,38 m entre polígonos **es** el muro. La medición ya está hecha y es consistente (las separaciones reales no pasan de 0,38 m; el siguiente salto, ya entre habitaciones no contiguas, es de 2,27 m). El grafo puede materializar muros *inferidos* a partir de esos huecos, con espesor medido y confianza declarada, y ganar de golpe un tipo de nodo que hoy no existe. Con estado de presencia **inferido**, nunca observado (§0.4).

---

## 2. Catálogo de nodos

Once tipos, cerrados. Ocho son los que pedía el esquema de partida; los tres añadidos (Parcela, Planta, y Hueco como padre de puerta y ventana) no son ampliación de alcance, son coherencia con `ARCHITECTURAL_ONTOLOGY.md`, que ya los tiene definidos y ya los usa en las relaciones de otros conceptos.

Cada ficha lleva: identidad · atributos observados/declarados · derivados admitidos (§0.2) · relaciones · **estado de presencia hoy** · **qué NO lleva** (los campos que la §0.1 expulsa, dichos por su nombre, porque son justamente los que se colarían).

### 2.1 Proyecto

- **Identidad:** raíz del grafo. Un análisis, un Proyecto. Se corresponde 1:1 con la fila de `storage.py` que ya persiste hoy los análisis.
- **Atributos:** origen (`dxf` | `generado`), fecha, escala detectada y su procedencia (`escala.py` ya la produce y ya se niega a continuar si no la sabe), capa de estancias elegida y cómo se eligió (automáticamente / a petición del arquitecto), tipología declarada, ciudad declarada, azimut del norte declarado.
- **Relaciones:** contiene Parcela (0..1); contiene Edificio (1..n).
- **Presencia hoy:** observado. Es el único nodo con datos completos.
- **No lleva:** puntuación global, número de problemas, veredicto. Todo eso es `GLOBAL_ASSESSMENT.md`, y depende de reglas que cambian sin que el proyecto cambie.

### 2.2 Parcela

- **Identidad:** referencia catastral cuando exista; si no, identidad local del proyecto.
- **Atributos:** superficie, geometría del lindero, referencia catastral, calificación urbanística — **todos declarados o desconocidos**.
- **Relaciones:** se ubica en ámbito territorial normativo; contiene Edificio (0..n).
- **Presencia hoy:** **no observable**. Ningún DXF de distribución la contiene. Los cálculos de ocupación, edificabilidad y retranqueos de `evaluator.py` funcionan hoy sobre datos declarados en `/api/generar` y sobre un proxy en `/api/analizar`; el nodo existe para que esa diferencia sea visible en el grafo en vez de estar enterrada en el módulo.
- **No lleva:** aprovechamiento consumido ni ocupación resultante (derivados que necesitan a los edificios: son Facts derivados, no atributos).

### 2.3 Edificio

- **Identidad:** local al proyecto.
- **Atributos:** número de plantas (declarado), altura declarada, año (declarado).
- **Relaciones:** pertenece a Parcela; contiene Planta (1..n).
- **Presencia hoy:** **inferido trivialmente** — hoy se asume un edificio por archivo, y esa suposición no está escrita en ninguna parte. Escribirla como nodo con procedencia *supuesto* ya es una mejora sobre el estado actual.

### 2.4 Planta

- **Identidad:** cota o número de planta.
- **Atributos:** nivel, altura libre (declarada en `/api/generar`, **desconocida** en todo DXF), superficie construida.
- **Relaciones:** pertenece a Edificio; contiene Unidad (1..n); contiene Espacio (n) — un espacio pertenece a la vez a su Unidad y a su Planta, y eso es correcto: son dos dimensiones de ámbito distintas, exactamente como `FACT_MODEL.md` §2.3 previó.
- **Presencia hoy:** **no observable**. Un DXF de una planta no dice qué planta es. Este nodo es el que hará falta el día en que se aborde la coherencia entre plantas —la laguna nº 5 de `ARCHITECTURAL_KNOWLEDGE_MAP.md`—; hasta entonces existe con una sola instancia supuesta.

### 2.5 Unidad (Vivienda o Local)

- **Identidad:** la etiqueta real del plano (`UNIT_LABEL_PATTERN`, tipo `VT1/3`) cuando existe; si no, identidad derivada del agrupamiento por proximidad.
- **Atributos:** etiqueta, uso (vivienda | local | zona común), número de dormitorios *observado* (cuenta de espacios tipo dormitorio, derivado — no declarado).
- **Relaciones:** pertenece a Planta; contiene Espacio (1..n).
- **Presencia hoy:** observado cuando el plano trae etiquetas `VT`; **inferido** cuando no, mediante el agrupamiento por proximidad a 2,0 m. Hoy esa diferencia es invisible aguas abajo: una vivienda "de verdad" y una vivienda "adivinada por cercanía" entran idénticas en el evaluador. Con procedencia en el nodo, deja de serlo.
- **No lleva:** superficie útil, superficie total ni eficiencia. La superficie útil exige decidir que las terrazas y tendederos no cuentan, y eso es una regla del Dominio 3, no una propiedad de la vivienda. (Hoy `Unit.total_area_m2` sí es una suma pura y podría sobrevivir como derivado admitido; `useful_area` no.)

### 2.6 Espacio

El nodo central, y hoy el único con datos de verdad.

- **Identidad:** ver §3 — es el único nodo cuya estabilidad entre versiones es un problema difícil y hay que resolverlo bien.
- **Atributos observados:** polígono (geometría cerrada, ya en metros), rótulo literal leído del plano, capa de origen, puntero de procedencia al DXF (entidad y capa, en el esquema canónico de `FACT_MODEL.md` §9, para que la interfaz pueda resaltar el polígono real y para que ese rastro sobreviva al futuro salto a IFC).
- **Atributo resuelto:** tipo de espacio, del catálogo cerrado de `SPACE_TAXONOMY.md`, siempre como par (valor, origen) según §0.3.
- **Derivados admitidos:** área, perímetro, centroide, rectángulo envolvente, alargamiento, profundidad máxima.
- **Relaciones:** pertenece a Unidad y a Planta; conecta con Espacio (a través de un Hueco); es contiguo a Espacio (a través de un Muro); delimitado por Muro (n); contiene Hueco (n, a través de sus muros); sirve a / servido por Espacio.
- **Presencia hoy:** **observado**, con dos condiciones que el parser ya sabe exigir en vez de suponer: que la escala del dibujo sea determinable (`EscalaIndeterminada` si no) y que la capa de estancias sea identificable (`CapaIndeterminada` si no). Ambas negativas son buenas noticias para este modelo: son ya el patrón "no inventes un dato que no tienes" aplicado en el punto de entrada.
- **No lleva:** iluminación, ventilación, orientación, si cumple superficie mínima, puntuación de calidad espacial, ni la lista de problemas detectados. Todo eso son conclusiones que referencian este nodo.
- **Aviso de clasificación, ya real:** `evaluator.py` reconoce hoy `SALON|COCINA` como **un solo patrón con un solo umbral** (20,0 m²). Salón y Cocina son dos tipos distintos en `SPACE_TAXONOMY.md`, con requisitos distintos. Un plano que los dibuje separados hoy se evalúa como dos aciertos de la misma regla. El grafo no arregla eso por sí solo —el arreglo está en el clasificador— pero sí lo hace visible: dos nodos con el mismo tipo resuelto donde debería haber dos tipos.

### 2.7 Muro (elemento de separación)

- **Identidad:** el par de ámbitos que separa, más su eje.
- **Atributos:** eje (segmento), espesor, tipo (carga | tabique | medianera | fachada — **desconocido** hoy en todos los casos), composición constructiva (**desconocida**, y esta es la laguna que a la vez tapona acústica, térmica y estructura: laguna nº 1 de `ARCHITECTURAL_KNOWLEDGE_MAP.md`).
- **Relaciones:** delimita Espacio (1..2 — un muro entre dos espacios delimita dos; uno de fachada, uno solo); contiene Hueco (n); se apoya en / soporta.
- **Presencia hoy:** **inferido**, y solo el eje y el espesor. Procedimiento: el hueco entre dos polígonos de espacio contiguos (0,03–0,38 m medidos en `ejemplo.dxf`) define un muro cuyo espesor es esa separación y cuyo eje es la mediatriz del tramo compartido. Confianza baja-media, y jamás promovible a *observado* mientras la fuente sea un DXF de distribución. Un muro exterior (el que da a la calle) no es inferible por este método: no hay segundo polígono al otro lado. Eso hay que decirlo, no rellenarlo.
- **No lleva:** resistencia al fuego, aislamiento acústico, transmitancia. Nada de eso es deducible de una geometría 2D, y ponerlo como campo es invitar a que alguien lo rellene con un valor por defecto.

### 2.8 Hueco (Puerta / Ventana / Paso libre)

Un solo tipo de nodo con subtipo, no tres tipos. Es la decisión de `ARCHITECTURAL_ONTOLOGY.md` D.4 y aquí se mantiene: puerta, ventana y paso libre comparten geometría (una abertura en un muro, con anchura y altura), comparten relaciones (perforan un muro, conectan dos ámbitos) y se diferencian en el subtipo y en qué reglas les aplican.

- **Atributos:** subtipo, anchura, altura, antepecho, superficie practicable (la que ventila, distinta de la total).
- **Relaciones:** pertenece a Muro; conecta Espacio con Espacio (puerta y paso) o da a exterior/patio (ventana); habilita la relación *conecta con* entre dos espacios.
- **Presencia hoy:** **no observable**. Es el nodo ausente más caro del sistema, y conviene tener presente exactamente cuánto: sin huecos observados, la ventilación, la iluminación natural, la ventilación cruzada, la relación de hueco de 1/8 y la orientación efectiva de cada estancia se calculan hoy sobre un **proxy** —ancho de fachada × 0,25, con altura supuesta 1,30 m— que aparece por partida doble en el Bloque 15 y el Bloque 19 con umbrales distintos (1,5 % y 12,5 %). Ese proxy es la razón de que 14 de 16 comprobaciones de hueco fallen en `ejemplo.dxf`. **El grafo no puede arreglar esto**; lo que puede es que cada conclusión que dependa de él arrastre visiblemente el estado *no observable* del nodo del que cuelga, en vez de presentarse con la misma cara que una conclusión sobre superficie medida.
- **Consecuencia de diseño, no negociable:** mientras Hueco esté en *no observable*, ninguna inferencia negativa sobre huecos es legítima (§0.4). "Esta habitación no ventila" no se puede afirmar; "no sé si ventila, y esto es por qué" sí.

### 2.9 Pilar (elemento estructural puntual)

- **Atributos:** sección, posición, material, canto (todos desconocidos hoy).
- **Relaciones:** se ubica en Planta; soporta; puede invadir un Espacio (esta es su utilidad real a corto plazo: un pilar dentro de una habitación cambia su superficie útil y su usabilidad, y es un error frecuente del catálogo de errores).
- **Presencia hoy:** **no observable**, con un matiz que lo separa de Hueco: un pilar *sí puede estar dibujado* en una capa de estructura de muchos DXF reales. Es, de los cuatro nodos ausentes, el candidato más barato a pasar a *observado* — la maquinaria de detección de capas por contenido que ya existe (`capas_candidatas`) es el mismo patrón aplicado a otra capa. No es trabajo de este documento decidirlo, pero conviene saber que es la puerta más cercana.

### 2.10 Instalación (sistema)

- **Atributos:** tipo (fontanería | saneamiento | eléctrica | climatización | ventilación), trazado, elementos terminales.
- **Relaciones:** sirve a Espacio / Unidad / Edificio; atraviesa Espacio.
- **Presencia hoy:** **no observable** por completo. El único razonamiento sobre instalaciones que hoy existe es indirecto: la agrupación de núcleos húmedos, que se deduce de la contigüidad de baños y cocinas, no de ninguna instalación dibujada.
- **Nota de ámbito:** `FACT_MODEL.md` §2.3 ya anticipó que la instalación es una **dimensión de ámbito propia**, no una rama del árbol físico de contención. Un montante que atraviesa cinco plantas no "pertenece" a ninguna de ellas. Ese es el motivo por el que el grafo no puede ser solo un árbol: es un grafo.

### 2.11 Zona común

- Espacio que no pertenece a ninguna Unidad sino al Edificio (portal, rellano, escalera, garaje).
- **Presencia hoy:** observable en la medida en que se dibuje y rotule como los demás espacios. Se separa de Espacio porque su ámbito de pertenencia es distinto y porque casi todas las reglas de vivienda no le aplican — hoy, un portal rotulado dentro del área de análisis entraría en el agrupamiento por proximidad como si fuera una habitación más de la vivienda más cercana.

---

## 3. Identidad: el problema difícil

Todo lo anterior es catálogo. Esto es el punto donde un modelo de datos se gana la vida o se rompe a los seis meses.

**La pregunta:** el arquitecto analiza un plano, ArchMuse le señala doce hallazgos, él corrige tres cosas en AutoCAD y vuelve a subir el DXF. ¿Cómo sabe el sistema que el "Dormitorio 2" del segundo análisis es el mismo Dormitorio 2 del primero?

No es una pregunta teórica. `OBSERVATION_MODEL.md` construyó toda la estabilidad de los Hallazgos —que un problema persista, se agrave, se resuelva o se reabra en vez de desaparecer y reaparecer como uno nuevo— sobre una huella hecha de `concept_id` de Constraint **más `concept_id` de ámbito**. Ese segundo componente es, literalmente, la identidad de un nodo de este grafo. Si la identidad de los espacios no es estable entre versiones, el ciclo de vida de los hallazgos no funciona, y con él se cae el histórico del proyecto, la comparación entre versiones y el futuro Dominio 13.

**Lo que no vale:** el orden de aparición en el DXF (arbitrario, cambia al editar), el índice en la lista (lo mismo), el rótulo por sí solo (hay tres "Dormitorio 2" en un edificio de seis viviendas), el centroide exacto (cambia con cualquier retoque de 2 cm).

**Propuesta: identidad en dos niveles, la misma separación de `FACT_MODEL.md` §7.**

- **`instance_id`** — identifica a este nodo en esta versión del grafo. Se regenera en cada lectura, no significa nada fuera de ella.
- **`concept_id`** — identifica "esta habitación" a lo largo de la vida del proyecto. Es el que tiene que sobrevivir.

**Cómo se asigna el `concept_id` en una relectura:** por **emparejamiento**, no por cálculo. Se toman los nodos de la versión anterior y los de la nueva y se emparejan por una combinación de solapamiento geométrico (¿el polígono nuevo cubre la mayor parte del viejo?), unidad de pertenencia y tipo resuelto. Un espacio emparejado hereda el `concept_id`; uno sin pareja es un espacio nuevo; un viejo sin pareja ha desaparecido. Nunca se empareja por igualdad exacta de valores: dos habitaciones pueden tener por casualidad la misma superficie, que es el mismo motivo por el que `FACT_MODEL.md` §11.3 prohibió deduplicar Facts por valor desnudo.

**Y una honestidad que el modelo debe conservar:** un emparejamiento es una **inferencia**, no un hecho. Cuando el arquitecto une dos habitaciones en una, o parte el salón en dos, el emparejamiento correcto es ambiguo y no hay respuesta única. El grafo debe poder decir "creo que este es el mismo espacio, con confianza media" y dejar que la ambigüedad llegue arriba, en vez de elegir en silencio. Es el mismo principio que gobierna todo lo demás.

**Versionado:** cada lectura produce una versión nueva del grafo, completa e inmutable; las anteriores no se editan. Es la disciplina *append-only* que `REASONING_ENGINE_SPEC.md` fijó para todas las entidades con historia, y aquí tiene un beneficio inmediato y concreto: comparar dos versiones —qué cambió entre el análisis del martes y el del jueves— es una operación sobre datos, no una reconstrucción a posteriori.

---

## 4. Aristas

Ocho tipos (§0.5). Lo que sigue es lo que cada una necesita para no ser ambigua: dirección, cardinalidad, quién la crea y con qué criterio.

| Relación | Dirección | Entre | Quién la crea | Criterio hoy |
|---|---|---|---|---|
| **contiene / pertenece a** | par inverso | Contenedor ↔ contenido | Constructor, fase 3 | Etiqueta `VT` o proximidad ≤ 2,0 m |
| **es contiguo a** | simétrica | Espacio ↔ Espacio | Constructor, fase 5 | Distancia entre contornos ≤ tolerancia de muro, **y** longitud de tramo enfrentado suficiente |
| **conecta con** | simétrica | Espacio ↔ Espacio | Constructor, fase 5 | Hoy: contigüidad (aproximación declarada). Con huecos: existencia de puerta o paso |
| **delimita** | dirigida | Muro → Espacio | Constructor, fase 4 | Muro inferido del hueco entre polígonos |
| **da a / se abre a** | dirigida | Hueco → exterior / patio | — | **No creable hoy** |
| **sirve a / servido por** | par inverso | Espacio/Instalación → ámbito servido | Motor de dominio, no el Constructor | Criterio funcional (`FUNCTIONAL_RELATIONS.md`), nunca geométrico |
| **se apoya en** | dirigida | Elemento → elemento estructural | — | **No creable hoy** |
| **se ubica en** | dirigida | Parcela → ámbito normativo | Declarado | Ciudad declarada → zona climática (`cte_zonas.py`) |

Cuatro observaciones que el cuadro deja ver y conviene no perder:

1. **`conecta con` es hoy una aproximación de `es contiguo a`, y hay que decirlo dentro de la arista.** Sin huecos observados no se puede saber si dos habitaciones contiguas comunican. `circulation.py` ya toma esa decisión —trata la cercanía como conexión— pero la toma en silencio, dentro de una función privada. En el grafo, esa arista lleva su procedencia *supuesto*, y todo lo que se apoye en ella (recorridos, evacuación, espacios de paso) hereda esa incertidumbre en vez de heredar una falsa certeza.
2. **La contigüidad necesita dos condiciones, no una.** Solo distancia no basta: dos habitaciones que se tocan en una esquina pasarían el filtro. Solo borde compartido tampoco: es lo que hoy no se dispara nunca. La conjunción —cercanía dentro del espesor plausible de un muro *y* un tramo enfrentado de longitud mínima— es la que captura la intención de las dos implementaciones actuales sin heredar el fallo de ninguna.
3. **`sirve a` no la crea el Constructor.** Es criterio profesional (servido/servidor, la distinción de Kahn que `FUNCTIONAL_RELATIONS.md` desarrolla), no geometría. Si la creara el Constructor, el grafo estaría opinando, y eso rompe la §0.1.
4. **Dos aristas no son creables hoy en absoluto.** Están en el catálogo porque el modelo tiene que ser el mismo antes y después de que haya datos de huecos; lo que cambia con IFC es el relleno, no la forma. Que estén vacías es un dato del sistema, no un olvido.

---

## 5. Quién construye el grafo

Actor nuevo, con el mismo patrón de gobierno que el Compositor de Hechos (`FACT_MODEL.md`), el Intérprete de Constraints (`CONSTRAINT_MODEL.md`) y el Motor de Síntesis de Hallazgos (`OBSERVATION_MODEL.md`): **un solo proceso compartido, catálogo cerrado de criterios, nunca lógica ad hoc por dominio**.

**El Constructor del Grafo.** Única entrada: un origen de datos (DXF hoy; IFC, un proyecto generado por IA, o una edición manual mañana). Única salida: una versión sellada del grafo. Fases:

- **Fase 0 — Admisión.** Escala determinable y capa de estancias identificable. Ya existe: `escala.py` y `capas_candidatas`/`elegir_capa`, con dos excepciones que se niegan a seguir a ciegas (`EscalaIndeterminada`, `CapaIndeterminada`). Es el precedente real de todo este documento: la única parte del sistema que ya prefiere no responder a responder mal.
- **Fase 1 — Espacios.** Polígonos cerrados → nodos Espacio, con procedencia al DXF. Incluye el descarte de contornos agrupadores (`_discard_container_candidates`), que hoy es una heurística de color con una condición fina —solo descarta si el contorno duplica una etiqueta ya representada— y que debe entrar al grafo **como decisión registrada**, no como polígono que simplemente no aparece.
- **Fase 2 — Clasificación.** Rótulo → tipo de `SPACE_TAXONOMY.md`, siempre como par (valor, origen). Un espacio sin rótulo dentro de `TOLERANCIA_ETIQUETA` produce `(desconocido, —)`, no un espacio que se cae del análisis.
- **Fase 3 — Agrupación.** Espacios → Unidades, por etiqueta `VT` (observado) o por proximidad (inferido), con la procedencia distinguida.
- **Fase 4 — Muros inferidos.** Huecos entre polígonos contiguos → nodos Muro con eje y espesor, presencia *inferido*.
- **Fase 5 — Topología.** Aristas de contigüidad y de conexión, **una sola vez, con un solo criterio**. Aquí es donde mueren las cuatro definiciones de la §1.
- **Fase 6 — Sellado y validación.** Se comprueban los invariantes (§6) y la versión queda inmutable.

**Regla dura:** ningún dominio, ninguna regla y ningún módulo de presentación crea, modifica ni completa nodos o aristas. Leen. Si un dominio necesita una relación que el grafo no tiene, la respuesta correcta es discutir si esa relación entra en el catálogo, no calcularla por su cuenta —que es literalmente lo que produjo el estado descrito en la §1.

---

## 6. Invariantes

Un grafo que no puede ser inválido es un grafo en el que nadie confía. Estos son los que deben comprobarse en la fase 6, y cuyo incumplimiento es un error del Constructor, no un hallazgo del proyecto:

1. Todo Espacio pertenece exactamente a una Unidad o a un Edificio (zona común). Ninguno huérfano.
2. Todo Espacio pertenece exactamente a una Planta.
3. Ningún par de polígonos de Espacio se solapa más de una tolerancia mínima dentro de la misma Unidad. (Un solapamiento **entre** unidades sí es un hallazgo real: es la comprobación de compartimentación que ya existe.)
4. Toda arista une nodos existentes en la misma versión del grafo.
5. `es contiguo a` y `conecta con` son simétricas: si A conecta con B, B conecta con A.
6. Todo Muro delimita uno o dos Espacios. Ninguno delimita cero.
7. Todo atributo resuelto tiene origen. Un valor sin origen es un grafo inválido, no un valor por defecto.
8. Todo tipo de nodo tiene un estado de presencia declarado para el ámbito. La ausencia de nodos de un tipo nunca es interpretable sin ese estado.
9. Una versión sellada no se modifica. Cualquier cambio produce una versión nueva.

Los invariantes 7 y 8 son los únicos que no son estructurales sino epistémicos, y son los dos que de verdad protegen contra el Bug #1.

---

## 7. Qué le tiene que poder preguntar el sistema

El contrato del grafo son las **consultas**, no los campos. Estas son las que el código actual necesitaría desde el primer día, cada una sustituyendo a un cálculo que hoy se hace suelto en algún módulo:

- Espacios de una Unidad · Unidades de una Planta · Unidad a la que pertenece un Espacio.
- Espacios **contiguos** a uno dado (→ Bloque 16 acústico, hoy inoperante).
- Espacios **conectados** a uno dado (→ `circulation.py`).
- Camino más corto entre dos Espacios, en número de espacios cruzados y en distancia (→ recorridos absurdos, evacuación, espacios de paso).
- Muros que delimitan un Espacio · Espacios que separa un Muro.
- Huecos de un Espacio y de un Muro (hoy: vacío, con presencia *no observable*).
- Espacios de un tipo dado dentro de un ámbito (→ jerarquía de dormitorios, ratio baños/dormitorios).
- Geometría agrupada de una Unidad para dibujar (→ `plan_svg`, `spatial_quality`, `circulation`, que hoy agrupan tres veces por su cuenta).
- Diferencias entre dos versiones del grafo.
- **Qué no se sabe de un ámbito** — la lista de atributos `desconocido` y de tipos de nodo *no observable* que le afectan. Esta es la consulta que alimenta directamente el protocolo de datos insuficientes de `DECISION_ENGINE.md` §12, y hoy no hay nada capaz de responderla.

Nótese lo que **no** está: "¿cumple esta vivienda la superficie mínima?", "¿qué problemas tiene este espacio?", "¿cuál es la superficie útil?". Ninguna de las tres es una consulta al grafo. La tercera parece que sí, y es el ejemplo más útil de la frontera: sumar áreas es aritmética, pero decidir **qué espacios entran en la suma** —terrazas y tendederos fuera— es una regla normativa que cambia por comunidad autónoma. El grafo entrega los espacios y sus áreas; quién los suma y con qué criterio es del dominio.

---

## 8. El mapa honesto: qué habría hoy dentro de este grafo

| Nodo | Estado hoy | Qué falta para observarlo |
|---|---|---|
| Proyecto | ✅ observado | — |
| Espacio | ✅ observado | — |
| Unidad | ✅ observado / inferido | Etiquetas `VT` presentes en el plano |
| Zona común | ✅ observable si se rotula | Distinguirla del resto de estancias |
| Edificio | ⚠️ inferido (uno por archivo) | Multi-edificio declarado |
| Muro | ⚠️ inferido (eje y espesor) | Capa de muros, o IFC |
| Planta | ❌ no observable | Dato declarado, o juego de plantas |
| Parcela | ❌ no observable | Dato declarado o catastro |
| Hueco | ❌ no observable | Capa de carpintería, o IFC |
| Pilar | ❌ no observable | Capa de estructura (**la más cercana**) |
| Instalación | ❌ no observable | IFC |

**Cuatro de once tipos tienen datos. El grafo de hoy es, honestamente, un grafo de espacios con dos tipos de arista y muros inferidos.**

Esto no es un argumento en contra —es la razón de que este documento se escriba antes que el código, y coincide con el hallazgo del 21 % de conceptos reconocibles de `ARCHITECTURAL_ONTOLOGY.md`, obtenido por otro camino—. Sí es un argumento contra dos cosas concretas:

1. **Construir los once tipos de nodo de golpe.** Siete de ellos serían clases vacías durante meses, con el riesgo conocido de que alguien las rellene con valores por defecto plausibles para que "funcione". Los estados de presencia (§0.4) existen precisamente para que esos siete puedan estar declarados y vacíos sin que nadie sienta la tentación.
2. **Vender el grafo como el paso que desbloquea muros, huecos e instalaciones.** No desbloquea nada de eso: el cuello de botella es el origen de datos, no la representación. Lo que desbloquea es que las cuatro definiciones de contigüidad pasen a ser una, que la topología deje de reinventarse en cada módulo, que la identidad de las estancias sobreviva entre versiones, y que "no lo sé" sea un valor que el sistema puede decir.

---

## 9. Riesgos

1. **El grafo se convierte en el nuevo cajón de sastre.** El riesgo más probable con diferencia. Alguien necesita `orientacion` en un espacio, la frontera de la §0.1 le parece burocracia en una tarde de plazo, y añade el campo. En un año hay veinte campos derivados dentro de los nodos, ninguno con evidencia, y `FACT_MODEL.md` es un documento que nadie aplica. Es la misma clase de riesgo que `FACT_MODEL.md` §12.1 identificó como el mayor de todo el modelo —la erosión de la frontera entre dato y conclusión— y la defensa es la misma: no es estructural, es disciplina de gobierno sostenida.
2. **Migración big-bang de un evaluador de 2.966 líneas.** "El evaluador dejaría de leer el parser y leería el grafo" es la dirección correcta y la ejecución más peligrosa. Ese módulo es hoy la única pieza validada extremo a extremo contra un plano real, y no hay ninguna prueba que cubra su comportamiento completo. Un cambio de sustrato de datos en un solo salto es el escenario clásico de regresión silenciosa: sigue devolviendo números, y son otros.
3. **La topología única cambia resultados el día uno.** Unificar cuatro criterios de contigüidad significa, necesariamente, que algún módulo dejará de ver lo que veía. El Bloque 16 acústico, que hoy no se dispara nunca, empezará a disparar — probablemente mucho. Eso no es un fallo del grafo: es una regla que llevaba meses sin funcionar y de repente funciona. Pero si aparece sin avisar, se leerá como una regresión.
4. **El emparejamiento entre versiones se toma como resuelto.** La §3 propone un mecanismo, no lo demuestra. Habitaciones fusionadas, partidas o renumeradas son casos genuinamente ambiguos, y si el emparejamiento falla en silencio, todo el ciclo de vida de los hallazgos produce ruido en vez de historia.
5. **Coste sin usuario visible.** Ningún arquitecto pagará más por que ArchMuse tenga un grafo. Todo el valor es indirecto: menos bugs de topología, hallazgos estables entre versiones, y una base sobre la que el resto de `docs/brain/` es implementable. Es una inversión defendible, pero hay que defenderla como tal, no disfrazarla de funcionalidad.
6. **Nomenclatura.** El esquema de partida proponía un paquete de código `brain/knowledge/`. `docs/brain/` ya significa otra cosa en este proyecto —el diseño del motor de razonamiento— y un tercer sentido de "brain" en el árbol de código añadiría confusión gratuita. Es una decisión de implementación, no de modelo, pero conviene resolverla antes y no después.

---

## 10. Cómo llegaría esto a existir

Este documento **no autoriza escribir código** — y no solo por la petición explícita de no programar todavía: la regla de proceso de `CLAUDE.md` exige un PRD aprobado antes de cualquier capacidad nueva, y esto es la capacidad más transversal que se ha propuesto hasta ahora.

Dos cosas que ese PRD tendría que resolver, y que no son de este documento:

**Primera: la relación con `PRD-001-Core-Reasoning-Engine.md`.** El grafo no es un proyecto paralelo al motor de razonamiento — es su capa de ámbito. Los Facts necesitan a qué referirse; los Hallazgos necesitan una identidad de ámbito estable; el Constructor del Grafo es hermano del Compositor de Hechos. Abrir un segundo frente de implementación en paralelo al PRD-001, que sigue sin aprobar, iría justo en contra de lo que `BRAIN_REVIEW.md` recomendó: no ensanchar el alcance hasta que aterrice algo. Lo razonable es que el grafo sea **la primera fase del PRD-001**, no un PRD nuevo compitiendo por el mismo tiempo.

**Segunda: orden de adopción, nunca sustitución de golpe.** El grafo se construye **al lado** del flujo actual, no en su lugar, y se le van pasando consumidores de menor a mayor riesgo:

1. `circulation.py` primero — ya es un grafo, con su propio criterio de adyacencia; migrarlo es sustituir su grafo privado por el compartido, y es el único módulo cuyo comportamiento actual ya está descrito en términos de nodos y aristas.
2. `plan_svg.py` y `spatial_quality.py` después — consumen agrupación y geometría, no reglas normativas; un error aquí se ve en pantalla, no en un veredicto.
3. `evaluator.py` al final, y **regla por regla**, no de una vez. Primero las que dependen de topología (adyacencia acústica, ancho de pasillo, distancia de evacuación), que son las que el grafo mejora de verdad; las de superficie pura no ganan nada con migrar y pueden esperar.
4. Antes de tocar el evaluador, un juego de pruebas que congele su salida actual sobre `ejemplo.dxf` — ya existe el precedente (`test(ingesta): congelar la salida actual de ejemplo.dxf`), y es la única forma de distinguir "cambió porque el grafo lo arregla" de "cambió porque el grafo lo rompe".

---

## 11. Autocrítica: qué no resuelve este documento

- **No resuelve la geometría de los muros exteriores.** El método de inferencia por hueco entre polígonos funciona entre dos espacios; el muro que da a la calle no tiene segundo polígono. La envolvente —de la que dependen compacidad, orientación y todo el Dominio 8— sigue siendo un proxy.
- **No dice cuánto cuesta.** Un modelo de datos que se cruza con quince módulos tiene un coste de migración real, y este documento no lo estima. El PRD tendrá que hacerlo, y la respuesta podría ser que no compensa hacerlo entero.
- **No decide qué pasa con `/api/generar`.** Un proyecto generado por IA tiene, en principio, más datos que un DXF (alturas, huecos declarados). Ese flujo podría poblar nodos que el flujo DXF no puede, y eso significa que **dos proyectos del mismo sistema tendrían estados de presencia distintos**. Es coherente con el modelo, pero abre la pregunta de si una puntuación calculada sobre un grafo rico es comparable con una calculada sobre un grafo pobre. Sospecho que no lo es, y que decir que lo es sería la misma clase de deshonestidad que el percentil fabricado de `scoring.py`.
- **No prueba que el emparejamiento entre versiones funcione.** Lo propone (§3). Es el punto más débil y el que más se beneficiaría de una prueba temprana sobre dos versiones reales de un mismo plano, antes de comprometer nada del resto.
- **No convierte en implementable la mitad del catálogo.** Siete de once nodos siguen vacíos después de todo este diseño. Eso es una propiedad del origen de datos, no de este documento, pero conviene no leerlo como un avance mayor del que es: el grafo hace **honesto y único** lo que ya se sabe. No añade conocimiento nuevo sobre el edificio.

---

**Estado:** documento de diseño. Sin código, sin implementación aprobada. Sexta capa de la subserie de dominio (Ontología → Taxonomía → Relaciones funcionales → Principios → Errores → **Grafo de instancia**), y la primera de ellas que describe objetos concretos de un proyecto concreto en vez de vocabulario general.
