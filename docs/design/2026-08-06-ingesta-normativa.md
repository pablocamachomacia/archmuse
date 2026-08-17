# Ingesta de normativa oficial — diseño y estado de entrega

**Fecha:** 2026-08-06 · **Alcance:** pipeline de ingesta, no el corpus ni el
motor de resolución (`normativa/`, ya entregado en Fases 0-1). Documento
corto a propósito — Pablo pidió parar la serie de documentos de arquitectura.

## 0. Auditoría en una tabla

| Ya existe | Qué aporta a este pipeline |
|---|---|
| `normativa/modelo.py` — `NormaFuente`, `ReglaNormativa`, `Vigencia` bitemporal | El formato de destino. Este pipeline no inventa un esquema nuevo: produce candidatos que, aprobados, se transcriben a este mismo formato |
| `normativa/esquema/regla.schema.json` + `normativa/validacion.py` (17 validaciones) | El filtro de calidad que ya existe. Un candidato aprobado pasa por aquí exactamente igual que una regla escrita a mano — no se le exime |
| `docs/design/NORMATIVE_ENGINE.md` §12 — "regla de dos personas" | **La norma no negociable que gobierna todo este diseño**: ninguna regla evaluable entra en producción sin que un arquitecto colegiado valide que su condición representa lo que el artículo dice. Este pipeline no la relaja — la sirve mejor, dándole candidatos ya extraídos en vez de que transcriba desde cero |
| `docs/design/TRACEABILITY.md` | El principio de "traza persistida, nunca recalculada" se reutiliza para el propio pipeline: cada descarga queda registrada, nunca se regenera en silencio |
| `normativa/loader.py` — fail-closed, `.indice.sqlite` gitignored como caché regenerable | El precedente exacto que este diseño copia para el almacén de descargas (§3) |
| `docs/prd/2026-08-06-motor-de-normativa-territorial.md` tarea 18 | Sigue bloqueada — sigue exigiendo colegiado. Este pipeline no la evita, la alimenta |

**No se ha vuelto a leer la serie `docs/brain/`** (20 documentos) para este diseño: la pregunta que resuelve este documento — cómo entra un documento oficial al sistema — no está contestada allí y no hacía falta revisarla entera para confirmarlo.

## 1. La decisión que ordena todo lo demás

**Nada de lo que descarga o genera este pipeline es visible para `normativa_aplicable()` hasta que un humano lo promueve.**

`normativa/loader.py` descubre y carga cualquier YAML válido que encuentre bajo `normativa/es/`. Si este pipeline escribiera ahí directamente, un texto mal extraído por un LLM empezaría a regir proyectos reales en cuanto pasara el JSON Schema — que valida forma, no verdad. Sería exactamente el error que la "regla de dos personas" existe para impedir, solo que automatizado.

Por eso el pipeline vive en un paquete nuevo, `ingesta/`, que **no escribe nunca dentro de `normativa/`**. Produce candidatos en su propio almacén; la promoción a `normativa/es/...` es un paso humano, manual, deliberadamente fuera del alcance de este pipeline (igual que la transcripción real de la tarea 18).

```
BOE (u otra fuente)
      │  descarga + detección de cambios          ← FASE 1, entregada hoy
      ▼
ingesta/estado/   (documentos oficiales versionados, fuera de normativa/)
      │  extracción de artículos                  ← Fase 2, no entregada
      ▼
      │  conversión asistida por IA → candidatos   ← Fase 3, no entregada
      ▼
ingesta/candidatos/  (ReglaCandidata, confianza, sin efecto en el resolver)
      │  cola de revisión humana (colegiado)       ← Fase 4, no entregada
      ▼
normativa/es/.../*.yaml   (promoción manual, mismas 17 validaciones de siempre)
```

## 2. Las fases, y por qué la primera es la única que se implementa hoy

| Fase | Contenido | Riesgo si se adelanta |
|---|---|---|
| **1 — Conexión y descarga** | Conector por fuente, listar publicaciones, descargar documento, detectar cambios por hash, guardar versionado con metadatos y trazabilidad hasta la URL oficial | Ninguno: no toca el corpus, no cuesta tokens de IA, es determinista y probable contra la API real |
| 2 — Extracción de artículos | Segmentar el texto de un documento en artículos/apartados localizables | Los documentos legales varían de estructura (Ley ≠ Real Decreto ≠ Orden); hacerlo mal silenciosamente es peor que no hacerlo |
| 3 — Conversión por IA | Cada artículo → borrador de `ReglaNormativa` (patrón, condiciones, parámetro) | Es donde vive el riesgo real: un LLM interpretando texto legal. Necesita la cola de revisión (fase 4) lista *antes*, no después |
| 4 — Revisión humana | Cola de candidatos, ordenada por confianza, con aprobación/rechazo explícitos | — |
| 5 — Promoción | Candidato aprobado → fichero en `normativa/`, mismas 17 validaciones | Reutiliza infraestructura ya validada; no hay diseño nuevo que hacer aquí |

Se implementa solo la Fase 1, tal y como se pidió. Las fases 2-5 se han dejado definidas (arriba) para que la Fase 1 se construya con la forma correcta desde el principio, no para adelantar su código.

## 3. Fase 1 — decisiones concretas

### 3.1 Fuente elegida: BOE, por su API de datos abiertos real

Verificado contra el servicio real (no documentación de memoria):

- Sumario diario: `GET https://www.boe.es/datosabiertos/api/boe/sumario/{AAAAMMDD}` (`Accept: application/json`). Devuelve, por sección/departamento/epígrafe, cada publicación del día con su `identificador` (`BOE-A-2026-17003`) y sus URLs en PDF/HTML/XML.
- Documento individual: `GET https://www.boe.es/diario_boe/xml.php?id={identificador}` → metadatos estructurados (`rango`, `departamento`, `numero_oficial`, `fecha_publicacion`, `url_eli`, `fecha_actualizacion`) que mapean casi 1:1 con `normativa.modelo.Fuente`.
- Un día sin boletín (festivo) no es un error: `status.code` distinto de `"200"` se trata como "sin publicaciones", nunca como fallo de red.
- **Trampa real encontrada al inspeccionar una respuesta real, no al leer documentación**: la respuesta del BOE es JSON generado desde XML por PHP, así que **cualquier campo que podría repetirse sale como `dict` cuando hay uno solo y como `list` cuando hay varios** (`diario`, `seccion`, `departamento`, `epigrafe`, `item`, los cinco). Además, `epigrafe` cuelga unas veces de `departamento.texto.epigrafe` y otras directamente de `departamento.epigrafe`, según la sección — verificado comparando la sección "I. Disposiciones generales" contra "II.A Nombramientos" del mismo sumario real. Un parser que asuma una sola forma pierde items en silencio. `ingesta/fuentes/boe.py` normaliza los cinco niveles con un único helper (`_como_lista`) y prueba ambas formas de `epigrafe` con datos reales grabados como fixture, no inventados.

Por qué BOE y no Comunidad de Madrid o un ayuntamiento primero: es la única de las tres fuentes que Pablo mencionó con una **API de datos abiertos documentada y estable**, en vez de HTML pensado para lectura humana. Es también la cima de la jerarquía competencial ya modelada (`normativa/esquema/competencias.yaml`): el CTE, que ya está citado en el esquema de materias, sale de aquí. BOCM y los ayuntamientos son la extensión natural, no el punto de partida — y son, además, los que `docs/design/NORMATIVE_ENGINE.md` §12 ya señaló como "el coste fijo por ciudad, permanente".

### 3.2 Extensibilidad: una interfaz, no una promesa

`ingesta/fuentes/base.py` define `FuenteOficial` (ABC) con dos métodos: `listar_sumario(fecha)` y `descargar_documento(item)`. `pipeline.py` y `almacen.py` no importan `boe.py` en ningún sitio — reciben cualquier `FuenteOficial` como parámetro. Añadir BOCM el día que haga falta es escribir `fuentes/bocm.py` implementando la misma interfaz; nada en `pipeline.py` ni `almacen.py` cambia. Es el mismo patrón de frontera que ya usa `normativa/registro.py` (resolver por ámbito, sin que el resolver sepa de municipios concretos).

### 3.3 Detección de cambios y versionado: mismo principio que el índice SQLite de `normativa/`

`normativa/.indice.sqlite` ya está gitignored con el argumento "es caché, se regenera, la fuente de verdad es otra". Aquí se aplica el mismo principio, pero con el BOE como fuente de verdad en vez de git:

- `ingesta/estado/ledger.jsonl` — **versionado en git**. Una línea por cada vez que se descarga un documento: `identificador`, hash del texto, `hash_anterior`, estado (`nuevo` / `sin_cambios` / `modificado`), y la fecha en que ArchMuse lo vio. Pequeño, legible, es la traza de "qué sabíamos y cuándo" — el eje de registro de `NORMATIVE_ENGINE.md` §4.1, aplicado al pipeline en vez de al corpus.
- `ingesta/estado/cache/` — **gitignored**. El XML crudo de cada versión distinta descargada (nunca se sobrescribe: `{identificador}__{hash[:12]}.xml`). Se puede borrar y volver a descargar del BOE en cualquier momento porque el BOE mantiene acceso permanente a sus documentos (identificadores ELI persistentes) — es la misma razón por la que el índice SQLite es desechable.
- Un documento nunca visto → `nuevo`. Mismo hash que la última vez → `sin_cambios` (no se vuelve a guardar el crudo). Hash distinto → `modificado`, se guarda como versión nueva sin tocar la anterior.

### 3.4 Qué NO hace la Fase 1, explícitamente

- No extrae artículos ni genera ninguna `ReglaNormativa`. Guarda el documento completo con sus metadatos oficiales; segmentarlo en artículos es la Fase 2.
- No llama a ningún modelo de IA. Cero coste, cero riesgo de alucinación todavía.
- No descarga masivamente. Los tests corren contra fixtures grabados (deterministas, sin red); la demostración contra el servicio real se limita a un día concreto y al propio CTE (`BOE-A-2006-5515`) por su identificador — no un barrido histórico.
- No mapea el vocabulario de `rango` del BOE (p. ej. código `1340` = "Real Decreto", pero también existen decenas de rangos como "Corrección de errores" que no tienen equivalente directo en el enum cerrado de `regla.schema.json`) al catálogo cerrado de la Fase 0. Esa traducción es responsabilidad de la Fase 5 (promoción), con criterio del Curador — automatizarla ahora sería inventar una tabla de equivalencias sin que nadie la haya pedido.

## 4. Confianza — una escala distinta de `nivel_de_conocimiento`, a propósito

El encargo pide "asignar un nivel de confianza a cada regla" y "marcar para revisión humana las de baja confianza". Esto **no** es lo mismo que `nivel_de_conocimiento` (1-4) del esquema ya existente, y conviene no confundirlos cuando llegue la Fase 3:

- `nivel_de_conocimiento` es una propiedad de la **regla ya aceptada**: la asigna el Curador y describe la naturaleza del conocimiento (1 hecho objetivo … 4 criterio). Vive en `ReglaNormativa`.
- La confianza de extracción es una propiedad del **borrador, antes de existir como regla**: qué tan bien el proceso automático cree haber entendido un artículo. Nunca debe escribirse en `nivel_de_conocimiento` — sería que una máquina se autoevalúe con la misma escala reservada al juicio de un colegiado.

Por eso, cuando llegue la Fase 3, la confianza vivirá en una entidad propia (`ReglaCandidata`, no `ReglaNormativa`) y será cualitativa (Alta/Media/Baja), nunca un porcentaje — la misma disciplina que ya se aplicó en `docs/brain/INFERENCE_ENGINE.md` frente a la tentación de una probabilidad numérica visible. Y, siguiendo la "regla de dos personas": **la confianza ordena la cola de revisión, nunca decide saltársela.** Un candidato de confianza Alta se revisa antes; ninguno se promueve sin que un colegiado lo apruebe, sea cual sea su confianza. Esto se deja escrito aquí porque es la decisión de diseño que evita que la Fase 3, cuando se construya, erosione silenciosamente la única norma no negociable del corpus.

## 5. Integración: qué no se rompe

- `evaluator.py` — no se toca, no se importa desde `ingesta/`.
- `normativa/` — no se toca. `ingesta/` no lo importa (mismo tipo de frontera de sentido único que ya protege `test_normativa_fronteras.py`; se añade `test_ingesta_fronteras.py`, con las cuatro direcciones prohibidas: ninguno de los tres paquetes importa a los otros dos sin autorización, y ninguno referencia en código — no en docstring — una ruta del otro).
- El corpus real sigue vacío tras esta entrega. `normativa_aplicable()` sigue bloqueando con `CoberturaInsuficiente` exactamente igual que ayer.

## 6. Estado de entrega (2026-08-06)

Implementado `ingesta/` completo para la Fase 1: `modelo.py`, `errores.py`,
`red.py` (HTTP mínimo, sin dependencias nuevas), `fuentes/base.py` (contrato
`FuenteOficial`), `fuentes/boe.py` (conector real) y `almacen.py` +
`pipeline.py` (versionado, detección de cambios, orquestación).

**Verificado contra el servicio real, no solo contra fixtures**: ingesta
directa del CTE (`BOE-A-2006-5515`) por identificador, reingesta del mismo
documento (→ `sin_cambios`, no duplica caché) e ingesta de un día real
completo (5 de agosto de 2026: 194 items en el sumario, 193 filtrados por no
ser "I. Disposiciones generales", 1 descargado). `ingesta/estado/ledger.jsonl`
se deja con una entrada real y mínima (el CTE) como evidencia intencional, no
como semilla de datos — sigue sin haber ningún candidato de regla ni ninguna
promoción al corpus.

29 tests nuevos (`test_ingesta_boe.py`: 20, incluida una prueba opcional
contra `boe.es` en vivo tras `ARCHMUSE_TEST_RED=1`; `test_ingesta_fronteras.py`:
4), deterministas contra fixtures reales grabados
(`tests/fixtures/boe/BOE-A-2006-5515.xml` es el CTE real completo;
`sumario-20260805.json` es un recorte real, no inventado, que conserva las dos
formas estructurales distintas que el BOE usa según la sección). Regresión:
sin cambios en el resto de la suite — el único fallo preexistente
(`test_scoring_coherencia.py`) sigue siendo la misma decisión abierta de
siempre. `evaluator.py` y `normativa/` sin tocar.

**Limitaciones, ninguna oculta** (repetidas de §3.4 para quien lea solo esta
sección): no extrae artículos, no llama a IA, no mapea `rango` del BOE al
enum cerrado del esquema de reglas, no ha corrido contra ningún rango de
fechas amplio ni contra otra fuente distinta de BOE. Todas son la Fase 1 tal
y como se pidió — el punto de partida bien diseñado, no el pipeline entero.
