# PRD — Revisión de coherencia del plano antes de entregarlo

**Estado:** Borrador · **Fecha:** 2026-08-19 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

> **Lo primero, porque es lo que sostiene todo el documento.** Los siete
> hallazgos de la §1.2 **no son hipotéticos**: salen de ejecutar el código que
> ya existe sobre `v2s.dxf`, el plano real del cliente, hoy. No hay ni una cifra
> estimada en este PRD.

---

## 1. Problema que resuelve

### 1.1 El trabajo humano que se está pagando

Antes de que un plano salga del estudio —al colegio, al cliente, al aparejador,
al siguiente miembro del equipo— alguien lo repasa. Comprueba que el cuadro de
superficies y el dibujo hablan del mismo piso, que no hay recintos pisándose,
que ninguna pieza se ha quedado sin rotular, que lo que la tabla enumera existe
dibujado. Se hace **a ojo**, y se rehace **entera en cada revisión del plano**,
porque mover un tabique invalida el repaso anterior.

Es media hora larga por plano y revisión, en el peor momento posible: con la
entrega encima. Y es un repaso que falla de la peor manera — **en silencio**.
Nadie se entera de que dos recintos se solapan hasta que las superficies no
cuadran, y para entonces el plano ya está fuera.

### 1.2 Lo que ArchMuse ya sabe y tira a la basura

Aquí está el hallazgo que motiva este PRD. Ejecutando el código **de hoy**,
sin escribir nada nuevo, sobre `v2s.dxf`:

| # | Hallazgo real, medido | Qué hace ArchMuse hoy con él |
|---|---|---|
| 1 | `Tendedero` y `Tendedero` se solapan **4,00 m² (95 % de la pieza menor)** | Se usa para negarse a medir. El arquitecto ve «no se puede medir», no ve **por qué** |
| 2 | `Terraza` y `Tendedero` se solapan **3,08 m² (93 %)** | Igual |
| 3 | Polilínea `A61724`: el flag `closed` está mal puesto | **Una línea de `_log.warning`.** El propio código dice que «tiene que quedar visible para quien audite», y va a un terminal que nadie lee |
| 4 | Polilínea `A6188E`: flag `closed` mal puesto, **hueco de 2,95 cm** | Igual. Un hueco de 3 cm cerrado por el parser es una superficie que se está calculando sobre una suposición |
| 5 | La etiqueta `Tendedero` está **dos veces** (4,22 y 8,63 m²) y el cuadro sólo tiene un hueco | Se convierte en una celda `BLOQUEADO` con su motivo. Mejor que adivinar, pero el arquitecto no sabe que el problema es que rotuló dos piezas igual |
| 6 | El cuadro pide `pasillo`, `terraza_2` y `vestibulo`: **ninguna pieza dibujada lleva esos nombres** | **Nadie lo calcula.** No existe |
| 7 | El plano dibuja 9 piezas; el cuadro nombra 11 | **Nadie lo calcula.** No existe |

Siete hallazgos. Ninguno necesita una línea de corpus normativo — son geometría
y texto del propio fichero, contrastados entre sí. **Cinco ya se calculan y se
desperdician; dos no cuesta nada calcularlos.** El producto está tirando su
mejor entregable disponible porque lo usa como insumo interno en vez de como
resultado.

### 1.3 Por qué esta y no otra

`docs/design/2026-08-19-valor-comercial-de-las-skills.md` dejó dos candidatas
esperando una medición (carpintería) o una firma colegiada (normativa). Esta no
espera a nadie: el dato está, se ha medido, y el entregable no afirma nada sobre
normativa.

---

## 2. Usuario afectado

**El arquitecto que va a entregar un plano**, y muy especialmente el que trabaja
sobre un DXF que no dibujó él: un colaborador, un plano heredado de otra fase,
el archivo que devuelve el delineante. Ahí el repaso no es una formalidad —es la
única forma de saber qué le están dando— y es donde más horas se van.

Usuario secundario real: **el propio ArchMuse**. Los siete hallazgos explican
por qué `SK-1` deja celdas en blanco. Hoy el arquitecto recibe el efecto y no la
causa.

---

## 3. Objetivo de negocio

1. **Un entregable vendible que no depende del corpus.** Es el único del
   catálogo con esa propiedad, y por tanto lo único que ArchMuse puede cobrar
   antes de que un colegiado firme la primera regla. `C5` mantiene el corpus en
   el camino crítico; esto no lo sustituye, lo financia.
2. **Convierte la desconfianza en argumento de venta.** `DESTROY_ARCHMUSE.md`
   dice que el ataque nº1 es la alucinación normativa. Este entregable **no
   afirma nada sobre normativa**: dice «estas dos piezas se solapan 4,00 m²» y
   lo puedes comprobar en tres clics. Es la demostración más barata de que el
   producto mide en vez de opinar.
3. **Explica `SK-1` sin ampliarlo.** Sube el valor percibido del vertical que ya
   existe en vez de abrir uno nuevo.

---

## 4. Objetivo técnico

- Dado un DXF, ArchMuse produce una lista de hallazgos donde **cada uno nombra
  la entidad concreta** —etiqueta, superficie, `handle` del DXF— para que un
  tercero pueda ir a verlo. Un hallazgo que no se puede ir a comprobar no se
  emite.
- **No se gradúa la gravedad.** Ningún hallazgo se marca «crítico» ni «leve»:
  se dice qué es y cuánto mide. Ver §9 R-1; es la decisión de diseño que hace
  que esto no esté bloqueado por `D-7`.
- **Cero normativa.** Ninguna comprobación usa un umbral de ninguna norma. La
  única tolerancia es `ROOM_OVERLAP_TOLERANCE_M2 = 0,05`, que ya existe y está
  documentada como ruido de dibujo.
- **Lectura pura.** No escribe en el DXF del arquitecto ni en ningún sitio salvo
  el informe que se le pide explícitamente.
- Un plano sin ningún problema produce **un informe que lo dice**, no un informe
  vacío.

---

## 5. Casos de uso

**CU-1 · «Voy a entregar esto, repásamelo.»** El caso central. DXF dentro,
informe fuera, con los hallazgos y la lista de lo que sí se ha mirado.

**CU-2 · «Me han pasado este DXF, ¿qué me están dando?»** El de más valor por
hora ahorrada, y el que `docs/prd/2026-08-02-ingesta-de-dxf-ajenos.md` ya
identificó como el punto ciego del producto.

**CU-3 · «¿Por qué `SK-1` me ha dejado esta celda en blanco?»** El informe
contesta con la causa —dos piezas rotuladas igual, un solape— en vez de con el
efecto.

**CU-4 · El plano está bien.** Sale un informe que enumera **qué se ha
comprobado** y dice que no se ha encontrado nada. Un informe vacío se lee como
«no ha funcionado».

---

## 6. Casos límite

| Caso | Qué tiene que pasar |
|---|---|
| El DXF no trae cuadro de superficies | Los hallazgos de geometría se emiten igual; los de contraste cuadro↔dibujo salen como **no comprobados, con motivo**. Nunca ausentes |
| La unidad del dibujo no se puede deducir | Se para y se pregunta, **antes de medir nada**. Mismo criterio que `SK-1`: un plano en milímetros leído como metros da solapes de 4.000.000 m² |
| No se puede determinar la capa de recintos | Igual: se pregunta, no se adivina |
| Cero recintos leídos | No es un informe vacío: es un hallazgo («no se ha leído ninguna pieza en la capa X»), que casi siempre significa capa equivocada |
| Recintos sin etiqueta | Hallazgo propio. Sin rótulo no hay contraste posible con el cuadro, y hay que decirlo |
| Una pieza contenida entera dentro de otra (100 % de solape) | Se emite igual. Es la firma del contorno agrupador colado como habitación, y el `overlap_pct_menor` lo delata |
| Dos piezas que comparten borde | **No es un solape.** La tolerancia existe para esto |
| El cuadro pide una pieza que no está dibujada | Se dice como **discrepancia a revisar**, no como defecto: un pasillo puede no dibujarse como recinto propio, y llamarlo error sería inventar criterio |
| Un plano con varias viviendas | Fuera de alcance de la v1, declarado en `limitaciones`. Mismo límite que `SK-1` |

---

## 7. Flujo del usuario

1. `python scripts/revisar_plano.py mi_plano.dxf`. Sin clave de API y sin red.
2. Si la unidad o la capa no se pueden deducir, **para y pregunta**. Nada se ha
   medido y nada se ha escrito.
3. Enseña el recuento por tipo de hallazgo y la lista, cada uno con su entidad.
4. Escribe el informe en PDF junto al plano, marcado como borrador, con el
   sha256 del DXF de origen impreso dentro y el acta de procedencia.
5. Termina diciendo **qué se ha comprobado y qué no**, derivado de los
   manifiestos, no redactado a mano.

---

## 8. Criterios de aceptación

1. Sobre `v2s.dxf`, el informe contiene **los siete hallazgos de la §1.2**, cada
   uno con su magnitud y su entidad. Es el test que define «hecho».
2. El DXF de entrada conserva su sha256, verificado antes y después.
3. Ningún hallazgo lleva grado de gravedad. Un test lo comprueba sobre el
   vocabulario de salida.
4. Ninguna comprobación consulta el corpus normativo: comprobado porque la Skill
   **no declara ninguna capacidad de normativa** y el registro lo hace cumplir.
5. Sin unidad determinable, la salida es la pregunta y **no se ha medido nada**.
6. Un plano limpio produce un informe que enumera lo comprobado y declara que no
   se ha encontrado nada.
7. Cada hallazgo permite localizar su entidad: etiqueta, superficie o `handle`.
8. El informe sale `borrador=True` con su sello sha256.
9. Los avisos que hoy van a `_log.warning` llegan al informe. Un test captura el
   log y comprueba que ninguno se pierde por el camino.
10. La Skill declara sus limitaciones, y ninguna es normativa.

---

## 9. Riesgos

**R-1 · Emitir criterio profesional sin querer.** El riesgo real de este PRD.
Decir «esto es un error grave» es criterio de arquitecto, y `D-7` está sin
firmar. *Mitigación, y es la decisión de diseño central:* **no se gradúa nada**.
Se mide y se nombra. «Se solapan 4,00 m²» es un hecho; «esto es grave» es una
opinión. Con esa frontera, la Skill cumple lo que `agente/skills/__init__.py`
exige a las tres existentes y **no queda bloqueada por `D-7`**.

**R-2 · Falsos positivos.** `DESTROY_ARCHMUSE.md` §5.1: un hallazgo falso
destruye la confianza en los verdaderos. *Mitigación:* toda comprobación es
geométrica y exacta, con la única tolerancia ya calibrada contra planos reales;
y las dos comprobaciones nuevas (§1.2 nº6 y nº7) se emiten explícitamente como
«discrepancia a revisar», no como defecto.

**R-3 · Se lee como una revisión de proyecto.** Un arquitecto podría creer que
un informe limpio significa que el plano cumple. *Mitigación:* la limitación
—«esto no comprueba normativa: dice si el plano es coherente consigo mismo»— va
en el manifiesto, en la primera página del informe y en el acta.

**R-4 · Compite con `NOR-2`.** Sí, y hay que decirlo. La defensa es la misma:
transcribir normativa no lo hace un programador. Estimación ~1 jornada.

**R-5 · No toca `REFACTOR_MASTERPLAN.md`.** Añade ficheros; no modifica
`analyzer/parser.py`, ni `evaluator.py`, ni `app.py`, ni el frontend.

---

## 10. Impacto sobre módulos existentes

**Ficheros nuevos, y sólo nuevos:** `analyzer/coherencia.py` (la auditoría),
`agente/herramientas/coherencia.py` (una capacidad), `agente/skills/coherencia.py`
(el procedimiento), `analyzer/coherencia_pdf.py` (el informe),
`scripts/revisar_plano.py`, y sus tests.

**Cero modificaciones al runtime de `agente/`.** El registro de capacidades y el
de Skills funcionan **por descubrimiento**: basta dejar un fichero que exponga
`CAPACIDADES` o `SKILLS`. Ni `registro.py`, ni `nucleo.py`, ni `ejecucion.py`,
ni ningún `__init__.py` se tocan. Verificado leyendo `agente/registro.py`.

**Se consume sin modificar:** `analyzer/parser.py` (`leer_plano`,
`geometria_no_leida`), `analyzer/evaluator.py` (`evaluate_room_overlap`,
`group_rooms_by_*`), `analyzer/cuadro_superficies.py`
(`detectar_cuadro_superficies`), `agente/skills/_comun.py`.

**Techo de C4:** el registro pasa de 9 a **10** capacidades. Dentro del límite
de 8-12, y la nueva es gruesa (una capacidad, una auditoría completa), no tres
finas.

**A vigilar:** los avisos del parser viajan por `logging`. Capturarlos exige un
manejador propio durante la lectura, y hacerlo mal se llevaría por delante la
configuración de log del proceso anfitrión. Se aísla y se restaura siempre.

---

## 11. Plan de implementación dividido en pequeñas tareas

| # | Tarea | ~ | Depende |
|---|---|---|---|
| **CO-1** | `analyzer/coherencia.py`: el tipo `Hallazgo` (tipo, descripción, entidad, magnitud — **sin gravedad**) y la captura aislada de los avisos del parser. | 1,5h | — |
| **CO-2** | Las comprobaciones que reutilizan lo existente: solapes, geometría descartada, etiquetas duplicadas, recintos sin rótulo. | 1,5h | CO-1 |
| **CO-3** | Las dos nuevas: piezas del cuadro sin dibujar, y piezas dibujadas que el cuadro no contempla. Emitidas como discrepancia, no como defecto. | 1,5h | CO-2 |
| **CO-4** | La capacidad `plano.coherencia`, sin efectos (sólo lee). Golden incluido, como exige `TL-4`. | 1,5h | CO-3 |
| **CO-5** | La Skill `revision.coherencia_del_plano`: procedimiento, `produce`, y verificaciones (nada sin entidad localizable; ninguna gravedad; el original intacto). | 2h | CO-4 |
| **CO-6** | El informe en PDF: recuento, hallazgos con su entidad, qué se ha comprobado, marca de borrador y sha256 del origen. | 2h | CO-5 |
| **CO-7** | `scripts/revisar_plano.py`, sin clave de API y sin red. | 1h | CO-6 |
| **CO-8** | Los diez criterios de aceptación como tests, incluido el de los siete hallazgos sobre `v2s.dxf`. | 2h | CO-7 |

Total ~13h. **CO-1 a CO-4 ya tienen valor sueltas:** la capacidad se puede
invocar desde la línea de órdenes, desde MCP o desde un plugin sin la Skill.

## 12. Plan de pruebas

- **Unitarias sobre `analyzer/coherencia.py`** con planos sintéticos: dos
  polígonos que se solapan, dos que comparten borde (no es solape), una etiqueta
  repetida, un recinto sin rótulo. Ahí vive la lógica y ahí se prueba, sin
  ficheros grandes.
- **El test que define «hecho»:** los siete hallazgos de la §1.2 sobre
  `v2s.dxf`, con sus magnitudes. Se salta con motivo sin `ARCHMUSE_DXF_V2S`,
  mismo criterio que el resto de la suite.
- **De política:** ninguna cadena del vocabulario de salida contiene grado de
  gravedad; la Skill no declara ninguna capacidad de normativa.
- **De no regresión:** suite completa verde con el plano real. Como todo son
  ficheros nuevos, una regresión aquí significaría que el descubrimiento de
  capacidades ha roto algo, que es justo lo que hay que saber.
- **Sin red y sin clave** en todas.

## 13. Métricas para medir el éxito

1. **Hallazgos por plano, y cuántos el arquitecto reconoce como reales.** La
   métrica que importa. Si la segunda cifra baja, hay falsos positivos y se
   para (R-2).
2. **Planos revisados por proyecto.** Si es 1, se usa como curiosidad; si sube,
   ha entrado en el flujo de trabajo, que es donde está el negocio.
3. **Cuántos hallazgos existían ya y nadie había visto.** Se mide preguntando en
   los primeros diez planos. Es la cifra que convierte esto en venta.
4. **Cero informes emitidos sobre un plano cuya unidad no se pudo determinar.**
   No es métrica de éxito: es la condición para que las otras tres signifiquen
   algo.

## 14. Posibles motivos para NO implementar la idea

**1. No es lo que ArchMuse dice ser.** La visión es un asesor arquitectónico con
corpus normativo; esto es un **linter de DXF**. Es un producto más pequeño y
menos defendible que el del `NORTH_STAR_2031.md`, y hay un riesgo real de que
funcione lo bastante bien como para distraer del corpus durante meses. *Mi
respuesta:* es un entregable de una jornada que no consume la única cola que
importa —la del colegiado—, y que puede financiar esa contratación. Pero el
riesgo de distracción es real y conviene ponerle fecha de revisión.

**2. El foso es débil.** Detectar solapes de polígonos lo hace cualquiera con
Shapely en una tarde. Lo que no es trivial es el resto: leer un DXF ajeno sin
suponer la unidad ni la capa, atravesar bloques, no adivinar ante la ambigüedad
y trazar cada número. Eso son meses de trabajo ya hechos. Aun así, **el foso de
esta Skill concreta es de ejecución, no estructural**, y hay que decirlo.

**3. La muestra sigue siendo de uno.** Siete hallazgos en un plano es una señal
excelente, pero es **un** plano — y encima uno con problemas conocidos. Cabe que
un plano bien dibujado no dé ninguno y el informe se lea como un producto que no
hace nada. *Mitigación parcial:* el CU-4 exige que un informe limpio enumere lo
comprobado. *Mitigación real:* medir el segundo plano, que es la misma tarea
pendiente de `OP-13` y sirve para las dos cosas.

**4. La alternativa aburrida, otra vez.** `NOR-2`. Si hubiera colegiado
contratado, mi recomendación sería aplazar esto.

**Recomendación como CTO:** **hacerlo.** Es la única candidata que cumple los
cuatro criterios del encargo —ahorra horas reales, entregable tangible,
verificable, independiente del corpus— y la única que se ha podido **medir**
sobre trabajo real antes de escribir una línea. Con dos condiciones: que no
gradúe gravedad (§9 R-1), y que se revise contra un segundo plano antes de
cobrar por ello.

---

**Decisión:** _pendiente de revisión por Pablo_
