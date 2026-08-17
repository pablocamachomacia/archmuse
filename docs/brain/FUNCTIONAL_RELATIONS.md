# FUNCTIONAL_RELATIONS.md

**Propósito:** modelar cómo razona un arquitecto sénior sobre las relaciones **entre** espacios — no qué mínimo exige la norma a cada Pieza por separado (eso ya vive en `SPACE_TAXONOMY.md`, campo "requisitos normativos habituales"), sino qué le dice el criterio profesional sobre cómo deberían **componerse entre sí**: qué acercar, qué separar, cómo se recorre una vivienda, dónde vive la intimidad, dónde el ruido, a quién le corresponde la mejor luz, qué depende de qué. **Este documento no cita normativa en ningún punto** — todo lo que sigue es Nivel 3-4 de `ARCHITECTURAL_KNOWLEDGE_MAP.md` (buena práctica y criterio arquitectónico), nunca Nivel 1-2. Sin código, como el resto de la serie.

**Referencias obligatorias, asumidas como ya decididas:**
- `SPACE_TAXONOMY.md` — los 29 tipos de espacio sobre los que razona este documento; cada tipo ya tiene un campo "relaciones funcionales" e "incompatibilidades" propios, breves y por tipo. Este documento no los repite — profundiza el *porqué* detrás de esas relaciones y las trata de forma cruzada entre tipos, no una por una.
- `ARCHITECTURAL_ONTOLOGY.md` §0.1 — el vocabulario cerrado de relaciones estructurales (contiene/pertenece a, delimita, da a/se abre a, sirve a/servido por, conecta con, se apoya en, se ubica en). Este documento no lo sustituye ni lo repite — añade un tipo de conocimiento distinto: no *qué conecta con qué* (eso ya lo dice la ontología), sino *cuánto conviene* que estén cerca, separados, o en qué orden se recorren.
- `ARCHITECTURAL_QUALITY.md` §1-2 — los siete ejes de excelencia (parti, respuesta al lugar, promenade architecturale, servido/servidor de Kahn, luz compositiva, proporción, economía de medios) y los tres niveles de aproximación (A: proxy geométrico, B: heurística comparativa, C: criterio irreducible). Este documento vive, casi en su totalidad, en el Nivel B — comparaciones razonadas entre espacios — con la sección 10 asomándose deliberadamente al Nivel C.
- `CHAIN_REASONING.md` §5 — los pares de tensión estructural entre **dominios**. Este documento es su análogo a nivel de **espacio**: no "Accesibilidad vs. Superficie útil" sino "Dormitorio junto a Escalera" — el mismo tipo de conocimiento, un nivel más concreto.
- `DECISION_ENGINE.md` §5, `CONFLICT_ENGINE.md` §1 (Tipo 5) — discrepancia legítima de criterio, el mecanismo que sostiene la sección 10 de este documento.
- Grounding real: `analyzer/evaluator.py`, `_ORIENTATION_RULES` — el sistema ya codifica, hoy, un criterio de orientación óptima/a evitar por tipo de pieza (Salón/Cocina: óptimo S/SO, evitar N; Dormitorio 1/2: óptimo E/S, evitar N; Dormitorio 3, Baño, Aseo: sin óptimo declarado, evitar N) como *recomendación no bloqueante*, nunca como incumplimiento — es, ya en producción, exactamente el tipo de conocimiento de criterio (no normativo) que este documento formaliza y amplía en la sección 7.

---

## 0. Marco y alcance

### 0.1 Qué tipo de conocimiento es este, y qué no es

Todo lo que sigue responde a la pregunta *"¿qué haría un arquitecto sénior, aunque nada se lo exigiera?"* — nunca a *"¿qué exige la norma?"*. Una consecuencia práctica de esto: ninguna afirmación de este documento puede convertirse, tal cual, en un `Problem` bloqueante (`REASONING_ENGINE_SPEC.md` entidad 11) — como mucho, en un Hallazgo de recomendación de calidad (`OBSERVATION_MODEL.md` §3), exactamente igual que ya hace `evaluate_orientation` en `evaluator.py`, que nunca marca una orientación desfavorable como incumplimiento.

### 0.2 Escalas cerradas — el vocabulario que sustituye a "cerca/lejos/bien/mal"

Igual que el resto de la serie cierra sus vocabularios de comparadores y relaciones, este documento define, una sola vez, cuatro escalas cerradas que se reutilizan en todas las secciones siguientes — nunca una valoración libre redactada distinta para cada par de espacios:

**Escala de proximidad** (secciones 1-2): `Adyacencia directa` (contacto físico o conexión sin pieza intermedia) → `Proximidad preferente` (cerca, admite un elemento de paso entre medias) → `Indiferente` (sin preferencia de criterio) → `Distancia preferente` (mejor si no son vecinas) → `Separación estricta` (nunca deberían ser adyacentes sin un filtro intermedio).

**Escala de privacidad** (sección 4): `Público` → `Semi-público` → `Privado` → `Íntimo`.

**Escala de merecimiento lumínico** (sección 6): `Prioritario` → `Preferente` → `Aceptable interior` → `Indiferente`.

**Escala de jerarquía espacial** (sección 8): `Principal` → `Secundaria` → `Servidora` → `Técnica`.

---

## 1. Proximidad funcional — qué espacios deberían estar próximos

| Espacio A | Espacio B | Proximidad | Razón |
|---|---|---|---|
| Cocina (2.1/2.2) | Comedor (1.2) | Adyacencia directa | El trayecto de servir la comida es el recorrido más repetido de la vida doméstica diaria; cualquier distancia entre ambos se paga en cada comida, no una vez. |
| Salón (1.1) | Terraza (5.1) | Adyacencia directa (si existe Terraza) | La continuidad visual y de uso interior-exterior es, según `ARCHITECTURAL_QUALITY.md` §1, parte de la relación con el lugar — una terraza accesible solo desde un Dormitorio no cumple la misma función social. |
| Dormitorio principal (1.4) | Baño en suite (3.1) | Proximidad preferente | Preferente, no estricta, porque un baño compartido bien ubicado es una solución igualmente legítima (ver sección 10.1) — pero cuando existe baño en suite, su valor depende enteramente de la adyacencia directa. |
| Vestíbulo (4.1) | Distribuidor (4.2) | Adyacencia directa | Son, funcionalmente, el primer y el segundo tramo del mismo recorrido de reparto interior. |
| Lavadero (2.4) | Cocina (2.1) | Proximidad preferente | Comparten instalación de fontanería; la distancia no invalida la vivienda pero encarece y complica cada uso cotidiano. |
| Trastero (4.4) | Acceso de servicio o Vestíbulo | Proximidad preferente | El trastero se usa, típicamente, al entrar o salir cargado — un recorrido largo hasta él penaliza su uso real más que su existencia formal. |
| Aseo (3.2) | Salón (1.1) | Proximidad preferente | El aseo de cortesía sirve a las visitas, que permanecen en la zona social — su proximidad al Salón, no a los Dormitorios, es lo que lo distingue funcionalmente de un Baño (`SPACE_TAXONOMY.md` 3.2). |
| Núcleo húmedo de una Planta | Núcleo húmedo de la Planta inmediatamente inferior | Adyacencia directa (vertical) | No es una relación de proximidad en planta sino de apilamiento entre Plantas — el mismo criterio de coherencia vertical ya nombrado en `ARCHITECTURAL_ONTOLOGY.md` C.4/F.1, aquí reafirmado desde el lado del criterio de composición, no solo de viabilidad de instalaciones. |

**Excepción general de la sección:** ninguna de estas proximidades es absoluta cuando el programa de la vivienda es reducido — en una vivienda muy compacta, casi todo está, por necesidad geométrica, en proximidad directa con casi todo lo demás, y la escala deja de discriminar. El criterio de proximidad tiene valor real a partir de un tamaño de vivienda donde existe margen de elección — por debajo de ese margen, las prioridades de la sección 2 (separación) pesan más, porque ahí sí suele haber elección real incluso en poca superficie.

---

## 2. Separación funcional — cuáles deberían separarse

| Espacio A | Espacio B | Separación | Razón |
|---|---|---|---|
| Dormitorio (1.4) | Cocina (2.1/2.2) | Separación estricta (sin filtro intermedio) | Olores, ruido de actividad diurna y horario de uso incompatible con el descanso — de los pares de mayor consenso profesional de toda esta lista. |
| Dormitorio (1.4) | Escalera común / Ascensor (6.2/6.3) | Separación estricta | Ruido de paso de vecinos y de maquinaria, en un horario que el propio residente no controla. |
| Zona de noche (Dormitorios) | Zona de día (Salón, Cocina) | Distancia preferente, nunca separación estricta | La relación correcta no es una pared sino un gradiente — un Distribuidor o Vestíbulo que medie entre ambas zonas, no un muro que las aísle por completo (la vivienda sigue siendo un único conjunto habitado, no dos mitades independientes). |
| Baño (3.1) | Salón (1.1), cuando el acceso al baño es visible desde el Salón | Separación preferente de visibilidad, no de proximidad física | La adyacencia física entre Baño y Salón es habitual y aceptable; lo que se evita es que la puerta del baño quede en el campo de visión directo de quien está sentado en el Salón — es un problema de ángulo de apertura y de privacidad (sección 4), no de distancia. |
| Espacio técnico / Sala de instalaciones (Categoría 7) | Cualquier Pieza habitable (C.2) | Separación estricta, salvo filtro (Vestidor, Trastero, Distribuidor) | Vibración y ruido continuo — el mismo criterio, aquí generalizado, que `SPACE_TAXONOMY.md` 7.2 ya señala para Sala de calderas en particular. |
| Garaje colectivo (8.2) | Dormitorio en Planta inmediatamente superior | Distancia preferente vertical | El ruido de motor y portón, aunque de corta duración, es más disruptivo sobre una pieza de descanso que sobre una de uso diurno — cuando la geometría del edificio obliga a elegir qué queda directamente sobre el garaje, un Dormitorio es la peor opción posible, un Distribuidor o Trastero la mejor. |

**Excepción explícita:** cuando el programa no deja alternativa geométrica real (una vivienda de una sola crujía, por ejemplo, donde Cocina y Dormitorio no pueden dejar de ser vecinos sin sacrificar otra relación de mayor peso), la separación estricta se relaja a preferente-mitigada: se busca el filtro intermedio más barato disponible (un armario, un vestidor, un tabique reforzado sin llegar a exigencia normativa) en vez de declarar la solución como necesariamente deficiente — el criterio existe para guiar la decisión de diseño, no para producir un veredicto binario allí donde la geometría ya limitó las opciones reales.

---

## 3. Recorridos habituales — cómo se camina una vivienda

Un arquitecto sénior no diseña piezas sueltas — diseña **secuencias de recorrido** que un residente repite miles de veces a lo largo de los años de uso de la vivienda. Tres recorridos característicos, no exhaustivos pero sí los de mayor peso en el criterio profesional:

**El recorrido social** — Acceso principal → Vestíbulo → (Distribuidor si existe zona social separada, o directamente) → Salón/Salón-comedor, con posible desvío a Aseo de cortesía. Es el recorrido que ve una visita, y por tanto el que más pesa en la primera impresión del proyecto (`ARCHITECTURAL_QUALITY.md` §1, promenade architecturale) — nunca debería cruzar, ni siquiera tangencialmente, la Zona de noche.

**El recorrido de servicio** — Acceso de servicio (si existe) o el mismo acceso principal → Cocina → Lavadero/Tendedero → Trastero. Distinto del recorrido social porque transporta objetos (compra, ropa, basura) en vez de personas en tránsito social — su criterio de calidad es la longitud mínima y la ausencia de obstáculos (puertas estrechas, cambios de nivel), no la calidad de la experiencia espacial que sí importa en el recorrido social.

**El recorrido nocturno** — Dormitorio → Baño, el trayecto más corto y más repetido de todos (varias veces por noche, en la oscuridad, medio dormido). Debería ser el recorrido de menor longitud y de menor número de decisiones de orientación de toda la vivienda — un criterio de calidad real, aunque casi nunca se verbaliza como tal en memoria de proyecto, y uno de los pocos de este documento donde el criterio arquitectónico coincide casi exactamente con la ergonomía pura, sin margen de interpretación de gusto.

**Excepción:** en viviendas de superficie muy reducida, los tres recorridos colapsan parcialmente en uno solo (el mismo Distribuidor sirve a los tres) — no es un defecto de diseño, es la consecuencia inevitable de la escala; el criterio de calidad en ese caso no es "tener tres recorridos diferenciados" sino que el recorrido único resultante no favorezca desproporcionadamente a uno de los tres usos a costa de los otros dos (por ejemplo, que el recorrido de servicio no obligue a atravesar el Salón).

---

## 4. Privacidad — el gradiente de intimidad

La privacidad no es una propiedad binaria de una Pieza (pública o privada) — es un gradiente de cuatro niveles, y el criterio central de esta sección es que **la mirada y el recorrido de un visitante nunca deberían saltar directamente de un nivel a otro sin atravesar los intermedios**:

| Nivel | Espacios típicos |
|---|---|
| **Público** | Portal, Zona ajardinada común, Rellano |
| **Semi-público** | Vestíbulo, Salón (mientras recibe visitas), Aseo de cortesía |
| **Privado** | Distribuidor interior, Dormitorio secundario, Despacho |
| **Íntimo** | Dormitorio principal, Baño, Vestidor |

**La regla de composición central:** desde la puerta de acceso de la vivienda, la secuencia de niveles atravesados debería ser siempre ascendente y continua (Público → Semi-público → Privado → Íntimo), nunca con un salto que exponga un nivel Íntimo directamente al primer nivel Público. Esto es, en esencia, la misma lógica de la sección 3 (recorrido social) descrita ahora desde el punto de vista de la privacidad en vez del uso.

**Excepción real y frecuente:** el Baño de cortesía (Aseo, 3.2) rompe deliberadamente el gradiente — es, funcionalmente, un espacio Íntimo por naturaleza de uso, pero se ubica a propósito en zona Semi-pública para servir a las visitas sin que estas tengan que penetrar en zona Privada. No es una anomalía a corregir — es la única pieza de esta ontología cuyo nivel de privacidad de *uso* y de *ubicación* se disocian a propósito, y un sistema de reglas que penalizara automáticamente esa disociación estaría equivocado.

---

## 5. Ruido — criterio compositivo, no acústico-normativo

Distinto, deliberadamente, del aislamiento acústico exigible entre unidades independientes (eso es Nivel 1-2, normativo, y no vive en este documento). Aquí el criterio es de composición: qué espacios **generan** ruido de uso cotidiano y cuáles lo **reciben mal**, dentro de la misma vivienda, sin que exista ninguna exigencia normativa de por medio (dos piezas de la misma unidad de uso rara vez tienen una exigencia de aislamiento acústico entre sí).

**Espacios generadores habituales:** Cocina (electrodomésticos, actividad), Salón (televisión, conversación, en horario extendido), Distribuidor si conecta con Zona común ruidosa, Espacio técnico.

**Espacios receptores sensibles:** Dormitorio (por definición, el más sensible de todos, en el horario en que menos tolerancia hay), Despacho (sensibilidad alta durante el horario de uso, aunque ese horario coincida con el de menor ruido generado por el resto de la vivienda).

**Criterio de composición:** ningún espacio receptor sensible debería ser adyacente directo a un espacio generador sin un espacio-filtro entre medias (un Distribuidor, un Vestidor, un armario empotrado) — el mismo principio que la sección 2 ya aplica a Dormitorio/Cocina, generalizado aquí como regla de composición explícita, no solo como par prohibido puntual.

**Excepción:** en una tipología de Salón-comedor-cocina abierto (`SPACE_TAXONOMY.md` 1.3), la propia decisión de diseño ya acepta que Cocina y Salón compartan ambiente acústico sin filtro — no es un error de composición, es una decisión de programa consciente y frecuente (ver también sección 10.2); el criterio de esta sección se aplica entre la zona social fusionada resultante y los Dormitorios, no dentro de la propia zona fusionada.

---

## 6. Iluminación — quién merece la mejor luz

Más allá del mínimo normativo de superficie de hueco (Nivel 1-2, no tratado aquí), existe una jerarquía de criterio sobre **a qué pieza se le reserva la mejor calidad de luz disponible** cuando el proyecto no puede dar la mejor orientación a todas a la vez:

| Nivel | Espacios | Razón |
|---|---|---|
| **Prioritario** | Salón/Estar, Salón-comedor | Es la pieza de mayor permanencia diurna y la que sostiene la jerarquía espacial principal (sección 8) — coincide, no por casualidad, con la pieza que `SPACE_TAXONOMY.md` 1.1 ya señala como la de mayor superficie esperada. |
| **Preferente** | Dormitorio principal, Cocina si tiene uso social (cocina-comedor) | Uso prolongado, aunque de menor permanencia diurna que el Salón. |
| **Aceptable interior** | Dormitorio secundario, Despacho | Puede aceptar una calidad de luz menor (orientación menos favorable, hueco más modesto) sin que ello constituya, por sí solo, un defecto de proyecto. |
| **Indiferente** | Baño, Distribuidor, Trastero, Espacio técnico | Su función no depende de luz natural de calidad — un Baño interior sin ventana no es, por criterio, un peor Baño; es, simplemente, un Baño distinto (con ventilación mecánica), sin que "interior" implique automáticamente "inferior" en este eje concreto. |

**Excepción de composición, no de jerarquía:** un Distribuidor con luz cenital o un hueco propio no es una mejora obligatoria — es una decisión de calidad opcional (`ARCHITECTURAL_QUALITY.md` §1, "luz como herramienta compositiva") que, cuando existe, se valora positivamente sin que su ausencia constituya un defecto, exactamente la misma distinción que ese documento ya establece entre Nivel A/B (cumplimiento de proxy) y Nivel C (mérito de diseño no exigible).

---

## 7. Orientación — preferencias por tipo de espacio

Grounded directamente en el criterio ya codificado, y en producción, en `evaluator.py` (`_ORIENTATION_RULES`) — este documento no inventa un criterio nuevo, formaliza y extiende el que ya existe:

| Espacio | Orientación óptima (criterio) | Orientación a evitar (criterio) | Razón |
|---|---|---|---|
| Salón / Salón-comedor | Sur, Suroeste | Norte | Uso vespertino-nocturno predominante; el sol de tarde es, en clima mediterráneo, el momento de mayor ocupación real de la pieza. |
| Dormitorio principal, Dormitorio secundario | Este, Sur | Norte | Luz de mañana coherente con el momento de despertar; evita el sobrecalentamiento de tarde que sí es deseable en el Salón pero no en una pieza de descanso. |
| Dormitorio de menor jerarquía (p. ej. "Dormitorio 3") | Sin óptimo declarado | Norte | El criterio existente (`evaluator.py`) ya reconoce que no toda pieza necesita una orientación óptima positiva para ser aceptable — basta con evitar la peor, un matiz de criterio real que una regla más simplista ("toda pieza habitable necesita orientación óptima") perdería. |
| Baño, Aseo | Sin óptimo declarado | Norte (criterio débil, no estricto) | Su sensibilidad a la orientación es baja por naturaleza de uso — el criterio existente lo trata con la exigencia más débil de toda la tabla, correctamente. |
| Cocina, cuando se evalúa de forma independiente de Salón (`SPACE_TAXONOMY.md` 1.3, error de fusión ya señalado) | Norte, Noreste (preferente, no codificado hoy) | Sur en climas cálidos | Una cocina orientada a sur acumula carga térmica de la propia actividad de cocinar sumada a la solar — criterio arquitectónico razonable, hoy no formalizado en el sistema porque, al fusionarse con Salón (`SPACE_TAXONOMY.md` §1.3), hereda la orientación óptima del Salón sin poder tener una propia. |

**Excepción de zona climática:** toda esta tabla asume clima mediterráneo/templado, el contexto implícito de `evaluator.py` hoy. En zona climática fría (norte peninsular, alta montaña), el criterio de "evitar Norte" para Dormitorio pierde parte de su fuerza y el criterio de "Sur óptimo para Salón" se refuerza — la orientación es, estructuralmente, un criterio dependiente del contexto climático (`ARCHITECTURAL_ONTOLOGY.md` H.1), no una preferencia universal fija; este documento describe el criterio dominante en el contexto real de uso actual de ArchMuse, no una verdad arquitectónica absoluta e independiente del clima.

---

## 8. Jerarquía espacial — servido y servidor

Reutiliza directamente la distinción de Louis Kahn ya citada en `ARCHITECTURAL_QUALITY.md` §1: piezas **servidas** (las que sostienen el propósito principal de la vivienda) y piezas **servidoras** (las que existen para que las servidas funcionen bien). Cuatro niveles, cerrados:

| Nivel | Espacios | Implicación de criterio |
|---|---|---|
| **Principal** | Salón/Estar, Dormitorio principal | Mayor superficie relativa esperada; mejor orientación y luz disponibles (secciones 6-7); posición privilegiada en el recorrido (sección 3). |
| **Secundaria** | Dormitorio secundario, Despacho, Comedor independiente | Superficie y calidad de luz aceptables, sin necesidad de ser las óptimas del proyecto. |
| **Servidora** | Cocina, Baño, Vestidor, Distribuidor, Vestíbulo | Existe en función de la pieza a la que sirve — su calidad se mide por cuán bien resuelve esa función de servicio, no por cuán protagonista es en sí misma. |
| **Técnica** | Espacio técnico, Trastero, Patinillo de instalaciones | El menor peso jerárquico — su exigencia de criterio es de funcionamiento correcto, nunca de protagonismo espacial. |

**La regla de composición central de esta sección:** un proyecto donde una pieza Servidora (por ejemplo, un Distribuidor sobredimensionado) supera en superficie o en calidad de luz a una pieza Principal es, según este criterio, una jerarquía invertida — un síntoma de calidad espacial baja, exactamente el tipo de observación que `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 9 ya nombra como "coherencia entre la jerarquía de usos declarada y la jerarquía espacial real construida".

**Excepción:** en tipologías de muy alta gama, un Vestidor o un Distribuidor de generosas dimensiones puede ser, deliberadamente, una pieza de alto valor de diseño (casi una pieza Principal en superficie) sin que eso invierta la jerarquía real — el criterio de "jerarquía invertida" se aplica al desequilibrio no intencionado, no a una decisión de programa explícita y coherente con el rango del proyecto (mismo matiz que `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 9 §7 ya señala: el listón de referencia cambia con el rango del proyecto, sin que eso signifique menor rigor).

---

## 9. Dependencias funcionales — qué espacio no existe sin otro

Un grafo de dependencia, no jerárquico como la sección 8 sino de existencia condicionada — reutiliza la relación "sirve a" de `ARCHITECTURAL_ONTOLOGY.md` §0.1 desde el ángulo de qué espacio **no tiene sentido propio** sin el espacio al que sirve:

| Espacio dependiente | Depende de | Naturaleza de la dependencia |
|---|---|---|
| Baño en suite (3.1, variante) | Dormitorio principal | Existencial — un "baño en suite" sin el dormitorio al que sirve deja de ser, por definición, un baño en suite; pasa a ser un Baño compartido más. |
| Vestidor (4.3) | Dormitorio | Existencial — sin el dormitorio al que sirve, un Vestidor es indistinguible de un Trastero pequeño. |
| Comedor independiente (1.2) | Cocina o Salón | Funcional fuerte — puede existir como pieza propia, pero pierde sentido si no está servido por una fuente de comida cercana. |
| Terraza (5.1) | Fachada exterior disponible en la pieza a la que se abre | Física — no puede existir sin un tramo de Fachada libre desde el que abrirse. |
| Distribuidor (4.2) | Existencia de más de una Pieza que conectar | Trivial pero real — un Distribuidor que solo conecta con una única pieza no cumple su función de reparto, es indicio de una circulación mal resuelta, no de un Distribuidor legítimo. |
| Rampa de acceso (8.3) | Garaje colectivo (8.2) | Existencial — no tiene sentido propio sin el garaje al que da acceso. |
| Patinillo de instalaciones (7.3) | Núcleo húmedo en más de una Planta | Funcional fuerte — un patinillo sin continuidad vertical real que servir no cumple su propósito, aunque exista como espacio geométrico. |

**Excepción/matiz:** la dependencia "existencial" (la más fuerte de la tabla) no implica que el espacio dependiente deba modelarse como parte de la misma Pieza que su servido — Baño en suite y Vestidor siguen siendo Piezas propias en el sentido de `ARCHITECTURAL_ONTOLOGY.md` C.1, con su propia geometría y su propio Fact de superficie; la dependencia es de **sentido funcional**, no de identidad geométrica. Confundir ambas cosas sería repetir, en sentido inverso, el mismo error ya señalado en `SPACE_TAXONOMY.md` (4.3): tratar una relación de servicio como si fuera una relación de contención física.

---

## 10. Casos de discrepancia legítima — donde varias soluciones son igualmente válidas

Cinco casos reales donde dos arquitectos sénior, ambos competentes, resolverían de forma distinta sin que ninguno esté equivocado — el mismo tratamiento que `CONFLICT_ENGINE.md` §1 (Tipo 5) reserva para discrepancias de Nivel 4 puro. Ninguno de estos casos debe resolverse automáticamente por un sistema de reglas; se exponen, no se deciden (`ARCHITECTURAL_QUALITY.md` §3, "espejo, no juez").

### 10.1 Baño en suite vs. baño compartido bien ubicado

Un Dormitorio principal con baño en suite maximiza privacidad e independencia; un baño único bien centrado entre varios dormitorios maximiza eficiencia de superficie y de instalaciones, y sigue siendo una solución de calidad si su proximidad a los dormitorios que sirve es buena (sección 1). Ninguna de las dos es superior en abstracto — la elección correcta depende del programa (número de dormitorios, presupuesto, composición familiar esperada), no de un criterio arquitectónico universal.

### 10.2 Cocina abierta vs. cocina cerrada

Ya apuntado en `SPACE_TAXONOMY.md` 1.3/2.2 desde el ángulo de clasificación; aquí se nombra desde el ángulo de criterio: la cocina abierta favorece la relación social y la luz compartida (sección 6) a costa de aceptar ruido y olor compartidos con la zona de día (sección 5); la cocina cerrada protege esa contención a costa de una relación social más fragmentada. Es, posiblemente, la decisión de programa con mayor componente de estilo de vida declarado de toda esta lista — el criterio correcto es preguntar la intención del cliente (`ARCHITECTURAL_QUALITY.md` §4, intención de diseño declarada), no imponer una de las dos por defecto.

### 10.3 Recorrido de servicio separado vs. recorrido único

En programas de alta gama con presupuesto y superficie suficientes, mantener el recorrido de servicio (sección 3) completamente independiente del recorrido social es un signo de calidad reconocido. En programas de superficie media o reducida, forzar esa separación completa suele producir una circulación general peor (más superficie dedicada a pasillos, menos a piezas habitables) que aceptar un recorrido único bien resuelto. La superioridad de "recorridos separados" es real solo por encima de un umbral de programa disponible, no una regla universal de calidad.

### 10.4 Dormitorio principal en planta baja vs. planta alta (vivienda unifamiliar de dos plantas)

Existen dos tradiciones de criterio igualmente asentadas: colocar el dormitorio principal en planta baja (accesibilidad a largo plazo, uso de la vivienda en la vejez, independencia respecto a los dormitorios secundarios en planta alta) frente a colocarlo en planta alta junto a los demás dormitorios (agrupación de la zona de noche completa, jerarquía de privacidad más clásica). Ninguna es un defecto de proyecto — dependen de una intención declarada del cliente sobre cómo espera envejecer o usar la vivienda a largo plazo, exactamente el tipo de dato que `ARCHITECTURAL_QUALITY.md` §4 ya reserva como Preference de ámbito "todo el proyecto".

### 10.5 Distribuidor central vs. pasillo lineal

Un distribuidor central (reparte a varias piezas desde un único punto compacto) suele ser más eficiente en superficie que un pasillo lineal largo, pero un pasillo lineal bien proporcionado puede ofrecer una secuencia de recorrido más rica (promenade architecturale, `ARCHITECTURAL_QUALITY.md` §1) que un reparto puramente funcional desde un punto. La elección depende de si el proyecto prioriza eficiencia pura o calidad de experiencia de recorrido — ambas son intenciones de diseño legítimas, no hay una "mejor forma de repartir" universal.

---

## Cierre

Nueve ejes de razonamiento y cinco casos de discrepancia legítima no agotan el criterio de un arquitecto sénior sobre las relaciones entre espacios — agotan lo que se puede formalizar con la misma disciplina de catálogo cerrado y escala cerrada que sostiene el resto de esta serie, sin fingir que existe una única respuesta correcta donde, con frecuencia, no la hay. El riesgo real de este documento, igual que el de `ARCHITECTURAL_QUALITY.md` que lo precede en espíritu, es el mismo de siempre en sentido inverso: convertir cualquiera de estas nueve tablas en un `Constraint` bloqueante solo porque tiene forma de tabla y de umbral. Ninguna fila de este documento debería, nunca, producir un incumplimiento — como mucho, una Recommendation con Confidence Media o Baja, siempre distinguible de una infracción normativa real. La prueba de que este documento se ha usado bien no es cuántas de sus reglas se aplican, sino que ninguna se aplique nunca como si fuera la sección 3-2 de `ARCHITECTURAL_KNOWLEDGE_MAP.md` disfrazada de aquí.
