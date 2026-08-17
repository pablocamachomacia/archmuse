# PRD — Navegación profesional y lindes de parcela en el Sandbox 3D

**Estado:** Implementado · **Fecha:** 2026-08-16 · **Fecha de cierre:** 2026-08-16 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (alcance completo, §11 tareas 1-6)

---

## 0. Contexto: qué de lo pedido ya existe y qué es capacidad nueva

La petición ("AUDITORÍA DE UX/UI... EXPERIENCIA DEL ARQUITECTO") listaba 8 puntos sobre `static/viewer-sandbox.js`. Se leyó el archivo completo (493 líneas) antes de escribir esto — no todo lo pedido es trabajo nuevo:

- **Ya implementado, no se toca:** `enableDamping`/`dampingFactor=0.05` (línea 284); encuadre de cámara adaptativo al `Box3` real de la escena (`encuadrarCamaraAContenido`, PRD `2026-08-16-sandbox-encuadre-camara-y-sombra.md`, ya ejecutado); terreno con relieve orgánico (`construirTerrenoOrganico`) cuando no hay parcela real; volúmenes asentados sobre la altura real del terreno con `polygonOffset` para evitar z-fighting.
- **Capacidad nueva, cubierta por este PRD:** gizmo/brújula de orientación, recentrado por doble clic, límites de `OrbitControls` (`min/maxDistance`, `near/far`) derivados del `Box3` real en vez de constantes fijas, barra de herramientas flotante (Isométrica / Planta-Norte arriba / Sombras), y contorno de la parcela real (lindes).
- Las dos primeras (gizmo, doble clic) reutilizan el patrón exacto ya construido y verificado hoy mismo en `static/viewer-edificio.js` (`buildCompass`, `onDblClickRecenter`) — coste bajo, riesgo bajo. El contorno de parcela es el ítem con más incertidumbre real (ver §9) porque implica un campo nuevo en el backend, no solo three.js.

## 1. Problema que resuelve

Comparado con herramientas de referencia (Mapbox 3D, Cesium, Lumion), el Sandbox tiene dos carencias reales de orientación espacial: (1) los límites de zoom/near-far son constantes fijas sin relación con el contenido real, lo que puede dejar clipping o zoom excesivo en escenas muy pequeñas o muy grandes; (2) no hay ninguna referencia visual de norte ni de los límites reales de la parcela — el arquitecto ve edificios colindantes y una ortofoto, pero no dónde termina legalmente su solar.

## 2. Usuario afectado

El arquitecto que usa el Modo Sandbox (`static/index.html` → "Lienzo libre") para bocetar volumetría, con o sin parcela real vinculada del Paso 0.

## 3. Objetivo de negocio

Mismo criterio que el PRD de encuadre/sombra de hoy: `MOAT_ANALYSIS.md` (§6) ya señala el visor 3D como "vistoso para una demo" pero de foso bajo. Esto sigue sin cambiar esa valoración — es higiene de una pieza que ya se enseña a clientes potenciales, no una apuesta estratégica nueva. El contorno de parcela es la única pieza con algo más de sustancia: mostrar la linde legal real (no solo edificios colindantes) es información que un arquitecto necesita para decidir dónde puede construir, no solo cómo se ve.

## 4. Objetivo técnico

- `OrbitControls` (`minDistance`, `maxDistance`, `near`, `far`) se recalculan desde el `Box3` real de la escena, no desde constantes fijas — coherente con el criterio que ya usa `encuadrarCamaraAContenido`/`ajustarFrustumSombra`.
- Doble clic sobre terreno/ortofoto/colindantes recentra el pivote de la cámara sin cambiar distancia/ángulo.
- Gizmo de norte visible, clicable (vuelve al norte), rota en tiempo real con la órbita.
- Barra de herramientas flotante con tres accesos: reset a vista isométrica de estudio, vista en planta (norte arriba), alternar sombras.
- Si el proyecto tiene parcela real vinculada y Catastro devuelve geometría de parcela, se dibuja su contorno real (polyline) sobre el terreno — nunca inventado, nunca aproximado a partir de los colindantes.

## 5. Casos de uso

- Sandbox sin parcela real: gizmo, doble clic y toolbar funcionan igual (norte = -Z local, sin dato real de orientación); sin contorno de parcela (no hay nada real que dibujar).
- Sandbox con parcela real y Catastro con geometría disponible: aparece el contorno real de la parcela, alineado con la ortofoto y los colindantes (misma proyección `metrosEsteNorteDesde`/`rotarAEjesLocales` que ya usan ambos).
- Sandbox con parcela real pero Catastro sin geometría para ese punto (ocurre hoy, ver `analyzer/sitio.py` línea 276-295: "Catastro no tiene ninguna parcela en esas coordenadas" es un caso ya observado, no hipotético): igual que con edificios colindantes vacíos — sin contorno, sin aviso de error.
- Volumen añadido cerca del borde de los límites actuales de zoom: los nuevos límites adaptativos lo cubren igual que ya hace el encuadre de cámara.

## 6. Casos límite

- Escena vacía (parcela real recién abierta, sin volúmenes ni terreno cargado todavía): `Box3` vacío — los límites de controles caen a un valor mínimo razonable, no a `NaN`/cero (mismo guard que ya usa `radioHorizontalEscena`).
- Geometría de parcela con anillo interior (patio) — `_geometria_parcela_catastro` (`analyzer/sitio.py:229-230`) ya documenta que solo usa el anillo EXTERIOR; el contorno 3D hereda ese mismo criterio, no dibuja huecos.
- Doble clic sobre el edificio/volumen que el arquitecto está diseñando: en Sandbox el clic simple ya selecciona el volumen (`alClicEnMount`) pero **no cierra nada** (a diferencia de `viewer-edificio.js`, aquí no hay conflicto real) — aun así, el recentrado por doble clic se limita a terreno/ortofoto/colindantes (no a los volúmenes propios) para no interferir con la selección/edición del volumen, que es la interacción principal del modo.
- Vista "Planta/Norte arriba": el Sandbox no tiene cámara ortográfica (a diferencia de `viewer-edificio.js`). Implementarla con una `PerspectiveCamera` casi cenital (mismo criterio que ya usa `getCameraPose("top", ...)` en el otro visor) evita añadir una segunda cámara y su gestión de cambio, manteniendo el Sandbox más simple que el visor de edificio a propósito.

## 7. Flujo del usuario

1. El arquitecto abre el Sandbox (con o sin parcela real).
2. Ve el gizmo de norte y la barra de herramientas desde el primer fotograma.
3. Si hay parcela real con geometría de Catastro disponible, ve el contorno real de su solar sobre el terreno/ortofoto.
4. Puede recentrar la vista con doble clic en cualquier punto del terreno/entorno, o usar los tres accesos rápidos de la barra de herramientas.

## 8. Criterios de aceptación

- [x] `controls.minDistance`/`maxDistance`/`camera.near`/`far` varían según el tamaño real de la escena — verificado por consola: sin parcela real (terreno orgánico, radio 150) `minDistance=7.5, maxDistance=550, near=0.75, far=2000`, coherente con la fórmula de `ajustarLimitesCamara`.
- [x] Doble clic sobre terreno/ortofoto/colindantes recentra el pivote sin saltos; doble clic sobre un volumen propio NO lo hace — verificado en vivo: `controls.target` sin cambios tras doble clic directo sobre un volumen, y con desplazamiento correcto tras doble clic sobre el terreno a su lado.
- [x] El gizmo de norte gira en tiempo real y al clicarlo vuelve al norte sin cambiar zoom/elevación — verificado en vivo (capturas antes/después).
- [x] La barra de herramientas tiene 3 botones funcionales: Isométrica (reset), Planta/Norte arriba, Alternar sombras — los 3 verificados en vivo.
- [x] Con parcela real y Catastro con geometría disponible, el contorno de parcela se ve alineado con la ortofoto — verificado en vivo con la parcela real de Madrid ya usada en PRDs anteriores de esta sesión (el contorno amarillo encaja exactamente sobre la vivienda real de la imagen).
- [x] Sin parcela real: cero contorno, cero aviso de error, cero regresión visual — verificado en vivo.
- [x] `node --input-type=module --check` (`viewer-sandbox.js`, `viewer-terreno.js`) y `python -m py_compile` (`app.py`, `analyzer/sitio.py`) sin errores; verificación visual en vivo (Chrome) completa.

**Bug encontrado y corregido durante la verificación:** el gizmo reutiliza la clase CSS `.viewer-compass` de `viewer-edificio.js`, que trae `opacity:0` de fábrica (fade de entrada que solo ese otro visor completa con `.intro-in`). El Sandbox no tiene esa coreografía — sin el fix quedaba invisible pese a existir en el DOM. Corregido añadiendo `.intro-in` al crearlo.

## 9. Riesgos

- **El contorno de parcela requiere un campo nuevo en el backend**: `_entorno_3d_para` (`app.py:1392`) hoy solo devuelve `centro`+`edificios_colindantes`; añadir `geometria_parcela` implica llamar a `obtener_datos_parcela`/`_geometria_parcela_catastro` (`analyzer/sitio.py`) desde ahí, con el mismo criterio best-effort que ya usa `edificios_colindantes_geometria`. Riesgo técnico bajo (la función ya existe y ya se usa en producción en otro flujo — Paso 0), pero es una llamada de red adicional por apertura de Sandbox con parcela real (Catastro WFS), con su propio coste de latencia — mitigado porque ya es asíncrono y "llega de refresco" como el resto del entorno urbano.
- **Ambigüedad de si "profesional tipo Cesium/Lumion" es el objetivo real del Sandbox**: el propio archivo documenta en su cabecera que el Sandbox es deliberadamente un boceto rápido, no una herramienta de precisión ("NO intenta convertir el volumen dibujado en la geometría EXACTA del edificio generado"). Elevar su pulido de navegación tiene sentido (barato, sin riesgo), pero no debería usarse como argumento para invertir más allá de esto sin una razón de negocio nueva — ver §14.
- No compite con `REFACTOR_MASTERPLAN.md` (módulo aislado); el campo nuevo de backend es aditivo, no rompe a nadie que ya consuma `_entorno_3d_para` (incluido `viewer-edificio.js`, que simplemente lo ignoraría a menos que se decida usarlo ahí también en un PRD aparte).

## 10. Impacto sobre módulos existentes

- `analyzer/sitio.py`: sin cambios — se reutiliza `obtener_datos_parcela`/`_geometria_parcela_catastro`, ya existentes.
- `app.py`: `_entorno_3d_para` gana un campo aditivo `geometria_parcela` (lat/lon del anillo exterior, o `None`).
- `static/viewer-terreno.js`: nueva función para proyectar el anillo de la parcela a ejes locales (reutiliza `metrosEsteNorteDesde`/`rotarAEjesLocales`, ya exportadas) y construir la polyline — compartible con `viewer-edificio.js` si en el futuro se quisiera ahí también (fuera de alcance de este PRD).
- `static/viewer-sandbox.js`: gizmo, doble clic, límites adaptativos, barra de herramientas, consumo del contorno de parcela.
- No toca `static/viewer-edificio.js` ni `static/viewer-vivienda.js`.

## 11. Plan de implementación dividido en pequeñas tareas

1. Límites de `OrbitControls` (`min/maxDistance`, `near/far`) derivados del `Box3` real — recalculados junto a `encuadrarCamaraAContenido`/`ajustarFrustumSombra`.
2. Gizmo de norte (adaptar `buildCompass` de `viewer-edificio.js`) + recentrado por doble clic (adaptar `onDblClickRecenter`), excluyendo los volúmenes propios del raycast.
3. Barra de herramientas flotante: Isométrica (reset a `encuadrarCamaraAContenido` + pose de estudio), Planta/Norte arriba (pose cenital), Alternar sombras (`sunLight.castShadow`/`renderer.shadowMap.enabled`, mismo patrón que `btnSombras` de `viewer-edificio.js`).
4. Backend: `geometria_parcela` en `_entorno_3d_para`, best-effort.
5. Frontend: construcción y render de la polyline del contorno en `viewer-terreno.js`, consumida desde `cargarEntorno`/`open()` del Sandbox.
6. Verificación: `node --check` + prueba en vivo (Chrome) con la parcela real ya usada en esta sesión (y confirmación de que Catastro sí devuelve geometría para ese punto, o documentar honestamente si no la tiene).

## 12. Plan de pruebas

- Prueba en vivo: escena pequeña (1 volumen) vs. escena con parcela real + colindantes — confirmar que los límites de zoom cambian.
- Prueba en vivo: doble clic sobre terreno recentra; doble clic sobre un volumen propio no interfiere con su selección.
- Prueba en vivo: gizmo clicable, vuelve al norte.
- Prueba en vivo: los 3 botones de la barra de herramientas.
- Prueba en vivo: contorno de parcela alineado con la ortofoto real, en la parcela de prueba de Madrid ya usada hoy.
- Prueba en vivo: parcela sin geometría de Catastro disponible — cero regresión.

## 13. Métricas para medir el éxito

Sin telemetría de uso del Sandbox hoy (mismo límite ya señalado en los dos PRDs anteriores de esta sesión). Éxito verificable por inspección contra los criterios de aceptación de §8.

## 14. Posibles motivos para NO implementar la idea (o para acotarla)

- El Sandbox es, por diseño explícito de su propio código, una herramienta de boceto rápido — no compite con Cesium/Lumion en ningún sentido real, y no debería intentar hacerlo más allá de una navegación cómoda. Si la vara de medida es "a la altura de un software profesional de arquitectura", la respuesta honesta es que no lo va a estar con estos cinco cambios ni con diez más — el objetivo realista es "no se siente torpe", no "compite con Cesium".
- `MOAT_ANALYSIS.md` sigue sin cambiar su valoración de foso bajo para el visor 3D — nada de este PRD lo mueve.
- El contorno de parcela es el único ítem con valor de producto real más allá de lo estético (información legal real, no solo pulido visual) — si el presupuesto de esta iteración es limitado, es el candidato a priorizar solo a él y posponer gizmo/toolbar/límites adaptativos (que son mejoras cosméticas de bajo riesgo pero también de bajo impacto de negocio).
- Alternativa más barata: implementar solo las tareas 1-3 (gizmo, doble clic, límites adaptativos, toolbar — todo frontend, sin tocar backend) y dejar el contorno de parcela (tarea 4-5, la única con cambio de backend) para una segunda fase si Pablo confirma que la información legal de linde es lo que de verdad le importa, no solo la estética de navegación.

---

**Decisión:** Implementado 2026-08-16 — alcance completo (§11, tareas 1-6), verificado en vivo.
