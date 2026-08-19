# Revisión crítica del stack — hacia un agente profesional 24/7

**Fecha:** 2026-08-18 · **Estado:** propuesta, no aprobada · **Complementa** (no sustituye) a `2026-08-18-auditoria-arquitectura-tecnologica.md`, cuyas 18 decisiones siguen vigentes salvo donde aquí se diga lo contrario.

**Encargo:** revisar cada pieza del stack contra un objetivo nuevo —ArchMuse como copiloto agéntico profesional, no como analizador de plantas con IA— y decidir **mantener / sustituir / introducir / aplazar**, con justificación por capacidad real, mantenimiento, rendimiento, ecosistema, coste y adecuación.

---

## 0. La tabla, y después el porqué de lo que cambia

| Pieza | Hoy | Decisión | Motivo en una línea |
|---|---|---|---|
| UI web | SPA en `static/index.html` (274 líneas) + Jinja | **Sustituir** por Next.js App Router | Ya decidido en la auditoría §3; sigue siendo correcto y no se reabre |
| Framework web núcleo | Flask 3.1 + waitress | **Mantener** (congelado) + **introducir** FastAPI para lo nuevo | Estrangulador: nada se cae, lo nuevo nace tipado y con OpenAPI |
| Lenguaje del núcleo | Python 3.14 | **Mantener** | `ifcopenshell`, `ezdxf`, `shapely` y `trimesh` no tienen equivalente en TS. No es preferencia: es que la mitad del producto no existiría |
| Base de datos | SQLite/ficheros | **Sustituir** por Postgres gestionado (UE) | Auditoría §11. Sin cambios |
| Cola y ejecución | ninguna (todo en la petición HTTP) | **Introducir** cola en Postgres `SKIP LOCKED` **+ checkpoints por paso** | El cambio real de esta revisión: ver §2 |
| Ejecución durable (Temporal/DBOS) | — | **Aplazar**, con criterio de reapertura escrito | §2 |
| Almacenamiento de ficheros | BLOB en base + disco | **Sustituir** por S3/R2 con URL firmada | Auditoría §14 |
| Observabilidad | `logging` + nada | **Mantener** el acta de ejecución como producto + **introducir** OpenTelemetry para lo operativo | §3 |
| Autenticación | ninguna | **Introducir** IdP gestionado (Clerk o WorkOS) | Auditoría §12. Residencia UE, pendiente |
| IFC / BIM | `ifcopenshell` 0.8.5, solo export | **Mantener** la librería, **introducir** la frontera `bim/` | §4 |
| DXF / CAD | `ezdxf` 1.4.4 | **Mantener** | Es el estándar de facto en Python y está probado contra un plano real de cliente |
| Revit | — | **Aplazar**, con la arquitectura ya preparada | §4 |
| Proveedor de LLM | Anthropic, `claude-sonnet-5` incrustado en 6 módulos | **Mantener** el proveedor, **sustituir** el modelo incrustado por configuración | §5 |
| Sistema de Tools | `agente/` (construido hoy) | **Mantener** y ampliar | Manifiesto ejecutable, registro por descubrimiento |
| Sistema de Skills | no existe | **Introducir** | Es el objeto de esta misión. PRD aparte |
| Memoria | no existe | **Introducir** memoria de proyecto; las otras dos se aplazan | §6 |
| Framework de agentes (LangGraph, OpenAI Agents SDK, CrewAI…) | — | **Rechazar**, y por segunda vez | §7 |
| Empaquetado y entorno | `pip` + tres `requirements*.txt` | **Aplazar** `uv` | Ganancia real pero cambia el flujo de todos; decisión humana |
| Validación de manifiestos | `dataclass` + JSON Schema escrito a mano | **Aplazar** `pydantic`, provisional `dataclass` | §8 |

---

## 1. Lo que esta revisión **no** reabre

La auditoría del 2026-08-18 está aprobada y su análisis sigue siendo válido. No se reabre: Next.js frente a React pelado, la frontera Python/TypeScript, Postgres frente a otra base, RLS frente a esquema por cliente, IdP comprado frente a construido, ni la negativa a hacer RAG sobre los PDF del CTE.

Esa última merece una frase, porque el objetivo agéntico la pone a prueba: un copiloto que redacta memorias justificativas parece pedir a gritos un RAG sobre el CTE. **No.** Un agente que cita una cifra normativa recuperada de un PDF por similitud semántica es exactamente el producto que un arquitecto abandona a la primera cifra mal citada. El corpus curado sigue siendo la única fuente admisible de un número; la recuperación puede localizar y **mostrar** articulado, nunca producirlo. Lo que sí cambia es la urgencia del corpus: un copiloto sin corpus tiene una tercera parte de las capacidades que promete.

## 2. El cambio importante: ejecución durable, y por qué no es Temporal

**El problema que aparece con el objetivo nuevo y no existía antes.** Un análisis de planta dura segundos. «Prepárame la memoria justificativa» dura minutos, toca varias Skills, escribe ficheros, puede pararse a **pedir aprobación a un humano** y tiene que sobrevivir a que el proceso se reinicie mientras espera. Eso es ejecución durable, y la cola con `SELECT ... FOR UPDATE SKIP LOCKED` de la auditoría §14 no lo cubre: reparte trabajos, no reanuda uno a mitad.

**Las tres opciones reales, evaluadas:**

| Opción | Qué da | Qué cuesta | Veredicto |
|---|---|---|---|
| **Temporal** | Reanudación exacta, reintentos, señales, timers, esperas humanas de días | Un clúster más (o Temporal Cloud), un modelo de programación con determinismo obligatorio en los workflows, y una dependencia de la que no se sale | **Aplazar** |
| **DBOS** | Durabilidad sobre el Postgres que ya habrá, decoradores, sin clúster nuevo | Proyecto joven; el bloqueo es menor pero real | **Aplazar**, y es el primer candidato si hace falta |
| **Checkpoints propios en Postgres** | Cada paso del plan se persiste antes y después de ejecutarse; reanudar es releer la tabla | Hay que escribirlo (~1 jornada) y no da timers ni esperas de días | **Introducir ahora** |

**Decisión: checkpoints propios.** El motivo no es evitar dependencias por deporte, es que **las capacidades deterministas son idempotentes por contrato** —está en el manifiesto y hay tests que lo comprueban—, y con idempotencia la reanudación se reduce a «¿qué pasos ya tienen resultado sellado?». Eso son doscientas líneas contra un sistema entero. Temporal resuelve el caso difícil (esperas de días, sagas, compensaciones) que ArchMuse no tiene todavía.

**Criterio de reapertura, escrito para que no se decida por inercia:** se adopta ejecución durable de terceros cuando ocurra la primera de estas tres — (a) un flujo necesite esperar una acción humana durante más de 24 h, (b) haya que compensar efectos ya aplicados a un fichero del cliente, o (c) los checkpoints propios pasen de 500 líneas.

**Ya implementado esta noche:** el ejecutor persiste el estado paso a paso y una ejecución interrumpida se reanuda sin repetir lo hecho (`agente/ejecucion.py`). El sustrato de hoy es el sistema de ficheros; cambiar a Postgres es sustituir una clase, no el diseño.

## 3. Observabilidad: dos cosas distintas, y confundirlas cuesta el foso

- **El acta de procedencia** —qué capacidad produjo cada dato, con qué entrada, qué versión y qué no comprobó— **es producto**, no telemetría. Se guarda con el proyecto, se le enseña al cliente y es la mitad del argumento de venta. No vive en un proveedor de observabilidad.
- **La traza operativa** —latencia, tokens, errores, coste— es telemetría. **Introducir OpenTelemetry** cuando entre FastAPI: es el estándar de 2026, no ata a ningún proveedor y `ia/uso.py` ya mide lo caro (coste por llamada y por llamante).

Mantenerlas separadas es lo que impide el fallo clásico: enseñarle a un arquitecto un volcado de trazas y llamarlo transparencia.

## 4. BIM: la frontera importa más que la librería

`ifcopenshell` 0.8.5 ya está en `requirements.txt` y `analyzer/ifc_export.py` exporta. **Mantener.** No hay alternativa seria en Python y su ecosistema es el que usa la industria.

Lo que **se introduce** es una frontera: `bim/` como adaptador entre IFC y el grafo de `modelo/`, en las dos direcciones, con IFC tratado como **formato de intercambio y nunca como modelo interno**. El motivo es concreto y ya se puede anticipar: Revit no habla IFC nativo, habla su API .NET; un `RevitDocument` y un `IfcFile` solo tienen en común lo que el grafo ya sabe representar. Si la lógica de dominio se escribe contra `ifcopenshell`, el día que entre Revit hay que reescribirla; si se escribe contra el grafo, entra un adaptador más.

**Revit se aplaza**, y la preparación correcta no es código Revit: es (a) que ninguna capacidad importe transporte —ya hay un test que lo vigila—, (b) que el registro de capacidades se pueda exponer por MCP, y (c) la frontera `bim/`. Con esas tres, un complemento de Revit es un cliente más.

## 5. Modelos de lenguaje: el proveedor se mantiene, el modelo sale del código

`claude-sonnet-5` está escrito literalmente en seis módulos. Eso no es una decisión de proveedor, es una constante duplicada seis veces: cambiar de modelo hoy es un `grep`, y elegir un modelo distinto por tarea (barato para clasificar, caro para planificar) es imposible sin tocar código.

**Decisión:** el proveedor se mantiene —Anthropic, con el patrón de `tool_choice` forzado que este repositorio ya usa bien— y **el modelo pasa a configuración por perfil de tarea**. Abstraer el proveedor entero se **aplaza**: una capa de compatibilidad multiproveedor escrita antes de tener un segundo proveedor real siempre acaba siendo el mínimo común denominador, y el uso de herramientas es justo donde más difieren.

## 6. Memoria: se introduce una de las tres

La auditoría §8 distingue tres memorias. Con el objetivo agéntico, el orden de necesidad queda claro:

1. **Memoria de proyecto** (requisitos del cliente, decisiones tomadas, restricciones declaradas, hechos observados) — **introducir ahora**. Sin ella, «mejora este proyecto respetando estas restricciones» es imposible: el agente no sabe cuáles son.
2. **Memoria de ejecución** (qué se hizo, con qué versión) — **introducir ahora**, porque es el acta y los checkpoints, que ya hacían falta por otro motivo.
3. **Memoria semántica del estudio** (cómo trabaja este despacho, sus criterios, sus soluciones tipo) — **aplazar**. Es el foso a tres años y no se puede construir sin proyectos reales dentro.

Ninguna de las tres es un almacén de vectores, y la primera menos que ninguna: un requisito del cliente se recupera por identidad y por proyecto, no por parecido.

## 7. Frameworks de agentes: no, otra vez, y ahora con más motivo

El objetivo nuevo —Skills, planificación, verificación, aprobación humana— es exactamente lo que LangGraph vende. Merece una respuesta seria y no un reflejo.

Lo que LangGraph o el SDK de agentes de OpenAI aportarían: un grafo de estados, reanudación, y un ecosistema de integraciones. Lo que costarían: un modelo de ejecución ajeno en el centro del producto, una dependencia que versiona rápido bajo los pies, y —lo decisivo— **integraciones genéricas donde ArchMuse necesita lo contrario**. El valor de este producto no está en encadenar llamadas: está en el manifiesto de capacidades con `requiere`, en la procedencia epistémica de cada dato, en el portero de invariantes y en el acta. Nada de eso lo da un framework, y todo eso hay que escribirlo igual encima.

El bucle completo —con Skills, verificación, aprobación y reanudación— cabe en la escala que la auditoría estimó. **Se confirma la negativa.**

## 8. Dos aplazamientos que son decisión humana, no técnica

- **`pydantic` para los manifiestos.** Generaría el JSON Schema de herramienta, la operación OpenAPI y la validación desde una sola declaración — que es exactamente lo que pide V1-5. Entra gratis con FastAPI. Se aplaza a ese momento para no meter hoy una dependencia que el stack actual no tiene; provisionalmente, `dataclass` con el esquema escrito a mano, que es reversible.
- **`uv` en lugar de `pip`.** Es más rápido y más determinista, y el repositorio ya tiene un `.lock`. Cambia el flujo de trabajo de quien contribuya: decisión de Pablo, anotada en `decisiones-pendientes.md`.

## 9. Lo que esta revisión deja sin verificar

No he medido rendimiento de nada de lo que propongo, no he probado Postgres ni el IdP, y las cifras de coste siguen siendo las de la auditoría §15. La frontera `bim/` está razonada pero no construida: hoy solo existe como regla de dependencia, no como código.
