# PRD — Resiliencia Catastro: caché ampliada y reintentos por timeout

**Estado:** Implementado (alcance §14) · **Fecha:** 2026-08-17 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (vía "EJECUCIÓN DE PRD")

---

## 0. Nota de proceso

Encargo recibido: "MEJORA DE RESILIENCIA EN PASO 0: CACHÉ LOCAL Y RETRY AUTOMÁTICO PARA CATASTRO", con tres instrucciones literales (caché en `analyzer/sitio.py`, retry por timeout con buffer creciente, caché "por proximidad" entre clics cercanos). Es una capacidad nueva (dos mecanismos de resiliencia que no existen hoy tal como se piden), no una corrección de bug ni una tarea ya planificada en `REFACTOR_MASTERPLAN.md` — así que, según la regla de proceso del proyecto, este PRD va primero y el código después de que Pablo lo apruebe.

Antes de diseñar la solución, este documento dice explícitamente qué de lo pedido **ya existe** (para no duplicarlo) y dónde el encargo, tal cual está escrito, choca con una decisión de arquitectura ya tomada y documentada en el propio código.

## 1. Problema que resuelve

Dos dolores reales, ya vistos en vivo en esta misma sesión:

1. **`/api/entorno-3d-punto` y `/api/normativa-urbanistica-punto` no cachean nada.** Cada vez que se abre el Sandbox sobre una parcela ya consultada en el Paso 0 (o ya abierta antes), se repite la consulta completa a Catastro + Overpass desde cero — con el mismo coste y el mismo riesgo de timeout que la primera vez, aunque los datos no hayan cambiado. Esto es un gap real, no percibido: `/api/analizar-sitio` (Paso 0) SÍ cachea; estos otros dos endpoints (añadidos después, ver `docs/prd/2026-08-16-sandbox-navegacion-profesional-y-lindes.md` y `docs/prd/2026-08-16-integracion-normativa-catastro-pgou.md`) se quedaron fuera de ese mecanismo.
2. **Cuando Catastro/Overpass están genuinamente lentos (degradación externa, ya documentada varias veces en esta sesión — 40-90s+, a veces sin respuesta ni a 120s), hoy la única redundancia es la espiral de proximidad de `analyzer/sitio.py` (`_referencia_por_proximidad`), y solo cubre "Catastro no tiene parcela en el punto exacto" — no cubre "la petición ha tardado demasiado".** Un timeout de red hoy sube tal cual como error, sin ningún reintento adicional.

## 2. Usuario afectado

El arquitecto que ya ha localizado su parcela (Paso 0) y entra y sale del Sandbox varias veces en la misma sesión de trabajo, o vuelve más tarde al mismo proyecto — hoy paga el coste completo de red cada vez.

## 3. Objetivo de negocio

Menos fricción visible = menos abandono en el momento más frágil del flujo (selección de parcela, ya identificado en sesiones anteriores como el punto de mayor volatilidad de servicios externos). No depende de terceros para mejorar.

## 4. Objetivo técnico

- Una segunda consulta (Sandbox, o un segundo proyecto sobre la misma parcela) sobre una parcela ya resuelta con éxito no debe volver a llamar a Catastro/Overpass.
- Un timeout transitorio en la consulta puntual a Catastro obtiene un segundo intento acotado antes de declararse fallo, sin disparar el problema ya conocido de "el spinner no termina de cargar nada" (ver `docs/prd/2026-08-15-...`, fix ya aplicado).

## 5. Lo que YA EXISTE (no reinventar)

- **Caché por parcela real, persistente (SQLite), ya en producción**: `analyzer/storage.py` (`guardar_sitio`/`obtener_sitio_por_clave`), consumida hoy solo por `/api/analizar-sitio` en `app.py`. Clave: referencia catastral si se conoce, si no `"%.4f,%.4f" % (lat, lon)` (~11 m de precisión). Sin TTL — deliberado y correcto: una parcela catastral no cambia de un día para otro.
- **Reintento por proximidad ya existente, pero con un disparador distinto al que pide este encargo**: `_referencia_desde_coordenadas_resiliente` (`analyzer/sitio.py`, PRD `2026-08-16-resiliencia-catastro-paso0.md`) reintenta en espiral (5/10/20 m) cuando el punto exacto falla — **por CUALQUIER `ErrorDeSitio`, incluido un timeout** — pero solo protege la resolución de referencia catastral por coordenadas, no la geometría WFS ni las 4 consultas Overpass que vienen después.
- **Decisión de arquitectura ya tomada y escrita explícitamente en el módulo** (`analyzer/sitio.py`, cabecera del fichero): *"Caché por parcela (PRD §4/§8): vive en `analyzer/storage.py`/`app.py`, no aquí — este módulo es una función pura, sin estado."* Esto no es un descuido — es una decisión deliberada para poder testear `analyzer/sitio.py` como funciones puras sin mockear una base de datos.

## 6. Casos límite

- Dos coordenadas "cercanas" que caen en parcelas catastrales DISTINTAS (habitual en cascos urbanos densos, parcelas de pocos metros de frente) — un acierto de caché "por proximidad" demasiado generoso devolvería la parcela equivocada como si fuera la del punto pedido. Esto es exactamente el tipo de dato fabricado/engañoso que este proyecto evita en todo el resto del código (ver `analyzer/normativa_madrid.py`, `sitio.py` spiral, etc.) — un acierto de caché no es "inventar un valor", pero el efecto observable para el arquitecto es el mismo: un dato mostrado como real que no corresponde al punto exacto que pinchó.
- Retry-por-timeout mal acotado alarga el peor caso en vez de acortarlo — ya hay un incidente documentado esta sesión de "el spinner no termina de cargar nada" causado por reintentos no acotados en Overpass.
- Caché sin invalidación: si Catastro corrige una geometría (recalificación, segregación de parcela), sin TTL el arquitecto seguiría viendo la geometría vieja indefinidamente. Riesgo bajo (estos cambios son infrecuentes y ya así es como funciona hoy para `/api/analizar-sitio`), pero debe quedar documentado, no implícito.

## 7. Flujo del usuario

Sin cambios visibles de flujo — es una mejora de lo que pasa "detrás" cuando ya se pinchó un punto. El único cambio observable: la segunda vez que se abre el Sandbox sobre la misma parcela (o un proyecto ya visitado antes), carga más rápido.

## 8. Criterios de aceptación

1. Abrir el Sandbox dos veces seguidas sobre la misma parcela hace **una sola** llamada real a Catastro/Overpass (verificable con `read_network_requests` / logs); la segunda se sirve de `storage.sitios`.
2. Un timeout transitorio en la consulta puntual de geometría WFS obtiene un reintento (máximo 1, con backoff corto) antes de propagarse como error — sin superar el presupuesto total ya establecido para el Paso 0 (60s cliente) ni el nuevo de Sandbox (45s, ver arreglo anterior).
3. Ningún acierto de caché "por proximidad" cruza el límite de una parcela real: se implementa solo como caché EXACTA por celda (mismo criterio que ya usa `/api/analizar-sitio`), nunca como búsqueda difusa por radio.
4. `analyzer/sitio.py` sigue siendo funciones puras sin estado — la caché se sigue resolviendo en la capa de `app.py`/`storage.py`, no dentro del módulo.

## 9. Riesgos

- **Riesgo principal, ya señalado en §6**: implementar la caché "por proximidad" tal como está escrita en el encargo (radio difuso, no celda exacta) puede servir la parcela equivocada en zonas de parcelación fina — inaceptable dado el principio de "nunca mostrar un dato que no corresponde exactamente al punto real" que gobierna el resto del proyecto.
- Poner la caché dentro de `analyzer/sitio.py` (tal como pide el encargo, punto 1) contradice una decisión de arquitectura ya tomada y documentada — hacerlo crea DOS mecanismos de caché paralelos con claves y semántica distintas, más difíciles de razonar juntos que uno solo extendido.
- Compite con tiempo de otras tareas de `REFACTOR_MASTERPLAN.md`, aunque es pequeña.

## 10. Impacto sobre módulos existentes

- `app.py`: `entorno_3d_punto()` y `normativa_urbanistica_punto()` ganan una consulta a `storage.sitios`/nueva tabla antes de llamar a `analyzer/*`, igual que ya hace `/api/analizar-sitio`.
- `analyzer/storage.py`: posible clave de caché nueva o reuso de `sitios` según qué se decida cachear (¿el `_entorno_3d_para` completo, con colindantes? ¿o solo `geometria_parcela`, reusando la fila que ya deja `/api/analizar-sitio`?) — decisión de diseño para la fase de implementación, no de este PRD.
- `analyzer/sitio.py`: el reintento por timeout se añade en el mismo punto que ya existe la espiral de proximidad (`_referencia_desde_coordenadas_resiliente` y, si se decide extender, la llamada a la geometría WFS) — sin tocar la firma pública de `obtener_datos_parcela`/`geometria_parcela_por_coordenadas`.

## 11. Plan de implementación dividido en pequeñas tareas

*(Solo tras aprobación explícita de Pablo sobre el enfoque de §14.)*

1. Extender `entorno_3d_punto()`/`normativa_urbanistica_punto()` en `app.py` para consultar `storage.sitios` (clave `"%.4f,%.4f"`) antes de llamar a `analyzer/*`, y guardar el resultado tras un éxito — mismo patrón exacto que `/api/analizar-sitio`.
2. Reintento acotado (1 intento extra, mismo timeout, sin buffer creciente — ver §14) en la llamada WFS de geometría dentro de `analyzer/sitio.py`, solo ante error de red/timeout (no ante "sin parcela aquí", que ya tiene su propio camino con la espiral).
3. Test manual: dos aperturas seguidas del Sandbox sobre la misma parcela, verificar con `read_network_requests` que la segunda no llama a Catastro/Overpass.
4. Actualizar el docstring de `analyzer/sitio.py` (§5 de este documento) para que siga reflejando la realidad tras el cambio.

## 12. Plan de pruebas

Manual, contra el servidor local real (mismo criterio que el resto de esta sesión): abrir Sandbox dos veces sobre la misma parcela y confirmar por red que la segunda no sale a Catastro/Overpass; forzar un timeout artificial (bajar el timeout a un valor imposible temporalmente) para confirmar que el reintento se dispara y que el error final, si llega, sigue siendo honesto (nunca inventa geometría).

## 13. Métricas para medir el éxito

Tiempo de apertura del Sandbox en la segunda visita a una misma parcela (objetivo: <1s, servido de caché) frente a la primera (varios segundos a minuto, según Overpass).

## 14. Posibles motivos para NO implementar la idea tal como está escrita

**La idea tiene valor real — el problema #1 de §1 (Sandbox/normativa sin caché) es un gap genuino que vale la pena cerrar.** Pero dos de las tres instrucciones literales del encargo, tal como están escritas, no deberían implementarse así:

- **"Añade caché en `analyzer/sitio.py`"**: contradice una decisión de arquitectura ya tomada y escrita en el propio módulo (§5). La alternativa mejor es extender la caché que YA EXISTE en `app.py`/`storage.py` a los dos endpoints que hoy se quedaron fuera (`entorno-3d-punto`, `normativa-urbanistica-punto`) — mismo mecanismo, una sola fuente de verdad, sin tocar la pureza de `analyzer/sitio.py`.
- **"Caché por proximidad" (punto 3 del encargo, "un punto cercano ya consultado")**: tal como está escrito (radio difuso) arriesga servir la parcela equivocada en parcelación fina — ver §6/§9. La caché EXACTA por celda de ~11 m que ya existe cubre el caso real de "el arquitecto pincha dos veces casi el mismo sitio" sin ese riesgo; ampliar el radio de "cercano" no aporta suficiente valor extra para asumir ese riesgo.
- **"Retry aumentando el buffer de búsqueda"**: para la resolución de RC por coordenadas esto YA EXISTE (espiral de proximidad, PRD anterior) y ya se dispara ante timeout. Lo que falta es un reintento simple (mismo buffer, no creciente) en la llamada de geometría WFS — aumentar el buffer de búsqueda en cada reintento no tiene un análogo claro en una consulta WFS por punto exacto (no es una búsqueda por área que admita "buffer"), así que esa parte del encargo parece asumir un mecanismo que no encaja con cómo funciona el servicio real.

**Recomendación**: aprobar una versión reducida — extender la caché existente a los dos endpoints sin caché (alto valor, bajo riesgo) + un reintento simple y acotado por timeout en la geometría WFS — y descartar explícitamente la caché "por proximidad" difusa.

---

## 15. Cierre — implementación y verificación en vivo (2026-08-17)

Implementado exactamente el alcance reducido de §14 (no la versión literal del encargo original): caché extendida a los dos endpoints del Sandbox usando el mismo mecanismo SQLite ya existente, más un reintento simple (mismo timeout, sin buffer creciente) ante timeout real en la descarga WFS. Sin caché por proximidad difusa, sin caché dentro de `analyzer/sitio.py`.

**1. Caché (`app.py`)**: `entorno_3d_punto()` y `normativa_urbanistica_punto()` consultan `obtener_sitio_por_clave` antes de llamar a `analyzer/*`, y guardan con `guardar_sitio` tras la primera resolución — mismo patrón exacto que `/api/analizar-sitio`, reutilizando la tabla `sitios` (`storage.py`) con un prefijo de clave propio por endpoint (`"entorno3d:%.4f,%.4f"`, `"normativa_madrid:%.4f,%.4f"`) para no mezclar formas de dato distintas bajo la misma clave que ya usa el Paso 0.

**2. Reintento por timeout (`analyzer/sitio.py`)**: nueva `_es_timeout(exc)` distingue un timeout de red real de un `HTTPError` (respuesta real del servidor, p. ej. 404) o un error de certificado — solo el primero se reintenta. `_get()` gana un parámetro opcional `intentos_ante_timeout` (por defecto 1, **sin cambio de comportamiento para el resto de los ~15 llamadores existentes** de esta función); solo `_geometria_parcela_catastro` pide 2 intentos.

**Verificado en vivo:**
- `_es_timeout`: 4 casos (`TimeoutError` directo, `URLError` con `reason=TimeoutError`, `URLError` con otra razón, `HTTPError` 404) — los 4 clasificados correctamente.
- Reintento real: servidor HTTP local (`ThreadingHTTPServer`) que falla por timeout en el primer intento y responde bien en el segundo — `_get(..., intentos_ante_timeout=2)` recupera el dato, 2 peticiones reales, 0.53s totales. Confirmado también que el comportamiento POR DEFECTO (sin el parámetro) sigue sin reintentar — 1 sola petición, mismo `ErrorDeSitio` de siempre.
- Caché de `/api/entorno-3d-punto` y `/api/normativa-urbanistica-punto`: verificado con el cliente de pruebas de Flask (`test_client`), con la función real sustituida por una que cuenta invocaciones — 1ª llamada `cache:false` (invoca la función real una vez), 2ª llamada sobre las mismas coordenadas `cache:true`, **cero** invocaciones adicionales, datos idénticos.
- Confirmado también contra el servidor real en marcha (no solo el test client): `/api/normativa-urbanistica-punto` con una coordenada fuera de Madrid, dos peticiones `curl` seguidas → 1ª `cache:false`, 2ª `cache:true`, mismo contenido.
- Caso feliz sin regresión: `_geometria_parcela_catastro` contra una RC real (Palacio de Cibeles) sigue resolviendo en 0.16s, sin disparar ningún reintento innecesario.
- **No pude completar una prueba end-to-end de `/api/entorno-3d-punto` contra Catastro/Overpass reales**: el servicio de Overpass está genuinamente degradado ahora mismo (mismo problema externo ya documentado varias veces en esta sesión) — una petición real tardó >90s sin responder. Por eso la verificación de la caché de este endpoint se hizo con la función externa sustituida por una versión de prueba (arriba), que prueba exactamente el código nuevo (la lógica de caché) sin depender de la disponibilidad de un servicio externo fuera de mi control.

Sin regresiones: `python -m py_compile` limpio en los tres ficheros tocados.

---

**Decisión:** Implementado 2026-08-17 con el alcance reducido de §14 (caché extendida + reintento simple), verificado en vivo salvo el tramo bloqueado por la degradación externa de Overpass — misma limitación externa, no de este cambio.
