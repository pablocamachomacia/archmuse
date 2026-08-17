# PRD — Entrevistador arquitectónico inteligente (sustituto de "Generar proyecto")

**Estado:** Implementado (Fases A-G + extensión mínima del generador) · **Fecha:** 2026-08-12 · **Revisión:** v2, tras auditoría crítica · **Autor:** ArchMuse (CTO)
**Aprobado por:** Pablo — implementación dirigida y cerrada en sesión (2026-08-12/2026-08-13)

**Cierre (2026-08-13):** Implementado el modelo de información completo (Parte I), el motor de entrevista
determinista + Claude (§21, `analyzer/interview/motor.py`), el compilador Especificación→params (§17/§22,
`analyzer/interview/compilador.py`), el modo experto convergente (§29, `static/entrevista.js`), y la
**extensión mínima del generador (§30) — aprobada y construida**, no solo analizada: las 5 categorías de
decisión B (accesibilidad, no-negociables, privacidad, cocina abierta/cerrada, referencias estéticas)
producen `DirectivaCualitativa` reales que llegan a `ai_generator.py` (`_validar_directivas`,
`verificar_directivas_duras`), verificadas con datos reales end-to-end (justificación de Claude citando las
directivas, verificación determinista de accesibilidad contra la geometría generada, `TrazaDeGeneracion`
persistida). Dos correcciones adicionales, no previstas como huecos en la v2 pero descubiertas por auditoría
posterior al cierre inicial: (1) `compilar_params()` no incluía `contexto_cualitativo` en su salida —
corregido, es lo que conecta de verdad la entrevista con la extensión mínima; (2) el "puente" de datos
técnicos y el botón "Editar en modo experto" creaban una sesión `edicion_experta` nueva en vez de reutilizar
la sesión real, aplanando a `Hecho` toda `Hipótesis`/`Inferencia` ya recogida — corregido reutilizando la
sesión existente (`anadir_valores_expertos()`, endpoint `POST /api/entrevista/<id>/valores_expertos`), que es
exactamente el mecanismo que §29.4 y la nota de §13/§11 de esta parte II ya preveían ("un usuario puede
cambiar de un modo a otro a mitad de camino sin perder lo ya introducido, porque ambos escriben sobre la
misma Especificación") pero que la primera implementación no cumplía todavía.

**Huecos conocidos, deliberadamente sin cerrar en esta etapa** (decisión explícita de alcance, no descuido):
ninguna de las 15 preguntas del catálogo pregunta `edificio.plantas` (solo el máximo normativo,
`restricciones.plantas_maximas`, un dato distinto) — la entrevista guiada sola nunca compila sin pasar por el
puente; y los tests de esta iniciativa (`tests/test_interview_*.py`, `tests/test_ai_generator_contexto.py`)
siguen siendo scripts standalone (`python tests/test_X.py`), no funciones `pytest` — ambos, fuera de alcance
de esta sesión de cierre.

**Historial:** v1 (2026-08-12) se auditó críticamente el mismo día. La auditoría encontró 5 problemas
críticos: el documento no era autocontenido (dependía de una conversación de chat como fuente normativa), la
mayoría de las preguntas de la entrevista no tenían ningún campo de destino en el generador actual, el esquema
de la "Especificación Arquitectónica" nunca se definió, dos preguntas prometían capacidades que no existen en
el código, y el presupuesto de llamadas a Claude no estaba realmente minimizado. Esta v2 corrige los cinco.
Nada de lo corregido es cosmético: cambia el esquema de datos (§7), el contrato con el generador (§12), el
contenido de 2 de las 15 preguntas (§3, §6.4), y el presupuesto de API (§21).

**Esta etapa sigue siendo solo diseño.** No se ha escrito ni modificado ninguna línea de código, ni de
`app.py`, ni de `analyzer/*`, ni de `static/*`. No se ha hecho commit.

**Referencias obligatorias:** `BRAIN_ARCHITECTURE.md`, `ARCHITECTURAL_KNOWLEDGE_MAP.md`, `DECISION_ENGINE.md`,
`REASONING_ENGINE_SPEC.md`, `docs/brain/FACT_MODEL.md`, `docs/design/TRACEABILITY.md`,
`docs/design/2026-08-11-modelo-arquitectonico-comun.md`, `docs/prd/PRD-001-Core-Reasoning-Engine.md`,
`REFACTOR_MASTERPLAN.md`, `TECH_REVIEW.md`, `MOAT_ANALYSIS.md`, `NORTH_STAR_2031.md`.

**Grounding de esta revisión:** releído contra el código real `app.py:550-768`, `analyzer/ai_generator.py`
completo (`SYSTEM_PROMPT`, `_build_user_message`, `place_rooms`), y confirmado, línea por línea, que no existe
en el repositorio ningún módulo de normativa urbanística municipal (PGOU) — el hallazgo que obliga a
reformular la pregunta de plantas máximas en §6.4.

**Índice.** Parte I (§1-§6) es el modelo de información, incorporado íntegro — ya no depende de ninguna
conversación externa. Parte II (§7-§20) es el PRD según las 14 secciones mínimas de `CLAUDE.md`. Parte III
(§21-§30) es el diseño interno del entrevistador. Parte IV (§31-§33) cierra con la autoauditoría, las
decisiones abiertas y la decisión final.

---

# PARTE I — Modelo de información (Etapa 0.2, incorporado íntegro)

Todo lo que sigue en esta parte sustituye por completo a "la conversación de la Etapa 0.2" como fuente. Si
algo de este documento remite a "una categoría" o "una pregunta", remite a esta parte, no a un chat.

## 1. Las 15 categorías

Trece originales más dos que la auditoría encontró ausentes (§9 de la propia auditoría): **Relaciones
espaciales y circulación** y **Estructura y sistema constructivo**.

| # | Categoría | Qué cubre |
|---|---|---|
| 1 | Contexto y ubicación | Ciudad, comunidad autónoma, tipo de entorno, dirección si existe |
| 2 | Parcela | Superficie, forma, topografía, linderos |
| 3 | Programa de necesidades | Uso, tipología, nº de viviendas, mix, programa por vivienda |
| 4 | Usuarios y forma de vida | Para quién, accesibilidad, rutinas |
| 5 | Prioridades y trade-offs | Qué pesa más en un conflicto, no-negociables |
| 6 | Restricciones normativas y de proceso | Ocupación/edificabilidad/altura/retranqueos, plazos, presupuesto |
| 7 | Entorno y privacidad | Vecinos, vistas, necesidad de privacidad |
| 8 | Orientación y clima | Orientación real de la parcela, preferencias solares, zona climática (inferida) |
| 9 | Espacios exteriores | Terraza, jardín, zona comunitaria |
| 10 | Movilidad y accesos | Aparcamiento, acceso principal, ascensor |
| 11 | Sostenibilidad y eficiencia | Nivel de exigencia energética, sistemas deseados |
| 12 | Identidad arquitectónica | Referencias visuales, materiales, sensación buscada |
| 13 | Presupuesto | Cifra u horquilla, prioridad coste vs. calidad |
| **14** | **Relaciones espaciales y circulación** *(nueva)* | Separación público/privado, cocina abierta/cerrada, transición de entrada |
| **15** | **Estructura y sistema constructivo** *(nueva)* | Ver §5 — decisión de alcance, no un cuestionario nuevo |

## 2. Los 8 datos imprescindibles

Bloquean la generación si faltan — deben terminar en estado *Hecho* o *Hipótesis explícita*, nunca
`pendiente`, para poder generar (§28).

1. Ciudad/municipio.
2. Uso del edificio y tipología.
3. Superficie del solar.
4. Forma/dimensiones del solar (o "irregular, decídelo tú" como respuesta válida).
5. Nº de viviendas deseado y mix aproximado de tamaños.
6. Prioridad principal ante conflicto (superficie vs. luz vs. coste vs. nº de viviendas).
7. Accesibilidad requerida, si aplica.
8. Orientación real de la parcela — en lenguaje natural o mapa, **nunca** en grados (ver §3, §6.3, corrige el
   error de diseño de v1).

No se añade un noveno imprescindible pese a la categoría 14 nueva — ver §5.1: la relación público/privado se
trata como recomendable, no imprescindible, precisamente para no repetir el error de sobre-preguntar.

## 3. Datos opcionales

Dirección/parcela exacta · topografía · vecinos y vistas · presupuesto (cifra u horquilla) · plazos · espacios
exteriores deseados · aparcamiento deseado · sostenibilidad (nivel, sistemas) · referencias estéticas /
materiales / sensación buscada · rutinas de los usuarios · privacidad frente a calle/vecinos · aspectos
"no negociables" (formalmente opcional pero de altísimo valor si aparece, ver §7 pregunta 4) · preferencia
solar interior (qué pieza recibe el sol — ver §6.3, degradada de imprescindible a opcional en esta revisión).

## 4. Información que ArchMuse debe inferir y nunca preguntar — corregido y verificado contra código

La v1 mezclaba en una sola lista cosas que el código ya deriva hoy con cosas que solo se derivarían si
existiera un motor que no existe. Esta revisión las separa, porque confundirlas es exactamente el error que
produjo la pregunta 7 rota de v1.

**Confirmado en código, usar sin dudar:**

| Dato | Se deriva de | Dónde |
|---|---|---|
| Zona climática CTE | Ciudad | `cte_zonas.get_zona_cte()` |
| Densidad urbana | Ciudad | `cte_zonas.get_densidad_urbana()` |
| Obligatoriedad de ascensor / altura de evacuación | Plantas + altura libre **ya preguntadas** | `altura_evacuacion.resolver_altura_evacuacion()` |

**NO confirmado en código — aspiracional, no prometer todavía (corrige el error de v1 §10):**

| Dato | Por qué no es "nunca preguntar" hoy |
|---|---|
| Ocupación máxima / edificabilidad máxima / retranqueos / plantas máximas por PGOU municipal | No existe ningún módulo de normativa urbanística municipal en el repositorio. `evaluate_solar_occupation`/`evaluate_buildability` **comparan** lo construido contra un umbral que el usuario declara — no lo derivan de la ciudad. Ver §6.4 para cómo se pregunta esto sin mentir. |
| Ratio mínimo de aparcamiento | No existe función que lo calcule desde el nº de viviendas |
| Rango razonable de nº de viviendas dado el solar | No existe función que lo sugiera — es aritmética simple (superficie × edificabilidad ÷ tamaño medio) pero **no está implementada**; no se presenta como "ArchMuse lo calcula" hasta que lo esté |

## 5. Relaciones espaciales y circulación — qué se pregunta y qué resuelve el motor

**Decisión de esta revisión:** una sola pregunta nueva, no una lista. La mayoría de las relaciones espaciales
(zona húmeda junto a dormitorio, salón en la mejor fachada, dormitorios accesibles desde circulación) **ya
están resueltas como reglas fijas dentro de `ai_generator.SYSTEM_PROMPT`** y son responsabilidad del Motor, no
del usuario — preguntarlas sería repetir el error de v1 de sobre-preguntar cosas ya resueltas.

**5.1 — Lo único que sí se pregunta:** cocina abierta o cerrada respecto al salón (pregunta 15 de §7) —
categoría recomendable, no imprescindible: es la única relación espacial donde la preferencia del usuario
cambia genuinamente el resultado (afecta a huecos, acústica y superficie percibida) y es fácil de responder sin
vocabulario técnico.

**5.2 — Todo lo demás pertenece al Motor, con esta salvedad:** si el usuario menciona una relación espacial en
su respuesta libre a la pregunta 1 ("quiero que los dormitorios queden lejos de la puerta principal") se
registra como no-negociable (§7 pregunta 4) y viaja como texto — no se traduce a una regla geométrica nueva en
esta etapa, ver §13 sobre la extensión mínima del generador.

## 6. Las 15 preguntas iniciales — versión corregida

Formato: número · tipo (Abierta/Opción/Condicional) · categoría · texto literal · qué corrige esta revisión
respecto a v1.

1. **(A)** Programa · *"Describe con tus palabras el proyecto que tienes en la cabeza — y si quieres, en una
   frase, cómo te gustaría que se sintiera por dentro."* — Absorbe la antigua pregunta 15 ("una palabra para
   describir la sensación") en vez de hacerla un turno aparte: eran redundantes, se fusionan para ahorrar un
   turno y una llamada.
2. **(O)** Usuarios · *"¿Este proyecto es para vivir tú, para vender, para alquilar, o todavía no lo sabes?"*
3. **(C)** Parcela · *"¿Ya tienes la parcela, o todavía la estás buscando/imaginando?"*
4. **(A)** Prioridades · *"¿Qué es lo que NO puede faltar en este proyecto, pase lo que pase?"*
5. **(A)** Prioridades · *"¿Y qué es lo que menos te importa, aunque otros lo consideren importante?"*
6. **(O)** Programa · *"Si tuvieras que elegir: ¿viviendas más grandes y menos, o más pequeñas y más?"*
7. **(O)** Restricciones · *"¿Sabes cuántas plantas puedes construir en tu solar, o necesitas que te ayudemos a
   estimarlo?"* — **Reformulada (§6.4)**: ya no promete "lo comprobamos por ti" (v1 prometía una verificación
   normativa municipal inexistente); ahora ofrece ayudar a *estimar* y es honesta sobre el límite.
8. **(C, imprescindible)** Orientación · *"¿Hacia dónde da la fachada principal de tu parcela — norte, sur,
   este, oeste, o una combinación? Si tienes la dirección, dínosla y te ayudamos con un mapa."* —
   **Reemplaza por completo** a la pregunta de v1 ("¿por dónde te gustaría que entrara el sol...?"), que
   pedía una *preferencia* cuando `norte_grados` necesita un *hecho geométrico* (§6.3). La preferencia de qué
   pieza recibe el sol pasa a ser una pregunta opcional aparte (§6.3), nunca la misma.
9. **(A)** Presupuesto · *"¿Cuánto te gustaría gastar aproximadamente? Puede ser una horquilla."*
10. **(O)** Sostenibilidad · *"¿Qué pesa más para ti: ahorrar en la factura energética a largo plazo, o
    mantener bajo el coste de construcción ahora?"*
11. **(A)** Identidad · *"Cuéntanos 2 o 3 casas o edificios que te gusten — fotos, nombres, o una
    descripción."*
12. **(O)** Privacidad · *"¿Cuánta privacidad necesitas frente a la calle o los vecinos: mucha, la normal, o te
    da igual?"*
13. **(Sí/No)** Usuarios · *"¿Va a vivir, o podría vivir en el futuro, alguien con movilidad reducida?"*
14. **(O)** Exteriores · *"¿Prefieres que cada vivienda tenga su propio espacio exterior aunque sea a costa de
    metros interiores, o prefieres aprovechar cada metro cuadrado por dentro?"*
15. **(O, nueva)** Relaciones espaciales · *"¿Te gusta la cocina integrada con el salón (abierta), o prefieres
    que quede separada (cerrada)?"* — sustituye, en la lista de 15, a la antigua pregunta 15 fusionada en la 1.

### 6.3 — Orientación real vs. preferencia solar, ahora dos cosas distintas

| | Orientación real de la parcela | Preferencia solar interior |
|---|---|---|
| Qué es | Un hecho geométrico del solar | Una preferencia de diseño interior |
| Pregunta | #8, imprescindible | Opcional, solo si el usuario la menciona espontáneamente o en modo experto |
| Alimenta | `norte_grados` — un dato real que el generador necesita | Nada hoy — `SYSTEM_PROMPT` ya decide por defecto que el dormitorio principal y el salón miran a sur/sureste; una preferencia distinta del usuario no tiene dónde aplicarse sin tocar `ai_generator.py` (§13) |
| Error de v1 | — | v1 las trataba como la misma pregunta y ninguna de las dos quedaba bien resuelta |

### 6.4 — La pregunta de normativa municipal, honesta

Contrato explícito de la pregunta 7, para que ninguna futura implementación prometa de más:

- **Si en el futuro existe un motor de normativa municipal fiable** (no existe hoy — ver §4): la pregunta se
  reduce a confirmación ("hemos comprobado que en tu municipio el máximo son N plantas, ¿es correcto?").
- **Mientras no exista** (el caso de hoy, y el único que este PRD autoriza a construir): se pide el dato al
  usuario; si no lo sabe, se registra como `Hipótesis` con confianza Baja y motivo *"sin verificación normativa
  municipal disponible"*, nunca como si ArchMuse lo hubiera comprobado. El resumen (§27) debe mostrar este
  aviso de forma visible, no enterrado.

---

# PARTE II — El PRD (14 secciones mínimas de `CLAUDE.md`)

## 7. Problema que resuelve

El formulario actual (`renderGenerarForm`, `static/app.js:637-792`) pide 15 campos técnicos de golpe a una
persona que, según la Parte I, no sabe responder la mayoría directamente. Pero hay que ser precisos sobre qué
arregla esto y qué no — la v1 decía *"el problema no es la calidad del generador"*, y eso era una
simplificación que esta revisión corrige explícitamente en §11.

Cuatro capas distintas intervienen en llegar de una idea a un proyecto competitivo, y este PRD solo construye
la primera:

```
ENTREVISTADOR       → mejora la fidelidad de la intención capturada.        (este PRD)
GENERADOR           → convierte la intención en arquitectura.               (ai_generator.py, sin tocar)
EVALUADOR           → comprueba la arquitectura resultante.                 (evaluator.py, sin tocar)
MOTOR DE CALIDAD     → distingue una solución mediocre de una excelente.     (no existe todavía, en ningún PRD)
```

El problema que este PRD resuelve es real y acotado: hoy nadie verifica que lo que entra en el generador
refleje lo que el usuario quiere. No resuelve, ni pretende resolver, que el generador (`place_rooms`, una
zonificación rectangular simple) o el motor de calidad (inexistente) estén a la altura de un concurso — eso se
trata explícitamente en §11.

## 8. Usuario afectado

Principal: persona sin conocimientos de arquitectura. Secundario, y ya no una tensión sin resolver como en v1:
el arquitecto profesional, servido por el **modo experto** (§29) — edición directa de la misma Especificación
que produce la entrevista, no una segunda vía de generación.

## 9. Objetivo de negocio

Sin cambios respecto a v1: un entrevistador con trazabilidad es más defendible que un formulario clonable
(`MOAT_ANALYSIS.md`), y es un paso hacia `NORTH_STAR_2031.md`. Matiz añadido por la auditoría: este objetivo se
cumple solo si el trabajo de la entrevista tiene adónde ir (§12) — de lo contrario el negocio invierte en una
conversación mejor sin que el producto final cambie.

## 10. Objetivo técnico y alcance

Lo que debe ser cierto tras implementar esto (etapa posterior, no esta):

- `Generar proyecto` abre una conversación guiada (o el modo experto, §29) que termina en un resumen
  determinista, auditable y corregible.
- Esa conversación produce una **Especificación Arquitectónica** (§22, esquema propio, ya no un alias del
  `params` dict — corrige el error crítico de v1).
- Toda decisión relevante es trazable (§22.3).
- El coste de Claude por entrevista está acotado a 3-5 llamadas (§21).

**Lo que este PRD explícitamente NO afirma** (corrige la sobreventa implícita de v1, exigido por la
auditoría): que esto por sí solo acerque a ArchMuse a producir proyectos capaces de competir en un concurso
arquitectónico difícil. Esa capacidad depende del Generador y de un Motor de Calidad que no existen todavía
(§11). Este PRD entrega, honestamente, una mejora de fidelidad de entrada — necesaria, no suficiente.

## 11. Casos de uso

1. Particular sin conocimientos técnicos — caso central.
2. Promotor con cifras de negocio claras, sin vocabulario técnico.
3. **Arquitecto profesional en modo experto** (§29) — ya no una tensión sin resolver, es un caso de uso de
   primera clase de esta etapa.
4. Usuario que abandona y vuelve más tarde.
5. Usuario que corrige el resumen.
6. Usuario que empieza en modo experto y cambia a entrevista guiada a medias, o viceversa (§29.4).

## 12. Casos límite

Iguales que v1, más dos nuevos que la auditoría forzó a hacer explícitos:

- Dos respuestas contradictorias en momentos distintos.
- "No sé" / "decide tú" ante un dato imprescindible.
- Una respuesta libre contesta a más de un campo sin que se le pida.
- Petición geométricamente imposible dado lo declarado.
- El usuario quiere terminar antes de cerrar los imprescindibles.
- Corte de red/API a mitad de turno.
- **Nuevo:** el usuario alcanza el tope de turnos (§28) sin haber cerrado los imprescindibles — el sistema
  debe poder forzar el cierre con lo que tiene, marcando el resto como `Hipótesis`, nunca bloquear sin salida.
- **Nuevo:** edición en modo experto dejando la Especificación en un estado que la entrevista guiada nunca
  produciría (p. ej. un campo imprescindible vacío) — debe validarse con las mismas reglas, no con reglas más
  laxas por venir de un experto.

## 13. Flujo del usuario

```
Inicio → Nuevo proyecto → Generar proyecto
              │
              ├── (usuario elige) Entrevista guiada ───┐
              │                                          │
              └── (usuario elige) Modo experto ──────────┤
                                                          ▼
                                          Especificación Arquitectónica (§22)
                                          — un único esquema, dos caminos de entrada —
                                                          │
                                          Resumen de lo entendido (§27, determinista)
                                                          │
                                          Usuario confirma/corrige (§28)
                                                          │
                                          Contrato Especificación→params (§12 de esta parte / §17)
                                                          │
                                          Generador (ai_generator.py, SIN TOCAR)
                                                          │
                                          Evaluación (evaluator.py, SIN TOCAR)
                                                          │
                                          Proyecto generado → 2D/3D → Iteración humana
                                          (fuera de alcance — ver límite de trazabilidad en §22.3)
```

La diferencia con v1: modo experto ya no es un caso sin resolver colgando fuera del flujo — converge en el
mismo punto (Especificación) que la entrevista guiada, con el mismo resumen de confirmación obligatorio.

## 14. Criterios de aceptación

- Un usuario sin conocimientos completa la entrevista y entiende el resumen sin ayuda externa.
- Los 8 imprescindibles (§2) terminan en `Hecho` o `Hipótesis`, nunca `pendiente`.
- Cero preguntas sobre lo confirmado como inferible en código (§4, tabla superior) — y cero promesas sobre lo
  aspiracional (§4, tabla inferior) más allá de lo que dice §6.4.
- El generador recibe el `params` dict compilado desde la Especificación sin cambios en `ai_generator.py`
  (salvo que se apruebe la extensión mínima de §13, que es una decisión separada, no parte de esta etapa).
- Toda `Inferencia`/`Hipótesis` del resumen es trazable hasta la respuesta que la originó.
- Cada campo de la Especificación declara explícitamente su `destino_generador` (§22) — ningún dato
  recogido puede quedar en un limbo sin que el documento diga qué pasa con él.
- El nº de llamadas a Claude por entrevista respeta el presupuesto de §21 (3-5).
- El modo experto produce una Especificación validable con las mismas reglas que la entrevista guiada.

## 15. Riesgos

- **El riesgo que ya no aplica igual que en v1:** que el entrevistador recoja información sin destino de forma
  silenciosa — mitigado estructuralmente por el contrato de §12 y el campo `destino_generador` obligatorio en
  cada `CampoEspecificacion` (§22). Sigue existiendo el riesgo de que ese contrato se ignore en la
  implementación real; se mitiga con el criterio de aceptación correspondiente en §14.
- Coste de API impredecible si el presupuesto de §21 se trata como aspiración y no como límite duro con
  fallback determinista.
- Interpretación silenciosamente errónea de una respuesta libre — el resumen determinista (§27) reduce el
  riesgo de que el propio resumen introduzca una segunda capa de error (el LLM parafraseando mal lo que ya
  interpretó mal), pero no lo elimina en la interpretación original.
- Compite por tiempo de desarrollo con `REFACTOR_MASTERPLAN.md`/`PRD-001` — sin resolver, es de Pablo.
- Dependencia declarada con `PRD-001` — igual que en v1.
- **Nuevo:** la Especificación Arquitectónica ahora es un esquema más rico (§22) — más superficie para
  mantener, más riesgo de que la implementación se quede corta o se sobre-diseñe. Mitigación: §22 fija los
  campos mínimos, no es una invitación a añadir más sin justificación.
- **Nuevo:** el modo experto (§29) puede producir una Especificación con combinaciones que la entrevista
  guiada nunca generaría (p. ej. estructura declarada sin que el resto del proyecto la respalde) — mitigado
  por la validación compartida del criterio de aceptación de §14, pero es una superficie de casos límite nueva
  que antes no existía.

## 16. Plan de implementación en fases

Igual que v1 a nivel de fase, con dos fases nuevas:

- **Fase A** — Estado de entrevista + preguntas fijas iniciales, deterministas.
- **Fase B** — Integración de Claude con el presupuesto de §21 desde el primer commit.
- **Fase C** — Priorización de siguiente pregunta (§25).
- **Fase D** — Contradicciones y ambigüedad (§26).
- **Fase E** — Compilador Especificación → `params` (§12/§17), con `especificacion_id` y trazabilidad.
- **Fase F** — Resumen determinista + corrección editable (§27-§28).
- **Fase G** — Sustitución de `renderGenerarForm`, con **modo experto ya incluido, no como flag futuro**
  (corrige a v1, que lo pateaba a una decisión abierta).
- **Fase H** *(nueva)* — Si Pablo aprueba la extensión mínima de §13: implementarla como cambio aislado y
  reversible en `ai_generator.py`, con su propio test de no-regresión contra el prompt actual.
- **Fase I** *(antes Fase H)* — Medición contra las métricas de §19.

## 17. Contrato entre la entrevista y el generador — tabla campo por campo

Esto es lo que la v1 no tenía y la auditoría marcó como crítico. Cubre las 15 categorías de §1. Columna
`Decisión` solo aplica a lo que no tenía destino en v1 — usa el criterio A) mantener y almacenar / B) extensión
mínima del generador / C) eliminar temporalmente, exigido por la corrección.

| Información | ¿Se recoge? | ¿Dónde se almacena? | ¿La usa el generador hoy? | ¿La usará un futuro generador? | Mientras tanto | Decisión |
|---|---|---|---|---|---|---|
| Ciudad, tipología | Sí | `CampoEspecificacion` → `params.proyecto` | **Sí, directo** | Sí | — | N/A, ya integrado |
| Superficie/forma/dimensiones del solar | Sí | → `params.solar` | **Sí, directo** | Sí | — | N/A |
| Orientación real de la parcela | Sí (§6.3) | → `params.solar.norte_grados` | **Sí, directo** | Sí | — | N/A |
| Plantas, altura libre, planta baja comercial | Sí | → `params.edificio` | **Sí, directo** | Sí | — | N/A |
| Mix de viviendas (nº por tamaño) | Sí (traducido desde pregunta 6, §18) | → `params.mix_viviendas` | **Sí, directo** | Sí | — | N/A |
| Ocupación/edificabilidad/retranqueos/plantas máx. (§6.4) | Sí, o `Hipótesis` si no se sabe | → `params.normativa` | **Sí, directo** | Sí | Se muestra el aviso de §6.4 si es Hipótesis | N/A |
| Para quién es (vivir/vender/alquilar) | Sí | `CampoEspecificacion`, categoría 4 | No | Posible, si se define un "modo de uso" del proyecto | Visible en el resumen como contexto, no afecta la geometría | **A** |
| No-negociables (texto libre) | Sí | `CampoEspecificacion`, categoría 5 | No | Sí, vía extensión mínima | Se anexa como texto a `contexto_cualitativo` si §13 se aprueba; si no, se guarda | **B** |
| Lo que menos importa | Sí | Categoría 5 | No | Posible, alimenta un futuro motor de priorización | Se guarda | **A** |
| Presupuesto | Sí | Categoría 13 | No | Posible, valida viabilidad económica cuando exista ese dominio | Se guarda, se muestra en el resumen | **A** |
| Sostenibilidad vs. coste | Sí | Categoría 11 | No (el prompt ya deriva un matiz automático por zona CTE) | Posible | Se guarda | **A** |
| Referencias estéticas | Sí | Categoría 12 | No | Sí, vía extensión mínima | Se anexa a `contexto_cualitativo` si §13 se aprueba | **B** |
| Privacidad | Sí | Categoría 7 | No | Sí, vía extensión mínima | Se anexa a `contexto_cualitativo` si §13 se aprueba | **B** |
| Accesibilidad / movilidad reducida | Sí | Categoría 4 | No (solo se evalúa a posteriori en `evaluator.py`) | **Sí, prioridad alta** — evita generar lo que el evaluador rechazará | Se anexa a `contexto_cualitativo` si §13 se aprueba — es el candidato de mayor prioridad | **B** |
| Exterior propio vs. interior | Sí | Categoría 9 | No (el prompt decide terraza/tendedero por su cuenta) | Posible | Se guarda | **A** |
| Cocina abierta/cerrada (nueva) | Sí | Categoría 14 | No | Sí, vía extensión mínima | Se anexa a `contexto_cualitativo` si §13 se aprueba | **B** |
| Estructura/sistema constructivo | No, en entrevista guiada; sí, en modo experto | Categoría 15 | No | Solo cuando exista un dominio de Estructura (`BRAIN_ARCHITECTURE.md`) | Ver §5 de la Parte I | **C** en entrevista guiada, expuesto solo en modo experto |

**Ninguna fila queda sin destino explícito** — esto es lo que corrige el hallazgo crítico de la auditoría: cada
dato recogido tiene ahora una respuesta a "¿y qué pasa mientras tanto?", nunca "desaparece".

## 18. Traducción de "mix grande/pequeño" a números — la decisión que v1 dejaba indefinida

La auditoría señaló que convertir "prefiero viviendas más pequeñas y más numerosas" (pregunta 6) en valores
concretos de `dorm_1`/`dorm_2`/`dorm_3` es, si se hace con una fórmula libre, el Entrevistador invadiendo el
trabajo del Motor. Regla explícita para no repetir el error: el ajuste es **una interpolación acotada entre
dos escenarios ya calculados por aritmética simple determinista** (nº total de viviendas ya declarado o
estimado × tamaño medio del solar disponible), nunca una decisión de programa nueva — el Entrevistador se
limita a mover un control deslizante entre dos extremos que el propio dato del solar ya acota, no a inventar un
mix. Si el resultado interpolado no es entero o produce una combinación rara, se marca como `Hipótesis` de
confianza Media y se muestra explícitamente en el resumen para que el usuario la confirme o la ajuste a mano —
igual que cualquier otra Hipótesis, sin trato especial.

## 19. Métricas para medir el éxito

Igual que v1, con una añadida: **% de campos de la Especificación con `destino_generador = "almacenado_sin_uso"`
que el usuario corrige o comenta explícitamente en el resumen** — si es alto, es una señal de que se está
recogiendo información que el usuario valora y el generador todavía no puede usar, y refuerza el caso de
negocio para aprobar la extensión mínima de §13 antes que después.

## 20. Motivos para NO implementar la idea

Igual que v1 (alternativa de formulario progresivo sin IA conversacional; prematuro si `PRD-001` no avanza),
más un tercero que la auditoría hizo explícito: **si Pablo decide no aprobar ninguna extensión mínima del
generador (§13) a corto plazo**, vale la pena preguntarse si construir el esquema rico de §22 —con 5 categorías
en estado "recogido pero sin uso"— aporta valor inmediato o es trabajo especulativo hasta que exista destino.
La recomendación de este documento (§13) es aprobar al menos la extensión mínima de accesibilidad y
privacidad junto con esta etapa, precisamente para que esto no ocurra.

---

# PARTE III — Diseño interno del entrevistador

## 21. Estrategia para minimizar llamadas a Claude/API — rediseñada

**Objetivo, ya no aspiración: 3-5 llamadas por entrevista completa**, con 0 llamadas siempre que sea posible.

### 21.1 Qué es 100% determinista (0 llamadas)

- Todas las preguntas de opción cerrada (2, 3, 6, 7, 10, 12, 13, 14, 15 de §6 — 9 de las 15).
- Todo lo confirmado como inferible (§4, tabla superior).
- Contradicciones entre dos valores estructurados del mismo campo (comparación directa, no requiere semántica).
- La priorización de la siguiente pregunta (§25).
- La compilación Especificación → `params` (§17).
- **El resumen final** (§27) — plantilla, no llamada. Esto es un cambio deliberado sobre v1: el resumen es
  precisamente el artefacto que el usuario debe poder confiar sin que un LLM lo parafrasee de más; una
  plantilla determinista sobre datos ya estructurados y etiquetados (Hecho/Inferencia/Hipótesis) es más segura
  y más barata a la vez.

### 21.2 Qué requiere Claude, y por qué

| Llamada | Cuándo | Qué hace | Coste típico |
|---|---|---|---|
| 1 — Interpretación del bloque fijo | Tras las respuestas a preguntas 1, 4, 5 (todas abiertas, presentadas juntas en la misma pantalla) | Extrae de una vez programa preliminar, no-negociables, prioridades y carácter — una sola llamada para 3 preguntas | Obligatoria |
| 2 — Interpretación del bloque adaptativo abierto | Solo si el usuario escribe texto libre en preguntas 9 u 11 (presupuesto detallado, referencias estéticas) | Extrae los campos correspondientes | Condicional — 0 si el usuario responde con cifras/opciones simples |
| 3 — Contradicción semántica | Solo si dos respuestas libres se contradicen de forma no detectable por comparación directa de campos | Señala el conflicto para presentarlo al usuario | Condicional, raro |
| 4-5 — Reintento de baja confianza | Solo si la llamada 1 o 2 devuelve una interpretación de confianza Baja en un dato imprescindible | Repregunta dirigida | Condicional |

En el caso típico (usuario responde con claridad, sin abrir contradicciones): **2 llamadas**. En el peor caso
dentro del presupuesto: **5**. Nunca 8-10 como proponía v1 — esa cifra mezclaba llamadas evitables (detección
de contradicciones como paso separado pudiendo integrarse en la llamada 1-2, que ya recibe el estado completo
como contexto) con la redacción del resumen, que deja de requerir IA en esta revisión.

### 21.3 Agrupación de turnos, no solo de campos

Cambio de diseño respecto a v1: las preguntas 1, 4 y 5 (todas abiertas, todas del bloque fijo) se presentan
**en la misma pantalla**, no en tres turnos separados — el usuario las responde de una vez y se interpretan
juntas en la llamada 1. Esto reduce llamadas *y* turnos a la vez, no solo llamadas por turno.

### 21.4 Límite duro

Máximo 5 llamadas a Claude por entrevista. Al alcanzarlo, el sistema cierra los imprescindibles restantes
exclusivamente con preguntas de opción cerrada, sin excepción.

## 22. La Especificación Arquitectónica — esquema completo (corrige el error crítico de v1)

**Ya no es un alias del `params` dict.** Es su propio artefacto, con más información de la que el generador
actual consume, precisamente para que la información sin destino hoy no desaparezca (§17).

### 22.1 Estructura

```
EspecificacionArquitectonica
├── especificacion_id         UUID estable del documento completo
├── version                   incrementa con cada corrección (§28)
├── sesion_entrevista_id       referencia a la Traza de Entrevista origen (null si viene de modo experto puro)
├── modo_origen                "entrevista_guiada" | "edicion_experta" | "mixto"
├── campos [ ]                  lista de CampoEspecificacion — ver 22.2
├── params_generador            subconjunto compilado 1:1 con el `params` dict de `ai_generator.py` hoy
│                                (derivado de "campos", nunca editado directamente)
├── contexto_cualitativo        texto compilado desde los campos con decisión B (§17) — solo se usa
│                                si se aprueba la extensión mínima de §13; vacío si no
└── decisiones_pendientes [ ]   campos imprescindibles sin resolver, si se fuerza generar igualmente (§28)
```

### 22.2 `CampoEspecificacion` — la unidad, con lo que pediste explícitamente

```
CampoEspecificacion
├── especificacion_id          id ESTABLE del campo (p. ej. "solar.superficie_m2", "prioridades.trade_off")
│                               — concept_id, sobrevive a correcciones (mismo principio que FACT_MODEL.md §7)
├── categoria                   una de las 15 de §1
├── etiqueta                    nombre legible
├── tipo_dato                   información_usuario | inferencia | preferencia | restricción
├── valor
├── confianza                   Alta / Media / Baja — solo si tipo_dato = inferencia; cualitativa, nunca numérica
├── origen [ ]                  ids de turno/respuesta que lo originaron — trazabilidad hasta la respuesta cruda
├── destino_generador            "usado_directo" | "usado_via_extension_minima" | "almacenado_sin_uso" | "no_aplica"
├── decision_contrato            A | B | C (§17) — solo si destino_generador ≠ "usado_directo"
└── editable_por_usuario        bool — si aparece en el resumen (§27) como corregible
```

`tipo_dato` cubre explícitamente lo pedido: información del usuario, inferencia, preferencia y restricción son
cuatro valores distintos del mismo campo, nunca mezclados. Las decisiones pendientes viven en la lista de nivel
superior, no como un quinto valor de `tipo_dato` — son ausencia de campo, no un tipo de campo.

### 22.3 La cadena de trazabilidad — hasta dónde llega hoy, y qué se deja preparado para el resto

Pedida explícitamente: *respuesta → interpretación → requisito → decisión arquitectónica → geometría →
evaluación.*

| Tramo | ¿Se sostiene con este diseño? | Cómo |
|---|---|---|
| Respuesta → interpretación | Sí | `RespuestaInterpretada.respuesta_cruda` → `.naturaleza` + `.confianza` |
| Interpretación → requisito | Sí | `RespuestaInterpretada.derivada_de` → `CampoEspecificacion.origen` |
| Requisito → decisión arquitectónica | **Sí, implementado (2026-08-13)** | `verificar_directivas_duras()` produce `VerificacionDeterminista` por directiva dura (cumple/no_cumple/no_verificable), persistida en `TrazaDeGeneracion`; y `GeneratedProject.referencias_especificacion` recoge el autoinforme opcional de Claude (`respuesta.referencias_especificacion`, contrato §9-§10 — best-effort, nunca la única fuente fiable) |
| Decisión arquitectónica → geometría | **No, y no depende de este PRD** | `ai_generator.py` sigue sin anotar qué habitación responde a qué instrucción concreta; corregirlo es un cambio más profundo en ese archivo, fuera de alcance |
| Geometría → evaluación | Ya existe | `evaluator.py` ya referencia `unit.name`/`room` |

**El gancho barato que deja esto preparado, sin implementarlo:** cada `CampoEspecificacion` tiene un
`especificacion_id` estable. Si en el futuro se aprueba la extensión mínima de §13, el cambio mínimo adicional
en `ai_generator.py` sería que el JSON que Claude devuelve pudiera incluir, por vivienda o habitación, una
lista opcional `referencias_especificacion: [especificacion_id, ...]` citando qué requisitos tuvo en cuenta.
No se pide a Claude que lo haga en esta etapa — se deja documentado como el punto exacto de extensión futura,
para que cuando se aborde no haga falta rediseñar el esquema de la Especificación, solo extender el prompt y el
parseo de la respuesta.

## 23. Principios de diseño del entrevistador

Los 10 de v1 se mantienen; se añade uno:

11. **Todo dato recogido declara su destino.** Ningún `CampoEspecificacion` puede existir sin un
    `destino_generador` explícito (§22.2) — es la aplicación directa, a nivel de dato individual, de la
    corrección más importante de esta revisión.

## 24. Estado de conversación

Igual que v1 (`EstadoEntrevista`), con dos campos nuevos:

```
EstadoEntrevista
├── ...  (igual que v1: sesion_id, modo, historial_turnos, respuestas_interpretadas,
│        contradicciones, no_negociables, progreso, llamadas_ia_consumidas)
├── turnos_totales             contador independiente del de llamadas — ver §28
└── modo_entrada                "entrevista_guiada" | "edicion_experta" — determina si §29 aplica desde el inicio
```

## 25. Árbol / estrategia de decisión para la siguiente pregunta

Sin cambios respecto a v1 — la cola priorizada por (1) imprescindible sin resolver, (2) contradicción
pendiente, (3) cuántas preguntas condiciona, (4) coste de respuesta para el usuario sigue siendo el diseño
correcto; la auditoría no encontró fallos aquí.

## 26. Manejo de respuestas ambiguas, contradictorias o incompletas

Sin cambios de fondo respecto a v1 (§22 de v1) — ambigua → `Hipótesis` confianza Baja; contradictoria → nunca
se sobrescribe en silencio, se presenta y el usuario decide; incompleta → estado explícito, nunca valor por
defecto silencioso.

## 27. Presentación del resumen — ahora determinista

Cambio respecto a v1: ya no es "redactado por Claude a partir de la Especificación" — es una **plantilla**,
organizada por las 15 categorías de §1, con una frase fija por combinación de `tipo_dato` + `destino_generador`:

- *"Nos dijiste que..."* — `tipo_dato = información_usuario`.
- *"Entendemos que..., porque nos dijiste que..."* — `tipo_dato = inferencia`, cita `origen`.
- *"Hemos asumido que..., porque..."* — `tipo_dato` con `confianza = Baja`, aviso visual obligatorio.
- Cuando `destino_generador = "almacenado_sin_uso"`: una nota explícita, no oculta — *"Esto lo hemos guardado,
  pero el generador actual todavía no lo usa para diseñar"* — es la aplicación directa a nivel de UI del
  principio 11 de §23.

Un enlace "ver todos los detalles" abre la Traza de Entrevista completa, igual que en v1.

## 28. Corrección y criterio de parada — con los dos límites pedidos

**Corrección:** igual que v1 — edición por bloque, invalidación en cascada de lo derivado, visible.

**Criterio de parada, con dos límites explícitos donde v1 solo tenía uno:**

1. Los 8 imprescindibles en `Hecho`/`Hipótesis`, sin contradicciones pendientes — igual que v1.
2. **Límite de llamadas a IA: 5** (§21.4).
3. **Límite de turnos totales: 20**, independiente del anterior — a partir del turno 15 el sistema avisa
   cuánto queda; en el turno 20, si aún faltan imprescindibles, fuerza el cierre con lo disponible, marcando el
   resto como `Hipótesis` explícita en `decisiones_pendientes`. Este límite es nuevo en esta revisión: v1 solo
   acotaba coste de API, no fatiga del usuario — una entrevista hecha enteramente de preguntas de opción
   cerrada no gasta presupuesto de IA pero sí puede alargarse indefinidamente sin este segundo tope.

## 29. Modo experto — incorporado como parte del diseño de esta etapa

No estaba en v1 más que como riesgo sin resolver. Contrato mínimo, sin implementarlo:

1. **Entrada:** al pulsar "Generar proyecto", el usuario elige entre "Entrevista guiada" (por defecto) o
   "Modo experto".
2. **Modo experto** abre un editor estructurado de la Especificación Arquitectónica —organizado por las 15
   categorías de §1— **sobre el mismo esquema de datos** que produce la entrevista (§22), no un segundo
   formulario paralelo. El compilador Especificación → `params` (§17) es compartido: un solo camino desde la
   Especificación hasta el generador, sea cual sea el origen.
3. **Campos exclusivos de modo experto:** los de la categoría 15 (estructura/sistema constructivo, §5 de la
   Parte I) solo son editables aquí — la entrevista guiada nunca los pregunta, pero un arquitecto puede
   declararlos si quiere.
4. **Convergencia, no bifurcación irreversible:** ambos modos terminan en el mismo resumen de confirmación
   (§27) antes de generar — ni siquiera el modo experto se salta esa revisión, porque el principio "nada
   decidido por el sistema queda oculto" (§23, principio 9) aplica igual a los valores por defecto que el
   propio modo experto pueda dejar sin tocar. Un usuario puede además cambiar de un modo a otro a mitad de
   camino sin perder lo ya introducido, porque ambos escriben sobre la misma Especificación.
5. **Validación compartida:** un `CampoEspecificacion` imprescindible vacío bloquea la generación igual en
   modo experto que en la entrevista guiada (criterio de aceptación de §14) — ser experto no exime de
   completar lo imprescindible, solo de que se lo pregunten conversacionalmente.

## 30. Extensión mínima del generador — aprobada e implementada (2026-08-13)

Responde directamente a §17 (decisión B en 5 filas: no-negociables, referencias estéticas, privacidad,
accesibilidad, cocina abierta/cerrada). **Implementada**, con el mismo alcance de las 5 filas que este
análisis proponía — ninguna categoría nueva añadida fuera de las ya decididas aquí.

**Mecanismo implementado — más rico que el propuesto originalmente, mismo principio:** en vez de un único
`contexto_cualitativo: str` de texto plano, `params.contexto_cualitativo` es un dict `{directivas: [...],
texto_prompt: str, especificacion_id: str}` — cada directiva conserva su `categoria`/`fuerza`
(`dura`/`blanda`)/`texto_origen`/`texto_prompt`/`verificable_geometricamente`, no solo la frase final. La
razón del cambio de forma, descubierta durante la implementación: una directiva "dura" (p. ej.
accesibilidad) necesita poder verificarse de forma determinista después de generar
(`verificar_directivas_duras()`, contrato §12), lo que exige conservar su identidad, no solo su texto.
`texto_prompt` sigue siendo la compilación determinista (nunca por Claude) que se anexa a
`_build_user_message` — el principio central de este análisis ("no reescribe ninguna regla de
`SYSTEM_PROMPT`, solo anexa") se mantiene exactamente igual en el código real
(`ai_generator._compilar_bloque_directivas`).

`compilar_params()` (`analyzer/interview/compilador.py`) es quien compone este dict desde los
`CampoEspecificacion` con `decision_contrato = B`, con el mismo `especificacion_id` de la Especificación para
que `app.py:_guardar_traza_de_generacion()` pueda enlazar la generación con la entrevista que la originó.

**Orden de prioridad si se aprueba, y por qué:**

1. **Accesibilidad.** Es la única de las cinco con una consecuencia negativa ya medible hoy: `evaluator.py`
   evalúa accesibilidad post-hoc (bloques 8, 21) y puede rechazar un proyecto que se generó sin ninguna guía de
   accesibilidad. Generar a ciegas y rechazar después es el peor de los mundos.
2. **Privacidad.** Afecta directamente a huecos y orientación de estancias, algo que `SYSTEM_PROMPT` ya
   razona en prosa — el canal encaja de forma natural.
3. **No-negociables.** Es, por definición, lo que el usuario ha dicho explícitamente que no se puede perder;
   ignorarlo en la generación después de haberlo preguntado con tanto énfasis es contradictorio con el propio
   diseño de la entrevista.
4. **Cocina abierta/cerrada.** Instrucción simple, de bajo riesgo, alto valor percibido.
5. **Referencias estéticas.** La de mayor incertidumbre de interpretación (texto libre sobre "casas que te
   gustan" es más difícil de traducir a una instrucción de prompt útil que las cuatro anteriores) — última en
   la cola, no descartada.

Sostenibilidad y presupuesto se quedan en decisión A (§17): no tienen un hueco natural en la lógica de
generación de habitaciones de `SYSTEM_PROMPT` sin un cambio más profundo que "anexar texto" — extenderlos exige
tocar la lógica de reglas, no solo el mensaje, y eso sí sería el rediseño de `ai_generator.py` que esta etapa
tiene explícitamente prohibido.

---

# PARTE IV — Cierre

## 31. Autoauditoría de esta revisión

- **¿Es autocontenido?** Sí — la Parte I reproduce íntegras las 15 categorías, los 8 imprescindibles, los
  opcionales, la lista de inferibles verificada contra código, y las 15 preguntas literales. Ya no hay ninguna
  referencia a "la conversación de la Etapa 0.2" como fuente.
- **¿Cada pregunta tiene destino?** Sí, tabla de §17 — 15 de 15 filas con decisión explícita (N/A si ya usada
  directamente, A/B/C si no).
- **¿Se promete alguna capacidad inexistente?** No — §6.4 corrige la pregunta 7; §4 separa explícitamente lo
  confirmado en código de lo aspiracional.
- **¿El coste de API está limitado?** Sí — 3-5 llamadas objetivo, 5 como límite duro, con fallback determinista
  garantizado (§21).
- **¿La trazabilidad está preparada?** (Actualizado 2026-08-13.) Los tramos respuesta→interpretación→requisito
  y requisito→decisión arquitectónica quedan cerrados (§22.3: `VerificacionDeterminista` +
  `referencias_especificacion`, implementados). Decisión arquitectónica→geometría (qué habitación concreta
  responde a qué instrucción) sigue sin cerrar — no depende de este PRD, exige anotar `ai_generator.py` a
  nivel de habitación, no solo de proyecto.

## 32. Decisiones que quedan abiertas

1. ~~**¿Se aprueba la extensión mínima del generador (§30)?**~~ **Resuelta (2026-08-13): aprobada e
   implementada** — ver §30. Los 5 campos de decisión B llegan de verdad a `ai_generator.py`, verificados con
   generación real.
2. **Presupuesto exacto de llamadas** — 3-5 es el objetivo de diseño; falta validar contra coste real en uso.
3. Grado de alineación con `PRD-001` — igual que v1.
4. Dónde persiste `EstadoEntrevista`/`EspecificacionArquitectonica` entre turnos — detalle de Etapa 0.4.
5. Prioridad relativa frente a `REFACTOR_MASTERPLAN.md`/`PRD-001` — de Pablo.
6. Si el modo experto necesita, además de edición de campos, una vista de "diff" cuando alguien alterna entre
   modo experto y guiado sobre la misma Especificación — no resuelto, riesgo menor.

## 33. Problemas que siguen abiertos, sin resolver del todo

Actualizado 2026-08-13 — con la misma honestidad que exige este proyecto:

- ~~La extensión mínima del generador (§30) es un análisis, no una decisión tomada~~ — **cerrado**: aprobada,
  implementada y verificada con generación real (justificación de Claude citando las directivas, verificación
  determinista de accesibilidad, traza persistida).
- La cadena de trazabilidad completa (requisito → geometría, a nivel de habitación individual) sigue sin
  cerrarse — requisito → decisión arquitectónica sí quedó cerrado en esta etapa (§22.3); decisión → geometría
  exige anotar `ai_generator.py` habitación a habitación, fuera de alcance.
- **Nuevos, encontrados por auditoría posterior al cierre inicial de esta iniciativa** (no estaban previstos
  como huecos en esta v2, pero es donde quedaron realmente los dos bugs de cierre):
  el catálogo de 15 preguntas nunca pregunta `edificio.plantas` (solo el máximo normativo) — la entrevista
  guiada sola no compila sin pasar por el puente de datos técnicos; y los tests de esta iniciativa siguen sin
  adaptarse a `pytest` (siguen siendo scripts standalone). Ambos, deliberadamente fuera de alcance de la
  sesión de cierre de 2026-08-13.

---

**Decisión:** Implementado y aprobado por Pablo (2026-08-13). Verificado end-to-end con Flask + Claude reales:
entrevista guiada completa, puente de datos técnicos, modo experto (desde cero y como corrección sobre una
sesión existente), conexión real con `ai_generator.py` (Fase F/§30), y trazabilidad epistémica
(Hecho/Inferencia/Hipótesis) preservada en ambos flujos de edición. No quedan decisiones abiertas de las
listadas en §32 salvo la #2 (presupuesto exacto de llamadas, pendiente de datos de uso real) y las de alcance
explícitamente diferido en el párrafo de Cierre al principio de este documento.
