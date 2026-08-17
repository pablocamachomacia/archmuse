# DB-SI_DECISIONS.md — Cierre de decisiones bloqueantes del modelo de hechos

**Fecha:** 2026-08-08 · **Estado:** decisiones documentales, sin implementar
**Entrada:** `docs/audits/DB-SI_REVIEW.md`, `docs/audits/DB-SI_IMPLEMENTATION_PLAN.md`, `docs/design/DB-SI_FACT_MODEL.md`
**Restricción cumplida:** cero código, cero commits, ningún documento anterior modificado, ninguna normativa inventada.

---

## 0. Hallazgo que cambia el marco de tres de las cinco decisiones

`DB-SI_FACT_MODEL.md` §13 dio por hecho que el Anejo SI A no estaba disponible y marcó como *pendiente de ingesta* todo lo que
dependiera de él. **Al buscar la fuente para estas decisiones, resultó que sí está disponible — dos veces, y en el propio
repositorio:**

| Fuente | Ruta en el repo | Qué contiene |
|---|---|---|
| **DB-SI completo, 92 páginas** | `ingesta/estado/cache/codigotecnico__DB-SI__0a2e78cd6247.pdf` | Incluye el **Anejo SI A Terminología** íntegro |
| **RD 314/2006 (CTE Parte I)** | `tests/fixtures/boe/BOE-A-2006-5515.xml` | Incluye el **Anejo III Terminología** (44 términos) |

El PDF estaba en la caché de ingesta desde 2026-08-06; lo que faltaba no era el documento, sino la **extracción**: el pipeline generó
25 candidatas de 31 segmentos, y los anejos quedaron fuera del lote de candidatas revisado.

Esto no invalida nada de lo escrito antes —la marca *pendiente de ingesta* era la conducta correcta con la información disponible—
pero **permite cerrar con texto literal, y no con criterio, tres decisiones que se creían bloqueadas.** Todas las citas de este
documento se han leído de esas dos fuentes, en modo lectura, sin modificarlas.

El propio Anejo SI A fija además la regla de gobernanza del corpus, y conviene transcribirla porque resuelve `D5`:

> *«A efectos de aplicación del DB-SI, los términos que figuran en letra cursiva deben utilizarse conforme al significado […] que se
> establecen para cada uno de ellos en este anejo, cuando se trate de términos relacionados únicamente con el requisito básico
> "Seguridad en caso de incendio", **o bien en el Anejo III de la Parte I de este CTE, cuando sean términos de uso común en el
> conjunto del Código**.»*

Dos anejos, con precedencia definida por la propia norma. No es una decisión nuestra.

---

# DECISIÓN 1 — Definición de superficie útil

## 1.1 Decisión ejecutiva

**CERRADA para el ámbito DB-SI.** El DB-SI define "superficie útil" en su Anejo SI A. La definición existe, es citable, y **es
incompatible con lo que ArchMuse calcula hoy** — no por matiz, sino en la dirección insegura.

## 1.2 Evidencia normativa

**(a) DB-SI, Anejo SI A, verbatim** (`codigotecnico__DB-SI__0a2e78cd6247.pdf`, Anejo A. Terminología, p. 49-50):

> **Superficie útil**
> *Superficie en planta de un recinto, sector o edificio **ocupable por las personas**. En uso Comercial, cuando no se defina en
> proyecto la disposición de mostradores, estanterías, cajas registradoras y, en general, de aquellos elementos que configuran la
> implantación comercial de un establecimiento, se tomará como superficie útil de las zonas destinadas al público, al menos el 75% de
> la superficie construida de dichas zonas.*

**(b) CTE Parte I, Anejo III (RD 314/2006)** — se listaron sus **44 términos**: `superficie útil` **no figura entre ellos**. Sí figuran
`Uso previsto`, `Uso del edificio`, `Recinto habitable`, `Recinto protegido`, `Particiones interiores`, `Edificio`.

Lectura conjunta: **no existe una definición de superficie útil común a todo el CTE.** La del DB-SI es específica de ese Documento
Básico y funcional (*ocupable por las personas*), no un protocolo de medición.

**(c) Otras acepciones en el corpus** — "superficie útil" aparece además en DB-HS (§3.3 y §3.4) y DB-SUA 9.1, en contextos de
ventilación y accesibilidad. Nada indica que compartan la definición del DB-SI, y el Anejo SI A dice expresamente que su significado
rige *«a efectos de aplicación del DB-SI»*.

**(d) `Recinto habitable`, CTE Parte I Anejo III, verbatim:**

> *«Se consideran recintos habitables los siguientes: a) Habitaciones y estancias […] e) **Cocinas, baños, aseos, pasillos y
> distribuidores**, en edificios de cualquier uso; f) Zonas comunes de circulación […] Se consideran recintos no habitables aquellos no
> destinados al uso permanente de personas […] En esta categoría se incluyen explícitamente como no habitables **los garajes,
> trasteros**, las cámaras técnicas y desvanes no acondicionados, y sus zonas comunes.»*

**Terraza y tendedero no aparecen en ninguna de las dos listas.**

## 1.3 Decisión adoptada

**D1.a — La definición de referencia para CAP-3 es la del Anejo SI A del DB-SI.** Citable, con localizador
`DB-SI / Anejo SI A / Superficie útil`.

**D1.b — El criterio actual de ArchMuse NO puede usarse para calcular ocupación DB-SI.** Y ésta es la consecuencia práctica que
importa:

`NON_USEFUL_PATTERN = TERRAZA|TENDEDERO` excluye recintos que, bajo la definición del DB-SI, **son superficie útil**: una terraza es
superficie en planta ocupable por personas. Excluirla **reduce la superficie útil**, y como la ocupación se obtiene *dividiendo* por
la densidad, una superficie menor produce **menos ocupantes**.

En materia de evacuación, subestimar la ocupación es el error en la dirección insegura: propaga a número de salidas (`C09`), a
dimensionado de medios (`C10`, A ≥ P/200) y a plazas de refugio (`C15`). Medido en `ejemplo.dxf`, VT6/2 tiene 28,14 m² de terrazas
sobre 103,76 m² de recintos: la exclusión recorta más de un cuarto de la superficie.

**Se decide, por tanto, que son dos hechos distintos y que ninguno hereda el nombre del otro:**

| Hecho | Criterio de inclusión | Uso | Cita |
|---|---|---|---|
| `superficie_suelo_agregada` (criterio ArchMuse) | Excluye terraza y tendedero | R03, R07, R14 — comportamiento actual, sin cambio de números | Ninguna. Criterio propio, declarado |
| `superficie_util_db_si` | **Superficie en planta ocupable por las personas** | **Sólo CAP-3** | `DB-SI / Anejo SI A` |

**D1.c — La clasificación habitable / no habitable pasa a tener respaldo citable.** El CTE Parte I Anejo III permite clasificar
garajes y trasteros como *recintos no habitables* con cita, en lugar de por criterio propio. Es una mejora real, pero **no es
superficie útil**: son ejes distintos y no deben fusionarse. Se registra como definición del corpus, no como criterio de CAP-1.

**D1.d — Lo que sigue sin resolverse.** "Ocupable por las personas" es una definición funcional que requiere juicio en los casos
frontera: una terraza de 1,2 m de fondo, un tendedero cerrado, un armario empotrado. El DB-SI no da protocolo de medición (ni si se
mide a cara interior, ni si descuenta tabiquería, ni umbral de altura libre). Para el caso residencial que ArchMuse analiza esos
casos frontera son de bajo impacto, pero **la definición no es autoaplicable al 100 %**.

## 1.4 Nivel de confianza

**Alta** para la existencia y el texto de la definición (leída literalmente de la fuente oficial cacheada).
**Media** para su aplicación automática, por §1.3.d.
**Alta** para la conclusión de que el criterio actual no sirve para DB-SI: no depende de interpretar la frontera, sino de que una
terraza es o no ocupable por personas, y lo es.

## 1.5 Impacto en arquitectura

- CAP-1 emite **dos hechos con criterios distintos** desde el mismo motor de composición. El criterio deja de estar incrustado en un
  regex y pasa a ser parámetro de la función.
- `superficie_util_db_si` nace con `referencia_normativa` poblada; es **el primer hecho de ArchMuse con cita de artículo real**.
- El eje `recinto_habitable` se incorpora al corpus de definiciones (`NORMATIVE_ENGINE.md` §6, tipo `definicion`), no al cálculo.

## 1.6 Impacto en UX

Ninguno inmediato: R03/R07/R14 conservan su criterio y sus números. Cuando la ocupación se muestre, llevará la cita del Anejo SI A y
—importante— **una superficie distinta de la que la interfaz enseña como "superficie útil" de la vivienda**. Dos números de superficie
en la misma pantalla necesitan etiquetas que los distingan, o generarán una consulta de soporte por proyecto.

## 1.7 Decisiones pendientes

- **P1.1** ¿Qué definición usa R07 (superficie mínima de vivienda)? Es materia autonómica, no DB-SI; su definición sigue sin
  determinar y **no se resuelve con esta decisión**. Queda como estaba.
- **P1.2** Casos frontera de "ocupable" (§1.3.d): fijar criterio documentado con validación de arquitecto colegiado.

---

# DECISIÓN 2 — Redondeo de la ocupación

## 2.1 Decisión ejecutiva

**NO CERRABLE como norma — y la búsqueda revela que probablemente la pregunta está mal planteada.** El DB-SI no establece regla de
redondeo para la ocupación, pero **sí establece redondeo explícito allí donde lo quiere**, y no es en la ocupación.

## 2.2 Evidencia normativa

Búsqueda exhaustiva sobre el **texto completo del DB-SI (92 páginas)**:

| Expresión | Apariciones | Dónde |
|---|---|---|
| `redonde…` | 1 | Anejo E, redondeo de aristas en carbonización de madera. **Nada que ver** |
| `por exceso` | **0** | — |
| `número entero` | **0** | — |
| `al alza` | **0** | — |
| **`o fracción`** | **13** | **Todas en magnitudes *derivadas* de la ocupación, nunca en la ocupación misma** |

Los usos de *"o fracción"* son del tipo:

> *«una para usuario de silla de ruedas por cada **100 ocupantes o fracción**, conforme a SI3-2»* (SI 3 §9)
> *«Uno más por cada **10.000 m² adicionales o fracción**»* (SI 4, hidrantes)

Y el apartado que calcula la ocupación (SI 3 §2) **no contiene ninguna de esas expresiones**.

Búsqueda equivalente en DB-HS y DB-SUA: ninguna regla general de redondeo aplicable.

## 2.3 Decisión adoptada

**La conclusión no es "no lo dice": es que el DB-SI demuestra saber decirlo cuando quiere, y no lo dice aquí.** El redondeo por exceso
está escrito, trece veces, en el punto donde la norma convierte ocupantes en *plazas*, *equipos* o *anchuras* — no en el punto donde
calcula ocupantes.

De ahí la decisión, que es más limpia que la propuesta preliminar:

> **`ocupacion_exacta` = superficie útil ÷ densidad — valor fraccionario, se conserva y se transporta sin redondear.**
> **`redondeo_normativo` = `UNKNOWN`** — el DB-SI no establece regla de redondeo de la ocupación.
> **El "o fracción" se aplica en la regla que lo cita, no en el hecho**, con la cita del apartado que lo exige.

Es decir: **ArchMuse no redondea la ocupación. Nunca.** Cuando `C15` necesite plazas de refugio aplicará su propio "o fracción" con
cita de SI 3 §9; cuando `C10` dimensione aplicará P/200 sobre el valor exacto. El redondeo deja de ser una decisión global y pasa a
ser una propiedad de cada regla, tal como está escrito.

La propuesta preliminar de `ceil` **queda retirada como criterio de ArchMuse.** No se convierte en requisito normativo, ni siquiera
como inferencia técnica aplicada: no hace falta.

**Presentación:** cuando haya que enseñar un número a una persona, se muestra redondeado por exceso y **etiquetado como presentación**
(*"≈ 3 personas"*), conservando el exacto en el dato. Eso es formato, no cálculo, y no viaja a ninguna regla.

## 2.4 Nivel de confianza

**Alta** para la ausencia de regla (búsqueda exhaustiva sobre el documento completo, no sobre un extracto).
**Alta** para la decisión adoptada: no requiere interpretar nada; consiste precisamente en **no** añadir una regla que la norma no
tiene.
**Media** para la observación de que trece "o fracción" en magnitudes derivadas implican intención — es lectura nuestra del patrón,
razonable pero interpretativa. Se marca como **INFERENCIA TÉCNICA**, aunque no cambia la decisión: aun sin ella, la conclusión
"no redondear el hecho" se sostiene sola.

## 2.5 Impacto en arquitectura

- `ocupacion` es un hecho **fraccionario**, no entero. Su unidad es `personas` y admite decimales.
- Desaparece la necesidad de una decisión global de redondeo — un parámetro menos, y un parámetro que habría sido invisible y
  difícil de auditar.
- Cada regla que consuma ocupación declara su propio tratamiento, citando el apartado. Encaja sin fricción con el catálogo de 5
  patrones de `CONSTRAINT_MODEL.md`: el "o fracción" es parte del parámetro de la regla, no del hecho.

## 2.6 Impacto en UX

La ficha muestra *"Ocupación estimada: ≈ 3 personas (2,38 según la densidad de 20 m²/persona de la Tabla 2.1)"*. El fraccionario
visible es una señal de honestidad: deja claro que es un cálculo normativo, no un recuento.

## 2.7 Decisiones pendientes

- **P2.1** Formato exacto de presentación (¿"≈3" o "2,4"?). Cosmética; no bloquea.
- **P2.2** Al implementar `C15`, verificar que el "o fracción" de SI 3 §9 se aplica sobre `ocupacion_exacta` y no sobre un valor ya
  redondeado — el doble redondeo cambia el resultado en el borde.

---

# DECISIÓN 3 — Comportamiento cuando una superficie es UNKNOWN

## 3.1 Decisión ejecutiva

**CERRADA.** Decisión de producto, no normativa. Se adopta la opción (a) de `DB-SI_FACT_MODEL.md` §12.3: el hecho no se emite, la
regla dependiente devuelve `UNKNOWN` con cadena causal, y la vivienda afectada no desaparece del informe — cambia de categoría.

## 3.2 Evidencia

No es una cuestión normativa; la evidencia es el estado del código y lo medido:

- `evaluate_room_overlap` (`evaluator.py:3075`) ya detecta el problema, y su comentario de cabecera (`:3042`) dice
  *«ESTO DETECTA, NO CURA»*.
- Medido sobre `ejemplo.dxf`: VT5/1 duplica 12,43 m² (22 %), VT6/2 duplica 27,32 m² (36 %). 4 de 6 viviendas están limpias.
- El principio aplicable ya está fijado: `INFERENCE_ENGINE.md` §2.2 (una conclusión negativa nunca se deriva de un dato ausente) y
  `FACT_MODEL.md` §10 (contrato de lectura de cuatro estados, nunca silencio).

## 3.3 Decisión adoptada

**D3.a — Propagación.** Un insumo `UNKNOWN` produce un derivado `UNKNOWN`. Una regla cuyo insumo es `UNKNOWN` **no produce `PASS` ni
`FAIL`**: produce `UNKNOWN` y conserva la cadena causal completa, hop a hop.

**D3.b — La cadena causal se muestra entera, no colapsada.** Formato:

```
Comprobación de ocupación: NO CONCLUYENTE
  └─ ocupación no determinable
      └─ superficie útil no verificada
          └─ las piezas de VT6/2 se solapan 27,32 m² (36 %):
             "Salón/cocina" contiene a las 4 terrazas
```

Es la aplicación literal de la regla de explicabilidad de `CHAIN_REASONING.md`: mostrar el camino paso a paso, nunca un veredicto
colapsado.

**D3.c — Los tres estados no se mezclan en la presentación.** `KNOWN` produce cumple/no cumple. `ESTIMATED` produce un aviso, nunca
una afirmación de cumplimiento. `UNKNOWN` produce "no comprobado" con motivo. **Un `UNKNOWN` no cuenta como aprobado ni como
suspenso en ningún recuento**, y esto incluye `score_pct`: una comprobación no realizada no puede sumar al porcentaje de
comprobaciones superadas.

**D3.d — Informe ejecutivo vs. inspector técnico.** Se separan deliberadamente:

| | **Informe ejecutivo** | **Inspector técnico** |
|---|---|---|
| Qué muestra | Que la vivienda **no ha podido analizarse**, en una categoría propia junto a verde/amarillo/rojo — no un cuarto color de calidad, sino "sin datos" | La cadena causal completa (D3.b), con las piezas implicadas y sus metros |
| Recuento | *"4 de 6 viviendas analizadas. 2 requieren revisión del plano."* | Par de piezas, solape en m² y % de la pieza menor — lo que `RoomOverlapResult` ya calcula |
| Qué NO muestra | Ninguna superficie, ninguna ocupación, ninguna puntuación de esa vivienda | — |
| Acción ofrecida | Qué hacer: revisar el contorno agrupador en el DXF | Igual, con la referencia geométrica concreta |

**D3.e — Lo que esto cuesta, dicho antes de aprobar.** Dos de las seis viviendas del proyecto de ejemplo pasan de tener puntuación a
no tenerla. El informe pierde números y gana veracidad. Es una regresión aparente de funcionalidad y **debe comunicarse como lo que
es**: el motor dejó de puntuar lo que no puede medir.

**D3.f — Frontera explícita.** Esta decisión **no arregla el parser**. La causa —contornos agrupadores conservados por
`_discard_container_candidates`— sigue ahí, y arreglarla cambia las superficies de todos los proyectos ya guardados. Es una decisión
aparte, como el propio comentario del código señala.

## 3.4 Nivel de confianza

**Alta.** No depende de ninguna interpretación normativa, y es coherente con cuatro documentos de diseño previos. El único juicio
discutible es §3.3.e, que es de producto y se explicita para que lo decida Pablo.

## 3.5 Impacto en arquitectura

- El resultado de una regla deja de ser binario: `PASS | FAIL | UNKNOWN`. **Es el cambio estructural de mayor alcance de las cinco
  decisiones**, porque afecta a la firma de todo resultado, no sólo a los del Bloque A.
- `score_pct` necesita un denominador que excluya lo no comprobado.
- `evaluate_room_overlap` deja de ser una incidencia independiente y pasa a ser el guardián del estado de CAP-1. Su cálculo no cambia.

## 3.6 Impacto en UX

Es el impacto mayor de las cinco decisiones. Requiere una categoría visual nueva ("no analizable") que no se lea como un suspenso —
un plano con un contorno agrupador no es un mal proyecto, es un plano que ArchMuse no sabe leer, y la diferencia debe quedar clara
para no ofender al arquitecto que lo envió.

## 3.7 Decisiones pendientes

- **P3.1** Tratamiento visual de la categoría "no analizable" — diseño, no arquitectura.
- **P3.2** ¿Se emite puntuación global del proyecto cuando 2 de 6 viviendas no son analizables? Recomendación: sí, sobre las
  analizables, **declarando la cobertura** (*"87 sobre 4 de 6 viviendas"*), nunca ocultando el denominador.
- **P3.3** ¿Cuándo se arregla el parser (§3.3.f)? Requiere plan de migración de proyectos guardados.

---

# DECISIÓN 4 — Reglas existentes que consumen superficies no fiables

## 4.1 Decisión ejecutiva

**CERRADA como inventario. 15 reglas consumen superficie. Ninguna debe pasar a `UNKNOWN` de forma permanente, pero 12 deben pasar a
`UNKNOWN` en las viviendas con solape** — que hoy no lo hacen. Y el inventario ha destapado dos defectos independientes del solape.

## 4.2 Evidencia

Inventario completo por lectura de `analyzer/evaluator.py`. Dos modos de fallo distintos, y la distinción importa:

- **Agregadas:** suman áreas de varias piezas → el solape **duplica metros**.
- **Por pieza:** evalúan una pieza aislada → el solape no duplica, pero **el contorno agrupador entra como pieza fantasma** y se
  evalúa como si fuera una habitación. En VT5/1 el "Salón/cocina" de 52,13 m² es ese contorno.

| Regla | Hecho consumido | ¿El hecho es fiable? | Riesgo | Acción |
|---|---|---|---|---|
| **R03** eficiencia útil/total `:445` | útil + total agregados | **No** con solape | Ratio calculado sobre metros duplicados | `UNKNOWN` si solape |
| **R07** superficie mínima vivienda `:819` | útil agregado | **No** con solape | **Sobrestima**: una vivienda pequeña puede "cumplir" el mínimo legal por duplicación | `UNKNOWN` si solape |
| **R14** eficiencia de circulación `:1218` | pasillo / útil | **No** con solape | Ratio distorsionado | `UNKNOWN` si solape |
| **R29** ratio a sur `:3264` | suma áreas habitables | **No** con solape | Denominador duplicado | `UNKNOWN` si solape |
| **R22/23/24** urbanismo `:2806` | `unit.total_area_m2` por planta | **No** — ver §4.3 | Ver §4.3 | Corregir cita y dato |
| **R00** superficie mínima por etiqueta `:79` | `room.area_m2` | Sí, salvo pieza fantasma | Evalúa un contorno agrupador como habitación | `UNKNOWN` para la pieza solapada |
| **R02** jerarquía dormitorios `:388` | áreas comparadas | Sí, salvo fantasma | Comparación contra pieza inexistente | Ídem |
| **R13** jerarquía espacial `:1177` | salón vs. dorm1 | **No** con fantasma | El contorno agrupador **siempre** es la pieza mayor: la regla pasa trivialmente | `UNKNOWN` si solape |
| **R15b** factor luz natural `:1370` | `room.area_m2` | Sí, salvo fantasma | — | `UNKNOWN` para la pieza solapada |
| **R19** huecos 1/8 `:1872` | `room.area_m2` | Sí, salvo fantasma | Ver §4.4 | Ídem + §4.4 |
| **R20** superficie mínima dormitorio `:1947` | `room.area_m2` | Sí, salvo fantasma | — | Ídem |
| **R21** baño adaptado `:2001` | `room.area_m2` | Sí, salvo fantasma | — | Ídem |
| **R01** proporción tubo `:227` | lados, no área | **Sí** | El área es informativa | Sin cambio |
| **R26** compartimentación `:3000` | intersección de huellas | **Sí** (geométrico puro) | Ya tratado en `C01` | Sin cambio aquí |
| `evaluate_room_overlap` `:3075` | intersección piezas | **Sí** | Es el detector | Pasa a guardián de estado (D3) |

**R13 merece subrayado:** un contorno agrupador conservado como "Salón/cocina" es, por construcción, la pieza de mayor superficie de
la vivienda. La regla "el salón debe ser la pieza mayor" pasa **precisamente porque el dato está mal**. Es un falso aprobado causado
por el defecto, no a pesar de él.

## 4.3 Hallazgo independiente: la superficie construida del urbanismo no es superficie construida

`compute_floor_areas` (`evaluator.py:2806`) tiene este docstring: *«**Superficie construida** (suma de áreas de vivienda/local) por
planta»*. Pero suma `unit.total_area_m2`, que es la suma de polígonos de recinto — medidos a cara interior de muro, **sin espesor de
cerramientos ni tabiquería** (`DB-SI_FACT_MODEL.md` §3.2).

Alimenta R22 (ocupación de solar), R23 (edificabilidad) y R24 (altura máxima), cuyos parámetros urbanísticos se definen legalmente en
superficie **construida**. El error es sistemático y va en una sola dirección: **infraestima la superficie construida**, de modo que
un proyecto podría mostrarse dentro de la edificabilidad máxima estando por encima.

Detalle adicional: la función sólo asigna planta a viviendas cuyo nombre case `Planta <n> · …`, convención de `/api/generar`. Para un
DXF analizado (`VT1/3`) **devuelve un diccionario vacío**, así que estas tres reglas no llegan a evaluarse en el flujo DXF — lo que
hoy limita el daño, y explica por qué no se ha detectado antes.

**Acción:** corregir el docstring y la magnitud citada; el hecho correcto es `superficie_suelo_agregada`, no superficie construida.
Queda fuera del Bloque A (es urbanismo, no DB-SI) pero **debe registrarse ahora**, porque CAP-1 es exactamente el sitio donde se
consolidaría el error si nadie lo anota.

## 4.4 Segundo hallazgo independiente: el 1/8 de R19 no está en el DB-HS3 ingerido

Al inventariar consumidores de `room.area_m2` apareció esto, en el texto de **DB-HS 3 §4.4** (corpus ingerido,
`codigotecnico__DB-HS__68df3caacc95.jsonl`, registro 12), verbatim:

> *«La superficie total practicable de las ventanas y puertas exteriores de cada local debe ser como mínimo **un veinteavo de la
> superficie útil** del mismo.»*

Es **1/20 (5 %)**, referido a superficie **practicable** — una exigencia de **ventilación**. R19 (`evaluate_window_opening_ratio`,
`:1872`) usa `MIN_WINDOW_TO_FLOOR_RATIO = 1/8` (12,5 %) y emite código `CTE-DB-HS3`.

No es lo mismo: distinta fracción y distinta magnitud (superficie practicable ≠ superficie de hueco de iluminación). El 1/8 procede
con toda probabilidad de decretos autonómicos de habitabilidad —materia de iluminación, competencia autonómica— y no del DB-HS3.

**Esto refuerza el hallazgo H3 de `NORMATIVE_AUDIT.md` §6.3 desde un ángulo nuevo:** hasta ahora se sabía que R19 comparaba magnitudes
dimensionalmente incoherentes; ahora consta además que **el umbral no está en el documento que cita.**

**Acción:** fuera del alcance del Bloque A. Se registra aquí con la cita para que la corrección de R19 (acción nº 1 de
`NORMATIVE_AUDIT.md` §8) parta de esta evidencia y no se limite a arreglar las unidades. Requiere validación de arquitecto colegiado
antes de tocar el umbral.

## 4.5 Decisión adoptada

**D4.a — Ninguna regla pasa a `UNKNOWN` de forma permanente.** El proxy no es inválido en general: es inválido **en las viviendas con
solape**. La condición es por vivienda, no por regla.

**D4.b — 12 de las 15 reglas pasan a `UNKNOWN` en las viviendas con solape**, según la tabla. Es la aplicación de D3 al inventario
existente, y responde a la preocupación explícita del encargo: **CAP-1 no puede crear un modelo correcto mientras las reglas antiguas
siguen consumiendo el proxy en silencio.** Sin D4.b, CAP-1 sería una segunda fuente de verdad conviviendo con la primera.

**D4.c — R13 es prioritaria** pese a no ser normativa: hoy produce un aprobado que el propio defecto fabrica.

**D4.d — §4.3 y §4.4 se registran como hallazgos, no se corrigen aquí.** Ninguno pertenece al Bloque A.

## 4.6 Nivel de confianza

**Alta** para el inventario (lectura directa del código, líneas citadas).
**Alta** para §4.3 (el docstring y la magnitud se contradicen; verificable en dos líneas).
**Media** para §4.4: la cita del 1/20 es literal y verificada, pero afirmar de dónde procede el 1/8 sería especular — sólo consta que
**no está en el DB-HS3 ingerido**.

## 4.7 Impacto en arquitectura

- La condición "esta vivienda tiene solape" debe ser consultable por todas las reglas, no recalculada por cada una. Es un hecho más.
- Confirma que el resultado de regla necesita el tercer valor `UNKNOWN` (D3.5): sin él, D4.b no se puede expresar.

## 4.8 Impacto en UX

En `ejemplo.dxf`, VT5/1 y VT6/2 pasarían de mostrar incidencias y puntuación a mostrar "no analizable" con motivo. Coherente con D3.

## 4.9 Decisiones pendientes

- **P4.1** ¿R01 (proporción tubo) debe evaluarse sobre una pieza fantasma? Usa lados, no área, así que el número es correcto — pero
  describe una pieza que no existe. Recomendación: excluirla también.
- **P4.2** Corrección de `compute_floor_areas` (§4.3) — fuera del Bloque A, requiere decidir si se estima la construida o se declara.
- **P4.3** Corrección de R19 (§4.4) — requiere validación colegiada.

---

# DECISIÓN 5 — Bloque 0: ingesta de terminología

## 5.1 Decisión ejecutiva

**CERRADA, y más barata de lo previsto.** No hay que descargar nada: las dos fuentes están en el repositorio. Lo que falta es
extraerlas y almacenarlas como definiciones.

## 5.2 Evidencia — fuente normativa oficial

| | **DB-SI Anejo SI A** | **CTE Parte I Anejo III** |
|---|---|---|
| Norma | DB-SI, versión con comentarios | **RD 314/2006, de 17 de marzo** |
| Boletín | — (documento consolidado del Ministerio) | **BOE-A-2006-5515**, BOE nº 74 de 28/03/2006 |
| URL oficial | `https://www.codigotecnico.org/pdf/Documentos/SI/DBSI.pdf` | `https://www.boe.es/…/BOE-A-2006-5515` |
| En el repo | `ingesta/estado/cache/codigotecnico__DB-SI__0a2e78cd6247.pdf` (92 pp.) | `tests/fixtures/boe/BOE-A-2006-5515.xml` + `ingesta/estado/cache/boe__BOE-A-2006-5515__0c92cd9f89fe.xml` |
| Alcance | Términos **exclusivos** de seguridad en caso de incendio | Términos **de uso común** en todo el CTE (44) |
| Precedencia | Fijada por el propio Anejo SI A (§0) | Ídem |

## 5.3 Términos que afectan al Bloque A

Verificados presentes en la fuente:

| Término | Anejo | Para qué | Estado |
|---|---|---|---|
| **Superficie útil** | SI A | CAP-1 / CAP-3 — **cierra D1** | ✅ localizado y transcrito |
| **Uso previsto** | **Parte I, III** | CAP-2. Dice *«se debe reflejar documentalmente»* — §5.5 | ✅ localizado |
| **Uso Residencial Vivienda** | SI A | CAP-2 — §5.5 | ✅ localizado |
| **Zona de ocupación nula** | SI A | Estado `NO_APLICABLE` de CAP-3. Incluye *«trasteros de viviendas»* | ✅ localizado |
| Uso del edificio | Parte I, III | Distinción con `uso previsto` | ✅ |
| Recinto habitable / no habitable | Parte I, III | Eje citable (D1.c) | ✅ |
| Usos Administrativo, Comercial, Docente, Hospitalario, Aparcamiento, Almacén, Residencial Público | SI A | Catálogo cerrado de valores de CAP-2 | ✅ presentes |

## 5.4 Términos que afectan a capacidades futuras

Todos verificados presentes en el Anejo SI A:

| Término | Capacidad | Por qué importa |
|---|---|---|
| **Origen de evacuación** | CAP-6, `C09`, `C10` | **Ver §5.6 — es el hallazgo de mayor consecuencia** |
| **Altura de evacuación** | CAP-5, `C11`, `C15`, `C18` | *«Máxima diferencia de cotas entre un origen de evacuación y la salida de edificio que le corresponda»* — confirma que `plantas × altura_libre` no es esa magnitud |
| **Salida de planta / de edificio / de emergencia** | CAP-6 | Define qué cuenta como salida |
| **Sector de incendio** | `C01` | *«Espacio […] separado […] por elementos constructivos delimitadores resistentes al fuego»* — confirma que el solape de huellas no es sectorización |
| Sector de riesgo mínimo, sector bajo rasante | `C01`, `C21` | Excepciones de tablas |
| Espacio exterior seguro | `C09` | Extremo del recorrido |
| Escalera protegida / especialmente protegida / abierta al exterior | `C11` | El tipo de escalera que `C11` no puede conocer |
| Aparcamiento abierto | `C14` | Condición de activación |
| Recorrido de evacuación, recorridos alternativos | `C09` | — |
| Establecimiento | `C07` | — |
| Vestíbulo de independencia, pasillo protegido, zona de refugio, ascensor de emergencia | `C15`, `C01` | — |

## 5.5 Confirmaciones que el Bloque A gana de inmediato

**(a) CAP-2 deja de ser una invención de ArchMuse.** CTE Parte I Anejo III, verbatim:

> *«**Uso previsto**: uso específico para el que se proyecta y realiza un edificio y **que se debe reflejar documentalmente**. El uso
> previsto se caracteriza por las actividades que se han de desarrollar en el edificio y por el tipo de usuario.»*

Pedir al arquitecto que declare el uso previsto no es una exigencia nuestra: **la norma da por supuesto que consta documentalmente**.
Y *«se caracteriza por las actividades […] y por el tipo de usuario»* confirma que no es derivable de la geometría.

**(b) El mapeo tipología → uso queda citado, no asumido.** Anejo SI A, verbatim:

> *«**Uso Residencial Vivienda**: Edificio o zona destinada a alojamiento permanente, **cualquiera que sea el tipo de edificio:
> vivienda unifamiliar, edificio de pisos o de apartamentos**, etc.»*

Plurifamiliar **y** unifamiliar son Residencial Vivienda. `DB-SI_FACT_MODEL.md` §4.1 lo daba por correcto pero implícito; ahora es
citable. (Rehabilitación sigue sin decir nada sobre el uso, como se señaló.)

**(c) `NO_APLICABLE` tiene respaldo textual.** Anejo SI A: *«**Zona de ocupación nula**: Zona en la que la presencia de personas sea
ocasional o bien a efectos de mantenimiento, tales como salas de máquinas y cuartos de instalaciones, locales para material de
limpieza, determinados almacenes y archivos, **trasteros de viviendas**, etc.»*, y añade que sus puntos *«no es preciso tomarlos en
consideración a efectos de determinar […] el número de ocupantes»*. El cuarto estado del contrato no es un invento de diseño.

## 5.6 El hallazgo de mayor consecuencia: origen de evacuación

Anejo SI A, verbatim:

> *«**Origen de evacuación**: Es todo punto ocupable de un edificio, **exceptuando los del interior de las viviendas** y los de todo
> recinto o conjunto de ellos comunicados entre sí, en los que la densidad de ocupación no exceda de 1 persona/5 m² y cuya superficie
> total no exceda de 50 m² […]»*

`DB-SI_REVIEW.md` (`C09`) sostuvo que el ámbito de R17 era incorrecto y lo marcó como **pendiente de ingesta**, sin usarlo como base
para ninguna acción. **Con este texto, la marca se levanta y la conclusión queda confirmada por la norma:** los puntos del interior de
las viviendas están expresamente excluidos como origen de evacuación, de modo que medir un recorrido dentro de una vivienda y
compararlo con los 25 m del DB-SI no tiene fundamento normativo.

No cambia la acción recomendada —ya era retirar el veredicto de R17— pero **cambia su justificación de "inferencia razonable" a "cita
literal"**, que es exactamente el salto que la regla de dos personas de `NORMATIVE_ENGINE.md` §12 pretende.

## 5.7 Decisión adoptada

**D5.a — El Bloque 0 se amplía a los dos anejos, íntegros.** No sólo los términos del Bloque A: el coste marginal es casi nulo y
evita una segunda ingesta en el Bloque C.

**D5.b — Se almacenan como `definicion`**, el tipo de primera clase de `NORMATIVE_ENGINE.md` §6: no se evalúan, se referencian. Cada
definición es una `NormaFuente` con su localizador (`DB-SI / Anejo SI A / <término>` o `RD 314/2006 / Anejo III / <término>`),
literal transcrito y `hash_texto`.

**D5.c — Se modela la precedencia que la propia norma fija** (§0): término de incendios → Anejo SI A; término común → Anejo III de la
Parte I. Es una arista `se_mide_segun` del grafo tipado de `NORMATIVE_ENGINE.md` §9, no lógica del motor.

**D5.d — Una regla del corpus:** ningún hecho o Constraint que use un término definido puede omitir la arista a su definición. Es lo
que impide que reaparezca una "superficie útil" sin decir cuál.

**D5.e — El pipeline necesita revisión, no sólo ejecución.** La extracción produjo 25 candidatas de 31 segmentos y los anejos no
llegaron al lote. Antes de dar el Bloque 0 por hecho hay que confirmar que los anejos se segmentan y almacenan; extraer definiciones
no es lo mismo que extraer exigencias, y el `regla.schema.json` actual está pensado para lo segundo.

## 5.8 Nivel de confianza

**Alta** para las fuentes, su ubicación y los textos citados (leídos de los ficheros del repositorio).
**Media** para el esfuerzo de `D5.e`: no se ha verificado que el segmentador maneje anejos de terminología, y una prueba directa del
segmentador sobre el PDF cacheado devolvió 0 segmentos con una construcción manual del documento — indicio de que la ruta de ingesta
no es trivialmente reutilizable, no prueba de que falle.

## 5.9 Impacto en arquitectura

- Nace el catálogo de **definiciones** del corpus, con dos fuentes y precedencia declarada.
- Primer uso real de la arista `se_mide_segun`.
- CAP-2 estrena catálogo cerrado de usos **tomado de la norma**, no redactado por nosotros.

## 5.10 Impacto en UX

La ficha de una incidencia puede mostrar, junto al umbral, la definición literal del término que usa. Es exactamente la promesa de
`MOAT_ANALYSIS.md` §1 que hoy no se cumple en ninguna regla — y con estas dos ingestas empieza a cumplirse en la primera.

## 5.11 Decisiones pendientes

- **P5.1** ¿El segmentador maneja anejos de terminología, o hace falta una ruta específica? (§5.8)
- **P5.2** Esquema de almacenamiento de una `definicion` — `regla.schema.json` está orientado a exigencias evaluables.
- **P5.3** Verificar si la versión del PDF cacheado (hash `0a2e78cd…`, fecha 2025-03-04) es la vigente antes de fijar `vigencia_desde`.

---

# DECISIÓN 6 — ¿Computa una terraza como superficie útil DB-SI? *(añadida 2026-08-08)*

## 6bis.1 Decisión ejecutiva

**CERRADA: sí computa.** Cierra también P1.2, que quedaba pendiente de criterio profesional. No hizo falta: la
respuesta está en el texto, y la pregunta sobre si la terraza está cubierta o dentro de la envolvente resulta **no
ser necesaria** para decidirlo.

## 6bis.2 Evidencia normativa

**(a) La definición no excluye nada.** DB-SI, Anejo SI A: *«Superficie en planta de un recinto, sector o edificio
ocupable por las personas»*. No dice «interior», no remite a ninguna lista de exclusiones.

**(b) No existe ninguna exclusión de superficie útil en todo el DB-SI.** Búsqueda sobre las 92 páginas
(`no computa`, `no se considera`, `se excluye`, `no forman parte`, `descuenta`): la única exclusión de superficie es
*«(4) Las zonas de aseos no computan a efectos del cálculo de la superficie **construida**»* — otra magnitud, otro
propósito (clasificar locales de riesgo especial) y otro recinto. **Para la superficie útil no hay exclusión de
ningún tipo.**

**(c) El DB-SI nombra la terraza, y la trata como espacio con evacuación.** Tabla 3.1, dos veces:
*«…o bien de un espacio al aire libre en el que el riesgo de incendio sea irrelevante, por ejemplo, una cubierta de
edificio, **una terraza**, etc.»*

**(d) La prueba decisiva — Tabla 4.1 dimensiona las zonas al aire libre en función de la ocupación:**

> **En zonas al aire libre:** Pasos, pasillos y rampas A ≥ **P/600**; Escaleras A ≥ **P/480**
> *«P = Número total de personas cuyo paso está previsto por el punto cuya anchura se dimensiona.»*

Una zona al aire libre tiene P. Y P sale de la Tabla 2.1, que es superficie útil ÷ densidad. **Si una terraza no
tuviera superficie útil no tendría ocupación, y estas dos filas del DB-SI carecerían de entrada.** El propio
documento presupone, por tanto, que las zonas al aire libre tienen superficie útil.

**(e) El CTE Parte I (RD 314/2006) no menciona «terraza» ni una sola vez, y no define «superficie útil».** No hay
regla general que contradiga lo anterior.

## 6bis.3 Decisión adoptada

**La terraza se incluye en `superficie_util_db_si`.** El tendedero también: no lo nombra ninguna norma, pero la carga
de la prueba está en excluir y nada respalda excluirlo.

Regla general que sustituye a la clasificación por lista blanca: **un recinto rotulado de la vivienda es superficie
útil salvo que la norma diga lo contrario, y no lo dice de ninguno.** La única clase que se aparta es *zona de
ocupación nula* (Anejo SI A), y ni siquiera deja de ser superficie útil: el Anejo la excluye del *«número de
ocupantes»*, que es cosa de CAP-3, no de la superficie.

`AMBIGUO` queda reservado a lo que no se puede identificar como recinto —un polígono **sin rótulo**—, donde la duda
no es normativa sino de lectura del plano.

**Sobre la pregunta de la cobertura, que era el núcleo del encargo:** saber si la terraza está cubierta o cerrada
**sí** es normativamente relevante en DB-SI, pero para otras cosas — la longitud admisible del recorrido (25/50 m
frente a los 75 m de las zonas al aire libre, Tabla 3.1) y el coeficiente de dimensionado (P/200 frente a P/600,
Tabla 4.1). **No lo es para decidir si la superficie computa.** Justificar `UNKNOWN` con «no sabemos si está
cubierta» era, por tanto, un no-sequitur: el dato hace falta para `C09` y `C10`, no para CAP-1.

## 6bis.4 Nivel de confianza

**Alta** para la terraza: se apoya en cita directa (c) y en un argumento estructural del propio documento (d), no en
interpretación. **Media** para el tendedero: no lo nombra ninguna norma; la inclusión se deduce de la ausencia
universal de exclusiones (b), que es sólido pero es un argumento *ex silentio*.

## 6bis.5 Impacto

- Sobre **CAP-1**: `clasificar_recinto` invierte su criterio — inclusivo por defecto en vez de lista blanca.
- Sobre **`_superficie_suelo_agregada_m2`** (criterio antiguo, `NON_USEFUL_PATTERN`): confirma que su exclusión de
  terraza y tendedero **no tiene ningún respaldo en DB-SI**. No se toca: tiene consumidores antiguos (R03, R07, R14)
  y cambiarlo altera proyectos ya guardados. Refuerza D1: son dos magnitudes distintas y deben seguir separadas.
- Sobre **`ejemplo.dxf`**: 4 de 6 viviendas pasan de `UNKNOWN` a `KNOWN`. Las 2 restantes siguen `UNKNOWN`, ahora
  por su causa real y única —el solape—, no por las terrazas.

## 6bis.6 Decisiones pendientes

- **P6.1** Cubierta/cerramiento de la terraza: sigue sin poder determinarse desde el DXF, y hará falta para `C09` y
  `C10`. Es un dato de entrada, no una decisión.
- **P6.2** El argumento *ex silentio* del tendedero (6bis.4) conviene confirmarlo con arquitecto colegiado, aunque no
  bloquea nada.

---

## 6. Tabla final de decisiones

| Decisión | Estado | Decisión | Confianza | Bloquea implementación |
|---|---|---|---|---|
| **D1** Definición de superficie útil | **CERRADA** | Anejo SI A: *«superficie en planta […] ocupable por las personas»*. Dos hechos separados: `superficie_suelo_agregada` (criterio ArchMuse, para R03/R07/R14) y `superficie_util_db_si` (citada, sólo para CAP-3). El criterio actual **no sirve** para DB-SI: excluye terrazas que sí son útiles, y subestima la ocupación | Alta (definición) / Media (aplicación) | **No** |
| **D2** Redondeo de la ocupación | **CERRADA como "no procede"** | ArchMuse **no redondea** la ocupación. `ocupacion_exacta` fraccionaria; `redondeo_normativo = UNKNOWN`; el *«o fracción»* se aplica en cada regla que lo cita. `ceil` retirado | Alta | **No** |
| **D3** Comportamiento ante `UNKNOWN` | **CERRADA** | Propagación con cadena causal; ni `PASS` ni `FAIL`; no computa en `score_pct`; categoría "no analizable" en el ejecutivo y cadena completa en el inspector | Alta | **No** |
| **D4** Reglas que consumen superficie | **CERRADA como inventario** | 15 reglas inventariadas; 12 pasan a `UNKNOWN` en viviendas con solape (no de forma permanente). R13 prioritaria: hoy aprueba *gracias* al defecto. Dos hallazgos nuevos registrados (§4.3, §4.4) | Alta / Media (§4.4) | **No** |
| **D6** ¿Computa la terraza? | **CERRADA** | **Sí computa.** El DB-SI no excluye ningún recinto de la superficie útil, nombra la terraza y dimensiona las zonas al aire libre en función de la ocupación. Cierra P1.2 | Alta (terraza) / Media (tendedero) | **No** |
| **D5** Bloque 0 (terminología) | **CERRADA** | Dos anejos, ambos ya en el repo: DB-SI Anejo SI A + RD 314/2006 Anejo III. Ingesta íntegra, tipo `definicion`, precedencia según la propia norma | Alta (fuentes) / Media (esfuerzo) | **Sí — precede a CAP-1/2/3** |

### 6.1 Pendientes que sobreviven

| # | Pendiente | Bloquea |
|---|---|---|
| P1.1 | Definición de superficie útil para R07 (materia autonómica) | No — R07 no cambia |
| ~~P1.2~~ | ~~Casos frontera de "ocupable por las personas"~~ — **cerrada por D6** | No |
| P2.2 | Verificar el *«o fracción»* de SI 3 §9 al implementar `C15` | No — Bloque C |
| P3.2 | ¿Puntuación global con 2 de 6 viviendas no analizables? | No — recomendación en §3.7 |
| P3.3 | Arreglo del parser y migración de proyectos guardados | No |
| P4.2 | `compute_floor_areas` no mide superficie construida | No — urbanismo |
| P4.3 | El 1/8 de R19 no está en el DB-HS3 ingerido | No — requiere validación colegiada |
| P5.1 | ¿El segmentador maneja anejos de terminología? | **Sí — es el Bloque 0** |
| P5.2 | Esquema de almacenamiento de `definicion` | **Sí — es el Bloque 0** |

---

*Decisiones documentales. Ninguna línea de código escrita ni modificada. `evaluator.py` y `parser.py` intactos. Ninguna regla creada
ni modificada. Sin commits. Ningún documento anterior alterado. Todas las citas normativas de este documento se han leído literalmente
de `ingesta/estado/cache/codigotecnico__DB-SI__0a2e78cd6247.pdf` y `tests/fixtures/boe/BOE-A-2006-5515.xml`, ambos ya presentes en el
repositorio; no se ha inventado ninguna definición ni umbral. Las conclusiones de §4.4 y P1.1 requieren validación de un técnico
competente antes de traducirse en cambios de código.*
