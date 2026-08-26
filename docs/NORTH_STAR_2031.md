# NORTH_STAR_2031.md — La visión de ArchMuse en 2031

> **Nota de alineación (2026-08-18).** Este documento **no** ha quedado obsoleto por la visión del "Cerebro Arquitecto". El reparto entre ambos está resuelto en `docs/design/2026-08-18-alineacion-estrategica-paso0.md`: el ADR manda sobre *qué* razona ArchMuse, este documento manda sobre *dónde* vive. Leer esa nota antes de usar cualquiera de los dos como criterio.

**Punto de partida de este documento:** ninguno de los párrafos que siguen describe el software que existe hoy. Es 2031. ArchMuse es la plataforma líder de validación de proyectos arquitectónicos en Europa. Miles de estudios la usan cada día. Este documento describe ese producto perfecto y después trabaja hacia atrás para definir qué debe existir en 24, 12, 6, 3 y 1 mes desde hoy para que esa visión sea alcanzable.

---

## La visión

### 1. ¿Qué problema resuelve mejor que nadie?

ArchMuse elimina la incertidumbre normativa como fricción del acto de diseñar. No "revisa cumplimiento" — responde, en el instante exacto en que un arquitecto toma una decisión de diseño, a la pregunta que de verdad le preocupa: *¿esto es legal, es seguro, y puedo firmarlo con mi nombre?* En cualquier país europeo, con cualquier marco regulatorio local, con la misma fiabilidad. Nadie más lo hace mejor porque nadie más ha construido, verificado y mantenido durante años la profundidad normativa necesaria país por país, comunidad por comunidad, mientras al mismo tiempo lo ha hecho vivir dentro del flujo real de trabajo del arquitecto en vez de al lado de él.

### 2. Un día con ArchMuse

Un arquitecto abre por la mañana su software de diseño habitual — ArchMuse ya no es una pestaña aparte, es una capa nativa dentro de él. Mientras distribuye una planta, un halo sutil de color en cada estancia indica su estado normativo en tiempo real: no interrumpe, no hay que pedirle nada, simplemente está encendido, como la corrección ortográfica en un procesador de texto.

Al cerrar una planta, pide una lectura completa. ArchMuse no le entrega una lista de fallos — le entrega los problemas ordenados por impacto económico y de plazo, y para cada uno, dos o tres variantes de diseño generadas automáticamente que lo resuelven sin romper el resto del proyecto. El arquitecto elige. No redibuja desde cero.

A media mañana revisa, junto a su equipo — todos conectados al mismo proyecto, con roles e historial compartido —, el "pasaporte de cumplimiento" del edificio: no un informe estático, sino un estado vivo que se actualiza con cada cambio.

Por la tarde, con el diseño cerrado, pulsa un botón: ArchMuse genera el paquete completo de documentación de visado — memoria justificativa con cita literal de artículos, planos anotados, cálculos — y lo envía directamente al colegio de arquitectos a través de la integración institucional. No se exporta nada a mano.

Ese mismo día, el promotor con el que trabaja recibe (si el arquitecto lo autoriza) un resumen del presupuesto de riesgo del proyecto: qué queda por resolver, cuánto costaría no resolverlo, qué plazo añadiría.

Meses después, en obra, el aparejador usa la aplicación de campo de ArchMuse para comparar lo construido contra lo aprobado, con el mismo lenguaje y las mismas referencias normativas que se usaron en el diseño. El ciclo — diseño, visado, obra — se completa dentro de un único sistema, no en tres herramientas distintas que nadie reconcilia.

### 3. ¿Qué tareas han desaparecido?

- Repasar manualmente el articulado normativo antes de cada entrega.
- Redactar a mano la memoria justificativa de cumplimiento.
- Exportar y convertir formatos para poder pasar un plano por una herramienta de verificación aparte.
- Descubrir en el visado, semanas después, que algo no cumplía.
- Rehacer un proyecto entero por un fallo detectado tarde.
- Preguntarse si una norma concreta aplica en esta comunidad autónoma o este país — el sistema ya lo sabe por la ubicación del proyecto.
- Formar a cada arquitecto junior desde cero, a base de PDF, en la letra pequeña del cumplimiento normativo.
- Reconciliar a mano discrepancias entre estructura, instalaciones y arquitectura.

### 4. ¿Qué decisiones toma ArchMuse automáticamente?

- Qué normativa aplica según ubicación, tipología, uso y fecha del proyecto, incluidas excepciones y regímenes transitorios.
- La priorización de qué corregir primero según impacto legal, económico y de plazo.
- La generación de variantes de diseño que resuelven un incumplimiento concreto sin crear uno nuevo — comprobado automáticamente antes de proponerlas, nunca a ciegas.
- El borrador completo de la documentación de visado.
- La detección de choques entre disciplinas.
- Las alertas proactivas cuando cambia una normativa y afecta a un proyecto en curso o ya construido.
- La verificación en obra del as-built contra lo aprobado.

### 5. ¿Qué sigue decidiendo el arquitecto?

- El diseño en sí: la intención espacial, la composición, la relación con el entorno, la identidad del proyecto. ArchMuse nunca decide cómo debe ser un edificio, solo si una decisión concreta es viable.
- Cuál de las variantes propuestas usar — o ninguna, con pleno conocimiento de causa.
- Qué riesgo asumir de forma consciente y documentada en las zonas grises donde la norma admite interpretación y hace falta juicio profesional, no una regla.
- La relación con el cliente y el promotor: cómo comunicar el equilibrio entre diseño, coste y plazo.
- La firma. La responsabilidad civil sigue siendo del arquitecto colegiado. ArchMuse informa con el máximo rigor posible; nunca sustituye esa firma.

### 6. ¿Qué métricas convierten a ArchMuse en indispensable?

- El porcentaje de proyectos que pasan visado a la primera entre estudios usuarios frente al resto del sector — una cifra pública y auditada que se ha convertido en el argumento de venta central.
- El tiempo medio ahorrado por proyecto entre concepción y visado.
- La reducción medible de siniestros de responsabilidad civil profesional entre estudios usuarios — un dato que las propias aseguradoras empiezan a exigir o a premiar con mejores condiciones.
- El volumen acumulado de proyectos analizados: el benchmark comparativo, ahora real y no estimado, se ha convertido en la referencia del sector — "percentil ArchMuse" se usa en conversación profesional igual que cualquier otro estándar de industria consolidado.
- La retención: casi ningún estudio que lo adopta lo abandona, porque quitar ArchMuse no es cancelar una suscripción, es desmontar el proceso de control de calidad de todo el estudio.

### 7. ¿Qué dicen los clientes cuando lo recomiendan?

*"No sabría cómo firmar un proyecto sin esto ya."*
*"Mi seguro de responsabilidad civil es más barato desde que lo uso."*
*"Formo a mis arquitectos junior con ArchMuse, no con el CTE en PDF."*
*"Cuando un cliente me pregunta si esto va a pasar el visado, le enseño la pantalla de ArchMuse, no mi opinión."*
*"Cambié de estudio y lo primero que pedí fue que tuvieran ArchMuse."*

### 8. ¿Qué hace que abandonarlo sea una mala decisión?

- Perder el historial completo de decisiones y validaciones de cada proyecto — la memoria institucional del estudio entero.
- Perder la garantía asociada a los hallazgos críticos.
- Perder la integración directa con el colegio de arquitectos, con lo que el visado vuelve a ser más lento y más manual.
- Tener que reentrenar a todo el equipo en un proceso de control de calidad distinto.
- Perder el acceso al benchmark comparativo acumulado — sin histórico, no hay con qué medir el propio progreso.
- Que el cliente o el promotor, ya acostumbrado a recibir el pasaporte de cumplimiento de cada proyecto, deje de confiar en un estudio que ha dejado de ofrecerlo.

### 9. ¿Cómo ha cambiado la profesión gracias a ArchMuse?

Los arquitectos jóvenes aprenden normativa dentro del propio flujo de trabajo, no memorizando el texto legal. El tiempo entre concepción y visado se ha reducido de forma estructural en todo el sector, no solo entre los estudios usuarios — se ha convertido en la expectativa estándar de la industria. La responsabilidad civil profesional se documenta y se defiende de forma sistemática, y eso ha cambiado cómo las aseguradoras evalúan el riesgo de un estudio. El oficio se ha desplazado hacia diseño e intención, y se ha alejado de la verificación administrativa manual — la parte del trabajo que menos satisfacción daba a la mayoría de arquitectos. Los promotores empiezan a exigir contractualmente "verificado con ArchMuse", con el mismo peso con el que hoy se exige un seguro decenal.

### 10. ¿Qué productos han intentado copiarlo y por qué han fracasado?

- **Clones de IA sin motor de reglas verificado.** Fallan a la primera vez que un arquitecto que se juega su firma encuentra un hallazgo incorrecto — y no hay segunda oportunidad con ese tipo de error.
- **Plugins nativos construidos internamente por fabricantes de software BIM.** Tienen la distribución, pero no la profundidad normativa multi-país ni años de historial de datos — cobertura superficial disfrazada de integración profunda.
- **Startups bien financiadas que atacaron con velocidad de producto.** Construyeron rápido, pero llegaron tarde a la relación institucional con colegios y aseguradoras, que ya estaba cerrada — y sin esa distribución, la velocidad de producto no basta.
- **Herramientas horizontales de "compliance con IA" que intentaron entrar en arquitectura desde fuera del sector.** Nunca entendieron que un arquitecto no compra "cumplimiento normativo" en abstracto — compra defensa profesional y tiempo de vida, y eso exige un producto construido por gente que ha vivido el oficio, no solo el problema técnico.

---

## Trabajando hacia atrás: la empresa que hay que construir

*Cada horizonte parte del anterior. Ningún horizonte asume capacidades que no se hayan sentado en el paso previo.*

### Horizonte: 24 meses

**Objetivo:** dejar de ser "una herramienta a la que se sube un archivo" y convertirse en una capa nativa de cumplimiento en tiempo real dentro del flujo BIM del arquitecto, operando en varios países, con la primera relación institucional real ya firmada y el activo de datos propio empezando a acumularse de verdad.

**Funcionalidades imprescindibles:**
- Comprobación normativa en tiempo real dentro de al menos un entorno BIM mayoritario, en uso por clientes de pago reales, no en beta cerrada.
- Colaboración de equipo completa: roles, historial de proyecto, trazabilidad de quién decidió qué.
- Generación automática de la documentación de visado.
- Primer módulo de verificación en obra, aunque sea en piloto con un número reducido de estudios.
- Garantía o seguro sobre los hallazgos críticos, activo en al menos un mercado.

**Capacidades técnicas necesarias:**
- Integración nativa con al menos un formato/SDK de BIM (no reconstrucción de geometría a partir de exportaciones 2D).
- Arquitectura multi-tenant real: aislamiento de datos por cliente, control de acceso por rol.
- Motor de reglas multi-país, con una capa de localización normativa que permita añadir un país sin reescribir el núcleo.
- Un pipeline de datos que acumula, con consentimiento explícito, el histórico agregable necesario para que el benchmark deje de ser una promesa.

**Riesgos:**
- Que la relación institucional (colegio o aseguradora) no llegue a tiempo — depende de terceros fuera de nuestro control directo.
- Que la expansión a varios países se haga demasiado rápido y diluya el rigor normativo que sostiene toda la confianza del producto.
- Que un actor con más distribución (un fabricante de software BIM) mueva ficha antes en la misma dirección.
- Que el compromiso de garantía/seguro exponga a la empresa a un riesgo financiero real el día que el motor falle en un caso caro — hay que dimensionarlo con disciplina actuarial, no con optimismo de producto.

**Criterios de etapa completada:**
- Al menos un colegio profesional o una aseguradora con acuerdo firmado y activo, no en conversación.
- Cobertura normativa auditada externamente en al menos tres países.
- El chequeo en tiempo real funcionando de forma estable, dentro de al menos un entorno BIM mayoritario, con clientes que pagan por ello de forma continuada.

### Horizonte: 12 meses

**Objetivo:** demostrar con clientes de pago reales — no con una demo — que "vivir dentro del flujo BIM, en equipo, con documentación automática" es un producto que se retiene y se paga, antes de comprometer el resto de la inversión en escalarlo.

**Funcionalidades imprescindibles:**
- Chequeo en tiempo real sobre un subconjunto acotado pero rigurosamente verificado de reglas de alto riesgo — no falta amplitud, sobra la tentación de perseguirla antes de tiempo.
- Multiusuario, roles e historial de proyecto.
- Primera versión de generación de borrador de memoria justificativa.
- Panel de priorización de hallazgos por impacto económico y de plazo.

**Capacidades técnicas necesarias:**
- Integración funcional con al menos un SDK de BIM, en producción.
- Arquitectura multi-tenant con autenticación y aislamiento de datos por cliente.
- Trazabilidad completa de cada hallazgo (quién lo vio, cuándo se corrigió) — la base técnica del futuro "pasaporte de cumplimiento".

**Riesgos:**
- Sobreextender el alcance de reglas antes de tener la capacidad de auditoría que las respalde.
- Que el coste real de construir la integración BIM sea mayor de lo estimado y arrastre el resto del roadmap.
- Perder foco por avanzar en distribución institucional y en producto al mismo tiempo sin equipo suficiente para ambas cosas a la vez.

**Criterios de etapa completada:**
- Clientes de pago reales usando la versión nativa en BIM en producción, no solo el flujo de análisis por archivo.
- Testimonios o métricas que confirmen que "vivir dentro del flujo" se percibe como mejor, no solo como distinto.
- Primera auditoría externa del motor de reglas completada y en condiciones de publicarse.

### Horizonte: 6 meses

**Objetivo:** demostrar con un piloto real, no con una demo interna, que el chequeo en tiempo real dentro de un entorno BIM es técnicamente viable y que arquitectos reales le encuentran valor frente al flujo de trabajo que ya conocen.

**Funcionalidades imprescindibles:**
- Entre 5 y 10 reglas de alto riesgo real funcionando en tiempo real dentro del entorno BIM piloto.
- Multiusuario básico, suficiente para que un piloto de estudio pequeño lo use en equipo.

**Capacidades técnicas necesarias:**
- Primer plugin o integración funcional, en beta cerrada.
- Infraestructura multi-tenant mínima viable.

**Riesgos:**
- Que la integración BIM resulte más compleja de lo estimado y consuma todo el horizonte sin nada utilizable al final.
- Que los estudios piloto no encuentren suficiente valor en una cobertura de reglas todavía reducida frente a la comodidad de un flujo de "subir archivo" con más cobertura ya conocida.

**Criterios de etapa completada:**
- Al menos un estudio piloto usando el chequeo en tiempo real de forma continuada — no una prueba de un día — y dispuesto a dar testimonio de ello.

### Horizonte: 3 meses

**Objetivo:** no construir todavía el producto nativo en BIM — validar con evidencia real que es la apuesta correcta antes de comprometer el grueso de la inversión en construirlo.

**Funcionalidades imprescindibles:**
- Ninguna nueva de cara al cliente. Es, deliberadamente, una fase de validación, no de construcción.

**Capacidades técnicas necesarias:**
- Prueba de concepto técnica de lectura (y, si es viable, escritura) sobre un modelo BIM real — validación de viabilidad, no producto en producción.

**Riesgos:**
- Gastar este tiempo sin disciplina y llegar al horizonte de 6 meses sin una validación clara, arrastrando la incertidumbre a fases mucho más caras de corregir.

**Criterios de etapa completada:**
- Un informe de validación, con evidencia y no con opinión, de que la integración BIM es técnicamente viable y de que arquitectos reales la preferirían al flujo de trabajo actual.

### Horizonte: 1 mes

**Objetivo:** sentar los cimientos de equipo y de cultura que hacen posible todo lo demás — este es el mes en que se decide qué tipo de empresa se está construyendo, no qué se va a construir.

**Funcionalidades imprescindibles:**
- Ninguna.

**Capacidades técnicas necesarias:**
- Ninguna todavía. Es deliberado.

**Riesgos:**
- Precipitarse a construir producto antes de tener claro el equipo fundador y la disciplina de datos, repitiendo exactamente el error de fondo que este mismo ejercicio de visión ha identificado: construir rápido sin haber decidido primero qué tipo de confianza se quiere merecer.

**Criterios de etapa completada:**
- Equipo fundador con la combinación de experiencia real de arquitectura (visado, responsabilidad civil) e ingeniería cerrada, o en proceso avanzado de incorporación.
- Un documento interno de principios de producto redactado y compartido con todo el equipo fundador — empezando por uno no negociable: **nunca se muestra un dato como real si no lo es**, y **ArchMuse nunca sustituye la firma ni la responsabilidad del arquitecto**.
