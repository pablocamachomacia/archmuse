# Plan de implementación — Entrevistador arquitectónico

**Fecha:** 2026-08-12 · **Tipo:** plan de implementación, sin código · **Estado:** para decisión
**Etapa:** 0.5 — ejecuta lo ya aprobado en `docs/prd/2026-08-12-entrevistador-generador.md` v2 y
`docs/design/2026-08-12-contrato-entrevistador-generador.md`, con las 7 decisiones de Pablo ya incorporadas
donde corresponde (marcadas `[Decisión Pablo #N]` en el texto).

**Nada de este documento se ha ejecutado.** Cero código escrito o modificado, cero commit. Es el desglose en
tareas de ≤2h que ambos documentos anteriores pospusieron deliberadamente a esta etapa.

## Alcance — qué construye esto y qué no

**Construye:** el camino completo `persona normal → entrevista → Especificación Arquitectónica → generador
actual (`ai_generator.py`, sin sustituir) → evaluación → resultado auditable`, más el modo experto, más la
extensión mínima del generador ya diseñada en el contrato.

**No construye, y no debe confundirse con esto:** ningún generador arquitectónico nuevo. `place_rooms()` no se
toca ni se mejora. La calidad artística/geométrica del resultado sigue siendo la de hoy — esta etapa mejora la
fidelidad de la intención capturada, no la sofisticación de lo que `ai_generator.py` construye con ella (mismo
límite que el PRD v2 §11 ya declaró explícitamente y que este plan no reabre).

## Principio de aislamiento — la interfaz limpia pedida

Las Fases A-E producen y validan una `EspecificacionArquitectonica` + `ContextoCualitativo` que **no saben que
`ai_generator.py` existe**. La única fase que conoce `place_rooms()`, `SYSTEM_PROMPT` o `_build_user_message` es
la **Fase F**, y ahí el cambio se limita a un adaptador delgado (compilar → params, inyectar contexto en el
prompt, verificar directivas duras). **Cuando en el futuro se sustituya `place_rooms()` por un motor más
sofisticado, solo la Fase F se reescribe — A, B, C, D y E permanecen intactas**, porque consumen y producen la
Especificación, no la geometría. Esto no es una aspiración: es la razón por la que el orden de fases de este
documento pone F al final y la diseña como el único punto de contacto con el generador actual.

---

## FASE A — Modelo de estado

Sin Flask, sin Claude, sin UI. Solo estructuras de datos y persistencia — la base de la que dependen todas las
demás fases. Nuevo paquete aislado `analyzer/interview/` (mismo principio de aislamiento que `reasoning/` en
`PRD-001`: nada dentro de `analyzer/ai_generator.py`).

| # | Tarea | Archivos | Depende de | Criterio de aceptación |
|---|---|---|---|---|
| A1 | `EstadoEntrevista` + `RespuestaInterpretada` como dataclasses (PRD v2 §17-§18) | `analyzer/interview/modelo.py` (nuevo) | — | Serializa/deserializa a JSON sin pérdida; test de round-trip |
| A2 | `EspecificacionArquitectonica` + `CampoEspecificacion` (PRD v2 §22) | mismo archivo | A1 | Round-trip JSON; `especificacion_id` de cada campo es estable entre serializaciones |
| A3 | `DirectivaCualitativa` + `ContextoCualitativo`, con el catálogo cerrado de 5 categorías (contrato §6.1-§6.2) | `analyzer/interview/modelo.py` | A2 | Construir una `DirectivaCualitativa` con una categoría fuera del catálogo lanza error explícito **[Decisión Pablo #3]** |
| A4 | `TrazaDeGeneracion` (contrato §6.3) | mismo archivo | A2 | Round-trip JSON |
| A5 | Extender `storage.py`: tabla nueva `entrevistas` (id, estado JSON, especificacion JSON nullable, creado_en, modificado_en) — mismo patrón de `_migrar_columna_modelo`, idempotente | `analyzer/storage.py` | A1-A2 | `init_db()` sigue siendo idempotente; una base ya existente gana la tabla sin perder filas de `proyectos` |
| A6 | Extender `storage.py`: columna `traza_generacion` en `proyectos`, mismo patrón que la columna `modelo` (E2) — **persistida desde el primer commit [Decisión Pablo #2]** | `analyzer/storage.py` | A4 | Columna nullable, `ALTER TABLE ADD COLUMN` idempotente, filas antiguas con `NULL` |
| A7 | `guardar_entrevista()` / `obtener_entrevista()` / `guardar_traza_generacion()` — funciones de persistencia siguiendo exactamente el estilo ya existente (`guardar_proyecto`/`obtener_proyecto`) | `analyzer/storage.py` | A5-A6 | Test: guardar, reiniciar conexión, recuperar — idéntico byte a byte |
| A8 | Suite de tests unitarios de la Fase A completa (serialización, persistencia, catálogo cerrado) | `tests/test_interview_modelo.py` (nuevo) | A1-A7 | Cubre los 4 tipos de dato + las 2 tablas/columnas nuevas |

**Nota de riesgo de esta fase:** es la única con cambios de esquema de base de datos — cualquier error aquí se
paga en todas las fases posteriores. Por eso es también la fase recomendada para empezar (ver "qué fase
primero" al final).

---

## FASE B — API

Endpoints nuevos, todos aditivos. `/api/generar` y `/api/analizar` no se tocan en su comportamiento por
defecto — solo `/api/generar` gana una clave opcional en el body.

| # | Tarea | Archivos | Depende de | Criterio de aceptación |
|---|---|---|---|---|
| B1 | Diseño de contrato request/response de los 6 endpoints (tabla abajo) — documento de interfaz, no código | comentario/docstring en `app.py` o doc aparte | Fase A | Cada endpoint tiene un ejemplo de request y de response documentado |
| B2 | `POST /api/entrevista` — crea sesión, devuelve `sesion_id` + primera pregunta (bloque fijo, determinista, sin Claude) | `app.py` | A5-A7, C1-C2 | Nueva fila en `entrevistas`; responde sin llamar a Claude |
| B3 | `POST /api/entrevista/<id>/responder` — recibe una respuesta de turno, delega en el motor (Fase C), persiste el nuevo estado, devuelve la siguiente pregunta o el cierre | `app.py` | B2, Fase C | Estado persistido tras cada turno — sobrevive un reinicio del proceso |
| B4 | `GET /api/entrevista/<id>` — recupera el estado completo (para reanudar tras abandono) | `app.py` | B2 | Devuelve exactamente el estado que había al último turno guardado |
| B5 | `POST /api/entrevista/<id>/finalizar` — fuerza el cierre y compila a Especificación (delega en Fase D) | `app.py` | Fase D | Si faltan imprescindibles, quedan en `decisiones_pendientes`, nunca bloquea |
| B6 | `PATCH /api/entrevista/<id>/especificacion` — corrección de un campo del resumen; dispara invalidación en cascada (PRD v2 §28) | `app.py` | Fase D | Los campos con `derivada_de` apuntando al corregido se re-evalúan y quedan marcados como cambiados |
| B7 | `POST /api/entrevista/experto` — crea una Especificación vacía en `modo_origen="edicion_experta"`, sin turno conversacional — **comparte el mismo compilador que B5-B6 [Decisión Pablo #6]** | `app.py` | Fase D | La Especificación resultante es indistinguible en esquema de una producida por entrevista guiada |
| B8 | Extender `_parse_generar_params` para aceptar `contexto_cualitativo` opcional en el body de `/api/generar`, sin cambiar el comportamiento si no llega | `app.py` | Fase D, Fase F (contrato de forma) | Un request idéntico al de hoy (sin la clave nueva) produce exactamente la misma respuesta que hoy — test de regresión byte a byte |
| B9 | Tests de integración de la API (Flask test client) para B2-B8 | `tests/test_endpoints_entrevista.py` (nuevo) | B2-B8 | Cada endpoint cubierto con caso feliz + caso límite (id inexistente, estado corrupto) |

**Contrato de los 6 endpoints nuevos, resumen:**

| Endpoint | Entrada | Salida |
|---|---|---|
| `POST /api/entrevista` | `{}` (o modo inicial) | `{sesion_id, pregunta_actual, progreso}` |
| `POST /api/entrevista/<id>/responder` | `{respuesta: str/valor}` | `{pregunta_actual \| null, progreso, cerrada: bool}` |
| `GET /api/entrevista/<id>` | — | `EstadoEntrevista` completo |
| `POST /api/entrevista/<id>/finalizar` | `{}` | `EspecificacionArquitectonica` |
| `PATCH /api/entrevista/<id>/especificacion` | `{especificacion_id, nuevo_valor}` | `EspecificacionArquitectonica` actualizada + lista de campos recalculados |
| `POST /api/entrevista/experto` | `{}` | `{sesion_id, especificacion_vacia}` |

---

## FASE C — Motor de entrevista

100% determinista salvo C7/C8/C9 (las únicas tareas que llaman a Claude). Se construye y se prueba entera
antes de tocar Flask — B2-B3 son wrappers finos sobre esto.

| # | Tarea | Archivos | Depende de | Criterio de aceptación |
|---|---|---|---|---|
| C1 | Catálogo declarativo de las 15 preguntas (PRD v2 Parte I §6) — datos, no lógica imperativa por pregunta | `analyzer/interview/preguntas.py` (nuevo) | A1-A3 | Cada pregunta tiene tipo (A/O/C), categoría, `especificacion_id` de destino |
| C2 | Motor de bloques: fijo inicial (preguntas 1,4,5 juntas en una pantalla) → adaptativo → cierre (PRD v2 §19/§21.3) | `analyzer/interview/motor.py` (nuevo) | C1 | El bloque fijo se presenta siempre en una sola pantalla/turno, nunca 3 turnos separados |
| C3 | Cola priorizada para la siguiente pregunta del bloque adaptativo (PRD v2 §25: imprescindible sin resolver > contradicción pendiente > cuánto condiciona > coste de respuesta) | `analyzer/interview/motor.py` | C1-C2 | Test con estados sintéticos verificando el orden exacto de desempate |
| C4 | Preguntas condicionales — bifurcación de la pregunta 3 (¿tienes parcela?) y cualquier otra marcada `C` en el catálogo | `analyzer/interview/motor.py` | C1 | La rama no tomada nunca se pregunta |
| C5 | Contadores y límites: `turnos_totales` (máx. 20, aviso desde 15) y `llamadas_ia_consumidas` (máx. 5) **[Decisión Pablo #4]** | `analyzer/interview/motor.py` | A1 | Al alcanzar cualquiera de los dos, el motor pasa a cerrar con preguntas de opción cerrada exclusivamente |
| C6 | Detección determinista de contradicción — mismo campo, valor estructurado distinto (comparación directa, sin Claude) | `analyzer/interview/motor.py` | C1 | Cubre los campos de opción cerrada; los de texto libre quedan para C8 |
| C7 | Integración de Claude — llamada de interpretación del bloque fijo (preguntas 1,4,5 juntas → programa, no-negociables, prioridades, carácter) | `analyzer/interview/claude_interprete.py` (nuevo, reutiliza patrón `_extract_json` ya usado en `ai_analyst.py`/`ai_generator.py`) | C1-C2 | 1 llamada produce ≥3 `RespuestaInterpretada` distintas sobre un texto de prueba real |
| C8 | Integración de Claude — llamada de interpretación del bloque adaptativo abierto, **con detección de contradicción semántica incluida en el mismo prompt/salida** (contrato: no llamada aparte **[Decisión Pablo #5]**) | mismo archivo | C6-C7 | La salida estructurada incluye un campo opcional `contradiccion_detectada`; no existe ninguna llamada dedicada solo a esto |
| C9 | Reintento por baja confianza (condicional, dentro del presupuesto de 5) | mismo archivo | C7-C8 | Nunca se dispara más de una vez por dato; el contador de C5 lo contempla |
| C10 | Manejo de "no sé"/incompleto — estado explícito, nunca valor por defecto silencioso (PRD v2 §26) | `analyzer/interview/motor.py` | C1 | Produce `RespuestaInterpretada` con `naturaleza=Hipótesis`, `confianza=Baja`, motivo explícito |
| C11 | Criterio de parada compuesto (PRD v2 §28: imprescindibles resueltos + sin contradicciones pendientes + límite de llamadas/turnos) | `analyzer/interview/motor.py` | C5, C6, C10 | Función pura, testeable sin Flask ni Claude: `puede_cerrar(estado) -> bool` |
| C12 | Tests del motor completo, con Claude mockeado (nunca llamado de verdad en tests unitarios) | `tests/test_interview_motor.py` (nuevo) | C1-C11 | Cubre bloques, bifurcaciones, límites, contradicciones y parada, todo determinista salvo el mock |

---

## FASE D — Compilador

Traduce `EstadoEntrevista` (de la Fase C) o una edición directa (modo experto, Fase B7) en
`EspecificacionArquitectonica` + `ContextoCualitativo`. **Un único punto de entrada compartido**, resolviendo
directamente la Decisión Pablo #6.

| # | Tarea | Archivos | Depende de | Criterio de aceptación |
|---|---|---|---|---|
| D1 | `compilar_especificacion(estado: EstadoEntrevista) -> EspecificacionArquitectonica` — traduce cada `RespuestaInterpretada` a `CampoEspecificacion`, con `especificacion_id` estable tomado del catálogo de C1 | `analyzer/interview/compilador.py` (nuevo) | A2, C1 | Cada campo del catálogo tiene, como máximo, un `CampoEspecificacion` resultante |
| D2 | Interpolación determinista del mix de viviendas (PRD v2 §18: preferencia "más pequeñas y más" → números concretos, acotada por aritmética del solar, nunca una decisión de programa libre) | mismo archivo | D1 | Mismo input produce siempre el mismo resultado (determinismo verificado por test) |
| D3 | Compilación de `params_generador` — 1:1 con el `params` dict que hoy consume `_parse_generar_params` | mismo archivo | D1-D2 | Comparado campo a campo contra `_parse_generar_params` real, sin discrepancias de forma |
| D4 | Compilación de `ContextoCualitativo`/`DirectivaCualitativa` — mapeo categoría→`fuerza` (contrato §8.3), **solo para las 5 categorías del catálogo cerrado [Decisión Pablo #3]** | mismo archivo | A3, D1 | Un `CampoEspecificacion` de una categoría fuera del catálogo nunca produce una `DirectivaCualitativa` — se queda como decisión A (almacenado sin uso), no lanza directiva |
| D5 | Trazabilidad: `origen[]` de cada `CampoEspecificacion` apunta a los `turno_id`/`respuesta_id` reales de `EstadoEntrevista.historial_turnos` | mismo archivo | D1 | Para cualquier campo, se puede recuperar el texto literal de la respuesta que lo originó |
| D6 | Validación: los 8 imprescindibles (PRD v2 §2) deben quedar en `Hecho`/`Hipótesis`; si al compilar por `finalizar()` (B5) alguno sigue `pendiente`, se listan en `decisiones_pendientes`, nunca se inventa un valor | mismo archivo | D1 | Test con una entrevista deliberadamente incompleta produce `decisiones_pendientes` no vacío, no un error |
| D7 | El mismo `compilar_especificacion()` acepta también una edición de modo experto (un dict de valores ya estructurados, sin `EstadoEntrevista` real detrás) — **mismo compilador, dos orígenes [Decisión Pablo #6]** | mismo archivo | D1-D6, B7 | Una Especificación producida en modo experto pasa exactamente las mismas validaciones de D6 |
| D8 | Tests del compilador — deterministas, sin Claude, sin Flask | `tests/test_interview_compilador.py` (nuevo) | D1-D7 | Casos: entrevista completa, entrevista con huecos, edición experta, catálogo cerrado respetado |

---

## FASE E — UI

Sustituye `renderGenerarForm`. Nuevo archivo de cliente, no se amplía más `static/app.js` (~3000 líneas ya).

| # | Tarea | Archivos | Depende de | Criterio de aceptación |
|---|---|---|---|---|
| E1 | Pantalla de elección "Entrevista guiada" / "Modo experto" al pulsar "Generar proyecto" | `static/entrevista.js` (nuevo), `static/app.js` (solo el punto de entrada) | B2, B7 | Ambas opciones navegables desde el mismo menú que hoy abre `renderGenerarForm` |
| E2 | Componente de turno: pregunta abierta (texto libre) | `static/entrevista.js` | B3 | Envía a `POST /responder`, muestra la siguiente pregunta devuelta |
| E3 | Componente de turno: pregunta de opción cerrada / condicional | `static/entrevista.js` | B3 | Sin llamada a Claude perceptible por el usuario (latencia baja, feedback inmediato) |
| E4 | Indicador de progreso (imprescindibles resueltos / turnos usados frente al límite de 20) | `static/entrevista.js` | B4 | Visible en todo turno, coherente con PRD v2 §23 principio 7 |
| E5 | Pantalla de resumen — renderizado determinista por categoría, con procedencia visible (Hecho/Inferencia/Hipótesis) y aviso "guardado, sin uso todavía" donde `destino_generador != usado_directo` | `static/entrevista.js` | B5 | Ningún campo aparece sin su procedencia; ninguna llamada a Claude en esta pantalla (PRD v2 §21.1) |
| E6 | Edición por bloque en el resumen, con invalidación en cascada visible | `static/entrevista.js` | B6 | Corregir un campo del que dependía una inferencia muestra el cambio derivado, no lo oculta |
| E7 | Editor de modo experto — mismas 15 categorías, formulario estructurado, incluida la categoría 15 (estructura) exclusiva de este modo | `static/entrevista.js` | B7, D7 | Un arquitecto puede completar y confirmar sin pasar por ningún turno conversacional |
| E8 | Convergencia: ambos caminos llegan al mismo componente de resumen (E5-E6); alternar de modo a mitad sin perder lo introducido | `static/entrevista.js` | E1-E7 | Cambiar de modo conserva los campos ya compilados de la Especificación compartida |
| E9 | Manejo de abandono/reanudación en cliente — recuperar `sesion_id` desde almacenamiento local, `GET /api/entrevista/<id>` al volver | `static/entrevista.js` | B4 | Cerrar la pestaña y volver reconstruye exactamente el último turno guardado |
| E10 | Tests de navegador manuales/scriptados de E1-E9 (ver Fase G para el detalle de escenarios) | — | E1-E9 | Ver Fase G |

---

## FASE F — Integración con el generador

**Única fase que toca `ai_generator.py`.** Cambios aislados y aditivos, exactamente como quedó diseñado en el
contrato — nada de esto reescribe `place_rooms()` ni la lógica de reglas del prompt existente.

| # | Tarea | Archivos | Depende de | Criterio de aceptación |
|---|---|---|---|---|
| F1 | Añadir el párrafo fijo de precedencia a `SYSTEM_PROMPT` (contrato §8.1) | `analyzer/ai_generator.py` | Fase D (contrato de forma) | El resto de `SYSTEM_PROMPT` no cambia ni un carácter — diff mínimo, verificado por test de snapshot |
| F2 | Extender `_build_user_message` para anexar la sección "DIRECTIVAS ADICIONALES" solo si `params.get("contexto_cualitativo")` existe (contrato §8.2) | `analyzer/ai_generator.py` | F1, D4 | Sin `contexto_cualitativo`, el mensaje generado es idéntico al de hoy — test de regresión |
| F3 | `app.py:generar()` pasa `contexto_cualitativo` desde `params` a `generate_project()` — sin cambiar la firma pública de `generate_project` (el dict `params` ya lo lleva) | `app.py` | B8, F2 | `/api/generar` sin la clave nueva se comporta exactamente igual que hoy |
| F4 | Parseo opcional de `referencias_especificacion` en la respuesta de Claude (contrato §9) — aditivo, `.get()` con default, nunca rompe si falta | `analyzer/ai_generator.py` | F2 | Un JSON de respuesta sin ese campo se parsea igual que hoy |
| F5 | `verificar_directivas_duras(units, directivas)` — reutiliza `evaluator.evaluate_bathroom_accessibility` / `evaluate_accessible_bathroom_area`, determinista, sin llamar a Claude | `analyzer/ai_generator.py` | D4 | Test con una unidad sin baño accesible detecta el incumplimiento; con una que sí lo tiene, no |
| F6 | **Disparo de reintento por accesibilidad incumplida**: extiende la condición de reintento ya existente en `generate_project()` (hoy solo geométrica, >50% de viviendas) para incluir directivas duras verificables incumplidas; **si el reintento también falla, se conserva el resultado con advertencia explícita en `advertencias` [Decisión Pablo #1]** | `analyzer/ai_generator.py` | F5 | Test: incumplimiento en la 1ª pasada + cumplimiento en la 2ª → sin advertencia; incumplimiento en ambas → resultado conservado + advertencia explícita, nunca un error 5xx |
| F7 | Construir y persistir `TrazaDeGeneracion` tras cada generación — **desde la primera implementación [Decisión Pablo #2]**, usando A6-A7 | `app.py` (en `generar()`) | A6-A7, F4-F6 | Toda generación con `contexto_cualitativo` deja una fila recuperable en `traza_generacion` |
| F8 | Tests de integración del generador extendido — con y sin `contexto_cualitativo`, verificando compatibilidad hacia atrás byte a byte cuando no hay contexto | `tests/test_ai_generator_contexto.py` (nuevo) | F1-F7 | Incluye explícitamente el caso "mismo `params` de siempre, sin la clave nueva → misma salida que antes de esta fase" |

---

## FASE G — Pruebas

No es "tests genéricos": son los escenarios pedidos explícitamente, cada uno con su nivel (unitario/integración/
navegador) y qué fases debe tener terminadas para poder ejecutarse.

| # | Escenario | Nivel | Requiere (fases) | Qué verifica |
|---|---|---|---|---|
| G1 | Usuario que sabe exactamente lo que quiere | Integración | A-D, F | Turnos y llamadas mínimas (dentro del objetivo 3-5, PRD v2 §21) |
| G2 | Usuario que no sabe nada ("no sé"/"decide tú" en todo) | Integración | A-D | Termina igual, todo marcado `Hipótesis`, nunca bloqueado |
| G3 | Respuestas contradictorias | Integración | C6, C8 | Se presenta el conflicto explícitamente, nunca se sobrescribe en silencio |
| G4 | Información incompleta al forzar cierre | Integración | C5, C11, D6 | `decisiones_pendientes` no vacío, `finalizar()` no falla |
| G5 | Accesibilidad dura incumplida | Integración | F5-F6 | Dispara reintento; si persiste, advertencia explícita, resultado conservado **[Decisión Pablo #1]** |
| G6 | Preferencias blandas (privacidad, carácter) | Integración | D4, F2 | Aparecen en el prompt como "intenta", nunca como "DEBES"; Claude libre de interpretarlas |
| G7 | Modo experto | Integración | B7, D7, E7 | Especificación válida sin ningún turno conversacional; mismas validaciones que la guiada |
| G8 | Abandono/reanudación | Integración + navegador | B4, E9 | Estado recuperado íntegro tras cerrar y reabrir |
| G9 | Límite de llamadas IA alcanzado | Integración | C5, C9 | Con Claude mockeado devolviendo baja confianza repetidamente, el motor cierra en opción cerrada al llegar a 5 |
| G10 | **Generación sin entrevista, para comprobar compatibilidad** | Integración | F3, F8 | Un request idéntico al `/api/generar` de hoy (formulario técnico, sin `contexto_cualitativo`) produce una salida idéntica byte a byte a la de antes de esta etapa |
| G11 | Suite de navegador de los flujos E1-E9 | Navegador | E1-E9 | Cubre como mínimo G1, G2, G7 y G8 sobre navegador real, no solo mockeado |

**Nota:** G10 es la prueba de mayor prioridad de toda la fase — es la que demuestra que nada de lo construido
en A-F rompió lo que ya funcionaba. Debe poder ejecutarse (y pasar) incluso antes de que la Fase E exista.

---

## FASE H — Auditoría (gate de cierre, no tareas de construcción)

No son tareas de ≤2h de código — es la lista de comprobación antes de dar por cerrada la etapa, mismo patrón
que la Fase 6 de `PRD-001` (checkpoint de decisión, no de construcción).

1. **`git status` limpio** antes de empezar y diff completo revisado al terminar — ningún archivo fuera de
   `analyzer/interview/*`, `analyzer/ai_generator.py` (solo F1-F7), `analyzer/storage.py` (solo A5-A7),
   `app.py` (solo B1-B8, F3, F7), `static/entrevista.js`, `tests/*` debería aparecer en el diff.
2. **Suite completa del repositorio en verde** — no solo los tests nuevos: correr toda la suite existente
   (`pytest`) para confirmar que nada de lo tocado en `ai_generator.py`/`storage.py`/`app.py` rompió una regla
   ya probada.
3. **Pruebas de navegador** de G11 ejecutadas, no solo escritas.
4. **Comprobación de llamadas reales a Claude**: ejecutar G1 y G7 contra la API real (no mockeada) al menos
   una vez cada uno, contar llamadas reales, confirmar que quedan dentro de 3-5 **[Decisión Pablo #4]** y que
   no aparece ninguna llamada de auditoría adicional **[Decisión Pablo #5]**.
5. **Comprobación de persistencia**: reiniciar el proceso del servidor a mitad de una entrevista real y
   confirmar recuperación íntegra (G8 contra el servidor real, no en memoria de test).
6. **Comprobación de trazabilidad**: para un proyecto generado con al menos una directiva dura y una blanda,
   reconstruir manualmente la cadena respuesta → interpretación → requisito → directiva → verificación
   (accesibilidad) usando solo lo persistido en `entrevistas` y `traza_generacion` — sin mirar logs ni memoria
   del proceso.
7. **Informe de resultados** — documento corto (`docs/design/2026-08-12-entrevistador-resultados.md` o
   similar, análogo a la Fase 6 de `PRD-001`), con las métricas del PRD v2 §19 medidas de verdad, no
   estimadas, y un punto de decisión explícito con Pablo antes de sustituir `renderGenerarForm` en producción.

---

## Resumen de dependencias entre fases

```
A (modelo)
 ├──► B (API)         — B2-B7 son wrappers sobre C y D; B8 es independiente, solo toca app.py/ai_generator
 ├──► C (motor)        — depende solo de A; se construye y prueba sin Flask
 │      └──► D (compilador) — depende de A y C
 │             ├──► E (UI)  — depende de B (que a su vez depende de C y D)
 │             └──► F (generador) — depende de D, NO de E ni de B más allá de B8/F3
 │                    (F puede implementarse en paralelo con E una vez D está lista)
 └──► G (pruebas) — G1-G10 requieren A-D y F; G11 requiere además E
                     G10 es la excepción: solo requiere F3+F8, se puede correr en cuanto F termine
H (auditoría) — estrictamente al final, gate de cierre, no antes de que G esté completa
```

**El hallazgo de dependencias que más cambia el orden intuitivo:** la Fase F (integración con el generador) no
depende de la Fase E (UI) — depende de D. Esto significa que se puede validar todo el contrato con el generador
real (incluida la Decisión Pablo #1 de reintento por accesibilidad) **antes** de que exista una sola pantalla
de interfaz, llamando al compilador y a `generate_project()` directamente desde tests de integración. Vale la
pena aprovechar esto: reduce el riesgo de descubrir un problema de integración tarde, cuando ya hay UI
construida encima.

---

## Riesgos de este plan de implementación

- **Fase A es la única con cambios de esquema de base de datos** — un error de diseño aquí (p. ej. un campo que
  falta en `EspecificacionArquitectonica`) se paga reescribiendo migraciones en producción más adelante, no solo
  código. Mitigación: A8 (tests de round-trip) antes de que ninguna otra fase dependa de A.
- **C7-C9 son las únicas tareas de la Fase C que llaman a Claude de verdad** — todo el resto del motor se puede
  y debe probarse mockeado; si se mezclan, los tests dejan de ser deterministas y el CI se vuelve intermitente.
- **F6 (reintento por accesibilidad) reutiliza el mecanismo de reintento existente de `generate_project()`** —
  riesgo real de que extender su condición de disparo introduzca un efecto secundario en el caso ya existente
  (reintento por >50% de fallos geométricos). Mitigación: F8 debe incluir explícitamente un test del caso
  antiguo (solo fallo geométrico, sin directivas duras) para confirmar que sigue disparando igual que hoy.
- **B8/F3 son el único punto de la Fase B/F donde `/api/generar` cambia de comportamiento posible** — todo el
  resto de riesgo de compatibilidad se concentra ahí; por eso G10 se marca como la prueba de mayor prioridad.
- **El catálogo cerrado de directivas (Decisión Pablo #3) depende de disciplina, no solo de código** — A3/D4
  lo hacen imposible de saltarse por accidente (error explícito), pero alguien puede decidir "añadir una sexta
  categoría rápido" sin pasar por la decisión explícita que Pablo exigió; no hay control de proceso que este
  plan pueda imponer más allá de que el propio código falle si no se declara.
- **El almacenamiento de `TrazaDeGeneracion` desde el primer commit (Decisión Pablo #2) añade una escritura más
  por generación** — coste de almacenamiento no medido todavía; aceptable dado que es un blob JSON pequeño
  (mismo orden de magnitud que `modelo`), pero vale la pena vigilarlo si el volumen de proyectos generados
  crece mucho.
- **Nueve archivos nuevos y tres modificados** es una superficie de cambio considerable para una sola etapa —
  el orden de fases de este plan existe precisamente para poder detenerse tras cualquier fase completa (A, o
  A+B+C, etc.) con algo funcionalmente probado, no solo al final.

---

## Recomendación de por dónde empezar

**Fase A.** Es la única sin dependencias, no llama a Claude, no toca Flask, no toca `ai_generator.py`, y todo
lo que construyen B, C, D, E y F se apoya directamente en sus estructuras de datos. Un error de diseño aquí es
barato de corregir ahora (nada depende todavía de ella) y carísimo de corregir después (todo dependerá).
Segunda recomendación, una vez A esté cerrada y probada (A8 en verde): **C antes que B** — el motor de
entrevista es determinista, se prueba solo, y valida las decisiones de diseño más discutibles del PRD (cola de
priorización, límites, criterio de parada) antes de invertir en los endpoints que lo envuelven.
