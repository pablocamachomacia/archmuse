# PRD — E0: red de seguridad y contrato del modelo arquitectónico común

**Estado:** Borrador · **Fecha:** 2026-08-11 · **Autor:** ArchMuse (CTO) · **Aprobado por:** _pendiente_

Diseño de referencia: [`docs/design/2026-08-11-modelo-arquitectonico-comun.md`](../design/2026-08-11-modelo-arquitectonico-comun.md) §18 (etapa E0)
y [`docs/brain/KNOWLEDGE_GRAPH.md`](../brain/KNOWLEDGE_GRAPH.md) §§0, 3, 4, 5, 6.

> **Alcance de E0, en una frase:** escribir el contrato del modelo en papel y congelar el comportamiento actual con
> golden tests. **E0 no crea `modelo/`.** Todo lo que E0 produce son ficheros nuevos bajo `tests/`, más este
> documento. Cero líneas de producción tocadas.

---

## 1. Problema que resuelve

El documento de diseño del 2026-08-11 estableció que ArchMuse necesita un modelo arquitectónico común y que la
primera materialización (E1) consiste en construir `modelo/` **al lado** del flujo actual, con un adaptador, sin
tocar `evaluator.py`. Ese plan tiene un agujero: **hoy no hay forma de demostrar que E1 no rompe nada.**

- 43 de 44 ficheros de test pasan, pero ninguno congela la salida de extremo a extremo sobre `ejemplo.dxf`.
- `KNOWLEDGE_GRAPH.md` §9.2 ya identificó la migración de sustrato de datos como el riesgo mayor: *"sigue
  devolviendo números, y son otros"*.
- `experimentos/` demostró que el grafo cambia resultados el día uno: en VT6/2 desaparece un hallazgo que hoy se
  muestra en producción (*"Baño: acceso directo desde Salón/cocina, sin antesala"*, apoyado en un contacto de
  **0,000 m** de tramo enfrentado).

Sin red de seguridad, ese cambio y una regresión real son indistinguibles. E0 existe para que dejen de serlo.

Segundo problema, más barato de resolver ahora que después: **hay tres vocabularios de incertidumbre** en el repo
(`Hecho` en CAP-1…CAP-5, `passed`+float en `evaluator.py`, `Valor(valor, origen)` en `experimentos/grafo/`).
Si E1 arranca sin decidir cuál gana, nace con el cuarto.

## 2. Usuario afectado

**Ninguno directamente.** E0 es trabajo interno: su usuario es quien implemente E1. Se dice sin adornos porque el
propio documento de diseño (§19.4) avisa de que el valor del modelo común es indirecto y hay que defenderlo como
inversión, no disfrazarlo de funcionalidad.

El beneficiario último es el arquitecto de `NORTH_STAR_2031.md`, dos etapas más allá (E2: reabrir y recalcular un
proyecto guardado).

## 3. Objetivo de negocio

Proteger el activo más caro y más frágil del repositorio —`analyzer/evaluator.py`, ~3.000 líneas validadas contra
un plano real y sin cobertura de comportamiento completo— antes de empezar la única migración transversal que el
producto necesita. E0 cuesta ~2 días; una regresión silenciosa en el evaluador descubierta tres meses después
cuesta la confianza en todos los informes emitidos entre medias.

## 4. Objetivo técnico

Al terminar E0, debe ser cierto que:

1. Existe un juego de golden tests que, ejecutado sobre `ejemplo.dxf` **sin red y sin `ANTHROPIC_API_KEY`**,
   reproduce y compara byte a byte la salida actual del pipeline en ocho puntos de control.
2. Cada golden es **sensible**: alterar deliberadamente la constante que gobierna su comportamiento lo hace
   fallar, y no hace fallar a los demás (§ prueba del canario).
3. El **contrato mínimo del modelo** está escrito, es concreto y no admite dos lecturas: identidad, nodos,
   aristas, geometría, atributos, invariantes y serialización.
4. Queda decidido y escrito que el vocabulario de incertidumbre del modelo es el de `analyzer/hechos.py`, **sin
   modificar ese fichero**.
5. `git diff` sobre `analyzer/`, `app.py`, `static/`, `normativa/`, `ingesta/` y `extraccion/` está vacío.

## 5. Casos de uso

**CU-1 — Implementar E1 sin miedo.** Quien construya `modelo/` ejecuta `python tests/test_golden_*.py` antes y
después de cada paso. Si un golden cambia, o hay una regresión o hay una mejora deliberada que hay que documentar.

**CU-2 — Cambiar el criterio de contigüidad con datos.** Cuando lleguen los 5–8 proyectos reales y haya que
decidir el umbral (decisión abierta §17.2 del diseño), G3 y G4 dicen exactamente qué hallazgos aparecen y cuáles
desaparecen con cada valor, unidad por unidad.

**CU-3 — Aprobar la única diferencia esperada.** El falso positivo de VT6/2 queda congelado en G4 *como está hoy*.
Cuando E1 lo haga desaparecer, el diff del golden es la petición de aprobación: se acepta explícitamente y se
recaptura, o se investiga.

## 6. Casos límite

| Caso | Comportamiento exigido |
|---|---|
| `ejemplo.dxf` no está en disco | El golden **se salta con aviso y sale con código 0**, igual que `test_analizar_planta.py` líneas 78-81. Nunca falla por ausencia del plano |
| `ANTHROPIC_API_KEY` configurada en el entorno | El golden la **borra del entorno antes de importar `app`** y comprueba que `analisis_ia` viaja como `null`. Un golden que dependa de una llamada de red no es un golden |
| Diferencias de coma flotante entre máquinas | Todo número se congela **redondeado a 3 decimales** (milímetro), el mismo redondeo que ya aplica `api_serializer._polygon_points` |
| Orden no determinista de diccionarios o conjuntos | Prohibido serializar conjuntos. Toda lista se ordena por una clave explícita antes de comparar |
| El SVG cambia por un retoque de estilo | **No se congela ningún SVG.** G6 congela estructura y valores, no presentación |
| El golden se vuelve obsoleto por un cambio aprobado | Se recaptura con `python tests/golden.py --recapturar <nombre>` y **el diff se revisa a mano**. Precedente: `docs/design/2026-08-02-dos-sistemas-de-puntuacion.md` §106 |
| Un golden tarda demasiado | Presupuesto: la suite completa de goldens ≤ 90 s. `ejemplo.dxf` se lee **una sola vez** por fichero y se reutiliza |

## 7. Flujo del usuario

No hay flujo de usuario final. El flujo del desarrollador es:

```
  1. python tests/golden.py --capturar-todo      # una vez, al cerrar E0
     └─ escribe tests/fixtures/golden/*.json (8 ficheros, versionados en git)

  2. <se implementa un paso de E1>

  3. python tests/golden.py                       # o pytest tests/
     ├─ 8/8 OK          -> el paso no cambió nada. Seguir.
     └─ N fallos        -> leer el diff:
                            ¿mejora esperada?  -> documentar y recapturar
                            ¿no esperada?      -> es una regresión. Parar.
```

## 8. Criterios de aceptación

E0 está hecho cuando **todos** son verificables sin ambigüedad:

- **A1.** Existen los 8 ficheros `tests/test_golden_*.py` y sus 8 fixtures en `tests/fixtures/golden/`.
- **A2.** `python tests/golden.py` termina en 0 con `ANTHROPIC_API_KEY` **sin definir** y sin acceso a red.
- **A3.** La suite completa (`pytest tests/`) sigue en 43 pasando y 1 fallando, y el fallo sigue siendo
  `test_scoring_coherencia.py` — el marcador deliberado de la decisión pendiente sobre los dos sistemas de
  puntuación, no un defecto nuevo.
- **A4.** La prueba del canario pasa entera (§ Prueba del canario): 4 mutaciones, cada una hace fallar exactamente
  los goldens previstos y ninguno más.
- **A5.** `git diff --stat -- analyzer/ app.py static/ normativa/ ingesta/ extraccion/ experimentos/` está
  **vacío**. E0 no toca una sola línea de producción ni del experimento.
- **A6.** El contrato mínimo (§ Contrato mínimo del modelo) está aprobado por Pablo, y las cinco decisiones que
  fija están escritas sin alternativas abiertas.
- **A7.** Los goldens tardan ≤ 90 s en total en una máquina de desarrollo.
- **A8.** El plan de E1 (§ Plan de E1) tiene 15 pasos, cada uno con entregable comprobable y ninguno estimado en
  más de 2 h.

## 9. Riesgos

1. **Congelar un bug y volverlo doctrina.** G4 congela el falso positivo de VT6/2. *Mitigación:* está documentado
   por su nombre en este PRD, en el fixture y en CU-3; el golden lleva un comentario que dice que es un defecto
   conocido a la espera de E1, no un comportamiento deseado.
2. **Goldens frágiles que nadie mantiene.** Si fallan por ruido, se acaban ignorando. *Mitigación:* redondeo a 3
   decimales, cero SVG, cero IA, cero red, ordenación explícita, y presupuesto de 90 s.
3. **E0 se convierte en E1 por inercia** — "ya que estoy, creo `modelo/`". *Mitigación:* A5 lo prohíbe de forma
   mecánica, y el criterio se comprueba con `git diff`, no con buena voluntad.
4. **Compite con `REFACTOR_MASTERPLAN.md`.** Sí compite: son ~2 días. Argumento a favor: la tarea 18 de ese plan
   es precisamente *"suite de test golden-master"* — E0 **es** esa tarea, ejecutada sobre el caso que más la
   necesita, no una tarea nueva que se cuela.
5. **`ejemplo.dxf` es un solo plano de un solo despacho.** Los goldens no prueban generalidad y no deben venderse
   como tal. Prueban **no-regresión**, que es exactamente lo que E1 necesita.

## 10. Impacto sobre módulos existentes

**Ficheros modificados: ninguno.**

Ficheros nuevos, todos bajo `tests/`:

```
tests/golden.py                        runner + --capturar-todo / --recapturar <nombre>
tests/test_golden_plano.py             G1
tests/test_golden_unidades.py          G2
tests/test_golden_adyacencia.py        G3
tests/test_golden_circulacion.py       G4
tests/test_golden_hechos_cap.py        G5
tests/test_golden_api_analizar.py      G6
tests/test_golden_grafo_experimento.py G7
tests/test_golden_determinismo.py      G8
tests/fixtures/golden/*.json           8 fixtures capturados
```

Módulos **leídos** por los goldens (sin tocarlos): `parser`, `evaluator`, `adyacencia`, `circulation`,
`superficie_util`, `uso_previsto`, `planta`, `ocupacion`, `sectorizacion`, `altura_evacuacion`, `app`,
`experimentos.grafo`.

Consumidores indirectos afectados: ninguno. Un test nuevo no cambia el comportamiento de nada.

## 11. Plan de implementación dividido en pequeñas tareas

Siete tareas, ninguna de más de 2 h. E0 completo: **~1,5 días**.

| # | Tarea | Entregable | Est. |
|---|---|---|---|
| E0.1 | `tests/golden.py`: runner con `check()` (misma convención que el resto de tests), captura/recaptura, borrado de `ANTHROPIC_API_KEY`, lectura única de `ejemplo.dxf`, salto limpio si no existe | runner ejecutable | 2 h |
| E0.2 | G1 + G2 (plano y unidades) | 2 tests + 2 fixtures | 1,5 h |
| E0.3 | G3 (adyacencia) — incluye medir y **registrar sin exigir** el tramo enfrentado, para no cerrar §17.2 | 1 test + fixture | 1,5 h |
| E0.4 | G4 (circulación) — con el comentario del falso positivo de VT6/2 | 1 test + fixture | 1,5 h |
| E0.5 | G5 (hechos CAP-1…CAP-5) | 1 test + fixture | 2 h |
| E0.6 | G6 + G7 + G8 | 3 tests + 3 fixtures | 2 h |
| E0.7 | Prueba del canario: script `tests/canario.py` que aplica las 4 mutaciones en memoria y comprueba el patrón de fallos esperado | script + resultado documentado | 1,5 h |

## 12. Plan de pruebas

E0 **es** el plan de pruebas de E1. Su propia verificación es:

- **Que los goldens pasan** en verde recién capturados (trivial, pero descarta no determinismo).
- **Que los goldens fallan cuando deben:** la prueba del canario (E0.7). Un golden que nunca falla no protege
  nada; ésta es la única prueba real de que la red de seguridad existe.
- **Que no rompen la suite:** A3.
- **Que no tocan producción:** A5, comprobado con `git diff --stat`.

## 13. Métricas para medir el éxito

Se miden **durante E1**, no ahora:

1. **Nº de fallos de golden por paso de E1** que resultan ser regresiones reales. Si es 0 en 15 pasos, E0 no era
   necesario; si es ≥1, se ha pagado solo.
2. **Nº de diferencias aceptadas conscientemente** (esperado: 1 — VT6/2). Si aparecen 5, el modelo está cambiando
   más cosas de las previstas y hay que parar.
3. **Tiempo entre "un paso de E1 rompe algo" y "se sabe qué"**. Objetivo: minutos. Hoy: no se sabría.

## 14. Posibles motivos para NO implementar la idea

Tres, y el tercero es el serio:

1. **Cero valor para el usuario y ~1,5 días de coste.** Cierto. Pero E1 sin E0 es una migración de sustrato de
   datos sin oráculo, y el propio `KNOWLEDGE_GRAPH.md` §9.2 la marca como el riesgo mayor del modelo.
2. **`ejemplo.dxf` no es representativo.** Cierto, y por eso los goldens se venden como no-regresión, no como
   validación. Cuando lleguen los proyectos reales se añaden goldens nuevos; el runner ya lo soporta.
3. **La alternativa real: saltar a E2 (persistir el proyecto), que sí tiene valor visible.** Es el argumento en
   contra más fuerte y hay que contestarlo: **E2 no es posible antes que E1** — no se puede persistir un modelo
   que no existe; persistir hoy sería seguir guardando el informe, que es exactamente el problema §16.1 del
   diseño. El orden E0 → E1 → E2 no es preferencia, es dependencia.

**Un motivo que NO es válido:** "ya tenemos `tests/fixtures/ejemplo-dxf-analisis.json`". Ese fixture es la
respuesta cruda de `/api/analizar` capturada el 2026-08-02 y lo único que lo consume hoy es `test_storage.py`,
como payload de entrada. No compara nada, no cubre `adyacencia`/`circulation`/CAP-1…CAP-5, y no es sensible a
cambios. No es una red de seguridad: es un dato de prueba.

---

# Contrato mínimo del modelo

Lo que E1 debe implementar, y nada más. Cinco decisiones cerradas, todo lo demás explícitamente aplazado.

## C1 — Identidad en dos niveles

```
instance_id   identifica un nodo DENTRO de una versión del grafo.
              Determinista y derivado del orden de lectura, para que dos
              construcciones de la misma versión den los mismos ids:
                  proyecto  -> "pr"
                  edificio  -> "ed-01"
                  planta    -> "pl-01"
                  unidad    -> "un-0001"   (orden de group_rooms_by_unit_label)
                  espacio   -> "es-0001"   (orden de lectura del parser)
              NO significa nada fuera de la versión. Se regenera en cada lectura.

concept_id    identifica "esta habitación" a lo largo de la vida del proyecto.
              OPACO (uuid4 hex de 12, misma forma que storage.py). Se asigna en la
              primera lectura y se HEREDA por emparejamiento en las siguientes.
```

**Prohibido por contrato:** derivar `concept_id` de ningún valor que pueda cambiar — centroide, área, rótulo,
índice, nombre de unidad. La huella provisional del experimento (`f"{unidad}#{x:.1f},{y:.1f}"`,
`experimentos/grafo/constructor.py:117`) **no se promueve**; su propio docstring ya avisa de que no es la solución.

**Aplazado a E2+ (no lo resuelve E1):** el algoritmo de emparejamiento entre versiones. E1 entrega la interfaz
`emparejar(version_anterior, version_nueva) -> dict[instance_id, concept_id]` que **lanza `NotImplementedError`**,
para que el hueco esté declarado y no se rellene por accidente. Con una sola versión, `concept_id` se asigna nuevo
siempre.

## C2 — Cinco nodos

| Nodo | Cardinalidad en E1 | Presencia sobre `ejemplo.dxf` |
|---|---|---|
| `Proyecto` | 1 (raíz) | observado |
| `Edificio` | 1, supuesto | inferido |
| `Planta` | 1, supuesta | no observable |
| `Unidad` | n | observado (etiqueta VT) / inferido (proximidad) |
| `Espacio` | n | observado |

Los otros seis tipos del catálogo (`Parcela`, `Muro`, `Hueco`, `Pilar`, `Instalación`, `Zona común`)
**no tienen clase en E1**: existen **sólo como entrada en el mapa de presencia** del `Proyecto`, con su estado
declarado. Es la aplicación literal de `KNOWLEDGE_GRAPH.md` §8.1 — siete clases vacías durante meses son una
invitación a rellenarlas con valores plausibles.

`Muro` queda fuera de E1 **a propósito**, aunque sea inferible: materializarlo cambia lo que ven las reglas y E1
tiene que ser demostrablemente neutro.

**Ningún nodo lleva campos evaluativos.** Lista negra explícita, comprobada por test: `iluminacion`, `ventilacion`,
`orientacion`, `cumple`, `passed`, `puntuacion`, `score`, `problemas`, `superficie_util`, `eficiencia`.

## C3 — Dos aristas

```
es_contiguo_a   simétrica.  Espacio <-> Espacio.  Comparten separación física.
conecta_con     simétrica.  Espacio <-> Espacio.  Se puede pasar de uno a otro.
                origen = SUPUESTO siempre en E1: sin datos de puertas, tratar la
                contigüidad como paso es una hipótesis, y va escrita en la arista.
```

Atributos de arista: `separacion_m`, `tramo_m`, `distancia_m` (los tres a 3 decimales).

**La pertenencia NO es una arista.** `Espacio.unidad_id` y `Espacio.planta_id` son campos. Representarla dos veces
es la primera vía por la que un modelo empieza a poder contradecirse.

**Criterio de contigüidad en E1 = exactamente el de hoy**, parametrizado pero con el valor actual por defecto:
`tolerancia_muro_m = 0.5` (`adyacencia.WALL_GAP_TOLERANCE_M`), `tramo_minimo = 0.0`. El `tramo_m` **se mide y se
guarda pero no filtra**. Así el umbral queda disponible para decidirlo con los proyectos reales (§17.2 del diseño)
sin que E1 lo cierre por la puerta de atrás.

## C4 — Geometría por referencia

```
AlmacenGeometria          geom_id -> objeto shapely.   ÚNICO sitio del modelo
                          donde vive shapely.
Espacio.geometrias        {"huella_2d": "g-0001"}      un mapa, no un polígono.
```

En E1 la única representación es `"huella_2d"`. `"eje"`, `"solido"` y `"malla"` están en el vocabulario y no se
producen.

Los nodos **no exponen shapely**. Exponen sólo los derivados admitidos por `KNOWLEDGE_GRAPH.md` §0.2 —función pura
de la propia geometría, sin umbrales, estables: `area_m2`, `perimetro_m`, `centroide`, `envolvente`,
`alargamiento`, `profundidad_maxima`. Todos redondeados a 3 decimales al serializar.

**Unidad de medida en el contrato, no en el comentario** (P4 del diseño): el almacén sólo admite geometría en
metros y lo comprueba al insertar. Es la corrección estructural del defecto latente de `Room.area_m2`.

## C5 — `Atributo`: el vocabulario de `hechos.py`, sin tocar `hechos.py`

Todo atributo resuelto de un nodo es un `Atributo`, y `Atributo` **importa** de `analyzer/hechos.py` en vez de
redefinir nada:

```python
# modelo/atributo.py  (E1 — aquí sólo se especifica)
from analyzer.hechos import (KNOWN, ESTIMATED, UNKNOWN, NO_APLICABLE,
                             ALTA, MEDIA, BAJA, Motivo, Hecho)

ORIGENES = ("observado", "declarado", "derivado", "supuesto")

@dataclass(frozen=True)
class Atributo:
    valor:      Optional[Any]
    estado:     str                 # de hechos.ESTADOS
    origen:     Optional[str]       # de ORIGENES; None sólo si estado == UNKNOWN
    confianza:  Optional[str]       # ALTA | MEDIA | BAJA
    motivos:    Tuple[Motivo, ...] = ()
```

Reglas que el tipo hace cumplir por construcción, calcadas de `Hecho.__post_init__`:

- `estado in (KNOWN, ESTIMATED)` exige `valor is not None` **y** `origen in ORIGENES`.
- `estado == UNKNOWN` exige `valor is None` y `motivos` no vacío.
- Nunca un valor sin origen. (Invariante I5.)

**Los dos ejes son ortogonales** y ésta es la decisión que cierra el problema de los tres vocabularios: `estado`
responde *¿qué sé?* y `origen` responde *¿de dónde?*. `Valor(valor, origen)` de `experimentos/grafo/modelo.py`
**desaparece** al promocionar el experimento; era el eje 2 sin el eje 1.

**Puente único hacia el motor:** `Atributo.a_hecho(nombre, ambito, unidad, **extra) -> Hecho`. Es el **único**
punto donde el modelo produce un `Hecho`. Nada dentro de `modelo/` importa CAP-1…CAP-5.

**`analyzer/hechos.py` no se modifica en E1.** Los tres campos que el diseño §7.3 propone (`depende_de`,
`version_modelo`, `actor`/`fecha`) son de E2 en adelante, cuando exista recomputación que los necesite.

## C6 — Ocho invariantes

Se comprueban en el **sellado** de la versión. Su incumplimiento es un error del constructor, nunca un hallazgo
del proyecto.

| # | Invariante |
|---|---|
| I1 | Todo `Espacio` pertenece a exactamente una `Unidad`. Ninguno huérfano |
| I2 | Todo `Espacio` pertenece a exactamente una `Planta` |
| I3 | Toda arista une dos nodos existentes **en esta misma versión** |
| I4 | `es_contiguo_a` y `conecta_con` son simétricas: si A→B, entonces B→A |
| I5 | Todo `Atributo` tiene estado y, salvo `UNKNOWN`, origen. Un valor desnudo es un modelo inválido |
| I6 | Los 11 tipos del catálogo tienen presencia declarada en `Proyecto.presencia`. Ninguno ausente del mapa |
| I7 | Todos los `instance_id` son únicos dentro de la versión |
| I8 | Una versión sellada no se modifica: se congela y su hash de serialización no cambia |

Fuera de E1 (no comprobables sin nodos que no existen): "todo Muro delimita 1..2 espacios" y el solape entre
polígonos —este último ya es una regla de producción (`evaluate_room_overlap`), y **es un hallazgo, no un
invariante**.

## C7 — Serialización determinista

Un único formato, JSON, que es a la vez el artefacto de los goldens y el futuro formato de persistencia de E2.

```json
{
  "contrato": "1.0",
  "sellado": "<sha256 del cuerpo canónico>",
  "proyecto":  {"origen": "dxf", "escala": {...}, "capa": {...}, "presencia": {...}},
  "edificios": [...],
  "plantas":   [...],
  "unidades":  [{"id": "un-0001", "concepto": "...", "etiqueta": {...}, "espacios": ["es-0001", ...]}],
  "espacios":  [{"id": "es-0001", "concepto": "...", "unidad_id": "un-0001", "planta_id": "pl-01",
                 "rotulo": "Dormitorio 1", "tipo": {"valor": "dormitorio", "estado": "KNOWN",
                 "origen": "observado", "confianza": "Media"},
                 "geometrias": {"huella_2d": "g-0001"},
                 "derivados": {"area_m2": 12.345, "perimetro_m": 14.2, ...},
                 "procedencia": {"formato": "dxf", "capa": "00 areas", "id_nativo": "..."}}],
  "aristas":   [{"tipo": "es_contiguo_a", "a": "es-0001", "b": "es-0002", "origen": "observado",
                 "separacion_m": 0.12, "tramo_m": 1.84, "distancia_m": 3.201}],
  "geometrias": {"g-0001": {"tipo": "poligono", "unidad": "m", "puntos": [[0.0, 0.0], ...]}}
}
```

Reglas duras, todas comprobables:

1. **Todo float redondeado a 3 decimales.** Sin excepción.
2. **Toda lista ordenada por `id`** antes de serializar. Ningún conjunto.
3. **JSON con `sort_keys=True`, `ensure_ascii=False`, separadores fijos.**
4. **Round-trip sin pérdida**: `cargar(volcar(m)) == m`, y `volcar(cargar(j)) == j` byte a byte.
5. **`sellado`** = sha256 del cuerpo sin el propio campo. Es la comprobación mecánica de I8.
6. **Cero campos con nombre de formato** fuera de `procedencia` (P6 del diseño). `layer`, `block`, `handle`,
   `guid` sólo pueden aparecer dentro de ese objeto.
7. **Cero campos evaluativos** (lista negra de C2).

## C8 — Cómo se preservan CAP-1…CAP-5

Los ocho módulos cerrados —`hechos.py`, `superficie_util.py`, `uso_previsto.py`, `ocupacion.py`, `planta.py`,
`sectorizacion.py`, `altura_evacuacion.py`, `avisos_altura_evacuacion.py`— y sus tests **no se tocan en E0 ni en
E1**. La preservación es estructural, no una promesa:

1. **Adaptador de compatibilidad** `modelo/compat.py`: `grafo → List[evaluator.Unit]`, reproduciendo **exactamente**
   el orden y la composición de `group_rooms_by_unit_label` (lo congela G2). CAP-1…CAP-5 siguen recibiendo `Unit`
   y no se enteran de que existe un modelo.
2. **Dirección de dependencia de una sola vía:** `modelo/` **no importa** CAP-1…CAP-5. El puente es
   `Atributo.a_hecho()`, y va del modelo al hecho, nunca al revés.
3. **G5 lo demuestra:** congela los hechos que CAP-1…CAP-5 publican hoy sobre `ejemplo.dxf` (estado, valor,
   confianza, código de motivo). Si E1 los mueve un decimal, falla.

---

# Ocho golden tests

Todos sobre `ejemplo.dxf`, sin red, sin `ANTHROPIC_API_KEY`, con la convención de `check()`/`fallos` del resto de
`tests/`. Cada uno compara contra su fixture en `tests/fixtures/golden/`.

| ID | Fichero | Qué congela exactamente | Protege |
|---|---|---|---|
| **G1** | `test_golden_plano.py` | `leer_plano()`: unidad y origen de escala, factor, capa elegida, nº de rooms, y la lista ordenada de `(rotulo, area_m2, capa)` por room | El lector. Cualquier cambio en `parser`/`escala` |
| **G2** | `test_golden_unidades.py` | `group_rooms_by_unit_label()`: nombres de unidad **en orden**, composición (rótulos por unidad) y `total_area_m2` | La agrupación. Es lo que el adaptador de E1 (C8.1) debe reproducir clavado |
| **G3** | `test_golden_adyacencia.py` | Por unidad, pares contiguos con `WALL_GAP_TOLERANCE_M = 0.5`: `(rotulo_a, rotulo_b, separacion_m, distancia_m)` ordenados. **Y `tramo_m` registrado sin exigirlo** | El grafo. Es el oráculo de C3 y del futuro cambio de umbral (CU-2) |
| **G4** | `test_golden_circulacion.py` | `evaluate_circulation()` por unidad: `(tipo, passed, message, path_labels, metric_value)` ordenados. **Incluye el falso positivo conocido de VT6/2, marcado como tal en el fixture** | El primer consumidor que E1 migra. Es el A/B directo del experimento |
| **G5** | `test_golden_hechos_cap.py` | CAP-1…CAP-5 sobre `ejemplo.dxf`: para cada hecho de `superficie_util_db_si`, `superficie_util_ocupable_db_si`, `usos_por_zona`, `planta`, `ocupacion`, `limite_superficie_sector` y `altura_evacuacion` → `(nombre, ambito, estado, valor, confianza, codigo_motivo)`. Esperado según CAP-3: 4 `ESTIMATED` + 2 `UNKNOWN` de ocupación | **C8.** Es la prueba de que CAP-1…CAP-5 salen intactos de E1 |
| **G6** | `test_golden_api_analizar.py` | `POST /api/analizar` sin planta declarada: claves de primer nivel del payload, nº de viviendas, y por vivienda `(nombre, nº habitaciones, puntuacion, títulos de problemas ordenados)`. **`analisis_ia` debe ser `null`.** Sin SVG, sin textos de IA | El contrato de la API. Lo que ve la SPA |
| **G7** | `test_golden_grafo_experimento.py` | `experimentos.grafo.construir_grafo(CRITERIO_ACTUAL)`: nº de espacios, nº de aristas por tipo, mapa de `presencia` completo y salida de `desconocidos()` | La semilla que E1 promociona. Si el experimento cambia, se sabe |
| **G8** | `test_golden_determinismo.py` | Que serializar dos veces da **bytes idénticos**; que el orden de las listas no depende del orden de iteración; que todos los floats tienen ≤3 decimales; y que ningún fixture contiene claves de la lista negra evaluativa ni claves de formato fuera de `procedencia` | Que los otros siete goldens sirvan para algo |

---

# Prueba del canario

Un golden que nunca falla no protege nada. `tests/canario.py` aplica cuatro mutaciones **en memoria** (con
`unittest.mock.patch`, sin escribir en disco, sin tocar ficheros) y comprueba que el patrón de fallos es
**exactamente** el previsto.

> **Enmienda del 2026-08-11, tras ejecutar el canario.** La tabla original de esta sección se escribió sin
> ejecutar nada, y al medirla **dos de las cuatro mutaciones resultaron inertes sobre `ejemplo.dxf`**: no
> cambiaban ni un golden, y habrían dado por cubierta una cascada que no lo estaba. K1 y K4 se sustituyen por
> mutaciones que sí perturban el pipeline, y la matriz pasa a ser la medida, no la supuesta. **No cambia ninguna
> decisión de arquitectura**: el contrato C1–C8, los goldens G1–G8, los invariantes I1–I8 y los criterios A1–A8
> quedan exactamente como estaban aprobados.

**Por qué las dos mutaciones originales eran inertes:**

- **K1 `0,5 → 0,6 m`.** Las 45 aristas de `ejemplo.dxf` tienen separaciones entre 0,000 y **0,380 m**, y el primer
  par no contiguo está a **2,270 m**. Cualquier tolerancia entre 0,39 y 2,26 produce el mismo grafo — que es
  justamente lo que la cabecera de `adyacencia.py` afirma cuando dice que «el margen es enorme». Subir el umbral
  no prueba nada. **Bajarlo a 0,25 m sí**: desaparecen 4 de las 45 aristas (las de 0,261, 0,262, 0,350 y 0,380 m).
- **K4 «Pasillo» → ocupación nula.** En `ejemplo.dxf` **no hay ni un recinto rotulado «Pasillo»**. Los 34 son
  Terraza 8, Dormitorio 1 6, Salón/cocina 5, Tendedero 5, Baño 4, Dormitorio 2 4, Aseo 1, Dormitorio 3 1.
  Reclasificar un rótulo inexistente no cambia nada. **«Terraza» sí existe** —ocho recintos— y además es el error
  plausible de verdad: `superficie_util.py` documenta que el DB-SI **no** excluye la terraza de la superficie
  útil, así que excluirla es exactamente la clase de cambio razonable-pero-equivocado que un golden debe atrapar.

| # | Mutación | FALLAN (medido) | PASAN (medido) |
|---|---|---|---|
| **K1** | `adyacencia.WALL_GAP_TOLERANCE_M`: `0.5` → `0.25` | G3, G4 | G1, G2, G5, G6, G7, G8 |
| **K2** | agrupación forzada por proximidad a `3.0` m en vez de por etiqueta `VT` | G2, G3, G4, G5, G6 | G1, G7, G8 |
| **K3** | `escala`: forzar factor `×10` | G1, G2, G3, G4, G5, G6, G7 | G8 |
| **K4** | `superficie_util`: «Terraza» reclasificada como zona de ocupación nula | G5, G6 | G1, G2, G3, G4, G7, G8 |

**Criterio A4 (sin cambios):** las cuatro mutaciones producen su patrón exacto — 0 goldens insensibles, 0 fallos
adicionales. Un golden que pasa cuando debería fallar es un golden roto.

**Tres diferencias respecto de la predicción original, todas hacia una red más tupida:**

1. **K2 rompe también G3.** Las aristas se listan por vivienda: si cambia el reparto de recintos, cambia el
   listado aunque el criterio de contigüidad sea idéntico.
2. **K3 rompe los siete goldens de comportamiento**, no cuatro. La escala multiplica las separaciones entre
   polígonos, que cruzan la tolerancia de muro, y G7 parte del mismo plano leído. Es la mutación más transversal y
   demuestra que la cascada geométrica está cubierta de extremo a extremo.
3. **K1 no rompe G6, y conviene no perder el motivo.** El único consumidor de `adyacencia` dentro del evaluador es
   `evaluate_evacuation_distance` (`evaluator.py:1653`), y en las seis viviendas de `ejemplo.dxf` devuelve «no
   evaluable» porque ninguna tiene pieza de circulación rotulada. Es decir: **el payload de la API es ciego a los
   cambios de topología en este plano.** En E1, quien protege la topología son G3 y G4, no G6.

**Dos notas metodológicas que el canario dejó comprobadas:**

- **`evaluator.MAX_GAP_BETWEEN_ROOMS_M` no se puede mutar parcheando la constante.** Se enlaza como valor por
  defecto del parámetro `max_gap_m` al definir `group_rooms_by_proximity`, así que cambiar el atributo del módulo
  después no tiene efecto. K2 muta la función de agrupación, que es la única forma que surte efecto. Está
  comprobado explícitamente en `tests/canario.py` (`_nota_constante_inerte`), porque es justo el tipo de detalle
  que hace que una mutación parezca cubierta sin estarlo.
- **G8 es insensible a las cuatro mutaciones por diseño**, y así queda declarado (`INSENSIBLES_POR_DISENO`). No
  vigila el comportamiento del pipeline —para eso están G1–G7— sino la integridad en disco de los fixtures con que
  se vigila; las mutaciones son en memoria y nunca tocan el disco.

K2 y K3 son deliberadamente transversales: comprueban que la cascada agrupación → superficie → hechos → API está
cubierta de extremo a extremo, que es justo el camino que E1 va a mover.

---

# Plan de E1 — 15 pasos

**No se ejecuta hasta que E0 esté aceptado y este PRD aprobado.** Cada paso ≤ 2 h, con entregable comprobable y
los 8 goldens en verde al terminarlo (salvo E1.14, la única diferencia esperada).

| # | Paso | Entregable | Goldens |
|---|---|---|---|
| **E1.1** | Paquete `modelo/` vacío + `tests/test_modelo_fronteras.py`: prohíbe `ezdxf` en todo `modelo/`, `shapely` fuera de `geometria.py`, e importar `parser`/`evaluator` fuera de `constructor.py`/`compat.py` | test de frontera en verde sobre un paquete vacío | 8/8 |
| **E1.2** | `modelo/identidad.py` — `instance_id` determinista (C1), `concept_id` opaco, `emparejar()` que lanza `NotImplementedError` | ids reproducibles entre dos construcciones | 8/8 |
| **E1.3** | `modelo/atributo.py` — `Atributo` sobre el vocabulario de `hechos.py` + `a_hecho()` (C5) | `Atributo` rechaza valor sin origen y `UNKNOWN` sin motivo | 8/8 |
| **E1.4** | `modelo/geometria.py` — `AlmacenGeometria`, derivados puros, comprobación de metros, redondeo a 3 dec (C4) | derivados idénticos a los de `Room` sobre las mismas geometrías | 8/8 |
| **E1.5** | `modelo/nodos.py` — los 5 nodos (C2) + lista negra de campos evaluativos comprobada por test | 5 dataclasses sin un solo campo de conclusión | 8/8 |
| **E1.6** | `modelo/aristas.py` — 2 aristas + `Criterio` parametrizado con los valores de hoy por defecto (C3) | `tramo_m` se mide y no filtra | 8/8 |
| **E1.7** | `modelo/grafo.py` — versión sellada + Graph API portada de `experimentos/grafo/api.py` | `get_spaces`, `neighbors`, `connected_spaces`, `contiguous_spaces`, `find`, `camino`, `camino_mas_corto`, `presencia`, `desconocidos` | 8/8 |
| **E1.8** | `modelo/invariantes.py` — los 8 de C6, comprobados al sellar | sellado que falla ante un grafo inválido construido a mano | 8/8 |
| **E1.9** | `modelo/serializacion.py` — volcado/carga JSON de C7 + round-trip + hash | `cargar(volcar(m)) == m` y bytes idénticos entre ejecuciones | 8/8 |
| **E1.10** | `modelo/constructor.py` — único módulo que importa `parser`; fases 0→3, 5, 6 de `KNOWLEDGE_GRAPH.md` §5 | `PlanoLeido` → versión sellada de `ejemplo.dxf` | 8/8 |
| **E1.11** | `modelo/compat.py` — adaptador `grafo → List[Unit]` (C8.1) | **G2 pasa con las `Unit` producidas por el adaptador**, no sólo con las del evaluador | 8/8 |
| **E1.12** | Golden nuevo **G9**: modelo serializado de `ejemplo.dxf`; y comprobación cruzada de que las aristas del modelo ≡ el fixture de G3 | 9º fixture + equivalencia demostrada | 9/9 |
| **E1.13** | `circulation.py` lee del modelo tras `ARCHMUSE_MODELO=1` (defecto: apagado). **Único fichero de producción tocado en todo E1** | G4 pasa con el flag apagado **y** encendido, salvo VT6/2 | ver E1.14 |
| **E1.14** | Documentar la diferencia de VT6/2 (tramo enfrentado 0,000 m) y **pedir aprobación explícita a Pablo** | nota en el fixture de G4 + decisión escrita | 1 diff esperado |
| **E1.15** | Recapturar G4 con la diferencia aprobada, retirar el flag, `circulation.py` lee sólo del modelo | flag eliminado, 9/9 en verde | 9/9 |

**Lo que E1 NO toca, y es comprobable con `git diff`:** `evaluator.py`, `parser.py`, `storage.py`, `app.py`,
`api_serializer.py`, `plan_svg.py`, `hechos.py`, los ocho módulos de CAP-1…CAP-5, `normativa/`, `ingesta/`,
`extraccion/`, `static/`. El único fichero de producción modificado en los 15 pasos es `circulation.py`, en
E1.13 y E1.15.

**Lo que E1 NO resuelve, dicho para que no se cuele:** emparejamiento entre versiones (E2), persistencia (E2),
muros y huecos (E4), multiplanta y ensamblaje (E3), el umbral de contigüidad definitivo (necesita los proyectos
reales), y CAP-6, que sigue bloqueado y que E1 no desbloquea.

---

**Decisión:** _pendiente de revisión por Pablo_
