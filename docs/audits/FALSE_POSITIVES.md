# FALSE_POSITIVES.md — Auditoría de comportamiento de las reglas

**Fecha:** 2026-08-05 · **Código:** commit `7a908e4` · **Datos:** `ejemplo.dxf` (único plano real disponible)
**Método:** ejecución instrumentada del motor completo, no lectura de código. Todos los números de este informe están medidos.
**Restricción:** auditoría de solo lectura. **Ninguna línea de código modificada.**

Complementa a `NORMATIVE_AUDIT.md` (2026-08-05), que auditó la *estructura* de las reglas. Este documento audita su *comportamiento*: qué dispara cuando no debe, qué no dispara cuando debe, y qué mide mal.

---

## 1. Resumen por impacto

| # | Hallazgo | Tipo | Evidencia medida | Impacto |
|---|---|---|---|---|
| **F1** | **Dos viviendas de seis tienen su contorno completo contado como una habitación "Salón/cocina"**, solapando dormitorio y baño | Geometría | VT5/1: 52,13 m² = 76,1 % de la vivienda. VT6/2: 58,58 m² = 56,5 %. Solape interno: 12,43 y 27,32 m² | **Crítico** |
| **F2** | **Una vivienda de tres dormitorios no tiene ni salón ni cocina, y puntúa 91,7** | Falso negativo | VT1/3: 7 piezas, ninguna Salón/cocina. Ninguna regla exige que exista | **Crítico** |
| **F3** | **R17 (evacuación ≤ 25 m) es incapaz de disparar** | Falso negativo | Máximo medido 2,88 m. Margen al umbral: 22,12 m | **Crítico** |
| **F4** | **R18c (itinerario accesible) dispara en 6 de 6 viviendas por ausencia de dato** | Falso positivo | 0 pasillos etiquetados en todo el plano → 6 incidencias | **Alto** |
| **F5** | **R19 falla en el 93,8 % de los casos y R15b en el 0 %, midiendo lo mismo** | Umbral inconsistente | Ratios medidos 7,0–12,7 %. Umbrales 12,5 % y 1,5 % | **Alto** |
| **F6** | **R16a (adyacencia acústica) no puede disparar sobre datos reales** | Falso negativo | 1 de 85 pares de piezas comparte borde; umbral exige > 0,3 m | **Alto** |
| **F7** | **`_bounding_sides` mide mal en el 85 % de las piezas** | Geometría | 29 de 34 piezas no son rectangulares; peor caso llena el 42,5 % de su rectángulo | **Alto** |
| **F8** | **R01 (habitación "tubo") solo dispara en terrazas** | Falso positivo | 3 de 3 hallazgos son Terrazas de VT6/2 | Medio |
| **F9** | **R00 y R20 discrepan sobre el mismo dormitorio** | Umbral inconsistente | VT3/3 Dormitorio 2 = 7,17 m²: R00 falla (min 8), R20 pasa (min 6) | Medio |
| **F10** | **`superficie útil` se define cuatro veces y `lado corto` significa siete cosas** | Definición duplicada | Ver §11 | Medio |
| **F11** | **La puntuación depende del número de piezas que el parser consiga leer** | Geometría | VT5/1: 3 piezas → 26 checks. VT1/3: 7 piezas → 48 checks | Medio |
| **F12** | **12 de 22 reglas no producen ni un hallazgo sobre el único plano real** | Cobertura | Ver §12 | Medio |

**Consecuencia agregada:** de las 6 viviendas de `ejemplo.dxf`, **3 se analizan sobre geometría incorrecta** (VT1/3, VT5/1, VT6/2). El motor no lo detecta en ningún caso.

---

## 2. Método

Tres sondas ejecutadas contra el motor real (`evaluate_advanced` con `tipologia=plurifamiliar`, `zona_cte=D`, `densidad_urbana=alta`), instrumentando resultados regla a regla, pieza a pieza.

Corrección de método que conviene registrar: un primer intento contó 51 polígonos en la capa `00 areas` y dedujo que el parser perdía 17. **Ese dato era falso** — la sonda no filtraba polilíneas abiertas, que el parser descarta correctamente (`_esta_cerrada`, `parser.py:246`). Las cifras reales son 42 cerradas → 34 habitaciones, con 8 descartes deliberados. Todo lo que sigue usa las funciones del propio proyecto, no reimplementaciones.

**Aviso de alcance:** un solo plano, de un solo estudio. Las tasas de disparo de §12 no son estadística; son el comportamiento sobre el único caso real que existe. Los hallazgos F3, F6, F7 y F10 son estructurales y no dependen del plano; el resto sí.

---

## 3. F1 — Contornos de vivienda contados como habitación 🔴

El hallazgo dominante. `_discard_container_candidates` (`parser.py:259`) descarta un polígono agrupador **solo si** contiene otro polígono BYLAYER *con su misma etiqueta*. Medido sobre `ejemplo.dxf`, cinco polígonos "Salón/cocina" con color explícito ACI 10 entran a esa criba:

| Área | Contiene piezas | Resultado |
|---|---|---|
| 61,38 m² | 4 | descartado ✔ |
| 72,70 m² | 4 | descartado ✔ |
| 62,10 m² | 3 | descartado ✔ |
| **52,13 m²** | **1** | **conservado ✘** |
| **58,58 m²** | **2** | **conservado ✘** |

Los dos conservados no tenían dentro ningún "Salón/cocina" más pequeño, así que la condición de duplicado no se cumplió y el filtro los dejó pasar — que es exactamente el comportamiento documentado en su docstring como deseable ("es la única representación de esa habitación, descartarla dejaría a la vivienda sin superficie habitable"). Pero no son habitaciones: son el contorno de la vivienda.

**Consecuencia medida — solape interno de polígonos:**

| Vivienda | Suma de áreas | Área real (unión) | Doble contabilidad | Piezas engullidas |
|---|---|---|---|---|
| VT1/3–VT4/2 | — | — | 0,00 m² | — |
| **VT5/1** | 68,49 m² | 56,06 m² | **12,43 m² (18 %)** | Dormitorio 1 (12,09 m², el 100 % dentro) |
| **VT6/2** | 103,76 m² | 76,44 m² | **27,32 m² (26 %)** | Dormitorio 1, Baño, 2 Terrazas |

En VT6/2 el "Salón/cocina" de 58,58 m² contiene íntegros el Dormitorio 1 (13,04 m²) y el Baño (4,00 m²). No es una habitación grande: es la planta entera.

### 3.1 Corrección a una conclusión previa del proyecto

VT6/2 se usa como ejemplo canónico en al menos cinco documentos de `docs/brain/` (`OBSERVATION_MODEL.md` §1 y §3, `ARCHITECTURAL_ONTOLOGY.md`, `ARCHITECTURAL_MISTAKES.md`, `BRAIN_REVIEW.md`) con esta lectura: *"baja eficiencia útil/total en `evaluator.py` y, por separado, la puntuación más baja en `spatial_quality.py` — dos sistemas de puntuación distintos confirmando el mismo problema real"*, con causa raíz atribuida a *"la superficie de terraza desproporcionada de esa vivienda"*.

**Los datos no sostienen esa causa raíz.** VT6/2 falla útil/total porque su superficie útil (75,62 m²) cuenta tres veces la misma planta: el salón contenedor, más el dormitorio y el baño que están dentro de él. Y los dos sistemas de puntuación **no son independientes**: ambos consumen la misma geometría corrupta, así que su coincidencia no es una validación cruzada.

El hallazgo "VT6/2 es la peor vivienda" sobrevive. Su explicación, no. Conviene corregirlo donde se usa como ejemplo de agrupación por causa raíz compartida — la causa raíz compartida existe, pero es un fallo de parseo, no un exceso de terrazas.

---

## 4. F2 — Una vivienda sin cocina puntúa 91,7 🔴

VT1/3, medido:

```
piezas:  Dormitorio 1, Dormitorio 2, Dormitorio 3, Aseo, Baño, Tendedero, Terraza
checks:  48   ·   fallos: 4   ·   score: 91,7  →  "Cumplimiento correcto"
```

Tres dormitorios, dos piezas húmedas, ningún espacio de estar ni de cocinar. Como vivienda es inhabitable y jurídicamente inviable.

**Ninguna de las 22 reglas lo detecta.** Verificado: no existe ningún patrón `PRESENCIA_OBLIGATORIA` en `evaluator.py`. Y las reglas que podrían haberlo notado están escritas para devolver `None` cuando la pieza falta, no para fallar:

| Regla | Comportamiento si falta la pieza |
|---|---|
| `evaluate_spatial_hierarchy` (R13) | `return None` — no evalúa |
| `evaluate_cross_ventilation` (R11) | `return None` |
| `evaluate_bathroom_accessibility` (R08) | `return None` |
| `evaluate_accessible_bathroom_area` (R21) | `return None` |
| `evaluate_circulation_efficiency` (R14) | `return None` |

Devolver `None` es correcto para una regla que mide una propiedad de una pieza que no existe. El problema es que **no hay ninguna regla del otro tipo**: ninguna comprueba que el programa mínimo de la vivienda esté presente. El resultado es la asimetría más peligrosa del motor: *cuantas menos piezas tenga una vivienda, menos cosas pueden fallarle*.

La única regla de presencia que existe es R09 (ratio de baños), y funciona: detecta correctamente que VT4/2 y VT5/1 no tienen ningún Baño. Es la prueba de que el patrón es viable y de que sencillamente no se aplicó al resto del programa.

---

## 5. F3 — R17 (evacuación) no puede disparar 🔴

`evaluate_evacuation_distance` (`evaluator.py:1539`) calcula `unit_boundary.distance(room.polygon.centroid)`: la distancia del centroide de la pieza al **punto más cercano** del contorno exterior de la vivienda.

Eso no es un recorrido de evacuación. Es, aproximadamente, la semidistancia de la pieza a la fachada más próxima.

| Métrica | Valor medido |
|---|---|
| Evaluaciones | 16 |
| Distancia mínima | 0,50 m |
| Distancia máxima | **2,88 m** |
| Umbral | 25,0 m |
| Margen | **22,12 m** |

Comparación directa con la mitad del lado corto de cada pieza, que es lo que la fórmula realmente aproxima:

```
VT2/2  Dormitorio 1    dist_a_borde=0,50   medio_lado_corto=1,40
VT1/3  Dormitorio 2    dist_a_borde=1,01   medio_lado_corto=1,33
VT2/2  Salón/cocina    dist_a_borde=1,40   medio_lado_corto=2,87
```

Para que esta regla disparase, una pieza tendría que estar a más de 25 m del borde más cercano de su propia vivienda. **No existe la vivienda que lo cumpla.** La regla se presenta como CRÍTICO con código `CTE-DB-SI-3` y es, en la práctica, un `False` constante.

Es además el peor modo de fallo posible: un falso negativo silencioso en materia de incendios. El informe no dice "no evaluable"; dice, implícitamente, "cumple".

---

## 6. F4 — R18c dispara siempre, por falta de dato 🔴

Medido, vivienda por vivienda:

```
VT1/3  pasillos=0  →  FALLA        VT4/2  pasillos=0  →  FALLA
VT2/2  pasillos=0  →  FALLA        VT5/1  pasillos=0  →  FALLA
VT3/3  pasillos=0  →  FALLA        VT6/2  pasillos=0  →  FALLA
```

`evaluate_itinerario_accesible` (`evaluator.py:1684`) recorre las piezas buscando un "Pasillo" de anchura ≥ 1,20 m; si no encuentra ninguno, devuelve fallo. En `ejemplo.dxf` no hay ni una pieza etiquetada "Pasillo" — el vocabulario completo del plano son ocho etiquetas: Terraza, Dormitorio 1/2/3, Salón/cocina, Tendedero, Baño, Aseo.

Seis incidencias IMPORTANTE, el 16 % del total del proyecto, generadas por una etiqueta que el dibujante no usó. **Ninguna corresponde a un defecto del proyecto.**

Es el mismo patrón que F3 con signo opuesto, y las dos son el error que `docs/brain/INFERENCE_ENGINE.md` prohíbe explícitamente: derivar una conclusión negativa de un dato ausente en lugar de declarar un `Unknown`.

---

## 7. F5 — Dos umbrales sobre la misma medida, ninguno discriminante 🔴

R15b y R19 calculan idéntica expresión (`evaluator.py:1337` y `:1759`) y la comparan contra 1,5 % y 12,5 %. Valores reales medidos:

| Pieza | Área | "Fachada" | "Hueco" | Ratio | R15b (1,5 %) | R19 (12,5 %) |
|---|---|---|---|---|---|---|
| Dormitorio 1 | 12,72 m² | 6,46 m | 1,62 | 12,69 % | pasa | pasa |
| Dormitorio 2 | 8,48 m² | 3,21 m | 0,80 | 9,45 % | pasa | **falla** |
| Salón/cocina | 23,38 m² | 6,58 m | 1,65 | 7,04 % | pasa | **falla** |
| Dormitorio 1 | 15,07 m² | 6,05 m | 1,51 | 10,04 % | pasa | **falla** |

**Tasas: R15b falla 0 de 16 (0 %). R19 falla 15 de 16 (93,8 %).**

Los ratios reales se concentran entre 7 % y 12,7 %. Un umbral está muy por debajo de esa banda y el otro justo por encima: uno no puede fallar nunca y el otro no puede pasar casi nunca. **Ninguno de los dos discrimina nada.** Dos reglas, una vacua y otra universal, sobre la misma medida.

Recuérdese el hallazgo H3 de `NORMATIVE_AUDIT.md` §6.3: esa medida es además dimensionalmente incoherente (metros divididos entre metros cuadrados). Aquí queda confirmado el efecto práctico: el 41 % de las incidencias del proyecto salen de una comparación cuyo resultado estaba determinado de antemano por la elección del umbral, no por el proyecto.

---

## 8. F6 — R16a no puede disparar 🔴

`evaluate_acoustic_adjacency` exige `_shared_edge_length > 0,3 m`: intersección literal de contornos.

| Métrica | Valor medido |
|---|---|
| Pares de piezas dentro de una misma vivienda | 85 |
| Pares con borde compartido > 0 | **1** |
| Separación entre piezas próximas | 0,000 – 0,380 m |
| Evaluaciones dormitorio↔baño | 11 |
| Fallos | **0** |

Las piezas se dibujan a cara interior de muro, así que entre dos habitaciones contiguas queda el espesor del tabique. Un solo par de 85 llega a tocarse, y aun así no supera los 0,3 m de tramo compartido exigidos.

`circulation._rooms_are_connected` (`circulation.py:134`) ya resolvió esto con un umbral de distancia (`WALL_GAP_TOLERANCE_M = 0.5`) validado empíricamente. R16a nunca se migró.

Matiz que conviene conservar, y que `docs/brain/KNOWLEDGE_GRAPH.md` §0.5 ya señala: no es cierto que los contornos "nunca se toquen" — hay pares con separación exactamente 0,000 m. Lo que ocurre es que se tocan en un punto o en un tramo irrelevante, no a lo largo de un muro. La medida correcta es la contigüidad, no el contacto.

---

## 9. F7 — La geometría base mide mal en el 85 % de las piezas 🟠

`_bounding_sides` (`evaluator.py:210`) devuelve los lados del **rectángulo mínimo envolvente**. Para una pieza rectangular es exacto. Para cualquier otra, sobreestima.

**29 de 34 piezas de `ejemplo.dxf` no son rectangulares.** Grado de llenado (área real / área del rectángulo envolvente):

| Llenado | Pieza | Área real | Rectángulo | "Lado corto" devuelto |
|---|---|---|---|---|
| 0,425 | Terraza | 11,55 m² | 27,22 m² | 3,63 m |
| 0,533 | Salón/cocina | 23,85 m² | 44,77 m² | 5,74 m |
| 0,620 | Salón/cocina | 23,38 m² | 37,71 m² | 5,73 m |
| 0,712 | Dormitorio 1 | 12,72 m² | 17,86 m² | 2,76 m |
| 0,806 | Baño | 4,00 m² | 4,96 m² | 1,93 m |

Un Salón/cocina en L de 23,85 m² recibe un rectángulo envolvente de 44,77 m². Su "lado corto" de 5,74 m no corresponde a ninguna dimensión física de la pieza.

**Siete reglas dependen de esta función**, y la sobreestimación las sesga todas hacia el falso negativo:

| Regla | Usa | Sesgo introducido |
|---|---|---|
| R01 proporción tubo | L/S | Ratio **menor** del real → no detecta tubos |
| R06 ancho de pasillo | S | Ancho **mayor** → no detecta pasillos estrechos |
| R08 baño 1,2 × 1,8 | L, S | Baño parece accesible sin serlo |
| R15a profundidad | S | Profundidad falsa |
| R18a giro de baño 1,50 | S | Baño parece tener giro sin tenerlo |
| R18b ancho de pieza 2,40 | S | **0 fallos de 16**; mínimo medido 2,63 m |
| R19 / R15b hueco | L | "Fachada" **mayor** → hueco inflado |

Caso concreto de fragilidad, medido en R15a: dos Salón/cocina fallan con profundidad 6,04 m contra un umbral de 6,0 m. **El hallazgo se decide por 4 cm** de una magnitud que, en piezas con llenado 0,53 y 0,87, no es la profundidad de nada.

Existe además un antecedente en el propio repositorio de que la técnica correcta se conoce: `spatial_quality._check_dead_space` usa apertura morfológica (`buffer(-0.3).buffer(0.3)`) para aislar zonas más estrechas que un umbral. Es exactamente la herramienta que R06, R18a y R18b necesitan.

---

## 10. F8 — R01 solo dispara en terrazas 🟠

Los 3 hallazgos de "habitación tubo" del plano completo:

```
VT6/2  Terraza  ratio=5,07  5,61 × 1,11 m  (4,93 m²)
VT6/2  Terraza  ratio=5,03  7,26 × 1,44 m  (5,36 m²)
VT6/2  Terraza  ratio=5,39  5,83 × 1,08 m  (6,30 m²)
```

`evaluate_proportions` (`evaluator.py:226`) excluye explícitamente "Pasillo" —*"una franja de circulación larga y estrecha es correcta arquitectónicamente"*— y no excluye Terraza ni Tendedero. Pero una terraza corrida de 1,1 m de fondo es tan normal como un pasillo: es la forma habitual de una terraza de fachada.

**El 100 % de los hallazgos de esta regla son falsos positivos**, y los tres se concentran en la vivienda que F1 ya identifica como mal parseada.

---

## 11. F9 y F10 — Umbrales inconsistentes y definiciones duplicadas 🟠

### 11.1 Umbrales que se contradicen

| Materia | Reglas en conflicto | Valores |
|---|---|---|
| Superficie de dormitorio | R00 (`RULES`, invisible) vs R20 (CRÍTICO) | D1>10 / D2>8 / D3>6 **vs** 6 individual / 10 doble |
| Accesibilidad de baño | R08 vs R18a vs R21 | 1,2×1,8 m **vs** lado ≥ 1,50 m **vs** 3,60 m² + 1,50 m |
| Anchura de circulación | R06 vs R18c | 0,90 m **vs** 1,20 m |
| Hueco de iluminación | R15b vs R19 | 1,5 % **vs** 12,5 % (misma medida) |

**Caso real medido**, el que demuestra que la primera fila no es teórica:

```
VT3/3  Dormitorio 2   7,17 m²
       R20 (visible, CRÍTICO):  mínimo 6,0 → pasa
       R00 (invisible, puntúa): mínimo 8,0 → FALLA
```

La puntuación de VT3/3 baja por un fallo que **ninguna incidencia explica**, mientras la regla que sí se muestra declara que esa misma pieza cumple el mínimo legal. Es la asimetría F11/H6 hecha caso concreto.

### 11.2 Definiciones duplicadas

**"Superficie útil" se calcula cuatro veces**, con la misma expresión copiada (`suma de áreas excepto TERRAZA|TENDEDERO`), en `evaluate_unit_efficiency` (:444), `evaluate_unit_minimum_area` (:818), `evaluate_circulation_efficiency` (:1217) y `scoring.py`. Cambiar el criterio exige tocar cuatro sitios. Y ninguno cita la norma de la que sale esa definición — la auditoría anterior ya señaló que no es la de ninguna fuente citada.

**"Lado corto" (`_bounding_sides`) significa siete cosas distintas** según quién lo llame: anchura de pasillo (R06), dimensión de accesibilidad de baño (R08), profundidad de habitación desde fachada (R15a), diámetro de giro (R18a), anchura habitable (R18b), anchura de itinerario (R18c) y, su lado largo, anchura de fachada (R19). Una única función geométrica sostiene siete conceptos arquitectónicos que no son el mismo. Cuando se corrija F7 para uno de ellos, habrá que decidir por separado para los siete.

**"Adyacencia" se define dos veces**, incompatiblemente: `evaluator._is_adjacent` (contacto de contornos > 0,3 m, que no dispara nunca) y `circulation._rooms_are_connected` (distancia < 0,5 m, validada). Conviven en el mismo análisis.

---

## 12. F11 y F12 — Cobertura y efecto de la puntuación 🟠

### 12.1 La puntuación depende de cuántas piezas se lean

`score_pct = comprobaciones superadas / comprobaciones totales`, y el total crece con el número de piezas:

| Vivienda | Piezas | Checks | Fallos | Score |
|---|---|---|---|---|
| VT1/3 | 7 | 48 | 4 | 91,7 |
| VT2/2 | 6 | 44 | 3 | 93,2 |
| VT3/3 | 6 | 44 | 4 | 90,9 |
| VT4/2 | 5 | 38 | 5 | 86,8 |
| VT5/1 | 3 | 26 | 5 | 80,8 |
| VT6/2 | 7 | 34 | 8 | 76,5 |

VT5/1 tiene 26 comprobaciones porque solo se leyeron 3 piezas: cada fallo pesa un 3,8 %, frente al 2,1 % de VT1/3. **Una vivienda peor parseada obtiene una puntuación con menos resolución y más volátil**, sin que nada lo advierta.

### 12.2 Reglas que no producen ningún hallazgo

Tasas de fallo medidas sobre el plano completo:

| Regla | Evaluadas | Fallan | | Regla | Evaluadas | Fallan |
|---|---|---|---|---|---|---|
| R00 basic | 21 | 1 | | R13 salón principal | 5 | **0** |
| R01 tubo | 34 | 3 | | R15a profundidad | 16 | 2 |
| R02 jerarquía | 5 | **0** | | R15b FLN | 16 | **0** |
| R03 útil/total | 6 | 1 | | R16a acústica | 11 | **0** |
| R05 fachada | 16 | **0** | | R17 evacuación | 16 | **0** |
| R06 pasillo | **0** | 0 | | R18a giro baño | 4 | 1 |
| R07 sup. vivienda | 6 | **0** | | R18b ancho 2,40 | 16 | **0** |
| R08 baño 1,2×1,8 | 4 | **0** | | R19 huecos 1/8 | 16 | 15 |
| R09 ratio baños | 6 | 2 | | R20 sup. dormitorio | 11 | **0** |
| R11 vent. cruzada | 6 | 2 | | R21 baño adaptado | 4 | 1 |
| R12 dist. entrada | **0** | 0 | | | | |

Dos reglas (R06, R12) **no llegan a evaluarse** porque dependen de una etiqueta "Pasillo" inexistente. Doce no producen ningún hallazgo. De esas doce, tres lo hacen por imposibilidad estructural (R16a, R17, y R15b por umbral inalcanzable) y el resto, presumiblemente, porque el proyecto cumple — pero con la salvedad de F7: R08, R18b y R20 miden con una función que sobreestima, así que su silencio no es prueba de cumplimiento.

---

## 13. Prioridad de corrección

Ordenada por impacto sobre la credibilidad ante un arquitecto, no por esfuerzo.

| # | Acción | Hallazgo | Esfuerzo |
|---|---|---|---|
| **1** | **Detectar solape entre piezas de una misma vivienda y rechazar el análisis o avisar.** Hoy `evaluate_fire_compartmentation` solo compara vivienda contra vivienda; el solape interno (27 m² en VT6/2) es invisible | F1 | 2 h |
| **2** | **Retirar R17 de las incidencias.** Un CRÍTICO de incendios que no puede disparar es peor que no tenerlo: afirma cumplimiento donde no hay comprobación | F3 | 1 h |
| **3** | **Convertir R18c y R16a en `no evaluable` cuando falta el dato**, en vez de en fallo y en silencio respectivamente | F4, F6 | 3 h |
| **4** | **Retirar R19 o R15b.** Dos umbrales sobre la misma medida, uno vacuo y otro universal, no son dos reglas | F5 | 1 h |
| **5** | **Añadir una regla de programa mínimo de vivienda** (debe existir zona de estar/cocina). Es el patrón que R09 ya aplica bien a los baños | F2 | 2 h |
| **6** | **Excluir Terraza y Tendedero de R01**, igual que ya se excluye Pasillo | F8 | 30 min |
| **7** | **Sustituir `_bounding_sides` por medidas específicas** en las siete reglas que la usan, decidiendo caso por caso qué mide cada una. Existe precedente en `spatial_quality._check_dead_space` | F7, F10 | PRD propio |
| **8** | **Unificar la definición de superficie útil** en una única función, y citar su fuente | F10 | 2 h |
| **9** | **Reconciliar R00 con R20** — o R00 deja de puntuar, o se hace visible | F9 | 2 h |
| **10** | **Normalizar la puntuación** para que no dependa del número de piezas leídas | F11 | PRD propio |

Las acciones 1-6, 8 y 9 son correcciones de comportamiento existente. Las 7 y 10 son cambios de capacidad y requieren PRD previo (`CLAUDE.md`).

**Las acciones 2, 3 y 4 se pueden hacer hoy y eliminan 21 de las 37 incidencias del proyecto de ejemplo** — todas ellas sin correspondencia con un defecto real del proyecto.

---

## 14. Qué no cubre esta auditoría

- **Un solo plano, de un solo estudio.** F1, F2, F4, F8 y las tasas de §12 dependen de este archivo. F3, F6, F7, F9 y F10 son estructurales y no.
- **No se ha auditado `/api/generar`.** Los proyectos generados por IA producen geometría sintética y rectangular, donde F7 no se manifiesta — lo que significa que el flujo de generación puede estar ocultando el problema en las pruebas.
- **No se han auditado `spatial_quality.py` ni `circulation.py`** más allá de sus interacciones con `evaluator.py`. La observación de la interfaz de que "Espacio muerto" dispara en 7 de 7 piezas de VT1/3, incluida una terraza, sugiere que un análisis equivalente daría hallazgos comparables.
- **No se ha verificado ninguna cita normativa.** Eso es `NORMATIVE_AUDIT.md` §6, y requiere validación de un arquitecto colegiado.

---

*Auditoría de solo lectura. Ninguna línea de código modificada. Todas las cifras proceden de la ejecución del motor sobre `ejemplo.dxf` en el commit `7a908e4`; las sondas quedan en el directorio temporal de la sesión y son reproducibles contra las funciones públicas del proyecto.*
