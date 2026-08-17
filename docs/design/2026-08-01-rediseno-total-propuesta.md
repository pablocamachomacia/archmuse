# Rediseño total — propuesta y auditoría de eliminación

**Estado:** Propuesta · **Fecha:** 2026-08-01 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

Cuarto documento de la serie. Los tres anteriores ya cubren buena parte de lo pedido aquí; este no los repite. Hace tres cosas que ellos no hacen: **resuelve tres contradicciones** entre esta petición y lo ya aprobado, **audita la eliminación** con inventario real del código, y **fija el sistema visual** (paleta, tipografía, densidad) que hasta ahora estaba implícito.

---

## 1. Qué de esta petición ya está resuelto

No vuelvo a escribirlo. Punteros:

| Regla de la petición | Dónde está resuelta |
|---|---|
| 1 — El plano manda | Iteración 3 (implementada) + `arquitectura-de-producto.md` §4 |
| 2 — Eliminar aspecto web | Este documento, §5 (inventario) |
| 3 — Shell con menús | `especificacion-shell.md` §2 — **con tres conflictos, §3 de aquí** |
| 4 — Panel izquierdo tipo árbol | `especificacion-shell.md` §3 — **con un conflicto de datos, §3.2 de aquí** |
| 5 — Inspector, nunca dashboard | Iteración 3 (implementada) + `especificacion-shell.md` §5.2 |
| 6 — Espacio negativo | Este documento, §4.3 |
| 7 — Paleta | Este documento, §4.1 — **con un conflicto, §3.3 de aquí** |
| 8 — Tipografía jerárquica | Este documento, §4.2 |
| 9 — Navegación de software | `especificacion-shell.md` §9 (hash routing) |
| 10 — ¿Ayuda a decidir? | `flujo-de-usuario.md` completo (auditoría minuto a minuto) |

Lo que sigue es solo lo nuevo.

## 2. Sobre "no optimices, rediseña"

Estoy de acuerdo con el espíritu y lo aplico en §5 sin contemplaciones. Pero una precisión honesta: **la iteración 3 ya fue un rediseño desde cero de la pantalla de resultados**, no una optimización. Se eliminó el dashboard entero, la barra de contexto, los badges de puntuación sobre el plano, el pulso azul de 2 segundos, las listas de problemas, los iconos por fila y las etiquetas técnicas. Lo que queda del Workspace (plano reencuadrado, informe ejecutivo de 3 puntos, foco por atenuación, barra de modos) es el resultado de aplicar exactamente el criterio de la regla 10.

Lo digo porque "elimina el 70%" tiene una respuesta distinta según de dónde se mida: **del ArchMuse de hace una semana, ya se ha eliminado más de la mitad.** De lo que queda hoy, el recorte adicional que propongo en §5 es real pero no llega al 70% — y forzarlo hasta esa cifra significaría cortar cosas que sí ayudan a decidir. La cifra correcta la fija la regla 10, no un porcentaje objetivo.

## 3. Tres contradicciones que necesito que resuelvas

Esta petición choca en tres puntos con decisiones que ya aprobaste o con lo que el código puede sostener. No las resuelvo por mi cuenta.

### 3.1 "Archivo" + "Proyecto" + "Exportar" son tres menús para dos ideas

Pides barra superior: `Archivo · Proyecto · Herramientas · Exportar · Ventana` y `Configuración` a la derecha. Hace dos turnos aprobaste: `Proyecto · Herramientas · Exportar · Ventana` y `Usuario` a la derecha.

Dos cambios, y ambos me parecen un retroceso:

- **"Archivo" y "Proyecto" se solapan.** En Revit, "Archivo" contiene Nuevo/Abrir/Guardar/Exportar — es *todo* el ciclo del documento. Si ArchMuse tiene "Archivo" *y* "Proyecto" *y* "Exportar", el usuario tiene que adivinar en cuál de los tres está "abrir un análisis anterior". Además, aquí no hay archivos que el usuario gestione: hay un DXF que se sube una vez y un proyecto que ArchMuse posee. **Recomiendo: un solo menú, "Proyecto"**, tal como estaba aprobado.
- **"Configuración" en lugar de "Usuario" a la derecha.** Tú mismo pediste hace dos turnos que Usuario existiera con Configuración, Estado IA, Logs y Acerca de dentro. Si el trigger pasa a llamarse "Configuración", las otras tres secciones (Estado IA, Logs, Acerca de) quedan sin sitio natural: nadie busca los logs dentro de "Configuración". **Recomiendo mantener "Usuario"** como contenedor y Configuración como su primera sección, que es lo aprobado.

Si prefieres "Archivo" y "Configuración" pese a esto, dilo y lo aplico — pero quería que la contradicción fuera explícita antes, no descubrirla al implementar.

### 3.2 El árbol "Viviendas / Plantas / Elementos" no tiene datos detrás

Pides que el panel izquierdo muestre `Proyecto → Viviendas · Plantas · Elementos`. Dos de esas tres ramas no existen:

- **Plantas** — ya lo documenté en el PRD de persistencia: el concepto solo existe para proyectos *generados*, codificado en el nombre de la vivienda (`"Planta 1 · …"`) y leído por expresión regular en `evaluator.py:2579`. Un DXF analizado produce `VT1/3`, `VT2/2`… sin ninguna planta asociada; el propio docstring de `compute_floor_areas` dice que esas viviendas "no se asignan a ninguna planta". Una rama "Plantas" en un DXF analizado estaría **siempre vacía**.
- **Elementos** — no existe en absoluto. El modelo de datos llega hasta la habitación (`Room`: etiqueta, polígono, área) y nada más. No hay muros, ni puertas, ni ventanas, ni forjados como entidades: el parser extrae polilíneas cerradas de una capa y las convierte en habitaciones (`parser.py:200`). Una rama "Elementos" sería un nodo que al desplegarse no contiene nada.

Un árbol con dos de tres ramas permanentemente vacías es peor que no tener árbol: enseña al usuario que la aplicación promete más de lo que tiene. **Recomiendo el árbol de dos niveles ya aprobado** (`Proyecto → Vivienda → Habitación`), con Plantas apareciendo **solo cuando el dato existe** (proyectos generados). "Elementos" requeriría extraer entidades del DXF que hoy se descartan — es un PRD de análisis, no de interfaz.

### 3.3 "Solo grises" mata el modo Espacio

Pides: paleta de grises, y color solo para error, advertencia, correcto y selección. Nada más.

El modo **Espacio** de la barra de modos —aprobado e implementado en la iteración 3— existe precisamente para lo contrario: pinta cada habitación con el color de su uso (verde salón/cocina, azul dormitorio, crema baño, naranja terraza, lila tendedero), definidos en `analyzer/plan_svg.py:52-58`. Ese color no comunica error ni corrección: comunica **tipo de espacio**, que es información arquitectónica legítima y es la razón de ser del modo.

Son incompatibles. Tres salidas, por orden de mi preferencia:

1. **La regla aplica a la Shell, no al plano.** Toda la interfaz (barras, menús, inspector, árbol) en grises estrictos con los cuatro colores semánticos; el plano conserva el color por uso **dentro del modo Espacio y solo ahí** — en Resumen, Luz, Normativa, Problemas y Diagnóstico el plano ya es papel neutro hoy. El color por uso deja de ser decoración y pasa a ser el contenido de un modo concreto, que es exactamente lo que la regla 7 pide ("el color comunica algo"). **Es la que recomiendo.**
2. **Eliminar el modo Espacio.** Coherente con la regla al pie de la letra, pero pierde una vista que sí ayuda a decidir (ver de un golpe el reparto de usos de una vivienda).
3. **Recolorear el modo Espacio en escala de grises** por uso. Mantiene la vista y la regla, pero cinco grises distinguibles y además legibles sobre papel neutro es un problema de contraste que dudo que se resuelva bien.

## 4. Sistema visual (lo que faltaba por fijar)

### 4.1 Paleta

**Grises — la escala completa de la interfaz.** Doce pasos, del fondo al texto primario, con el mismo tono en claro y oscuro invertido. Todo lo que no sea plano ni estado se dibuja con estos: fondos, bordes, texto, iconos, separadores. Un gris no comunica nada por sí solo — comunica **profundidad** (qué está delante) y **jerarquía** (qué se lee antes).

**Color — cuatro, y ni uno más:**

| Rol | Uso permitido | Uso prohibido |
|---|---|---|
| Error | Severidad crítica: pin de problema, habitación en modo Problemas, contador | Bordes, fondos de sección, cualquier cosa "importante" |
| Advertencia | Severidad no crítica, mismas superficies | Ídem |
| Correcto | Confirmación de estado (vivienda sin problemas) | Botones de acción, éxito de operaciones triviales |
| Selección | El elemento con foco — y **uno solo a la vez en toda la pantalla** | Hover, activo de menú, filas alternas |

La regla operativa: **un color en pantalla debe poder responderse con "porque esto está mal/bien/seleccionado".** Si la respuesta es "porque es un botón importante" o "para que destaque", se retira.

Consecuencia inmediata sobre el código actual: de los tokens de color definidos hoy, `--accent`, `--accent-hover`, `--accent-soft` y `--accent-border` son exactamente ese caso — color de marca aplicado a botones primarios y estados activos. **Se colapsan al gris de selección.** Sobreviven `--green/--green-bg`, `--yellow/--yellow-bg`, `--red/--red-bg` como los tres estados, más la paleta de plano (`--plan-room`, `--plan-wall`, `--plan-warning`, `--plan-problem`, `--plan-dim`) introducida en la iteración 3.

### 4.2 Tipografía

Cuatro tamaños en toda la aplicación. Ni uno más — cada tamaño adicional es una jerarquía que el usuario tiene que aprender.

| Rol | Tamaño | Peso | Uso |
|---|---|---|---|
| Cifra | 3.25rem | 600 | La puntuación del informe ejecutivo. Solo ahí. |
| Título | 1.05rem | 500 | Encabezado del inspector, nombre del elemento seleccionado |
| Cuerpo | 0.8125rem (13px) | 400 | Todo lo demás: menús, árbol, informe, etiquetas |
| Meta | 0.75rem | 400 | Datos secundarios, siempre en gris atenuado |

Regla de sustitución de texto por forma, aplicada donde hoy hay texto redundante: la severidad de un problema **es** el color de su pin, no la palabra "Impacto alto" repetida junto a él; la orientación **es** la aguja de la brújula, no la palabra "Sur" además del glifo. En ambos casos se conserva la palabra **solo** cuando el color o la forma no bastan para desambiguar (p. ej. distinguir "alto" de "medio" sin comparar dos pines lado a lado).

### 4.3 Densidad y espacio negativo

Es donde más se juega la sensación de escritorio, y donde el instinto web engaña: **las aplicaciones profesionales son densas en los controles y generosas en el lienzo.** Revit no separa sus entradas de menú con 16px de aire; las apila a 22px de alto y deja todo el espacio restante al modelo. La regla "usa mucho espacio negativo" (tu punto 6) se aplica al **lienzo**, no a los paneles: aire alrededor del plano, densidad en árbol, menús e inspector.

Escala de espaciado a cuatro pasos —4 / 8 / 16 / 32px— y nada intermedio.

## 5. Auditoría de eliminación

Inventario real del `static/index.html` actual: **173 clases CSS**, **30 elementos `<button>`** en el marcado estático, **60 custom properties**, **7 SVG inline**.

### 5.1 Muere

| Elemento | Por qué |
|---|---|
| Todo el color de acento (`--accent*`, 4 tokens y sus usos) | No comunica estado — regla 7 |
| Botones de acción del header (`.btn-header-action` ×4: Generar, PDF, CSV, Nuevo) | Pasan a menús — regla 3, "no quiero botones flotando" |
| Botón de tema con emoji (`#btn-theme-toggle` + ☀️/🌙) | Emoji — regla 2. Pasa al menú Ventana |
| `.badge`, `.badge-lg`, `.badge-verde/amarillo/rojo` | La severidad ya la comunica el color del pin — regla 8 |
| `#header-score` + `#score-breakdown-popover` + `.sb-legend*` (7 clases) | La puntuación vive en el informe ejecutivo; duplicarla en la barra es ruido |
| `#dashboard-panel` (nodo muerto desde la iteración 3) | Ya no se renderiza; el nodo sigue en el DOM |
| `.upload-card`, `.upload-screen`, `.dropzone-icon`, `.dropzone-sub` | La tarjeta con sombra es el elemento más "web" que queda — regla 2 |
| `.orient-badge*` (4 clases), `.orient-neutral` | Insignias de texto dentro de una lista — regla 8 |
| `.filter-chip`, `.filter-chip-count`, `.filter-row` | Los filtros de severidad/disciplina son de la era del dashboard; el informe de 3 puntos no filtra |
| `.detail-more`, `.detail-more-body` | "Detalles técnicos" plegables — información que no ayuda a decidir, regla 10 |
| `.form-section`, `.form-grid`, `.form-field-full` (cajas del formulario de generar) | Cajas dentro de cajas — regla 2 |
| Los 7 SVG inline decorativos (chispa de "Generar", flecha de dropzone, check, documento…) | Iconos que acompañan a un texto que ya dice lo mismo — regla 2 |

Suma aproximada: **~55 clases CSS y 12 de los 30 botones**. Alrededor de un tercio de la superficie visual actual, no el 70% — y es, honestamente, lo que la regla 10 justifica cortar. Forzar la cifra hasta el 70% exigiría eliminar el árbol de viviendas, la barra de modos o el informe de tres puntos, y las tres cosas ayudan a decidir.

### 5.2 Sobrevive, y por qué

- **Barra de escala y brújula del plano** (`.scale-bar-*`, `.viewer-compass*`) — son las dos únicas piezas de la interfaz que un arquitecto espera encontrar en cualquier plano, y ambas responden preguntas que el dibujo solo no responde (¿de qué tamaño es esto? ¿hacia dónde mira?).
- **Panel flotante** (`.float-panel*`) — lista de habitaciones y orientación bajo demanda. Es la aplicación literal de tu regla permanente: esconder detrás de una interacción sencilla en vez de mostrar.
- **Visores 3D** (`#viewer-3d`, `#room-viewer-3d`) — sobreviven a esta auditoría porque no compiten con el plano (lo sustituyen por completo), pero conviene recordar que `MOAT_ANALYSIS.md` los señala como complejidad sin foso claro. Esa es una decisión de producto, no de interfaz, y no la tomo aquí.
- **Tooltip de habitación** (`.room-tooltip`) — responde "¿qué es esto?" sin gastar un clic ni ocupar espacio permanente.

## 6. Qué necesito de ti para pasar a implementar

1. **§3.1** — ¿"Archivo" separado de "Proyecto", y "Configuración" en lugar de "Usuario"? Mi recomendación es mantener lo ya aprobado (Proyecto + Usuario).
2. **§3.2** — ¿Confirmas el árbol de dos niveles en vez de Viviendas/Plantas/Elementos? Las dos ramas que faltan no tienen datos detrás.
3. **§3.3** — ¿Opción 1 (grises en la Shell, color por uso solo dentro del modo Espacio)? Es la que recomiendo.
4. **§5** — ¿Apruebas la lista de eliminación tal cual, o hay algo ahí que quieras conservar?

Con esas cuatro respuestas, el diseño queda cerrado y empiezo por la Shell, en el orden ya fijado en `arquitectura-de-producto.md` §8.

---

**Decisión:** _pendiente de revisión por Pablo_
