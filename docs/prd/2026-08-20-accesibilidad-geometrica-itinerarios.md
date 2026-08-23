# PRD — Accesibilidad geométrica de itinerarios: anchos de paso y radios de giro (OP-17)

**Estado:** Borrador · **Fecha:** 2026-08-20 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 0. Alcance de esta Fase, explícito

Este PRD documenta **OP-17**, decidido por Pablo el 2026-08-20 (`docs/AGENTE_BACKLOG.md` §13.3, entrada "Decidida el 2026-08-20"), marcado en el propio backlog como **"PRÓXIMA, tras cerrar V1"** — no antes. No implementa nada; es el primer paso que el propio backlog ya prevé para esta entrada ("Tareas: por definir cuando se aborde").

Reutiliza el mismo motor geométrico que `OP-16` (`superficies.medicion_de_planta`, `analyzer/medicion.py`) y **complementa, sin sustituir**, las comprobaciones de accesibilidad que ya existen hoy en `analyzer/evaluator.py` (espacio de giro por baño, ancho mínimo de estancia, itinerario accesible de 1.20m). No toca el techo de C4 ni el registro de capacidades (`agente/registro.py`, D-12): esto es una extensión de checks geométricos, no una Capacidad nueva.

**Aviso honesto de alcance, desde ya:** la descripción de OP-17 en el backlog promete tres cifras — anchos de paso libres, radios de giro y pendientes de rampa. De las tres, **solo las dos primeras son calculables hoy** con los datos que el repositorio tiene. Ver §6 y §14.

## 1. Problema que resuelve

Hoy, la accesibilidad geométrica se evalúa como una serie de proxies puntuales, no como un recorrido real:

- `evaluate_bathroom_turning_space` mide el espacio de giro **dentro de cada baño**, aislado.
- `evaluate_minimum_room_width` mide el ancho mínimo **de cada estancia**, aislado.
- `evaluate_itinerario_accesible` comprueba que **al menos un** Pasillo tenga lado corto ≥1.20m — un umbral fijo sobre una pieza, no una medición a lo largo de la ruta real que un arquitecto (o una silla de ruedas) recorrería desde la entrada hasta cada estancia.

Ninguno de los tres responde a la pregunta que el backlog pone en el título de OP-17: *"¿se puede circular por esta planta y llegar a todas partes?"* — un pasillo puede pasar el check de ancho fijo y aun así tener un estrechamiento puntual (un resalte de tabique, un cambio de sección) que un check de pieza completa no detecta. Es el mismo tipo de hueco que ya motivó `analyzer/circulation.py` para los recorridos en general (recorridos absurdos, espacios de paso), pero aplicado específicamente a accesibilidad, que hoy no lo tiene.

## 2. Usuario afectado

El mismo arquitecto de hoy, evaluando un proyecto (DXF real o generado) con requisitos de accesibilidad — vivienda plurifamiliar, uso público o colectivo. No abre un segmento de usuario nuevo: endurece una comprobación que ya se hace, igual que la Fase A de parcela de hoy.

## 3. Objetivo de negocio

Accesibilidad es, en muchos usos, una comprobación bloqueante en visado (DB-SUA). Un hallazgo que dice "pasa/no pasa contra 1.20m fijo" es mucho menos defendible ante un colegio que uno que dice "el punto más estrecho del recorrido entre la entrada y el Dormitorio 2 mide 1.14m, aquí" — misma lógica de defendibilidad que ya motivó la Fase A de procedencia de parcela de hoy.

## 4. Objetivo técnico

Una vez implementado:

1. Para cada itinerario del grafo que ya construye `analyzer/circulation.py`, se mide el **ancho libre mínimo real** a lo largo del tramo (no un promedio ni un valor fijo de la pieza), con la pieza/segmento concreto del que sale la cifra.
2. Donde la geometría lo permite, se reporta el **diámetro de giro real alcanzable** en los puntos relevantes del recorrido — no solo un pass/fail contra el umbral fijo `turning_space_min` que ya existe.
3. Lo que **no** es evaluable hoy (anchos de hueco de puerta, pendientes de rampa) se dice explícitamente, con el mismo patrón que ya usa `evaluator.get_missing_data_warnings` — nunca se omite en silencio ni se asume "sin problema".
4. Ningún check existente cambia de valor ni de comportamiento — esto es un añadido.

## 5. Casos de uso

1. El arquitecto analiza un DXF de vivienda plurifamiliar; además del espacio de giro por baño, ve el ancho libre mínimo medido en cada tramo del itinerario entre la entrada y cada estancia.
2. Un pasillo tiene un estrechamiento puntual que hoy pasa el check de ancho fijo (por medirse sobre la pieza completa, no sobre el punto más desfavorable) — con OP-17 se detecta el punto real más estrecho.
3. El arquitecto ve, listado de forma explícita, qué no se ha podido comprobar (anchos de puerta, pendientes de rampa) en vez de asumir en silencio que no hay problema.

## 6. Casos límite

- **Itinerarios con geometría cóncava o en L**: la técnica de erosión/offset del polígono de circulación debe manejar autointersección sin romper geometría — mismo problema, ya resuelto una vez en este repo para otro propósito (`poligonoAutointersecta`, `static/viewer-terreno.js`, usado por el sólido capaz del Sandbox, `docs/prd/2026-08-17-solido-capaz-sandbox.md`).
- **Unidades sin "Pasillo" etiquetado en el grafo**: ya documentado que 3 de los 5 checks de `circulation.py` no disparan en `ejemplo.dxf` por esta misma razón — el mismo límite aplicaría aquí; no es un fallo nuevo, es una limitación conocida del dato de entrada.
- **Plano sin ninguna puerta modelada** (el caso general hoy — no hay modelo de carpintería): ancho de hueco de puerta y pendiente de rampa son explícitamente "no evaluable", nunca un pase falso positivo.

## 7. Flujo del usuario

Sin cambio en el flujo de entrada (sigue siendo subir DXF o generar un proyecto). Se añade un bloque de hallazgos nuevo, o se enriquece el existente de accesibilidad, en el informe/API ya existentes.

## 8. Criterios de aceptación

1. Para cada tramo del itinerario del grafo de `circulation.py`, el ancho libre mínimo medido se muestra con la pieza/segmento concreto del que sale.
2. Donde la geometría lo permite, se muestra el diámetro de giro real alcanzable en los puntos relevantes del recorrido, no solo pass/fail contra el umbral fijo ya existente.
3. La lista de "no evaluable" (ancho de hueco de puerta, pendiente de rampa) aparece explícitamente cuando corresponda — nunca en silencio.
4. La suite de tests existente de `analyzer/evaluator.py` y `analyzer/circulation.py` sigue en verde sin tocarla.
5. `UMBRALES_TIPOLOGIA` sigue siendo la única fuente de los umbrales por tipología — no se duplica una tabla nueva de parámetros.

## 9. Riesgos

- **Técnico, medio.** El grafo de `circulation.py` usa una tolerancia de distancia entre centroides (`WALL_GAP_TOLERANCE_M`) para decidir adyacencia, no geometría de paso real. Medir "ancho libre" real a lo largo de una ruta exige una técnica distinta — erosión/buffer del área de circulación —, que hoy solo existe en el repo, con otro propósito, en `analyzer/spatial_quality.py` (`_check_dead_space`, apertura morfológica) y en cliente (`viewer-sandbox.js`/`viewer-terreno.js`, para geometría de parcela, no de planta). La técnica ya está probada en este repo; aplicarla a esta finalidad concreta es trabajo nuevo, no un riesgo de invención desde cero.
- **De arquitectura, a decidir en la implementación, no aquí.** Si esto se integra como bloque nuevo dentro del pipeline CTE de `evaluator.py` (con `IssueReport`, cita de código DB-SUA, como `evaluate_itinerario_accesible`) o como módulo aparte no-normativo (como `circulation.py`/`spatial_quality.py`, sin cita legal). Ya hay precedente de ambos patrones conviviendo en el repo; la decisión no es obvia y no se fuerza aquí.
- **Techo de C4, respetado.** Esto es una extensión de checks geométricos ya existentes sobre datos que ya se miden (mismo motor que OP-16), no una Capacidad nueva registrada en `agente/registro.py`. Si al implementar resultara necesario tocar el registro de capacidades, es motivo de pausa y pregunta a Pablo — no una decisión de este documento.
- **De producto, real y hay que decirlo con claridad.** Dos de los tres sub-entregables que promete la descripción de OP-17 en el backlog — anchos de hueco de puerta y pendientes de rampa — **no son calculables hoy**: no existe modelo de carpintería (puertas como objetos) ni datos de cota vertical/pendiente en el pipeline DXF, y el propio `evaluator.py` ya lo advierte explícitamente en `get_missing_data_warnings`. Ver §14.
- **De negocio, ninguno nuevo.** No compite por las mismas horas que `REFACTOR_MASTERPLAN.md`.

## 10. Impacto sobre módulos existentes

| Fichero | Qué tocaría |
|---|---|
| `analyzer/circulation.py` | Grafo de recorridos ya construido — candidato natural para añadir la medición de ancho libre mínimo por tramo del itinerario. |
| `analyzer/spatial_quality.py` | Técnica de erosión/dilatación de polígono (`_check_dead_space`) ya probada en el repo — reutilizable para calcular ancho libre real y diámetro de giro alcanzable. |
| `analyzer/medicion.py` | Motor de medición de OP-16 (ver `docs/prd/2026-08-19-capacidades-de-medicion-de-planta.md`) — fuente de los polígonos reales sobre los que medir. |
| `analyzer/evaluator.py` | `evaluate_bathroom_turning_space`, `evaluate_minimum_room_width`, `evaluate_itinerario_accesible`, `UMBRALES_TIPOLOGIA` (`corridor_width_min`, `turning_space_min`) — checks ya existentes que OP-17 debe complementar sin duplicar ni contradecir, mismo patrón deliberado de convivencia ya usado entre otros dos bloques del propio `evaluator.py`. |
| `app.py` / `analyzer/api_serializer.py` | Wiring del nuevo bloque de hallazgos hacia la API, si se decide exponerlo — no se toca en este PRD. |
| `static/index.html` | Visualización del nuevo hallazgo — fuera de alcance de este PRD (documentación, no implementación). |

## 11. Plan de implementación dividido en pequeñas tareas

Especulativo — se valida y se detalla si Pablo aprueba el PRD:

1. **Decisión de ubicación** (evaluator.py pipeline CTE vs. módulo separado no-normativo) — con Pablo, antes de escribir código. Sin estimación de horas: es una decisión de producto, no una tarea de desarrollo.
2. **Medición de ancho libre mínimo** a lo largo del grafo de `circulation.py`, reutilizando la técnica de erosión de `spatial_quality.py` (~3h).
3. **Cálculo de diámetro de giro alcanzable** en los nodos relevantes del recorrido (~2h).
4. **Wiring a la API/serializer**, si aplica (~1h).
5. **Tests** (~2h).

Explícitamente fuera de este plan: anchos de hueco de puerta y pendientes de rampa — no se planifican como tarea porque no son calculables hoy (§9, §14); quedarían para un PRD futuro si Pablo decide construir primero un modelo de carpintería/cotas verticales.

Total estimado (sin contar la decisión previa de la tarea 1): ~8h.

## 12. Plan de pruebas

- Nuevo test sobre `circulation.py`: unidad sintética con un pasillo con un estrechamiento puntual — verificar que se detecta el punto más estrecho real, no un promedio ni el ancho de la pieza completa.
- Nuevo test sobre el cálculo de diámetro de giro: unidad sintética con geometría conocida donde el diámetro inscrito es calculable a mano.
- Regresión completa de `analyzer/evaluator.py` y `analyzer/circulation.py` — deben seguir en verde sin tocarlas.

## 13. Métricas para medir el éxito

No hay una métrica de producto medible a corto plazo (es una mejora de precisión sobre una comprobación que ya se hace, no una función nueva que el arquitecto elija usar más o menos) — el criterio de éxito es de auditoría: dentro de un mes, un hallazgo de accesibilidad expone la pieza concreta y el punto real de la que sale la cifra, no solo un pass/fail contra un umbral fijo.

## 14. Posibles motivos para NO implementar la idea (o recortarla)

- **El propio backlog fija esto como "próxima, tras cerrar V1"**, no antes — implementarlo hoy competiría con lo que sí está priorizado para cerrar V1 primero (`docs/AGENTE_BACKLOG.md` §13.3).
- **Recorte honesto posible:** implementar solo el ancho libre mínimo a lo largo del itinerario (tarea 2), dejando el diámetro de giro real (tarea 3) para una segunda vuelta, ya que el umbral fijo `turning_space_min` ya cubre ese caso, con menos precisión pero sin coste adicional. Se apunta como recorte posible, no como recomendación — el backlog describe las tres cifras como el "devuelve" completo de OP-17, así que este PRD no lo recorta por su cuenta.
- **Motivo de fondo, el más importante:** dos de las tres cifras que promete el backlog para OP-17 (anchos de hueco de puerta, pendientes de rampa) no son honestamente entregables hoy sin datos que el repositorio no tiene. Si Pablo aprueba este PRD asumiendo que OP-17 va a devolver esas tres cosas completas, hay que decírselo explícitamente aquí: no, salvo que antes se abra un PRD aparte para un modelo de carpintería/cotas verticales — algo que hoy ni siquiera está en el backlog.

---

**Decisión:** _pendiente de revisión por Pablo_
