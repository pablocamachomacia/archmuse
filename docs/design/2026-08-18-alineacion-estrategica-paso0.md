# Alineación estratégica — el norte único de ArchMuse

**Fecha:** 2026-08-18 · **Estado:** DECISIÓN, vinculante · **Cierra:** paso 0 de la secuencia de `docs/design/2026-08-18-cerebro-arquitecto-adr.md` §F

**Qué resuelve este documento.** El ADR del "Cerebro Arquitecto" identificó en su §E.1 un conflicto directo entre la reorientación propuesta y `NORTH_STAR_2031.md`, y dejó la resolución explícitamente fuera de su alcance: *"una de las dos está obsoleta y hay que decir cuál, por escrito"*. Esto es ese escrito. Mientras no existiera, cada decisión de arquitectura tenía dos criterios de aceptación incompatibles y el trabajo se hacía dos veces.

---

## 1. El conflicto, enunciado sin suavizar

Tres documentos aprobados responden lo contrario a la misma pregunta: **¿dónde vive ArchMuse?**

| Documento | Qué dice |
|---|---|
| `NORTH_STAR_2031.md`, horizonte 24 meses | *"dejar de ser 'una herramienta a la que se sube un archivo' y convertirse en una capa nativa de cumplimiento en tiempo real dentro del flujo BIM"* |
| `DESTROY_ARCHMUSE.md` §1a | *"ArchMuse obliga a exportar a DXF, subir el archivo, esperar y leer un informe aparte… no es una mejora de UX, es un cambio de categoría"* |
| La visión del Cerebro Arquitecto | *"el usuario exprese una intención… o adjunte archivos de trabajo… y reciba trabajo profesional terminado"* |

Adjuntar un archivo y esperar es exactamente el flujo que los dos primeros identifican como la debilidad estructural número uno. La visión del cerebro lo mantiene y lo hace **más lento**, porque una orquestación agéntica tarda más que una petición directa.

Hay un segundo conflicto, del mismo tipo y no menos caro: la visión dice *"el usuario no ve la complejidad"*, mientras `MOAT_ANALYSIS.md` Pilar 2 sitúa la transparencia — *"te decimos exactamente qué hemos comprobado y qué no"* — como el argumento comercial principal y el más difícil de replicar.

---

## 2. La decisión

**Se adopta la salida 2 del ADR §E.1: el cerebro es el motor; BIM es la superficie.**

En una frase: **ArchMuse construye ahora el cerebro, y lo construye desde el primer día para poder invocarse desde dentro del entorno de diseño del arquitecto, no solo desde una web a la que se sube un fichero.**

Las dos visiones dejan de competir porque dejan de responder a la misma pregunta:

| Pregunta | Documento que manda | Respuesta |
|---|---|---|
| **Qué** razona ArchMuse y con qué garantías | El ADR del Cerebro Arquitecto | Un núcleo determinista de reglas y geometría, con procedencia epistémica tipada, orquestado por una capa agéntica que planifica pero no calcula |
| **Dónde** se le pide y dónde se entrega | `NORTH_STAR_2031.md` | Dentro del flujo del arquitecto: hoy web, a 6-24 meses nativo en BIM |
| **Cómo** se gana la confianza que sostiene ambas | `MOAT_ANALYSIS.md` Pilar 2 | Diciendo qué se ha comprobado, con qué dato y qué ha quedado sin comprobar |

Ninguno de los tres queda obsoleto. Lo que queda derogado es la lectura de la visión del cerebro que la convierte en un producto de "sube un fichero y espera": esa lectura **no se implementa**.

### Por qué esta salida y no las otras dos

- **Salida 1 (el cerebro sustituye al North Star).** Rechazada. Obligaría a reescribir `NORTH_STAR_2031.md`, cuyos horizontes de 3, 6, 12 y 24 meses son el único plan del proyecto trabajado hacia atrás desde un objetivo concreto y con criterios de etapa verificables. Cambiarlo por una visión sin horizontes ni criterios es cambiar un plan por una aspiración.
- **Salida 3 (aparcar el cerebro).** Rechazada. Desaprovecha `docs/brain/` (22 documentos ya escritos), `modelo/` (2.194 líneas de procedencia epistémica ya construidas) y `normativa/` (4.752 líneas de motor territorial completo). Es donde está el diferencial no replicable, y aparcarlo deja a ArchMuse compitiendo por UX contra fabricantes de BIM que tienen la distribución.
- **Salida 2.** Es la única que no tira trabajo, y la única compatible con el hecho medido de que hoy no existe importación de IFC ni ingesta de imágenes: el cerebro puede empezar a construirse sobre el DXF que ya se lee, mientras la superficie BIM se valida en paralelo con la prueba de concepto que `NORTH_STAR_2031.md` ya sitúa en el horizonte de 3 meses.

---

## 3. Consecuencias vinculantes

Estas cinco no son recomendaciones. Son criterios de aceptación: un PRD que las incumpla se rechaza en revisión.

**C1 — Ninguna capacidad se diseña acoplada a la web.** Toda capacidad del cerebro se registra con un manifiesto (ADR §B.3), recibe datos del grafo de proyecto y devuelve datos al grafo. Un endpoint de Flask es *un* invocador, nunca el dueño de la lógica. El criterio de verificación es mecánico: si mover una capacidad a un plugin de Revit exigiera reescribirla, está mal construida.

**C2 — Lo invisible es el esfuerzo, nunca el razonamiento.** Se deroga *"el usuario no ve la complejidad"* y se sustituye por **"el trabajo hecho, con el porqué a un clic"**. El arquitecto no ve las 200 llamadas, pero sí ve, en una página, qué se comprobó, con qué dato, de dónde salió ese dato y qué quedó sin comprobar. Esto convierte el acta de procedencia (ADR §E.5.1) en un entregable de producto, no en un anexo opcional.

**C3 — Todo entregable sale marcado como borrador para revisión de un colegiado.** ArchMuse asesora; no firma. Cuanto más terminado es el artefacto que produce, más cerca está de la autoría y más difícil es sostener la frontera que `NORTH_STAR_2031.md` §5 declara innegociable. La marca de borrador y el acta de procedencia adjunta viajan con cada artefacto generado, sin excepción y sin opción de desactivarlas.

**C4 — Cobertura antes que catálogo.** Se deroga el objetivo de "cientos de capacidades". El MVP se construye con entre 8 y 12, elegidas por fiabilidad auditable. Añadir capacidades mientras el corpus normativo siga vacío amplifica el riesgo de alucinación normativa, no el valor.

**C5 — El corpus normativo entra en el camino crítico desde hoy.** Su motor está construido y esperando contenido; el cuello de botella es contractual — un arquitecto colegiado transcribiendo —, no técnico. Ninguna decisión de arquitectura lo desbloquea, y es probablemente la contratación más rentable del proyecto. Se gestiona en paralelo a todo lo demás, no después.

---

## 4. Encaje con `ROADMAP_VISION_ARQUITECTONICA.md`

`CLAUDE.md` nombra ese documento brújula oficial (aprobado el 2026-08-16) para 3D/entorno, asesor urbanístico, sostenibilidad y navegación. **No entra en conflicto con esta decisión y se mantiene íntegro.** Su §6 ordena una secuencia de trabajo de producto sobre superficies ya existentes; esta decisión ordena dónde vive el motor. Son ejes distintos.

Sí queda acotado un punto: los pasos de su §6 que amplían el visor 3D compiten por el mismo tiempo de desarrollo que el cerebro. Cuando compitan, manda el paso 1 de su propia §6 — conectar el visor a los hallazgos del motor de reglas —, porque es el único que aumenta el valor del motor en vez de aumentar la superficie que hay que mantener.

---

## 5. Qué NO cambia

Para que esta decisión no se lea como más ambiciosa de lo que es:

- **No cambia la Fase 2 del `REFACTOR_MASTERPLAN.md`.** El paso 1 de la secuencia del ADR sigue siendo cerrar el golden de tipología y zona climática. Un motor sin red de seguridad no se puede mover a ninguna superficie.
- **No autoriza a escribir código de capacidades agénticas.** Cada capacidad nueva sigue necesitando su PRD aprobado, por la regla de proceso de `CLAUDE.md`. Esta decisión fija el criterio con el que se evaluarán esos PRD; no los sustituye.
- **No promete IFC ni ingesta de imágenes.** Hoy son cero líneas. Siguen siendo cero hasta que tengan su propio PRD, y la ingesta de imágenes sigue siendo lo que el ADR §F desaconseja explícitamente: máximo riesgo, mínimo valor demostrado.

---

## 6. Cómo se verifica que esta decisión se está cumpliendo

Tres comprobaciones baratas, aplicables en cualquier revisión:

1. **Prueba del plugin.** Coger una capacidad cualquiera y preguntar: ¿qué habría que reescribir para invocarla desde Revit? Si la respuesta no es "solo el invocador", C1 se ha incumplido.
2. **Prueba del acta.** Coger un artefacto generado y preguntar: ¿puedo decir, celda a celda, de qué entidad de qué fichero salió cada número? Si no, C2 se ha incumplido.
3. **Prueba del catálogo.** Contar las capacidades registradas frente a las auditadas. Si la primera cifra crece más rápido que la segunda, C4 se ha incumplido.

---

**Decisión pendiente de la firma de Pablo.** Hasta entonces esto es una propuesta de resolución, no la resolución. Una vez aprobado, `NORTH_STAR_2031.md`, `MOAT_ANALYSIS.md`, `ROADMAP_VISION_ARQUITECTONICA.md` y el ADR del Cerebro Arquitecto pasan a leerse juntos bajo el reparto de la §2, y deja de haber dos nortes.
