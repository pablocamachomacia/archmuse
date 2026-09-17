# PRD — Modo preguntar: tablas completas sin inventar ninguna cifra

**Estado:** Aprobado en el encargo · **Fecha:** 2026-09-17 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo, en el mismo encargo («Descongelo el código. Trabaja de forma autónoma: PRD → tests → implementación → suite completa → commit/push»). Las decisiones de cómo se lee cada respuesta (§4, D-1 a D-12) son de Claude y quedan **propuestas, pendientes de firma**; lo que dijo Pablo va entre comillas.

---

## 1. Problema que resuelve

El banco del plano maestro (2026-09-17) da 15 de 25 viviendas que coinciden en todo
con el cuadro del arquitecto y **0 cifras incorrectas**. Las otras 10 no están mal:
están incompletas. ArchMuse deja la celda vacía con motivo cuando no puede demostrar
un dato, y casi un tercio de esas celdas (34 de 49) lo resolvería una pregunta simple
al arquitecto (clasificación UN CLIC del banco). Hoy no se hace esa pregunta, así que
el arquitecto recibe una tabla con huecos que tiene que rellenar a mano, mirando las
notas.

Y una celda que el plano sí declara sale vacía siempre: `NUMERO UDS`. El plano maestro
escribe «8uds.», «1 ud.», «3 uds.» junto al rótulo de cada tipo; ArchMuse dice «el
plano lo declara, pero leer lo que el plano declara (C-8) no está implementado».

Lo pide Pablo: «conseguir tablas completas sin inventar ninguna cifra, combinando
mejor deducción + preguntas al arquitecto». «No fuerces el objetivo de 25/25 si para
conseguirlo habría que asumir un dato. La prioridad es: 0 cifras inventadas.»

## 2. Usuario afectado

El arquitecto de la beta, en AutoCAD, con el comando ARCHMUSE (dos clics). La web no
pregunta (§6).

## 3. Objetivo de negocio

Que la tabla que se lleva el arquitecto esté terminada, no a medias. Una tabla con
cuatro celdas vacías y notas que leer ahorra menos de lo que parece; una con una
pregunta de un segundo y ninguna celda vacía es el producto.

## 4. Objetivo técnico

1. **Modo preguntar.** Cuando ArchMuse no puede determinar un dato con certeza y una
   respuesta cerrada del arquitecto lo resolvería, se la pide en AutoCAD:
   - **Pieza que puede ser de dos viviendas:** se resalta y «¿Esta pieza es de VT15/3?
     [Si/No]».
   - **Superficie construida no identificada:** «Haz clic en la polilínea de
     superficie construida de VT15/3», y se mide la que marque.
   - **Nombre dudoso** (`C-18`, dos nombres dentro): se resalta y se ofrecen los
     nombres, numerados. Y la pregunta que ya existía, interior o exterior de una
     familia que ArchMuse no reconoce, entra en el mismo turno.
2. **Antes de preguntar, todas las deducciones deterministas** que ya existen (`C-12`,
   `C-17`, `C-20`, `C-21`, reparto por cercanía): sólo se pregunta lo que queda.
3. **Como mucho 3 preguntas por vivienda**, las que más celdas rellenan; si harían falta
   más, la nota dice cuántas celdas quedan vacías.
4. **Las respuestas persisten** asociadas al plano: la siguiente vez no se pregunta.
5. **Esc** (o Enter sin contestar): la celda queda vacía y el motivo lo dice.
6. **Trazabilidad:** todo dato que depende de una respuesta lleva «Confirmado por el
   arquitecto», en la nota de detalle y contado en las notas del dibujo.
7. **`C-8`, número de unidades:** se lee del rótulo de la vivienda cuando lo declara.
8. **Banco:** mide VT6/2, VT7/2, VT15/3 y VT17/1 con un arquitecto simulado (§12).

### Decisiones propuestas, pendientes de firma

- **D-1 · Identidad de una pieza:** su handle en el dibujo. **De una vivienda:** su
  rótulo y la posición del rótulo (la misma identidad que ya usa el clic, `C-17`, con su
  tolerancia de 1 cm). Si el arquitecto borra y redibuja la pieza o mueve el rótulo, la
  respuesta deja de aplicarse y se vuelve a preguntar: falla hacia preguntar, nunca
  hacia una cifra.
- **D-2 · Dónde se guardan:** fuera del dibujo, en la carpeta de datos de ArchMuse
  (`respuestas-del-arquitecto/`), un fichero por plano identificado por la ruta completa
  del DWG. **Nunca en su DWG** (`C-16`: ArchMuse sólo añade al dibujo la tabla). Un
  plano copiado o renombrado vuelve a preguntar. **Nunca se guarda una cifra**: sólo a
  qué vivienda pertenece un handle, qué handle es la construida, qué nombre tiene un
  handle y qué ámbito tiene una familia. Las cifras se miden cada vez.
- **D-3 · Esc o Enter sin contestar no se guarda.** La celda queda vacía, la nota añade
  «El arquitecto no ha respondido», el registro lo cuenta, y la siguiente vez se vuelve
  a preguntar. Guardarlo obligaría a un comando para «desrechazar».
- **D-4 · «Sí» a una vivienda es «No» para todas las demás:** una pieza es de una sola
  vivienda. **«No» no se la da a nadie**: sólo sale de esa tabla, con nota.
- **D-5 · Con «No», la tabla se cierra sin esa pieza**: sus totales se calculan con las
  demás. Es la respuesta del arquitecto la que lo permite, y la nota lo dice.
- **D-6 · Construida marcada:** se mide y sólo se escribe si pasa la comprobación de
  `C-12` (contiene todas las piezas interiores de la tabla y ninguna exterior, 5 cm).
  Si no pasa, vacía con motivo y **no se guarda**. Si el plano rotula sin duda otra
  polilínea distinta de la marcada, vacía con motivo: dos declaraciones que no coinciden
  no se resuelven hacia ninguna.
- **D-7 · Qué preguntas son «las más importantes»:** el conjunto de hasta 3 que rellena
  más celdas si la respuesta es la que completa la tabla; a igualdad, el de menos
  preguntas; después, el orden de la tabla. Un total sólo cuenta si con esas respuestas
  no le queda ningún bloqueo. Nunca se pregunta algo que no rellenaría ninguna celda.
- **D-8 · El tope de 3 es por vivienda y por pasada del comando**, e incluye la de
  interior/exterior. Tras contestar se vuelve a medir; si aparece una pregunta nueva y
  queda cupo, se hace.
- **D-9 · Nº de unidades (`C-8`):** un número entero ≥ 1 seguido de «ud», «uds»,
  «unidad» o «unidades» (con o sin punto, espacio o mayúsculas) **en el propio rótulo**
  («VT1/3 8 uds», «VT1/3 - 8 uds.», «VT1/3 (8 uds)», «VT1/3\P8 uds») **o en un texto
  suelto que sólo diga eso** a menos de 3 alturas del rótulo y más cerca de él que de
  cualquier otro rótulo de vivienda. Dos declaraciones que no dicen el mismo número, o
  ninguna: vacía con motivo. Medido en el plano maestro: 25 textos «N ud(s).» a 1,5-1,7 alturas debajo del
  rótulo de su tipo; el rótulo de otro tipo, a más de 13 m.
- **D-10 · Nota de trazabilidad:** en el detalle, «Dormitorio 1, S. CONSTRUIDA C.:
  Confirmado por el arquitecto.»; en el dibujo, «Confirmado por el arquitecto: N
  dato(s)». Los totales calculados con respuestas no se marcan: son cálculo de ArchMuse
  sobre datos marcados.
- **D-11 · Piezas de la vecina:** se preguntan («¿Esta pieza es de VT15/3?») si su reparto
  por cercanía duda entre la vecina y ésta, o si el plano las mete en la construida
  rotulada de ésta. Con «Sí» entra en la tabla; su cupo cuenta aquí.
- **D-13 · Una pieza de la vecina que duda si es de ésta bloquea también los totales de
  ésta** (`C-5`, la ambigüedad es de las dos). *Medido el mismo día en el banco:* se probó
  a no preguntar esas piezas (parecían preguntas de más) y, al contestar «Sí» a la única
  pieza dudosa de VT13/3, sus totales salieron **sin dos piezas que su cuadro le da** y
  que se habían medido con VT14/3: 2 cifras incorrectas. Antes del modo preguntar el agujero
  existía igual, tapado por el otro bloqueo. Afecta también a la web y al agente.
- **D-12 · No se pregunta lo que ninguna respuesta cerrada arregla:** piezas dibujadas
  dos veces, contornos rotulados como construida (`C-20`), piezas sin rótulo o con un
  código por nombre (`C-18`), cifras que redondean a cero (`D-13`), viviendas
  indistinguibles sin clic (`C-13`).

## 5. Casos de uso

1. **Construida sin rótulo que la identifique** (VT7/2 del maestro): una pregunta, un
   clic en la polilínea, tabla completa.
2. **Dos piezas dentro de la construida rotulada de la vecina** (VT17/1): dos
   preguntas; con «No» a las dos, la tabla se cierra y la construida rotulada de esta
   vivienda ya pasa la comprobación de `C-12` sin preguntar.
3. **Tres piezas en duda y la construida** (VT15/3): cuatro preguntas harían falta; se
   hacen tres y la nota dice cuántas celdas quedan.
4. **Segunda vez sobre el mismo plano:** no pregunta nada; la tabla sale con las notas
   «Confirmado por el arquitecto».

## 6. Casos límite

- **Web y agente:** no preguntan ni guardan. Leen el número de unidades (`C-8`) igual
  que el comando (`C-9`: las dos vías leen igual el plano; las respuestas no son plano).
- **Plano sin guardar** (sin ruta): se pregunta, pero no se guarda.
- **Un handle guardado que ya no existe:** se ignora y se pregunta otra vez.
- **Clic en algo que no es una polilínea cerrada:** se dice y se vuelve a pedir, hasta
  tres intentos; después, sin respuesta.
- **Respuesta contradictoria guardada** (dos «Sí» a viviendas distintas): gana la
  última, que es la que el arquitecto dio después.
- **Esc en cualquier otra parte del comando:** igual que hoy («Cancelado con Esc»).

## 7. Flujo del usuario

1. ARCHMUSE → clic en la vivienda → «Midiendo…».
2. Si hay algo que preguntar (como mucho 3):
   `ArchMuse necesita 2 respuestas para completar la tabla de VT17/1.`
   `«Dormitorio 1» (resaltada) está dentro de la superficie construida que el plano rotula para VT16/3.`
   `¿Esta pieza es de VT17/1? [Si/No] <sin contestar>:`
3. Vuelve a medir con las respuestas, guarda las respuestas y sigue como hoy (tabla,
   segundo clic).

## 8. Criterios de aceptación

1. Con una respuesta «Sí», la celda de la pieza lleva su cifra medida y la nota
   «Confirmado por el arquitecto»; con «No», la pieza no está en la tabla y la nota lo
   dice; sin respuesta, vacía con «El arquitecto no ha respondido».
2. Una construida marcada que contiene la vivienda escribe su superficie medida; una que
   no, deja la celda vacía con motivo.
3. Nunca más de 3 preguntas por vivienda en una pasada; si quedan, la nota dice cuántas
   celdas vacías quedan.
4. Guardadas las respuestas, la segunda medición del mismo plano no pregunta nada y da la
   misma tabla.
5. Ninguna cifra sale de una respuesta: las respuestas sólo dicen pertenencia, nombre,
   ámbito o qué polilínea es la construida (test sobre el almacén).
6. `NUMERO UDS` sale del rótulo en las formas de D-9, y vacía con motivo en las demás.
7. Banco: 0 cifras incorrectas con el arquitecto simulado, y las cuatro viviendas
   medidas con sus cifras de §13.
8. Suite completa en verde.

## 9. Riesgos

- **El `.lsp` no se puede probar entero fuera de AutoCAD**: `getkword`/`entsel` dentro
  de `vl-catch-all-apply` para que Esc no cancele el comando, y el resaltado con
  `redraw`, quedan **sin ejecutar en AutoCAD** hasta la prueba de Pablo (§ «Qué probar»).
- **Una respuesta guardada que ya no es verdad** (el arquitecto cambia el reparto de
  piezas sin cambiar los handles): se aplica. Mitigación: la nota «Confirmado por el
  arquitecto» va siempre en la tabla, así que se ve.
- **El arquitecto simulado del banco usa su cuadro para contestar**: mide cuántas
  preguntas harían falta y si con ellas la tabla sale bien, no si él contestaría así.

## 10. Impacto sobre módulos existentes

- `analyzer/parser.py`: `Room.handle` (nuevo, opcional).
- `analyzer/unidades_declaradas.py` (nuevo): `C-8` para el número de unidades.
- `analyzer/respuestas_del_arquitecto.py` (nuevo): modelo, lectura de la petición,
  almacén.
- `analyzer/plantilla_cuadro.py`: `construir` aplica respuestas, genera y prioriza las
  preguntas, nota de trazabilidad, `NUMERO UDS`.
- `app.py`: `/api/medicion-geometria` (plano, respuestas, guardar) y
  `/api/vivienda-en-punto` (polilíneas marcadas que tiene que mandar el comando).
- `autocad/archmuse.lsp` 3.10.0: el turno de preguntas.
- `benchmark/ejecutar.py`: arquitecto simulado y número de unidades.
- Textos que citaban `C-8` sin implementar: `agente/herramientas/plano.py`,
  `docs/beta/INSTRUCCIONES.md`, tests.

## 11. Plan de implementación

- T1 `Room.handle` en el lector (1 h).
- T2 `C-8` número de unidades + tests de variantes (1,5 h).
- T3 Respuestas: modelo, lectura, almacén + tests (1,5 h).
- T4 `construir` con respuestas: pertenencia, nombre, ámbito, construida, notas (2 h).
- T5 Preguntas: candidatas, prioridad, tope 3, nota de lo que queda (2 h).
- T6 Endpoints + tests de ida y vuelta con guardado (1,5 h).
- T7 `.lsp` 3.10.0 + tests estáticos (2 h).
- T8 Banco con arquitecto simulado; medir las cuatro viviendas (2 h).
- T9 Criterios, PROGRESS, folio; suite; commit, push; 0.3.30 en «prueba» (1,5 h).

## 12. Plan de pruebas

- Planos sintéticos (nunca DXF real, repo público): pertenencia con Sí/No/sin
  respuesta, pieza de la vecina, construida marcada válida e inválida, nombre `C-18`,
  tope de 3 y nota, segunda pasada sin preguntas, `C-8` con sus variantes.
- Endpoint: ida y vuelta con `ARCHMUSE_DATA_DIR` temporal.
- `.lsp`: pruebas estáticas del estilo de `tests/test_dos_clics.py`.
- **Banco** (fuera del repositorio, plano maestro): arquitecto simulado que contesta
  con su cuadro — pertenencia «Sí» si su cuadro tiene esa estancia con esa cifra, «No»
  si su cuadro no tiene ninguna fila libre de esa familia, y si no, sin respuesta;
  construida, la polilínea que pasa `C-12` con la cifra de su cuadro (si no hay una,
  sin respuesta); nombre y ámbito, el que casa con su cuadro. Se mide lo pedido: celdas
  indeterminadas al principio, preguntas, completas después, lo que sigue sin resolver.

## 13. Métricas para medir el éxito

- Banco del maestro con arquitecto simulado: cifras incorrectas = 0; viviendas completas
  antes y después; preguntas por vivienda.
- `NUMERO UDS`: coincidencias con su cuadro (25 cuadros).
- En la beta: preguntas contestadas frente a Esc (registro, sólo recuentos).

## 14. Posibles motivos para NO implementarlo

- **Preguntar es trabajo para el arquitecto.** Tres preguntas por vivienda en un bloque
  de 25 son 75. Contra eso: sólo se pregunta lo que el banco dice que quedaría vacío, y
  una vez por plano.
- **El riesgo de una respuesta equivocada es suyo, pero la cifra sale en una tabla de
  ArchMuse.** Por eso la marca «Confirmado por el arquitecto» es obligatoria y no se
  puede quitar desde el comando.
- **Alternativa descartada: nuevas deducciones** (por ejemplo, dar por ajena una pieza
  que está dentro de la construida rotulada de otra vivienda y fuera de la suya). Harían
  menos preguntas, pero son criterio sin firmar; aquí se pregunta, y si Pablo firma la
  deducción, la pregunta desaparece sola.
