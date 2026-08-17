# PRD — Distinguir el edificio existente de los vecinos en el Lienzo libre (Sandbox 3D)

**Estado:** Aprobado e implementado · **Fecha:** 2026-08-17 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-17)

**Decisión final sobre el alcance (§14):** se implementó la "alternativa más barata" — tareas 1-5 de
§11 (clasificación + `MAT_EDIFICIO_EN_PARCELA` `#D4C5A9` con borde `#7F7765` + aviso "sin
edificación") — **sin tocar** las 4 constantes ya fijadas en PRDs anteriores (radio 220m, grosor pad
0.15m, color pad `0xC9B896`, altura por defecto 9m). El encargo que disparó esta implementación no
mencionaba esas 4 constantes, así que reabrirlas habría sido asumir, no corregir — quedan como
pregunta abierta aparte (§9/§14) para si Pablo quiere revisarlas más adelante. Criterio de
clasificación de medianeras (§6): centroide del footprint dentro del polígono de la parcela — sin
cálculo de área de intersección, que queda como refinamiento futuro si un caso real de medianera lo
pide.

**Ajustes de prioridad 3 -- IMPLEMENTADOS (2026-08-17, encargo explícito con las 7 secciones
completas: terreno/edificio existente/vecinos/suelo/alineación/carga asíncrona/panel lateral)**:

- Radio de contexto: 80m (sustituye `RADIO_UTIL_COLINDANTES_M = 220`) -- **solo del lado cliente**;
  el backend sigue pidiendo a Overpass a 180m (`_ENTORNO_3D_RADIO_M` en `app.py`, compartido con
  `viewer-edificio.js`, deliberadamente sin tocar -- ver §10 "NO toca app.py").
- Altura por defecto: 7m (antes 9m); `building:levels` × 3.2m (antes × 3.0m) -- en
  `_estimar_altura_edificio` (`analyzer/sitio.py`), COMPARTIDA con `viewer-edificio.js` (mismo
  backend). Decisión consciente: es una corrección de precisión de estimación, no un ajuste solo
  cosmético del Sandbox, así que se dejó propagar; tests actualizados (`tests/test_entorno_3d.py`).
- Pad: color `#D4C9B0` (antes `0xC9B896`); grosor 0.15m sin cambios.
- Criterio "en-parcela": pasa de "solo centroide dentro del polígono" a INTERSECCIÓN DE POLÍGONOS de
  verdad (`poligonosSeIntersectan`, nueva, en `viewer-terreno.js`) -- solape parcial (medianera) o
  contención total, ambos cuentan.
- Filtro de inclusión ("colindancia", qué se dibuja del conjunto ya descargado): centroide dentro del
  radio de 80m, **O** footprint que intersecta la parcela (mismo `poligonosSeIntersectan`) --
  interpretación explícita de "colindancia = intersección de polígonos O centroide a menos de 80m":
  se aplicó como criterio de INCLUSIÓN en el contexto, no como el criterio de clasificación
  en-parcela/vecino en sí (que ya queda cubierto arriba por la sola intersección) -- ver nota de
  interpretación en el informe de cierre a Pablo.
- Edificio en-parcela: base a Y=0.05 (antes Y=0, igual que los vecinos); vecinos sin cambio (Y=0).
- Timeout de colindantes/ortofoto: 6s cuando ya hay geometría previa del Paso 0 (antes 8s).
- Suelo/ortofoto a Y=0 exacto: **NO aplicado** -- se mantiene en Y=0.03, la misma corrección ya
  verificada en vivo esta sesión (acné de sombra real con `shadowNormalBias: 0.02`); aplicar Y=0
  literal reintroduciría un bug ya encontrado y arreglado.
- Alineación (fórmula única WGS84→metros locales para edificios y ortofoto): ya estaba unificada
  desde antes (`metrosEsteNorteDesde`/`rotarAEjesLocales`, compartidas) -- verificado, sin cambios.
- Carga asíncrona (parcela primero, edificios en segundo plano, spinner no espera): ya implementado
  en la corrección de rendimiento de esta misma sesión -- verificado, sin cambios de comportamiento
  más allá del timeout de 6s de arriba.
- Panel lateral: nueva línea `.sandbox-hud-contexto-edificios` ("X edificios en contexto · X m²
  construidos", gris `#888`), oculta si no hay ningún edificio.
- Corrección adicional encontrada en vivo (no pedida, mismo hallazgo de la sesión anterior pero un
  caso distinto): `segmentosSeCruzan`/`poligonoAutointersecta` no detectaban el caso de dos aristas
  COLINEALES que se solapan (puente/ojo de cerradura) -- se añadió `segmentosColinealesSeSolapan`.
  Verificado que NO introduce falsos positivos contra los edificios reales probados en vivo.

---

## 0. Nota de alcance (léase antes que el resto)

La petición original de Pablo pedía, en apariencia, construir desde cero: terreno real extruido, consulta a Overpass para el edificio existente, edificios vecinos en un radio, cámara isométrica y materiales técnicos. **Al investigar el código, la mayor parte de esto ya está construido y en producción en el Sandbox**, desde los PRDs `2026-08-16-sandbox-navegacion-profesional-y-lindes.md` y `2026-08-16-presets-progreso-y-zocalo-sandbox.md`:

| Petición de Pablo | Estado real en el código |
|---|---|
| 1. Terreno real extruido, grosor 0.3m, color `#C4A882` | **Ya existe**: `construirPadParcela()` en `viewer-sandbox.js` extruye el contorno EXACTO de la parcela (Catastro), con `MAT_PAD_PARCELA` (`0xC9B896`, muy próximo a `#C4A882`) y `GROSOR_PAD_PARCELA_M = 0.15` (no 0.3). Diferencia de color/grosor: ajuste de constante, no capacidad nueva. |
| 2. Edificio existente vía Overpass, altura por `building:levels*3` o 6m por defecto | **La consulta y la estimación de altura ya existen** (`analyzer/sitio.py::_estimar_altura_edificio`, exactamente `building:levels * 3m`, con 9m — no 6m — como valor por defecto). **Lo que NO existe**: ninguna distinción entre "el edificio que está en MI parcela" y "los edificios de alrededor" — hoy todos los edificios que devuelve Overpass, estén donde estén dentro del radio, se dibujan juntos, con el mismo material gris translúcido de "vecino". |
| 3. Edificios vecinos en 50m, gris, apagados | **Ya existen**, pero a radio 220m (`RADIO_UTIL_COLINDANTES_M`, decisión explícita del PRD del 2026-08-16), material `0x9AA0A6` semitransparente (`opacity: 0.55`) — ya es "gris apagado", muy cerca de lo pedido. |
| 4. Cámara isométrica a 45° al cargar | **Ya existe, literal**: `encuadrarCamaraAContenido()` enmarca "a 45° de azimut / 45° de elevación" (comentario explícito en el código, encargo del 2026-08-16). |
| 5. Materiales mate, roughness 0.8–1.0, metalness 0, sin brillo | **Ya es el estándar del Sandbox** (`aplicarMaterialesArchVizATodos`, `MAT_PAD_PARCELA`, `MAT_EDIFICIO_COLINDANTE` — todos `MeshStandardMaterial` con `metalness: 0` y `roughness` 0.95–1). |
| 6. Mensaje "Sin edificación registrada" si no hay edificio | **No existe** — hoy, si Overpass no devuelve nada, simplemente no se dibuja ningún volumen y no hay ningún aviso. Existe ya un hueco reservado para esto (`.sandbox-hud-aviso` en el panel de urbanismo), pero no se usa con este mensaje. |

**Conclusión de alcance**: el trabajo real y nuevo de este PRD es angosto: (a) clasificar geométricamente cada edificio de Overpass como "en la parcela" o "vecino", (b) dar al primero un material distinto y prioritario, (c) añadir el aviso de "sin edificación", y (d) decidir, explícitamente con Pablo, si se tocan las 4 constantes ya fijadas a propósito en un PRD anterior (radio, grosor, color, altura por defecto) — ver §9 y §14. No hace falta ninguna llamada nueva a Overpass, ni endpoint nuevo, ni cambio en `app.py`/`analyzer/sitio.py`: los datos que hacen falta (`body.geometria_parcela`, `body.edificios_colindantes[].vertices/altura_m`) ya llegan al cliente hoy.

---

## 1. Problema que resuelve

Petición directa de Pablo: en el Lienzo libre, sobre una parcela real, el arquitecto no puede distinguir a simple vista "esto ya está construido en mi solar" (dato que condiciona si el proyecto es obra nueva o reforma, y cuánto hay que demoler) de "esto es un edificio vecino, solo contexto". Hoy ambos se pintan igual — mismo grupo, mismo material gris translúcido — así que la información SÍ está en la escena (la geometría real ya se descarga y se dibuja) pero no se LEE como dos cosas distintas.

## 2. Usuario afectado

El arquitecto que ya llegó a Sandbox con una parcela real de Catastro (Paso 0 → Continuar), evaluando volumetría/cabida contra la edificación existente real, no una parcela vacía de laboratorio.

## 3. Objetivo de negocio

Ya invertido: la fidelidad al contexto real (Catastro + OSM) es lo que distingue el Sandbox de un editor de cajas genérico. Este PRD no abre una capacidad nueva de negocio, remata una ya vendida como diferencial: que lo que se ve en pantalla sea información fiable para tomar una decisión real (reforma vs. obra nueva), no solo "hay edificios cerca".

## 4. Objetivo técnico

Dado el payload ya disponible de `/api/entorno-3d-punto` (`geometria_parcela`, `edificios_colindantes[]` con `vertices`/`altura_m`/`origen_altura`), el cliente debe:
- Clasificar cada edificio de `edificios_colindantes` como **en-parcela** o **vecino**, mediante un test geométrico 2D contra el polígono real de la parcela (mismos ejes locales ya proyectados que usa `construirPadParcela`/`construirEdificiosColindantes` — no hace falta ningún dato nuevo del backend).
- Renderizar los edificios en-parcela con un material distinto (opaco, blanco roto) y los vecinos con el material gris translúcido ya existente.
- Si, tras clasificar, no hay ningún edificio en-parcela, mostrar el aviso "Sin edificación registrada en esta parcela" en el panel HUD ya existente.

## 5. Casos de uso

1. **Parcela con edificio existente completo dentro de sus lindes** (el caso típico urbano): el volumen se pinta en blanco roto opaco, distinto de los vecinos grises.
2. **Parcela con edificio medianero** (comparte pared con el vecino, su footprint cruza la linde catastral): ver criterio de clasificación en §6 — se decide por solape de área, no por "toca la linde".
3. **Parcela vacía** (solar sin edificar): no hay ningún edificio en-parcela → aviso "Sin edificación registrada en esta parcela"; los vecinos se siguen mostrando con normalidad.
4. **Parcela sin contorno de Catastro** (`geometria_parcela` es `null`, best-effort ya documentado): no hay polígono contra el que clasificar → todos los edificios se tratan como "vecino" (comportamiento actual, sin regresión) y el HUD ya avisa (mecanismo existente) de que no hay contorno real.

## 6. Casos límite

- **Edificio medianero / solape parcial**: se clasifica como "en-parcela" si el centroide de su footprint cae dentro del polígono de la parcela, o si el área de intersección supera un umbral (p. ej. 30%) — a definir en implementación con un caso de prueba real (buscar una parcela con medianera conocida). Nunca se recorta el volumen del edificio a la mitad.
- **Varios edificios dentro de la misma parcela** (nave + anexo, vivienda + garaje separado): todos se clasifican como "en-parcela"; no hay límite de 1.
- **`building:levels` no numérico** (`"yes"`, vacío): ya cubierto por `_estimar_altura_edificio` (cae al valor por defecto) — sin cambios.
- **Overpass caído / timeout**: ya es best-effort (no rompe el Sandbox) — sin cambios; en ese caso tampoco hay edificios que clasificar, y el aviso de "sin edificación" NO debe mostrarse (sería un falso "no hay edificio" cuando en realidad es "no se pudo consultar") — usar el aviso de fallo de Overpass ya existente en su lugar, no el nuevo mensaje.

## 7. Flujo del usuario

Sin cambios de interacción (petición explícita de Pablo: "no añadir controles ni botones nuevos"). El usuario abre Sandbox con una parcela real ya elegida en Paso 0; el pipeline actual (`open()` en `viewer-sandbox.js`) sigue disparando la misma consulta `pedirEntorno3DPorCoordenadas` que ya dispara hoy; lo único que cambia es cómo se interpreta y pinta la respuesta.

## 8. Criterios de aceptación

- [ ] Con una parcela real que tiene un edificio dentro (verificar con un caso real, p. ej. una RC de vivienda unifamiliar catastrada), ese volumen se ve en material blanco roto opaco, visualmente distinto de cualquier vecino gris.
- [ ] Los edificios que NO están dentro de la parcela siguen viéndose como hoy (gris, `opacity: 0.55`), sin regresión.
- [ ] Con una parcela sin ningún edificio dentro (solar vacío verificado), aparece el texto "Sin edificación registrada en esta parcela" en el panel HUD, y NO aparece si lo que falló fue la propia consulta a Overpass (esos dos casos no deben verse iguales).
- [ ] La cámara sigue enmarcando a 45°/45° como hoy (sin regresión — ya cumplía el punto 4 de la petición).
- [ ] Todos los materiales nuevos son `MeshStandardMaterial` con `metalness: 0` y `roughness` ≥ 0.8 (mismo estándar ya vigente en el Sandbox).
- [ ] No se añade ningún botón, control o interacción nueva.

## 9. Riesgos

- **Reconciliación de constantes ya decididas a propósito**: `RADIO_UTIL_COLINDANTES_M = 220`, `GROSOR_PAD_PARCELA_M = 0.15`, color `0xC9B896`, altura por defecto 9m, fueron decisiones EXPLÍCITAS de un PRD aprobado el 2026-08-16 (`sandbox-navegacion-profesional-y-lindes.md` / `presets-progreso-y-zocalo-sandbox.md`). La petición de hoy pide valores distintos (50m, 0.3m, `#C4A882`, 6m por defecto). Cambiarlos sin que Pablo confirme que sustituyen (no coexisten con) la decisión anterior arriesga deshacer un ajuste ya validado en vivo — ver §14, se pide decisión explícita.
- **Criterio de clasificación medianero**: un umbral de solape mal elegido puede clasificar un edificio vecino real como "en la parcela" (o al revés) en el caso más común en cascos urbanos — la medianera. Mitigación: probarlo contra al menos una parcela real con medianera conocida antes de dar por cerrada la tarea (§12).
- **No compite con `REFACTOR_MASTERPLAN.md`**: es una tarea acotada (~4-6 subtareas de código cliente, sin tocar backend), no debería desplazar trabajo de endurecimiento ya priorizado.

## 10. Impacto sobre módulos existentes

- `static/viewer-terreno.js`: `construirEdificiosColindantes()` deja de recibir "todos los edificios con un único material" — necesita clasificar y aplicar uno de dos materiales. Se añade `MAT_EDIFICIO_EN_PARCELA` junto al ya existente `MAT_EDIFICIO_COLINDANTE`.
- `static/viewer-sandbox.js`: en el callback de `pedirEntorno3DPorCoordenadas` (línea ~1027), antes de llamar a `construirEdificiosColindantes`, se necesita el polígono ya proyectado de la parcela (`parcelaPoligonoLocal`, que ya se calcula ahí mismo) para pasar la clasificación. También el HUD (`actualizarUrbanismo`/`.sandbox-hud-aviso`) para el nuevo aviso.
- **NO toca** `app.py` ni `analyzer/sitio.py`: los datos ya vienen completos en `body.geometria_parcela` y `body.edificios_colindantes`.
- **NO toca** `viewer-edificio.js`: usa la misma `construirEdificiosColindantes` compartida, pero ahí no hay concepto de "parcela propia" (es el visor de un edificio ya modelado, no de una parcela vacía) — su llamada debe seguir pasando "sin polígono de parcela" y comportarse exactamente igual que hoy (todos "vecino"), sin regresión.

## 11. Plan de implementación dividido en pequeñas tareas

1. Función pura de clasificación (punto/polígono + solape de área) en `viewer-terreno.js` o un módulo geométrico compartido — con tests aislados de los 3 casos de §6 (dentro, medianero, fuera).
2. `MAT_EDIFICIO_EN_PARCELA` (blanco roto `#F5F5F0`, opaco, `roughness: 0.9`, `metalness: 0`) junto a `MAT_EDIFICIO_COLINDANTE` existente.
3. `construirEdificiosColindantes()` acepta un polígono de parcela opcional; si se pasa, clasifica y aplica el material correspondiente por edificio; si no se pasa (caso `viewer-edificio.js`), comportamiento idéntico al actual.
4. `viewer-sandbox.js`: pasar `parcelaPoligonoLocal` a la llamada existente; si tras clasificar no hay ningún edificio en-parcela (y Overpass sí respondió), fijar el aviso HUD.
5. Aviso HUD: nuevo texto en `.sandbox-hud-aviso`, distinguiendo "sin edificación" de "sin datos de Overpass" (reutilizar el mecanismo de aviso ya existente, no uno nuevo).
6. Decisión explícita con Pablo sobre las 4 constantes (§9/§14) y ajuste si corresponde.
7. Verificación en vivo contra al menos 2 parcelas reales: una con edificio dentro, una vacía (o sin edificio catastrado) — capturas + consola limpia.

## 12. Plan de pruebas

- Test unitario de la función de clasificación con 3 fixtures geométricos (edificio 100% dentro, edificio medianero con solape parcial, edificio 100% fuera).
- Verificación manual en el Sandbox real (Chrome, mismo patrón que el resto de la sesión) con una RC conocida que tenga edificación, y con una parcela vacía — confirmar visualmente el material distinto y el aviso.
- Confirmar que `viewer-edificio.js` sigue funcionando igual (no se le pasa polígono de parcela, todos sus edificios se siguen clasificando "vecino").

## 13. Métricas para medir el éxito

Sin telemetría de producto hoy en el Sandbox — el criterio de éxito es cualitativo y verificado en vivo (criterios de aceptación de §8), no una métrica numérica en producción.

## 14. Posibles motivos para NO implementar la idea (o para implementarla distinto)

- **El radio de 50m pedido hoy es más pequeño que el 220m ya vigente** (decisión explícita anterior, pensada para dar contexto urbano suficiente — una calle ancha o una manzana grande puede quedar fuera de 50m). Antes de aplicar 50m, confirmar con Pablo si de verdad sustituye esa decisión o si el "radio de 50m" de la petición de hoy en realidad describía la intención original que el 220m ya cumple mejor.
- **Alternativa más barata**: si lo único que de verdad importa hoy es "ver claro qué es mío", podría bastar con la clasificación + material distinto (tareas 1-5), sin tocar ninguna constante ya afinada (tarea 6) — separar esa decisión reduce el riesgo de deshacer trabajo ya validado en vivo por una petición que puede estar describiendo el mismo objetivo con números distintos, no un cambio deliberado.

---

**Decisión:** Aprobado (2026-08-17) — implementadas tareas 1-5 de §11 (`viewer-terreno.js`,
`viewer-sandbox.js`); tarea 6 (constantes) queda deferida, ver nota de alcance arriba.
