# NORMATIVE_AUDIT.md — Auditoría del motor de reglas normativas

**Fecha:** 2026-08-05 · **Autor:** auditoría técnica (arquitecto de software sénior) · **Código auditado:** commit `7a908e4`
**Alcance:** todo el código que aplica una regla sobre un proyecto y produce un juicio visible para el arquitecto.
**Restricción:** auditoría de solo lectura. **No se ha modificado ni una línea de código.**

---

## 0. Aviso previo sobre el contenido normativo

Este informe lo escribe un auditor de software, no un técnico competente en CTE. La distinción importa
para leerlo bien:

- **Los hallazgos estructurales son verificables en el código** (duplicación, hardcodeo, propagación de
  parámetros, asimetrías puntuación/incidencia, dependencias). Son hechos, y están citados con archivo y línea.
- **Los hallazgos de *cita normativa*** (§6) señalan discrepancias entre lo que el código afirma y lo que
  el Documento Básico citado regula por título. Están marcados como **CONFIRMAR** cuando la corrección
  final exige el criterio de un arquitecto colegiado. Ninguno debe corregirse en el código sin esa validación.

Ese matiz es, además, el propio problema de fondo del producto: hoy el código emite afirmaciones legales
categóricas con más seguridad de la que sus datos de entrada permiten.

---

## 1. Resumen ejecutivo

Se han inventariado **58 reglas** repartidas en 5 módulos. De ellas, **41 producen un juicio visible**
para el arquitecto (incidencia, puntuación o ambas).

| Hallazgo | Gravedad |
|---|---|
| **H1.** 4 grupos de reglas duplicadas evalúan el mismo objeto físico y producen incidencias separadas; el peor caso genera **2 CRÍTICOS sobre el mismo baño** | **Alta** — daña la credibilidad en la primera pantalla |
| **H2.** 3 reglas de habitabilidad (superficie mínima de vivienda, superficie mínima de dormitorio, huecos 1/8) están fijadas a un valor único, sin eje de comunidad autónoma, siendo competencia autonómica | **Alta** — incorrección legal fuera de la región implícita |
| **H3.** Las reglas 15b y 19 emiten afirmaciones legales sobre una superficie de hueco **inventada** (`ancho_fachada × 0.25`), y el cálculo es además **dimensionalmente incoherente** (m, no m²) | **Alta** — 15 de las 37 incidencias del proyecto de ejemplo salen de aquí |
| **H4.** 5 citas de Documento Básico no se corresponden con la materia que regula ese DB | **Alta** (CONFIRMAR) |
| **H5.** `classify_problems` se ejecuta **dos veces por análisis, con parámetros distintos**; la lista que ve la IA no es la que ve el arquitecto | Media |
| **H6.** Asimetría puntuación/incidencia: 6 reglas bajan la nota sin explicarse nunca; 6 generan incidencia sin afectar a la nota | Media |
| **H7.** 2 reglas fallan por **ausencia de dato**, no por incumplimiento (itinerario accesible, adyacencia acústica) | Media |
| **H8.** 41 umbrales escalares hardcodeados; solo 7 tienen resolución por contexto | Media |

**Verdicto de arquitectura:** el motor está bien escrito —módulos coherentes, docstrings honestos, proxies
declarados— pero su *modelo* de regla se agotó. Cada regla es un `if` imperativo con su umbral incrustado, y
la lógica de clasificación (`classify_problems`, 330 líneas) es una función-dios. Es exactamente el problema
que `docs/brain/CONSTRAINT_MODEL.md` ya diseñó para resolver; esta auditoría confirma empíricamente que esa
necesidad es real y no teórica.

---

## 2. Método y escala de confianza

Se usan dos ejes independientes, porque una cita puede ser correcta y la medición no serlo (y al revés).

**Eje A — Nivel de conocimiento** (escala propia del proyecto, `ARCHITECTURAL_KNOWLEDGE_MAP.md`):

| Nivel | Significado |
|---|---|
| **N1** | Hecho objetivo (geometría medible sin interpretación) |
| **N2** | Normativa verificable (umbral legal explícito y citable) |
| **N3** | Buena práctica (criterio profesional consensuado, no legal) |
| **N4** | Criterio arquitectónico (sin respuesta única correcta) |

**Eje B — Confianza de medición** (¿los datos de entrada soportan la comprobación?):

| Nivel | Significado |
|---|---|
| **Alta** | Se mide directamente sobre la geometría del DXF |
| **Media** | Proxy geométrico razonable, declarado como tal |
| **Baja** | El dato necesario **no existe**; se sustituye por una suposición |

**Confianza efectiva = la menor de las dos** (regla del eslabón más débil, `docs/brain/EVIDENCE_MODEL.md`).
Una regla N2/Baja es el peor caso del sistema: afirma cumplimiento legal sobre un dato inventado.

---

## 3. Inventario completo de reglas

### 3.1 `analyzer/evaluator.py` — motor CTE principal (2.966 líneas, 35 reglas)

Leyenda de columnas: **Cód.** = valor de `IssueReport.codigo`; **Art.** = ¿cita artículo/apartado concreto?;
**Punt.** = ¿entra en `score_pct`?; **Inc.** = ¿genera `IssueReport` visible?

| # | Regla | Función · línea | Normativa que representa | Cód. emitido | Art. | Punt. | Inc. | Umbral | A | B |
|---|---|---|---|---|---|---|---|---|---|---|
| R00 | Superficie mínima por etiqueta (Salón 20, D1 10, D2 8, D3 6, Baño 3, Aseo 1.5 m²) | `RULES` :69 · `evaluate_room` :79 | Habitabilidad autonómica (implícito) | — | ❌ | ✅ | ❌ | 6 valores :70-75 | N2 | Alta |
| R01 | Proporción "tubo" ≤ 1:2.5 | `evaluate_proportions` :226 | Ninguna — heurística de diseño | `HABITABILIDAD` | ❌ | ✅ | ✅ | `MAX_ASPECT_RATIO` :182 | N3 | Alta |
| R02 | Jerarquía D1 > D2 > D3 | `evaluate_dormitory_hierarchy` :388 | Ninguna — convención de proyecto | `HABITABILIDAD` | ❌ | ✅ | ✅ | — | N4 | Alta |
| R03 | Ratio útil/total ≥ 80 % | `evaluate_unit_efficiency` :444 | Ninguna — criterio comercial | `EFICIENCIA` | ❌ | ✅ | ✅ | `MIN_USEFUL_RATIO` :420 | N3 | Alta |
| R04 | Orientación por uso de pieza | `evaluate_orientation` :595 | DB-HE (implícito) | — | ❌ | ✅ | ❌ | `ORIENTATION_RULES` :474 | N3 | Media |
| R05 | Pieza habitable con fachada exterior | `evaluate_natural_light` :708 | CTE DB-HS3 | `CTE-DB-HS` | ❌ | ✅ | ✅ | — | N2 | Media |
| R06 | Ancho mínimo de pasillo | `evaluate_corridor_width` :750 | CTE DB-SUA | `CTE-DB-SUA-1` | ❌ | ✅ | ✅ | 0.90/0.80 m :782-795 | N2 | Alta |
| R07 | Superficie útil mínima de vivienda | `evaluate_unit_minimum_area` :818 | LOE / decreto autonómico | `CTE-DB-HE` ⚠️ | ❌ | ✅ | ✅ | 30/40/24 m² :782-795 | N2 | Alta |
| R08 | Baño accesible ≥ 1.2 × 1.8 m (agregado) | `evaluate_bathroom_accessibility` :864 | CTE DB-SUA | `CTE-DB-SUA-1` | ❌ | ✅ | ✅ | :841-842 | N2 | Media |
| R09 | Ratio dormitorios/baños | `evaluate_bathroom_ratio` :906 | Ninguna — buena práctica | `CTE-DB-HS` ⚠️ | ❌ | ✅ | ✅ | `bathroom_ratio_strict` :784 | N3 | Alta |
| R10 | Horas de sol estimadas | `evaluate_solar_hours` :992 | DB-HE (orientativo) | — | ❌ | ❌ | ❌ | `SOLAR_HOURS_TABLE` :944 | N3 | Baja |
| R11 | Ventilación cruzada | `evaluate_cross_ventilation` :1068 | CTE DB-HS3 | `CTE-DB-HS3` | ❌ | ✅ | ✅ | — | N2 | Media |
| R12 | Distancia entrada→dormitorio ≤ 5 m | `evaluate_entry_distance` :1124 | Ninguna — heurística | `EFICIENCIA` | ❌ | ❌ | ✅ | :1105 | N4 | Media |
| R13 | El salón debe ser la pieza mayor | `evaluate_spatial_hierarchy` :1177 | Ninguna — criterio | `EFICIENCIA` | ❌ | ✅ | ✅ | — | N4 | Alta |
| R14 | Pasillo ≤ 15 % de superficie útil | `evaluate_circulation_efficiency` :1217 | Ninguna — criterio | `EFICIENCIA` | ❌ | ❌ | ✅ | :1198 | N3 | Alta |
| R15a | Profundidad de pieza ≤ 6 m | `evaluate_natural_lighting` :1295 | DB-HS (implícito) | `CTE-DB-HS` | ❌ | ✅ | ✅ | `MAX_ROOM_DEPTH_M` :1251 | N3 | Alta |
| R15b | Factor de luz natural ≥ 1.5 % | `evaluate_natural_lighting` :1295 | DB-HE | `CTE-DB-HS` | ❌ | ✅ | ✅ | :1252-1253 | N3 | **Baja** |
| R16a | Dormitorio no adyacente a baño/aseo | `evaluate_acoustic_adjacency` :1384 | CTE DB-HR (Rw ≥ 45 dB) | `CTE-DB-HR` | ✅ (Rw) | ❌ | ✅ | :1355 | N2 | **Baja** |
| R16b | Exposición a ruido exterior | `evaluate_acoustic_exposure` :1431 | CTE DB-HR | `CTE-DB-HR` | ❌ | ❌ | ✅¹ | :1408-1409 | N3 | Baja |
| R16c | Riesgo de condensaciones fachada N | `evaluate_condensaciones` :1492 | CTE DB-HE | `CTE-DB-HE-COND` | ❌ | ❌ | ✅ | :1474-1475 | N3 | Baja |
| R17 | Recorrido de evacuación ≤ 25 m | `evaluate_evacuation_distance` :1539 | CTE DB-SI | `CTE-DB-SI-3` | ❌ | ✅ | ✅ | :1518 | N2 | Media |
| R18a | Espacio de giro en baño ≥ 1.50 m | `evaluate_bathroom_turning_space` :1593 | CTE DB-SUA | `CTE-DB-SUA-1` | ❌ | ✅ | ✅ | 1.50/1.20 :782-795 | N2 | Media |
| R18b | Anchura de pieza habitable ≥ 2.40 m | `evaluate_minimum_room_width` :1642 | Proxy de accesibilidad | `CTE-DB-SUA` | ❌ | ✅ | ✅ | :1622 | N3 | Alta |
| R18c | Itinerario accesible ≥ 1.20 m | `evaluate_itinerario_accesible` :1684 | CTE DB-SUA | `CTE-DB-SUA-2-ITIN` ⚠️ | ✅ (SUA-2) | ❌ | ✅ | :1669 | N2 | **Baja** |
| R19 | Huecos ≥ 1/8 de superficie útil | `evaluate_window_opening_ratio` :1738 | DB-HS3 + decretos autonómicos | `CTE-DB-HS3` ⚠️ | ✅ (1/8) | ✅ | ✅ | :1716 + :1253 | N2 | **Baja** |
| R20 | Superficie mínima de dormitorio (6/10 m²) | `evaluate_bedroom_minimum_area` :1810 | LOE / decreto autonómico | `HABITABILIDAD-SUP` | ❌ | ✅ | ✅ | :1787-1788 | N2 | Media |
| R21 | Baño adaptado ≥ 3.60 m² + ⌀1.50 | `evaluate_accessible_bathroom_area` :1873 | Guías técnicas de accesibilidad | `CTE-DB-SUA-1` ⚠️ | ❌ | ✅ | ✅ | :1851 | N2 | Media |
| R22 | Ocupación de solar | `evaluate_solar_occupation` :2609 | Planeamiento municipal | `URBANISMO-OC` | n/a | ❌ | ✅ | parámetro | N2 | Alta² |
| R23 | Edificabilidad | `evaluate_buildability` :2646 | Planeamiento municipal | `URBANISMO-ED` | n/a | ❌ | ✅ | parámetro | N2 | Alta² |
| R24 | Nº máximo de plantas | `evaluate_max_floors` :2683 | Planeamiento municipal | `URBANISMO-AL` | n/a | ❌ | ✅ | parámetro | N2 | Alta² |
| R25 | Retranqueos | `evaluate_retranqueos` :2717 | Planeamiento municipal | `URBANISMO-RETR` | n/a | ❌ | ✅ | margen 3 m :2735 | N2 | **Baja** |
| R26 | Sectorización de incendios (solape) | `evaluate_fire_compartmentation` :2773 | CTE DB-SI | `CTE-DB-SI-3` ⚠️ | ❌ | ❌ | ✅ | :2754 | N1 | Alta³ |
| R27 | Altura libre ≥ 2.50 m | `evaluate_ceiling_height` :2828 | DB-SUA / decreto autonómico | `CTE-DB-SUA-1` ⚠️ | ❌ | ❌ | ✅ | :112 | N2 | Alta² |
| R28 | Compacidad del edificio | `evaluate_building_compactness` :2893 | CTE DB-HE | `EFICIENCIA-ENE` | ❌ | ❌ | ✅ | `UMBRALES_ZONA` :958 | N3 | **Baja**⁴ |
| R29 | ≥ 40 % de superficie a sur | `evaluate_building_orientation_ratio` :2942 | CTE DB-HE (pasivo) | `EFICIENCIA-ENE` | ❌ | ❌ | ✅ | :2924 | N3 | Media |

¹ Solo si `densidad_urbana == "alta"`. ² Alta si el arquitecto informa el parámetro; si no, la regla no se
evalúa (correcto). ³ Alta como condición *necesaria*; no verifica EI-60, que sigue sin ser evaluable.
⁴ El perímetro está sobreestimado por construcción — advertencia explícita en `compute_floor_perimeter_m` :2862.

**Reglas informativas sin juicio** (correcto que no puntúen ni generen incidencia):
`get_missing_data_warnings` :116 — 10 avisos de "no evaluable". **Es la mejor pieza de honestidad del
repositorio** y hoy está infrautilizada en la interfaz.

### 3.2 `analyzer/spatial_quality.py` — calidad de diseño (5 reglas, ninguna normativa)

| # | Regla | Función · línea | Normativa | Cód. | Umbral | A | B |
|---|---|---|---|---|---|---|---|
| S1 | Proporción tubo | `_check_tubo` :121 | Ninguna | n/a | reusa `MAX_ASPECT_RATIO` | N3 | Alta |
| S2 | Profundidad de luz diurna | `_check_daylight_depth` :152 | Ninguna | n/a | 1.30 m × 2.5 :148-149 | N3 | **Baja** |
| S3 | Escala humana | `_check_human_scale` :193 | Ninguna | n/a | `HUMAN_SCALE_RANGES` :185 | **N4** | Baja |
| S4 | Espacio muerto | `_check_dead_space` :234 | Ninguna | n/a | 0.6 m :225 | N3 | Alta |
| S5 | Jerarquía espacial | `_issues_from_hierarchy` :274 | Ninguna | n/a | envuelve R02 | N4 | Alta |

Separación correcta: este módulo **no emite ningún código normativo**, tal como exige el diseño. Es la
decisión de arquitectura más acertada del motor y debe preservarse.

**Pero:** S3 (escala humana) es N4 puro — un rango inventado en una sesión de diseño, sin fuente— y se
presenta al usuario con el mismo peso visual que S4. Y **S4 es el mayor generador de ruido del producto**:
en `ejemplo.dxf` dispara en 7 de 7 habitaciones de VT1/3, incluida la terraza.

### 3.3 `analyzer/circulation.py` — grafo de circulación (5 reglas, ninguna normativa)

| # | Regla | Función · línea | Normativa | Umbral | A | B |
|---|---|---|---|---|---|---|
| C1 | Recorridos absurdos (dormitorio→baño cruzando salón) | `_check_absurd_routes` :223 | Ninguna | — | N3 | Media |
| C2 | Pasillos sobredimensionados | `_wrap_oversized_corridor` :263 | Ninguna | envuelve R14 | N3 | Alta |
| C3 | Espacios de paso | `_check_pass_through_rooms` :286 | Ninguna | — | N3 | Media |
| C4 | Baño sin antesala | `_check_bathroom_access` :319 | Ninguna | `WALL_GAP_TOLERANCE_M` :131 | N3 | Media |
| C5 | Recorrido de evacuación (por grafo) | `_check_evacuation_route` :344 | CTE DB-SI (umbral) | reusa `MAX_EVACUATION_DISTANCE_M` | N2 | Media |

**C5 es el caso más delicado del módulo:** consume un umbral legal (25 m) pero el módulo entero se
presenta como no normativo. Mide lo mismo que R17 con otro método y puede discrepar.

### 3.4 `analyzer/chain_effects.py` — efectos derivados (6 reglas, 0 cálculos propios)

Ninguna calcula un `passed`; todas envuelven resultados existentes. **Pero sí emiten códigos normativos
propios** (`normativa_relacionada`), 17 en total, ninguno con artículo.

| # | Regla | Función · línea | Origen que envuelve | Cód. |
|---|---|---|---|---|
| E1 | Pasillo estrecho | `_regla_pasillo_estrecho` :63 | **recalcula** R18c | `CTE-DB-SUA-2-ITIN` |
| E2 | Sin ventilación cruzada | `_regla_sin_ventilacion_cruzada` :106 | R11 | `CTE-DB-HS3` |
| E3 | Baño sin antesala | `_regla_bano_sin_antesala` :150 | C4 | `HABITABILIDAD-CIRC` |
| E4 | Habitación tubo | `_regla_habitacion_tubo` :192 | R01 | `HABITABILIDAD` |
| E5 | Dormitorio a norte | `_regla_dormitorio_norte` :237 | R04 | `CTE-DB-HE-ORIENT` |
| E6 | Sin baño adaptado | `_regla_sin_bano_adaptado` :280 | R21 | `CTE-DB-SUA-1` |

Cada una añade 2-3 `EfectoDerivado` con severidad y **coste estimado** (`impacto_coste_estimado`:
"Bajo <500€" / "Medio 500-3000€" / "Alto >3000€", :101 y ss.). **Esos rangos de coste no proceden de
ninguna fuente** — son constantes literales dentro de cada regla. Es la misma clase de fabricación que
`TIPOLOGIA_BENCHMARKS`, en un sitio distinto y todavía no retirado.

### 3.5 `analyzer/scoring.py` — no aplica normativa, la reinterpreta

| Elemento | Línea | Observación |
|---|---|---|
| `CATEGORY_WEIGHTS` (6 categorías) | :41 | Pesos sin justificación documentada |
| `DEDUCTION_BY_SEVERITY` (15/7/2) | :50 | Deducción lineal por incidencia |
| `categoria_for` | :57 | Clasifica por **prefijo de string** del código |
| `TIPOLOGIA_BENCHMARKS` | :209 | **Tabla fabricada**, 3 puntos escritos a mano |
| `estimar_percentil` | :216 | Sigue calculándose y **sigue viajando en el JSON** |

**`categoria_for` es frágil por diseño:** clasifica reglas por el prefijo textual del código. Consecuencia
directa medida en `ejemplo.dxf`: R09 (ratio de baños, un criterio de confort **sin base legal**) emite
`CTE-DB-HS` y por tanto puntúa en la categoría "Iluminación y ventilación". Un cambio de literal en un
código reasigna silenciosamente el peso de una categoría entera.

Sobre el percentil: se retiró de la interfaz (`static/app.js` :1994) —decisión correcta— pero
`estimar_percentil` sigue vivo y `percentil_estimado` sigue en el payload de `/api/proyectos/<id>`
(verificado: `{"percentil": 40, "top_pct": 60}`). El dato fabricado ya no se enseña, pero se sigue
sirviendo y se sigue guardando en la base de datos.

---

## 4. Reglas duplicadas

### D1 — Accesibilidad de baño: **tres reglas sobre el mismo objeto** 🔴

| Regla | Línea | Comprueba | Severidad |
|---|---|---|---|
| R08 | :864 | ≥ 1.2 × 1.8 m en al menos un baño | CRÍTICO |
| R18a | :1593 | lado corto ≥ 1.50 m, **por cada** baño | CRÍTICO |
| R21 | :1873 | ≥ 3.60 m² **y** lado corto ≥ 1.50 m, en al menos un baño | CRÍTICO |

R18a y R21 comparten `MIN_BATHROOM_TURNING_SPACE_M`; R21 es R18a más una condición de superficie. Un baño
que falla R21 casi siempre falla R18a. **Verificado en la interfaz:** VT1/3 muestra "Baño sin superficie ni
giro de baño adaptado" y "Baño sin espacio de giro para accesibilidad" como dos CRÍTICOS distintos, y
`compute_puntos_ganados` asigna **+2.3 puntos a cada uno** — el mismo defecto se penaliza dos veces y se
promete dos veces la misma recompensa por arreglarlo.

Los docstrings de R18a y R21 documentan la distinción con precisión. El problema no es que el programador
no lo supiera: es que **la distinción no sobrevive al viaje hasta la pantalla**.

### D2 — Superficie de hueco: mismo proxy, dos umbrales 🔴

| Regla | Línea | Umbral | Emite |
|---|---|---|---|
| R15b | :1295 | FLN ≥ 1.5 % | "Factor de luz natural insuficiente" |
| R19 | :1738 | ratio ≥ 12.5 % | "Superficie de huecos insuficiente (regla 1/8)" |

Ambas calculan `long_side × WINDOW_TO_FACADE_RATIO / area`. **Es literalmente la misma expresión** (:1345 y
:1755) con dos constantes de comparación distintas. Toda habitación que falla R15b falla R19; el recíproco
no. Documentado como deliberado en :1705-1714, pero para el arquitecto son dos incidencias sobre la misma
ventana inexistente.

Impacto medido: **15 de las 37 incidencias del proyecto de ejemplo (41 %) proceden solo de R19.**

### D3 — Superficie mínima de dormitorio: dos criterios simultáneos 🟠

| Regla | Línea | Criterio | Visible |
|---|---|---|---|
| R00 | :69 | Por **posición** (D1 > 10, D2 > 8, D3 > 6 m²) | ❌ solo puntúa |
| R20 | :1810 | Por **ocupación** (6 individual / 10 doble) | ✅ CRÍTICO |

Ambas se ejecutan sobre cada dormitorio. Con etiquetas sin "Doble" —el caso normal— R20 exige 6 m² y R00
exige 10 m² al Dormitorio 1: **R00 es más estricta que la regla que el sistema presenta como "el mínimo
legal"**, y falla en silencio. Un Dormitorio 1 de 8 m² baja la nota sin que aparezca ninguna incidencia
que lo explique.

### D4 — Recorrido de evacuación: dos mediciones del mismo umbral 🟠

R17 (:1539, distancia recta al borde) y C5 (`circulation.py` :344, Dijkstra sobre el grafo) comparten
`MAX_EVACUATION_DISTANCE_M = 25.0`. Métodos distintos, resultados potencialmente contradictorios sobre la
misma vivienda, presentados en pestañas distintas ("Problemas" vs. "Circulación") sin referencia cruzada.

### D5 — Proporción tubo y jerarquía: cálculo repetido 🟡

R01/S1 (tubo) se calculan dos veces de forma independiente con la misma constante; R02/S5 (jerarquía) se
envuelve correctamente. La habitación tubo aparece hoy en tres sitios: Problemas (R01), Calidad Espacial
(S1) y Efectos en Cadena (E4).

### D6 — `classify_problems` recalcula dos reglas dentro de sí misma 🟠

`evaluate_condensaciones` (:2072) y `evaluate_itinerario_accesible` (:2083) **se invocan desde dentro de
`classify_problems`**, no desde `score_unit`. No se guardan en `UnitScore`, no entran en `checks`, y
`chain_effects._regla_pasillo_estrecho` (:66) las vuelve a llamar por tercera vez. Tres cálculos del mismo
predicado en un solo análisis.

---

## 5. Valores hardcodeados

### 5.1 Los únicos 7 umbrales con resolución por contexto

| Umbral | Tabla | Ejes |
|---|---|---|
| `min_unit_area_m2` (30/40/24) | `UMBRALES_TIPOLOGIA` :782 | tipología |
| `bathroom_ratio_strict` | `UMBRALES_TIPOLOGIA` :782 | tipología |
| `corridor_width_min` (0.90/0.80) | `UMBRALES_TIPOLOGIA` :782 | tipología |
| `turning_space_min` (1.50/1.20) | `UMBRALES_TIPOLOGIA` :782 | tipología |
| `compact_ratio_min` | `UMBRALES_ZONA` :958 | zona CTE |
| `solar_hours_good_winter` | `UMBRALES_ZONA` :958 | zona CTE |
| `solar_hours_acceptable_winter` | `UMBRALES_ZONA` :958 | zona CTE |

Además, la severidad de R08/R21 se modula por tipología (:1987). **Y nada más.**

### 5.2 Los 41 umbrales escalares sin contexto

| Constante | Línea | Valor | ¿Debería tener eje? |
|---|---|---|---|
| `MIN_CEILING_HEIGHT_M` | :112 | 2.5 m | **CCAA** |
| `MIN_STAIR_WIDTH_M` | :113 | 1.0 m | CCAA |
| `MAX_ASPECT_RATIO` | :182 | 2.5 | no (heurística) |
| `MAX_GAP_BETWEEN_ROOMS_M` | :301 | 2.0 m | no (parsing) |
| `MIN_USEFUL_RATIO` | :420 | 0.80 | no (criterio) |
| `MIN_CORRIDOR_WIDTH_M` | :730 | 0.9 m | ya tiene tipología |
| `ACCESSIBLE_BATHROOM_MIN_SHORT/LONG_M` | :841-842 | 1.2 / 1.8 m | **CCAA** |
| `SOLAR_HOURS_TABLE` | :944 | 8 pares | **latitud** |
| `MAX_ENTRY_DISTANCE_M` | :1105 | 5.0 m | no |
| `MAX_CIRCULATION_RATIO` | :1198 | 0.15 | no |
| `MAX_ROOM_DEPTH_M` | :1251 | 6.0 m | **CCAA** |
| `MIN_NATURAL_LIGHT_FACTOR_PCT` | :1252 | 1.5 % | — |
| `WINDOW_TO_FACADE_RATIO` | :1253 | **0.25** | **ver §6.3** |
| `_ADJACENCY_MIN_LENGTH_M` | :1355 | 0.3 m | no |
| `_CONDENSATION_RISK_ZONAS` | :1475 | {D, E} | ya usa zona |
| `MAX_EVACUATION_DISTANCE_M` | :1518 | 25 m | **uso + rociadores** |
| `MIN_BATHROOM_TURNING_SPACE_M` | :1573 | 1.50 m | ya tiene tipología |
| `MIN_HABITABLE_ROOM_WIDTH_M` | :1622 | 2.40 m | **CCAA** |
| `MIN_ITINERARIO_ACCESIBLE_M` | :1669 | 1.20 m | CCAA |
| `MIN_WINDOW_TO_FLOOR_RATIO` | :1716 | 1/8 | **CCAA** |
| `BEDROOM_MIN_AREA_INDIVIDUAL/DOUBLE_M2` | :1787-1788 | 6 / 10 m² | **CCAA** |
| `ACCESSIBLE_BATHROOM_MIN_AREA_M2` | :1851 | 3.60 m² | **CCAA** |
| `SCORE_GREEN/YELLOW_THRESHOLD` | :1899-1900 | 85 / 70 | no |
| `FIRE_COMPARTMENTATION_OVERLAP_TOLERANCE_M2` | :2754 | 0.01 m² | no |
| `MIN_CEILING_HEIGHT_COMMON_M` | :2810 | 2.20 m | CCAA |
| `MIN_SOUTH_FACING_RATIO_PCT` | :2924 | 40 % | no |
| margen de retranqueo | :2735 | 3 m | **municipal** |
| `ASSUMED_WINDOW_HEIGHT_M` | sq :148 | 1.30 m | — |
| `DAYLIGHT_DEPTH_FACTOR` | sq :149 | 2.5 | — |
| `HUMAN_SCALE_RANGES` | sq :185 | 4 rangos | inventados |
| `DEAD_SPACE_MIN_WIDTH_M` | sq :225 | 0.6 m | no |
| `SCORE_IMPACT_*` (5) | sq :73-77 | 15/20/10/30/10 | sin justificar |
| `WALL_GAP_TOLERANCE_M` | circ :131 | 0.5 m | no (validado) |
| `SCORE_IMPACT_*` (5) | circ :66-70 | 15/10/15/10/20 | sin justificar |
| `CATEGORY_WEIGHTS` (6) | sc :41 | pesos | sin justificar |
| `DEDUCTION_BY_SEVERITY` (3) | sc :50 | 15/7/2 | sin justificar |
| `TIPOLOGIA_BENCHMARKS` | sc :209 | **fabricado** | — |
| rangos de coste (3) | ce :101 y ss. | **fabricados** | — |

### 5.3 El hallazgo estructural: **no existe eje de comunidad autónoma** 🔴

Ninguna regla del motor conoce la comunidad autónoma. Sin embargo, al menos **6 de los umbrales marcados
arriba pertenecen a decretos autonómicos de habitabilidad**, que difieren entre comunidades: superficie
mínima de vivienda, superficie mínima de dormitorio, altura libre, anchura mínima de pieza, superficie de
hueco 1/8 y superficie de baño adaptado.

El formulario ya pide **ciudad** (`app.py` :154) y ya existe un mapa ciudad→zona (`cte_zonas.py` :12). El
dato para deducir la CCAA **ya está en el sistema**; simplemente ningún umbral lo consulta. La consecuencia
práctica: ArchMuse emite hoy un juicio de cumplimiento legal calibrado para una región implícita, sobre
proyectos de cualquier punto de España, sin decirlo.

`docs/brain/CONSTRAINT_MODEL.md` §9 ya diseñó exactamente la solución (tabla de parámetros multi-eje con
cadena de repliegue registrada en la Evidence). Este informe confirma que ese diseño ataca un problema real
y medible, no hipotético.

---

## 6. Citas normativas

### 6.1 Cobertura de artículo

De las 41 reglas con juicio visible:

- **0 citan un artículo o apartado concreto** en un campo estructurado.
- 3 mencionan una cifra normativa dentro del texto libre del mensaje (Rw ≥ 45 dB en R16a; 1/8 en R19; SUA-2 en R18c).
- 38 emiten como mucho el nombre del Documento Básico.

`IssueReport.codigo` (:1927) se documenta como "código normativo" pero su contenido real es una **etiqueta
de agrupación**, no una referencia: `HABITABILIDAD`, `EFICIENCIA`, `URBANISMO-OC` no son códigos de nada.
Y `scoring.categoria_for` (:57) los usa como si fueran taxonomía estable.

Esto choca de frente con el argumento de venta declarado en `MOAT_ANALYSIS.md` §1 — *"cada aviso cita el
artículo CTE real"*. **Hoy eso no es cierto de ninguna regla.**

### 6.2 Discrepancias entre código emitido y materia regulada — **CONFIRMAR**

| # | Regla | Código emitido | Materia del DB citado | Discrepancia |
|---|---|---|---|---|
| M1 | R07 superficie mínima de vivienda | `CTE-DB-HE` | DB-HE = Ahorro de energía | La superficie mínima de vivienda no es materia de DB-HE. Es LOE/decreto autonómico — como el propio docstring (:775) reconoce. **La cita contradice al comentario que la encabeza.** |
| M2 | R18c itinerario accesible | `CTE-DB-SUA-2-ITIN` | DB-SUA-2 = Impacto y atrapamiento | La accesibilidad es materia de DB-SUA-9. Aparece además en `chain_effects` :72 y :86. |
| M3 | R26 sectorización de incendios | `CTE-DB-SI-3` | DB-SI-3 = Evacuación de ocupantes | Los sectores de incendio se definen en DB-SI-1 (propagación interior). SI-3 es correcto para R17, no para R26 — **ambas emiten el mismo código**. |
| M4 | R08/R18a/R21 accesibilidad de baño | `CTE-DB-SUA-1` | DB-SUA-1 = Riesgo de caídas | Materia de DB-SUA-9 y del RD 173/2010. Mismo código en R27 (altura libre). |
| M5 | R09 ratio dormitorios/baños | `CTE-DB-HS` | DB-HS = Salubridad | El propio docstring (:906) dice *"se recomienda"*: es criterio de confort **sin base legal**, emitiendo un código CTE. |

M5 es la más grave de las cinco en términos de producto: convierte una preferencia en una cita normativa.
M3 es la más grave en términos de consecuencia: el mismo código para dos exigencias distintas hace
imposible trazar cuál se está incumpliendo.

### 6.3 La superficie de hueco: proxy inventado **y** error dimensional 🔴

```python
# evaluator.py:1252-1253
MIN_NATURAL_LIGHT_FACTOR_PCT = 1.5
WINDOW_TO_FACADE_RATIO = 0.25  # % de la fachada asumido como hueco de ventana

# evaluator.py:1336-1338 (R15b)
facade_width_m = long_side
window_area_m2 = facade_width_m * WINDOW_TO_FACADE_RATIO
fln_pct = window_area_m2 / room.area_m2 * 100

# evaluator.py:1759-1760 (R19) — misma expresión, sin la variable intermedia
window_area_m2 = long_side * WINDOW_TO_FACADE_RATIO
ratio = window_area_m2 / room.area_m2
```

Dos problemas independientes, ambos verificables leyendo esas tres líneas:

**(a) El dato no existe.** El DXF no contiene carpintería. El 0.25 es una suposición global aplicada a
todas las piezas de todos los proyectos. Está declarado con honestidad en los docstrings, pero el mensaje
que llega al arquitecto no lo está: la ficha de la incidencia dice *"hueco de iluminación **estimado** 9.4 %"*
en la explicación —correcto— y a renglón seguido, en Impacto, *"**Incumple** el mínimo legal de iluminación
natural directa de la pieza; puede impedir obtener cédula de habitabilidad"* (:2137). Una estimación
en un párrafo se convierte en un incumplimiento legal categórico en el siguiente.

**(b) Las unidades no cuadran.** `facade_width_m` está en metros. Multiplicado por un ratio adimensional
sigue estando **en metros**, no en m² — pese al nombre `window_area_m2`. El cociente resultante es
m / m², que no es un porcentaje de nada. La regla *funciona* como discriminante monótono (penaliza
habitaciones profundas frente a anchas) pero **el número que enseña no significa lo que dice significar**, y
compararlo contra un umbral legal expresado en porcentaje de superficie (1/8) no es válido dimensionalmente.

Esto explica por qué R19 falla en 15 de 16 comprobaciones sobre `ejemplo.dxf`: el umbral del 12.5 % se está
comparando contra una magnitud que no es ese porcentaje. **No es una calibración agresiva: es una
comparación entre magnitudes distintas.**

Es el hallazgo más importante de esta auditoría. Afecta al 41 % de las incidencias del proyecto de ejemplo,
en una regla que cita el CTE y menciona la cédula de habitabilidad.

---

## 7. Hallazgos estructurales adicionales

### 7.1 `classify_problems` se ejecuta dos veces con parámetros distintos 🟠

| Invocación | Línea | `zona_cte` | Destino |
|---|---|---|---|
| A | `app.py` :167 | **no se pasa** → `"C"` por defecto | `issues_criticos` → prompt de la IA |
| B | `api_serializer.py` :234 | sí, desde `proyecto` | `issues` → interfaz y PDF |

La lista B es correcta. La lista A, para un proyecto en Madrid (zona D), se calcula como si fuera zona C.
Hoy el impacto práctico es nulo —`zona_cte` solo afecta a R16c, que es IMPORTANTE, y A solo filtra
CRÍTICOS— pero es una trampa armada: **cualquier regla futura de severidad CRÍTICO que dependa de la zona
hará que la IA redacte su diagnóstico sobre un conjunto de problemas distinto del que ve el arquitecto**,
en silencio. Es la misma familia que el Bug #1 de `TECH_REVIEW.md`, resuelto en la ruta principal y
superviviente en la secundaria.

### 7.2 Dos recuentos de problemas en el mismo payload 🟠

`total_problemas` (`api_serializer.py` :228, cuenta `room_problems` + eficiencia) y
`issues_summary.total` (:247, cuenta `IssueReport`) miden cosas distintas y ambos viajan en el mismo JSON.
Verificado en `ejemplo.dxf`: **26 frente a 37.**

### 7.3 Asimetría puntuación / incidencia 🟠

**Bajan la nota y nunca se explican** (en `checks`, no en `classify_problems`):
R00, R04, R10 (informativo pero listado en `score_unit` :2337), y la mitad de los `basic_results`.

**Generan incidencia y no tocan la nota** (en `classify_problems`, no en `checks`):
R12, R14, R16a, R16b, R16c, R18c.

Consecuencia directa, verificada en la interfaz: VT1/3 muestra **92 / "Cumplimiento correcto"** junto a
**2 CRÍTICOS**, y el proyecto entero muestra `valoracion_global: "verde"` con 87 puntos y 2 CRÍTICOS.
Ningún arquitecto que firme un proyecto acepta que "cumplimiento correcto" y "crítico de accesibilidad"
convivan en la misma pantalla. El origen es estructural: `score_pct` es un porcentaje de comprobaciones
superadas —donde 2 fallos entre 30 dan 93— y `valoracion_global` se deriva de él sin que ninguna severidad
pueda vetarlo.

`BRAIN_ARCHITECTURE.md` ya prescribió el remedio: veredicto en tres capas separadas (viabilidad binaria /
riesgo ponderado / calidad no bloqueante), sin colapsar a un número hasta la presentación final. Esta
pantalla es la demostración de por qué esa decisión era correcta.

### 7.4 Dos reglas fallan por ausencia de dato 🟠

**R18c — itinerario accesible** (:1684): recorre las piezas buscando un "Pasillo" ≥ 1.20 m; si **no hay
ninguna pieza etiquetada "Pasillo"**, devuelve fallo. Una vivienda sin pasillo —planta abierta, o
simplemente un plano cuyo autor no rotuló el distribuidor— se declara sin itinerario accesible. En
`ejemplo.dxf`, donde ninguna de las 6 viviendas usa esa etiqueta, esto produce **6 incidencias, una por
vivienda**: el segundo mayor generador de ruido del producto, y es puramente artefacto de etiquetado.

**R16a — adyacencia acústica** (:1384): exige `_shared_edge_length > 0.3 m`, es decir, contacto literal
entre contornos. En DXF reales las habitaciones se dibujan a cara interior de muro y **nunca se tocan**
(hueco de 0.03-0.38 m). La regla no puede fallar nunca sobre datos reales — falso negativo silencioso.
`circulation._rooms_are_connected` (:134) ya resuelve esto con un umbral de distancia validado; R16a nunca
se migró.

Las dos son la misma patología con signo opuesto, y las dos son exactamente lo que
`docs/brain/INFERENCE_ENGINE.md` prohíbe: **conclusión negativa derivada de un dato ausente**, en vez de
un `Unknown` declarado.

---

## 8. Recomendaciones priorizadas

Ninguna se ha aplicado. Las tres primeras son correcciones de veracidad; el resto es deuda estructural.

| # | Acción | Archivo | Esfuerzo |
|---|---|---|---|
| **1** | **Retirar R19 de la lista de incidencias hasta resolver §6.3.** Es indefendible ante un arquitecto: cita el CTE, menciona la cédula de habitabilidad y compara magnitudes de distinta dimensión. Mientras tanto, mover el aviso a `get_missing_data_warnings` ("superficie de huecos: no evaluable sin datos de carpintería") — que es lo que realmente ocurre | `evaluator.py` :1738, :2133 | 1 h |
| **2** | **Colapsar D1 en una sola incidencia de baño accesible.** Dos CRÍTICOS sobre el mismo baño, con +2.3 puntos prometidos cada uno, es el defecto más visible del producto | `evaluator.py` :2019, :2036, :2062 | 2 h |
| **3** | **Cortar el veredicto verde con CRÍTICOS.** Un CRÍTICO debe vetar "Cumplimiento correcto" y el color verde, con independencia del porcentaje | `evaluator.py` :1903, `scoring.py` | 2 h |
| **4** | **Convertir R18c y R16a en `Unknown` cuando falta el dato**, en vez de en fallo/silencio | `evaluator.py` :1684, :1365 | 3 h |
| **5** | Pasar `zona_cte` en `app.py` :167, o eliminar esa invocación duplicada y reutilizar la de `api_serializer` | `app.py` :167 | 30 min |
| **6** | Unificar `total_problemas` e `issues_summary.total` | `api_serializer.py` :228 | 30 min |
| **7** | **Corregir las 5 citas de §6.2 con validación de un arquitecto colegiado.** No tocar el código antes de esa validación | varios | 4 h + revisión |
| **8** | Retirar `estimar_percentil` del payload y de la BD, o etiquetarlo explícitamente como estimación no respaldada | `scoring.py` :216 | 1 h |
| **9** | Eliminar los rangos de coste fabricados de `chain_effects.py`, o sustituirlos por una escala cualitativa sin cifras | `chain_effects.py` :101 y ss. | 2 h |
| **10** | Documentar en cada regla su nivel N1-N4 como campo estructurado, y mostrarlo en la incidencia | `evaluator.py` | 6 h |
| **11** | **Introducir el eje de comunidad autónoma** en los 6 umbrales autonómicos (§5.3), reutilizando la ciudad que el formulario ya pide | `evaluator.py`, `cte_zonas.py` | PRD propio |
| **12** | Resolver la asimetría puntuación/incidencia: toda regla que puntúa debe poder explicarse, y toda regla que se explica debe puntuar | `evaluator.py` :2337 | PRD propio |

Las acciones 11 y 12 son cambios de capacidad, no correcciones: requieren PRD previo según la regla
vigente del proyecto (`CLAUDE.md`). Las acciones 1-10 son correcciones de comportamiento existente.

---

## 9. Conclusión

El motor tiene **58 reglas, 41 con juicio visible, 0 con referencia a artículo, 5 con cita de DB
discrepante, 4 grupos duplicados y 41 umbrales sin eje de contexto**. Su mayor virtud —
`get_missing_data_warnings`, 10 declaraciones explícitas de "esto no lo sé"— convive con su mayor defecto:
reglas que afirman incumplimiento legal sobre datos que el sistema no tiene, en un caso con un cálculo
dimensionalmente incoherente.

La distancia entre `docs/brain/` y `analyzer/` es hoy el hecho más relevante del repositorio. Los documentos
de diseño ya anticiparon, uno por uno, casi todos los hallazgos de esta auditoría: el eje de contexto
(`CONSTRAINT_MODEL.md` §9), la conclusión negativa sobre dato ausente (`INFERENCE_ENGINE.md`), el veredicto
en tres capas (`BRAIN_ARCHITECTURE.md`), la confianza como eslabón más débil (`EVIDENCE_MODEL.md`), la
prohibición de precisión fabricada. **El diseño es correcto y el código todavía no lo refleja.** Esta
auditoría no propone rediseñar nada: propone empezar a cobrar los intereses de un diseño que ya está pagado.

---

*Auditoría de solo lectura. Ninguna línea de código modificada. Las conclusiones de §6 requieren validación
de un técnico competente antes de traducirse en cambios.*
