# Checklist — primer día de trial de AutoCAD

**Fecha:** 2026-09-08 · **Actualizado:** 2026-09-10 · **PRD:**
`docs/prd/2026-09-08-integracion-autocad-autolisp.md` (**APROBADO**).

> **EJECUTADO EL 2026-09-09, EN AUTOCAD 2027, SOBRE `V5.dxf`.** Pasos 1 a 6
> superados; el 7, en lo que este plano permite comprobar. **Falló el paso 8**:
> las columnas llevaban un ancho fijo, el texto se partía letra a letra en
> vertical y las cabeceras eran ilegibles. Corregido el 2026-09-10 (el ancho
> sale ahora del contenido real) y **la corrección está sin ejecutar**: cuando
> se vuelva a abrir AutoCAD, el paso 8 se repite entero. Lo que este plano no
> tiene —ninguna vivienda bloqueada— sigue sin probarse, y está marcado abajo
> como tal. Las casillas con `[x]` son las que se vieron con los ojos ese día;
> las vacías, las que no.

> **Actualización del 2026-09-09.** El PRD está aprobado, `archmuse.lsp` está
> escrito y las cifras esperadas del paso 5 se han rehecho: el criterio firmado
> `C-1` retiró la «superficie útil total», así que lo que hay que contrastar son
> **dos** magnitudes por vivienda y no tres. Si en la pantalla aparece una cifra
> que sume interior y exterior, **eso es el fallo**, no la referencia.

**Para qué existe:** el trial es un reloj corriendo. Este documento es el orden
del día para no improvisar. **Se lee entero antes de instalar nada.**

**Regla de oro de este documento:** cada prueba dice, si falla, **de quién es la
culpa** — del *flujo* (la idea no sirve) o del *lenguaje* (AutoLISP es incómodo).
Es la única forma de que un prototipo fallido siga siendo informativo (`R-1` del
PRD).

---

## Paso 0 · Antes de activar el trial (hazlo hoy, no el día 1)

- [ ] **El trial es de AutoCAD completo, NO de AutoCAD LT.** `vlax-create-object`
      no existe en LT: devuelve `nil` siempre, y sin él no hay HTTP. Un trial de
      LT hace inejecutable el prototipo entero, y no se puede deshacer.
- [ ] Windows: el objeto COM `WinHTTP.WinHTTPRequest.5.1` es del sistema, no de
      AutoCAD. Se puede comprobar **sin AutoCAD**, desde PowerShell:
      `New-Object -ComObject WinHttp.WinHttpRequest.5.1`. Si eso falla, el
      problema no es AutoCAD y se arregla antes de gastar un día de licencia.
- [ ] Servidor ArchMuse levantado y contestando: `curl http://127.0.0.1:5000/medir`
      devuelve 200.
- [ ] Ten a mano `_material/ejemplo.dxf`. Es el plano con el que están medidas
      todas las cifras esperadas de este documento.

## Paso 1 · El fichero carga sin error de sintaxis

- [x] `APPLOAD` → `autocad/archmuse.lsp` → **no aparece ninguna ventana de error**.
      *2026-09-09, AutoCAD 2027: carga limpio a la primera.*
- [x] En la línea de comandos aparece la línea de bienvenida con la versión.

**Si falla:** es del **lenguaje**. Un paréntesis. El error de AutoCAD dice el
número de línea; anótalo, no lo depures a ojo.

> Esto era lo que más probabilidad tenía de fallar el primer día y no falló: 568
> líneas de un lenguaje escrito sin intérprete delante cargaron sin un solo
> error de sintaxis. Dicho lo cual, el fichero ha cambiado el 2026-09-10 y la
> versión que cargó ya no es la que hay en disco: **este paso se repite**.

## Paso 2 · El comando existe

- [x] Teclea `ARCHMUSE` → responde algo. No «Comando desconocido».

**Si falla:** el `defun` no lleva el prefijo `c:`, o el fichero cargó a medias.
Del **lenguaje**.

## Paso 3 · Selección correcta de polilíneas

Con `ejemplo.dxf` abierto:

- [x] El script anuncia la capa que ha detectado. Sobre este plano debe ser
      **`00 areas`**. *Sobre `V5.dxf`, el 2026-09-09: detectó `00 areas`, y era
      la única candidata.*
- [x] Anuncia **cuántas polilíneas cerradas** ha cogido. Sobre `ejemplo.dxf` la
      medición por la web da **40 piezas** repartidas en 6 viviendas: si el
      número que anuncia el script es muy distinto, párate aquí.
      *Sobre `V5.dxf`: **22 polilíneas, ninguna descartada**.*
- [ ] Prueba a dar una capa a mano cuando pregunte, y comprueba que la respeta.
      *Sin probar el 2026-09-09: se aceptó la capa propuesta con INTRO.*

> **El aviso de polilíneas descartadas no se ha visto dispararse, y ahora se
> sabe por qué.** El punto 1 de más abajo dice que en `V5.dxf` hay **3
> polilíneas de 22 con el flag de cerrada mal puesto**; abierto el plano en
> AutoCAD, el comando avisó de **cero**. No es una contradicción: son dos
> ficheros. El original `_material/V5.dxf` tiene las 3; el fixture
> `tests/fixtures/reales/planta_tres_viviendas.dxf` tiene **0**, porque
> `derivar_fixture_anonimo.py` no copia entidades —reconstruye el plano y
> escribe todas las polilíneas con `close=True`—, así que la anonimización
> arregló el defecto sin querer. Medido el 2026-09-10; el detalle y lo que
> implica, en `docs/PROGRESS.md`.
>
> Consecuencia para este paso: **con los fixtures del repositorio este aviso no
> puede dispararse nunca**. Para verlo funcionar hace falta abrir un plano que
> tenga el defecto de verdad.

**Si el recuento no cuadra**, mira primero estos tres, que son diferencias
**conocidas y esperadas** frente a la web, no fallos:

1. **Polilíneas con el flag de «cerrada» mal puesto.** Es la causa más probable
   y está medida: `ssget` sólo filtra por el bit del código 70, y el lector de
   Python además recupera las que cierran geométricamente. En los planos reales
   son **3 de 22 en `V5.dxf`, 2 de 10 en `v2s.dxf` y 9 de 53 en `ejemplo.dxf`**
   — hasta un 17%. **El propio comando te dice cuántas deja fuera antes de
   enviar**: si ese número explica la diferencia, no hay nada que depurar.
2. **Bloques anidados.** `ssget` no entra en bloques; el lector Python sí. Si el
   plano dibuja recintos dentro de bloques, el script verá menos.
3. **Polilíneas con arco (*bulge*).** El script las declara aparte y no las
   mide.

Cualquier otra diferencia es del **flujo** y hay que anotarla: significa que lo
que AutoCAD llama «los recintos» y lo que ArchMuse llama «los recintos» no es lo
mismo, que es un hallazgo mayor que el prototipo.

## Paso 4 · El POST llega

- [x] Mira la consola del servidor: tiene que aparecer la línea de acceso a
      `/api/medicion-geometria`. *Llegó, y devolvió 200.*
- [x] AutoCAD no se queda colgado para siempre: **avisa** de que va a tardar
      (~10 s sobre 6 viviendas) y vuelve. *Volvió con la respuesta.*

**Si no llega nada al servidor**, en este orden:

1. `localhost` contra `127.0.0.1` — prueba el segundo.
2. Antivirus o cortafuegos bloqueando el COM de AutoCAD.
3. El objeto COM no se creó (comprobado en el paso 0).

Los tres son del **lenguaje/entorno**. Ninguno dice nada del flujo.

## Paso 5 · La respuesta se lee

- [x] El script imprime en la línea de comandos el total de la primera vivienda
      **antes** de dibujar nada. *Imprimió las tres, antes de pedir el punto.*
- [ ] **Contrástalo contra las cifras conocidas.** Sobre `ejemplo.dxf`, y son
      **dos por vivienda, que no se suman** (criterio firmado `C-1`):

  | Vivienda | útil interior | útil exterior |
  |---|---|---|
  | VT1/3 | **58,78** | **7,54** |
  | VT2/2 | **50,97** | **7,47** |
  | VT3/3 | **59,11** | **7,45** |
  | VT4/2 | **50,91** | **7,56** |
  | VT5/1 | **41,05** | **4,27** |
  | VT6/2 | **no se publica** | **no se publica** (solape de 8,47 m²) |

  Planta: **sin cifras** — falta VT6/2, y una planta a la que le falta una
  vivienda no se totaliza. Y aviso: el rótulo `VT22/1` no tiene ningún recinto.

  Si prefieres un plano que sí dé cifras de planta, usa `V5.dxf`: **168,86**
  interior y **22,46** exterior, 3 de 3 viviendas.

- [x] **`V5.dxf`, 2026-09-09: las cinco cifras coinciden una a una.** VT1/3
      58,78 / 7,54 · VT2/2 50,97 / 7,47 · VT3/3 59,11 / 7,45 · planta 168,86 /
      22,46. Esto es lo que se venía a comprobar: el modo de entrada nuevo **no
      mide por su cuenta**, dibuja lo que mide el servidor. Sobre `ejemplo.dxf`
      (6 viviendas, una bloqueada) sigue sin ejecutarse.
- [x] **Acentos.** Comprueba que un motivo con tildes y comillas angulares se lee
      bien y no sale como `Â«VT6/2Â»`. Es el fallo más probable después de la
      sintaxis, y es de **codificación** (UTF-8 del servidor contra ANSI de
      AutoCAD), no del flujo. *No hubo problema: las tildes salieron bien en
      AutoCAD 2027. Ojo, sin motivos de bloqueo en pantalla lo único que se
      comprobó fueron las cabeceras del propio `.lsp`; el texto con tildes que
      viene del servidor sigue sin verse.*

**Si los números no coinciden con la tabla**, es del **flujo** y es grave: el
modo de entrada nuevo estaría midiendo por su cuenta. Para y avisa.

## Paso 6 · La tabla se inserta

- [x] Pide punto de inserción y respeta el que pulsas.
- [x] Es una **entidad TABLE nativa** — pínchala: se selecciona como tabla, no
      como un montón de texto. `LIST` dice `ACAD_TABLE`.
- [ ] La tabla es editable como cualquier otra tabla de AutoCAD.
      *Sin probar: no se editó ninguna celda el 2026-09-09.*

**Si sale como MTEXT o como líneas sueltas:** del **lenguaje** (`vla-AddTable`
mal invocado).

## Paso 7 · La tabla dice la verdad

Esto es lo que de verdad se viene a probar. Es más importante que los seis
pasos anteriores.

- [ ] **VT6/2 no trae NINGUNA de las dos cifras** — ni la interior ni la
      exterior (criterio firmado `C-2`: un solape puede caer a caballo entre las
      dos). Trae el motivo: los 8,47 m² dibujados dos veces, con las dos
      magnitudes (74,37 suma de piezas / 65,89 superficie real).
      **SIN PROBAR, y es lo que falta.** `V5.dxf` mide sus 3 viviendas de 3, así
      que el camino de la vivienda bloqueada —las dos celdas «no se publica», la
      fila fusionada del motivo, el total de planta ausente— no se ha ejecutado
      **ni una sola vez**. Es el trozo de código con más ramas y el que nadie ha
      visto funcionar. Se prueba con `ejemplo.dxf`.
- [ ] **No hay cifras de planta**, y la tabla dice qué vivienda lo bloquea.
      *Idem: sobre `V5.dxf` la planta sí totaliza, y totalizó bien.*
- [x] **No aparece por ningún lado una «superficie útil total»** que sume
      interior y exterior. Si aparece, alguien ha reintroducido el campo que
      `C-1` retiró, y es el hallazgo más grave que puede salir de esta prueba.
      *Dos columnas separadas, sin fila de suma. `C-1` se respeta.*
- [x] **La marca de borrador está** («Borrador para revisión de un colegiado»,
      `C3`) y **no hay forma de quitarla** desde el comando.
- [x] Ninguna celda trae un número que no venga del servidor. Ninguna celda
      vacía sin motivo escrito. *Sobre las 8 cifras de `V5.dxf`.*

**Si aparece un número inventado o una omisión silenciosa, el prototipo ha
fallado en lo único que no era negociable.** Anótalo y para.

## Paso 8 · Formato legible

**FALLÓ EL 2026-09-09. Corregido el 2026-09-10, sin volver a ejecutar.**

- [ ] Se lee a la escala del plano, sin hacer zoom.
- [ ] Los motivos largos no se salen de la celda ni se cortan a mitad de palabra.
- [ ] La tabla no tapa el dibujo.

Del **lenguaje**, y es lo último que hay que arreglar. Un formato feo con las
cifras bien es un prototipo que ha funcionado.

> **Qué pasó.** Las columnas se creaban con un ancho fijo —16, 12 y 12 unidades
> multiplicadas por la escala del dibujo— sin mirar qué texto iba dentro. El
> texto no cabía y AutoCAD lo partió **letra a letra en vertical**: la cabecera
> «Útil interior (m²)» salía como una columna de letras sueltas y las cifras se
> rompían en dos líneas. Las filas, que llevaban un alto fijo de 1 unidad sin
> relación con el tamaño del texto, quedaron descompensadas alrededor.
>
> Un formato feo con las cifras bien sigue siendo un prototipo que ha
> funcionado, y este funcionó. Pero **esto no era feo: era ilegible**, y una
> tabla ilegible no se le puede enseñar a un arquitecto, que es para lo que
> existe el paso 9.
>
> **Qué se ha cambiado** (`am:ancho-columna`, `am:altura-de-texto`,
> `am:lineas-de`): el ancho de cada columna sale ahora de la cadena más larga
> que de verdad ha caído en ella —cabecera, nombre de vivienda o cifra, lo que
> sea más largo— multiplicada por la altura del texto; la altura de fila sale de
> la altura del texto y no de una constante; y la altura del texto se **lee** de
> la tabla después de fijarla, porque si el estilo de texto del plano tiene
> altura fija, esa gana y calcular el ancho con la otra volvería a partir el
> texto. Las dos filas fusionadas (el motivo y la marca de borrador) sí se
> parten en varias líneas, que es lo suyo, y se les calcula el alto.
>
> **Qué hay que volver a mirar cuando se abra AutoCAD**, en este orden: que la
> cabecera larga de la tercera columna entre en una o dos líneas y se lea; que
> ninguna cifra se parta; que la marca de borrador ocupe dos líneas y no doce; y
> que la tabla entera tenga un tamaño sensato al lado de la planta —el texto se
> pide de 0,25 m, que a 1:100 son 2,5 mm de papel, y si sale un sello diminuto o
> un cartel enorme el problema está en `am:escala-de-dibujo` y en el `INSUNITS`
> de ese plano, no en el ancho de columna.

## Paso 8 bis · El cuadro del arquitecto (2026-09-10 — **SUSTITUIDO** por el 8 ter)

> **SUPERADO el 2026-09-11, en AutoCAD 2027, sobre `v1plantas.dxf`, con la
> v2.0.2.** Las diez cifras en sus filas, las seis celdas intactas, la marca
> debajo del cuadro sin solapar y la tabla con sus 14 filas. Hicieron falta
> **tres intentos**: el primero no escribió nada (servidor antiguo), el segundo
> escribió «superficie util» en las ocho filas (el rótulo salía del orden de
> llegada de los textos) y el tercero pintó la marca encima del cuadro y luego
> reventó al colocarla, dejando cifras sin advertencia. Cada uno está anotado en
> la casilla que lo cazó.

El comando ya no inserta una tabla propia: rellena la que el plano trae. Lo de abajo sustituye a los pasos 6 a 8
cuando se pruebe `archmuse.lsp` v2.0.0, y **se prueba con `v1plantas.dxf`**, que
es el plano cuyo cuadro se ha usado para escribirlo.

- [ ] El comando **encuentra el cuadro** y dice su tamaño («14 filas x 4
      columnas»). Si no lo encuentra, se para y **no inserta ninguna tabla**.
- [ ] **Enseña el reparto antes de tocar nada** y pide confirmación. Contestar
      «No» tiene que dejar el plano exactamente como estaba.
- [ ] Las celdas que escribe son las 10 del reparto conocido de `VT1/3`:
      salón + cocina 21,90 · pasillo 0,00 · dormitorios 12,72 / 8,48 / 8,53 ·
      baño 4,01 · aseo 3,14 · vestíbulo 0,00 · tendedero 4,22 · TOTAL SUP.
      INTERIOR 58,78.
- [ ] **`terraza 1` y `terraza 2` se quedan vacías**, con su motivo en la línea
      de comandos. Ninguna recibe la cifra de la otra.
- [ ] **`VIVIENDA TIPO` conserva `VT1 /3`**: la celda que él ya rellenó no se
      toca.
- [ ] **Ninguna celda lleva `N/D`** ni ningún texto de ArchMuse: lo que no se
      puede rellenar se queda como estaba.
- [ ] La marca de borrador está **en la capa `ARCHMUSE - BORRADOR`**, debajo del
      cuadro, y **la tabla tiene las mismas filas que antes** — si ha crecido una
      fila, alguien ha metido la marca dentro y eso le cambia la maquetación.
- [ ] **La marca no solapa ninguna celda del cuadro.** Cae por debajo del borde
      inferior de la tabla, con margen, no sobre las primeras filas.
      *Falló el 2026-09-11: se colocaba desde el punto de inserción de la tabla,
      que es su esquina **superior** izquierda, así que «debajo» la dejaba encima
      y tapaba tres de las filas recién rellenadas — las de arriba, que son las
      que primero se miran.*
- [ ] **Su texto no excede el ancho de la tabla.** Se ajusta a él y parte en las
      líneas que haga falta.
      *Falló el mismo día: ancho fijo de 60 caracteres, y el texto se salía de la
      pantalla por la derecha.*
- [ ] **Se lee a la misma escala que el cuadro.** Su altura de texto sale de una
      celda de la tabla; si se ve al triple de tamaño que las cifras, la está
      calculando en vez de leerla.
- [ ] **Un solo `UNDO`** deshace todo lo escrito.
- [ ] Se lee a la escala del plano, sin hacer zoom.

**Si escribe una cifra en la fila equivocada, para y avisa.** Es el único fallo
de esta capacidad que no se ve leyendo el resultado: el cuadro queda cuadrado y
mal, y eso llega al visado.

## Paso 8 ter · El cuadro propio de ArchMuse (desde el 2026-09-12, `.lsp` 3.0.0)

> **Escrito a ciegas, sin AutoCAD delante.** El riesgo lo asumió Pablo el
> 2026-09-12. Todo lo del servidor está probado —232 celdas sobre
> `plantasimple.dxf`, 17 tests—; lo de aquí no se ha ejecutado nunca.
>
> **Sustituye al paso 8 bis.** El comando ya no rellena tu cuadro: dibuja el
> suyo al lado. Lo del 8 bis sigue valiendo como historia de lo que se probó.

**Con qué probarlo, en este orden:** `v1plantas.dxf` (un cuadro, el caso
simple), `plantasimple.dxf` (25 cuadros, el caso de verdad) y `V5.dxf` (sin
cuadro, que es el que antes se rendía).

### Lo que hay que mirar

- [ ] **1. Tu cuadro está intacto.** Es la comprobación que manda sobre todas
      las demás. Abre dos de tus cuadros y mira celda a celda: tiene que estar
      **exactamente** como estaba. Si ha cambiado una sola, para y avísame.
- [ ] **2. Aparecen tantas tablas de ArchMuse como cuadros emparejados.** En
      `plantasimple.dxf` deberían ser **22** —no 25: tres declaran `VT11 /2 PMR`,
      `VT13 /3 FN` y `VT16 /3 FN`, y esos no se emparejan a propósito—.
- [ ] **3. Ninguna cae encima de un cuadro tuyo ni de dibujo importante.** El
      punto se propone a la derecha del tuyo; si no te vale, se mueve con el
      ratón antes de dibujar.
- [ ] **4. Las filas de mi cuadro son las tuyas**, con tu redacción —incluida
      `EXPACIOS INTERORES`, que se copia con su errata a propósito—. En
      `V5.dxf`, que no tiene cuadro, las filas son las de ArchMuse y la tabla lo
      dice.
- [ ] **5. Las cifras son mías, no tuyas.** Se distinguen a simple vista: yo
      escribo `23,85 m²` —coma y espacio— y tú `23.85m²`. **Si ves una cifra
      con punto dentro de mi tabla, es un fallo grave**: significa que he
      copiado un número tuyo y lo he firmado como medido (`C-11`).
- [ ] **6. Las casillas sin cifra llevan una marca `(1)`, `(2)`… y su motivo
      está al pie de la tabla.** Ninguna casilla muda.
- [ ] **7. La marca de borrador está**, debajo de MI tabla, en su capa.
- [ ] **8. Un solo `UNDO` lo quita todo.**
- [ ] **9. Compara.** Pon los dos cuadros lado a lado y mira si alguna cifra no
      cuadra. Eso es para lo que existe esto, y es tu trabajo, no el mío.

### Y de paso, la pregunta de `D-7` que sigue abierta

- [ ] **¿Los nombres de estancia son nombres o cifras?** Al medir
      `plantasimple.dxf`, si en vez de «Salón/cocina» ves «21.90m²», es que
      `ssget` devuelve los textos en otro orden que el lector del DXF. **Es la
      única forma de saberlo** y decide si hace falta criterio o no.

### Si algo falla

El `.lsp` no se ha ejecutado nunca. Lo más probable, por orden: que
`vla-AddTable` no acepte el número de filas, que `vla-MergeCells` falle en las
notas al pie, o que la tabla salga de un tamaño absurdo porque
`am:escala-de-dibujo` no acierte con las unidades de ese plano. Los tres dejan
rastro en la línea de comandos; cópialo tal cual.

---

## Paso 8 quater · La plantilla fija en una ventana (desde el 2026-09-13, `.lsp` 3.2.0)

> **Sustituye al 8 ter en los puntos 3, 4 y 6.** La tabla ya no copia las filas
> de tu cuadro: es siempre la misma plantilla de 4 columnas, con una fila por
> estancia medida, y se dibuja **dentro de la ventana que marcas con dos
> esquinas**. Todo lo del servidor tiene tests; **nada de este `.lsp` se ha
> ejecutado** — `getcorner`, `SetColumnWidth`, `SetCellTextHeight` y el estilo de
> texto `ARCHMUSE` con `arial.ttf` son primitivas que nunca han corrido aquí.

- [ ] **1. Ningún `0,00 m²` en ninguna parte** (`D-13`). Ni en la tabla ni en
      las notas. Si ves uno, es el fallo que motivó todo esto: para y avísame.
- [ ] **2. Ninguna palabra partida en vertical** (`D-14`). Mira sobre todo
      `SUPERFICIES UTILES EXT.` y la fila `VIVIENDA TIPO`.
- [ ] **3. Marca una ventana pequeña a propósito.** Tiene que negarse, decir que
      no cabe y pedirte otra (hasta tres veces). No debe dibujar nada.
- [ ] **4. Marca la ventana encima de tu cuadro.** Tiene que negarse también.
- [ ] **5. Filas = estancias dibujadas.** Si tu cuadro pide `pasillo` y el plano
      no tiene pasillo, **no hay fila de pasillo**. Orden: salón/cocina, cocina,
      pasillo, distribuidor, dormitorios, baños, aseos, vestíbulo; lo que no
      reconoce, al final de su bloque.
- [ ] **6. Si hay un trastero (o cualquier cosa que no reconozca), pregunta una
      vez por familia** si es interior o exterior, y la fila aparece donde
      dijiste.
- [ ] **7. Las notas van debajo de la tabla, fuera del marco**, y cada casilla
      vacía tiene la suya.
- [ ] **8. `S. CONSTRUIDA C.` sale vacía, con su nota**, aunque el plano tenga
      la polilínea roja rotulada «Superficie construida cerrada». `C-12` está
      desactivado hasta que lo confirme un arquitecto: **si ves una cifra ahí,
      es un fallo**.
- [ ] **9. Un solo `UNDO` quita tabla, notas y marca.**
- [ ] **10. Los textos de la tabla se leen a la misma altura que tus rótulos**, o
      algo mayor — nunca más pequeños. Si en tu AutoCAD `arial.ttf` se sustituye
      por otra fuente, díselo: los anchos se miden con Arial y llevan un 15 % de
      holgura, no más.

**Añadido el 2026-09-13 (noche), `.lsp` 3.2.1**, tras la primera prueba de la
3.2.0 sobre `v1plantas.dxf`:

- [ ] **11. Con una sola vivienda no pregunta «¿de cuál dibujo el cuadro?».** En
      la 3.2.0 ofrecía «1. VT1/3 / 2. VT1/3»: era la misma tabla leída dos
      veces. Si vuelve a salir una lista con nombres repetidos, es un fallo.
- [ ] **12. Dos viviendas con el mismo rótulo no se ofrecen** (`C-13`): tiene que
      decir «No te ofrezco estas viviendas: hay 2 viviendas rotuladas…» (o «No
      dibujo ningún cuadro:» si no hay otras), **nunca** «esto es un fallo suyo»,
      y ninguna cifra de esas viviendas en ningún sitio.
**Añadido el 2026-09-13 (noche), `.lsp` 3.3.0: estilo, capa y color propios.**
Nada de esto se puede probar fuera de AutoCAD: los tests comprueban lo que pide
el servidor, no lo que dibuja AutoCAD («C-7, otra vez», en los criterios).

- [ ] **13. Las notas quedan DEBAJO del marco**, sin tocar la última fila.
- [ ] **14. Todas las filas del cuerpo miden lo mismo** y el título algo más.
      Para medirlo: selecciona la tabla y mira el alto de dos filas del cuerpo
      en Propiedades. Si una es mucho más alta, AutoCAD sigue agrandándolas.
- [ ] **15. La tabla y las notas están en la capa «ARCHMUSE - CUADRO»**, que es
      blanca o negra según el fondo, **y no amarillas** aunque el color activo
      sea amarillo.
- [ ] **16. Existe el estilo de tabla «ARCHMUSE»** (`ESTILOTABLA`). Si no está,
      no es grave —la tabla lleva sus medidas puestas igualmente—, pero dímelo:
      es la parte del `.lsp` que no se ha podido contrastar con AutoCAD.

**Añadido el 2026-09-13 (noche), `.lsp` 3.4.0: el punto único.** Sustituye a las
casillas 3 y 4 del paso 8 quater, que eran de la ventana de dos esquinas.

- [ ] **17. Pide UN punto**, la esquina de arriba a la izquierda, y ninguna
      segunda esquina. La tabla sale del tamaño que necesita, con el texto a la
      altura de tu cuadro (0,09 en tus planos). **No debe decir nunca «marca una
      ventana mayor».**
- [ ] **18. Marca el punto encima de tu cuadro**: tiene que decir que la tabla
      pisaría tu cuadro, pedirte otro punto y no dibujar nada hasta que lo des.

**Añadido el 2026-09-13 (noche), `.lsp` 3.4.1**, porque la 3.4.0 falló al dibujar
sin decir por qué:

- [ ] **19. Si no dibuja, la línea dice en qué paso y el mensaje de AutoCAD**:
      «No he podido dibujar la tabla al <paso>: <mensaje>». **Cópiala tal cual.**
- [ ] **20. Si dibuja con avisos**, aparece «La tabla está dibujada, pero esto no
      se ha podido hacer:» y una lista. Cópiala también: dice qué parte del
      estilo, la capa o el color no ha aceptado tu AutoCAD.
- [ ] **21. Antes de nada, mira si la 3.4.0 dejó una tabla suelta** en
      `v1plantas`: aquel mensaje decía «no se ha quedado nada a medias» sin
      comprobarlo.

**Añadido el 2026-09-13 (madrugada), `.lsp` 3.5.0: sin estilo de texto propio.**
La 3.4.1 falló al crear su estilo con `arial.ttf` («Error de archivador»). La
3.2.0 lo creó sin fallar sobre el mismo plano, **y no se sabe por qué**.

- [ ] **22. No aparece ningún estilo de texto «ARCHMUSE» nuevo** (`ESTILO`): la
      tabla usa el estilo de texto de tu cuadro.
- [ ] **23. Ninguna palabra se sale de su casilla.** Los anchos los ha medido
      tu AutoCAD con `textbox`; si alguna se parte o se sale, dímelo con el
      texto exacto: es la parte que no se ha podido comprobar fuera de AutoCAD.
- [ ] **24. Sobre un plano sin cuadro ni rótulos de estancia**, tiene que decir
      que no dibuja la tabla porque no hay estilo del que sacarla, y no dibujar
      nada.

**Añadido el 2026-09-13, `.lsp` 3.6.0: `C-12` firmado, la construida por su
rótulo.**

- [ ] **25. Antes de ejecutar nada, en `v1plantas`**: selecciona la polilínea
      rotulada «Superficie construida cerrada» y la del Dormitorio 3, y apunta
      de cada una **capa, color y handle** (Propiedades). En la copia de ArchMuse
      la construida es `A6188E`, en `00 areas`, y es la única roja; la del
      Dormitorio 3 es `A61769`, naranja por capa. Si tu plano dice otra cosa, es
      más nuevo que esa copia: dilo antes de seguir.
- [ ] **26. Tras «Envío N polilínea(s) de «00 areas»»** aparece otra línea: «Envío
      M polilínea(s) de otras capas». En `v1plantas` M debería ser 1.
- [ ] **27. La fila S. CONSTRUIDA C. dice 73,07 m²** en `v1plantas`, sin nota.
- [ ] **28. Borra (o cambia) el rótulo «Superficie construida cerrada»** y vuelve
      a lanzar el comando: la fila tiene que salir vacía con la nota «el plano no
      rotula ninguna polilínea…». Aunque la polilínea roja siga ahí. Deshaz después.

---

## Paso 9 · La pregunta que hay que hacerle al arquitecto

Con la tabla ya en su plano, delante de él:

1. ¿Esto te ahorra el copiado a mano, o te lo cambia por revisar lo que ha
   escrito el programa?
2. ¿Querrías que escribiera **dentro de tu cuadro existente** en vez de insertar
   una tabla nueva?
3. ¿La marca de borrador te estorba para entregar, o te tranquiliza?
4. **¿Qué son `PMR` y `FN`?** (añadida el 2026-09-12). En `plantasimple.dxf`,
   tres de los 25 cuadros dicen ser de `VT11 /2 PMR`, `VT13 /3  FN` y
   `VT16 /3  FN`, y el plano rotula esas viviendas `VT11/2`, `VT13/3` y
   `VT16/3`. Lo que hace falta saber es una sola cosa: **¿es la misma tipología
   con un calificativo, o es otra vivienda?** Si es lo primero, ArchMuse puede
   emparejarlas; si es lo segundo, tiene que seguir negándose. Hoy se niega, que
   es lo firmado: 3 de 25 cuadros se quedan sin rellenar y se dice por qué.
   **No lo decidimos nosotros** —es vocabulario de su estudio—.

Sus respuestas valen más que los pasos 1-8. Si la respuesta a la 2 es «sí», el
camino bueno no era este prototipo: era `superficies.cuadro_de_vivienda`, que ya
existe (§14.3 del PRD).

---

## Lo que este checklist NO puede comprobar

Escrito aquí para que nadie lo dé por probado:

- **Rendimiento con un plano grande de verdad.** 12 s son los de `ejemplo.dxf`.
  Un plano de estudio con 40 capas y bloques anidados no se ha medido nunca por
  esta vía.
- **Que `ssget` coja lo mismo que el lector Python** en un plano cualquiera.
  Sólo se ha razonado sobre los dos planos reales que hay.
- **En qué ORDEN los devuelve `ssget`, y sobre `plantasimple.dxf` eso importa.**
  Ese plano rotula cada salón con varios MTEXT de la misma capa —el nombre
  repetido dos o tres veces y la cifra de su superficie, todos MTEXT en
  `00 TEXTO`—: 156 recintos tienen más de un texto dentro y 63 tienen tres
  compitiendo. Quién gana lo decide hoy **el orden del recorrido**, y `ssget` no
  garantiza ninguno. Si sale al revés, las estancias se llamarán «21.90m²» en
  vez de «Salón/cocina» —y con ese nombre no se reparte ninguna fila—.
  **Qué mirar en el trial:** al medir `plantasimple.dxf` desde AutoCAD, que los
  nombres de estancia que imprime el comando sean nombres y no cifras. Es la
  única forma de saber en qué orden recorre el AutoCAD de verdad.

  **Y esto va antes de cualquier criterio de desempate**, por decisión de Pablo
  del 2026-09-12: si el orden de `ssget` resulta ser estable, **no hace falta
  criterio ninguno**, y escribir uno sin haberlo mirado sería inventarse un
  problema y un criterio profesional de propina. Está declarado como
  `xfail(strict=True)` en `tests/test_dos_vias_leen_igual.py` —el día que deje de
  fallar, se pone rojo y hay que venir a mirarlo—.
- **Versiones de AutoCAD distintas de la del trial.** `vla-AddTable` existe desde
  hace muchas versiones, pero eso es documentación, no una comprobación. Desde
  el 2026-09-09 hay **una** versión comprobada, AutoCAD 2027, y ninguna más.
- **Que `vla-SetTextHeight`, `HorzCellMargin` y `VertCellMargin` hagan algo.** Se
  añadieron el 2026-09-10 y van dentro de `vl-catch-all-apply`: si alguna no
  existe en una versión, la tabla se dibuja igual con la altura de su estilo. Lo
  que no se sabe es si en 2027 funcionan, porque no se han ejecutado.
- **Un plano cuyo estilo de texto tenga altura fija.** `am:altura-de-texto` está
  escrita para ese caso y es el camino que más falta hace probar, porque es el
  normal en una plantilla de estudio y ninguno de los dos planos de prueba lo
  tiene.
- **Nada en Mac.** El COM de Windows no existe allí. La integración con AutoCAD
  para Mac es un problema entero sin empezar.
