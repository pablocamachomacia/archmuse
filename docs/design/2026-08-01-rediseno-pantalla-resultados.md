# Rediseño de la pantalla de resultados

**Fecha:** 2026-08-01
**Ámbito:** `static/index.html` (solo capa de presentación — CSS y marcado generado)
**Tipo:** rediseño de una pantalla existente. **No es una capacidad nueva**, así que no lleva PRD
(ver `CLAUDE.md`). La clasificación se consultó con Pablo antes de implementar.

Tres iteraciones:

1. **Jerarquía visual** — un solo protagonista (el plano), menos cajas y bordes.
2. **Revelación progresiva** — de dashboard a herramienta profesional: el inspector reacciona al
   contexto en vez de mostrar listas abiertas.
3. **Narrativa de diagnóstico** — de herramienta a conclusión: la pantalla no espera a que el
   usuario pregunte, responde antes.

---

# Iteración 3 — Narrativa de diagnóstico

## Qué faltaba

Las dos iteraciones anteriores optimizaron **cuánta** información se ve. Ninguna atacó **qué tipo**
de información es. La pantalla entregaba datos organizados; lo que faltaba era un juicio. Un
arquitecto no abre esto para explorar: lo abre para saber si el proyecto pasa y qué tocar primero.

## La regla que gobierna la iteración

> **Una lista es lo que queda cuando nadie ha decidido. Un informe es el resultado de haber
> decidido.**

De ahí sale el límite duro del informe ejecutivo: **exactamente 3 puntos, y sin contador de resto**
("y 9 más"). En cuanto aparece ese contador vuelve a leerse como una lista truncada y se pierde el
efecto. Los 12 siguen a un clic, en el modo Problemas.

Esto resuelve la contradicción aparente entre "quiero una lista de 3 puntos" y "menos listas": tres
elementos jerarquizados y justificados no son una lista, son la conclusión.

## El informe ejecutivo

Sustituye al inspector en reposo. Puntuación grande sin el signo `%`, veredicto en palabras, una
única línea divisoria, y los tres puntos numerados. Cada punto es pulsable y **localiza su
habitación en el plano**.

Cambio de dato relevante: `valoracion` llega de la API como `"verde"`/`"amarillo"`/`"rojo"` y el
panel lo imprimía tal cual — un nombre de color donde debía ir un juicio. Ahora se traduce
(`VEREDICTO`) a "Calidad espacial buena / mejorable / insuficiente".

## Por qué el impacto va en palabras y no en puntos

Hay **dos puntuaciones distintas** en el JSON, calculadas en paralelo:

- `v.puntuacion` — de `evaluator.UnitScore.score_pct`. Es el número que muestra el informe.
- `desglose_puntuacion.puntuacion_total` — de `scoring.compute_scoring_breakdown`. Es al que
  pertenece `puntos_ganados`, el único dato que dice cuánto sube la nota al corregir algo.

Escribir "+4,2 puntos" bajo un "86" habría sido aritmética falsa: esos 4,2 no suben ese 86. Se
eligió (decisión de Pablo, opción A) **mantener el 86** y expresar el impacto como *Impacto alto /
medio / bajo*. `puntos_ganados` sí se usa, pero solo para **ordenar** los tres puntos, nunca para
mostrar una cifra.

La alternativa (opción B: titular = `puntuacion_total`) daba aritmética honesta pero obligaba a
unificar las dos puntuaciones en todo el producto, PDF incluido. Es un PRD propio.

## De herramientas a modos

`Resumen · Espacio · Luz · Normativa · Problemas · Diagnóstico`, y el 3D aparte al final.

Dos cambios de semántica respecto a la iteración 2:

- **Siempre hay un modo activo.** Desaparece el estado "ninguna herramienta": "Resumen" no es la
  ausencia de modo, es un modo con contenido propio.
- **"IA" pasó a llamarse "Diagnóstico".** El arquitecto elige una lectura del proyecto, no una
  tecnología.

Esto acerca los modos a las pestañas que la iteración 2 rechazaba. Lo que evita que lo sean es una
regla dura, implementada en `pintarPlano()`: **ningún modo deja el plano igual**. Un modo que solo
cambiara la columna derecha sería una pestaña disfrazada.

| Modo | Qué le hace al plano |
|---|---|
| Resumen | Papel neutro + los puntos numerados ①②③ del informe |
| Espacio | Devuelve el color por tipo de uso |
| Luz | Overlay de orientación |
| Normativa | Marca las habitaciones con incumplimiento de código |
| Problemas | Color por severidad |
| Diagnóstico | Atenúa el plano al 50%: aquí el protagonista es el texto |

## El plano

**Reencuadre (`ajustarViewBox`).** `plan_svg.py` escala cada vivienda a un viewBox fijo de 800×600
con 40px de margen y el `<svg>` se estira al contenedor: una vivienda alargada quedaba encajada en
un 4:3 dentro de un panel 16:9, con bandas vacías por los cuatro lados. **Esa era la causa real de
la sensación de lienzo vacío, no el padding.** Ahora el viewBox se ajusta al contorno real del
dibujo (+4% de margen) y el padding del contenedor baja de `2.5rem 3rem` a `12px 16px`.

El contorno se calcula leyendo los atributos (`points` de los polígonos, `cx/cy/r` de la rosa de los
vientos) en vez de con `getBBox()`. Es más largo, pero no depende de que el navegador haya hecho
layout, así que funciona en un DOM headless — que es lo que permite verificar el reencuadre en el
test en vez de dejarlo a ojo.

**Color con propósito.** Nuevas variables `--plan-room` / `--plan-wall` / `--plan-warning` /
`--plan-problem`, en claro y oscuro. El plano dejó de colorearse permanentemente por tipo de uso;
esa lectura no se ha perdido, vive dentro del modo Espacio. Muros a 1.4px en tinta (`--plan-wall`)
en vez de 1px en `--border`.

**Foco por atenuación.** El borde azul pulsante de 2s se ha eliminado. Al enfocar una habitación se
atenúa el resto (`.has-focus`, opacidad `--plan-dim`) y se encuadra con un zoom deliberadamente
generoso: la habitación ocupa como mucho un tercio del ancho, porque el arquitecto necesita seguir
viendo dónde está dentro de la vivienda.

## Máquina de estados

Un solo eje con dos niveles: `state.modo` (siempre poblado) y `state.seleccion` (el foco, que tiene
prioridad). Reglas:

1. Abrir una vivienda entra **siempre** en Resumen, sin foco.
2. Cambiar de modo descarta el foco.
3. **Un clic en el plano siempre gana**: selecciona esa habitación sea cual sea el modo, sin
   abandonarlo.
4. El foco tiene **tres salidas** al mismo sitio — `Escape`, "volver", y pulsar el vacío del plano —
   porque salir nunca debe costar pensar cuál era el gesto.

## Emparejamiento informe ↔ plano

Los números del informe y los puntos del plano son el mismo sistema: pasar el ratón por uno realza
el otro, en ambas direcciones. Es el detalle que hace que las dos columnas se lean como un
diagnóstico y no como un dibujo al lado de una tabla.

**`room_label` no siempre es una habitación.** En los issues de vivienda completa el backend lo
rellena con el nombre de la vivienda ("VT1/3"). Sin resolverlo contra las habitaciones reales
(`indiceHabitacion`), el informe habría escrito "Impacto alto · VT1/3" y prometido un punto en el
plano que no existe. Ahora esas líneas se quedan sin habitación y sin marca, que es lo honesto.

## Qué se eliminó

Barra de contexto bajo el header (los 3 contadores por severidad) · rótulo "VIVIENDAS" del riel ·
`zoom-hint` ("Rueda del ratón: zoom") · `#center-badge` (el `%` junto al título duplicaba el número
del informe) · los contadores de cada herramienta en la barra inferior · el triángulo de aviso
repetido en los dos tooltips · el borde del `.btn-reveal` · el pulso azul de localización.

Se quedan: los filtros de problemas (están plegados y son función real), el tooltip del riel, el
desglose por categorías del header.

Ajuste de comportamiento: el tooltip del plano aparecía al instante y bastaba cruzar el plano con el
ratón para que saltaran cinco cajas seguidas. Ahora tiene 400ms de retardo.

## Medidas

| Elemento | Antes | Ahora |
|---|---|---|
| `.panel-left` | 212px | 168px |
| `.panel-right` | 288px | 320px |
| `.svg-container` padding | 2.5rem 3rem 3rem | 12px 16px |
| viewBox | fijo 800×600 | contorno real + 4% |

En 1440px de ancho el panel central se queda en ~66%, y en 1920 en ~75%. Llegar al 75% en portátil
exigiría que el inspector flotara sobre el plano, y se descartó: taparía plano justo donde está el
problema que el informe describe. La ganancia de percepción viene del reencuadre, no de los píxeles
del panel.

## Lo que NO se hizo

**Conexiones visuales entre problemas encadenados.** Había datos reales (`efectos_cadena`) y habría
sido potente, pero es la única pieza que sería **capacidad nueva** y no reorganización. Decisión de
Pablo: fuera de esta iteración, PRD aparte.

**No se tocó `analyzer/plan_svg.py`.** Todo el reencuadre y el repintado ocurren sobre el SVG ya
insertado en el DOM. Motivo: ese mismo SVG lo consumen el informe HTML del CLI y el PDF, y un cambio
de estética de la SPA no debe propagarse ahí.

## Verificación

**72/72 comprobaciones pasan, sin errores de JS en consola** (`smoke.js`, jsdom, con el JSON real de
`ejemplo.dxf`). Cubre el montaje, el reencuadre (incluido que no recorta el dibujo), el informe
ejecutivo y lo que NO muestra, el emparejamiento informe↔plano con su numeración, el foco y sus tres
salidas, que cada modo repinta el plano de forma distinta, el panel flotante, el clic en el plano y
el cambio de vivienda.

CSS: balance de llaves OK, 55 variables usadas todas definidas. `GET /` → 200.

**No verificado: el aspecto visual.** La extensión de Chrome sigue sin conectar. jsdom valida
estructura y comportamiento, no diseño.

## Hallazgos abiertos

1. **Dos detectores solapados llenan dos de los tres huecos del informe.** En VT1/3 los puntos 1 y 2
   son "Baño sin superficie ni giro de baño adaptado" y "Baño sin espacio de giro para
   accesibilidad": el mismo defecto real detectado por dos vías (`evaluator` y
   `circulation`/`spatial_quality`), con códigos y títulos distintos. En una lista de 12 pasaba
   desapercibido; en un informe de 3 es evidente y desperdicia un tercio del espacio. **No se ha
   parcheado en la interfaz**: cualquier regla de deduplicación aquí sería frágil (los dos títulos y
   los dos códigos difieren) y taparía un problema que hay que arreglar en origen.
2. **Pocos puntos localizables en el plano.** En VT1/3 solo 1 de los 3 puntos tiene habitación
   asociada, porque los de mayor severidad son de vivienda completa. El orden por severidad es el
   honesto y no se ha alterado para que salgan más marcas, pero conviene mirarlo en varias viviendas
   antes de dar el emparejamiento por bueno.
3. **El plano en modo Espacio** recupera el color por uso incluyendo el tinte rojizo que el backend
   ya hornea en las habitaciones con problemas. Es el aspecto original del plano, pero ensucia
   ligeramente la lectura "por uso".

---

# Iteración 2 — Revelación progresiva

## Principio

El plano es el producto; todo lo demás son herramientas a su alrededor. La regla operativa ante
cualquier duda: **si se puede esconder detrás de una interacción sencilla, se esconde**.

## Los tres niveles

**Nivel 1 (permanente):** el plano, la puntuación global en la cabecera, el nombre y la puntuación
de la vivienda activa, y el riel de navegación entre viviendas.

**Nivel 2 (un clic):** problemas, superficies, luz, normativa, plan de acción — detrás de las
herramientas de la barra inferior.

**Nivel 3 (profesional):** código normativo, coste estimado, efectos en cadena, análisis IA
completo — plegado dentro del Nivel 2, nunca en pantalla propia.

## Las herramientas no son pestañas

La barra bajo el plano (Superficies · Luz · Normativa · Problemas · IA) se comporta como una caja
de herramientas, no como una barra de pestañas, y la diferencia es deliberada:

- **Existe el estado "ninguna".** No hay segmento "Plano": el plano desnudo es lo que queda cuando
  no hay herramienta activa, que es el estado inicial. Volver a pulsar la herramienta activa la
  apaga.
- **Solo una a la vez.** Es lo que garantiza que la pantalla no pueda volver a llenarse.
- **Cada herramienta lleva su contador** al lado del nombre. Es la única cifra visible sin abrir
  nada, y existe precisamente para no tener que abrirla para saber si tiene contenido.
- **El 3D va al final, separado por un hueco mayor.** No es una capa sobre el plano: es otro modo
  de ver el proyecto, y la separación visual lo dice.

Dos herramientas pintan sobre el plano (Luz y Problemas); las otras tres solo cambian el
inspector. Es una asimetría real y consciente: son las dos únicas sobreimpresiones que el código
sabe dibujar hoy, y este rediseño no añade lógica nueva.

Cambio relevante: **el tinte de severidad sobre las habitaciones antes se aplicaba siempre**. Ahora
solo con la herramienta Problemas activa. Por defecto el plano se ve limpio.

## El inspector

Una sola función (`renderInspector`) decide qué se ve, con esta prioridad:

1. **Hay algo seleccionado** (un problema o una habitación) → su detalle.
2. **Hay herramienta activa** → el panel de esa herramienta.
3. **Nada** → reposo.

El **estado de reposo** muestra la puntuación de la vivienda, su estado, y su problema más grave
resumido con un botón "Ver detalle". Nada más. Es el caso particular que hace que la pantalla
arranque respondiendo a las tres preguntas del arquitecto (qué hay, qué tal está, hay algo grave)
sin desplegar una sola lista.

La **preselección automática del problema más grave** al abrir una vivienda es lo que llena ese
estado de reposo: primero por severidad, y a igualdad de severidad el primero que entregó
`buildUnifiedProblems` (los issues del evaluador van antes que las heurísticas).

**La navegación va del plano al inspector, no al revés.** Pulsar una habitación en el plano la
selecciona y el inspector pasa a describirla. Pulsar un problema en la lista lo abre en detalle y
además lo localiza en el plano.

## Qué se ocultó y dónde está ahora

| Antes, siempre visible | Ahora |
|---|---|
| Lista de habitaciones | Panel flotante, desde la herramienta Superficies |
| Orientación y luz por habitación | Panel flotante, desde la herramienta Luz |
| Normativa CCAA | Herramienta Normativa |
| Lista completa de problemas | Herramienta Problemas |
| Detalle de cada problema | Selección de un problema |
| Código, coste, efectos en cadena | Nivel 3, plegado dentro del detalle |
| Plan de acción | Dentro de la herramienta Problemas |
| Análisis IA (3 bloques) | Herramienta IA |
| Filtros de problemas | Dentro de la herramienta Problemas, plegados |
| Filtros de vivienda + CSV en el riel | CSV movido a la cabecera; los filtros de vivienda se eliminaron |
| Superficie y barra de categorías por vivienda | Tooltip del riel (Nivel 3) |

## Decisiones de producto tomadas en esta iteración

**El percentil comparativo se ha eliminado, no escondido.** Salía de `scoring.TIPOLOGIA_BENCHMARKS`,
una tabla de referencia inventada, y se presentaba como percentil de mercado — deshonesto, ya
flagueado en `PROJECT_AUDIT.md` y `TECH_REVIEW.md`. Ya no aparece en ninguna parte de la interfaz.
Verificado además que el PDF nunca lo incluyó. **Pendiente:** el backend lo sigue calculando y
enviando (`api_serializer.py` → `percentil_estimado`); quitarlo de ahí es un cambio de lógica y
queda fuera del alcance de este rediseño.

**"Aplicar mejora" no se ha implementado.** Modificar la geometría y recalcular es una capacidad
nueva de producto: contradice la restricción de "no añadir funcionalidades" y necesitaría un PRD.
No se pone un botón que no hace nada.

**Iconos eliminados:** el ☀️ del botón de luz, la ★ del indicador lumínico, los ✓/✗ de normativa y
los pictogramas de tipo de habitación. Estos últimos porque la etiqueta ya dice "Dormitorio": un
icono redundante con su texto no mejora la comprensión, solo añade textura de app móvil.

## Verificación

Se instaló jsdom (en el scratchpad, no en el proyecto) para poder ejecutar la pantalla de verdad
sin navegador. El script `smoke.js` carga el SPA, le inyecta el JSON real de `/api/analizar` sobre
`ejemplo.dxf` y recorre la interacción completa: **41/41 comprobaciones pasan, sin errores de JS en
consola.** Cubre el montaje del workspace, el estado de reposo (y que NO despliega listas), el paso
a detalle con sus cuatro bloques, el plegado del Nivel 3, el encendido/apagado de herramientas, el
panel flotante y su cierre con Escape, la selección desde el plano, la navegación lista→detalle, el
cambio de vivienda y la ausencia del percentil.

El test encontró dos fallos reales que ya están corregidos: apagar la última herramienta dejaba el
reposo diciendo "sin incidencias" en viviendas que sí las tenían (faltaba restaurar la
preselección), y una condición con precedencia de operadores confusa en el botón "Volver".

**No verificado:** el aspecto visual. La extensión de Chrome sigue sin conectar, así que nadie ha
mirado la pantalla todavía. jsdom valida estructura y comportamiento, no diseño.

## Puntos a revisar a ojo

1. **Densidad del inspector en reposo.** Ahora muestra muy poco a propósito. Si al usarlo resulta
   escaso, el ajuste natural es añadir el recuento de problemas por severidad bajo la puntuación,
   no devolver listas.
2. **Descubribilidad de la barra de herramientas.** Son botones de texto sin borde. Si cuesta ver
   que son pulsables, darles fondo permanente tenue antes que borde.
3. **Coste en clics para el usuario experto.** Barrer los 12 problemas de una vivienda es ahora un
   clic (herramienta Problemas los lista todos de golpe), pero leer el detalle de cada uno es un
   clic más por problema. Es la contrapartida comprada con la revelación progresiva.

---

# Iteración 1 — Jerarquía visual

Reglas que siguen vigentes y que están escritas como comentario en el CSS (bloque `--- Workspace ---`):

1. **Ningún borde ni fondo separa paneles.** La jerarquía la da el espacio.
2. **El plano es el único elemento con color saturado.** El resto en grises; el color solo donde
   codifica severidad, y siempre como texto o punto, nunca como caja.
3. **Lo secundario entra con retardo.** El panel central aparece de inmediato y el resto 0,45 s
   después, así que durante ese medio segundo el plano es lo único visible.

**Cuidado con la animación:** no puede ir sobre `.svg-container` ni sobre `#inspector`, porque
`fadeSwap()` les escribe `opacity` en línea y una animación con `fill-mode: both` ganaría a ese
estilo para siempre, dejando el fundido roto tras el primer cambio de vivienda. Por eso
`plan-reveal` va en `.panel-center` (sin `fill-mode`) y `chrome-in` solo en contenedores cuya
opacidad no manipula nadie más.

Reducción medida de cajas, bordes y separadores en el primer pintado, sobre `ejemplo.dxf`
(6 viviendas; VT1/3 con 7 habitaciones, 12 problemas, 3 acciones, IA presente): **98 → 2 (−98%)**,
frente al objetivo de ≥60%. Las dos supervivientes son el realce de la vivienda seleccionada y la
marca ✓/✗ de superficie mínima CCAA. Tras la iteración 2 la cifra baja aún más, porque el riel
perdió sus filtros y el inspector ya no monta listas en reposo.

Elementos eliminados en esta iteración: pestañas de planta del header (duplicaban el riel), círculo
de puntuación global del riel (duplicaba la cabecera), separadores verticales del header, trama de
puntos del lienzo, fondos de color de los iconos de habitación, emojis 🔴🟠🔵 de la barra de
contexto, tarjetas de problema, y las pastillas tintadas de orientación, puntuación y plan de
acción.
