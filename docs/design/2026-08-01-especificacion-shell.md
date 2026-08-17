# Especificación de la Shell — ArchMuse

**Estado:** v4 · Decisiones cerradas · **Fecha:** 2026-08-02 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

> ## v4 (2026-08-02): workspace tipo AutoCAD
>
> Añadida el mismo día que la v3, por decisión de Pablo recogida en
> `docs/prd/2026-08-02-workspace-tipo-autocad.md`. **No deroga la v3**: el Inicio y el
> sidebar se quedan exactamente como están ("el inicio lo dejamos así"). Lo que cambia
> es **el interior de un proyecto**, que pasa a tener la shell de AutoCAD:
>
> | Elemento | Qué es en ArchMuse |
> |---|---|
> | **Ribbon** | 3 pestañas: Vista (los 6 modos + encuadre), Análisis (capas + navegación por problemas), Salida (PDF/CSV). **No 7 como AutoCAD**: 5 estarían vacías, y una pestaña vacía es lo que se borró al eliminar Herramientas y Cuenta. Sustituye a `.plan-modebar`. |
> | **Línea de comandos** | Catálogo real con alias AutoCAD (`ZE`, `Z`, `LA`…). Los comandos de dibujo (`LINE`, `TRIM`…) responden explicando que ArchMuse analiza y no dibuja, nunca con un error genérico. `?` lista lo disponible. |
> | **Pestañas Modelo / 3D** | **No** Modelo/Presentación: no hay layouts ni trazado. Modelo y 3D sí son dos representaciones reales, y el visor 3D deja de ser un botón descolgado al final de los modos. |
> | **Barra de estado** | Coordenadas en metros reales del DXF + indicadores. |
> | **Navegación CAD** | Paneo (botón central **y** barra espaciadora + arrastre), zoom anclado al cursor, encuadre (`ZE`). Antes no había paneo en absoluto. |
> | **Capas** | De ArchMuse, no del DXF (el parser solo lee `"00 areas"`): Rellenos, Etiquetas, Norte. |
>
> **Jerarquía modo ↔ capas (era el riesgo nº1 del PRD):** el **modo manda** y fija el preset
> de capas; el panel de Análisis permite desviarse; **cambiar de modo restablece el preset**.
> La barra de estado señala solo las capas *desviadas* del preset — marcar toda capa apagada
> pondría "RELLENOS OFF" permanentemente en Resumen, que es su estado normal.
>
> **Coordenadas: el hallazgo que condicionó el diseño.** `plan_svg._compact_clusters` y
> `_grid_layout` **trasladan** habitaciones respecto al DXF para que una vivienda dispersa sea
> legible. Por eso el plano no permitía deducir coordenadas reales. Ahora el backend publica la
> transformación (`data-escala`, `data-ox`, `data-oy`, `data-minx`, `data-maxy` en el `<svg>`, y
> `data-dx`/`data-dy` por habitación) y el frontend la invierte. Dentro de una habitación las
> coordenadas son las del DXF; fuera, en un plano compactado, se marcan con `~` y la barra de
> estado muestra `COMPACTADO`. Protegido por `tests/test_plan_coords.py`.
>
> **Decisión 3 intacta:** ni un token de color nuevo. El plano queda en gris en reposo —
> incluidas las miniaturas del Inicio, neutralizadas por CSS para no tocar `plan_svg.py`, del que
> dependen también el informe de la CLI y el PDF.

---

Sustituye a la v2 de este mismo archivo. **La v2 quedó derogada el 2026-08-02** por las decisiones de Pablo recogidas en `docs/prd/2026-08-02-shell-lateral-e-inicio-de-proyectos.md`: la navegación deja de ser una barra superior de menús y pasa a ser **un único panel lateral izquierdo, colapsable**, presente en toda la aplicación.

> **Qué cambia respecto a la v2, en una línea:** desaparecen la barra superior y sus cinco menús (§5 reescrito); el Explorador deja de ser un panel propio y pasa a ser el contenido contextual del sidebar (§6 reescrito); el Nivel Aplicación deja de ser una tarjeta centrada de 480px y pasa a ser la parrilla de proyectos (§2.2 reescrito).
>
> **Qué NO cambia:** las decisiones 2, 3 y 4 siguen íntegras. En particular la **decisión 3 (escala de grises en la interfaz)** se mantiene sin matices: la referencia a Canva que motivó este cambio se adopta en estructura, nunca en identidad visual. El lienzo, los modos, el inspector y el informe ejecutivo no se tocan.

---

## 1. Decisiones cerradas

| # | Decisión |
|---|---|
| 1 | ~~Barra superior con cinco menús.~~ **Derogada en v3.** Navegación en un **sidebar izquierdo único** (240px, colapsable a 48px), persistente en Inicio y en Workspace. Sin barra superior. Ningún elemento de navegación sin función real. |
| 2 | Árbol **adaptativo al tipo de proyecto**. Sin placeholders vacíos. Plantas solo si existen de verdad. |
| 3 | Escala de grises en la **interfaz**; el **lienzo** usa color cuando el modo activo le da función (Espacios→uso, Problemas→severidad, Luz→orientación). |
| 4 | No se elimina funcionalidad. Se elimina ruido: decoración, duplicidades y elementos sin decisión asociada. |
| 5 | **(v3)** El Inicio es la **parrilla de proyectos guardados**, no un formulario. Estructura tomada de Canva; identidad visual, no. |

Se conservan íntegros: informe ejecutivo, modos del workspace, inspector, plano interactivo.

> **Corrección a `rediseno-total-propuesta.md` §4.1.** Allí dije que `--accent*` era "color de marca" a colapsar en gris. Al revisar los tokens: `--accent` ya vale `#1a1a1a` — es neutro desde antes. No hay que quitarle color, hay que **renombrarlo por su función** (`--selection`), que es lo que la regla 3 pide. Cambia el trabajo de implementación, no la conclusión.

## 2. Layout

### 2.1 Nivel Proyecto (Workspace)

```
┌──────────┬──────────────────────────────────────┬─────────────────┐
│          │  ejemplo.dxf                   VT1/3 │                 │
│ SIDEBAR  ├──────────────────────────────────────┤                 │
│          │  Vista │ Análisis │ Salida    ribbon │   INSPECTOR     │
│ 240px    │  [Resumen][Espacio][Luz]… [Encuadrar]│                 │
│ (48px    ├──────────────────────────────────────┤     320px       │
│ colap-   │                  ┼                   │                 │
│ sado)    │            LIENZO + crosshair        │                 │
│          │                                       │                 │
│          ├───────────────────────────────────────┴────────────────┤
│          │  Comando:                                        30px  │
│          ├────────────┬───────────────────────────────────────────┤
│          │ Modelo│ 3D │ -575.387, -295.204 m      COMPACTADO 28px │
└──────────┴────────────┴───────────────────────────────────────────┘
```

**No hay barra superior.** El nombre del proyecto vive en un **encabezado de proyecto** dentro de la columna del lienzo — no en una franja que cruce toda la ventana. Es la diferencia entre un dato del documento abierto y una barra de aplicación: lo primero pertenece al documento, y se va con él. **Exportar dejó de estar aquí en la v4**: está en la pestaña Salida del ribbon, que es donde un usuario de AutoCAD la busca.

El lienzo recibe todo el ancho restante: en 1440px son 880px ≈ **61%**, y con el sidebar colapsado 1072px ≈ **74%**. Con el Inspector además cerrado (§7.4), 1392px ≈ **97%**. La regla "el plano manda" se cumple permitiendo cerrar, no estrujando.

El sidebar sustituye al Explorador de la v2: mismo cometido (navegar dentro del proyecto), pero es el mismo elemento que ya estaba ahí antes de abrirlo — no aparece ni desaparece al cambiar de nivel. Ver §6.

### 2.2 Nivel Aplicación (Inicio)

```
┌──────────┬─────────────────────────────────────────────────────────┐
│          │  Proyectos                                              │
│ SIDEBAR  │                                                         │
│          │  ┌─────────┐  ┌─────────┐  ┌─────────┐                 │
│ 240px    │  │ ▣ plano │  │ ▣ plano │  │ ▣ plano │                 │
│          │  ├─────────┤  ├─────────┤  ├─────────┤                 │
│          │  │ Calle M.│  │ Ronda S.│  │ Norte   │                 │
│          │  │ 92 · 6 v│  │ 78 · 4 v│  │ 85 · 9 v│                 │
│          │  └─────────┘  └─────────┘  └─────────┘                 │
└──────────┴─────────────────────────────────────────────────────────┘
```

Sin Inspector y sin barra de modos — **ausentes del grid, no colapsados**. El sidebar sí permanece: es lo que hace que Inicio y Workspace se sientan la misma aplicación y no dos pantallas.

La parrilla es de ancho fluido con tarjetas de 240px mínimo y `auto-fill`, alineada a la izquierda — nunca centrada: una parrilla centrada con tres elementos se lee como un cuadro de diálogo, no como el contenido principal.

**Estado sin proyectos:** la parrilla no se dibuja. En su lugar, los dos puntos de entrada reales (Analizar plano / Generar proyecto) ocupan el área principal. No es un "estado vacío" con ilustración y texto de consuelo: es la pantalla de creación, que es lo único que un usuario nuevo puede hacer.

## 3. Tamaños

Tabla única. Todo lo que no esté aquí se deriva de la escala de espaciado (4/8/16/32).

| Elemento | Medida |
|---|---|
| Sidebar | 240px ancho · 48px colapsado |
| Encabezado de proyecto | 44px alto |
| ~~Barra de modos~~ | **Derogada en v4** — los modos son el grupo "Modos" del ribbon |
| Ribbon: tira de pestañas | 30px alto |
| Ribbon: panel | 56px alto mínimo |
| Línea de comandos | 30px alto |
| Barra de estado | 28px alto |
| Lectura de coordenadas | 160px mín., cifras tabulares (no debe bailar al mover el cursor) |
| Inspector / panel derecho | 320px ancho |
| Tarjeta de proyecto | 240px ancho mín., miniatura 4:3 |
| Fila de sidebar | 30px alto (32px la acción primaria) |
| Fila de árbol | 26px alto |
| Radio de esquina | 4px (todo). Nada mayor. |
| Borde | 1px, siempre `--border-subtle` |
| Umbral de colapso automático | 900px de ancho de ventana |

Una sola sombra en toda la aplicación: `0 4px 12px rgba(0,0,0,.12)`, exclusiva de capas flotantes (desplegables, modal). Superficies en reposo: sin sombra, nunca.

## 4. Jerarquía visual

Cuatro niveles de atención. Cada elemento pertenece a uno y solo uno — es la regla que evita que la interfaz vuelva a competir con el plano.

| Nivel | Qué contiene | Cómo se consigue |
|---|---|---|
| **1 — Lienzo** | El plano y su contenido | Es lo único con color de uso/severidad y lo único que ocupa área grande |
| **2 — Decisión** | La cifra del informe, el elemento seleccionado, el problema con foco | Peso 600 o color de selección. **Uno solo visible a la vez** |
| **3 — Estructura** | Árbol, modos, títulos de panel, triggers de menú | `--text-primary` a 13px, peso 400-500, sin fondo |
| **4 — Contexto** | Metadatos, unidades, contadores, timestamps | `--text-tertiary` a 12px. Nunca en negrita, nunca con fondo |

Prueba de la jerarquía: entornando los ojos ante la pantalla, deben distinguirse el plano y **como mucho un** elemento de nivel 2. Si se distinguen tres cosas, algo del nivel 3 está sobreactuando.

### 4.1 Tipografía

| Rol | Token | Uso |
|---|---|---|
| Cifra | 3.25rem / 600 | La puntuación del informe ejecutivo. **Solo ahí** |
| Título | `--text-lg` 16px / 500 | Encabezado de inspector, nombre del elemento seleccionado |
| Cuerpo | `--text-sm` 13px / 400 | Menús, árbol, informe, etiquetas — el 90% de la interfaz |
| Meta | `--text-xs` 11px / 400 | Nivel 4, siempre en `--text-tertiary` |

`--text-base` (14px) y `--text-xl` (20px) dejan de usarse en la Shell: cinco tamaños son dos jerarquías que nadie puede aprender.

### 4.2 Color

Fuera del lienzo, cuatro roles y ni uno más:

| Rol | Token | Superficie permitida |
|---|---|---|
| Error | `--color-critical` | Pin de severidad crítica, contador de críticos |
| Advertencia | `--color-warning` | Ídem, severidad no crítica |
| Correcto | `--color-success` | Confirmación de estado (vivienda sin problemas) |
| Selección | `--selection` (ex `--accent`) | El elemento con foco, uno a la vez |

**`--color-recommendation` (azul) desaparece de la interfaz.** Hoy pinta la tercera severidad ("RECOMENDACION"), que no es ni error ni advertencia ni corrección: es información. Pasa a `--text-tertiary` — sigue distinguiéndose de las otras dos severidades, pero deja de reclamar atención de nivel 2 para algo que por definición es opcional.

Dentro del lienzo, el color lo determina el modo activo (decisión 3): Espacios→uso, Problemas→severidad, Luz→orientación. En Resumen, Normativa y Diagnóstico el plano es papel neutro.

## 5. Sidebar

Sustituye por completo a los cinco menús de la v2. Un solo panel, tres zonas fijas y una zona contextual:

```
┌──────────────────────┐
│ ArchMuse          ⟨⟩ │  marca (→ Inicio) + colapsar
├──────────────────────┤
│ + Nuevo              │  acción primaria
│ ⌂ Inicio             │  navegación
├──────────────────────┤
│ RECIENTES            │  ZONA CONTEXTUAL
│   Calle Mayor        │  · sin proyecto: 5 recientes
│   Ronda Sur          │  · con proyecto: sus viviendas
├──────────────────────┤
│ ⚙ Ajustes            │  al fondo
└──────────────────────┘
```

**`+ Nuevo`** despliega los dos únicos orígenes de proyecto que existen: Analizar plano y Generar proyecto. Es el antiguo menú Proyecto reducido a lo que de verdad hacía.

**`Inicio`** sustituye a "Cerrar proyecto". Con persistencia, cerrar deja de destruir nada: se vuelve al Inicio y el proyecto sigue ahí. Un verbo destructivo para una acción que no destruye era el problema, no la etiqueta.

**Zona contextual** — ver §6.

**`Ajustes`** al fondo, separado. Hoy abre un panel con una sola sección real; crece añadiendo secciones, nunca overlays nuevos (misma regla que el modal de Cuenta de la v2, que era lo único aprovechable de aquel menú).

**Qué desaparece y por qué:**

| v2 | v3 |
|---|---|
| Menú **Herramientas** (`Inspector de capas DXF`) | **Se elimina de la Shell.** Nunca se implementó y estaba `disabled`. El problema real que lo justificaba (`AREA_LAYER = "00 areas"` fijo en `parser.py:19` ⇒ un DXF con otra capa devuelve cero habitaciones sin explicar por qué) **sigue siendo válido**, pero su sitio es el mensaje de error del análisis fallido, sobre el archivo concreto que falló — no un menú global que el usuario debe saber que existe. |
| Menú **Ventana** (tema claro/oscuro) | **Se elimina.** El producto tiene un único tema oscuro desde el rediseño visual industrial. Un selector de un solo valor no es una opción. |
| Menú **Cuenta** | **Se elimina.** Estaba `disabled` y sin implementación. Sin cuentas ni login (decisión de Pablo, 2026-08-02), lo único con contenido real es Ajustes, que ya tiene su sitio al fondo del sidebar. |
| **Exportar** como trigger de barra | Pasa al **encabezado de proyecto** (§2.1). Sigue abriendo el panel derecho (§7.3), no una lista. |

Comportamiento: sin animación de entrada; Escape cierra cualquier desplegable; el estado colapsado/expandido persiste entre sesiones y se fuerza a colapsado por debajo de 900px sin perder la preferencia manual del usuario.

## 6. Zona contextual del sidebar

Un solo panel izquierdo con dos contenidos según haya proyecto abierto o no. **Nunca los dos a la vez, nunca un segundo panel.**

**Sin proyecto (Inicio):** encabezado `RECIENTES` y hasta **5** proyectos por última modificación. El límite es deliberado: la lista completa vive en la parrilla del Inicio, que es su sitio. Duplicarla entera en el sidebar daría dos rutas para la misma acción y ninguna canónica.

**Con proyecto abierto:** el árbol de la vivienda, con las reglas de §6.1 intactas.

**Colapsado (48px):** la zona contextual se oculta por completo — a 48px no cabe ningún nombre, y un nombre truncado a tres letras no es navegación. Permanecen visibles solo la marca, `+ Nuevo`, `Inicio` y `Ajustes`, como iconos.

### 6.1 Árbol adaptativo

**DXF analizado** (siempre hoy):
```
▾ Proyecto
  ▾ Viviendas
      VT1/3
      VT2/2
```

**Proyecto generado** (cuando el dato de planta existe de verdad):
```
▾ Proyecto
  ▾ Planta 1
      Vivienda A
      Vivienda B
  ▾ Planta 2
      Vivienda A
```

La rama intermedia se decide en tiempo de render: si `_PLANTA_NAME_PATTERN` (`evaluator.py:2579`) resuelve para todas las viviendas, se agrupa por planta; si no resuelve para ninguna, se agrupa bajo "Viviendas". **Caso mixto** (unas resuelven y otras no): se agrupa bajo "Viviendas", sin inventar una planta "Sin asignar" — un nodo que solo aparece cuando los datos están sucios es exactamente el placeholder que la decisión 2 prohíbe.

### 6.2 Anatomía de fila

Alto 26px, indentación 16px por nivel, texto 13px. Triángulo de plegado `▸`/`▾` a 10px, solo en nodos con hijos (los nodos hoja no reservan ese espacio — no hay columna de triángulos fantasma). Sin iconos de tipo: el nivel del árbol ya dice qué es cada cosa.

Marcador de problemas: punto de 4px a la derecha de la fila, en `--color-critical` o `--color-warning` según la severidad máxima de esa vivienda. Sin número, sin badge — la cifra exacta ya está en el inspector, aquí solo hace falta saber dónde mirar.

## 7. Paneles

### 7.1 Contrato del slot derecho

Un panel activo a la vez: **Inspector** (reposo, sin botón de cierre — no hay a dónde cerrarlo) o **Exportar** (temporal, con `×` que devuelve al Inspector). Un panel futuro se añade a esta lista sin tocar el resto de la Shell.

### 7.2 Inspector

Sin cambios respecto a la iteración 3, ya implementada: informe ejecutivo (reposo) / detalle de problema / detalle de habitación.

### 7.3 Exportar

```
┌ Exportar                          × ┐
│                                      │
│  Formato                             │
│   ○ Informe PDF                      │
│   ○ Datos CSV                        │
│                                      │
│   [ opciones del formato ]           │
│                                      │
│      Generar y descargar             │
│                                      │
│  Exportado en esta sesión            │
│   13:42  informe.pdf                 │
└──────────────────────────────────────┘
```

Sin paso "Alcance" mientras solo exista una opción real (el backend solo exporta el proyecto completo: `pdf_report.py:47`, `index.html:2251`). La región de opciones de formato queda reservada, vacía hoy. El historial lee del registro de eventos de sesión (§8.3).

### 7.4 Colapso de paneles

`Ctrl+1` alterna el sidebar, `Ctrl+2` el panel derecho. Es lo que hace verdadera la regla "el plano manda" sin sacrificar los paneles: con ambos cerrados el lienzo ocupa casi todo el ancho. **Diferencia con la v2:** el sidebar no se cierra del todo, colapsa a 48px — sigue siendo el sitio al que volver al Inicio, y una aplicación sin ninguna afordancia de navegación visible es una aplicación en la que el usuario se queda atrapado. El panel derecho sí se cierra por completo.

El estado de colapso persiste entre sesiones (a diferencia de la v2, donde no se guardaba) y no va en la URL (§9.2).

## 8. Estados

### 8.1 Estados de componente

| Componente | Reposo | Hover | Activo / seleccionado | Deshabilitado |
|---|---|---|---|---|
| Fila de sidebar | `--text-secondary`, sin fondo | `--text-primary`, fondo `--overlay-subtle` | `--text-primary`, fondo `--overlay-hover` | `--text-tertiary`, sin hover, `cursor:default` |
| Tarjeta de proyecto | borde `--border-subtle` | borde `--border-strong` | — | — |
| Fila de menú | `--text-primary` | fondo `--overlay-subtle` | — | `--text-tertiary`, sin hover |
| Fila de árbol | `--text-primary` | fondo `--overlay-subtle` | fondo `--selection` al 10%, barra de 2px a la izquierda | — |
| Botón de modo | `--text-secondary` | `--text-primary` | `--text-primary` + subrayado de 2px | — |
| Punto del informe | `--text-primary` | fondo `--overlay-subtle` | fondo `--overlay-hover` + pin emparejado realzado | — |

Foco de teclado: contorno de 2px en `--selection`, con `:focus-visible` (nunca en click de ratón). Es el único uso de contorno en toda la aplicación.

### 8.2 Estados vacíos

- **Inicio sin proyectos**: no se muestra una sección "Recientes" vacía ni una parrilla vacía — ninguna de las dos existe hasta que pueda tener contenido. El área principal la ocupan los dos puntos de entrada de creación (§2.2).
- **Vivienda sin problemas**: el informe ejecutivo lo dice en positivo, sin lista vacía. Ya resuelto en iteración 3.
- **Logs, sesión recién abierta**: "Sin eventos en esta sesión." Sin tabla con cabeceras huérfanas.
- **Estado IA sin `ANTHROPIC_API_KEY`**: "Sin clave de API configurada" — no mostrar el modelo como si estuviera activo. Hoy `analyze_with_ai` ya devuelve `None` en silencio (`ai_analyst.py:143`).
- **Análisis sin habitaciones** (capa mal nombrada): el error ofrece "Ver capas de este archivo" sobre el DXF que acaba de fallar.

### 8.3 Registro de eventos de sesión

Buffer en memoria, últimos 50, `{ timestamp, tipo, detalle }` con `tipo` ∈ `analisis` | `exportacion` | `error`. Lo leen la sección Logs y el historial de Exportar — un dato, dos vistas. Se pierde al recargar; no hay backend que lo reciba hasta el PRD de persistencia.

### 8.4 Estado de carga

Durante el análisis, el sidebar permanece (con `+ Nuevo` deshabilitado) y el área central muestra el progreso. **No se sustituye la Shell entera por una pantalla de carga**: eso es lo que hace una web al navegar; una aplicación de escritorio mantiene su marco y trabaja dentro.

## 9. Navegación

### 9.1 Rutas

| Ruta | Vista |
|---|---|
| `#/` | **Inicio: parrilla de proyectos** (v3 — ya no es el formulario de subida) |
| `#/nuevo/analizar` | Analizar plano |
| `#/nuevo/generar` | Generar proyecto |
| `#/proyecto/:id` | Workspace |

`#/proyectos` desaparece: era una reserva para lo que ahora es `#/`. Con persistencia, `:id` es el identificador estable del proyecto en disco, así que recargar en `#/proyecto/:id` **carga el proyecto**, ya no degrada a `#/`.

### 9.2 Qué no se enruta

Overlays, panel de Ajustes, panel de Exportar, colapso del sidebar, vivienda y modo activos. No son destinos: son estado. La restauración de vivienda/modo/encuadre ya está diseñada en las tareas 12-13 del PRD de persistencia; duplicarla en la URL sería la misma responsabilidad en dos sitios.

### 9.3 Teclado

| Tecla | Acción |
|---|---|
| `Escape` | Cierra la capa más alta abierta. Una por pulsación |
| `Ctrl+1` / `Ctrl+2` | Alterna sidebar / panel derecho |
| `↑` `↓` | Navega el árbol; `←` `→` pliega y despliega |
| `1`…`6` | Cambia de modo |
| `Espacio` (mantenida) + arrastre | **(v4)** Panea el plano. Segunda vía junto al botón central, para ratones y trackpads que no lo tienen |
| Doble clic en vacío | **(v4)** Encuadra (equivale a `ZE`) |

**Regla de foco (v4):** con el cursor dentro de la línea de comandos, ningún atajo global se dispara — ni `1`…`6`, ni la barra espaciadora del paneo. Escribir un comando no puede tener efectos colaterales por el camino.

### 9.4 Capas

| z-index | Elemento |
|---|---|
| 40 | Desplegable de `+ Nuevo` |
| 60 | Tooltips |
| 70 / 71 | Panel flotante — backdrop / contenido |
| 80 | Panel de Ajustes |
| 100 / 105 | Visores 3D y su tooltip |

## 10. Transiciones

- Entre vistas de Nivel Aplicación: fundido de 120ms del contenido central.
- Inspector ↔ Exportar: el mismo `fadeSwap` que ya usa el Inspector entre sus estados.
- Desplegables: **sin animación**.
- Panel de Ajustes: fundido + escala 0.98→1, 150ms.
- Colapso del sidebar: 140ms sobre el ancho. **El sidebar nunca se desmonta al navegar** — si se recreara en cada cambio de vista, la transición sería un parpadeo y se perdería la sensación de marco persistente que justifica todo este rediseño.
- Restricción heredada de la iteración 1, vigente: `fadeSwap` escribe `opacity` inline, así que ninguna animación de entrada sobre `.svg-container` o `#inspector` puede usar `fill-mode: both`.

## 11. Delta de implementación

**Tokens que se añaden:** `--selection` (renombre de `--accent`), `--overlay-subtle` y `--overlay-hover` (ya existen, pasan a ser los únicos fondos de interacción de la Shell).

**Tokens que se retiran de la interfaz:** `--color-recommendation` (§4.2), `--accent-soft`, `--accent-border`, `--shadow-sm`, `--shadow-lg` (queda solo `--shadow-md` para capas flotantes), `--radius-md`, `--radius-lg`, `--radius-xl` (todo a 4px).

**Muere** (de `rediseno-total-propuesta.md` §5.1, aprobado): los 4 botones del header, el toggle de tema con emoji, `.badge*`, `#header-score` + `#score-breakdown-popover` + `.sb-legend*`, `#dashboard-panel`, `.upload-card`, `.dropzone-icon`, `.dropzone-sub`, `.orient-badge*`, `.filter-chip*`, `.detail-more*`, `.form-section`/`.form-grid`, y los 7 SVG decorativos.

**Orden de construcción (v3):** los pasos 1 y 7 de la v2 ya están hechos. El resto se sustituye por el plan de §11 del PRD `2026-08-02-shell-lateral-e-inicio-de-proyectos.md`, que es ahora el orden vigente:

1. ~~Sistema visual~~ — **hecho** (commit `2470610`).
2. ~~Barra superior~~ — **derogado**; se elimina en su lugar.
3. ~~Los cinco menús~~ — **derogado**; ver §5.
4. Sidebar: estructura, colapso, persistencia de la preferencia.
5. Eliminación de la barra superior y reubicación de sus funciones.
6. Fusión del riel de viviendas en la zona contextual del sidebar (§6).
7. Inicio: estado de creación y parrilla de proyectos.
8. Atajos de teclado y repaso de accesibilidad.

> **Corrección de hecho (2026-08-02).** La v2 cerraba diciendo "cada paso se verifica con el smoke test jsdom (hoy 72 comprobaciones)". **Ese smoke test no existe y no ha existido nunca**: no hay `package.json`, ni runner de JS, ni un solo archivo de test en el repositorio — `PROJECT_AUDIT.md` ya lo decía y esta especificación lo contradecía. El PRD de persistencia arrastra el mismo error en su §12. Lo que sí existe desde el 2026-08-02 es `tests/fixtures/ejemplo-dxf-analisis.json`: la respuesta real de `/api/analizar` sobre `ejemplo.dxf` (6 viviendas), utilizable como golden master interceptando `window.fetch` para montar el workspace sin volver a subir un DXF de 20 MB ni pagar otra llamada a la IA. Es el punto de partida de la red de seguridad, no la red terminada.

---

**Decisión:** _pendiente de revisión por Pablo_
