# PRD — Capacidades de medición de una planta (`TL-11`)

**Estado:** **APROBADO** (retroactivo) · **Fecha:** 2026-08-19 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo, 2026-08-19

> **Por qué es retroactivo, dicho por delante.** `TL-11` se implementó el
> 2026-08-19 bajo orden directa de Pablo y **sin PRD previo**, contra la regla de
> `CLAUDE.md`. Este documento no finge que se escribió antes: recoge lo
> construido en la forma que la regla exige, para que la excepción quede visible
> y para que nada que dependa de estas capacidades se fusione sin una
> especificación contra la que contrastarlo. Escrito a partir del código, sus
> tests y las notas de `docs/AGENTE_BACKLOG.md`.

---

## 1. Problema que resuelve

Las capacidades del cuadro (`plano.cuadro_de_superficies`, `plano.escribir_cuadro`)
trabajan sobre **el cuadro que el plano ya trae dibujado**: rellenan las filas del
`ACAD_TABLE` que puso el arquitecto. Eso exige dos cosas — que la tabla exista, y
que haya **una sola vivienda** para saber a cuál describe.

Un plano con tres viviendas y sin tabla no cumple ninguna de las dos, y **ninguna
de las dos ausencias es un defecto del plano**. Hasta `TL-11`, ese plano —que es
el caso normal en obra nueva— no tenía por dónde entrar.

## 2. Usuario afectado

El arquitecto que mide una planta entera, y sobre todo el que mide **un DXF que
no dibujó él**: un colaborador, una fase anterior, el archivo del delineante.

## 3. Objetivo de negocio

Cierra el hueco de `OP-1` sobre el caso normal. Sin esto, el primer vertical sólo
servía para planos de una vivienda con tabla dibujada, que es una fracción de lo
que un estudio maneja.

## 4. Objetivo técnico

- Dos capacidades **separadas por el efecto**: `plano.medicion_de_la_planta`
  mide y no escribe (`efectos=()`, sin autorización); `plano.medicion_en_pdf`
  escribe el documento y declara `escribe_fichero`.
- El DXF de entrada se abre **sólo para leer**, con su sha256 verificado antes y
  después.
- Las dos respetan el contrato de salida —`dict` con `ok`— también al fallar.
- La lista de «lo que no se comprueba» del PDF la **deriva la propia capacidad**
  de los manifiestos, y no es un argumento: si lo fuera, quien la invoca podría
  entregar un documento con la lista recortada.

## 5. Casos de uso

**CU-1 · Medir una planta de varias viviendas sin tabla dibujada.** El caso
central y el motivo de existir.

**CU-2 · Entregar la medición en PDF** con la procedencia de cada cifra.

**CU-3 · Mirar sin generar documento.** La capacidad de lectura basta y no pide
autorización — para eso están separadas.

## 6. Casos límite

| Caso | Qué pasa |
|---|---|
| Unidad del dibujo indeterminable | Se para y se pregunta, antes de medir nada |
| El destino es el propio DXF | Se niega (`_destino_seguro`) |
| El destino ya existe | Se niega: podría ser un entregable ya revisado |
| Sin autorización de escritura | La que escribe no se ejecuta |
| El original cambia durante la ejecución | `_con_sello_intacto` lo detecta y el resultado pasa a fallo |
| Fichero inexistente | `ok: false` con la pregunta |

## 7. Flujo del usuario

Vía la Skill `SK-10` o directamente: ruta del DXF → medición estructurada; con
destino → PDF con la procedencia. El plano nunca se modifica.

## 8. Criterios de aceptación

1. Las dos respetan el contrato de salida también en el camino de fallo.
2. La que escribe se niega sin autorización del efecto.
3. El destino no puede ser el DXF ni un fichero existente.
4. El original conserva su sha256, verificado antes y después.
5. Los guardianes de escritura se **importan** de `plano.py`, no se
   reimplementan.
6. Contrato congelado y golden capturado en el mismo cambio, contra un fixture
   de **dos** viviendas.

*(Los seis están comprobados por tests hoy.)*

## 9. Riesgos

**R-1 · Reimplementar la protección de escritura.** Es el defecto nº1 que se le
corrigió a `SK-9` días antes. *Mitigado:* se importan, y hay un test de política
que lo vigila sobre el fuente.

**R-2 · Inflar el catálogo.** Estas dos llevaron el registro de 11 a 13 y, con
`proyecto.ajustar_programa`, a 14 — por encima del tope de `C4`. Es `D-12`, y
está **sin resolver a propósito**, con el test en rojo.

**R-3 · Solaparse con las capacidades del cuadro.** *Mitigado:* son dos trabajos
distintos con dos entregables distintos. Las del cuadro siguen siendo las buenas
cuando el plano trae su tabla — devolverle al arquitecto su propio plano con su
tabla rellena vale más que darle una lista.

## 10. Impacto sobre módulos existentes

**Nuevos:** `analyzer/medicion.py`, `analyzer/medicion_pdf.py`,
`agente/herramientas/medicion.py` y sus tests.
**Consumido sin modificar:** `analyzer/parser.py`, `analyzer/evaluator.py`
(el reparto en viviendas **se usa**, no se reimplementa), y los guardianes de
`agente/herramientas/plano.py`.
**No se toca:** el runtime de `agente/`.

## 11. Plan de implementación

Ejecutado en un cambio: el cálculo puro, el documento, las dos capacidades con
sus manifiestos, contrato congelado, golden, y los tests de los seis criterios.

## 12. Plan de pruebas

Unitarias del cálculo; de contrato para las dos capacidades incluido el camino de
fallo; golden contra un fixture de dos viviendas —congelarlo contra el piso de
una sola dejaría sin vigilar el motivo por el que la capacidad existe—; y contra
los dos planos reales del cliente.

## 13. Métricas para medir el éxito

1. Planos que antes no entraban y ahora sí.
2. Cero incidencias de original modificado.
3. Que la separación por efecto se mantenga: el día que alguien pida
   autorización para medir, se ha perdido.

## 14. Posibles motivos para NO implementar la idea

**1. Cruza el tope de `C4` con el corpus vacío.** El argumento de `C4` es que
añadir capacidades con el corpus vacío amplifica el riesgo de alucinación
normativa. Estas dos miden geometría y no consultan ni una norma, así que el
riesgo concreto que `C4` nombra no sube — pero **el tope es el tope**, y saltarlo
con un buen argumento es como se saltan todos los topes. Por eso el test quedó en
rojo en vez de ajustarse.

**2. Podría haber sido una limitación menos en las capacidades del cuadro.** Se
descartó con motivo (§9 R-3), pero es la alternativa honesta y habría dejado el
catálogo en 11.

**Recomendación:** mantener, y resolver `D-12` antes de añadir la siguiente.

---

**Decisión: APROBADO por Pablo el 2026-08-19.** Lo aprobado es lo que describe este documento; lo que quede fuera de él vuelve a necesitar PRD.
