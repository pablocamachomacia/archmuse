# CHAIN_REASONING.md

**Propósito:** este documento diseña, en profundidad, el Dominio 12 (Efectos en Cadena y Resolución de Conflictos) de `BRAIN_ARCHITECTURE.md` — el dominio que `ARCHITECTURAL_KNOWLEDGE_MAP.md` señaló como el de mayor valor estratégico a largo plazo y, a la vez, el que menos conocimiento documentado tiene hoy. Este documento es el primer depósito real de conocimiento en ese dominio.

No es una lista de reglas. Es un **modelo de propagación de consecuencias**: cómo un cambio en un punto del proyecto se convierte, en la cabeza de un arquitecto experimentado, en una cadena de efectos sobre el resto del proyecto — qué se activa, en qué orden, con qué certeza, y cómo se decide cuándo parar de seguir esa cadena.

El punto de partida no es el sistema. Es la pregunta que se hace un arquitecto sénior cuando, con el proyecto ya avanzado, mueve un muro: **"¿qué más deja de ser cierto si hago esto?"**

---

## 1. Qué tipos de cambios pueden ocurrir en un proyecto

Un cambio, a efectos de este modelo, no es "cualquier edición del plano" — es cualquier modificación que altera un **hecho** del que dependen una o más evaluaciones ya realizadas. Los cambios reales en un proyecto residencial avanzado se agrupan en ocho familias:

**A. Cambios geométricos de límite** — mover, añadir o eliminar un muro o tabique; cambiar el perímetro de una estancia.

**B. Cambios de apertura y hueco** — mover, ampliar, reducir, añadir o eliminar una puerta, ventana, o patio de luces.

**C. Cambios de superficie y programa** — ampliar o reducir una habitación; cambiar el uso declarado de una pieza (de trastero a dormitorio, de office a dormitorio).

**D. Cambios de elementos verticales de circulación** — mover, redimensionar o cambiar el tipo de escalera o ascensor.

**E. Cambios de núcleos técnicos** — mover un baño, una cocina, o un espacio de instalaciones.

**F. Cambios de composición constructiva sin mover geometría** — cambiar el material o el grosor de un muro (por ejemplo, reforzar su masa acústica) sin desplazar su posición.

**G. Cambios de agregación de unidades** — dividir una vivienda en dos, o fusionar dos viviendas en una.

**H. Cambios de volumen o emplazamiento general** — cambiar la altura libre de una planta, el número de plantas, el retranqueo a lindero, o la posición del edificio en la parcela.

Esta clasificación importa porque **cada familia tiene un patrón de propagación característico**: las familias A-C afectan sobre todo dentro de la misma planta y vivienda; D y H tienden a propagarse verticalmente entre plantas; E y F afectan sobre todo a dominios técnicos concretos (instalaciones, acústica); G es la única familia que puede cambiar qué normativa aplica de raíz, no solo si se cumple.

---

## 2. Qué dominios pueden verse afectados, por tipo de cambio

| Familia de cambio | Dominios directamente afectados (primer salto) |
|---|---|
| A. Límite geométrico (muro/tabique) | 3 (Geometría), y a través de él, potencialmente 5, 6, 7, 10 |
| B. Apertura/hueco (puerta, ventana, patio) | 4 (Iluminación/Ventilación), 8 (Térmica), 7 (Acústica si da a fachada ruidosa) |
| C. Superficie/uso de pieza | 2 (Programa/Tipología si cambia el uso), 3 (Geometría), 4, 5, 6 |
| D. Elemento vertical de circulación | 3, 5 (Accesibilidad), 6 (Evacuación), 11 (Estructura) |
| E. Núcleo técnico (baño/cocina) | 10 (Instalaciones), 7 (Acústica), 3 |
| F. Composición constructiva | 7 (Acústica), 8 (Térmica), 11 (Estructura si afecta a un elemento portante) |
| G. Agregación de unidades | 2 (Programa/Tipología), 5, 6, 7 — prácticamente todos, por ser un cambio de marco, no de detalle |
| H. Volumen/emplazamiento | 1 (Urbanístico), 8 (Térmica), 11 (Estructura) |

Esta tabla es solo el **primer salto**. La parte más importante de este documento — y la que un checklist plano nunca captura — es lo que ocurre después de ese primer salto: cómo esos dominios afectados, a su vez, afectan a otros.

---

## 3. Cómo se propagan las consecuencias

El mecanismo de propagación no consiste en que los dominios "se avisen entre sí" — consiste en que **un cambio altera un hecho, ese hecho es entrada de una o más evaluaciones de dominio, y la diferencia entre el resultado anterior y el nuevo resultado es lo que se propaga**. Es, conceptualmente, el mismo principio por el que una hoja de cálculo recalcula: no hace falta que una celda "sepa" de las demás, basta con que dependa de un valor que ha cambiado.

El proceso, paso a paso, tal como lo recorre un arquitecto experimentado:

1. **Se identifica el hecho alterado** (Capa 1 de `BRAIN_ARCHITECTURE.md`) — qué dato objetivo ha cambiado: una superficie, una posición, un uso, una composición constructiva.
2. **Se re-evalúan todos los dominios cuya entrada incluye directamente ese hecho** — esto produce el conjunto de *efectos inmediatos* (ver sección 4).
3. **Para cada dominio cuyo resultado ha cambiado, se identifican los dominios que consumen ese resultado como entrada** (no el hecho original, sino la conclusión ya elaborada de otro dominio) — esto produce los *efectos indirectos*.
4. **El paso 3 se repite, siguiendo el grafo de dependencias por capas** (ver sección 6), hasta que ningún dominio adicional cambia su conclusión — este es el **punto fijo** de la propagación, el momento en que la cadena se agota de forma natural.
5. **En paralelo, se acumula un registro de todos los cambios de la sesión de edición**, no solo del último — porque algunos efectos solo aparecen cuando varios cambios pequeños se suman (ver *efectos acumulativos*, sección 4).

Una regla estructural importante: la propagación **sigue siempre la dirección de las dependencias del grafo de capas** definido en `BRAIN_ARCHITECTURE.md` (Parte 3) — nunca "sube" de una capa inferior a una superior salvo hacia el Dominio 12 mismo. Esto es lo que impide que la propagación se convierta en una red de vuelta y vuelta sin fin (desarrollado en la sección 8).

---

## 4. Consecuencias inmediatas, indirectas y acumulativas

**Inmediatas** — el primer salto de la propagación. Se detectan sin necesitar ningún otro cambio previo: re-evaluar directamente el dominio cuya entrada incluye el hecho modificado. *Ejemplo:* mover un muro cambia la superficie de la pieza — efecto inmediato en el Dominio 3.

**Indirectas** — segundo salto en adelante. Requieren que el efecto inmediato ya se haya calculado, porque lo que se propaga no es el hecho original sino la *conclusión* del dominio anterior. *Ejemplo:* el muro movido reduce el ancho del pasillo (efecto inmediato en Dominio 3) → ese pasillo más estrecho incumple ahora el itinerario accesible (efecto indirecto en Dominio 5, que depende del resultado geométrico del Dominio 3, no del muro en sí).

**Acumulativas** — no aparecen por ningún cambio individual, solo quando varios cambios, cada uno inocuo por separado, cruzan un umbral juntos. Requieren memoria de la sesión completa de edición, no solo del último cambio. *Ejemplo:* reducir ligeramente cinco habitaciones distintas, una a una, puede no disparar ningún aviso individual (cada una sigue por encima del mínimo), pero la suma de esas reducciones cambia la eficiencia útil/construida global de la vivienda o el cómputo de ocupación total a efectos de evacuación del edificio — un efecto que solo es visible mirando el conjunto de cambios, no cada uno aislado.

La distinción no es cosmética: un sistema que solo detecta efectos inmediatos parece funcionar bien en la demo y falla en el uso real, porque el uso real de un arquitecto es casi siempre una secuencia de pequeños ajustes, no un cambio único — y es exactamente en esa secuencia donde vive el efecto acumulativo.

---

## 5. Conflictos habituales entre dominios

Los conflictos no son errores del modelo — son la señal de que dos exigencias legítimas compiten por la misma decisión de diseño. Los patrones más recurrentes, ya identificados de forma dispersa en `ARCHITECTURAL_KNOWLEDGE_MAP.md` y aquí consolidados como pares de tensión estructural:

- **Accesibilidad vs. Superficie útil** (Dominio 5 vs. 3) — ensanchar un paso reduce superficie de piezas adyacentes.
- **Iluminación vs. Térmica** (Dominio 4 vs. 8) — más hueco mejora luz y empeora comportamiento térmico.
- **Evacuación vs. Calidad espacial** (Dominio 6 vs. 9) — sectorizar y compartimentar rompe relaciones espaciales abiertas.
- **Acústica vs. Instalaciones** (Dominio 7 vs. 10) — los patinillos compartidos son puntos de fuga acústica.
- **Urbanístico vs. Habitabilidad** (Dominio 1 vs. 3/4) — la ocupación máxima aprovechada deja menos margen para patios y huecos suficientes.
- **Estructura vs. Calidad espacial** (Dominio 11 vs. 9) — una malla estructural coherente impone restricciones a la libertad espacial deseada.
- **Acústica vs. Térmica** (Dominio 7 vs. 8) — reforzar aislamiento acústico y térmico a la vez tensiona el grosor y composición admisible de una misma partición.

Estos siete pares cubren la gran mayoría de los conflictos reales observables en proyectos residenciales — no son exhaustivos, pero son los que un arquitecto sénior reconoce casi de memoria.

---

## 6. Sistema de dependencias entre dominios

No todas las dependencias son del mismo tipo, y confundirlas es una fuente habitual de propagación mal diseñada. Se distinguen tres clases:

**Dependencia estructural (siempre activa)** — un dominio necesita el resultado de otro para funcionar en cualquier caso. Ejemplo: el Dominio 5 (Accesibilidad) siempre depende del Dominio 2 (Tipología) para saber qué exigencia aplica.

**Dependencia condicional (activa solo bajo ciertas condiciones)** — un dominio depende de otro únicamente cuando se dan ciertas circunstancias del proyecto. Ejemplo: el Dominio 11 (Estructura) solo depende de la geometría de otras plantas si el proyecto tiene más de una planta; en un proyecto de una sola planta, esa dependencia simplemente no existe.

**Dependencia de referencia (consume conclusión, no hecho crudo)** — un dominio no necesita el dato original, solo la conclusión ya elaborada de otro dominio. Ejemplo: el Dominio 9 (Calidad Espacial) no necesita la geometría bruta de huecos para valorar luz — le basta el resultado ya calculado del Dominio 4.

Esta última distinción es la que sostiene la regla más importante de todo el sistema (heredada de `BRAIN_ARCHITECTURE.md`, Parte 4, principio 3): **el Dominio 12 solo tiene dependencias de referencia, nunca estructurales ni de hecho crudo, respecto a los demás dominios.** Es lo único que impide que el meta-dominio termine duplicando el conocimiento interno de los otros trece.

---

## 7. Grafo conceptual de propagación

```
                         CAMBIO INTRODUCIDO
                     (uno de los 8 tipos, sección 1)
                                │
                                ▼
                 ┌─────────────────────────────┐
                 │   HECHO ALTERADO (Capa 1)    │
                 └─────────────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
     EFECTO INMEDIATO   EFECTO INMEDIATO   EFECTO INMEDIATO
      (Dominio X)         (Dominio Y)         (Dominio Z)
              │                 │                 │
     ¿su resultado es entrada de otro dominio?
              │                 │                 │
              ▼                 ▼                 ▼
     EFECTO INDIRECTO    EFECTO INDIRECTO   (sin más dependientes:
      (Dominio X')         (Dominio Y')       la rama se cierra aquí)
              │                 │
              ▼                 ▼
         ... continúa hasta que ningún dominio cambia su conclusión ...
              │
              ▼
                    ┌───────────────────────────────┐
                    │  PUNTO FIJO DE LA PROPAGACIÓN  │
                    └───────────────────────────────┘
                                │
                                ▼
                 ┌─────────────────────────────┐
                 │   DOMINIO 12 (meta-dominio)   │
                 │  lee TODAS las conclusiones   │
                 │  finales, detecta conflictos, │
                 │  agrupa síntomas relacionados │
                 └─────────────────────────────┘
                                │
                                ▼
                    Efecto en cadena documentado
                    (con nivel de impacto, sección 9,
                     y justificación trazable, sección 10)

   ··· en paralelo, a lo largo de TODA la sesión de edición ···
   ┌──────────────────────────────────────────────────────┐
   │  REGISTRO ACUMULADO DE CAMBIOS DE LA SESIÓN            │
   │  → alimenta la detección de EFECTOS ACUMULATIVOS       │
   │    (umbral cruzado por la suma, no por un cambio solo) │
   └──────────────────────────────────────────────────────┘
```

Cada rama del árbol de propagación avanza estrictamente en el sentido de las capas de `BRAIN_ARCHITECTURE.md` (0→1→2→3→4→5). Ninguna rama vuelve nunca hacia atrás — ese es, precisamente, el mecanismo que evita los ciclos (sección 8).

---

## 8. Cómo evitar que la propagación produzca ciclos infinitos

Hay dos tipos de ciclo distintos, y cada uno se evita con un mecanismo diferente.

**Ciclo estructural en el grafo de dependencias** — ocurriría si el Dominio A dependiera del Dominio B y B dependiera, a su vez, de A. Esto se evita **por diseño, no por detección en tiempo de evaluación**: el grafo de dependencias entre los 14 dominios es, por construcción, un grafo acíclico dirigido (DAG) organizado en capas estrictas (`BRAIN_ARCHITECTURE.md`, Parte 3) — las flechas solo bajan de capa, nunca suben, con la única excepción del Dominio 12, que lee de todos pero al que ningún dominio normativo lee de vuelta. Si en algún momento se detecta que un dominio nuevo "necesita" leer al Dominio 12 para funcionar, eso no es un ciclo a resolver técnicamente — es una señal de que ese conocimiento está mal clasificado y debería vivir en una capa inferior, no en el meta-dominio.

**Ciclo de razonamiento en la resolución de conflictos** — este es más sutil y no aparece en el grafo, aparece en la práctica: resolver el problema A moviendo un elemento genera el problema B; la solución "obvia" para B es deshacer parcialmente el cambio que resolvió A — un ping-pong de soluciones que, sin control, no converge nunca. Esto se evita con dos mecanismos:

1. **Registro de estados visitados** — cada propuesta de resolución se compara contra el historial de estados ya explorados en la misma sesión de razonamiento; si una solución propuesta reproduce (total o parcialmente) un estado ya descartado, se detecta como ciclo y se detiene, presentándose al arquitecto como un conflicto genuino sin solución automática de compromiso, no como algo que seguir intentando resolver solo.
2. **El Dominio 12 no auto-resuelve, expone** — coherente con que gran parte de este dominio es Nivel 4 (criterio arquitectónico, ver `ARCHITECTURAL_KNOWLEDGE_MAP.md`), su función no es encontrar automáticamente la solución que rompe el ciclo, sino **detectar el ciclo y explicarlo como un conflicto de fondo real** entre dos criterios legítimos, dejando la decisión final al arquitecto. Un sistema que intenta resolver automáticamente un ciclo de este tipo no está siendo más inteligente — está ocultando que ha llegado al límite de lo que puede decidir por sí mismo.

Adicionalmente, como salvaguarda de diseño (no de contenido de conocimiento sino de robustez del razonamiento), toda cadena de propagación debe tener un **límite máximo de saltos razonable** — si una cadena de efectos indirectos supera un número de saltos inusualmente alto sin alcanzar un punto fijo, es más probable que exista un error de clasificación de dependencias que un efecto en cadena genuinamente tan largo, y debe tratarse como una señal a revisar, no como un resultado a mostrar tal cual.

---

## 9. Niveles de impacto

Un mismo efecto en cadena no tiene el mismo peso si se queda contenido en una pieza que si termina afectando a la relación con la parcela vecina. Se definen seis niveles, de menor a mayor alcance:

- **Local** — el efecto se queda dentro de la pieza directamente modificada. *Ejemplo:* mover un tabique cambia la proporción de la propia habitación.
- **Planta** — el efecto afecta a la relación entre varias piezas de la misma planta. *Ejemplo:* el mismo tabique estrecha el pasillo que sirve a otras piezas de esa planta.
- **Vivienda** — el efecto afecta a la unidad completa como conjunto (superficie útil total, programa, puntuación global de la vivienda). *Ejemplo:* la reducción acumulada de varias piezas cambia la eficiencia útil/construida de toda la vivienda.
- **Edificio** — el efecto afecta a relaciones entre plantas distintas o entre unidades distintas (estructura vertical, instalaciones compartidas, acústica entre viviendas, evacuación conjunta). *Ejemplo:* mover la escalera principal afecta a la continuidad estructural de todas las plantas.
- **Parcela** — el efecto afecta a la relación del edificio con el solar en su conjunto (ocupación, patios compartidos, retranqueos). *Ejemplo:* ampliar la huella construida reduce el margen de patio disponible dentro de la misma parcela.
- **Urbanístico** — el efecto afecta al cumplimiento de parámetros del planeamiento o a la relación con el entorno/vecinos. *Ejemplo:* aumentar la altura de una planta supera la altura máxima permitida, o reduce un retranqueo por debajo del mínimo generando una posible servidumbre de luces con la parcela colindante.

El nivel de impacto no es solo informativo — determina, en gran medida, la severidad y la urgencia con la que un arquitecto experto trata el hallazgo: un efecto Local se puede corregir sin replantear nada; un efecto Urbanístico casi siempre exige reconsiderar la decisión de origen, no solo parchear su consecuencia.

---

## 10. Cómo debe ArchMuse justificar cada efecto en cadena para generar confianza

Un arquitecto no va a confiar en una afirmación como "este cambio genera 3 problemas nuevos" si no puede ver el razonamiento completo detrás. La justificación de cada efecto en cadena debe cumplir, sin excepción, estos principios:

1. **Mostrar la cadena de causalidad completa, no solo el resultado final.** Cada efecto en cadena se presenta como una secuencia explícita de pasos (cambio → hecho alterado → dominio X → dominio Y → conclusión), nunca como una conclusión aislada sin recorrido visible.
2. **Citar, en cada salto, qué dominio y qué criterio concreto se activó**, con referencia trazable a la norma o heurística correspondiente (mismo principio de trazabilidad exigido en `BRAIN_ARCHITECTURE.md`, Parte 4, para reglas individuales — aquí se extiende a cadenas completas).
3. **Distinguir explícitamente qué parte de la cadena es Nivel 1-2 (hecho/norma verificable) y qué parte es Nivel 3-4 (heurística/criterio)**, tal como se clasifica cada dominio en `ARCHITECTURAL_KNOWLEDGE_MAP.md`. Una cadena que empieza en un hecho objetivo y termina en un juicio de calidad espacial debe dejarlo claro tramo a tramo — la confianza de la cadena entera es, como mínimo, la del eslabón más débil, y ese eslabón debe ser visible, no promediado y ocultado.
4. **Mostrar el camino alternativo no tomado cuando exista**, especialmente en conflictos de la sección 5 — si hay más de una forma razonable de resolver la tensión, exponer el trade-off explícitamente en vez de sugerir una única solución como si fuera la única posible.
5. **Permitir que el arquitecto descarte un efecto en cadena con justificación**, y conservar ese descarte como conocimiento — un "esto no aplica en mi caso porque..." registrado es, con el tiempo, la materia prima real del propio Dominio 12 (y, indirectamente, del Dominio 13, Riesgo de Visado): un catálogo de conflictos reales resueltos por profesionales, no solo generados por el sistema.
6. **Nunca fusionar una cadena en una única conclusión sin desglose.** Igual que el veredicto global del proyecto se mantiene en capas separadas (`BRAIN_ARCHITECTURE.md`, Parte 1.8), cada efecto en cadena individual también debe mantener visibles sus pasos hasta el final — colapsar la cadena en "esto está mal" sin mostrar el recorrido es exactamente el tipo de opacidad que hace que un arquitecto experto desconfíe de una herramienta, por buena que sea su conclusión final.

La confianza en este dominio no se gana con más reglas — se gana con que cada afirmación sea, en todo momento, más fácil de verificar manualmente que de creer a ciegas.

---

## Los 20 efectos en cadena más frecuentes en proyectos residenciales

1. Ensanchar un pasillo para cumplir el itinerario accesible reduce la superficie de la habitación adyacente por debajo del mínimo habitable.
2. Ampliar una ventana para mejorar la iluminación natural incrementa la superficie acristalada y empeora la demanda energética de calefacción/refrigeración.
3. Desplazar un tabique para ganar superficie en un dormitorio estrecha el pasillo de evacuación por debajo del ancho mínimo exigido.
4. Eliminar el muro entre salón y cocina para abrir el espacio elimina también la compartimentación acústica frente a la vivienda o zona colindante.
5. Reubicar un baño en una planta rompe el apilamiento vertical de bajantes con la planta inferior, complicando el recorrido de instalaciones.
6. Ampliar la superficie privativa de una vivienda a costa del rellano común reduce el ancho de escalera/rellano por debajo del mínimo de evacuación y accesibilidad comunes.
7. Cambiar el uso declarado de una pieza de trastero a dormitorio activa de golpe exigencias de superficie mínima, iluminación, ventilación y evacuación que antes no aplicaban a esa pieza.
8. Dividir una vivienda en dos unidades independientes obliga a que cada una cumpla programa mínimo, accesibilidad y evacuación por separado, y crea una adyacencia acústica nueva entre ambas donde antes había una sola unidad.
9. Fusionar dos viviendas en una reduce el número de unidades del edificio, lo que puede cambiar el umbral normativo de exigencia de ascensor o accesibilidad aplicable al conjunto.
10. Mover la escalera principal de posición afecta simultáneamente a la superficie disponible en todas las plantas, a la continuidad estructural vertical y al recorrido de evacuación de cada nivel.
11. Aumentar la altura libre de una planta incrementa la altura total del edificio y puede superar la altura máxima permitida por el planeamiento urbanístico.
12. Reducir el retranqueo a lindero para ganar superficie construida puede vulnerar el mínimo urbanístico exigido o generar servidumbre de luces/vistas con la parcela colindante.
13. Ampliar un patio de luces para mejorar la iluminación de las piezas que vierten a él reduce la superficie útil total edificable dentro de la misma ocupación permitida.
14. Cerrar una zona de circulación abierta para cumplir sectorización contra incendio rompe la relación visual/espacial que sostenía la calidad percibida de una vivienda de planta abierta.
15. Reforzar el aislamiento acústico de una partición (más masa constructiva) reduce ligeramente la superficie útil de ambas piezas colindantes por el mayor grosor del muro resultante.
16. Añadir una nueva ventana en una fachada con orientación desfavorable mejora la iluminación de una pieza pero introduce riesgo de sobrecalentamiento, o de pérdida de aislamiento acústico si esa fachada da a una zona ruidosa.
17. Cambiar la posición de la cocina en planta altera el recorrido de fontanería/saneamiento y puede alejarla del baño más cercano, encareciendo o complicando la instalación conjunta.
18. Reducir el número de plantas del edificio cambia el cómputo de ocupación total y la altura de evacuación, lo que puede modificar las exigencias de protección contra incendio que antes aplicaban.
19. Incorporar una rampa para resolver un desnivel de acceso consume una longitud de recorrido considerable, lo que puede alargar el itinerario de evacuación medido desde las piezas más alejadas.
20. Ampliar el número de dormitorios de una vivienda sin ampliar su superficie total reduce la superficie media por dormitorio y tensiona el cumplimiento de superficie mínima individual en varias piezas a la vez, no solo en la ampliada.

Estos veinte no son una lista cerrada de reglas a implementar — son la evidencia empírica de que el patrón dominante en un proyecto residencial real no es "una regla se incumple", es **"resolver algo aquí mueve el problema allí"**. Es precisamente ese patrón el que un checklist plano de 500 reglas independientes nunca puede capturar por sí solo, y es la razón última por la que este dominio, bien construido, vale más que cualquier otro de los catorce.
