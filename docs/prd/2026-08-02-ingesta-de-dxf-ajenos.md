# PRD — Ingesta de DXF ajenos

**Estado:** Borrador · **Fecha:** 2026-08-02 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 1. Problema que resuelve

ArchMuse solo sabe leer los DXF de Pablo.

`analyzer/parser.py` está acoplado, a fuego, a las convenciones de dibujo de un único estudio. Esto no es una sospecha: son seis puntos verificados en el código, ordenados de más grave a menos.

**a) Las unidades del dibujo se dan por supuestas.** `Room.area_m2` (`parser.py:41-43`) devuelve `self.polygon.area` con el comentario literal *«se asume metros»*. Ningún módulo del proyecto lee la variable de cabecera `$INSUNITS` — comprobado con `grep` sobre todo `analyzer/`. Un DXF dibujado en milímetros, que es práctica corriente en España, entra con todas las áreas multiplicadas por 1.000.000.

Y aquí está lo peor: **no revienta**. Un dormitorio de 12 m² se lee como 12.000.000, todas las reglas de superficie mínima se cumplen holgadamente, el SVG se normaliza al `viewBox` y se dibuja perfecto, y el proyecto sale con una puntuación alta y creíble. El sistema no falla: **miente con confianza**. Para un producto cuyo único activo es que un arquitecto se fíe de él, este es el peor modo de fallo posible de todo el repositorio.

**b) Solo se mira el modelspace de primer nivel.** `msp.query('LWPOLYLINE[layer=="..."]')` (`parser.py:70,77`) no atraviesa referencias de bloque. No hay ni una llamada a `virtual_entities()` ni ninguna mención a `INSERT` en el módulo. Si las habitaciones vienen dentro de un bloque —montaje habitual cuando se referencia una planta tipo— son sencillamente invisibles. Cero habitaciones, sin explicación.

**c) El nombre de la capa es una constante.** `AREA_LAYER = "00 areas"` (`parser.py:19`), interpolado directamente en el filtro de consulta. `SUPERFICIES`, `AREAS`, `A-AREA-IDEN` o `00 Areas` con mayúscula: cero habitaciones.

**d) Solo se leen MTEXT.** `extract_labels` y `extract_unit_labels` (`parser.py:150,190`) consultan `MTEXT` y nada más. Un plano rotulado con `TEXT` simple —muy común— produce habitaciones sin nombre. Y sin nombre no hay tipo de habitación, y sin tipo de habitación buena parte del motor de reglas no tiene sobre qué pronunciarse.

**e) El descarte de contornos agrupadores depende de una convención de color ACI.** `_discard_container_candidates` (`parser.py:91-130`) asume que las habitaciones reales van siempre en BYLAYER (256) y que los contornos agrupadores llevan color explícito. Es una convención de un estudio, no un estándar. En un plano donde todo lleva color explícito, la heurística deja de discriminar.

**f) El repliegue de etiquetas es global, no local.** `match_label_to_room` (`parser.py:160-178`), si no encuentra ningún texto dentro del polígono, coge **el más cercano de todo el plano**, sin límite de distancia. En un DXF con varias viviendas separadas, una habitación puede heredar la etiqueta de otra vivienda distinta. Además, cuando caen varios textos dentro, `inside[0]` elige por orden de aparición en el archivo, que es arbitrario.

*(Un séptimo punto que **no** es un defecto, para no inflar la lista: si no hay etiquetas `VT<n>`, `group_rooms_by_unit_label` sí tiene repliegue —`group_rooms_by_proximity`, `evaluator.py:279-280`—. Es más frágil, y el propio código lo dice, pero degrada en vez de romper.)*

Nada de esto está medido contra archivos reales. **No existe hoy ningún dato sobre cuántos de estos seis fallos ocurren de verdad, ni con qué frecuencia.** Ese vacío es el problema que este PRD ataca primero.

## 2. Usuario afectado

El arquitecto que **no** es Pablo — es decir, el primero que podría pagar.

Hoy el producto tiene exactamente un usuario compatible. Todo lo demás del roadmap (colaboración, garantía, integración BIM, relación institucional) presupone un usuario que todavía no puede ni subir un archivo. `NORTH_STAR_2031.md` sitúa a este usuario ya en el horizonte de 6 meses, con estudios piloto usándolo de forma continuada; eso es imposible mientras la ingesta solo acepte un dialecto de DXF.

## 3. Objetivo de negocio

Convertir un script personal en un producto. Es literalmente el paso de un usuario a *N* usuarios, y no hay ninguna otra capacidad del proyecto que pueda dar ese paso.

Además desbloquea el activo compuesto que `DESTROY_ARCHMUSE.md` §8 identifica como irrecuperable retroactivamente: sin ingesta de archivos ajenos no hay volumen de análisis, y sin volumen el percentil comparativo nunca dejará de ser una tabla de tres puntos escrita a mano. Cada mes sin acumular es un mes que no se recupera.

Y hay un objetivo defensivo, más incómodo: el punto (a) de la sección 1 es una **responsabilidad latente**. El día que ArchMuse dé una puntuación alta a un proyecto medido en milímetros y alguien tome una decisión con ella, el problema deja de ser de producto.

## 4. Objetivo técnico

Una vez implementado, debe ser cierto que:

1. ArchMuse **nunca analiza un DXF cuya escala no haya confirmado**, ni explícitamente por el usuario ni deduciblemente del archivo.
2. Ante un DXF que no entiende, ArchMuse **dice qué no ha entendido y qué esperaba encontrar** — nunca devuelve un análisis vacío, y nunca devuelve un análisis confiado sobre datos que no ha sabido leer.
3. El nombre de la capa de áreas y el tipo de entidad de rótulo dejan de ser constantes del código y pasan a ser **parámetros deducidos y confirmables**.
4. Existe una herramienta que, dado un lote de DXF, produce una tabla de qué se ha encontrado en cada uno — sin llamar a la IA y sin escribir nada en la base de datos.

El punto 4 es el que hay que construir primero, y la sección 11 explica por qué.

## 5. Casos de uso

**CU-1 — Medición (Pablo, herramienta interna).** Pablo reúne DXF de otros arquitectos, lanza el diagnóstico sobre la carpeta y obtiene una tabla: por archivo, unidades declaradas, capas candidatas con su recuento de polilíneas cerradas, entidades dentro de bloques, rótulos MTEXT y TEXT, y etiquetas `VT`. En una tarde sabe cuáles de los seis fallos son reales y en qué proporción.

**CU-2 — Subida de un DXF compatible.** Nada cambia respecto de hoy, salvo una confirmación de escala si el archivo no la declara.

**CU-3 — Subida de un DXF con otro nombre de capa.** ArchMuse propone las capas candidatas ordenadas por número de polilíneas cerradas: *«He encontrado 24 polilíneas cerradas en `SUPERFICIES` y 3 en `MOBILIARIO`. ¿Cuál contiene las habitaciones?»*. El arquitecto elige y el análisis continúa.

**CU-4 — Subida de un DXF en milímetros.** ArchMuse lee `$INSUNITS`, detecta milímetros y lo muestra: *«El archivo declara milímetros. La habitación mayor mide 24,3 m². ¿Correcto?»*. La comprobación de plausibilidad va incluida porque `$INSUNITS` a menudo está a 0 (sin especificar) o directamente mal.

**CU-5 — Subida de un DXF que no se entiende.** Ninguna capa contiene polilíneas cerradas en cantidad razonable. ArchMuse lo dice, enumera lo que sí ha visto y explica qué necesita. No crea proyecto.

## 6. Casos límite

- **`$INSUNITS = 0`** (sin especificar). Muy frecuente. Hay que recurrir a plausibilidad por tamaño y, si sigue siendo ambiguo, preguntar. Nunca suponer en silencio.
- **Unidades imperiales.** Se detectan y se rechazan con un mensaje claro: el motor entero está escrito contra el CTE en métrico. Rechazar es correcto; convertir sería fingir una cobertura que no existe.
- **Habitaciones repartidas entre varias capas.** Debe poder elegirse más de una.
- **Bloques anidados.** `virtual_entities()` resuelve un nivel; hay que decidir hasta qué profundidad se desciende y qué se hace con la transformación de coordenadas de cada `INSERT`.
- **Un DXF que ya funcionaba y que deja de funcionar.** `ejemplo.dxf` es el guardián de esta regresión y no puede degradarse en ningún punto.
- **Habitaciones como HATCH y no como polilínea.** Existe y es común. Queda **fuera de alcance** de este PRD, pero el diagnóstico debe contarlas, porque si resulta ser mayoritario cambia la prioridad de todo lo demás.
- **DXF de 25 MB o más.** `app.py:50` corta en 25 MB y `ejemplo.dxf` ya pesa 20. El diagnóstico trabajará sobre archivos locales sin ese límite, pero conviene saber cuántos lo superarían.

## 7. Flujo del usuario

Hoy: subir → analizar → informe.

Propuesto: subir → **ArchMuse informa de lo que ha entendido del archivo** → el arquitecto lo confirma o lo corrige → analizar → informe.

El paso nuevo debe autocompletarse cuando ArchMuse tiene certeza razonable, de modo que en el caso compatible sea un vistazo y un clic, no un formulario. Pero **no debe poder saltarse**, porque su función real no es configurar: es que el usuario vea que ArchMuse ha leído su plano antes de opinar sobre él. Ese momento es, además, la mejor demostración de competencia que el producto puede dar en los primeros diez segundos de uso.

## 8. Criterios de aceptación

1. `herramientas/diagnostico_dxf.py <ruta|carpeta>` emite una fila por archivo con: unidades declaradas, capas candidatas y su recuento de polilíneas cerradas, recuento de las que están dentro de bloques, MTEXT, TEXT, etiquetas `VT` y área de la mayor habitación candidata.
2. No llama a la API de Anthropic ni escribe en `~/.archmuse/archmuse.db`. Verificable sin clave de API configurada.
3. `parser.py` expone la detección de unidades y la lista de capas candidatas como funciones puras y testeables, sin dependencia de Flask.
4. Un DXF en milímetros **no** produce un análisis silencioso: o se corrige la escala o se detiene con un mensaje explícito.
5. Las habitaciones dentro de referencias de bloque se detectan, con sus coordenadas correctamente transformadas.
6. El nombre de la capa deja de ser una constante obligatoria; `AREA_LAYER` sobrevive solo como valor por defecto.
7. Los rótulos `TEXT` se leen igual que los `MTEXT`.
8. **`ejemplo.dxf` produce exactamente el mismo resultado que hoy**: mismo número de habitaciones, mismas etiquetas, mismas áreas, mismas viviendas.
9. Ningún DXF de la muestra de prueba produce un análisis completo sin que ArchMuse haya declarado antes qué capa y qué unidades ha usado.

## 9. Riesgos

**Que la muestra sea demasiado pequeña para concluir nada.** Con tres archivos de dos conocidos no se decide nada. Hacen falta ocho o diez, de estudios distintos. Es el riesgo principal y no es técnico: depende de que Pablo pida archivos.

**Que el diagnóstico revele que el problema es más grande de lo que este PRD supone** — por ejemplo, que la mayoría de los planos ajenos no tengan ninguna capa de áreas porque ese estudio simplemente no la dibuja. Sería un resultado incómodo y valiosísimo: significaría que ArchMuse necesita deducir habitaciones de los propios muros, que es un proyecto de otra magnitud. **Mejor descubrirlo con un script de dos horas que con seis meses de producto encima.**

**Compite con `REFACTOR_MASTERPLAN.md`.** Sí. Y también con la reconciliación de puntuación del PRD `2026-08-02-desglose-de-puntuacion-desplegable.md`, que sigue siendo un defecto real. La secuencia que propongo es: primero medir (tarea 1, dos horas), y con el dato en la mano decidir si sigue esto o si va antes la puntuación. No las dos a la vez.

**Que se construya la pantalla de confirmación antes de saber qué hay que confirmar.** El antídoto es el orden de la sección 11.

**Riesgo de regresión sobre el único usuario que hoy funciona.** Cualquier cambio en `parser.py` puede romper el caso de Pablo. Cubierto por el criterio 8 y por la tarea 2.

## 10. Impacto sobre módulos existentes

- **`analyzer/escala.py`** — módulo nuevo. *(Desviación respecto de la primera versión de este PRD, que preveía meter la detección de unidades dentro de `parser.py`. Se sacó fuera al implementar la tarea 3: es un concepto cerrado, se prueba sin fabricar ningún DXF, y `parser.py` ya es el archivo con más consecuencias por línea de todo el repositorio como para engordarlo 150 líneas más.)*
- **`analyzer/parser.py`** — el módulo entero. Es el archivo más pequeño (220 líneas) del núcleo y el que más consecuencias tiene.
- **`analyzer/evaluator.py`** — no se toca, pero **todo** lo que calcula depende de que las áreas estén en metros. Es el consumidor silencioso del defecto (a).
- **`app.py`** — `/api/analizar` necesita un paso previo, o un parámetro nuevo de capa y escala.
- **`static/app.js`** — pantalla de confirmación tras seleccionar el archivo.
- **`analyzer/plan_svg.py`** — no se toca; normaliza al `viewBox` y es indiferente a la escala. Precisamente por eso un plano en milímetros se dibuja perfecto, que es lo que hace el defecto (a) tan difícil de ver a simple vista.
- **`analyzer/storage.py`** — conviene guardar en el payload la capa y la escala usadas. Un proyecto guardado debe poder explicar de dónde salieron sus números.
- **`tests/`** — hoy hay 3 archivos de prueba para ~8.000 líneas de `analyzer/`. Ninguno cubre `parser.py`.

## 11. Plan de implementación dividido en pequeñas tareas

**El orden importa más que las tareas.** Las tareas 3 a 8 están escritas contra seis fallos *hipotéticos*. La tarea 1 existe para convertirlos en fallos *medidos*, y es perfectamente posible que su resultado reordene o elimine varias de las que vienen después. Por eso la tarea 2 es un alto explícito.

| # | Tarea | Estimación |
|---|---|---|
| 1 | ~~`herramientas/diagnostico_dxf.py`: lote de DXF → tabla de lo encontrado. Sin IA, sin base de datos, sin tocar `analyzer/`.~~ **HECHA** | 2 h |
| 2 | **Alto.** Pasar el diagnóstico sobre 8-10 DXF ajenos y reordenar de la 3 a la 9 con el dato delante. **PENDIENTE — faltan los archivos.** | — |
| 3 | ~~Detección de unidades: leer `$INSUNITS` + comprobación de plausibilidad por tamaño. Función pura, con pruebas.~~ **HECHA** (`analyzer/escala.py`). Adelantada saltándose la tarea 2 a propósito: es la única de la lista que no depende de la medición, porque el defecto está verificado por inspección y no por hipótesis. | 2 h |
| 4 | ~~Aplicar el factor de escala en `build_rooms_from_document`, con `ejemplo.dxf` como guardián de regresión.~~ **HECHA**, pero en una función nueva `parser.leer_plano` y no dentro de `build_rooms_from_document`: la escala hay que aplicarla a la geometría **y** a las coordenadas de las etiquetas de vivienda a la vez, y con dos funciones sueltas cualquier llamante puede escalar solo la mitad y agrupar mal las viviendas sin ningún error visible. | 2 h |
| 5 | ~~Capas candidatas: función que puntúa cada capa por polilíneas cerradas y devuelve la lista ordenada.~~ **HECHA** (`parser.capas_candidatas` / `parser.elegir_capa`). Puntúa por cuatro señales y no solo por recuento: contar polilíneas elegiría la capa de mobiliario, que siempre tiene más. **Los pesos son provisionales** — calibrados contra un solo DXF real, y hay que revisarlos con los datos de la tarea 2. | 2 h |
| 6 | ~~Parametrizar el nombre de la capa de extremo a extremo (`parser` → `app.py` → SPA).~~ **HECHA.** `AREA_LAYER` ya no es obligatorio: sobrevive como preferencia cuando existe y sirve. En la SPA no se añade un campo fijo — los controles solo aparecen cuando ArchMuse ha tenido que preguntar, y el archivo elegido ya no se pierde al fallar. | 2 h |
| 7 | ~~Leer `TEXT` además de `MTEXT` en ambos extractores de etiquetas.~~ **HECHA**, pero no como un `query("TEXT")` más: en `ejemplo.dxf` hay cinco `TEXT` que son marcas de carpintería (`PE-01`, `VE-01`) y **dos caen dentro de una habitación**, así que leerlos sin prioridad renombraba dos estancias. Los MTEXT van antes que los TEXT, y esa es la regla de desempate. Se lee además `align_point` cuando el rótulo está alineado. | 1 h |
| 8 | ~~Atravesar referencias de bloque con `virtual_entities()`, transformando coordenadas.~~ **HECHA.** Las coordenadas no hay que transformarlas: ezdxf ya las devuelve en el sistema del plano. Lo que sí hubo que hacer a mano es **resolver la herencia de la capa `0`** — ezdxf devuelve la capa literal, y dibujar las habitaciones en capa 0 dentro del bloque es lo más habitual. **Es la única de las nueve sin ninguna validación real:** `ejemplo.dxf` no tiene ni un `INSERT`. | 2 h |
| 9 | ~~Acotar el repliegue de `match_label_to_room` con una distancia máxima.~~ **HECHA.** Umbral **relativo** (`0,5 × √área`), no absoluto en metros: esta función trabaja en unidades de dibujo, antes de la conversión de escala. Inocuo para `ejemplo.dxf`, donde las 34 estancias tienen su rótulo dentro y el repliegue **no se ejecuta ni una vez**. | 1 h |
| 11 | **NUEVA, pendiente de decisión de Pablo.** `inside[0]` elige por orden de aparición en el archivo cuando hay varios rótulos dentro del mismo polígono. Ocurre en **33 de 34** estancias de `ejemplo.dxf`; en 5 los rótulos se contradicen y en **2 el resultado cambiaría** si mandara la cercanía al centroide (dos polígonos grandes, de 52,1 y 58,6 m², que hoy salen «Salón/cocina» y pasarían a «Baño»). No se toca sin decisión: cambia el tipo de estancia y con él la puntuación de un proyecto ya guardado. Ver §14. | — |
| 10 | Pantalla de confirmación en la SPA. **Requiere PRD propio de diseño** — no se improvisa aquí. | — |

Las tareas 3, 5, 7 y 9 son independientes entre sí y pueden ir en cualquier orden. La 4 depende de la 3; la 6 depende de la 5.

## 12. Plan de pruebas

**Guardián de regresión, no negociable:** `ejemplo.dxf` debe seguir dando 6 viviendas, las mismas habitaciones, las mismas etiquetas y las mismas áreas después de cada tarea. Se congela hoy la salida actual como fichero de referencia, **antes de tocar nada**. Sin este paso el resto del plan es imprudente.

**Nuevo `tests/test_parser_ingesta.py`**, siguiendo el patrón de `tests/test_plan_envolvente.py` (bloque rápido sintético + bloque lento sobre el DXF real):
- Unidades: `$INSUNITS` en metros, milímetros, centímetros, ausente, e imperial.
- Escala: un mismo polígono en metros y en milímetros debe dar la misma área en m².
- Capas candidatas: ordenación correcta, y ninguna candidata en un DXF sin polilíneas cerradas.
- Rótulos: `TEXT` y `MTEXT` mezclados en el mismo plano.
- Bloques: una habitación dentro de un `INSERT` desplazado y rotado aterriza donde debe.
- Repliegue de etiqueta: una habitación sin texto dentro y con el texto más cercano a 40 m **no** hereda esa etiqueta.

Los DXF de la muestra que resulten problemáticos se conservan en `tests/fixtures/`, con permiso de sus autores, como banco de pruebas permanente. Ese banco es, con el tiempo, más valioso que el código de este PRD.

## 13. Métricas para medir el éxito

- **La métrica que de verdad importa: cuántos de 10 DXF ajenos producen un análisis correcto sin intervención manual.** Hoy ese número es desconocido, y mi expectativa honesta es que esté entre 0 y 2. El objetivo tras las tareas 3-9 es 7 de 10, con los 3 restantes fallando de forma **explicada**, nunca silenciosa.
- Cero análisis completados sin escala confirmada (verificable en el payload guardado).
- Tiempo desde que un arquitecto ajeno abre ArchMuse hasta que ve su primer informe correcto. Si supera los cinco minutos, el paso de confirmación está mal diseñado.
- Número de DXF distintos, de estudios distintos, analizados con éxito. Es el contador de si esto es un producto.

## 14. Posibles motivos para NO implementar la idea

**El argumento más fuerte en contra: esto solo importa si alguien más va a usar ArchMuse, y esa decisión no está tomada.** Si el proyecto es una herramienta personal excelente —que lo es— y va a seguir siéndolo, las seis dependencias de la sección 1 no son defectos: son **especialización**, y hacen el código más simple. Un producto que solo funciona con tus archivos es un problema exclusivamente si el plan es venderlo. Este PRD nace de que Pablo preguntó qué falta para venderlo. Si esa premisa cambia, el documento entero se cae.

**Segundo argumento: hay un defecto más urgente sin arreglar.** Las tres escalas de puntuación que no coinciden —`evaluator.score_rating` en 90/70, `pdf_report.py:30` en 80/60, y el total distinto de `scoring.py` (87 verde en pantalla contra 62,7 rojo en el desglose, medido sobre `ejemplo.dxf`)— son un defecto vivo hoy, para el usuario que ya existe. La ingesta es un defecto para usuarios que todavía no existen. Es un argumento serio de secuenciación, y por eso la tarea 2 es un punto de decisión y no un trámite.

**Tercero: puede que la respuesta correcta no sea DXF.** `DESTROY_ARCHMUSE.md` §3 sostiene que todo el trabajo de reconstruir habitaciones desde geometría 2D es *«la cicatriz de haber elegido trabajar desde el formato equivocado»*, y que en IFC las habitaciones ya son objetos de primera clase con sus límites y adyacencias. Este PRD invierte en robustecer precisamente ese trabajo compensatorio. Es una objeción legítima y no la descarto: la respondo con que un arquitecto español pequeño en 2026 todavía manda DXF, y que IFC es una apuesta de horizonte de 6-12 meses que además exige validación previa (`NORTH_STAR_2031.md`, horizonte de 3 meses). No conviene apostar a IFC sin haber confirmado antes que hay demanda.

**Lo que sí sostengo sin matices, pase lo que pase con el resto del documento:** la tarea 1 cuesta dos horas, no toca ni una línea de producto, y produce el único dato con el que se puede decidir cualquiera de estas tres discusiones. Aunque este PRD se rechace entero, esa tarea debería hacerse igual.

**Recomendación:** aprobar la tarea 1 sola. Volver a leer este documento con la tabla del diagnóstico delante.

---

**Decisión:** _pendiente de revisión por Pablo_
