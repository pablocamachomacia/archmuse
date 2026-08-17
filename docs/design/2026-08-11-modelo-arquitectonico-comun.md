# El modelo arquitectónico común de ArchMuse

**Fecha:** 2026-08-11 · **Tipo:** diseño de arquitectura, sin implementación · **Estado:** para decisión
**HEAD:** `f52956d` · árbol limpio · CAP-1…CAP-5 cerrados · B1 `37c1aa7`, B3 `5f16091`, B2 `85d7733`

Continúa [2026-08-10-importacion-de-proyectos.md](2026-08-10-importacion-de-proyectos.md) y
[2026-08-11-poc-bloques-vt.md](2026-08-11-poc-bloques-vt.md). No los repite: aquellos preguntaban *qué se
puede leer de un DXF*; éste pregunta **qué objeto interno tiene que existir para que todo el producto —normativa,
generador, editor, 3D, documentación— trabaje sobre el mismo proyecto**.

**Grounding.** Todas las afirmaciones sobre el código de hoy están comprobadas leyendo los ficheros el 2026-08-11:
`analyzer/parser.py`, `evaluator.py`, `hechos.py`, `planta.py`, `ocupacion.py`, `uso_previsto.py`,
`altura_evacuacion.py`, `sectorizacion.py`, `superficie_util.py`, `adyacencia.py`, `circulation.py`,
`spatial_quality.py`, `chain_effects.py`, `plan_svg.py`, `api_serializer.py`, `storage.py`, `ai_generator.py`,
`pdf_report.py`, `app.py`, `static/viewer-edificio.js`, `static/viewer-vivienda.js`, `experimentos/grafo/*`.
Cuando un documento de `docs/brain/` afirma algo que el código no sostiene, gana el código y se dice.

**Advertencia previa, y es la conclusión más incómoda de todo el informe.** Buena parte de lo que pides ya está
diseñado: `docs/brain/KNOWLEDGE_GRAPH.md` (46 KB) resuelve las secciones 1, 2, 3, 4 y 8 de tu encargo con más
detalle del que yo añadiría, y `experimentos/grafo/` ya lo tiene ejecutándose contra `ejemplo.dxf` con 12 de 12
salidas idénticas a producción. **El problema de ArchMuse hoy no es falta de diseño del modelo: es que el modelo
diseñado no existe en el código, y el volumen de diseño acumulado (≈1,4 MB en `docs/brain/` y raíz) crece más
rápido que su materialización.** Este documento, por tanto, no vuelve a diseñar el grafo: lo da por bueno, lo
extiende a lo que `KNOWLEDGE_GRAPH.md` no cubre (generador, editor, 3D, documentación, importación multiformato,
conflictos de evidencia) y dedica su parte más útil a la §15 (compatibilidad) y la §18 (plan por etapas).

---

## 1. Principios

Nueve, y los seis primeros no son nuevos: son los que CAP-1…CAP-5 ya hacen cumplir por construcción. Los tres
últimos son la aportación de este documento.

**P1 — El modelo describe; el motor concluye.** Ningún nodo lleva un campo evaluativo. `Espacio.iluminacion`,
`Vivienda.cumple`, `Planta.puntuacion` no existen. (`KNOWLEDGE_GRAPH.md` §0.1.)

**P2 — Ningún valor viaja desnudo.** Todo atributo resuelto es (valor, estado, procedencia). Es literalmente el
contrato de `analyzer/hechos.py`, que ya rechaza en `__post_init__` un `UNKNOWN` con valor o sin motivo.

**P3 — El silencio está prohibido.** "No hay ventanas" y "este plano no dibuja ventanas" son estados distintos del
modelo, no la misma ausencia de nodos (`KNOWLEDGE_GRAPH.md` §0.4).

**P4 — La unidad de medida es parte del tipo, no del comentario.** Hoy `Room.area_m2` devuelve `polygon.area` y
sólo es verdad si la `Room` vino de `leer_plano`; el propio docstring lo admite. Un modelo común no puede
sostener esa distinción en prosa.

**P5 — Una definición, un sitio.** Contigüidad, agrupación en viviendas y pertenencia a planta se deciden una vez.
Hoy hay cinco implementaciones de "estas dos habitaciones están juntas" con cuatro umbrales distintos
(`KNOWLEDGE_GRAPH.md` §1; `adyacencia.py` desduplicó sólo una de ellas).

**P6 — Ninguna capa conoce el formato de origen.** El modelo no tiene campos llamados `layer`, `block`,
`ifc_guid`. Esos punteros viven dentro de la procedencia, con un esquema canónico.

**P7 — La fuente de verdad se declara; todo lo demás se recalcula.** Si un dato puede derivarse del modelo, no se
persiste como dato. Si se persiste (caché), lleva la versión del modelo con la que se calculó y muere con ella.

**P8 — Una identidad estable o no hay producto.** Sin `concept_id` que sobreviva a una relectura no hay editor, ni
histórico, ni comparación de versiones, ni ciclo de vida de hallazgos. Hoy `circulation.py` usaba `id()` de Python
como identidad de habitación — la identidad más efímera posible.

**P9 — Una sola geometría de proyecto, y las vistas se derivan de ella.** Nunca al revés. Hoy la API publica en
`poligono` la geometría **re-colocada para el SVG** (`plan_svg.layout_room_polygons`: modo real, compactado o
cuadrícula) y el visor 3D extruye eso. La presentación está autorando geometría.

---

## 2. Modelo conceptual

Cinco capas. La aportación estructural de este documento es **separar la capa 1 de la capa 2**, que hoy están
fundidas en `Room` (polígono + rótulo + capa del DXF en el mismo objeto).

```
   ┌───────────────────────────────────────────────────────────────┐
   │ 4. CONCLUSIONES        Hechos derivados · Hallazgos · Reglas   │  ← normativa, scoring
   │    (no viven en el modelo; lo referencian)                     │
   ├───────────────────────────────────────────────────────────────┤
   │ 3. EVIDENCIA           de dónde salió cada afirmación,         │  ← hechos.py (ya existe)
   │    procedencia · método · confianza · fecha · puntero          │
   ├───────────────────────────────────────────────────────────────┤
   │ 2. SEMÁNTICA           identidad · tipo · rol · pertenencia    │  ← el grafo
   │    Proyecto/Edificio/Planta/Unidad/Espacio/Muro/Hueco/…        │
   ├───────────────────────────────────────────────────────────────┤
   │ 1. GEOMETRÍA           puntos · polilíneas · polígonos ·       │  ← sin nombres, sin semántica
   │    sólidos · transformaciones · CRS · unidad                    │
   ├───────────────────────────────────────────────────────────────┤
   │ 0. OBSERVACIONES       entidades neutras del fichero de origen │  ← lector DXF/DWG/IFC
   └───────────────────────────────────────────────────────────────┘
```

Reglas de tráfico entre capas, y son las que hacen que el modelo sirva de verdad:

- La capa 2 **referencia** geometría por id; nunca la contiene. Un elemento puede tener varias representaciones
  geométricas a la vez (huella 2D, eje, sólido, malla) sin dejar de ser el mismo elemento. Es lo que permite que
  el 3D consuma el mismo modelo y no una conversión (§13).
- La capa 3 cuelga de **afirmaciones**, no de objetos: no es "el Espacio tiene confianza media", es "que este
  espacio sea un dormitorio tiene confianza media, porque se leyó de un rótulo".
- La capa 4 **no puede escribir** en las capas 1–3. Ni una regla, ni un serializador, ni un visor.
- La capa 0 se descarta después de construir el modelo, salvo los punteros de procedencia.

### 2.1 El objeto que falta y que lo explica todo: el ensamblaje

`ejemplo.dxf` tiene 0 `INSERT`: la geometría de las 25 viviendas tipo existe, pero **el dato de qué tipo va en qué
planta y en qué posición no está en el fichero**. Ese dato tiene nombre y hoy no existe en ninguna parte de
ArchMuse: es el **ensamblaje**.

Y no falta sólo en el DXF. Falta en el producto entero, tres veces:

| Dónde | Qué hace hoy | Consecuencia |
|---|---|---|
| `ai_generator.UNIT_OFFSET_M = 500.0` | Separa cada vivienda generada 500 m en X para que las reglas no confundan medianeras | El proyecto generado **no tiene coordenadas reales** |
| `plan_svg._layout_rooms` | Re-coloca las habitaciones (real / compactado / cuadrícula) para dibujar | La geometría publicada no es la del proyecto |
| `static/viewer-edificio.js` | Agrupa por el prefijo `"Planta N · …"` del nombre, cierra el hueco de 500 m y **reconstruye el edificio en JavaScript** con `WALL_THICKNESS = 0.15` propio | El edificio sólo existe en el cliente, y es otro edificio distinto en cada visor |

**El edificio de ArchMuse se ensambla tres veces, de tres maneras, y ninguna de ellas es el modelo.** El modelo
común es, antes que nada, el sitio donde el ensamblaje se decide una vez: instancias con transformación, plantas
con cota, y unidades con posición real.

---

## 3. Entidades

Tu lista tenía 25 candidatos. **Sólo 11 deben ser entidades.** El resto son tipos, relaciones, propiedades,
derivados, hipótesis o roles — y convertirlos en clases sería el error clásico de duplicar el vocabulario del
dominio en el vocabulario del código.

### 3.1 Las once entidades

| Entidad | Identidad | Por qué es entidad | Estado hoy |
|---|---|---|---|
| **Proyecto** | raíz, versionada | ciclo de vida propio, es lo que se guarda y se edita | ⚠️ existe como *informe*, no como proyecto |
| **Parcela** | 1 por proyecto (hoy) | ámbito normativo urbanístico, referencia externa (catastro) | ❌ declarada por formulario, sin nodo |
| **Edificio** | n por parcela | agrupa plantas; ámbito de altura de evacuación (CAP-5 ya lo usa) | ⚠️ implícito, uno por fichero |
| **Planta** | n por edificio | **el ámbito que el DB-SI indexa** (`planta.py` lo documenta) | ❌ hoy es un *hecho*, no una entidad |
| **Unidad** | vivienda o local | agrupa espacios; ámbito de casi toda la normativa de habitabilidad | ✅ `evaluator.Unit`, sin identidad estable |
| **Espacio** | el nodo central | todo lo demás cuelga de él | ✅ `parser.Room`, sin identidad estable |
| **Muro / partición** | elemento de separación | soporta espesor, superficie construida, sectorización física | ⚠️ inferible del hueco entre polígonos (0,03–0,38 m) |
| **Hueco** | puerta \| ventana \| paso | conexión real entre espacios; superficie de iluminación | ❌ no observable en el DXF de distribución |
| **Elemento estructural** | pilar \| viga \| forjado | Dominio 11; canto de forjado para cotas 3D | ❌ hay capa `00 PILAR`, sin leer |
| **Núcleo** | agrupación con identidad | sirve a n plantas; origen de evacuación y salida de planta (CAP-6) | ❌ hay bloques `nucleo`, `escaleralat`, `ascensorcombo` |
| **Instalación** | sistema | Dominio de instalaciones | ❌ fuera de alcance a corto |

### 3.2 Lo que NO debe ser una clase, y por qué

| Candidato | Qué es realmente | Justificación |
|---|---|---|
| **Habitación** | = Espacio | "habitación" es un *tipo* del catálogo de `SPACE_TAXONOMY.md` (29 tipos), no otra clase |
| **Vivienda** | = Unidad con uso residencial | si fueran clases distintas, cada regla de superficie se escribiría dos veces |
| **Pasillo / circulación** | Espacio de tipo circulación | la *circulación* como sistema es un recorrido sobre el grafo, un resultado, no una entidad |
| **Puerta / Ventana** | Hueco con subtipo | comparten atributos (ancho, alto, antepecho, muro anfitrión) y todas las reglas los tratan juntos |
| **Escalera / Ascensor** | Espacio + relación `conecta_plantas` | son recintos reales que ocupan superficie y computan en la ocupación: si fueran clases aparte quedarían fuera de las sumas |
| **Sector de incendio** | agrupación **normativa** derivada | conjunto de espacios + hipótesis; vive en el dominio DB-SI, referenciando espacios. Nunca un campo `Espacio.sector` |
| **Salida** | **rol** de un hueco o espacio en un recorrido | "salida de planta" es una conclusión del DB-SI, cambia con la altura de evacuación y la ocupación |
| **Fachada** | agrupación derivada de muros exteriores | hoy es un proxy (`_facade_bearing_deg` sobre el lado largo del polígono); no puede ser fuente de verdad sin envolvente observada |
| **Cubierta** | elemento constructivo horizontal | misma familia que forjado; declarada, no observada |
| **Cota** | propiedad de Planta (`cota_base_m`) | no tiene identidad ni ciclo de vida |
| **Superficie** | **magnitud con criterio** | no hay "la" superficie: hay útil, construida, ocupable DB-SI, computable urbanística. Cada una es un Hecho con su definición normativa citada — `superficie_util.py` ya lo hace bien |
| **Volumen** | derivado de huella × altura | idem |
| **Material** | **referencia externa** + asignación | una entidad `Material` por cada hormigón es un catálogo, no un modelo de proyecto |

### 3.3 Clasificación pedida en tu §1

- **Entidades:** las once de §3.1.
- **Relaciones:** contiene/pertenece, delimita, da a, sirve a, conecta con, se apoya en, se ubica en, es contiguo a
  (los siete de `ARCHITECTURAL_ONTOLOGY.md` §0.1 + el añadido de `KNOWLEDGE_GRAPH.md` §0.5). Ver §5.
- **Propiedades:** rótulo literal, tipo (valor, origen), cota, espesor, altura libre, uso previsto.
- **Geometría:** capa 1, referenciada por id (§6).
- **Hechos derivados:** superficies, ocupación, altura de evacuación, límite de sector — **ya existen y están
  bien**: CAP-1…CAP-5.
- **Hipótesis:** altura de hueco 1,30 m; muro inferido del hueco entre polígonos; `conecta con` aproximada por
  contigüidad; altura de evacuación estimada por nº de plantas × altura libre (`altura_evacuacion.py`
  `ORIGEN_HIPOTESIS_PLANTAS`). Todas deben llevar estado `ESTIMATED` y su hipótesis pegada, como ya hacen.
- **Referencias externas:** `concept_id` del corpus normativo (`normativa/`), municipio/zona climática INE,
  catastro, catálogos de material. **Nunca se copian dentro del modelo: se citan.** `hechos.py` ya lo resolvió
  guardando `referencia_normativa` como `concept_id` y no como literal.

---

## 4. Semántica

La semántica es el par (tipo, origen) más la pertenencia. Tres reglas.

**4.1 El tipo nunca es un `str` desnudo.** Un espacio no es `tipo = "dormitorio"`. Es
`tipo = (dormitorio, observado-por-rótulo)`, `(dormitorio, declarado)` o `(desconocido, —)`. Hoy `evaluator.py`
clasifica por expresión regular sobre el rótulo y un polígono sin rótulo entra en el motor sin tipo, y las reglas
simplemente no le aplican, en silencio.

**4.2 El rótulo literal se conserva siempre, junto al tipo interpretado.** Son dos datos distintos:
`"DORM. PPAL."` es el dato observado; `dormitorio` es la interpretación. Hoy sólo sobrevive el primero y cada
módulo lo vuelve a interpretar con su propia regex.

**4.3 La semántica no puede depender de que el texto esté bien escrito.** El `SYSTEM_PROMPT` de `ai_generator.py`
obliga literalmente al modelo a escribir `"Dormitorio 1"` *"EXACTAMENTE así, con esas mayúsculas y acentos, para
que el sistema de reglas automático… las reconozca"*. Eso es un acoplamiento entre el generador y las regex del
evaluador disfrazado de instrucción de diseño. En el modelo común el generador emite `tipo=dormitorio, orden=1`
como dato; el rótulo es cosmética.

---

## 5. Relaciones y grafo espacial

### 5.1 Las relaciones que pediste, y cómo se representan

| Pedida | Representación | Quién la crea | Nota |
|---|---|---|---|
| Edificio → plantas | `contiene`, ordenada por cota | declarada o por fichero | hoy no existe: no hay entidad Planta |
| Planta → espacios | `contiene` | constructor | invariante: todo espacio en exactamente una planta |
| Espacio → vivienda | `pertenece a` | constructor (etiqueta VT observada, o proximidad inferida) | el origen se conserva |
| Vivienda → habitaciones | inverso del anterior | — | no es una relación nueva |
| Habitación → puertas | `Hueco` con `muro_anfitrion` + 2 espacios | reconocedor, si hay carpintería | ❌ no creable hoy |
| Puerta → espacios conectados | la arista `conecta con` **se deriva del hueco** | constructor | hoy `conecta con` es contigüidad supuesta |
| Ventana → muro/fachada | `Hueco.muro_anfitrion` + `da a` (exterior/patio) | reconocedor | ❌ no creable hoy |
| Escalera → plantas | `Espacio(tipo=escalera)` + `conecta_plantas[]` | ensamblaje | requiere multiplanta |
| Ascensor → plantas | idéntico, con subtipo | ensamblaje | idéntico |
| Espacio → sector | **no es arista del grafo**: es una agrupación del dominio DB-SI que referencia espacios | motor normativo | P1 |
| Elemento → geometría | referencia por id, n representaciones | constructor | §6 |

### 5.2 Por qué el grafo espacial es la pieza que más devuelve

Porque tres dominios distintos —evacuación, accesibilidad y circulación— hacen hoy la misma pregunta topológica con
tres criterios distintos, y ninguno sabe de los otros:

```
        HOY                                  FUTURO

  evaluator._is_adjacent (0,30 m borde)      ┌──────────────┐
  evaluator.group_by_proximity (2,0 m)       │              │
  circulation → adyacencia.py (0,5 m)   ───► │ GRAFO ESPACIAL│ ◄── una definición,
  plan_svg._cluster_rooms (2,0 m)            │  (una vez)    │     un umbral,
  ai_generator._is_adjacent (copia)          │              │     una corrección
                                             └──────┬───────┘
   5 implementaciones, 4 umbrales                   │
   la acústica no dispara NUNCA           evacuación · accesibilidad · circulación
   (1 de 85 pares en ejemplo.dxf)         acústica · sectorización · superficie
```

El experimento `experimentos/grafo/` **ya midió esto**: dos reglas portadas a una Graph API, 12 de 12 salidas
idénticas, de 9 a 5 dependencias en el módulo de reglas, y desaparecen las regex, `_normalize` y el `id()` como
identidad. Además encontró dos cosas que nadie buscaba: un **falso positivo real en producción** (VT6/2, baño sin
antesala apoyado en un contacto de 0,000 m de tramo enfrentado) y que **el umbral de 0,60 m propuesto no está
justificado** (VT3/3 tiene un tramo de 0,570 m que cambia el resultado). Es la mejor prueba disponible de que el
grafo es la inversión correcta *y* de que el criterio de contigüidad necesita datos reales antes de fijarse.

**Consecuencia para el motor normativo:** evacuación deja de ser "distancia entre centroides encadenados" y pasa a
ser un recorrido sobre aristas con procedencia. Cuando la arista es `supuesto`, el recorrido hereda `ESTIMATED`.
Hoy hereda certeza.

---

## 6. Geometría

**Principio:** la geometría es un valor referenciado, no un atributo embebido. `Espacio.geometrias` es un mapa
`representacion → geometria_id`, no un polígono.

```
Espacio(id=e-042, tipo=(dormitorio, observado))
   └─ geometrias:
        "huella_2d"  → g-118   Polígono, plano local de la planta
        "solido"     → g-903   Extrusión (cota_base, altura_libre)   [derivado]
        "malla"      → g-1204  Triangulación para el visor           [derivado, caché]
Muro(id=m-007)
   └─ geometrias:
        "eje"        → g-455   Polilínea + espesor
        "solido"     → g-456   [derivado]
```

Por qué esto y no un polígono dentro del objeto:

1. **El editor** mueve geometría sin tocar identidad ni semántica.
2. **El 3D** obtiene su representación del mismo elemento, no de una conversión (§13).
3. **El importador** puede aportar dos geometrías del mismo elemento (huella 2D del DXF, sólido del IFC) sin que
   una destruya la otra — que es exactamente el problema de la §11.
4. **La presentación** genera una representación más (`layout_svg`) marcada como *vista*, y así deja de
   contaminar el dato. Hoy no está marcada y sale por la API como `poligono`.

**Coordenadas y unidades, cerrado por contrato:**

- Un proyecto tiene **un sistema de coordenadas de proyecto** en metros. Punto.
- Cada planta tiene una `cota_base_m` y su geometría 2D vive en el plano de esa cota.
- Las instancias (vivienda tipo, núcleo, carpintería) llevan **transformación** (traslación + rotación + espejo),
  como el `INSERT` del DXF. Esto es el ensamblaje de §2.1.
- La escala se resuelve **en la frontera de entrada** y nunca después. `analyzer/escala.py` +
  `EscalaIndeterminada` ya hacen exactamente esto y son el precedente correcto: prefieren no responder a responder
  mal. Se conservan tal cual.
- Ninguna magnitud interna admite otra unidad. `area_m2` deja de ser una property que espera que alguien haya
  hecho lo correcto antes.

---

## 7. Evidencia y confianza

### 7.1 No hacen falta estados nuevos

Tu §3 preguntaba si `KNOWN` / `ESTIMATED` / `UNKNOWN` bastan, y si hacen falta *inferido, detectado
automáticamente, confirmado por usuario, contradictorio, ambiguo*.

**Respuesta: no hace falta ningún estado nuevo. Hacen falta dos ejes y una cardinalidad.**

El error sería meterlos todos en el mismo `enum`, porque no son el mismo tipo de cosa:

```
   EJE 1 — ESTADO (¿qué sé?)          EJE 2 — PROCEDENCIA (¿de dónde?)
   ────────────────────────           ─────────────────────────────────
   KNOWN                              observado    (leído del fichero)
   ESTIMATED                          declarado    (lo dijo el arquitecto)
   UNKNOWN      + motivo obligatorio  derivado     (composición pura)
   NO_APLICABLE                       supuesto     (hipótesis del sistema)
                                      desconocido
```

Los dos ejes **ya existen** en `hechos.py`: `estado` (los cuatro de arriba, validados en `__post_init__`) y
`tipo` + `fuente` + `procedencia` (el segundo eje, hoy menos formalizado). Y cada uno de tus candidatos cae en una
casilla existente:

| Candidato | Dónde cae | Comentario |
|---|---|---|
| inferido | `ESTIMATED` + `derivado`/`supuesto` | ya lo usa `planta.py` (`ORIGEN_CONVENCION_NOMBRE`, ESTIMATED/Media) |
| detectado automáticamente | `KNOWN`/`ESTIMATED` + `observado` | la distinción real no es el estado, es la confianza |
| confirmado por usuario | `KNOWN` + `declarado` | **más una fecha y un actor** — ver 7.3 |
| ambiguo | `UNKNOWN` + motivo `AMBIGUO` | `capas_candidatas` ya produce exactamente esto |
| contradictorio | **no es un estado: es cardinalidad ≥ 2** | §11 |

**Lo único que falta de verdad es lo último**, y es un cambio de forma, no de vocabulario: hoy un `Hecho` es
*monovaluado* — un valor, un estado, una fuente. No puede sostener cuatro medidas de la misma magnitud. Eso es la
§11 y es el hallazgo más accionable de esta sección.

### 7.2 Confianza: cualitativa, y no se multiplica

`hechos.py` fija Alta/Media/Baja y `ocupacion.py`/`sectorizacion.py` propagan con `_peor_confianza(...)` — el
mínimo, no un producto de probabilidades. **Es correcto y debe generalizarse tal cual.** Un porcentaje de
confianza en este dominio es precisión fabricada, la misma clase de deshonestidad que retiró
`TIPOLOGIA_BENCHMARKS` y que sostiene hoy el percentil de `scoring.py` (deuda ya identificada, fuera de alcance
aquí).

### 7.3 Tres campos que `Hecho` necesitará y hoy no tiene

Aditivos, no rompen nada:

- **`depende_de: tuple[str, ...]`** — ids de los hechos/nodos que consumió. Sin esto no hay recomputación
  selectiva y por tanto no hay editor (§12). Hoy la dependencia existe sólo como prosa en `explicacion`.
- **`version_modelo: str`** — a qué versión sellada del modelo se refiere. Sin esto un hecho cacheado no puede
  invalidarse.
- **`actor` y `fecha`** — quién lo afirmó y cuándo. Es lo que convierte "confirmado por el usuario" en un dato
  auditable en vez de un estado más.

---

## 8. Estados de conocimiento aplicados al modelo entero

Además del estado por *afirmación* (§7), el modelo necesita un estado por *tipo de nodo dentro de un ámbito* —
los cuatro estados de presencia de `KNOWLEDGE_GRAPH.md` §0.4:

| Presencia | Significado | Qué autoriza a concluir |
|---|---|---|
| **observado** | está en el origen y se ha leído | todo |
| **inferido** | se deduce de otra geometría, con confianza | nunca por encima de esa confianza |
| **no observable** | el origen es estructuralmente incapaz de contenerlo | **nada** — sólo Unknowns |
| **ausencia verificada** | podría contenerlo, se buscó, no está | **la única** que autoriza inferencia negativa |

Es la defensa contra el fallo que más asusta y que falla en la dirección tranquilizadora: *"no hay problema de
ventilación, no hay huecos que evaluar"*. Mapa honesto para un DXF de distribución como `ejemplo.dxf`:

```
 Proyecto  ██████████ observado        Planta    ░░░░░░░░░░ no observable (declarada)
 Espacio   ██████████ observado        Parcela   ░░░░░░░░░░ no observable (declarada)
 Unidad    ████████░░ observado/inferido  Hueco  ░░░░░░░░░░ no observable
 Edificio  ████░░░░░░ inferido (1/fichero) Pilar ░░░░░░░░░░ no observable (capa existe)
 Muro      ████░░░░░░ inferido (hueco 0,03–0,38 m)  Instalación ░░░░░░░░░░ no observable
```

**Cuatro de once tipos tienen datos.** Eso no es un argumento contra el modelo: es la razón de que los otros siete
deban existir *declarados y vacíos* en vez de no existir, para que nadie los rellene con valores plausibles.

---

## 9. Flujo de importación

### 9.1 La frontera, dicha en una frase

> El lector conoce el formato y no conoce la arquitectura. El reconocedor conoce la arquitectura y no conoce el
> formato. El motor normativo no conoce ninguno de los dos.

```
 DXF ─┐
 DWG ─┤  NIVEL 0        NIVEL 1              NIVEL 2            MODELO
 IFC ─┼─► LECTOR ──────► RECONOCEDOR ◄────── PERFIL DE      ──► ARQUITECTÓNICO
 PDF ─┤   (1 por        (único,              CONVENCIÓN         COMÚN
 …   ─┘    formato)      compartido)         (detectado y       (capas 1-3)
                                              confirmado)            │
           entidades      Hechos con                                 │
           neutras        estado + motivo                            ▼
           + punteros     + confianza                    normativa · generador · 3D
                                                         editor · documentación
   ┌──────────────────────────────────────────────────────────────────────────┐
   │ IFC entra por Nivel 0 y ATRAVIESA el Nivel 1 casi sin reconocimiento:    │
   │ ya trae muros, huecos, plantas y espacios semantizados. Ese es el punto  │
   │ de diseñar el Nivel 1 como opcional, no como paso obligatorio.           │
   └──────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Cómo se hace cumplir la frontera (no basta con dibujarla)

Con las mismas pruebas de frontera que el proyecto **ya tiene y ya funcionan**:
`tests/test_normativa_fronteras.py` verifica que `analyzer/` sólo consume `normativa/` por su superficie pública,
y `test_ingesta_fronteras.py` / `test_extraccion_fronteras.py` hacen lo propio. Se añaden dos simétricas:

1. Ningún módulo de `modelo/` importa `ezdxf`, `ifcopenshell` ni ningún lector.
2. Ningún módulo de `modelo/` tiene atributos cuyo nombre venga de un formato (`layer`, `block`, `handle`,
   `guid`). Hoy `parser.Room.layer` incumpliría esta prueba, y es la señal exacta de que `Room` no es un nodo del
   modelo sino un residuo del lector.

### 9.3 Lo que el importador **no** debe hacer

- No fabricar certeza: devuelve `Hecho` con estado, no geometría "buena". (Ya decidido el 2026-08-10.)
- No elegir en silencio entre dos convenciones plausibles: pregunta, como ya hacen `CapaIndeterminada` y
  `EscalaIndeterminada`.
- No inventar el ensamblaje. Si el fichero no lo trae (0 `INSERT`), el modelo tiene **plantas con presencia *no
  observable*** y lo dice; no coloca las viviendas por proximidad y sigue como si nada.

---

## 10. Flujo de generación

### 10.1 Qué genera hoy el generador, medido

`ai_generator.py` pide a Claude un JSON de `plantas[].viviendas[].habitaciones[]` con `{nombre, ancho, largo}` —
**rectángulos con nombre**. `place_rooms` los coloca en filas, `_clamp_room_proportions` los recorta, y cada
vivienda se traslada a su carril de 500 m. De ahí salen `Room`/`Unit` idénticos a los del DXF, "sin ningún camino
de código paralelo" (su docstring, y es una decisión acertada).

El precio de esa decisión: **el generador no puede producir nada que `Room` no sepa representar.** No hay muros,
ni huecos, ni núcleo, ni fachada, ni cotas, ni ensamblaje. Un edificio generado es una colección de habitaciones
rectangulares a 500 m unas de otras.

### 10.2 Qué debe generar para que el resultado sea REALMENTE analizable

Ordenado por lo que desbloquea, no por dificultad:

| Debe generar | Sin ello, no funciona |
|---|---|
| **Ensamblaje**: planta, cota, posición y rotación de cada unidad y del núcleo | ninguna regla de edificio, ninguna medianera real, ningún 3D honesto |
| **Muros** con eje, espesor y altura | superficie construida, edificabilidad, sectorización física, envolvente |
| **Huecos** con muro anfitrión, ancho, alto, antepecho y los dos espacios que conectan | iluminación (hoy proxy `ancho × 0,25`), ventilación, C12, adyacencia real |
| **Grafo de conexión explícito** (qué puerta comunica qué) | evacuación, accesibilidad, recorridos — hoy todo supuesto |
| **Núcleo** con escalera y ascensor y las plantas que sirve | CAP-6: origen de evacuación, salida de planta, C09/C10/C11 |
| **Cotas y alturas**: cota base por planta, altura libre, canto de forjado | altura de evacuación (hoy hipótesis), 3D, sección |
| **Envolvente**: fachadas con orientación y cubierta | compacidad, orientación, soleamiento (hoy proxy sobre el lado largo) |
| **Semántica declarada**, no rotulada | quitar el acoplamiento del prompt con las regex del evaluador |
| **Y su propia evidencia**: todo con procedencia `declarado-por-generador` | ver 10.3 |

### 10.3 La trampa que hay que evitar, y es seria

Un proyecto generado tendrá **más presencia observada** que uno importado de un DXF de distribución: huecos
declarados, alturas declaradas, conexiones declaradas. Eso significa que **dos proyectos del mismo sistema tendrán
grafos de riqueza distinta**, y por tanto:

> Una puntuación calculada sobre un proyecto generado **no es comparable** con una calculada sobre un DXF
> importado, y decir que lo es sería exactamente la misma deshonestidad que el percentil fabricado.

El modelo debe llevar el **mapa de presencia** (§8) en el proyecto y toda comparación debe consultarlo. Es
gratis hacerlo ahora y muy caro añadirlo después de haber publicado comparaciones.

---

## 11. Conflictos y datos incompletos

### 11.1 Tu caso: 80 / 82 / 79,6 / 81 m²

**Antes de resolver el conflicto hay que comprobar que existe.** Cuatro números distintos de "superficie" pueden
ser cuatro magnitudes distintas medidas correctamente:

- 80 m² del DXF puede ser superficie **útil** con el criterio de aquel despacho;
- 82 m² del PDF puede ser superficie **construida con parte proporcional de comunes**;
- 79,6 m² de la geometría es la suma de polígonos **con el solape descontado** (`superficie_util.py` ya lo mide);
- 81 m² del usuario puede ser lo que figura en la escritura.

**Primera regla: normalizar el criterio antes que el valor.** Si los criterios difieren, no hay conflicto: hay
cuatro magnitudes, y el sistema debe mostrar cuatro filas, no discutir cuál gana. Esto no es teoría —
`superficie_util.py` ya distingue `superficie_util_db_si` de `superficie_util_ocupable_db_si` y `app.py` documenta
por qué C01 consume una y CAP-3 la otra.

### 11.2 La forma de dato: `Magnitud` con N evidencias

```
Magnitud(nombre="superficie_util", ambito="vivienda VT01", criterio="DB-SI Anejo A")
  ├─ Evidencia(79.6 m², origen=observado,  método=suma de polígonos,   confianza=Media,
  │            puntero=dxf:capa "00 areas", fecha=2026-08-11)
  ├─ Evidencia(80.0 m², origen=observado,  método=cuadro del DXF,      confianza=Media,
  │            puntero=dxf:MTEXT #4471)
  ├─ Evidencia(82.0 m², origen=observado,  método=tabla del PDF p.3,   confianza=Alta,
  │            puntero=pdf:pág3/tabla1/fila7)   ⚠ criterio distinto: construida
  └─ Evidencia(81.0 m², origen=declarado,  actor=arquitecto,           confianza=Alta,
               fecha=2026-08-11)

  → publicado: Hecho(valor=81.0, estado=KNOWN, confianza=Media,
                     resolucion="declaración del arquitecto sobre medición",
                     discrepancia_max=2.4 m² (3,0 %))
  → y además:  Hallazgo("Discrepancia de superficie del 3,0 % entre cuatro fuentes")
```

Cuatro invariantes que hacen que esto no degenere:

1. **Nada se borra.** Las cuatro evidencias persisten en todas las versiones del modelo. El valor publicado es una
   *proyección*, no una sustitución.
2. **La resolución es explícita, nombrada y reversible.** Una política ("declarado > observado > derivado"), no un
   `if` dentro de una regla. El usuario puede cambiarla y se recalcula.
3. **La discrepancia es un dato del modelo**, y si supera una tolerancia se convierte en Hallazgo. Hoy una
   discrepancia del 3 % desaparecería sin dejar rastro.
4. **La confianza del valor publicado no puede ser mayor que la de la discrepancia.** Cuatro fuentes que no
   coinciden no dan más confianza que una: dan menos. Es la misma disciplina de `_peor_confianza`.

### 11.3 Y el caso feo que hay que decidir pronto

¿Qué pasa cuando el arquitecto declara 81 m² y la geometría dice 79,6? La tentación es **mover la geometría** para
que cuadre. No debe hacerse nunca automáticamente: la declaración no es geometría, y una geometría alterada para
cuadrar un número es un modelo que ya no representa el proyecto. La declaración gana en el *valor publicado*; la
geometría gana en el *modelo*; y la diferencia es visible. (Decisión abierta en §17.)

---

## 12. Flujo de edición

*"Mueve esta pared 40 cm"* y *"haz esta vivienda 5 m² más grande"* **no son la misma petición** y confundirlas es
el mayor riesgo de diseño de esta sección.

- La primera es una **operación**: destino determinado, resultado calculable.
- La segunda es un **objetivo**: hay infinitas soluciones, requiere decidir por dónde crecer, a costa de qué, y
  respetando qué. Eso no es un editor: es el generador trabajando con restricciones.

**Recomendación: v1 del editor implementa sólo operaciones, y enruta los objetivos al generador con una propuesta
que el arquitecto acepta o rechaza.** Fingir que el editor resuelve objetivos produce el peor resultado posible:
un sistema que mueve paredes por su cuenta y no sabe explicar por qué.

### 12.1 La arquitectura de datos que lo permite

```
  COMANDO                MODELO                     RECOMPUTACIÓN
  ───────                ──────                     ─────────────
  mover(m-007, 0.40 m)   v12 ──► v13 (sellada,      grafo de dependencias:
        │                        inmutable)          quién consumió qué
        ▼                          │                        │
  valida invariantes ──────────────┘                        ▼
  (§6 KNOWLEDGE_GRAPH)                        invalidar SOLO lo alcanzable
                                              desde m-007:
  ✗ NO edita coordenadas sueltas               superficie(VT01) ✗
  ✓ Edita entidades identificadas              ocupación(VT01)  ✗  (depende de superficie)
                                               sector(planta 2) ✗
                                               superficie(VT02) ✓ intacta
                                               altura evac.     ✓ intacta
```

Cinco requisitos, y **hoy no se cumple ninguno**:

| Requisito | Por qué | Estado hoy |
|---|---|---|
| **Identidad estable** | un comando referencia `m-007`, no "la tercera pared" | ❌ `Room` no tiene id; se usaba `id()` de Python |
| **Modelo persistido** | editar exige que el proyecto exista entre peticiones | ❌ el proyecto vive dentro del `try` de `/api/analizar` y muere con la respuesta |
| **Versiones inmutables** | deshacer, comparar, auditar | ❌ `storage.guardar_proyecto` guarda un informe, sin versión |
| **Dependencias declaradas** | recalcular lo justo, no todo | ❌ están en prosa, dentro de `explicacion` |
| **Invariantes verificables** | una edición no puede dejar un modelo inválido | ❌ no hay invariantes que comprobar |

Los dos primeros son **el cuello de botella de todo el producto que quieres**, no sólo del editor.

### 12.2 La decisión que condiciona el editor entero

¿La fuente de verdad geométrica es **el recinto** o **el muro**?

- Un DXF de distribución da **recintos** (polígonos de área). Mover un muro no significa nada: hay que mover los
  polígonos vecinos y confiar en que el hueco entre ellos siga siendo plausible.
- Un IFC da **muros**. Los recintos son la consecuencia.
- El generador puede producir cualquiera de los dos.

**Un editor honesto sólo es posible sobre un modelo muro-primero.** Recomendación: el modelo soporta ambos y
**declara cuál es el origen de verdad de cada proyecto**; el editor de geometría se habilita únicamente en
proyectos muro-primero, y en los demás ofrece edición semántica (renombrar, reclasificar, declarar) que sí es
segura. Es preferible a un editor que funciona a medias sin decir cuándo.

---

## 13. Flujo 3D

**Lo que no debe pasar, y es lo que pasa hoy.** `static/viewer-edificio.js` recibe polígonos 2D, agrupa por el
prefijo del nombre de la vivienda, cierra el hueco de 500 m de `UNIT_OFFSET_M`, calcula un AABB por vivienda,
inventa `WALL_THICKNESS = 0.15` y `SLAB_THICKNESS = 0.15`, y monta un edificio con ventanas sintéticas. Es un
trabajo bien hecho *y* es arquitectura generada en la capa de presentación, con constantes que ningún motor
normativo verá jamás. Y hay un segundo visor (`viewer-vivienda.js`) que extruye con `ROOM_HEIGHT_M = 2.5` y
`PASILLO_HEIGHT_M = 2.2`, valores propios, duplicando además la paleta de `plan_svg._ROOM_TYPES` "a propósito".

**Tres alturas de referencia distintas en el producto, ninguna en el modelo.**

Lo que el modelo común debe contener para que el 3D sea una **lectura** y no una reconstrucción:

| Dato | Para qué | Hoy |
|---|---|---|
| Cota base y altura libre por planta, canto de forjado | apilar plantas de verdad | ❌ constante en JS |
| Muros con eje, espesor, altura, y a qué espacios delimitan | volumen real | ❌ inventado en JS |
| Huecos con antepecho, dintel, ancho, y su muro | ventanas donde están, no donde tocan | ❌ sintéticas |
| Forjados y cubierta | envolvente cerrada | ❌ losa genérica |
| Ensamblaje (transformaciones) | el edificio existe en el backend | ❌ se recompone en el cliente |
| Norte y geolocalización | soleamiento, sombras, render creíble | ⚠️ norte declarado, sólo 2D |
| Asignación de material por elemento (referencia a catálogo) | render, mediciones, acústica, térmica | ❌ colores por tipo, en dos sitios |

Y una separación que conviene fijar ahora aunque el 3D tarde:

> **Escena ≠ modelo.** Cámaras, luces, mobiliario decorativo, materiales de render y prompts de IA viven en una
> capa *escena* que **referencia** el modelo y nunca lo modifica. Un render es una vista; jamás una fuente de
> verdad. El mobiliario que sí computa (sanitarios, cocina — que `ejemplo.dxf` sí trae, en `00 SANITARIOS2` y
> `00-INST`) es modelo, no escena. La frontera es: *si una regla puede consultarlo, es modelo*.

---

## 14. Flujo documental

### 14.1 Qué es fuente de verdad y qué es derivado

| Fuente de verdad (se persiste, se edita, se versiona) | Derivado (se recalcula, nunca se edita) |
|---|---|
| Geometría tal como fue autorada o importada | Todas las superficies (útil, construida, ocupable, computable) |
| Declaraciones del arquitecto (tipología, ciudad, norte, planta, altura de evacuación) | Ocupación, altura de evacuación estimada, límites de sector |
| Semántica resuelta (tipo, pertenencia) con su origen | Adyacencias, conexiones, recorridos |
| Evidencias (las N de §11), incluidas las descartadas | Planos, SVG, layouts, vistas 3D, mallas |
| Referencias externas: `concept_id` normativo, municipio INE, catastro | Comprobaciones normativas, hallazgos, puntuación |
| Perfil de convención del despacho | Mediciones y presupuesto |
| Decisiones del usuario (resoluciones de conflicto, confirmaciones) | Memoria e informes |

**Regla operativa (P7):** un derivado sólo se persiste como caché, y siempre con `version_modelo`. Si la versión
no coincide, se recalcula o se muestra como caducado — nunca se sirve como si fuera actual.

### 14.2 La inversión que hay hoy, y es el hallazgo estructural más grave

```
   HOY                                    DEBE SER

   DXF ──► análisis ──► informe JSON      DXF ──► MODELO (persistido, versionado)
                            │                        │
                            ▼                        ├──► análisis  ──► informe (derivado)
                     ┌──────────────┐                ├──► 3D        ──► vista   (derivado)
                     │  storage.py  │                ├──► planos    ──► SVG/PDF (derivado)
                     │  payload TEXT│                └──► mediciones──► tablas  (derivado)
                     └──────────────┘                        │
                            │                                ▼
                     el "proyecto" es                 ┌──────────────┐
                     un informe de 288 KB             │  storage.py  │
                                                      │ modelo+vers. │
                     ✗ no se puede editar             └──────────────┘
                     ✗ no se puede recalcular
                     ✗ no se puede comparar
```

`storage.py` guarda `payload TEXT NOT NULL` con el resultado completo de `serialize_analysis`, más columnas
denormalizadas (`puntuacion`, `valoracion`, `num_viviendas`) y una `miniatura` que es el SVG de la primera
vivienda. Es un módulo bien hecho, con validación de ids y `SCHEMA_VERSION` — pero **lo que guarda es la
conclusión, no el proyecto**. Cambiar el umbral de una regla mañana no puede recalcular ningún proyecto guardado:
habría que volver a subir el DXF.

**Esto, y no la falta de un grafo, es lo que bloquea el editor, el 3D honesto, la documentación y el histórico.**

---

## 15. Compatibilidad con la arquitectura actual

Nada de lo que sigue propone tirar código. El mapa completo, con veredicto por pieza:

### 15.1 NO TOCAR — son el modelo bien hecho, sólo cambia de dónde vienen sus insumos

| Pieza | Por qué |
|---|---|
| `analyzer/hechos.py` | **Es el núcleo del futuro modelo, ya escrito.** Estado inseparable del valor, motivo obligatorio, confianza cualitativa, `referencia_normativa` como `concept_id`. Sólo crecerá con los tres campos de §7.3 |
| `uso_previsto.py`, `planta.py`, `ocupacion.py`, `sectorizacion.py`, `altura_evacuacion.py`, `avisos_altura_evacuacion.py`, `superficie_util.py` | CAP-1…CAP-5. Funciones puras que reciben hechos y devuelven hechos, sin parseo de texto dentro y con las fuentes cerradas por la firma. Migrar el sustrato **no les cambia una línea**: hoy reciben `Unit`, mañana reciben una vista del modelo |
| `analyzer/escala.py` | La frontera de unidades ya resuelta, con `EscalaIndeterminada` que prefiere preguntar |
| `normativa/`, `extraccion/`, `ingesta/` (B1) | Tienen frontera propia y pruebas que la verifican. El modelo común no las toca |
| Los tests de CAP-1…CAP-5 y de fronteras | Son la red de seguridad de todo lo demás |

### 15.2 ADAPTAR — cambian de sustrato, conservan su lógica

| Pieza | Cambio | Riesgo |
|---|---|---|
| `circulation.py` + `adyacencia.py` | **Primer consumidor del grafo.** Ya es un grafo con su criterio propio; sustituirlo por el compartido está medido: 12/12 equivalencia, 30→24 y 14→13 líneas | Bajo — y hay que asumir que **desaparece un falso positivo real** (VT6/2) y que el umbral de contigüidad no está justificado |
| `spatial_quality.py` | Consume `UnitScore` y geometría; pasa a consumir el modelo | Bajo, se ve en pantalla |
| `plan_svg.py` | **Separar `_layout_rooms`/`_grid_layout` (presentación) de la geometría del modelo.** El layout deja de salir por la API como `poligono` | Medio: el visor 3D depende hoy de esa geometría re-colocada |
| `chain_effects.py` | Consume `UnitScore`; sin cambios de lógica | Bajo |
| `app.py` | Las ~280 líneas de orquestación dentro de `/api/analizar` salen a un caso de uso "analizar proyecto" que recibe un modelo. El endpoint queda en HTTP | Medio, pero es refactor mecánico |
| `parser.py` | **Se parte en dos** (§9): lector DXF (Nivel 0) y reconocedor (Nivel 1). Se conservan `_recorrer_plano` —que ya sabe descender por `INSERT` con `virtual_entities()`—, `capas_candidatas`, `elegir_capa` y todo `escala.py` | Medio |

### 15.3 ENCAPSULAR — no se reescriben, se aíslan detrás de un adaptador

| Pieza | Estrategia |
|---|---|
| **`evaluator.py` (145 KB, ~3.000 líneas, ~40 reglas)** | **No se reescribe. No se migra de golpe.** Se construye el modelo **al lado** y un adaptador `modelo → List[Unit]` para que las 40 reglas sigan funcionando sin tocarse. Después, regla a regla, empezando por las que dependen de topología (acústica, ancho de pasillo, evacuación, itinerario accesible) — que son las únicas que el grafo mejora de verdad. Las de superficie pura no ganan nada migrando y pueden esperar años |
| `evaluator.Unit` / `parser.Room` | Se degradan a **vista de compatibilidad** generada desde el modelo. Dejan de ser el modelo sin dejar de existir |
| `api_serializer.py` | Se parte en dos serializadores: **modelo** y **resultados**. Hoy mezcla ambos y además publica geometría de presentación |

### 15.4 SUSTITUIR EVENTUALMENTE — no ahora, pero el destino está claro

| Pieza | Sustitución | Cuándo |
|---|---|---|
| `storage.py` (esquema) | Tablas `proyecto` / `version_modelo` / `evidencia` + el informe como derivado con `version_modelo`. Se conserva el módulo, su validación de ids y su `SCHEMA_VERSION` | Etapa E2 — es el desbloqueo principal |
| `ai_generator.py` (contrato de salida) | Emite modelo (§10.2), no rectángulos con nombre. Se conserva su acierto: generado y analizado por el mismo pipeline | Cuando el modelo soporte muros y huecos |
| `viewer-edificio.js` | La reconstrucción arquitectónica baja al backend; el visor pasa a leer | Etapa E4 |
| `UNIT_OFFSET_M = 500.0` | Desaparece con el ensamblaje real | Etapa E3 |

### 15.5 PROMOCIONAR

| Pieza | Qué hacer |
|---|---|
| `experimentos/grafo/` (`modelo.py`, `api.py`, `constructor.py`) | **Es la semilla del futuro `modelo/`.** 993 líneas que ya aplican §0.1 (nada evaluativo), §0.3 (`Valor(valor, origen)`), §0.4 (presencia) y una Graph API validada. Promocionarlo es más barato y mucho menos arriesgado que empezar de cero — pero hay que **unificar su vocabulario con `hechos.py`** antes (hoy `Valor.origen` y `Hecho.estado` son dos ejes distintos que nadie ha cruzado) |

### 15.6 FUERA DE ALCANCE

`scoring.py` (percentil fabricado, dos sistemas de puntuación en conflicto — deuda ya documentada en
`docs/design/2026-08-02-dos-sistemas-de-puntuacion.md` y marcada con un test deliberadamente en rojo),
`pdf_report.py` (formatea el JSON, no recalcula: sigue funcionando), `ai_analyst.py`.

---

## 16. Problemas de arquitectura detectados

Sin suavizar. Los cinco primeros son bloqueantes para tu visión; el resto es deuda que empeora con el tiempo.

**16.1 — No hay modelo de proyecto. Hay un pipeline de análisis.** El "proyecto" existe dentro del `try` de
`/api/analizar` como `List[Room]` + `List[Unit]` y muere con la respuesta HTTP. Lo que se persiste es el informe.
**Editor, 3D honesto, documentación, histórico y recálculo son todos imposibles hasta que esto cambie**, y ninguno
es más fácil que otro: los cuatro dependen de lo mismo.

**16.2 — No hay identidad.** `Room` no tiene id. `circulation.py` usaba `id()` de Python como identidad de
habitación (el experimento lo señala como una de las cosas que desaparecen con el grafo). Sin identidad estable no
hay comando de edición, ni ciclo de vida de hallazgos, ni comparación entre versiones. `OBSERVATION_MODEL.md`
construyó toda la estabilidad de los hallazgos sobre una identidad de ámbito que no existe.

**16.3 — ArchMuse no puede representar un edificio.** Puede representar **una planta suelta de viviendas**. No hay
entidad `Planta` (CAP-4 publica el *hecho* planta, un valor declarado por análisis, replicado por vivienda), no
hay colección de plantas, no hay cotas. `/api/analizar` analiza una sola planta por análisis y lo documenta como
decisión de v1. Todo lo que pides —edificio, núcleos, evacuación vertical, 3D apilado— empieza aquí.

**16.4 — La geometría publicada es geometría de presentación.** `api_serializer._serialize_room` publica en
`poligono` el polígono **ya re-colocado por el layout del SVG**, y el comentario lo dice sin rodeos: *"mismo layout
(real/compactado/cuadrícula) que el plano SVG — lo consume el visor 3D para extrudir la habitación sin tener que
recalcular su disposición"*. Cuando el layout entra en modo cuadrícula, la posición original del DXF se ignora
por completo. **El 3D está extruyendo un diagrama.**

**16.5 — El ensamblaje se hace tres veces, en tres capas, con tres criterios** (§2.1), y ninguna de las tres es
autoritativa. `UNIT_OFFSET_M = 500.0` es el síntoma más visible: una constante que existe para engañar a las
reglas de orientación y que el visor JS tiene que deshacer.

**16.6 — Tres modelos de incertidumbre coexistiendo sin conocerse.**

| Modelo | Dónde | Forma |
|---|---|---|
| `Hecho` | CAP-1…CAP-5 | estado + motivo + confianza + procedencia. **Correcto** |
| `*Result` (≈40 dataclasses) | `evaluator.py` | `passed: bool` + floats desnudos. **Es el patrón que `hechos.py` existe para corregir** |
| `Valor(valor, origen)` | `experimentos/grafo/modelo.py` | un tercer vocabulario, con orígenes que no son los estados de `hechos.py` |

Los dos ejes deben cruzarse una vez (§7.1) y el tercero debe desaparecer al promocionar el experimento. Mientras
tanto, cada regla nueva elige, y elige mal la mitad de las veces porque `evaluator.py` es el fichero más grande.

**16.7 — `evaluator.py` acopla cinco responsabilidades.** Modelo (`Unit`), ~40 reglas, clasificación de problemas
(`classify_problems`, 376 líneas), umbrales de puntuación y helpers de geometría. Consecuencia medible:
`ai_generator.py` importa `Unit` **y `_normalize`, un privado del evaluador**, para poder generar; `pdf_report.py`
importa sus umbrales de color. Cualquier consumidor nuevo arrastra el evaluador entero.

**16.8 — La semántica depende de que el texto esté bien escrito.** Regex sobre rótulos en `evaluator.py`
(`DORMITORIO\s*1\b`), en `superficie_util.clasificar_recinto`, en `plan_svg.room_type`, y un `SYSTEM_PROMPT` que
obliga al LLM a escribir los nombres exactos. El patrón `VT\s*\d+` para identificar viviendas es la convención de
rotulado de un despacho concreto, elevada a constante de producción.

**16.9 — Superficie construida es estructuralmente imposible hoy** y con ella toda la rama urbanística
(edificabilidad, ocupación de solar, retranqueos trabajan sobre proxies). Sin muros no hay envolvente, y sin
envolvente `evaluate_building_compactness` y `evaluate_orientation` miden el lado largo de un polígono de recinto.

**16.10 — El diseño crece más rápido que el código.** ≈1,4 MB de documentos de arquitectura
(`docs/brain/` + raíz), de los cuales `KNOWLEDGE_GRAPH.md` ya resolvía cinco de las trece preguntas de este
encargo hace seis días, `PRD-001-Core-Reasoning-Engine.md` sigue sin aprobar, y la única materialización
existente son 993 líneas en `experimentos/`. **Este documento es la última pieza de diseño que deberías encargar
sobre el modelo antes de materializar algo.** Si dentro de un mes hay un documento más y ningún módulo `modelo/`,
el problema no será la arquitectura.

**16.11 — La unidad de medida no está en el tipo** (P4): `Room.area_m2` es correcto sólo si la `Room` vino de
`leer_plano`, y el propio docstring explica que es una convención, no una garantía. Es un bug latente que ya
costó una vez (un DXF en milímetros pasaba todas las superficies mínimas con nota alta).

**16.12 — El grafo no desbloquea muros ni huecos**, y conviene no vendérselo a nadie así. El cuello de botella es
el origen de datos. Lo que el modelo común desbloquea es: una sola definición de topología, identidad estable,
proyecto persistido, ensamblaje único y "no lo sé" como valor decible. Es mucho, y es indirecto.

---

## 17. Decisiones que NO debemos cerrar todavía

Cada una necesita datos que hoy no tenemos. Cerrarlas ahora es la forma más cara de equivocarse.

1. **Recinto-primero o muro-primero como fuente de verdad geométrica** (§12.2). Depende de qué traigan los 5–8
   proyectos reales. El modelo debe soportar ambos y declararlo por proyecto.
2. **El umbral de contigüidad.** El experimento demostró que el 0,60 m propuesto no está justificado: un tramo de
   0,570 m en VT3/3 cambia el resultado de la regla. **Elegirlo con un solo plano sería inventarlo.**
3. **Si la Planta es una entidad o un ámbito declarado.** Depende de si los proyectos reales entregan una planta
   por fichero, todas en una, o montadas por XREF.
4. **El alcance del `concept_id` entre versiones.** El emparejamiento por solapamiento geométrico está propuesto,
   no demostrado; habitaciones fusionadas o partidas son genuinamente ambiguas. Necesita dos versiones reales del
   mismo plano.
5. **Si el modelo es event-sourced o versionado por instantáneas.** Ambos sirven para el editor; el coste es muy
   distinto y no hay volumetría real todavía.
6. **La política de resolución de conflictos por defecto** (§11.2). Se decide cuando existan cuatro fuentes
   reales, no antes.
7. **DWG: conversión en servidor u obligación de exportar DXF.** Es licencia y operaciones, no arquitectura.
8. **Cuándo se construye el lector IFC.** El modelo debe estar listo para él; el lector no debe escribirse hasta
   que un cliente entregue IFC.
9. **Si un modelo generado y uno importado son comparables** (§10.3). Sospecho que no. Hasta decidirlo, no
   publicar comparaciones entre ellos.
10. **Dónde vive el código** (`modelo/`, no `brain/`: `docs/brain/` ya significa otra cosa). Decisión menor, pero
    mejor tomada antes que después.

---

## 18. Plan de implementación por etapas

Ordenado por **desbloqueo**, no por dificultad. Lo importante: **E0, E1 y E2 no dependen de los proyectos reales**
— y son precisamente lo que hace que la muestra sirva de algo cuando llegue.

```
  E0 ──► E1 ──► E2 ──►┌─ E3 (ensamblaje/multiplanta) ─┐
  red    modelo  persis│                              ├──► E5 (editor + generador
  segur. al lado tencia└─ E4 (muros/huecos) ──────────┘         que escribe modelo)
   │       │       │                │
   │       │       │                └── depende de los 5-8 proyectos reales
   │       │       └── DESBLOQUEA: editor, 3D honesto, documentación, histórico
   │       └── DESBLOQUEA: una sola topología, identidad estable
   └── sin esto, cualquier cambio en el evaluador es indistinguible de una regresión
```

**E0 — Red de seguridad y proceso.** *No depende de nada.*
Golden tests que congelan la salida actual de `ejemplo.dxf` regla a regla (ya hay precedente en el repo), y el PRD
del modelo común, que `CLAUDE.md` exige antes de cualquier capacidad nueva y que debe resolver dos cosas que este
documento no resuelve: **el coste de migración** y **la relación con `PRD-001`** (el modelo no es un frente
paralelo al motor de razonamiento: es su capa de ámbito, y debería ser su primera fase, no un PRD que compita por
el mismo tiempo).

**E1 — `modelo/` mínimo, construido al lado.** *No depende de la muestra.*
Proyecto / Planta / Unidad / Espacio, identidad en dos niveles, presencia, Graph API. Poblado desde `leer_plano`.
Adaptador `modelo → List[Unit]` para que `evaluator.py` no se entere de nada. **Primer y único consumidor:
`circulation.py`**, que ya está medido a 12/12. Promocionar `experimentos/grafo/` unificando su vocabulario con
`hechos.py`. Criterio de éxito: la salida de `/api/analizar` no cambia, salvo el falso positivo de VT6/2, que
debe desaparecer *y explicarse*.

**E2 — El proyecto empieza a existir.** *No depende de la muestra. Es el desbloqueo principal.*
Persistir modelo + versión; el informe pasa a ser un derivado con `version_modelo`. `storage.py` gana tablas, no
se reescribe. A partir de aquí un proyecto se puede reabrir, recalcular y comparar — y todo lo demás deja de estar
bloqueado.

**E3 — Ensamblaje y multiplanta.** *Depende de la muestra.*
Edificio → Plantas (con cota) → Unidades con posición real. Muere `UNIT_OFFSET_M`. Desbloquea CAP-6 **sólo si**
los proyectos reales traen el ensamblaje; si ninguno lo trae, la respuesta correcta es que las plantas queden con
presencia *no observable* y se declaren, no inventarlas.

**E4 — Muros y huecos.** *Depende de la muestra.*
Sólo cuando los 5–8 proyectos digan si son reconocibles de forma general o sólo en la convención de un despacho.
Desbloquea superficie construida, envolvente, iluminación real, C12 y el 3D honesto. **Es la etapa con más riesgo
de todo el plan** y la que la PoC identificó como "el trabajo real": pasar de líneas sueltas en `00 MURO` a un
muro con dos caras y un espesor es reconocimiento geométrico, no lectura de fichero.

**E5 — Edición y generación sobre el modelo.** Comandos tipados, invalidación por alcanzabilidad, generador que
emite modelo en vez de rectángulos. El editor de geometría, sólo en proyectos muro-primero (§12.2).

### 18.1 El primer paso concreto cuando lleguen los proyectos reales

**No es escribir el importador.** Es medir la muestra contra las siete convenciones de
`2026-08-10-importacion-de-proyectos.md` §1.4 y contestar cuatro preguntas que sólo los datos pueden contestar:

1. ¿Recinto-primero o muro-primero? (decide §12.2, y con ella el editor)
2. ¿Viene el ensamblaje en el fichero? (decide si E3 es lectura o declaración)
3. ¿Qué umbral de contigüidad resiste tres despachos distintos? (decide §17.2)
4. ¿Hay una verdad de referencia (cuadro de superficies) contra la que medir el error? (decide si podemos afirmar
   algo sobre precisión)

Y si para entonces E1 y E2 están hechos, esa medición se hace **contra un modelo**, con hechos y evidencias, en
vez de contra un montón de polígonos. Ésa es toda la diferencia.

---

## 19. Riesgos

1. **El modelo se convierte en el nuevo cajón de sastre.** El riesgo más probable con diferencia: alguien necesita
   `orientacion` en un espacio una tarde con plazo, y en un año hay veinte campos evaluativos sin evidencia. La
   defensa no es estructural, es gobierno sostenido — y una prueba que falle si aparece un campo evaluativo.
2. **Migración big-bang de `evaluator.py`.** Es la ejecución más peligrosa posible: sigue devolviendo números, y
   son otros. Por eso E1 construye al lado y con adaptador.
3. **La topología única cambia resultados el día uno.** La acústica, que hoy no dispara nunca (1 de 85 pares),
   empezará a disparar. No es una regresión: es una regla que llevaba meses sin funcionar. Pero si aparece sin
   avisar, se leerá como tal.
4. **Coste sin usuario visible.** Ningún arquitecto pagará más porque ArchMuse tenga un modelo común. Todo el
   valor es indirecto y hay que defenderlo como inversión, no disfrazarlo de funcionalidad. La excepción honesta
   es E2: "puedo reabrir mi proyecto y recalcularlo" **sí** es visible.
5. **Diseñar el modelo sobre un solo fichero.** `ejemplo.dxf` es un despacho, una convención y cero `INSERT`.
   Todo lo que este documento afirma sobre presencia y observabilidad puede cambiar con el primer proyecto ajeno.
6. **Que E3/E4 se adelanten a la muestra.** Es la forma más cara de equivocarse: construir reconocimiento de muros
   para una convención que resulta ser minoritaria.
7. **Que este documento se convierta en el trabajo** (§16.10). El diseño ya está por delante del código; añadir
   más diseño antes de materializar E1 empeora activamente el problema.

---

**Estado:** documento de diseño. Sin código, sin implementación aprobada, sin commits. Extiende
`docs/brain/KNOWLEDGE_GRAPH.md` (que sigue siendo la referencia del catálogo de nodos, identidad, aristas e
invariantes) al producto completo. **No autoriza escribir código:** la regla de `CLAUDE.md` exige un PRD aprobado
antes, y ésta es la capacidad más transversal propuesta hasta ahora.
