# Criterios firmados de medición

**Qué es este documento y en qué se diferencia de `decisiones-pendientes.md`.**
Aquél registra lo que **necesita a Pablo** y no se ha decidido. Éste registra lo
contrario: criterios profesionales que **ya se han dictaminado**, quién los
dictaminó y cuándo, para que dejen de vivir como comentarios sueltos dentro del
código que los aplica.

Existe porque `D-7` lleva abierta desde el 2026-08-19 diciendo que hay criterio
profesional codificado y sin firmar, y que eso «no puede quedarse sin firmar
cuando esto se cobre». Cada criterio que sale de esa lista entra en ésta.

**Regla de este documento:** un criterio no se escribe aquí hasta que alguien
con competencia para dictaminarlo lo ha dictaminado. La implementación cita el
criterio; el criterio no se deduce de la implementación.

---

## C-1 · La superficie útil interior y la exterior no se suman

> **DEROGADO EN PARTE el 2026-09-13 por `C-14`**, firmado por un arquitecto
> colegiado tras ver la tabla en AutoCAD. La fila «TOTAL S. ÚTIL» de la tabla de
> ArchMuse **ya no sale vacía**: se calcula con la regla de `C-14`, que no suma
> las dos al 100 % sino que computa la exterior con tope. Lo que sigue en pie de
> `C-1`: interior y exterior son dos magnitudes y se publican por separado en la
> medición, el acta, la API y la pantalla `/medir`; el total existe **sólo** en
> la fila del cuadro y **sólo** con la regla de `C-14`. El cuadro antiguo por
> clonación (`cuadro_superficies.calcular_relleno_cuadro`, con su `N/D`) no lo
> usa ya ninguna salida del producto y no se ha tocado.

**Dictaminado por:** el arquitecto, en la sesión de validación del 2026-09-07.
**Aprobado por Pablo:** 2026-09-08. **Estado:** implementado el 2026-09-08.

**El criterio.** Una vivienda tiene **dos** superficies útiles —interior y
exterior (terrazas y tendederos)— y son dos magnitudes, no un desglose de una
tercera. **No existe una «superficie útil total» que las sume.**

**Qué había antes.** Un único `total_util_m2 = interior + exterior`, con los
espacios exteriores computando al **100 %**. Sobre el plano real, la vivienda
`VT1/3` publicaba 66,32 m² de «superficie útil total», de los que 7,54 eran
terraza contando igual que un dormitorio.

**Por qué importa más de lo que parece.** El cómputo de los espacios exteriores
(al 100 %, al 50 %, fuera del útil) depende de la ordenanza y del criterio del
técnico que firma. Una cifra que lo resuelve por su cuenta no es una medición:
es una decisión profesional disfrazada de cálculo, y viaja hasta la memoria
justificativa, que alguien presenta y firma.

**Dónde está aplicado, y es en todas partes.** `total_util_m2` no existe en
ninguna capa: ni en el modelo (`analyzer/medicion.py`), ni en el acta de
procedencia (`agente/skills/medicion.py` publica `medicion.util_interior_m2` y
`medicion.util_exterior_m2` como **dos hechos**), ni en el PDF de medición, ni
en la memoria justificativa, ni en la API, ni en la pantalla `/medir`, ni en el
CLI. La celda «TOTAL S. ÚTIL» del `ACAD_TABLE` del plano sale **`N/D` con su
motivo escrito** (`MOTIVO_TOTAL_UTIL_NO_SE_SUMA`), no en blanco: en blanco se
leería como «ArchMuse no ha sabido», y lo que ha hecho es no decidir por el
arquitecto.

**El único sitio donde se suman**, y es una comprobación, no una salida:
`_todo_total_suma_todas_sus_piezas` verifica que entre las dos no se ha perdido
ninguna pieza. Está documentado ahí mismo para que nadie lo confunda con
reintroducir el total.

---

## C-2 · Un impedimento bloquea las dos superficies, no sólo su suma

**Propuesto por:** ArchMuse (CTO), al implementar `C-1` el 2026-09-08.
**Dictaminado por Pablo:** 2026-09-08 — «aprobada y bien argumentada».
**Estado:** implementado.

**El criterio.** Cuando una vivienda tiene un impedimento —piezas solapadas,
reparto entre viviendas no firme, o una pieza que no se sabe clasificar—
**ninguna de las dos superficies se publica**. Las dos salen ausentes, con el
motivo y su magnitud. Las piezas se siguen midiendo y enseñando una a una.

**Qué había antes, y por qué cambia.** Hasta el 2026-09-08 los parciales
interior y exterior se publicaban **aunque** el total estuviera bloqueado: eran
el desglose de una cifra que el lector ya veía ausente, y se leían como
información de apoyo. Al desaparecer el total, esos dos parciales **pasan a ser
ellos mismos el resultado**, y publicar un resultado con un impedimento abierto
es exactamente el «número que puede estar mal» que la regla dura del módulo
existe para no dar.

**El razonamiento, que es lo que hay que poder discutir.** Un solape puede caer
dentro de lo interior, dentro de lo exterior o a caballo entre los dos: no se
sabe a cuál de las dos cifras le sobra superficie. Una pieza sin clasificar no
se sabe de qué lado cuenta, así que a las dos les puede faltar. Un reparto
dudoso puede llevarse cualquier pieza a la vivienda de al lado. En los tres
casos, publicar **una** de las dos sería afirmar que esa está bien, y no consta.

**Es una extensión de una regla ya firmada**, no una nueva: «una cifra que puede
estar mal es peor que su ausencia — la primera se copia a la memoria del
proyecto y la segunda se pregunta».

**Comprobado sobre plano real:** `tests/fixtures/reales/vivienda_con_solapes.dxf`
(7,08 m² dibujados dos veces) no publica ninguna de las dos, y sus nueve piezas
siguen medidas.

---

## C-3 · La marca de borrador va en lo que se entrega, no en lo que se lee

**Propuesto por:** ArchMuse (CTO), al cazarlo el guardián de la marca el
2026-09-08. **Dictaminado por Pablo:** 2026-09-08 — «queda como criterio, no como
parche». **Estado:** implementado.

**El criterio.** `C3` («todo entregable sale marcado como borrador para revisión
de un colegiado, sin excepción y sin opción de desactivarlo») gobierna lo que
**llega a una persona**. Un fichero interno que el producto se escribe a sí mismo
para leerlo un segundo después no es un entregable, y **no lleva la marca**.

**Por qué no es una rendija en `C3`, y esto es lo que hay que poder discutir.**
No se exime por comodidad: estamparla ahí **falsearía la medición**. La marca es
un `MTEXT`; el DXF que `analyzer/geometria_recibida.py` materializa existe
precisamente para que `parser.leer_plano` busque rótulos de estancia en los
`MTEXT`. Un texto que ArchMuse se inventa y que cae dentro de un recinto puede
acabar siendo el rótulo de ese recinto. Sería el producto contaminando su propia
entrada, y el fallo aparecería como una superficie mal rotulada, no como una
marca de más.

**Lo que sí lleva marca en ese mismo flujo**, y por eso el criterio no afloja
nada: el PDF de medición (`medicion_pdf.py`) y la tabla nativa que el cliente CAD
inserta en el plano del arquitecto, que el PRD de AutoCAD exige con marca y sin
opción de quitarla.

**Cómo se sostiene, que es la parte que importa.** El guardián
`test_ningun_modulo_guarda_un_dxf_sin_pasar_por_la_marca` **se ha endurecido, no
relajado**. La exención exige tres cosas a la vez: declarar la constante
`DXF_INTERNO_SIN_MARCA_DE_BORRADOR` con el motivo escrito en su propio valor,
estar nombrada a mano en el test —o sea, aparecer en el diff de quien la añada— y
pasar un test que comprueba que el DXF materializado **no lleva ni un texto** que
no venga del cliente. Una puerta trasera vale lo que valga su cerradura.

---

## C-4 · Un `0,00 m²` sólo se escribe sobre una medición limpia

> **DEROGADO el 2026-09-13 por `D-13`** (abajo). Ya no se escribe `0,00 m²` ni
> con la medición limpia: ninguna habitación mide cero. El texto de `C-4` se
> conserva porque su argumento —un cero es peor que una celda vacía, porque se
> lee como «esto está mirado»— es exactamente el que `D-13` lleva hasta el final.
> Lo que falló fue la condición: «limpia» no bastaba. El 2026-09-13, en AutoCAD,
> sobre una medición limpia, el cuadro del arquitecto pedía `pasillo` y
> `vestibulo`, ese estudio mete el pasillo en el salón, y ArchMuse escribió
> `0,00 m²` en las dos filas.

**Dictaminado por:** Pablo, 2026-09-10, elevando a criterio una objeción de
ArchMuse (CTO) al criterio anterior.

**Qué dice.** Cuando el cuadro del arquitecto pide una pieza que la vivienda no
tiene, se escribe `0,00 m²` — pero **sólo si la medición de esa vivienda está
limpia**: sin impedimentos abiertos, sin polilíneas descartadas en su capa, sin
piezas sin clasificar y sin piezas medidas que no hayan encontrado fila.

> **Ampliado por `C-7` (2026-09-10).** «Limpia» incluye desde entonces una
> condición más, y es la que faltaba: que **conste que el cliente mandó todo lo
> que había**. Sin eso, una medición sin impedimentos puede ser una medición a la
> que le falta media vivienda y no lo sabe — pasó, con el salón de
> `v1plantas.dxf`. Si algo
de eso falta, la celda **se queda en blanco** y el motivo dice que no se ha
encontrado ninguna y que la medición no está limpia.

**Por qué.** La regla anterior escribía `0,00 m²` sin condición, con el
argumento de que es un hecho negativo verificado —se buscó y no hay ninguna— y
no una ausencia de información. El argumento es bueno **y depende por entero de
que la búsqueda haya sido completa**.

El 2026-09-10 se comprobó que no siempre lo es. En `v1plantas.dxf` el baño
**estaba dibujado y rotulado**, y ArchMuse no lo veía: su rótulo llevaba la eñe
escapada (`Ba\U+00F1o`) y ningún patrón casaba. Si el cuadro hubiera pedido una
fila que ArchMuse no supiera leer, la regla habría escrito `0,00 m²` **en el
plano del arquitecto para una habitación que existe**.

Eso no es un hecho negativo verificado: es un fallo de lectura con formato de
dato. Y es peor que una celda vacía, porque una celda vacía se lee como «esto
hay que mirarlo» y un `0,00 m²` se lee como «esto está mirado».

El coste es cobertura: sobre un plano con impedimentos abiertos se rellenan
menos celdas. Lo que se compra es que ninguna cifra escrita en el documento de
alguien pueda ser una omisión disfrazada de medida.

**Dónde se aplica.** `analyzer/cuadro_superficies.py`, estado `CERO_REAL`.

---

## C-5 · Una ambigüedad de reparto no se reparte ni se suma

**Dictaminado por:** Pablo, 2026-09-10. Cierra el punto 2 de «lo que sigue sin
firmar» de este mismo documento, abierto el 2026-09-08.

**Qué dice.** Cuando el cuadro pide N huecos de una familia y la geometría no da
exactamente N piezas inequívocas, **ninguna de las celdas implicadas se
rellena**, y cada una lleva su motivo. Ni se reparte por orden de aparición, ni
se suman las piezas, ni se rellena una dejando la otra en blanco.

**Los dos casos, con el plano en el que se dictaminó** (`v1plantas.dxf`):

- El cuadro pide `terraza 1` y `terraza 2`; el plano dibuja **una** `Terraza` de
  3,32 m². **Las dos celdas se quedan vacías.** Escribir 3,32 en «terraza 1» es
  decidir por el arquitecto cuál de sus dos filas ha dibujado, y dejar la otra en
  blanco insinúa que mide cero, que es distinto de «no lo sé».
- El cuadro pide una fila `tendedero` y aparecen dos piezas con ese rótulo:
  **no se suman.** Sumarlas afirma que son el mismo espacio.

**La alternativa que se descarta, y por qué.** Otro arquitecto podría sostener
que «la mayor manda» o que se reparta por orden. Es defendible para quien firma
el proyecto; no lo es para un programa que no sabe cuál de las dos terrazas del
cuadro es la dibujada. El criterio elegido es el conservador a propósito: deja
trabajo al arquitecto en vez de arriesgar una cifra en el sitio equivocado.

**Nota sobre el caso que lo motivó.** Los «dos Tendedero» de `v1plantas.dxf` no
eran una ambigüedad de reparto: eran un tendedero y el **contorno** que lo
agrupa con la terraza (ver la nota de C-6 y `tests/test_contorno_agrupador.py`).
El criterio se firma igualmente porque el caso de las dos terrazas sí es real y
sigue en pie.

---

## C-6 · Conservación de la medida: ninguna superficie desaparece en silencio

**Dictaminado por:** Pablo, 2026-09-10, como **invariante permanente** del
producto — no como detalle de la tarea en la que salió.

**Qué dice.** Toda pieza medida termina en **exactamente uno** de estos tres
sitios, y en ninguno más:

1. una celda del cuadro,
2. la lista de piezas que no han encontrado fila,
3. la lista de bloqueos, con su motivo.

La unión de las tres es el total de piezas medidas, y ninguna aparece dos veces.
**Es comprobable, y se comprueba con un test**, no con una revisión a ojo.

Y una consecuencia que se firma con el criterio: si hay una pieza medida sin
fila donde ir, **el total correspondiente no se rellena**. Un total que no
incluye una superficie medida es un total falso, y un cuadro cuadrado y
equivocado es peor que uno incompleto — el incompleto se ve.

**Por qué es un invariante y no una regla de una tarea.** El daño que evita no
depende de por dónde entre el trabajo: una superficie que se mide y no aparece
en ningún sitio del entregable es el fallo que hace que un cuadro pase un visado
diciendo una cifra que no es. Aplica al cuadro del arquitecto, al camino web, y
a cualquier salida futura que reparta piezas medidas en huecos.

---

## C-7 · Una medición limpia no prueba que haya llegado todo

**Dictaminado por:** Pablo, 2026-09-10, a partir de una fuga medida ese mismo
día. **El mecanismo de verificación lo propone ArchMuse y está pendiente de tu
visto bueno** — el criterio, no.

**Qué dice.** El servidor **no puede concluir «esta vivienda no tiene salón»**.
Sólo puede concluir «no ha llegado nada que parezca un salón». Son dos frases
distintas y hasta hoy el producto las trataba como la misma.

Por lo tanto: **una medición sin impedimentos no es una medición completa** hasta
que consta que el cliente mandó todo lo que había. Mientras eso no conste, todo
lo que dependa de una ausencia —`0,00 m²` por `C-4`, un total, un «no existe»—
queda sin escribir.

### El caso que lo motiva, medido

`v1plantas.dxf`, 2026-09-10. El cliente CAD seleccionaba con `ssget` filtrando
por el bit de «cerrada» del código 70, que es lo único que `ssget` sabe hacer. En
ese plano ese bit está mal puesto en 2 de 10 polilíneas, **y una es el
`Salón/cocina` de 21,90 m²**. Resultado:

- la polilínea del salón **no salía del dibujo**;
- el servidor medía 7 piezas en vez de 8, sin ningún hueco aparente;
- la medición salía **sin un solo impedimento** — porque desde el servidor no
  faltaba nada: lo que no llega no se echa de menos;
- y `C-4` daba el visto bueno para escribir un **`0,00 m²` en la fila del salón**
  del cuadro que el arquitecto firma.

`C-4` funcionó exactamente como se firmó. El problema es que `C-4` mira si la
medición está limpia, y **la medición estaba limpia**. Lo que estaba roto era el
transporte, y el transporte no tenía quién lo mirara.

### Cómo se verifica de forma permanente (propuesta)

Tres piezas. Las tres son necesarias: la primera hace el fallo detectable, las
otras dos hacen que no pueda volver a introducirse en silencio.

**1. El cliente declara qué barrió, y el servidor lo comprueba.**

El payload lleva, además de los recintos, lo que el cliente vio antes de
mandarlos:

```json
"seleccion": {
  "criterio": "todas las polilineas de la capa",
  "polilineas_en_la_capa": 10
}
```

Y el servidor compara ese número con los recintos recibidos. **Si no cuadran, la
medición NO está limpia**, diga lo que diga el resto — se declara como
impedimento con su cifra («el cliente vio 10 polilíneas en la capa y han llegado
8») y `C-4` deja de autorizar ceros.

Es autodeclarado, sí. No detecta a un cliente que mienta; detecta al que **filtre
sin darse cuenta**, que es lo que pasó y lo que volverá a pasar. Y el criterio
declarado convierte un filtro nuevo en un cambio visible: para colar uno hay que
cambiar esa cadena, y eso se ve en el diff.

**2. El simulador no puede filtrar, y hay un test que lo dice.**

`payload_desde_dxf` es lo que los 34 tests del endpoint usan como cliente. Si él
filtra, los tests corren sobre un mundo que no existe — que es exactamente lo que
pasó: el error vivió meses ahí porque ningún fixture tenía el defecto. El test
comprueba que **manda tantos recintos como polilíneas hay en la capa**, sobre un
fixture que sí tiene polilíneas con el flag mal puesto
(`14_flag_de_cerrada_mal_puesto.dxf`).

**3. El `.lsp` no puede filtrar, y hay otro test que lo dice.**

Un guardián sobre `am:recolectar`: su `ssget` de recintos no puede llevar más
filtro que la capa. Nada de `(-4 . "&")` ni de `(70 . 1)`. Es una comprobación de
texto sobre el fichero, del mismo tipo que las que ya vigilan que no se
reintroduzca `vla-AddTable`, y es la única forma de vigilar el cliente sin
AutoCAD delante.

### Por qué no basta con «acordarse»

Porque ya nos habíamos acordado. La nota del 2026-09-09 decía que la solución
buena era de servidor y estaba escrita con sus cifras (3 de 22, 2 de 10, 9 de
53). Sobrevivió un día entero como pendiente mientras el producto escribía ceros.
Un criterio que depende de que alguien recuerde una nota no es un criterio: es
una esperanza. Las tres piezas de arriba lo convierten en algo que falla solo.

---

## C-7, otra vez · Los tests comprueban lo que calcula el servidor, no lo que dibuja AutoCAD

**Anotado por orden de Pablo el 2026-09-13**, después de que costara dos bugs en
la primera prueba del `.lsp` 3.2.0 sobre `v1plantas.dxf`. Es la misma forma que
`C-7` —una comprobación que pasa no prueba lo que parece probar— en otra capa.

- **Las notas se dibujaban encima de la tabla.** El servidor las colocaba debajo
  de la tabla **que él había calculado** (borde en y = −293,58, primera nota en
  −293,72), y su test lo comprobaba y pasaba. Pero AutoCAD dibuja con el estilo
  de tabla activo del plano (`Standard`: margen vertical 1,5, texto 4,5), y las
  filas crecen hasta decenas de veces lo calculado. El test miraba el cálculo, no
  el dibujo.
- **«Dos viviendas VT1/3» donde había una.** El servidor devolvía una vivienda,
  y su test lo comprobaba y pasaba. Pero la respuesta LISP llevaba el mismo
  bloque dos veces (`repartos` y `reparto`), y el `.lsp` cuenta apariciones de
  texto. Ningún test hacía lo que hace el `.lsp` con esa respuesta.

**La regla.** Un test del servidor no dice nada de lo que ve el arquitecto en
AutoCAD. Mientras el `.lsp` no se pueda ejecutar en CI, cada cosa que el comando
hace con la respuesta —contar, elegir, dibujar a una medida— tiene que tener o
un test que reproduzca **esa misma lectura** sobre la respuesta real, o una
casilla en `docs/design/checklist-primera-prueba-autocad.md` que diga que está
sin comprobar. «El test pasa» sin una de las dos es una hipótesis.

---

## C-13 · Dos viviendas que no se pueden distinguir no se fusionan

**Dictaminado por:** Pablo, 2026-09-13: «Si dos viviendas no se pueden
distinguir, no se fusionan: se declara y se deja sin escribir. Firmo el
criterio.»

**Qué dice.** Cada rótulo de vivienda es una vivienda, aunque su texto sea igual
que el de otra. Si varias viviendas de la planta llevan el mismo rótulo, ninguna
cifra suya se publica —ni su superficie útil, ni su tabla, ni el total de la
planta— y el motivo lo dice, con cuántas son. Sus piezas se siguen enseñando una
a una.

**Por qué es lo más grave que salió ese día.** El agrupador asignaba cada
habitación al TEXTO del rótulo más cercano, así que dos `VT1/3` se fundían en una
sola vivienda: filas repetidas y **TOTAL SUP. INTERIOR 87,40 m²**, la suma de las
dos, con la medición limpia y sin nota. Un `0,00` se ve; esto no. Y `VT1/3`
significa «tipo 1, tres unidades»: las viviendas repetidas del mismo tipo son lo
normal en un bloque, no un caso raro. Medido además en un plano real:
`plantasimple.dxf` rotula `VT22/1` dos veces, a 1.385 m una de otra.

**Dónde se aplica.** `evaluator.group_rooms_by_unit_label` (agrupa por rótulo, no
por texto), `medicion.ViviendaMedida.impedimentos` y `medicion.motivo_c13` (una
sola redacción), `plantilla_cuadro.construir` (se niega), el endpoint del
comando (una entrada sin tabla por rótulo repetido), la exportación web y
`plano.superficie_util` del agente.

**Cómo se guarda.** `tests/test_c13_viviendas_indistinguibles.py`: el guardián
estructural —ninguna vivienda contiene recintos de dos rótulos— y un centinela
por valor sobre toda la respuesta; con un control de dos viviendas con rótulos
distintos que sí se miden.

> **ENMIENDA, firmada por Pablo el 2026-09-15, para el comando por clic.** «El
> clic decide la vivienda aunque su rótulo se repita. Dos viviendas con el mismo
> nombre se distinguen por su posición; nunca se fusionan ni se suman. Si hay
> duda real de cuál está más cerca, sigue diciendo "No mido".» (En su mensaje
> citó `C-15`; el texto es el de este criterio.)
>
> **Qué cambia.** Con un clic (`C-17`) la vivienda elegida se mide y se dibuja
> aunque otra lleve su rótulo: es la del rótulo que el agrupador le ha asignado,
> con sus piezas y sólo las suyas. **Qué no cambia.** Sin clic —la planta entera,
> la web, el agente— no hay posición que las distinga y siguen sin publicarse. Y
> dentro de una misma medición nunca se suman ni se funden: la tabla es la de una
> vivienda, idéntica a medirla sola (`tests/test_un_clic_una_tabla.py`).

---

## C-14 · El total útil computa la exterior con tope

**Dictaminado por:** un arquitecto colegiado, 2026-09-13, tras ver la tabla en
AutoCAD. «Son criterio profesional, no sugerencias.» **Deroga la parte de `C-1`
que dejaba esta fila vacía.**

**El criterio.**

    TOTAL S. ÚTIL = útil interior + el MENOR de
                    a) el 50 % de la útil exterior
                    b) el 10 % de la útil interior

**El ejemplo**, medido en `v1plantas.dxf`: interior 58,78 · exterior 7,54 · 50 % del
exterior 3,77 · 10 % del interior 5,88 · gana el menor → **62,56 m²**. Desde `C-19`
(2026-09-16) la cuenta va sin redondear: 58,7837 + 7,5450 / 2 = 62,5562 → 62,56.
*El día que se firmó `C-14` se calculaba sobre las cifras redondeadas y daba 62,55.*

**Si la interior o la exterior no se pueden afirmar, el total tampoco**: fila
vacía con su motivo. No se calcula sobre una cifra bloqueada.

**Cómo se aplica** (`plantilla_cuadro.superficie_util_total` y `_total_util`):

- Sobre **la útil interior y la exterior sin redondear** (`C-19`, firmado el
  2026-09-16). *Hasta ese día se calculaba sobre las dos cifras ya redondeadas de
  la fila de totales, para que quien la leyera la rehiciera a mano; `C-19` lo
  deroga.*
- Resultado redondeado a céntimos **hacia arriba en el medio** (`ROUND_HALF_UP`,
  en `Decimal`). *Decisión de ArchMuse, declarada, no del criterio: ni `C-14` ni
  `C-19` dicen cómo se redondea un medio.* Con áreas sin redondear un medio
  exacto prácticamente no se da.
- **Un lado sin ningún espacio** está afirmado y aporta cero: es el caso «sin
  exterior: 100 → 100» del criterio. Su celda de total sigue vacía con la nota
  de `D-13` (un total vacío no se escribe como cero), pero no bloquea.
- **Un lado bloqueado** —impedimento (`C-2`), pieza sin fila (`C-6`), una fila
  sin cifra— deja el total vacío con la nota «la superficie útil exterior no se
  puede afirmar (ver su nota), y el total no se calcula sobre una cifra
  bloqueada (C-14)». Nunca «58,78 + 0».
- Sin ningún espacio interior no hay total: vacía con motivo.

**Cómo se guarda.** `tests/test_c14_total_util.py`: los tres casos del criterio
con sus cifras (62,56 · 110 · 100), los mismos por la plantilla del fixture
sintético, los bloqueos, y un guardián que rehace el total desde lo escrito en la
tabla en cinco escenarios y exige que coincida, o que esté vacío si algún lado
está bloqueado.

---

## C-8 · Lo que el plano declara manda sobre lo que ArchMuse deduce

**Dictaminado por:** Pablo, 2026-09-11. **Criterio firmado; sin implementar** —
toca `medicion.py`, los totales y la forma en que `C-2` bloquea, así que va en
sesión propia.

**Qué dice.** Cuando el plano **declara** en qué magnitud entra un recinto, esa
declaración manda. La deducción por familia —«terraza» → exterior, «dormitorio»
→ interior— **sólo actúa cuando no hay declaración**.

Nunca al revés, y nunca «las dos y que gane la que coincida»: si el plano dice
una cosa y la familia sugiere otra, **manda el plano**, y la discrepancia se
declara como hallazgo para que el arquitecto la mire. No se resuelve en silencio
hacia ninguno de los dos lados.

### Por qué

Porque el ámbito de un recinto es criterio profesional, y `C-1` y `C-2` ya
dicen que ArchMuse no lo decide por el técnico que firma. Hasta hoy lo decidía:
deducía interior o exterior del nombre de la estancia, porque no había otra cosa
de la que deducirlo.

Resulta que sí la hay. En `v1plantas.dxf`, cada recinto lleva **dos** MTEXT: el
nombre y un título de campo encima que dice qué magnitud es.

| Título en el plano | Recintos |
|---|---|
| `superficie util` | Salón/cocina, Dormitorio 1, Dormitorio 2, Dormitorio 3, Baño, Aseo |
| `superficie util exterior` | Terraza, Tendedero |
| `Superficie construida cerrada` | *(un rótulo suelto, sin recinto)* |
| `Superficie construida exterior` | *(idem)* |

Sin una sola excepción, y coincide con lo que ArchMuse deducía. **Que coincida es
precisamente lo que lo hace seguro de adoptar**: se puede cambiar el origen del
dato sin cambiar ninguna cifra, y las discrepancias que aparezcan en otros planos
serán informativas, no una regresión.

Deducir lo que el arquitecto ya ha escrito no es un atajo: es ignorarlo. Y el
día que un plano diga algo distinto de lo que ArchMuse deduciría —una terraza
cerrada que él computa como interior, que es una decisión suya y legítima—
deducir sería sustituir su criterio por el nuestro sin decírselo.

### Qué implica implementarlo, para el día que se haga

- **`parser`** tiene que conservar el título de campo del recinto, no sólo
  descartarlo para elegir el nombre (que es lo único que hace hoy, desde el
  arreglo del 2026-09-11). Hace falta un campo nuevo en `Room`.
- **`medicion.py`** tiene que preferirlo a `FAMILIAS` al asignar el ámbito, y
  dejar `FAMILIAS` como camino por defecto.
- **Los totales** cambian de origen: hoy suman por ámbito deducido.
- **`C-2`** sigue igual, pero con un caso nuevo: un recinto con declaración
  ilegible o contradictoria no es «sin clasificar por su rótulo», es otra cosa y
  merece su propio motivo.
- **Un hallazgo nuevo:** declaración y familia que no coinciden. No bloquea —el
  plano manda— pero se dice.

---

## C-9 · Dos vías de entrada no pueden leer distinto el mismo plano

**Dictaminado por:** Pablo, 2026-09-11, como **invariante permanente**, al mismo
nivel que `C-6`.

**Qué dice.** ArchMuse tiene dos formas de recibir un plano —el DXF subido por la
web y la geometría que manda el cliente CAD— y **las dos tienen que leer lo
mismo**: los mismos recintos, los mismos rótulos, las mismas superficies. Si
divergen, es un fallo de severidad alta aunque las dos cifras parezcan
razonables, porque **no se sabe cuál de las dos es la buena**.

> **AMPLIADO el 2026-09-11: y lo que cada vía ESCRIBE, no sólo lo que lee.**
>
> El criterio se firmó mirando la entrada, y por eso no cazó el primer fallo de
> salida que apareció: la vía web marcaba el borrador en la capa
> `00 ARCHMUSE BORRADOR` y el comando de AutoCAD en `ARCHMUSE - BORRADOR`. **El
> mismo plano marcado por los dos caminos acababa con dos capas distintas**, y
> el arquitecto que apagara una seguiría viendo la otra — o creería haber
> quitado la marca sin haberla quitado.
>
> Los tests de `C-9` estaban todos en verde mientras eso pasaba, porque comparan
> **mediciones**. Que no lo vieran es una **carencia del invariante, no una
> defensa**: la pregunta que este criterio hace no es «¿miden igual?» sino «¿hacen
> lo mismo?», y lo que se escribe en el dibujo forma parte de lo que se hace.
>
> Desde hoy, cualquier cosa que las dos vías dejen en el plano —la capa de la
> marca, su texto, dónde va— tiene que ser la misma, y comprobarse. Lo hace
> `tests/test_marca_borrador.py::test_las_dos_vias_marcan_en_LA_MISMA_capa`,
> que compara las dos cadenas directamente porque **entre Python y LISP no hay
> forma de compartir una constante**. Cuando el servidor declare sus convenciones
> y el cliente las lea al arrancar —deuda P2 del PRD del 2026-09-10— ese test
> dejará de hacer falta y el invariante se cumplirá por construcción.

Y se comprueba con un test que corre **las dos vías sobre el mismo plano** y
compara el resultado. No basta con que cada una tenga los suyos.

### Por qué es un invariante y no un detalle

Porque ya ha pasado **cuatro veces**, todas con el mismo patrón —una vía en
verde, la otra rota, y nadie mirando el hueco entre ellas:

1. **2026-09-10, el color y el flag de cerrada.** El payload del cliente no
   llevaba ni el color ni el bit de cerrada, así que el DXF materializado salía
   entero en BYLAYER y con todo cerrado. Por la vía web el salón medía 21,90 m²;
   por la vía CAD, el mismo plano perdía el salón entero y escribía `0,00 m²` en
   el cuadro.
2. **2026-09-11, los títulos de campo.** `match_label_to_room` devolvía el primer
   texto que cayera dentro del recinto, y el orden de llegada no es el mismo
   leyendo un DXF que recibiendo un `ssget`. El mismo plano daba «Dormitorio 1»
   por una vía y «superficie util» por la otra.

3. **2026-09-11, la capa de la marca.** Dos nombres distintos para la misma
   capa, uno por vía. Este mismo criterio estaba en verde mientras pasaba,
   porque miraba la entrada y esto era la salida.

4. **2026-09-11, el tipo de entidad de los rótulos — cerrado el 2026-09-12.**
   `geometria_recibida.escribir_dxf` escribía **todos** los textos como MTEXT
   porque el payload no decía de qué tipo era cada uno. `extract_labels` ordena
   los MTEXT antes que los TEXT justamente para desempatar dos rótulos dentro
   del mismo recinto, así que aplanar los dos tipos le quitaba a esa regla el
   dato con el que decide. Sobre `plantasimple.dxf`:

   | | Por la web | Por el comando |
   |---|---:|---:|
   | Recintos | 157 | 169 |
   | Con nombre | 156 | 168 |
   | Viviendas con superficie | **16** | **3** |

   Doce contornos agrupadores dejaban de reconocerse y contaban superficie dos
   veces, y `C-6` bloqueaba 13 viviendas. **Se cerró sin criterio nuevo:** el
   payload declara el tipo (`"tipo": "MTEXT"` / `"TEXT"`, que el `.lsp` ya leía
   del `assoc 0` y no mandaba) y el materializador lo respeta. La prioridad
   sigue viviendo en `extract_labels`, que es donde estaba probada. Después del
   arreglo las dos vías dan **157 / 156 / 16**, idénticas pieza a pieza.

5. **2026-09-15, las referencias externas — ABIERTO, sin arreglar.** Con `C-15`
   el comando detecta que los recintos están en una xref, se para y dice qué
   fichero abrir. La vía web no sabe de xrefs: el parser no puede verlas (en el
   DXF la definición tiene cero entidades) y su `CapaIndeterminada` dice que
   las superficies pueden estar «dentro de bloques», que es otra causa. **Sobre
   el mismo plano, las dos vías dan motivos distintos: ya no leen igual.** En el
   DXF sí quedan la ruta de la xref y las capas `xref|capa`, así que la web
   podría detectarlas y decir lo mismo; no se ha hecho. Ningún test de
   `test_dos_vias_leen_igual.py` lo cubre: el banco no tiene ningún plano con
   xrefs. Declarado por Pablo como incumplimiento de este criterio el
   2026-09-15.

   **Arreglado el 2026-09-17.** Medido antes con un plano sintético: la web no se
   paraba y medía los rectángulos de marco de la hoja. Ahora `parser.leer_plano`,
   antes de buscar capa, mira las capas `referencia|capa de recintos`: si una
   referencia la tiene y el dibujo no tiene ninguna polilínea en esa capa, lanza
   `RecintosEnReferenciaExterna` con el fichero y **sin ofrecer capas**, como el
   comando. **Límite que queda:** con polilíneas en los dos, el DXF no dice si la
   referencia tiene recintos (el comando sí lo ve) y la web mide los del dibujo.
   Test: `tests/test_c9_referencias_externas_web.py`.

Los cuatro primeros tenían tests, y los cuatro tenían **todos sus tests en verde**: cada
vía se probaba por separado y ninguno cruzaba. El hueco entre dos caminos
correctos no lo vigila nadie salvo que se vigile a propósito — y el tercero
enseña algo más: **un invariante también tiene huecos**, y el suyo estaba en
haberse definido sobre lo que se lee.

El cuarto enseña el otro hueco posible: **contra qué planos corre**. Los seis
del banco eran todo-MTEXT o todo-TEXT, así que ninguno podía ejercitar la
prioridad; y `plantasimple.dxf`, que sí la ejercita, **se saltaba en silencio**
porque no resuelve su capa solo. Un invariante que elige contra qué se comprueba
no es un invariante. Desde el 2026-09-12 el banco lleva el plano con su capa
declarada y un fixture sintético que mezcla los dos tipos
(`15_mtext_y_text_en_el_mismo_recinto.dxf`), y sólo se salta lo que no está en
la máquina.

### Cómo se verifica

`tests/test_dos_vias_leen_igual.py`: sobre cada plano disponible —los fixtures
del repositorio y los reales si están en la máquina— se lee por las dos vías y se
comparan recintos, rótulos y superficies. Y **con el orden de los textos
invertido**, porque el orden de llegada es lo único que el cliente no puede
garantizar.

Cuando aparezca una tercera vía de entrada —el plugin nativo, IFC, un DWG
convertido— entra en ese test el mismo día que se escribe, no después.

**Las superficies se comparan a dos decimales, que es a los que se publican.**
No es una tolerancia de conveniencia: el payload lleva las coordenadas a seis
decimales porque es lo que `am:json-num` sabe mandar (`(rtos x 2 6)`), y en un
recinto de `plantasimple.dxf` con el perímetro a 300 m del origen ese micrómetro
por vértice acumula 0,0001 m² —el «Tendedero» mide 4,1236 m² por una vía y
4,1237 por la otra—. Es **1 cm² en 1 de 157 piezas** y es el único resto de todo
el banco. Comparar más fino sería comparar el ruido del transporte; subir la
precisión del simulador lo haría más fino que lo simulado, que es el error que
ya se cometió una vez con el flag de cerrada.

### Lo que el banco ampliado ha destapado, y no se ha arreglado

Con `plantasimple.dxf` dentro, el test del **orden de los textos** falla, y no
por el tipo: ese plano rotula cada salón con **varios MTEXT de la misma capa**
—el nombre repetido dos o tres veces y la cifra de su superficie, todos MTEXT en
`00 TEXTO`—. Medido el 2026-09-12: **156 recintos tienen más de un texto dentro
y 63 tienen tres MTEXT compitiendo**. Ni la prioridad MTEXT-sobre-TEXT (mismo
tipo) ni la regla de la capa que nombra (misma capa) desempatan eso: lo desempata
el orden del recorrido, y `ssget` no garantiza ninguno. Al invertirlo, las
estancias pasan de llamarse «Salón/cocina» a llamarse «21.90m²».

Está **declarado como `xfail(strict=True)`** con su motivo, no tapado: cuál de
dos textos de la misma capa y el mismo tipo nombra una estancia es criterio
profesional (`D-7`) y **está sin firmar**. El día que se firme, el xfail se pone
rojo y hay que venir a borrarlo.

---

## C-11 · ArchMuse no escribe ninguna cifra que no haya medido él

**Dictaminado por:** Pablo, 2026-09-12, al revisar el cuadro propio.

**Qué dice.** En el cuadro que ArchMuse dibuja no puede aparecer **ni una cifra
que no proceda de su propia medición**. Ni copiada del cuadro del arquitecto, ni
leída de un texto del plano, ni heredada de una celda que ya tenía valor. Si una
cifra no la ha medido ArchMuse, no se escribe: se deja la celda con su nota.

**Por qué es un criterio y no una comprobación más.** Los demás criterios de este
documento gobiernan *qué se puede afirmar*. Éste gobierna algo anterior: **de
quién es lo que se afirma**. Un cuadro firmado «ArchMuse» con dentro las cifras
del arquitecto no es una medición incompleta —eso sería `C-6`—: es ArchMuse
poniendo su nombre debajo de un número que no ha comprobado. Y como el número
viene de él, **coincide con su documentación y nada chirría**: el error es
invisible por construcción, y sobrevive hasta que alguien mide a mano.

### El caso que lo motiva, y cómo se vio

El 2026-09-12, construyendo el cuadro propio. `cuadro_superficies._construir_cuadro`
mete en su lista de etiquetas **todos** los MTEXT de la rejilla, y una celda de
valor —`21.90m²`— es un MTEXT como cualquier otro: llegaba al código que copia
las filas indistinguible de un encabezado, y se copiaba dentro de la tabla de
ArchMuse como si fuera una fila suya.

> **Se vio por el formato, y eso fue suerte, no diseño.** El arquitecto escribe
> `21.90m²` —punto decimal, sin espacio— y ArchMuse `21,90 m²` —coma y
> espacio—. La cifra desentonaba a simple vista. **Si él escribiera con coma, no
> lo habría visto nadie**: el número sería plausible, coincidiría con su memoria
> y el cuadro habría salido perfecto y mintiendo.
>
> Por eso este criterio **no se comprueba comparando textos**. Comparar cadenas
> funciona mientras los dos formatos difieran, es decir, por casualidad; y además
> daría un falso positivo el día que ArchMuse midiera exactamente lo mismo que él
> escribió, que es el caso bueno.

### Cómo se comprueba, y por qué así

**Por procedencia, no por aspecto, y de forma cerrada.** Todo texto que salga en
el cuadro dibujado tiene que ser una de estas cuatro cosas y ninguna más:

1. una **etiqueta** copiada de su cuadro (o del formato canónico de ArchMuse),
2. un **valor** producido por `calcular_relleno_cuadro` con `escribir=True`,
3. una **marca de nota** (`(1)`, `(2)`…),
4. el **título**.

El test recorre el cuadro dibujado y exige que cada celda caiga en una de las
cuatro. No mira si el texto «parece» una superficie ni de qué se parece a qué:
si aparece algo cuyo origen no es ninguno de los cuatro, falla —venga de
`_construir_cuadro`, de `cuadro_desde_celdas` o de lo que alguien escriba mañana
para leer las celdas de otra manera—.

Vive en `tests/test_cuadro_propio.py`:
`test_toda_cifra_del_cuadro_sale_de_la_medicion` y
`test_ningun_texto_del_cuadro_tiene_origen_desconocido`.

### Lo que este criterio NO prohíbe

**Leer sus cifras.** ArchMuse las lee y las necesita: el rótulo `VIVIENDA TIPO`
es lo que empareja el cuadro con la vivienda (`elegir_vivienda`). Lo que no puede
es **reemitirlas como suyas**. Leer, sí; firmar, no.

> **Desde el 2026-09-13 el cuadro de ArchMuse ya no copia ni las etiquetas** del
> cuadro del arquitecto: es una plantilla fija (PRD
> `docs/prd/2026-09-13-cuadro-plantilla-fija.md`). Las cuatro procedencias de
> arriba se quedan en tres —texto de la plantilla, valor medido, nota— y el test
> que lo guarda es `tests/test_plantilla_cuadro.py`. Los tests de
> `test_cuadro_propio.py` que lo guardaban sobre el cuadro clonado siguen
> vigilando `reparto_cuadro.cuadro_dibujable`, que ya no usa el producto.

---

> **Sobre la numeración de los tres apartados que siguen.** Nacieron el
> 2026-09-13 como `D-8`, `D-9` y `D-10`, y **esos números ya existían** en
> `docs/design/decisiones-pendientes.md` con otro significado (umbral de
> propuesta de Skill, push en sesión autónoma, tipo de cambio). El mismo día, por
> orden de Pablo —«tres etiquetas con dos significados en el mismo repo no se
> arreglan solas»—, se renumeraron a los primeros libres: **`D-13`, `D-14` y
> `D-15`**, en el código, los tests, los nombres de fichero y los documentos.
> Quien encuentre `D-8`…`D-10` en una conversación de ese día, que lea éstos.

## D-13 · Un `0,00 m²` no es nunca una superficie válida de estancia

**Dictaminado por:** Pablo, 2026-09-13, tras verlo en AutoCAD. **Deroga `C-4`.**

**Qué dice.** Ninguna celda de superficie de ningún cuadro que produzca ArchMuse
contiene `0,00`. Si la geometría de una estancia no está limpia, o el plano no
dibuja lo que una fila pediría, la celda se queda **vacía** y su motivo va en una
nota **debajo de la tabla, fuera del marco** — no altera la plantilla y se queda
en el plano. `C-5` no se toca: una terraza para dos huecos deja los dos sin cifra
y con nota, y ese es el mecanismo que se reutiliza.

**Cómo se midió el fallo.** Tres constructores del estado `CERO_REAL` en
`analyzer/cuadro_superficies.py` (familia simple, salón + cocina, familia
múltiple) más `condicionar_ceros` en `reparto_cuadro.py`, que sobre una medición
limpia los dejaba pasar. En el fixture sintético, antes del arreglo: por el
comando, `(6,1,'0,00 m²')` y `(7,1,'0,00 m²')`; por la web, dos `0,00 m²`.

**Cómo se guarda.** `CERO_REAL` ya no existe; su sitio lo ocupa `NO_DIBUJADA`,
que no escribe. Y **un guardián a la salida** (`cuadro_superficies.guardian_d13`)
convierte cualquier cero que se cuele en una celda vacía **con un motivo propio**
(`MOTIVO_GUARDIAN_D13`): no calla, y un test exige que ese motivo no aparezca
nunca. Tests: `tests/test_d13_ninguna_superficie_cero.py`,
`tests/test_plantilla_cuadro.py`.

## D-14 · El tamaño de la tabla lo decide el servidor, dentro de una ventana

> **ENMENDADO el 2026-09-13 (noche) por Pablo, tras probarlo en AutoCAD:** «Quita
> la fricción del tamaño. El arquitecto no debe adivinar cuánto mide la tabla ni
> recibir "marca una ventana mayor".» Ya no se pide una ventana: se pide **un
> punto** —la esquina de arriba a la izquierda— y la tabla sale a la altura
> mínima legible, del tamaño que necesita (`maquetacion_cuadro.maquetar_en_punto`,
> `.lsp` 3.4.0). La única negativa que queda es que pisaría su cuadro, y entonces
> se pide otro punto. Sigue en pie todo lo demás: el servidor decide el tamaño,
> ninguna palabra se parte y el umbral de legibilidad sale de sus cuadros o sus
> rótulos, nunca de una constante.
>
> **ENMENDADO otra vez el 2026-09-13 (madrugada), tras la 3.4.1 en AutoCAD.** La
> tabla del comando **no crea estilo de texto**: se dibuja con uno que ya existe
> en el plano —el de su cuadro, o el de sus rótulos—, y **los anchos los mide
> AutoCAD** con `textbox`. El servidor sigue decidiendo el tamaño, ahora con esas
> medidas (`/api/maquetar-cuadro`). **Si el plano no tiene ni cuadro ni rótulos
> de los que sacar el estilo, no se dibuja y se dice por qué**: no se inventa una
> fuente (Pablo). Motivo: crear un estilo con `arial.ttf` falló en `v1plantas.dxf`
> y depender de un `.ttf` concreto es frágil.

**Dictaminado por:** Pablo, 2026-09-13.

**Qué dice.** El comando pide una **ventana de dos esquinas** (declaración
explícita: manda sobre cualquier deducción, como en `C-8`). El servidor devuelve
la tabla resuelta: esquina, altura de texto, ancho de cada columna —proporcional
a su contenido— y posición de cada nota. **Ninguna palabra se parte.** Si no cabe
legible, no se dibuja y se pide una ventana mayor. El umbral de legibilidad sale
de la altura del texto del cuadro del arquitecto; sin cuadro, de la mediana de
las alturas de los rótulos de estancia del propio plano. **No hay constante.**

**Cómo se midió el fallo (hipótesis de mecanismo, síntoma visto).** Palabras
partidas en vertical en AutoCAD. En el `.lsp` 3.1 las medidas de la tabla eran
constantes escritas a mano (`1.0`, `14.0`) y la altura del texto no se fijaba,
así que la hereda del estilo del dibujo. **Que ésa sea la causa de lo visto no se
ha medido en AutoCAD**: el `.lsp` 3.2.0 no se ha ejecutado todavía.

**Cómo se guarda.** `analyzer/maquetacion_cuadro.py` y
`tests/test_d14_maquetacion_cuadro.py`, que además exige que `am:dibujar-cuadro`
no contenga ninguna medida literal.

## D-15 · La web nunca aplicó `C-4`

**Registrado por:** Pablo, 2026-09-13.

La exportación de la web (`cuadro_superficies_export.exportar_cuadro_relleno`)
nunca pasó por `condicionar_ceros`: escribía `0,00 m²` también con la medición
sucia. Con `D-13` la cuestión desaparece —ya no hay cero que condicionar— y la
web dibuja la misma plantilla que el comando. Test:
`test_d15_por_la_web_no_se_escribe_ningun_cero_ni_con_la_medicion_sucia`, y el
contenido igual por las dos vías en `test_dos_vias_leen_igual.py`
(`test_las_dos_vias_dibujan_la_misma_tabla`).

## C-12 · La superficie construida cerrada es la polilínea que el arquitecto rotula

**Firmado:** 2026-09-13, por un arquitecto colegiado («Queda FIRMADO. Es la
polilínea rotulada "Superficie construida cerrada"») y con el visto bueno de
Pablo a la forma de identificarla: **por su rótulo, no por el color**. «Es
declaración explícita del arquitecto, la misma lógica de C-8, y si no está el
rótulo la fila queda vacía en vez de coger otra polilínea.»

**Historia, para quien lea el código viejo.** Nació el mismo día como propuesta
de ArchMuse: la polilínea **con color propio** de la capa de recintos que
contuviera la vivienda. Estuvo desactivada (`C12_FIRMADO = False`) hasta que lo
confirmara un arquitecto. Al firmar se vio que el color no identifica una sola
cosa y se sustituyó entero; **el criterio por color ya no existe en el código**.

**El criterio.**

1. **El rótulo:** un TEXT o MTEXT del espacio modelo, de cualquier capa, que
   dice exactamente «superficie construida cerrada» o «s. construida cerrada»
   (sin distinguir mayúsculas ni acentos; espacios colapsados). Las dos formas
   están firmadas; «superficie construida exterior» y «s. construida ext.» no
   son esto.
2. **Su polilínea:** las `LWPOLYLINE` de **cualquier capa** —cerradas con el flag
   o recuperadas por geometría— cuyo borde está a **menos de 3 alturas del texto
   del rótulo** (firmado). **Si hay más de una, no se elige:** se declara y la
   fila queda vacía. Nunca la más grande ni la primera (condición 1 de Pablo).
3. **La comprobación:** la polilínea tiene que contener todas las piezas
   interiores de la vivienda y ninguna exterior (5 cm de tolerancia).
4. **La cifra sólo existe si hay exactamente una polilínea rotulada** que
   contenga la vivienda (condición 3). Sin rótulo, vacía con motivo: **nunca a
   cero, nunca otra polilínea parecida, nunca por color, ni como respaldo**
   (condición 2).

**Lo que se midió antes de escribir el código** (siete DXF de `_material`):

- En `v1plantas.dxf` la construida (`A6188E`) está **en `00 areas`** y es **la
  única roja**; la del Dormitorio 3 va por capa (naranja 30). Contradecía lo que
  se dijo al firmar; se pidió comprobarlo en AutoCAD.
- El rótulo, a 0,11-0,28 m del borde de su envolvente, con textos de 0,125; lo
  siguiente, a 0,49 m o más. `ejemplo.dxf` usa «S. construida cerrada».
- El `.lsp` sólo mandaba la capa de recintos: una construida en otra capa la
  habría visto la web y no el comando (`C-9`). Desde la 3.6.0 manda las
  polilíneas de las demás capas **sin color** (`otras_polilineas`).

**Lo que salió al implementarlo, medido:** ezdxf escribe altura 2,5 en todo
texto que llega sin ella (y también si se le da 0). Por la vía del comando, un
rótulo sin altura buscaba su polilínea a 7,50 m, y la maquetación de `D-14`
tenía el mismo fallo. Se marca con XDATA y se lee con
`geometria_recibida.altura_de_texto`.

**Cómo se guarda.** `tests/test_c12_construida_por_rotulo.py`: doce escenarios
sobre el fixture sintético (con y sin rótulo, abreviado, en otra capa y sin
color, otra polilínea mayor al alcance, dos rotuladas, sin altura, lejos, junto
a una pieza), el guardián de la condición 3 sobre todos, un guardián que prohíbe
leer el color en las tres funciones, las dos vías leyendo igual una construida en
otra capa, y la medición intacta con y sin las otras capas.

**Lo que queda abierto.** Qué hacer con una envolvente que contiene el patio o el
hueco de escalera. Y el parser ya conocía una capa `AM_CONS_CER` (contrato de
clasificación, Fase 3) que es otra forma de declarar la construida: `C-12` no la
usa y nadie ha decidido si debería.

---

## C-15 · Si los recintos están en una referencia externa, se dice dónde y no se mide

**Dictaminado por:** Pablo, 2026-09-15, tras medir los 70 DWG de un estudio:
«que el comando detecte la xref y diga "este dibujo referencia plantas base.dwg;
los recintos y el cuadro están ahí, abre ese fichero", en vez de culpar a la
capa», y «que ArchMuse no ofrezca elegir otra capa cuando ha detectado que los
recintos están en una xref. Elegir mal ahí acaba en cifra falsa, que es lo único
que no nos podemos permitir».

**Qué dice.** Antes de buscar el cuadro y antes de ofrecer la lista de capas, el
comando mira las referencias externas cargadas del dibujo. Si alguna tiene
polilíneas en la capa de recintos, dice qué fichero es, que los recintos —y el
cuadro, si también está— están ahí, y que lo abra. **No ofrece otra capa y no
mide.** Con la capa que él elija, si es otra, se repite la comprobación.

**Por qué.** `ssget "_X"` no ve el contenido de una xref, y el parser no puede
verlo nunca: en el DXF la definición de la xref tiene cero entidades. En una hoja
montada sobre un maestro, el comando no encontraba la capa, culpaba a su nombre y
ofrecía la lista; elegir otra capa ahí mide lo que no es. Medido el 2026-09-15:
19 de 58 DWG distintos del estudio tienen sus recintos sólo en una xref.

**Recintos a la vez en el dibujo y en la xref: también se para.** Lo propuso
Claude al aplicar la regla y **lo firmó Pablo el 2026-09-15**: «si hay recintos
aquí y en la xref, parar. Una cifra de menos es peor que no medir». En los 58 DWG
no apareció ningún caso real.

**Xref sin cargar: se avisa y se puede elegir capa. Decidido, y con un riesgo
abierto.** Pablo, 2026-09-15: «por ahora deja el aviso y que se pueda elegir
capa. Es un caso sin medir y no quiero cerrar la puerta a ciegas». De una xref
sin cargar no se puede saber qué tiene, así que no hay detección que justifique
pararse.

> **RIESGO ABIERTO.** Si la xref no está cargada y el arquitecto elige una capa
> cualquiera de la lista, **puede salir una cifra falsa igual**: es exactamente
> el fallo que `C-15` cierra para las xref cargadas. Lo único que hay delante es
> el aviso. En el estudio medido, 23 de 58 DWG distintos tienen alguna xref que
> no se resolvía en la copia; cuántas de ésas llevan los recintos no se sabe.

**Incumplimiento abierto de `C-9`: la vía web no sabe de xrefs.** El parser no las
ve y su `CapaIndeterminada` sigue diciendo «bloques». Con `C-15` el comando se
para y dice dónde están los recintos; la web, sobre el mismo plano, da otra causa.
**Las dos vías ya no leen igual.** Registrado en `C-9`.

**Alcance — medido en UN estudio.** En ese estudio el cuadro vive con sus
recintos en el plano maestro (521 cuadros, todos en los maestros; ninguno propio
en las hojas), así que el caso es molesto: basta abrir el maestro. **Otro estudio
que ponga el cuadro en la hoja y los recintos en la xref cae en este caso cada
vez**, y con este criterio no mide nada allí. Eso no se ha medido en ningún otro
estudio.

**Dónde se aplica.** `autocad/archmuse.lsp` 3.7.0: `am:xrefs`,
`am:contenido-de-xref`, `am:recintos-en-xref-p`, `am:avisar-xrefs-sin-cargar`, y
`c:ARCHMUSE` antes de buscar el cuadro y después de elegir capa.

**Cómo se guarda.** `tests/test_c15_referencias_externas.py` sobre el fuente, y la
ejecución de las funciones de detección en AutoCAD Core Console sobre copias de
DWG reales (`docs/PROGRESS.md`, 2026-09-15).

---

## C-16 · El comando ARCHMUSE deja AutoCAD exactamente como lo encontró, pase lo que pase

**Estado: PROPUESTO, PENDIENTE DE FIRMA.** Lo pidió Pablo el 2026-09-15, al abrir
una auditoría del comando: «ArchMuse deja AutoCAD exactamente como lo encontró,
pase lo que pase». La redacción es de Claude y no está firmada.

**Qué dice.** Las variables de sistema, los ajustes y el registro de AutoCAD
quedan como estaban al terminar el **comando**: si acaba bien, si falla a medias y
si el arquitecto pulsa Esc en cualquier pregunta. Lo que ArchMuse dibuja no entra
aquí: va en un solo grupo de deshacer, y tras un Esc o un fallo se retira (`C-3`).

**Se refiere al comando (`archmuse.lsp` dentro de AutoCAD), no al instalador.**
El instalador y el actualizador sí escriben en el registro de AutoCAD —añaden la
carpeta de ArchMuse a `TRUSTEDPATHS`—, lo hacen a propósito, lo dicen en la
pantalla del instalador y lo quitan al desinstalar. Eso está bien y no incumple
este criterio.

**Por qué.** Es `C-7` otra vez: el servidor no ve el estado de AutoCAD, así que
ningún test del servidor puede verlo. Y un ajuste que un comando deja cambiado lo
encuentra el arquitecto horas después, en otro comando, sin nada que lo relacione
con quien lo cambió.

**Auditoría del 2026-09-15, leyendo el `.lsp`:**

| Qué toca | Al terminar | Si falla o pulsa Esc |
|---|---|---|
| CMDECHO, la única variable que cambia | se devuelve | se devuelve en *error* |
| Grupo de deshacer | se cierra | **no se cerraba**: arreglado en 3.7.1 |
| FILEDIA, OSMODE, capa, color, estilo de tabla y de texto activos, SECURELOAD | no se tocan | no se tocan |
| Órdenes de AutoCAD | sólo `_.DELAY` y `_.U` | lo mismo |

**El hueco que encontró.** Un Esc o un error sin capturar mientras dibujaba
dejaba el grupo de deshacer abierto y la tabla a medias sin marca de borrador. Desde
el `.lsp` 3.7.1, *error* cierra el grupo y retira lo dibujado. **El Esc a mitad del
dibujo no se ha ejecutado en AutoCAD todavía.**

**Medido por Pablo con el guardián, 2026-09-15, 0.3.8:** hasta el final y Esc al
pedir el punto, «AutoCAD está exactamente como estaba», sin «Registro cambiado».
Esc en la capa y servidor parado: sin informe, así que sin medir.

> **Nota sobre FILEDIA — CORREGIDA el 2026-09-16.** Aquí ponía «ArchMuse
> descartado; causa desconocida», y el descarte estaba mal hecho: sólo se miró el
> comando. **Causa reproducida:** AutoCAD Core Console escribe `FileDialog = 0` en
> el perfil del usuario al arrancar y sólo lo devuelve si sale limpio. Los Core
> Console matados de las herramientas de desarrollo lo dejaron a 0 el 14 y el
> 15-sep, y cada reinicio de AutoCAD tras instalar lo leía. El comando sigue sin
> tocarlo. Informe: `docs/audits/2026-09-16-incidente-filedia-a-cero.md`.
>
> **Ampliación propuesta el 2026-09-16, pendiente de firma:** `C-16` vale también
> para **la instalación, la actualización (con ARCHMUSE-ACTUALIZAR), el arranque de
> AutoCAD y cualquier herramienta del repositorio que lance AutoCAD o Core
> Console**. Lo único que pueden cambiar es lo que el instalador ya dice:
> `TRUSTEDPATHS`, para añadir o quitar la carpeta de ArchMuse. Core Console sólo se
> lanza por `herramientas/core_console.py`, con `/isolate`.

**Dónde se aplica.** `autocad/archmuse.lsp` 3.7.1: el *error* de `c:ARCHMUSE` y
la bandera `grupo-abierto`.

**Cómo se guarda.** Dos piezas, y ninguna basta sola:
`tests/test_lsp_deja_autocad_como_estaba.py` en la suite, leyendo el código (una
variable o una orden nueva, el grupo sin cerrar); y
`herramientas/guardian_autocad/guardian.lsp`, que lo comprueba **ejecutando
ARCHMUSE en un AutoCAD real**: foto de las variables y del registro antes, el
comando como se quiera probar, y foto después. Desde el 2026-09-16 la foto se
guarda en un fichero, y el guardián sirve también para ARCHMUSE-ACTUALIZAR y para
cerrar y abrir AutoCAD. Lo que pasa fuera de AutoCAD lo vigilan
`tests/test_guardian_instalacion_y_arranque.py`,
`tests/test_core_console_no_toca_autocad.py` y
`herramientas/guardian_autocad/guardian_registro.py`.

---

## C-17 · Un clic mide la vivienda más cercana al punto; si hay duda, no mide

**Estado: PROPUESTO, PENDIENTE DE FIRMA.** Lo pidió Pablo el 2026-09-15: «el
usuario hace UN clic al lado del dibujo de una vivienda y ArchMuse mide SOLO esa
vivienda […]. El clic elige la vivienda: la más cercana al punto. Si hay duda (dos
a distancia parecida), no mide y lo dice». La redacción y **los tres números son
de Claude** y no están firmados. PRD `docs/prd/2026-09-15-un-clic-una-tabla.md`.

**Qué dice.**

1. La distancia del punto a una vivienda es la distancia a la más cercana de sus
   piezas (cero si el punto cae dentro de una).
2. Se mide la vivienda más cercana, **salvo que haya duda**: la segunda más
   cercana está a menos del **doble** de distancia que la primera, o a menos de
   **1 m** más lejos. Entonces no se mide, y se dicen las dos distancias. **Un
   punto dentro de una pieza de una sola vivienda no tiene duda** (añadido el
   2026-09-15 tras medir el maestro: 7 de 52 clics dentro de la pieza mayor de su
   vivienda caían en la regla del metro por el tabique de la de al lado).
3. Si la más cercana está a más de **30 m**, no se mide: un clic tan lejos no
   dice de qué vivienda es la tabla.
4. **Rótulo repetido: el clic la distingue por su posición** (enmienda de `C-13`
   firmada por Pablo el 2026-09-15). Se mide la elegida, sola; nunca se suma ni
   se funde con la otra. Este punto sí está firmado; los tres números de arriba,
   no.

**Por qué no se elige ante la duda.** Es la lógica de `C-5` y `C-15`: una tabla de
la vivienda de al lado, dibujada donde él ha marcado, es una cifra falsa en el
sitio correcto — la que menos se ve.

**Cómo se guarda.** `tests/test_un_clic_una_tabla.py`, con planos sintéticos.

---

## C-18 · Una cifra de área nunca es el nombre de una pieza

**Dictaminado por:** Pablo, 2026-09-15, tras ver en AutoCAD (0.3.12) el maestro del
estudio sin una sola pieza reconocida: «Un texto que es solo una cifra de área
(23.24m², 8,53 m2, 3.16...) nunca es el nombre de una pieza. Con varios textos en
un recinto, gana el que es un nombre reconocible, sin depender del orden de ssget.
Si hay dos nombres distintos, no se elige: se deja vacío con motivo.» Y: «Nunca
preguntar por un rótulo sin sentido como «M»». **Cierra la parte de `D-7`** que
decía qué texto nombra un recinto cuando hay varios.

**Qué dice.**

1. Un texto que es sólo una cifra, con o sin «m²/m2», no nombra una pieza.
2. Entre varios textos dentro de un recinto gana el nombre reconocible (una
   familia del vocabulario de medición); si ninguno lo es, el que tiene una
   palabra de tres letras sobre un código («F», «PE-01»). El orden no cuenta.
3. El mismo nombre repetido es un nombre. **Dos nombres distintos no se eligen**:
   la pieza queda sin fila y la nota dice cuáles eran.
4. **Nunca se pregunta** «¿interior o exterior?» por un rótulo sin una palabra de
   tres letras: se anota que no es un nombre de estancia.

**Por qué.** El maestro rotula cada recinto con su nombre (tres veces) y con un
campo de AutoCAD que escribe su área. Leído en el orden del DXF salía bien; desde un
`ssget` el campo llegaba primero, el recinto se llamaba «23.24m²», se bloqueaban
los totales y la construida, y la pregunta era por «M» —lo que queda de «m²» sin
cifras—.

**Dónde se aplica.** `parser._es_cifra_de_area`, `parser._elegir_nombre`,
`parser.match_label_to_room` (`conflicto`), `Room.rotulos_en_conflicto` y
`plantilla_cuadro.construir`.

**Cómo se guarda.** `tests/test_rotulo_con_cifra_de_area.py` (sintético) y el test
de orden de `tests/test_dos_vias_leen_igual.py`, ya sin xfail.

---

## C-20 · Una polilínea rotulada como construida nunca es superficie útil

**Dictaminado por:** Pablo, 2026-09-16, tras un error de cifra. **Criterio firmado**
en lo que dice Pablo; las cuatro decisiones de cómo se lee, abajo, son **propuestas,
pendientes de firma**.

**Qué dice (Pablo).** Una polilínea rotulada como construida (interior o exterior)
nunca puede usarse como superficie útil de una estancia. **Si hay duda sobre cuál es
la útil, la celda queda vacía con motivo.**

**El caso que lo motiva.** Un tendedero del plano maestro dibujado con dos
contornos: el útil, con su nombre, y alrededor la construida exterior, rotulada «S.
construida ext.». ArchMuse escribía la construida como útil, y el error pasaba al
total exterior y al útil. Medido: el contorno útil tiene `closed=False` y se cierra
**encima de su primer tramo** con una cola del 5 % de su diagonal; se descartaba por
abierto y la construida, ya sin nadie dentro con su nombre, ocupaba su sitio.

**Qué es «rotulada»** (la lectura de `C-12`): un rótulo señala los contornos de la
capa de recintos cuyo borde está a menos de 3 alturas de su texto.

**Decisiones propuestas, pendientes de firma:**
1. **Formas del rótulo:** las dos firmadas de la cerrada y, de la exterior, «s.
   construida ext.», «superficie construida exterior» y «s. construida exterior».
   «Sup. construida» a secas no dice cuál es y no cuenta.
2. **Contornos anidados al alcance del mismo rótulo:** si uno contiene a los demás,
   el rotulado es ése (la construida contiene a la útil) y los de dentro no están en
   duda. Sin esto, la mitad de los tendederos del plano maestro, que hoy coinciden
   con el arquitecto, quedarían vacíos.
3. **Dos o más contornos al alcance sin que uno contenga a los otros:** duda, y
   ninguno se escribe como útil.
4. **Un contorno rotulado sale de las estancias si todos los nombres que tiene
   dentro están también dentro de otra estancia**, que es la que lo representa (o
   si no tiene ninguno). Si no, se queda como estancia **sin cifra y con motivo**,
   y ningún total de la vivienda se escribe: la estancia no puede desaparecer en
   silencio, ni el total salir corto. *Corregido el mismo día:* la primera versión
   pedía que contuviera la otra estancia al 90 %, y una construida exterior que
   cubría el 88 % de su terraza útil se quedaba, solapada con ella.
5. **Una pieza cuyo reparto entre viviendas no es firme** (`HOLGURA_MINIMA_DE_REPARTO`)
   se enseña **sin cifra** en la tabla, con la nota de entre qué viviendas duda.
   Medido en el plano maestro: en cuatro parejas de viviendas vecinas el reparto
   por cercanía metía un dormitorio o un aseo de una en la tabla de la otra, con
   su cifra. Los totales ya salían vacíos; la fila no.

**Regla de Pablo del 2026-09-17, propuesta y pendiente de firma: si ArchMuse no puede
demostrar que una cifra pertenece a esa vivienda, no la muestra.** Aplicada sin
heurísticas nuevas, cruzando dos señales que ya existen: el reparto firme y la
construida rotulada leída con `C-12`. Una construida rotulada es de una vivienda
cuando contiene todas sus piezas interiores de reparto firme y ninguna exterior. Si una
pieza está dentro de la construida de otra vivienda y no de la suya, su celda queda
vacía con motivo («puede ser de …»). Sin construida rotulada no cambia nada.
Dónde: `plantilla_cuadro.piezas_de_otra_vivienda`. Test:
`tests/test_pieza_de_otra_vivienda.py`.

**El cierre montado (arreglo, no criterio).** Una polilínea con `closed=False` cuyo
último vértice cae encima de su primer tramo (a menos del 1 % de su diagonal, entre
sus extremos) se lee cerrada sin la cola, **si la cola no pasa del 10 % de la
diagonal** y la superficie no cambia más del 1 % se lea como se lea. Con una cola
larga está mal dibujada y sigue abierta.

**Dónde se aplica.** `analyzer/construida_rotulada.py`; `parser._anillo_montado`,
`parser._puntos_del_anillo`, `parser.extract_room_polygons` (`no_utiles`),
`Room.no_es_util`; `medicion.PiezaMedida.no_es_util` e impedimento de la vivienda;
`plantilla_cuadro.construir` (celda vacía con nota). No mira el color.

**Cómo se guarda.** `tests/test_construida_nunca_es_util.py`, sobre un plano
sintético: el tendedero útil abierto con cola dentro de su construida exterior; sin
contorno útil (celda y totales vacíos, también en la medición); la construida sin
color propio; la forma larga del rótulo; los dos anidados al alcance; la duda entre
dos que no se contienen; el rótulo lejos; y que el módulo no lea el color.

---

## C-19 · Los totales se calculan con las áreas sin redondear

**Dictaminado por:** Pablo, 2026-09-16, siguiendo al arquitecto. **Criterio
firmado.**

**Qué dice.** Los totales se calculan con las áreas **sin redondear**, y sólo se
redondea el resultado final a dos decimales: total interior, total exterior, el
50 %/10 % de `C-14` y el total útil. **Aunque a mano la tabla no cuadre por un
céntimo, así lo hace el arquitecto.**

**El caso que lo motiva.** Una vivienda de su plano maestro: la tabla del
arquitecto suma los campos de área sin redondear, y ArchMuse sumaba las cifras
publicadas y se quedaba un céntimo por debajo.

**Qué no cambia.** Cada pieza se sigue publicando redondeada a dos decimales. El
redondeo de un medio exacto sigue siendo hacia arriba (decisión de ArchMuse,
declarada en `C-14`).

**Dónde se aplica.**
- `medicion.ViviendaMedida`: la útil interior y la exterior, y la suma de las
  piezas, sobre `PiezaMedida.area_cruda_m2`; la planta, sobre la suma sin
  redondear de sus viviendas.
- `plantilla_cuadro.construir`: los dos totales y `C-14` sobre las sumas sin
  redondear.
- `cuadro_superficies._celda_total`: sobre el área sin redondear de cada celda
  calculada. Una cifra ya escrita en el plano o declarada por el arquitecto se
  suma tal como está.

**Cómo se guarda.** `tests/test_c19_totales_sin_redondear.py`: un plano sintético
en el que cada pieza redondea hacia abajo, de modo que las dos formas de sumar dan
distinto (41,00 frente a 41,01; útil 44,75 frente a 44,77), por la medición, por la
tabla de ArchMuse y por el reparto sobre el cuadro.

---

## Lo que sigue sin firmar

De los tres criterios que `D-7` enumera desde el 2026-08-19, **`C-1` y `C-2`
resuelven el tercero** (qué hacer ante un solape) y `C-5` cierra el segundo.
Sigue abierto:

1. **El orden del procedimiento de `superficies.cuadro_de_vivienda`** —
   comprobar la unidad antes de medir, medir por un camino separado del cálculo,
   y cruzar los dos. Ese orden es criterio profesional y hoy lo eligió Claude.
2. ~~**Qué hacer ante una ambigüedad de reparto.**~~ **Firmado el 2026-09-10
   como `C-5`.** Y con una corrección de los hechos que lo motivaron: las «dos
   piezas Tendedero» de las que hablaba este punto **no existían** — eran un
   tendedero y el contorno que lo agrupa con la terraza. El caso de «una Terraza
   para dos filas» sí es real, y es el que sostiene el criterio.

Y de las cuatro preguntas abiertas de la sesión de validación siguen sin
contestar dos: **qué vocabulario de rótulos** reconoce el motor (hoy ocho
familias, y lo que no entra bloquea la vivienda entera) y **la tasa real de
discrepancias** memoria↔plano, que es la que gobierna el PRD del 2026-08-22.
