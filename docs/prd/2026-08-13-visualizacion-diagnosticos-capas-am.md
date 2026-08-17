# PRD — Visualización de diagnósticos de clasificación de capas `AM_*`

**Estado:** Implementado y verificado · **Fecha:** 2026-08-13 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-13)

**Cierre (2026-08-13):** auditoría posterior confirmó que el código de `static/app.js`/`static/style.css` ya
implementa la opción D de este PRD tal cual (mismo mecanismo de panel flotante, misma partición local/proyecto,
mismos tokens de color). Pablo revisó la auditoría y resolvió las 3 decisiones pendientes de §13 en el sentido
en que ya estaban implementadas (ver abajo), sin abrir ninguna decisión nueva. Verificado con navegador real
sobre `prueba_am.dxf` (los 6 códigos de diagnóstico, entrada local y de proyecto, panel flotante) y con
cobertura de test añadida para los 2 códigos que la auditoría había señalado sin ejercitar a nivel de contrato
JSON (`VIVIENDA_SIN_ENVOLVENTE`, `ENVOLVENTE_SIN_VIVIENDA`) más `POLILINEA_ABIERTA`
(`tests/test_integracion_am_tabla.py`, bloques H/I/J).

Origen: auditoría técnica de 2026-08-13 sobre el estado de la integración `AM_*` ↔ tablas (informe de
conversación, sin fichero propio). Continúa el cierre de Fases 1-3 del contrato de clasificación DXF
(`analyzer/parser.py`, `analyzer/evaluator.py`, `analyzer/validacion_capas.py`), ya implementado y probado
(49 tests en verde: `tests/test_capas_am.py`, `tests/test_validacion_capas_am.py`,
`tests/test_integracion_am_tabla.py`).

---

## 0. Alcance de este documento — qué NO es

El working tree de ArchMuse tiene hoy, sin commitear, tres iniciativas simultáneas que no tienen relación entre
sí: (a) el cierre del contrato `AM_*` (este PRD), (b) el "entrevistador/generador"
(`analyzer/ai_generator.py`, `analyzer/interview/`, `docs/prd/2026-08-12-entrevistador-generador.md`), y (c)
la unificación del motor 3D (`static/viewer-core.js`/`viewer-geometry.js`/`viewer-materials.js`,
`viewer-edificio.js`, `viewer-vivienda.js`). **Este PRD no toca ninguna de las otras dos.** Su plan de
implementación (§11) se limita a `static/app.js`, `static/style.css` y, si acaso, `analyzer/api_serializer.py`
para exponer un dato ya calculado — nunca a `analyzer/ai_generator.py`, `analyzer/interview/` ni a los
ficheros `viewer-*`. Cualquier PRD futuro sobre esas dos iniciativas es independiente de este.

## 1. Problema que resuelve

La auditoría de 2026-08-13 confirmó que el backend del contrato de clasificación `AM_*` está completo y
probado, y que `api_serializer.serialize_analysis()` ya envía en cada respuesta de `/api/analizar` tres
piezas de información que el frontend nunca lee:

| Campo | Nivel | Contenido | ¿Se pinta hoy? |
|---|---|---|---|
| `clasificacion_capas` | vivienda | `"am"` / `"heredado"` | Sí (`capasAmHtml`, bloque "Origen de clasificación") |
| `envolvente_cerrada_m2`, `superficie_util_exterior_m2`, `envolvente_exterior_m2` | vivienda | superficies AM_* | Sí (`capasAmHtml`) |
| `capas_am_detectadas` | plano | qué capas `AM_*` están en uso en este DXF | **No** |
| `diagnosticos_clasificacion` | plano/vivienda mixto | avisos de conformidad del contrato (Fase 2, `validacion_capas.py`) | **No** |

`tests/test_integracion_am_tabla.py` (untracked, 2026-08-13) afirma en su docstring que la cadena llega
*"hasta la tabla que ve el arquitecto (`static/app.js`, `modoEspacioHtml`/`capasAmHtml`)"* — cierto solo para
2 de los 4 campos de la tabla de arriba. Un arquitecto que escriba `AM_UTIL_INT_` en vez de `AM_UTIL_INT`, o
que tenga dos polilíneas en `AM_CONS_CER` compitiendo por la misma vivienda, hoy **no se entera**: el
`envolvente_cerrada_m2` de esa vivienda sale `null`, exactamente igual que si la capa no existiera, y el
motivo real (`ENVOLVENTE_AMBIGUA`, ya calculado, ya en el JSON) queda invisible.

## 2. Usuario afectado

El arquitecto que sube su propio DXF ya clasificado con capas `AM_*` (el "usuario avanzado" del contrato de
clasificación) — el mismo perfil que Pablo describe como objetivo de este contrato desde su Fase 1. Un
arquitecto que usa el modo heredado (capa `"00 areas"` u otra, sin ninguna capa `AM_*`) no se ve afectado en
absoluto: por diseño (`validacion_capas.py`, "silencioso quiere decir silencioso"), un plano sin capas `AM_*`
no genera ningún diagnóstico y por tanto no dispara nada de lo que define este PRD.

## 3. Objetivo de negocio

El contrato `AM_*` es la vía para que un estudio de arquitectura dibuje siguiendo una convención propia y
ArchMuse la entienda sin ambigüedad — es infraestructura para volumen (varios DXF, varios proyectos, quizá
varios arquitectos de un mismo estudio con hábitos de dibujo distintos). Sin un canal de vuelta que explique
por qué una vivienda concreta no recibió su envolvente o su superficie exterior, el contrato falla en
silencio para quien más lo necesita: exactamente el arquitecto que ya invirtió en clasificar su plano. Un
fallo silencioso de una función que el usuario adoptó activamente es el peor tipo de fallo de confianza.

## 4. Objetivo técnico

Que `capas_am_detectadas` y `diagnosticos_clasificacion` — ya presentes en el JSON de `/api/analizar`, sin
cambio de contrato de API — sean visibles en la SPA, con la misma disciplina "silencioso" que ya rige el resto
del contrato: un plano sin ninguna capa `AM_*` en uso no debe ver ni un píxel nuevo.

## 5. Casos de uso

1. **Plano sin ninguna capa `AM_*`** (mayoría de los planos analizados hoy): la SPA no cambia. Cero elementos
   nuevos visibles.
2. **Plano con las 4 capas `AM_*` correctamente usadas, sin ningún diagnóstico**: la SPA sigue mostrando lo
   que ya muestra (`capasAmHtml` sin cambios) — sin un nuevo elemento "todo correcto" que esta auditoría no
   ha visto precedente para en el resto de la SPA (ver §6.4).
3. **Una vivienda con `AM_CONS_CER` ambigua** (dos envolventes candidatas): el arquitecto abre esa vivienda,
   ve que "Superficie construida cerrada" no aparece (como hoy), y ahora además ve un indicador que explica
   por qué y le deja abrir el detalle.
4. **Una capa mal escrita** (`AM_UTIL_INT_`, `AM_CONS_CERR`): diagnóstico `CAPA_CASI_CORRECTA`, sin vivienda
   asociada — no tiene dueño natural en el inspector por-vivienda actual (ver §10, hallazgo arquitectónico).
   El arquitecto necesita encontrarlo sin tener que adivinar en qué vivienda mirar.
5. **Geometría inválida dentro de una capa `AM_*`** (`GEOMETRIA_INVALIDA`, severidad ERROR): la única
   severidad ERROR del contrato — implica que una pieza de superficie real se ha descartado por completo.

## 6. Casos límite

1. **`capas_am_detectadas` no vacío, `diagnosticos_clasificacion` vacío** (capas en uso, todo correcto): no
   se añade ningún elemento nuevo — ver §6.4/decisión de UX.
2. **Diagnóstico sin `vivienda`** (la mayoría: `CAPA_CASI_CORRECTA`, `CAPA_RESERVADA_NO_OPERATIVA`, geometría
   descartada, y `ENVOLVENTE_SIN_VIVIENDA` cuando el plano no tiene ninguna etiqueta VT): no tiene vivienda
   a la que anclarse. No puede vivir solo en `capasAmHtml()`, que es por-vivienda.
3. **Diagnóstico con `vivienda` que no coincide con ninguna `Unit` final** (`ENVOLVENTE_SIN_VIVIENDA` cuando
   la etiqueta VT existe en el DXF pero ninguna habitación quedó agrupada bajo ella): el nombre de vivienda
   del diagnóstico no es necesariamente uno de `state.data.viviendas` — no se puede asumir que siempre hay
   una fila de sidebar a la que enlazar.
4. **Plano heredado que casualmente tiene una capa llamada de forma parecida a `AM_*`** por una casualidad de
   nomenclatura ajena al contrato (p. ej. un DXF de otro estudio con una capa `AM_ARMARIOS`): ya cubierto por
   backend (`_capas_casi_correctas` exige que el nombre empiece por `AM` y esté a distancia de edición ≤ 2 de
   una capa real del catálogo) — no es un caso límite nuevo de este PRD, se hereda resuelto.
5. **Varios diagnósticos del mismo código para la misma vivienda** (p. ej. tres capas casi-correctas a la
   vez): no hay deduplicación en `validacion_capas.py` ni falta hacerla — se listan todos, cada uno con su
   propio `handle`/`capa`.

## 7. Flujo del usuario

1. El arquitecto analiza un DXF con capas `AM_*`.
2. Si `diagnosticos_clasificacion` no está vacío, aparece un punto de entrada visible pero no intrusivo
   (§8, Decisión) — nunca un modal, nunca algo que bloquee ver el resultado del análisis.
3. Al activarlo, se abre un listado con todos los diagnósticos: agrupados por vivienda cuando el diagnóstico
   tiene una, bajo un grupo "Plano general" cuando no. Cada fila: severidad, capa afectada, mensaje.
4. Desde una vivienda concreta con al menos un diagnóstico propio, un indicador local en el bloque de
   "Espacio" abre el mismo listado ya filtrado a esa vivienda — mismo dato, mismo componente, dos puertas de
   entrada.
5. Cerrar el listado no cambia nada del análisis: es de solo lectura, igual que el resto del contrato.

## 8. Decisión de UX

### 8.1 Lo que ya existe y hay que respetar

- **El inspector es por-vivienda, sin excepción.** `inspectorModoHtml(v)` (`static/app.js:1909-1917`) siempre
  recibe una vivienda; las 6 pestañas del ribbon (`resumen`/`espacio`/`luz`/`normativa`/`problemas`/`ia`,
  `static/app.js:1170-1175`) no tienen ningún modo "de proyecto". No existe hoy ningún panel de nivel-plano en
  la SPA — ni siquiera `avisos_evacuacion` o los hechos CAP-2/CAP-3/CAP-4/CAP-5 (`proyecto.*`) se muestran en
  ningún sitio (verificado por búsqueda: cero referencias en `static/*.js`). Este PRD no arregla eso — lo
  señala porque condiciona la decisión de abajo.
- **El patrón "panel flotante" ya existe y ya resuelve exactamente este tipo de problema.**
  `abrirPanelFlotante(tipo)` (`static/app.js:2381-2414`) es un overlay que se abre desde un botón
  `.btn-reveal[data-panel]`, no desplaza el plano, se cierra con Escape o click fuera — hoy tiene dos usos
  (`"habitaciones"`, `"orientacion"`), ambos disparados desde dentro de `modoEspacioHtml`/`toolLuzHtml`. Es
  el único sitio de la SPA pensado para "una lista que se consulta y se cierra", que es exactamente lo que
  necesita un listado de diagnósticos.
- **El vocabulario de color rojo/ámbar/verde está tomado.** `--color-critical`/`--color-warning`/
  `--color-success` (`static/style.css:65-69`) son el semáforo normativo (CRITICO/IMPORTANTE/RECOMENDACION,
  `evaluator.rating_con_severidad`) y el indicador `tiene-aviso` de la fila de vivienda en el sidebar
  (`static/app.js:1006-1009`) ya usa ese mismo semáforo. Las severidades del contrato `AM_*`
  (`ERROR`/`WARNING`/`INFO`, `analyzer/validacion_capas.py:37-41`) **no son normativas** — son avisos de
  higiene de dibujo. Reutilizar la misma paleta las haría indistinguibles de un incumplimiento del CTE, que
  es precisamente la confusión que la tarea 6 de este encargo pide evitar.

### 8.2 Comparación de las 4 alternativas

**A. Solo ampliar `capasAmHtml()`/modo Espacio.** Resuelve bien los diagnósticos con `vivienda` (3 de 6
códigos: `ENVOLVENTE_AMBIGUA`, `VIVIENDA_SIN_ENVOLVENTE`, y el caso con-etiqueta de `ENVOLVENTE_SIN_VIVIENDA`).
**No tiene dónde poner los otros 3** (`CAPA_CASI_CORRECTA`, `CAPA_RESERVADA_NO_OPERATIVA`, geometría
descartada, y el caso sin-etiqueta de `ENVOLVENTE_SIN_VIVIENDA`) sin vivienda asociada — descartada como
única solución, no por gusto sino porque deja información sin sitio.

**B. Panel independiente nuevo.** Correcto para los diagnósticos sin vivienda, pero "nuevo" en el sentido de
inventar un mecanismo de presentación que la SPA no tiene (un modo de proyecto, o una nueva familia de
componente) cuando ya existe uno que hace exactamente este trabajo (el panel flotante). Construir una segunda
forma de "lista que se abre y se cierra" al lado de la que ya hay sería la duplicación que la tarea 4 de este
encargo pide evitar.

**C. Badges/avisos junto al selector de vivienda.** Reutiliza el patrón `tiene-aviso` visualmente, pero para
que signifique algo por fila hace falta reducir N diagnósticos de severidades distintas a un solo indicador
por vivienda — y esa fila ya lleva el indicador normativo (`tiene-aviso` + `semaforoColorVar`). Dos
indicadores de "algo va mal" con orígenes distintos en la misma fila, sin más contexto que un color, es
exactamente el riesgo de confusión de §8.1. Además dos de cada tres diagnósticos no tienen vivienda que
marcar.

**D. Combinación — la elegida.** Un único listado (mismo dato, un solo componente) que cubre los 6 códigos
sin excepción, montado sobre el mecanismo de panel flotante ya existente (cero patrón nuevo), con dos puertas
de entrada:
  - Un punto de entrada **por-vivienda**, dentro de `capasAmHtml()` (extiende A): solo visible si la vivienda
    actual tiene al menos un diagnóstico propio, abre el panel ya filtrado a ella.
  - Un punto de entrada **de proyecto**, en el panel flotante existente reutilizado con un tercer `tipo`
    (`"diagnosticos-capas-am"`) accesible aunque la vivienda seleccionada no tenga ningún diagnóstico propio
    — resuelve el caso límite §6.2/§6.3 sin inventar un modo de proyecto nuevo en el ribbon.

### 8.3 Justificación de D frente a las otras tres

- **UX:** un arquitecto que ya está mirando la vivienda con el problema lo encuentra ahí (entrada local);
  uno que solo sabe que "algo salió raro con las capas" lo encuentra sin tener que adivinar en qué vivienda
  buscar (entrada de proyecto). Las dos entradas abren el mismo panel — no hay dos informaciones que puedan
  desincronizarse.
- **Coherencia con la arquitectura actual:** cero patrón de interacción nuevo. Reutiliza `abrirPanelFlotante`
  tal cual, con un tercer valor de `tipo` — el mismo cambio de forma que ya separa `"habitaciones"` de
  `"orientacion"` hoy.
- **Mínima duplicación:** un único renderer de lista de diagnósticos, no dos vistas del mismo dato.
- **Escalabilidad:** si el contrato `AM_*` añade una quinta o sexta capa (`AM_DESCUENTO` ya está reservada
  para el futuro, `analyzer/parser.py:61`), sus diagnósticos entran en el mismo panel sin decisión de diseño
  nueva — el panel ya está preparado para "0 a N diagnósticos, con o sin vivienda".
- **Claridad para el arquitecto:** severidad, capa y mensaje visibles sin necesitar interpretar un color que
  ya significa otra cosa en la misma pantalla.

### 8.4 Sobre el caso "todo correcto" (§6.1)

Se descarta deliberadamente un indicador positivo ("Capas AM_* en uso: sin incidencias") para la vivienda o
el proyecto sin ningún diagnóstico. Ningún otro punto de la SPA afirma activamente "esto está bien" cuando no
hay nada que decir (el semáforo verde es la ausencia de marca, no una marca positiva — ver el propio
comentario de `static/app.js:993-1002`); introducir aquí la primera excepción sin que Pablo lo haya pedido
sería una capacidad nueva no solicitada. `capasAmHtml()` ya comunica implícitamente que el contrato está en
uso y funcionando (muestra las superficies AM_* calculadas) — no hace falta un mensaje adicional.

## 9. Estados visuales, jerarquía de información

- **Severidad → color, tabla cerrada, sin reutilizar el semáforo normativo:**
  - `ERROR` (`GEOMETRIA_INVALIDA`, la única): color de alerta técnica, visualmente distinto de
    `--color-critical` — p. ej. un tono ámbar/rojo desaturado propio de "aviso de datos", a definir en
    implementación con un nuevo par de tokens (`--color-am-error`, etc.), nunca los tokens del semáforo.
  - `WARNING` (`CAPA_CASI_CORRECTA`, `ENVOLVENTE_AMBIGUA`, `ENVOLVENTE_SIN_VIVIENDA`,
    `VIVIENDA_SIN_ENVOLVENTE`, tipo-no-soportado, polilínea-abierta, menos-de-3-vértices): tono neutro de
    aviso, no el ámbar normativo.
  - `INFO` (`CAPA_RESERVADA_NO_OPERATIVA`, la única): tinta terciaria, sin color de alerta — es una nota, no
    un aviso.
- **Siempre visible** (sin abrir nada): el punto de entrada mismo — solo si hay ≥1 diagnóstico — con un
  conteo (mismo patrón que `problems-counter`/`.count-critico` etc., `static/style.css:1179-1181`, pero con
  la paleta nueva de arriba).
- **Bajo detalle/expandir:** el listado completo de diagnósticos (mensaje, capa, `vivienda` si la tiene,
  `handle` si lo tiene) vive dentro del panel flotante — nunca en línea en el inspector, que ya está apretado
  (mismo criterio que llevó "habitaciones" y "orientación" al panel flotante en vez de listarlas en línea).
- **Sin capas `AM_*` en absoluto** (`capas_am_detectadas` vacío): cero elementos nuevos, en ningún sitio —
  ni el punto de entrada por-vivienda ni el de proyecto se renderizan.
- **Clasificación ambigua o incorrecta:** se muestra tal cual la reporta `validacion_capas.py` — mensaje
  literal del backend, sin que el frontend reinterprete ni resuma la causa (mismo criterio que
  `toolNormativaHtml`, que ya "pinta lo que el backend ya ha evaluado, no calcula nada").

## 10. Naturaleza de los diagnósticos: informativos, nunca normativos, nunca bloqueantes

Respuesta explícita a la tarea 6 del encargo: **son puramente informativos.** No generan ningún `IssueReport`,
no entran en `classify_problems`, no afectan a `score_pct`/`puntuacion`/`valoracion`, no bloquean guardar,
reanalizar, exportar a PDF ni ninguna otra acción. Evidencia de que esto ya es así en el backend, no una
decisión nueva: `evaluator.classify_problems` no importa ni referencia `validacion_capas` en ningún punto
(verificado por búsqueda), y `validar_capas_am()` lo dice en su propio docstring — *"Nunca cambia `doc`,
`plano` ni `unidades`: es de solo lectura (...) no decide nada por sí mismo"*. Este PRD no cambia esa
naturaleza: solo la hace visible. Si en el futuro alguien quisiera que una capa mal clasificada bloqueara
algo, eso es una decisión de producto distinta, con su propio PRD — no se cuela aquí.

## 11. Impacto sobre módulos existentes

- **`static/app.js`:** foco principal.
  - `capasAmHtml(v)` — añade el punto de entrada por-vivienda cuando `v` tiene diagnósticos propios (filtro
    por `vivienda === v.nombre`, más los sin-vivienda si se decide incluirlos también aquí — a resolver en
    implementación, ver §13).
  - `abrirPanelFlotante(tipo)` — nuevo valor de `tipo` (`"diagnosticos-capas-am"`), con un tercer parámetro
    opcional de filtro (nombre de vivienda) para la entrada local.
  - Nueva función `listaDiagnosticosCapasAmHtml(diagnosticos, filtroVivienda)`, mismo patrón que
    `listaHabitacionesHtml`/`listaOrientacionHtml`.
- **`static/style.css`:** nuevos tokens de color para `ERROR`/`WARNING`/`INFO` del contrato `AM_*`
  (deliberadamente distintos de `--color-critical`/`--color-warning`/`--color-success`), y las clases del
  nuevo listado (mismo espíritu que `.orient-badge`/`.orientation-list`).
- **`analyzer/api_serializer.py`:** posible ajuste menor si en implementación se decide adjuntar a cada
  `_serialize_unit` la lista de sus propios diagnósticos ya filtrada (evitar que el frontend repita ese
  filtro) — a decidir en implementación, no bloquea este PRD (ver §13, decisión pendiente 2).
- **No toca:** `analyzer/evaluator.py`, `analyzer/validacion_capas.py`, `analyzer/parser.py`, `app.py` (todos
  ya completos y probados, según la auditoría previa), ni `analyzer/pdf_report.py` (ver §12), ni ningún
  fichero de `analyzer/ai_generator.py`/`analyzer/interview/`/`viewer-*.js` (§0).

## 12. Sobre el PDF — fuera de alcance, justificado

`analyzer/pdf_report.py` no incluye hoy ninguno de los 5 campos del contrato `AM_*` (confirmado por
búsqueda). Se deja explícitamente fuera de este PRD por tres razones:

1. El PDF es un informe para entregar/archivar, no una herramienta de depuración interactiva — un aviso como
   "la capa AM_UTIL_INT_ está casi bien escrita" tiene sentido mientras el arquitecto está trabajando en la
   SPA y puede corregir el DXF y volver a subirlo; en un PDF ya generado no hay ninguna acción que tomar.
2. Meterlo ahora duplicaría el trabajo de diseño de estados visuales (§9) en un medio completamente distinto
   (estático, sin interacción, sin panel flotante posible) antes de validar que el diseño de la SPA es el
   correcto.
3. Ampliar el alcance a un segundo medio de salida sin que nadie lo haya pedido es exactamente el tipo de
   capacidad no solicitada que este proceso (PRD antes de código) existe para frenar.

Si en el futuro se decide que el PDF también debe reflejarlo, es una extensión natural pero **un PRD propio**
(el criterio de qué severidades merecen aparecer en un documento entregable a un cliente final es una
decisión de producto distinta a qué se muestra en la herramienta de trabajo).

## 13. Decisiones pendientes — resueltas (2026-08-13)

Las tres se resolvieron en la implementación ya presente en el árbol y quedaron confirmadas por Pablo al
cerrar este PRD, sin abrir ninguna decisión nueva fuera de las que ya planteaba este documento:

1. **¿El punto de entrada por-vivienda incluye también los diagnósticos sin `vivienda`?** Resuelto: **no** —
   se sigue la recomendación original. Los diagnósticos sin `vivienda`, o con una `vivienda` que no coincide
   con ninguna `Unit` final, viven solo en la entrada de PROYECTO (`diagnosticosCapasAmSinVivienda()`,
   `static/app.js`); la entrada local (`diagnosticosCapasAmDeVivienda()`) filtra estrictamente por
   `d.vivienda === v.nombre`. Verificado con navegador real: `CAPA_CASI_CORRECTA`,
   `RESERVADA_NO_OPERATIVA`, `GEOMETRIA_INVALIDA` y la polilínea abierta descartada aparecieron los 4 en la
   entrada de proyecto sobre `prueba_am.dxf`, nunca en una entrada local.
2. **¿Filtrar en frontend o en backend?** Resuelto: **en frontend**. `api_serializer.py` sigue publicando
   `diagnosticos_clasificacion` como lista plana sin agrupar; `static/app.js` filtra por `d.vivienda ===
   v.nombre` (entrada local) o por ausencia/no-coincidencia (entrada de proyecto), mismo patrón que ya usa el
   resto de la SPA para `issue.unit_name`/`calidad_espacial`/`circulacion`. `api_serializer.py` no se ha
   tocado para este cierre.
3. **Valores hexadecimales de los nuevos tokens de color:** Resuelto: `--color-am-diag: #8b7cc7` (morado/lila,
   con `--color-am-diag-bg: rgba(139, 124, 199, 0.16)` para el fondo de severidad ERROR), deliberadamente
   distinto de `--color-critical`/`--color-warning`/`--color-success`. Confirmado visualmente que las 3
   severidades (`diag-capas-sev-error/warning/info`) no se confunden con el semáforo normativo CTE en pantalla.

## 14. Posibles motivos para NO implementar la idea

- **Volumen de uso real hoy es bajo.** Según la auditoría previa, el contrato `AM_*` es nuevo y `ejemplo.dxf`
  (el único plano de referencia usado en los tests) no tiene ninguna capa `AM_*` — no hay todavía evidencia
  de cuántos arquitectos reales están usando el contrato ni de si se topan con estos diagnósticos en la
  práctica. Es razonable esperar a que un arquitecto real reporte confusión antes de invertir en la UI, en
  vez de anticiparlo.
- **Contraargumento:** el coste de implementación es bajo (reutiliza un mecanismo ya existente, no introduce
  arquitectura nueva) frente al coste de que el primer estudio que adopte el contrato lo abandone por no
  entender por qué una vivienda se quedó sin envolvente — silencioso no es gratis cuando el usuario ya
  invirtió esfuerzo en clasificar su plano (§3). Se mantiene la recomendación de implementar, pero se deja
  constancia de que no es urgente si hay trabajo con impacto medido esperando (p. ej. el propio entrevistador/
  generador, o `REFACTOR_MASTERPLAN.md`).

---

**Decisión:** Implementado y aprobado por Pablo el 2026-08-13. Verificado con navegador real sobre
`prueba_am.dxf` (los 6 códigos de diagnóstico, entrada local y de proyecto, panel flotante, paleta de color
propia) y con cobertura de test añadida en `tests/test_integracion_am_tabla.py` (bloques H/I/J:
`VIVIENDA_SIN_ENVOLVENTE`, `ENVOLVENTE_SIN_VIVIENDA` en sus dos variantes, `POLILINEA_ABIERTA`). No quedan
decisiones abiertas de este PRD.
