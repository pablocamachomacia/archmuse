# PRD — E2: el modelo arquitectónico común se persiste

**Estado:** Borrador · **Fecha:** 2026-08-11 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

Diseño de referencia: [`docs/design/2026-08-11-modelo-arquitectonico-comun.md`](../design/2026-08-11-modelo-arquitectonico-comun.md) §18 (etapa E2)
Contrato heredado: [`docs/prd/2026-08-11-e0-modelo-arquitectonico.md`](2026-08-11-e0-modelo-arquitectonico.md) (C1–C8, I1–I8)
Registro de E1: [`docs/design/2026-08-11-e1-implementacion.md`](../design/2026-08-11-e1-implementacion.md)

> **Por qué este documento existe antes de tocar código.** `CLAUDE.md` exige un PRD aprobado para toda capacidad
> nueva de producto, y E2 lo es: cambia el esquema de `storage.py`, añade una tabla o columna nueva y modifica
> cómo `/api/analizar` construye y reutiliza el modelo. E0 y E1 siguieron el mismo patrón —diseño → PRD → aprobación
> → implementación— y no hay razón para saltárselo aquí. Este PRD estudia `storage.py` y el flujo completo antes de
> proponer nada, tal y como se pidió.

---

## 0. Lo que se midió antes de proponer nada

**`storage.py` hoy** (`analyzer/storage.py`): SQLite de la stdlib, una tabla `proyectos`, un blob `payload` (el JSON
completo que devuelve `/api/analizar` o `/api/generar`). `guardar_proyecto()` genera el id (uuid4 hex-12, nunca
derivado de la entrada del usuario), inyecta `proyecto_id` en el payload y lo inserta. `obtener_proyecto()` devuelve
ese mismo blob, byte a byte, sin volver a parsear el DXF ni volver a evaluar reglas. **No guarda el modelo.** Guarda
el informe — exactamente el diagnóstico 16.1 del documento de diseño, sin resolver todavía.

**El flujo completo, medido, no supuesto:**

```
POST /api/analizar
  └─ leer_plano(doc)                              1 lectura del DXF
       └─ evaluate_advanced(rooms, unit_labels…)  agrupa por VT, corre ~40 reglas
            └─ evaluate_circulation(unit_score)   llamado 2 VECES por vivienda:
                 ├─ api_serializer.py:330          (serializar circulación)
                 └─ chain_effects.py:159            (efectos en cadena)
                      └─ _build_adjacency_graph(unit)
                           └─ modelo_compat.grafo_de_adyacencia(unit)
                                └─ constructor.construir_de_unidad(unit)   ← RECONSTRUYE
                                     el modelo entero para esa vivienda: identidad,
                                     geometría, invariantes I1-I8, sellado.
  └─ serialize_analysis(...)                       arma el payload de presentación
  └─ guardar_proyecto(payload)                     INSERT, payload tal cual
```

Sobre `ejemplo.dxf` (6 viviendas) esto es **12 construcciones completas del modelo por análisis** — dos por
vivienda, cada una repitiendo sellado e invariantes desde cero. E1 ya lo dejó escrito como deuda pendiente
(§5 de `2026-08-11-e1-implementacion.md`: *"conviene no repetirlo por regla cuando migren más consumidores"*).
Con `/api/analizar` sirviendo un único DXF y 6 viviendas la latencia no se nota (goldens: +8%), pero es la prueba
concreta —no hipotética— de por qué el objetivo 2 de E2 ("construir el modelo una sola vez por análisis") es un
requisito real y no una aspiración.

**Lo que NO existe hoy y bloquea a los cuatro consumidores futuros (editor, 3D, generador, documentación):** el
modelo se construye y se tira. `obtener_proyecto()` devuelve geometría de presentación (`api_serializer` ya la
re-coloca por el layout del SVG — diagnóstico 16.4), nunca la geometría real ni el grafo de nodos/aristas. Reabrir
un proyecto hoy es "ver el informe otra vez", no "recuperar el proyecto".

---

## 1. Problema que resuelve

`modelo/` (E1) sabe construirse, validarse y serializarse de forma determinista (C7), pero vive y muere dentro de
una petición HTTP. No hay manera de:

1. Recuperar el grafo de un proyecto ya analizado sin volver a subir el DXF.
2. Evitar que el mismo análisis construya el modelo doce veces.
3. Darle a un futuro consumidor (editor, 3D, generador) algo más que el JSON de presentación.

## 2. Usuario afectado

Directo: **ninguno todavía** — igual que E0 y E1, E2 es infraestructura. Indirecto: el arquitecto que reabre un
proyecto guardado, que hoy ve el informe pero no tiene, detrás, nada sobre lo que construir un editor o un 3D real.

## 3. Objetivo de negocio

Desbloquear E3/E4/E5 (ensamblaje, muros, editor) sin comprometerlos: son imposibles mientras el proyecto no exista
como objeto persistente (diagnóstico 16.1). E2 es barata porque no inventa esquema nuevo — extiende el que ya
existe — y es la única etapa entre E1 y "el producto puede prometer reabrir y recalcular", que es un hito de
`NORTH_STAR_2031.md`.

## 4. Objetivo técnico

Al terminar E2 debe ser cierto que:

1. `guardar_proyecto()` persiste, además del payload actual, el modelo serializado (C7) del análisis que lo generó.
2. `obtener_modelo(proyecto_id)` devuelve un `modelo.Grafo` reconstruido, sellado, idéntico al que se construyó en
   el análisis original (mismo `sellado`, comprobado por test).
3. `/api/analizar` construye el modelo **una sola vez**; los consumidores que ya lo usan (circulation) lo
   reutilizan en vez de reconstruirlo.
4. Proyectos guardados **antes** de E2 (payload sin columna `modelo`, o con `modelo` a `NULL`) se siguen abriendo
   exactamente igual que hoy — `obtener_proyecto()` no cambia de forma. `obtener_modelo()` de un proyecto antiguo
   devuelve `None`, explícitamente, nunca un error.
5. Nada de lo anterior cambia un solo resultado normativo, de scoring, ni el payload de `/api/analizar` byte a
   byte (salvo el campo nuevo que E2 añade explícitamente, ver C-E2.4).
6. G1–G9 y K1–K4 siguen en verde. La suite completa sigue en 55 OK / 1 fallo conocido.

## 5. Casos de uso

**CU-1 — Reabrir sin recalcular.** Un arquitecto reabre un proyecto de la parrilla del Inicio. `GET
/api/proyectos/<id>` sigue devolviendo el informe de siempre (sin cambios). Un futuro `GET
/api/proyectos/<id>/modelo` (fuera de alcance de E2 como endpoint HTTP — ver §9 — pero ya posible internamente)
podría devolver el grafo real.

**CU-2 — Un análisis, un modelo.** Con 6 viviendas, `/api/analizar` construye el modelo del proyecto una vez, no
doce. Medible con un contador de invocaciones a `constructor.construir*` durante un análisis (test E2 dedicado).

**CU-3 — Proyecto antiguo, sin ruptura.** Una fila de `proyectos` creada por E1 o antes (sin columna `modelo`, tras
la migración con el valor a `NULL`) se abre, se lista y se borra exactamente igual. `obtener_modelo()` sobre ella
devuelve `None` sin lanzar excepción.

## 6. Casos límite

| Caso | Comportamiento exigido |
|---|---|
| Fila anterior a E2 (columna `modelo` no existía) | Migración `ALTER TABLE` la añade como `NULL`; `obtener_modelo()` devuelve `None` |
| Proyecto `origen="generado"` (sin DXF, `ai_generator`) | E2 **no** migra `/api/generar`. La columna `modelo` queda `NULL` para estos — documentado, no un fallo (ver §9, "no forzar migración") |
| El modelo no puede reconstruirse (JSON corrupto a mano) | `obtener_modelo()` devuelve `None`, mismo criterio que `obtener_proyecto()` con un payload corrupto — nunca propaga la excepción |
| Dos peticiones concurrentes a `/api/analizar` | Cada una construye su propio modelo (sin estado compartido entre peticiones) — el cacheo de E2 es **por análisis**, no un caché de proceso |
| `ARCHMUSE_DATA_DIR` apuntando a una base ya en `SCHEMA_VERSION=1` | `init_db()` migra en el arranque, de forma idempotente, sin borrar filas existentes |

## 7. Flujo del usuario

Sin flujo de usuario final nuevo — `/api/analizar` y `/api/proyectos/<id>` no cambian su contrato HTTP visible,
salvo el campo nuevo de C-E2.4. El flujo interno pasa de "modelo se construye y se tira" a "modelo se construye,
se reutiliza dentro de la petición, se guarda".

## 8. Criterios de aceptación

- **B1.** `proyectos` tiene columna `modelo` (TEXT, nullable). Migración idempotente, verificada sobre una base
  ya existente con filas de antes de E2.
- **B2.** `guardar_proyecto()` acepta el grafo del análisis (parámetro opcional, `None` por defecto — proyectos
  generados y cualquier llamador que no lo tenga siguen funcionando) y lo serializa con `modelo.serializacion.volcar`.
- **B3.** `obtener_modelo(proyecto_id) -> Optional[modelo.Grafo]` reconstruye con `serializacion.cargar` y su
  `sellado` coincide exactamente con el que tenía en el momento de guardar (test round-trip contra la base real).
- **B4.** `/api/analizar` construye el modelo una vez y lo reutiliza en `circulation` — medido, no supuesto, con un
  contador de construcciones (antes: 12 sobre `ejemplo.dxf`; después: 1).
- **B5.** El payload de `/api/analizar` es idéntico al de antes de E2, salvo el campo nuevo `proyecto.modelo_id`
  (ver C-E2.4) — comprobado por G6 y por un diff explícito payload-antes/payload-después.
- **B6.** G1–G9, K1–K4, suite completa (55 OK / 1 fallo conocido), CAP-1…CAP-5, circulation: todos en verde,
  igual que al cierre de E1.
- **B7.** Tests nuevos de E2 (persistencia, round-trip, determinismo, identidad, reconstrucción, aislamiento entre
  proyectos, compatibilidad hacia atrás, construcción única) — todos en verde.
- **B8.** `git diff` fuera de los ficheros listados en §10 está vacío.

## 9. Riesgos

1. **Que E2 se convierta en "reescribir storage.py".** *Mitigación:* B1–B2 son una columna y un parámetro
   opcional, no un esquema nuevo. El diseño (§18) habla de tablas nuevas a largo plazo (event-sourcing de
   versiones) — **eso no es E2**, es una etapa posterior que necesita el emparejamiento (`identidad.emparejar()`,
   todavía `NotImplementedError`) para tener sentido. Persistir una versión sin poder emparejarla con la anterior
   es una tabla vacía de significado.
2. **Que migrar `circulation` para reutilizar el modelo rompa el orden de vecinos** (que E1 demostró que decide
   los empates). *Mitigación:* mismo criterio de neutralidad medida que E1 — antes/después con `ejemplo.dxf`,
   comprobado por test, no supuesto.
3. **Que `/api/generar` (proyectos sin DXF) se quede sin modelo y eso se lea como una regresión.** No lo es: hoy
   tampoco lo tiene. `modelo/constructor.py` sólo sabe construir desde `PlanoLeido` (DXF). Construir un modelo
   desde `ai_generator.project` es un adaptador distinto, de otro tamaño, y forzarlo en E2 mezclaría B1/B2/B3
   (prohibido explícitamente). Se documenta como deuda, no se implementa.
4. **Migrar un segundo consumidor "porque ya se puede".** El propio encargo lo prohíbe ("no fuerces una migración
   solo para aumentar el número de módulos migrados"). E2 propone migrar exactamente uno más allá de circulation
   —ninguno— y se justifica por qué en §11.

## 10. Impacto sobre módulos existentes

**Modificados:**

```
analyzer/storage.py     +columna modelo, +guardar_proyecto(grafo=None), +obtener_modelo()
analyzer/circulation.py  _build_adjacency_graph reutiliza un grafo ya construido si se le pasa
app.py                   construye el grafo una vez tras leer_plano(), lo pasa a guardar_proyecto()
                          y al mecanismo de reutilización de circulation
```

**Nuevos:**

```
modelo/persistencia.py   (o el nombre que decida la implementación) — capa fina que envuelve
                          serializacion.volcar/cargar para el formato de fila de storage.py,
                          si hace falta separarlo de storage.py mismo (decisión abierta, §12)
tests/test_e2_persistencia.py
tests/test_e2_construccion_unica.py
```

**NO tocados:** `hechos.py`, CAP-1…CAP-5, `parser.py`, `evaluator.py` (salvo cero — no aparece en la lista de
arriba), `plan_svg.py`, `spatial_quality.py`, `ai_generator.py`, `api_serializer.py`, `normativa/`, `ingesta/`,
`extraccion/`, `experimentos/`, `static/`.

## 11. Decisiones esenciales que este PRD cierra

Cuatro decisiones que faltaban y que la implementación necesita resueltas antes de escribir una línea. Todas
siguen el criterio del encargo: **el cambio mínimo que persiste el modelo sin reescribir `storage.py`.**

### C-E2.1 — Esquema: una columna, no una tabla nueva

`storage.py` gana `ALTER TABLE proyectos ADD COLUMN modelo TEXT` (nullable), migrado en `init_db()` comprobando
`PRAGMA table_info(proyectos)` antes de intentar añadirla (idempotente, no rompe una base ya migrada).
`SCHEMA_VERSION` sube a `2`.

**Por qué no la tabla `version_modelo` que sugiere el diseño (§18):** esa tabla tiene sentido cuando existen
*varias* versiones de un proyecto que emparejar entre sí — es decir, cuando `identidad.emparejar()` deje de
lanzar `NotImplementedError`. Hoy cada `guardar_proyecto()` crea una fila nueva sin relación con ninguna anterior
(no hay endpoint de "reanalizar"). Una tabla de versiones sin emparejamiento es infraestructura sin función:
guardaría una lista de un elemento. Se deja escrito como el primer paso de una etapa posterior, no de E2.

### C-E2.2 — Identidad: sin semilla, `concept_id` nuevo en cada análisis

El grafo se construye **sin** `semilla` (`constructor.construir(plano, fichero=filename)`, tal como hoy en
producción no-test). `concept_id` sale aleatorio (uuid4), igual que ya especifica C1 del contrato E0 para cuando
no hay versión anterior con la que emparejar. El `proyecto_id` que genera `storage.py` (uuid4 hex-12) **no se usa
como semilla del modelo** — mezclar los dos ids violaría la frontera ya establecida en `storage.py`
("los identificadores se generan aquí, nunca se derivan de la entrada del usuario... ningún módulo de `analyzer/`
importa este archivo") y además no aportaría nada: sin `emparejar()` implementado, sembrar la identidad no cambia
qué se puede reconstruir, sólo maquillaría un determinismo que no existe todavía.

### C-E2.3 — Construcción única: memoización acotada a la petición, sin tocar `evaluator.py`

`app.py` construye `grafo = constructor.construir(plano, fichero=filename)` **una vez**, inmediatamente después de
`leer_plano()`. Para que `circulation.py` deje de reconstruir por vivienda (12 veces → 1 por peticón, ya no 12),
`modelo/compat.py` gana una memoización interna: un `dict` que asocia `id(unit)` → grafo de adyacencia, con
limpieza automática por `weakref` cuando el objeto `Unit` deja de tener referencias (no un `lru_cache` ingenuo por
`id()`, que arriesgaría colisión si un `id()` se reutiliza tras recolectarse un objeto en un proceso de larga
vida — riesgo real en el servidor Flask, que no muere entre peticiones).

Esto **no** cambia la firma de `evaluate_circulation()`, `api_serializer.py` ni `chain_effects.py`: los dos
llamadores actuales le pasan el mismo objeto `Unit` (referencia compartida dentro de `advanced.unit_scores`), así
que la memoización por identidad de objeto colapsa las dos llamadas por vivienda a una sola construcción real, sin
tocar ningún fichero más allá de `circulation.py` (ya tocado en E1) y `modelo/compat.py`.

**Por qué no threading un `Grafo` explícito por toda la cadena de llamadas:** exigiría un parámetro nuevo en
`evaluate_circulation`, `serialize_unit_circulation` (`api_serializer.py`) y en `chain_effects.py` — tres ficheros
más tocados para el mismo resultado medible. La memoización por identidad de objeto es el cambio mínimo que
cumple el objetivo 2 sin ampliar la superficie de E2. Si en una etapa posterior el grafo del proyecto necesita
viajar explícito (por ejemplo, para que el editor lo edite en vivo), se revisita esta decisión — documentado como
deuda en §13, no resuelto aquí por decisión, no por olvido.

### C-E2.4 — Qué campo nuevo aparece en el payload público

`serialize_analysis()` no cambia. `guardar_proyecto()` añade `payload["proyecto"]["modelo_id"] = None` — en
realidad no hace falta ni ese campo: **no se añade ningún campo nuevo al payload público en E2.** El modelo se
guarda en su propia columna, no dentro del payload JSON ya existente, así que `/api/analizar` devuelve exactamente
lo mismo que devuelve hoy. B5 se reformula: **el payload de E2 es byte a byte idéntico al de antes de E2**, sin
excepción. Es una garantía más fuerte y más fácil de comprobar que la que abría este apartado, y es la que se
implementa.

## 12. Plan de implementación dividido en pequeñas tareas

Diez tareas, ninguna de más de 2h. Orden: primero persistencia (no depende de nada más), luego construcción única
(depende de tener algo que reutilizar), última la migración de `circulation`.

| # | Tarea | Entregable | Tests |
|---|---|---|---|
| **E2.1** | `storage.py`: migración `ALTER TABLE ADD COLUMN modelo`, idempotente, `SCHEMA_VERSION=2` | migración verificada sobre una base con filas de antes de E2 | nuevo |
| **E2.2** | `storage.guardar_proyecto(payload, origen, grafo=None)`: si `grafo` no es `None`, guarda `serializacion.volcar(grafo)` en la columna nueva | fila con y sin modelo, ambas válidas | nuevo |
| **E2.3** | `storage.obtener_modelo(proyecto_id) -> Optional[Grafo]`: `serializacion.cargar` sobre la columna; `None` si no existe, no es válida, o el proyecto no existe | round-trip: `sellado` antes = `sellado` después | nuevo |
| **E2.4** | `app.py`: construir `grafo = constructor.construir(plano, fichero=filename)` una vez tras `leer_plano()`; pasarlo a `guardar_proyecto` | el payload no cambia ni un byte; la fila nueva tiene columna `modelo` no nula | G1–G9, nuevo |
| **E2.5** | `modelo/compat.py`: memoización de `grafo_de_adyacencia` por identidad de objeto (`Unit` → grafo), con limpieza por `weakref` | mismo grafo, mismo `sellado`, una sola construcción medida por unidad en vez de dos | nuevo, K1–K4 |
| **E2.6** | Confirmar `circulation.py` sigue devolviendo lo mismo con la memoización activa | G4 sin cambios | G4, test_modelo_compat |
| **E2.7** | Test E2: aislamiento entre proyectos — dos análisis consecutivos (`ejemplo.dxf` dos veces) no comparten memoización ni fila | dos filas, dos modelos, `concept_id` distintos entre sí | nuevo |
| **E2.8** | Test E2: compatibilidad hacia atrás — abrir una fila creada antes de E2.1 (columna `modelo` ausente en la fila, `NULL` tras migrar) | `obtener_proyecto` igual que siempre; `obtener_modelo` devuelve `None` | nuevo |
| **E2.9** | Test E2: determinismo — mismo DXF, dos análisis, mismos nodos/aristas/geometría (el `concept_id` cambia por diseño, C-E2.2 — no se compara) | comparación campo a campo salvo `concept_id` | nuevo |
| **E2.10** | Documentar en `docs/design/2026-08-11-e2-implementacion.md` lo realmente construido y cualquier desviación, con la misma estructura que E1 (decisión original / problema / solución / impacto / compatibilidad) | documento de registro | — |

## 13. Plan de pruebas

Además de la tabla de arriba: ejecutar G1–G9, K1–K4, suite completa (runner real del repo), CAP-1…CAP-5,
circulation — exactamente la batería que cerró E1 — al final de E2.10, no sólo al final de cada tarea. El baseline
esperado es el mismo: **55 OK / 1 fallo conocido** (`test_scoring_coherencia.py`). Cualquier cambio de resultado
existente se investiga antes de seguir, no se documenta como "esperado" sin más.

## 14. Métricas para medir el éxito

1. **Construcciones del modelo por análisis** sobre `ejemplo.dxf`: 12 → 1. Medible con un contador simple en los
   tests de E2.7/E2.9.
2. **Filas de `proyectos` con columna `modelo` no nula** tras un análisis nuevo: 100% de los `origen="dxf"`, 0% de
   los `origen="generado"` (documentado, no un fallo).
3. **Regresiones de comportamiento**: 0, en las mismas ocho verificaciones que cerraron E1.

## 15. Posibles motivos para NO implementar la idea

1. **Nadie pide reabrir y editar un proyecto todavía.** Cierto — no hay editor. Pero sin este paso, cuando exista
   la petición, la respuesta seguirá siendo "hay que volver a analizar el DXF", que es precisamente el límite que
   E2 existe para levantar antes de que alguien lo pida en producción.
2. **Podría esperarse a tener el emparejamiento (`identidad.emparejar()`) resuelto y hacer las dos cosas juntas.**
   Se decide explícitamente NO: emparejar necesita datos de proyectos reales reabiertos dos veces, que hoy no
   existen. Persistir primero, sin emparejar, dejando la interfaz declarada (igual que E1 dejó `emparejar()`
   lanzando `NotImplementedError` a propósito) es la secuencia de menor riesgo.
3. **La alternativa: migrar `spatial_quality.py` o `plan_svg.py` en la misma etapa**, ya que el diseño los marca de
   riesgo bajo (§15.2). Se decide explícitamente NO, por la regla del propio encargo: no forzar una migración para
   sumar módulos. Ninguno de los dos necesita el modelo persistido para funcionar hoy, y migrarlos sin necesidad
   real amplía la superficie de E2 sin desbloquear nada nuevo.

---

## Lo que E2 NO resuelve, dicho por su nombre

- **Emparejamiento entre versiones** (`identidad.emparejar()`): sigue lanzando `NotImplementedError`. E2 persiste
  una versión; comparar dos es una etapa posterior.
- **`/api/generar` sin modelo**: los proyectos generados por IA siguen sin `modelo/` — necesitan un constructor
  distinto (`Unit` → `Grafo` sin DXF de origen), no forzado aquí.
- **Endpoint HTTP para el modelo** (`GET /api/proyectos/<id>/modelo`): E2 deja `obtener_modelo()` disponible
  internamente; publicarlo por HTTP es decisión de producto de una etapa que sí tenga quien lo consuma (editor).
- **Migración de `spatial_quality.py`, `plan_svg.py`, `api_serializer.py`, `ai_generator.py`**: siguen con su
  propio criterio de agrupación/geometría, documentado como pendiente, igual que al cierre de E1.
- **Tabla de versiones / event-sourcing** (`version_modelo` del diseño §18): necesita emparejamiento primero.

---

**Decisión:** _pendiente de revisión por Pablo_
