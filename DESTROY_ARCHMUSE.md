# DESTROY_ARCHMUSE.md — Plan de guerra de un competidor con 50M€

**Quién habla en este documento:** el fundador de una startup nueva, con 50M€ de financiación, sin ningún vínculo con ArchMuse, cuyo único objetivo es que ArchMuse deje de existir como negocio en 24 meses. No hay lealtad al proyecto en este documento. Si algo de lo que sigue duele, es porque está diseñado para doler — ese es el encargo.

**Regla de honestidad:** cada ataque de este documento se apoya en una debilidad real y verificada de ArchMuse (código, arquitectura, o decisión de producto), no en un ataque genérico de manual de startups. Donde el ataque es especulativo (sobre el mercado, no sobre el producto), se dice explícitamente.

---

## 1. ¿Cómo construiría un producto claramente superior?

Con tres decisiones que ArchMuse no ha tomado y que, con 50M€, puedo tomar desde el día uno:

**a) No seríamos una herramienta a la que se sube un archivo. Viviríamos dentro de Revit y ArchiCAD.** ArchMuse obliga a exportar a DXF, subir el archivo, esperar y leer un informe aparte. Nosotros comprobaríamos el cumplimiento normativo **mientras el arquitecto dibuja**, dentro del mismo software que ya usa ocho horas al día — como un corrector ortográfico en tiempo real, no como un servicio de corrección que se manda por email y se espera. Esto no es una mejora de UX, es un cambio de categoría: convertimos "otra pestaña que hay que acordarse de abrir" en "algo que ya está encendido".

**b) No trabajaríamos desde geometría reconstruida de un DXF. Trabajaríamos desde el modelo BIM real.** Esto es el ataque más importante de todo este documento y vuelvo a él en la pregunta 3.

**c) No inventaríamos ningún dato.** Desde el primer cliente, cada comparación, cada percentil, cada estimación de coste que mostremos vendrá marcada como "estimado" hasta que tengamos volumen real para calcularla de verdad — y, mientras tanto, no mostraremos ningún percentil en absoluto. Es más lento salir al mercado con esta disciplina, pero es la única forma de que, el día que alguien nos audite el dato, no encontremos lo que se puede encontrar hoy dentro de ArchMuse.

---

## 2. ¿Qué partes de ArchMuse ignoraría por completo?

- **El visor 3D navegable.** Es la parte más cara de construir (varias iteraciones documentadas: cámaras, modo paseo, panel de plantas) y, tal como está, no está conectada a los hallazgos de cumplimiento — no resalta los problemas sobre el edificio en 3D, solo en el plano SVG. Es una demo bonita, no una herramienta de validación. No la construiría hasta tener el core del producto ganado; cuando la construya, la construiré ya conectada a los hallazgos, algo que ArchMuse todavía no ha hecho.
- **El flujo de línea de comandos heredado.** Ni existiría. Es inversión de ingeniería real sirviendo, hoy, a un único usuario interno del propio equipo que lo construyó.
- **La arquitectura de "un único archivo HTML de 5.000 líneas".** Ni por un segundo. Con 50M€ contrato un equipo de frontend desde el día uno y construyo con una base de componentes real. ArchMuse no lo hizo porque empezó como el proyecto de una sola persona — nosotros no tenemos esa excusa ni esa limitación.
- **La persecución de "40 reglas normativas" como métrica de vanidad.** No competiría por tener más reglas que ArchMuse. Competiría por tener las 10-15 reglas de mayor riesgo real (las que de verdad provocan un rechazo de visado o una responsabilidad civil) con una fiabilidad absolutamente verificada y auditada externamente, antes de perseguir cobertura amplia. Amplitud sin fiabilidad no vale nada la primera vez que un arquitecto encuentra un fallo.
- **El parser de geometría DXF hecho a mano.** Esto merece su propia pregunta — la 3, porque es el ataque central.

---

## 3. ¿Qué haría radicalmente diferente?

**Evitaría por completo el problema que ArchMuse ha tenido que resolver a base de fuerza bruta: reconstruir habitaciones a partir de polígonos de un DXF exportado.**

El documento de análisis de foso de ArchMuse (que he leído, porque cualquier competidor serio audita lo que puede) señala como "joya de la corona" el trabajo de reconocer qué polígono de un DXF es una habitación real y cuál es un polígono de agrupación que hay que descartar, y de tolerar que las habitaciones reales dejen un hueco de hasta 0,38m entre sí por el grosor del muro antes de considerarlas "adyacentes". Eso no es una joya. **Es la cicatriz de haber elegido trabajar desde el formato equivocado.**

Un modelo BIM real (Revit, ArchiCAD, cualquier cosa que exporte IFC) ya tiene las habitaciones como objetos de primera clase, con sus límites, su adyacencia real y su altura libre modelada — no hay que *adivinar* nada de eso a partir de líneas y colores de un plano 2D exportado. Si construimos desde IFC/BIM en vez de desde DXF, todo el trabajo que ArchMuse presenta como su activo más difícil de replicar **deja de ser necesario, porque el problema que resuelve no existe en nuestro enfoque.**

Esto es, con diferencia, el ataque más serio de todo este documento: no se trata de construir mejor lo mismo que hace ArchMuse, se trata de que la mitad de lo que hace ArchMuse es trabajo compensatorio por partir de datos pobres, y con más presupuesto (y sin la carga de un producto ya construido alrededor del DXF) no tenemos que compensar nada — atacamos el problema desde donde de verdad vive la información.

*(Matiz honesto: no todos los estudios españoles trabajan en BIM todavía; muchos siguen en AutoCAD/DXF puro, sobre todo estudios pequeños. No abandonaríamos el DXF de un día para otro — lo trataríamos como una vía de entrada de segunda categoría mientras el producto se construye nativamente alrededor de BIM/IFC, para no cerrarnos el mercado que hoy todavía no ha migrado.)*

**Segundo cambio radical: no venderíamos confianza, la compraríamos.** El análisis de foso de ArchMuse asume que la confianza institucional "no se compra, se gana con años". Eso es cierto para una startup sin capital. No es cierto para nosotros. Con 50M€ podemos:
- Contratar una auditoría externa reconocida (una consultora de prestigio en el sector AEC) que certifique públicamente la precisión de nuestro motor de reglas.
- Ofrecer una **garantía respaldada por seguro**: si nuestra herramienta no detecta un incumplimiento del CTE que le cuesta dinero a un cliente, lo cubrimos. Ningún competidor sin capital puede ofrecer esto, y es el argumento que neutraliza de un golpe la ventaja de "años de confianza acumulada" que un incumbente más antiguo cree tener.
- Fichar como asesores o caras visibles a arquitectos de prestigio reconocido en el sector, no solo contratar ingenieros.

Comprar velocidad de confianza es exactamente lo que el capital permite hacer que el tiempo, por sí solo, tarda años en construir.

**Tercer cambio radical: el producto no termina en el visado.** ArchMuse cubre el momento de diseño. Nosotros cubriríamos todo el ciclo: diseño (en tiempo real, dentro del BIM), documentación de visado (generación automática de la memoria justificativa citando los artículos CTE reales, no solo un informe de hallazgos), y verificación en obra (una app de campo que compara lo construido contra lo proyectado y aprobado). Cuanto más largo el ciclo que cubrimos, más caro es para un cliente salirse de nuestro ecosistema.

---

## 4. ¿Qué frustraciones de los arquitectos seguimos sin resolver?

Ni nosotros ni ArchMuse, siendo honesto:

- **El informe llega después, nunca durante.** El diseño y la validación siguen siendo dos pasos separados en el tiempo en cualquier herramienta de este tipo hoy, incluida la nuestra en su primera versión.
- **Nadie automatiza la memoria justificativa real que hay que entregar en el visado** — el documento textual, con cita de artículos, que exige el colegio de arquitectos. Detectar el problema es la mitad del trabajo; redactar la justificación normativa formal es la otra mitad, y sigue siendo manual en todas partes.
- **La coordinación entre disciplinas** (estructura, instalaciones, arquitectura) sigue sin resolverse — un proyecto puede cumplir arquitectónicamente y fallar por un choque con la instalación eléctrica o con la estructura, y ninguna herramienta centrada solo en arquitectura lo ve.
- **Rehabilitación y patrimonio siguen siendo el caso más difícil y el más desatendido** — la normativa de edificios existentes tiene excepciones y casuística mucho más compleja que la de obra nueva, y es precisamente donde una herramienta automática es más arriesgada y menos fiable.
- **Nadie cierra el círculo con la fase de obra.** El proyecto se valida sobre el papel; nadie verifica sistemáticamente que lo construido coincide con lo aprobado. Esa frustración — "¿lo que se construyó de verdad es lo que se firmó?" — es más grande que la de validar un plano, y sigue completamente abierta.

---

## 5. ¿Qué haría que un cliente abandonara ArchMuse?

Con brutal honestidad, ordenado de más a menos probable:

1. **Descubrir que un resultado de cumplimiento estaba mal.** He verificado (leyendo el propio código, no especulando) que en el flujo de subir un DXF real, ArchMuse hoy **no aplica correctamente la tipología ni la zona climática seleccionadas por el arquitecto** — el motor evalúa siempre con los valores por defecto, sin importar lo que se indique en el formulario. Un arquitecto que suba un proyecto unifamiliar en Madrid y compare mentalmente el resultado con lo que sabe que debería aplicar (zona D, exigencias distintas a plurifamiliar) puede notar que "esto no está diferenciando nada" — y en el momento en que un profesional que se juega su firma detecta un hallazgo normativo incorrecto o inconsistente, no vuelve a confiar en el resto de hallazgos del informe, aunque el 95% restante sea correcto. Es el tipo de fallo que no se perdona una segunda vez.
2. **Necesitar trabajar en equipo y no poder.** Sin usuarios, sin roles, sin historial compartido, cualquier estudio que crezca de "un arquitecto" a "un equipo" choca con un techo de cristal inmediato. En el momento en que exista una alternativa con colaboración real, ese cliente se va sin mirar atrás.
3. **Descubrir que el percentil comparativo no es un dato real.** Es una tabla de tres puntos de calibración escrita a mano, presentada como una comparación de mercado. Un cliente que pregunte "¿de dónde sale este número?" y reciba una respuesta poco convincente pierde la confianza en todo el sistema de puntuación de golpe, no solo en el percentil.
4. **Un competidor que viva dentro de su propio Revit/ArchiCAD.** El coste de exportar, subir y esperar deja de ser aceptable en cuanto exista una alternativa que no lo exija.
5. **Precio sin crecimiento de valor percibido**, en cuanto el factor sorpresa de "esto usa IA" se normalice en el sector (y se normalizará rápido) y el cliente empiece a juzgar la herramienta solo por lo que hace, no por cómo suena.

---

## 6. ¿Qué empresa podría convertirse en nuestro mayor competidor (o en el de ArchMuse)?

Honestidad sin filtro: **la amenaza más grande no somos nosotros, es Autodesk.**

- **Autodesk (Revit, y sobre todo Autodesk Forma)** ya tiene la distribución — todos los arquitectos que importan ya usan su software a diario — y ya está invirtiendo en análisis de viabilidad y cumplimiento generativo integrado. Si Autodesk decide que "comprobación de normativa en tiempo real" es una función nativa de Revit en vez de un producto aparte, tanto ArchMuse como cualquier startup que ataque desde fuera pierden de la noche a la mañana la razón de existir como herramienta independiente. Esto no es una posibilidad remota: es la trayectoria natural de cualquier plataforma dominante con presupuesto de I+D, y ya se mueve en esa dirección con sus herramientas de análisis generativo.
- **Nemetschek/Graphisoft (ArchiCAD)**, con fuerza particular en el mercado europeo, tiene el mismo incentivo y la misma capacidad.
- **Startups de diseño generativo con financiación real y ya activas en el mercado** (categorías como viabilidad de solar y diseño paramétrico con reglas urbanísticas incorporadas) — esta categoría ya existe hoy a nivel internacional; no es una amenaza futura, es una amenaza presente que todavía no se ha especializado a fondo en el detalle normativo español (CTE artículo por artículo), pero que tiene el capital y el producto base para hacerlo si decide entrar.
- **Los propios colegios de arquitectos, si alguien les ofrece construir esto gratis a cambio de exclusividad.** El propio análisis de foso de ArchMuse identifica a los colegios como el canal institucional más valioso todavía sin explotar. Es exactamente el mismo canal en el que un competidor con capital puede entrar primero — financiar o subvencionar una herramienta oficial del colegio profesional convierte a ArchMuse de "la herramienta a probar" en "la alternativa a la que ya usa mi colegio", de un plumazo.

---

## 7. ¿Qué tecnología podría dejar obsoleto este enfoque por completo?

- **Comprobación de normativa nativa dentro del software BIM.** Ya cubierto en la pregunta 3 y 6 — es el riesgo existencial real, no una hipótesis lejana.
- **Modelos de IA capaces de razonar directamente sobre un modelo BIM completo (geometría + metadatos) sin ningún motor de reglas programado a mano.** Hoy el enfoque de ArchMuse (y el nuestro, en gran parte) todavía depende de reglas codificadas explícitamente. Si un modelo de fundación mejora lo suficiente como para leer un modelo BIM y el texto íntegro del CTE y razonar el cumplimiento de forma fiable sin reglas programadas artesanalmente, gran parte del trabajo de ingeniería de ambos (el nuestro y el de ArchMuse) se convierte en una capa fina sobre una capacidad genérica de terceros — y en ese escenario, ninguno de los dos tiene ventaja real; gana quien tenga mejor distribución, no quien tenga mejores reglas escritas a mano.
- **Estándares de datos abiertos de cumplimiento normativo** (normativa codificada de forma legible por máquina, publicada oficialmente por el propio regulador) — si algún día el Ministerio o los colegios publican el CTE en un formato estructurado y verificable oficialmente, la ventaja de "hemos codificado la norma nosotros mismos con cuidado" desaparece, porque deja de ser trabajo diferencial y pasa a ser un dato público que cualquiera puede consumir igual de bien.

---

## 8. ¿Qué decisiones tomadas hoy parecerán equivocadas dentro de tres años?

Hablo de las decisiones de ArchMuse, porque son las que puedo auditar con datos reales — y varias de ellas las cometeríamos también nosotros si no las evitáramos deliberadamente:

- **Haber construido el foso alrededor de la geometría DXF en vez de alrededor de BIM/IFC.** Dentro de tres años, si el mercado se mueve hacia BIM nativo (y se está moviendo), ese trabajo — hoy presentado como el activo más valioso del proyecto — puede convertirse en la razón por la que el producto se queda estructuralmente atado a un formato de entrada en declive.
- **No haber empezado a acumular ningún historial de análisis desde el primer día.** El efecto de red del percentil comparativo, identificado por el propio proyecto como su ventaja compuesta a largo plazo, no ha empezado a construirse todavía porque no hay persistencia. Cada mes sin ese dato acumulándose es un mes de ventaja de red que un competidor que empiece a acumularlo antes se queda para siempre — el efecto de red no se puede recuperar retroactivamente.
- **Haber apostado el diferencial de "coste estimado y urgencia" (la pieza con más potencial comercial, según el propio análisis del proyecto) sobre cifras no validadas contra datos reales de obra**, en vez de buscar un socio de datos de coste real desde el principio. Dentro de tres años, si un competidor entra con coste calibrado de verdad (aunque sea con menos reglas normativas), gana la conversación con el comprador que de verdad firma cheques — el promotor — de la que ArchMuse todavía no ha empezado a ocuparse en serio.
- **Haber construido primero para el arquitecto individual y no para el estudio o la institución.** Es una decisión de secuenciación defendible para arrancar, pero si tres años después ArchMuse sigue sin colaboración de equipo real, quien construya eso desde el principio se queda con todo el segmento de estudios medianos y grandes sin oposición.
- **No haber hablado con ningún colegio profesional ni aseguradora todavía.** Cada mes que pasa sin iniciar esa relación es un mes en el que un competidor con más presupuesto puede llegar antes a la misma conversación y cerrar la puerta.

---

## 9. ¿Qué producto construiría si empezara desde cero hoy?

No un "verificador de planos con IA". Construiría **la capa de cumplimiento normativo en tiempo real, nativa dentro de Revit y ArchiCAD**, que:

- Comprueba el cumplimiento mientras se dibuja, no después de exportar.
- Trabaja sobre el modelo BIM real (IFC), sin necesidad de reconstruir habitaciones a partir de geometría 2D.
- No enseña ningún dato comparativo hasta tener volumen real que lo respalde — y lo comunica así, activamente, como argumento de confianza.
- Genera automáticamente el borrador de la memoria justificativa de visado, no solo un listado de hallazgos.
- Se extiende de fábrica más allá de España (arquitectura pensada desde el primer día para poder incorporar normativa de otros países, no atada a una única regulación nacional).
- Ofrece garantía respaldada por seguro sobre los hallazgos críticos desde el lanzamiento — comprando confianza con capital en vez de esperar a ganarla con años.
- Está pensado para el estudio y el equipo desde la primera línea de producto, no añadido después.
- Cubre diseño, documentación de visado y verificación en obra como un único ciclo, no como una herramienta que termina en el momento de dibujar.

---

## Hoja de ruta de 24 meses para derrotar a ArchMuse

### Meses 0-3 — Cimientos que ArchMuse no puede replicar rápido
- Contratar un equipo mixto: arquitectos con experiencia real en visado y responsabilidad civil junto a ingenieros — no solo perfil técnico, exactamente el hueco que un competidor construido por un único desarrollador no puede llenar de la noche a la mañana.
- Empezar en paralelo, no en secuencia: (1) el esqueleto del plugin nativo para Revit/ArchiCAD, (2) las primeras conversaciones con al menos un colegio de arquitectos y una aseguradora de responsabilidad civil, y (3) la búsqueda de un socio de datos de coste de construcción real para no repetir el error del percentil inventado.
- Arquitectura de datos pensada desde el primer commit para acumular historial de cada análisis — el reloj del efecto de red empieza a correr desde el día uno, no como un añadido posterior.

### Meses 3-6 — El golpe de distribución
- Lanzar una primera versión del plugin embebido en Revit/ArchiCAD con comprobación en tiempo real de las 10-15 reglas normativas de mayor riesgo real (no las 40 de ArchMuse — las que de verdad importan), verificadas y auditadas externamente antes del lanzamiento.
- Multi-usuario, roles y proyectos compartidos desde el primer día — atacar directamente el techo de cristal que hoy bloquea a ArchMuse en cuanto un cliente crece de un arquitecto a un equipo.
- Cerrar el primer piloto institucional (colegio o aseguradora), aunque sea regional y pequeño — el objetivo no es el volumen todavía, es tener la primera credencial institucional que ArchMuse no tiene.

### Meses 6-12 — Comprar la confianza que el tiempo todavía no nos ha dado
- Publicar una auditoría externa independiente de la precisión del motor de reglas, con nombre y prestigio reconocible detrás.
- Lanzar la garantía respaldada por seguro sobre hallazgos críticos — el argumento comercial que ningún competidor sin capital puede igualar.
- Escalar la cobertura normativa con el equipo de arquitectos-consultores contratado en el mes 0, con disciplina de ingeniería (pruebas automatizadas desde el primer bloque de reglas, evitando desde el origen el techo de mantenibilidad que ya limita el ritmo de crecimiento del motor de ArchMuse).
- Empezar a vender directamente a estudios medianos con el argumento de estandarización de equipo — el comprador que ArchMuse todavía no ha empezado a atender en serio.

### Meses 12-18 — Ampliar el terreno de juego
- Publicar el primer benchmark comparativo **con datos reales agregados**, explícitamente contrastado como "datos reales, no estimaciones" — un ataque directo y honesto a la práctica común del sector (incluida ArchMuse) de mostrar comparativas sin datos reales detrás.
- Expandir a un segundo y tercer país (empezando por mercados con marcos regulatorios similares o traducibles), aprovechando que el equipo y la arquitectura de producto se diseñaron multi-país desde el mes 0 — mientras un competidor centrado solo en España sigue limitado a ese único mercado.
- Lanzar la primera versión de verificación en obra (app de campo comparando lo construido contra lo aprobado) — empezar a cubrir un ciclo de vida del proyecto que ningún competidor centrado solo en fase de diseño cubre todavía.

### Meses 18-24 — Cerrar el cerco
- Usar la ventaja de capital para una estrategia de precio agresiva dirigida específicamente al segmento de arquitecto individual/estudio pequeño — el cliente natural de un competidor sin nuestros recursos —, subvencionando o regalando el acceso básico mientras el ingreso real viene de contratos institucionales y de estudios grandes.
- Ofrecer migración asistida y garantías de continuidad a clientes de herramientas más pequeñas y menos capitalizadas del sector.
- Consolidar el benchmark de datos reales como referencia reconocida del sector — con volumen suficiente, licenciarlo o publicarlo como informe de industria, convirtiéndolo en un activo de marca más allá del propio producto.
- Para entonces, cualquier competidor que siga dependiendo de exportar-subir-esperar sobre geometría DXF reconstruida a mano, sin colaboración de equipo, sin respaldo institucional y sin datos reales detrás de sus comparativas, ya no compite en el mismo mercado que nosotros — compite por lo que quede de un segmento que ya hemos dejado de considerar el centro del negocio.
