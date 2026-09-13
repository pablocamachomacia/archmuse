# PRD — Integración con AutoCAD: prototipo AutoLISP

**Estado:** **APROBADO** · **Fecha:** 2026-09-08 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo, 2026-09-08

> **Lo que Pablo aprobó, con sus palabras (2026-09-08).** Los cuatro hallazgos
> de la §0, aceptados uno a uno:
>
> 1. **Trial de AutoCAD completo, nunca LT** — «crítico, lo tendré en cuenta al
>    activarlo».
> 2. **El criterio de rótulo no se duplica en LISP.** El script manda geometría
>    y textos en crudo; el emparejamiento se queda en `parser.match_label_to_room`.
> 3. **La marca de borrador `C3` es obligatoria en la tabla**, sin opción de
>    desactivarla.
> 4. **Salida A de la §4.1** (DXF temporal en el servidor). `D-12` no se toca y
>    no se añade ninguna capacidad al registro.
>
> **Alcance de ejecución, y va detrás de otras cosas.** La recomendación de
> «hoy no» (§14) se acepta **a medias**: se hace la demo del `ACAD_TABLE`
> (§14.3), pero **no en lugar del resto**. El orden de trabajo del 2026-09-08 es
> estricto y este PRD es lo **último** de la lista:
>
> 0. Cerrar el trabajo de `/medir` del 3 de septiembre, sin commitear.
> 1. **Prioridad máxima:** los tres cambios de criterio validados con el
>    arquitecto — útil interior y exterior como dos sumas separadas, el fallo de
>    duplicación del «Tendedero» y el del «Baño» en `sin_clasificar`.
> 2. La demo del `ACAD_TABLE` relleno, ya con las dos sumas nuevas y la marca `C3`.
> 3. **Sólo si queda tiempo:** las tareas 1-4 y 7-8 de la §11 de este PRD. El
>    `.lsp` (tareas 5 y 6) queda para el día del trial.
>
> **Consecuencia sobre la §14.1, y conviene que quede escrita.** La objeción de
> fondo era que el criterio de medición no estaba firmado. El punto 1 del orden
> de trabajo la resuelve para tres de las cuatro preguntas: el arquitecto ya
> dictaminó que interior y exterior van separados, que el «Tendedero» duplicado
> se avisa y no se suma, y que un «Baño» es siempre interior. **Queda abierta la
> cuarta** — la tasa real de discrepancias memoria↔plano (`R-2`) —, que es la
> que gobierna el PRD del 2026-08-22, no éste.

> **CORRECCIÓN DE LOS HECHOS (2026-09-10). El «Tendedero duplicado» no era una
> duplicación: era un contorno.** Esta nota lleva desde el 2026-09-08 hablando
> de un fallo de duplicación del «Tendedero», y la duplicación no existía.
> Medido sobre `v1plantas.dxf`: lo que parecían dos tendederos era **un
> tendedero de 4,22 m² y el contorno de 8,63 m² que lo agrupa con la terraza** —
> cubre el 94,8% del uno y el 92,7% de la otra. Se colaba como una habitación
> más porque `_discard_container_candidates` exigía que el polígono contenido
> estuviera en BYLAYER, y este estudio dibuja sus piezas exteriores en verde.
>
> Consecuencias, todas comprobadas: la vivienda declaraba **7,08 m² dibujados
> dos veces** y no publicaba **ninguna** superficie. Arreglado el 2026-09-10
> (`analyzer/parser.py`, `tests/test_contorno_agrupador.py`). El otro fallo de
> esta lista —el «Baño» en `sin_clasificar`— tampoco era de criterio: era que
> nadie decodificaba `Ba\U+00F1o` (`analyzer/texto_dxf.py`,
> `tests/test_escapes_unicode.py`).
>
> Los dos se daban por «cambios de criterio validados con el arquitecto». **Eran
> dos bugs**, y el criterio no hacía falta para ninguno de los dos. Lo que sí
> hacía falta era mirar el plano.

> **Encargo de Pablo (2026-09-08), literal en su alcance:** prototipo en AutoLISP
> para validar el flujo; el plugin nativo .NET vendrá después y sólo si el flujo
> convence; **hoy no se escribe nada de .NET/C#**. Pablo **no tiene AutoCAD
> instalado** — activará el trial cuando esto esté listo —, así que todo se
> escribe y se verifica **sin poder ejecutar el script real**.
>
> Este documento existe porque el propio encargo pedía avisar **antes** de tocar
> `/api/medicion` si el formato actual no admitía el payload. **No lo admite**
> (§4.1), y averiguar por qué ha destapado tres cosas más que cambian el plan.

---

## 0. Las cuatro cosas que cambian el encargo, por delante

1. **El endpoint no admite el payload, y el motivo no es el formato: es que no
   hay costura.** `/api/medicion` no sólo exige `multipart` con un fichero
   `.dxf` — todo el camino de abajo (Skill → `plano.medicion_de_la_planta` →
   `parser.leer_plano`) trabaja sobre una **ruta a un fichero** y un `Drawing`
   de ezdxf. Detalle y las dos salidas posibles en §4.1.

2. **El script no debe repetir el criterio de proximidad rótulo↔recinto.** El
   encargo pide extraerlo en AutoLISP «con el mismo criterio que el motor
   Python». Ese criterio **ya es código puro y sin ezdxf**
   (`parser.match_label_to_room` + `_capas_de_rotulo` + `_es_solo_numero`: capas
   válidas del plano, descarte de textos que sólo son cifra, dentro-del-polígono
   antes que cercanía). Reescribirlo en LISP crea una **segunda implementación
   de un criterio profesional**, que es justo lo que `D-7` y la regla de no
   duplicar prohíben. El script manda polilíneas y textos **en crudo**; el
   emparejamiento lo sigue haciendo el motor, una sola vez, donde ya está
   probado.

3. **AutoCAD LT no puede ejecutar este script, y hoy estás a punto de elegir un
   trial.** AutoLISP no tiene HTTP: la única vía es COM
   (`vlax-create-object "WinHTTP.WinHTTPRequest.5.1"`), y `vlax-create-object`
   **no existe en AutoCAD LT** — devuelve `nil` siempre. El trial tiene que ser
   de **AutoCAD completo**, no LT. Si el trial se gasta en LT, el prototipo
   entero es inejecutable.

4. **La tabla que se inserta en su plano es un entregable, y `C3` es
   innegociable.** «Todo entregable sale marcado como borrador para revisión de
   un colegiado, sin excepción y sin opción de desactivarlo»
   (`alineacion-estrategica-paso0.md` §3, criterio de aceptación de todo PRD
   nuevo). El encargo no lo menciona: la tabla necesita una fila que lo diga, y
   no puede ser opcional. Importa más aquí que en el PDF, porque un PDF se
   archiva y **una tabla nativa se queda dentro del plano que se entrega**.

---

## 1. Problema que resuelve

Hoy el flujo es: el arquitecto exporta un DXF, abre un navegador, sube el
fichero, lee un PDF y **copia las cifras a mano** a su cuadro de superficies.
La medición está automatizada; el viaje de vuelta al plano, no. Ese copiado
manual es precisamente el trabajo que se venía a delegar — el mismo argumento
con el que el 2026-09-03 se añadió el total de planta: «un cuadro sin total
obliga al arquitecto a sumar la columna a mano».

Origen: petición directa de Pablo, 2026-09-08, inmediatamente después de dar el
motor por sólido.

## 2. Usuario afectado

El arquitecto o delineante que **vive dentro de AutoCAD** y no quiere salir de
él. Es el usuario de hoy, no uno de horizonte futuro: es el mismo perfil que el
del experimento de validación de una semana abierto el 2026-09-03.

## 3. Objetivo de negocio

Dos cosas, y la segunda vale más que la primera:

- **Retención.** Una herramienta que vive en la barra de comandos del programa
  donde ya se trabaja se usa; una que exige exportar, subir y copiar se usa una
  vez. `MOAT_ANALYSIS.md` sitúa la fricción de entrada como motivo principal de
  no volver.
- **Es la prueba de `C1`, ejecutada de verdad.** `C1` dice: «si mover una
  capacidad a un plugin de Revit exigiera reescribirla, está mal construida», y
  la §5.1 de ese documento la define como prueba operativa. Hasta hoy nadie la
  ha corrido. Este PRD la corre contra AutoCAD, y **su resultado es el criterio
  de éxito real del prototipo**, por encima de si la tabla queda bonita.

## 4. Objetivo técnico

Que sea cierto, después:

- **El motor de medición no cambia ni una línea.** `medicion.medir_planta()`
  recibe el mismo objeto y produce el mismo `Medicion`, con los mismos tres
  impedimentos y la misma regla dura de totales.
- Existe un **segundo modo de entrada** que, partiendo de geometría en crudo,
  produce exactamente el mismo objeto que produce hoy la lectura de un DXF.
- El mismo criterio de rótulo, la misma detección de escala y la misma acta de
  procedencia (`C2`) que hoy.
- El script AutoLISP es **un invocador tonto**: selecciona, serializa, envía y
  dibuja lo que le devuelven. No decide nada.

### 4.1 Por qué `/api/medicion` no admite el payload (respuesta a la pregunta del encargo)

Tres barreras, en orden de profundidad:

1. **La superficial.** `app.py:3453-3457` lee `request.files["dxf"]` y devuelve
   `400` si no hay fichero o si el nombre no acaba en `.dxf`. Un cuerpo JSON
   muere ahí, antes de llegar a nada.
2. **La real.** `_ejecutar_medicion_de_planta` (`app.py:3017`) escribe el
   fichero en un temporal y ejecuta la Skill `superficies.medicion_de_planta`
   por el Ejecutor. La capacidad de debajo, `plano.medicion_de_la_planta`
   (`agente/herramientas/medicion.py:93`), tiene por primer argumento
   `ruta: str` y empieza comprobando que ese fichero existe. **Ningún punto de
   ese camino acepta geometría.**
3. **La que no se ve.** El contrato de esa capacidad está **congelado** en
   `tests/fixtures/contratos_de_capacidad.json` (`CAD-2`): cambiarle la firma
   rompe el guardián. Y añadir una capacidad nueva
   (`plano.medicion_de_geometria`) sube el registro **de 13 a 14**, cuando el
   guardián de `C4` ya está **rojo a propósito** en 13 > 12 y `D-12` sigue sin
   decidir. O sea: la salida aparentemente limpia es la que despierta una
   decisión tuya abierta desde el 19 de agosto.

**La buena noticia, y es la que abarata todo esto:** la costura correcta existe
un nivel más abajo y está limpia. `medir_planta(plano)` sólo toca `.rooms`,
`.unit_labels` y `.geometria_no_leida`; `Room` es `(label, polygon, layer)`;
`escala.detectar_escala(insunits, areas)` es una función pura de números;
`match_label_to_room` es pura sobre polígonos y tuplas. **Nada de eso importa
ezdxf.**

**Dos salidas, y recomiendo la A:**

- **A — Materializar un DXF temporal en el servidor.** El endpoint nuevo recibe
  el JSON, escribe con ezdxf un DXF mínimo en el temporal (polilíneas y textos
  en sus capas) y llama al camino que **ya existe, entero y sin tocar**: misma
  Skill, misma acta, mismo PDF, mismo mecanismo de efectos y autorización
  (`SEG-1`), mismo guardián de contrato. Cero capacidades nuevas → **`D-12` no
  se toca**. El *handle* real de AutoCAD de cada polilínea viaja en el payload y
  se adjunta al acta, así que la procedencia sigue apuntando a la entidad del
  plano del arquitecto y no a la del fichero sintético.
  **Coste: un fichero nuevo, ~120 líneas, ninguna modificación de lo existente.**
- **B — Una segunda constructora de `PlanoLeido`.** Más elegante y más rápida
  (se ahorra escribir y releer un DXF), pero exige capacidad nueva o cambio de
  contrato congelado: despierta `D-12`. **Es la salida buena para el plugin
  .NET, no para un prototipo desechable.**

Para un prototipo cuyo propósito declarado es «validar el flujo», gastar la
decisión de `C4` es un precio absurdo. **A** — aprobada por Pablo el 2026-09-08.

> **Precisión sobre el alcance real del contrato congelado** (comprobado el
> 2026-09-08 al planificar el cambio de las dos sumas). `contratos_de_capacidad.json`
> congela de cada capacidad **los parámetros de entrada, los obligatorios, los
> efectos, la naturaleza, el recuento de limitaciones y la versión** — *no* la
> forma de su salida. Así que cambiar los campos que devuelve
> `plano.medicion_de_la_planta` (`total_util_m2` → dos sumas separadas) **no
> rompe `CAD-2`**; lo que sí lo rompería es cambiarle la firma, que es
> exactamente lo que la salida B exigía. La barrera 3 de arriba sigue en pie tal
> como está escrita, pero conviene no leerla más ancha de lo que es.

### 4.2 El formato de respuesta que el script puede leer

AutoLISP **no tiene parser JSON**. Escribir uno en LISP (~150 líneas, sin
tests posibles sin AutoCAD) sería la pieza más frágil del prototipo y justo la
que no se puede verificar antes del trial.

**Recomendación:** el endpoint nuevo devuelve, además del JSON, la misma
respuesta como **s-expresión** (`?formato=lisp`), que AutoLISP lee con `read`
en una línea. Es una función de presentación en el servidor —donde hay tests—
en vez de un parser en el cliente —donde no los hay—. Diez líneas de Python
sustituyen a ciento cincuenta de LISP no verificable.

## 5. Casos de uso

1. **Camino feliz.** El arquitecto teclea `ARCHMUSE`, acepta la capa detectada,
   pulsa un punto y aparece una tabla nativa con útil interior, útil exterior,
   total y la marca de borrador.
2. **Capa no detectada.** El script pregunta en la línea de comandos, con la
   misma lista de capas candidatas que hoy propone el formulario web.
3. **Vivienda bloqueada.** Un solape o una pieza sin clasificar: la fila del
   total **dice el motivo**, con su magnitud, y no da número.
4. **Planta incompleta.** Falta una vivienda: no hay total de planta, y la tabla
   lo dice con el nombre de la que falta.

## 6. Casos límite

| Caso | Qué debe pasar |
|---|---|
| Servidor apagado | Mensaje claro en la línea de comandos («ArchMuse no responde en localhost:5000»). Nunca una tabla vacía |
| Selección vacía o sin polilíneas cerradas | Se dice y se sale. No se inserta nada |
| Polilínea con arcos (*bulge*) | **Se declara.** La serialización por vértices pierde el arco y el área saldría corta: entra como geometría no leída, igual que hoy hace `geometria_no_leida` |
| Bloques anidados | El motor Python los recorre (`_recorrer_plano`); `ssget` en LISP **no entra en bloques**. Diferencia real de alcance frente a la web: se declara, no se disimula |
| `$INSUNITS` = 0 o imperial | Misma respuesta que hoy: se pregunta, o se rechaza (`NO_METRICOS`), sin convertir |
| Plano grande | 6 viviendas ≈ 12 s medidos hoy. AutoCAD se queda congelado ese rato: hay que avisar antes de enviar |
| Respuesta con acentos | UTF-8 desde Flask, AutoLISP en Windows lee ANSI. **Riesgo real de mojibake** en los motivos («VT6/2 no lleva…»). Se prueba explícitamente |

## 7. Flujo del usuario

1. `APPLOAD` → `archmuse.lsp`. 2. Teclea `ARCHMUSE`. 3. El script propone la capa
detectada; se acepta o se corrige. 4. Selecciona recintos, o toma la capa entera.
5. Avisa «midiendo, ~10 s» y hace el POST. 6. Pide punto de inserción.
7. Inserta la tabla. 8. Si algo está bloqueado, la tabla lo dice en su fila.

## 8. Criterios de aceptación

- [ ] Test de integración del endpoint en verde con el payload **exacto** que
      mandaría el script, derivado de `ejemplo.dxf` **y** de `v2s.dxf`.
- [ ] Ese test comprueba que las cifras coinciden **al céntimo** con las que
      devuelve hoy `/api/medicion` sobre el mismo DXF. Si divergen, el modo nuevo
      está midiendo por su cuenta, y eso es un fallo, no una tolerancia.
- [ ] El caso bloqueado (VT6/2, solape de 8,47 m²) llega a la salida **con su
      motivo**, no como un total ausente y silencioso.
- [ ] `archmuse.lsp` escrito, cada función contrastada contra la referencia
      oficial de Autodesk, y **con la lista de lo no verificable sin AutoCAD** al
      principio del propio fichero.
- [ ] La tabla lleva la marca de borrador de `C3`, con un test que falla si
      alguien la quita.
- [ ] `docs/design/checklist-primera-prueba-autocad.md` escrito.
- [ ] `PROGRESS.md` declara explícitamente qué **no** se ha podido verificar.

## 9. Riesgos

**R-1 · El prototipo puede no validar nada.** Si falla, no se sabrá si falló el
*flujo* o si falló *AutoLISP*. Un fallo de COM, de codificación o de `ssget` en
bloques no dice nada sobre si el arquitecto quiere esto. *Mitigación:* el
checklist separa, prueba a prueba, «esto es del flujo» de «esto es del lenguaje».

**R-2 · Compite con la validación en curso.** La semana abierta el 2026-09-03
—arquitecto real, DXF real, informe de superficies— está **sin terminar**, y sus
cuatro preguntas abiertas (terrazas al 100%, vocabulario de rótulos, solapes,
tasa de discrepancias) **pueden cambiar la cifra que esta tabla escribe**.
Construir el transporte antes de saber qué número transporta es trabajo que se
rehace.

**R-3 · El árbol está sucio.** Hay 11 ficheros modificados y 6 sin seguir — el
trabajo de `/medir` del 3 de septiembre, **sin commitear**. Empezar una
capacidad nueva encima mezcla dos cosas en el mismo diff.

**R-4 · Trial quemado.** Días de licencia gastados depurando sintaxis. Es
exactamente lo que el checklist existe para evitar, y la razón por la que el
punto 3 del encargo es el más valioso de los tres.

**R-5 · LT.** Ver §0.3. Elegir mal el trial invalida el prototipo entero.

## 10. Impacto sobre módulos existentes

| Fichero | Qué le pasa |
|---|---|
| `analyzer/medicion.py` | **Nada.** Es el punto entero de la salida A |
| `analyzer/parser.py`, `analyzer/escala.py` | **Nada.** Se reutilizan sus funciones puras |
| `agente/` (Skill, capacidades, contratos) | **Nada.** La salida A entra por el camino ya existente |
| `app.py` | Ruta nueva `/api/medicion-geometria` y serializador s-expresión. **No se toca `/api/medicion`** |
| `autocad/archmuse.lsp` | Nuevo |
| `tests/` | Test de integración nuevo con los dos payloads |

Consumidores indirectos afectados: **ninguno**. `/medir`, `/api/acta-legible`,
`/api/preguntar` y `/api/memoria-superficies` siguen entrando por donde entraban.

## 11. Plan de implementación

| # | Tarea | ~ | Estado |
|---|---|---|---|
| 1 | Extraer de los dos DXF reales el payload que mandaría el script | 1 h | **HECHO** 2026-09-08 — `geometria_recibida.payload_desde_dxf()`, derivado de los dos fixtures anónimos y no escrito a mano |
| 2 | `/api/medicion-geometria`: JSON → DXF temporal (ezdxf) → camino existente | 2 h | **HECHO** 2026-09-08 |
| 3 | Test de integración: cifras idénticas a `/api/medicion` sobre ambos planos, al céntimo | 1,5 h | **HECHO** 2026-09-08 — 28 tests |
| 4 | Serializador s-expresión y su test | 1 h | **HECHO** 2026-09-08 |
| 5 | `archmuse.lsp`: selección, serialización, POST por COM | 2 h | **HECHO Y EJECUTADO** 2026-09-09 en AutoCAD 2027, sobre `V5.dxf`: capa `00 areas`, 22 polilíneas, POST y respuesta correctos |
| 6 | `archmuse.lsp`: tabla nativa (`vla-AddTable`), marca `C3`, motivos de bloqueo | 2 h | **HECHO**, ejecutado a medias 2026-09-09: tabla, cifras y marca `C3` correctas; el ancho de columna partía el texto (corregido 2026-09-10, **sin volver a ejecutar**) y **el camino de vivienda bloqueada sigue sin ejecutarse** — `V5.dxf` no tiene ninguna |
| 7 | Checklist de primera prueba | 1 h | **HECHO** 2026-09-08 |
| 8 | `PROGRESS.md` con lo no verificado | 0,5 h | **HECHO** 2026-09-08 |

**11 h.** Las tareas 5 y 6 son las únicas que **no se pueden probar** hasta el
trial; 1-4 y 7-8 se cierran hoy con la suite en verde.

## 12. Plan de pruebas

- Payloads derivados de `ejemplo.dxf` (6 viviendas, una bloqueada por solape) y
  de `v2s.dxf`. Se **derivan** del DXF, no se escriben a mano: un payload
  inventado probaría el test, no el producto.
- Comparación **al céntimo** contra la salida de `/api/medicion` — el guardián
  de que no hay una segunda medición.
- Caso bloqueado, caso de planta sin total, caso de capa no resuelta.
- Suite completa (1350) en verde: nada de esto toca los caminos existentes.
- **Lo que no se puede probar sin AutoCAD:** todo `archmuse.lsp`. Se declara, no
  se simula. Un *mock* de AutoCAD daría confianza falsa sobre lo único que este
  prototipo existe para averiguar.

## 13. Métricas para medir el éxito

1. **La prueba de `C1`:** ¿cuántas líneas del motor hubo que reescribir? La
   respuesta correcta es **cero**. Si es más, `C1` está incumplido y ese hallazgo
   vale más que el prototipo.
2. Días de trial hasta la primera tabla correcta insertada. Objetivo: **1**.
3. ¿El arquitecto vuelve a teclear `ARCHMUSE` sin que se lo pidan?

## 14. Posibles motivos para NO implementar la idea

**14.1 · El orden está invertido, y es la objeción de fondo.** El encargo dice
«motor ya sólido». El motor mide bien lo que sabe medir — pero **cuatro
preguntas de criterio siguen sin contestar**, y las cuatro afectan al número que
esta tabla escribiría en el plano de un cliente: si las terrazas van al 100% en
el total (hoy sí, sin coeficiente), qué vocabulario de rótulos se reconoce (hoy
8 familias, el resto bloquea el total), si un solape es fallo del plano o
convención del autor, y la tasa real de discrepancias. **Automatizar la escritura
de una cifra en el plano del arquitecto antes de que un colegiado firme el
criterio con el que se calcula es acercarse a la autoría por la puerta de
atrás** — la frontera que `C3` y `NORTH_STAR_2031.md` §5 declaran innegociable.
Un PDF se lee y se descarta; una tabla nativa se queda dentro del plano que se
visa.

**14.2 · El prototipo desechable puede no salir más barato que el bueno.** Si el
flujo convence, todo el LISP se tira. Si no convence, no se sabrá si fue el flujo
o el lenguaje (`R-1`). Un prototipo cuyo fracaso no es informativo es un
prototipo caro.

**14.3 · Hay una alternativa mucho más barata para validar lo mismo.** Lo que se
quiere saber es «¿el arquitecto quiere el resultado dentro de su plano?». Eso se
contesta en **media hora y sin una línea de LISP**: `superficies.cuadro_de_vivienda`
**ya rellena el `ACAD_TABLE` del propio DXF** (existe, aprobado, `SK-1`).
Devuélvele su DXF con el cuadro relleno y mira si le cambia la cara. Si le
cambia, el prototipo AutoLISP queda justificado y además ya sabes qué columnas
quiere. Si no le cambia, te has ahorrado 11 horas y unos días de trial.

**14.4 · Nada de esto es `C5`.** El corpus normativo sigue con **cero reglas
firmadas** y es, por decisión escrita, lo único en el camino crítico. Ni este PRD
ni ningún otro lo desbloquea, pero conviene decirlo cada vez que se abre uno.

---

### Recomendación

**Aprobar, con dos condiciones y en este orden:**

1. **Antes:** enseñarle al arquitecto el DXF con el `ACAD_TABLE` ya relleno
   (§14.3) y contestar las cuatro preguntas de criterio. Media hora, hoy, con él
   delante.
2. **Al aprobar:** la salida **A** de la §4.1 (DXF temporal, `D-12` intacto) y la
   respuesta en s-expresión de la §4.2.

Si se prefiere arrancar ya, **el alcance mínimo defendible son las tareas 1-4 y
7-8** — servidor, tests y checklist: todo lo verificable sin AutoCAD —, dejando
5 y 6 para el día que empiece el trial. Así nada de lo escrito hoy queda sin
comprobar, y el checklist llega antes que el primer día de licencia, que es lo
que el propio encargo quería proteger.

**Decisión:** _pendiente de revisión por Pablo_
