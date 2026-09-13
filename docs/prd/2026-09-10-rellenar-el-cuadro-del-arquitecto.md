# PRD — Rellenar el cuadro que el arquitecto ya tiene dibujado

**Estado:** APROBADO · **Fecha:** 2026-09-10 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo, 2026-09-10

> **Condiciones de la aprobación (textuales).** **Orden estricto de trabajo:
> nada de cuadro hasta que 0 y 1 estén en verde.** Documento independiente, no
> ampliación del de agosto. Arquitectura de escritura aprobada: Python decide
> `(fila, columna, texto)`, LISP transporta y escribe con `vla-SetText`, no
> interpreta. `terraza 1`/`terraza 2` en blanco las dos y `tendedero` sin sumar,
> tal cual. C3 en capa propia debajo del cuadro, **sin añadir filas a su tabla**.
> Celda que no se puede rellenar: **no se escribe nada**, el motivo vive en el
> acta. El fixture con `ACAD_TABLE` **no se intenta con el anonimizador**:
> alternativa a proponer cuando se llegue, no ahora.
>
> **Elevado a criterio firmado:** la objeción sobre `pasillo`/`vestibulo` — el
> `0,00 m²` queda condicionado a que la medición de la vivienda esté limpia — es
> ahora `C-4`. La invariante de §0.2.4 es `C-6`, **permanente**, no un detalle de
> esta tarea. Y la ambigüedad de reparto es `C-5`. Los tres en
> `docs/design/2026-09-08-criterios-firmados-de-medicion.md`.
>
> **Sigue pendiente del arquitecto** (§14.2): la fila «TOTAL S. UTIL(m2)» y qué
> espera cuando el cuadro pide una fila que el plano no dibuja.

## Estado de ejecución

| Tarea | Estado |
|---|---|
| **0 · El contorno agrupador** | **HECHA** 2026-09-10 — `analyzer/parser.py`, `tests/test_contorno_agrupador.py` (9 tests). Test rojo primero, arreglo después |
| **1 · Los escapes `\U+xxxx`** | **HECHA** 2026-09-10 — `analyzer/texto_dxf.py`, `tests/test_escapes_unicode.py` (24 tests) |
| **2 · Emparejamiento y escritura vía LISP** | **HECHA** 2026-09-10, del lado del servidor entero. `analyzer/emparejador_cuadro.py` (17 de 17 campos en los dos cuadros), `analyzer/reparto_cuadro.py` (el reparto y `C-6`), `cuadro_desde_celdas`, el endpoint y `autocad/archmuse.lsp`. **VERIFICADA EN AUTOCAD 2027 el 2026-09-11** con la v2.0.2, sobre `v1plantas.dxf`: 10 celdas con sus cifras, 6 vacías, marca debajo del cuadro, 14 filas, sin crash |
| 2b · El payload perdía el salón | **HECHA**, y no estaba en el plan. `ssget` filtra por el flag de cerrada y en `v1plantas.dxf` ese flag está mal en 2 de 10 — una es el salón. Ahora el cliente manda todo con `cerrada` y `color`, y decide el servidor |

### Orden de trabajo desde el 2026-09-10 (noche), fijado por Pablo

1. **Probar el `.lsp` v2.0.0 en AutoCAD**, con `v1plantas.dxf` y el paso 8 bis
   del checklist. **Nada más hasta que eso pase.** Lista corta para ir tachando
   en `_barrido/PRUEBA-8bis.md`.
2. **`plantasimple.dxf`** — el único proyecto completo del lote, y el que hoy se
   rinde. Dos frentes en este orden:
   a. **Que el usuario pueda dar la capa desde el comando** cuando el heurístico
      no decide. En este plano hay cuatro capas candidatas y ninguna destaca; el
      comando debe dejar decirlo, no rendirse.
   b. **CU-2, cuadro↔vivienda**, con **25 cuadros reales** contra los que
      probarlo por primera vez.
   **Antes de escribir código de (b): abrir `plantasimple.dxf` en AutoCAD y
   comprobar si `vla-get-Columns` devuelve 0** en esas tablas. En el DXF
   declaran `n_cols = 0`; si AutoCAD dice lo mismo, no hay celdas que leer y
   todo (b) cambia de forma.
3. **`C-7`** — que una medición limpia en el servidor no se pueda confundir con
   «ha llegado todo». Ver §0.3.

Con 0 y 1 hechas, `v1plantas.dxf` **publica por fin sus superficies**: cero
impedimentos, ocho piezas, útil interior y exterior con cifra. Antes de hoy esta
vivienda no publicaba ninguna, así que el cuadro habría salido entero en blanco
por mucho que el emparejamiento funcionara.

## 0.0 Por qué la vía AutoCAD es el producto y la vía web es la demo

**Esto no es una preferencia de diseño: es un recuento.** El 2026-09-10 se barrió
la carpeta de proyectos reales del arquitecto (5.352 ficheros,
`_barrido/BARRIDO.md`, fuera del repositorio). De todo eso:

| | |
|---|---:|
| `.dwg` | **70** |
| `.dxf` | 9, de los cuales 4 son copias — **5 planos distintos** |

**El corpus real de un arquitecto está en DWG.** El DXF es un formato de
intercambio: existe cuando alguien exporta a propósito, y los cinco que hay son
justamente los que se exportaron para probar ArchMuse. Los 70 DWG son el trabajo.

`ezdxf` no lee DWG —es un formato binario propietario de Autodesk— así que **la
vía web sólo puede tocar el 6% de lo que el arquitecto tiene**, y sólo después de
que él exporte cada plano a mano.

**La vía AutoCAD no tiene ese problema, y por una razón estructural: no lee un
fichero, lee el dibujo abierto.** Cuando `ARCHMUSE` se ejecuta, AutoCAD ya ha
resuelto el formato; el comando pregunta por entidades, no por bytes. Un DWG, un
DXF, un DWG de 2007 o uno de 2027 son lo mismo desde dentro. **El formato deja de
importar**, y con él desaparece el trabajo de exportar y la mitad de las cosas
que se pierden al exportar.

De ahí el reparto que este PRD fija y que conviene no volver a discutir:

> **La vía AutoCAD es el producto. La vía web es la demo** — sirve para enseñar
> qué hace ArchMuse sin instalar nada, y para el arquitecto que quiere probarlo
> antes de dejarle tocar su dibujo. Las dos miden igual (mismo motor, mismo
> contrato `CAD-2`), pero sólo una llega al fichero en el que se trabaja.

**Consecuencia sobre el soporte de DWG nativo:** deja de hacer falta. Está
anotado como deuda en §14.3 con esa razón, y sólo volvería a ser necesario si
algún día se quisiera una vía **sin AutoCAD delante** — un servidor que procese
una carpeta de planos, por ejemplo. Hoy no es el producto.

---

> **Cambio de objetivo, y viene del usuario real.** Hasta hoy `ARCHMUSE` (el
> comando de AutoCAD, PRD `2026-09-08-integracion-autocad-autolisp.md`)
> **inserta una tabla nueva** con formato de ArchMuse. El arquitecto no quiere
> una tabla nueva: quiere que le **rellenen la suya**, la que su estudio ya
> tiene maquetada, respetando sus filas, sus columnas y su redacción.
>
> No es un cambio de formato. Es un cambio de a quién pertenece el entregable.

## 0.0 bis · Decisión de arquitectura: el servidor corre EN LOCAL

**Decidido por Pablo el 2026-09-11.** El servidor de ArchMuse se instala y se
ejecuta **en el equipo del arquitecto**, no en la nube.

**La razón principal no es técnica: los planos son de sus clientes.** Un DXF de
proyecto lleva el nombre de quien lo guardó, la promoción, a veces la dirección
de la parcela. Subirlo a un servidor nuestro convierte a ArchMuse en el
custodio de documentación ajena y nos mete en una conversación —dónde se guarda,
cuánto tiempo, quién responde de una filtración— que no queremos tener y que el
producto no necesita tener.

Y es el argumento de venta ante un estudio que no nos conoce de nada:

> **Tus planos no salen de tu ordenador.** No hay que fiarse de nosotros, porque
> no nos llega nada.

Lo demás es que sale gratis: **es exactamente lo que ya existe**. El `.lsp` habla
con `localhost:5000` desde el primer día —no por previsión, sino porque era lo
único que podía hacer sin AutoCAD—, así que la arquitectura que hay ya es la
definitiva. No hay nada que rehacer, sólo que empaquetar.

**Encaja con §0.0**: si la vía AutoCAD es el producto, el servidor ya tiene que
estar donde está AutoCAD. Un servidor en la nube sólo tendría sentido para la
vía web, que es la demo.

### NO SE IMPLEMENTA AHORA — deuda, con lo que implicará

Queda pendiente hasta que el cuadro se rellene bien. Lo que habrá que resolver,
anotado ahora para que el día que se haga no se descubra sobre la marcha:

**1. Un instalador único.** Hoy hacen falta tres cosas —Python, el servidor con
sus dependencias, y el `.lsp` cargado en AutoCAD— y un arquitecto no tiene por
qué saber qué es un entorno virtual. Lo que hay que entregar es **un ejecutable
que se instala como cualquier programa**. Implica empaquetar el intérprete con
el código (PyInstaller o equivalente), y ahí aparecen dos cosas que hoy no
duelen: el tamaño (`shapely`, `ezdxf` y `reportlab` no son ligeros) y que
algunos antivirus miran con lupa un `.exe` que abre un puerto.

**2. Que el servidor arranque solo.** Si hay que abrir una consola y teclear
`python app.py`, el producto se usa dos veces. Tiene que estar levantado cuando
el arquitecto teclee `ARCHMUSE` sin que él haya hecho nada — un servicio de
Windows, o que el propio `.lsp` lo arranque al no encontrarlo. La segunda opción
es más simple y tiene una ventaja: el comando ya sabe detectar que no hay
servidor, así que el sitio donde poner «y si no está, lo levanto» ya existe.

**3. Cómo se actualiza.** Es lo que más va a doler y conviene decirlo pronto: con
el servidor en casa del cliente, **cada corrección hay que llevarla a cada
máquina**. Hoy un bug se arregla en un fichero; entonces habrá versiones
distintas en sitios distintos midiendo la misma planta con criterios distintos.
Hará falta, como mínimo, que el comando **diga qué versión tiene delante** — las
`capacidades` que el endpoint ya declara desde el 2026-09-11 son el principio de
eso— y decidir si las actualizaciones se comprueban solas o las lanza él.

**4. Y una consecuencia de producto que no es menor.** Con el servidor en local
**no hay telemetría**: no sabremos cuántos planos se miden, cuáles fallan, ni
qué rótulos aparecen que el vocabulario no reconoce. Todo lo que hemos aprendido
estos dos días salió de mirar planos reales en esta máquina. Con el producto
instalado en cinco estudios, esa información deja de llegar salvo que ellos la
manden a propósito. Es el precio de la promesa, y hay que pagarlo con los ojos
abiertos: **la privacidad que se vende es la misma que nos deja a ciegas.**

---

## 0. Nota de proceso: esto NO es un PRD nuevo del todo

Hay **tres PRDs aprobados** que cubren ya el objetivo «rellenar el cuadro de
superficies del arquitecto»:

| PRD | Estado | Qué cubre |
|---|---|---|
| `2026-08-14-cuadro-de-superficies-autocompletar.md` | Aprobado | La capacidad entera por la vía web: detectar el cuadro, calcular el relleno, exportar una copia |
| `2026-08-19-escritura-protegida-del-dxf-del-cliente.md` | APROBADO | Original intacto y verificado por SHA-256, efecto autorizado, `N/D` nunca convertido en número |
| `2026-08-19-skill-del-cuadro-de-superficies.md` | APROBADO | El procedimiento `superficies.cuadro_de_vivienda` de principio a fin |

**Lo que este documento añade y no está en ninguno de los tres:** que el relleno
ocurra **dentro de AutoCAD, sobre el dibujo abierto y en la tabla de verdad**, y
que el emparejamiento rótulo→fila funcione en **el cuadro del arquitecto, no en
el único cuadro contra el que se escribió**. Lo segundo es un fallo medido, no
una mejora especulativa (§0.1, pregunta 2).

Si prefieres que esto sea una ampliación del PRD del 14-ago en vez de un
documento aparte, es un movimiento de texto: la decisión es tuya y no la tomo
yo. Lo abro aparte porque el cambio de vía (web → AutoCAD) cambia la
arquitectura de la escritura, que es la mitad del documento.

---

## 0.1 Investigación previa — las cuatro preguntas, con las medidas

Todo lo de esta sección está medido sobre `v1plantas.dxf` el 2026-09-10.

**Dónde está el fichero.** No estaba en `_material/`; estaba en
`Desktop\PRUEBA ARCHMUSE DXF\`, junto a `V5.dxf`, `v2s.dxf` y `v3s.dxf`. Copiado
a `_material/v1plantas.dxf` el 2026-09-10 para trabajar, y **fuera del
repositorio**: `_material/` está un directorio por encima del árbol de git, así
que un plano real de cliente no puede colarse en un repositorio público por
descuido. Los tests que lo usan se **saltan** si no está.

### Pregunta 1 — ¿Es un `ACAD_TABLE` real o son líneas y textos sueltos?

**Es un `ACAD_TABLE` real.** Una sola, en `modelspace()`, capa `0`, handle
`D6BDBF`, **14 filas × 4 columnas**. El DXF es `AC1015` (R2000), `$DWGCODEPAGE`
`ANSI_1252`, `$INSUNITS` 6 (metros).

Su contenido está donde el arquitecto lo dejó, y coincide **exactamente** con la
estructura que describiste, incluida la errata de la cabecera —`EXPACIOS
INTERORES`, no `ESPACIOS`—, que importa porque cualquier emparejamiento que
dependa de cómo está escrita esa cabecera ya estaría roto:

|  | col 0 | col 1 | col 2 | col 3 |
|---|---|---|---|---|
| f0 | CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA | | | |
| f1 | EXPACIOS INTERORES | SUPERFICIES UTILES INT. | ESPACIOS EXTERIORES | SUPERFICIES UTILES EXT. |
| f2 | salón + cocina | _(vacía)_ | tendedero | _(vacía)_ |
| f3 | pasillo | _(vacía)_ | terraza 1 | _(vacía)_ |
| f4 | dormitorio 1 | _(vacía)_ | terraza 2 | _(vacía)_ |
| f5-f9 | dormitorio 2, dormitorio 3, baño, aseo, vestibulo | _(vacías)_ | | |
| f10 | TOTAL SUP. INTERIOR (m2) | _(vacía)_ | TOTAL SUP. EXTERIOR (m2) | _(vacía)_ |
| f11 | TOTAL S. UTIL(m2) | _(vacía)_ | | |
| f12 | S. CONSTRUIDA C. | _(vacía)_ | | |
| f13 | VIVIENDA TIPO | VT1 /3 | NUMERO UDS: | _(vacía)_ |

**33 de las 56 celdas están vacías.** Ése es el hueco que hay que rellenar.

**Y ahora la parte que cambia el enfoque, que no es «tabla sí o no» sino «desde
dónde se escribe».** `ezdxf` 1.4.4 carga esa entidad como
`AcadTableBlockContent`: **no tiene `get_text()` ni `get_cell()`**. Lo que sí
hay:

- El texto de las 56 celdas está en **tags de código 1**, en orden de lectura.
  Se leen sin problema.
- Lo que se ve dibujado es un **bloque anónimo `*T633`** con 23 MTEXT y 21 LINE
  — la tabla *renderizada*. Es lo que ya usa `detectar_cuadro_superficies()` a
  través de `virtual_entities()`, y funciona.
- **Escribir en esas celdas desde Python: probado y no funciona.** Sustituí el
  tag de código 1 de la celda (2,1), guardé y reabrí: la celda vuelve vacía. La
  entidad se reserializa desde su propio estado interno y la modificación del
  tag se pierde. Ir más allá sería ingeniería inversa de una entidad
  propietaria de Autodesk, sobre el fichero de trabajo de un cliente.

**Conclusión de la pregunta 1, y es la decisión de arquitectura del documento:**
la tabla se **lee** desde Python y se **escribe** desde AutoCAD. `vla-SetText`
sobre una tabla que ya existe es una llamada de una línea y es lo único que
AutoLISP hace mejor que nosotros: tiene la API que a `ezdxf` le falta. El
reparto queda:

> **Python decide qué número va en qué celda. AutoCAD escribe esa celda.**
> El LISP no interpreta nada: transporta una lista de `(fila, columna, texto)`.

Eso además respeta `D-7` sin discusión: no hay un segundo sitio donde se decida
nada.

### Pregunta 2 — ¿Cómo localizar la fila correcta para cada recinto?

Ya vive en Python, en `analyzer/cuadro_superficies.py`, que es donde tiene que
seguir. El problema es otro: **no generaliza, y está medido cuánto**.

`_ETIQUETA_A_CAMPO` es un diccionario de **cadenas exactas** tomadas de
`v2s.dxf`. Ejecutado hoy sobre `v1plantas.dxf` —el mismo arquitecto, el mismo
estudio, el mismo modelo de cuadro— detecta **11 campos de los 17** que la tabla
pide. Fallan seis, por dos motivos distintos:

**(a) Escapes Unicode sin decodificar.** El DXF guarda las tildes y las eñes
como `\U+00F3` / `\U+00F1`, y `plain_text()` de ezdxf 1.4.4 **no los decodifica**
(comprobado). Nada en `analyzer/` lo hace tampoco. Así que:

- `sal\U+00F3n + cocina` no casa con `SALON + COCINA` → la fila del salón no se
  detecta.
- `ba\U+00F1o` no casa con `BANO` → la fila del baño no se detecta.

**Y el mismo escape rompe el otro lado.** El rótulo del plano es
`Ba\U+00F1o`, que normalizado da `BA\U+00F1O` y **no casa con `\bBANO\b`**. Es
decir: **hoy, en este plano, el baño no se mide** — y eso no es un problema del
cuadro, es un fallo vivo del camino `/medir` con cualquier plano que guarde así
sus rótulos. Es el hallazgo más importante de la investigación y no lo buscaba
nadie. (De paso: «salón + cocina» sí casó en el lado del plano, pero por
casualidad — el patrón es `SALON|COCINA` y acertó por la palabra «COCINA» de
`SAL\U+00F3N/COCINA`. Acertar por suerte cuenta como no estar probado.)

> **Actualizado el 2026-09-10, tras la tarea 1.** Los escapes ya se decodifican
> (`analyzer/texto_dxf.py`), así que de los seis campos que faltaban se han
> recuperado dos: `salon_cocina` y `bano`. **Ahora detecta 13 de 17.** Los cuatro
> que siguen sin detectarse son los del punto (b), que es un problema distinto y
> necesita el emparejador de la tarea 3.

**(b) El arquitecto no escribe dos veces igual.** Entre sus dos cuadros:

| En `v2s.dxf` (lo que el código espera) | En `v1plantas.dxf` (lo que hay) |
|---|---|
| `TOTAL SUP.UTIL INTERIOR (M2)` | `TOTAL SUP. INTERIOR (m2)` |
| `TOTAL SUP.UTIL EXTERIOR (M2)` | `TOTAL SUP. EXTERIOR (m2)` |
| `TOTAL S. UTIL (M2)` | `TOTAL S. UTIL(m2)` |
| `S. CONSTRUIDA CERRADA` | `S. CONSTRUIDA C.` |

Un espacio, un punto y una abreviatura. Un diccionario de cadenas exactas no
sobrevive a esto, y **el siguiente plano volverá a romperlo**: es la vía por la
que esta capacidad se convierte en una que hay que parchear plano a plano.

**Lo que propongo** (detalle en §11, tareas 1-4):

1. **Decodificar `\U+xxxx` antes de normalizar**, en un solo sitio, y aplicarlo
   a los dos lados —rótulo del plano y etiqueta del cuadro—. Arreglar sólo el
   lado del cuadro dejaría el baño sin medir igual.
2. **Sustituir el diccionario exacto por un emparejador** con familia +
   sinónimos + número ordinal, que **declara su confianza**: alta (coincidencia
   inequívoca), media (coincidencia por familia con una sola candidata), o
   ninguna. Lo que no casa con seguridad **no se rellena** y sale en el acta con
   su nombre. Nunca se reparte por orden de aparición.
3. El emparejador vive en Python y se prueba **contra los dos cuadros reales**,
   no contra uno. El criterio de aceptación es que los 17 campos de los dos
   ficheros se detecten, y que un cuadro inventado con etiquetas ajenas no
   invente correspondencias.

### Pregunta 3 — Filas que el cuadro tiene y el plano no, y al revés

**Respuesta corta: es el problema central de esta capacidad, no un caso borde, y
tiene sección propia — §0.2.** Las reglas firmadas (reglas 1-4 de
`analyzer/cuadro_superficies.py`) siguen valiendo, pero medidas contra este plano
se quedan cortas en dos sitios: `0,00 m²` puede ser una mentira si la medición no
está limpia, y una pieza medida sin fila donde ir hoy no tiene salida en el
camino de AutoCAD.

### Pregunta 4 — ¿Sirve `superficies.cuadro_de_vivienda` como base?

**Sirve, y más de lo esperado: no es un caso parecido, es el mismo cuadro.**
Ejecutado hoy sobre `v1plantas.dxf` sin tocar una línea:

- **detecta el cuadro** (por encabezado, reconstruyendo la rejilla desde las
  LINE de esa tabla — no por coordenadas fijas);
- **mide el plano**: capa `00 areas`, 9 recintos, la vivienda `VT1/3`;
- y produce 11 de las 16 celdas.

Lo que se aprovecha entero: la detección, el catálogo cerrado de cuatro estados,
las cuatro reglas de producto, `N/D` nunca convertido en número, el original
intacto verificado por SHA-256, y el acta que dice celda a celda de dónde sale
cada número.

**Lo que no sirve, y hay que decirlo con todas las letras:** la escritura.
`analyzer/cuadro_superficies_export.py` **no rellena el `ACAD_TABLE`** — dibuja
un MTEXT nuevo en modelspace encima del hueco de la celda. Su propio docstring
lo dice sin adornos, y para entregar una copia por la web es una solución
legítima. Pero **no es el encargo de hoy**: un texto superpuesto no es una celda
rellena. Si el arquitecto mueve la tabla, edita una fila o cambia un ancho de
columna, los números se quedan donde estaban y el cuadro queda mintiendo. En su
plano, abierto en su AutoCAD, eso es peor que no rellenarlo.

De ahí la conclusión de la pregunta 1: la escritura se va a AutoCAD, y el módulo
existente se queda **como está** para la vía web.

---

## 0.2 EL PROBLEMA CENTRAL: el cuadro y el plano no dicen lo mismo

Esto no es un caso límite que aparecerá algún día. **Es lo que hay en el plano de
prueba**, y es lo primero que se ve al cruzar las dos listas:

| El cuadro pide (11 filas de pieza) | El plano rotula (8 piezas) |
|---|---|
| salón + cocina | Salón/cocina |
| pasillo | — |
| dormitorio 1 · 2 · 3 | Dormitorio 1 · 2 · 3 |
| baño | Baño |
| aseo | Aseo |
| vestibulo | — |
| tendedero | Tendedero |
| terraza 1 · terraza 2 | Terraza *(una sola)* |

Tres desajustes, y cada uno se resuelve distinto.

### 0.2.1 Lo que hay que saber antes: hoy este cuadro saldría entero en blanco

Antes de repartir nada conviene mirar qué dice hoy la medición de `v1plantas.dxf`.
Dice esto, literalmente:

```
util_interior_m2: null
util_exterior_m2: null
impedimentos:
  - "hay 7,08 m² dibujados dos veces: la suma de las piezas da 74,95 m² y la
     superficie que ocupan realmente es 67,87 m²"
  - "1 pieza(s) no se sabe si son superficie interior o exterior por su rótulo
     («Ba\U+00F1o» 4,01 m²)"
```

**ArchMuse no publica hoy ni una sola superficie de esta vivienda.** Con el
criterio `C-2` firmado, un solape bloquea la vivienda entera. Así que el trabajo
de emparejar filas es necesario pero no suficiente: **si no se resuelven estos
dos impedimentos, la capacidad entrega un cuadro vacío**.

Los dos tienen causa conocida y arreglo distinto:

**(a) El segundo «Tendedero» de 8,63 m² no es un tendedero: es el contorno que
los envuelve.** Medido: cubre el **94,8%** del Tendedero (4,22) y el **92,7%** de
la Terraza (3,32). Es un contorno agrupador, la convención con la que este
estudio dibuja «la zona exterior». El parser tiene `CONTAINMENT_THRESHOLD = 0.9`
y `_discard_container_candidates` para exactamente esto, y **aquí no lo ha
descartado** pese a que los dos porcentajes superan el umbral. Hay que averiguar
por qué antes de tocar el cuadro: mientras eso no se resuelva, este plano y
todos los del estudio con la misma convención quedan bloqueados.

**(b) El «Baño» sin clasificar es el bug de los escapes** (§0.1, pregunta 2).
`Ba\U+00F1o` no casa con `\bBANO\b`, así que la pieza no entra ni en interior ni
en exterior. Se arregla con la tarea 1 y desaparece el segundo impedimento.

> **Nota de arquitectura, a favor:** `medicion.py` **importa** los patrones de
> `cuadro_superficies.py` — `_PATRON_BANO`, `_PATRON_TERRAZA`, etc. No hay dos
> implementaciones del criterio de familia, hay una. Arreglar el escape en ese
> sitio arregla la medición y el cuadro a la vez.

### 0.2.2 Qué se rellena y qué no, fila a fila

Con los dos impedimentos resueltos, esto es lo que propongo que escriba ArchMuse
en el cuadro de `v1plantas.dxf`. La columna «estado» es el catálogo cerrado que
ya existe:

| Fila del cuadro | Qué hay en el plano | Se escribe | Estado |
|---|---|---|---|
| salón + cocina | `Salón/cocina`, una pieza | **21,90 m²** | CALCULADO |
| dormitorio 1 | `Dormitorio 1` | **12,72 m²** | CALCULADO |
| dormitorio 2 | `Dormitorio 2` | **8,48 m²** | CALCULADO |
| dormitorio 3 | `Dormitorio 3` | **8,53 m²** | CALCULADO |
| baño | `Baño` | **4,01 m²** | CALCULADO |
| aseo | `Aseo` | **3,14 m²** | CALCULADO |
| tendedero | `Tendedero` | **4,22 m²** | CALCULADO |
| pasillo | nada | ver §0.2.3 | CERO_REAL *(condicionado)* |
| vestibulo | nada | ver §0.2.3 | CERO_REAL *(condicionado)* |
| terraza 1 | una sola `Terraza` | **nada** | BLOQUEADO |
| terraza 2 | una sola `Terraza` | **nada** | BLOQUEADO |
| TOTAL SUP. INTERIOR | suma de las interiores | sólo si no falta ninguna | CALCULADO / BLOQUEADO |
| TOTAL SUP. EXTERIOR | suma de las exteriores | **nada**, mientras la terraza esté bloqueada | BLOQUEADO |
| TOTAL S. UTIL | — | **nada** — decisión del arquitecto, §14.2 | — |
| S. CONSTRUIDA C. | no se puede medir | N/D | NO_DISPONIBLE |
| VIVIENDA TIPO | ya lo trae: `VT1 /3` | **no se toca** | preexistente |
| NUMERO UDS | el plano rotula `8uds.` | ver §0.2.4 | declarado, no medido |

**«salón + cocina» contra «Salón/cocina» es el caso fácil, y conviene decir por
qué.** La etiqueta del cuadro declara una unión —«salón **+** cocina»— y el
rótulo del plano declara la misma unión con otra grafía. Es la excepción ya
documentada del módulo: para este campo, y sólo para éste, una pieza `Salón`
más una pieza `Cocina`, o una sola `Salón/cocina`, valen igual. El emparejador
nuevo tiene que seguir tratándolo como unión declarada, no como coincidencia de
texto.

**«terraza 1» y «terraza 2» contra una sola `Terraza` se bloquean las dos.**
Escribir 3,32 en «terraza 1» es decidir por el arquitecto cuál de sus dos filas
es la que ha dibujado — y la otra quedaría en blanco insinuando que mide cero,
que es distinto de «no lo sé». Ninguna de las dos cosas la decide un programa.
El motivo que se declara es exactamente ése.

### 0.2.3 `0,00 m²` sólo es honesto si la búsqueda fue completa

La regla 1 firmada dice: pieza que el cuadro pide y la vivienda no tiene →
`0,00 m²` (`CERO_REAL`), porque es un hecho negativo verificado. **Propongo
añadirle una condición, y no lo hago por mi cuenta porque la regla está
firmada.**

El motivo está en este mismo plano: hasta hoy, `Baño` **existía y ArchMuse no lo
veía** por el escape Unicode. Si el cuadro hubiera pedido una fila que ArchMuse
no supiera leer, la regla habría escrito `0,00 m²` en el cuadro del arquitecto
para una habitación que está dibujada. Eso no es un hecho negativo verificado:
es un fallo de lectura con formato de dato.

**Condición propuesta:** `0,00 m²` sólo se escribe cuando la medición de esa
vivienda está **limpia** — sin impedimentos, sin polilíneas descartadas en su
capa, sin piezas sin clasificar y sin piezas medidas sin fila. Si no lo está, la
celda se queda en blanco con el motivo «no se ha encontrado ninguna, pero esta
medición no está limpia: [lo que sea]». Sobre `v1plantas.dxf` tal como está hoy,
esa condición **no se cumple**, y `pasillo` y `vestibulo` se quedarían en blanco
en vez de a cero.

Cuesta un poco de cobertura y compra que ninguna cifra escrita en el plano de
alguien pueda ser una omisión disfrazada de medida.

### 0.2.4 Una pieza medida sin fila donde ir NO desaparece

Es la parte que hoy no existe en ningún sitio, y la que puede hacer daño de
verdad: si una pieza medida no encuentra fila y nadie lo dice, el cuadro queda
**cuadrado y equivocado** — los totales no incluyen esa superficie y nada en el
documento revela que falta.

**Regla de conservación de la medida** (propuesta, y es un invariante
comprobable, no una buena intención):

> Toda pieza medida termina en **exactamente uno** de estos tres sitios: una
> celda del cuadro, la lista de piezas sin fila, o la lista de bloqueos con su
> motivo. Un test recorre las tres listas y comprueba que la unión son todas las
> piezas medidas y que no hay ninguna repetida.

Y las piezas sin fila no son todas iguales. Son tres cosas distintas y se dicen
distinto:

| Tipo | Ejemplo en este plano | Qué se hace |
|---|---|---|
| **Pieza real que el cuadro no contempla** | — (aquí no hay) | No se escribe. Se declara con nombre y superficie, y **el TOTAL correspondiente no se rellena**: un total que no incluye una superficie medida es un total falso |
| **Contorno agrupador tomado por pieza** | el `Tendedero` de 8,63 m² | No es una pieza. Bloquea la vivienda y se declara como lo que es: *«esta polilínea envuelve al Tendedero y a la Terraza — ¿es un recinto o el contorno de la zona exterior?»* |
| **Rótulo sin recinto** | `VT22/1` | Ya se avisa hoy. Se mantiene |

**Dónde se dice**, en los tres sitios y antes de escribir nada:

1. **En la línea de comandos de AutoCAD**, antes de pedir confirmación. El
   arquitecto ve lo que va a pasar y puede cancelar sin que se haya tocado el
   plano.
2. **En el acta**, celda a celda, con el motivo entero.
3. **En el propio cuadro no**: una celda que no se puede rellenar se queda como
   esté y no se le escribe una explicación dentro — el cuadro es suyo y no es
   sitio para los recados de ArchMuse. La marca de esas celdas es la tercera
   pregunta abierta de §14.2.

Y una salida que hay que tratar como fallo, no como resultado: **si no se puede
escribir ninguna celda, el comando no escribe nada y lo dice**. Rellenar tres
celdas de diecisiete y callar las catorce restantes es peor que no haber
empezado.

---

---

## 1. Problema que resuelve

El arquitecto no tiene un problema de tablas: tiene un problema de transcripción.
Su cuadro de superficies ya está maquetado, con sus filas, su redacción y su
sitio en el plano. Lo que hace a mano es **leer el plano y copiar números dentro
de él**, celda a celda, cada vez que cambia una distribución.

Hasta hoy ArchMuse le ofrecía una tabla nueva al lado de la suya. Eso no le
ahorra el trabajo: se lo cambia por otro —comparar dos tablas y copiar de una a
otra— y le mete en el plano un elemento que no es suyo y que su cajetín no
contempla. La petición, textual del arquitecto, es que se rellene **el suyo**.

Es además el hito que `NORTH_STAR_2031.md` describe como «no se exporta nada a
mano», aplicado al sitio donde el arquitecto trabaja de verdad, que es AutoCAD y
no un navegador.

## 2. Usuario afectado

El arquitecto que redacta y firma, trabajando sobre su propio DXF abierto. No es
el usuario objetivo de un horizonte futuro: es la persona concreta que probó
esto el 2026-09-09 y dijo qué le faltaba.

Secundariamente, el estudio: el cuadro maquetado es un activo del estudio —su
formato, su vocabulario, su orden de filas— y una herramienta que lo respeta se
adopta; una que lo sustituye, no.

## 3. Objetivo de negocio

`MOAT_ANALYSIS.md` sitúa el foso en evitar el coste de un rechazo de visado, no
en dibujar bonito. Un cuadro de superficies que no cuadra con los planos es
exactamente ese tipo de detalle. Pero hay un segundo efecto, y para la retención
pesa más:

**Escribir dentro del entregable del arquitecto es la diferencia entre una
herramienta que se prueba y una que se adopta.** Una tabla nueva se borra al
terminar la sesión. Un cuadro relleno se queda en el plano que se entrega.

## 4. Objetivo técnico

Una vez implementado, debe ser cierto que:

1. Con el plano del arquitecto abierto en AutoCAD, `ARCHMUSE` **localiza su
   cuadro** y escribe los valores medidos **en las celdas de esa tabla**, no en
   una tabla nueva ni en textos superpuestos.
2. **Ninguna celda que el arquitecto ya haya rellenado se sobrescribe.**
3. Cada celda escrita corresponde a un recinto medido por el servidor, y el
   emparejamiento rótulo→fila se decide **en Python, en un solo sitio**.
4. Lo que no se puede resolver —ambigüedad, fila sin recinto, recinto sin
   fila— **se declara antes de escribir**, en la línea de comandos, y el
   arquitecto decide si sigue.
5. El emparejamiento funciona sobre **los dos cuadros reales del arquitecto**,
   no sobre uno.
6. Si algo falla a mitad, el cuadro **no se queda a medias con números
   plausibles**.
7. **Conservación de la medida** (§0.2.4): toda pieza medida acaba en una celda,
   en la lista de piezas sin fila, o en la de bloqueos con su motivo. Ninguna
   superficie medida desaparece del entregable sin que se diga.

## 5. Casos de uso

**CU-1 · El caso principal.** Plano abierto, un cuadro, una vivienda. `ARCHMUSE`
mide, empareja, enseña por la línea de comandos qué va a escribir y dónde, pide
confirmación, escribe. El arquitecto ve su cuadro relleno con su formato.

**CU-2 · Varias viviendas, varios cuadros.** Un plano con `VT1/3`, `VT2/2`… y un
cuadro por tipo. Hay que emparejar **cuadro↔vivienda** además de fila↔recinto: en
`v1plantas.dxf` el cuadro dice `VT1 /3` (con espacio) y la etiqueta del plano
`VT1/3` (sin él). Si el emparejamiento no es inequívoco, no se escribe nada.

**CU-3 · Celdas ya rellenas.** El arquitecto ya escribió `VIVIENDA TIPO` →
`VT1 /3`. Se respeta tal cual, no se reformatea, y se dice que no se ha tocado.

**CU-4 · El cuadro no se reconoce.** Un cuadro con otra maquetación, o que no es
`ACAD_TABLE`. El comando lo dice y **no escribe nada** ni ofrece insertar una
tabla propia como consuelo.

**CU-5 · Sin AutoCAD.** La vía web sigue como está: copia del DXF con el MTEXT
superpuesto. No se rompe, no se cambia, y se documenta que son dos caminos con
dos calidades distintas de resultado.

## 6. Casos límite

- **Escapes `\U+xxxx` en rótulo o en etiqueta.** Medido en este plano. Se
  decodifican; si tras decodificar sigue sin casar, no se rellena.
- **La errata del arquitecto** (`EXPACIOS INTERORES`). El emparejador no puede
  depender de la cabecera de grupo: sólo de la etiqueta de la fila.
- **Dos filas para una pieza, dos piezas para una fila, fila sin pieza, pieza
  sin fila.** No son casos límite: son **el problema central**, y están
  resueltos uno a uno en §0.2, con la regla de conservación de la medida.
- **Cuadro con filas que ArchMuse no entiende.** Se dejan intactas y se listan.
- **Contorno agrupador tomado por recinto.** Medido en este plano (§0.2.1). Hoy
  bloquea la vivienda entera y **no está resuelto**: es la tarea 0 del plan.
- **Unidades.** `$INSUNITS` = 6 (metros) en este plano, pero el cuadro pide `m2`
  y el criterio de escala ya existe (`analyzer/escala.py`). Si la unidad no se
  puede saber, se para y se pregunta — regla 1 del procedimiento de la Skill.
- **La tabla está dentro de un bloque o en espacio papel.** En este plano está en
  modelspace; si no lo estuviera, el comando lo dice en vez de no encontrarla.
- **AutoCAD LT.** Sin COM no hay comando. Ya está resuelto y avisado.

## 7. Flujo del usuario

1. El arquitecto abre su plano y teclea `ARCHMUSE`.
2. El comando detecta la capa de recintos y **el cuadro**, y dice qué ha
   encontrado: *«Cuadro de superficies detectado, 14 filas, vivienda VT1 /3»*.
3. Mide (servidor) y empareja (servidor).
4. **Enseña el reparto antes de tocar nada**: qué celda va a llevar qué número,
   qué filas se quedan en blanco y por qué, y qué recintos medidos no tienen
   fila.
5. El arquitecto confirma, o cancela sin que se haya escrito nada.
6. Se escriben las celdas. El comando dice cuántas ha escrito y cuántas ha
   dejado.

## 8. Criterios de aceptación

- [ ] Sobre `v1plantas.dxf`, el emparejador detecta **los 17 campos** del cuadro,
      incluidos `salón + cocina`, `baño` y los cuatro de totales/construida.
- [ ] Sobre `v2s.dxf` sigue detectando los suyos: la generalización **no rompe**
      el cuadro contra el que se escribió el código original.
- [ ] El rótulo `Ba\U+00F1o` se mide como baño. (Hoy no se mide: es un bug vivo.)
- [ ] `terraza 1` y `terraza 2` quedan **en blanco con motivo** al haber una sola
      terraza. Ninguna recibe la cifra de la otra.
- [ ] El contorno de 8,63 m² **no ocupa la fila `tendedero`** ni se suma a
      ninguna otra: o se reconoce como contorno, o bloquea y se dice por qué.
- [ ] **Conservación de la medida**: un test comprueba que las nueve piezas
      medidas están, cada una y sin repetirse, en una celda, en la lista de
      piezas sin fila o en la de bloqueos. La suma de las tres listas es el
      total medido.
- [ ] `pasillo` y `vestibulo` **no reciben `0,00 m²` mientras la medición de la
      vivienda no esté limpia** (§0.2.3).
- [ ] `VIVIENDA TIPO` conserva `VT1 /3` exactamente como está.
- [ ] Ninguna celda recibe un número que no venga de una medición del servidor.
- [ ] El reparto completo se enseña **antes** de escribir, y cancelar no deja
      nada escrito.
- [ ] Si no se puede escribir ninguna celda, **no se escribe ninguna** y el
      comando lo dice.
- [ ] Un test compara, celda a celda, el resultado contra una verdad conocida
      del plano.

## 9. Riesgos

**R-1 · Escribir en el fichero de trabajo del cliente, en vivo.** Es la
diferencia de fondo con todo lo anterior: la vía web trabaja sobre una copia y
verifica el SHA-256 del original; aquí se escribe en el dibujo abierto. La red
de seguridad no puede ser un hash: es `UNDO` de AutoCAD, la confirmación previa
y no escribir nunca una celda que ya tenía contenido. **Esto merece su propia
decisión explícita antes de implementar.**

**R-2 · El emparejamiento generalizado puede acertar de más.** Un emparejador
tolerante que rellena la fila equivocada es peor que uno estricto que no rellena.
Mitigación: confianza declarada, y en caso de duda no escribir.

**R-3 · Compite con el PRD del 08-sep, que está a medias.** El comando
`ARCHMUSE` ejecutado el 2026-09-09 tiene el camino de vivienda bloqueada **sin
ejecutar ni una vez**, y la corrección del ancho de columna sin volver a probar.
Este PRD **reemplaza el destino** de esa tabla: si se aprueba, la tabla nueva
deja de ser el entregable y parte de esa deuda deja de importar. Conviene
decidirlo antes de gastar otra sesión en ella.

**R-4 · Dos calidades de resultado para lo mismo.** Con AutoCAD se rellena la
tabla; sin AutoCAD, se superpone un MTEXT. Es una diferencia real que hay que
contar al usuario, no esconder.

**R-5 · `ACAD_TABLE` es una entidad propietaria.** Se lee con `virtual_entities`
y se escribe con la API de AutoCAD. Cualquier atajo por debajo (tocar tags a
mano) ya se ha probado y no funciona; volver a intentarlo es tiempo perdido
sobre el fichero de un cliente.

## 10. Impacto sobre módulos existentes

| Fichero | Qué le pasa |
|---|---|
| `analyzer/cuadro_superficies.py` | **Cambia**: `_ETIQUETA_A_CAMPO` deja de ser un diccionario exacto; entra la decodificación de escapes |
| `analyzer/parser.py` | **Cambia**: `_texto_de` decodifica `\U+xxxx`. Toca a todo el que lee rótulos |
| `analyzer/cuadro_superficies_export.py` | **Nada.** Sigue siendo la vía web |
| `app.py` | Ruta nueva o ampliación de `/api/medicion-geometria` para devolver el reparto por celdas |
| `autocad/archmuse.lsp` | **Cambia de propósito**: de `vla-AddTable` a `vla-SetText` sobre la tabla existente |
| `agente/skills/superficies.py` | Sin cambio funcional; hereda la mejora del emparejador |

**Consumidores indirectos:** todo lo que lee rótulos de estancia depende del
punto 2 (`parser._texto_de`). Es un cambio pequeño con alcance ancho, y por eso
va en su propia tarea, con la suite entera como red.

## 11. Plan de implementación

| # | Tarea | ~ |
|---|---|---|
| **0** | **Averiguar por qué `_discard_container_candidates` no descarta el contorno de 8,63 m²** que cubre el 94,8% del tendedero y el 92,7% de la terraza. Sin esto, este plano —y todos los del estudio con la misma convención— quedan bloqueados y el cuadro sale vacío | 2 h |
| 1 | Decodificar `\U+xxxx` en un solo sitio + test con los dos ficheros reales | 1 h |
| 2 | Aplicarlo en `parser._texto_de` y comprobar que el baño de `v1plantas` se mide | 1 h |
| 3 | Emparejador de etiquetas con familia, sinónimos y confianza declarada | 2 h |
| 4 | Cambiar `_ETIQUETA_A_CAMPO` por el emparejador; los 17 campos en los dos cuadros | 1,5 h |
| 5 | Emparejar cuadro↔vivienda (`VT1 /3` ↔ `VT1/3`), sin adivinar | 1 h |
| 6 | Endpoint: devolver el reparto como lista de `(fila, columna, texto, motivo)` | 1,5 h |
| 6b | Regla de conservación de la medida: las tres listas y su test invariante | 1 h |
| 7 | Fixture anónimo derivado de `v1plantas.dxf`, **con su `ACAD_TABLE`** | 2 h |
| 8 | `archmuse.lsp`: localizar el cuadro y escribir con `vla-SetText` | 2 h |
| 9 | `archmuse.lsp`: enseñar el reparto y pedir confirmación antes de escribir | 1 h |
| 10 | Marca `C3` — **sólo si se aprueba §14.2** | 1 h |

**~17 h.** La tarea 0 va primero: mientras no esté, las demás no tienen sobre qué demostrarse — el cuadro saldría vacío igual. Las tareas 0-7 son de servidor y se prueban sin AutoCAD. Las 8-10 no.

> **Aviso sobre la tarea 7.** El anonimizador actual (`derivar_fixture_anonimo.py`)
> **no copia entidades: reconstruye el plano** desde los polígonos leídos. Un
> `ACAD_TABLE` no sobrevive a eso, igual que no sobrevive el flag de cerrada
> (medido el 2026-09-10, ver `PROGRESS.md`). O se amplía el anonimizador para
> copiar la tabla, o el fixture se construye a mano. **Es la tarea con más
> riesgo de las diez** y conviene hacerla antes que la 8.

## 12. Plan de pruebas

- Unitarias del decodificador y del emparejador, con las etiquetas reales de los
  **dos** cuadros y con etiquetas ajenas que no deben casar.
- Golden-master del reparto sobre `v1plantas.dxf`: las 16 celdas con su estado y
  su motivo, comparadas contra una verdad escrita a mano leyendo el plano.
- Regresión: la suite entera (1.416 tests) tras la tarea 2, que es la de alcance
  ancho.
- En AutoCAD, con el checklist: que no se sobrescriba ninguna celda con
  contenido, que cancelar no deje nada, y que `UNDO` deshaga en un solo paso.

## 13. Métricas de éxito

1. **Celdas rellenas sin retoque** sobre el total de celdas de valor, en planos
   reales. Objetivo: >80% en un cuadro de una vivienda medible.
2. **Cero celdas mal emparejadas.** No es una métrica de porcentaje: una sola
   invalida la capacidad.
3. **El arquitecto entrega el plano con el cuadro relleno por ArchMuse.** Es la
   única métrica que importa de verdad; las otras dos son cómo se llega.

## 14. Motivos para NO implementarlo, y las tres decisiones que no son mías

### 14.1 Motivos para no hacerlo

- **Un cuadro maquetado por estudio.** Este PRD generaliza de uno a dos cuadros
  del mismo arquitecto. El tercero, de otro estudio, puede no parecerse en nada,
  y la capacidad se convertiría en «adaptar ArchMuse a cada cliente». Antes de
  la tarea 3 conviene mirar un cuadro de otro estudio, aunque sea uno.
- **La vía web ya entrega algo.** Si el arquitecto acepta la copia con el MTEXT
  superpuesto, esto es mucho trabajo por una diferencia de calidad. **No lo
  acepta**: es literalmente lo que ha pedido cambiar. Pero conviene tenerlo
  escrito.
- **Escribir en vivo en el fichero abierto** (R-1) es el mayor salto de riesgo
  que ha dado el producto. Se puede posponer entregando el reparto como una
  lista que el arquitecto pega a mano — feo, y probablemente inútil.

### 14.3 DEUDA APUNTADA: DWG nativo, y por qué no hace falta

70 de los 75 planos del arquitecto son DWG y `ezdxf` no los lee. La lectura
directa de DWG —con `ODA File Converter`, con `dwg2dxf`, o con una librería de
pago— se ha valorado y **se descarta por ahora, a propósito**.

El motivo no es el coste: es que **la vía AutoCAD la hace innecesaria para el
producto** (§0.0). El comando lee el dibujo abierto, y ahí el formato ya está
resuelto por AutoCAD. Añadir un conversor sería mantener una segunda forma de
leer los mismos planos, con su propia lista de cosas que se pierden al convertir,
para un camino —la vía web— que es la demo.

**Cuándo volvería a hacer falta**, y conviene tenerlo escrito para reconocerlo el
día que pase:

- si se quisiera **procesar planos en lote sin AutoCAD delante** (una carpeta, un
  servidor, un visado automático);
- si un cliente no tuviera licencia de AutoCAD y usara otro CAD que exporte DWG;
- o si el plugin nativo .NET se descartara y la vía web volviera a ser el
  producto.

Ninguna de las tres es hoy.

### 14.4 LÍMITE APUNTADO: ArchMuse ve **un** cuadro por plano (2026-09-12)

`cuadro_superficies.detectar_cuadro_superficies` devuelve **el primer**
`ACAD_TABLE` con el título. Al correr `CU-2` contra `plantasimple.dxf` se ha
medido que ese plano tiene **25**, uno por vivienda —y es el único proyecto
completo del lote—. **Varios cuadros por plano no es un caso límite: es la forma
normal de un proyecto de verdad.**

Por la vía del comando no se nota —el cliente manda las celdas del cuadro que el
arquitecto ha elegido—. Por la vía web **no es una pérdida muda**: `coherencia`
mete el contraste en `no_comprobado` en cuanto hay más de una vivienda. Lo que
está mal es **el motivo que da**: dice *«un cuadro describe una sola vivienda»*
cuando lo cierto es que **hay 25 cuadros y se ha leído 1**. `C-6` se cumple de
forma; el arquitecto se lleva la impresión de que el problema es su plano.

**Lo mínimo, cuando se toque:** que el barrido viva en `cuadro_superficies.py`
—no en un test ni en un script, que sería una segunda implementación del
criterio (`D-7`)— y que, mientras haya uno solo, se **declare** cuántos hay.
Apuntado el 2026-09-12 con la medición hecha; no implementado.

### 14.2 Las tres que decide el arquitecto, no yo

**(1) La fila «TOTAL S. UTIL(m2)».** No la relleno y no propongo criterio. Lo
que sí aporto es que **esta pregunta ya se contestó una vez**: el criterio `C-1`,
firmado el 2026-09-07 y recogido en
`docs/design/2026-09-08-criterios-firmados-de-medicion.md`, dice que la útil
interior y la exterior **no se suman en una sola cifra**, porque el cómputo de
terrazas y tendederos (¿100%? ¿50%? ¿fuera?) es criterio del técnico que firma.
El código ya lo aplica: deja la celda en `N/D` con el motivo escrito, no en
blanco, «porque una celda vacía se lee como *ArchMuse no ha sabido*, y aquí sí ha
sabido: ha decidido no decidir».

Pero su cuadro **tiene esa fila**, y la tiene porque él la usa. Las dos cosas no
encajan solas. La pregunta para él, tal cual:

> Su cuadro tiene una fila «TOTAL S. UTIL(m2)» que suma interior y exterior.
> El criterio que usted validó el 7 de septiembre dice que esas dos magnitudes
> no se suman. ¿Cuál de las tres?
> **(a)** Dejarla en blanco / `N/D` con el motivo, y la rellena usted a mano.
> **(b)** Rellenarla con un criterio de cómputo que usted fija ahora
> (100%, 50%, otro) y que quedaría escrito y aplicado siempre igual.
> **(c)** El criterio `C-1` cambia: en su cuadro esa fila sí es una suma simple.

Hasta que conteste, la celda **no se toca** y el motivo va en el acta.

**(2) Dónde va la marca de borrador `C3`.** Vinculante, y ahora escribimos dentro
de su maquetación, donde no sobra sitio. Tres opciones, con mi recomendación,
**sin implementar ninguna hasta que la apruebes**:

| | Dónde | A favor | En contra |
|---|---|---|---|
| **(a) Recomendada** | MTEXT en **capa propia** (`ARCHMUSE - BORRADOR`), justo debajo del cuadro y anclado a él | No toca ni una celda ni una línea de su tabla; él puede **apagar la capa para imprimir** sin borrar nada; es el mismo mecanismo que ya usa `marca_borrador.estampar_dxf()` en la vía web | Está fuera de la tabla: si alguien recorta el cuadro, la marca no viaja |
| (b) | Una fila añadida al final de la tabla | La marca viaja con el cuadro pase lo que pase | **Le cambia la maquetación**, que es exactamente lo que ha pedido que no hagamos. Descartada salvo que él la pida |
| (c) | Sólo en el acta/PDF, nada en el plano | No toca el plano | **No cumple `C3`**: el plano sale sin marca. Descartada |

La diferencia con la vía web es dónde se ancla: `estampar_dxf()` la pone bajo
`$EXTMIN` (la esquina del dibujo entero). Aquí propongo **bajo el cuadro**, para
que se lea junto a los números que califica.

**(3) Con qué marca se queda una celda que no se puede rellenar.** Sale de §0.2 y
no la decido porque cambia lo que aparece escrito en su documento.

La vía web escribe `N/D` en esas celdas, con un argumento bueno: «una celda vacía
se lee como *ArchMuse no ha sabido*». Pero ese argumento se escribió para un
cuadro que rellenaba ArchMuse entero. **Aquí el cuadro es suyo y la celda vacía
es su estado normal**: es lo que él rellenaría a mano. Escribirle `N/D` en seis
celdas es meter texto de ArchMuse en su entregable.

| | Qué se escribe en la celda | A favor | En contra |
|---|---|---|---|
| **(a) Recomendada** | **Nada.** La celda se queda como estaba, y el motivo va en la línea de comandos y en el acta | Su documento sale sin una palabra que no sea suya; puede rellenarla a mano sin borrar antes | Mirando sólo el plano no se distingue «no lo sé» de «no lo he mirado» |
| (b) | `N/D` | Coherente con la vía web; ninguna celda queda muda | Es texto de ArchMuse dentro de su cuadro, y hay que borrarlo para escribir encima |
| (c) | Un guion `—` | Más discreto que `N/D` y marca que se ha mirado | Sigue siendo texto que él no ha escrito, y no dice el motivo |

Recomiendo **(a)** por coherencia con lo que ha pedido —que el cuadro siga siendo
suyo— y porque el motivo no se pierde: está en la línea de comandos antes de
escribir y en el acta después. Si él prefiere ver la marca en el plano, (b) y (c)
son un cambio de una línea.

---

## Anexo — De dónde sale cada cifra de este documento

Todo medido el 2026-09-10 sobre
`C:\Users\<usuario>\Desktop\PRUEBA ARCHMUSE DXF\v1plantas.dxf`, con `ezdxf` 1.4.4 y
el propio `analyzer/` del repositorio:

- `ACAD_TABLE`, 14×4, modelspace, capa `0`, handle `D6BDBF`; bloque de dibujo
  `*T633` (23 MTEXT + 21 LINE); 56 tags de código 1, 33 celdas vacías.
- Escritura por sustitución de tag de código 1: probada, **no sobrevive a
  guardar y reabrir**.
- `detectar_cuadro_superficies()`: detecta el cuadro y devuelve **11** celdas de
  valor de **17**.
- `parser.leer_plano()`: capa `00 areas`, **9 recintos**, unidad `VT1/3`
  (etiqueta suelta `VT22/1` sin recintos). Salón/cocina 21,900 · Dormitorio 1
  12,725 · Dormitorio 2 8,483 · Dormitorio 3 8,534 · Tendedero 4,220 · Aseo
  3,136 · Baño 4,006 · Terraza 3,325 · Tendedero 8,627 m².
- **El noveno recinto es un contorno agrupador:** el «Tendedero» de 8,627 m²
  cubre el **94,8%** del Tendedero de 4,220 y el **92,7%** de la Terraza de
  3,325 (intersecciones de 3,999 y 3,083 m²). `CONTAINMENT_THRESHOLD` vale 0,9
  y aun así no se ha descartado.
- `medicion.medir_planta()` sobre este plano: `util_interior_m2` y
  `util_exterior_m2` valen **`null`**. Dos impedimentos: 7,08 m² dibujados dos
  veces (74,95 de suma contra 67,87 de superficie real) y una pieza sin
  clasificar (`Ba\U+00F1o`, 4,01 m²).
- Rótulos en `00 areas` que no son de estancia y hoy no van a ningún recinto:
  «superficie util» ×6, «superficie util exterior» ×2, «Superficie construida
  cerrada», «Superficie construida exterior». Y en `00 TEXTO`: `VT1/3`,
  `VT22/1`, `8uds.`, `PE-01`, `VE-01`. **El plano declara «8uds.»**, que es
  justo lo que pide la fila `NUMERO UDS:` — declarado por él, no medido.
- `medicion.FAMILIAS` **importa** sus patrones de `cuadro_superficies.py`: una
  sola implementación del criterio de familia, no dos.
- `ezdxf.tools.text.plain_mtext("ba\U+00F1o")` devuelve la cadena **sin
  decodificar**.

---

# DECISIÓN DE PRODUCTO (2026-09-11): el perfil del estudio

**Decidida por Pablo. No se construye hoy — cambia cómo se construye a partir de
hoy.**

## Lo que se decide

**Ningún estudio dibuja igual.** ArchMuse funciona hoy con las convenciones de
**un** arquitecto: su capa `00 areas`, sus rótulos, el título de su cuadro. Otro
estudio no funcionaría, y eso no es un fallo aislado que se arregle una vez: es
la forma del producto.

La salida **no** es personalizar cada instalación a mano. Eso es consultoría, no
producto: no escala, no se mantiene y convierte cada cliente nuevo en un
proyecto. La salida es que **el propio arquitecto configure su perfil una vez**:
qué capa usa para los recintos, cómo rotula sus estancias, cómo es su cuadro.

**Y no se construye ahora**, porque falta el dato que decide su forma: *¿las
diferencias entre estudios son de tres parámetros o de treinta?* Con un solo
estudio delante no se puede saber, y un sistema de configuración diseñado para el
caso equivocado es peor que ninguno — o se queda corto al segundo cliente, o es
un formulario de cuarenta campos que nadie rellena.

## La regla que sí entra en vigor hoy

> **Nada de convenciones escritas a fuego.** Todo lo que sea un valor de
> convención de ESTE estudio —un nombre de capa, un patrón de rótulo, el título
> de un cuadro— tiene que quedar en un sitio **identificable como parámetro de
> perfil**, aunque de momento tenga un solo valor y nadie pueda cambiarlo.

No es refactorizar: es no volver a esparcirlas. Una constante con nombre en la
cabecera de su módulo, marcada como convención, cuesta lo mismo de escribir que
un literal en medio de una función y ahorra tener que buscarla dentro de un año.

## Inventario: dónde están hoy esos valores

Buscado en el código el 2026-09-11, no de memoria. **Lo que sigue no se toca
todavía** — es el mapa para cuando se decida el perfil.

### A · Capas

| Valor | Dónde | Nota |
|---|---|---|
| `"00 areas"` | `parser.AREA_LAYER` | Ya es constante con nombre, y su propio comentario avisa: *«es el nombre que usa un único estudio»* |
| `"00 areas"` | `geometria_recibida.CAPA_POR_DEFECTO` | **Duplicado del anterior.** Dos definiciones del mismo hecho |
| `"00 areas"` | `archmuse.lsp` → `*am:capa-por-defecto*` | **Tercera copia**, y en otro lenguaje |
| `"00 CUADROS"` | `cuadro_superficies_export.CAPA_CUADRO` | Dónde escribe la vía web |
| `"00 ARCHMUSE BORRADOR"` | `marca_borrador.CAPA_DXF` | La nuestra, no la suya: **no es parámetro de perfil** |
| `"ARCHMUSE - BORRADOR"` | `archmuse.lsp` | **Y no coincide con la anterior.** Dos capas distintas para la misma marca según la vía |
| `AM_UTIL_INT` / `AM_UTIL_EXT` / `AM_CONS_EXT` | `parser` | Convención **nuestra**, propuesta, no del estudio |

**Lo más urgente del apartado A no es el perfil: son las tres copias de
`"00 areas"` y las dos capas distintas de la marca.** Eso ya es deuda hoy.

### B · Rótulos de estancia

| Valor | Dónde |
|---|---|
| `_PATRON_SALON_COCINA`, `_PATRON_PASILLO`, `_PATRON_VESTIBULO`, `_PATRON_BANO`, `_PATRON_ASEO`, `_PATRON_TENDEDERO`, `_PATRON_TERRAZA` | `cuadro_superficies.py` |
| `_PATRON_DORMITORIO` | `medicion.py` |
| `FAMILIAS` (patrón → familia → ámbito) | `medicion.py`, importando los de arriba |
| `_PATRON_TITULO_DE_CAMPO` («superficie útil», «superficie construida») | `parser.py` |
| `UNIT_LABEL_PATTERN` = `^VT\s*\d+` | `parser.py` |

**Ocho familias y nada más.** Un rótulo fuera de esas ocho deja la pieza sin
clasificar, y eso hoy **bloquea la vivienda entera**. Es el parámetro de perfil
más probable de todos: el vocabulario de un estudio no es el de otro.

`UNIT_LABEL_PATTERN` merece mención aparte: **`VT<n>` es la nomenclatura de este
estudio para «vivienda tipo»**. Otro puede usar `T1`, `A`, `Tipo 1` o nada.

### C · El cuadro

| Valor | Dónde |
|---|---|
| `TITULO_CUADRO` = «CUADRO DE SUPERFICIES POR TIPO DE VIVIENDA» | `cuadro_superficies.py` |
| El mismo título | `archmuse.lsp` → `*am:titulo-del-cuadro*` | **Cuarta copia de una convención** |
| `REQUISITOS` (17 campos con sus palabras) | `emparejador_cuadro.py` |
| `CAMPOS_UTIL_INTERIOR` / `_EXTERIOR` / `CAMPOS_CONSTRUIDA` | `cuadro_superficies.py` |
| `COLUMNA_INTERIOR = 1` / `COLUMNA_EXTERIOR = 3` | `reparto_cuadro.py` |

~~**`COLUMNA_INTERIOR`/`COLUMNA_EXTERIOR` son el caso más silencioso de
todos.**~~ **ARREGLADO el 2026-09-11, sin esperar a los perfiles.** No era deuda:
era un bug latente del mismo tipo que `C-4` y `C-7` —un fallo que no se
manifiesta como error—. Un cuadro con las etiquetas en otras columnas no daba
excepción ni celda vacía: escribía **cifras correctas en la columna equivocada**
del documento que alguien firma.

La columna de valor se **deriva** ahora de dónde estaba la etiqueta emparejada
—la celda de su derecha, sea cual sea el índice— y **qué celda es una etiqueta lo
decide el emparejador, no su posición**. Si la etiqueta está en la última columna
no hay dónde escribir, y eso se declara en vez de elegir otro sitio.
`tests/test_columna_de_valor.py` lo fija con cuadros de 2, 4, 5 y 6 columnas y
con las etiquetas en posiciones que este estudio no usa.

De paso salió otra confusión del mismo tipo: un cuadro sin ninguna celda
escribible devolvía `None`, y el arquitecto leía «no se reconoce ningún cuadro»
—falso, y le manda a mirar donde no es—. Ahora se distingue «no hay cuadro» de
«hay cuadro y no se puede rellenar».

### D · Lo que NO es parámetro de perfil, y conviene que quede dicho

Para que el día que se construya el perfil nadie meta aquí lo que no debe:

- **Los criterios firmados `C-1` a `C-9`.** Son criterio profesional, no
  convención de dibujo. Que un estudio sume terrazas al 50% es una decisión suya
  sobre el cómputo, no sobre cómo dibuja — y `C-1` dice que ArchMuse no la toma.
- **La marca de borrador.** `C-3` es innegociable y no se configura.
- **Las tolerancias de medición** (`TOLERANCIA_CIERRE`, `CONTAINMENT_THRESHOLD`).
  Son propiedades de la geometría, no del estudio.

## Las dos deudas que quedan, por prioridad

Las dos salieron del inventario y **no dependen de que el perfil se construya**:
son incoherencias de hoy.

### ~~PRIORIDAD 1 · Dos capas de marca distintas según la vía~~ — ARREGLADO 2026-09-11

**Se queda `ARCHMUSE - BORRADOR`**, el nombre de la vía AutoCAD, porque ésa es la
que va a ser el producto y la web es la demo (§0.0). La vía web pasa a usarlo.
**No hay migración**: los únicos planos con el nombre viejo están en la máquina
de desarrollo y en pruebas, ningún cliente tiene ninguno. Si algún día aparece un
plano con `00 ARCHMUSE BORRADOR`, es anterior a esta fecha y su marca sigue
siendo válida — sólo está en otra capa.

`C-9` ampliado en consecuencia: compara ahora también **lo que cada vía escribe**,
no sólo lo que mide. Guardián en
`tests/test_marca_borrador.py::test_las_dos_vias_marcan_en_LA_MISMA_capa`,
verificado contra tres formas de volver a separarlas.

<details><summary>El problema original, conservado</summary>


`marca_borrador.CAPA_DXF` vale `"00 ARCHMUSE BORRADOR"` y el `.lsp` escribe en
`"ARCHMUSE - BORRADOR"`. **El mismo plano marcado por los dos caminos acaba con
dos capas distintas**, y el arquitecto que apague una seguirá viendo la otra —o
peor, creerá que ha quitado la marca y no.

**Es una violación de `C-9` en la práctica**: las dos vías no hacen lo mismo.
Que el invariante no la cace es una carencia del invariante, no una defensa: `C-9`
compara **mediciones**, y esto es un efecto sobre el dibujo. Cuando se arregle,
conviene ampliar el test para que compare también **lo que cada vía escribe**, no
sólo lo que lee.

Arreglarlo es una constante compartida. Lo que hay que decidir antes es **cuál de
los dos nombres se queda**, porque el otro deja planos ya marcados con una capa
que nadie volverá a tocar.

</details>

### PRIORIDAD 0 · Ningún fixture del repositorio tiene cuadro (2026-09-12)

**Medido:** de todos los DXF versionados —`tests/fixtures/`, los seis planos del
banco de `C-9`, los 15 de tortura, los plausibles— **cero tienen un
`ACAD_TABLE`**. Los únicos planos con cuadro son los del arquitecto
(`v1plantas`, `v2s`, `v3s`, `ejemplo`, `plantasimple`), que **no se versionan
porque son de sus clientes y el repositorio es público**.

**Qué significa, sin suavizarlo:** toda la capacidad del cuadro —detección,
emparejamiento de filas, reparto, `C-4`, `C-6`, `C-11`, el cuadro propio—
**sólo se prueba de verdad en el ordenador de Pablo**. En CI esos tests se
saltan. Es el mismo patrón que dejó pasar las tres divergencias `C-9`: un camino
en verde y nadie mirando el otro.

Se ha mitigado en lo que se podía: `tests/test_cuadro_propio.py` construye el
cuadro con `cuadro_desde_celdas` —que además es **la vía que usa el comando de
verdad**—, así que 15 de sus 17 tests corren siempre. Pero eso cubre la vía de
AutoCAD, **no la lectura del DXF**: `_construir_cuadro`, la reconstrucción de la
rejilla desde las `LINE` y el filtro de celdas de valor siguen sin probarse en
CI, y ahí es donde estuvo el fallo de `C-11`.

**Lo que hace falta**, pendiente de hablarlo con Pablo (dicho el 2026-09-12,
*«cuando termines el `.lsp`, hablamos de qué fixture sintético hace falta»*):

- un DXF sintético con un `ACAD_TABLE` de verdad —no celdas simuladas— que
  reproduzca la forma de sus cuadros: dos pares etiqueta/valor por fila,
  encabezados de grupo en columna de valor, alguna celda ya rellena y alguna
  vacía, y la errata;
- y decidir si basta con uno o hacen falta dos (uno con varios cuadros, para
  `detectar_cuadros_superficies`).

**La dificultad real, dicha por delante:** `ezdxf` escribe `ACAD_TABLE` pero
`virtual_entities()` tiene que devolver los MTEXT y las LINE que
`_construir_cuadro` espera. Si no lo hace, el fixture no sirve y habría que
derivar uno anónimo de un plano suyo con `derivar_fixture_anonimo.py` —que ya
existe y que, ojo, **borró sin querer el defecto del flag de cerrada** la última
vez que se usó—.

### PRIORIDAD 2 · Cuatro copias de la misma convención

> **Decidido el 2026-09-11: se hace JUNTO con el sistema de perfiles, no antes.**
> La salida —que el servidor declare sus convenciones y el cliente las lea al
> arrancar— es **el mismo mecanismo** que necesitará el perfil del estudio.
> Hacerlo ahora sería construirlo dos veces.

`"00 areas"` está escrito en **tres** sitios (`parser.AREA_LAYER`,
`geometria_recibida.CAPA_POR_DEFECTO` y el `.lsp`) y el título del cuadro en
**dos** (Python y LISP). Hoy coinciden; nada garantiza que sigan coincidiendo, y
el día que una cambie sin las otras el síntoma será que una vía encuentra el
cuadro y la otra no.

Las copias entre Python y LISP son las más difíciles: **no hay forma de
compartir una constante entre los dos lenguajes**. La salida razonable es que el
servidor las declare —como ya declara `capacidades`— y el cliente las lea al
arrancar, en vez de llevarlas escritas. Eso es media hora y elimina la clase
entera de problema.

---

## Lo que hace falta antes de diseñarlo

**Ver más estudios.** Concretamente, y por orden de lo que más decide la forma:

1. **Un cuadro de otro estudio.** Si se parece al de éste, el perfil son tres
   parámetros; si no se parece en nada, el perfil no es un formulario sino un
   asistente que aprende de un ejemplar.
2. **Los rótulos de otro estudio.** Ocho familias pueden ser universales o ser
   las de una oficina.
3. **Su nombre de capa.** Es lo más fácil y lo menos informativo: ya sabemos que
   cambia.

Hasta entonces, la regla de arriba y este inventario. Nada más.
