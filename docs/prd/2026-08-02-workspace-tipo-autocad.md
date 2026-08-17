# PRD — Workspace tipo AutoCAD

**Estado:** Borrador · **Fecha:** 2026-08-02 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

> **Alcance acotado por Pablo:** "el inicio lo dejamos así". El Inicio (parrilla de proyectos) y el sidebar lateral, entregados hoy en `a4ba005`, **no se tocan**. Todo lo que sigue ocurre al entrar en un proyecto.
>
> Esto implica una **v4 de `docs/design/2026-08-01-especificacion-shell.md`**, que hoy va por la v3. Ver §14: es el tercer paradigma de navegación en tres días y tengo una objeción de proceso que quiero dejar escrita, aunque la decisión ya esté tomada.

**Decisiones de Pablo (2026-08-02):**

| # | Decisión |
|---|---|
| 1 | **Shell completa de AutoCAD** dentro del proyecto: ribbon, línea de comandos y pestañas Modelo/Presentación. |
| 2 | **Gris en reposo**, color solo donde el modo lo usa como dato (mantiene la decisión 3 de la Shell). |
| 3 | Los **cuatro** elementos concretos: paneo/zoom al cursor/zoom extents, crosshair + coordenadas + barra de estado, panel de capas de análisis, y línea de comandos. |

---

## 1. Problema que resuelve

El workspace de ArchMuse se manipula como una página web: la rueda hace zoom centrado y topado a 3×, y **no hay paneo en absoluto** (`wireZoom`, `app.js:2032` — un único listener de `wheel` que escribe `transform: scale()`). Un arquitecto que lleva veinte años en AutoCAD intenta arrastrar con el botón central el primer minuto y no pasa nada. Esa fricción no es estética: es la señal de que la herramienta no es de los suyos.

Al mismo tiempo, el plano compite visualmente con la interfaz en los modos que colorean por relleno, y las miniaturas del Inicio salen a todo color mientras el resto del producto es una escala de grises industrial.

El objetivo es que el arquitecto entre en un proyecto y reconozca el entorno: plano técnico monocromo, navegación CAD, coordenadas reales, capas que se encienden y apagan, y las acciones al alcance de la mano donde espera encontrarlas.

## 2. Usuario afectado

El arquitecto que usa AutoCAD a diario — es decir, prácticamente todo el mercado objetivo de ArchMuse en España. No es un usuario nuevo: es el mismo de siempre, cuyo modelo mental de "manipular un plano" está formado por AutoCAD y no por Google Maps.

No afecta a quien solo mira el informe: el diagnóstico, el inspector y la exportación no cambian de contenido.

## 3. Objetivo de negocio

1. **Credibilidad profesional.** `DESTROY_ARCHMUSE.md` señala que el ataque más plausible contra ArchMuse es "parece un juguete web al lado de las herramientas que ya usa el estudio". Un lienzo que se maneja como CAD es la respuesta más directa y barata a ese ataque.
2. **Reducir el tiempo hasta la primera lectura útil del plano.** Sin paneo, revisar una vivienda grande obliga a zooms sucesivos y torpes.
3. **Coherencia con la visión.** `NORTH_STAR_2031.md` apunta a BIM/IFC. Cuanto antes el lienzo se comporte como una herramienta técnica, menos tendrá que reaprender el usuario cuando el modelo debajo cambie.

## 4. Objetivo técnico

Una vez implementado debe ser cierto que:

- El plano se **panea** (botón central o barra espaciadora), el zoom **se ancla al cursor**, y existe un **zoom extents** que reencuadra el plano completo.
- Hay una lectura continua de **coordenadas en metros reales** del plano bajo el cursor.
- Las superposiciones de análisis se encienden y apagan **individualmente** desde un panel de capas.
- Existe una **línea de comandos** que ejecuta acciones reales de ArchMuse, con alias al estilo AutoCAD.
- El plano está en **gris en reposo** en todo el producto, incluidas las miniaturas del Inicio.
- **Ningún control del ribbon, de la barra de estado ni de las pestañas está vacío o deshabilitado permanentemente.** Es la regla que ya costó eliminar `Herramientas` y `Cuenta`; se aplica igual aquí.
- El Inicio, el sidebar y el inspector siguen funcionando exactamente como hoy.

## 5. Casos de uso

**CU-1 — Navegar el plano como en AutoCAD.** Abre una vivienda, arrastra con el botón central para desplazarse, gira la rueda apuntando a un baño y el zoom entra hacia ese baño, no hacia el centro. Pulsa el botón de encuadre y vuelve al plano completo.

**CU-2 — Medir de un vistazo.** Pasa el cursor por una esquina y lee `12.480, 8.320` en la barra de estado. No necesita abrir nada.

**CU-3 — Aislar una lectura.** Apaga las capas de circulación y calidad espacial para quedarse solo con los problemas normativos sobre el plano limpio.

**CU-4 — Ir por teclado.** Escribe `ZE` y el plano se encuadra. Escribe `PROBLEMAS` y salta a ese modo. Sin soltar el teclado.

**CU-5 — Del plano al 3D.** Cambia de la pestaña `Modelo` a la pestaña `3D` y aparece el visor que ya existe, sin salir del proyecto.

## 6. Casos límite

- **Ratón sin botón central** (portátil, trackpad): el paneo debe tener una segunda vía — barra espaciadora + arrastre, y arrastre con botón izquierdo sobre zona vacía. Un solo gesto sería excluyente.
- **Paneo frente a selección de habitación**: hoy el click izquierdo sobre una habitación la selecciona (`wireRoomSelection`). El paneo no puede robar ese gesto: botón central e izquierdo tienen que convivir sin ambigüedad.
- **Coordenadas fuera del plano**: el cursor sobre zona vacía del lienzo sigue teniendo coordenada válida (el espacio del plano es infinito); no mostrar `--` salvo que el cursor salga del lienzo.
- **Zoom extents sin geometría**: una vivienda sin polígonos dibujables no debe dejar el lienzo en blanco ni lanzar excepción.
- **Comando desconocido**: responder como AutoCAD (`Comando desconocido "XYZ"`), no en silencio y no con un error de aplicación.
- **La línea de comandos captura el teclado**: hoy `1`…`6` cambian de modo y `Escape` suelta el foco. Con el cursor dentro de la caja de comandos, esos atajos **no** deben dispararse.
- **Capa apagada y problema seleccionado**: si el usuario apaga la capa de problemas mientras tiene uno con foco, hay que decidir — recomiendo que apagar la capa suelte el foco, no que el foco fuerce la capa encendida.
- **Modo y capa en conflicto**: los 6 modos ya deciden qué se pinta. Un panel de capas encima puede contradecirlos. Es el riesgo de diseño número uno de este PRD (§9).

## 7. Flujo del usuario

1. Abre un proyecto desde el Inicio. El sidebar se colapsa a 48px automáticamente para dejar sitio (ver §14: decisión mía, discutible).
2. Aparece el workspace con ribbon arriba, lienzo con crosshair en el centro, inspector a la derecha, y abajo línea de comandos, pestañas `Modelo`/`3D` y barra de estado.
3. Panea, hace zoom al cursor, encuadra.
4. Enciende y apaga capas desde el ribbon o el panel de capas.
5. Escribe comandos si prefiere el teclado.
6. Vuelve al Inicio expandiendo el sidebar y pulsando `Inicio`.

**Distribución propuesta:**

```
┌────┬────────────────────────────────────────────────────┬──────────┐
│    │ Vista │ Análisis │ Salida            ← RIBBON      │          │
│ S  ├────────────────────────────────────────────────────┤          │
│ I  │ [Resumen][Espacio][Luz][Normativa][Problemas][IA]  │ INSPEC-  │
│ D  ├────────────────────────────────────────────────────┤ TOR      │
│ E  │                     ┼                              │          │
│ B  │              ╔══════════════╗                      │ (sin     │
│ A  │              ║              ║                      │ cambios) │
│ R  │              ╚══════════════╝                      │          │
│    ├────────────────────────────────────────────────────┤          │
│48px│ Comando:                                           │          │
│    ├──────────┬─────────────────────────────────────────┴──────────┤
│    │ Modelo│3D│ 12.480, 8.320 m    REJILLA  CAPAS  ORTO            │
└────┴──────────┴────────────────────────────────────────────────────┘
```

## 8. Criterios de aceptación

1. El paneo funciona con botón central **y** con barra espaciadora + arrastre, sin interferir con la selección de habitación por click izquierdo.
2. El zoom con rueda mantiene fijo el punto del plano bajo el cursor.
3. Existe zoom extents, accesible desde el ribbon, desde un comando y con doble click en zona vacía.
4. Las coordenadas mostradas coinciden con las del DXF en metros, verificable contra un vértice conocido de `ejemplo.dxf`.
5. Cada capa de análisis se enciende y apaga por separado y el plano lo refleja al instante.
6. Todo comando de la línea de comandos ejecuta una acción que **ya existe** en el producto; no hay comandos declarativos ni "próximamente".
7. Con el foco en la línea de comandos, `1`…`6` escriben texto y no cambian de modo.
8. El plano está en gris en reposo, y las miniaturas del Inicio también.
9. Ninguna pestaña del ribbon está vacía y ningún control queda deshabilitado de forma permanente.
10. Inicio, sidebar, inspector, exportación PDF/CSV y ambos visores 3D siguen funcionando igual que antes del cambio.
11. El sidebar sigue sin remontarse al navegar (propiedad ya verificada en `a4ba005`).

## 9. Riesgos

- **Modos y capas compiten por la misma responsabilidad.** Los 6 modos ya deciden qué se pinta sobre el plano; un panel de capas hace lo mismo desde otro sitio. Si ambos existen sin una jerarquía explícita, el usuario podrá poner el sistema en estados contradictorios ("modo Problemas con la capa de problemas apagada") y no habrá respuesta correcta. **Mitigación propuesta: el modo fija un preset de capas y el panel permite desviarse de él; el indicador de modo muestra que está modificado.** Hay que resolverlo en diseño antes de escribir código.
- **Ribbon vacío.** AutoCAD tiene siete pestañas porque tiene cientos de comandos de dibujo. ArchMuse tiene seis modos, dos exportaciones y un visor. Un ribbon fiel a AutoCAD estaría casi vacío, y un ribbon casi vacío es peor que ninguno. **Por eso este PRD propone tres pestañas reales (Vista, Análisis, Salida) y no siete.**
- **Pestañas Modelo/Presentación sin presentaciones.** ArchMuse no traza láminas ni tiene layouts. Reproducirlas literalmente sería decorado. **Propuesta: la tira de pestañas existe pero es `Modelo` / `3D`**, que sí son dos representaciones reales del mismo proyecto y hoy conviven mal (el 3D es un botón perdido entre los modos).
- **La línea de comandos es el elemento con más riesgo de quedar en teatro.** Solo se sostiene si el catálogo de comandos es real y descubrible. Un `Comando:` que solo acepta cuatro palabras y falla con todo lo que un usuario de AutoCAD escribiría por instinto (`LINE`, `TRIM`, `OFFSET`) genera más decepción que ausencia.
- **Densidad.** Sidebar + ribbon + modos + inspector + comandos + pestañas + barra de estado sobre un lienzo que ya competía por espacio. En 1440px el lienzo puede bajar del 50% del ancho. Hay que medirlo, no suponerlo.
- **Sin tests de interfaz.** Sigue sin haber ninguno más allá de `tests/test_storage.py` (backend). Todo lo de este PRD es frontend puro sobre `app.js`, que acaba de crecer a 2.546 líneas.

## 10. Impacto sobre módulos existentes

- **`static/app.js`** — el grueso. `wireZoom` se reescribe entero (paneo + zoom al cursor + extents). `wireModebar` pasa a vivir dentro del ribbon. `pintarPlano` incorpora el estado de capas además del modo. Se añaden línea de comandos, barra de estado y pestañas.
- **`static/style.css`** — ribbon, barra de estado, línea de comandos, pestañas, crosshair. Sin tokens de color nuevos: la decisión 3 sigue vigente.
- **`analyzer/plan_svg.py`** — solo si se quieren miniaturas en gris generadas en backend. **Alternativa preferible: dejar el SVG como está y neutralizarlo con CSS en la tarjeta**, que no toca un módulo del que dependen también el informe HTML de la CLI y el PDF.
- **`analyzer/plan_svg.py`, el problema serio (verificado el 2026-08-02).** No es que la conversión píxel → metro sea difícil: **es que no existe**. El SVG que se muestra hoy *miente deliberadamente sobre la posición*:
  - `_compact_clusters` detecta grupos de habitaciones desconectados y **los traslada en bloque** (`translate(room.polygon, xoff=dx, yoff=dy)`) para cerrar los huecos reales del DXF.
  - `_grid_layout` va más lejos: para viviendas muy dispersas **ignora por completo la posición original** y coloca cada habitación en su propia celda de una cuadrícula.
  - El SVG solo expone `data-room`; no publica ninguna de esas transformaciones.

  Las dos cosas están hechas a propósito y por buenas razones (VT6/2 de `ejemplo.dxf` tiene 4 terrazas muy separadas; sin compactar, el plano sería ilegible). Pero significan que **un crosshair con coordenadas del DXF sobre el SVG actual mostraría números falsos** en cualquier vivienda multi-grupo.

  La buena noticia: la geometría real sí llega al frontend. Cada habitación viaja en el JSON con su `poligono` **en metros reales** (`api_serializer._serialize_room`, el mismo campo que ya consume el visor 3D). O sea, el dato está; lo que no está es la correspondencia con lo dibujado.

  Tres salidas, en orden de fidelidad creciente y de coste creciente (§14):
  1. Mostrar coordenadas **del dibujo**, no del DXF. Barato y honesto, pero no es lo que un usuario de AutoCAD entiende por coordenadas.
  2. **Publicar la transformación por habitación** en el SVG (`data-dx`, `data-dy`, escala global) e invertirla en el frontend. Coste medio, coordenadas reales, y el plano sigue siendo legible.
  3. **Dibujar el plano en el frontend desde `poligono`**, a coordenadas reales, como haría AutoCAD. Máxima fidelidad, y de paso el zoom deja de ser `transform: scale()`. Coste alto y se pierde la compactación que hace legibles las viviendas dispersas.

- **`analyzer/parser.py`** — sin cambios.
- **`static/viewer-*.js`** — sin cambios internos; solo cambia desde dónde se invocan (pestaña `3D` en vez de botón en la barra de modos).
- **`docs/design/…-especificacion-shell.md`** — a **v4**. §2.1, §3, §5, §7 y §9.3 quedan afectados.
- **Inicio, sidebar, storage, endpoints** — sin cambios.

## 11. Plan de implementación dividido en pequeñas tareas

1. **Elegir entre las tres salidas de §10** al conflicto entre el plano legible y el plano fiel. Es una decisión de producto, no técnica, y condiciona las tareas 4, 5 y 11. **No se escribe código hasta que esté tomada.**
2. **Decidir y documentar la jerarquía modo ↔ capas** (§9). Diseño, no código.
3. **Especificación de Shell a v4**, con lo decidido en 1 y 2.
4. **Navegación CAD**: paneo (dos vías), zoom al cursor, zoom extents. Entregable útil por sí solo.
5. **Crosshair + coordenadas + barra de estado.**
6. **Panel de capas de análisis**, con el preset por modo de la tarea 2.
7. **Ribbon** con las tres pestañas reales, absorbiendo la barra de modos.
8. **Pestañas `Modelo` / `3D`**, absorbiendo el botón 3D.
9. **Línea de comandos** con catálogo real, alias AutoCAD y ayuda descubrible (`?` lista los comandos).
10. **Gris en reposo**: neutralizar miniaturas del Inicio por CSS.
11. **Medición de densidad** a 1440px y 1920px; ajustar si el lienzo baja del 55%.
12. **Repaso de teclado y foco**: la línea de comandos no puede robar `1`…`6` ni `Escape`.

Las tareas 4 y 5 son la mitad que aporta valor real inmediato. Las 7, 8 y 9 son las que más se parecen a AutoCAD y las que más riesgo de decorado tienen.

## 12. Plan de pruebas

- **Coordenadas contra verdad conocida**: comparar la coordenada mostrada con el `poligono` en metros que ya viaja en el JSON, **en una vivienda multi-grupo** (VT6/2 de `ejemplo.dxf`, que es la que dispara la compactación). Una vivienda de un solo grupo pasaría la prueba aunque el problema de §10 siguiera sin resolver.
- **Paneo y zoom**: el punto bajo el cursor no se mueve al hacer zoom (invariante comprobable numéricamente, no a ojo).
- **Zoom extents**: tras panear y ampliar al azar, encuadrar devuelve siempre al mismo encuadre.
- **No regresión de selección**: click izquierdo sobre habitación sigue seleccionando; el paneo no la dispara.
- **Capas**: cada combinación encendido/apagado se refleja en el DOM del SVG.
- **Comandos**: cada comando del catálogo ejecuta su acción; un comando inventado responde con el mensaje de desconocido.
- **Foco de teclado**: con el cursor en la caja de comandos, `1`…`6` no cambian de modo.
- **Golden master de workspace**: reutilizar `tests/fixtures/ejemplo-dxf-analisis.json` interceptando `window.fetch`, como en el cambio anterior, para comprobar que el workspace sigue montando 6 viviendas, SVG, inspector y exportación.

## 13. Métricas para medir el éxito

- **Uso del paneo por sesión de proyecto.** Si es cero, el gesto no se ha descubierto y el problema es de afordancia, no de implementación.
- **Proporción de acciones ejecutadas por comando frente a por ratón.** Es la métrica que dice si la línea de comandos es una herramienta o un adorno. Si se queda por debajo del 5%, sobra.
- **Zooms por minuto.** Debería **bajar** respecto a hoy: con paneo y zoom al cursor hacen falta menos correcciones.
- **Capas modificadas respecto al preset del modo.** Si nadie se desvía nunca, el panel de capas no aporta y los modos bastaban.
- **Contra-métrica: tiempo hasta el primer clic dentro del proyecto.** Si sube, la densidad nueva está costando orientación.

## 14. Posibles motivos para NO implementar la idea

**Mi objeción principal no es al diseño, es al ritmo.** La especificación de Shell ha pasado por v1, v2 (barra superior) y v3 (sidebar) — y la v3 se escribió, implementó y verificó **hoy**, hace unas horas. Este PRD la lleva a v4. El coste no es el código, que es reescribible: es que **ninguna decisión está durando lo suficiente para saber si era buena**. Nadie ha usado todavía el sidebar con un proyecto real durante una semana. Recomiendo formalmente **usar lo entregado hoy antes de sustituirlo**, y traer a la v4 lo que el uso real demuestre que falta. Si aun así quieres avanzar, mi orden preferido es tareas 1-5 (navegación y coordenadas: valor real, riesgo bajo, no derogan nada) y dejar el ribbon, las pestañas y la línea de comandos para cuando el sidebar lleve un tiempo en uso.

**Sobre partes concretas de lo pedido, mi recomendación difiere:**

- **El ribbon de siete pestañas de AutoCAD no es replicable honestamente.** AutoCAD las tiene porque tiene cientos de comandos de dibujo; ArchMuse no dibuja nada. Propongo **tres pestañas con contenido real** (Vista, Análisis, Salida) en vez de siete, cinco de ellas vacías. Un ribbon fiel y vacío sería exactamente el error que acabamos de corregir borrando `Herramientas` y `Cuenta`.
- **Las pestañas Modelo/Presentación no tienen equivalente.** No hay layouts, ni cajetines, ni trazado. Propongo **`Modelo` / `3D`**, que son dos representaciones reales y de paso arreglan que el visor 3D sea hoy un botón descolgado al final de la barra de modos.
- **La línea de comandos solo se sostiene si es honesta.** Un usuario de AutoCAD escribirá `LINE` o `TRIM` en los primeros treinta segundos. La respuesta no puede ser un error genérico: debe decir que ArchMuse analiza y no dibuja, y ofrecer `?` con lo que sí existe. Si no se hace así, este elemento genera más decepción que ausencia.
- **El sidebar dentro del proyecto.** He propuesto en §7 que se colapse solo al entrar. Es una decisión mía y es discutible: contradice en parte que el colapso sea una preferencia del usuario, que es como se implementó hoy. La alternativa es dejarlo expandido y aceptar menos lienzo. **Necesito tu criterio aquí antes de implementar.**
- **El conflicto que no esperaba, y el más importante de este documento: el plano actual miente sobre la posición a propósito** (§10). `_compact_clusters` mueve grupos de habitaciones y `_grid_layout` los recoloca en cuadrícula, ambos para que viviendas dispersas sean legibles. Eso es incompatible con la idea misma de un entorno CAD, donde la posición **es** el dato. No es un detalle de implementación: es una contradicción entre "quiero que se parezca a AutoCAD" y una decisión de diseño anterior que resolvía un problema real. Hay que elegir cuál gana, y elegirlo antes de escribir nada. Mi recomendación es la salida 2 (publicar la transformación e invertirla): conserva la legibilidad, da coordenadas verdaderas y no obliga a reescribir el renderizado.

- **Lo que de verdad te va a cambiar el día a día son las tareas 4 y 5** (paneo, zoom al cursor, extents, coordenadas), no el ribbon. Son también las más baratas y las únicas que no derogan ninguna decisión previa. Si de todo este documento solo se aprueba una cosa, que sea esa.

---

**Decisión:** _pendiente de revisión por Pablo_
