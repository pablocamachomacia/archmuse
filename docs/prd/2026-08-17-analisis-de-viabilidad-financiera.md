# PRD — Análisis de viabilidad financiera (Cash Flow, Margen Promotor, TIR, sensibilidad)

**Estado:** Borrador · **Fecha:** 2026-08-17 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 0. Resumen para decidir rápido

Encargo de Pablo: un módulo nuevo `analyzer/feasibility.py` + una pestaña dedicada que calcule Cash Flow y margen del proyecto, muestre Margen Promotor (%), TIR estimada y Ratio de Eficiencia de Superficie (Útil/Construida), y permita un análisis de sensibilidad (±10% coste de construcción, variación de precio de venta).

Esto **no es la misma pieza** que la pestaña "Viabilidad Económica y Exportación" que ya existe hoy (`docs/prd/2026-08-17-viabilidad-economica-y-exportacion-dxf.md`, implementada en `static/app.js:2990-3180`) — es una evolución mucho más ambiciosa de la misma idea. Antes de proponer el plan, tres hallazgos que cambian el planteamiento:

- **El Ratio de Eficiencia de Superficie (Útil/Construida) es el único de los tres KPIs que ArchMuse puede calcular hoy con datos 100% reales**: la superficie útil por vivienda ya existe (`analyzer/superficie_util.py::superficie_util_db_si`, definición DB-SI real) y la superficie construida total ya existe (`cuadro_superficies.py`/`evaluator.py`, mismo dato que usa la pestaña de Viabilidad Económica actual). Este KPI se puede mostrar con confianza total, sin badge de "estimación tuya".
- **El Margen Promotor (%) y el Cash Flow dependen de "costes indirectos, licencias, honorarios técnicos, coste financiero" y de un "precio orientativo por m² de zona"** — ninguno de estos datos existe hoy en ArchMuse ni tiene fuente real detrás. Es exactamente el mismo punto que ya se resolvió en la pestaña de Viabilidad Económica actual (§0 y §14 de ese PRD): sin fuente de mercado verificada, cualquier valor por defecto sería un número inventado presentado como si viniera de ArchMuse. La solución ya adoptada y en producción — el usuario introduce sus propios valores, todo se etiqueta como estimación suya — es directamente reutilizable aquí, y este PRD la extiende, no la reinventa.
- **La TIR (IRR) es el riesgo real de este PRD, y es distinto a los anteriores.** Una TIR requiere un flujo de caja con *tiempos*: en qué mes se paga el suelo, en qué mes se factura cada certificación de obra, en qué mes entran los ingresos por venta. ArchMuse no tiene hoy ningún dato de calendario de obra ni de fases de venta — no existe un solo campo de fecha/duración en todo el modelo de proyecto. Calcular una TIR sin esto obliga a **inventar una estructura temporal** (duración de obra, ritmo de ventas, curva de certificaciones) que nadie ha introducido. Presentar esa TIR sin dejar clarísimo que la estructura temporal también es una hipótesis del usuario (no un cálculo de ArchMuse) sería el mismo error que este proyecto ya se ha negado a cometer con los ratios de coste — pero aquí el riesgo es mayor, porque una TIR *suena* a cálculo financiero riguroso y puede generar una falsa sensación de precisión que un simple margen bruto no genera. Este PRD solo es defendible si la TIR se construye con un modelo de fases explícitamente simple y editable por el usuario, con esa limitación dicha en la propia interfaz, no en la letra pequeña.

## 1. Problema que resuelve

Hoy, la pestaña de Viabilidad Económica responde "¿cuánto cuesta construir esto y qué margen bruto deja, en un único instante?" (PEM = superficie × ratio, margen = precio venta − PEM − suelo). No responde a las preguntas que de verdad usa un promotor para decidir si un proyecto sigue adelante: ¿qué rentabilidad relativa tiene la inversión (margen promotor %, no solo margen bruto en €), ¿compensa el tiempo y riesgo del capital invertido (TIR), y ¿qué tan bien aprovecha el edificio su superficie construida (eficiencia útil/construida, un indicador de diseño con impacto económico directo)? Y no permite explorar qué pasa si el coste de construcción sube un 10% o si el precio de venta baja — la pregunta que cualquier promotor hace antes de comprometer capital.

## 2. Usuario afectado

El mismo arquitecto de la pestaña de Viabilidad Económica actual, pero en un momento de decisión más avanzado: cuando ya tiene un proyecto con volumetría y mix de viviendas definidos y quiere presentarlo (a sí mismo, a un promotor, a un cliente) con las métricas que un promotor real usa para aprobar o rechazar una inversión. Sigue siendo **una sola persona en una sola sesión**, sin fuente de datos de mercado — no es el usuario de un futuro con feed de precios por zona.

## 3. Objetivo de negocio

Conecta con el mismo pilar de "asesor" de `NORTH_STAR_2031.md` que la pestaña de Viabilidad Económica, un paso más adentro: de "cuánto cuesta" a "compensa la inversión". El riesgo de credibilidad es el eje de `DESTROY_ARCHMUSE.md` que más aplica aquí — una TIR mal explicada que luego no se parece en nada a la real es más dañina para la confianza que no tener TIR. El valor de negocio solo es real si la honestidad del dato se mantiene: la pestaña debe leerse como una calculadora asistida potente, nunca como un informe de viabilidad de ArchMuse.

## 4. Objetivo técnico

- Un módulo nuevo y puro `analyzer/feasibility.py`, sin I/O, que recibe superficies (útil/construida, ya calculadas), un mix de viviendas, y un diccionario de parámetros económicos introducidos por el usuario (ratio €/m² construcción, coste de suelo, costes indirectos, licencias, honorarios técnicos, coste financiero, precio de venta por m² por tipología, y un modelo de fases simple para la TIR) y devuelve: Cash Flow por fase, Margen Promotor (%), TIR, Ratio de Eficiencia de Superficie.
- Reutiliza el mismo dato de superficie construida total y el mismo patrón de "campo vacío hasta que el usuario lo rellena, todo etiquetado como estimación propia" ya validado en la pestaña de Viabilidad Económica actual — no se reinventa esa convención.
- La TIR se calcula con un modelo de fases explícito y mínimo (ver §5/§6), nunca con fechas reales inventadas por ArchMuse.
- Análisis de sensibilidad: recalcular Margen Promotor y TIR con coste de construcción en −10% / base / +10%, y con precio de venta ajustable por el usuario (slider o campo), mostrando los tres/varios escenarios lado a lado — cálculo puro, sin llamadas a IA ni a red.

## 5. Casos de uso

1. Arquitecto con un proyecto que ya tiene mix de viviendas (Programa de Necesidades) y superficies calculadas abre "Viabilidad Financiera", introduce ratio de construcción, coste de suelo, costes indirectos/licencias/honorarios (como % del PEM o importe fijo, a elegir) y precio de venta por m² por tipología → ve PEM, Margen Promotor (%) y Ratio de Eficiencia Útil/Construida, todos con badge de estimación propia salvo el ratio de eficiencia (real).
2. El mismo arquitecto introduce una duración de obra en meses y un ritmo de ventas simplificado (p. ej. "todo se vende al finalizar obra" o "ventas repartidas linealmente durante la obra", las dos únicas opciones del modelo mínimo) → ve una TIR estimada, con aviso explícito de que la estructura temporal es una hipótesis suya, no un dato de ArchMuse.
3. Arquitecto quiere saber qué pasa si el coste de construcción sube: activa el análisis de sensibilidad → ve Margen Promotor y TIR recalculados en −10%/base/+10% de coste, y puede mover el precio de venta para ver el punto en que el margen se vuelve negativo.

## 6. Casos límite

- **Ningún dato introducido todavía**: la pestaña no debe mostrar TIR ni Margen Promotor con valores por defecto — se queda vacía/sin calcular, mismo criterio que la pestaña actual.
- **Mix de viviendas vacío o superficie construida cero** (proyecto sin Programa de Necesidades resuelto): el Ratio de Eficiencia y el Cash Flow no pueden calcularse — mostrar mensaje explicando qué falta (mismo patrón que el aviso ya añadido en Sandbox para "Generar plantas con IA" cuando falta el Sólido Capaz), no un error genérico.
- **TIR matemáticamente indeterminada** (todos los flujos de caja positivos, o todos negativos, o el newton-raphson/bisección del cálculo no converge): mostrar "TIR no calculable con estos datos", nunca un número forzado o `NaN` crudo.
- **Costes indirectos/honorarios como % vs. importe fijo**: si el usuario mezcla ambos criterios sin darse cuenta (p. ej. introduce honorarios como % pero el campo se interpreta como €), el resultado sería silenciosamente incorrecto — cada campo debe dejar inequívoca su unidad en la propia UI (mismo campo nunca acepta ambas).
- **Ratio de Eficiencia por debajo de umbrales típicos de mercado** (p. ej. <70%) o sospechosamente alto (>95%): no se bloquea ni se juzga — se muestra el número real, sin comentario editorial de ArchMuse sobre si es "bueno" o "malo", salvo que exista ya una fuente normativa real para ese juicio (no la hay hoy).

## 7. Flujo del usuario

1. Arquitecto abre un proyecto con mix de viviendas y superficies ya resueltos, entra en "Viabilidad Financiera" (pestaña nueva, junto a "Viabilidad Económica y Exportación" — ver §14 sobre si deben fusionarse).
2. Ve el Ratio de Eficiencia de Superficie (real, sin badge de estimación) calculado automáticamente.
3. Introduce ratio de construcción, coste de suelo, costes indirectos, licencias, honorarios técnicos, coste financiero y precio de venta por tipología → ve PEM, Cash Flow simplificado y Margen Promotor (%) en vivo.
4. Opcionalmente, introduce duración de obra y ritmo de ventas → ve TIR estimada, con el aviso de hipótesis propia visible junto al número, no en una nota aparte.
5. Activa "Análisis de sensibilidad" → ve tabla/gráfico con Margen Promotor y TIR en −10%/base/+10% de coste de construcción, y puede ajustar el precio de venta con un control para ver el efecto en tiempo real.

## 8. Criterios de aceptación

1. El Ratio de Eficiencia de Superficie coincide exactamente con superficie útil real (`superficie_util_db_si`) entre superficie construida total real (`cuadro_superficies.py`/`evaluator.py`) — mismos números que ya usa el resto de la app, sin recalcular con una fórmula distinta.
2. Ningún valor de coste, precio o TIR aparece pre-rellenado ni con un valor por defecto que el usuario no haya introducido — todos parten vacíos.
3. La TIR nunca se muestra sin, junto a ella, la indicación explícita de qué hipótesis de fases/tiempos la sustentan y que son del usuario, no de ArchMuse.
4. El análisis de sensibilidad recalcula Margen Promotor y TIR correctamente para −10%/+10% del ratio de construcción, verificable comparando manualmente los tres escenarios con la fórmula de `analyzer/feasibility.py`.
5. `analyzer/feasibility.py` es testeable sin Flask ni fixtures de proyecto real — funciones puras con datos sintéticos, con tests para el caso de TIR no convergente.

## 9. Riesgos

- **Riesgo de credibilidad (el central de este PRD)**: una TIR es el tipo de número que un promotor puede citar en una decisión de inversión real. Si no queda inequívoco que las fases/tiempos son una hipótesis del propio arquitecto, ArchMuse puede terminar pareciendo responsable de una proyección financiera que nunca hizo con datos reales. Mitigación: aviso visible junto al número (no en tooltip), nunca en texto pequeño.
- **Complejidad de UI**: cash flow + sensibilidad + TIR con fases es bastante más superficie de interfaz que la pestaña de Viabilidad Económica actual (3 campos). Riesgo de que la pestaña se sienta como una hoja de cálculo dentro de ArchMuse en vez de una herramienta guiada — mitigar con valores por defecto de fases razonables pero vacíos hasta que el usuario los confirme, no con más campos de los tres del modelo mínimo (§6).
- **Compite por tiempo** con lo ya priorizado en `REFACTOR_MASTERPLAN.md` y con la implementación aún pendiente de exportación DXF real con muros/puertas/huecos, si Pablo decide priorizar esa vía en su lugar (ver §14 del PRD de Viabilidad Económica).
- **Solapamiento de producto**: dos pestañas de "viabilidad" (Económica y Financiera) compitiendo por el mismo espacio mental del usuario es un riesgo de producto, no solo técnico — ver §14.

## 10. Impacto sobre módulos existentes

- **Nuevo** `analyzer/feasibility.py`: funciones puras — `calcular_pem`, `calcular_cash_flow_fases`, `calcular_margen_promotor`, `calcular_tir`, `ratio_eficiencia_superficie`, `analisis_sensibilidad`. Sin dependencias de red ni de IA.
- `app.py`: si el cálculo se mantiene client-side (como la pestaña actual) no requiere endpoint nuevo; si se decide mover a backend (recomendado para la TIR, que necesita un solver numérico — ver §11), nuevo endpoint `POST /api/proyectos/<id>/viabilidad-financiera` que recibe los parámetros del usuario y devuelve el cálculo, sin persistir nada nuevo en `analyzer/storage.py` salvo que Pablo quiera guardar los escenarios (fuera de alcance de este PRD).
- `static/app.js` o nuevo `static/viabilidad-financiera.js`: nueva pestaña, reutilizando el patrón de overlay ya usado por `#viabilidad-economica` y `#checklist-campo`.
- `static/style.css`: nuevas clases siguiendo la convención `.viabilidad-*` ya existente (o `.viabilidad-financiera-*` para no colisionar).
- Lee (no modifica) `analyzer/superficie_util.py`, `cuadro_superficies.py`/`evaluator.py`, y el mix de viviendas ya resuelto en `programa.num_viviendas_mix` (ver `static/entrevista.js`, `app.py::_parse_generar_params`).

## 11. Plan de implementación dividido en pequeñas tareas

1. `analyzer/feasibility.py`: `calcular_pem(superficie_construida, ratio_m2)` y `ratio_eficiencia_superficie(superficie_util, superficie_construida)` — reutilizan fórmulas ya probadas en la pestaña actual.
2. `analyzer/feasibility.py`: `calcular_margen_promotor(pem, coste_suelo, costes_indirectos, licencias, honorarios, coste_financiero, ingresos_venta) -> {margen_eur, margen_pct}`.
3. `analyzer/feasibility.py`: ingresos por venta a partir del mix de viviendas (`{dorm_1, dorm_2, dorm_3}` counts) × superficie media por tipología × precio €/m² introducido por el usuario por tipología.
4. `analyzer/feasibility.py`: `calcular_cash_flow_fases(...)` con el modelo mínimo de 2 fases (obra, venta) y `calcular_tir(flujos)` vía Newton-Raphson o bisección sobre `numpy_financial.irr`-equivalente casero (revisar si `numpy_financial` ya es dependencia; si no, implementar bisección simple, sin añadir dependencia nueva solo para esto).
5. `analyzer/feasibility.py`: `analisis_sensibilidad(parametros_base, variacion_coste=[-0.1, 0, 0.1])` — recalcula 2-4 y devuelve los escenarios.
6. Tests: `tests/test_feasibility.py`, con datos sintéticos, incluyendo el caso de TIR no convergente (§6).
7. UI: nueva pestaña "Viabilidad Financiera" (decisión previa necesaria: ¿pestaña nueva independiente o sección añadida a la pestaña de Viabilidad Económica ya existente? — ver §14, recomiendo resolver esto con Pablo antes de tocar HTML).
8. UI: formulario de parámetros + Cash Flow + KPIs (Margen Promotor %, TIR, Ratio de Eficiencia), con los avisos de estimación propia obligatorios en cada resultado no-real.
9. UI: bloque de análisis de sensibilidad (tabla o mini-gráfico ±10% coste, control de precio de venta).
10. Verificación: los 5 criterios de §8 con un proyecto con mix de viviendas real (usar el mismo proyecto de prueba "Gran Vía 1, Madrid" ya usado para verificar Sandbox → Generar plantas).

## 12. Plan de pruebas

- `python -m py_compile app.py analyzer/feasibility.py` (o `pytest --collect-only` si se integra en la suite).
- `tests/test_feasibility.py`: casos con datos sintéticos para cada función pura, incluyendo el caso límite de TIR no convergente y el de superficie construida cero.
- En vivo: los 3 casos de uso de §5, con el mismo proyecto de prueba ya validado en la sesión anterior (Sandbox, mix 20/60/20/0).

## 13. Métricas para medir el éxito

Cualitativo: Pablo confirma que la TIR, tal como se presenta, no podría confundirse con una proyección financiera real de ArchMuse; y que el Ratio de Eficiencia de Superficie es útil como indicador de diseño, no solo de negocio.

## 14. Posibles motivos para NO implementar la idea (o para recortar el alcance)

- **La TIR con un modelo de fases inventado por el usuario tiene un valor cuestionable**: si las fases/tiempos no vienen de un calendario de obra real (que ArchMuse no tiene ni está previsto que tenga pronto), la TIR resultante es, en el mejor caso, una ilustración pedagógica de cómo cambia la rentabilidad con el tiempo de exposición del capital — no una TIR de verdad que un promotor pueda usar para decidir. Recomiendo que la primera versión **no incluya TIR** y se limite a Margen Promotor (%), Cash Flow estático (sin fases temporales) y Ratio de Eficiencia — los tres KPIs donde ArchMuse puede ser honesto sin inventar una estructura temporal. La TIR quedaría como una fase 2 explícita, solo si Pablo confirma que el valor pedagógico compensa el riesgo de confusión.
- **Solapa directamente con la pestaña "Viabilidad Económica y Exportación" ya existente**: ambas piden al usuario ratio de construcción, coste de suelo y precio de venta. Tener dos pestañas de "viabilidad" con formularios parecidos pero resultados distintos (una con margen bruto simple, otra con margen promotor/TIR/sensibilidad) es más probable que confunda que que ayude. Recomiendo **extender la pestaña actual en vez de crear una segunda** — mismo formulario base, con un bloque adicional plegable "Análisis avanzado" para Margen Promotor, Ratio de Eficiencia y sensibilidad. Si Pablo prefiere mantenerlas separadas (p. ej. porque una es "estimación rápida" y la otra es "análisis serio para promotor"), este PRD se puede implementar como pestaña independiente sin cambios de fondo.
- Si Pablo confirma alcance mínimo honesto (sin TIR, o con TIR claramente marcada como hipótesis pedagógica) y decide si se fusiona con la pestaña existente o queda separada, este PRD es implementable tal como está.

---

**Decisión:** **Aprobado (2026-08-17)**, con alcance recortado respecto al §11 original: extiende la pestaña de Viabilidad Económica existente con un bloque plegable "Análisis Avanzado" (no pestaña separada) que muestra Margen Promotor (%), Cash Flow estático (sin fases temporales) y Ratio de Eficiencia de Superficie. **La TIR queda excluida de esta v1** (motivo ya documentado en §14: sin calendario de obra/ventas real, la TIR exigiría hipótesis de tiempos inventadas). Alcance de sensibilidad (±10% coste) se mantiene.
