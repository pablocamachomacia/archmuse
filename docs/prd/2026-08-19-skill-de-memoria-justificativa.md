# PRD — Skill de memoria justificativa (`SK-7`)

**Estado:** Borrador · **Fecha:** 2026-08-19 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

> **Aviso de entrada, y es lo primero que hay que leer.** Este PRD **no propone
> redactar la memoria justificativa**. Propone la mitad de ese trabajo que hoy
> se puede defender delante de un juez, y se niega explícitamente a la otra
> mitad. Si al terminar de leerlo la sensación es «esto no es lo que pedí», la
> §14 explica por qué la versión que se pidió no debe construirse todavía y qué
> hay que hacer para que pueda construirse.

---

## 1. Problema que resuelve

La memoria justificativa del cumplimiento del CTE es, según el propio
`docs/AGENTE_BACKLOG.md` (OP-6), **el entregable que más se va a pedir** y el
trabajo más tedioso del proyecto. También es el que el backlog aplaza con el
veredicto más duro del catálogo: «peor relación valor/riesgo mientras el corpus
esté vacío», porque «una memoria justificativa mal citada no es un bug: es
responsabilidad civil del arquitecto que la firma».

Las dos cosas son ciertas a la vez, y de esa contradicción sale el problema real
que sí está sin resolver hoy:

**Un arquitecto que va a redactar la memoria justificativa no sabe, antes de
empezar, qué parte de ella tiene los datos disponibles y qué parte no.** Lo
descubre a mitad de la redacción, cuando ya ha escrito tres apartados y el
cuarto le pide una superficie que nadie ha medido o una ocupación que el cliente
no ha declarado. Ese descubrimiento tardío es el que convierte un documento de
dos días en uno de dos semanas.

Y hay un segundo problema, este de ArchMuse y no del arquitecto: **hoy nadie
puede decir, con una cifra, cuánto vale el corpus normativo.** C5 lo pone en el
camino crítico y `NOR-2` es la tarea `P0` continua, pero la única forma de
justificar esa inversión ante Pablo es una impresión. Un documento que diga «de
los 47 apartados de esta memoria, ArchMuse puede justificar 0 hoy y 12 con el
DB-SI transcrito» convierte esa impresión en un número.

## 2. Usuario afectado

**El arquitecto individual o el estudio pequeño que redacta el proyecto básico**
— el mismo de `SK-1`, y no por casualidad: es quien no tiene un aparejador
dedicado a montar los datos de partida, así que los monta él a mano cada vez.

**Usuario secundario, y hoy más importante: Pablo.** El apartado de cobertura de
este documento es el instrumento con el que se decide si se contrata al
colegiado de `NOR-1` y con qué prioridad se transcribe cada Documento Básico.
No es un usuario objetivo de `NORTH_STAR_2031.md`; es el usuario de esta semana.

## 3. Objetivo de negocio

Tres cosas, en orden de importancia:

1. **Hacer medible el foso.** `MOAT_ANALYSIS.md` sostiene que lo defendible es
   el corpus, no el visor ni el generador. Esta Skill es la primera pieza que
   traduce «tenemos corpus» a «justificamos N apartados que antes no
   justificábamos», y el número sube solo al transcribir. Es la métrica de
   `NOR-2` cobrando forma de producto.
2. **Vender la honestidad como característica.** El ataque nº1 de
   `DESTROY_ARCHMUSE.md` es la alucinación normativa. Un competidor con un LLM
   redacta la memoria entera hoy y suena mejor; ArchMuse entrega un documento
   que dice **qué no puede justificar y por qué**, con la cita cuando la tiene y
   el hueco declarado cuando no. Esa diferencia sólo se puede enseñar con un
   documento delante.
3. **Preparar `DOC-5` sin pagar su riesgo.** Cuando `NOR-2` cierre, redactar la
   prosa será añadir un paso a un procedimiento ya probado, no empezar de cero.

## 4. Objetivo técnico

Una vez implementado, debe ser cierto que:

- ArchMuse produce un documento con **un apartado por exigencia**, y cada
  apartado lleva **exactamente uno** de cuatro estados: `JUSTIFICADO`,
  `SIN_DATO`, `SIN_CORPUS`, `NO_APLICA`. No hay quinto estado y no hay apartado
  sin estado.
- **Ninguna cifra del documento puede no estar respaldada.** El detector de
  `agente/respaldo.py` es una verificación *bloqueante* de la Skill, no un
  aviso. Hoy ese módulo existe y no lo usa nadie.
- **Ningún apartado se marca `JUSTIFICADO` si su materia no es `afirmable`** en
  `normativa/manifiesto.py`. Con el corpus de hoy —una regla, sin firmar— eso
  significa que el documento sale con cero apartados justificados, y **eso es el
  resultado correcto**, no un fallo.
- Lo que falta se entrega como **preguntas contestables**, con la forma exacta
  de la respuesta, no como una lista de claves internas.
- El documento sale marcado como borrador (C3) y con el acta de procedencia
  pegada (C2).

## 5. Casos de uso

**CU-1 · «Voy a redactar la memoria de este proyecto: dime qué tengo.»**
El arquitecto ya ha pasado `SK-1` sobre su plano, así que la superficie útil y
el cuadro están en la memoria del proyecto con su procedencia. Pide la memoria
justificativa. Recibe el índice de apartados con su estado, los datos de partida
que ya existen con el origen de cada uno, y la lista de lo que falta.

**CU-2 · «¿Qué me cubre ArchMuse de esta normativa?»**
Sin plano y sin proyecto: sólo el municipio y el uso. Recibe la declaración de
cobertura por Documento Básico. Es la pregunta comercial, y hoy se contesta a
mano.

**CU-3 · Contesto lo que falta y vuelvo a pedirla.**
Las respuestas entran en la memoria del proyecto como declaraciones del
arquitecto —con esa procedencia, no como cálculo de ArchMuse— y los apartados
que dependían de ellas pasan de `SIN_DATO` a `JUSTIFICADO` o se quedan en
`SIN_CORPUS` si el problema no era el dato.

**CU-4 · El día que llegue la primera firma colegiada.**
Un apartado pasa de `SIN_CORPUS` a `JUSTIFICADO` **sin tocar la Skill**. Es la
prueba de que el valor está en el corpus y no en el código, y es el criterio de
aceptación nº8.

## 6. Casos límite

| Caso | Qué tiene que pasar |
|---|---|
| El corpus está vacío (**hoy**) | Todos los apartados salen `SIN_CORPUS` con el nombre de la materia. El documento se entrega igual: su contenido es el hueco. |
| El municipio no se resuelve | La cadena territorial no se finge. Todo `SIN_DATO` y una pregunta: «¿en qué municipio está?». Es el comportamiento que ya tiene `territorial.py`. |
| Regla en el corpus pero **sin firmar** | `SIN_CORPUS`, no `JUSTIFICADO`. Lo garantiza la validación 18 más la comprobación de `afirmable`. Es el caso de hoy, y el más peligroso: la regla *existe* y resuelve. |
| La regla aplica pero no se puede evaluar (`aplica_no_evaluable`) | Apartado propio: `SIN_DATO`, con el motivo que da el motor, nunca `NO_APLICA`. Confundir «no lo he podido mirar» con «no le aplica» es el error que este producto existe para no cometer. |
| El proyecto no ha pasado por `SK-1` | `SIN_DATO` en todo lo geométrico, con la pregunta que lo desbloquea señalando a `SK-1`. La memoria no calcula superficies: las consume. |
| Una cifra aparece en el texto y no en el grafo | La verificación bloqueante falla y **el documento no se entrega**. Es el único caso de este PRD en el que no hay entregable. |
| Dos DB dicen cosas distintas del mismo dato | Fuera de alcance de v1: se declara en `limitaciones`. Reconciliar exigencias contradictorias es criterio profesional y va a `D-7`. |

## 7. Flujo del usuario

1. El arquitecto pide la memoria justificativa de su proyecto (CLI, y más
   adelante la interfaz).
2. ArchMuse comprueba los **requisitos** contra la memoria del proyecto. Si
   falta alguno, **la salida es la pregunta** y no se ha gastado ni un token:
   el chequeo es una consulta, es el comportamiento que `RequisitosInsatisfechos`
   ya implementa.
3. Con los datos: resuelve el ámbito territorial, pide las reglas aplicables, y
   cruza cada exigencia contra (a) si hay cobertura afirmable y (b) si hay dato
   de proyecto.
4. Escribe el documento y el acta. Los dos van juntos y con el mismo nombre.
5. La salida en pantalla enseña el recuento: «justificados N · sin dato N · sin
   corpus N · no aplica N», y las preguntas.

## 8. Criterios de aceptación

1. La Skill está registrada como `memoria.justificacion_cte@1.0.0`, se valida al
   cargar y declara sus capacidades, efectos y limitaciones.
2. **No añade ninguna capacidad nueva al registro** (C4). Compone
   `territorial.resolver_ambito` y `normativa.reglas_aplicables`, que ya existen.
3. Ejecutada con el corpus de hoy produce un documento con **cero apartados
   `JUSTIFICADO`** y todos los demás con estado y motivo. Un test lo fija.
4. Un apartado `JUSTIFICADO` sin `concept_id`, sin artículo y sin referencia al
   boletín hace fallar una verificación **bloqueante**.
5. Una cifra del documento que no esté en el respaldo hace fallar una
   verificación **bloqueante**, comprobado con una cifra inyectada a mano.
6. Ninguna materia no `afirmable` puede producir un apartado `JUSTIFICADO`,
   comprobado con un manifiesto de prueba que declare `transcrito_sin_firmar`.
7. Faltando un requisito, la salida es la pregunta, **sin haber invocado ninguna
   capacidad** — comprobable con un registro que cuente invocaciones.
8. Promover la materia a `parcial` en un manifiesto de prueba, sin tocar la
   Skill, convierte apartados de `SIN_CORPUS` en `JUSTIFICADO`. Es el criterio
   que demuestra que el valor está en el corpus.
9. El entregable es `borrador=True` y lleva su sello sha256.
10. Toda pregunta que la Skill devuelve dice cómo se contesta, con el mismo
    criterio que se acaba de corregir en `SK-1`.

## 9. Riesgos

**R-1 · El documento de hoy parece un producto roto.** Un PDF que dice «no puedo
justificar nada» enseñado en una demo puede leerse como incapacidad y no como
honestidad. *Mitigación:* el documento se titula por lo que es —el **plan de
trabajo de la memoria**, no la memoria— y encabeza con el recuento y con la
frase de qué desbloquea cada hueco. Riesgo real; no desaparece del todo.

**R-2 · Compite con `NOR-2`, que es `P0`.** Este PRD estima ~2 jornadas. Las
mismas 2 jornadas puestas en transcribir DB-SI producen más valor **hoy**.
*Mitigación:* no las produce la misma persona — transcribir es trabajo de
colegiado, y el colegiado no está contratado. Si lo estuviera, este PRD se
aplaza; ver §14.

**R-3 · Deslizamiento hacia la prosa.** El paso de «índice de apartados» a
«redactar el apartado» es de una tarde, y es exactamente el que no debe darse.
*Mitigación:* la Skill **no declara ninguna capacidad de naturaleza `llm`** y no
puede adquirirla sin cambiar su manifiesto, que es un cambio visible. `DOC-4` es
quien traerá la prosa, y depende de `ME-2`.

**R-4 · Choca con `REFACTOR_MASTERPLAN.md`.** No: no toca `analyzer/`, ni
`app.py`, ni el frontend. Vive en `agente/skills/` y compone lo que ya existe.

**R-5 · Terminal 1 trabaja en `agente/` en paralelo.** El plan de la §11 está
escrito para no tocar el núcleo: lo común va a `agente/skills/_comun.py`, que es
un fichero nuevo en el subpaquete de Skills.

## 10. Impacto sobre módulos existentes

**Ficheros nuevos:** `agente/skills/_comun.py`,
`agente/skills/memoria_justificativa.py`, `tests/test_agente_skill_memoria.py`,
y el generador del PDF del documento.

**Modificados:** `agente/skills/__init__.py` (una línea de registro), y —sólo en
la tarea MJ-1— `superficies.py`, `evacuacion.py`, `territorial.py` para que las
tres pasen a usar la pieza común. Esa tarea no cambia comportamiento y está
cubierta por sus tests actuales.

**Se consume sin modificar:** `normativa/manifiesto.py` (`afirmable`),
`normativa/resolucion.py`, `agente/respaldo.py`, `agente/herramientas/reglas.py`,
`agente/herramientas/territorial.py`.

**No se toca:** `analyzer/`, `app.py`, `static/`, `bim/`, y el núcleo de
`agente/` (`skill.py`, `nucleo.py`, `ejecucion.py`, `planificador.py`).

**Consumidor indirecto a vigilar:** el acta (`agente/acta.py`) imprime
`preguntas` y `no_hecho`; un documento con cuarenta apartados sin corpus produce
un acta larga. Se resuelve agrupando por Documento Básico en la propia Skill, no
cambiando el acta.

## 11. Plan de implementación dividido en pequeñas tareas

| # | Tarea | ~ | Depende |
|---|---|---|---|
| **MJ-1** | `agente/skills/_comun.py`: extraer `sin_producir()` —lo prometido y no producido sale `UNKNOWN` con motivo— y `valor()`. Hoy hay **tres implementaciones distintas** del mismo invariante (`_sin_hacer` en `superficies`, `_desconocidas` en `evacuacion`, un bucle a pelo en `territorial`), y arreglar una no arregla las otras. Migrar las tres. | 2h | — |
| **MJ-2** | Mover `_pregunta_legible` de `superficies.py` a `_comun.py` y generalizarla: toda Skill devuelve preguntas contestables, no títulos. | 1h | MJ-1 |
| **MJ-3** | `_comun.py`: `apartados_por_cobertura()` — dada la salida de `normativa.reglas_aplicables` y el manifiesto, producir el apartado con su estado. Es el corazón, y se prueba solo, sin Skill. | 2h | MJ-1 |
| **MJ-4** | La Skill: manifiesto, requisitos con sus preguntas, procedimiento escrito para que lo juzgue un arquitecto, y `_ejecutar` componiendo las dos capacidades. Sin entregable todavía. | 2h | MJ-3 |
| **MJ-5** | Las cuatro verificaciones: cifra sin respaldo, apartado justificado sin cita, materia no afirmable justificada, apartado sin estado. Las cuatro **bloqueantes**. | 2h | MJ-4 |
| **MJ-6** | El entregable PDF, con el recuento en cabecera, la marca de borrador y el acta. Reutiliza `analyzer/cuadro_pdf.py` como patrón. | 2h | MJ-4 |
| **MJ-7** | El guion: `python scripts/memoria_justificativa.py`, sin clave de API y sin red. | 1h | MJ-6 |
| **MJ-8** | Documentación de producto: qué es y qué no es este documento, en `README.md` y en el backlog. | 1h | MJ-7 |

Total ~13h. **MJ-1 a MJ-3 tienen valor aunque el resto se cancele**: son la
arquitectura común de Skills, que es la prioridad 4 del encargo.

## 12. Plan de pruebas

- **Unitarias sin Skill** (MJ-3): la tabla de decisión estado por estado, con
  manifiestos de prueba. Es donde vive el riesgo, y se prueba sin ficheros.
- **De la Skill**: los diez criterios de la §8, uno a uno.
- **El test que más importa**, y que hay que mirar el día que falle: con el
  corpus **real**, cero apartados `JUSTIFICADO`. Cuando llegue la primera firma
  dejará de pasar, y ese día se comprueba que la firma es de verdad — no se
  ajusta el test. Mismo criterio que
  `test_ninguna_materia_del_corpus_de_produccion_es_afirmable_todavia`.
- **De no regresión**: la suite entera verde, con `ARCHMUSE_DXF_V2S` definido,
  después de la migración de las tres Skills de MJ-1.
- **Sin red y sin clave**: ninguna prueba de este PRD llama a la API.

## 13. Métricas para medir el éxito

1. **Apartados justificables / apartados totales.** La métrica del corpus. Hoy
   0/N. Es la cifra que justifica la contratación de `NOR-1`.
2. **Preguntas por documento, y cuántas se contestan.** Si el arquitecto no
   contesta ninguna, las preguntas están mal escritas — no es que no le
   interesen.
3. **Apartados que cambian de estado sin desplegar código.** Debería ser el 100 %
   de los que cambian. Si para justificar algo hubo que tocar la Skill, el valor
   no estaba en el corpus.
4. **Cero incidencias de cifra sin respaldo en producción.** No es una métrica de
   éxito: es la condición para seguir existiendo.

## 14. Posibles motivos para NO implementar la idea

**El motivo de fondo, y hay que decirlo entero: lo que se pidió no debe
construirse hoy, y este documento no lo construye.**

Se pidió «la Skill de memoria justificativa». La memoria justificativa es el
documento que **justifica** el cumplimiento del CTE, y justificar exige citar.
El corpus de ArchMuse tiene hoy **una regla, sin firmar**. Una Skill que redacte
esa memoria hoy produciría un documento en el que el 100 % de las
justificaciones vendría de un modelo de lenguaje sin fuente — es decir, el
`OP-6` que el backlog aplaza con el peor veredicto del catálogo, y el ataque nº1
de `DESTROY_ARCHMUSE.md` construido a propósito. No lo hago, y si Pablo lo pide
otra vez después de leer esto, lo haré con esta objeción registrada por escrito
y con la firma de la decisión en `D-7`.

**Tres motivos honestos contra incluso la versión recortada de este PRD:**

1. **No es lo que se pidió, y eso tiene un coste.** Si lo que hace falta esta
   semana es enseñar una memoria redactada a un cliente potencial, este
   documento no sirve para eso y decirlo tarde sería peor.
2. **Su valor hoy es casi todo interno.** El apartado que de verdad se usa esta
   semana es el recuento de cobertura, y ese recuento **ya lo da**
   `scripts/validar_corpus.py` en dos líneas de texto. La diferencia es que aquí
   sale por proyecto y con los datos de partida al lado; es una diferencia real,
   pero es menor de lo que parecen 13 horas.
3. **La alternativa dominante existe y es aburrida:** poner esas 13 horas en
   `NOR-2`. Cada regla transcrita sube la métrica nº1 de esta misma Skill. Si
   hubiera un colegiado contratado, mi recomendación sería **aplazar este PRD
   entero** y transcribir.

**Mi recomendación como CTO, con el colegiado sin contratar:** implementar
**MJ-1 a MJ-3** ya —son la arquitectura común de Skills, valen por sí solas y no
dependen de esta decisión— y **MJ-4 a MJ-8 sólo si Pablo confirma** que quiere
el documento de cobertura por proyecto antes que la prosa. La prosa no se hace
hasta `NOR-2`, y eso no lo cambia ninguna aprobación: lo cambia una firma
colegiada en el corpus.

---

**Decisión:** _pendiente de revisión por Pablo_
