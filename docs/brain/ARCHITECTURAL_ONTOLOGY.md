# ARCHITECTURAL_ONTOLOGY.md

**Propósito:** el diccionario oficial del conocimiento arquitectónico sobre el que razona ArchMuse — todos los conceptos del mundo real que un arquitecto reconoce al mirar un proyecto (Parcela, Pieza, Fachada, Itinerario...), sus atributos, cómo se relacionan entre sí, y cómo un sistema puede reconocerlos a partir de un plano. Este documento no piensa en programación en ningún momento — no hay clases, ni esquemas, ni código. Es vocabulario, no mecanismo.

**Frontera con `REASONING_ENGINE_SPEC.md` — léase antes que el resto, para no repetir el error de nombres ya señalado en `OBSERVATION_MODEL.md`:** este documento y `REASONING_ENGINE_SPEC.md` son dos ontologías distintas, deliberadamente. `REASONING_ENGINE_SPEC.md` define **entidades técnicas** — Fact, Constraint, Inference — que son la maquinaria con la que el motor razona. Este documento define **conceptos de dominio** — Pieza, Fachada, Itinerario — que son *sobre qué* razona esa maquinaria. La relación entre ambos es precisa y unidireccional: el atributo "tipo namespaced" de un Fact (`FACT_MODEL.md` §3) y las "dimensiones de ámbito" que un Fact puede referenciar (`FACT_MODEL.md` §2.3) apuntan siempre a un concepto de **este** documento — un Fact de tipo `pieza.superficie_util` es un dato técnico cuyo tipo solo tiene sentido si "Pieza" y "Superficie útil" están aquí, definidos con precisión. Sin este documento, el espacio de nombres de Fact (`FACT_MODEL.md` §12.2, ya señalado como riesgo) no tiene un vocabulario controlado del que tomar sus nombres — los inventa cada dominio por su cuenta. Este documento es esa fuente única.

**Referencias obligatorias, asumidas como ya decididas:**
- `ARCHITECTURAL_KNOWLEDGE_MAP.md` — la sección 1 ("Conceptos fundamentales") de cada uno de los 14 dominios ya nombra la mayoría de estos conceptos, dispersos y sin relación explícita entre ellos. Este documento no inventa contenido nuevo — consolida, relaciona y desambigua lo que ya estaba disperso en 14 secciones distintas.
- `FACT_MODEL.md` §2.3 — el ámbito de un Fact como conjunto de dimensiones (física, elemento constructivo, sistema/instalación, itinerario). Los conceptos de este documento son, precisamente, los nodos posibles de esas dimensiones.
- `CONSTRAINT_MODEL.md` §10-12 — tipología, zona climática y contexto como ejes de resolución de parámetros. Este documento fija con precisión qué son esos conceptos, de los que `CONSTRAINT_MODEL.md` ya asumía el significado sin definirlo formalmente.
- `EXPLANATION_ENGINE.md` §2 — el "vocabulario canónico único" que el Narrador debe usar. Este documento es la fuente de la que ese diccionario debe derivar sus nombres — no dos vocabularios paralelos, uno.
- Grounding real: `analyzer/parser.py` — hoy el parser reconoce, exclusivamente, polilíneas cerradas del layer `"00 areas"` (constante `AREA_LAYER`) como polígonos de Pieza, descarta contornos agrupadores por su color DXF explícito (ACI 10/150, distinto de `BYLAYER_COLOR`), asocia cada polígono al `MTEXT` más cercano como etiqueta de uso, y reconoce etiquetas de vivienda con el patrón `VT<n>/<m>` (`UNIT_LABEL_PATTERN`). No reconoce muros, huecos, elementos estructurales ni fachadas como entidades DXF distintas — esto se declara explícitamente en cada concepto que lo afecta, sección "cómo reconocerlo automáticamente", en vez de asumir una capacidad de reconocimiento que el parser real no tiene.

---

## 0. Cómo está organizado este documento

**42 conceptos**, agrupados en 8 familias que cruzan los 14 dominios de `BRAIN_ARCHITECTURE.md` (un concepto como Pieza es usado por los Dominios 3, 4, 5, 6, 7 y 9 a la vez — agrupar por dominio habría repetido el mismo concepto 6 veces). Cada concepto se define con exactamente los 10 campos pedidos, en el mismo orden siempre, para que el documento se pueda usar como diccionario de consulta, no solo de lectura lineal.

### 0.1 Vocabulario cerrado de tipos de relación

Igual que `CONSTRAINT_MODEL.md` cierra su vocabulario de comparadores, las relaciones entre conceptos de este documento usan siempre uno de estos siete verbos — nunca una relación libre inventada para un caso concreto:

| Relación | Significado | Ejemplo |
|---|---|---|
| **contiene / pertenece a** | Relación de contención jerárquica (par inverso) | Edificio contiene Planta; Planta pertenece a Edificio |
| **delimita** | Un elemento físico marca el borde de un espacio | Partición delimita Pieza |
| **da a / se abre a** | Relación de apertura o vista entre un elemento y un espacio | Hueco da a Fachada; Pieza se abre a Patio |
| **sirve a / servido por** | Relación funcional de servicio (par inverso, distinción de Kahn ya citada en `ARCHITECTURAL_QUALITY.md` §1) | Núcleo húmedo sirve a Vivienda |
| **conecta con** | Relación de continuidad de circulación | Itinerario conecta Pieza con Pieza |
| **se apoya en** | Relación de dependencia física estructural | Forjado se apoya en Elemento estructural |
| **se ubica en** | Relación de pertenencia a un ámbito territorial/normativo, no físico-arquitectónico | Parcela se ubica en Ámbito territorial normativo |

---

## Familia A — Marco territorial y legal

### A.1 Parcela

- **Definición:** porción delimitada de terreno con identidad registral y catastral propia, sobre la que puede o no ser posible edificar.
- **Atributos:** superficie, geometría del perímetro, referencia catastral, calificación urbanística vigente.
- **Relaciones:** se ubica en Ámbito territorial normativo; contiene Edificio (cero o más); delimitada por Retranqueo respecto a linderos y vial.
- **Sinónimos:** terreno, finca (uso coloquial, evitar como término técnico por imprecisión registral).
- **Concepto padre:** ninguno — es la raíz territorial de toda la ontología.
- **Conceptos hijo:** Solar (especialización, ver A.2).
- **Ejemplos:** una parcela urbana catalogada en el PGOU con edificabilidad asignada.
- **Contraejemplos:** una superficie de terreno sin referencia catastral propia (parte de una parcela mayor no segregada) no es, todavía, una Parcela a efectos de este modelo.
- **Ambigüedades:** el uso coloquial confunde Parcela y Solar constantemente; este documento los distingue a propósito (ver A.2) porque `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 1 ya lo exige.
- **Cómo reconocerlo automáticamente:** no es reconocible desde el DXF de distribución — no hay geometría de parcela en los planos que hoy procesa `parser.py`. Requiere un dato declarado (referencia catastral) o una integración externa (visor catastral/urbanístico), ninguna existente hoy.

### A.2 Solar

- **Definición:** Parcela que ya cuenta con los servicios urbanísticos exigidos (acceso rodado, abastecimiento, saneamiento, energía) y es, por tanto, apta para edificar sin trámite de urbanización previo.
- **Atributos:** los mismos que Parcela, más la condición binaria de disponer de servicios urbanísticos completos.
- **Relaciones:** especializa a Parcela (ver A.1); condición previa para que Edificabilidad (A.3) sea ejercitable.
- **Sinónimos:** ninguno preciso — "parcela edificable" se usa a veces de forma imprecisa como sinónimo.
- **Concepto padre:** Parcela.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** una parcela urbana consolidada con acera y red de saneamiento ya conectada.
- **Contraejemplos:** una parcela rústica sin acceso rodado ni saneamiento no es un Solar, aunque tenga referencia catastral y sea, en sentido coloquial, "un terreno".
- **Ambigüedades:** la distinción Parcela/Solar es, con diferencia, la confusión terminológica más frecuente en el lenguaje no técnico — vale la pena que el vocabulario canónico de `EXPLANATION_ENGINE.md` nunca los use como intercambiables.
- **Cómo reconocerlo automáticamente:** no reconocible desde el DXF; es un dato declarado o verificado contra fuente municipal, exactamente igual que Parcela.

### A.3 Edificabilidad

- **Definición:** cantidad máxima de superficie construible que el planeamiento urbanístico permite sobre una Parcela, expresada como ratio (m²/m² de parcela) o como valor absoluto en m².
- **Atributos:** valor máximo, unidad (ratio o absoluto), fuente normativa (ficha urbanística del PGOU/PGOM).
- **Relaciones:** se ubica en Ámbito territorial normativo; limita la Superficie construida (G.2) total del conjunto de Edificios que contiene una Parcela.
- **Sinónimos:** ninguno estricto en el uso profesional español.
- **Concepto padre:** ninguno (es un parámetro urbanístico de primer nivel, no una especialización de otro concepto de esta ontología).
- **Conceptos hijo:** ninguno.
- **Ejemplos:** "edificabilidad 1,2 m²/m²" en una ficha urbanística.
- **Contraejemplos:** la superficie realmente construida en un proyecto concreto no es Edificabilidad — es Superficie construida (G.2); Edificabilidad es el límite, no el resultado.
- **Ambigüedades:** se confunde con frecuencia con Aprovechamiento urbanístico (ver revisión final, sección "Redundancias resueltas" — 1) y con Ocupación en planta, que es un límite en planta, no en superficie total edificada.
- **Cómo reconocerlo automáticamente:** no reconocible desde el DXF de distribución; es un dato normativo consultado en la ficha urbanística, no derivado de geometría de proyecto.

### A.4 Aprovechamiento urbanístico

- **Definición:** derecho edificatorio realmente atribuido a una Parcela concreta, resultante de aplicar la Edificabilidad del planeamiento a la superficie real de esa Parcela, descontadas cesiones obligatorias si las hubiera.
- **Atributos:** valor en m² edificables realmente asignados a esta parcela concreta, cesiones descontadas si aplica.
- **Relaciones:** se deriva de Edificabilidad (A.3) aplicada sobre la superficie de una Parcela concreta (A.1).
- **Sinónimos:** ninguno estricto.
- **Concepto padre:** ninguno.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** una parcela de 500 m² con edificabilidad 1,2 m²/m² y sin cesiones tiene un aprovechamiento de 600 m².
- **Contraejemplos:** la Edificabilidad en sí (el ratio del planeamiento, aplicable a cualquier parcela de esa zona) no es Aprovechamiento urbanístico — este último es siempre un valor ya aplicado a una parcela específica.
- **Ambigüedades:** en la práctica profesional española, "edificabilidad" y "aprovechamiento" se usan con frecuencia como sinónimos — este documento los mantiene separados porque la distinción (ratio general vs. derecho ya calculado sobre una parcela concreta, con cesiones descontadas) es real y relevante para Dominio 1, pero es, con diferencia, el par de conceptos con mayor solape real de toda esta ontología (ver revisión final).
- **Cómo reconocerlo automáticamente:** no reconocible desde el DXF; se calcula, no se observa, a partir de A.1 y A.3.

### A.5 Retranqueo

- **Definición:** distancia mínima obligatoria que debe separar la edificación de un lindero de Parcela, de la alineación a vial, o de otra edificación dentro de la misma parcela.
- **Atributos:** distancia mínima, lindero de referencia (frontal/lateral/fondo), fuente normativa.
- **Relaciones:** delimita el área edificable dentro de una Parcela; condiciona, junto con Ocupación en planta, cuánta Superficie construida (G.2) es geométricamente posible por planta.
- **Sinónimos:** separación a linderos.
- **Concepto padre:** ninguno.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** "retranqueo mínimo a lindero lateral: 3 m".
- **Contraejemplos:** la distancia real entre dos edificios ya construidos no es, por sí sola, un Retranqueo — Retranqueo es el mínimo normativo exigido, no la medida observada (esa medida observada, si acaso, es un Fact que se compara contra el Retranqueo como Constraint).
- **Ambigüedades:** ninguna significativa — es de los conceptos más precisos de esta familia.
- **Cómo reconocerlo automáticamente:** el valor normativo no es reconocible desde el DXF (viene de la ficha urbanística); la distancia real construida sí sería medible geométricamente si el DXF incluyera la geometría del lindero de parcela, cosa que hoy no ocurre — el parser actual no procesa geometría de parcela en absoluto.

---

## Familia B — Organización del edificio y del programa

### B.1 Proyecto arquitectónico

- **Definición:** el conjunto completo de información (geometría, declaraciones, normativa aplicable) sobre una intervención constructiva concreta que ArchMuse evalúa como una unidad.
- **Atributos:** tipología declarada, alcance de la intervención (obra nueva/rehabilitación), fecha de referencia normativa.
- **Relaciones:** contiene uno o más Edificio; se ubica en una Parcela (aunque el proyecto pueda evaluarse sin ese dato, ver A.1).
- **Sinónimos:** "el proyecto", "la intervención".
- **Concepto padre:** ninguno — es la raíz de la dimensión de contención física (`FACT_MODEL.md` §2.3).
- **Conceptos hijo:** Edificio.
- **Ejemplos:** el conjunto que analiza ArchMuse a partir de `ejemplo.dxf` más los datos de formulario (tipología, ciudad, norte).
- **Contraejemplos:** un único DXF con dos edificios completamente independientes en la misma parcela son, en este modelo, un Proyecto que contiene dos Edificios, no dos Proyectos.
- **Ambigüedades:** ninguna relevante.
- **Cómo reconocerlo automáticamente:** es la unidad de entrada del sistema — se corresponde 1:1 con lo que produce una ejecución de `build_rooms_from_document` sobre un DXF más los parámetros de formulario; no requiere reconocimiento, es el marco que el usuario declara al subir un archivo.

### B.2 Edificio

- **Definición:** construcción física completa, delimitada por su propia envolvente, que agrupa una o más Plantas y, dentro de ellas, una o más Unidades de uso.
- **Atributos:** número de plantas, altura de evacuación, existencia de ascensor.
- **Relaciones:** pertenece a Proyecto arquitectónico; contiene Planta; se ubica, indirectamente vía Proyecto, en Parcela.
- **Sinónimos:** "la edificación".
- **Concepto padre:** Proyecto arquitectónico (por contención, no por especialización).
- **Conceptos hijo:** Planta.
- **Ejemplos:** un bloque plurifamiliar de 6 plantas.
- **Contraejemplos:** una Planta suelta sin el resto del edificio no es, por sí sola, un Edificio.
- **Ambigüedades:** ninguna relevante.
- **Cómo reconocerlo automáticamente:** no reconocible directamente — el parser actual procesa un único DXF de una planta a la vez; la agrupación de varias plantas en un mismo Edificio es, hoy, un supuesto implícito del flujo de análisis, no un dato reconocido de la geometría.

### B.3 Planta

- **Definición:** nivel horizontal completo de un Edificio, con su propia geometría de distribución.
- **Atributos:** número de nivel (sótano/baja/1ª...), altura libre, superficie total.
- **Relaciones:** pertenece a Edificio; contiene Unidad de uso y Elemento común; se apoya en la Planta inferior (relación estructural, Familia F).
- **Sinónimos:** nivel, piso (uso coloquial, evitar como término técnico porque "piso" también significa Vivienda en España, ver ambigüedad).
- **Concepto padre:** Edificio.
- **Conceptos hijo:** Unidad de uso, Zona común (C.6).
- **Ejemplos:** "planta primera" de un edificio plurifamiliar.
- **Contraejemplos:** un altillo o entreplanta parcial que no cubre la totalidad de la huella del edificio es una figura distinta (no modelada en detalle en esta versión de la ontología) y no debe tratarse como una Planta completa sin más.
- **Ambigüedades:** "piso" en español coloquial significa tanto Planta como Vivienda — el vocabulario canónico de `EXPLANATION_ENGINE.md` nunca debe usar "piso" para evitar esa ambigüedad, prefiriendo siempre "planta" o "vivienda" según corresponda.
- **Cómo reconocerlo automáticamente:** hoy, cada DXF procesado corresponde implícitamente a una única Planta — no hay reconocimiento automático de "a qué planta pertenece este DXF"; es un dato de contexto, no derivado de la geometría.

### B.4 Unidad de uso

- **Definición:** conjunto de Piezas con un único uso independiente asignado, delimitado como una unidad funcional y, habitualmente, de propiedad o alquiler independiente.
- **Atributos:** superficie útil total, número de piezas habitables, uso principal.
- **Relaciones:** pertenece a Planta; contiene Pieza; sirve de ámbito para Núcleo húmedo.
- **Sinónimos:** ninguno genérico — sus especializaciones (Vivienda, Local) sí tienen sinónimos propios.
- **Concepto padre:** ninguno propio — es el concepto genérico del que Vivienda y Local son especializaciones.
- **Conceptos hijo:** Vivienda (B.5), Local (B.6).
- **Ejemplos:** cualquier Vivienda o Local considerado individualmente.
- **Contraejemplos:** una Zona común (escalera, portal) no es una Unidad de uso — no tiene propiedad/uso independiente asignado a un solo titular.
- **Ambigüedades:** ninguna relevante a este nivel genérico.
- **Cómo reconocerlo automáticamente:** el parser reconoce las etiquetas de vivienda con el patrón `VT<n>/<m>` (`UNIT_LABEL_PATTERN`, distinto del `MTEXT` de uso de cada Pieza) — esto identifica Vivienda como caso concreto; no existe hoy un mecanismo equivalente para reconocer Local como Unidad de uso distinta.

### B.5 Vivienda

- **Definición:** Unidad de uso destinada a residencia habitual de personas.
- **Atributos:** los de Unidad de uso, más número de dormitorios, superficie útil/construida propia.
- **Relaciones:** especializa a Unidad de uso; contiene Pieza habitable y Pieza no habitable; sirve de ámbito de aplicación para la mayoría de reglas de los Dominios 3-7.
- **Sinónimos:** piso (coloquial, ver ambigüedad en B.3), unidad residencial.
- **Concepto padre:** Unidad de uso.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** la unidad etiquetada "VT6/2" en `ejemplo.dxf`.
- **Contraejemplos:** un trastero o plaza de garaje vinculado a una vivienda no es, por sí solo, una Vivienda — es una Pieza no habitable vinculada, con régimen normativo distinto.
- **Ambigüedades:** el límite entre una Vivienda con dos núcleos independientes y una "bifamiliar" real es, según `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 2 §8, un caso genuinamente sin respuesta correcta automática — se nombra aquí para que quede registrado también a nivel de vocabulario, no solo de regla.
- **Cómo reconocerlo automáticamente:** con fiabilidad alta hoy — el patrón `VT<n>/<m>` en `MTEXT` (`UNIT_LABEL_PATTERN`) es, precisamente, la etiqueta de vivienda real del plano, distinta de las etiquetas de uso de cada pieza individual.

### B.6 Local

- **Definición:** Unidad de uso destinada a un uso distinto del residencial (terciario, comercial, dotacional).
- **Atributos:** los de Unidad de uso, más uso específico declarado (comercial, oficina, dotacional...).
- **Relaciones:** especializa a Unidad de uso.
- **Sinónimos:** local comercial (cuando el uso específico lo es).
- **Concepto padre:** Unidad de uso.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** un local comercial en planta baja de un edificio plurifamiliar.
- **Contraejemplos:** una plaza de garaje individual no es un Local — es una Pieza no habitable, salvo que constituya, ella sola, la totalidad de una unidad de propiedad independiente con uso propio declarado.
- **Ambigüedades:** el límite entre Local y Espacio técnico (C.6) cuando un espacio técnico grande (sala de máquinas) tiene, además, valor de superficie computable — caso poco frecuente pero real.
- **Cómo reconocerlo automáticamente:** no reconocible hoy — no existe un patrón de etiqueta equivalente al `VT<n>/<m>` de Vivienda para Local; se apoya, en la práctica actual, en la etiqueta de uso de la Pieza (`MTEXT`) sin agrupación automática a nivel de unidad completa.

### B.7 Tipología edificatoria

- **Definición:** clasificación del Proyecto según el número de unidades de vivienda, existencia de elementos comunes, y uso característico — el filtro que determina qué conjunto de normativa de cada dominio posterior aplica.
- **Atributos:** valor cerrado del catálogo (unifamiliar aislada/pareada/entre medianeras, plurifamiliar, rehabilitación, terciario, dotacional).
- **Relaciones:** determinada por/asociada a Proyecto arquitectónico; condiciona qué Constraint aplica a Pieza, Itinerario, Núcleo húmedo en prácticamente todos los dominios normativos.
- **Sinónimos:** ninguno preciso.
- **Concepto padre:** ninguno.
- **Conceptos hijo:** ninguno (los valores del catálogo cerrado no son, en sí mismos, sub-conceptos con relaciones propias, son valores de un mismo atributo).
- **Ejemplos:** "plurifamiliar", "unifamiliar aislada", "rehabilitación integral".
- **Contraejemplos:** el uso de una Pieza individual (dormitorio, cocina) no es Tipología edificatoria — Tipología opera a nivel de Proyecto/Edificio, no de pieza.
- **Ambigüedades:** es, según `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 2, el concepto de mayor impacto en cascada si se declara mal — ninguna ambigüedad conceptual propia, pero la mayor sensibilidad de toda la ontología a un error de declaración (el propio Bug #1 vive exactamente aquí).
- **Cómo reconocerlo automáticamente:** **no reconocible desde la geometría del DXF bajo ninguna circunstancia** — es, por diseño, un dato declarado explícitamente por el Arquitecto vía formulario, nunca inferido. Cualquier intento de "adivinar" la tipología a partir del número de unidades detectadas sería exactamente el tipo de inferencia no verificada que `FACT_MODEL.md` §1 prohíbe.

---

## Familia C — Elementos espaciales interiores

### C.1 Pieza

- **Definición:** superficie delimitada dentro de una Unidad de uso o de una Zona común, con un uso asignado, reconocible como una unidad espacial propia dentro de la distribución.
- **Atributos:** superficie, geometría del polígono, uso asignado, altura libre.
- **Relaciones:** pertenece a Unidad de uso (o a Zona común); delimitada por Partición; puede darse a Fachada, a Patio, o a otra Pieza.
- **Sinónimos:** estancia (ver ambigüedad — este documento los trata como sinónimos plenos, resolviendo la redundancia que se planteaba entre ambos, ver "Redundancias resueltas" #2), habitación (uso coloquial).
- **Concepto padre:** ninguno propio a este nivel — es el concepto base de la Familia C.
- **Conceptos hijo:** Pieza habitable (C.2), Pieza no habitable (C.3).
- **Ejemplos:** un dormitorio, un salón, un baño, un trastero.
- **Contraejemplos:** un hueco de escalera o un patio de luces, aunque tengan un polígono cerrado propio y superficie medible, no son Pieza en el sentido pleno del término — se modelan como conceptos propios (Escalera, Patio) precisamente porque su naturaleza funcional es distinta, aunque geométricamente el parser los capture con el mismo mecanismo.
- **Ambigüedades:** el límite entre Pieza y Zona común cuando un espacio (un vestíbulo amplio, por ejemplo) sirve simultáneamente a una función de paso y de estancia — casos reales frecuentes que no siempre tienen una clasificación única y objetiva.
- **Cómo reconocerlo automáticamente:** con fiabilidad alta hoy — es, literalmente, lo que `parser.py` ya extrae: toda polilínea cerrada del layer `"00 areas"` cuyo color DXF es `BYLAYER_COLOR` (no un contorno agrupador de color ACI 10/150), con su uso tomado del `MTEXT` más cercano.

### C.2 Pieza habitable

- **Definición:** Pieza destinada a la permanencia de personas, sujeta a mínimos normativos de superficie, iluminación y ventilación natural.
- **Atributos:** los de Pieza, más su condición de sujeción a normativa de habitabilidad.
- **Relaciones:** especializa a Pieza; sujeta a Constraint de Dominios 3, 4, 7.
- **Sinónimos:** ninguno adicional a los ya listados en Pieza.
- **Concepto padre:** Pieza.
- **Conceptos hijo:** ninguno modelado con nombre propio en esta versión (dormitorio, salón, cocina son valores del atributo "uso", no sub-conceptos con relaciones propias).
- **Ejemplos:** dormitorio, salón, cocina.
- **Contraejemplos:** un trastero interior sin ventana no es Pieza habitable, aunque tenga superficie y uso asignado — está exenta, por naturaleza, de los mínimos de iluminación/ventilación natural.
- **Ambigüedades:** un office o una cocina sin ventana en algunas tipologías puede o no considerarse habitable según el decreto autonómico aplicable — la respuesta depende del Constraint vigente, no es una propiedad fija del concepto.
- **Cómo reconocerlo automáticamente:** la Pieza en sí se reconoce como en C.1; si es habitable o no depende del uso leído del `MTEXT` comparado contra un catálogo cerrado de usos habitables — mecanismo hoy solo parcialmente implementado en `evaluator.py` para un subconjunto de usos conocidos.

### C.3 Pieza no habitable

- **Definición:** Pieza no destinada a la permanencia continuada de personas, exenta de los mínimos de habitabilidad que sí aplican a Pieza habitable.
- **Atributos:** los de Pieza.
- **Relaciones:** especializa a Pieza; puede estar sujeta a Constraint de otros dominios (Dominio 10, Instalaciones) aunque no de habitabilidad.
- **Sinónimos:** ninguno adicional.
- **Concepto padre:** Pieza.
- **Conceptos hijo:** Espacio técnico (C.6) es, en la práctica, el caso más frecuente de este concepto, aunque se modela aparte por su relación funcional distinta con instalaciones.
- **Ejemplos:** trastero, garaje, vestíbulo interior sin ventana.
- **Contraejemplos:** un baño, aunque en algunos casos carezca de ventilación natural (ventilación mecánica), sigue tratándose como Pieza habitable a efectos de superficie mínima en la mayoría de decretos autonómicos — no es automáticamente Pieza no habitable por el mero hecho de no tener hueco.
- **Ambigüedades:** compartida con C.2 — el límite depende del Constraint vigente, no es intrínseco al concepto.
- **Cómo reconocerlo automáticamente:** igual que C.2, mediante el catálogo cerrado de usos aplicado al `MTEXT` asociado.

### C.4 Núcleo húmedo

- **Definición:** Pieza o conjunto de Piezas que concentran instalaciones de fontanería y saneamiento (cocina, baños).
- **Atributos:** posición relativa dentro de la Unidad de uso, coherencia vertical con núcleos húmedos de otras Plantas.
- **Relaciones:** es una especialización funcional de Pieza (cruza con C.2/C.3 según el caso); sirve a Unidad de uso; se apoya en, o condiciona, el trazado de Elemento estructural cuando hay patinillos verticales.
- **Sinónimos:** zona húmeda.
- **Concepto padre:** Pieza (por composición funcional, no por especialización estricta — un núcleo húmedo es, en rigor, una agrupación de Piezas, no una Pieza única).
- **Conceptos hijo:** ninguno.
- **Ejemplos:** el conjunto cocina + baño de una vivienda.
- **Contraejemplos:** un aseo de cortesía aislado, sin relación de apilamiento con otros núcleos húmedos del edificio, se identifica igualmente como Núcleo húmedo aunque no participe en el análisis de coherencia vertical del Dominio 10.
- **Ambigüedades:** el criterio de "cuánta proximidad geométrica" constituye un Núcleo húmedo agrupado frente a piezas húmedas simplemente cercanas por casualidad no está cerrado en ningún documento previo de la serie.
- **Cómo reconocerlo automáticamente:** parcialmente — cada Pieza individual (cocina, baño) se reconoce por C.1; agruparlas en un Núcleo húmedo requiere una heurística de proximidad geométrica entre piezas de uso húmedo, no implementada hoy en `parser.py` ni en `evaluator.py`.

### C.5 Espacio técnico

- **Definición:** Pieza no habitable dedicada específicamente a alojar instalaciones (cuadro eléctrico, sala de máquinas, patinillo registrable).
- **Atributos:** los de Pieza no habitable, más la instalación específica que aloja.
- **Relaciones:** especializa a Pieza no habitable; sirve a Planta o a Edificio completo (a diferencia de Núcleo húmedo, que sirve a una Unidad de uso concreta).
- **Sinónimos:** cuarto de instalaciones.
- **Concepto padre:** Pieza no habitable.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** cuarto de contadores, sala de calderas.
- **Contraejemplos:** un trastero, aunque también sea Pieza no habitable, no es Espacio técnico salvo que aloje instalaciones — la distinción es funcional, no de mero uso "no residencial".
- **Ambigüedades:** ninguna significativa.
- **Cómo reconocerlo automáticamente:** igual que C.3, vía catálogo de usos aplicado al `MTEXT`; hoy sin un valor de catálogo específico y estable para distinguir Espacio técnico de otras Piezas no habitables genéricas en `evaluator.py`.

### C.6 Zona común

- **Definición:** espacio compartido por más de una Unidad de uso dentro de un mismo Edificio, sin asignación de propiedad/uso individual.
- **Atributos:** los de Pieza, más su condición de titularidad compartida.
- **Relaciones:** pertenece a Planta o a Edificio (no a una Unidad de uso concreta); contiene o coincide con elementos de circulación (Familia E).
- **Sinónimos:** elemento común, zona comunitaria.
- **Concepto padre:** ninguno propio — comparte atributos de Pieza pero se distingue por su relación de pertenencia (a Planta/Edificio, no a Unidad de uso), por lo que no se modela como especialización estricta de Pieza sino como concepto emparentado.
- **Conceptos hijo:** ninguno con nombre propio en esta ontología (Escalera, Rellano de la Familia E son, funcionalmente, casos de Zona común, pero se modelan aparte por su papel en circulación).
- **Ejemplos:** portal, rellano de escalera, sala de comunidad.
- **Contraejemplos:** el descansillo interior de una vivienda unifamiliar de dos plantas no es Zona común — pertenece en exclusiva a esa Unidad de uso.
- **Ambigüedades:** el límite entre Zona común y Núcleo húmedo cuando existe un aseo de cortesía en una zona común (frecuente en locales comerciales de uso compartido).
- **Cómo reconocerlo automáticamente:** igual mecanismo que C.1, distinguida de una Unidad de uso por no tener una etiqueta `VT<n>/<m>` asociada — hoy, en la práctica, cualquier Pieza sin etiqueta de vivienda asociada se trata implícitamente como fuera de una unidad, sin una clasificación explícita y positiva de "esto es zona común".

---

## Familia D — Cerramientos, huecos y aberturas

### D.1 Partición

- **Definición:** elemento constructivo vertical que delimita físicamente una Pieza, con o sin función estructural.
- **Atributos:** grosor, composición constructiva (si se conoce), función (portante/no portante).
- **Relaciones:** delimita Pieza; puede sirve_a la compartimentación contra incendio (Sector de incendio, F.2) o acústica entre unidades.
- **Sinónimos:** cerramiento interior, división.
- **Concepto padre:** ninguno propio — raíz de la Familia D junto a Hueco.
- **Conceptos hijo:** Muro de carga (D.2), Tabique (D.3).
- **Ejemplos:** cualquier línea de cerramiento interior de un plano de distribución.
- **Contraejemplos:** una Fachada (D.5), aunque también es un cerramiento vertical, se modela aparte porque su relación (con el exterior, no entre dos Piezas interiores) es de naturaleza distinta.
- **Ambigüedades:** sin datos constructivos, distinguir Muro de carga de Tabique por geometría 2D sola no siempre es fiable (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 11 ya lo señala como limitación estructural).
- **Cómo reconocerlo automáticamente:** **no reconocible hoy** — `parser.py` no extrae líneas de partición como entidades propias; solo reconoce el contorno cerrado que ya delimita cada Pieza como polígono, sin distinguir explícitamente los segmentos de ese polígono que son particiones reales de los que podrían ser, por ejemplo, un límite virtual sin partición física construida.

### D.2 Muro de carga

- **Definición:** Partición con función estructural, que transmite cargas verticales.
- **Atributos:** los de Partición, más su papel en la continuidad estructural vertical entre Plantas.
- **Relaciones:** especializa a Partición; se apoya en Muro de carga de la Planta inferior (Familia F); condiciona la Coherencia estructural del Dominio 11.
- **Sinónimos:** muro portante, muro estructural.
- **Concepto padre:** Partición.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** el muro perimetral de un edificio de carga de fábrica.
- **Contraejemplos:** un muro de gran grosor pero sin continuidad vertical con la planta inferior no debe asumirse Muro de carga solo por su espesor aparente — es, precisamente, el tipo de asunción sin verificar que `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 11 advierte de no convertir en conclusión firme.
- **Ambigüedades:** alta — sin datos de cálculo estructural real, la clasificación Muro de carga vs. Tabique desde un plano de distribución 2D es, en el mejor caso, una hipótesis razonada, nunca un hecho verificado.
- **Cómo reconocerlo automáticamente:** no reconocible con fiabilidad desde el DXF actual; en el mejor de los casos, aproximable por grosor de línea o por capa DXF si el plano de origen usa una convención de capas para diferenciarlo — convención no estandarizada ni verificada hoy en `parser.py`.

### D.3 Tabique

- **Definición:** Partición sin función estructural, de espesor generalmente menor que un Muro de carga.
- **Atributos:** los de Partición.
- **Relaciones:** especializa a Partición.
- **Sinónimos:** tabiquería.
- **Concepto padre:** Partición.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** la división entre dos dormitorios de una misma vivienda.
- **Contraejemplos:** un muro medianero entre dos unidades de uso distintas, aunque geométricamente parezca un tabique, suele exigir tratamiento de Muro de carga o de compartimentación acústica reforzada por su función entre unidades independientes.
- **Ambigüedades:** compartida con D.2.
- **Cómo reconocerlo automáticamente:** igual limitación que D.1/D.2 — no reconocible con fiabilidad desde el DXF actual sin convención de capas adicional.

### D.4 Hueco

- **Definición:** abertura practicada en una Partición o Fachada que permite paso de personas, luz o aire.
- **Atributos:** ancho, altura, superficie, posición.
- **Relaciones:** se abre en Partición o Fachada; da a Pieza, a otra Pieza, o al exterior.
- **Sinónimos:** ninguno genérico — Ventana y Puerta son sus especializaciones con nombre propio.
- **Concepto padre:** ninguno propio — raíz junto a Partición.
- **Conceptos hijo:** Ventana (especialización por función: luz/ventilación), Puerta (especialización por función: paso).
- **Ejemplos:** cualquier ventana o puerta del plano.
- **Contraejemplos:** un hueco de doble altura sin cerramiento (un vacío entre plantas) no es un Hueco en el sentido de este concepto — es una discontinuidad de forjado, ajena a esta familia.
- **Ambigüedades:** una puerta-ventana (balconera) cumple ambas funciones (paso y luz) simultáneamente — el modelo no fuerza una única especialización, un Hueco puede tener ambos roles a la vez.
- **Cómo reconocerlo automáticamente:** **no reconocible hoy** — `parser.py` no extrae huecos como entidades DXF distintas; toda la evaluación de iluminación/ventilación en `evaluator.py` hoy usa un proxy estimado (superficie de fachada × 0,25, ya documentado como Estimation en `UNCERTAINTY_MODEL.md` §4) precisamente *porque* el Hueco real no se reconoce geométricamente.

### D.5 Fachada

- **Definición:** Partición perimetral de un Edificio que separa el interior del exterior o de un Patio.
- **Atributos:** orientación, longitud, superficie total, superficie de Hueco que contiene.
- **Relaciones:** delimita Pieza por su lado exterior; contiene Hueco; determina Orientación de las Piezas que da_a ella.
- **Sinónimos:** cerramiento exterior.
- **Concepto padre:** Partición (comparte su naturaleza de cerramiento vertical, aunque con relación al exterior en vez de entre dos Piezas — se trata como concepto emparentado, no como especialización estricta, por esa diferencia de naturaleza de la relación que delimita).
- **Conceptos hijo:** ninguno.
- **Ejemplos:** la fachada principal de un edificio a vial.
- **Contraejemplos:** el muro perimetral de un Patio interior no orientado a vial ni a espacio público es, funcionalmente, una Fachada (delimita interior/exterior de la pieza) aunque coloquialmente no se le llame así — este documento lo trata como Fachada a todos los efectos de reglas de iluminación/ventilación.
- **Ambigüedades:** el límite entre "Fachada a patio" y "Fachada a vial" tiene reglas normativas distintas de dimensión mínima de patio, exactamente la distinción que `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 4 ya exige.
- **Cómo reconocerlo automáticamente:** no reconocible como entidad propia hoy; el proxy actual (§ D.4) trata el perímetro exterior del polígono de Pieza como fachada implícita para el cálculo de superficie de hueco estimada, sin identificar tramos de fachada como elementos propios ni su orientación real (que depende del parámetro "norte_grados" declarado por formulario, no de reconocimiento geométrico).

### D.6 Patio

- **Definición:** espacio abierto no edificado, delimitado total o parcialmente por Fachada, que proporciona luz y/o ventilación a las Piezas que dan a él.
- **Atributos:** superficie, dimensión mínima (ancho/diámetro inscrito), altura del edificio que vierte a él.
- **Relaciones:** delimitado por Fachada; recibe Hueco de las Piezas que da_a él.
- **Sinónimos:** patio de luces, patio de ventilación (distinción funcional, no siempre exigida en el mismo espacio físico).
- **Concepto padre:** ninguno propio.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** un patio interior de manzana o un patio de luces individual de una vivienda.
- **Contraejemplos:** una terraza, aunque también sea un espacio abierto no edificado en contacto con Pieza, no es un Patio a efectos normativos — su función y su régimen de cómputo de superficie son distintos.
- **Ambigüedades:** patios mancomunados entre parcelas colindantes (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 4 §8) son, explícitamente, un caso sin respuesta correcta automática.
- **Cómo reconocerlo automáticamente:** parcialmente — un Patio puede aparecer como un polígono más en el layer `"00 areas"` con un `MTEXT` de uso "patio" si el plano de origen lo etiqueta así (mismo mecanismo que C.1); no hay hoy una verificación geométrica independiente de que ese polígono cumpla la definición funcional de Patio (delimitado por fachada, no edificado) más allá de confiar en la etiqueta declarada en el propio DXF.

---

## Familia E — Circulación

### E.1 Itinerario

- **Definición:** secuencia continua de espacios y elementos de paso que conecta dos puntos de un Edificio.
- **Atributos:** ancho mínimo a lo largo de todo su recorrido, longitud total, continuidad (verificada extremo a extremo, no por tramos).
- **Relaciones:** conecta Pieza con Pieza (o con el exterior); atraviesa Pasillo, Rellano, Escalera.
- **Sinónimos:** recorrido (genérico — evitar como sinónimo pleno de Recorrido de evacuación, que es una especialización con régimen propio, ver E.3).
- **Concepto padre:** ninguno propio — raíz de la Familia E.
- **Conceptos hijo:** Itinerario accesible (E.2), Recorrido de evacuación (E.3).
- **Ejemplos:** el camino desde el acceso del edificio hasta la puerta de una vivienda concreta.
- **Contraejemplos:** un Pasillo aislado, sin verificar que conecta dos puntos relevantes de principio a fin, no constituye por sí solo un Itinerario completo — `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 5 ya señala la verificación de continuidad extremo a extremo como el punto más frecuente de fallo real.
- **Ambigüedades:** ninguna propia a este nivel genérico.
- **Cómo reconocerlo automáticamente:** **no reconocible como elemento propio hoy** — no existe en `parser.py` ni en `evaluator.py` un modelo de grafo de circulación conectado; la circulación se infiere, cuando se infiere, a partir de adyacencia geométrica entre polígonos de Pieza (mecanismo ya usado para adyacencia acústica en `evaluator._is_adjacent`), no como un itinerario verificado de punto a punto.

### E.2 Itinerario accesible

- **Definición:** Itinerario que cumple, en toda su longitud, los mínimos de ancho, pendiente y espacio de giro exigidos por la normativa de accesibilidad.
- **Atributos:** los de Itinerario, más el cumplimiento verificado tramo a tramo de los mínimos de accesibilidad.
- **Relaciones:** especializa a Itinerario; puede coincidir parcialmente, o no, con Recorrido de evacuación (tensión estructural ya documentada en `CHAIN_REASONING.md` §5).
- **Sinónimos:** ninguno adicional.
- **Concepto padre:** Itinerario.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** el itinerario desde el acceso hasta una vivienda que cumple ancho mínimo 1,20 m en todo su recorrido.
- **Contraejemplos:** un itinerario que cumple el ancho mínimo en el 90% de su recorrido pero se estrecha en un solo punto no es un Itinerario accesible — la exigencia es de continuidad completa, no de cumplimiento mayoritario.
- **Ambigüedades:** ninguna adicional a las ya heredadas de Itinerario.
- **Cómo reconocerlo automáticamente:** no reconocible hoy por la misma razón que E.1 — requiere el mismo grafo de circulación conectado, todavía no modelado.

### E.3 Recorrido de evacuación

- **Definición:** Itinerario por el que los ocupantes de un Edificio deben poder alcanzar una salida de emergencia en caso de incendio, dentro de una longitud máxima normativa.
- **Atributos:** los de Itinerario, más ocupación que sirve, longitud máxima admisible según número de salidas alternativas disponibles.
- **Relaciones:** especializa a Itinerario; puede tensionar con Itinerario accesible (mismo espacio disputado); atraviesa Sector de incendio.
- **Sinónimos:** recorrido de evacuación (sin sinónimos coloquiales relevantes).
- **Concepto padre:** Itinerario.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** el recorrido desde la pieza más alejada de una planta hasta la escalera protegida más cercana.
- **Contraejemplos:** la distancia en línea recta teórica entre dos puntos no es el Recorrido de evacuación — debe medirse sobre la geometría real transitable, tal como ya señala `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 6 §5.
- **Ambigüedades:** el cómputo de ocupación combinado en edificios de uso mixto (§8 del mismo dominio) admite más de un criterio razonable.
- **Cómo reconocerlo automáticamente:** no reconocible hoy, misma limitación de grafo de circulación que E.1-E.2.

### E.4 Escalera

- **Definición:** elemento constructivo de circulación vertical que conecta Plantas mediante peldaños.
- **Atributos:** ancho, número de tramos, protección contra incendio (protegida/no protegida/especialmente protegida).
- **Relaciones:** conecta Planta con Planta; forma parte de Itinerario y de Recorrido de evacuación; se apoya en Elemento estructural.
- **Sinónimos:** caja de escalera (cuando incluye su recinto de compartimentación).
- **Concepto padre:** ninguno propio.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** la escalera principal de un edificio plurifamiliar.
- **Contraejemplos:** una rampa, aunque cumpla función de circulación vertical, no es una Escalera — tiene régimen y geometría propios.
- **Ambigüedades:** ninguna significativa.
- **Cómo reconocerlo automáticamente:** parcialmente reconocible por polígono en `"00 areas"` con `MTEXT` de uso "escalera" si el plano lo etiqueta así (mismo mecanismo que C.1); su geometría interna de peldaños no se reconoce ni es necesaria para el uso actual del dato.

### E.5 Rellano

- **Definición:** superficie horizontal de descanso o distribución situada al final de un tramo de Escalera o entre plantas.
- **Atributos:** superficie, ancho.
- **Relaciones:** pertenece a Zona común; conecta Escalera con Pieza de acceso a las Unidades de uso de esa Planta.
- **Sinónimos:** descansillo.
- **Concepto padre:** ninguno propio — emparentado con Zona común (C.6) por su relación de pertenencia.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** el rellano al que abren las puertas de dos viviendas en una misma planta.
- **Contraejemplos:** el propio tramo de peldaños de la Escalera no es Rellano — Rellano es, específicamente, la superficie de descanso horizontal.
- **Ambigüedades:** ninguna significativa.
- **Cómo reconocerlo automáticamente:** igual mecanismo parcial que E.4, dependiente de etiquetado explícito en el DXF de origen.

### E.6 Pasillo

- **Definición:** Pieza de circulación horizontal, alargada, que conecta otras Piezas dentro de una misma Unidad de uso o Zona común.
- **Atributos:** ancho, longitud.
- **Relaciones:** especializa a Pieza (por delimitación) y forma parte de Itinerario (por función); conecta Pieza con Pieza.
- **Sinónimos:** distribuidor (cuando cumple función adicional de reparto a varias piezas a la vez).
- **Concepto padre:** Pieza no habitable (comparte su exención de mínimos de iluminación/ventilación en la mayoría de los casos, aunque su régimen de ancho mínimo es propio de circulación, no de habitabilidad).
- **Conceptos hijo:** ninguno.
- **Ejemplos:** el pasillo que conecta el salón con los dormitorios de una vivienda.
- **Contraejemplos:** un vestíbulo de entrada amplio que también sirve de zona de estar no es un Pasillo puro — mismo tipo de ambigüedad ya señalada en C.1 entre Pieza y Zona común.
- **Ambigüedades:** compartida con C.1.
- **Cómo reconocerlo automáticamente:** igual mecanismo que C.1, distinguido por el valor de uso "pasillo"/"distribuidor" en el `MTEXT` asociado, ya usado hoy por `evaluator.py` para el bloque de ancho mínimo de pasillo.

---

## Familia F — Estructura y compartimentación

### F.1 Elemento estructural

- **Definición:** componente constructivo cuya función es transmitir cargas — soportes verticales (pilares, muros de carga) y elementos horizontales (vigas, forjados).
- **Atributos:** tipo (pilar/viga/forjado/muro de carga), posición, continuidad vertical con el elemento equivalente de la Planta adyacente.
- **Relaciones:** se apoya en Elemento estructural de la Planta inferior; condiciona la distribución de Pieza y el trazado de Itinerario.
- **Sinónimos:** elemento portante.
- **Concepto padre:** ninguno propio — Muro de carga (D.2) es, a la vez, una Partición (Familia D) y un Elemento estructural (Familia F); se modela con doble pertenencia deliberada, no como error de clasificación — un mismo elemento físico puede pertenecer legítimamente a dos familias de esta ontología a la vez cuando cumple dos funciones distintas.
- **Conceptos hijo:** Pilar, Viga, Forjado (valores del atributo "tipo", no sub-conceptos con relaciones propias distintas en esta versión).
- **Ejemplos:** un pilar de hormigón visible en dos plantas consecutivas en la misma posición.
- **Contraejemplos:** un Tabique (D.3), por definición, no es Elemento estructural.
- **Ambigüedades:** alta — ver D.2; sin cálculo real, la clasificación de qué es y qué no es Elemento estructural desde un plano 2D de distribución es, en el mejor caso, una lectura razonada, nunca un hecho verificado (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 11 §10).
- **Cómo reconocerlo automáticamente:** no reconocible con fiabilidad desde el DXF actual; requiere, como mínimo, geometría de más de una Planta para verificar continuidad vertical — dato no disponible en el flujo actual de un único DXF por análisis.

### F.2 Sector de incendio

- **Definición:** porción de un Edificio delimitada por elementos de compartimentación con resistencia al fuego suficiente para contener la propagación de un incendio dentro de sus límites durante un tiempo normativo.
- **Atributos:** superficie, uso, resistencia al fuego de su compartimentación perimetral (EI).
- **Relaciones:** delimitado por Compartimentación (F.3); contiene una o más Unidad de uso o Zona común; determina la longitud máxima admisible de Recorrido de evacuación dentro de sus límites.
- **Sinónimos:** ninguno preciso.
- **Concepto padre:** ninguno propio.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** cada planta de un edificio residencial plurifamiliar constituye, habitualmente, un sector de incendio propio.
- **Contraejemplos:** una Unidad de uso individual no es, por sí sola, un Sector de incendio salvo que su compartimentación perimetral cumpla la resistencia exigida de forma verificada — no se asume automáticamente por coincidir con los límites de una vivienda.
- **Ambigüedades:** el cómputo de sectorización en edificios de uso mixto (residencial + terciario en planta baja) admite más de un criterio razonable, mismo caso ya señalado en E.3.
- **Cómo reconocerlo automáticamente:** **no reconocible en absoluto desde un DXF de distribución 2D** — exige datos de composición constructiva (resistencia EI de cada partición) que el plano de distribución no contiene por definición; es, estructuralmente, el concepto de esta ontología con el techo de reconocimiento automático más bajo, junto con D.2.

### F.3 Compartimentación

- **Definición:** conjunto de elementos constructivos (Partición, forjado) que, por su resistencia al fuego o su aislamiento acústico, separan dos ámbitos que deben permanecer independientes entre sí ante fuego o ruido.
- **Atributos:** resistencia al fuego (EI) o aislamiento acústico (dB) según la función que cumple, ámbitos que separa.
- **Relaciones:** delimita Sector de incendio; se materializa a través de Partición.
- **Sinónimos:** ninguno preciso — se usa a veces "cerramiento cortafuegos" para el caso específico de resistencia al fuego.
- **Concepto padre:** ninguno propio.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** la partición entre dos Unidades de uso independientes, con resistencia al fuego y aislamiento acústico reforzados por su condición de separar unidades distintas.
- **Contraejemplos:** un Tabique interior de una misma Unidad de uso, sin exigencia de resistencia al fuego ni aislamiento acústico reforzado, no constituye Compartimentación en el sentido normativo de este concepto.
- **Ambigüedades:** ninguna significativa más allá de la ya heredada de Partición sobre su composición constructiva real.
- **Cómo reconocerlo automáticamente:** no reconocible desde el DXF; depende de datos constructivos no disponibles, misma limitación que F.2 y D.1-D.3.

---

## Familia G — Magnitudes y cualidades medibles

### G.1 Superficie útil

- **Definición:** superficie interior de una Pieza o Unidad de uso, medida al paramento interior de sus Particiones, excluyendo el grosor de los muros.
- **Atributos:** valor en m², método de cómputo (según decreto autonómico aplicable, que puede variar en el tratamiento de elementos con altura reducida).
- **Relaciones:** atributo medible de Pieza y de Unidad de uso (agregación de las superficies útiles de sus Piezas).
- **Sinónimos:** ninguno pleno (ver "Superficie habitable" en la revisión final, redundancia #3).
- **Concepto padre:** ninguno propio — magnitud, no objeto espacial.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** la superficie útil de un dormitorio medida al paramento interior de sus cuatro tabiques.
- **Contraejemplos:** Superficie construida (G.2) no es Superficie útil — incluye el grosor de particiones y elementos estructurales.
- **Ambigüedades:** el tratamiento de piezas bajo cubierta con altura variable (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 3 §7) sigue reglas de cómputo específicas y distintas según decreto autonómico.
- **Cómo reconocerlo automáticamente:** con fiabilidad alta hoy — es, directamente, el área del polígono cerrado que `parser.py` ya extrae por Pieza (vía `shapely`), sin necesidad de mecanismo adicional.

### G.2 Superficie construida

- **Definición:** superficie total de una Pieza, Unidad de uso o Planta, medida al perímetro exterior de sus cerramientos, incluyendo el grosor de particiones y elementos estructurales.
- **Atributos:** valor en m².
- **Relaciones:** atributo medible de Unidad de uso y Planta; limitada por Edificabilidad (A.3) a nivel de conjunto del Proyecto.
- **Sinónimos:** ninguno preciso.
- **Concepto padre:** ninguno propio.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** la superficie construida de una vivienda, mayor que su superficie útil por el grosor de sus tabiques y muros perimetrales.
- **Contraejemplos:** Superficie útil (G.1) no es intercambiable con esta — es sistemáticamente menor.
- **Ambigüedades:** ninguna adicional.
- **Cómo reconocerlo automáticamente:** **no reconocible con precisión hoy** — como las particiones (D.1) no se reconocen como entidades propias, calcular la superficie construida exige conocer el grosor real de los cerramientos perimetrales, dato que el parser actual no extrae; el eficiencia útil/construida que hoy calcula `evaluator.py` depende de un dato de superficie construida declarado, no derivado geométricamente con la misma fiabilidad que la superficie útil.

### G.3 Ancho de paso

- **Definición:** dimensión mínima libre, medida perpendicularmente a la dirección de circulación, disponible en un punto concreto de un Itinerario, Pasillo o Hueco de paso.
- **Atributos:** valor en metros, punto de medición concreto dentro del recorrido.
- **Relaciones:** atributo medible de Pasillo, Itinerario, Puerta.
- **Sinónimos:** ancho libre.
- **Concepto padre:** ninguno propio.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** el ancho libre de 0,85 m en el punto más estrecho de un pasillo.
- **Contraejemplos:** el ancho nominal de diseño de un elemento no es el Ancho de paso real si existe una obstrucción puntual (un radiador, una columna) que lo reduce en la práctica — el concepto se refiere siempre al mínimo real, no al proyectado sin obstrucciones.
- **Ambigüedades:** en piezas de geometría irregular, "el ancho" puede no tener un único criterio de medición universal, mismo caso ya señalado en `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 3 §8.
- **Cómo reconocerlo automáticamente:** parcialmente — medible geométricamente sobre el polígono de una Pieza reconocida (C.1/E.6) mediante cálculo de anchura mínima del polígono, ya aplicado en `evaluator.py` para algunos bloques; no verifica obstrucciones puntuales no representadas como parte del propio polígono.

### G.4 Altura libre

- **Definición:** distancia vertical entre el pavimento terminado y la cara inferior del forjado o elemento que lo cubre, en un punto de una Pieza.
- **Atributos:** valor en metros, variable si la Pieza tiene techo inclinado o forjado no horizontal.
- **Relaciones:** atributo medible de Pieza y de Planta.
- **Sinónimos:** ninguno preciso.
- **Concepto padre:** ninguno propio.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** 2,50 m de altura libre mínima exigida en pieza habitable.
- **Contraejemplos:** la altura total del edificio (relevante para A.5 y para el Dominio 1) no es Altura libre — son magnitudes de escalas distintas (planta individual vs. edificio completo).
- **Ambigüedades:** el cómputo de superficie útil bajo cubierta inclinada depende directamente de la Altura libre variable, con reglas específicas por decreto autonómico (ya señalado en G.1).
- **Cómo reconocerlo automáticamente:** **no reconocible desde un DXF 2D de planta** — la altura libre es un dato de sección vertical, no de planta; hoy no forma parte de ningún dato extraído por `parser.py`, es un valor declarado o asumido por defecto normativo, nunca observado geométricamente en el flujo actual.

### G.5 Orientación

- **Definición:** dirección cardinal a la que da una Fachada o el Hueco principal de una Pieza, referida al norte geográfico real del emplazamiento.
- **Atributos:** ángulo respecto al norte geográfico.
- **Relaciones:** atributo de Fachada; condiciona la evaluación de Dominio 8 (Térmica) y Dominio 4 (Iluminación) sobre las Piezas que da_a esa fachada.
- **Sinónimos:** ninguno preciso.
- **Concepto padre:** ninguno propio.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** "fachada orientada a sureste".
- **Contraejemplos:** el ángulo del norte del propio DXF (referido a los ejes de dibujo, no al norte geográfico real) no es, por sí solo, Orientación — requiere el dato declarado "norte_grados" para convertirse en una orientación real interpretable.
- **Ambigüedades:** ninguna conceptual — el riesgo real no es de ambigüedad de definición sino de depender enteramente de un dato declarado correctamente (si el arquitecto introduce mal el ángulo de norte, toda Orientación derivada es incorrecta sin que el sistema pueda, por sí solo, detectarlo).
- **Cómo reconocerlo automáticamente:** calculable, no observable — se deriva combinando la geometría de la Fachada (hoy no reconocida como entidad propia, ver D.5) con el parámetro "norte_grados" ya recibido por formulario; es, en la práctica actual, un cálculo que depende de una aproximación mayor (perímetro exterior del polígono de Pieza) más que de una Fachada real identificada.

---

## Familia H — Contexto normativo y climático

### H.1 Zona climática

- **Definición:** clasificación del territorio español, codificada por letra y número (CTE DB-HE), según su severidad climática de invierno y verano, que determina las exigencias de comportamiento térmico de la envolvente.
- **Atributos:** letra (A-E, severidad de invierno) y número (severidad de verano).
- **Relaciones:** se deriva de Ámbito territorial normativo (H.2) mediante una tabla de referencia (ciudad → zona); condiciona Constraint del Dominio 8 sobre Fachada y Hueco.
- **Sinónimos:** ninguno preciso.
- **Concepto padre:** ninguno propio.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** "zona climática C1".
- **Contraejemplos:** la Comunidad autónoma no es, por sí sola, la Zona climática — dentro de una misma comunidad autónoma pueden coexistir varias zonas climáticas distintas según el municipio (España tiene relieve y clima muy heterogéneos incluso dentro de una misma región administrativa).
- **Ambigüedades:** ninguna conceptual — el riesgo real es, exactamente, el ya confirmado como Bug #1 en `TECH_REVIEW.md`: que este valor no llegue correctamente desde el dato declarado hasta las reglas que lo necesitan.
- **Cómo reconocerlo automáticamente:** calculable con fiabilidad alta a partir del dato "ciudad" declarado por formulario, vía la tabla de referencia ya existente en `analyzer/cte_zonas.py` (`get_zona_cte`) — no es un dato observado del DXF, es un Fact derivado de un dato declarado mediante una función de composición ya real y en producción.

### H.2 Ámbito territorial normativo

- **Definición:** división administrativa (estatal, autonómica, municipal) que determina qué conjunto de normativa aplica a un Proyecto según su ubicación.
- **Atributos:** nivel (estatal/autonómico/municipal), identificador de la división concreta (nombre de comunidad autónoma, municipio).
- **Relaciones:** se ubica_en jerárquicamente (estatal contiene autonómico contiene municipal); determina qué Fuente normativa (H.3) es aplicable a cada Constraint.
- **Sinónimos:** jurisdicción normativa (uso poco frecuente en el dominio).
- **Concepto padre:** ninguno propio.
- **Conceptos hijo:** ninguno con nombre propio (Comunidad autónoma y Municipio son valores del atributo "nivel", no sub-conceptos con relaciones distintas en esta versión).
- **Ejemplos:** "Comunidad de Madrid" como ámbito autonómico.
- **Contraejemplos:** la Zona climática (H.1), aunque se deriva de la ubicación, no es en sí misma un Ámbito territorial normativo — es una clasificación técnica derivada de él, con su propia lógica de fronteras que no coincide con las administrativas.
- **Ambigüedades:** ninguna conceptual relevante.
- **Cómo reconocerlo automáticamente:** el dato de ciudad se recibe declarado por formulario, no reconocido geométricamente; derivar de él la Comunidad autónoma correspondiente es una función de composición trivial, hoy no verificada como existente de forma explícita y separada en el código (se infiere implícitamente junto con la zona climática, sin un Fact propio de "comunidad autónoma" documentado).

### H.3 Fuente normativa

- **Definición:** documento legal o técnico concreto (artículo de CTE, decreto autonómico, ordenanza municipal) del que se deriva la exigencia de un Constraint.
- **Atributos:** identificador exacto (código de DB, número de artículo/decreto), ámbito territorial de aplicación, vigencia temporal.
- **Relaciones:** justifica Constraint (`CONSTRAINT_MODEL.md` §8); aplicable dentro de un Ámbito territorial normativo (H.2).
- **Sinónimos:** cita normativa, referencia legal.
- **Concepto padre:** ninguno propio.
- **Conceptos hijo:** ninguno.
- **Ejemplos:** "CTE DB-SUA, sección 1, artículo 4".
- **Contraejemplos:** un criterio profesional sin respaldo legal (Nivel 3 de `ARCHITECTURAL_KNOWLEDGE_MAP.md`) no es una Fuente normativa en sentido estricto, aunque `CONSTRAINT_MODEL.md` §8 exige citarlo igualmente con el mismo tratamiento visual ("criterio profesional: [documento/guía]") — se incluye aquí como concepto porque el mecanismo de cita es el mismo aunque la naturaleza de la fuente sea distinta.
- **Ambigüedades:** cuando una misma restricción tiene fuente estatal y autonómica simultáneas (`CONSTRAINT_MODEL.md` §13), ambas son Fuente normativa válida a la vez, sin que una "sustituya" a la otra en la trazabilidad.
- **Cómo reconocerlo automáticamente:** no reconocible desde ningún dato de proyecto — es, por naturaleza, un dato de catálogo mantenido por el Curador de Conocimiento (`CONSTRAINT_MODEL.md` §8), nunca derivado del DXF ni del formulario.

---

## Revisión final — inconsistencias y conceptos redundantes

Cierre explícito, tal como se pidió: una revisión honesta de dónde esta ontología, tal como está escrita arriba, tiene solape real — no una lista de que "todo está bien".

### Redundancias resueltas

**1. Edificabilidad (A.3) vs. Aprovechamiento urbanístico (A.4).** Es el solape más real de toda la ontología. La distinción formal (ratio general del planeamiento vs. derecho ya calculado sobre una parcela concreta con cesiones descontadas) es correcta y tiene valor técnico para el Dominio 1 en casos con cesiones obligatorias — pero en la inmensa mayoría de los proyectos reales que ArchMuse va a evaluar (parcelas urbanas consolidadas sin cesión pendiente), los dos valores coinciden numéricamente y la distinción no aporta nada observable. **Recomendación:** mantener los dos conceptos definidos (la distinción es correcta cuando aplica), pero no crear dos Fact independientes por defecto — Aprovechamiento urbanístico debería tratarse como un Fact derivado de Edificabilidad (`FACT_MODEL.md` §4, composición pura) que solo diverge de su fuente cuando existe una cesión declarada, nunca como dos datos que un Curador de Conocimiento tenga que mantener por separado desde el principio.

**2. Pieza (C.1) vs. Estancia.** Se declaran sinónimos plenos en la propia definición de C.1, no dos conceptos. Se nombra aquí explícitamente porque el encargo pedía identificar redundancias y esta es la más obvia de resolver: "estancia" no necesita entrada propia en el diccionario canónico de `EXPLANATION_ENGINE.md` §2 — cualquier Explanation debe usar siempre "pieza", nunca alternar entre los dos términos, exactamente la misma disciplina de vocabulario único que ese documento ya exige para evitar que 14 dominios describan el mismo Fact con sinónimos distintos.

**3. Superficie útil (G.1) vs. "Superficie habitable".** Este documento define solo Superficie útil y deliberadamente no da entrada propia a "superficie habitable" como concepto distinto — en el uso profesional español, "superficie habitable" se emplea unas veces como sinónimo exacto de superficie útil y otras como "superficie útil de las piezas habitables únicamente, excluyendo piezas no habitables computables" (un subconjunto, no un sinónimo). Esta ambigüedad de uso real es la razón exacta por la que este documento no la trata como concepto propio: cualquier Constraint que necesite el segundo significado debe expresarse como una Superficie útil (G.1) restringida por AGREGACION_AMBITO (`CONSTRAINT_MODEL.md` §3.1) sobre el subconjunto de Pieza habitable (C.2), nunca inventando un tercer concepto de superficie con nombre propio.

### Inconsistencia estructural señalada, no resuelta aquí

**Doble pertenencia de Muro de carga (D.2).** Se declara, en F.1, que Muro de carga pertenece simultáneamente a la Familia D (Partición) y a la Familia F (Elemento estructural) — una excepción deliberada a que cada concepto tenga una familia de pertenencia clara. Es la decisión correcta (el elemento físico real cumple ambas funciones a la vez) pero es la única ruptura de la organización por familias de todo el documento, y debe tratarse como tal si en el futuro se automatiza cualquier consulta "dame todos los conceptos de la Familia F" — esa consulta debe saber que tiene que buscar también D.2, no asumir que las 8 familias son una partición estricta y disjunta del catálogo completo de conceptos.

### El hallazgo más importante de esta revisión: el mapa de qué es reconocible automáticamente hoy es mucho más pequeño que el mapa de qué existe conceptualmente

De los 42 conceptos, solo **9** (Pieza, Pieza habitable/no habitable en su versión básica, Vivienda, Zona común de forma parcial, Ancho de paso de forma parcial, Superficie útil, Zona climática, Ámbito territorial normativo) tienen un mecanismo de reconocimiento automático real y en producción hoy, vía `parser.py`/`evaluator.py`/`cte_zonas.py`. Otros **6** (Patio, Escalera, Rellano, Pasillo, Espacio técnico, Orientación) son parcialmente reconocibles, dependientes de que el DXF de origen use una convención de etiquetado que no está garantizada. Los **27 restantes** — toda la Familia A (marco territorial), toda la Familia D salvo Fachada de forma aproximada, toda la Familia F, Superficie construida, Altura libre, Tipología (por diseño, nunca automática) — **no son reconocibles desde el flujo de datos actual bajo ninguna circunstancia**, no por una limitación de esta ontología sino porque el DXF de distribución 2D, tal como se procesa hoy, no contiene esa información. Esta proporción (9 de 42 reconocibles, ~21%) es, probablemente, el dato más útil de todo este documento para decidir qué Dominios de `BRAIN_ARCHITECTURE.md` son viables con el pipeline de datos actual y cuáles requieren, antes que más diseño de reglas, una fuente de datos distinta (BIM/IFC, ya apuntado como dirección estratégica en `NORTH_STAR_2031.md`) — no más ingeniería de reconocimiento de patrones sobre un DXF 2D que, estructuralmente, no lleva esa información.
