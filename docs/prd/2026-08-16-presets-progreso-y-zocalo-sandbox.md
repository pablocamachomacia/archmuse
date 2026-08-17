# PRD — Presets de direcciones, barra de progreso % y zócalo de maqueta en el Sandbox

**Estado:** Implementado · **Fecha:** 2026-08-16 · **Fecha de cierre:** 2026-08-16 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (alcance completo, §11 tareas 1-6)

---

## 0. Resumen para decidir rápido

Petición con 3 objetivos independientes entre sí (no comparten código, pueden aprobarse/implementarse por separado):

| # | Objetivo | Backend nuevo | Riesgo principal |
|---|----------|---------------|-------------------|
| 1 | Chips de direcciones destacadas de Madrid en el buscador del Paso 0 | Ninguno — reutiliza `/api/geocodificar` tal cual | Bajo. Cosmético + cableado de eventos ya existentes. |
| 2 | Barra de progreso con % real en el overlay de carga del Sandbox | Ninguno | Medio-bajo. El % es honesto solo si refleja hitos reales del pipeline async ya existente (§6). |
| 3a | Zócalo/base bajo el terreno del Sandbox (estética de maqueta física) | Ninguno | Bajo. Geometría añadida, no sustituye nada. |
| 3b | Filtrar colindantes cuyo footprint se sale del radio útil | Ninguno (filtro solo en cliente) | Medio. Hay un motivo técnico real (ver §1) pero recortar geometría real de Catastro/OSM es una decisión de fidelidad, no solo estética — se marca claramente en §8 qué criterio de corte se usa. |

Los tres objetivos son aditivos sobre `viewer-sandbox.js`/`viewer-terreno.js`/`entrevista.js`/`style.css`. Ninguno toca `viewer-edificio.js`, `app.py`, ni `analyzer/`.

---

## 1. Problema que resuelve

Tres fricciones distintas reportadas sobre el flujo Paso 0 → Sandbox:

1. **Arranque en frío del buscador**: para probar el Sandbox con un sitio real hay que escribir una dirección de memoria. No hay ningún atajo para los tipos de entorno urbano que de verdad interesa comparar en una demo o una prueba rápida (denso/manzana cerrada/torres/residencial unifamiliar).
2. **Opacidad del tiempo de espera**: el overlay de carga del Sandbox (`#sandbox-loading`) ya tiene spinner + texto fijo ("Cargando parcela y entorno 3D…"), pero no dice CUÁNTO queda ni QUÉ está pasando en cada momento del pipeline (Catastro → ortofoto → colindantes → sombra/encuadre), que puede tardar varios segundos reales.
3. **Estética "lámina flotante"**: el terreno del Sandbox (`construirTerrenoOrganico`/`crearGroundNeutro`) es un disco/círculo de grosor cero suspendido en el vacío sin ningún borde visible, y los edificios colindantes que devuelve Overpass pueden extenderse mucho más allá del radio de 180 m que en teoría delimita la consulta (Overpass `around:180` incluye cualquier edificio con AL MENOS un nodo dentro de 180 m — un edificio grande puede tener el resto de su fachada a 300-400 m del centro), lo que ensucia visualmente las esquinas de la escena con volúmenes parciales muy alejados del punto de interés.

## 2. Usuario afectado

El arquitecto que usa el Sandbox para bocetar rápido sobre una parcela real (Paso 0 → Lienzo libre), tanto en uso real como en demos comerciales del producto (los 4 presets pedidos son explícitamente "preparados para proyectos", pensados también para enseñar la herramienta).

## 3. Objetivo de negocio

Reduce fricción de "cold start" en demos (presets) y refuerza la percepción de producto pulido/profesional frente a "prototipo" (progreso real, zócalo de maqueta) — todo esto es percepción y velocidad de prueba, no una capacidad nueva de análisis; no cambia el foso del producto (`MOAT_ANALYSIS.md` ya señala el visor 3D como área de complejidad sin foso propio — esto no lo agrava ni lo resuelve, es pulido de UX sobre lo que ya existe).

## 4. Objetivo técnico

- Un clic en un preset ejecuta el mismo camino que ya ejecuta seleccionar un resultado de búsqueda real (geocodifica → centra mapa → consulta Catastro), sin caminos de código nuevos ni duplicados.
- El overlay de carga del Sandbox muestra un `%` que avanza de forma monótona (nunca retrocede) y refleja hitos reales verificables del pipeline (no una animación falsa por tiempo).
- El terreno del Sandbox se percibe como un objeto físico con espesor, no como una lámina 2D.
- Los edificios colindantes mostrados quedan contenidos dentro de un radio útil coherente con el resto de la escena (mismo criterio que ya usa `ajustarFrustumSombra`: 180 m + margen).

## 5. Casos de uso

1. Pablo abre "Generar proyecto" → Paso 0, hace clic en el chip "Gran Vía, Madrid" → el buscador se rellena, el mapa centra ahí, Catastro se consulta automáticamente, igual que si lo hubiera buscado a mano.
2. Un arquitecto abre el Sandbox sobre una parcela real y ve "35% — Descargando ortofoto de alta resolución…" en vez de un spinner mudo.
3. Un arquitecto abre el Sandbox sin parcela real (Laboratorio): ve el terreno orgánico con un zócalo de base visible bajo el relieve, en vez de un disco flotando en el vacío.
4. Un arquitecto abre el Sandbox sobre una parcela con un edificio colindante grande (p. ej. una manzana completa cuyo centro está a 170 m pero cuya esquina lejana está a 350 m): esa esquina lejana ya no aparece cortando el encuadre.

## 6. Casos límite

- **Preset cuya geocodificación falla o Nominatim no devuelve nada** (CDN/red caída, límite de uso alcanzado): se comporta exactamente como una búsqueda manual fallida hoy (mensaje "No se ha podido buscar esa dirección ahora mismo" en el dropdown) — no se inventa un camino de error nuevo.
- **Preset con varios resultados de Nominatim para el mismo texto** (p. ej. "Gran Vía" existe en más de una ciudad): se usa el primer resultado, igual que ya asume `mostrarResultados` con cualquier búsqueda ambigua — es un comportamiento ya existente, no nuevo, así que las 4 direcciones se escriben con ciudad incluida ("Gran Vía, Madrid") precisamente para minimizar la ambigüedad, no para eliminarla del todo.
- **Progreso cuando NO hay parcela real (Laboratorio)**: no hay pipeline de red que medir — el overlay se cierra igual de rápido que hoy (`loadingEl.hidden = true` inmediato), sin mostrar una barra de 0% a 100% que no correspondería a ninguna espera real.
- **Progreso cuando el mosaico de ortofoto falla pero colindantes sí llegaron** (ruta `.catch()` ya existente en `open()`): el % debe llegar a 100% igual (mismo criterio que hoy: best-effort, nunca se queda "colgado" a mitad).
- **Progreso cuando `pedirEntorno3DPorCoordenadas` falla del todo** (red caída): salta directo a ocultar el overlay, igual que hoy — no tiene sentido fingir hitos intermedios que nunca ocurrieron.
- **Zócalo con terreno orgánico (relieve variable)**: el borde inferior del zócalo debe seguir estando por debajo del punto más bajo del relieve en TODO el radio, no solo en el centro, o se vería el "fondo" del terreno asomando por un lateral en las zonas más bajas.
- **Filtro de colindantes por radio**: se filtra por el CENTROIDE del footprint de cada edificio (no por cada vértice individual) contra el mismo radio que ya usa `ajustarFrustumSombra` (180 m + margen) — un edificio con centroide dentro del radio pero una esquina fuera se conserva completo (cortar un edificio real a la mitad sería peor que dejarlo un poco largo); solo se descarta el edificio completo si su centroide cae fuera.

## 7. Flujo del usuario

**Presets:**
1. Pablo llega a la pantalla "¿Dónde está tu parcela?" (Paso 0).
2. Ve 4 chips bajo el buscador: "Gran Vía, Madrid" / "Calle Velázquez, Madrid" / "Paseo de la Castellana / AZCA, Madrid" / "La Moraleja, Madrid".
3. Clic en un chip → mismo flujo que elegir un resultado de búsqueda: `inputBuscar.value` se rellena, el mapa centra y hace zoom, se dispara `consultarSitio(lat, lon, etiqueta)`.

**Progreso:**
1. Pablo abre el Sandbox sobre una parcela real.
2. El overlay muestra una barra + "10% — Conectando con Catastro…", que avanza a "35% — Descargando ortofoto…", "70% — Procesando edificios colindantes…", "90% — Generando sombras y encuadre…", "100%" y se oculta.

**Zócalo + filtro de colindantes:**
1. Pablo abre el Sandbox (con o sin parcela real).
2. El terreno tiene un borde/base visible de varios metros de grosor bajo el relieve, con un material neutro de maqueta.
3. Si hay parcela real, los edificios colindantes mostrados no se extienden mucho más allá del radio ya usado por el resto de la escena.

## 8. Criterios de aceptación

Todos verificados en vivo (Chrome, servidor local) el 2026-08-16.

1. **[x]** Los 4 chips existen bajo `.parcela-buscador`, con las 4 direcciones/etiquetas exactas del encargo. Verificado: captura de pantalla del Paso 0 con "Gran Vía, Madrid" / "Calle Velázquez, Madrid" / "Castellana / AZCA, Madrid" / "La Moraleja, Madrid" visibles como cápsulas bajo el buscador.
2. **[x]** Un clic en cualquier chip rellena el input, centra el mapa y dispara la misma consulta a Catastro que una búsqueda manual. Verificado dos veces: clic en "Gran Vía, Madrid" (geocodificó, centró el mapa, consultó Catastro, mostró el aviso real de "sin referencia en ese punto exacto" — mismo comportamiento que una búsqueda manual sobre un punto de calle) y clic en "La Moraleja, Madrid" seguido de un clic manual sobre un edificio real, que devolvió referencia catastral real `6372801VK4867S` (3730 m², Madrid).
3. **[x]** El overlay de carga del Sandbox (con parcela real) muestra un `%` visible con los hitos reales del pipeline, sin retroceder nunca, y sin quedarse nunca parado por debajo de 100% tras cerrarse el overlay. Verificado: "10% — Conectando con Catastro (WFS)…" capturado en pantalla; al completar, lectura directa del DOM confirmó `100% / Listo. / hidden=true`. Nota: el orden de los hitos sigue el orden CRONOLÓGICO real del pipeline (WFS 10% → colindantes 40% → ortofoto 65% → sombras/encuadre 90% → 100%), no el orden literal en que se enumeraron en el encargo (WFS→ortofoto→colindantes) — ver comentario en `viewer-sandbox.js` y §9.
4. **[x]** Sin parcela real (Laboratorio), el overlay se comporta igual que antes (cierre inmediato, sin barra de progreso falsa) — verificado, `loadingBarraWrapEl` permanece `hidden`.
5. **[x]** El terreno del Sandbox tiene un zócalo visible bajo su borde, con material propio (tono neutro `#C9C4B8`), sin huecos visibles bajo el relieve en ningún punto del radio. Verificado visualmente (zoom sobre el canto del disco, franja del zócalo visible) y numéricamente: `CylinderGeometry(radio=150, altura=3)` con borde superior en y=-1.2; muestreo de `alturaTerrenoOrganico` en todo el radio (pasos de 2 m / 10°) dio un mínimo real de **y=-0.55**, un margen de 0.65 m por debajo del punto más bajo — sin huecos posibles.
6. **[x]** Con parcela real, ningún edificio colindante RENDERIZADO tiene su centroide a más de 220 m (180+40) del centro de la parcela. Verificado con un sitio real (La Moraleja): el backend devolvió 14 colindantes crudos, 1 con centroide a 307,6 m; la escena renderizada contó exactamente 13 mallas de colindante (material `#9AA0A6`) — el filtro excluyó el único edificio fuera de radio, ninguno de más.
7. **[x]** Cero regresión: verificado en vivo — "+ Añadir volumen" sigue creando un volumen y abriendo su panel de edición; el botón "Planta · Norte arriba" de la barra de herramientas sigue animando la cámara a vista cenital; la ortofoto real, el contorno de parcela y los colindantes siguen renderizando correctamente sobre una parcela real. Consola del navegador sin errores tras recarga limpia.

**Nota de verificación:** durante las pruebas se usó un hook temporal `window.ArchmuseSandbox._debug()` para inspeccionar `scene`/`camera`/`controls` desde la consola — añadido, usado y retirado antes de cerrar el PRD (confirmado: `grep _debug static/viewer-sandbox.js` no devuelve nada en la versión final).

## 9. Riesgos

- **% de progreso "falso" si se implementa mal**: un progreso basado en `setInterval`/tiempo estimado en vez de en los hitos reales del pipeline sería peor que el spinner actual (promete precisión que no tiene). Mitigación: cada `%` se dispara únicamente desde un punto real del código donde ese hito ya ocurre (inicio de `pedirEntorno3DPorCoordenadas`, resolución de esa promesa, inicio/fin de `construirMosaicoOrtofoto`), nunca desde un temporizador.
- **Filtrar colindantes por centroide es una decisión de fidelidad, no puramente estética**: un edificio real y colindante de verdad podría quedar oculto si su centroide (no su footprint más cercano) cae justo fuera del radio. Es el mismo compromiso que ya asume `_ENTORNO_3D_RADIO_M = 180` en el backend (un límite arbitrario razonable, no una frontera física real) — este cambio solo lo aplica también en cliente para eliminar el caso peor (edificios que ya deberían haberse filtrado del todo pero Overpass devuelve por tener un nodo dentro del radio).
- **4 presets fijos, todos en Madrid**: si ArchMuse se usa fuera de Madrid, los presets no aportan nada a ese usuario — están etiquetados igual ("Madrid") en el propio texto del chip, así que no engañan sobre su alcance.
- **Ninguno de los 3 objetivos compite con tareas priorizadas en `REFACTOR_MASTERPLAN.md`** — son aditivos y acotados a Sandbox/Paso 0, no tocan el bug crítico de tipología/zona climática de `/api/analizar` que sí tiene prioridad documentada ahí.

## 10. Impacto sobre módulos existentes

- `static/entrevista.js`: `vistaParcelaInicial()` (añade el bloque de chips al HTML) y `wireParcelaInicial()` (cablea el clic de cada chip a `consultarSitio` reutilizando el mismo camino que un resultado de búsqueda).
- `static/style.css`: nuevas reglas `.parcela-presets`/`.parcela-preset-chip`; nuevas reglas `.sandbox-loading-barra`/`.sandbox-loading-progreso`/`.sandbox-loading-porcentaje`.
- `static/viewer-sandbox.js`: `open()` instrumentado con actualizaciones de `%` en los puntos ya existentes del pipeline async; nueva función `actualizarProgreso(pct, texto)`. Filtro de colindantes por centroide antes de `construirEdificiosColindantes` (o dentro, como parámetro).
- `static/viewer-terreno.js`: nueva función `construirZocaloTerreno(radio, grosor)` (o extensión de `construirTerrenoOrganico`/`crearGroundNeutro` para incluirlo). Posible extensión de `construirEdificiosColindantes` para aceptar un radio de corte, o un filtro previo en `viewer-sandbox.js` (a decidir en implementación, ambos son válidos y locales a estos dos archivos).
- `static/index.html`: bump de cache-busting en los `<script>`/`<link>` afectados.
- Ningún cambio en `app.py`, `analyzer/`, ni en `viewer-edificio.js` (que tiene su propio overlay de carga y su propio terreno, fuera de alcance aquí).

## 11. Plan de implementación dividido en pequeñas tareas

1. **Presets de direcciones**: añadir el bloque de chips en `vistaParcelaInicial()`, cablear cada clic en `wireParcelaInicial()` a geocodificar (reusa `apiFetch("GET", "/api/geocodificar?q=...")`) y disparar `consultarSitio` con el primer resultado, igual que `mostrarResultados`. CSS de las cápsulas.
2. **Barra de progreso — estructura HTML/CSS**: añadir marcado de barra + `%` dentro de `#sandbox-loading` en `index.html` (junto al spinner ya existente), estilos en `style.css`.
3. **Barra de progreso — instrumentación**: función `actualizarProgreso(pct, texto)` en `viewer-sandbox.js`; llamadas en los 5 puntos reales del pipeline dentro de `open()`.
4. **Zócalo de terreno**: nueva geometría de base (extrusión bajo el radio del terreno) en `viewer-terreno.js`, añadida en `open()` de `viewer-sandbox.js` tanto para el caso orgánico como el neutro/plano.
5. **Filtro de colindantes por radio útil**: filtro por centroide antes de renderizar, usando el mismo radio que `ajustarFrustumSombra`.
6. **Verificación en vivo** (Chrome): los 4 chips, progreso con parcela real Madrid, zócalo visible con y sin parcela real, colindantes recortados en un sitio con edificios grandes cerca del borde del radio. Bump de cache-busting. Cierre del PRD.

## 12. Plan de pruebas

- Verificación manual en navegador real (Chrome vía `mcp__claude-in-chrome__*`), igual que el resto de esta sesión: no hay suite de tests automatizada para el frontend 3D en este proyecto todavía (`REFACTOR_MASTERPLAN.md` tarea 18, sin empezar).
- `python -m py_compile` no aplica (sin cambios en Python). `node --input-type=module --check` sobre `viewer-sandbox.js`/`viewer-terreno.js` tras cada edición.
- Casos a verificar en vivo: los 4 casos de uso de §5, más los casos límite marcados como verificables en §6 (geocodificación fallida de un preset, Laboratorio sin barra de progreso falsa, zócalo sin huecos en el relieve más bajo).

## 13. Métricas para medir el éxito

Sin instrumentación de analítica en este proyecto todavía — el criterio de éxito es cualitativo: Pablo confirma en uso real que (a) los presets aceleran probar el Sandbox, (b) el progreso se percibe como informativo y no falso, (c) el terreno ya no se ve como "mesa de billar flotante".

## 14. Posibles motivos para NO implementar la idea

- Los 3 objetivos son pulido de UX/estética sobre una herramienta (Sandbox) que el propio `MOAT_ANALYSIS.md` ya señala como área sin foso defendible — invertir aquí en vez de en el bug crítico de tipología/zona climática de `/api/analizar` (con prioridad ya documentada en `REFACTOR_MASTERPLAN.md`) es una decisión consciente de priorización, no automática. Dicho eso, el encargo es acotado (una tarde de trabajo, no un rediseño), así que el coste de oportunidad real es bajo.
- Los 4 presets son específicos de Madrid y quedarán obsoletos/parciales el día que ArchMuse tenga usuarios fuera de esa ciudad — no se ha pedido que sean configurables ni gestionados desde ningún panel de administración (no existe ninguno), así que hoy son literales en el código; si el catálogo de presets creciera o necesitara variar por usuario, esto merecería su propio PRD de "presets configurables", no una extensión de este.
- El filtro de colindantes por centroide (§9) es la única pieza de las tres que roza "cambiar qué datos reales se muestran" en vez de solo cómo se ven — se recomienda tratarlo con el mismo cuidado que cualquier cambio de fidelidad de datos, aunque el criterio elegido (mismo radio que ya usa `ajustarFrustumSombra`, no uno nuevo inventado) minimiza esa preocupación.
- Alternativa más barata para el objetivo 2 (progreso): quedarse con el spinner + texto ya existente (que ya mejoró la experiencia respecto al estado anterior a esta sesión) y no construir un `%` cuya granularidad real (solo 5 hitos discretos) es más aparente que sustantiva — un `%` con solo 5 saltos posibles puede sentirse tan artificial como el spinner que sustituye si no se gestiona bien la transición visual entre hitos. Se incluye igualmente por ser un encargo explícito, no por convicción propia de que sea la mejora de mayor valor de las tres.

---

**Decisión:** Implementado 2026-08-16 — alcance completo (§11, tareas 1-6), verificado en vivo.
