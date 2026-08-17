# PRD — Motor de estilos (carácter arquitectónico → parámetros del generador)

**Estado:** Borrador · **Fecha:** 2026-08-15 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 0. Un hallazgo bueno primero: esto ya tiene dónde encajar

A diferencia de los dos PRDs anteriores (sitio, solar), este **no depende de nada sin aprobar**. Y hay una pieza que ya existe y encaja casi exacta: `ai_generator.py` (Fase F, ya implementada) tiene un canal de "directivas cualitativas" (`contexto_cualitativo.directivas`) con un catálogo cerrado de categorías — **`"caracter"` ya es una de las cinco** (`CATEGORIAS_DIRECTIVA_VALIDAS`), y `fuerza="blanda"` ya es, por diseño de ese canal, precedencia de **nivel 4** ("intenta", la misma que pide el punto 5 de este encargo). Este PRD no necesita tocar el `SYSTEM_PROMPT` ni inventar una jerarquía nueva: necesita traducir `EstiloParams` a una o varias directivas `categoria="caracter"`, `fuerza="blanda"` — reutilizando `_validar_directivas`/el `tool_choice` forzado que ya existen, no una vía paralela.

## 1. Problema que resuelve

Hoy "Generar proyecto" no tiene ningún campo de carácter/estilo — el arquitecto no puede decirle a ArchMuse "quiero algo mediterráneo con huecos verticales" y que eso influya en algo. Encargo directo de Pablo (2026-08-15).

## 2. Usuario afectado

El mismo arquitecto de los PRDs anteriores, en el momento de definir la intención estética de un proyecto, antes o en vez de una entrevista completa.

## 3. Objetivo de negocio

Palanca de diferenciación real frente a un generador puramente normativo — conecta con el Pilar 4 de `MOAT_ANALYSIS.md` (generar-evaluar-corregir como el producto), añadiendo una dimensión que hoy no existe en absoluto: intención de diseño, no solo cumplimiento.

## 4. Objetivo técnico

- **Biblioteca determinista primero, IA solo cuando hace falta.** Con 14 estilos base y sinónimos razonables, la mayoría de descripciones libres deberían resolver por coincidencia léxica determinista (sin llamar a Claude) — mismo principio que Pablo fijó el 2026-08-01. Claude entra solo para describir libre que no encaja claramente con ningún estilo de la biblioteca, o para el refinamiento fino que el encargo pide (punto 1: "que Claude puede refinar").
- **Nunca se inventan referencias verificables.** `referencias: [{nombre_edificio, ciudad, año, url_imagen_publica}]` tal como se pidió es el punto más delicado de este PRD — ver §9, es donde más me aparto del encargo literal.
- **Nunca se afirma viabilidad VPP como si fuera normativa comprobada.** Mismo principio que ya rige `claude_interprete.py` ("nunca inventes un dato normativo") — `restricciones_compatibles_vpp` sale como nota orientativa citada como tal, nunca como una regla verificada.
- **`viabilidad_presupuesto` es una estimación cualitativa, no un cálculo de coste** — ArchMuse no tiene ningún dato real de coste de construcción en ningún sitio del sistema (mismo hueco ya detectado hoy en el PRD del verificador de pliegos, con el check de PEM). Se etiqueta como tal.

## 5. Casos de uso

1. **Descripción que coincide con la biblioteca** ("quiero algo minimalista y luminoso"): resuelve determinista, sin IA, instantáneo.
2. **Descripción ambigua o mixta** ("algo cálido, mediterráneo pero con líneas limpias, nada recargado"): la biblioteca no basta, se llama a Claude para refinar sobre la base más cercana.
3. **Generación con estilo**: al pulsar "Generar con IA", si hay un `EstiloParams` ya interpretado, se traduce a directivas `categoria="caracter", fuerza="blanda"` (Fase F) — nivel 4, nunca por encima de normativa ni de una directiva dura.

## 6. Casos límite

- **Descripción vacía o solo técnica** ("que cumpla la normativa"): no hay estilo que interpretar — `EstiloParams` no se fuerza, el generador sigue sin capa de carácter, como hoy.
- **Descripción que pide algo incompatible con la tipología/presupuesto** (p. ej. "fachada de piedra natural" con presupuesto de VPP ajustado): se refleja en `viabilidad_presupuesto=baja` y en la nota, nunca se descarta en silencio ni se sustituye por otra cosa sin decirlo.
- **Claude propone una referencia real** (edificio, arquitecto, año): sin verificación externa, no se puede garantizar que el edificio, la ciudad o el año sean correctos — y una URL de imagen "pública" que Claude complete es, con alta probabilidad, no resoluble o no la imagen real (patrón de alucinación bien conocido en URLs). Ver §9 para el rediseño de este campo.
- **El mismo texto libre se interpreta dos veces** (el arquitecto reabre el formulario): sin caché de por medio, sale una segunda llamada — a diferencia de pliego/sitio, aquí no hay una entidad persistente natural que cachear por (no hay "referencia catastral" equivalente); se acepta como coste conocido, no se resuelve en este PRD.

## 7. Flujo del usuario

1. En "Generar proyecto", campo de texto libre "¿Qué carácter quieres darle?".
2. El arquitecto escribe y pulsa una acción explícita ("Ver estilo" o similar) — **no en cada pulsación de tecla**, ver Riesgos.
3. Si coincide con la biblioteca: resultado instantáneo, sin llamada de red.
4. Si no: `POST /api/interpretar-estilo`, con estado de carga.
5. Se muestran los parámetros interpretados y (si Claude propuso referencias) claramente marcadas como sugerencias no verificadas, con enlace a buscarlas, no una imagen embebida de una URL sin comprobar.
6. Al generar, el estilo interpretado se traduce a directivas de carácter (nivel 4) — visible en el informe qué influencia tuvo, igual que ya se traza para las directivas de Fase F existentes.

## 8. Criterios de aceptación

- Una descripción que nombra un estilo de la biblioteca ("brutalista") resuelve sin ninguna llamada a Claude.
- Ninguna `url_imagen_publica` se muestra como imagen embebida sin que el arquitecto haya podido verificarla — ver rediseño de §9.
- `restricciones_compatibles_vpp` nunca aparece sin la coletilla de que es orientativo, no una verificación normativa.
- El `EstiloParams` interpretado se traduce a directivas `categoria="caracter"`, `fuerza="blanda"` — comprobable en `GeneratedProject.directivas_aplicadas` tras generar.
- Escribir en el campo de texto sin pulsar la acción explícita no dispara ninguna llamada de red.
- Generar sin haber interpretado ningún estilo se comporta exactamente igual que hoy (cero regresión).

## 9. Riesgos

- **`url_imagen_publica` generada por Claude es el riesgo más serio de este PRD.** Es el patrón de alucinación de URL mejor documentado de los LLM — una URL con forma plausible que no resuelve, o que no muestra lo que dice mostrar. Publicarla como si fuera un enlace verificado, en un producto que un arquitecto usa para decisiones reales, es exactamente el tipo de "inventar un dato" que este proyecto ha evitado sistemáticamente hoy (pliegos, hechos, interview). **Recomiendo explícitamente NO pedirle a Claude una URL** — que proponga `nombre_edificio`/`ciudad`/`año` como referencia citada (con el mismo aviso de "sin verificar" que ya lleva `NORMATIVA_AVISO` en el resto de la app), y que la búsqueda de la imagen la haga el arquitecto o, como mejora futura aparte, una búsqueda de imágenes real y verificada — no una URL inventada por el modelo.
- **`restricciones_compatibles_vpp` puede sonar a verificación normativa sin serlo.** Mismo riesgo que motivó la regla 1 de `claude_interprete.py` ("nunca inventes un dato normativo") — aquí el dato es más blando (compatibilidad de estilo con VPP, no un umbral CTE), pero el riesgo de que se lea como autoritativo es real. Debe ir con la misma coletilla que `NORMATIVA_AVISO` ya usa en el resto del informe.
- **`viabilidad_presupuesto` reabre el mismo hueco de datos que el check de PEM del verificador de pliegos**: ArchMuse no tiene ningún coste real de construcción en ningún sitio. Es la segunda vez en el día que una función pedida necesita un dato de coste que el sistema no tiene — vale la pena considerar si esto merece una fuente de datos de coste real compartida, en vez de resolverse dos veces por separado con heurísticas distintas.
- **Curación de los 14 estilos base es contenido, no código** — a diferencia de una tabla CTE (verificable contra un texto legal), "los parámetros compositivos correctos del racionalismo" es una cuestión de criterio arquitectónico. Sin la revisión de alguien con ese criterio (Pablo, presumiblemente), el motor publicaría composiciones con la autoridad de ArchMuse pero sin ninguna verificación real detrás — mismo patrón que ya se señaló hoy para el corpus normativo vacío en la auditoría de la mañana ("motor construido antes que el contenido").
- **No compite con `REFACTOR_MASTERPLAN.md`.** Sí es ya el sexto PRD de la sesión de hoy — mismo comentario de secuenciación que en el PRD de análisis solar: ninguno de los cuatro anteriores no implementados tiene todavía uso real medido.

## 10. Impacto sobre módulos existentes

- **`analyzer/estilos.py`** (nuevo): biblioteca determinista de 14 estilos + `interpretar_estilo()` (llama a Claude solo si la biblioteca no resuelve con confianza).
- **`analyzer/ai_generator.py`**: **no cambia el `SYSTEM_PROMPT`** — `EstiloParams` se traduce a entradas de `contexto_cualitativo.directivas` (`categoria="caracter"`, `fuerza="blanda"`), reutilizando `_validar_directivas` tal cual. Cero cambio de precedencia, cero riesgo de romper el test que compara el `SYSTEM_PROMPT` contra HEAD.
- **`app.py`**: ruta nueva `POST /api/interpretar-estilo` (incluye `tipologia_edificio` en el body, el encargo lo omite en la firma del endpoint pero la función sí lo pide — hay que ser consistente entre los dos).
- **`static/app.js`**: campo de texto + acción explícita (no en cada tecla) en `renderGenerarForm`, con las referencias mostradas como sugerencias sin verificar, no como imágenes embebidas de una URL no comprobada.
- **No toca** `analyzer/interview/` — el encargo no lo pide para esta pieza, a diferencia del PRD de sitio/solar.

## 11. Plan de implementación dividido en pequeñas tareas

1. Biblioteca determinista de los 14 estilos (`EstiloParams` predefinido por estilo + tabla de sinónimos/keywords para el match determinista).
2. Matching determinista de `descripcion_libre` contra la biblioteca (sin IA) — cubre el caso de uso 1 completo.
3. `interpretar_estilo()`: llamada a Claude SOLO para el caso sin match claro, `tool_choice` forzado, sin pedir `url_imagen_publica` (rediseño de §9).
4. Traducción `EstiloParams` → `contexto_cualitativo.directivas` (`categoria="caracter"`, `fuerza="blanda"`).
5. `POST /api/interpretar-estilo`.
6. UI: campo + acción explícita + presentación de referencias sin verificar, claramente marcadas.
7. Tests deterministas del matching de biblioteca (sin red) + tests gated (`ARCHMUSE_TEST_IA=1`) de la rama con Claude.

## 12. Plan de pruebas

- Tests deterministas del matching léxico contra la biblioteca — sin red, cubren la mayoría de los casos reales esperados.
- Test de que `EstiloParams` se traduce correctamente a una directiva válida contra `_validar_directivas` (categoría/fuerza correctas).
- Test de que el `SYSTEM_PROMPT` de `ai_generator.py` es bit a bit idéntico con o sin estilo interpretado (la influencia va por `contexto_cualitativo`, nunca por el prompt fijo).
- Ningún test de biblioteca ni de traducción llama a Claude.

## 13. Métricas para medir el éxito

- % de descripciones que resuelven por biblioteca sin llamar a Claude (mide si el diseño "software primero" está funcionando de verdad).
- Nº de proyectos generados con al menos una directiva de carácter, frente al total.

## 14. Posibles motivos para NO implementar la idea (ahora, en este alcance)

- **El campo de referencias tal como se pidió (con URL de imagen) no debería implementarse literalmente** — es el motivo más claro de todo este PRD para no aprobarlo "tal cual venía"; con el rediseño de §9 (sin URL, con aviso de no verificado) el riesgo baja a un nivel razonable.
- **La curación de los 14 estilos es trabajo de contenido, no solo de código** — si nadie con criterio arquitectónico real revisa los parámetros base, el motor publica composiciones con apariencia de autoridad sin haberla verificado nadie, mismo patrón que el corpus normativo vacío señalado en la auditoría de esta mañana.
- **Alternativa más barata**: implementar solo la biblioteca determinista (tareas 1-2, 4-6) en una primera versión, dejando la llamada a Claude para descripciones ambiguas (tarea 3) para una segunda aprobación una vez visto cuántas descripciones reales no encajan con los 14 estilos — la mayor parte del valor (un campo de carácter que influye de verdad en el generador) no necesita IA en absoluto para empezar.

---

**Decisión:** _pendiente de revisión por Pablo_
