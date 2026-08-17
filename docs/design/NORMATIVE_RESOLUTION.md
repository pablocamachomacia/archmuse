# NORMATIVE_RESOLUTION.md — Resolución territorial de normativa aplicable

**Fecha:** 2026-08-06 · **Estado:** diseño, sin implementar · **Ninguna línea de código escrita ni modificada.**

**La pregunta que responde este documento:** dado que el arquitecto solo declara *país / comunidad / provincia / municipio / tipo de proyecto / uso / tipología*, ¿cómo determina el sistema **todo** el conjunto de normativa aplicable, y cómo lo hace de forma que añadir el municipio 8.001 no toque una sola línea de código?

---

## 0. Frontera con lo que ya está diseñado

Tres documentos previos cubren partes de este encargo. Repetirlos sería peor que no escribir nada.

| Documento | Qué resuelve ya | Este documento lo reutiliza |
|---|---|---|
| `docs/brain/CONSTRAINT_MODEL.md` | Cómo se **evalúa** una restricción: 5 patrones cerrados, comparadores cerrados, tablas de parámetros multi-eje con repliegue | Íntegro, **sin ampliar** |
| `docs/design/NORMATIVE_ENGINE.md` | Ciclo de vida de la norma: `NormaFuente`/`ReglaNormativa`, bitemporalidad, `concept_id`/`instance_id`, grafo tipado de referencias, git como fuente de verdad, gobernanza | Íntegro |
| `docs/design/TRACEABILITY.md` | La traza inmutable de un resultado emitido | Íntegro (§12.4) |

**Lo que ninguno resuelve y es lo que este documento aporta:**

1. **El ámbito territorial como estructura de datos**, no como campo. `NORMATIVE_ENGINE.md` §3.3 lo declara "derivado del ámbito territorial" pero no define ese ámbito ni cómo se resuelve desde lo que el usuario escribe (§2, §3).
2. **El motor de herencia.** `NORMATIVE_ENGINE.md` §10.1 da un algoritmo de 6 pasos en pseudocódigo; no dice cómo se compone un umbral estatal con uno autonómico ni qué pasa por defecto (§7).
3. **El perfil de proyecto** (tipo × uso × tipología) como segundo eje de filtrado, independiente del territorial (§4).
4. **La escala.** `NORMATIVE_ENGINE.md` está deliberadamente acotado a 4 ciudades y advierte que cada una es un coste permanente. Este documento diseña para 8.131 municipios sin contradecir esa advertencia — porque separa **capacidad estructural** de **compromiso de contenido** (§13).
5. **Loader, Resolver y API interna** como componentes concretos con contrato (§6, §8, §11).
6. **Cobertura declarada** como dato de primera clase, no como ausencia inferida (§10).

**Regla de frontera de todo el documento:** este subsistema decide *qué reglas aplican*. No decide si se cumplen. `evaluator.py` y el futuro Intérprete de Constraints deciden si se cumplen, y **nunca preguntan por el municipio**.

---

## 1. Auditoría del estado actual (medido, 2026-08-06)

### 1.1 Qué hay hoy

| Elemento | Estado real | Fichero |
|---|---|---|
| Contexto geográfico que se pide | **Un campo de texto libre, "Ciudad"** | `static/app.js:501`, `app.py:154` |
| Ciudades reconocidas | **30**, tabla cerrada | `analyzer/cte_zonas.py:12` |
| Ejes de contexto que usa alguna regla | **2**: tipología y zona climática | `evaluator.py:783`, `:959` |
| Reglas con eje de comunidad autónoma | **0** | — |
| Reglas con eje de municipio | **0** | — |
| Umbrales escalares sin ningún eje | **41** | `docs/audits/NORMATIVE_AUDIT.md` §5.2 |
| Reglas con referencia a artículo | **0** | `NORMATIVE_AUDIT.md` §6.1 |
| Corpus normativo externo al código | **No existe** | — |

Dos cosas que la auditoría de ayer daba por pendientes y hoy ya no lo están, verificadas en código:

- **El Bug #1 está corregido.** `app.py:158-186` sí pasa `tipologia` y `zona_cte` a `evaluate_advanced()` y a `serialize_analysis()`. La nota de `TECH_REVIEW.md` sobre este punto está obsoleta.
- El repositorio tiene `tests/` con seis suites y `git status` limpio salvo trabajo en curso.

### 1.2 El hallazgo que obliga a actuar

Hay **una regla normativa autonómica viviendo en el frontend**:

```javascript
// static/app.js:120-140
var SUPERFICIE_MIN_CCAA = {
  "Comunidad de Madrid": 40, "Cataluña": 36, "Comunidad Valenciana": 30, ...
};
// app.js:1919-1932 — toolNormativaHtml()
var cumple = v.superficie_total_m2 >= minimo;   // ← emite "cumple" / "no cumple"
```

Su propio comentario declara el origen: *"cifras orientativas recopiladas de fuentes secundarias (prensa/portales inmobiliarios que resumen los decretos), no verificadas contra el texto íntegro de cada decreto"*.

Esto es, simultáneamente:

1. **Un juicio de cumplimiento legal emitido desde el navegador**, sin traza, sin cita y sin evidencia.
2. **Una contradicción con el backend.** `evaluator.py:783` fija la superficie mínima por **tipología** (30/40/24 m²); `app.js` la fija por **comunidad autónoma** (40/36/30…). Para una vivienda plurifamiliar en Madrid, el backend exige 30 m² y el frontend 40 m². **Las dos cifras se muestran en la misma pantalla.**
3. **El anti-patrón exacto** que el encargo pide erradicar: un diccionario grande de territorios incrustado en el código, mezclado con la lógica de presentación.
4. Materia **autonómica** evaluada, en el backend, con un eje que no es el competente — el problema M1 de `NORMATIVE_AUDIT.md`, del que esto es la otra mitad.

Esta es la justificación no teórica del subsistema: no se trata de prepararse para 8.000 municipios, sino de que **el producto hoy da dos respuestas distintas a la misma pregunta legal en la misma pantalla**.

### 1.3 Qué se modifica y qué permanece intacto

| Zona | Decisión | Motivo |
|---|---|---|
| `analyzer/evaluator.py` (3.272 líneas) | **Intacto en Fases 0-2.** Fase 3 migra **una** regla | Es el activo con más valor validado del repositorio (`MOAT_ANALYSIS.md`); tocarlo en bloque es el mayor riesgo posible |
| `analyzer/parser.py`, `escala.py`, `plan_svg.py`, `circulation.py`, `spatial_quality.py` | **Intactos.** No tienen nada normativo | Producen geometría y heurística de diseño, no juicio legal |
| `analyzer/cte_zonas.py` | **Absorbido** como dato del registro geográfico; la función pública se mantiene como fachada | Es hoy la única fuente de verdad ciudad→zona; duplicarla sería el error que el encargo prohíbe |
| `app.py` | **Un punto de sutura**: construir el contexto territorial y pasarlo | Ya es donde se resuelve hoy zona y densidad |
| `static/app.js` `SUPERFICIE_MIN_CCAA` | **Se elimina.** Sustituido por dato servido por la API | §1.2 |
| `analyzer/scoring.py`, `chain_effects.py` | Intactos | No consultan normativa |
| Paquete nuevo `normativa/` | Todo el subsistema vive aquí | Aislamiento: se puede borrar entero sin romper el análisis |

---

## 2. Arquitectura: siete capas desacopladas

Las capas se comunican **solo hacia abajo** y con estructuras de datos, nunca con llamadas de vuelta.

```
┌────────────────────────────────────────────────────────────────┐
│ 7 · EXPLICACIÓN        por qué aplica / por qué no aplica       │
├────────────────────────────────────────────────────────────────┤
│ 6 · EJECUCIÓN          Intérprete de Constraints  (evaluator)   │  ← no conoce municipios
├────────────────────────────────────────────────────────────────┤
│ 5 · COMPOSICIÓN        motor de herencia + prioridades          │
├────────────────────────────────────────────────────────────────┤
│ 4 · RESOLUCIÓN         qué reglas aplican a este proyecto       │
├────────────────────────────────────────────────────────────────┤
│ 3 · ÍNDICE             corpus cargado, validado e indexado      │
├────────────────────────────────────────────────────────────────┤
│ 2 · CARGA              loader + validadores (fail-closed)       │
├────────────────────────────────────────────────────────────────┤
│ 1 · DATOS              corpus en ficheros + registro geográfico │  ← lo único que crece
└────────────────────────────────────────────────────────────────┘
```

**La propiedad que hace que esto escale** es que el crecimiento territorial ocurre **solo en la capa 1**. Las capas 2-7 tienen tamaño constante: no crecen con el número de municipios, comunidades ni países. Un municipio nuevo es un directorio nuevo en la capa 1 y una fila en el registro geográfico —  que ya está completo desde el día uno (§3.2).

**Las tres fronteras que no se pueden cruzar nunca:**

| Frontera | Enunciado | Qué la rompe |
|---|---|---|
| **F1** | La capa 6 no conoce territorio | Un `if comunidad ==` dentro de una regla |
| **F2** | La capa 1 no contiene lógica | Un `.py` dentro de `normativa/es/` |
| **F3** | La capa 5 no inventa jerarquía | Resolver un conflicto con "gana el más restrictivo" |

F3 es la menos obvia y la más importante: se justifica en §7.3.

---

## 3. El ámbito territorial

### 3.1 Identidad: código, no nombre

Un municipio se identifica por su **código INE**, nunca por su nombre.

| | Nombre | Código INE |
|---|---|---|
| Estable en el tiempo | No — se cambian, se traducen, se fusionan | Sí |
| Único | No — 11 municipios "Villanueva de…" | Sí |
| Ordenable/jerárquico | No | Sí: `28115` contiene la provincia `28` |
| Escribible por un usuario | Sí | No |

Decisión: **el código es la identidad, el nombre es una etiqueta con alias.** Lo que el usuario escribe se resuelve contra un índice de alias (con y sin tildes, con y sin artículo, nombre cooficial: *A Coruña / La Coruña / Coruña*).

El identificador de ámbito es una ruta jerárquica de códigos:

```
es                    España
es.13                 Comunidad de Madrid          (código INE de CCAA)
es.13.28              Provincia de Madrid
es.13.28.28115        Pozuelo de Alarcón
```

Un ámbito **supra**municipal que no es un nivel administrativo (área metropolitana, mancomunidad, comarca) se modela como ámbito con lista explícita de miembros, no como nivel de la ruta:

```
es.09.amb              Àrea Metropolitana de Barcelona → [08019, 08073, ...]
```

Esto evita el error clásico de forzar cinco niveles fijos: **la profundidad de la cadena es variable y la determina el dato, no el esquema.** Portugal tendrá cuatro niveles; Francia, otros. Nada en las capas 2-7 asume un número de niveles.

### 3.2 El registro geográfico se completa el primer día

**Decisión estructural:** el registro con los 8.131 municipios, 50 provincias y 17+2 comunidades se incorpora **completo desde la Fase 0**, aunque el corpus normativo cubra cero municipios.

Motivo: es lo único que hace literalmente cierta la promesa *"añadir un municipio no requiere tocar código"*. Si el registro se poblara a demanda, añadir Pozuelo exigiría añadir su fila — y esa fila estaría, inevitablemente, en algún sitio del código o en un fichero mantenido a mano con criterio ad hoc.

Es barato y acotado: el fichero completo del INE ocupa del orden de 400 KB, tiene licencia de reutilización y cambia unas pocas veces al año (fusiones, segregaciones, cambios de denominación). Se versiona como cualquier otro dato del corpus, con su fecha de vigencia — un municipio fusionado en 2019 debe seguir existiendo para analizar un proyecto de 2018.

**Consecuencia deliberada y sana:** el sistema conoce los 8.131 municipios y tiene corpus para unos pocos. Esa asimetría es visible y honesta (§10), en lugar de que "no conozco ese municipio" y "no tengo su normativa" se confundan en el mismo silencio.

### 3.3 Ámbitos sectoriales: superpuestos, no heredados

Este es el punto donde un diseño ingenuo se rompe a los seis meses.

Patrimonio, protección civil, zona inundable, servidumbre aeroportuaria, costas, vía pecuaria — **no son niveles territoriales**. No cuelgan del municipio: lo atraviesan. Una parcela de Pozuelo puede estar en un conjunto histórico y otra no.

| | Ámbito territorial | Ámbito sectorial |
|---|---|---|
| Se activa por | La cadena del municipio | Un **Fact del proyecto** |
| Estructura | Ruta jerárquica | Conjunto, sin orden |
| Ejemplo | `es.13.28.28115` | `patrimonio.conjunto_historico` |
| Se conoce | Al elegir municipio | Solo si el arquitecto lo declara o se integra un dato oficial |

Modelarlos como un sexto nivel de la ruta obligaría a que la ruta dependiera de la parcela, no del municipio, y con ello a recalcular la cadena por proyecto en lugar de por municipio — perdiendo toda la cacheabilidad de §12.

Cuando un ámbito sectorial **no se ha declarado**, el resultado no es "no aplica": es `desconocido`, y las reglas de ese ámbito quedan en estado `aplica_no_evaluable` con la pregunta pendiente hecha explícita al arquitecto. Es la aplicación directa de `UNCERTAINTY_MODEL.md`: la ausencia de declaración no es declaración de ausencia.

---

## 4. El perfil de proyecto

Segundo eje de filtrado, **ortogonal** al territorial. Los tres campos que el encargo enumera no son lo mismo y confundirlos genera reglas que no aplican:

| Campo | Qué es | Catálogo |
|---|---|---|
| `tipo_de_intervencion` | Qué se hace | obra_nueva · ampliacion · reforma · rehabilitacion · cambio_de_uso · demolicion · legalizacion |
| `uso` | A qué se destina | residencial · administrativo · comercial · docente · sanitario · publica_concurrencia · aparcamiento · industrial · hotelero |
| `tipologia` | Cómo se organiza | unifamiliar_aislada · unifamiliar_pareada · unifamiliar_adosada · plurifamiliar · colectiva_alojamiento |

Tres decisiones:

**El uso es un árbol, no una lista.** `residencial.vivienda_libre`, `residencial.vivienda_protegida`, `residencial.alojamiento_dotacional`. Una regla declara el nodo más alto al que aplica y **cubre todos sus descendientes**. Sin esto, cada regla tendría que enumerar variantes de uso, que es la misma explosión combinatoria que el encargo prohíbe, movida de sitio.

**El uso es por pieza, no solo por edificio.** Un edificio residencial con local comercial en planta baja tiene dos usos simultáneos, y las reglas de pública concurrencia aplican al local aunque el edificio sea residencial. El perfil de proyecto lleva por tanto un **uso principal** y un conjunto de **usos presentes por ámbito físico**. Diseñarlo con un solo uso ahorra dos días ahora y obliga a rehacerlo entero al primer proyecto de uso mixto.

**`tipologia` amplía el catálogo actual sin romperlo.** Hoy `evaluator.py` maneja tres valores (`plurifamiliar`/`unifamiliar`/`rehabilitacion`), y uno de ellos —`rehabilitacion`— **no es una tipología, es un tipo de intervención**. La tabla de correspondencia entre el catálogo actual y el nuevo es explícita, y `rehabilitacion` se traduce a `tipo_de_intervencion=rehabilitacion` conservando la tipología declarada. Mientras la migración no esté completa, el valor viejo se acepta y se marca como asunción visible, nunca se traduce en silencio.

---

## 5. Modelo de datos y formato

### 5.1 Formato: YAML

Confirmando `NORMATIVE_ENGINE.md` §11 (git como fuente de verdad, SQLite como índice derivado), y decidiendo lo que aquel documento dejó implícito:

| | YAML | JSON | TOML | BD |
|---|---|---|---|---|
| Diff legible por un curador no programador | **Sí** | Regular | Sí | No |
| Texto legal multilínea | **Nativo** (`\|`) | Escapado, ilegible | Regular | Sí |
| Comentarios (nota del curador, "pendiente de verificar") | **Sí** | **No** | Sí | Aparte |
| Anclas/reutilización | Sí — **se prohíbe** | No | No | — |
| Revisión por PR | Sí | Sí | Sí | No |

**YAML, con dos restricciones de estilo obligatorias:** prohibidas las anclas y referencias (`&`/`*`) — hacen el fichero ilegible para quien más tiene que leerlo, el arquitecto validador; y prohibido un fichero que declare más de una `NormaFuente`.

El JSON Schema del formato se versiona junto al corpus y es lo que ejecuta el validador de carga (§9).

### 5.2 Los campos de una regla

El encargo pide 22 campos. Se distribuyen entre las dos entidades que `NORMATIVE_ENGINE.md` §2 ya separó — la norma es un hecho externo, la regla es nuestra interpretación — más los tres bloques nuevos de este documento (aplicabilidad territorial, aplicabilidad de perfil, composición).

| Campo pedido | Entidad | Forma real |
|---|---|---|
| id | ambas | `concept_id` + `instance_id` |
| nombre | ReglaNormativa | — |
| ámbito | **Aplicabilidad** | Ruta de ámbito (§3.1) + sectoriales |
| organismo | NormaFuente | `fuente.organismo` |
| fuente oficial | NormaFuente | Estructura de `NORMATIVE_ENGINE.md` §3.1 |
| url oficial | NormaFuente | `fuente.url_oficial` (versión consolidada) |
| fecha | ambas | Bitemporal: 4 fechas, no una |
| versión | ambas, independientes | — |
| tipo de proyecto | **Aplicabilidad** | `tipo_de_intervencion` + `uso` |
| tipologías | **Aplicabilidad** | Lista; vacía = todas |
| condiciones de aplicación | ReglaNormativa | `CONSTRAINT_MODEL.md` §4, sin ampliar |
| prioridad | ReglaNormativa | 4 valores de `DECISION_ENGINE.md` §3 |
| dependencias | Grafo | Aristas tipadas de `NORMATIVE_ENGINE.md` §9 |
| regla ejecutable | ReglaNormativa | Uno de los 5 patrones cerrados |
| mensaje | ReglaNormativa | — |
| explicación técnica | ReglaNormativa | — |
| explicación para cliente | ReglaNormativa | — |
| referencia legal | NormaFuente | — |
| artículo | NormaFuente | Localizador jerárquico |
| severidad | ReglaNormativa | = prioridad; **no es un campo aparte** |
| categoría | ReglaNormativa | `materia` — catálogo cerrado (§7.2) |
| tags | ReglaNormativa | Libres, **nunca usados para resolver** |

Cuatro precisiones que el encargo no pide y son necesarias:

- **`severidad` y `prioridad` son el mismo eje.** Mantener dos campos garantiza que se contradigan. Lo que sí es distinto es la severidad *final del hallazgo*, que el contexto modula (hoy ya ocurre: `evaluator.py:1987`) y que es salida, no dato de la regla.
- **`categoría` no puede ser libre.** Es `materia`, y es lo que determina la competencia (§7.2). Si es texto libre, la jerarquía normativa deja de ser computable.
- **`tags` es libre precisamente porque no decide nada.** En cuanto un tag influya en si una regla aplica, se ha creado un eje de resolución sin gobierno. Prohibido por diseño: el resolver no lee `tags`.
- **Falta un campo en la lista del encargo: `nivel_de_conocimiento` (1-4).** Sin él, `EVIDENCE_MODEL.md` §3 no puede calcular la fuerza de un tramo, y toda la cadena de confianza se queda sin su primer eslabón.

### 5.3 Los parámetros nunca son escalares

Reafirmando `CONSTRAINT_MODEL.md` §9 en la forma que este subsistema hace obligatoria:

```yaml
parametro:
  ejes: [tipo_de_intervencion, tipologia]
  valores:
    - { tipologia: plurifamiliar, valor: 30.0 }
    - { tipologia: unifamiliar,   valor: 40.0 }
  repliegue: [tipologia, ninguno]     # cadena explícita y ordenada
  unidad: m2
```

`repliegue: [..., ninguno]` significa que si no hay valor, **no hay valor** — la regla devuelve `aplica_no_evaluable`, no un valor por defecto. Cada uso de un nivel de repliegue se escribe en la Evidence. Un repliegue silencioso en materia autonómica es el Bug #1 reencarnado en la capa normativa.

---

## 6. Estructura de carpetas

```
normativa/
  esquema/
    regla.schema.json              # valida cada fichero en carga
    materias.yaml                  # catálogo cerrado de materias (§7.2)
    competencias.yaml              # matriz materia × nivel → modo (§7.1)
    usos.yaml                      # árbol de usos (§4)
    patrones.yaml                  # los 5 de CONSTRAINT_MODEL.md — cerrado

  geografia/
    es/
      paises.yaml
      comunidades.yaml
      provincias.yaml
      municipios.yaml              # 8.131, completo desde el día 1 (§3.2)
      alias.yaml                   # variantes escritas → código INE
      supramunicipales.yaml        # áreas metropolitanas, mancomunidades
      derivados/
        zona_climatica.yaml        # absorbe cte_zonas.py
        densidad_urbana.yaml

  es/
    estatal/
      cte/
        db-si/…  db-sua/…  db-hs/…  db-he/…  db-hr/…  db-se/…
      loe/…
      accesibilidad/…
      definiciones/
        superficie_util.yaml       # tipo `definicion` (NORMATIVE_ENGINE §6)

    13-madrid/                     # 13 = código INE de la CCAA
      _ambito.yaml                 # metadatos + cobertura declarada
      habitabilidad/…
      accesibilidad/…
      municipios/
        28115-pozuelo-de-alarcon/
          _ambito.yaml
          pgou/…
          ordenanzas/…
        28079-madrid/
          _ambito.yaml
          …
    09-cataluna/
      municipios/08019-barcelona/…

  sectorial/
    patrimonio/…
    inundabilidad/…
    aeroportuario/…

  cobertura/
    manifiesto.yaml                # qué materias hay por ámbito y desde cuándo (§10)
```

Cuatro decisiones sobre esta estructura:

**El directorio lleva código y slug: `28115-pozuelo-de-alarcon`.** El código es la identidad (ordena, es estable, evita colisiones entre los 11 "Villanueva de…"); el slug es para el humano que navega el repositorio. Si el nombre oficial cambia, se renombra el directorio sin que nada dependa de ello — porque nada resuelve por nombre de directorio.

**El nivel de provincia no aparece en la ruta de ficheros.** Ninguna provincia española tiene competencia normativa en edificación. Está en el registro geográfico porque el usuario la declara y sirve para desambiguar homónimos, pero crear 50 directorios vacíos sería estructura falsa. Si algún día una diputación regula algo, se añade el nivel sin migrar nada, porque la cadena de ámbitos es de profundidad variable (§3.1).

**Cada ámbito tiene `_ambito.yaml`.** Es lo que convierte "añadir un municipio" en una operación de datos: crear el directorio, escribir su `_ambito.yaml` con la fecha de verificación y el responsable, y declarar su cobertura. El loader lo descubre recorriendo el árbol; no hay ningún registro central de municipios activos que actualizar.

**`sectorial/` cuelga de la raíz, no del municipio.** Consecuencia directa de §3.3: la normativa de patrimonio no pertenece a un municipio, se activa por un Fact de la parcela.

---

## 7. Motor de herencia y composición

El núcleo del subsistema, y donde se concentran los errores caros.

### 7.1 La herencia no es sobrescritura

El modelo ingenuo —el hijo pisa al padre— es **legalmente incorrecto** y produce respuestas equivocadas con regularidad. Tampoco vale "gana la más restrictiva": una ordenanza municipal no puede rebajar el DB-SI, pero el CTE **no regula en absoluto** la superficie mínima de vivienda, así que ahí no hay nada que comparar (es el hallazgo M1 de `NORMATIVE_AUDIT.md`).

La composición se resuelve **por materia y competencia**, con cuatro modos:

| Modo | Significado | Ejemplo de materia |
|---|---|---|
| `exclusivo` | Solo la capa competente aplica; las demás no tienen nada que decir | Habitabilidad → autonómica. Urbanismo → municipal |
| `suelo` | La capa superior fija un mínimo; la inferior puede endurecer, nunca relajar | Seguridad en caso de incendio, estructural, salubridad → estatal |
| `acumula` | Todas aplican simultáneamente; ninguna desplaza a otra | Sectorial (patrimonio) sobre lo demás |
| `exime` | Bajo condición, retira la aplicabilidad de otra | Régimen de edificio catalogado |

Esta matriz vive en `esquema/competencias.yaml` como **datos**:

```yaml
- materia: habitabilidad_superficies
  competencia: autonomica
  modo: exclusivo
  estatal_regula: false        # el CTE no dice nada de esto
- materia: seguridad_incendio
  competencia: estatal
  modo: suelo
  permite_endurecer: [autonomica, municipal]
- materia: urbanismo_parametros
  competencia: municipal
  modo: exclusivo
```

**Es la única pieza del sistema que codifica el reparto competencial español, y se toca cuando cambia la Constitución territorial, no cuando se añade un municipio.**

### 7.2 El catálogo de materias es cerrado

Una materia es la unidad sobre la que se resuelve la competencia. Debe ser cerrada, gobernada por el Curador, y de granularidad suficiente para que la competencia sea uniforme dentro de ella. Catálogo inicial propuesto (14):

`seguridad_incendio` · `seguridad_utilizacion` · `accesibilidad` · `salubridad` · `ahorro_energia` · `proteccion_ruido` · `seguridad_estructural` · `habitabilidad_superficies` · `habitabilidad_dimensional` · `habitabilidad_programa` · `urbanismo_parametros` · `urbanismo_estetica` · `patrimonio` · `medio_ambiente`

Crecer este catálogo es un acto de gobernanza, con la misma disciplina que el catálogo de 5 patrones de `CONSTRAINT_MODEL.md` §14: si una norma no encaja en ninguna materia, la primera hipótesis es que está mal clasificada, no que falte una materia.

### 7.3 Algoritmo de composición

```
entrada:  cadena de ámbitos, perfil de proyecto, fecha de devengo
salida:   ConjuntoAplicable

1. CANDIDATAS
   Unión de las reglas de todos los ámbitos de la cadena
   + ámbitos sectoriales activos (§3.3)

2. FILTRO TEMPORAL
   vigencia_desde <= fecha_devengo < vigencia_hasta
   (+ eje de registro para reconstruir un informe pasado — NORMATIVE_ENGINE §4)

3. FILTRO DE PERFIL
   tipo_de_intervencion ∈ declarados     (vacío = todos)
   uso ∈ subárbol declarado              (§4)
   tipologia ∈ declaradas                (vacía = todas)

4. FILTRO DE CONDICIONES
   árbol AND/OR/NOT de CONSTRAINT_MODEL.md §4 sobre Facts de contexto
   → una condición que necesita un Fact desconocido NO descarta la regla:
     la marca `aplica_no_evaluable` con la pregunta pendiente

5. AGRUPACIÓN POR MATERIA

6. COMPOSICIÓN, por materia, según competencias.yaml
   exclusivo → se conserva solo la capa competente; las demás se
               descartan con motivo registrado ("materia no competencia
               de este nivel"), nunca en silencio
   suelo     → estatal como base; inferior sustituye solo si endurece
               (comparación en la dirección declarada por la regla,
               no por magnitud del número)
   acumula   → todas conviven
   exime     → se evalúa la condición de exención; si se cumple, la
               regla eximida pasa a `no_aplica` con la cita del eximente

7. ARISTAS
   remite_a → se sigue.  deroga/modifica → ya resueltas en el paso 2

8. CONFLICTO
   Lo que sigue en contradicción NO se resuelve aquí.
   Se materializa como Conflict (DECISION_ENGINE.md §3) con ambas
   fuentes citadas, y decide el arquitecto.
```

**El paso 8 no es una carencia, es el diseño.** Existen discrepancias reales entre decreto autonómico y ordenanza municipal. Un motor que las zanja en silencio produce una respuesta segura de sí misma y equivocada la mitad de las veces. Uno que las expone con las dos citas es lo que un arquitecto puede llevar a una reunión.

**Y el paso 6 no puede caer en un desempate no declarado.** Si dos reglas de la misma materia y el mismo nivel se contradicen, es un error de corpus y debe fallar la validación (§9), no resolverse por orden alfabético de id ni por orden de carga — el riesgo que `CONFLICT_ENGINE.md` §2 nombra como el más probable bajo presión de entrega.

### 7.4 Prioridad ≠ jerarquía

Se reafirma `NORMATIVE_ENGINE.md` §7 porque es donde más se confunde: **prioridad** (qué pasa si se incumple: bloqueante / riesgo variable / recomendable / preferencial) y **jerarquía** (qué norma prevalece) son ejes independientes. Una regla municipal puede prevalecer sobre una estatal en su materia y ser, a la vez, de prioridad menor. Fusionarlos en un campo es un error que se paga en la segunda comunidad autónoma.

---

## 8. Loader y Resolver

### 8.1 Loader — tres etapas, fail-closed

```
descubrir → parsear → validar → indexar
```

**Fail-closed es la decisión importante.** Si un fichero de Pozuelo no valida, el sistema **no** carga "lo que sí funciona": marca esa materia de ese municipio como `sin_cobertura` y lo dice. La alternativa —cargar parcialmente— produce el peor resultado posible: un informe que afirma cumplimiento sobre un corpus mutilado sin que nadie lo sepa.

**Carga perezosa por ámbito.** No se carga el corpus: se carga la cadena del proyecto. Para Pozuelo son cinco ámbitos (estatal, CCAA 13, municipio 28115, más los sectoriales activos), del orden de 5-15 ficheros. **El coste de carga es independiente del tamaño total del corpus** — la propiedad sin la cual 8.000 municipios sí serían un problema.

**El índice es caché, nunca fuente de verdad** (`NORMATIVE_ENGINE.md` §11): SQLite generado a partir de los ficheros, con clave `(ambito, materia, vigencia)`, borrable y regenerable. Se sella con el hash del corpus; si no coincide, se regenera.

### 8.2 Resolver — contrato

Dos entradas, una salida, **sin estado**:

```
resolver(cadena_ambitos, perfil_proyecto, fecha_devengo) → ConjuntoAplicable
```

`ConjuntoAplicable` contiene, para cada regla candidata, **uno de cuatro estados y nunca silencio** (`NORMATIVE_ENGINE.md` §13):

| Estado | Significado |
|---|---|
| `aplica` | Rige y es evaluable |
| `no_aplica` | Vigente, pero sus condiciones excluyen este proyecto — **con el motivo** |
| `aplica_no_evaluable` | Rige, pero es cualitativa o falta un dato — se informa, no se puntúa |
| `sin_cobertura` | **No tenemos esa materia cargada para este ámbito** |

Y además, el propio conjunto lleva el **informe de cobertura** (§10). Un `ConjuntoAplicable` sin informe de cobertura no se puede interpretar: 12 reglas cumplidas no significan nada si no se sabe sobre cuántas materias.

---

## 9. Validación

Se ejecuta en carga y en CI. Ninguna regla entra en producción sin pasarla. Amplía las 8 validaciones de `NORMATIVE_ENGINE.md` §11.1 con las que este subsistema hace posibles:

| # | Validación | Qué error real previene |
|---|---|---|
| 1-8 | Las de `NORMATIVE_ENGINE.md` §11.1 | Citas sin boletín, escalares desnudos, ciclos de derogación… |
| 9 | El ámbito declarado existe en el registro geográfico | Un municipio inventado o un código INE mal escrito |
| 10 | La materia pertenece al catálogo cerrado | La categoría libre que rompe la competencia |
| 11 | **La materia es competencia del nivel que la declara** | El caso M1: una regla municipal fijando superficie mínima de vivienda |
| 12 | El `documento_basico` citado es compatible con la materia | Las 5 discrepancias M1-M5 |
| 13 | El uso declarado existe en el árbol de usos | Un uso escrito a mano que no filtra nada |
| 14 | No hay dos reglas de igual materia, ámbito y perfil en contradicción | El desempate silencioso de §7.3 |
| 15 | Toda arista apunta a un `concept_id` existente y vigente | Remisiones rotas |
| 16 | Toda regla evaluable declara `nivel_de_conocimiento` | Una cadena de confianza sin primer eslabón |
| 17 | El manifiesto de cobertura coincide con lo que hay en disco | Declarar cobertura que no existe — o tenerla y no declararla |

La 11 y la 17 son las que este documento añade y ninguna estructura previa podía comprobar.

---

## 10. Cobertura declarada

**El estado `sin_cobertura` no se puede inferir de la ausencia de reglas.** Que no haya reglas de patrimonio cargadas para Pozuelo no significa que Pozuelo no tenga normativa de patrimonio: significa que no la hemos transcrito. Confundir ambas cosas es exactamente la inferencia negativa que `INFERENCE_ENGINE.md` §2.2 prohíbe — y es la más peligrosa del sistema, porque falla como un tranquilizador "no hay problemas".

Por eso la cobertura es un **dato declarado**, no una consulta al corpus:

```yaml
# cobertura/manifiesto.yaml
- ambito: es.13.28.28115
  materias:
    urbanismo_parametros: { estado: parcial, verificado: 2026-08-06, por: "…" }
    patrimonio:           { estado: ausente }
    habitabilidad_superficies: { estado: no_competente }   # es autonómica
```

Y se muestra en producto. La diferencia entre estas dos frases es la diferencia entre un producto insostenible y uno vendible:

- ❌ *"Tu proyecto cumple."*
- ✅ *"Tu proyecto cumple las 214 reglas cargadas para Pozuelo de Alarcón (CTE completo, habitabilidad de la Comunidad de Madrid completa, urbanismo municipal parcial). **No hay cobertura de patrimonio ni de medio ambiente.** Última verificación del corpus municipal: 2026-08-06."*

`estado: no_competente` es un tercer valor necesario y no obvio: distingue "no lo tenemos" de "aquí no hay nada que tener porque la materia es de otro nivel". Sin él, todo municipio aparecería eternamente incompleto en materias que nunca le corresponden.

---

## 11. API interna

Seis funciones. Es todo lo que el resto del sistema puede llamar.

```python
# normativa/api.py  —  única superficie pública del paquete

resolver_ambito(pais, comunidad=None, provincia=None, municipio=None)
    → CadenaAmbitos            # o AmbitoAmbiguo si el nombre no desambigua

perfil_proyecto(tipo_intervencion, usos, tipologia)
    → PerfilProyecto

normativa_aplicable(cadena, perfil, fecha_devengo=None, sectoriales=())
    → ConjuntoAplicable        # incluye informe de cobertura

cobertura(cadena, fecha=None)
    → InformeCobertura

explicar_aplicabilidad(concept_id, cadena, perfil, fecha)
    → Explicacion              # por qué aplica o por qué no, con la cadena causal

diff_normativo(cadena, perfil, fecha_a, fecha_b)
    → [CambioNormativo]        # la consulta de NORMATIVE_ENGINE.md §4.3
```

Reglas del contrato:

- **Nada más es público.** Loader, índice, grafo y validadores son privados. Si algo fuera del paquete necesita leerlos, es señal de que la frontera está mal puesta.
- **Todo es puro y sin estado.** Mismas entradas → mismo `ConjuntoAplicable`, siempre. Es requisito de la traza reproducible de `TRACEABILITY.md` §10.
- **El resolver no importa nada de `analyzer/`.** La dependencia va en un solo sentido. `normativa/` se puede probar, y de hecho se prueba, sin un DXF.
- **`fecha_devengo=None` no es "hoy" en silencio.** Devuelve el conjunto de hoy *y* una asunción explícita en el resultado, que la capa de explicación está obligada a mostrar.
- **`resolver_ambito` puede fallar con `AmbitoAmbiguo`**, y debe. "Villanueva" no es un municipio; el sistema devuelve los candidatos y pregunta, no elige el más poblado.

---

## 12. Flujo completo

```
  USUARIO
  país · comunidad · provincia · municipio · tipo · uso · tipología · fecha
      │
      ▼
┌─────────────────────┐   nombre → código INE, alias, homónimos
│ resolver_ambito()   │   ─────────────────────────────────────────►  AmbitoAmbiguo → preguntar
└─────────┬───────────┘
          │  CadenaAmbitos:  es → es.13 → es.13.28 → es.13.28.28115
          │                  + sectoriales activos (por Fact, §3.3)
          ▼
┌─────────────────────┐
│ perfil_proyecto()   │   tipo_intervencion × árbol de usos × tipología
└─────────┬───────────┘
          ▼
┌─────────────────────┐   carga perezosa: SOLO los ámbitos de la cadena
│ LOADER (fail-closed)│   ~5-15 ficheros, coste independiente del corpus
└─────────┬───────────┘   fallo de validación → sin_cobertura, nunca parcial
          ▼
┌─────────────────────┐   1 candidatas   2 temporal   3 perfil   4 condiciones
│ RESOLVER            │   5 materia      6 competencia  7 aristas  8 conflicto
└─────────┬───────────┘
          ▼
   ConjuntoAplicable  +  InformeCobertura
   aplica · no_aplica(motivo) · aplica_no_evaluable · sin_cobertura
          │
          ▼
┌─────────────────────┐   ← FRONTERA F1: aquí abajo nadie sabe qué es un municipio
│ INTÉRPRETE / evaluator│  evalúa las reglas `aplica` contra la geometría
└─────────┬───────────┘
          ▼
   Problemas + Evidence  ──►  Conflictos abiertos (paso 8) ──► decide el arquitecto
          │
          ▼
   INFORME  +  cobertura declarada  +  traza inmutable (TRACEABILITY.md)
```

---

## 13. Ejemplo: Pozuelo de Alarcón

Vivienda unifamiliar aislada, obra nueva, licencia solicitada el 2026-03-15.

**Entrada del usuario**

```
País:       España
Comunidad:  Comunidad de Madrid
Provincia:  Madrid
Municipio:  Pozuelo de Alarcón
Tipo:       obra_nueva
Uso:        residencial.vivienda_libre
Tipología:  unifamiliar_aislada
Fecha:      2026-03-15
```

**Cadena resuelta**

```
es                    → CTE (DB-SI, DB-SUA, DB-HS, DB-HE, DB-HR, DB-SE), LOE, accesibilidad estatal
es.13                 → habitabilidad y diseño de la Comunidad de Madrid
es.13.28              → (sin competencia normativa; solo desambigua)
es.13.28.28115        → PGOU y ordenanzas de Pozuelo de Alarcón
sectoriales           → ninguno declarado → patrimonio y medio ambiente quedan como
                        pregunta pendiente, no como "no aplica"
derivados             → zona climática D (desde geografia/derivados/, absorbe cte_zonas.py)
```

**Composición por materia**

| Materia | Capas con reglas | Modo | Resultado |
|---|---|---|---|
| `seguridad_incendio` | estatal | suelo | Aplica el DB-SI. Ninguna capa inferior lo endurece |
| `accesibilidad` | estatal + autonómica | suelo | Estatal como base; la autonómica prevalece **solo donde endurece**, y el hecho de que endurezca se registra en la Evidence |
| `habitabilidad_superficies` | **autonómica** | exclusivo | Aplica la de la Comunidad de Madrid. **El CTE se descarta con motivo explícito: no regula esta materia.** Es la corrección del hallazgo M1 |
| `urbanismo_parametros` | **municipal** | exclusivo | La regla es *"la ocupación no puede superar el máximo aplicable"*. **El valor del máximo no está en el corpus** (§14) |
| `patrimonio` | — | — | `sin_cobertura` — declarado, no silenciado |

**Lo que el arquitecto ve**

> Se han aplicado **N reglas** para Pozuelo de Alarcón, vigentes a 2026-03-15.
> **Cobertura:** CTE completo · habitabilidad Comunidad de Madrid completa · urbanismo municipal parcial · **sin cobertura de patrimonio ni medio ambiente**.
> **Pendiente de declarar:** ¿está la parcela en ámbito de protección patrimonial? Afecta a 6 reglas.
> **1 parámetro no informado:** ocupación máxima de la parcela — dato de la ficha urbanística, no del corpus.
> Última verificación del corpus municipal: 2026-08-06.

**Y el mismo plano en Barcelona (`es.09.08.08019`)** cambia de resultado sin que se toque una línea de código: cambia la capa autonómica de habitabilidad y la municipal de urbanismo. Cambiar el resultado según el territorio *es* el comportamiento correcto — hoy no ocurre, y por eso el producto emite un juicio calibrado para una región implícita sobre proyectos de toda España.

> **Aviso sobre este ejemplo.** Los identificadores oficiales, artículos y umbrales concretos de la normativa autonómica de Madrid y del planeamiento de Pozuelo **se dejan deliberadamente sin fijar**. Son contenido a transcribir del boletín y validar por un arquitecto colegiado (`NORMATIVE_ENGINE.md` §12), no algo que un documento de arquitectura deba dar por sabido. Escribirlos aquí de memoria sería cometer, en el documento que diseña la solución, exactamente el error que la solución existe para impedir — y es literalmente el origen de la tabla `SUPERFICIE_MIN_CCAA` de §1.2.

---

## 14. Lo que este diseño no resuelve

**Los parámetros urbanísticos por parcela.** Se reafirma `NORMATIVE_ENGINE.md` §10.2 porque es la trampa de toda la capa municipal: una ordenanza **no dice** "ocupación máxima 60 %". Dice que la ocupación es la que fije la norma zonal de esa parcela, que se lee en su ficha urbanística.

| Parte | Naturaleza | Dónde vive |
|---|---|---|
| *"La ocupación no puede superar el máximo aplicable"* | ReglaNormativa | Este corpus |
| *"El máximo de esta parcela es 60 %"* | **Fact declarado o integrado** | El proyecto |

El código ya funciona así por accidente: `evaluate_solar_occupation` (`evaluator.py:2609`) devuelve `None` si no se informa `ocupacion_maxima_pct`. Ese comportamiento es **correcto y debe preservarse**. Cualquier intento de meter los parámetros urbanísticos de 8.000 municipios en el corpus está mal planteado: es integración de datos catastrales y de planeamiento, de otro orden de magnitud, y no es lo que este documento diseña.

---

## 15. Rendimiento y escala

| Magnitud | Estimación | Consecuencia |
|---|---|---|
| Municipios en el registro | 8.131 (completo) | ~400 KB de datos, carga única |
| Ámbitos por proyecto | **5-8** | Constante — no crece con el corpus |
| Ficheros leídos por análisis | 5-15 | Carga perezosa (§8.1) |
| Reglas candidatas por proyecto | 400-900 | Filtrado sobre cientos, no sobre el corpus |
| Coste de resolución tras índice | Filtrado de conjuntos | Irrelevante frente al parseo del DXF (segundos) |
| Índice completo | Artefacto de build | No es coste de petición |

**El riesgo de rendimiento real no es el volumen: es la dependencia declarada en exceso.** Es el mismo peligro que `CHAIN_ENGINE.md` §9 nombra para la propagación. Una regla que declare aplicabilidad territorial `es` cuando en realidad solo aplica a un uso concreto no produce ningún error visible: el sistema sigue siendo correcto, solo deja de ser específico, y el conjunto candidato crece hasta que el filtrado deja de discriminar. Se detecta midiendo el tamaño del conjunto candidato por análisis, no esperando a que algo falle.

**Coste de arranque en frío:** cargar el registro geográfico completo. Se hace una vez por proceso y se puede sellar como artefacto binario si alguna vez importa. No importa hoy.

---

## 16. Riesgos

| # | Riesgo | Mitigación | Residual |
|---|---|---|---|
| 1 | **El contenido, no la arquitectura, es el cuello de botella.** 8.131 municipios × 14 materias = 113.834 casillas de curación que nunca se llenarán | Cobertura declarada (§10): la cobertura parcial es honesta y segura, no un fallo | **Alto y permanente.** Es la naturaleza del problema, no un defecto |
| 2 | **Error de transcripción.** Un dígito mal copiado se propaga a cientos de informes | Regla de dos personas, `hash_texto`, tests de regresión | **Alto.** Ninguna estructura de datos protege de esto |
| 3 | **Deriva de la capa municipal.** Las ordenanzas cambian sin canal de aviso | Fecha de verificación visible en producto | **Medio-alto.** Coste fijo por municipio, permanente |
| 4 | **Sobrediseño para un producto sin usuarios externos** | Fase 1 entrega valor sola (§17) | **Real.** Ver abajo |
| 5 | **Que la matriz de competencias se toque para resolver un caso concreto** | Es esquema, no corpus; cambiarla exige revisión explícita | **Medio.** Riesgo de gobernanza, no de estructura |
| 6 | **Migrar `evaluator.py` en bloque** | Estrangulamiento: una regla, con test de salida congelada | **Bajo si se respeta la secuencia** |
| 7 | **Que "gana la más restrictiva" vuelva** por ser cómodo | §7.1 y validación 11 | **Medio.** Es lo primero que se propone cuando aprieta la entrega |

**Sobre el riesgo 4, con franqueza.** Esto es infraestructura considerable para un producto sin usuarios de pago. Lo que la justifica no es la escala futura: es que **hoy hay dos respuestas contradictorias a la misma pregunta legal en la misma pantalla** (§1.2), y que las decisiones de identidad territorial y de tiempo no se pueden añadir después. Un corpus que resuelve por nombre de ciudad no se convierte retroactivamente en uno que resuelve por código INE con vigencia.

**La lectura correcta no es "constrúyelo entero".** Es: acierta el esquema territorial y el eje temporal desde la primera regla, y puebla el corpus al ritmo que lo pidan clientes reales. Un municipio nuevo no es una funcionalidad que se entrega: es un compromiso de mantenimiento permanente.

---

## 17. Plan por fases

Cada fase deja el producto en un estado mejor y publicable. **Ninguna fase modifica el comportamiento de una regla existente sin un test de salida congelada delante.**

| Fase | Contenido | Toca `evaluator.py` | Resultado observable |
|---|---|---|---|
| **0** | Paquete `normativa/`, esquema, registro geográfico completo, loader, validadores. Corpus vacío | No | Nada visible. Se puede resolver la cadena de cualquier municipio de España |
| **1** | Resolver + motor de herencia + matriz de competencias. Corpus semilla: **una materia, una regla** — superficie mínima de vivienda, en su capa correcta (autonómica) | No | **Muere `SUPERFICIE_MIN_CCAA` del frontend.** El dato se sirve desde la API, con cita y cobertura |
| **2** | Informe de cobertura en producto | No | El producto deja de afirmar "cumple" a secas |
| **3** | Estrangulamiento: `evaluate_unit_minimum_area` pasa a consumir el corpus | **Sí — una función** | Un mismo plano da resultado distinto en Madrid y en Sevilla, que es lo correcto |
| **4** | Transcripción del resto de reglas de `evaluator.py` con su cita real | Gradual | Las 5 discrepancias M1-M5 mueren en el validador; el producto pasa de 0 reglas citando artículo a todas |
| **5** | Capa municipal (reglas, no parámetros de parcela) para 1 municipio real | No | Cobertura urbanística real, en un municipio, verificada |
| **6** | `diff_normativo` | No | La capacidad diferencial de `NORMATIVE_ENGINE.md` §4.3 |

**La Fase 1 es la que más valor entrega por unidad de esfuerzo**, y no depende de las demás: elimina una contradicción visible hoy en pantalla y sustituye una tabla sacada de la prensa por un dato con fuente, fecha y cobertura declarada.

Las fases 0-2 y 4 son, en rigor, corrección de comportamiento existente. Las fases 3, 5 y 6 son capacidad nueva y requieren PRD aprobado (`CLAUDE.md`).

---

## 18. Resumen de decisiones estructurales

1. **Identidad territorial por código INE**, nunca por nombre. El nombre es una etiqueta con alias.
2. **La cadena de ámbitos tiene profundidad variable**, la determina el dato. Ningún componente asume cinco niveles.
3. **El registro geográfico está completo desde el día 1**; el corpus normativo no. Es lo que hace literalmente cierto que añadir un municipio no toca código.
4. **Los ámbitos sectoriales se superponen, no se heredan** — se activan por un Fact del proyecto, no por el municipio.
5. **El uso es un árbol y es por pieza**, no un valor único por edificio.
6. **La herencia se resuelve por materia y competencia** (4 modos), no por sobrescritura ni por "gana la más restrictiva".
7. **La matriz de competencias es la única pieza que codifica el reparto territorial español**, y es un dato.
8. **El catálogo de materias es cerrado**; `tags` es libre precisamente porque no decide nada.
9. **Ningún parámetro es un escalar**: siempre tabla con cadena de repliegue, y cada repliegue se escribe en la Evidence.
10. **Loader fail-closed y carga perezosa por cadena** — el coste no depende del tamaño del corpus.
11. **La cobertura se declara, no se infiere de la ausencia.** `no_competente` es un estado distinto de `ausente`.
12. **Cuatro estados, nunca silencio**, y el conflicto genuino se expone con las dos citas en lugar de zanjarse.
13. **Seis funciones públicas.** `normativa/` no importa nada de `analyzer/`.
14. **Los parámetros urbanísticos por parcela quedan fuera del corpus** — son Facts del proyecto.

---

*Documento de diseño. Ninguna línea de código escrita ni modificada. Los identificadores oficiales, artículos y umbrales de la normativa autonómica y municipal se dejan expresamente sin fijar: son contenido a transcribir y validar contra boletín por el Curador y el validador técnico, no algo que un documento de arquitectura deba dar por sabido.*
