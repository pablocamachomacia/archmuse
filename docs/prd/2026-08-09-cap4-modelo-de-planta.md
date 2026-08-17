# PRD — CAP-4: Modelo de planta

**Estado:** Aprobado · **Fecha:** 2026-08-09 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (2026-08-09)

> **Modificación de Pablo sobre el borrador original:** `C01` parcial (límite de 2.500 m² por planta) **deja de ser tarea opcional y
> pasa a ser criterio de cierre obligatorio de CAP-4.** Razón de producto y arquitectura, textual: *"CAP-4 debe terminar entregando
> al menos una capacidad normativa consumidora del nuevo hecho `planta`. No quiero crear una capa de datos que simplemente quede
> esperando CAP-5."* Este documento incorpora esa modificación en §4, §5, §6, §8, §9, §10, §11 y §14; el resto del borrador aprobado
> se mantiene sin cambios de fondo.

**Diseño de referencia:** `docs/design/DB-SI_FACT_MODEL.md` §2.1, §3.3, §4.2, §9, §12.4 (modelo `edificio → uso_previsto_principal →
planta → zona → uso_previsto → recintos`, ya decidido, no implementado; y el hallazgo de que `superficie_construida` **no es
obtenible del DXF actual**, clave para la definición precisa de `C01` en §4ter) y `docs/audits/DB-SI_IMPLEMENTATION_PLAN.md` §2
(ficha `CAP-4`), §3 (grafo de dependencias), §6 (qué desbloquea), §12 (Bloque C). Ambos documentos, junto con `DB-SI_DECISIONS.md`,
están commiteados en `bd1a62f`.

**Alcance de este PRD:** el hecho `planta` a nivel de `Unit` (misma granularidad que CAP-2/CAP-3: una planta por vivienda, no por
recinto), la corrección del ámbito de `ocupacion` que depende de él, y **la regla `C01` parcial (límite de 2.500 m² por planta) como
primera consumidora normativa del hecho `planta`, con criterio de cierre obligatorio**. **No incluye** el modelo completo de `zona`
(varias zonas con usos distintos por planta — sigue reservado, tal como `DB-SI_FACT_MODEL.md` §4.2 ya decidió), el EI 60 de `C01`
(bloqueado por `CAP-8`, fuera del alcance del formato DXF), ni CAP-5, ni CAP-6, ni ninguna regla de evacuación nueva.

---

## 1. Problema que resuelve

`analyzer/ocupacion.py` (CAP-3, commit `bd1a62f`) emite el hecho `ocupacion` con un parche declarado desde el primer día:

```python
# El ámbito real de la tabla es la planta; sin CAP-4 se emite por vivienda.
ambito_provisional = {
    "ambito_normativo": "planta (Tabla 2.1: «Plantas de vivienda»)",
    "ambito_emitido": "vivienda",
    "agregado_no_normativo": True,
    "motivo_del_desvio": "ArchMuse no modela plantas hasta CAP-4",
}
```

Esto es honesto — mejor un ámbito declarado como provisional que uno silenciosamente equivocado — pero es un parche **incondicional**:
se emite siempre, para todo proyecto, sin excepción, porque no existe ningún mecanismo para que sea de otra forma. La Tabla 2.1 del
DB-SI indexa *"Plantas de vivienda"*, no vivienda; agregar por vivienda es cómodo pero no es lo que la norma mide
(`DB-SI_IMPLEMENTATION_PLAN.md` riesgo #2, §14).

Consecuencia concreta ya registrada: `C01` (sectorización, límite de 2.500 m² por sector de incendio) no es evaluable ni parcialmente
porque ArchMuse no tiene forma de agregar superficie construida por planta (`DB-SI_IMPLEMENTATION_PLAN.md` §6, fila `CAP-4`).

Origen: decisión explícita diferida en el propio código y en `DB-SI_FACT_MODEL.md` §9 desde el cierre de CAP-3; no es una idea nueva,
es completar un contrato que ya existe y que cita su propia deuda.

## 2. Usuario afectado

**Hoy:** el arquitecto que analiza cualquier DXF con `/api/analizar` ve, en el JSON de proyecto, una ocupación con
`"ambito_normativo": "planta (...)"` y `"ambito_emitido": "vivienda"` sin ninguna vía para que ArchMuse sepa que es una sola planta y
cierre esa discrepancia — el parche es permanente, no transitorio, para el 100 % de los proyectos analizados hasta hoy.

**Objetivo (`NORTH_STAR_2031.md`, vía `MOAT_ANALYSIS.md` §1):** el arquitecto de 20 años de oficio que decide si confía su firma a
ArchMuse precisamente porque cita el artículo real. Ese mismo perfil es el que nota cuando el ámbito citado (planta) no coincide con
el ámbito calculado (vivienda) — es la clase exacta de discrepancia que erosiona la credibilidad que sostiene el precio.

## 3. Objetivo de negocio

1. **Cerrar una discrepancia que el propio producto ya se auto-diagnosticó.** No es una funcionalidad especulativa: es la brecha entre
   lo que `MOAT_ANALYSIS.md` §1 promete ("cita el artículo real") y lo que el código admite hacer hoy.
2. **Desbloquear valor parcial pero real:** `C01` con el límite de superficie (sin EI 60, que sigue en `CAP-8`) — la única regla nueva
   que CAP-4 en solitario puede activar, según §6.
3. **Es la pieza que CAP-5 necesita para existir.** El objetivo de negocio de CAP-5 (altura de evacuación, condiciones de activación de
   `C11`/`C15`/`C18`) no se puede perseguir sin esto — ver §14 y la sección "Dependencias" al final.

## 4. Objetivo técnico

Una vez implementado, debe ser observable que:

- Existe un hecho `planta` (`analyzer/planta.py`), con los mismos cuatro elementos que todo hecho del contrato (`hechos.py`): estado,
  confianza, procedencia, motivo si es `UNKNOWN`.
- `ocupacion()` deja de emitir el parche incondicional. El ámbito real ("planta N", con su posición sobre/bajo rasante) se emite
  **cuando y sólo cuando** el hecho `planta` correspondiente es `KNOWN` o `ESTIMATED`. Cuando `planta` es `UNKNOWN`, el comportamiento
  es el actual, sin cambios — no una versión distinta del parche, el mismo parche, ahora **condicional y explicado por una causa
  concreta** en vez de incondicional.
- Existe una regla `C01` parcial (`analyzer/sectorizacion.py`, nuevo — no `evaluator.py`) que consume `planta` + `superficie_util_db_si`
  (CAP-1) y produce `FAIL`/`UNKNOWN` sobre el límite de 2.500 m² por planta, nunca un `PASS` sin fundamento (definición precisa en
  §4ter). Es la capacidad normativa que cierra CAP-4: **sin ella, este PRD no se considera terminado.**
- **Ningún nombre de vivienda (`VT1/3`, `VT2/2`, `VT6/2`...) se interpreta jamás como número de planta, en ningún módulo, para ningún
  fin — ni para `planta` ni para `C01`.** El identificador tras `VT` es el tipo de vivienda dentro de la convención de rotulado del
  DXF (`group_rooms_by_unit_label`), no una posición en el edificio; no tiene ninguna relación semántica con planta. Es una
  prohibición de diseño, no sólo de implementación: no debe existir ningún camino de código, ni siquiera como *fallback* o
  aproximación de última instancia, que derive `planta` de ese patrón. Test dedicado en §12.
- `ejemplo.dxf` — la única muestra real disponible, y que no declara planta en ningún sitio — **no cambia ni un número en `ocupacion`**:
  las 4 `ESTIMATED` y 2 `UNKNOWN` que fijó CAP-3 se mantienen exactamente iguales, ahora con `agregado_no_normativo: true` explicado
  por "planta no declarada para este proyecto" en lugar de "ArchMuse no modela plantas hasta CAP-4" — la frase cambia porque ya no es
  cierta; el dato no cambia porque nadie lo ha declarado. Y `C01` sobre `ejemplo.dxf` sale `UNKNOWN` por el mismo motivo (planta no
  declarada) — no hay ningún salto mágico a un veredicto sobre la única muestra real, y hay que decirlo así de claro.

### 4bis. Las tres fuentes de `planta`, sin ambigüedad entre ellas

| | Planta **declarada** | Planta **estimada por convención** | Planta **desconocida** |
|---|---|---|---|
| Estado del hecho | `KNOWN` | `ESTIMATED` | `UNKNOWN` |
| Fuente | Campo de formulario de `/api/analizar`, rellenado explícitamente por el arquitecto | Prefijo `Planta <n> · <nombre>` del nombre de unidad, **sólo** en el flujo `/api/generar` (§10) | Ninguna de las dos anteriores está presente |
| Confianza | Alta | Media — depende de que se haya seguido la convención, no de una afirmación directa | — (no aplica confianza a un valor ausente) |
| Naturaleza (`DECISION_ENGINE.md` §11) | Hecho | Inferencia mecánica sobre un patrón de texto — **no** una hipótesis libre; el patrón es determinista, la incertidumbre es sobre si el nombre miente | — |
| Prevalece sobre | La estimada, si ambas existen y difieren (§6) | Nada — es la fuente más débil que aun así cuenta | — |
| ¿Puede venir de `VT1/3`, `VT2/2`...? | **No, nunca** | **No, nunca** | Es precisamente lo que produce este caso |
| ¿Puede venir de geometría (solape de huellas, cota Z)? | **No, prohibido por diseño** (§9, riesgo heredado de `_discard_container_candidates`) | **No, prohibido por diseño** | — |

**Sobre por qué no hay una cuarta fuente "inferida por geometría":** `DB-SI_IMPLEMENTATION_PLAN.md` ya lo advierte para CAP-4 en su
propia ficha: *"La detección automática por solape de huellas es tentadora y engañosa — el propio motor ya aprendió esa lección con
`_discard_container_candidates`."* CAP-4 no reabre esa lección.

### 4ter. Definición precisa de `C01` (límite de 2.500 m² por planta)

**Qué exige la norma, citado:** DB-SI 1 §1 (corregido de `CTE-DB-SI-3`, la cita errónea que usa hoy `evaluator.py` para un chequeo
distinto — ver nota de colisión en §10) fija 2.500 m² como superficie máxima de un sector de incendio, con el sector típico
coincidiendo con la planta en el caso residencial sin más declaración.

**Qué superficie se compara — y por qué no es la ideal.** La norma mide **superficie construida** por sector. `DB-SI_FACT_MODEL.md`
§3.3 ya estableció, con evidencia medida (reconstrucción por casco convexo: error del −24 % al +49 % sobre `ejemplo.dxf`, *"no es una
aproximación con margen: es ruido"*), que **`superficie_construida` no es obtenible del DXF actual** y queda `UNKNOWN` por diseño.
CAP-4 no resuelve esa carencia — sería inventar una fuente que no existe. En su lugar, `C01` compara la **suma de
`superficie_util_db_si` (CAP-1, D6: incluye terrazas) de todas las unidades cuya `planta` resuelve al mismo número**, declarada
explícitamente como proxy, nunca renombrada como superficie construida.

**La dirección del error importa, y fija el rango de veredictos posible:**

`superficie_util_db_si` mide a cara interior de muro (excluye espesor de cerramientos y elementos comunes) — es **sistemáticamente
menor o igual** que la superficie construida real. Por tanto:

| Suma de `superficie_util_db_si` de la planta | Veredicto | Por qué es válido |
|---|---|---|
| **≥ 2.500 m²** | **FAIL** | Si el proxy (que subestima) ya supera el límite, la construida real también lo supera. Dirección segura |
| **< 2.500 m²** | **UNKNOWN** — *nunca `PASS`* | El proxy subestima por un margen no acotado con fiabilidad (§3.3: hasta +49 % medido). Que el proxy esté por debajo no prueba que la construida real lo esté |

**Consecuencia que hay que decir sin rodeos antes de implementar:** con los datos que el DXF puede dar hoy, **`C01` no puede emitir
`PASS` en la práctica.** No es un defecto de esta implementación: es que ArchMuse no tiene, y no puede reconstruir con fiabilidad, el
dato que un `PASS` de sectorización exigiría. `C01` con estos datos es, en efecto, un detector de sectores que seguro que exceden el
límite — no un certificador de que no lo excedan. Se documenta así en `explicacion` y en la ficha de la regla, para que no se lea como
una comprobación incompleta por descuido.

**Qué ocurre si `planta` es `UNKNOWN`:** `C01` es `UNKNOWN` para esa unidad/planta, con motivo *"no se puede agregar por planta: la
planta no está declarada"* y procedencia que apunta al hecho `planta` concreto. No se agrega con el resto de unidades del proyecto
bajo ningún supuesto de "misma planta por defecto".

**Qué ocurre si `superficie_util_db_si` de alguna unidad de la planta es `UNKNOWN`** (p. ej. por solape geométrico, D3 de
`DB-SI_DECISIONS.md` — el caso de VT5/1 y VT6/2 en `ejemplo.dxf`): se suman primero las unidades `KNOWN`/`ESTIMATED` de esa planta.
Si esa suma parcial **ya** alcanza 2.500 m², el veredicto es `FAIL` (razonamiento monótono: una unidad adicional, aunque no se pueda
medir, no puede restar superficie). Si la suma parcial no alcanza 2.500 m², el veredicto es `UNKNOWN` — no se puede descartar que la
unidad no medida complete el resto, y tampoco se puede afirmar que lo complete.

**Nunca se convierte `UNKNOWN` en `PASS` ni en `FAIL` por comodidad, en ningún punto de esta cadena.** Es la aplicación literal de D3
de `DB-SI_DECISIONS.md` a la primera regla real que CAP-4 activa.

## 5. Casos de uso

**CU1 — Proyecto DXF de una sola planta, arquitecto la declara.** El formulario de `/api/analizar` incluye un campo opcional "planta
de este proyecto" (p. ej. "Planta 1ª", "Planta baja", "Sótano 1"). Declarado, `planta` sale `KNOWN`, confianza Alta, y `ocupacion` se
emite con ámbito "planta 1ª" real, sin agregado.

**CU2 — Proyecto sin declarar planta (el caso de `ejemplo.dxf` hoy).** `planta` sale `UNKNOWN` con motivo explícito
("no se ha declarado la planta de este análisis"). `ocupacion` mantiene el comportamiento actual: ámbito vivienda, marcado como
agregado no normativo, con cadena causal que ahora incluye el motivo real de `planta`.

**CU3 — Proyecto generado por `/api/generar` con la convención `Planta <n> · <nombre>` ya existente.** `app.py` extrae el número con
`_PLANTA_NAME_PATTERN` (reutilizado de `evaluator.py`, no duplicado) y lo pasa a `planta()` como fuente "convención de nombre".
`planta` sale `ESTIMATED` (no `KNOWN`: es una inferencia sobre un patrón de texto, no una declaración explícita en un campo dedicado),
confianza Media. `ocupacion` hereda esa confianza como su eslabón más débil (`_peor_confianza`, ya existente).

**CU4 — Edificio realmente multiplanta subido como un único DXF por `/api/analizar`.** Fuera de alcance de CAP-4 v1 (§14, no-goals).
El formulario de un solo campo "planta de este proyecto" no lo modela; el resultado es `UNKNOWN` para todas las unidades, igual que
CU2 — comportamiento honesto, no un error.

**CU5 — Planta declarada cuya suma de `superficie_util_db_si` supera 2.500 m².** `C01` sale `FAIL`, con la cita DB-SI 1 §1, el
desglose de qué unidades componen la suma y su ámbito ("planta 1ª"), y la advertencia explícita de que la comparación usa un proxy
que subestima la superficie construida real (§4ter) — el `FAIL` es, si acaso, optimista, nunca alarmista de más.

**CU6 — Planta declarada cuya suma no llega a 2.500 m² (el caso más común, probablemente, de vivienda plurifamiliar por planta).**
`C01` sale `UNKNOWN`, no `PASS`, con la explicación de que `superficie_construida` no es obtenible del DXF actual. Es el caso que más
fácil sería "arreglar" relajando el criterio, y es exactamente el que este PRD prohíbe relajar.

## 6. Casos límite

| Caso | Comportamiento exigido |
|---|---|
| DXF sin ninguna declaración de planta | `UNKNOWN` explícito, propaga a `ocupacion` exactamente como hace hoy `uso_previsto`/`superficie_util` cuando faltan (D3 de `DB-SI_DECISIONS.md`) |
| Nombre de vivienda `VT1/3`, `VT2/2`... | **Prohibido inferir planta de aquí bajo cualquier circunstancia.** El número tras `VT` es el tipo de vivienda, no la planta. Test dedicado que falla si `planta.py` o `app.py` intentan parsear `VT\d` como planta |
| Declaración de planta contradictoria con la convención `_PLANTA_NAME_PATTERN` (p. ej. formulario dice "Planta 2" y el nombre de unidad dice "Planta 3 · X") | La declaración explícita (KNOWN) **prevalece siempre** sobre la convención de nombre (ESTIMATED) — mismo principio que ya usa `ocupacion()` para la salvedad de ocupación declarada (D-SI 3 ap. 2). Se registra el conflicto en `diagnostico`, no se descarta en silencio |
| Proyecto de una sola unidad, sin ninguna fuente | `UNKNOWN`. **No se asume "planta única" por ser el caso más común** — sería exactamente el patrón que `DECISION_ENGINE.md` §12 prohíbe (completar el vacío con un valor por defecto que pase por dato real) |
| Campo de planta declarado con texto no parseable ("varias", "?") | `UNKNOWN` con motivo "declaración de planta no interpretable", nunca un `KNOWN` forzado |
| `/api/generar` con una unidad cuyo nombre no casa `_PLANTA_NAME_PATTERN` (ninguna planta en el prefijo) | `UNKNOWN` para esa unidad — mismo comportamiento silencioso-a-explícito que ya corrigió CAP-3 para el solape geométrico (D3) |
| Sótano o planta bajo rasante | Debe poder declararse (booleano `sobre_rasante`), y se conserva en el hecho `planta` aunque `C01` v1 **no lo use para variar el límite de 2.500 m²** — el corpus ingerido no tiene, verificada, una cifra distinta para sótano, y no se inventa una (D2 de `DB-SI_DECISIONS.md`: no añadir umbrales que la norma no ha demostrado dar). Lo pide `CAP-5` (§14, dependencias) y es más barato declararlo ahora que añadirlo después |
| Dos o más unidades con `planta` `KNOWN` en distinto número dentro del mismo proyecto (`/api/generar`, CU3) | `C01` agrega **por número de planta resuelto**, no por proyecto: cada planta se evalúa contra 2.500 m² de forma independiente |
| Suma de `superficie_util_db_si` de la planta por debajo de 2.500 m² con **todas** las unidades `KNOWN` (sin ninguna `UNKNOWN` de por medio) | Sigue siendo `UNKNOWN`, no `PASS` (§4ter) — el motivo no es la falta de un dato de la planta, es que el proxy nunca puede demostrar el límite por abajo |
| Una unidad con `superficie_util_db_si` `UNKNOWN` cuyas hermanas de planta **ya** suman ≥ 2.500 m² | `FAIL` igualmente (razonamiento monótono, §4ter) — no se retrasa el `FAIL` a la espera de un dato que sólo podría aumentar la suma |

## 7. Flujo del usuario

1. En el formulario de `/api/analizar`, junto a "Ciudad" y "Uso previsto" (CAP-2), aparece un campo opcional: "Planta de este
   análisis" — texto libre con ayuda ("Planta baja", "Planta 3ª", "Sótano 1"), sin valor por defecto.
2. Si se rellena y es interpretable, el backend lo normaliza a `(numero: int, sobre_rasante: bool)` y construye el hecho `planta`
   `KNOWN`.
3. Si se deja vacío, `planta` sale `UNKNOWN` — el análisis continúa exactamente igual que hoy, sin bloquear nada.
4. En `/api/generar`, el flujo no cambia de cara al usuario: el número de planta ya se declara al generar la distribución
   (`edificio.plantas`, `app.py`). CAP-4 conecta ese dato ya existente con el nuevo hecho, vía la convención de nombre (CU3).
5. El informe (JSON) expone `proyecto.planta` (nuevo) y actualiza `proyecto.ocupacion[].ambito`/`ambito_normativo` para reflejar el
   estado real, tal como ya hace con `proyecto.usos` desde CAP-2/3.

## 8. Criterios de aceptación

1. `analyzer/planta.py` existe, expone una función `planta(...)` que devuelve un `Hecho` con las cuatro propiedades del contrato
   (`hechos.py`), y no importa nada de `evaluator.py`, `analyzer/adyacencia.py` ni `normativa/` — mismo aislamiento que `ocupacion.py`,
   `uso_previsto.py`, `superficie_util.py`.
2. `ocupacion()` acepta un parámetro `planta: Optional[Hecho] = None`. Con `planta=None` o `planta.estado == UNKNOWN`, la salida es
   **byte a byte idéntica** a la de `bd1a62f` salvo el texto de `motivo_del_desvio` (test de equivalencia, como el que ya protege la
   extracción de `_superficie_suelo_agregada_m2`).
3. Con `planta.estado in (KNOWN, ESTIMATED)`, `ocupacion.ambito` deja de decir "vivienda" y pasa a identificar la planta real;
   `diagnostico["agregado_no_normativo"]` pasa a `False`; la confianza de `ocupacion` incorpora la de `planta` como insumo adicional
   del eslabón más débil.
4. Ningún test ni código de producción deriva un número de planta de un nombre de vivienda con prefijo `VT`. Verificado por un test
   que construye una unidad `VT9/9` sin ninguna declaración y comprueba que `planta` sale `UNKNOWN`, nunca `9`.
5. `ejemplo.dxf` sigue produciendo exactamente 4 `ESTIMATED` + 2 `UNKNOWN` en `ocupacion`, con los mismos valores fraccionarios que
   `bd1a62f` (regresión dura, ver §12).
6. `_PLANTA_NAME_PATTERN`, `compute_floor_areas`, `_floor_rooms`, `compute_floor_perimeter_m` de `evaluator.py` **no se modifican**.
   `planta.py` no los importa; `app.py` sí importa el patrón (reutilizado, no duplicado) para el caso `/api/generar`.
7. `app.py` publica `proyecto.planta` en el payload de `/api/analizar` con la misma forma que `proyecto.usos`/`proyecto.ocupacion`
   (ver §10).
8. No existe ningún camino de código que infiera planta por geometría (cota Z, solape de huellas). Es una prohibición de diseño, no
   sólo de implementación — no hay nada que testear porque no debe existir el código.
9. **`analyzer/sectorizacion.py` existe** y expone la regla `C01`, con código de incidencia **distinto** de `"CTE-DB-SI-3"` (el que ya
   usa `evaluator.evaluate_fire_compartmentation` para un proxy geométrico no relacionado — ver §10). No importa nada de
   `evaluator.py`.
10. Un proyecto con `planta` `KNOWN` (o `ESTIMATED`) para todas sus unidades y suma de `superficie_util_db_si` por planta ≥ 2.500 m²
    produce `C01 = FAIL`, con cita `DB-SI 1 §1`, el desglose de las unidades sumadas y su ámbito, y la advertencia textual de que la
    magnitud comparada es un proxy que subestima la construida real.
11. El mismo proyecto con una suma < 2.500 m² produce `C01 = UNKNOWN`, **nunca `PASS`**, con la explicación de que
    `superficie_construida` no es obtenible del DXF actual (`DB-SI_FACT_MODEL.md` §3.3). Test explícito que falla si `C01` emite
    `PASS` en cualquier escenario del conjunto de pruebas — no debe existir ningún caso semilla que lo produzca.
12. Un proyecto con `planta` `UNKNOWN` produce `C01 = UNKNOWN` con motivo "planta no declarada", sin agregar esa unidad con ninguna
    otra bajo un supuesto de planta compartida.
13. Una planta con una unidad de `superficie_util_db_si` `UNKNOWN` cuyas hermanas ya suman ≥ 2.500 m² produce `C01 = FAIL` (razonamiento
    monótono, §4ter); si la suma parcial no llega, produce `UNKNOWN`.
14. `ejemplo.dxf` produce `C01 = UNKNOWN` para las 6 unidades (planta no declarada en ningún sitio) — regresión explícita, ver §12.

## 9. Riesgos

| Riesgo | Comentario |
|---|---|
| **Sobre-diseño de la jerarquía completa** | `DB-SI_FACT_MODEL.md` §4.2 ya decidió el modelo `planta → zona(1..n)` pero **implementarlo con el mínimo viable**: una zona por vivienda. Este PRD respeta esa nota de alcance a propósito — construir la multiplicidad de zonas ahora, sin ningún consumidor que la necesite, sería la misma sobre-inversión que `DB-SI_IMPLEMENTATION_PLAN.md` riesgo #8 advierte para `CAP-6`/`CAP-7` |
| **Valor casi nulo para la única muestra real** | `ejemplo.dxf` no declara planta en ningún sitio y no la declarará solo porque exista el campo. El resultado inmediato sobre el único dato real disponible es "el mismo `UNKNOWN`, mejor explicado" — no un salto de `UNKNOWN` a `KNOWN`. Hay que decirlo antes de aprobar, no después |
| **Compite por el mismo desarrollador con B1/B2/B3** | El árbol de trabajo tiene ahora mismo tres iniciativas abiertas sin cerrar (motor normativa territorial, fix de scoring/severidad, experimento de grafo). Añadir una cuarta rama de trabajo sin cerrar ninguna de las tres agrava el riesgo que `REFACTOR_MASTERPLAN.md` tarea 1 ya señaló (pérdida de trabajo por árbol sucio) |
| **Tentación de reutilizar `_PLANTA_NAME_PATTERN` como fuente universal** | Ese mecanismo sólo cubre `/api/generar` y ya tiene un defecto documentado (`compute_floor_areas` se llama a sí mismo "superficie construida" sin serlo, `DB-SI_DECISIONS.md` §4.3, pendiente P4.2). CAP-4 debe consumirlo tal cual está, sin heredar ni corregir ese defecto — corregirlo es una tarea aparte, ya registrada, fuera de este PRD |
| **Formulario nuevo que casi nadie rellena** | Mismo patrón que el motivo 2 del PRD de normativa territorial: la arquitectura no vale nada sin el dato. Mitigación: el campo es honesto sobre su propio vacío (`UNKNOWN` explicado), así que no hay coste de tener el campo aunque nadie lo use — a diferencia de un corpus vacío, aquí no hay contenido que curar |
| **Colisión de nombre con la sectorización que ya existe en `evaluator.py`** | `evaluate_fire_compartmentation` ya emite incidencias con código `"CTE-DB-SI-3"` para un proxy geométrico de solape de huella entre viviendas — no relacionado con el límite de 2.500 m². Ambos comparten el campo semántico "sectorización" y es fácil que alguien los confunda o los fusione sin querer. Mitigación: `C01` (este PRD) usa un código de incidencia propio y distinto, documentado en el criterio de aceptación 9; no se toca ni se retagea `evaluate_fire_compartmentation` (eso es Bloque B, trabajo aparte, ya identificado en `DB-SI_IMPLEMENTATION_PLAN.md` §12) |
| **`C01` nunca puede dar `PASS` con los datos de hoy** | Hay que comunicarlo antes de que alguien lo lea como una regla a medio implementar. No es una limitación de esta implementación: es el techo real que impone no tener `superficie_construida`. Mitigación: `explicacion` de la regla lo dice explícitamente en cada `UNKNOWN` (§4ter) |

## 10. Impacto sobre módulos existentes

| Módulo | Cambio |
|---|---|
| `analyzer/planta.py` | **Nuevo.** Hecho `planta`, mismo patrón que `uso_previsto.py`. Sin dependencias de `evaluator.py` ni `normativa/` |
| `analyzer/sectorizacion.py` | **Nuevo.** Regla `C01` (§4ter), consume `planta` + `superficie_util_db_si` (CAP-1). Sin dependencias de `evaluator.py`. Código de incidencia propio, distinto de `"CTE-DB-SI-3"` |
| `analyzer/ocupacion.py` | Firma de `ocupacion()` gana `planta: Optional[Hecho] = None`. El bloque `ambito_provisional` deja de ser incondicional |
| `analyzer/hechos.py` | Sin cambios — se reutiliza tal cual |
| `app.py` | Nuevo campo de formulario (`/api/analizar`); extracción de planta por convención de nombre para `/api/generar` (importa **sólo** la constante `_PLANTA_NAME_PATTERN` de `evaluator.py`, sin duplicarla — es el único punto de contacto con `evaluator.py` en todo este PRD); nuevo bloque `proyecto.planta` en el payload; llamada a `sectorizacion.c01(...)`; `ocupacion_hechos` pasa a construirse con el nuevo parámetro |
| `analyzer/evaluator.py` | **Sin cambios de código.** No se modifica, no se retagea `"CTE-DB-SI-3"`, no se toca `evaluate_fire_compartmentation`, no se consolida con `compute_floor_areas`. `_PLANTA_NAME_PATTERN` se **lee** (import), no se mueve ni se reimplementa. El mecanismo urbanístico existente (`_PLANTA_NAME_PATTERN`/`compute_floor_areas`/`_floor_rooms`/`compute_floor_perimeter_m`) y el modelo DB-SI nuevo (`planta.py`/`sectorizacion.py`) quedan deliberadamente separados: comparten una constante de texto, nada más |
| `tests/test_ocupacion.py` | Se amplía (no se reescribe) con los casos de ámbito planta; el bloque L (compatibilidad con `ejemplo.dxf`) se conserva íntegro como regresión |
| `tests/test_planta.py` | **Nuevo** |
| `tests/test_sectorizacion.py` | **Nuevo** — casos de §4ter y §8 (9-14) |
| B1/B2/B3 (`normativa/`, `extraccion/`, `analyzer/evaluator.py` no relacionado con planta, `experimentos/`) | **Ninguno.** CAP-4 no depende de ellos ni ellos de CAP-4 |

## 11. Plan de implementación dividido en pequeñas tareas

Mismo formato que `REFACTOR_MASTERPLAN.md`, tareas de máximo 2 horas.

1. **`analyzer/hechos.py`**: sin tarea — se reutiliza.
2. **`analyzer/planta.py` — el hecho, fuentes declaración y convención.** Función `planta(ambito, *, numero, sobre_rasante, fuente,
   confianza)` → `Hecho`. Sin parseo de texto dentro: recibe ya normalizado. `NO_APLICABLE` no se usa para este hecho (toda unidad
   ocupable pertenece a alguna planta; no hay categoría análoga a "zona de ocupación nula").
3. **Normalizador de la declaración del formulario.** Función pura texto → `(numero, sobre_rasante)` o `None` si no interpretable
   ("Planta baja"→0, "Planta 3ª"→3, "Sótano 1"→(-1, bajo rasante=True), etc.), con su propio test de casos ambiguos.
4. **`ocupacion()` deja de emitir el parche incondicional.** Nuevo parámetro `planta`; rama condicional; test de equivalencia primero
   (mismo patrón D2 que ya protegió `_superficie_suelo_agregada_m2`), luego el cambio.
5. **`app.py` — flujo `/api/analizar`.** Campo de formulario, llamada al normalizador, construcción del hecho `planta` por unidad
   (mismo valor para todas, v1 es un campo por proyecto), paso a `calcular_ocupacion`.
6. **`app.py` — flujo `/api/generar`.** Import de la constante `_PLANTA_NAME_PATTERN` desde `evaluator` (sin duplicarla, sin tocar
   `evaluator.py`), extracción por unidad, hecho `ESTIMATED`.
7. **Payload `proyecto.planta`.** Serialización en `serialize_analysis`/`app.py`, mismo estilo que `proyecto.usos`.
8. **Test de prohibición `VT<n>`.** Unidad sintética `VT9/9` sin declaración → `planta` debe salir `UNKNOWN`, nunca `9`. Cubre tanto
   `planta.py` como el punto de entrada de `app.py`, para que la prohibición no dependa de un único módulo.
9. **`analyzer/sectorizacion.py` — la regla `C01`.** Agregación de `superficie_util_db_si` por número de planta resuelto; lógica
   `FAIL`/`UNKNOWN` de §4ter (incluida la suma monótona con componentes `UNKNOWN`); código de incidencia propio, verificado distinto
   de `"CTE-DB-SI-3"` (criterio de aceptación 9).
10. **Test que falla si `C01` emite `PASS` en cualquier caso semilla.** Es la comprobación negativa de §4ter/criterio 11 — tan
    importante como los positivos.
11. **Test de regresión `ejemplo.dxf`.** Ampliar el bloque L de `tests/test_ocupacion.py`: mismos 4 `ESTIMATED`/2 `UNKNOWN` de
    `ocupacion`, mismo `ambito_emitido="vivienda"`, `agregado_no_normativo=True` con el nuevo motivo; y `C01 = UNKNOWN` para las 6
    unidades por planta no declarada (criterio de aceptación 14).
12. **Fixture multiplanta sintética.** Para probar CU3, CU5 y CU6 sin depender de `ejemplo.dxf` (que no tiene ninguno de los tres
    casos): al menos una planta que supere 2.500 m² sumando varias unidades, y una que no llegue.

**Ninguna tarea toca `evaluator.py`.** `C01` no es una tarea opcional al final: las tareas 9-11 son tan parte del criterio de cierre
de CAP-4 como las 1-8, por decisión expresa de Pablo (ver nota de modificación en la cabecera de este documento).

## 12. Plan de pruebas

- `tests/test_planta.py` (nuevo): estados KNOWN/ESTIMATED/UNKNOWN, las dos fuentes, el conflicto declaración-vs-convención, la
  prohibición `VT<n>`, sobre/bajo rasante.
- `tests/test_sectorizacion.py` (nuevo): los 6 casos de §4ter (FAIL por suma directa, UNKNOWN por debajo del límite, UNKNOWN por
  planta no declarada, FAIL monótono con componente UNKNOWN, UNKNOWN con componente UNKNOWN sin alcanzar el límite, y el test negativo
  dedicado a que `C01` nunca produzca `PASS`), más la verificación del código de incidencia distinto de `"CTE-DB-SI-3"`.
- `tests/test_ocupacion.py` (ampliado): golden-master de `ejemplo.dxf` sin cambios numéricos; nuevos casos con `planta` KNOWN y
  ESTIMATED verificando el cambio de ámbito y de confianza; `C01 = UNKNOWN` para las 6 unidades de `ejemplo.dxf`.
- Suite completa (`pytest -q --ignore=tests/test_scoring_coherencia.py`) debe seguir en verde, sin tocar B1/B2/B3.

## 13. Métricas para medir el éxito

- **% de análisis con `planta` `KNOWN`/`ESTIMATED`** una vez publicado el campo — métrica de adopción real, se espera baja al
  principio y es la métrica honesta (no una de vanidad): si se queda en 0 %, es la señal de que el campo no está resolviendo nada y
  hay que revisar el flujo del formulario, no la implementación.
- **Nº de proyectos donde `ocupacion.ambito` deja de decir "vivienda (agregado no normativo)"** — el indicador directo de que el
  parche dejó de ser incondicional en la práctica, no sólo en el código.
- **Nº de proyectos donde `C01` emite `FAIL`** — la única señal de que la regla está encontrando algo real, dado que `PASS` no es un
  veredicto alcanzable con los datos de hoy (§4ter). Si este número es 0 durante meses, no es necesariamente un fallo de la regla:
  puede ser que ningún proyecto analizado tenga de verdad una planta de más de 2.500 m² — hay que mirar la distribución de superficie
  antes de concluir nada.

## 14. Posibles motivos para NO implementar la idea

Cuatro argumentos honestos, escritos en el borrador original. Los dos primeros pesan más que los otros dos. **Pablo cerró el motivo 1
explícitamente al aprobar este PRD** (ver nota de modificación en la cabecera); se conservan los cuatro tal cual se plantearon, con la
resolución anotada, porque el registro de la decisión importa tanto como la decisión.

**1. ~~En solitario, el valor visible es casi nulo~~ — CERRADO por decisión de Pablo.** `C09`, `C10`, `C15`, `C16` — los cuatro
consumidores reales de `ocupacion` — siguen bloqueados después de CAP-4 por `CAP-5`/`CAP-6`/`CAP-7` y por el hallazgo `§1.1` de
`DB-SI_IMPLEMENTATION_PLAN.md`. Eso seguía siendo cierto. Lo que cambia es que Pablo decidió no dejarlo así: `C01` parcial deja de ser
opcional y pasa a ser criterio de cierre obligatorio (§4ter, §8, §11). El resultado observable de este PRD ya no es sólo "un parche
mejor explicado": es una regla normativa real, con veredicto `FAIL`/`UNKNOWN` verificable, consumiendo el hecho `planta` desde el
primer commit de CAP-4.

**2. `DB-SI_IMPLEMENTATION_PLAN.md` §12 ya agrupó CAP-4 con CAP-5 en un solo "Bloque C", no como bloques independientes.** Sigue en
pie, sin resolver por esta aprobación. Ver la decisión arquitectónica/de orden/de dependencias al final del documento, que responde a
esto de forma independiente de la discusión de valor del motivo 1.

**3. Compite por el mismo desarrollador con tres iniciativas ya abiertas y sin cerrar** (B1 motor normativa territorial, B2 fix de
scoring/severidad, B3 experimento de grafo — todas en el árbol de trabajo ahora mismo, ninguna commiteada). Sigue en pie. Añadir `C01`
como criterio obligatorio no lo agrava ni lo alivia — es trabajo dentro de CAP-4, no una rama nueva.

**4. La única muestra real (`ejemplo.dxf`) no se beneficia del cambio.** Sigue siendo cierto incluso con `C01` obligatorio:
`ejemplo.dxf` no declara planta, así que también `C01` sale `UNKNOWN` sobre él (criterio de aceptación 14). La diferencia es que ahora
existe una regla real capaz de decir `FAIL` en cuanto exista un proyecto que sí declare planta y la supere — antes no existía ninguna,
declarase lo que declarase el arquitecto.

### Recomendación

**Aprobado por Pablo con la modificación de que `C01` es criterio de cierre obligatorio, no opcional — esta sección documenta que la
recomendación original (motivo 1 abierto) queda superada por esa decisión.** Se mantiene la condición 1 del borrador original:

1. **Diseñar `planta` anticipando lo que CAP-5 necesitará** (número + sobre/bajo rasante, ya incluido en §6 y en la tarea 2 de
   §11), para que CAP-5, cuando se apruebe, sea un PRD que *consume* este hecho y no que lo rediseña.

Lo que **no** se recomienda, y sigue sin recomendarse, es fusionar CAP-4 con CAP-5 en un solo PRD gigante — este PRD, con `C01`
incluido, sigue siendo del tamaño correcto para revisarse y cerrarse en un commit, igual que CAP-3.

---

## Decisión arquitectónica vs. orden de implementación vs. dependencias

Tal como pidió Pablo, separadas explícitamente:

**Decisión arquitectónica — diseñar CAP-4 conociendo a CAP-5.** El hecho `planta` incluye desde v1 el campo `sobre_rasante`, aunque
CAP-4 v1 no tenga ningún consumidor para él. Es la única forma de que CAP-5 (`altura_evacuacion`, que la propia
`DB-SI_IMPLEMENTATION_PLAN.md` describe como *"Fact derivado a partir de CAP-4, o declarado"*) no obligue a rediseñar `planta` cuando
llegue. Coste marginal: un campo. Beneficio: CAP-5 nace como PRD de consumo, no de rediseño.

**Orden de implementación — CAP-4 primero, aislado, con su propio commit — igual que CAP-3.** No se implementa a la vez que CAP-5 ni
se bloquea a esperarlo. Se implementa, se prueba contra `ejemplo.dxf` (regresión), se cierra. CAP-5 es el siguiente PRD, posterior,
que parte de `planta` ya publicado — no simultáneo.

**Dependencias — asimétricas, y hay que decirlo así de claro:**

- **CAP-5 depende de CAP-4** (dependencia dura, documentada en `DB-SI_IMPLEMENTATION_PLAN.md`: la altura de evacuación se deriva de
  la planta, o se declara directamente si CAP-4 no basta). CAP-5 no se puede empezar con sensatez antes de que este PRD se cierre.
- **CAP-6 NO depende de CAP-4.** Su bloqueo es otro, independiente y más grave: el hallazgo `§1.1` — los bloques de núcleo de
  comunicación y carpintería existen en `ejemplo.dxf` y no están insertados en modelspace. Es un problema de convención de entrega del
  DXF (`DB-SI_IMPLEMENTATION_PLAN.md` "Bloque D — decisión de producto, no de ingeniería"), no de modelo de datos. **Aprobar o
  posponer CAP-4 no adelanta ni retrasa CAP-6 en absoluto.**
- **CAP-4 no depende de CAP-5 ni de CAP-6.** Es autocontenido sobre lo que ya existe (CAP-1/2/3, commiteados).

---

## Deuda conocida, encontrada durante la implementación (tarea 6, sin resolver a propósito)

**Dos convenciones de numeración de planta distintas conviven en `/api/generar`, y CAP-4 no las armoniza.**

- El hecho `planta` de CAP-4 usa `sobre_rasante = numero > 0` (coherente con `analyzer/planta.py` y con el normalizador de
  `/api/analizar`: planta 0/negativa no está sobre rasante).
- El urbanismo ya existente en esa misma ruta (`evaluator.compute_floor_areas`, `compute_floor_perimeter_m`, invocados en
  `app.py` con `floor=1`) trata la planta **"1" como planta baja** — `floor_areas.get(1, 0.0)` se usa literalmente como
  `superficie_planta_baja`.

Para un edificio generado con planta "1", el hecho `planta` de CAP-4 diría `sobre_rasante=True` mientras que el cálculo
urbanístico de la misma ruta la trata como la planta a nivel de rasante. Dos lecturas del mismo número, en dos sistemas
distintos, en el mismo endpoint.

**No se resuelve en CAP-4**: arreglarlo exige tocar `evaluator.py` (`compute_floor_areas`) o renegociar la convención de
`ai_generator._unit_from_dict`, y ambas cosas son ajenas al alcance de este PRD (`evaluator.py` explícitamente fuera de
alcance, por instrucción directa). Queda registrado aquí, en `app.py` (comentario junto al cableado de `/api/generar`) y
en el resumen de la tarea 6, como **deuda separada para una futura decisión arquitectónica** — candidata natural para
`CAP-5` (altura de evacuación), que es quien primero necesitará que "sobre rasante" signifique lo mismo en todo el sistema.

---

**Decisión:** **Aprobado por Pablo (2026-08-09)**, con la modificación de que `C01` parcial (§4ter) es criterio de cierre obligatorio
de CAP-4, no una tarea opcional. El resto del PRD queda tal como se redactó originalmente. Pendiente de implementación (§11).
