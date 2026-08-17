# PRD — Shell lateral e Inicio de proyectos

**Estado:** Borrador · **Fecha:** 2026-08-02 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

> **Deroga la decisión 1 de `docs/design/2026-08-01-especificacion-shell.md`** (barra superior de menús) y **absorbe la tarea 11 del PRD `2026-08-01-gestor-de-proyectos-y-persistencia.md`** ("Pantalla de proyectos en la SPA"), que deja de ser una tarea de aquel documento y pasa a ser este. Si este PRD se aprueba, la especificación de Shell debe pasar a v3 en la misma tanda de trabajo: dejar dos "decisiones cerradas" contradictorias en el repositorio es peor que cualquiera de las dos por separado.

**Decisiones de Pablo que fijan el alcance (2026-08-02):**

| # | Decisión |
|---|---|
| 1 | El sidebar izquierdo **sustituye** la barra superior. Un solo panel izquierdo en toda la aplicación, colapsable a 48px. |
| 2 | **Sin cuentas ni login.** "Mis proyectos" = los proyectos guardados en esta máquina. |
| 3 | De Canva se adopta **la estructura, no la identidad visual.** Se mantiene el sistema en escala de grises (decisión 3 de la Shell, intacta). |

---

## 1. Problema que resuelve

Al abrir ArchMuse hoy aparece un formulario de subida de DXF. No hay noción de "dónde estoy" ni de "qué he hecho antes": la aplicación empieza siempre desde cero, en la misma pantalla, sin memoria y sin destino al que volver. La navegación existente es una barra superior de cinco elementos de la que **dos no hacen absolutamente nada** — `Herramientas` y `Cuenta` están marcados `disabled` en `static/index.html:1087` y `:1092` y no tienen entrada en `SHELL_MENUS`, así que ni siquiera abren un desplegable vacío: son etiquetas muertas. Un tercero, `Exportar`, está deshabilitado hasta que hay proyecto abierto. La barra que debía organizar la aplicación está medio vacía, y contradice de hecho la regla que la propia especificación se puso ("ningún menú sin función real").

El resultado es que ArchMuse se comporta como un formulario web de un solo uso y no como una aplicación con la que se trabaja varios días. Los productos que Pablo cita como referencia — ChatGPT, Copilot, Claude, Canva — comparten una decisión estructural que ArchMuse no ha tomado: **hay un lugar permanente a la izquierda que dice qué es la aplicación y qué hay dentro, y un Inicio que muestra tu trabajo en vez de un formulario en blanco.**

Esto enlaza con `NORTH_STAR_2031.md` (el producto que se abre cada día) y es la mitad visible del problema que `2026-08-01-gestor-de-proyectos-y-persistencia.md` ataca por debajo. Sin esa mitad de abajo, esta no existe (§9, §14).

## 2. Usuario afectado

El arquitecto que ya usa ArchMuse en local, en su propia máquina. Es el mismo usuario del PRD de persistencia y por la misma razón: es quien vuelve al mismo plano varios días seguidos y quien hoy no tiene forma de volver a él.

Explícitamente **no** cubre al estudio con varias personas: sin cuentas (decisión 2), "mis proyectos" significa "los de esta máquina", no "los míos frente a los de mi socio".

## 3. Objetivo de negocio

1. **Convertir ArchMuse en un lugar y no en un trámite.** Un Inicio que muestra tu trabajo acumulado es la diferencia entre una herramienta que se abre cuando hay un archivo nuevo y una que se abre por costumbre.
2. **Hacer visible el activo que se está acumulando.** El histórico de proyectos analizados es, según `MOAT_ANALYSIS.md`, de lo poco que un competidor no puede copiar clonando funcionalidad. Si el usuario nunca lo ve, para él no existe.
3. **Dejar de pagar el coste de una navegación que no navega.** Dos menús muertos y una barra que solo se activa con proyecto abierto son deuda de interfaz: ocupan espacio, prometen función y no la dan.

## 4. Objetivo técnico

Una vez implementado debe ser cierto que:

- Existe **un único panel de navegación izquierdo** en toda la aplicación, presente tanto en Inicio como con un proyecto abierto, colapsable a 48px y con su estado (abierto/colapsado) recordado entre sesiones.
- **No queda ninguna barra superior de menús.** Cada función que hoy vive en ella tiene destino nuevo explícito o se elimina (§10).
- El Inicio es una **parrilla de proyectos guardados** con miniatura del plano, no un formulario.
- Abrir un proyecto **no recarga la página ni desmonta el sidebar**: cambia el contenido a la derecha y el estado contextual del sidebar.
- Ningún elemento de navegación existe sin función real: si algo no tiene comportamiento, no se dibuja.
- El sistema visual en escala de grises no cambia: **cero tokens de color nuevos en la interfaz** (decisión 3 de la Shell, que este PRD no toca).

## 5. Casos de uso

**CU-1 — Abrir la aplicación con trabajo previo.** El arquitecto abre ArchMuse y ve su Inicio: una parrilla con "Calle Mayor", "Ronda Sur" y "Residencial Norte", cada uno con miniatura del plano, fecha y puntuación. Pulsa uno y entra al workspace.

**CU-2 — Primera vez, sin nada guardado.** Abre ArchMuse por primera vez. El Inicio no muestra una parrilla vacía con un hueco triste: muestra los dos puntos de entrada reales — analizar un DXF o generar un proyecto con IA — como contenido principal, no como estado de error.

**CU-3 — Crear desde cualquier sitio.** Está dentro de un proyecto y quiere empezar otro. El botón `+ Nuevo` del sidebar está siempre visible; no tiene que cerrar lo que tiene abierto ni buscar un menú.

**CU-4 — Navegar dentro del proyecto abierto.** Con un proyecto abierto, el sidebar muestra las viviendas de ese proyecto. Cambia de VT1/3 a VT4/2 desde el mismo sitio desde el que antes cambió de proyecto: un solo panel izquierdo, dos contextos.

**CU-5 — Recuperar espacio para el plano.** Colapsa el sidebar a 48px. El lienzo gana 192px. Al volver mañana sigue colapsado.

**CU-6 — Volver al Inicio.** Pulsa el nombre "ArchMuse" o "Inicio" en el sidebar y vuelve a la parrilla. El proyecto no se pierde: sigue guardado y visible en la parrilla.

## 6. Casos límite

- **Cero proyectos guardados** (CU-2): el Inicio no es una parrilla vacía. Es la pantalla de creación. La parrilla aparece cuando hay algo que poner en ella.
- **Un solo proyecto:** una parrilla de una tarjeta se ve rota. Definir el mínimo a partir del cual la retícula se justifica, o alinear a la izquierda sin centrar.
- **Muchos proyectos (>30):** hoy improbable, pero la parrilla necesita orden por defecto (última modificación) antes de necesitar búsqueda. No se implementa búsqueda en esta iteración.
- **Proyecto sin miniatura** (plano no dibujable, o proyecto generado sin SVG): la tarjeta va sin miniatura, con el espacio ocupado por los metadatos. **No** un icono de relleno — misma regla que el PRD de persistencia §6.
- **Proyecto ilegible o de esquema antiguo:** aparece en la parrilla como "no se puede abrir", con opción de borrar. No desaparece silenciosamente ni rompe la carga del resto.
- **Sidebar colapsado + proyecto abierto:** a 48px no caben nombres de vivienda. Decidir: o el colapsado solo muestra iconos de sección y la lista de viviendas se oculta, o el colapso queda deshabilitado dentro de un proyecto. Recomiendo lo primero.
- **Pantalla estrecha (<900px):** dos paneles laterales más lienzo no caben. El sidebar debe colapsar automáticamente por debajo de un umbral, sin perder la preferencia manual del usuario.
- **Proyecto abierto que se borra desde la parrilla:** no debe poder borrarse el proyecto que se está mirando sin cerrarlo antes, o el borrado debe devolver al Inicio.

## 7. Flujo del usuario

1. Abre ArchMuse → **Inicio**: sidebar a la izquierda, parrilla de proyectos a la derecha.
2. Pulsa una tarjeta → entra al workspace. El sidebar permanece; su sección de contenido pasa de "Recientes" a las viviendas del proyecto. Aparece un encabezado de proyecto sobre el lienzo con el nombre y las acciones contextuales (Exportar).
3. Trabaja: cambia de vivienda desde el sidebar, de modo desde la barra inferior del plano, consulta el inspector a la derecha.
4. Colapsa el sidebar si necesita más lienzo.
5. Pulsa `ArchMuse` / `Inicio` → vuelve a la parrilla, con el proyecto guardado.
6. Pulsa `+ Nuevo` en cualquier momento → analizar DXF o generar proyecto.

**Estructura del sidebar (240px):**

```
┌──────────────────────┐
│ ArchMuse          ⟨⟩ │  marca + colapsar
├──────────────────────┤
│ + Nuevo              │  acción primaria
│                      │
│ ⌂ Inicio             │  navegación
├──────────────────────┤
│ RECIENTES            │  contexto: sin proyecto
│   Calle Mayor        │
│   Ronda Sur          │
│   Residencial Norte  │
│                      │
│  — o, con proyecto — │
│                      │
│ VIVIENDAS            │  contexto: proyecto abierto
│   VT1/3          ●   │
│   VT2/2              │
│   VT4/2          ●   │
├──────────────────────┤
│ ⚙ Ajustes            │  al fondo
└──────────────────────┘
```

## 8. Criterios de aceptación

1. No existe ningún elemento `.shell-trigger` ni barra superior de menús en el DOM renderizado.
2. El sidebar está presente en Inicio y en workspace, y **no se desmonta ni se vuelve a montar** al navegar entre ambos.
3. El estado colapsado/expandido persiste entre recargas.
4. Colapsado ocupa 48px; expandido 240px; el lienzo absorbe la diferencia sin desbordamiento horizontal.
5. Con proyectos guardados, el Inicio muestra una tarjeta por proyecto con miniatura, nombre, fecha de última modificación, puntuación global y número de viviendas.
6. Sin proyectos guardados, el Inicio muestra los puntos de entrada de creación como contenido principal, no un estado vacío decorativo.
7. Abrir un proyecto desde la parrilla llega al mismo workspace que hoy produce `/api/analizar`, sin diferencias funcionales.
8. Con proyecto abierto, el sidebar lista sus viviendas y seleccionar una equivale exactamente a la selección actual del `panel-left`.
9. `Exportar` (PDF y CSV) sigue accesible con proyecto abierto y sigue produciendo los mismos archivos.
10. `Herramientas` y `Cuenta` no aparecen en ninguna parte (§10).
11. El diff de CSS **no introduce ningún token de color nuevo**: la interfaz sigue en la escala de grises actual.
12. Por debajo de 900px de ancho el sidebar se colapsa automáticamente sin perder la preferencia manual.

## 9. Riesgos

- **Riesgo número uno: este PRD depende por completo de uno que no está aprobado.** El Inicio muestra proyectos guardados; hoy no se guarda nada (`app.py` usa un `TemporaryDirectory` que se destruye al terminar la petición). Sin `2026-08-01-gestor-de-proyectos-y-persistencia.md` implementado —al menos sus tareas 2 a 10— este PRD produce **una parrilla que siempre está vacía**. No es un riesgo de calendario: es la diferencia entre construir la capacidad y construir su decorado. Ver §11 y §14.
- **Dos documentos de diseño en contradicción.** La especificación de Shell v2 se define a sí misma como "el plano de implementación" y su decisión 1 es la barra superior. Este PRD la deroga. Mientras la v3 no exista, cualquier sesión futura que lea `especificacion-shell.md` implementará lo contrario de esto.
- **`static/index.html` tiene 5.779 líneas.** Es el archivo que ya concentra tres iteraciones de rediseño, y este PRD le añade un paradigma de navegación completo más una segunda pantalla de primer nivel. El PRD de persistencia ya señalaba que era "buen momento para evaluar si sigue siendo un solo archivo"; con este encima, deja de ser una evaluación y pasa a ser una condición para poder trabajar.
- **La referencia está ligeramente mal recordada, y eso importa.** El sidebar de ChatGPT y Claude es un **historial de conversaciones**: cientos de elementos efímeros y baratos, donde una lista larga es la respuesta correcta. El de Canva **no es una lista de diseños**, son secciones (Plantillas, Proyectos, Marca). Un arquitecto tendrá entre 3 y 30 proyectos, duraderos y caros. Aplicar el patrón de historial a ese volumen da un sidebar casi vacío. Mitigación adoptada en §7: el sidebar lleva **secciones + un máximo de recientes**, y la lista completa vive en la parrilla del Inicio — que es, de hecho, la estructura de Canva y no la de ChatGPT, coherente con la decisión 3 de Pablo.
- **Duplicación de la lista de proyectos.** Si el sidebar lista todos los proyectos y la parrilla también, hay dos sitios para la misma acción y ninguno es el canónico. Resuelto arriba, pero es el error fácil de cometer durante la implementación.
- **Sin tests de regresión de interfaz más allá del humo actual.** El PRD de persistencia ya condiciona su tarea 1 a un golden master; aquí el equivalente es que el smoke test jsdom cubra la navegación nueva antes de borrar la barra superior, no después.

## 10. Impacto sobre módulos existentes

**`static/index.html`** — todo el impacto se concentra aquí. Desglose por partes:

- **Barra superior (`:1084`–`:1092`, CSS `:177`–`:205`):** se elimina. Con ella, `SHELL_MENUS`, `SHELL_ACTIONS`, `openShellMenu`, `buildShellDropdown`, `wireShellMenu` y la maquinaria de flyout con hover-intent corregida hoy (2026-08-02). **Buena noticia: es código que se borra, no que se migra.**
- **`shell-breadcrumb` / `updateShellProject`:** el nombre del proyecto se muda al encabezado sobre el lienzo. La función sobrevive con otro destino.
- **`panel-left` (lista plana de viviendas, `:1944`–`:1946`):** se funde con el sidebar. Aquí hay una ventaja real que conviene registrar: **el "Explorador" con árbol adaptativo de la especificación de Shell §6.1 nunca llegó a implementarse** — lo que existe es una lista plana. No hay árbol que rehacer ni trabajo que tirar; el coste de fusionar es mucho menor de lo que la especificación sugiere.
- **`renderUpload` / `renderGenerarForm`:** dejan de ser la pantalla de arranque y pasan a ser destinos de `+ Nuevo`. Su contenido no cambia.
- **`cerrarProyecto`:** cambia de significado. Hoy "cerrar" es "volver al formulario de subida"; pasa a ser "volver al Inicio", que ya no destruye el proyecto porque el proyecto persiste.
- **`descargarPdf` / `exportarCSV`:** intactas. Solo cambia desde dónde se invocan.
- **`Herramientas` y `Cuenta`:** **se eliminan, no se migran.** Están deshabilitados y sin implementación desde que existen. Portar una etiqueta muerta a un sidebar nuevo es trasladar deuda y volver a incumplir "ningún menú sin función real". Cuando haya Ajustes de verdad, entran por la puerta de abajo del sidebar (§7).

**`app.py`** — sin cambios propios de este PRD. Consume `GET /api/proyectos` y `GET /api/proyectos/<id>`, que son entregables del PRD de persistencia, no de este.

**`analyzer/`** — sin cambios. Ningún módulo de análisis se entera de este PRD.

**`docs/design/2026-08-01-especificacion-shell.md`** — debe pasar a v3: §1 decisión 1, §2.1, §2.2, §5 y §6 quedan derogados o reescritos. **Es una tarea del plan, no una nota al pie** (§11.1).

**`docs/prd/2026-08-01-gestor-de-proyectos-y-persistencia.md`** — su tarea 11 se elimina de aquel plan y se sustituye por una referencia a este PRD.

## 11. Plan de implementación dividido en pequeñas tareas

**Precondición dura:** las tareas 2–10 del PRD de persistencia deben estar terminadas antes de la tarea 6 de esta lista. Las tareas 1–5 de aquí no dependen de persistencia y pueden hacerse antes o en paralelo.

1. **Actualizar `especificacion-shell.md` a v3.** Primero el documento, luego el código: si se implementa antes de corregirlo, queda un repositorio que se contradice a sí mismo. ≤1h.
2. **Crear la red de seguridad mínima.** *(Corrección 2026-08-02: aquí decía "extender el smoke test jsdom". **No existe ningún smoke test** — no hay `package.json` ni runner de JS en el repositorio. El error venía del §12 del PRD de persistencia y lo arrastré sin comprobarlo.)* Lo que sí hay desde hoy es `tests/fixtures/ejemplo-dxf-analisis.json`, la respuesta real de `/api/analizar` sobre `ejemplo.dxf`. Sirve como golden master interceptando `window.fetch`: monta el workspace completo sin resubir 20 MB ni pagar otra llamada a la IA.
3. **Componente sidebar, estático:** marca, `+ Nuevo`, `Inicio`, `Ajustes`, sin contexto de proyecto. Convive temporalmente con la barra superior.
4. **Colapso:** 240px ↔ 48px, persistencia de la preferencia, colapso automático bajo 900px.
5. **Eliminar la barra superior** y reubicar sus funciones: `+ Nuevo` absorbe el menú Proyecto, el encabezado del lienzo absorbe nombre y `Exportar`, `Herramientas` y `Cuenta` se borran.
6. **Fusionar `panel-left` en el sidebar:** con proyecto abierto, la sección de contenido lista viviendas con su marcador de severidad.
7. **Pantalla Inicio — estado sin proyectos:** los dos puntos de entrada como contenido principal.
8. **Pantalla Inicio — parrilla:** tarjetas desde `GET /api/proyectos`, orden por última modificación.
9. **Miniatura en la tarjeta:** consumir la que genera la tarea 9 del PRD de persistencia. Sin miniatura, tarjeta sin hueco de relleno.
10. **Recientes en el sidebar:** máximo 5, ordenados por última modificación.
11. **Borrado desde la tarjeta**, con confirmación y con la protección de §6 sobre el proyecto abierto.
12. **Repaso de accesibilidad y teclado:** foco visible, orden de tabulación, Escape, y navegación del sidebar sin ratón.

Las tareas 1–5 son un entregable completo por sí solas (navegación nueva, sin Inicio). Las 7–11 son la mitad que exige persistencia.

## 12. Plan de pruebas

- **Golden master por fixture** (tarea 2): montar el workspace desde `tests/fixtures/ejemplo-dxf-analisis.json` y comprobar 6 viviendas en el riel, SVG pintado, inspector con contenido y Exportar activo. Debe pasar antes y después de borrar la barra superior — es la prueba de que la eliminación no perdió funciones. Verificado ya el 2026-08-02 tras dividir `index.html`.
- **Persistencia del colapso:** colapsar, recargar, sigue colapsado.
- **Continuidad del sidebar:** comprobar que el nodo del sidebar es el **mismo elemento** antes y después de abrir un proyecto (criterio 8.2), no uno nuevo con el mismo aspecto.
- **Estado vacío frente a estado con datos:** ambos Inicios renderizan sin error; el vacío no dibuja retícula.
- **Sin regresión de color:** comprobación automática de que el diff de CSS no añade tokens de color (criterio 8.11).
- **Reflujo responsive:** 1440px, 1100px, 899px y 700px sin desbordamiento horizontal.
- **Paridad de exportación:** el PDF y el CSV generados tras el cambio son idénticos a los de antes.
- **Proyecto ilegible en la parrilla:** un registro corrupto no impide cargar el resto.

## 13. Métricas para medir el éxito

- **Proporción de sesiones que empiezan abriendo un proyecto existente** frente a las que empiezan subiendo un DXF. Es la métrica que dice si el Inicio cumple su función; si se queda cerca de cero, el Inicio es un paso intermedio de más.
- **Proyectos abiertos por sesión.** Si sube por encima de 1, el sidebar está sirviendo para navegar entre proyectos, que es su justificación.
- **Uso del colapso.** Si casi nadie lo usa, 240px permanentes están bien invertidos; si casi todos colapsan, el sidebar estorba y hay que replantear su ancho por defecto.
- **Clics hasta abrir un proyecto conocido.** Hoy es infinito (imposible). Objetivo: 1.
- **Contra-métrica: tiempo hasta el primer análisis en un usuario nuevo.** Si el Inicio añade un paso a quien solo quiere analizar un DXF, esta métrica empeora y hay que revisar CU-2.

## 14. Posibles motivos para NO implementar la idea

**El motivo más serio sigue siendo el orden, y es el mismo que ya señalé en el PRD de persistencia.** Este documento describe un Inicio lleno de proyectos guardados. Hoy no se guarda ni uno. Si se implementa este PRD antes que la persistencia, el resultado es una parrilla permanentemente vacía y un sidebar con una sección "Recientes" que nunca tiene nada: exactamente el "decorado sobre nada" contra el que ya advertí. Y la persistencia, a su vez, tiene su propia precondición sin resolver — el golden master y el bug de tipología/zona climática de `TECH_REVIEW.md`. **Hay tres cosas en fila y esta es la tercera.** Recomiendo aprobarla, pero no empezarla por las tareas 6–11.

**Sobre partes concretas de lo pedido, mi recomendación difiere:**

- **El sidebar no debe listar todos los proyectos**, aunque las referencias citadas lo sugieran. ChatGPT y Claude listan historial: cientos de elementos efímeros. Un arquitecto tendrá entre 3 y 30 proyectos duraderos. Un sidebar de 240px con cuatro entradas y mucho vacío parece un producto sin usar. **Alternativa adoptada en §7: secciones + máximo 5 recientes; la lista completa vive en la parrilla.** Que es, además, cómo funciona Canva de verdad — y Canva es la referencia que Pablo eligió.
- **`Herramientas` y `Cuenta` no se migran: se borran.** Llevan deshabilitados desde que se escribieron. Copiarlos al sidebar sería empezar el rediseño incumpliendo la misma regla que motivó el rediseño anterior.
- **No añadir búsqueda de proyectos en esta iteración.** Con menos de 30 elementos ordenados por fecha, un buscador es trabajo que resuelve un problema que aún no existe. Entra cuando la métrica de §13 muestre que la parrilla se navega con esfuerzo.
- **Dividir `static/index.html` debería ir antes que la tarea 5, no después.** No lo he metido como tarea porque es una decisión de arquitectura de código con entidad propia y afecta a más cosas que este PRD, pero añadir un paradigma de navegación completo a un archivo de 5.779 líneas es la clase de decisión que se paga durante el resto de la vida del proyecto. **Si vas a aprobar solo una cosa de este documento antes que el resto, que sea esta.**
- **"Que se parezca a Canva" tiene un límite que conviene dejar escrito ahora:** Canva es un producto de consumo cuyo Inicio vende plantillas. ArchMuse es una herramienta de diagnóstico técnico cuyo Inicio muestra trabajo propio. La estructura se puede tomar prestada; la intención comercial de esa estructura, no. Si en algún momento el Inicio empieza a proponer plantillas o ejemplos por delante de los proyectos del usuario, nos habremos pasado de la referencia.

---

**Decisión:** _pendiente de revisión por Pablo_
