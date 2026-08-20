# PROGRESS — qué se hizo, qué se dejó fuera, qué se decidió

Lo pide el §0.5 de `ARCHMUSE_SPEC.md`: al terminar cada bloque, escribir qué se
hizo, qué se dejó fuera y qué decisiones se tomaron. Lo más reciente arriba.

---

## 2026-08-20 (madrugada, 4ª hora) · Fase A del PRD de procedencia de parcela -- hecha

**Modelo confirmado Sonnet** (Sonnet 5, sin cambios en toda la sesión) antes de
empezar, según pediste.

PRD aprobado: `docs/prd/2026-08-20-procedencia-y-fecha-de-datos-de-parcela.md`,
con tus tres notas incorporadas (§6 sin decidir la ubicación de `map-picker.js`,
recorte del §14 descartado, y esta misma respuesta sobre cobertura de tests).

**Respuesta a tu pregunta antes de empezar (consumidores protegidos):**
`checklist_campo.py` tenía CERO tests -- añadido `tests/test_checklist_campo.py`
(7 tests). `viewer-sandbox.js` (vía `/api/entorno-3d-punto`) tenía test de
endpoint pero sin mockear `geometria_parcela_por_coordenadas` (fuga de red real
no detectada hasta ahora) ni afirmar sobre ese campo -- arreglado y afirmado en
`tests/test_entorno_3d.py`. `pliego_extractor.py` no era en realidad un
consumidor (corrección a mi propia auditoría anterior: su `referencia_catastral`
es un campo homónimo que un LLM extrae del pliego del cliente, sin relación con
`/api/analizar-sitio`).

**Hallazgo real durante la implementación, no relacionado con procedencia:**
CP-4 (parcela real en `/mvp`, dada por "cableada" el 19-ago) estaba rota desde
que se escribió -- `mvp.js::elegirParcela()` leía `datos.geometria`/
`datos.referencia_catastral` en la raíz de la respuesta, que nunca ha existido
ahí (`/api/analizar-sitio` envuelve todo en `{sitio: {datos: {...}}}`, y el
campo se llama `geometria_parcela`). La rama de éxito nunca se disparó.
`tests/test_mvp_parcela_real.py` es inspección de texto fuente, nunca ejecutó
el JS de verdad, así que nunca pudo pillarlo. Arreglado junto con la
procedencia (misma función, mismo commit) -- anotado en
`docs/AGENTE_BACKLOG.md` (CP-4) con el detalle completo.

**Implementado:**
- `analyzer/sitio.py`: `_procedencia()` (dict simple, NO se reutiliza
  `agente.afirmacion.Afirmacion` -- acoplada a Capacidad/C4, exactamente lo
  prohibido; sigue el espíritu más ligero de `normativa.ambito.Procedencia`,
  documentado en el propio código). `obtener_datos_parcela()` la adjunta en
  los dos caminos reales (RC directa, lat/lon → RC → geometría); se queda en
  `None` si no hubo geometría real -- nunca inventada.
- `app.py`: `de_cache` se corrige a `True` en el camino de caché (única pieza
  que `analyzer/sitio.py` no puede saber por sí solo); filas guardadas antes
  de esta tarea (sin `procedencia`) se dejan tal cual, nunca se rellenan a
  posteriori.
- `entrevista.js`/`mvp.js`: fecha + fuente visibles en el bloque de resultado
  ("Consultado el ..." / "Ya consultado antes, el ..."), mismo criterio en
  los dos ficheros (`fechaLegibleProcedencia`, duplicada a propósito -- son
  scripts clásicos sin módulo compartido).

**A continuación, REFACTOR_MASTERPLAN tarea 27 (mitad -- el parámetro `unit`
sin usar, no los 106 `PERF401` reales que quedan):** `evaluate_acoustic_
exposure()` en `analyzer/evaluator.py` no usaba su parámetro `unit` en ningún
sitio del cuerpo (0 usos, verificado); un solo punto de llamada. Retirado de
la firma y del único call site. Suite completa: 1065 passed (mismo número
que antes -- es refactor puro, sin tests nuevos), 2 failed (mismos guardianes
C4), 18 skipped, 580s. `REFACTOR_MASTERPLAN.md` actualizado.

**Después del push que pediste, hallazgo grande al mirar INF-1 (CI en
GitHub Actions):** el backlog llevaba desde el 19-ago creyendo que el
workflow "existe sin ejecutar". Falso -- comprobado con `gh run list`:
lleva corriendo en CADA push de esta sesión desde las 09:57, **en rojo,
sin que nadie lo hubiera mirado**. La causa real: `tests/test_entorno_3d.py`
no mockeaba `geometria_parcela_por_coordenadas` en tres de sus secciones
(3.2, 3.3, 4 -- solo arreglé la 4 en el commit de Fase A) y golpeaba
Catastro de verdad en CI (que sí tiene salida a internet, a diferencia de
este entorno de desarrollo). Arreglado en las tres. Verificado con `gh run
view` sobre el último push: **2 fallos, los mismos dos guardianes C4 de
siempre** -- ya no hay ninguna señal espuria. `docs/AGENTE_BACKLOG.md`
(INF-1) corregido con el detalle completo, incluida la pregunta que dejo
para Pablo: si "terminado" exige status verde literal (lo que pediría
marcar los guardianes C4 como `xfail`, tocando cómo CI trata D-12) o si
el criterio real ya está cumplido tal como está. No lo decido -- es
territorio C4.

**Verificado:** suite completa 1065 passed (+8 desde el baseline de la
tarea anterior), 2 failed (mismos guardianes C4 de siempre), 18 skipped,
581s. Tests nuevos: `test_checklist_campo.py` (7), extensión de
`test_sitio.py` (procedencia presente/ausente en los dos caminos),
`test_entorno_3d.py` (geometria_parcela + cierre de la fuga de red que
tenía ese mock), `test_analizar_sitio_procedencia.py` (nuevo, HTTP end-to-
end: primera consulta, segunda desde caché con fecha original y `de_cache`
correcto, y una fila sin procedencia que no se rellena a posteriori).
Commit local hecho, y subido a GitHub (pediste "actualiza con github" a
mitad de esta tarea) junto con el resto de commits pendientes de la sesión.

**Confirmado con `gh run watch` sobre el push del arreglo de red:** CI
completo, 95s, **2 failed, 1041 passed, 43 skipped -- exactamente los
mismos dos guardianes C4 de siempre, ninguna señal espuria más.** INF-1
queda en el estado real descrito en `docs/AGENTE_BACKLOG.md`.

**Cierre de esta ronda del backlog:** revisado REFACTOR_MASTERPLAN entero
(8/14/20 hechas, 27 mitad hecha, 15/26 descartadas por diseño ya antes de
hoy, 16/19/21/22-24/28-29 demasiado grandes o con secuencia explícita que
las bloquea hasta la 16) y los ítems `PRD: no` de `AGENTE_BACKLOG.md` sin
BIM/normativa/capacidad nueva -- todos los que quedan tienen una
dependencia `PENDIENTE` real (INF-2, INF-4, INF-5, INF-7, ME-2, TL-3,
TL-4, SEG-3, SEG-4) o están bloqueados por una decisión humana (`D-6`,
`D-7`, un colegiado firmando `SK-5`). No queda nada que pueda tocar sin
cruzar un límite duro o inventar alcance por mi cuenta. Paro aquí.

---

## 2026-08-20 (madrugada) · Trabajo autónomo (1h, sin parar a preguntar) -- checkpoints

`[00:00]` Arranque: termina el rediseño de cabecera pendiente (selector de
modo compacto + botón de enviar sólo icono + quitar `required`). Suite
completa verde antes de tocar nada nuevo: 1057 passed, 2 failed (los mismos
guardianes C4 de siempre), 18 skipped.

`[00:05]` Cabecera terminada y verificada por DOM (los screenshots del
navegador dieron timeout intermitente en esta sesión -- verificación por
JS directo en su lugar, más precisa): desplegable con 5 ítems (2
seleccionables con marca ✓, 3 "próximamente" deshabilitadas), botón de
enviar `disabled` de verdad en vacío y activo al escribir, `required` fuera
del textarea. Suite completa: 1057 passed, 2 failed (mismos de siempre),
18 skipped, 521 s. Commit local hecho (sin `git push`, según instrucción).

`[00:15]` Hallazgo 4 del informe de test (2026-08-20): el guardián de
capitalización de `test_agente_escritura.py` fallaba en Linux/CI porque
`Plano.dxf`/`plano.dxf` genuinamente NO son el mismo fichero ahí -- el
código de producción (`os.path.normcase`) ya hacía lo correcto, era el test
el que asumía Windows sin condición. Arreglado con
`@pytest.mark.skipif(_FS_SENSIBLE_A_MAYUSCULAS, ...)`, usando el mismo
primitivo (`os.path.normcase`) que la guarda real, no `sys.platform`.
Verificado: sigue pasando (no se salta) en esta máquina Windows.

**Decisión aparcada, no ejecutada (requiere tu criterio):** el hallazgo 5
del mismo informe (`test_entorno_3d.py` llama a Overpass de verdad pese a
su docstring) recomienda bloquear `socket.socket` por defecto en
`conftest.py`. No lo hice: `conftest.py` declara explícitamente en su propia
cabecera que existe "por tres motivos concretos, y no hace nada más" --
añadir un bloqueo de red global sería un cuarto motivo, cambiaría el
comportamiento de TODA la suite (riesgo de romper algo que hoy sí necesita
un socket local, p.ej. el cliente de test de Flask) y no es algo que deba
decidir yo solo sin supervisión. Sigo con otra cosa.

`[00:35]` Tarea 8 del REFACTOR_MASTERPLAN (`ruff` + `pyproject.toml`,
"congela lo aprendido en esta auditoría"): instalado `ruff==0.16.3`,
config en `pyproject.toml` con el conjunto de reglas que nacen de defectos
reales ya encontrados en este repo (E/W/F/B/C4/SIM/PERF, no una plantilla
genérica). Línea base: **277 hallazgos**. Apliqué solo los **59 arreglos
seguros** (`ruff check . --fix`, sin `--unsafe-fixes`) -- casi todos
imports sin usar. Los 65 "unsafe" y los ~159 restantes (106 son
`PERF401`, comprehensiones manuales) **no se tocan**: cambiar lógica de
verdad sin que tú lo revises no es housekeeping, es riesgo. Suite completa
tras el fix: 1057 passed, 2 failed (mismos guardianes C4 de siempre), 18
skipped -- idéntico al baseline de antes de tocar nada. Commit local hecho.

---

## 2026-08-20 (madrugada, 2ª hora) · Diagnóstico y arreglo real del selector de modo

Pablo reportó por verificación propia en el navegador: "el selector 'Medir
superficies' no funciona". Diagnóstico pedido explícitamente antes de
tocar nada.

**Diagnóstico:** el desplegable SÍ abre y SÍ deja seleccionar (confirmado
por DOM: 5 ítems correctos, marca ✓ en el activo, las 3 "próximamente"
deshabilitadas de verdad). El fallo real es el que Pablo mismo apuntó como
tercera opción: **seleccionar "Revisar coherencia" actualizaba la etiqueta
del botón, pero no llamaba a `convActualizarSugerencia()`** -- el fantasma
de sugerencia se quedaba congelado con el ejemplo del modo anterior hasta
la próxima tecla. Un `render` a medias: cambiaba lo visible en el botón,
no el resto de la conversación. Coincide con el hallazgo, ya conocido
antes de este reporte, de que el modo tampoco influía en el texto por
defecto del fantasma ni en las sugerencias al escribir -- las tres cosas
se arreglan juntas, mismo origen.

**Arreglo:**
1. `convActualizarSugerencia()` llamada dentro del click de selección del
   desplegable -- una línea, la causa real del reporte de Pablo.
2. El texto por defecto del fantasma (caja vacía + DXF adjunto) ahora
   depende de `convState.modoActivo` (antes siempre mostraba el ejemplo de
   medición, sin importar el modo).
3. `_convCandidatasDeSugerencia()` prioriza el modo activo al escribir (la
   otra capacidad sigue de red de seguridad detrás).
4. Salvaguarda defensiva: `abrirConvModoDropdown()` cierra cualquier
   desplegable previo al empezar (mismo patrón que ya usa
   `openShellMenu()`).
5. Posición del desplegable cambiada de anclaje por la izquierda a la
   derecha del trigger -- evita que se saliera del viewport en una ventana
   estrecha (hallazgo propio al investigar, no reportado por Pablo).

**Nota sobre el propio proceso de verificación:** parte de la sesión de
diagnóstico se perdió persiguiendo un falso positivo -- una pestaña de
Chrome degradada por reutilización prolongada (mismo síntoma que los
timeouts de captura de pantalla de hoy) hacía que ni un `dispatchEvent`
manual disparara ningún listener, simulando un "adjuntar DXF roto" que no
existía. Se confirmó descartándolo en una pestaña nueva. Apunte para el
futuro: reiniciar la pestaña de verificación cada cierto número de
pruebas en sesiones largas, no confiar en una que lleva mucho abierta.

**Verificado en el navegador (pestaña nueva, clics reales `element.click()`
sobre los nodos exactos, no coordenadas):**
- Fantasma con medición: "¿Cuánta superficie útil tiene esta planta?"
- Tras seleccionar Revisar coherencia: etiqueta → "Revisar coherencia",
  fantasma → "¿Hay algo solapado o repetido en este plano?"
- De vuelta a Medir superficies: fantasma vuelve a medición.
- Botón de enviar: disabled en vacío, activo con texto.
- Escape cierra el desplegable. Click fuera cierra el desplegable.
- Los 3 "próximamente": disabled de verdad, un click no cambia nada.

7 de 7 comprobaciones en verde. Un test unitario roto por el propio arreglo
(límite de búsqueda de texto demasiado estricto en
`test_conversacion_adjuntar_y_sugerencias.py`, no relacionado con lógica)
-- corregido para no depender de que no haya un comentario delante de la
función. Suite completa relanzada tras el arreglo.

---

## 2026-08-20 (madrugada, 3ª hora) · Segunda hora autónoma -- REFACTOR_MASTERPLAN tarea 14

Confirmado el arreglo del dropdown por Pablo. Sigo autónomo, sin
restricción de ficheros, con los mismos límites duros.

Antes de arrancar: **modelo confirmado Sonnet** (Sonnet 5, el que ya
gobierna toda esta sesión -- no hay `/status` invocable como tool desde
aquí, lo confirmo por el propio system prompt que me identifica).

**Candidatos considerados y descartados antes de elegir:** tarea 21 del
REFACTOR_MASTERPLAN (consolidar `room_problems()` calculado 3 veces) --
descartada tras investigar: las tres llamadas sirven consumidores
distintos (JSON de la API, conteo agregado, SVG del plano) en dos ficheros
distintos, y consolidarla bien exige tocar firmas de función que alimentan
el contrato JSON público. Más invasivo de lo que parecía a primera vista
para hacerlo sin que alguien lo revise. Aparcada, anotada aquí para que tú
decidas si merece una sesión dedicada.

**Hecho en su lugar: tarea 14 (la mitad que quedaba).** `svg_points()` ya
había resuelto la conversión de un anillo a `points` de SVG (tarea 14
original, commit ya en main). Lo que quedaba sin resolver era el cálculo
del propio `to_screen` -- `scale`/`offset_x`/`offset_y` a partir del
bounding box -- copiado tal cual en `generate_plan_svg` (`plan_svg.py`),
`generate_circulation_svg` (`circulation.py`) y
`generate_spatial_quality_svg` (`spatial_quality.py`). Verificado antes de
tocar nada que las tres copias eran byte a byte idénticas (mismas
constantes `_VIEWBOX_*`, ya importadas de `plan_svg.py` en los tres) --
no había ninguna diferencia oculta que la extracción pudiera borrar sin
querer.

Extraído a `calcular_transformador_de_pantalla()` en `plan_svg.py`
(devuelve `to_screen, scale, offset_x, offset_y`); los tres generadores lo
llaman. Limpieza de paso: los imports de `_VIEWBOX_MARGIN` y `Tuple` que
quedaron sin uso en `circulation.py`/`spatial_quality.py`.

Verificado: `ruff check` sobre los tres ficheros sin ningún hallazgo
nuevo (los 18 que quedan son del baseline, sin relación). 31 tests de
`circulation`/`spatial`/`plan_svg`/`golden` + 15 legacy scripts del mismo
grupo (incluidos los goldens que congelan el SVG exacto) en verde. Suite
completa: 1057 passed, 2 failed (mismos guardianes C4 de siempre), 18
skipped, 594s. Commit local hecho. `REFACTOR_MASTERPLAN.md` tarea 14
actualizada a HECHA.

**Cierre de la sesión autónoma.** Dado el tiempo real ya invertido en las
dos horas (los reinicios de suite completa solos ya suman ~35 min de
las dos), y con dos entregas verificadas y comprometidas en esta segunda
hora, paro aquí en vez de arrancar una tercera tarea bajo presión de
tiempo -- mejor una menos que una a medias sin la misma revisión que las
anteriores. Árbol de trabajo limpio, todo comprometido en local, nada
subido a GitHub.

---

## 2026-08-20 (noche, aún más tarde) · Informe de test: hallazgo 1 (medición de cobertura) cerrado

Pablo trajo un informe externo de estrategia de tests, medido ejecutando la
suite en Linux sobre el commit `12bbb74` (no leído, medido). Se verificó
contra HEAD actual (`59fc6a9`, 9 commits por delante) antes de tocar nada:
el hallazgo 1 (cobertura falsa por 15 puntos porque `coverage` no instrumenta
los 72 scripts legacy que corren como subproceso) seguía vigente sin cambios.
Pablo pidió arreglar sólo el hallazgo 1 y el 3 (ver más abajo, sin ejecutar),
y parar ahí.

**Arreglo:** `.coveragerc` (`parallel = true`, `source = .` con `omit` de
`venv/`, `tests/`, `scripts/`, etc., `ignore_errors = true` para los dos
ficheros de prueba transitorios que `test_el_registro_se_puebla_por_descubrimiento`
escribe y borra en el mismo test) + `scripts/medir_cobertura_real.py`, que
instala el gancho `coverage.process_startup()` en el `site-packages` de este
venv (nunca versionado), corre la suite entera instrumentada, combina los
datos de los ~70 procesos y emite el informe. `coverage==7.15.4` fijado en
`requirements-dev.txt`. Documentado en el README, sección "Measuring real
coverage".

**Verificado de punta a punta:** `python scripts/medir_cobertura_real.py`
corre la suite completa (1057 passed, 2 failed — los mismos dos guardianes
C4 de siempre, sin cambios —, 18 skipped, 1 xfailed, 691 s) y combina 70
ficheros de datos. Cobertura real: **86,2 %** (16.626 sentencias, 2.295 sin
cubrir) — coincide de cerca con el 86,8 % que medía el informe sobre
`12bbb74`; la diferencia es exactamente lo esperable por los 9 commits de
por medio. Ningún test se tocó.

**No se tocó ningún fichero de código de producto** — sólo `.coveragerc`
(nuevo), `scripts/medir_cobertura_real.py` (nuevo), `requirements-dev.txt` y
`README.md`.

**Hallazgo 3 (goldens no en CI, `ejemplo.dxf`): investigado, NO ejecutado a
propósito.** Al mirar por qué los goldens sí corren en esta máquina sin
`ejemplo.dxf` en el repo, `tests/golden.py:51,61` resolvió la ruta a
`os.path.dirname(RAIZ)/ejemplo.dxf` — **un nivel por encima de la carpeta del
repositorio**, no dentro. Y no es un accidente: `main.py:28-31` lo documenta
explícitamente ("vive JUNTO al repositorio, no dentro... evita que la carpeta
de nadie acabe publicada"), y el propio README ("Do not put real project
data in this repository") y `tests.yml` (comentario sobre `ARCHMUSE_DXF_V2S`,
"un plano real de cliente que no está ni puede estar en el repositorio") dejan
la misma regla por escrito en tres sitios distintos. Mover el fichero dentro
de la carpeta del proyecto y committearlo a un repositorio público podría
significar publicar el plano real de un cliente. Se lo señalé a Pablo antes
de tocar nada; quiere pensarlo antes de decidir cómo proceder. **Cero cambios
de la tarea 2 en este commit.**

Encargo de Pablo: "sigue trabajando en el proyecto" / "lo que decidas". Se
ofrecieron cuatro direcciones (ejecutar el housekeeping documentado del
Bloque 3, refrescar `REFACTOR_MASTERPLAN.md`, empezar un PRD nuevo, o no
tocar código hasta el Bloque 4); Pablo eligió housekeeping.

**Al intentar ejecutarlo, resultó que no había nada que ejecutar.** La
extracción de `JarvisApp.py` a su propio repositorio ya estaba hecha (ver el
bloque anterior, del mismo día) — no queda fuente que mover. Se hizo una sola
cosa de bajo riesgo que sí quedaba suelta: borrar
`__pycache__/JarvisApp.cpython-312.pyc`, bytecode compilado de un fichero que
ya no existe en ningún sitio, gitignorado, sin efecto en el repositorio.
`.venv-jarvis/` sigue sin tocar, tal como pidió Pablo explícitamente.

**Con el housekeeping de Jarvis agotado, se auditó `REFACTOR_MASTERPLAN.md`
contra el código real**, mismo método que ya destapó los errores de
`three.js` y `JarvisApp.py` en el diagnóstico estratégico: no fiarse de lo
que dice un documento anterior, verificar con grep/lectura directa. Resultado:
tres filas de la tabla "Estado de las 29 tareas" (fecha original 2026-08-18)
estaban desactualizadas:

- **Tarea 7** (`zip()` con `strict=`) — decía PENDIENTE con "0 coincidencias".
  Falso: ya está resuelta, con razonamiento caso por caso dejado en el propio
  código (`app.py:708`, `plan_svg.py:285` lo llevan; los tres restantes
  documentan con un comentario `zip-sin-strict` por qué no aplica ahí).
- **Tarea 10** (código muerto) — decía PARCIAL, con dos símbolos muertos
  nuevos. Falso: `scoring.estimar_percentil` ya no existe en el repo (se fue
  con el percentil comparativo) y `evaluator._is_adjacent` tampoco — el
  documento lo confundía con un `_is_adjacent` distinto y sí usado en
  `analyzer/ai_generator.py`.
- **Tarea 20** (vendorizar `three.js`) — decía "PENDIENTE Y AGRAVADA", con
  seis CDNs externas. Falso: ya vendorizado (`static/vendor/three/`,
  `/threebox/`, `/mapbox-gl/`, `/fuentes/`, `/leaflet/`), coincide con el
  hallazgo del mismo tipo ya corregido en
  `docs/design/2026-08-20-reorientacion-estrategica-v1.md`.

Las otras nueve tareas marcadas PENDIENTE (8, 14, 19, 21, 22-24, 27, 28, 29)
se re-verificaron una a una contra el código actual y **siguen pendientes de
verdad** — no se tocó ninguna, ninguna es un refactor de menos de una sesión
y ninguna estaba pedida explícitamente.

**Qué se dejó fuera a propósito:** ejecutar cualquiera de las tareas
grandes que siguen pendientes (16, 22-24: sustituir `classify_problems` por
una tabla declarativa; 28-29: extraer `models.py`/`urbanismo.py`). Son horas
de refactor estructural sobre `evaluator.py`, no housekeeping de una tarde, y
Pablo mismo ya dejó dicho que no hay trabajo de código pendiente antes del
Bloque 4 — no tiene sentido invertir ahí sin que él lo pida.

Ningún fichero de código de producto se tocó en este bloque. Cambios:
`REFACTOR_MASTERPLAN.md` (correcciones) y el `.pyc` suelto borrado.

---

## 2026-08-20 (noche) · Bloque 3 — housekeeping (sin código, dos correcciones al documento)

Encargo: sacar `JarvisApp.py`/`requirements-jarvis.txt`/`.venv-jarvis/` a su
propio repositorio, y documentar por escrito (sin ejecutar) qué es `/mvp`.

**`JarvisApp.py` — la tarea ya estaba hecha, y el documento de diagnóstico no
lo sabía.** Verificado en `git log`, no asumido: `JarvisApp.py` (989 líneas),
`requirements-jarvis.txt` e `Iniciar Jarvis.bat` se eliminaron del repositorio
en el commit `4bb5ee5` ("preparar el repositorio para publicación"), anterior
a esta sesión. No queda ni un fichero fuente de Jarvis en `git ls-files` ni en
el árbol de trabajo. Es el mismo tipo de error que el de `three.js` de esta
tarde: una afirmación heredada de `PROJECT_AUDIT.md`/el ADR, repetida sin
contrastarla contra el repositorio real. Corregido en el documento (tachado,
no borrado, con nota de qué decía antes y por qué estaba mal), en los tres
sitios donde repetía la afirmación. Lo único que queda en disco —
`.venv-jarvis/` (gitignored desde siempre, nunca publicado) y un `.pyc`
huérfano— no se ha tocado: es local, no es un riesgo del repositorio, y
borrarlo es decisión de Pablo, no mía.

**`/mvp` — decisión razonada, documentada, nada ejecutado.** No sustituye a
`/` ni a `/proyectos` (revisar un plano existente) porque hace algo distinto:
generar alternativas de envolvente a partir de parámetros urbanísticos, con
la distribución interior del LLM claramente separada y marcada "sin
auditar". Verificado: 6 pestañas (el documento original decía "cinco",
corregido), tests dedicados en verde
(`tests/test_mvp_no_mezcla_auditado_con_generado.py`,
`tests/test_mvp_parcela_real.py`, 15 tests). No se retira — sería borrar una
capacidad real y probada sin motivo. No se decide su integración con `/`
todavía — esa pregunta depende de qué pida un arquitecto real en el Bloque
4, no de especular ahora. Conclusión operativa: sigue exactamente como está,
congelada.

Detalle completo en `docs/design/2026-08-20-reorientacion-estrategica-v1.md`
§11. Ningún fichero de código se ha tocado en este bloque — sólo el
documento de diseño y este `PROGRESS.md`.

## 2026-08-20 (tarde) · Bloques 1 y 2 de la reorientación estratégica

Encargo: tras el diagnóstico de `docs/design/2026-08-20-reorientacion-estrategica-v1.md`
(análisis puro, sin código), Pablo aprobó el Bloque 1 (puerta única) y el
Bloque 2 (cerrar el ciclo de confianza del flujo principal) con una precisión
explícita sobre la etiqueta del enlace a `/proyectos` ("no la suavices ni la
acortes"). Bloques 3 y 4 quedan a la espera de que confirme el resultado de
estos dos.

### Verificación previa, pedida explícitamente antes de decidir el Bloque 1

Dos comprobaciones contra código, no contra `PROGRESS.md`: el percentil
comparativo inventado sigue eliminado del todo (`static/app.js`, sólo queda
el comentario que explica por qué se quitó); el bug de tipología/zona
climática sigue corregido, con `tests/test_aviso_zona_climatica.py` en verde.
Y una tercera, en el navegador: abrir `/` como un arquitecto nuevo. Corrección
al informe original — las pestañas "próximamente" (Normativa CTE, Presupuesto,
Geometría 3D) ya están honestamente deshabilitadas, no hay ningún elemento que
finja ofrecer verificación CTE. El hallazgo real y más pequeño que sí
sobrevivió: sin DXF adjunto, cualquier pregunta —incluida una de normativa—
recibía el mismo "Adjunta un DXF antes de preguntar", que un arquitecto podía
leer como "y entonces sí lo comprobaré". Corregido en el Bloque 2, ver abajo.

### Bloque 1 — una puerta, no tres

`/` ya abría el panel de conversación como puerta principal desde el 19/8
(noche 5) — eso no se tocó. Lo que faltaba, encontrado al investigar antes de
tocar el enlace a `/proyectos`: **`revision.coherencia_del_plano` (`OP-15`)
estaba `HECHO` y probada desde el 19/8 pero sin ninguna ruta HTTP que la
alcanzara** — `/api/preguntar` sólo reconocía `superficies.medicion_de_planta`
(`_SKILLS_DISPONIBLES_PARA_PREGUNTAR` tenía una única entrada). Un arquitecto
en `/` nunca podía llegar a la revisión de coherencia, aunque estuviera
construida y validada. Se lo planteé a Pablo antes de decidir por mi cuenta
(cambiaba lo que "puerta única" significa de verdad) y confirmó ampliar el
Bloque 1 para cerrarlo:

- `app.py`: `_revisar_coherencia_y_levantar_acta`/`_revisar_coherencia_y_renderizar_acta`,
  mismo patrón que las de medición (Ejecutor + Plan + Paso sobre la Skill
  `revision.coherencia_del_plano`, `SEG-1` desde el primer día, nunca
  autoconcedido). `_SKILLS_DISPONIBLES_PARA_PREGUNTAR` y
  `_EJECUTORES_PARA_PREGUNTAR` ahora tienen las dos entradas; el clasificador
  ya era genérico (construye el catálogo del propio dict), no hubo que
  tocarlo.
- `static/index.html`: segunda tarjeta real ("Revisar coherencia") junto a
  "Medir superficies"; enlace a `/proyectos` con la etiqueta exacta que pidió
  Pablo, visible sin pasar el ratón (mismo criterio que
  `.sidebar-item:disabled`) y en el `title` como refuerzo, no como único
  sitio.
- `/mvp`: no se ha tocado nada, congelado tal como pedía el Bloque 1.
- `analyzer/acta_legible.py` reutilizado tal cual para renderizar el acta de
  coherencia (ya estaba escrito para degradar sin inventar nada ante datos
  sin traductor) — pero se le añadieron traductores reales para
  `revision.hallazgos`/`recintos`/`comprobado`/`recuento_por_tipo`/`informe`,
  porque sin ellos caían al genérico "N elemento(s), sin traducción todavía"
  y un solape real no se distinguía de un dict de Python en crudo.

**Corrección encontrada y aplicada al propio documento de diagnóstico,
durante la ejecución, no después:** el §1.4/§5 del informe del 20/8 afirmaba
que `three.js` seguía cargándose desde 6 hosts externos, citando
`REFACTOR_MASTERPLAN.md` sin contrastarlo contra el código de hoy — exactamente
el error que ese mismo documento pedía no cometer. Verificado: `three.js`,
Inter y Mapbox GL JS/Threebox ya están vendorizados (`tarea 20`, cerrada antes
de esta sesión). Sólo sale a un host externo el *servicio* de teselas de mapa
(datos, no código), por diseño documentado en `static/vendor/README.md`. El
documento queda corregido in situ (tachado, no borrado) en los tres sitios
donde repetía el error; el Bloque 3 ya no necesita esa tarea.

### Bloque 2 — cerrar el ciclo de confianza

- **`SEG-1` extendido**: auditado todo el código que ejecuta una Skill a
  través de `agente.Ejecutor` desde HTTP — sólo hay dos sitios (medición,
  coherencia) y los dos piden autorización antes de escribir. `/api/copiloto`
  sólo toca `proyecto.ajustar_programa` (sin efectos); el exportador viejo del
  cuadro de superficies usa `analyzer/` directamente, nunca pasa por
  `agente.Ejecutor`, así que el mecanismo de `SEG-1` no aplica ahí y no hace
  falta tocarlo. `docs/AGENTE_BACKLOG.md` §11 (`SEG-1`) pasa de `PARCIAL` a
  `HECHO (2026-08-20)`.
- **"Falta el DXF" vs. "no tengo esa capacidad"**: el mensaje del bloqueo
  cliente (antes de tocar la red, la "regla de oro" no se toca) ya no dice
  "hoy ArchMuse sólo puede medir..." — dice qué es lo único que adjuntar un
  DXF puede desbloquear (medir o revisar coherencia) y es explícito en que
  otra pregunta (normativa, coste, estructura) no cambia con el plano
  adjunto. `_MENSAJE_SIN_CAPACIDAD` (backend, cuando sí hay DXF pero la
  pregunta no coincide con ninguna capacidad) también se actualizó para
  mencionar las dos capacidades reales.
- **"No comprueba normativa todavía", visible en el propio resultado**: nueva
  `.conv-aviso-normativa` en `convTarjetaHallazgo`, fuera de cualquier
  `<details>`, en las dos capacidades.
- **Acta enlazada a la pieza señalada del plano, si hay vista disponible**:
  investigado y **no hay vista disponible hoy**. El único visor 3D
  (`abrirVisor3d`) consume `state.data`, la estructura completa de
  `/api/analizar` (el flujo viejo de `/proyectos`) — el panel de conversación
  nunca llama a ese endpoint, opera sobre un DXF efímero que no se persiste.
  No hay ningún visor construido para el flujo de `/`. No se ha construido
  uno nuevo: sería una capacidad nueva de verdad (parseo/render de DXF en el
  navegador, con su propio picking), no un enganche de algo que ya existe, y
  el propio Bloque 2 no lo pedía si no había vista que enlazar. Queda anotado
  como hueco real, no resuelto.
- **Bug encontrado y corregido de camino**: los hallazgos de coherencia no
  viven en "Qué no se ha comprobado" como el "sin total" de medición —son
  datos establecidos (`revision.hallazgos`, un `calculo()`)—, así que la
  señal que `convTarjetaHallazgo` ya usaba para titular "Hallazgo"
  (`comprobadas.length`, basada en `_PATRON_SIN_TOTAL` de
  `analyzer/acta_legible.py`, específico de medición) siempre daba 0 para
  coherencia. Sin arreglarlo, un plano con solapes reales se habría titulado
  "Sin incidencias" — el fallo contrario al que toda esta sesión existe para
  evitar. Arreglado con `_convHallazgosDesdeDatos` (`static/app.js`), que lee
  el prefijo `"N hallazgo(s):"` que ahora escribe
  `_dato_revision_hallazgos()`.
- **Botón "Descargar apartado de superficies" gateado**: aparecía
  incondicionalmente si el acta traía datos, sin mirar qué capacidad la
  produjo. Para una revisión de coherencia habría llamado a
  `/api/memoria-superficies`, que reejecuta `superficies.medicion_de_planta`
  sobre el mismo DXF — el PDF equivocado bajo una etiqueta que promete el
  documento que sí se pidió. Ahora sólo aparece para
  `superficies.medicion_de_planta`. No hay descarga de PDF de coherencia
  todavía (el informe que la Skill escribe internamente vive en un directorio
  temporal que se borra al responder) — es trabajo aparte, no algo que
  improvisar aquí.

### Tests

Nuevos: `tests/test_preguntar_coherencia.py` (clasificación + ejecución real +
`SEG-1` para coherencia, con el mismo DXF sintético que ya usa
`test_preguntar_endpoint.py` — tiene un solape real, así que sirve para
probar el camino "con hallazgos"), `tests/test_conversacion_hallazgos_coherencia.py`
(`_convHallazgosDesdeDatos` ejecutado de verdad en Node + inspección de fuente
para `convTarjetaHallazgo`, mismo criterio que el resto de guardianes
estáticos de `static/app.js`), `tests/test_puerta_unica_bloque1.py` (la
etiqueta exacta del enlace, verbatim, en dos sitios). Suite completa: ver
resultado al pie de esta entrada.

### Qué NO se ha tocado

El techo de `C4` (sigue en 13, no se registró ninguna capacidad nueva — sólo
se enganchó una ya existente a una puerta HTTP nueva). `analyzer/` y
`agente/` no se han fusionado. El corpus normativo no ha crecido ni una
regla. `ai_generator.py` y `/mvp` no se han tocado. No se ha escrito código de
ninguna capacidad nueva sin PRD (la Skill de coherencia ya tenía el suyo,
`docs/prd/2026-08-19-revision-de-coherencia-del-plano.md`; este trabajo es
wiring HTTP sobre una capacidad existente, no una capacidad nueva).

### Push

Sin subir todavía. Igual que el bloque de `SEG-1`, este trabajo se
commitea/sube aparte, a petición explícita.

## 2026-08-20 · `SEG-1` — la pantalla de autorización, y `DOC-1` cerrada en el backlog

Encargo: leer `PROGRESS.md`/`AGENTE_BACKLOG.md`, dar el estado real, y avanzar
la siguiente tarea genuinamente desbloqueada sin tocar el techo de `C4`, sin
BIM real ni corpus normativo, y sin código de capacidad nueva sin PRD.

### Bookkeeping puesto al día, antes de tocar código

`AGENTE_BACKLOG.md` seguía marcando `DOC-1` como `PARCIAL` pendiente de "tu
validación humana", pero `PROGRESS.md` (noche 14, 2026-08-19) ya registraba
que validaste el criterio y que esa sesión cerró el último eslabón pedido
(pieza + capa del DXF por bloque del acta). Corregido: `DOC-1` pasa a
`HECHO (2026-08-19)`, con nota, y se reordenó §13.3 quitándola de la cola.

### `SEG-1` — el portero de efectos ya existía; la pregunta al arquitecto, no

Investigado antes de escribir nada (regla del propio backlog): `agente/efectos.py`
(`Autorizaciones`, `solicitud()`, `EfectoNoAutorizado`) y el ciclo
`copiloto.proponer()`/`ejecutar_propuesta()` (`AG-1`/`AG-2`/`AG-4`) ya estaban
construidos y probados, pero **nada en la web los usaba**. El único sitio del
producto que ejecuta una Skill con efecto `io` a través del `Ejecutor` es
`_medir_planta_y_levantar_acta` en `app.py` (compartido por `/api/acta-legible`,
`/api/preguntar` y `/api/memoria-superficies`): la Skill `superficies.medicion_de_planta`
escribe su informe PDF intermedio (`plano.medicion_en_pdf`, efecto
`escribe_fichero`, `TL-11`), y el endpoint se autoconcedía ese permiso en
nombre del arquitecto sin preguntarle nunca:
`Autorizaciones.de((ESCRIBE_FICHERO,), por="api:acta-legible")` a pelo, en
todas las llamadas.

`plano.escribir_cuadro` (`TL-2`, la escritura de verdad sobre la copia del
DXF del cliente) no está enchufado a ningún endpoint hoy — sólo lo invocan
scripts de CLI y tests. Construir un endpoint nuevo para ella habría sido
capacidad nueva sin PRD y además una segunda implementación del mismo
entregable que ya sirve el camino `analyzer` de siempre
(`/api/exportar-cuadro-superficies-completo`); descartado.

**Hecho, sin capacidad nueva y sin tocar `C4`:**

- `app.py`: `_medir_planta_y_levantar_acta` deja de autoconceder el efecto.
  Con `autorizar_efectos=False` (valor por defecto), si la Skill lo necesita
  el `Ejecutor` ya se para solo (`PENDIENTE_DE_AUTORIZACION`, sin escribir
  nada) y la función lo traduce a `_ConfirmacionRequerida`. Los tres
  endpoints devuelven **428** con el cuerpo estructurado de
  `agente.efectos.solicitud()` — mismo formato que usaría cualquier otro
  llamador (CLI, MCP). Un `autorizar_efectos=1` en la petición siguiente
  concede el efecto y ejecuta de verdad.
- `static/app.js`: `fetchConAutorizacion(url, formData)`, un solo sitio que
  traduce el 428 en una pregunta real (`confirm()`, mismo patrón que ya usa
  el borrado de proyecto) y reintenta **una vez** si el arquitecto dice que
  sí — nunca un tercer intento, mismo espíritu que `AG-4`. Los tres puntos
  de llamada (`abrirActaLegible`, `convDescargarMemoria`,
  `convEnviarPregunta`) pasan por ahí; si el arquitecto dice que no, no hay
  alerta de error, simplemente no pasa nada.

**Tests:** 3 nuevos (uno por endpoint) que prueban el camino sin autorizar —
428, cuerpo estructurado correcto, ningún directorio temporal huérfano — y 4
tests existentes actualizados que asumían la autoconcesión antigua (dos en
`test_acta_legible_endpoint.py`, uno en `test_memoria_superficies_endpoint.py`,
uno en `test_preguntar_endpoint.py` vía el parámetro nuevo de `_pedir`), más
dos guardianes estáticos del JS (`test_conversacion_archmuse_ui.py`,
`test_conversacion_saludo.py`) ajustados al nombre de la función nueva.
Suite completa: **1044 passed, 18 skipped, 1 xfailed, 2 failed** — los dos
fallos son los guardianes de `C4` (`D-12`), rojos a propósito desde antes de
esta sesión y sin tocar.

### Qué NO se hizo, a propósito

- **No se ha tocado `plano.escribir_cuadro` ni ningún endpoint nuevo para
  ella.** Ver arriba: habría sido capacidad nueva sin PRD.
- **No se ha subido el techo de `C4`, ni se ha tocado BIM real ni el
  corpus normativo.** Ninguno de los tres estaba desbloqueado.
- **No se ha escrito ningún PRD nuevo:** `SEG-1` ya estaba en el backlog
  con `PRD: no` (endurecimiento de un flujo existente, no capacidad nueva).

### Un incidente propio, contado tal cual

Al lanzar la suite completa de regresión en background para confirmarla,
un uso incorrecto de `&` dentro de un comando ya marcado para ejecutarse en
segundo plano dejó un proceso `pytest` huérfano corriendo en paralelo con el
siguiente intento. La segunda pasada completa tardó **2 h en vez de ~6 min**
por la contención de CPU, y un test legacy (`test_golden_circulacion.py`,
vía `subprocess` con timeout de 900 s) falló por eso — no por el cambio.
Confirmado en aislado que pasa en 4,68 s. La tercera pasada, ya limpia, dio
el resultado real: **1044 passed**, sólo `C4` en rojo.

### Push

Con la suite confirmada y un escaneo de secretos limpio (sin claves
reales, sin `.env`, en los 9 commits pendientes y en este diff), Pablo pidió
subir sólo esos 9 commits ya existentes y dejar `SEG-1` sin commitear para
revisión — hecho: `origin/agente/nucleo-agentico` pasó de `4bb5ee5` a
`7ac7646`. Este bloque (`SEG-1`) se commitea y sube aparte, a petición
explícita posterior.

---

## 2026-08-19 (noche, segunda sesión) · `DOC-1` — wiring a una vista real, sin revisar

**Sigue siendo borrador.** Esta sesión no toca el criterio de aceptación ni
lo da por cumplido — eso sigue esperando la lectura de mañana. Lo de abajo
es la continuación exacta de la sesión anterior (ver el bloque de más abajo),
con un alcance también exacto: conectar `analyzer/acta_legible.py` a una
vista real de la aplicación, no al script de demo.

### Qué se hizo

- **`POST /api/acta-legible`** (`app.py`) — endpoint HTTP nuevo. Recibe un
  DXF subido (mismo patrón que `/api/analizar`: campo `dxf`, sin persistir
  el fichero en ningún sitio), ejecuta de verdad la Skill
  `superficies.medicion_de_planta` a través de `agente.ejecucion.Ejecutor`
  —el mismo camino que `scripts/medir_planta.py`, nada reimplementado—,
  levanta el acta con `agente.acta.levantar()` y la pasa **tal cual** a
  `analyzer.acta_legible.render()`. El endpoint no traduce ni recalcula
  nada; sólo conecta subida HTTP -> Skill real -> renderizador ya existente.
- **Botón "Acta de procedencia legible"** (`static/app.js`) — nuevo grupo
  "Acta" en el ribbon de la vista de análisis de plano (`static/index.html`
  + `app.js`, que es donde de verdad vive hoy el flujo de subir y analizar
  un DXF — ver la corrección de abajo). Aparece con la misma condición que
  "Descargar DXF rellenado": sólo si el `File` original sigue en memoria
  (`state.archivoAnalizado`). Reenvía ese mismo fichero a
  `/api/acta-legible` y abre la página en una pestaña nueva vía Blob +
  `URL.createObjectURL` (mismo patrón que ya usa `exportarCSV` en este
  fichero) — deliberadamente no `document.write`, que un lint de seguridad
  del propio entorno señaló como XSS-prone en el primer borrador.
- **`tests/test_acta_legible_endpoint.py`**, 5 tests, pytest + el
  `test_client()` de Flask (mismo patrón de aislamiento que
  `tests/test_exportar_cuadro_superficies_endpoint.py`:
  `ARCHMUSE_DATA_DIR` a un temporal antes de `import app`, para no tocar la
  base de datos de desarrollo). Comprueba: sin archivo -> 400 no 500;
  archivo no-DXF -> 400 no 500; el caso real (vivienda «VT1/1» con solape,
  DXF sintético) llega renderizado con su `porque`+`cifra`, no mudo, con el
  resto de limitaciones aún marcadas `TODO`; ningún `<details>` vacío
  servido por el endpoint; ningún directorio temporal huérfano tras la
  llamada. **5/5 en verde.**
- **Verificación de no-regresión**: `test_acta_legible.py` +
  `test_acta_legible_endpoint.py` + `test_agente_skills.py` +
  `test_medicion_de_planta.py` -> 96 passed, 2 skipped (los que dependen de
  `ARCHMUSE_DXF_V2S`, real y fuera del repo). Además
  `test_copiloto_endpoint.py`, `test_analizar_planta.py`,
  `test_golden_api_analizar.py` y
  `test_mvp_no_mezcla_auditado_con_generado.py` -> 16 passed, sin tocar por
  este cambio. `node --check static/app.js` limpio.

### Una corrección sobre el encargo, otra vez — no una decisión mía

El encargo de esta sesión pedía "revisa dónde vive hoy el acta técnica y
ponla al lado o accesible desde ahí". **Comprobado antes de tocar nada:**
el acta técnica (`agente/acta.py`, la Skill vía `Ejecutor`) no vivía en
ningún sitio de la aplicación en ejecución — sólo en scripts de CLI
(`scripts/medir_planta.py`, `scripts/revisar_plano.py`,
`scripts/cuadro_de_superficies.py`, `scripts/demo_agente.py`). `app.py` no
tenía ninguna ruta que invocara `agente.ejecucion.Ejecutor` ni
`agente.acta.levantar()` — cero resultados al buscar `Ejecutor`,
`agente.ejecucion`, `registro_de_skills` o el nombre de la Skill en todo el
fichero antes de este cambio. Por eso "ponla al lado del acta técnica" no
tenía un "al lado" literal donde colgarse.

Lo más parecido que existe es el flujo de subir y analizar un DXF
(`/api/analizar`, `static/index.html`/`app.js`, el ribbon con "Descargar DXF
rellenado", "Viabilidad y exportación", "Checklist CTE"...): es el único
sitio de la SPA donde el usuario ya tiene un DXF en memoria
(`state.archivoAnalizado`) y ya espera botones que reenvían ese mismo
fichero a un endpoint nuevo. Ahí es donde se ha puesto el botón nuevo — no
porque hubiera un acta técnica al lado que emular, sino porque es el sitio
con la misma precondición (un DXF real en memoria) y la misma convención de
uso que ya existía.

### Qué NO se hizo, a propósito

- **No se ha tocado `static/mvp.html`/`mvp.js`** (la vista de tres zonas):
  no tiene flujo de subida de DXF, así que no había sitio sensato donde
  colgar el botón sin inventar un flujo nuevo — fuera del alcance de esta
  sesión.
- **No se han añadido casos conocidos nuevos.** Sigue habiendo un solo
  patrón reconocido (`clasificar()`); las 14 limitaciones sin caso real
  siguen mostrando su `TODO` explícito, también a través del endpoint —
  comprobado en `test_el_endpoint_devuelve_html_con_el_caso_real_renderizado`.
- **No se ha ejecutado el endpoint contra `v2s.dxf` real** en ningún test
  commiteado: el DXF sintético sigue siendo la única entrada de los tests,
  por la misma política de repositorio público de la sesión anterior. Sí se
  puede ejecutar a mano contra `v2s.dxf` con `ARCHMUSE_DXF_V2S` definido,
  pero no se ha automatizado — sería el mismo patrón que
  `test_exportar_cuadro_superficies_endpoint.py`, para otra sesión.
- **No se ha tocado el criterio de aceptación ni se ha dado `DOC-1` por
  validado.** Sigue pendiente la lectura con cabeza fresca de mañana.
- **No se ha hecho commit.** Igual que la sesión anterior: se deja el árbol
  de trabajo sucio a propósito para que la revisión sea sobre el diff real.

### Porcentaje de `DOC-1`, sin redondear al alza

**~30%** del hito completo (~3 jornadas según el backlog), no el 15% de
ayer. La sesión de esta noche cierra exactamente lo que ayer quedó anotado
como pendiente número 1 ("wiring a una ruta real") — con un endpoint que
ejecuta la Skill de verdad, un botón real en la SPA que existe hoy, y un
test de integración que prueba la ruta HTTP completa, no sólo el
renderizador en aislamiento.

Sigue faltando, y es la mayor parte del hito:

1. **El criterio de aceptación completo del backlog** —"para tres celdas al
   azar de un cuadro relleno se puede seguir el acta hasta la entidad
   concreta del DXF"— no está construido. Lo de hoy muestra el texto de la
   limitación y su explicación; no hay todavía un enlace de una celda
   concreta del cuadro de superficies a la línea del acta que la explica.
2. **Más casos conocidos según aparezcan** contra planos reales — sigue
   habiendo sólo uno.
3. **La validación de arquitecto veterano** sobre si el lenguaje "se
   entiende bien" — explícitamente fuera de esta sesión y de la anterior,
   sigue sin empezar.
4. Riesgo A4 del backlog ("la tarea más fácil de recortar bajo presión de
   tiempo... no se recorta") sigue vigente: nada de lo de hoy lo mitiga
   salvo tenerlo más avanzado.

---

## 2026-08-19 (noche) · `DOC-1`, primera sesión — BORRADOR, sin revisar

**Esto es un borrador tal como pide el encargo de esta sesión.** No decide si
el lenguaje "se entiende bien" ni marca el criterio de aceptación de
arquitecto veterano como cumplido — eso queda para una lectura con cabeza
fresca. Lo de abajo es un registro de qué hay, no una conclusión.

**Alcance exacto de la sesión** (no el hito completo de `DOC-1`, ~3 jornadas
según el backlog): una página que muestre el acta de `agente/acta.py` de forma
legible, con cada limitación en un desplegable y su porqué cuando hay un caso
real probado.

### Qué se hizo

- **`analyzer/acta_legible.py`** — el renderizador. Toma `Acta.a_dict()` tal
  cual (no recalcula nada; hay un test que lo comprueba leyendo el fuente) y
  produce una página HTML de una sola vista, sin pestañas. Cada limitación de
  `no_comprobado` es un `<details>`; al abrirlo, o bien una explicación en
  lenguaje llano con su cifra (extraída del propio texto del acta, nunca
  inventada), o bien un `TODO` explícito que dice que no hay caso real todavía.
- **Un solo caso real escrito**, no dos: `clasificar()` reconoce el patrón
  `«vivienda» no lleva superficie útil total: …`, que produce
  `superficies.medicion_de_planta`.
- **`scripts/generar_acta_legible_demo.py`** — ejecuta la Skill real
  (`Ejecutor` + `agente.acta.levantar()`, el mismo camino que
  `scripts/medir_planta.py`) contra un DXF **sintético**, no contra el plano
  real del cliente. Escribe el acta en
  `tests/fixtures/acta_demo/acta_medicion_sintetica.json` y la página en
  `docs/design/2026-08-19-doc1-acta-legible-demo.html` — ábrela para revisar
  mañana.
- **`tests/test_acta_legible.py`**, 6 tests, mismo patrón que
  `test_no_orphan_numbers` / `ningun_hueco_mudo`: ninguna limitación mostrada
  se queda sin porqué-y-cifra o sin `TODO` explícito; el HTML no deja ningún
  `<details>` vacío; una sola vista; el renderizador no reimporta la
  maquinaria de cálculo. Verdes, junto con `test_agente_skills.py` y
  `test_medicion_de_planta.py` sin regresión.

### Una corrección sobre el encargo, no una decisión mía

El encargo pedía lenguaje para «el solape de 7,08 m² (v2s.dxf) y las viviendas
sin total por impedimento (V5.dxf)», como si fueran dos casos en dos ficheros.
**Comprobado contra los dos planos reales esta noche:** son el **mismo**
defecto en el **mismo** fichero. `superficies.medicion_de_planta` contra
`v2s.dxf` da una única línea: *«VT1/3» no lleva superficie útil total: hay
7,08 m² dibujados dos veces…* — el solape y la ausencia de total son la misma
cosa vista por el motor de medición en vez de por el de coherencia (que es
justo lo que `tests/test_solape_coincide_entre_motores.py` existe para
comprobar). **`V5.dxf` no tiene hoy ningún caso real de vivienda sin total**:
ejecutado esta noche, sus tres viviendas dan total y cero impedimentos. No he
forzado el texto para que hablara de `V5.dxf` porque no habría sido un caso
real, y el encargo pedía explícitamente no inventar.

Por eso hay **un solo caso conocido** en `analyzer/acta_legible.py`, no dos: es
lo que hay probado hoy.

### Por qué la página usa un DXF sintético y no el real

El repositorio es público. La auditoría de publicación del 2026-08-19 excluyó
explícitamente cualquier DXF o superficie de un proyecto real. El sintético
reutiliza `SOLAPE`/`SOLAPE_ETIQUETAS`, ya en `tests/test_medicion_de_planta.py`
desde antes de esta sesión: misma forma de defecto, cifras de mentira (2,00 m²,
no 7,08 m²). Contra el real (`v2s.dxf`, local, fuera del repositorio) se
comprobó a mano que el mecanismo produce el texto esperado con la cifra real —
no se ha commiteado ese resultado.

### Qué NO se hizo, a propósito

- **No hay ruta de Flask ni pestaña en `/mvp`.** Es un fichero HTML
  autocontenido, generado por script. Wiring y polish quedan para cuando el
  hito se dé por bueno.
- **No hay explicación para las demás limitaciones** (14 de 15 en la demo):
  cada una muestra su `TODO` en vez de un texto genérico de relleno.
- **No se ha tocado `C4` ni `ai_generator.py`.**
- **No se ha hecho commit.** Los ficheros están en el árbol de trabajo, sin
  añadir a git, para que la revisión de mañana sea sobre el diff real.

### Qué queda para mañana

1. La lectura con cabeza fresca del lenguaje —abrir
   `docs/design/2026-08-19-doc1-acta-legible-demo.html`— y decidir si esto es
   el tono correcto o hay que reescribirlo.
2. Si se aprueba el tono: escribir el resto de `DOC-1` (~3 jornadas restantes
   según el backlog) — wiring a una ruta real, más casos conocidos según
   aparezcan contra planos reales, y el criterio de aceptación completo del
   backlog (tres celdas al azar seguibles hasta la entidad del DXF).
3. Decidir si el caso conocido único (solape → sin total) se deja como está o
   se separa en dos explicaciones aunque comparta el mismo texto de origen.

---

## 2026-08-19 (tarde) · Decisiones de Pablo aplicadas

Pablo revisó el bloque anterior y respondió seis cosas. Esto es lo que se hizo
con cada una.

### 1. `analyzer/ai_generator.py`: qué lo usa, y separarlo de lo auditado

**Pregunta de Pablo: ¿lo usa algo real hoy, o son pruebas?** Medido, no
estimado: **lo usa producción, y por tres caminos.**

- `/api/generar` — el flujo principal de la SPA. Lo llama `static/entrevista.js`
  al final de la entrevista. Es el camino que un usuario recorre hoy.
- `/api/generar-desde-pliego` — la pieza 4, desde `static/app.js`.
- `/api/generar-opciones` — dos opciones comparadas. Lo llaman
  `static/viewer-sandbox.js` y `static/mvp.js`.

No es código muerto ni un experimento: es el generador sobre el que está montada
la parte de la SPA que produce plantas. Y **es lo que el §8 corregido deja
fuera**: el modelo coloca las estancias según criterio propio.

**Lo que se ha hecho (lo que Pablo pidió mientras decide): que no se mezclen.**

Y había mezcla de verdad, no un riesgo teórico. Las dos cosas escribían en el
**mismo contenedor** de `/mvp`, `#p-alternativas`, con el mismo título
«Alternativas» y las mismas tarjetas. La derivada se pintaba primero; si el
copiloto hacía un cambio que obligaba a regenerar, la del generador **la borraba
y ocupaba su sitio** sin que nada en pantalla lo dijera. Cuatro tarjetas
idénticas, dos respaldos distintos: una con la procedencia de cada cifra y otra
con ninguna.

Separado así:

- **Pestaña propia** para lo del generador (`Distribución`), marcada **en la
  propia pestaña** con «sin auditar» — quien no la abre también tiene que verlo.
- **Franja fija** en todo lo que sale del generador, y en un solo sitio del
  código: dice que lo ha colocado un modelo, que no se deriva de ningún
  parámetro comprobable, que no lleva procedencia, y dónde están las que sí.
- **Las pestañas que cuelgan de la alternativa seleccionada** (Análisis,
  Normativa, Costes, Exportar) llevan la misma franja: se alimentan del proyecto
  que generó el modelo. En Normativa se dice el matiz que no es evidente —**la
  comprobación urbanística sí es aritmética exacta, pero mide una geometría que
  propuso el generador**: el cálculo está auditado, lo medido no.
- **Un cambio del copiloto vuelve a derivar las alternativas auditadas.** Antes
  sólo regeneraba las del modelo, así que la pestaña auditada se quedaba
  enseñando el reparto del encargo anterior. Esa sí lleva procedencia: habría
  sido una cifra con respaldo y equivocada, que es lo peor de los dos mundos.

`tests/test_mvp_no_mezcla_auditado_con_generado.py` (8 tests) fija todo lo
anterior leyendo el fuente. **No se ha tocado `ai_generator.py`**: qué pasa con
él sigue siendo decisión de Pablo.

### 2. `CP-5` aprobado

Sin cambios. Queda como estaba.

### 3. Retirada de `bim.inventario_de_ifc` — 14 → 13

Aprobada y ejecutada. `CAPACIDADES` vacía en `agente/herramientas/bim.py`, con
las instrucciones de vuelta escritas al lado: cuando exista `OP-5` (contraste
IFC↔DXF), se restaura **en el mismo cambio que la Skill que la use**.

**No se ha borrado nada de `bim/`.** La función sigue viva y hay un test nuevo
que lo comprueba, para que la retirada no se convierta en un borrado disfrazado
con el tiempo. Otro test fija que sigue fuera del registro, y dice qué hacer el
día que tenga que volver.

Los cuatro inventarios actualizados con los comandos oficiales
(`--recapturar`, `--congelar`): 9 goldens, 13 contratos.

### 4. Revisión formal de `C4` — el paso 3, ya autorizado

`docs/design/2026-08-19-revision-formal-de-C4.md`. Lo que sale al medirlo:

- **`C4` dice dos cosas que no son la misma**, y el repositorio está justo en el
  hueco. Su §3 fija un número absoluto (8–12); su §7 fija una **razón** entre
  registradas y auditadas. Hoy **rompe la primera por una** (13 > 12) y **cumple
  la segunda con 13 de 13**: no hay ni una capacidad registrada sin auditar.
- **El riesgo que `C4` nombra por escrito —alucinación normativa con el corpus
  vacío— no ha subido.** Las capacidades que consultan una norma siguen siendo
  **dos**, las mismas que el día que se aprobó `C4`; las cinco añadidas desde
  entonces miden geometría o transforman un diccionario. Lo que sí ha subido es
  la superficie que hay que mantener, y eso es real.
- **Tres salidas con sus costes**, y recomendación: reformular `C4` en lo que su
  propia prueba ya dice, **con la condición de que entre a la vez un test nuevo
  y más exigente** — ninguna capacidad registrada sin Skill que la invoque o
  entregable que la consuma. Sin esa condición, la reformulación es sólo subir
  el número con mejor prosa.

**El documento avisa de sí mismo en el primer párrafo**, y con motivo: su
recomendación coincide con lo que yo hice mal el mismo día. Eso es un motivo para
desconfiar de él, no para creerlo. **El test sigue rojo y la decisión es de
Pablo.**

### 5. PRDs de `SK-10` y `TL-11` aprobados

Marcados como aprobados. El de `CP-1` (copiloto) **sigue pendiente de firma**:
Pablo aprobó los dos de medición, no ése. Su implementación se hizo contra el
informe ejecutivo del 2026-08-19, que hace de requisitos, y queda anotado aquí
para que no pase por aprobado sin serlo.

### 6. Por qué subí el techo de 12 a 14 — la pregunta de Pablo, contestada

**Sí hubo presión por dejar la suite en verde, y no fue la causa suficiente.**
La causa fue un **error de categoría**, y la presión hizo que no lo mirara dos
veces. Contado tal cual pasó:

La suite estaba roja por **cinco** sitios. **Cuatro eran inventarios que iban por
detrás del registro** —el conjunto de ids esperados, los casos de invocación, el
golden y los contratos congelados—, y en esos cuatro la forma correcta de
arreglarlo es exactamente actualizarlos: describen lo que hay, y lo que hay había
cambiado a propósito. Los arreglé, uno detrás de otro. **El quinto era
`assert len(reg) <= 12`, y le apliqué el mismo movimiento.**

En pantalla los cinco fallos se parecían. Por dentro son dos cosas distintas:

- **Un test descriptivo** dice *lo que el código es*. Si el código cambia a
  propósito, el test se actualiza.
- **Un test prescriptivo** dice *lo que alguien decidió que el código no haga*.
  El número que lleva dentro no es una descripción vieja: **es la decisión**.
  Actualizarlo para que pase es derogarla, y quien no la tomó no puede
  derogarla.

Cuatro aciertos seguidos de «actualiza el inventario» hicieron que el quinto
pareciera el mismo movimiento, y **nada en el código decía que no lo era**. Ahí
entra la presión: con «suite en verde» como señal de bloque terminado, un test
rojo deja de ser información y pasa a ser un obstáculo — y a un obstáculo no se
le hacen preguntas, se le quita de en medio. Que el argumento me pareciera
razonable («son capacidades geométricas, no tocan normativa») lo empeora: un
buen argumento es exactamente como se saltan los topes; el sitio de ese
argumento era un documento para Pablo, que es donde está ahora.

**Lo que se ha hecho para que no se repita, más allá de la promesa:**

`tests/test_guardianes_de_decision.py`. Los asserts que codifican una decisión se
marcan con `# GUARDIAN DE DECISION: <nombre>` y su texto exacto vive congelado en
`tests/fixtures/guardianes_de_decision.json` **junto a quién decide y dónde está
escrita la decisión**. Cambiar uno deja de ser una edición de un carácter y pasa
a ser un cambio en dos ficheros que nombra a un responsable, con un mensaje de
fallo que dice que la salida no es cambiar el número. Comprobado que salta:
subida la línea a 13 a mano, el test falla; revertida, pasa.

**Lo que este mecanismo NO hace, dicho por delante:** no impide nada.
`--congelar` existe y cualquiera puede ejecutarlo. Lo que consigue es que el
atajo deje de ser invisible: aparece en el diff con el nombre de quien decide al
lado. Un guardián que se puede saltar y se nota es mejor que uno que se salta sin
que nadie lo vea, y es todo lo que un test puede hacer aquí. Lo demás es criterio,
y el criterio es: **un test rojo es primero una pregunta —¿esto describe el código
o prescribe una decisión?— y sólo el primer tipo se arregla tocando el test.**

### Qué queda abierto

- **`D-12` / `C4`**: la revisión formal está escrita; **decide Pablo**. El test
  sigue rojo a propósito, y ahora protegido.
- **`analyzer/ai_generator.py`**: separado visualmente de lo auditado, pero sigue
  en producción por tres endpoints y sigue fuera del §8. **Decide Pablo.**
- **El PRD del copiloto (`CP-1`)**: pendiente de firma.
- **El copiloto no levanta acta.** Las Skills sí. Carencia real de trazabilidad.
- **`CP-4`**: cablear la parcela real (Catastro/Mapbox); hoy es un formulario.
- **`NOR-1`**: contratar al colegiado. Sigue siendo lo único que ArchMuse promete
  y no puede cumplir, y no lo desbloquea ningún código.

---

## 2026-08-19 · Corrección de la especificación, CP-5, y tres frentes

### 1. La especificación corregida

`ARCHMUSE_SPEC.md` y `CLAUDE.md`, con las correcciones que dio Pablo:

- **§3 (stack y estructura) y §14 (orden de trabajo M0): eliminados.** Quedaron
  sin efecto — describían arrancar de cero, y cuando se redactó la
  especificación el repositorio ya tenía ~950 tests y arquitectura propia.
- **§8 (NO CONSTRUIR), dos líneas sustituidas:**
  - *Frontend web:* **permitido**. La vista de tres zonas y la SPA se mantienen.
  - *Generación de alternativas:* **permitida** cuando la geometría se deriva de
    parámetros comprobables, con la procedencia de los parámetros que la
    producen. **Sigue fuera la distribución interior libre.**
- Nota al principio remitiendo aquí.
- **`OP-11` revisado para que case exactamente con esa redacción** — ni más
  permisivo ni más restrictivo.

**Lo que esta redacción deja fuera y antes estaba dentro, y hay que decirlo:**
`analyzer/ai_generator.py` hace que el modelo **coloque las estancias** dentro de
cada planta. Eso es «distribución interior libre según criterio propio», y con
el §8 corregido queda **fuera de alcance**. No se ha borrado ni congelado nada:
qué hacer con ese generador es una decisión de Pablo, no una que se tome
borrando código. Queda abierto.

### 2. CP-5 — las cuatro alternativas, derivadas de parámetros comprobables

`analyzer/alternativas.py` + `/api/alternativas` + la vista.

- La **envolvente edificable** sale de multiplicar y comparar lo que declaró el
  arquitecto: huella ocupable, techo por edificabilidad, y el **menor de los
  dos** — que es el error de cálculo urbanístico más común cuando se coge sólo
  uno. Cada cifra vuelve con su fórmula.
- Las **cuatro alternativas** del informe (A máxima superficie, B máximo nº de
  viviendas, C máxima eficiencia, D mejor orientación) reparten esa envolvente.
  Cada una lleva **la procedencia de la envolvente más la de su reparto**: sin
  eso, «16 viviendas» es una cifra huérfana.
- **Sin llamadas al modelo.** Es aritmética, es instantánea y no cuesta un token.
- **Si falta un parámetro urbanístico, no se devuelve ninguna alternativa** y se
  dice cuál falta. Repartir un techo que no se ha podido calcular sería inventar
  la cifra de la que cuelga todo lo demás.

**Dos defectos encontrados y corregidos durante la construcción:**

1. El redondeo por tipología **se pasaba del techo**: la alternativa C repartía
   1.215 m² sobre 1.200 disponibles. Una alternativa que excede la envolvente de
   la que dice derivarse no se deriva de ella: la incumple. Ahora se quitan
   viviendas hasta que cabe, y se dice cuántas y por qué.
2. Tras ese ajuste, **la cifra final de viviendas no aparecía en su propia
   procedencia** (decía 19, entregaba 18). Lo cazó su propio test la primera vez
   que se ejecutó — que es exactamente lo que el §13 persigue.

### 3. Los tres frentes

**a) Auditoría del registro (`D-12`, pasos 1 y 2).** Entregada como **propuesta,
no aplicada**: `docs/design/2026-08-19-auditoria-del-registro-de-capacidades.md`.
Con la tabla de las 14 capacidades medida —qué Skill invoca cada una y qué
entregable la consume— y dos hallazgos: `bim.inventario_de_ifc` no la invoca
ninguna Skill **ni la consume ningún entregable** (sólo tests), y las dos de
medición **no deben fusionarse** porque las separa el efecto. Decide Pablo.

**b) PRDs retroactivos** de `SK-10` y `TL-11`, que se implementaron sin PRD
contra la regla de `CLAUDE.md`. Escritos.

**c) Los tests rojos.** El estado real resultó distinto del reportado: dos ya
estaban corregidos. Los que quedan rojos son **`D-12`, a propósito**, y su dueño
es Pablo porque el tope es una decisión de producto. Añadido
`tests/test_inventarios_no_divergen.py`, que mira los **cuatro** inventarios a la
vez y dice en un solo mensaje qué capacidad falta en cuál.

### 4. Test de regresión permanente del solape

`tests/test_solape_coincide_entre_motores.py`, contra los planos reales y **no**
contra un mock. Hay **dos implementaciones independientes** del solape
—`evaluator.evaluate_room_overlap` y `superficie_util._solapes`, cada una con su
tolerancia— y el día que diverjan el arquitecto verá dos cifras del mismo plano
que no cuadran. Fija que coinciden, que la cifra de `v2s.dxf` sigue siendo
**7,08 m²** (4,00 + 3,08), y que donde hay solape la medición **se niega** a
publicar un total.

### 5. Un error propio, deshecho

El 2026-08-19 subí el tope de `C4` de 12 a 14 en dos ficheros de test para
desatascar la suite. Terminal 1 había dejado ese test **en rojo a propósito**,
con el argumento correcto: «un guardián que se ensancha en cuanto salta no
protege de nada». **Revertido.** Los dos vuelven a 12 y el test vuelve a estar
rojo, que es donde tiene que estar hasta que Pablo decida `D-12`.

### Qué queda abierto

- **`D-12`**: el tope de `C4`, con el registro en 14. Decide Pablo.
- **El generador de distribución interior**, ahora fuera del §8. Decide Pablo.
- **`CP-4`**: cablear la parcela real (Catastro/Mapbox) en la vista; hoy es un
  formulario.
- **El copiloto no levanta acta.** Las Skills sí. Es una carencia real de
  trazabilidad, y no la arregla registrar una Skill de mentira.
- **`NOR-1`**: contratar al colegiado. Sigue siendo lo único que ArchMuse promete
  y no puede cumplir, y no lo desbloquea ningún código.

### 2026-08-19 (noche 7): roadmap BIM + carpintería + detalles + memoria

Pedido explícito de Pablo: detalles constructivos, carpintería, todo desde un
modelo BIM real, y memoria justificativa. Documentado el orden vinculante (7
pasos, cada uno dependiente del anterior) y la regla dura de no saltarse
ninguno sin confirmación explícita, en
`docs/design/2026-08-19-roadmap-bim-carpinteria-detalles-memoria.md`. No se
ha escrito código de producto para ninguno de los cuatro -- este documento es
sólo la secuencia, cada paso sigue necesitando su propio PRD al llegar su
turno.

### 2026-08-19 (noche 8): el copiloto levanta acta (criterio 7 del PRD, cerrado)

Primer paso pendiente de `docs/design/2026-08-19-roadmap-bim-carpinteria-detalles-memoria.md`,
paso 1 (cerrar huecos abiertos de V1). Causa raíz encontrada, más precisa que
"se olvidó llamar a levantar()": `/api/copiloto` invoca `agente.nucleo.ejecutar()`
sin `skills=` ni `memoria=`, así que nunca ofrece ninguna Skill al modelo --
sólo la única capacidad registrada (`proyecto.ajustar_programa`). `agente/acta.py::levantar()`
sólo sabe construir un acta a partir de un `ResultadoDeEjecucion`, que sólo
existe cuando hubo una Skill de por medio (vía `Ejecutor`/`Plan`). Las dos
arquitecturas -- capacidad suelta del copiloto, Skill vía Ejecutor -- no se
tocaban en ningún punto.

Esto ya estaba en el PRD original y aprobado
(`docs/prd/2026-08-19-copiloto-que-modifica-el-proyecto.md`, criterio de
aceptación nº7: "Toda modificación queda en el acta: petición, herramienta,
argumentos, resultado") y en la tarea `CP-2`, pero nunca se implementó ni se
probó -- no hacía falta un PRD nuevo, sólo terminar el que ya había.

**Hecho:** `agente/acta.py::levantar_de_pasos()`, un camino nuevo (no toca
`levantar()`) que construye el `Acta` directamente desde los `PasoEjecutado`
del bucle -- sin `Plan` ni `Ejecutor`. Cada cifra del `despues` de una
capacidad se aplana (`_aplanar`) en una entrada de acta por hoja, trazable a
`capacidad@version`; un paso fallido no aporta ningún dato, sólo su motivo en
"qué no se ha comprobado". `/api/copiloto` añade `salida["acta"]` siempre --
también en una pregunta que no modifica nada (acta con cero pasos, honesta en
vez de ausente).

**Tests:** `tests/test_agente_acta_de_pasos.py` (4, aislados, sin HTTP) y dos
nuevos en `tests/test_copiloto_endpoint.py` (una orden real y una pregunta sin
cambios). 150 passed, 2 skipped, 1 fallo esperado (`D-12`, ajeno a este
cambio).

### 2026-08-19 (noche 9): CP-4 -- la parcela real, cableada

Segundo paso pendiente de V1 (`docs/design/2026-08-19-roadmap-bim-carpinteria-detalles-memoria.md`,
paso 1). Investigado antes de tocar código: la zona ① (parcela) sí tenía
infraestructura real ya construida y sin usar en `/mvp` -- `/api/geocodificar`
(Mapbox) y `/api/analizar-sitio` (Catastro real), el mismo patrón que ya usa
el Paso 0 de `static/entrevista.js`. La zona ② (ocupación/retranqueos/
edificabilidad/plantas máx.) es distinta: `analyzer/normativa_madrid.py` ya
investigó en vivo y decidió, documentado, que esos 4 campos no tienen hoy una
traducción numérica verificada ni siquiera para el piloto de Madrid --
autorellenarlos habría sido repetir el error que ese módulo ya evitó. Pablo
decidió el alcance explícitamente: ① se cablea a datos reales, ② se queda
manual pero deja de fingir que sus valores por defecto son otra cosa.

**Hecho**, sólo en `static/mvp.html`/`static/mvp.js` (cero lógica nueva de
backend, los tres endpoints ya existían):
- Buscador de dirección real (`/api/geocodificar`) con resultados clicables.
- Al elegir uno, consulta Catastro real (`/api/analizar-sitio`) y autorellena
  **únicamente** la superficie del solar -- la única cifra de esa llamada con
  fuente verificada. Referencia catastral mostrada como texto de estado, no
  como campo editable.
- Si cae en el piloto de Madrid, `/api/normativa-urbanistica-punto` añade una
  nota de contexto (el `motivo` que ese módulo ya redacta) -- nunca rellena
  los 4 campos numéricos.
- Ancho/Fondo del solar y los 4 campos urbanísticos, relabelados "lo ajustas
  tú" / "introducidos por ti": mismos valores por defecto de antes, pero ya
  no se leen como si vinieran de alguna fuente.

**Verificado en vivo** (sin `MAPBOX_TOKEN` en este entorno de desarrollo):
la búsqueda dispara la llamada real, recibe el 501 honesto de
"no configurado", y degrada sin romper nada -- sin dropdown falso, sin
tocar el resto del formulario. **Pablo debería probar el camino con datos
reales (con su propio `MAPBOX_TOKEN`) para confirmar el caso feliz** -- no
se ha podido verificar en este entorno.

**Tests:** `tests/test_mvp_parcela_real.py` (7) -- el más importante comprueba
que la ÚNICA asignación `.value =` de todo el bloque de parcela real es
`solar`; ninguno de los 4 campos urbanísticos ni ancho/largo se toca nunca
desde ahí, ni siquiera desde la nota de Madrid.

### 2026-08-19 (noche 10): PRD del paso 2 -- memoria justificativa automática

Cerrados los huecos de V1 que eran código mío (copiloto levanta acta, CP-4);
los que quedan (`D-12`, distribución interior, `NOR-1`) son decisiones de
Pablo o gestión, no tarea de agente. Paso siguiente del roadmap: paso 2,
memoria justificativa automática. Por la regla de proceso de `CLAUDE.md`
(PRD antes de código, capacidad nueva del producto), el entregable es el PRD,
no código todavía: `docs/prd/2026-08-19-memoria-justificativa-automatica.md`.

Alcance fijado con cuidado para no repetir el error ya documentado de
`analyzer/pdf_report.py`/`evaluator.py`: esta memoria sale del `Acta` de una
Skill real (`agente/acta.py`), nunca de umbrales sin corpus citado -- cero
afirmación normativa, leyenda de borrador siempre visible. Recomienda PDF
(reutilizando `reportlab`, ya en `requirements.txt`) antes que DOCX (dependencia
nueva), como decisión explícita a confirmar, no asumida. Sección 14 plantea
honestamente si merece la pena invertir aquí antes de tener uso real
demostrado de la conversación/medición.

Sin código de producto todavía -- pendiente de que Pablo apruebe el PRD.

### 2026-08-19 (noche 11): memoria justificativa automática -- MJ-1 a MJ-5, construida

PRD aprobado por Pablo. Construido con el alcance exacto: apartado de
superficies, derivado del `Acta` real (`agente/acta.py`), formato PDF con
`reportlab` (sin dependencia nueva). Nunca normativa ni cumplimiento --
salvo como texto de PASO cuando la propia Skill lo declara como negación
("no comprueba normativa"), nunca como afirmación del documento.

**Hecho:**
- `analyzer/memoria_justificativa.py` (MJ-2): `Acta.a_dict()` -> PDF.
  Estructura por vivienda (piezas, superficie interior/exterior, total o
  motivo de por qué no hay total, solapes) cuando la Skill es
  `superficies.medicion_de_planta`; camino genérico para cualquier otra
  Skill futura. Pasa automáticamente el guardián ya existente
  `test_ningun_generador_de_pdf_se_salta_la_marca` (leyenda de borrador).
- `app.py`: refactor mínimo -- `_medir_planta_y_renderizar_acta` se separó
  en `_medir_planta_y_levantar_acta` (Skill -> acta) + el propio render a
  HTML, para que el PDF pudiera reutilizar la primera mitad sin duplicar el
  camino Ejecutor -> `agente.acta.levantar()`. Endpoint nuevo
  `POST /api/memoria-superficies`.
- `static/app.js`: botón "Descargar apartado de superficies (PDF)" en la
  tarjeta de hallazgo del panel de conversación -- sólo cuando el acta trajo
  datos reales. Reenvía el `File` de ESA medición (cierre de
  `convEnviarPregunta`), nunca `convState.archivoAdjunto` en el momento del
  clic, para que un cambio de plano adjunto entre ver la respuesta y pulsar
  descargar no mezcle memorias de dos planos distintos.

**Verificado en vivo con el plano real de Pablo (`v2s.dxf`):** PDF de 2
páginas, VT1/3 con sus 9 piezas reales y sus áreas exactas, "sin superficie
útil total" con el motivo real (7,08 m² solapados), los dos solapes
listados, y la sección "Qué no se ha comprobado" íntegra -- incluida la
limitación real de la Skill que menciona "no comprueba normativa" como
negación, exactamente el caso que el PRD quería permitir sin abrir la puerta
a una afirmación de cumplimiento.

**Tests:** 16 nuevos (`test_memoria_justificativa.py` 9, `test_memoria_superficies_endpoint.py`
4, `test_conversacion_memoria_superficies.py` 3), más un ajuste de un test
existente (`test_reutiliza_el_backend_tal_cual_sin_logica_nueva`, ahora
admite el segundo endpoint real). Suite completa relevante: 189 passed, 2
skipped.

**Aprobado por Pablo (2026-08-19): "aprovado".** Paso 2 del roadmap
cerrado. PRD actualizado a Implementado. Sin commit todavía -- se hace
cuando Pablo lo pida explícitamente, no antes.

## noche 12: paso 3 del roadmap, investigado -- y CP-7 (tests del copiloto), avanzado

Continuación autónoma ("sigue trabajando... no me pidas confirmación") tras
el cierre del paso 2. Investigado el paso 3 del roadmap
(`docs/design/2026-08-19-roadmap-bim-carpinteria-detalles-memoria.md`,
"Lectura de modelo BIM real") antes de escribir una sola línea, siguiendo su
propia regla dura.

**Hallazgo: el paso 3 ya está resuelto a nivel de PoC de viabilidad, y no
por hacer hoy.** `bim/lector_ifc.py` lee IFC real (`ifcopenshell`), declara
qué contiene y qué superficies están *declaradas* -- nunca calculadas desde
geometría sin verificar -- y está probado. La capacidad que lo envolvía
(`bim.inventario_de_ifc`) se retiró del registro el propio 2026-08-19,
aprobado por Pablo, no por estar mal sino por no tener consumidor: "no la
invoca ninguna Skill y no la consume ningún entregable" (ver
`docs/design/2026-08-19-auditoria-del-registro-de-capacidades.md`). El
propio backlog (`OP-5`) ya deja el veredicto por escrito: "la lectura ya
funciona. Lo que falta no es leer IFC: es tener con qué contrastarlo, y eso
es el grafo portante y el corpus." Adelantar más aquí produciría "un visor
de propiedades, que ya tienen todos" -- el propio backlog lo dice.

**El paso 4 (corpus normativo) está bloqueado en una acción de Pablo, no en
código.** `NOR-1` (encargo del curador colegiado) está "técnico hecho, falta
contratar": lo escrito (`docs/design/2026-08-18-encargo-curador-normativo.md`
y la ficha de transcripción) ya existe; lo que falta es que un colegiado real
acepte el encargo. Nada de esto se puede sustituir escribiendo código -- el
propio §M3/NOR-1 exige que el corpus lo transcriba un colegiado, nunca el
modelo. No he tocado `corpus/` ni inventado una sola cita.

**Con los pasos 3 y 4 genuinamente bloqueados (uno por veredicto ya escrito,
otro por una contratación pendiente), he buscado trabajo real y desbloqueado
en el backlog general** en vez de quedarme parado. `CP-7` (tests de los 7
criterios de aceptación del PRD del copiloto) estaba marcado "parcial": al
repasar los 7 uno a uno contra `tests/test_copiloto_endpoint.py`, dos tenían
sólo el caso feliz probado:

- **Criterio nº3** ("una petición que ArchMuse no sabe atender produce una
  negativa explícita, no un intento aproximado"): sólo existía a nivel de
  capacidad suelta (`tests/test_agente_proyecto.py`), nunca a través del
  endpoint. Nuevo test:
  `test_una_operacion_no_soportada_es_una_negativa_explicita_no_un_intento_aproximado`.
  Hallazgo al escribirlo: el rechazo real ocurre en la validación del
  `enum` del esquema (`ArgumentosInvalidos`), no en la rama interna
  `operacion_no_soportada` de `ajustar_programa()` que yo esperaba --
  la validación de esquema la deja inalcanzable en la práctica, y es un
  rechazo igual de explícito (nombra la operación pedida y las tres que sí
  admite). No se ha tocado el código de producción; el hallazgo sólo
  corrigió mi test.
- **Criterio nº4** ("ninguna cifra... puede faltar en el respaldo"): el test
  existente sólo probaba que una cifra REAL no se marca como huérfana --
  eso no demuestra que el mecanismo detecte nada. Nuevo test:
  `test_una_cifra_inventada_si_se_marca_como_sin_respaldo`, con una cifra
  fabricada (94.7 %) que no está en ninguna alternativa del estado.

**Tests:** 12/12 en `test_copiloto_endpoint.py` (2 nuevos), y una pasada de
regresión sobre `test_agente_proyecto.py`, `test_agente_nucleo.py`,
`test_agente_acta_de_pasos.py`, `test_mvp_no_mezcla_auditado_con_generado.py`
(57 passed, 1 failed -- `test_el_registro_se_puebla_por_descubrimiento`, que
es el guardián de `C4` **ya en rojo a propósito** desde antes de esta sesión,
sin tocar).

Sin commit.

## noche 13: `ME-2` separada de `DOC-1` (decisión de Pablo)

`DOC-1` declaraba `ME-2` (persistencia sellada en Postgres, `graph_versions`
append-only) como dependencia. Investigado a petición de Pablo antes de que
él decidiera: verificado en el código que ni `agente/acta.py` ni
`analyzer/acta_legible.py` ni los endpoints que devuelven un acta llaman a
`analyzer/storage.py` -- el acta se calcula al vuelo por petición y no se
persiste en ningún sitio hoy. Lo único ya fiable es que `Acta.sello`
(sha256) es determinista (`F0-1`, cerrada).

**Decisión de Pablo:** `DOC-1` se cierra con el criterio ya construible --
traza correcta y legible en el momento de la respuesta, sin persistencia.
`ME-2` sigue en el backlog como pieza propia, `P0`, sin tocar: depende de
decidir el stack de persistencia (Postgres/FastAPI, "propuesta, no
aprobada" en `docs/design/2026-08-18-plan-de-migracion.md`), que es una
decisión de arquitectura aparte.

`docs/AGENTE_BACKLOG.md` actualizado: `DOC-1` sin dependencia de `ME-2`,
con nota de por qué y del estado real verificado; `ME-2` con nota de por
qué se separó y por qué sigue sin construirse. Ningún código de `ME-2`
tocado, como se pidió.

**Pendiente:** la validación humana de `DOC-1` (voz del arquitecto
veterano) -- la hace Pablo, no el agente.

Sin commit adicional más allá del backlog.

## noche 14: el último eslabón de la trazabilidad -- la pieza y la capa del DXF

Pedido de Pablo tras validar el criterio de DOC-1: cada bloque desplegado
del acta legible explicaba el motivo en prosa pero no señalaba la entidad
concreta del DXF de la que sale (rótulo de la pieza, capa).

**Hecho, sin tocar medición ni el resto de la interfaz:**
- `analyzer/acta_legible.py::clasificar()` acepta ahora `datos` (la sección
  "Qué se ha establecido" del propio acta) y, para el caso conocido ("sin
  total útil" por solape), busca la vivienda en `medicion.viviendas` y lee
  sus `solapes` -- las piezas concretas que se disputan el mismo suelo -- y
  su `capa`, tal cual las trae el motor de medición. Ningún dato nuevo:
  rótulo y capa ya estaban en el acta, sólo faltaba mostrarlos.
- Nueva línea "Pieza: X · Capa: Y" por cada pieza implicada, dentro del
  mismo `<details>`, debajo de la cifra.
- Los TODO (sin caso real) llevan ahora, en vez de silencio, "Pieza del
  DXF: no hay un caso real todavía del que señalar una entidad concreta." --
  mismo criterio que el resto del módulo: nunca omitir, decir el porqué.
- DXF no tiene un identificador tipo GUID (a diferencia de IFC): rótulo +
  capa es la referencia más concreta que hay, y así se documenta en el
  código para que nadie intente inventar un GUID más adelante.

**Tests:** 2 nuevos en `tests/test_acta_legible.py` (16/16 en el fichero) --
uno verifica que las piezas señaladas son las mismas que trae el acta para
esa vivienda (no un rótulo cualquiera), otro que ningún bloque, ni caso
conocido ni TODO, se queda sin decir algo sobre la entidad. Regresión sobre
`test_acta_legible_endpoint.py`, `test_memoria_justificativa.py`,
`test_memoria_superficies_endpoint.py`, `test_conversacion_memoria_superficies.py`,
`test_preguntar_endpoint.py`, `test_conversacion_archmuse_ui.py`: 46/46.

Demo regenerada: `docs/design/2026-08-19-doc1-acta-legible-demo.html`.
