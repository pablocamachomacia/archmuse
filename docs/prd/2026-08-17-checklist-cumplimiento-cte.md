# PRD — Checklist de cumplimiento CTE (DB-SI / DB-SUA / Habitabilidad)

**Estado:** Borrador · **Fecha:** 2026-08-17 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 0. Resumen para decidir rápido

Encargo de Pablo: un `analyzer/cte_checker.py` que audite las plantas generadas contra el CTE (distancia a escalera de evacuación DB-SI, superficies mínimas y anchuras DB-SUA/habitabilidad) y un panel "Checklist de Cumplimiento" con indicadores verde/rojo.

Antes de escribir una línea de código, un hallazgo que cambia el planteamiento por completo: **ArchMuse ya tiene un motor de reglas CTE maduro y en producción** — no hace falta construirlo, hace falta **exponerlo** como checklist y **rellenar dos huecos reales**. Escribir `cte_checker.py` como motor nuevo desde cero duplicaría lógica ya escrita, testeada y documentada, con el riesgo real de que el nuevo cálculo diverja del existente y el mismo proyecto se contradiga a sí mismo sobre si una vivienda cumple o no.

Lo que ya existe hoy, verificado leyendo el código (no de memoria):

- **Distancia de evacuación (DB-SI)**: `analyzer/evaluator.py::evaluate_evacuation_distance` (línea 1807) ya mide el recorrido real por el grafo de piezas contiguas hasta la salida de la vivienda, con `MAX_EVACUATION_DISTANCE_M = 25.0` (línea 1768). El propio docstring de esa función (líneas 1831-1838) ya documenta la limitación honesta: **los 25 m del DB-SI son hasta la salida del EDIFICIO (portal/escalera), no hasta la puerta de la vivienda**, y el modelo no tiene geometría de zonas comunes — así que hoy se mide un proxy (recorrido interior hasta la pieza de circulación de la propia vivienda), nunca la distancia real que exige la norma. Existe también `circulation.py::_check_evacuation_route`, una segunda medición del mismo umbral con distinta topología (grafo de recorridos vs. recta al perímetro), ya reconciliada y documentada como "miden cosas distintas, mismo umbral".
- **Itinerario accesible ≥1.20 m (DB-SUA-2/9)**: `evaluator.py::evaluate_itinerario_accesible` (línea 1993) ya existe, ya está integrado en `chain_effects.py::_regla_pasillo_estrecho` (línea 63) con severidad IMPORTANTE y cita normativa, y ya aparece en el informe.
- **Superficie mínima de dormitorio**: `evaluator.py` línea 2151 ya la comprueba, con severidad CRÍTICO y código `HABITABILIDAD-SUP`, ya citado en `referencias_normativas.py`.
- `referencias_normativas.py` ya mantiene el catálogo de códigos → texto legal (`CTE-DB-SUA`, `HABITABILIDAD-SUP`, etc.) que cualquier regla nueva debe reutilizar, no reinventar.
- `checklist_campo.py` + su panel en `static/` (PRD `2026-08-16-checklist-inspeccion-campo.md`) ya establece el patrón visual verde/rojo/aviso para un panel de checklist — es la plantilla directa a reutilizar para "Checklist de Cumplimiento", no un panel nuevo desde cero.

Lo que **de verdad no existe hoy** y sí es trabajo nuevo:

- Anchura mínima de **hueco de paso** (puertas): ninguna regla lo comprueba.
- Superficie mínima de **estancias principales más allá del dormitorio** (salón, cocina): `evaluator.py` solo comprueba dormitorio.
- Un **agregador** que junte todos estos resultados (existentes + nuevos) en forma de checklist pass/fail por regla, en vez de como `IssueReport`/`ChainEffect` sueltos.
- La distinción **25 m fondo único / 50 m con dos salidas** del encargo: hoy no existe ningún concepto de "número de salidas del edificio" en el modelo — ver §6, es el punto de mayor riesgo de honestidad de este PRD.

## 1. Problema que resuelve

Las reglas CTE relevantes existen ya en ArchMuse, pero están repartidas entre `evaluator.py` (bloques numerados, `IssueReport`), `circulation.py` y `chain_effects.py`, mezcladas con reglas que no son normativas (eficiencia, orientación). No hay un sitio único donde el arquitecto vea, de un vistazo, "¿esta vivienda cumple o no cumple el CTE en los puntos que sí puedo comprobar hoy", con la trazabilidad legal (artículo/DB) visible.

## 2. Usuario afectado

El mismo arquitecto que ya usa el resto de checks de ArchMuse — aquí en el momento de validar una distribución (generada por IA o subida) antes de darla por buena, no en visita de campo (eso ya lo cubre `checklist_campo.py`, un checklist distinto y no normativo).

## 3. Objetivo de negocio

Es el pilar de "asesor normativo" de `NORTH_STAR_2031.md` hecho visible de un vistazo — pero el riesgo de `DESTROY_ARCHMUSE.md` que más aplica aquí es el mismo que ya se resolvió con la distancia de evacuación en 2026-08-05 (ver cita en §0): un checklist en verde que en realidad no ha comprobado el criterio real es el peor fallo posible en una app que se apoya en credibilidad técnica. Este PRD solo aporta valor si cada fila del checklist es honesta sobre qué mide exactamente y qué no puede comprobar todavía.

## 4. Objetivo técnico

`analyzer/cte_checker.py` como **capa de agregación**, no de recálculo:

- Reutiliza `evaluator.evaluate_evacuation_distance`, `evaluator.evaluate_itinerario_accesible` y la comprobación de superficie mínima de dormitorio ya existentes — las llama, no las reimplementa.
- Añade las dos reglas genuinamente nuevas: anchura mínima de hueco de paso, superficie mínima de estancias principales no-dormitorio.
- Devuelve una lista de `ChecklistItem` (código normativo, título, estado `cumple / no_cumple / no_evaluable`, medida real, umbral, motivo si `no_evaluable`) — mismo espíritu que `checklist_campo.py`: un ítem `no_evaluable` explícito es preferible a forzar un "cumple" sin comprobar.
- La regla de 25 m/50 m con dos salidas **no se auto-detecta** (el modelo no tiene esa información) — ver §6 para el diseño honesto de esto.

## 5. Casos de uso

1. Arquitecto genera o analiza una vivienda, abre "Checklist de Cumplimiento" → ve una fila por regla (evacuación, itinerario accesible, superficie de dormitorio, superficie de estancias principales, anchura de huecos de paso), cada una en verde/rojo/gris (no evaluable) con la medida real y el umbral.
2. Una fila en rojo (p. ej. hueco de paso de 0.72 m contra un mínimo de 0.80 m) muestra el artículo CTE exacto (reutilizando `referencias_normativas.py`) y qué habitación/puerta concreta falla.
3. Arquitecto quiere comprobar el criterio de 50 m (dos salidas) en vez del de 25 m → marca explícitamente "este edificio tiene dos salidas de evacuación independientes" (checkbox, no autodetectado) y el checklist recalcula el umbral de esa fila, dejando visible que es una afirmación del usuario, no un hecho verificado por ArchMuse.

## 6. Casos límite

- **Vivienda sin pieza de circulación identificable**: la fila de evacuación pasa a `no_evaluable`, reutilizando el motivo que ya devuelve `evaluate_evacuation_distance` (línea 1846) — nunca "cumple" por defecto.
- **El umbral de 50 m con dos salidas**: como el modelo no tiene geometría de portal/escalera ni sabe si el EDIFICIO (no la vivienda) tiene una o dos salidas independientes, este dato **no puede autodetectarse hoy con ningún nivel de fiabilidad** — es información a nivel de edificio completo, no de vivienda individual, y ArchMuse analiza viviendas. Diseño propuesto: checkbox explícito "confirmo que el edificio tiene dos salidas de evacuación alternativas" controlado por el usuario, con el checklist dejando dicho que el umbral usado (25 o 50 m) depende de esa afirmación no verificada — mismo patrón que el ratio €/m² de la pestaña de Viabilidad Económica.
- **"1.10 m" de anchura de pasillo citado en el encargo**: no coincide con ningún valor ya usado en el código (`evaluator.py` usa 1.20 m para itinerario accesible DB-SUA-2/9, que es el único ancho de pasillo con base normativa ya verificada en este proyecto). El CTE DB-SUA no fija una anchura mínima general de pasillo en vivienda fuera del itinerario accesible; esa cifra suele venir de normativa autonómica de habitabilidad (que varía por comunidad, mismo caso ya documentado en `api_serializer.py:194` para superficie mínima de vivienda). Antes de codificar 1.10 m como si fuera CTE, hay que decidir: ¿se trata como parámetro de habitabilidad autonómica configurable (mismo criterio que superficie mínima), o Pablo confirma una fuente concreta para ese número? Ver §14.
- **Hueco de paso sin dato de puertas real**: el modelo no tiene puertas modeladas explícitamente (ver limitación ya documentada en `circulation.py`, líneas 8-16: "el modelo no tiene datos reales de puertas"). La anchura de hueco de paso solo puede comprobarse si existe un hueco/puerta detectado en el DXF de origen (proyectos analizados) — en proyectos generados por IA sin geometría de puerta explícita, esta fila debe marcarse `no_evaluable`, no asumir un valor.
- **Estancia principal sin superficie mínima clara** (p. ej. "Salón-Cocina" combinado): reutilizar el mismo criterio de `evaluator.py` para clasificación de piezas (`_normalize`, patrones de etiqueta) en vez de inventar una clasificación paralela.

## 7. Flujo del usuario

1. Arquitecto abre un proyecto con al menos una vivienda con planta resuelta.
2. Abre "Checklist de Cumplimiento" (nuevo panel, mismo patrón visual que `checklist_campo.py`).
3. Ve una fila por regla: verde (cumple, con medida real), rojo (no cumple, con medida real + artículo CTE), gris (no evaluable, con el motivo).
4. Si quiere comprobar el umbral de 50 m, marca el checkbox de "dos salidas" y ve la fila de evacuación recalculada, con la afirmación visible como propia.

## 8. Criterios de aceptación

1. La fila de evacuación del checklist usa el mismo número que ya devuelve `evaluator.evaluate_evacuation_distance` para esa vivienda — no una medición paralela.
2. La fila de itinerario accesible usa el mismo resultado que ya calcula `evaluator.evaluate_itinerario_accesible` — reutilizado, no reimplementado.
3. Ninguna fila del checklist muestra "cumple" en una vivienda donde el dato de origen (puertas, piezas de circulación) no existe — se muestra `no_evaluable` con motivo, verificable con un proyecto sintético sin puertas.
4. El umbral 50 m solo se aplica cuando el usuario ha marcado explícitamente el checkbox de dos salidas, y el checklist deja visible que es una afirmación del usuario.
5. Cada fila en rojo cita el código de `referencias_normativas.py` correspondiente (reutilizado, no un texto nuevo suelto).
6. `analyzer/cte_checker.py` es testeable con datos sintéticos sin depender de Flask.

## 9. Riesgos

- **Riesgo de honestidad, el mismo de siempre en este proyecto**: repetir aquí, con una regla nueva, el error que ya se corrigió en evacuación en 2026-08-05 (checklist en verde que no ha comprobado nada real) sería especialmente grave porque el nombre del panel ("Checklist de Cumplimiento") suena a verificación normativa definitiva.
- **Riesgo de duplicar y divergir**: si `cte_checker.py` reimplementa en vez de reutilizar, cualquier corrección futura en `evaluator.py` (como la ya documentada de 2026-08-05) puede dejar de propagarse al checklist y las dos partes de la app dirían cosas distintas sobre la misma vivienda.
- **Fuente del valor 1.10 m sin verificar** (§6) — publicar un umbral como si fuera CTE cuando en realidad es autonómico/no verificado dañaría la misma confianza que este proyecto protege deliberadamente en superficie mínima de vivienda.
- Compite por tiempo con `REFACTOR_MASTERPLAN.md` y con los otros PRD ya en cola (Viabilidad Financiera, exportación DXF con muros reales).

## 10. Impacto sobre módulos existentes

- **Nuevo** `analyzer/cte_checker.py`: agregador puro, importa y llama a `evaluator.py`/`circulation.py`, añade `_check_hueco_paso` y `_check_superficie_estancia_principal` como las dos reglas genuinamente nuevas.
- `analyzer/referencias_normativas.py`: nuevas entradas para los códigos de las 2 reglas nuevas (hueco de paso, superficie de estancia principal), mismo formato que las existentes.
- `app.py`: no debería requerir un endpoint nuevo si el checklist se calcula sobre datos ya presentes en la respuesta de análisis/generación — evaluar si se sirve embebido en la respuesta existente o en un endpoint propio ligero.
- `static/`: nuevo panel siguiendo el patrón de `checklist_campo.py` + su overlay ya existente en `static/index.html`/`app.js`.
- Ningún cambio en `evaluator.py` ni `circulation.py` salvo que, al integrarlos, aparezca algún ajuste menor de superficie de API (exponer un resultado que hoy es interno).

## 11. Plan de implementación dividido en pequeñas tareas

1. `analyzer/cte_checker.py`: `ChecklistItem` (dataclass) + función que envuelve `evaluate_evacuation_distance` en un ítem checklist, con el caso `no_evaluable` ya cubierto.
2. Envolver `evaluate_itinerario_accesible` igual.
3. Envolver la comprobación de superficie mínima de dormitorio igual.
4. Nueva regla: `_check_hueco_paso` — solo evaluable si hay geometría de puerta/hueco real en el proyecto; `no_evaluable` en caso contrario.
5. Nueva regla: `_check_superficie_estancia_principal` — salón/cocina, con el umbral que Pablo confirme como fuente (ver §14).
6. Checkbox de "dos salidas" + recalculo del umbral 25/50 m — decidir si vive en el estado del checklist o en el proyecto.
7. Tests: `tests/test_cte_checker.py`, con datos sintéticos, incluyendo los 3 casos `no_evaluable` de §6.
8. UI: panel "Checklist de Cumplimiento", reutilizando el CSS/patrón de `checklist_campo.py`.
9. Verificación con un proyecto real generado (mix 20/60/20/0 ya usado en sesiones anteriores) y uno analizado desde DXF con puertas reales si existe alguno en `tests/fixtures`.

## 12. Plan de pruebas

- `python -m py_compile app.py analyzer/cte_checker.py`.
- `tests/test_cte_checker.py`: por cada regla, un caso que cumple, uno que no cumple, uno `no_evaluable`.
- Verificar contra `tests/test_evacuacion.py`, `tests/test_itinerario_accesible.py` ya existentes que los números que expone el checklist coinciden exactamente con los que esos tests ya validan para `evaluator.py` — es la prueba de que no hay divergencia.

## 13. Métricas para medir el éxito

Cualitativo: Pablo confirma que ninguna fila del checklist podría leerse como "CTE verificado al 100%" cuando en realidad mide un proxy, y que el checklist no contradice en ningún caso lo que ya dice el informe PDF existente para la misma vivienda.

## 14. Posibles motivos para NO implementar la idea (o para recortar el alcance)

- **La superficie mínima de estancias principales y la anchura de pasillo tienen la misma trampa que ya se documentó para superficie mínima de vivienda**: son, en gran parte, competencia autonómica, no un número único del CTE. Publicar 1.10 m sin una fuente concreta sería inventar una cifra con la misma autoridad aparente que el resto de reglas CTE reales del proyecto. Recomiendo antes de implementar: o (a) Pablo confirma la fuente exacta del valor (¿CTE DB-SUA artículo concreto, o normativa autonómica de una comunidad específica?), o (b) se trata como parámetro configurable por el usuario, igual que el ratio €/m² de Viabilidad Económica, con el mismo badge de "no es un dato verificado de ArchMuse".
- **La regla 25 m/50 m con dos salidas no puede resolverse con datos reales del edificio hoy** — es, en el mejor caso, una casilla de confirmación del propio usuario, nunca una detección de ArchMuse. Si el valor esperado era "ArchMuse detecta automáticamente si el edificio tiene dos salidas", eso no es alcanzable con el modelo de datos actual (no hay geometría de edificio completo, solo de vivienda) y sería un proyecto bastante más grande (modelar el edificio, no solo la vivienda).
- **El hueco de paso no es evaluable en la mayoría de proyectos generados por IA** (sin geometría de puerta real) — el valor de esta fila concreta puede ser bajo en la práctica si la mayoría de casos de uso terminan en `no_evaluable`. Si eso resulta ser el caso dominante tras la primera implementación, vale la pena reconsiderar si merece su propio panel o si debería posponerse hasta que el generador modele puertas reales (mismo punto ya señalado en el PRD de exportación DXF, §14, sobre el generador no teniendo muros/puertas/huecos reales — son la misma carencia de fondo, dos PRD distintos tropezando con ella).
- Si Pablo confirma la fuente del valor de anchura de pasillo/estancias principales y acepta que la regla de dos salidas es una casilla de usuario, no una detección, este PRD es implementable en el alcance descrito, apoyándose en el motor ya existente en vez de duplicarlo.

---

**Decisión:** **Aprobado (2026-08-17)**. Se implementa como capa de agregación sobre `evaluator.py`/`circulation.py`/`chain_effects.py` (§4 tal como está, no un motor nuevo). El umbral de evacuación de 50 m solo se aplica tras confirmación explícita del usuario (checkbox "dos salidas") — opción A de §6, nunca autodetección. La anchura de itinerario accesible usa 1.20 m (mismo valor ya verificado y en producción en `evaluator.py::evaluate_itinerario_accesible`, CTE DB-SUA-2/9) — se descarta el 1.10 m del encargo original por no tener fuente verificada (§14).
