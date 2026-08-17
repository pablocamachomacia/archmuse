# Importación de proyectos — diagnóstico y camino

**Fecha:** 2026-08-10 · **Tipo:** fase estratégica corta, sin implementación · **Estado:** para decisión

Objetivo: determinar cómo debe evolucionar la importación para que ArchMuse no dependa de un DXF preparado a medida.
No es una auditoría exhaustiva: lo que no bloquea una decisión inmediata queda marcado **PENDING**.

---

## 1. El problema real del importador

### 1.1 La cifra que resume todo

`ejemplo.dxf`, medido con `ezdxf`:

| | |
|---|---|
| Entidades en modelspace | **219** |
| Entidades dentro de definiciones de bloque | **53.281** |
| Definiciones de bloque | **429** |
| `INSERT` en modelspace | **0** |
| `INSERT` en paperspace | **0** |
| Bloques con contenido que nunca se insertan | **429 de 429** |
| Referencias externas (XREF) | **0** |
| Capas vacías en modelspace | **47 de 55** |

**ArchMuse lee el 0,4 % de la geometría del fichero.** El hallazgo §1.1 del plan DB-SI describía esto como "bloques sin
insertar en modelspace"; medido, es más radical: **no hay ningún `INSERT` en ninguna parte del fichero**. No es que el
montaje esté escondido en un sitio que no miramos — **el montaje no existe en este DXF**.

### 1.2 Qué lee hoy ArchMuse

Todo `analyzer/parser.py` se reduce a dos cosas:

1. **Polígonos cerrados de UNA capa** (`AREA_LAYER = "00 areas"`, o la que elija `capas_candidatas()`).
2. **`MTEXT`/`TEXT` como rótulos**, asignados al polígono que los contiene.

De ahí sale `Room(polígono, etiqueta)` → `Unit`. Y ya está. El modelo de datos de todo el motor —CAP-1 a CAP-5
incluidos— se apoya en esas dos lecturas.

Nota: `_recorrer_plano()` **ya sabe descender por `INSERT` con `virtual_entities()`**, resolviendo capa efectiva y
transformaciones anidadas. Es maquinaria correcta y bien hecha que en este fichero nunca llega a ejecutarse, porque no
hay ningún `INSERT` del que colgar.

### 1.3 Qué información arquitectónica perdemos

Todo lo que no sea "un polígono de superficie con su rótulo". En este fichero, concretamente:

| Capa / familia de bloque | Contenido | Qué desbloquearía |
|---|---|---|
| `00 MURO` | Muros de todas las viviendas | Superficie construida real (hoy imposible, `DB-SI_FACT_MODEL.md` §3.3); sectorización física |
| `00 PUERTA`, `00 PUERTAS` + 154 bloques de carpintería | Puertas, con su hoja y barrido | `C12` (puertas en recorrido de evacuación); adyacencia real en vez de proximidad |
| `00 vidrio` | Acristalamiento | Superficie de hueco real — hoy es un proxy inventado (`ancho fachada × 0,25`, bloques 15 y 19 del evaluador) |
| `nucleo`, `nucleo2`, `escaleralat`, `ascensorcombo`, `asc aparc` | **Núcleos de comunicación completos** (147, 118, 146, 472, 485 entidades) | **CAP-6**: origen de evacuación, salida de planta, `C09`/`C10`/`C11` |
| `00 PILAR`, `00 estructura`, `PILAR_HORMIGON` | Estructura | Dominio 11 de `BRAIN_ARCHITECTURE.md` |
| `VT01`…`VT25` | **25 tipos de vivienda, dibujados a escala real en el origen** | La geometría verdadera de cada vivienda |

### 1.4 Las convenciones que ArchMuse asume hoy — ninguna es un estándar

Están implícitas en el código, nunca declaradas como requisito al usuario:

1. Existe **una capa** con **un polígono cerrado por estancia** (no muros: el área ya dibujada).
2. Esa capa se llama `00 areas`, o es adivinable por heurística (`capas_candidatas`).
3. El rótulo de la estancia es un texto **dentro** del polígono.
4. La vivienda se identifica por un rótulo de texto suelto, tipo `VT<n>/<m>`.
5. Todo lo relevante está en **modelspace** (o alcanzable por `INSERT` desde él).
6. Un color distinto de BYLAYER puede significar "polígono contenedor" y hay que descartarlo
   (`_discard_container_candidates`).
7. La escala sale de `$INSUNITS` o la declara el usuario.

**Esto no es "el formato DXF": es la convención de rotulado de un despacho concreto.** Otro estudio dibujará las
superficies en `A-AREA-BNDY`, o no las dibujará en absoluto y esperará que se midan desde los muros, o entregará una
planta por fichero, o montará el edificio con XREFs. Ninguna de esas variantes se lee hoy.

### 1.5 Qué se resuelve leyendo `BLOCK` directamente, y qué no

**Sí se resuelve** — hay un puente determinista y verificable:

- El rótulo `VT22/1` de modelspace ↔ la definición de bloque `VT22` (mismo número, con cero a la izquierda).
  Los 7 rótulos VT de modelspace tienen los 25 bloques `VT01`…`VT25` detrás.
- Cada bloque VT está dibujado **en metros, en el origen** (`VT22`: 7,5 × 9,9 m, base point 0,0), con muros, puertas,
  vidrio, sanitarios, cocina y mobiliario, e `INSERT` anidados de carpintería que `virtual_entities()` ya sabe resolver.
- Los núcleos (`nucleo`, `escaleralat`, `ascensorcombo`) están igual de disponibles.

Es decir: **la geometría real por tipo de vivienda es recuperable hoy, sin cambiar el formato de entrega.**

**No se resuelve — y esto es lo importante para CAP-6:**

- **El ensamblaje.** Qué tipo va en qué planta, cuántas unidades de cada tipo, dónde queda el núcleo respecto a las
  viviendas, qué puerta abre al rellano. Con 0 `INSERT`, esa información **no está en el fichero**. No se puede leer
  algo que no se ha escrito. → **CAP-6 no se desbloquea leyendo bloques.**
- **La semántica de la geometría.** Pasar de "líneas sueltas en la capa `00 MURO`" a "un muro con dos caras y un
  espesor", o de "arco + línea en `00 PUERTA`" a "un hueco de paso de 82 cm entre la estancia A y la B", es
  **reconocimiento geométrico**, no lectura de fichero. Ese es el trabajo real, y es donde vive el riesgo.

### 1.6 Qué exige de verdad una convención del archivo

Sólo dos cosas, y conviene no pedir más:

1. **Que el proyecto esté montado** (INSERTs, XREFs, o una planta por fichero). Sin esto no hay edificio, sólo un
   catálogo de tipos.
2. **Que se sepa qué planta es cada cosa.** Es lo mismo que CAP-4 ya resolvió preguntando en vez de adivinar.

Todo lo demás (nombres de capa, colores, rotulado) **no debe ser una convención impuesta**: debe ser un perfil detectado
y confirmado. Ver §3.

---

## 2. Qué necesitamos de proyectos reales

No hace falta un corpus. Hace falta **diversidad de convención**: 3 despachos distintos valen más que 20 ficheros del
mismo. Objetivo: **5–8 proyectos de al menos 3 despachos**.

### Por proyecto — obligatorio

1. **El DXF/DWG tal y como se entregó**, sin limpiar ni preparar. Un fichero "arreglado para que funcione" destruye
   exactamente el dato que buscamos.
2. **El PDF del mismo plano** — para saber qué se ve, y por tanto qué debería haberse leído.
3. **Cinco preguntas contestadas** por quien lo dibujó:
   - ¿En qué capa están las superficies de las estancias, si es que hay una?
   - ¿Cómo se rotula una vivienda?
   - ¿El plano está montado en modelspace, por bloques, o por XREF a otros ficheros?
   - ¿Una planta por fichero, o todas en el mismo?
   - ¿En qué unidades dibujáis (m, cm, mm)?

### Por proyecto — muy deseable

4. **La memoria/cuadro de superficies** (PDF o Excel). Es la única **verdad de referencia** contra la que medir el error
   del importador. Hoy no tenemos ninguna: los números de `ejemplo.dxf` no están contrastados contra nada externo.

### Criterio de aceptación de la muestra

No es la cantidad. La muestra está completa cuando **al menos dos proyectos rompan una convención distinta** de las
siete de §1.4. Si los 8 se leen igual que `ejemplo.dxf`, la muestra no sirve: no ha probado nada.

**PENDING:** cómo se consigue (red de contactos de Pablo, colegio de arquitectos, cliente piloto). Es el punto de mayor
plazo de todo el plan y por eso debe arrancar antes que cualquier código.

---

## 3. Arquitectura recomendada para la capa de importación

Tres niveles separados. Hoy `parser.py` mezcla el 0 y el 1, y ése es el refactor de fondo.

**Nivel 0 — Lector (por formato).** Fichero → entidades geométricas neutras (polilíneas, líneas, textos, bloques con su
transformación). No sabe nada de arquitectura. Un lector por formato; es la única pieza que se duplica al añadir uno.

**Nivel 1 — Reconocedor (único, compartido).** Entidades neutras → hechos arquitectónicos (estancia, muro, hueco,
núcleo, planta). Aquí vive toda la incertidumbre, y aquí está la decisión clave:

> **El importador no devuelve geometría "buena o mala": devuelve `Hecho` con estado, confianza y procedencia** —
> exactamente el contrato de `analyzer/hechos.py` que CAP-1…CAP-5 ya usan.

Eso hace que "no he sabido leer los muros" deje de ser un fallo silencioso y pase a ser un `UNKNOWN` con motivo, que el
motor ya sabe propagar sin fabricar un veredicto. Es también, literalmente, la relación Observación → Hecho de
`docs/brain/FACT_MODEL.md`: el Nivel 0 produce Observaciones, el Nivel 1 las promueve a Hechos.

**Nivel 2 — Perfil de convención.** Una declaración por despacho (qué capa, qué rotulado, qué unidades, cómo se monta),
**detectada y confirmada por el usuario, nunca adivinada en silencio**. El embrión ya existe y funciona:
`capas_candidatas()` + `CapaIndeterminada`/`EscalaIndeterminada` preguntan en vez de asumir. Generalizar ese patrón —
no inventarlo.

**Principio rector, heredado de CAP-1…CAP-5:** ante la duda, preguntar o marcar `UNKNOWN`; jamás rellenar el hueco con
un valor por defecto que luego viaja como si fuera un dato. Es el mismo principio que ya evitó inventar
`superficie_construida` y que gobierna la hipótesis de CAP-5.

---

## 4. Formatos, por prioridad

**1 — DXF/DWG real, sin preparar. Prioridad absoluta.** Es lo que los arquitectos tienen hoy, es lo único que el
producto ya lee parcialmente, y es donde está el 100 % del valor a corto plazo. Todo lo demás puede esperar.

**2 — IFC. Es el destino, no el presente.** Un IFC trae muros, huecos, plantas y espacios **ya semantizados**: elimina
de golpe el Nivel 1 entero, que es justo la parte cara y arriesgada. Pero casi ningún despacho residencial español
pequeño o mediano entrega IFC hoy. Recomendación: **no construirlo ahora, y sin embargo diseñar el Nivel 1 de modo que
un IFC entre por el Nivel 0 y se salte el reconocimiento** — el modelo de `Hecho` ya lo permite sin cambios. Es el hito
de BIM de `NORTH_STAR_2031.md`, y llegar a él sin migración de datos depende de decidir bien ahora.

**3 — PDF. Prioridad baja, y NO para geometría.** Un PDF vectorial da líneas sin capas ni semántica: para reconocer
arquitectura es *peor* que el DXF, no mejor. Su valor real es doble y distinto: **verdad de referencia** (el cuadro de
superficies, §2.4) y fallback de "no tengo DXF".
⚠️ No confundir con `extraccion/segmentador_pdf.py`, que ya existe: **ése lee texto normativo del CTE, no planos.** Son
dos problemas sin relación.

**DWG:** no es una decisión de formato, es un problema de conversión — `ezdxf` no lo lee.
**PENDING:** convertir en servidor (ODA File Converter, licencia por revisar) o exigir DXF en la exportación. No bloquea
nada mientras la muestra se pida en los dos formatos.

---

## 5. Estado del repositorio — B1 / B2 / B3

Inventario a fecha de hoy, **sin tocar nada**. `HEAD` = `fe084d6` (CAP-5). Verificado: el árbol commiteado importa y
arranca por sí solo — nada de lo pendiente es necesario para que el producto funcione hoy.

| | **B1 — Motor de normativa territorial** | **B2 — Scoring / severidad / falsos positivos** | **B3 — Experimento de grafo** |
|---|---|---|---|
| **Código sin trackear** | `normativa/` (~3.777 líneas .py + corpus YAML + esquemas), `extraccion/almacen.py`, `segmentador_pdf.py`, `terminologia.py`, `ingesta/fuentes/codigotecnico.py`, `scripts/` | `analyzer/referencias_normativas.py` | `experimentos/` (~993 líneas), `analyzer/adyacencia.py` |
| **Modificado sobre commit** | `analyzer/cte_zonas.py` (−133/+133, pasa a leer de `normativa/`), `normativa/loader.py`, `ingesta/*`, `extraccion/pipeline.py`, `requirements.txt` (+pyyaml, jsonschema, pypdf) | `analyzer/evaluator.py` (**+531**: `evaluate_evacuation_distance`, `evaluate_itinerario_accesible`, `rating_con_severidad`, `evaluate_room_overlap`, hueco dimensional), `api_serializer.py`, `static/app.js` (−190) | `analyzer/circulation.py` (−113, extracción del grafo a `adyacencia.py`) |
| **Tests sin trackear** | `test_normativa_*` (5), `test_ingesta_codigotecnico`, `test_extraccion_*` (2), `test_terminologia`, `test_cte_zonas_fachada` | `test_severidad_veta_color`, `test_sin_duplicados`, `test_solape_interno`, `test_hueco_dimensional`, `test_evacuacion`, `test_itinerario_accesible`, `test_superficie_equivalencia` | — |
| **Docs sin trackear** | `NORMATIVE_ENGINE.md`, `NORMATIVE_RESOLUTION.md`, `TRACEABILITY.md`, los dos de auditoría de fuentes CTE del 06-08 | `FALSE_POSITIVES.md`, `NORMATIVE_AUDIT.md` | `docs/brain/KNOWLEDGE_GRAPH.md` |
| **Veredicto** | **Conservar entero.** Es la iniciativa más grande y más avanzada; CAP-1…CAP-5 ya citan su corpus (`dbsi_anejo_a.yaml`) | **Conservar.** `evaluator.py` es el fichero más delicado del repo y es el que más ha cambiado sin versionar — el de mayor riesgo de pérdida | **Conservar, pero es lo único genuinamente experimental.** `adyacencia.py` sí es producción (lo consume `evaluator.py`) |

**Lo que NO debe tocarse en ningún caso:** `analyzer/hechos.py`, `superficie_util.py`, `uso_previsto.py`, `ocupacion.py`,
`planta.py`, `sectorizacion.py`, `altura_evacuacion.py`, `avisos_altura_evacuacion.py` y sus tests — CAP-1…CAP-5,
cerrados y commiteados. Ninguna de las tres ramas los necesita.

**Nada parece obsoleto.** No hay ficheros muertos ni duplicados entre las tres ramas; `adyacencia.py` es precisamente lo
contrario (una des-duplicación deliberada). No hay nada que proponga borrar.

**Riesgos, por orden:**

1. **`evaluator.py` con +531 líneas sin versionar** es la mayor exposición del repo. Un fichero de ~3.000 líneas, el más
   acoplado de todos, con cinco reglas nuevas dentro y sin punto de retorno.
2. **Las tres ramas tocan `requirements.txt`, `evaluator.py` y `api_serializer.py` sin coordinación.** Cuanto más se
   tarde en separarlas en commits, más caro será hacerlo.
3. 43 de 44 ficheros de test pasan; el único fallo (`test_scoring_coherencia.py`) es un marcador deliberado de la
   decisión pendiente sobre los dos sistemas de puntuación, no un defecto.

**No se ha hecho ningún commit de B1/B2/B3, ni se han mezclado, ni se ha borrado nada.**

---

## 6. Recomendación del siguiente paso

**Dos cosas en paralelo, y ninguna es escribir el importador.**

**(a) Empezar hoy a pedir la muestra (§2).** Es lo que más plazo tiene y no depende de nosotros. Cualquier decisión de
arquitectura tomada sin ella es una decisión tomada sobre un solo fichero de un solo despacho — exactamente el error que
esta fase existe para no cometer.

**(b) Una prueba de concepto de un día contra `ejemplo.dxf`**, en `experimentos/`, sin tocar producción: leer los
bloques `VT01`…`VT25` y los núcleos, y **medir** cuánta información arquitectónica nueva aparece (muros, huecos,
puertas) frente a lo que hoy se lee. Es barato, es medible, y contesta la pregunta concreta que bloquea la decisión: si
el reconocimiento del Nivel 1 es viable o es un pozo.

**Y una decisión que sí conviene tomar ya, aunque no requiera código:** el fichero de trabajo del repo. Recomiendo
**separar B1/B2/B3 en tres commits** antes de abrir cualquier frente nuevo — empezando por `evaluator.py` (B2), que es
la exposición más grande. No es una tarea de producto, pero es la que más valor protege por hora invertida.

**Lo que NO recomiendo ahora:** empezar CAP-6 (sigue bloqueado, y §1.5 demuestra que leer bloques no lo desbloquea),
construir el lector IFC (§4.2), ni tocar el importador antes de tener la muestra.
