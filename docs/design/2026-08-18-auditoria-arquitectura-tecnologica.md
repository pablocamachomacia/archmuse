# Auditoría de arquitectura tecnológica — orientada al producto vendible

**Fecha:** 2026-08-18 · **Estado:** propuesta, no aprobada · **Alcance:** decisiones de stack y arquitectura, no bugs

**Qué es este documento.** Dieciocho decisiones de arquitectura, cada una con su alternativa rechazada y el motivo. No es una auditoría de calidad de código — eso ya está en `TECH_REVIEW.md` y `REFACTOR_MASTERPLAN.md`, y no hace falta repetirlo. La pregunta que se responde aquí es otra: **con qué arquitectura ArchMuse se puede vender a un estudio de arquitectura y sostenerse tres años sin reescribirse.**

**Qué NO es.** No es el plan de migración. El plan por fases se escribe después de que estas decisiones estén aprobadas; §18 deja el esqueleto sobre el que se construirá, deliberadamente sin fichas de tarea.

**Criterios de aceptación aplicados.** Las cinco consecuencias vinculantes C1-C5 de `docs/design/2026-08-18-alineacion-estrategica-paso0.md` (aprobado por Pablo el 2026-08-18). Cada decisión se justifica también contra ellas, y donde una decisión existe **solo** por C1-C5, lo digo.

**Cómo he verificado.** Todo dato numérico sale de leer el repositorio hoy, no de documentos anteriores. Donde no he podido verificar, está en §19.

---

## 0. Las dieciocho decisiones, en una tabla

| # | Pregunta | Decisión | Alternativa rechazada |
|---|---|---|---|
| 1 | Qué conservar | El motor: `modelo/`, `normativa/`, geometría, 38 reglas, exportadores, la suite | Conservar también la SPA |
| 2 | Qué migrar | Las **superficies**: transporte HTTP, frontend, base de datos, identidad | Migrar el motor a otro lenguaje |
| 3 | React vs Next | **Next.js (App Router)** como BFF + UI, sin lógica de negocio dentro | React+Vite puro; Next como backend |
| 4 | Python vs TypeScript | **Python** todo lo que toque geometría, reglas, grafo y orquestación. **TypeScript** solo UI y transporte | Reescribir reglas en TS; escribir agentes en TS |
| 5 | OpenAI Agents vs LangGraph | **Ninguno.** Orquestador propio (~600 líneas) sobre tool use de Anthropic | LangGraph (dos modelos de estado); Agents SDK (proveedor equivocado) |
| 6 | Arquitectura de agentes | Un planificador → validador determinista → ejecutor de DAG → invariantes → sellado. Un ciclo de replanificación | Bucle de agente libre; multi-agente en debate |
| 7 | Tools | Manifiesto único que genera **tres** consumidores: JSON Schema del LLM, OpenAPI y plugin. 8-12 capacidades gruesas | 38 herramientas finas expuestas al planificador |
| 8 | Memoria | Tres memorias separadas: grafo sellado (proyecto), filas de run (ejecución), preferencias de estudio (retención). Sin memoria conversacional | Vector store como "memoria del agente" |
| 9 | RAG / normativa | Corpus curado en YAML como única fuente de cifras. Recuperación **solo** para localizar y mostrar articulado | RAG sobre los PDF del CTE |
| 10 | MCP | Sí, como **canal de distribución** del registro de capacidades. No como consumidor de servicios externos | MCP antes de que exista el registro |
| 11 | Base de datos | **Postgres gestionado** en la UE, con `graph_versions` append-only. Ficheros a almacenamiento de objetos | Seguir en SQLite; BLOB en tabla |
| 12 | Autenticación | IdP gestionado con organizaciones y roles desde el día uno (Clerk o WorkOS) | Construirla en Flask |
| 13 | Multiusuario | Single-DB multi-tenant con RLS y `tenant_id` en el contexto de toda capacidad | Schema por cliente; edición colaborativa en tiempo real |
| 14 | Despliegue | Contenedores Linux en plataforma gestionada, **worker con cola** para lo largo, región UE | Túnel `cloudflared` desde el portátil |
| 15 | Costes por usuario | Escalonado por modelo + caché determinista por sello. Precio de asiento con generación medida | Asiento plano con generación ilimitada |
| 16 | Observabilidad | El log de ejecución **es** el acta de procedencia. Evaluación partida por `naturaleza` | Añadir observabilidad como capa aparte |
| 17 | Qué permite venderlo | Cuatro propiedades: registro defendible, frontera de lo no comprobado, invocable donde trabaja, equipos desde el día uno | Más capacidades, mejor visor |
| 18 | Fases | Seis fases; ninguna deja el producto caído | Un "gran salto" de stack |

---

## 1. El punto de partida, medido hoy

Contado sobre ficheros versionados, excluyendo `venv/` y `static/vendor/`:

| Zona | Ficheros | Líneas | Estado real |
|---|---:|---:|---|
| `analyzer/` | 50 | 22.031 | Es el producto |
| `tests/` | 104 | 24.584 | Mayor que el producto. El activo más importante del repositorio |
| `docs/` | 102 | 27.630 | Más volumen que el producto |
| `static/` (sin vendor) | 13 | 18.345 | SPA vanilla, **sin `package.json`, sin build** |
| `normativa/` | 15 | 3.777 | Motor completo · **`normativa/es/` está vacío: cero reglas** |
| `app.py` | 1 | 2.713 | 40 rutas en un fichero |
| `modelo/` | 11 | 2.199 | Grafo con procedencia epistémica · **no participa en ningún cálculo** |
| `extraccion/` + `ingesta/` | 21 | 2.386 | Pipeline normativo por LLM, aislado |

Seis hechos verificados que condicionan todo lo que sigue:

1. **No hay autenticación.** `grep -rniE 'login|session\[|jwt|oauth|password|autentic'` sobre `app.py`, `analyzer/`, `normativa/`, `modelo/` e `ia/` devuelve **cero coincidencias**. No hay usuarios, ni roles, ni aislamiento.
2. **`normativa/es/` es un directorio vacío.** Las únicas reglas normativas en formato declarativo del repositorio están en `tests/fixtures/corpus_ficticio/`. El motor de resolución territorial funciona y no tiene nada que resolver.
3. **No hay telemetría de coste.** `response.usage` no se lee en ningún sitio: ni `input_tokens`, ni `output_tokens`, ni coste. Hoy es **imposible** responder "cuánto cuesta un usuario" con datos; §15 lo estima desde los techos de `max_tokens`.
4. **No hay cola de trabajos.** Cero `threading`, cero `Queue`, cero streaming (`text/event-stream`). Una llamada al generador puede retener un hilo de `waitress` hasta 15 minutos (300 s × 3 reintentos, documentado en `ia/cliente.py`), con un pool de 8 hilos.
5. **El despliegue actual es un portátil.** `waitress` sobre `127.0.0.1` (`app.py:2669`) más un túnel; `cloudflared_tunnel.log` pesa 731 KB, así que se ha usado en serio.
6. **Hay dependencias externas sin SLA, y una con problema de licencia de uso.** `analyzer/sitio.py` llama a Catastro OVC, Overpass (con dos espejos de reserva) y **Nominatim**. La política de uso de Nominatim prohíbe explícitamente el uso intensivo o comercial de su instancia pública: es un bloqueante de venta, no un detalle.

Y un hecho que es una ventaja y conviene no perder de vista: **la suite es mayor que el producto**. Es lo que hace que este documento sea ejecutable en vez de aspiracional.

---

## 2. Qué se conserva, qué se migra, qué se congela, qué se mata

La regla que ordena esta sección: **se conserva lo que es difícil de replicar y no está acoplado a la web; se migra lo que es superficie; se congela lo que demo bien y no vende.**

### 2.1 Se conserva íntegro (es el foso)

| Módulo | Por qué |
|---|---|
| `modelo/` (2.199) | Procedencia epistémica tipada: `Atributo` no admite valor sin `origen`. Ningún competidor tiene esto. Es la base del acta de procedencia y del sello. **Y hoy no se usa** — conservarlo significa hacerlo portante, no dejarlo quieto |
| `normativa/` (3.777) | Motor de resolución territorial puro, sin estado, sin dependencia de `analyzer/`. Es la pieza mejor diseñada del repositorio |
| Las 38 `evaluate_*` de `evaluator.py` | Puras, tipadas, con su `*Result`. Ya tienen forma de herramienta: envolverlas es cablear, no reescribir |
| Geometría: `parser.py`, `escala.py`, `plan_svg.py`, `circulation.py`, `spatial_quality.py`, `ocupacion.py`, `sectorizacion.py`, `altura_evacuacion.py` | Reconstruir un plano desde un DXF sucio es el trabajo que nadie quiere hacer. El mercado español pequeño sigue en DXF |
| Exportadores: `dxf_export`, `ifc_export`, `cuadro_superficies_export`, `dossier_pdf`, `pdf_report` | Ya producen ficheros de entrega. Son el embrión del contrato "trabajo terminado" |
| `extraccion/` + `ingesta/` | El pipeline que convierte PDF oficial en candidato de corpus. Con el corpus en el camino crítico (C5), esto pasa de aislado a central |
| `analyzer/interview/` (2.545) | **Se conserva pero cambia de papel.** Deja de ser un asistente de 20 preguntas y pasa a ser el generador de preguntas del validador de planes: "qué falta para poder ejecutar esto". Es la lógica más difícil de la orquestación y ya está escrita |
| `tests/` (24.584) | Sin discusión |

### 2.2 Se migra (es superficie, no motor)

| Qué | A qué | Por qué ahora |
|---|---|---|
| Los 40 handlers de `app.py` | Capa de capacidades + transporte fino | C1: hoy la lógica vive en el handler, así que **ninguna** capacidad pasa la prueba del plugin |
| `api_serializer.py` (533) | Serializar el **grafo**, no `List[Room]` | Es el paso que hace portante a `modelo/`. Hoy hay dos representaciones del proyecto y manda la pobre |
| SQLite en `~/.archmuse` | Postgres gestionado (§11) | Multi-tenant, concurrencia real, recuperación a un punto en el tiempo |
| `static/app.js` + `entrevista.js` + `programa-necesidades.js` (~8.200) | **Reescritura** en Next + TS (§3) | Es el único sitio donde reescribir cuesta menos que migrar: sin build, sin tipos, sin componentes, 117 `getElementById` y 32 `innerHTML` en un fichero |
| Nada de autenticación | IdP gestionado (§12) | Se vende a estudios, no a individuos |

### 2.3 Se congela (funciona, no se amplía)

| Qué | Postura |
|---|---|
| Visor 3D (`viewer-*.js`, ~5.900 líneas de three.js) | **Se conserva tal cual y se envuelve como isla**, no se reescribe a React Three Fiber. Es la reescritura de mayor riesgo y menor valor disponible en este repositorio. Único trabajo autorizado: conectarlo a los hallazgos del motor de reglas (paso 1 de `ROADMAP_VISION_ARQUITECTONICA.md` §6) |
| `main.py` + `analyzer/reporter.py` (628) | Congelada, ya con banner. Ni capacidades nuevas ni borrado todavía |
| `experimentos/` (1.163) | Desechable por diseño. Correcto como está |
| El percentil comparativo | `MOAT_ANALYSIS.md` dice que no da foso. Ya etiquetado como estimación. No recibe trabajo |

### 2.4 Se saca del repositorio

| Qué | Dónde va |
|---|---|
| `JarvisApp.py` (989) + `requirements-jarvis.txt` + `.venv-jarvis/` + `Iniciar Jarvis.bat` | Su propio repositorio. Es un asistente de Gemini sin relación con ArchMuse, y arrastra un entorno virtual entero y una clave de otro proveedor por el `.env.example` del producto |
| `cloudflared_tunnel.log` (731 KB), `flask*.log`, `venv_server_*.log`, `venv/`, `.venv-jarvis/` | Fuera del árbol versionado. Un repositorio que se va a compartir con un desarrollador o un inversor no lleva logs de 731 KB ni dos entornos virtuales |

---

## 3. React vs Next: **Next.js con App Router**

**Decisión.** Next.js (App Router) como **única superficie web**: UI de producto, páginas públicas de marketing y precio, y BFF (sesión, cookies, proxy autenticado hacia el núcleo Python). TypeScript estricto. Despliegue como servicio propio.

**La regla que hace que esta decisión no viole C1:** *Next no contiene lógica de negocio. Ni una regla, ni un cálculo, ni una decisión normativa.* Next hace tres cosas: renderiza, mantiene la sesión y reenvía. Si algún día hay que servir la misma capacidad desde un plugin de Revit, Next no se toca porque nunca supo nada.

**Por qué Next y no React+Vite:**

- Se vende a estudios: hace falta registro, invitación, sesión con cookie `httpOnly` y rutas protegidas en servidor. En un SPA puro eso obliga a montar un servidor aparte de todas formas — y entonces ya tienes Next, peor hecho.
- Hace falta superficie pública indexable (qué es, precio, para quién, aviso legal). Un SPA la sirve mal, y no es un detalle cosmético cuando el objetivo es vender.
- Las ejecuciones del orquestador son largas (§14). Streaming de estado por capacidad se sirve mucho mejor desde un servidor de rendering con RSC + streaming que desde un SPA haciendo polling.
- Las descargas autenticadas (DXF, IFC, PDF, GLB) necesitan una ruta de servidor que ponga la cabecera y compruebe el permiso. En SPA acabas exponiendo URLs firmadas antes de tiempo.
- Contratación: Next es el estándar. Un desarrollador frontend entra sabiendo dónde está todo.

**Lo que Next cuesta, con los ojos abiertos:** un runtime más que operar, un `node_modules` en un proyecto que hoy no tiene ninguno, y la tentación permanente de escribir "solo esta validación" en una Route Handler. Contra lo último, un test mecánico: **ninguna ruta de Next puede importar nada que no sea el cliente generado de la API** (§4).

**Migración del visor.** Los `viewer-*.js` ya son módulos ES con `importmap` y librerías vendorizadas. Se montan como isla cliente (`dynamic(..., {ssr:false})`) con un contrato de props explícito. No se traducen a React Three Fiber: eso es un trimestre para llegar al mismo sitio.

---

## 4. Python vs TypeScript: la frontera, y por qué no es negociable

**Python — todo el núcleo.** Geometría, reglas, grafo, normativa, orquestación, exportadores, ingesta.

El motivo es material, no de gusto: `ezdxf`, `ifcopenshell`, `shapely` y `trimesh` no tienen equivalente creíble en TypeScript. `ifcopenshell` en particular es la única implementación seria de IFC en un lenguaje de alto nivel, y el importador de IFC es el paso 8 de la secuencia del ADR y lo que neutraliza el ataque de `DESTROY_ARCHMUSE.md` §3. Mover el núcleo a TS es tirar el foso para ganar homogeneidad de lenguaje. No se hace.

**TypeScript — UI, BFF, visor 3D.** Nada más.

**La frontera: un contrato generado, nunca escrito dos veces.**

Hoy `api_serializer.py` mantiene a mano la forma de la respuesta, y el JS la consume sin tipos: 5.523 líneas leyendo JSON no tipado. Ese es el defecto real que hay que cerrar, y se cierra así:

1. El núcleo Python expone su esquema OpenAPI — lo que sugiere sustituir Flask por **FastAPI + Pydantic** en la capa de transporte. No en el motor: el motor no sabe que existe HTTP.
2. Del OpenAPI se **genera** el cliente TypeScript en CI.
3. Fallo de CI si el cliente generado difiere del comiteado. Cero tipos escritos a mano en el frontend.

**Prohibiciones explícitas**, para no discutirlas por PR: no se escribe geometría en TS; no se escribe lógica de agente en TS; no se duplica un tipo del dominio en TS.

---

## 5. OpenAI Agents SDK vs LangGraph: **ninguno de los dos**

Es la decisión con la que más gente discutirá, así que va argumentada entera.

**Decisión.** Orquestador propio, en Python, sobre el tool use de la API de Anthropic. Estimación: 500-700 líneas para planificador + validador + ejecutor + registro. Con `tool_choice` forzado contra un JSON Schema — patrón que **este repositorio ya usa correctamente** en `pliego_extractor.py` y `extraccion/interprete.py`.

**Por qué no LangGraph.** LangGraph aporta un runtime de grafo con checkpointing y reanudación. Suena a exactamente lo que hace falta. El problema es que su modelo de estado **no es** el modelo de procedencia de `modelo/`, y no se le puede convencer de que lo sea. Acabarías con dos representaciones del estado del proyecto — que es precisamente el techo que este proyecto ya tiene y está intentando cerrar. Además, la propiedad que más importa aquí es que **el plan sea inspeccionable y rechazable antes de gastar un token**; eso es un validador determinista sobre un DAG tipado, no un grafo de ejecución. Y a cambio pagas una dependencia grande, con ritmo de cambios propio, en el camino crítico de un producto cuyo argumento de venta es la reproducibilidad a dos años.

**Por qué no el Agents SDK de OpenAI.** Dos motivos independientes, cada uno suficiente. (a) Proveedor equivocado: el repositorio tiene seis puntos de llamada a Anthropic, con caché de prompt ya puesta en los seis y `tool_choice` forzado en dos; cambiar de proveedor es trabajo sin beneficio de producto. (b) Modelo equivocado: es un framework de bucle de agente, y §B.4 del ADR ya rechazó el bucle por escrito — un agente que llama herramientas en bucle no es inspeccionable, ni cacheable, ni reproducible, ni mostrable antes de ejecutar.

**Lo que se pierde al no usar framework, dicho sin adornos.** No hay ejecución durable gratis, ni observabilidad integrada, ni primitivas de human-in-the-loop. Y aquí está el argumento que cierra la decisión: **esas tres piezas hay que poseerlas de todas formas por motivos de producto.** La durabilidad son filas de `runs`/`run_steps` en Postgres, que es el sustrato del acta de procedencia (C2). La observabilidad es el log de ejecución, que **es** el acta (§16). El human-in-the-loop es la confirmación de los efectos `io` del manifiesto. Importar un framework para eso te obliga a mantener dos versiones de cada una: la suya y la que el producto necesita.

**Cuándo reconsiderarlo, con criterio concreto.** El día que una ejecución tenga que sobrevivir a un reinicio del proceso a mitad de camino y reanudarse exactamente donde estaba, el problema se llama **ejecución durable**, y la respuesta es **Temporal**, no LangGraph. No antes: hoy una ejecución que falla se relanza, porque las capacidades deterministas son idempotentes por definición y el grafo de entrada está sellado.

**Nota sobre el Claude Agent SDK.** Es una herramienta excelente para el lado de *construcción* — agentes que trabajan sobre el repositorio. No es el runtime del producto y no debe entrar en él.

---

## 6. Arquitectura de agentes

Se adopta §B.4 del ADR sin cambios de fondo, con cuatro precisiones que faltaban.

```
intención + ficheros
        ↓
  [ingesta]  → Atributos con procedencia → GRAFO (sellado v0)
        ↓
  [planificador]  1 llamada LLM · tool_choice forzado · devuelve DAG tipado
        ↓
  [validador]  determinista · ¿existe la capacidad? ¿versión? ¿`requiere` KNOWN? ¿presupuesto?
        ↓                           ↘ inválido → PREGUNTA concreta (interview/motor.py)
  [ejecutor]  DAG · paralelo donde es independiente · cada paso escribe en el grafo
        ↓
  [invariantes]  portero, no informe → viola = se rechaza el paso
        ↓
  [sellado]  sha256 canónico → entregables + acta de procedencia + limitaciones
```

**Precisión 1 — el planificador no ve el grafo entero.** Ve un resumen tipado: qué rutas están `KNOWN`, cuáles `UNKNOWN`, y los manifiestos. Meter el grafo completo en el contexto es caro, invalida la caché de prompt en cada ejecución y no mejora el plan.

**Precisión 2 — presupuesto explícito por ejecución.** El validador suma `coste_estimado_ms` y un coste en tokens estimado del plan, y rechaza lo que supere el techo del plan del cliente. Es la defensa de R8 y también el mecanismo de negocio de §15.

**Precisión 3 — un ciclo de replanificación, y el segundo fallo es una pregunta.** Si tras replanificar sigue faltando un dato, el sistema **no vuelve a intentarlo**: pregunta. `analyzer/interview/motor.py` ya sabe preguntar solo lo que falta y no repetir.

**Precisión 4 — un solo redactor, sin debate.** Nada de multi-agente ni de críticos enfrentados. Hay exactamente dos papeles con LLM: el que planifica y el que redacta prosa a partir de atributos ya calculados. Multi-agente aquí multiplica coste y latencia y no mejora la única cosa que importa —que las cifras sean correctas—, y las cifras no las toca ningún LLM (§B.1 del ADR).

---

## 7. Tools: un manifiesto, tres consumidores

Se adopta el `Capacidad` de §B.3 del ADR. Tres añadidos que son los que lo convierten en decisión de arquitectura y no en dataclass.

**Añadido 1 — el manifiesto genera los tres consumidores.** De una sola declaración salen: (a) el JSON Schema de la herramienta para la API de Anthropic, (b) la operación OpenAPI del endpoint HTTP, (c) la firma que un plugin de Revit invocaría. **Esta es la verificación mecánica de C1**: si añadir una capacidad obliga a escribir su forma tres veces, C1 está incumplido de nacimiento. Y como el OpenAPI genera el cliente TS (§4), añadir una capacidad llega al frontend tipada sin escribir tipos.

**Añadido 2 — granularidad gruesa hacia el planificador.** Las 38 `evaluate_*` **no** se exponen como 38 herramientas. Un planificador que elige entre 38 opciones casi idénticas se degrada; es el error clásico. Se agrupan en 4-6 capacidades por dominio (`cte.evacuacion`, `cte.habitabilidad`, `cte.accesibilidad`, `cte.sectorizacion`, `geometria.planta`, `territorial.parcela`), y dentro de cada una las sub-reglas deterministas se ejecutan **todas**, porque son baratas y su resultado agregado es el que el arquitecto quiere ver. Con exportadores y redacción, el catálogo del MVP queda en 10-12 — exactamente lo que C4 exige.

**Añadido 3 — toda capacidad devuelve `List[Atributo]`, nunca prosa ni dict libre.** Es lo que permite que el invariante de §B.1 sea comprobable: una capacidad `llm` que intente emitir `origen=OBSERVADO` falla en el sellado, no en revisión de código.

**Y el nudo que hay que deshacer antes:** `evaluator.classify_problems` (382 líneas de `if/elif`; tareas 16 y 22-24 del `REFACTOR_MASTERPLAN.md`) es lo que hoy impide que una regla declare su propia traducción a hallazgo. Sin invertirlo no hay registro posible. Va antes del manifiesto, no después.

---

## 8. Memoria: tres cosas distintas que se confunden con una

**Decisión.** Tres memorias, con sustratos distintos, y ninguna es un vector store.

| Memoria | Qué es | Dónde vive | Vida |
|---|---|---|---|
| **De proyecto** | El grafo sellado y versionado. La verdad sobre el proyecto | `graph_versions`, append-only | Para siempre. Es el registro que se defiende ante una aseguradora |
| **De ejecución** | Plan, pasos, resultados, tokens, veredictos de invariante | `runs` + `run_steps` | Se conserva por proyecto; es la materia prima del acta |
| **De estudio** | Convenciones del cliente: nomenclatura de capas, formato de cuadro, criterios habituales, plantillas | Filas estructuradas por `tenant_id` | Mientras el cliente sea cliente |

**La memoria de estudio es una decisión de negocio disfrazada de técnica.** Es lo que hace que el producto encaje cada vez mejor en un estudio concreto, y lo que convierte "cancelar" en "desmontar un proceso" — que es literalmente el argumento de retención de `MOAT_ANALYSIS.md`. Se guarda como datos estructurados, revisables y editables por el cliente. **No** como embeddings: el cliente tiene que poder ver y corregir lo que ArchMuse "cree" sobre su forma de trabajar.

**Lo que se descarta explícitamente:** memoria conversacional persistente entre sesiones inyectada al contexto del LLM. Es la vía de entrada de alucinaciones con apariencia de historia ("el proyecto anterior usaba 2,50 m de altura libre"), es un problema de privacidad entre proyectos de clientes distintos, y no resuelve ningún dolor del arquitecto. La memoria del sistema es el grafo, y el grafo tiene procedencia.

---

## 9. RAG y normativa: la decisión más importante del documento

**Decisión.** No se hace RAG sobre los PDF del CTE. El corpus curado en YAML es la **única** fuente admisible de una cifra normativa. La recuperación existe, pero solo para localizar y mostrar articulado — nunca para producir un número.

**Por qué esto no es purismo.** El modo de fallo del RAG sobre texto normativo es una cita plausible y equivocada. `DESTROY_ARCHMUSE.md` §5.1 dice que el motivo nº1 de abandono es descubrir un resultado mal calculado, y que después el arquitecto **no vuelve a confiar en el 95% correcto**. En un producto cuyo argumento de venta es defensa profesional ante una firma, un artículo mal citado no es un bug: es el fin de la relación comercial. Y hay una razón de diseño además de la comercial — `normativa/` no es un índice, es un **motor de resolución determinista** con esquemas JSON, ocho pasos y geografía española completa. Meterle recuperación difusa por debajo es sustituir lo que ya está bien construido por algo peor.

**La arquitectura, en cuatro piezas:**

1. **Corpus de registro:** YAML en git, validado por `jsonschema` (ya construido), revisado por un colegiado. El diff es legible por quien no programa — por eso se eligió YAML y sigue siendo correcto.
2. **Pipeline de extracción como asistente del curador, nunca como autor.** `extraccion/` + `ingesta/` proponen una entrada candidata con el **fragmento literal** y su fuente (BOE, `codigotecnico.org`); una persona aprueba. Ningún candidato entra al corpus sin firma humana. Esto ya existe, y hay que preservar su naturaleza al industrializarlo.
3. **Recuperación, sí, pero acotada:** Postgres full-text + `pgvector` **sobre el corpus curado**, no sobre PDF crudos. Dos usos legítimos: que el arquitecto vea el articulado que respalda un hallazgo, y que el curador encuentre lo ya transcrito antes de duplicarlo.
4. **La regla dura:** una cifra en un entregable solo puede venir del corpus o de la geometría. Si el corpus no la tiene → `UNKNOWN` con motivo. **Esto ya es lo que `normativa/api.py` hace hoy correctamente**, y es el comportamiento que hay que proteger con un test, no una mejora pendiente.

**Lo que hay que decir con incomodidad.** El corpus está vacío y ninguna decisión de este documento lo llena. Es C5, es el camino crítico, y es una contratación —un arquitecto colegiado transcribiendo—, no un sprint. Si de esta auditoría sale una sola acción, que sea esa: **es la línea de presupuesto con mejor retorno del proyecto**, y todo lo demás de este documento vale menos sin ella.

---

## 10. MCP: canal de distribución, no funcionalidad

**Decisión (sí).** Exponer el registro de capacidades como servidor MCP, **inmediatamente después** de que el registro exista y no antes.

Es casi gratis: el manifiesto ya genera tres consumidores (§7), y MCP es el cuarto con la misma declaración. Y estratégicamente es lo más rentable por línea de código del documento: es cómo ArchMuse entra en Claude Desktop, en Cursor, y en la capa agéntica que los fabricantes de BIM acabarán publicando. Encaja exactamente con el reparto de la §2 del documento de alineación —el cerebro es el motor, la superficie es discutible— y es la prueba del plugin ejecutada de verdad, no en una revisión.

**Decisión (no).** ArchMuse no consume servidores MCP externos por ahora. Catastro, BOE y Mapbox son HTTP con clientes que ya existen; envolverlos en MCP añade un salto y un modo de fallo sin ganar nada.

**Restricción de seguridad, no negociable.** El servidor MCP **no** expone capacidades con efecto `io` sin confirmación explícita. Un agente ajeno no escribe ficheros en el proyecto de un cliente ni gasta su presupuesto de tokens porque le pareció razonable. El campo `efectos` del manifiesto es lo que hace esa política comprobable en vez de confiada.

---

## 11. Base de datos: Postgres gestionado, en la UE

**Decisión.** Postgres gestionado (Neon, Supabase o RDS — indiferente; elegir por región y precio). Región **UE, decidida antes que el proveedor**.

**Por qué se sale de SQLite.** No es que SQLite sea malo: la decisión de `storage.py` fue correcta para lo que era. Se sale por cuatro cosas concretas: aislamiento por cliente con RLS, concurrencia real (hoy 8 hilos de `waitress` compitiendo con llamadas de hasta 15 minutos), recuperación a un punto en el tiempo en un producto cuyo valor es la defensibilidad de un registro, y `pgvector` para §9 sin añadir otro sistema.

**Y por qué la migración es barata.** `storage.py` lo documenta él mismo: *"Ningún módulo de `analyzer/` importa este archivo… el sentido de la flecha es siempre app.py → storage"*. Hay un único escritor. Se conserva su interfaz y se cambia el driver.

**Dirección del esquema:**

| Tabla | Papel |
|---|---|
| `tenants`, `users`, `memberships` | Estudio, personas, rol |
| `projects` | Metadatos, `tenant_id` |
| `graph_versions` | **Append-only.** Grafo serializado + `sello_sha256` + versión del motor + versión del corpus. Nunca se actualiza una fila |
| `runs`, `run_steps` | Plan, paso, capacidad+versión, duración, tokens, coste, veredicto |
| `artifacts` | Clave en almacenamiento de objetos + tipo + qué versión del grafo lo produjo |
| `studio_prefs` | La memoria de estudio de §8 |
| `corpus_versions` | Qué corpus estaba vigente cuando se emitió un análisis |

**`graph_versions` append-only es la decisión de la que depende que el producto se pueda vender**, y merece decirse aquí en vez de en §17: es lo que permite responder, dos años después, "esto se dijo con este dato, esta regla en esta versión y este corpus". `sellado_de()` ya existe. Lo que falta es que su resultado viva en una tabla que nadie pueda sobreescribir.

**Ficheros fuera de la base.** DXF, PDF, IFC, GLB a S3/R2 con URL firmada. Hoy `pliegos.pdf` es un BLOB — funciona con un usuario en un portátil y no sobrevive a veinte estudios.

---

## 12. Autenticación: comprada, no construida

**Decisión.** IdP gestionado con organizaciones, invitaciones y roles: **Clerk** (más rápido de integrar con Next) o **WorkOS** (mejor camino a SSO empresarial). Cualquiera de los dos antes que construirla.

Construir autenticación en Flask son tres semanas mal invertidas: registro, verificación de correo, recuperación de contraseña, invitaciones, rotación de sesión, MFA. Nada de eso diferencia a ArchMuse, y todo es un incidente de seguridad esperando. Esas tres semanas van al corpus.

**Roles, derivados del negocio y no del framework:**

| Rol | Puede |
|---|---|
| Propietario | Facturación, miembros, borrar proyectos |
| Arquitecto | Crear y ejecutar, exportar, confirmar hipótesis (`SUPUESTO` → `DECLARADO`) |
| Colaborador | Ejecutar, no confirmar hipótesis |
| **Lectura (promotor / inversor)** | Ver hallazgos, acta y coste estimado. Nada más |

El último rol no es un extra de permisos: es el segundo comprador que `MOAT_ANALYSIS.md` identifica — el promotor que necesita cuantificar riesgo antes de comprometer capital. Un rol de lectura monetizable es la forma más barata de abrir ese canal.

**Restricción de dos capas.** La autorización vive **también** en el núcleo Python, no solo en el middleware de Next: `tenant_id` en el contexto de toda capacidad y en toda lectura del grafo, con un test que falle si alguna consulta no lleva predicado de tenant. Confiar el aislamiento a la capa web es exactamente lo que C1 prohíbe: el día que la superficie sea un plugin de Revit, el middleware no está.

---

## 13. Multiusuario: single-DB, RLS, y un "no" explícito

**Decisión.** Una base de datos, un esquema, `tenant_id` en cada fila, Row Level Security de Postgres. No schema-por-cliente (operativamente doloroso a partir de cien estudios), no base-por-cliente.

**Colaboración = versiones selladas, no edición simultánea.** Un proyecto es una secuencia de versiones del grafo con autor y sello. "Quién decidió qué" —que es lo que `NORTH_STAR_2031.md` pide a 12 y 24 meses— sale de ahí gratis.

**El "no" explícito: no se construye edición colaborativa en tiempo real.** Nadie la ha pedido, cuesta un trimestre, y el modelo de valor del producto es un registro auditable de decisiones, que es casi lo contrario de un documento que dos personas editan a la vez.

---

## 14. Despliegue: sacar el producto del portátil

Lo de hoy —`waitress` en `127.0.0.1` más un túnel desde una máquina Windows— es un banco de pruebas, y no se puede vender. Ni por fiabilidad, ni por la conversación de protección de datos que aparece en cada venta a un estudio.

**Decisión, cinco piezas:**

| Pieza | Qué | Por qué |
|---|---|---|
| Núcleo Python | Contenedor Linux en plataforma gestionada (Fly.io o Cloud Run) | En Linux `gunicorn` funciona — `requirements.txt` documenta que se eligió `waitress` porque gunicorn no va en Windows. Deja de ser una restricción |
| **Worker con cola** | Proceso aparte consumiendo trabajos, **no** una petición HTTP | Es el hueco arquitectónico más grande que hay hoy: una llamada de hasta 15 minutos ocupa uno de 8 hilos. **Cola sobre Postgres con `SKIP LOCKED`**, no Redis+Celery: a este volumen, añadir un sistema es peor que usar el que ya tienes |
| Frontend | Next en Vercel o en el mismo Cloud Run | Indiferente. Que no arrastre decisiones del núcleo |
| Ficheros | S3 / R2, URL firmadas | Los BLOB no escalan y no se sirven bien |
| Región y secretos | **UE**, gestor de secretos, no `.env` en disco | Datos de proyecto de arquitectos españoles. Se pregunta en toda venta |

**CI desde el primer día.** GitHub Actions ejecutando la suite completa (~14 minutos hoy). Marcar rápido/lento para que en local se pueda correr lo rápido; en CI se corre todo. Con 24.584 líneas de test, no tenerlas en CI es desperdiciar el activo principal.

**Y una deuda de terceros que hay que cerrar antes de vender:** Nominatim. La instancia pública prohíbe uso intensivo/comercial. Hay que pasar a geocodificación de Mapbox (ya hay token) o a una instancia propia. Overpass necesita caché agresiva y un plan para cuando no responda. Catastro ya tiene reintentos y caché por PRD; ese patrón se extiende a los otros dos.

---

## 15. Costes por usuario: la aritmética, y lo que implica en el precio

**Primero, el hecho incómodo:** hoy esto no se puede medir. `response.usage` no se lee en ningún punto del repositorio. La primera acción de esta sección no es optimizar, es **instrumentar**: registrar `input_tokens`, `output_tokens`, `cache_read_input_tokens` y modelo en cada llamada, en `run_steps`. Hasta que eso exista, todo lo que sigue son estimaciones desde los techos de `max_tokens`.

**Precios vigentes** (Claude API, tarifa por millón de tokens; consultados el 2026-08-18 — verificar antes de comprometerlos en un plan de negocio):

| Modelo | Entrada | Salida |
|---|---:|---:|
| Opus 5 | $5,00 | $25,00 |
| Sonnet 5 | $3,00 ($2,00 promocional hasta 2026-08-31) | $15,00 ($10,00 promocional) |
| Haiku 4.5 | $1,00 | $5,00 |

Lectura de caché ≈ 0,1× la entrada; escritura ≈ 1,25×. Batch API ≈ 50%, asíncrono.

**Coste estimado de un proyecto hoy** (los seis puntos de llamada usan `claude-sonnet-5`):

| Llamada | `max_tokens` salida | Estimación |
|---|---:|---:|
| Diagnóstico experto (`ai_analyst`) | 4.096 | ~$0,12 |
| Generador de planta (`ai_generator`) | 8.192 | ~$0,14 |
| Motor de estilos | 1.024 | ~$0,02 |
| Extractor de pliego | 4.096 | ~$0,15 |
| Entrevista (`claude_interprete`), ~20 turnos | 2.048/turno | **~$0,50-0,80** |

**Total ~$0,90-1,20 por proyecto completo con entrevista**, dominado por la entrevista y por la generación. La caché de prompt ya está puesta en los seis, y es lo único que hoy contiene el coste.

**Con orquestador, cinco palancas en orden de rentabilidad:**

1. **Caché determinista por `(versión de capacidad, sello del grafo de entrada)`.** Las capacidades `determinista` son reproducibles por definición, así que un acierto de caché es gratis **y correcto**. Es la palanca más grande y no cuesta calidad.
2. **Escalonado de modelo.** Haiku 4.5 para clasificación y extracción estructurada (con `tool_choice` forzado, la tarea es de forma, no de criterio); Sonnet 5 para redacción; Opus 5 solo para el planificador, y solo si se mide que Sonnet planifica peor. Nunca Opus en el camino caliente por defecto.
3. **Presupuesto del plan antes de ejecutar** (§6, precisión 2). Se rechaza lo que no cabe, en vez de descubrirlo en la factura.
4. **Batch API para la ingesta de corpus.** No es sensible a latencia: 50% de descuento por no hacer nada.
5. **Caché de prompt sobre los manifiestos**, que son el prefijo estable del planificador. Ojo con el invalidador silencioso: el orden de los manifiestos tiene que ser determinista, o la caché no acierta nunca.

**La implicación de negocio, que es el motivo real de esta sección.** Con esa aritmética, un asiento de €49/mes con generación ilimitada es un riesgo: un usuario intensivo puede consumirlo en llamadas. Y no hace falta: la parte **valiosa** —verificación normativa, geometría, cuadro de superficies, acta— es determinista y casi gratis; la parte **cara** —generar plantas, redactar prosa— es la de menos foso (`MOAT_ANALYSIS.md` ya lo dice del generador). Por tanto:

> **Asiento por arquitecto con verificación ilimitada, y generación/redacción medida en creaciones por mes.** Alinea el precio con el valor (defensa profesional) y el coste con la parte medida.

Y una ventaja estructural que conviene saber vender: **cada regla determinista que se añade mejora el margen**, porque sustituye trabajo que un competidor puramente LLM paga por token. La economía unitaria mejora con el uso. Eso es un argumento de inversor, no solo de ingeniero.

**Infraestructura,** para cerrar el número: Postgres gestionado + un contenedor + un worker + almacenamiento de objetos ≈ €50-150/mes hasta bien entrados los primeros clientes, más los tiles de Mapbox, que sí escalan con uso y hay que vigilar. A veinte estudios eso es ruido frente al coste de LLM. **El coste dominante por usuario es el LLM, y es controlable con las cinco palancas.**

---

## 16. Observabilidad y evaluación: el log de ejecución *es* el producto

**La decisión que cambia el planteamiento.** La observabilidad no se añade como capa: es el mismo dato que el acta de procedencia que C2 convierte en entregable. Una fila por ejecución de capacidad, con capacidad+versión, sello del grafo de entrada, atributos producidos, duración, tokens, coste y veredicto de invariantes. Leída por un ingeniero es una traza; leída por un arquitecto y renderizada, es el acta. **Un dato, dos productos.** Esto es lo que hace que no haga falta el framework de §5.

**Trazas.** OpenTelemetry desde el principio, con exportador intercambiable. Si se quiere visor de spans de LLM, Langfuse autoalojado en la UE; si no, OTel + Grafana. Lo que no debe pasar es que el instrumento sea propiedad de un proveedor que luego condiciona la región.

**Evaluación, partida por `naturaleza` — y esa es la razón de que el campo exista:**

| `naturaleza` | Cómo se prueba | Bloquea release |
|---|---|---|
| `determinista` | Golden obligatorio (G1-G9 ya existen). Misma entrada, misma salida | Sí |
| `llm` | Contrato: forma, `origen` emitido, ausencia de cita fuera del corpus. **Nunca** el texto exacto | Sí (el contrato, no la prosa) |
| `io` | Sobre copia, con sha256 del original antes/después y `audit()` de la copia | Sí |

El patrón de `io` no es nuevo: `tests/test_cuadro_superficies_export.py` ya verifica byte a byte que el DXF original queda intacto y que ninguna celda bloqueada lleva una cifra inventada. **Ese test es el mejor activo cultural del repositorio.** Lo que hay que hacer es elevarlo a requisito de todo exportador.

**La métrica que manda comercialmente: tasa de falsos positivos por regla.** Ya hay `docs/audits/FALSE_POSITIVES.md`. Se mide por regla, se publica internamente, y **bloquea release** si sube. `DESTROY_ARCHMUSE.md` §5.1 explica por qué vale más que cualquier medida de cobertura: un hallazgo falso destruye la confianza en los verdaderos.

**Añadir: regresión contra proyecto real de cliente.** `ARCHMUSE_DXF_V2S` ya inventa el patrón — un plano real fuera del repositorio que habilita ~4 minutos de cobertura extra. Industrializarlo: dos o tres proyectos reales, con permiso, en almacenamiento privado, ejecutados en CI nocturno. Es la única prueba que detecta lo que los fixtures sintéticos no ven.

---

## 17. Qué arquitectura permitiría venderlo de verdad

Hay que empezar por algo que no es una decisión de stack: **lo que hoy impide vender ArchMuse no es la arquitectura, es que el corpus normativo está vacío.** Ninguna de las dieciséis decisiones anteriores mueve esa aguja. Dicho eso, la arquitectura decide si el producto es vendible **cuando** el corpus exista, y hay cuatro propiedades que tiene que hacer baratas.

**1. Un registro que sobreviva a una disputa.** `graph_versions` append-only + versión de capacidad + versión de corpus + sello sha256. Permite responder, dos años después: *este número salió de esta entidad de este fichero, con esta regla en esta versión, contra este corpus.* Eso es lo que un arquitecto enseña a su aseguradora, y no lo tiene nadie. No es una tabla más: es el producto.

**2. Una frontera escrita de lo que NO se comprobó.** Derivada de los `limitaciones` de los manifiestos ejecutados, no redactada a mano. Es el Pilar 2 de `MOAT_ANALYSIS.md` generado por construcción, y es lo contrario de lo que hace cualquier herramienta con IA, que sobrevende. En una venta, decir con precisión qué no sabes es lo que hace creíble lo que sí sabes.

**3. Invocable donde el arquitecto trabaja.** Un núcleo, cuatro transportes: HTTP, MCP, plugin, CLI. Es C1, y su valor comercial es que ArchMuse deja de competir por ser una web mejor —competencia que pierde contra quien tiene la distribución— y pasa a ser el motor al que se le pregunta. La prueba es mecánica: coger una capacidad y contar qué habría que reescribir para llamarla desde Revit. Si no es "solo el invocador", no está vendible.

**4. Equipos y tenencia desde el día uno.** Se vende a estudios. Y meter multi-tenancy después es el refactor más caro que existe, porque toca cada consulta y cada permiso. Es la decisión que hay que tomar antes de tener clientes, precisamente porque no se nota hasta que ya es tarde.

**Y el negativo, igual de importante.** El visor 3D, el percentil comparativo y la generación de plantas demuestran bien y **no venden**: `MOAT_ANALYSIS.md` y `DESTROY_ARCHMUSE.md` coinciden en los tres. La arquitectura tiene que permitir **congelarlos sin romper nada**. Esa es otra razón de la frontera de capacidades: convierte "congelar una funcionalidad" en una decisión de una línea del registro, en vez de en un refactor.

---

## 18. Esqueleto de fases (entrada para el plan de migración, no el plan)

Seis fases. Ninguna deja el producto caído; cada una tiene una prueba de que terminó.

| Fase | Contenido | Terminó cuando |
|---|---|---|
| **F0 · Higiene y medición** | Cerrar Fase 2 del masterplan (golden de tipología/zona). CI con la suite. Telemetría de tokens y coste. Sacar Jarvis, logs y venvs del árbol. Sustituir Nominatim | La suite corre en CI y hay una cifra real de coste por proyecto |
| **F1 · El grafo gobierna** | `modelo/` portante. `api_serializer` serializa el grafo. Invertir `classify_problems`. Postgres con `graph_versions` append-only | Una sola representación del proyecto, y el `GET` de un proyecto sale del grafo |
| **F2 · Capacidades** | Manifiesto + registro por descubrimiento. Las 38 reglas envueltas en 4-6 capacidades gruesas. Generación de JSON Schema + OpenAPI desde el manifiesto. Transporte a FastAPI | Añadir una capacidad no toca ningún fichero central, y la prueba del plugin pasa |
| **F3 · Orquestador y primer entregable** | Planificador + validador + ejecutor + un ciclo de replanificación. Worker con cola. MVP del cuadro de superficies. **Acta de procedencia** | Un arquitecto pide en lenguaje natural, recibe DXF relleno + acta, y el acta dice qué no se pudo calcular |
| **F4 · Producto vendible** | IdP con organizaciones y roles. RLS. Next + cliente TS generado. Visor envuelto como isla. Despliegue en UE. Precio y medición de generación | Un estudio ajeno se registra, invita a alguien y paga sin que nadie le abra un túnel |
| **F5 · Superficie y alcance** | Servidor MCP. Importador de IFC. Corpus con contenido real. Prueba de concepto de BIM (horizonte de 3 meses del North Star) | Una capacidad se ejecuta desde fuera de la web, y una cifra normativa sale del corpus |

**En paralelo desde F0 y sin depender de nada de esto: la contratación del colegiado para el corpus** (C5). Es el camino crítico real.

**Lo que NO entra en ninguna fase:** ingesta de imágenes, ampliar el visor 3D, memoria justificativa antes de que haya corpus, edición colaborativa en tiempo real, reescribir el visor en React Three Fiber, y perseguir "cientos de capacidades".

**Nota de proceso.** F0 y F1 son endurecimiento y refactorización de lo que ya existe: por `CLAUDE.md` no necesitan PRD nuevo. F2 en adelante introduce capacidades nuevas (orquestador, acta, MCP, importador IFC) y **cada una necesita su PRD aprobado** antes de una línea de código.

---

## 19. Lo que no he verificado

- **No he ejecutado la aplicación.** Todo juicio sobre comportamiento sale del código y de la suite.
- **No he leído `evaluator.py` entero** (3.521 líneas). La afirmación de que las 38 `evaluate_*` son puras y agrupables en 4-6 capacidades viene del ADR y de una lectura parcial; hay que confirmarla función por función antes de F2.
- **No he medido tokens reales.** Las cifras de §15 salen de los techos de `max_tokens` y de longitudes de prompt estimadas, no de facturas. Es exactamente el motivo de que instrumentar sea la primera tarea de F0.
- **No he validado los precios contra la tarifa publicada hoy.** Están consultados a 2026-08-18 e incluyen una promoción de Sonnet 5 que expira el 2026-08-31; verificar antes de meterlos en un plan financiero.
- **No he evaluado proveedores de IdP ni de Postgres en detalle** (precio, región, RGPD, DPA). Las decisiones de §11 y §12 son de categoría, no de proveedor; elegir proveedor es una tarea con su propia comparativa.
- **No he estimado plazos ni euros de desarrollo.** Sin conocer la capacidad del equipo, cualquier cifra sería inventada.
- **No he leído los 22 documentos de `docs/brain/`.** Puede haber decisiones cerradas ahí que este documento reabra sin saberlo — sobre todo en §8, porque `PROJECT_MEMORY.md` existe y no lo he leído.
