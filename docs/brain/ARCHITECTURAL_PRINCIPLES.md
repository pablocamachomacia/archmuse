# ARCHITECTURAL_PRINCIPLES.md

**Propósito:** recopilar los principios de diseño arquitectónico que seguirían siendo ciertos aunque el CTE desapareciera mañana y se sustituyera por otro código completamente distinto, o aunque ArchMuse se usara en un país sin ninguna de las normas que hoy conoce. **Ninguna referencia legal en este documento** — donde otros documentos de la serie citan un artículo, un decreto o un umbral, este documento pregunta qué había *antes* de ese artículo, y qué seguiría habiendo si se derogara. Sin código, como el resto de la serie.

**El criterio de inclusión, aplicado a cada principio antes de escribirlo:** *¿seguiría siendo cierto si la normativa cambiara por completo, si el proyecto se construyera en otro país, o en otra época?* Un principio que solo tiene sentido porque el CTE lo exige no pertenece aquí — pertenece a `CONSTRAINT_MODEL.md`. Este documento recoge, precisamente, la otra mitad: los principios que con frecuencia **explican por qué existe** un umbral normativo concreto, sin ser ellos mismos ese umbral.

**Referencias obligatorias, asumidas como ya decididas — y frontera explícita con cada una, para no duplicar contenido ya escrito:**
- `ARCHITECTURAL_QUALITY.md` §1-3 — los siete ejes de excelencia (parti, respuesta al lugar, promenade architecturale, servido/servidor, luz compositiva, proporción, economía de medios) y el marco de tres niveles de aproximación (A: proxy geométrico, B: heurística comparativa, C: criterio irreducible), reutilizado aquí sin cambios como la escala de "nivel de objetividad" de cada principio. **Frontera:** ese documento juzga la excelencia de un proyecto ya construido (evaluación, casi todo Nivel 4); este documento recoge principios generativos que un arquitecto aplica *mientras diseña*, muchos de ellos Nivel 3 — casi objetivos, aunque no legales. La unidad de intención o "parti" (`ARCHITECTURAL_QUALITY.md` §1) es, en sí misma, el principio raíz que sostiene a todos los que siguen — no se repite aquí como entrada propia.
- `FUNCTIONAL_RELATIONS.md` — las nueve escalas de relación entre espacios concretos (proximidad, separación, privacidad, ruido, luz, orientación, jerarquía, dependencia). **Frontera:** ese documento dice qué hacer con pares de espacios concretos de `SPACE_TAXONOMY.md`; este documento explica el principio general del que esas reglas concretas son una aplicación — por ejemplo, "Dormitorio lejos de Cocina" (`FUNCTIONAL_RELATIONS.md` §2) es una instancia concreta del principio más general de zonificación día/noche (§B.2 de este documento).
- `ARCHITECTURAL_ONTOLOGY.md`, `SPACE_TAXONOMY.md` — el vocabulario de conceptos y tipos de espacio sobre los que se aplican estos principios.
- Grounding real: `analyzer/parser.py` y `analyzer/evaluator.py` — cada principio declara honestamente si hoy es detectable con el pipeline DXF 2D real, o si requiere datos que el sistema no captura (misma disciplina ya aplicada en `ARCHITECTURAL_ONTOLOGY.md`, sección de revisión final: el 21% de conceptos reconocibles hoy).

---

## 0. Cómo leer este documento

15 principios en 4 familias, cada uno con seis campos fijos: **fundamento** (por qué es cierto, con razonamiento físico, humano o económico — nunca legal), **cuándo aplica**, **cuándo no aplica**, **conflictos habituales** (con qué otro principio o dominio tensiona), **nivel de objetividad** (Nivel A/B/C de `ARCHITECTURAL_QUALITY.md` §2), **cómo podría detectarlo ArchMuse**.

---

## Familia A — Clima y energía pasiva

### A.1 Doble orientación y ventilación cruzada

- **Fundamento:** una pieza con huecos en dos fachadas no paralelas permite renovar el aire por diferencia de presión sin depender de mecanismo alguno — es física de fluidos, no una preferencia cultural; se practica en arquitectura vernácula de climas y siglos completamente distintos entre sí, precisamente porque el principio no depende de ningún contexto normativo.
- **Cuándo aplica:** en cualquier pieza de uso prolongado (Salón, Dormitorio) cuya geometría lo permita — parcelas con más de una fachada libre disponible.
- **Cuándo no aplica:** en parcelas entre medianeras con una única fachada disponible, donde la doble orientación es geométricamente imposible sin patio interior; en piezas de uso breve (Aseo, Distribuidor) donde el beneficio no compensa el coste de doble hueco.
- **Conflictos habituales:** con Compacidad de la envolvente (A.3) — maximizar fachada disponible para ventilación cruzada tensiona con minimizar superficie de envolvente por eficiencia térmica; con Densidad urbanística (`ARCHITECTURAL_ONTOLOGY.md` A.3), que a menudo empuja hacia plantas más profundas y menos fachada por pieza.
- **Nivel de objetividad:** Nivel A — verificable geométricamente sin ambigüedad (¿la pieza tiene huecos en más de una orientación no paralela?).
- **Cómo podría detectarlo ArchMuse:** hoy no, con fiabilidad — requiere reconocer Hueco (`ARCHITECTURAL_ONTOLOGY.md` D.4) como entidad propia por fachada, y el parser actual no extrae huecos individuales; sería computable en cuanto exista ese dato (ya señalado como brecha en `ARCHITECTURAL_ONTOLOGY.md`, revisión final).

### A.2 Orientación solar coherente con el uso horario

- **Fundamento:** cada actividad humana tiene un ritmo horario propio (dormir de noche, cocinar y comer al mediodía, socializar de tarde) — orientar cada pieza según el momento del día en que su sol es más deseable es, simplemente, alinear la geometría del edificio con el reloj humano, un principio válido en cualquier latitud aunque el ángulo óptimo cambie con ella.
- **Cuándo aplica:** siempre que el proyecto tenga margen de elección de orientación por pieza — la mayoría de programas residenciales con más de una fachada.
- **Cuándo no aplica:** en clima ecuatorial, donde la diferencia de calidad solar entre orientaciones se reduce drásticamente y el principio pierde buena parte de su fuerza frente a otros (protección de lluvia, ventilación) que pasan a dominar la decisión.
- **Conflictos habituales:** con la Edificabilidad y Retranqueo del solar (`ARCHITECTURAL_ONTOLOGY.md` A.3/A.5), que a menudo fijan la orientación posible del volumen antes de que exista margen de elección por pieza; con el propio parti si la mejor orientación solar no coincide con la mejor relación con el acceso o la calle.
- **Nivel de objetividad:** Nivel B — el criterio general es casi consensual entre profesionales, pero su aplicación exacta (qué pieza cede ante cuál) es comparativa, no un umbral único.
- **Cómo podría detectarlo ArchMuse:** parcialmente, ya en producción — `evaluator.py` (`_ORIENTATION_RULES`, ya documentado en `FUNCTIONAL_RELATIONS.md` §7) evalúa esto hoy como recomendación no bloqueante, condicionado al parámetro `norte_grados` declarado por formulario, no observado geométricamente.

### A.3 Compacidad de la envolvente

- **Definición del término dentro del principio:** relación entre la superficie de envolvente exterior (fachada + cubierta) y el volumen habitable que encierra — a menor superficie de envolvente por unidad de volumen, menor pérdida/ganancia térmica pasiva.
- **Fundamento:** un volumen compacto pierde y gana calor más lentamente que uno de geometría fragmentada de igual superficie útil — es geometría sólida elemental (relación superficie/volumen), cierta en cualquier época constructiva, desde el iglú hasta el hormigón armado.
- **Cuándo aplica:** en climas de fuerte amplitud térmica (frío marcado, calor marcado, o ambos), donde el coste energético de calefactar/refrigerar una envolvente extensa es alto.
- **Cuándo no aplica:** en clima templado de amplitud térmica moderada, donde el beneficio energético de la compacidad es menor y otros principios (A.1, respuesta al lugar de `ARCHITECTURAL_QUALITY.md` §1) pueden pesar más sin penalización relevante; tampoco aplica como principio absoluto cuando el propio parti exige una geometría fragmentada por razones de programa (patios internos, por ejemplo, que a la vez sirven a A.1).
- **Conflictos habituales:** con Doble orientación (A.1) de forma directa — más fachada favorece ventilación cruzada y penaliza compacidad, el mismo par ya señalado en A.1.
- **Nivel de objetividad:** Nivel A — calculable de forma exacta (superficie de envolvente / volumen) sin ambigüedad de criterio.
- **Cómo podría detectarlo ArchMuse:** parcialmente — la superficie en planta y el perímetro exterior del polígono de una Unidad de uso o Edificio ya son calculables con la geometría existente (`shapely`); falta el dato de altura/volumen real (Familia G de `ARCHITECTURAL_ONTOLOGY.md`, no disponible en un DXF de planta 2D) para completar el ratio real.

### A.4 Protección solar pasiva antes que corrección mecánica

- **Fundamento:** resolver el exceso de radiación solar con geometría (voladizo, retranqueo de hueco, orientación, vegetación) es, estructuralmente, más duradero y de menor coste de mantenimiento a lo largo de la vida del edificio que resolverlo con un sistema mecánico (aire acondicionado) que consume energía cada vez que se usa y que puede fallar o quedar obsoleto — es un principio de jerarquía de soluciones, no de prohibición del sistema mecánico.
- **Cuándo aplica:** en cualquier pieza con exposición solar significativa en horas de mayor uso, especialmente en climas cálidos.
- **Cuándo no aplica:** en fachadas norte de clima templado/frío, donde el exceso de radiación no es, en la práctica, un problema a resolver; tampoco aplica como criterio absoluto en rehabilitación de fachadas protegidas, donde añadir elementos de protección pasiva puede no ser una opción real (`ARCHITECTURAL_ONTOLOGY.md` D.5, contraejemplo de fachada protegida).
- **Conflictos habituales:** con Luz natural como generadora de espacio (Familia B, principio raíz de `ARCHITECTURAL_QUALITY.md` §1) — una protección solar bien dimensionada reduce simultáneamente exceso térmico y cantidad de luz, y encontrar el punto que resuelve lo primero sin sacrificar lo segundo es, precisamente, el ejercicio de diseño que este principio exige, no un resultado automático.
- **Nivel de objetividad:** Nivel B — el principio en sí es de amplio consenso profesional, pero el dimensionado correcto de la protección (cuánto voladizo, qué orientación) es comparativo y depende de la latitud/clima concretos.
- **Cómo podría detectarlo ArchMuse:** no reconocible hoy — requiere geometría de elementos de protección solar (voladizos, lamas) que no existen como entidad en el DXF de distribución 2D; es, estructuralmente, información de sección/alzado, ajena al plano de planta que el parser procesa.

---

## Familia B — Organización interior

### B.1 Separación de flujos (social y de servicio) como principio de orden

- **Fundamento:** cuando dos tipos de recorrido con propósitos distintos (recibir visitas, transportar objetos y residuos) comparten el mismo trayecto físico, cada uno degrada la experiencia del otro — un principio de orden compositivo anterior a cualquier normativa, presente ya en la organización de las casas romanas (atrio vs. servicio) mucho antes de que existiera ningún código de edificación.
- **Cuándo aplica:** en programas de superficie suficiente para sostener dos recorridos diferenciados sin penalizar la eficiencia global de la distribución.
- **Cuándo no aplica:** ya señalado como caso de discrepancia legítima en `FUNCTIONAL_RELATIONS.md` §10.3 — en programas de superficie reducida, forzar la separación completa produce, con frecuencia, una circulación general peor que aceptar un recorrido único bien resuelto; el principio cede ante la eficiencia cuando el programa no sostiene ambos.
- **Conflictos habituales:** con la eficiencia de superficie útil/construida — todo recorrido adicional dedicado a diferenciar flujos resta superficie a piezas habitables.
- **Nivel de objetividad:** Nivel B — el principio es de consenso amplio, pero "cuánta separación merece la pena" es una comparación de trade-offs, no un umbral fijo.
- **Cómo podría detectarlo ArchMuse:** no reconocible hoy con fiabilidad — requiere el grafo de circulación conectado (`ARCHITECTURAL_ONTOLOGY.md` E.1, ya señalado como no modelado), sin el cual no se puede verificar si existen efectivamente dos recorridos distintos o solo uno.

### B.2 Zonificación día/noche como estructura del parti

- **Fundamento:** agrupar las piezas de uso diurno-social en una zona y las de descanso en otra, con una transición reconocible entre ambas, reduce las interferencias funcionales (ruido, horario, visibilidad) entre actividades incompatibles sin necesidad de aislamiento reforzado pieza a pieza — es más barato y más robusto resolver la incompatibilidad agrupando que resolverla partición por partición.
- **Cuándo aplica:** en cualquier vivienda con más de una o dos piezas habitables — es, probablemente, el principio de zonificación de mayor consenso universal de toda esta lista.
- **Cuándo no aplica:** en programas de una sola pieza (estudio/loft), donde la zonificación física no es posible y debe resolverse, si acaso, con mobiliario o desnivel, no con distribución; también se relaja quando el propio cliente declara una intención de vivienda completamente abierta sin distinción de zonas (Preference de ámbito de proyecto, `ARCHITECTURAL_QUALITY.md` §4).
- **Conflictos habituales:** con Doble orientación (A.1) cuando la mejor orientación solar no coincide con la agrupación deseada de zona de noche; con la propia jerarquía servido/servidor si la zona de noche, por necesidad geométrica, queda con peor acceso o peor luz que la zona de día.
- **Nivel de objetividad:** Nivel B — ampliamente compartido entre profesionales, verificable por comparación de agrupación, no por un único proxy geométrico cerrado.
- **Cómo podría detectarlo ArchMuse:** parcialmente — con el catálogo de usos de `SPACE_TAXONOMY.md` ya aplicado a cada Pieza, es computable si las piezas de uso "noche" (Dormitorio) están geométricamente agrupadas y separadas de las de uso "día" (Salón, Cocina) mediante un proxy de proximidad entre centroides o de contigüidad de polígonos — no implementado hoy, pero no requiere ningún dato que el parser no tenga ya.

### B.3 Ningún espacio habitable interior ciego sin justificación

- **Fundamento:** una pieza destinada a permanencia humana prolongada sin ninguna relación con el exterior (ni luz ni aire directos) es, con independencia de cualquier norma concreta, una condición de habitabilidad degradada — el principio antecede a cualquier ratio numérico de superficie de hueco: incluso sin cifra exacta, "toda pieza habitable debería tener una ventana propia" es un consenso profesional que existía antes del primer código de edificación moderno.
- **Cuándo aplica:** a cualquier Pieza habitable (`ARCHITECTURAL_ONTOLOGY.md` C.2) de uso prolongado.
- **Cuándo no aplica:** en piezas explícitamente no habitables por definición (Trastero, Vestidor, Distribuidor — `SPACE_TAXONOMY.md` Categoría 4), donde la ausencia de hueco no es una carencia sino una condición coherente con su uso; también en rehabilitaciones donde la geometría preexistente no permite abrir un hueco nuevo sin alterar un elemento protegido — el principio sigue siendo cierto en abstracto, pero cede ante una imposibilidad física real, no ante la mera conveniencia de proyecto.
- **Conflictos habituales:** con Compacidad de la envolvente (A.3) y con Edificabilidad/Ocupación en parcelas de fondo profundo, donde maximizar superficie construida en planta tiende a generar piezas interiores sin fachada disponible.
- **Nivel de objetividad:** Nivel A — la presencia o ausencia de relación directa con el exterior es, en sí misma, un hecho binario verificable, aunque la ponderación de "cuánta" luz/aire sea suficiente sea ya Nivel B (competencia normativa, no de este documento).
- **Cómo podría detectarlo ArchMuse:** hoy, de forma indirecta — el proxy de superficie de hueco por fachada (`facade_width × 0,25`, ya documentado como Estimation en `UNCERTAINTY_MODEL.md` §4) permite inferir si una pieza tiene o no fachada disponible propia; una pieza sin ningún tramo de perímetro exterior en su polígono, y que además el catálogo de `SPACE_TAXONOMY.md` clasifica como habitable, sería un candidato directo a incumplir este principio, con la geometría ya disponible hoy.

### B.4 Modulación estructural coherente con la distribución

- **Fundamento:** cuando la retícula estructural (posición de soportes) y la distribución de particiones comparten una lógica geométrica común, el edificio es más económico de construir, más fácil de reformar en el futuro y más legible espacialmente — un edificio cuya estructura "no tiene nada que ver" con su distribución interior es, con alta probabilidad, más caro de construir y más difícil de adaptar más adelante, independientemente de qué norma estructural esté vigente en el momento.
- **Cuándo aplica:** en cualquier proyecto con estructura porticada regular (la inmensa mayoría de vivienda plurifamiliar contemporánea).
- **Cuándo no aplica:** en proyectos con sistema estructural deliberadamente singular (grandes luces buscadas como decisión de diseño, ya señalado como excepción en `ARCHITECTURAL_ONTOLOGY.md` F.1) — ahí la falta de coincidencia entre malla y distribución es una decisión consciente, no un defecto de coordinación.
- **Conflictos habituales:** con la libertad de distribución interior que el propio cliente o el criterio de calidad espacial (`ARCHITECTURAL_QUALITY.md` Dominio 9) puedan desear — una malla estructural muy regular impone restricciones a soluciones espaciales más libres.
- **Nivel de objetividad:** Nivel B — comparativo (¿cuánto coincide la retícula con la distribución?), no reducible a un único proxy sin datos de sección/estructura reales.
- **Cómo podría detectarlo ArchMuse:** no reconocible hoy — depende de Elemento estructural (`ARCHITECTURAL_ONTOLOGY.md` F.1), ya señalado como el concepto de menor techo de reconocimiento automático de toda la ontología (requiere, como mínimo, geometría de más de una Planta, no disponible en el flujo actual de un único DXF).

---

## Familia C — Percepción y uso humano

### C.1 Proporción y escala humana en el dimensionado

- **Fundamento:** el cuerpo humano y sus movimientos (alcance, paso, campo visual) son una referencia dimensional estable en cualquier época y cultura — un pasillo, una puerta o una altura libre se diseñan, en última instancia, en relación con el cuerpo que los va a usar, no con ninguna cifra normativa concreta; la norma, cuando fija un mínimo, casi siempre está intentando aproximar este mismo principio antropométrico, no inventando uno nuevo.
- **Cuándo aplica:** a cualquier dimensión de paso, altura libre o proporción de pieza destinada a uso humano directo.
- **Cuándo no aplica:** en espacios técnicos o de almacenamiento sin presencia humana continuada (Espacio técnico, `ARCHITECTURAL_ONTOLOGY.md` C.5), donde la referencia dimensional relevante es la del equipo que albergan, no la del cuerpo humano.
- **Conflictos habituales:** con la eficiencia de superficie — cualquier margen por encima del mínimo antropométrico estricto compite por superficie útil con otras piezas.
- **Nivel de objetividad:** Nivel A para las dimensiones puramente antropométricas (ancho de paso, altura libre); Nivel B para la "sensación de escala" completa de una pieza, que depende también de proporción y luz, no solo de medida absoluta.
- **Cómo podría detectarlo ArchMuse:** ya parcialmente en producción — el cálculo de ancho mínimo de pasillo y las heurísticas de proporción de `spatial_quality.py` (proporción "tubo", relación superficie/altura) ya aplican este principio, aunque sin nombrarlo explícitamente como tal.

### C.2 Legibilidad del recorrido de acceso

- **Fundamento:** un visitante que entra por primera vez a un edificio o vivienda debería poder entender, sin señalización explícita, hacia dónde dirigirse — la geometría y la secuencia espacial comunican por sí solas, un principio de comunicación no verbal que precede a cualquier norma de señalización o accesibilidad informativa.
- **Cuándo aplica:** al punto de acceso principal de cualquier Unidad de uso o Edificio.
- **Cuándo no aplica:** en accesos de servicio o técnicos, donde la legibilidad para un usuario no familiarizado no es el criterio relevante (el usuario habitual del acceso de servicio ya conoce el recorrido).
- **Conflictos habituales:** con Separación de flujos (B.1) — un vestíbulo que reparte con claridad hacia zona social y zona de servicio a la vez es, precisamente, donde ambos principios se refuerzan o compiten según cómo se resuelva la bifurcación.
- **Nivel de objetividad:** Nivel C — depende en gran medida de la experiencia subjetiva de orientación de una persona, terreno de "espejo, no juez" (`ARCHITECTURAL_QUALITY.md` §3); solo admite proxies débiles, nunca un veredicto firme.
- **Cómo podría detectarlo ArchMuse:** no reconocible con fiabilidad — sin un modelo de grafo de circulación conectado ni datos de campo visual desde el punto de acceso, este principio queda, por ahora, fuera del alcance de cualquier verificación geométrica seria; el sistema, como mucho, podría describir la secuencia de piezas atravesadas (una vez exista el grafo de B.1), nunca juzgar si es "legible".

### C.3 Accesibilidad universal como principio de diseño, no como imposición legal

- **Fundamento:** diseñar para el rango completo de capacidades humanas (movilidad reducida temporal o permanente, distintas edades, distintas estaturas) desde el planteamiento inicial produce, casi siempre, mejores soluciones para todos los usuarios que añadir accesibilidad como corrección posterior sobre un diseño ya cerrado — el principio de diseño universal es anterior y más amplio que cualquier normativa de accesibilidad concreta, y seguiría siendo una buena práctica de diseño en un hipotético mundo sin ninguna ley de accesibilidad.
- **Cuándo aplica:** a la totalidad del recorrido interior de cualquier proyecto, no solo a los elementos que una normativa concreta declare obligatorios.
- **Cuándo no aplica:** el principio en sí no tiene excepciones de fondo — lo que varía es su grado de exigencia (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 5 §5, "accesible" vs. "adaptado" como umbrales de ambición, no de validez del principio); en rehabilitación de patrimonio protegido, la aplicación puede verse limitada por la preexistencia, no por invalidez del principio.
- **Conflictos habituales:** con Superficie útil (ensanchar un paso reduce superficie de piezas adyacentes, ya documentado en `CHAIN_REASONING.md` §5 y en `FUNCTIONAL_RELATIONS.md`); con Modulación estructural (B.4) si la retícula no anticipó anchos de paso accesibles desde el principio.
- **Nivel de objetividad:** Nivel A para los componentes dimensionales estrictos (ancho, espacio de giro); Nivel B-C para la calidad de integración de la solución accesible en el diseño general (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 5, Nivel 4: "accesibilidad de trámite" frente a "bien integrada").
- **Cómo podría detectarlo ArchMuse:** los componentes dimensionales, sí, con el mismo mecanismo ya en producción para ancho de paso y espacio de giro de baño (`evaluate_bathroom_accessibility`); la calidad de integración del diseño, no — sigue siendo, honestamente, terreno de criterio humano (Nivel C), no de detección automática.

---

## Familia D — Perdurabilidad y adaptabilidad

### D.1 Flexibilidad de uso en el tiempo

- **Fundamento:** las familias, los hogares y los usos cambian a lo largo de la vida útil de un edificio (décadas), mientras que la estructura y la envolvente son mucho más caras de modificar que la distribución interior — un proyecto cuya distribución puede reorganizarse sin tocar estructura ni instalaciones principales sobrevive mejor a esos cambios que uno que fija de forma rígida el uso de cada pieza para siempre, con independencia de qué normativa esté vigente en cada momento futuro.
- **Cuándo aplica:** especialmente relevante en vivienda de larga vida útil esperada y en piezas de uso menos determinado (Dormitorios secundarios, Despacho) que con más probabilidad cambien de función con el tiempo (de dormitorio infantil a despacho, por ejemplo).
- **Cuándo no aplica:** en piezas cuya función está intrínsecamente ligada a su posición e instalaciones (Baño, Cocina) — la flexibilidad de uso no aplica igual a un Núcleo húmedo, cuya reubicación sí implica coste estructural/de instalaciones real; también se relaja en proyectos de uso muy específico y no residencial, donde la especialización total puede ser, precisamente, el objetivo del programa.
- **Conflictos habituales:** con Modulación estructural coherente (B.4) — una estructura que anticipa flexibilidad futura (luces regulares, sin muros de carga interiores) puede tensionar con la eficiencia estructural de una solución más ajustada a la distribución actual.
- **Nivel de objetividad:** Nivel B — comparativo, no reducible a un único proxy: "cuánta flexibilidad tiene esta distribución" depende de varios factores combinados (posición de muros de carga, posición de núcleos húmedos), no de una única medida.
- **Cómo podría detectarlo ArchMuse:** no reconocible hoy con fiabilidad — depende, otra vez, de distinguir Muro de carga de Tabique (`ARCHITECTURAL_ONTOLOGY.md` D.2/D.3), ya señalado como de fiabilidad baja sin datos constructivos reales; sería computable, en el futuro, contando cuántas particiones interiores de una Unidad de uso son Tabique (reubicables) frente a Muro de carga (fijo).

### D.2 Durabilidad y facilidad de mantenimiento

- **Fundamento:** una decisión de diseño que exige mantenimiento frecuente, especializado o de difícil acceso tiene un coste real a lo largo de la vida del edificio que rara vez se contabiliza en el momento de proyectar, pero que un arquitecto sénior sabe anticipar — es un principio económico y de responsabilidad a largo plazo con el usuario final, independiente de cualquier normativa de garantía o de responsabilidad civil concreta (aunque, con frecuencia, esas normativas también intentan aproximarlo).
- **Cuándo aplica:** a cualquier elemento cuyo mal funcionamiento o degradación afecte al uso cotidiano del edificio — especialmente Núcleo húmedo, Fachada, Elementos técnicos de instalaciones.
- **Cuándo no aplica:** en elementos deliberadamente efímeros o de sustitución esperada y económica (acabados interiores de vida útil corta por decisión de diseño consciente, no por descuido) — ahí la durabilidad extrema no es el objetivo, y exigirla sería un criterio mal aplicado.
- **Conflictos habituales:** con Economía de medios inicial (`ARCHITECTURAL_QUALITY.md` §1, coste de construcción) — la solución de mayor durabilidad no siempre es la de menor coste inicial, y el trade-off entre ambos es, precisamente, terreno de decisión de programa (presupuesto disponible, `DECISION_ENGINE.md` §2 Tipo 3), no de superioridad universal de una sobre otra.
- **Nivel de objetividad:** Nivel C — depende de datos de composición constructiva que un plano de distribución no contiene, y de un juicio de vida útil esperada que varía por material y por uso; sin datos constructivos reales, cualquier afirmación al respecto es, en el mejor caso, una hipótesis razonada.
- **Cómo podría detectarlo ArchMuse:** no reconocible en absoluto desde el DXF de distribución actual — depende enteramente de datos de composición constructiva que hoy no existen en ningún punto del pipeline de datos del proyecto.

### D.3 Reversibilidad de las decisiones de diseño

- **Fundamento:** algunas decisiones de proyecto son fáciles de deshacer si resultan equivocadas (una distribución interior en fase de anteproyecto) y otras son prácticamente irreversibles una vez construidas (la posición de un núcleo de escalera, el volumen general del edificio) — un arquitecto sénior pondera el coste de equivocarse de forma distinta según en qué punto de esa escala está la decisión, y ese criterio es, en sí mismo, un principio de diseño responsable, no una imposición normativa. Es, de hecho, el mismo criterio ya formalizado como tercer nivel de la jerarquía de prioridad en `DECISION_ENGINE.md` §3 — aquí se recoge como principio de origen, no como mecanismo de decisión.
- **Cuándo aplica:** a cualquier decisión de proyecto, con mayor peso cuanto más avanzada esté la fase de desarrollo o mayor sea el coste de deshacerla.
- **Cuándo no aplica:** en fases muy tempranas de anteproyecto, donde prácticamente todo es reversible por igual y el principio no discrimina todavía entre alternativas.
- **Conflictos habituales:** con la ambición de diseño — las decisiones de mayor potencial de calidad (una geometría singular, una estructura expresiva) suelen ser, también, las menos reversibles; el principio no dice "evita lo irreversible", dice "pondera su coste con más cuidado cuanto menos reversible sea".
- **Nivel de objetividad:** Nivel B — la reversibilidad de una familia de cambio es clasificable de forma razonablemente consensuada (ya formalizado, de hecho, en `RECOMMENDATION_ENGINE.md` §8, tabla de techos de reversibilidad por familia de cambio de `CHAIN_REASONING.md`), aunque el caso concreto siempre admite matices.
- **Cómo podría detectarlo ArchMuse:** ya diseñado, aunque no implementado — es, literalmente, el mecanismo de `RECOMMENDATION_ENGINE.md` §8, que asigna un techo de reversibilidad a cada una de las 8 familias de cambio de `CHAIN_REASONING.md` §1; este principio no añade un mecanismo nuevo, confirma que el que ya existe en la serie tiene, además, una justificación de diseño atemporal detrás, no solo una utilidad de ingeniería de decisión.

---

## Cierre

Los catorce principios de arriba comparten una propiedad que merece decirse explícitamente, porque es la prueba de que este documento cumplió su propio criterio de inclusión: ninguno menciona un artículo, un decreto, ni una cifra normativa concreta, y sin embargo casi todos son, en la práctica, la razón última por la que existe alguna norma relacionada en algún dominio de `BRAIN_ARCHITECTURE.md` — la ventilación cruzada (A.1) explica por qué el CTE exige una superficie mínima de ventilación, no al revés; la accesibilidad universal (C.3) explica por qué existe una normativa de accesibilidad, no al revés. Esta es, precisamente, la utilidad de mantener este documento separado de `CONSTRAINT_MODEL.md`: cuando una normativa cambie —y lo hará, como ya cambia hoy entre comunidades autónomas— estos catorce principios seguirán siendo el criterio de fondo contra el que evaluar si el cambio normativo tiene sentido o lo ha perdido. Un sistema que solo conociera los umbrales y nunca los principios que los motivan no podría distinguir nunca esa diferencia — sabría que algo cambió, nunca sabría si el cambio es una mejora o un retroceso respecto a lo que la normativa, en su origen, estaba intentando proteger.
