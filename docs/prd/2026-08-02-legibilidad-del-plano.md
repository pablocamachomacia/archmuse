# PRD — Legibilidad del plano (dibujo, no datos)

**Estado:** Borrador · **Fecha:** 2026-08-02 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

> **Alcance.** Este PRD cubre **solo el bloque A** de los dos que aparecieron
> al diagnosticar "mejorar el plano central": dibujar bien lo que ya se sabe.
> El bloque B —leer muros, huecos y carpintería del DXF— es un cambio de
> producto, no de presentación, y necesita su propio PRD (§14.4). Mezclarlos
> sería prometer un plano de arquitectura entregando un diagrama repintado.

---

## 1. Problema que resuelve

Petición directa de Pablo (2026-08-02): *"ahora quiero mejorar el plano
central, donde se ve el plano"*.

### 1.1 Lo que realmente hay dibujado

`analyzer/parser.py` lee **una única capa del DXF** (`AREA_LAYER = "00 areas"`)
y solo polilíneas cerradas. El `Room` resultante tiene tres campos: `label`,
`polygon`, `layer`. No hay muros, ni puertas, ni ventanas, ni estructura, ni
cotas — **no es que no se dibujen: no entran en el sistema**.

Lo que en pantalla parece un muro es el borde compartido de dos polígonos de
habitación: una línea de grosor cero entre dos superficies. El lienzo central
no muestra un plano de arquitectura; muestra un **diagrama de superficies**.
Esa es la causa de fondo de que "no acabe de verse bien", y este PRD **no la
resuelve**: la asume y saca el máximo del dato disponible.

### 1.2 Un defecto medido, este sí de presentación

El grosor de línea **escala con el zoom**, que es lo contrario de lo que hace
cualquier CAD. Medido sobre `ejemplo.dxf`/VT1/3 en el navegador:

| Estado | viewBox | Grosor en pantalla |
|---|---|---|
| Reposo (encuadre) | 644 u | **1,12 px** |
| Zoom ×4 | 161 u | **4,49 px** |
| Zoom ×20 | 32 u | **≈ 22 px** |

`vector-effect` computado: `none`. Consecuencias, las dos malas:

- **En reposo el plano está dibujado con poco más de un píxel**, sin jerarquía
  alguna: fachada y tabique pesan exactamente lo mismo. De ahí la sensación de
  dibujo lavado y sin cuerpo.
- **Al acercarse, los muros se convierten en losas** y a partir de ×10 el
  interior de una habitación pequeña queda comido por su propio contorno.

En AutoCAD el grosor de línea es constante en pantalla y la jerarquía de
grosores es *la* convención que hace legible un plano: se lee el edificio
antes que las particiones. Hoy no existe ninguna de las dos cosas.

### 1.3 Dónde se cambia esto (importa, y de-riesga el trabajo)

El SVG del backend trae `stroke="var(--border)"` y `stroke-width="1.0"`, pero
**la aplicación web los sobrescribe**: `pintarPlano()` (`static/app.js`) fija
`fill`, `stroke` y `strokeWidth` como estilo en línea sobre cada polígono, con
valores distintos por modo (1,4 normal, 1,6 en habitaciones con problema).

Es decir: **casi todo este PRD es frontend, y no toca el informe HTML de la
CLI ni el PDF**, que consumen los atributos propios de `plan_svg.py`. La única
excepción es la envolvente (§5.2), que sí conviene generar en backend para que
el PDF también la aproveche.

## 2. Usuario afectado

El arquitecto que mira el plano — hoy, Pablo. El lienzo es el 61% del ancho de
la ventana y es donde se pasa el tiempo; la especificación de Shell lo resume
como "el plano manda". Es el elemento con más superficie y menos trabajo de
diseño acumulado de toda la aplicación.

En el horizonte de `NORTH_STAR_2031.md` afecta a cualquier salida que enseñe
el dibujo a un tercero (informe a cliente, revisión colegial). Un diagrama de
cajas resta credibilidad a un análisis que por debajo es serio.

## 3. Objetivo de negocio

Credibilidad. `MOAT_ANALYSIS.md` sitúa el foso en el rigor normativo, no en la
interfaz — pero un análisis riguroso presentado sobre un dibujo que no parece
de arquitectura se descuenta antes de leerse. `DESTROY_ARCHMUSE.md` describe
justo ese ataque: el juicio de "esto es un juguete" se emite en los primeros
diez segundos y lo emite el dibujo, no el motor.

Es además el trabajo de mejor relación resultado/coste que queda pendiente:
horas de frontend sobre datos ya calculados, sin tocar el motor de análisis.

## 4. Objetivo técnico

Una vez implementado debe ser cierto que:

1. **El grosor de línea no depende del zoom.** A cualquier nivel de zoom, un
   muro mide lo mismo en píxeles de pantalla.
2. **Existe jerarquía de líneas.** La envolvente de la vivienda se dibuja con
   más peso que las particiones interiores, y se distingue a simple vista sin
   necesidad de acercarse.
3. **El plano tiene referencia métrica**: rejilla en unidades de dibujo que
   acompaña al encuadre, y escala gráfica que se actualiza con el zoom.
4. **Ninguna etiqueta queda tapada** por un marcador numerado ni por otra
   etiqueta.
5. **El informe HTML de la CLI y el PDF siguen generándose igual** salvo por
   la envolvente, que también los mejora.

## 5. Casos de uso

### 5.1 Leer el plano de un vistazo
El arquitecto abre una vivienda y distingue inmediatamente el perímetro
construido de las divisiones interiores, sin acercarse y sin leer etiquetas.

### 5.2 Acercarse a un detalle
Hace zoom ×10 sobre un baño. Las líneas mantienen su peso en pantalla, la
habitación no queda comida por su contorno y el dibujo aguanta la ampliación.

### 5.3 Estimar una medida sin herramienta
Mira la rejilla y la escala gráfica y estima que el pasillo tiene "poco más de
un metro" sin activar coordenadas ni medir. Es la lectura que un arquitecto
hace por defecto sobre papel.

### 5.4 Localizar un problema
Los tres marcadores numerados del informe ejecutivo se ven **y** se sigue
leyendo el nombre y la superficie de la habitación que marcan.

## 6. Casos límite

| Caso | Comportamiento exigido |
|---|---|
| Vivienda de una sola habitación | La envolvente coincide con el único polígono. Se dibuja una vez, no dos superpuestas. |
| Layout `_grid_layout` (viviendas muy dispersas) | Las habitaciones están en posiciones sintéticas: **no hay envolvente real**. Se dibuja el contorno de cada agrupación, nunca uno que sugiera un edificio que no existe. Coherente con no pintar el norte en ese modo. |
| Layout `_compact_clusters` | Varias agrupaciones disjuntas: la unión da un MultiPolygon. Se emite un anillo por agrupación, más los anillos interiores (patios), también con peso de envolvente. |
| Habitación con patio interior | El anillo interior es envolvente, no partición. |
| Zoom extremo (×50) | La rejilla cambia de paso (10 m → 5 m → 1 m) para no convertirse en una mancha ni desaparecer. |
| Plano `data-fiel="0"` | La rejilla sigue siendo válida en **tamaño** pero no en posición absoluta. No se numera ni se rotula con coordenadas; el indicador `COMPACTADO` de la barra de estado ya avisa. |
| Habitación demasiado pequeña para su etiqueta | Ya resuelto por `_text_fits`: la etiqueta se omite. No se cambia. |
| Marcador sobre etiqueta | Nuevo: el marcador se desplaza, la etiqueta nunca. |
| Modo Espacio (color por uso) | Los rellenos por tipo siguen mandando; la jerarquía de líneas se aplica igual encima. |
| `prefers-reduced-motion` | No aplica: aquí no se introduce ninguna animación. |

## 7. Flujo del usuario

No hay flujo nuevo. Todo esto ocurre sin que el usuario pulse nada: abre un
proyecto y el plano está mejor dibujado. La rejilla y la escala gráfica se
suman a las capas ya existentes del panel Análisis (`Rellenos`, `Etiquetas`,
`Norte`), apagables como las demás.

## 8. Criterios de aceptación

**Grosor**

- [ ] Con `vector-effect: non-scaling-stroke`, el grosor medido en píxeles de
      pantalla es el mismo en reposo, a ×4 y a ×20 (tolerancia 0,1 px).
- [ ] Partición 1,0 px; envolvente 2,2 px; habitación con problema conserva su
      realce actual sin romper la jerarquía.

**Jerarquía**

- [ ] Existe un elemento de envolvente distinto de los polígonos de
      habitación, con su propia clase, y no captura eventos de ratón
      (`pointer-events: none`) — no puede robar el clic de selección.
- [ ] En layout de cuadrícula NO se dibuja envolvente global.
- [ ] El PDF y el informe HTML de la CLI muestran también la envolvente.

**Referencia métrica**

- [ ] La rejilla está en unidades de dibujo: se desplaza y escala con el
      encuadre, nunca queda fija respecto a la ventana.
- [ ] El paso cambia entre 10 / 5 / 1 m según el zoom, sin salto brusco.
- [ ] La escala gráfica muestra una medida redonda y se actualiza al hacer
      zoom (reutilizar el algoritmo de `updateScaleBar` de
      `viewer-edificio.js`, que ya resuelve el ajuste a valores redondos).
- [ ] Ambas son capas apagables y su estado se recuerda como el resto.

**Etiquetas**

- [ ] Ningún marcador numerado se superpone a texto en las 6 viviendas de
      `ejemplo.dxf` (hoy el ② tapa la superficie del baño en VT1/3).
- [ ] Nombre y superficie se distinguen tipográficamente entre sí.

**No regresión**

- [ ] Selección de habitación, hover, coordenadas y capas siguen funcionando
      con y sin rellenos (`pointer-events: all` sobre los polígonos sigue
      siendo necesario — ver el bug ya corregido en `63af1bf`).
- [ ] `tests/test_plan_coords.py` sigue en verde: la transformación publicada
      no cambia.

## 9. Riesgos

**R1 — La envolvente puede robar el clic (alto si se descuida).** Un elemento
nuevo encima de las habitaciones rompería la selección, el hover y las
coordenadas. Ya pasó dos veces en este proyecto con las etiquetas y con
`fill:none`. Mitigación: `pointer-events: none` explícito y comprobación
manual en las 6 viviendas.

**R2 — La rejilla ensucia en vez de ayudar (medio).** Una rejilla mal
calibrada convierte el fondo en ruido y compite con el dibujo. Mitigación:
muy poco contraste, paso adaptativo y capa apagable. Si en uso real se apaga
siempre, se retira.

**R3 — Sugerir precisión que no existe (medio).** Una rejilla métrica sobre un
plano `data-fiel="0"` puede leerse como si las posiciones fueran reales. No lo
son. Mitigación: sin coordenadas rotuladas, y `COMPACTADO` ya visible.

**R4 — Compite con `REFACTOR_MASTERPLAN.md` y con dos PRD sin aprobar
(medio).** Están abiertos y sin decisión el desglose de puntuación —con dos
sistemas contradictorios dentro— y la invalidación de caché por versión de
motor. **Ambos son defectos; esto es una mejora.** Si hay que ordenar, los
defectos van antes.

**R5 — Maquillar el diagrama (medio, y es el riesgo de producto).** Cuanto
mejor dibujado esté, más parecerá que hay muros de verdad. Mitigación: nada de
grosores falsos que simulen espesor de muro, ni símbolos de puerta o ventana
inventados. Se dibuja mejor lo que se sabe; no se dibuja lo que no se sabe.

## 10. Impacto sobre módulos existentes

| Módulo | Impacto |
|---|---|
| `static/app.js` — `pintarPlano()` | **Alto.** Es el punto donde hoy se deciden `fill`/`stroke`/`strokeWidth` por modo. |
| `static/app.js` — `wireLienzoCAD`, `zoomExtents` | Medio: rejilla y escala gráfica se actualizan con el encuadre. |
| `static/style.css` | Medio. Sin tokens de color nuevos; `--plan-wall` ya existe. |
| `analyzer/plan_svg.py` | **Bajo pero real:** un elemento de envolvente por agrupación (`unary_union` de los polígonos ya calculados). Nada más. |
| `analyzer/pdf_report.py`, `reporter.py` | Indirecto y positivo: heredan la envolvente. **Verificar que no se rompen.** |
| `analyzer/parser.py` | **Ninguno.** Deliberado: eso es el bloque B. |
| `tests/test_plan_coords.py` | Debe seguir pasando sin cambios. |

## 11. Plan de implementación

Tareas independientes, ≤2 h. Del mayor efecto al menor.

| # | Tarea | Depende |
|---|---|---|
| 1 | `vector-effect: non-scaling-stroke` en polígonos de habitación; recalibrar grosores a píxeles reales. **Es el arreglo con más efecto visible por hora.** | — |
| 2 | Envolvente en `plan_svg.py`: `unary_union` del layout, anillos exteriores e interiores, clase propia, `pointer-events: none`, omitida en layout de cuadrícula. | — |
| 3 | Jerarquía en `pintarPlano()`: envolvente 2,2 px / partición 1,0 px, respetando los realces por modo. | 1, 2 |
| 4 | Verificar PDF e informe HTML de la CLI con la envolvente. | 2 |
| 5 | Tipografía de etiqueta: nombre y superficie diferenciados. | — |
| 6 | Colisión marcador/etiqueta: desplazar el marcador, nunca la etiqueta. | 5 |
| 7 | Rejilla de unidades de dibujo con paso adaptativo 10/5/1 m, como capa apagable. | — |
| 8 | Escala gráfica 2D reutilizando el algoritmo de `updateScaleBar`. | 7 |
| 9 | Actualizar `docs/design/2026-08-01-especificacion-shell.md`. | 3, 8 |

**Las tareas 1-3 son el 80% del resultado.** Si solo hubiera tiempo para una
tanda, esa.

## 12. Plan de pruebas

**Automático**

- Nuevo `tests/test_plan_envolvente.py`: para las 6 viviendas de
  `ejemplo.dxf`, la envolvente existe cuando el layout no es de cuadrícula, y
  la suma de sus anillos encierra todos los polígonos de habitación.
- `tests/test_plan_coords.py` sin cambios y en verde.
- `tests/test_storage.py` en verde.
- Golden master `tests/fixtures/ejemplo-dxf-analisis.json`: **cambia** (el SVG
  lleva un elemento nuevo). Recapturar y revisar el diff a mano.

**Manual, en navegador**

- Medir el grosor en píxeles a ×1, ×4 y ×20: mismo valor.
- Recorrer las 6 viviendas: ningún marcador tapa texto.
- Con y sin rellenos: selección, hover y coordenadas siguen vivas.
- Modos Espacio, Luz, Problemas y Normativa: la jerarquía sobrevive a los
  realces.
- Generar el PDF y abrir el informe HTML de la CLI.

## 13. Métricas para medir el éxito

Con un usuario, métricas de producto verificables a mano:

1. **Grosor constante (binaria).** Hoy varía ×20 con el zoom. Objetivo: no
   varía.
2. **¿Se distingue la envolvente a tamaño de miniatura?** Si en la tarjeta del
   Inicio se lee el perímetro de la vivienda, la jerarquía funciona.
3. **¿Pablo deja la rejilla encendida?** A las dos semanas. Si la apaga
   siempre, sobra y se retira — igual que el criterio del PRD del desglose.
4. **Anti-métrica.** Si el paneo o el zoom pierden fluidez, el cambio ha
   fracasado. La rejilla es lo primero que se sacrifica.

## 14. Posibles motivos para NO implementar la idea

### 14.1 Estamos puliendo el síntoma

El motivo real de que el plano no parezca un plano es que **no hay un plano en
memoria**, solo superficies. Cabe defender que las horas van mejor a leer el
DXF de verdad (bloque B) que a dibujar mejor las cajas. Contraargumento, y por
eso el PRD sigue: B es semanas y toca el motor; A son horas, no toca el motor,
y el defecto de la §1.2 es un defecto real que no depende de B.

### 14.2 La rejilla puede sobrar

Es lo más discutible del documento. En AutoCAD la rejilla sirve para
**dibujar**; aquí no se dibuja, se revisa. Una rejilla que solo aporta
ambientación CAD es ruido con coartada. Recomendación: implementarla
**apagada por defecto** y decidir con uso real. Si esto se recorta, se recorta
por aquí (tareas 7-8), no por las 1-3.

### 14.3 Hay defectos por delante de esto

Sin resolver, ambos ya documentados: las dos puntuaciones contradictorias
(`docs/prd/2026-08-02-desglose-de-puntuacion-desplegable.md` §1.2) y la
invalidación de caché por versión de motor, que ya provocó servir un SVG
obsoleto esta semana. **Un plano bonito con una nota mal calculada sigue
teniendo la nota mal calculada.** Si hay que elegir, esos van antes.

### 14.4 El bloque B, dicho en claro para que no se pierda

Leer del DXF los muros (espesor real), los huecos (puertas y ventanas) y la
carpintería no es un PRD de presentación: es lo que separa un diagrama de un
plano. Y tiene consecuencia analítica directa, no solo estética — hoy el
motor evalúa itinerarios accesibles de ≥1,20 m y giros de baño **sin haber
visto una sola puerta**, y estima el factor de luz natural **sin haber visto
una sola ventana**. Ahí hay una cuestión de foso, no de dibujo. Merece su PRD
y su discusión, y no debe colarse dentro de este.

### 14.5 Otra vez, el argumento del uso real

Sigue en pie lo dicho tres veces: la especificación de Shell va por la v4 en
48 horas y ninguna versión ha sobrevivido a un uso real. Matiz idéntico al del
PRD anterior: **las tareas 1-3 no son cuestión de gusto.** Que el grosor de
línea se multiplique por veinte con el zoom es un defecto, y no mejora
esperando. Las 5-8 sí pueden esperar a que uses la herramienta unos días.

---

**Decisión:** _pendiente de revisión por Pablo_
