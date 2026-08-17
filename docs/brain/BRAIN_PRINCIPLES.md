# BRAIN_PRINCIPLES.md

**Propósito:** fijar la constitución del Reasoning Engine — los principios que ninguna implementación futura, ningún plazo, ninguna presión comercial puede relajar sin pasar antes por una revisión explícita de este mismo documento. No son un resumen de los catorce documentos anteriores de `docs/brain/` — son su destilado: cada uno de los principios que siguen ya apareció, razonado y justificado con detalle, en al menos uno de ellos. Este documento no repite esa justificación — la cita, y la convierte en regla.

**Cómo leer este documento:** cada principio lleva, entre paréntesis, el documento donde se razonó por primera vez con detalle. Ese documento es la referencia si hace falta entender el *porqué*; este documento es la referencia para saber *que* la regla existe y que tiene prioridad. En caso de conflicto entre cualquier documento futuro — de diseño, de PRD, o de implementación — y uno de estos principios, **el principio gana**, y el documento que lo contradice se corrige, no al revés.

**En caso de duda sobre qué cuenta como "innegociable":** un principio de esta lista nunca se relaja por conveniencia de implementación, por presión de plazo, ni porque una versión menos estricta "sería casi lo mismo". Sí puede refinarse — un principio puede ganar precisión con el tiempo — pero nunca se contradice ni se vacía de contenido sin que esa decisión quede documentada como una enmienda explícita a este documento (Título VIII).

---

## Título I — Sobre los hechos y su origen

**1. Ningún hecho se inventa.** Todo Fact tiene un origen trazable hasta una Observation real o hasta una función de composición exacta y declarada — nunca aparece un dato sin que se pueda seguir de dónde vino. *(`FACT_MODEL.md`)*

**2. El origen de un dato es inseparable de su valor.** Nunca se presenta un número o una afirmación sin decir si es observado, derivado, estimado o promovido desde una hipótesis. *(`FACT_MODEL.md`, `UNCERTAINTY_MODEL.md`)*

**3. Nada se edita — todo se sustituye.** Un cambio en un dato nunca modifica el registro anterior; crea una versión nueva que lo sucede, dejando el histórico completo intacto y consultable. *(`REASONING_ENGINE_SPEC.md`)*

**4. Un dato ausente nunca se convierte en un valor por defecto**, ni de forma directa ni disfrazada de una estimación o una hipótesis aplicadas sin criterio. *(`UNCERTAINTY_MODEL.md`)*

---

## Título II — Sobre la inferencia y la lógica

**5. Toda inferencia debe tener evidencia.** Ninguna conclusión existe sin un rastro completo y trazable de los datos y las reglas que la sostienen. *(`REASONING_ENGINE_SPEC.md`, `EVIDENCE_MODEL.md`)*

**6. Los mismos datos, con la misma regla, producen siempre la misma conclusión.** Si no la producen, es un defecto que corregir, nunca una variabilidad legítima. *(`INFERENCE_ENGINE.md`)*

**7. Una conclusión negativa solo nace de una comprobación positiva de ausencia.** Que algo no existe o no se cumple nunca se infiere de un dato que simplemente falta — ausencia de evidencia no es evidencia de ausencia. *(`INFERENCE_ENGINE.md`)*

**8. Ninguna restricción se expresa como lógica nueva.** Toda restricción es un dato dentro de un catálogo cerrado y gobernado — el motor crece por catálogo, nunca por código particular para un caso. *(`CONSTRAINT_MODEL.md`)*

---

## Título III — Sobre la incertidumbre

**9. La incertidumbre nunca se oculta.** Toda conclusión que no alcanza la certeza más alta lo dice de forma explícita — nunca de forma implícita, y nunca en un tono que sugiera más seguridad de la que hay. *(`EXPLANATION_ENGINE.md`, `UNCERTAINTY_MODEL.md`)*

**10. La confianza siempre es cualitativa.** Nunca se expresa como un número o un porcentaje que sugiera una precisión que el sistema, honestamente, no tiene. *(`DECISION_ENGINE.md`, `REASONING_ENGINE_SPEC.md`)*

**11. La confianza de una conclusión es la de su eslabón más débil.** Nunca un promedio, nunca una mayoría, nunca una fórmula que reparta el peso entre lo sólido y lo frágil. *(`EVIDENCE_MODEL.md`)*

**12. Toda hipótesis y toda aproximación se marcan siempre como tales**, sin importar cuánta confianza alcancen con el tiempo — nunca indistinguibles de un dato observado directamente. *(`UNCERTAINTY_MODEL.md`)*

---

## Título IV — Sobre los dominios y su gobierno

**13. Los dominios no modifican hechos de otros dominios.** Un dominio solo puede consumir las conclusiones ya publicadas de otro dominio, nunca su conocimiento interno ni sus datos crudos. *(`BRAIN_ARCHITECTURE.md`, `CHAIN_REASONING.md`)*

**14. Ninguna severidad bloqueante se diluye.** El resultado combinado de varias severidades es siempre el máximo entre ellas, nunca un promedio que la esconda entre hallazgos menores. *(`BRAIN_ARCHITECTURE.md`, reafirmado en cada documento posterior)*

**15. Todo catálogo cerrado del motor** — patrones de evaluación, comparadores, tipos de dato, criterios de agrupación o de conflicto — **se gobierna de forma centralizada.** Ningún dominio lo extiende por su cuenta para resolver un caso particular. *(`CONSTRAINT_MODEL.md`, `FACT_MODEL.md`)*

**16. Ninguna restricción se activa sin una fuente citable** — una norma verificable, o un criterio profesional declarado explícitamente como tal, nunca en silencio. *(`CONSTRAINT_MODEL.md`)*

---

## Título V — Sobre los conflictos y las decisiones

**17. Las preferencias nunca sustituyen a la normativa.** Una preferencia solo desempata dentro del espacio ya filtrado por lo bloqueante — nunca puede relajar ni anular un incumplimiento. *(`DECISION_ENGINE.md`, `REASONING_ENGINE_SPEC.md`)*

**18. Una discrepancia legítima entre dos criterios expertos nunca se resuelve por la fuerza.** Se expone como tal, permanentemente si hace falta — no es un fallo del sistema, es el resultado correcto. *(`CONFLICT_ENGINE.md`, `DECISION_ENGINE.md`)*

**19. Ningún empate real entre criterios de prioridad se rompe con un criterio no declarado** — ni el orden de registro, ni el número de dominio, ni ningún otro desempate silencioso disfrazado de determinismo técnico. *(`CONFLICT_ENGINE.md`)*

**20. Toda decisión que se aparta de una decisión anterior sobre la misma tensión lo reconoce explícitamente** — nunca contradice un precedente en silencio. *(`CONFLICT_ENGINE.md`)*

**21. Toda recomendación debe ser reproducible**: las mismas alternativas, evaluadas con el mismo criterio de comparación, producen siempre el mismo resultado, auditable en cualquier momento. *(`RECOMMENDATION_ENGINE.md`, `CONFLICT_ENGINE.md`)*

**22. Ninguna recomendación se presenta sin haber sido evaluada en sus consecuencias reales** — nunca en una aproximación de lo que probablemente pasaría. *(`RECOMMENDATION_ENGINE.md`, `REASONING_ENGINE_SPEC.md`)*

---

## Título VI — Sobre el juicio y el criterio

**23. Un juicio de criterio arquitectónico nunca se presenta con la misma certeza que un hecho verificado**, por bien razonado que esté. *(`ARCHITECTURAL_QUALITY.md`, `EVIDENCE_MODEL.md`)*

**24. El sistema nunca inventa una intención de diseño no declarada** para justificar un juicio que, sin esa intención, no le corresponde emitir. *(`ARCHITECTURAL_QUALITY.md`)*

**25. Ninguna dimensión de un juicio se combina con otra en una puntuación única** — ni siquiera para comparar un proyecto contra otro. *(`GLOBAL_ASSESSMENT.md`, `BRAIN_ARCHITECTURE.md`)*

**26. La viabilidad de un proyecto nunca se diluye ni se compensa con buen desempeño en otras dimensiones** — un "no viable" sigue siendo la primera lectura, sin importar cuánto brille el resto. *(`GLOBAL_ASSESSMENT.md`)*

**27. El sistema describe antes que juzga**, siempre que la pregunta en cuestión no tenga una respuesta objetivamente correcta. *(`ARCHITECTURAL_QUALITY.md`)*

---

## Título VII — Sobre el arquitecto humano

**28. El sistema nunca reclama la firma ni la responsabilidad profesional del arquitecto**, en ninguna forma, por explícita o implícita que sea la pregunta que se lo sugiera. *(`VIRTUAL_ARCHITECT.md`, `NORTH_STAR_2031.md`)*

**29. El sistema nunca cede una cifra o un veredicto prohibido solo por parecer más útil o más agradable** — ni siquiera cuando el arquitecto humano insiste en pedirlo directamente. *(`VIRTUAL_ARCHITECT.md`, `GLOBAL_ASSESSMENT.md`)*

**30. Toda reversión de una posición anterior se explica de forma explícita** — el sistema nunca presenta una conclusión nueva como si siempre hubiera sido la respuesta. *(`VIRTUAL_ARCHITECT.md`)*

---

## Título VIII — Sobre esta constitución

**31. Estos principios tienen prioridad sobre cualquier implementación futura.** Ninguna decisión de ingeniería, de plazo o de conveniencia comercial los puede relajar sin una revisión explícita de este documento — la revisión es el mecanismo permitido, el silencio no lo es.

**32. Esta constitución se modifica exactamente igual que todo lo demás en este modelo**: nunca en el sitio, siempre con una versión nueva y fechada, nunca en silencio. Un principio que deja de aplicar no desaparece de este documento — se marca como derogado, con la razón y la fecha, de la misma forma en que un Constraint obsoleto se marca con fecha de fin de vigencia en vez de borrarse (`CONSTRAINT_MODEL.md` §8). La historia de esta constitución es, en sí misma, parte de la memoria que `PROJECT_MEMORY.md` ya exige conservar.

---

## Cierre

Treinta y dos principios, no más de los que hacían falta y no menos de los que la serie completa ya había demostrado, uno por uno, que eran innegociables. Ninguno es una preferencia de estilo — cada uno existe porque algún documento anterior mostró exactamente qué se rompe si se relaja: un dato inventado reproduce el Bug #1; una puntuación fabricada reproduce `TIPOLOGIA_BENCHMARKS`; un dominio que toca los datos de otro reproduce el monolito incoherente que `BRAIN_ARCHITECTURE.md` nombró como el enemigo principal desde el primer documento de toda la serie. Este documento no añade ninguna idea nueva — su valor es que, a partir de hoy, ya no hace falta releer catorce documentos para saber si una decisión de implementación es aceptable: basta con comprobar si contradice alguno de estos treinta y dos.
