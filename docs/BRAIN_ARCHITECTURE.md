# BRAIN_ARCHITECTURE.md

**Propósito de este documento:** diseñar la arquitectura de conocimiento del "cerebro" de ArchMuse — no el código, no las clases, no los módulos Python. La pregunta que responde no es "¿cómo lo programamos?" sino "¿cómo debería razonar ArchMuse si tuviera que pensar como un arquitecto sénior con 25 años de experiencia revisando un proyecto por primera vez, y ese razonamiento tuviera que seguir siendo coherente dentro de 10 años, con 500+ reglas activas y equipos distintos añadiendo conocimiento constantemente?"

Todo lo que sigue es intencionadamente independiente de `evaluator.py` y del resto del código actual. El código actual es una implementación parcial y, en partes, incorrecta (ver `TECH_REVIEW.md`) de una fracción de este cerebro. Este documento no describe cómo migrar hacia él — eso es un ejercicio posterior, de refactor, no de diseño. Aquí se diseña la arquitectura ideal de conocimiento sin restricciones del presente.

---

## Parte 1 — Cómo razona un arquitecto sénior (el modelo mental que hay que reproducir)

Antes de dividir el cerebro en dominios, hay que entender qué es lo que se está dividiendo. Un arquitecto con 25 años de experiencia, al recibir un proyecto nuevo por primera vez, no aplica una checklist plana de 500 normas en orden aleatorio. Aplica un embudo de razonamiento con una jerarquía muy clara, en la que cada nivel **acota** el nivel siguiente.

### 1. Qué analiza primero: el marco de lo posible

Lo primero que un arquitecto sénior establece no es si el proyecto "cumple" nada — es **qué es este proyecto y qué le está permitido ser**. Esto incluye el encaje urbanístico (qué se puede construir en ese solar, con qué parámetros) y el programa/tipología (¿vivienda unifamiliar, plurifamiliar, rehabilitación, uso terciario?). Este paso no evalúa el diseño; define el marco legal y funcional dentro del cual todo lo demás tiene sentido. Un arquitecto que se salta este paso puede pasar horas evaluando habitabilidad de un proyecto que ya es inviable por edificabilidad, o aplicando reglas de vivienda plurifamiliar a una rehabilitación donde no aplican.

Esto es, con diferencia, el error individual más caro que puede cometer un sistema de evaluación: **evaluar con el conjunto de reglas equivocado**. (Es, no por casualidad, el bug más grave encontrado en `TECH_REVIEW.md` — la tipología y zona climática reales del proyecto nunca llegaban al motor de reglas, que evaluaba todo con los valores por defecto.)

### 2. Qué analiza después: los hechos geométricos objetivos

Con el marco establecido, el arquitecto sénior extrae los hechos medibles del plano: superficies, dimensiones, proporciones, número de piezas, orientación, huecos. No juzga todavía si están bien o mal — construye primero un modelo mental fiel del objeto que va a evaluar. Un arquitecto sénior desconfía de evaluar sobre datos mal leídos; primero confirma que "ha entendido el plano" antes de opinar sobre él.

### 3. Después: lo que compromete la seguridad de las personas

Aquí es donde empieza el juicio normativo, y el orden importa: lo primero que un arquitecto sénior revisa es lo que pone en riesgo vidas o impide legalmente habitar el edificio — evacuación e incendio, accesibilidad, estructura (a nivel de compatibilidad geométrica). Esto no es una preferencia estética de orden; es una jerarquía de consecuencias. Un fallo aquí no es "una nota a mejorar", es un motivo de rechazo de proyecto o de inhabitabilidad.

### 4. Después: lo que compromete la habitabilidad y el confort

Iluminación y ventilación natural, acústica, eficiencia energética. Son también normativos y obligatorios (CTE), pero su incumplimiento no suele ser tan catastrófico ni tan urgente de resolver como un fallo de evacuación — a menudo son corregibles con soluciones constructivas sin rehacer la distribución.

### 5. Después: lo que compromete la calidad, no la legalidad

Proporciones de las estancias, relación con el exterior, privacidad, lógica de circulación interna, calidad espacial en sentido amplio. Un proyecto puede cumplir el 100% de la normativa y ser un mal proyecto. Un arquitecto sénior sabe distinguir "esto es ilegal" de "esto es legal pero mediocre" — y un cliente que paga por asesoramiento de calidad quiere ambas respuestas, no solo la primera.

### 6. En paralelo, todo el tiempo: los conflictos entre criterios

Esta es la parte que ningún checklist plano captura y que sí hace un arquitecto sénior de forma casi inconsciente: **sabe que resolver un problema en un dominio casi siempre mueve o crea un problema en otro**. Ejemplos reales y recurrentes:

- Ampliar un hueco para cumplir iluminación natural empeora el comportamiento térmico de la envolvente (DB-HE).
- Ensanchar un pasillo para cumplir accesibilidad reduce la superficie útil de las piezas adyacentes, pudiendo hacerlas incumplir superficie mínima.
- Reforzar la compartimentación acústica entre viviendas (más masa, menos huecos en el muro medianero) puede chocar con la distribución de instalaciones o con la geometría estructural existente.
- Cerrar una zona para cumplir sectorización de incendio puede romper la relación visual/espacial que sostenía la calidad espacial de una vivienda abierta.
- Maximizar densidad/superficie vendible (criterio del promotor) tensiona casi todos los mínimos de habitabilidad al mismo tiempo.

Un arquitecto sénior no resuelve estos conflictos dominio a dominio de forma aislada — los sostiene todos a la vez y busca la solución que menos otros criterios sacrifica. Esto es, estructuralmente, la parte más difícil de automatizar, y es la razón por la que el cerebro necesita un **meta-dominio de razonamiento cruzado**, no solo dominios independientes que informan por separado (ver Parte 3).

### 7. Cómo prioriza cuando los criterios entran en conflicto

La priorización no es un promedio ni una votación entre normas. Sigue una jerarquía de consecuencia, en este orden:

1. **Lo obligatorio y bloqueante** (impide la licencia o el visado, o compromete la seguridad de personas) — no es negociable, se resuelve siempre primero, cueste lo que cueste al resto del proyecto.
2. **Lo obligatorio pero de interpretación o de riesgo variable** (normativa ambigua, criterio local del colegio o del técnico municipal, zonas grises de aplicación) — se resuelve con criterio de riesgo, no con certeza absoluta; un arquitecto sénior sabe cuándo algo "probablemente pasa" y cuándo no vale la pena arriesgarse.
3. **Lo recomendable pero no obligatorio** (calidad espacial, buenas prácticas por encima del mínimo) — se mejora si no cuesta sacrificar los dos niveles anteriores, y se sacrifica primero cuando hay que ceder algo.
4. **Lo preferencial o de mercado** (percepción de valor, estética, criterio del cliente) — el último criterio en la jerarquía, y el único donde el arquitecto sénior actúa más como asesor que como garante normativo.

### 8. Cómo llega a una conclusión global

Un arquitecto sénior no entrega "una nota". Entrega un **veredicto en capas**, porque son preguntas distintas con audiencias distintas:

- **¿Es viable?** — binario, basado exclusivamente en lo bloqueante. Si hay algo bloqueante sin resolver, todo lo demás es secundario.
- **¿Es defendible ante el visado / la inspección / el cliente si algo sale mal?** — ponderado por riesgo, no binario. Aquí es donde entra el juicio profesional y la responsabilidad (LOE).
- **¿Es un buen proyecto, más allá del mínimo legal?** — la evaluación de calidad, la que diferencia un proyecto correcto de uno excelente.

Estas tres capas **no se colapsan en un único número**. Colapsarlas es exactamente el error que comete cualquier sistema de "score único" — puede ocultar un problema bloqueante detrás de una buena nota media, o hacer parecer mediocre un proyecto legalmente impecable pero con margen de mejora estético. El cerebro de ArchMuse debe preservar esta separación de capas hasta el final, y el usuario debe poder ver las tres por separado.

---

## Parte 2 — Los dominios de conocimiento

Cada dominio es una unidad de conocimiento independiente: tiene su propio vocabulario, sus propias fuentes normativas, su propio ciclo de vida (algunas normas cambian cada pocos años, otras casi nunca), y puede, en principio, ser mantenido por una persona experta distinta sin que necesite entender los demás dominios en detalle. Esa independencia es la que permite escalar a 500+ reglas sin que el sistema colapse en un monolito ilegible (ver Parte 4).

Los dominios están organizados en capas, siguiendo el mismo orden de razonamiento descrito en la Parte 1. La capa determina *cuándo* actúa el dominio en el flujo global y de qué otras capas puede depender — nunca al revés.

### Capa 0 — Contexto y marco legal

#### Dominio 1: Encaje Normativo-Urbanístico
- **Qué conocimiento representa:** las reglas de planeamiento que definen qué se puede construir en un solar concreto — edificabilidad, ocupación, alturas, retranqueos, usos permitidos, y las particularidades del planeamiento municipal/autonómico aplicable.
- **Qué preguntas intenta responder:** ¿este proyecto es siquiera legalmente posible en este emplazamiento? ¿qué parámetros urbanísticos lo condicionan?
- **Qué datos necesita:** ubicación/parcela, planeamiento vigente en esa zona, normativa municipal y autonómica de aplicación.
- **Qué produce como salida:** el marco de restricciones urbanísticas dentro del cual se evalúa todo lo demás; alertas si el proyecto excede parámetros del solar.
- **De qué otros dominios depende:** de ninguno — es la capa más externa.
- **Prioridad:** Alta a medio plazo. Hoy ArchMuse no lo modela en absoluto (parte del vacío ya señalado en `NORTH_STAR_2031.md`), pero sin él el resto del razonamiento parte de un supuesto no verificado ("este proyecto es viable donde está"), que es exactamente el tipo de supuesto que un arquitecto sénior nunca da por hecho.

#### Dominio 2: Programa y Tipología
- **Qué conocimiento representa:** qué tipo de proyecto es esto — vivienda unifamiliar, plurifamiliar, rehabilitación, uso terciario/dotacional — y qué conjunto de reglas de cada dominio posterior le aplica.
- **Qué preguntas intenta responder:** ¿qué es este proyecto? ¿qué normativa le corresponde y cuál no? ¿qué uso tiene cada espacio del programa?
- **Qué datos necesita:** metadatos del proyecto (tipología declarada), lectura de la geometría y de los usos etiquetados de cada estancia.
- **Qué produce como salida:** la clasificación que activa o desactiva reglas en todos los demás dominios.
- **De qué otros dominios depende:** de ninguno funcionalmente, aunque en la práctica se informa junto al Dominio 1.
- **Prioridad:** Crítica y **ya urgente hoy**, no a futuro. Es exactamente el dominio cuyo fallo de propagación causó el bug más grave documentado en `TECH_REVIEW.md`: cuando este dominio no llega correctamente a los demás, cada dominio posterior evalúa con supuestos por defecto en lugar de los reales. Ningún otro dominio puede compensar un fallo aquí.

### Capa 1 — Hechos objetivos

#### Dominio 3: Geometría y Dimensionado Habitable
- **Qué conocimiento representa:** los mínimos dimensionales y de superficie que debe cumplir cada tipo de estancia según CTE y decretos de habitabilidad autonómicos.
- **Qué preguntas intenta responder:** ¿cada pieza tiene la superficie, el ancho mínimo, la proporción que exige la norma para su uso?
- **Qué datos necesita:** geometría de cada estancia, uso asignado (del Dominio 2), normativa autonómica de habitabilidad aplicable (varía por comunidad autónoma).
- **Qué produce como salida:** lista de incumplimientos dimensionales por estancia, con la referencia normativa exacta.
- **De qué otros dominios depende:** del Dominio 2 (uso/tipología) y, indirectamente, del 1 (para saber qué decreto autonómico de habitabilidad aplica).
- **Prioridad:** Alta. Es el dominio más maduro hoy en el código actual (buena parte de `evaluator.py`), y el de mayor volumen de reglas — probablemente el que primero llegará a decenas de reglas por comunidad autónoma.

#### Dominio 4: Iluminación y Ventilación Natural
- **Qué conocimiento representa:** los requisitos de huecos, superficie de iluminación/ventilación y relación con patios o fachada exterior.
- **Qué preguntas intenta responder:** ¿cada pieza habitable tiene luz y ventilación natural suficiente y en la proporción exigida respecto a su superficie?
- **Qué datos necesita:** geometría de huecos, orientación, relación de cada pieza con el exterior o con patios, dimensiones de los patios.
- **Qué produce como salida:** incumplimientos de iluminación/ventilación por pieza, y qué piezas dependen de un patio insuficiente.
- **De qué otros dominios depende:** del Dominio 3 (geometría de las piezas) y del 2 (uso, ya que los requisitos varían según si la pieza es habitable o no).
- **Prioridad:** Alta. Es normativa obligatoria de aplicación universal, con impacto directo en la viabilidad del diseño.

### Capa 2 — Seguridad de las personas

#### Dominio 5: Accesibilidad
- **Qué conocimiento representa:** los itinerarios accesibles exigidos, las dimensiones mínimas de paso, y qué elementos del edificio deben ser accesibles según la tipología y el número de plantas/viviendas.
- **Qué preguntas intenta responder:** ¿existe un itinerario accesible desde el acceso hasta cada vivienda/local? ¿los baños, pasillos y accesos cumplen las dimensiones mínimas de accesibilidad?
- **Qué datos necesita:** geometría de la circulación, tipología (el requisito varía radicalmente entre unifamiliar y plurifamiliar), número de plantas, existencia de ascensor.
- **Qué produce como salida:** incumplimientos de accesibilidad, marcados con severidad distinta según si comprometen un itinerario obligatorio o un elemento recomendable.
- **De qué otros dominios depende:** del Dominio 2 (tipología — la regla de itinerario accesible en plurifamiliar no debe evaluarse igual en unifamiliar) y del 3 (geometría de circulación).
- **Prioridad:** Crítica. Es normativa de seguridad de personas, no de confort — y es, de nuevo, el dominio directamente afectado por el bug de propagación de tipología documentado en `TECH_REVIEW.md`.

#### Dominio 6: Evacuación y Seguridad frente a Incendio
- **Qué conocimiento representa:** recorridos de evacuación, sectorización, resistencia al fuego de compartimentaciones, salidas exigidas según ocupación.
- **Qué preguntas intenta responder:** ¿los recorridos de evacuación cumplen la longitud y anchura máxima/mínima exigida? ¿la compartimentación entre sectores es la que corresponde al uso y superficie?
- **Qué datos necesita:** geometría de circulación y salidas, uso y superficie de cada sector, número de ocupantes estimado.
- **Qué produce como salida:** incumplimientos de recorridos de evacuación y de sectorización, priorizados por gravedad.
- **De qué otros dominios depende:** del Dominio 2 (uso) y del 3 (geometría).
- **Prioridad:** Crítica. Junto con accesibilidad, es el dominio de mayor consecuencia si falla — y hoy es el que menos desarrollado está en el sistema actual (bloque de adyacencia acústica aparte, `TECH_REVIEW.md` no documenta un motor de evacuación real).

### Capa 3 — Confort y habitabilidad normativa

#### Dominio 7: Acústica
- **Qué conocimiento representa:** los requisitos de aislamiento acústico entre unidades independientes y frente a ruido exterior (DB-HR).
- **Qué preguntas intenta responder:** ¿qué particiones separan unidades independientes y necesitan aislamiento reforzado? ¿qué adyacencias entre usos (p. ej. dormitorio junto a escalera) generan riesgo acústico?
- **Qué datos necesita:** adyacencia real entre estancias de distintas unidades (no solo intersección geométrica — requiere tolerancia a huecos de plano reales, un problema ya identificado en el código actual), uso de cada estancia.
- **Qué produce como salida:** alertas de adyacencias acústicamente críticas sin resolver.
- **De qué otros dominios depende:** del Dominio 2 (qué estancias pertenecen a unidades distintas) y del 3 (geometría de adyacencia).
- **Prioridad:** Media-alta. Normativa obligatoria, pero el riesgo real de incumplimiento es más difícil de detectar solo con geometría — depende de datos constructivos (masa del muro, tipo de partición) que hoy ni el sistema actual ni este diseño conceptual resuelven completamente sin información adicional del proyecto.

#### Dominio 8: Eficiencia Energética y Envolvente Térmica
- **Qué conocimiento representa:** los requisitos de comportamiento térmico de la envolvente según la zona climática del emplazamiento (DB-HE).
- **Qué preguntas intenta responder:** ¿la relación de huecos/opacos y la orientación son coherentes con la exigencia térmica de la zona climática real del proyecto?
- **Qué datos necesita:** zona climática (depende del emplazamiento real, Dominio 1), geometría de huecos y orientación.
- **Qué produce como salida:** alertas de riesgo térmico por zona climática mal considerada.
- **De qué otros dominios depende:** del Dominio 1 (zona climática real) y del 4 (geometría de huecos ya calculada para iluminación).
- **Prioridad:** Media. Es también un dominio directamente afectado por el bug de propagación de zona climática — hoy nunca recibe la zona real del proyecto.

#### Dominio 9: Calidad Espacial (habitabilidad subjetiva)
- **Qué conocimiento representa:** todo lo que separa un proyecto "legal" de un proyecto "bueno" — proporciones, relación con el exterior, privacidad entre piezas, lógica de circulación interna, ausencia de espacios residuales o mal resueltos.
- **Qué preguntas intenta responder:** ¿este proyecto, más allá de cumplir el mínimo, está bien resuelto espacialmente?
- **Qué datos necesita:** geometría completa, resultados ya calculados de los dominios normativos (para no repetir juicios ya hechos), relaciones de circulación.
- **Qué produce como salida:** valoraciones de calidad no bloqueantes, explícitamente separadas de los incumplimientos normativos.
- **De qué otros dominios depende:** de prácticamente todos los anteriores — es el dominio que más se beneficia de que los demás ya hayan hecho su trabajo, porque juzga sobre hechos ya evaluados, no sobre geometría cruda.
- **Prioridad:** Alta estratégicamente (es lo que diferencia a ArchMuse de un simple checklist normativo, ver `MOAT_ANALYSIS.md`), pero solo tiene sentido construirlo bien **después** de que los dominios normativos de las capas 0-2 sean fiables — juzgar calidad sobre datos de tipología/zona incorrectos produce juicios de calidad igual de incorrectos.

### Capa 4 — Sistemas y compatibilidad técnica

#### Dominio 10: Compatibilidad de Instalaciones
- **Qué conocimiento representa:** el espacio y las condiciones que necesitan las instalaciones (fontanería, electricidad, climatización, ventilación mecánica) para ser viables dentro de la distribución propuesta.
- **Qué preguntas intenta responder:** ¿hay espacio técnico suficiente y bien ubicado? ¿la distribución permite recorridos de instalaciones razonables (p. ej. baños apilados entre plantas)?
- **Qué datos necesita:** geometría en planta, posición relativa entre plantas (si hay varias), ubicación de núcleos húmedos.
- **Qué produce como salida:** alertas de incompatibilidad de instalaciones con la distribución propuesta.
- **De qué otros dominios depende:** del Dominio 3 (geometría) y, si hay varias plantas, de un modelo de coherencia vertical que hoy no existe en ningún dominio.
- **Prioridad:** Baja-media a corto plazo. Es de los dominios de mayor complejidad de modelar con la información disponible hoy (DXF 2D, sin sección constructiva) y de menor urgencia normativa directa — buen candidato a quedar fuera de los primeros años del roadmap.

#### Dominio 11: Coherencia Estructural Geométrica
- **Qué conocimiento representa:** no cálculo estructural, sino la compatibilidad geométrica básica entre la distribución propuesta y un sistema estructural razonable (luces excesivas, falta de continuidad vertical de soportes, voladizos no justificados).
- **Qué preguntas intenta responder:** ¿esta distribución es estructuralmente razonable a simple vista, o presenta incoherencias que un arquitecto sénior señalaría de inmediato?
- **Qué datos necesita:** geometría en planta, y si existen, plantas de otros niveles para verificar continuidad vertical.
- **Qué produce como salida:** alertas de incoherencia estructural aparente, explícitamente no vinculantes (no sustituye el cálculo de un ingeniero/arquitecto estructurista).
- **De qué otros dominios depende:** del Dominio 3.
- **Prioridad:** Baja a corto plazo, pero con valor estratégico a medio plazo si ArchMuse avanza hacia proyectos multiplanta y BIM (ver `NORTH_STAR_2031.md`) — mucho más valioso en un flujo BIM-nativo, donde la información estructural es explícita, que sobre DXF 2D.

### Capa 5 — Meta-razonamiento (el dominio que ningún checklist plano tiene)

#### Dominio 12: Efectos en Cadena y Resolución de Conflictos
- **Qué conocimiento representa:** no normativa propia, sino las **relaciones conocidas de tensión entre dominios** — qué patrones de solución en un dominio suelen generar problemas en otro (los ejemplos descritos en la Parte 1.6). Es el dominio que reproduce el instinto del arquitecto sénior de "sostener todos los criterios a la vez".
- **Qué preguntas intenta responder:** si se resuelve el problema X del dominio A de la forma más obvia, ¿qué problema nuevo aparece probablemente en el dominio B? ¿qué incumplimientos detectados por separado son en realidad síntomas del mismo conflicto de fondo?
- **Qué datos necesita:** las salidas ya calculadas de todos los demás dominios — nunca sus reglas internas ni su geometría cruda. Este es el límite de diseño más importante del documento (ver Parte 4): el meta-dominio consume conclusiones, no implementación.
- **Qué produce como salida:** agrupación de incumplimientos relacionados en un mismo conflicto de fondo, y advertencias de "si arreglas esto así, es probable que rompas aquello otro".
- **De qué otros dominios depende:** de todos los de las capas 0-4 — es, por diseño, el único dominio transversal.
- **Prioridad:** Estratégicamente la más alta de todo el documento a medio plazo. Es lo que hoy existe solo de forma incipiente (`chain_effects.py`, confirmado como código muerto en `TECH_REVIEW.md` — es decir, la intención ya estaba ahí, pero nunca se conectó) y es, según `MOAT_ANALYSIS.md` y `DESTROY_ARCHMUSE.md`, el tipo de razonamiento que un competidor no puede replicar copiando reglas sueltas en una semana. Un checklist de 500 reglas sin este dominio sigue siendo un checklist; con él, empieza a parecer criterio profesional.

### Capa 6 — Riesgo profesional y posicionamiento

#### Dominio 13: Riesgo de Visado y Responsabilidad Profesional
- **Qué conocimiento representa:** no es normativa técnica, sino **conocimiento de proceso administrativo y de responsabilidad** — qué tipo de incumplimientos suelen generar reparos en el visado colegial, qué documentación se exige para justificar decisiones límite, y qué implica cada hallazgo en términos de responsabilidad LOE del arquitecto firmante.
- **Qué preguntas intenta responder:** de todos los hallazgos, ¿cuáles son los que realmente pueden bloquear o retrasar el visado? ¿qué documentación adicional debería preparar el arquitecto para defender una decisión de zona gris?
- **Qué datos necesita:** las salidas de todos los dominios normativos, y una base de conocimiento propia sobre criterios reales de visado (que hoy no existe en ningún sitio del sistema — es conocimiento a construir, no a derivar de la geometría).
- **Qué produce como salida:** una capa de riesgo administrativo/profesional, separada de la capa de cumplimiento técnico puro.
- **De qué otros dominios depende:** de todos los normativos (capas 0-3 principalmente) y del Dominio 12 (un conflicto en cadena mal resuelto es, casi siempre, un riesgo de visado mayor que un incumplimiento aislado).
- **Prioridad:** Alta a medio plazo, no inmediata. Es exactamente el tipo de dominio que convierte a ArchMuse de "herramienta que dice qué está mal" a "infraestructura de control de riesgo profesional" — la identidad de marca objetivo descrita en `MOAT_ANALYSIS.md`. Pero depende de que las capas inferiores sean fiables primero; construirlo antes sería, otra vez, construir juicio de riesgo sobre datos incorrectos.

#### Dominio 14: Benchmark de Mercado y Posicionamiento
- **Qué conocimiento representa:** cómo se compara este proyecto con proyectos reales similares (misma tipología, ubicación, rango de superficie) en métricas relevantes de mercado.
- **Qué preguntas intenta responder:** ¿este proyecto está por encima o por debajo de lo habitual del mercado en los aspectos que un cliente valora (relación superficie útil/construida, calidad espacial relativa, eficiencia de la distribución)?
- **Qué datos necesita:** una base de datos real y creciente de proyectos evaluados — **no puede construirse con datos inventados**; hacerlo fue ya identificado como un error grave del sistema actual (`TIPOLOGIA_BENCHMARKS` fabricado, señalado en `PROJECT_AUDIT.md` y `TECH_REVIEW.md`), y contradice directamente el principio no negociable fijado en `NORTH_STAR_2031.md` de nunca mostrar datos fabricados como reales.
- **Qué produce como salida:** comparativas de posicionamiento, solo cuando hay masa de datos real suficiente para que tengan significado estadístico.
- **De qué otros dominios depende:** de los Dominios 3 y 9 principalmente (las métricas que tiene sentido comparar).
- **Prioridad:** Baja hoy, condicionalmente alta en el futuro. Este dominio **no debe activarse** hasta que exista una base de datos real — su prioridad no es "cuándo lo construimos" sino "cuándo hay datos reales que lo justifiquen". Construirlo antes repite exactamente el error ya cometido.

---

## Parte 3 — El grafo de dependencias, en una vista

```
Capa 0 (contexto)     [1] Encaje urbanístico     [2] Programa y tipología
                              │                          │
                              └───────────┬──────────────┘
                                          ▼
Capa 1 (hechos)               [3] Geometría y dimensionado
                                          │
                                          ▼
                              [4] Iluminación y ventilación
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
Capa 2 (seguridad)  [5] Accesibilidad     [6] Evacuación/incendio
                    │                     │
                    └──────────┬──────────┘
                               ▼
Capa 3 (confort)    [7] Acústica    [8] Térmica/energética    [9] Calidad espacial
                               │
Capa 4 (sistemas)   [10] Instalaciones    [11] Coherencia estructural
                               │
                               ▼
Capa 5 (meta)                 [12] Efectos en cadena y resolución de conflictos
                               │                     (consume salidas de TODOS los anteriores)
                               ▼
Capa 6 (riesgo/mercado)  [13] Riesgo de visado    [14] Benchmark de mercado
```

Una regla de diseño se desprende directamente de este grafo y es la más importante de todo el documento: **las flechas solo bajan de capa, nunca suben, excepto hacia el Dominio 12**. Ningún dominio normativo (capas 1-4) debe depender jamás del meta-dominio ni de los dominios de riesgo/mercado. Si алgún día un dominio normativo "necesita" saber algo del Dominio 12 o 13 para funcionar, es una señal de que ese conocimiento está mal clasificado y en realidad pertenece a una capa inferior.

---

## Parte 4 — La arquitectura que soporta 500+ reglas sin volverse inmanejable

Con 14 dominios y un objetivo de 500+ reglas, cada dominio individual puede terminar albergando docenas de reglas (el Dominio 3, por ejemplo, fácilmente decenas solo por variación autonómica de habitabilidad). Esto es exactamente el punto en el que un sistema mal diseñado se vuelve ingobernable. Los principios que lo evitan, en términos de conocimiento y no de implementación, son los siguientes:

**1. Cada regla pertenece a exactamente un dominio, nunca a dos.** Si una regla parece pertenecer a dos dominios a la vez, no es una regla mal ubicada — es una señal de que en realidad hay un conflicto entre dominios, y ese conflicto pertenece al Dominio 12, no a ninguno de los dos dominios originales duplicando la regla.

**2. Cada dominio expone un contrato de entrada/salida estable, independiente de cuántas reglas tenga dentro.** Añadir la regla número 80 a un dominio que ya tenía 79 no debe cambiar nada de lo que otros dominios reciben de él. Esto es lo que permite que un dominio crezca de 10 a 100 reglas sin que ningún otro dominio, ni el meta-dominio, se entere del cambio salvo por sus salidas.

**3. El meta-dominio (12) consume conclusiones, nunca reglas internas.** Es la regla que impide la explosión combinatoria N×N: con 14 dominios, permitir que cada uno conozca los detalles internos de los demás generaría, en el límite, cientos de acoplamientos cruzados. Limitando el conocimiento cruzado a un único dominio que solo lee salidas ya resueltas, la complejidad de mantenimiento crece linealmente con el número de dominios, no exponencialmente.

**4. Toda regla declara su fuente normativa exacta y su vigencia.** Artículo, decreto, comunidad autónoma de aplicación, fecha desde la que es vigente. Esto no es burocracia — es lo que permite que cuando una norma cambie (y las normas de habitabilidad autonómica cambian con frecuencia razonable), se pueda encontrar y actualizar exactamente la regla afectada sin auditar el dominio entero. Es también, según `NORTH_STAR_2031.md` y `DESTROY_ARCHMUSE.md`, la base de confianza institucional necesaria para que un colegio profesional o una aseguradora respalden el sistema — un cerebro que no puede explicar de dónde sale cada conclusión no es auditable, y lo que no es auditable no genera la confianza institucional que es, a largo plazo, el foso real del negocio.

**5. La severidad de cada regla es parte del conocimiento, no un ajuste posterior.** Si la jerarquía de prioridad descrita en la Parte 1.7 (bloqueante / riesgo variable / recomendable / preferencial) no está codificada como parte de la regla misma desde el momento en que se define, cualquier intento posterior de "calcular" la severidad centralizadamente reintroduce exactamente el tipo de función gigante e imposible de mantener que ya existe hoy (`classify_problems`, señalada en `TECH_REVIEW.md` como el peor ejemplo de función-dios del sistema actual: 327 líneas, complejidad ciclomática 49).

**6. El crecimiento de reglas dentro de un dominio no debe requerir entender los demás dominios.** Un experto en acústica debe poder añadir la regla 40 del Dominio 7 sin necesitar entender cómo funciona el Dominio 11. Esto es una consecuencia directa de los principios 1 y 2, pero merece decirse explícitamente porque es el criterio último de éxito de esta arquitectura: **¿puede una persona nueva, experta en un solo dominio normativo, contribuir conocimiento sin leer ni entender el resto del cerebro?** Si la respuesta es sí, la arquitectura escala a 10 años y a cientos de reglas. Si la respuesta es no, no importa cuán bien divididos estén los dominios sobre el papel — el sistema volverá a converger en un monolito.

**7. Las tres capas del veredicto global (Parte 1.8) se mantienen separadas hasta la salida final.** Ningún dominio, ni siquiera el meta-dominio, debe colapsar "viabilidad", "riesgo de visado" y "calidad" en un número único en ningún punto intermedio del razonamiento. La fusión en un solo número, si se produce, debe ser la última operación de todo el sistema, no una que ocurra dominio a dominio — de lo contrario se pierde información que un arquitecto sénior nunca perdería.

---

## Cierre

Este cerebro, tal como está diseñado, no es una versión más grande del `evaluator.py` actual — es un modelo distinto de cómo se organiza el conocimiento profesional de un arquitecto sénior: primero el marco de lo posible, después los hechos, después lo que compromete la seguridad, después el confort, después la calidad, y por encima de todo eso, un dominio que existe únicamente para sostener las tensiones entre los demás, tal como lo hace un profesional experimentado de forma instintiva.

La implicación de mayor calado del documento no es la lista de 14 dominios — es la Capa 5. Un competidor puede copiar reglas normativas sueltas en semanas (`DESTROY_ARCHMUSE.md` ya lo señala). Lo que no puede copiar fácilmente es un motor de razonamiento cruzado maduro, con años de conflictos reales acumulados y resueltos. Si ArchMuse construye bien un solo dominio de los catorce, ese es el que debería construir primero y proteger con más cuidado a largo plazo — aunque, como se detalla en la Parte 2, solo puede construirse bien **después** de que las capas 0-2 sean fiables, porque un motor de conflictos sobre datos de entrada incorrectos no razona mejor que un checklist plano; solo se equivoca con más confianza.
