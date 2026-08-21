# PRD — Ubicación estructurada de hallazgos (contrato de datos para el futuro visor 2D)

**Estado:** Aprobado · **Fecha:** 2026-08-21 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-21, con UB-6 incluido)

> Este PRD **no construye ningún visor**. Construye el contrato de datos del
> que un visor 2D con zoom-to-hallazgo podría alimentarse más adelante, en un
> prompt aparte. Todo lo verificado aquí sale de leer el código de hoy —
> `analyzer/coherencia.py`, `analyzer/parser.py`, `agente/skills/coherencia.py`,
> `agente/acta.py` —, no de suponer cómo está construido.

---

## 1. Problema que resuelve

`revision.coherencia_del_plano` (PRD `2026-08-19-revision-de-coherencia-del-plano.md`,
implementado y en producción desde el 2026-08-20) ya produce `Hallazgo`s con una
`entidad` — «handle X», «sala A + sala B», «capa «X»» — pensada para que la lea
un humano. Localizar ese hallazgo en el plano hoy exige parsear ese texto o
volver a abrir el DXF a mano. Un visor que quiera hacer «haz zoom a este
hallazgo» necesita coordenadas, no una frase.

Esto viene de una petición directa de Pablo con el contrato ya especificado
(campo, forma, regla de no-inventar-geometría, mapeo hallazgo-por-hallazgo).
No hay ningún hallazgo de `TECH_REVIEW.md`/`MOAT_ANALYSIS.md` detrás — es
trabajo de plomería explícitamente pedido como paso previo a una UI futura.

**Lo que la lectura del código añadió a la petición original**, y que cambia
el alcance real de "hecho": el camino HTTP real de esta Skill hoy (`/api/preguntar`,
único punto de entrada — no hay endpoint dedicado) no expone `Revision.a_dict()`
tal cual. Pasa por `agente/skills/coherencia.py`, que sólo promueve a
`afirmaciones` los campos listados en su `PRODUCE` (`revision.recintos`,
`.hallazgos`, `.recuento_por_tipo`, `.comprobado`, `.informe`), y luego por
`agente/acta.py:levantar()`, que sólo copia `afirmaciones`/`entregables`/
`no_hecho` del resultado de la Skill al acta — y termina renderizado como
**HTML** por `analyzer/acta_legible.py`, no como JSON. Ver §9 R-1 y R-3: esto
importa para saber qué significa "hecho" en este PRD.

---

## 2. Usuario afectado

El arquitecto que revisa un hallazgo de coherencia y quiere verlo señalado
sobre el plano en vez de leer sólo su descripción — mismo usuario que el PRD
base, un paso más adelante en la misma tarea.

Usuario secundario: el propio ArchMuse / el siguiente prompt. Este PRD existe
para que ese prompt no tenga que releer el DXF ni inventar dónde vive cada
tipo de hallazgo.

---

## 3. Objetivo de negocio

No tiene uno propio distinto del PRD base — es infraestructura de datos para
el objetivo de negocio ya aprobado allí (§3: «un entregable vendible que no
depende del corpus», «convierte la desconfianza en argumento de venta»). El
argumento de venta de esa Skill es «esto se puede comprobar en tres clics»; un
visor con zoom-to-hallazgo es la primera vez que eso deja de ser una frase y
se vuelve literal. Este PRD no vende nada por sí solo: hace posible que el
visor, cuando exista, sí lo haga.

---

## 4. Objetivo técnico

- `Hallazgo` gana un campo `ubicacion: Optional[Dict[str, Any]] = None`, con
  forma `{"bbox": [xmin, ymin, xmax, ymax]}` cuando existe, en las mismas
  unidades escaladas que las áreas en m² del resto del informe — nunca
  unidades de dibujo crudas.
- **Regla dura, sin excepción:** sin geometría real y verificable para ese
  hallazgo concreto, `ubicacion = None`. Nunca un bbox aproximado o centrado.
  `None` es un resultado válido, no un fallo.
- `Revision.a_dict()` gana `recintos_geometria`: por cada `Room` leída,
  `{"label", "layer", "puntos"}` con los puntos del polígono exterior.
- Esto es cierto **como función Python** (`analyzer.coherencia.revisar()` y
  `agente/herramientas/coherencia.py:revisar_coherencia()`, que usa
  `Revision.a_dict()` sin reconstruirlo — verificado). Para ser cierto también
  **a través de la Skill/acta** (el único camino HTTP real hoy) hace falta
  además UB-6 (§11) — sin eso, `recintos_geometria` se pierde en el paso a
  `afirmaciones` antes de llegar a ningún sitio que un futuro visor pueda leer.
- **Límite exacto de lo que UB-6 alcanza — no más.** UB-6 hace que
  `ubicacion` y `recintos_geometria` sobrevivan hasta la `Afirmacion`
  `revision.hallazgos`/`revision.recintos_geometria` y, de ahí, hasta
  `Acta.a_dict()` (el acta interna que construye `agente/acta.py:levantar()`).
  **No** implica que `/api/preguntar` empiece a devolver JSON al navegador:
  hoy ese endpoint renderiza HTML vía `analyzer/acta_legible.py`
  (`_revisar_coherencia_y_renderizar_acta`), y sigue haciéndolo exactamente
  igual al cerrar este PRD — no se toca `/api/preguntar` ni ningún fichero de
  `static/`. Exponer estos campos como JSON consumible por un frontend es un
  PRD/prompt aparte, no algo que este PRD deje implícitamente resuelto.

---

## 5. Casos de uso

**CU-1 · Zoom a un SOLAPE.** El visor recibe `ubicacion.bbox` = unión de los
`.bounds` de `room_a`/`room_b` y encuadra ahí.

**CU-2 · Zoom a un RECINTO_SIN_ETIQUETA / ETIQUETA_DUPLICADA.** Igual, con la
unión de las `Room` implicadas dentro de esa vivienda.

**CU-3 · Hallazgo sin ubicación.** `CUADRO_PIDE_PIEZA_NO_DIBUJADA`,
`PIEZA_DIBUJADA_FUERA_DEL_CUADRO`, `RECUENTO_NO_COINCIDE`, `SIN_RECINTOS`, o un
`POLILINEA_MAL_CERRADA`/`GEOMETRIA_DESCARTADA` cuyo handle no resuelve: el
visor no puede encuadrar y lo dice («sin ubicación, ver acta») — no es un
fallo, es el contrato cumpliéndose.

**CU-4 · Dibujar el plano sin ningún hallazgo seleccionado.** `recintos_geometria`
basta para pintar todos los recintos leídos, con o sin hallazgos.

---

## 6. Casos límite

| Caso | Qué tiene que pasar |
|---|---|
| Handle no resuelve en `doc.entitydb`/`ezdxf.bbox.extents` (borrado, en un bloque no atravesado, tipo sin geometría calculable) | `ubicacion = None`. Nunca una excepción que tumbe la revisión entera por un solo hallazgo |
| `POLILINEA_MAL_CERRADA`/`GEOMETRIA_DESCARTADA` con `handle is None` (entidad "virtual" de un bloque, ver `parser.py` línea ~94) | `ubicacion = None` directamente, sin intentar resolver nada |
| El bbox de la entidad sale en unidades de dibujo crudas | Hay que multiplicarlo por `plano.escala.factor` (el mismo factor ya aplicado a `Room.polygon`, confirmado en `parser.leer_plano`) antes de guardarlo — si no, el bbox queda en una unidad distinta a los recintos y el visor encuadraría mal sin ningún error visible |
| `SIN_RECINTOS` (cero recintos leídos) | `ubicacion = None` (no hay nada que encuadrar) y `recintos_geometria = []` |
| Los cuatro tipos de discrepancia cuadro↔dibujo o de recuento | Siempre `ubicacion = None`, aunque técnicamemte haya geometría cerca (p. ej. piezas fuera del cuadro) — son discrepancias de capa entera, no un punto del plano; no se infiere nada |
| Una vivienda con varias `Room` en `RECINTO_SIN_ETIQUETA`/`ETIQUETA_DUPLICADA` | El bbox es la unión de **todas** las implicadas, no sólo la primera |

---

## 7. Flujo del usuario

No hay flujo de usuario final en este PRD — es un contrato interno. El flujo
técnico: dado un DXF ya abierto (`doc`), `coherencia.revisar(doc, ...)` produce
una `Revision` cuyos `Hallazgo`s ya traen `ubicacion` cuando existe geometría
verificable, y cuyo `a_dict()` trae `recintos_geometria` con el polígono de
cada recinto. Un futuro cliente (test, CLI, o el visor del próximo prompt)
puede pintar el plano y encuadrar un hallazgo sin volver a abrir el DXF ni
parsear `entidad`.

---

## 8. Criterios de aceptación

1. Un test por cada tipo de hallazgo que SÍ lleva ubicación (SOLAPE,
   RECINTO_SIN_ETIQUETA, ETIQUETA_DUPLICADA, y POLILINEA_MAL_CERRADA/
   GEOMETRIA_DESCARTADA cuando el handle resuelve), verificando que el bbox
   contiene los puntos esperados de un DXF sintético.
2. Un test explícito por cada tipo que NO lleva ubicación (los cuatro de
   discrepancia cuadro↔dibujo, SIN_RECINTOS, y el caso de handle sin
   resolver), verificando `ubicacion is None`.
3. `Hallazgo.ubicacion` por defecto es `None` — no rompe ningún sitio que
   construya un `Hallazgo` sin pasarlo.
4. `Revision.a_dict()["recintos_geometria"]` verificado con al menos dos
   recintos reales.
5. El bbox de un hallazgo por handle está en las mismas unidades que las
   áreas del resto del informe (test que compara escala, no sólo presencia).
6. **Con UB-6 incluido:** un test de regresión que ejecute la Skill completa
   (`revision.coherencia_del_plano`) y confirme que `recintos_geometria`
   sobrevive hasta `Acta.a_dict()` — sin este test, el hallazgo del §9 R-1
   podría reintroducirse sin que nada lo avise.
7. Al cerrar: `Revision.a_dict()` completo de un DXF de test con al menos un
   SOLAPE, un RECINTO_SIN_ETIQUETA y un SIN_RECINTOS, mostrado para revisar
   el contrato real antes de tocar el SVG (pedido explícitamente en el
   encargo original).

---

## 9. Riesgos

**R-1 · El dato no llega a ningún sitio real sin un cambio más.** Verificado
leyendo `agente/skills/coherencia.py:_ejecutar()`: `PRODUCE` es una lista
cerrada de 5 nombres y `hechas` sólo construye una `Afirmacion` por cada uno.
`recintos_geometria` no está ahí. `agente/acta.py:levantar()` sólo copia
`afirmaciones`/`entregables`/`no_hecho` de lo que la Skill entregó — no hay un
paso posterior que "recupere" un campo olvidado. Sin una tarea que añada
`revision.recintos_geometria` al `PRODUCE`/`hechas` (mismo patrón que las 4
existentes), el campo existiría en `Revision.a_dict()` pero moriría en el
primer paso de la cadena real, y el objetivo técnico del §4 sería cierto sólo
para quien llame a la función Python directamente. *Mitigación:* UB-6 en el
plan de implementación — mecánica, ~30 min, mismo patrón ya usado 4 veces en
el mismo fichero.

**R-2 · `hallazgos[].ubicacion` sí sobrevive, y no hace falta tocar nada para
eso.** Verificado en la misma función: `hechas["revision.hallazgos"] =
calculo("revision.hallazgos", revision.get("hallazgos") or [], ...)` pasa la
lista de hallazgos **completa y sin filtrar campo a campo** — un campo nuevo
en cada `Hallazgo.a_dict()` viaja gratis. Asimetría real entre los dos campos
nuevos de este PRD, y por eso R-1 habla sólo de `recintos_geometria`.

**R-3 · No existe hoy ningún endpoint JSON para coherencia.** El único camino
HTTP (`/api/preguntar` → `_revisar_coherencia_y_renderizar_acta`) devuelve
HTML ya renderizado por `analyzer/acta_legible.py`, pensado para que lo lea un
humano, no para que lo consuma un visor con `fetch()`. El PRD del visor 2D
tendrá que decidir si añade un endpoint JSON nuevo o si extrae datos de la
página HTML — **este PRD no lo resuelve**, sólo lo deja escrito para que el
siguiente no lo descubra por sorpresa a mitad de implementación.

**R-4 · Escalado incorrecto es un fallo silencioso, no un crash.** El bbox
crudo de `ezdxf.bbox.extents()` está en unidades de dibujo; los `Room.polygon`
ya están escalados a metros por `parser.leer_plano` (`plano.escala.factor`,
aplicado con `origin=(0,0)`, confirmado en el código). Si el bbox por handle
no se multiplica por ese mismo factor antes de guardarse, el resultado no
falla — encuadra mal, en silencio, mezclando dos sistemas de unidades en el
mismo `Revision.a_dict()`. Es exactamente el bug class que `EscalaIndeterminada`
existe para evitar en el resto del pipeline. *Mitigación:* criterio de
aceptación §8.5, con test dedicado.

**R-5 · No compite con `REFACTOR_MASTERPLAN.md`.** Es aditivo: un campo nuevo
en dos dataclasses ya existentes, una función de resolución de bbox, y enhebrar
un parámetro `doc` por la cadena de llamadas ya existente. No toca `parser.py`
más allá de leer lo que ya expone (`Room.polygon`, `EntidadDescartada.handle`),
ni `evaluator.py`, ni el frontend.

---

## 10. Impacto sobre módulos existentes

**Se modifica:**
- `analyzer/coherencia.py` — `Hallazgo.ubicacion` + `a_dict()`; `_solapes`,
  `_rotulos` (ambos hallazgos), calculan bbox desde `Room.polygon.bounds` ya
  disponibles donde se construye el `Hallazgo` hoy; `_polilineas_mal_cerradas`
  y `_geometria_descartada` ganan resolución de bbox por `handle` (nueva
  función, p. ej. `_bbox_por_handle(doc, handle, factor)`); `revisar()` pasa
  `doc` a las dos funciones que lo necesitan (hoy no lo reciben — hay que
  enhebrarlo, `doc` ya está disponible en `revisar()`); `Revision.a_dict()`
  gana `recintos_geometria` desde `plano.rooms` (ya en memoria en `revisar()`,
  no hace falta releer nada).
- `agente/skills/coherencia.py` — `PRODUCE` gana `"revision.recintos_geometria"`;
  `_ejecutar()` gana una entrada más en `hechas` (UB-6, ver R-1). Ningún otro
  cambio: no toca las verificaciones existentes, y ninguna de ellas mira
  `ubicacion` ni `recintos_geometria`, así que no hay riesgo de que una
  verificación existente empiece a fallar por un campo que no conocía.

**Se consume sin modificar:**
- `analyzer/parser.py` — `Room.polygon` (`.bounds`), `PlanoLeido.escala.factor`,
  `EntidadDescartada.handle`. Ninguna función nueva aquí salvo que en
  implementación se decida que la resolución de bbox por handle vive mejor en
  `parser.py` que en `coherencia.py` (decisión de implementación, no de
  contrato — este PRD no la fija).
- `ezdxf.bbox.extents()` (parte de la dependencia ya instalada, `ezdxf==1.4.4`,
  confirmado) para resolver la geometría de una entidad por su handle sin
  reinventar el cálculo por tipo de entidad.

**No se toca:**
- `analyzer/acta_legible.py` — `_dato_revision_hallazgos` sólo lee
  `tipo`/`entidad`/`magnitud`/`unidad` de cada hallazgo (`h.get(...)`,
  verificado); un campo `ubicacion` adicional no le afecta. No se le añade un
  formateador para `recintos_geometria` en este PRD — no hay ninguna vista de
  texto que deba enseñarlo, es dato para un visor, no para el acta legible.
- `app.py` — nada. La ruta `/api/preguntar` ya usa
  `_revisar_coherencia_y_renderizar_acta` sin reconstruir el dict a mano
  (verificado); el problema real no está en `app.py`, está un paso antes, en
  la Skill (§9 R-1).
- `static/` — nada, por mandato explícito del encargo.

---

## 11. Plan de implementación dividido en pequeñas tareas

| # | Tarea | ~ | Depende |
|---|---|---|---|
| **UB-1** | `Hallazgo.ubicacion: Optional[Dict[str, Any]] = None` + `a_dict()`. | 0,5h | — |
| **UB-2** | Función de resolución de bbox por `handle` (`ezdxf.bbox.extents` + escalado por `plano.escala.factor`), con `None` defensivo si no resuelve. | 1h | — |
| **UB-3** | `ubicacion` en SOLAPE (`_solapes`) y en RECINTO_SIN_ETIQUETA/ETIQUETA_DUPLICADA (`_rotulos`): unión de `Room.polygon.bounds`. | 1h | UB-1 |
| **UB-4** | Enhebrar `doc` desde `revisar()` hasta `_polilineas_mal_cerradas` y `_geometria_descartada`; `ubicacion` por `handle` con UB-2, `None` si no hay handle o no resuelve. | 1,5h | UB-1, UB-2 |
| **UB-5** | `recintos_geometria` en `Revision.a_dict()` desde `plano.rooms`. | 0,5h | — |
| **UB-6** | `agente/skills/coherencia.py`: `revision.recintos_geometria` en `PRODUCE`/`hechas` — sin esto, R-1 deja el dato inalcanzable desde cualquier camino HTTP real. | 0,5h | UB-5 |
| **UB-7** | Los tests del §8 (1-6). | 1,5h | UB-1 a UB-6 |
| **UB-8** | Entregable de cierre: `Revision.a_dict()` completo de un DXF con SOLAPE + RECINTO_SIN_ETIQUETA + SIN_RECINTOS, para revisar el contrato antes del prompt del visor. | 0,5h | UB-7 |

Total ~7h.

---

## 12. Plan de pruebas

- **Unitarias sobre `analyzer/coherencia.py`**, reutilizando los DXF sintéticos
  que ya existen para cada tipo de hallazgo en `tests/test_preguntar_coherencia.py`
  y `tests/test_coherencia.py` — no se crean fixtures nuevas si las que hay ya
  cubren el caso.
- **De unidades:** un test que compare explícitamente el bbox de un hallazgo
  por handle contra el bbox de un `Room` vecino de área conocida, para pillar
  un error de escala (R-4) que un test de "no es `None`" no pillaría.
- **De regresión de la cadena Skill→Acta:** ejecutar
  `revision.coherencia_del_plano` end-to-end (mismo patrón que
  `tests/test_agente_skill_coherencia.py`) y comprobar que `recintos_geometria`
  aparece en el resultado final — el test que blinda contra que R-1 vuelva
  a colarse en un cambio futuro.
- **Sin red y sin clave**, como el resto de la suite de coherencia.

---

## 13. Métricas para medir el éxito

1. **De los hallazgos que se emiten en el próximo plano real, cuántos traen
   `ubicacion` no nula.** No es una cifra de vanidad: si en la práctica la
   mayoría de handles no resuelven, el visor que se construya encima tendrá
   que apoyarse mucho en el estado "sin ubicación, ver acta" y hay que saberlo
   antes de diseñarlo, no después.
2. **Cero bboxes en la unidad equivocada** en producción — condición, no
   métrica de éxito en sí: si esto falla, nada de lo demás importa (R-4).

---

## 14. Posibles motivos para NO implementar la idea

**1. Es infraestructura para un visor que todavía no tiene PRD aprobado.**
Se podría posponer hasta que el visor 2D esté aprobado de verdad, para no fijar
un contrato (`bbox` como caja envolvente) que la UI real podría necesitar de
otra forma — p. ej. el polígono exacto del hallazgo en vez de su envolvente,
si el visor quiere resaltar la forma real de un solape y no sólo su rectángulo.
*Mi respuesta:* el encargo ya fija `bbox` explícitamente y con motivo (es lo
mínimo que hace falta para encuadrar una vista, no para dibujar el hallazgo
en detalle) — construirlo ahora no cierra esa puerta, porque nada impide que
un `Hallazgo` futuro añada un campo de geometría más rico sin tocar `bbox`.

**2. Sin UB-6, esto es trabajo invisible.** El hallazgo real de este PRD (R-1)
es que `recintos_geometria` no llega a ningún sitio alcanzable sin ese cambio
en la Skill. Si Pablo aprueba sólo el modelo de datos puro (UB-1 a UB-5, UB-7
parcial) y deja UB-6 fuera, hay que decirlo con esas palabras al cerrar: la
capacidad existiría "de función Python", no como dato que un futuro visor
pueda pedir por HTTP.

**3. No hay todavía un segundo plano real contra el que medir cuántos handles
resuelven de verdad.** Igual que el PRD base midió sobre `v2s.dxf`, aquí no
hay cifra real de qué porcentaje de `POLILINEA_MAL_CERRADA`/`GEOMETRIA_DESCARTADA`
tendrán `ubicacion` no nula en un plano de verdad — sólo se sabe que
`ezdxf.bbox.extents` está disponible y funciona sobre entidades sintéticas.
*Mitigación parcial:* la métrica del §13.1 se mide en el primer plano real
después de implementar, no se estima aquí.

**Recomendación como CTO:** hacerlo, **con UB-6 incluido** — sin él, el
objetivo técnico del §4 queda incompleto de una forma que no se nota hasta que
alguien intenta construir el visor sobre él y descubre que el dato nunca llegó.
Es un PRD pequeño (~7h), no compite con `REFACTOR_MASTERPLAN.md`, y su mayor
valor no es el código en sí sino haber encontrado R-1 antes de escribir el
visor encima de un contrato que no llegaba a ningún sitio.

**4. Límite de alcance explícito, para que no quede implícito en ningún sitio.**
UB-6 cierra R-1 (el dato sobrevive hasta la `Afirmacion`/el acta interna) pero
**no** abre ningún endpoint JSON nuevo ni toca `/api/preguntar`. Si hoy ese
endpoint devuelve HTML renderizado, lo sigue haciendo exactamente igual al
cerrar este PRD. Un frontend que quiera leer `ubicacion`/`recintos_geometria`
por HTTP necesita un PRD/prompt aparte que decida cómo exponerlo — este PRD
dejó el dato listo para esa capa, no construyó esa capa.

---

**Decisión:** Aprobado por Pablo (2026-08-21), con UB-6 incluido. Alcance
confirmado: hasta la Afirmación/acta interna — no incluye JSON en
`/api/preguntar` ni cambios en `static/`.

---

## Addendum — Fase 2: exponer el contrato como JSON (2026-08-21b)

**Estado:** Aprobado · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo
(2026-08-21b, "Prompt 2")

### ¿PRD nuevo o extensión de éste? — la decisión pedida explícitamente

Pablo pidió comprobar esto antes de tocar código, con el mismo criterio que
la Fase 1. Aplicando [[feedback_archmuse_prd_first]] (PRD nuevo para
**capacidad nueva**; extensión/fix para lo que ya está evaluado):

- **No hay decisión de negocio nueva que evaluar.** El objetivo de negocio
  (§3) ya cubre esto explícitamente: "infraestructura de datos para el
  objetivo de negocio ya aprobado... hace posible que el visor, cuando
  exista, [comprobar en tres clics] se vuelva literal". Este addendum no
  cambia esa justificación, la ejecuta un paso más.
- **No hay lógica de dominio nueva.** No se toca `analyzer/coherencia.py` ni
  `agente/skills/coherencia.py` (confirmado al implementar: no hizo falta).
  Es serialización pura sobre un cálculo ya aprobado y ya verificado
  end-to-end en la Fase 1.
- **Ya estaba anticipado y con la pregunta ya planteada por este mismo PRD**:
  R-3 dice literalmente "El PRD del visor 2D tendrá que decidir si añade un
  endpoint JSON nuevo..." — esto no es un tema que aparece de la nada, es la
  continuación declarada de la Fase 1, no una capacidad que nadie evaluó.
- **No crece el registro de capacidades** (`agente/registro.py`, guardián
  C4): es una ruta Flask nueva sobre una función ya existente
  (`_revisar_coherencia_y_levantar_acta`), no una `Capacidad` ni una `Skill`
  nueva.
- **Riesgo bajo y acotado**: sólo lectura, sin normativa, sin nueva
  superficie de negocio, mismo control de acceso/autorización que ya
  protege el camino HTML (`SEG-1`, autorización de `ESCRIBE_FICHERO` para el
  informe PDF que la Skill sigue generando de paso).

**Decisión: extensión de este PRD (Fase 2), no un documento nuevo.** Si
alguna vez esto creciera hacia algo con más superficie (autenticación,
paginación, un contrato versionado, caché entre peticiones), eso sí sería
capacidad nueva y pediría su propio PRD — no es el caso de una ruta de
sólo lectura que reexpone un cálculo ya aprobado.

### Decisión de diseño: endpoint nuevo, no un parámetro de `/api/preguntar`

`/api/preguntar` (`app.py:3342`) hace dos cosas antes de ejecutar nada: exige
`ANTHROPIC_API_KEY` y llama al LLM para clasificar la intención
(`_capacidad_que_coincide`) — un coste y una dependencia real, por diseño
(es la puerta de lenguaje natural). Un futuro visor que ya sabe que quiere
`revision.coherencia_del_plano` no tiene ninguna intención que clasificar:
forzarlo a pasar por el LLM para pedir datos que ya sabe que quiere sería
imponerle un coste y una dependencia (la clave de API) que no le hacen
falta, y que hoy además puede fallar con 502/503 por motivos que no tienen
nada que ver con el DXF.

El propio código ya nombra el patrón a seguir, en el docstring de
`/api/preguntar`: "el mismo camino que usaría su propio endpoint dedicado si
lo tuviera (`/api/acta-legible` para medición; **para coherencia no hay
endpoint propio**, sólo esta puerta)". Medición ya tiene su puerta directa
sin LLM (`/api/acta-legible` → `_medir_planta_y_renderizar_acta`); a
coherencia le faltaba la suya. Este addendum se la da, y de paso resuelve el
hueco que el propio comentario señalaba.

**`POST /api/coherencia-datos`** — mismos parámetros de formulario que
`/api/acta-legible`/`/api/preguntar` para esta Skill (`dxf`, `capa`,
`escala`, `autorizar_efectos`), sin `pregunta` y sin tocar el LLM. Llama a
`_revisar_coherencia_y_levantar_acta` (la misma función que ya usa el
camino HTML, sin duplicarla) y mapea el `dict` del acta que ya devuelve —
no ejecuta la Skill dos veces con lógicas distintas, ejecuta la misma
función una vez por petición, igual que cualquier otro endpoint de este
fichero.

### Forma del JSON — subconjunto directo, nombres estables

```json
{
  "recintos_geometria": [{"label": ..., "layer": ..., "puntos": [[x, y], ...]}],
  "hallazgos": [{"tipo": ..., "descripcion": ..., "ubicacion": {"bbox": [...]} | null}]
}
```

Mismos nombres que ya usa `Revision.a_dict()`/la Afirmación — no se inventa
vocabulario nuevo. `hallazgos` no repite `entidad`/`magnitud`/`unidad`/
`detalle`: el visor (prompt aparte) sólo necesita `tipo`+`descripcion` para
etiquetar y `ubicacion` para encuadrar; el resto sigue disponible en el acta
completa para quien lo necesite. Si un futuro prompt del visor pide más
campos, se añaden ahí — no es una decisión que este addendum tenga que
cerrar de más.

### Riesgos

**R-6 · Dos rutas HTTP ejecutando la misma Skill por separado.** Cada
petición HTTP procesa su propio DXF subido — no hay caché ni estado
compartido entre una llamada a `/api/preguntar` y una a
`/api/coherencia-datos` sobre "el mismo" plano; son dos ejecuciones
independientes de la misma función, no una compartida. Es el mismo patrón
que ya existe entre `/api/acta-legible` y `/api/preguntar` para medición —
no es un patrón nuevo que este addendum introduzca, y no se resuelve aquí
(cachear resultados sería una capacidad nueva de verdad, con sus propios
riesgos de invalidación).

**R-7 · Endpoint de sólo lectura pero que de camino escribe un PDF.**
`_revisar_coherencia_y_levantar_acta` invoca la Skill completa, que incluye
`plano.informe_de_coherencia` (escribe el informe PDF a un fichero temporal)
— no hay forma de pedir sólo los campos JSON sin que ese efecto ocurra
también, porque es la misma función que ya usa el camino HTML. Sigue
protegido por `SEG-1` (`autorizar_efectos`) exactamente igual. No se separa
en este addendum: separar "sólo mirar" de "mirar y escribir el PDF" para
esta Skill sería tocar `agente/skills/coherencia.py`, y el encargo pide no
tocarlo salvo necesidad probada — no lo es, sólo es menos elegante.

### Criterios de aceptación

1. `POST /api/coherencia-datos` devuelve `{"recintos_geometria": [...],
   "hallazgos": [...]}` con al menos un hallazgo con `ubicacion` no nula y
   uno con `ubicacion: null`, sobre un DXF sintético con ambos casos.
2. El HTML de `/api/preguntar` para coherencia es idéntico byte a byte a
   antes de este addendum (test de regresión explícito).
3. `/api/coherencia-datos` no requiere `ANTHROPIC_API_KEY` ni llama al LLM.
4. Un test demuestra que el mapeo a JSON es una función pura sobre el
   `dict` del acta (no reconstruye nada desde `coherencia.revisar`
   directamente).

### Plan de implementación

| # | Tarea | ~ |
|---|---|---|
| **JS-1** | `_coherencia_a_json(documento)` en `app.py`: mapeo puro del acta a `{"recintos_geometria", "hallazgos"}`. | 0,5h |
| **JS-2** | `POST /api/coherencia-datos`: mismo patrón de validación que `acta_legible_endpoint`, llama a `_revisar_coherencia_y_levantar_acta` + `_coherencia_a_json`. | 0,5h |
| **JS-3** | Tests: forma del JSON (con y sin ubicación), HTML sin cambios, sin LLM, mapeo puro. | 1h |

Total ~2h.

**Decisión:** Aprobado por Pablo (2026-08-21b). No requiere PRD nuevo.
