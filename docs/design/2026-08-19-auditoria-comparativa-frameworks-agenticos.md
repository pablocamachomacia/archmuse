# Auditoría comparativa: `agente/` contra Deep Agents, PydanticAI, LangGraph y Agno

**Fecha:** 2026-08-19 · **Estado:** auditoría, no propuesta aprobada · **Encargo de Pablo:** comparar el código **real** de ArchMuse contra los cuatro, no la idea que tenemos de él.

**Qué se ha leído para escribir esto.** Los 19 módulos de `agente/` (5.082 líneas), sus 12 ficheros de prueba (4.025 líneas), `ia/cliente.py`, `ia/modelos.py`, `ia/uso.py`, `requirements.txt` y el árbol de dependencias real. Las 9 capacidades y las 4 Skills declaradas hoy. Ninguna cifra de este documento viene de un documento anterior: todas se han contado sobre el código.

**Lo que este documento NO reabre.** La auditoría del 2026-08-18 (§5) y la revisión de stack (§7) ya rechazaron LangGraph y el SDK de agentes de OpenAI, dos veces, con argumentos que siguen en pie. Este documento no repite ese debate: lo somete a dos frameworks que aquellos documentos **no** evaluaron (Deep Agents y Agno), a uno que sólo se mencionó de pasada (PydanticAI, bajo D-3), y —lo importante— al código que existe hoy y que entonces no existía.

---

## 0. El veredicto, antes del porqué

| Framework | Veredicto | En una línea |
|---|---|---|
| **LangGraph** | **Rechazar** (tercera vez), con el criterio de reapertura **corregido** | Su modelo de estado sigue chocando con `modelo/`; pero el criterio de reapertura que escribimos está mal medido y hay que arreglarlo |
| **PydanticAI** | **Adoptar una capa, rechazar el resto** | Sólo el esquema de argumentos. Invierte `comprobar_coherencia` de test a imposibilidad. Su `Agent` es el mismo error que LangGraph |
| **Deep Agents** | **Rechazar, y robarle dos ideas** | Es LangGraph + un prompt + un `todo`. Nuestra Skill es más fuerte. Su gestión de contexto largo, no |
| **Agno** | **Rechazar**, y es el más fácil de los cuatro | Optimiza un problema de escala que no tenemos y trae RAG vectorial de serie, que es justo lo que este producto no puede tener |

**Y el hallazgo que no es sobre frameworks** (§7): la mejor pieza construida —el planificador tipado y su revisión previa— **no está conectada a nada que un usuario pueda alcanzar**, y `agente/` entero no aparece ni una vez en `app.py`. Eso cuesta hoy más que cualquiera de las cuatro decisiones de arriba.

---

## 1. Qué hay realmente construido

Conviene fijarlo con números antes de compararlo, porque la comparación honesta depende de no exagerar en ninguna dirección.

| Pieza | Fichero | Líneas | Qué hace de verdad |
|---|---|---:|---|
| Bucle con el modelo | `nucleo.py` | 461 | Turno a turno con `tool_use`; aísla los tres modos de fallo de una capacidad; deriva limitaciones |
| Plan y ejecutor | `ejecucion.py` | 469 | DAG, orden topológico determinista, checkpoints en JSONL append-only, reanudación, aislamiento de fallos |
| Skill | `skill.py` | 468 | Procedimiento declarado: `requiere`/`capacidades`/`produce`/`efectos`/`verificaciones`, con `Contexto` que las hace cumplir |
| Planificador tipado | `planificador.py` | 444 | Una llamada, `tool_choice` forzado, plan validado; más `revisar()`, que dice todo lo que se puede saber sin gastar un token |
| Memoria de proyecto | `memoria.py` | 348 | Append-only, conflictos declarados y no resueltos, `KNOWN`/`ESTIMATED` como puerta |
| Manifiesto → 3 consumidores | `manifiesto.py` | 334 | Herramienta de Anthropic + operación OpenAPI + firma Python, y `comprobar_coherencia` contra la función real |
| Acta de procedencia | `acta.py` | 253 | Sellada, con versiones fijadas y «no comprobado» **derivado** |
| Registros por descubrimiento | `registro.py` | 242 | Sin import manual; resolución `id@version` que **se niega** ante una mayor distinta |
| Compatibilidad de contrato | `compatibilidad.py` | 230 | Política semver escrita, huella del contrato, y CI en rojo si el contrato cambia sin subir versión |
| Verificación | `verificacion.py` | 330 | Deterministas, tres estados (pasa / falla / **no se ha podido comprobar**), genéricas irrenunciables |
| Efectos y autorización | `efectos.py` | 196 | Catálogo cerrado de 6, portero fail-closed, alcance puntual obligatorio para lo irreversible |
| Afirmación | `afirmacion.py` | 227 | Naturaleza epistémica por valor: hecho / cálculo / inferencia / propuesta |
| Respaldo numérico | `respaldo.py` | 73 | Cada cifra de la prosa final tiene que aparecer en algún resultado real |
| Contexto acotado | `contexto.py` | 194 | Acota por **estructura**, no truncando; prefijo cacheable ordenado |
| Fachada / CLI / carencias | `copiloto.py`, `invocar.py`, `carencias.py` | 128 / 198 / 228 | Una puerta; invocable sin web; se anota lo que no se supo hacer |

Catálogo vivo: **9 capacidades, 4 Skills.** Pruebas: **4.025 líneas** repartidas en 12 ficheros, incluyendo goldens congelados para las capacidades deterministas y un contrato de compatibilidad congelado en `tests/fixtures/contratos_de_capacidad.json`.

Es un orquestador propio pequeño con una capa de gobierno grande. Esa proporción es la que decide todo lo que sigue.

---

## 2. Los cuatro, descritos sin folleto

**LangGraph.** Runtime de grafo con estado. Su aportación real es la persistencia: checkpointer por *superstep*, `interrupt()` que congela la ejecución y la reanuda desde el checkpoint, ejecución paralela de nodos independientes dentro de un superstep, y *time travel* sobre el historial de checkpoints. Todo lo demás es andamiaje. Su requisito duro: el estado del grafo es **su** estado, con su forma y su ciclo de vida.

**Deep Agents.** Librería de LangChain construida **sobre** LangGraph. Cuatro piezas: una herramienta de planificación (`todo`), un sistema de ficheros virtual con backends intercambiables (memoria, disco, store, con reglas de permiso de lectura/escritura), subagentes con contexto aislado, y un prompt de sistema largo. Su versión 0.2 añadió lo que realmente importa aquí: **desalojo de resultados de herramienta grandes, resumen del historial de conversación, y reparación de llamadas a herramienta colgadas**. Adoptarlo es adoptar LangGraph.

**PydanticAI.** Framework de agentes de Pydantic Services, ~17k estrellas, versión 2.0 en junio de 2026. Su primitiva no es el grafo: es el **tipo**. `Agent` con dependencias tipadas y `output_type` como modelo Pydantic; herramientas cuyo esquema se **deriva de la firma Python**; `ModelRetry`, que devuelve el error de validación al modelo para que se corrija; abstracción de proveedor; toolsets; MCP; herramientas diferidas para *human-in-the-loop*; ejecución durable de primera parte sobre Temporal, DBOS o Prefect; y `pydantic-evals` para medir comportamiento.

**Agno.** Antes Phidata. Framework Python de agentes multi-agente con memoria, conocimiento (RAG agéntico sobre vectores), sesiones, equipos y flujos, más **AgentOS**, un runtime FastAPI preconstruido. Su argumento central es rendimiento: instanciación en ~2 µs y 3,75 KiB por agente, miles de sesiones concurrentes en hardware modesto.

---

## 3. La matriz

`✔` lo da; `~` lo da a medias o hay que construirlo encima; `✘` no lo da; `✔✔` es su punto fuerte.

| Propiedad | ArchMuse hoy | LangGraph | Deep Agents | PydanticAI | Agno |
|---|:---:|:---:|:---:|:---:|:---:|
| Bucle con herramientas | ✔ | ✔ | ✔ | ✔ | ✔ |
| Plan tipado inspeccionable **antes** de ejecutar | ✔✔ | ~ | ~ | ~ | ~ |
| DAG con orden determinista | ✔ | ✔ | ~ | ~ | ~ |
| **Ejecución paralela de pasos independientes** | ✘ | ✔✔ | ✔ | ✔ | ✔ |
| Checkpoints y reanudación | ✔ | ✔✔ | ✔ | ✔ | ✔ |
| Pausa/reanudación *cross-process* a mitad de paso | ✘ | ✔✔ | ✔ | ✔ | ~ |
| **Async y streaming** | ✘ | ✔ | ✔ | ✔✔ | ✔✔ |
| **Gestión de contexto largo** (desalojo, resumen) | ✘ | ~ | ✔✔ | ~ | ✔ |
| Subagentes con contexto aislado | ✘ | ✔ | ✔✔ | ~ | ✔✔ |
| **Validación completa del esquema de argumentos** | ✘ | ~ | ~ | ✔✔ | ✔ |
| Reintento estructurado ante salida inválida | ~ | ~ | ~ | ✔✔ | ✔ |
| Esquema **derivado** de la función (no escrito aparte) | ✘ | ~ | ~ | ✔✔ | ✔ |
| Independencia de proveedor de modelo | ✘ | ✔ | ✔ | ✔✔ | ✔✔ |
| Trazas / observabilidad operativa | ✘ | ✔ | ✔ | ✔✔ | ✔✔ |
| Evaluación medida del comportamiento del modelo | ✘ | ~ | ~ | ✔✔ | ~ |
| Presupuesto por ejecución y replanificación | ✘ | ~ | ~ | ~ | ~ |
| **Catálogo cerrado de efectos + portero fail-closed** | ✔✔ | ✘ | ~ | ✘ | ✘ |
| **Alcance puntual obligatorio para lo irreversible** | ✔✔ | ✘ | ✘ | ✘ | ✘ |
| **Compatibilidad de contrato vigilada por CI** | ✔✔ | ✘ | ✘ | ✘ | ✘ |
| **Naturaleza epistémica por valor** | ✔✔ | ✘ | ✘ | ✘ | ✘ |
| **Acta de procedencia sellada con versiones** | ✔✔ | ✘ | ✘ | ✘ | ✘ |
| **Requisito insatisfecho → la pregunta, sin gastar** | ✔✔ | ✘ | ✘ | ✘ | ✘ |
| **Verificación con tercer estado («no se pudo»)** | ✔✔ | ✘ | ✘ | ✘ | ✘ |
| **Comprobación de respaldo numérico de la prosa** | ✔✔ | ✘ | ✘ | ✘ | ✘ |
| Memoria append-only con conflictos declarados | ✔✔ | ~ | ~ | ~ | ~ |
| Runtime de producción listo (API, UI, escalado) | ✘ | ~ | ~ | ~ | ✔✔ |

Léase la matriz por su forma, no fila a fila: **hay una franja abajo donde ArchMuse está solo y una franja arriba donde ArchMuse es el único que no llega.** Las dos son reales y ninguna anula a la otra.

---

## 4. Lo que ArchMuse tiene y ninguno de los cuatro da

Estas siete propiedades no aparecen en ningún framework de los evaluados, ni como opción. Escribirlas encima de cualquiera de ellos costaría exactamente lo que ha costado escribirlas aquí.

1. **El catálogo cerrado de efectos con portero en dos capas** (`efectos.py`, y `Capacidad.invocar` además de `Skill.ejecutar`). Deep Agents es el que más se acerca: su sistema de ficheros virtual admite reglas de permiso de lectura/escritura por ruta. Pero eso es una regla sobre ficheros, no un vocabulario que una pantalla pueda enseñarle a un arquitecto —«consultar el Catastro», «modificar un fichero aportado por el cliente»— antes de tocar nada. Y ninguno de los cuatro tiene la regla que aquí es la buena: **un efecto irreversible sólo admite alcance `ejecucion`**, obligado por el constructor. LangGraph da `interrupt()`, que es un mecanismo; esto es una política.

2. **La marca `INTENTADO` escrita *antes* de un efecto irreversible.** Es el mecanismo más fino del repositorio y ningún framework lo hace: si el proceso muere a mitad, en la bitácora sobrevive la marca pero no el resultado, y la reanudación exige volver a autorizar. LangGraph advierte de que «el código anterior a `interrupt()` tiene que ser idempotente» y ahí acaba su ayuda: te avisa del problema, no lo resuelve.

3. **`compatibilidad.py` entero.** Política semver escrita por *a quién rompe* —añadir un efecto es MAYOR, añadir una limitación es MENOR—, huella del contrato, y un test que compara con el contrato congelado y pone CI en rojo diciendo qué tramo tocaba subir. **Ninguno de los cuatro tiene nada parecido, ni de lejos.** Es lo que hará que un complemento de Revit instalado en un estudio siga funcionando el martes siguiente.

4. **La naturaleza epistémica por valor** (`afirmacion.py`: hecho / cálculo / inferencia / propuesta, más `KNOWN`/`ESTIMATED`/`UNKNOWN`, más origen, fuente e hipótesis). Los cuatro frameworks tratan un valor como un valor. Aquí es la frontera entre asesorar y firmar.

5. **El acta de procedencia sellada.** No es telemetría: viaja con el entregable, fija `skill@version` y `capacidad@version`, y su lista de «no comprobado» se **deriva** de lo que se ejecutó. LangSmith, Logfire y AgentOS dan trazas para el que opera el sistema. Ninguno da un documento para el que firma el proyecto.

6. **«Requisito insatisfecho → la pregunta concreta, sin gastar un token ni tocar un fichero.»** En los cuatro frameworks, averiguar que falta el municipio cuesta al menos una llamada al modelo y probablemente una llamada a herramienta. Aquí es una consulta a un `dict`. Con un catálogo de 40 Skills eso deja de ser una elegancia y pasa a ser una diferencia de coste.

7. **`respaldo.py` y el tercer estado de `verificacion.py`.** El primero convierte «se lo ha inventado» en algo que sale en un test. El segundo impide que ArchMuse acuse al plano de un arquitecto de un defecto que no llegó a mirar. Los dos son producto, no ingeniería, y por eso ningún framework genérico los tendrá nunca.

**La conclusión de esta sección, dicha sin adornos:** adoptar cualquiera de los cuatro no ahorraría **ninguna** de estas siete. Habría que escribirlas igual, encima de un modelo de ejecución ajeno. Ése sigue siendo el argumento, y el código de hoy lo respalda mejor de lo que lo respaldaba el documento de ayer.

---

## 5. Lo que ArchMuse no tiene y los cuatro sí

Esta sección es la que justifica la auditoría. Ordenada por daño real, no por dificultad.

### 5.1 No hay ejecución paralela, y el prompt del planificador promete que la hay

`planificador.py` le dice al modelo, regla 5: *«Los pasos independientes se declaran independientes: es lo que permite ejecutarlos a la vez»*. `Plan.orden()` calcula el orden topológico y lo aplana a una tupla. Y `Ejecutor.ejecutar` es un `for paso in plan.orden():` estrictamente secuencial.

Es decir: **le pedimos al modelo un dato que no usamos, y se lo justificamos con una razón falsa.** No es un bug funcional —el resultado es correcto— pero es una promesa incumplida dentro del propio prompt, y es la única mentira que le contamos al modelo en todo el repositorio.

LangGraph ejecuta los nodos independientes de un superstep en paralelo. Deep Agents lanza subagentes en paralelo. Agno y PydanticAI lo dan por async. Aquí `Plan.orden()` **ya calcula las capas**: el bucle `while pendientes` genera exactamente el conjunto `listos` de cada nivel, y luego lo desperdicia aplanándolo.

**Coste de arreglarlo:** exponer `Plan.capas()` junto a `Plan.orden()` y ejecutar cada capa con un `ThreadPoolExecutor` — las capacidades son E/S y CPU de `shapely`/`ezdxf`, no hay GIL que estorbe de forma decisiva. La bitácora ya tiene su cerrojo. **Media jornada, y no necesita ningún framework.**

### 5.2 No hay gestión de contexto largo, y el primer plano grande lo va a demostrar

`nucleo.ejecutar` añade **cada resultado de herramienta íntegro** a `mensajes`, serializado a JSON, y vuelve a enviarlo entero en cada iteración. Con 6 iteraciones y `plano.leer_dxf` o `bim.inventario_de_ifc` de por medio, un plano real de cliente llena la ventana antes de terminar el trabajo. No hay desalojo, no hay resumen, no hay descarga a fichero, no hay handles.

Deep Agents 0.2 existe casi enteramente para esto: desalojo de resultados grandes, resumen del historial, y un sistema de ficheros virtual que precisamente sirve para que un resultado grande **no viva en la conversación**.

Esto es lo mejor que hay para robar de los cuatro. No hay que adoptar Deep Agents: hay que adoptar su idea. Un resultado por encima de un umbral se escribe en la bitácora —que ya existe, ya es append-only y ya está sellada— y al modelo le vuelve un resumen estructurado más un identificador que puede reabrir con una capacidad nueva, `bitacora.leer_resultado`. Encaja con la arquitectura que ya hay en vez de pelearse con ella, y de paso hace que un resultado grande quede en el acta en lugar de evaporarse con la conversación. **Una jornada.**

### 5.3 La validación de argumentos es superficial — y `jsonschema` ya está instalado

`Capacidad.invocar` comprueba dos cosas: que no sobre ninguna clave y que estén las obligatorias. **Ni tipos, ni `enum`, ni rangos, ni objetos anidados, ni `additionalProperties`.** Un modelo que pase `{"municipio": 42}` o `{"uso": "resdiencial"}` atraviesa el portero y llega a la función.

Esto contradice frontalmente lo que el módulo dice de sí mismo. El docstring de `ResultadoInvalido` argumenta que un resultado no estructurado «volvería al modelo como prosa y ahí ya no se distingue un dato medido de una frase plausible». La misma exigencia en la dirección contraria —lo que entra— no se aplica. Y `comprobar_coherencia` verifica que los **nombres** del esquema, los tres consumidores y la función real coinciden, pero nunca comprueba los **tipos**: puede declararse `{"type": "string"}` sobre un parámetro que la función usa como `float` y los 253 líneas de `test_agente_manifiesto.py` pasan.

Lo agravante: `jsonschema==4.26.0` es **dependencia directa** de este repositorio y `normativa/validacion.py` ya lo usa con `Draft202012Validator`. Es decir, la validación superficial no es una decisión de evitar dependencias —no habría ninguna que evitar—, es un hueco.

**Coste de arreglarlo:** unas 15 líneas en `Capacidad.invocar`, más el traspaso del error a `ArgumentosInvalidos`, que ya existe y ya se convierte en `ok: false` con motivo. **Dos horas, cero dependencias nuevas.**

Esto no elimina el argumento de PydanticAI, pero lo reduce a su mitad buena: ver §6.2.

### 5.4 Todo es síncrono y no hay streaming

Ni un `async def`, ni un `ThreadPoolExecutor`, ni un `stream=True` en `agente/` ni en `ia/`. Un trabajo de varios minutos —«prepárame la memoria justificativa»— no tiene forma de mostrar progreso, y el timeout real de una llamada colgada es `timeout × 3` (6 minutos en el tramo estándar) con el hilo retenido.

Los cuatro frameworks son async-first. Aquí la decisión de fondo ya está tomada por la revisión de stack (§2: cola en Postgres con `SKIP LOCKED` + checkpoints por paso), y el streaming es de la capa de transporte, no del motor. Pero conviene registrar que **hoy no existe ninguno de los dos** y que la cola tampoco está construida, así que la propiedad «ArchMuse trabaja durante minutos» no es cierta todavía por ninguna vía.

### 5.5 No hay presupuesto por ejecución ni replanificación

`MAX_ITERACIONES = 6` es un freno contra el bucle infinito, y su propio docstring lo dice. `ia/uso.py` tiene un tope, pero global y del proceso, no por ejecución ni por proyecto ni por cliente. Un plan de 12 pasos con Skills que gastan tokens no tiene techo propio.

Ninguno de los cuatro lo resuelve bien tampoco (`~` en toda la fila de la matriz), así que esto no es un argumento a favor de adoptar nada. Es una tarea pendiente, ya identificada como `AG-4`.

### 5.6 No hay medición del comportamiento del modelo

Hay goldens deterministas —`G11_capacidades.json`, 7 casos, comparando el resultado entero— y están bien. Lo que no hay es ninguna medida de **si el planificador elige la Skill correcta**. Con 4 Skills en el catálogo, elegir mal es raro y se detecta a ojo. Con 40, elegir mal pasa a ser el modo de fallo dominante, y hoy no hay ni una cifra que lo mida ni un fichero donde ponerla.

`pydantic-evals` hace exactamente esto y es la parte de PydanticAI que se puede usar **suelta**, sin adoptar su `Agent`. Merece considerarse por separado antes de que el catálogo crezca — porque el día que crezca ya será tarde para tener una línea base con la que comparar.

### 5.7 Dependencia de forma de la API de Anthropic

`nucleo.py` y `planificador.py` hablan `input_schema`, bloques `tool_use`, `tool_result` con `is_error`, y `cache_control: ephemeral`. `_como_dict` está escrito con pato y no importa el SDK, lo cual está bien y hace testeable el bucle sin red; pero la **forma** del protocolo es de Anthropic de arriba abajo.

La revisión de stack decidió mantener el proveedor, y sigue siendo correcto. Sólo conviene no confundir «mantenemos Anthropic» con «podríamos cambiar»: hoy no se podría sin reescribir los dos módulos. Es un coste asumido, no un coste inexistente, y hay que anotarlo junto a la promesa de reproducibilidad a dos años.

---

## 6. Veredicto por framework

### 6.1 LangGraph — rechazar, y **corregir nuestro criterio de reapertura**

El argumento de la auditoría §5 sigue siendo el bueno y el código de hoy lo refuerza: el modelo de estado de LangGraph no es el modelo de procedencia de `modelo/`, y acabaríamos con dos representaciones del estado del proyecto —que es exactamente el techo que este proyecto está intentando cerrar. Lo que sí aporta y aquí falta (paralelismo, `interrupt`, streaming) se obtiene por separado y mucho más barato: §5.1 son 30 líneas contra una dependencia en el camino crítico.

**Pero hay que arreglar una cosa nuestra.** La revisión de stack §2 escribió como criterio de reapertura: *«(c) los checkpoints propios pasen de 500 líneas»*. `ejecucion.py` tiene **469**. Con ese criterio, adoptar ejecución durable de terceros dependería de que alguien añada una `dataclass` de treinta líneas — y eso es un criterio mal medido, no un umbral.

La lógica de reanudación de verdad —leer la bitácora, saltar lo terminal, la marca `INTENTADO` y su rama— son **unas 50 líneas**. El resto de `ejecucion.py` es el `Plan`, los estados, los dos sustratos de bitácora y el resultado, que son estructura del producto y existirían igual con Temporal debajo.

**Propuesta de corrección, para decidir por Pablo:** sustituir el criterio (c) por *«la lógica de reanudación en sí —no el fichero que la contiene— pase de 250 líneas, o aparezca el primer reintento con backoff, timer o compensación»*. Los criterios (a) —espera humana de más de 24 h— y (b) —compensar un efecto ya aplicado a un fichero del cliente— se quedan como están, y siguen siendo los buenos.

### 6.2 PydanticAI — adoptar **una capa**, rechazar el resto

Es el único de los cuatro que merece una segunda mirada seria, y no como orquestador.

**Lo que rechazamos:** `Agent`, `output_type`, toolsets, ejecución durable. Es el mismo modelo de ejecución ajeno en el centro que LangGraph, con mejor gusto. Su `output_type` tipado es más débil que lo que ya tenemos: `ResultadoDeSkill` no sólo está tipado, además se **verifica** contra `produce`, y sus valores llevan naturaleza epistémica. Cambiar hacia arriba no es cambiar.

**Lo que sí merece adoptarse:** el **esquema de argumentos derivado de la función**. Hoy `manifiesto.comprobar_coherencia` es un test que atrapa la divergencia entre el esquema escrito a mano y la función real. Con un modelo Pydantic por capacidad, esa divergencia **no puede existir**: el esquema se genera de la firma. Pasar de «un test lo detecta» a «es imposible» es exactamente la clase de cambio que este repositorio hace en todas partes —`_MemoriaSoloLectura`, el `Entregable` que no admite `borrador=False`, `Autorizaciones` fail-closed— y sería incoherente rechazarlo aquí por costumbre.

Y llegaría de propina la validación completa de §5.3, más `ModelRetry`, que devuelve el error al modelo en vez de gastar un turno en un `ok: false`.

**Pero hay una alternativa más barata que hay que evaluar antes.** §5.3 se cierra con `jsonschema`, que ya está instalado, en dos horas y sin dependencia nueva. Lo que **no** se cierra sin Pydantic es la *derivación* — que el esquema no se pueda escribir mal porque no se escribe.

**Recomendación concreta para D-3:** cerrarla con un **sí estrecho**, en dos pasos y en este orden.
1. **Ahora:** validar el esquema completo con `jsonschema` en `Capacidad.invocar`, y añadir a `comprobar_coherencia` la comprobación de tipos contra las anotaciones de la función. Cierra el hueco hoy, sin dependencias.
2. **Cuando entre FastAPI** (que trae Pydantic de todas formas): derivar `parametros` de un modelo Pydantic por capacidad, y borrar la mitad de `comprobar_coherencia` que deje de tener sentido. `Capacidad` y `Skill` **siguen siendo `dataclass`**: `naturaleza`, `efectos`, `limitaciones` y `referencia_normativa` no son validación, son gobierno, y no ganan nada dentro de un `BaseModel`.

Y una tercera pieza, evaluable por separado y sin adoptar nada del framework: **`pydantic-evals` para §5.6.** Es una librería suelta, se usa contra funciones propias, y responde la pregunta que dentro de seis meses será la importante — si el planificador elige bien.

### 6.3 Deep Agents — rechazar, y robarle dos ideas

Adoptarlo es adoptar LangGraph, así que hereda el veredicto de §6.1 antes de empezar a discutirse por sí mismo. Y por sí mismo, **su modelo es más débil que el nuestro en la parte que le da nombre**: una Skill de ArchMuse es un «prompt detallado» que además declara qué necesita, qué produce, qué capacidades puede tocar, qué efectos causa, qué verifica y qué no comprueba, con semver. Su herramienta de planificación (`todo`) es una lista que el modelo se escribe a sí mismo; nuestro `Plan` es un DAG validado antes de ejecutar nada.

**Lo que sí tiene y aquí falta, y es serio:**

- **Desalojo de resultados grandes y resumen del historial** (§5.2). Lo mejor de los cuatro para robar. Que se implemente sobre la bitácora que ya existe, no sobre un sistema de ficheros virtual nuevo.
- **Subagentes con contexto aislado.** Hoy todo vive en una lista de mensajes. Para un trabajo que recorra ocho Skills, aislar el contexto de cada una y devolver sólo su `SalidaDeSkill` sería lo natural — y de hecho `SalidaDeSkill` **ya es** ese resumen estructurado. La pieza que falta no es el subagente: es dejar de meter en la conversación principal lo que la Skill ya resumió. Está más cerca de lo que parece.
- **Reglas de permiso por ruta en el sistema de ficheros.** Comparar con `escribe_fichero` antes de que ese efecto crezca: hoy es un permiso binario sin ámbito de ruta, y el día que una Skill escriba donde no debía, el catálogo de efectos habrá dicho la verdad y aun así habrá pasado.

### 6.4 Agno — rechazar, y es el más claro de los cuatro

Su argumento es el rendimiento: instanciación en microsegundos, miles de sesiones concurrentes. **Ese no es el problema de ArchMuse por ningún lado.** Aquí un trabajo dura minutos, lo pide un arquitecto, y el cuello de botella son `ezdxf`, `shapely` y la latencia del modelo. Optimizar la instanciación del agente es optimizar el 0,001 % del reloj.

Su sistema de conocimiento es RAG agéntico sobre vectores, y la revisión de stack §1 ya cerró ese debate por escrito: *«un agente que cita una cifra normativa recuperada de un PDF por similitud semántica es exactamente el producto que un arquitecto abandona a la primera cifra mal citada»*. Adoptar Agno pondría ese patrón como camino por defecto en el centro de un producto cuyo argumento de venta es el corpus curado. Es peor que una dependencia innecesaria: es una pendiente.

AgentOS —FastAPI preconstruido con API, sesiones y gestión— es lo único con valor real, y compite con la capa de transporte que la auditoría ya decidió construir con FastAPI directamente, sin el resto del framework atado.

**Nada que robar**, salvo quizá su marco de «niveles 1-5 de sistema agéntico» como vocabulario para explicar el roadmap. Y no hace falta escribir un criterio de reapertura: si algún día ArchMuse necesita miles de sesiones de agente concurrentes, será porque el producto habrá cambiado tanto que esta auditoría no valdrá.

---

## 7. El hallazgo que no es sobre frameworks

Al rastrear quién llama a qué salen dos cosas que pesan más que las cuatro decisiones anteriores.

**1. El planificador tipado no está en el camino de entrega.** `planificador.planificar()` y `planificador.revisar()` se invocan desde `tests/test_agente_planificador.py` (468 líneas) y desde `scripts/demo_agente.py`. **Y desde ningún otro sitio.** La fachada `copiloto.atender()` llama a `nucleo.ejecutar()`, que es el bucle paso a paso.

Esto significa que la propiedad que el PRD de `AG-1` vendía —*«lo que un bucle no puede hacer es enseñarse […] el arquitecto no puede verlo antes ni pararlo»*, y es «de producto, no de ingeniería»— **no la tiene hoy ningún usuario por ninguna vía**. Están construidos el planificador, la revisión previa, `a_texto()` que dibuja el plan para enseñarlo, y el ejecutor que sabe recibirlo. Falta el cable.

**2. `agente/` no aparece en `app.py`.** Ni una vez. El motor agéntico entero es alcanzable por `python -m agente.invocar`, por los scripts y por los tests. Por el producto, no.

Ninguno de los cuatro frameworks arregla esto, y ninguno lo habría causado. Pero es lo que hace que la pregunta «¿deberíamos adoptar un framework de agentes?» esté hoy mal planteada: **el orquestador propio no está perdiendo contra ningún framework, está esperando a que alguien lo enchufe.**

---

## 8. Recomendación

Seis tareas, ninguna de las cuales exige adoptar nada. Ordenadas por relación entre daño evitado y coste.

| # | Tarea | Coste | Cierra |
|---|---|---|---|
| 1 | Conectar `planificar` → `revisar` → `a_texto` → `Ejecutor` en `copiloto.atender()`, con `nucleo.ejecutar` como el camino conversacional que sigue siendo | 1 jornada | §7 |
| 2 | Validar el esquema completo con `jsonschema` en `Capacidad.invocar`; añadir tipos a `comprobar_coherencia` | 2 h | §5.3 |
| 3 | `Plan.capas()` + ejecución de cada capa en paralelo. Deja de mentirle al modelo en la regla 5 | 0,5 jornada | §5.1 |
| 4 | Desalojo de resultados grandes a la bitácora, con handle y capacidad para reabrirlos | 1 jornada | §5.2 |
| 5 | Corregir el criterio (c) de reapertura de ejecución durable en la revisión de stack | 15 min | §6.1 |
| 6 | Línea base de evaluación del planificador (`pydantic-evals` o casos propios) **antes** de que el catálogo pase de 10 Skills | 1 jornada | §5.6 |

Y una decisión que pide firma: **cerrar D-3 con el sí estrecho de §6.2** —Pydantic sólo para el esquema de argumentos, y sólo cuando entre FastAPI—, en lugar de dejarla abierta indefinidamente.

Las tareas 1 a 4 caben en una semana y dejan el motor en un sitio donde la pregunta del framework deja de tener sentido durante bastante tiempo.

---

## 9. Qué me haría cambiar de opinión

Escrito por adelantado, para que la decisión no se reabra por moda ni se mantenga por inercia:

- **PydanticAI como orquestador** dejaría de ser un error el día que ArchMuse tenga que hablar con un segundo proveedor de modelos en producción **y** su ejecución durable de primera parte (Temporal / DBOS) resulte más barata que la cola en Postgres que ya está decidida. Las dos condiciones, no una.
- **LangGraph** volvería a la mesa si `Plan` dejara de ser un DAG de pasos y necesitara ciclos con estado compartido —replanificación con vuelta atrás, por ejemplo—, porque entonces sí estaríamos escribiendo un runtime de grafo y sería mejor no escribirlo.
- **Deep Agents** entraría si el trabajo típico pasara de 4-6 llamadas a más de 30 con subagentes, es decir, si ArchMuse dejara de resolver encargos acotados y pasara a investigar. No es la dirección del producto.
- **Agno** no tiene condición de reapertura razonable dentro de este producto.

Y en la otra dirección: si dentro de seis meses las siete propiedades de §4 siguen siendo las que nadie más tiene, y las siete carencias de §5 siguen sin cerrarse **con código propio**, entonces el argumento de «lo escribimos nosotros porque lo nuestro es lo difícil» habrá dejado de ser verdad, y esta auditoría hay que rehacerla con menos benevolencia.

---

## Fuentes

- [Deep Agents overview — LangChain](https://docs.langchain.com/oss/python/deepagents/overview) · [langchain-ai/deepagents](https://github.com/langchain-ai/deepagents) · [Doubling down on Deep Agents](https://www.langchain.com/blog/doubling-down-on-deepagents)
- [Pydantic AI](https://pydantic.dev/pydantic-ai) · [pydantic-ai en PyPI](https://pypi.org/project/pydantic-ai/) · [Durable agents con PydanticAI y Temporal](https://temporal.io/blog/build-durable-ai-agents-pydantic-ai-and-temporal)
- [Interrupts — LangChain docs](https://docs.langchain.com/oss/python/langgraph/interrupts) · [Why checkpoints aren't durable execution](https://www.diagrid.io/blog/checkpoints-are-not-durable-execution-why-langgraph-crewai-google-adk-and-others-fall-short-for-production-agent-workflows)
- [Agno](https://www.agno.com/) · [AgentOS](https://www.agno.com/agentos) · [Agno, the agent framework for Python teams — WorkOS](https://workos.com/blog/agno-the-agent-framework-for-python-teams)
