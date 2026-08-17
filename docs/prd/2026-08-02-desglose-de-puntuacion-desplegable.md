# PRD — Desglose de puntuación desplegable

**Estado:** Borrador · **Fecha:** 2026-08-02 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

> **Aviso al lector.** Este PRD nació como "hacer el índice de calidad más
> estético, con desplegables y una animación agradable". Al verificar los
> datos antes de escribirlo apareció un problema anterior y más grave: **hay
> dos sistemas de puntuación conviviendo en el proyecto y no están de
> acuerdo**. La sección 1 lo documenta con los números reales. El desplegable
> sigue siendo buena idea, pero no se puede implementar antes de resolver
> eso: enseñaría un desglose que contradice al número que tiene encima.

---

## 1. Problema que resuelve

### 1.1 El problema tal como lo planteó Pablo

Petición directa (2026-08-02), inmediatamente después de neutralizar el
marcador que resultaba "infantil" (commit `19a6549`):

> "si el indice de calidad es importante quiero que sea mas estetico, que sea
> como desplegables y haya una animacion bonita para que sea gustoso trabajar
> alli"

Detrás del acabado hay un hueco real de producto. Hoy el inspector afirma
**92** y no puede responder a la única pregunta que ese número provoca:
*¿por qué 92 y no 80?* La respuesta —qué categoría está tirando de la nota
hacia abajo— es exactamente lo que un arquitecto necesita para decidir dónde
intervenir, y no está en pantalla.

No es que falte el dato. El dato se calcula, se serializa, se envía en cada
respuesta de la API y **el frontend lo tira**. `desglose_puntuacion` vive en
cada vivienda desde `analyzer/scoring.py`, tuvo un popover en la barra
superior, y el rediseño de la Shell lo eliminó dejándolo anotado como pérdida
consciente en `static/app.js`:

> "Ese desglose por categoría no tiene hoy otro sitio en la interfaz: se
> pierde con este cambio, no se traslada."

Este PRD es el sitio.

### 1.2 El problema que apareció al verificarlo

Al comprobar la aritmética contra el proyecto real `ejemplo.dxf` (6
viviendas), la premisa se cayó. Estos son los datos de la API, hoy:

| Vivienda | `puntuacion` (lo que se ve) | `desglose.puntuacion_total` | `valoracion` | `desglose.valoracion` |
|---|---|---|---|---|
| VT1/3 | 92 | 92,4 | verde | verde |
| VT2/2 | 93 | 94,0 | verde | verde |
| VT3/3 | 91 | 95,8 | verde | verde |
| VT4/2 | 87 | 91,2 | verde | verde |
| **VT5/1** | **81** | **93,7** | **amarillo** | **verde** |
| **VT6/2** | **76** | **88,5** | **amarillo** | **verde** |

Y a nivel de proyecto la contradicción es total:

| | Valor | Semáforo |
|---|---|---|
| `puntuacion_global` (lo que se ve en el Inicio) | **87** | **verde** |
| `desglose_puntuacion.puntuacion_total` | **62,7** | **rojo** |

**Son dos cálculos independientes sobre los mismos issues.** No es un error
de redondeo: son 24,3 puntos y dos semáforos opuestos sobre el mismo
proyecto. La discrepancia está incluso documentada en el código, aunque sin
llamarla por su nombre — `analyzer/api_serializer.py` describe el desglose
como *"ADITIVO a `puntuacion`/`valoracion`, que siguen viniendo de
`UnitScore.score_pct`/`.rating` sin tocar"*. "Aditivo" aquí significa "otro
sistema, en paralelo, sin reconciliar".

Nadie lo ha notado porque **el segundo sistema es invisible**. En cuanto se
publique en el inspector, el panel dirá "93,7" justo debajo de un "81".

Hay una tercera consecuencia ya en producción: `percentil_estimado` se
calcula desde `desglose_global.puntuacion_total` (62,7), **no** desde el 87
que se enseña. El percentil que hoy ve el usuario está anclado a un número
que el usuario nunca ve y que contradice al que sí ve. `MOAT_ANALYSIS.md` ya
cuestionaba el percentil como funcionalidad sin foso; esto le añade que
además es incoherente.

### 1.3 Por qué el desglose global está peor que el de vivienda

El desglose por vivienda es aritméticamente sano: cada categoría parte de 100
y resta por sus issues. El global aplica **la misma función** a los issues de
las 6 viviendas juntas, contra un único techo de 100 puntos por categoría.
Resultado: "Iluminación y ventilación" cae a **0** no porque el proyecto sea
inhabitable, sino porque seis viviendas acumulan deducciones sobre un techo
pensado para una. Con 20 viviendas, todas las categorías darían 0 y todos los
proyectos serían idénticamente pésimos.

Eso no es un desacuerdo de criterio: es un defecto de agregación.

## 2. Usuario afectado

El arquitecto individual de hoy — el único usuario real, el propio Pablo
revisando un DXF. Es quien mira el número y decide si abre el plano o cierra
la aplicación.

En el horizonte de `NORTH_STAR_2031.md` afecta además a cualquier escenario
donde la puntuación salga del ordenador de quien la generó (informe a
cliente, revisión de colegio profesional, criterio de aseguradora). Ahí un
número que no se puede explicar no vale nada, y dos números que se
contradicen valen menos que ninguno.

## 3. Objetivo de negocio

**Convertir la puntuación en algo defendible.** Hoy es una cifra opaca; una
cifra opaca es fácil de imitar y fácil de desconfiar. `MOAT_ANALYSIS.md`
sitúa el foso en el rigor normativo, no en la interfaz: una puntuación que
se abre y enseña "Accesibilidad 63, −5,6 puntos, DB-SUA" *es* ese rigor hecho
visible, y es lo que separa a ArchMuse de un validador genérico.

Efecto secundario, y no menor: el defecto de la sección 1.2 es exactamente el
tipo de ataque que `DESTROY_ARCHMUSE.md` describe. Un competidor —o un
cliente escéptico— que encuentre dos puntuaciones contradictorias en la misma
respuesta de la API tiene material para descartar el producto entero. Se
arregla ahora, en local y sin usuarios, o se arregla delante de alguien.

## 4. Objetivo técnico

Una vez implementado, debe ser cierto que:

1. **Existe una sola puntuación.** Para cualquier vivienda y para el
   proyecto, `puntuacion` y el total del desglose son el mismo número, o uno
   de los dos ha dejado de existir. Verificable con un test, no con una
   inspección visual.
2. El desglose por categoría es **visible y auditable** desde el inspector:
   la suma de puntos perdidos por categoría explica exactamente la distancia
   entre 100 y la puntuación.
3. El inspector usa **un patrón de sección plegable único**, no un widget
   especial para el índice: mismo marcado, misma animación, mismo recuerdo de
   estado que ya tienen el sidebar (`Ctrl+1`) y el propio inspector (`Ctrl+2`).
4. La animación es **funcional y respeta `prefers-reduced-motion`**: informa
   de que algo se despliega, no adorna.

## 5. Casos de uso

**CU-1 — "¿Por qué 92?"** El arquitecto abre una vivienda, ve el índice,
despliega el desglose y lee en dos segundos que toda la pérdida está en
Accesibilidad e Iluminación. Cierra. Sabe dónde mirar.

**CU-2 — Del diagnóstico a la incidencia.** Desde el desglose pulsa
"Accesibilidad" y la lista de incidencias queda filtrada a esa categoría.
Deja de haber un salto entre "qué está mal" y "qué corrijo".

**CU-3 — Comparar viviendas.** Recorre VT1 a VT6 con el desglose abierto. La
sección conserva su estado abierto entre viviendas, así que la comparación es
directa: la misma tabla cambiando de valores, no seis clics.

**CU-4 — Justificar ante un tercero.** Exporta o enseña la pantalla a un
cliente. La nota deja de ser una opinión del software y pasa a ser una cuenta
con sus sumandos a la vista.

## 6. Casos límite

| Caso | Comportamiento exigido |
|---|---|
| Vivienda sin incidencias (100/100) | El desglose se despliega igual, con las seis categorías a 100 y sin ninguna barra roja. No se oculta la sección: su ausencia se leería como un fallo de carga. |
| Todas las categorías a 100 menos una | Orden por pérdida: la única con pérdida arriba, las cinco restantes agrupadas debajo (ver §14, riesgo de ruido). |
| `desglose_puntuacion` ausente | Proyectos **ya guardados** en SQLite antes de este cambio no tienen por qué traerlo. La sección no se pinta, sin error en consola. Relacionado con la invalidación de caché por versión de motor, pendiente del PRD de persistencia (tarea 4) — que sigue sin implementar y que ya provocó una vez servir un SVG obsoleto. |
| Categoría con peso 0 | No se pinta: no puede perder ni ganar puntos. |
| Proyecto de 1 vivienda | El desglose global y el de la única vivienda deben coincidir. Hoy **no coinciden**; es el test más barato del defecto de §1.3. |
| Payload viejo con `valoracion` y `desglose.valoracion` distintos | Manda `valoracion` (lo que ya se enseña); nunca se pintan los dos. |

## 7. Flujo del usuario

1. Abre un proyecto → entra en modo Resumen (sin cambios).
2. Ve la cabecera actual: `ÍNDICE DE CALIDAD · ▌92 /100 · Cumplimiento
   correcto · 2 críticas · 3 importantes · 7 recomendaciones`.
3. Debajo, una fila plegada: `▸ Desglose por categoría — 7,6`.
4. Pulsa. La sección se despliega en 180 ms; las seis barras crecen desde
   cero escalonadas 30 ms, ordenadas por puntos perdidos.
5. Lee. Pulsa "Accesibilidad" → salta al modo Problemas filtrado a esa
   categoría.
6. Vuelve. La sección sigue abierta. Cambia de vivienda: sigue abierta.
   Cierra la aplicación y vuelve mañana: sigue abierta.

## 8. Criterios de aceptación

**Puntuación (bloqueante, precede a todo lo demás)**

- [ ] `tests/test_scoring_coherencia.py` comprueba, sobre las 6 viviendas de
      `ejemplo.dxf` y sobre el proyecto, que `puntuacion` y el total del
      desglose no difieren en más de 1 punto y que ambos caen en el mismo
      semáforo. Hoy este test falla en 4 de 6 viviendas y en el proyecto: se
      escribe **antes** del arreglo y debe pasar después.
- [ ] Un proyecto de 1 vivienda tiene desglose global idéntico al de esa
      vivienda.
- [ ] `percentil_estimado` se calcula desde la misma puntuación que se
      muestra, o se retira (ver §14).

**Desglose**

- [ ] Las seis categorías aparecen con nombre, puntuación y puntos perdidos.
- [ ] La suma de puntos perdidos iguala `100 − puntuación`, con tolerancia
      de 0,1 por redondeo.
- [ ] El orden es por puntos perdidos descendente, estable ante empates.
- [ ] Pulsar una categoría lleva al modo Problemas filtrado a esa categoría.

**Plegado y animación**

- [ ] El estado de cada sección persiste en `localStorage` y sobrevive a
      recargar, cambiar de vivienda y cambiar de proyecto.
- [ ] La apertura no produce salto de altura al terminar la transición
      (`grid-template-rows: 0fr → 1fr`, sin medir alturas en JS).
- [ ] Con `prefers-reduced-motion: reduce` la sección abre y cierra sin
      transición y sin escalonado.
- [ ] Ninguna animación se dispara al cargar, ni en bucle, ni sobre el
      lienzo.
- [ ] Teclado: la cabecera de sección es un `<button>` con `aria-expanded`
      correcto.

## 9. Riesgos

**R1 — El arreglo de puntuación es más grande de lo que parece (alto).**
Decidir cuál de los dos sistemas sobrevive no es una decisión de interfaz:
cambia la nota de todos los proyectos ya guardados y el percentil. Mitigación:
la decisión se toma explícitamente antes de tocar código (tarea 1), y las
notas de proyectos guardados se recalculan o se invalidan.

**R2 — Compite con `REFACTOR_MASTERPLAN.md` (medio).** Sí compite, y hay
tareas de endurecimiento con más derecho al tiempo que un desplegable —
señaladamente la invalidación de caché por versión de motor, que ya causó un
fallo real esta semana. **Pero la parte de puntuación de este PRD no es una
mejora estética: es un defecto de datos**, y encaja en el masterplan por
derecho propio aunque el desplegable se posponga.

**R3 — Ruido visual (medio).** Seis filas de las que cinco dicen 100 son
cinco filas que no informan. Mitigación en §14.

**R4 — La animación envejece mal (bajo).** Lo que deleita el primer día irrita
el día treinta. Mitigación: 180 ms, solo en apertura provocada por el usuario,
y el escalonado limitado a las barras. Explícitamente **descartado** el
contador animado del número (§14).

**R5 — Solapamiento con los filtros existentes (bajo).** El modo Problemas ya
filtra por severidad y por disciplina. La categoría de puntuación es un tercer
eje. Mitigación en §14.

## 10. Impacto sobre módulos existentes

| Módulo | Impacto |
|---|---|
| `analyzer/scoring.py` | **Alto.** `compute_scoring_breakdown` es correcta por vivienda e incorrecta agregando. Se corrige la agregación o se elimina el desglose global. |
| `analyzer/evaluator.py` | **Alto si se decide unificar hacia `scoring.py`.** `UnitScore.score_pct` es hoy la fuente de lo que se enseña. |
| `analyzer/api_serializer.py` | Medio. Es donde conviven los dos sistemas (líneas ~130, ~153, ~258, ~279, ~309). El comentario "ADITIVO" queda obsoleto. |
| `static/app.js` | Medio. `informeEjecutivoHtml` y un nuevo patrón `seccionPlegable`. |
| `static/style.css` | Bajo. Tokens ya existentes; sin colores nuevos. |
| `analyzer/report_html.py` / PDF | **Revisar.** Si el informe de la CLI imprime la puntuación, cambia con ella. |
| `analyzer/storage.py` | Bajo, pero los proyectos guardados quedan con la nota vieja. Ver tarea 4 del PRD de persistencia. |
| `percentil_estimado` | Alto: hoy cuelga del número equivocado. |

## 11. Plan de implementación

Tareas independientes, ≤2 h. **Las tareas 1-3 son bloqueantes: sin ellas el
desplegable publica una contradicción.**

| # | Tarea | Depende |
|---|---|---|
| 1 | ~~Escribir `tests/test_scoring_coherencia.py` con los criterios de §8. Debe **fallar** al escribirlo.~~ **HECHA** — falló 6 de 6 al escribirlo, como debía. | — |
| 2 | ~~Decidir y documentar qué sistema es la fuente de verdad~~ **DOCUMENTADA, DECISIÓN PENDIENTE DE PABLO** en `docs/design/2026-08-02-dos-sistemas-de-puntuacion.md`. Recomendación: el sistema 2. No se implementa por iniciativa propia porque cambia todos los números de un proyecto ya guardado, y al alza. | 1 |
| 3 | **PARCIAL.** Los tres defectos que no requerían decisión, hechos: umbrales del PDF unificados (eran 80/60 frente a 85/70), agregación del desglose por vivienda (69,7 «rojo» → 93,8 «verde»), y `percentil_estimado` retirado. **La contradicción verde/rojo ha desaparecido.** Queda la brecha numérica de 7,2 puntos, que depende de la tarea 2. | 2 |
| 4 | ~~Anclar `percentil_estimado` a la puntuación superviviente, o retirarlo.~~ **HECHA: retirado.** Colgaba de la puntuación perdedora (percentil 45 en vez de 79) y no tenía ningún consumidor — se quitó de la interfaz hace semanas por ser dato inventado; dejarlo en el JSON solo servía para que volviera a colarse. | 3 |
| 5 | Patrón `seccionPlegable(id, titulo, meta, contenido)` en `app.js` + CSS con `grid-template-rows`, `aria-expanded` y `prefers-reduced-motion`. | — |
| 6 | Migrar "Prioridad de intervención" al patrón nuevo, sin cambiar su contenido. Valida el patrón sin arriesgar nada. | 5 |
| 7 | Sección "Desglose por categoría": datos, orden por pérdida, barras, puntos perdidos. | 3, 5 |
| 8 | Escalonado de barras al abrir (30 ms), anulado con `prefers-reduced-motion`. | 7 |
| 9 | Persistencia del estado de secciones en `localStorage`. | 5 |
| 10 | Categoría clicable → modo Problemas filtrado. Requiere resolver §14.3. | 7 |
| 11 | Actualizar `docs/design/2026-08-01-especificacion-shell.md` a v5. | 7 |

## 12. Plan de pruebas

**Automático**

- `tests/test_scoring_coherencia.py` (nuevo, tarea 1) — el test que importa.
- `tests/test_storage.py` — debe seguir en verde: si la puntuación cambia,
  cambia lo que se guarda.
- `tests/fixtures/ejemplo-dxf-analisis.json` — golden master. **Este cambio
  lo invalida a propósito**: hay que recapturarlo y revisar el diff a mano,
  que es justamente la prueba de que la puntuación cambió como se esperaba.

**Manual, en navegador**

- Abrir y cerrar la sección 20 veces seguidas: sin salto de altura, sin
  parpadeo, sin acumulación de listeners.
- Recorrer las 6 viviendas con la sección abierta: los valores cambian, el
  estado no.
- Con `prefers-reduced-motion` activo: abre instantáneo.
- Con el inspector plegado (`Ctrl+2`) y desplegado: sin residuos.
- Un proyecto guardado **antes** de este cambio: no revienta.

## 13. Métricas para medir el éxito

Con un solo usuario no hay analítica que valga. Las métricas honestas aquí
son de producto, verificables a mano:

1. **Coherencia (binaria).** ¿Existe algún par de números contradictorios en
   la respuesta de la API? Hoy sí. Objetivo: no.
2. **¿Pablo lo usa?** A las dos semanas: ¿deja la sección abierta o cerrada?
   Si vive cerrada, el desglose no aporta y sobra — el mejor indicador
   disponible, y por eso el estado se persiste.
3. **¿Reduce clics?** Hoy, ir del número al problema son 3 clics (modo
   Problemas → filtro → incidencia). Objetivo: 1.
4. **Anti-métrica.** Si el inspector tarda más en pintarse o la navegación
   del plano pierde fluidez, el cambio ha fracasado aunque se vea bien.

## 14. Posibles motivos para NO implementar la idea

### 14.1 El desplegable no era el problema

Pablo pidió estética; lo que la verificación encontró fue un defecto de
datos. Si hubiera que elegir una sola cosa, **es el arreglo de la puntuación
y no el desplegable**. Un número mal calculado y bonito sigue estando mal
calculado. Recomendación: tareas 1-4 sí o sí; 5-11 solo después.

### 14.2 Cinco de seis filas dirán 100

En un proyecto sano el desglose es cinco líneas que no informan y una que sí.
La alternativa —enseñar solo las categorías con pérdida y agrupar el resto en
"4 categorías sin incidencias"— es más honesta y ocupa un tercio. **Es la que
recomiendo**, aunque sea menos vistosa que seis barras animadas. Si de las
seis barras solo importan dos, seis barras son decoración con datos encima.

### 14.3 El filtrado por categoría añade un tercer eje

El modo Problemas ya filtra por severidad y por disciplina. Categoría es un
tercer criterio que se solapa parcialmente con disciplina y que puede dejar la
interfaz en un estado que el usuario no sabe deshacer. Alternativa más barata
y probablemente mejor: pulsar una categoría **resalta** sus incidencias en la
lista sin filtrar nada. Decidir antes de la tarea 10; en la duda, no filtrar.

### 14.4 Lo que se descarta explícitamente

- **Contador animado de 0 a 92.** Es el efecto más apetecible y el que
  devuelve el marcador a la condición de trofeo que se acaba de corregir en
  `19a6549`. No.
- **Animar el ribbon o el lienzo.** AutoCAD no anima su cromo por una razón:
  el informe se lee, el espacio modelo se trabaja.
- **Gráfico de tarta o radar de las seis categorías.** Seis valores no
  necesitan un radar; necesitan seis líneas ordenadas.

### 14.5 El argumento de fondo: cuatro rediseños en dos días

La especificación de Shell va por la versión 4 en 48 horas y **ninguna
versión ha sobrevivido a un uso real**. Este PRD propone la v5. Sostengo lo
que ya he dicho dos veces: usar la herramienta unos días con planos propios
antes de la siguiente ronda de rediseño produciría mejor información que
cualquier propuesta hecha mirando capturas.

Matiz importante: eso vale para las tareas 5-11. **No vale para las 1-4.** Que
el proyecto tenga dos puntuaciones contradictorias no es una cuestión de gusto
que el uso vaya a aclarar; es un defecto, está ahí desde antes de esta
conversación, y no mejora esperando.

---

**Decisión:** _pendiente de revisión por Pablo_
