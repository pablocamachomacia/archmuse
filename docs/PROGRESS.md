# PROGRESS — qué se hizo, qué se dejó fuera, qué se decidió

Lo pide el §0.5 de `ARCHMUSE_SPEC.md`: al terminar cada bloque, escribir qué se
hizo, qué se dejó fuera y qué decisiones se tomaron. Lo más reciente arriba.

---

## 2026-09-13 (noche) · `C-12` firmado: la construida por su rótulo; `.lsp` 3.6.0

**Visto bueno de Pablo** a la propuesta: identificar la polilínea por su rótulo,
nunca por color, con las dos formas del rótulo y 3 alturas de texto de alcance.
Tres condiciones: con más de una candidata no se elige; nunca por color, ni como
respaldo; guardián de «cifra sólo con exactamente una polilínea rotulada», roto
a propósito.

**Qué se hizo.**

- `plantilla_cuadro.medir_construida` reescrito: rótulos de cualquier capa →
  polilíneas de cualquier capa a menos de 3 alturas de su texto (más de una: no
  se elige y la nota las nombra) → que contenga todas las interiores y ninguna
  exterior. `C12_FIRMADO = True`. **El criterio por color de la propuesta
  anterior ya no existe.**
- `.lsp` 3.6.0: `am:otras-polilineas` manda las `LWPOLYLINE` del espacio modelo
  que no son de la capa de recintos, **sin color**; el servidor las recibe en
  `otras_polilineas`, aparte de los recintos, y las escribe en su capa. Una sin
  capa o de la capa de recintos se rechaza con motivo.

**Dos fallos que salieron al implementarlo, medidos, y su arreglo.**

1. **ezdxf escribe altura 2,5 en todo texto que llega sin ella** (y también si
   se le da 0). Se vio porque `test_c12_escenarios[sin_altura]` salió rojo con
   «4 polilíneas a menos de 7,50 m». El mismo fallo estaba en `D-14`:
   `alturas_de_rotulos` devolvía `[2.5, 2.5, …]` con un payload sin alturas y la
   tabla se maquetaba con una altura que nadie dibujó. **Esto no se había
   pedido**; se arregló porque es la misma línea: marca XDATA
   `ARCHMUSE_SIN_ALTURA` al escribir y `geometria_recibida.altura_de_texto` al
   leer, en los dos sitios.
2. **Por la vía del comando las notas nombraban handles que no existen en el
   plano del arquitecto.** La verificación sobre `ejemplo.dxf` dio para VT6/2
   «(A61863, CA4293)» por la web y otros handles por el comando: los del DXF
   materializado. El handle de origen viaja ahora en XDATA
   (`ARCHMUSE_HANDLE`, `handle_de_origen`); hoy sólo lo lee `C-12`.

**Sobre los siete DXF de `_material`, por las dos vías** (web leyendo el DXF;
comando con el payload que mandaría el `.lsp`), **cifra y nota idénticas en
todas las viviendas**, y la medición igual con y sin las otras capas:

| Plano | S. CONSTRUIDA C. |
|---|---|
| `v1plantas`, `v2s`, `v2s_ArchMuse_relleno` | 73,07 m² (`A6188E`) |
| `ejemplo` VT1-VT5 | 73,07 · 61,38 · 72,70 · 62,10 · 52,13 m², una rotulada cada una |
| `ejemplo` VT6/2 | vacía: «el rótulo (D6BC3D) tiene 2 polilíneas a menos de 0,38 m (A61863, CA4293): no se elige ninguna» |
| `V5`, `v3s` | vacías: el plano no rotula la construida |
| `plantasimple` (25) | vacías: sin piezas interiores (ver abajo) |

Es lo que se había previsto antes de escribir el código.

**Sin explicar y anotado:** en `plantasimple.dxf` leída por `00 areas` las 206
piezas salen «(sin rótulo)», así que ninguna vivienda tiene interiores y la nota
de la construida lo dice. Es un problema de lectura anterior a `C-12`, no de él.

**Fallos reintroducidos: 13 de 13 en rojo**, ficheros restaurados byte a byte.
El guardián (condición 3), roto de dos maneras: con dos rotuladas escribe la
mayor, y la cifra sale con «una o más». Condición 1: coger la más cercana, la
más grande, la primera, y callar un rótulo dudoso. Condición 2: respaldo por
color sin rótulo, y el `.lsp` mandando el color. Además: el `.lsp` sin mandar
las otras capas, el servidor sin escribirlas, rótulo por «contiene construida»,
alcance de 10 alturas, y el 2,5 de ezdxf en un texto sin altura.

**Suite entera:** 1944 pasan, 39 saltados, 1 xfail (D-7), 0 fallos, en
25 min 31 s con el venv. Los dos avisos de `ifcopenshell` de siempre. G11
recapturado: la única diferencia es la nota de la construida del piso del agente,
que no tiene rótulo.

**Queda abierto:** la envolvente que contiene un patio o el hueco de escalera; y la
capa `AM_CONS_CER` del contrato de clasificación, que es otra forma de declarar
la construida y `C-12` no usa.

---

## 2026-09-13 · `C-14` (TOTAL S. ÚTIL) implementado; `C-12` medido y a la espera

**Lo que llegó:** dos correcciones firmadas por un arquitecto colegiado tras ver
la tabla en AutoCAD. `C-14` cerrada; `C-12` firmada, pero con tres preguntas que
contestar antes de escribir código.

### `C-14`

TOTAL S. ÚTIL = útil interior + el menor entre el 50 % de la exterior y el 10 %
de la interior. Deroga la parte de `C-1` que dejaba la fila vacía (anotado en la
cabecera de `C-1`). `plantilla_cuadro.superficie_util_total` y `_total_util`;
como lo usan el comando, la web y el agente, las tres salidas cambian a la vez.

- **Los tres casos del criterio**, con sus cifras: 58,78/7,54 → 62,55;
  100/40 → 110; 100/0 → 100. Por la plantilla del fixture sintético: 45,95
  (tope no activo), 48,07 (tope activo), 43,70 (sin terraza).
- **Bloqueo:** si un lado no se puede afirmar, fila vacía con «…no se calcula
  sobre una cifra bloqueada (C-14)». Guardián que rehace el total desde lo
  escrito en cinco escenarios.
- **Decisiones mías, declaradas, sin firmar:** se calcula sobre las dos cifras
  ya redondeadas de la tabla; redondeo `ROUND_HALF_UP` en `Decimal`
  (7,55 → 62,56); un lado sin espacios aporta cero (así leo «sin exterior»).
- **Fallos reintroducidos: 8 de 8 en rojo** (máximo en vez de mínimo, exterior al
  100 %, sin tope, exterior bloqueada como cero, cálculo sobre medición
  bloqueada, lado vacío que bloquea, redondeo en coma flotante, fila vacía
  siempre), ficheros restaurados byte a byte.
- **Tests que cambiaron porque cambió el criterio, no por rotos:** el cierre y
  la `C-11` de `test_plantilla_cuadro.py` (45,95 es la única cifra derivada que
  se admite), `test_agente_plano.py` y `test_agente_skill_superficies.py` (ya no
  esperan la útil total entre lo no hecho; ahora el número de unidades) y G11
  recapturado: la única diferencia es la celda `45,00 m²` y la nota de `C-1` que
  desaparece. `test_toda_celda_vacia_de_cierre_tiene_su_nota` tenía un fallo mío:
  buscaba la nota por su principio y dos celdas comparten nota.
- **No tocado:** el cuadro antiguo por clonación
  (`cuadro_superficies.calcular_relleno_cuadro`, con su `N/D`), que ya no usa
  ninguna salida; y la medición, el acta y la API siguen publicando interior y
  exterior por separado, que es lo que queda de `C-1`.

**Suite entera:** 1904 pasan, 39 saltados, 1 xfail (D-7), 0 fallos, en
26 min 8 s con el venv. Los mismos dos avisos de `ifcopenshell` de siempre.
**Sin explicar:** las suites anteriores tardaban ~17 min y ésta 26. No
coincidió con la medición de `C-12` ni con la batería de afectados, que
acabaron antes de lanzarla; no se ha medido qué fue.

### `C-12`: lo medido, y la propuesta que espera visto bueno

**Hallazgos** (scripts de medición en el directorio temporal de la sesión, sobre
los siete DXF de `_material`; mi `v1plantas.dxf` es del 2026-09-10 20:58):

- En `v1plantas.dxf` **hay una sola polilínea roja discontinua** (`A6188E`, ACI
  10, `DASHED` explícito, 73,07 m², flag de cerrada sin poner) y **está en
  `00 areas`**, igual que las seis envolventes de `ejemplo.dxf`. Buscado también
  en bloques y presentaciones. Esto **contradice** dos cosas que se dijeron al
  firmar («no está en 00 areas», «hay dos rojas, una alrededor del Dormitorio
  3»). La del Dormitorio 3 (`A61769`) va por capa: ACI 30 naranja con
  `ACAD_ISO03W100`, como todas las estancias. **Hipótesis sin medir:** que lo
  que se vio rojo sea ese naranja, o que el plano abierto en AutoCAD sea más
  nuevo que esta copia. Se mide mirando capa, color y handle en Propiedades.
- El `.lsp` sólo manda las `LWPOLYLINE` de la capa de recintos
  (`am:recolectar`): una construida en otra capa la vería la web y no el
  comando (`C-9`). Mandar las de todas las capas pesa poco: máximo 236
  polilíneas / 2.703 vértices (`plantasimple`), 11 en `v1plantas`.
- Rótulos: «superficie construida cerrada» en `v1plantas`/`v2s`, **«s.
  construida cerrada»** en `ejemplo` y `plantasimple`. Borde de la envolvente a
  0,11–0,28 m del rótulo; lo siguiente, a 0,49 m o más. En `ejemplo`, VT6/2
  tiene un rótulo dentro de la polilínea de construida exterior y otro
  equidistante (1,876 / 1,889). En `plantasimple` los rótulos están a más de 5 m
  de cualquier polilínea.

**Propuesta enviada** (sin código): rótulo con texto exacto de un vocabulario a
firmar → la polilínea de cualquier capa cuyo borde esté más cerca, a menos de 3
alturas de texto y sin otra dentro de esa distancia → que contenga todas las
interiores y ninguna exterior. Sin color. Resultado previsto: `v1plantas` 1/1,
`ejemplo` 5/6 (VT6/2 vacía), `plantasimple`, `v3s` y `V5` vacías.
`C12_FIRMADO` sigue en `False` hasta el visto bueno.

---

## 2026-09-13 (madrugada) · `.lsp` 3.5.0: sin estilo de texto propio, anchos medidos en AutoCAD

**Lo que dijo la 3.4.1 en AutoCAD sobre `v1plantas.dxf`:** «No he podido dibujar
la tabla al crear el estilo de texto «ARCHMUSE» con arial.ttf: Error de
automatización. Error de archivador.» El mensaje nuevo funcionó: dijo dónde, con
qué y qué contestó AutoCAD. **La causa no era ninguno de los cuatro candidatos
anotados en la entrada anterior.**

**Lo que no se sabe, y queda escrito aunque el arreglo lo esquive** (Pablo: «un
acierto sin explicación es una hipótesis con suerte»). La 3.2.0 creó ese mismo
estilo, con el mismo código, sobre `v1plantas.dxf`, y dibujó. La 3.4.1 no pudo.
No se sabe por qué, ni cuál de las dos llamadas de ese paso falló (crear el
estilo o ponerle la fuente). Que la 3.2.0 funcionara no probó que el código
fuera correcto.

**Decisión (Pablo): ArchMuse no crea estilo de texto.** Depender de un `.ttf`
concreto es frágil, y `txt.shx` no lo mide el servidor. Ahora:

- La tabla se dibuja con **un estilo que ya existe en el plano**: el de su cuadro
  y, si no tiene, el más repetido de sus rótulos de estancia. Lo elige el
  servidor (`maquetacion_cuadro.estilo_de_texto`).
- **Sin cuadro ni rótulos, no se dibuja** y se dice por qué: «ArchMuse no inventa
  una fuente» (Pablo: «no inventes fuente: declara y no dibujes»).
- **Los anchos los mide AutoCAD** con `textbox`, en ese estilo y a altura 1. Qué
  medir lo decide el servidor (`textos_a_medir`); con esas medidas maqueta
  `/api/maquetar-cuadro`, sin volver a medir el plano. Una medida que falta no se
  sustituye a ojo. La web sigue midiendo con Arial: no tiene AutoCAD delante.

**Medido por el camino:** `ezdxf` no escribe el código 7 cuando vale «Standard»,
así que en el DXF materializado `dxf.get("style")` daba `None` y el servidor no
encontraba ningún estilo. Se lee `dxf.style`, que es lo que AutoCAD usa para un
texto sin código 7.

**Sin verificar en AutoCAD:** que `textbox` mida lo mismo que ocupa el texto
dentro de una casilla (holgura del 5 %). Checklist, casillas 22 a 24.

**Suite entera:** 1886 pasan, 39 saltados, 1 xfail (D-7), 0 fallos, en
17 min 19 s con el venv. Dos avisos de `ifcopenshell` (`KeyError` en
`file.__del__`) en `tests/test_bim_lector.py`, ajenos al cuadro: salen
iguales en todas las suites de estos días, desde la de referencia (1814).

---

## 2026-09-13 (madrugada) · `.lsp` 3.4.1: un fallo al dibujar dice en qué paso y por qué

**Lo que pasó en AutoCAD con la 3.4.0 sobre `v1plantas.dxf`.** Ya no preguntaba
«1 o 2» ni pedía ventana. El servidor resolvió 30 casillas y 4 notas, y el
comando dijo «No he podido dibujar la tabla. No se ha quedado nada a medias.» y
nada más. AutoCAD no mostró ningún error.

**Causa del silencio, medida leyendo el código.** `am:dibujar-cuadro` terminaba
en `(if (vl-catch-all-error-p (vl-catch-all-apply …)) nil tabla)`: capturaba el
error de AutoCAD y lo tiraba. Además `am:estilo-de-tabla` devolvía `nil` sin
motivo, las llamadas protegidas casilla a casilla se tragaban su fallo (una
casilla sin texto seguía contándose como «escrita»), y «no se ha quedado nada a
medias» no se comprobaba: una tabla ya creada se quedaba en el dibujo.

**Causa del fallo: SIN MEDIR.** Candidatos, todos nuevos en la 3.3.0 y nunca
ejecutados (lo que la 3.2.0 ya dibujó queda descartado): el estilo de tabla
creado por `AddObject` y aplicado a la tabla, que puede hacer fallar los pasos
siguientes o la regeneración final; la propiedad `Color` (obsoleta en favor de
`TrueColor`) en la capa, la tabla y las notas; la capa nueva; el margen vertical.

**Lo que se hizo (método firmado: el mensaje dice la causa).** Cada paso que
puede tumbar la tabla se nombra antes de darlo y, si falla, el comando dice «No
he podido dibujar la tabla al <paso>: <mensaje de AutoCAD>» y lo registra. Lo que
puede fallar sin impedir la tabla —estilo, capa, color, margen vertical, fusión,
casillas— va por `am:intentar` y se enseña como aviso con su motivo. Si llegó a
dibujarse algo, se deshace con el mismo `UNDO` que la marca de borrador; si no,
no se toca nada (un `UNDO` con el grupo vacío desharía lo último del arquitecto).

**Guardianes** (`tests/test_lsp_fallos_con_causa.py`), vistos ponerse rojos
cuatro de cuatro: handler que tira el mensaje, llamada que se traga su fallo,
`am:intentar` sin motivo, y `UNDO` sin comprobar. **Lo que no guardan:** que el
nombre de cada paso sea el correcto; sólo que haya uno antes de cada llamada.

**Suite entera: 1.868 pasan, 39 se saltan, 1 xfail (`D-7`), 0 fallos, 17 min 29 s.**

**Pendiente de Pablo en AutoCAD** con la 3.4.1: casillas 19 a 21 del checklist.
La línea «No he podido dibujar la tabla al <paso>: <mensaje>» —o la lista de
avisos si dibuja— es la medida que convierte los candidatos de arriba en causa.

---

## 2026-09-13 (noche) · `C-13`: dos viviendas iguales no se funden, y el `.lsp` 3.2.1

La primera prueba del `.lsp` 3.2.0 en AutoCAD sobre `v1plantas.dxf` dejó cuatro
problemas. Pablo fijó el orden y firmó un criterio.

### 1. La fusión de viviendas (`C-13`, firmado)

**El fallo, medido.** `evaluator.group_rooms_by_unit_label` agrupaba las
habitaciones por el TEXTO del rótulo más cercano. Dos viviendas `VT1/3` —tipo 1,
tres unidades: lo normal en un bloque— salían como una: filas repetidas y **TOTAL
SUP. INTERIOR 87,40 m²**, la suma de las dos, con la medición limpia y sin nota.
Reproducido con el fixture sintético duplicado. En los planos reales,
`plantasimple.dxf` rotula `VT22/1` dos veces, a 1.385 m una de otra.

**El criterio** (Pablo): «Si dos viviendas no se pueden distinguir, no se
fusionan: se declara y se deja sin escribir.» Registrado como `C-13`.

**Lo que se hizo.** El agrupador reparte por rótulo, no por texto, con el orden
de siempre. La medición declara `C-13` como impedimento de cada vivienda con
rótulo repetido: sin totales de vivienda ni de planta, las piezas una a una. El
cuadro se niega en las tres vías (comando: una entrada sin tabla con motivo; web
y agente: error con el mismo motivo) y `plano.superficie_util` no publica cifra.

**Antes de tocar nada se fotografiaron 41 casos** (los planos del arquitecto,
todos los fixtures, `plantasimple` con y sin alinear): **después, los 41 salen
idénticos.** Ningún plano del banco tiene dos viviendas con recintos bajo el
mismo rótulo; el `VT22/1` de `plantasimple` que sobraba no tenía ninguno.

**Guardián**, en `tests/test_c13_viviendas_indistinguibles.py`: estructural
—ninguna vivienda contiene recintos de dos rótulos— más un centinela por valor
sobre toda la respuesta y un control con rótulos distintos que sí se miden.
**Visto ponerse rojo** reintroduciendo, por separado, la fusión por texto, la
medición sin `C-13` y el comando sin negativa (ficheros restaurados byte a byte).

### 2. «2 viviendas VT1/3» en el `.lsp` (3.2.1)

**El fallo, medido.** No había dos: la respuesta LISP llevaba la tabla en
`repartos` y otra vez en `reparto`, una copia que nadie leía, y `am:viviendas-de`
cuenta `("cuadro_a_dibujar"` en todo el texto. Se quita la copia del servidor y
el `.lsp` busca sólo dentro de `repartos` (protege también de un servidor
anterior). Además, sin tabla por `C-13` el comando decía «esto es un fallo suyo»:
ahora enseña el motivo, y cuando hay otras viviendas, dice cuáles no ofrece.
`tests/test_lsp_lectura_de_repartos.py` reproduce la lectura del `.lsp` sobre la
respuesta real.

### 3. Estilo de tabla, capa y color propios (`.lsp` 3.3.0)

**Diagnóstico medido.** Las notas salían encima de la tabla, las filas
desiguales y la tabla amarilla. El servidor colocaba bien las notas (borde de la
tabla en y = −293,58, primera nota en −293,72); lo que fallaba era el dibujo: la
tabla se creaba con el estilo activo del plano (`Standard` de `v1plantas.dxf`:
margen vertical 1,5, texto 4,5 y 6,0, medidos en su DXF), el `.lsp` no fijaba el
margen vertical ni la altura de las celdas vacías, y `$CECOLOR = 2` (amarillo).

**Proporciones medidas, no inventadas**, en los cuadros del arquitecto
(`ejemplo`, `v1plantas`, `v2s`, `v3s`, la misma plantilla): fila 0,18 para texto
0,09 (2,0), título 0,12 en fila de 0,22, cuatro columnas iguales de 1,27.

**Lo que se hizo.** El servidor decide todo: filas de 2,0 alturas, título a 1,33
en fila de 2,44, columnas iguales, margen vertical 0,25 (texto + dos márgenes
cabe en cada fila, así que AutoCAD no tiene por qué agrandarlas), capa «ARCHMUSE
- CUADRO» en color 7 y estilo de tabla «ARCHMUSE». El `.lsp` 3.3.0 crea ese
estilo, pone tabla y notas en su capa y PorCapa, fija el margen vertical, el alto
del título y la altura de TODAS las celdas. La web dibuja igual.

**Guardianes vistos ponerse rojos** (seis de seis): margen vertical de 1,5,
columnas desiguales, borde de la tabla con todas las filas iguales, `.lsp` sin
margen vertical, `.lsp` sin capa, web sin color. **El sexto no se puso rojo a la
primera**: comprobaba el color 7, y `ezdxf` crea las capas en 7 por defecto, así
que pasaba igual sin pasar el color. Ahora la prueba pide el 3.

**Sin verificar en AutoCAD, y dicho donde toca** (checklist, casillas 13 a 16):
que AutoCAD respete la altura de fila con esos márgenes, y la creación del estilo
de tabla por ActiveX (`AddObject` «AcDbTableStyle»). Si esto último falla, la
tabla lleva igualmente sus medidas puestas.

**Suite entera después del paso 3: 1.853 pasan, 39 se saltan, 1 xfail (`D-7`),
0 fallos, 17 min 06 s.**

### 4. El punto único (`.lsp` 3.4.0)

Pablo: «el arquitecto no debe adivinar cuánto mide la tabla ni recibir "marca una
ventana mayor"». Marca **un punto** —la esquina de arriba a la izquierda— y el
servidor devuelve la tabla a la altura mínima legible, del tamaño que necesite.
Sólo se niega si esa huella pisaría su cuadro, y entonces pide **otro punto**, no
otro tamaño. Enmienda la regla «la ventana manda» de `D-14`.

**Guardianes vistos ponerse rojos** (cuatro de cuatro): tabla colgada a media
altura legible, sin la negativa por pisar el cuadro, `.lsp` pidiendo otra vez una
segunda esquina, y servidor que ignora el punto. El test que exigía la ventana no
se borró: se invirtió, con lo que decía antes escrito en su docstring.

**Suite entera después del paso 4: 1.861 pasan, 39 se saltan, 1 xfail (`D-7`),
0 fallos, 17 min 12 s.**

**Pendiente de Pablo en AutoCAD** con el `.lsp` 3.4.0: casillas 11 a 18 del
checklist (una sola opción por vivienda, `C-13`, notas debajo, filas iguales,
capa y color, estilo de tabla, punto único y negativa por pisar su cuadro).
- **Anotado en los criterios, junto a `C-7`:** «los tests comprueban lo que
  calcula el servidor, no lo que dibuja AutoCAD». Costó los dos bugs de arriba.

**Suite entera después de los pasos 1 y 2: 1.848 pasan, 39 se saltan, 1 xfail
(`D-7`), 0 fallos, 17 min 41 s.**

---

## 2026-09-13 · El cuadro de ArchMuse es una plantilla fija (D-13, D-14, D-15)

PRD `docs/prd/2026-09-13-cuadro-plantilla-fija.md`, escrito y ejecutado sin
esperar aprobación por orden de Pablo («esto deroga un criterio firmado»).

### Lo que falló en AutoCAD, y de dónde salía (medido)

- **`D-13` · `0,00 m²` en `pasillo` y `vestibulo`.** Salía de los tres
  constructores de `CERO_REAL` en `cuadro_superficies.py` y de
  `condicionar_ceros`, que sobre una medición limpia los dejaba pasar. En el
  fixture sintético, antes del arreglo: comando `(6,1)` y `(7,1)` a `0,00 m²`;
  web, dos `0,00 m²`.
- **`D-14` · palabras partidas en vertical.** Hipótesis de mecanismo, no medida
  en AutoCAD: medidas de tabla escritas a mano en el `.lsp` 3.1 y altura de
  texto sin fijar.
- **`D-15` · la web nunca aplicó `C-4`.** Escribía ceros también con la
  medición sucia.

### Lo que se hizo

- **Plantilla fija** (`analyzer/plantilla_cuadro.py`): 4 columnas, una fila por
  estancia medida, orden de familias fijo, filas de cierre. El cuadro del
  arquitecto ya no se clona: sólo se detecta para no dibujar encima.
- **Ningún cero**: `CERO_REAL` → `NO_DIBUJADA` (celda vacía con motivo) y
  `guardian_d13` a la salida, que no calla (motivo propio).
- **Maquetación en el servidor** (`analyzer/maquetacion_cuadro.py`): ventana
  de dos esquinas, anchos proporcionales medidos con la fuente, ninguna
  palabra partida, negativa si no cabe. Umbral de altura del cuadro del
  arquitecto o, sin él, de la mediana de los rótulos del plano.
- **Interior/exterior dudoso**: una pregunta por familia, que decide el
  servidor y el `.lsp` sólo transporta.
- **`S. CONSTRUIDA C.`** con la envolvente roja rotulada: `C-12`,
  **propuesto, sin firmar** — y desactivado esa misma tarde (abajo).
  `TOTAL S. UTIL` y `NUMERO UDS` vacíos con nota.
- **`.lsp` 3.2.0**, web (exportación y SPA) con la misma plantilla.
- Fixture sintético `tests/fixtures/cuadro_sintetico/` (sin datos de nadie).

### Guardianes, vistos ponerse rojos

Cada fallo se reintrodujo a propósito, se corrieron sus tests y se restauró el
fichero (sha256 igual antes y después). Los siete se pusieron rojos: productor
de ceros con y sin guardián, fila `pasillo` clonada a `0,00`, columnas estrechas,
medida de columna `(* 14.0 k)` y alto de fila literal en el `.lsp`, y un
`0,00 m²` en la web. `C-9` compara ahora también el contenido de la tabla por
las dos vías (`test_las_dos_vias_dibujan_la_misma_tabla`). El grupo de
deshacer sigue intacto.

**Suite entera: 1.813 pasan, 39 se saltan, 1 xfail (`D-7`), 1 falla, 17 min 01 s.**
La que fallaba era `test_zip_estricto`: el `zip()` de `plantilla_cuadro.construir`
que empareja recintos y piezas por posición. Arreglado con `strict=True` y un
comentario que dice dónde se decide esa correspondencia (`medicion.py`, mismo
agrupador). Tras el arreglo se relanzaron los cinco ficheros que lo tocan: 101
pasan y 1 xfail. **La suite entera no se ha vuelto a pasar después.**

Por el camino: el `python` global de esta máquina no tiene `ezdxf`, así que los
tests se corren con `venv\Scripts\python.exe`.

### La misma tarde: las cuatro decisiones de Pablo sobre lo anterior

Suite entera **antes de tocar nada**, como pidió: **1.814 pasan, 39 se saltan,
1 xfail (`D-7`), 0 fallos, 16 min 54 s.**

1. **Renumeración.** Los tres criterios nacieron como `D-8`, `D-9` y `D-10`, que
   ya existían en `decisiones-pendientes.md` con otro significado. Pasan a
   **`D-13`, `D-14` y `D-15`** (los primeros libres; nadie usaba del 13 en
   adelante). Con un script sobre una lista explícita de 28 ficheros: números,
   identificadores (`guardian_d13`, `MOTIVO_GUARDIAN_D13`, `test_d13_…`) y los
   dos ficheros de test renombrados. Comprobado al final: **cero** `D-8/9/10`
   fuera de los tres sitios con el significado antiguo (`agente/carencias.py`,
   `AGENTE_BACKLOG.md`, `decisiones-pendientes.md`).
2. **`C-12` desactivado** hasta que lo confirme un arquitecto. El código queda en
   `medir_construida` detrás de `C12_FIRMADO = False`; la fila sale vacía con
   nota. Sus tests lo activan dentro del test, y uno nuevo exige que esté apagado.
3. **El agente, a la plantilla** («si el agente calcula distinto que el comando y
   la web, `C-9` vuelve a romperse por un tercer sitio»):
   `plano.cuadro_de_superficies` y `superficies.cuadro_de_vivienda` pasan a
   **2.0.0**; el PDF del cuadro presenta la plantilla; `obtener_estado_cuadro`
   se retira. Un DXF sin cuadro del arquitecto deja de ser un error, y eso
   permite algo que antes no se podía: **el trabajo completo de la Skill —DXF,
   PDF, suma cruzada— se prueba en CI con el piso sintético**, sin `v2s.dxf`.
   G11 y el contrato de capacidades se recapturaron con el motivo escrito en el
   caso; en G11 cambia sólo `plano.cuadro_de_superficies`.
4. **Tests contra `v2s.dxf` que describían la 1.x**: marcados caducados con
   motivo, no reescritos a ciegas (dos en `test_agente_plano.py`, uno en
   `test_agente_skill_superficies.py`), igual que el script del endpoint.

**Dos hallazgos por el camino, medidos:**

- **Las notas escribían «0,00 m²».** «…un total de 0,00 m² no es una superficie
  (D-13)» iba al plano, a la web y al PDF debajo de la tabla: el mismo cero que
  `D-13` prohíbe, fuera de la celda. Se vio porque el PDF de punta a punta del
  piso sintético (sin exteriores) lo contenía. Reescritas las cuatro notas y
  añadido `test_d13_tampoco_una_nota_escribe_una_superficie_cero`.
- **El contrato congelado de `plano.medicion_de_la_planta` estaba atrasado**: el
  registro va por 1.1.0 con el parámetro opcional `alinear_rotulos`, y el
  congelado seguía en 1.0.0. Era compatible (opcional nuevo = menor, y la menor
  se subió), así que `CAD-2` no lo denunciaba; se ha recongelado junto al cuadro.

**Guardianes nuevos vistos ponerse rojos**, con el mismo método que por la
mañana (anclas únicas, restauración en `finally`, sha256 igual antes y después):
`C12_FIRMADO = True` pone rojo
`test_c12_esta_desactivado_hasta_que_lo_confirme_un_arquitecto`, y una nota que
vuelve a decir «0,00 m²» pone rojo
`test_d13_tampoco_una_nota_escribe_una_superficie_cero`. **Este segundo no se
puso rojo a la primera**: el fixture tiene terraza, así que la nota del lado
vacío no salía nunca y el test pasaba sin mirarla. Se le añadió el caso sin
exteriores —que además comprueba que esa nota sale— y entonces sí.

**Suite entera después de todo: 1.822 pasan, 39 se saltan, 1 xfail (`D-7`),
0 fallos, 16 min 50 s.**

### Lo que NO se ha hecho, y es deliberado

- **Nada del `.lsp` 3.2.0 se ha ejecutado en AutoCAD.** Checklist, paso 8 quater.
- **`C-12` sigue sin firmar**, y así seguirá hasta que lo confirme un arquitecto.
- **Los tests contra `v2s.dxf` del contrato antiguo** (endpoint, agente, Skill):
  caducados con motivo; se reescriben cuando ese plano se pueda ejecutar.

---

## 2026-09-13 · Arranque de un clic, la suite vista terminar, y la beta empaquetada

### 1. El servidor de desarrollo, sin terminal

`herramientas/servidor_dev.pyw` + tres accesos directos en el escritorio
(**ArchMuse**, **ArchMuse · reiniciar**, **ArchMuse · parar**), con `pythonw`:
ninguna ventana. Un segundo clic no levanta otro (cerrojo: puerto de control
`127.0.0.1:5099` en exclusiva). **Al guardar un `.py` se reinicia solo, pero
sólo si compila**: con un error de sintaxis avisa y deja vivo el servidor que
funcionaba. Avisos por notificación de Windows; logs en
`%LOCALAPPDATA%\ArchMuse-dev\`. Probado: segundo clic, recarga, error de
sintaxis, reiniciar, parar. **No es el lanzador de la beta.**

### 2. La suite del 12-sep, terminada

**1.710 pasan, 39 se saltan, 1 xfail (`D-7`), en 20 min 04 s.** Ningún test
nombraba ya `am:rellenar-cuadro`: el temor del cierre de ayer no se confirmó.

### 3. La beta: T3, T4, T5, T9, T10 y T11 (borrador)

Todo en `docs/prd/2026-09-11-beta-instalable-en-el-ordenador-del-arquitecto.md`,
apartado «Ejecución · 2026-09-13», con **cuatro desviaciones medidas** — la que
más importa: `schtasks /SC ONLOGON` sin elevar da **«Acceso denegado»**, así que
el arranque al iniciar sesión es un acceso directo en Inicio. Y el cotejo de
D-2 es de versión **exacta** del `.lsp` (servidor 0.3.x y comando 3.x no se
pueden comparar por la parte mayor).

| | |
|---|---:|
| Instalador | 37,1 MB |
| Actualización `.archmuse` | 0,9 MB |
| Runtime embebido | 154,0 MB |
| Prueba de humo con el runtime | medición 200, **0 módulos de fuera** |

`.lsp` **3.1.0**: puerto desde `servidor.json`, rama C (levanta el servidor y
espera 20 s a `/api/salud`), y **no escribe** si el servidor va con otro `.lsp`.
Tests nuevos: `tests/test_empaquetado.py` (18) y `tests/test_beta_lsp.py` (11).
`test_archmuse_lsp.py` suma `read-line` a sus primitivas verificadas.

**Suite entera después de todo lo anterior: 1.738 pasan, 39 se saltan, 1 xfail
(`D-7`), 21 min 25 s.**

**Un fallo propio por el camino, arreglado de raíz.** La salida de
`construir.py` vivía en `empaquetado/salida/`, dentro del árbol: la capa B es
una copia de `analyzer/`, `ia/`…, y `test_nadie_construye_el_cliente_por_su_cuenta`
—que recorre todos los `.py` del repositorio— encontró `ia/cliente.py` duplicado.
No se ha excluido en el test: **la salida se ha sacado del repositorio**, a
`Proyectos/archmuse/_empaquetado/` (junto a `_barrido/`), y el `.iss` la recibe
con `/DSalida`. Allí están `ArchMuse-Beta-0.3.1.exe` y, para ensayar actualizar y
volver en la máquina limpia, `prueba/ArchMuse-0.3.2.archmuse`
(`construir.py --paquete-de-prueba 0.3.2`).

### Lo que NO se ha hecho, y es deliberado

- **El instalador no se ha ejecutado en ningún sitio.** Aquí instalaría el
  bundle en el AutoCAD de trabajo; la VM (T12) no está montada.
- **La rama C y el cotejo no se han ejecutado en AutoCAD.**
- El folio tiene dos límites `[CONFIRMAR]`: el §4.5 del PRD quedó viejo el 12-sep.
- `D-7`, sin tocar: lo mide Pablo en AutoCAD.

---

## 2026-09-12 (cierre) · El cuadro propio: ArchMuse deja de depender del hueco que le dejen

PRD `docs/prd/2026-09-12-el-cuadro-propio-de-archmuse.md` (aprobado y ejecutado,
T1-T8). Criterio nuevo: **`C-11`**.

> **Estado de la suite al cerrar, sin redondear.** El último pase completo en
> verde es de **antes** del `.lsp`: **1.706 pasan, 39 se saltan, 1 xfail** —con
> T1-T6 y los 15 tests del cuadro propio dentro, sin los de `C-11` ni el `.lsp`—.
> Después de eso se verificaron **por separado**: `tests/test_cuadro_propio.py`
> (17, en verde, incluidos los tres de `C-11`) y
> `tests/test_archmuse_lsp.py` + `test_registro_y_informe_lsp.py` (44, en verde).
>
> **El pase completo posterior al `.lsp` se quedó a medias al cerrar la sesión**
> —iba por el 50% y todo verde hasta ahí— y **no se ha visto terminar**.
> Correrlo entero es el primer paso de mañana, y está abajo.

### El cambio de diseño, y de dónde viene

**Del arquitecto, no de nosotros.** ArchMuse tiene que entregar **siempre** su
cuadro de superficies con sus mediciones: si no hay cuadro lo dibuja, si lo hay
—vacío o lleno— dibuja el suyo **al lado**. El del arquitecto no se toca nunca.

Eso resuelve de raíz los 73 ceros de la mañana: ya no depende de rellenar huecos.

### El núcleo no era dibujar una tabla

Dibujarla es la parte visible. El cambio de verdad estaba en una línea del
cálculo: **«nunca sobrescribir» estaba implementado como «no calcular».**
`_resolver_o_preexistente` veía una celda con texto y ni siquiera llamaba al
cálculo. Con destino propio eso deja a ArchMuse mudo sobre un plano que ha
medido entero.

| `plantasimple.dxf`, 396 celdas de 22 cuadros | Antes | Ahora |
|---|---:|---:|
| Celdas que ArchMuse afirma | 74 | **232** |
| De ellas `0,00 m²` | 73 | 74 |
| **Cifras reales** | **1** | **158** |

La implementación es `CuadroSuperficies.como_plantilla()`: mismas filas, mismo
orden, valores vacíos. **«Nunca sobrescribir» no se debilita, se cumple mejor**:
pasa de ser una regla del cálculo —frágil, depende de acertar qué celda está
llena— a una propiedad de la arquitectura.

### `C-11`, firmado hoy: ninguna cifra que no haya medido él

**Y el fallo que lo motiva lo cometí construyendo esto.**
`_construir_cuadro` mete en su lista de etiquetas **todos** los MTEXT de la
rejilla, y una celda de valor —`21.90m²`— es un MTEXT como cualquier otro: se
copiaban dentro de la tabla de ArchMuse como si fueran filas suyas. No es que
faltara un dato: **ArchMuse habría firmado números que no ha medido**, y como
vienen de él, habrían cuadrado con su documentación y no habría chirriado nada.

**Se vio por el formato —él escribe `21.90m²`, ArchMuse `21,90 m²`— y eso fue
suerte, no diseño.** Si él usara coma, habría pasado por bueno. Por eso el
guardián **no compara textos**: exige que todo texto del cuadro dibujado sea una
etiqueta, un valor calculado, una marca de nota o el título —vocabulario
cerrado—, y hay un test que **reintroduce el fallo con formato de ArchMuse** y
comprueba que salta.

El filtro es por posición —la celda de valor de un campo reconocido— y no por
aspecto, para que un encabezado que viva en columna de valor («SUPERFICIES
UTILES») no desaparezca. Y va en **las dos vías**: leyendo el DXF y en
`cuadro_desde_celdas`, que es la que usa el comando de verdad. Ponerlo sólo en
una habría sido una divergencia `C-9` de libro.

### Lo que se ha construido

| | |
|---|---|
| `detectar_cuadros_superficies` | los N del plano (25 en `plantasimple`, 6 en `ejemplo`); el singular queda como envoltura |
| `FilaDeCuadro` | sus filas literales, con columna de etiqueta y de valor |
| `como_plantilla()` | el núcleo |
| `plantilla_canonica()` | los 18 campos, para el plano sin cuadro |
| `reparto_cuadro.cuadro_dibujable()` | la tabla lista para dibujar, con notas al pie numeradas y deduplicadas |
| Endpoint | `cuadros` en plural, `cuadro_a_dibujar` en la respuesta, y **ya no devuelve `ok: False` cuando no reconoce cuadro** |
| `.lsp` **3.0.0** | `am:buscar-cuadros`, `am:dibujar-cuadro`, `am:punto-a-la-derecha`; **fuera `am:rellenar-cuadro`** |

**`V5.dxf` pasa de rendirse a entregar su cuadro completo**, con el salón de
21,90 m². Era el plano que mejor mide del lote y el único que no tenía dónde
poner nada.

### Dos guardianes que se dieron la vuelta, y no se borraron

- `test_no_se_inserta_ninguna_tabla_nueva` **prohibía** `vla-AddTable`, porque el
  10-sep se decidió que una tabla al lado no le ahorraba trabajo. Hoy el
  arquitecto ha dicho lo contrario. El test no se borra: **se invierte y se deja
  escrito lo que decía antes**, y ahora comprueba algo más fuerte —que todos los
  `vla-SetText` viven dentro de `am:dibujar-cuadro`, que escribe en una tabla
  que ha creado él mismo—. Un guardián que desaparece se lleva con él el motivo
  por el que existía.
- `am:rellenar-cuadro`, `am:buscar-cuadro` y `am:reparto-celdas` **se han
  quitado**, no dejado sin usar. Una función que sabe escribir en su tabla es
  una pistola cargada encima de la mesa.

### PRIORIDAD 0 apuntada: ningún fixture del repositorio tiene cuadro

Medido: de **todos** los DXF versionados, **cero** `ACAD_TABLE`. Toda la
capacidad del cuadro se prueba sólo en el ordenador de Pablo; en CI se salta.
Mitigado en lo que se podía —los tests nuevos construyen el cuadro con
`cuadro_desde_celdas`, que es la vía del comando— pero **la lectura del DXF
sigue sin probarse en CI, y es donde estuvo el fallo de `C-11`**. Anotado en el
PRD del 10-sep como PRIORIDAD 0, con la dificultad dicha por delante. Pendiente
de hablarlo.

### Lo que NO se ha hecho, y es deliberado

- **`D-7` sigue sin tocar**, esperando a que Pablo mire el orden de `ssget`.
- **No se compara**: ArchMuse pone su cifra al lado de la suya y calla. Comparar
  es del arquitecto (orden de Pablo). El PRD del 22-ago sigue en su gate.
- **El `.lsp` no se ha ejecutado nunca.** Riesgo asumido por Pablo. El checklist
  del trial es el paso 8 ter de `docs/design/checklist-primera-prueba-autocad.md`.

### El primer paso de mañana, en este orden

1. **Correr la suite entera y verla terminar.** Es lo único de hoy que queda sin
   comprobar de punta a punta. Tarda unos 11-15 minutos. Si sale roja, lo más
   probable es que sea un test que nombraba `am:rellenar-cuadro` o
   `am:reparto-celdas` y que no se haya encontrado al reajustar los guardianes
   —se localizaron tres, pero la búsqueda fue por fallo, no exhaustiva—.
2. **Pablo prueba el `.lsp` 3.0.0 en AutoCAD**, con el paso 8 ter delante y en
   el orden que dice: `v1plantas` (un cuadro), `plantasimple` (25) y `V5` (sin
   cuadro). Nada de esto se ha ejecutado nunca. Y de paso, la pregunta de `D-7`:
   si los nombres de estancia salen como nombres o como cifras.
3. **Con lo que salga de (2), decidir**: si `ssget` devuelve un orden estable,
   `D-7` se cierra borrando el `xfail` y no hace falta criterio ninguno.
4. **Hablar del fixture sintético con cuadro** (PRIORIDAD 0 del PRD del 10-sep).
   Pablo lo dejó fijado para después del `.lsp`.
5. Y **después** el instalador, que es el objetivo, y del que Pablo quiere plazo
   **medido** y no a ojo.

**Lo que NO hay que empezar mañana:** nada nuevo del cuadro. El PRD del 12-sep
está ejecutado entero y lo que falta es mirarlo funcionar en AutoCAD, no
añadirle capacidades.

---

## 2026-09-12 · La divergencia `C-9` del MTEXT cerrada, y `CU-2` contra los 25 cuadros

Suite en verde: **1.691 pasan, 39 se saltan, 1 xfail** (el xfail es nuevo y está
explicado abajo: es un defecto declarado, no un test roto).

### El arreglo: el payload declara el tipo, el materializador lo respeta

La vía de la web y la del comando leían distinto el mismo plano porque
`geometria_recibida.escribir_dxf` escribía **todos** los textos como MTEXT.
`extract_labels` ordena los MTEXT antes que los TEXT para desempatar dos rótulos
dentro de un mismo recinto, así que aplanar los dos tipos no simplificaba nada:
**le quitaba a ese criterio el dato con el que decide**.

| `plantasimple.dxf` | Web | Comando (antes) | Comando (ahora) |
|---|---:|---:|---:|
| Recintos | 157 | 169 | **157** |
| Con nombre | 156 | 168 | **156** |
| Viviendas con superficie | 16 | 3 | **16** |

Idénticas pieza a pieza y cifra a cifra. **Sin criterio nuevo:** el payload lleva
ahora `"tipo": "MTEXT"` / `"TEXT"` —que el `.lsp` ya leía en su `assoc 0` y
sencillamente no mandaba—, `validar` lo normaliza y `escribir_dxf` escribe
`add_text` o `add_mtext` según lo que diga. La prioridad sigue viviendo en
`extract_labels`, que es donde estaba probada.

El `.lsp` sube a **2.4.0** porque el payload cambia. Un comando 2.3.0 contra un
servidor nuevo **sigue midiendo** —sin `tipo` se escribe MTEXT, que es lo de
antes— pero mide lo de antes, y `D-2` no lo caza porque la parte mayor no cambia.
Queda escrito en un test
(`test_un_payload_antiguo_sin_tipo_sigue_midiendo_y_se_comporta_como_antes`) con
lo que se pierde medido, no como nota.

### Lo que el arreglo NO era, y costó verlo: el banco no miraba

Los seis planos del banco de `C-9` son **todo-MTEXT o todo-TEXT** (26, 11 / 4, 8,
8, 7). Ninguno podía ejercitar la prioridad. Y `plantasimple.dxf`, que sí la
ejercita, **se saltaba en silencio**: el banco era una lista de rutas y el filtro
de saltos descartaba lo que no resolvía su capa solo. Un invariante que elige
contra qué se comprueba no vigila nada.

Dos arreglos, los dos en el banco y no en el motor:

- **`Plano(ruta, capa, alinear)`** en vez de una ruta suelta. Un plano que
  necesita que le digan la capa es un plano normal: lo que se le dice, se dice en
  el banco e idéntico por las dos vías. Sólo se salta lo que no está en la
  máquina.
- **`15_mtext_y_text_en_el_mismo_recinto.dxf`**, caso 15 del banco de tortura:
  cuatro estancias con el nombre en MTEXT y la cifra en TEXT, y **el TEXT escrito
  primero** para que sin la prioridad gane la cifra. Es la forma de
  `plantasimple` (651 MTEXT y 136 TEXT en la misma capa) sin datos de nadie, y
  corre siempre en CI.

### Dos decimales, y el micrómetro que quedaba

La huella se compara ahora a **dos decimales, los que se publican**. El payload
lleva las coordenadas a seis porque es lo que `am:json-num` sabe mandar
(`(rtos x 2 6)`); en un recinto de `plantasimple` con el perímetro a 300 m del
origen eso acumula **0,0001 m²**: el «Tendedero» sale 4,1236 por una vía y 4,1237
por la otra. **1 cm² en 1 de 157 piezas**, y es el único resto de todo el banco.
Subir la precisión del simulador lo haría más fino que lo simulado —el error que
ya se cometió con el flag de cerrada— y comparar a cuatro es comparar el ruido
del transporte.

### Lo que el banco ampliado destapa y NO se ha arreglado (`D-7`, sin firmar)

Con `plantasimple` dentro, el test del **orden de los textos** falla, y no por el
tipo. Ese plano rotula cada salón con **varios MTEXT de la misma capa**: el
nombre repetido dos o tres veces y la cifra de su superficie, todos MTEXT en
`00 TEXTO`. Medido: **156 recintos tienen más de un texto dentro y 63 tienen tres
MTEXT compitiendo**. Ni la prioridad MTEXT-sobre-TEXT (mismo tipo) ni la regla de
la capa que nombra (misma capa) desempatan eso —lo desempata **el orden del
recorrido**, y `ssget` no garantiza ninguno—. Al invertirlo, las estancias pasan
de llamarse «Salón/cocina» a llamarse «21.90m²».

Hoy no se nota porque `payload_desde_dxf` recorre en el mismo orden que la web.
**En el AutoCAD del arquitecto puede notarse**, y es el riesgo abierto del trial
sobre este plano.

Está como **`xfail(strict=True)`** con su motivo escrito, no tapado: cuál de dos
textos de la misma capa y el mismo tipo nombra una estancia es criterio
profesional y **es de Pablo**. El día que se firme, el xfail se pone rojo y hay
que venir a borrarlo.

### `CU-2` contra los 25 cuadros, ejecutado

Primera vez que el emparejamiento cuadro↔vivienda se corre contra un proyecto
completo. Por la vía determinista (el DXF leído con `ezdxf`, sin AutoCAD):

| | |
|---|---:|
| `ACAD_TABLE` con el título del cuadro | **25 de 25** |
| Cuadros construidos (17 campos cada uno) | **25 de 25** |
| Emparejados con su vivienda | **22 de 25** |
| Repartos con `se_puede_escribir` | **16 de 22** |
| Filas del cuadro no entendidas | **0** |
| Fallos de conservación de la medida | **0** |
| Piezas medidas sin fila | **1** |

**El `n_cols = 0` no bloquea la vía Python.** La pregunta que el plan dejaba
abierta —si `vla-get-Columns` devuelve 0 en estas tablas— sigue **sin contestar**
para la vía COM y hay que mirarla en AutoCAD; pero `_construir_cuadro` no usa
`n_cols`: reconstruye la rejilla desde las `LINE` del propio `ACAD_TABLE`, y los
25 salen con sus 17 campos.

**Los 3 que no emparejan, y por qué está bien que no emparejen.** Sus cuadros
declaran `VT11 /2 PMR`, `VT13 /3  FN` y `VT16 /3  FN`; el plano rotula `VT11/2`,
`VT13/3` y `VT16/3`. `elegir_vivienda` compara sin espacios y exige igualdad, así
que el sufijo rompe la correspondencia y **se niega en vez de adivinar**, que es
lo que está firmado. Decidir que `PMR` y `FN` son calificativos que no cambian la
tipología **es criterio, y no se ha tomado**. Son 3 de 25 —el 12%— y en un plano
real: la pregunta va a volver.

**El resultado incómodo, y es el que importa.** De las 74 celdas que ArchMuse
escribiría en los 22 cuadros, **73 son `0,00 m²`**. La única cifra real es un
aseo de 3,81 m² en VT17/1. El motivo no es un fallo: **el arquitecto ya tiene su
cuadro relleno**, y `CU-3` respeta cada celda escrita sin recalcularla. Lo que
ArchMuse añade son los ceros de `pasillo` y `vestibulo` en las viviendas que no
tienen ninguno de los dos —`C-4` los deja pasar porque esas 16 mediciones están
limpias, y sobre una medición limpia un cero es un hecho negativo verificado—.

Sobre un proyecto ya terminado, **rellenar el cuadro no tiene casi nada que
rellenar**. Lo que este plano pide no es autocompletar: es **contrastar** —decir
si lo que él escribió cuadra con lo que está dibujado—, que es justo el PRD del
2026-08-22 y no está ejecutado. No se ha tocado nada: se deja medido.

### Un límite real, no un detalle: ArchMuse ve **un** cuadro por plano

`detectar_cuadro_superficies` recorre los `ACAD_TABLE` del modelspace y
**devuelve el primero** que lleve el título. Este plano tiene **25**, uno por
vivienda, y es el único proyecto completo del lote: el caso de varios cuadros no
es una rareza que ya llegará, **es la forma normal de un proyecto de verdad**.

Por la vía del comando el límite no se ve, porque el cliente CAD manda las
celdas del cuadro que él ha elegido y el servidor reparte ese. Por la vía web
**no es una pérdida muda** —`coherencia.revisar` mete el contraste en
`no_comprobado` en cuanto hay más de una vivienda, así que `C-6` se cumple—,
pero **el motivo que da es el equivocado**: dice «un cuadro describe una sola
vivienda» cuando lo cierto es que **hay 25 cuadros y se ha leído 1**. El
arquitecto se lleva la impresión de que el problema es su plano.

El barrido de los 25 de hoy se hizo con un **arnés**, no con el producto, y no se
ha convertido en test a propósito: un test que recorriera las tablas por su
cuenta sería una segunda implementación del criterio fuera del módulo, que es lo
que prohibe `D-7`. **Si `CU-2` va a ser una capacidad de verdad, el barrido tiene
que vivir en `cuadro_superficies.py` y el test detrás.** Anotado, no hecho.

### Lo decidido por Pablo hoy, sobre lo medido

1. **`D-7` (el desempate entre dos MTEXT iguales): no se resuelve todavía.**
   Queda como `xfail(strict=True)` y en el checklist del trial, tal cual.
   **Primero hay que saber qué orden devuelve `ssget` de verdad en AutoCAD**:
   si resulta estable, no hace falta criterio ninguno, y escribir uno antes de
   mirarlo sería inventarse un problema. La medición va antes que la regla.
2. **`PMR` y `FN`: no lo decide ArchMuse y tampoco Pablo.** Es vocabulario del
   estudio —`PMR` probablemente «persona con movilidad reducida»— y va a la
   **lista de preguntas para el arquitecto**, que pasa a ser de **seis**.
   Mientras tanto, `elegir_vivienda` **sigue negándose**, que es lo firmado.
3. **Los 73 ceros son el hallazgo del día y cambian la conversación de
   producto** —ver abajo—. **No se abre el PRD del 2026-08-22 todavía.**

### ⚠ La pregunta abierta más importante que hay ahora mismo

**Sobre un proyecto terminado, rellenar el cuadro no tiene casi nada que
rellenar. Lo que pide es contrastar.**

Está medido, no intuido. Las **396 celdas** de los 22 cuadros emparejados se
reparten así:

| | Celdas | |
|---|---:|---|
| Ya rellenas por el arquitecto | **175** | `CU-3` las respeta sin recalcular |
| `VIVIENDA TIPO` ya declarada, y coincide | **22** | también suyas |
| Total bloqueado por criterio (`C-1`, `C-6`) | 66 | no se suman: lo decide el técnico |
| Construida exterior: falta el dato | 22 | no se conoce el espesor de muro |
| Cero retenido por `C-4` (medición sucia) | 23 | no es un hecho verificado |
| Familia ambigua (terrazas a medias) | 14 | no se adivina qué pieza es cuál |
| **Escritas por ArchMuse** | **74** | **73 de ellas `0,00 m²`** |

**197 de 396 —la mitad del cuadro— ya las había escrito él.** La capacidad que se
ha construido —autocompletar— supone un cuadro vacío, y el único proyecto
completo del lote **no tiene ni uno vacío**. Del resto, lo que ArchMuse no
escribe no lo calla: cada celda lleva su motivo, y los motivos son buenos. Lo
que aporta de nuevo, en cifras, es **un aseo de 3,81 m²**.

No se trabaja todavía: queda **señalado** como la pregunta que hay que contestar
antes de seguir añadiendo capacidad de relleno. El PRD que la aborda existe
(`docs/prd/2026-08-22-contraste-superficies-memoria-vs-plano.md`) y **no se
ejecuta hasta que Pablo lo diga**.

---

## 2026-09-11 (cierre 3) · La capa que nombra, y `plantasimple` publicando superficies

Suite en verde: **1.672 pasan, 39 se saltan**. PRDs:
`2026-09-11-que-capa-nombra-las-estancias.md` (nuevo, aprobado) y
`2026-09-11-alinear-rotulos-desplazados.md` (A3 y A4 ya hechas).

### `plantasimple.dxf`, de principio a fin

| | Antes de hoy | Ahora, sin alinear | Ahora, alineando |
|---|---|---|---|
| Piezas medidas | 0 (`GEOSException`) | 206 | 157 |
| Recintos con nombre | 0 | 0 | **156** |
| Viviendas con total | 0 | 0 | **16 de 25** |

Cifras reales por vivienda: 50,97 m² útil interior + 7,47 exterior; 59,11 + 7,45;
50,91 + 7,56…

### La regla de la capa que nombra (opción 1, firmada)

`UMBRAL_CAPA_DE_ROTULOS = 0,5` — la primera tiene que nombrar **más del doble**
que la segunda. Los datos que lo sostienen: cinco de los seis planos tienen **una
sola** capa que nombra (ratio 0,000) y el umbral no los toca; el único con
varias está en 0,414. El caso que Pablo puso como no holgado, 111 contra 95,
daría 0,856. **No hay ni un plano medido entre 0,4 y 0,6**, así que 0,5 es una
convención declarada y no un óptimo medido — anotado también en el código.

Ambiguo = no se elige y **no se estrecha nada**: se deja lo de antes y se emite
`coherencia.ROTULOS_DE_VARIAS_CAPAS` con el reparto en cifras. Elegir sería
adivinar; no nombrar nada rompería planos que hoy funcionan.

### La opción 3, medida y descartada con datos

El desempate por cercanía al centroide, simulado copiando `match_label_to_room`
entera y cambiando sólo esa línea: **cambia 0 rótulos de 0 en los cinco planos
de referencia** —`ejemplo.dxf` incluido, ni una cifra— y **115 de 160 en
`plantasimple`, para peor**: el rótulo más próximo al centro de una estancia no
es su nombre, es **el texto de su superficie** (`'F'` → `'21.90m²'`). Descartada
con la medición hecha, no por intuición.

### Deuda preexistente, anotada porque es más grande que el caso

`_capas_de_rotulo` admite como capa de rótulos **cualquiera que ponga un texto
dentro de un recinto**. Eso no fue un problema mientras los rótulos de
`plantasimple` estaban a 50 m. **Que haya salido ahora es suerte, no diseño** —
y el mismo patrón de regla («vale cualquiera que cumpla algo una vez») puede
estar en más sitios de `parser.py`.

### Divergencia `C-9` nueva, medida y sin arreglar

El mismo plano alineado da **16 viviendas con total por la vía web** y **3 por la
vía del comando**. Causa localizada: el DXF que se materializa desde el payload
escribe **todos los textos como MTEXT**, y la prioridad MTEXT-sobre-TEXT de
`extract_labels` cambia qué rótulo gana, lo que cambia qué contornos agrupadores
se reconocen — 169 recintos en vez de 157, con 12 contornos duplicando
superficie y bloqueando el total de 13 viviendas por `C-6`. Es preexistente y
sólo se ve ahora que este plano tiene rótulos. **Pendiente.**

### Dos fallos propios que conviene no repetir

- `_desplaza` quedó insertada **entre `@app.route` y su función**, así que Flask
  registró el ayudante como vista y el endpoint devolvía 500. Una función nueva
  encima de una ruta va antes del decorador, no debajo.
- El consejo del `DESPLAZA` salía como `-0,25,-50,00`: el resto del producto usa
  coma decimal y ahí no puede, porque la coma separa `dx` de `dy` en AutoCAD.
  Cuatro números en vez de dos.

---

## 2026-09-11 (cierre 2) · Alinear rótulos: A1/A2/A5 hechas, A3/A4 paradas con motivo

Suite en verde: **1.657 pasan, 39 se saltan**. PRD:
`docs/prd/2026-09-11-alinear-rotulos-desplazados.md` (aprobado, con las tres
condiciones duras de Pablo como parte de la firma).

**Hecho.** El detector distingue ahora **declarar** de **ofrecer**: `limpio` es
`True` sólo si la traslación explica ≥95% **y** ninguna otra traslación distinta
explica algo comparable (`competidoras == 0`). `leer_plano(alinear_rotulos=True)`
aplica la corrección **a los rótulos, en memoria**, volviendo a leer los mismos
polígonos con las etiquetas corridas; `extract_labels`/`extract_unit_labels`
aceptan el desplazamiento y las dos se mueven juntas —alinear los nombres y no
las etiquetas de vivienda dejaría cada pieza bien nombrada en la vivienda
equivocada—. `PlanoLeido.rotulos_alineados` declara lo aplicado.

**El test que da permiso a todo lo demás:** el hash SHA-256 del DXF es idéntico
antes y después de una medición alineada. Y las dos condiciones duras tienen su
test: sin pedirlo no se alinea ni con el desfase más limpio del mundo, y
pidiéndolo con un desfase no limpio tampoco.

**Un fixture que estaba mal y lo dijo el propio detector.** El primer test de
«desfase limpio» usaba una rejilla perfectamente periódica y salía
`limpio=False`. Tenía razón: si todos los recintos son iguales y equiespaciados,
correr los rótulos una columna entera los mete igual de bien en el recinto de al
lado — hay varias traslaciones válidas y ninguna es *la* respuesta. El caso
quedó como test propio en vez de taparse.

### A3 y A4 paradas: alinear destapa que cualquier capa puede nombrar

Con la alineación, `plantasimple` pasa de **0 recintos con nombre a 159 de 160**.
Pero 46 de esos nombres salen de `00-INST` y son **«F», «FR», «LD»** — códigos
de electrodoméstico. Las viviendas con total pasan de 0 a **2 de 25**, y el
impedimento de las otras 23 es *«3 pieza(s) no se sabe si son superficie interior
o exterior por su rótulo («F» 21,90 m²)»*: **21,90 m² es el salón**.

La causa no es la alineación: `parser._capas_de_rotulo` admite como capa de
rótulos **cualquiera que ponga un texto dentro de un recinto**, y mientras los
rótulos estuvieron a 50 m ningún texto caía dentro de nada. Debilidad
preexistente, destapada.

Arreglarla es elegir qué capa puede nombrar una estancia y cuál de dos textos
dentro del mismo recinto gana — criterio profesional (`D-7`), y hoy lo decide el
orden de un `for`, que es literalmente el ejemplo que pone el cierre de
`CLAUDE.md`. **Pendiente de Pablo.**

---

## 2026-09-11 (cierre) · `C-10` implementado: `plantasimple.dxf` ya se mide

Suite en verde: **1.641 pasan, 39 se saltan**. PRD cerrado
(`docs/prd/2026-09-11-reparar-geometria-invalida-c10.md`, R1-R5).

| | Antes | Después |
|---|---|---|
| `plantasimple` por la vía del comando | `GEOSException`, **0 piezas** | **206 piezas, 25 viviendas** |
| Su superficie total | 3.305,18 m² (con geometría rota dentro) | **3.305,18 m²** |
| Recintos inválidos | 10 | **0** |
| Los cinco planos de referencia | — | **+0,0000 m², pieza a pieza** |

**Un solo criterio para los dos caminos.** `_validar_o_reparar` es ahora el
único sitio donde se decide qué hacer con un polígono inválido, y lo llaman el
modo heredado y el de las capas `AM_*`. La tolerancia (`TOLERANCIA_REPARACION`,
0,005 m²) separa sola los dos casos: los 10 reales dan delta **0,000000** y se
reparan; la pajarita da **8,0000** y se descarta, igual que antes.

**Lo que se declara, y dónde.** `GeometriaReparada` en `PlanoLeido` ->
`Medicion.geometria_reparada` -> afirmación `medicion.geometria_reparada` del
acta -> `geometria_reparada` en la respuesta, más una frase ya redactada
(`geometria_reparada_aviso`) que el `.lsp` imprime antes de medir. El hallazgo
`coherencia.GEOMETRIA_REPARADA` lleva el `handle` y `superficie_cambiada:
False`. La frase la escribe el servidor, nunca el cliente.

**Dos cifras que no conviene confundir.** Por la vía del comando se reparan
**9** y no 10: el payload redondea los vértices a 4 decimales y ese redondeo
arregla por su cuenta una de las diez degeneraciones. Las dos vías miden lo
mismo; no reparan exactamente lo mismo, y el motivo está medido.

**Un test reescrito, no borrado.**
`test_capas_am.py::test_inventario_en_modo_heredado_no_excluye_geometria_invalida`
afirmaba el criterio anterior palabra por palabra. Ahora se llama
`..._aplica_el_mismo_criterio_que_las_capas_am` y su docstring cuenta qué decía
antes y por qué cambió — borrarlo habría dejado el cambio sin rastro.

**Los tres goldens que cambian, comprobados con un guardián.** Sólo claves
nuevas (`geometria_reparada: []`) y una entrada más en `comprobado`. Se escribió
un comparador que **rechaza cualquier cambio de valor** de algo que ya existía y
sólo admite crecimiento de listas; con él se actualizaron.

### Lo que `C-10` NO ha desbloqueado

`plantasimple` se mide, pero **ninguna de sus 25 viviendas publica total**: el
desplazamiento de 50,00 deja cada pieza a 47-53 m de dos etiquetas de vivienda
distintas y `C-5` se niega a repartir lo ambiguo. Los 25 hallazgos lo dicen uno
a uno («el reparto de 10 pieza(s) entre viviendas no es firme: «(sin rótulo)»
está a 47.39 m de VT1/3 y a 51.67 m de VT2/2»). **Eso es lo que bloquea CU-2.**

---

## 2026-09-11 (noche) · `C-9` medido, el paquete a la mitad, y el registro local

Suite en verde: **1.616 pasan, 39 se saltan** (eran 1.574 esta tarde).

### La divergencia `C-9` de los bloques: medida, y no es bloqueante

Pablo pidió medir antes de decidir prioridad. **Cero**, en los seis planos: ni un
recinto ni un rótulo de recinto vive dentro de una referencia de bloque, y no hay
un solo `ATTRIB` en todo el corpus. Lo que `ssget "_X"` no ve, en estos planos,
no existe.

| Plano | Recintos | En bloque | Rótulos sólo dentro de bloque |
|---|---:|---:|---:|
| `plantasimple` | 206 | 0 | 0 |
| `v1plantas` / `v2s` / `v3s` | 10 / 10 / 8 | 0 | 0 |
| `V5` / `ejemplo` | 22 / 51 | 0 | 0 |

**El límite de esta medición, dicho:** cubre los 6 DXF legibles. Los 70 DWG no
los lee `ezdxf`, así que de ellos no se sabe — y averiguarlo es, literalmente,
para lo que existe la beta. Lo barato mientras tanto no es arreglar la
divergencia, es **detectarla**: que el comando recorra la tabla de bloques por
ActiveX y diga «esta capa además tiene N polilíneas dentro de bloques, que no
puedo medir». Convierte una pérdida invisible en una declarada (`C-6`). Propuesto,
no hecho.

### `C-10` (reparar y declarar): PRD escrito, con las cifras medidas antes de tocar nada

`docs/prd/2026-09-11-reparar-geometria-invalida-c10.md`, Borrador. Se parcheó
`_closed_polygons_with_color` **en memoria** y se midió pieza a pieza:

- **Los cinco planos de referencia no cambian nada.** `ejemplo` 40 → 40 piezas y
  369,4734 → 369,4734 m². `v1plantas`/`v2s`/`v3s` 8 → 8 y 66,3286 → 66,3286.
  `V5` 22 → 22 y 191,3194 → 191,3194. **Delta +0,0000 m² en los cinco.**
- **`plantasimple` pasa de no medirse a medirse**: `coherencia.revisar` deja de
  reventar, 25 viviendas y 272 hallazgos en 10,6 s, con el área total idéntica
  (3.305,18 m²) y los recintos inválidos de 10 a 0.
- **La tolerancia separa los dos casos sola:** los 10 reales dan delta
  **0,000000**; la pajarita de los tests `AM_*` da **8,0000**, así que `C-10` la
  descarta igual que hoy. Por eso unificar el camino `AM_*` (cuarta condición de
  Pablo) es seguro y **no relaja nada**: hoy `AM_*` descarta toda geometría
  inválida porque no sabía distinguir; con la tolerancia, distingue.

### El paquete de la beta: de 303,7 a 172,4 MB

`analyzer/ifc_export.py` importaba `ifcopenshell` (**94,5 MB**, el paquete más
grande de todos) en su cabecera, `app.py` importaba ese módulo en la suya, y el
resultado era que **el servidor no arrancaba sin él** aunque nadie fuera a
exportar un IFC. Ahora se importa dentro de la función, con `TYPE_CHECKING` para
la anotación, y quien exporte sin el paquete recibe un motivo en castellano en
vez de un `ModuleNotFoundError`.

`anthropic` no hacía falta tocarlo: ya estaba en `try/except ImportError`.
Fuera del paquete: `ifcopenshell` 94,5 · `pdfminer` 9,3 · `anthropic` 6,2 ·
`trimesh` 4,0 · `pypdf` 3,7 · `mapbox_earcut` 0,1 MB. El arranque baja de 1,19 s
a 0,51 s.

`tests/test_paquete_ligero.py` (18 tests) **arranca el servidor en un proceso
aparte con cada paquete vetado en el `sys.meta_path`** y comprueba que mide
igual. No prueba que el paquete sea pequeño: prueba que nada obligatorio depende
de lo que se va a dejar fuera, que es lo que se rompe sin querer con un `import`
añadido por costumbre.

### T6 · El registro local y `ARCHMUSE-INFORME` (`.lsp` 2.3.0)

**El registro lo escribe el cliente y no el servidor**, y no por comodidad: un
registro que depende del servidor está mudo justo cuando el servidor es el
problema, que es el fallo nº 1 que va a tener esta beta.

- `%LOCALAPPDATA%\ArchMuse\registro\archmuse-AAAA-MM.log`, rotación mensual. **No**
  en `Documentos` ni en el `Escritorio`: los dos suelen ir a OneDrive, y un
  registro en la nube contradice la promesa.
- Por línea: fecha · versión del `.lsp` · versión del servidor · versión de
  AutoCAD · **`DWGNAME`, sin `DWGPREFIX`** · capa y quién la eligió · el suceso.
- Se registra: el envío, que el servidor no responde, 0 celdas rellenables, la
  cancelación, la marca de borrador que no se pudo poner, el resultado, y el
  `*error*` del comando.
- **Nunca:** vértices, rótulos, celdas ni rutas. Garantizado estructuralmente —
  `am:log` no se llama desde ninguna función que toque el payload, y hay un test
  por cada una de las siete.
- `ARCHMUSE-INFORME` enseña la lista exacta con tamaños, pide `Si`, y empaqueta
  con PowerShell (`Compress-Archive`, y `[Environment]::GetFolderPath('Desktop')`
  para acertar con OneDrive). Si el ZIP falla, **siempre dice la carpeta**.
- `ARCHMUSE-INFORME-PLANO` es **otro comando**, no una opción: mandar el proyecto
  de un cliente tiene que costar teclear otro nombre.
- `*am:version-corta*` ("2.3.0") separada de la larga, para el cotejo de D-2 y
  para que quepa en una línea de registro. Un test comprueba que la larga
  empieza por la corta.

`tests/test_registro_y_informe_lsp.py`, 24 tests sobre las promesas, no sobre la
sintaxis.

---

## 2026-09-11 (tarde) · `plantasimple.dxf`: la capa, los 50,00, y un tercer bloqueo que no sabíamos

Suite entera en verde: **1.574 pasan, 39 se saltan**.

### 1. La capa de recintos es `00 areas`, y ahora con tres pruebas independientes

| Prueba | Resultado |
|---|---|
| Superficie de cada polígono contra las cifras que el arquitecto escribió en su plano | **125 de 152** coinciden a ±0,01 m² |
| Tamaño de estancia bajo alguna unidad métrica | única capa que lo cumple (mediana 7,84 m², en metros) |
| Rótulos dentro tras desplazar | **152 de 152** |

### 2. Las «cuatro capas candidatas» son un fenómeno de la vía web, no del comando

`ssget "_X"` **no baja a las referencias de bloque**; `parser._recorrer_plano` sí.
Medido en los cinco planos: sobre `plantasimple.dxf` el servidor ve **9** capas
candidatas y el comando ve **2** (`00 areas` y `00 TEXTO`), y `00 areas` ya es la
que el comando propone. Así que por la vía AutoCAD la elección de capa **nunca fue
el bloqueo** de este plano.

**Divergencia `C-9` declarada y sin arreglar:** un plano que dibuje sus recintos
dentro de un bloque lo mide la vía web y no lo mide el comando. En los cinco
planos disponibles no ocurre — los recintos están siempre en el modelspace — pero
el hueco es real, no una hipótesis.

Aun así `am:elegir-capa` se ha rehecho (`.lsp` 2.2.0): lista numerada siempre,
se admite número o nombre sin distinguir mayúsculas, **se valida contra la lista**
y se vuelve a preguntar hasta tres veces. Antes se mandaba al `ssget` lo que él
tecleara, y una errata aparecía tres pasos después como «no hay ninguna polilínea
en la capa X», que parece un problema del plano.

### 3. El desfase de 50,00 es de ESTE plano, no del estudio

Medido en los seis DXF disponibles. `plantasimple.dxf`: **0 de 206** recintos con
rótulo dentro; los textos están **50,00 unidades de dibujo por debajo**, con
**dx = 0 exacto** (meseta limpia de dy 49,50 a 50,25; extrusión normal y elevación
0, así que son sus coordenadas reales). `v1plantas`, `v2s`, `v3s`, `V5` y
`ejemplo`: **100 % rotulados sin desplazar nada**.

**Por eso se detecta y se declara, y NO se corrige** (criterio de Pablo, y el
cierre de `CLAUDE.md` sobre las decisiones implícitas sin dueño):
`parser.detectar_desplazamiento_de_rotulos` vota la traslación y la verifica con
un índice espacial; `PlanoLeido.rotulos_desplazados` la lleva; y
`coherencia.ROTULOS_DESPLAZADOS` emite **un** hallazgo con `aplicado: False`
dentro — no los 206 `RECINTO_SIN_ETIQUETA` que repiten el síntoma y esconden la
causa. Coste medido: 0,26 s en el plano patológico, **1 ms** en uno ya rotulado.
18 tests en `tests/test_rotulos_desplazados.py`, incluido el que se pondrá rojo
el día que alguien decida mover el plano del arquitecto.

### 4. **El bloqueo de verdad de `plantasimple.dxf`, y no lo sabíamos**

Mandando el plano entero por la vía del comando (211 polilíneas, 787 textos), el
servidor devuelve **HTTP 200 con CERO piezas** y un solo hallazgo:

```
GEOSException: TopologyException: side location conflict at -325.82 -292.68
```

**Causa medida:** 10 de los 206 polígonos de `00 areas` son
auto-intersecantes, y `evaluator.evaluate_room_overlap` revienta al intersecar.
No es el rótulo, no es la capa: **no hay medición ninguna**.

`_closed_polygons_with_color` **no valida `is_valid` a propósito** —está escrito
en su docstring— mientras que el camino de las capas `AM_*` sí lo hace y las
descarta con `MOTIVO_GEOMETRIA_INVALIDA`. Los números para decidir:

| Plano | Polígonos | Inválidos | % del área |
|---|---:|---:|---:|
| `plantasimple` | 206 | **10** | 5,8 % |
| `ejemplo` | 51 | 1 | 0,9 % |
| `v1plantas`, `v2s`, `v3s`, `V5` | — | 0 | 0 % |

Y el dato que decide entre las dos salidas: **`make_valid` conserva el área
exacta** en los casos mirados (24,92 → 24,92; 12,61 → 12,61; 7,24 → 7,24), así
que son auto-intersecciones degeneradas —picos de área cero, vértices
repetidos—, no lazos de verdad. Descartar costaría 5,8 % de superficie real
(`C-6`); reparar la conserva, pero «ArchMuse repara tu geometría» es una decisión
de producto y cambia el resultado de `ejemplo.dxf`, que es el fixture de
referencia de toda la suite.

**Deliberadamente sin tocar, y pendiente de Pablo.** No es una elección que se
tome de lado mientras se arregla otra cosa.

### 5. Del PRD de la beta (APROBADO hoy), adelantado T1

`GET /api/salud` —de lo que depende la rama C de D-1— y `version` en cada
respuesta de `/api/medicion-geometria`, junto a `capacidades`.
`analyzer/version.py` prefiere el `version.json` del paquete y cae a la
constante del repositorio; un `version.json` roto no tumba la medición.
7 tests en `tests/test_salud_y_version.py`.

**T2, medido y sin implementar.** Bloqueando módulos en el import: `trimesh`,
`mapbox_earcut`, `pdfminer` y `pypdf` se pueden dejar fuera **hoy y sin tocar
código** (el endpoint sigue devolviendo 200). `ifcopenshell` (**93 MB**, el
paquete más grande con diferencia) y `anthropic` se importan en la cabecera de
`app.py` y **tumban el arranque** si faltan: sacarlos exige imports perezosos.
`site-packages` son 303,7 MB; lo que el camino del comando carga, 231,8 MB.

**T6 (el log) no se ha empezado.**

## 2026-09-11 (cierre de sesión) · Estado, y lo que espera a `plantasimple.dxf`

**ArchMuse rellena el cuadro de superficies dentro de AutoCAD**, verificado por el
arquitecto en pantalla sobre cuatro planos reales. Suite en verde.

### La capa de `plantasimple.dxf`: contestada sin abrir AutoCAD

Era la pregunta que encabezaba el trabajo de mañana. **Es `00 areas`**, y no hace
falta preguntárselo a nadie: las cuatro candidatas se distinguen por el tamaño de
lo que contienen.

| Capa | Polígonos | Área mediana | Rango | Qué son |
|---|---:|---:|---|---|
| **`00 areas`** | 206 | **8,53 m²** | 3,02 – 84,75 | **habitaciones** |
| `00 TEXTO` | 25 | 0,63 m² | todas iguales | cajas de texto — y **25**, como los 25 cuadros |
| `00-INST` | 123 | 0,25 m² | 0,12 – 0,36 | instalaciones, sanitarios |
| `00 LINEA` | 277 | 0,49 m² | 0,00 – 1,02 | líneas auxiliares |

Ninguna habitación mide 0,25 m². **La distribución de áreas lo decide sola.**

**Y ahí está el hallazgo aprovechable:** el heurístico las puntúa 0,485 / 0,464 /
0,435 — casi empatadas, por eso se rinde. Puntúa alto a `00 TEXTO` y a `00-INST`
porque **el 100% y el 81% de sus polígonos tienen un rótulo dentro**… que es su
propio texto: son cajas de texto conteniéndose a sí mismas. El heurístico premia
«tiene rótulo dentro» y no distingue una habitación rotulada de una etiqueta
dentro de su caja.

**Lo que le falta es el discriminador más obvio: el tamaño.** Un recinto de 0,25
m² no es una habitación, y `analyzer/escala.py` ya tiene la noción de área
plausible (`unidades_plausibles`). Puede que el ingrediente ya esté.

### Pero forzar la capa no basta: aparecen dos problemas más

Leído `plantasimple.dxf` con `leer_plano(doc, "00 areas")`:

**A · Los 206 recintos salen SIN RÓTULO.** Los 939 rótulos del plano están en
`00 TEXTO` (787), `00-INST` (150) y `00 GRIS` (2) — **ninguno en `00 areas`**—, y
`_capas_de_rotulo` devuelve `{'00 areas'}`, o sea, sólo acepta rótulos de la capa
que no los tiene. Además, **ni uno solo de los 939 cae dentro de ninguno de los
80 primeros recintos**, que es lo que hay que entender antes de tocar nada: en
los otros planos del estudio sí caían.

Sin rótulo no hay familia; sin familia no hay ámbito; y el cuadro no se puede
rellenar por mucho que la capa sea la correcta.

**B · `medir_planta` REVIENTA con un traceback.**

```
shapely.errors.GEOSException: TopologyException: side location conflict
at -325.82 -292.68. This can occur if the input geometry is invalid.
```

**10 de los 206 polígonos son inválidos** —auto-intersecciones, uno de 84,75 m²—
y `extract_room_polygons` **no los filtra**: devuelve los 206 tal cual, y
`unary_union` explota.

Esto es lo más grave de los dos, y no por el plano: **es un traceback ante el
fichero de un cliente.** La regla de oro del banco de tortura dice que *«lo único
que NUNCA es aceptable es un traceback: eso es un bug, no un rechazo
controlado»*. Y el caso está en el banco —`09_geometria_basura.dxf` incluye una
polilínea en pajarita— pero **el banco prueba los scripts, no `medir_planta`**,
así que nunca se ejercitó por este camino. Es el mismo patrón que `C-9`: dos
caminos, uno probado.

### El primer paso de mañana, en este orden

1. **B antes que nada**: que una geometría inválida se descarte con motivo en vez
   de reventar. Es corrección, no capacidad, y afecta a cualquier plano real.
2. **A**: por qué ningún rótulo cae dentro de ningún recinto en este plano.
3. **Que el comando permita decir la capa** cuando el heurístico no decida — con
   la respuesta ya sabida (`00 areas`) como caso de prueba.
4. Y si sobra tiempo, el discriminador de tamaño para el heurístico, que
   probablemente haga innecesario el punto 3 en este plano concreto.

**Nada de esto se ha tocado hoy**: está medido y escrito, no arreglado.

### Lo que sigue pendiente, sin cambios

- **Cinco preguntas para el arquitecto**: la fila «TOTAL S. UTIL», qué espera
  cuando el cuadro pide una fila que el plano no dibuja, con qué marca se queda
  una celda sin rellenar, si el «8uds.» es el número de unidades, y **por qué
  `V5.dxf` no tiene cuadro**. *(Desde el 2026-09-12 son **seis**: qué significan
  `PMR` y `FN` en `VT11 /2 PMR` y `VT13 /3  FN`, y si cambian la tipología o sólo
  la califican.)*
- **`C-8`** firmado y sin implementar.
- **Los perfiles de estudio** y, con ellos, la deuda P2 (las cuatro copias de
  convenciones).
- **Distribución en local**: decidida, sin empezar.

---

## 2026-09-11 (tarde-noche) · La columna de valor era una constante, y eso era un bug latente

Pablo señaló que el punto 3 del inventario de convenciones **no era deuda sino un
bug latente**, y tenía razón: `COLUMNA_INTERIOR = 1` y `COLUMNA_EXTERIOR = 3` no
producen una excepción ni una celda vacía en un cuadro con otra disposición.
Producen **cifras correctas escritas en la columna equivocada** del documento que
alguien firma. Es el mismo patrón que `C-4` —un `0,00` sobre una lectura
fallida— y `C-7` —una medición limpia a la que le falta media vivienda—: **el
resultado parece bueno**.

**Arreglado sin esperar a los perfiles.** Dos cambios:

1. **La columna de valor se deriva de la etiqueta**: la celda a rellenar es la de
   la derecha de su etiqueta, sea cual sea el índice. `CeldaCuadro` guarda ahora
   `columna_etiqueta` además de `columna_indice`, para que la relación entre las
   dos sea **comprobable** y no una convención tácita.
2. **Qué celda es una etiqueta lo decide el emparejador, no su posición.** Antes
   se clasificaba por paridad —pares etiqueta, impares valor—, que es como son
   los tres cuadros de este estudio y nada más lo garantizaba.

Y si la etiqueta está en la última columna no hay dónde escribir: **se declara**
en vez de elegir otro sitio.

`tests/test_columna_de_valor.py`, 9 tests con cuadros de **2, 4, 5 y 6 columnas**
y con las etiquetas en posiciones que este estudio no usa (impares, desplazadas,
en la última). Seis fallaban antes del arreglo. El cuadro real de `v1plantas.dxf`
sigue dando exactamente lo mismo, comprobado de punta a punta por el endpoint.

**Una confusión más del mismo tipo, encontrada al escribir el test:** un cuadro
sin ninguna celda escribible devolvía `None`, y el arquitecto leía «no se
reconoce ningún cuadro» — falso, y le manda a mirar donde no es. Ahora se
distingue «no hay cuadro» de «hay cuadro y no se puede rellenar». Es la cuarta
vez en dos días que un mensaje da por supuesta la causa.

### Las dos deudas que quedan, apuntadas con prioridad

En el PRD del 10-sep, y ninguna depende de que se construyan los perfiles:

- **PRIORIDAD 1 — dos capas de marca distintas según la vía.** La web escribe en
  `00 ARCHMUSE BORRADOR` y el `.lsp` en `ARCHMUSE - BORRADOR`. El mismo plano
  marcado por los dos caminos acaba con dos capas, y quien apague una seguirá
  viendo la otra — o creerá que quitó la marca y no. **Es una violación de `C-9`
  en la práctica**: las dos vías no hacen lo mismo. Que el invariante no la cace
  es una carencia suya, no una defensa: `C-9` compara **mediciones**, y esto es
  un efecto sobre el dibujo. Cuando se arregle, hay que ampliarlo para que
  compare también **lo que cada vía escribe**.
- **PRIORIDAD 2 — cuatro copias de la misma convención.** `"00 areas"` en tres
  sitios y el título del cuadro en dos. Las copias entre Python y LISP son las
  peores porque no hay forma de compartir una constante entre los dos lenguajes;
  la salida razonable es que el servidor las declare —como ya declara
  `capacidades`— y el cliente las lea al arrancar.

---

## 2026-09-11 (cierre real) · El mensaje de V5, y la decisión que cambia cómo se construye

### El mensaje de `V5.dxf`, corregido

Decía que quizá su cuadro estuviera dibujado con líneas y textos sueltos. En
`V5.dxf` eso **no era verdad**: no hay cuadro de ninguna clase. Mandaba a buscar
algo que no existe, igual que el mensaje de las celdas mandó a mirar `ssget`
cuando el fallo era del servidor.

Ahora distingue dos casos con lo que sabe (`am:cuantas-tablas`):

- **Cero tablas en el dibujo** → «Este plano NO TIENE ningún cuadro de
  superficies. No es que no lo entienda: no hay ninguna tabla de AutoCAD.» Y dos
  salidas útiles: que el cuadro puede estar en otro plano, o que si lo tiene
  dibujado a mano hay que decirlo, porque entonces el trabajo es enseñarle a leer
  el suyo, no dibujarle otro.
- **Hay tablas y ninguna es el cuadro** → dice cuántas hay y qué título busca, y
  añade lo que importa: *«si tu cuadro se titula de otra forma, dilo; ArchMuse no
  debería dar por hecho cómo titulas tus tablas»*.

Es la tercera vez en dos días que un mensaje **da por supuesta la causa** y manda
el diagnóstico al sitio equivocado. Los tres costaron tiempo: el de las celdas
una sesión, el del cuadro media, y éste habría costado un PRD entero si no se
hubiera mirado el DXF antes de decidir.

### El PRD de crear cuadro queda parado

`docs/prd/2026-09-11-crear-el-cuadro-donde-no-lo-hay.md`, en **Borrador y sin
trabajar**, hasta que el arquitecto conteste **por qué `V5.dxf` no tiene cuadro**.
Es la quinta pregunta pendiente para él, y la que más trabajo decide.

### DECISIÓN DE PRODUCTO: el perfil del estudio

Anotada al final del PRD del 10-sep. **No se construye hoy; cambia cómo se
construye a partir de hoy.**

**Ningún estudio dibuja igual.** ArchMuse funciona con las convenciones de **un**
arquitecto —su capa `00 areas`, sus rótulos, el título de su cuadro— y otro
estudio no funcionaría. La salida no es personalizar cada instalación a mano
(eso es consultoría: no escala y convierte cada cliente en un proyecto), sino que
**el arquitecto configure su perfil una vez**.

No se diseña todavía porque falta el dato que decide su forma: **si las
diferencias entre estudios son de tres parámetros o de treinta**. Con un solo
estudio delante no se sabe, y un sistema de configuración diseñado para el caso
equivocado o se queda corto al segundo cliente o es un formulario que nadie
rellena.

**La regla que sí entra en vigor hoy:** nada de convenciones escritas a fuego.
Todo valor de convención queda en un sitio identificable como parámetro de
perfil, aunque de momento tenga un solo valor. No es refactorizar: es no volver a
esparcirlas.

**Y el inventario, buscado en el código y no de memoria**, con tres cosas que no
esperaba encontrar:

- **`"00 areas"` está escrito en tres sitios** (`parser.AREA_LAYER`,
  `geometria_recibida.CAPA_POR_DEFECTO`, y el `.lsp`), y **el título del cuadro
  en dos** (Python y LISP). Cuatro copias de convenciones que ya son deuda hoy,
  antes de que exista ningún perfil.
- **La marca de borrador usa dos capas distintas según la vía**:
  `00 ARCHMUSE BORRADOR` por la web y `ARCHMUSE - BORRADOR` desde AutoCAD. El
  mismo plano marcado por los dos caminos acaba con dos capas.
- **`COLUMNA_INTERIOR = 1` y `COLUMNA_EXTERIOR = 3`** dan por hecho un cuadro de
  cuatro columnas con las etiquetas en las pares. Los tres cuadros de este
  estudio lo cumplen; si otro no lo cumple, **no fallará ruidosamente: escribirá
  en la columna equivocada**. Es el supuesto más silencioso de todo el
  inventario.

Queda anotado también **lo que NO es perfil**, para que el día que se construya
nadie meta ahí lo que no debe: los criterios firmados `C-1` a `C-9` (son criterio
profesional, no convención de dibujo), la marca de borrador (`C-3` no se
configura) y las tolerancias de medición (son propiedades de la geometría).

---

## 2026-09-11 (noche) · Los otros cuatro planos: una alerta descartada, un plano sin cuadro y una pregunta bloqueante resuelta

Probados `v2s.dxf`, `v3s.dxf` y `V5.dxf` con el comando, después de que
`v1plantas.dxf` funcionara. Tres resultados.

### 1. VERIFICADO: las cifras idénticas de v1plantas/v2s/v3s NO son un bug

Los tres devolvían **exactamente** las mismas superficies —salón 21,90,
dormitorios 12,72 / 8,48 / 8,53, baño 4,01, aseo 3,14, tendedero 4,22, total
58,78— y eso podía ser legítimo o podía ser que ArchMuse midiera siempre lo
mismo. **Medido leyendo los tres DXF directamente, sin pasar por el endpoint:**

| | sha256[:16] | polilíneas en `00 areas` | recintos |
|---|---|---|---|
| `v1plantas.dxf` | `2262ce8b732b43a9` | 10 | 8 |
| `v2s.dxf` | `37e982b4856bce70` | 10 | 8 |
| `v3s.dxf` | `541182ba111ef4c4` | **8** | 8 |

Tres ficheros distintos, **la misma geometría con los mismos handles**
(`A61724`, `A61743`, `A61769`…): son la misma vivienda guardada tres veces.
`v3s.dxf` tiene dos polilíneas menos —le faltan el contorno agrupador `A6188E` y
`CA428D`—, y eso es la prueba de que no hay caché ni estado compartido: con
caché, `v3s` habría dado diez.

**Confirmado además por inspección visual del arquitecto**: son la misma vivienda
dibujada tres veces, con distinta rotulación.

**Y el dato bueno del episodio:** `v1plantas.dxf` rotula con **dos líneas**
(«superficie util» + «Dormitorio 1») y `v2s`/`v3s` con **una sola**
(«Dormitorio 1»). **Las dos convenciones funcionan sin tocar nada.** Los cuadros
de `v2s`/`v3s` tienen además una fila que `v1plantas` no tiene —
`S.CONSTRUIDA EXTERIOR`— y el emparejador la reconoce: **18 campos en esos dos,
17 en el primero, los tres al 100%.** Es la primera vez que el emparejador se
prueba contra cuadros que no son iguales entre sí, y es lo que se le pedía.

### 2. `V5.dxf` no tiene cuadro. No es que no se entienda: no existe

El comando decía «si tu cuadro está dibujado con líneas y textos sueltos…», y
había que averiguar cuál de los dos casos era antes de decidir nada. **Es el
primero**, medido:

| | `V5.dxf` | `v1plantas.dxf` (control) |
|---|---|---|
| `ACAD_TABLE` (modelspace, layouts, bloques) | **0** | 1 |
| `LINE` en modelspace | **0** | 0 |
| Textos que suenen a cuadro | **0** de 29 | los suyos |
| Capa `00 CUADROS` | existe, **vacía** | existe, **vacía** |

Los 29 textos de `V5.dxf` son rótulos de estancia y códigos de vivienda, nada
más. Un cuadro dibujado a mano necesitaría líneas y **no hay ni una**. La capa
`00 CUADROS` no dice nada: está vacía en los dos, y el `ACAD_TABLE` de
`v1plantas` vive en la capa `0`.

Y `V5.dxf` es **el plano que mejor mide del lote**: 22 recintos, tres viviendas
completas publicando superficie. Es el único donde ArchMuse tiene todo lo que
necesita y no tiene dónde ponerlo.

**Abierto como PRD aparte**, `docs/prd/2026-09-11-crear-el-cuadro-donde-no-lo-hay.md`,
en Borrador y **con la recomendación de no hacerlo todavía**. Dos motivos, y
ninguno es el coste:

- **Falta una pregunta que sólo contesta el arquitecto: ¿por qué `V5.dxf` no
  tiene cuadro?** Si es «aún no lo he hecho», el PRD vale. Si es «el cuadro de
  esa planta está en otro plano» —la hipótesis que más encaja: `V5` es una
  **planta de tres viviendas** y los tres que sí tienen cuadro son **viviendas
  tipo**— entonces crear uno le mete un documento duplicado. Construir antes de
  saberlo es apostar a una de tres.
- **No existe «el formato del estudio».** Sus tres cuadros **no son iguales**: 17
  campos en uno y 18 en los otros dos, y la misma fila escrita de tres maneras
  (`S. CONSTRUIDA C.` / `S. CONSTRUIDA CERRADA` / `S. CONSTRUIDA CERRADA.`).
  Copiar uno es elegir por él cuál de sus tres formatos es el bueno, que es el
  tipo de decisión que `C-1`, `C-2` y `C-8` dicen que ArchMuse no toma.

Lo que sí conviene hacer ya, y es barato: **el mensaje de `V5.dxf` es falso**.
Dice que a lo mejor su cuadro está dibujado con líneas sueltas, y en ese plano no
hay cuadro de ninguna clase. Manda a buscar algo que no existe, igual que el
mensaje de las celdas mandó a mirar `ssget` cuando el problema era el servidor.
Distinguir los dos casos es mirar si hay algún `ACAD_TABLE`, e **independiente de
que ese PRD se apruebe**.

### 3. Resuelta con dato la pregunta que bloqueaba `plantasimple.dxf`

El barrido del 10-sep avisó de que las 25 tablas de `plantasimple.dxf` declaran
`n_cols = 0` en el DXF, y quedó marcado como **bloqueante**: si AutoCAD decía lo
mismo, no habría celdas que leer y `CU-2` cambiaba de forma.

**Ya está contestado, y por evidencia.** `v2s.dxf` y `v3s.dxf` declaran
`n_rows=33 n_cols=0` **y los dos rellenaron correctamente desde AutoCAD**. O sea:
`vla-get-Columns` sobre la tabla viva devuelve el valor bueno aunque el DXF diga
cero. Es un artefacto de cómo ezdxf lee esa entidad, no del dibujo.

**`CU-2` ya no está bloqueado**, y la comprobación que encabezaba el plan de
mañana se puede tachar sin abrir AutoCAD.

### Lo que queda para mañana

El primer paso cambia: ya no hace falta comprobar `vla-get-Columns`. Queda:

1. **Qué capa de `plantasimple.dxf` es la buena** de las cuatro candidatas
   (`00 areas`, `00 TEXTO`, `00-INST`, `00 LINEA`). Eso no se deduce: se mira el
   plano o se pregunta. Es lo que desbloquea el frente (a).
2. **El mensaje falso de `V5.dxf`** (§14.3 del PRD nuevo), que es corrección y no
   capacidad.
3. Y las preguntas para el arquitecto, que ahora son **cinco**: las cuatro de
   esta mañana más **por qué `V5.dxf` no tiene cuadro**.

---

## 2026-09-11 (cierre) · El cuadro del arquitecto se rellena de verdad, en su AutoCAD

**`archmuse.lsp` v2.0.2, verificado en AutoCAD 2027 sobre `v1plantas.dxf`.** Diez
celdas escritas con sus cifras correctas, seis vacías sin inventar nada, la marca
de borrador debajo del cuadro sin solapar, catorce filas antes y después, sin
crash.

Es la primera vez que ArchMuse escribe dentro del entregable de un arquitecto y
sale bien. Lo que hay hoy en el cuadro de `VT1/3`:

| Fila | Escrito | | Fila | Por qué no |
|---|---|---|---|---|
| salón + cocina | **21,90 m²** | | terraza 1 | una sola terraza para dos filas |
| pasillo | **0,00 m²** | | terraza 2 | idem |
| dormitorio 1 | **12,72 m²** | | TOTAL SUP. EXTERIOR | depende de las terrazas |
| dormitorio 2 | **8,48 m²** | | TOTAL S. UTIL | `C-1`, y pregunta abierta |
| dormitorio 3 | **8,53 m²** | | S. CONSTRUIDA C. | no se puede medir |
| baño | **4,01 m²** | | NUMERO UDS | dato de proyecto |
| aseo | **3,14 m²** | | VIVIENDA TIPO | ya la tenía rellena, no se toca |
| vestibulo | **0,00 m²** | | | |
| tendedero | **4,22 m²** | | | |
| TOTAL SUP. INTERIOR | **58,78 m²** | | | |

### Los cuatro arreglos de hoy, en orden

**1. El servidor era antiguo.** Cero celdas, y el mensaje mandaba a mirar donde
no era. El endpoint declara ahora `capacidades`, y el comando distingue «no ha
podido» de «no lo tiene».

**2. El rótulo salía del orden de un `for`.** Dos MTEXT dentro de cada recinto
—«superficie util» y «Dormitorio 1»— y `match_label_to_room` devolvía el primero
que llegara. El mismo plano daba un resultado leyendo el DXF y otro desde
AutoCAD. Un nombre gana ahora siempre a un título de campo, reconocido por lo
que dice y no por dónde está.

**3. La marca tapaba el cuadro y era ilegible.** Se colocaba desde el punto de
inserción de la tabla —su esquina **superior** izquierda— así que «debajo» la
dejaba encima, sobre las tres primeras filas recién rellenadas; con altura fija
al triple de la del cuadro y ancho de 60 caracteres, saliéndose de la pantalla.
Las tres medidas salen ahora de la propia tabla: su borde inferior, la altura de
texto de sus celdas y su ancho.

**4. Y el que más importaba: números sin marca.** El arreglo anterior reventó
—`vla-GetBoundingBox` escribe safearrays donde `vla-get-InsertionPoint` devuelve
variantes— **después** de escribir las diez celdas, dejando el plano con cifras y
sin advertencia. Eso no es un crash: es el estado que `C-3` existe para impedir,
y parece un cuadro definitivo. Ahora todo va en un solo grupo de deshacer, la
marca **devuelve si se puso**, y si no se puso **se retira lo escrito** — con un
aviso explícito si ni siquiera eso funciona, porque el aviso no puede depender
del deshacer.

### Lo que queda pendiente

**Del arquitecto — cuatro preguntas, ninguna la decide ArchMuse:**

1. **La fila «TOTAL S. UTIL(m2)»**, que suma interior y exterior contra el
   criterio `C-1` que él mismo validó. Hoy se deja vacía. Las tres salidas
   posibles están redactadas en §14.2 del PRD.
2. **Qué espera cuando el cuadro pide una fila que el plano no dibuja.** Hoy:
   `0,00 m²` si la medición está limpia (`C-4`), en blanco si no.
3. **Con qué marca se queda una celda que no se puede rellenar.** Hoy no se
   escribe nada, y el motivo vive en la línea de comandos y en el acta.
4. **`NUMERO UDS:`** — el plano declara «8uds.» en la capa `00 TEXTO`. Hoy la
   celda se deja vacía porque es dato de proyecto, no medición. Leerlo es fácil;
   decidir que ese texto suelto es el número de unidades no lo decide un
   programa.

**Del producto:**

- **`plantasimple.dxf`** — el único proyecto completo del lote (2.326 polilíneas,
  25 cuadros, 4 capas candidatas) y el único de los cinco que hoy **no se mide**.
  Ya está copiado en `_material/`. Dos frentes, en este orden: (a) que el usuario
  pueda dar la capa desde el comando cuando el heurístico no decida, y (b) `CU-2`
  cuadro↔vivienda. **Antes de escribir código de (b)**: abrir el plano en AutoCAD
  y comprobar si `vla-get-Columns` devuelve 0 en esas tablas — en el DXF declaran
  `n_cols = 0`, y si AutoCAD dice lo mismo no hay celdas que leer y (b) cambia de
  forma.
- **`C-8` firmado y sin implementar.** Lo que el plano declara manda sobre lo que
  ArchMuse deduce. Toca `medicion.py`, los totales y `C-2`: sesión propia.
- **Distribución en local** (§0.0 bis del PRD): decidida, sin empezar. Instalador
  único, arranque automático, y cómo se actualiza — más la consecuencia de que
  sin servidor nuestro **no hay telemetría**.
- **DWG nativo:** deuda consciente. 70 de los 75 planos son DWG, y la vía AutoCAD
  lo hace innecesario porque lee el dibujo abierto, no el fichero.
- **`v3s.dxf` y `V5.dxf`** tienen cuadro y no se han probado por el comando.

### El primer paso de mañana

**Abrir `plantasimple.dxf` en AutoCAD y mirar dos cosas, en este orden:**

1. **`vla-get-Columns` sobre una de sus 25 tablas.** Si devuelve 0, el plan de
   `CU-2` cambia entero y hay que saberlo antes de escribir una línea.
2. **Qué capa es la buena** de las cuatro candidatas (`00 areas`, `00 TEXTO`,
   `00-INST`, `00 LINEA`). Eso no se deduce: se mira el plano, o se le pregunta
   al arquitecto. Es el dato que desbloquea el frente (a).

Nada de código hasta tener esas dos respuestas.

### Estado de la suite

**1.538 tests en verde**, 39 saltados. Los que se saltan son los que necesitan
planos reales que no están versionados —son de clientes y el repositorio es
público— más `plantasimple.dxf`, que se salta con motivo hasta que se pueda
resolver su capa.

### Lo que esta sesión ha enseñado, y ya está en `CLAUDE.md`

Tres veces el mismo patrón en dos días: **una explicación plausible anotada sin
medir sobrevive mucho más de lo que debería**, y cuanto mejor suena, más tarda
alguien en comprobarla. La tercera añadió el matiz que faltaba: **cuando algo
funciona y no sabes por qué, es tan investigable como cuando falla**. El aviso
concreto —cada vez que el código resuelve una ambigüedad que nadie escribió, hay
una decisión implícita sin dueño, y suele salir del orden de un `for`.

Y una segunda, que aparece cuatro veces hoy y merece quedar escrita: **un test
que pasa no prueba que vigile nada.** El guardián del `ssget`, el de las
variables locales, el de las erratas en símbolos citados y el de la marca: los
cuatro se escribieron, pasaron, y sólo se supo si servían al **romper el código a
propósito y comprobar que fallaban**. Uno de ellos —el de las variables— pasaba
con el fallo dentro.

---

## 2026-09-11 · El rótulo dependía del orden de llegada, y nadie miraba el hueco entre las dos vías

Primera prueba real del `.lsp` v2.0.0 en AutoCAD, y el camino entero de
diagnóstico. Tres cosas distintas, en el orden en que aparecieron.

### 1. Un falso culpable: el servidor era antiguo

La primera ejecución dio **cero celdas**. El mensaje del comando decía «no le
llegan las celdas del cuadro», así que la búsqueda fue a `ssget` y a
`vla-GetText` — y los dos estaban bien. Con el cuerpo reconstruido carácter a
carácter como lo escribe `am:recolectar` y mandado como cuerpo crudo, el
servidor devolvía el reparto completo.

**El proceso Flask que atendía era anterior al reparto.** `python app.py` no
recarga al cambiar los ficheros. Medía perfectamente —por eso todo lo demás
funcionaba— y no conocía la palabra `reparto`.

Lo que se ha hecho para que no se repita: el endpoint **declara qué sabe hacer**
(`capacidades: ["medicion", "reparto_de_cuadro"]`, siempre), y el comando
distingue «este servidor no ha podido» de «este servidor no lo tiene», con la
instrucción de reiniciarlo. Es `C-7` en el sentido contrario: igual que el
servidor no puede suponer que le ha llegado todo, el cliente no puede suponer que
al otro lado está la versión que espera.

Y dos fallos propios por el camino, que cuento porque el segundo enseña más que
el primero: al escribir ese mensaje usé `n-celdas`, local de `am:recolectar`, que
ya no existe cuando el comando llega ahí — AutoLISP no avisa, devuelve `nil`, y
`(itoa nil)` habría reventado **justo en el camino de error**. Escribí un
guardián para ese tipo de fallo y **pasó con el fallo dentro**: `re.findall` no
solapa, así que al casar `(itoa ` se comía el espacio que `n-celdas` necesitaba
como delimitador, y el único símbolo que había que cazar era justo el que se
escapaba. Corregido, y **comprobado a la inversa**: reintroducido el fallo, ahora
falla. Un test que pasa no prueba que vigile nada.

### 2. El fallo de verdad: el rótulo salía del orden de un `for`

Con el servidor reiniciado, el reparto llegó y dijo la causa real: los ocho
recintos se llamaban **«superficie util»**.

Los planos de este estudio rotulan cada estancia con **dos MTEXT
independientes** —comprobado en el DXF, no deducido: handles distintos, misma
altura, ningún `\P` ni `\n`—:

```
superficie util          <- el título de campo (qué magnitud es)
Dormitorio 1             <- el nombre
```

**Los dos caen dentro del polígono**, y `match_label_to_room` devolvía
`inside[0]`. O sea: el nombre de la estancia era **el primer texto que llegara**,
y ese orden no es el mismo en `doc.modelspace()` que en un `ssget` de AutoCAD.
Medido invirtiendo el orden: los ocho recintos pasan a llamarse «superficie
util».

Eso explica lo que parecía imposible: **el barrido del 2026-09-10 leyó los ocho
nombres bien y el comando leyó los ocho mal, con el mismo plano y el mismo
código.** No había dos comportamientos, había uno que dependía de algo que nadie
controlaba.

**El arreglo** (`parser._es_titulo_de_campo`): un nombre gana siempre a un título
de campo, esté donde esté en la lista. El título se reconoce **por lo que dice**
—un patrón corto y literal, `superficie|sup.|s.` + `util|construida`— y no por
su posición, que era la otra salida posible y la mala: «el de abajo» no es un
criterio, es una coincidencia de este plano. Si el único texto de un recinto es
un título, la pieza **se queda sin rótulo** en vez de heredar el nombre de una
magnitud.

`tests/test_rotulo_con_titulo_de_campo.py`, 9 tests, con la reproducción exacta
sobre `v1plantas.dxf`. Cinco fallaban antes.

### 3. Lo que de verdad faltaba: nadie comparaba las dos vías

Los dos fallos de estos dos días son el mismo error de diseño de las pruebas:

| | Por la web | Por el cliente CAD |
|---|---|---|
| **10-sep**, color y flag de cerrada | salón 21,90 m² | **el salón desaparece**, `0,00` en el cuadro |
| **11-sep**, títulos de campo | «Dormitorio 1» | **«superficie util»** |

Las dos vías tenían tests. **Los dos estaban en verde.** Cada camino se probaba
por separado y ninguno cruzaba, así que el hueco entre dos caminos correctos no
lo vigilaba nadie.

De ahí `C-9`, firmado hoy como **invariante permanente**: las dos vías tienen que
leer lo mismo —los mismos recintos, los mismos rótulos, las mismas superficies—
y si divergen es grave aunque las dos cifras parezcan razonables, porque no se
sabe cuál es la buena. `tests/test_dos_vias_leen_igual.py` lo comprueba sobre los
seis fixtures del repositorio y los tres planos reales que hay en esta máquina,
**y con el orden de los textos invertido**, que es lo único que el cliente no
puede garantizar.

Verificado como se verifica un guardián: revertidos los tres fallos históricos
uno a uno, **el invariante falla con los tres**.

### 4. Lo que queda escrito y sin implementar

- **`C-8` · Lo que el plano declara manda sobre lo que ArchMuse deduce.**
  Firmado hoy, sin tocar código. «superficie util exterior» no es ruido: es el
  arquitecto declarando en qué magnitud entra cada recinto, y coincide sin una
  excepción con lo que ArchMuse deducía por familia. Deducir lo que él ya ha
  escrito es sustituir su criterio, que es lo que `C-1` y `C-2` prohíben. Toca
  `medicion.py`, los totales y `C-2`, así que va en sesión propia.
- **Distribución en local** (§0.0 bis del PRD): el servidor correrá en el equipo
  del arquitecto. La razón es que los planos son de sus clientes y no deben salir
  de su máquina, y es además el argumento de venta ante un estudio que no nos
  conoce. Sale gratis porque **es lo que ya hay**. Queda anotado qué implicará:
  un instalador único, que el servidor arranque solo, cómo se actualizará — y una
  consecuencia que no es menor, que **con el servidor en local no hay
  telemetría**: todo lo aprendido estos días salió de mirar planos reales aquí.
  La privacidad que se vende es la misma que nos deja a ciegas.

### La lección, por tercera vez

El barrido del 10-sep **anotó esos diez textos en su propio informe** y los dejó
como curiosidad. La pregunta que se hizo era «¿qué son estos textos?» y tenía
respuesta fácil. La que faltaba era la otra:

> Si hay dos textos dentro de cada recinto, **¿por qué entonces el rótulo sale
> bien?**

Está en `CLAUDE.md` como regla: **cuando algo funciona y no sabes por qué, es tan
investigable como cuando falla.** Un acierto sin explicación es una hipótesis con
suerte, y aguanta hasta que cambia lo que no sabías que importaba —el orden de
una lista, el ordenador de otro— y entonces falla delante del usuario. El aviso
concreto que hay que aprender a ver: **cada vez que el código resuelve una
ambigüedad que nadie escribió, hay una decisión implícita sin dueño**, y suele
estar saliendo del orden de un `for`.

---

## 2026-09-10 (noche) · El cuadro del arquitecto se rellena, y por el camino aparecieron dos fugas de superficie

Tarea 2 del PRD `2026-09-10-rellenar-el-cuadro-del-arquitecto.md`, aprobada con
orden estricto y ejecutada después de que 0 y 1 estuvieran en verde. **1.496
tests pasan**, 39 saltados (eran 1.449).

### Lo que se ha construido

**`analyzer/emparejador_cuadro.py` — qué fila del cuadro es cada etiqueta.**
Sustituye a un diccionario de cadenas exactas copiadas de un solo plano, que
sobre el segundo cuadro del mismo arquitecto reconocía 13 de 17 campos. Los
cuatro que fallaban eran el mismo señor escribiendo dos veces: `TOTAL SUP.
INTERIOR (m2)` contra `TOTAL SUP.UTIL INTERIOR (M2)`, `S. CONSTRUIDA C.` contra
`S. CONSTRUIDA CERRADA`. Ahora empareja **por palabras presentes**: `TOTAL` más
`INTERIOR` es la fila del total interior, y la palabra `UTIL` que las separa deja
de importar porque nunca importó. Las palabras prohibidas hacen la distinción
fina — `TOTAL S. UTIL(M2)` es el total de todo **porque no dice ni INTERIOR ni
EXTERIOR**. **17 de 17 en los dos cuadros.**

Y la regla que impide que invente: una etiqueta que encaja en dos campos no
encaja en ninguno, y un campo que reclaman dos filas se queda sin ninguna. Es
estricto a propósito: un emparejador que acierta el 95% escribe en la fila
equivocada del cuadro que alguien firma una de cada veinte veces, y ese error no
se ve leyendo el resultado.

**`analyzer/reparto_cuadro.py` — la frontera.** Lo que sale es una lista de
`(fila, columna, texto)` y tres listas de lo que no se ha podido escribir. El
cliente CAD **no interpreta nada**. Aquí viven `C-4` (el `0,00` sólo sobre
medición limpia), `C-5` (las dos terrazas en blanco, los tendederos sin sumar) y
`C-6`, con `verificar_conservacion()` comprobando que toda pieza medida está en
exactamente uno de los tres sitios.

**`autocad/archmuse.lsp` v2.0.0.** Ya no inserta una tabla: busca la del
arquitecto por su título, lee sus celdas con `vla-GetText`, las manda, enseña el
reparto, **pide confirmación** y escribe con `vla-SetText`. La marca `C3` va en
la capa `ARCHMUSE - BORRADOR`, debajo del cuadro, sin tocar ni una celda. Se han
retirado las funciones que la tabla propia usaba y no usa nadie.

### Las dos fugas de superficie que aparecieron al probarlo de verdad

Con todo escrito, el reparto por la vía AutoCAD **no coincidía** con el del DXF
directo. Las dos causas eran del transporte, no del reparto, y las dos borraban
superficie sin decirlo:

**1. El payload no llevaba el color, y el color es lo que distingue una
habitación de un contorno.** `_discard_container_candidates` mira si el polígono
lleva color propio o el de su capa. El DXF materializado salía entero en
BYLAYER, así que el contorno de la zona exterior volvía a entrar como una
habitación más: 8 piezas pasaban a 10 y reaparecían los 7,08 m² dibujados dos
veces que se habían arreglado por la mañana.

**2. El cliente filtraba por el flag de cerrada, y ese flag está mal puesto — en
`v1plantas.dxf`, en el salón.** `ssget` sólo sabe mirar el bit del código 70. En
este plano 2 de 10 polilíneas lo llevan mal, y **una es el `Salón/cocina` de
21,90 m²**. Filtrando en el cliente, esa polilínea no salía del dibujo, el
servidor no podía recuperarla, y el resultado era esto:

> el cuadro del arquitecto recibía un **`0,00 m²` en la fila del salón**, con la
> medición aparentemente limpia y sin un solo aviso.

Es exactamente el fallo que `C-4` existe para evitar, y `C-4` no lo veía: desde
el servidor la medición **estaba** limpia. Lo que faltaba no se había perdido
midiendo, se había perdido antes de llegar.

**El arreglo es el que la nota del 2026-09-09 ya proponía**, y ahora las cifras
que lo justificaban están confirmadas: el cliente manda **todas** las polilíneas
de la capa con su `color` y su flag en `cerrada`, y decide `parser._esta_cerrada`
en el servidor, que además sabe recuperar la que cierra geométricamente.

Con eso, el reparto por la vía AutoCAD coincide **exactamente** con el del DXF
directo: salón 21,90 · dormitorios 12,72 / 8,48 / 8,53 · baño 4,01 · aseo 3,14 ·
tendedero 4,22 · pasillo y vestíbulo 0,00 · **TOTAL SUP. INTERIOR 58,78** · las
dos terrazas en blanco con su motivo · `VIVIENDA TIPO` intacto.

**Un tercer detalle, pequeño y del mismo tipo.** `validar` quitaba el vértice
repetido del final de cada contorno. Con `close=True` sobra; con el flag mal
puesto **es la única prueba de que la polilínea cierra**. Quitarlo convertía el
anillo en una línea con los extremos en esquinas distintas y la recuperación
geométrica dejaba de funcionar. Ahora sólo se quita cuando el flag dice cerrada.

### Dos tests que cambiaron de verdad porque la verdad cambió

`test_el_payload_filtra_por_el_flag_igual_que_ssget` y
`test_el_motor_mide_dos_recintos_mas_de_los_que_el_cliente_puede_mandar` medían
la carencia: 6 medidos, 4 enviables. El segundo decía en su docstring: «cuando
esa mejora se haga, este test tiene que cambiar a 6 y 6 — y el cambio quedará en
el diff, que es el punto». Eso es lo que ha pasado. Ahora dicen que el cliente
manda las 7 con su flag y que el servidor recupera 6.

### Lo que NO se ha ejecutado, y es la mitad del trabajo

**Nada del `.lsp` v2.0.0 ha corrido en AutoCAD.** Lo que se probó el 2026-09-09
fue el comando anterior; de lo que hay hoy, lo único ya visto funcionando es la
parte que no ha cambiado —selección, POST y lectura de la respuesta—. Sin probar:
encontrar el cuadro, `vla-GetText`, `vla-SetText`, la confirmación, la marca en
su capa y el `UNDO`. Está en el **paso 8 bis** del checklist, escrito para
`v1plantas.dxf` y con las diez cifras que tienen que salir.

Del lado del servidor, en cambio, el reparto entero está probado contra el plano
real: 23 tests en `test_reparto_cuadro.py`, 20 en `test_emparejador_cuadro.py`.

### Lo que sigue pendiente del arquitecto

Sin cambios desde esta mañana, y ninguna de las dos la decide ArchMuse:

1. **La fila «TOTAL S. UTIL(m2)»**, que suma interior y exterior contra el
   criterio `C-1` que él mismo validó. Hoy no se rellena.
2. **Qué espera cuando el cuadro pide una fila que el plano no dibuja.** Hoy:
   `0,00 m²` si la medición está limpia (`C-4`), y en blanco si no.

Y una tercera que no estaba: el cuadro pide `NUMERO UDS:` y **el plano lo
declara** — hay un texto «8uds.» en la capa `00 TEXTO`. Hoy esa celda se deja en
blanco porque el número de unidades es un dato de proyecto, no una medición.
Sería fácil leerlo del plano y marcarlo como declarado por él, pero eso es
decidir que un texto suelto del plano es el número de unidades, y eso no lo
decide un programa.

---

## 2026-09-10 (tarde) · Dos bugs que llevaban meses midiendo mal, y que se daban por criterios

Cambio de objetivo del producto, y viene del arquitecto: `ARCHMUSE` no tiene que
insertar una tabla nueva, tiene que **rellenar el cuadro que su estudio ya tiene
maquetado**. PRD `docs/prd/2026-09-10-rellenar-el-cuadro-del-arquitecto.md`,
aprobado con orden estricto de trabajo: nada de cuadro hasta que estén en verde
las dos correcciones de abajo.

Y las dos correcciones son lo importante de la sesión, porque **ninguna de las
dos era lo que decía la ficha que era**.

### La investigación: el cuadro no se podía rellenar aunque el emparejamiento fuera perfecto

Antes de escribir el PRD se midió `v1plantas.dxf` —el plano de prueba del
arquitecto— con lo que ya hay. `medir_planta` devolvía esto:

```
util_interior_m2: null
util_exterior_m2: null
impedimentos:
  - "hay 7,08 m² dibujados dos veces: la suma de las piezas da 74,95 m² y la
     superficie que ocupan realmente es 67,87 m²"
  - "1 pieza(s) no se sabe si son superficie interior o exterior por su rótulo
     («Ba\U+00F1o» 4,01 m²)"
```

**Ni una sola superficie publicable.** El cuadro habría salido entero en blanco
por muy bien que funcionara el emparejamiento de filas. De ahí el orden que
impuso la aprobación.

### Bug 1 · El «Tendedero duplicado» no era una duplicación: era un contorno

Llevaba desde el 2026-09-08 anotado como «fallo de duplicación del Tendedero» y
figuraba entre los **tres cambios de criterio validados con el arquitecto**. No
era un criterio y no había duplicación: lo que parecían dos tendederos era **un
tendedero de 4,22 m² y el contorno de 8,63 m² que lo agrupa con la terraza**.
Cubre el 94,8% del uno y el 92,7% de la otra.

`_discard_container_candidates` existe justo para descartar eso, y aquí no lo
descartaba por una cuarta condición que exigía que el polígono **contenido**
estuviera en BYLAYER. La condición se apoyaba en una suposición que el propio
docstring daba por buena —«las habitaciones reales de estos planos siempre usan
el color del layer»— y que es falsa: este estudio dibuja sus piezas exteriores en
verde (ACI 3) y el contorno que las agrupa en 150.

De qué color esté dibujado lo de dentro no dice nada sobre si lo de fuera es un
contorno. Eso lo dicen las otras tres condiciones —color propio, misma etiqueta,
contención por encima del umbral— y siguen intactas, con sus tests de control.

`tests/test_contorno_agrupador.py`, 9 tests: el caso nuevo, el que ya funcionaba,
los dos controles de lo que NO debe cambiar (un contorno en BYLAYER se conserva;
un contorno con otra etiqueta se conserva, que es lo que evita dejar a una
vivienda sin su salón) y tres de regresión sobre el plano real. **Rojo primero,
arreglo después**, como pedía la aprobación.

### Bug 2 · `\U+00F1` no es una eñe hasta que alguien la decodifica

El segundo impedimento era el «Baño» sin clasificar, también anotado como
criterio validado. Tampoco lo era.

AutoCAD guarda las tildes y las eñes de un TEXT o un MTEXT como escapes —
`ba\U+00F1o`, `sal\U+00F3n`— y **`plain_text()` de ezdxf 1.4.4 no los
decodifica** (comprobado contra la librería). Nada en `analyzer/` lo hacía
tampoco. Así que `Ba\U+00F1o` normalizaba a `BA\U+00F1O`, no casaba con
`\bBANO\b`, la pieza se quedaba sin ámbito y **bloqueaba la vivienda entera**.

Dicho en corto: **hasta hoy ArchMuse no medía el baño de ningún plano que
guardara así sus eñes.** No es un caso raro — es cómo AutoCAD guarda un DXF ANSI
con acentos, y «baño» es la pieza que aparece en todas las viviendas. Es un
fallo de producción del camino `/medir`, no del cuadro.

El arreglo vive en `analyzer/texto_dxf.py`, un módulo sin dependencias, y lo
usan los dos lados: `parser._texto_de` (el rótulo del plano) y
`cuadro_superficies._normalizar` (la etiqueta del cuadro). Un módulo propio y no
una función dentro de `parser.py` porque `cuadro_superficies.py` **no importa
`parser.py`** por una decisión escrita y razonada, y no había por qué romperla.
La función es idempotente, que es lo que permite ponerla en los dos extremos sin
coordinarlos.

`tests/test_escapes_unicode.py`, 24 tests, con los dos escapes reales del plano
y con TEXT y MTEXT por separado.

### Lo que las dos correcciones juntas consiguen

`v1plantas.dxf` **publica por fin sus superficies**: cero impedimentos, 8 piezas
(no 9), un solo tendedero, y útil interior y exterior con cifra. Hay un test que
lo comprueba y que dice justo eso — sin las dos, el cuadro del arquitecto saldría
en blanco.

**1.449 tests en verde**, 39 saltados. Eran 1.416 esta mañana.

### Tres criterios nuevos firmados

En `docs/design/2026-09-08-criterios-firmados-de-medicion.md`:

- **`C-4` · Un `0,00 m²` sólo se escribe sobre una medición limpia.** Sale de
  una objeción de ArchMuse a la regla anterior, que escribía `0,00` sin
  condición para una pieza que el cuadro pide y la vivienda no tiene. El bug 2
  demuestra por qué: el baño **existía** y no se veía, así que «no hay ninguna»
  puede ser un fallo de lectura. Un `0,00 m²` se lee como «esto está mirado»;
  una celda vacía, como «esto hay que mirarlo». Escribir el primero sobre una
  búsqueda incompleta es un fallo con formato de dato.
- **`C-5` · Una ambigüedad de reparto no se reparte ni se suma.** Cierra un
  punto que llevaba abierto desde el 2026-09-08. Con la corrección de los hechos
  incorporada: los «dos Tendedero» que lo motivaban no existían.
- **`C-6` · Conservación de la medida**, como **invariante permanente**: toda
  pieza medida acaba en exactamente uno de tres sitios —una celda, la lista de
  piezas sin fila, o la de bloqueos con motivo—, la unión son todas y ninguna se
  repite. Con un test, no con una revisión a ojo. Y su consecuencia: si hay una
  pieza medida sin fila, el total correspondiente **no se rellena**, porque un
  total que no incluye una superficie medida es un total falso.

### La lección, que es la misma de esta mañana

Dos fallos anotados durante días como «criterios profesionales validados con el
arquitecto» eran **dos bugs**. El criterio no hacía falta para ninguno de los
dos; hacía falta abrir el plano y medir. Es la segunda vez hoy: por la mañana,
las «3 de 22 polilíneas con el flag mal puesto» que no aparecían en el fixture
tampoco eran una contradicción, eran dos ficheros distintos.

El patrón se repite: **una explicación plausible anotada sin medir sobrevive
mucho más tiempo del que debería**, y cuanto más razonable suena, más tarda
alguien en comprobarla.

### Lo que queda, y quién lo decide

- **Tarea 2 del PRD** (emparejador de etiquetas y escritura vía LISP): sin
  empezar. Es lo que la aprobación desbloquea ahora.
- Del cuadro del arquitecto se detectan **13 de 17** campos. Los cuatro que
  faltan son variantes de redacción entre sus dos planos (`TOTAL SUP. INTERIOR
  (m2)` contra `TOTAL SUP.UTIL INTERIOR (M2)`, `S. CONSTRUIDA C.` contra
  `S. CONSTRUIDA CERRADA`) y necesitan el emparejador, no el decodificador.
- **Pendiente del arquitecto**, y no lo decide ArchMuse: la fila
  «TOTAL S. UTIL(m2)», que suma interior y exterior contra el criterio `C-1` que
  él mismo validó; y qué espera cuando el cuadro pide una fila que el plano no
  dibuja.
- El fixture con `ACAD_TABLE` no se intenta con el anonimizador —una tabla no
  sobrevive a la reconstrucción, igual que no sobrevivía el flag de cerrada—.
  Alternativa a proponer cuando se llegue a la tarea 7.

---

## 2026-09-10 · La primera ejecución real en AutoCAD: funcionó, y el único fallo fue que la tabla era ilegible

`archmuse.lsp` se ejecutó el **2026-09-09 en AutoCAD 2027**, sobre `V5.dxf`. Es
la primera vez que corre: hasta ese día el fichero llevaba escrito en su propia
cabecera que **nunca se había ejecutado**, y el test que lo vigilaba se ha
cambiado a mano hoy, que es lo que esa cabecera mandaba hacer.

### Qué funcionó, a la primera

- **`APPLOAD` cargó sin un solo error de sintaxis.** 568 líneas de un lenguaje
  escrito sin intérprete delante. El paso 1 del checklist era el que más
  probabilidad tenía de fallar y no falló; el test de paréntesis y de erratas en
  nombres de función hizo su trabajo antes de que costara un día de trial.
- **La capa se detectó sola:** `00 areas`, 22 polilíneas cerradas, **ninguna
  descartada**.
- **El COM, el POST y la respuesta:** el servidor recibió la petición, contestó
  200, y el lector de cuatro campos —el que existe porque `read` no traga 6.564
  caracteres— sacó las cifras sin construir listas.
- **Las cifras coinciden una a una con la verdad del fixture:** VT1/3 58,78 /
  7,54 · VT2/2 50,97 / 7,47 · VT3/3 59,11 / 7,45 · planta 168,86 / 22,46. Esto
  es lo único que el prototipo existía para averiguar: **el modo de entrada
  nuevo no mide por su cuenta**, transporta lo que mide el servidor.
- **Dos columnas separadas y ninguna fila que las sume.** `C-1` se respeta desde
  AutoCAD igual que desde el navegador.
- **La marca de borrador de `C3` está**, y no hay forma de quitarla.
- **Las tildes salieron bien.** El fallo de codificación que el checklist daba
  por el más probable después de la sintaxis **no apareció**: AutoCAD 2027 leyó
  el UTF-8 del fichero sin convertirlo a `Â«`. Aviso: lo que se vio fueron las
  cabeceras del propio `.lsp`. El texto con tildes que viene del servidor —los
  motivos de bloqueo— sigue sin verse en pantalla, porque este plano no bloquea
  ninguna vivienda.

### El fallo: ancho de columna fijo, texto partido letra a letra

Las columnas se creaban con 16, 12 y 12 unidades de ancho por la escala del
dibujo, **sin mirar qué texto iba dentro**. No cabía, y AutoCAD lo partió letra
a letra en vertical: la cabecera «Útil interior (m²)» salió como una columna de
letras sueltas y las cifras se rompieron en dos líneas. Las filas, con un alto
fijo de 1 unidad sin ninguna relación con el tamaño del texto, quedaron
descompensadas alrededor.

Cosmético, y aun así **no se le puede enseñar a un arquitecto**, que es
exactamente para lo que existe el paso 9 del checklist. Un formato feo con las
cifras bien sigue siendo un prototipo que ha funcionado; uno ilegible no llega a
la conversación que había que tener.

**Lo que se ha cambiado** (`am:ancho-columna`, `am:altura-de-texto`,
`am:lineas-de`, y `am:dibujar-tabla` reescrita alrededor):

1. **El ancho sale del contenido real.** Mientras la tabla se rellena se va
   guardando lo que cae en cada columna —cabecera, nombre de vivienda, cifra,
   «no se publica»— y al final el ancho es el de la cadena más larga de esa
   lista, por la altura del texto, más los dos márgenes. Se mide lo que se ha
   escrito, no lo que se preveía escribir.
2. **La altura del texto se lee, no se supone.** Se pide 0,25 m —2,5 mm de papel
   a 1:100, con la misma tabla de `INSUNITS` que ya escalaba el alto de fila— y
   después **se pregunta a la tabla con qué altura va a escribir de verdad**. Si
   el estilo de texto del plano tiene altura fija, esa gana y la de la celda se
   ignora: calcular el ancho con la altura pedida y escribir con otra mayor es
   precisamente la forma de volver a partir el texto. Se toma la mayor de las
   tres candidatas, porque pasarse de ancho deja la tabla holgada y quedarse
   corto la deja ilegible, y los dos errores no cuestan lo mismo.
3. **El alto de fila sale de la altura del texto**, no de una constante: dos
   veces esa altura en las filas normales, y las líneas que hagan falta en las
   dos que llevan frase entera (el motivo de bloqueo y la marca de borrador),
   que sí tienen que partirse.
4. **El título no puede partirse**: si las tres columnas juntas no le llegan, la
   diferencia se le da a la primera.

Un test nuevo, `test_el_ancho_de_columna_no_es_una_constante`, falla si alguien
vuelve a escribir un número a mano en un `vla-SetColumnWidth` o en un
`vla-SetRowHeight`. Es una regresión que no se ve leyendo el diff: se ve
abriendo AutoCAD.

Y el guardián de la marca de borrador se ha reescrito de paso. Buscaba la
palabra `if` en el texto que seguía a la leyenda, así que cualquier condición
vecina —aunque no la envolviera— lo hacía saltar; ahora mira **qué formas
envuelven de verdad** a su `vla-SetText` y exige que sea la última celda que se
escribe. Comprueba lo que decía comprobar.

### Lo que sigue sin ejecutarse, y hay que decirlo

- **La corrección de hoy.** No se ha vuelto a abrir AutoCAD. El ancho por
  contenido, `vla-SetTextHeight`, `HorzCellMargin`, `VertCellMargin` y
  `vla-SetRowHeight` **no se han ejecutado nunca**; las tres primeras van dentro
  de `vl-catch-all-apply` para que, si una versión no las tuviera, la tabla se
  dibuje con lo que traiga su estilo en vez de abortar el comando con el plano
  ya medido. Que en 2027 funcionen es documentación, no comprobación.
- **El camino de la vivienda bloqueada.** `V5.dxf` mide sus 3 viviendas de 3, y
  las dos celdas «no se publica», la fila fusionada del motivo y el total de
  planta ausente **no se han ejecutado ni una vez**. Es el trozo con más ramas
  del fichero y el que nadie ha visto funcionar. Se prueba con `ejemplo.dxf`.
- **Un plano cuyo estilo de texto tenga altura fija.** Es el caso normal en una
  plantilla de estudio, `am:altura-de-texto` está escrita para él, y ninguno de
  los dos planos de prueba lo tiene.
- **Dar la capa a mano.** El 2026-09-09 se aceptó la propuesta con INTRO.
- **Editar la tabla** como cualquier otra tabla de AutoCAD.
- **La pregunta del paso 9** —si esto le ahorra el copiado a mano o se lo cambia
  por revisar lo que ha escrito el programa— **no se le ha hecho a nadie**. Es
  lo que más vale de toda esta tarea y sigue pendiente.

### El dato que no cuadraba: no era una contradicción, eran dos ficheros

No hay contradicción. El plano que se abrió en AutoCAD **no es** el que tiene el
defecto: es el fixture anonimizado, y el proceso de anonimización lo arregló sin
querer. Medido con el criterio del propio parser (`_esta_cerrada` más
`_recuperar_cierre_por_geometria`), sobre la capa `00 areas`:

| Fichero | Polilíneas | Flag bien | **Flag mal puesto** |
|---|---|---|---|
| `_material/V5.dxf` (original) | 22 | 19 | **3** |
| `tests/fixtures/reales/planta_tres_viviendas.dxf` (derivado) | 22 | 22 | **0** |
| `_material/v2s.dxf` (original) | 10 | 8 | **2** |
| `tests/fixtures/reales/vivienda_con_solapes.dxf` (derivado) | 9 | 9 | **0** |
| `_material/ejemplo.dxf` (original, sin derivar) | 53 | 42 | **9** (y 2 abiertas de verdad) |

Las tres cifras del registro del 2026-09-09 —3 de 22, 2 de 10, 9 de 53— **son
correctas**, y lo son sobre los originales. El motivo de que el derivado no las
reproduzca está en el propio anonimizador y es estructural, no un descuido:
`scripts/derivar_fixture_anonimo.py` no copia entidades, **reconstruye** el plano
desde los polígonos ya leídos y escribe `msp.add_lwpolyline(..., close=True)`.
Un defecto que vive en el flag de una entidad no puede sobrevivir a un proceso
que no copia entidades. Es exactamente la propiedad que hace seguro al
anonimizador —lo que no se copia explícitamente no existe en la salida— y aquí
tiene el precio de que **el fixture es más limpio que la realidad**.

### Lo que eso implica: ningún fixture del repositorio ejercita ese camino

Comprobados los **26 DXF** de `tests/fixtures/`: ninguno tiene una sola
polilínea con `closed=False` y extremos coincidentes.
`dxf_tortura/04_polilinea_abierta.dxf` tiene 2 abiertas **de verdad**, que es el
camino contrario —el del descarte—, no el de la recuperación.

El camino de recuperación **sí está probado**, pero con planos sintéticos
construidos dentro del propio test (`test_cierre_recuperado.py`, 16 tests que
pasan). Los dos únicos tests que lo comprueban contra los planos reales se
**saltan**, incluso en esta máquina, donde los dos ficheros existen: el buscador
de `_ruta_proyecto_real` mira en `Proyectos/archmuse/` y en `~/Desktop`, y los
planos están en `Proyectos/archmuse/_material/`. Dos tests de regresión sobre
datos reales que nadie ha visto correr.

Y de ahí, lo que importa para la decisión que estaba en el aire:

- **La justificación para tocar el endpoint es real**, y ahora está medida otra
  vez: sobre `V5.dxf`, `ssget` seleccionaría **19** de 22 recintos y el lector de
  Python mide **22**. Sobre `v2s.dxf`, 8 contra 10. Eso es superficie que falta
  en la tabla de AutoCAD, y es lo que la propuesta —que el payload lleve el flag
  por recinto y decida `parser._esta_cerrada`— existe para arreglar.
- **Pero no había con qué probarlo.** Cualquier test de esa mejora, escrito
  sobre los fixtures de ayer, correría con todas las polilíneas bien flagueadas:
  **pasaría igual con la implementación correcta que con la incorrecta**. Un
  test que no puede distinguir las dos cosas no es una red, es un adorno. De ahí
  el fixture nuevo, abajo.
- **Y había un defecto ya presente que esos fixtures tapaban.**
  `geometria_recibida.payload_desde_dxf()` decía en su docstring que «simula lo
  que hace `ssget`» y filtraba con `parser._esta_cerrada` — es decir, **con la
  recuperación geométrica activada**, que es justo lo que `ssget` no sabe hacer.
  Sobre los fixtures la diferencia es cero y nadie se entera; sobre `V5.dxf` el
  payload simulado llevaba 22 recintos donde AutoCAD manda 19. El simulador era
  más listo que lo simulado, así que los 28 tests del endpoint comparaban el
  camino nuevo contra el viejo **sin la diferencia que separa a los dos**.
  Corregido; ver abajo.

**El endpoint sigue sin tocarse**, que era la condición: la mejora del payload
—que lleve el flag por recinto— no se ha hecho, sólo se ha dejado medida y con
un test que la reclama.

### Lo que se ha arreglado, una vez medido

**1. `payload_desde_dxf` mentía sobre lo que simulaba, y era lo más grave.** Su
docstring decía «simula lo que hace `ssget`» y filtraba con
`parser._esta_cerrada` **con la recuperación geométrica activada**, que es
exactamente lo que `ssget` no sabe hacer: en AutoCAD sólo se puede filtrar por
el bit del código 70. El simulador era más listo que lo simulado, así que los 28
tests que comparan `/api/medicion-geometria` contra `/api/medicion` comparaban
el camino nuevo con el viejo **sin la diferencia que separa a los dos**. Ahora
pasa `recuperar_geometria=False`.

Al hacerlo **no se puso rojo ningún test**, y eso no es tranquilizador: es la
demostración del problema. Sobre los fixtures del repositorio la corrección es
un no-op exacto, porque ninguno tiene el defecto. Estaban en verde por la razón
equivocada y habrían seguido en verde con la implementación mal. No se ha
relajado nada; se han añadido los tests que hacen visible la diferencia
(sección 8 de `test_medicion_geometria_endpoint.py`, 5 tests), y uno de ellos
deja escrito **por qué** la sección 1 puede estar en verde sin probar este
camino.

**2. `14_flag_de_cerrada_mal_puesto.dxf`**, en el banco de tortura. Siete
polilíneas: cuatro bien cerradas, dos cerradas de verdad pero declaradas
abiertas —hueco 0 y hueco del 0,6% de la diagonal, los dos patrones medidos en
`V5.dxf`— y una abierta de verdad, que tiene que seguir descartándose. Sobre él,
el motor mide **6 recintos y el cliente sólo puede mandar 4**: la carencia del
endpoint, por fin en un número que corre en la suite. El día que el payload lleve
el flag por recinto, ese test pasa a 6 y 6 y el cambio queda en el diff.

Construirlo enseñó algo que no se buscaba: **con una sola polilínea bien
flagueada, el plano entero deja de leerse**. `MINIMO_POLIGONOS_CAPA` son 3 y el
heurístico de detección de capa cuenta sólo por flag (`recuperar_geometria=False`,
deliberado y documentado), así que la capa deja de ser candidata y sale
`CapaIndeterminada`. En un plano donde el defecto afectara a la mayoría de los
recintos, esto no daría una medición corta: no daría ninguna. No se ha tocado
—es una decisión tomada y razonada en el parser— pero queda anotado.

**3. `_ruta_proyecto_real` ya mira en `_material/`.** Los dos tests de regresión
sobre `V5.dxf` y `v2s.dxf` llevaban saltándose **incluso en la máquina que tiene
los ficheros**, a un directorio de distancia. Ahora corren: 18 pasan en
`test_cierre_recuperado.py`, cero saltados. En CI seguirán saltándose, que es lo
correcto —son planos de cliente y no se versionan—, pero aquí ya no.

Total: **1.416 tests en verde**, 39 saltados (eran 1.406 y 41).

### DEUDA APUNTADA, NO HECHA: el anonimizador entrega planos más limpios que la realidad

`scripts/derivar_fixture_anonimo.py` no copia entidades: lee el plano con
`parser.leer_plano`, se queda con los polígonos ya interpretados y escribe un DXF
nuevo con `msp.add_lwpolyline(..., close=True)`. Esa propiedad es justo lo que lo
hace seguro —lo que no se copia explícitamente no existe en la salida, y por eso
no se escapó el `$LASTSAVEDBY` del original, con un nombre de pila— y tiene un precio que
hasta hoy nadie había pagado en voz alta: **el fixture no hereda los defectos del
plano del que sale**. El flag de cerrada es el caso que se ha medido (3 de 22
pasan a 0 de 22), pero no hay motivo para pensar que sea el único: todo lo que
viva en un atributo de entidad y no en la geometría desaparece igual.

La consecuencia es que los dos ficheros que el MANIFIESTO presenta como «derivados
de planos reales» son, para todo lo que no sea geometría, **planos sintéticos**.
Miden lo mismo que sus originales, que es lo que se comprobó al derivarlos y es
verdad; no se parecen a ellos en lo demás, y eso no se comprobó porque nadie se
lo había preguntado.

**La opción de arreglarlo —que el anonimizador conserve el flag original— está
descartada por ahora, a propósito.** Implica regenerar los dos fixtures (dos
ficheros commiteados que cambian), volver a pasar `auditar_fixture_anonimo.py`,
re-verificar pieza a pieza las invariantes del MANIFIESTO, y aceptar que
cualquier test que cuente descartes o warnings puede moverse. Es un cambio de
política del anonimizador, no un fixture más, y se decide con calma. El fixture
sintético del punto 2 cubre mientras tanto lo que bloqueaba.

### El primer paso al volver a abrir AutoCAD

1. Servidor levantado (`python app.py`), `V5.dxf` abierto.
2. `APPLOAD` de nuevo: **el fichero ha cambiado**, y la versión que cargó el
   2026-09-09 ya no es la que hay en disco. Vuelve a ser el paso 1 del
   checklist, con su misma probabilidad de fallar por un paréntesis.
3. `ARCHMUSE`, y mirar **sólo el paso 8**: que la cabecera larga de la tercera
   columna se lea, que ninguna cifra se parta, que la marca de borrador ocupe
   dos líneas y no doce, y que la tabla tenga un tamaño sensato al lado de la
   planta. Si sale un sello diminuto o un cartel enorme, el problema está en
   `am:escala-de-dibujo` y en el `INSUNITS` de ese plano, no en el ancho.
4. Y después, `ejemplo.dxf`, que es el que trae la vivienda bloqueada.

---

## 2026-09-09 · `archmuse.lsp`, escrito sin AutoCAD y con lo que no se ha podido comprobar declarado

Tareas 5 y 6 del PRD de AutoCAD, con el trial instalándose. **No se ha tocado el
motor, ni el endpoint, ni el registro de capacidades.**

### Tres hallazgos que cambiaron el script antes de escribirlo

1. **`read` no sirve para leer la respuesta.** Tiene un tope de unos 2.300
   caracteres, y la s-expresión de la planta de tres viviendas ocupa **6.564**
   (medido, no supuesto); la de seis pasa de 13.000. El script extrae los cuatro
   campos que la tabla necesita con búsqueda de cadenas — no construye listas y
   no es un parser.
2. **`ssget` no puede seleccionar lo que el navegador sí mide.** Sólo sabe
   filtrar por el bit de «cerrada» del código 70, y el lector de Python además
   recupera las polilíneas con el flag mal puesto que cierran geométricamente
   (tolerancia del 1% de su diagonal). En los planos reales eso es **3 de 22 en
   `V5.dxf`, 2 de 10 en `v2s.dxf` y 9 de 53 en `ejemplo.dxf` — hasta un 17%**.
   No se ha replicado esa tolerancia en LISP: es criterio del parser y duplicarlo
   repetiría el error que `D-7` prohíbe. El comando **cuenta las que deja fuera y
   lo anuncia antes de enviar**, con la recomendación de subir el mismo plano a
   `/medir` para comparar.
3. **Un MTEXT de más de 250 caracteres parte su contenido** en códigos 3 más el
   1 final. Leer sólo el 1 devolvería la cola del rótulo. Se concatenan.

**La solución buena del punto 2 es de servidor** y no se ha hecho porque tocaría
el endpoint: que el payload lleve el flag de cerrada por recinto y decida
`parser._esta_cerrada`, igual que en el camino web. Es el primer candidato de la
próxima sesión de servidor, y las cifras de arriba son su justificación.

### Lo que sí se ha verificado, sin AutoCAD

`tests/test_archmuse_lsp.py`, 10 comprobaciones. **Encontró un fallo real**: un
`setq` con un paréntesis de más que habría hecho fallar `APPLOAD` el primer día
del trial, que es exactamente el escenario que el checklist existe para evitar.
Comprueba paréntesis y comillas con un lector que distingue cadena de comentario;
que ningún `defun` esté anidado; que **cada función llamada** sea una primitiva
contrastada contra la referencia de Autodesk o esté definida en el fichero (una
errata tipo `vla-SetTex` no se ve leyendo); que la marca de `C3` sea literalmente
la misma cadena que `analyzer/marca_borrador.LEYENDA` y que se escriba sin
condición; que no se llame a `read`; y que no haya ningún cálculo de distancia
entre texto y polígono, que sería el criterio de rótulo reimplementado.

Contrastado contra documentación oficial, función a función: el filtro bit a bit
de `ssget` es `(-4 . "&")` y no `&=`; `vla-AddTable` es
`(InsertionPoint NumRows NumColumns RowHeight ColWidth)`; `MergeCells` es
`(MinRow MaxRow MinColumn MaxColumn)`; `vlax-create-object` no existe en LT.

### Lo que NO se ha podido comprobar, y no se simula

**Nada del script se ha ejecutado nunca.** El fichero lo dice en su cabecera y
hay un test que lo vigila; el día que corra, ese test se cambia a mano y el
cambio queda en el diff. En concreto, sigue sin comprobarse:

- Que `APPLOAD` lo cargue. Es lo más probable que falle, y fallar ahí **no dice
  nada** sobre si el flujo sirve.
- Que el objeto COM se cree y que la petición salga (antivirus, cortafuegos).
- **La codificación.** El servidor manda UTF-8 y AutoCAD en Windows lee ANSI.
  Los motivos llevan tildes y comillas angulares: es el fallo más probable
  después de la sintaxis, y es de codificación, no del flujo.
- Que `vla-AddTable` acepte el número de filas calculado, y que `vla-SetText`
  escriba en la fila de título y en las celdas fusionadas como se espera.
- Que `ssget` coja el mismo número de recintos que el lector de Python en un
  plano cualquiera. Sólo se ha razonado sobre los tres planos reales.
- El rendimiento con un plano grande de verdad, y el comportamiento de
  `SetTimeouts` (puesto a 5 minutos de recepción a propósito: el valor por
  defecto de WinHttp son 30 s y una planta de seis viviendas tarda unos 12).
- Nada en Mac. El COM de Windows no existe allí.

Un *mock* de AutoCAD no se ha escrito a propósito: daría confianza falsa sobre
lo único que este prototipo existe para averiguar.

### El primer paso al volver (el equipo se reinicia para terminar de instalar AutoCAD)

Literalmente esto, en este orden, y nada más hasta que los tres pasen:

1. **Levantar el servidor:** `python app.py`, y comprobar que
   `http://127.0.0.1:5000/medir` contesta. Sin él, el comando no tiene a quién
   preguntar y el fallo parecería del script.
2. **`APPLOAD`** → `autocad/archmuse.lsp`. Si sale una ventana de error, es un
   paréntesis y **no dice nada sobre si el flujo sirve** — anota el número de
   línea y sigue el paso 1 del checklist.
3. **`ARCHMUSE`** en la línea de comandos, con `_material/ejemplo.dxf` abierto.

Y a partir de ahí, `docs/design/checklist-primera-prueba-autocad.md` **desde el
paso 0**, que se lee entero antes de tocar nada. Dos cosas que conviene tener
presentes al llegar al paso 3: el recuento de polilíneas puede no cuadrar con el
del navegador, y la primera sospecha son las que llevan el flag de cerrada mal
puesto — el propio comando dice cuántas deja fuera antes de enviar, así que si
ese número explica la diferencia no hay nada que depurar. Y en el paso 5, lo que
hay que contrastar son **dos** cifras por vivienda: si aparece una que sume
interior y exterior, eso es el fallo.

---

## 2026-09-08 · Dos superficies donde había una, y dos planos reales que ya viajan con el repositorio

**Encargo de Pablo**, en orden estricto: cerrar lo del 3 de septiembre sin
commitear; los cambios de criterio validados con el arquitecto; la demo del
`ACAD_TABLE`; y sólo si sobraba tiempo, el endpoint de AutoCAD.

### El criterio, que es lo que de verdad cambia

`total_util_m2` **ha desaparecido del producto entero**. En su lugar,
`util_interior_m2` y `util_exterior_m2`, que no se suman. Escrito como criterio
firmado en `docs/design/2026-09-08-criterios-firmados-de-medicion.md` (`C-1`),
no como detalle de implementación: el cómputo de terrazas y tendederos lo decide
el técnico que firma, y una cifra que lo resolvía sola viajaba hasta la memoria
justificativa.

Cifras antes y después, sobre los tres planos reales:

| Plano | Antes (`total_util_m2`) | Después (interior · exterior) |
|---|---|---|
| `V5.dxf` VT1/3 | 66,32 | **58,78 · 7,54** |
| `V5.dxf` VT2/2 | 58,44 | **50,97 · 7,47** |
| `V5.dxf` VT3/3 | 66,56 | **59,11 · 7,45** |
| `V5.dxf` planta | 191,32 | **168,86 · 22,46** |
| `ejemplo.dxf` planta | sin total (falta VT6/2) | sin cifras, mismo motivo |
| `v2s.dxf` VT1/3 | sin total (7,08 m² solapados) | sin cifras, mismo motivo |

Los 22,46 m² de exterior de `V5` son los que antes iban dentro de los 191,32
como si fueran superficie interior: un **11,7 %** del «total útil» de esa planta
era terraza computando al 100 %.

**`C-2`, criterio nuevo propuesto al implementar y aprobado por Pablo:** un
impedimento bloquea **las dos** cifras, no sólo su suma. Antes los parciales se
publicaban junto a un total ausente porque eran su desglose; al pasar a ser
ellos el resultado, publicarlos con un solape abierto sería el «número que puede
estar mal» que la regla dura existe para no dar — un solape puede caer dentro de
lo interior, dentro de lo exterior o a caballo.

**14 ficheros de producto tocados**, ninguno con el campo viejo conviviendo:
modelo, acta (dos hechos con procedencia en vez de uno), PDF de medición,
memoria justificativa, acta legible, API, `/medir` y el CLI. Interior y exterior
se suman **en un solo punto de todo el repositorio**: la verificación que
comprueba que entre las dos no se ha perdido ninguna pieza.

**La celda «TOTAL S. ÚTIL» del `ACAD_TABLE`** sale `N/D` **con su motivo
escrito**, no en blanco. En blanco se lee como «ArchMuse no ha sabido»; con
motivo se lee como lo que es, que ha decidido no decidir por el arquitecto.

### Dos planos reales dentro del repositorio, y por qué no son los planos

Pablo pidió guardar `V5.dxf` en `tests/fixtures/reales/`. **Se paró antes de
hacerlo**: el repositorio es público y el `.gitignore` prohíbe los DXF con su
motivo escrito («una fuga de datos que el historial no olvida»), con la única
excepción `!tests/fixtures/**/*.dxf` — o sea que la carpeta pedida era
justamente donde la red de seguridad no salta. Pablo eligió la opción
anonimizada.

**No se anonimiza borrando: se reconstruye.** `scripts/derivar_fixture_anonimo.py`
lee el plano con el mismo `parser.leer_plano` del producto, se queda con los
polígonos y los rótulos, y escribe un DXF nuevo desde cero. Lo que no se copia
no existe en la salida porque nunca llegó a existir.

**La diferencia no era teórica:** el original de `V5.dxf` traía en
`$LASTSAVEDBY` el nombre de pila de quien lo guardó,
que ningún borrado de capas habría quitado. En el derivado esa variable vale
`ezdxf` y los dos GUID del documento son nuevos.

`scripts/auditar_fixture_anonimo.py` audita el resultado como si viniera de un
desconocido: cabecera entera, capas apagadas y congeladas, bloques insertados o
no, estilos, todo el texto de todos los layouts y bloques, `XDATA`, diccionarios
y propiedades. Lo que queda son rótulos de estancia y códigos `VT<n>/<m>`.

- `planta_tres_viviendas.dxf` — de 19,5 MB a **33 KB**. La planta que sí se mide.
- `vivienda_con_solapes.dxf` — de 19,1 MB a **24 KB**. La rama bloqueada.

Los dos miden **exactamente** lo mismo que sus originales, comprobado al
derivarlos. Y `tests/test_fixtures_reales.py` añade un guardián de la fuga, no
sólo de la medición: se pone rojo si alguien regenera un fixture desde un plano
de cliente sin pasar por el script.

Hasta hoy la regresión contra plano real dependía de `ARCHMUSE_DXF_PLANTA`: en
cualquier máquina que no fuera la de Pablo **se saltaba en silencio**. Ahora
corre siempre, también en CI.

### La demo del punto 2

`_material/demo/v2s_ArchMuse_cuadro_2026-09-08.dxf`: el DXF del arquitecto con
su propio `ACAD_TABLE` relleno, con las dos sumas nuevas, con la marca de
borrador de `C3` estampada, y con el original intacto (sello SHA-256
recalculado). `TOTAL SUP.UTIL INTERIOR: 58,78 m²`; `TOTAL S. ÚTIL: N/D` con su
motivo. **Fuera del repositorio**, por lo mismo que los fixtures.

### El punto 3, hecho después: la puerta para AutoCAD, sin `.lsp`

Tareas 1-4 y 7-8 del PRD aprobado. **Sin capacidades nuevas y sin tocar el
guardián de `C4`**, que era la condición.

`/api/medicion-geometria` recibe JSON con las polilíneas y los textos en crudo,
lo materializa en un DXF mínimo en el temporal y entra por
`_ejecutar_medicion_de_planta` — **la misma función** que usa `/api/medicion`.
Toda la costura es que esa función sólo le pide a lo que recibe un método
`save(ruta)`: `SubidaMaterializada` se lo da, y por eso no hay que tocar ni una
línea de la Skill, la capacidad, el acta, el PDF ni el motor.

- **`C1` corrido de verdad, que era el criterio de éxito real** (§13.1 del PRD):
  **cero líneas del motor reescritas** para servir a un cliente que no es la web.
- El cliente **no empareja rótulos con recintos**: manda las dos cosas sueltas y
  lo resuelve `parser.match_label_to_room`, donde ya estaba probado (`D-7`).
- La escala la sigue decidiendo `analyzer/escala.py`. Comprobado: con un
  `$INSUNITS` que miente (milímetros sobre geometría en metros), no mide — hace
  la pregunta de siempre.
- Nada se cae en silencio: una polilínea de dos vértices no se descarta callando,
  sale en `geometria_descartada` con su motivo y su handle.
- `?formato=lisp` devuelve lo mismo como s-expresión. AutoLISP no trae parser
  JSON, y escribir uno en el cliente serían ~150 líneas imposibles de probar sin
  AutoCAD: diez de Python con tests las sustituyen. Una superficie que no se
  publica sale como `nil`, que es exactamente lo que significa.

**Los payloads de los tests no están escritos a mano**: se derivan de los dos
fixtures anónimos con `payload_desde_dxf()`, que simula lo que hace `ssget`. Por
eso la comprobación central significa algo — las dos rutas dan **exactamente** la
misma medición sobre los dos planos, al céntimo, vivienda a vivienda y pieza a
pieza. Si eso se pone rojo, hay un segundo motor de medición y no se ajusta la
tolerancia: se busca por qué.

**Lo que sigue sin poderse verificar, y no se simula.** Todo `autocad/archmuse.lsp`,
que ni siquiera está escrito: tareas 5 y 6, para el día del trial. Un *mock* de
AutoCAD daría confianza falsa sobre lo único que el prototipo existe para
averiguar. El checklist de `docs/design/checklist-primera-prueba-autocad.md` ya
está escrito y separa, prueba a prueba, lo que sería fallo del flujo de lo que
sería fallo del lenguaje.

### Estado al cerrar la sesión del 2026-09-08

**Cerrado:** el punto 0 (el trabajo del 3 de septiembre, commiteado), el 1a (las
dos superficies), el 2 (la demo del `ACAD_TABLE`) y el 3 (el endpoint de
geometría con sus tests de integración). **Cinco commits en la rama
`medicion/totales-y-herramienta-medir`**, `main` intacto, nada empujado.
Suite: **1395 pasan, 41 se saltan**.

**Bloqueado, y por qué:**

| Qué | Por qué | Qué lo desbloquea |
|---|---|---|
| **1b** — el fallo de duplicación del «Tendedero» | El DXF donde se vio no está disponible. Un test escrito contra un fallo que nadie ha visto reproduce lo que uno imagina, no lo que pasó | Que Pablo encuentre el fichero |
| **1c** — el «Baño» que cae en `sin_clasificar` | Lo mismo. Hay dos sospechosos ya localizados: el plural «BAÑOS», que no casa con `BANO`, y que el rótulo no se haya asociado al recinto — en ese caso el arreglo está en otro sitio | El mismo fichero |
| **`autocad/archmuse.lsp`** (tareas 5 y 6 del PRD) | No hay licencia de AutoCAD. No se simula: un *mock* daría confianza falsa sobre lo único que el prototipo existe para averiguar | Activar el trial, **de AutoCAD completo, nunca LT** |

**El primer paso de la próxima sesión** depende de qué haya llegado, y en este
orden:

1. **Si está el DXF que falló:** 1b y 1c, con el test que reproduce cada fallo
   escrito **antes** del arreglo, y el fichero derivado y auditado con
   `scripts/derivar_fixture_anonimo.py` antes de que entre al repositorio.
2. **Si está el trial de AutoCAD:** `archmuse.lsp`, con
   `docs/design/checklist-primera-prueba-autocad.md` abierto al lado desde el
   paso 0. Está escrito para que no se gasten días de licencia improvisando.
3. **Si no está ninguno de los dos:** las cuatro preguntas de criterio que
   siguen abiertas, empezando por el **vocabulario de rótulos** — hoy son ocho
   familias y todo lo que no entra bloquea la vivienda entera, que es el fallo
   más probable sobre un plano ajeno.

**Y una decisión de Pablo pendiente que no es técnica:** qué hacer con la rama.
Los cinco commits están sin empujar y `main` sigue en `faff391`.

### Qué NO se ha hecho, y por qué

- **Los puntos 1b y 1c siguen bloqueados**: el fallo de duplicación del
  «Tendedero» y el del «Baño» en `sin_clasificar` se detectaron sobre un DXF que
  todavía no está disponible. No se han empezado a ciegas, por orden expresa de
  Pablo y porque un test escrito contra un fallo que nadie ha visto reproduce lo
  que uno imagina, no lo que pasó.
- **El punto 3** (endpoint de geometría del PRD de AutoCAD) no se ha tocado: iba
  detrás de todo lo demás.
- El segundo fixture se deriva de `v2s`, **no** del DXF que falló. Cubre la rama
  bloqueada, que la planta de tres viviendas no ejercita, pero no sustituye al
  que hará falta para 1b y 1c.

### Validación

Suite completa en verde. Los dos planos reales, ya como fixtures, con sus cifras
escritas a mano en `tests/test_fixtures_reales.py`.

---

## 2026-09-03 · Los totales de superficie, y la herramienta mínima

**Encargo de Pablo**: un experimento de validación de una semana. Un arquitecto
entrega un DXF y recibe un informe de medición de superficies que le sirva.
Nada más — sin XLSX, sin exportación DXF, sin IFC, sin normativa, sin
autenticación, sin dashboard.

### Auditoría: había tres caminos, no uno

1. `/api/analizar` → `evaluator.evaluate_advanced` → SPA. Las 38 reglas, el
   visor, la IA. Su cifra por vivienda (`superficie_total_m2`) es la suma de
   estancias, no una medición auditada.
2. **La Skill `superficies.medicion_de_planta`** (`analyzer/medicion.py` +
   `medicion_pdf.py`): DXF → parser → medición pieza a pieza → PDF con
   procedencia. Multi-vivienda, con la regla dura de los totales y auditoría de
   solapes y de reparto. **Éste es el camino bueno, y ya existía.**
3. `superficies.cuadro_de_vivienda`: rellena el `ACAD_TABLE` del propio DXF.
   Sólo admite un DXF de una vivienda, y escribe en el plano — fuera del
   alcance de este experimento.

No se ha construido ningún motor de medición nuevo. Lo único que faltaba era la
puerta: `_ejecutar_medicion_de_planta` escribía el PDF en un temporal y lo
borraba, así que sólo se podía obtener por CLI.

### Los totales que estaban mal

- **`agente/skills/superficies.py::_suma_cuadra` sumaba magnitudes que no se
  acumulan.** Decidía qué celdas del cuadro sumar por el nombre («si contiene
  *total*, no lo sumes»), lo que deja fuera los totales y deja dentro las dos
  celdas de **superficie construida** y el **`NUMERO UDS`**. Con el cuadro de
  `ejemplo.dxf` («NUMERO UDS: 8») sumaba ocho metros cuadrados inexistentes, y
  en cuanto el arquitecto declaraba la construida —el flujo que las
  `Solicitud` numéricas le piden— le sumaba encima una vivienda medida por otro
  criterio. Todo eso se cruzaba contra la superficie ÚTIL medida.
  Su parseo, además, era propio y más laxo que el del cuadro: `"8"` colaba como
  8 m² y `"21.90m2"` —el formato real de las celdas de `ejemplo.dxf`— no colaba
  y se descartaba **en silencio**, dejando la suma corta sin decirlo.
- **`plano.superficie_util_total_m2` publicaba un total al que le faltaba una
  vivienda.** Sumaba sólo las medibles: sobre `ejemplo.dxf`, 295,10 m² con
  VT6/2 (~66 m²) fuera y sin declararlo. La regla que `analyzer/medicion.py` ya
  aplica vivienda a vivienda no se aplicaba un nivel más arriba.
- **`plano.leer_dxf` llamaba `superficie_util_total_m2` a una suma cruda de
  áreas**, con los solapes contados dos veces y los polígonos sin rótulo
  dentro. Dos magnitudes distintas con el mismo nombre en el mismo registro.
- **La SPA usaba superficie útil como superficie construida.**
  `superficieConstruidaTotal()` sumaba `superficie_total_m2` de las viviendas
  cuando no había urbanismo declarado. Falseaba el PEM, la repercusión de suelo
  y el «Ratio de Eficiencia Útil/Construida», que salía ~0,9 y se pintaba sin
  badge de estimación por estar declarado como el único dato REAL del bloque.

### Qué se hizo

- **Catálogo cerrado de magnitudes del cuadro** en `analyzer/cuadro_superficies.py`
  (`CAMPOS_SUMANDOS_UTIL`, `CAMPOS_TOTAL_UTIL`, `CAMPOS_CONSTRUIDA`,
  `CAMPOS_SIN_SUPERFICIE`), con un test que falla si un campo nuevo no queda
  clasificado. De paso deduplica las dos listas de componentes que la cascada
  de totales tenía copiadas.
- **`superficie_en_m2` pública**, el parseo estricto único. Un sumando que no
  se puede leer ya no se salta: la comprobación se declara «no se ha podido
  comprobar», que es el tercer estado que ya existía.
- **Sin total del plano si falta una vivienda**, con el nombre de la que falta.
- **Renombrado** `leer_dxf.superficie_util_total_m2` →
  `suma_de_areas_de_recintos_m2` (golden G11 recapturado a mano: mismo valor).
- **`superficieConstruidaTotal()` devuelve `null`** sin dato declarado. El
  panel ya pintaba `--` para todo lo que falta.
- **`GET /medir` + `POST /api/medicion`**: la herramienta mínima. Un fichero
  HTML sin dependencias y un endpoint que ejecuta la Skill **una vez** y
  devuelve la medición y el PDF (base64, 11 KB sobre el plano de seis
  viviendas) en la misma respuesta. Nada se guarda en el servidor.
- **Las dos listas de «lo que no se ha comprobado», separadas**: los hallazgos
  de ESTE plano abiertos; las 17 limitaciones genéricas plegadas. Mezcladas,
  el único hallazgo real quedaba en la línea 9 de un muro.

### Qué se dejó fuera, a propósito

- No se ha tocado `/api/analizar`, `evaluator.py`, la SPA (salvo el `null` de
  arriba) ni `superficies.cuadro_de_vivienda`.
- **La superficie construida sigue sin calcularse**, y ahora se declara en el
  payload y en la página con su motivo. No es un hueco pendiente: un DXF de
  recintos no trae espesores de muro.
- La página `/medir` no contesta las preguntas del plano por el arquitecto:
  las enseña y le da los dos campos (capa, unidad) para contestarlas.

### Segunda vuelta (mismo día): el total de la planta

Pablo, al revisar: un cuadro de superficies sin total de planta obliga al
arquitecto a sumar la columna a mano, que es el trabajo que viene a delegar.

La regla vivía a medias: `analyzer/medicion.py` la aplicaba por vivienda y
nadie la aplicaba a la planta. Ahora `Medicion` tiene `total_util_m2`,
`impedimentos` y `advertencias`, con el mismo criterio que una vivienda —una
planta a la que le falta una vivienda no se totaliza— y se publica como hecho
con procedencia (`medicion.total_util_m2`), no se suma en la capa de
presentación. Llega a la cabecera de `/medir` y al PDF:

- **Con total**: la cifra con el recuento pegado («90,00 m² · 2 de 2 viviendas»).
  Un total sin saber sobre cuántas viviendas se ha calculado no se puede juzgar.
- **Sin total**: «Sin total de planta» con la vivienda que lo bloquea **en la
  cabecera**, no sólo abajo en los hallazgos.
- **Tercer estado, y no lo pidió nadie pero ocurre en los dos planos reales**:
  un rótulo «VT…» sin ningún recinto asignado no bloquea el total (podría ser
  una etiqueta de otra planta o de una leyenda) pero es la cifra del total la
  que podría estar corta, así que la advertencia viaja **pegada al número**.

### La superficie construida: cerrado con medida, no con suposición

Se miró antes de dar por imposible el cálculo. Los tres planos reales
(`ejemplo`, `v2s`, `V5`) traen una capa `00 MURO`, y en los tres contiene
**los mismos 9 hatches de 0,36 m², 2,54 m² en total** — un bloque de detalle
copiado, no los muros del proyecto. Contra 437,38 m² de recintos en
`ejemplo.dxf`. No hay geometría de muro de la que derivar nada.

Lo que sí existe y no está conectado a `/medir`: el contrato `AM_*`
(`AM_CONS_CER`), que `parser.py` y `evaluator.asignar_envolvente_cerrada` ya
leen y que hoy sólo consume `/api/analizar`. Comprobado sobre un DXF de prueba:
útil 32,00 m² / construida 38,72 m² → ratio 0,826. Es lectura de una envolvente
dibujada, no una aproximación.

### Exactitud: lo que sí está contrastado, y contra qué

Hasta aquí todo lo verificado era consistencia interna. Faltaba una comparación
independiente, y estaba disponible sin esperar a ningún encargo: `ejemplo.dxf`
trae el cuadro que el arquitecto rellenó a mano en su `ACAD_TABLE`, escrito en
el fichero antes de que ArchMuse existiera. Contrastado pieza a pieza contra la
medición geométrica, **sin redondear**, sobre VT1/3:

| pieza | declarado | ArchMuse (crudo) | residuo |
|---|---|---|---|
| salón/cocina | 21,90 | 21,900338005 | +0,000338 |
| dormitorio 1 | 12,72 | 12,724520145 | +0,004520 |
| dormitorio 2 | 8,48 | 8,482579576 | +0,002580 |
| dormitorio 3 | 8,53 | 8,534461408 | +0,004461 |
| baño | 4,01 | 4,006022041 | −0,003978 |
| aseo | 3,14 | 3,135805602 | −0,004194 |
| tendedero | 4,22 | 4,220139826 | +0,000140 |
| terraza 1 | 3,32 | 3,324818339 | +0,004818 |

Las ocho por debajo del umbral de redondeo (0,005): la medición cruda redondea
exactamente a lo que el arquitecto firmó. Los residuos son su redondeo, no
error de ArchMuse.

**Lo que NO prueba**, y es la limitación que importa: es el mismo dibujo, así
que acredita que ArchMuse lee la geometría como la lee AutoCAD, no que el
**criterio** (qué entra en útil, dónde se mide el borde, qué cuenta como
exterior) sea el que firmaría un colegiado. Eso sólo lo contrasta el cuadro de
la memoria, hecho con un criterio y posiblemente distinto. Es una muestra: las
otras dos plantas no traen cuadro relleno.

La segunda pata de exactitud ya existía y estaba mal contada en este documento:
los 11 `tests/fixtures/dxf_plausibles/` tienen **verdad conocida por
construcción** (36,00 m², tolerancia 0,01) y cubren robustez de lectura —
milímetros con `$INSUNITS`, rótulos fuera con directriz, muros de doble línea,
capas de ruido, capa opaca, cinco nomenclaturas de capa.

### Defecto encontrado al cerrar, sin corregir

`_celda_total` nunca mira `celda.texto_actual`. Un cuadro que declara «TOTAL
SUP.UTIL INTERIOR: 70,00 m²» sobre piezas que miden 36,00 recibe 36,00 marcado
como CALCULADO, se sobrescribe la cifra del arquitecto y **la discrepancia de
34 m² no se declara**. Rompe la regla 4 del módulo y la regla 5 del §4 del
`CLAUDE.md`, y pierde justo lo que el §1 llama la razón por la que alguien
paga. No lo dispara ningún plano del banco (en `ejemplo.dxf` los totales están
vacíos); lo dispara el plano de un arquitecto con la memoria redactada. Anotado
en el docstring de la función, con el arreglo indicado (`_con_conflicto_o`).

### Validación

Suite completa: 1350 pasan, 41 se saltan (era 1321/41). Ocho DXF por el
endpoint real: `ejemplo.dxf` (6 viviendas, 5 con total, 295,11 m², 10,3 s),
`v2s.dxf`, `V5.dxf` (3/3, 191,32 m²), dos sintéticos, un fixture y dos planos
ajenos que devuelven la pregunta de capa/unidad en vez de un número. Aritmética
comprobada a mano sobre `ejemplo.dxf`: VT1/3 = 58,78 + 7,54 = 66,32 m².

---

## 2026-08-23 · El acta abre con un veredicto, y el motivo deja de repetirse

**Defecto encontrado por Pablo**, probando la revisión de coherencia con un
plano ajeno (`cs_01.dxf`): el mismo párrafo pegado cinco o seis veces
seguidas, un muro de texto, y ninguna línea que dijera lo esencial.

### La causa, medida y no supuesta

Ocho copias del mismo texto en el objeto de resultado, por tres eslabones:

1. `agente/herramientas/plano.py::_fallo_de_lectura` devolvía
   `{"detalle": str(exc), "pregunta": str(exc)}` — **el mismo texto en los dos
   campos**, rompiendo la convención que el resto del repositorio ya seguía
   (`detalle` = qué ha pasado; `pregunta` = qué hay que contestar). Copias 1-2.
   `agente/herramientas/coherencia.py` tenía además **su propia copia** de esa
   cadena de `isinstance`, en vez de importarla.
2. `agente/skills/coherencia.py::_sin_hacer` pasaba ese `detalle` a
   `sin_producir(PRODUCE, ...)`, y `PRODUCE` tiene **6 entradas**: cada
   afirmación no producida nacía con el párrafo entero como motivo. Copias
   3-8. `agente/skills/medicion.py` igual, con 5.
3. `analyzer/acta_legible.py::_seccion_datos` pintaba una línea por dato, sin
   agrupar. Ahí se hacían visibles.

**Medido antes de tocar nada**, sobre los ficheros reales: motivo de 326
caracteres, repetido **7 veces** (coherencia) y **6** (medición) en el HTML;
`cs_05.dxf` idéntico. Los planos buenos (`V5`, `v2s`) daban 0 repeticiones —
el defecto vivía sólo en el camino de fallo. Después: motivo de 50 caracteres
y el texto largo **una sola vez**.

### Qué se hizo

- **`detalle` corto, `pregunta` larga.** Tabla `_MOTIVO_CORTO` por código en
  `plano.py`. `coherencia.py` deja de duplicar la lógica y **importa**
  `_fallo_de_lectura` — mantener dos copias fue lo que obligó a arreglar lo
  mismo dos veces.
- **Agrupación por motivo idéntico**, con el mismo criterio exacto (no
  aproximado) que `_seccion_limitaciones` usa desde el 21-08, en los dos
  soportes de texto: `acta_legible._seccion_datos` (web/PDF) y
  `agente/acta.py::a_texto` (CLI). Seis campos con el mismo motivo son una
  frase que dice cuántos son, no seis frases.
- **Veredicto en una línea** (`acta_legible._veredicto`), y los tres soportes
  salen de él para que no digan cosas distintas: «Plano revisado · 22
  recintos, 3 hallazgos», «Planta medida · 22 piezas en 3 viviendas», «Este
  plano no trae las estancias como polilíneas cerradas». **No calcula nada**:
  sólo lee cifras ya establecidas.
- **Plegado**: la explicación visible son 2-3 frases; la enumeración de capas
  candidatas y las dos secciones largas van detrás de `<details>`.
  `_partir_explicacion` parte el mensaje del parser **sin perder un carácter**
  (test propio).

### Decisiones

- **El titular nombra el hecho, no califica.** «Este plano no trae las
  estancias como polilíneas cerradas» y no «plano incompleto»: calificar el
  trabajo de otro arquitecto es justo lo que `D-7` prohíbe. Decisión de Pablo.
- **Fallback honesto**: un código sin titular propio no se improvisa — sale
  «No se ha podido completar la revisión» y el mensaje **dice qué código ha
  llegado**.
- **`PRODUCE` y el contrato de `Afirmacion` no se tocan.** Cada afirmación
  sigue llevando su motivo; lo que cambia es que el motivo es corto, que es lo
  que siempre debió ser.

### Qué se dejó fuera

- **El PDF no se tocó y no hacía falta**: `analyzer/coherencia_pdf.py` no pasa
  por `acta_legible`. El riesgo que el plan anotaba sobre este punto era
  parcialmente falso; verificado comparando el PDF de `V5` antes y después
  (3701 bytes, idéntico).
- El fallo preexistente de `tests/test_conversacion_menus_barra_entrada.py::test_el_cuerpo_de_la_respuesta_sigue_intacto`
  (sobre `static/app.js`, que no se ha tocado). Comprobado que **también falla
  en HEAD limpio**: no es de este cambio y queda para quien lo abriera.

### Verificación

`tests/test_veredicto_acta.py` — 12 casos nuevos, incluidos los tres que
congelan la no-repetición. Suite completa y los tres soportes (web, PDF, CLI)
comprobados. Guardián de regresión: las actas normalizadas de `V5` y `v2s`
salen **byte a byte idénticas** a las de antes del cambio.

### La congelación: excepción autorizada, y qué queda pendiente de comprobar

`analyzer/` está congelado hasta el jueves 28
(`docs/prd/2026-08-22-contraste-superficies-memoria-vs-plano.md` §R-3, por
competencia de tiempo con la validación del corpus del 25-26), y
`analyzer/acta_legible.py` cae dentro. **Pablo autorizó la excepción el
2026-08-23**: hace falta para una demo y el trabajo es del día 23, así que no
compite con lo que la congelación protege.

**Pendiente, para cuando se haga la validación del corpus (25-26):**
comprobar que este cambio no la afecta. El guardián ya está capturado y es
suficiente — si las actas normalizadas de `V5` y `v2s` siguen saliendo
idénticas, el cambio es ortogonal y no hay nada que revisar. El capturador
vive fuera del repositorio (scratchpad de la sesión,
`capturar_linea_base.py`): fija `emitida_en` y `ejecucion_id`, y **neutraliza
`momento`, `sello_del_paso` y `sello`**, que cambian en cada ejecución aunque
la entrada sea idéntica — `emitida_en` no controla el `momento` de cada paso,
así que comparar sellos crudos no dice nada.

*(Anotado también en la cabecera del PRD del 22-08, que es donde se mirará
durante la validación.)*

---

## 2026-08-21 · Curación y firma humana del corpus DB-SUA

Ver `docs/prd/2026-08-21-curacion-y-firma-del-corpus-db-sua.md` (**Cerrado**,
Aprobado por Pablo el mismo día). No es una reversión de la decisión de la
mañana de no contratar curador colegiado externo: es Pablo mismo aprobando o
rechazando explícitamente cada regla, formalizado en el estado `FIRMADA` que
el esquema ya reservaba desde el cierre del Prompt 2.

**Hecho:**
- `scripts/curar_corpus.py` (nuevo), dos subcomandos en dos actos separados
  a propósito, nunca fusionados en una tecla:
  - `resolver <verificacion_doble.jsonl>` — decisión campo a campo
    (`[a]probar / [r]echazar con motivo / [e]ditar y aprobar / [s]altar`),
    ledger append-only y reanudable en
    `extraccion/estado/curacion/resoluciones.jsonl`. Nunca escribe en
    `normativa/es/` — ni siquiera recibe un directorio de salida.
  - `firmar --curador NOMBRE --sha256-pdf HASH <candidatas_a.jsonl>` — única
    acción que escribe en `normativa/es/`: genera la regla `estado: FIRMADA`
    (bloque `firma: {curador, fecha}`, hash del documento, cita literal),
    la valida, y la escribe SIN prefijo `_` (descubrible por el loader).
    Regla firmada = inmutable: si el fichero ya existe, no lo toca.
- `normativa/esquema/regla.schema.json`: bloque `firma` nuevo (aditivo).
- `normativa/validacion.py`: validación 19, `firma` obligatoria para toda
  regla `FIRMADA` — defensa en profundidad, no depende de pasar por la
  herramienta.
- `scripts/generar_borrador_corpus.py::_construir_documento`: extendido con
  el parámetro opcional `firma`, reusado (no duplicado).
- `tests/test_curar_corpus.py` (nuevo, 26 tests): las cuatro opciones,
  reanudabilidad de los dos actos por separado, inmutabilidad de una regla
  firmada, integración real contra el loader (patrón de
  `test_normativa_borrador_no_afirma.py`), y dos tests contra el fichero
  REAL de 101 entradas (recorrerlas todas sin excepción, saltando y
  aprobando).

**Hallazgo no anticipado:** ninguna de las 101 entradas reales del Prompt 2
tiene `lectura_a` y `lectura_b` pobladas a la vez — siempre exactamente una.
El camino de "elegir entre A y B" que pedía la tarea original sigue
implementado y probado, pero no lo ejerce ninguna de las 101 reales.

**Dejado fuera, explícitamente, por decisión de Pablo:** el golden set de
preguntas (`tests/golden/dbsua_preguntas.jsonl`) — posterior a una sesión
real de curación, con preguntas aportadas por Pablo, no una plantilla
rellenada antes de tener corpus real que preguntar.

**Limitación conocida — RESUELTA en la misma sesión, a petición explícita de
Pablo antes de cerrar la tarea.** Firmar más de una regla de la misma
materia+patrón con `aplicabilidad` genérica chocaba con la validación 14
(aplicabilidad genérica) y tumbaba la carga del corpus COMPLETO — verificado
que ocurría al firmar la 2ª-3ª regla, no en un caso extremo de volumen: con
el ritmo real de esta semana (~90-100 reglas DB-SUA) era seguro, no
probable. Arreglado ampliando la clave de
`normativa/validacion.py::validar_sin_contradiccion` con la cita del
artículo + el nombre de la regla (ninguno inventado, los dos ya estaban en
el documento), en vez de la alternativa que exigía inventar
`usos`/`tipologias` por regla. De paso, dos bugs relacionados en
`scripts/curar_corpus.py::_generar_regla_firmada`: no aplicaba el
`patron_override` de la cláusula atómica (heredaba el patrón del artículo
padre) y no aplicaba `sufijo_desambiguador` (varias sub-candidatas del
mismo artículo habrían compartido `concept_id`). Detalle completo y las
cifras de la verificación en la adenda de cierre del PRD y en
`docs/design/2026-08-21-limite-aplicabilidad-generica-verificada-automatica.md`
(marcado RESUELTO). Verificado con las 20 candidatas reales de DB-SUA: 39
reglas `FIRMADA` cargan sin colisión — test permanente
`tests/test_curar_corpus.py::test_loader_carga_sin_colision_al_firmar_todo_el_corpus_real_de_db_sua`.

**Tests:** suite completa, `1264 passed, 18 skipped, 1 xfailed, 0 failed`
(575s) — arrancado desde el verde de 1237 declarado al cierre del Prompt 2;
las 27 pruebas de más son de esta tarea (26 de la implementación inicial +
1 del arreglo de la validación 14). Los 2 warnings del resumen
(`ifcopenshell`, `tests/test_bim_lector.py`) son preexistentes y ajenos.

**Cierre de sesión (2026-08-21, tarde).** Todo lo pedido hoy sobre este PRD
está hecho y verificado, nada quedó a medias ni interrumpido. Primer paso
de mañana: Pablo ejecuta `python scripts/curar_corpus.py resolver
extraccion/estado/pendientes/codigotecnico__DB-SUA__3cfb5bbb135e.verificacion_doble.jsonl`
sobre las 101 entradas reales, y después `firmar` con su `--curador`. El
golden set (`tests/golden/dbsua_preguntas.jsonl`) es tarea posterior a esa
sesión de curación real, con preguntas que aporta Pablo — no se empieza
antes de tener corpus real que preguntar, y no se ha tocado hoy.

---

## 2026-08-20 (tarde/noche) · Paso 3 del roadmap: lectura BIM real -- en curso

**Modelo confirmado Sonnet** (Sonnet 5). Trabajo autónomo de 2h sobre
`bim/lector_ifc.py` únicamente, sin tocar C4/registro de capacidades, sin
corpus normativo, sin `ai_generator.py`. Checkpoints cada 20-30 min.

**[checkpoint 1]** Confirmado que el PoC sigue funcionando contra IFC reales
de terceros (no solo el round-trip sintético de `analyzer/ifc_export.py`):
descargados 3 ficheros públicos de `buildingSMART/Sample-Test-Files`
(licencia de test de interoperabilidad) -- `Building-Architecture.ifc`
(SketchUp, IFC4), `Building-Structural.ifc` (software distinto, con
`IfcBeam`/`IfcBuildingElementProxy`/`IfcFooting`/`IfcRoof`), `wall-with-
opening-and-window.ifc` (fichero de referencia ISO con una ventana real). El
lector abre y procesa los tres sin excepción.

**Hallazgo real durante la verificación, no hipotético:** confirmado con un
experimento (fabricar un IFC en milímetros a propósito) que `get_psets()`
devuelve el valor **crudo** del fichero, sin convertir a metros. Los tres IFC
reales **y el propio exportador de ArchMuse** (`analyzer/ifc_export.py`,
comentario "SI por defecto: metro" -- **incorrecto**, verificado leyendo el
código fuente de `ifcopenshell.api.unit.assign_unit`: su valor por defecto es
milímetros) declaran la longitud en mm. Corregido con `ifcopenshell.util.
unit.calculate_unit_scale()`. Segunda vuelta de tornillo, encontrada
verificando contra los ficheros reales (no por inspección de código): la
superficie/volumen **no** se derivan de la escala de longitud al
cuadrado/cubo -- los cuatro ficheros las declaran como unidad SI
independiente, ya en m²/m³. El primer intento (escala²) habría dejado la
superficie 1.000.000 de veces menor que la real; corregido antes de que
llegara a ningún test, pero queda documentado en el propio módulo como aviso
para el futuro.

**Implementado en `bim/lector_ifc.py` (nada fuera de él):**
- Corrección de unidades (longitud/área/volumen leídas cada una con su
  propia escala, `_Escalas`/`_escalas_unidad`), con aviso explícito en el
  inventario cuando la escala no es 1.0.
- Inventario de clases ahora completo (`_conteo_por_clase`), no una lista
  fija de 9 -- verificado que la lista fija dejaba invisible casi la mitad de
  los elementos de `Building-Structural.ifc`.
- `EspacioIFC` gana `volumen_m3` (mismo patrón "declarado o `None` con
  motivo" que ya regía para superficie).
- `PlantaIFC` (nuevo): elevación declarada por planta.
- `AberturaIFC` (nuevo): puertas/ventanas con ancho/alto declarados
  (`OverallWidth`/`OverallHeight`, atributos directos del IFC, no geometría).
- `SitioIFC` (nuevo): coordenadas geográficas declaradas del `IfcSite`
  (latitud/longitud desde `IfcCompoundPlaneAngleMeasure`, elevación).

**Verificado con la suite existente:** `tests/test_bim_lector.py`, 12/12 en
verde tras la corrección de unidades (2 fallaron primero por el bug de
escala², arreglado antes de seguir).

**[checkpoint 2]** Añadidos como fixture 3 IFC reales de terceros a
`tests/fixtures/ifc_real/` (buildingSMART/Sample-Test-Files, licencia CC BY
4.0, README con procedencia) y 8 tests nuevos en `tests/test_bim_lector.py`
que ejercitan cada uno: lectura sin excepción, inventario de clases completo
(confirmado contra `Building-Structural.ifc` que antes dejaba invisibles
`IfcBuildingElementProxy`/`IfcFooting`/`IfcRoof`/`IfcChimney`/
`IfcDiscreteAccessory`), conversión de unidades, ventana real con
ancho/alto=1.0m (no 1000, el bug que se habría colado sin la corrección),
sitio real con lat/lon convertidas desde grados-minutos-segundos, sitio sin
coordenadas que no inventa 0.0, planta sin ruido de "-0.0". `tests/test_bim_
lector.py`: 20/20 en verde (12 existentes intactos + 8 nuevos).

Detalle menor encontrado y corregido en el camino: `Elevation` de una planta
real salía `-0.0` (ruido de punto flotante redondeado) -- normalizado a
`0.0`, con un test que lo fija.

Escrito `docs/design/2026-08-20-lector-ifc-que-le-falta-para-ser-capacidad.md`
(punto 3 del encargo): qué falta para `BIM-1` (wiring al grafo de atributos)
y `BIM-2` (contraste IFC↔declarado↔DXF), por qué `BIM-2` no puede vivir
dentro de `bim/lector_ifc.py` aunque se le añadan más lecturas, y qué de
`BIM-4` (robustez) sigue sin probar (IFC2X3, ficheros grandes, elementos
estructurales con dimensión declarada). No registra nada, no toca
`agente/registro.py`.

**[checkpoint 3, cierre]** Suite completa del repo confirmada como regresión
final: **1073 passed, 18 skipped, 1 xfailed, 2 failed** -- los 2 fallos son
los guardianes de `C4`/`D-12` de siempre (`registro` en 13, tope en 12,
decisión de Pablo pendiente desde el 19-ago), sin relación con este cambio.
Cero regresiones nuevas.

Commit local hecho (**sin push**, según pediste): `8b94e8e` en
`agente/nucleo-agentico`, acotado a `bim/lector_ifc.py`,
`tests/test_bim_lector.py`, `tests/fixtures/ifc_real/`, el documento de
diseño, y esta misma entrada de `PROGRESS.md` -- **deliberadamente sin
incluir** los PRD de `docs/prd/` que seguían modificados/nuevos de la sesión
anterior (siguen sin commitear, a la espera de tu lectura, como pediste esa
vez).

**Qué NO se hizo, a propósito:** no se ha tocado `agente/registro.py` ni el
techo de `C4` (`bim.inventario_de_ifc` sigue retirada del registro, tal como
estaba). No se ha empezado corpus normativo CTE. No se ha tocado
`ai_generator.py`. No se ha probado contra IFC2X3, ficheros grandes, ni
dimensión declarada de elementos estructurales (muros/columnas/vigas/losas)
-- documentado como gap explícito en el documento de diseño, no silenciado.

---

## 2026-08-20 (tarde, 3ª sesión) · Tres decisiones documentales cerradas con criterio propio

**Modelo confirmado Sonnet** (Sonnet 5). Solo documentación, cero código.
OP-17/OP-18 siguen sin aprobar. No se ha interpretado contenido normativo ni
técnico que no pudiera verificar directamente en el repo -- las tres
decisiones de abajo se apoyan en evidencia ya citada en la sesión anterior.

**1. `docs/prd/2026-08-15-analisis-de-sitio.md` -- confirmado como Aprobado.**
Cabecera y párrafo de cierre actualizados: `Aprobado por: Pablo -- confirmación
tardía, aprobación implícita nunca formalizada -- se cierra el 2026-08-20 por
consistencia con el resto del backlog que ya lo daba por firme` (CP-4, Fase A
de procedencia de parcela, integración normativa-Catastro ya construyen sobre
él como si estuviera firme, sin que nadie lo hubiera formalizado por escrito).
**No cerrado, a propósito:** la sub-pregunta separada de §9/§14 (punto 5 -- si
el análisis se dispara automático al importar un pliego, o solo por botón)
sigue sin confirmar; no es la misma pregunta que la aprobación general, así
que se deja anotada tal cual estaba.

**2. Aclaración retroactiva sobre `docs/prd/2026-08-19-copiloto-que-modifica-
el-proyecto.md`** (contradicción entre dos entradas antiguas de este mismo
fichero, detectada la sesión anterior). **No se han editado las entradas
antiguas** -- esto es una aclaración nueva, con fecha de hoy, no una
reescritura de lo que ya se escribió entonces:

- La entrada "2026-08-19 (tarde) · Decisiones de Pablo aplicadas" (más abajo
  en este fichero) dice, con toda intención: *"El de `CP-1` (copiloto) sigue
  pendiente de firma: Pablo aprobó los dos de medición, no ése... queda
  anotado aquí para que no pase por aprobado sin serlo."* -- está escrita
  precisamente para prevenir esta confusión.
- La entrada "2026-08-19 · Corrección de la especificación, CP-5, y tres
  frentes" (más abajo todavía, es decir, más antigua) dice de pasada *"esto ya
  estaba en el PRD original y aprobado (`docs/prd/2026-08-19-copiloto-que-
  modifica-el-proyecto.md`, criterio de aceptación nº7...)"* -- uso impreciso
  de "aprobado": se refiere a que el criterio ya estaba **redactado** en el
  borrador del PRD, no a que Pablo lo hubiera aprobado.
- **Versión vigente: la primera.** Confirmado contra la fuente más fiable, la
  cabecera actual del propio PRD, que dice hoy `Estado: Borrador · Aprobado
  por: _pendiente -- el informe ejecutivo de Pablo del 2026-08-19 hace de
  requisitos_`. El PRD sigue sin aprobación formal; la implementación de esa
  época se hizo (legítimamente, según el propio PRD) contra el informe
  ejecutivo de Pablo como requisitos de facto, no contra un PRD firmado.

**3. `docs/prd/PRD-001-Core-Reasoning-Engine.md` -- NO tocado, duda real
declarada, esta vez leyendo el PRD completo antes de decidir (no solo
inferido, como en la sesión anterior).** No es una supersesión limpia: es una
**duplicación no resuelta** entre dos diseños para el mismo problema. `PRD-001`
implementa en modo sombra el modelo de `REASONING_ENGINE_SPEC.md`/
`BRAIN_ARCHITECTURE.md` (entidades `Fact`/`Constraint`/`Rule`/`Inference`/
`Evidence`, 20 entidades en total, MVP de 2 dominios). La especificación que
reorienta `CLAUDE.md` (`ARCHMUSE_SPEC.md`, incrustada ahí) define **su propio**
modelo de razonamiento para el mismo problema -- `Project Model`, `Tool`,
`Provenance`, `Finding`, `Evidence`, hitos M0-M4 -- con vocabulario y alcance
distintos, y **ningún documento de los dos declara al otro derogado**.
Decidir cuál manda es exactamente el tipo de interpretación de la línea de
razonamiento del producto que tengo prohibido resolver por mi cuenta. Se deja
`PRD-001` sin editar, con esta duda -- no una simple ausencia de mención en
`PROGRESS.md` -- anotada aquí para que la resuelvas tú.

Todo sin commitear.

---

## 2026-08-20 (tarde, 2ª sesión) · Cabecera de procedencia corregida + auditoría documental

**Modelo confirmado Sonnet** (Sonnet 5) antes de empezar, según pediste. Solo
documentación -- cero código tocado, OP-17/OP-18 siguen sin aprobar ni
implementar, C4/BIM/normativa/`ai_generator.py` no tocados.

**1. Cabecera de `docs/prd/2026-08-20-procedencia-y-fecha-de-datos-de-parcela.md`
corregida:** de `Estado: Borrador · Aprobado por: _pendiente_` a `Aprobado e
implementado (Fase A completa) · Aprobado por: Pablo (2026-08-20, con 3 notas
incorporadas...)` -- reflejando lo que la entrada de PROGRESS.md de más abajo
("Fase A del PRD de procedencia de parcela -- hecha") ya documentaba desde
hace horas.

**2. Auditoría documental** (agente de solo lectura: cabeceras de los 57 PRDs
de `docs/prd/` cruzadas contra `PROGRESS.md` completo, ~1500 líneas). Tres
correcciones aplicadas, mismo patrón que el punto 1 pero detectable dentro del
propio fichero (cabecera dice `APROBADO`, el párrafo de cierre seguía diciendo
"Decisión pendiente de Pablo" sin actualizar):

- `docs/prd/2026-08-19-skill-del-cuadro-de-superficies.md` -- párrafo de
  cierre sustituido: la condición de aprobación (verificación de suma
  informativa hasta 10 proyectos) ya estaba resuelta y citada en la propia
  cabecera; solo el párrafo final no se había actualizado.
- `docs/prd/2026-08-19-escritura-protegida-del-dxf-del-cliente.md` -- párrafo
  de cierre sustituido: la Capacidad `plano.escribir_cuadro` (tareas de §11)
  está construida y probada según `PROGRESS.md` ("`SEG-1` -- la pantalla de
  autorización"), deliberadamente sin endpoint HTTP -- eso sí seguía siendo
  cierto y se conserva en la corrección.
- `docs/prd/2026-08-19-planificador-tipado.md` -- párrafo de cierre
  sustituido: `AG-1`/`AG-2`/`AG-4` ya construidos y probados según la misma
  entrada de `SEG-1`. La pregunta secundaria que ese párrafo dejaba abierta
  (¿el bucle de `nucleo.py` se conserva indefinidamente o se le pone fecha?)
  **sigue sin decidir** -- no encontré evidencia en `PROGRESS.md` de que se
  resolviera, así que la dejé anotada como pendiente en el propio PRD, no la
  cerré por mi cuenta.

**Encontrado y NO corregido, a la espera de que tú lo confirmes** (no había
evidencia suficiente para decidirlo sin ti):

- `docs/prd/2026-08-15-analisis-de-sitio.md` -- cabecera dice `Aprobado por:
  Pablo (implícito -- pedido repetido dos veces; confirmar)`, sin confirmar
  nunca por escrito, mientras varios PRDs posteriores ya construyen sobre
  `/api/analizar-sitio` como si estuviera firme (CP-4, Fase A de hoy,
  integración normativa-Catastro). El propio cuerpo del PRD también deja sin
  cerrar si el punto 5 se implementa o se revierte. No lo toco -- si sigue en
  pie, confírmalo y actualizo la cabecera; si el punto 5 se descartó, dímelo
  también.
- `PROGRESS.md` mismo usa la palabra "aprobado" de forma floja en una entrada
  sobre `docs/prd/2026-08-19-copiloto-que-modifica-el-proyecto.md` (línea
  ~1202), mientras otra entrada más arriba dice explícitamente que ese PRD
  "sigue pendiente de firma". La cabecera del PRD en sí está bien (dice
  `Borrador · _pendiente_`, correcto) -- no toqué entradas antiguas de
  `PROGRESS.md` porque es un registro cronológico y reescribir texto ya
  cerrado de sesiones pasadas parecía peor que dejarlo anotado aquí.
- `docs/prd/PRD-001-Core-Reasoning-Engine.md` -- sigue en `Borrador/_pendiente_`,
  técnicamente no es falso, pero `CLAUDE.md` (ANEXO y AVISO) ya trata esa
  línea de trabajo (el "Cerebro Arquitecto") como superada por la arquitectura
  real del repo. `PROGRESS.md` no lo menciona ni una vez, así que es una
  inferencia mía, no una verificación directa -- y toca de cerca el territorio
  de corpus normativo/razonamiento que tengo prohibido tocar, así que lo dejo
  sin editar y solo lo anoto.

**Cobertura honesta:** `PROGRESS.md` documenta en detalle sobre todo el
trabajo de 2026-08-19 y 2026-08-20; no dice nada de los PRDs de 2026-08-01 a
2026-08-13. Para esos solo se revisó la cabecera (sin encontrar nada
obviamente roto: fechas imposibles o "pendiente" en algo evidentemente ya en
producción) -- no hay garantía de que estén al día, solo que no saltó ninguna
señal fuerte con esta pasada.

Todo sin commitear (`git status`: `M` en `PROGRESS.md` y en los 4 PRDs
tocados; `??` en los dos PRDs de OP-17/OP-18 de la sesión anterior, que siguen
sin tocar) -- a la espera de que lo revises.

---

## 2026-08-20 (tarde) · PRDs de OP-17 y OP-18 -- borradores, sin código

**Modelo confirmado Sonnet** (Sonnet 5) antes de empezar, según pediste. Sesión
de trabajo autónomo (~1h, sin supervisión) con alcance acotado a documentación
pura -- cero código tocado.

**Hecho:** dos PRDs nuevos en `docs/prd/`, siguiendo el mismo formato y nivel
de detalle que `2026-08-20-procedencia-y-fecha-de-datos-de-parcela.md`
(§0 Alcance explícito, preguntas abiertas separadas de las 14 secciones,
tabla de impacto por fichero con funciones/líneas concretas citadas):

- `docs/prd/2026-08-20-accesibilidad-geometrica-itinerarios.md` (OP-17).
  Complementa, sin sustituir, los checks de accesibilidad ya existentes en
  `evaluator.py` (`evaluate_bathroom_turning_space`, `evaluate_minimum_room_width`,
  `evaluate_itinerario_accesible`). Aviso honesto incluido en el propio PRD: de
  las tres cifras que promete OP-17 en el backlog (anchos de paso, radios de
  giro, pendientes de rampa), **las dos últimas -- anchos de hueco de puerta y
  pendientes de rampa -- no son calculables hoy** sin un modelo de carpintería/
  cotas verticales que el repo no tiene (el propio `evaluator.get_missing_data_
  warnings` ya lo advierte). No se decide recortar el alcance por mi cuenta --
  queda como §14, a la espera de que Pablo lo lea.
- `docs/prd/2026-08-20-retranqueos-vs-parcela-real.md` (OP-18). Cruza la huella
  de edificio medida (OP-16) con la geometría real de parcela de Catastro
  (Fase A de hoy), sin tocar el proxy `evaluate_retranqueos` existente. El
  riesgo técnico central queda como pregunta abierta explícita (§6), sin
  decidirla: no existe hoy ningún mecanismo de transformación entre el sistema
  de referencia de Catastro (lon/lat) y las coordenadas locales del DXF -- dos
  caminos posibles (anclaje manual declarado vs. georreferenciación automática
  con una dependencia nueva tipo `pyproj`), ninguno elegido aquí.

Ambos PRDs quedan en `Estado: Borrador`, `Aprobado por: _pendiente_`, **sin
commitear** (`git status` confirma `??` en los dos ficheros) -- a la espera de
que Pablo los lea antes de que entren al repo, tal como pidió explícitamente.
Ningún código de producto tocado; `ai_generator.py` no se ha abierto.

**Revisión del backlog pedida ("¿queda algo genuinamente desbloqueado?"):**
no hay nada nuevo que añadir -- la entrada de más abajo de este mismo día
("Cierre de esta ronda del backlog") ya cerró exactamente esta pregunta hace
unas horas: todo lo que queda en `AGENTE_BACKLOG.md` sin BIM/normativa/
capacidad nueva tiene o bien una dependencia `PENDIENTE` real (INF-2, INF-4,
INF-5, INF-7, ME-2, TL-3, TL-4, SEG-3, SEG-4) o está bloqueado por una decisión
humana (D-6, D-7, un colegiado firmando SK-5). Contrastado también contra un
"Bloque 3 (housekeeping)" mencionado en un informe aparte (vendorizar three.js
-- ya hecho; sacar `JarvisApp.py` del repo; decidir el futuro de `/mvp`): esos
tres ítems están explícitamente "a la espera de que Pablo confirme el
resultado de los Bloques 1 y 2" en ese mismo informe, así que tampoco cuentan
como libres de decisión de Pablo. Ninguno se ha ejecutado -- se deja anotado
para que él decida, tal como pidió.

**Hallazgo aparte, no corregido a propósito (fuera de alcance de esta
sesión):** la cabecera de `docs/prd/2026-08-20-procedencia-y-fecha-de-datos-
de-parcela.md` sigue diciendo `Estado: Borrador` / `Aprobado por: _pendiente_`,
pero la entrada de PROGRESS.md justo debajo de ésta documenta esa misma Fase A
como aprobada, implementada, testeada y subida a GitHub. Parece que la
cabecera del PRD nunca se actualizó tras el cierre (el propio proceso PRD-first
pide `Estado: Implementado` + fecha de cierre al terminar). No lo he tocado --
no es de las dos capacidades que me pediste documentar y cambiar la cabecera
de un PRD ajeno sin que me lo pidieras explícitamente no me pareció "acotado y
seguro". Lo dejo anotado para que lo cierres tú si es un despiste real.

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

## 2026-08-20 · Simplificación al máximo del estado de reposo de la conversación

Pedido de Pablo con referencia visual descrita (no imagen): en reposo, la
pantalla de conversación debía verse como una sola caja de texto flotando
centrada sobre un fondo casi negro con glow azul difuso, sin cabecera, sin
sidebar, sin bienvenida aparte -- y todo el resto (Adjuntar DXF, selector de
modo, statusbar) apareciendo solo al interactuar.

**Hecho:**
- `.conv-header` deja de ser fijo en `/` -- se oculta entera vía
  `.conv-sin-cabecera` (antes solo escondía el botón "Volver"), sin tocar el
  caso `/proyectos` (que sigue abriendo la conversación como overlay con su
  cabecera intacta -- el condicional sigue acotado a `pathname === "/"`).
- La sidebar entera vive detrás de `#conv-menu-toggle` (☰, fijo, siempre
  encontrable): colapsada a `width:0` por defecto, se abre con
  `.conv-sidebar-abierta` (click, cierra con click-fuera o Escape). El aviso
  legal de "sin corpus firmado todavía" **no se ha tocado ni movido de
  sitio** -- sigue en el DOM tal cual, solo detrás de un clic.
- La bienvenida grande centrada desaparece como texto aparte: su primera
  frase pasa a ser el placeholder por defecto del sistema de sugerencia
  fantasma (`CONV_SUGERENCIA_SIN_ADJUNTO`) dentro de la propia caja.
- `.conv-activo` (clase en `.conv-main`, de un solo sentido) gobierna la
  revelación de "Adjuntar DXF", el selector de modo y la statusbar --
  ocultos por CSS mientras no está presente.
- Refuerzo del glow: dos `radial-gradient(--accent-soft)` a distinto radio
  en `.conv-main::before` (mismo token, núcleo más denso sin inventar color).

**Dos bugs reales encontrados verificando en el navegador (no en tests, que
no cubren nada de esto):**
1. `abrirConversacion()` hace `textarea.focus()` al cargar `/` (ya existía,
   para dejar el cursor listo) -- un `focus` real, no de automatización,
   dispara igual que un click del usuario. Engancharle `convActivar()` al
   evento `"focus"` (mi primer intento) activaba la pantalla entera para
   CUALQUIER visitante real en cuanto cargaba la página, anulando el reposo
   por completo. Arreglo: `convActivar()` ahora cuelga de `"mousedown"` y
   `"keydown"` en el textarea, nunca de `"focus"` -- esos dos eventos sólo
   los dispara hardware real, `.focus()` programático no.
2. `.shell-dropdown` (componente reutilizado del selector de modo) vivía a
   `z-index:41`, hermano de `#conversacion-archmuse` (`z-index:100`) por
   estar añadido a `<body>`. El desplegable se abría (`display:block`,
   posición correcta) pero quedaba pintado DEBAJO del overlay --
   invisible y sin poder pulsarlo, aunque el DOM dijera que estaba abierto.
   Subido a `z-index:101`.
   También se retiró un `@media (max-width: 900px) { .conv-sidebar {
   display: none; } }` obsoleto que sobrevivía de cuando la sidebar
   arrancaba visible a 240px: con el nuevo `width:0` por defecto, ese
   `display:none` sólo servía para anular el toggle nuevo en pantallas
   estrechas, dejando el aviso legal inalcanzable ahí.

**Verificado en el navegador** (no solo en tests): reposo limpio a 1400×900
(sólo caja + botón enviar + ☰), sidebar abre/cierra con el aviso legal
visible (click-fuera y Escape), activación real por click/tecleo (no por
`.focus()` programático), dropdown de modo visible y funcional tras el
arreglo de z-index, envío de pregunta sin adjunto renderiza la respuesta de
error esperada en `#conv-log`.

**Tests:** suite completa, `1065 passed, 2 failed (los dos guardianes de
C4, esperados), 18 skipped, 1 xfailed` -- sin regresiones.

## 2026-08-22 · Corpus firmado DB-SI 3 (viernes/sábado del PRD) + rediseño de los PDF de medición y revisión

Dos encargos de Pablo en la misma sesión. Calendario vinculante: sesión de
validación con el arquitecto colegiado y la coordinadora de AENOR el **lunes
25**; volcado el **martes 26**; `analyzer/`, `scripts/` y `tests/fixtures/`
congelados hasta el **jueves 28** (el rediseño de PDF fue excepción puntual
confirmada por Pablo para tres ficheros de presentación, nada más).

**Corpus firmado (PRD `docs/prd/2026-08-22-corpus-firmado-dbsi3-evacuacion.md`,
aprobado por Pablo con 3 decisiones explícitas -- §11.0):**
- La fase de firma ya existía del PRD cerrado del 21-08 y nunca se había
  ejecutado en producción; esta fase la ejecuta y cierra sus dos huecos: la
  firma no estaba atada al contenido, y los modelos A (tag colegiado) y B
  (firma nominal) convivían sin hablarse. Resolución: `curador`=Pablo +
  `firma.validado_por` (registro nominal de la validación externa en papel).
- 7 borradores `normativa/es/estatal/_paquete_dbsi3_*.yaml` (15 reglas: 11
  exigencias + 4 definiciones del Anejo A que el glosario no cubre),
  transcritos a mano con la ficha (promovida a **aprobada**) desde el PDF
  oficial de fixtures, con `hash_texto` y `documento_sha256`. El pipeline
  automático NO podía producirlos (fuentes solo-DB-SUA y prefijo hardcodeado
  en scripts congelados; tablas multi-eje inconvertibles por diseño).
- `normativa/firma.py` (nuevo): `hash_de_contenido_firmado` sobre
  serialización canónica JSON que excluye `{firma, estado, tags}`
  (CLAVES_DE_FLUJO) -- por eso la huella impresa en la hoja (borrador) y la de
  la regla firmada son LA MISMA, y el acta en papel ancla el corpus.
- Validación 20 (`validar_integridad_de_firma`, en VALIDACIONES_POR_FICHERO):
  manipular una regla firmada tumba su fichero en la siguiente carga
  (fail-closed). Fase 1 tolera FIRMADA sin hash (compatibilidad con el
  formato del 21-08); la fase 2 del jueves lo hace obligatorio (invertir T4).
- Esquema: `firma.hash_contenido` + `firma.validado_por` (aditivo, opcional);
  comentario obsoleto de `FIRMADA` corregido.
- Paquete nuevo `curacion/` (fuera del congelado `scripts/`, herramienta
  permanente): `comprobar_borradores`, `hoja_de_revision` (HTML A4: página de
  decisiones única que se firma, con F·L·M, huella por fila y huella de
  paquete; anexo de literales solo lectura) y `volcar_acta`
  (`transcribir`→ledger append-only `extraccion/estado/curacion/
  actas_papel.jsonl`; `firmar --curador` exige huella==ledger --el papel
  manda--, escribe `dbsi3_evacuacion_*.yaml` visible e inmutable).
- Hoja generada e imprimible: `docs/curacion/2026-08-25-dbsi3-evacuacion-p1.html`
  + lista de dudas (10, entregable de la ficha) en
  `docs/curacion/2026-08-25-dbsi3-evacuacion-dudas.md`.
- Tests nuevos: `test_firma_integridad.py` (hash canónico/manipulación/
  tolerancia fase 1), `test_curacion_hoja.py` (volcado: papel manda,
  inmutable+reanudable, corrección al margen, hoja completa),
  `test_politica_corpus_produccion.py` (toda regla de producción FIRMADA con
  hash válido o marcada con el tag; el flag `pendiente_de_firma_colegiada`
  de la capacidad cae solo al firmar -- G11 intacto). Whitelist de
  `test_normativa_aplicable.py` ampliada con los 7 borradores.
- **Pendiente y calendarizado**: martes 26 volcado + supersede de la piloto +
  manifiesto a `parcial` (en ese orden) + reescritura de los dos tests de
  producción; jueves 28 fase 2 del hash + `curar_corpus.py` + validación 14
  bitemporal. El legacy D4 (`evaluator.py:1785`) NO se toca sin PRD propio.

**Rediseño de PDF (medición y revisión), opción A elegida por Pablo:**
- `marca_borrador.py` crece a módulo de mobiliario de página: `chip_borrador`
  (franja discreta de cabecera), `pie_tecnico` (filete, referencia del
  documento, huella SHA-256 del plano al pie -- ya no en cabecera) y
  `lienzo_numerado` («Página X de Y»). La firma de `estampar` y la leyenda
  DOC-3 intactas (sus tests lo exigen).
- `medicion_pdf.py`: cajetín en bloque (documento/plano/fecha/herramienta),
  criterio de medición dicho UNA vez, cuadro por vivienda con columna
  estrecha «Referencia» (rótulo · capa), cifras a la derecha con coma decimal
  y unidad en la cabecera de columna, filas alternas, TOTAL con filete,
  notas por familia, descartes agrupados por motivo (el motivo encabeza, las
  líneas solo capa + entidades).
- `coherencia_pdf.py`: misma retícula; `_magnitud` en formato de medición
  («4,00 m²»), sin repetir la cifra cuando la descripción ya la dice, y
  «-1 piezas de diferencia» dicho en legible («falta 1 pieza» / «sobran N»)
  -- traducción de PRESENTACIÓN, `coherencia.py` sin tocar.
- `agente/herramientas/{medicion,coherencia}.py`: clave `herramienta` para el
  cajetín (la versión de la Skill no llega ahí sin romper el contrato de la
  capacidad, congelado en fixtures: se declara la capacidad).
- PDFs de `v2s.dxf` regenerados en `Desktop/ArchMuse_ejemplos_pdf/` (los
  anteriores conservados como `*.anterior.pdf`); verificado en el texto
  extraído: cajetín, huella al pie, «Página X de Y», sin «m2» crudo,
  falta/sobra en legible.

**Tests:** suite completa, `1324 passed, 18 skipped, 1 xfailed` -- cero
fallos, sin regresiones.
