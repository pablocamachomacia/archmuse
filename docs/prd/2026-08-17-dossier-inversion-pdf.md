# PRD — Dossier de Inversión en PDF

**Estado:** Borrador · **Fecha:** 2026-08-17 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 0. Resumen para decidir rápido

Encargo de Pablo: `analyzer/dossier_pdf.py` que genere un PDF estilo dossier corporativo (portada con render 3D + mapa, ficha urbanística, planos 2D, cuadro de viabilidad), con cabecero personalizable (logo/nombre de la promotora).

A diferencia del PRD de IFC, aquí **no hay ningún dato inventado en juego** — el riesgo de este PRD es de **plomería técnica**, no de honestidad: varias de las piezas pedidas existen como dato real pero viven hoy en sitios de los que `analyzer/dossier_pdf.py` (backend, Python) no puede tirar directamente sin trabajo de integración. Verificado leyendo el código:

- **`reportlab` ya es la librería usada para PDF en este proyecto** (`analyzer/pdf_report.py`) — no hace falta una dependencia nueva y pesada como en el PRD de IFC. Riesgo de dependencia bajo.
- **El Sólido Capaz ya se persiste en servidor** (`analyzer/storage.py`, columna `solido_capaz`, `app.py:178-187`) — la ficha técnica urbanística (edificabilidad, ocupación, plantas) se puede construir con datos reales ya guardados, sin recalcular nada.
- **Los planos 2D ya existen y ya se reutilizan en informes** (`analyzer/plan_svg.py`, ya consumido por `reporter.py` y por el informe HTML) — reutilizable directamente.
- **Ya hay un `MAPBOX_TOKEN` disponible en el servidor** (`app.py:157`, hoy expuesto solo al cliente para el visor 3D) — puede reutilizarse en el backend para pedir una imagen estática de mapa (Mapbox Static Images API) centrada en la ubicación real ya geocodificada del proyecto (Catastro), sin depender de que el navegador esté abierto ni de capturar nada del cliente. Esto SÍ es alcanzable de forma honesta y sin plomería nueva compleja.
- **El render 3D del edificio es la única pieza que hoy no tiene ninguna vía de generación server-side.** El visor 3D es Three.js puro en el navegador (`viewer-edificio.js`) — no existe renderizado 3D headless en el servidor, ni un mecanismo ya construido para capturar el canvas del cliente y subirlo. Generarlo de verdad requiere uno de dos caminos nuevos (ver §6/§9): (a) el navegador captura el `<canvas>` ya renderizado (`canvas.toDataURL()`) y lo sube al endpoint del dossier — barato, reutiliza el render que el usuario ya está viendo, pero exige que el dossier se pida desde una sesión con el visor 3D ya abierto y renderizado; o (b) un renderizador 3D headless en servidor (Puppeteer/Playwright + Three.js offscreen, o similar) — mucho más pesado, nueva infraestructura, nuevo punto de fallo.
- **La "viabilidad económica" que se pide en el cuadro hoy solo existe en memoria del navegador** (`state.viabilidad` en `static/app.js`, nunca se envía al backend) — el endpoint del dossier necesita recibir esos valores (ratio €/m², coste de suelo, precio de venta) como parte de la petición, igual que cualquier otro dato que hoy solo vive en el cliente. No es un problema grave, pero es una pieza de integración nueva, no algo que el backend ya tenga.
- **"Métricas de rentabilidad"** (más allá de PEM/margen bruto ya existente) depende del PRD de Viabilidad Financiera (`2026-08-17-analisis-de-viabilidad-financiera.md`, aún sin aprobar). Por defecto, este PRD asume que el cuadro de viabilidad del dossier muestra lo que YA está aprobado e implementado (PEM, repercusión de suelo, margen bruto) — si Pablo aprueba antes el PRD de Financiera, el dossier puede incluir también Margen Promotor (%)/TIR cuando estén disponibles.

## 1. Problema que resuelve

Hoy, tras generar/analizar un proyecto, no hay forma de producir un documento presentable a un tercero (promotor, banco, inversor) — solo existe el informe técnico de calidad arquitectónica (`pdf_report.py`), pensado para el propio arquitecto, no para presentar una inversión.

## 2. Usuario afectado

El arquitecto o el estudio que necesita presentar un proyecto a un promotor, inversor o entidad financiera — un documento de cara al cliente final de ArchMuse, no una herramienta de trabajo interno como el resto de informes.

## 3. Objetivo de negocio

Conecta con el pilar de "asesor"/herramienta profesional completa de `NORTH_STAR_2031.md` — un dossier de calidad presentable es lo que separa una herramienta de análisis de una herramienta de venta de proyectos. El riesgo de `DESTROY_ARCHMUSE.md` aquí es más de **calidad percibida** que de honestidad de datos: un dossier con maquetación pobre, con un mapa o render ausente, o con un cuadro económico que dice "estimación tuya" en un documento pensado para un banco, puede restar más credibilidad de la que suma. La calidad estética del documento es, en este PRD, un requisito funcional, no cosmético.

## 4. Objetivo técnico

- `analyzer/dossier_pdf.py`: función que recibe el proyecto (rooms/units), el Sólido Capaz ya persistido, los parámetros de viabilidad económica (recibidos en la petición, ver §0), datos de ubicación ya geocodificados, y opcionalmente una imagen de render 3D subida por el cliente y un logo/nombre de promotora, y produce un PDF multi-página con maquetación de dossier corporativo (portada, ficha urbanística, planos, cuadro de viabilidad).
- Portada: título, nombre del proyecto, imagen de mapa (generada server-side vía Mapbox Static Images API con el `MAPBOX_TOKEN` ya disponible) + imagen de render 3D si el cliente la ha subido (ver §6 para el caso sin ella).
- Ficha técnica urbanística: edificabilidad, ocupación, plantas y demás parámetros del Sólido Capaz ya persistido — mismos números que ya muestra el Sandbox, sin recalcular.
- Planos 2D: reutiliza `plan_svg.py`, una página por planta.
- Cuadro de viabilidad: reutiliza los mismos campos y fórmula ya en producción en la pestaña de Viabilidad Económica, con el mismo badge de "estimación tuya" ya establecido — un dossier de cara a un tercero es exactamente el sitio donde ese badge importa más, no menos.
- Cabecero personalizable: logo (imagen subida) + nombre de la promotora/estudio, aplicado a todas las páginas.

## 5. Casos de uso

1. Arquitecto con un proyecto y Sólido Capaz calculados, viabilidad económica rellenada y el visor 3D ya renderizado en pantalla, pulsa "Generar Dossier de Inversión" → sube automáticamente la captura del canvas 3D, introduce (opcionalmente) logo y nombre de su estudio → descarga un PDF con portada (mapa real + render 3D real), ficha urbanística, planos y cuadro de viabilidad.
2. Arquitecto sin viabilidad económica rellenada aún → el dossier se genera igualmente, con esa sección marcada como "pendiente de completar" en vez de con datos inventados o vacíos sin explicación.
3. Arquitecto sin haber abierto el visor 3D en esa sesión → el dossier se genera sin la imagen de render 3D en portada (sustituida por el mapa y/o el plano de planta baja, nunca por un render inventado o un placeholder genérico que aparente ser real).

## 6. Casos límite

- **Sin captura de render 3D disponible** (caso de uso 3): la portada no debe fallar ni mostrar una imagen rota — usar un layout de portada alternativo sin esa imagen (mapa + planta baja a mayor tamaño), documentado como comportamiento esperado, no como error.
- **Proyecto en un municipio sin datos completos de edificabilidad/ocupación** (limitación ya documentada en `normativa_madrid.py`, no exclusiva de este PRD): la ficha urbanística debe mostrar "no disponible" en esos campos, nunca inventar un valor plausible para no dejar la ficha con huecos.
- **Viabilidad económica sin rellenar**: mismo criterio que la pestaña actual — sección del dossier vacía/marcada como pendiente, no con ceros que parezcan un cálculo real.
- **Logo subido en formato o tamaño no soportado**: validar formato (PNG/JPG) y tamaño máximo antes de intentar embeberlo en el PDF, con error claro al usuario, no un fallo silencioso de generación.
- **Proyecto sin ninguna planta resuelta** (caso límite improbable pero posible): el dossier no debe generarse vacío — mensaje explicando qué falta antes de poder generarlo.

## 7. Flujo del usuario

1. Arquitecto con proyecto, Sólido Capaz y (opcionalmente) viabilidad económica y visor 3D ya usados en la sesión, abre "Generar Dossier de Inversión".
2. Opcionalmente sube logo y nombre de la promotora/estudio.
3. Si el visor 3D estaba abierto, el sistema captura automáticamente el canvas actual como imagen de portada (con posibilidad de que el usuario la vea y confirme antes de generar, no un envío ciego).
4. Pulsa "Generar" → recibe el PDF, con las secciones ausentes marcadas honestamente en vez de omitidas sin explicación o rellenadas con datos inventados.

## 8. Criterios de aceptación

1. La ficha técnica urbanística del PDF coincide exactamente con los datos del Sólido Capaz ya persistido para ese proyecto — mismos números que el Sandbox.
2. Los planos 2D del PDF son el mismo SVG/geometría que ya usa el resto de informes (`plan_svg.py`), no una representación paralela.
3. El cuadro de viabilidad económica del PDF usa la misma fórmula ya en producción y lleva el mismo badge de estimación propia cuando aplica.
4. El PDF se genera correctamente (sin error, con layout coherente) tanto con como sin imagen de render 3D disponible.
5. El logo y nombre de la promotora, cuando se proporcionan, aparecen en el cabecero de todas las páginas del documento.
6. Ningún campo del PDF muestra un valor inventado cuando el dato de origen no existe — se muestra "no disponible"/"pendiente", nunca un placeholder que aparente ser un dato real.

## 9. Riesgos

- **El render 3D depende de que el usuario ya haya abierto el visor en esa sesión** — si Pablo esperaba un render generado sin depender del navegador (p. ej. desde un enlace compartido o una generación programada), eso requiere renderizado headless server-side, un proyecto bastante más grande y con dependencias nuevas pesadas (mismo tipo de riesgo que `ifcopenshell` en el PRD de IFC). Este PRD asume la vía de captura de cliente por defecto — ver §14 si Pablo prefiere la otra.
- **Calidad estética "banca privada" es subjetiva y difícil de validar sin iteración visual** — recomiendo una primera versión revisada visualmente con Pablo antes de darla por cerrada, no solo verificada por criterios de aceptación funcionales.
- **Envío de datos de viabilidad económica al backend** (hoy solo en el cliente) abre una superficie nueva pequeña — validar los mismos campos que ya valida el cliente (`numeroOVacio`), no confiar ciegamente en lo recibido.
- Compite por tiempo con el resto de PRD en cola hoy — y depende parcialmente del de Viabilidad Financiera si se quiere Margen Promotor/TIR en el cuadro (ver §0).

## 10. Impacto sobre módulos existentes

- **Nuevo** `analyzer/dossier_pdf.py`, usando `reportlab` (ya dependencia).
- `app.py`: nuevo endpoint `POST /api/proyectos/<id>/dossier-pdf`, recibiendo viabilidad económica + imagen de render 3D (opcional, como archivo/base64) + logo (opcional) en el cuerpo de la petición; reutiliza `obtener_solido_capaz` ya existente.
- `static/app.js` o nuevo `static/dossier.js`: captura del canvas 3D (`canvas.toDataURL()`), formulario de logo/nombre, botón "Generar Dossier de Inversión".
- Lee (no modifica) `plan_svg.py`, `analyzer/storage.py`, el `MAPBOX_TOKEN` ya expuesto en `app.py:161` (reutilizado server-side, no cambia su contrato actual con el cliente).

## 11. Plan de implementación dividido en pequeñas tareas

1. `analyzer/dossier_pdf.py`: portada base (título, mapa vía Mapbox Static Images API, sin render 3D todavía) — función pura testeable con datos sintéticos.
2. `analyzer/dossier_pdf.py`: ficha técnica urbanística desde `solido_capaz` persistido.
3. `analyzer/dossier_pdf.py`: página(s) de planos 2D reutilizando `plan_svg.py`.
4. `analyzer/dossier_pdf.py`: cuadro de viabilidad económica (recibido como parámetro).
5. `app.py`: endpoint que junta todo, recibiendo viabilidad + logo + imagen 3D opcional.
6. `static/`: captura de canvas 3D + formulario de logo/nombre + botón de generación.
7. `analyzer/dossier_pdf.py`: cabecero con logo/nombre aplicado a todas las páginas.
8. Verificación visual con Pablo (criterio subjetivo de calidad estética, no solo funcional).
9. Verificación de los 6 criterios de §8, incluyendo los 2 casos límite de "sin render 3D" y "municipio sin datos de edificabilidad".

## 12. Plan de pruebas

- `python -m py_compile app.py analyzer/dossier_pdf.py`.
- Tests con datos sintéticos para cada sección del PDF (ficha urbanística, planos, viabilidad) por separado.
- En vivo: generar el dossier completo para el proyecto de prueba ya usado en sesiones anteriores, con y sin render 3D, con y sin logo, revisando visualmente el resultado.

## 13. Métricas para medir el éxito

Cualitativo: Pablo confirma que el dossier generado tiene calidad suficiente para entregarlo a un tercero real (promotor/banco) sin necesitar retoque manual posterior, y que ninguna sección muestra un dato inventado.

## 14. Posibles motivos para NO implementar la idea (o para recortar el alcance)

- **Si el render 3D "de verdad" (sin depender de que el navegador esté abierto) es un requisito no negociable**, este PRD tal como está no lo cubre — haría falta renderizado headless server-side, un proyecto notablemente más grande y con una dependencia nueva pesada, del mismo tipo de riesgo ya señalado en el PRD de IFC. Recomiendo empezar con captura de cliente (más barato, disponible ya) y evaluar la necesidad real del caso headless después de ver cuánto limita en la práctica.
- **El cuadro de "métricas de rentabilidad" pedido en el encargo original probablemente se refiere a Margen Promotor (%) y TIR**, que hoy no existen (dependen del PRD de Viabilidad Financiera, aún sin aprobar) — si Pablo los considera imprescindibles en el dossier desde la v1, conviene aprobar primero ese PRD.
- **La calidad estética "banca privada" es el criterio más caro de cumplir bien** — vale la pena invertir en una ronda de iteración visual con Pablo antes de considerar esto terminado, en vez de asumir que el primer resultado de `reportlab` ya alcanza ese nivel.
- Si Pablo acepta la vía de captura de cliente para el render 3D y el alcance de viabilidad económica ya existente (sin esperar a Financiera), este PRD es implementable en el alcance descrito.

---

**Decisión:** **Aprobado (2026-08-17)**. Render 3D vía captura de `<canvas>` cliente (opción por defecto de §14, no headless server-side). Cuadro de viabilidad usa los datos ya introducidos en el formulario de Viabilidad Económica/Análisis Avanzado (enviados en la petición, ver §0). Mapa de ubicación vía Mapbox Static Images API server-side con el `MAPBOX_TOKEN` ya existente.
