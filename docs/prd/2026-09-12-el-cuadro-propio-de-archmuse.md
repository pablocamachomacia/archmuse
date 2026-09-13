# PRD — El cuadro propio de ArchMuse, siempre, y nunca encima del suyo

**Estado:** **APROBADO** · **Fecha:** 2026-09-12 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo, 2026-09-12

> **Alcance de la aprobación, literal.** Pablo aprobó las cinco respuestas de
> diseño *«tal cual»*: copiar sus filas literales (errata incluida), a la derecha
> con `getpoint` movible, el motivo dentro del propio cuadro, y los N cuadros
> dentro de este trabajo. Más dos encargos expresos: que el cambio de «no
> calcular» a «calcular siempre» quede como **núcleo** (§0) y no como detalle, y
> un checklist corto para el trial (§12). Orden fijado: **PRD → servidor →
> `.lsp`**. El riesgo de escribir el `.lsp` a ciegas lo asume él.

> **Origen: cambio de diseño pedido por el arquitecto**, trasladado por Pablo el
> 2026-09-12. No sale de una medición nuestra ni de una idea de producto: sale
> del usuario real diciendo que lo que habíamos construido es más estrecho de lo
> que el producto tiene que ser.

> **Qué sustituye y qué redirige.**
>
> - **Sustituye a `2026-09-11-crear-el-cuadro-donde-no-lo-hay.md`** (Borrador,
>   nunca aprobado). Aquel cubría un caso —«no hay cuadro»— y se paraba a esperar
>   un dato del arquitecto. El dato ha llegado y es más ancho que la pregunta:
>   se dibuja **siempre**, haya cuadro o no. Aquel PRD pasa a ser el caso A de
>   éste. **Su §14.2 queda resuelta**, y abajo se explica cómo.
> - **Redirige `2026-09-10-rellenar-el-cuadro-del-arquitecto.md`** (Aprobado,
>   implementado). Su motor entero sigue vivo; lo que cambia es **el destino de
>   las cifras**. Sus `CU-1`…`CU-5` siguen siendo los casos de uso buenos, con
>   otra salida.
> - **No toca `2026-08-22-contraste-superficies-memoria-vs-plano.md`**, que es
>   otro problema (memoria PDF contra plano) y sigue en su gate.

---

## 0. El núcleo del cambio, y no es «dibujar una tabla»

Dibujar la tabla es la parte visible. **El cambio de verdad es de una línea y
está en el cálculo:**

```
hoy:    si la celda del arquitecto ya tiene texto -> NO SE CALCULA
mañana: se calcula SIEMPRE. Su celda no es una entrada; es que no la tocamos.
```

Hoy `cuadro_superficies._resolver_o_preexistente` ve una celda con contenido y
**ni siquiera llama al cálculo**: devuelve «ya había un valor, no se recalcula».
Era la forma correcta de cumplir «nunca sobrescribir» cuando el destino era su
celda. Con destino propio, esa misma línea deja a ArchMuse mudo sobre un plano
que ha medido entero.

**De ahí salen las 158 cifras.** Medido sobre `plantasimple.dxf` el 2026-09-12,
mismas filas, misma medición, cambiando sólo esto:

| Las 396 celdas de los 22 cuadros emparejados | Hoy | Con cuadro propio |
|---|---:|---:|
| Celdas que ArchMuse afirma | 74 | **232** |
| De ellas, `0,00 m²` | 73 | 74 |
| **Cifras reales** | **1** | **158** |

No es una mejora incremental: hoy la capacidad, sobre el único proyecto completo
del lote, aporta **un aseo de 3,81 m²**.

«Nunca sobrescribir» no se debilita — **se cumple mejor**: pasa de ser una regla
del cálculo (frágil, porque depende de acertar qué celda está llena) a ser una
propiedad de la arquitectura (no escribimos en su tabla porque no escribimos en
su tabla).

## 1. Problema que resuelve

ArchMuse mide bien y **no tiene dónde poner lo medido** salvo que el plano venga
preparado. De los seis planos reales:

| | Cuadros | Qué pasa hoy |
|---|---:|---|
| `v1plantas`, `v2s`, `v3s` | 1 | Se rellena lo que él dejó vacío |
| `plantasimple` | **25** | Se lee **uno**; se escriben 74 celdas, 73 son ceros |
| `V5` | **0** | El comando se para: *«no sé rellenarlo»*. Y es el plano que mejor mide |
| `ejemplo` | 1 | Llega con casi todo declarado |

Los tres modos de fallo son el mismo: **el producto depende del hueco que le deje
el arquitecto**. Un proyecto terminado no deja huecos, y un proyecto empezado no
tiene cuadro.

## 2. Usuario afectado

El arquitecto, en los dos momentos de su trabajo:

- **Antes de documentar** (`V5.dxf`): planta distribuida, sin cuadro. Quiere las
  cifras para empezar.
- **Documentando o revisando** (`plantasimple.dxf`): cuadro hecho a mano.
  Quiere **comprobar** que lo que escribió es lo que hay dibujado.

El segundo es el que hoy no se atiende en absoluto, y es el de los 25 cuadros.

## 3. Objetivo de negocio

Que ArchMuse **entregue siempre**, con cualquier plano medible, sin depender del
estado de la documentación del cliente. Es la diferencia entre una herramienta
que funciona en el 60% de los planos del lote y una que funciona en el 100% de
los que sabe medir.

Y desbloquea lo que estaba bloqueado: la beta instalable no puede salir a un
estudio real si el producto se rinde ante un proyecto terminado.

## 4. Objetivo técnico

Una vez implementado, debe ser cierto que:

1. **ArchMuse dibuja su cuadro en los tres casos**: sin cuadro en el plano, con
   cuadro vacío, y con cuadro relleno.
2. **Ninguna entidad previa del dibujo se modifica.** Ni una celda, ni un texto,
   ni un vértice. Comprobable, no prometido.
3. Las cifras se calculan **siempre desde la medición**, nunca copiadas ni
   suprimidas por lo que el arquitecto tenga escrito.
4. Si el plano tiene cuadro, el de ArchMuse **tiene sus mismas filas, en su
   orden y con su redacción literal**.
5. Si el plano tiene N cuadros, se dibujan **N**, cada uno junto al suyo.
6. Una celda que no se puede afirmar **queda vacía con su motivo escrito en el
   propio cuadro**, no sólo en la línea de comandos.
7. El cuadro lleva la marca de borrador de `C3` y **un solo `UNDO` lo quita
   entero**.

## 5. Casos de uso

**CU-A · No hay cuadro** (`V5.dxf`). ArchMuse mide, dice qué ha medido, y ofrece
dibujar su cuadro donde el arquitecto pinche. Formato canónico de ArchMuse.
*(Era el PRD del 2026-09-11 entero.)*

**CU-B · Hay cuadro y está vacío.** Se copian sus filas y se dibuja el de
ArchMuse **al lado**, relleno. El suyo se queda vacío. Sí: aunque parezca
desperdicio, **no se rellena el suyo** — la regla no tiene excepciones, y una
excepción aquí obligaría a decidir «cuándo está suficientemente vacío».

**CU-C · Hay cuadro y está relleno** (`plantasimple.dxf`, los 22 emparejados).
Igual que B. El arquitecto compara los dos mirando.

**CU-D · El plano tiene N cuadros** (`plantasimple.dxf`, N=25). N tablas, cada
una junto a la suya, emparejadas por `elegir_vivienda`. Los cuadros que no
emparejan (hoy 3, los de `PMR`/`FN`) **no reciben tabla** y se dicen por su
nombre.

**CU-E · Hay cuadro y ArchMuse no lo reconoce.** Se dibuja el canónico igual,
diciendo que no ha sabido leer el suyo y que por eso las filas son las de
ArchMuse y no las de él. **Cambio respecto del PRD del 11-sep**, que aquí no
creaba nada por miedo a duplicar: con la regla de «nunca tocar el suyo», duplicar
ya no es un riesgo, es el diseño.

**CU-F · Sin AutoCAD (vía web).** El PDF de medición ya entrega estas mismas
cifras y no cambia. Lo que sí cambia es que deja de leerse un cuadro de 25.

## 6. Casos límite

- **El punto propuesto cae encima de dibujo.** No se comprueba colisión: se
  propone el punto y **se deja mover** (`getpoint` con el propuesto por defecto).
  Comprobar colisión en un plano ajeno es un problema abierto; moverlo con el
  ratón es un gesto que el arquitecto ya hace cien veces al día.
- **25 tablas llenan el plano.** Se anuncia cuántas antes de dibujar ninguna y se
  pide **una sola** confirmación. Un `UNDO` las quita todas.
- **Una fila suya que ArchMuse no entiende** (`EXPACIOS INTERORES`, encabezados
  de grupo). Se copia **literal** y se deja sin valor. No se corrige su ortografía
  ni se omite la fila: la comparación tiene que ser fila con fila.
- **Su cuadro tiene una fila para algo que el plano no dibuja.** Cero o vacío
  según `C-4`, con el motivo al lado.
- **El plano tiene una pieza medida que su cuadro no contempla.** No se añade una
  fila —eso rompería la alineación visual, que es todo el valor— : va en una
  **nota bajo la tabla**, con su rótulo y su superficie. `C-6` se cumple.
- **Escala.** La tabla se dimensiona con el mismo criterio de unidades que ya usa
  `am:escala-de-dibujo` (mm/cm/dm/m). No es criterio nuevo: es el que ya está.
- **AutoCAD LT.** Sin COM no hay comando. Igual que hoy.

## 7. Flujo del usuario

1. El arquitecto abre su plano y teclea `ARCHMUSE`.
2. Mide (servidor) y dice qué ha encontrado: *«25 viviendas medidas, 25 cuadros
   en el plano, 22 emparejados. Voy a dibujar 22 tablas de ArchMuse al lado de
   las tuyas. Las tuyas no se tocan.»*
3. **Enseña las cifras antes de dibujar nada** y pide una confirmación.
4. Propone el punto de la primera (a la derecha de su cuadro) y deja moverlo.
5. Dibuja. Dice cuántas tablas, cuántas celdas con cifra y cuántas en blanco.
6. `UNDO` lo deshace entero.

## 8. Criterios de aceptación

- [ ] **Sobre `plantasimple.dxf`: 232 de 396 celdas con valor** (158 cifras +
      74 ceros), frente a 74 hoy. Es la cifra medida el 2026-09-12 y es el
      criterio de que el núcleo del §0 está bien hecho.
- [ ] **Los 25 cuadros se leen**, no uno. Y se dice que son 25.
- [ ] **Ninguna entidad previa cambia**: el SHA-256 del DXF de entrada es
      idéntico antes y después de una medición (el mismo test que protege la
      alineación de rótulos).
- [ ] En el DXF resultante, las celdas del `ACAD_TABLE` del arquitecto tienen
      exactamente el contenido que tenían.
- [ ] Las filas del cuadro de ArchMuse son las suyas, literales, en su orden
      —`EXPACIOS INTERORES` incluida— cuando hay cuadro.
- [ ] Sobre `V5.dxf` (sin cuadro) se dibuja el canónico y se dice que el formato
      es de ArchMuse, no suyo.
- [ ] Cada celda en blanco lleva su motivo **dentro del cuadro**.
- [ ] `C-9`: las dos vías siguen leyendo lo mismo.
- [ ] Un `UNDO` deja el plano como estaba.

## 9. Riesgos

**R-1 · Dibujar geometría nueva en el plano de un cliente, ×25.** Es el riesgo
del PRD del 11-sep multiplicado. La marca de borrador —un solo MTEXT— costó tres
intentos. Mitigación: una sola confirmación, punto movible, `UNDO` atómico, y el
`.lsp` recupera `am:dibujar-tabla`, que **ya funcionó en AutoCAD 2027**.

**R-2 · El plano se llena de tablas.** 25 cuadros suyos + 25 nuestros. Puede que
al verlo diga que quiere sólo la de la vivienda que está mirando. No se resuelve
por adelantado: se pregunta cuando lo vea.

**R-3 · El formato canónico de `CU-A` sigue siendo una elección nuestra.** Ver
§14.2.

**R-4 · Todo el `.lsp` se escribe a ciegas.** Asumido explícitamente por Pablo el
2026-09-12. Mitigación: checklist corto para el trial (§12).

**R-5 · Compite con el instalador**, que es el objetivo. Es deliberado: sin esto
el instalador entrega una herramienta que se rinde ante un proyecto terminado.

## 10. Impacto sobre módulos existentes

| Fichero | Qué le pasa |
|---|---|
| `analyzer/cuadro_superficies.py` | **El núcleo.** `CuadroSuperficies.como_plantilla()` (mismas filas, sin valores) y `detectar_cuadros_superficies(doc)` en plural. `_celda_preexistente` deja de usarse en este flujo |
| `analyzer/reparto_cuadro.py` | Las celdas apuntan a **nuestra** rejilla. `elegir_vivienda` no cambia |
| `analyzer/emparejador_cuadro.py` | **Nada.** Sigue emparejando etiqueta→campo para leer el suyo y copiar sus filas |
| `analyzer/medicion.py`, `parser.py`, los criterios | **Nada** |
| `app.py` | El endpoint devuelve la **plantilla** (filas y textos) además de los valores, y una lista de cuadros en vez de uno |
| `autocad/archmuse.lsp` | Vuelve `am:dibujar-tabla` (recuperable de `git show`), N tablas, columna de motivo, punto por defecto movible. **Se va `am:rellenar-cuadro`** |
| `tests/test_archmuse_lsp.py` | `test_no_se_inserta_ninguna_tabla_nueva` **se reescribe, no se borra**: el invariante que vigilaba («no le cambies su documento») sigue vivo y ahora se comprueba al revés — que no se escriba en su tabla |
| `analyzer/coherencia.py` | El motivo de «no comprobado» deja de mentir: dirá cuántos cuadros hay |

## 11. Plan de implementación

Tareas independientes, ninguna de más de 2 horas.

| # | Tarea | Termina cuando |
|---|---|---|
| T1 | `detectar_cuadros_superficies(doc)` en plural, y el singular como envoltura | Sobre `plantasimple` devuelve 25 y un test lo fija |
| T2 | `CuadroSuperficies.como_plantilla()` | Mismas filas, `texto_actual=None`, mismo orden |
| T3 | **El núcleo**: el reparto se calcula sobre la plantilla | **232 celdas sobre `plantasimple`**, con test |
| T4 | La rejilla propia: filas copiadas + columna de motivo + nota de piezas sin fila | El reparto devuelve una tabla dibujable, no coordenadas suyas |
| T5 | Plantilla canónica para `CU-A` | `V5.dxf` produce un cuadro completo |
| T6 | Endpoint: lista de cuadros + plantilla + punto propuesto | Contrato cerrado y probado sin AutoCAD |
| T7 | `.lsp`: recuperar `am:dibujar-tabla`, N tablas, motivos, `getpoint` | A ciegas |
| T8 | Reescribir el test del `.lsp` y el mensaje de `coherencia` | Suite en verde |

T1-T6 son servidor y se prueban enteras sin AutoCAD. T7 es el riesgo.

## 12. Plan de pruebas

**Servidor**, contra los seis planos: las cifras de `plantasimple` (232/396), que
`V5` produzca cuadro, que los cinco de referencia no cambien ni un m², `C-9`
verde, y el SHA-256 del DXF intacto.

**Checklist para el trial** (corto, como pidió Pablo, y va a
`docs/design/checklist-primera-prueba-autocad.md`):

1. ¿Aparecen **22 tablas** y ninguna encima de un cuadro suyo?
2. ¿Los cuadros del arquitecto están **exactamente** como estaban? (mirar dos al
   azar celda a celda)
3. ¿Las filas de la tabla de ArchMuse son **las suyas**, con su redacción?
4. ¿Se ve el motivo de las celdas en blanco **dentro de la tabla**?
5. ¿Un `UNDO` quita las 22?
6. ¿El punto propuesto es razonable, y se puede mover antes de dibujar?
7. Y la de `D-7`, de paso: **¿los nombres de estancia son nombres o cifras?**

## 13. Métricas de éxito

La única que vale, heredada del PRD del 11-sep: **que el arquitecto se quede la
tabla**. Si la borra, el formato está mal por bien que funcione.

La segunda, medible aquí: **cifras reales entregadas por plano**. Hoy, sobre
`plantasimple`, es 1. El objetivo es 158.

## 14. Motivos para NO implementarlo

### 14.1 El argumento honesto en contra

**Puede que el arquitecto no quiera 25 tablas en su plano.** Ha pedido que
ArchMuse entregue siempre lo suyo, y eso es inequívoco; lo que no ha visto es el
plano con 25 tablas más. La respuesta razonable si eso pasa no invalida este PRD
—el cálculo y el cuadro siguen siendo los buenos— pero sí cambiaría el flujo:
dibujar sólo la de la vivienda que esté mirando.

**No lo bloqueo por eso** porque el coste de equivocarse es un `UNDO`, y porque
la alternativa —esperar a preguntárselo— es el error que ya se cometió en el PRD
del 11-sep: se esperó un dato y el resultado fue no entregar nada durante un día.

### 14.2 La objeción del 11-sep, y por qué el diseño nuevo la disuelve

Aquel PRD se frenó en parte porque **no existe «el formato del estudio»**: sus
tres cuadros tienen 17, 18 y 18 campos y escriben la misma fila de tres maneras.
Copiar uno era elegir por él.

**Con este diseño esa decisión desaparece en los casos B, C y D**: no se elige
formato, se **copia el que tiene delante**, literal. Sobrevive sólo en `CU-A`
—cuando no hay ninguno— y ahí se resuelve declarándolo: la tabla dice
**«ArchMuse · BORRADOR»** y usa `CAMPOS_DEL_CUADRO`, que es **el formato de
ArchMuse**, no una imitación del suyo. No se le atribuye a él un formato que no
ha elegido, y por eso deja de ser una decisión tomada en su nombre.

### 14.3 Lo que este PRD NO hace, y podría tentar

- **No compara.** ArchMuse pone su cifra al lado de la suya y calla. Sería fácil
  añadir «él dice 23,85, yo mido 23,83» y **no se hace**: comparar es del
  arquitecto (orden de Pablo, 2026-09-12), y un delta automático es el PRD del
  2026-08-22, que sigue en su gate.
- **No rellena el suyo aunque esté vacío.** Ver `CU-B`.
- **No añade filas** para piezas que su cuadro no contempla. Van en nota.

---

**Decisión:** aprobado por Pablo el 2026-09-12. Ejecución en curso.
