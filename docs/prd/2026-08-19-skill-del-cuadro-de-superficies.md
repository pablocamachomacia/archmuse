# PRD — Skill del cuadro de superficies (tarea `SK-1`)

**Estado:** APROBADO · **Fecha:** 2026-08-19 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo, 2026-08-19

> **Condición de la aprobación (textual):** la verificación de la suma será **informativa, no bloqueante**, hasta disponer de al menos **10 proyectos reales**. Dice la diferencia y no impide entregar. El cambio a bloqueante es una decisión posterior, con datos.

**Tarea del backlog:** `SK-1`. Depende de `TL-1` (HECHO), `TL-9` (HECHO) y `TL-2` (PRD escrito, pendiente). Es el procedimiento que convierte las capacidades sueltas del vertical en **el trabajo que un arquitecto reconoce como suyo**.

---

## 1. Problema que resuelve

Después de `TL-1` y `TL-9`, ArchMuse ya sabe hacer las piezas: leer un DXF en metros, calcular el cuadro celda a celda, decir qué no puede calcular y recibir lo que el arquitecto declare. Lo que **no** sabe es hacer el trabajo.

La diferencia no es retórica. Un arquitecto que rellena un cuadro de superficies sigue un procedimiento: comprueba primero que el plano está en la unidad que dice, mira si las estancias están rotuladas, calcula, revisa que la suma cuadre con la superficie útil total, se pregunta si falta alguna pieza, y **no entrega nada** si dos terrazas podrían estar intercambiadas. Ese orden y esos controles son criterio profesional, no encadenamiento de funciones.

Hoy ese procedimiento no existe en ninguna parte: está implícito en el orden en que un programador llamaría a tres capacidades. Un modelo que las llame en otro orden, o que se salte la comprobación de la suma, produce un cuadro que parece igual de bueno y no lo es.

**Y hay una segunda razón, de C4.** El catálogo de ArchMuse tiene que poder enseñarse: «esto es lo que sé hacer, así lo hago, y esto no lo compruebo». Una lista de capacidades no se puede enseñar a un arquitecto; una lista de procedimientos, sí.

## 2. Usuario afectado

El arquitecto de estudio pequeño —una a cinco personas— que dedica media tarde a contar polilíneas para rellenar el cuadro de una vivienda tipo. Es el usuario de `OP-1` y el único cuyo tiempo ahorra ArchMuse de forma medible hoy.

## 3. Objetivo de negocio

- **Es el primer entregable vendible.** Sin Skill hay capacidades; con Skill hay un trabajo que se pide en una frase y se cobra.
- **Es lo que hace comparable el resultado consigo mismo.** El mismo procedimiento, versionado, ejecutado sobre el mismo plano dentro de seis meses, da el mismo cuadro — y si no lo da, se puede decir qué versión cambió. Eso es el sello de `ME-2` y es el foso de `MOAT_ANALYSIS.md`.
- **Es la unidad que un colegiado puede firmar** (`SK-5`). Nadie firma «una capacidad»; se firma un procedimiento.

## 4. Objetivo técnico

- Existe `superficies.cuadro_de_vivienda` en el registro de Skills, versionada.
- Declara sus **requisitos**, y con uno sin cumplir devuelve **la pregunta concreta** sin gastar un token ni tocar un fichero.
- Declara las capacidades que usa, y **sólo puede invocar esas** (ya lo vigila `Contexto.invocar`).
- Declara sus **verificaciones deterministas**, y sin pasarlas el resultado no se marca como verificado.
- Declara sus **efectos**: hoy ninguno mientras no entre `TL-2`; con `TL-2`, `escribe_fichero`.
- Sus **limitaciones** se derivan de los manifiestos de las capacidades que ejecutó, no se redactan a mano — es lo que alimenta el acta.

## 5. Casos de uso

**CU-1 · Camino feliz.** DXF con una vivienda y su `ACAD_TABLE`. La Skill lee el plano, calcula el cuadro, verifica, y entrega las 18 celdas con su estado y las preguntas pendientes.

**CU-2 · Sin escala determinable.** El plano no declara unidad y su tamaño admite dos lecturas. La Skill **pregunta** en vez de suponer, y no ejecuta nada más. Es el criterio de terminado que el backlog fija para esta tarea.

**CU-3 · Con las respuestas del arquitecto.** Se reejecuta con lo que él ha declarado; las celdas afectadas quedan resueltas y marcadas como suyas.

**CU-4 · Plano con dos viviendas.** Se declara fuera de alcance con el motivo, no se elige una.

**CU-5 · La suma no cuadra.** La suma de las celdas calculadas difiere de la superficie útil medida por encima de una tolerancia declarada. **La Skill no entrega**: da el resultado marcado como no verificado, con la diferencia y las dos cifras. Es el control que hace un arquitecto y que ninguna capacidad suelta hace.

## 6. Casos límite

| Caso | Comportamiento |
|---|---|
| DXF sin `ACAD_TABLE` de cuadro | Fuera de alcance, con el motivo. No se inventa una tabla |
| Recintos sin etiqueta | Se cuentan y se dicen: una pieza sin rótulo no entra en ninguna familia, y callarlo haría que la suma no cuadrara sin explicación |
| Dos piezas para un solo hueco del cuadro | Celda `BLOQUEADA` con la pregunta de asignación. Nunca se reparte por orden de aparición |
| Celda ya escrita en el DXF | Se conserva literal y se anota como preexistente |
| Respuesta del arquitecto que contradice una celda ya escrita | Conflicto declarado, sin sobrescribir (`aplicar_respuestas` ya lo hace) |
| Tolerancia de la suma | **Declarada como parámetro de la Skill**, no escondida en el código. Un umbral invisible es un criterio oculto |
| El DXF pesa 200 MB | Límite declarado; por encima, se rechaza con el motivo en vez de tumbar el proceso |

## 7. Flujo del usuario

1. Sube el DXF y escribe «rellena el cuadro de superficies de este plano».
2. ArchMuse le enseña el plan (`AG-1`) o, mientras no exista, ejecuta la Skill directamente.
3. Ve el cuadro celda a celda: qué ha calculado, qué ha dejado en blanco y **por qué**.
4. Contesta las preguntas que quiera contestar.
5. Ve el cuadro completo, todavía sin que se haya tocado su fichero.
6. Autoriza la escritura (`TL-2` + `SEG-1`) y descarga el DXF relleno, marcado como borrador (`DOC-3`), con su acta (`DOC-1`).

Los pasos 3, 4 y 5 ya son posibles hoy con las capacidades; lo que falta es que sean **un solo trabajo** en vez de tres llamadas.

## 8. Criterios de aceptación

1. `superficies.cuadro_de_vivienda@1.0.0` está en el registro de Skills y `comprobar_registro` la valida contra el registro de capacidades al cargar.
2. Ejecutada sobre el `v2s.dxf` real, produce el cuadro relleno con sus 18 celdas.
3. Ejecutada sobre un plano sin escala determinable, **pregunta** y no ejecuta ninguna capacidad de cálculo. Sin gastar un token.
4. La verificación de la suma existe, es determinista, y su tolerancia está declarada en el manifiesto.
5. Un resultado que no pasa la verificación **no se marca como verificado** y dice por qué.
6. Las limitaciones del acta se derivan de los manifiestos ejecutados: quitar una capacidad del procedimiento cambia la lista sin que nadie la edite.
7. La Skill no puede invocar una capacidad que no declara (ya vigilado; se añade el caso a su test).
8. Mientras `TL-2` no esté aprobada e implementada, la Skill **no declara efectos** y no escribe nada.

## 9. Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| El procedimiento codificado no es el que sigue un arquitecto de verdad | **Media** | **Alto** — es mala praxis con buena presentación | `SK-5`: lo firma un colegiado. Está bloqueada por D-7, y esta Skill es la que hace que D-7 deje de poder aplazarse |
| La tolerancia de la suma se elige a ojo y produce falsos positivos | Alta | Alto — `DESTROY_ARCHMUSE.md` §5.1: un hallazgo falso destruye la confianza en los verdaderos | Se calibra contra planos reales antes de fijarla, y se declara. Si no hay planos suficientes, se empieza con la verificación **informativa** y no bloqueante |
| Se convierte en una Skill que hace de todo | Media | Medio | Alcance: una vivienda, un cuadro. Varias viviendas es otra Skill, y probablemente otra conversación |
| Depende de `TL-2` para ser útil de verdad | Alta | Medio | Los pasos 3-5 del flujo ya valen sin escritura. La Skill se puede entregar y probar antes |

## 10. Impacto sobre módulos existentes

- **`agente/skills/`:** un módulo nuevo. El descubrimiento ya funciona; no se toca ningún `__init__`.
- **`agente/herramientas/plano.py`:** sin cambios. La Skill es consumidora.
- **`agente/verificacion.py`:** recibe su primera verificación de dominio real (la suma). Hoy sólo lo prueban los tests.
- **`analyzer/`:** **no se toca nada.**
- **`app.py`:** no se toca.

## 11. Plan de implementación (tareas de ~1 jornada o menos)

| # | Tarea | Salida verificable |
|---|---|---|
| 1 | Manifiesto de la Skill: requisitos con su pregunta, capacidades declaradas, entregables, limitaciones | Aparece en el catálogo; `comprobar_registro` la acepta |
| 2 | El procedimiento: leer → calcular → (respuestas) → verificar, en ese orden y con el corte de `CU-2` | Test del camino feliz con DXF sintético |
| 3 | Verificación de la suma, con tolerancia declarada | Test del `CU-5`: no verificado, con las dos cifras |
| 4 | Derivación de limitaciones desde los manifiestos ejecutados | Test: quitar una capacidad cambia la lista |
| 5 | Prueba contra el `v2s.dxf` real, gated por `ARCHMUSE_DXF_V2S` | Las 18 celdas |

Estimación: **2 jornadas**, que es lo que dice el backlog.

## 12. Plan de pruebas

- **DXF sintético** para el procedimiento, el corte por escala y la derivación de limitaciones.
- **`v2s.dxf` real**, gated, para el resultado completo.
- **Sin gastar tokens:** la Skill es determinista de punta a punta; no necesita modelo.
- **De frontera:** los tests de C1 y de «una Skill sólo invoca lo que declara» siguen verdes.
- **Manual, una vez:** que un arquitecto mire el cuadro resultante y diga si el orden de las comprobaciones es el suyo. Ningún test dice eso, y es el criterio 9 del riesgo principal.

## 13. Métricas de éxito

1. **Celdas resueltas sin preguntar**, sobre planos reales. Es el ahorro medible.
2. **Preguntas por plano.** Si son muchas, el procedimiento pide demasiado y el arquitecto abandona antes de terminar.
3. **Verificaciones fallidas que resultan ser falsas alarmas.** Debe tender a cero; si no lo hace, la tolerancia está mal y hay que pararla antes de que erosione la confianza.
4. **Tiempo desde subir el plano hasta descargar el cuadro.** Frente a la media tarde que cuesta a mano.

## 14. Motivos para NO implementar esto

1. **Las capacidades ya hacen el trabajo.** Un arquitecto puede hoy ejecutar `python -m agente.invocar plano.cuadro_de_superficies --ruta plan.dxf` y obtener exactamente el mismo cuadro. Lo que añade la Skill es **procedimiento, versión y verificación** — importante a dos años, invisible esta semana. Si el objetivo fuera enseñárselo a un arquitecto el viernes, esto se aplaza y se enseña la capacidad.
2. **Codifica criterio profesional sin tener quién lo firme.** D-7 sigue sin decidir. Esta Skill es la primera que roza el criterio (el orden de las comprobaciones, la tolerancia de la suma), así que implementarla antes de resolver D-7 es asumir que el criterio de un programador vale como el de un colegiado. **Esta es la objeción seria**, y la recomendación es resolver D-7 —aunque sea con un acuerdo informal— antes de empezar la tarea 3 de §11.
3. **La tolerancia de la suma no se puede calibrar sin planos reales,** y hoy hay uno. Elegir un número con una muestra de uno es adivinar. Alternativa: entregar la verificación como **informativa** (dice la diferencia, no bloquea) hasta tener diez planos, y entonces decidir el umbral con datos.
4. **El corpus sigue vacío.** Mismo argumento que gobierna todo el backlog.

---

**Decisión pendiente de Pablo.** Dos, en realidad: aprobar este PRD, y decir si la verificación de la suma arranca **bloqueante** o **informativa**. La recomendación es informativa hasta tener diez planos reales.
