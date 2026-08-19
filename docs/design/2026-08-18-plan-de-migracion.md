# Plan de migración de ArchMuse — v2, agresiva: un vertical funcionando cuanto antes

**Fecha:** 2026-08-18 · **Estado:** propuesta, no aprobada · **Sustituye a la v1 del mismo día.**

**El objetivo, y no hay un segundo.** Poner **un vertical completo funcionando en el stack nuevo, demostrable a un estudio ajeno**, en el menor número de jornadas posible. Todo lo demás —las 38 reglas, la SPA entera, IFC, MCP, el corpus— se aplaza explícitamente hasta que ese vertical esté en pie.

**Decisiones de partida** (tomadas por Pablo el 2026-08-18):

- **Meta del vertical:** demostrable a un estudio ajeno. Incluye identidad con organizaciones, aislamiento por `tenant_id` y despliegue en la UE. Un estudio que no conoce a Pablo se registra y lo usa.
- **Convivencia (estrangulador):** Flask y la SPA siguen sirviendo lo de hoy; FastAPI y Next sirven **solo** el vertical nuevo, detrás del mismo dominio. Nada se cae, y se aceptan dos stacks a la vez durante unos meses.

**Qué se conserva de la v1.** Toda la dirección arquitectónica de `docs/design/2026-08-18-auditoria-arquitectura-tecnologica.md`, aprobada el 2026-08-18. La v2 no cambia ninguna decisión de stack: cambia el **orden** y el **alcance**.

**F0-1 está cerrada** (defecto H1, `modelo/geometria.py::_canonica`, G9 recapturado). Es la única tarea de la v1 ya ejecutada; su continuación está en V0-1.

---

## 1. Qué cambia respecto de la v1, y por qué

La v1 estaba ordenada por **capas**: primero el grafo entero, luego todas las capacidades, luego el orquestador, luego el producto. Es el orden correcto para no dejar deuda — y el peor posible para obtener señal pronto: el primer entregable de punta a punta caía en la jornada ~63, y todavía sin identidad ni despliegue.

La v2 se ordena por **rebanada vertical**: una sola capacidad atraviesa las siete capas del stack nuevo (Next → FastAPI → registro → orquestador → grafo → Postgres → fichero de entrega), con identidad y desplegada. El resto de cada capa se queda sin hacer a propósito.

| | v1 (por capas) | v2 (por vertical) |
|---|---:|---:|
| Primer entregable de punta a punta | jornada ~63 | **jornada ~42** |
| ¿Incluye identidad y despliegue? | No (llegaban en la ~80) | **Sí** |
| Reglas CTE migradas | 38 | **0, a propósito** |
| Pantallas de la SPA migradas | todas | **1** |
| Rutas HTTP migradas | 40 | **las del vertical** |

**Corrección honesta de una cifra.** Al proponer este giro estimé «~35 jornadas». Desglosado tarea a tarea salen **~42**. Sigue siendo unas 20 jornadas antes que la v1 y con ocho jornadas de trabajo que la v1 no tenía a esa altura (identidad, aislamiento, despliegue), pero la cifra buena es 42.

---

## 2. El vertical, definido sin ambigüedad

**El cuadro de superficies, entregado como DXF modificado.** No se reabre la elección: el ADR ya la justificó y los cuatro motivos siguen siendo ciertos, y ahora además pesan más:

1. Devuelve **un fichero de trabajo**, no una pantalla.
2. **No depende del corpus vacío** — el único entregable grande que no lo necesita.
3. Se apoya en código ya probado **contra un plano real de cliente** (`ARCHMUSE_DXF_V2S`), con un test que verifica byte a byte que el original queda intacto.
4. Ejercita el ciclo agéntico completo: intención → plan → validación → ejecución → invariantes → sellado → entrega.

**El recorrido, extremo a extremo:**

```
Arquitecto (Next, autenticado, en su organización)
   │  sube DXF + "rellena el cuadro de la VT1 y dime qué no has podido calcular"
   ▼
FastAPI (solo las rutas del vertical; Flask sigue sirviendo el resto)
   ▼
Cola en Postgres (SKIP LOCKED) → worker
   ▼
Planificador (1 llamada, tool_choice forzado) → DAG tipado
   ▼
Validador determinista → si falta un dato, PREGUNTA en vez de fallar
   ▼
Ejecutor → capacidades → Atributos con procedencia → GRAFO
   ▼
Invariantes (portero) → sellado sha256 → graph_versions (append-only)
   ▼
DXF relleno + cuadro PDF + ACTA DE PROCEDENCIA + sello   [marcado BORRADOR]
```

**El criterio de que el vertical existe** (uno solo, y se comprueba desde fuera):

> Un estudio ajeno se registra, invita a un compañero, sube su DXF, escribe la intención, y descarga el DXF relleno con su acta — donde puede seguir, celda a celda, de qué entidad de qué fichero salió cada número y por qué las demás quedaron `N/D`. Y su original no ha cambiado ni un byte.

---

## 3. Qué se aplaza, explícitamente

Esto es la mitad del plan. Sin esta lista, «agresivo» se convierte en «lo mismo pero con prisa».

| Aplazado | Jornadas que libera | Por qué el vertical no lo necesita |
|---|---:|---|
| Envolver las 38 reglas CTE en capacidades | 3j | El cuadro de superficies no ejecuta ninguna regla del CTE |
| Invertir `classify_problems` (382 líneas de `if/elif`) | 4j | Solo hace falta para las 38 reglas. **Es el mayor aplazamiento y el más contraintuitivo** |
| `api_serializer` sirviendo el grafo, y `modelo/` portante en `/api/analizar` | 6j | El camino viejo sigue con `List[Room]`; el grafo gobierna **solo** en el camino nuevo |
| Migrar las 40 rutas a FastAPI | 3j | Convivencia: FastAPI solo monta las del vertical |
| Migrar la SPA entera | 3j+ | Una pantalla nueva en Next; el resto sigue en la SPA |
| Envolver el visor 3D como isla | 1,5j | El vertical no muestra 3D |
| Sustituir Nominatim y cachear Overpass | 2j | El vertical no geocodifica. **Ojo: sigue siendo bloqueante antes de cobrar**, no antes de demostrar |
| Capacidad de redacción (`llm`) | 1,5j | El entregable son cifras y un acta, no prosa |
| Importador de IFC, servidor MCP, PoC BIM | 6,5j+ | Ensanchado, no vertical |
| Corpus normativo | continuo | El vertical se eligió justo para no depender de él. **Sigue siendo la línea crítica del negocio** |

---

## 4. Qué NO se recorta, aunque estorbe

Bajo presión de velocidad, esto es lo primero que alguien propondría cortar. No se corta, y conviene tener escrito el porqué antes de que alguien lo pregunte con prisa:

- **El sello y `graph_versions` append-only.** Es el foso. Un vertical sin registro reproducible demuestra una arquitectura de software, no un producto defendible.
- **El acta de procedencia.** Sin ella el vertical es «una app que rellena una tabla», y eso lo hace cualquiera. El acta es lo único que un competidor no tiene.
- **El patrón `io` de escritura** (sha256 del original antes/después, `audit()` de la copia, nunca escribir sobre el original). Protege el fichero de un cliente.
- **Golden obligatorio por capacidad `determinista`.**
- **Las dos capas de autorización** (`tenant_id` en el núcleo, no solo en el middleware de Next).
- **La marca de borrador** en todo entregable (C3).
- **La telemetría de coste.** Correr rápido a ciegas no es correr rápido.

---

## 5. Fases

```
V0 (arranque, 4,5j) ─► V1 (el vertical, ~38j) ─► V2 (ensanchar)
CORPUS ═══════════════════════════════════════════► en paralelo desde V0
```

| Fase | Qué | Jornadas | Criterio de cierre |
|---|---|---:|---|
| **V0** | Arranque: cerrar el cabo de G8, CI, telemetría, limpieza | 4,5j | Un push ejecuta la suite entera y hay una cifra medida de coste por proyecto |
| **V1** | El vertical completo, desplegado y con identidad | ~38j | El criterio de la §2, ejecutado por un estudio ajeno |
| **V2** | Ensanchar: las 38 reglas, la SPA, Nominatim, IFC, MCP | por fichar | Se fichará cuando V1 cierre, no antes |

---

# V0 — Arranque (4,5j)

**Criterio de cierre:** `python tests/canario.py` termina en verde, un push ejecuta la suite en CI, y existe una cifra **medida** del coste en euros de un análisis completo.

### V0-1 — Cerrar el cabo de G8 y dejar el canario en verde
**Categoría:** `[BLOQUEANTE]` · **Esfuerzo:** 0,5j

- **Objetivo:** G8 congela el `sha256` de los demás goldens para que ninguna recaptura pase inadvertida. La recaptura de G9 (F0-1) lo ha disparado, con un diff de 3 líneas, todas en `manifiesto[7]`: `bytes` 114476→113728, `lineas` 5454→5410 y el `sha256` de G9. Comprobar que el diff es **solo** eso, recapturar G8, y dejar `tests/canario.py` verde: las cuatro mutaciones (K1 tolerancia de muro, K2 agrupación por proximidad, K3 escala ×10, K4 Terraza reclasificada) deben romper exactamente los goldens que su docstring anuncia.
- **Beneficio:** el canario es la única prueba de que los nueve goldens **muerden** en vez de solo pasar. Lleva parado desde el 2026-08-13. Todo V1 se apoya en que la red avise.
- **Riesgo:** bajo. Si alguna mutación rompe **menos** goldens de lo esperado, es un hueco de cobertura: se anota como tarea, no se ajusta el mapa para que cuadre.
- **Archivos:** `tests/fixtures/golden/G8_determinismo.json`, y `tests/canario.py` solo si el mapa de mutaciones ya no describe la realidad.
- **Dependencias:** F0-1 (cerrada).
- **Comprobación:** salida 0 del canario, con las cuatro mutaciones reportando los goldens que rompen.

### V0-2 — CI en GitHub Actions con la suite completa
**Categoría:** `[DX]` · **Esfuerzo:** 1j

- **Objetivo:** workflow que en cada push y PR instale `requirements.lock.txt` + `requirements-dev.txt` y ejecute `pytest` entero (~14 min). Marcador `lento`. `ARCHMUSE_TEST_RED`, `ARCHMUSE_TEST_IA` y `ARCHMUSE_DXF_V2S` desactivados en CI público; job nocturno aparte que los activa.
- **Beneficio:** 24.584 líneas de test que hoy solo corren cuando alguien se acuerda. V1 mueve mucha superficie; sin una red que se dispare sola, la velocidad se paga en regresiones.
- **Riesgo:** medio. Aparecerán tests que pasan en la máquina de Pablo y fallan en un runner limpio (rutas Windows, `\r\n`, dependencias de `ifcopenshell`). Encontrarlos es el beneficio; presupuestar que el primer arranque no sale verde.
- **Archivos:** `.github/workflows/tests.yml`, `pyproject.toml`.
- **Comprobación:** un PR con un umbral cambiado a mano pone CI en rojo.

### V0-3 — Telemetría de tokens, coste y tope de gasto
**Categoría:** `[MEDICIÓN]` · **Esfuerzo:** 1,5j

- **Objetivo:** en `ia/cliente.py` —único sitio donde se construye el cliente de Anthropic, ya con test de guardia— registrar por llamada: módulo, modelo, `input_tokens`, `output_tokens`, `cache_read_input_tokens`, duración y coste. JSONL local ahora; pasa a `run_steps` en V1-1. Tope de gasto acumulado por proceso, configurable, que corta con error explícito. **Solo métricas, nunca texto de prompt** (son datos de proyecto de un cliente).
- **Beneficio:** hoy `response.usage` no se lee en ningún punto del repositorio, así que no hay forma de responder cuánto cuesta un usuario. Además verifica que la caché de prompt de los seis puntos de llamada acierta: si `cache_read_input_tokens` sale cero de forma sostenida, hay un invalidador que nadie ha visto.
- **Riesgo:** bajo. No romper `tests/test_anthropic_timeout.py`.
- **Archivos:** `ia/cliente.py`, `.env.example`, módulo nuevo de registro.
- **Comprobación:** un análisis completo con entrevista devuelve una cifra en euros desglosada por punto de llamada.

### V0-4 — Sacar del árbol lo que no es el producto
**Categoría:** `[DX]` · **Esfuerzo:** 0,5j

- **Objetivo:** `JarvisApp.py`, `requirements-jarvis.txt` e `Iniciar Jarvis.bat` a su propio repositorio; fuera del árbol versionado `cloudflared_tunnel.log` (731 KB), `flask*.log`, `venv_server_*.log`, `venv/` y `.venv-jarvis/`; quitar de `.env.example` la sección de Gemini.
- **Beneficio:** el repositorio se va a enseñar a un desarrollador y probablemente a un inversor. Y quita ruido: hoy un `wc -l` ingenuo sobre `*.py` devuelve 353.305 líneas en vez de 60.784.
- **Riesgo:** bajo. Comprobar que nada importa de `JarvisApp`.
- **Comprobación:** clon limpio, `pip install -r requirements-dev.txt`, `pytest` en verde.

### V0-5 — Ficha de transcripción y encargo del curador
**Categoría:** `[CORPUS]` · **Esfuerzo:** 1j · **Línea crítica, en paralelo**

- **Objetivo:** (a) la ficha que sigue un colegiado para convertir un artículo del CTE en entrada válida contra `normativa/esquema/regla.schema.json`, con fragmento literal y fuente, probada transcribiendo **una** regla real (propuesta: DB-SI 3 §4) y comprobando que `normativa/` la resuelve de punta a punta; (b) el encargo escrito: alcance, prioridad de Documentos Básicos, cadencia y revisión.
- **Beneficio:** `normativa/es/` está **vacío** —cero reglas— y el motor lleva 3.777 líneas esperando contenido. El cuello de botella es contractual, no técnico. Esta tarea convierte «hay que contratar a alguien» en un encargo que alguien puede aceptar el lunes.
- **Riesgo:** que la escriba un ingeniero sin un colegiado al lado. No se da por cerrada hasta que un colegiado transcriba una **segunda** regla siguiéndola sin ayuda.
- **Dependencias:** ninguna, y **no bloquea nada de V1**. Es deliberado.
- **Comprobación:** la regla piloto está en `normativa/es/`, `normativa/validacion.py` la acepta, y una resolución territorial la devuelve como exigible.

---

# V1 — El vertical (~38j)

Tres bloques. Se pueden solapar los bloques B y C si hay dos personas; dentro de cada bloque el orden es de dependencia.

**Todas las tareas de V1 marcadas `[CAPACIDAD]` o `[PRODUCTO]` necesitan su PRD aprobado antes de una línea de código** (regla de `CLAUDE.md`). Este plan fija el orden y el criterio, no los sustituye.

## Bloque A — Sustrato (8j)

### V1-1 — Postgres: esquema mínimo del vertical
`[MIGRACIÓN]` · **2j** · depende de: —

- **Objetivo:** proveedor gestionado, **región UE decidida antes que proveedor**. Solo las tablas que el vertical usa: `tenants`, `users`, `memberships`, `projects`, `graph_versions`, `runs`, `run_steps`, `artifacts`. `studio_prefs` y `corpus_versions` se aplazan. Cambiar el driver de `analyzer/storage.py` conservando su interfaz, y migrar los datos de SQLite.
- **Beneficio:** habilita cola, aislamiento y registro reproducible. Barato porque `storage.py` documenta su propio invariante: hay un único escritor y `analyzer/` no lo importa.
- **Riesgo:** medio. Los blobs JSON pasan a `JSONB` casi sin cambio; el riesgo está en las migraciones idempotentes por `PRAGMA table_info`, que hay que reescribir como migraciones de verdad.
- **Comprobación:** la suite pasa contra Postgres y una base SQLite con proyectos reales se migra sin pérdida.

### V1-2 — `graph_versions` append-only con sello verificado
`[MIGRACIÓN]` · **1,5j** · depende de: V1-1

- **Objetivo:** cada versión sellada se escribe como fila nueva —nunca `UPDATE`— con `sello_sha256`, versión del motor y versión del corpus. Verificar el sello al escribir. Revocar `UPDATE`/`DELETE` sobre la tabla **a nivel de base de datos**, no por convención.
- **Beneficio:** es la propiedad de la que depende que esto se pueda vender: responder dos años después «este número salió de este dato, con esta regla en esta versión». `sellado_de()` ya existe y desde F0-1 es fiable.
- **Riesgo:** bajo, con una trampa operativa: append-only solo crece. Decidir ya la política de retención.
- **Comprobación:** un `UPDATE` con el usuario de la aplicación falla por permisos; guardar dos veces crea dos filas y la primera queda intacta.

### V1-3 — Ficheros a almacenamiento de objetos
`[MIGRACIÓN]` · **1j** · depende de: V1-1

- **Objetivo:** DXF, PDF y GLB a S3/R2 con URL firmada de caducidad corta; `artifacts` guarda clave, tipo y qué versión del grafo lo produjo. Sacar `pliegos.pdf` del BLOB.
- **Beneficio:** los BLOB no sobreviven a veinte estudios, y la trazabilidad artefacto→versión es media acta.
- **Riesgo:** medio. Una URL firmada mal acotada expone el plano de un cliente: comprobar la tenencia **antes** de firmar, ya en esta tarea.
- **Comprobación:** subir y descargar sin que la base guarde un byte del PDF; una URL caducada devuelve 403.

### V1-4 — `Capacidad` y registro por descubrimiento
`[CAPACIDAD]` · **1,5j** · depende de: —

- **Objetivo:** el `dataclass Capacidad` del ADR §B.3 (`id`, `version`, `dominio`, `naturaleza`, `requiere`, `produce`, `origen_emitido`, `efectos`, `coste_estimado_ms`, `referencia_normativa`, `limitaciones`) y el registro poblado por **descubrimiento de manifiestos**. Paquete `capacidades/`.
- **Beneficio:** de esta pieza dependen las demás. `requiere` es lo que hace imposible el dato plausible: si el grafo no tiene un valor como `KNOWN`, la capacidad no se ejecuta, se pregunta.
- **Riesgo:** medio. `version` en semver desde el día uno, para que ampliar el manifiesto no invalide planes guardados.
- **Comprobación:** dejar un fichero de capacidad nueva y verla en el registro sin tocar ningún `__init__.py`.

### V1-5 — Un manifiesto, tres consumidores generados
`[CAPACIDAD]` · **2j** · depende de: V1-4

- **Objetivo:** generar desde una sola declaración (a) el JSON Schema de herramienta para Anthropic, (b) la operación OpenAPI, (c) la firma de invocación programática.
- **Beneficio:** **es la verificación mecánica de C1.** Si añadir una capacidad obliga a escribir su forma tres veces, C1 está incumplido de nacimiento.
- **Riesgo:** medio. Los tres destinos no admiten lo mismo; el manifiesto será el subconjunto común, no la unión.
- **Comprobación:** los tres artefactos de una capacidad son coherentes en nombres de parámetro.

## Bloque B — La capacidad y el orquestador (17,5j)

### V1-6 — Test mecanizado de la prueba del plugin (C1)
`[CAPACIDAD]` · **0,5j** · depende de: V1-4

- **Objetivo:** test que recorra `capacidades/` y falle si algún módulo importa `flask`, `fastapi`, `request` o cualquier cosa del transporte. Al estilo del que ya vigila que `normativa/` no importe de `analyzer/`.
- **Beneficio:** convierte «¿qué habría que reescribir para invocarla desde Revit?» en un fallo de CI en vez de una pregunta de revisión.
- **Comprobación:** añadir `from flask import request` a una capacidad rompe CI.

### V1-7 — El grafo lleva el cuadro de superficies
`[CAPACIDAD]` · **2j** · depende de: V1-4

- **Objetivo:** que el cuadro (celdas, solicitudes, estado) viva como `Atributo` con procedencia dentro del grafo, no como estructura aparte. **Solo en el camino nuevo:** `/api/analizar` sigue con `List[Room]` y no se toca.
- **Beneficio:** es lo que hace que el acta sea posible: sin procedencia por celda no hay nada que contar. Y es «hacer portante el grafo» reducido a lo que el vertical necesita, en vez de a todo el producto.
- **Riesgo:** medio. Aparecerán datos del cuadro que hoy no tienen dónde vivir en el grafo; cada uno es una decisión de modelo, no un `dict` suelto.
- **Comprobación:** un cuadro relleno se reconstruye del grafo y cada celda dice de qué entidad salió.

### V1-8 — Capacidades de geometría que el cuadro necesita
`[CAPACIDAD]` · **1,5j** · depende de: V1-4

- **Objetivo:** envolver como capacidades solo lo que el vertical usa de `parser.py`, `escala.py`, `superficie_util.py` y `cuadro_superficies.py`. Nada más de `analyzer/`.
- **Beneficio:** es el aplazamiento hecho concreto: 4-5 capacidades en vez de las 38 reglas más geometría completa.
- **Riesgo:** bajo. La tentación será envolver «ya que estamos» dos o tres más.
- **Comprobación:** el registro tiene entre 6 y 8 capacidades al cerrar V1, no más.

### V1-9 — Capacidad de documento con el patrón `io`
`[CAPACIDAD]` · **2j** · depende de: V1-4

- **Objetivo:** `documentos.cuadro_superficies` con `naturaleza="io"`, y elevar a requisito el patrón que `tests/test_cuadro_superficies_export.py` ya aplica: sha256 del original antes y después, `audit()` sobre la copia, ningún otro fichero escrito, nunca escribir sobre el original, y ninguna celda bloqueada con una cifra inventada.
- **Beneficio:** ese test es el mejor activo cultural del repositorio. El vertical lo convierte en política.
- **Riesgo:** medio-bajo; el patrón ya existe y está probado.
- **Comprobación:** el DXF de cliente de `ARCHMUSE_DXF_V2S` sale relleno y el original conserva su sha256.

### V1-10 — Planificador: una llamada, DAG tipado
`[CAPACIDAD]` · **2j** · depende de: V1-5

- **Objetivo:** una sola llamada a Claude con `tool_choice` forzado contra un JSON Schema cuya salida es un DAG de `(capacidad_id, versión, argumentos)`. Recibe un **resumen tipado** del grafo (qué está `KNOWN`, qué `UNKNOWN`) más los manifiestos en orden determinista, en el prefijo cacheado. **Nunca el grafo completo.**
- **Beneficio:** un plan tipado es inspeccionable, cacheable, reproducible y mostrable antes de ejecutar. El patrón de `tool_choice` forzado ya está probado en `pliego_extractor.py` y `extraccion/interprete.py`.
- **Riesgo:** medio. Si el orden de los manifiestos no es determinista la caché no acierta nunca y el planificador se encarece en silencio; V0-3 lo detecta.
- **Comprobación:** la misma intención sobre el mismo grafo da un plan equivalente dos veces, y `cache_read_input_tokens` > 0 en la segunda.

### V1-11 — Validador determinista, y la pregunta como salida
`[CAPACIDAD]` · **2j** · depende de: V1-10

- **Objetivo:** validar **sin gastar un token ni tocar un fichero**: ¿existe la capacidad?, ¿la versión?, ¿`requiere` satisfecho y `KNOWN`?, ¿DAG acíclico?, ¿cabe en presupuesto? El rechazo es tipado, y cuando es por `requiere` insatisfecho genera la pregunta concreta reutilizando `analyzer/interview/motor.py`, que ya sabe preguntar solo lo que falta.
- **Beneficio:** convierte el peor momento del producto —«no puedo hacer esto»— en el mejor: una pregunta concreta. Y rechaza sin gastar dinero.
- **Riesgo:** medio. `interview/motor.py` se escribió para un flujo lineal; adaptarlo puede pedir refactor. Presupuestado aquí.
- **Comprobación:** cuatro planes inválidos (capacidad inexistente, ciclo, `requiere` sin cumplir, fuera de presupuesto) se rechazan con motivos distintos y cero tokens; el tercero produce la pregunta que lo desbloquea.

### V1-12 — Ejecutor del DAG con invariantes como portero
`[CAPACIDAD]` · **2,5j** · depende de: V1-11

- **Objetivo:** ejecución en orden topológico, en paralelo donde los nodos son independientes; cada capacidad escribe `Atributo` con procedencia; tras cada paso `comprobar_invariantes()`, y **un paso que viola un invariante se rechaza, no se registra**; al final, sellar. **Un solo** ciclo de replanificación: si tras replanificar sigue faltando algo, se para y se pregunta.
- **Beneficio:** los invariantes como portero son lo que impide que una alucinación llegue a un entregable. El límite de un ciclo es lo que impide comerse el presupuesto sin converger.
- **Riesgo:** alto; es la pieza con más estado. Mitiga que las capacidades no se hablen entre sí —escriben y leen del grafo— y que las deterministas sean idempotentes.
- **Comprobación:** un plan de 5 capacidades ejecuta y sella; forzar una violación de invariante hace que ese paso se rechace y el grafo quede sin ese atributo.

### V1-13 — Cola en Postgres con `SKIP LOCKED` y worker
`[MIGRACIÓN]` · **2j** · depende de: V1-1

- **Objetivo:** worker aparte consumiendo `SELECT ... FOR UPDATE SKIP LOCKED`. Las ejecuciones dejan de vivir en una petición HTTP. **Ni Redis ni Celery**: a este volumen, añadir un sistema es peor que usar el que ya hay.
- **Beneficio:** cierra el hueco más grande de hoy: una llamada puede retener uno de los 8 hilos de `waitress` hasta 15 minutos (300 s × 3 reintentos, documentado en `ia/cliente.py`).
- **Riesgo:** medio. Relanzar es seguro porque las deterministas son idempotentes y el grafo de entrada está sellado — y eso es justo lo que hace innecesaria la ejecución durable de un framework.
- **Comprobación:** 20 ejecuciones simultáneas; la API responde al instante con un identificador, ningún trabajo se procesa dos veces, y matar el worker a mitad recupera el trabajo.

### V1-14 — Acta de procedencia
`[PRODUCTO]` · **3j** · depende de: V1-12, V1-2

- **Objetivo:** el documento que dice, celda a celda, de qué entidad de qué fichero salió cada número, qué quedó `UNKNOWN` y por qué, y qué no se comprobó. La lista de «no comprobado» **se deriva** de los `limitaciones` de las capacidades ejecutadas; no se redacta a mano. Viaja con cada artefacto.
- **Beneficio:** es el diferencial. Nadie más lo tiene, y la infraestructura ya existe (`Procedencia`, `Atributo`, `sellado_de()`, y desde V1-2 la tabla). Es el Pilar 2 convertido en artefacto.
- **Riesgo:** medio-alto, y **no es técnico**: que salga ilegible para un arquitecto. Un volcado de trazas no es un acta. Su presentación se valida con la voz del arquitecto veterano antes de implementarla; el criterio es C2: una página, con el porqué a un clic.
- **Comprobación:** para tres celdas al azar de un cuadro relleno se puede seguir el acta hasta la entidad concreta del DXF; para una celda `N/D`, leer el motivo.

### V1-15 — Marca de borrador en todo entregable
`[PRODUCTO]` · **0,5j** · depende de: V1-9

- **Objetivo:** todo artefacto sale marcado como **borrador para revisión de un colegiado**, con el acta adjunta, sin excepción y sin opción de desactivarlo.
- **Beneficio:** es C3 literal y la frontera legal del producto: ArchMuse asesora, no firma.
- **Riesgo:** bajo, con un detalle: marcar un DXF sin corromperlo remite al patrón `io` de V1-9.
- **Comprobación:** el DXF y el PDF llevan la marca, y no existe opción de configuración para quitarla.

## Bloque C — Superficie, identidad y despliegue (12,5j)

### V1-16 — FastAPI junto a Flask, solo las rutas del vertical
`[MIGRACIÓN]` · **1,5j** · depende de: V1-5

- **Objetivo:** montar FastAPI **conviviendo** con Flask detrás del mismo dominio, sirviendo únicamente las rutas del vertical, generadas desde el manifiesto. Las 40 rutas de `app.py` **no se tocan**.
- **Beneficio:** es la decisión que hace posible todo el recorte: se estrena el transporte nuevo sin migrar 2.713 líneas de handlers.
- **Riesgo:** bajo-medio. Definir el reparto de prefijos y que no haya dos rutas compitiendo.
- **Comprobación:** el vertical responde por FastAPI y el resto del producto sigue respondiendo por Flask, sin cambios en la SPA.

### V1-17 — Cliente TypeScript generado en CI
`[DX]` · **1j** · depende de: V1-16

- **Objetivo:** generar el cliente TS desde el OpenAPI en CI y fallar si difiere del comiteado. Cero tipos del dominio escritos a mano.
- **Beneficio:** cierra el defecto real del frontend actual: 5.523 líneas de JS leyendo JSON no tipado contra un contrato mantenido a mano.
- **Comprobación:** renombrar un campo de un modelo Pydantic pone CI en rojo.

### V1-18 — IdP gestionado: organizaciones, invitaciones, roles
`[PRODUCTO]` · **2j** · depende de: V1-1

- **Objetivo:** Clerk o WorkOS, con organizaciones e invitaciones y los cuatro roles (propietario, arquitecto, colaborador, lectura). Comparativa escrita antes de elegir, con región y DPA como criterios de primer orden.
- **Beneficio:** construirlo en Flask son tres semanas que no diferencian nada y son un incidente esperando. Esas tres semanas van al corpus.
- **Riesgo:** medio. Verificar región europea y DPA **antes** de firmar.
- **Comprobación:** dos correos crean dos estudios; una invitación aceptada da acceso al estudio correcto y solo a ese.

### V1-19 — `tenant_id` en el núcleo, RLS y test de aislamiento
`[SEGURIDAD]` · **2,5j** · depende de: V1-18, V1-4

- **Objetivo:** objeto de contexto (`tenant_id`, `user_id`, `run_id`) que atraviesa toda invocación de capacidad, RLS en Postgres, y un test que falle si alguna consulta carece de predicado de tenant, más un test que ataque: autenticado como A, intentar leer datos de B en cada endpoint.
- **Beneficio:** retrofit de tenencia es el refactor más caro que existe. Y la doble capa es C1: el día que la superficie sea un plugin, el middleware de Next no está.
- **Riesgo:** alto. Un hueco aquí es una fuga entre clientes. RLS actúa de red además del predicado.
- **Comprobación:** una consulta sin predicado devuelve cero filas por RLS; el test de ataque falla en todos los endpoints.

### V1-20 — Next: shell, sesión y la pantalla del vertical
`[PRODUCTO]` · **3j** · depende de: V1-18, V1-17

- **Objetivo:** proyecto Next (App Router, TS estricto), sesión con cookie `httpOnly`, rutas protegidas en servidor, páginas públicas mínimas, y **una** pantalla: subir DXF, escribir la intención, ver el plan y el progreso por capacidad, descargar entregables y leer el acta. **Ni una línea de lógica de negocio**, y una regla de lint que lo impida.
- **Beneficio:** es la mitad visible del vertical y donde se juega si un arquitecto entiende el acta.
- **Riesgo:** medio. La tentación de migrar «ya que estamos» otra pantalla. No.
- **Comprobación:** la pantalla completa el recorrido de la §2 de principio a fin, y ninguna Route Handler importa nada salvo el cliente generado.

### V1-21 — Despliegue en la UE
`[SEGURIDAD]` · **2,5j** · depende de: V1-13, V1-1

- **Objetivo:** contenedor Linux del núcleo (con `gunicorn`, que en Linux sí funciona), worker como proceso separado, frontend desplegado, secretos en gestor, región UE, y el túnel `cloudflared` retirado del camino del vertical.
- **Beneficio:** hoy el producto vive en `127.0.0.1` detrás de un túnel desde un portátil Windows, y eso no se puede enseñar a un estudio ajeno.
- **Riesgo:** medio. Presupuestar que `ifcopenshell` y `mapbox_earcut` darán trabajo en la imagen. Runbook mínimo: qué hacer si el worker se atasca.
- **Comprobación:** dominio propio con TLS, sin túnel; matar el worker no tira la API; ningún secreto en el repositorio ni en la imagen.

---

# V2 — Ensanchar (se ficha cuando V1 cierre)

Sin fichas todavía, a propósito: ficharlas ahora sería planificar contra un stack que aún no existe. El orden previsto, y lo que lo justifica:

1. **Sustituir Nominatim** — bloqueante legal antes de **cobrar**, no antes de demostrar. Lo primero de V2.
2. **Invertir `classify_problems`** y envolver las 38 reglas CTE — el segundo vertical.
3. **Migrar la SPA por pantallas**, y envolver el visor 3D como isla.
4. **`api_serializer` sobre el grafo** y `modelo/` portante también en el camino viejo; retirar Flask.
5. **Servidor MCP** — casi gratis con el manifiesto ya hecho, y es canal de distribución.
6. **Importador de IFC**, y después la PoC de BIM del horizonte de 3 meses.
7. **Caché determinista** por (versión, sello) y escalonado de modelo — cuando haya volumen que lo justifique.

---

# Riesgos propios de ir agresivo

Los de cada tarea están en su ficha. Estos son los que **crea la v2** y la v1 no tenía:

| # | Riesgo | Mitigación |
|---|---|---|
| **A1** | **Dos stacks a la vez durante meses.** Flask+SPA y FastAPI+Next conviviendo: doble despliegue, doble sesión, dos sitios donde mirar un fallo. | Es el precio elegido de la convivencia. Se acota con un reparto de prefijos escrito y con la regla de que **ninguna pantalla vieja se toca** mientras dure V1. Si V2 no arranca en los tres meses siguientes al cierre de V1, la convivencia deja de ser una fase y pasa a ser el estado permanente: eso es el fracaso a vigilar. |
| **A2** | **El vertical se queda solo.** Un producto con una capacidad nueva y 38 reglas en el stack viejo. | El criterio de cierre de V1 es que lo use un estudio ajeno. Si eso ocurre, V2 se financia solo; si no ocurre, la respuesta correcta no es ensanchar, es entender por qué. |
| **A3** | **Aplazar `classify_problems` se convierte en no hacerlo nunca.** Es el nudo de 382 líneas que impide registrar capacidades, y la v2 lo empuja fuera del camino crítico. | Está el primero de la fila técnica de V2, y el segundo vertical no puede empezar sin él. Anotado aquí para que nadie lo redescubra dentro de un año. |
| **A4** | **La velocidad se cobra en el acta.** Es la tarea más fácil de recortar bajo presión y la única que hace el vertical diferente de una app cualquiera. | Está en la lista de §4. Su criterio de aceptación es de arquitecto, no de ingeniero. |
| **A5** | **El corpus sigue vacío al terminar V1**, porque el vertical se eligió para no necesitarlo. | V0-5 arranca el día uno y no depende de nada. Pero conviene decirlo sin adornos: **un vertical impecable con el corpus vacío sigue siendo un producto que no puede verificar normativa.** Es el riesgo dominante del proyecto y ninguna decisión de este documento lo mueve. |
| **A6** | **Una persona.** Las ~42 jornadas son secuenciales para un solo ejecutor. | Los bloques B y C de V1 son solapables y está marcado dónde. Ninguna fase deja el producto caído, así que parar entre bloques es una opción real. |
