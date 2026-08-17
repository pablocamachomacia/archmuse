# Contrato de integración Entrevistador → Generador

**Fecha:** 2026-08-12 · **Tipo:** diseño técnico, sin implementación · **Estado:** para decisión
**Etapa:** 0.4 del rediseño del generador — continúa `docs/prd/2026-08-12-entrevistador-generador.md` v2.

**Precondición ya decidida por Pablo:** se aprueba construir la extensión mínima del generador propuesta en
`§30` del PRD v2 (`contexto_cualitativo`). Este documento **no da esa aprobación por buena sin más** — la
sección 4 la audita, encuentra que el mecanismo tal como quedó descrito en el PRD (un único string de texto
libre) es insuficiente, y propone una versión más precisa que sigue siendo, en coste y alcance, la misma
"extensión mínima" aprobada — no un rediseño de `ai_generator.py`.

**Ninguna línea de código se ha escrito o modificado para producir este documento.** No hay commit.

**Grounding.** Releído contra el código real: `analyzer/ai_generator.py` completo (`SYSTEM_PROMPT`,
`_build_user_message`, `place_rooms`, `_validate_unit`, `generate_project`), `app.py:550-768`
(`_parse_generar_params`, `generar()`), `analyzer/evaluator.py` (`evaluate_bathroom_accessibility` línea 912,
`evaluate_accessible_bathroom_area` línea 2051, `evaluate_advanced_for_units` línea 2745),
`analyzer/api_serializer.py:227-386`, `analyzer/storage.py` completo (patrón de columna opcional ya usado por
`modelo`/E2). Toda afirmación sobre "qué hace hoy el código" está verificada contra estas lecturas, no asumida.

---

## 1. Estado

Documento de diseño técnico. Nada autorizado a implementarse todavía — eso es una decisión posterior de
Pablo, condicionada a que las decisiones pendientes de §15 queden resueltas.

## 2. Objetivo

Diseñar, con precisión de implementación (aunque sin implementar), cómo la Especificación Arquitectónica del
entrevistador (PRD v2 §22) llega al generador actual sin que la mayoría de lo que recoge se pierda — que es
exactamente el defecto que la auditoría de v1 encontró y que el PRD v2 dejó como análisis pendiente de
aprobación (§30). La aprobación ya llegó; este documento es el diseño técnico que la hace real sin
comprometer tres cosas no negociables del encargo: **coste de API, compatibilidad hacia atrás, y la separación
de responsabilidades entre quién decide, quién interpreta, quién calcula y quién valida.**

## 3. Arquitectura actual

```
static/app.js:renderGenerarForm()
        │  POST /api/generar  { proyecto, solar, edificio, mix_viviendas, normativa }
        ▼
app.py:_parse_generar_params()      — valida y normaliza el JSON de entrada
        │
        ▼
app.py:generar()
        │
        ▼
ai_generator.generate_project(params)
        │
        ├─ _call_claude(client, params, model)
        │      SYSTEM_PROMPT (fijo, ~100 líneas de reglas)
        │      + _build_user_message(params)  ← vuelca proyecto/solar/edificio/mix/normativa como JSON
        │      → 1 llamada a claude-sonnet-4-6
        │      → _extract_json(texto) → {justificacion, plantas:[{viviendas:[{habitaciones:[...]}]}]}
        │
        ├─ _parse_generated_units(data) → List[Unit]
        │
        ├─ place_rooms(habitaciones)     — determinista: coloca cada habitación por zonas (sur/pasillo/norte)
        │
        └─ _validate_unit(unit)          — determinista: solapes, adyacencia baño/pasillo, dormitorio↔pasillo
               │  si >50% de viviendas fallan → UN reintento completo de _call_claude
               ▼
        GeneratedProject(units, rooms, justificacion, advertencias)
        │
        ▼
app.py:generar()  — evaluate_advanced_for_units(), urbanismo de edificio, energía
        │
        ▼
api_serializer.serialize_analysis()  — mismo contrato JSON que /api/analizar
        │
        ▼
storage.guardar_proyecto(payload, origen="generado")
        │
        ▼
static/app.js:renderWorkspace() → viewer-edificio.js (3D) / plan_svg.py (2D, ya en el payload)
```

**El único punto donde interviene la IA es la llamada única de `_call_claude`.** Todo lo demás —colocación
geométrica, validación, evaluación normativa, serialización, persistencia, render— es determinista y no se
toca en este diseño. `/api/analizar` no pasa por ninguno de estos módulos de generación: usa
`analyzer/ai_analyst.py`, un fichero distinto, sin solapamiento — se confirma explícitamente en §13.

**El punto exacto de inserción** de la Especificación Arquitectónica es la entrada de `generate_project()`: el
`params` dict que hoy recibe gana, como muy pronto, una clave nueva y opcional. No se toca la firma pública, no
se toca `place_rooms`, no se toca `_validate_unit` salvo la extensión descrita en §12.

## 4. Auditoría del mecanismo aprobado — ¿es `contexto_cualitativo` como texto libre suficiente?

**No, tal como lo dejó el PRD v2 §30.** Cuatro problemas concretos:

1. **Un único string opaco no distingue restricción de preferencia.** El PRD v2 §17 ya clasificaba
   accesibilidad como "decisión B, prioridad alta, por tener una consecuencia negativa ya medible en
   `evaluator.py`" y carácter/referencias estéticas como la de "mayor incertidumbre de interpretación". Meter
   ambas en el mismo bloque de prosa, sin marcar cuál es casi-obligatoria y cuál es genuinamente libre,
   hace que Claude las trate con el mismo peso — exactamente el riesgo que el encargo pide evitar
   explícitamente ("Claude puede interpretar una preferencia" ≠ "Claude debe diseñar libremente").
2. **No hay forma de verificar, ni de detectar, que una directiva no tuvo ningún efecto.** Un texto libre
   anexado al prompt puede ser ignorado por Claude sin que nada en el sistema se entere — el propio encargo lo
   nombra como el riesgo central a evitar.
3. **Conflicto no resuelto con las reglas fijas de `SYSTEM_PROMPT`.** El prompt ya obliga, por defecto, a que
   "el salón/cocina y el dormitorio principal miren preferentemente a sur/sureste" — si un usuario declara una
   preferencia distinta como no-negociable, el diseño de v2 no dice qué prevalece. Sin una regla de precedencia
   explícita, Claude arbitra el conflicto por su cuenta y en silencio — otra vez, justo lo que no queremos.
4. **Coste de tokens no nulo, aunque coste de llamadas sí lo sea.** Un bloque de texto libre sin estructura
   tiende a crecer con el tiempo (cada categoría nueva añade más prosa) sin ningún mecanismo que lo acote — no
   es un problema de *llamadas* (§11), pero sí de tamaño de prompt por llamada.

**Lo que se mantiene del §30 del PRD:** el principio de "un solo campo nuevo, string, anexado al mensaje, sin
tocar `SYSTEM_PROMPT`" era demasiado simple. La corrección de este documento (§5-§8) sigue siendo una extensión
mínima —cero cambios en `place_rooms`, cero cambios en la lógica de reglas del prompt existente, cero llamadas
nuevas— pero con la estructura interna necesaria para que la prosa que llega a Claude ya venga clasificada.

## 5. Arquitectura propuesta

```
Especificación Arquitectónica (PRD v2 §22)
        │
        ▼
Compilador de Directivas Cualitativas   ← NUEVO, determinista, sin IA (§8)
        │  produce una lista de DirectivaCualitativa (§6) + el texto ya redactado
        ▼
params["contexto_cualitativo"] = {
    directivas: [ DirectivaCualitativa, ... ],   ← se conserva para trazabilidad (§10), NO se envía tal cual
    texto_prompt: str                             ← esto es lo único que entra en el prompt (§8.2)
}
        │
        ▼
ai_generator._build_user_message(params)   ← EXTENDIDA: si existe contexto_cualitativo, añade una sección
        │                                      nueva y delimitada al mensaje (§8.2), nunca dentro del JSON de datos
        ▼
ai_generator.SYSTEM_PROMPT   ← EXTENDIDO con UN párrafo fijo nuevo (§8.1): la regla de precedencia y el
        │                       aviso de que las directivas marcadas "dura" son casi-obligatorias
        ▼
_call_claude()   — SIGUE SIENDO UNA LLAMADA (§11)
        │
        ▼
_parse_generated_units() + place_rooms() + _validate_unit()   ← SIN CAMBIOS
        │
        ▼
Verificación determinista de directivas "dura" verificables geométricamente  ← NUEVA (§12), reutiliza
        │                                                                       evaluator.py, sin llamar a Claude
        ▼
GeneratedProject(units, rooms, justificacion, advertencias)
        advertencias ← EXTENDIDA: además de errores geométricos, incluye directivas "dura" no verificadas
```

## 6. Esquema de datos

### 6.1 `DirectivaCualitativa` — la unidad nueva

```
DirectivaCualitativa
├── especificacion_id            id del CampoEspecificacion (PRD v2 §22.2) del que proviene
├── categoria                     no_negociable | privacidad | accesibilidad | caracter | relacion_espacial
├── fuerza                        dura | blanda
│                                  — dura: accesibilidad, no-negociables declarados explícitamente
│                                  — blanda: privacidad, carácter, referencias, relaciones espaciales suaves
├── texto_origen                  resumen de lo que dijo el usuario (para trazabilidad, §10)
├── texto_prompt                  la frase ya redactada, en el registro imperativo que corresponde a `fuerza`
│                                  (dura → "DEBES:"; blanda → "Si es posible, intenta:")
└── verificable_geometricamente   bool — true solo para accesibilidad hoy (§12); el resto no tiene chequeo
                                    determinista posible con el código actual
```

`fuerza` es el campo que el PRD v2 no tenía y que resuelve el problema 1 de §4: es una propiedad del dato, no
una decisión que tome Claude al leer el texto.

### 6.2 `contexto_cualitativo` — lo que de verdad recibe `ai_generator.py`

```
ContextoCualitativo
├── directivas [ DirectivaCualitativa ]   — se conserva server-side para §10, NUNCA se serializa dentro del
│                                           JSON de `datos` que ya construye _build_user_message
└── texto_prompt                          — la compilación determinista de todas las `texto_prompt`,
                                            agrupadas por `fuerza`, en dos bloques con cabecera distinta (§8.2)
```

### 6.3 `TrazaDeGeneracion` — el artefacto de trazabilidad (diseñado, no persistido todavía)

```
TrazaDeGeneracion
├── especificacion_id              de la Especificación completa que originó esta generación
├── directivas_enviadas [ ]        copia de las DirectivaCualitativa realmente incluidas en el prompt
├── respuesta_ia
│   ├── justificacion               texto libre que ya devuelve Claude hoy (`data["justificacion"]`)
│   └── referencias_especificacion  OPCIONAL — lista de especificacion_id que Claude declara haber tenido en
│                                    cuenta, si el esquema de respuesta lo pide (§9) — best-effort, no fiable
│                                    por sí sola, ver §10
└── verificaciones_deterministas [ ]
        { especificacion_id, metodo, resultado: cumple | no_cumple | no_verificable }
```

No se persiste en esta etapa (§10 explica por qué y qué se deja preparado).

## 7. Flujo completo

```
1. Usuario completa la entrevista (o modo experto) → Especificación Arquitectónica (PRD v2 §22)
2. [NUEVO] Compilador de Directivas Cualitativas (determinista, 0 llamadas) produce ContextoCualitativo
3. app.py:generar() construye params, ahora con params["contexto_cualitativo"] si existe
4. ai_generator.generate_project(params) — SIN CAMBIO DE FIRMA
5. _call_claude(): SYSTEM_PROMPT (+1 párrafo fijo) + _build_user_message() (+1 sección nueva)
   → 1 llamada a Claude, exactamente como hoy
6. _parse_generated_units() + place_rooms() + _validate_unit() — SIN CAMBIOS
7. [NUEVO] verificar_directivas_duras(units, directivas) — determinista, reutiliza evaluator.py
   → si alguna directiva "dura" verificable no se cumple, se añade a `advertencias`
   → NO dispara un reintento nuevo; se apoya en el mecanismo de reintento YA EXISTENTE (§11, §12)
8. GeneratedProject → evaluate_advanced_for_units() (evaluator.py, sin cambios)
9. serialize_analysis() — sin cambios en el contrato público (§13)
10. guardar_proyecto() — sin cambios obligatorios; extensión opcional descrita en §10.3
11. Render 2D/3D — sin cambios, consume las mismas Room/Unit de siempre
```

## 8. Contrato Especificación → Generador

### 8.1 Cambio único y fijo en `SYSTEM_PROMPT`

Un párrafo nuevo, añadido una vez, no dinámico por proyecto — establece la regla de precedencia que falta en
v2 (problema 3 de §4):

> *"Si se te proporcionan directivas adicionales marcadas como DEBES cumplir, tienen prioridad sobre las
> preferencias por defecto de este documento (p. ej. orientación preferente del salón), salvo que entren en
> conflicto directo con la normativa o con la nomenclatura obligatoria de habitaciones, que siempre prevalece.
> Las directivas marcadas como preferencia (`intenta`) se aplican solo si son compatibles con todo lo
> anterior."*

Esto fija una jerarquía de tres niveles (normativa/nomenclatura > directiva dura > regla por defecto > directiva
blanda) en vez de dejarla implícita.

### 8.2 Cambio dinámico en `_build_user_message`

Se añade, **después** del bloque JSON de `datos` (nunca mezclado dentro de él — evita el problema de que un
parser o un lector futuro confunda prosa con datos estructurados), una sección con cabecera explícita:

```
DIRECTIVAS ADICIONALES DEL ARQUITECTO QUE ENCARGA EL PROYECTO:

DEBES CUMPLIR:
- <texto_prompt de cada DirectivaCualitativa con fuerza=dura>

PREFERENCIAS DE DISEÑO (aplícalas si son compatibles con lo anterior):
- <texto_prompt de cada DirectivaCualitativa con fuerza=blanda>
```

Si no hay directivas de un tipo, esa sub-sección no se imprime — no se envía una sección vacía.

### 8.3 Tabla de mapeo — cada categoría de la Especificación, dónde aterriza

| Categoría (PRD v2 §1) | ¿Entra en `params` estructurado? | ¿Entra en `contexto_cualitativo`? | `fuerza` |
|---|---|---|---|
| Ciudad, tipología, solar, edificio, mix, normativa | Sí, directo (sin cambios) | No | — |
| Accesibilidad / movilidad reducida | No | **Sí** | **dura** |
| No-negociables (texto libre) | No | **Sí** | **dura** |
| Privacidad | No | **Sí** | blanda |
| Cocina abierta/cerrada | No | **Sí** | blanda |
| Referencias estéticas / carácter | No | **Sí** | blanda |
| Para quién, lo que menos importa, presupuesto, sostenibilidad, exterior propio/interior | No | **No** — quedan como decisión A del PRD v2 (almacenadas, sin efecto todavía) | — |
| Estructura/sistema constructivo | No (solo modo experto) | No | — |

Esta tabla **es** la corrección concreta del hallazgo de v1 ("12 de 15 preguntas sin destino"): baja a 5 las
categorías sin ningún efecto en la generación (frente a las 10 de v1), con una razón explícita por cada una de
por qué no entra todavía (todas ya estaban justificadas como decisión A en el PRD v2 §17 — presupuesto y
sostenibilidad no tienen un hueco natural en un prompt de distribución de habitaciones sin un cambio más
profundo que "anexar texto", que sí sería rediseñar `ai_generator.py`).

## 9. Contrato Generador → resultado

**Extensión opcional del esquema de respuesta que Claude debe producir** (aditiva — si Claude no la incluye,
`_extract_json`/`_parse_generated_units` siguen funcionando exactamente igual que hoy, `.get()` con default):

```json
{
  "justificacion": "...",
  "plantas": [ ... ],
  "referencias_especificacion": ["accesibilidad.requerida", "privacidad.nivel"]
}
```

Este campo es **best-effort, no la fuente de verdad de la trazabilidad** (§10) — un LLM puede olvidar
incluirlo u omitir una referencia real sin que eso sea detectable solo con este campo. Se guarda si viene, se
ignora si no viene; nunca bloquea el flujo.

**`GeneratedProject.advertencias` se reutiliza, no se sustituye:** hoy ya contiene errores de geometría
detectados por `_validate_unit`. Se le añade una segunda fuente — directivas "dura" verificables que no se
cumplieron (§12) — con el mismo formato de string que ya usa (`"{nombre}: {motivo}"`), sin nueva estructura de
datos en el tipo `GeneratedProject`.

## 10. Trazabilidad

Responde directamente a la pregunta pedida: *"¿qué decisión del usuario provocó esta decisión del
generador?"* — con dos canales, deliberadamente redundantes porque ninguno solo es fiable:

**Canal 1 — autoinforme del LLM (`referencias_especificacion`, §9):** rápido, gratis (no añade llamadas), pero
no verificable por sí solo. Útil como pista, nunca como prueba.

**Canal 2 — verificación determinista (§12):** solo cubre lo que es geométricamente comprobable hoy
(accesibilidad), pero es fiable porque no depende de que Claude coopere. Registra `cumple`/`no_cumple`/
`no_verificable` por directiva dura.

**Lo que esto NO cierra**, con la misma honestidad que ya exige el PRD v2 §22.3: no hay trazabilidad hasta "qué
polígono concreto responde a qué directiva" para las directivas blandas (privacidad, carácter) — eso exigiría
que Claude anotara decisión por habitación, lo cual no está pedido en esta etapa por no complicar el esquema de
respuesta más de lo mínimo. Queda como el siguiente escalón natural si `referencias_especificacion` demuestra
ser útil en la práctica.

### 10.3 Qué se deja preparado, sin persistir todavía

`TrazaDeGeneracion` (§6.3) se diseña pero no se guarda en esta etapa. Si en el futuro se decide persistirla, el
patrón ya existe en el propio `storage.py`: la columna `modelo` (E2) es exactamente el precedente —
opcional, `NULL` en filas antiguas, añadida con `ALTER TABLE ... ADD COLUMN` idempotente, nunca dentro de
`payload`. Una columna `traza_generacion` seguiría el mismo patrón. **No se propone implementarlo ahora** —
se deja documentado como el camino de menor fricción cuando haga falta, precisamente para no rediseñar
`storage.py` cuando llegue el momento.

## 11. Control de coste de API

**Cero llamadas nuevas.** El contexto cualitativo se compila de forma determinista (§5, paso 2) y se inserta en
el **mismo** mensaje de la **misma** llamada única de `_call_claude` que ya existe. La verificación de
directivas duras (§12) es determinista, reutiliza funciones ya existentes de `evaluator.py`, y no llama a
Claude en absoluto — se descarta explícitamente la alternativa de "una llamada de auditoría a Claude para
comprobar cumplimiento", que sería la forma obvia y equivocada de resolver el problema 2 de §4 gastando API de
más.

**El único coste real es de tokens de entrada por llamada** (prompt más largo), no de número de llamadas — el
mecanismo de reintento único que ya existe en `generate_project()` (si >50% de viviendas fallan validación
geométrica) se reutiliza tal cual, sin ampliar su presupuesto: el peor caso sigue siendo 2 llamadas, igual que
hoy.

## 12. Validaciones

**Nueva función `verificar_directivas_duras(units, directivas)`**, determinista, junto a `_validate_unit` en
`ai_generator.py`:

- Para cada `DirectivaCualitativa` con `fuerza=dura` y `verificable_geometricamente=true` (hoy, solo
  accesibilidad): reutiliza `evaluator.evaluate_bathroom_accessibility()` / `evaluate_accessible_bathroom_area()`
  sobre las unidades ya generadas — **no duplica esa lógica**, la importa, exactamente como `ai_generator.py`
  ya importa hoy `Unit`/`_normalize` desde `evaluator.py` (mismo sentido de la dependencia, nada nuevo
  arquitectónicamente).
- Si no se cumple: se añade a `advertencias` (§9), **no bloquea la generación** — coherente con el principio ya
  fijado en el PRD v2 (§16, principio 6: "nunca bloquear por un dato opcional"); aquí se extiende a "nunca
  bloquear la generación por un incumplimiento detectado a posteriori", solo advertir con claridad.
- Directivas duras sin verificación geométrica posible (no-negociables de texto libre) quedan marcadas
  `no_verificable` — se muestran igual en el resumen si se decide exponerlo, nunca se presentan como
  verificadas cuando no lo están.

**Decisión pendiente, no resuelta aquí (§15):** si accesibilidad `no_cumple` debería en el futuro disparar el
reintento existente (igual que el fallo geométrico >50%), en vez de solo advertir. Esta versión lo deja como
advertencia por ser el cambio de menor riesgo; escalarlo a reintento es una decisión de producto, no técnica.

## 13. Compatibilidad

| Componente | ¿Se rompe? | Por qué |
|---|---|---|
| `/api/analizar` | No | Usa `ai_analyst.py`, módulo distinto, sin overlap con `ai_generator.py` — verificado en el import de `app.py:21` |
| `/api/generar` | No | `contexto_cualitativo` es una clave opcional nueva en el JSON de entrada; si no llega (el formulario técnico actual no la envía), `params.get("contexto_cualitativo")` es `None` y el flujo es byte a byte el de hoy |
| `evaluator.py` | No | Recibe los mismos `Room`/`Unit`, generados igual que hoy; se le añaden dos *llamadas* nuevas desde `ai_generator.py` (funciones ya existentes), no se le modifica ni una línea |
| `api_serializer.py` | No | `serialize_analysis()` no cambia de firma ni de contrato de salida en esta etapa; una futura exposición de `TrazaDeGeneracion` en el payload sería aditiva, no se propone aquí |
| `storage.py` | No | Sin cambios obligatorios; la extensión de §10.3 es opcional, futura, y sigue el patrón ya usado por la columna `modelo` |
| Visor 2D (`plan_svg.py`) | No | Consume `Room.polygon`, ajeno a cómo se decidió la geometría |
| Visor 3D (`viewer-edificio.js`) | No | Consume `poligono`/`edificio` del payload serializado, sin cambios de forma |

**Compatibilidad durante la transición:** mientras el entrevistador (Etapa 0.4+ de implementación) no exista
todavía, `renderGenerarForm` sigue funcionando exactamente igual, sin enviar `contexto_cualitativo` — este
diseño no obliga a construir el entrevistador y el generador extendido en el mismo cambio.

## 14. Riesgos

- **Claude puede seguir ignorando una directiva "dura" pese al lenguaje imperativo y la regla de precedencia**
  — un LLM no garantiza cumplimiento por instrucción, ni siquiera marcada "DEBES". Mitigado parcialmente por la
  verificación determinista de §12 para accesibilidad; **no mitigado** para no-negociables de texto libre, que
  siguen sin verificación posible — riesgo residual real, no eliminado, y hay que decirlo así.
- **La regla de precedencia de §8.1 es una frase en el prompt, no una garantía de código** — sigue siendo el
  LLM quien la aplica. Es mejor que no tener regla, pero no es una validación dura.
- **Ambigüedad de clasificación `dura`/`blanda`** al construir el compilador: quién decide que "no-negociable"
  siempre es dura y "carácter" siempre es blanda — hoy es una regla fija por categoría (§8.3), simple y
  auditable, pero rígida: un no-negociable trivial ("que tenga terraza") pesa igual que uno crítico
  ("necesito acceso sin escalones") solo por estar en la misma categoría.
- **Crecimiento futuro del catálogo de categorías** sin control — si cada solicitud nueva añade una categoría
  más al compilador, se repite el patrón de deuda que `CONSTRAINT_MODEL.md` §12 ya identificó para otro
  módulo del proyecto (un catálogo cerrado que crece sin gobierno). Mitigación propuesta: tratar las 5
  categorías de §8.3 como un catálogo cerrado hasta que haya evidencia real de necesitar una sexta, misma
  disciplina que ya se exige en `docs/brain/`.
- Este diseño depende de que la Etapa 0.4 de implementación real (el entrevistador en sí) exista para producir
  una Especificación Arquitectónica de la que compilar directivas — sin eso, este contrato no tiene entrada
  real que consumir todavía.

## 15. Decisiones pendientes (de Pablo)

1. **¿Un incumplimiento de accesibilidad detectado por §12 debe disparar el reintento existente, o basta con
   advertir?** Este documento eligió advertir (menor riesgo, coherente con "nunca bloquear"), pero es una
   decisión de producto real, no solo técnica.
2. **¿Se persiste `TrazaDeGeneracion` ya en esta implementación, o se difiere?** §10.3 deja el camino
   preparado pero no lo ejecuta.
3. **¿El catálogo de 5 categorías de directivas (§8.3) se trata como cerrado por defecto** (cualquier
   categoría nueva exige una decisión explícita, no una adición automática), **o se deja abierto a crecer**
   con cada nueva pregunta que se añada a la entrevista?
4. Todas las decisiones pendientes ya listadas en el PRD v2 §32 (alineación con `PRD-001`, prioridad frente a
   `REFACTOR_MASTERPLAN.md`, etc.) siguen abiertas y no las reabre este documento.

## 16. Qué queda preparado para el futuro generador arquitectónico

Cuando `place_rooms()` se sustituya por un generador más sofisticado (motor de reglas/optimización separado de
la generación geométrica, según el propio horizonte de `BRAIN_ARCHITECTURE.md`), esto es lo que se descarta y
lo que sobrevive:

**Se descarta:**
- El mecanismo de entrega como *prosa dentro de un prompt de LLM* (§8.2) — un motor de reglas no "lee" texto
  libre; consumiría las `DirectivaCualitativa` directamente como datos estructurados, sin pasar por
  `texto_prompt` en absoluto.
- La verificación geométrica ad-hoc de §12, ligada a las funciones actuales de `evaluator.py` sobre la
  geometría concreta que produce `place_rooms` — un generador nuevo probablemente valida sus propias
  restricciones de otra forma, más integrada.
- El reintento único heredado de `_validate_unit` como mecanismo de corrección — un motor más sofisticado
  probablemente no necesita "generar todo de nuevo y esperar que salga mejor".

**Sobrevive, y es la razón de peso para construir esto ahora en vez de esperar:**
- **El modelo de datos** — `CampoEspecificacion`, `DirectivaCualitativa` con su `fuerza` dura/blanda, y la
  clasificación por categoría (§6, §8.3) — es independiente de cómo se entregue al generador. Es, de hecho,
  precisamente el contrato de entrada que un futuro motor de reglas necesitaría, ya clasificado y ya separado
  en restricción vs. preferencia — el trabajo más caro de este diseño (decidir qué es negociable y qué no) no
  se tira.
- **El principio de dos canales de trazabilidad** (autoinforme + verificación determinista, §10) — un motor de
  reglas explícito puede hacer el canal determinista mucho más completo que hoy (puede loguear literalmente
  qué regla se activó por qué dato de entrada, sin depender de que un LLM recuerde citarlo) — el diseño de
  `TrazaDeGeneracion` (§6.3) se vuelve *más* fácil de rellenar de forma fiable, no obsoleto.
- **La regla de precedencia de tres niveles** (§8.1: normativa > directiva dura > defecto del sistema >
  directiva blanda) — es una decisión de producto sobre autoridad, no una particularidad del prompt actual;
  un motor de reglas la necesitaría igual, probablemente como una prioridad numérica real en vez de una frase.
- **La separación `params` estructurado vs. directivas cualitativas** (§8.3) sigue siendo la frontera correcta
  incluso si el mecanismo de entrega cambia — lo estructurado seguirá siendo estructurado, lo cualitativo
  seguirá necesitando algún tipo de traducción, sea LLM o motor de reglas.

---

## Tabla final — quién decide qué

| DECISIÓN | ¿LA TOMA EL USUARIO? | ¿LA INTERPRETA CLAUDE? | ¿LA CALCULA EL MOTOR? | ¿LA VALIDA EL EVALUADOR? |
|---|---|---|---|---|
| Número de viviendas | Sí | No | Parcialmente (compilador interpola si la respuesta es una preferencia, PRD v2 §18) | Indirectamente (ocupación/edificabilidad revisan si caben) |
| Mix de viviendas (tamaños) | Sí | No — nunca decide el programa por su cuenta | Sí — interpolación acotada determinista (PRD v2 §18) | No directamente |
| Accesibilidad | Sí (dato imprescindible si aplica) | Parcialmente — traduce la directiva a disposición, pero no decide si aplica | Sí — verificación geométrica determinista (§12) | Sí — `evaluate_bathroom_accessibility`, `evaluate_accessible_bathroom_area` ya existentes |
| Orientación (real de la parcela) | Sí, como hecho declarado | No — nunca decide `norte_grados` | No, solo transmite | Sí — orientación, horas de sol, todo lo que depende de `norte_grados` |
| Privacidad | Sí (preferencia) | Sí — libremente, dentro de una directiva blanda | No hay verificación geométrica hoy | No — no existe regla de privacidad en `evaluator.py` |
| Presupuesto | Sí | No — decisión A, no llega al prompt (§8.3) | No | No |
| Sostenibilidad | Sí (preferencia) | Parcialmente — solo el hint automático por zona climática, no por la preferencia declarada | No | No — evalúa compacidad/orientación estructural, no preferencias declaradas |
| Carácter arquitectónico | Sí (referencias/sensación) | Sí, libremente — es la categoría donde la libertad interpretativa es apropiada | No | No, deliberadamente — es juicio humano final |
| Relaciones entre espacios | Parcialmente (solo cocina abierta/cerrada es editable; el resto son reglas fijas) | Sí, la mayoría, siguiendo `SYSTEM_PROMPT` | Sí — `place_rooms` las materializa en coordenadas | Parcialmente — adyacencia acústica, evacuación revisan algunas a posteriori |
| Superficies | Sí (mínimos por vivienda/solar) | Decide ancho/largo de cada pieza dentro de esos mínimos | Sí — `place_rooms` ajusta proporciones | Sí, extensamente — decenas de reglas de superficie en `evaluator.py` |
| Distribución (layout) | No, salvo relaciones limitadas | Sí, decide la distribución completa | Sí — `place_rooms` la materializa | Sí — circulación, adyacencia, jerarquía espacial |
| Normativa (ocupación/edificabilidad/retranqueos/plantas máx.) | Sí, hoy (declarada; `Hipótesis` si no se sabe, PRD v2 §6.4) | No — nunca decide estos valores | No — no existe motor de normativa municipal | Sí, íntegramente — `evaluate_solar_occupation`, `evaluate_buildability`, `evaluate_max_floors` |
| Geometría final (polígonos/coordenadas) | No | Decide ancho/largo por habitación | Sí — `place_rooms` calcula x/y; `_validate_unit` valida | No decide, solo mide sobre la geometría ya fijada |

---

*Documento de diseño. Ninguna línea de código escrita ni modificada.*
