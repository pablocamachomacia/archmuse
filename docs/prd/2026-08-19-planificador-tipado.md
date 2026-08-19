# PRD — Planificador tipado: una llamada, un DAG validado (tarea `AG-1`)

**Estado:** APROBADO · **Fecha:** 2026-08-19 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo, 2026-08-19

> **Condición de la aprobación (textual):** mantenerlo **deliberadamente pequeño**. No crear un framework de agentes ni introducir LangGraph u otro orquestador. Produce un DAG y nada más: no reintenta, no ejecuta, no observa. Cualquier añadido que se parezca a un framework se rechaza en revisión.

**Tarea del backlog:** `AG-1`. Bloquea `AG-2`, `AG-4`, `AG-5`, `AG-8`. Dependencias ya cerradas: `TL-3` (un manifiesto, tres consumidores) y `ME-5` (resumen tipado del grafo), ambas HECHO el 2026-08-19.

---

## 1. Problema que resuelve

Hoy `agente/nucleo.py::ejecutar` funciona así: se le da la intención al modelo con las herramientas, el modelo pide una, se ejecuta, se le devuelve el resultado, y se repite hasta que deja de pedir. Es el bucle clásico de uso de herramientas, y **funciona** — está probado con cliente guionizado y ejecuta las tres Skills reales.

Tiene tres defectos, y los tres son de producto, no de ingeniería:

1. **No se puede enseñar.** Un bucle no tiene forma hasta que ha terminado. El arquitecto no puede ver qué va a hacer ArchMuse antes de que lo haga, y por tanto **no puede pararlo**. Es lo contrario de la relación que este producto quiere tener con él.
2. **No se puede presupuestar.** Sin plan completo por adelantado no hay forma de sumar el coste antes de gastarlo (`AG-3`) ni de rechazar lo que no cabe. Se descubre el gasto cuando ya está hecho.
3. **No se cachea.** Cada iteración manda de nuevo todo el prefijo. `ME-5` acaba de construir el prefijo estable justo para esto, y sin planificador no lo usa nadie.

Y hay un cuarto, más callado: **el ejecutor ya espera un `Plan`**. `agente/ejecucion.py` está escrito alrededor de un DAG tipado con reanudación por checkpoint. Hoy ese `Plan` lo construye el bucle paso a paso, de uno en uno, así que la mitad de las garantías del ejecutor —validar antes de ejecutar, detectar ciclos, ordenar dependencias— no se ejercen nunca. La pieza que falta no es el ejecutor: es **quien produzca el plan de una sola vez**.

## 2. Usuario afectado

El arquitecto, en el momento exacto en que escribe qué quiere y todavía no ha pasado nada. Es el único momento en que puede corregir el rumbo sin haber pagado.

Secundariamente, ArchMuse: sin plan explícito no hay forma de razonar sobre coste, paralelismo ni reproducibilidad, y esas tres cosas son `AG-3`, `AG-8` y el sello de `ME-2`.

## 3. Objetivo de negocio

- **Convertir lo construido en algo pedible en una frase.** Hoy `agente/` tiene 3.495 líneas que funcionan y no están enchufadas a ningún producto. El planificador es la pieza que hace que «rellena el cuadro de este DXF» se traduzca sola en trabajo.
- **Hacer visible el trabajo antes de hacerlo,** que es la mitad de la propuesta de valor: la otra mitad es el acta, que explica lo hecho *después*.
- **Bajar el coste por ejecución** con caché de prefijo, que es lo que decide si el precio de `INF-9` se sostiene.

## 4. Objetivo técnico

- Una **sola** llamada al modelo, con `tool_choice` forzado sobre una herramienta de esquema fijo, produce un objeto `Plan` validado.
- El plan es un **DAG**: pasos con `id`, `capacidad_id` o `skill`, `argumentos`, `depende_de`. Nada más. El planificador **no ejecuta nada** y no ve resultados.
- El prompt se compone como `prefijo_cacheable(...)` (estable, de `ME-5`) + estado del proyecto (variable) + intención. En esa orden, y sin mezclar.
- La misma intención sobre el mismo grafo produce un plan **equivalente** dos veces seguidas, y la segunda acierta caché (`cache_read_input_tokens > 0`).
- Un plan inválido —capacidad inexistente, versión inexistente, ciclo, argumento no declarado— se rechaza **sin ejecutar nada**. (La validación completa es `AG-2`; aquí basta con que el plan sea sintácticamente un DAG tipado y que sus capacidades existan.)
- El planificador es indiferente al transporte: se invoca igual desde la web, desde el CLI (`agente/invocar.py`) o desde un plugin. C1 sigue vigente.

## 5. Casos de uso

**CU-1 · Intención simple.** «¿Qué normativa aplica a una parcela en Madrid?» → plan de un paso: `territorial.ficha_normativa_de_parcela`.

**CU-2 · Intención compuesta.** «Comprueba la parcela y si el recorrido de evacuación cabe en norma» → plan de dos pasos, el segundo dependiendo del primero. Es el plan que hoy construye a mano `scripts/demo_agente.py`.

**CU-3 · Intención con ramas independientes.** «Lee este DXF y dime la superficie útil y qué normativa aplica» → dos ramas sin dependencia entre sí. El plan lo refleja, y `AG-8` podrá ejecutarlas en paralelo sin cambiar nada aquí.

**CU-4 · Intención imposible.** «Calcula la estructura del forjado» → ArchMuse no tiene esa capacidad. El plan sale **vacío**, con el motivo, y se registra como carencia (`agente/carencias.py`, ya existente). No se inventa un plan aproximado con las capacidades que sí hay: eso es lo que produce respuestas plausibles y falsas.

**CU-5 · Intención ambigua.** «Revisa esto» sin decir qué. El planificador devuelve plan vacío **con la pregunta**, no un plan de todo lo que sabe hacer.

## 6. Casos límite

| Caso | Comportamiento exigido |
|---|---|
| El modelo nombra una capacidad que no existe | Rechazo con el nombre y la lista de las que hay. Nunca «la más parecida» |
| El modelo nombra una versión que no existe | Rechazo. Un plan guardado tiene que poder reproducirse con la versión que usó |
| El plan tiene un ciclo | Rechazo con el ciclo dibujado |
| El plan tiene un paso que depende de un `id` inexistente | Rechazo |
| El plan está vacío | **No es un error.** Es una respuesta legítima: ArchMuse no sabe hacer eso, o falta un dato. Lleva motivo o pregunta |
| El plan tiene 40 pasos | Se rechaza por encima de un techo declarado. Un plan de 40 pasos no lo ha pedido nadie: es un modelo perdido |
| El modelo devuelve texto en vez de llamar a la herramienta | Se reintenta **una vez** con `tool_choice` forzado; si insiste, se declara fallo del planificador, no se interpreta el texto |
| El modelo mete un argumento no declarado en el manifiesto | Rechazo en la validación de `Capacidad.invocar`, ya existente |
| El grafo no tiene ningún dato | El plan puede seguir siendo válido: los pasos que necesiten datos fallarán con su pregunta al ejecutarse, que es el comportamiento correcto de las Skills |

## 7. Flujo del usuario

1. Escribe qué quiere, en una frase.
2. ArchMuse enseña **el plan**: qué va a hacer, en qué orden, con qué herramientas, qué va a costar y qué efectos tiene (escribir un fichero, gastar tokens).
3. El arquitecto lo acepta, lo corrige, o lo cancela.
4. Al ejecutar, ve el avance paso a paso (`AG-5`).
5. Al terminar, recibe el trabajo y el acta (`DOC-1`).

El paso 2 es la novedad entera. Hoy no existe.

## 8. Criterios de aceptación

1. `planificar(intencion, memoria, capacidades, skills, cliente) -> Plan` existe y hace **exactamente una** llamada al modelo en el camino feliz.
2. El `Plan` que devuelve lo acepta `Ejecutor.ejecutar` sin adaptación ninguna.
3. La misma intención sobre el mismo grafo produce dos planes equivalentes (mismos pasos, mismas dependencias) en dos ejecuciones seguidas.
4. En la segunda ejecución, `cache_read_input_tokens > 0` — medido con la telemetría de `SEG-4`, ya existente.
5. Un plan con capacidad inexistente, versión inexistente, ciclo o dependencia rota se rechaza **con cero ejecuciones** y con un mensaje que nombra la causa concreta.
6. Una intención que ArchMuse no sabe atender produce plan vacío **con motivo**, y queda registrada en `carencias`.
7. El planificador no importa transporte; el test de C1 sigue verde.
8. Los tests usan cliente guionizado: la suite **no gasta un céntimo** ni necesita clave.
9. `scripts/demo_agente.py` deja de construir su plan a mano y lo pide al planificador, con un cliente guionizado para que la demostración siga siendo gratis.

## 9. Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| El plan de una llamada sale peor que el bucle iterativo en intenciones compuestas | **Media** | Alto | `AG-4` ya prevé un ciclo de replanificación. Y se conserva el bucle actual: no se borra hasta que el planificador demuestre ser mejor sobre casos reales |
| La caché no acierta porque el prefijo cambia | Media | Medio | `ME-5` ya lo ordena y hay test; el criterio 4 lo mide de verdad |
| El modelo produce planes válidos y absurdos (pasos innecesarios que cuestan dinero) | Alta | Medio | Techo de pasos (§6) y presupuesto por plan (`AG-3`). Y el arquitecto lo ve antes de aceptar |
| Se convierte en un mini-framework de agentes hecho en casa | Media | Alto | Alcance cerrado: produce un DAG y nada más. No reintenta, no ejecuta, no observa. Lo que se parezca a LangGraph se rechaza en revisión |
| Enseñar el plan resulta ser ruido que nadie lee | Media | Medio | Es el riesgo que sólo se resuelve con usuarios. Si nadie lo lee, el plan se colapsa a una frase y se guarda el detalle para el acta |

## 10. Impacto sobre módulos existentes

- **`agente/nucleo.py`:** **no se toca.** El bucle actual sigue existiendo y sigue probado. El planificador es un camino nuevo, no una sustitución; decidir cuál manda es una decisión posterior con datos.
- **`agente/ejecucion.py`:** no cambia. Es el consumidor, y su contrato ya está escrito.
- **`agente/contexto.py`** (`ME-5`): pasa a tener su primer usuario real.
- **`agente/carencias.py`:** recibe el caso `CU-4`.
- **`ia/uso.py`:** ninguna modificación; la telemetría ya envuelve todas las llamadas.
- **`app.py`:** no se toca. La pantalla es `INF-7`.

## 11. Plan de implementación (tareas de ~1 jornada o menos)

| # | Tarea | Salida verificable |
|---|---|---|
| 1 | Esquema JSON del plan (pasos, dependencias, techo de pasos) como herramienta de esquema fijo | El esquema valida los tres planes de ejemplo de §5 y rechaza los cuatro rotos de §6 |
| 2 | `agente/planificador.py`: compone prefijo + estado + intención y hace **una** llamada con `tool_choice` forzado | Test con cliente guionizado |
| 3 | Traducción de la respuesta a `Plan`, con rechazo tipado de lo que no encaja | Los cuatro rechazos de §6, con cero ejecuciones |
| 4 | Plan vacío con motivo, y registro de carencia | Test del `CU-4` |
| 5 | Medición de caché sobre la segunda llamada | Criterio 4, con la telemetría existente |
| 6 | `scripts/demo_agente.py` pide el plan en vez de construirlo | La demostración sigue corriendo sin clave |

Estimación: **2 jornadas**, que es lo que dice el backlog.

## 12. Plan de pruebas

- **Con cliente guionizado**, como `tests/test_agente_nucleo.py`: es lo que permite probar el planificador sin gastar y sin depender de que el modelo esté de buen humor.
- **De rechazo:** los cuatro planes inválidos de §6, cada uno con su mensaje distinto, y comprobando que **no se ejecutó nada** (bitácora vacía).
- **De determinismo:** dos planificaciones seguidas con el mismo guion producen planes iguales.
- **De frontera:** el test de C1 (nada de transporte) tiene que seguir verde.
- **De integración:** el plan producido se pasa a `Ejecutor` y ejecuta las Skills reales contra el corpus real.
- **Con modelo real:** una sola prueba, marcada como lenta y detrás de la variable que ya existe para eso, que comprueba el criterio 4 (caché) con una llamada de verdad. Es la única forma de medirlo, y por eso está aislada.

## 13. Métricas de éxito

1. **Tasa de aciertos de caché** en la segunda llamada. Si es baja, el prefijo se está moviendo y hay que arreglarlo antes de seguir.
2. **Coste medio por plan** (`SEG-4`). Es la cifra que decide el modelo de cada perfil en `AG-3`.
3. **Proporción de planes que el arquitecto acepta sin cambiar.** Baja = el planificador no entiende lo que le piden; muy alta y con poco uso = nadie lo lee.
4. **Carencias registradas por semana.** Es la lista de qué falta, medida por uso real y no por intuición — la entrada de `AG-7`.

## 14. Motivos para NO implementar esto

1. **El bucle actual ya funciona.** Ninguna de las tres Skills existentes necesita un planificador para ejecutarse. Todo lo que aporta esta tarea es *visibilidad y control por adelantado*, no capacidad nueva. Si el objetivo del trimestre fuera cerrar el primer entregable cuanto antes, esta tarea se podría aplazar entera detrás de `TL-2` y `SK-1` sin bloquear `OP-1`.
2. **Es la tarea con más riesgo de convertirse en un framework.** El repositorio ya decidió no usar LangGraph (auditoría §5); construir uno propio poco a poco sería la misma decisión tomada sin darse cuenta. Este PRD acota el alcance a «produce un DAG y nada más» precisamente porque ese riesgo es real.
3. **El corpus sigue vacío.** Un planificador impecable planificando sobre un corpus con una regla es una demostración muy buena de algo que todavía no se puede vender. Mismo argumento que gobierna todo el backlog: si `NOR-1` dejara de avanzar en paralelo, esto se aplaza.
4. **Alternativa más barata, descartada:** enseñar el plan *reconstruido* del bucle actual —dejar que itere y mostrar lo que va haciendo. Cuesta mucho menos y da el 60 % del valor de §3. Se descarta porque no permite parar antes de gastar ni presupuestar, que son las dos razones principales; pero si Pablo prefiere ese camino, es una decisión defendible y **más rápida**.

---

**Decisión pendiente de Pablo.** No se toca código de producto hasta que este PRD esté aprobado. Si se aprueba, conviene decidir a la vez si el bucle de `nucleo.py` se conserva indefinidamente o se le pone fecha.
