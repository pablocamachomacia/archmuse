# ARCHITECTURAL_KNOWLEDGE_MAP.md

**Propósito:** este documento no diseña software. Diseña **el contenido** que cada uno de los 14 dominios definidos en `BRAIN_ARCHITECTURE.md` tendría que llegar a saber para razonar como un arquitecto experto, no solo para verificar reglas. Es el mapa de conocimiento, no el motor que lo ejecuta — la pregunta que responde cada sección es "¿qué tendría que saber un arquitecto con 25 años de experiencia sobre esto?", no "¿cómo lo codificamos?".

Cada dominio se desarrolla en las 10 dimensiones solicitadas y se cierra con la clasificación en 4 niveles de conocimiento (hechos objetivos → normativa verificable → buenas prácticas → criterio arquitectónico), que es también, de facto, un mapa de **cuánto puede automatizarse cada pieza de conocimiento** sin perder rigor. Nivel 1 y 2 son automatizables con alta confianza. Nivel 3 es automatizable con confianza media, marcado siempre como recomendación, no como incumplimiento. Nivel 4 es, en gran parte de los dominios, terreno que un sistema experto solo puede **apoyar**, no sustituir — y donde lo honesto es decirlo así, no fingir una respuesta que no existe.

Un aviso que aplica a todo el documento: donde se cita normativa (códigos de DB del CTE, artículos, decretos autonómicos), se hace con el nivel de precisión razonable para un mapa de conocimiento — la referencia exacta de cada artículo debe verificarse contra el texto vigente en el momento de construir cada regla, no darse aquí por definitiva. Este documento mapea **qué tipo de conocimiento normativo existe y dónde vive**, no sustituye la consulta directa del texto legal en el momento de implementar.

---

## Dominio 1 — Encaje Normativo-Urbanístico

### 1. Conceptos fundamentales
Parcela y solar (no son sinónimos: solar es parcela ya urbanizada y apta para edificar), edificabilidad (m² edificables por m² de parcela, o total en m²), ocupación en planta (% de la parcela que puede cubrir la edificación), altura reguladora (en plantas y/o metros), retranqueos y alineaciones (a vial, a linderos, entre edificaciones), fondo edificable, parcela mínima edificable, uso característico y usos compatibles/prohibidos/tolerados, densidad (viviendas/hectárea), cesiones obligatorias, aprovechamiento urbanístico.

### 2. Principios arquitectónicos
El proyecto se subordina siempre al planeamiento vigente — ningún criterio de diseño posterior puede compensar un incumplimiento urbanístico. Jerarquía normativa clara: legislación estatal del suelo → legislación urbanística autonómica → planeamiento general municipal (PGOU/PGOM) → planeamiento de desarrollo (Plan Parcial, Plan Especial, Estudio de Detalle) → ordenanza municipal de edificación. Un arquitecto experto revisa siempre en ese orden, nunca al revés.

### 3. Normativa relacionada
Texto Refundido de la Ley de Suelo y Rehabilitación Urbana (estatal), legislación urbanística propia de cada comunidad autónoma (distinta en nombre y estructura en cada una — Cataluña, Valencia, Andalucía, Madrid, etc. no comparten texto), PGOU/PGOM del municipio, Plan Parcial o Plan Especial si existe, Ordenanzas municipales de edificación, normativa de protección patrimonial si el edificio o el entorno está catalogado.

### 4. Reglas objetivas
Edificabilidad máxima (m²/m² o total), ocupación máxima en planta (%), altura máxima (en plantas y/o metros a cornisa/cumbrera), retranqueos mínimos obligatorios, parcela mínima edificable, número máximo de viviendas por parcela si el planeamiento lo fija.

### 5. Reglas heurísticas (criterio profesional)
Cuándo conviene tramitar un Estudio de Detalle en lugar de forzar la interpretación literal de una ordenanza ambigua; cómo interpretar expresiones como "alineación de fachada tradicional del entorno" cuando el PGOU no da un valor numérico; criterio sobre si apurar al máximo la edificabilidad permitida compromete la calidad del proyecto resultante (casi siempre lo hace, y un arquitecto experto lo advierte incluso si el cliente insiste); cuándo un solar "raro" (muy irregular, con pendiente fuerte) hace que los parámetros urbanísticos estándar no sean directamente aplicables sin un criterio adicional de interpretación geométrica.

### 6. Conflictos habituales con otros dominios
Con el Dominio 3 (Geometría y Dimensionado): a mayor ocupación aprovechada, menos margen queda para patios de luz suficientes. Con el Dominio 9 (Calidad Espacial): edificabilidad máxima empuja hacia programas más densos y compactos, en detrimento de la calidad espacial. Con el Dominio 8 (Térmica): retranqueos y alturas condicionan la exposición solar y por tanto el comportamiento energético.

### 7. Excepciones
Edificios fuera de ordenación (preexistentes, no ajustados al planeamiento vigente, con régimen especial de obras permitidas), edificios catalogados o en entornos de protección patrimonial (donde la ordenanza general no aplica sin más, hay normativa específica de protección), situaciones de planeamiento en revisión o suspendido, convenios urbanísticos particulares que alteran parámetros para una parcela concreta.

### 8. Casos donde no existe una respuesta correcta
Solares afectados por doble planeamiento superpuesto sin resolver contradicción explícita; interpretación de conceptos no cuantificados del PGOU ("tipología tradicional", "armonía con el entorno"); planeamiento en fase de redacción donde el régimen aplicable depende de la fecha exacta de solicitud de licencia.

### 9. Datos mínimos necesarios para poder evaluarlo
Ubicación exacta o referencia catastral de la parcela, calificación urbanística vigente, ficha urbanística aplicable (edificabilidad, ocupación, altura, retranqueos), existencia o no de planeamiento de desarrollo o catalogación patrimonial.

### 10. Nivel de confianza que puede alcanzar el sistema
Bajo-medio hoy, potencialmente alto a medio plazo. El límite no es conceptual sino de acceso a datos: el planeamiento municipal español no está unificado ni siempre digitalizado de forma consultable automáticamente. La confianza sube directamente con la calidad de la integración con fuentes oficiales (sede electrónica del ayuntamiento, catastro, visores urbanísticos autonómicos), no con más reglas internas.

### Clasificación en 4 niveles
- **Nivel 1 (hechos objetivos):** superficie de parcela, ubicación, geometría del solar.
- **Nivel 2 (normativa verificable):** edificabilidad, ocupación, altura y retranqueos máximos según la ficha urbanística vigente.
- **Nivel 3 (buenas prácticas):** no agotar el máximo edificable si compromete calidad espacial; dejar margen de retranqueo superior al mínimo en fachadas orientadas a sur.
- **Nivel 4 (criterio arquitectónico):** interpretación de conceptos ambiguos del PGOU ("armonía con el entorno", "tipología tradicional") y decisión de si merece la pena negociar un Estudio de Detalle.

---

## Dominio 2 — Programa y Tipología

### 1. Conceptos fundamentales
Tipología edificatoria (vivienda unifamiliar aislada/pareada/entre medianeras, vivienda plurifamiliar, rehabilitación, uso terciario, uso dotacional), programa funcional (conjunto de espacios y sus relaciones exigidas por el uso), pieza habitable vs. no habitable, unidad de uso independiente (vivienda, local), régimen de propiedad (si afecta a exigencias de compartimentación o accesibilidad).

### 2. Principios arquitectónicos
La tipología no es una etiqueta administrativa — es el filtro que determina qué conjunto de normativa aplica y con qué exigencia. Un arquitecto experto nunca evalúa un proyecto sin fijar primero, con certeza, qué es. La rehabilitación tiene un régimen normativo distinto (a menudo más flexible, por imposibilidad física de cumplir el mínimo de obra nueva) que debe declararse explícitamente, no asumirse.

### 3. Normativa relacionada
CTE (aplicación diferenciada obra nueva/rehabilitación, DB SI/SUA/HS/HE/HR según uso), LOE (agentes y responsabilidades según tipo de intervención), decretos autonómicos de habitabilidad (definen la tipología a efectos de superficies y programa mínimo), normativa de accesibilidad (exigencias distintas según tipología y número de viviendas).

### 4. Reglas objetivas
Clasificación tipológica a partir del número de unidades de vivienda, existencia de elementos comunes, y uso declarado; determinación de si aplica régimen de obra nueva o de rehabilitación según el alcance de la intervención declarado.

### 5. Reglas heurísticas (criterio profesional)
Cómo inferir la tipología real cuando la documentación de origen es ambigua o inconsistente (p. ej. un DXF etiquetado como "vivienda" que en realidad tiene varias unidades independientes); cuándo una "rehabilitación" es en realidad, a efectos normativos, una obra nueva por el alcance de la intervención (demolición sustancial); criterio sobre proyectos mixtos (planta baja terciaria + plantas de vivienda) donde el programa cambia por planta.

### 6. Conflictos habituales con otros dominios
Es el dominio con mayor impacto en cascada de todo el sistema: un error aquí no genera un conflicto puntual, invalida silenciosamente la evaluación de prácticamente todos los demás dominios (Geometría, Iluminación, Accesibilidad, Térmica), porque todos consumen la tipología como parámetro de entrada.

### 7. Excepciones
Proyectos de cambio de uso (de terciario a residencial o viceversa) donde la tipología "de origen" del edificio no coincide con la tipología "de destino" del proyecto; edificios con usos mixtos por planta que no encajan en una única categoría; viviendas colaborativas (cohousing) o alojamientos dotacionales que no encajan limpiamente en unifamiliar/plurifamiliar clásico.

### 8. Casos donde no existe una respuesta correcta
Proyectos híbridos genuinamente ambiguos (p. ej. una gran vivienda unifamiliar con dos núcleos independientes que podría interpretarse como bifamiliar) donde la clasificación depende de una decisión de proyecto, no de un hecho verificable objetivamente.

### 9. Datos mínimos necesarios para poder evaluarlo
Declaración explícita de tipología (no inferida por defecto), número de unidades independientes, uso de cada planta/zona, alcance de la intervención (obra nueva vs. rehabilitación y su grado).

### 10. Nivel de confianza que puede alcanzar el sistema
Muy alto **si el dato de entrada es correcto y llega realmente a los demás dominios** — y muy bajo, con consecuencias graves y silenciosas, si no llega (exactamente el fallo ya confirmado en el sistema actual, ver `TECH_REVIEW.md`). Este dominio no tiene un problema de conocimiento complejo; tiene un problema de garantizar que su salida se propaga siempre, sin excepción, a todo lo que depende de él.

### Clasificación en 4 niveles
- **Nivel 1 (hechos objetivos):** número de unidades independientes, número de plantas, superficie total declarada.
- **Nivel 2 (normativa verificable):** régimen normativo aplicable (obra nueva/rehabilitación) según el alcance de la intervención.
- **Nivel 3 (buenas prácticas):** declarar la tipología de forma explícita y verificada antes de cualquier otra evaluación, nunca inferirla por defecto.
- **Nivel 4 (criterio arquitectónico):** clasificación de programas híbridos o ambiguos que no encajan limpiamente en una categoría estándar.

---

## Dominio 3 — Geometría y Dimensionado Habitable

### 1. Conceptos fundamentales
Superficie útil vs. superficie construida, pieza habitable, ancho mínimo de pieza, proporción/relación de aspecto de una estancia, altura libre, superficie mínima por uso (dormitorio individual/doble, salón, cocina, baño), programa mínimo de vivienda según tipología.

### 2. Principios arquitectónicos
El dimensionado mínimo normativo es un suelo de habitabilidad legal, no un objetivo de diseño — cumplirlo exactamente no es sinónimo de que el espacio funcione bien (eso pertenece al Dominio 9). Un arquitecto experto distingue siempre "cumple el mínimo" de "está bien dimensionado", y sabe que espacios en el límite legal exacto suelen generar problemas de amueblamiento reales que la norma no captura.

### 3. Normativa relacionada
CTE DB-SUA (dimensiones de circulaciones y elementos), decretos autonómicos de habitabilidad (cada comunidad autónoma fija su propio programa mínimo de superficies y anchos — no hay un único decreto estatal de habitabilidad de vivienda), LOE en cuanto a superficie útil mínima de vivienda si aplica.

### 4. Reglas objetivas
Superficie mínima por tipo de pieza según decreto autonómico, ancho mínimo de pieza habitable, proporción máxima de aspecto (para evitar piezas "tubo" no funcionales aunque cumplan superficie), altura libre mínima.

### 5. Reglas heurísticas (criterio profesional)
Cuándo una pieza que cumple la superficie mínima normativa es, aun así, inamueblable en la práctica (geometrías en L, irregularidades, huecos de paso mal situados); criterio sobre cuánto margen por encima del mínimo normativo conviene dejar según el rango de mercado del proyecto; cómo valorar piezas cuya superficie útil real queda reducida por elementos estructurales o de instalaciones no reflejados en el plano bruto.

### 6. Conflictos habituales con otros dominios
Con el Dominio 5 (Accesibilidad): ensanchar circulaciones para cumplir itinerario accesible reduce superficie útil de piezas adyacentes. Con el Dominio 1 (Urbanístico): la ocupación máxima permitida condiciona cuánta superficie total hay disponible para repartir entre piezas. Con el Dominio 9: cumplir el mínimo dimensional no garantiza calidad espacial, y a veces las tensiona (una pieza mínima y bien proporcionada puede ser mejor que una más grande pero mal resuelta).

### 7. Excepciones
Rehabilitaciones donde la geometría preexistente impide físicamente alcanzar mínimos de obra nueva (régimen de "mínimo posible" o de intervención asumible, según cada decreto autonómico); piezas bajo cubierta con altura variable, donde el cómputo de superficie útil sigue reglas específicas distintas de una planta estándar.

### 8. Casos donde no existe una respuesta correcta
Piezas de geometría muy irregular donde el "ancho mínimo" es ambiguo de medir (no hay un único criterio universal de cómo medir anchura en una planta no rectangular); espacios de uso mixto sin destino único claro (un office que también es zona de paso) donde no está definido a qué mínimo dimensional debería exigírsele cumplir.

### 9. Datos mínimos necesarios para poder evaluarlo
Geometría fiable de cada pieza (polígono, no solo superficie total), uso asignado a cada pieza, tipología del proyecto (para saber qué decreto autonómico de habitabilidad aplica), comunidad autónoma del emplazamiento.

### 10. Nivel de confianza que puede alcanzar el sistema
Alto. Es el dominio más maduro y objetivable de todos — la geometría es un hecho medible directamente y la normativa, aunque fragmentada por comunidad autónoma, es explícita y cuantificada. El principal riesgo de confianza no es conceptual sino de calidad del dato de entrada (geometría mal extraída del plano origen).

### Clasificación en 4 niveles
- **Nivel 1 (hechos objetivos):** superficie, ancho, proporción, altura libre medidos directamente de la geometría.
- **Nivel 2 (normativa verificable):** mínimos de superficie/ancho por uso y comunidad autónoma.
- **Nivel 3 (buenas prácticas):** margen recomendado por encima del mínimo legal según rango del proyecto.
- **Nivel 4 (criterio arquitectónico):** valoración de si una pieza que cumple el mínimo es realmente amueblable y funcional.

---

## Dominio 4 — Iluminación y Ventilación Natural

### 1. Conceptos fundamentales
Superficie de hueco de iluminación, superficie de hueco de ventilación (no siempre coinciden), relación hueco/superficie útil de la pieza, patio de luces/ventilación y sus dimensiones mínimas (a menudo en función de la altura del edificio), ventilación cruzada, profundidad de iluminación natural.

### 2. Principios arquitectónicos
La luz y el aire naturales son, junto con el dimensionado, la base histórica de la habitabilidad — anteceden al CTE. Un arquitecto experto evalúa esto no solo como un ratio geométrico sino como una experiencia real: dos piezas con idéntico ratio hueco/superficie pueden tener calidad de luz completamente distinta según orientación y profundidad.

### 3. Normativa relacionada
CTE DB-HS3 (calidad del aire interior, exigencias de ventilación), CTE DB-HE (relacionado indirectamente vía huecos y envolvente), decretos autonómicos de habitabilidad (exigencias de iluminación/ventilación natural por tipo de pieza, a menudo más estrictos o específicos que el CTE estatal).

### 4. Reglas objetivas
Ratio mínimo de superficie de hueco de iluminación respecto a la superficie útil de la pieza, ratio mínimo de hueco de ventilación (puede ser distinto del de iluminación), dimensión mínima de patios en función de la altura del edificio que vierte a ellos.

### 5. Reglas heurísticas (criterio profesional)
Cómo valorar la calidad real de luz más allá del ratio mínimo (orientación, profundidad de la pieza respecto al hueco, obstrucción por edificios vecinos o por el propio patio); criterio sobre cuándo un patio que cumple la dimensión mínima normativa sigue siendo un patio de mala calidad lumínica en la práctica (patios estrechos y profundos cumplen el mínimo y son percibidos como oscuros); cuándo merece la pena sacrificar superficie útil por ampliar un hueco más allá del mínimo.

### 6. Conflictos habituales con otros dominios
Con el Dominio 8 (Térmica): más superficie acristalada mejora iluminación pero empeora comportamiento térmico, sobre todo en zonas climáticas cálidas o en orientaciones no favorables. Con el Dominio 1: patios mayores reducen la superficie edificable aprovechable dentro de los mismos parámetros urbanísticos. Con el Dominio 7 (Acústica): huecos grandes hacia fachadas con ruido exterior tensionan el aislamiento acústico exigido.

### 7. Excepciones
Piezas no habitables (trasteros, garajes, algunos vestíbulos) exentas de exigencia de iluminación/ventilación natural; rehabilitaciones donde la envolvente preexistente no permite ampliar huecos sin alterar fachadas protegidas.

### 8. Casos donde no existe una respuesta correcta
Patios mancomunados entre parcelas colindantes, donde el cumplimiento depende de una edificación futura no controlada por el proyecto actual; piezas con iluminación indirecta a través de otra pieza (habitual en rehabilitación), donde el criterio de "cumplimiento" varía mucho entre decretos autonómicos y no hay consenso único.

### 9. Datos mínimos necesarios para poder evaluarlo
Geometría y superficie de cada hueco, orientación de cada fachada, dimensiones y geometría de los patios a los que vierte cada pieza, superficie útil de cada pieza, tipología (para saber qué decreto aplica).

### 10. Nivel de confianza que puede alcanzar el sistema
Alto para el cumplimiento del ratio normativo mínimo; medio para la valoración de "calidad real de luz", que depende de datos que un plano 2D no siempre contiene con fiabilidad (obstrucción de edificios vecinos, geometría exacta de patios ajenos).

### Clasificación en 4 niveles
- **Nivel 1 (hechos objetivos):** superficie de huecos, orientación, dimensiones de patios.
- **Nivel 2 (normativa verificable):** ratios mínimos hueco/superficie e iluminación/ventilación por decreto autonómico.
- **Nivel 3 (buenas prácticas):** margen recomendado sobre el mínimo, orientación preferente por tipo de pieza.
- **Nivel 4 (criterio arquitectónico):** valoración de calidad real de luz más allá del cumplimiento del ratio.

---

## Dominio 5 — Accesibilidad

### 1. Conceptos fundamentales
Itinerario accesible, ancho libre de paso, espacio de giro (⌀1.50m), pendiente máxima de rampa, elemento accesible vs. adaptado, vivienda accesible vs. vivienda practicable/adaptable, ascensor accesible.

### 2. Principios arquitectónicos
La accesibilidad no es una pieza puntual del proyecto (el baño accesible) sino una cualidad de un **recorrido completo**, desde el acceso exterior hasta el interior de cada unidad. Un arquitecto experto revisa el itinerario entero, no elementos sueltos — un baño accesible al final de un pasillo que no cumple el ancho mínimo no sirve de nada.

### 3. Normativa relacionada
CTE DB-SUA (secciones 1 y 9 principalmente, accesibilidad universal), normativa autonómica y a veces municipal de accesibilidad (puede añadir exigencias sobre el CTE estatal), Orden VIV o equivalente autonómica sobre condiciones básicas de accesibilidad, LOE en cuanto a responsabilidad del proyectista.

### 4. Reglas objetivas
Ancho mínimo de itinerario accesible, espacio de giro mínimo en puntos clave (acceso, ante baño accesible), pendiente máxima de rampas según longitud, exigencia de ascensor accesible a partir de determinado número de plantas u ocupantes, dimensiones mínimas de baño accesible.

### 5. Reglas heurísticas (criterio profesional)
Cómo verificar que un itinerario es accesible **de extremo a extremo** y no solo en tramos aislados (el fallo más habitual en proyectos reales); criterio sobre cuándo conviene proyectar más allá del mínimo "accesible" hacia "adaptado" aunque no sea obligatorio, por criterio de futuro-proofing del edificio; cómo valorar soluciones accesibles que cumplen el mínimo normativo pero generan un recorrido incómodo o estigmatizante (accesibilidad "de trámite" frente a accesibilidad bien integrada en el diseño).

### 6. Conflictos habituales con otros dominios
Es uno de los dominios con más conflictos estructurales: con el Dominio 3 (ensanchar pasillos reduce superficie útil de piezas adyacentes), con el Dominio 6 (un itinerario accesible y un recorrido de evacuación no siempre coinciden geométricamente y a veces compiten por el mismo espacio), con el Dominio 9 (la solución más accesible no siempre es la espacialmente más elegante, y un arquitecto experto busca integrarlas, no simplemente coexistir).

### 7. Excepciones
Vivienda unifamiliar donde, según la normativa aplicable, la exigencia de itinerario accesible interior puede no ser obligatoria salvo en accesos comunes o en determinados programas de vivienda protegida; rehabilitaciones donde la imposibilidad técnica o económica desproporcionada de cumplir accesibilidad completa está expresamente contemplada en la normativa (con memoria justificativa).

### 8. Casos donde no existe una respuesta correcta
Rehabilitaciones en edificios protegidos donde cumplir accesibilidad completa exige alterar elementos protegidos — la solución de compromiso depende de negociación con patrimonio, no de una regla aplicable automáticamente; edificios existentes plurifamiliares sin ascensor donde instalarlo es técnicamente posible pero exige sacrificar superficie o luz natural de viviendas existentes, generando un conflicto entre derechos de accesibilidad y derechos adquiridos que la norma no resuelve de forma única.

### 9. Datos mínimos necesarios para poder evaluarlo
Geometría completa del recorrido desde acceso exterior hasta cada unidad y hasta cada baño, tipología (determina si aplica exigencia interior o solo en zonas comunes), número de plantas y existencia de ascensor, anchos y espacios de giro en cada punto del recorrido.

### 10. Nivel de confianza que puede alcanzar el sistema
Alto para tramos individuales medibles geométricamente (anchos, giros, pendientes); medio para la verificación de continuidad del itinerario completo, que requiere un modelo de circulación conectado (no solo piezas aisladas) — exactamente el tipo de análisis que un grafo de circulación resuelve mejor que reglas por pieza sueltas.

### Clasificación en 4 niveles
- **Nivel 1 (hechos objetivos):** anchos, pendientes, espacios de giro medidos en el plano.
- **Nivel 2 (normativa verificable):** mínimos de itinerario accesible según CTE DB-SUA y normativa autonómica.
- **Nivel 3 (buenas prácticas):** proyectar por encima del mínimo "adaptado" cuando sea razonable; verificar continuidad de extremo a extremo.
- **Nivel 4 (criterio arquitectónico):** integración de la solución accesible en el diseño sin que se perciba como añadido de trámite.

---

## Dominio 6 — Evacuación y Seguridad frente a Incendio

### 1. Conceptos fundamentales
Sector de incendio, recorrido de evacuación, longitud máxima de recorrido, ocupación (personas) según uso y superficie, salida de emergencia, resistencia al fuego de compartimentación (EI), reacción al fuego de materiales, escalera protegida/especialmente protegida.

### 2. Principios arquitectónicos
Es el dominio de mayor consecuencia directa sobre vidas humanas de todo el sistema, y un arquitecto experto lo trata con ese peso jerárquico por encima de casi cualquier otro criterio. La lógica de evacuación no es local (una pieza) sino global (el edificio entero como sistema de recorridos y sectores), lo que lo hace estructuralmente parecido en complejidad al Dominio 5.

### 3. Normativa relacionada
CTE DB-SI (todas sus secciones: propagación interior, propagación exterior, evacuación de ocupantes, instalaciones de protección, intervención de bomberos, resistencia estructural al incendio), normativa municipal específica de bomberos si existe (algunos ayuntamientos añaden criterios propios de accesibilidad de bomberos).

### 4. Reglas objetivas
Longitud máxima de recorrido de evacuación según número de salidas disponibles, ocupación calculada por superficie y uso según tablas del DB-SI, anchura mínima de salidas y pasos según ocupación, resistencia al fuego mínima de elementos compartimentadores según uso y altura de evacuación del edificio.

### 5. Reglas heurísticas (criterio profesional)
Cómo estimar ocupación real en programas atípicos no cubiertos exactamente por las tablas del DB-SI; criterio sobre cuándo un recorrido que cumple la longitud máxima en línea recta teórica en realidad, por la geometría real del proyecto, resulta más largo y arriesgado de lo que sugiere el cálculo simplificado; cuándo compensar con protección pasiva adicional un recorrido en el límite normativo, aunque no sea estrictamente exigible.

### 6. Conflictos habituales con otros dominios
Con el Dominio 5: itinerario accesible y recorrido de evacuación accesible no siempre son el mismo recorrido, y ambos deben coexistir. Con el Dominio 9: la sectorización y compartimentación exigida puede romper relaciones espaciales abiertas que mejoran la calidad percibida. Con el Dominio 10 (Instalaciones): patinillos y registros de instalaciones deben respetar la compartimentación contra incendio, un punto de fallo habitual en obra si no se coordina en proyecto.

### 7. Excepciones
Edificios existentes en rehabilitación donde el DB-SI admite soluciones alternativas o de "menor exigencia justificada" cuando el cumplimiento literal es inviable por la configuración preexistente; usos de pública concurrencia con aforo reducido que pueden acogerse a exigencias simplificadas.

### 8. Casos donde no existe una respuesta correcta
Edificios de uso mixto donde el cómputo de ocupación total combinado (residencial + terciario en planta baja, por ejemplo) admite más de un criterio de cálculo razonable; rehabilitaciones donde ninguna solución técnicamente posible alcanza el cumplimiento literal, y la decisión final es de riesgo asumido y justificado documentalmente, no de cumplimiento binario.

### 9. Datos mínimos necesarios para poder evaluarlo
Geometría completa de recorridos y salidas, uso y superficie de cada sector, número de plantas y altura de evacuación del edificio, ubicación y dimensión de escaleras y salidas.

### 10. Nivel de confianza que puede alcanzar el sistema
Medio hoy, con potencial alto. La medición geométrica de recorridos es automatizable con fiabilidad razonable (como ya demuestra el análisis de circulación existente en el sistema actual), pero el cálculo correcto de ocupación, sectorización y resistencia al fuego real de la compartimentación requiere datos constructivos que un plano 2D de distribución no contiene por sí solo (composición de muros, no solo su posición).

### Clasificación en 4 niveles
- **Nivel 1 (hechos objetivos):** longitud y geometría de recorridos, superficie de cada sector.
- **Nivel 2 (normativa verificable):** longitud máxima de recorrido, ocupación según tablas DB-SI, anchura mínima de salidas.
- **Nivel 3 (buenas prácticas):** margen de seguridad sobre el máximo normativo en programas de alta ocupación.
- **Nivel 4 (criterio arquitectónico):** valoración de riesgo real de un recorrido en el límite normativo, más allá del cálculo simplificado.

---

## Dominio 7 — Acústica

### 1. Conceptos fundamentales
Aislamiento acústico a ruido aéreo entre unidades independientes, aislamiento a ruido de impactos, adyacencia crítica (piezas de dos unidades distintas compartiendo partición), ruido exterior y aislamiento de fachada, tiempo de reverberación en zonas comunes.

### 2. Principios arquitectónicos
El aislamiento acústico real depende de la solución constructiva (masa, capas, desolidarización), no solo de la geometría de la distribución — es el dominio donde la distancia entre "lo que se puede saber con un plano de distribución" y "lo que realmente determina el cumplimiento normativo" es mayor de todos los dominios normativos. Un arquitecto experto sabe que puede señalar **riesgo de adyacencia**, pero no puede certificar aislamiento real sin datos constructivos.

### 3. Normativa relacionada
CTE DB-HR (protección frente al ruido), normativa autonómica o municipal complementaria de ruido ambiental si existe.

### 4. Reglas objetivas
Aislamiento mínimo a ruido aéreo exigido entre unidades de uso independiente, aislamiento mínimo frente a ruido de instalaciones y de impactos en forjados entre unidades distintas, exigencias específicas para determinadas adyacencias (dormitorio junto a zonas comunes ruidosas, por ejemplo).

### 5. Reglas heurísticas (criterio profesional)
Qué adyacencias geométricas son de riesgo acústico alto aunque el cálculo formal de aislamiento no se haya hecho todavía (dormitorio junto a caja de escalera, junto a cuarto de instalaciones, junto a salón de otra unidad); criterio sobre cuándo recomendar refuerzo constructivo preventivo en una adyacencia de riesgo, sin poder afirmar con certeza que incumplirá.

### 6. Conflictos habituales con otros dominios
Con el Dominio 4: huecos grandes hacia fachadas con ruido exterior tensionan el aislamiento acústico de fachada exigido. Con el Dominio 10: patinillos de instalaciones compartidos entre unidades son un punto de fuga acústica habitual que la geometría de distribución por sí sola no revela. Con el Dominio 9: la solución acústicamente más segura (muros macizos continuos) puede limitar la flexibilidad espacial deseada.

### 7. Excepciones
Piezas no habitables o de uso técnico exentas de exigencia de aislamiento entre sí; rehabilitaciones donde la estructura existente limita las soluciones constructivas posibles de mejora acústica.

### 8. Casos donde no existe una respuesta correcta
Evaluación de aislamiento real sin conocer la composición constructiva de la partición — en ausencia de ese dato, cualquier afirmación de "cumple" o "no cumple" el valor exacto en dB sería una afirmación no verificable, y el sistema debe decirlo explícitamente como limitación, no aproximarlo como si fuera un hecho.

### 9. Datos mínimos necesarios para poder evaluarlo
Adyacencia real entre piezas de unidades independientes (con tolerancia geométrica a huecos de plano, no solo intersección literal de polígonos), uso de cada pieza adyacente, y — para una evaluación real de cumplimiento, no solo de riesgo — la composición constructiva de la partición, dato que hoy no está disponible en un DXF de distribución.

### 10. Nivel de confianza que puede alcanzar el sistema
Bajo-medio, y estructuralmente limitado: el sistema puede alcanzar confianza alta señalando **dónde existe riesgo de adyacencia acústica crítica**, pero no puede, sin datos constructivos adicionales, certificar cumplimiento normativo real en decibelios. Esta es una limitación honesta que debe comunicarse siempre, no disimularse con una cifra aproximada presentada como si fuera precisa.

### Clasificación en 4 niveles
- **Nivel 1 (hechos objetivos):** adyacencia geométrica real entre piezas de unidades distintas.
- **Nivel 2 (normativa verificable):** valores mínimos de aislamiento exigidos por tipo de adyacencia según DB-HR (aplicable solo si se conoce la solución constructiva).
- **Nivel 3 (buenas prácticas):** evitar dormitorios junto a zonas de instalaciones o circulación ruidosa incluso sin cálculo formal.
- **Nivel 4 (criterio arquitectónico):** decisión de cuánto margen preventivo añadir en una adyacencia de riesgo sin dato constructivo confirmado.

---

## Dominio 8 — Eficiencia Energética y Envolvente Térmica

### 1. Conceptos fundamentales
Zona climática (definida por ubicación, CTE la codifica por letra/número), transmitancia térmica de la envolvente, factor solar de huecos, compacidad del edificio (relación superficie envolvente/volumen), puente térmico, demanda energética de calefacción y refrigeración.

### 2. Principios arquitectónicos
El comportamiento térmico depende de la envolvente completa como sistema (opacos + huecos + orientación + compacidad), no de un elemento aislado — un hueco grande bien orientado a sur en zona fría puede ser positivo, el mismo hueco en zona cálida o mal orientado es un problema. Un arquitecto experto nunca juzga un hueco sin conocer la zona climática real.

### 3. Normativa relacionada
CTE DB-HE (ahorro de energía, en sus distintas secciones: limitación de demanda energética, rendimiento de instalaciones), Reglamento de Instalaciones Térmicas en los Edificios (RITE) para la parte de instalaciones, certificación energética (procedimiento derivado, no normativa de diseño en sí).

### 4. Reglas objetivas
Transmitancia térmica máxima de cada elemento de la envolvente según zona climática, factor solar máximo de huecos según orientación y zona, límites de demanda energética global del edificio.

### 5. Reglas heurísticas (criterio profesional)
Cómo valorar la coherencia entre proporción de huecos y orientación antes incluso de tener datos precisos de transmitancia (una fachada norte con mucho hueco es una señal de alerta térmica temprana, independientemente del cálculo formal); criterio sobre cuándo la compacidad de la propuesta compromete de partida cualquier posibilidad de buen comportamiento energético, antes de entrar en detalle de materiales.

### 6. Conflictos habituales con otros dominios
Con el Dominio 4: más superficie de hueco mejora iluminación y empeora comportamiento térmico, tensión directa y constante. Con el Dominio 1: la orientación y compacidad posibles están condicionadas por retranqueos y alineaciones obligatorias del planeamiento. Con el Dominio 9: la solución más eficiente energéticamente (compacta, huecos reducidos y bien orientados) no siempre coincide con la solución espacialmente más generosa o luminosa deseada.

### 7. Excepciones
Rehabilitaciones donde la envolvente existente no puede modificarse sustancialmente (fachadas protegidas), sujetas a régimen de mejora parcial en lugar de cumplimiento pleno; edificios muy pequeños o auxiliares exentos de parte de las exigencias.

### 8. Casos donde no existe una respuesta correcta
Rehabilitaciones donde mejorar la envolvente exige alterar el aspecto exterior protegido de un edificio catalogado — el conflicto entre exigencia energética y protección patrimonial no tiene una solución universal, depende de negociación caso a caso con el organismo de patrimonio competente.

### 9. Datos mínimos necesarios para poder evaluarlo
Zona climática real del emplazamiento (no un valor por defecto), geometría y orientación de huecos y opacos, compacidad del volumen edificado, y — para un cálculo de demanda real, no solo un indicador temprano — composición constructiva de la envolvente, dato no disponible en un DXF de distribución.

### 10. Nivel de confianza que puede alcanzar el sistema
Medio. Alto para señales tempranas de coherencia geométrica huecos/orientación/zona climática; bajo para el cálculo formal de demanda energética, que requiere datos constructivos de los que hoy el sistema no dispone — de nuevo, una limitación a comunicar explícitamente, no a aproximar como si fuera un cálculo completo.

### Clasificación en 4 niveles
- **Nivel 1 (hechos objetivos):** superficie y orientación de huecos y opacos, zona climática del emplazamiento.
- **Nivel 2 (normativa verificable):** transmitancias y factores solares máximos por zona climática (aplicables con dato constructivo real).
- **Nivel 3 (buenas prácticas):** coherencia recomendada entre proporción de hueco y orientación por zona climática.
- **Nivel 4 (criterio arquitectónico):** equilibrio entre eficiencia energética e iluminación/calidad espacial deseada.

---

## Dominio 9 — Calidad Espacial (habitabilidad subjetiva)

### 1. Conceptos fundamentales
Proporción y forma de una pieza, relación visual y física con el exterior, privacidad entre piezas, jerarquía espacial (piezas principales vs. servidoras), fluidez de circulación interna, espacio residual o "muerto", escala humana (relación superficie/altura percibida).

### 2. Principios arquitectónicos
Esta es la frontera entre "legal" y "bueno" — un proyecto puede cumplir el 100% de la normativa de las capas anteriores y ser, aun así, un mal proyecto. Un arquitecto experto emite juicio de calidad espacial constantemente, incluso cuando no hay ninguna norma que lo exija, porque es precisamente lo que un cliente espera de un profesional y no de un simple verificador normativo.

### 3. Normativa relacionada
No hay normativa directa de obligado cumplimiento para la mayoría de estos criterios — es, por definición, el dominio menos normativo y más profesional de todos. Puede haber referencias indirectas (proporciones máximas en algún decreto autonómico de habitabilidad para evitar piezas "tubo" no funcionales), pero la mayor parte de este dominio es juicio, no ley.

### 4. Reglas objetivas
Las pocas que existen son proxies geométricos calculables: relación de aspecto máxima razonable de una pieza, profundidad máxima razonable respecto al hueco de luz principal, proporción superficie/altura dentro de un rango de confort.

### 5. Reglas heurísticas (criterio profesional)
La inmensa mayoría del conocimiento de este dominio es heurístico: relación adecuada entre pieza principal y piezas servidoras, ausencia de espacios residuales sin uso claro, privacidad entre dormitorios y zonas comunes, calidad de la relación visual con el exterior más allá del cumplimiento mínimo de iluminación, coherencia entre la jerarquía de usos declarada y la jerarquía espacial real construida.

### 6. Conflictos habituales con otros dominios
Con casi todos: es, junto con el Dominio 12, el dominio que más tensiones absorbe del resto — la solución normativamente correcta en accesibilidad, evacuación o térmica casi siempre exige un coste espacial que este dominio es el que evalúa y hace visible. Su función no es solo evaluar por sí mismo, sino **hacer explícito el precio en calidad** de las decisiones tomadas en otros dominios.

### 7. Excepciones
No aplica en el sentido normativo — no hay "excepciones" a un juicio de calidad, hay contextos que cambian el criterio (una vivienda de bajo coste no se juzga con el mismo listón que una de alta gama, sin que eso signifique menor rigor, sino un rango de referencia distinto).

### 8. Casos donde no existe una respuesta correcta
La mayoría de este dominio, por naturaleza. La valoración de calidad espacial tiene un componente de gusto y de contexto cultural/de mercado que no converge en una única respuesta correcta entre arquitectos expertos distintos — dos profesionales senior pueden discrepar legítimamente sobre si una solución es buena, sin que ninguno esté "equivocado". El sistema debe modelar esto como rango de valoración razonado, no como veredicto único.

### 9. Datos mínimos necesarios para poder evaluarlo
Geometría completa, resultados ya calculados de los dominios normativos anteriores (para no repetir juicio ya hecho en otro dominio), relaciones de circulación entre piezas, altura libre.

### 10. Nivel de confianza que puede alcanzar el sistema
Medio, y con un techo estructural distinto al resto de dominios: aquí "confianza alta" no significa "una única respuesta correcta" sino "un razonamiento bien fundamentado y consistente", porque la naturaleza del conocimiento es de juicio, no de verificación. Un sistema experto maduro en este dominio se mide por la calidad de su razonamiento explicado, no por la precisión de una cifra.

### Clasificación en 4 niveles
- **Nivel 1 (hechos objetivos):** geometría, proporciones, superficies medidas directamente.
- **Nivel 2 (normativa verificable):** los pocos proxies geométricos con respaldo normativo indirecto (proporciones máximas de algún decreto autonómico).
- **Nivel 3 (buenas prácticas):** heurísticas de proporción, profundidad de luz, ausencia de espacio residual, ampliamente compartidas entre profesionales.
- **Nivel 4 (criterio arquitectónico):** la práctica totalidad del dominio — juicio de calidad espacial propiamente dicho, donde caben discrepancias legítimas entre expertos.

---

## Dominio 10 — Compatibilidad de Instalaciones

### 1. Conceptos fundamentales
Patinillo de instalaciones, recorrido de fontanería/saneamiento/electricidad/climatización, coherencia vertical entre plantas (huecos técnicos alineados), espacio técnico mínimo, compatibilidad entre distribución arquitectónica y viabilidad de instalación.

### 2. Principios arquitectónicos
Las instalaciones no son un añadido posterior al diseño — un arquitecto experto sabe que una distribución que ignora la viabilidad de instalaciones genera sobrecostes y soluciones forzadas en obra que degradan tanto el proyecto como, a menudo, la calidad espacial ya evaluada en el Dominio 9. La compatibilidad vertical entre plantas (que los núcleos húmedos se apilen) es el criterio más determinante y el más fácil de verificar sin datos de instalaciones detallados.

### 3. Normativa relacionada
CTE DB-HS (secciones de suministro de agua y evacuación), RITE para climatización, Reglamento Electrotécnico de Baja Tensión (REBT) para electricidad — normativa de instalaciones propiamente dicha, no de arquitectura, pero que condiciona la viabilidad de la distribución.

### 4. Reglas objetivas
Existencia de espacio técnico mínimo dedicado, coherencia de posición vertical de núcleos húmedos entre plantas consecutivas (cuando hay más de una planta).

### 5. Reglas heurísticas (criterio profesional)
Cómo detectar, solo con la geometría en planta, distribuciones que previsiblemente generarán recorridos de instalaciones excesivamente largos o forzados (cocina y baños muy distantes entre sí sin justificación); criterio sobre cuándo la falta de apilamiento vertical entre plantas es asumible con una solución técnica razonable y cuándo es un problema estructural de la distribución que debería replantearse.

### 6. Conflictos habituales con otros dominios
Con el Dominio 7 (Acústica): patinillos compartidos entre unidades son puntos de fuga acústica. Con el Dominio 6: los recorridos de instalaciones deben respetar la compartimentación contra incendio, un punto de fricción habitual entre el proyecto de arquitectura y el de instalaciones si no se coordinan desde el principio. Con el Dominio 9: reservar espacio técnico suficiente compite por superficie útil con la calidad espacial deseada.

### 7. Excepciones
Rehabilitaciones donde la estructura y las instalaciones existentes condicionan fuertemente la distribución posible, invirtiendo el orden habitual (aquí la instalación existente condiciona el diseño, no al revés).

### 8. Casos donde no existe una respuesta correcta
Sin sección constructiva ni proyecto de instalaciones, cualquier verificación de viabilidad real de instalaciones es, en el mejor de los casos, una estimación razonada — este dominio, evaluado solo desde un plano 2D de distribución, tiene un techo de certeza estructuralmente bajo, y el sistema debe comunicarlo así, no como una conclusión firme.

### 9. Datos mínimos necesarios para poder evaluarlo
Geometría en planta, posición relativa de núcleos húmedos y espacios técnicos entre plantas si existen varias, ubicación declarada de patinillos si el proyecto los define.

### 10. Nivel de confianza que puede alcanzar el sistema
Bajo-medio, y de los dominios con techo más bajo de todo el mapa mientras la fuente de datos sea un DXF 2D sin sección constructiva. Su valor real como dominio automatizado crece directamente con el paso a un flujo de datos más rico (BIM), no con más reglas internas sobre los mismos datos limitados.

### Clasificación en 4 niveles
- **Nivel 1 (hechos objetivos):** posición en planta de núcleos húmedos y espacios técnicos.
- **Nivel 2 (normativa verificable):** exigencias mínimas de espacio técnico según instalación (aplicables solo con datos de instalaciones reales).
- **Nivel 3 (buenas prácticas):** apilamiento vertical de núcleos húmedos entre plantas, proximidad razonable entre cocina y baños.
- **Nivel 4 (criterio arquitectónico):** valoración de si una distribución sin datos de instalaciones detallados es, aun así, previsiblemente viable.

---

## Dominio 11 — Coherencia Estructural Geométrica

### 1. Conceptos fundamentales
Luz estructural (distancia entre apoyos), continuidad vertical de soportes entre plantas, voladizo y su justificación, malla estructural coherente con la distribución, punto de apoyo.

### 2. Principios arquitectónicos
Este dominio no calcula estructura — evalúa si la distribución propuesta es **geométricamente razonable** para un sistema estructural convencional, del mismo modo que un arquitecto experto, sin hacer ningún cálculo, detecta a primera vista una luz excesiva o una falta de continuidad de soportes que "no cuadra". Es un filtro de sentido común estructural, no un sustituto del cálculo real.

### 3. Normativa relacionada
Código Estructural (antigua normativa de hormigón/acero unificada), Documentos Básicos de seguridad estructural del CTE (DB-SE y sus derivados) — normativa que este dominio no aplica en detalle, pero cuyo marco conceptual (luces razonables, continuidad de cargas) sí utiliza como referencia de coherencia.

### 4. Reglas objetivas
Prácticamente ninguna a este nivel de abstracción sin cálculo real — lo más objetivable es la detección geométrica de continuidad o discontinuidad de elementos verticales entre plantas consecutivas, cuando existe información de varias plantas.

### 5. Reglas heurísticas (criterio profesional)
Umbrales razonables de luz libre según tipología de forjado habitual antes de considerar necesaria una solución estructural especial; detección de voladizos aparentes sin apoyo o refuerzo evidente en el plano; señales de alerta cuando la distribución de una planta superior no guarda relación de apoyo con la inferior.

### 6. Conflictos habituales con otros dominios
Con el Dominio 9: una malla estructural coherente puede imponer restricciones a la libertad espacial deseada. Con el Dominio 1: alturas y volumetría permitidas por el planeamiento condicionan qué sistema estructural es razonable. Es, en general, el dominio con menos conflictos activos con los demás porque actúa como una validación de fondo, no como un generador de exigencias frecuentes.

### 7. Excepciones
Proyectos con sistema estructural expresamente singular (grandes luces buscadas de forma deliberada, estructura vista como elemento de diseño) donde los umbrales "razonables" convencionales no aplican por decisión consciente de proyecto, no por error.

### 8. Casos donde no existe una respuesta correcta
Sin cálculo estructural real, cualquier "alerta" de este dominio es una señal de atención, no una verdad verificada — una luz que parece excesiva puede ser perfectamente viable con un sistema estructural adecuado no visible en el plano de distribución. El sistema debe presentarlo siempre como aviso a revisar por el técnico competente, nunca como una conclusión estructural firme.

### 9. Datos mínimos necesarios para poder evaluarlo
Geometría en planta, y — de forma importante — geometría de otras plantas del mismo edificio si existen, para verificar continuidad vertical; sin ese dato, el dominio solo puede evaluar razonabilidad de luces en una planta aislada.

### 10. Nivel de confianza que puede alcanzar el sistema
Bajo, y deliberadamente así — es el dominio donde más explícitamente el sistema debe declararse un apoyo de primera revisión, nunca un sustituto del juicio de un arquitecto o ingeniero estructurista. Su valor crece mucho más con datos multiplanta y con un flujo BIM (donde el sistema estructural puede ser explícito) que con reglas adicionales sobre plantas aisladas en 2D.

### Clasificación en 4 niveles
- **Nivel 1 (hechos objetivos):** geometría en planta de posibles elementos de apoyo, luces aparentes entre ellos.
- **Nivel 2 (normativa verificable):** prácticamente inaplicable a este nivel de abstracción sin cálculo real.
- **Nivel 3 (buenas prácticas):** umbrales de luz razonable según tipología de forjado habitual.
- **Nivel 4 (criterio arquitectónico):** práctica totalidad del dominio — es, estructuralmente, el dominio con mayor proporción de Nivel 4 de todo el mapa.

---

## Dominio 12 — Efectos en Cadena y Resolución de Conflictos

### 1. Conceptos fundamentales
Conflicto entre criterios (dos exigencias legítimas que tensionan la misma decisión de diseño), síntoma vs. causa raíz (varios hallazgos aparentemente distintos que son, en realidad, la misma tensión de fondo), coste de resolución (qué se sacrifica en un dominio al resolver un problema en otro).

### 2. Principios arquitectónicos
Este es el dominio que reproduce lo que distingue a un arquitecto sénior de una checklist: la capacidad de sostener varios criterios a la vez y anticipar que resolver un problema aquí probablemente crea uno allí. No tiene normativa propia — su conocimiento es sobre **relaciones entre dominios**, no sobre ningún dominio en sí mismo.

### 3. Normativa relacionada
Ninguna directamente — este dominio no cita código normativo propio, opera exclusivamente sobre las conclusiones ya producidas por los demás dominios (todos los cuales sí tienen su normativa propia, referenciada en sus secciones correspondientes).

### 4. Reglas objetivas
Los pares de conflicto estructuralmente conocidos y recurrentes (luz vs. térmica, accesibilidad vs. superficie útil, evacuación vs. calidad espacial, acústica vs. instalaciones, urbanístico vs. habitabilidad) pueden documentarse como relaciones objetivas conocidas, aunque su resolución en un caso concreto no lo sea.

### 5. Reglas heurísticas (criterio profesional)
Cómo priorizar cuál de los dos criterios en conflicto cede primero (siguiendo la jerarquía general: bloqueante > riesgo variable > recomendable > preferencial, ver `BRAIN_ARCHITECTURE.md`), y cómo detectar que varios hallazgos individuales reportados por dominios distintos son, en realidad, síntomas de la misma causa raíz (por ejemplo: un pasillo estrecho puede generar simultáneamente un aviso de accesibilidad y uno de evacuación — son el mismo problema, no dos).

### 6. Conflictos habituales con otros dominios
Por definición, todos — es el único dominio cuya función es precisamente detectar y mediar conflictos entre los demás. No tiene "conflictos propios" en el mismo sentido; su trabajo consiste en gestionar los de los demás.

### 7. Excepciones
No aplica en sentido normativo — no hay excepción a "puede haber conflicto", solo casos donde el conflicto detectado resulta, tras análisis, no ser real (falsos positivos de correlación entre hallazgos que en realidad son independientes).

### 8. Casos donde no existe una respuesta correcta
Es, junto con el Dominio 9, el dominio con mayor proporción de decisiones sin respuesta única — cuando dos criterios legítimos compiten por el mismo espacio de diseño (accesibilidad vs. superficie útil, por ejemplo), no hay una resolución "correcta" universal, hay una decisión de proyecto que un arquitecto experto toma con criterio y que el sistema, como mucho, puede exponer con claridad para que se tome informadamente.

### 9. Datos mínimos necesarios para poder evaluarlo
Las salidas ya calculadas de todos los demás dominios — nunca su geometría cruda ni sus reglas internas (límite de diseño explícito en `BRAIN_ARCHITECTURE.md`, necesario para que la complejidad de mantenimiento no crezca de forma combinatoria).

### 10. Nivel de confianza que puede alcanzar el sistema
Bajo-medio hoy porque casi no existe conocimiento acumulado y documentado todavía (el código actual tiene la intención pero no la implementación real, ver `TECH_REVIEW.md`); potencialmente el dominio de mayor valor estratégico a largo plazo si se alimenta con años de conflictos reales resueltos y su resultado — es, según `MOAT_ANALYSIS.md` y `DESTROY_ARCHMUSE.md`, el tipo de conocimiento más difícil de copiar por un competidor.

### Clasificación en 4 niveles
- **Nivel 1 (hechos objetivos):** ninguno propio — consume los de los demás dominios.
- **Nivel 2 (normativa verificable):** ninguno propio.
- **Nivel 3 (buenas prácticas):** catálogo documentado de pares de conflicto estructuralmente conocidos y recurrentes.
- **Nivel 4 (criterio arquitectónico):** la práctica totalidad del dominio — priorización y resolución de conflictos concretos entre criterios legítimos.

---

## Dominio 13 — Riesgo de Visado y Responsabilidad Profesional

### 1. Conceptos fundamentales
Reparo de visado colegial, documentación justificativa de solución de zona gris, responsabilidad del proyectista según la LOE, memoria de cumplimiento normativo, riesgo de reclamación post-entrega.

### 2. Principios arquitectónicos
Este dominio no evalúa si el proyecto es correcto técnicamente (eso ya lo hicieron los dominios normativos) — evalúa si el proyecto, y su documentación, **resiste el escrutinio administrativo y la responsabilidad profesional** que asume quien lo firma. Un arquitecto experto sabe que un hallazgo técnico menor mal documentado puede generar más fricción de visado que un hallazgo técnico mayor bien justificado.

### 3. Normativa relacionada
LOE (Ley de Ordenación de la Edificación — agentes, responsabilidades, garantías), normativa colegial de visado (varía por colegio profesional territorial, no es uniforme en toda España), criterios internos de revisión de cada colegio (a menudo no publicados formalmente, son conocimiento de práctica profesional acumulada).

### 4. Reglas objetivas
Prácticamente ninguna a nivel nacional único — los criterios de visado varían por colegio profesional territorial y no siempre están codificados de forma pública y verificable automáticamente.

### 5. Reglas heurísticas (criterio profesional)
Qué tipo de hallazgos suelen generar reparo de visado con más frecuencia según la experiencia acumulada (independientemente de si son los técnicamente más graves); qué nivel de documentación justificativa suele ser suficiente para defender una solución de zona gris ante un colegio o ante una reclamación posterior; criterio sobre cuándo un hallazgo de riesgo variable (ver jerarquía del Dominio 12) merece memoria justificativa explícita aunque no sea estrictamente exigida.

### 6. Conflictos habituales con otros dominios
Con el Dominio 12: un conflicto en cadena mal resuelto o mal documentado es, casi siempre, un riesgo de visado mayor que un incumplimiento aislado bien identificado. Con todos los dominios normativos (1-8): cualquier hallazgo de riesgo variable de cualquiera de ellos es materia prima directa de este dominio.

### 7. Excepciones
No aplica en sentido normativo estricto — este dominio es, por naturaleza, la gestión de la excepción y la zona gris de los demás.

### 8. Casos donde no existe una respuesta correcta
Casi todo el dominio, por definición — evalúa exactamente las situaciones donde el cumplimiento normativo puro no es binario y depende de criterio de interpretación, tanto del proyectista como del técnico revisor de turno en el colegio, que puede variar entre revisores del mismo colegio.

### 9. Datos mínimos necesarios para poder evaluarlo
Las salidas de todos los dominios normativos (especialmente los hallazgos de riesgo variable, no solo los bloqueantes), y — dato que hoy no existe en ningún sitio del sistema — una base de conocimiento propia sobre criterios reales de visado acumulados por experiencia, que debe construirse activamente, no puede derivarse solo de la geometría del proyecto.

### 10. Nivel de confianza que puede alcanzar el sistema
Bajo hoy porque el conocimiento de base casi no existe todavía en ninguna forma estructurada; es, de los 14 dominios, el que depende de forma más directa de acumulación de experiencia real y de relación institucional (colegios, aseguradoras) más que de análisis geométrico — su madurez está más ligada a la estrategia de negocio (`MOAT_ANALYSIS.md`, `NORTH_STAR_2031.md`) que a mejoras técnicas internas.

### Clasificación en 4 niveles
- **Nivel 1 (hechos objetivos):** ninguno propio.
- **Nivel 2 (normativa verificable):** LOE en cuanto a marco general de responsabilidad, no en criterios específicos de visado.
- **Nivel 3 (buenas prácticas):** patrones de documentación justificativa que suelen resistir revisión de visado.
- **Nivel 4 (criterio arquitectónico):** la práctica totalidad del dominio.

---

## Dominio 14 — Benchmark de Mercado y Posicionamiento

### 1. Conceptos fundamentales
Comparable de mercado, percentil de posicionamiento, eficiencia superficie útil/construida como métrica de valor percibido, rango de mercado de un proyecto (económico/medio/alto).

### 2. Principios arquitectónicos
Un arquitecto experto con años de práctica tiene, informalmente, un sentido de "esto está por encima o por debajo de lo habitual" basado en proyectos reales vistos a lo largo de su carrera — este dominio intenta formalizar ese sentido, pero solo tiene sentido si se construye sobre datos reales acumulados, nunca sobre una estimación presentada como si fuera un dato de mercado real.

### 3. Normativa relacionada
Ninguna — es el único dominio de los 14 sin ninguna base normativa, puramente de mercado y posicionamiento comercial.

### 4. Reglas objetivas
Ninguna en sentido normativo; las únicas "reglas objetivas" posibles aquí son estadísticas calculadas sobre un conjunto real de datos (medias, percentiles), y solo son válidas si ese conjunto de datos es real y suficientemente amplio.

### 5. Reglas heurísticas (criterio profesional)
Qué métricas son realmente indicativas de valor percibido de mercado (eficiencia útil/construida, calidad espacial relativa) frente a cuáles son ruido estadístico sin relación real con percepción de valor.

### 6. Conflictos habituales con otros dominios
Con el Dominio 3 y el 9 principalmente: las métricas de comparación se construyen sobre resultados ya calculados por esos dominios, no sobre datos propios.

### 7. Excepciones
No aplica de forma significativa.

### 8. Casos donde no existe una respuesta correcta
Comparar proyectos de contextos de mercado muy distintos (ubicación, momento temporal, segmento) sin normalizar correctamente introduce comparaciones engañosas — sin ese cuidado metodológico, cualquier percentil presentado es, en la práctica, una afirmación falsa aunque tenga apariencia numérica precisa.

### 9. Datos mínimos necesarios para poder evaluarlo
Una base de datos real y suficientemente amplia de proyectos evaluados previamente, con metadatos comparables (tipología, ubicación, rango de mercado, fecha) — dato que **hoy no existe** en el sistema.

### 10. Nivel de confianza que puede alcanzar el sistema
Nulo por diseño hasta que exista una base de datos real. Este no es un límite técnico a mejorar con más reglas — es una condición de activación: el dominio **no debe producir ninguna salida** mientras no haya datos reales suficientes, exactamente como ya se señaló como error grave del sistema actual (el percentil `TIPOLOGIA_BENCHMARKS` fabricado, ver `PROJECT_AUDIT.md` y `TECH_REVIEW.md`). Repetir ese error aquí, en un mapa de conocimiento que se supone que lo corrige, sería la contradicción más grave posible de todo este documento.

### Clasificación en 4 niveles
- **Nivel 1 (hechos objetivos):** métricas propias del proyecto evaluado (superficie útil/construida, etc.), ya calculadas por otros dominios.
- **Nivel 2 (normativa verificable):** no aplica — dominio sin base normativa.
- **Nivel 3 (buenas prácticas):** selección de métricas realmente indicativas de valor de mercado, y normalización correcta por contexto antes de comparar.
- **Nivel 4 (criterio arquitectónico):** interpretación cualitativa de una posición de mercado más allá del número — y, mientras no haya datos reales, la decisión de no emitir ningún veredicto en absoluto.

---

## Lagunas importantes de conocimiento detectadas

Estas son las carencias que aparecen de forma transversal al construir este mapa y que ningún dominio individual puede resolver por sí solo — son, en conjunto, la lista más honesta de "lo que ArchMuse todavía no sabe":

1. **No existe hoy ninguna fuente de datos constructivos** (composición de muros, forjados, envolvente). Esto limita estructuralmente el techo de confianza de los Dominios 7 (Acústica), 8 (Térmica) y 11 (Estructura) — los tres coinciden en depender de un dato que un DXF de distribución 2D nunca contiene. Es la misma laguna, repetida en tres dominios distintos, no tres problemas independientes.

2. **No existe integración con fuentes urbanísticas oficiales** (planeamiento municipal, catastro). El Dominio 1 depende enteramente de esto para pasar de confianza baja-media a alta, y hoy no hay ningún dato de entrada de este tipo en el sistema.

3. **No existe ninguna base de conocimiento sobre criterios reales de visado** (Dominio 13). Es, de los 14 dominios, el que parte de más cerca de cero — no es una laguna de reglas sino de la materia prima misma (experiencia acumulada, relación con colegios profesionales) que el dominio necesita para existir.

4. **No existe ninguna base de datos real de proyectos comparables** (Dominio 14). Ya se identificó el riesgo de llenar este vacío con datos fabricados — la laguna correcta a señalar no es "faltan reglas" sino "falta la disciplina de no producir nada hasta tener datos reales", que debe mantenerse activamente, no una sola vez.

5. **No existe un modelo de coherencia entre plantas** cuando el proyecto tiene más de un nivel — afecta directamente a los Dominios 10 (Instalaciones) y 11 (Estructura), ambos dependientes de continuidad vertical, y hoy el sistema evalúa fundamentalmente en clave de planta aislada.

6. **El Dominio 12 (Efectos en Cadena) es, hoy, el que menos conocimiento documentado tiene de los 14** a pesar de ser el de mayor valor estratégico señalado en `BRAIN_ARCHITECTURE.md` — no hay todavía un catálogo real de conflictos observados y sus resoluciones históricas, que es exactamente el tipo de conocimiento que más tiempo cuesta acumular y más difícil es de copiar. Es la laguna con mayor coste de oportunidad de las seis.

Ninguna de estas seis lagunas se resuelve con más reglas dentro de un dominio existente — todas requieren, o bien una fuente de datos que hoy no existe, o bien un proceso de acumulación de conocimiento (visado, conflictos resueltos, mercado real) que no puede escribirse de una vez: se construye con años de uso real, que es, precisamente, la razón de que este documento se plantee como base para "los próximos años" y no como un catálogo cerrado.
