# Nota de decisión — Los dos sistemas de puntuación

**Fecha:** 2026-08-02 · **Estado:** decisión pendiente de Pablo
**Origen:** tarea 2 del PRD `docs/prd/2026-08-02-desglose-de-puntuacion-desplegable.md`
**Evidencia ejecutable:** `python tests/test_scoring_coherencia.py`

---

## Lo que había

Tres escalas distintas para el mismo proyecto. Medido sobre `ejemplo.dxf`:

| | puntuación proyecto | valoración |
|---|---|---|
| Sistema 1 — `UnitScore.score_pct` (lo que se ve en pantalla) | **86,6** | verde |
| Sistema 2 — `scoring.compute_scoring_breakdown` (el desglose) | **69,7** | **rojo** |
| Sistema 3 — umbrales propios de `pdf_report.py` | 80/60 en vez de 85/70 | — |

Nadie lo había notado porque el sistema 2 se volvió invisible cuando el
rediseño del Shell retiró su popover, y el 3 solo se ve al descargar el PDF.

## Lo que ya está corregido (no requería decisión)

**a) Los umbrales del PDF.** Eran 80/60 frente a los 85/70 de la aplicación: un
proyecto de 82 salía verde en pantalla y naranja en su propio PDF. Ahora
`pdf_report.py` importa los umbrales de `evaluator`. No hay ninguna lectura de
dos escalas distintas que no sea «el programa se contradice».

**b) La agregación del desglose a nivel de proyecto.** `compute_scoring_breakdown`
arranca cada categoría en 100 y resta; al pasarle de golpe los issues de las
seis viviendas aplicaba **un solo techo de 100 puntos a los problemas de
todas**. Consecuencia: un proyecto puntuaba peor cuanto más grande era, aunque
cada vivienda por separado estuviera bien. «Iluminación y ventilación» salía a
**0,0** sin que ninguna vivienda la tuviera a 0.

`compute_project_breakdown` puntúa cada vivienda por separado y promedia por
categoría; los problemas de edificio —ocupación del solar, edificabilidad,
altura— se restan **una sola vez**, porque afectan al proyecto una vez y no
una por vivienda. El desglose del proyecto pasa de 69,7 a ~93,8.

**c) `percentil_estimado`.** Retirado del payload. Colgaba de la puntuación
perdedora (daba percentil 45 en vez de 79 — la diferencia entre «por debajo de
la media» y «top 21%», sobre el mismo proyecto), y sobre todo **no tenía ningún
consumidor**: se retiró de la interfaz hace semanas por ser una tabla de tres
puntos escrita a mano presentada como comparación de mercado. Dejarlo en el
JSON solo servía para que volviera a colarse. Es el principio no negociable de
`NORTH_STAR_2031.md`: nunca se muestra un dato como real si no lo es.

## La decisión que queda: cuál de los dos es LA puntuación

Corregida la agregación, los dos sistemas **siguen sin coincidir** — 93,8
frente a 86,6 — y no van a coincidir nunca, porque no miden lo mismo:

| | Sistema 1 (`score_pct`) | Sistema 2 (desglose) |
|---|---|---|
| Cómo | comprobaciones superadas ÷ aplicables × 100 | 100 − deducciones por severidad (15/7/2), media ponderada por categoría |
| Gravedad | **no la distingue**: un fallo crítico de sectorización de incendios pesa igual que una recomendación sobre el fondo de una habitación | sí |
| Comparable entre viviendas | **no**: el denominador cambia según cuántas reglas apliquen a cada vivienda, así que dos «90» no significan lo mismo | sí, escala fija |
| Desglose por categoría | no lo produce | es su forma natural |
| Dónde se ve hoy | en todas partes | en ninguna |

Por vivienda, en `ejemplo.dxf`:

| vivienda | sistema 1 | sistema 2 |
|---|---|---|
| VT1/3 | 91,7 verde | 92,4 verde |
| VT2/2 | 93,2 verde | 95,8 verde |
| VT3/3 | 90,9 verde | 95,8 verde |
| VT4/2 | 86,8 verde | 94,8 verde |
| VT5/1 | 80,8 **amarillo** | 93,7 **verde** |
| VT6/2 | 76,5 **amarillo** | 90,2 **verde** |

### Recomendación

**El sistema 2 debería ser la puntuación, y `score_pct` quedarse como dato
interno** («ha superado 33 de 36 comprobaciones»), que es informativo y honesto
pero no es una nota.

Las dos razones son estructurales, no de gusto: una puntuación que no distingue
un incumplimiento crítico de una recomendación no sirve para priorizar, que es
justamente para lo que un arquitecto la mira; y una puntuación cuyo denominador
cambia de vivienda a vivienda no se puede comparar entre viviendas, que es
justamente lo que hace la barra lateral.

### Por qué no lo he hecho ya

**Porque cambia todos los números de un proyecto que ya está guardado**, y en
una dirección incómoda: todo sube. VT6/2 pasa de 76,5 amarillo a 90,2 verde.
Un motor que de repente aprueba lo que antes marcaba merece que alguien mire si
las deducciones (15/7/2 desde una base de 100) no son sencillamente blandas.

Eso es calibración, no refactor, y calibrar contra un único proyecto sería
repetir el error que ya arrastran los pesos de `capas_candidatas` y la
tolerancia de `match_label_to_room`.

**Alternativa que merece considerarse antes de decidir:** que el sistema 2
tampoco sea el bueno tal cual, y que lo correcto sea mantener su estructura
—ponderada por gravedad, con desglose— y recalibrar las deducciones para que
la escala resultante sea defendible ante un colegio profesional. Eso ya no es
una tarea de dos horas.

### Qué hace falta para cerrar esto

1. Decidir si la puntuación pasa a ser el sistema 2 (una línea).
2. Si sí: recalibrar `DEDUCTION_BY_SEVERITY` con criterio, no con el default.
3. Recapturar `tests/fixtures/ejemplo-dxf-analisis.json` y revisar el diff a mano.
4. `tests/test_scoring_coherencia.py` pasa a verde.

Hasta entonces ese test **falla a propósito**: la contradicción sigue viva y es
mejor que esté en rojo en la consola que en silencio dentro del producto.
