# DB-SI_REVIEW.md — Revisión de las 24 reglas candidatas pendientes de DB-SI

**Fecha:** 2026-08-08 · **Alcance:** las 25 candidatas extraídas de `extraccion/estado/candidatas/codigotecnico__DB-SI__0a2e78cd6247.jsonl`
(versión de documento `0a2e78cd6247…`, fecha de la fuente 2025-03-04, 31 segmentos → 25 candidatas).
**Estado del lote según `extraccion/estado/ledger.jsonl`:** 1 confianza Alta (`C17`, ya `lista_para_promocion`), **24 pendientes de revisión**.

**Restricción cumplida:** revisión de solo lectura. **No se ha modificado ni una línea de código.** No se ha implementado ninguna
regla nueva. No se ha promocionado ninguna candidata.

---

## 0. Qué es este documento y qué no es

Esto **no** es una verificación de que un edificio cumpla el DB-SI. Es la respuesta a una pregunta mucho más estrecha:

> ¿Puede ArchMuse, con lo que hoy sabe leer de un DXF, **comprobar** esta condición concreta — y si no puede, lo está diciendo?

Esa distinción es la restricción crítica del encargo y gobierna todas las fichas. Una regla que no se puede comprobar debe terminar
en `UNKNOWN` o en un aviso de "no evaluable" (`evaluator.get_missing_data_warnings`, hoy la mejor pieza de honestidad del
repositorio), **nunca** en un cumplimiento fabricado ni en un incumplimiento derivado de un dato ausente. Esto último es lo que
`docs/brain/INFERENCE_ENGINE.md` §2.2 prohíbe explícitamente y lo que `docs/audits/NORMATIVE_AUDIT.md` §7.4 ya documentó como
patología presente en el motor.

### 0.1 Las cuatro etiquetas del encargo

Cada ficha clasifica el requisito en una de estas cuatro categorías antes de opinar sobre la implementación:

| Etiqueta | Significado |
|---|---|
| **NORMA CONFIRMADA** | El requisito está literalmente en el texto vigente del DB-SI ingerido, y se cita el apartado |
| **INFERENCIA TÉCNICA** | Razonable, pero es lectura nuestra del texto — no está escrito así |
| **NO VERIFICABLE DESDE DXF** | El requisito es correcto, pero el dato de entrada no existe en el modelo |
| **REGLA INCORRECTA / OBSOLETA** | Lo que el código afirma no se corresponde con lo que el artículo exige |

Las cuatro son independientes: un requisito puede ser NORMA CONFIRMADA **y** NO VERIFICABLE DESDE DXF a la vez, y de hecho ése es
el caso mayoritario de este lote.

### 0.2 Nota sobre el alcance del corpus ingerido

Los 31 segmentos ingeridos cubren las secciones SI 1 a SI 6. **No incluyen el Anejo SI A (Terminología).** Esto importa mucho más de
lo que parece: la definición de *origen de evacuación* — que es la que decide si los 25 m de SI 3 se miden desde dentro de una
habitación o desde la puerta de la vivienda — vive en ese Anejo. Varias candidatas lo referencian (`C13`, `C25`) pero su texto no
está cargado.

Por tanto, toda afirmación de esta revisión que dependa del Anejo SI A queda marcada como **pendiente de ingesta**, y no se usa como
base para una acción de código. Es deliberado: dar por sabida una definición que no está en el corpus sería exactamente el error que
`docs/design/NORMATIVE_ENGINE.md` §12 ("regla de dos personas") existe para prevenir.

### 0.3 Estado de partida honesto

De los 25 registros del lote, la única candidata con confianza Alta (`C17`, DB-SI 4.2) lo es porque es de tipo `remision`: no dice
nada propio, delega en el RD 513/2017. Es decir: **la única candidata promocionable de todo el DB-SI es la que no exige nada
evaluable.** Es un dato revelador sobre la naturaleza de este Documento Básico frente a un modelo puramente geométrico de planta.

---

## 1. Fichas de las 24 reglas pendientes

---

```text
ID: C01
Nombre: Compartimentación en sectores de incendio
Módulo: Sección DB-SI 1 — Propagación interior
```

**Referencia normativa:** DB-SI 1, apartado 1, Tabla 1.1 (condiciones de compartimentación) y Tabla 1.2 (resistencia al fuego de los
elementos separadores). **NORMA CONFIRMADA** — literal en el segmento ingerido.

**Requisito exacto:** para uso Residencial Vivienda, la Tabla 1.1 exige dos cosas distintas: *«La superficie construida de todo
sector de incendio no debe exceder de 2.500 m²»* y *«Los elementos que separan viviendas entre sí deben ser al menos EI 60»*. La
Tabla 1.2 fija además EI 60/90/120 para paredes y techos que separan el sector del resto del edificio, según altura de evacuación
(h ≤ 15 m → EI 60; 15 < h ≤ 28 m → EI 90; h > 28 m → EI 120; plantas bajo rasante → EI 120).

**Datos necesarios:** uso previsto del edificio; superficie **construida** agregada por sector; altura de evacuación; resistencia al
fuego real de los elementos separadores entre viviendas y de sector.

**Datos disponibles actualmente:** superficie por vivienda y agregada, sí (aunque ArchMuse mide superficie *útil* con criterio propio
—`evaluator.py` excluye terraza y tendedero— no superficie construida normativa). Uso previsto: no se declara; sólo hay `tipologia`
(plurifamiliar/unifamiliar/rehabilitacion), que no es lo mismo. Altura de evacuación: **no existe** en el flujo DXF; en
`/api/generar` hay `edificio.plantas` y `edificio.altura_libre_m`, con los que sería aproximable. Resistencia al fuego (EI):
**no existe en ningún flujo**.

**¿Verificable desde DXF?:** **Parcial.** El límite de 2.500 m² por sector es medible en superficie con las salvedades anteriores.
El EI 60 entre viviendas **no lo es en absoluto** y no lo será nunca desde un DXF de planta sin datos constructivos.

**Implementación actual:** `evaluate_fire_compartmentation` (`analyzer/evaluator.py:3000`, R26 en `NORMATIVE_AUDIT.md`). Compara las
huellas de cada par de viviendas y, si se solapan más de `FIRE_COMPARTMENTATION_OVERLAP_TOLERANCE_M2` (0,01 m²), emite una incidencia
con código `CTE-DB-SI-3` y el mensaje *«sectorización de incendio no garantizada entre ambas viviendas»*.

**Problema detectado:** tres, de gravedad decreciente.

1. **REGLA INCORRECTA — la cita señala al Documento equivocado.** La sectorización se regula en **SI 1** (propagación interior), no
   en SI 3 (evacuación de ocupantes). Es el hallazgo M3 de `NORMATIVE_AUDIT.md` §6.2, aquí confirmado contra el texto: el mismo
   código `CTE-DB-SI-3` lo emiten R17 (evacuación, donde sí es correcto) y R26 (sectorización, donde no lo es). Con un solo código
   para dos exigencias distintas es imposible trazar cuál se incumple.
2. **La regla no comprueba nada de lo que el artículo exige.** Ni los 2.500 m², ni el EI 60, ni la Tabla 1.2. Comprueba que dos
   polígonos no se solapen, que es una condición de integridad geométrica del dibujo — un solape es casi siempre un error de parsing
   o de agrupación (véase el bug de contornos agrupadores en `parser.py`), no un incumplimiento de DB-SI.
3. **INFERENCIA TÉCNICA presentada como norma.** El docstring es honesto y declara que es una condición *necesaria, no suficiente*.
   Ese matiz no sobrevive al viaje hasta la pantalla — mismo patrón que el H1 de la auditoría. El mensaje que lee el arquitecto
   afirma que la sectorización "no está garantizada", que es una conclusión sobre resistencia al fuego a partir de un dato que el
   sistema no tiene.

**Nivel de confianza: MEDIA** — para el sub-requisito de 2.500 m², que sí es real y aproximadamente medible. La implementación
actual, por sí sola, sería BAJA.

**Acción recomendada:** (a) **corregir la cita** de `CTE-DB-SI-3` a DB-SI 1 §1 en R26, y desacoplarla de la de R17; (b)
**reclasificar el solape de huellas** como comprobación de integridad geométrica, sin código DB-SI y sin lenguaje de sectorización —
es lo que realmente detecta; (c) mantener el EI 60 donde ya está, en `get_missing_data_warnings`, que hoy lo redacta correctamente;
(d) el límite de 2.500 m² es **candidata a regla nueva**, pero requiere antes declarar uso previsto y definir superficie construida
(ver `C08` y `NORMATIVE_ENGINE.md` §6 sobre `definicion` como tipo de primera clase).

---

```text
ID: C02
Nombre: Locales y zonas de riesgo especial
Módulo: Sección DB-SI 1 — Propagación interior
```

**Referencia normativa:** DB-SI 1, apartado 2, Tabla 2.1 (clasificación por grado de riesgo) y Tabla 2.2 (condiciones exigibles).
**NORMA CONFIRMADA.**

**Requisito exacto:** los locales de riesgo especial se clasifican en riesgo bajo/medio/alto según uso y una métrica dimensional o
energética, y deben cumplir las condiciones de la Tabla 2.2. Lo directamente aplicable a Residencial Vivienda: **Trasteros**
50 < S ≤ 100 m² (bajo), 100 < S ≤ 500 m² (medio), S > 500 m² (alto); aparcamiento de vehículos con S ≤ 100 m² o integrado en vivienda
unifamiliar, riesgo bajo *en todo caso*; y, en cualquier edificio, salas de calderas, local de contadores, sala de maquinaria de
ascensores, etc. La Tabla 2.2 exige entonces R 90/120/180, EI 90/120/180, vestíbulo de independencia, puertas EI₂ y recorrido máximo
hasta salida del local ≤ 25 m.

**Datos necesarios:** identificación tipada del local (no sólo su rótulo libre), superficie construida agregada por tipo de local, y
—para la Tabla 2.2— composición constructiva y puertas.

**Datos disponibles actualmente:** la superficie, sí. La identificación del local, **sólo si el DXF rotula la estancia** y el parser
la reconoce. `analyzer/parser.py` extrae `Room.label` como texto libre; no existe ninguna taxonomía de locales no habitables.
`ejemplo.dxf` no contiene trasteros ni cuartos de instalaciones rotulados. Nada de la Tabla 2.2 está disponible.

**¿Verificable desde DXF?:** **Parcial**, y condicionado a la rotulación. Sólo la *clasificación* del grado de riesgo (Tabla 2.1) y
sólo para trasteros y aparcamiento. La Tabla 2.2 es enteramente no verificable.

**Implementación actual:** **ninguna.** No existe ninguna regla en `evaluator.py` sobre locales de riesgo especial.

**Problema detectado:** el riesgo aquí no es una regla mal escrita, es la tentación de escribirla mal. Clasificar un trastero como
"riesgo bajo" a partir de su superficie es correcto y útil; **afirmar a continuación que cumple** las condiciones de la Tabla 2.2
sería fabricar cumplimiento sobre datos constructivos inexistentes. Y depender del rótulo tiene el precedente exacto de R18c
(`NORMATIVE_AUDIT.md` §7.4): una vivienda sin pieza rotulada "Pasillo" se declaraba sin itinerario accesible — un artefacto de
convención de dibujo convertido en incumplimiento. Ausencia de rótulo "Trastero" debe producir `UNKNOWN`, jamás "no hay locales de
riesgo especial".

**Nivel de confianza: MEDIA** — para la clasificación del grado de riesgo de trasteros. BAJA para todo lo demás.

**Acción recomendada:** **requiere nuevos datos del parser** (taxonomía de locales no habitables) antes de poder implementarse. Si se
implementa, que sea estrictamente clasificatoria: emitir el grado de riesgo y las condiciones que *quedarían exigidas*, como
información al arquitecto, sin ningún juicio de cumplimiento. No implementar ahora.

---

```text
ID: C03
Nombre: Espacios ocultos. Paso de instalaciones a través de elementos de compartimentación
Módulo: Sección DB-SI 1 — Propagación interior
```

**Referencia normativa:** DB-SI 1, apartado 3. **NORMA CONFIRMADA.**

**Requisito exacto:** la compartimentación debe tener continuidad en patinillos, cámaras, falsos techos y suelos elevados; y debe
mantenerse la resistencia al fuego en los puntos atravesados por instalaciones, *«excluidas las penetraciones cuya sección de paso no
exceda de 50 cm²»*, mediante obturación automática (compuerta EI t (i↔o), intumescente) o elementos pasantes de resistencia
equivalente.

**Datos necesarios:** existencia y geometría de espacios ocultos; trazado de instalaciones; sección de cada penetración; resistencia
al fuego del elemento atravesado.

**Datos disponibles actualmente:** **ninguno.** El modelo contiene polígonos de estancia en planta. No hay sección vertical, ni
falsos techos, ni instalaciones.

**¿Verificable desde DXF?:** **No.**

**Implementación actual:** ninguna.

**Problema detectado:** ninguno en el código — la ausencia de regla es aquí la decisión correcta. El único defecto es de
comunicación: `get_missing_data_warnings` no menciona la continuidad de compartimentación en espacios ocultos entre sus 10 avisos.

**Nivel de confianza: DESCARTAR** — como regla evaluable.

**Acción recomendada:** no implementar. Conservar la candidata en el corpus con tipo `exigencia_cualitativa` /
`aplica_no_evaluable` (`NORMATIVE_ENGINE.md` §13), y considerar añadir un aviso de no evaluable. Además, los dos `parametros` que la
extracción declaró (`50 cm²` y `"la mitad"`) son correctos en su cita pero **relativos**: `"la mitad"` no es un umbral absoluto y no
debería viajar como parámetro evaluable — la propia candidata lo señala.

---

```text
ID: C04
Nombre: Reacción al fuego de los elementos constructivos, decorativos y de mobiliario
Módulo: Sección DB-SI 1 — Propagación interior
```

**Referencia normativa:** DB-SI 1, apartado 4, Tabla 4.1. **NORMA CONFIRMADA.**

**Requisito exacto:** clases de reacción al fuego de revestimientos por zona (zonas ocupables C-s2,d0 / E_FL; pasillos y escaleras
protegidos B-s1,d0 / C_FL-s1; aparcamientos y recintos de riesgo especial B-s1,d0 / B_FL-s1; espacios ocultos B-s3,d0 / B_FL-s2),
exigibles sólo cuando el revestimiento supere el 5 % de la superficie total del conjunto. La nota (4) **excluye expresamente el
interior de viviendas** de las condiciones de zonas ocupables.

**Datos necesarios:** materiales y revestimientos de cada paramento, con su clasificación UNE-EN 13501-1.

**Datos disponibles actualmente:** **ninguno.** El DXF no contiene materiales.

**¿Verificable desde DXF?:** **No.** Es la categoría de dato que `ARCHITECTURAL_KNOWLEDGE_MAP.md` ya identificó como laguna
transversal nº 1 (sin fuente de datos constructivos/materiales, los Dominios 7, 8 y 11 quedan simultáneamente limitados). No es un
problema de reglas, es un problema de fuente de datos.

**Implementación actual:** ninguna.

**Problema detectado:** ninguno. Merece registrarse, eso sí, que la exclusión del interior de viviendas (nota 4) hace que buena parte
de este artículo **no aplique** a la tipología principal de ArchMuse — un `no_aplica` razonado, distinto de un `sin_cobertura`.

**Nivel de confianza: DESCARTAR.**

**Acción recomendada:** no implementar. Registrar la exención de la nota (4) en el corpus para que el motor pueda decir *por qué* no
aplica, en lugar de callar.

---

```text
ID: C05
Nombre: Medianerías y fachadas (propagación exterior)
Módulo: Sección DB-SI 2 — Propagación exterior
```

**Referencia normativa:** DB-SI 2, apartado 1. **NORMA CONFIRMADA.**

**Requisito exacto:** los elementos verticales separadores de otro edificio deben ser al menos EI 120. Para limitar la propagación
entre sectores o edificios, los puntos de fachada que no sean al menos EI 60 deben estar separados una distancia *d* que depende del
ángulo α formado por los planos exteriores de dichas fachadas (tabla con interpolación lineal). Franja EI 60 de 1 m en encuentros de
fachada entre sectores, reducible por salientes. Los sistemas constructivos de fachada que ocupen más del 10 % tienen condiciones
propias de reacción al fuego.

**Datos necesarios:** geometría 3D de fachadas, posición y dimensión de huecos, ángulos entre planos de fachada, y resistencia al
fuego de los paños.

**Datos disponibles actualmente:** el ángulo α entre dos fachadas sería geométricamente calculable en planta. **Todo lo demás falta**:
no hay huecos (carpintería) en el DXF, no hay resistencia al fuego, y no hay identificación de sectores.

**¿Verificable desde DXF?:** **No.** El ángulo por sí solo no permite comprobar nada: la regla mide distancia *entre huecos*, y los
huecos no existen en el modelo.

**Implementación actual:** ninguna.

**Problema detectado:** ninguno hoy, pero conviene dejar constancia de un riesgo concreto: éste es uno de los dos sitios de todo el
DB-SI donde sería tentador reutilizar el proxy de huecos `ancho_fachada × WINDOW_TO_FACADE_RATIO` (`evaluator.py:1253`). Ese proxy es
el hallazgo H3 de `NORMATIVE_AUDIT.md` §6.3 — dimensionalmente incoherente y sin dato real detrás — y **no da ni posición ni
dimensión de hueco**, que es exactamente lo que esta regla necesita. Reutilizarlo aquí sería propagar el defecto a materia de
incendios. (El otro sitio es `C19`.)

**Nivel de confianza: DESCARTAR.**

**Acción recomendada:** no implementar. Prohibición explícita de usar el proxy de huecos para esta materia.

---

```text
ID: C06
Nombre: Cubiertas (propagación exterior)
Módulo: Sección DB-SI 2 — Propagación exterior
```

**Referencia normativa:** DB-SI 2, apartado 2. **NORMA CONFIRMADA.**

**Requisito exacto:** franja REI 60 en el encuentro entre cubierta y elemento compartimentador o medianería (con alternativa de
prolongar el elemento 0,60 m por encima del acabado de cubierta), y tabla de doble entrada (d, h) que relaciona la distancia
horizontal de cubierta sin EI 60 con la altura de fachada sin EI 60.

**Datos necesarios:** geometría de cubierta y su encuentro con fachadas; resistencia al fuego de los paños.

**Datos disponibles actualmente:** **ninguno.** ArchMuse analiza plantas; no hay modelo de cubierta en ningún flujo.

**¿Verificable desde DXF?:** **No.**

**Implementación actual:** ninguna.

**Problema detectado:** ninguno.

**Nivel de confianza: DESCARTAR.**

**Acción recomendada:** no implementar. La propia candidata señala que la tabla (d, h) no encaja en ninguno de los 5 patrones
cerrados de `CONSTRAINT_MODEL.md` §3.1 — es un buen ejemplo de la situación que §14 anticipa, y la respuesta correcta **no** es
añadir un sexto patrón, sino clasificarla como no evaluable.

---

```text
ID: C07
Nombre: Compatibilidad de los elementos de evacuación
Módulo: Sección DB-SI 3 — Evacuación de ocupantes
```

**Referencia normativa:** DB-SI 3, apartado 1. **NORMA CONFIRMADA.**

**Requisito exacto:** los establecimientos de uso Comercial o Pública concurrencia de cualquier superficie, y los de uso Docente,
Hospitalario, Residencial Público o Administrativo con superficie construida > 1.500 m², integrados en un edificio de uso principal
distinto, deben cumplir condiciones a) y b) sobre salidas de uso habitual y de emergencia. Excepción para establecimientos de Pública
concurrencia ≤ 500 m² integrados en centros comerciales.

**Datos necesarios:** uso previsto de cada establecimiento, uso principal del edificio, superficie construida por establecimiento, y
trazado de recorridos hasta elementos comunes.

**Datos disponibles actualmente:** ninguno de los tres primeros se declara. ArchMuse conoce `tipologia`, no una lista de usos por
zona.

**¿Verificable desde DXF?:** **No.**

**Implementación actual:** ninguna.

**Problema detectado:** el matiz que importa aquí es de honestidad, no de cálculo: en un edificio residencial puro este artículo
**no aplica**. Pero ArchMuse no puede *saber* que el edificio es residencial puro — el DXF no declara usos, y la ausencia de locales
rotulados no demuestra su inexistencia. Concluir "no aplica" por silencio sería la variante más peligrosa del Bug #1
(`INFERENCE_ENGINE.md`: la inferencia negativa que falla como un tranquilizador "no hay problema").

**Nivel de confianza: DESCARTAR** — para el alcance actual.

**Acción recomendada:** **pasar a UNKNOWN condicionado.** No implementar como regla; si algún día se declara el uso del edificio,
resolver a `no_aplica` con motivo explícito. Nunca resolverlo por ausencia de datos.

---

```text
ID: C08
Nombre: Cálculo de la ocupación
Módulo: Sección DB-SI 3 — Evacuación de ocupantes
```

**Referencia normativa:** DB-SI 3, apartado 2, **Tabla 2.1 (Densidades de ocupación)**. **NORMA CONFIRMADA** — verificado literalmente
en el texto ingerido.

**Requisito exacto:** *«Para calcular la ocupación deben tomarse los valores de densidad de ocupación que se indican en la tabla 2.1
en función de la superficie útil de cada zona»*. Para **uso Residencial Vivienda, zona "Plantas de vivienda": 20 m²/persona**
(literal, verificado en el segmento). Excepciones del propio texto: cuando sea previsible una ocupación mayor, se usa la mayor;
cuando una disposición legal exija una menor, la menor; y las zonas no incluidas en la tabla toman los valores más asimilables.
La nota (1) obliga a considerar usos alternativos circunstanciales.

**Datos necesarios:** superficie **útil** por zona, y uso previsto de esa zona.

**Datos disponibles actualmente:** **la superficie útil ya se calcula** en `analyzer/evaluator.py` (es la base de R03,
`MIN_USEFUL_RATIO`, y de R07). El uso previsto no se declara como tal, pero la tipología `plurifamiliar`/`unifamiliar` identifica
inequívocamente el caso Residencial Vivienda, que es el único que ArchMuse analiza hoy.

**¿Verificable desde DXF?:** **Sí.** Es la única de las 24 que lo es sin condicionantes de dato ausente.

**Implementación actual:** **ninguna.** La ocupación no se calcula en ningún punto del motor — ni en `evaluator.py`, ni en
`circulation.py`, ni en `api_serializer.py`.

**Problema detectado:** ésta es la conclusión más importante de toda la revisión, y es una **ausencia**, no un error.

La ocupación es el dato del que dependen `C09` (número de salidas y longitud de recorridos), `C10` (dimensionado: A ≥ P/200),
`C15` (evacuación de personas con discapacidad) y buena parte de `C16`. **Sin ocupación calculada, ninguna regla de evacuación del
DB-SI puede evaluarse de verdad** — y eso explica estructuralmente por qué R17 lleva desde su origen comparando un número contra un
umbral que no le corresponde. No falta una regla: falta el Hecho del que todas las reglas de esta sección derivan. Es, en el
vocabulario de `docs/brain/FACT_MODEL.md` §4, un **Fact derivado** por una función de composición pura (superficie útil ÷ densidad),
no una regla — la aritmética ocurre aguas arriba y ningún Constraint la contiene.

Dos cautelas que condicionan la calificación ALTA y deben resolverse antes de implementar:

1. **La definición de "superficie útil" de ArchMuse es propia, no normativa.** `evaluator.py` excluye terraza y tendedero con
   criterio propio; `NORMATIVE_ENGINE.md` §6 ya señaló esto al defender `definicion` como tipo de primera clase. La ocupación
   heredaría esa definición, y por tanto su margen de error. Hay que declarar contra qué definición se mide.
2. **El ámbito de la tabla es la planta, no la vivienda.** El texto dice "Plantas de vivienda". Calcular una "ocupación de la
   vivienda VT3/3" es una extrapolación cómoda pero no es lo que la tabla indexa. El ámbito correcto es la planta completa —
   coherente con el eje de ámbito de `FACT_MODEL.md` §2.3.

**Nivel de confianza: ALTA** — condicionada a resolver esas dos cautelas, que son decisiones de implementación, no dudas normativas.
El umbral (20 m²/persona) es literal, el dato de entrada existe y la operación es aritmética pura.

**Acción recomendada:** **regla nueva — máxima prioridad de este lote.** Pero no como "regla" con veredicto: como **Fact derivado**
(ocupación calculada), expuesto al arquitecto como dato, sin `passed`/`failed`. Por sí sola la ocupación no se cumple ni se
incumple; es el insumo de las que sí. Al ser capacidad nueva, requiere PRD previo (`CLAUDE.md`).

---

```text
ID: C09
Nombre: Número de salidas y longitud de los recorridos de evacuación
Módulo: Sección DB-SI 3 — Evacuación de ocupantes
```

**Referencia normativa:** DB-SI 3, apartado 3, **Tabla 3.1**. **NORMA CONFIRMADA** — verificado literalmente.

**Requisito exacto**, transcrito del segmento ingerido:

- **Plantas o recintos con una única salida:** la ocupación no excede de 100 personas (*«500 personas en el conjunto del edificio, en
  el caso de salida de un edificio de viviendas»*); **la longitud de los recorridos de evacuación hasta una salida de planta no
  excede de 25 m**; y la altura de evacuación descendente no excede de 28 m.
- **Plantas o recintos con más de una salida:** la longitud **no excede de 50 m**, con excepción de **35 m** *«en zonas en las que se
  prevea la presencia de ocupantes que duermen»* — que es precisamente el caso residencial.
- Nota (1): las longitudes **se pueden aumentar un 25 %** en sectores protegidos con instalación automática de extinción.

**Datos necesarios:** ocupación (→ `C08`); número de salidas de planta; geometría de las zonas comunes (portal, núcleo de escalera)
hasta la salida de planta; altura de evacuación; existencia de rociadores; y la definición de *origen de evacuación* (Anejo SI A,
**no ingerido**).

**Datos disponibles actualmente:** **ninguno de los seis.** El DXF de ArchMuse contiene viviendas; no contiene núcleo de
comunicación, ni salidas de planta, ni puertas.

**¿Verificable desde DXF?:** **Parcial, y engañosamente.** Se puede medir *un* recorrido —el interior de la vivienda— con precisión.
Pero no es el recorrido que la norma limita.

**Implementación actual:** `evaluate_evacuation_distance` (`analyzer/evaluator.py:1583`, R17), con
`MAX_EVACUATION_DISTANCE_M = 25.0` (`:1555`). Recorre el grafo de piezas contiguas hasta la pieza de circulación y compara contra 25 m.
Adicionalmente, `circulation.py` (`C5` del inventario) **reutiliza la misma constante** con un método distinto (Dijkstra sobre el
grafo) — la duplicación D4 de `NORMATIVE_AUDIT.md` §4.

Hay que reconocer lo que ya se hizo bien: la corrección del 2026-08-05 sustituyó una medición sin sentido (distancia del centroide al
borde de la propia vivienda) por un recorrido real, y —más importante— introdujo `motivo_no_evaluable` cuando no hay pieza de
circulación desde la que situar la salida. Eso es exactamente el patrón correcto.

**Problema detectado:** **REGLA INCORRECTA en su ámbito**, y el propio código ya lo sabe. El docstring (`:1607-1614`) dice, literal:

> *«Los 25 m del DB-SI son la longitud del recorrido hasta la salida del EDIFICIO, no hasta la puerta de un piso. […] el umbral no
> llega a apretar casi nunca a esta escala.»*

Esta revisión confirma ese diagnóstico contra el texto y añade dos defectos que el docstring no recoge:

1. **Los 25 m sólo rigen el caso de una única salida.** Con más de una salida el límite es 50 m, o 35 m en zonas donde se duerme.
   ArchMuse aplica un escalar único sin conocer el número de salidas — que no puede conocer. La nota (1) añade un +25 % por
   rociadores que tampoco se contempla.
2. **La condición de ocupación de la Tabla 3.1 no se comprueba en absoluto** (≤ 100 personas / 500 en edificio de viviendas), porque
   la ocupación no se calcula (`C08`).

El resultado neto: una regla que emite `passed=True` citando el CTE DB-SI sobre una comprobación que no ha realizado. En materia de
incendios es el peor modo de fallo posible — el mismo argumento que el propio docstring usa para justificar la corrección anterior,
sólo que aplicado un nivel más arriba.

**Nivel de confianza: BAJA.** La medición del recorrido interior es un dato útil de diseño; no es una comprobación de DB-SI.

**Acción recomendada:** **corregir + degradar a UNKNOWN.** Concretamente: (a) retirar el veredicto de cumplimiento y el código
`CTE-DB-SI-3` del recorrido interior, presentándolo como métrica informativa de circulación (donde `circulation.py` ya lo trata
mejor); (b) declarar el recorrido normativo como no evaluable mientras no exista geometría de zonas comunes — añadiéndolo a
`get_missing_data_warnings`; (c) resolver de paso la duplicación D4, dejando una sola medición; (d) **ingerir el Anejo SI A** antes de
cualquier reimplementación, para fijar el origen de evacuación sobre texto y no sobre memoria.

---

```text
ID: C10
Nombre: Dimensionado de los medios de evacuación
Módulo: Sección DB-SI 3 — Evacuación de ocupantes
```

**Referencia normativa:** DB-SI 3, apartado 4, Tabla 4.1. **NORMA CONFIRMADA.**

**Requisito exacto:** dimensionado en función del número de personas P: puertas y pasos A ≥ P/200 ≥ 0,80 m; pasillos y rampas
A ≥ P/200 ≥ 1,00 m; escaleras no protegidas A ≥ P/160. Hipótesis de inutilización de una salida cuando deba existir más de una, con
las excepciones del punto 4.1.2. Anchuras específicas mayores en uso Hospitalario (puertas ≥ 1,05 m, pasillos ≥ 2,20 m).

**Datos necesarios:** ocupación P (→ `C08`); anchura libre de puertas; anchura libre de pasillos de evacuación; número de salidas.

**Datos disponibles actualmente:** la anchura de pasillo **sí** es medible y de hecho ya se mide (`evaluate_corridor_width`, R06). La
anchura de puertas no: no hay carpintería en el modelo — `get_missing_data_warnings` ya lo declara. La ocupación, no (`C08`).

**¿Verificable desde DXF?:** **Parcial**, y sólo para pasillos.

**Implementación actual:** ninguna que cite DB-SI. Existe R06 `evaluate_corridor_width` (`evaluator.py:750`), que comprueba
0,90 / 0,80 m según tipología y emite código `CTE-DB-SUA-1`.

**Problema detectado:** un hallazgo que corrige un riesgo latente, más que un error actual.

Sería natural "reforzar" R06 citando DB-SI 3.4 y su mínimo de 1,00 m para pasillos. **Sería incorrecto.** El pasillo *interior de una
vivienda* no es un recorrido de evacuación a efectos del DB-SI: en Residencial Vivienda el origen de evacuación se sitúa en la puerta
de la vivienda (Anejo SI A — **pendiente de ingesta**, ver §0.2), de modo que DB-SI 3.4 dimensiona los pasillos *comunes*, no el
distribuidor de un piso. El ancho del pasillo interior es materia de habitabilidad autonómica, no del CTE — lo que coincide con la
tabla de competencias de `NORMATIVE_ENGINE.md` §10 y con `normativa/esquema/materias.yaml`, donde `habitabilidad_dimensional` tiene
`documentos_basicos: []`.

Dicho de otro modo: el valor de esta ficha no es una regla nueva, es **impedir una sexta cita cruzada errónea** de la familia M1-M5.

**Nivel de confianza: BAJA** — para cualquier aplicación dentro de la vivienda. Sería MEDIA para pasillos comunes, si algún día se
modelan.

**Acción recomendada:** no implementar. **Documentar explícitamente** que DB-SI 3.4 no respalda el ancho de pasillo interior, para
que la corrección de la cita de R06 (hoy `CTE-DB-SUA-1`) no derive hacia DB-SI al revisarse.

---

```text
ID: C11
Nombre: Protección de las escaleras
Módulo: Sección DB-SI 3 — Evacuación de ocupantes
```

**Referencia normativa:** DB-SI 3, apartado 5, Tabla 5.1. **NORMA CONFIRMADA.**

**Requisito exacto:** para Residencial Vivienda y evacuación descendente: escalera **no protegida** admisible con h ≤ 14 m;
**protegida** con h ≤ 28 m; **especialmente protegida** admisible en todo caso. Para evacuación ascendente: no protegida con
h ≤ 2,80 m; protegida con 2,80 < h ≤ 6,00 m si P ≤ 100 personas.

**Datos necesarios:** altura de evacuación h; tipo de protección de la escalera; ocupación (ascendente); geometría de la escalera.

**Datos disponibles actualmente:** **ninguno en el flujo DXF.** `get_missing_data_warnings` ya declara *«Escalera: no evaluable — el
modelo actual no contiene elementos de escalera»*. En `/api/generar` existen `edificio.plantas` y `edificio.altura_libre_m`, con los
que h sería *aproximable*; el tipo de protección es dato constructivo y no existe en ningún flujo.

**¿Verificable desde DXF?:** **No.**

**Implementación actual:** ninguna (sólo el aviso de no evaluable, correcto).

**Problema detectado:** ninguno. Merece señalarse que el umbral de 14 m ≈ 4-5 plantas es un límite que muchos proyectos
plurifamiliares reales rozan, por lo que es un buen candidato a **aviso informativo condicional** en `/api/generar` — *«con
N plantas la altura de evacuación estimada supera 14 m; verificar protección de escalera según DB-SI 3, Tabla 5.1»*. Aviso, nunca
comprobación: la altura estimada es una hipótesis y el tipo de escalera sigue sin conocerse.

**Nivel de confianza: BAJA.**

**Acción recomendada:** **pasar a UNKNOWN** explícito. Mantener el aviso actual. Valorar el aviso condicional en `/api/generar`, con
el dato marcado como hipótesis (`DECISION_ENGINE.md`: nunca hipótesis presentada como hecho).

---

```text
ID: C12
Nombre: Puertas situadas en recorridos de evacuación
Módulo: Sección DB-SI 3 — Evacuación de ocupantes
```

**Referencia normativa:** DB-SI 3, apartado 6. **NORMA CONFIRMADA.**

**Requisito exacto:** las puertas previstas como salida de planta o de edificio y las previstas para la evacuación de más de 50
personas deben ser abatibles con eje vertical y su sistema de cierre no debe actuar mientras haya actividad; abatimiento en el
sentido de evacuación cuando la evacuación supere 100 personas (y 200 en determinados supuestos). Condiciones adicionales para
puertas giratorias y peatonales automáticas.

**Datos necesarios:** carpintería (existencia, hoja, sentido de apertura, herrajes) y ocupación.

**Datos disponibles actualmente:** **ninguno.** El DXF no contiene carpintería — es la misma ausencia estructural que ya invalida el
proxy de huecos (H3) y que `get_missing_data_warnings` declara en dos avisos distintos.

**¿Verificable desde DXF?:** **No.**

**Implementación actual:** ninguna.

**Problema detectado:** uno menor, de cita. El aviso existente dice *«Puertas de evacuación: no evaluable […] Mínimo CTE DB-SI:
0.80m de anchura libre en puertas de salida»* (`evaluator.py:160-164`). Los 0,80 m proceden de **DB-SI 3.4** (dimensionado, `C10`),
no de este apartado 3.6. La cifra es correcta; la atribución, imprecisa. Es exactamente el tipo de imprecisión que el corpus
versionado con localizador jerárquico (`NORMATIVE_ENGINE.md` §3.2) elimina por construcción.

**Nivel de confianza: DESCARTAR.**

**Acción recomendada:** no implementar. Al transcribir las reglas al corpus (Fase 1 de `NORMATIVE_ENGINE.md` §14), afinar la
atribución del aviso de puertas a DB-SI 3 §4.

---

```text
ID: C13
Nombre: Señalización de los medios de evacuación
Módulo: Sección DB-SI 3 — Evacuación de ocupantes
```

**Referencia normativa:** DB-SI 3, apartado 7 (señales UNE 23034:1988). **NORMA CONFIRMADA.**

**Requisito exacto:** señalización de salidas conforme a UNE 23034:1988. **Apartado a): los edificios de uso Residencial Vivienda
quedan exentos de la señal "SALIDA"** en salidas de recinto, planta y edificio. Otras exenciones: recintos ≤ 50 m² visibles desde
todo punto con ocupantes familiarizados; señal de dirección frente a toda salida de recinto con ocupación > 100 personas que acceda
lateralmente a un pasillo.

**Datos necesarios:** posición y tipo de señalización proyectada; ocupación por recinto.

**Datos disponibles actualmente:** ninguno — y no debería esperarse: la señalización no es materia de un plano de distribución.

**¿Verificable desde DXF?:** **No.**

**Implementación actual:** ninguna.

**Problema detectado:** ninguno. Pero esta ficha aporta el hallazgo más limpio del lote en la otra dirección: **para la tipología
principal de ArchMuse, el núcleo de este artículo no aplica por exención expresa**. Eso es información valiosa para el arquitecto y
hoy no existe forma de expresarla — es justamente el estado `no_aplica` con motivo de `NORMATIVE_ENGINE.md` §13, distinto tanto de
"cumple" como de "no evaluable".

**Nivel de confianza: DESCARTAR** — como regla evaluable.

**Acción recomendada:** no implementar. **Registrar la exención de Residencial Vivienda en el corpus** como `no_aplica` razonado,
para que el motor pueda explicarla en lugar de omitirla.

---

```text
ID: C14
Nombre: Control del humo de incendio
Módulo: Sección DB-SI 3 — Evacuación de ocupantes
```

**Referencia normativa:** DB-SI 3, apartado 8. **NORMA CONFIRMADA.**

**Requisito exacto:** sistema de control de humo obligatorio en tres supuestos alternativos: a) zonas de uso Aparcamiento que no sean
aparcamiento abierto; b) establecimientos Comercial o Pública concurrencia con ocupación > 1.000 personas; c) atrios con ocupación
> 500 personas en el sector, o previstos para evacuar > 500 personas. Parámetros específicos para aparcamientos mecánicos
(extracción ≥ 150 l/plaza·s, aportación ≤ 120 l/plaza·s, compuertas E300 60, ventiladores F300 60).

**Datos necesarios:** existencia y tipo de aparcamiento; ocupación; existencia de atrios; instalaciones de ventilación.

**Datos disponibles actualmente:** ninguno.

**¿Verificable desde DXF?:** **No.**

**Implementación actual:** ninguna.

**Problema detectado:** ninguno. Los tres supuestos de activación son ajenos a una vivienda plurifamiliar sin aparcamiento modelado;
pero, igual que en `C07`, ArchMuse no puede *demostrar* que no hay aparcamiento — sólo que no ve ninguno rotulado.

**Nivel de confianza: DESCARTAR.**

**Acción recomendada:** no implementar. Si algún día se declara la existencia de aparcamiento, resolver a `aplica` o `no_aplica` con
motivo; nunca por silencio.

---

```text
ID: C15
Nombre: Evacuación de personas con discapacidad en caso de incendio
Módulo: Sección DB-SI 3 — Evacuación de ocupantes
```

**Referencia normativa:** DB-SI 3, apartado 9. **NORMA CONFIRMADA.**

**Requisito exacto:** en edificios de **uso Residencial Vivienda con altura de evacuación superior a 28 m** (Residencial Público,
Administrativo o Docente > 14 m; Comercial o Pública Concurrencia > 10 m; plantas de Aparcamiento > 1.500 m²), toda planta que no sea
zona de ocupación nula y que no disponga de alguna salida del edificio accesible dispondrá de posibilidad de paso a un sector
alternativo mediante una salida de planta accesible, o bien de una zona de refugio con espacio para personas usuarias de silla de
ruedas. Excepción expresa: las plazas de refugio para personas con otro tipo de movilidad reducida (1 por cada 33 ocupantes) **no son
exigibles en uso Residencial Vivienda**.

**Datos necesarios:** altura de evacuación; identificación de salidas accesibles; geometría de zonas de refugio; ocupación (→ `C08`).

**Datos disponibles actualmente:** ninguno en el flujo DXF. En `/api/generar`, la altura de evacuación sería aproximable como
`plantas × altura_libre_m` — con la advertencia de que ese producto **no es** la altura de evacuación normativa (que se mide desde el
origen de evacuación hasta la salida del edificio, y no coincide con la suma de alturas libres al ignorar cantos de forjado).

**¿Verificable desde DXF?:** **No.**

**Implementación actual:** ninguna.

**Problema detectado:** el riesgo dominante aquí es simétrico y conviene nombrarlo. Para la inmensa mayoría de proyectos
residenciales (h ≤ 28 m, es decir, aproximadamente hasta 9 plantas) este artículo **no aplica**. Afirmar cumplimiento sería tan
erróneo como afirmar incumplimiento: en ambos casos el sistema estaría opinando sobre una condición de activación que no ha medido.

**Nivel de confianza: BAJA.**

**Acción recomendada:** **pasar a UNKNOWN.** No implementar como regla. Valorar, sólo en `/api/generar`, un aviso condicional cuando
la altura estimada se acerque a 28 m, marcando la estimación como hipótesis.

---

```text
ID: C16
Nombre: Dotación de instalaciones de protección contra incendios
Módulo: Sección DB-SI 4 — Instalaciones de protección contra incendios
```

**Referencia normativa:** DB-SI 4, apartado 1, Tabla 1.1. **NORMA CONFIRMADA.**

**Requisito exacto:** dotación de equipos e instalaciones según uso previsto y umbrales de superficie construida, altura de
evacuación y ocupación (extintores portátiles, bocas de incendio equipadas, columna seca, sistemas de detección y alarma,
hidrantes...). La tabla es una matriz uso × instalación × umbral.

**Datos necesarios:** uso previsto; superficie construida; altura de evacuación; ocupación; y —para comprobar la dotación— la
posición real de los equipos proyectados.

**Datos disponibles actualmente:** ninguna instalación de PCI está modelada en el DXF ni en el generador.

**¿Verificable desde DXF?:** **No.**

**Implementación actual:** ninguna.

**Problema detectado:** ninguno hoy. Vale la pena registrar que una de las exigencias de la tabla —*extintores a no más de 15 m de
recorrido desde todo origen de evacuación*— **sí sería geométricamente evaluable** el día que existan posiciones de extintor en el
modelo, reutilizando el grafo de adyacencia que `analyzer/adyacencia.py` ya provee. Es la única línea de DB-SI 4 con futuro
geométrico, y depende de un dato de entrada nuevo, no de una regla nueva.

**Nivel de confianza: DESCARTAR.**

**Acción recomendada:** no implementar. La propia candidata señala que la estructura plana de `parametros` no puede representar una
tabla matricial — de descomponerse algún día, sería una regla por celda, nunca un registro único.

---

```text
ID: C18
Nombre: Condiciones de aproximación y entorno (intervención de bomberos)
Módulo: Sección DB-SI 5 — Intervención de los bomberos
```

**Referencia normativa:** DB-SI 5, apartado 1 (1.1 viales de aproximación, 1.2 entorno del edificio). **NORMA CONFIRMADA.**

**Requisito exacto:** viales de aproximación con anchura libre ≥ 3,5 m, gálibo ≥ 4,5 m y capacidad portante ≥ 20 kN/m²; en tramos
curvos, radios de 5,30 / 12,50 m y anchura libre de circulación 7,20 m. **Espacio de maniobra obligatorio cuando la altura de
evacuación descendente > 9 m**: anchura libre ≥ 5 m, separación máxima del vehículo a fachada según altura (h ≤ 15 m → 23 m;
15 < h ≤ 20 m → 18 m; h > 20 m → 10 m), distancia máxima hasta los accesos ≤ 30 m, pendiente ≤ 10 %, resistencia al punzonamiento
≥ 100 kN sobre 20 cm. Vías sin salida > 20 m requieren espacio de maniobra. Zonas forestales: franja libre de 25 m y camino
perimetral de 5 m.

**Datos necesarios:** geometría del viario y del entorno de la parcela; altura de evacuación; posición de los accesos; pendientes y
capacidad portante del pavimento.

**Datos disponibles actualmente:** el DXF no contiene entorno urbano. En `/api/generar` existen `solar.ancho_m`, `solar.largo_m` y
`normativa.retranqueos_m`, que describen la parcela pero no el viario ni sus características.

**¿Verificable desde DXF?:** **No.**

**Implementación actual:** ninguna. Existe R25 `evaluate_retranqueos` (`evaluator.py`), pero es urbanismo municipal, no DB-SI.

**Problema detectado:** hay una relación conceptual tentadora que conviene desactivar por escrito: un retranqueo insuficiente podría
impedir el espacio de maniobra de 5 m que exige DB-SI 5. Es una **INFERENCIA TÉCNICA** razonable y probablemente cierta, pero **no es
lo que la norma dice** — DB-SI 5 regula el espacio de maniobra, no el retranqueo, y el espacio de maniobra puede resolverse en el
viario público sin depender del retranqueo. Convertir esa correlación en una incidencia de DB-SI sería fabricar una exigencia. Si
algún día interesa, su sitio es `chain_effects.py` como efecto derivado explícito, con su cadena causal visible, nunca como regla
normativa.

**Nivel de confianza: BAJA.**

**Acción recomendada:** **pasar a UNKNOWN.** No implementar. No vincularla a R25.

---

```text
ID: C19
Nombre: Accesibilidad por fachada (intervención de bomberos)
Módulo: Sección DB-SI 5 — Intervención de los bomberos
```

**Referencia normativa:** DB-SI 5, apartado 2. **NORMA CONFIRMADA.**

**Requisito exacto:** las fachadas a las que se refiere el apartado 1.2 deben disponer de huecos que permitan el acceso desde el
exterior al personal del servicio de extinción, con **altura de alféizar respecto del nivel de la planta ≤ 1,20 m**, **dimensiones
horizontal y vertical del hueco ≥ 0,80 m y 1,20 m** respectivamente, y **distancia máxima entre ejes verticales de dos huecos
consecutivos ≤ 25 m**, medida sobre la fachada. No deben instalarse en fachada elementos que impidan el acceso por dichos huecos
(salvo, con matices, en plantas con altura de evacuación ≤ 9 m).

**Datos necesarios:** posición, dimensión y altura de alféizar de cada hueco de fachada.

**Datos disponibles actualmente:** **ninguno.** El DXF no contiene carpintería.

**¿Verificable desde DXF?:** **No.**

**Implementación actual:** ninguna.

**Problema detectado:** ésta es la ficha con mayor **riesgo de reincidencia** de todo el lote, y por eso conviene ser explícito.

Es el segundo de los dos artículos del DB-SI (con `C05`) que se expresa en términos de huecos de fachada, y ArchMuse ya tiene una
"superficie de hueco": `window_area_m2 = long_side × WINDOW_TO_FACADE_RATIO` (`evaluator.py:1253`, usada por R15b y R19). Esa
expresión es el hallazgo H3 de `NORMATIVE_AUDIT.md` §6.3 — un 0,25 supuesto, dimensionalmente incoherente (metros presentados como
m²) y responsable del 41 % de las incidencias del proyecto de ejemplo. **No da posición de hueco, ni altura de alféizar, ni
separación entre ejes**, que es literalmente todo lo que este artículo mide.

Usarlo aquí trasladaría un defecto ya identificado desde materia de salubridad a materia de incendios, que es donde un falso
cumplimiento tiene peores consecuencias.

**Nivel de confianza: DESCARTAR.**

**Acción recomendada:** no implementar. **Prohibición explícita** de derivar esta regla del proxy de huecos existente, mientras el
modelo no incorpore carpintería real.

---

```text
ID: C20
Nombre: Generalidades (resistencia al fuego de la estructura)
Módulo: Sección DB-SI 6 — Resistencia al fuego de la estructura
```

**Referencia normativa:** DB-SI 6, apartado 1. **NORMA CONFIRMADA**, pero mayoritariamente descriptiva.

**Requisito exacto:** el apartado enmarca los métodos admisibles de evaluación de la estructura frente al fuego. Sólo dos de sus
siete párrafos tienen carácter de exigencia o permiso condicionado; el resto son descripción y remisiones a normas externas y a los
Anejos. Párrafo 7: *«si se utilizan los métodos simplificados indicados en este Documento Básico no es necesario tener en cuenta las
acciones indirectas derivadas del incendio»*.

**Datos necesarios:** ninguno de naturaleza geométrica; es un marco metodológico.

**Datos disponibles actualmente:** no aplica.

**¿Verificable desde DXF?:** **No.**

**Implementación actual:** ninguna.

**Problema detectado:** un defecto de la propia extracción, no del motor: la candidata declara `severidad_sugerida: procedimental`,
que **no pertenece a la escala cerrada de 4 valores** (bloqueante / riesgo variable / recomendable / preferencial) de
`DECISION_ENGINE.md` §3, reutilizada por `NORMATIVE_ENGINE.md` §7. El propio pipeline lo detectó (*«la severidad declarada no es una
de las 4 de la escala existente»*). Debe corregirse en el registro antes de cualquier promoción.

**Nivel de confianza: DESCARTAR.**

**Acción recomendada:** no implementar. Reclasificar como tipo `procedimental` (`NORMATIVE_ENGINE.md` §6) y **corregir la severidad
fuera de catálogo** en el registro de la candidata.

---

```text
ID: C21
Nombre: Resistencia al fuego de la estructura (criterio de suficiencia)
Módulo: Sección DB-SI 6 — Resistencia al fuego de la estructura
```

**Referencia normativa:** DB-SI 6, apartado 2. **NORMA CONFIRMADA.**

**Requisito exacto:** la resistencia es suficiente si el valor de cálculo del efecto de las acciones no supera la resistencia del
elemento en ningún instante del incendio; se admite comprobar sólo el instante de mayor temperatura según la curva normalizada
tiempo-temperatura. Alternativa por fuegos localizados (UNE-EN 1991-1-2:2004) en sectores de riesgo mínimo o donde no sea previsible
un fuego totalmente desarrollado.

**Datos necesarios:** modelo estructural completo, materiales, secciones y carga de fuego.

**Datos disponibles actualmente:** ninguno. ArchMuse no modela estructura.

**¿Verificable desde DXF?:** **No.**

**Implementación actual:** ninguna.

**Problema detectado:** ninguno. La elección entre los dos métodos depende además de condiciones cualitativas (*«no sea previsible la
existencia de fuegos totalmente desarrollados»*) que son criterio profesional, no umbral — es un caso de manual del tipo
`exigencia_cualitativa` de `NORMATIVE_ENGINE.md` §6: se expone, no se evalúa.

**Nivel de confianza: DESCARTAR.**

**Acción recomendada:** no implementar. Clasificar como `exigencia_cualitativa`.

---

```text
ID: C22
Nombre: Elementos estructurales principales
Módulo: Sección DB-SI 6 — Resistencia al fuego de la estructura
```

**Referencia normativa:** DB-SI 6, apartado 3, Tabla 3.1. **NORMA CONFIRMADA.**

**Requisito exacto:** clase de resistencia al fuego R exigible a los elementos estructurales principales (forjados, vigas y soportes)
en función del uso del sector, la posición (bajo rasante / sobre rasante) y la altura de evacuación. Condiciones específicas para
cubiertas ligeras no previstas para evacuación con altura ≤ 28 m, y para elementos de escaleras y pasillos protegidos.

**Datos necesarios:** identificación de los elementos estructurales, su material y sección, y la resistencia al fuego alcanzada;
altura de evacuación; uso del sector.

**Datos disponibles actualmente:** **ninguno.** El DXF que ArchMuse lee contiene polígonos de estancia, no estructura. Es la misma
laguna transversal que `ARCHITECTURAL_KNOWLEDGE_MAP.md` identifica limitando simultáneamente los Dominios 7, 8 y 11.

**¿Verificable desde DXF?:** **No.**

**Implementación actual:** ninguna.

**Problema detectado:** ninguno. La tabla es clara y perfectamente formalizable — el obstáculo no es normativo ni de modelado de
reglas, es de fuente de datos. Es un buen ejemplo de por qué el corpus normativo y el motor de evaluación son problemas separables:
esta regla puede vivir correctamente en el corpus durante años sin ser evaluable ni una sola vez.

**Nivel de confianza: DESCARTAR.**

**Acción recomendada:** no implementar. Transcribir al corpus como regla evaluable-en-el-futuro con estado `aplica_no_evaluable`.

---

```text
ID: C23
Nombre: Elementos estructurales secundarios
Módulo: Sección DB-SI 6 — Resistencia al fuego de la estructura
```

**Referencia normativa:** DB-SI 6, apartado 4. **NORMA CONFIRMADA.**

**Requisito exacto:** los elementos estructurales cuyo colapso no pueda ocasionar daños a los ocupantes ni comprometer la estabilidad
global, la evacuación o la compartimentación **no precisan cumplir ninguna exigencia** de resistencia al fuego. Los suelos que deban
garantizar la resistencia R de la Tabla 3.1, sí. Las estructuras sustentantes de cerramientos textiles (carpas) serán **R 30**, salvo
que se acredite que el elemento textil es T2 (UNE-EN 15619:2014) o C-s2,d0, o que no presenta perforación ≥ 20 cm² tras el ensayo
UNE-EN 14115:2002.

**Datos necesarios:** clasificación de cada elemento estructural como principal o secundario —que es un **juicio técnico**, no una
propiedad geométrica— y su resistencia al fuego.

**Datos disponibles actualmente:** ninguno.

**¿Verificable desde DXF?:** **No.**

**Implementación actual:** ninguna.

**Problema detectado:** ninguno. La condición de exención ("cuyo colapso no pueda ocasionar daños…") es criterio profesional puro,
Nivel 4 en la escala de `ARCHITECTURAL_KNOWLEDGE_MAP.md`. Los dos parámetros que la candidata extrajo (R 30 para carpas, 20 cm² de
perforación) son correctos pero pertenecen a un supuesto —cerramientos textiles— ajeno a la edificación residencial.

**Nivel de confianza: DESCARTAR.**

**Acción recomendada:** no implementar.

---

```text
ID: C24
Nombre: Determinación de los efectos de las acciones durante el incendio
Módulo: Sección DB-SI 6 — Resistencia al fuego de la estructura
```

**Referencia normativa:** DB-SI 6, apartado 5 (fórmulas 5.2 y 5.3). **NORMA CONFIRMADA**, de naturaleza procedimental.

**Requisito exacto:** deben considerarse las mismas acciones permanentes y variables que en situación persistente, si es probable que
actúen en caso de incendio. Simplificaciones admitidas: tomar sólo el efecto de la temperatura si se usan los métodos del propio
DB-SI, y estimar el efecto en situación de incendio a partir del de situación persistente mediante los coeficientes de las
fórmulas 5.2/5.3.

**Datos necesarios:** modelo de cálculo estructural y los coeficientes γ_G, γ_Q,1, ψ_1,1 — que el segmento **no proporciona**: remite
al DB-SE §4.2.2, no ingerido.

**Datos disponibles actualmente:** ninguno.

**¿Verificable desde DXF?:** **No.**

**Implementación actual:** ninguna.

**Problema detectado:** ninguno en el motor. Sí una nota para el corpus: la regla depende de valores que viven en otro Documento
Básico no ingerido, lo que la convierte en candidata natural para una arista `remite_a` del grafo tipado de `NORMATIVE_ENGINE.md` §9
en lugar de un registro con parámetros propios.

**Nivel de confianza: DESCARTAR.**

**Acción recomendada:** no implementar. Modelar la dependencia al DB-SE como arista, no duplicar coeficientes.

---

```text
ID: C25
Nombre: Determinación de la resistencia al fuego
Módulo: Sección DB-SI 6 — Resistencia al fuego de la estructura
```

**Referencia normativa:** DB-SI 6, apartado 6. **NORMA CONFIRMADA.**

**Requisito exacto:** la resistencia al fuego de un elemento puede establecerse por tablas y métodos simplificados de los Anejos C a
F, por ensayo conforme a normas UNE-EN, o por métodos generales de cálculo. *«Los valores de los coeficientes parciales de
resistencia en situación de incendio deben tomarse iguales a la unidad: γ_M,fi = 1»*, salvo que el anejo del material específico
indique lo contrario.

**Datos necesarios:** los Anejos C a F, **no ingeridos**; y el modelo estructural.

**Datos disponibles actualmente:** ninguno.

**¿Verificable desde DXF?:** **No.**

**Implementación actual:** ninguna.

**Problema detectado:** dos defectos de la propia extracción, ambos ya señalados por el pipeline: (a) *«declara patrón/parámetro en
un tipo de regla no evaluable, o al revés»* — coherente con la validación 3 de `NORMATIVE_ENGINE.md` §11.1; (b) el único parámetro
extraído (γ_M,fi = 1) es un coeficiente de cálculo, no un umbral de proyecto, y no debería viajar como parámetro evaluable.

**Nivel de confianza: DESCARTAR.**

**Acción recomendada:** no implementar. Retirar el parámetro γ_M,fi del registro o reclasificarlo; la regla es procedimental y remite
a anejos no ingeridos.

---

## 2. Tabla resumen

| ID | Regla | Referencia | Verificable DXF | Confianza | Acción |
|---|---|---|---|---|---|
| C01 | Compartimentación en sectores de incendio | DB-SI 1 §1, Tablas 1.1 y 1.2 | Parcial | **MEDIA** | Corregir cita (SI-3→SI-1) y reclasificar el proxy de solape |
| C02 | Locales y zonas de riesgo especial | DB-SI 1 §2, Tablas 2.1 y 2.2 | Parcial | **MEDIA** | Requiere taxonomía de locales en el parser; no implementar ahora |
| C03 | Espacios ocultos y paso de instalaciones | DB-SI 1 §3 | No | DESCARTAR | No implementar; aviso de no evaluable |
| C04 | Reacción al fuego de elementos constructivos | DB-SI 1 §4, Tabla 4.1 | No | DESCARTAR | No implementar; registrar exención nota (4) |
| C05 | Medianerías y fachadas | DB-SI 2 §1 | No | DESCARTAR | No implementar; prohibido usar el proxy de huecos |
| C06 | Cubiertas | DB-SI 2 §2 | No | DESCARTAR | No implementar |
| C07 | Compatibilidad de elementos de evacuación | DB-SI 3 §1 | No | DESCARTAR | UNKNOWN condicionado; nunca `no_aplica` por silencio |
| C08 | **Cálculo de la ocupación** | **DB-SI 3 §2, Tabla 2.1 (20 m²/pers.)** | **Sí** | **ALTA** | **Regla nueva (Fact derivado) — prioridad máxima; PRD previo** |
| C09 | Nº de salidas y longitud de recorridos | DB-SI 3 §3, Tabla 3.1 | Parcial | **BAJA** | Corregir + degradar a UNKNOWN; resolver duplicación D4 |
| C10 | Dimensionado de los medios de evacuación | DB-SI 3 §4, Tabla 4.1 | Parcial | **BAJA** | No implementar; documentar que no respalda el pasillo interior |
| C11 | Protección de las escaleras | DB-SI 3 §5, Tabla 5.1 | No | **BAJA** | UNKNOWN; mantener aviso; posible aviso condicional |
| C12 | Puertas en recorridos de evacuación | DB-SI 3 §6 | No | DESCARTAR | No implementar; afinar atribución del aviso a SI 3 §4 |
| C13 | Señalización de los medios de evacuación | DB-SI 3 §7 | No | DESCARTAR | No implementar; registrar exención Residencial Vivienda |
| C14 | Control del humo de incendio | DB-SI 3 §8 | No | DESCARTAR | No implementar |
| C15 | Evacuación de personas con discapacidad | DB-SI 3 §9 | No | **BAJA** | UNKNOWN; posible aviso condicional en `/api/generar` |
| C16 | Dotación de instalaciones de PCI | DB-SI 4 §1, Tabla 1.1 | No | DESCARTAR | No implementar |
| C18 | Aproximación y entorno (bomberos) | DB-SI 5 §1 | No | **BAJA** | UNKNOWN; no vincular a R25 (retranqueos) |
| C19 | Accesibilidad por fachada (bomberos) | DB-SI 5 §2 | No | DESCARTAR | No implementar; prohibido derivar del proxy de huecos |
| C20 | Generalidades (estructura) | DB-SI 6 §1 | No | DESCARTAR | Reclasificar `procedimental`; corregir severidad fuera de catálogo |
| C21 | Resistencia al fuego de la estructura | DB-SI 6 §2 | No | DESCARTAR | Clasificar `exigencia_cualitativa` |
| C22 | Elementos estructurales principales | DB-SI 6 §3, Tabla 3.1 | No | DESCARTAR | Transcribir al corpus como `aplica_no_evaluable` |
| C23 | Elementos estructurales secundarios | DB-SI 6 §4 | No | DESCARTAR | No implementar |
| C24 | Efectos de las acciones durante el incendio | DB-SI 6 §5 | No | DESCARTAR | Modelar remisión al DB-SE como arista `remite_a` |
| C25 | Determinación de la resistencia al fuego | DB-SI 6 §6 | No | DESCARTAR | Retirar el parámetro γ_M,fi; procedimental |

---

## 3. Clasificación por acción

### 3.1 Mantener tal cual

**Ninguna.**

No es una omisión: es el resultado. De las 24 candidatas, sólo dos tienen hoy alguna implementación en `evaluator.py` (`C01` → R26 y
`C09` → R17), y **ambas necesitan corrección**. Las otras 22 no están implementadas, así que no hay nada que mantener.

Dicho sin rodeos: **ArchMuse no tiene hoy ninguna regla de DB-SI correctamente respaldada y correctamente citada.**

### 3.2 Corregir

| ID | Qué corregir | Dónde |
|---|---|---|
| C01 | Cita `CTE-DB-SI-3` → DB-SI 1 §1; separar del código que usa R17; reclasificar el solape de huellas como integridad geométrica sin lenguaje de sectorización | `evaluator.py:3000` y su mensaje |
| C09 | Retirar el veredicto de cumplimiento contra 25 m del recorrido interior; declarar no evaluable el recorrido normativo; unificar con la medición duplicada de `circulation.py` (D4) | `evaluator.py:1555`, `:1583`; `circulation.py` |
| C10 | Documentar que DB-SI 3 §4 **no** respalda el ancho de pasillo interior, para que la revisión de la cita de R06 no derive hacia DB-SI | documentación de R06 |
| C12 | Afinar la atribución del aviso de puertas: los 0,80 m son de DB-SI 3 §4, no de §6 | `evaluator.py:160-164` |
| C20 | `severidad_sugerida: procedimental` está fuera de la escala cerrada de 4 valores | registro de la candidata |
| C25 | El parámetro γ_M,fi = 1 es un coeficiente de cálculo, no un umbral de proyecto | registro de la candidata |

### 3.3 Requieren nuevos datos del parser (o del formulario)

| ID | Dato que falta | Comentario |
|---|---|---|
| C08 | Uso previsto declarado + definición normativa de superficie útil + ámbito "planta" | Lo demás ya existe. Es el desbloqueo de toda la sección SI 3 |
| C01 | Superficie **construida** por sector + altura de evacuación | La superficie útil actual no sirve para el límite de 2.500 m² |
| C02 | Taxonomía tipada de locales no habitables (trastero, contadores, calderas…) | Hoy `Room.label` es texto libre; depender del rótulo repetiría el fallo de R18c |
| C11, C15 | Altura de evacuación real | Aproximable en `/api/generar`, inexistente en el flujo DXF |
| C10, C12, C19, C05 | Carpintería (huecos y puertas: posición, dimensión, alféizar, sentido de apertura) | Es la misma ausencia que invalida el proxy H3. Un solo dato desbloquearía cuatro fichas |
| C16 | Posiciones de equipos de PCI | Sólo entonces el criterio de 15 m sería evaluable con `adyacencia.py` |

### 3.4 Deben pasar a UNKNOWN

`C07`, `C09` (la parte normativa; la medición interior se conserva como métrica informativa), `C11`, `C15`, `C18`.

En los cinco casos el patrón es el mismo y es el que `INFERENCE_ENGINE.md` §2.2 exige: **la condición de activación no se ha podido
medir**, de modo que ni "cumple" ni "no cumple" son afirmaciones sostenibles. El estado correcto es declarar que no se ha comprobado.

### 3.5 Deben eliminarse

No hay reglas implementadas que eliminar por completo. Lo que **sí** debe eliminarse:

1. **El código `CTE-DB-SI-3` en R26** (`C01`). No es una imprecisión de redacción: atribuye a Evacuación de ocupantes una exigencia de
   Propagación interior, y hace indistinguibles dos incumplimientos distintos que hoy comparten código.
2. **La afirmación de cumplimiento de R17 contra los 25 m** (`C09`). El número medido puede quedarse; el veredicto normativo, no.
3. **Cualquier uso futuro del proxy `ancho_fachada × 0,25` en materia de incendios** (`C05`, `C19`). Eliminación preventiva, por
   escrito, antes de que ocurra.

---

## 4. Recuento final

| Métrica | Valor |
|---|---|
| Reglas revisadas | **24** |
| **ALTA** | **1** — `C08` (cálculo de la ocupación) |
| **MEDIA** | **2** — `C01`, `C02` |
| **BAJA** | **5** — `C09`, `C10`, `C11`, `C15`, `C18` |
| **DESCARTAR** | **16** — `C03`, `C04`, `C05`, `C06`, `C07`, `C12`, `C13`, `C14`, `C16`, `C19`, `C20`, `C21`, `C22`, `C23`, `C24`, `C25` |

**Verificabilidad desde DXF:**

| Estado | Nº | IDs |
|---|---|---|
| **Sí** | **1** | `C08` |
| **Parcial** | **4** | `C01`, `C02`, `C09`, `C10` |
| **No** | **19** | el resto |

Es decir: **de 24 exigencias del DB-SI, exactamente 1 es hoy comprobable de forma fiable desde un DXF de planta, y 4 más lo son
parcialmente. Las 19 restantes (79 %) no lo son con ningún grado de fiabilidad.**

**Requieren cambios posteriores:** 12 fichas.

- **6 correcciones** sobre lo existente (`C01`, `C09`, `C10`, `C12`, `C20`, `C25`) — no son capacidad nueva y, según `CLAUDE.md`, no
  necesitan PRD.
- **1 capacidad nueva** (`C08`) — sí requiere PRD previo.
- **5 degradaciones a UNKNOWN** (`C07`, `C11`, `C15`, `C18`, y la parte normativa de `C09`).
- Las **6 entradas de "nuevos datos del parser"** (§3.3) son requisitos de habilitación, no tareas independientes: bloquean a las
  anteriores más que constituir trabajo por sí solas.

---

## 5. Conclusión

Tres hechos, en orden de importancia.

**1. Falta un Hecho, no faltan reglas.** La ausencia del cálculo de ocupación (`C08`) es la causa estructural de que toda la sección
SI 3 sea inevaluable. No es una regla más de la lista: es el insumo del que dependen `C09`, `C10`, `C15` y parte de `C16`. Es también
la única de las 24 con confianza ALTA y verificabilidad plena, y su umbral (20 m²/persona para plantas de vivienda) está verificado
literalmente contra el texto ingerido. Es, con diferencia, la acción de mayor valor por unidad de esfuerzo de este lote.

**2. Las dos reglas de DB-SI que existen hoy miden algo distinto de lo que citan.** R26 comprueba solapes de polígonos y lo llama
sectorización de incendio; R17 mide un recorrido dentro de una vivienda y lo compara con un umbral que la norma define hasta la
salida de planta. Ninguna de las dos es negligente —los docstrings son honestos y R17 fue corregida de buena fe en agosto— pero en
ambas **la honestidad del docstring no sobrevive al viaje hasta la pantalla**, que es exactamente el patrón H1 de
`NORMATIVE_AUDIT.md` repitiéndose en materia de incendios.

**3. La proporción 1 de 24 no es un fracaso de la extracción: es el diagnóstico.** El DB-SI regula sectores, resistencias al fuego,
instalaciones, señalización, estructura y accesos de bomberos. Un modelo compuesto por polígonos de estancia en planta, sin
carpintería, sin materiales, sin estructura, sin instalaciones y sin zonas comunes, no puede comprobar casi nada de eso — y no es un
defecto del motor de reglas, es la frontera del dato de entrada. Lo que esta revisión sí establece es cuál es esa frontera, con
nombre y apellidos, en lugar de dejar que se cruce sin que nadie lo note.

La conclusión operativa es la misma que gobierna el resto de la serie: ArchMuse no puede afirmar que un edificio cumple el DB-SI.
Puede, si se hacen las 6 correcciones y se calcula la ocupación, afirmar algo mucho más pequeño y mucho más defendible — **qué
condiciones concretas ha comprobado, cuáles no, y por qué.**

---

*Revisión de solo lectura. Ninguna línea de código modificada. Ninguna regla implementada. Ninguna candidata promocionada. Las
conclusiones normativas de este documento requieren validación de un técnico competente antes de traducirse en cambios de código,
conforme a la regla de dos personas de `docs/design/NORMATIVE_ENGINE.md` §12.*
