# PRD — Elevación real (DEM) en el visor de edificio

**Estado:** Implementado · **Fecha:** 2026-08-16 · **Fecha de cierre:** 2026-08-16 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (alcance acotado, no el plan DEM real completo — ver nota de cierre en §8 y §14)

---

## 0. Contexto: por qué este PRD no sigue el plan técnico tal como se pidió

La petición original proponía crear `src/terrain/elevationLoader.js`, `src/terrain/terrainMesh.js` y `src/buildings/buildingPlacer.js`, usando Mapbox Terrain-RGB como fuente principal. Se descarta esa forma concreta, no el objetivo, por dos motivos verificados en este mismo repo:

- **No existe ningún directorio `src/`** — el frontend entero vive en `static/*.js`, módulos ES cargados directamente desde `index.html` vía `importmap` (three.js por CDN), sin bundler. Ese árbol de archivos no lo cargaría ningún `<script>` existente.
- **No hay `MAPBOX_TOKEN` configurado en este entorno** (confirmado en vivo por `visor-mapa.js`/`map-picker.js`), y la ortofoto real que ya usa ArchMuse no viene de Mapbox sino de ArcGIS World Imagery, sin token. Pablo confirmó seguir solo con Copernicus DEM, sin depender de un token que hoy no existe.

Este documento sustituye ese plan por uno que encaja con la arquitectura real: extiende `static/viewer-terreno.js` (ya comparte georreferenciación y ortofoto entre `viewer-edificio.js` y `viewer-sandbox.js`) y añade una consulta de elevación **desde el backend** (`analyzer/sitio.py` + `app.py`), con el mismo patrón que ya usa `edificios_colindantes_geometria` para Overpass: el navegador nunca llama directamente a un servicio externo de terreno, pide datos ya resueltos a `/api/proyectos/<id>/entorno-3d`. Se aplica solo a `viewer-edificio.js`, confirmado por Pablo — el Sandbox mantiene su terreno orgánico sintético, decisión ya tomada en `docs/prd/2026-08-16-sandbox-encuadre-camara-y-sombra.md`.

## 1. Problema que resuelve

Hoy, tanto el suelo sintético de seguridad (`buildGround`, `PlaneGeometry` plano) como la ortofoto real superpuesta (`construirPlanoOrtofoto`) son completamente planos — no hay ninguna cota real. En una parcela con pendiente real, el edificio y su entorno urbano flotan sobre un plano que no representa la topografía real del sitio, lo cual es honestamente incorrecto para cualquier decisión de implantación (rasante, movimiento de tierras, accesos) que un arquitecto pudiera querer visualizar.

## 2. Usuario afectado

El arquitecto que ya tiene un proyecto con un sitio real vinculado (Paso 0) y abre el visor de edificio (`viewer-edificio.js`) — no el usuario del Sandbox, que trabaja deliberadamente sin datos reales de topografía (ver PRD de encuadre/sombra de hoy).

## 3. Objetivo de negocio

Ninguno de los hitos de `NORTH_STAR_2031.md` (1/3/6/12/24 meses) menciona el terreno, la topografía ni el visor 3D — la hoja de ruta a 2031 está enteramente centrada en profundidad normativa e integración BIM. `MOAT_ANALYSIS.md` (§6) ya señala el visor 3D como "vistosa para una demo" pero de foso bajo, sin conexión hoy con el motor de hallazgos. **Esto es honestidad, no una recomendación de no hacerlo**: el objetivo de negocio de este PRD es modesto y explícito — reducir un incorrección visual real (un edificio flotando sobre un plano sin relieve en una parcela con pendiente) para el usuario que ya usa el visor de edificio, no abrir una nueva línea de valor estratégico. Ver §14 para la alternativa de no implementarlo ahora.

## 4. Objetivo técnico

- Cuando el proyecto tiene un sitio real vinculado, el suelo del visor de edificio (plano sintético + ortofoto) tiene el relieve real de la parcela y su entorno, con la escala vertical suficiente para ser perceptible sin exagerar la pendiente real.
- Los edificios colindantes reales (`construirEdificiosColindantes`) se apoyan sobre la cota real de su ubicación, no sobre Y=0.
- Si el servicio de elevación falla o no cubre la zona, el visor se comporta exactamente como hoy (suelo plano) — mismo criterio "no disponible, no error" que ya usa `_entorno_3d_para`.

## 5. Casos de uso

- Proyecto con sitio real en una zona con pendiente perceptible (p. ej. una ladera): el suelo del visor refleja esa pendiente, el edificio y los colindantes se asientan sobre ella.
- Proyecto con sitio real en zona llana: el resultado es visualmente casi idéntico al actual (relieve mínimo, correcto).
- Proyecto sin sitio real vinculado, o servicio de elevación caído/sin cobertura: comportamiento actual sin cambios, sin ningún aviso de error visible.

## 6. Casos límite

- Parcela en el límite de cobertura del servicio de elevación (algunos DEM globales tienen huecos en zonas concretas): tratar como "no disponible", no como error.
- Escala vertical: una parcela casi perfectamente plana no debe producir una escala vertical absurdamente amplificada que convierta ruido de medición en pendiente falsa — necesita un suelo mínimo de variación por debajo del cual no se aplica relieve (ver Riesgos).
- El suelo sintético de seguridad (`buildGround`) y la ortofoto real conviven hoy con el criterio "si no hay ortofoto real, el sintético sigue debajo" — el relieve real debe respetar el mismo criterio: si el DEM no llega, el sintético (plano) sigue siendo el suelo, nunca una malla a medio deformar.
- Recorte de DEM y ortofoto al mismo bbox real (misma parcela, mismo radio) — si no coinciden exactamente, la ortofoto quedaría desalineada respecto al relieve. Esta es una invariante que hay que documentar y respetar en el código, no una casualidad.

## 7. Flujo del usuario

1. El arquitecto abre el visor de un proyecto con sitio real vinculado (igual que hoy).
2. El edificio se renderiza de inmediato sobre el suelo sintético plano (igual que hoy, sin esperar a ningún dato real).
3. Segundos después, si hay datos de elevación disponibles para esa zona, el suelo (sintético + ortofoto) se deforma con el relieve real y los colindantes se reasientan sobre su cota real — mismo patrón "llega de refresco" que ya usan hoy la ortofoto y los colindantes.

## 8. Criterios de aceptación

**Nota de cierre (2026-08-16):** los 5 criterios de abajo describían el plan DEM real (elevación con datos verificables) tal como se planteó en §1-§7. Ese plan **no se implementó** — Pablo optó explícitamente por la alternativa sintética de §14 en vez de abrir la investigación de la Tarea 1. Se dejan sin marcar, como registro honesto de lo que este documento proponía originalmente y no se construyó; no son aplicables al resultado final. Los criterios que sí gobernaron lo que se implementó y verificó en vivo (Chrome, proyecto real de Madrid + proyecto sin sitio vinculado) son los del "ALCANCE APROBADO" que sustituyó a este plan:

- [ ] En una parcela real con pendiente conocida, el suelo del visor de edificio muestra un desnivel perceptible y en la dirección correcta. — *(no aplica: sin datos DEM reales, ver nota de cierre)*
- [ ] Sin sitio real vinculado, o con el servicio de elevación caído, el visor se comporta exactamente igual que antes de este cambio (regresión cero). — *(no aplica)*
- [ ] La ortofoto sigue alineada píxel a píxel con el relieve (ningún desplazamiento visible entre calles/edificios reales de la imagen y la forma del terreno). — *(no aplica)*
- [ ] Los edificios colindantes reales se apoyan sobre su cota real, no sobre Y=0, cuando hay relieve cargado. — *(no aplica)*
- [ ] `[DEM] rango de elevación: Xm–Ym, escala vertical: Z` queda registrado en consola al cargar relieve real, para poder verificar en vivo sin abrir DevTools línea a línea. — *(no aplica)*

**Criterios reales de la implementación (alcance acotado, aprobado y verificado en vivo el 2026-08-16):**

- [x] El entorno alrededor del edificio tiene relieve orgánico visible, no un plano perfecto (verificado por geometría: rango de altura no nulo sin sitio real vinculado; correctamente aplanado bajo la ortofoto real cuando la hay, ver §14).
- [x] La parcela real del edificio mantiene su geometría correcta (acera/footprint sin cambios).
- [x] El scroll con rueda hace zoom sin saltos ni rigidez (damping ya existente + límites min/maxDistance ahora adaptativos al tamaño real del edificio).
- [x] Doble clic en terreno recentra el pivote suavemente — acotado a terreno/entorno urbano, no al edificio (decisión explícita de Pablo: un solo clic sobre una habitación ya selecciona y cierra el visor).
- [x] La brújula gira en tiempo real y al clicarla vuelve al norte.
- [x] Botones +/- y Recentrar funcionan con transición suave.
- [x] No se han modificado otros viewers ni el Sandbox (solo `static/viewer-edificio.js` + `static/style.css` aditivo).
- [x] Sin dependencias nuevas en `requirements.txt` ni `package.json`.

## 9. Riesgos

- **Formato de los datos de elevación, sin resolver todavía**: los servicios DEM públicos habituales (incluido Copernicus DEM) sirven habitualmente GeoTIFF, no un PNG codificado como Mapbox Terrain-RGB. Decodificar GeoTIFF en Python sin GDAL/rasterio (ninguno de los dos está hoy en `requirements.txt`, que deliberadamente solo usa dependencias ligeras y permisivas, ver comentarios del propio archivo) puede no ser trivial. **Antes de comprometer el resto del plan de implementación, la tarea 1 de este PRD es una investigación acotada (media jornada) para confirmar un endpoint concreto, sin token, con un formato que se pueda decodificar con una dependencia razonable** — si esa investigación concluye que hace falta una dependencia pesada (GDAL) o un servicio de pago, se vuelve a este documento antes de seguir, no se improvisa a mitad de implementación.
- **CORS**: si en algún momento se considerase pedir el DEM directamente desde el navegador (como hace hoy la ortofoto de ArcGIS), muchos servicios WCS pensados para clientes GIS de escritorio (QGIS) no habilitan CORS para navegadores — motivo por el que este PRD propone pedirlo desde el backend (Python no tiene restricción CORS), igual que ya se hace con Overpass.
- **Escala vertical mal calibrada** puede exagerar o aplanar la pendiente real de forma engañosa — un arquitecto podría tomar una decisión de implantación basándose en un relieve visualmente incorrecto. Mitigación: exponer siempre el rango real de elevación en metros (criterio de aceptación de arriba), nunca solo la versión escalada, y usar una escala vertical conservadora por defecto (1:1, sin exagerar) en vez de la fórmula de auto-exageración que proponía el plan original.
- No compite con `REFACTOR_MASTERPLAN.md` (módulo aislado), pero si la tarea 1 revela que hace falta una dependencia pesada, sí compite en tiempo de desarrollo con el resto del roadmap — decisión a revisar en ese momento, no ahora.

## 10. Impacto sobre módulos existentes

- `analyzer/sitio.py`: nueva función de consulta de elevación (paralela a `edificios_colindantes_geometria`), mismo patrón de "best-effort, nunca rompe el endpoint entero" que ya usa `_entorno_3d_para`.
- `app.py`: `_entorno_3d_para` gana un campo nuevo (p. ej. `elevacion` o `dem`) en su respuesta JSON — aditivo, no rompe a nadie que ya consuma ese endpoint (Sandbox incluido, que simplemente lo ignoraría).
- `static/viewer-terreno.js`: nueva función para deformar la malla de `construirPlanoOrtofoto`/el suelo sintético con los datos de elevación recibidos, y para muestrear la cota real al posicionar colindantes (`construirEdificiosColindantes`) — ambas ya reciben `centro`/coordenadas, se les añade la cota.
- `static/viewer-edificio.js`: `cargarEntornoUrbano` pasa a usar el campo de elevación nuevo; `buildGround` no cambia su comportamiento por defecto (sigue siendo el suelo sintético plano de seguridad).
- No toca `static/viewer-sandbox.js` (excluido explícitamente, decisión ya tomada).

## 11. Plan de implementación dividido en pequeñas tareas

1. **Investigación acotada (media jornada, spike)**: confirmar un servicio de elevación real, sin token, con cobertura de España, y un formato decodificable sin dependencias pesadas nuevas — o documentar honestamente que hace falta una dependencia nueva y su coste, antes de seguir.
2. Backend: función de consulta de elevación en `analyzer/sitio.py`, best-effort (nunca lanza, se degrada a "sin datos" igual que Overpass).
3. Backend: integrar el resultado en `_entorno_3d_para` (`app.py`), campo aditivo nuevo.
4. Frontend: deformar la geometría de `construirPlanoOrtofoto`/el suelo sintético en `viewer-terreno.js` a partir de los datos recibidos, con `computeVertexNormals()` tras el desplazamiento (imprescindible para que la iluminación no se rompa).
5. Frontend: muestreo de cota real (interpolación bilineal) para reasentar `construirEdificiosColindantes` sobre el relieve real.
6. Frontend: log `[DEM] rango de elevación: Xm–Ym, escala vertical: Z` al cargar relieve real.
7. Verificación: `node --check` + prueba en vivo (Chrome) en al menos una parcela real con pendiente conocida y otra en zona llana; confirmar que sin sitio real vinculado el visor no cambia.

## 12. Plan de pruebas

- Unit test (backend): con un GeoTIFF/tile de elevación de muestra fijado en el repo, confirmar que la función de decodificación produce la altura esperada para un píxel conocido.
- Prueba en vivo: parcela real con pendiente conocida (a elegir con Pablo) — confirmar visualmente el desnivel y la dirección correcta.
- Prueba en vivo: parcela sin sitio real vinculado — confirmar cero regresión.
- Prueba en vivo: alineación ortofoto/relieve — ninguna calle o edificio real de la imagen debe quedar desplazada respecto a la forma del terreno.

## 13. Métricas para medir el éxito

Sin telemetría de uso del visor hoy (mismo límite ya señalado en el PRD de encuadre/sombra). Éxito verificable por inspección contra los criterios de aceptación de §8, no por medición en producción.

## 14. Posibles motivos para NO implementar la idea (o para posponerla)

- **No conecta con ningún hito de `NORTH_STAR_2031.md`.** El roadmap a 2031 completo está centrado en profundidad normativa e integración BIM — el relieve real del terreno no adelanta ninguno de esos hitos.
- **`MOAT_ANALYSIS.md` ya identifica el visor 3D como funcionalidad "vistosa para una demo" pero de foso bajo, no conectada con el motor de hallazgos.** Esta mejora, honestamente, hace que la demo se vea mejor en una parcela con pendiente — no cambia esa valoración de fondo.
- **La tarea 1 (investigación) puede revelar que la única vía realista exige una dependencia pesada** (GDAL/rasterio) que este proyecto ha evitado deliberadamente hasta ahora (ver comentarios de `requirements.txt`) — si es así, el coste de mantenimiento a largo plazo probablemente no compensa el beneficio visual, y la recomendación en ese punto sería no implementarlo, no forzarlo.
- **Alternativa más barata si el objetivo real es "que no se vea plano y falso"**: aplicar el mismo relieve orgánico sintético que ya existe en el Sandbox (`construirTerrenoOrganico`, ruido determinista, sin dependencia externa) *solo* al entorno alrededor del edificio (no a la parcela del edificio en sí, que sigue siendo el terreno de diseño real y debe quedar plano), en vez de datos DEM reales. Es visualmente honesto (no pretende ser topografía real) y no tiene ningún riesgo de dependencia externa ni de coste de desarrollo. Si Pablo no necesita que el relieve sea *real* (con cotas verificables), sino solo que el suelo deje de parecer visualmente un plano perfecto, esta alternativa cuesta una fracción del tiempo de este PRD.
- **Cierre (2026-08-16):** esta fue la opción que Pablo eligió implementar — la alternativa sintética de arriba, no el plan DEM real de §1-§7. El spike de la Tarea 1 (investigación de un endpoint Copernicus DEM real, sin token, con formato decodificable) queda explícitamente abierto como una posible **fase secundaria**, a retomar solo si en algún momento surge un requisito explícito de cotas reales verificables — no por defecto.

---

**Decisión:** Implementado 2026-08-16 — alcance acotado a la alternativa sintética de §14 (terreno) + navegación fluida (fuera del alcance original de este documento, aprobada en el mismo mensaje de cierre). Plan DEM real de §1-§7 no implementado; spike de Tarea 1 abierto como fase secundaria.
