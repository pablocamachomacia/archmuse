# SPACE_TAXONOMY.md

**Propósito:** la taxonomía completa de tipos de espacio arquitectónico sobre la que ArchMuse debe poder clasificar cualquier pieza de un proyecto con un vocabulario único y consistente — el catálogo cerrado de valores de "uso" que `ARCHITECTURAL_ONTOLOGY.md` (§C.1-C.3) ya anticipaba como necesario y dejaba sin enumerar ("un catálogo cerrado de usos... hoy solo parcialmente implementado"). Este documento lo cierra. Sin código, como el resto de la serie.

**Referencias obligatorias, asumidas como ya decididas:**
- `ARCHITECTURAL_ONTOLOGY.md` — Familia C (Pieza C.1, Pieza habitable C.2, Pieza no habitable C.3, Núcleo húmedo C.4, Espacio técnico C.5, Zona común C.6), Familia D (Fachada D.5, Patio D.6), Familia E (Pasillo E.6). Este documento no redefine ninguno de esos conceptos — los especializa en tipos concretos con nombre propio. Reutiliza también, sin cambios, el vocabulario cerrado de relaciones (§0.1 de ese documento: contiene/pertenece a, delimita, da a/se abre a, sirve a/servido por, conecta con, se apoya en, se ubica en) para la columna "relaciones funcionales" de cada tipo — no se inventa un vocabulario de relaciones nuevo.
- `ARCHITECTURAL_KNOWLEDGE_MAP.md` — Dominio 3 (superficies/anchos mínimos), Dominio 4 (iluminación/ventilación), Dominio 5 (accesibilidad), Dominio 7 (acústica, adyacencias críticas), Dominio 9 (calidad espacial, jerarquía servido/servidor).
- `CONSTRAINT_MODEL.md` §10-12 — uso, tipología y contexto como ejes de una tabla de resolución de parámetros; el catálogo de tipos de este documento es, precisamente, el conjunto de valores válidos que ese eje "uso" puede tomar.
- `CHAIN_REASONING.md` §5 — los pares de tensión estructural entre dominios (accesibilidad vs. superficie, luz vs. térmica...), reutilizados aquí a nivel de pieza concreta en la columna "incompatibilidades".
- Grounding real: `analyzer/evaluator.py` — hoy reconoce, exclusivamente, seis patrones de uso sobre el `MTEXT` normalizado de cada Pieza: `SALON|COCINA` (fusionados en un único tipo, umbral 20,0 m²), `DORMITORIO\s*1` (10,0 m²), `DORMITORIO\s*2` (8,0 m²), `DORMITORIO\s*3` (6,0 m²), `BANO` (3,0 m²), `ASEO` (1,5 m²), más `PASILLO` (sin umbral de superficie, evaluado por ancho) y `TERRAZA|TENDEDERO` (excluido del cómputo de superficie útil). Este es el vocabulario real en producción hoy — una fracción pequeña del catálogo completo que sigue. Se declara aquí, una sola vez, para no repetirlo en cada entrada y para que la brecha entre "lo que existe en el código" y "lo que define esta taxonomía" quede explícita desde el principio, no descubierta al final.

---

## 0. Cómo está organizado este documento

**9 categorías, 29 tipos de espacio con nombre propio.** Cada tipo se define con los 8 campos pedidos: definición, variantes, usos compatibles, incompatibilidades, relaciones funcionales, requisitos normativos habituales, requisitos de calidad, errores frecuentes de clasificación. Los "requisitos normativos habituales" son valores orientativos de referencia — como ya advierte `ARCHITECTURAL_KNOWLEDGE_MAP.md` en su nota inicial, la cifra exacta debe verificarse siempre contra el `Constraint` vigente, nunca darse aquí como definitiva; donde el valor coincide con un umbral real ya en producción en `evaluator.py`, se cita explícitamente como tal.

### 0.1 Catálogo cerrado de tipos de incompatibilidad

Igual que `ARCHITECTURAL_ONTOLOGY.md` cerró su vocabulario de relaciones, la columna "incompatibilidades" de cada tipo usa siempre uno de estos cuatro valores — nunca una incompatibilidad libre redactada distinta para cada caso:

| Tipo | Significado |
|---|---|
| **Acústica** | La adyacencia entre este tipo y otro genera riesgo de aislamiento insuficiente (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 7) |
| **Funcional** | Los dos usos compiten por el mismo espacio o por el mismo elemento de servicio de forma que degradan mutuamente su función |
| **Normativa** | La combinación viola directamente un mínimo exigido (superficie, iluminación, evacuación) si se fusionan o se sustituyen entre sí sin más |
| **De privacidad** | La adyacencia o visibilidad mutua compromete la intimidad de una pieza que normativamente o por criterio de calidad la requiere |

---

## Categoría 1 — Piezas habitables principales

### 1.1 Salón / Estar

- **Definición:** pieza habitable destinada a la vida social y de estar de la vivienda, sin función de dormir ni de cocinar.
- **Variantes:** salón simple; salón de doble altura (poco frecuente en vivienda plurifamiliar); salón con zona de estudio integrada (sin partición, no constituye Despacho aparte, ver 1.5).
- **Usos compatibles:** puede fusionarse funcionalmente con Comedor (→ Salón-comedor, 1.3) y, en plantas abiertas, con Cocina americana (2.2) sin partición — en ese caso es una única Pieza con uso compuesto, no tres piezas superpuestas.
- **Incompatibilidades:** Acústica, si es adyacente a un Dormitorio sin refuerzo de partición (uso diurno ruidoso junto a uso nocturno silencioso).
- **Relaciones funcionales:** sirve a Vivienda como pieza principal (jerarquía servido/servidor); da a Fachada o Patio preferentemente en orientación sur/suroeste; conecta con Vestíbulo/Recibidor (4.1) y con Distribuidor (4.2).
- **Requisitos normativos habituales:** superficie mínima de referencia 20,0 m² cuando se computa junto con Cocina (umbral real ya en `evaluator.py` para el patrón fusionado `SALON|COCINA`); iluminación/ventilación natural obligatoria (Dominio 4); es, junto con Dormitorio 1, la pieza que determina la jerarquía espacial mínima de la vivienda (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 9).
- **Requisitos de calidad:** debe ser, salvo justificación, la pieza de mayor superficie de la vivienda (jerarquía servido/servidor, Kahn — ya citada en `ARCHITECTURAL_QUALITY.md` §1); orientación preferente sur/suroeste; relación visual directa con el exterior más allá del mínimo normativo de hueco.
- **Errores frecuentes de clasificación:** confundir un Salón con un Distribuidor amplio que además alberga mobiliario de estar — el criterio de desambiguación es si la pieza es, principalmente, un espacio de permanencia (Salón) o de paso (Distribuidor, 4.2), no su superficie ni su forma.

### 1.2 Comedor

- **Definición:** pieza habitable, o zona de una pieza mayor, destinada específicamente a la actividad de comer en mesa formal, distinta de Cocina.
- **Variantes:** comedor independiente (pieza propia, hoy poco frecuente en vivienda de superficie media/reducida); zona de comedor integrada en Salón (→ Salón-comedor, 1.3, el caso dominante).
- **Usos compatibles:** con Salón (fusión funcional habitual, ver 1.3); con Cocina en modelos de "cocina-comedor" de superficie reducida.
- **Incompatibilidades:** Funcional, con Cocina cuando ambas compiten por el mismo espacio de forma que ninguna alcanza su superficie de referencia por separado, sin declararse expresamente como una única pieza fusionada.
- **Relaciones funcionales:** sirve a Vivienda; conecta con Cocina (2.1/2.2) por proximidad funcional directa.
- **Requisitos normativos habituales:** sin umbral propio y diferenciado en la mayoría de decretos autonómicos — normalmente absorbido dentro del cómputo de Salón o de Salón-comedor.
- **Requisitos de calidad:** proximidad directa a Cocina, sin recorrido largo ni cruce por otras piezas; relación visual con Salón si están fusionados.
- **Errores frecuentes de clasificación:** tratar un Comedor independiente como una pieza distinta a efectos de superficie mínima cuando el decreto autonómico aplicable lo computa junto con Salón — genera un doble cómputo o un déficit aparente que no es real.

### 1.3 Salón-comedor

- **Definición:** pieza habitable única que fusiona, sin partición interna, las funciones de Salón (1.1) y Comedor (1.2) — la variante dominante en vivienda plurifamiliar de superficie media.
- **Variantes:** salón-comedor simple; salón-comedor-cocina (planta completamente abierta, fusión de las tres funciones, ver 2.2).
- **Usos compatibles:** con Cocina americana (2.2), fusión total en planta abierta.
- **Incompatibilidades:** ninguna propia distinta de las ya heredadas de Salón (1.1).
- **Relaciones funcionales:** sirve a Vivienda como pieza principal; hereda las relaciones de 1.1 y 1.2 combinadas.
- **Requisitos normativos habituales:** el umbral de referencia de 20,0 m² del patrón `SALON|COCINA` de `evaluator.py` corresponde, en la práctica, a este caso — el propio nombre del patrón ya asume la fusión salón/cocina como el caso normal, no como una excepción.
- **Requisitos de calidad:** los de 1.1, con el matiz de que la fusión debe mantener una jerarquía interna legible (zona de estar diferenciada de zona de mesa) aunque no exista partición física — un espacio "genérico" sin ninguna organización interna es, según `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 9, un síntoma de calidad espacial baja aunque cumpla superficie.
- **Errores frecuentes de clasificación:** **este es, hoy, el error más real y ya presente en el código de producción — no un caso hipotético.** `evaluator.py` fusiona `SALON` y `COCINA` bajo un único patrón (`SALON|COCINA`) y un único umbral, lo que significa que el sistema real no distingue hoy entre un Salón-comedor con Cocina independiente (dos piezas reales, cada una con su propio umbral y sus propios requisitos de iluminación/ventilación) y un verdadero Salón-comedor-cocina en planta abierta (una sola pieza). Si el DXF de origen etiqueta ambas piezas por separado ("SALON" y "COCINA" en polígonos distintos), el patrón actual las trataría como dos coincidencias del mismo umbral en vez de aplicar el umbral correcto y distinto que le correspondería a cada una si `evaluator.py` las tratara como los tipos 1.1 y 2.1 de esta taxonomía, separados.

### 1.4 Dormitorio

- **Definición:** pieza habitable destinada al descanso, con exigencia de privacidad y de aislamiento acústico frente al resto de la vivienda.
- **Variantes:** dormitorio principal/doble (el de mayor superficie, habitualmente con baño en suite o vestidor asociado); dormitorio individual; dormitorio infantil (sin régimen normativo distinto, pero con criterio de calidad propio de proximidad a dormitorio principal). **Convención real del proyecto:** el DXF de referencia y `evaluator.py` no etiquetan por rol (principal/individual) sino por número — "Dormitorio 1" > "Dormitorio 2" > "Dormitorio 3" — con la jerarquía de superficie ya verificada por el sistema (`evaluate_dormitorio_hierarchy`, umbrales reales 10,0 / 8,0 / 6,0 m²); esta taxonomía trata "Dormitorio 1" como equivalente funcional del dormitorio principal, sin que ambas nomenclaturas sean, formalmente, el mismo concepto (ver "errores frecuentes" más abajo).
- **Usos compatibles:** con Vestidor (4.3) anexo sin partición completa, cuando forma parte del mismo ámbito de la unidad.
- **Incompatibilidades:** Acústica, adyacente a Escalera, Ascensor o Espacio técnico (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 7 §5); De privacidad, adyacente a Zona común con visibilidad directa desde hueco.
- **Relaciones funcionales:** sirve a Vivienda; conecta con Distribuidor (4.2), nunca directamente con Vestíbulo de acceso sin pasar por un elemento de circulación intermedio (criterio de calidad, no exigencia normativa universal); puede servirse de Baño (3.1) en suite.
- **Requisitos normativos habituales:** superficie mínima jerarquizada por posición (10,0 / 8,0 / 6,0 m², umbrales reales de `evaluator.py`); iluminación/ventilación natural obligatoria; orientación óptima este/sur, penalizada a norte (ya evaluado en `evaluator.py` vía `evaluate_orientation`).
- **Requisitos de calidad:** proporción no alargada ("pieza tubo", ya cubierta como heurística en `analyzer/spatial_quality.py`); distancia razonable desde el acceso de la vivienda (`evaluate_entry_distance` ya existente); privacidad respecto a Salón y a Zona común.
- **Errores frecuentes de clasificación:** confundir la numeración "Dormitorio 1/2/3" (jerarquía de superficie, orden descendente) con un rol funcional fijo ("Dormitorio 1 = principal siempre") — ambas cosas suelen coincidir mas no son, por definición, el mismo criterio; un dormitorio etiquetado "Dormitorio 2" podría, en un proyecto concreto, ser el dormitorio principal si el arquitecto decidió numerarlos en otro orden, y el sistema no tiene hoy ningún mecanismo para verificarlo más allá de la superficie.

### 1.5 Despacho / Estudio

- **Definición:** pieza habitable destinada a trabajo o estudio individual, sin función de dormir.
- **Variantes:** despacho independiente (pieza propia); zona de estudio integrada sin partición en Salón (no constituye tipo propio, se trata como parte de 1.1).
- **Usos compatibles:** con Dormitorio, cuando un dormitorio de superficie amplia integra una zona de trabajo sin partición — no cambia su clasificación como Dormitorio.
- **Incompatibilidades:** ninguna propia relevante.
- **Relaciones funcionales:** sirve a Vivienda; conecta con Distribuidor.
- **Requisitos normativos habituales:** sin umbral normativo propio en la mayoría de decretos de habitabilidad — cuando existe como pieza independiente, suele evaluarse con los mismos mínimos que un Dormitorio secundario por similitud dimensional, no por régimen normativo propio distinto.
- **Requisitos de calidad:** buena iluminación natural (mayor peso relativo que en un dormitorio, por la actividad que aloja); aislamiento acústico si es adyacente a Zona común ruidosa.
- **Errores frecuentes de clasificación:** clasificar automáticamente una pieza de superficie similar a un dormitorio pequeño como Dormitorio por defecto cuando su etiqueta real dice "despacho" o "estudio" — un sistema que solo mira superficie sin mirar la etiqueta comete este error con frecuencia; es, estructuralmente, el mismo riesgo que `FACT_MODEL.md` §1 nombra como "nunca inventar un hecho": el uso de una pieza es un dato declarado (vía etiqueta), nunca inferido solo de su geometría.

---

## Categoría 2 — Cocina y anexos

### 2.1 Cocina independiente

- **Definición:** pieza habitable, con partición completa respecto al resto de la vivienda, destinada a la preparación de alimentos.
- **Variantes:** cocina independiente cerrada (partición completa, puerta); cocina independiente con paso abierto parcial (partición incompleta, no llega a ser Cocina americana, 2.2).
- **Usos compatibles:** con Comedor de superficie reducida integrado (→ "cocina-comedor", ver 1.2).
- **Incompatibilidades:** Acústica, si es adyacente a Dormitorio sin refuerzo (electrodomésticos, fontanería); Normativa, respecto a Núcleo húmedo (`ARCHITECTURAL_ONTOLOGY.md` C.4) — comparte régimen de instalaciones pero no de habitabilidad.
- **Relaciones funcionales:** sirve a Vivienda; conecta con Comedor y con Lavadero/Tendedero (2.4); se apoya, junto con Baño, en la coherencia vertical de instalaciones entre Plantas (`ARCHITECTURAL_ONTOLOGY.md` Familia F).
- **Requisitos normativos habituales:** cuando se computa por separado de Salón (no es el caso más habitual en el corpus actual, ver 1.3), superficie mínima de referencia en el rango de 7-8 m² según decreto autonómico; ventilación obligatoria (natural o mecánica según normativa vigente).
- **Requisitos de calidad:** proximidad a Comedor y a acceso de servicio si existe; ubicación coherente con la coherencia vertical de Núcleo húmedo entre plantas.
- **Errores frecuentes de clasificación:** ver 1.3 — el error dominante hoy es no distinguirla en absoluto de Salón cuando ambas comparten el mismo patrón de reconocimiento.

### 2.2 Cocina americana / abierta

- **Definición:** Cocina sin partición completa respecto a Salón o Salón-comedor, integrada visual y funcionalmente en un espacio mayor.
- **Variantes:** con isla o barra de separación funcional sin partición física; totalmente integrada sin ningún elemento de separación.
- **Usos compatibles:** fusión plena con Salón-comedor (1.3).
- **Incompatibilidades:** Acústica, con Dormitorio adyacente, agravada respecto a Cocina independiente por la ausencia de partición que en la cocina cerrada sí mitigaría parte del ruido.
- **Relaciones funcionales:** las mismas que 2.1, heredadas, más las de 1.3 por fusión.
- **Requisitos normativos habituales:** cuando fusionada con Salón, el umbral de referencia es el conjunto (20,0 m², patrón `SALON|COCINA` de `evaluator.py`), no un mínimo propio y distinto de Cocina.
- **Requisitos de calidad:** ventilación mecánica de extracción reforzada, por la ausencia de partición que en cocina cerrada contendría olores/humedad; iluminación natural compartida con Salón, sin exigir hueco propio.
- **Errores frecuentes de clasificación:** tratarla como una pieza (Fact/Pieza) distinta de Salón cuando, geométricamente, es el mismo polígono sin subdivisión — el sistema no debe intentar "separar" en dos piezas un espacio que el propio plano no separa; la fusión debe reconocerse como tal, no forzarse a la taxonomía cerrada de 1.1+2.1 por separado.

### 2.3 Office

- **Definición:** pieza pequeña anexa a Cocina, destinada a comida informal o a tareas domésticas ligeras, sin ser Comedor formal.
- **Variantes:** office con mesa integrada; office de paso sin mobiliario de estar (más próximo, en ese caso, a Distribuidor, 4.2).
- **Usos compatibles:** con Lavadero/Tendedero (2.4), cuando comparte espacio.
- **Incompatibilidades:** Funcional, con Comedor si ambos existen en la misma vivienda de superficie reducida y compiten redundantemente por la misma función.
- **Relaciones funcionales:** sirve a Cocina (2.1); conecta con Comedor si existe.
- **Requisitos normativos habituales:** sin umbral propio en la mayoría de decretos — se computa habitualmente como parte de la superficie de Cocina si no está delimitado como pieza independiente.
- **Requisitos de calidad:** proximidad directa a Cocina, sin recorrido intermedio.
- **Errores frecuentes de clasificación:** confundirlo con un Distribuidor (4.2) cuando su función real es de paso, no de estar — el criterio de desambiguación (igual que en 1.1) es la presencia declarada de mobiliario de estar/comida en el uso, no solo la superficie o proporción de la pieza.

### 2.4 Lavadero / Tendedero

- **Definición:** pieza o espacio, interior o exterior, destinado a lavado y secado de ropa.
- **Variantes:** lavadero interior cerrado (Pieza no habitable computable como superficie construida, no siempre como útil); tendedero exterior (terraza de servicio, excluida del cómputo de superficie útil).
- **Usos compatibles:** con Cocina (proximidad funcional por instalaciones de fontanería compartidas).
- **Incompatibilidades:** Normativa, si se pretende computar su superficie como útil cuando el decreto autonómico lo excluye explícitamente (caso del tendedero exterior).
- **Relaciones funcionales:** sirve a Vivienda; se apoya en la misma coherencia vertical de instalaciones que Cocina y Núcleo húmedo.
- **Requisitos normativos habituales:** el tendedero exterior está expresamente excluido del cómputo de superficie útil en el criterio ya aplicado por `evaluator.py` (patrón `TERRAZA|TENDEDERO`, mismo criterio que Terraza, 5.1).
- **Requisitos de calidad:** ventilación directa al exterior (evita humedad residual); proximidad a Cocina.
- **Errores frecuentes de clasificación:** computar un Tendedero exterior como superficie útil de la vivienda — es, precisamente, el error que el patrón `NON_USEFUL_PATTERN` de `evaluator.py` ya existe para prevenir; un sistema nuevo que reimplemente este criterio sin conocer esa exclusión ya validada reintroduciría un error ya resuelto.

---

## Categoría 3 — Piezas húmedas

### 3.1 Baño completo

- **Definición:** Pieza habitable-húmeda (`ARCHITECTURAL_ONTOLOGY.md` C.4) con inodoro, lavabo y ducha/bañera, destinada a aseo personal completo.
- **Variantes:** baño en suite (anexo directo a Dormitorio principal, 1.4); baño principal compartido; baño accesible/adaptado (ver 3.3, especialización normativa, no un tipo distinto de espacio).
- **Usos compatibles:** ninguno — es, por naturaleza, monofuncional.
- **Incompatibilidades:** Acústica, adyacente a Dormitorio o a Salón sin refuerzo de partición (instalaciones, descarga de cisterna); De privacidad, si su hueco (cuando lo tiene) da directamente a Zona común con visibilidad.
- **Relaciones funcionales:** sirve a Vivienda o, en variante suite, específicamente a un Dormitorio; se apoya en la coherencia vertical de Núcleo húmedo entre Plantas.
- **Requisitos normativos habituales:** superficie mínima de referencia 3,0 m² (umbral real de `evaluator.py`, patrón `BANO`); espacio de giro mínimo de accesibilidad exigido en al menos un baño de la vivienda (`evaluate_bathroom_accessibility` ya en producción); relación mínima dormitorios/baños ya verificada (`evaluate_bathroom_ratio`: 1-2 dormitorios → mínimo 1 baño; 3+ dormitorios → además mínimo 1 aseo en tipología plurifamiliar).
- **Requisitos de calidad:** ventilación mecánica o natural fiable, sin depender de un patio de dimensión mínima ajustada; proximidad razonable a los Dormitorios a los que sirve.
- **Errores frecuentes de clasificación:** confundir Baño con Aseo (3.2) por similitud de etiqueta o de uso — la distinción real no es de nombre sino de programa (presencia o ausencia de ducha/bañera), y ambos tienen umbrales de superficie muy distintos (3,0 m² vs. 1,5 m² en los valores ya en producción) — tratarlos como intercambiables produciría falsos incumplimientos o falsos cumplimientos según qué patrón se aplique al que no corresponde.

### 3.2 Aseo

- **Definición:** Pieza habitable-húmeda con inodoro y lavabo, sin ducha ni bañera — "medio baño".
- **Variantes:** aseo de cortesía en Zona común (uso compartido, no vinculado a una Vivienda concreta); aseo vinculado a una Vivienda.
- **Usos compatibles:** ninguno.
- **Incompatibilidades:** las mismas de 3.1, heredadas.
- **Relaciones funcionales:** sirve a Vivienda (o a Zona común en su variante de cortesía); se apoya en la misma coherencia vertical que Baño.
- **Requisitos normativos habituales:** superficie mínima de referencia 1,5 m² (umbral real de `evaluator.py`, patrón `ASEO`); exigido como pieza adicional solo en tipología plurifamiliar con 3+ dormitorios (criterio real ya aplicado, `strict=True` en `evaluate_bathroom_ratio` — en unifamiliar/rehabilitación un único Baño compartido es aceptable sin Aseo adicional).
- **Requisitos de calidad:** proximidad a Zona común de la vivienda (Salón), no a los Dormitorios — a diferencia de Baño, cuya proximidad de calidad prioritaria es a los dormitorios a los que sirve.
- **Errores frecuentes de clasificación:** ver 3.1 — mismo riesgo de intercambio con Baño; también, exigir el Aseo adicional en una vivienda unifamiliar de 3+ dormitorios sin comprobar la tipología primero repetiría, en sentido inverso, el mismo patrón del Bug #1 (aplicar una regla de plurifamiliar a un proyecto que no lo es).

### 3.3 Baño accesible / adaptado

- **Definición:** especialización normativa de Baño (3.1), no un tipo de espacio distinto: un Baño que cumple, además de los mínimos generales, el espacio de giro y las dimensiones exigidas por accesibilidad universal.
- **Variantes:** ninguna adicional.
- **Usos compatibles:** los de Baño.
- **Incompatibilidades:** las de Baño.
- **Relaciones funcionales:** especializa a Baño (3.1); su exigencia se satisface con que exista al menos uno por vivienda, no todos (criterio ya aplicado: `has_accessible_bathroom=any(...)`).
- **Requisitos normativos habituales:** espacio de giro mínimo de accesibilidad (CTE DB-SUA); no exige superficie mínima distinta de Baño, sino una geometría interna concreta compatible con el giro.
- **Requisitos de calidad:** ubicación en planta accesible del itinerario, no solo cumplimiento geométrico interno aislado (coherente con `ARCHITECTURAL_ONTOLOGY.md` E.2, verificación de continuidad extremo a extremo).
- **Errores frecuentes de clasificación:** tratarlo como un tipo de pieza con etiqueta propia distinta de "Baño" — no lo es; es un atributo de cumplimiento sobre una instancia concreta de 3.1, y modelarlo como un tipo aparte en el catálogo duplicaría innecesariamente la taxonomía (mismo tipo de redundancia ya señalado en `ARCHITECTURAL_ONTOLOGY.md`, sección de revisión final).

---

## Categoría 4 — Piezas no habitables de la vivienda

### 4.1 Vestíbulo / Recibidor

- **Definición:** Pieza no habitable de transición inmediata entre el acceso de la Vivienda y el resto de su distribución interior.
- **Variantes:** vestíbulo simple de paso; vestíbulo con función de armario/guardarropa integrado.
- **Usos compatibles:** con Distribuidor (4.2), cuando no hay una separación funcional clara entre ambos.
- **Incompatibilidades:** Funcional, si se pretende que sirva simultáneamente como único itinerario accesible y como zona de estar/comedor de facto.
- **Relaciones funcionales:** sirve a Vivienda como primer punto de la circulación interior; conecta la puerta de acceso con Distribuidor, Salón o Cocina.
- **Requisitos normativos habituales:** ancho mínimo de paso, mismo régimen que Distribuidor (4.2) si forma parte del itinerario interior.
- **Requisitos de calidad:** debe evitar la visión directa hacia Dormitorios o Baño desde la puerta de entrada (privacidad); tamaño proporcionado, ni residual ni sobredimensionado (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 9, "espacio residual sin uso claro").
- **Errores frecuentes de clasificación:** confundirlo con Distribuidor cuando ambos aparecen en el mismo plano sin partición — la distinción tiene valor conceptual (el vestíbulo es el punto de llegada, el distribuidor es el eje de reparto interior) pero no siempre una frontera geométrica clara; cuando el DXF no los separa, deben tratarse como una única Pieza con el uso más restrictivo aplicable, no forzar una subdivisión que el plano no tiene.

### 4.2 Distribuidor / Pasillo

- **Definición:** Pieza no habitable de circulación horizontal que conecta otras Piezas dentro de la misma Unidad de uso — especializa directamente a Pasillo (`ARCHITECTURAL_ONTOLOGY.md` E.6), sin añadir un concepto nuevo.
- **Variantes:** pasillo lineal simple; distribuidor central (reparte a varias piezas desde un único punto, geometría más compacta que un pasillo lineal).
- **Usos compatibles:** con Vestíbulo (4.1), ver arriba.
- **Incompatibilidades:** Normativa, si su ancho cae por debajo del mínimo exigido en cualquier tramo de su recorrido (no solo en el promedio).
- **Relaciones funcionales:** conecta Pieza con Pieza; forma parte de Itinerario y, potencialmente, de Recorrido de evacuación (`ARCHITECTURAL_ONTOLOGY.md` E.1/E.3).
- **Requisitos normativos habituales:** ancho mínimo de paso ya evaluado en producción (`evaluate_hallway_width`, CTE DB-SUA); es, además, el ámbito de referencia para el proxy de "recorrido entrada→dormitorio" ya calculado (`evaluate_entry_distance`).
- **Requisitos de calidad:** longitud contenida, sin recorridos innecesariamente largos que reduzcan la eficiencia útil/construida de la vivienda; proporción no excesivamente estrecha respecto a su longitud (heurística de "pieza tubo" no aplicable en sentido negativo aquí, porque es, precisamente, su función ser alargado — la heurística de proporción de `spatial_quality.py` debe excluir explícitamente este tipo, no aplicarlo con el mismo criterio que a un Dormitorio).
- **Errores frecuentes de clasificación:** aplicar la heurística de proporción "pieza tubo" (pensada para Dormitorio/Salón) a un Distribuidor, que por definición y correctamente es alargado — es un ejemplo concreto de por qué el uso de la pieza tiene que condicionar qué reglas de calidad se le aplican, nunca aplicar el mismo conjunto de heurísticas a toda Pieza indiscriminadamente.

### 4.3 Vestidor

- **Definición:** Pieza no habitable destinada al almacenamiento de ropa y objetos personales, anexa habitualmente a un Dormitorio.
- **Variantes:** vestidor cerrado con partición completa; vestidor abierto integrado en el propio Dormitorio (en ese caso no constituye Pieza aparte).
- **Usos compatibles:** con Dormitorio (1.4), como anexo.
- **Incompatibilidades:** Normativa, si su superficie se computa erróneamente como parte de la superficie mínima habitable del Dormitorio al que sirve, cuando el decreto autonómico aplicable la excluye por ser pieza no habitable.
- **Relaciones funcionales:** sirve a Dormitorio.
- **Requisitos normativos habituales:** sin mínimo de superficie propio en la mayoría de decretos — su existencia es de calidad, no de obligación.
- **Requisitos de calidad:** proximidad y conexión directa con el Dormitorio al que sirve, sin atravesar otras piezas.
- **Errores frecuentes de clasificación:** confundirlo con un Dormitorio secundario pequeño por similitud de superficie — la distinción depende del uso declarado (ausencia de ventana exigida, ausencia de función de descanso), no de la geometría; un vestidor sin hueco al exterior es perfectamente válido, un dormitorio sin hueco no lo es, y confundir ambos en una u otra dirección produce un incumplimiento fabricado o un incumplimiento real no detectado.

### 4.4 Trastero (vinculado a vivienda)

- **Definición:** Pieza no habitable destinada a almacenamiento general, vinculada como anexo a una Vivienda, dentro o fuera de su envolvente directa.
- **Variantes:** trastero interior a la propia vivienda; trastero vinculado en planta distinta (sótano, por ejemplo) — en ese caso pertenece a otra Unidad de uso a efectos de Planta pero conserva su vínculo de titularidad con la Vivienda.
- **Usos compatibles:** ninguno particular.
- **Incompatibilidades:** Normativa, si se computa como superficie útil habitable cuando el régimen aplicable lo excluye.
- **Relaciones funcionales:** sirve a Vivienda, aunque no pertenezca_a su misma Planta necesariamente.
- **Requisitos normativos habituales:** sin mínimo de habitabilidad (no es Pieza habitable); puede tener normativa propia de ventilación mínima si su uso incluye almacenamiento de ciertos materiales, caso poco relevante en vivienda residencial estándar.
- **Requisitos de calidad:** proximidad razonable a la vivienda a la que sirve si está en planta distinta (accesibilidad de uso cotidiano).
- **Errores frecuentes de clasificación:** tratarlo como parte de la misma Unidad de uso (misma Vivienda como contenedor físico) cuando en realidad pertenece a otra Planta — la relación de servicio ("sirve a" esta Vivienda) no es lo mismo que la relación de contención física (`ARCHITECTURAL_ONTOLOGY.md` §0.1), y confundir ambas produce un cómputo de superficie de la vivienda incorrecto.

---

## Categoría 5 — Espacios exteriores vinculados a la unidad

### 5.1 Terraza

- **Definición:** espacio exterior abierto, vinculado a una Vivienda, con acceso directo desde una Pieza habitable interior, no computable como superficie útil interior.
- **Variantes:** terraza de uso general (estar exterior); terraza de servicio (tendedero, ver 2.4, tratado como caso especializado).
- **Usos compatibles:** con Salón (acceso directo habitual).
- **Incompatibilidades:** Normativa, si se pretende computar su superficie como útil sin la reducción de coeficiente que la mayoría de decretos autonómicos exige para superficies exteriores.
- **Relaciones funcionales:** se abre desde Salón o Dormitorio; da a Fachada exterior o a Patio.
- **Requisitos normativos habituales:** excluida del cómputo de superficie útil en el criterio real ya aplicado por `evaluator.py` (patrón `TERRAZA|TENDEDERO`, mismo tratamiento que 2.4).
- **Requisitos de calidad:** orientación favorable (sur/suroeste preferente, mismo criterio que Salón); proporción utilizable, no residual.
- **Errores frecuentes de clasificación:** confundirla con Balcón (5.2) — la distinción real es de escala y de uso (la Terraza admite mobiliario de estar exterior con normalidad, el Balcón es, típicamente, un espacio de tránsito o de permanencia puntual) más que una frontera normativa única; en la práctica, ambas comparten el mismo tratamiento de exclusión de superficie útil, por lo que el error de clasificación entre ambas rara vez cambia el resultado normativo, aunque sí afecta a la narrativa de calidad.

### 5.2 Balcón

- **Definición:** espacio exterior abierto de reducida profundidad, en voladizo o retranqueado, vinculado a una Pieza habitable, sin la escala suficiente para uso de estar exterior pleno.
- **Variantes:** balcón corrido (varias piezas); balcón individual por pieza.
- **Usos compatibles:** con Dormitorio o Salón.
- **Incompatibilidades:** las mismas de Terraza, heredadas.
- **Relaciones funcionales:** las mismas de Terraza, heredadas.
- **Requisitos normativos habituales:** los mismos de Terraza; puede tener, además, régimen propio de barandilla/protección (Dominio 5/6, seguridad de personas, fuera del alcance normativo de habitabilidad puro).
- **Requisitos de calidad:** los mismos de Terraza, con expectativa de escala menor.
- **Errores frecuentes de clasificación:** ver 5.1.

### 5.3 Patio privativo

- **Definición:** especialización de Patio (`ARCHITECTURAL_ONTOLOGY.md` D.6) de uso y titularidad exclusivos de una Vivienda concreta, típicamente en planta baja.
- **Variantes:** ninguna adicional a las ya cubiertas por Patio en general.
- **Usos compatibles:** con Salón o Dormitorio de planta baja (acceso directo).
- **Incompatibilidades:** las mismas heredadas de Patio (D.6).
- **Relaciones funcionales:** especializa a Patio; sirve a una única Vivienda, a diferencia del Patio de manzana o Patio de luces compartido, que sirve_a varias.
- **Requisitos normativos habituales:** los de Patio (D.6), con el matiz de que su titularidad exclusiva no lo exime de las dimensiones mínimas si otras piezas (de otras viviendas) también dan a él, aunque no lo usen en exclusiva.
- **Requisitos de calidad:** privacidad respecto a parcelas o patios colindantes.
- **Errores frecuentes de clasificación:** asumir que, por ser "privativo", queda exento de las reglas dimensionales de Patio compartido — la exigencia dimensional depende de a cuántas piezas y de cuántas viviendas sirve como fuente de luz/ventilación, no de su régimen de titularidad.

### 5.4 Porche / Solana

- **Definición:** espacio exterior cubierto pero no cerrado lateralmente (o parcialmente cerrado), vinculado a una Vivienda, de transición entre interior y Terraza/Patio.
- **Variantes:** porche de acceso (vinculado al Vestíbulo); solana de estar (vinculada a Salón).
- **Usos compatibles:** con Vestíbulo (4.1) o Salón (1.1) según su posición.
- **Incompatibilidades:** ninguna propia adicional a las de Terraza.
- **Relaciones funcionales:** conecta interior con Terraza/Patio; da a Fachada.
- **Requisitos normativos habituales:** régimen de cómputo similar a Terraza; puede tener tratamiento distinto según el grado real de cerramiento lateral (un porche muy cerrado puede, en algunos decretos, computar de forma distinta a una terraza abierta).
- **Requisitos de calidad:** protección climática razonable sin perder la condición de espacio exterior.
- **Errores frecuentes de clasificación:** clasificarlo como Pieza habitable interior cuando su grado de cerramiento es alto — el criterio de "espacio exterior" no depende solo de tener cubierta, sino de la proporción de cerramiento lateral, un dato que el DXF de planta por sí solo no siempre deja inequívoco.

---

## Categoría 6 — Zonas comunes del edificio

### 6.1 Portal / Vestíbulo de acceso

- **Definición:** Zona común (`ARCHITECTURAL_ONTOLOGY.md` C.6) de acceso principal al Edificio, primer punto de contacto entre el exterior y la circulación vertical.
- **Variantes:** portal simple; portal con conserjería/zona de recepción integrada.
- **Usos compatibles:** con Escalera (6.2) y Ascensor (6.3), como continuación directa de la circulación.
- **Incompatibilidades:** ninguna propia significativa.
- **Relaciones funcionales:** sirve a todas las Unidad de uso del Edificio; conecta el acceso exterior con Escalera y Ascensor.
- **Requisitos normativos habituales:** régimen de accesibilidad reforzado (es, por definición, el primer tramo de cualquier Itinerario accesible del Edificio).
- **Requisitos de calidad:** proporción y luminosidad acordes al rango del edificio; legibilidad clara del acceso a cada núcleo de circulación vertical.
- **Errores frecuentes de clasificación:** confundirlo con Rellano (6.4) de planta baja — el Portal es, específicamente, el punto de contacto con el exterior, mientras que un Rellano es un punto de distribución entre plantas ya dentro del edificio.

### 6.2 Escalera común

- **Definición:** especialización de Escalera (`ARCHITECTURAL_ONTOLOGY.md` E.4) de uso compartido por más de una Unidad de uso.
- **Variantes:** escalera protegida; escalera especialmente protegida (régimen de resistencia al fuego, `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 6).
- **Usos compatibles:** con Ascensor, como circulación vertical alternativa/complementaria.
- **Incompatibilidades:** Funcional, si su ancho o su geometría compiten por el mismo espacio que el Ascensor de forma que ninguno de los dos alcanza su dimensión mínima por separado.
- **Relaciones funcionales:** especializa a Escalera; sirve a todas las Unidad de uso de las Plantas que conecta; forma parte de Recorrido de evacuación.
- **Requisitos normativos habituales:** los de Escalera (E.4), con exigencia añadida de protección contra incendio según el uso y altura de evacuación del Edificio.
- **Requisitos de calidad:** iluminación natural si es posible (escalera con hueco a fachada o patio, valorada positivamente frente a escalera interior ciega).
- **Errores frecuentes de clasificación:** ninguna adicional a las ya heredadas de Escalera.

### 6.3 Ascensor

- **Definición:** Zona común, elemento mecánico de circulación vertical entre Plantas.
- **Variantes:** ascensor accesible (cumple dimensiones de cabina y embarque exigidas); ascensor no accesible (admisible solo en determinados regímenes normativos según número de plantas/viviendas).
- **Usos compatibles:** con Escalera, como par de circulación vertical del Edificio.
- **Incompatibilidades:** Funcional, ver 6.2.
- **Relaciones funcionales:** conecta Planta con Planta; sirve a todas las Unidad de uso.
- **Requisitos normativos habituales:** exigencia de ascensor accesible a partir de determinado número de plantas u ocupantes (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 5).
- **Requisitos de calidad:** proximidad razonable desde Portal.
- **Errores frecuentes de clasificación:** asumir su existencia obligatoria en tipologías (unifamiliar, edificios de pocas plantas) donde la normativa no lo exige — mismo tipo de error de propagación de tipología ya nombrado como Bug #1 en `TECH_REVIEW.md`, aplicado aquí a un elemento concreto en vez de a un umbral numérico.

### 6.4 Rellano

- **Definición:** especialización de Rellano (`ARCHITECTURAL_ONTOLOGY.md` E.5) — se lista aquí por completitud del catálogo de Zona común, sin contenido adicional al ya fijado en la ontología.
- **Variantes:** las ya cubiertas en E.5.
- **Usos compatibles:** con Escalera y Ascensor, como su punto de llegada en cada Planta.
- **Incompatibilidades:** ninguna propia adicional.
- **Relaciones funcionales:** las ya fijadas en E.5.
- **Requisitos normativos habituales:** ancho mínimo de itinerario y de espacio de maniobra ante puertas de Vivienda que abren a él.
- **Requisitos de calidad:** privacidad razonable entre las puertas de las distintas Vivienda que comparten el mismo Rellano.
- **Errores frecuentes de clasificación:** los ya heredados de E.5.

### 6.5 Cuarto de basuras

- **Definición:** Zona común destinada al almacenamiento temporal de residuos del Edificio antes de su recogida.
- **Variantes:** cuarto de basuras interior; punto limpio exterior vinculado.
- **Usos compatibles:** ninguno particular.
- **Incompatibilidades:** Acústica y de privacidad (olores), si es adyacente a Vivienda sin aislamiento adecuado.
- **Relaciones funcionales:** sirve a todas las Unidad de uso del Edificio; se ubica habitualmente en planta baja o sótano, con acceso desde Zona común.
- **Requisitos normativos habituales:** ventilación reforzada; a veces clasificado, según el decreto, como Espacio técnico (7.x) más que como Zona común pura — se mantiene aquí por su naturaleza de servicio compartido, con una nota explícita de doble pertenencia posible.
- **Requisitos de calidad:** alejado de fachadas de piezas habitables y de accesos principales.
- **Errores frecuentes de clasificación:** clasificarlo exclusivamente como Espacio técnico (Categoría 7) ignorando su naturaleza de Zona común de uso compartido por los residentes — a diferencia de un cuarto de instalaciones puro, aquí sí hay uso humano cotidiano, aunque breve.

### 6.6 Sala de comunidad / Zona de ocio común

- **Definición:** Zona común de uso social o recreativo compartido por los residentes del Edificio (sala polivalente, gimnasio comunitario, etc.).
- **Variantes:** sala polivalente; gimnasio; sala infantil.
- **Usos compatibles:** ninguno particular, cada variante suele ser monofuncional.
- **Incompatibilidades:** Acústica, si es adyacente a Vivienda.
- **Relaciones funcionales:** sirve a todas las Unidad de uso del Edificio.
- **Requisitos normativos habituales:** sin régimen normativo propio de habitabilidad (no es Pieza habitable de una Vivienda); sujeta a normativa de pública concurrencia si el aforo lo justifica.
- **Requisitos de calidad:** accesible desde Portal sin atravesar zonas privadas.
- **Errores frecuentes de clasificación:** poco frecuente en proyectos de tamaño medio; el riesgo principal es de omisión (no reconocerla en absoluto si el DXF no la etiqueta con un patrón previsto) más que de confusión con otro tipo.

### 6.7 Zona ajardinada / patio de manzana común

- **Definición:** espacio exterior no edificado de uso y titularidad compartidos por el conjunto de Unidad de uso del Edificio o de varios edificios de la misma Parcela.
- **Variantes:** jardín comunitario; patio de manzana compartido entre parcelas colindantes (caso ya señalado como sin respuesta correcta única en `ARCHITECTURAL_ONTOLOGY.md` D.6).
- **Usos compatibles:** con Patio (D.6) en su función de iluminación/ventilación de piezas que dan a él, si coincide geométricamente.
- **Incompatibilidades:** ninguna propia adicional a las ya heredadas de Patio.
- **Relaciones funcionales:** sirve a todas las Unidad de uso; puede ser, simultáneamente, Patio (D.6) a efectos de iluminación de piezas colindantes.
- **Requisitos normativos habituales:** los de Patio si cumple esa función simultánea; sin régimen propio adicional como zona ajardinada en sí misma en la mayoría de decretos de habitabilidad.
- **Requisitos de calidad:** proporción de superficie ajardinada respecto al total de la parcela, criterio de calidad urbanística más que de habitabilidad de vivienda individual.
- **Errores frecuentes de clasificación:** tratarlo como una entidad distinta de Patio cuando, geométricamente y funcionalmente, cumple exactamente ese papel para las piezas que dan a él — mismo riesgo de duplicación conceptual ya señalado en la revisión final de `ARCHITECTURAL_ONTOLOGY.md`.

---

## Categoría 7 — Espacios técnicos y de instalaciones

### 7.1 Cuarto de contadores

- **Definición:** especialización de Espacio técnico (`ARCHITECTURAL_ONTOLOGY.md` C.5) destinada específicamente a alojar contadores de suministros (agua, electricidad, gas).
- **Variantes:** cuarto de contadores general del Edificio; armario de contadores por Planta.
- **Usos compatibles:** ninguno.
- **Incompatibilidades:** Normativa, respecto a compartimentación contra incendio si su ubicación interfiere con un Sector de incendio o un Recorrido de evacuación (`ARCHITECTURAL_ONTOLOGY.md` F.2/E.3).
- **Relaciones funcionales:** sirve a todas las Unidad de uso del Edificio; se ubica habitualmente próximo al Portal o al acceso.
- **Requisitos normativos habituales:** espacio técnico mínimo dedicado según reglamento de cada suministro (electrotécnico, de agua).
- **Requisitos de calidad:** accesibilidad para mantenimiento sin necesidad de atravesar Vivienda privada.
- **Errores frecuentes de clasificación:** ninguna significativa más allá de la ya heredada de Espacio técnico en general.

### 7.2 Sala de calderas / climatización

- **Definición:** especialización de Espacio técnico destinada a equipos de generación térmica centralizada (calefacción, ACS, climatización).
- **Variantes:** sala de calderas individual por vivienda (poco frecuente en centralizada); sala de calderas centralizada del Edificio.
- **Usos compatibles:** ninguno.
- **Incompatibilidades:** Acústica (vibración de equipos) si es adyacente a Pieza habitable; Normativa, régimen de ventilación y de resistencia al fuego propio del RITE.
- **Relaciones funcionales:** sirve a todas las Unidad de uso, en su variante centralizada; se apoya en la coherencia vertical de patinillos de instalaciones (7.3) para distribuir a cada Planta.
- **Requisitos normativos habituales:** ventilación obligatoria de seguridad (RITE); dimensión mínima según potencia instalada.
- **Requisitos de calidad:** alejada de Dormitorio y Salón por vibración/ruido.
- **Errores frecuentes de clasificación:** subestimar su incompatibilidad acústica por tratarla igual que cualquier otro Espacio técnico genérico — a diferencia de un cuarto de contadores (pasivo, sin vibración), esta sí genera ruido/vibración activos y merece un criterio de adyacencia más estricto.

### 7.3 Patinillo de instalaciones

- **Definición:** conducto vertical registrable que aloja el trazado de instalaciones (fontanería, saneamiento, ventilación, electricidad) entre Plantas.
- **Variantes:** patinillo registrable desde Pieza; patinillo registrable solo desde Zona común.
- **Usos compatibles:** ninguno.
- **Incompatibilidades:** Acústica, con Dormitorio adyacente (fuga acústica ya señalada en `ARCHITECTURAL_ONTOLOGY.md` D.5/`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 7 §6); Normativa, si interrumpe la Compartimentación (`ARCHITECTURAL_ONTOLOGY.md` F.3) de un Sector de incendio sin sellado adecuado.
- **Relaciones funcionales:** conecta Núcleo húmedo de una Planta con el de la Planta adyacente (coherencia vertical); se apoya en la posición de Elemento estructural para no interferir con él.
- **Requisitos normativos habituales:** continuidad vertical exigida por criterio de coherencia de instalaciones (`ARCHITECTURAL_ONTOLOGY.md` Dominio 10, no un umbral dimensional único sino un criterio de posición relativa).
- **Requisitos de calidad:** apilamiento vertical exacto entre plantas consecutivas — su ausencia es, según `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 10, el criterio más determinante y más fácil de verificar sin datos de instalaciones detallados.
- **Errores frecuentes de clasificación:** no es reconocible como polígono propio en el DXF de distribución actual (mismo techo de reconocimiento que Elemento estructural, `ARCHITECTURAL_ONTOLOGY.md` F.1) — el riesgo de clasificación no es de confundirlo con otro tipo, es de que no exista ningún mecanismo hoy para detectarlo en absoluto sin datos de sección o de instalaciones.

---

## Categoría 8 — Aparcamiento

### 8.1 Plaza de garaje

- **Definición:** Pieza no habitable delimitada, destinada al estacionamiento de un vehículo, vinculada habitualmente a una Vivienda o comercializada de forma independiente.
- **Variantes:** plaza estándar; plaza accesible (dimensiones ampliadas de accesibilidad).
- **Usos compatibles:** ninguno.
- **Incompatibilidades:** Normativa, si su superficie se computa erróneamente como parte de la superficie útil habitable de la vivienda a la que está vinculada.
- **Relaciones funcionales:** vinculada a Vivienda (relación de servicio, no de contención física); pertenece a Garaje colectivo (8.2) como contenedor físico.
- **Requisitos normativos habituales:** dimensión mínima de plaza según reglamento local; ancho ampliado en plaza accesible.
- **Requisitos de calidad:** proximidad al núcleo de circulación vertical del Edificio si está vinculada a una Vivienda en planta superior.
- **Errores frecuentes de clasificación:** mismo error de contención-vs-servicio ya señalado en Trastero (4.4) — pertenece físicamente a Garaje colectivo/Planta sótano, no a la Vivienda, aunque le "sirva".

### 8.2 Garaje colectivo

- **Definición:** Planta o parte de Planta destinada en conjunto al aparcamiento de vehículos de varias Unidad de uso.
- **Variantes:** garaje en sótano; garaje en planta baja.
- **Usos compatibles:** con Espacio técnico (instalaciones de ventilación forzada, obligatorias en garaje cerrado).
- **Incompatibilidades:** Normativa, régimen de sectorización contra incendio propio y reforzado (uso de riesgo especial según el CTE); Acústica, si es adyacente a Vivienda en planta superior sin aislamiento a ruido de impacto y vibración.
- **Relaciones funcionales:** contiene Plaza de garaje (8.1); se apoya en Elemento estructural que, a su vez, sostiene las Plantas residenciales superiores.
- **Requisitos normativos habituales:** ventilación forzada obligatoria; sectorización de incendio propia; recorrido de evacuación propio, distinto del de las viviendas.
- **Requisitos de calidad:** rampa de acceso (8.3) sin comprometer la calidad espacial de las plantas residenciales sobre ella.
- **Errores frecuentes de clasificación:** ninguna significativa — es, de los espacios de esta categoría, el de identificación funcional más inequívoca.

### 8.3 Rampa de acceso a garaje

- **Definición:** elemento de circulación vehicular que conecta la rasante exterior con Garaje colectivo (8.2).
- **Variantes:** rampa recta; rampa curva/helicoidal.
- **Usos compatibles:** ninguno.
- **Incompatibilidades:** Normativa, pendiente máxima exigida distinta de cualquier Itinerario peatonal (E.1-E.3), régimen propio de vehículos.
- **Relaciones funcionales:** conecta Parcela (nivel de rasante) con Garaje colectivo.
- **Requisitos normativos habituales:** pendiente máxima según normativa local, distinta de la de rampa peatonal.
- **Requisitos de calidad:** visibilidad de seguridad en el encuentro con la vía pública.
- **Errores frecuentes de clasificación:** aplicarle, por error, los criterios normativos de pendiente de un Itinerario accesible peatonal (E.2) — son regímenes normativos distintos aunque ambos sean "rampas".

---

## Categoría 9 — Locales de uso no residencial

**Nota de alcance:** `PRD-001-Core-Reasoning-Engine.md` limita el MVP a vivienda; esta categoría se incluye por completitud del catálogo, no como prioridad de implementación cercana — coherente con `BRAIN_REVIEW.md`, que ya señaló que ampliar el alcance más allá de lo aprobado es, precisamente, el riesgo a vigilar en esta serie.

### 9.1 Local comercial

- **Definición:** Local (`ARCHITECTURAL_ONTOLOGY.md` B.6) destinado a actividad comercial de cara al público, habitualmente en planta baja.
- **Variantes:** local diáfano; local con entreplanta.
- **Usos compatibles:** ninguno particular a nivel de esta taxonomía (su programa interno es responsabilidad de cada actividad concreta, fuera del alcance de esta ontología residencial).
- **Incompatibilidades:** Acústica, con Vivienda en planta superior si la actividad genera ruido; Normativa, ocupación y evacuación calculadas con criterios de pública concurrencia, distintos de vivienda.
- **Relaciones funcionales:** pertenece a Planta baja habitualmente; conecta con Fachada a vial directamente, sin pasar por Portal residencial.
- **Requisitos normativos habituales:** cómputo de ocupación por superficie y uso comercial (DB-SI), distinto del residencial.
- **Requisitos de calidad:** fuera del alcance de esta taxonomía, orientada a vivienda.
- **Errores frecuentes de clasificación:** aplicarle, por defecto, los umbrales de superficie mínima pensados para Pieza habitable residencial — no le corresponden en absoluto, es un régimen normativo distinto de raíz.

### 9.2 Oficina / uso terciario

- **Definición:** Local destinado a actividad administrativa o profesional, sin atención directa al público en la escala de un comercio.
- **Variantes:** oficina individual; oficina compartida/coworking.
- **Usos compatibles:** ninguno particular a esta taxonomía.
- **Incompatibilidades:** las mismas de Local comercial, heredadas.
- **Relaciones funcionales:** las mismas de Local comercial.
- **Requisitos normativos habituales:** los de uso terciario/administrativo del CTE, distintos de vivienda.
- **Requisitos de calidad:** fuera del alcance de esta taxonomía.
- **Errores frecuentes de clasificación:** los mismos de 9.1.

---

## Errores transversales de clasificación (no ligados a un tipo concreto)

Cinco patrones de error que aparecen repetidos en varias entradas de arriba y merecen nombrarse una vez, de forma consolidada, porque son el verdadero riesgo operativo de este documento — no la falta de cobertura de tipos, sino cómo se aplica mal la cobertura que ya existe:

1. **Inferir el uso desde la geometría en vez de leerlo del dato declarado.** Ya señalado en 1.5 (Despacho vs. Dormitorio) y en 4.3 (Vestidor vs. Dormitorio): el uso de una Pieza es siempre un Fact declarado (etiqueta), nunca una Inference derivada de su superficie o proporción — hacerlo al revés es, estructuralmente, el mismo tipo de fallo que `FACT_MODEL.md` §1 prohíbe para cualquier otro dato.
2. **Aplicar un conjunto de reglas de calidad pensado para un tipo a otro tipo distinto solo porque comparten geometría similar.** El caso de Distribuidor (4.2) frente a la heurística de "pieza tubo" es el ejemplo más claro: una regla correcta para Dormitorio es incorrecta si se aplica sin condicionarla al uso real de la pieza.
3. **Confundir la relación "sirve a" con la relación "pertenece a".** Repetido en Trastero (4.4) y Plaza de garaje (8.1): un espacio puede servir a una Vivienda sin pertenecer físicamente a su misma Planta o Unidad de uso — tratarlas como la misma relación produce cómputos de superficie y de contención incorrectos.
4. **Fusionar dos tipos funcionalmente distintos bajo un único patrón de reconocimiento** — el caso ya confirmado y real de `SALON|COCINA` en `evaluator.py` (1.3), el ejemplo más concreto de todo este documento de un error de clasificación que no es hipotético, ya está en producción, y que esta taxonomía existe, en parte, para que la próxima implementación del motor de reglas no repita.
5. **No distinguir un tipo de espacio técnico o de instalación (Categoría 7) simplemente porque hoy no es geométricamente reconocible** — el riesgo aquí no es clasificar mal, es no clasificar en absoluto y que la ausencia total de dato se confunda con "no existe", cuando en realidad es "no se puede observar con los datos actuales" (`UNCERTAINTY_MODEL.md`, distinción entre Missing Data y ausencia real).

---

## Cierre

Esta taxonomía cubre 29 tipos con nombre propio sobre 9 categorías, construida enteramente por especialización de los conceptos ya fijados en `ARCHITECTURAL_ONTOLOGY.md` — no introduce ningún concepto de dominio nuevo que no fuera ya, implícitamente, una variante de Pieza, Pieza habitable, Pieza no habitable, Núcleo húmedo, Espacio técnico o Zona común. Su valor no es la novedad conceptual, es la operatividad: da nombre y régimen a cada tipo con el que un `Constraint` de `CONSTRAINT_MODEL.md` puede indexar su tabla de parámetros por uso, sin que cada dominio tenga que inventar su propio vocabulario de tipos como ya advertía el riesgo de `FACT_MODEL.md` §12.2. El hallazgo más útil de este documento no es ningún tipo concreto — es la confirmación explícita, con el caso real de `SALON|COCINA`, de que el vocabulario de uso que existe hoy en producción es más estrecho que el vocabulario real del dominio, y que esa estrechez no es neutra: ya está produciendo, en el sistema actual, una pérdida de precisión concreta y localizable entre Salón y Cocina como tipos independientes.
