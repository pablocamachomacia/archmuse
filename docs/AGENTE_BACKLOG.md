# AGENTE_BACKLOG — fuente de verdad del desarrollo de ArchMuse

**Fecha:** 2026-08-19 · **Estado:** propuesta, pendiente de aprobación de Pablo · **Sustituye a:** nada; *coordina* `docs/design/2026-08-18-plan-de-migracion.md` (que fija el orden del vertical) y `docs/design/2026-08-18-auditoria-arquitectura-tecnologica.md` (que fija el stack).

Este documento existe para responder una sola pregunta, siempre igual: **¿cuál es la siguiente tarea que hay que hacer?** No es un catálogo de ideas ni un inventario de deseos. Está ordenado por **valor de producto y dependencia**, no por comodidad técnica ni por lo que resulta agradable programar.

Dos advertencias antes de entrar, y las dos son incómodas:

1. **El corpus normativo sigue vacío.** `normativa/es/` tiene una regla piloto y el motor tiene 3.777 líneas esperando contenido. Ninguna tarea de este backlog lo arregla salvo `NOR-1` y `NOR-2`, y ninguna otra lo sustituye. Un producto impecable con el corpus vacío sigue siendo un producto que **no puede verificar normativa**.
2. **La mitad de este documento es lo que NO se hace.** Las secciones §2 y §12 son tan importantes como las tareas. Un backlog sin rechazos explícitos se convierte en una lista de deseos en tres semanas.

---

## 0. Cómo se usa este documento

### 0.1 El bucle de trabajo autónomo

```
1. Buscar la primera tarea PENDIENTE cuyas dependencias estén todas HECHO.
2. ¿Su cabecera dice «PRD: sí»?
     sí  → ¿existe el PRD aprobado en docs/prd/?
             no  → escribir SOLO el PRD y parar. No se toca código de producto.
             sí  → seguir.
     no  → seguir.
3. Implementar la tarea completa. Nada de «ya que estamos».
4. Ejecutar los tests afectados, y la suite completa si toca fichero compartido.
5. Verificar el criterio de «Terminado cuando» literalmente, no por aproximación.
6. Marcar HECHO con la fecha en la cabecera de la tarea. No hacer commit salvo orden expresa.
7. Volver al paso 1.
```

**Si una tarea resulta estar bloqueada por una decisión de producto:** marcarla `BLOQUEADO`, anotar en `docs/design/decisiones-pendientes.md` cuál, y **seguir con la siguiente desbloqueada**. Nunca esperar.

**Si una tarea resulta ser más grande de una jornada:** partirla aquí antes de empezarla, no durante.

### 0.2 Estados y prioridades

| Marca | Significado |
|---|---|
| `PENDIENTE` | Nadie la ha empezado |
| `EN CURSO` | Alguien la tiene abierta |
| `HECHO (AAAA-MM-DD)` | Su criterio de terminado se ha verificado |
| `BLOQUEADO (motivo)` | No se puede avanzar sin una decisión o un tercero |
| `PARCIAL` | Existe el código, falta el criterio de terminado |

| Prioridad | Significado |
|---|---|
| `P0` | Está en el camino crítico del primer vertical vendible. Nada la adelanta |
| `P1` | Hace falta para cobrar, o cierra un riesgo legal/de seguridad |
| `P2` | Ensancha el producto una vez el vertical esté en pie |
| `P3` | Real, justificado, y deliberadamente tarde |
| `APLAZADO` | Decidido que no ahora, con motivo escrito |

### 0.3 Lo que ya existe (base de partida, medida el 2026-08-19)

| Pieza | Estado real |
|---|---|
| `agente/` (2.900 líneas + 2.000 de test) | Bucle propio, 4 capacidades, 3 Skills, memoria, ejecutor con reanudación, acta, verificación. **Funciona, y no está enchufado a ningún producto** |
| `modelo/` (2.199) | Grafo con procedencia epistémica. Portante solo dentro de `agente/` |
| `normativa/` (3.777) | Motor completo · **una** regla real transcrita |
| `analyzer/` (22.031) | El producto de hoy: DXF → análisis → 38 reglas. Camino viejo, intacto |
| `bim/` (264) | Lectura de IFC, con ida y vuelta probada |
| `tests/` (24.584 + agente) | 494 verdes. Mayor que el producto. El activo principal |
| Autenticación, Postgres, cola, despliegue | **No existen** |

---

## 1. Objetivos de producto

Un objetivo de producto es **una frase que un arquitecto puede escribir y un resultado que puede usar en su trabajo**. Si no se puede formular así, no es un objetivo: es una funcionalidad buscando justificación.

Cada objetivo lleva un veredicto. **No todos entran en el MVP, y decirlo es la mitad del trabajo de este documento.**

### OP-1 · «Rellena el cuadro de superficies de este DXF y dime qué no has podido calcular» — **MVP**

- **Devuelve:** el DXF del arquitecto relleno (su original intacto, byte a byte), el cuadro en PDF, y el acta que dice celda a celda de qué entidad salió cada número y por qué las demás quedaron `N/D`.
- **Por qué éste primero:** es el único entregable grande que **no depende del corpus vacío**, se apoya en código ya probado contra un plano real de cliente, devuelve un fichero de trabajo en vez de una pantalla, y ejercita el ciclo agéntico completo. La elección viene del plan de migración §2 y no se reabre.
- **Tareas:** `TL-1`, `TL-9`, `TL-2`, `SK-1`, `AG-1`, `AG-2`, `AG-4`, `AG-5`, `AG-6`, `DOC-1`, `DOC-2`, `DOC-3`, `ME-2`, `SK-4`, `INF-2`, `INF-3`, `INF-5`, `INF-7`.

### OP-2 · «Guarda lo que ha pedido el cliente, y avísame cuando algo lo contradiga» — **MVP (barato y diferencial)**

- **Devuelve:** los requisitos del proyecto declarados con quién los dijo y cuándo, los conflictos entre versiones sin resolver en silencio, y la advertencia cuando una decisión posterior los contradice.
- **Por qué está en el MVP pese a ser pequeño:** el sustrato ya existe (`agente/memoria.py`, `agente/skills/programa.py`), no necesita corpus, no necesita LLM para ser correcto, y es lo que convierte «cancelar la suscripción» en «desmontar un proceso». Es retención, que es lo que `MOAT_ANALYSIS.md` dice que falta.
- **Tareas:** `ME-1`, `ME-3`, `ME-4`, `SK-3`.

### OP-3 · «¿Qué normativa se le aplica a esta parcela y qué exige?» — **MVP degradado, honesto**

- **Devuelve:** el ámbito territorial resuelto (estatal + autonómico + municipal), las reglas aplicables con su cita literal al BOE, y **la lista explícita de lo que no hay en el corpus**.
- **El veredicto incómodo:** hoy esto responde con una regla. Entra en el MVP **solo** si la respuesta declara su propia cobertura; si no la declara, es peor que no tenerlo, porque un arquitecto asume que el silencio significa «cumple».
- **Tareas:** `NOR-1`, `NOR-2`, `NOR-3`, `NOR-5`, `NOR-6`, `SK-2`, `TL-8`.

### OP-4 · «Revisa esta planta contra el CTE y dame los hallazgos» — **V2**

- **Devuelve:** los incumplimientos con su regla, su umbral, su cita y su acta; y los que no ha podido evaluar, con el motivo.
- **Por qué no en el MVP:** exige desatar `evaluator.classify_problems` (382 líneas de `if/elif`) y envolver 38 reglas, y exige corpus. Son ~7 jornadas de refactor que no acercan ni un día el primer entregable. Es el **segundo** vertical, y su primera tarea (`TL-5`) es la que más riesgo tiene de no hacerse nunca.
- **Tareas:** `TL-5`, `TL-6`, `SK-2`, `SK-6`, `NOR-2`, `NOR-4`, `NOR-7`, `AG-8`.

### OP-5 · «Analiza este modelo BIM y contrástalo con lo que me han dicho» — **V2**

- **Devuelve:** el inventario de espacios, superficies y plantas del IFC, y las discrepancias contra lo declarado por el cliente y contra el DXF.
- **El veredicto:** la lectura ya funciona (`bim/lector_ifc.py`). Lo que falta no es leer IFC: es **tener con qué contrastarlo**, y eso es el grafo portante y el corpus. Adelantarlo produce un visor de propiedades, que ya tienen todos.
- **Tareas:** `BIM-1`, `BIM-2`, `BIM-3`, `BIM-4`.

### OP-6 · «Genera la memoria justificativa del cumplimiento del CTE» — **APLAZADO, y es el que más se va a pedir**

- **Devuelve:** el documento redactado con las cifras del proyecto y los artículos aplicables.
- **Por qué se aplaza pese a la demanda:** es el entregable con **peor relación valor/riesgo del catálogo** mientras el corpus esté vacío. Una memoria justificativa mal citada no es un bug: es responsabilidad civil del arquitecto que la firma. Y es el artefacto más cercano a la autoría, o sea el que más tensiona C3. Se hace **después** del corpus, no antes, y con el acta pegada.
- **Tareas:** `DOC-5`, y no empieza sin `NOR-2` cerrada.

### OP-7 · «Prepara la documentación de entrega» — **V2**

- **Devuelve:** el paquete de planos, cuadros y fichas coherentes entre sí y sellados juntos.
- **El veredicto:** los exportadores ya existen (`dossier_pdf`, `pdf_report`, `dxf_export`, `ifc_export`). Lo que no existe es la **coherencia sellada** entre ellos, que es lo único que aporta valor sobre exportar a mano. Sin `ME-2` esto es un botón de «descargar todo».
- **Tareas:** `DOC-2`, `DOC-5`, `ME-2`, `INF-3`.

### OP-8 · «Modifica el proyecto: cambia esto y recalcula lo que dependa» — **V2**

- **Devuelve:** el fichero modificado, la lista de lo que cambió como consecuencia, y el original intacto.
- **Por qué no en el MVP:** escribir en el fichero de un cliente es el efecto más caro de equivocarse del producto. El patrón `io` (`TL-2`) tiene que llevar meses funcionando en un solo tipo de escritura antes de generalizarlo.
- **Tareas:** `TL-2`, `SEG-1`, `CAD-2`.

### OP-9 · «Trabaja desde mi Revit / mi AutoCAD, sin salir» — **APLAZADO (V3), pero se prepara desde hoy**

- **Devuelve:** las mismas capacidades invocadas desde el entorno donde el arquitecto ya está.
- **El veredicto:** es donde el producto se gana la distribución, y por eso **la arquitectura no puede impedirlo** — pero construir un plugin antes de tener capacidades que merezcan invocarse es hacer el envoltorio de un regalo vacío. Lo que sí se hace ahora es la **prueba** de que se podrá (`CAD-1`), que cuesta media jornada.
- **Tareas:** `CAD-1` (HECHO el 2026-08-19: `python -m agente.invocar`), `CAD-2`, `CAD-3` (aplazadas), y `TL-7` (servidor MCP), que es la misma idea por otra puerta: ArchMuse dentro de Claude Desktop o del editor del arquitecto, con el mismo manifiesto y sin exponer capacidades `io` sin confirmación.

### OP-10 · «Resume estos correos y saca de ahí los requisitos» — **RECORTADO, no rechazado**

- **Devuelve:** *solo* requisitos de proyecto extraídos de un texto pegado, cada uno como una declaración con su fuente, para que el arquitecto los apruebe uno a uno.
- **El veredicto de CTO, sin adornos:** un resumidor de correos genérico **no tiene foso ninguno** — lo hace mejor y gratis el cliente de correo del arquitecto. Lo que sí tiene valor es la **puerta de entrada a la memoria de proyecto** (OP-2): convertir prosa en requisitos trazables. Se implementa como eso y nada más. Integración con bandejas de correo: **no**.
- **Tareas:** `SK-3`, `ME-3`.

### OP-11 · «Ayúdame a decidir esto del diseño» — **REVERTIDO el 2026-08-19 por el informe ejecutivo de Pablo**

- **El veredicto:** `MOAT_ANALYSIS.md` y `DESTROY_ARCHMUSE.md` coinciden en que la generación de plantas y el asesoramiento de diseño demuestran bien y **no venden**; son también lo más caro por token y lo que más tensiona la frontera de autoría. El generador actual se **congela**: no recibe trabajo, no se amplía, no se borra.
- **ACOTADA el 2026-08-19 por la correccion del §8 de `ARCHMUSE_SPEC.md`.** La reversion no es un cheque en blanco: la generacion de alternativas queda **permitida cuando la geometria se deriva de parametros comprobables** —envolvente y volumen edificable a partir de retranqueos, ocupacion, edificabilidad y alturas—, y cada alternativa lleva la procedencia de los parametros que la producen. **Sigue fuera la distribucion interior libre:** repartir estancias dentro de una planta segun criterio propio no se deriva de nada comprobable. Eso deja `analyzer/ai_generator.py` —donde el modelo coloca las estancias— **fuera de alcance**; no se ha borrado ni congelado, y que hacer con el es una decision de Pablo. Lo que si esta construido y dentro de la redaccion es `CP-5`: `analyzer/alternativas.py`, aritmetica pura sobre los parametros del arquitecto, sin una sola llamada al modelo.
- **LA REVERSIÓN, y conviene que quede escrita entera.** El informe ejecutivo de Pablo del 2026-08-19 pone la **generación de alternativas en el centro del MVP**: «parcela → restricciones → programa → generación de alternativas → evaluación → comparación → modificación → exportación». Eso contradice de frente el veredicto de arriba, que congelaba el generador citando que «demuestra bien y no vende» y que es lo que más tensiona la frontera de autoría.
- **Es una decisión de Pablo y se ejecuta**, pero con dos condiciones escritas para que la reversión no se pierda: (1) el veredicto anterior **no se borra** —sigue arriba, con sus motivos—, y (2) **la prueba del §7 del informe es el juez**: darle ArchMuse a un arquitecto sin explicarle nada y ver si dice «esto me ahorraría trabajo». Si a las 24 h dice «está muy chulo pero no lo usaría», el veredicto congelado era el correcto y se vuelve a él sin discutir. El propio informe lo dice: «no añadas tecnología; cambia el producto».
- **Tareas:** `CP-1` a `CP-7` (`docs/prd/2026-08-19-copiloto-que-modifica-el-proyecto.md`).

### OP-12 · «Acuérdate de todo esto dentro de ocho meses» — **transversal, no es una funcionalidad**

- **Devuelve:** el proyecto entero reconstruible dos años después: qué se dijo, con qué dato, con qué regla en qué versión, y quién lo decidió.
- **El veredicto:** esto no es un objetivo que se implemente; es una **propiedad** que las tareas `ME-2`, `SEG-5` y `NOR-4` o bien conservan o bien destruyen. Está aquí para que se pueda comprobar que ninguna tarea la rompe.
- **Tareas:** `ME-2`, `SEG-5`, `NOR-4`. *(La retención y la purga son criterio de `ME-2`, no tarea aparte.)*

### OP-15 · «Repásame este plano antes de que lo entregue» — **HECHO (2026-08-19)**

- **Devuelve:** el informe de qué no cuadra en el plano, con la entidad concreta de cada hallazgo —rótulo, superficie, `handle` del DXF— y su magnitud.
- **Por qué es el primero que se ha podido hacer entero:** es **el único objetivo del catálogo que no depende del corpus normativo**. Todo lo que comprueba es geometría y texto del propio fichero contrastados entre sí, así que su valor no espera a ninguna firma colegiada. Y ahorra un trabajo real: el repaso previo a la entrega se hace hoy a ojo y se rehace entero en cada revisión del plano, porque mover un tabique invalida el anterior.
- **El hallazgo que lo motivó:** casi todo esto ya se calculaba **y se tiraba**. Los solapes servían para negarse a medir —el arquitecto veía el efecto, nunca la causa—; los avisos de polilínea mal cerrada iban a `_log.warning`, o sea a un terminal que nadie lee, pese a que el propio parser documenta que «tiene que quedar visible para quien audite»; y la etiqueta repetida acababa en una celda `BLOQUEADO`. Sobre `v2s.dxf` eso son **nueve hallazgos reales** que el producto ya sabía y no decía.
- **Lo que lo mantiene fuera de `D-7`:** **no gradúa la gravedad de nada.** «Se solapan 4,00 m²» es un hecho comprobable; «esto es grave» es criterio profesional, y el de ArchMuse está sin firmar. La frontera es la verificación bloqueante `ningun_hallazgo_lleva_gravedad`, con su test de que **falla de verdad**.
- **Entregable demostrable:** `python scripts/revisar_plano.py mi_plano.dxf` — enseña el procedimiento, revisa, escribe el informe en PDF, imprime el acta y no toca el DXF (sha256 verificado antes y después). Sin clave de API y sin red. **Desde el 2026-08-20 (Bloque 1), también desde la web:** `/` → tarjeta "Revisar coherencia" o pregunta libre → `/api/preguntar` → `revision.coherencia_del_plano` de verdad, con `SEG-1`. Hasta ese bloque esta Skill estaba `HECHO` y probada pero sin ninguna puerta HTTP -- sólo se podía llegar a ella desde un test o la línea de órdenes.
- **Tareas:** `CO-1` a `CO-8` (todas hechas). PRD: `docs/prd/2026-08-19-revision-de-coherencia-del-plano.md`.

### OP-16 · «Mídeme esta planta y dime lo que mide cada vivienda» — **HECHO (2026-08-19)**

- **Devuelve:** la medición de superficies útiles de **todas** las viviendas de una planta, pieza a pieza, con la procedencia de cada cifra —qué recinto, con qué rótulo, en qué capa del DXF—, los subtotales interior y exterior, y el total de cada vivienda **sólo cuando se puede afirmar**.
- **Por qué éste, y se eligió midiendo y no opinando:** `OP-1` promete un cuadro relleno y **se negaba a empezar en cuanto el DXF tenía más de una vivienda**. Ejecutado sobre el segundo plano real del cliente (`V5.dxf`), ArchMuse no entregaba nada: «esta función de momento solo admite un DXF con una única vivienda detectada; tiene 3». Y ese plano no tiene ningún defecto — es **una planta normal de un edificio residencial**, con tres viviendas (`VT1/3`, `VT2/2`, `VT3/3`, 22 recintos) y **cero `ACAD_TABLE`**. Es decir: el producto sólo funcionaba sobre el piso recortado, que es el caso raro.
- **Lo que ya existía y no usaba nadie:** el reparto de recintos por vivienda estaba resuelto y probado en `evaluator.group_rooms_by_unit_label` desde antes, y lo consumía **una sola** capacidad (`plano.superficie_util`) para dar un número por vivienda que no llegaba a ningún entregable. Lo que faltaba era llevarlo hasta un documento, auditar el propio reparto y negarse a totalizar lo que no cuadra.
- **Lo que lo mantiene fuera de `D-7`:** no gradúa nada. No dice si una vivienda es pequeña ni si un solape es un error del plano o una convención de su autor: dice qué piezas hay, cuánto miden y qué impide totalizar. Frontera comprobada por la verificación bloqueante `la_medicion_no_califica`, con su test de que **falla de verdad**.
- **Entregable demostrable:** `python scripts/medir_planta.py mi_planta.dxf` — enseña el procedimiento, mide, escribe el PDF, imprime el acta y no toca el DXF (sha256 verificado antes y después). Sin clave de API y sin red.
- **Tareas:** `TL-11`, `SK-10`. **No depende del corpus normativo ni de ninguna firma**, igual que `OP-15`.

### OP-17 · «¿Se puede circular por esta planta y llegar a todas partes?» — **PRÓXIMA, tras cerrar V1**
`Decidida el 2026-08-20`

- **Devuelve:** anchos de paso libres, radios de giro y pendientes de rampa medidos sobre el DXF/BIM real —no supuestos—, con la pieza concreta de la que sale cada cifra.
- **Por qué entra en el backlog y por qué no antes de V1:** es geometría pura sobre un plano ya medido, así que reutiliza el mismo motor que `superficies.medicion_de_planta` (`OP-16`) en vez de abrir un camino nuevo — mismo perfil de riesgo bajo que `OP-15`/`OP-16`, no depende del corpus normativo. No entra antes porque V1 no está cerrado todavía y esto amplía, no completa, el vertical ya en marcha.
- **Tareas:** por definir cuando se aborde. No implementado ni empezado — esta entrada es sólo la decisión de que es la siguiente ampliación, no una tarea abierta.

### OP-18 · «¿Se retranquea el edificio lo que exige la parcela real?» — **PRÓXIMA, tras cerrar V1**
`Decidida el 2026-08-20`

- **Devuelve:** el contraste entre la geometría del edificio (de `superficies.medicion_de_planta`) y el límite real de la parcela (de Catastro, Fase A ya construida — ver `CP-4` y `docs/prd/2026-08-20-procedencia-y-fecha-de-datos-de-parcela.md`), con el retranqueo medido en cada lindero.
- **Por qué entra en el backlog y por qué no antes de V1:** cruza dos geometrías que **ya existen y ya están medidas por separado** — no añade ninguna fuente de dato nueva, sólo el cruce entre ellas. Mismo motivo que `OP-17` para no entrar antes: amplía un vertical que todavía no está cerrado.
- **Tareas:** por definir cuando se aborde. No implementado ni empezado.

### OP-13 · «Sácame el cuadro de carpintería de este plano» — **NO como estaba pensada** (medido, 2026-08-19)

- **Devuelve:** la tabla de puertas y ventanas por vivienda tipo, con dimensiones, tipo y acabado, y su procedencia pieza a pieza.
- **Por qué entra en la lista:** es la candidata que **más reutiliza el procedimiento ya probado de `SK-1`** —leer geometría, producir tabla, negarse a adivinar, escribir copia del DXF, PDF con procedencia, acta— y es la única de alto valor que **no necesita ni una regla del corpus**. Sobre el papel, la mejor.
- **Por qué NO se decide todavía, medido sobre `v2s.dxf` el 2026-08-19:** las **puertas** están, con el dato dentro del nombre del bloque tal como lo exportó Revit (`K_Puerta de entrada - 825 x 2150 mm-…-VT25`), 3 a 9 piezas por vivienda tipo y la dimensión legible en ~3 de cada 4. **Las ventanas no.** Todo lo que suena a ventana son cuatro bloques genéricos (`ven01`, `ven2`, `ven3`, `00 SEC VENTANA`), sin dimensiones y sin asociación a ninguna vivienda tipo: están dibujadas como geometría, no como objetos. Y en un cuadro de carpintería español **las ventanas son la mitad cara** — las del vidrio, las del DB-HE, las que se presupuestan pieza a pieza. Un cuadro que trae las puertas y deja las ventanas en blanco no ahorra la tarde.
- **Siguiente paso, y es barato:** medir **un segundo plano real** (media jornada, mismo sondeo, sin código de producción). Una muestra de uno no distingue una convención del sector de la costumbre de este estudio. Si las ventanas vienen como bloques con atributos, esto pasa a ser la mejor candidata del catálogo por bastante margen; si vienen otra vez sueltas, el problema real es **reconocer huecos en muros**, que es visión por computador sobre DXF y merece su propia decisión.
- **Segundo plano medido el 2026-08-19 (`V5.dxf`, 606 definiciones de bloque): confirma, no rescata.** Misma estructura exacta que el primero — puertas con la dimensión en el nombre del bloque, ventanas otra vez como los mismos cuatro genéricos (`ven01`, `ven2`, `ven3`, `00 SEC VENTANA`) sin dimensiones ni vivienda tipo, y 0 `INSERT` en modelspace. Dos ficheros distintos y la misma conclusión: ya no es una muestra de uno, es **cómo dibuja este estudio**.
- **Veredicto, con datos y no con impresión:** el cuadro de carpintería **no se hace como estaba pensado**. Quedan dos caminos y ninguno es ése: (1) un **cuadro de puertas**, llamándolo así — un día, honesto, y bastante menos valor del que prometía la idea; (2) **reconocer huecos en muros**, que es lo que haría falta para las ventanas, y que no es esta Skill sino visión por computador sobre DXF: semanas, PRD propio, y la pieza que desbloquearía varias cosas a la vez (carpintería, superficies construidas, DB-HE).
- **Lo que costó y lo que evitó:** media jornada de sondeo, tres días de Skill escrita contra un fichero que no tiene el dato. Es el mejor argumento del repositorio a favor de medir antes de escribir.
- **Análisis completo:** `docs/design/2026-08-19-valor-comercial-de-las-skills.md` §3.

### OP-14 · «Genérame los detalles constructivos» — **NO SE HACE**, y queda escrito

- **El veredicto:** un detalle constructivo no se deriva del proyecto, se **elige** con criterio, según clima, sistema constructivo, presupuesto y con qué industrial trabaja el estudio. ArchMuse no tiene ninguno de esos cuatro datos, y pedirlos todos es un formulario, no una Skill. Foso nulo: todo estudio con dos años tiene su biblioteca afinada a base de obras y no la cambia por una generada, y las de los fabricantes son gratis y con garantía detrás. Es además **lo más cercano a la autoría de todo el catálogo** — un detalle mal resuelto no es un aviso en un PDF, es una humedad o un desprendimiento —, así que rompe C3 justo donde `NORTH_STAR_2031.md` §5 la declara innegociable. Mismo patrón que `OP-11`: demuestra muy bien y no vende.
- **Se registra aquí para que nadie lo redescubra como idea nueva dentro de seis meses.**

**Resumen: 17 objetivos. 4 en el MVP (OP-1, OP-2, OP-3, OP-15), 4 en V2, 2 aplazados, 2 rechazados, 1 transversal, 1 recortado, 1 medido y reorientado, 2 próximas tras cerrar V1 (OP-17, OP-18).**

---

## 2. Lo que este backlog decide NO hacer

| Idea | Veredicto | Motivo |
|---|---|---|
| Framework de agentes (LangChain, LangGraph, OpenAI Agents SDK) | **No** | Auditoría §5. El orquestador propio ya existe, funciona y su modelo de estado *es* el de `modelo/` |
| RAG sobre los PDF del CTE | **No** | Auditoría §9. El modo de fallo es una cita plausible y equivocada, y eso termina la relación comercial |
| Memoria conversacional inyectada al LLM | **No** | Alucinación con apariencia de historia, y fuga entre proyectos de clientes distintos |
| Multi-agente, críticos enfrentados, debate | **No** | Multiplica coste y latencia y no mejora lo único que importa: que las cifras sean correctas |
| Edición colaborativa en tiempo real | **No** | Un trimestre, nadie la ha pedido, y es casi lo contrario del registro auditable que se vende |
| Reescribir el visor 3D en React Three Fiber | **No** | La reescritura de mayor riesgo y menor valor disponible en el repositorio |
| Cientos de capacidades | **No** | C4: 8-12 auditadas, no un catálogo. El registro tiene 4; al cerrar el MVP debe tener entre 8 y 12, **no más** |
| Ingesta de imágenes / planos escaneados | **Aplazado** | El mercado objetivo entrega DXF |
| Que el agente se instale Skills solo | **Prohibido por diseño** | Un sistema que se amplía a sí mismo pierde la propiedad de que alguien pueda decir qué sabe hacer |
| Checklist determinista de documentación para visado | **Aplazado, 2026-08-20** | Dominio administrativo/normativo, no geométrico — el mismo riesgo que se evitó a propósito no construyendo sobre el corpus CTE vacío. No se construye sin un corpus verificado detrás |
| Detección de incoherencias entre memoria descriptiva (texto) y planos medidos | **Aplazado, 2026-08-20** | Requiere NLP sobre texto ambiguo. No encaja con el estándar «nunca inventar» de este producto sin generar falsos silencios — el mismo riesgo que ya costó reescribir `OP-15` y `OP-16` para no dar avisos falsos sobre geometría, aquí sin ni siquiera geometría de por medio |
| Mediciones y presupuesto desde geometría verificada | **Aplazado, 2026-08-20** | Expansión de mercado, no del foso actual — aparcado hasta que haya evidencia real de demanda, no intuición |

---

## 3. Experiencia y cerebro del agente

### AG-1 · Planificador tipado: una llamada, un DAG validado
`P0` · `HECHO (2026-08-19)` · PRD: **APROBADO por Pablo el 2026-08-19** — `docs/prd/2026-08-19-planificador-tipado.md` · dep: `TL-3` (HECHO), `ME-5` (HECHO) · ~2j

> **Condición de la aprobación:** mantenerlo **deliberadamente pequeño**. Ni framework de agentes, ni LangGraph, ni otro orquestador. Produce un DAG y nada más.

- **Objetivo:** una sola llamada a Claude con `tool_choice` forzado contra un JSON Schema cuya salida es un DAG de `(capacidad_id, versión, argumentos)`. El ejecutor (`agente/ejecucion.py`) **ya espera un `Plan` validado**; hoy lo construye el bucle paso a paso. Esta tarea es quien lo produce de una vez.
- **Valor para el arquitecto:** puede **ver lo que ArchMuse va a hacer antes de que lo haga**, y pararlo. Un bucle no se puede enseñar; un plan sí.
- **Terminado cuando:** la misma intención sobre el mismo grafo produce un plan equivalente dos veces seguidas, y `cache_read_input_tokens > 0` en la segunda.
- **Cómo quedó (2026-08-19):** `agente/planificador.py`. **Una** llamada con `tool_choice` forzado sobre una herramienta de esquema fijo; el `Plan` que sale lo ejecuta `Ejecutor` **sin adaptación**. Rechaza sin ejecutar nada —Skill inexistente, ciclo, dependencia rota, techo de pasos, paso sin skill— y el plan **vacío es una respuesta, no un fallo**: sale con motivo y queda anotado como carencia, que es cómo se mide lo que falta por uso real. `a_texto()` lo enseña **con los efectos que habrá que autorizar**: enterarse de que algo escribe un fichero después no sirve de nada. Prefijo de manifiestos delante y marcado para caché, estado detrás, y los valores del proyecto **no viajan**.
- **La condición de la aprobación tiene su propio test:** `test_el_planificador_no_ejecuta_nada` comprueba por AST que no se importe ningún framework y que este módulo no ejecute, no observe ni invoque — un planificador que empieza a hacer eso *es* un framework de agentes escrito a plazos. Y `test_solo_hay_un_punto_de_llamada_al_modelo` fija que la llamada sea una.
- **Se ve funcionando:** `python scripts/demo_agente.py`, secciones 4 y 5 — con el modelo guionizado, así que no cuesta nada.
- **Alcanzable desde la fachada (2026-08-19, cuarta sesión):** `copiloto.atender(via=VIA_PLAN)`, o partido en dos con `copiloto.proponer()` / `copiloto.ejecutar_propuesta()`. Hasta entonces el planificador sólo lo llamaban los tests y la demostración. **El defecto sigue siendo `VIA_BUCLE`** y hay un test que lo fija: cambiarlo cambia el comportamiento de todo llamador existente y se decide con datos de uso (`AG-3`), no de golpe.

### AG-2 · Validador determinista del plan, con la pregunta como salida
`P0` · `HECHO (2026-08-19)` · PRD: no · dep: `AG-1` · ~1,5j

- **Objetivo:** validar el plan **sin gastar un token ni tocar un fichero**: ¿existe la capacidad?, ¿la versión?, ¿requisitos satisfechos y `KNOWN`?, ¿DAG acíclico?, ¿cabe en presupuesto? Ya existe a nivel de Skill (`agente/skill.py` devuelve la pregunta concreta); falta a nivel de plan.
- **Valor para el arquitecto:** convierte el peor momento del producto —«no puedo hacer esto»— en el mejor: **una pregunta concreta que él sabe responder**.
- **Terminado cuando:** cuatro planes inválidos (capacidad inexistente, ciclo, requisito sin cumplir, fuera de presupuesto) se rechazan con motivos distintos y **cero tokens**; el tercero produce la pregunta que lo desbloquea.
- **Cómo quedó (2026-08-19):** `planificador.revisar()`. Distingue tres cosas que se confunden con facilidad: **motivos** (el plan está mal y no se arregla contestando nada), **preguntas** (el plan está bien y le faltan datos del proyecto — la salida es la pregunta concreta, no un «faltan datos» que nadie sabe contestar) y **efectos a autorizar** (lo que va a pasarle al ordenador del arquitecto, enseñado antes). Los cuatro rechazos dan **motivos distintos**, con un test que lo exige: «no se puede ejecutar» sin decir cuál de las cuatro cosas falla obliga a depurar a ojo. Vive aparte del planificador porque un plan puede llegar de tres sitios —del modelo, de un fichero guardado hace meses, o de una pantalla— y los tres tienen que pasar por el mismo portero sin pagar una llamada.
- **Alcanzable desde la fachada (2026-08-19, cuarta sesión):** lo llama `copiloto.proponer()`, y su salida es lo que se le enseña al arquitecto antes de ejecutar nada — con los efectos separados entre los que faltan por autorizar y los ya concedidos, que allí no se sabía.
- **Lo que falta y es de `AG-3`:** el presupuesto. Sumar el coste estimado del plan exige la tabla medida por perfil de `SEG-4`, y ésa es la siguiente tarea de esta rama.

### AG-3 · Presupuesto por ejecución y escalonado de modelo medido
`P1` · `PENDIENTE` · PRD: no · dep: `AG-2`, `SEG-4` · ~1j

- **Objetivo:** el validador suma el coste estimado del plan y rechaza lo que supera el techo del plan del cliente. Y con las cifras de `SEG-4` en la mano, decidir el modelo de cada perfil de `ia/modelos.py` **midiendo**, no por intuición (D-5).
- **Valor para el arquitecto:** no descubre el coste en la factura, y no paga Opus por una clasificación.
- **Terminado cuando:** un plan que excede el presupuesto se rechaza antes de la primera llamada, y existe una tabla medida de coste por perfil.

### AG-4 · Un ciclo de replanificación, y el segundo fallo es una pregunta
`P1` · `HECHO (2026-08-19)` · PRD: no · dep: `AG-2` · ~1j

- **Objetivo:** si tras ejecutar falta un dato, se replanifica **una vez**. Si tras replanificar sigue faltando, se para y se pregunta. Nunca un tercer intento.
- **Valor para el arquitecto:** el sistema no se come su presupuesto dando vueltas, y no le entrega media respuesta como si fuera entera.
- **Terminado cuando:** un escenario con un dato ausente replanifica una vez y termina en pregunta, con el coste acotado y registrado.
- **Cómo quedó (2026-08-19):** `copiloto._atender_con_plan`, detrás de `atender(via=VIA_PLAN)`. `planificar()` acepta `observacion`, que va **con lo que cambia y nunca en el prefijo cacheado**; el planificador sigue haciendo exactamente una llamada y sigue sin decidir cuándo replanificar — eso es de la fachada.
- **La observación se deriva de los pasos, no la redacta un modelo.** Si la escribiera una llamada intermedia, el segundo plan se construiría sobre un resumen y no sobre lo que pasó, que es el hueco por el que entra un dato que nadie midió. Dice qué salió (con su id, para que el segundo plan lo conserve), qué no salió y por qué, y qué haría falta saber.
- **Cuándo NO se replanifica, que es la mitad del diseño:** si salió todo; si el plan ni llegó a ejecutarse (vacío, rechazado, **no confirmado** — proponerle otro a quien acaba de decir que no es lo contrario de lo que significó su «no»); si el segundo plan es **idéntico** al que acaba de fallar (no hay nada nuevo que pueda salir de él, y sí una factura); y —la regla dura— **nunca para esquivar una autorización**. Si un paso quedó `PENDIENTE_DE_AUTORIZACION`, se para y se pide el permiso. Buscar otra ruta que no necesite el permiso que acaban de no darte es la única cosa que este sistema no puede hacer nunca.
- **El techo es duro:** `MAX_REPLANIFICACIONES = 1`, y `atender` recorta a ese valor aunque le pidan cinco. Un parámetro que admitiera cinco es cómo se consigue el agente que da vueltas.
- **Lo ya hecho no se repite:** la segunda ejecución reutiliza el mismo `ejecucion_id`, así que la reanudación del `Ejecutor` salta los pasos completados — ni recalcula, ni vuelve a cobrar, ni vuelve a escribir un fichero.
- **El defecto que esto destapó, y que ya existía:** la reanudación buscaba el paso anterior **por `paso_id` a secas**. Con un plan interrumpido y relanzado tal cual daba igual, porque el plan era el mismo; en cuanto entra la replanificación, no: un segundo plan que reutilizara el id «ficha» para otra Skill, o para los mismos argumentos cambiados, se habría llevado el resultado viejo **con su sello y su acta, sin que nada fallara**. Ahora `ResultadoDePaso` lleva `sello_de_entrada` (Skill + argumentos) y `_es_el_mismo_paso` lo compara. Un apunte antiguo sin ese sello se acepta —rechazarlo repetiría el trabajo de las ejecuciones ya en curso, incluidas las que escribieron un fichero— pero la Skill sí se compara, que es lo que se podía comparar antes.
- **Se comprueba en:** `tests/test_agente_replanificacion.py`, 17 tests. Los dos que más importan: `test_un_permiso_que_falta_no_se_rodea_replanificando` y `test_nunca_hay_un_tercer_intento`.

### AG-5 · Progreso por paso, en directo
`P1` · `PENDIENTE` · PRD: **sí** · dep: `INF-4`, `INF-5` · ~1,5j

- **Objetivo:** exponer el avance de una ejecución (paso, capacidad, estado, duración) como flujo de eventos, leyendo la bitácora que ya se escribe.
- **Valor para el arquitecto:** un trabajo de diez minutos deja de ser una rueda girando. Ve qué se está comprobando ahora mismo.
- **Terminado cuando:** una ejecución de cinco pasos emite un evento por paso y la pantalla los muestra sin recargar.

### AG-6 · Conversación sobre un trabajo ya hecho
`P1` · `PENDIENTE` · PRD: **sí** · dep: `DOC-1` · ~1,5j

- **Objetivo:** que el arquitecto pueda preguntar «¿por qué esta celda quedó vacía?» sobre una ejecución terminada, y la respuesta salga de la bitácora y del acta — **nunca** de una nueva inferencia del modelo.
- **Valor para el arquitecto:** es C2 hecho producto: el trabajo hecho, con el porqué a un clic.
- **Terminado cuando:** una pregunta sobre una celda `N/D` se responde citando el paso concreto, y una pregunta cuya respuesta no está en la bitácora se contesta «no lo sé», no se infiere.

### AG-7 · Propuesta de Skill que falta, con umbral
`P2` · `PARCIAL` · PRD: no · dep: D-8 decidida · ~1j

- **Objetivo:** `agente/carencias.py` ya registra cuándo un objetivo no encuentra Skill. Falta el umbral: cuántas veces tiene que repetirse antes de proponérselo a Pablo, y con qué forma.
- **Valor para el arquitecto:** el producto aprende **qué le falta** por uso real, no por intuición del que lo programa.
- **Terminado cuando:** una carencia repetida N veces genera una propuesta con su borrador de manifiesto, y **ArchMuse sigue sin poder instalarla solo** (el test que lo vigila no se toca).
- **Bloqueada por:** D-8 en `decisiones-pendientes.md`.

### AG-8 · Ejecución en paralelo de pasos independientes
`P2` · `HECHO (2026-08-19)` · PRD: no · dep: `AG-1` · ~1j

- **Objetivo:** ejecutar en paralelo los nodos del DAG que no dependen entre sí, manteniendo el determinismo del resultado y el orden de la bitácora.
- **Valor para el arquitecto:** un análisis de una planta baja de diez minutos pasa a tres.
- **Terminado cuando:** un plan con cuatro ramas independientes tarda menos que en serie y produce **el mismo sello** que en serie.
- **El defecto que cierra, y era una mentira escrita:** el prompt del planificador le pide al modelo que declare qué pasos son independientes «porque es lo que permite ejecutarlos a la vez». No lo permitía: `Plan.orden()` calculaba los niveles topológicos y **los aplanaba**, y el ejecutor recorría la lista. La independencia se calculaba para tirarla.
- **Cómo quedó (2026-08-19):** `Plan.niveles()` devuelve los niveles y `orden()` pasa a ser su aplanado —el orden de referencia de la bitácora, que no se mueve—. `Ejecutor` acepta `max_paralelo` (4 por defecto, `1` lo desactiva del todo) y ejecuta un nivel en hilos **con dos condiciones a la vez**: nivel entero seguro y más de un paso.
- **Qué es «seguro», y por qué lista blanca:** `efectos.SEGUROS_EN_PARALELO = {llama_api_externa, gasta_tokens}` — los dos que esperan por la red y no tocan nada compartido, que es donde está todo el tiempo de un análisis. Los otros cuatro **no** están, cada uno con su motivo escrito: dos pasos podrían escribir la misma ruta; una marca `INTENTADO` tiene que quedar apuntada antes de ejecutar; dos escrituras a la vez en la memoria dejan los conflictos del proyecto en el orden de quien ganó la carrera, y ese orden se le enseña al arquitecto. Cerrada a propósito: un efecto nuevo del catálogo **nace secuencial**.
- **Todo o nada por nivel, y cuesta velocidad a propósito:** basta con que un paso del nivel no sea seguro para que el nivel entero vaya en serie. A cambio, nadie tiene que razonar sobre interleavings para saber si un plan es seguro.
- **La bitácora se apunta siempre en el orden de `orden()`**, no en el de llegada: los apuntes de un nivel paralelo se difieren y se escriben al final, en orden. Diferir es seguro sólo ahí —esos pasos no tienen efectos que deshacer—, y es lo que permite que dos ejecuciones del mismo plan se comparen línea a línea, que es de lo que depende la reanudación.
- **Se comprueba en:** `tests/test_agente_paralelo.py`, 18 tests. Los dos que llevan el criterio de la tarea: `test_mismos_sellos_y_misma_bitacora_que_en_serie` (mismos estados, mismos sellos y bitácora idéntica) y `test_cuatro_ramas_independientes_tardan_menos_que_en_serie`.

### AG-9 · Contexto largo: recortar lo que ve el modelo sin abrir un hueco
`P1` · `HECHO (2026-08-19)` · PRD: no · dep: — · ~0,5j

- **El defecto que cierra:** `nucleo.ejecutar` añadía cada resultado de herramienta al historial **entero y literal**, y no quitaba nada nunca. Con un DXF de cuarenta recintos leído de punta a punta, un solo resultado se come el contexto y las herramientas siguientes fallan por una razón que no tiene nada que ver con lo que se pidió — o sea, justo con el plano del cliente. No se ve venir y no da un error legible.
- **Cómo quedó (2026-08-19):** `agente/recorte.py`. Tres reglas, y las tres son de no-invención antes que de eficiencia: se recorta **con la estructura y no con la cadena** (ninguna clave desaparece y lo que sale sigue siendo JSON válido: un modelo que recibe un JSON roto improvisa); el recorte **se declara donde el modelo lo lee** (clave `__recorte__` con aviso, más regla nueva en el prompt del sistema) y viaja hasta `Respuesta.recortes`; y **no se resume nunca** — resumir un resultado de herramienta es inventar en pequeño.
- **El original no se pierde:** queda íntegro en `PasoEjecutado.resultado`, y es contra el original —no contra el recorte— contra lo que `respaldo.py` comprueba las cifras del texto final. Un modelo que ve menos puede citar menos, nunca más.
- **Y si ya no cabe la conversación entera**, el bucle **para antes de llamar** (`parada == "contexto_agotado"`) conservando lo hecho, en vez de pagar una llamada para recibir un error del proveedor.
- **Topes:** 20.000 caracteres por resultado (~5k tokens) y 300.000 de historial. Que no salten nunca en uso normal es el diseño.
- **Se comprueba en:** `tests/test_agente_recorte.py`, 12 tests.

---

## 4. Skills

### SK-1 · Skill del cuadro de superficies
`P0` · `HECHO (2026-08-19)` · PRD: **APROBADO por Pablo el 2026-08-19** — `docs/prd/2026-08-19-skill-del-cuadro-de-superficies.md` · dep: `TL-1` (HECHO), `TL-9` (HECHO), `TL-2` · ~2j

> **Condición de la aprobación:** la verificación de la suma es **informativa, no bloqueante**, hasta tener al menos **10 proyectos reales**.

- **Objetivo:** el procedimiento profesional completo del vertical, declarado como Skill: qué necesita, qué capacidades usa, qué produce, qué efectos tiene y **qué verificaciones deterministas debe pasar** antes de darse por buena.
- **Valor para el arquitecto:** el trabajo que hoy le lleva media tarde de contar polilíneas, con la traza de cada número.
- **Terminado cuando:** ejecutada sobre el DXF real de `ARCHMUSE_DXF_V2S` produce el cuadro relleno; ejecutada sin escala definida **pregunta** en vez de suponer.
- **Cómo quedó (2026-08-19):** `agente/skills/superficies.py`, `superficies.cuadro_de_vivienda@1.0.0`. El orden del procedimiento es lo que aporta: **primero** se comprueba la unidad del plano (un DXF en milímetros leído como metros cumple todos los mínimos y sale impecable), luego se mide la superficie útil **por su propio camino** para poder cruzarla contra la suma, y sólo entonces se calcula y se escribe. La verificación de la suma es **informativa y no bloqueante**, condición textual de Pablo, con su propio test para que cambiarla sea deliberado. `ruta_destino` es obligatoria: mirar sin tocar ya lo hace la capacidad `plano.cuadro_de_superficies`, y pedir autorización para no escribir enseñaría al arquitecto a concederlas sin leerlas. Cortarse a mitad **no se presenta como fallo del sistema**: es una respuesta con su pregunta.
- **Consolidada el 2026-08-19 (segunda pasada).** La Skill declaraba «no resuelve las ambiguedades del plano: las pregunta» y devolvia solo el `titulo` de cada solicitud. La capacidad las da completas —que hueco resuelven, que opciones hay, con que superficie cada una y con que forma se contesta— y todo eso se perdia: para contestar habia que saltarse la Skill e ir a la capacidad, o sea leer el codigo. **Una pregunta que no se puede contestar no es preguntar**, es el mismo hueco mudo con signos de interrogacion. Corregido, con un test de punta a punta sobre `v2s.dxf` — hace falta el plano real porque las solicitudes de asignacion nacen de una ambiguedad de verdad (dos «Tendedero», una «Terraza» solapada) y un `ACAD_TABLE` no se sintetiza. La pieza vive ahora en `agente/skills/_comun.py`: es cierta para toda Skill, no solo para esta.
- **Entregable demostrable:** `python scripts/cuadro_de_superficies.py mi_plano.dxf` — enseña qué va a hacer, lo hace, imprime el acta y dice qué no ha podido calcular. Sin clave de API y sin red.

### SK-2 · Skill de comprobación de una planta
`P2` · `PENDIENTE` · PRD: **sí** · dep: `TL-5`, `NOR-2` · ~2j

- **Objetivo:** el procedimiento que un arquitecto sigue al revisar una planta, con las reglas agrupadas por Documento Básico y la cobertura declarada por adelantado.
- **Valor para el arquitecto:** una revisión con criterio de arquitecto, no una lista de 38 comprobaciones sueltas.
- **Terminado cuando:** produce hallazgos agrupados por DB, cada uno con cita, y una sección de «no evaluado» derivada de las limitaciones, no redactada.

### SK-3 · Requisitos del cliente desde texto libre
`P1` · `PARCIAL` · PRD: no · dep: `ME-1` · ~1j

- **Objetivo:** `agente/skills/programa.py` ya registra requisitos declarados. Falta la entrada real: pegar un correo o un acta de reunión y obtener **requisitos candidatos con su fragmento literal de origen**, que el arquitecto aprueba uno a uno.
- **Valor para el arquitecto:** deja de perder en un hilo de correo lo que el cliente pidió en marzo.
- **Terminado cuando:** un texto de reunión produce candidatos con su cita textual, ninguno entra en la memoria sin aprobación explícita, y lo aprobado queda con su origen.

### SK-4 · Catálogo de Skills visible y versionado
`P1` · `PENDIENTE` · PRD: no · dep: `INF-7` · ~1j

- **Objetivo:** que el arquitecto pueda ver qué sabe hacer ArchMuse, con la versión de cada procedimiento, qué necesita para ejecutarlo y qué **no** comprueba.
- **Valor para el arquitecto:** sabe qué está comprando y qué no. Es lo contrario de la caja negra que sobrevende.
- **Terminado cuando:** el catálogo se genera del registro (no de una lista escrita a mano) y una Skill nueva aparece sin tocar la pantalla.

### SK-5 · Validación colegiada del procedimiento de cada Skill
`P1` · `PENDIENTE` · PRD: no · dep: D-7 decidida · ~0,5j por Skill

- **Objetivo:** el proceso —no el código— por el que un arquitecto colegiado revisa y firma que el procedimiento de una Skill es el que se sigue en un estudio de verdad. Con registro de quién firmó qué versión.
- **Valor para el arquitecto:** la diferencia entre «un programador creyó que se hace así» y «un colegiado dice que se hace así».
- **Terminado cuando:** las tres Skills existentes tienen firma y versión firmada, y una Skill sin firmar sale marcada como tal en el catálogo.
- **Bloqueada por:** D-7.

### MVP-1 · El MVP de las 5 piezas (informe ejecutivo del 2026-08-19)
`P0` · `PARCIAL (2026-08-19)` · PRD: **escrito** para la pieza 5 — `docs/prd/2026-08-19-copiloto-que-modifica-el-proyecto.md` · dep: — · ~1j

- **Lo que pide el informe:** ① crear proyecto, ② análisis automático, ③ generador multi-alternativa, ④ evaluador, ⑤ copiloto que **modifica** el proyecto. Más la vista de tres zonas del §4.
- **El hueco real, medido antes de construir nada:** ①②③④ **ya existían** como endpoints (`/api/analizar-sitio`, `/api/generar-opciones` con su comparador, `/api/analizar`, `/api/viabilidad-financiera`). Lo que no existía era ⑤ —ni en el backend (es `OP-8`, aplazado a V2) ni en el frontend: **cero líneas de chat en los 800 KB de la SPA**— y la vista de tres zonas.
- **Lo que desbloqueó ⑤:** `OP-8` está aplazado porque escribir en el fichero de un cliente es el efecto más caro de equivocarse. Aquí **no hay ningún fichero de cliente**: se transforma el diccionario de parámetros con el que se generó una alternativa. Con esa distinción, ⑤ deja de ser V2 peligroso y pasa a ser una jornada.
- **Hecho (`CP-1`, `CP-2`, `CP-3`):** `agente/herramientas/proyecto.py` (una capacidad, `proyecto.ajustar_programa`, aritmética y estrecha), el endpoint `/api/copiloto` con **registro estrecho** —el copiloto sólo ve una herramienta, así que no puede leer un DXF ni escribir un fichero aunque quiera—, y la vista `/mvp` de tres zonas con las cinco pestañas. 23 tests nuevos.
- **La decisión de producto de Pablo (2026-08-19) sobre la pestaña Normativa:** se separa **comprobado** de **estimado**. Los parámetros urbanísticos (edificabilidad, ocupación, altura, retranqueos) se comprueban con aritmética exacta contra lo que el usuario introdujo y ahí sí se dice «cumple»; las 20+ reglas de `evaluator.py` llevan umbrales **que no salen de ninguna fuente citada** y se enseñan como «indicadores de diseño», con el aviso de que no son verificación normativa. Presentarlas como cumplimiento es el modo de fallo nº1 del producto, y la prueba del §7 es un arquitecto que va a preguntar de dónde sale un número.
- **`CP-4` (cablear ①② de parcela real por Catastro/Mapbox): se dio por cableada el 2026-08-19, y estaba rota.** Hallazgo del 2026-08-20 al implementar la Fase A del PRD de procedencia de parcela (`docs/prd/2026-08-20-procedencia-y-fecha-de-datos-de-parcela.md`): `static/mvp.js::elegirParcela()` leía `datos.referencia_catastral`/`datos.geometria.superficie_m2` en la raíz de la respuesta -- pero `/api/analizar-sitio` envuelve todo en `{sitio: {datos: {...}}}` y el campo se llama `geometria_parcela`, no `geometria`. La condición era siempre `undefined && undefined`: la rama de éxito **nunca se disparó desde que se escribió el código**, y `tests/test_mvp_parcela_real.py` (inspección de texto fuente, nunca ejecuta el JS) no podía haberlo pillado. Arreglado el mismo día, junto con la procedencia estructurada y la fecha visible que pedía la Fase A -- verificado con un test HTTP nuevo (`tests/test_analizar_sitio_procedencia.py`) que no existía antes para este endpoint.
- **Pendiente:** `CP-5` (los cuatro objetivos de optimización: hoy el generador da **2** opciones, no 4), `CP-6` hecho, `CP-7` parcial.
- **El juez es la prueba del §7**, no esta lista. Ver `OP-11`.

### SK-9 · Skill de revisión de coherencia del plano
`P0` · `HECHO (2026-08-19)` · PRD: **escrito e implementado** — `docs/prd/2026-08-19-revision-de-coherencia-del-plano.md` · dep: — · ~1j

- **Objetivo:** el procedimiento que sigue un arquitecto al repasar un plano antes de entregarlo, declarado como Skill: comprobar la unidad **primero**, buscar solapes, recoger los contornos cerrados por suposición y la geometría descartada, mirar los rótulos, contrastar el cuadro contra el dibujo, y entregar el informe diciendo también **qué se ha comprobado**.
- **Valor para el arquitecto:** la media hora larga de repaso a ojo que se rehace en cada revisión del plano, y —su caso de más valor— saber qué le están dando cuando recibe un DXF que no dibujó él.
- **Terminado cuando:** sobre `v2s.dxf` produce los nueve hallazgos con su entidad y su magnitud, el original conserva su sha256, y ningún hallazgo califica su gravedad. **Los tres comprobados por tests.**
- **Cómo quedó (2026-08-19):** `analyzer/coherencia.py` (la auditoría), `analyzer/coherencia_pdf.py` (el informe), `agente/herramientas/coherencia.py` (dos capacidades, separadas por el efecto), `agente/skills/coherencia.py` (el procedimiento, cuatro verificaciones bloqueantes) y `scripts/revisar_plano.py`. **Cero modificaciones al runtime de `agente/`:** el registro de capacidades y el de Skills funcionan por descubrimiento, así que basta dejar el fichero. El registro pasa de 9 a **11** capacidades, dentro del techo de C4.
- **El falso positivo que se encontró probando contra el plano real, y que conviene no repetir:** el cuadro numera los *huecos* (`dormitorio_1`) y el arquitecto numera los *rótulos* («Dormitorio 1»). Comparando sin normalizar los dos lados, un piso de tres dormitorios perfectamente correcto producía **seis hallazgos falsos**. Seis avisos falsos en el primer plano real habrían bastado para que nadie volviera a abrir el informe (`DESTROY_ARCHMUSE.md` §5.1). Tiene su test.
- **Corregido el 2026-08-19 (tres contratos de `agente/` que no cumplía, detectados por Terminal 1).** Los tres eran reales y los tres los cazó un test de política, que es exactamente para lo que están:
  1. **La protección de escritura estaba reimplementada, no reutilizada.** `agente/herramientas/coherencia.py` tenía su propia comprobación de destino y su propio sellado, «parecidos» a `_destino_seguro` y `_con_sello_intacto` de `plano.py`. Funcionaban, y ése es el problema: el día que se endurezca la protección —porque se pierda el plano de un cliente— se endurece en un sitio y la copia se queda como estaba sin que nadie lo note. Ahora se **importan**. Efecto secundario que además mejora el producto: un informe anterior ya no se sobrescribe, porque podría estar revisado y anotado.
  2. **Los contratos de las dos capacidades no estaban congelados** (`tests/test_agente_compatibilidad.py`). Congelados con `--congelar`: 11 contratos, **60 líneas añadidas y ninguna borrada** — ningún contrato existente cambió.
  3. **Las dos capacidades no estaban en el test de invocación** que recorre el registro entero comprobando que toda salida es un `dict` con `ok`, también al fallar. Añadidas, con su caso de fallo.
- **Y un cuarto, encontrado al verificar de extremo a extremo, que no había detectado ningún test:** pidiendo el informe **encima del propio plano**, la capacidad se negaba correctamente y el DXF no se tocaba —el sha256 lo confirma—, pero `scripts/revisar_plano.py` decidía si había entregable mirando si el fichero de destino existía. Como el destino *era* el plano del arquitecto, existía, y el guion anunciaba «LO QUE TE LLEVAS: PDF tu_plano.dxf». La protección aguantó; lo que falló fue lo que se le contaba al arquitecto, y en un entregable eso es igual de grave. Ahora lo que decide es que **la Skill declare el entregable**. Tiene su test.
- **Medido contra un SEGUNDO plano real el 2026-08-19 (`V5.dxf`), y ahí estaba el falso positivo que importaba.** Era exactamente la tarea que este backlog tenía como siguiente, y sirvió para lo que se esperaba: `V5.dxf` tiene **tres viviendas completas y correctas** en un solo fichero (VT1/3, VT2/2, VT3/3, 22 recintos), y la primera versión contaba los rótulos repetidos **sobre el plano entero**. Resultado: **11 hallazgos, 8 de ellos falsos** —«el rótulo Salón/cocina aparece 3 veces», «Baño 3 veces», «Dormitorio 1 3 veces»— sobre un plano bien dibujado. Ocho avisos falsos en el segundo plano real habrían bastado para que nadie volviera a abrir el informe.
  - **Corregido:** los rótulos se cuentan **dentro de cada vivienda**, con la misma agrupación que usa el resto del motor (`VT<n>` cuando lo hay, proximidad si no). Un rótulo sólo se repite —en el sentido que importa— cuando se repite dentro de la misma vivienda, porque es ahí donde el cuadro tiene un único hueco para él. `V5.dxf` pasa de 11 hallazgos a **3, los tres reales**; `v2s.dxf` no cambia.
  - **Y la segunda consecuencia:** con más de una vivienda, el contraste cuadro↔dibujo **no se hace** y se declara no comprobado con su motivo. Un cuadro describe una vivienda; cruzarlo contra los rótulos de tres daría discrepancias en todas las familias y ninguna sería cierta.
  - **Lo que sí quedó de `V5.dxf`:** tres contornos con el flag `closed` mal puesto, uno con **3 cm** de hueco. Y el handle `A61724` aparece **en los dos planos**, así que no es un descuido: es una costumbre de dibujo del estudio, y es justo lo que un informe recurrente sirve para ver.
  - **La limitación «sólo admite un DXF con una única vivienda detectada» era un desmentido, no una limitación:** estaba declarada y la herramienta no la hacía cumplir — emitía ocho hallazgos falsos tan campante. Ahora el número de viviendas va en la cabecera del informe, para que si ArchMuse agrupa mal se vea en la primera línea en vez de deducirse de unos hallazgos raros.
- **Lo que este entregable NO hace, y va en su manifiesto:** no comprueba normativa, no ordena por importancia, no lee muros ni carpintería, y **no compara la cifra escrita en una celda del cuadro contra la medida** — porque hoy no hay ningún plano real con el cuadro relleno con el que comprobar que eso funciona. Ver §12 y `OP-13`.

### SK-10 · Skill de medición de una planta con varias viviendas
`P0` · `HECHO (2026-08-19)` · PRD: no (ver nota) · dep: `TL-11` · ~1j

- **Objetivo:** el procedimiento que sigue un arquitecto al medir una planta: comprobar la unidad **primero**, separar las viviendas por los rótulos que puso él mismo en el plano, **auditar ese reparto**, medir cada recinto, cruzar la suma contra la geometría, totalizar sólo lo que se puede afirmar, y entregar el documento con la procedencia de cada cifra.
- **Valor para el arquitecto:** la medición pieza a pieza de una planta entera, que hoy se hace con una calculadora y se rehace entera en cada revisión del plano. Y —su caso de más valor— sirve para un DXF que no dibujó él.
- **Terminado cuando:** sobre la planta real de tres viviendas produce los tres cuadros con sus cifras exactas, sobre el plano con solapes se niega a totalizar con la cifra que lo explica, y ninguna vivienda con un impedimento lleva total. **Los tres comprobados por tests.**
- **Cómo quedó (2026-08-19):** `analyzer/medicion.py` (el cálculo puro), `analyzer/medicion_pdf.py` (el documento), `agente/herramientas/medicion.py` (dos capacidades, separadas por el efecto), `agente/skills/medicion.py` (el procedimiento, cinco verificaciones) y `scripts/medir_planta.py`. **Cero modificaciones al runtime de `agente/` y cero a `analyzer/parser.py` o `analyzer/evaluator.py`:** el reparto en viviendas ya existía y se **usa**, no se reimplementa. Registro de capacidades: de 11 a **13**.
- **La regla dura, que es la decisión de producto de esta Skill:** basta **un** impedimento para que una vivienda no lleve **ningún** total. Los tres son piezas solapadas, reparto dudoso entre viviendas, y una pieza cuyo rótulo no dice si es superficie interior o exterior. Un total que puede estar mal se copia a la memoria del proyecto y se firma; la ausencia de total se pregunta. Las piezas se miden igual —ahí está casi todo el valor— y el impedimento va escrito **con su magnitud**.
- **La auditoría del reparto, que es lo que separa medir de adivinar.** El reparto por «etiqueta `VT` más cercana» ya existía y es correcto en un plano con las viviendas separadas; en dos viviendas medianeras deja de serlo y **no avisaba de nada**. Ahora se mide la holgura de cada pieza (`HOLGURA_MINIMA_DE_REPARTO = 2`, calibrado contra el plano real: su peor pieza tiene 2,67) y un reparto apretado se declara y bloquea el total de esa vivienda.
- **El descuadre de redondeo, que habría sido el falso positivo de esta entrega.** La primera versión cruzaba la **suma de las cifras publicadas** contra la unión geométrica. Redondear ocho piezas a dos decimales y sumarlas produce hasta un céntimo de metro de diferencia que no es ningún solape: `VT3/3` daba 66,56 contra 66,55 y habría salido con un aviso de «metros dibujados dos veces» de 0,01 m². Se detectó ejecutando contra el plano real antes de escribir el test. Ahora se cruzan las magnitudes **crudas** —el aviso desaparece— y el total publicado sigue siendo la suma de las cifras publicadas, para que la tabla cuadre cuando el arquitecto la sume a mano. Son dos cifras distintas a propósito y está escrito por qué.
- **Nota de proceso (`CLAUDE.md`):** no lleva PRD propio. Se implementó bajo la orden directa de Pablo del 2026-08-19 («elige el siguiente trabajo profesional de mayor valor, impleméntalo de principio a fin y pruébalo con un proyecto real»), y lo que hace es cerrar el hueco de un objetivo ya aprobado (`OP-1`) sobre el caso normal. Queda anotado aquí para que la excepción sea visible y no una costumbre.
- **Lo que NO hace, y va en su manifiesto:** no mide superficie construida, no comprueba normativa ni ningún mínimo, no rellena el cuadro del DXF (para eso está `superficies.cuadro_de_vivienda`, que sí escribe en el plano) y no lee muros ni carpintería.

### SK-8 · Arquitectura común: escribir la Skill nº5 sin duplicar la nº1
`P1` · `PARCIAL (2026-08-19)` · PRD: no (es refactor, no capacidad nueva) · dep: — · ~0,5j

- **El hallazgo que la motiva, contado con las cifras:** al ir a escribir la segunda Skill de verdad se conto lo que ya habia, y el invariante mas caro del producto —*todo lo que una Skill prometio y no produjo sale `UNKNOWN` con motivo, nunca ausente*— estaba escrito **tres veces y de tres formas distintas**: `_sin_hacer` en `superficies.py`, `_desconocidas` en `evacuacion.py`, y dos bucles a pelo dentro de `territorial.py`. No es redundancia defensiva: son cuatro sitios donde arreglar el bug de uno deja los otros tres rotos. Y el invariante no es cosmetico — un hueco mudo se lee como «no aplica», que es la lectura contraria a la verdadera.
- **Hecho:** `agente/skills/_comun.py` con `sin_producir()`, `valor()` y `pregunta_legible()`. Las tres Skills migradas, `tests/test_agente_skills_comun.py` con 13 tests, y **una guardia estructural** que lee el fuente de `agente/skills/` y falla si alguna Skill vuelve a construir una afirmacion `UNKNOWN` a mano. Se mira el fuente y no el comportamiento a proposito: el comportamiento de la copia seria correcto, y ese es justo el problema.
- **Donde vive y por que ahi:** en `agente/skills/`, no en `agente/skill.py`. Esto no es el contrato de una Skill —ese lo hace cumplir `skill.py` con sus cinco garantias— sino la caja de herramientas de quien escribe una. Una Skill que prefiera no usar nada de aqui sigue siendo valida.
- **Pendiente:** `MJ-3` (`apartados_por_cobertura`), que sale del PRD de `SK-7` y espera su aprobacion.
- **Lo que NO va aqui, y es la mitad del criterio:** el procedimiento profesional. El dia que dos Skills compartan procedimiento es que son la misma Skill.

### SK-6 · Composición: una Skill que invoca otra
`P2` · `PENDIENTE` · PRD: no · dep: `SK-1`, `SK-2` · ~1j

- **Objetivo:** que una Skill pueda apoyarse en otra sin duplicar su procedimiento, manteniendo la declaración de efectos y verificaciones de ambas.
- **Valor para el arquitecto:** una revisión completa reutiliza el mismo procedimiento de evacuación que la revisión suelta, así que no puede dar dos resultados distintos.
- **Terminado cuando:** una Skill compuesta acumula los efectos y las limitaciones de las que invoca, y un test demuestra que no puede saltarse las verificaciones de la interna.

### SK-7 · Skill de redacción de memoria justificativa
`P3` · `PENDIENTE` · PRD: **ESCRITO el 2026-08-19, pendiente de aprobación** — `docs/prd/2026-08-19-skill-de-memoria-justificativa.md` · dep: `NOR-2`, `DOC-4` · ~3j

- **Objetivo:** el procedimiento de redacción, con la regla dura de que **toda cifra viene de un atributo ya calculado** y toda cita del corpus.
- **Valor para el arquitecto:** el documento más tedioso del proyecto, con su acta.
- **Terminado cuando:** ninguna cifra del texto puede rastrearse a algo que no esté en el grafo, verificado por el detector de cifras sin respaldo, y el documento sale marcado como borrador.
- **No empieza antes de `NOR-2`.** Ver OP-6.
- **La postura del PRD del 2026-08-19, y conviene leerla antes de aprobarlo:** el PRD **no propone redactar la memoria**. Redactarla hoy, con una regla en el corpus y sin firmar, produciria un documento cuyas justificaciones vendrian al 100 % de un modelo sin fuente — el `OP-6` que este backlog aplaza y el ataque nº1 de `DESTROY_ARCHMUSE.md` construido a proposito. Lo que propone es la mitad defendible: **el indice de apartados con su estado** (`JUSTIFICADO`, `SIN_DATO`, `SIN_CORPUS`, `NO_APLICA`), los datos de partida con su procedencia, y las preguntas que faltan. Con el corpus de hoy sale con **cero apartados justificados, y ese es el resultado correcto**. Efecto secundario que puede que valga mas que la Skill: convierte el valor del corpus en una cifra («justificamos N de M»), que es el argumento que hoy falta para contratar `NOR-1`. **No añade ninguna capacidad al registro** (C4): compone `territorial.resolver_ambito` y `normativa.reglas_aplicables`, que ya existen.
- **Sus tareas `MJ-1` a `MJ-3` valen aunque el PRD se rechace:** son la arquitectura comun de Skills (`SK-8`), no la memoria.

---

## 5. Tools (capacidades)

### TL-1 · Capacidades de geometría que el cuadro necesita
`P0` · `HECHO (2026-08-19)` · PRD: no · dep: — · ~1,5j

- **Objetivo:** envolver como capacidades **solo** lo que el vertical usa de `parser.py`, `escala.py`, `superficie_util.py` y `cuadro_superficies.py`. Nada más de `analyzer/`.
- **Valor para el arquitecto:** es lo que permite que el agente calcule superficies de verdad en vez de repetir lo que le digan.
- **Terminado cuando:** el registro tiene entre 6 y 8 capacidades, **no más**, y cada una devuelve resultado estructurado con `ok` y su golden.
- **Cómo quedó (2026-08-19):** `agente/herramientas/plano.py` con tres capacidades gruesas — `plano.leer_dxf`, `plano.cuadro_de_superficies`, `plano.superficie_util` — sobre `parser`, `escala`, `cuadro_superficies_export` y `superficie_util`. Registro: **7** capacidades, dentro del techo de C4. Ninguna escribe nada (la escritura es `TL-2`), y el test comprueba el sha256 del DXF de entrada. Lo que más importa: un plano cuya unidad no se puede deducir devuelve `ok: false` **con la pregunta**, y confirmar la escala desbloquea.

### TL-2 · Capacidad `io` de escritura de DXF, con el patrón de protección
`P0` · `HECHO (2026-08-19)` · PRD: **APROBADO por Pablo el 2026-08-19** — `docs/prd/2026-08-19-escritura-protegida-del-dxf-del-cliente.md` · dep: `TL-1` (HECHO) · ~2j

> **Condiciones de la aprobación:** original **siempre intacto y verificado por SHA-256**; efecto **explícitamente autorizado**; **`N/D` nunca convertido en número**.

- **Objetivo:** elevar a política lo que `tests/test_cuadro_superficies_export.py` ya hace: sha256 del original antes y después, `audit()` de la copia, ningún otro fichero escrito, **nunca escribir sobre el original**, ninguna celda bloqueada con una cifra inventada.
- **Valor para el arquitecto:** su plano no se toca. Esa frase, verificada byte a byte, es lo que permite que confíe la primera vez.
- **Terminado cuando:** el DXF de cliente sale relleno y el original conserva su sha256, verificado en test.
- **Cómo quedó (2026-08-19):** `plano.escribir_cuadro`, la **primera y única capacidad `io`** del registro. Las tres condiciones de la aprobación son tests: el sello del original se recalcula **también cuando la escritura falla a mitad** (que es donde de verdad podría tocarse algo) y un cambio convierte el resultado en un fallo grave; el portero de efectos se ha bajado de `Ejecutor` a **`Capacidad.invocar`**, de modo que cubre el CLI, MCP y un futuro plugin y no sólo las Skills; y las celdas sin resolver salen `N/D` con su motivo. `_destino_seguro` rechaza el origen por cuatro vías (misma cadena, ruta con rodeo, capitalización de Windows, `samefile`) y **se niega a sobrescribir un fichero existente**, que podría ser un entregable ya revisado. Invariante nuevo: **una Skill no puede declarar una capacidad cuyo efecto no declara** — el manifiesto no puede mentir por omisión sobre lo que le va a pasar al ordenador del arquitecto.

### TL-3 · Un manifiesto, tres consumidores generados
`P0` · `HECHO (2026-08-19)` · PRD: no · dep: — · ~2j

- **Objetivo:** de una sola declaración de `Capacidad` salen (a) el JSON Schema de herramienta para Anthropic, (b) la operación OpenAPI, (c) la firma de invocación programática.
- **Valor para el arquitecto:** indirecto pero decisivo — es lo que hace que ArchMuse pueda vivir dentro de su Revit algún día sin reescribirse.
- **Terminado cuando:** los tres artefactos de una capacidad son coherentes en nombres de parámetro, y añadir una capacidad no obliga a escribir su forma tres veces. **Es la verificación mecánica de C1.**
- **Cómo quedó (2026-08-19):** `agente/manifiesto.py` genera los tres del mismo `dataclass`; `comprobar_registro()` los compara entre sí **y contra la función Python real**, y `tests/test_agente_manifiesto.py::test_TODAS_las_capacidades_del_registro_son_coherentes` recorre el registro, de modo que la garantía cubre también las capacidades que aún no existen. El defecto que cierra: declarar `municipio` en el esquema sobre una función que espera `nombre_municipio` — hoy eso reventaba con `TypeError` delante de un cliente y nada lo detectaba antes.

### TL-10 · Validación estructural de los argumentos de una capacidad
`P0` · `HECHO (2026-08-19)` · PRD: no · dep: `TL-3` · ~0,5j

- **El defecto que cierra:** `Capacidad.invocar` comprobaba **dos cosas** —que no sobrara ninguna clave y que no faltara ninguna obligatoria— y nada más. Ni tipos, ni `enum`, ni rangos, ni nada anidado. Un `"25 m"` donde el manifiesto dice `number`, o un `"nave industrial"` donde dice `enum: [vivienda, local]`, entraba en la función y salía por el otro lado convertido en un resultado con pinta de bueno.
- **Por qué aquí importa más que en otro sitio:** los argumentos no los escribe un programador, los rellena un modelo leyendo un esquema. Que se equivoque es lo normal, no lo excepcional. Rechazarlo aquí cuesta **cero tokens** y produce un mensaje que el modelo sabe corregir en la iteración siguiente; dejarlo pasar produce un número que nadie midió y que ya no se distingue de uno medido.
- **No añade ninguna dependencia:** `jsonschema==4.26.0` ya era directa (`normativa/validacion.py`). La validación somera era una **omisión**, no una decisión de no depender de nada.
- **Cómo quedó (2026-08-19):** `Draft202012Validator` compilado en `__post_init__`, así que un esquema mal escrito revienta **al declarar la capacidad** y no seis meses después cuando el modelo por fin use esa herramienta. Se devuelven **todos** los problemas y no el primero, ordenados por la ruta del argumento para que dos llamadas iguales den el mismo mensaje. Los mensajes van en castellano y nombran el argumento como lo escribiría quien llama (`plantas[1].altura_m`, no un `deque`), porque los lee un modelo que tiene que corregir la llamada y, en el CLI de `CAD-1`, una persona.
- **Los dos mensajes que ya había se conservan**, porque son mejores que los del esquema: dicen qué se admite y qué falta. No se repiten con dos redacciones distintas.
- **Un hueco que encontró su propio test:** al descartar los `required`/`additionalProperties` que ya decía `invocar`, se descartaban también los **anidados** — y ésos no los dice nadie más, porque las dos comprobaciones a mano sólo miran el primer nivel. Es justo donde un modelo se equivoca de verdad. Corregido antes de cerrar.
- **Se comprueba en:** `tests/test_agente_argumentos.py`, 22 tests, incluido el de punta a punta que fija que el rechazo llega al bucle como `ok: false` con `is_error`, no como una excepción que tumbe la conversación.

### TL-11 · Capacidades de medición de una planta
`P0` · `HECHO (2026-08-19)` · PRD: no · dep: `TL-1` · ~0,5j

- **Objetivo:** las dos capacidades que `SK-10` necesita, separadas por el efecto: `plano.medicion_de_la_planta` (mide, no escribe nada) y `plano.medicion_en_pdf` (el documento, único con efecto).
- **Por qué dos capacidades nuevas y no quitar una limitación a las que ya había.** Las del cuadro (`plano.cuadro_de_superficies`, `plano.escribir_cuadro`) trabajan sobre **el cuadro que el plano ya trae dibujado**: sus filas son las que el arquitecto puso en su `ACAD_TABLE` y su trabajo es rellenarlas dentro del propio DXF. Eso exige que la tabla exista y que haya una sola vivienda para saber a cuál describe. Un plano con tres viviendas y sin tabla no cumple ninguna de las dos, y **ninguna de las dos condiciones es un defecto del plano**. Son dos trabajos distintos con dos entregables distintos, no uno con una limitación. Las del cuadro siguen siendo las buenas cuando el plano trae su tabla: devolverle al arquitecto su propio plano con su propia tabla rellena vale más que darle una lista.
- **Terminado cuando:** las dos respetan el contrato de salida también al fallar, la que escribe se niega sin autorización, el destino no puede ser el DXF ni un fichero existente, y el original conserva su sha256. **Todo comprobado por tests.**
- **Cómo quedó:** `_destino_seguro`, `_con_sello_intacto`, `_falta_el_fichero`, `_fallo_de_lectura` y `_sha256` se **importan** de `plano.py`, no se reimplementan — es el defecto nº1 que se le corrigió a `SK-9` y no se repite. La lista de «lo que no se comprueba» del PDF la deriva la propia capacidad de los manifiestos, y **no es un argumento**: si lo fuera, quien la invoca podría entregar un documento con la lista recortada. Contrato congelado y golden capturado en el mismo cambio (contra un fixture de **dos** viviendas: congelar la medición contra el piso de una sola dejaría sin vigilar el motivo por el que la capacidad existe).

### TL-4 · Golden obligatorio por capacidad determinista
`P1` · `HECHO (2026-08-19)` · PRD: no · dep: `TL-1` · ~0,5j

- **Objetivo:** test de política que recorra el registro y **falle** si una capacidad de naturaleza `determinista` no tiene su golden.
- **Valor para el arquitecto:** la garantía de que la misma entrada da la misma salida el año que viene.
- **Terminado cuando:** añadir una capacidad determinista sin golden pone la suite en rojo.
- **Cómo quedó (2026-08-19):** `tests/test_agente_goldens.py` recorre el registro y exige caso congelado en `tests/fixtures/golden/G11_capacidades.json` para toda capacidad `determinista` — 7 casos hoy. Compara el resultado entero, no campos elegidos, y las claves excluidas van declaradas con motivo por caso (GUID de IFC, ruta temporal). `python tests/test_agente_goldens.py --recapturar` regenera. **Limitación anotada:** el caso de `plano.cuadro_de_superficies` congela la negativa (DXF sin `ACAD_TABLE`); el camino bueno sólo se prueba contra el `v2s.dxf` real cuando `ARCHMUSE_DXF_V2S` está definida.

### TL-5 · Desatar `classify_problems` y envolver las 38 reglas
`P2` · `PENDIENTE` · PRD: no · dep: `TL-3` · ~4j

- **Objetivo:** invertir las 382 líneas de `if/elif` de `evaluator.classify_problems` para que cada regla declare su propia traducción a hallazgo, y agrupar las 38 `evaluate_*` en 4-6 capacidades **gruesas** (no 38 herramientas finas: un planificador que elige entre 38 opciones casi idénticas se degrada).
- **Valor para el arquitecto:** es lo que abre OP-4, la revisión completa.
- **Terminado cuando:** ninguna regla necesita una rama en `classify_problems`, y los goldens existentes siguen pasando sin recapturar.
- **Riesgo registrado:** es el aplazamiento más peligroso del plan (riesgo A3). Si el segundo vertical no arranca, esto no se hace nunca y el producto se queda con una capacidad.

### TL-6 · Caché determinista por (versión de capacidad, sello del grafo)
`P2` · `PENDIENTE` · PRD: no · dep: `ME-2`, `TL-4` · ~1j

- **Objetivo:** las capacidades deterministas son reproducibles por definición: un acierto de caché es gratis **y correcto**.
- **Valor para el arquitecto:** reanálisis instantáneo tras un cambio pequeño, y factura menor.
- **Terminado cuando:** reejecutar un plan sobre un grafo sin cambios no ejecuta ninguna capacidad determinista y da el mismo sello.

### TL-7 · Servidor MCP del registro de capacidades
`P2` · `PENDIENTE` · PRD: **sí** · dep: `TL-3` · ~1,5j

- **Objetivo:** exponer el registro como servidor MCP — el cuarto consumidor del mismo manifiesto. **Restricción no negociable:** no expone capacidades con efecto `io` sin confirmación explícita.
- **Valor para el arquitecto:** ArchMuse entra en Claude Desktop y en su editor. Es canal de distribución, no funcionalidad.
- **Terminado cuando:** una capacidad se ejecuta desde fuera de la web sin escribir código nuevo, y un intento de invocar una capacidad `io` sin confirmación es rechazado.

### TL-9 · Contestar las preguntas del cuadro, sin escribir nada
`P0` · `HECHO (2026-08-19)` · PRD: no · dep: `TL-1` · ~0,5j

**Añadida el 2026-08-19, durante `TL-1`.** Carencia encontrada al usar la capacidad recién hecha: `plano.cuadro_de_superficies` sabía decir qué no podía calcular y **no tenía forma de recibir la respuesta**. Los datos que faltan —el espesor de muro, cuántas viviendas de este tipo hay, qué pieza del plano es cada espacio exterior— no están en el dibujo: están en la cabeza del arquitecto. Una capacidad que sólo sabe decir «no puedo» deja el cuadro a medias para siempre, y el objetivo `OP-1` promete un cuadro relleno.

- **Objetivo:** que la misma capacidad acepte `respuestas` y rehaga el cálculo incorporándolas, marcadas como **declaradas por el arquitecto** y no como calculadas por ArchMuse.
- **Valor para el arquitecto:** cierra el bucle pregunta → respuesta → cuadro completo **sin tocar todavía ningún fichero**. Puede recorrer el flujo entero antes de arriesgar su DXF.
- **Terminado cuando:** contestar una pregunta numérica deja su celda `CALCULADO` con `declarado_por_usuario: true`, y el resultado lista aparte qué celdas vienen de él.
- **Cómo quedó:** `respuestas` en el manifiesto, con los tres consumidores regenerados solos (`TL-3`); `[]` y `None` no se confunden; la limitación «no comprueba lo que el arquitecto declara, lo registra con esa procedencia» va declarada en el manifiesto y por tanto llega al modelo y al acta.

### TL-8 · Sustituir Nominatim
`P1` · `HECHO (2026-08-19)` · PRD: no · dep: — · ~1j

- **Objetivo:** pasar la geocodificación a Mapbox (ya hay token) o a instancia propia, y cachear Overpass agresivamente con plan para cuando no responda.
- **Valor para el arquitecto:** ninguno visible — y por eso hay que anotarlo aquí: **la política de uso de Nominatim prohíbe el uso comercial de su instancia pública**. Es un bloqueante legal antes de **cobrar**, no antes de demostrar.
- **Terminado cuando:** ninguna llamada del producto va a `nominatim.openstreetmap.org`, y Overpass caído degrada con mensaje en vez de romper.
- **Cómo quedó (2026-08-19):** `analyzer/sitio.py` geocodifica con **Mapbox** (v6, y entiende también la forma v5), acotando a España y limitando resultados en el servidor porque la cuota la paga ArchMuse. **Sin `MAPBOX_TOKEN` no hay repliegue a Nominatim**: se lanza `GeocodificacionNoConfigurada` y `/api/geocodificar` responde **501, no 502** — «esto no está montado aquí» y «vuelve a intentarlo» son dos conversaciones distintas. `tests/test_geocodificacion_y_overpass.py` vigila que el dominio prohibido no reaparezca por ninguna puerta. La mitad de Overpass ya estaba resuelta (espejos, fallo aislado por consulta, `entorno_consultado=False` cuando hay errores); lo que faltaba era el test que lo sujeta, y ya está.
- **Pendiente de verificar con token real:** el parser se ha probado contra las dos formas documentadas de respuesta, pero **nadie ha hecho aún una llamada real a Mapbox** desde este cambio: hace falta un `MAPBOX_TOKEN` válido y ejecutar `ARCHMUSE_TEST_RED=1 python tests/test_sitio.py`. Hasta entonces, la sustitución está probada contra fixtures, no contra el servicio.

---

## 6. Memoria y contexto de proyecto

### ME-1 · La memoria de proyecto sale de ficheros a Postgres
`P1` · `PENDIENTE` · PRD: no · dep: `INF-2`, D-6 decidida · ~1,5j

- **Objetivo:** `agente/memoria.py` guarda hoy JSONL append-only en disco. Conservar la interfaz y cambiar el sustrato, sin perder el orden ni la procedencia.
- **Valor para el arquitecto:** su proyecto deja de vivir en un portátil.
- **Terminado cuando:** la suite de memoria pasa contra Postgres y una memoria en ficheros se migra sin perder una declaración.
- **Bloqueada por:** D-6.

### ME-2 · `graph_versions` append-only con sello verificado
`P0` · `PENDIENTE` · PRD: no · dep: `INF-2` · ~1,5j

- **Objetivo:** cada versión sellada se escribe como fila nueva —nunca `UPDATE`— con `sello_sha256`, versión del motor y versión del corpus. **`UPDATE` y `DELETE` revocados a nivel de base de datos**, no por convención. Incluye decidir la política de retención antes de que la tabla crezca.
- **Valor para el arquitecto:** es lo que enseña a su aseguradora dos años después. Sin esto, ArchMuse es una app que rellena tablas.
- **Terminado cuando:** un `UPDATE` con el usuario de la aplicación falla por permisos; guardar dos veces crea dos filas y la primera queda intacta.
- **Separada de `DOC-1` el 2026-08-19 (decisión de Pablo).** Vivía como dependencia de `DOC-1`, pero son dos promesas distintas: `DOC-1` es que la traza sea correcta y legible *en el momento de la respuesta* (eso ya funciona, sin `ME-2`, y ahí se cierra); `ME-2` es que ArchMuse **conserve** esa traza por su cuenta, sellada, para poder volver a consultarla años después sin depender de que el arquitecto la guardara él mismo. Resolverla "de rebote" dentro de DOC-1 habría colado una decisión de arquitectura grande (persistencia en Postgres) dentro del cierre de una tarea que no la necesitaba.
- **Por qué sigue sin tocarse:** depende de qué stack de persistencia use ArchMuse — hoy `analyzer/storage.py` es SQLite; `docs/design/2026-08-18-plan-de-migracion.md` describe la misma tarea como `V1-2`, sobre Postgres, dentro de un plan marcado **"propuesta, no aprobada"** (salvo su primera pieza, `F0-1`, que sí está cerrada). Construir `ME-2` sin esa decisión de stack tomada es construir sobre una base que puede cambiar entera debajo. Se queda en el backlog, `P0`, a la espera de esa decisión — no de más trabajo de DOC-1.

### ME-3 · Conflictos de requisitos, visibles y resolubles
`P1` · `PARCIAL` · PRD: no · dep: `ME-1` · ~1j

- **Objetivo:** `memoria.conflictos()` ya los detecta y hace mandar al más reciente sin elegir en silencio. Falta que el arquitecto pueda **resolverlos**: cuál vale, por qué, y que la decisión quede sellada.
- **Valor para el arquitecto:** el cliente dijo tres dormitorios en marzo y cuatro en agosto. ArchMuse no decide por él, pero tampoco lo deja pasar.
- **Terminado cuando:** un conflicto sin resolver bloquea el entregable que depende de él, y resolverlo queda registrado con autor y fecha.

### ME-4 · Memoria de estudio: las convenciones del cliente
`P2` · `PENDIENTE` · PRD: **sí** · dep: `SEG-2` · ~2j

- **Objetivo:** nomenclatura de capas, formato de cuadro, criterios habituales del estudio, como **datos estructurados revisables y editables por el cliente** — nunca como embeddings.
- **Valor para el arquitecto:** ArchMuse encaja cada vez mejor en su forma de trabajar. Es la retención de `MOAT_ANALYSIS.md`.
- **Terminado cuando:** el cliente puede ver y corregir todo lo que ArchMuse «cree» sobre su forma de trabajar, y eso cambia el resultado de una ejecución.

### ME-5 · Resumen tipado del grafo para el planificador
`P0` · `HECHO (2026-08-19)` · PRD: no · dep: — · ~1j

- **Objetivo:** el planificador **nunca ve el grafo completo**: ve qué rutas están `KNOWN`, cuáles `UNKNOWN`, y los manifiestos en orden determinista, en el prefijo cacheado.
- **Valor para el arquitecto:** coste y latencia bajos, y ningún dato de su proyecto viajando al modelo sin motivo.
- **Terminado cuando:** el resumen tiene tamaño acotado independientemente del tamaño del proyecto, y el orden de manifiestos es estable entre ejecuciones (si no, la caché no acierta nunca y el planificador se encarece en silencio).
- **Cómo quedó (2026-08-19):** `agente/contexto.py`. Se acota **por estructura, no truncando**: las claves que alguna Skill exige van una a una (su número lo fija el catálogo, no el proyecto) y el resto se agrega por espacio de nombres, diciendo cuántas hay. Probado con 10.000 atributos: el resumen no llega al doble del de 20. Los valores del proyecto **no viajan al modelo**, sólo los estados. `prefijo_cacheable()` separa la mitad estable de la variable.

---

## 7. BIM / IFC

### BIM-1 · Importador de IFC a atributos con procedencia
`P2` · `PENDIENTE` · PRD: **sí** · dep: `TL-3` · ~2j

- **Objetivo:** `bim/lector_ifc.py` ya lee espacios y cantidades. Falta que lo leído entre al grafo como `Atributo` con `origen=observado` y la entidad IFC concreta como procedencia.
- **Valor para el arquitecto:** deja de tener que redibujar en DXF lo que ya modeló.
- **Terminado cuando:** un IFC exportado por el propio repositorio entra al grafo y cada superficie dice de qué `IfcSpace` salió.

### BIM-2 · Contraste IFC ↔ declarado ↔ DXF
`P2` · `PENDIENTE` · PRD: **sí** · dep: `BIM-1` · ~2j

- **Objetivo:** detectar discrepancias entre lo que dice el modelo, lo que declaró el cliente y lo que hay en el plano, y **presentarlas como discrepancias, no elegir una**.
- **Valor para el arquitecto:** encuentra el error de coordinación que hoy aparece en obra.
- **Terminado cuando:** una superficie que difiere más del umbral entre las tres fuentes produce un hallazgo con las tres cifras y sus tres orígenes.

### BIM-3 · Mover la escritura de IFC dentro de `bim/`
`P3` · `PENDIENTE` · PRD: no · dep: `BIM-1` · ~1j

- **Objetivo:** `analyzer/ifc_export.py` (~300 líneas probadas) pasa a `bim/`, manteniendo la regla de que `bim/` no importa `agente/` ni `analyzer/`.
- **Valor para el arquitecto:** ninguno directo. Es higiene de frontera.
- **Terminado cuando:** los tests de exportación pasan sin cambios y la regla de dependencia sigue vigilada.
- **Nota:** mover hoy 300 líneas probadas no gana nada. Se hace cuando el vertical BIM lo pida.

### BIM-4 · Robustez contra IFC de software real
`P3` · `PENDIENTE` · PRD: no · dep: `BIM-1` · ~2j

- **Objetivo:** ficheros exportados por Revit y ArchiCAD reales, con sus rarezas (`IfcRelAggregates` vs `IfcRelContainedInSpatialStructure`, cantidades ausentes, unidades exóticas), más límites de tamaño y memoria.
- **Valor para el arquitecto:** que funcione con **su** fichero, no con el de laboratorio.
- **Terminado cuando:** tres IFC de origen distinto se leen o fallan con `ok=False` y motivo — **nunca con un número inventado**.

---

## 8. Revit / AutoCAD

### CAD-1 · La prueba del plugin, ejecutada de verdad
`P1` · `HECHO (2026-08-19)` · PRD: no · dep: `TL-3` · ~0,5j

- **Objetivo:** un CLI que invoque una capacidad cualquiera **sin HTTP, sin Flask, sin FastAPI**, con el mismo manifiesto. No es un plugin: es la prueba de que el plugin sería posible.
- **Valor para el arquitecto:** ninguno hoy. Es el seguro de que el día que quiera ArchMuse dentro de Revit, no haya que reescribir el motor.
- **Terminado cuando:** `python -m archmuse.invocar territorial.resolver_ambito --municipio Madrid` devuelve el mismo resultado que la API, y el test que prohíbe importar transporte en `agente/` sigue verde.
- **Cómo quedó (2026-08-19):** el comando es `python -m agente.invocar territorial.resolver_ambito --municipio Madrid` — no se crea un paquete `archmuse` sólo para esto; el punto de la tarea es que el motor responda sin transporte, y `agente/` ya es ese motor. Los argumentos se derivan del esquema, así que una capacidad nueva aparece en el CLI sin tocar el fichero. Trae además `--openapi` (el contrato) y `--comprobar` (la coherencia de `TL-3` a un comando). `ok: false` sale con código 1 **conservando la pregunta**: tratarlo como excepción perdería lo único que hace útil esa respuesta.

### CAD-2 · Contrato de invocación estable y versionado
`P2` · `HECHO (2026-08-19)` · PRD: no · dep: `CAD-1` · ~1j

- **Objetivo:** semver del manifiesto con política escrita: qué cambio es compatible, cuál obliga a mayor, y cómo un invocador antiguo sigue funcionando.
- **Valor para el arquitecto:** su plugin no deja de funcionar el martes porque alguien añadió un parámetro.
- **Terminado cuando:** un cambio incompatible sin subir la mayor rompe un test, y un plan guardado con una versión antigua sigue ejecutándose o falla con un mensaje claro.
- **Cómo quedó (2026-08-19):** `agente/compatibilidad.py` con la política escrita y ejecutable: `huella()` reduce cada capacidad a **su contrato** —dejando la prosa fuera, para que reescribir lo que lee el modelo no obligue a nadie a actualizar un complemento instalado— y `revisar()` la compara con `tests/fixtures/contratos_de_capacidad.json`. Un cambio de contrato sin subir el tramo que toca pone la suite en rojo **diciendo qué cambió y qué tramo tocaba**. El caso que más importa: **añadir un efecto es MAYOR**, porque una capacidad que ayer era pura y hoy escribe un fichero se ejecutaría bajo una autorización concedida para otra cosa. Y `Registro.buscar` acepta `id@version`: la versión exacta y cualquier posterior de la misma mayor se ejecutan; otra mayor se **rechaza** con las dos versiones en el mensaje, porque ejecutar «lo más parecido» reescribiría en silencio lo que se hizo aquel día.

### CAD-3 · Complemento de Revit / AutoCAD
`APLAZADO` · `PENDIENTE` · PRD: **sí** · dep: `CAD-2`, OP-1 en manos de estudios reales · ~10j+

- **Objetivo:** el complemento real, con su instalación, su firma y su ciclo de actualización.
- **Valor para el arquitecto:** ArchMuse donde ya trabaja, que es donde se gana la distribución.
- **Terminado cuando:** un arquitecto ejecuta una capacidad desde Revit sin abrir un navegador.
- **Por qué aplazado:** construir el envoltorio antes de tener capacidades que merezcan invocarse es hacer el lazo de un regalo vacío. Y son diez jornadas de un ecosistema (C#, instaladores, versiones de Revit) que no se parece a nada del repositorio actual.

---

## 9. Normativa verificable

> **Esta sección es el camino crítico del negocio.** Todo lo demás de este backlog vale menos sin ella, y ninguna decisión de arquitectura la desbloquea. Es C5.

### NOR-1 · Encargo del curador colegiado
`P0` · `PARCIAL (2026-08-19)` · PRD: no · dep: — · lo técnico hecho; falta contratar

- **Objetivo:** el encargo escrito —alcance, prioridad de Documentos Básicos, cadencia, revisión, tarifa— y la ficha de transcripción probada, de modo que un colegiado pueda aceptarlo el lunes. Las dos piezas ya existen en borrador (`docs/design/2026-08-18-encargo-curador-normativo.md`, `...-ficha-de-transcripcion-normativa.md`).
- **Valor para el arquitecto:** es literalmente todo. Sin corpus, ArchMuse no puede verificar normativa.
- **Terminado cuando:** un colegiado que no ha hablado con Pablo transcribe una segunda regla siguiendo la ficha **sin ayuda**, y `normativa/` la resuelve de punta a punta.

**Hecho el 2026-08-19 — lo que impedía el «sin ayuda»:**

- **`scripts/validar_corpus.py`.** El curador comprueba su propio trabajo y obtiene el fichero, la regla y el motivo con el número de validación. Antes las diecisiete validaciones existían pero **sólo se invocaban desde los tests**: la única forma de saber si un YAML recién escrito estaba bien era preguntarle a un programador, lo que convertía a Pablo en el cuello de botella del único trabajo que no puede tenerlo. El guion enumera además los tres criterios humanos que no puede ver, para no enseñar a confiar en él de más.
- **Estado de cobertura `transcrito_sin_firmar`** (`normativa/manifiesto.py`). Es el estado en el que vive toda regla entre transcribirla y firmarla — o sea, el estado normal durante todo el trabajo que queda. No existía, y al declarar la primera regla real había que elegir entre dos mentiras: `ausente` niega un trabajo hecho y en disco, y `parcial` es **afirmable**, con lo que ArchMuse habría evaluado seguridad contra incendios con una regla que nadie ha revisado.
- **Validación 18** (`validar_firma_de_lo_declarado`). Rechaza al cargar cualquier promoción a `completo`/`parcial` mientras alguna regla de esa materia conserve `pendiente_firma_colegiado`. Convierte el orden de trabajo en algo que no se puede saltar por descuido: transcribir → declarar sin firmar → firmar → retirar la etiqueta → promover.
- **Defecto real corregido en la validación 17.** Su segundo recorrido —«hay reglas en disco sin declarar»— vivía **dentro** del bucle sobre lo declarado, así que un ámbito sin entrada en el manifiesto no se miraba nunca. El corpus de producción estaba exactamente en ese caso (una regla en disco, `cobertura: []`) y la validación respondía que todo cuadraba. Es el error que comete quien **empieza** a transcribir, es decir, todo el trabajo que queda por delante.
- **El manifiesto de cobertura dice la verdad** por primera vez: declara la regla que hay, la declara sin firmar, y por tanto ArchMuse sigue bloqueando por falta de cobertura de seguridad contra incendios — que es lo correcto hasta la primera firma.

**Lo que sigue pendiente, y es el 100 % de lo que queda:** que un colegiado acepte el encargo. Es **contratación, no programación**, y ninguna tarea de este backlog la sustituye. El corpus tiene una regla, sin firmar; ArchMuse no puede verificar ni una sola norma.

- **No depende de nada y no bloquea nada de V1. Arranca hoy, en paralelo.**

### NOR-2 · Primer Documento Básico completo en el corpus
`P0` · `PENDIENTE` · PRD: no · dep: `NOR-1` · continuo

- **Objetivo:** DB-SI entero transcrito, validado y resolviendo. No una selección: **completo**, para poder decir «este DB lo cubrimos» sin asteriscos.
- **Valor para el arquitecto:** la primera frase honesta de venta que ArchMuse puede decir.
- **Terminado cuando:** toda regla del DB-SI que el producto invoca sale del corpus con su cita al BOE, y la cobertura declarada (`NOR-5`) dice «DB-SI: completo».

### NOR-3 · Endurecer la validación del corpus
`P0` · `HECHO (2026-08-19)` · PRD: no · dep: — · ~0,5j

- **Objetivo:** `normativa/validacion.py` regla 7 acepta **cualquier cadena** como nivel de repliegue. Eso es lo que dejó pasar una regla piloto cuyo repliegue no casaba con ningún eje y por tanto no se resolvía nunca. Validar contra los ejes declarados.
- **Valor para el arquitecto:** una regla mal transcrita falla al cargar, en vez de quedarse muda y parecer que «no aplica».
- **Terminado cuando:** una regla con un nivel de repliegue inexistente es rechazada por el validador, con el nombre del nivel en el mensaje.
- **Es media jornada y cierra un defecto real ya observado. Hacer pronto.**

### NOR-4 · La versión del corpus viaja en el sello
`P1` · `PENDIENTE` · PRD: no · dep: `ME-2`, `NOR-2` · ~1j

- **Objetivo:** cada versión sellada del grafo registra qué corpus estaba vigente. Y una regla derogada no invalida en silencio un análisis antiguo: lo marca como emitido bajo la norma anterior.
- **Valor para el arquitecto:** puede defender un análisis de hace dos años **con la norma que estaba vigente entonces**, que es exactamente lo que le preguntarán.
- **Terminado cuando:** dos análisis del mismo proyecto con corpus distintos son distinguibles, y el acta dice cuál.

### NOR-5 · Cobertura declarada: qué se puede verificar hoy
`P1` · `PENDIENTE` · PRD: no · dep: `NOR-2` · ~1j

- **Objetivo:** una respuesta normativa **declara su propia cobertura**: qué DB están, cuáles parcialmente, cuáles no, y qué ámbitos territoriales.
- **Valor para el arquitecto:** el silencio deja de significar «cumple». Es la diferencia entre una herramienta que sobrevende y una en la que se puede confiar.
- **Terminado cuando:** una consulta sobre un DB ausente responde «sin cobertura» con esas palabras y no devuelve `no_aplica`, y la diferencia está probada.

### NOR-6 · Recuperación acotada sobre el corpus curado
`P2` · `PENDIENTE` · PRD: no · dep: `NOR-2`, `INF-2` · ~1,5j

- **Objetivo:** búsqueda de texto completo **sobre el corpus curado**, nunca sobre PDF crudos. Dos usos legítimos: que el arquitecto vea el articulado que respalda un hallazgo, y que el curador no duplique lo ya transcrito.
- **Valor para el arquitecto:** lee el artículo entero sin salir a buscarlo.
- **Terminado cuando:** la búsqueda localiza y muestra articulado y **no puede producir una cifra**, verificado por test.

### NOR-7 · Ordenanzas municipales
`P3` · `PENDIENTE` · PRD: **sí** · dep: `NOR-2` · continuo

- **Objetivo:** el nivel municipal del motor territorial, que existe y está vacío. Empezando por los municipios donde estén los primeros clientes, no por los grandes.
- **Valor para el arquitecto:** la normativa que realmente le bloquea un proyecto suele ser la municipal, no la estatal.
- **Terminado cuando:** un municipio tiene su ordenanza resolviendo y el resto declara `sin_cobertura` sin fingir.

---

## 10. Generación de trabajo profesional

### DOC-1 · Acta de procedencia legible por un arquitecto
`P0` · `HECHO (2026-08-19)` · PRD: **sí** · dep: — · ~3j

- **Objetivo:** `agente/acta.py` ya la levanta y deriva las limitaciones de los manifiestos. Lo que falta es **que se entienda**: una página, con el porqué a un clic, en el lenguaje de un arquitecto y no de un ingeniero.
- **Valor para el arquitecto:** es el diferencial entero. Sin el acta, ArchMuse es una app que rellena una tabla, y eso lo hace cualquiera.
- **Terminado cuando:** para tres celdas al azar de un cuadro relleno se puede seguir el acta hasta la entidad concreta del DXF, y para una celda `N/D` se lee el motivo. **El criterio de aceptación es de arquitecto, no de ingeniero:** lo valida la voz del arquitecto veterano antes de darse por buena.
- **Riesgo A4:** es la tarea más fácil de recortar bajo presión de tiempo y la única que hace este producto distinto de una app cualquiera. No se recorta.
- **`ME-2` retirada de aquí como dependencia (decisión de Pablo, 2026-08-19).** DOC-1 se cierra con **traza correcta y legible en el momento de la respuesta** (celda → línea del acta → entidad del DXF): eso ya funciona hoy y no necesita persistencia para pasar la validación de un arquitecto veterano. La promesa que sí necesitaría `ME-2` — que ArchMuse conserve esa traza por su cuenta y se pueda volver a consultar dos años después, sin que el arquitecto tuviera que guardarla él mismo — queda **fuera del criterio de aceptación de DOC-1**, no resuelta ni descartada: es la ficha `ME-2` la que la lleva ahora, sola. Ver su nota.
- **Estado real (verificado 2026-08-19):** ni `agente/acta.py` ni `analyzer/acta_legible.py` ni los endpoints que devuelven un acta (`/api/acta-legible`, `/api/copiloto`, `/api/memoria-superficies`) llaman a `analyzer/storage.py` — el acta se calcula al vuelo en cada petición y no se guarda en ningún sitio. `Acta.sello` (sha256) es determinista, y eso es lo único que `F0-1` ya cerró; la persistencia sigue sin construir (es `ME-2`, aparte).
- **Cerrada (2026-08-19, noche 14).** Pablo validó el criterio de arquitecto veterano sobre el borrador (§ noche 8-13 de `PROGRESS.md`) y pidió el último eslabón que faltaba: cada bloque desplegado explicaba el motivo en prosa pero no señalaba la entidad concreta del DXF. Añadido sin tocar medición ni el resto de la interfaz: `analyzer/acta_legible.py::clasificar()` ahora lee `datos` (la sección "Qué se ha establecido" del acta) y, para el caso conocido, muestra "Pieza: X · Capa: Y" por cada pieza implicada — rótulo y capa ya estaban en el acta, sólo faltaba mostrarlos. Los `TODO` (sin caso real) llevan la misma explicitud en vez de silencio. 2 tests nuevos en `tests/test_acta_legible.py` (16/16), regresión 46/46 sobre los ficheros relacionados. Commit `7ac7646`, sin push (ver `INF-1`/`D-9`).

### DOC-2 · Los entregables del vertical: DXF relleno y cuadro en PDF
`P0` · `HECHO (2026-08-19)` · PRD: no · dep: `TL-2`, `DOC-3` · ~1j

- **Objetivo:** los dos ficheros que el arquitecto se lleva, con el acta viajando con ellos.
- **Valor para el arquitecto:** trabajo terminado, no una pantalla que hay que copiar a mano.
- **Terminado cuando:** ambos se descargan, ambos llevan la marca y el acta, y el original conserva su sha256.
- **Cómo quedó (2026-08-19):** `analyzer/cuadro_pdf.py` + la capacidad `plano.cuadro_en_pdf`. Los dos entregables salen con el mismo nombre y en la misma carpeta a propósito: en una carpeta con veinte ficheros, que el PDF que explica un DXF se llame igual es lo que evita enseñarle a un cliente el acta de otro plano. **La columna que importa del PDF no es la del número: es la última** — de dónde sale cada cifra, o por qué la celda está en blanco. Distingue «declarado por el arquitecto» de «calculado por ArchMuse» y de «ya estaba escrito en el DXF»: tres procedencias que en un acta no valen lo mismo. Los estados van en castellano de arquitecto (quien lo lee no sabe qué es un `CERO_REAL`), la lista de «lo que NO comprueba» se deriva de los manifiestos ejecutados, y la huella SHA-256 del original va impresa para que «tu plano no se ha tocado» sea comprobable. Si el PDF falla, **el DXF ya escrito no se pierde**: se declara con motivo.
- **Lo que queda para `DOC-1`:** el acta a nivel de ejecución (qué Skills, qué versiones, qué sello) sigue saliendo por consola y en JSON. El PDF lleva el acta **a nivel de celda**, que es la que el arquitecto necesita para decidir si se fía; juntarlas en un solo documento es trabajo de `DOC-1`.

### DOC-3 · Marca de borrador, sin opción de desactivarla
`P0` · `HECHO (2026-08-19)` · PRD: no · dep: `TL-2` · ~0,5j

- **Objetivo:** todo artefacto sale marcado como **borrador para revisión de un colegiado**, sin excepción y **sin opción de configuración que lo quite**.
- **Valor para el arquitecto:** protege la frontera legal del producto: ArchMuse asesora, no firma. Y le protege a él.
- **Terminado cuando:** DXF y PDF llevan la marca, y un test demuestra que no existe forma de generarlos sin ella.
- **Cerrada (2026-08-19):** faltaba la mitad del DXF y ya está. `analyzer/marca_borrador.py::estampar_dxf` pone la leyenda en **su propia capa** (`00 ARCHMUSE BORRADOR`): el arquitecto puede apagarla para imprimir sin borrar nada suyo, y las consultas que el producto ya hace sobre `00 CUADROS` siguen viendo lo mismo. Se estampa en el único sitio que guarda un DXF, así que **no hay camino que produzca una copia sin ella** — y hay un test que recorre `analyzer/` buscando cualquier módulo nuevo que guarde un DXF sin pasar por la marca.
- **Cómo va (2026-08-19): la mitad de PDF, HECHA.** `analyzer/marca_borrador.py` estampa la leyenda en **todas** las páginas de `pdf_report` y `dossier_pdf` — no sólo en la primera, que es la que nadie mira cuando el documento circula suelto. La leyenda es **una sola**: `agente/acta.py` la importa de allí en vez de repetirla. `tests/test_marca_borrador.py` recorre `analyzer/` y se pone rojo si aparece un generador de PDF que no pase por ella, y comprueba por AST que no exista ningún parámetro ni variable de entorno para desactivarla. **Falta la mitad del DXF**, que depende de `TL-2` (PRD escrito, pendiente de aprobación). Hallazgo del camino: los PDF del producto actual **no llevaban ninguna marca** — C3 estaba incumplido en lo que ya se entrega, no sólo en lo que viene.
- **Es C3 literal.**

### DOC-4 · Redactor que solo cita atributos ya calculados
`P2` · `PENDIENTE` · PRD: **sí** · dep: `ME-2` · ~1,5j

- **Objetivo:** la única capacidad de naturaleza `llm` que produce prosa. Con la regla dura de que **no toca ninguna cifra**: las recibe calculadas y las redacta. El detector de cifras sin respaldo de `agente/respaldo.py` es su portero.
- **Valor para el arquitecto:** texto presentable sin el riesgo de que el modelo invente un número por el camino.
- **Terminado cuando:** un intento de emitir una cifra que no está en el grafo falla la verificación, y está probado.

### DOC-5 · Memoria justificativa y dossier de entrega
`P3` · `PENDIENTE` · PRD: **sí** · dep: `SK-7`, `NOR-2`, `DOC-4` · ~4j

- **Objetivo:** el documento largo, y el paquete de entrega coherente y sellado junto.
- **Valor para el arquitecto:** el trabajo más tedioso del proyecto.
- **Terminado cuando:** el documento se genera, va marcado como borrador, y cada cifra rastrea a su atributo.
- **Ver OP-6:** es el objetivo que más se va a pedir y el más peligroso de adelantar. No empieza sin `NOR-2`.

---

## 11. Seguridad, aprobación y trazabilidad

### SEG-1 · Aprobación explícita antes de un efecto
`P0` · **HECHO (2026-08-20)** · PRD: no · dep: `TL-2` · ~1j

- **Objetivo:** el portero de efectos existe en `agente/efectos.py` y rechaza lo no autorizado. El paso de producto (428 + `solicitud()` en el backend, `fetchConAutorizacion` reintentando en el frontend) se cerró el 2026-08-19/20 para las tres puertas de medición (`/api/acta-legible`, `/api/memoria-superficies`, `/api/preguntar`), y el 2026-08-20 (Bloque 2 de `docs/design/2026-08-20-reorientacion-estrategica-v1.md`) se extendió al único punto de escritura que quedaba alcanzable por HTTP sin cubrir: `revision.coherencia_del_plano` dentro de `/api/preguntar`. Auditado el resto del código HTTP-reachable (`/api/copiloto` sólo toca `proyecto.ajustar_programa`, sin efectos; `/api/exportar-cuadro-superficies-completo` usa `analyzer/` directamente, nunca `agente.Ejecutor`, así que el mecanismo de `SEG-1` no aplica ahí) y no queda ningún punto de escritura de `agente/` alcanzable desde la web sin pasar por esta pantalla.
- **Valor para el arquitecto:** nada le ocurre a sus ficheros ni a su presupuesto sin que lo haya visto antes.
- **Terminado cuando:** una ejecución con efecto `io` se detiene, muestra el efecto declarado en el manifiesto, y sin confirmación no escribe ni un byte. ✓

### SEG-2 · `tenant_id` en el núcleo, RLS y test de ataque
`P1` · `PENDIENTE` · PRD: no · dep: `SEG-3`, `INF-2` · ~2,5j

- **Objetivo:** un objeto de contexto (`tenant_id`, `user_id`, `run_id`) que atraviesa **toda** invocación de capacidad; RLS en Postgres como segunda capa; un test que falle si alguna consulta carece de predicado de tenant; y un test que **ataque**: autenticado como A, intentar leer datos de B en cada endpoint.
- **Valor para el arquitecto:** el plano de su cliente no lo ve otro estudio. Es la primera pregunta de toda venta.
- **Terminado cuando:** una consulta sin predicado devuelve cero filas por RLS, y el test de ataque falla en todos los endpoints.
- **Por qué dos capas:** el día que la superficie sea un plugin de Revit, el middleware de Next no está. Es C1.

### SEG-3 · Identidad gestionada: organizaciones, invitaciones, roles
`P1` · `PENDIENTE` · PRD: **sí** · dep: `INF-2`, D-1 decidida · ~2j

- **Objetivo:** Clerk o WorkOS, con los cuatro roles (propietario, arquitecto, colaborador, **lectura**). Comparativa escrita antes de elegir, con región europea y DPA como criterios de primer orden.
- **Valor para el arquitecto:** invita a su equipo. Y el rol de lectura abre el segundo comprador: el promotor que quiere cuantificar riesgo.
- **Terminado cuando:** dos correos crean dos estudios; una invitación aceptada da acceso al estudio correcto **y solo a ese**.
- **Bloqueada por:** D-1 (residencia de datos).

### SEG-4 · Telemetría de tokens, coste y tope de gasto
`P0` · `HECHO (2026-08-19)` · PRD: no · dep: — · ~1,5j

- **Objetivo:** en `ia/cliente.py` —único sitio donde se construye el cliente— registrar por llamada: módulo, modelo, tokens de entrada, de salida, de lectura de caché, duración y coste. Tope acumulado configurable que corta con error explícito. **Solo métricas, nunca texto de prompt:** son datos del proyecto de un cliente.
- **Valor para el arquitecto:** indirecto — pero hoy es **imposible** responder cuánto cuesta un usuario, y sin eso no hay precio defendible.
- **Terminado cuando:** un análisis completo devuelve una cifra en euros desglosada por punto de llamada, y ningún prompt aparece en el registro.
- **Cómo quedó (2026-08-19):** `ia/uso.py` acumula por punto de llamada y por modelo; `desglose_de_registro()` lo reconstruye del JSONL cuando el análisis lo hizo otro proceso; `python scripts/coste_de_uso.py` lo imprime. **Los euros exigen declarar `ARCHMUSE_EUR_POR_USD`**: la tarifa de Anthropic está en dólares y un cambio inventado da una cifra que parece contable sin serlo. Sin cambio declarado el desglose sale en USD, nunca convertido a ojo.

### SEG-5 · Bitácora exportable como registro defendible
`P1` · `PENDIENTE` · PRD: no · dep: `ME-2`, `DOC-1` · ~1j

- **Objetivo:** que el arquitecto pueda **exportar** el registro completo de un proyecto: qué se ejecutó, con qué versión, contra qué corpus, con qué resultado, sellado.
- **Valor para el arquitecto:** es lo que enseña a su aseguradora o a un juzgado. Y es lo que hace que irse de ArchMuse no signifique perder el historial — lo cual, contraintuitivamente, es lo que hace que se quede.
- **Terminado cuando:** el registro exportado permite reconstruir el resultado sin acceso al sistema, y su sello se verifica desde fuera.

---

## 12. Infraestructura y producto SaaS

### INF-1 · CI en GitHub Actions con la suite completa, y árbol limpio
`P0` · `PARCIAL, mucho más avanzada de lo que creía este backlog` · PRD: no · dep: — · ~1,5j

- **Objetivo:** workflow que en cada push instale las dependencias fijadas y ejecute `pytest` entero (~8 min hoy), con marcador `lento` y un job nocturno para las pruebas que necesitan red, IA o el DXF real. Y de paso, lo que ensucia el clon: `JarvisApp.py` y su entorno a su propio repositorio; `cloudflared_tunnel.log` (731 KB), `flask*.log`, `venv/` y `.venv-jarvis/` fuera del árbol versionado.
- **Valor para el arquitecto:** indirecto y enorme — 24.584 líneas de test que hoy solo corren cuando alguien se acuerda.
- **Terminado cuando:** un PR con un umbral cambiado a mano pone CI en rojo, y un clon limpio instala y pasa la suite.
- **Presupuestar que el primer arranque no sale verde** (rutas Windows, `\r\n`, `ifcopenshell`). Encontrar eso **es** el beneficio.
- **Corrección importante (2026-08-20):** este backlog llevaba desde el 19-ago creyendo que `.github/workflows/` "existe sin ejecutar" y que la tarea estaba "bloqueada en el último paso... esperando un push". **Falso, verificado con `gh run list`:** el workflow lleva ejecutándose en CADA push desde al menos las 09:57 del 20-ago (ocho pushes de esta sesión, todos con la suite corriendo de verdad en Linux) -- **y todos en rojo, sin que nadie lo hubiera mirado.** Nadie comprobó el estado real; el backlog describía una tarea bloqueada que en realidad llevaba horas produciendo señal, ignorada.
- **Lo que estaba rojo de verdad, encontrado y arreglado el mismo día (2026-08-20):** `tests/test_entorno_3d.py` no mockeaba `geometria_parcela_por_coordenadas` en ninguna de sus tres secciones que la disparan (3.2, 3.3, 4) -- en CI (con salida a internet real, a diferencia de este entorno de desarrollo) eso golpeaba Catastro de verdad en cada push, con fallos intermitentes según cómo respondiera la red esa vez. Arreglado con mocks explícitos en las tres secciones. El guardián de capitalización (hallazgo 4 del informe de test) también estaba fallando en CI (Linux, sensible a mayúsculas) hasta el `skipif` de esta misma sesión.
- **Estado real tras arreglar ambos:** CI pasa **exactamente igual que en local** -- 2 fallos, los mismos dos guardianes C4 deliberados (`assert 13 <= 12`, ver `D-12`), que están rojos A PROPÓSITO hasta que Pablo decida el techo. No es un fallo de infraestructura: es la señal que ese guardián existe para dar.
- **Lo que queda, y es una decisión de Pablo, no técnica:** ¿el criterio de "terminado" de esta tarea exige status verde LITERAL (lo que obligaría a marcar los guardianes C4 como `xfail` esperado, ocultando la cuenta atrás de D-12 dentro de CI), o el criterio real es "sin fallos que no sean los ya conocidos y deliberados" (que es donde está hoy)? No se decide aquí -- tocar cómo CI trata un guardián de C4 es territorio de D-12, fuera de alcance sin su decisión explícita.

### INF-2 · Postgres: el esquema mínimo del vertical
`P0` · `PENDIENTE` · PRD: no · dep: — · ~2j

- **Objetivo:** proveedor gestionado, **región UE decidida antes que proveedor**. Solo las tablas que el vertical usa: `tenants`, `users`, `memberships`, `projects`, `graph_versions`, `runs`, `run_steps`, `artifacts`. Cambiar el driver de `analyzer/storage.py` conservando su interfaz.
- **Valor para el arquitecto:** su proyecto sobrevive a que se apague un portátil.
- **Terminado cuando:** la suite pasa contra Postgres, y una base SQLite con proyectos reales se migra sin pérdida.
- **Barato porque `storage.py` documenta su propio invariante:** hay un único escritor y `analyzer/` no lo importa.

### INF-3 · Ficheros a almacenamiento de objetos
`P1` · `PENDIENTE` · PRD: no · dep: `INF-2` · ~1j

- **Objetivo:** DXF, PDF, IFC y GLB a S3/R2 con URL firmada de caducidad corta; `artifacts` guarda clave, tipo y qué versión del grafo lo produjo.
- **Valor para el arquitecto:** sus ficheros dejan de vivir dentro de una fila de base de datos.
- **Terminado cuando:** subir y descargar sin que la base guarde un byte del PDF, y una URL caducada devuelve 403.
- **Riesgo:** una URL firmada mal acotada expone el plano de un cliente. La tenencia se comprueba **antes** de firmar, ya en esta tarea.

### INF-4 · Cola en Postgres con `SKIP LOCKED` y worker
`P1` · `PENDIENTE` · PRD: no · dep: `INF-2` · ~2j

- **Objetivo:** worker aparte consumiendo `SELECT ... FOR UPDATE SKIP LOCKED`. Las ejecuciones dejan de vivir dentro de una petición HTTP. **Ni Redis ni Celery:** a este volumen, añadir un sistema es peor que usar el que ya hay.
- **Valor para el arquitecto:** puede cerrar la pestaña y volver. Hoy una llamada retiene uno de los 8 hilos hasta 15 minutos.
- **Terminado cuando:** 20 ejecuciones simultáneas; la API responde al instante con un identificador, ningún trabajo se procesa dos veces, y matar el worker a mitad recupera el trabajo.
- **Nota:** el ejecutor ya reanuda por checkpoint, y eso es justo lo que hace innecesaria la ejecución durable de un framework (D-4).

### INF-5 · FastAPI conviviendo con Flask, solo las rutas del vertical
`P1` · `PENDIENTE` · PRD: no · dep: `TL-3` · ~1,5j

- **Objetivo:** montar FastAPI junto a Flask detrás del mismo dominio, sirviendo **únicamente** las rutas del vertical, generadas desde el manifiesto. Las 40 rutas de `app.py` **no se tocan**.
- **Valor para el arquitecto:** nada de lo que usa hoy se cae.
- **Terminado cuando:** el vertical responde por FastAPI y el resto del producto sigue respondiendo por Flask, sin cambios en la SPA.

### INF-6 · Cliente TypeScript generado en CI
`P1` · `PENDIENTE` · PRD: no · dep: `INF-5` · ~1j

- **Objetivo:** generar el cliente TS desde el OpenAPI en CI y **fallar si difiere del comiteado**. Cero tipos del dominio escritos a mano.
- **Valor para el arquitecto:** menos errores tontos en la pantalla que usa.
- **Terminado cuando:** renombrar un campo de un modelo Pydantic pone CI en rojo.

### INF-7 · Next: shell, sesión y la pantalla del vertical
`P1` · `PENDIENTE` · PRD: **sí** · dep: `SEG-3`, `INF-6` · ~3j

- **Objetivo:** proyecto Next (App Router, TS estricto), sesión con cookie `httpOnly`, rutas protegidas en servidor, y **una** pantalla: subir DXF, escribir la intención, ver el plan y el progreso por capacidad, descargar los entregables y leer el acta. **Ni una línea de lógica de negocio**, con una regla de lint que lo impida.
- **Valor para el arquitecto:** es la mitad visible del producto, y donde se juega si entiende el acta.
- **Terminado cuando:** la pantalla completa el recorrido de punta a punta, y ninguna ruta de servidor importa nada salvo el cliente generado.

### INF-8 · Despliegue en la UE
`P1` · `PENDIENTE` · PRD: no · dep: `INF-4`, `INF-2` · ~2,5j

- **Objetivo:** contenedor Linux del núcleo (con `gunicorn`, que en Linux sí funciona), worker como proceso separado, frontend desplegado, secretos en gestor, región UE, y el túnel `cloudflared` retirado del camino del vertical.
- **Valor para el arquitecto:** puede usarlo sin que nadie le abra un túnel desde un portátil Windows.
- **Terminado cuando:** dominio propio con TLS sin túnel; matar el worker no tira la API; ningún secreto en el repositorio ni en la imagen.
- **Presupuestar que `ifcopenshell` y `mapbox_earcut` darán trabajo en la imagen.**

### INF-9 · Precio, medición y límites por plan
`P2` · `PENDIENTE` · PRD: **sí** · dep: `SEG-4`, `AG-3` · ~2j

- **Objetivo:** asiento por arquitecto con **verificación ilimitada** y generación/redacción **medida**. Alinea el precio con el valor (defensa profesional) y el coste con la parte cara.
- **Valor para el arquitecto:** paga por lo que le sirve y no subvenciona al usuario que genera plantas todo el día.
- **Terminado cuando:** un plan agotado degrada con mensaje claro en vez de fallar, y la cifra de consumo que ve el cliente coincide con la medida.
- **Ventaja estructural que conviene saber vender:** cada regla determinista que se añade **mejora el margen**, porque sustituye trabajo que un competidor puramente LLM paga por token.

---

## 13. Cola de trabajo

### 13.1 Lo hecho el 2026-08-19 (sesión autónoma)

Dieciséis tareas cerradas y una a medias. En orden de ejecución:

| Tarea | Qué quedó |
|---|---|
| `NOR-3` | La validación del corpus rechaza un nivel de repliegue inexistente **nombrándolo**, y también uno inalcanzable. Cierra el defecto real ya observado |
| `SEG-4` | Coste desglosado por punto de llamada y por modelo, en vivo y desde el registro. `scripts/coste_de_uso.py` |
| `TL-3` | Un manifiesto, tres consumidores, y la comprobación de que no se separan — recorriendo el registro |
| `CAD-1` | `python -m agente.invocar`: el motor responde sin transporte. La prueba del plugin, ejecutada |
| `ME-5` | `agente/contexto.py`: el planificador ve lo que decide y nada más, con tamaño acotado |
| `TL-1` | Tres capacidades de geometría. El registro pasa a 7, dentro del techo de C4 |
| `TL-9` | *(añadida durante `TL-1`)* Contestar las preguntas del cuadro, sin escribir nada |
| `TL-4` | Golden obligatorio por capacidad determinista, con test de política |
| `TL-8` | Fuera Nominatim, entra Mapbox. Bloqueante legal antes de cobrar, cerrado |
| `CAD-2` | Política de compatibilidad escrita y ejecutable; `id@version` en el registro para los planes guardados |
| `TL-2` | La escritura protegida del DXF del cliente. PRD aprobado por Pablo; sus tres condiciones son tests |
| `SK-1` | El procedimiento del vertical, con la verificación de suma **informativa** que pidió Pablo |
| `DOC-2` | El cuadro en PDF con el porqué de cada celda; los dos entregables viajan juntos |
| `AG-1` | El planificador tipado: una llamada, un DAG validado, y el plan enseñable antes de ejecutarlo |
| `AG-2` | El validador determinista: rechaza sin gastar, y cuando faltan datos la salida es la pregunta |
| `DOC-3` | **Cerrada:** faltaba la mitad del DXF, y la marca va ya en su propia capa |
| `INF-1` | **Parcial:** árbol limpio y workflow revisado. El último paso exige un push (ver D-9) |

Tres PRD escritos y pendientes de aprobación: `TL-2`, `AG-1`, `SK-1`. Son las tres piezas que faltan para que `OP-1` sea un entregable, y ninguna se implementa sin la firma de Pablo.

### 13.2 Lo que queda sin hacer teniendo las dependencias cerradas, y por qué

| Tarea | Por qué no |
|---|---|
| `NOR-1` | Es **contratación**, no programación. El encargo y la ficha están redactados; falta que un colegiado los acepte. **Sigue siendo lo más importante del backlog**, y sigue sin empezar |
| `INF-2` | Exige provisionar un Postgres gestionado y decidir la región antes que el proveedor. Sin credenciales, una sesión autónoma sólo podría escribir el esquema a ciegas |
| `INF-5` | Exige meter `fastapi` y `uvicorn` en `requirements.txt` y regenerar el lock, con consecuencias de despliegue que no se pueden verificar desde aquí. Ver `D-11` |
| `TL-5` | Cuatro jornadas que no acercan el primer vertical. Sigue siendo el aplazamiento más peligroso del plan (riesgo A3): anotado, no olvidado |
| `SK-5` | Bloqueada por `D-7`. **Ahora urge**: `SK-1` ya codifica criterio profesional —el orden de las comprobaciones, la tolerancia de la suma— y nadie lo ha firmado |
| `AG-3` | Necesita la tabla de coste **medida** por perfil. `SEG-4` da la maquinaria; falta ejecutar cargas reales y leer las cifras |

### 13.4 Lo hecho el 2026-08-19 (segunda sesión: el plano real y el corpus)

**Sobre `v2s.dxf`, el plano real del cliente.** El flujo completo se ejecutó de punta a punta y **entregó**: DXF relleno (18 textos añadidos, 0 perdidos), PDF explicativo de 2 páginas, acta, y el original con su sha256 intacto (`37e982b4…`, idéntico antes y después). La celda que el plano ya traía (`VT1 /3`) no se sobrescribió. La suite entera corre ya **sin saltos**: 733 tests con `ARCHMUSE_DXF_V2S` definido.

Tres defectos reales que **sólo el plano real podía destapar**, porque los fixtures no tienen ni tildes ni solapes:

| Defecto | Por qué importaba |
|---|---|
| Una comprobación que **no pudo ejecutarse** se imprimía como `[FALLA]` | El plano tiene recintos solapados, así que no había superficie medida contra la que cruzar la suma. El arquitecto leía «la suma no cuadra»: una acusación sobre su trabajo por algo que nadie llegó a mirar. Gasta la credibilidad que hará falta el día que falle de verdad. Ahora hay un tercer estado (`NoSeHaPodidoComprobar`) que no cuenta como superada —no comprobar no es comprobar— pero tampoco acusa |
| Los rótulos del PDF salían **sin tildes ni eñe**: «Bano», «Salon cocina», «Vestibulo» | Es el documento que el arquitecto le enseña a su cliente. El nombre bueno ya estaba leído (`CeldaCuadro.etiqueta`), sólo que no viajaba hasta el PDF: el rótulo se derivaba del identificador interno, que es ASCII a propósito |
| El PDF decía `BLOQUEADO` donde el DXF escribe `N/D` | Dos vocabularios para la misma celda, en un documento cuyo único trabajo es explicar el otro |

**Sobre el corpus (`NOR-1`, ahora `PARCIAL`).** Ver la tarea para el detalle. Lo importante: la validación 17 no veía el error que comete quien **empieza** a transcribir, el manifiesto obligaba a mentir sobre una regla sin firmar, y el curador no tenía forma de comprobar su trabajo sin un programador. Las tres cosas están cerradas. Lo que queda es contratar a un colegiado, y no lo sustituye ninguna tarea.

### 13.5 Lo hecho el 2026-08-19 (tercera sesión: consolidar Skills y decidir la siguiente)

Encargo: consolidar `SK-1`, diseñar la Skill de memoria justificativa, hacer que el agente **pregunte en vez de inventar**, montar la arquitectura común de Skills, y evaluar qué Skill vale más comercialmente.

**1. `SK-1` consolidada, con un defecto real que sólo el plano de un cliente enseña.** La Skill declaraba «no resuelve las ambigüedades del plano: las pregunta», y devolvía únicamente el `titulo` de cada solicitud. La capacidad las da completas —qué hueco resuelven, qué opciones hay con qué superficie cada una, y con qué forma se contesta— y todo eso se tiraba por el camino. El arquitecto leía la pregunta y no podía contestarla sin ir a leer el código. **Una pregunta que no se puede contestar no es preguntar:** es el mismo hueco mudo que el producto entero existe para evitar, con signos de interrogación. Test de punta a punta sobre `v2s.dxf`, porque las solicitudes de asignación nacen de una ambigüedad de verdad y un `ACAD_TABLE` no se sintetiza.

**2. `SK-8`: la arquitectura común, motivada por un recuento y no por gusto.** Al ir a escribir la segunda Skill se contó lo que ya había: el invariante más caro del producto —*lo prometido y no producido sale `UNKNOWN` con motivo, nunca ausente*— estaba escrito **cuatro veces y de tres formas distintas**. Ahora vive una vez en `agente/skills/_comun.py`, con una guardia estructural que lee el fuente y falla si vuelve a aparecer.

**3. El PRD de la memoria justificativa, escrito diciendo que no.** Ver `SK-7`. Resumen honesto: lo que se pidió no debe construirse hoy, y el PRD no lo construye. Propone la mitad defendible —el índice de apartados con su estado y las preguntas que faltan— que con el corpus de hoy sale con cero apartados justificados, **y ese es el resultado correcto**. De regalo, convierte el valor del corpus en la cifra que hoy falta para justificar `NOR-1`.

**4. La evaluación comercial, con una medición que cambió mi propia recomendación.** Iba a proponer la Skill de carpintería: reutiliza el procedimiento entero de `SK-1` y no necesita corpus. Medí `v2s.dxf` antes de escribir el PRD y las **ventanas no están** — sólo cuatro bloques genéricos sin dimensiones ni asociación a vivienda tipo, mientras las puertas vienen con todo el dato en el nombre. En un cuadro de carpintería español las ventanas son la mitad cara. Conclusión: **medir un segundo plano antes de decidir**, media jornada. Es el hallazgo más rentable de la sesión, porque lo que evita es escribir tres días de Skill contra un fichero y descubrir en el segundo cliente que el 60 % sale en blanco. Documento completo: `docs/design/2026-08-19-valor-comercial-de-las-skills.md`, que además rechaza los detalles constructivos (`OP-14`) y confirma BIM en V2 con un argumento que faltaba: **un IFC llega de Revit, donde el arquitecto ya tiene sus tablas**.

**Lo que esta sesión NO hizo, a propósito:** no tocó el núcleo de `agente/` (Terminal 1 trabajaba en él en paralelo), no transcribió normativa, y no implementó `MJ-4` a `MJ-8` — esperan la aprobación del PRD.

---

### 13.6 Lo hecho el 2026-08-19 (cuarta sesión: el núcleo agéntico, en paralelo con la tercera)

Encargo: enchufar el planificador a la fachada, poder enseñar el plan antes de ejecutar efectos, arreglar la gestión de contexto largo, y corregir los defectos reales del bucle. Sin cambiar de framework y sin construir interfaz.

**1. El planificador, alcanzable.** `AG-1` y `AG-2` estaban `HECHO` y **no los alcanzaba nadie**: `planificar()` sólo lo llamaban los tests y `scripts/demo_agente.py`. Ahora `copiloto.atender(via=VIA_PLAN)`, o partido en dos —`proponer()` planifica y audita sin ejecutar; `ejecutar_propuesta(confirmar=…)` ejecuta ese plan y sólo ése—, que es lo que pone un sitio donde decir que no. **Decir que no no ejecuta ni el primer paso**, ni siquiera el que no tenía efectos. Y por esa vía hay **una sola llamada al modelo en total**: la de planificar. No hay redacción final, y no haberla es lo que hace estructuralmente imposible que aparezca una cifra que ninguna herramienta produjo.

**2. `AG-8`, que era una mentira escrita.** El prompt del planificador le pedía al modelo declarar qué pasos son independientes «porque es lo que permite ejecutarlos a la vez». No lo permitía. Ver la tarea: ahora sí, con lista blanca cerrada de efectos, regla de nivel entero, y la bitácora siempre en el orden de `Plan.orden()`.

**3. `AG-9` y `TL-10`, los dos defectos que se descubren con el plano del cliente y no con un fixture.** El historial crecía sin límite hasta reventar el contexto, y los argumentos de una capacidad no se validaban más allá de «esta clave existe». Ver las dos tareas.

**4. Dos defectos más, corregidos de paso:**

| Defecto | Por qué importaba |
|---|---|
| `ResultadoDeEjecucion.completa` era `all(...)` sobre cero pasos | `all()` de nada es cierto, así que **una ejecución sin un solo paso se declaraba completa**, y esa bandera viaja al acta. Ya pasaba por la vía del bucle: una respuesta en prosa sin ninguna Skill ejecutada emitía un acta que decía `completa: true`. Un acta que afirma eso sobre un trabajo que nadie hizo es la clase de afirmación que este sistema existe para no emitir |
| La lista de efectos salía dos veces en el plan, con dos criterios | `planificador.a_texto` los listaba todos y la fachada los listaba otra vez separando lo pendiente de lo concedido. Imprimir la misma lista dos veces con dos criterios distintos es cómo se consigue que el arquitecto deje de leerla |

**Lo que esta sesión NO hizo, a propósito:** no cambió el defecto a `VIA_PLAN`, no tocó `app.py` (la pantalla es `INF-7`), no migró a ningún framework, y no tocó `agente/skills/` — la tercera sesión trabajaba ahí en paralelo. Documento de decisión: `docs/design/2026-08-19-el-planificador-en-la-fachada.md`.

**5. `AG-4`, y un defecto que sólo aparece cuando existe la replanificación.** Se replanifica **una vez** y nunca dos, nunca para esquivar una autorización, y nunca con un plan idéntico al que acaba de fallar. Al montarlo salió que la reanudación buscaba el paso anterior **por `paso_id` a secas**: un segundo plan que reutilizara el id «ficha» para otra Skill se habría llevado el resultado del primero, con su sello y su acta, sin que nada fallara. Ver `AG-4` para el detalle y para por qué un apunte antiguo sin `sello_de_entrada` se sigue aceptando.

**Lo que queda anotado y sin hacer:** el planificador no suma coste (`AG-3`), y los niveles mixtos —uno que escribe un fichero junto a tres que consultan la red— van enteros en serie por la regla de todo-o-nada. Lo último es deliberado y se puede afinar el día que se mida que duele.

### 13.7 Lo hecho el 2026-08-19 (el entregable que no espera al corpus)

Encargo: buscar dentro del repositorio qué entregable profesional se puede construir **con los datos que ArchMuse ya extrae de un DXF real**, que ahorre horas, sea verificable y **no dependa del corpus normativo**; y si la candidata es clara, implementarla.

**La candidata, y cómo se eligió.** No se eligió por parecer buena: se eligió **midiendo**. `analyzer/evaluator.py` tiene 3.521 líneas y decenas de comprobaciones, pero casi todas llevan un umbral —superficie mínima de dormitorio, ancho de pasillo— que no sale de ninguna fuente citada; construir sobre ellas sería alucinación normativa por la puerta de atrás. Lo que queda al filtrar eso es lo puramente geométrico y de coherencia interna, y ejecutado sobre `v2s.dxf` da **nueve hallazgos reales**:

| Hallazgo, medido | Qué se hacía antes con él |
|---|---|
| Dos solapes: `Tendedero`+`Tendedero` **4,00 m²** (95 % de la pieza menor) y `Terraza`+`Tendedero` **3,08 m²** | Servían para negarse a medir. El arquitecto veía el efecto, nunca la causa |
| Dos contornos con el flag `closed` mal puesto, uno con **2,95 cm** de hueco | Una línea de `_log.warning`, o sea un terminal que nadie lee — pese a que el parser documenta que «tiene que quedar visible para quien audite» |
| El rótulo `Tendedero` **dos veces** (4,22 y 8,63 m²) | Una celda `BLOQUEADO`, sin decir que la causa era el rótulo repetido |
| El cuadro reserva 1 tendedero y el plano dibuja 2; reserva 2 terrazas y dibuja 1 | **Nadie lo calculaba** |
| El cuadro pide `pasillo` y `vestibulo`: ninguna pieza rotulada así | **Nadie lo calculaba** |

Siete de los nueve ya se sabían y se tiraban. El producto estaba desperdiciando su mejor entregable disponible porque lo usaba como insumo interno.

**Por qué esta y no otra.** Es la única del catálogo que cumple los cuatro criterios a la vez: ahorra horas de verdad (el repaso previo a la entrega, que se rehace en cada revisión del plano), entrega un documento, cada hallazgo se puede ir a comprobar, y **no necesita ni una línea de corpus**. La carpintería sigue esperando un segundo plano (`OP-13`) y la memoria justificativa sigue esperando a `NOR-2` (`SK-7`).

**El falso positivo, que es la parte que más enseña.** La primera versión producía **seis hallazgos falsos** sobre el plano real: el cuadro numera los huecos (`dormitorio_1`) y el arquitecto numera los rótulos («Dormitorio 1»), y sin normalizar los dos lados un piso de tres dormitorios correcto salía lleno de avisos. Se detectó ejecutándolo contra el fichero del cliente antes de escribir ningún test, y tiene el suyo. Seis avisos falsos en el primer plano real habrían bastado para que nadie volviera a abrir el informe.

**La frontera con `D-7`, que es lo que permite entregar esto sin firma colegiada.** La Skill **no gradúa la gravedad de nada**: dice qué es y cuánto mide. No es una convención de estilo — es la verificación bloqueante `ningun_hallazgo_lleva_gravedad`, con un test que comprueba que **falla de verdad** cuando un hallazgo califica. Mientras pase, ArchMuse mide; el día que alguien la haga fallar, ha empezado a opinar sobre el trabajo de un colegiado.

**Lo que esta sesión NO hizo, a propósito:** no tocó el runtime de `agente/` —el descubrimiento hace que añadir capacidades y Skills sea dejar un fichero—, no implementó memoria justificativa ni carpintería, y no transcribió normativa.

---

### 13.8 Lo hecho el 2026-08-19 (la planta entera, y no un piso recortado)

Encargo: «elige el siguiente trabajo profesional de mayor valor que ArchMuse pueda hacer con lo que ya existe, impleméntalo de principio a fin y pruébalo con un proyecto real; no construyas infraestructura nueva salvo que sea imprescindible».

**Cómo se eligió, y otra vez no fue por parecer buena.** Se ejecutó el vertical existente contra los **dos** planos reales del cliente y se miró qué salía:

| Plano | Qué es | Qué entregaba ArchMuse antes de hoy |
|---|---|---|
| `v2s.dxf` | Un piso recortado, con su `ACAD_TABLE` de cuadro | DXF relleno + PDF + acta. Funciona |
| `V5.dxf` | **Una planta de tres viviendas** (`VT1/3`, `VT2/2`, `VT3/3`), 22 recintos, **sin ningún `ACAD_TABLE`** | **Nada.** «esta función de momento solo admite un DXF con una única vivienda detectada; tiene 3» |

El caso que no funcionaba es **el normal**: una planta de un edificio residencial tiene tres, cuatro o seis viviendas, y el cuadro de superficies suele dibujarse *después* de medir, no antes. El producto sólo sabía trabajar sobre el piso recortado y con la tabla ya puesta.

**Por qué esta candidata y no otra.** Cumple los cuatro criterios a la vez, igual que la revisión de coherencia en §13.7: ahorra horas de verdad (medir una planta a mano se rehace entera en cada revisión), entrega un documento, cada cifra se puede ir a comprobar al DXF, y **no necesita ni una línea de corpus normativo**. Las alternativas que se descartaron con datos: la superficie construida sigue sin ser medible con honestidad (§`DOC-2`: reconstrucción por casco convexo con error del −24 % al +49 %), la memoria justificativa sigue esperando a `NOR-2`, y `DOC-1` —que era el siguiente de la cola— es presentación de algo que ya se entrega, no un trabajo que hoy no se pueda hacer.

**Cuánta infraestructura hizo falta: ninguna.** El reparto de recintos por vivienda ya existía, probado, en `evaluator.group_rooms_by_unit_label`, y lo usaba una sola capacidad para producir un número que no llegaba a ningún entregable. `agente/` no se tocó —capacidades y Skills se descubren dejando un fichero—, y `analyzer/parser.py` y `analyzer/evaluator.py` tampoco. Cinco ficheros nuevos y ninguno modificado, aparte de las tres listas que el propio sistema exige actualizar al añadir una capacidad (invocaciones, contrato congelado y golden).

**Los dos defectos que encontró probar contra el plano real antes de escribir los tests**, que es el orden que ya funcionó en §13.7:

1. **El descuadre de redondeo.** Cruzar la suma de las cifras **publicadas** contra la unión geométrica daba en `VT3/3` un descuadre de 0,01 m² —redondear ocho piezas a dos decimales y sumarlas— que habría salido como «metros dibujados dos veces». Un aviso falso en la primera vivienda medida de la primera planta real. Se cruzan las magnitudes crudas; el total publicado sigue siendo la suma de las publicadas para que la tabla cuadre a mano. Tiene su test.
2. **`H.ay 7,08 m²`** en el PDF: una expresión de capitalización mal parentizada. Trivial, y sólo se ve leyendo el PDF generado — que es exactamente por lo que hay que leerlo.

**Lo que la medición encuentra en cada plano, y son resultados distintos a propósito:**

- `V5.dxf`: **tres viviendas medidas enteras** — `VT1/3` 66,32 m², `VT2/2` 58,44 m², `VT3/3` 66,56 m² de superficie útil, con sus 22 piezas, su ámbito y su procedencia. Cero avisos falsos.
- `v2s.dxf`: **se niega a dar el total** y dice por qué: «hay 7,08 m² dibujados dos veces: la suma de las piezas da 74,95 m² y la superficie que ocupan realmente es 67,87 m²», con los dos pares que se pisan (`Tendedero`+`Tendedero` 4,00 m² y `Terraza`+`Tendedero` 3,08 m²). Las nueve piezas siguen medidas. **Son los mismos 7,08 m² que la revisión de coherencia encuentra por su cuenta y por otro camino**, y que dos caminos independientes den la misma cifra es lo que hace creíbles a los dos.

**Lo que esta sesión NO hizo, a propósito:** no tocó el runtime de `agente/`, no dibujó ningún `ACAD_TABLE` nuevo en el DXF (escribir el cuadro cuando no existe es otra tarea y otro riesgo), no midió superficie construida y no transcribió normativa.

**Anotado como deuda de proceso:** `SK-10` y `TL-11` no llevan PRD propio, contra la regla de `CLAUDE.md`. Ver la nota en `SK-10`.

**Y un test que se ha dejado en rojo a propósito, que es el resultado más importante de la sesión.** Añadir dos capacidades puso el registro en **14** y disparó `test_el_registro_sigue_dentro_del_tamano_que_C4_permite`: `C4` fija el MVP en 8–12. El test hizo exactamente su trabajo, al primer intento. **No se ha tocado el número**, porque un guardián que se ensancha en cuanto salta no protege de nada y el tope es una de las cinco consecuencias vinculantes. Queda como `D-12` con las cifras, el argumento por ambos lados y una recomendación: separar el contador de capacidades **normativas** —donde el riesgo que `C4` nombra es real y el corpus sigue vacío— del de las geométricas, que no pueden alucinar una norma. Decide Pablo.

**Estado de la suite al cerrar:** 951 pasados, 1 xfailed. Tres rojos, y ninguno es un cálculo: el de `C4` (arriba), el de descubrimiento de Skills (corregido en el mismo cambio) y `test_toda_capacidad_devuelve_un_dict_con_ok`, que estaba rojo por `proyecto.ajustar_programa` — capacidad de la sesión que corría en paralelo, sin su entrada en el test de invocación. No se ha tocado: es su trabajo en vuelo y el test rojo es el recordatorio que está diseñado para ser.

---

### 13.3 Lo siguiente, en orden

**Nota del 2026-08-19 (§13.8):** esta lista no contenía `OP-16` y aun así fue lo que se hizo, con motivo. Los tres primeros puestos siguen bloqueados por una contratación (`NOR-1`, `D-7`) o por una decisión (`D-9`), y el cuarto (`DOC-1`) presenta mejor algo que **ya se entrega**. Medir una planta con varias viviendas era trabajo que un arquitecto pide todas las semanas y que ArchMuse sencillamente **no podía hacer**. Cuando la cola y el plano real no coinciden, manda el plano real.

**Actualización noche 14 (2026-08-19):** `DOC-1` se cerró — Pablo validó el criterio de arquitecto veterano y se añadió el último eslabón (pieza + capa del DXF por cada bloque del acta). Sale de esta lista.

**Actualización 2026-08-20 (reorientación estratégica, Bloques 1 y 2):** `SEG-1` se cerró del todo — cubría ya las tres puertas de medición desde el 19/8, y hoy se extendió a `revision.coherencia_del_plano` dentro de `/api/preguntar`, la única capacidad con efecto `io` que quedaba alcanzable por HTTP sin la pantalla de autorización. De paso, esa misma Skill (`OP-15`, `HECHO` desde el 19/8 pero sin ninguna puerta HTTP) se enganchó a `/` como segunda capacidad real del panel de conversación — ver `docs/design/2026-08-20-reorientacion-estrategica-v1.md` §7/§8. Sale de esta lista. Reordenada sin ella:

| # | Tarea | Por qué va aquí |
|---:|---|---|
| 1 | **`NOR-1` (contratar)** | Lo técnico está hecho el 2026-08-19: el curador ya puede trabajar solo. Queda **contratar**, y sigue siendo lo único que ArchMuse promete y no puede cumplir: una regla en el corpus, sin firmar, cero normas verificables |
| 2 | `D-7` | Ya no es preventivo. `SK-1` **tiene** criterio profesional aplicado sobre un plano real y sin firmar: el orden del procedimiento, qué hacer ante una ambigüedad de reparto, y si un solape es error del plano o convención del autor. Los tres van enumerados en la decisión. Bloquea cobrar por el cuadro de superficies |
| 3 | `INF-1` (cerrar) | Ver `D-9`. **Revisar antes de fiarse de esta fila:** los 9 commits que motivaron esta entrada ya se subieron a `origin/agente/nucleo-agentico` el 2026-08-20 (a petición explícita de Pablo) — falta comprobar qué queda pendiente de verdad en `INF-1`, no asumir que sigue igual que el 19/8 |
| 4 | `INF-2` → `ME-2` | Postgres y el registro append-only sellado. Es el foso, y hasta aquí todo vive en ficheros. Necesita credenciales/proveedor que sólo puede dar Pablo |
| 5 | `AG-3` | Presupuesto por ejecución, con las cifras medidas de `SEG-4`. Necesita ejecutar cargas reales y leer las cifras antes de poder implementarse — no es sólo código |

Después, vestir el vertical: `SEG-3` → `SEG-2` → `INF-4` → `INF-5` → `INF-6` → `INF-7` → `INF-8`.

Y, en paralelo (no compite por tiempo de ingeniería): el Bloque 3 (housekeeping: vendorizar three.js si hiciera falta -- ya está hecho, ver `static/index.html`; sacar `JarvisApp.py` del repo; decidir por escrito el futuro de `/mvp`, congelado desde el Bloque 1) y el Bloque 4 (probar el flujo de revisión con 3 arquitectos reales) del informe del 2026-08-20, ambos a la espera de que Pablo confirme el resultado de los Bloques 1 y 2 antes de arrancar.

**Decisiones de producto del 2026-08-20 (dirección, no código):** Pablo fijó dos próximas capacidades tras cerrar V1 — `OP-17` (accesibilidad geométrica: anchos de paso, radios de giro, pendientes de rampa) y `OP-18` (retranqueos del edificio vs. límite real de parcela, cruzando `superficies.medicion_de_planta` con la geometría de Catastro de `CP-4`) — ambas sobre el mismo motor geométrico ya existente, sin tocar el corpus normativo. Y descartó explícitamente tres ideas por ahora: el checklist de documentación para visado (dominio normativo, sin corpus detrás), la detección de incoherencias memoria-texto vs. planos (NLP sobre texto ambiguo, riesgo de falso silencio) y mediciones/presupuesto (expansión de mercado sin evidencia de demanda todavía). Detalle completo en `OP-17`, `OP-18` (§1) y la tabla de §2. Ninguna de las dos capacidades nuevas se ha implementado — es sólo la decisión de dirección, registrada para no perderla.

---

## 14. Decisiones pendientes que bloquean tareas

De `docs/design/decisiones-pendientes.md`. Una tarea bloqueada por una decisión **no se empieza**: se salta y se sigue con la siguiente.

| Decisión | Bloquea | Urgencia |
|---|---|---|
| D-1 · Residencia de datos del proveedor de identidad | `SEG-3` | Alta: condiciona `SEG-2`, `INF-7`, `INF-8` |
| D-2 · `uv` en lugar de `pip` | nada | Baja: conveniencia |
| D-3 · `pydantic` para los manifiestos | `TL-3` (forma, no fondo) | Media |
| D-4 · Ejecución durable de terceros | nada hoy | Baja: reabrir solo si `INF-4` no basta |
| D-5 · Modelo por perfil de tarea | `AG-3` | Media: se decide **con** las cifras de `SEG-4`, no antes |
| D-6 · Dónde vive la memoria de proyecto | `ME-1` | Alta |
| D-7 · Qué Skills primero y quién valida su procedimiento | `SK-5` | Alta: es contratación, como `NOR-1` |
| D-8 · Umbral para mostrar una propuesta de Skill | `AG-7` | Baja |
| D-9 · Si una sesión autónoma puede empujar a una rama con prefijo | `INF-1` | **Alta**: es lo único que bloquea la red de seguridad de todo lo demás |
| D-10 · Tipo de cambio para facturar en euros | nada hoy | Baja: se decide con `INF-9`, y entonces el cambio tiene que guardarse **con la factura** |
| D-11 · Cuándo entra FastAPI y quién regenera el lock de dependencias | `INF-5` | Media: hoy serviría capacidades que no llama nadie; el valor llega con `INF-6` e `INF-7` |
| D-12 · El techo de 12 capacidades de `C4`, superado por una (**13**, tras retirar `bim.inventario_de_ifc` el 2026-08-19) | **Dos tests en rojo a propósito**, protegidos por `tests/test_guardianes_de_decision.py`. Pasos 1 y 2 aprobados y ejecutados; paso 3 autorizado y escrito en `docs/design/2026-08-19-revision-formal-de-C4.md` | Alta: es una de las cinco consecuencias vinculantes y criterio de aceptación de todo PRD |

---

## 15. Cómo se sabe que este backlog está funcionando

Cuatro señales, y ninguna es «número de tareas hechas»:

1. **El registro de capacidades crece más despacio que la lista de capacidades auditadas.** Si se invierte, C4 está incumplido y hay que parar de añadir.
2. **La tasa de falsos positivos por regla no sube.** Un hallazgo falso destruye la confianza en los verdaderos; `DESTROY_ARCHMUSE.md` §5.1 dice que es el motivo nº1 de abandono. Bloquea release.
3. **Toda tarea `HECHO` tiene su criterio verificado, no aproximado.** Un criterio que se da por bueno «en espíritu» es una tarea sin hacer con etiqueta verde.
4. **El corpus crece cada semana.** Si esta señal está parada, las otras tres dan igual.
