# Reorientación estratégica — ArchMuse hacia un V1 demostrable

**Fecha:** 2026-08-20 · **Estado:** diagnóstico, sin implementar nada · **Encargo:** Pablo, "actúa como director técnico y de producto" · **Regla seguida al escribir esto:** cada afirmación sobre qué existe hoy se ha verificado leyendo código y tests reales de este repositorio el 2026-08-20, no asumido de los documentos estratégicos anteriores — varios de ellos (`PROJECT_AUDIT.md`, `TECH_REVIEW.md`) describen un estado de hace tres semanas que ya no es cierto en varios puntos importantes.

**No se ha tocado código de producto ni se ha hecho commit.** Este documento es el diagnóstico que el propio encargo pidió antes de implementar nada.

---

## 0. Cómo llegar a este diagnóstico sin repetir lo ya escrito

Este proyecto **ya se audita a sí mismo con una disciplina poco común**: `PROJECT_AUDIT.md`, `TECH_REVIEW.md`, `MOAT_ANALYSIS.md`, `DESTROY_ARCHMUSE.md`, `NORTH_STAR_2031.md`, `ROADMAP_VISION_ARQUITECTONICA.md`, `REFACTOR_MASTERPLAN.md` y el ADR del "Cerebro Arquitecto" (`docs/design/2026-08-18-cerebro-arquitecto-adr.md`, resuelto por `docs/design/2026-08-18-alineacion-estrategica-paso0.md`) ya cubren, con rigor real, buena parte de lo que este encargo pide. No los voy a repetir. Los voy a **contrastar contra el código de hoy** y a decir, con nombre y apellidos, dónde ese trabajo de auditoría ya está resuelto, dónde sigue abierto, y — esto es lo que ninguno de esos documentos podía ver porque se escribieron en momentos distintos — **qué ha pasado por construir dos verticales en paralelo sin haber decidido todavía cuál es "el producto".**

---

## 1. Estado real

### 1.1 La cifra que más importa: hay dos productos, no uno

```
analyzer/   24.947 líneas — el producto viejo (40 reglas CTE, 3D, scoring, chain_effects)
agente/     10.110 líneas — el producto nuevo (Skills con acta de procedencia, riguroso)
normativa/   3.938 líneas — motor territorial completo, corpus con 1 regla sin firmar
modelo/      2.297 líneas — grafo epistémico, portante SÓLO dentro de agente/
bim/           264 líneas — lectura IFC probada, sin capacidad activa en el registro
```

Y las rutas de Flask lo confirman sin ambigüedad (`app.py:164-192`):

- **`/`** (la puerta de entrada, desde el 2026-08-19 noche 5) abre el **panel de conversación nuevo** — `agente/`, una sola capacidad reconocida hoy: medir superficies. Si el primer visitante pregunta "¿esto cumple el CTE?", la respuesta es *"ArchMuse no tiene esa capacidad todavía"*.
- **`/proyectos`** abre la **SPA clásica** — `analyzer/`, el motor de ~40 reglas CTE, el semáforo verde/amarillo/rojo, el visor 3D, `chain_effects` (coste/urgencia estimados). Es lo más parecido a "sube un plano y encuentra problemas normativos" que existe en el repositorio hoy.
- **`/mvp`** es una tercera vista (el informe ejecutivo del 2026-08-19): cinco pestañas que mezclan capacidades viejas, un generador de alternativas nuevo (aritmética pura, sin LLM) y el copiloto.

**Esto no estaba planificado así — es una consecuencia no decidida de construir el vertical nuevo sin fusionarlo con el viejo.** El ADR del Cerebro Arquitecto (§F, paso 4) recomendaba explícitamente "tool-ificar" las 38 reglas de `evaluator.py` — envolverlas, no reescribirlas. Lo que se construyó en su lugar fueron capacidades nuevas de geometría y coherencia, sin tocar el motor CTE existente. Es una decisión defendible (el corpus estaba vacío; envolver 38 reglas sin corpus firmado habría inflado el riesgo de alucinación normativa que `C4` existe para limitar) — pero **nadie ha escrito por qué se desvió del paso 4 del propio ADR**, y el resultado es que hoy conviven dos productos que no se hablan.

### 1.2 Lo que funciona de verdad, verificado hoy

| Pieza | Estado verificado hoy (2026-08-20) |
|---|---|
| `analyzer/` — 40 reglas CTE, `/proyectos` | Funciona. Bug crítico de tipología/zona **corregido y con golden multiescenario** (`REFACTOR_MASTERPLAN.md` Fase 2). Adyacencia acústica inerte **corregida** (`analyzer/adyacencia.py`). Percentil comparativo inventado **eliminado del todo** — no está en el payload ni en la SPA, confirmado en `static/app.js`. |
| `agente/` — medición y coherencia | Funciona y es riguroso. `OP-15` (revisión de coherencia) y `OP-16` (medición multivivienda) están `HECHO`, verificados contra dos planos reales de cliente, con acta de procedencia celda a celda (`DOC-1`, cerrado hoy con validación de arquitecto veterano de Pablo). Hoy mismo se cerró `SEG-1`: el sistema ya no se autoconcede permiso para escribir un fichero, lo pregunta. |
| Corpus normativo | **Una sola regla transcrita**, sin firmar por un colegiado (`normativa/es/estatal/seguridad_incendio.yaml`). El motor que la resolvería (4.752 líneas, territorial completo) está construido y sin nada que resolver. |
| Tests | 1044 passed, 18 skipped, 1 xfailed, hoy mismo (verificado en esta sesión, no en un documento). De 0 tests el 31/7 a esto es el activo de ingeniería más sólido y menos discutible del proyecto. |
| Capacidades registradas | 13, por encima del techo `C4` (8-12), decisión pendiente de Pablo desde el 19/8 (`D-12`), guardián de test rojo a propósito. |

### 1.3 Lo que está construido pero no aporta valor hoy

- **`docs/brain/`** — 22 documentos, 7.594 líneas, sin fecha posterior al 2026-08-01. Es la primera versión de la visión del "Cerebro Arquitecto", escrita antes de que existiera nada de `agente/`. El propio ADR de 2026-08-18 lo dice con estas palabras: *"docs/ es mayor que analyzer/... es una ventaja: el diseño ya está pagado. Pero también es la señal de riesgo a vigilar."* Nada de ese diseño se ha invalidado, pero tampoco hay ninguna necesidad de volver a leerlo para avanzar: lo que de él importaba ya se destiló en el ADR y en `alineacion-estrategica-paso0.md`.
- **Visor 3D** (`viewer-*.js`, ~5.900 líneas) — sigue sin conectar a los hallazgos del motor de reglas. Dos documentos independientes (`MOAT_ANALYSIS.md`, `DESTROY_ARCHMUSE.md`) lo señalan como la debilidad más citada del producto, y sigue sin corregirse cuatro días después de que `ROADMAP_VISION_ARQUITECTONICA.md` lo pusiera como la primera tarea del horizonte de 1 mes.
- **`ai_generator.py`** — coloca estancias con criterio propio del modelo. Fuera del §8 corregido de `ARCHMUSE_SPEC.md`, sigue en producción por tres endpoints, decisión pendiente de Pablo desde el 19/8.
- ~~`JarvisApp.py` (989 líneas, Gemini)~~ **corrección (2026-08-20, ver §11.1): ya no existe en el repositorio, se eliminó en el commit `4bb5ee5`.** Y `experimentos/` — ajeno al producto, señalado en su momento, decisión sin tomar todavía.
- **`static/index.html`/`app.js`** clásico — 6.346 líneas de JS vanilla sin build. Sostenible con un desarrollador, no con dos, ya señalado y sin resolver.

### 1.4 Lo que podría romperse en una demo real

Esto es lo más importante de esta sección, porque es lo que un arquitecto real vería:

1. **El primer contacto (`/`) es el producto más estrecho, no el más completo.** Un arquitecto que pregunte por normativa en la puerta de entrada recibe una negativa educada. La riqueza real (40 reglas CTE) está dos clics más allá, en `/proyectos`, y nadie lo dirige ahí.
2. ~~`three.js` sigue cargándose desde 6 hosts externos~~ **CORRECCIÓN (2026-08-20, durante la ejecución del Bloque 1):** este punto estaba mal — venía de `REFACTOR_MASTERPLAN.md` sin contrastarlo contra el código de hoy, y es exactamente el error que este documento pedía no cometer. Verificado ahora: `three.js`, Inter y Mapbox GL JS/Threebox están **vendorizados y servidos desde el propio origen** (`static/vendor/`, `tarea 20` ya cerrada — ver los comentarios de `static/index.html` y `static/visor-mapa.js`). Lo único que sigue saliendo a un host externo es el **servicio** de teselas de mapa/satélite (`api.mapbox.com`, `server.arcgisonline.com`) — datos, no código ejecutable, y sólo cuando el arquitecto abre explícitamente "Ver en mapa real", no en la carga de la página. Eso es un riesgo mucho más pequeño y ya documentado como aceptado en `static/vendor/README.md`. El Bloque 3 de este documento (más abajo) queda corregido: no hace falta vendorizar nada más.
3. **El copiloto (`/api/copiloto`) sólo puede tocar una cosa** (`proyecto.ajustar_programa`, aritmética sobre un diccionario en memoria). Cualquier petición que suene a "cambia esto de mi plano" y no sea ajustar el programa de necesidades del generador de alternativas queda fuera de alcance sin decirlo con la misma claridad que el resto del producto.
4. **`classify_problems` sigue en 383 líneas** (peor que las 327 originales) sin ningún test que aísle qué bloque produjo qué hallazgo — cualquier cambio de umbral en el motor CTE sigue pudiendo alterar otro bloque en silencio.

---

## 2. Mayor riesgo actual

**No es técnico. Es que ArchMuse tiene hoy dos respuestas distintas a "¿qué es ArchMuse?", y las dos son ciertas a la vez.**

Si le preguntas al código en `/proyectos`: es un verificador de cumplimiento CTE con 40 reglas, semáforo de severidad, coste estimado y visor 3D — el producto que describen `PROJECT_AUDIT.md` y `TECH_REVIEW.md`, con su deuda técnica conocida pero con una promesa de producto reconocible y cercana a lo que un arquitecto espera de "control de calidad normativo".

Si le preguntas al código en `/`: es un copiloto que mide superficies y revisa coherencia geométrica con un rigor de trazabilidad que no tiene ningún competidor descrito en `DESTROY_ARCHMUSE.md` — pero que **no verifica ni una sola norma**, porque decidió, correctamente, no inventar ninguna cita sin corpus firmado.

Ninguna de las dos respuestas es falsa. El riesgo es que **nadie ha decidido cuál se enseña primero, y la que se enseña primero hoy (por una decisión de UX del 19/8, no de estrategia) es la más limitada de las dos.** Eso es exactamente el tipo de sorpresa que `DESTROY_ARCHMUSE.md` §5 identifica como el motivo nº1 de que un arquitecto no vuelva: no un hallazgo incorrecto, sino una promesa incumplida en el primer minuto.

---

## 3. Qué conservar

1. **`OP-15` (revisión de coherencia) y `OP-16` (medición multivivienda).** Son lo único del catálogo completo que cumple los cuatro criterios de tu propio encargo a la vez: no depende del corpus vacío, se apoya en código probado contra planos reales de cliente, devuelve un fichero de trabajo, y ejerce el ciclo agéntico entero. Están `HECHO`, verificados, y ya tienen la disciplina de "no inventar" que pides en tu punto 3.
2. **El acta de procedencia (`DOC-1`) y el mecanismo de autorización (`SEG-1`, cerrado hoy).** Es exactamente la infraestructura de confianza que `MOAT_ANALYSIS.md` Pilar 2 identifica como el argumento comercial más difícil de replicar, y ya existe, probada, no como aspiración.
3. **`normativa/` como motor, sin tocar su código.** Está completo y correcto. Lo único que le falta es contenido, y eso es una contratación (`NOR-1`), no una tarea de ingeniería.
4. **La suite de tests (1044 passed).** Es lo que permite tocar cualquiera de las dos verticales sin miedo a romper la otra.
5. **`agente/efectos.py` + el registro de capacidades (`Capacidad`, manifiesto, `C4`).** Es la disciplina anti-sobreconstrucción que tu propio punto 1 pide, ya construida y ya aplicada (el guardián de `C4` está en rojo a propósito ahora mismo).
6. **El motor CTE de `analyzer/evaluator.py`, como lógica, no como arquitectura.** `MOAT_ANALYSIS.md` §7 tiene razón: es la pieza más difícil de replicar del catálogo entero. El problema no es lo que sabe, es que vive fuera del sistema de procedencia. Ver §4.

---

## 4. Qué congelar

1. **`docs/brain/` (22 documentos) como fuente de trabajo activo.** No se borra — es historia real del proyecto y parte de su diseño ya destilado —, pero ninguna decisión nueva debería evaluarse contra él directamente: el ADR de 2026-08-18 y `alineacion-estrategica-paso0.md` ya lo sustituyen como criterio de aceptación vigente.
2. **El visor 3D, tal como está.** No se amplía con más materiales ni más realismo (`ROADMAP_VISION_ARQUITECTONICA.md` ya lo dice, y sigue siendo cierto cuatro días después: conectar el 3D a los hallazgos es lo único que aumenta su valor; todo lo demás aumenta la superficie que hay que mantener). Congelado, no eliminado — el trabajo ya invertido (PBR, sombras solares, terreno real) tiene valor el día que se conecte.
3. **`ai_generator.py`.** Sigue siendo una decisión pendiente de Pablo, no una que se tome por inercia de ingeniería. Mientras no se decida, no recibe trabajo nuevo.
4. **`/mvp` como tercera superficie.** Cinco pestañas es una superficie más de la que se puede validar bien con tres arquitectos reales. No se amplía hasta que se decida si sustituye a `/proyectos`, a `/`, o a ninguna de las dos.
5. **El techo de `C4` (13, por encima de 12).** No se sube. Es tu decisión pendiente (`D-12`) y el guardián que ya la protege sigue haciendo su trabajo.

---

## 5. Qué eliminar (o decidir eliminar ya, no aplazar más)

1. ~~`JarvisApp.py` + `requirements-jarvis.txt` + `.venv-jarvis/`. Ajeno al producto... sacarlo a su propio repositorio es una tarea de 15 minutos~~ **corrección (2026-08-20, ver §11.1): ya no aplica.** El código ya se eliminó del repositorio en un commit anterior a este documento (`4bb5ee5`) — este punto se escribió sin comprobarlo contra `git log`. Sólo queda `.venv-jarvis/` en disco, gitignored desde siempre, nunca publicado.
2. ~~La dependencia de `three.js` desde 6 CDNs externas~~ **Ya no aplica — corregido el 2026-08-20, ver la corrección de §1.4.** `three.js`/Inter/Mapbox GL JS ya están vendorizados desde `tarea 20`. Sólo quedan afuera los servicios de teselas de mapa (datos, no código), que no se vendorizan por diseño (`static/vendor/README.md`).
3. **La duplicación del bucle polígono→SVG**, que ha pasado de 3 a 4 copias mientras nadie lo consolidaba. Barato, mecánico, cero riesgo.
4. **La pregunta abierta de qué es `/mvp` frente a `/` y `/proyectos`.** No se elimina código todavía, pero **hay que eliminar la ambigüedad**: no puede haber tres puertas de entrada sin que ninguna sepa cuál es la principal.

---

## 6. Momento mágico

### 6.1 Tu ejemplo, contrastado con lo que existe

> *"Subo un plano y ArchMuse encuentra problemas normativos, me explica por qué existen, me muestra dónde están y me propone cómo solucionarlos."*

Contrastado contra el código: la mitad de esta frase (encontrar, explicar, mostrar dónde) **ya existe hoy, en dos sitios que no son el mismo**: `/proyectos` lo hace para normativa CTE (con deuda técnica conocida y sin acta de procedencia); `/` + el panel de conversación lo hace para coherencia geométrica y medición (sin deuda, con acta de procedencia completa). La otra mitad — "propone cómo solucionarlo" — **no existe en ningún sitio todavía**: ni el motor CTE ni las Skills nuevas generan una corrección, sólo un diagnóstico.

### 6.2 Por qué el momento mágico NO debe ser "cumplimiento CTE" en V1

No porque no sea deseable — es exactamente lo que `NORTH_STAR_2031.md` y tu propio ejemplo describen —, sino porque **hoy es imposible hacerlo sin violar tu propia regla del punto 3**: el corpus normativo tiene una regla, sin firmar. Cualquier cita de artículo CTE que no venga de ahí es, por definición, una alucinación con apariencia de rigor — el ataque nº1 que `DESTROY_ARCHMUSE.md` ya identificó contra el propio proyecto. El motor de `evaluator.py` es real y valioso, pero sus umbrales son Python escrito a mano, no citas verificadas — no tiene el nivel de procedencia que tú mismo exiges en el punto 3 de tu encargo.

### 6.3 El momento mágico correcto para hoy, ya construido

**"Sube tu plano y comprueba que está bien medido y bien dibujado antes de entregarlo — con el motivo exacto y la pieza señalada del propio DXF, o con un 'no puedo comprobarlo' explícito donde corresponda."**

Es `OP-15` + `OP-16` + `DOC-1`, ya `HECHO`, ya validado contra dos planos reales de cliente, con la disciplina exacta que pides: nunca un número sin procedencia, nunca "esto está mal" sin decir por qué y dónde, y una limitación explícita («no comprueba normativa») en vez de fingir que sí lo hace.

**Lo que le falta para ser un momento mágico completo, no sólo un motor correcto, son tres cosas concretas — todas de interfaz, ninguna de motor nuevo:**

1. Una sola puerta de entrada que lo enseñe primero, en vez de esconderlo detrás de "adjunta un DXF y pregunta".
2. Que el hallazgo señale la pieza sobre una vista del plano (hoy señala rótulo + capa en texto; falta el clic que lleva a verlo).
3. Un cierre honesto de la frase que sí puedes prometer hoy: *"esto no comprueba normativa todavía — eso llega en cuanto el corpus tenga su primera regla firmada."* Dicho así, en la propia interfaz, conviertes tu mayor carencia en el argumento de confianza que `MOAT_ANALYSIS.md` Pilar 2 dice que es el más difícil de replicar.

### 6.4 Qué desbloquea el momento mágico grande

`NOR-1` — contratar al colegiado que firme la primera regla del corpus — no es una tarea de ingeniería, es la única acción que convierte "coherencia y medición" en "coherencia, medición y una primera norma real, citada y defendible". Sigue siendo, con diferencia, la tarea de mayor apalancamiento del proyecto y sigue sin empezar. No la sustituye ningún sprint.

---

## 7. Definición del V1

### DEBE EXISTIR

- **Una sola puerta de entrada**, no tres. Recomendación concreta: `/` sirve el flujo de "revisa este plano" (`OP-15`+`OP-16`+`DOC-1`, ya construido), con el copiloto de conversación como forma de pedirlo, no como producto aparte.
- **El acta de procedencia visible en cada resultado**, sin excepción — ya existe, sólo falta que sea la norma en la puerta principal, no una función que hay que descubrir.
- **La declaración explícita de qué NO comprueba** (normativa, hoy) en el mismo sitio donde se enseña el resultado, no en un aviso técnico aparte.
- **`SEG-1` en todo flujo que escriba algo** — ya cerrado hoy; extenderlo es barato porque el mecanismo ya existe.
- ~~Vendorizar `three.js`~~ **Ya no aplica — ya estaba hecho antes de este documento (`tarea 20`), corregido el 2026-08-20.**

### PUEDE ESPERAR

- Conectar el visor 3D a los hallazgos (valioso, pero no es lo que hace que un arquitecto diga "esto me sirve" en la primera sesión — lo dice el acta, no el render).
- `/mvp` y sus cinco pestañas, incluidas las alternativas paramétricas — interesante, no imprescindible para que 3 arquitectos digan si esto vale.
- Refactorizar `classify_problems` (383 líneas) — deuda real, pero no bloquea ninguna demo mientras nadie toque un umbral con prisa.
- Autenticación y persistencia multiusuario — necesario para cobrar a un segundo cliente, no para que el primero diga "sí".
- BIM/IFC real, generación de alternativas ampliada, `TL-5` (envolver las 38 reglas CTE) — todo correcto en su momento, ninguno es el momento actual.

### NO DEBEMOS HACERLO AHORA

- **Ampliar el corpus normativo sin firma de un colegiado.** Ni una regla más sin `NOR-1` resuelto — es la línea que separa "no inventamos nada" de convertirse en lo que `DESTROY_ARCHMUSE.md` ataca.
- **Subir el techo de `C4` (13→más).** Cada capacidad nueva sin corpus es más superficie de riesgo de alucinación normativa, no más valor. `D-12` sigue siendo tu decisión, no una que se tome añadiendo código.
- **Fusionar `analyzer/` y `agente/` de golpe.** Es tentador y es el error de alcance más caro posible ahora mismo: mezclar dos sistemas de trazabilidad distinta en una sola sesión de refactor sin red de pruebas dedicada a esa fusión es exactamente el tipo de "arquitectura prematuramente compleja" que tu punto 5 pide vigilar.
- **Cualquier percentil, score comparativo o "posición frente al mercado".** El único ya existente se eliminó por buena razón. No se reintroduce sin datos reales.
- **Escribir código de capacidad nueva sin PRD.** Sigue siendo la regla de `CLAUDE.md`, y este documento no la deroga.

---

## 8. Bloques de trabajo prioritarios

Secuencia corta, cada bloque deja el producto en pie y demostrable, en orden:

**Bloque 1 — Una puerta, no tres (1-2 días).**
Decidir y ejecutar cuál es la ruta principal. Recomendación: `/` = el flujo de revisión (`OP-15`+`OP-16`), con enlace claro a `/proyectos` (motor CTE) etiquetado honestamente como "verificación normativa, sin corpus firmado todavía — usa esto bajo tu propio criterio profesional", no escondido ni presentado como equivalente en rigor al flujo principal. `/mvp` se congela hasta decidir su futuro. Esto es, sobre todo, una decisión de producto tuya, no una tarea de ingeniería larga.

**Bloque 2 — Cerrar el ciclo de confianza del flujo principal (2-3 días).**
Extender `SEG-1` a cualquier otro punto de escritura que quede. Enlazar el acta de procedencia a la pieza señalada del plano (hoy es texto: "Pieza: X · Capa: Y" — falta el clic que la resalta si hay una vista del DXF disponible). Cerrar la limitación "no comprueba normativa" en el propio resultado, no en un aparte.

**Bloque 3 — Housekeeping que protege la demo (medio día → menos, ver corrección).**
~~Vendorizar `three.js`~~ ya estaba hecho (corrección del 2026-08-20, ver §1.4). ~~Sacar `JarvisApp.py` de este repositorio~~ también ya estaba hecho (corrección, ver §11.1). Decidir por escrito qué es `/mvp` — hecho, ver §11.2: no sustituye a nada y no se retira.

**Bloque 4 — Probarlo con 3 arquitectos reales.**
No es un bloque de ingeniería. Es el criterio del §10. Se hace en cuanto los bloques 1-3 estén cerrados, no después de perseguir más funcionalidad.

**En paralelo, desde hoy, sin competir por el mismo tiempo de ingeniería: `NOR-1`.** Es contratación, no código. Es la tarea de mayor apalancamiento del proyecto entero y lleva "técnico hecho, falta contratar" desde el 19/8.

---

## 9. Qué NO hacer todavía

- No tocar el techo de `C4`.
- No empezar BIM real (importador IFC) ni ingesta de imágenes.
- No escribir ni una regla más de corpus sin firma colegiada.
- No fusionar `analyzer/` y `agente/`.
- No ampliar el visor 3D con más realismo antes de decidir si se conecta a los hallazgos o se congela definitivamente.
- No construir la memoria justificativa automática con contenido normativo real (el PRD de `SK-7` ya lo dice: el índice de apartados sin corpus es defendible, redactar contenido no lo es).
- No perseguir autenticación/multiusuario/billing todavía — es la base de vender al segundo cliente, no de que el primero diga que sí.
- No escribir código de ninguna capacidad nueva sin su PRD aprobado.

---

## 10. Criterio objetivo para declarar ArchMuse "listo para primeros arquitectos"

Cinco condiciones verificables, no una sensación:

1. **Una sola puerta de entrada**, y quien la abre no recibe nunca una negativa a la primera pregunta razonable sobre su plano — o si la recibe, la negativa explica exactamente qué haría falta y por qué no está todavía.
2. **Para tres celdas o hallazgos al azar del resultado, un arquitecto que no ha visto el código puede rastrear cada uno hasta la entidad concreta del DXF** — el mismo criterio que ya validaste para `DOC-1`, aplicado como estándar de todo lo que se enseñe, no de una sola función.
3. **Ningún dato inventado en pantalla.** Cero percentiles, cero "score frente al mercado", cero cita normativa sin corpus firmado detrás. Verificable leyendo la interfaz, no el código.
4. **La demo sobrevive sin conexión perfecta.** Ni una CDN externa puede romper visiblemente la sesión.
5. **Un arquitecto real, sin que nadie le explique nada, dice — sin que se lo sugieras — "esto me ahorraría trabajo" antes de que termine la demo.** Es la prueba del §7 del informe ejecutivo del 19/8, ya escrita y aprobada como criterio: si a las 24h dice "está chulo pero no lo usaría", no está listo, sin excepciones ni relecturas optimistas del resultado.

---

## 11. Bloque 3 — housekeeping (2026-08-20, tarde)

### 11.1 `JarvisApp.py` — corrección: la tarea ya estaba hecha, y este documento no lo sabía

**Verificado en `git log`, no asumido de `PROJECT_AUDIT.md`/el ADR (que es de donde venía la afirmación de §1.3/§5 de este mismo documento):** `JarvisApp.py`, `requirements-jarvis.txt` e `Iniciar Jarvis.bat` **ya se eliminaron del repositorio** en el commit `4bb5ee5` ("docs+feat: preparar el repositorio para publicación, y la revisión de coherencia del plano") — 989 líneas de `JarvisApp.py` incluidas. No queda ni un fichero fuente de Jarvis en el árbol de trabajo ni en `git ls-files`. Es la misma clase de error que el de `three.js` en §1.4/§5: una afirmación heredada de un documento anterior, repetida sin contrastarla contra el estado real del repositorio hoy. Corregido aquí, no en otro documento aparte.

Lo único que queda en disco, y **no está en git** (`.venv-jarvis/` está en `.gitignore` desde siempre, nunca formó parte del repositorio publicado):

- `.venv-jarvis/` — un entorno virtual de Python completo (site-packages con PyAudio, adodbapi, PyWin32...), local, en el disco de Pablo.
- `__pycache__/JarvisApp.cpython-312.pyc` — el bytecode compilado de un fichero que ya no existe.

**No se ha borrado nada de esto.** Es un entorno local, no un riesgo del repositorio ni de ninguna demo, y no hay forma de saber desde aquí si Pablo lo sigue usando para ejecutar Jarvis desde una copia del código que guarda en otro sitio. Decisión pendiente de Pablo, no mía: si confirma que no lo necesita, borrar `.venv-jarvis/` y el `.pyc` es un `Remove-Item -Recurse` de un minuto.

### 11.2 `/mvp` — decisión razonada, sin ejecutar nada

**No sustituye a nada, y no se retira.** Es una tercera capacidad, no una alternativa a las otras dos:

- `/` (desde Bloque 1): revisar un plano que ya existe — medición y coherencia, sobre un DXF real.
- `/proyectos`: verificación normativa CTE de ~40 reglas, sobre un DXF real.
- `/mvp`: **generar** alternativas de envolvente a partir de parámetros urbanísticos (parcela, ocupación, edificabilidad, programa) — no revisa nada que ya exista, lo produce. Aritmética con procedencia (`analyzer/alternativas.py`), con la generación de distribución interior por LLM claramente separada y marcada "sin auditar" (franja de aviso permanente, nunca mezclada visualmente con lo aritmético) — cumple el §8 corregido de `ARCHMUSE_SPEC.md` al pie de la letra.

Verificado hoy: 6 pestañas (Alternativas, Distribución, Análisis, Normativa, Costes, Exportar — este documento decía "cinco" en su versión original; corregido aquí), 541 líneas de `mvp.js`, con test dedicado y en verde (`tests/test_mvp_no_mezcla_auditado_con_generado.py`, `tests/test_mvp_parcela_real.py`, 15 tests). No es código a medias ni abandonado — es una capacidad real, construida por petición directa de Pablo (informe ejecutivo del 19/8), que simplemente no compite por el mismo hueco que la revisión de un plano.

**Por qué no se retira:** borrar una capacidad real, probada y pedida explícitamente, sin que nadie haya dicho que no sirve, sería exactamente la clase de decisión que este documento pide no tomar por inercia. No aporta nada a la demo del Bloque 4 (que es sobre revisar un plano, no sobre generar alternativas), así que no compite por ese tiempo — y por eso el Bloque 1 ya lo dejó congelado, decisión que se mantiene.

**Por qué no se decide su integración todavía:** la pregunta real no es "¿se borra?" — es "¿debería `/mvp` acabar siendo una cuarta pestaña dentro de la misma `/`, o quedarse como herramienta aparte para una fase distinta del trabajo (programar antes de tener un plano que revisar, frente a revisar un plano que ya existe)?". Esa es una decisión de producto que depende de si un arquitecto real, en el Bloque 4, pide las dos cosas en la misma sesión o las trata como tareas separadas — no se puede responder bien especulando ahora, y adelantarla sería el mismo error que el de construir sin pasar primero por el arquitecto real. Se revisita después del Bloque 4, con datos.

**Conclusión operativa:** `/mvp` sigue exactamente como está — congelado, sin trabajo nuevo, sin borrar nada — hasta que el Bloque 4 dé una razón concreta para decidir lo contrario.
