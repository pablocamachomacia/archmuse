# MOAT_ANALYSIS.md — ArchMuse desde cuatro perspectivas

**Postura de este documento:** estrategia de producto y ventaja competitiva, no ingeniería. No se propone ningún cambio técnico ni de código — solo se ha vuelto a mirar qué hace hoy el producto (motor de reglas, capa de efectos en cadena, generación con IA, visor 3D, sistema de puntuación) para razonar sobre su valor de negocio, no sobre su implementación.

Se analiza ArchMuse desde cuatro voces con intereses distintos y a veces enfrentados:

- **F** — Fundador de una startup SaaS de 100M — piensa en ARR, retención, foso defendible frente a un competidor con capital.
- **A** — Arquitecto con 20 años de ejercicio — piensa en riesgo profesional real, responsabilidad civil, y si le confiaría su firma a esto.
- **I** — Responsable de innovación de un estudio grande — piensa en adopción de equipo, estandarización, integración con lo que ya usan, cómo justificarlo ante dirección.
- **V** — Inversor de venture capital — piensa en TAM, velocidad de replicación por alguien con financiación, y en si esto es un producto o una función de otro producto.

---

## 1. ¿Por qué un arquitecto pagaría todos los meses por ArchMuse?

**A:** Porque hoy ese control de calidad se hace a ojo, o no se hace de forma exhaustiva nunca. Nadie repite a mano, proyecto tras proyecto, 40 comprobaciones normativas distintas sobre cada vivienda de un edificio — ni yo con 20 años de oficio lo hago con esa disciplina. El coste real que evita ArchMuse no es "tiempo de dibujo", es el coste de un rechazo de visado (semanas de retraso, un cliente que pierde confianza) o, peor, el de una responsabilidad civil que aparece años después de firmado el proyecto. Pagaría por poder decir, documentado, que cada proyecto pasó por un control sistemático antes de mi firma — eso es defensa profesional, no comodidad.

**F:** Es exactamente el tipo de dolor que sostiene una suscripción y no un pago único: cada proyecto nuevo necesita su propia validación, así que el problema se repite mes a mes por diseño, no por fricción artificial de precio.

**I:** En un estudio con arquitectos junior y senior, ArchMuse no sustituye criterio, lo estandariza. Hoy la calidad de una revisión CTE depende de quién la haga y de cuánta prisa tenga esa semana. Con esto, la vara de medir es la misma para todo el equipo — y además entrena al junior en el momento, porque cada aviso cita el artículo CTE real, no un "esto está mal" genérico.

**V:** El valor no está en "generar un plano bonito", está en reducir una cola de coste asimétrico: cientos de euros de suscripción frente a miles (o la reputación del estudio) en un rechazo de visado o un litigio. Ese desequilibrio es lo que sostiene precio, no la novedad de la IA.

---

## 2. ¿Qué hace que el producto sea difícil de abandonar?

- **Se convierte en un paso del proceso, no en una herramienta opcional.** Igual que un compilador no es "una ayuda", es el paso obligatorio antes de que el código exista de verdad — en cuanto un estudio institucionaliza "esto se pasa por ArchMuse antes de visado", quitarlo exige rediseñar el proceso de calidad interno, no solo cancelar una suscripción.
- **El historial acumulado de análisis se convierte en memoria institucional del estudio.** Hoy el producto no persiste nada (cada análisis vive solo mientras la pestaña está abierta) — mientras eso se mantenga así, este punto es una promesa, no una realidad. En el momento en que exista un histórico, abandonarlo significa perder la trazabilidad de qué se revisó y por qué en cada proyecto pasado, algo que ningún estudio quiere borrar por decisión unilateral de cambiar de herramienta.
- **El equipo se forma en el lenguaje del producto** (severidad CRITICO/IMPORTANTE/RECOMENDACION, formato impacto/solución) — cambiar de herramienta no es solo migrar datos, es reentrenar el hábito de lectura de todo el estudio.
- **El sistema de puntuación y percentil**, una vez esté respaldado por datos reales de uso, se convierte en el termómetro con el que el estudio mide su propia mejora mes a mes — perderlo es perder la serie histórica de "cómo hemos evolucionado", no solo una función.
- **A:** lo que de verdad me haría no irme es poder decir, ante un cliente o ante un seguro de responsabilidad civil, "este proyecto se validó con un proceso documentado" — ese argumento se pierde en el momento en que dejo de usarlo, y no se puede reconstruir retroactivamente.

---

## 3. ¿Qué puede copiar un competidor en una semana?

- Un parser de DXF que extraiga habitaciones y aplique un puñado de comprobaciones geométricas superficiales (proporción de habitación, área mínima) — hay librerías de código abierto (`ezdxf`, `shapely`) que hacen la mitad del trabajo pesado.
- Un asistente de IA que "comenta" un plano en lenguaje natural — con cualquier LLM comercial de hoy, esto es una tarde de trabajo de *prompt engineering*, no un producto.
- Un panel visual con colores de severidad y una lista de problemas — maquetación, no ingeniería de dominio.
- Un visor 3D básico sobre geometría generada — `three.js` tiene ejemplos públicos que cubren el 80% de esto.

**V:** esto es justo lo que un competidor bien financiado enseñaría en un pitch para levantar ronda — y es la razón por la que "tenemos IA" no puede ser el argumento de venta. Cualquiera lo tiene en una semana.

---

## 4. ¿Qué necesitaría seis meses para copiar?

- Un motor de reglas realmente amplio y **correcto** sobre varios Documentos Básicos del CTE (SI, SUA, HS, HE, HR) más LOE y decretos autonómicos de habitabilidad, con umbrales que varíen de verdad por tipología y por zona climática — no basta con conocer la norma, hay que iterar contra planos reales y descubrir (como ya le pasó a este propio proyecto) que la geometría real de un DXF tiene huecos de hasta 0,38m entre muros que rompen cualquier comprobación ingenua de adyacencia.
- Un sistema de puntuación internamente coherente, donde dos formas independientes de medir calidad (cumplimiento normativo y calidad de diseño) lleguen al mismo veredicto sobre el mismo proyecto — eso solo se consigue validando contra casos reales, no diseñando en abstracto.
- Una capa de calidad de diseño (circulación, proporciones, jerarquía espacial) que aporte señal real y no ruido — requiere calibrar contra el criterio de arquitectos de verdad, no solo contra la letra de la norma.

**A:** esto es la parte que un competidor con dinero pero sin arquitectos en el equipo fundador va a hacer mal durante mucho más de seis meses — conozco herramientas "de cumplimiento" hechas por ingenieros de software puros, y se nota en la primera hora de uso que nunca han defendido un proyecto ante un visado.

---

## 5. ¿Qué necesitaría años para copiar?

- **Confianza institucional.** Que un arquitecto se juegue su firma y su responsabilidad civil en lo que dice la herramienta no se compra con una campaña de marketing — se gana con años de resultados correctos y de admitir abiertamente lo que la herramienta *no* puede verificar todavía (algo que ArchMuse ya hace hoy, de forma explícita, con su lista de "limitaciones").
- **Un percentil comparativo real**, construido sobre datos agregados de cientos de proyectos analizados de verdad por distintos estudios — hoy esa tabla está inventada (tres puntos de calibración escritos a mano); convertirla en un dato real requiere volumen de uso real, que solo se consigue con tiempo y con clientes, no con ingeniería.
- **Cobertura mantenida del mosaico normativo español** — 17 comunidades autónomas, decretos de habitabilidad distintos, variaciones municipales de urbanismo. No es un problema que se resuelva una vez: hay que mantenerlo actualizado para siempre, y eso compone con el tiempo a favor de quien empezó antes.
- **Un motor de coste/urgencia (`chain_effects`) calibrado contra costes de construcción reales** por región — hoy son estimaciones razonadas pero no validadas contra datos reales de obra; convertirlas en cifras fiables exige partenariados o años de calibración con proyectos reales ejecutados.
- **Relaciones institucionales**: colegios de arquitectos, aseguradoras de responsabilidad civil, fabricantes de software BIM — canales de distribución y de credibilidad que se construyen con relación humana sostenida, no con una API.

**F:** esto es lo único que de verdad protege una startup de 100M frente a un competidor con más capital: no la tecnología en sí, sino todo lo que solo se puede construir viviendo el problema durante años.

---

## 6. ¿Qué funcionalidades actuales aportan poco valor aunque sean complejas?

- **El visor 3D navegable.** Es la pieza más vistosa para una demo (paseo virtual, cámaras, panel de plantas — trabajo real de varias iteraciones), pero hoy no está conectado al motor de hallazgos: no resalta los problemas detectados sobre el propio edificio en 3D, solo los muestra en el plano SVG plano. Es una demostración de capacidad técnica, no una herramienta de validación todavía.
- **El percentil comparativo.** Tiene detrás una lógica matemática cuidada (interpolación entre puntos de calibración, categorías ponderadas), pero al no estar respaldado por datos reales, hoy aporta la *apariencia* de inteligencia de mercado sin el contenido — complejidad invertida en un número sin señal real.
- **El flujo de línea de comandos heredado (CLI).** Sigue mantenido y sigue funcionando, pero ya no recibe las funcionalidades nuevas (circulación, calidad espacial, efectos en cadena, puntuación) — es inversión de ingeniería real sirviendo a un único usuario interno.
- **La comprobación de "compartimentación contra incendios" por solape geométrico.** Cita un artículo real del CTE (DB-SI-3) y suena autorizada, pero es explícitamente un proxy geométrico — no verifica resistencia real al fuego de los muros. Bien explicado, es una comprobación de sanidad útil; mal comunicado, puede sonar a garantía de cumplimiento que no es.

**I:** esto es justo lo que un responsable de innovación tiene que vigilar al evaluar cualquier herramienta con IA — que lo espectacular en la demo (el 3D, el número de percentil) no sea, sin querer, lo que menos protege a mi equipo el día que algo sale mal.

---

## 7. ¿Qué parte del producto es la auténtica "joya de la corona"?

**El motor de reglas normativas** — no como archivo de código, sino como el conjunto de decisiones de dominio que contiene: qué articulado del CTE aplica a qué situación, cómo varían los umbrales por tipología y zona climática, y sobre todo, cómo traducir la geometría imperfecta de un DXF real (huecos entre muros, polígonos de agrupación que no son habitaciones reales) en un hallazgo que se pueda citar con seguridad ante un visado.

Es la única parte del producto que **no se puede comprar con financiación**, solo con tiempo y con exposición a planos reales. El resto — interfaz, IA narrativa, visor 3D, exportación a PDF — es replicable por cualquier equipo de ingeniería competente en semanas o meses. Esto no.

---

## 8. Si solo pudiéramos conservar un único módulo, ¿cuál sería y por qué?

El motor de reglas — pero la respuesta correcta no es "conservad el archivo", es **"conservad el proceso que lo hizo así"**: los umbrales calibrados por tipología y zona, los proxies geométricos validados contra fallos reales (el descarte de polígonos contenedores, la tolerancia de hueco entre muros), las decisiones documentadas de qué se puede verificar y qué no.

Un competidor que robara literalmente ese código sin el proceso que lo produjo empezaría a desviarse del criterio correcto en cuanto apareciera el primer DXF con una convención de capas distinta, o el primer municipio con una normativa que no encaja en las tablas actuales — porque no tendría el hábito de validación empírica que hoy sostiene ese módulo. El activo real no es el texto del código, es la disciplina de cómo se construyó.

**A:** dicho de otra forma — lo que hace confiable esta pieza no es que "sepa" la norma, es que alguien ya se equivocó con ella contra un plano real y lo corrigió. Eso no se copia leyendo el código, se copia repitiendo los mismos errores.

---

## 9. ¿Qué ventaja competitiva todavía no estamos explotando?

- **Cerrar el círculo generar → evaluar → corregir → volver a evaluar.** Hoy "analizar un plano" y "generar un proyecto con IA" son dos flujos separados que comparten motor pero no conversan entre sí. El verdadero salto de producto es que, ante un hallazgo, el sistema pueda proponer y regenerar solo la parte afectada del proyecto y volver a evaluarla al instante — ningún competidor que solo "revise" planos (sin generar) puede replicar esto, y ningún competidor que solo "genere" planos (sin evaluar con este rigor) tampoco.
- **Convertir los efectos en cadena (coste estimado + urgencia) en un argumento dirigido al que paga la obra, no solo al que la dibuja.** Hoy esa capa habla en el idioma del arquitecto. Agregada a nivel de proyecto completo, es un argumento directo para un promotor o un inversor inmobiliario: "este proyecto tiene un riesgo estimado de X€ en correcciones antes de que empiece la obra" — eso abre un comprador nuevo, no solo un usuario nuevo.
- **La honestidad sobre las propias limitaciones no se está usando como argumento de marca.** Hoy vive en un aviso técnico dentro del informe. Es, con diferencia, el argumento más creíble frente al escepticismo natural de un arquitecto senior hacia "otra herramienta de IA que promete cumplir la norma" — y no se está diciendo en ningún sitio de cara al mercado.
- **No hay ningún canal institucional explotado todavía**: colegios de arquitectos, aseguradoras de responsabilidad civil, fabricantes de software BIM. Cualquiera de los tres podría distribuir o avalar ArchMuse — hoy no se ha hablado con ninguno.
- **El propio efecto de red del percentil comparativo no ha empezado a acumularse**, porque hoy no hay ningún registro histórico de análisis. El reloj de "cuantos más estudios lo usen, más valioso es el benchmark para todos" ni siquiera ha arrancado.

**V:** de estos cinco, el que de verdad cambia la categoría del negocio es el primero — cerrar el círculo generar-evaluar-corregir convierte ArchMuse de "checker" a "copiloto de diseño", y ese es un mercado con un TAM completamente distinto.

---

## 10. ¿Qué debería convertirse en la identidad de ArchMuse?

No "una herramienta con IA para revisar planos". Esa categoría es genérica, se satura rápido y compite en precio.

La identidad correcta es la de **infraestructura de control de riesgo profesional**: el paso obligatorio, documentado y de confianza que cualquier proyecto residencial serio atraviesa antes de visado — el mismo lugar que ocupa un corrector ortográfico profesional para un texto, o una batería de tests automatizados antes de publicar software: no es una función más, es *el paso que nadie se salta*.

Concretamente: ArchMuse no vende "análisis con inteligencia artificial". Vende **la certeza de que un proyecto se ha revisado de forma sistemática, documentada y defendible antes de que un error cueste dinero, tiempo o responsabilidad legal.** La IA es cómo se construye eso por dentro; no es lo que se vende por fuera.

---

## Estrategia: de "herramienta con IA" a "la plataforma imprescindible para validar un proyecto arquitectónico"

*(Estrategia de producto y ventaja competitiva. Ningún punto de esta sección implica cambios técnicos — son decisiones de posicionamiento, modelo de negocio, secuencia de mercado y comunicación.)*

### Pilar 1 — Reposicionar la categoría antes que la función

Dejar de comunicar "análisis con IA de planos DXF" y empezar a comunicar "control de calidad y de riesgo antes de visado". La IA se menciona como el cómo, nunca como el qué se vende. El mensaje central deja de ser "más rápido" y pasa a ser "más seguro" — el ahorro de tiempo es un efecto secundario, no la promesa principal. Esto cambia también a quién se le vende: no es una herramienta de productividad para el arquitecto que dibuja, es una póliza de calidad para el estudio que firma.

### Pilar 2 — Convertir la transparencia en el argumento de venta principal

Hoy la lista de "qué no puede verificar todavía" el sistema vive enterrada en un informe técnico. Debe convertirse en la pieza central del discurso comercial: "te decimos exactamente qué hemos comprobado y qué no, para que decidas tú, no una caja negra que promete cumplimiento total". Es el argumento más difícil de replicar rápido por un competidor centrado en marketing de IA, porque exige admitir limitaciones en vez de exagerar capacidades — y es precisamente lo que un arquitecto con 20 años de oficio, escéptico por experiencia, necesita oír para empezar a confiar.

### Pilar 3 — Empezar a acumular el activo de datos, aunque el producto de hoy no lo necesite para funcionar

El percentil comparativo y el efecto de red que puede generar solo existen si hay un historial real de proyectos analizados por muchos estudios distintos a lo largo del tiempo. Cuanto más tarde se empiece a acumular ese histórico, más tarde arranca el único foso de este documento que se compone con el tiempo en vez de con el esfuerzo puntual. La secuencia de mercado debe priorizar volumen de análisis reales cuanto antes, incluso por delante de monetización agresiva al principio — cada estudio adicional que analiza un proyecto real hoy es un ladrillo de un foso que un competidor no puede comprar, solo esperar a que se construya en otro sitio antes que en el suyo.

### Pilar 4 — Cerrar el círculo generar-evaluar-corregir como el verdadero producto

La estrategia de producto a medio plazo debe dejar de tratar "analizar un DXF" y "generar un proyecto con IA" como dos funciones paralelas del mismo motor, y empezar a venderlas como una sola cosa: un ciclo iterativo de diseño asistido y validado en el mismo movimiento. Es la diferencia entre "una herramienta que te dice qué está mal" y "un copiloto con el que diseñas ya sabiendo que va a cumplir" — ese reposicionamiento cambia el tamaño del mercado direccionable, porque deja de competir solo con otros checkers de cumplimiento y empieza a competir con la fase de diseño conceptual en sí misma.

### Pilar 5 — Diversificar a quién se le vende, no solo qué se vende

El comprador de hoy es el arquitecto individual o el estudio pequeño. La capa de efectos en cadena (coste estimado, urgencia) ya habla, sin saberlo, el idioma de un segundo comprador: el promotor o el inversor inmobiliario que necesita cuantificar el riesgo de un proyecto antes de comprometer capital. Agregada a nivel de proyecto completo ("riesgo estimado total antes de obra: X€, Y días de retraso probable"), esa misma capa técnica se convierte en un producto de due-diligence inmobiliaria — un canal de venta distinto, con un ticket medio distinto, sin construir nada nuevo desde cero conceptualmente.

### Pilar 6 — Construir distribución institucional, no solo adquisición directa

Los tres canales que ningún competidor nuevo puede replicar rápido son relación, no tecnología: colegios de arquitectos (como recomendación o integración con el proceso de visado), aseguradoras de responsabilidad civil profesional (como condición o descuento por uso documentado), y fabricantes de software BIM (como integración o partenariado de distribución). Cualquiera de los tres convierte a ArchMuse de "una herramienta más que un arquitecto puede probar" a "algo que su colegio, su aseguradora o su propio software de cabecera ya le indica que use" — la diferencia entre vender y ser prescrito.

### Pilar 7 — Usar la profundidad normativa como cuña de entrada, no como techo

La estrategia de expansión de cobertura normativa (más comunidades autónomas, más municipios, más Documentos Básicos del CTE) no debe tratarse como una tarea de producto más — es, en sí misma, la estrategia de expansión geográfica de la empresa. Cada normativa autonómica añadida con rigor real es simultáneamente una mejora de producto y una entrada a un nuevo mercado regional, con la ventaja de que un competidor que quiera replicarlo tiene que rehacer el mismo trabajo de validación región por región, mientras el histórico de ArchMuse ya compone a su favor en las regiones donde empezó antes.

### Secuencia recomendada (orden de mercado, no de ingeniería)

1. Consolidar la confianza y el discurso de transparencia con los primeros estudios pequeños/autónomos — son el comprador natural de hoy y el que valida si el argumento de riesgo/responsabilidad civil realmente convierte en pago recurrente.
2. Extender a estudios medianos con equipos, vendiendo el ángulo de estandarización y formación de junior (el comprador que valora esto es el responsable de innovación, no el arquitecto individual).
3. Iniciar conversación con al menos un canal institucional (colegio profesional o asegurador) en paralelo, no después — son relaciones que tardan en madurar y deben empezar mientras el producto todavía se está afinando con los primeros dos segmentos.
4. Solo cuando exista volumen real de análisis acumulado, activar el percentil comparativo con datos reales y empezar a comunicarlo como diferencial de marca — hacerlo antes, con datos inventados, es gastar la credibilidad que el Pilar 2 se ha propuesto construir.
