# Flujo de usuario — de abrir ArchMuse a exportar el informe

**Estado:** Propuesta · **Fecha:** 2026-08-01 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

Precede a `2026-08-01-arquitectura-de-producto.md` y `2026-08-01-especificacion-shell.md` en el orden correcto: primero la experiencia, después la arquitectura que la sirve. Este documento audita ambos contra un recorrido real y corrige lo que sobraba.

---

## 1. El recorrido, minuto a minuto

Un arquitecto tiene el DXF de la planta baja de un edificio de seis viviendas recién exportado de AutoCAD. Quiere saber si tiene problemas antes de mandarlo al cliente.

**00:00 — Abre ArchMuse.** Lo primero que ve es la zona para arrastrar el DXF, ocupando el centro de la pantalla, con norte/ciudad/tipología debajo como campos discretos ya rellenados con valores por defecto. **No** una pantalla "Inicio" con dos tarjetas ("Analizar" / "Generar") para elegir antes de llegar aquí — si no tiene ningún proyecto guardado, que es siempre hoy, esa elección no aporta nada: el 95% de las veces la respuesta es "tengo un DXF". Cero clics hasta la acción real.

**00:04 — Arrastra el archivo.** Aparece el chip de confirmación, el botón "Analizar plano" se habilita.

**00:07 — Pulsa Analizar** (no toca norte/ciudad/tipología — ya traían valores razonables).

**00:08 → 00:2X — Espera.** Pantalla de carga con progreso. Esta es la única espera larga de todo el recorrido, y como se detalla en la sección 3, **no depende de ninguna decisión de interfaz** — es la que de verdad importa optimizar.

**00:2X — Entra al Workspace.** Ve el informe ejecutivo: 86, "Calidad espacial buena", tres puntos numerados. **Este es el primer momento de valor real** de toda la sesión — todo lo anterior era fricción necesaria (subir el archivo) o espera.

**00:2X+08 — Pulsa el primer punto** ("Dormitorio 2 con iluminación insuficiente"). El plano hace foco en esa habitación, atenúa el resto. Segundo momento de valor: de "hay un problema" a "veo exactamente dónde".

**00:2X+35 — Cambia de vivienda** en el Explorador (panel izquierdo) para ver si el mismo problema se repite en VT2/2. Se repite — el plano y el informe se actualizan.

**00:2X+50 — Cambia al modo Luz** en la barra inferior, para ver el mapa de luz natural del edificio completo, no solo de una vivienda.

**00:2X+65 — Decide que ya tiene lo que necesita.** Quiere un PDF para el cliente.

**00:2X+66 — Exportar** (barra superior) → elige Informe PDF → Generar y descargar.

**00:2X+70 — Descarga completada.** Tercer y último momento de valor: el informe en su mano.

Esfuerzo real del usuario, sin contar la espera del backend en 00:08→00:2X: **por debajo de dos minutos**, casi todo "arrastrar → click → click". Ese es el número que hay que proteger.

## 2. Auditoría: qué participa, qué no, y qué hago con ello

| Elemento | ¿En el camino descrito? | Veredicto |
|---|---|---|
| Dropzone + campos (Analizar) | Sí — es el primer paso | Sin cambios |
| **"Inicio" como pantalla separada de "Analizar"** | No — solo añade una decisión antes del primer paso | **Cortar: se fusionan (§3)** |
| Generar proyecto (vista) | No — es un camino de entrada alternativo real, no el dominante | Mantener, pero degradado a enlace secundario (§3) |
| Pantalla de carga | Sí — obligatoria | Sin cambios de interfaz; ver hallazgo de fondo (§3.1) |
| Informe ejecutivo (modo Resumen) | Sí — es el momento de valor | Sin cambios |
| Foco pin ↔ plano | Sí — el segundo momento de valor | Sin cambios |
| Explorador de viviendas | Sí | Sin cambios |
| Barra de modos | Sí | Sin cambios |
| Exportar | Sí — el cierre del recorrido | Mantener, simplificar (§4) |
| Menú Proyecto (Nuevo / Cerrar proyecto) | Parcialmente — "Nuevo" al empezar una sesión nueva, "Cerrar" al terminarla | Justificado: baja frecuencia, por eso vive en un menú y no como botón permanente |
| Menú Herramientas → Inspector de capas DXF | No en el camino feliz — sí en el camino de error (DXF con la capa de habitaciones mal nombrada) | Mantener, **y exponer también en el punto de fallo** (§5), no solo enterrado en un menú |
| Menú Herramientas → Comparar versiones | No participa en ningún flujo hoy, ni siquiera de error — no hay versiones que comparar | **Cortar del todo por ahora** (§5) — un marcador de dirección deshabilitado no ayuda a nadie hoy; se añade cuando exista de verdad |
| Menú Ventana (tema) | No — preferencia pura | Justificado: coste casi cero (una línea de menú), ya no es un botón de la barra |
| Usuario → Configuración | No en la primera vez — sí ahorra tecleo en sesiones repetidas | Mantener, perfil bajo |
| Usuario → Estado IA | No — transparencia y control de coste, pedido explícitamente por Pablo | Mantener, perfil bajo |
| Usuario → Logs | No en el camino feliz — sí como historial cuando algo falla | Mantener, perfil bajo |
| Usuario → Acerca de | No, en ningún flujo | Justificado como convención mínima esperada de cualquier aplicación de escritorio; coste ≈ 0 |
| Mis proyectos | No existe hoy — pero en cuanto exista, **sustituye por completo los minutos 00:00→00:2X** de un usuario que vuelve | No se corta: se refuerza como la vía de mayor valor una vez llegue el PRD de persistencia — ver §6 |

La regla que se aplicó en cada fila: si el elemento cuesta un clic en el camino de los dos minutos, tiene que ganárselo con valor real; si vive en un menú de baja frecuencia y no interpone nada, basta con que exista una razón honesta, aunque sea secundaria.

## 3. El hallazgo que importa más

Ninguno de los ajustes de interfaz de este documento mueve la aguja tanto como esto: **la espera de 00:08 a 00:2X está dominada por una llamada a la IA que bloquea un dato que ya estaba listo antes de hacerla.**

En `app.py:79-101`, `evaluate_advanced(...)` — la geometría pura, sin red, milisegundos — calcula ya la puntuación del 86% antes de que `analyze_with_ai(...)` (`ai_analyst.py:130`) se ejecute. Esa llamada es sin streaming, `max_tokens=4096`, sobre todas las viviendas del edificio a la vez, y el payload completo —incluida la puntuación ya calculada— no se devuelve al navegador **hasta que la IA termina de responder**. El usuario mira una pantalla de carga genérica esperando algo que, en su mayor parte, ya estaba resuelto antes de empezar a esperar.

Esto no se arregla tocando la Shell — es un cambio de contrato de la API (`/api/analizar` pasaría a responder en dos tiempos, o por streaming) y por la regla de proceso de `CLAUDE.md` necesita su propio PRD antes de tocar código. Lo señalo aquí porque este ejercicio de pensar en minutos reales es exactamente lo que lo saca a la luz: es la única partida de la sesión medida en segundos de espera muerta en lugar de clics, y ningún rediseño de pantalla la toca. **Si el objetivo es tiempo hasta el valor, esto vale más que cualquier ajuste de Shell pendiente en este documento.**

## 4. Cambio en Exportar: quitar el paso que no existe todavía

La especificación de la Shell (§5.3) diseñaba el paso "Alcance" del flujo de Exportar con dos opciones, una de ellas ("Vivienda actual") deshabilitada porque el backend no la soporta hoy. Bajo el criterio de este documento eso es un coste sin valor en el camino de los dos minutos: nadie necesita ver una opción que no puede elegir en el único momento en que solo quiere su PDF. **Se corrige:** el paso Alcance no se renderiza mientras exista una sola opción real. La región sigue reservada en el layout (para el día que haya una segunda), pero no se le enseña al usuario un radio button que no lleva a nada — misma regla que ya aplicamos a "Abrir…" en el menú Proyecto.

## 5. Cambio en Herramientas: la del camino de error se mueve, la que no sirve a nadie se corta

- **Inspector de capas DXF** deja de vivir solo en el menú Herramientas. Cuando `/api/analizar` no encuentra habitaciones (el síntoma real de una capa mal nombrada, dado que `AREA_LAYER = "00 areas"` está fijo en `analyzer/parser.py:19`), el banner de error de la pantalla de Analizar debe ofrecer directamente "Ver capas de este archivo" sobre el mismo DXF ya elegido — no obligar a que el usuario adivine que existe un menú Herramientas y que ahí hay algo que le puede ayudar. El menú se mantiene como acceso general (para inspeccionar un DXF antes de analizarlo), pero el camino de error real pasa por el punto del fallo, no por un menú.
- **Comparar versiones** se retira del menú. No participa en ningún flujo — ni el feliz ni el de error — porque no hay versiones que comparar todavía, ni las habrá hasta el PRD de persistencia. Un ítem deshabilitado permanente no comunica dirección, comunica una promesa sin fecha. Se añade el día que haya algo real detrás, con el mismo criterio que ya aplicamos a "Abrir…" en el menú Proyecto — no antes.

Herramientas queda, por ahora, con un único ítem real. Es correcto que sea así: un menú de un ítem que existe por una razón concreta es mejor que uno de dos que finge ser una plataforma de extensiones.

## 6. Cambio en Inicio: se fusiona con Analizar plano

Se elimina "Inicio" como pantalla intermedia para el caso de hoy (sin proyectos guardados). El contenido pasa a ser condicional dentro de una sola vista, no dos:

- **Sin proyectos guardados** (siempre, hasta el PRD de persistencia): la vista `#/` muestra directamente el formulario de Analizar plano — dropzone al centro, campos debajo. Debajo del botón principal, un enlace de menor peso: "¿Sin plano todavía? Generar un proyecto desde cero →", que lleva a `#/nuevo/generar`. Un único CTA visualmente dominante, uno secundario, cero pantallas de por medio.
- **Con proyectos guardados** (una vez exista persistencia): la vista `#/` se invierte — pasa a mostrar primero la franja de recientes (la vía de mayor valor para un usuario que vuelve, ver §1: sustituye 00:00→00:2X enteros por un clic) y el formulario de Analizar queda como una acción secundaria ("Nuevo análisis"), no al revés.

`#/nuevo/analizar` se mantiene como ruta estable — es el mismo contenido que `#/` muestra en el caso vacío, y sirve además para volver a él explícitamente desde el menú Proyecto una vez hay proyectos guardados y `#/` ya no lo muestra por defecto.

## 7. Lo que esto no cambia

Explorador, barra de modos, foco pin↔plano, informe ejecutivo — todo lo construido en las iteraciones 1-3 pasó la auditoría sin cambios: cada pieza participa en el camino de los dos minutos y ya se diseñó bajo el mismo criterio ("si un elemento no ayuda a tomar una decisión arquitectónica, ocultarlo"). Este documento confirma que ese criterio, aplicado ahora a la Shell, produce los mismos cortes que ya hicimos en el panel derecho.

---

**Decisión:** _pendiente de revisión por Pablo_
