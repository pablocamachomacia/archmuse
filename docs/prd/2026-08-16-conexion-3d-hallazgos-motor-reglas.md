# PRD — Conexión visor 3D ↔ hallazgos del motor de reglas (Sandbox)

**Estado:** Implementado · **Fecha:** 2026-08-16 · **Fecha de cierre:** 2026-08-16 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (ejecución directa)

---

## 0. Resumen para decidir rápido

Este PRD ejecuta el punto §6.1 de `ROADMAP_VISION_ARQUITECTONICA.md` ("conectar el visor 3D a los hallazgos del motor de reglas"), acotado al Sandbox (`static/viewer-sandbox.js`) y a las **reglas de urbanismo de edificio** (ocupación, edificabilidad, altura/plantas, retranqueos) — no a las ~40 reglas CTE de habitaciones, que no aplican a un volumen sin distribución interior.

**Dos correcciones de encuadre respecto al encargo, antes de diseñar nada:**

1. **Las funciones de "motor de reglas" que aplican aquí viven en `analyzer/evaluator.py`** (`evaluate_solar_occupation`, `evaluate_buildability`, `evaluate_max_floors`, `evaluate_retranqueos`), no en `analyzer/sitio.py` (que solo resuelve geometría de parcela/colindantes vía Catastro/Overpass — ya integrado en el Sandbox desde el PRD anterior). `sitio.py` es la fuente del dato (`superficie_m2` de la parcela real); `evaluator.py` es quien lo evalúa contra un límite normativo.
2. **`/api/analizar` no es el endpoint correcto para validar en backend.** Analiza un DXF ya subido (habitaciones reales de un plano existente) — no acepta volúmenes dibujados a mano. Las cuatro funciones anteriores son puras (reciben números sueltos, sin depender de un DXF) y **ya se usan hoy en `/api/generar`** (`app.py:1151-1185`) — este PRD propone un endpoint nuevo y mínimo que las reutiliza tal cual, sin reimplementar ninguna regla normativa por segunda vez.

**Hallazgo que condiciona todo el diseño:** hoy, en el momento en que el Sandbox está abierto, **no existe en ningún sitio de la aplicación un valor de "edificabilidad máxima" / "ocupación máxima" / "retranqueos" / "plantas máximas".** Esos campos son un formulario que el arquitecto rellena en Modo Experto (`static/app.js:755-760`) o en la Entrevista guiada (`static/entrevista.js:222-225`), **siempre después** de cerrar el Sandbox (`entrevista.js:936-962`: el Sandbox se abre solo con `lat`/`lon`, nunca con normativa). Sin resolver esto, "resaltar cuando un volumen sobrepase la edificabilidad máxima" no tiene con qué comparar. Este PRD añade un panel compacto y opcional de límites urbanísticos **dentro del propio Sandbox**, con los mismos campos y los mismos valores por defecto que ya usa Modo Experto (§7) — no un dato nuevo inventado, el mismo dato, más temprano en el flujo.

| Pieza | Ya existe (reutilizada tal cual) | Nueva en este PRD |
|---|---|---|
| Geometría/superficie real de la parcela | `body.geometria_parcela` (Catastro, vía `pedirEntorno3DPorCoordenadas`, PRD anterior) | — |
| Fórmulas de ocupación/edificabilidad/plantas máximas | `evaluator.py: evaluate_solar_occupation/evaluate_buildability/evaluate_max_floors` | Replicadas en cliente para respuesta instantánea (mismas fórmulas, documentadas con referencia cruzada) + endpoint nuevo que reutiliza las funciones reales para reconciliar |
| Retranqueos | `evaluator.py: evaluate_retranqueos` (proxy rectangular, sin geometría real) | **Mejora, no reutilización directa**: el Sandbox ya tiene el polígono REAL de la parcela — se comprueba distancia de cada volumen al borde real, más preciso que el proxy rectangular existente (ver §9) |
| Límites urbanísticos (valores) | Formulario de Modo Experto/Entrevista (`ocupacion_maxima_pct`, `retranqueos_m`, `edificabilidad_maxima`, `plantas_maximas`) | Mismo formulario, en miniatura, dentro del Sandbox — para que exista un valor ANTES de dibujar el primer volumen |
| Highlight visual de incumplimiento | — (no existe) | Nuevo estado de material por volumen, con prioridad definida frente a la selección existente (§7) |

---

## 1. Problema que resuelve

Confirmado por dos documentos independientes del propio proyecto (`MOAT_ANALYSIS.md` §6, `DESTROY_ARCHMUSE.md` §2): el visor 3D "no está conectado al motor de hallazgos... es una demostración de capacidad técnica, no una herramienta de validación." Hoy, un arquitecto puede dibujar un volumen en el Sandbox que incumple claramente la normativa del solar (ocupación, edificabilidad, retranqueos) y no se entera hasta que, mucho más adelante, genera el proyecto completo con IA y lo evalúa por separado. El objetivo es mover ese feedback al momento en que de verdad se toma la decisión de diseño — mientras se arrastra el volumen, no después.

## 2. Usuario afectado

El mismo arquitecto que ya usa el Sandbox (Modo "Lienzo libre") para bocetar volúmenes rápidos sobre una parcela real, antes de comprometerse a una distribución interior completa.

## 3. Objetivo de negocio

Es la corrección de mayor prioridad relativa señalada por `ROADMAP_VISION_ARQUITECTONICA.md` §2 y §6: barata comparada con el resto del roadmap, y corrige la debilidad de producto más citada por el propio análisis de foso (`MOAT_ANALYSIS.md`) y por el ataque de competidor (`DESTROY_ARCHMUSE.md`) — un visor 3D vistoso pero desconectado de la validación real.

## 4. Objetivo técnico

- Las métricas agregadas de la escena (ocupación %, edificabilidad m²/m², plantas vs. máximo) se recalculan de forma reactiva cada vez que se añade, escala, rota o borra un volumen — sin llamada de red en el camino instantáneo.
- Los mismos números, calculados en cliente, coinciden exactamente (mismo redondeo, misma fórmula) con lo que devolvería `evaluator.py` para el mismo input — verificado con una llamada de reconciliación al backend, no solo por inspección de código.
- Un volumen cuyo footprint invade la banda de retranqueo del polígono real de la parcela se distingue visualmente de uno que no.
- Nunca se muestra un número de ocupación/edificabilidad/retranqueos cuando no hay datos reales de parcela para calcularlo — mismo criterio de honestidad que ya aplica `evaluator.py` (`return None` en vez de inventar).

## 5. Casos de uso

1. Arquitecto abre el Sandbox sobre una parcela real de 500 m², deja los límites urbanísticos en los valores por defecto (ocupación 70%, sin edificabilidad/plantas máximas informadas), añade un volumen de 20×15 m → el HUD muestra "Ocupación: 60% de 70%" en verde; añade un segundo volumen de 15×15 m → el HUD sube a 105% y pasa a rojo, y el volumen recién añadido (el que causó el salto) se resalta.
2. El mismo arquitecto edita el panel de límites urbanísticos e introduce edificabilidad máxima = 1.5 m²/m² → el HUD añade esa fila y la recalcula con los volúmenes ya dibujados, sin tener que volver a tocarlos.
3. Arquitecto dibuja un volumen cuya esquina queda a 1,2 m del borde real de la parcela, con un retranqueo mínimo de 3 m configurado → ese volumen (y solo ese) se resalta en naranja/rojo; el resto de volúmenes, que sí respetan el retranqueo, mantienen sus materiales normales.
4. Arquitecto abre el Sandbox en modo Laboratorio (sin parcela real) → el panel de métricas indica explícitamente que no hay datos de parcela real para calcular ocupación/edificabilidad/retranqueos, en vez de mostrar un 0% o un dato inventado.
5. Arquitecto pulsa "Generar plantas con IA" → antes de proceder, se reconcilia una última vez contra el backend (`evaluate_solar_occupation`/`evaluate_buildability`/`evaluate_max_floors` reales) y, si hay discrepancia con lo mostrado en cliente, se registra en consola para depuración (nunca bloquea silenciosamente el flujo existente).

## 6. Casos límite

- **Parcela real sin `geometria_parcela`** (Catastro no encontró parcela exacta en esas coordenadas, `body.geometria_parcela: null`, ya contemplado por el PRD anterior): ninguna de las tres métricas es evaluable — el panel lo dice explícitamente, no se muestra `0%`.
- **Volúmenes solapados**: la ocupación/edificabilidad se calculan como la SUMA de las huellas de cada volumen (`largo × ancho`), no como la unión geométrica real — si dos volúmenes se solapan deliberadamente, el cálculo sobreestima la ocupación real. Es una aproximación explícita y documentada (ver §9), no un bug oculto; calcular la unión real exigiría una librería de geometría 2D que hoy no existe en el frontend.
- **Rotación de volúmenes**: el área de la huella (`largo × ancho`) no cambia con la rotación, así que ocupación/edificabilidad no se ven afectadas por rotar un volumen — pero el chequeo de retranqueos SÍ debe usar las 4 esquinas ya rotadas del volumen (no su bounding box sin rotar), o un volumen girado podría dar un falso negativo/positivo cerca del borde.
- **Ningún límite urbanístico informado** (todos los campos del panel en blanco salvo ocupación, que trae un valor por defecto): mismo criterio que `evaluator.py` — sin `edificabilidad_maxima`/`plantas_maximas`/`retranqueos_m`, esas filas del HUD no se muestran (no `Optional[...]` = `None`, no un `0` engañoso).
- **Solar con superficie de Catastro pero polígono degenerado** (menos de 3 vértices válidos, mismo criterio que ya usa `construirContornoParcela`): retranqueos no evaluable; ocupación/edificabilidad sí (solo necesitan `superficie_m2`, no la forma).
- **El volumen "atribuido" a un salto de edificabilidad se borra después**: el resaltado de "responsable del exceso" desaparece con él; si el agregado sigue por encima del límite tras borrarlo, no hay ya un volumen concreto que señalar como causante — el HUD sigue en rojo pero ningún volumen concreto se resalta por ese motivo (ver §7, política de atribución).
- **Reconciliación backend-cliente en Laboratorio** (sin parcela real): no hay nada que reconciliar — el endpoint nuevo no se llama.

## 7. Flujo del usuario

1. Al abrir el Sandbox (con parcela real), un panel compacto "Límites urbanísticos" aparece junto al panel de edición de volumen existente, pre-rellenado con los mismos valores por defecto que Modo Experto (`ocupacion_maxima_pct: 70`, `retranqueos_m: 3`, `edificabilidad_maxima` y `plantas_maximas` vacíos/opcionales) — editable en cualquier momento, sin llamada de red al cambiarlo.
2. Un HUD flotante (nueva pieza, distinta del panel de edición de volumen y de la barra de herramientas ya existentes) muestra, en todo momento que haya al menos un volumen:
   - **Ocupación**: `X% de Y%` (huella total / superficie del solar), con `Y` solo si está informado.
   - **Edificabilidad**: `X,XX de Y,YY m²/m²`, igual.
   - **Plantas**: `X de Y`, igual (proxy simple de "gálibo": no hay ningún campo de altura máxima en metros en la aplicación hoy — se usa el mismo vocabulario ya existente en el resto del producto, `plantas_maximas`, en vez de inventar un campo nuevo).
3. Cada vez que se añade/escala/rota/borra un volumen (mismos 4 puntos de entrada que ya reencuadran la cámara en `viewer-sandbox.js`), el HUD se recalcula en cliente, instantáneo.
4. Si el agregado de una métrica supera su máximo, esa fila del HUD se resalta (fondo/texto rojo) y **el volumen cuyo cambio causó el cruce del límite** (el que se acaba de añadir/escalar/mover en esa interacción) recibe un material de aviso, con esta prioridad frente a otros estados visuales: `seleccionado (amarillo) > incumple retranqueo (rojo) > incumple agregado, atribuido (naranja) > normal`. Un volumen puede estar en más de una categoría a la vez (p. ej. seleccionado Y con retranqueo inválido); se aplica siempre la de mayor prioridad, nunca se mezclan dos tintes.
5. El chequeo de retranqueos es independiente del agregado y se recalcula para TODOS los volúmenes en cada cambio (no solo el último tocado): cualquier volumen cuyo footprint invada la banda de retranqueo del polígono real se resalta, sin importar cuándo se dibujó.
6. Al pulsar "Generar plantas con IA", antes del callback existente (`onGenerarCallback`), se llama una vez al endpoint nuevo (`POST /api/validar-urbanismo`) con los números agregados actuales; el resultado se compara con lo ya mostrado y cualquier discrepancia se registra en consola (`console.warn`) — nunca bloquea ni cambia el comportamiento ya existente del botón.

## 8. Criterios de aceptación

Todos verificados en vivo (Chrome, servidor local, parcela real de La Moraleja — Catastro, 3618 m²) el 2026-08-16.

1. **[x]** El panel de límites urbanísticos existe en el Sandbox ("Urbanismo" + `<details>Límites urbanísticos</details>`), con los 4 campos y los mismos valores por defecto que Modo Experto (`app.js:755-760`: ocupación 70%, retranqueos 3 m, edificabilidad/plantas vacíos), editable sin recargar ni perder los volúmenes ya dibujados.
2. **[x]** El HUD de métricas aparece con al menos un volumen en escena y desaparece/queda vacío sin ninguno; con parcela real, sus 3 filas solo muestran el máximo cuando está informado. Verificado además un bug real encontrado y corregido durante la verificación: las filas usaban `display:flex` en su clase, que pisaba el `[hidden]` nativo del navegador (mismo patrón de bug ya conocido en este proyecto para `.viewer-compass`) — sin la corrección, "Edificabilidad"/"Plantas" se veían vacías en vez de desaparecer. Corregido con `.sandbox-hud-fila[hidden] { display: none; }`.
3. **[x]** Añadir/escalar/rotar/borrar un volumen actualiza el HUD sin llamada de red — verificado leyendo el código (todo el cálculo es síncrono en cliente) y confirmando que la única petición de red (`/api/validar-urbanismo`) solo se dispara desde `reconciliarConBackend()`, llamada exclusivamente al pulsar "Generar plantas con IA".
4. **[x]** Los números del HUD coinciden exactamente con `POST /api/validar-urbanismo`: verificado con un volumen 60×60×3 sobre una parcela de 3618 m² — cliente y backend dieron **ambos** `ocupacion_pct: 99.50248756218906` y `edificabilidad_real: 2.985074626865672`, cifra a cifra.
5. **[x]** Retranqueos: el mismo volumen 60×60 (cuyas esquinas rotadas caen fuera del polígono real de 3618 m²) se resaltó en rojo (`0xe0523f`, `volumenInvadeRetranqueo() === true`); con `retranqueos_m` puesto a `null` (no evaluable), el mismo volumen dejó de mostrar rojo — aislando correctamente el chequeo de retranqueos del de agregado.
6. **[x]** Exceso agregado: con el mismo volumen (ocupación 100% de 70%) y sin retranqueo evaluable, el volumen se resaltó en naranja (`0xf2994a`, `MAT_VOLUMEN_AGREGADO`) — confirmando la prioridad `seleccionado > retranqueo > agregado > normal` en los 3 estados posibles.
7. **[x]** En Laboratorio y con un punto real sin parcela catastral exacta (probado con `40.5320326,-3.6354938`, el mismo punto de una prueba anterior de esta sesión que ya no resolvía Catastro), el HUD mostró el aviso explícito "Sin datos reales de parcela (Catastro)..." sin ningún porcentaje.
8. **[x]** "Generar plantas con IA" sigue funcionando exactamente igual: verificado con un `onGenerar` de prueba que recibió `{forma: "rectangular", plantas: 3, superficie_m2: 120}` igual que antes de este PRD, y `read_network_requests` confirmó la llamada aditiva a `/api/validar-urbanismo` (200 OK) en paralelo, sin retrasar ni alterar el callback.
9. **[x]** Cero regresión: volúmenes, panel de edición, toolbar (Isométrica/Planta/Sombras), contorno de parcela y ortofoto siguen funcionando; consola sin errores tras recarga limpia con la versión final (sin instrumentación de depuración).

## 9. Riesgos

- **Duplicación de fórmulas (cliente + `evaluator.py`).** Es una decisión deliberada por "arquitectura ligera" (encargo explícito), no un descuido — pero es exactamente el mismo patrón de riesgo que ya causó un bug real en este proyecto (`evaluator._is_adjacent` vs. `circulation._rooms_are_connected`, documentado en `TECH_REVIEW.md` Bug #2: dos implementaciones del mismo concepto que divergen con el tiempo). Mitigación: la llamada de reconciliación de §7.6 existe precisamente para detectar esa deriva pronto, y el código cliente lleva un comentario con referencia cruzada exacta a la función de `evaluator.py` que replica.
- **El chequeo de retranqueos contra el polígono real es MEJOR que `evaluate_retranqueos` (proxy rectangular), no equivalente** — esto puede crear una inconsistencia visible si el mismo proyecto se valida más tarde en Modo Experto/`/api/generar`, que seguirá usando el proxy rectangular antiguo. Igual que con la adyacencia acústica, se deja constancia aquí explícitamente en vez de dejar que se descubra por accidente: backportear el chequeo de polígono real a `evaluate_retranqueos` es trabajo futuro razonable, fuera de alcance de este PRD.
- **Ocupación/edificabilidad por suma de huellas, no por unión geométrica real** (§6): sobreestima si hay volúmenes solapados. Aceptable porque solapar volúmenes deliberadamente no es un caso de uso real del Sandbox hoy, pero debe quedar documentado en el propio código, no solo aquí.
- **Atribución del "volumen causante" del exceso agregado es una heurística** (el último modificado), no una verdad matemática única — con varios volúmenes ya por encima del límite, cuál se resalta depende del orden de edición, no hay una única respuesta "correcta". Se explica así en la UI (tooltip), no se presenta como un hecho objetivo.
- **Nuevo endpoint público sin autenticación** (`POST /api/validar-urbanismo`): mismo nivel de exposición que el resto de la API hoy (`TECH_REVIEW.md` ya señala la ausencia total de autenticación como riesgo transversal, no específico de este PRD) — no se introduce un riesgo nuevo, se hereda el ya conocido.

## 10. Impacto sobre módulos existentes

- `static/viewer-sandbox.js`: nuevo panel de límites urbanísticos, nuevo HUD de métricas, nueva función de cálculo agregado (llamada tras cada uno de los 4 puntos ya existentes de añadir/escalar/rotar/borrar), nuevo chequeo de retranqueos contra `body.geometria_parcela`, nuevo material de aviso con prioridad frente a `MAT_VOLUMEN_SELECCIONADO`, nueva llamada de reconciliación antes de `onGenerarCallback`.
- `static/style.css`: estilos del nuevo panel/HUD (mismo lenguaje visual que `.sandbox-panel`/`.sandbox-toolbar` ya existentes).
- `app.py`: nuevo endpoint `POST /api/validar-urbanismo`, importa y reutiliza `evaluate_solar_occupation`/`evaluate_buildability`/`evaluate_max_floors` de `analyzer/evaluator.py` (ya importadas en el módulo) — cero lógica normativa nueva en Python.
- `static/index.html`: bump de cache-busting.
- Ningún cambio en `analyzer/evaluator.py`, `analyzer/sitio.py`, `viewer-edificio.js`, ni en el flujo de Modo Experto/Entrevista/`/api/generar` ya existentes.

## 11. Plan de implementación dividido en pequeñas tareas

1. **Backend**: endpoint `POST /api/validar-urbanismo` en `app.py`, reutilizando las 3 funciones de `evaluator.py` ya importadas; sin nueva lógica de negocio.
2. **Panel de límites urbanísticos** en `viewer-sandbox.js`/`index.html`/`style.css`: 4 campos, valores por defecto, estado en memoria del módulo (no persistido).
3. **Cálculo agregado en cliente**: función que recorre `volumenes`, suma huellas/superficie construida, calcula los 3 ratios — con comentario de referencia cruzada a `evaluator.py`.
4. **HUD de métricas**: marcado + estilos + función de render, llamada tras cada cambio relevante.
5. **Chequeo de retranqueos contra el polígono real**: distancia punto-segmento de cada esquina rotada de cada volumen a cada arista del polígono de `geometria_parcela`.
6. **Material de aviso + política de prioridad** frente a la selección existente; atribución del "volumen causante" del exceso agregado.
7. **Reconciliación con el backend** antes de `onGenerarCallback`, con `console.warn` en caso de discrepancia.
8. **Verificación en vivo** (Chrome): los 9 criterios de aceptación de §8. Bump de cache-busting. Cierre del PRD.

## 12. Plan de pruebas

- Verificación manual en navegador real, mismo criterio que el resto de este proyecto (sin suite de tests de frontend todavía).
- `python -m py_compile app.py` tras el nuevo endpoint.
- `node --input-type=module --check` sobre `viewer-sandbox.js` tras cada edición.
- Casos a verificar en vivo: los 5 de §5, más los límite marcados como verificables en §6 (solape de volúmenes documentado como aproximación, rotación de volumen cerca del borde, ningún límite informado, polígono degenerado, borrar el volumen atribuido).

## 13. Métricas para medir el éxito

Sin instrumentación de analítica todavía — el criterio de éxito es cualitativo: Pablo confirma que el Sandbox deja de sentirse como "una demo bonita" y empieza a sentirse como una herramienta de validación real, cerrando la brecha que señalan `MOAT_ANALYSIS.md` y `DESTROY_ARCHMUSE.md`.

## 14. Posibles motivos para NO implementar la idea

- El Sandbox es, por diseño explícito de su propio docstring, una herramienta de boceto rápido — no pretende sustituir el análisis completo de `/api/generar`/`/api/analizar`. Añadir un HUD normativo aquí puede dar una falsa sensación de "esto ya está validado del todo" cuando en realidad son solo 3 de las decenas de reglas reales del motor (nada de CTE, nada de habitaciones, nada de accesibilidad). Mitigación ya incorporada: el HUD solo habla de urbanismo de edificio, nunca de "cumplimiento normativo" en general — pero merece un texto explícito en la UI que lo deje claro, no solo en este documento.
- El panel de límites urbanísticos duplica un formulario que ya existe en Modo Experto — dos sitios donde declarar el mismo dato es, en sí mismo, una fuente de inconsistencia (¿qué pasa si el arquitecto los declara distinto en cada uno?). Se acepta este PRD porque el Sandbox ya alimenta a Modo Experto con `solar.superficie_m2`/`solar.forma`/`edificio.plantas` al pulsar "Generar" (`entrevista.js:953-957`) — el mismo patrón podría extenderse para que los límites urbanísticos también viajen de uno a otro, pero eso es una mejora futura razonable, no parte de este alcance.
- Alternativa más barata: no construir el panel de límites en el Sandbox y, en su lugar, solo mostrar el HUD cuando el Sandbox se abre DESDE Modo Experto con esos datos ya declarados (en vez de siempre, con un panel nuevo). Se descarta porque hoy el Sandbox solo se abre ANTES de Modo Experto (nunca después, `entrevista.js:936-962`), así que esa alternativa dejaría el HUD sin usarse casi nunca — el panel propio es necesario para que la conexión 3D↔hallazgos exista en el momento en que de verdad se dibuja.

---

**Decisión:** Implementado 2026-08-16 — alcance completo (§11, tareas 1-8), verificado en vivo con datos reales de Catastro.
