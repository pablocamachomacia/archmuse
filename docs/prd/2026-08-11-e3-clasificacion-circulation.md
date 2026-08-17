# PRD — E3: `circulation.py` deja de clasificar por su cuenta

**Estado:** Aprobado · **Fecha:** 2026-08-11 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (auditoría final E3, 2026-08-11)

Diseño de referencia: [`docs/design/2026-08-11-modelo-arquitectonico-comun.md`](../design/2026-08-11-modelo-arquitectonico-comun.md) §15.3
Contrato heredado: [`docs/prd/2026-08-11-e0-modelo-arquitectonico.md`](2026-08-11-e0-modelo-arquitectonico.md) (C2, C5)
Precedente directo: [`docs/prd/2026-08-11-e2-persistencia-modelo.md`](2026-08-11-e2-persistencia-modelo.md)
Medición previa: [`tests/test_e3_paridad_clasificacion.py`](../../tests/test_e3_paridad_clasificacion.py) (E3.1)

> **Alcance de este PRD, en una frase:** que `analyzer/circulation.py` pregunte al modelo qué tipo es cada
> habitación en vez de averiguarlo con sus propios cinco patrones regex sobre `room.label`. Nada más se mueve.

---

## 0. Nomenclatura — para no confundir con el "E3" de la hoja de ruta

`docs/design/2026-08-11-modelo-arquitectonico-comun.md` §18 llama "E3" a *ensamblaje y multiplanta* (depende de
proyectos reales, mata `UNIT_OFFSET_M`). Este documento usa "E3" en el sentido en que se ha usado en esta
conversación desde la auditoría de consumidores: la siguiente ola de migración a `modelo/`, continuación directa
de lo que E1 hizo con la adyacencia de `circulation.py`. Son dos iniciativas distintas con el mismo número; este
PRD no toca la de ensamblaje.

## 1. Estado actual

`circulation.py` migró su **adyacencia** al modelo en E1 (`_build_adjacency_graph` llama a
`modelo_compat.grafo_de_adyacencia`). Su **clasificación semántica** no se tocó: cinco comprobaciones booleanas
sobre `room.label`, evaluadas con regex, deciden qué habitación es dormitorio, cuál es baño, cuál es zona social y
cuál es circulación:

| Patrón | Definición | De dónde viene |
|---|---|---|
| `_DORMITORIO_ANY_PATTERN` | `r"DORMITORIO"` | importado de `evaluator.py` |
| `_SALON_PATTERN` | `r"SALON\|COCINA"` | importado de `evaluator.py` |
| `_CIRCULATION_ROOM_PATTERN` | `r"PASILLO\|VESTIBULO\|DISTRIBUIDOR\|RECIBIDOR\|ANTESALA"` | propio de `circulation.py` |
| `_BANO_OR_ASEO_PATTERN` | `r"BANO\|ASEO"` | propio de `circulation.py` |
| `_DESTINATION_PATTERN` | `r"SALON\|COCINA\|DORMITORIO\|BANO\|ASEO"` | propio de `circulation.py` |

Usos exactos, con línea:

```
169  dormitorios  = [r for r in unit.rooms if ... _DORMITORIO_ANY_PATTERN...]      _check_absurd_routes
170  banos        = [r for r in unit.rooms if ... _BANO_OR_ASEO_PATTERN...]        _check_absurd_routes
180  crossed_social = [r for r in path[1:-1] if ... _SALON_PATTERN...]             _check_absurd_routes
232  destinations = [r for r in unit.rooms if ... _DESTINATION_PATTERN...]         _check_pass_through_rooms
241  if room.label and _CIRCULATION_ROOM_PATTERN...: continue                      _check_pass_through_rooms
265  banos        = [r for r in unit.rooms if ... _BANO_OR_ASEO_PATTERN...]        _check_bathroom_access
270  direct_social = [n for n,_ in neighbors if ... _SALON_PATTERN...]             _check_bathroom_access
296  destinations = [r for r in unit.rooms if any(p... _EVACUATION_DESTINATION_PATTERNS)]  _check_evacuation_route
```

**Fuera de los 5, y hay que decirlo para no confundirlo con ellos:** la línea 290 busca el Pasillo de la vivienda
con una comprobación literal aparte, `"PASILLO" in _normalize(r.label)`, no con `_CIRCULATION_ROOM_PATTERN`. Este
PRD no la incluye en el alcance (ver §4); se menciona para que nadie dé por cubierta una sexta comprobación que
no lo está.

**Lo que E3.1 midió** (`tests/test_e3_paridad_clasificacion.py`, ejecutado sobre `ejemplo.dxf`):

1. **Paridad demostrada, 34/34.** Sobre los 34 recintos de `ejemplo.dxf`, los 5 patrones coinciden exactamente
   con `modelo.constructor.clasificar()`, comparando por el conjunto de tipos del modelo que cada patrón
   representa (ver §5).
2. **Cero divergencias observadas.** No hay ni una fila donde el patrón diga una cosa y el modelo otra.
3. **La equivalencia de Baño/Aseo y Salón/Cocina es semántica, no léxica.** El modelo distingue `"bano"` de
   `"aseo"` y `"salon"` de `"cocina"` como tipos separados; `circulation.py` sólo pregunta una cosa más gruesa
   ("¿es del tipo húmedo?", "¿es del tipo social?"). Coinciden porque la pregunta correcta es "¿el tipo del modelo
   cae dentro del conjunto que representa el patrón?", no "¿son la misma palabra?".
4. **`ANTESALA`/`PASILLO`/`VESTIBULO`/`DISTRIBUIDOR`/`RECIBIDOR` NO están demostrados.** Ninguno de los 34
   rótulos de `ejemplo.dxf` es de esta familia (el censo es Terraza, Dormitorio 1/2/3, Salón/cocina, Tendedero,
   Baño, Aseo). `_CIRCULATION_ROOM_PATTERN` nunca se activó durante la medición, así que su paridad con el modelo
   es una hipótesis sin comprobar, no un hecho medido. Y hay una asimetría conocida y sin medir: `ANTESALA`
   aparece en el patrón de `circulation.py` pero **no existe como entrada en absoluto** en
   `modelo.constructor.CLASIFICACION` — un recinto así etiquetado clasificaría como `UNKNOWN` en el modelo
   (`TIPO_NO_RECONOCIDO`) y como circulación en `circulation.py` hoy. No se afirma que esto rompa nada: se afirma
   que no se sabe, porque no hay datos que lo digan.
5. **`tests/test_e3_paridad_clasificacion.py` es la red de seguridad y la evidencia de este PRD**, no un test
   desechable de la auditoría: se conserva y se ejecuta como parte de la verificación de cualquier paso de
   migración.

## 2. Objetivo

Que `circulation.py` deje de tener su propia definición de "qué es un dormitorio", y pase a leer `Espacio.tipo`
del modelo — la misma fuente de la que ya lee la adyacencia desde E1. Cierra la última pieza no migrada de este
consumidor: después de este PRD, `circulation.py` no vuelve a mirar `room.label` para nada semántico.

## 3. Usuario afectado

Ninguno directamente — mismo criterio que E0/E1/E2: infraestructura interna. El beneficiario indirecto es
`evaluator.py`, que hoy repite esta misma clasificación veinte veces con patrones ligeramente distintos
(`docs/design/2026-08-11-modelo-arquitectonico-comun.md` §15.3): que `circulation.py` sea el segundo consumidor
en depender de una única definición hace la tercera migración (la de `evaluator.py`, regla a regla) más barata.

## 4. Alcance y fuera de alcance

**Dentro de alcance, exclusivamente:**

- `analyzer/circulation.py`: las 8 llamadas listadas en §1 a los 5 patrones, y sólo ellas.
- El mapeo de cada patrón al conjunto de tipos del modelo que debe sustituirlo (§6).

**Fuera de alcance, explícito:**

- La comprobación literal de "PASILLO" en la línea 290 (`_check_evacuation_route`) — no es uno de los 5 patrones
  y no se toca en este PRD.
- Cualquier regla de `evaluator.py`. Su clasificación es un frente propio, de veinte reglas, y migrarlo de golpe
  es exactamente la "refactorización general" que las reglas de esta iniciativa prohíben.
- `spatial_quality.py`, `plan_svg.py`, `api_serializer.py`, `ai_generator.py` — ninguno se toca.
- El umbral de contigüidad (sigue abierto, decisión 3 de E1).
- `Muro`/`Hueco` (siguen fuera del modelo, decisión 2 de E1).
- CAP-1…CAP-5, `hechos.py` — no se tocan ni se leen desde este cambio.
- `scoring.py` — sin cambios; los impactos de puntuación (`_SCORE_IMPACT_BY_TIPO`) no se tocan, sólo la entrada
  que decide qué `CirculationRoute` se genera.
- Materializar `PASILLO`/`VESTIBULO`/`DISTRIBUIDOR`/`RECIBIDOR`/`ANTESALA` en `modelo.constructor.CLASIFICACION`
  con datos nuevos: si se decide cerrar la brecha de §1.4, es una decisión de vocabulario del modelo, independiente
  de si `circulation.py` lo consume o no, y no la resuelve implícitamente este PRD.

## 5. Mapeo explícito: los 5 patrones → tipos del modelo

Este mapeo es el contrato central de la migración. Cada patrón es hoy una pregunta booleana ("¿esta habitación es
de esta familia?"); tras migrar, la misma pregunta se contesta mirando si `Espacio.tipo.valor` (o alguno de sus
`tipos_ambiguos`) cae dentro del conjunto de la derecha.

| Patrón (hoy, en `circulation.py`) | Regex | Conjunto de tipos del modelo | Estado de la paridad |
|---|---|---|---|
| `_DORMITORIO_ANY_PATTERN` | `DORMITORIO` | `{"dormitorio"}` | **Demostrada** (34/34, sin divergencias) |
| `_SALON_PATTERN` | `SALON\|COCINA` | `{"salon", "cocina"}` | **Demostrada** (34/34, sin divergencias) |
| `_BANO_OR_ASEO_PATTERN` | `BANO\|ASEO` | `{"bano", "aseo"}` | **Demostrada** (34/34, sin divergencias) |
| `_DESTINATION_PATTERN` | `SALON\|COCINA\|DORMITORIO\|BANO\|ASEO` | `{"salon","cocina","dormitorio","bano","aseo"}` | **Demostrada** (34/34, sin divergencias) |
| `_CIRCULATION_ROOM_PATTERN` | `PASILLO\|VESTIBULO\|DISTRIBUIDOR\|RECIBIDOR\|ANTESALA` | `{"circulacion"}` | **NO demostrada.** Cero ocurrencias en `ejemplo.dxf`. Asimetría conocida: `ANTESALA` no tiene entrada en `modelo.constructor.CLASIFICACION` — clasificaría `UNKNOWN` en el modelo |

**Consecuencia directa para la estrategia (§8):** los cuatro primeros patrones tienen paridad medida y son
candidatos a migrar tal cual. El quinto (`_CIRCULATION_ROOM_PATTERN`) no puede migrarse con la misma confianza
hasta que exista, o bien un dato real con una de esas etiquetas, o bien una decisión explícita sobre qué hacer
con `ANTESALA` en el modelo. Tratarlos igual sería la parte de este PRD donde "no inventar éxito" importa más.

## 6. Comportamiento esperado

Tras la migración (E3.3, no en este documento):

- `circulation.py` sigue devolviendo exactamente las mismas `CirculationRoute` que hoy sobre `ejemplo.dxf` —
  neutralidad medida, mismo criterio que E1/E2, comprobada por goldens, no supuesta.
- `circulation.py` deja de importar `_DORMITORIO_ANY_PATTERN`/`_SALON_PATTERN` de `evaluator.py` para este fin
  (puede seguir importándolos si otro uso lo exige; no es el caso hoy) y deja de definir
  `_CIRCULATION_ROOM_PATTERN`/`_BANO_OR_ASEO_PATTERN`/`_DESTINATION_PATTERN` como regex propios.
- La fuente de verdad de "qué tipo es esta habitación" para `circulation.py` pasa a ser el mismo objeto
  (`Espacio.tipo`, vía el modelo ya construido una vez por análisis desde E2) que ya gobierna su topología.
- Sobre un plano futuro con recintos de tipo `circulacion` distintos de "Pasillo", el comportamiento podría
  cambiar respecto al de hoy — y **eso no es una regresión de este PRD**, es la consecuencia declarada de la
  brecha de §1.4, que se resuelve por decisión explícita, no por accidente (ver §8, paso 3).

## 7. Riesgos

1. **Migrar el patrón sin paridad demostrada (`_CIRCULATION_ROOM_PATTERN`) como si lo estuviera.** Es el riesgo
   más concreto de este PRD, y por eso el mapeo de §5 lo marca aparte y la estrategia de §8 lo trata en un paso
   separado, no junto a los otros cuatro.
2. **La brecha de `ANTESALA` se vuelve invisible tras la migración.** Si un futuro DXF trae un recinto
   "Antesala", hoy `circulation.py` lo trataría como circulación (patrón); tras migrar sin resolver la brecha,
   el modelo lo marcaría `UNKNOWN` y `circulation.py` dejaría de reconocerlo como tal — un cambio de
   comportamiento real, no cosmético. Mitigación: el paso 3 de §8 exige decidir esto explícitamente antes de
   tocar el quinto patrón, no dentro del mismo commit que los otros cuatro.
3. **`ejemplo.dxf` es el único plano real disponible.** La paridad 34/34 prueba ausencia de regresión sobre esa
   muestra, no generalidad — mismo límite ya reconocido en el PRD de E0 (§9.5) para los goldens.
4. **Confundir "coincide hoy" con "es la misma pregunta".** El modelo pregunta *qué es* un recinto (una función
   de su rótulo, resuelta una vez, con motivo si no se sabe). `circulation.py` pregunta *si pertenece a un grupo*,
   cinco veces, con cinco agrupaciones ligeramente distintas de los mismos tipos. Migrar bien exige mantener esa
   distinción explícita en el código (leer `tipo` y comparar contra un conjunto), no aplanarla a un único campo
   nuevo que reinvente las cinco preguntas.
5. **Segundo sistema de incertidumbre.** `Espacio.tipo` es un `Atributo` (estado × origen × confianza), no un
   string desnudo. La migración debe leer `.valor` (y tratar `UNKNOWN` explícitamente, no como cadena vacía) —
   igual que ya hace `constructor.clasificar()` — para no reintroducir el problema que `hechos.py` existe para
   resolver.
6. **Orden de fallback.** `_check_absurd_routes`/`_check_bathroom_access` etc. asumen que un recinto sin tipo
   reconocido simplemente no entra en ninguna lista (hoy: el regex no casa). Con `Atributo`, un tipo `UNKNOWN`
   debe seguir produciendo el mismo "no entra en ninguna lista" — comportamiento por defecto correcto, pero que
   hay que verificar explícitamente, no asumir.

## 8. Estrategia de migración

**Dos pasos, no uno**, precisamente por la asimetría de §5:

1. **Migrar los 4 patrones con paridad demostrada** (`_DORMITORIO_ANY_PATTERN`, `_SALON_PATTERN`,
   `_BANO_OR_ASEO_PATTERN`, `_DESTINATION_PATTERN`) a comparar `Espacio.tipo.valor` (y `tipos_ambiguos`) contra
   el conjunto correspondiente de §5. `_CIRCULATION_ROOM_PATTERN` se queda como está, sin tocar, en este paso.
2. **Verificar neutralidad** con la misma disciplina de E1: goldens antes/después, canario, y
   `test_e3_paridad_clasificacion.py` ampliado para comparar también contra el comportamiento *migrado* de
   `circulation.py`, no sólo contra los patrones originales.
3. **Decisión explícita sobre `_CIRCULATION_ROOM_PATTERN`**, sólo después de 1–2, y sólo si Pablo la pide: o se
   consigue/produce un dato real con alguna de esas etiquetas para medir paridad de verdad, o se decide
   explícitamente añadir `ANTESALA` a `modelo.constructor.CLASIFICACION` (decisión de vocabulario del modelo, no
   de `circulation.py`) antes de migrar el quinto patrón, o se deja el quinto patrón sin migrar indefinidamente,
   documentado como deuda. Las tres son válidas; ninguna se decide en este documento.

Nada de esto se ejecuta en este PRD (E3.2). Es la propuesta para E3.3, pendiente de tu aprobación.

## 9. Tests de regresión

- **`tests/test_e3_paridad_clasificacion.py`** (ya existe, E3.1): se ejecuta antes y después del paso 1 de §8.
  Se amplía en E3.3 para comparar también la salida real de `circulation.py` migrado contra la de hoy, no sólo
  los patrones contra el modelo.
- **G4 (`tests/test_golden_circulacion.py`)**: el golden directo de `evaluate_circulation()`. Cualquier
  diferencia en las 5 comprobaciones por vivienda debe ser cero tras el paso 1.
- **`tests/test_modelo_compat.py`**: ya cubre la equivalencia de adyacencia; no necesita cambios para este PRD,
  pero debe seguir en verde (confirma que el resto del puente no se ha tocado).
- **`tests/canario.py`**: K1–K4 deben seguir rompiendo exactamente el mismo patrón de goldens. Si la migración
  introduce sensibilidad nueva a K4 (reclasificación de "Terraza"), sería una señal de que el cambio se ha salido
  de alcance — K4 muta `superficie_util`, no clasificación de `circulation.py`, y no debería tocar esta zona.
- **Suite completa**: 58 ficheros, 57 OK, 1 fallo conocido (`test_scoring_coherencia.py`) — mismo baseline que
  cerró E2, sin cambios.

## 10. Criterios de aceptación

- **B1.** Los 4 patrones con paridad demostrada leen `Espacio.tipo` en vez de su regex propio; el quinto no se
  toca en E3.3.
- **B2.** G4 idéntico antes/después, byte a byte.
- **B3.** `test_e3_paridad_clasificacion.py` ampliado pasa, incluyendo la comparación contra el comportamiento
  real migrado.
- **B4.** Canario (K1–K4) sin cambios de patrón.
- **B5.** Suite completa: 58 ficheros, 57 OK, 1 fallo conocido — sin variación.
- **B6.** `git diff` fuera de `analyzer/circulation.py` y los tests listados en §9 está vacío.
- **B7.** `_CIRCULATION_ROOM_PATTERN` sigue exactamente como está hasta que se tome la decisión explícita de §8.3.

## 11. Rollback

Mismo criterio que E1 (`docs/design/2026-08-11-e1-implementacion.md` §1, "Sin interruptor"): no se introduce una
variable de entorno ni una rama condicional para volver atrás. Si la migración del paso 1 muestra una diferencia
no prevista, la vuelta atrás es un `git revert` del commit de E3.3 — mantener dos implementaciones de la misma
clasificación "por si acaso" es exactamente la duplicación que este PRD existe para eliminar, y es la que se
pudre primero porque nadie ejecuta la rama apagada.

## 12. Plan de implementación dividido en pequeñas tareas

| # | Tarea | Entregable | Est. |
|---|---|---|---|
| E3.3.1 | Migrar `_DORMITORIO_ANY_PATTERN` y `_BANO_OR_ASEO_PATTERN` en `_check_absurd_routes`/`_check_bathroom_access` a `Espacio.tipo` | G4 sin cambios | 1,5 h |
| E3.3.2 | Migrar `_SALON_PATTERN` (3 usos: `_check_absurd_routes`, `_check_bathroom_access`, `_EVACUATION_DESTINATION_PATTERNS`) | G4 sin cambios | 1,5 h |
| E3.3.3 | Migrar `_DESTINATION_PATTERN` en `_check_pass_through_rooms` | G4 sin cambios | 1 h |
| E3.3.4 | Ampliar `test_e3_paridad_clasificacion.py` para comparar circulation.py migrado vs. comportamiento original | test ampliado, en verde | 1,5 h |
| E3.3.5 | Batería completa (G1–G9, K1–K4, suite, CAP-1…CAP-5, circulation) + informe | informe compacto, sin commit hasta aprobación | 1 h |

`_CIRCULATION_ROOM_PATTERN` no tiene tarea en esta lista: depende de la decisión de §8.3, fuera de este plan.

## 13. Métricas para medir el éxito

1. **Patrones propios de `circulation.py` tras la migración**: de 5 a 1 (`_CIRCULATION_ROOM_PATTERN`, en espera
   de decisión).
2. **Diferencias de comportamiento sobre `ejemplo.dxf`**: 0, medidas por G4.
3. **Cobertura de la paridad**: sigue siendo 34/34 sobre un solo plano; no mejora con este PRD y no se vende como
   si lo hiciera.

## 14. Posibles motivos para NO implementar la idea

1. **El ahorro es pequeño: cuatro `if` menos, en un fichero de 462 líneas que ya funciona.** Cierto. El valor no
   es el ahorro de líneas: es que `circulation.py` deja de tener una fuente de verdad propia sobre semántica,
   que es exactamente el patrón que después hace más barata la migración de `evaluator.py` (veinte reglas, no
   una).
2. **Podría esperarse a resolver primero la brecha de `ANTESALA`/circulación y migrar los 5 patrones juntos.**
   Se decide explícitamente NO: mezclaría una migración neutra (los 4 con paridad demostrada) con una decisión
   de producto sin datos que la respalden (§8.3) — exactamente el tipo de mezcla que las reglas de esta
   iniciativa prohíben.
3. **La alternativa: migrar `evaluator.py` directamente, que es donde vive el 90% de la duplicación.** Cierto,
   y por eso está fuera de alcance aquí (§4): es un frente de veinte reglas que necesita su propio PRD,
   regla a regla, y `circulation.py` es el paso previo más barato porque ya importa el modelo desde E1.

---

**Decisión:** Aprobado por Pablo en la auditoría final de E3 (2026-08-11), junto con E3.3 (implementación de
este PRD) y E3.4 (`evaluate_proportions`/`evaluate_corridor_width` en `analyzer/evaluator.py`, migrados al
mismo patrón `AlmacenGeometria` de usar y tirar — ver diffs y `tests/test_e3_geometria_proporciones.py`).
E3.4 no tiene PRD propio: el §4 de este documento excluye explícitamente "cualquier regla de `evaluator.py`"
del alcance aquí y pide un PRD dedicado, regla a regla, para ese frente. Se aprueba igualmente en esta
auditoría porque Pablo, con la evidencia medida delante (suite 61/60+1 sin variación, G4/G6/G8 sin diferencia
o revisados a mano, canario 11/11 sin patrón nuevo, cero cambios de veredicto en 34 recintos reales + 7 casos
sintéticos pegados al umbral), decidió explícitamente tratar esta auditoría como la aprobación puntual de
ambos, en vez de bloquear E3.4 a la espera de un PRD que documente formalmente lo que ya está medido. No es
un precedente: la próxima regla de `evaluator.py` que se quiera migrar sigue necesitando su propio PRD.
