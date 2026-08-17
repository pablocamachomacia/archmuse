# Arquitectura de producto — ArchMuse

**Estado:** Propuesta · **Fecha:** 2026-08-01 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

No implementado. Este documento define la arquitectura completa antes de tocar ninguna pantalla, como se ha pedido.

---

## 1. Diagnóstico: qué falla hoy

`static/index.html` tiene un único contenedor, `#view-root`, en el que se reconstruye por completo el DOM cada vez que cambia de "pantalla": `renderUpload` (subir DXF), `renderGenerarForm` (generar proyecto), `renderLoading` (transición) y `renderWorkspace` (plano + inspector). Todo vive al mismo nivel — no hay jerarquía entre ellas.

Eso produce un síntoma concreto en el `<header>` (`static/index.html:1147-1178`): en la misma barra conviven, sin distinción, **acciones de aplicación** (Generar proyecto, Nuevo proyecto), **acciones de proyecto** (Descargar PDF, CSV) y **contenido de análisis** (el badge de puntuación con su popover de desglose). Las tres cosas se muestran u ocultan a mano, vista a vista (`btnNuevo.hidden = ...` se repite en `renderUpload` y `renderGenerarForm`), porque no existe una barra de aplicación real que sepa por sí sola qué mostrar según el nivel en el que está el usuario.

El resultado es el mismo problema que señalabas en el rediseño de la pantalla de resultados, pero un nivel por encima: **la aplicación entera resuelve "elegir cómo empezar", "meter datos de un proyecto nuevo" y "diagnosticar un proyecto abierto" en la misma superficie**, sin fronteras. Revit no mezcla la pantalla de inicio con el documento abierto; Figma no mezcla el listado de archivos con el lienzo. ArchMuse hoy sí.

La arquitectura que sigue introduce esa frontera.

## 2. El principio: tres niveles, no una lista de pantallas

En vez de pensar en "pantallas" sueltas, ArchMuse tiene tres niveles, cada uno con una pregunta que responde y ninguna otra:

| Nivel | Pregunta que responde | Sabe que existe un proyecto abierto |
|---|---|---|
| **Shell** (barra de aplicación) | ¿Dónde estoy y qué puedo hacer desde cualquier sitio? | Sí, pero no lo muestra en detalle — solo su nombre |
| **Aplicación** | ¿Con qué proyecto quiero trabajar? | No — no hay proyecto todavía |
| **Proyecto** | ¿Qué dice el diagnóstico de este proyecto? | Sí — todo aquí asume un proyecto cargado |

Ninguna vista de "Aplicación" debe saber dibujar un plano. Ninguna vista de "Proyecto" debe saber cómo se crea un proyecto nuevo. Esa es la regla que hoy se rompe.

## 3. Mapa de vistas

### 3.1 Shell — barra de aplicación persistente

No es una vista: es el marco que envuelve a todas. No se reconstruye al navegar.

**Contiene:**
- Wordmark `Archmuse` (izquierda) — pulsarlo cierra el proyecto activo y vuelve a Inicio. Si ya está en Inicio, no hace nada.
- Menú **Proyecto**: Nuevo (submenú: Analizar plano / Generar proyecto) · Abrir… (→ Mis proyectos) · Cerrar proyecto.
- Menú **Exportar**: Informe PDF · CSV. Deshabilitado sin proyecto abierto.
- Menú **Ventana**: Tema claro/oscuro. Aquí es donde se traslada el interruptor que hoy vive en el header como icono de sol/luna (línea 1177) — deja de ser un botón con emoji suelto y pasa a ser una entrada de menú con estado, que es donde vive ese tipo de preferencia en Figma o VS Code.
- Nombre del proyecto activo (centro-derecha), como breadcrumb de solo lectura — sustituye al badge de puntuación que hoy vive en el header. **La puntuación dejó de ser contenido de la aplicación**: es contenido del proyecto, y ya tiene su sitio en el informe ejecutivo del modo Resumen. Duplicarla en la barra de app es la misma clase de ruido que ya eliminamos del panel derecho en la iteración 3.
- Icono de **Ajustes** (extremo derecho) → abre Configuración.

**Deliberadamente NO contiene:**
- Menú **Herramientas** — lo pedías en el punto 3, pero ya existe: es la barra de modos del Workspace (Resumen · Espacio · Luz · Normativa · Problemas · Diagnóstico · 3D). Ponerlo también arriba, como menú, sería la misma herramienta accesible por dos caminos distintos — Figma no duplica su barra de herramientas en el menú superior, y nosotros tampoco deberíamos.
- Menú **Ayuda** — no hay hoy contenido real que poner detrás (ni documentación, ni changelog, ni soporte). Un menú que abre a nada es exactamente el tipo de elemento "que parece app" que se pidió eliminar. Se añade el día que haya algo real detrás.
- Menú/avatar de **Usuario** con perfil, licencia y cerrar sesión — como te dije en la respuesta anterior, esto es una aplicación Flask local de un solo usuario; no hay contra qué autenticar. Queda como **Ajustes**, sin identidad de usuario, hasta que exista despliegue multiusuario real.

### 3.2 Nivel Aplicación

No hay proyecto abierto. Estas vistas no dibujan planos ni inspectores.

**Inicio**
- *Responsabilidad única:* ofrecer el punto de partida de mayor valor según el estado del usuario — no una elección previa a él.
- *Contenido, corregido tras auditar el flujo minuto a minuto* (ver `2026-08-01-flujo-de-usuario.md`): **no es una pantalla de elección con dos tarjetas.** Sin proyectos guardados (el caso de hoy, siempre, sin persistencia), `#/` muestra directamente el formulario de Analizar plano — dropzone al centro — con "Generar proyecto" como enlace secundario debajo, no como acción de igual peso. Con proyectos guardados (tras el PRD de persistencia), se invierte: la franja "Recientes" pasa a primer plano y Analizar queda como acción secundaria — porque para un usuario que vuelve, abrir un proyecto ya analizado vale más que repetir la subida. Insertar una pantalla de elección entre abrir la aplicación y la acción real costaba un clic sin dar nada a cambio en el caso dominante.
- *Entra desde:* abrir la aplicación, o "Cerrar proyecto" desde el Shell.
- *Sale hacia:* Analizar plano (implícito, mismo contenido de `#/` en el caso vacío), Generar proyecto, o Mis proyectos.
- *Bloqueado por PRD:* solo la franja de recientes y la inversión de prioridad necesitan persistencia. El caso vacío es construible ya, fusionado con Analizar plano — ya no son dos vistas.

**Mis proyectos**
- *Responsabilidad única:* encontrar y abrir un proyecto ya analizado.
- *Contenido:* rejilla de tarjetas — nombre, fecha, miniatura del plano, puntuación, nº de viviendas. Sin edición aquí, sin analizar nada nuevo (eso es "Analizar plano"). Acción secundaria por tarjeta: eliminar.
- *Entra desde:* Inicio ("Ver todos"), Shell (Proyecto → Abrir…).
- *Sale hacia:* Workspace (al abrir una tarjeta — **sin llamar a la IA**, servido desde caché).
- *Bloqueado por PRD:* por completo. Esta vista no existe hasta que exista almacenamiento. La incluyo en la arquitectura porque la pediste explícitamente y porque el hueco debe estar reservado desde ahora, pero no se implementa en la fase de rediseño visual.

**Analizar plano** (hoy `renderUpload`)
- *Responsabilidad única:* recibir un DXF y los tres parámetros mínimos (norte, ciudad, tipología) para analizarlo.
- *Sale hacia:* Cargando → Workspace.

**Generar proyecto** (hoy `renderGenerarForm`)
- *Responsabilidad única:* recibir los parámetros de un proyecto paramétrico (solar, edificio, mix de viviendas, normativa).
- *Sale hacia:* Cargando → Workspace.
- Se mantienen como dos vistas separadas, no pestañas de una — analizar y generar parten de datos de naturaleza distinta (un archivo existente vs. un formulario de intención) y mezclarlas en una vista con pestañas volvería a juntar dos responsabilidades donde hoy hay una frontera limpia.

**Cargando** (hoy `renderLoading`)
- *Responsabilidad única:* mostrar progreso mientras el backend analiza o genera. No es navegable — no hay nada que hacer aquí salvo esperar (o cancelar, si se añade).
- Es un estado transitorio del Shell, no una vista con entidad propia en el mapa de navegación.

### 3.3 Nivel Proyecto

Hay un proyecto cargado. Todo aquí asume sus datos.

**Workspace** (hoy `renderWorkspace`, ya rediseñado en las iteraciones 1-3)
- *Responsabilidad única:* diagnosticar el proyecto abierto — el plano como protagonista, el árbol de viviendas a la izquierda, los modos de análisis abajo, el inspector contextual a la derecha.
- No dibuja nada de nivel Aplicación. Si hoy el botón "Generar proyecto" aparece dentro del header mientras estás en el Workspace (línea 1166), es exactamente la fuga de responsabilidad que esta arquitectura corrige: esa acción vive en el Shell (Proyecto → Nuevo) o en Inicio, nunca dentro de la vista de un proyecto ya abierto.
- *Sale hacia:* Inicio (Shell → Cerrar proyecto), Configuración (overlay), diálogo de Exportar (overlay).

**Exportar** — sea diálogo, no vista
- Se pedía como posible vista principal. Mi recomendación es que **no** lo sea: hoy son dos formatos (PDF, CSV) y ninguna gestión de exportaciones pasadas (no hay historial, no hay persistencia de archivos exportados). Elevarlo a vista de primer nivel crearía una pantalla con una sola decisión ("¿PDF o CSV?") y nada más — el mismo tipo de sobre-construcción que se pidió evitar en el panel derecho. Se modela como un panel superpuesto anclado al menú Exportar del Shell, con las dos opciones y nada más. Si en el futuro hay más formatos o un historial de exportaciones, se reconsidera como vista.

## 4. Configuración — ¿vista o superposición?

Se pedía como vista principal. La trato como una **capa modal sobre lo que hubiera debajo** (como el diálogo de Ajustes de Figma o el de Opciones de Revit), no como un destino con historial de navegación propio — porque no es un lugar donde se trabaja, es un lugar donde se ajustan tres cosas y se vuelve exactamente a donde estabas.

**Contenido, con lo que puede construirse hoy marcado:**

- **Apariencia** — tema claro/oscuro. *Construible ya* (es el mismo interruptor que hoy vive suelto en el header).
- **Estado del proveedor de IA**:
  - Proveedor y modelo activo (`Claude Sonnet`) — *construible ya*, es la constante `MODEL` de `analyzer/ai_analyst.py:30`.
  - Última llamada, tiempo medio, % de API restante, coste acumulado — **no construible.** Como te decía antes, nada de esto se mide hoy: `ai_analyst.py` descarta el objeto `usage` de cada respuesta, no hay registro de llamadas, y el "% de API restante" no es un dato que la API de Anthropic exponga. Esta sección se queda como placeholder ("Aún sin datos de uso") hasta que exista el PRD de instrumentación.
- **Acerca de** — versión, nada más. No hay licencia que mostrar todavía.

## 5. Grafo de navegación

```
                         ┌─────────────────────────┐
                         │  Shell (persistente)     │
                         │  Archmuse · Proyecto ·   │
                         │  Exportar · Ventana ·    │
                         │  [nombre proyecto] ·     │
                         │  Ajustes                 │
                         └────────────┬─────────────┘
                                      │ envuelve a todo lo de abajo

  NIVEL APLICACIÓN                                    NIVEL PROYECTO
  ┌───────────┐                                      ┌──────────────┐
  │  Inicio   │──── Ver todos ───▶ Mis proyectos      │  Workspace    │
  │           │◀────────────────────────┐  │ abrir    │  (plano +     │
  │           │                          │  └─────────▶│  inspector +  │
  │           │──Analizar plano─▶┌──────────┐          │  modos)       │
  │           │                  │ Analizar │──┐       │               │
  │           │                  └──────────┘  │       │  Cerrar       │
  │           │──Generar proyecto─▶┌──────────┐ │ Cargando│ proyecto  │
  │           │                    │ Generar  │─┤         │  (Shell)  │
  │           │                    └──────────┘ │         └─────┬─────┘
  └───────────┘                                 └───────────────┘  │
        ▲                                                          │
        └──────────────────── Cerrar proyecto (Shell) ─────────────┘

  Superposiciones (no cambian de vista, se apilan encima):
  Configuración (desde Ajustes, cualquier vista) · Exportar (desde Shell, solo en Proyecto)
```

## 6. Qué se puede construir ya vs. qué espera al PRD de persistencia

| Vista | Construible en esta fase (visual) | Depende del PRD de persistencia |
|---|---|---|
| Shell | Sí | El nombre de proyecto activo y "Cerrar proyecto" funcionan ya (estado en memoria) |
| Inicio | Sí, sin franja de recientes | Franja "Recientes" |
| Mis proyectos | No | Vista completa |
| Analizar plano | Sí (ya existe, se rediseña) | — |
| Generar proyecto | Sí (ya existe, se rediseña) | — |
| Workspace | Sí (ya en iteración 3) | Restaurar vivienda/modo/encuadre al reabrir |
| Configuración → Apariencia | Sí | — |
| Configuración → Estado IA (modelo) | Sí | — |
| Configuración → Estado IA (uso/coste) | No | Requiere además el PRD de instrumentación de IA |
| Exportar | Sí (ya existe como botones, se convierte en panel) | — |

Es decir: la fase de rediseño visual puede construir el Shell completo, Inicio sin recientes, ambas vistas de creación, el Workspace y Configuración salvo el uso de IA — **sin esperar a ningún PRD**. Solo "Mis proyectos" y la restauración de sesión quedan bloqueadas.

## 7. Decisiones que necesito que confirmes

1. **Configuración y Exportar como superposiciones, no vistas** (sección 4 y 3.3) — es mi recomendación, contraria a listarlas como "vistas principales" en tu petición original. ¿De acuerdo, o las quieres como vistas de pleno derecho con su propia navegación?
2. **Sin menú Herramientas ni Ayuda en el Shell** (sección 3.1) — Herramientas porque duplicaría la barra de modos del Workspace; Ayuda porque no hay contenido real todavía. ¿De acuerdo?
3. **Enrutado por hash** (`#/`, `#/proyectos`, `#/proyecto/<id>`) — hoy no existe ninguna URL interna, todo vive en `state` de memoria. Añadirlo ahora permitiría que recargar la página o pulsar "atrás" del navegador no rompiera la aplicación, y prepara el terreno para cuando exista persistencia real. Es una decisión de alcance para esta fase: ¿lo incluyo en la Fase 0, o lo dejamos para cuando llegue el PRD de persistencia (que de todas formas necesitará tocar esto)?

## 8. Orden de implementación pantalla por pantalla (una vez aprobado)

1. Shell — barra de aplicación persistente, con sus menús y el traslado del tema desde el icono suelto.
2. Inicio/Analizar plano — una sola vista fusionada (§3.2 corregido), sin franja de recientes todavía.
3. Generar proyecto — mismo contenido de hoy, sobriedad visual, reposicionado como enlace secundario desde Inicio.
4. Workspace — ajustar para que deje de recibir botones de nivel Aplicación en su cabecera (ya no los necesita: los tiene el Shell).
5. Configuración — Apariencia y Estado IA (solo modelo), Acerca de.
6. Exportar como panel del Shell, sustituyendo a los botones sueltos de PDF/CSV.

"Mis proyectos" y la restauración de sesión entran cuando apruebes el PRD de persistencia — no antes.

---

**Decisión:** _pendiente de revisión por Pablo_
