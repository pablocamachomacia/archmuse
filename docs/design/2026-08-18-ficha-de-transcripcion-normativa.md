# Ficha de transcripción normativa — procedimiento del curador

**Fecha:** 2026-08-18 · **Estado:** propuesta, no aprobada · **Cierra:** tarea V0-5 del plan de migración v2
**Destinatario:** el arquitecto colegiado que transcribe. No hace falta saber programar.

---

## 0. Qué es esto y por qué existe

El motor normativo de ArchMuse está construido: `normativa/` son 3.777 líneas que resuelven, para un proyecto en un municipio concreto, qué normas le son exigibles y con qué prioridad. Está probado y funciona.

**Y no tiene nada que resolver.** El directorio `normativa/es/` está vacío: cero reglas. Hoy el sistema responde correctamente que, para cualquier proyecto, falta *toda* la normativa exigible — que es lo honesto, pero no es un producto.

El cuello de botella no es técnico. **Es una persona leyendo el articulado y escribiéndolo en una ficha.** Este documento es esa ficha.

**La regla que gobierna todo lo demás:** una cifra que llega a un entregable sale del corpus o de la geometría del plano. De ningún otro sitio. Si el corpus no la tiene, ArchMuse dice que no lo sabe. Nunca la deduce, nunca la recuerda, nunca la aproxima.

---

## 1. Alcance: qué se transcribe y qué no

### Sí se transcribe

| Tipo | Ejemplo | `tipo` en la ficha |
|---|---|---|
| Un umbral numérico exigible | «la longitud de los recorridos de evacuación no excede de 25 m» | `exigencia_cuantitativa` |
| Una obligación de que algo exista | «toda vivienda dispondrá de…» | `exigencia_de_presencia` |
| Una definición que otras reglas usan | qué se entiende por «origen de evacuación» | `definicion` |
| Una remisión a otra norma | «se medirá según DB-SUA 1» | `remision` |
| Una exigencia sin número | «se garantizará la estanqueidad» | `exigencia_cualitativa` |

### No se transcribe

- **Lo que no es exigible.** Comentarios, notas al pie explicativas, ejemplos ilustrativos, anejos informativos.
- **Lo que ya está en el motor como dato geográfico.** Zona climática y densidad urbana se derivan del municipio; están en `normativa/geografia/`.
- **Lo que no se puede citar.** Si no hay boletín oficial e identificador, no hay norma; y sin norma, no hay regla. Un criterio de buena práctica no entra aquí.
- **Lo dudoso.** Si no está claro si una frase es exigencia o contexto, **no se transcribe y se anota en la lista de dudas.** Una regla mal transcrita es peor que una regla ausente: la ausencia se ve, el error no.

### Prioridad de transcripción

En este orden, y no se pasa al siguiente hasta cerrar el anterior:

1. **DB-SI** (seguridad en caso de incendio) — es donde el motor ya tiene 38 reglas escritas a mano en Python que hoy no tienen respaldo declarativo.
2. **DB-SUA** (seguridad de utilización y accesibilidad).
3. **DB-HS 3** (calidad del aire) y **DB-HE 1** (limitación de demanda), por este orden.
4. Autonómico de la Comunidad de Madrid, y después ordenanza municipal, solo para los municipios donde ya haya proyectos reales.

---

## 2. Formato de entrega

Un fichero **YAML** por materia y ámbito, en la ruta que fija el ámbito:

```
normativa/es/estatal/seguridad_incendio.yaml          norma estatal
normativa/es/13-madrid/autonomico/accesibilidad.yaml  norma autonómica
normativa/es/13-madrid/municipios/28115-pozuelo-de-alarcon/urbanismo.yaml
```

YAML y no una hoja de cálculo por un motivo concreto: el cambio de una regla tiene que ser **legible en un diff** por quien lo revisa, y admite comentarios y texto legal multilínea.

Cada fichero declara **una** norma fuente y **una o más** reglas que salen de ella. La forma exacta la comprueba `normativa/esquema/regla.schema.json` de manera automática: un fichero mal formado se rechaza con el motivo, no entra a medias.

### Los campos, y qué se espera en cada uno

**Bloque `norma`** — de dónde sale. Se cita, nunca se evalúa.

| Campo | Qué poner | De dónde se saca |
|---|---|---|
| `fuente.rango` | `Real Decreto`, `Ley`, `Orden`, `Ordenanza`, `Plan`, `Documento técnico` | La cabecera del boletín |
| `fuente.organismo` | El ministerio o administración que la dicta | Ídem |
| `fuente.identificador_oficial` | `RD 314/2006`, `Ordenanza 5/2019`… | Ídem |
| `fuente.boletin` | El identificador del boletín: `BOE-A-2006-5515` | boe.es |
| `fuente.url_oficial` | Enlace al texto consolidado | boe.es o codigotecnico.org |
| `articulo` | Documento básico, sección, apartado, punto, tabla | El propio texto |
| `vigencia.vigencia_desde` | Fecha de entrada en vigor, no de publicación | La disposición final |

**Bloque `reglas`** — qué exige. Una por exigencia distinguible.

| Campo | Qué poner |
|---|---|
| `nombre` | Una frase que un arquitecto reconozca. No el número del artículo |
| `materia` | Del catálogo cerrado de `normativa/esquema/materias.yaml` |
| `tipo` | De la tabla de §1 |
| `prioridad` | `bloqueante` (impide visado u obra), `riesgo_variable`, `recomendable`, `preferencial`. **No es la jerarquía de la norma**: es cuánto duele incumplirla |
| `nivel_de_conocimiento` | `2` para todo lo transcrito de una norma. `1` es un hecho objetivo, `3` buena práctica, `4` criterio — no se usan aquí |
| `aplicabilidad.ambito`, `.usos`, `.tipologias` | A quién aplica. Vacío significa «a todos» |
| `parametro` | La tabla de valores por ejes, con su cadena de repliegue. Ver §3 |
| `mensaje` | Lo que el arquitecto leerá cuando la regla no se cumpla |
| `explicacion_tecnica` | El porqué, en el lenguaje del artículo |

**Bloque `literal`** (dentro de `norma`) — **el texto tal cual**, copiado del documento oficial, sin resumir ni reordenar. Es lo que sostiene que la cita sea una cita.

---

## 3. La parte difícil: `parametro` y el repliegue

Un umbral casi nunca es un número. Es **una tabla con excepciones**, y el motor necesita saber en qué orden buscar.

- `ejes`: las variables que hacen que el valor cambie (`numero_salidas`, `uso`, `altura_evacuacion`…).
- `valores`: una fila por combinación, con las condiciones que la seleccionan.
- `repliegue`: **el orden en que se busca** cuando el proyecto no encaja en ninguna fila exacta. Se lee de izquierda a derecha; el último suele ser `ninguno`, que significa «si llegas aquí, no hay valor aplicable y hay que decirlo».

La cadena de repliegue es lo que impide el peor fallo posible: coger el valor de otra fila porque «se le parece». Cada repliegue que el motor usa queda escrito en la evidencia, así que el arquitecto ve por qué se le aplicó ese número y no otro.

**Si una norma no encaja en ninguno de los cinco patrones** (`UMBRAL_SIMPLE`, `UMBRAL_CON_EXCEPCION`, `PRESENCIA_OBLIGATORIA`, `COMBINACION_LOGICA`, `AGREGACION_AMBITO`), la primera hipótesis es que está mal clasificada, no que falte un patrón. Añadir un sexto patrón es una decisión de gobernanza, nunca la reacción a una norma incómoda.

---

## 4. Criterios de calidad

Una entrada se acepta cuando cumple **las siete**. Las cuatro primeras las comprueba la máquina; las tres últimas, una persona.

**Automáticas** (`normativa/validacion.py` + el esquema JSON). Las ejecutas tú, sin ayuda de nadie:

```
python scripts/validar_corpus.py
```

Sale con código 1 si algo falla, y dice el fichero, la regla y el motivo con el número de la validación que ha protestado, para que puedas volver aquí y leer qué exige.


1. **Forma válida.** Pasa `regla.schema.json`: campos obligatorios, tipos y catálogos cerrados.
2. **Catálogos respetados.** `materia`, `uso`, `tipologia`, `tipo` y `prioridad` existen en su catálogo. Un valor inventado se rechaza.
3. **Coherencia documento-materia.** Una regla de `seguridad_incendio` no puede citar DB-SUA. Es la validación que habría impedido las cinco discrepancias documentadas en `docs/audits/NORMATIVE_AUDIT.md`.
4. **Aristas resolubles y sin ciclos.** Si una regla dice que deroga o endurece a otra, esa otra tiene que existir.

**Humanas** (revisión de un segundo colegiado, o de quien encargó):

5. **Fidelidad al literal.** Cada número de la ficha aparece en el texto citado. Se comprueba leyendo el `literal` y la ficha en paralelo. Un número que no esté en el literal es motivo de rechazo, sin discusión.
6. **Localización exacta.** `articulo` apunta al sitio donde un tercero puede ir a comprobarlo en un minuto.
7. **El mensaje sirve.** `mensaje` le dice a un arquitecto qué hacer, no le repite el artículo.

**Dónde vive una regla que ya has escrito pero nadie ha firmado.** En `normativa/cobertura/manifiesto.yaml`, como `transcrito_sin_firmar`. No es un estado provisional ni un apaño: es donde vive **toda** regla entre que la escribes y que alguien la revisa, y significa exactamente «está en disco y ArchMuse no afirma nada sobre ella». No lo declares `parcial` para que «salga cobertura»: la carga lo rechaza mientras la regla conserve su etiqueta `pendiente_firma_colegiado`, y con motivo — `parcial` es lo que autoriza a ArchMuse a evaluar proyectos contra esa regla.

**Y una regla de proceso que vale más que las siete:** ante la duda, no se transcribe. La lista de dudas es un entregable tan válido como las reglas; alimenta directamente lo que ArchMuse declara como «no comprobado».

---

## 5. Cadencia y flujo de trabajo

1. El curador transcribe un bloque coherente (una sección de un DB, no reglas sueltas).
2. Entrega el YAML más su lista de dudas.
3. La máquina pasa las validaciones 1-4. Si falla, vuelve con el motivo concreto.
4. Un segundo par de ojos pasa las 5-7.
5. Entra al corpus. A partir de ahí, ArchMuse la aplica y la cita.

**Cadencia propuesta:** entregas semanales, de tamaño de una sesión de trabajo. Es mejor una sección cerrada y revisada por semana que un documento básico entero sin revisar: el corpus vale por lo que se puede defender, no por lo que ocupa.

**Trazabilidad:** cada entrada lleva su vigencia y su boletín, así que un análisis emitido hace dos años se puede reproducir con el corpus que estaba vigente entonces. Es lo que permite defender una firma ante una reclamación, y por eso `vigencia_desde` no es un adorno.

---

## 6. Regla piloto: DB-SI 3, apartado 3, Tabla 3.1

Transcrita como demostración de que la cadena entera funciona: `normativa/es/estatal/seguridad_incendio.yaml`.

**Por qué esta.** Es cuantitativa, tiene excepciones por dos ejes distintos (número de salidas y uso), y por tanto ejercita `parametro`, `ejes` y `repliegue` — la parte difícil de §3. Si la ficha sirve para esta, sirve para casi todo DB-SI.

**Fuente:** Real Decreto 314/2006, de 17 de marzo, por el que se aprueba el Código Técnico de la Edificación (BOE-A-2006-5515, Ministerio de Vivienda, 28-03-2006), Documento Básico SI, sección SI 3 «Evacuación de ocupantes», apartado 3, Tabla 3.1.

**El literal se copió del PDF oficial** que el repositorio ya guarda en `tests/fixtures/codigotecnico/DB-SI.pdf`, no de memoria ni de una fuente secundaria. Es el procedimiento que esta ficha exige, aplicado a sí misma.

**Los seis valores que salen de la tabla:**

| Salidas | Condición | Longitud máxima |
|---|---|---:|
| Una única salida | general | 25 m |
| Una única salida | uso Aparcamiento | 35 m |
| Una única salida | planta con salida directa a espacio exterior seguro y ocupación ≤ 25 personas | 50 m |
| Más de una salida | general | 50 m |
| Más de una salida | zonas con ocupantes que duermen; hospitalización o tratamiento intensivo; escuela infantil o primaria | 35 m |
| Más de una salida | espacios al aire libre con riesgo de incendio irrelevante | 75 m |

**Dudas que la transcripción deja abiertas**, y que son parte del entregable:

- «Ocupantes que duermen» no está definido en el propio apartado. Un uso Residencial Vivienda ¿entra siempre? La transcripción **no lo asume**: aplica el valor general y deja el caso sin resolver hasta que un colegiado lo dictamine.
- «Espacio exterior seguro» y «origen de evacuación» son definiciones del Anejo A del propio DB-SI. Hasta que se transcriban como `tipo: definicion`, las filas que dependen de ellas no pueden evaluarse automáticamente y el motor debe declararlas `UNKNOWN` con motivo.
- La altura de evacuación (28 m descendente, 10 m ascendente) es una condición **distinta** de la longitud del recorrido y va en su propia regla. No se mezcla en esta ficha.

---

## 7. Lo que este documento no resuelve

- **No convierte el corpus en un problema de software.** Sigue siendo una persona leyendo. Esta ficha solo hace que esa persona pueda empezar el lunes.
- **No fija cuánto se tarda.** Nadie ha medido cuántas reglas por sesión salen de un DB real. La primera entrega es también la primera medición.
- **No cierra el catálogo de materias ni el de patrones.** Ampliarlos es gobernanza, con la disciplina de §3.
