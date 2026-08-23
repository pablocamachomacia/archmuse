# PRD — Detección asistida de convenciones de capas

**Estado:** Borrador · **Fecha:** 2026-08-23 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

> **Congelación vigente, y aquí sí aplica:** `analyzer/`, `scripts/` y
> `tests/fixtures/` están congelados hasta el jueves 2026-08-28 por
> competencia de tiempo con la validación del corpus del 25-26
> (`docs/prd/2026-08-22-contraste-superficies-memoria-vs-plano.md`, §R-3).
> **Todo el alcance de este PRD cae dentro de esos tres directorios**
> (`analyzer/parser.py`, `tests/fixtures/dxf_plausibles/`,
> `herramientas/diagnostico_dxf.py`), así que la congelación lo bloquea entero.
> Nada de este PRD se implementa antes de esa fecha, ni después sin
> aprobación explícita de Pablo en esta cabecera.
>
> Sucede en su alcance restante al PRD `2026-08-02-ingesta-de-dxf-ajenos.md`
> (tareas 2 y 10 de aquel documento). Sus tareas 3–9 ya están implementadas y
> son el sustrato de éste.

---

## 1. Problema que resuelve

El 2026-08-23 Pablo probó el motor con un DXF ajeno (`cs_05.dxf`, plano
latinoamericano de descarga, capas `A-POLIGONO` / `A-TEXTOS AREAS`) y no
obtuvo superficies por estancia. El diagnóstico medido en sesión — ejecutando
el propio `parser.capas_candidatas` contra el fichero — dice algo distinto de
lo que parecía:

**Lo que NO falló.** La detección heurística de capas ya existe y funciona:
`capas_candidatas` (`analyzer/parser.py:1118`) puntúa cada capa por contenido
— proporción de polígonos con rótulo dentro (peso 0,45), tamaño plausible de
estancia (0,35), volumen relativo (0,15) y pista en el nombre (0,05) —,
`elegir_capa`/`_resolver_capa` usa la candidata clara o lanza
`CapaIndeterminada` para preguntar, `app.py:498` la captura y la SPA muestra
el selector (`static/app.js:509`). `AREA_LAYER = "00 areas"` sobrevive solo
como preferencia. Con `cs_05.dxf` el heurístico **hizo lo correcto al
negarse**: la mejor candidata (`A-JARDINERIA`) puntuó 0,15, muy por debajo
del umbral de 0,5.

**Lo que sí falló.** La premisa «el dato estaba ahí» resultó falsa, y el
motor no supo decirlo:

- `A-POLIGONO` contiene 4 polilíneas **abiertas** (dos de solo 2 vértices) y
  2 `LINE`: es el lindero de la parcela, no los recintos.
- Cero polilíneas cerradas de estancia en todo el plano — comprobado también
  con la recuperación geométrica de cierre. Cero `HATCH` de recintos.
- Los 25 textos de `A-TEXTOS AREAS` son solo nombres («Recámara principal»,
  «Cocina», «Closet»…), sin una sola cifra de m².

**El plano no trae los recintos dibujados** — las estancias solo existen
implícitamente entre los muros. Es exactamente el escenario que el §9 del PRD
del 02-08 predijo: *«que la mayoría de los planos ajenos no tengan ninguna
capa de áreas porque ese estudio simplemente no la dibuja»*.

El defecto real, por tanto, tiene tres partes:

a) **Cuando ninguna candidata es plausible, el motor ofrece candidatas
   absurdas** (jardinería, mobiliario) en vez de decir qué falta. La pregunta
   que hoy hace ante `cs_05.dxf` no es honesta: invita a elegir entre
   opciones que él mismo sabe malas.
b) **No usa la señal que tenía delante:** 25 rótulos de estancia sin ninguna
   geometría cerrada que los contenga. Ese cruce —rótulos huérfanos— es la
   diferencia entre «no entiendo tu plano» y «tu plano no trae los recintos
   dibujados como polilíneas cerradas; encontré los nombres pero no su
   geometría».
c) **El heurístico sigue calibrado contra un solo DXF real**, como su propio
   docstring declara. La tarea 2 del PRD del 02-08 (medir 8–10 DXF ajenos)
   nunca se hizo por falta de archivos; `cs_05.dxf` es el nº 1 de esa muestra.

## 2. Usuario afectado

El arquitecto que no es Pablo — el primero que podría pagar (mismo §2 del PRD
del 02-08) — y Pablo mismo cada vez que prueba el motor con un plano ajeno
para evaluar la generalización del producto.

## 3. Objetivo de negocio

Que el primer contacto de un DXF ajeno con ArchMuse produzca **o un análisis
o una explicación competente de por qué no** — nunca un cero mudo ni una
pregunta absurda. El paso de confirmación es la primera impresión del
producto (§7 del PRD del 02-08: «la mejor demostración de competencia que el
producto puede dar en los primeros diez segundos de uso»), y hoy, ante un
plano sin recintos dibujados, esa primera impresión es una pregunta que
delata que el motor no ha entendido nada.

## 4. Objetivo técnico

Ante cualquier DXF, exactamente tres salidas posibles, todas honestas:

1. **Candidata clara** → se usa y se declara (ya existe, no se toca).
2. **Duda entre candidatas plausibles** → se pregunta con la lista ordenada
   (ya existe, no se toca).
3. **Ninguna candidata plausible** → **diagnóstico específico**, nuevo: qué
   se encontró (N rótulos de estancia sin geometría cerrada que los contenga,
   capas con geometría abierta, HATCH si los hay), qué esperaba encontrar
   (polilíneas cerradas de recinto con su rótulo dentro), y la conclusión de
   que no se puede medir. Nunca inventar, nunca ofrecer como plausible lo que
   el propio heurístico ha puntuado como implausible.

## 5. Casos de uso

- **CU-1 — DXF del primer estudio** (`00 areas`): idéntico a hoy, sin ninguna
  diferencia observable. Es el guardián de regresión.
- **CU-2 — DXF ajeno con capa de recintos bajo otro nombre** (`AREAS`,
  `A-SUP-UTIL`, `03 recintos`… — convenciones ya cubiertas por los fixtures
  `tests/fixtures/dxf_plausibles/`): candidata clara o pregunta con
  candidatas, como hoy.
- **CU-3 — `cs_05.dxf` o equivalente** (rótulos sin recintos): mensaje del
  tipo «He encontrado 25 rótulos de estancia (Cocina, Recámara principal…)
  pero ninguna polilínea cerrada que los contenga: este plano no trae los
  recintos dibujados. Para medir superficies necesito los recintos como
  polilíneas cerradas.» — con los recuentos reales, y sin selector de
  candidatas implausibles.
- **CU-4 — DXF sin nada** (ni polilíneas cerradas ni rótulos): el mensaje
  actual de «ninguna capa con polilíneas cerradas» sigue siendo el correcto.

## 6. Casos límite

- **Rótulos huérfanos por geometría en bloques no atravesados.** El
  recorrido ya atraviesa `INSERT` (tarea 8 del PRD del 02-08), pero con
  límite de profundidad: si el recuento de huérfanos procede de no haber
  bajado lo suficiente, el mensaje mentiría. El diagnóstico debe declarar
  hasta dónde miró.
- **Textos que no son estancias.** `cs_05.dxf` incluye «PLANTA BAJA»,
  «PLANTA ALTA», «ELEVACIÓN PRINCIPAL» en la misma capa de textos. El
  recuento de rótulos huérfanos debe filtrar títulos (o declararlos aparte);
  25 huérfanos donde 3 son títulos es una cifra inflada, y este producto no
  infla cifras.
- **Geometría y textos en capas separadas** (la convención de `cs_05.dxf`):
  ya cubierto — `extract_labels` lee todo el plano y `_proporcion_rotulada`
  cruza contra polígonos de cualquier capa. No es el defecto y no hay que
  tocarlo.
- **Recintos como HATCH.** Fuera de alcance de medición, igual que en el PRD
  del 02-08 — pero el diagnóstico del caso 3 debe contarlos y decirlo, porque
  si aparecen planos así en la muestra, cambia la prioridad.
- **Un DXF que hoy funciona no puede degradarse.** Ni los del primer estudio ni los
  11 `dxf_plausibles/` ni los 13 `dxf_tortura/`.

## 7. Flujo del usuario

Sin pantallas nuevas. El selector de capa existente en la SPA gana un tercer
estado: cuando no hay candidatas elegibles, en vez de la lista muestra el
diagnóstico del caso 3 (qué se encontró, qué falta). En CLI y agente,
`CapaIndeterminada` ya viaja con el mensaje redactado
(`agente/herramientas/plano.py:64`, `main.py:67`): solo cambia el texto que
transporta.

## 8. Criterios de aceptación

1. `ejemplo.dxf`, `V5.dxf`, `v2s.dxf` y los 11 fixtures de
   `dxf_plausibles/` producen exactamente el mismo resultado que hoy
   (misma capa elegida, mismas estancias, mismas áreas, mismas preguntas).
2. Ante `cs_05.dxf` (vía fixture sintético equivalente — ver T1), el motor
   produce el mensaje de rótulos huérfanos con el recuento real y **no**
   ofrece un selector de candidatas implausibles.
3. Ninguna ruta devuelve superficies sin capa declarada (hoy ya se cumple;
   es criterio para que no regrese).
4. El mensaje de `CapaIndeterminada` distingue los tres casos del §4 y un
   test lo verifica caso a caso.
5. El diagnóstico completo funciona sin clave de API y sin red.
6. Los umbrales (`UMBRAL_CAPA_ACEPTABLE`, `VENTAJA_MINIMA`,
   `MINIMO_POLIGONOS_CAPA`, pesos de `capas_candidatas`) quedan documentados
   con la procedencia de su calibración: contra qué archivos se fijaron y
   cuándo (hoy: un solo DXF, y el docstring lo confiesa — eso debe seguir
   siendo verdad o dejar de serlo con datos).

## 9. Riesgos

- **La muestra de DXF ajenos depende de conseguir archivos.** Riesgo
  principal, no técnico, heredado tal cual del PRD del 02-08 (§9). Hoy la
  muestra real es: 2 planos del primer estudio + `cs_05.dxf`. Con eso no se recalibra
  nada — solo se confirma o se desmiente el caso 3.
- **Sobre-afinar contra 2–3 archivos es tan inventado como contra 1.** T4 es
  un alto de decisión, no una promesa de recalibración.
- **El mensaje de `CapaIndeterminada` tiene 4 consumidores** (`app.py`,
  `main.py`, `agente/herramientas/plano.py`,
  `agente/herramientas/coherencia.py`): cambiar su contenido exige revisar
  los cuatro, no solo la SPA.
- **Licencia de `cs_05.dxf` desconocida** (descarga de internet): no puede
  entrar en `tests/fixtures/`. Se reproduce su convención en un fixture
  sintético y el original queda fuera del repo (patrón `ARCHMUSE_DXF_V2S`).

## 10. Impacto sobre módulos existentes

- `analyzer/parser.py` — nueva señal de rótulos huérfanos (cruce
  `extract_labels` × polígonos cerrados, con filtro de títulos);
  `_mensaje_de_capa` con los tres casos; `CapaCandidata`/`CapaIndeterminada`
  transportan el diagnóstico. No se tocan ni la puntuación ni los umbrales
  (eso es T4, con datos).
- `static/app.js` — tercer estado del selector de capa.
- `herramientas/diagnostico_dxf.py` — columna de rótulos huérfanos en la
  tabla por archivo.
- `tests/` — fixture nuevo + tests del §12. No se toca `analyzer/evaluator.py`
  ni el runtime de `agente/` salvo el texto que ya transportan.

## 11. Plan de implementación dividido en pequeñas tareas

Tareas de ~1 jornada máximo (regla de ejecución vigente). **Ninguna empieza
antes del 2026-08-28 ni sin aprobación de este PRD.**

| # | Tarea | Estimación |
|---|---|---|
| T1 | Fixture sintético `tests/fixtures/dxf_plausibles/12_rotulos_sin_recintos.dxf` que reproduce la convención de `cs_05.dxf`: lindero abierto en `A-POLIGONO`, nombres de estancia (y 2–3 títulos) en `A-TEXTOS AREAS`, muros, mobiliario. El original queda fuera del repo, referenciado por variable de entorno como `v2s.dxf`. | 0,5 j |
| T2 | Señal de rótulos huérfanos + `_mensaje_de_capa` con los tres casos del §4 + revisión de los 4 consumidores + tests. | 1 j |
| T3 | SPA: tercer estado del selector (mostrar diagnóstico en vez de lista cuando no hay candidatas elegibles). | 0,5 j |
| T4 | **Alto de decisión.** Pasar `herramientas/diagnostico_dxf.py` (con la columna nueva) sobre toda la muestra disponible; pegar la tabla en este PRD; decidir con Pablo si los pesos/umbrales se recalibran, se confirman, o se espera a más archivos. | 0,5 j |

T1 y T2 son secuenciales; T3 depende de T2; T4 puede ir en paralelo desde T1.

## 12. Plan de pruebas

- **Guardianes de regresión** (criterio 1): la salida actual sobre
  `ejemplo.dxf` y los `dxf_plausibles/` se congela antes de tocar nada —
  mismo procedimiento que el §12 del PRD del 02-08.
- Test del mensaje del caso 3 contra el fixture T1: recuento exacto de
  huérfanos, títulos excluidos del recuento, y ausencia de candidatas
  ofrecidas.
- Test de que los tres casos del §4 producen tres mensajes distinguibles.
- Patrón existente de `tests/` para `dxf_plausibles` (scripts con
  `check()`/`fallos`).

## 13. Métricas para medir el éxito

- **La del PRD del 02-08, sin cambio:** de N DXF ajenos, cuántos terminan en
  análisis correcto **o en explicación específica de por qué no**. Hoy
  `cs_05.dxf` termina en pregunta absurda; tras esto debe terminar en
  explicación. La meta de «7 de 10 analizados» de aquel PRD sigue esperando
  a la muestra.
- Cero análisis completados con capa no declarada (se cumple hoy; vigilarlo).

## 14. Posibles motivos para NO implementar la idea

**a) Lo pedido ya existe en un ~80%.** «Buscar la capa por heurística de
contenido, usar la clara, preguntar si duda, nunca inventar» — todo eso está
implementado desde el PRD del 02-08 y funcionó correctamente ante
`cs_05.dxf`. El margen real de este PRD es el caso 3 (el mensaje honesto
cuando no hay recintos) y la calibración pendiente. Si al leer esto Pablo
decide que el mensaje actual —una lista de candidatas débiles— es
suficiente, este PRD se cae entero y no pasa nada grave.

**b) Deducir recintos desde muros queda explícitamente FUERA.** Es lo único
que haría medible un plano como `cs_05.dxf`, y es visión geométrica sobre
DXF: semanas de trabajo, mismo patrón que las ventanas de `OP-13`
(el dato no está como objeto; habría que reconocerlo). Decisión aparte, con
su propio PRD, y solo si la muestra de T4 demuestra que los planos sin
recintos dibujados son mayoría. Comprometerse a eso hoy, con una muestra de
uno, sería exactamente el error que `OP-13` ya enseñó a no cometer.

**c) Esto robustece la compensación del formato equivocado.**
`DESTROY_ARCHMUSE.md` §3: en IFC los recintos son objetos de primera clase;
el paso 3 del roadmap (lectura BIM) ya está en PoC verificado contra IFC
reales. Cada jornada invertida en heurísticas DXF es una jornada que el
paso 3 volverá parcialmente redundante. La respuesta de este PRD: el
arquitecto español pequeño sigue mandando DXF en 2026, y las 2,5 jornadas de
T1–T4 son un coste proporcionado; más que eso ya no lo sería.

**d) Compite con cerrar V1**, que es la regla nº 1 de ejecución. 2,5
jornadas es el tope que este PRD se autoimpone por esa razón.

---

**Decisión:** _pendiente de revisión por Pablo_
