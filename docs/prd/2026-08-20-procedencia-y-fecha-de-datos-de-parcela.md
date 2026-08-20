# PRD — Procedencia estructurada y fecha visible para los datos de parcela (Fase A)

**Estado:** Borrador · **Fecha:** 2026-08-20 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

---

## 0. Alcance de esta Fase, explícito

Esto es **Fase A** de la capacidad de parcela/Catastro, tal como la delimitó Pablo: dar procedencia estructurada y fecha visible a lo que **ya existe y funciona hoy** — `static/map-picker.js`, `/api/analizar-sitio`, la consulta real al WFS/INSPIRE del Catastro. **No toca edificabilidad ni zonificación** (Fase B, sin empezar, sin PRD todavía) y **no decide** si el flujo de "Generar proyecto" debe moverse de sitio (pregunta abierta de Pablo, ver §6).

Este PRD nace directamente de la auditoría pedida el mismo día (turno anterior de esta conversación) y no repite lo que ya midió: cita sus hallazgos como hechos ya verificados, no como suposiciones.

## 1. Problema que resuelve

La auditoría encontró un hueco concreto, no hipotético: **hoy se le dice al arquitecto de dónde sale un dato de parcela, pero no cuándo se obtuvo, y no de una forma que un código pueda verificar después.**

- `/mvp` (CP-4) y "Generar proyecto" (Paso 0, `entrevista.js`) muestran textos como *"Catastro real: 340 m² · ref. 1234567AB1234C"* / *"Superficie obtenida de Catastro: 340 m²"* — la fuente está en el texto, pero es una frase, no un dato estructurado que sobreviva a un cambio de copy o se pueda comprobar por test.
- La fecha de la consulta **existe**, pero solo como `creado_en`/`modificado_en` en la fila de caché de `analyzer/storage.py` (tabla `sitios`) — nunca llega al arquitecto, y no viaja pegada al valor (`superficie_m2`, `referencia_catastral`, la geometría) que describe.
- Esto es exactamente el defecto que `docs/design/2026-08-18-alineacion-estrategica-paso0.md` y la "regla de oro" de `ARCHMUSE_SPEC.md` prohíben para cualquier cifra: *"si un número aparece en una respuesta o en un informe sin un registro de procedencia que diga qué tool lo produjo, con qué inputs y con qué versión, es un bug de severidad crítica."* Los datos de parcela llevan meses en producción (CP-4 es del 19-ago) incumpliéndola, sin que nadie lo hubiera medido hasta ahora.

## 2. Usuario afectado

El arquitecto que usa "Generar proyecto" (flujo principal, `entrevista.js`) o `/mvp` (vista de tres zonas) para arrancar un proyecto sobre una parcela real. Es el mismo usuario de hoy, no uno futuro: la parcela real ya se consulta en producción, esto no abre una capacidad nueva de cara al usuario — endurece una que ya usa.

## 3. Objetivo de negocio

Un dato de Catastro sin fecha visible es un dato que el arquitecto no puede defender ante un colegio o un cliente dentro de seis meses — "¿esto lo comprobaste hoy o hace un año?" es exactamente la pregunta que un colegiado hace, y hoy ArchMuse no tiene forma de responderla. Es la misma lógica de negocio que ya motivó `DOC-1` (el acta de medición): la procedencia no es un adorno de transparencia, es lo que hace que un dato sea defendible, y lo defendible es el foso de este producto frente a "una app que también consulta Catastro" (`MOAT_ANALYSIS.md`).

## 4. Objetivo técnico

Una vez implementado:

1. Cada dato de parcela que hoy viene de Catastro (`referencia_catastral`, `geometria_parcela.superficie_m2`, `geometria_parcela.coordenadas`, `coordenadas` del centro) lleva adjunto un registro de procedencia con, como mínimo: **fuente nombrada** (el servicio exacto, no solo "Catastro"), **fecha/hora de la consulta**, y si el valor salió de caché o de una llamada nueva.
2. Esa fecha es **visible para el arquitecto**, no solo interna — en los dos sitios donde hoy se muestra el resultado (`/mvp` y "Generar proyecto").
3. Ningún dato existente cambia de valor ni de comportamiento. Esto es un añadido de trazabilidad, no una capacidad nueva de cara al dato en sí.

## 5. Casos de uso

1. El arquitecto busca una dirección en el mapa de "Generar proyecto", hace clic sobre la parcela; ve la superficie, la referencia catastral **y la fecha de la consulta**, en el mismo bloque de texto.
2. El arquitecto vuelve dos días después al mismo proyecto (o consulta la misma parcela desde otro proyecto): la respuesta viene de caché (`analyzer/storage.py`) — la fecha mostrada es la de la consulta **original**, no la de hoy, y algo distingue visualmente "esto es de caché" de "esto se acaba de consultar".
3. Un test (o un desarrollador dentro de un año) puede tomar la respuesta JSON de `/api/analizar-sitio` y verificar programáticamente cuándo se obtuvo cada dato, sin tener que parsear un texto en español.

## 6. Pregunta abierta — NO decidida en este PRD

**¿Debe `map-picker.js` (y el flujo de parcela real que hoy vive dentro de "Generar proyecto", Paso 0) quedarse donde está, o moverse a otro sitio de la app?** Es una decisión de producto de Pablo, no de este documento. Fase A se implementa **donde el flujo ya vive hoy** (Paso 0 de "Generar proyecto", más el añadido puntual en `/mvp` que ya introdujo CP-4); si Pablo decide mover el flujo después, la procedencia estructurada que aquí se construye viaja con los datos y no depende de en qué pantalla se muestren — así que esta pregunta no bloquea Fase A en ningún sentido.

## 7. Flujo del usuario

Sin cambios respecto al de hoy (clic en el mapa → Catastro real → parcela dibujada). Lo único que se añade es un renglón más en el bloque de resultado, con la fecha, y el dato estructurado detrás de cada valor mostrado.

## 8. Criterios de aceptación

Mismo rigor que exigió `DOC-1` para el acta de medición — **criterio de arquitecto, no de ingeniero**:

1. Para un dato de parcela cualquiera mostrado al usuario (superficie, referencia catastral, o la parcela dibujada en el mapa), un arquitecto puede leer **de qué servicio salió y cuándo se consultó**, sin abrir la consola del navegador ni preguntar a un programador.
2. Ese mismo dato, visto en el JSON de `/api/analizar-sitio`, lleva la fecha y la fuente como campos propios — no como parte de un texto libre.
3. Consultar la misma parcela una segunda vez (dentro de la ventana de caché) muestra la fecha de la **primera** consulta, y lo dice explícitamente ("consultado el AAAA-MM-DD", no repite la fecha de hoy como si fuera nueva).
4. Ningún test existente de `tests/test_sitio.py`, `tests/test_mvp_parcela_real.py`, `tests/test_sitio_proyecto_link.py` se rompe — los consumidores que ya leen `datos.geometria_parcela`/`datos.referencia_catastral` (`checklist_campo.py`, `pliego_extractor.py`, `viewer-sandbox.js`) siguen recibiendo esos mismos campos, sin cambios.
5. `analyzer/sitio.py` sigue siendo una función pura sin estado (documentado explícitamente en su propio módulo) — la procedencia se construye ahí como dato de retorno, no rompe ese invariante escribiendo a disco desde dentro.

## 9. Riesgos

- **Técnico, bajo.** Es un campo nuevo añadido a una respuesta ya existente, no una reescritura. El mayor riesgo real es de nomenclatura: que el campo de procedencia se llame distinto en cada uno de los tres consumidores (`/mvp`, `entrevista.js`, un futuro cuarto) y acabe siendo tres formatos que decir lo mismo — se evita fijando la forma exacta en este PRD antes de tocar cada fichero por separado (§11).
- **De arquitectura, a decidir en la implementación, no aquí.** `agente/afirmacion.py::Afirmacion` (el patrón real que hoy hace de "Provenance/SourceRef" en este repo, aunque con otro nombre — ver §10) tiene su campo `fuente` acoplado a `capacidad_id@version`: exige que quien produce el dato esté registrado como `Capacidad` en `agente/registro.py`. `/api/analizar-sitio` vive fuera del todo del vertical `agente/` (lo llama un endpoint Flask directo, sin `Ejecutor`/`Plan`/`Skill` de por medio) — registrarlo como Capacidad nueva **tocaría el techo de C4**, expresamente prohibido para este trabajo. La recomendación técnica de este PRD (no una decisión cerrada, se afina al implementar) es **no reutilizar `Afirmacion` literalmente** y en su lugar seguir el patrón más ligero que el propio repositorio ya usa para un caso parecido: `normativa/ambito.py::Procedencia` (`origen: str`, `verificado: bool`, `aviso: Optional[str]`) — mismo espíritu (ningún valor viaja desnudo), sin la maquinaria de Capacidad/Skill. Se añadiría un campo de fecha a ese mismo patrón para el caso de parcela.
- **De negocio, ninguno nuevo.** No compite con `REFACTOR_MASTERPLAN.md` por las mismas horas: es trabajo en `analyzer/sitio.py`/`app.py`/frontend de parcela, ninguno de los ficheros que ese plan prioriza.

## 10. Impacto sobre módulos existentes

Mapeado en la auditoría previa, confirmado aquí fichero a fichero:

| Fichero | Qué toca |
|---|---|
| `analyzer/sitio.py` | `_geometria_parcela_catastro()`, `_referencia_desde_coordenadas()`, `obtener_datos_parcela()` — añadir el bloque de procedencia al `dict` que ya devuelven. Sigue sin estado, sin tocar `analyzer/storage.py` desde aquí. |
| `analyzer/storage.py` | `guardar_sitio()`/`obtener_sitio_por_clave()` — la fecha de la **primera** consulta (`creado_en`) ya existe en la fila; hay que decidir si se copia dentro del propio `datos` JSON (para que viaje aunque alguien lea la fila fuera de este módulo) o se sigue leyendo solo de la columna. Recomendación: copiarla dentro de `datos`, así el JSON de `/api/analizar-sitio` es autosuficiente. |
| `app.py` | `analizar_sitio()` (`/api/analizar-sitio`) — sin lógica nueva, solo que la respuesta que ya arma incluye el bloque de procedencia que viene de `sitio.py`/`storage.py`. |
| `static/entrevista.js` | `htmlEstadoSitio()` (Paso 0) — añadir la línea de fecha al bloque que ya construye con `referenciaCatastral`/`superficieM2`/`ciudadDetectada`. |
| `static/mvp.js` | `elegirParcela()` (CP-4) — mismo añadido, en el `estadoEl.textContent` que ya construye. |
| `static/map-picker.js` | Ninguno. El mapa solo dibuja geometría; no muestra texto de procedencia, no le corresponde tocarlo. |

**Consumidores que leen esta misma caché y NO deben cambiar de comportamiento** (verificado en la auditoría, confirmado otra vez aquí): `analyzer/checklist_campo.py`, `analyzer/pliego_extractor.py`, `static/viewer-sandbox.js`. Añadir un campo nuevo al `dict` no les afecta si no lo leen; el criterio de aceptación §8.4 lo hace explícito.

## 11. Plan de implementación dividido en pequeñas tareas

Mismo formato que `REFACTOR_MASTERPLAN.md`, tareas de máximo 2h:

1. **Definir la forma exacta del bloque de procedencia** (~1h). Fijar el nombre de los campos (propuesta: `procedencia: {fuente, consultado_en, de_cache}` junto a cada bloque de dato, o uno solo a nivel de `sitio` — se decide mirando cómo lo van a leer los tres consumidores del frontend antes de escribir código en ninguno). Sin código todavía en este paso; es el punto donde de verdad se resuelve el riesgo de nomenclatura del §9.
2. **`analyzer/sitio.py`**: añadir el bloque a `obtener_datos_parcela()` (~1h). `fuente` fija por rama (WFS/INSPIRE Catastro vs. Overpass/OSM, ya se distinguen internamente); `consultado_en` con hora real del momento de la llamada.
3. **`analyzer/storage.py`**: decidir y aplicar dónde vive la fecha "de caché" (~0,5h) — que una relectura devuelva la fecha ORIGINAL, no la de hoy (criterio §8.3).
4. **Frontend, `entrevista.js`** (~0,5h): mostrar la fecha en `htmlEstadoSitio()`.
5. **Frontend, `mvp.js`** (~0,5h): mismo añadido en `elegirParcela()`.
6. **Tests**: extender `tests/test_sitio.py` y `tests/test_mvp_parcela_real.py` con el criterio de "la procedencia viaja con el dato" y "la fecha de caché es la original" (~1h).

Total estimado: ~4,5h, sin ninguna tarea que dependa de otra fuera de este PRD.

## 12. Plan de pruebas

- Extender `tests/test_sitio.py`: `obtener_datos_parcela()` con una geometría de Catastro devuelta trae el bloque de procedencia con `fuente`/`consultado_en`.
- Extender `tests/test_mvp_parcela_real.py`: el criterio ya existente ("solo `solar` se autorellena desde Catastro") se amplía para comprobar que la procedencia acompaña a ese mismo valor.
- Nuevo test sobre `analyzer/storage.py`: guardar un sitio, leerlo dos veces, comprobar que la fecha no cambia entre lecturas.
- Regresión completa de `tests/test_sitio_proyecto_link.py` y de los consumidores de checklist de campo — deben seguir en verde sin tocarlos.

## 13. Métricas para medir el éxito

No hay una métrica de producto medible a corto plazo (es trazabilidad, no una función que el arquitecto elige usar más o menos) — el criterio de éxito es binario y de auditoría: dentro de un mes, una consulta cualquiera a `/api/analizar-sitio` en producción tiene que poder responder "¿cuándo se comprobó esto?" sin mirar la base de datos a mano.

## 14. Posibles motivos para NO implementar la idea

- **Es trabajo de trazabilidad puro, sin superficie nueva que un arquitecto pueda tocar.** Si el criterio de priorización de esta fase de ArchMuse es "lo que un arquitecto real pide primero en la demo" (Bloque 4, ya en marcha), esto probablemente no es lo primero que alguien nota al ver el producto por primera vez — es lo que nota si vuelve dos meses después y pregunta "¿esto sigue siendo verdad?". Vale la pena decirlo así de claro: no es una tarea que vaya a impresionar en una demo de cinco minutos.
- **Alternativa más barata:** si lo único que hace falta a corto plazo es la fecha visible (criterio de negocio real, §3) sin el bloque de procedencia estructurado completo, se podría cerrar con solo las tareas 3-5 del plan (~2h) y dejar el objeto estructurado (tareas 1-2) para cuando haga falta que un consumidor programático lo lea de verdad. Se apunta aquí como recorte posible, no como recomendación — el criterio de aceptación §8.2 (JSON con campos propios, no texto libre) es explícito en el encargo de Pablo, así que el PRD no lo recorta por su cuenta.
