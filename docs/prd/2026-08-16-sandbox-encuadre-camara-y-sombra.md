# PRD — Encuadre automático de cámara y corrección de sombra en el Sandbox 3D

**Estado:** Borrador · **Fecha:** 2026-08-16 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 0. Contexto: qué queda FUERA de este PRD y por qué

La petición original ("REESTRUCTURACIÓN DE VISOR DE PARCELA Y ENTORNO 3D") pedía cuatro cosas. Antes de escribir código se verificó el estado real de cada una (lectura de código + prueba en vivo con datos reales de Puerta del Sol, Madrid, vía `/api/entorno-3d-punto`):

1. **Georreferenciación exacta (Norte/escala)** — ya implementada. `metrosEsteNorteDesde` + `rotarAEjesLocales` (`viewer-terreno.js`) hacen la proyección local en metros y la rotación a ejes locales, con fórmula verificada a mano en el propio código. Se descargaron y recompusieron a mano los 25 tiles reales del mosaico que arma `construirMosaicoOrtofoto` para lat=40.4168/lon=-3.7038: el resultado es una imagen coherente y correcta de Puerta del Sol — la matemática de tiles (`tileParaLonLat`) es correcta. **No hay bug de georreferenciación.**
2. **Geometría real de colindantes** — ya implementada. `construirEdificiosColindantes` extruye con `THREE.Shape`+`THREE.ExtrudeGeometry` los vértices reales que devuelve Overpass/OSM (`analyzer/sitio.py`), no cajas genéricas. Verificado contra una respuesta real del endpoint. **No hay bug de geometría.**
3. **DEM real (elevación del terreno)** — descartado explícitamente. Contradice la decisión de arquitectura ya tomada y documentada el 2026-08-16 (`viewer-terreno.js:221-228`): el DEM real queda reservado para `viewer-edificio.js`, que sí tiene una parcela georreferenciada permanente; el Sandbox puede no tener ninguna. Pablo confirmó mantener esa decisión.
4. **Encuadre de cámara (fit-bounds)** — **sí es una carencia real**, y es el objeto de este PRD.

Además, al reproducir la petición en vivo apareció un **segundo problema real, no pedido explícitamente pero con la misma causa raíz visual** (terreno con aspecto "estirado y oscuro" que el usuario atribuyó a la ortofoto): un desajuste entre el tamaño de la cámara de sombra del sol y el tamaño real del suelo que debe cubrir. Se documenta y se corrige en este mismo PRD porque comparte causa, módulo y verificación con el punto 4 — no es capacidad nueva, es una corrección (ver §10).

---

## 1. Problema que resuelve

Al abrir el Sandbox sobre una parcela real, la cámara arranca siempre en una posición fija (`45, 38, 45` mirando al origen), sin relación con el tamaño real de la parcela, el mosaico de ortofoto (~580×580 m) o los volúmenes que el usuario haya dibujado. Con parcelas grandes o volúmenes alejados del centro, esto puede dejar contenido relevante fuera de encuadre o forzar al usuario a hacer zoom/pan manual cada vez que abre el lienzo.

Además, la sombra del sol se configura con un `shadowHalfSize: 120` fijo (`viewer-sandbox.js:263`), independiente del tamaño real de lo que hay que iluminar: el mosaico de ortofoto mide ~580 m de lado y el radio de colindantes consultado al backend es 180 m (`_ENTORNO_3D_RADIO_M` en `app.py`) — ambos mayores que el frustum de sombra de 120 m de semilado. Fuera de ese frustum, three.js no proyecta sombra: en una vista oblicua/cercana (la misma que motiva el punto 4), el borde del terreno se ve con parches de luz/sombra inconsistentes que se pueden confundir con la propia textura de la ortofoto — es probablemente lo que Pablo interpretó como "ortofoto estirada y desalineada" en la captura que motivó el encargo original.

## 2. Usuario afectado

El arquitecto que usa el Modo Sandbox (`static/index.html` → "Lienzo libre") para probar volumetría sobre una parcela real ya vinculada en el Paso 0, antes de generar plantas con IA.

## 3. Objetivo de negocio

El Sandbox es la primera impresión visual del producto en esa parte del flujo. `MOAT_ANALYSIS.md` (§6) ya señala el visor 3D como pieza "vistosa para una demo" pero de foso bajo — precisamente por eso, los defectos visuales gratuitos (encuadre que corta la parcela, sombra que no cubre el terreno) cuestan credibilidad de forma desproporcionada a lo barato que es arreglarlos: no es una inversión estratégica, es higiene de una pieza que ya existe y ya se enseña.

## 4. Objetivo técnico

- Al abrir el Sandbox con una parcela real (o al añadir/editar/borrar un volumen), la cámara encuadra automáticamente todo el contenido relevante de la escena (ortofoto/terreno, colindantes y volúmenes del usuario) sin cortar nada, respetando `maxPolarAngle` ya existente.
- El frustum de la sombra del sol cubre siempre, como mínimo, el radio real del contenido cargado (mosaico de ortofoto o terreno orgánico + colindantes), no un valor fijo arbitrario.

## 5. Casos de uso

- Parcela real pequeña (mosaico ~580 m) sin volúmenes: la cámara encuadra el mosaico completo con un margen razonable.
- Parcela real con varios volúmenes de gran tamaño (hasta 60×60 m, 20 plantas) cerca del borde del radio de colindantes (180 m): el encuadre inicial los incluye a todos.
- Sin parcela real (terreno orgánico sintético): el encuadre se calcula sobre el terreno genérico + volúmenes, igual que hoy pero calculado, no fijo.
- Usuario borra el único volumen que había: el encuadre vuelve a cubrir solo parcela/terreno.

## 6. Casos límite

- Escena vacía (parcela real sin colindantes ni volúmenes todavía): no debe dividir por cero ni dejar una cámara degenerada; cae al encuadre por defecto actual (`45,38,45`→origen).
- Un volumen absurdamente grande (60×60×20 plantas, límites ya impuestos por los sliders del panel) no debe alejar tanto la cámara que la parcela quede minúscula — aplicar una distancia máxima razonable (reutilizar `maxDistance: 400` ya existente como techo).
- Recalcular el encuadre en cada cambio de volumen (no solo al abrir) podría resultar intrusivo si el usuario está orbitando manualmente — por eso el fit-bounds solo se dispara al abrir el Sandbox y al añadir/borrar un volumen (no en cada arrastre de slider), igual que hoy se reconstruye la geometría.
- Mosaico de ortofoto que aún no ha llegado (fetch en curso): el encuadre inicial usa lo que ya hay (terreno neutro) y no bloquea la apertura; no hace falta un segundo recálculo cuando llega la ortofoto porque su extensión es fija y conocida de antemano (~580 m), ya contemplada en el cálculo inicial cuando hay parcela real.

## 7. Flujo del usuario

1. El usuario abre el Sandbox (con o sin parcela real) o añade/borra un volumen.
2. La cámara se reposiciona automáticamente a una vista de estudio a 45° que encuadra todo el contenido relevante, sin cortar nada, sin que el usuario tenga que hacer zoom/pan manual.
3. El usuario puede seguir orbitando/paneando libremente después; el fit-bounds no vuelve a moverle la cámara hasta el siguiente añadir/borrar volumen.

## 8. Criterios de aceptación

- [ ] Al abrir el Sandbox con la parcela real de prueba (lat=40.4168, lon=-3.7038), el mosaico de ortofoto completo es visible en el primer fotograma sin recorte.
- [ ] Al añadir un volumen de 60×60 m cerca del borde del radio de colindantes, el encuadre automático lo incluye sin necesidad de zoom manual.
- [ ] El frustum de sombra (`shadow.camera.left/right/top/bottom`) cubre como mínimo el radio real del contenido cargado (≥180 m con parcela real; el tamaño del terreno orgánico sin parcela real), verificable leyendo `sunLight.shadow.camera` desde consola.
- [ ] Sin parcela real ni volúmenes, el comportamiento visual de apertura es equivalente al actual (no hay regresión en el caso ya probado).
- [ ] `node --input-type=module --check` sin errores sobre los archivos tocados; verificación visual en vivo (Chrome) del caso con parcela real de Puerta del Sol.

## 9. Riesgos

- Técnico: calcular un `Box3` sobre una escena con geometría todavía cargándose de forma asíncrona (ortofoto llega después de los colindantes) obliga a recalcular el encuadre en más de un punto del flujo de `open()` — riesgo de un segundo "salto" de cámara visible si no se hace con cuidado. Mitigación: calcular el encuadre final una vez, cuando se conoce de antemano la extensión máxima posible (radio de colindantes + tamaño fijo del mosaico), no esperar a cada pieza async.
- No compite con nada de `REFACTOR_MASTERPLAN.md` — es un módulo aislado (`viewer-sandbox.js`/`viewer-terreno.js`) sin dependencias con el motor de reglas ni el pipeline de análisis.

## 10. Impacto sobre módulos existentes

- `static/viewer-sandbox.js`: función de encuadre automático tras `open()` y tras `_reconstruirVolumen`/añadir/borrar; cambio del `shadowHalfSize` fijo (120) por uno calculado a partir del radio real de contenido.
- `static/viewer-terreno.js` / `static/viewer-geometry.js`: posible función compartida de "calcular Box3 + posición de cámara de estudio", si conviene reutilizar patrón similar al ya existente en `viewer-edificio.js:794` (no duplicar la lógica de fit-bounds si ya existe algo reutilizable).
- No toca `app.py` ni `analyzer/` — ninguno de los dos hallazgos requiere cambios de backend.

## 11. Plan de implementación dividido en pequeñas tareas

1. Extraer/adaptar una función `encuadrarCamaraAContenido(scene, camera, controls, radioMinimo)` que calcule un `Box3` de la escena y reposicione cámara+target manteniendo el ángulo de estudio a 45°, con techo en `maxDistance`.
2. Llamarla al final de `open()` (tras añadir terreno/colindantes/volúmenes ya existentes al abrir) y tras cada añadir/borrar volumen.
3. Sustituir `shadowHalfSize: 120` por un valor calculado (`Math.max(180, radio real del contenido)`), coherente con `_ENTORNO_3D_RADIO_M` del backend.
4. Verificación: `node --input-type=module --check` + prueba en vivo en Chrome con la parcela de Puerta del Sol y con un volumen grande añadido cerca del borde.

## 12. Plan de pruebas

- Prueba en vivo (Chrome, ya con servidor local corriendo): abrir Sandbox con lat/lon reales, capturar screenshot antes/después, confirmar que el mosaico completo cabe en el encuadre inicial.
- Prueba en vivo: añadir un volumen de 60×60 m, confirmar que el encuadre lo incluye.
- Inspección de `sunLight.shadow.camera.left/right/top/bottom` desde consola tras abrir con parcela real, confirmar que cubre ≥180 m.
- Caso sin parcela real: confirmar que no hay regresión visual respecto al comportamiento actual.

## 13. Métricas para medir el éxito

No hay telemetría de uso del Sandbox hoy (`MOAT_ANALYSIS.md` ya señala la falta de registro histórico como carencia general del producto). Éxito aquí es binario y verificable por inspección: los criterios de aceptación de §8 se cumplen. No se propone instrumentación nueva solo para esto — sería desproporcionado para un ajuste de encuadre.

## 14. Posibles motivos para NO implementar la idea

- El Sandbox es, por diseño, una herramienta de boceto rápido, no un visor de presentación final — el encuadre fijo actual funciona razonablemente bien para el caso común (parcela de tamaño medio, pocos volúmenes cerca del centro), y el usuario ya puede hacer zoom/pan manual en dos segundos. Si el volumen de uso real del Sandbox es bajo, esto es pulido cosmético de baja prioridad frente a otras tareas de `REFACTOR_MASTERPLAN.md`.
- Alternativa más barata: en vez de un fit-bounds dinámico completo, simplemente ampliar la posición de cámara por defecto y el `shadowHalfSize` a un valor fijo mayor (p. ej. 200 m) que cubra el caso común sin la complejidad de calcular `Box3` dinámicamente. Se descarta como alternativa principal porque no escala si en el futuro el radio de colindantes (`_ENTORNO_3D_RADIO_M`) cambia, pero es la opción a considerar si se prefiere el cambio mínimo.

---

**Decisión:** _pendiente de revisión por Pablo_
