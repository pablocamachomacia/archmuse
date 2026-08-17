# PRD — Paso 0 rápido (desacople de Overpass) y detección de parcela matriz

**Estado:** Punto 2 implementado (alcance §14) · Punto 3 sin implementar, pendiente de investigación · **Fecha:** 2026-08-17 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (vía "EJECUCIÓN DE PRD", punto 2 únicamente)

---

## 0. Nota de proceso

Encargo recibido: "MEJORA CRÍTICA: UX DE ESPERA, OPTIMIZACIÓN DE TIEMPO Y RESOLUCIÓN DE FINCA MATRIZ", con 3 instrucciones. La 1ª (mensajería de paciencia en `entrevista.js`) es un añadido puramente de texto/UI sobre un mecanismo de progreso ya existente (`docs/prd/2026-08-16-resiliencia-catastro-paso0.md`) — sin riesgo de dato fabricado, sin tocar arquitectura — se implementó directamente, ya está en producción y verificada en vivo (dos mensajes nuevos, a 8s y 25s, confirmados en pantalla).

Las otras 2 (desacople de Overpass del Paso 0, y detección de "parcela matriz") son capacidad nueva real, no correcciones de bug:

- La 2ª choca directamente con una línea explícita de `REFACTOR_MASTERPLAN.md` (§ alcance): *"cola de trabajos en segundo plano... ya están recogidos como Fase 2 del roadmap... fuera de alcance deliberadamente"* — es decir, "mover una consulta pesada a un proceso en segundo plano" es, por definición del propio proyecto, funcionalidad nueva, no un endurecimiento de lo que ya existe.
- La 3ª introduce un concepto (`parcela_matriz`) que no existe hoy en ningún servicio ya integrado (`Consulta_RCCOOR`, WFS `GetParcel`) ni en el código — no es "corregir" una función que ya intenta hacer esto y falla, es construir un mecanismo nuevo desde cero, con una heurística (superficie < 500 m²) que, comprobado contra un caso real de esta misma sesión, clasificaría mal una parcela genuina.

Por la regla de proceso del proyecto, este PRD va primero para las dos, código después de aprobación explícita.

## 1. Problema que resuelve

1. **Paso 0 puede tardar más de 2 minutos** cuando Overpass está lento (127s medidos en vivo hoy mismo, ver PRD de ayer) — de los cuales la parte que el arquitecto necesita de verdad para continuar (RC + polígono + superficie) suele estar lista en pocos segundos; el resto (colindantes/viales/zonas verdes/equipamientos) tarda porque Overpass tarda, no porque haga falta esperarlo para dibujar la parcela.
2. **Un clic sobre el tejado de una vivienda unifamiliar/pareada a veces resuelve a una referencia catastral de una parcela más pequeña de la esperada** — descrito en el encargo como "subparcela de la edificación" frente a la "finca matriz" real.

## 2. Usuario afectado

El mismo de siempre en Paso 0: el arquitecto que selecciona su parcela antes de empezar a proyectar. Ambos problemas le afectan en el momento de mayor fricción ya identificado (selección de parcela).

## 3. Objetivo de negocio

Menos abandono en Paso 0 (mismo objetivo que el PRD de ayer). El punto 2 (finca matriz), si es un problema real y no un malentendido de un caso concreto, evita que el arquitecto proyecte sobre una parcela equivocada — un error mucho más caro de arrastrar (normativa, cabida, todo el resto del análisis) que una espera larga.

## 4. Objetivo técnico

- Que dibujar el contorno de la parcela en Paso 0 no dependa de que Overpass responda.
- Que un clic sobre una vivienda dentro de una parcela real y completa siga devolviendo esa parcela completa, nunca una fracción de ella — pero solo si "fracción" es un caso real y demostrado, no una suposición sobre el tamaño.

## 5. Lo que YA EXISTE (no reinventar)

- **Mensajería de paciencia** (punto 1 del encargo): implementada hoy mismo, `static/entrevista.js` (`UMBRAL_FASE_PROCESANDO_MS` = 8000, `UMBRAL_FASE_SIGUE_BUSCANDO_MS` = 25000), verificada en vivo.
- **`/api/entorno-3d-punto`** (Sandbox, PRD de ayer) ya resuelve `geometria_parcela_por_coordenadas` (RC + WFS) por separado de `edificios_colindantes_geometria` (Overpass) — es decir, el patrón "geometría de parcela sin esperar a Overpass" **ya existe como función**, solo no se usa así en Paso 0 todavía.
- **`generar_checklist_campo`** (`analyzer/checklist_campo.py`) ya degrada con normalidad si `colindantes`/`viales`/`zonas_verdes` vienen vacíos — cada nota (`_nota_colindantes`, `_nota_viales`, `_nota_zonas_verdes`) devuelve `None` y el ítem se queda sin el detalle extra, nunca rompe ni inventa un dato. Esto importa para el punto 2 del encargo: hoy `/api/proyectos/<id>/checklist-campo` LEE `colindantes`/`viales`/`zonas_verdes` del mismo `sitio.datos` que cachea `/api/analizar-sitio` — si Paso 0 deja de pedirlos, el checklist de campo pierde esas notas a menos que se rellenen después por otra vía.
- **Caché SQLite exacta por celda** (`storage.sitios`, PRD de ayer) — la vía natural para que un "relleno en segundo plano" no dependa de un job en servidor.

## 6. Casos límite y hallazgos que cambian el enfoque

### Sobre el punto 2 (desacoplar Overpass)

- **`colindantes`/`viales`/`zonas_verdes` de `/api/analizar-sitio` SÍ tienen un consumidor real aguas abajo**: `/api/proyectos/<id>/checklist-campo` (`app.py`, "Checklist de inspección en campo", PRD 2026-08-16). Quitarlos del Paso 0 sin más degrada silenciosamente esa función más adelante en el flujo (menos notas, no un error) — hay que decidir explícitamente si eso es aceptable o si hace falta rellenarlos después.
- **`REFACTOR_MASTERPLAN.md` excluye explícitamente una "cola de trabajos en segundo plano"** como fuera de alcance de endurecimiento — cualquier solución de servidor con hilos/colas propias contradice esa decisión ya tomada. La alternativa que SÍ encaja sin inventar infraestructura nueva es un **segundo fetch "fire-and-forget" lanzado por el propio cliente** (el navegador ya tiene la pestaña abierta) contra un endpoint que YA existe en espíritu (`/api/entorno-3d-punto` ya hace esto para el Sandbox) — el servidor sigue siendo síncrono y sin estado de cola, solo se le pide dos veces: una vez rápida (RC+geometría) y otra, en paralelo, más lenta (Overpass), sin que el cliente espere a la segunda para continuar.
- **`equipamientos`** (radio 1000 m) no tiene ningún consumidor encontrado fuera de `analyzer/sitio.py` — es candidato claro a quitar del camino rápido sin que nada aguas abajo lo note, con o sin relleno posterior.

### Sobre el punto 3 (parcela matriz)

- **El caso de prueba más reciente de esta sesión contradice la heurística tal como está escrita**: la parcela real de Montepríncipe resuelta hoy mismo (RC `8433219VK2783S`, vivienda pareada en Boadilla del Monte) tiene **300 m² reales, completos, correctos** — no es una subparcela de nada, es el tamaño real y normal de una parcela unifamiliar pareada en esa zona. Un umbral "< 500 m² en zona unifamiliar/pareada → busca la matriz" clasificaría MAL esta parcela real y buena, e intentaría "corregirla" hacia una finca envolvente que no existe o que no le corresponde — exactamente el tipo de dato mostrado como real que no es el del punto exacto que el resto de este proyecto evita sistemáticamente (mismo principio que ya rechazó la caché por proximidad difusa ayer).
- **No hay ningún servicio ya integrado que exponga el concepto "parcela matriz"**: `Consulta_RCCOOR` devuelve una RC de 14 caracteres (`pc1`+`pc2`); el WFS `GetParcel` la resuelve a un polígono. Ninguno de los dos, en la forma en que ya están integrados, distingue "unidad dentro de una propiedad horizontal" de "parcela completa". El Catastro real SÍ tiene un concepto de propiedad horizontal (edificaciones con "elementos" — pisos/locales — bajo una misma finca), pero validarlo requeriría una PoC contra el servicio real con un caso reproducible, igual que se hizo para el resto de este módulo (ver docstring de `analyzer/sitio.py`, "validado contra los servicios reales antes de escribir este módulo").
- El propio encargo no da un caso reproducible verificado (a diferencia del PRD del 16-ago, que sí pedía explícitamente "localizar una edificación real de Montepríncipe donde el punto exacto falla" antes de construir la espiral) — sin uno, cualquier heurística de tamaño es una suposición, no un hallazgo.

## 7. Flujo del usuario

- Punto 2: sin cambio visible salvo la velocidad — Paso 0 muestra el contorno azul en segundos en vez de hasta 2 minutos; colindantes/viales, si se rellenan después, lo hacen sin que el arquitecto tenga que esperarlos ni volver a pedirlos.
- Punto 3: sin cambio de flujo salvo, si se confirma el problema, que el contorno mostrado sea el de la finca completa en vez de una fracción — mismo tipo de interacción (clic → contorno azul).

## 8. Criterios de aceptación

**Punto 2** (si se aprueba):
1. `/api/analizar-sitio` responde con RC + geometría + superficie en el tiempo que tarda solo Catastro (WFS), sin esperar a las 4 consultas de Overpass — mejora medible frente a los 127s ya documentados.
2. El checklist de campo, para un proyecto consultado después de que el relleno en segundo plano haya tenido tiempo de completarse, sigue mostrando las mismas notas de colindantes/viales/zonas verdes que hoy — criterio de "no regresión silenciosa".
3. Ningún cambio introduce una cola/worker/proceso en segundo plano en el servidor (respeta la exclusión de `REFACTOR_MASTERPLAN.md`).

**Punto 3** (si se aprueba, y solo tras la investigación de §14):
1. Al menos 2 casos reales reproducibles y verificados en vivo donde el punto exacto resuelve hoy a una parcela que un experto confirmaría como incorrecta (subparcela), con la RC de la parcela matriz real esperada.
2. La corrección nunca cambia una parcela ya correcta (como el caso de 300 m² de Montepríncipe de esta sesión) — verificable contra ese caso como caso de control negativo.

## 9. Riesgos

- **Punto 2**: un "fire-and-forget" desde el cliente que nadie espera puede fallar en silencio si el usuario cierra la pestaña antes de que termine — hay que decidir qué pasa con el checklist de campo en ese caso (¿se reintenta al entrar al Sandbox o al checklist, si el relleno no llegó a tiempo?). Compite con tiempo de otras tareas de `REFACTOR_MASTERPLAN.md`.
- **Punto 3**: el riesgo principal ya está en §6 — implementar la heurística tal como está escrita puede ACTIVAMENTE empeorar casos que hoy funcionan bien, sustituyendo una parcela real y correcta por una búsqueda de "matriz" mal fundamentada. Este es el mismo tipo de riesgo (dato mostrado como real que no corresponde al punto exacto) que este proyecto ya ha rechazado dos veces esta semana (caché por proximidad difusa, PRD de ayer) — coherencia importa.

## 10. Impacto sobre módulos existentes

- `app.py`: `analizar_sitio()` cambiaría de forma (qué se cachea, cuándo); posible nuevo endpoint o parámetro para el relleno en segundo plano de colindantes/viales/zonas verdes.
- `analyzer/sitio.py`: `obtener_datos_parcela` tendría que poder llamarse en dos "modos" (solo Catastro / solo Overpass) en vez de uno combinado — cambio de firma o nueva función, a decidir en fase de implementación.
- `analyzer/checklist_campo.py`: sin cambio de código si se opta por rellenar después la misma caché; si no, sus notas se degradan (aceptable o no, decisión de Pablo).
- `static/entrevista.js`: el fetch de Paso 0 pasaría a ser más rápido, y un segundo fetch en paralelo (no bloqueante) para colindantes/viales.

## 11. Plan de implementación dividido en pequeñas tareas

*(Solo tras aprobación explícita — y, para el punto 3, solo tras completar la investigación de §14 con casos reales.)*

**Punto 2:**
1. Separar `obtener_datos_parcela` en una función que resuelve solo RC+geometría y otra que resuelve solo Overpass (o parámetro que desactive Overpass), sin romper `/api/analizar-sitio` cuando se llama con RC ya conocida (import de pliego, etc. — revisar todos los llamadores antes de tocar la firma).
2. `analizar_sitio()` responde con RC+geometría en cuanto están listos; lanza el resto en un segundo request client-side (o documentar la alternativa elegida si Pablo prefiere otra).
3. Verificar que `checklist-campo` sigue recibiendo colindantes/viales/zonas verdes una vez el segundo fetch termina.

**Punto 3:**
1. PoC acotada (como la del propio `analyzer/sitio.py`, "validado contra los servicios reales antes de escribir el módulo"): encontrar y confirmar en vivo al menos un caso real de "clic en tejado → RC de subparcela" con una fuente fiable de cuál sería la RC correcta de la matriz.
2. Solo si el caso se confirma: diseñar la detección real (no heurística de tamaño) basada en lo que el servicio de Catastro devuelva de verdad para ese caso.
3. Si no se confirma ningún caso reproducible, cerrar este punto como "no reproducido" en vez de construir una corrección para un problema no demostrado.

## 12. Plan de pruebas

Punto 2: medir tiempo de respuesta de Paso 0 antes/después con Overpass en su estado actual (degradado); confirmar que el checklist de campo no pierde notas para un proyecto consultado con margen de tiempo.
Punto 3: contra los casos reales de §11.1, más el caso de control negativo de Montepríncipe (300 m², no debe tocarse).

## 13. Métricas para medir el éxito

Punto 2: tiempo de respuesta de `/api/analizar-sitio` (objetivo: <5s con Catastro sano, acotado por Catastro con Overpass degradado — no por Overpass).
Punto 3: nº de casos reales corregidos vs. nº de parcelas correctas que la corrección deja intactas (objetivo: 0 falsos positivos sobre el caso de control).

## 14. Posibles motivos para NO implementar la idea tal como está escrita

**Punto 1 (mensajería): ya implementado, sin objeción — bajo riesgo, alto valor inmediato.**

**Punto 2 (desacople de Overpass): la idea tiene valor real, pero "segundo plano" tal como está escrito en el encargo no es viable sin contradecir una decisión ya tomada** (`REFACTOR_MASTERPLAN.md` excluye colas de trabajo en segundo plano). Recomendación: aprobar una versión que logre el mismo resultado (Paso 0 rápido) con un mecanismo más simple — un segundo fetch no bloqueante lanzado por el propio cliente, que rellena la misma caché SQLite ya existente — en vez de infraestructura de cola en el servidor. Esto requiere antes decidir qué pasa con `checklist-campo` si el arquitecto llega a él antes de que ese segundo fetch termine (degradación aceptada, o reintento en ese punto).

**Punto 3 (parcela matriz): no recomiendo construir esto todavía, tal como está escrito.** La heurística de tamaño (<500 m² en zona unifamiliar/pareada) ya falla contra un caso real y verificado de esta misma sesión (300 m², parcela correcta, no una subparcela) — implementarla como está escrita activamente empeoraría ese caso, no lo mejoraría. No existe hoy ningún hallazgo confirmado en vivo (a diferencia de la espiral de proximidad del 16-ago, que sí partió de un caso real localizado antes de escribir código) de que el problema descrito ocurra de verdad con los servicios ya integrados. Recomendación: antes de diseñar una corrección, localizar y confirmar en vivo al menos un caso real reproducible (§11, tarea 1) — si no aparece ninguno, cerrar este punto como no reproducido en vez de construir una heurística especulativa que arriesga mostrar datos de una parcela que no es la real.

---

## 15. Cierre — implementación y verificación en vivo (2026-08-17)

Implementado exactamente el punto 2 en el alcance reducido de §14 (fetch no bloqueante desde el cliente, sin cola/worker en el servidor). Punto 3 (parcela matriz) sigue sin implementar — no llegó ninguna aprobación para él ni la investigación previa que este mismo PRD pedía como condición.

**1. Respuesta rápida (`analyzer/sitio.py`)**: `obtener_datos_parcela` gana `incluir_overpass: bool = True` (por defecto, sin cambio de comportamiento para tests y otros llamadores). El bloque de las 4 consultas de Overpass se extrajo a `_entorno_overpass`/`entorno_overpass_por_coordenadas` (reutilizable), y un nuevo campo `entorno_consultado` distingue "todavía no pedido" de "pedido y sin resultados".

**2. Endpoint (`app.py`)**: `/api/analizar-sitio` sin `solo_entorno` ahora llama con `incluir_overpass=False` — responde con RC + geometría + superficie en cuanto Catastro/WFS resuelve, sin esperar a Overpass. Con `solo_entorno: true` (requiere `lat`/`lon`), busca la fila ya cacheada, pide el entorno de Overpass y la actualiza in situ — idempotente: si `entorno_consultado` ya es `true`, no repite las 4 consultas.

**3. Cliente (`static/entrevista.js`)**: en cuanto se pinta la parcela con la respuesta rápida (si hay `referencia_catastral`), dispara `apiFetch(..., solo_entorno: true)` sin esperarlo — nadie bloquea la UI por él.

**Verificado en vivo:**
- Curl, coordenada fresca sin cachear (Madrid, Marqués de la Ensenada): respuesta rápida en **0.89s**, `entorno_consultado: false`, RC y polígono reales completos.
- Curl, mismo punto con `solo_entorno: true`: 126.6s (Overpass sigue degradado, mismo problema externo de toda la sesión — errores capturados con normalidad, nunca bloquea), `entorno_consultado: true` al terminar.
- Repetido `solo_entorno: true` una tercera vez sobre el mismo punto: 0.42s, **cero llamadas nuevas a Overpass** (idempotencia confirmada).
- Navegador real: clic sobre un tejado en Calle Alcalá (Madrid) sin cachear — parcela real dibujada (RC `0645402VK4704D`, 6301 m²) en **menos de 2s**; `read_network_requests` confirmó 2 peticiones a `/api/analizar-sitio`: la primera ya resuelta (200), la segunda (`solo_entorno`) todavía `pending` sin bloquear nada visible — el arquitecto puede continuar de inmediato.

Sin regresiones: `python -m py_compile` limpio en `app.py`/`analyzer/sitio.py`, `node --check` limpio en `entrevista.js`.

---

**Decisión:** Punto 2 implementado 2026-08-17 con el alcance reducido de §14, verificado en vivo. Punto 3 queda abierto — recomiendo no construirlo sin antes completar la investigación de §11 (casos reales reproducibles).
