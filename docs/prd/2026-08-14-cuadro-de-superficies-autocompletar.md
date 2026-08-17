# PRD — Autocompletar cuadro de superficies

**Estado:** Aprobado (retroactivo — Fases 1-4 ya escritas, Fase 5 en curso) · **Fecha:** 2026-08-14 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-14)

---

## 0. Nota de proceso

Este PRD se escribe **a posteriori**. Las Fases 1-4 (detección del cuadro, cálculo puro de relleno, exportación a una copia DXF, botón de descarga en la SPA) ya están implementadas y probadas en el árbol de trabajo, sin commit. La Fase 5 (formulario de datos imprescindibles) tiene la lógica pura terminada; falta la capa HTTP, el formulario en `static/app.js` y las pruebas formales. Nada de esto se ha comprometido a git.

El proceso correcto era escribir esto antes de la Fase 1. No se hizo porque cada fase llegó como un encargo puntual, muy detallado, y el hábito de secuenciarlas como "Fase N" ocultó que en conjunto son una capacidad de producto nueva. Se documenta aquí para dejar registro honesto y para que la aprobación de lo que falta (Fase 5: HTTP + UI + tests) sea explícita antes de tocar más superficie visible al usuario.

---

## 1. Problema que resuelve

El "CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA" es una tabla (`ACAD_TABLE`) que debe acompañar la documentación de visado de cualquier proyecto residencial en España — superficie útil de cada pieza (salón, dormitorios, baño, aseo, pasillo, vestíbulo, tendedero, terrazas) y los totales interior/exterior/útil por tipo de vivienda. Hoy el arquitecto la rellena a mano, celda a celda, releyendo el plano — trabajo repetitivo, propenso a error de transcripción, y que no dice nada sobre qué cifra viene de una medición real del DXF y cuál es una estimación a ojo.

Esto conecta directamente con el diagnóstico de `MOAT_ANALYSIS.md` (línea 16): el valor de ArchMuse no es "un plano bonito", es evitar el coste de un rechazo de visado — y un cuadro de superficies mal rellenado o inconsistente con el plano es justo el tipo de detalle administrativo que un visado rechaza. También es un paso concreto hacia el hito de `NORTH_STAR_2031.md` (línea 21): "genera el paquete completo de documentación de visado... No se exporta nada a mano" — el cuadro de superficies es una pieza pequeña pero real de ese paquete.

## 2. Usuario afectado

El arquitecto individual o de estudio que ya sube un DXF a ArchMuse para el análisis normativo (usuario de hoy, no uno futuro) — en el momento de preparar la documentación de visado de ese mismo proyecto.

## 3. Objetivo de negocio

Refuerza la identidad de "paso obligatorio antes de visado" (`MOAT_ANALYSIS.md` línea 114): cuantas más piezas reales de esa documentación resuelva ArchMuse de forma trazable, más caro es abandonarlo a mitad de proceso. No es una función de productividad aislada; es un ladrillo del "paquete completo de documentación" que ya está en la hoja de ruta de `NORTH_STAR_2031.md`.

## 4. Objetivo técnico

Dado un DXF con exactamente una vivienda detectada y un `ACAD_TABLE` "CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA" reconocible:

- Toda celda calculable de forma unívoca a partir de la geometría del plano se calcula sola, sin preguntar nada.
- Ninguna celda se rellena jamás con una estimación o un valor inventado.
- Toda celda que no se pueda resolver de forma unívoca se identifica y se pregunta al arquitecto — nunca se deja como `N/D` en la versión final descargable.
- Ninguna cifra ya presente en el DXF original se sobrescribe jamás, ni por cálculo ni por respuesta del usuario — un conflicto se muestra, no se resuelve en silencio.
- El DXF original nunca se modifica; solo se genera una copia nueva.
- Cada valor final queda identificado por procedencia: calculado, preexistente en el DXF, o declarado por el usuario.

## 5. Casos de uso

1. **Caso totalmente automático**: el plano no tiene ninguna ambigüedad (todas las piezas identificables sin duda, sin conflicto con datos preexistentes) → el cuadro se calcula entero y se puede descargar sin ninguna pregunta.
2. **Caso con datos imprescindibles pendientes** (el caso real de `v2s.dxf`): el plano tiene 2-3 huecos geométricos candidatos a "tendedero/terraza" que no se pueden asignar sin ambigüedad, y datos que el DXF no expresa en absoluto (superficie construida cerrada/exterior, número de unidades del tipo). ArchMuse muestra un formulario mínimo — únicamente esos campos, mostrando las geometrías candidatas con nombre, superficie y posición para que el arquitecto elija — y tras responder, genera la descarga completa.
3. **Caso de descarga rápida de borrador** (ya existente, Fase 3/4): el arquitecto quiere ver el estado actual con `N/D` en lo pendiente, sin responder preguntas todavía — se mantiene como opción secundaria.

## 6. Casos límite

- El DXF ya trae una celda con texto humano preexistente (p. ej. `VIVIENDA TIPO = "VT1 /3"`, o un estudio que ya rellenó `tendedero` a mano con un valor que no coincide con lo que ArchMuse mediría o con lo que el arquitecto responde en el formulario) → nunca se sobrescribe; se marca conflicto y bloquea la descarga completa hasta que se resuelva la discrepancia (fuera del alcance de este PRD decidir *cómo* se resuelve una discrepancia real — de momento solo se muestra).
- Más de una vivienda detectada en el DXF, o ningún `ACAD_TABLE` reconocible → error claro, ninguna función de este PRD aplica (limitación ya conocida, ver Riesgos).
- Una familia de piezas (p. ej. terrazas) con algunos huecos preexistentes y otros vacíos → los preexistentes se respetan, solo se pregunta por los vacíos restantes.
- El arquitecto cierra el formulario a medias → el botón de descarga completa permanece deshabilitado; el borrador con `N/D` sigue disponible.

## 7. Flujo del usuario

1. Sube el DXF y lo analiza (flujo ya existente de `/api/analizar`).
2. Si ArchMuse detecta un cuadro de superficies, aparece la opción de completarlo.
3. ArchMuse calcula en el momento qué celdas quedan sin resolver.
4. Si hay alguna: se muestra el formulario "Datos necesarios para completar el cuadro" — solo esos campos, nada más.
5. El arquitecto responde (elige qué geometría es cada pieza exterior; introduce las cifras que el DXF no expresa).
6. Si alguna respuesta contradice una celda ya presente en el DXF, se muestra el conflicto en el sitio, sin perder las demás respuestas ya dadas.
7. Con todo resuelto sin conflictos, el botón "Descargar cuadro completo" se habilita → descarga la copia DXF con el cuadro entero relleno (sin ningún `N/D`).

## 8. Criterios de aceptación

- Con un plano sin ambigüedad, la descarga completa funciona sin mostrar ningún formulario.
- Con `v2s.dxf`, el formulario muestra exactamente las cuatro solicitudes especificadas por Pablo (asignación de tendedero/terraza 1/terraza 2 con sus geometrías candidatas; superficie construida cerrada; superficie construida exterior; número de unidades) y ninguna otra.
- Tras responder esas cuatro, las 18 celdas del cuadro tienen un valor real; cero apariciones de `N/D`.
- Los totales (útil exterior, útil) se recalculan correctamente a partir de las respuestas.
- El archivo original en disco conserva exactamente el mismo hash antes y después de todo el flujo.
- Una respuesta que contradice una celda preexistente bloquea la descarga completa y explica el conflicto en vez de sobrescribir en silencio.
- La descarga de borrador con `N/D` (Fase 3/4) sigue funcionando sin cambios.
- Ninguna lógica de cálculo de superficies se duplica en `static/app.js` — vive solo en `analyzer/cuadro_superficies.py`.

## 9. Riesgos

- **Alcance geométrico estrecho**: `_analizar_para_cuadro` exige exactamente una vivienda detectada y el `ACAD_TABLE` con el título exacto "CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA". Validado solo contra `v2s.dxf` y `ejemplo.dxf`. Un DXF de otro estudio, con otra plantilla de cuadro o varias viviendas por planta, no se beneficia de nada de esto todavía — no se debe comunicar como "funciona con cualquier DXF".
- **Deuda de proceso**: este PRD es retroactivo. El riesgo real no es esta función en sí, sino que el hábito de "fase a fase, sin PRD" se repita en la próxima capacidad nueva. Vale la pena que quede explícito que a partir de aquí sí se para antes de seguir.
- **No compite con `REFACTOR_MASTERPLAN.md`**: es trabajo nuevo sobre un módulo propio (`cuadro_superficies*.py`), no toca el motor de reglas normativas ni las tareas ya priorizadas allí — no hay conflicto de tiempo de desarrollo que declarar.
- **Superficie de ataque HTTP nueva** (Fase 5 pendiente): dos endpoints nuevos que reciben un DXF completo por upload — mismo perfil de riesgo que el endpoint de Fase 4 ya en producción de facto (mismo patrón de validación, sin persistencia).

## 10. Impacto sobre módulos existentes

- `analyzer/cuadro_superficies.py` (nuevo módulo, cálculo puro) y `analyzer/cuadro_superficies_export.py` (nuevo módulo, I/O DXF) — no modifican `analyzer/parser.py` ni `analyzer/evaluator.py`, solo los consumen en modo lectura.
- `app.py` — nuevas rutas; ninguna ruta existente cambia de contrato.
- `static/app.js` — nueva sección de UI (pestaña Salida); no toca el resto de pestañas ni el estado de análisis existente.
- No hay persistencia nueva: `analyzer/storage.py` no cambia.

## 11. Plan de implementación dividido en pequeñas tareas

**Ya hecho (sin commit):**
1. ✅ Fase 1 — detección del `ACAD_TABLE` y sus celdas (`detectar_cuadro_superficies`).
2. ✅ Fase 2 — cálculo puro de relleno por celda (`calcular_relleno_cuadro`), catálogo cerrado de estados.
3. ✅ Fase 3 — exportación a copia DXF nueva (`exportar_cuadro_relleno`), verificación de reapertura sin corrupción.
4. ✅ Fase 4 — endpoint de descarga de borrador + botón en la SPA.
5. ✅ Fase 5a — lógica pura: `Solicitud`/`CandidatoAsignacion`, `detectar_solicitudes`, `aplicar_respuestas`, `celdas_sin_resolver`, manejo de conflicto con celda preexistente.

**Pendiente (bloqueado hasta aprobación de este PRD):**
6. Fase 5b — endpoint `POST` para obtener las solicitudes pendientes de un DXF.
7. Fase 5c — endpoint `POST` para aplicar respuestas y devolver la descarga completa (o 409/400 con el detalle de conflicto/pendientes).
8. Fase 5d — formulario en `static/app.js`: renderizado de las solicitudes, envío de respuestas, gating del botón de descarga completa, visualización de conflictos sin perder respuestas ya dadas.
9. Fase 5e — batería de pruebas formales (caso automático, `v2s.dxf` exacto, cero `N/D` tras responder, totales recalculados, hash del original intacto, conflicto bloquea descarga) + pruebas de endpoint + pruebas de UI (patrón `test_ui_exportar_dxf_relleno.py`).
10. Verificación visual real en navegador con `v2s.dxf` (subir, responder formulario, descargar, confirmar visualmente que no queda ningún `N/D`).

## 12. Plan de pruebas

Mismo patrón ya establecido en el proyecto: scripts standalone en `tests/` (no pytest), `check()`/`fallos`/`sys.exit(1)`, ejecutados contra `v2s.dxf` y `ejemplo.dxf` reales cuando estén disponibles en el entorno. Cobertura mínima exigida por Pablo para la Fase 5, ya enumerada en la sección 8 (Criterios de aceptación) — no se repite aquí.

## 13. Métricas para medir el éxito

No hay instrumentación de producto todavía (el análisis no persiste métricas de uso por función). Como proxy inmediato: que la descarga completa de `v2s.dxf` no tenga ningún `N/D` y el arquitecto no necesite tocar el DXF a mano después. Una métrica real de éxito en producción (porcentaje de análisis que llegan a descarga completa vs. solo borrador) requeriría antes la instrumentación de uso que hoy no existe — fuera de alcance de este PRD.

## 14. Posibles motivos para NO implementar la idea

- El alcance geométrico real (una sola vivienda, un título de tabla exacto) es tan estrecho hoy que el valor inmediato es válido solo para `v2s.dxf`/`ejemplo.dxf` y planos con la misma plantilla — no para la base de clientes en general. Si el objetivo a corto plazo es demostrar valor con clientes de pago reales (línea con `NORTH_STAR_2031.md`, fase "Retención"), esta función por sí sola no lo consigue hasta que se generalice a más plantillas de cuadro y a plantas con varias viviendas.
- Alternativa a considerar: en vez de generalizar la detección geométrica del cuadro (frágil, depende de cómo cada estudio dibuja su `ACAD_TABLE`), invertir ese esfuerzo en la "memoria justificativa" textual de `NORTH_STAR_2031.md` (línea 133, ya en el hito de 6 meses), que no depende de reconocer una tabla CAD ajena y cubre más superficie del paquete de visado por el mismo esfuerzo.
- Dicho esto: el trabajo ya está hecho y probado, el coste hundido es real, y como pieza aislada no compite por tiempo con `REFACTOR_MASTERPLAN.md`. La recomendación de este CTO es **completar la Fase 5 tal como está especificada y quedarse ahí** — sin invertir más en generalizar la detección de cuadro hasta que un segundo DXF real de otro estudio confirme que vale la pena.

---

**Decisión:** Aprobado por Pablo el 2026-08-14. Sigue la Fase 5 (tareas 6-10 de la sección 11) tal como está especificada.
