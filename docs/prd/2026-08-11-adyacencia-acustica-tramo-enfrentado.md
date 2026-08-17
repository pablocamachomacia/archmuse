# PRD — `evaluate_acoustic_adjacency()` pasa a usar `tramo_enfrentado_m`

**Estado:** Borrador · **Fecha:** 2026-08-11 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

Origen: análisis E3.5 (sin fichero propio — informe de conversación), decisión de Pablo: **A, adoptar el
criterio del modelo**.
Precedente técnico: [`docs/prd/2026-08-11-e3-clasificacion-circulation.md`](2026-08-11-e3-clasificacion-circulation.md) (E3.3/E3.4)

> **Por qué este PRD es un documento aparte, y no "E3.5 del otro PRD".** E3.3 y E3.4 fueron migraciones
> **neutras**: mismo resultado, medido antes y después, sustrato distinto. Esto **no lo es**. Adoptar
> `tramo_enfrentado_m` cambia lo que `evaluate_acoustic_adjacency()` decide sobre datos reales — 9 de 11 pares de
> `ejemplo.dxf` pasan de "sin incidencia" a "incidencia IMPORTANTE". Mezclarlo con E3.3/E3.4 habría enterrado un
> cambio de comportamiento normativo dentro de un commit que se vende como "sin cambios", que es exactamente lo
> que la disciplina de esta iniciativa existe para impedir.

---

## 1. Problema actual, con la evidencia medida en E3.5

`evaluate_acoustic_adjacency()` (CTE DB-HR: un dormitorio no debería compartir tabique con un baño/aseo sin
aislamiento verificado) usa `_is_adjacent()`, que exige que los polígonos **se toquen** (`shared_edge_length =
a.boundary.intersection(b.boundary).length > 0.3m`). En un DXF real cada recinto se dibuja en la cara interior de
su propio muro, así que dos habitaciones que comparten tabique casi nunca tienen polígonos que se tocan — hay un
hueco del espesor del muro entre ambos.

**Medido sobre `ejemplo.dxf`, no supuesto:**

| | |
|---|---|
| Pares Dormitorio × Baño/Aseo evaluados | 11 |
| Disparan HOY (`_is_adjacent`) | **0** |
| Dispararían con `tramo_enfrentado_m > 0,3m` | **9** |

Una regla normativa que nunca dispara sobre datos reales no protege nada. Es un defecto funcional, no una
curiosidad arquitectónica — y estaba ya diagnosticado por su nombre, dos veces, antes de este PRD: en el docstring
de `modelo/geometria.tramo_enfrentado_m` desde E1, y en el propio `analyzer/adyacencia.py`, que dice literalmente
*"`evaluator._is_adjacent` (Bloque 16, adyacencia acústica) exige contacto literal de contornos y por eso no
dispara nunca sobre datos reales... migrarlo cambia qué avisos acústicos aparecen, así que es una decisión
aparte."* Ese comentario ya predecía, antes de medir nada, exactamente la naturaleza de este PRD. E3.5 es la
primera vez que se mide contra el plano real en vez de citarlo.

## 2. Comportamiento actual

```python
_ADJACENCY_MIN_LENGTH_M = 0.3
_NOISY_ROOM_PATTERN = re.compile(r"BANO|ASEO")

def _shared_edge_length(a, b):
    return a.boundary.intersection(b.boundary).length

def _is_adjacent(a, b):
    return _shared_edge_length(a, b) > _ADJACENCY_MIN_LENGTH_M

def evaluate_acoustic_adjacency(unit):
    # para cada (dormitorio, baño/aseo): passed = not _is_adjacent(dorm.polygon, ruidosa.polygon)
```

`passed=False` produce un issue `IMPORTANTE`, código `CTE-DB-HR`, título *"Dormitorio adyacente a zona húmeda sin
aislamiento verificado"*. **No entra en `checks`/`score_pct`**: es informativo, no puntúa. Hoy, sobre
`ejemplo.dxf`, nunca se genera.

## 3. Comportamiento propuesto

`evaluate_acoustic_adjacency()` calcula el tramo enfrentado con `modelo.geometria.tramo_enfrentado_m`, sobre un
`AlmacenGeometria()` de usar y tirar — mismo patrón exacto que E3.4 en `evaluate_proportions`/
`evaluate_corridor_width`, sin construir el grafo ni tocar identidad:

```python
from modelo import AlmacenGeometria, HUELLA_2D
from modelo.geometria import tramo_enfrentado_m
from . import adyacencia as ady  # ya es una dependencia de evaluator.py

def evaluate_acoustic_adjacency(unit):
    almacen = AlmacenGeometria()
    for dorm in dormitorios:
        for ruidosa in ruidosas:
            ga = almacen.insertar(dorm.polygon, HUELLA_2D, unidad="m")
            gb = almacen.insertar(ruidosa.polygon, HUELLA_2D, unidad="m")
            tramo = tramo_enfrentado_m(almacen, ga, gb, ady.WALL_GAP_TOLERANCE_M)
            passed = tramo <= _ADJACENCY_MIN_LENGTH_M
            ...
```

`_shared_edge_length`/`_is_adjacent` **no se eliminan** en este PRD si algún otro sitio los usa (comprobar antes
de implementar; hoy, medido, sólo los usa esta regla — ver §13). El resto de la función (patrones de
clasificación, estructura de `AcousticAdjacencyResult`, dónde se engancha en `classify_problems`) no cambia.

## 4. Por qué `tramo_enfrentado_m` es el criterio correcto

No es sólo "el que da el modelo": es el que **mide lo que la norma le importa**. CTE DB-HR exige aislamiento entre
un dormitorio y un baño/aseo cuando **comparten un elemento constructivo** — un tabique o muro — no cuando sus
polígonos de recinto casualmente se tocan en el dibujo. `tramo_enfrentado_m` mide exactamente eso: cuánto del
contorno de cada recinto cae dentro del espesor de muro plausible del otro (`WALL_GAP_TOLERANCE_M`). `_is_adjacent`
mide una propiedad del dibujo (¿tocan los polígonos?), no una propiedad del edificio (¿comparten tabique?) — y por
eso falla sistemáticamente en datos reales.

## 5. El umbral de 0,3 m y su relación con `WALL_GAP_TOLERANCE_M = 0,5 m`

Son dos números con trabajos distintos, y la propuesta no inventa uno nuevo — recompone los dos que ya existen:

- **`WALL_GAP_TOLERANCE_M = 0,5 m`** (única definición, en `adyacencia.py`, leída y no copiada): la **distancia**
  máxima entre dos contornos para que tenga sentido preguntarse si comparten muro. Gobierna el `tolerancia` que
  recibe `tramo_enfrentado_m`.
- **`_ADJACENCY_MIN_LENGTH_M = 0,3 m`**: la **longitud** mínima de tramo enfrentado para que cuente como
  contacto real y no como un roce de esquina. Se conserva sin cambiar su valor ni su papel — sólo cambia la
  función que produce el número que compara.

**Riesgo que este PRD deja escrito, no resuelto:** en los 9 pares medidos, el tramo enfrentado va de 0,567 m a
5,246 m — ninguno cerca de 0,3 m. El umbral de 0,3 m no se ha probado nunca cerca de su margen con
`tramo_enfrentado_m`; se hereda porque ya existía, no porque se haya validado contra esta función. Si algún
proyecto real produce un tramo cercano a 0,3 m, ese es el caso que decidiría si el número sigue siendo el
correcto — no lo decide este PRD.

## 6. Casos reales afectados — los 9 pares, con sus números

```
VT1/3  Dormitorio 1 – Aseo   gap 0,035 m   tramo 5,246 m
VT1/3  Dormitorio 1 – Baño   gap 0,262 m   tramo 0,567 m
VT1/3  Dormitorio 2 – Aseo   gap 0,137 m   tramo 0,820 m
VT1/3  Dormitorio 2 – Baño   gap 0,135 m   tramo 2,106 m
VT2/2  Dormitorio 1 – Baño   gap 0,134 m   tramo 2,906 m
VT2/2  Dormitorio 2 – Baño   gap 0,136 m   tramo 2,205 m
VT3/3  Dormitorio 1 – Baño   gap 0,261 m   tramo 0,570 m
VT3/3  Dormitorio 2 – Baño   gap 0,133 m   tramo 2,294 m
VT6/2  Dormitorio 1 – Baño   gap 0,135 m   tramo 2,442 m
```

Los 2 pares que no disparan en ningún criterio (VT1/3 Dormitorio 3 – Aseo/Baño, gap 3,84 m y 2,33 m) siguen sin
disparar: están genuinamente lejos, y es la prueba de que el criterio nuevo no dispara porque sí.

## 7. Impacto de producto / API

- **9 incidencias `IMPORTANTE`, código `CTE-DB-HR`**, nuevas en `issues` y en `problemas_vivienda` de VT1/3,
  VT2/2, VT3/3 y VT6/2 (título: *"Dormitorio adyacente a zona húmeda sin aislamiento verificado"*).
- **`puntuacion_global` y `puntuacion` por vivienda NO cambian**: la regla sigue sin entrar en `checks`/
  `score_pct` — este PRD no toca eso, y no debería, sin un PRD propio para esa decisión.
- Un arquitecto que reanalice un proyecto ya guardado verá incidencias nuevas que antes no existían. Es una
  mejora de la herramienta, pero es visible, y hay que poder explicarla si alguien pregunta por qué "cambió" un
  informe: la respuesta es que antes la regla no funcionaba, no que el proyecto empeoró.

## 8. Impacto en goldens G6/G8

- **G6 (`test_golden_api_analizar.py`)**: cambia `issues.n`, `issues.por_severidad["IMPORTANTE"]` (+9),
  `issues.titulos` (9 líneas nuevas), `problemas_vivienda` de las 4 viviendas afectadas. Se recaptura, y el diff
  se revisa a mano — mismo procedimiento que fija el PRD de E0 (§6, "el golden se vuelve obsoleto por un cambio
  aprobado").
- **G8 (`test_golden_determinismo.py`)**: sella el manifiesto de los demás fixtures; se re-ejecuta/recaptura
  después de G6, mismo orden que cuando entró G9 en E1.
- **G1–G5, G7, G9**: sin impacto — ninguno consume `evaluate_acoustic_adjacency`. Se ejecutan igualmente como
  parte de la verificación, para confirmarlo, no por sospecha.

## 9. Nueva cobertura específica para `evaluate_acoustic_adjacency`

Hoy no existe ningún test dedicado a esta regla (comprobado por búsqueda en `tests/`, E3.5). Antes de esta
migración se crea `tests/test_acoustic_adjacency.py` (o el nombre que decida la implementación), con dos bloques,
mismo criterio que ya usó E3.4:

1. **Sobre `ejemplo.dxf` real**: los 9 pares que disparan y los 2 que no, con sus valores de `tramo_m` — capturado
   como el golden de esta regla, no como una comprobación de propiedad genérica.
2. **Casos sintéticos del espesor de muro** (ya escritos y medidos en el exploratorio de E3.5, se trasladan aquí
   como test permanente): gap 0,000 m (dispara en ambos criterios), gap 0,10 m y 0,20 m (sólo dispara con el
   criterio nuevo — es la prueba directa del defecto corregido), gap 0,60 m (no dispara en ninguno).

## 10. Riesgos y posibles falsos positivos

1. **El umbral de 0,3 m no se ha validado cerca de su margen** (§5) — riesgo aceptado y escrito, no resuelto.
2. **Recintos con geometría irregular** (no rectangular) podrían producir un `tramo_enfrentado_m` mayor de lo que
   la intuición esperaría, si el contorno serpentea dentro del buffer más de una vez. `ejemplo.dxf` no tiene
   ningún recinto así entre los 9 pares medidos — no hay evidencia de que ocurra, pero tampoco de que no pueda.
3. **Salón/cocina queda fuera a propósito** (decisión ya tomada, sin cambios en este PRD): sigue sin evaluarse,
   porque en España suele ser un espacio abierto — este PRD no reabre esa decisión.
4. **`WALL_GAP_TOLERANCE_M` es compartido con la adyacencia de circulación.** Si algún día cambia (sigue siendo
   la decisión abierta 3 de E1), esta regla cambia con él automáticamente — es la ventaja de leerlo, no copiarlo,
   pero significa que un cambio de umbral pensado para circulación también movería el criterio acústico. No es un
   riesgo nuevo: ya es así para toda pieza que lea el mismo número.
5. **Falsos positivos por proximidad sin muro real** (dos recintos separados por un patio o un hueco de
   instalación, no por un tabique): el gap-buffer de 0,5 m no distingue "hay un muro" de "hay 0,5 m de distancia
   por lo que sea". Es el mismo límite que ya acepta el criterio de contigüidad del modelo en general (decisión 3
   de E1, no resuelta aquí).

## 11. Criterios de aceptación

- **B1.** `evaluate_acoustic_adjacency` usa `tramo_enfrentado_m` sobre un `AlmacenGeometria` de usar y tirar,
  mismo patrón que E3.4.
- **B2.** `_ADJACENCY_MIN_LENGTH_M` conserva su valor (0,3); `tolerancia` lee `adyacencia.WALL_GAP_TOLERANCE_M`,
  no lo copia.
- **B3.** Sobre `ejemplo.dxf`, disparan exactamente los 9 pares de §6 — verificado, no asumido, antes de mover el
  golden.
- **B4.** G6 y G8 recapturados; el diff de G6 se revisa a mano y coincide exactamente con §6/§7.
- **B5.** `tests/test_acoustic_adjacency.py` nuevo, en verde, cubriendo ejemplo.dxf real y los 4 casos sintéticos
  de §9.
- **B6.** `puntuacion_global` y `puntuacion` por vivienda idénticos antes/después — comprobado, no asumido.
- **B7.** `git diff` limitado a: `analyzer/evaluator.py`, el test nuevo de §9, `tests/fixtures/golden/G6_*.json` y
  `G8_*.json`, y este PRD (sección Decisión). Ningún otro fichero.
- **B8.** Suite completa: mismo baseline que E3.4 salvo el test nuevo — 1 fallo conocido
  (`test_scoring_coherencia.py`), ninguno más.

## 12. Rollback

Mismo criterio que E1/E3.3/E3.4: sin interruptor, sin variable de entorno. Si tras implementar aparece un falso
positivo real no previsto en §10, la vuelta atrás es un `git revert` del commit de esta migración — no una rama
condicional que mantenga vivo el criterio roto "por si acaso".

## 13. Dependencias y orden de ejecución

1. **Depende de la decisión A ya tomada** (este documento). No depende de E3.3/E3.4 técnicamente —
   `evaluate_acoustic_adjacency` es independiente de `circulation.py` y de `evaluate_proportions`— pero **sí
   depende de que E3.4 haya demostrado el patrón** (`AlmacenGeometria` de usar y tirar dentro de una regla de
   `evaluator.py`, sin construir el grafo): esta migración lo repite, no lo inventa.
2. **No depende de ni bloquea** ninguna otra regla de `evaluator.py`, `spatial_quality.py`, `plan_svg.py` ni
   `ai_generator.py`.
3. **Ya verificado por búsqueda (E3.5, no queda para la implementación):** `_shared_edge_length`/`_is_adjacent`
   de `evaluator.py` los usa **únicamente** `evaluate_acoustic_adjacency`. `ai_generator.py` tiene su **propia
   copia independiente** de las dos funciones (líneas 386-393, no importada de `evaluator.py`), usada para validar
   adyacencias de layouts generados por IA — es la cuarta copia de este patrón en el repositorio, y queda
   **fuera de alcance** de este PRD (otra iniciativa, decisión ya tomada en E2/E3: no mezclar). No se toca.
4. **Commit separado** del de E3.3/E3.4, con mensaje que dijera explícitamente que es un cambio de comportamiento
   aprobado, no una migración neutra — mismo criterio que pidió Pablo para no mezclar las dos naturalezas de
   cambio en la misma unidad de git.
5. **No se implementa en esta tarea.** Este documento es el PRD; la implementación es la siguiente tarea,
   pendiente de aprobación.

---

**Decisión:** Pablo aprobó adoptar el criterio del modelo (Opción A, E3.5). Este PRD queda **pendiente de
aprobación de su contenido concreto** antes de implementar.
