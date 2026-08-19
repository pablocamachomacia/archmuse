# Qué Skill construir después, y por qué — evaluación de valor comercial

**Fecha:** 2026-08-19 · **Tipo:** evaluación de producto, no PRD · **Estado:** para decisión de Pablo

Encargo directo: «evaluar qué Skills tienen mayor valor comercial: detalles
constructivos, carpintería, BIM/IFC, normativa». Este documento las evalúa, y
**dos de las cuatro las evalúa contra una medición sobre el plano real del
cliente, no contra una impresión** — el sondeo está en la §3 y es el hallazgo
más accionable de todo el documento.

`docs/AGENTE_BACKLOG.md` §3 ya tiene veredicto sobre doce trabajos (OP-1 a
OP-12). Esto **no lo repite**: se ocupa de lo que no estaba evaluado —
carpintería y detalles constructivos no aparecen en ningún sitio del
repositorio— y revisa BIM y normativa sólo donde hay dato nuevo.

---

## 1. La rejilla con la que se decide

Cinco preguntas, y la primera manda sobre las otras cuatro:

1. **¿Está el dato?** Si ArchMuse tiene que preguntarle al arquitecto el 90 % de
   lo que va en el entregable, no es una Skill: es un formulario. Y un
   formulario no ahorra la tarde de trabajo que es la promesa entera.
2. **¿Cuánto duele hoy?** Frecuencia × tedio. Una tarea anual y odiosa vale
   menos que una semanal y molesta.
3. **¿Hay foso?** `MOAT_ANALYSIS.md`: lo defendible es el corpus y la
   trazabilidad, no el dibujo ni la generación.
4. **¿Cuánto cuesta equivocarse?** Un cuadro de superficies mal sumado se
   corrige; una memoria mal citada es responsabilidad civil del que firma.
5. **¿Reutiliza el procedimiento de `SK-1`?** Es la pregunta barata: leer
   geometría, producir una tabla, negarse a adivinar, escribir una copia del
   DXF, PDF con procedencia celda a celda y acta. Todo eso ya existe y está
   probado sobre un plano real.

---

## 2. El resultado, en una tabla

| Candidata | ¿Está el dato? | Dolor | Foso | Coste del error | Reutiliza SK-1 | **Veredicto** |
|---|---|---|---|---|---|---|
| **Cuadro de carpintería** | **No: las ventanas no están** (§3, dos planos medidos) | Alto | Medio | Bajo | Casi entero | **NO como estaba pensada.** Sólo puertas, o reconocer huecos en muros (otro proyecto) |
| **Memoria justificativa** | No (falta corpus) | Máximo | Alto | **Máximo** | Poco | La mitad honesta, ya con PRD |
| **Revisión normativa de planta** (`SK-2`) | No (falta corpus) | Alto | **El más alto** | Alto | Medio | Bloqueada por `NOR-2`. Correcto |
| **BIM / IFC** | Sí, y no sirve de mucho | Bajo | Bajo | Bajo | Poco | V2, confirmado. §5 |
| **Detalles constructivos** | **No, y no lo estará** | Medio | **Ninguno** | Alto | Nada | **No se hace.** §6 |
| *(evaluada de oficio)* **Mediciones y presupuesto** | Parcial | **Máximo** | Bajo | Medio | Medio | No en este horizonte. §7 |

---

## 3. Carpintería — el hallazgo, con las cifras delante

Era mi favorita antes de mirar el fichero. El razonamiento *a priori* era
sólido: un cuadro de carpinterías es una tabla de piezas con sus dimensiones,
igual que el cuadro de superficies es una tabla de recintos con las suyas, así
que el procedimiento de `SK-1` transfiere casi entero y no hace falta ni una
línea de corpus normativo.

**Lo medí sobre `v2s.dxf` antes de escribir un PRD, y la conclusión cambió.**

### 3.1 Lo que sí hay

Las 427 definiciones de bloque traen las **puertas** con el dato dentro del
propio nombre, tal como las exportó Revit:

```
K_Puerta de entrada - 825 x 2150 mm-2293629-VT25 - Mobiliario
K_Puerta abatible - P - 725mm - DM lacado blanco-1967079-VT25 - Mobiliario
DIR04_PE-_PUERTA - PE-01-2783739-VT25 - Mobiliario
```

Ahí están el tipo, las dimensiones, el acabado, un identificador único de
instancia y **a qué vivienda tipo pertenece**. Las 25 viviendas tipo tienen
entre 3 y 9 piezas de carpintería cada una. De las 4 de la VT25, **3 llevan la
dimensión en el nombre y 1 no**.

### 3.2 Lo que no hay, y es lo que decide

**Las ventanas no están.** Buscando en las 427 definiciones, todo lo que suena a
ventana son cuatro bloques genéricos: `ven01`, `ven2`, `ven3` y
`00 SEC VENTANA`. Sin dimensiones en el nombre, sin acabado, y **sin asociación
a ninguna vivienda tipo**. Es decir: las ventanas de este proyecto están
dibujadas como geometría, no como objetos identificados.

Eso importa más de lo que parece, porque **en un cuadro de carpintería español
las ventanas son la mitad cara**: son las que llevan vidrio, las que el DB-HE
mira, las que se presupuestan pieza a pieza y las que el cliente cambia tres
veces. Un cuadro de carpintería que trae las puertas y deja las ventanas en
blanco no ahorra la tarde: obliga a hacer la mitad difícil a mano y encima a
comprobar la fácil.

**Y el segundo problema, ya conocido:** hay **0 `INSERT` en el modelspace**, que
confirma lo que midió `docs/design/2026-08-11-poc-bloques-vt.md`. La carpintería
existe *dentro* de las definiciones de vivienda tipo, así que se puede contar
**por vivienda tipo** —que es justamente la granularidad del cuadro de
carpintería del proyecto básico, y eso es una buena noticia— pero no se puede
saber cuántas puertas lleva el edificio, porque el dato de qué vivienda va dónde
no está en este fichero. No es que el parser no lo lea: es que no existe.

### 3.3 El segundo plano, medido el 2026-08-19: confirma, no rescata

El veredicto de la §3.2 pedía **medir un segundo plano antes de decidir**, porque
una muestra de uno no distingue una convención del sector de la costumbre de
este estudio. Ya está medido: `V5.dxf`, 606 definiciones de bloque.

**Da exactamente lo mismo que el primero, hasta en los nombres:**

- Las **puertas** siguen trayendo el dato en el nombre del bloque
  (`K_Puerta de entrada - 825 x 2150 mm-…-VT25`), con su vivienda tipo.
- Las **ventanas** son otra vez los mismos cuatro bloques genéricos —`ven01`,
  `ven2`, `ven3`, `00 SEC VENTANA`— sin dimensiones y sin asociación a ninguna
  vivienda tipo.
- **0 `INSERT` en el modelspace**, igual que en el primero.

Dos ficheros distintos, la misma estructura. Ya no es una muestra de uno: es
**cómo dibuja este estudio**, y no hay nada en el fichero de lo que sacar el
cuadro de ventanas.

### 3.4 Veredicto

**Medido el segundo plano: la Skill de carpintería NO se hace como estaba
pensada.** El sondeo era la condición para decidir, y ha decidido que no.

Las ventanas no están en ninguno de los dos ficheros, y las ventanas son la
mitad cara del cuadro: las del vidrio, las que mira el DB-HE, las que se
presupuestan pieza a pieza y las que el cliente cambia tres veces. Un cuadro de
carpintería que trae las puertas y deja las ventanas en blanco **no ahorra la
tarde**: obliga a hacer a mano la mitad difícil y encima a comprobar la fácil.

Quedan dos caminos, y ninguno es el que se iba a escribir:

1. **Cuadro de puertas, y llamarlo así.** Un día de trabajo, entregable honesto,
   valor bastante menor del que prometía la idea original. Se puede hacer cuando
   no haya nada mejor en la cola; hoy lo hay.
2. **Reconocer huecos en muros**, que es lo que haría falta para las ventanas.
   Eso no es esta Skill: es visión por computador sobre geometría de DXF, son
   semanas y no días, y merece su propio PRD y su propia decisión. Es además la
   pieza que desbloquearía varias cosas a la vez —carpintería, superficies
   construidas, DB-HE—, así que si algún día se hace, se hace por eso y no por
   el cuadro de carpintería.

**El sondeo costó media jornada y evitó tres días de Skill** contra un fichero
que no tiene el dato. Es el mejor argumento que hay en este documento a favor de
medir antes de escribir.

---

## 4. Normativa — sin novedad, y la falta de novedad es el dato

`SK-2` (revisión de planta) sigue siendo la de más foso del catálogo y sigue
bloqueada por lo mismo: **el corpus tiene una regla y sin firmar**. No hay nada
que evaluar aquí que no estuviera evaluado, y ese es el punto: **es la única
candidata cuyo desbloqueo no depende de ninguna decisión técnica**. Depende de
contratar a un colegiado (C5, `NOR-1`).

Merece decirse claro porque es incómodo: cualquier hora que se ponga en las
otras candidatas de esta lista es una hora que no acerca `NOR-2`, y `NOR-2` es
`P0` continua. La única defensa honesta de este documento es que transcribir
normativa **no lo puede hacer un programador**, así que las dos colas avanzan en
paralelo sin competir. El día que haya colegiado contratado, esa defensa se cae
y la prioridad es evidente.

---

## 5. BIM / IFC — confirmado en V2, con un argumento que faltaba

`OP-5` ya dice lo esencial: la lectura funciona (`bim/lector_ifc.py`), y lo que
falta no es leer IFC sino tener con qué contrastarlo.

Añado el argumento comercial que no estaba escrito, y que a mí me parece
decisivo: **un IFC llega de Revit, y en Revit el arquitecto ya tiene las tablas
de planificación.** Contarle lo que hay en su propio modelo tiene valor cercano
a cero — lo hace su software, mejor, y ya lo ha pagado. Lo único que ArchMuse
puede hacer y Revit no es **cruzar el IFC contra otra fuente**: contra el DXF,
contra lo que el cliente pidió, contra la normativa. Las tres necesitan el grafo
de proyecto (`ME-2`), y las tres son V2.

Corolario práctico: **no ampliar `bim/` mientras tanto.** Cada capacidad nueva
de lectura IFC es catálogo sin cobertura, que es exactamente lo que C4 prohíbe.

---

## 6. Detalles constructivos — no se hace, y conviene dejarlo escrito

Es la única de las cuatro que rechazo de plano, y por el mismo motivo por el que
`OP-11` congela el generador de plantas.

1. **El dato no está y no va a estar.** Un detalle constructivo no se deriva del
   proyecto: se **elige**, con criterio, entre soluciones que dependen del clima,
   del sistema constructivo, del presupuesto y de con qué industrial trabaja el
   estudio. ArchMuse no tiene ninguno de esos cuatro datos, y pedirlos todos es
   un formulario.
2. **Foso nulo, y competencia gratuita.** Todo estudio con dos años de vida
   tiene su biblioteca de detalles, afinada a base de obras, y **no la va a
   cambiar por una generada**. Además existen las bibliotecas de los fabricantes,
   gratis y con garantía del fabricante detrás.
3. **Es lo más cercano a la autoría de todo el catálogo, y por tanto lo que más
   tensiona C3.** Un detalle mal resuelto no es un aviso en un PDF: es una
   humedad, un puente térmico o un desprendimiento. La frontera de
   `NORTH_STAR_2031.md` §5 se rompe justo aquí.
4. **Demuestra muy bien y no vende** — el patrón exacto que `MOAT_ANALYSIS.md`
   identifica en el visor 3D y en el generador.

Queda registrado aquí para que nadie lo redescubra como idea nueva dentro de
seis meses, igual que `OP-11`.

---

## 7. Mediciones y presupuesto — evaluada de oficio, y descartada por ahora

No estaba en el encargo y la evalúo porque, si se pregunta a un arquitecto
español qué documento del proyecto le roba más vida, la respuesta no es la
memoria: son las **mediciones**. Superficies de solado, de pintura, de falso
techo, metros de rodapié — todo derivable de la misma geometría que ArchMuse ya
lee, y con el mismo procedimiento de `SK-1`.

**Y aun así, no.** Tres motivos:

1. **Presto y Arquímedes llevan treinta años en esto**, con bases de precios
   mantenidas (BC3), y el formato de intercambio es su formato. Entrar ahí es
   competir de frente con producto maduro, no ocupar un hueco.
2. **El valor no está en medir: está en la base de precios**, que es un activo
   que hay que mantener y que ArchMuse no tiene ni tendría cómo mantener.
3. **Es un proyecto grande disfrazado de Skill.** Medir bien exige capas de
   acabados, alturas y encuentros que este parser no lee hoy.

Si algún día se hace, se hace **exportando a BC3** para que entre en el Presto
del arquitecto — no sustituyéndolo.

---

## 8. Recomendación

**Por orden, y con el colegiado sin contratar:**

1. **Media jornada: medir un segundo plano real** con el sondeo de la §3. Es lo
   más barato de esta lista y es lo que decide si la mejor candidata lo es de
   verdad. Ninguna decisión más de carpintería antes de eso.
2. **`MJ-1` a `MJ-3`** del PRD de la memoria justificativa —la arquitectura común
   de Skills— que valen aunque el resto de ese PRD se cancele. (`MJ-1` y `MJ-2`
   ya están hechas: son refactor, no capacidad nueva.)
3. **Nada de BIM, nada de detalles constructivos, nada de mediciones.**

**Y con colegiado contratado, la lista entera se reordena:** todo lo de arriba se
aplaza y la prioridad es `NOR-2`. Es la única candidata con foso real, y es la
única cuyo cuello de botella no lo desbloquea ningún programador.

---

**Decisión:** _pendiente de revisión por Pablo_
