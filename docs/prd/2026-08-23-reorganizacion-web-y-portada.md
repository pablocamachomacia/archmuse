# PRD — Reorganización de la web y portada de ArchMuse

**Estado:** Borrador · **Parcialmente aprobado: solo el §15** · **Fecha:** 2026-08-23 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-23), **únicamente el alcance acotado del §15**

> **Decisión de Pablo (2026-08-23), que fija el estado de este documento:**
> se aprueba **escribirlo**, no ejecutarlo. La reorganización completa (las 6
> páginas y la portada) queda **en cola detrás de (1) cerrar V1 y (2) la
> validación con arquitectos**.
>
> **Excepción aprobada el mismo día: el §15** — una barra de navegación
> mínima para poder moverse entre lo que ya existe, pedida para preparar una
> demo. Media jornada, pendiente de arrancar.
>
> **Precisión sobre la congelación (2026-08-23).** La congelación **existe y
> está documentada**, en `docs/prd/2026-08-22-contraste-superficies-memoria-vs-plano.md`
> (gate de arranque y §R-3): alcanza a **`analyzer/`, `scripts/` y
> `tests/fixtures/`** —no al repositorio entero— y llega **hasta el jueves
> 2026-08-28**. Su motivo es competencia por tiempo: la semana del 25 está
> tomada por la validación del corpus (lunes 25 y martes 26).
>
> Eso **no afecta al §15**, cuyo alcance son `static/`, `app.py` y
> `tests/test_rutas_paginas.py`, todos fuera de los tres directorios
> congelados. La fecha del 28 que figuraba antes en este párrafo se había
> copiado por asociación, no porque el §15 dependiera de ella.
>
> **Todo lo demás de este PRD sigue sin aprobar**, incluido el arreglo del
> error `credit balance too low` (§10, tarea 8): documentado, sin implementar.
> Quien ejecute el §15 no debe tocar nada fuera de su tabla.

---

## 1. Problema que resuelve

La web de ArchMuse está apelotonada en dos sitios y ninguno explica qué hace
el producto.

- **`/` abre el panel de conversación** desde el 2026-08-19, por petición
  directa de Pablo (documentado en el docstring de `app.py::index`: el usuario
  no encontraba el botón «Preguntar a ArchMuse» dentro del ribbon). El
  resultado es que la primera pantalla de ArchMuse es un cuadro de texto
  vacío, y **la conversación necesita `ANTHROPIC_API_KEY`**: sin clave, la
  puerta de entrada del producto no hace nada.
- **`/mvp` mete siete pestañas en una pantalla** (Alternativas, Distribución,
  Análisis, Normativa, Costes, Exportar) que mezclan lo determinista con lo
  generativo y lo que aún no existe.
- **La función principal —medir un DXF y sacar el cuadro de superficies— está
  enterrada.** Es determinista, no necesita clave de API, es lo único que
  `docs/AGENTE_BACKLOG.md` da por `HECHO` (`OP-15`, `OP-16`) y no tiene página
  propia. Un arquitecto que abre ArchMuse no encuentra lo único que ArchMuse
  sabe hacer bien.
- **Los errores de la IA se filtran crudos.** Con clave presente pero sin
  crédito, `analyzer/ai_generator.py:831` interpola el `str(exc)` de Anthropic
  y el arquitecto ve `credit balance too low` en su pantalla. Existe ya una
  degradación correcta para el caso de *falta de clave*
  (`codigo: "ia_no_disponible"`, 503, mensaje en castellano — `app.py:2855` y
  `:3432`), pero **no se aplica al caso de la API que falla**.

## 2. Usuario afectado

El arquitecto que abre ArchMuse por primera vez —el primer lector en la
demo, y cualquier arquitecto de la validación pendiente—, en los primeros
diez segundos, antes de saber qué es esto. Y Pablo, cada vez que enseña el
producto y tiene que explicar por dónde se empieza.

## 3. Objetivo de negocio

Que la primera pantalla de ArchMuse comunique en una frase qué hace y lleve a
la acción, con lo determinista delante y lo que depende de IA detrás y
etiquetado. Es condición previa de la validación con arquitectos: enseñar hoy
`/` a un arquitecto obliga a pedirle disculpas antes de empezar.

No es un objetivo comercial: **esta portada no vende, pone a trabajar**. Sin
precios, sin login, sin captura de correo (decisión de Pablo, 2026-08-23).

## 4. Objetivo técnico

1. Seis rutas de página con una función clara cada una, y una navegación que
   se ve entera de un vistazo.
2. **Cero regresión sobre lo que funciona**: el motor de medición, las ~15
   rutas `/api/*` y la SPA actual (`static/app.js`, 7.013 líneas) quedan
   intactos. Las páginas nuevas *envuelven*, no reescriben.
3. Ningún error de la API de Anthropic llega al usuario en su texto original.
   Todos degradan al contrato `ia_no_disponible` que ya existe.
4. El código nuevo nace separado: plantillas Jinja con componentes
   reutilizables, hojas de estilo por página, módulos JS de una función. Nada
   entra en `app.js` ni en `style.css` (salvo una línea de `@import`).

## 5. Casos de uso

- **CU-1 — Primer contacto.** Un arquitecto abre `http://localhost:5000`, lee
  en una frase qué hace ArchMuse, arrastra su DXF a la zona de subida que ya
  está en pantalla, y ve la medición. Sin clave de API en ningún momento.
- **CU-2 — Trabajo recurrente.** Pablo va directo a `/analizar`, sube un
  plano, descarga el cuadro. La portada es un paso que se salta.
- **CU-3 — Memoria.** Desde una medición hecha, `/memoria` genera y descarga
  la memoria de superficies (`/api/memoria-superficies`, ya implementada).
- **CU-4 — Función de IA sin clave.** El usuario entra en Copiloto: la
  navegación ya mostraba la etiqueta `requiere IA`, y la página explica qué
  falta y qué sí funciona sin ella. Nunca un error crudo.
- **CU-5 — Función de IA con clave sin crédito.** Mismo aviso sereno que
  CU-4, no `credit balance too low`.

## 6. Casos límite

- **DXF que ArchMuse no sabe leer** (capa indeterminada, escala indeterminada,
  o el caso de rótulos sin recintos del PRD
  `2026-08-23-deteccion-asistida-de-convenciones-de-capas.md`): la página de
  análisis debe mostrar el diagnóstico existente, no un error genérico. Las
  dos excepciones ya traen el mensaje redactado (`parser.CapaIndeterminada`,
  `EscalaIndeterminada`).
- **Fichero que no es DXF, o mayor de 25 MB** (`app.py` corta ahí): rechazo
  claro en la propia zona de subida, antes de subir.
- **Sin proyectos guardados:** la portada no enseña una parrilla vacía.
- **Navegador sin JS:** la portada debe seguir leyéndose y la nav funcionando;
  solo la zona de arrastre deja de arrastrar (queda el `<input type=file>`).
- **La SPA y las páginas nuevas comparten tokens CSS**: un cambio en los
  tokens afecta a las dos. Es deseado, y por eso el `:root` se extrae a un
  único fichero en vez de duplicarse.

## 7. Flujo del usuario

| Ruta | Página | Estado |
|---|---|---|
| `/` | **Inicio** — landing con zona de subida real | NUEVA |
| `/analizar` | **Analizar** — DXF → medición → cuadro → acta | NUEVA (envuelve API existente) |
| `/memoria` | **Memoria** — genera y descarga la memoria | NUEVA (envuelve API existente) |
| `/proyectos` | **Proyectos** — la SPA actual | EXISTENTE, sin tocar |
| `/copiloto` | **Copiloto** — la conversación que hoy vive en `/` | EXISTENTE, ruta nueva |
| `/mvp` | **Alternativas** — vista de tres zonas | EXISTENTE, sin tocar |

Navegación: `ArchMuse · Analizar · Memoria · Proyectos` a la izquierda; a la
derecha «Herramientas avanzadas ↗» con Copiloto y Alternativas, ambos con
etiqueta `requiere IA` cuando no hay clave. **Aparcado significa accesible y
honesto, no escondido.**

**Estructura de la portada** (boceto completo en el plan de sesión; modo
*Persuade* de app local — la acción va en el primer viewport porque el
producto ya está instalado, no hay desconfianza que vencer):

1. Hero: eyebrow `MEDICIÓN DETERMINISTA · SIN IA`, titular a dos líneas
   («Del DXF al cuadro de superficies. / Sin teclear una cifra.»), subtítulo,
   **zona de arrastre**, y un enlace secundario a un acta de ejemplo.
2. Banda de evidencia: filas reales de un acta, incluida la que más vende —
   `VT2 · total — sin total: dos recintos se solapan 4,00 m²`.
3. Cómo funciona, en tres pasos sin nombres inventados de producto.
4. **«Y te dice qué no ha comprobado»** — la sección firma, y el equivalente
   honesto del descargo de responsabilidad de la competencia.
5. Pie sobrio: corre en tu ordenador, no modifica tu DXF (sha256).

**Regla de copy, vinculante:** ninguna cifra de la portada puede ser
inventada. La banda de evidencia se genera de una medición real, no se
escribe a mano. Es el §1 de `CLAUDE.md` aplicado a la página de marketing.

**Dirección visual: heredar, no inventar.** ArchMuse tiene un mundo visual
establecido y deliberado, documentado en los comentarios de `static/style.css`
(fondo `#0a0a0c`, acento azul desaturado único `#4A90D9` nunca decorativo,
botón primario blanco sobre negro, vidrio esmerilado, Inter, separadores de
1px), con decisiones de Pablo revertidas y re-aplicadas el mismo día. Las
páginas nuevas viven dentro de ese mundo; no se abre una paleta nueva.

## 8. Criterios de aceptación

1. Las 6 rutas responden 200 y sirven cada una su plantilla.
2. **`/proyectos` y `/mvp` se ven exactamente igual que antes del cambio**,
   comparado contra capturas tomadas antes de empezar.
3. Subir `V5.dxf` desde `/analizar` da la misma medición y la misma acta que
   `python scripts/medir_planta.py V5.dxf`.
4. Con `ANTHROPIC_API_KEY` ausente **y** con clave inválida o sin crédito,
   ninguna pantalla muestra texto de Anthropic sin traducir; ambas muestran
   el aviso de `ia_no_disponible`.
5. La portada se lee y la navegación funciona con JavaScript desactivado.
6. Ninguna cifra de la portada carece de origen en una medición real.
7. La suite completa sin regresiones nuevas (línea base: 1073 passed,
   2 failed — los guardianes conocidos de C4).

## 9. Riesgos

- **Extraer el bloque `:root` de `style.css`** es el único cambio sobre CSS
  que ya funciona. Mitigación: se hace solo, se verifica que la SPA renderiza
  idéntica, y se revierte en una línea si falla.
- **Cambiar `/` deroga una petición explícita anterior de Pablo** (2026-08-19,
  «/ abre la conversación»). Mitigación: la conversación no desaparece, se
  muda a `/copiloto`; queda registrado aquí y en la v5 de la shell.
- **Es el quinto paradigma de navegación del proyecto.** Ver §14.
- **La portada puede prometer de más.** Mitigación: la regla de copy del §7.
- **Compite por tiempo con cerrar V1** — y por eso Pablo lo ha puesto en cola.

## 10. Impacto sobre módulos existentes

**Nuevos (nada de esto toca código que funciona):** `templates/base.html`,
`templates/_nav.html`, `templates/_pie.html`, `templates/inicio.html`,
`templates/analizar.html`, `templates/memoria.html`; `static/css/tokens.css`,
`static/css/base.css`, `static/css/paginas/{inicio,analizar,memoria}.css`;
`static/js/{subida,cuadro,ia-no-disponible}.js`; `analyzer/errores_ia.py`;
`tests/test_rutas_paginas.py`, `tests/test_errores_ia.py`.

**Modificados, y solo esto:**
- `static/style.css` — **una línea**: `@import url("css/tokens.css");` arriba,
  y se borra el `:root` recién extraído. Las ~200 reglas que consumen los
  tokens no se tocan.
- `app.py` — 3 rutas nuevas con `render_template`, `/` deja de servir
  `index.html`, `/copiloto` nueva. Ninguna ruta `/api/*` se toca.
- `analyzer/ai_generator.py:831` y `analyzer/ai_analyst.py:296` — dejan de
  interpolar `{exc}` crudo y llaman al traductor nuevo.

**Intactos:** todo `analyzer/` salvo esas dos líneas, todo `agente/`, todo
`modelo/`, `normativa/`, `bim/`, `static/app.js`, `static/mvp.js`, los
visores, la entrevista, y las ~15 rutas `/api/*`.

## 11. Plan de implementación dividido en pequeñas tareas

Nada empieza sin luz verde de Pablo. Total estimado: **4 jornadas**.

| Fase | # | Tarea | Est. |
|---|---|---|---|
| 0 | 1 | Este PRD + v5 de la especificación de shell | 0,5 j |
| 1 | 2 | Extraer `:root` a `static/css/tokens.css` + `@import` en `style.css`. Verificar que la SPA renderiza idéntica. | 0,25 j |
| 1 | 3 | `templates/base.html` + `_nav.html` + `_pie.html` + `static/css/base.css` | 0,25 j |
| 2 | 4 | `inicio.html` + su CSS + `static/js/subida.js` | 1 j |
| 2 | 5 | `analizar.html` + su CSS + `static/js/cuadro.js` | 0,75 j |
| 2 | 6 | `memoria.html` + su CSS | 0,25 j |
| 3 | 7 | Rutas en `app.py` (3 nuevas, `/` cambia, `/copiloto` nueva) | 0,25 j |
| 3 | 8 | `analyzer/errores_ia.py` + los 2 puntos de llamada + `ia-no-disponible.js` | 0,25 j |
| 4 | 9 | `test_rutas_paginas.py` + `test_errores_ia.py` + recorrido visual de las 6 rutas | 0,5 j |

La tarea 8 es la única que podría ir suelta y antes que el resto (arregla un
defecto visible hoy). **Pablo ha decidido que no vaya suelta**: queda en cola
con todo lo demás.

## 12. Plan de pruebas

- `tests/test_rutas_paginas.py` — las 6 rutas: 200 y plantilla correcta.
- `tests/test_errores_ia.py` — cada tipo de `anthropic.APIError` (crédito
  agotado, clave inválida, límite de tasa, timeout) produce
  `codigo: "ia_no_disponible"`, y **ningún** mensaje contiene el texto crudo
  de la excepción. Test negativo explícito, no solo positivo.
- **Guardián visual**: capturas de `/proyectos` y `/mvp` antes y después,
  comparadas a ojo. Sin esto la tarea 2 es imprudente.
- Recorrido end-to-end en navegador con `V5.dxf` real.
- Suite completa contra la línea base conocida.

## 13. Métricas para medir el éxito

- **La que importa:** un arquitecto que nunca ha visto ArchMuse llega a su
  primera medición sin que Pablo le explique nada. Se mide en la validación
  con arquitectos, observando, no preguntando.
- Cero pantallas con texto de error de Anthropic sin traducir.
- Segundos desde abrir `/` hasta soltar un DXF. Si pasa de treinta, la
  portada está mal escrita.

## 14. Posibles motivos para NO implementar la idea

**a) Es el quinto paradigma de navegación en tres semanas.** v2 barra
superior → v3 sidebar lateral → v4 workspace tipo AutoCAD → 2026-08-19 «/ es
la conversación» → esto. El PRD `2026-08-02-workspace-tipo-autocad.md` §14 ya
dejó escrita una objeción de proceso cuando iba por el tercero. La repito sin
suavizarla: **cada rehecho de navegación cuesta jornadas y no añade ninguna
capacidad**, y el patrón sugiere que el problema no es la navegación sino que
todavía no está decidido qué es ArchMuse para el usuario. La decisión de
producto del 2026-08-20 (capa de verificación antes de visado) apunta a que
la respuesta ya existe; si es así, esta reorganización es la primera que puede
durar. Si no, será la quinta que se tira.

**b) La validación con arquitectos podría invalidar la estructura.** Diseñar
seis páginas antes de que ningún arquitecto ajeno haya usado el producto es
diseñar contra una hipótesis. **Éste es el argumento que ha ganado**: Pablo lo
pone en cola detrás de la validación, y es la decisión correcta.

**c) Compite con cerrar V1**, que es la regla nº 1 de ejecución del proyecto
(`[[archmuse-reglas-de-ejecucion]]`: todo se subordina al primer vertical).
4 jornadas de presentación mientras el vertical sigue abierto es exactamente
lo que esa regla prohíbe.

**d) La tarea 8 sí se defiende sola.** Que un arquitecto vea
`credit balance too low` es un defecto de producto vivo hoy, cuesta un cuarto
de jornada y no depende de ninguna decisión de navegación. Si en algún momento
hay una demo a la vista y el resto sigue en cola, **esa tarea debería salir de
la cola sola** — no por este PRD, sino porque es una corrección, no una
capacidad nueva. Queda dicho aquí para que se pueda decidir sin releer todo.

---

## 15. Alcance acotado APROBADO — barra de navegación mínima

**Aprobado por Pablo el 2026-08-23. Pendiente de arrancar.** Es lo único
de este PRD que se implementa; el resto sigue en cola. *(La fecha
«2026-08-28» que aparecía aquí venía de una congelación del repositorio que
no existía — ver la corrección de la cabecera.)*

**Qué pidió, literal:** poder moverse de un clic entre la portada, `/mvp` y la
pantalla de subir DXF, sin escribir URLs a mano, y que quede claro cuál es la
pantalla «para enseñar» en la demo al primer lector. **No** rediseñar nada, **no**
tocar la SPA por dentro, ni el visor, ni el chat.

### Los tres hallazgos que condicionan el trabajo

1. **La pantalla de la demo no tiene URL.** La SPA no tiene enrutado por hash
   ni `pushState`: las vistas son funciones que pintan en `#view-root`.
   «Subir DXF» es `renderUpload()` (`static/app.js:541`) y hoy solo se alcanza
   por el desplegable «Nuevo» del sidebar (acción `nuevo-analizar`,
   `app.js:4858`). Sin una ruta nueva, ningún menú puede enlazarla.
2. **`static/mvp.html` no usa `style.css`** — lleva su propio `<style>`
   incrustado con otros tokens (`--tenue`). Por eso `nav.css` debe ser
   autónomo (valores propios con *fallback*). **`/mvp` seguirá teniendo otro
   aspecto que la SPA**: unificarlo no cabe en media jornada y queda fuera.
3. **`#app` es `height:100vh; display:flex; row`** (`style.css:237`). Una
   barra superior obliga a un cambio quirúrgico de esa línea — la única
   edición sobre CSS que ya funciona.

### Tareas (~4 h en total)

| # | Tarea | Est. |
|---|---|---|
| N1 | `static/css/nav.css` **nuevo**, autónomo, con los tokens actuales (negro/azul) y valores de reserva para `mvp.html`. Ninguna paleta nueva. | 1 h |
| N2 | Insertar el mismo bloque `<nav>` (~12 líneas) en `static/index.html` y `static/mvp.html` | 0,5 h |
| N3 | `static/style.css:237` → `height: calc(100vh - var(--nav-h, 0px))`. Inocuo donde no hay barra. Verificar que la SPA renderiza idéntica. | 0,5 h |
| N4 | Ruta `/subir` en `app.py` (~5 líneas) **+ 3 líneas en el arranque de `static/app.js`**, ampliando el `if (window.location.pathname === "/")` que ya existe (~línea 6961) con un `else if` que llame a `renderUpload()`. **Aprobado explícitamente por Pablo pese a la regla de no tocar la SPA**: son 3 líneas en el bloque de arranque, sobre un `switch` por `pathname` que ya está escrito ahí, reutilizando `renderUpload()` tal cual. Ninguna vista se reescribe. | 0,5 h |
| N5 | Verificación en navegador: los 4 enlaces, y capturas de `/proyectos` y `/mvp` comparadas contra las de la sesión del 2026-08-23 | 1 h |
| N6 | `tests/test_rutas_paginas.py` mínimo: `/`, `/subir`, `/proyectos`, `/mvp` responden 200 | 0,5 h |

### El menú

`ArchMuse · Subir plano · Proyectos · Alternativas`, con **«Subir plano» como
acción principal** (el botón blanco sobre negro que ya existe en los tokens:
`--btn-primary-bg`). Eso resuelve el segundo requisito: la pantalla de la
demo se ve como *la* acción, no como una opción más de la lista.

### Fuera de este alcance, explícitamente

La portada/landing, las páginas `/analizar` y `/memoria`, las plantillas
Jinja, `analyzer/errores_ia.py`, y cualquier cambio en el aspecto de la SPA o
de `/mvp`. Si al ejecutar aparece la tentación de arreglar algo de eso «ya que
estamos», **no**: se anota y se decide aparte.

### Criterios de aceptación del §15

1. Desde cualquiera de las cuatro pantallas se llega a las otras tres con un
   clic, sin escribir URLs.
2. `/subir` abre directamente la pantalla de subir DXF.
3. `/proyectos` y `/mvp` se ven **exactamente igual** que antes, salvo la
   barra añadida — comparado contra capturas.
4. La suite completa sin regresiones nuevas (línea base: 1073 passed,
   2 failed, los guardianes conocidos de C4).

---

**Decisión (2026-08-23):** el **§15 queda aprobado** y pendiente de arrancar.
El resto del PRD —las 6 páginas, la portada y el arreglo de los errores de
IA— sigue **en cola** hasta que Pablo dé luz verde, después de cerrar V1 y de
la validación con arquitectos.
