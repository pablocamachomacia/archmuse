# PRD — Terreno real y materiales ArchViz en el Visor Sandbox

**Estado:** Borrador · **Fecha:** 2026-08-16 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 1. Problema que resuelve

Petición directa de Pablo: el Visor Sandbox (`static/viewer-sandbox.js`, modo "Lienzo libre") representa los volúmenes sobre un `CircleGeometry` plano con `MeshStandardMaterial` mate, sin relieve de terreno ni materiales que se lean como arquitectura real (vidrio, hormigón, biselados). El dolor es de percepción en demo: los volúmenes se ven como cajas de estudio de masas, no como una propuesta arquitectónica.

Importante matizar el problema tal como está planteado, antes de diseñar la solución: la petición habla de "elevación real de la parcela", pero el Visor Sandbox es, por diseño, el modo que **puede no tener ninguna parcela real vinculada** — el propio comentario en `static/index.html:89-92` lo dice explícitamente: *"puede no haber ningún edificio todavía: es exactamente el punto de partida de este modo"*. El visor que sí trabaja siempre sobre un sitio georreferenciado real es otro, `viewer-edificio.js`, con su pipeline `/api/proyectos/<id>/entorno-3d` (ortofoto + edificios colindantes reales, añadido el 2026-08-16 a petición explícita). Esto cambia el diseño de la solución — ver §3 y §14.

## 2. Usuario afectado

Arquitecto individual o de estudio pequeño, en la fase de estudio de volumetría inicial (antes de tener una vivienda generada) o enseñando el producto en una demo comercial. No es un usuario que use el Sandbox para validar cumplimiento normativo — ese rol lo cumplen el motor de reglas y el visor de plano/edificio generado.

## 3. Objetivo de negocio

Ligado a la parte "vistosa en demo" del producto, no al foso técnico. `MOAT_ANALYSIS.md` (§6) ya identifica el visor 3D como una pieza que "aporta poco valor aunque sea compleja" precisamente por este motivo: es una demostración de capacidad técnica desconectada del motor de hallazgos, no una herramienta de validación. Mejorar su realismo visual **no cambia esa valoración** — sigue siendo inversión en la superficie más replicable del producto (`MOAT_ANALYSIS.md` línea 84: "el resto — interfaz, IA narrativa, visor 3D, exportación a PDF — es replicable por cualquier equipo de ingeniería competente en semanas o meses"). El valor de negocio real de esta tarea es concreto pero acotado: mejora la primera impresión en una demo comercial, no la retención ni el foso.

## 4. Objetivo técnico

Una vez implementado (en el alcance recomendado en §14, no el alcance completo pedido):
- Los volúmenes del Sandbox se renderizan con materiales que distinguen visualmente sólido (hormigón/blanco arquitectónico) de acristalado (vidrio con transmisión), con un borde sutil marcado.
- El terreno del Sandbox deja de ser un disco perfectamente plano: tiene una variación de relieve suave, generada localmente (sin llamada a ninguna API externa).
- La escena proyecta sombras reales de los volúmenes sobre el terreno (esto ya está parcialmente activado — `shadowMapSize`, `shadowBias`, etc. ya configurados en `construirEscena3D`, línea 168 — pero ninguna luz direccional ni malla del terreno participan todavía correctamente en ese pipeline; hay que confirmarlo en implementación).
- El rendimiento en un portátil de gama media no cae por debajo de 30 fps con la escena típica (1-6 volúmenes).

## 5. Casos de uso

1. Un arquitecto abre "Lienzo libre" sin ningún sitio vinculado, añade 2-3 volúmenes y ajusta plantas/rotación — ve una escena con terreno con relieve orgánico (no real) y materiales ArchViz.
2. Un arquitecto abre el Sandbox desde un proyecto que **sí** tiene un sitio real vinculado (Paso 0) — en el alcance recomendado, el Sandbox sigue usando terreno orgánico genérico (no DEM real); si se quiere terreno real georreferenciado, ese caso ya lo cubre `viewer-edificio.js` (ver §14).
3. Demo comercial: se enseña el Sandbox en vivo añadiendo volúmenes — la superficie sigue respondiendo con fluidez mientras se manipulan sliders de largo/ancho/plantas/rotación.

## 6. Casos límite

- Volumen colocado fuera del radio del disco de terreno (`CircleGeometry(150, ...)`): ya es un caso preexistente, no nuevo de esta tarea; confirmar que el relieve no genera artefactos visibles en el borde del disco.
- GPU integrada sin soporte completo de `MeshPhysicalMaterial`/`transmission` (equipos de gama muy baja): degradar sin excepción a `MeshStandardMaterial` en vez de romper el render — three.js no lanza error por esto normalmente, pero hay que verificarlo, no asumirlo.
- Sesión sin WebGL2 (`transmission` de `MeshPhysicalMaterial` depende de renderizar a un buffer de fondo, más caro que `MeshStandardMaterial`): confirmar degradación aceptable en el hardware real de Pablo antes de dar la tarea por cerrada, no solo en el navegador de desarrollo.

## 7. Flujo del usuario

Sin cambios respecto al flujo actual del Sandbox (`viewer-sandbox.js`): abrir modo Lienzo libre → "+ Añadir volumen" → ajustar con los sliders del panel → "Generar plantas con IA". Esta tarea no toca ese flujo, solo el resultado visual de cada paso.

## 8. Criterios de aceptación

1. Los volúmenes "sólidos" se ven con un material mate claro (hormigón/blanco arquitectónico), no gris translúcido plano.
2. Existe al menos un tipo de volumen o cara renderizable con material acristalado (`MeshPhysicalMaterial` con `transmission`, `roughness` bajo) — activable por el usuario o aplicado a una parte del volumen (fachada), a decidir en implementación.
3. Los bordes de cada volumen tienen una línea sutil (`EdgesGeometry` + `LineBasicMaterial` fino), visible pero no dominante.
4. El terreno tiene relieve no-plano (desplazamiento de vértices), generado localmente con ruido/interpolación — sin llamada de red.
5. Los volúmenes proyectan sombra visible sobre el terreno con relieve.
6. Con 6 volúmenes en escena, el frame rate no cae de forma perceptible (verificación manual, no hay infraestructura de medición de fps en este proyecto).
7. No se añade ninguna dependencia de red nueva (ninguna llamada a API de elevación) al camino crítico de carga del Sandbox — ver §14 sobre por qué se excluye del alcance.

## 9. Riesgos

- **Compite directamente con una tarea ya priorizada en `REFACTOR_MASTERPLAN.md`** (línea 271): vendorizar `three.js` para dejar de depender de `unpkg.com` en el visor 3D, precisamente porque hoy es un punto de fallo en demo. Añadir una *nueva* dependencia de red (API de elevación externa, como pedía el alcance completo) va en la dirección contraria a esa tarea — sustituye un riesgo de "la CDN no responde en la demo" por dos. Es la razón principal por la que en §14 se recomienda excluir la integración de DEM real del alcance.
- **Coste de render**: `MeshPhysicalMaterial` con `transmission` es notablemente más caro que `MeshStandardMaterial` (renderiza un pase adicional). Con SSAO añadido encima, el coste combinado en GPU integrada no está verificado — riesgo de que la mejora visual llegue con una regresión de fluidez que nadie pidió.
- **Riesgo de foso invertido** (ya señalado en `MOAT_ANALYSIS.md` §6): tiempo de ingeniería en la pieza del producto que un competidor replica "en semanas", mientras `REFACTOR_MASTERPLAN.md` tiene pendientes tareas que sí protegen el foso real (el motor de reglas, ver `TECH_REVIEW.md`). No es un motivo para no hacer nada de esto, pero sí para acotarlo (§14).

## 10. Impacto sobre módulos existentes

- `static/viewer-sandbox.js` (290 líneas): función `geometriaVolumen`/`MAT_VOLUMEN`/`MAT_VOLUMEN_SELECCIONADO` (línea 47-77) y la construcción del terreno (línea 62-64, `construirCirculoBase` o equivalente) son el foco principal.
- `static/index.html`: si se introduce un nuevo material o helper de terreno compartido entre visores, decidir si vive en un módulo nuevo (`static/terreno-organico.js` o similar) importado por `viewer-sandbox.js`, en vez de duplicar lógica si `viewer-edificio.js` ya tiene algo parecido para su terreno real (confirmar en implementación si existe).
- `static/viewer-edificio.js` (2048 líneas): **no se toca** en el alcance recomendado — si en el futuro se decide llevar terreno DEM real a algún visor, es el candidato natural (ya tiene el pipeline de sitio real), no el Sandbox.
- Ningún módulo de `analyzer/` ni `app.py` — esto es puramente cliente/three.js.

## 11. Plan de implementación dividido en pequeñas tareas

*(Alcance recomendado — ver §14; excluye integración de DEM/API de elevación externa)*

1. Sustituir `MAT_VOLUMEN` por dos materiales: uno sólido tipo hormigón/blanco (`MeshStandardMaterial` ajustado, roughness alto, color claro) y uno acristalado (`MeshPhysicalMaterial` con `transmission`, `roughness: 0.1`, `metalness: 0.1`), aplicables por cara o por volumen según se decida.
2. Añadir `EdgesGeometry` + `LineSegments` sutil a cada volumen al crearlo (`geometriaVolumen`/creación del mesh).
3. Sustituir el `CircleGeometry` plano del terreno por una malla con desplazamiento de vértices mediante ruido (Perlin/Simplex simple, sin dependencia nueva de npm — implementable en unas pocas líneas) para relieve orgánico suave.
4. Confirmar/ajustar la `DirectionalLight` existente para que el terreno con relieve reciba y proyecte sombra correctamente (el `shadowMap` ya está configurado, línea 168 de `viewer-sandbox.js`; falta confirmar que la luz y el material del terreno participan).
5. (Opcional, evaluar coste/beneficio en implementación) Añadir un pase de SSAO (`THREE.SSAOPass` de `examples/jsm/postprocessing`) solo si el frame rate en hardware de gama media lo admite — probarlo antes de darlo por incluido, no asumir.
6. Verificación manual de rendimiento con 1, 3 y 6 volúmenes en la máquina de Pablo.

*(Fuera de alcance en esta iteración, ver §14: integración de API de elevación real DEM/Terrain-RGB/Open-Elevation.)*

## 12. Plan de pruebas

No hay suite automatizada de pruebas visuales/3D en el proyecto (`TECH_REVIEW.md` no documenta ninguna para el visor). Verificación manual: abrir Sandbox, añadir volúmenes de distintos tamaños, confirmar visualmente materiales/bordes/sombras/relieve, y medir fluidez percibida (no hay instrumentación de fps en el proyecto — sería una mejora aparte, no bloqueante aquí).

## 13. Métricas para medir el éxito

Sin instrumentación de producto en este proyecto (no hay analítica de uso), el único criterio realista es cualitativo: valoración directa de Pablo tras ver el resultado en su máquina, y si se usa en una demo comercial, si mejora la reacción del interlocutor. No se propone ninguna métrica cuantitativa falsa solo por rellenar la sección.

## 14. Posibles motivos para NO implementar la idea (tal como se pidió)

El **alcance completo tal como se pidió** (materiales + terreno con relieve local + integración de DEM real vía API pública) tiene un problema de diseño, no solo de prioridad: **el Visor Sandbox es, por especificación explícita ya documentada en el código, el modo sin sitio real garantizado.** Pedirle elevación real de "la parcela" a un visor cuyo caso de uso central es no tener parcela vinculada todavía es resolver el problema en el módulo equivocado. Dos alternativas, en orden de recomendación:

1. **(Recomendada, es el alcance de este PRD)** Hacer la mejora de materiales/bordes/sombras/relieve orgánico local en `viewer-sandbox.js` — resuelve el dolor real ("se ve como cajas de estudio de masas") sin añadir ninguna dependencia de red nueva, y sin competir con la tarea ya priorizada de vendorizar `three.js` (`REFACTOR_MASTERPLAN.md` línea 271) en la dirección contraria.
2. Si lo que de verdad se quiere es terreno **real** georreferenciado, la tarea correcta es extender `viewer-edificio.js` (que ya tiene el pipeline de sitio real, `/api/proyectos/<id>/entorno-3d`, y ya trae ortofoto + edificios colindantes reales) — no el Sandbox. Eso sería un PRD aparte, con su propia evaluación de qué API de elevación usar (Mapbox Terrain-RGB requiere token y cuota de pago; Open-Elevation es un servicio comunitario sin garantía de disponibilidad — ninguna de las dos es gratis-y-fiable a la vez) y de cómo se degrada quando no hay datos, tal como ya pide el propio brief original.

Si Pablo prefiere el alcance completo tal como se pidió originalmente (incluyendo DEM real en el Sandbox), decirlo explícitamente al aprobar este PRD y se amplía §11 en consecuencia — pero la recomendación de este documento es no hacerlo en la primera iteración.

---

**Decisión:** _pendiente de revisión por Pablo_
