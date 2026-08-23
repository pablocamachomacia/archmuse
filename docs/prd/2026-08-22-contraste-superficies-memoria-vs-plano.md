# PRD — Contraste de superficies: memoria (PDF) contra plano (DXF)

**Estado:** **APROBADO, pendiente de validación de mercado** · **Fecha:** 2026-08-22 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo, 2026-08-22

> **Gate de arranque (orden expresa de Pablo, 2026-08-22).** Aprobado como
> documento, **sin licencia de implementación**. No se escribe código hasta que
> se cumplan LAS DOS condiciones: (1) fin de la congelación de `analyzer/`,
> `scripts/` y `tests/fixtures/` el jueves 2026-08-28; y (2) — la decisiva —
> **confirmación explícita de Pablo de que hay dolor real** (tasa de
> discrepancias medida en proyectos visados de un estudio real, §14.1).
> Sin esa confirmación, este PRD no arranca aunque pase el jueves.

> **Excepción a la congelación, autorizada por Pablo el 2026-08-23.** Se tocó
> `analyzer/acta_legible.py` —dentro del alcance congelado— para arreglar un
> defecto vivo: el motivo de fallo repetido 7 veces en la respuesta de
> coherencia, más el titular de veredicto que faltaba. Motivo de la excepción:
> hace falta para una demo, y el trabajo es del día **23**, así que no compite
> con la validación del corpus del **25-26** que esta congelación protege.
>
> **A comprobar cuando se haga esa validación (25-26):** que este cambio no la
> afecta. Ya hay con qué — el guardián de regresión está capturado: las actas
> normalizadas de `V5.dxf` y `v2s.dxf` de antes y después del cambio son
> idénticas, y el script que las regenera queda descrito en la entrada del
> 2026-08-23 de `PROGRESS.md`. Si esa comparación sigue en verde, el cambio es
> ortogonal a la validación y no hay nada que revisar.

> **Veredicto previo, dicho por delante.** El encargo original era «un lector de
> planos DXF que extraiga la superficie de cada estancia». **Eso ya existe y
> está testeado**: `analyzer/parser.py::leer_plano` (capa flexible con
> `capas_candidatas` y negativa explícita `CapaIndeterminada`; unidades por
> `$INSUNITS` × plausibilidad con parada `EscalaIndeterminada`; cruce
> rótulo↔polígono con `match_label_to_room`) y
> `analyzer/medicion.py::medir_planta` (superficie por estancia en m²,
> `"(sin rótulo)"` para piezas sin texto; PRD `TL-11` aprobado el 19-08).
> Reconstruirlo sería duplicar — justo lo que el propio encargo prohíbe. Este
> PRD propone en su lugar **el hueco real**: hoy lo medido no tiene contra qué
> compararse. No existe lector del cuadro de superficies de la memoria en PDF,
> ni casador declarado↔medido, ni delta. Eso es lo que se construye.

---

## 1. Problema que resuelve

La discrepancia entre el cuadro de superficies de la memoria y lo dibujado en
los planos es causa real de requerimientos de subsanación, y hoy ArchMuse no
puede detectarla: `analyzer/coherencia.py::revisar` compara el DXF **consigo
mismo** (y el contraste cuadro↔dibujo del `ACAD_TABLE` es por nombres y
recuentos, nunca por m²). Viene del giro estratégico aprobado por Pablo el
2026-08-22 (Camino B: control de calidad pre-visado, «memoria PDF vs planos
DXF» como V1) y de la propia spec de construcción (`CLAUDE.md` §1: «detectar
que el cuadro de superficies de la memoria no cuadra con los planos antes de
visar»; hito M2).

## 2. Usuario afectado

El arquitecto redactor, antes de visar o pedir licencia. El usuario de hoy, no
uno futuro.

## 3. Objetivo de negocio

Primer entregable del Camino B y diferencial verificable frente a D-LINIEX:
nosotros **medimos** el plano y **contrastamos** contra lo declarado; no
pedimos las cifras a mano. Es además el criterio M2 de la spec — «el corazón
económico» — acotado a superficies.

## 4. Objetivo técnico

Comportamiento observable una vez implementado:

1. Dado un PDF de memoria con texto nativo y un DXF, el sistema devuelve una
   lista de contrastes: cada estancia casada con su cifra declarada, su cifra
   medida, el delta con signo y la procedencia de ambos lados (página del PDF;
   capa/escala/handle del DXF).
2. La extracción del PDF es **determinista** (pdfplumber o `pypdf`, sin IA en
   ninguna cifra — regla de oro de `CLAUDE.md` §1). PDF escaneado o tabla no
   reconocible → fallo explícito con mensaje, nunca aproximación.
3. Lo que no casa (estancia declarada sin par medido, o al revés) se declara
   **no reconciliado**. Nunca se adivina un emparejamiento (regla M1 de la
   spec: un falso emparejamiento es peor que un hueco).
4. Piezas nuevas, todas funciones puras sobre datos (C1: cualquier invocador —
   Flask, capacidad del agente, futuro plugin — solo invoca):
   - `analyzer/memoria_lector.py` — PDF → `CuadroDeclarado`.
   - Contrato `SuperficieDeclarada`: estancia, tipo (útil/construida), valor
     m², página y fragmento de origen. Procedencia obligatoria, sin ella el
     dato no se construye.
   - `analyzer/contraste_superficies.py` — casador por nombre normalizado
     (reutilizando la normalización de rótulos de `medicion.clasificar`) +
     delta con tolerancia configurable.
   - Adaptador plano sobre `medir_planta`: lista ordenada
     `[{estancia, superficie_m2, unidad, procedencia}]` (hoy `a_dict()`
     devuelve árbol viviendas→piezas; la unidad y la procedencia existen a
     nivel de plano y se propagan por fila — se adapta formato, no se recalcula
     nada).

## 5. Casos de uso

**CU-1 · Contraste pre-visado.** Memoria PDF + DXF → lista de deltas y no
reconciliados. El caso central.

**CU-2 · Solo medir.** El adaptador plano vale por sí mismo como salida de
`medir_planta` comparable a mano, sin memoria.

**CU-3 · Discrepancia plantada.** El arquitecto corrige la memoria, vuelve a
pasar el contraste y la lista queda limpia.

## 6. Casos límite

| Caso | Qué pasa |
|---|---|
| PDF escaneado (sin capa de texto) | Fallo explícito: «no puedo leer este PDF», fuera de alcance V1 |
| Memoria sin cuadro de superficies reconocible | Se dice, con lo que sí se encontró; nunca se devuelve cuadro vacío como si fuera «0 discrepancias» |
| Estancia declarada sin par en el plano (o al revés) | Hallazgo «no reconciliado», nunca casado a la fuerza |
| Dos estancias medidas candidatas para una declarada | Ambigüedad explícita: se pregunta, no se elige |
| Unidad del DXF indeterminable | `EscalaIndeterminada` del pipeline existente — se para y se pregunta, como hoy |
| Cifras con coma decimal, «m2»/«m²», útil vs construida mezcladas | La V1 reconoce ambos separadores y exige tipo de superficie identificable; si el tipo no se distingue, la cifra queda como no contrastable, no se asume útil |

## 7. Flujo del usuario

Ruta del DXF + ruta del PDF de la memoria → medición (pipeline existente) →
lectura del cuadro declarado → casado → lista de contrastes con deltas y no
reconciliados, cada cifra con su procedencia. Ningún fichero de entrada se
modifica (mismos guardianes de lectura que `TL-11`).

## 8. Criterios de aceptación

1. Con un proyecto real y **una discrepancia plantada** en la memoria, el
   sistema la localiza (estancia y documento), cuantifica el delta **con el
   signo correcto** y la lista con la procedencia de ambos lados (criterio M2
   de la spec).
2. Ninguna cifra del resultado sin procedencia (invariante
   `test_no_orphan_numbers` del repo, extendido a `SuperficieDeclarada`).
3. Lo no casado aparece como no reconciliado; no existe ningún camino de
   código que empareje por debajo del umbral de confianza.
4. Cero llamadas a LLM en todo el camino de las cifras.
5. Los ficheros de entrada conservan su sha256, verificado antes y después.
6. Un PDF escaneado produce un fallo explícito, no un resultado vacío.

## 9. Riesgos

**R-1 · Variabilidad de formatos de memoria.** Cada estudio maqueta su cuadro
a su manera. *Mitigación:* desarrollar contra un corpus real (memorias de
un estudio real) y declarar honestamente qué formatos se
reconocen; lo no reconocido falla explícito (§6).

**R-2 · Falso emparejamiento.** Peor que un hueco: acusaría una discrepancia
donde no la hay o taparía una real. *Mitigación:* umbral conservador, la
ambigüedad se pregunta, y el plan de pruebas incluye casos adversarios
(estancias homónimas, «Dormitorio 1» vs «Dorm. 1» vs «D1»).

**R-3 · Competencia por tiempo.** La semana del 25 está tomada por la
validación del corpus (lunes 25, martes 26) y `analyzer/`, `scripts/` y
`tests/fixtures/` están **congelados hasta el jueves 28**. *Mitigación:* este
PRD no arranca código antes del jueves 2026-08-28; la aprobación puede ser
anterior.

**R-4 · Que el Camino B no valide.** El plan estratégico del 22-08 condiciona
todo a la validación (test de D-LINIEX con discrepancias plantadas + tasa real
de discrepancias en proyectos visados). Si sale negativa, este PRD muere con
ella — ver §14.

## 10. Impacto sobre módulos existentes

**Nuevos:** `analyzer/memoria_lector.py`, `analyzer/contraste_superficies.py`,
el adaptador plano (función nueva en `medicion.py` o módulo propio, a decidir
en T1) y sus tests.
**Consumido sin modificar:** `parser.py::leer_plano`, `medicion.py::medir_planta`,
`escala.py`, guardianes de lectura de `agente/herramientas/plano.py`.
**No se toca:** `coherencia.py` (el contraste vive aparte; integrarlo en
`revisar` será un PRD posterior), el runtime de `agente/` y su catálogo de
capacidades (C4: registrar la capacidad agéntica queda explícitamente fuera de
esta V1 — con `D-12` sin resolver, no se añade la 15ª), la SPA, `app.py`.
**Dependencia nueva:** pdfplumber (o ninguna, si `pypdf` ya presente basta —
se decide en T3 con el corpus real delante).

## 11. Plan de implementación dividido en pequeñas tareas

Inicio: **jueves 2026-08-28** (fin de la congelación). Tareas ≤2h:

- **T1** — Adaptador plano sobre `medir_planta` con unidad y procedencia por
  fila, ordenado (vivienda, rótulo). Tests unitarios.
- **T2** — Contrato `SuperficieDeclarada` + `CuadroDeclarado` con procedencia
  obligatoria. Tests de construcción inválida.
- **T3** — Lector PDF determinista contra 2-3 memorias reales de ese estudio;
  fallo explícito para escaneado/no reconocido. Tests con fixture PDF sintético
  pequeño versionado.
- **T4** — Casador + deltas con tolerancia; no reconciliados y ambigüedades
  explícitas. Tests adversarios de nombres.
- **T5** — Fixture end-to-end versionado: DXF sintético reducido (3 viviendas,
  patrón de V5.dxf, que NO se versiona — archivo de cliente >18MB, decisión
  previa) + PDF de memoria generado con discrepancia plantada. Test del
  criterio §8.1.
- **T6** — De paso (deuda detectada en la exploración): `tests/test_escala.py`,
  `test_capas.py` y `test_leer_plano.py` son scripts standalone que pytest no
  recoge — convertirlos a tests recolectables sin cambiar lo que comprueban.

## 12. Plan de pruebas

Unitarias por tarea (§11); end-to-end del criterio §8.1 sobre el fixture
sintético de T5; validación manual contra los dos planos reales del cliente
(V5.dxf, v2s.dxf vía `ARCHMUSE_DXF_PLANTA`) con sus memorias reales; y la
suite completa existente (~950 tests) en verde — nada de lo consumido se
modifica, así que cualquier rojo es regresión.

## 13. Métricas para medir el éxito

1. Discrepancias reales encontradas en los proyectos ya visados de ese estudio
   (si es >0, el producto tiene su primera prueba de valor con datos).
2. Cero falsos emparejamientos sobre el corpus de memorias reales.
3. Fracción de memorias reales cuyo cuadro se reconoce (mide R-1; decide si la
   V2 necesita más formatos u OCR).

## 14. Posibles motivos para NO implementar la idea

1. **La validación de mercado aún no está hecha.** El plan del 22-08 antepone
   una semana de validación (D-LINIEX + tasa de discrepancias). Lo honesto es
   aprobar este PRD condicionado a ese resultado — si la tasa real de
   discrepancias es ~0, esto es una feature sin dolor detrás.
2. **La extracción de PDF puede ser más frágil de lo previsto.** Si las
   memorias reales derrotan al lector determinista, la alternativa (extracción
   asistida por IA con validación humana obligatoria, patrón
   `pliego_extractor.py` + regla M3 de ordenanzas) es un PRD distinto con otro
   perfil de riesgo — no se cuela aquí por la puerta de atrás.
3. **Alternativa descartada:** reconstruir el «lector DXF» pedido
   originalmente. Ya existe; duplicarlo solo añadiría superficie de fallo sin
   diferencial ninguno.

---

**Decisión: APROBADO por Pablo el 2026-08-22, pendiente de validación de mercado.**
La implementación queda bloqueada hasta la confirmación explícita de Pablo de que
la validación de la §14.1 salió positiva (además del fin de la congelación el
jueves 2026-08-28). Lo aprobado es lo que describe este documento; lo que quede
fuera de él vuelve a necesitar PRD.
