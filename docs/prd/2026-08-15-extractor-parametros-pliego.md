# PRD — Extractor de parámetros de pliegos de concurso

**Estado:** Aprobado · **Fecha:** 2026-08-15 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-15)

---

## 1. Problema que resuelve

Cuando el encargo de un proyecto viene de un concurso (público o privado, típicamente VPP/VPPA), el pliego de condiciones fija de antemano una veintena de parámetros duros — mix de tipologías, edificabilidad, altura máxima, PEM, régimen de protección, plazas de garaje, normativa aplicable — que hoy el arquitecto tiene que leer entero (con frecuencia 40-100 páginas mezclando lo administrativo con lo técnico) y transcribir a mano antes de poder empezar a trabajar en ArchMuse. Es exactamente el mismo tipo de trabajo repetitivo y propenso a error de transcripción que ya se resolvió para el cuadro de superficies (`docs/prd/2026-08-14-cuadro-de-superficies-autocompletar.md`) — pero en la entrada del generador, no en la salida del analizador.

Encargo directo de Pablo (2026-08-15), con especificación de campos y reglas ya detallada.

## 2. Usuario afectado

El arquitecto o estudio que participa en concursos con pliego de condiciones formal — un perfil de usuario de hoy, pero un flujo de trabajo (licitación) que ArchMuse no ha tocado explícitamente hasta ahora: ni `NORTH_STAR_2031.md` ni `MOAT_ANALYSIS.md` mencionan pliegos ni concursos. Se señala explícitamente en la sección 14.

## 3. Objetivo de negocio

Conecta con el Pilar 4 de `MOAT_ANALYSIS.md` ("cerrar el círculo generar-evaluar-corregir como el verdadero producto", línea 136): esto extiende el círculo hacia atrás, al origen del encargo, alimentando el generador/entrevistador con datos reales del pliego en vez de que el arquitecto los reintroduzca a mano en un formulario. Reduce la fricción de entrada precisamente al módulo que `MOAT_ANALYSIS.md` señala como la pieza más difícil de copiar (línea 57-67, generación con verificación normativa real). No es, por sí sola, una palanca de retención o pricing — es una mejora de UX de entrada que hace más probable que el arquitecto complete el flujo de generación en vez de abandonarlo en el formulario manual.

## 4. Objetivo técnico

Dado un PDF de pliego:

- Todo parámetro cuyo valor aparece literalmente en el texto se extrae con estado `KNOWN` y motivo citable.
- Ningún parámetro se completa jamás con un valor plausible que no esté en el texto — un pliego que no menciona el PEM máximo produce ese campo como `UNKNOWN`, nunca un 0 ni una omisión silenciosa.
- Cada parámetro lleva confianza cualitativa (Alta/Media/Baja), nunca un porcentaje — misma disciplina que `analyzer/hechos.py`.
- La salida reutiliza el modelo `Hecho` de `analyzer/hechos.py` (valor + `Estado` KNOWN/ESTIMATED/UNKNOWN + `Confianza` + `Motivo` con código y detalle) en vez de un esquema de confianza paralelo — es el mismo problema (¿qué tan seguro estoy de este dato, y por qué?) que ya se resolvió una vez; inventar un segundo vocabulario de confianza sería la misma clase de inconsistencia que hoy separa `evaluator.py` del modelo común en `modelo/`.
- El JSON extraído se presenta para revisión humana antes de usarse; nunca alimenta directamente al generador sin que el arquitecto lo confirme.

## 5. Casos de uso

1. **Pliego bien estructurado** (mix de tipologías en tabla clara, edificabilidad y altura en un artículo dedicado): la mayoría de campos salen `KNOWN` con confianza Alta.
2. **Pliego que no fija un parámetro** (p. ej. no menciona trasteros): ese campo queda `UNKNOWN` con motivo ("no se encontró ninguna mención a trasteros en el texto"), nunca omitido ni en `null` sin explicación.
3. **Revisión antes de generar**: el arquitecto ve el JSON extraído campo a campo, con badge de confianza y motivo en los `UNKNOWN`, corrige lo que haga falta, y solo entonces esos valores prellenan el formulario/entrevista de generación existente (`analyzer/interview/`) — este PRD no cubre el enlace automático a la entrevista, solo la entrega del JSON revisado (ver Riesgos, alcance).

## 6. Casos límite

- **PDF sin texto extraíble** (escaneado sin OCR): mismo caso ya resuelto en `ingesta/fuentes/codigotecnico.py::DocumentoIlegible` — reutilizar ese diagnóstico, no reinventar la detección.
- **Pliego con rango, no valor único** (p. ej. "entre 20 y 30 viviendas"): mapea a `num_viviendas_minimo`/`num_viviendas_maximo`, nunca se promedia ni se elige un punto medio inventado.
- **Unidades ambiguas** (m² útil vs. construido no explicitado en un artículo): no se asume ninguna — el campo se marca con confianza Baja y el motivo cita la ambigüedad textual.
- **PDF que no es un pliego** (subido por error, o un documento técnico irrelevante): el modelo debe poder devolver "no parece un pliego de condiciones" en vez de forzar 17 campos vacíos con apariencia de análisis completo.
- **El arquitecto sube el pliego y abandona** sin llegar a crear un proyecto: qué pasa con ese registro — resuelto en §10 (tabla propia, no depende de que exista un `proyecto_id` todavía).
- **Pliego largo** (100+ páginas, mucho articulado administrativo irrelevante a estos 17 campos): riesgo de coste, tratado en Riesgos.

## 7. Flujo del usuario

1. En la pantalla "Nuevo proyecto", botón **"Importar pliego PDF"**.
2. Sube el PDF → `POST /api/extraer-pliego`.
3. Estado de carga mientras se procesa (una sola llamada a Claude).
4. Se muestra el JSON extraído en una tabla de revisión: cada parámetro con su valor, badge de confianza, y motivo visible cuando está `UNKNOWN` o confianza Baja/Media.
5. El arquitecto corrige a mano lo que haga falta directamente en esa tabla.
6. Confirma → los valores revisados quedan disponibles para prellenar el formulario/entrevista de generación (el enlace automático a `analyzer/interview/` es una iteración futura, no de este PRD — ver alcance en Riesgos).

## 8. Criterios de aceptación

- Con un pliego real con mix de tipologías en tabla, `mix_tipologias` se extrae con la estructura pedida (`tipo`, `porcentaje`, `sup_util_min`, `sup_util_max`) y sin inventar un tipo que no aparece en el texto.
- Un campo ausente del pliego se sirve como `UNKNOWN` con motivo, nunca como valor inventado ni como ausencia silenciosa de la clave en el JSON.
- Cada campo trae confianza Alta/Media/Baja — nunca numérica.
- Un PDF sin texto extraíble produce un error claro (mismo mensaje que `DocumentoIlegible`), no una respuesta con 17 campos `UNKNOWN`.
- El PDF original y el JSON extraído quedan recuperables desde la tabla `pliegos` (ver §10) tras refrescar la página, sin volver a llamar a Claude.
- Reabrir un pliego ya extraído nunca vuelve a llamar a la IA — mismo invariante que `analyzer/storage.py` ya impone para proyectos.
- Ningún test de la suite normal (no gated por `ARCHMUSE_TEST_IA=1`) hace una llamada real a Claude.

## 9. Riesgos

- **Coste por llamada, no amortizable con caching**: a diferencia de `extraccion/interprete.py` (mismo `SYSTEM_PROMPT` reutilizado en decenas de llamadas por artículo), aquí es **una llamada por pliego** — el `cache_control` en el bloque de sistema no se paga de vuelta salvo que el mismo pliego se reprocese en los 5 minutos de TTL. Se mantiene por consistencia con el resto del proyecto y porque no cuesta nada añadirlo, pero no hay que esperar ahorro real de él en este endpoint.
- **PDF largo**: un pliego de 100 páginas con mucho articulado administrativo irrelevante a estos 17 campos encarece la llamada sin necesidad. Alternativa a decidir en implementación: enviar el PDF completo como bloque `document` nativo (mejor para tablas, que es donde vive `mix_tipologias`) vs. pre-extraer texto con `pypdf` (mismo patrón que `ingesta/fuentes/codigotecnico.py::_texto_desde_pdf`) y recortar a las secciones con mayor densidad de los términos buscados. Se recomienda **PDF nativo** por fidelidad en tablas — es donde `pypdf` con extracción de texto plano falla más — aceptando el coste mayor, dado que esto se ejecuta una vez por proyecto, no en bucle.
- **Alcance de negocio no validado**: no sabemos qué proporción de proyectos en ArchMuse arrancan de un pliego de concurso formal frente a encargo libre. Antes de construir persistencia completa (tabla SQLite, PDF binario, pantalla de revisión), vale la pena confirmarlo con 1-2 pliegos reales de Pablo.
- **Superficie de ataque nueva**: otro endpoint de subida de archivos. El límite global `MAX_CONTENT_LENGTH` (25 MB, `app.py:99`) ya cubre esto, pero conviene validar tipo MIME/extensión igual que ya hacen las rutas de subida de DXF. Más relevante: un pliego contiene información económica y comercial de una promoción (PEM, régimen de protección) — más sensible que un DXF. **Esto compite directamente con la tarea de seguridad ya detectada hoy en la auditoría del proyecto: `app.py` sigue en `debug=True` (`app.py:1598`) sin servidor WSGI de producción, con indicios de haber estado expuesto por Cloudflare Tunnel.** Subir información de concursos a ese servidor antes de cerrar ese punto es empeorar el mismo riesgo que ya está abierto. Se recomienda resolver `debug=True` (tarea #13 de `REFACTOR_MASTERPLAN.md`, ya priorizada) antes o junto con este PRD, no después.
- **No compite por lógica con `REFACTOR_MASTERPLAN.md`** salvo el punto anterior — es un módulo propio, no toca el motor de reglas ni el modelo común.

## 10. Impacto sobre módulos existentes

- **Nuevo módulo `analyzer/pliegos.py`** (o `extraccion_pliego.py`, a decidir en implementación): único punto de contacto con Claude para esta capacidad, mismo patrón que `extraccion/interprete.py` — `tool_choice` forzado contra un JSON Schema cerrado, enums construidos donde exista un catálogo cerrado real (p. ej. `regimen_proteccion`: VPP/VPPA/libre), nunca escritos sueltos en el prompt.
- **Reutiliza `analyzer/hechos.py::Hecho`/`Estado`/`Confianza`/`Motivo`** para cada parámetro — no se define un esquema de confianza nuevo.
- **`analyzer/storage.py`**: tabla nueva `pliegos` (id, nombre_archivo, pdf blob, json extraído, `proyecto_id` **nullable**, timestamps). Nullable porque el botón vive en la pantalla de "nuevo proyecto", *antes* de que exista una fila en `proyectos` — el pliego se guarda como borrador standalone y se enlaza a un `proyecto_id` solo si/cuando el arquitecto continúa hasta generar el proyecto. Reabrir un pliego guardado nunca llama a la IA — mismo invariante que la tabla `proyectos` ya impone.
- **`app.py`**: ruta nueva `POST /api/extraer-pliego`; ninguna ruta existente cambia de contrato.
- **`static/app.js`**: botón "Importar pliego PDF" en la pantalla de nuevo proyecto + tabla de revisión del JSON extraído. No toca el resto del flujo de análisis/generación existente.
- **Modelo por defecto**: se usa `claude-sonnet-5`, no `claude-sonnet-4-6` como se cita en el encargo — es el modelo al que se migraron hoy mismo los otros 4 puntos de contacto con Claude del proyecto (`ai_analyst.py`, `ai_generator.py`, `interview/claude_interprete.py`, `extraccion/interprete.py`) precisamente para tener un único modelo en todo el proyecto. Usar `sonnet-4-6` aquí reintroduciría la misma inconsistencia que se acaba de eliminar. Señalado explícitamente para que se apruebe o se corrija en esta revisión.

## 11. Plan de implementación dividido en pequeñas tareas

1. Esquema de la tabla `pliegos` en `analyzer/storage.py` (id, nombre_archivo, pdf blob, json, proyecto_id nullable, timestamps) + funciones `guardar_pliego`/`obtener_pliego`.
2. `_tool_schema()` en el nuevo módulo: los 17 campos pedidos, enums cerrados donde exista catálogo real (`regimen_proteccion`), estructura anidada para `mix_tipologias`.
3. `SYSTEM_PROMPT` con las reglas de "nunca inventar" / "no_encontrado" explícito, mismo tono que `extraccion/interprete.py`.
4. Función `extraer_pliego(pdf_bytes) -> dict[str, Hecho]` — la llamada a Claude, sin HTTP todavía.
5. Manejo de PDF sin texto extraíble (reutilizar diagnóstico de `DocumentoIlegible`).
6. Ruta `POST /api/extraer-pliego` en `app.py`: recibe el PDF, llama a `extraer_pliego`, guarda en `pliegos`, devuelve el JSON.
7. Ruta `GET /api/pliegos/<id>` para reabrir un borrador ya extraído sin llamar a la IA.
8. Botón "Importar pliego PDF" + estado de carga en `static/app.js` (pantalla de nuevo proyecto).
9. Tabla de revisión editable del JSON extraído (badges de confianza, motivo visible en `UNKNOWN`/Baja).
10. Tests deterministas (schema, storage, manejo de PDF ilegible) + 1-2 fixtures de pliego real (a aportar por Pablo) para un test gated tras `ARCHMUSE_TEST_IA=1`, sin asserts sobre el texto exacto de la respuesta (no determinista campo a campo, sí sobre la forma del JSON).

## 12. Plan de pruebas

- Mismo patrón que `tests/test_extraccion_interprete.py`: suite normal sin ninguna llamada real (mock del cliente), llamada real solo gated tras `ARCHMUSE_TEST_IA=1` y solo comprobando forma/tipos, nunca el valor textual exacto que devuelva el modelo.
- Tests deterministas sin IA: validación del schema de salida, guardado/recuperación en `pliegos`, comportamiento con PDF sin texto extraíble, comportamiento con `proyecto_id` nulo vs. enlazado.
- Se necesitan 1-2 pliegos reales (anonimizables si hace falta) de Pablo como fixture — sin eso no hay forma de validar los criterios de aceptación del §8 contra un caso real.

## 13. Métricas para medir el éxito

- % medio de los 17 campos que salen `KNOWN` en pliegos reales (proxy de utilidad real del extractor).
- Nº de campos que el arquitecto corrige a mano tras la revisión, por pliego (cuanto más bajo, mejor calibrada la extracción).
- Cuántos proyectos nuevos arrancan desde "Importar pliego" frente a formulario en blanco, en las semanas siguientes al lanzamiento.

## 14. Posibles motivos para NO implementar la idea (ahora, en este alcance)

- **No está en la visión ya documentada.** Ni `NORTH_STAR_2031.md` ni `MOAT_ANALYSIS.md` mencionan pliegos, concursos ni licitaciones — esto abre un frente de producto (gestión de la entrada de un concurso) distinto al que hoy define ArchMuse (evaluar/generar un plano). No es necesariamente un error hacerlo, pero no se puede presentar como continuidad natural de la hoja de ruta sin decirlo así.
- **Compite con un riesgo de seguridad ya abierto y más grave que él mismo**: subir información económica de una promoción (PEM, régimen de protección) a un servidor que sigue en `debug=True` y que hay indicios de haber estado expuesto por túnel es empeorar, no solo mantener, un problema ya identificado hoy. Recomendación: resolver `debug=True`/servidor de producción (tarea #13, ya priorizada) antes de exponer este endpoint, no después.
- **Alcance más barato para validar la idea primero**: en vez de construir de entrada la tabla `pliegos` con el PDF en blob, la pantalla de revisión y el enlace `proyecto_id`, una primera versión podría devolver el JSON extraído sin persistir el PDF (solo para esa sesión, copiar/pegar al formulario existente) — valida si el % de campos `KNOWN` en pliegos reales de Pablo justifica la inversión en persistencia y UI de revisión antes de construirlas. Se deja como alternativa explícita, no como recomendación por defecto, porque el encargo ya pedía persistencia — Pablo decide si prefiere validar primero o ir directo a la versión completa.

---

**Decisión:** Aprobado por Pablo (2026-08-15), con las desviaciones señaladas en §10 (modelo `claude-sonnet-5`) aceptadas implícitamente al aprobar. Implementado el mismo día: `analyzer/pliego_extractor.py`, tabla `pliegos` en `analyzer/storage.py` (SCHEMA_VERSION 4), rutas `POST /api/extraer-pliego`/`GET /api/pliegos/<id>`, botón "Importar pliego PDF" + tabla de revisión en `static/app.js` (pantalla "Generar proyecto"). El conector con `ai_generator.py`/el entrevistador (uso real de estos parámetros) es un PRD aparte, todavía sin aprobar.
