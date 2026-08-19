# PRD — Skill de medición de una planta con varias viviendas (`SK-10`)

**Estado:** **APROBADO** (retroactivo) · **Fecha:** 2026-08-19 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo, 2026-08-19

> **Retroactivo, y el motivo por escrito.** `SK-10` se implementó el 2026-08-19
> bajo orden directa de Pablo («elige el siguiente trabajo profesional de mayor
> valor, impleméntalo de principio a fin y pruébalo con un proyecto real») y
> **sin PRD previo**, contra la regla de `CLAUDE.md`. Este documento recoge lo
> construido en la forma que la regla exige. Depende de `TL-11`, que tiene el
> suyo.

---

## 1. Problema que resuelve

Medir una planta entera pieza a pieza se hace hoy con una calculadora, y **se
rehace entera en cada revisión del plano**: mover un tabique invalida la
medición anterior. Es media tarde por planta y por revisión, y es aritmética —
exactamente el trabajo que una máquina no debería devolverle a una persona.

La Skill del cuadro (`superficies.cuadro_de_vivienda`) no lo cubría: exige que
el plano traiga su `ACAD_TABLE` y que haya una sola vivienda.

## 2. Usuario afectado

El arquitecto que mide una planta de obra nueva —varias viviendas, sin tabla
dibujada— y, sobre todo, el que mide un DXF que no dibujó él.

## 3. Objetivo de negocio

Segundo entregable profesional que **no depende del corpus normativo**, junto con
la revisión de coherencia. Mide y traza; no afirma nada sobre normativa, así que
su valor no espera a ninguna firma colegiada.

## 4. Objetivo técnico

- El procedimiento en el orden que sigue un arquitecto: **unidad primero**,
  separar viviendas por los rótulos que puso él, **auditar ese reparto**, medir,
  cruzar la suma contra la geometría, totalizar sólo lo afirmable, entregar con
  procedencia.
- **La regla dura:** basta **un** impedimento para que una vivienda no lleve
  **ningún** total. Las piezas se miden igual —ahí está casi todo el valor— y el
  impedimento va escrito **con su magnitud**.
- No emite criterio profesional: no dice si una vivienda es pequeña ni si un
  solape es un error del plano.

## 5. Casos de uso

**CU-1 · Medir una planta de tres viviendas.** El caso central.
**CU-2 · Un plano con solapes.** Se miden las piezas y **no** se totaliza, con la
cifra que lo explica.
**CU-3 · Un DXF ajeno.** Saber qué le están dando.

## 6. Casos límite

| Caso | Qué pasa |
|---|---|
| Unidad indeterminable | Para y pregunta antes de medir |
| Piezas solapadas | Piezas medidas, **sin total**, con la magnitud del solape |
| Reparto dudoso entre viviendas medianeras | Igual: se declara y bloquea el total de esa vivienda |
| Rótulo que no dice si la pieza es interior o exterior | Igual |
| Descuadre de redondeo | **No es un impedimento.** Ver §9 R-2 |

## 7. Flujo del usuario

`python scripts/medir_planta.py mi_plano.dxf` — enseña el procedimiento, mide,
escribe el PDF, imprime el acta y no toca el DXF.

## 8. Criterios de aceptación

1. Sobre la planta real de tres viviendas produce los tres cuadros con sus cifras
   exactas.
2. Sobre el plano con solapes se niega a totalizar, con la cifra que lo explica.
3. Ninguna vivienda con un impedimento lleva total.
4. El original conserva su sha256.
5. La Skill no emite criterio profesional.

*(Los cinco comprobados por tests hoy.)*

## 9. Riesgos

**R-1 · La auditoría del reparto, que es lo que separa medir de adivinar.** El
reparto por «etiqueta `VT` más cercana» ya existía y es correcto con las
viviendas separadas; en dos medianeras deja de serlo y **no avisaba de nada**.
*Mitigado:* se mide la holgura de cada pieza (`HOLGURA_MINIMA_DE_REPARTO = 2`,
calibrado contra el plano real, cuya peor pieza tiene 2,67) y un reparto apretado
se declara y bloquea el total.

**R-2 · El descuadre de redondeo, que habría sido el falso positivo de esta
entrega.** La primera versión cruzaba la **suma de las cifras publicadas** contra
la unión geométrica. Redondear ocho piezas y sumarlas da hasta un céntimo de
metro que no es ningún solape: `VT3/3` daba 66,56 contra 66,55 y habría salido
con un aviso de «metros dibujados dos veces» de 0,01 m². Detectado ejecutando
contra el plano real **antes** de escribir el test. *Mitigado:* se cruzan las
magnitudes **crudas**, y el total publicado sigue siendo la suma de las
publicadas para que la tabla cuadre si el arquitecto la suma a mano. Son dos
cifras distintas a propósito.

**R-3 · Falsos positivos en general.** Un hallazgo falso destruye la confianza en
los verdaderos. Los dos que aparecieron (R-1, R-2) salieron de ejecutar contra
planos reales, no de imaginarlos.

**R-4 · Sin PRD previo.** El riesgo de proceso, ya materializado. Este documento
lo cierra.

## 10. Impacto sobre módulos existentes

**Nuevos:** `agente/skills/medicion.py`, `scripts/medir_planta.py`, sus tests.
**Consumido sin modificar:** `TL-11`, `analyzer/parser.py`,
`analyzer/evaluator.py`, `agente/skills/_comun.py`.
**No se toca:** el runtime de `agente/`, ni `parser.py`, ni `evaluator.py`.

## 11. Plan de implementación

Ejecutado en un cambio, sobre `TL-11`: procedimiento declarado, cinco
verificaciones, el guion, y los tests de los cinco criterios contra los dos
planos reales.

## 12. Plan de pruebas

Unitarias con planos sintéticos; los cinco criterios contra `v2s.dxf` y `V5.dxf`,
que se saltan con motivo si no están; y de política, que la Skill no declare
ninguna capacidad de normativa.

## 13. Métricas para medir el éxito

1. Minutos frente a la medición manual.
2. Viviendas totalizadas frente a bloqueadas: si casi todas se bloquean, la regla
   dura es demasiado dura y hay que mirarlo con planos, no con opiniones.
3. Impedimentos que el arquitecto reconoce como reales.

## 14. Posibles motivos para NO implementar la idea

**1. La regla dura puede ser demasiado dura.** Un impedimento menor deja una
vivienda entera sin total. Es deliberado —un total que puede estar mal se copia a
la memoria y se firma; la ausencia se pregunta— pero si en la práctica bloquea
casi todo, el producto entrega menos de lo que podría. **Es la métrica nº2 y hay
que mirarla.**

**2. Compite con el corpus.** Como todo lo que no es `NOR-2`. La defensa es la de
siempre: transcribir normativa no lo hace un programador.

**3. Añadió dos capacidades con el corpus vacío**, cruzando el tope de `C4`. Ver
el PRD de `TL-11` §14 y `D-12`.

**Recomendación:** mantener. El valor está medido contra dos planos reales y los
dos falsos positivos que aparecieron están corregidos con su test.

---

**Decisión: APROBADO por Pablo el 2026-08-19.** Lo aprobado es lo que describe este documento; lo que quede fuera de él vuelve a necesitar PRD.
