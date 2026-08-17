# Extracción inteligente del CTE — Fase 2 del pipeline de ingesta

**Fecha:** 2026-08-06 · **Alcance:** paquete nuevo `extraccion/`. No toca
`ingesta/` (Fase 1, cerrada) ni el motor de resolución. Documento corto,
igual que el de la Fase 1 — sigue en pie "no más arquitectura".

## 0. Auditoría de la Fase 1 — un hallazgo real que cambia el diseño

`ingesta.fuentes.boe.FuenteBOE` descarga `BOE-A-2006-5515` (el Real Decreto
314/2006 que aprueba el CTE) y lo guarda entero en `DocumentoOficial.texto_crudo`.
**Verificado inspeccionando ese XML real, no asumido**: contiene la Parte I
del CTE (artículo único, disposiciones, 3 anejos generales) — el propio texto
lo dice: *"(En suplemento aparte se publica la Parte II del Código Técnico de
la Edificación)"*. **La Parte II — los Documentos Básicos (DB-SI, DB-SUA,
DB-HS, DB-HE, DB-HR, DB-SE), donde viven los umbrales numéricos que
`normativa/esquema/materias.yaml` ya modela — no está en el documento que la
Fase 1 ingiere hoy.**

Consecuencia de diseño, no una carencia que se disimula: la extracción contra
el documento real que sí tenemos (BOE-A-2006-5515) produce sobre todo reglas
`definicion`/`procedimental`/`exigencia_cualitativa` — contenido legítimo
(cumplimiento del CTE, contenido del proyecto, documentación de obra) pero no
el tipo `exigencia_cuantitativa` con umbral que el encargo pide ver. Para
probar ESA rama del extractor con material representativo, los tests usan
además un fragmento **explícitamente ficticio**, con el estilo real de un DB
(numeración, unidades, excepción), guardado aparte y marcado igual que
`tests/fixtures/corpus_ficticio/` — nunca como si fuera texto oficial. Traer
el identificador BOE real de un DB concreto es trabajo de una sesión futura
que decida ingerirlo (con `ingerir_documento`, ya construido en la Fase 1;
no hace falta ninguna fuente nueva) — no se hace aquí porque no se pidió y
alargaría esta fase con una decisión de qué DB priorizar que no me toca tomar
por mi cuenta.

## 1. Los dos pasos, y por qué son dos módulos, no uno

| Paso | Determinista | Qué hace |
|---|---|---|
| **Segmentación** | Sí, sin IA | XML crudo → lista de `Segmento` (artículo/anejo, con su capítulo/anejo de contexto y el texto literal completo) |
| **Interpretación** | No, usa IA | Cada `Segmento` evaluable → `ReglaCandidata`, con verificación mecánica y confianza calculada aparte |

Separarlos es lo que permite probar la segmentación entera contra el CTE real
sin gastar un solo token, y permite que la interpretación reciba SIEMPRE el
texto literal completo de un artículo — nunca un resumen previo que ya habría
perdido información antes de que la IA la viera.

## 2. Modelo: `ReglaCandidata`, no `ReglaNormativa`

Igual que se dejó dicho en el diseño de la Fase 1 (§4): la confianza de un
borrador de IA **no es** `nivel_de_conocimiento` (eso lo asigna el Curador
sobre una regla ya aceptada). `ReglaCandidata` es una entidad propia, con
todos los campos pedidos:

`texto_original` (cita literal exacta) · `articulo` / `apartado` / `documento`
· `version` (hash del `DocumentoOficial` de origen) · `fecha` · `url_oficial`
· `organismo` · `nivel_confianza` (Alta/Media/Baja, **nunca un número** —
misma disciplina que `docs/brain/INFERENCE_ENGINE.md`) · `explicacion_interpretacion`
(cómo se llegó del texto a la estructura, no solo el resultado) ·
`condicion_aplicacion` · `parametros` (cubre también "umbrales": un umbral es
un parámetro con comparador) · `excepciones` · `referencias_internas` (cubre
"dependencias": menciones a otros artículos/anejos del mismo documento —
**no** aristas resueltas a `concept_id`, eso es trabajo del Curador en la
promoción) · `severidad` (reutiliza el campo `prioridad` ya existente,
bloqueante/riesgo_variable/recomendable/preferencial — no se inventa una
escala nueva) · `categoria` (reutiliza `materia`, catálogo cerrado de 14) ·
`explicacion_tecnica` · `revisar_manualmente` (bool, mecánico) ·
`motivos_revision` · `señales` (la traza del propio cálculo de confianza).

**`extraccion/` no escribe en `normativa/es/` ni la importa como destino.**
Sí importa, de forma explícita y autorizada, los catálogos cerrados YA
existentes para no reinventarlos: `normativa.modelo` (7 tipos, 5 patrones, 4
prioridades) y `normativa.catalogos.materias()` (14 materias). Es la misma
clase de excepción ya autorizada para `analyzer/cte_zonas.py` — reutilizar un
vocabulario cerrado, no forkearlo — y tiene su propio test de frontera con la
lista exacta de qué puede importar.

## 3. Cómo se evitan las alucinaciones — ocho mecanismos, todos mecánicos

Ninguno depende de que la IA "diga la verdad" sobre sí misma. Todos son
verificaciones que corren en código nuestro, después de la llamada:

1. **Salida forzada a un esquema cerrado** (tool use de la API de Anthropic,
   `tool_choice` forzado). La IA no puede devolver un campo fuera del schema
   ni un `patron` que no sea uno de los 5, ni una `materia` que no sea una de
   las 14 — el enum se lo pasamos nosotros, tomado de `normativa.modelo`, no
   escrito a mano en el prompt.
2. **Cualquier cifra citada debe aparecer, literalmente, en el `texto_original`**
   que se le pasó. Es una comprobación de subcadena, no de la IA — un umbral
   que la IA "recuerda" de otra norma pero que no está en este artículo se
   detecta y tira la confianza a Baja automáticamente.
3. **Coherencia tipo↔patrón**, la misma validación 3 de `normativa/validacion.py`
   reaplicada aquí como señal: un tipo no evaluable (`exigencia_cualitativa`,
   `definicion`, `remision`, `procedimental`) que trae `patron` o `parametro`
   es una contradicción, no una regla candidata de confianza alta.
4. **El modelo declara su propia necesidad de revisión** (`necesita_revision_humana`,
   campo obligatorio del schema) — y esa declaración **nunca puede convivir
   con confianza Alta**, sea cual sea el resto de señales. Es la contradicción
   que `docs/brain/INFERENCE_ENGINE.md` llama "severidad oculta": un hallazgo
   que se dice seguro y a la vez pide que lo revisen es una contradicción, no
   una confianza alta con una nota aparte.
5. **La cita y el resumen viajan separados, siempre los dos** (`texto_original`
   nunca ausente cuando hay `explicacion_interpretacion`) — mismo principio
   de `NORMATIVE_ENGINE.md` §3.4 (`literal` vs `resumen_operativo`): el
   arquitecto que revise ve lo que dice la ley y lo que la IA entendió, nunca
   uno sin el otro.
6. **`temperature=0`** y el modelo/versión de prompt quedan anclados en
   `ReglaCandidata.version` junto al hash del documento fuente — mismo
   principio de "anclajes" de `TRACEABILITY.md` §10.1. Esto **no** hace la
   llamada 100% reproducible bit a bit (ningún LLM lo es) y no se promete que
   lo sea — es una limitación honesta, no oculta.
7. **La confianza es una función determinista nuestra, nunca un número que la
   IA elige.** `extraccion/confianza.py` no llama a ningún modelo: toma las
   señales de los puntos 1-4 y calcula Alta/Media/Baja por una tabla fija —
   se puede probar entera con datos inventados, sin gastar un token, y es lo
   que hace el punto 7 del encargo ("si la confianza no es alta, no
   promover") comprobable con un test, no confiable de palabra.
8. **`revisar_manualmente` es mecánico: `True` siempre que la confianza no
   sea Alta.** No es una decisión de la IA ni una casilla que alguien pueda
   olvidar marcar — se calcula con la confianza, en el mismo sitio.

**Lo que esto NO resuelve, con franqueza**: ninguna de estas ocho
comprobaciones puede detectar que la IA haya entendido bien un artículo
ambiguo cuya interpretación exige criterio jurídico — eso es exactamente lo
que la confianza Media/Baja y la cola de revisión existen para exponer, no
para que el sistema decida en su lugar. Es el mismo riesgo 2 que
`docs/design/NORMATIVE_ENGINE.md` §15 ya nombraba ("interpretación de
artículo ambiguo… es criterio profesional, no un problema técnico") aplicado
a la IA en vez de a un transcriptor humano.

## 4. Qué NO hace esta fase, explícitamente

- No promueve nada a `normativa/es/` — ninguna confianza, ni Alta, activa una
  promoción automática. Pedido así por Pablo y coherente con la "regla de dos
  personas" que ya gobierna el corpus.
- No añade ninguna fuente nueva ni toca `ingesta/`.
- No resuelve `referencias_internas` a `concept_id` reales — no hay ningún
  concept_id todavía, porque no hay ninguna regla promovida.
- No construye la tabla de repliegue completa de un `Parametro` (ejes,
  valores, cadena de repliegue) — captura el valor y el contexto tal como el
  artículo los cita; construir la tabla completa (posiblemente cruzando
  varios artículos y varias comunidades) es criterio del Curador en la
  promoción, no algo que se pueda inferir de un solo artículo aislado.

## 5. Estado de entrega (2026-08-06)

Implementado `extraccion/` completo: `modelo.py` (`Segmento`, `ReglaCandidata`,
`Señales`, `Parametro`), `segmentador.py` (determinista), `verificacion.py`
(las ocho comprobaciones mecánicas), `confianza.py` (la función pura de §3
puntos 5-7), `interprete.py` (la única llamada a un modelo, tool use forzado
contra un schema construido en tiempo de importación desde los catálogos
cerrados reales) y `pipeline.py` (orquesta los cuatro pasos).

**Segmentación verificada contra el CTE real completo**: 28 segmentos (1
artículo único + 9 disposiciones + 15 artículos numerados + 3 anejos),
contados a mano contra el índice real del documento, no estimados.

**Interpretación verificada EN VIVO contra la API real** (no solo mockeada),
con un hallazgo que merece registrarse tal cual salió, no suavizado: los tres
primeros segmentos probados —dos artículos reales (2 y 11) y el segmento
ficticio con excepción— salieron los tres con `necesita_revision_humana: true`
y confianza Baja, con motivos sustantivos y correctos (el artículo 2 acumula
cuatro condiciones cualitativas en su excepción; el 11 es un artículo-paraguas
que remite a seis sub-exigencias no presentes en el texto; el ficticio declara
una "solución alternativa razonable" que exige juicio humano). **No es un
fallo del mecanismo — es el mecanismo funcionando**: son artículos
genuinamente matizados, y marcarlos para revisión es la respuesta correcta,
no una que haya que ajustar para que salga más veces "Alta". Se confirmó por
separado que el sistema sí llega a Alta con un artículo ficticio simple y sin
matices (`test_segmento_ficticio_simple_sin_excepciones_llega_a_confianza_alta`)
— el mecanismo discrimina, no está atascado en Baja por un error de código.

**Segunda observación real, ya documentada como limitación honesta y no
oculta**: el mismo segmento ficticio, interpretado dos veces en sesiones
distintas, clasificó su `tipo` una vez como `exigencia_cuantitativa` y otra
como `exigencia_compuesta` — ambas lecturas razonables del mismo texto
(combina un umbral con dos excepciones de naturaleza distinta), pero
`temperature=0` no garantiza reproducibilidad bit a bit, tal y como se
advertía en §3 punto 6. Las cifras extraídas (1,20 m y 0,80 m) sí se
mantuvieron idénticas y correctas en ambas corridas — que es la parte que la
verificación mecánica realmente protege.

30 tests nuevos: 8 de segmentación (deterministas, CTE real), 18 de confianza
y verificación (deterministas, sin red ni IA), 4 de frontera, y 5 en
`test_extraccion_interprete.py` (saltados por defecto — cuestan tokens reales
— activados con `ARCHMUSE_TEST_IA=1`; los cinco verificados en vivo esta
sesión). Regresión: sin cambios en el resto de la suite (el único fallo
preexistente, `test_scoring_coherencia.py`, sigue siendo la misma decisión
abierta de siempre). `evaluator.py`, `normativa/` e `ingesta/` sin tocar.

**Qué falta, explícito, tal y como se pidió**: ninguna promoción al corpus
(ni automática ni asistida), ninguna cola de revisión con interfaz, ninguna
resolución de `referencias_internas` a `concept_id` reales, ningún Documento
Básico real ingerido todavía (el CTE ingerido en la Fase 1 solo trae Parte I
— ver §0), y ninguna otra fuente distinta del CTE ya ingerido.