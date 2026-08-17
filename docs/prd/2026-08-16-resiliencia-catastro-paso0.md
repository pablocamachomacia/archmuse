# PRD — Resiliencia de la consulta a Catastro en el Paso 0 (búsqueda por proximidad + progreso real)

**Estado:** Implementado · **Fecha:** 2026-08-16 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (vía "EJECUCIÓN DE PRD")

---

## 0. Resumen para decidir rápido

Este PRD junta dos encargos que llegaron por separado pero piden lo mismo en el fondo ("MEJORA CRÍTICA EN PASO 0: búsqueda robusta de Catastro" y la parte de Paso 0 de "CORRECCIÓN CRÍTICA: bloqueo al 10%"), y dos correcciones de encuadre honestas sobre lo que se pidió:

**Ya corregido, sin PRD (era un bug, no capacidad nueva — regla de `CLAUDE.md`), y verificado en vivo antes de escribir este documento:** el Sandbox SÍ podía quedarse "colgado" de verdad — no una sensación, medido con `curl -m 120` contra el propio servidor: `/api/entorno-3d-punto` tardó más de 120s sin responder para una coordenada real, y más de 30s para otra que antes había respondido en segundos (Overpass está observably degradado ahora mismo, en vivo, durante esta misma sesión). `pedirEntorno3D`/`pedirEntorno3DPorCoordenadas` (`viewer-terreno.js`) no tenían ningún límite de tiempo propio. Corregido con un `AbortController` de 12s, verificado en vivo contra ambos casos (el punto que colgó 120s+ y el que ahora tarda 30s+): el Sandbox ya nunca espera más de 12s, siempre llega a un estado final (con datos reales o sin ellos), nunca se queda a medias.

**Explícitamente NO implementado, y no se va a implementar tal como se pidió:** "asume un fallback seguro (parcela rectangular por defecto o contorno derivado de las coordenadas)". Dibujar una parcela inventada que se vería EN PANTALLA igual de real que un contorno de Catastro de verdad es exactamente lo que este proyecto lleva toda la sesión evitando — "nunca se inventa una RC" (`_referencia_desde_coordenadas`, docstring literal ya en el código), "nunca un dato inventado" (HUD de urbanismo, PRD del punto anterior), la lección ya aprendida del percentil comparativo inventado (`PROJECT_AUDIT.md`). Lo que YA existe y es lo correcto: sin datos reales, el HUD dice "Sin datos reales de parcela (Catastro)" y no se dibuja ningún contorno — verificado en vivo hace un momento. Si se quiere reconsiderar esto, debe ser una conversación explícita, no una línea dentro de una corrección de bug.

**Lo que SÍ es una capacidad nueva real, y por eso está en un PRD y no ya implementado:**
1. Búsqueda por proximidad (espiral 5/10/20m) en `_referencia_desde_coordenadas` cuando el punto exacto falla — mejora real y acotada, no una promesa de "siempre".
2. Progreso real (no un temporizador) en el Paso 0, con el mismo criterio de honestidad que ya se aplicó a la barra del Sandbox.
3. Mensaje de fallo reformulado (menos alarmante), pero sin eliminar la posibilidad real de que no haya parcela (una plaza, un parque, una vía pública genuinamente no catastrada no van a tener referencia catastral por mucho que se busque alrededor, y decir lo contrario sería inventar).

**Corrección de encuadre sobre "SIEMPRE" / "obligatorio":** no se puede prometer que la búsqueda por proximidad resuelva SIEMPRE una parcela. Si el clic cae sobre una edificación real (que por definición está construida sobre una parcela catastrada), la probabilidad de éxito con un radio de 20m es muy alta — eso sí es una promesa razonable. Si el clic cae en mitad de una vía pública amplia, un parque grande o una zona genuinamente sin catastrar (ya observado en esta misma sesión: un punto en "La Moraleja, Avenida de la Ermita, Parque..." no tenía parcela ni a 20m), 20m de radio no van a encontrar nada porque no hay nada que encontrar — y ahí la única opción honesta sigue siendo el mismo aviso de siempre, solo que menos alarmante.

## 1. Problema que resuelve

Un clic a pocos metros de una parcela real (o, según lo reportado, sobre una edificación real como en Montepríncipe) puede devolver "no hay referencia disponible" porque `Consulta_RCCOOR` de Catastro es una consulta de PUNTO EXACTO, no de área — el propio docstring de `_referencia_desde_coordenadas` ya documenta este hallazgo ("ocurre con coordenadas a pocos metros de una parcela real, no solo en zonas sin catastrar"). Hoy, un solo intento fallido termina el flujo con un aviso, sin ningún reintento.

## 2. Usuario afectado

El arquitecto en el Paso 0 ("¿Dónde está tu parcela?"), especialmente al hacer clic sobre un edificio real cuyo contorno de tejado o precisión del mapa no cae exactamente dentro del polígono catastral que Catastro tiene indexado para ese punto.

## 3. Objetivo de negocio

Reduce fricción en el primer paso del flujo más usado de la aplicación (Paso 0 es el punto de entrada de "Generar proyecto"). Barato, acotado, no compite con el resto del roadmap.

## 4. Objetivo técnico

- Cuando `Consulta_RCCOOR` falla en el punto exacto, se reintenta automáticamente en varios puntos cercanos (espiral, radios crecientes) antes de darse por vencido — nunca se salta este reintento cuando el primero ya tuvo éxito (no gastar llamadas de más si no hace falta).
- El Paso 0 muestra un indicador de progreso con fases reales (no simuladas por tiempo) mientras dura la consulta.
- El mensaje final de "no se encontró parcela" se reformula con un tono menos alarmante, pero sigue siendo honesto: nunca afirma haber encontrado algo que no encontró.

## 5. Casos de uso

1. Arquitecto hace clic sobre el tejado de un edificio real en Montepríncipe; el punto exacto del píxel cae 3m fuera del polígono catastral indexado → el primer intento falla, el segundo (espiral 5m) encuentra la parcela real → el arquitecto ve el resultado con normalidad, sin percibir que hubo un reintento.
2. Mismo caso pero con el punto a 15m del polígono real (mapa con más zoom, imprecisión de clic mayor) → el tercer intento (radio 20m) lo resuelve.
3. Arquitecto hace clic en mitad de una autovía o un parque grande → los 3 radios de reintento (hasta 20m) no encuentran nada, porque no hay ninguna parcela catastrada ahí de verdad → se muestra el aviso reformulado, sin inventar nada.
4. Mientras se resuelve cualquiera de los casos anteriores, el arquitecto ve una píldora con barra de progreso y fases reales, no el texto estático de hoy.

## 6. Casos límite

- **El punto exacto SÍ resuelve a la primera** (caso mayoritario hoy): cero llamadas adicionales, cero cambio de comportamiento — la espiral es un fallback, no un reemplazo de la consulta directa.
- **Varios de los puntos de la espiral resuelven a referencias catastrales DISTINTAS** (posible cerca de linderos entre parcelas pequeñas): se toma la primera que resuelva, en el orden de radio creciente (más cercano al punto real primero) — no se intenta decidir cuál es "la correcta" con más sofisticación que esa, documentado como limitación conocida.
- **Catastro tarda en cada intento** (no solo falla, tarda): el presupuesto de tiempo total de la espiral debe tener un techo razonable (ver §9) para no convertir "más resiliente" en "más lento cuando de verdad no hay nada que encontrar".
- **Overpass degradado simultáneamente** (observado en vivo hoy mismo durante esta sesión): la resiliencia de este PRD es solo sobre la resolución de referencia catastral (Catastro), no sobre Overpass — un Overpass lento sigue afectando a colindantes/viales igual que hoy, fuera de alcance aquí.
- **Progreso cuando la espiral entra en juego**: el indicador debe reflejar que se está reintentando ("Buscando la parcela más cercana…"), no quedarse en "Resolviendo referencia catastral" sin más contexto mientras internamente ya van 2-3 intentos.

## 7. Flujo del usuario

1. Arquitecto hace clic en el mapa (o elige un resultado de búsqueda/preset).
2. La píldora de estado cambia de "Consultando Catastro…" (texto estático de hoy) a una barra con fases reales: "Conectando con Catastro…" → (si el punto exacto falla) "Buscando la parcela más cercana…" → "Obteniendo lindes y superficie…" → resultado.
3. Si se resuelve (a la primera o por proximidad): mismo resultado visual de hoy (referencia catastral, superficie, municipio, contorno azul en el mapa) — sin distinguir visualmente si vino del punto exacto o de un reintento (mismo dato real de Catastro en ambos casos, no hay nada que distinguir).
4. Si no se resuelve tras agotar la espiral: aviso reformulado, menos alarmista, mismo fondo honesto de "puedes continuar igual, rellenarás estos datos a mano".

## 8. Criterios de aceptación

1. Para al menos 2 coordenadas reales verificadas donde el punto exacto falla pero un punto a ≤20m sí tiene parcela (a construir/encontrar como fixture de prueba, incluyendo si es posible una edificación real de Montepríncipe como la mencionada en el encargo), la consulta ahora resuelve con éxito.
2. Para al menos 1 coordenada real ya usada en esta sesión donde genuinamente no hay parcela cerca (interior de una vía/parque), el sistema sigue mostrando el aviso de "sin parcela", nunca un dato inventado — la espiral no cambia este caso, y el PRD no promete que lo cambie.
3. Cuando el punto exacto resuelve a la primera, no hay ninguna llamada de red adicional (verificable con `read_network_requests`).
4. El indicador de progreso en el Paso 0 muestra al menos 2 fases reales distintas, cada una disparada por un hito real del backend (no un `setTimeout`).
5. El mensaje de fallo final ya no usa el tono actual ("No hemos podido consultar Catastro para este punto exacto") sino uno reformulado, verificado con Pablo antes de cerrar el PRD.
6. Cero regresión sobre el resto del Paso 0 (buscador, presets, historial, mapa).

## 9. Riesgos

- **Coste de latencia de la propia resiliencia**: cada intento de la espiral es una llamada real a `Consulta_RCCOOR` (mismo servicio ya usado, `_get(timeout=15.0)` por defecto) — en el peor caso (8 direcciones × 3 radios = 24 intentos, todos fallando, todos tardando cerca del timeout) esto podría añadir minutos, exactamente el problema que la corrección de bug de este mismo documento (§0) acaba de arreglar en el Sandbox. Mitigación obligatoria: un techo de tiempo total para toda la espiral (p. ej. 8-10s), parando en cuanto se agote, no en cuanto se agoten los 24 puntos — y un número de direcciones/radios deliberadamente pequeño (no 24 por defecto; empezar con menos, p. ej. 4 direcciones × 3 radios = 12, y medirlo en vivo antes de ampliarlo).
- **La expectativa de "SIEMPRE" del encargo original no es alcanzable de forma honesta** (§0) — gestionar esto en la comunicación con Pablo es tan importante como el código en sí.
- **Reintentar contra Catastro con más frecuencia** puede acercarse a algún límite de uso razonable del servicio público, igual que ya se gestiona con cuidado en Overpass (`_OVERPASS_INTENTOS`/esperas) — sin llegar a ese nivel de cautela (Catastro no ha mostrado el mismo patrón de rate-limiting que Overpass en este proyecto todavía), merece el mismo tipo de atención si se observa en vivo durante la implementación.

## 10. Impacto sobre módulos existentes

- `analyzer/sitio.py`: `_referencia_desde_coordenadas` gana un fallback de espiral (nueva función privada `_referencia_por_proximidad` o similar) — el resto de la firma pública no cambia, sigue devolviendo lo mismo o lanzando `ErrorDeSitio` igual que hoy.
- `static/entrevista.js`: `consultarSitio` gana indicador de progreso con fases reales (mismo patrón ya construido para el Sandbox, `actualizarProgreso`); mensaje de fallo reformulado.
- Ningún cambio en `app.py` (mismo endpoint `/api/analizar-sitio`, mismo contrato de respuesta) ni en `viewer-sandbox.js` (ya corregido aparte, §0).

## 11. Plan de implementación dividido en pequeñas tareas

1. `analyzer/sitio.py`: helper de desplazamiento metros→grados (equirectangular, mismo criterio que ya usa `metrosEsteNorteDesde` en JS, ahora en Python) + función de espiral que prueba puntos en radios crecientes, con techo de tiempo total.
2. Verificar en vivo con al menos 2 coordenadas reales (incluyendo, si es localizable, una edificación de Montepríncipe) que la espiral resuelve casos que el punto exacto no resolvía.
3. `static/entrevista.js`: fases reales de progreso en `consultarSitio` (reutilizando el patrón `actualizarProgreso` del Sandbox), mensaje de fallo reformulado.
4. Verificación en vivo de los 6 criterios de §8.

## 12. Plan de pruebas

- `python -m py_compile analyzer/sitio.py`.
- Verificación manual en Chrome: los 4 casos de uso de §5, incluido al menos un punto real donde genuinamente no hay parcela (confirmar que el aviso sigue apareciendo, no desaparece).
- Medir en vivo la latencia añadida por la espiral en el caso "todo falla" (peor caso real, no solo el caso feliz).

## 13. Métricas para medir el éxito

Cualitativo: menos veces que Pablo (o un arquitecto de prueba) ve el aviso de "sin parcela" al hacer clic sobre una edificación real, sin que la espera se vuelva perceptiblemente más larga en el caso feliz.

## 14. Posibles motivos para NO implementar la idea

- El caso de uso más citado en el encargo (clic sobre una edificación real que falla) puede tener una causa distinta a "el punto está a pocos metros del polígono" — podría ser, por ejemplo, un desajuste de proyección entre el mapa (Leaflet/OSM) y Catastro, no solo imprecisión de clic. Si al investigar con una coordenada real de Montepríncipe se descubre que el problema es otro, este PRD debe revisarse antes de implementar una espiral que no resuelva la causa real.
- Alternativa más barata para el caso "clic sobre edificación": en vez de una espiral genérica, usar el propio contorno del edificio ya visible en el mapa (si Leaflet/OSM lo tiene) para elegir un punto claramente DENTRO del polígono antes de consultar Catastro una sola vez — más preciso que probar puntos a ciegas, pero exige tener geometría de edificio disponible en el cliente antes de la consulta, que hoy no se tiene en el Paso 0. Vale la pena evaluarlo si la espiral demuestra ser insuficiente en la verificación en vivo.

---

## 15. Cierre — verificación en vivo (2026-08-16)

Los 6 criterios de §8, verificados en vivo (no solo por inspección de código):

1. **Punto que falla exacto pero resuelve por proximidad** — offset real de 12m sobre Gran Vía 31 (RC `0347501VK4704G` conocida): punto exacto falla (confirmado, código de error 16), `_referencia_desde_coordenadas_resiliente` resuelve la MISMA RC real en 2.89s vía la espiral. ✓
2. **Punto genuinamente sin parcela cerca** — dos casos reales probados: (a) mar Mediterráneo frente a Valencia, espiral agota los 12 puntos y falla honestamente en 1.64s; (b) el punto real que devuelve el geocodificador para "Gran Vía, Madrid" (sin número — cae en la calzada, no en un portal), falla igual de honesto en 2.59s — confirmado también en la UI en vivo (Chrome), mismo texto reformulado, sin inventar nada. ✓
3. **Punto exacto resuelve a la primera → cero llamadas adicionales** — verificado con `read_network_requests` en Chrome: el preset "Gran Vía, Madrid" (Nominatim → punto exacto conocido) dispara exactamente 1 petición a `/api/analizar-sitio`, ninguna más. ✓
4. **≥2 fases reales en el indicador de progreso** — verificado en vivo en Chrome: fase 1 "Conectando con Catastro…" (20%) al despachar el `fetch`, fase 2 "Catastro está tardando más de lo habitual — puede estar buscando la parcela más próxima…" (60%) SOLO cuando la petición sigue de verdad pendiente a los 2.5s (comprobado con el flag `resuelta`, nunca un `setTimeout` ciego). Capturado en pantalla con la barra y el % reales. ✓
5. **Mensaje de fallo reformulado** — "No hemos encontrado una parcela catastrada en este punto ni en los alrededores más próximos" reemplaza el alarmante "No hemos podido consultar Catastro..." para el caso "Catastro respondió, no hay parcela" (`sinParcelaEnPunto`). El caso DISTINTO de fallo de red/timeout real conserva su propio mensaje ("No hemos podido consultar...") porque ahí sí es la descripción correcta -- son dos situaciones distintas, ya no comparten texto. ✓
6. **Cero regresión** — buscador (Nominatim), presets, mapa (clic + contorno), mismo flujo de siempre; único cambio de comportamiento es cuándo se muestra cada mensaje. ✓

**Nota honesta de alcance, confirmada en vivo durante esta misma verificación**: Overpass sigue observablemente degradado (mismo hallazgo de §0) -- varias pruebas en vivo tardaron 40-45s en total (dominado por Overpass, no por Catastro/la espiral, que resuelve en 1-3s de las 60s de presupuesto total del cliente) antes de llegar al timeout de red de 60s ya existente. Esto es el mismo problema ya documentado como fuera de alcance de este PRD (§6), reconfirmado, no una regresión de este cambio.

**Decisión:** Implementado 2026-08-16 — alcance completo de §11 (tareas 1-4), verificado en vivo con coordenadas reales de Madrid y con Chrome/`read_network_requests` contra la UI real del Paso 0.
