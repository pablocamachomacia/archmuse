# ARCHITECTURAL_MISTAKES.md

**Propósito:** la mayor base de conocimiento de errores reales de diseño arquitectónico que ArchMuse pueda tener — no una lista de incumplimientos normativos redactada de nuevo, sino el catálogo de **cómo y por qué un arquitecto se equivoca de verdad**, con su consecuencia, su gravedad, su frecuencia real, cómo detectarlo, evitarlo y corregirlo. Sin código, como el resto de la serie.

**Metodología de construcción, dicha una vez para que el catálogo no parezca una lista arbitraria:** los 306 errores de este documento no se han generado por asociación libre — se han derivado sistemáticamente de las capas de conocimiento que la serie ya fijó: los 14 dominios de `BRAIN_ARCHITECTURE.md` (categorías 1-11, 13), los 20 efectos en cadena empíricos de `CHAIN_REASONING.md` (categoría 12), los 9 ejes de `FUNCTIONAL_RELATIONS.md` (categoría 15), los 14 principios de `ARCHITECTURAL_PRINCIPLES.md` (categoría 16), y los bugs reales ya confirmados de `evaluator.py`/`app.py` documentados en `TECH_REVIEW.md` (citados explícitamente donde un error de esta lista es, literalmente, ese bug — no una analogía). Esto tiene una consecuencia importante: este catálogo no es una fuente de conocimiento nueva independiente del resto de la serie — es su reverso, la misma arquitectura de conocimiento leída desde el ángulo de "qué pasa cuando se hace mal" en vez de "qué hay que saber para hacerlo bien".

**Referencias obligatorias:** `BRAIN_ARCHITECTURE.md`, `ARCHITECTURAL_KNOWLEDGE_MAP.md`, `CHAIN_REASONING.md`, `DECISION_ENGINE.md` §3 (jerarquía de severidad, reutilizada sin cambios como escala de "gravedad"), `ARCHITECTURAL_ONTOLOGY.md`, `SPACE_TAXONOMY.md`, `FUNCTIONAL_RELATIONS.md`, `ARCHITECTURAL_PRINCIPLES.md`, `TECH_REVIEW.md` (Bug #1 y demás deuda técnica real, citados como grounding).

---

## 0. Cómo leer este documento

**306 errores en 16 categorías.** Cada error lleva diez campos fijos, en el mismo orden:

- **Descripción** — qué ocurre, en una frase.
- **Por qué ocurre** — la causa raíz habitual, casi siempre humana o de proceso, no solo técnica.
- **Consecuencias** — qué se rompe si el error no se corrige.
- **Gravedad** — reutiliza sin cambios la jerarquía de cuatro valores de `DECISION_ENGINE.md` §3: **Bloqueante** (impide licencia/visado o compromete seguridad) / **Riesgo variable** (interpretación o criterio local) / **Recomendable** (buena práctica, no obligatoria) / **Preferencial** (mercado o estética).
- **Frecuencia** — escala cerrada nueva, simple: **Alta** / **Media** / **Baja**, según qué tan a menudo aparece este error en proyectos reales según el criterio consolidado de la serie.
- **Detección** — cómo se identifica, distinguiendo siempre si es geométricamente verificable hoy con el pipeline DXF 2D real de ArchMuse o si requiere dato adicional (misma disciplina de honestidad que `ARCHITECTURAL_ONTOLOGY.md`).
- **Prevención** — cómo evitarlo desde el proceso de diseño, antes de que ocurra.
- **Corrección** — cómo resolverlo una vez detectado.
- **Normativa relacionada** — la categoría normativa que lo cubre, nunca un artículo exacto (misma cautela ya fijada en `ARCHITECTURAL_KNOWLEDGE_MAP.md`, aviso inicial); en errores de la categoría 16, este campo dice explícitamente "ninguna — principio de diseño, no exigencia legal", coherente con `ARCHITECTURAL_PRINCIPLES.md`.
- **Efecto en cadena** — si el error, típicamente, dispara consecuencias en otro dominio (`CHAIN_REASONING.md`), cuál; si no, se dice explícitamente "efecto contenido, sin cadena habitual".

---

## Categoría 1 — Encaje urbanístico y marco legal (15)

**1. Evaluar sin verificar la calificación urbanística vigente**
- Descripción: el proyecto se desarrolla asumiendo un régimen urbanístico sin confirmarlo contra la ficha vigente.
- Por qué ocurre: presión de plazo en fase de anteproyecto; confianza en información de segunda mano del cliente o del solar.
- Consecuencias: rediseño completo si la calificación real difiere.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no verificable desde el DXF; requiere consulta directa a fuente municipal/catastral.
- Prevención: verificación documental como primer paso del proyecto, antes de cualquier boceto.
- Corrección: replantear el marco de lo posible antes de continuar el desarrollo.
- Normativa relacionada: legislación urbanística autonómica y planeamiento municipal.
- Efecto en cadena: sí — invalida potencialmente toda evaluación posterior de los 13 dominios restantes.

**2. Superar la edificabilidad máxima por error de cómputo**
- Descripción: la superficie construida total excede el límite del planeamiento por un error de suma o de criterio de cómputo.
- Por qué ocurre: criterios de cómputo distintos entre superficie construida "a efectos urbanísticos" y superficie construida real (voladizos, patios cubiertos con criterio distinto).
- Consecuencias: reparo de visado, necesidad de reducir superficie ya diseñada.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: calculable si se dispone del dato de edificabilidad y de la superficie construida agregada del proyecto.
- Prevención: verificar el criterio de cómputo exacto del planeamiento aplicable antes de cerrar volumetría.
- Corrección: reducir superficie construida o revisar el criterio de cómputo con el técnico municipal.
- Normativa relacionada: ficha urbanística de edificabilidad.
- Efecto en cadena: sí — fuerza replanteamiento de programa y, potencialmente, de todas las superficies internas.

**3. No descontar cesiones obligatorias del aprovechamiento real**
- Descripción: se calcula el derecho edificatorio sobre la superficie total de parcela sin descontar la cesión exigida.
- Por qué ocurre: confusión entre Edificabilidad (ratio general) y Aprovechamiento urbanístico (derecho ya aplicado a la parcela concreta), ya señalada como el solape más real de `ARCHITECTURAL_ONTOLOGY.md`.
- Consecuencias: sobreestimación del volumen edificable real disponible.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no verificable desde el DXF; dato de planeamiento.
- Prevención: verificar si la parcela concreta tiene cesión pendiente antes de fijar el aprovechamiento de cálculo.
- Corrección: recalcular el aprovechamiento real y ajustar el programa.
- Normativa relacionada: legislación de suelo, cesiones urbanísticas.
- Efecto en cadena: sí — mismo efecto que error 2.

**4. Ignorar el retranqueo mínimo a linderos**
- Descripción: la edificación se sitúa más cerca del lindero que el mínimo exigido.
- Por qué ocurre: maximizar superficie construida sin verificar el retranqueo exacto por tipo de lindero (frontal/lateral/fondo).
- Consecuencias: reparo de visado, necesidad de retranquear la edificación ya diseñada.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: no reconocible hoy — requiere geometría de parcela, no disponible en el DXF de distribución.
- Prevención: verificar retranqueos exactos antes de fijar la huella del edificio.
- Corrección: reducir la huella edificada en el lado afectado.
- Normativa relacionada: ordenanza municipal de edificación.
- Efecto en cadena: sí — reduce superficie construida disponible, tensiona programa completo.

**5. Superar la altura máxima por cómputo erróneo de plantas**
- Descripción: la altura total del edificio excede el máximo permitido por un error en el cómputo de plantas o de altura de cornisa.
- Por qué ocurre: confusión entre "planta" a efectos de cómputo de altura y planta a efectos de programa (áticos, entreplantas).
- Consecuencias: reducción de altura libre en plantas o eliminación de una planta completa.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible desde un único DXF de planta; requiere sección/alzado.
- Prevención: verificar el criterio municipal exacto de cómputo de altura antes de fijar volumetría.
- Corrección: rediseñar la sección del edificio.
- Normativa relacionada: ordenanza de altura reguladora.
- Efecto en cadena: sí — afecta a estructura, instalaciones y protección contra incendio de todas las plantas superiores.

**6. No verificar planeamiento en revisión**
- Descripción: se proyecta contra el planeamiento vigente sin comprobar si está en proceso de revisión con criterios distintos ya avanzados.
- Por qué ocurre: falta de consulta a fuentes actualizadas del ayuntamiento.
- Consecuencias: proyecto obsoleto respecto al régimen que estará vigente en el momento de la licencia.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: no verificable desde el DXF.
- Prevención: consulta directa y actualizada al servicio de urbanismo municipal.
- Corrección: adaptar el proyecto al planeamiento en revisión si su aprobación es inminente.
- Normativa relacionada: planeamiento en fase de redacción o revisión.
- Efecto en cadena: potencialmente, sobre todos los dominios normativos si el nuevo planeamiento cambia parámetros básicos.

**7. Asumir planeamiento general sin comprobar plan especial**
- Descripción: se aplican los parámetros del PGOU sin verificar si existe un Plan Especial o Estudio de Detalle que los modifica para esa parcela concreta.
- Por qué ocurre: el PGOU es la referencia por defecto más consultada; los planes de desarrollo particulares se olvidan con facilidad.
- Consecuencias: parámetros urbanísticos incorrectos aplicados a todo el proyecto.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: no verificable desde el DXF.
- Prevención: comprobación explícita de existencia de planeamiento de desarrollo antes de fijar cualquier parámetro.
- Corrección: replantear parámetros urbanísticos con el plan correcto.
- Normativa relacionada: jerarquía de planeamiento (PGOU → Plan Parcial/Especial → ordenanza).
- Efecto en cadena: sí, igual que error 1.

**8. No identificar catalogación patrimonial**
- Descripción: se trata el edificio o entorno como no protegido cuando sí lo está, total o parcialmente.
- Por qué ocurre: falta de consulta al catálogo de protección municipal antes de proyectar intervenciones sobre fachada o volumetría.
- Consecuencias: proyecto de intervención no admisible en fase de visado o licencia.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no verificable desde el DXF.
- Prevención: consulta al catálogo de protección patrimonial como paso obligatorio en rehabilitación.
- Corrección: replantear la intervención dentro del régimen de protección real.
- Normativa relacionada: normativa de protección patrimonial.
- Efecto en cadena: sí — condiciona simultáneamente huecos, envolvente térmica y accesibilidad posibles.

**9. Confundir parcela con solar**
- Descripción: se asume que una parcela es edificable de inmediato sin verificar que cuenta con los servicios urbanísticos completos.
- Por qué ocurre: uso coloquial impreciso de ambos términos (`ARCHITECTURAL_ONTOLOGY.md` A.1-A.2).
- Consecuencias: imposibilidad de obtener licencia sin trámite de urbanización previo.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no verificable desde el DXF.
- Prevención: verificación explícita de la condición de solar antes de iniciar diseño.
- Corrección: tramitar la urbanización pendiente o replantear plazos del proyecto.
- Normativa relacionada: legislación de suelo.
- Efecto en cadena: no directo sobre el diseño, sí sobre viabilidad y plazo del proyecto completo.

**10. No verificar uso característico permitido**
- Descripción: se proyecta un uso (por ejemplo, terciario en planta baja) no permitido por la calificación de la parcela.
- Por qué ocurre: asumir compatibilidad de usos sin comprobar la ficha urbanística.
- Consecuencias: reparo de visado, necesidad de cambiar el programa.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no verificable desde el DXF.
- Prevención: verificación de usos compatibles/prohibidos antes de fijar programa.
- Corrección: sustituir el uso por uno permitido.
- Normativa relacionada: ficha urbanística de usos.
- Efecto en cadena: sí — afecta a Tipología edificatoria y, por tanto, a todos los dominios normativos posteriores.

**11. Ignorar densidad máxima de viviendas por parcela**
- Descripción: el número de unidades proyectadas excede el máximo de viviendas/hectárea permitido.
- Por qué ocurre: maximizar unidades vendibles sin verificar el límite de densidad.
- Consecuencias: reducción forzada del número de unidades ya diseñadas.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: calculable si se dispone del dato de densidad máxima y del recuento real de unidades.
- Prevención: verificar densidad máxima antes de fijar el programa de unidades.
- Corrección: fusionar o eliminar unidades hasta cumplir el límite.
- Normativa relacionada: ficha urbanística de densidad.
- Efecto en cadena: sí — afecta directamente al programa y a todas las evaluaciones por unidad.

**12. Aplicar ordenanza municipal incorrecta por error de localización**
- Descripción: se usa la ordenanza de un municipio o distrito distinto al real del proyecto.
- Por qué ocurre: error administrativo, reutilización de plantillas de proyectos anteriores sin actualizar referencias.
- Consecuencias: todos los parámetros urbanísticos incorrectos.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no verificable desde el DXF; verificable cruzando el dato de ciudad/municipio declarado.
- Prevención: verificación cruzada del municipio declarado contra la ordenanza citada.
- Corrección: sustituir la ordenanza de referencia por la correcta y revisar todos los parámetros ya aplicados.
- Normativa relacionada: ordenanza municipal.
- Efecto en cadena: sí — mismo alcance que error 1, invalida evaluaciones ya hechas.

**13. No contemplar servidumbre de luces/vistas**
- Descripción: se reduce un retranqueo sin verificar si genera una servidumbre con la parcela colindante.
- Por qué ocurre: foco exclusivo en el mínimo normativo propio, sin considerar el efecto sobre terceros.
- Consecuencias: conflicto legal con la propiedad colindante, no solo administrativo.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: no verificable desde el DXF sin datos de la parcela colindante.
- Prevención: verificar la situación de la parcela colindante antes de reducir cualquier retranqueo.
- Corrección: restituir el retranqueo o negociar la servidumbre formalmente.
- Normativa relacionada: código civil de servidumbres, ordenanza de retranqueos.
- Efecto en cadena: sí — ya documentado como efecto empírico #12 de `CHAIN_REASONING.md`.

**14. Asumir alineación de fachada sin verificar la exigida**
- Descripción: se sitúa la fachada sin comprobar la alineación obligatoria fijada por el PGOU en ese tramo de calle.
- Por qué ocurre: criterio de diseño propio prevalece sobre la comprobación normativa previa.
- Consecuencias: reparo de visado, necesidad de rediseñar la posición de fachada.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no verificable desde el DXF de distribución interior.
- Prevención: verificación de alineación obligatoria antes de fijar el perímetro del edificio.
- Corrección: recolocar la fachada según la alineación exigida.
- Normativa relacionada: PGOU, alineaciones.
- Efecto en cadena: sí — afecta a superficie construida disponible y a orientación de piezas perimetrales.

**15. No verificar vigencia temporal de la normativa aplicada**
- Descripción: se evalúa el proyecto contra una versión derogada de una norma.
- Por qué ocurre: reutilización de plantillas o umbrales de proyectos anteriores sin verificar actualizaciones normativas.
- Consecuencias: evaluación completa basada en criterios ya no vigentes.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: no verificable desde el DXF; requiere gobernanza del catálogo de normativa (`CONSTRAINT_MODEL.md` §8, vigencia).
- Prevención: verificación de vigencia como parte del proceso de actualización del catálogo de Constraint.
- Corrección: re-evaluar todo el proyecto contra la norma vigente real.
- Normativa relacionada: cualquiera, según qué norma haya quedado desactualizada.
- Efecto en cadena: sí — invalida potencialmente toda evaluación normativa del proyecto.

---

## Categoría 2 — Programa, tipología y datos de entrada (20)

**16. No declarar la tipología edificatoria real**
- Descripción: el proyecto se evalúa sin que la tipología real (unifamiliar/plurifamiliar/rehabilitación) llegue al motor de reglas.
- Por qué ocurre: fallo de propagación del dato entre el formulario de entrada y el motor de evaluación — el Bug #1 real, ya confirmado en `TECH_REVIEW.md` (`app.py`, `/api/analizar`).
- Consecuencias: todo el proyecto se evalúa con valores por defecto incorrectos, silenciosamente.
- Gravedad: Bloqueante.
- Frecuencia: Alta (mientras el bug no se corrija).
- Detección: verificable por test de regresión (dato de entrada vs. dato realmente usado en la evaluación).
- Prevención: garantizar por diseño que ningún dato declarado pueda perderse en el camino hacia el motor de reglas (`FACT_MODEL.md` §1, principio rector).
- Corrección: corregir la propagación del parámetro en el código (`REFACTOR_MASTERPLAN.md` tarea 5).
- Normativa relacionada: todas las que dependen de tipología (Dominios 2-9 de `BRAIN_ARCHITECTURE.md`).
- Efecto en cadena: sí — el de mayor alcance de todo este catálogo, invalida silenciosamente la mayoría de las evaluaciones posteriores.

**17. Asumir zona climática por defecto**
- Descripción: se evalúa el comportamiento térmico con una zona climática por defecto en vez de la real del emplazamiento.
- Por qué ocurre: misma causa raíz que el error 16, aplicada a la zona climática (`DEFAULT_ZONA_CTE`).
- Consecuencias: evaluación térmica completamente desconectada del emplazamiento real.
- Gravedad: Bloqueante.
- Frecuencia: Alta (mientras el bug no se corrija).
- Detección: verificable por test de regresión, mismo mecanismo que el error 16.
- Prevención: mismo principio que el error 16.
- Corrección: mismo mecanismo que el error 16.
- Normativa relacionada: Dominio 8, eficiencia energética.
- Efecto en cadena: sí, contenido al Dominio 8 principalmente.

**18. Clasificar mal rehabilitación como obra nueva**
- Descripción: se aplican mínimos de obra nueva a una intervención de rehabilitación donde no son físicamente alcanzables.
- Por qué ocurre: no declarar explícitamente el alcance de la intervención antes de evaluar.
- Consecuencias: incumplimientos fabricados que no reflejan la realidad del régimen aplicable.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable automáticamente sin el dato declarado de alcance de intervención.
- Prevención: exigir declaración explícita de alcance antes de cualquier evaluación (`ARCHITECTURAL_ONTOLOGY.md` B.7).
- Corrección: reevaluar con el régimen de rehabilitación correcto.
- Normativa relacionada: régimen diferenciado obra nueva/rehabilitación.
- Efecto en cadena: sí — mismo alcance que el error 16, por tratarse también de Tipología.

**19. No declarar el número real de unidades independientes**
- Descripción: el sistema cuenta menos o más unidades de las reales por un polígono mal etiquetado o mal cerrado.
- Por qué ocurre: error en la etiqueta `VT<n>/<m>` del DXF de origen o polígono agrupador confundido con vivienda real.
- Consecuencias: evaluación de accesibilidad/evacuación con un umbral de exigencia (número de viviendas) incorrecto.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: verificable comparando el recuento de etiquetas `VT<n>/<m>` contra el recuento declarado por el arquitecto.
- Prevención: verificación cruzada automática entre ambos recuentos antes de evaluar.
- Corrección: corregir el etiquetado del DXF de origen.
- Normativa relacionada: umbrales por número de viviendas (ascensor, accesibilidad).
- Efecto en cadena: sí — afecta a Dominios 5 y 6.

**20. Etiquetar una pieza con un uso incorrecto**
- Descripción: el `MTEXT` de una pieza no corresponde a su uso real construido.
- Por qué ocurre: error de transcripción del delineante, copia de un plano anterior sin actualizar etiquetas.
- Consecuencias: evaluación de la pieza contra el umbral de un uso que no le corresponde.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: parcialmente — un desajuste evidente entre superficie/proporción y uso declarado podría marcarse como sospechoso, no confirmado sin verificación humana.
- Prevención: revisión cruzada de etiquetas antes de la evaluación automática.
- Corrección: corregir la etiqueta en el DXF de origen.
- Normativa relacionada: la que corresponda al uso real, no al declarado.
- Efecto en cadena: sí — cualquier regla que dependa de ese uso queda mal aplicada.

**21. Fusionar dos usos distintos bajo una única etiqueta**
- Descripción: dos espacios funcionalmente distintos (Salón y Cocina) se evalúan como un único tipo con un único umbral.
- Por qué ocurre: el error ya confirmado y real de `evaluator.py`, patrón `SALON|COCINA` fusionado — documentado en detalle en `SPACE_TAXONOMY.md` §1.3.
- Consecuencias: pérdida de precisión en la evaluación de cada espacio por separado.
- Gravedad: Riesgo variable.
- Frecuencia: Alta.
- Detección: verificable comparando el catálogo de patrones de reconocimiento contra el catálogo real de tipos de `SPACE_TAXONOMY.md`.
- Prevención: separar el patrón de reconocimiento por tipo, aplicando el umbral que corresponde a cada uno.
- Corrección: ampliar el catálogo de patrones del motor de reglas.
- Normativa relacionada: superficie mínima por tipo de pieza.
- Efecto en cadena: no directo, pero degrada la precisión de toda evaluación posterior sobre esas piezas.

**22. No distinguir plurifamiliar de unifamiliar entre medianeras**
- Descripción: se aplica el régimen de vivienda plurifamiliar a una unifamiliar entre medianeras, o viceversa.
- Por qué ocurre: ambigüedad en la declaración de tipología cuando la vivienda comparte muros con otras sin ser, formalmente, plurifamiliar.
- Consecuencias: exigencias de accesibilidad/evacuación incorrectas.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: no verificable automáticamente sin dato declarado explícito.
- Prevención: exigir declaración explícita, nunca inferida.
- Corrección: reevaluar con la tipología correcta.
- Normativa relacionada: régimen diferenciado por tipología.
- Efecto en cadena: sí, mismo alcance que el error 16.

**23. Aplicar reglas de obra nueva a rehabilitación parcial**
- Descripción: se exige el programa mínimo completo de obra nueva a una intervención que solo toca una parte del edificio.
- Por qué ocurre: no declarar con precisión el alcance real (parcial vs. integral) de la rehabilitación.
- Consecuencias: incumplimientos fabricados sobre zonas del edificio no intervenidas.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable sin el dato de alcance declarado.
- Prevención: declaración explícita del alcance exacto de la intervención, zona por zona.
- Corrección: limitar la evaluación de obra nueva a las zonas efectivamente intervenidas.
- Normativa relacionada: régimen de rehabilitación parcial.
- Efecto en cadena: no directo, contenido a las zonas mal clasificadas.

**24. No declarar el alcance real de la intervención**
- Descripción: se evalúa sin saber si la intervención es integral o parcial.
- Por qué ocurre: dato omitido en la fase de captura de información del proyecto.
- Consecuencias: mismo tipo de error que el 23, de origen.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable sin declaración explícita.
- Prevención: hacer obligatoria la declaración de alcance en el proceso de ingesta.
- Corrección: solicitar el dato antes de continuar la evaluación.
- Normativa relacionada: régimen de rehabilitación.
- Efecto en cadena: sí, es la causa raíz del error 23.

**25. Confundir superficie útil con superficie construida al declarar**
- Descripción: se introduce un valor de superficie construida donde el sistema espera superficie útil, o al revés.
- Por qué ocurre: ambigüedad de vocabulario entre cliente/arquitecto y sistema (`ARCHITECTURAL_ONTOLOGY.md` G.1-G.2).
- Consecuencias: cómputo de eficiencia útil/construida incorrecto, umbral de superficie mal comparado.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: parcialmente — si el valor declarado es menor que el área geométrica medida del polígono, es indicio de confusión de magnitud.
- Prevención: etiquetar de forma inequívoca cada campo del formulario de entrada con su definición exacta.
- Corrección: corregir el dato de entrada y reevaluar.
- Normativa relacionada: cómputo de superficie útil/construida.
- Efecto en cadena: no directo, contenido al cálculo de eficiencia.

**26. No verificar consistencia entre plano y memoria descriptiva**
- Descripción: la memoria escrita declara datos (tipología, número de dormitorios) que no coinciden con lo dibujado.
- Por qué ocurre: la memoria se redacta o actualiza en un momento distinto al del plano, sin sincronización.
- Consecuencias: evaluación basada en un dato que contradice la geometría real.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: parcialmente — comparando el recuento geométrico real (número de dormitorios detectados) contra el declarado en memoria.
- Prevención: verificación cruzada automática entre ambas fuentes antes de evaluar.
- Corrección: sincronizar memoria y plano antes de la entrega.
- Normativa relacionada: ninguna directa — error de proceso documental.
- Efecto en cadena: no directo, riesgo de visado (categoría 13).

**27. Duplicar una vivienda por error de conteo de polígonos**
- Descripción: el mismo polígono se cuenta dos veces como si fueran dos unidades distintas.
- Por qué ocurre: un contorno agrupador mal descartado (color DXF no reconocido como duplicado) se trata como una vivienda real.
- Consecuencias: recuento total de unidades incorrecto, afecta a umbrales por número de viviendas.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: ya parcialmente mitigado en producción — `parser.py` descarta contornos agrupadores por su color DXF explícito (ACI 10/150 frente a `BYLAYER_COLOR`), aunque el mecanismo no es infalible ante convenciones de color distintas.
- Prevención: verificación visual del recuento final de unidades antes de evaluar.
- Corrección: ajustar el criterio de descarte de duplicados en el parser.
- Normativa relacionada: ninguna directa — error de proceso de ingesta de datos.
- Efecto en cadena: sí, mismo alcance que el error 19.

**28. Omitir una unidad por polígono mal cerrado**
- Descripción: una vivienda real no se reconoce porque su polilínea no está correctamente cerrada en el DXF.
- Por qué ocurre: error de dibujo del delineante, capa incorrecta, o polilínea abierta por un extremo.
- Consecuencias: una unidad completa queda fuera de toda evaluación, sin que nadie lo note.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: parcialmente — un recuento de unidades detectadas inferior al declarado por el arquitecto es indicio directo, mismo mecanismo que el error 19.
- Prevención: verificación automática de cierre de polilíneas antes de aceptar la ingesta.
- Corrección: cerrar la polilínea en el DXF de origen y reingerir.
- Normativa relacionada: ninguna directa — error de proceso de ingesta de datos.
- Efecto en cadena: sí — la unidad omitida queda completamente sin evaluar, el peor caso de silencio posible.

**29. Asumir el norte geográfico sin verificar el ángulo real**
- Descripción: la orientación de las piezas se calcula con el norte del DXF (ejes de dibujo) sin aplicar la corrección del norte real declarado.
- Por qué ocurre: no verificar que el parámetro "norte_grados" del formulario se ha aplicado correctamente al cálculo.
- Consecuencias: todas las recomendaciones de orientación quedan invertidas o desviadas.
- Gravedad: Recomendable (la orientación es Nivel 3, no bloqueante).
- Frecuencia: Media.
- Detección: verificable por test comparando el ángulo aplicado contra el declarado.
- Prevención: verificación explícita del parámetro antes de cualquier cálculo de orientación.
- Corrección: corregir la aplicación del ángulo y recalcular.
- Normativa relacionada: ninguna — criterio de calidad, no exigencia (`ARCHITECTURAL_PRINCIPLES.md` A.2).
- Efecto en cadena: no directo, contenido a las recomendaciones de orientación.

**30. No actualizar los datos tras un cambio de última hora**
- Descripción: se evalúa una versión del proyecto que ya no coincide con la última decisión del arquitecto.
- Por qué ocurre: falta de un mecanismo de versión única de verdad, evaluación sobre un archivo desactualizado.
- Consecuencias: informe entregado sobre un proyecto que ya no es el real.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable automáticamente sin un mecanismo de versionado (`REASONING_ENGINE_SPEC.md` entidad 1, `ProjectState`, hoy no implementado).
- Prevención: proceso de verificación de "última versión" antes de cada evaluación.
- Corrección: reevaluar sobre el archivo correcto.
- Normativa relacionada: ninguna directa — error de proceso.
- Efecto en cadena: no directo, pero invalida potencialmente todo el informe entregado.

**31. Mezclar datos de dos versiones distintas en la misma evaluación**
- Descripción: parte de los datos usados (geometría, parámetros de formulario) pertenecen a versiones distintas del proyecto.
- Por qué ocurre: reingesta parcial de un archivo sin reingerir también los parámetros de formulario asociados.
- Consecuencias: evaluación internamente inconsistente, sin que el error sea visible a simple vista.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: no verificable sin un mecanismo de trazabilidad de versión por dato (`FACT_MODEL.md` §7).
- Prevención: atar geometría y parámetros de formulario a la misma versión de forma indivisible.
- Corrección: reevaluar con ambos conjuntos de datos de la misma versión.
- Normativa relacionada: ninguna directa — error de proceso.
- Efecto en cadena: sí, potencialmente sobre toda la evaluación.

**32. No declarar plantas adicionales no representadas**
- Descripción: el proyecto tiene más plantas de las que el DXF analizado representa, sin advertirlo.
- Por qué ocurre: se analiza un único DXF por comodidad, sin declarar que hay más plantas fuera del alcance de esa evaluación concreta.
- Consecuencias: conclusiones sobre coherencia estructural o vertical que son, en realidad, incompletas.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable sin declaración explícita del número total de plantas del proyecto.
- Prevención: exigir declaración del alcance de plantas cubierto por cada evaluación.
- Corrección: ampliar el análisis a las plantas restantes o advertir explícitamente la limitación.
- Normativa relacionada: ninguna directa — alcance de análisis.
- Efecto en cadena: sí — sobre todo, Dominio 10 (Instalaciones) y Dominio 11 (Estructura), que dependen de coherencia entre plantas.

**33. Asumir programa mínimo estándar sin verificar requisitos del cliente**
- Descripción: se evalúa contra un programa genérico sin contrastar contra las necesidades reales declaradas por el cliente.
- Por qué ocurre: uso de plantillas de evaluación sin personalizar al encargo concreto.
- Consecuencias: recomendaciones desalineadas con lo que el cliente realmente necesita.
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: no verificable automáticamente — requiere el dato de Preference declarada (`REASONING_ENGINE_SPEC.md` entidad 13).
- Prevención: captura explícita de preferencias antes de generar recomendaciones.
- Corrección: reevaluar con las preferencias reales incorporadas.
- Normativa relacionada: ninguna — criterio de programa, no normativo.
- Efecto en cadena: no directo, contenido a recomendaciones de programa.

**34. No verificar coherencia entre uso declarado por planta y el real construido**
- Descripción: se declara un uso de planta (residencial, terciario) que no coincide con lo efectivamente construido en ella.
- Por qué ocurre: cambio de programa durante el desarrollo sin actualizar la declaración inicial.
- Consecuencias: evaluación de toda la planta con el régimen normativo incorrecto.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: parcialmente — comparando el catálogo de usos de piezas reconocidas contra el uso de planta declarado.
- Prevención: verificación cruzada automática antes de evaluar.
- Corrección: actualizar la declaración de uso de planta.
- Normativa relacionada: régimen por uso de planta.
- Efecto en cadena: sí, mismo alcance que el error 16 para esa planta concreta.

**35. Ignorar cambios de uso sobrevenidos durante el desarrollo**
- Descripción: una pieza cambia de uso (de trastero a dormitorio) durante el desarrollo del proyecto sin que se reevalúen las exigencias que ese cambio activa.
- Por qué ocurre: el cambio se incorpora al plano pero no se comunica como un evento que requiere re-evaluación completa.
- Consecuencias: la pieza queda con el uso nuevo pero sin cumplir ninguna de las exigencias (superficie, iluminación, evacuación) que ese uso activa de golpe.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: no verificable sin un mecanismo de Change/re-propagación (`CHAIN_REASONING.md`, efecto empírico #7).
- Prevención: tratar todo cambio de uso como disparador obligatorio de reevaluación completa de la pieza.
- Corrección: reevaluar la pieza con el nuevo uso contra el catálogo completo de exigencias que le corresponden.
- Normativa relacionada: todas las asociadas al nuevo uso.
- Efecto en cadena: sí — es, literalmente, el efecto empírico #7 de `CHAIN_REASONING.md`.

---

## Categoría 3 — Geometría y dimensionado (25)

**36. Dormitorio por debajo de la superficie mínima**
- Descripción: un dormitorio no alcanza la superficie mínima exigida según su jerarquía (principal/secundario).
- Por qué ocurre: presión de programa para encajar más dormitorios en la misma superficie total disponible.
- Consecuencias: incumplimiento normativo directo, rediseño de distribución.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: alta — ya en producción (`evaluator.py`, umbrales 10,0/8,0/6,0 m² por jerarquía).
- Prevención: verificar superficie mínima antes de cerrar la distribución definitiva.
- Corrección: ampliar la pieza a costa de una pieza adyacente de menor prioridad.
- Normativa relacionada: decreto autonómico de habitabilidad, superficie mínima de dormitorio.
- Efecto en cadena: sí — ampliar el dormitorio reduce la pieza adyacente (efecto empírico relacionado con #1 de `CHAIN_REASONING.md`).

**37. Salón/estar por debajo de la superficie mínima combinada**
- Descripción: el Salón (o Salón-comedor, o Salón-cocina fusionado) no alcanza el umbral combinado exigido.
- Por qué ocurre: sobredimensionar dormitorios a costa de la pieza principal.
- Consecuencias: incumplimiento directo, además de una jerarquía espacial invertida (categoría 9).
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: alta — ya en producción (umbral 20,0 m²).
- Prevención: fijar la superficie del Salón como referencia de partida del programa, no como resto.
- Corrección: redistribuir superficie desde piezas de menor jerarquía.
- Normativa relacionada: decreto autonómico de habitabilidad, superficie mínima de estancia principal.
- Efecto en cadena: sí — tensiona directamente con el resto del programa.

**38. Baño por debajo de la superficie mínima**
- Descripción: un Baño no alcanza el umbral mínimo exigido.
- Por qué ocurre: minimizar piezas húmedas para maximizar superficie de piezas habitables principales.
- Consecuencias: incumplimiento directo.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: alta — ya en producción (umbral 3,0 m²).
- Prevención: verificar el mínimo antes de cerrar la posición del núcleo húmedo.
- Corrección: ampliar la pieza, habitualmente a costa de un distribuidor adyacente.
- Normativa relacionada: decreto autonómico de habitabilidad.
- Efecto en cadena: no directo, contenido salvo que afecte a la coherencia vertical con otras plantas.

**39. Pieza con proporción "tubo"**
- Descripción: una pieza cumple la superficie mínima pero su proporción (muy alargada y estrecha) la hace poco funcional en la práctica.
- Por qué ocurre: geometría condicionada por una crujía estructural estrecha, sin ajustar la distribución interior a esa limitación.
- Consecuencias: pieza inamueblable en la práctica pese a cumplir el mínimo normativo.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: alta — ya en producción, heurística de proporción de `spatial_quality.py`.
- Prevención: verificar proporción, no solo superficie, en fase de anteproyecto.
- Corrección: redistribuir tabiquería para mejorar la relación de aspecto.
- Normativa relacionada: ninguna directa en la mayoría de decretos — criterio de calidad (Nivel 3).
- Efecto en cadena: no directo, contenido a la pieza afectada.

**40. Ancho de pieza habitable por debajo del mínimo**
- Descripción: el ancho mínimo exigido no se cumple aunque la superficie total sí.
- Por qué ocurre: geometría irregular o forma en L que cumple superficie pero no ancho en ningún punto suficiente.
- Consecuencias: incumplimiento directo.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: alta — calculable geométricamente sobre el polígono ya reconocido.
- Prevención: verificar ancho mínimo, no solo superficie, desde el primer boceto.
- Corrección: redistribuir la geometría de la pieza.
- Normativa relacionada: decreto autonómico de habitabilidad, ancho mínimo.
- Efecto en cadena: no directo, contenido a la pieza.

**41. Altura libre insuficiente**
- Descripción: la altura libre de una pieza habitable no alcanza el mínimo exigido.
- Por qué ocurre: forjado más grueso de lo previsto, o pieza bajo cubierta sin verificar la altura variable real.
- Consecuencias: incumplimiento directo.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible desde un DXF de planta 2D — dato de sección.
- Prevención: verificar altura libre real desde la sección constructiva, no solo desde la planta.
- Corrección: rediseño de sección o de posición de la pieza.
- Normativa relacionada: decreto autonómico de habitabilidad, altura libre mínima.
- Efecto en cadena: no directo, contenido a la pieza.

**42. Superficie útil mal computada por error de descuento de particiones**
- Descripción: se computa la superficie del polígono bruto sin descontar el grosor real de las particiones.
- Por qué ocurre: dibujar el polígono de superficie útil coincidiendo con el eje de la partición en vez de con su paramento interior.
- Consecuencias: superficie útil declarada mayor que la real.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no reconocible con fiabilidad sin datos de grosor de partición (`ARCHITECTURAL_ONTOLOGY.md` D.1, no reconocible hoy).
- Prevención: verificar el criterio de dibujo del polígono de superficie útil desde el origen del DXF.
- Corrección: corregir el polígono al paramento interior real.
- Normativa relacionada: criterio de cómputo de superficie útil.
- Efecto en cadena: no directo, pero afecta a todos los umbrales que dependen de esa superficie.

**43. No descontar elementos estructurales visibles**
- Descripción: un pilar o muro que invade una pieza no se descuenta del cómputo de superficie útil.
- Por qué ocurre: mismo origen que el error 42, aplicado a elementos estructurales interiores.
- Consecuencias: superficie útil sobreestimada.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: no reconocible sin datos de elementos estructurales (`ARCHITECTURAL_ONTOLOGY.md` F.1).
- Prevención: verificar que el polígono de superficie útil excluye elementos estructurales visibles.
- Corrección: corregir el polígono.
- Normativa relacionada: criterio de cómputo de superficie útil.
- Efecto en cadena: no directo.

**44. Computar terraza o tendedero como superficie útil interior**
- Descripción: se incluye superficie exterior en el cómputo de eficiencia útil/construida de la vivienda.
- Por qué ocurre: descuido en la clasificación de piezas exteriores como si fueran interiores.
- Consecuencias: eficiencia útil/construida sobreestimada, distorsiona un indicador de calidad real.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: alta — ya en producción (`NON_USEFUL_PATTERN`, exclusión de `TERRAZA|TENDEDERO`).
- Prevención: mantener el catálogo de exclusión actualizado y verificado.
- Corrección: recalcular excluyendo la superficie exterior.
- Normativa relacionada: criterio de cómputo de superficie útil.
- Efecto en cadena: no directo, contenido al indicador de eficiencia.

**45. Confundir superficie de proyecto con superficie realmente construida**
- Descripción: se evalúa contra la superficie prevista en fase de anteproyecto, sin actualizar tras cambios posteriores.
- Por qué ocurre: falta de sincronización entre versiones del proyecto (mismo origen que el error 30).
- Consecuencias: evaluación desconectada de la realidad final del proyecto.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable sin mecanismo de versión única de verdad.
- Prevención: mismo mecanismo que el error 30.
- Corrección: reevaluar con la superficie real actualizada.
- Normativa relacionada: ninguna directa — error de proceso.
- Efecto en cadena: no directo, pero invalida el informe si no se corrige.

**46. Pieza bajo cubierta con cómputo incorrecto de altura variable**
- Descripción: se computa la superficie completa de una pieza bajo cubierta sin aplicar la regla de altura mínima variable.
- Por qué ocurre: desconocimiento o descuido del criterio específico (distinto entre decretos autonómicos) para piezas de altura no uniforme.
- Consecuencias: superficie útil sobreestimada.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: no reconocible desde un DXF de planta 2D — requiere dato de sección/altura variable.
- Prevención: verificar el criterio de cómputo específico de altura variable de la comunidad autónoma aplicable.
- Corrección: recalcular excluyendo la zona por debajo de la altura mínima computable.
- Normativa relacionada: decreto autonómico, cómputo bajo cubierta.
- Efecto en cadena: no directo, contenido al cómputo de esa pieza.

**47. Jerarquía de dormitorios invertida**
- Descripción: un dormitorio de menor jerarquía declarada (Dormitorio 2 o 3) tiene mayor superficie que uno de mayor jerarquía (Dormitorio 1).
- Por qué ocurre: distribución no revisada tras cambios puntuales de tabiquería.
- Consecuencias: incoherencia de programa, aunque cada pieza individualmente cumpla su propio mínimo.
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: alta — ya en producción (`evaluate_dormitorio_hierarchy`).
- Prevención: verificar jerarquía tras cualquier ajuste de tabiquería.
- Corrección: reajustar superficies para restaurar la jerarquía declarada, o renumerar los dormitorios si la jerarquía real es distinta a la declarada.
- Normativa relacionada: ninguna directa — criterio de coherencia, no exigencia normativa.
- Efecto en cadena: no directo, contenido a la coherencia interna del programa.

**48. Espacio residual sin uso claro**
- Descripción: tras cerrar la distribución, queda un remanente de superficie sin asignar a ninguna pieza con función clara.
- Por qué ocurre: ajuste geométrico de última hora entre piezas que deja un resto sin resolver.
- Consecuencias: pérdida de eficiencia y de calidad espacial (categoría 9).
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible automáticamente sin un modelo de piezas etiquetadas completo (una pieza sin etiqueta de uso reconocible sería indicio).
- Prevención: verificar que toda la superficie del proyecto queda asignada a una pieza con uso declarado.
- Corrección: incorporar el remanente a una pieza adyacente o darle un uso propio.
- Normativa relacionada: ninguna — criterio de calidad.
- Efecto en cadena: no directo.

**49. Piezas de geometría irregular sin criterio claro de medición de ancho**
- Descripción: en una pieza no rectangular, el "ancho mínimo" se mide con un criterio ambiguo que puede dar resultados distintos según el método.
- Por qué ocurre: ausencia de un único criterio de medición estandarizado para geometrías no ortogonales (ya señalado en `ARCHITECTURAL_ONTOLOGY.md` C.1 como caso sin respuesta única).
- Consecuencias: evaluación de cumplimiento potencialmente distinta según el método de medición usado.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: parcialmente — calculable con distintos métodos (ancho mínimo inscrito, ancho medio), sin que exista un único criterio cerrado en la serie todavía.
- Prevención: fijar y documentar un único método de medición para geometrías irregulares.
- Corrección: reevaluar con el método acordado y, si es de zona gris, documentar la justificación (categoría 13).
- Normativa relacionada: decreto autonómico, ancho mínimo.
- Efecto en cadena: no directo.

**50. Redondeo optimista de una medida límite**
- Descripción: una medida en el límite exacto del mínimo (por ejemplo, 2,999 m redondeado a 3,00 m) se presenta como cumplida sin margen real.
- Por qué ocurre: presión por evitar un incumplimiento, tolerancia de redondeo mal aplicada.
- Consecuencias: incumplimiento real oculto tras una precisión de medición forzada.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: alta — verificable comparando el valor exacto, sin redondeo, contra el umbral.
- Prevención: nunca redondear a favor del cumplimiento; usar siempre el valor medido exacto.
- Corrección: corregir la geometría real, no el redondeo del informe.
- Normativa relacionada: cualquier umbral dimensional.
- Efecto en cadena: no directo, riesgo de visado si se descubre (categoría 13).

**51. No verificar la superficie real tras una revisión tardía**
- Descripción: un cambio de última hora en la distribución no se refleja en el cómputo final de superficies entregado.
- Por qué ocurre: falta de recomputo automático tras cada Change (mismo origen que el error 35).
- Consecuencias: informe final con datos de superficie desactualizados.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable sin recomputo automático disparado por cada cambio.
- Prevención: recomputar automáticamente tras cualquier modificación geométrica, nunca depender de recordarlo manualmente.
- Corrección: recalcular y reemitir el informe.
- Normativa relacionada: ninguna directa — error de proceso.
- Efecto en cadena: no directo, pero invalida el informe entregado.

**52. Cocina de superficie insuficiente al no computarse por separado**
- Descripción: al fusionarse Salón y Cocina bajo un único umbral (error 21), una Cocina real de superficie muy pequeña queda enmascarada dentro de un total que sí cumple.
- Por qué ocurre: consecuencia directa del error 21.
- Consecuencias: cocina funcionalmente insuficiente que el sistema no detecta como tal.
- Gravedad: Recomendable.
- Frecuencia: Alta.
- Detección: no verificable hoy, mismo origen que el error 21.
- Prevención: separar el reconocimiento de Cocina de Salón (`SPACE_TAXONOMY.md` §2.1).
- Corrección: ampliar el catálogo de patrones para evaluar cada pieza fusionada por separado cuando el DXF sí las distingue geométricamente.
- Normativa relacionada: superficie mínima de cocina, cuando existe como umbral independiente.
- Efecto en cadena: no directo, es consecuencia del error 21, no origen de uno nuevo.

**53. Vestidor computado como dormitorio secundario indebidamente**
- Descripción: una pieza sin ventana ni función de descanso se etiqueta y evalúa como dormitorio.
- Por qué ocurre: similitud de superficie entre un vestidor y un dormitorio pequeño (ya señalado en `SPACE_TAXONOMY.md` §4.3).
- Consecuencias: incumplimiento fabricado de iluminación/ventilación sobre una pieza que, correctamente clasificada, no lo exigiría.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: parcialmente — desajuste entre etiqueta declarada y ausencia de hueco sería indicio, no confirmación automática.
- Prevención: verificar la etiqueta declarada, nunca inferir el uso por superficie (`ARCHITECTURAL_PRINCIPLES.md` B.3).
- Corrección: corregir la etiqueta de uso.
- Normativa relacionada: superficie e iluminación mínima de dormitorio, mal aplicada.
- Efecto en cadena: no directo, contenido a esa pieza.

**54. No verificar la eficiencia útil/construida global**
- Descripción: el proyecto cumple todos los mínimos por pieza pero el ratio global de eficiencia de la vivienda es bajo.
- Por qué ocurre: exceso de superficie dedicada a circulación o a piezas de baja eficiencia (distribuidores largos, vestíbulos sobredimensionados).
- Consecuencias: vivienda percibida como poco eficiente pese a cumplir todos los mínimos individuales.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: alta — ya en producción (cómputo de eficiencia útil/construida excluyendo terraza/tendedero).
- Prevención: verificar el ratio global, no solo el cumplimiento pieza a pieza.
- Corrección: redistribuir superficie de circulación hacia piezas habitables.
- Normativa relacionada: ninguna directa en la mayoría de decretos — indicador de calidad.
- Efecto en cadena: no directo, agregado de otros errores individuales (por ejemplo, error 166).

**55. Sobreestimar la superficie útil por nichos o retranqueos no habitables**
- Descripción: se incluye en el cómputo un nicho o retranqueo de la pieza que, por su geometría, no es realmente utilizable.
- Por qué ocurre: cómputo automático sobre el polígono bruto sin filtrar zonas de utilidad marginal.
- Consecuencias: superficie útil declarada mayor que la realmente aprovechable.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: parcialmente — detectable geométricamente si el nicho tiene una proporción muy desfavorable, sin un criterio cerrado hoy en la serie.
- Prevención: definir un criterio de exclusión de zonas de utilidad marginal antes del cómputo.
- Corrección: recalcular excluyendo la zona no utilizable.
- Normativa relacionada: criterio de cómputo de superficie útil.
- Efecto en cadena: no directo.

**56. Confundir ancho de pieza con ancho de hueco de acceso**
- Descripción: se verifica el ancho de la puerta de acceso a una pieza como si fuera el ancho mínimo exigido de la propia pieza.
- Por qué ocurre: confusión de conceptos entre Ancho de paso (`ARCHITECTURAL_ONTOLOGY.md` G.3) y ancho de la Pieza en sí.
- Consecuencias: verificación incorrecta, potencialmente un falso cumplimiento.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: alta — son dos magnitudes distintas, verificable si ambas están claramente distinguidas en el modelo de datos.
- Prevención: mantener ambos conceptos claramente separados en el catálogo de Constraint.
- Corrección: verificar cada magnitud contra su propio umbral correspondiente.
- Normativa relacionada: ancho mínimo de pieza vs. ancho mínimo de paso, umbrales distintos.
- Efecto en cadena: no directo.

**57. No verificar coherencia dimensional entre plantas de un edificio multiplanta**
- Descripción: la misma pieza (núcleo húmedo, escalera) tiene dimensiones distintas e incoherentes entre plantas consecutivas.
- Por qué ocurre: evaluación de cada planta de forma aislada, sin comparar contra las plantas adyacentes.
- Consecuencias: incoherencia estructural o de instalaciones no detectada.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: no reconocible con el flujo actual de un único DXF por evaluación (mismo límite que el error 32).
- Prevención: evaluar siempre el conjunto de plantas disponibles, no cada una de forma aislada.
- Corrección: ajustar la planta discordante para restaurar coherencia.
- Normativa relacionada: coherencia estructural, Dominio 11.
- Efecto en cadena: sí — puede propagarse a estructura e instalaciones.

**58. Aplicar el umbral de superficie de una comunidad autónoma incorrecta**
- Descripción: se evalúa contra los mínimos de una comunidad autónoma distinta a la real del emplazamiento.
- Por qué ocurre: mismo tipo de error que el 12, aplicado específicamente al umbral de superficie de habitabilidad.
- Consecuencias: umbrales incorrectos en todo el Dominio 3.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: verificable si el dato de comunidad autónoma declarado se contrasta contra el catálogo de umbrales aplicado.
- Prevención: verificación cruzada del dato de ubicación contra el catálogo de umbrales usado.
- Corrección: reevaluar con el catálogo correcto.
- Normativa relacionada: decreto autonómico de habitabilidad.
- Efecto en cadena: sí, mismo alcance que el error 12.

**59. Ignorar el efecto de mobiliario fijo necesario sobre la superficie utilizable**
- Descripción: se declara cumplida la superficie mínima sin considerar que el mobiliario mínimo indispensable (cama, armario) no cabe razonablemente en la geometría resultante.
- Por qué ocurre: verificación puramente dimensional sin verificación de amueblamiento real.
- Consecuencias: pieza normativamente conforme pero funcionalmente deficiente.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible automáticamente hoy — requiere un modelo de amueblamiento mínimo, no implementado.
- Prevención: verificar amueblamiento razonable en fase de anteproyecto, no solo superficie total.
- Corrección: redistribuir la geometría de la pieza.
- Normativa relacionada: ninguna directa en la mayoría de decretos — criterio de calidad (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 3 §5).
- Efecto en cadena: no directo.

**60. No verificar proporción superficie/altura dentro de un rango de confort**
- Descripción: una pieza con altura libre excepcionalmente alta o baja respecto a su superficie genera una sensación de escala inadecuada, sin que ningún umbral dimensional aislado lo capture.
- Por qué ocurre: verificación de cada magnitud (superficie, altura) por separado, sin verificar su relación conjunta.
- Consecuencias: pieza normativamente conforme con escala percibida pobre.
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: no reconocible desde un DXF de planta 2D sin dato de altura libre real (mismo límite que el error 41).
- Prevención: verificar el ratio superficie/altura cuando exista dato de sección disponible.
- Corrección: ajustar sección o distribución.
- Normativa relacionada: ninguna directa — criterio de calidad (`ARCHITECTURAL_ONTOLOGY.md` G.4, Nivel 4 en su mayor parte).
- Efecto en cadena: no directo.

---

## Categoría 4 — Iluminación y ventilación natural (20)

**61. Superficie de hueco por debajo del ratio mínimo**
- Descripción: la superficie de hueco de una pieza no alcanza el ratio mínimo exigido respecto a su superficie útil.
- Por qué ocurre: priorizar composición de fachada exterior sobre el ratio interior exigido, o fachada insuficiente disponible para la pieza.
- Consecuencias: incumplimiento directo.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: parcial — hoy vía proxy estimado (`facade_width × 0,25`, ya documentado como Estimation en `UNCERTAINTY_MODEL.md`), no medición directa del hueco real.
- Prevención: verificar el ratio en fase de anteproyecto, antes de comprometer la composición de fachada.
- Corrección: ampliar el hueco o reducir la superficie de la pieza que lo exige.
- Normativa relacionada: decreto autonómico de habitabilidad, CTE DB-HS3.
- Efecto en cadena: sí — ya documentado como efecto empírico #2 de `CHAIN_REASONING.md` (tensiona con Dominio 8).

**62. Confundir superficie de iluminación con superficie de ventilación**
- Descripción: se verifica un único ratio cuando, en el decreto aplicable, iluminación y ventilación tienen exigencias distintas.
- Por qué ocurre: simplificación indebida de dos exigencias normativas distintas en una sola verificación.
- Consecuencias: cumplimiento de una exigencia mientras la otra queda sin verificar.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no verificable hoy sin distinguir ambos ratios en el catálogo de Constraint.
- Prevención: mantener ambos ratios como Constraint independientes.
- Corrección: verificar cada ratio por separado.
- Normativa relacionada: decreto autonómico, exigencias diferenciadas de luz y aire.
- Efecto en cadena: no directo, contenido a la pieza.

**63. Patio de luces de dimensión inferior a la mínima**
- Descripción: el patio al que vierten varias piezas no alcanza la dimensión mínima exigida según la altura del edificio.
- Por qué ocurre: maximizar superficie edificable a costa de reducir el patio, sin verificar el mínimo variable por altura.
- Consecuencias: incumplimiento que afecta a todas las piezas que vierten a ese patio simultáneamente.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible con fiabilidad hoy — el Patio es parcialmente reconocible solo si el DXF lo etiqueta explícitamente (`ARCHITECTURAL_ONTOLOGY.md` D.6).
- Prevención: verificar la dimensión mínima variable por altura antes de fijar la geometría del patio.
- Corrección: ampliar el patio, con el coste de superficie edificable que eso implica.
- Normativa relacionada: decreto autonómico, dimensión mínima de patio.
- Efecto en cadena: sí — ya documentado como efecto empírico #13 de `CHAIN_REASONING.md`, afecta a todas las piezas que vierten al mismo patio.

**64. Pieza habitable sin ningún hueco al exterior**
- Descripción: una pieza destinada a permanencia carece por completo de relación con el exterior.
- Por qué ocurre: parcela de fondo profundo, maximización de superficie construida sin reservar fachada suficiente.
- Consecuencias: incumplimiento directo del principio más básico de habitabilidad.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: parcial — verificable si el polígono de la pieza no tiene ningún tramo de perímetro coincidente con el exterior del proyecto (mismo mecanismo que `ARCHITECTURAL_PRINCIPLES.md` B.3).
- Prevención: verificar que toda pieza habitable tiene fachada propia disponible desde el primer boceto.
- Corrección: redistribuir la pieza hacia una posición con fachada, o cambiar su uso a no habitable.
- Normativa relacionada: decreto autonómico de habitabilidad, exigencia de iluminación natural.
- Efecto en cadena: no directo, pero es de los incumplimientos de mayor gravedad de toda esta categoría.

**65. Iluminación indirecta a través de otra pieza sin verificar el decreto**
- Descripción: se admite que una pieza reciba luz a través de otra sin comprobar si el decreto autonómico aplicable lo permite.
- Por qué ocurre: solución habitual en rehabilitación asumida como válida sin verificar el criterio autonómico concreto.
- Consecuencias: incumplimiento potencial según el decreto aplicable (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 4 §8, caso sin consenso único entre decretos).
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: no verificable sin conocer el criterio exacto del decreto autonómico aplicable.
- Prevención: verificar explícitamente si el decreto autonómico admite esta solución antes de adoptarla.
- Corrección: sustituir por iluminación directa si el decreto no la admite.
- Normativa relacionada: decreto autonómico, criterio variable entre comunidades.
- Efecto en cadena: no directo.

**66. No considerar la obstrucción de un edificio vecino**
- Descripción: se verifica el ratio de hueco sin considerar que un edificio vecino próximo reduce sustancialmente la luz real recibida.
- Por qué ocurre: el ratio normativo es geométrico, no mide obstrucción real del entorno construido.
- Consecuencias: cumplimiento normativo con calidad de luz real muy inferior a la esperada.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible sin datos del entorno construido, ausentes en el DXF de distribución del proyecto propio.
- Prevención: verificar el entorno real en fase de anteproyecto, más allá del cálculo normativo aislado.
- Corrección: ninguna corrección de diseño posible una vez fijado el entorno — solo advertir la limitación de calidad esperada.
- Normativa relacionada: ninguna directa — brecha entre cumplimiento normativo y calidad real (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 4 §5).
- Efecto en cadena: no directo.

**67. Patio estrecho y profundo que cumple el mínimo pero es de mala calidad**
- Descripción: el patio cumple la dimensión mínima normativa pero su proporción (muy profundo respecto a su ancho) produce una calidad de luz real deficiente.
- Por qué ocurre: cumplir el mínimo exacto sin verificar la proporción completa del patio.
- Consecuencias: piezas normativamente conformes con luz real percibida como oscura.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible con fiabilidad sin datos de altura del edificio que vierte al patio.
- Prevención: verificar proporción del patio, no solo su dimensión mínima aislada.
- Corrección: ampliar el patio más allá del mínimo estricto.
- Normativa relacionada: ninguna directa — brecha entre mínimo normativo y calidad real.
- Efecto en cadena: no directo.

**68. Ampliar un hueco sin verificar el efecto térmico**
- Descripción: se amplía un hueco para mejorar iluminación sin recalcular el efecto sobre la demanda energética.
- Por qué ocurre: tratamiento aislado del Dominio 4 sin verificar la tensión conocida con el Dominio 8.
- Consecuencias: mejora de un dominio a costa de un empeoramiento no advertido en otro.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: parcialmente — si ambos dominios están activos en la evaluación, es verificable por recomputo cruzado.
- Prevención: tratar cualquier cambio de hueco como disparador de recomputo del Dominio 8, nunca aislado.
- Corrección: compensar con protección solar (`ARCHITECTURAL_PRINCIPLES.md` A.4) o ajustar la ampliación.
- Normativa relacionada: CTE DB-HE, tras el cambio de hueco.
- Efecto en cadena: sí — es, literalmente, el efecto empírico #2 de `CHAIN_REASONING.md`.

**69. No verificar orientación desfavorable de un hueco principal**
- Descripción: el hueco de mayor superficie de una pieza principal se orienta a norte sin justificación.
- Por qué ocurre: prioridad de composición de fachada sobre criterio de orientación (`ARCHITECTURAL_PRINCIPLES.md` A.2, `FUNCTIONAL_RELATIONS.md` §7).
- Consecuencias: calidad de luz real inferior a la esperada para una pieza de esa jerarquía.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: alta — ya en producción (`_ORIENTATION_RULES`), condicionado al parámetro de norte declarado.
- Prevención: verificar orientación de piezas principales en fase de anteproyecto.
- Corrección: reorientar el volumen o redistribuir la jerarquía de piezas por fachada.
- Normativa relacionada: ninguna — criterio de calidad, no exigencia.
- Efecto en cadena: no directo.

**70. Confundir ventilación cruzada con doble hueco en la misma fachada**
- Descripción: se declara ventilación cruzada cuando ambos huecos están en la misma orientación, sin diferencia de presión real entre ellos.
- Por qué ocurre: confusión conceptual entre "dos huecos" y "dos orientaciones no paralelas" (`ARCHITECTURAL_PRINCIPLES.md` A.1).
- Consecuencias: ventilación real muy inferior a la asumida.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible hoy sin datos de Hueco individual por fachada.
- Prevención: verificar que los huecos considerados están en fachadas distintas no paralelas.
- Corrección: reorientar o añadir un hueco en fachada distinta si es geométricamente posible.
- Normativa relacionada: ninguna directa en la mayoría de decretos — criterio de calidad.
- Efecto en cadena: no directo.

**71. Ventilación mecánica no contemplada donde hace falta**
- Descripción: una pieza sin posibilidad de ventilación natural (baño interior, cocina cerrada sin patio) no tiene prevista ventilación mecánica.
- Por qué ocurre: verificación de solo la vía natural, sin verificar la vía alternativa cuando la natural no es posible.
- Consecuencias: pieza sin ninguna vía de ventilación viable.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible desde el DXF sin dato de instalación de ventilación mecánica declarado.
- Prevención: verificar explícitamente la vía de ventilación (natural o mecánica) de toda pieza que la requiera.
- Corrección: prever la instalación mecánica correspondiente.
- Normativa relacionada: CTE DB-HS3, RITE.
- Efecto en cadena: no directo.

**72. Reducir la superficie de patio sin recomputar las piezas que vierten a él**
- Descripción: una ampliación posterior reduce el patio sin verificar el efecto sobre todas las piezas que dependen de él para luz/ventilación.
- Por qué ocurre: tratamiento del cambio como local, sin propagar su efecto a todas las piezas que comparten el mismo patio.
- Consecuencias: incumplimiento sobrevenido en piezas que antes cumplían.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no verificable sin un mecanismo de propagación (`CHAIN_REASONING.md`, mismo efecto que el #13).
- Prevención: tratar cualquier cambio de patio como disparador de recomputo de todas las piezas que vierten a él.
- Corrección: restituir la dimensión de patio o compensar con otra solución de iluminación.
- Normativa relacionada: decreto autonómico, dimensión mínima de patio.
- Efecto en cadena: sí, mismo efecto que el error 63.

**73. No verificar profundidad de iluminación respecto al hueco principal**
- Descripción: una pieza muy profunda respecto a su hueco principal cumple el ratio de superficie pero recibe luz real solo en la zona próxima al hueco.
- Por qué ocurre: el ratio hueco/superficie no captura la distribución espacial de esa luz dentro de la pieza.
- Consecuencias: zona interior de la pieza con calidad de luz real muy inferior a la del ratio calculado.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: parcialmente — calculable como relación entre profundidad de la pieza y posición del hueco, sin proxy cerrado en la serie todavía.
- Prevención: verificar profundidad de iluminación, no solo ratio de superficie de hueco, en piezas profundas.
- Corrección: añadir un segundo hueco o reducir la profundidad de la pieza.
- Normativa relacionada: ninguna directa — brecha entre cumplimiento y calidad real.
- Efecto en cadena: no directo.

**74. Confiar en un patio mancomunado sin garantía de edificación futura controlada**
- Descripción: se cuenta con la dimensión actual de un patio compartido con la parcela colindante, sin considerar que esta última puede edificar y reducirlo.
- Por qué ocurre: asumir el estado actual del entorno como permanente sin verificar el planeamiento de la parcela vecina.
- Consecuencias: cumplimiento actual que puede dejar de serlo si la parcela colindante edifica.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: no verificable desde el DXF propio — dato de la parcela colindante.
- Prevención: advertir explícitamente esta limitación cuando el patio es mancomunado (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 4 §8).
- Corrección: no hay corrección de diseño posible sobre la parcela ajena — solo advertencia documentada.
- Normativa relacionada: ninguna directa — riesgo de dependencia de terceros.
- Efecto en cadena: no directo, riesgo latente no accionable por el proyecto propio.

**75. No verificar ventilación de piezas no habitables que la requieren por uso**
- Descripción: una cocina cerrada u otro espacio de generación de humedad/olor no tiene prevista ninguna vía de ventilación pese a no ser Pieza habitable.
- Por qué ocurre: asumir que solo las piezas habitables necesitan ventilación, ignorando exigencias por uso específico.
- Consecuencias: incumplimiento de exigencias de calidad de aire interior no ligadas a habitabilidad.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible sin dato de instalación de ventilación declarado.
- Prevención: verificar exigencias de ventilación por uso específico, no solo por condición de habitable.
- Corrección: prever la instalación correspondiente.
- Normativa relacionada: CTE DB-HS3.
- Efecto en cadena: no directo.

**76. Ampliar una pieza reduciendo proporcionalmente su ratio de hueco**
- Descripción: al ampliar la superficie de una pieza sin ampliar proporcionalmente su hueco, el ratio hueco/superficie cae por debajo del mínimo aunque antes cumplía.
- Por qué ocurre: tratar la ampliación de superficie como un cambio aislado sin recalcular el ratio afectado.
- Consecuencias: incumplimiento sobrevenido por un cambio que, en apariencia, solo mejoraba la pieza.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: verificable por recomputo automático del ratio tras cualquier cambio de superficie.
- Prevención: tratar todo cambio de superficie de pieza habitable como disparador de recomputo del ratio de hueco.
- Corrección: ampliar el hueco proporcionalmente o revertir la ampliación de superficie.
- Normativa relacionada: decreto autonómico, ratio hueco/superficie.
- Efecto en cadena: sí, variante del efecto empírico #2.

**77. Ignorar el efecto de un elemento de protección solar sobre la superficie efectiva de iluminación**
- Descripción: se computa la superficie de hueco bruta sin descontar el efecto de una protección solar fija que reduce la luz efectiva recibida.
- Por qué ocurre: el ratio normativo mide superficie de hueco, no luz efectiva tras protección.
- Consecuencias: cumplimiento normativo con calidad de luz real inferior a la esperada.
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: no reconocible desde el DXF de planta — dato de alzado/sección.
- Prevención: verificar el efecto de cualquier protección solar sobre la luz efectiva, no solo sobre el ratio normativo.
- Corrección: ajustar el dimensionado de la protección solar para equilibrar ambos objetivos (`ARCHITECTURAL_PRINCIPLES.md` A.4).
- Normativa relacionada: ninguna directa — brecha entre cumplimiento y calidad real.
- Efecto en cadena: no directo.

**78. No distinguir exigencia de iluminación de exigencia de ventilación cuando difieren**
- Descripción: variante del error 62 — se asume que ambas exigencias comparten siempre el mismo hueco cuando el decreto exige superficies distintas para cada una.
- Por qué ocurre: simplificación indebida repetida.
- Consecuencias: cumplimiento de una exigencia sin verificar la otra de forma independiente.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no verificable hoy sin Constraint independientes para cada exigencia.
- Prevención: mismo mecanismo que el error 62.
- Corrección: mismo mecanismo que el error 62.
- Normativa relacionada: decreto autonómico, exigencias diferenciadas.
- Efecto en cadena: no directo.

**79. Diseñar una fachada priorizando composición exterior sobre habitabilidad interior**
- Descripción: la composición estética de huecos en fachada se decide antes de verificar el ratio interior mínimo de cada pieza a la que sirve.
- Por qué ocurre: proceso de diseño que trabaja la fachada como elemento autónomo antes de cerrar la distribución interior.
- Consecuencias: incumplimientos de ratio de hueco descubiertos tarde, cuando la composición de fachada ya está decidida.
- Gravedad: Bloqueante (si termina en incumplimiento real).
- Frecuencia: Media.
- Detección: no verificable automáticamente — es un error de proceso, no de estado final.
- Prevención: verificar el ratio interior de cada pieza en paralelo al diseño de fachada, nunca después.
- Corrección: ajustar la composición de fachada para satisfacer los ratios interiores pendientes.
- Normativa relacionada: decreto autonómico, ratio hueco/superficie.
- Efecto en cadena: no directo, pero puede afectar a múltiples piezas simultáneamente si la fachada se rediseña por completo.

**80. No revisar el ratio de hueco tras fusionar o dividir piezas**
- Descripción: al fusionar dos piezas (Salón + Cocina en planta abierta) o dividirlas, el ratio de hueco/superficie no se recalcula sobre la nueva geometría resultante.
- Por qué ocurre: tratamiento de la fusión/división como cambio puramente distributivo, sin recomputar ratios dependientes.
- Consecuencias: incumplimiento sobrevenido en la pieza resultante.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: verificable por recomputo automático tras cualquier cambio de geometría de pieza.
- Prevención: tratar toda fusión/división de piezas como disparador de recomputo completo de ratios.
- Corrección: recalcular y ajustar hueco si es necesario.
- Normativa relacionada: decreto autonómico, ratio hueco/superficie.
- Efecto en cadena: sí, relacionado con el error 21/52.

---

## Categoría 5 — Accesibilidad (20)

**81. Itinerario accesible interrumpido en un punto aislado**
- Descripción: el recorrido cumple el ancho mínimo en la mayor parte de su trayecto salvo en un tramo puntual.
- Por qué ocurre: verificación por muestreo o por tramos aislados en vez de continuidad completa (`ARCHITECTURAL_ONTOLOGY.md` E.2).
- Consecuencias: itinerario no accesible en la práctica pese a que la mayoría de sus tramos sí cumplen.
- Gravedad: Bloqueante.
- Frecuencia: Alta — es, según `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 5 §5, el fallo más habitual en proyectos reales.
- Detección: no reconocible con fiabilidad sin un grafo de circulación conectado (`ARCHITECTURAL_ONTOLOGY.md` E.1).
- Prevención: verificar el itinerario completo de extremo a extremo, nunca por muestreo.
- Corrección: corregir el tramo estrecho concreto.
- Normativa relacionada: CTE DB-SUA, itinerario accesible.
- Efecto en cadena: no directo, contenido al tramo afectado si se corrige a tiempo.

**82. Ancho de itinerario inferior al mínimo en un tramo no verificado**
- Descripción: variante concreta del error 81 — un mueble fijo, un elemento estructural o un cambio de tabiquería reduce el ancho en un punto que no se comprobó.
- Por qué ocurre: verificación del ancho nominal de diseño sin comprobar obstrucciones puntuales reales.
- Consecuencias: mismo tipo que el error 81.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: parcialmente — calculable geométricamente si el elemento que obstruye está representado en el DXF.
- Prevención: verificar el ancho real en todo el trayecto, incluyendo elementos fijos.
- Corrección: reubicar el elemento que obstruye o ampliar el tramo.
- Normativa relacionada: CTE DB-SUA.
- Efecto en cadena: no directo.

**83. Espacio de giro insuficiente ante puerta de baño accesible**
- Descripción: el baño destinado a ser accesible no dispone del espacio de giro mínimo exigido.
- Por qué ocurre: dimensionado del baño por superficie total sin verificar la geometría específica de giro.
- Consecuencias: incumplimiento directo del baño accesible exigido.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: alta — ya en producción (`evaluate_bathroom_accessibility`).
- Prevención: verificar geometría de giro desde el primer boceto del baño destinado a ser accesible.
- Corrección: redistribuir el baño o ampliarlo.
- Normativa relacionada: CTE DB-SUA.
- Efecto en cadena: no directo.

**84. No verificar continuidad de extremo a extremo**
- Descripción: variante general del error 81 — se verifica la accesibilidad de tramos individuales sin verificar el recorrido completo como una única secuencia.
- Por qué ocurre: falta de un modelo de itinerario conectado (mismo origen que el 81).
- Consecuencias: mismo tipo que el error 81, a nivel de metodología de verificación, no de caso concreto.
- Gravedad: Bloqueante.
- Frecuencia: Alta.
- Detección: no reconocible con fiabilidad hoy.
- Prevención: mismo mecanismo que el error 81.
- Corrección: mismo mecanismo que el error 81.
- Normativa relacionada: CTE DB-SUA.
- Efecto en cadena: no directo.

**85. Exigir o eximir itinerario accesible interior según tipología incorrecta**
- Descripción: se aplica la exigencia de itinerario accesible interior de vivienda plurifamiliar a una unifamiliar donde no aplica igual, o al revés.
- Por qué ocurre: mismo origen que el error 16 — fallo de propagación de tipología.
- Consecuencias: sobre-exigencia o incumplimiento no detectado, según el sentido del error.
- Gravedad: Bloqueante.
- Frecuencia: Media (mientras el Bug #1 no se corrija).
- Detección: alta — verificable en cuanto la tipología se propaga correctamente.
- Prevención: mismo mecanismo que el error 16.
- Corrección: mismo mecanismo que el error 16.
- Normativa relacionada: CTE DB-SUA, exigencia diferenciada por tipología.
- Efecto en cadena: sí, mismo alcance que el error 16 para el Dominio 5.

**86. Pendiente de rampa superior a la máxima**
- Descripción: una rampa de acceso o de garaje supera la pendiente máxima admisible según su longitud.
- Por qué ocurre: resolver un desnivel con la longitud disponible sin verificar el límite de pendiente correspondiente.
- Consecuencias: incumplimiento directo, rampa no utilizable con seguridad.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible desde un DXF de planta sin dato de desnivel/sección.
- Prevención: verificar pendiente máxima antes de fijar la longitud disponible de la rampa.
- Corrección: alargar el recorrido de la rampa o introducir un tramo con descanso.
- Normativa relacionada: CTE DB-SUA.
- Efecto en cadena: sí — ya documentado como efecto empírico #19 de `CHAIN_REASONING.md` (alarga el recorrido de evacuación).

**87. No prever ascensor accesible donde se exige por número de plantas**
- Descripción: un edificio que supera el umbral de plantas/ocupantes que exige ascensor no lo contempla.
- Por qué ocurre: asumir la ausencia de ascensor por criterio de coste sin verificar si la normativa lo exige a partir de ese umbral.
- Consecuencias: incumplimiento directo.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: verificable si el número de plantas y el umbral aplicable están correctamente declarados.
- Prevención: verificar el umbral exacto antes de decidir la ausencia de ascensor.
- Corrección: incorporar el ascensor, con el efecto en cadena sobre estructura y superficie que implica.
- Normativa relacionada: CTE DB-SUA, exigencia por número de plantas.
- Efecto en cadena: sí — afecta a superficie disponible en todas las plantas y a continuidad estructural.

**88. Baño accesible fuera de un itinerario también accesible**
- Descripción: el baño cumple sus propias dimensiones de accesibilidad pero se llega a él por un recorrido que no es accesible.
- Por qué ocurre: verificación aislada del baño sin verificar el itinerario completo hasta él (mismo tipo de error que el 81, aplicado específicamente al baño).
- Consecuencias: baño accesible inútil en la práctica.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: no reconocible sin el grafo de circulación completo.
- Prevención: verificar accesibilidad de itinerario y de pieza de destino como una única unidad, nunca por separado.
- Corrección: corregir el tramo del itinerario que rompe la continuidad.
- Normativa relacionada: CTE DB-SUA.
- Efecto en cadena: no directo.

**89. Confundir "accesible" con "adaptado"**
- Descripción: se declara cumplido un nivel de exigencia (adaptado) cuando en realidad solo se cumple el nivel inferior (accesible).
- Por qué ocurre: uso impreciso de ambos términos como sinónimos (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 5, Nivel 3).
- Consecuencias: declaración de cumplimiento incorrecta ante el cliente o el visado.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: no verificable automáticamente sin un catálogo cerrado que distinga ambos niveles.
- Prevención: mantener ambos niveles como valores distintos y cerrados en el catálogo de exigencias.
- Corrección: corregir la declaración al nivel realmente alcanzado.
- Normativa relacionada: CTE DB-SUA, niveles diferenciados.
- Efecto en cadena: no directo, riesgo de visado (categoría 13).

**90. Solución accesible de trámite, no integrada en el diseño**
- Descripción: la solución accesible cumple el mínimo dimensional pero resulta incómoda o estigmatizante en el uso real.
- Por qué ocurre: tratar la accesibilidad como corrección posterior sobre un diseño ya cerrado en vez de como principio de diseño desde el origen (`ARCHITECTURAL_PRINCIPLES.md` C.3).
- Consecuencias: cumplimiento normativo con calidad de integración baja.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible automáticamente — Nivel C, terreno de "espejo, no juez".
- Prevención: incorporar accesibilidad desde el primer boceto, no como ajuste final.
- Corrección: rediseñar la solución con mayor integración, no solo verificar cumplimiento dimensional.
- Normativa relacionada: ninguna directa — brecha entre cumplimiento y calidad de integración.
- Efecto en cadena: no directo.

**91. No coordinar itinerario accesible con recorrido de evacuación**
- Descripción: ambos itinerarios compiten por el mismo espacio disponible sin que se verifique que ambos, simultáneamente, cumplen sus propias exigencias.
- Por qué ocurre: verificación de cada dominio por separado sin verificar la tensión conocida entre ambos (`CHAIN_REASONING.md` §5).
- Consecuencias: uno de los dos, o ambos, terminan incumpliendo.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: no reconocible sin el grafo de circulación conectado.
- Prevención: verificar ambos itinerarios de forma conjunta en cualquier tramo compartido.
- Corrección: redimensionar el tramo compartido para satisfacer ambas exigencias a la vez.
- Normativa relacionada: CTE DB-SUA y DB-SI, tensión conocida entre ambos.
- Efecto en cadena: sí — es exactamente el par de tensión estructural ya documentado en `CHAIN_REASONING.md` §5.

**92. Reducir el ancho de un pasillo accesible al resolver otro conflicto**
- Descripción: para ganar superficie en una pieza adyacente, se reduce el ancho de un pasillo que era accesible.
- Por qué ocurre: resolver un conflicto local (superficie de pieza) sin verificar el efecto sobre el itinerario.
- Consecuencias: incumplimiento sobrevenido de accesibilidad.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: verificable por recomputo automático del ancho tras cualquier cambio de tabiquería adyacente.
- Prevención: tratar todo cambio de tabiquería junto a un itinerario como disparador de recomputo de accesibilidad.
- Corrección: restituir el ancho o buscar superficie en otra pieza.
- Normativa relacionada: CTE DB-SUA.
- Efecto en cadena: sí — es, literalmente, el efecto empírico #1 de `CHAIN_REASONING.md`.

**93. No prever accesibilidad en zonas comunes exteriores**
- Descripción: el itinerario accesible se verifica solo dentro del edificio, sin verificar el tramo exterior (desde el acceso a la parcela hasta el portal).
- Por qué ocurre: alcance de verificación limitado al DXF de planta interior, sin considerar la urbanización exterior.
- Consecuencias: itinerario interior accesible con un tramo exterior no accesible que invalida el conjunto.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: no reconocible desde el DXF de distribución interior — requiere datos de urbanización de parcela.
- Prevención: verificar el itinerario completo desde el vial público, no solo desde el portal.
- Corrección: corregir el tramo exterior deficiente.
- Normativa relacionada: CTE DB-SUA.
- Efecto en cadena: no directo, pero invalida la accesibilidad completa si no se corrige.

**94. Vivienda accesible en planta baja sin verificar accesibilidad real del acceso**
- Descripción: se asume que una vivienda en planta baja es automáticamente accesible sin verificar el desnivel real de acceso desde vial.
- Por qué ocurre: asunción de que "planta baja" equivale a "sin desnivel", que no siempre es cierta.
- Consecuencias: vivienda declarada accesible sin serlo en la práctica.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible sin datos de topografía/desnivel de la parcela.
- Prevención: verificar el desnivel real, nunca asumirlo por posición de planta.
- Corrección: incorporar rampa o resolver el desnivel de acceso.
- Normativa relacionada: CTE DB-SUA.
- Efecto en cadena: no directo.

**95. No contemplar instalación futura de ascensor en edificio existente sin él**
- Descripción: en rehabilitación, no se reserva espacio para la instalación futura de un ascensor cuando el edificio no lo tiene y podría necesitarlo.
- Por qué ocurre: foco exclusivo en la exigencia actual sin criterio de previsión a futuro.
- Consecuencias: imposibilidad o alto coste de incorporar ascensor más adelante.
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: no verificable automáticamente — criterio de previsión, no de cumplimiento actual.
- Prevención: reservar espacio de hueco de ascensor en rehabilitaciones de edificios plurifamiliares sin él, cuando sea geométricamente viable.
- Corrección: no aplica una vez construido sin la reserva — es una prevención, no una corrección posterior sencilla.
- Normativa relacionada: ninguna directa — criterio de previsión de futuro-proofing (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 5 §5).
- Efecto en cadena: no directo.

**96. Aplicar criterio de obra nueva a rehabilitación sin margen físico**
- Descripción: se exige el mismo nivel de accesibilidad de obra nueva a una rehabilitación donde la preexistencia lo hace físicamente inviable.
- Por qué ocurre: no verificar el régimen de excepción por imposibilidad técnica o desproporción económica ya contemplado en la normativa para rehabilitación.
- Consecuencias: incumplimiento fabricado sobre una limitación real e inevitable.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable sin el dato de alcance de intervención (mismo origen que el error 23-24).
- Prevención: verificar el régimen de rehabilitación aplicable antes de exigir el nivel de obra nueva.
- Corrección: documentar la justificación de imposibilidad técnica (categoría 13).
- Normativa relacionada: régimen de excepción en rehabilitación.
- Efecto en cadena: no directo.

**97. No verificar altura de mecanismos en piezas accesibles**
- Descripción: interruptores, enchufes o grifería de una pieza accesible se ubican a una altura no alcanzable desde una posición sentada.
- Por qué ocurre: verificación geométrica del espacio libre sin verificar la altura de los elementos de uso.
- Consecuencias: pieza geométricamente accesible pero funcionalmente no usable con autonomía.
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: no reconocible desde un DXF de planta — dato de alzado interior.
- Prevención: verificar altura de mecanismos en fase de proyecto de instalaciones, no solo geometría en planta.
- Corrección: reubicar los mecanismos a la altura correcta.
- Normativa relacionada: CTE DB-SUA.
- Efecto en cadena: no directo.

**98. Espacio de giro obstruido por mobiliario fijo no contemplado**
- Descripción: el espacio de giro cumple en el plano de proyecto pero un elemento de mobiliario fijo previsto (armario empotrado) lo invade en la práctica.
- Por qué ocurre: verificación sobre el plano de distribución sin verificar el plano de amueblamiento fijo previsto.
- Consecuencias: espacio de giro normativamente conforme pero funcionalmente insuficiente.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: no reconocible sin el plano de amueblamiento fijo, ausente del DXF de distribución pura.
- Prevención: verificar el espacio de giro contra el plano de amueblamiento fijo, no solo contra la distribución vacía.
- Corrección: reubicar el mobiliario o ampliar el espacio.
- Normativa relacionada: CTE DB-SUA.
- Efecto en cadena: no directo.

**99. No verificar accesibilidad en cambios de nivel no señalizados**
- Descripción: un escalón aislado o un cambio de nivel de pocos centímetros dentro del itinerario no se identifica como barrera.
- Por qué ocurre: los cambios de nivel pequeños a menudo no se representan con claridad en el DXF de distribución.
- Consecuencias: barrera real no detectada por el sistema ni, con frecuencia, por una revisión superficial del plano.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: no reconocible desde un DXF de planta sin cota de nivel explícita en cada polígono.
- Prevención: verificar cotas de nivel de cada pieza del itinerario, no solo su geometría en planta.
- Corrección: eliminar el escalón o resolverlo con rampa.
- Normativa relacionada: CTE DB-SUA.
- Efecto en cadena: no directo.

**100. Confundir accesibilidad de vivienda con accesibilidad de portal únicamente**
- Descripción: se verifica accesibilidad solo hasta el portal del edificio, sin verificar el itinerario interior hasta cada vivienda.
- Por qué ocurre: alcance de verificación limitado a la zona común más visible, sin extenderlo al interior de cada unidad.
- Consecuencias: accesibilidad declarada del edificio sin que cada vivienda individual la tenga realmente.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: no reconocible sin verificar el itinerario completo hasta cada unidad, mismo origen que el error 84.
- Prevención: extender la verificación de accesibilidad hasta el interior de cada vivienda, no detenerla en zonas comunes.
- Corrección: corregir el tramo interior deficiente.
- Normativa relacionada: CTE DB-SUA, exigencia diferenciada por tipología.
- Efecto en cadena: no directo.

---

## Categoría 6 — Evacuación y seguridad contra incendio (22)

**101. Longitud de recorrido de evacuación superior a la máxima**
- Descripción: la distancia real desde la pieza más alejada hasta una salida supera el máximo admisible según el número de salidas disponibles.
- Por qué ocurre: cálculo sobre distancia en línea recta teórica en vez de sobre la geometría real transitable.
- Consecuencias: incumplimiento directo, riesgo real de seguridad de personas.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: no reconocible con fiabilidad sin el grafo de circulación conectado.
- Prevención: verificar el recorrido real, nunca la distancia teórica, desde el primer boceto de planta.
- Corrección: redistribuir para acortar el recorrido o añadir una salida alternativa.
- Normativa relacionada: CTE DB-SI.
- Efecto en cadena: sí — múltiples efectos empíricos de `CHAIN_REASONING.md` (#3, #6, #19) desembocan en este incumplimiento.

**102. Ancho de salida insuficiente para la ocupación calculada**
- Descripción: el ancho de la salida no es suficiente para la ocupación real del sector que sirve.
- Por qué ocurre: cálculo de ocupación incorrecto o ancho de salida fijado sin recomputar tras un cambio de uso o superficie.
- Consecuencias: incumplimiento directo.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible sin datos de ocupación y uso completos por sector.
- Prevención: recalcular el ancho de salida tras cualquier cambio de uso o superficie del sector.
- Corrección: ampliar la salida o reducir la ocupación del sector.
- Normativa relacionada: CTE DB-SI.
- Efecto en cadena: sí, relacionado con el error 35 (cambio de uso sobrevenido).

**103. Cálculo de ocupación incorrecto**
- Descripción: la ocupación estimada de un sector no corresponde a la superficie o el uso real.
- Por qué ocurre: aplicar el coeficiente de ocupación de un uso distinto al real, o superficie desactualizada tras un cambio.
- Consecuencias: toda la cadena de evacuación (ancho de salida, número de salidas, longitud máxima) calculada sobre una base incorrecta.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: parcialmente — verificable si el uso y la superficie de cada sector están correctamente reconocidos.
- Prevención: recomputar ocupación tras cualquier cambio de uso o superficie.
- Corrección: recalcular toda la cadena de exigencias de evacuación con la ocupación correcta.
- Normativa relacionada: CTE DB-SI, tablas de ocupación por uso.
- Efecto en cadena: sí, el de mayor alcance dentro de esta categoría.

**104. Sectorización de incendio insuficiente entre usos distintos**
- Descripción: dos usos distintos del mismo edificio (residencial y terciario en planta baja) no están sectorizados con la resistencia al fuego exigida entre ambos.
- Por qué ocurre: verificación de cada uso por separado sin verificar la compartimentación que los separa.
- Consecuencias: incumplimiento directo, riesgo real de propagación de incendio entre usos.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible sin datos de composición constructiva — mismo límite estructural que `ARCHITECTURAL_ONTOLOGY.md` F.2.
- Prevención: verificar sectorización desde el primer boceto que combine usos distintos.
- Corrección: reforzar la compartimentación entre sectores.
- Normativa relacionada: CTE DB-SI.
- Efecto en cadena: no directo, pero de alta gravedad si se descubre tarde.

**105. Compartimentación interrumpida por un patinillo sin sellado**
- Descripción: un patinillo de instalaciones atraviesa una compartimentación de sector sin el sellado exigido.
- Por qué ocurre: coordinación deficiente entre proyecto de arquitectura y proyecto de instalaciones.
- Consecuencias: vía de propagación de incendio no prevista.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: no reconocible desde el DXF de distribución — dato de instalaciones y detalle constructivo.
- Prevención: coordinar la posición de patinillos con la sectorización desde el proyecto básico.
- Corrección: sellar el paso del patinillo con el sistema constructivo adecuado.
- Normativa relacionada: CTE DB-SI.
- Efecto en cadena: sí — ya señalado como punto de fricción habitual en `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 6 §6.

**106. Escalera no protegida donde se exige por altura de evacuación**
- Descripción: la escalera del edificio no tiene el nivel de protección contra incendio exigido según la altura de evacuación real.
- Por qué ocurre: verificar el tipo de escalera sin recalcular la altura de evacuación real del edificio completo.
- Consecuencias: incumplimiento directo, riesgo real de seguridad.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible con un único DXF de planta — requiere el conjunto de plantas del edificio.
- Prevención: verificar la altura de evacuación total antes de decidir el tipo de escalera.
- Corrección: reforzar la protección de la escalera existente.
- Normativa relacionada: CTE DB-SI.
- Efecto en cadena: sí — afecta a estructura y a superficie disponible en todas las plantas si hay que ampliar la caja de escalera.

**107. Recorrido medido en línea recta teórica**
- Descripción: variante específica del error 101 — el cálculo de longitud usa la distancia euclídea entre dos puntos en vez del recorrido real transitable.
- Por qué ocurre: simplificación de cálculo sin modelar la geometría real del recorrido.
- Consecuencias: subestimación sistemática de la longitud real de evacuación.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: no reconocible sin el grafo de circulación conectado, mismo origen que el error 101.
- Prevención: modelar siempre el recorrido real, nunca la distancia en línea recta.
- Corrección: recalcular con el recorrido real.
- Normativa relacionada: CTE DB-SI.
- Efecto en cadena: no directo, es la causa metodológica del error 101.

**108. No recalcular ocupación tras un cambio de uso de pieza**
- Descripción: una pieza cambia de uso sin que se recalcule la ocupación del sector al que pertenece.
- Por qué ocurre: mismo origen que el error 35, aplicado específicamente al cómputo de ocupación.
- Consecuencias: toda la cadena de exigencias de evacuación queda desactualizada.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: no verificable sin recomputo automático disparado por cambio de uso.
- Prevención: tratar todo cambio de uso como disparador de recomputo de ocupación y evacuación.
- Corrección: recalcular toda la cadena de evacuación.
- Normativa relacionada: CTE DB-SI.
- Efecto en cadena: sí, es una consecuencia directa del error 35.

**109. Confundir itinerario accesible con recorrido de evacuación en un mismo tramo**
- Descripción: se asume que un tramo que cumple accesibilidad cumple automáticamente evacuación, o al revés, sin verificar ambos por separado.
- Por qué ocurre: ambos comparten a menudo el mismo espacio físico pero tienen exigencias distintas (mismo par que el error 91).
- Consecuencias: uno de los dos incumple sin que se detecte.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: no reconocible sin verificar ambos itinerarios de forma independiente sobre el mismo tramo.
- Prevención: verificar ambas exigencias siempre por separado, aunque compartan geometría.
- Corrección: redimensionar el tramo para satisfacer ambas.
- Normativa relacionada: CTE DB-SUA y DB-SI.
- Efecto en cadena: sí, mismo par que el error 91.

**110. Puerta de salida que abre en sentido contrario al de evacuación**
- Descripción: una puerta en el recorrido de evacuación abre hacia el interior del recorrido en vez de en el sentido de salida.
- Por qué ocurre: criterio de diseño de puertas decidido sin verificar el sentido de evacuación exigido.
- Consecuencias: obstrucción real del recorrido en caso de evacuación real con flujo de personas.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible desde el DXF sin dato de sentido de apertura de puerta, ausente del pipeline actual (mismo límite que Hueco, `ARCHITECTURAL_ONTOLOGY.md` D.4).
- Prevención: verificar sentido de apertura de toda puerta en recorrido de evacuación.
- Corrección: invertir el sentido de apertura.
- Normativa relacionada: CTE DB-SI.
- Efecto en cadena: no directo.

**111. No prever salidas alternativas suficientes**
- Descripción: el sector solo dispone de una salida cuando su ocupación exige más de una alternativa.
- Por qué ocurre: verificación de ancho de salida sin verificar el número mínimo de salidas exigido según ocupación.
- Consecuencias: incumplimiento directo.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: parcialmente — verificable si la ocupación del sector está correctamente calculada.
- Prevención: verificar número mínimo de salidas junto con el ancho, nunca por separado.
- Corrección: incorporar una salida adicional.
- Normativa relacionada: CTE DB-SI.
- Efecto en cadena: no directo.

**112. Resistencia al fuego de compartimentación no verificada por falta de datos**
- Descripción: se declara cumplida la sectorización sin dato real de la composición constructiva de la partición.
- Por qué ocurre: ausencia estructural de datos constructivos en un plano de distribución 2D (`ARCHITECTURAL_ONTOLOGY.md` F.3).
- Consecuencias: afirmación de cumplimiento no verificable honestamente.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no reconocible en absoluto sin datos constructivos, límite estructural reconocido explícitamente.
- Prevención: declarar la limitación de confianza en vez de afirmar cumplimiento sin dato real (`UNCERTAINTY_MODEL.md`).
- Corrección: obtener el dato constructivo real antes de certificar cumplimiento.
- Normativa relacionada: CTE DB-SI.
- Efecto en cadena: no directo, riesgo de visado si se afirma sin base (categoría 13).

**113. Sectorización de garaje insuficiente**
- Descripción: el garaje colectivo, uso de riesgo especial, no está sectorizado con la resistencia exigida respecto a las plantas residenciales.
- Por qué ocurre: tratamiento del garaje como espacio técnico menor sin verificar su régimen normativo propio y reforzado.
- Consecuencias: incumplimiento directo, riesgo real elevado por la naturaleza del uso.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible sin datos constructivos.
- Prevención: verificar el régimen de riesgo especial del garaje desde el primer boceto.
- Corrección: reforzar la compartimentación entre garaje y plantas residenciales.
- Normativa relacionada: CTE DB-SI, uso de riesgo especial.
- Efecto en cadena: no directo.

**114. Cómputo de ocupación combinado incorrecto en uso mixto**
- Descripción: en un edificio con residencial y terciario, se suma o se separa incorrectamente la ocupación de ambos usos.
- Por qué ocurre: ausencia de un criterio único y verificado de cómputo combinado (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 6 §8, caso sin criterio único).
- Consecuencias: exigencias de evacuación calculadas sobre una base incorrecta.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no verificable sin un criterio de cómputo cerrado y documentado.
- Prevención: fijar y documentar el criterio de cómputo combinado adoptado.
- Corrección: recalcular con el criterio correcto y documentar la justificación.
- Normativa relacionada: CTE DB-SI, tablas de ocupación.
- Efecto en cadena: no directo.

**115. No considerar el efecto de una ampliación sobre la ocupación total**
- Descripción: una ampliación de superficie no se traduce en un recomputo de la ocupación total del sector o del edificio.
- Por qué ocurre: tratar la ampliación como cambio puramente dimensional sin recomputar ocupación.
- Consecuencias: exigencias de evacuación desactualizadas tras la ampliación.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: verificable por recomputo automático tras cualquier cambio de superficie.
- Prevención: tratar toda ampliación como disparador de recomputo de ocupación.
- Corrección: recalcular toda la cadena de evacuación.
- Normativa relacionada: CTE DB-SI.
- Efecto en cadena: sí, mismo tipo que el error 108.

**116. Cerrar circulación abierta sin recalcular el recorrido de evacuación**
- Descripción: se cierra una zona de circulación previamente abierta (por sectorización u otro motivo) sin verificar el nuevo recorrido de evacuación resultante.
- Por qué ocurre: tratamiento del cierre como cambio de calidad espacial sin verificar su efecto normativo en evacuación.
- Consecuencias: recorrido de evacuación alargado o bloqueado sin detectarlo.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible sin el grafo de circulación conectado.
- Prevención: tratar todo cierre de circulación como disparador de recomputo de evacuación.
- Corrección: verificar y, si hace falta, prever una salida alternativa.
- Normativa relacionada: CTE DB-SI.
- Efecto en cadena: sí — es, literalmente, el efecto empírico #14 de `CHAIN_REASONING.md`, aquí visto desde el lado de evacuación en vez de calidad espacial.

**117. No verificar continuidad de la escalera protegida entre todas las plantas**
- Descripción: la escalera es protegida en algunas plantas pero pierde esa condición en un tramo concreto.
- Por qué ocurre: verificación planta a planta sin verificar la continuidad completa del elemento.
- Consecuencias: protección contra incendio ineficaz por el tramo débil.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible con un único DXF de planta.
- Prevención: verificar siempre el conjunto completo de plantas para elementos de protección continua.
- Corrección: reforzar el tramo débil.
- Normativa relacionada: CTE DB-SI.
- Efecto en cadena: no directo.

**118. Rampa que alarga el recorrido de evacuación medido desde piezas alejadas**
- Descripción: incorporar una rampa para resolver un desnivel de acceso consume longitud de recorrido que puede superar el máximo de evacuación desde las piezas más alejadas.
- Por qué ocurre: resolver el problema de accesibilidad sin verificar el efecto sobre evacuación (mismo par que el error 91, en sentido inverso).
- Consecuencias: incumplimiento de evacuación sobrevenido por resolver accesibilidad.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible sin el grafo de circulación conectado.
- Prevención: verificar el efecto sobre evacuación de cualquier rampa incorporada por accesibilidad.
- Corrección: buscar una solución de accesibilidad alternativa con menor coste de recorrido.
- Normativa relacionada: CTE DB-SI y DB-SUA, tensión conocida.
- Efecto en cadena: sí — es, literalmente, el efecto empírico #19 de `CHAIN_REASONING.md`.

**119. No prever protección de recorridos de evacuación frente a humo**
- Descripción: el recorrido de evacuación no dispone de las medidas de control de humo exigidas según su tipo y longitud.
- Por qué ocurre: foco en dimensiones geométricas del recorrido sin verificar exigencias de instalaciones de protección asociadas.
- Consecuencias: incumplimiento directo, riesgo real elevado (el humo es, con frecuencia, más letal que el propio fuego en una evacuación real).
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible desde el DXF de distribución — dato de instalaciones.
- Prevención: verificar exigencias de control de humo junto con las dimensionales.
- Corrección: incorporar la instalación de control de humo exigida.
- Normativa relacionada: CTE DB-SI.
- Efecto en cadena: no directo.

**120. Reducir ancho de escalera común al resolver otro conflicto**
- Descripción: para ganar superficie privativa a costa del rellano, se reduce el ancho de la escalera común por debajo del mínimo.
- Por qué ocurre: resolver un conflicto local de superficie sin verificar el efecto sobre el elemento común compartido.
- Consecuencias: incumplimiento de evacuación y accesibilidad común simultáneo.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: verificable por recomputo automático del ancho tras cualquier cambio de superficie privativa adyacente.
- Prevención: tratar todo cambio de superficie junto a un elemento común como disparador de recomputo.
- Corrección: restituir el ancho común.
- Normativa relacionada: CTE DB-SI y DB-SUA.
- Efecto en cadena: sí — es, literalmente, el efecto empírico #6 de `CHAIN_REASONING.md`.

**121. No verificar exigencia de evacuación de garaje como uso de riesgo especial**
- Descripción: el garaje se evalúa con el mismo criterio de evacuación que un uso residencial ordinario, sin aplicar el régimen reforzado de riesgo especial.
- Por qué ocurre: desconocimiento o simplificación indebida del régimen diferenciado del garaje.
- Consecuencias: incumplimiento directo.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible sin catálogo de uso específico para Garaje colectivo (`SPACE_TAXONOMY.md` 8.2).
- Prevención: aplicar siempre el régimen de riesgo especial cuando el uso corresponde a garaje.
- Corrección: recalcular con el régimen correcto.
- Normativa relacionada: CTE DB-SI, uso de riesgo especial.
- Efecto en cadena: no directo.

**122. Confiar en una solución de evacuación ya validada sin re-verificarla tras un cambio**
- Descripción: una solución de evacuación aprobada en una fase anterior del proyecto se sigue considerando válida tras cambios posteriores que la afectan.
- Por qué ocurre: falta de un mecanismo de re-propagación automática tras cada cambio (mismo origen que varios errores de esta categoría).
- Consecuencias: solución obsoleta presentada como vigente.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: no verificable sin recomputo automático disparado por cada Change relevante.
- Prevención: tratar toda solución de evacuación como dependiente y sujeta a recomputo tras cualquier cambio geométrico relevante, nunca como validada de forma permanente.
- Corrección: re-verificar completamente antes de dar por buena la solución final.
- Normativa relacionada: CTE DB-SI.
- Efecto en cadena: sí, agregado de todos los efectos de cadena no propagados de esta categoría.

---

## Categoría 7 — Acústica (18)

**123. Dormitorio adyacente a caja de escalera sin refuerzo**
- Descripción: un dormitorio comparte partición directa con la escalera común sin refuerzo acústico.
- Por qué ocurre: distribución que no considera el criterio de composición de ruido (`FUNCTIONAL_RELATIONS.md` §5) al ubicar dormitorios junto a zonas comunes.
- Consecuencias: molestia acústica real por ruido de paso de vecinos.
- Gravedad: Riesgo variable.
- Frecuencia: Alta — de los pares de adyacencia crítica más frecuentes según `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 7 §5.
- Detección: alta — verificable por adyacencia geométrica entre polígono de Dormitorio y de Escalera, con tolerancia a huecos de plano (mismo mecanismo que `evaluator._is_adjacent`).
- Prevención: verificar adyacencias críticas en fase de distribución, antes de cerrar la posición de dormitorios.
- Corrección: reubicar el dormitorio o reforzar la partición.
- Normativa relacionada: CTE DB-HR.
- Efecto en cadena: no directo, contenido a la adyacencia.

**124. Dormitorio adyacente a cuarto de instalaciones sin refuerzo**
- Descripción: variante del error 123 con Espacio técnico (`ARCHITECTURAL_ONTOLOGY.md` C.5) en vez de escalera.
- Por qué ocurre: mismo origen que el 123.
- Consecuencias: molestia acústica por vibración/ruido de equipos, potencialmente peor que el caso de escalera por ser continuo, no puntual.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: alta, mismo mecanismo que el error 123.
- Prevención: mismo mecanismo que el error 123.
- Corrección: mismo mecanismo que el error 123.
- Normativa relacionada: CTE DB-HR.
- Efecto en cadena: no directo.

**125. Partición entre unidades sin verificar composición constructiva**
- Descripción: se declara cumplido el aislamiento acústico exigido entre unidades independientes sin conocer la composición real de la partición.
- Por qué ocurre: ausencia estructural de datos constructivos en un DXF de distribución 2D.
- Consecuencias: afirmación de cumplimiento no verificable honestamente — mismo tipo de riesgo que el error 112.
- Gravedad: Riesgo variable.
- Frecuencia: Alta.
- Detección: no reconocible en absoluto sin datos constructivos — límite estructural ya reconocido explícitamente en `ARCHITECTURAL_ONTOLOGY.md` D.1 y `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 7 §10.
- Prevención: declarar riesgo de adyacencia, nunca certeza de cumplimiento, sin dato constructivo real.
- Corrección: obtener el dato constructivo antes de certificar.
- Normativa relacionada: CTE DB-HR.
- Efecto en cadena: no directo.

**126. Eliminar un muro de compartimentación acústica al abrir un espacio**
- Descripción: se elimina el muro entre Salón y Cocina (o entre unidades) para abrir el espacio sin verificar el efecto sobre la compartimentación acústica que sostenía.
- Por qué ocurre: decisión de diseño (planta abierta) tomada sin verificar su efecto acústico normativo, cuando el muro eliminado separaba unidades independientes.
- Consecuencias: pérdida de aislamiento acústico exigido frente a la unidad o zona colindante.
- Gravedad: Bloqueante (si la partición eliminada separaba unidades independientes) / Recomendable (si es interior a la misma unidad, ver `FUNCTIONAL_RELATIONS.md` §5, excepción).
- Frecuencia: Media.
- Detección: no reconocible sin datos de qué unidad está a cada lado de la partición eliminada.
- Prevención: verificar si la partición a eliminar separa unidades independientes antes de aprobar la apertura.
- Corrección: restituir la compartimentación o compensar con otra solución constructiva.
- Normativa relacionada: CTE DB-HR, si aplica entre unidades.
- Efecto en cadena: sí — es, literalmente, el efecto empírico #4 de `CHAIN_REASONING.md`.

**127. Patinillo compartido entre unidades sin verificar fuga acústica**
- Descripción: un patinillo de instalaciones compartido entre dos unidades independientes actúa como vía de transmisión de ruido no prevista.
- Por qué ocurre: foco en la viabilidad de instalaciones (Dominio 10) sin verificar el efecto acústico del propio patinillo (Dominio 7).
- Consecuencias: transmisión de ruido entre unidades a través de una vía no evidente en el plano de distribución.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no reconocible desde el DXF de distribución sin datos de instalaciones.
- Prevención: verificar el efecto acústico de todo patinillo compartido entre unidades distintas.
- Corrección: sellar/aislar el patinillo en el tramo compartido.
- Normativa relacionada: CTE DB-HR.
- Efecto en cadena: no directo, aunque tensiona con Dominio 10.

**128. No verificar adyacencia acústica con tolerancia geométrica real**
- Descripción: dos piezas que en la práctica son adyacentes (con un hueco de plano pequeño entre sus polígonos) no se detectan como tales por una verificación de intersección geométrica estricta.
- Por qué ocurre: los planos reales rara vez tienen polígonos perfectamente contiguos; un criterio de adyacencia sin tolerancia pierde casos reales.
- Consecuencias: adyacencias críticas reales no detectadas.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: alta — ya mitigado en producción (`evaluator._is_adjacent`, con tolerancia de distancia), aunque `ARCHITECTURAL_ONTOLOGY.md` D.1 señala que sigue siendo un problema activo a vigilar en `circulation._rooms_are_connected`, una segunda implementación equivalente pendiente de unificar (`REFACTOR_MASTERPLAN.md` tarea relacionada).
- Prevención: mantener un único criterio de adyacencia con tolerancia, no duplicado entre módulos.
- Corrección: unificar el criterio de tolerancia entre todos los módulos que lo necesiten.
- Normativa relacionada: CTE DB-HR.
- Efecto en cadena: no directo.

**129. Confiar en el cumplimiento sin dato de composición constructiva real**
- Descripción: variante general de los errores 112 y 125 — cualquier afirmación de cumplimiento acústico sin dato constructivo real.
- Por qué ocurre: presión por dar una respuesta definitiva cuando el dato disponible no la sostiene.
- Consecuencias: afirmación no honesta, riesgo de responsabilidad profesional si se descubre después.
- Gravedad: Riesgo variable.
- Frecuencia: Alta.
- Detección: no reconocible, límite estructural reconocido.
- Prevención: declarar siempre riesgo de adyacencia en vez de certeza cuando falta el dato (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 7 §8).
- Corrección: obtener el dato o mantener la declaración de riesgo, nunca elevarla a certeza sin base.
- Normativa relacionada: CTE DB-HR.
- Efecto en cadena: no directo.

**130. Ampliar un hueco hacia fachada ruidosa sin verificar aislamiento**
- Descripción: se amplía un hueco de iluminación en una fachada con ruido exterior significativo sin verificar el efecto sobre el aislamiento acústico de fachada.
- Por qué ocurre: tratamiento aislado del Dominio 4 sin verificar la tensión con Dominio 7 (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 4 §6).
- Consecuencias: mejora de iluminación a costa de un empeoramiento acústico no advertido.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: parcialmente, si se conoce el nivel de ruido exterior de la fachada afectada (dato habitualmente no disponible en el DXF).
- Prevención: verificar exposición a ruido exterior antes de ampliar cualquier hueco.
- Corrección: reforzar el aislamiento del hueco ampliado (doble acristalamiento reforzado, por ejemplo).
- Normativa relacionada: CTE DB-HR.
- Efecto en cadena: no directo.

**131. Reforzar aislamiento sin verificar el efecto en superficie útil**
- Descripción: al reforzar una partición para mejorar aislamiento acústico (más masa, más grosor), se reduce la superficie útil de las piezas colindantes sin recomputarla.
- Por qué ocurre: tratamiento del refuerzo acústico como cambio puramente técnico sin verificar su efecto dimensional.
- Consecuencias: incumplimiento de superficie mínima sobrevenido en la pieza colindante.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: verificable por recomputo automático de superficie tras cualquier cambio de grosor de partición.
- Prevención: tratar todo refuerzo de partición como disparador de recomputo de superficie de piezas colindantes.
- Corrección: verificar y compensar la pérdida de superficie si es crítica.
- Normativa relacionada: CTE DB-HR y decreto de habitabilidad, tensión conocida.
- Efecto en cadena: sí — es, literalmente, el efecto empírico #15 de `CHAIN_REASONING.md`.

**132. No prever adyacencia crítica con salón de la unidad vecina**
- Descripción: un dormitorio queda adyacente al Salón de la vivienda colindante, con uso horario incompatible (descanso vs. actividad social nocturna).
- Por qué ocurre: verificación de adyacencias críticas limitada a piezas técnicas, sin considerar el uso horario real de la pieza vecina.
- Consecuencias: molestia acústica por incompatibilidad de horario de uso, no solo de tipo de ruido.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: parcialmente, requiere conocer el uso de ambas piezas a cada lado de la partición.
- Prevención: verificar adyacencias críticas también entre unidades, no solo dentro de la misma vivienda.
- Corrección: reubicar o reforzar acústicamente.
- Normativa relacionada: CTE DB-HR.
- Efecto en cadena: no directo.

**133. Ignorar el ruido de instalaciones sobre dormitorios adyacentes**
- Descripción: un ascensor o una bomba de instalación genera vibración/ruido sobre un dormitorio adyacente sin que se prevea aislamiento específico.
- Por qué ocurre: tratamiento del ruido de instalaciones como asunto exclusivo del Dominio 10, sin verificar su efecto acústico sobre Dominio 7.
- Consecuencias: molestia acústica real de fuente mecánica, distinta y con frecuencia peor que la de origen humano.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: parcialmente, si la posición de la instalación mecánica está declarada.
- Prevención: verificar adyacencia de dormitorios respecto a cualquier instalación mecánica generadora de vibración.
- Corrección: reubicar la instalación o el dormitorio, o interponer aislamiento específico antivibratorio.
- Normativa relacionada: CTE DB-HR.
- Efecto en cadena: no directo.

**134. No distinguir riesgo de adyacencia de certificación real**
- Descripción: se comunica al cliente una adyacencia de riesgo como si fuera una certificación de incumplimiento o cumplimiento real.
- Por qué ocurre: simplificación indebida en la comunicación del resultado, perdiendo el matiz de incertidumbre real (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 7 §10).
- Consecuencias: expectativa incorrecta del cliente sobre la certeza de la afirmación.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable automáticamente — error de comunicación, no de cálculo.
- Prevención: mantener siempre el vocabulario de riesgo distinguido del de certeza (`EXPLANATION_ENGINE.md` §2).
- Corrección: corregir la comunicación al nivel de certeza real.
- Normativa relacionada: ninguna directa — error de comunicación.
- Efecto en cadena: no directo.

**135. Aceptar una adyacencia de riesgo sin recomendar refuerzo preventivo**
- Descripción: se identifica una adyacencia de riesgo acústico pero no se recomienda ningún refuerzo constructivo preventivo.
- Por qué ocurre: limitar la respuesta a "detectar" sin llegar a "recomendar" (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 7 §5).
- Consecuencias: oportunidad perdida de mitigar un riesgo real conocido a bajo coste en fase de proyecto.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: alta, una vez detectada la adyacencia (mismo mecanismo que el error 123).
- Prevención: acompañar toda detección de adyacencia crítica con una recomendación de refuerzo.
- Corrección: incorporar la recomendación en fase de proyecto, antes de obra.
- Normativa relacionada: ninguna directa — recomendación de buena práctica.
- Efecto en cadena: no directo.

**136. No verificar aislamiento a ruido de impactos entre forjados**
- Descripción: se verifica aislamiento a ruido aéreo entre unidades sin verificar, por separado, el aislamiento a ruido de impactos del forjado que las separa verticalmente.
- Por qué ocurre: tratamiento de "aislamiento acústico" como una única exigencia cuando en realidad son dos exigencias distintas (aéreo e impactos).
- Consecuencias: cumplimiento de una exigencia sin verificar la otra.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible sin datos constructivos del forjado.
- Prevención: mantener ambas exigencias como Constraint independientes.
- Corrección: verificar cada una por separado.
- Normativa relacionada: CTE DB-HR.
- Efecto en cadena: no directo.

**137. Cocina abierta adyacente a dormitorio sin advertir el riesgo**
- Descripción: en una planta abierta (Salón-comedor-cocina), la pieza fusionada resultante es adyacente a un dormitorio sin que se advierta el riesgo acústico agravado respecto a una cocina cerrada.
- Por qué ocurre: la fusión de piezas (decisión de programa legítima, `SPACE_TAXONOMY.md` 1.3) no dispara automáticamente una revisión de adyacencias acústicas de la nueva pieza resultante.
- Consecuencias: riesgo acústico mayor del que existiría con cocina cerrada, sin que se comunique al cliente.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: parcialmente, verificable si la fusión de piezas se reconoce y se recalculan las adyacencias de la pieza resultante.
- Prevención: recalcular adyacencias acústicas tras cualquier fusión de piezas.
- Corrección: reforzar la partición hacia el dormitorio afectado.
- Normativa relacionada: ninguna directa entre piezas de la misma unidad — criterio de calidad (`FUNCTIONAL_RELATIONS.md` §5).
- Efecto en cadena: no directo.

**138. No considerar tiempo de reverberación en zonas comunes**
- Descripción: una zona común de uso prolongado (portal, sala de comunidad) no verifica su tiempo de reverberación.
- Por qué ocurre: foco casi exclusivo en aislamiento entre unidades, sin considerar la calidad acústica interna de espacios comunes.
- Consecuencias: espacio común de calidad acústica interna deficiente (eco, ruido acumulado).
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: no reconocible desde el DXF de distribución — dato de materiales y volumen del espacio.
- Prevención: considerar el tiempo de reverberación en el diseño de acabados de zonas comunes de uso prolongado.
- Corrección: incorporar materiales absorbentes.
- Normativa relacionada: CTE DB-HR, en su caso aplicable.
- Efecto en cadena: no directo.

**139. Confiar en distancia geométrica sin considerar la vía de transmisión real**
- Descripción: se asume que dos piezas alejadas en planta no tienen riesgo acústico, ignorando que el ruido puede transmitirse por una vía indirecta (patinillo, forjado, estructura).
- Por qué ocurre: verificación limitada a adyacencia directa en planta, sin considerar vías de transmisión indirectas.
- Consecuencias: riesgo acústico real no detectado por estar geométricamente alejado en planta.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: no reconocible sin datos de instalaciones y de estructura compartida.
- Prevención: considerar vías de transmisión indirectas (patinillos, estructura), no solo adyacencia directa.
- Corrección: sellar o aislar la vía de transmisión indirecta identificada.
- Normativa relacionada: CTE DB-HR.
- Efecto en cadena: no directo.

**140. No revisar adyacencias acústicas tras una redistribución interior**
- Descripción: una redistribución completa de la vivienda no dispara una revisión de las adyacencias acústicas resultantes.
- Por qué ocurre: tratamiento de la redistribución como cambio puramente funcional/dimensional, sin recomputar adyacencias críticas.
- Consecuencias: nuevas adyacencias de riesgo no detectadas tras el cambio.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: verificable por recomputo automático de adyacencias tras cualquier cambio significativo de tabiquería.
- Prevención: tratar toda redistribución relevante como disparador de recomputo de adyacencias acústicas.
- Corrección: verificar y reforzar las adyacencias de riesgo resultantes.
- Normativa relacionada: CTE DB-HR.
- Efecto en cadena: sí, agregado de varios efectos empíricos de `CHAIN_REASONING.md`.

---

## Categoría 8 — Eficiencia energética y envolvente térmica (18)

**141. No usar la zona climática real del emplazamiento**
- Descripción: el comportamiento térmico se evalúa con una zona climática incorrecta.
- Por qué ocurre: mismo Bug #1 que el error 17, la otra cara del mismo fallo de propagación de dato.
- Consecuencias: evaluación térmica completa desconectada del emplazamiento real.
- Gravedad: Bloqueante.
- Frecuencia: Alta (mientras el bug no se corrija).
- Detección: alta, ya verificable por test de regresión.
- Prevención: mismo mecanismo que el error 16.
- Corrección: mismo mecanismo que el error 16.
- Normativa relacionada: CTE DB-HE.
- Efecto en cadena: sí, mismo alcance que el error 17.

**142. Proporción de huecos excesiva en fachada norte**
- Descripción: la fachada norte tiene una superficie de hueco desproporcionada, generando pérdida térmica sin compensación de ganancia solar.
- Por qué ocurre: decisión de composición de fachada sin verificar coherencia con la orientación desfavorable.
- Consecuencias: comportamiento térmico deficiente, señal de alerta temprana según `ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 8 §5.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: alta — verificable en cuanto se conoce la orientación y la superficie de hueco por fachada.
- Prevención: verificar coherencia huecos/orientación antes de cerrar la composición de fachada.
- Corrección: reducir superficie de hueco a norte o reforzar su transmitancia.
- Normativa relacionada: CTE DB-HE.
- Efecto en cadena: no directo, salvo si se corrige ampliando huecos en otra fachada (entonces conecta con Dominio 4).

**143. Compacidad de envolvente muy baja sin justificación**
- Descripción: el volumen del edificio tiene una relación superficie/volumen desfavorable sin que exista una razón de diseño que lo justifique.
- Por qué ocurre: geometría fragmentada resultante de un proceso de diseño que no consideró el principio de compacidad (`ARCHITECTURAL_PRINCIPLES.md` A.3).
- Consecuencias: mayor demanda energética de la necesaria.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: parcialmente — calculable con geometría en planta, incompleto sin dato de volumen real.
- Prevención: verificar compacidad en fase de anteproyecto volumétrico.
- Corrección: recomponer la volumetría, si la fase de proyecto lo permite.
- Normativa relacionada: CTE DB-HE.
- Efecto en cadena: no directo.

**144. No verificar coherencia huecos/orientación antes del cálculo formal**
- Descripción: se decide la composición de huecos sin una revisión temprana de coherencia con la orientación, dejando el cálculo formal de demanda energética como única verificación, tardía en el proceso.
- Por qué ocurre: proceso de diseño que pospone la verificación térmica a una fase avanzada.
- Consecuencias: descubrimiento tardío de un problema que habría sido barato de corregir al principio.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: alta, mismo mecanismo que el error 142.
- Prevención: verificar coherencia huecos/orientación como primer paso, no como verificación final.
- Corrección: ajustar composición de huecos si aún hay margen de proyecto.
- Normativa relacionada: CTE DB-HE.
- Efecto en cadena: no directo.

**145. Ampliar iluminación sin recalcular demanda energética**
- Descripción: repetición, desde el ángulo del Dominio 8, del error 68.
- Por qué ocurre: mismo origen.
- Consecuencias: mismo tipo.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: parcialmente, si ambos dominios están activos en la evaluación.
- Prevención: mismo mecanismo que el error 68.
- Corrección: mismo mecanismo que el error 68.
- Normativa relacionada: CTE DB-HE.
- Efecto en cadena: sí, efecto empírico #2 de `CHAIN_REASONING.md`.

**146. No considerar el efecto de una protección solar sobre el balance energético real**
- Descripción: se calcula la demanda energética sin considerar el efecto real de una protección solar fija prevista.
- Por qué ocurre: cálculo simplificado sin incorporar elementos de sombra al modelo térmico.
- Consecuencias: demanda energética calculada distinta de la real, en cualquier dirección.
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: no reconocible desde el DXF de planta — dato de alzado/sección.
- Prevención: incorporar el efecto de protecciones solares fijas al cálculo cuando estén previstas.
- Corrección: recalcular con el efecto de la protección incorporado.
- Normativa relacionada: CTE DB-HE.
- Efecto en cadena: no directo.

**147. Confiar en transmitancia estándar sin verificar composición real**
- Descripción: se usa un valor de transmitancia de referencia genérico en vez de la composición constructiva real prevista.
- Por qué ocurre: ausencia de datos constructivos reales en la fase de evaluación (mismo límite estructural que otros errores de composición constructiva).
- Consecuencias: cálculo de demanda energética con precisión falsa.
- Gravedad: Riesgo variable.
- Frecuencia: Alta.
- Detección: no reconocible sin datos constructivos reales.
- Prevención: declarar el uso de valor estándar como una Estimation explícita, nunca como dato observado (`UNCERTAINTY_MODEL.md`).
- Corrección: sustituir por el valor real cuando esté disponible.
- Normativa relacionada: CTE DB-HE.
- Efecto en cadena: no directo.

**148. No verificar factor solar de huecos según orientación y zona**
- Descripción: se evalúa el hueco solo por su superficie, sin verificar el factor solar exigido según su orientación y la zona climática.
- Por qué ocurre: simplificación indebida de una exigencia con más de una variable relevante.
- Consecuencias: incumplimiento potencial no detectado.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible sin dato de composición del acristalamiento.
- Prevención: verificar factor solar como exigencia independiente de la superficie de hueco.
- Corrección: sustituir el acristalamiento por uno de factor solar adecuado.
- Normativa relacionada: CTE DB-HE.
- Efecto en cadena: no directo.

**149. Compacidad excesiva que compromete otros criterios sin justificación**
- Descripción: en sentido inverso al error 143, maximizar compacidad sacrifica ventilación cruzada o relación con el lugar sin ponderar el trade-off.
- Por qué ocurre: aplicación mecánica de un único principio (compacidad) sin verificar su tensión con otros (`ARCHITECTURAL_PRINCIPLES.md` A.1/A.3).
- Consecuencias: eficiencia energética teórica alta con calidad espacial o ambiental degradada.
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: no reconocible automáticamente — juicio de trade-off, Nivel B/C.
- Prevención: ponderar compacidad frente a otros principios, nunca maximizarla de forma aislada.
- Corrección: revisar el equilibrio en fase de anteproyecto.
- Normativa relacionada: ninguna directa — tensión de criterio, no incumplimiento.
- Efecto en cadena: no directo.

**150. No recalcular demanda tras un cambio de superficie de hueco posterior**
- Descripción: un cambio de hueco introducido tarde en el proceso de proyecto no dispara un recálculo de demanda energética.
- Por qué ocurre: falta de recomputo automático (mismo origen que varios errores de esta lista).
- Consecuencias: cálculo de demanda desactualizado respecto al proyecto real final.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: verificable por recomputo automático tras cualquier cambio de hueco.
- Prevención: tratar todo cambio de hueco como disparador de recomputo del Dominio 8.
- Corrección: recalcular con los datos finales reales.
- Normativa relacionada: CTE DB-HE.
- Efecto en cadena: sí, mismo tipo que el error 68/145.

**151. Ignorar el efecto de retranqueos y alturas sobre la orientación posible**
- Descripción: se evalúa la orientación de piezas sin considerar que el propio planeamiento (retranqueos, alturas) ya condiciona qué orientaciones son geométricamente posibles.
- Por qué ocurre: tratamiento del Dominio 8 de forma aislada del Dominio 1.
- Consecuencias: recomendaciones de orientación no realistas dado el marco urbanístico ya fijado.
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: no verificable sin datos urbanísticos de la parcela.
- Prevención: verificar el margen real de orientación posible antes de generar recomendaciones del Dominio 8.
- Corrección: ajustar las recomendaciones al margen realmente disponible.
- Normativa relacionada: ninguna directa — coherencia entre dominios.
- Efecto en cadena: no directo.

**152. No considerar puentes térmicos en encuentros estructurales**
- Descripción: el cálculo de demanda energética no considera el efecto de puentes térmicos en encuentros de forjado con fachada u otros elementos estructurales.
- Por qué ocurre: ausencia de datos de detalle constructivo en un plano de distribución.
- Consecuencias: demanda energética real superior a la calculada.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible desde el DXF de distribución — dato de detalle constructivo.
- Prevención: incorporar el efecto de puentes térmicos habituales en fase de detalle constructivo.
- Corrección: incorporar rotura de puente térmico en el detalle constructivo.
- Normativa relacionada: CTE DB-HE.
- Efecto en cadena: no directo.

**153. Envolvente protegida en rehabilitación sin margen real de mejora**
- Descripción: se exige mejora energética de la envolvente en una rehabilitación donde la fachada protegida no permite alterarla sustancialmente.
- Por qué ocurre: no verificar el régimen de protección patrimonial antes de exigir mejora térmica (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 8 §8).
- Consecuencias: incumplimiento fabricado sobre una limitación real.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: no verificable sin el dato de catalogación patrimonial (mismo origen que el error 8).
- Prevención: verificar catalogación antes de exigir mejora térmica de fachada.
- Corrección: documentar la justificación de imposibilidad y aplicar el régimen de mejora parcial correspondiente.
- Normativa relacionada: CTE DB-HE, régimen de rehabilitación protegida.
- Efecto en cadena: no directo.

**154. No verificar coherencia energética entre plantas de un edificio multiplanta**
- Descripción: cada planta se evalúa térmicamente de forma aislada, sin verificar coherencia del comportamiento global del edificio.
- Por qué ocurre: mismo límite que el error 32 y 57 — evaluación de un único DXF por vez.
- Consecuencias: evaluación térmica parcial, no representativa del edificio completo.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no reconocible con el flujo actual de un único DXF.
- Prevención: evaluar siempre el conjunto de plantas disponibles.
- Corrección: ampliar el alcance del análisis.
- Normativa relacionada: CTE DB-HE.
- Efecto en cadena: no directo.

**155. Priorizar eficiencia energética a costa de iluminación sin ponderar el trade-off**
- Descripción: se reduce sistemáticamente la superficie de hueco para mejorar el balance térmico sin ponderar la pérdida de calidad de iluminación resultante.
- Por qué ocurre: optimización de un único dominio sin verificar su tensión conocida con otro (`CHAIN_REASONING.md` §5, mismo par que el error 61/68).
- Consecuencias: mejora energética a costa de una calidad de iluminación deficiente, no comunicada como trade-off explícito.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: parcialmente, si ambos dominios están activos en la evaluación.
- Prevención: presentar siempre ambos lados del trade-off, nunca optimizar uno silenciando el efecto en el otro (`DECISION_ENGINE.md` §7).
- Corrección: buscar el punto de equilibrio entre ambos criterios, no maximizar uno solo.
- Normativa relacionada: CTE DB-HE y decreto de habitabilidad, tensión conocida.
- Efecto en cadena: sí, mismo efecto empírico #2.

**156. No documentar la limitación de confianza cuando falta dato constructivo**
- Descripción: se presenta una conclusión térmica sin advertir que depende de datos constructivos no confirmados.
- Por qué ocurre: presión de presentar una respuesta definitiva (mismo patrón que el error 129, aplicado al Dominio 8).
- Consecuencias: afirmación no honesta sobre la certeza real del resultado.
- Gravedad: Riesgo variable.
- Frecuencia: Alta.
- Detección: no reconocible automáticamente sin trazabilidad de origen del dato.
- Prevención: declarar siempre el nivel de confianza real (`UNCERTAINTY_MODEL.md`).
- Corrección: corregir la comunicación al nivel de certeza real.
- Normativa relacionada: CTE DB-HE.
- Efecto en cadena: no directo.

**157. Confiar en un cálculo basado en datos de proyecto desactualizados**
- Descripción: el cálculo de demanda energética se basa en una versión del proyecto anterior a la última revisión.
- Por qué ocurre: mismo origen que el error 30/45, aplicado al Dominio 8.
- Consecuencias: resultado desconectado del proyecto real final.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable sin mecanismo de versión única de verdad.
- Prevención: mismo mecanismo que el error 30.
- Corrección: recalcular con los datos actualizados.
- Normativa relacionada: CTE DB-HE.
- Efecto en cadena: no directo.

**158. No revisar el comportamiento térmico tras fusionar Salón y Cocina**
- Descripción: al fusionar Salón y Cocina en planta abierta, no se recalcula el comportamiento térmico de la pieza resultante, que puede tener una carga interna (cocina) distinta de la asumida para un Salón puro.
- Por qué ocurre: la fusión de piezas (decisión legítima de programa) no dispara automáticamente un recomputo del Dominio 8 sobre la nueva pieza.
- Consecuencias: cálculo térmico basado en un uso (Salón) que ya no representa completamente a la pieza real (Salón-cocina).
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: no reconocible sin distinguir la carga térmica interna por tipo de uso, hoy no modelada con ese nivel de detalle.
- Prevención: recalcular tras cualquier fusión de piezas de cargas internas distintas.
- Corrección: ajustar el cálculo con la carga interna combinada real.
- Normativa relacionada: CTE DB-HE.
- Efecto en cadena: no directo.

---

## Categoría 9 — Calidad espacial y composición (25)

**159. Jerarquía servido/servidor invertida**
- Descripción: una pieza servidora (Distribuidor, Vestidor) supera en superficie o calidad de luz a una pieza principal.
- Por qué ocurre: ajuste geométrico tardío que cede superficie de piezas principales a piezas de servicio sin verificar la jerarquía resultante.
- Consecuencias: síntoma de calidad espacial baja, aunque cada pieza cumpla individualmente su mínimo.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: alta — comparación directa de superficies entre piezas ya clasificadas por jerarquía (`FUNCTIONAL_RELATIONS.md` §8).
- Prevención: fijar la jerarquía de superficies como referencia desde el primer boceto de programa.
- Corrección: redistribuir superficie hacia las piezas principales.
- Normativa relacionada: ninguna — criterio de calidad.
- Efecto en cadena: no directo.

**160. Ausencia de idea organizadora reconocible (parti incoherente)**
- Descripción: la distribución es la suma de soluciones correctas a cada requisito, sin una intención que las sostenga en conjunto.
- Por qué ocurre: proceso de diseño reactivo, resolviendo cada exigencia normativa por separado sin una idea de conjunto previa.
- Consecuencias: proyecto correcto pero no excelente (`ARCHITECTURAL_QUALITY.md` §1).
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: no reconocible automáticamente — Nivel C puro, terreno de "espejo, no juez".
- Prevención: fijar una intención de diseño explícita antes de empezar a resolver requisitos individuales.
- Corrección: revisión completa del parti, no un ajuste puntual.
- Normativa relacionada: ninguna — principio de diseño, no exigencia legal.
- Efecto en cadena: no directo.

**161. Espacio residual sin uso claro**
- Descripción: repetición, desde el ángulo de calidad, del error 48.
- Por qué ocurre: mismo origen.
- Consecuencias: mismo tipo, aquí evaluado como síntoma de calidad, no de superficie.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: parcial, mismo mecanismo que el error 48.
- Prevención: mismo mecanismo que el error 48.
- Corrección: mismo mecanismo que el error 48.
- Normativa relacionada: ninguna — criterio de calidad.
- Efecto en cadena: no directo.

**162. Falta de relación visual con el exterior más allá del mínimo**
- Descripción: la pieza cumple el ratio mínimo de hueco pero no ofrece ninguna relación visual de calidad con el exterior (vista enmarcada, continuidad espacial).
- Por qué ocurre: verificar solo el cumplimiento dimensional del hueco sin considerar su valor compositivo (`ARCHITECTURAL_QUALITY.md` §1).
- Consecuencias: cumplimiento normativo con experiencia espacial pobre.
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: no reconocible automáticamente — Nivel C.
- Prevención: considerar la calidad de la vista, no solo el ratio, en el diseño del hueco.
- Corrección: rediseñar posición o proporción del hueco.
- Normativa relacionada: ninguna — criterio de calidad.
- Efecto en cadena: no directo.

**163. Recorrido social que atraviesa la zona de noche**
- Descripción: el recorrido que sigue una visita cruza, aunque sea tangencialmente, la zona de dormitorios.
- Por qué ocurre: distribución sin verificar la secuencia de gradiente de privacidad desde el acceso (`FUNCTIONAL_RELATIONS.md` §3-4).
- Consecuencias: pérdida de privacidad real de la zona de noche ante cualquier visita.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible sin el grafo de circulación conectado.
- Prevención: verificar el recorrido social completo desde el acceso en fase de anteproyecto.
- Corrección: redistribuir el vestíbulo o distribuidor para evitar el cruce.
- Normativa relacionada: ninguna — criterio de calidad.
- Efecto en cadena: no directo.

**164. Ausencia de gradiente de privacidad desde el acceso**
- Descripción: la secuencia de niveles de privacidad (`FUNCTIONAL_RELATIONS.md` §4) no es ascendente y continua desde la puerta de entrada.
- Por qué ocurre: mismo origen general que el error 163, formulado como principio de composición, no como caso concreto.
- Consecuencias: sensación de exposición o de intimidad mal resuelta en toda la vivienda.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible automáticamente sin el grafo de circulación conectado.
- Prevención: verificar el gradiente completo, no solo casos puntuales.
- Corrección: redistribuir la secuencia de acceso.
- Normativa relacionada: ninguna — criterio de calidad.
- Efecto en cadena: no directo.

**165. Dormitorio adyacente a cocina sin filtro intermedio**
- Descripción: repetición, desde el ángulo de composición, del error de separación funcional ya señalado en `FUNCTIONAL_RELATIONS.md` §2.
- Por qué ocurre: mismo origen.
- Consecuencias: mismo tipo, aquí evaluado como defecto de composición, no solo de ruido puntual.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: alta, mismo mecanismo que el error 123.
- Prevención: interponer siempre un filtro (distribuidor, vestidor, armario) entre ambos usos.
- Corrección: redistribuir o interponer el filtro.
- Normativa relacionada: ninguna — criterio de composición.
- Efecto en cadena: no directo.

**166. Distribuidor sobredimensionado a costa de piezas principales**
- Descripción: el distribuidor ocupa una superficie desproporcionada, restando superficie disponible a Salón o Dormitorios.
- Por qué ocurre: geometría de circulación no optimizada, a menudo consecuencia de un parti poco resuelto (error 160).
- Consecuencias: eficiencia útil/construida baja (relacionado con el error 54) y jerarquía invertida (relacionado con el error 159).
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: alta — comparación directa de superficie de Distribuidor contra piezas principales.
- Prevención: verificar la proporción de superficie de circulación desde el primer boceto.
- Corrección: redistribuir hacia un esquema de circulación más compacto.
- Normativa relacionada: ninguna — criterio de eficiencia y calidad.
- Efecto en cadena: no directo.

**167. Salón que no es la pieza de mayor superficie sin justificación**
- Descripción: variante concreta del error 159 — el Salón, específicamente, queda por debajo de otra pieza en superficie sin que exista una razón de programa declarada.
- Por qué ocurre: mismo origen que el 159.
- Consecuencias: mismo tipo.
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: alta, comparación directa de superficies.
- Prevención: mismo mecanismo que el 159.
- Corrección: mismo mecanismo que el 159.
- Normativa relacionada: ninguna — criterio de calidad.
- Efecto en cadena: no directo.

**168. Recorrido nocturno innecesariamente largo**
- Descripción: la distancia entre Dormitorio y Baño es mayor de lo que la geometría del proyecto exigiría razonablemente.
- Por qué ocurre: posición del núcleo húmedo fijada por otros criterios (instalaciones, estructura) sin ponderar el coste de uso nocturno diario.
- Consecuencias: pérdida de calidad de uso cotidiano, especialmente relevante en el recorrido más repetido de la vivienda (`FUNCTIONAL_RELATIONS.md` §3).
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: alta — ya en producción (`evaluate_entry_distance` mide una relación análoga; el mismo mecanismo aplicaría a distancia dormitorio-baño con un ajuste menor).
- Prevención: verificar esta distancia como criterio de composición, no solo la de entrada.
- Corrección: reubicar el baño o el dormitorio más próximos entre sí.
- Normativa relacionada: ninguna — criterio de calidad de uso.
- Efecto en cadena: no directo.

**169. Cocina orientada a sur en clima cálido sin justificación**
- Descripción: la cocina recibe la orientación de mayor carga solar sin que exista una razón de diseño que lo justifique.
- Por qué ocurre: la cocina hereda la orientación de la pieza fusionada (Salón) sin evaluación propia (consecuencia del error 21/52).
- Consecuencias: sobrecalentamiento acumulado (actividad de cocinar + carga solar).
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: no reconocible hoy, mismo origen que el error 52 (fusión de patrones).
- Prevención: evaluar la orientación de Cocina de forma independiente cuando el DXF la distingue geométricamente de Salón.
- Corrección: reorientar si el proyecto lo permite, o reforzar protección solar/ventilación en esa fachada.
- Normativa relacionada: ninguna — criterio de calidad, `ARCHITECTURAL_PRINCIPLES.md` A.2.
- Efecto en cadena: no directo.

**170. Fusión de usos sin coherencia interna de zonas**
- Descripción: en un Salón-comedor-cocina abierto, no existe ninguna organización interna reconocible (zona de estar diferenciada de zona de mesa y de zona de cocina).
- Por qué ocurre: tratar la apertura de espacio como ausencia total de organización en vez de como una organización sin partición física.
- Consecuencias: espacio "genérico" sin jerarquía interna legible, síntoma de calidad baja pese a cumplir superficie (`SPACE_TAXONOMY.md` 1.3).
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: no reconocible automáticamente — Nivel C.
- Prevención: diseñar la organización interna de la pieza fusionada aunque no haya partición física.
- Corrección: reorganizar mobiliario/zonificación interna de la pieza.
- Normativa relacionada: ninguna — criterio de calidad.
- Efecto en cadena: no directo.

**171. Falta de continuidad interior-exterior en fachadas con terraza disponible**
- Descripción: existiendo Terraza vinculada, la pieza interior a la que sirve no tiene una relación de continuidad visual/física de calidad con ella.
- Por qué ocurre: la Terraza se resuelve como un añadido posterior sin integrarla en el diseño de la pieza interior desde el origen.
- Consecuencias: oportunidad de calidad perdida (`ARCHITECTURAL_PRINCIPLES.md`, principio de continuidad interior-exterior, implícito en la respuesta al lugar de `ARCHITECTURAL_QUALITY.md` §1).
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: no reconocible automáticamente — Nivel C.
- Prevención: diseñar la relación interior-exterior desde el primer boceto, no como ajuste posterior.
- Corrección: rediseñar el encuentro entre pieza interior y terraza.
- Normativa relacionada: ninguna — criterio de calidad.
- Efecto en cadena: no directo.

**172. Escalera sin luz natural en proyecto con posibilidad de darla**
- Descripción: la escalera común es interior y ciega pese a que el proyecto tenía margen geométrico para dotarla de un hueco propio.
- Por qué ocurre: decisión de composición de fachada que no prioriza la escalera como elemento merecedor de luz.
- Consecuencias: elemento de circulación de baja calidad ambiental, aunque cumpla su función normativa.
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: no reconocible automáticamente sin datos de Hueco por elemento.
- Prevención: considerar la escalera como candidata a luz natural desde el diseño de fachada.
- Corrección: incorporar un hueco en la caja de escalera si el proyecto lo permite.
- Normativa relacionada: ninguna — criterio de calidad, `SPACE_TAXONOMY.md` 6.2.
- Efecto en cadena: no directo.

**173. No declarar intención de diseño y evaluar calidad sin ese contexto**
- Descripción: se emite un juicio de calidad espacial (Nivel 4) sin haber preguntado ni incorporado la intención de diseño declarada por el arquitecto o el cliente.
- Por qué ocurre: tratamiento de la calidad espacial como juicio externo autónomo en vez de comparación contra la intención propia del proyecto (`ARCHITECTURAL_QUALITY.md` §4).
- Consecuencias: juicio de calidad menos defendible, potencialmente injusto con una decisión de diseño consciente.
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: no verificable automáticamente sin el dato de Preference declarada.
- Prevención: capturar la intención de diseño antes de evaluar calidad espacial.
- Corrección: reevaluar incorporando la intención declarada.
- Normativa relacionada: ninguna — criterio de calidad.
- Efecto en cadena: no directo.

**174. Confundir cumplimiento del mínimo con buen diseño**
- Descripción: se presenta una vivienda como "de calidad" únicamente por no tener incumplimientos normativos.
- Por qué ocurre: colapsar dos preguntas distintas (¿es legal? ¿es bueno?) en una sola respuesta, la misma confusión que `BRAIN_ARCHITECTURE.md` §1.5 ya nombra explícitamente.
- Consecuencias: expectativa de calidad incorrecta comunicada al cliente.
- Gravedad: Preferencial.
- Frecuencia: Alta.
- Detección: no verificable automáticamente — error de comunicación del resultado, no de cálculo.
- Prevención: mantener siempre separadas la capa de cumplimiento y la capa de calidad en la comunicación del resultado (`GLOBAL_ASSESSMENT.md` §0).
- Corrección: corregir la comunicación, distinguiendo ambas capas explícitamente.
- Normativa relacionada: ninguna — error de comunicación.
- Efecto en cadena: no directo.

**175. Malla estructural que impone restricciones no resueltas en la distribución final**
- Descripción: la retícula estructural obliga a soluciones de distribución forzadas (un pilar en medio de un salón, por ejemplo) sin que se haya intentado coordinar ambas desde el principio.
- Por qué ocurre: proyecto de estructura y de distribución desarrollados sin coordinación temprana (`ARCHITECTURAL_PRINCIPLES.md` B.4).
- Consecuencias: solución final con elementos estructurales mal integrados en el espacio habitable.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible sin datos de Elemento estructural, mismo límite ya señalado repetidamente en la serie.
- Prevención: coordinar malla estructural y distribución desde el anteproyecto.
- Corrección: rediseñar el encuentro problemático si aún hay margen.
- Normativa relacionada: ninguna — criterio de coordinación de proyecto.
- Efecto en cadena: no directo.

**176. Vestíbulo sin filtro de privacidad hacia dormitorios**
- Descripción: desde la puerta de entrada de la vivienda, hay visión directa hacia el interior de un dormitorio.
- Por qué ocurre: posición del vestíbulo y del dormitorio fijadas sin verificar el ángulo de visión resultante al abrir la puerta principal.
- Consecuencias: pérdida de privacidad inmediata en el momento más expuesto de la vivienda (cualquier visita, entrega, etc.).
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible automáticamente sin un modelo de campo visual, no implementado.
- Prevención: verificar el ángulo de visión desde el punto de acceso en fase de anteproyecto.
- Corrección: introducir un quiebro, un mueble separador o reorientar la puerta del dormitorio afectado.
- Normativa relacionada: ninguna — criterio de calidad.
- Efecto en cadena: no directo.

**177. Falta de coherencia entre jerarquía de usos declarada y jerarquía espacial construida**
- Descripción: la memoria de proyecto declara una jerarquía de piezas (cuál es la principal) que no se corresponde con la jerarquía real de superficies y posición construida.
- Por qué ocurre: la memoria se redacta con la intención original del proyecto, sin actualizarse tras ajustes posteriores a la distribución.
- Consecuencias: incoherencia documental y de diseño simultánea.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: parcialmente — verificable comparando la jerarquía declarada contra la jerarquía real de superficies (`FUNCTIONAL_RELATIONS.md` §8).
- Prevención: verificación cruzada entre memoria y jerarquía real construida antes de la entrega.
- Corrección: sincronizar memoria y proyecto, o corregir la distribución si la memoria refleja la intención correcta.
- Normativa relacionada: ninguna — coherencia documental.
- Efecto en cadena: no directo.

**178. Proporción de vivienda desequilibrada por priorizar una pieza sobre el conjunto**
- Descripción: una pieza (por ejemplo, un dormitorio principal muy amplio) crece a costa de desequilibrar el resto del programa de forma desproporcionada.
- Por qué ocurre: negociación de superficie pieza a pieza sin verificar el equilibrio del conjunto completo.
- Consecuencias: vivienda con una pieza sobresaliente y el resto degradado, en vez de un conjunto coherente.
- Gravedad: Preferencial.
- Frecuencia: Baja.
- Detección: parcialmente — verificable por comparación de proporciones relativas entre todas las piezas del programa.
- Prevención: verificar el equilibrio del conjunto, no solo el cumplimiento pieza a pieza.
- Corrección: redistribuir para restaurar un equilibrio razonable.
- Normativa relacionada: ninguna — criterio de calidad.
- Efecto en cadena: no directo.

**179. No mantener relación de proximidad entre cocina y comedor**
- Descripción: repetición, desde el ángulo de composición, de la relación ya fijada como adyacencia directa en `FUNCTIONAL_RELATIONS.md` §1.
- Por qué ocurre: distribución que no prioriza esta relación pese a ser de las de mayor consenso profesional.
- Consecuencias: uso cotidiano degradado (recorrido de servir la comida, el más repetido de la vida doméstica).
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: alta — verificable geométricamente por proximidad de centroides entre ambas piezas, una vez reconocidas.
- Prevención: fijar esta adyacencia como prioridad de composición desde el primer boceto.
- Corrección: redistribuir para aproximar ambas piezas.
- Normativa relacionada: ninguna — criterio de calidad.
- Efecto en cadena: no directo.

**180. Terraza vinculada a pieza secundaria en vez de a la principal**
- Descripción: la única terraza disponible se abre desde un dormitorio secundario en vez de desde el Salón.
- Por qué ocurre: la posición de fachada disponible para terraza se decide por criterios ajenos a la jerarquía de piezas (orientación, estructura) sin ponderar la jerarquía funcional.
- Consecuencias: la pieza de mayor valor de uso social queda sin el elemento de mayor valor añadido del proyecto.
- Gravedad: Preferencial.
- Frecuencia: Baja.
- Detección: alta — verificable por relación de adyacencia entre Terraza y la pieza a la que se abre, una vez ambas reconocidas.
- Prevención: priorizar la pieza principal al asignar la posición de terraza disponible.
- Corrección: redistribuir si el margen del proyecto lo permite.
- Normativa relacionada: ninguna — criterio de calidad.
- Efecto en cadena: no directo.

**181. Repetir la misma solución de distribución sin adaptarla a la orientación de cada unidad**
- Descripción: en un edificio plurifamiliar, todas las unidades usan la misma distribución interna sin ajustarla a la orientación real de cada una.
- Por qué ocurre: economía de proyecto (una única planta tipo replicada) sin verificar el coste de calidad que eso implica en las unidades peor orientadas.
- Consecuencias: unidades con la misma distribución pero calidad ambiental muy distinta según su orientación real.
- Gravedad: Preferencial.
- Frecuencia: Alta.
- Detección: parcialmente — verificable comparando la distribución y la orientación de piezas equivalentes entre unidades distintas del mismo edificio.
- Prevención: adaptar al menos la asignación de uso por pieza (qué pieza es dormitorio, cuál es salón) a la orientación real de cada unidad.
- Corrección: reasignar usos por unidad según orientación, sin necesidad de rediseñar la distribución completa.
- Normativa relacionada: ninguna — criterio de calidad.
- Efecto en cadena: no directo.

**182. No verificar privacidad visual entre baño y salón**
- Descripción: repetición, desde el ángulo de composición, del caso ya señalado en `FUNCTIONAL_RELATIONS.md` §2.
- Por qué ocurre: mismo origen.
- Consecuencias: mismo tipo.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible automáticamente sin modelo de campo visual.
- Prevención: verificar el ángulo de apertura de la puerta del baño respecto al Salón.
- Corrección: reorientar la puerta o interponer un elemento de filtro visual.
- Normativa relacionada: ninguna — criterio de calidad.
- Efecto en cadena: no directo.

**183. Sacrificar calidad espacial sistemáticamente para maximizar superficie vendible**
- Descripción: cada decisión de diseño se resuelve, de forma sistemática, a favor de la superficie computable frente a cualquier criterio de calidad espacial.
- Por qué ocurre: presión comercial del promotor sobre el criterio del arquitecto (Conflict Tipo 3, `DECISION_ENGINE.md` §2).
- Consecuencias: proyecto normativamente correcto y sistemáticamente mediocre en calidad espacial.
- Gravedad: Preferencial.
- Frecuencia: Alta.
- Detección: no verificable automáticamente de forma directa — patrón detectable solo por acumulación de otros errores de esta categoría a lo largo del proyecto completo.
- Prevención: fijar un mínimo de calidad espacial como preferencia declarada del arquitecto, no solo del promotor, desde el inicio.
- Corrección: no hay corrección puntual — requiere revisión de la postura de diseño completa del proyecto.
- Normativa relacionada: ninguna — tensión de criterio de negocio vs. calidad.
- Efecto en cadena: no directo, es la acumulación de muchos otros errores de esta categoría.

---

## Categoría 10 — Instalaciones y coherencia técnica (18)

**184. Núcleos húmedos no apilados verticalmente**
- Descripción: el baño o cocina de una planta no coincide en posición con el núcleo húmedo de la planta inferior.
- Por qué ocurre: distribución de cada planta resuelta de forma independiente sin verificar coherencia vertical.
- Consecuencias: recorridos de bajante forzados, sobrecoste de instalación, riesgo de solución constructiva deficiente.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible con el flujo actual de un único DXF por evaluación — requiere el conjunto de plantas.
- Prevención: verificar apilamiento vertical de núcleos húmedos entre plantas desde el anteproyecto.
- Corrección: reubicar el núcleo húmedo de la planta discordante si aún hay margen.
- Normativa relacionada: ninguna directa — criterio de coherencia técnica (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 10 §2, el criterio más determinante del dominio).
- Efecto en cadena: sí — es, literalmente, el efecto empírico #5 de `CHAIN_REASONING.md`.

**185. Recorrido de instalaciones excesivamente largo entre cocina y baños**
- Descripción: la posición de cocina y baños dentro de la misma vivienda genera un recorrido de fontanería innecesariamente largo.
- Por qué ocurre: ambas piezas se posicionan por otros criterios (orientación, jerarquía) sin verificar proximidad de instalaciones compartidas.
- Consecuencias: sobrecoste de instalación, recorridos forzados.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: parcialmente — verificable por distancia entre centroides de piezas húmedas, sin modelo real de trazado de instalación.
- Prevención: verificar proximidad razonable entre piezas húmedas desde el anteproyecto.
- Corrección: reubicar si el margen del proyecto lo permite.
- Normativa relacionada: ninguna directa — criterio de coherencia técnica.
- Efecto en cadena: no directo.

**186. Patinillo interrumpiendo compartimentación contra incendio**
- Descripción: repetición, desde el ángulo de instalaciones, del error 105.
- Por qué ocurre: mismo origen.
- Consecuencias: mismo tipo.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: mismo mecanismo que el error 105.
- Prevención: mismo mecanismo que el error 105.
- Corrección: mismo mecanismo que el error 105.
- Normativa relacionada: CTE DB-SI y DB-HS.
- Efecto en cadena: sí, mismo que el error 105.

**187. Espacio técnico insuficiente para la instalación prevista**
- Descripción: el cuarto de instalaciones dimensionado no alcanza el espacio mínimo real exigido por el equipo que va a alojar.
- Por qué ocurre: dimensionado del espacio técnico decidido antes de conocer las dimensiones reales del equipo a instalar.
- Consecuencias: instalación forzada o inviable con el espacio previsto.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no reconocible sin datos de la instalación específica prevista.
- Prevención: coordinar dimensión de espacio técnico con el proyecto de instalaciones desde el anteproyecto.
- Corrección: ampliar el espacio técnico si el margen del proyecto lo permite.
- Normativa relacionada: reglamento específico de la instalación (RITE, REBT, según el caso).
- Efecto en cadena: no directo.

**188. No coordinar posición de instalaciones con la distribución antes de cerrar el proyecto**
- Descripción: el proyecto de instalaciones se desarrolla después de cerrar por completo la distribución arquitectónica, sin margen de ajuste mutuo.
- Por qué ocurre: proceso de proyecto secuencial en vez de coordinado, con instalaciones tratadas como un añadido posterior (`ARCHITECTURAL_ONTOLOGY.md` C.5, principio arquitectónico).
- Consecuencias: soluciones forzadas de última hora que degradan tanto la viabilidad técnica como la calidad espacial ya cerrada.
- Gravedad: Riesgo variable.
- Frecuencia: Alta.
- Detección: no verificable automáticamente — error de proceso.
- Prevención: coordinar instalaciones desde el anteproyecto, no como fase posterior aislada.
- Corrección: revisar los puntos de conflicto identificados tardíamente caso a caso.
- Normativa relacionada: ninguna directa — error de proceso de coordinación de proyecto.
- Efecto en cadena: sí, agregado de varios otros errores de esta categoría.

**189. Cuarto de contadores sin acceso desde zona común**
- Descripción: el cuarto de contadores solo es accesible atravesando una vivienda privada.
- Por qué ocurre: posición decidida por proximidad geométrica sin verificar el criterio de acceso para mantenimiento.
- Consecuencias: imposibilidad de mantenimiento sin invadir la privacidad de una vivienda.
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: no reconocible sin el grafo de circulación conectado.
- Prevención: verificar acceso desde zona común como requisito de posición del cuarto de contadores.
- Corrección: reubicar el acceso o el propio espacio técnico.
- Normativa relacionada: reglamento electrotécnico/de suministros.
- Efecto en cadena: no directo.

**190. Sala de calderas adyacente a pieza habitable sin filtro**
- Descripción: repetición, desde el ángulo de instalaciones, del error 124/133 aplicado específicamente a Sala de calderas (`SPACE_TAXONOMY.md` 7.2).
- Por qué ocurre: mismo origen general.
- Consecuencias: vibración y ruido de equipo activo sobre pieza sensible.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: mismo mecanismo que el error 123, aplicado a este tipo de espacio técnico.
- Prevención: mismo mecanismo, con especial atención por tratarse de una fuente activa de vibración, no pasiva.
- Corrección: reubicar o reforzar aislamiento antivibratorio.
- Normativa relacionada: RITE.
- Efecto en cadena: no directo.

**191. No prever espacio para ventilación mecánica en cocina cerrada sin patio**
- Descripción: repetición, desde el ángulo de instalaciones, del error 71.
- Por qué ocurre: mismo origen.
- Consecuencias: mismo tipo.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: mismo mecanismo que el error 71.
- Prevención: mismo mecanismo que el error 71.
- Corrección: mismo mecanismo que el error 71.
- Normativa relacionada: CTE DB-HS3, RITE.
- Efecto en cadena: no directo.

**192. Ignorar viabilidad de instalaciones al evaluar solo desde plano 2D**
- Descripción: se declara viable una distribución de instalaciones sin verificar su compatibilidad real, algo que un plano de distribución 2D no puede confirmar por sí solo.
- Por qué ocurre: ausencia de sección constructiva o proyecto de instalaciones real en el momento de la evaluación (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 10 §8, techo de certeza estructuralmente bajo).
- Consecuencias: afirmación de viabilidad no honesta.
- Gravedad: Riesgo variable.
- Frecuencia: Alta.
- Detección: no reconocible en absoluto sin sección o proyecto de instalaciones — límite estructural reconocido explícitamente.
- Prevención: declarar siempre la limitación de confianza en evaluaciones de instalaciones desde plano de distribución únicamente.
- Corrección: obtener el proyecto de instalaciones real antes de certificar viabilidad.
- Normativa relacionada: ninguna directa — límite de dato, no de norma.
- Efecto en cadena: no directo.

**193. No verificar coherencia vertical de bajantes tras mover un baño**
- Descripción: repetición, desde el ángulo de un cambio concreto, del error 184 — aquí específicamente disparado por el efecto empírico #5 de `CHAIN_REASONING.md`.
- Por qué ocurre: mismo origen de falta de recomputo tras cambio (mismo patrón que numerosos errores de esta lista).
- Consecuencias: mismo tipo que el error 184, pero como consecuencia sobrevenida de un cambio, no como estado original.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible con el flujo actual de un único DXF por evaluación.
- Prevención: tratar todo cambio de posición de núcleo húmedo como disparador de recomputo de coherencia vertical.
- Corrección: verificar y ajustar si es necesario.
- Normativa relacionada: ninguna directa — criterio de coherencia técnica.
- Efecto en cadena: sí, es el efecto empírico #5 en su forma de cambio sobrevenido.

**194. Cuarto de basuras adyacente a vivienda sin aislamiento de olores/ruido**
- Descripción: repetición, desde el ángulo técnico, de la incompatibilidad ya señalada en `SPACE_TAXONOMY.md` 6.5.
- Por qué ocurre: posición decidida por proximidad a zona común de acceso sin verificar adyacencia con vivienda.
- Consecuencias: molestia real de olores y ruido de manipulación de contenedores.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: alta, mismo mecanismo de adyacencia que el error 123.
- Prevención: verificar adyacencias del cuarto de basuras como cualquier otro espacio técnico generador de molestia.
- Corrección: reubicar o reforzar aislamiento.
- Normativa relacionada: ninguna directa — criterio de composición.
- Efecto en cadena: no directo.

**195. No prever recorrido de mantenimiento sin atravesar vivienda privada**
- Descripción: variante general del error 189, aplicable a cualquier espacio técnico del edificio.
- Por qué ocurre: mismo origen.
- Consecuencias: mismo tipo, generalizado a toda instalación de mantenimiento periódico.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible sin el grafo de circulación conectado.
- Prevención: verificar acceso desde zona común para todo espacio técnico de mantenimiento periódico.
- Corrección: reubicar según sea necesario.
- Normativa relacionada: ninguna directa — criterio de coherencia técnica.
- Efecto en cadena: no directo.

**196. Rampa de garaje sin ventilación forzada prevista**
- Descripción: el garaje colectivo no dispone de la instalación de ventilación forzada obligatoria por su condición de uso cerrado con vehículos.
- Por qué ocurre: foco en la geometría de la rampa y las plazas sin verificar la instalación de ventilación asociada.
- Consecuencias: incumplimiento directo, riesgo real de acumulación de gases.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible desde el DXF de distribución sin dato de instalaciones.
- Prevención: verificar la instalación de ventilación forzada desde el anteproyecto de garaje.
- Corrección: incorporar la instalación exigida.
- Normativa relacionada: RITE, normativa de garajes.
- Efecto en cadena: no directo.

**197. No coordinar instalaciones de climatización con compartimentación de sectores**
- Descripción: los conductos de climatización atraviesan sectores de incendio sin las compuertas cortafuego exigidas.
- Por qué ocurre: coordinación deficiente entre proyecto de instalaciones y proyecto de protección contra incendio.
- Consecuencias: vía de propagación de incendio no prevista, mismo tipo de riesgo que el error 105.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: no reconocible desde el DXF de distribución — dato de detalle constructivo/instalaciones.
- Prevención: coordinar el trazado de climatización con la sectorización desde el proyecto básico.
- Corrección: incorporar las compuertas cortafuego exigidas.
- Normativa relacionada: CTE DB-SI, RITE.
- Efecto en cadena: no directo.

**198. Falta de espacio técnico dedicado en el diseño inicial**
- Descripción: no se reserva ningún espacio técnico en el anteproyecto, añadiéndose tarde y mal ubicado tras el desarrollo del proyecto de instalaciones.
- Por qué ocurre: tratamiento de las instalaciones como asunto de fases avanzadas del proyecto (mismo origen general que el error 188).
- Consecuencias: espacio técnico forzado en una posición no óptima, con coste de calidad espacial y de eficiencia de instalación.
- Gravedad: Recomendable.
- Frecuencia: Alta.
- Detección: no verificable automáticamente — error de proceso.
- Prevención: reservar espacio técnico desde el anteproyecto, antes de cerrar la distribución completa.
- Corrección: no hay corrección sencilla una vez cerrada la distribución — requiere reapertura parcial del diseño.
- Normativa relacionada: ninguna directa — error de proceso.
- Efecto en cadena: no directo, es causa raíz de varios otros errores de esta categoría.

**199. Confiar en la distribución en planta sin sección para verificar viabilidad**
- Descripción: variante general del error 192 formulada como principio metodológico, no como caso concreto.
- Por qué ocurre: mismo origen.
- Consecuencias: mismo tipo, generalizado a cualquier verificación de instalaciones.
- Gravedad: Riesgo variable.
- Frecuencia: Alta.
- Detección: mismo límite que el error 192.
- Prevención: mismo mecanismo que el error 192.
- Corrección: mismo mecanismo que el error 192.
- Normativa relacionada: ninguna directa — límite de dato.
- Efecto en cadena: no directo.

**200. No reservar espacio para contadores individuales por vivienda**
- Descripción: el proyecto no prevé espacio individual de contador por unidad cuando el régimen de suministro lo exige individualizado.
- Por qué ocurre: dimensionado del cuarto de contadores general sin verificar si el régimen exige individualización por vivienda.
- Consecuencias: incumplimiento del reglamento de suministros aplicable.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible sin dato del régimen de suministro exigido.
- Prevención: verificar el régimen de individualización antes de dimensionar el espacio técnico.
- Corrección: ampliar o redistribuir el espacio de contadores.
- Normativa relacionada: reglamento electrotécnico/de suministros.
- Efecto en cadena: no directo.

**201. Instalaciones que condicionan la distribución después de cerrada, generando soluciones forzadas**
- Descripción: variante de cierre de la categoría — el patrón general de todos los errores anteriores de esta categoría, nombrado como consecuencia acumulada.
- Por qué ocurre: ausencia sistemática de coordinación temprana entre arquitectura e instalaciones.
- Consecuencias: degradación simultánea de viabilidad técnica y de calidad espacial ya cerrada, el peor resultado posible de esta categoría.
- Gravedad: Riesgo variable.
- Frecuencia: Alta.
- Detección: no verificable automáticamente de forma directa — patrón acumulado, detectable solo por la suma de otros errores de esta categoría.
- Prevención: coordinación de instalaciones desde el anteproyecto, principio único que previene la mayoría de los 17 errores anteriores de esta categoría.
- Corrección: no hay corrección puntual — requiere revisión del proceso de coordinación de proyecto completo.
- Normativa relacionada: ninguna directa — error de proceso.
- Efecto en cadena: sí, es la síntesis de toda la categoría.

---

## Categoría 11 — Estructura y coherencia geométrica (15)

**202. Luz estructural excesiva sin justificación**
- Descripción: la distancia entre posibles apoyos verticales es mayor de lo razonable para un sistema estructural convencional, sin que exista una decisión de diseño singular que lo justifique.
- Por qué ocurre: distribución interior decidida sin verificar coherencia con un sistema estructural convencional viable.
- Consecuencias: alerta de revisión estructural, potencial necesidad de un sistema más costoso de lo previsto.
- Gravedad: Riesgo variable (nunca conclusión firme sin cálculo real, `ARCHITECTURAL_ONTOLOGY.md` F.1).
- Frecuencia: Baja.
- Detección: parcialmente — geometría de posibles apoyos detectable en planta, sin verificación de cálculo real.
- Prevención: verificar luces razonables según tipología de forjado habitual desde el anteproyecto.
- Corrección: introducir un apoyo intermedio o justificar el sistema singular.
- Normativa relacionada: Código Estructural, DB-SE (referencia conceptual, no de cálculo).
- Efecto en cadena: no directo, salvo que fuerce un rediseño de distribución.

**203. Falta de continuidad vertical de soportes entre plantas**
- Descripción: un elemento vertical de apoyo de una planta no tiene continuidad con un elemento equivalente en la planta inmediatamente inferior.
- Por qué ocurre: distribución de cada planta resuelta de forma independiente, mismo patrón de causa raíz que el error 184 aplicado a estructura.
- Consecuencias: alerta de incoherencia estructural aparente.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: no reconocible con el flujo actual de un único DXF — requiere el conjunto de plantas.
- Prevención: verificar continuidad vertical desde el anteproyecto, con el conjunto de plantas disponible.
- Corrección: redistribuir para restaurar continuidad, o justificar la solución estructural especial (viga de transferencia, por ejemplo).
- Normativa relacionada: DB-SE (referencia conceptual).
- Efecto en cadena: no directo, salvo rediseño de distribución completo.

**204. Voladizo sin apoyo o refuerzo evidente**
- Descripción: una parte del edificio vuela sobre el plano de fachada sin ningún elemento de apoyo o refuerzo visible en el plano.
- Por qué ocurre: decisión de composición volumétrica sin coordinación con la solución estructural que la sostendría.
- Consecuencias: alerta de revisión estructural.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: parcialmente — geometría del voladizo detectable en planta, sin verificación de cálculo real.
- Prevención: coordinar cualquier voladizo con el sistema estructural desde el anteproyecto.
- Corrección: justificar el sistema estructural que lo sostiene, o reducir el voladizo.
- Normativa relacionada: DB-SE (referencia conceptual).
- Efecto en cadena: no directo.

**205. Malla estructural incoherente entre plantas**
- Descripción: repetición, formulada de forma más general, del error 203 y del error 57.
- Por qué ocurre: mismo origen.
- Consecuencias: mismo tipo.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: mismo límite que el error 203.
- Prevención: mismo mecanismo.
- Corrección: mismo mecanismo.
- Normativa relacionada: DB-SE (referencia conceptual).
- Efecto en cadena: no directo.

**206. Confundir muro de carga con tabique sin verificar continuidad vertical**
- Descripción: se asume la función estructural o no estructural de una partición sin verificar su continuidad vertical real entre plantas.
- Por qué ocurre: clasificación por grosor aparente en vez de por verificación de continuidad real (`ARCHITECTURAL_ONTOLOGY.md` D.2, ambigüedad ya señalada explícitamente).
- Consecuencias: decisión de reforma que afecta, sin saberlo, a un elemento de carga real.
- Gravedad: Bloqueante (si termina en una intervención sobre elemento de carga no identificado).
- Frecuencia: Media.
- Detección: no reconocible con fiabilidad desde un DXF de planta sin datos de cálculo real — el mayor techo de incertidumbre de toda la ontología (`ARCHITECTURAL_ONTOLOGY.md` F.1).
- Prevención: nunca asumir la función de una partición sin verificación de continuidad vertical y, si hay duda, consulta a un técnico estructurista.
- Corrección: paralizar la intervención hasta verificar la función real del elemento.
- Normativa relacionada: DB-SE.
- Efecto en cadena: sí — puede comprometer la integridad estructural del edificio si no se detecta a tiempo.

**207. No verificar relación de apoyo cuando existe información de varias plantas**
- Descripción: se dispone de información de más de una planta pero no se usa para verificar continuidad estructural, limitándose el análisis a una única planta como si fuera la única disponible.
- Por qué ocurre: proceso de evaluación que no aprovecha el dato disponible, no un límite real de información.
- Consecuencias: oportunidad de verificación perdida cuando sí había datos suficientes.
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: no verificable automáticamente sin un flujo que procese varias plantas simultáneamente (mismo límite que el error 32, aquí en su vertiente evitable).
- Prevención: ampliar siempre el alcance del análisis a toda la información de plantas disponible.
- Corrección: reevaluar incorporando el conjunto completo de plantas disponibles.
- Normativa relacionada: DB-SE (referencia conceptual).
- Efecto en cadena: no directo.

**208. Presentar una alerta estructural como conclusión firme**
- Descripción: se comunica una observación de coherencia geométrica como si fuera un dictamen estructural certero.
- Por qué ocurre: simplificación indebida en la comunicación, perdiendo el matiz de que el análisis sin cálculo real es, en el mejor caso, una señal de atención (`ARCHITECTURAL_ONTOLOGY.md` F.1).
- Consecuencias: expectativa incorrecta sobre la certeza real de la afirmación, riesgo de responsabilidad profesional.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable automáticamente — error de comunicación.
- Prevención: mantener siempre el vocabulario de "aviso a revisar" distinguido de "conclusión firme" en este dominio específicamente.
- Corrección: corregir la comunicación al nivel de certeza real.
- Normativa relacionada: ninguna directa — error de comunicación.
- Efecto en cadena: no directo.

**209. No advertir de incoherencia estructural aparente cuando es detectable a simple vista**
- Descripción: variante inversa del error 208 — se omite advertir una incoherencia claramente visible en el plano por no tratarse de un incumplimiento normativo formal.
- Por qué ocurre: limitar la evaluación a exigencias normativas formales, sin comunicar observaciones de sentido común arquitectónico.
- Consecuencias: oportunidad de alerta temprana perdida.
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: parcialmente, mismo mecanismo que el error 202/204.
- Prevención: comunicar toda incoherencia geométrica aparente, aunque no constituya incumplimiento normativo formal.
- Corrección: incorporar la advertencia al informe.
- Normativa relacionada: ninguna — criterio de buena práctica.
- Efecto en cadena: no directo.

**210. Sistema estructural singular no distinguido de una incoherencia real**
- Descripción: se marca como incoherencia una decisión de diseño estructural deliberadamente singular (grandes luces buscadas a propósito).
- Por qué ocurre: no verificar si existe una decisión de diseño consciente antes de marcar una alerta (`ARCHITECTURAL_ONTOLOGY.md` F.1, excepción explícita).
- Consecuencias: falsa alerta sobre una decisión de diseño legítima.
- Gravedad: Riesgo variable (falso positivo).
- Frecuencia: Baja.
- Detección: no verificable automáticamente sin declaración explícita de la intención de diseño estructural.
- Prevención: verificar si existe una intención declarada de sistema singular antes de marcar la alerta.
- Corrección: retirar la alerta si la intención está justificada y documentada.
- Normativa relacionada: ninguna directa — falso positivo de criterio.
- Efecto en cadena: no directo.

**211. No verificar coherencia entre volumetría permitida y sistema estructural razonable**
- Descripción: la altura y volumetría que el planeamiento permite no se contrasta con si el sistema estructural razonable puede sostenerla en la forma proyectada.
- Por qué ocurre: tratamiento del Dominio 1 (urbanístico) y del Dominio 11 (estructura) de forma completamente aislada.
- Consecuencias: volumetría urbanísticamente viable pero estructuralmente cuestionable en su forma actual.
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: no reconocible desde el DXF de distribución — requiere datos volumétricos y estructurales combinados.
- Prevención: verificar coherencia entre ambos dominios en fase de anteproyecto volumétrico.
- Corrección: ajustar la volumetría o el sistema estructural.
- Normativa relacionada: ninguna directa — coherencia entre dominios.
- Efecto en cadena: no directo.

**212. Ignorar el efecto de mover una escalera sobre la continuidad estructural**
- Descripción: se reubica la escalera principal sin verificar el efecto sobre la continuidad estructural vertical del edificio completo.
- Por qué ocurre: tratamiento del cambio de posición de escalera como asunto puramente de circulación, sin verificar su efecto estructural.
- Consecuencias: incoherencia estructural sobrevenida en todas las plantas afectadas.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: no reconocible con el flujo actual de un único DXF.
- Prevención: tratar todo cambio de posición de escalera como disparador de verificación de continuidad estructural, superficie y evacuación simultáneamente.
- Corrección: verificar y ajustar según corresponda.
- Normativa relacionada: DB-SE (referencia conceptual).
- Efecto en cadena: sí — es, literalmente, el efecto empírico #10 de `CHAIN_REASONING.md`, el de mayor alcance simultáneo de todos los 20.

**213. No verificar apoyo de patinillo vertical sobre elemento estructural**
- Descripción: el patinillo de instalaciones que conecta núcleos húmedos entre plantas no se verifica contra la posición de los elementos estructurales de esas plantas.
- Por qué ocurre: coordinación deficiente entre Dominio 10 (instalaciones) y Dominio 11 (estructura).
- Consecuencias: conflicto de posición entre patinillo y elemento estructural, descubierto tarde.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: no reconocible sin datos combinados de estructura e instalaciones, ninguno de los dos disponible con fiabilidad hoy.
- Prevención: coordinar la posición de patinillos con la malla estructural desde el anteproyecto.
- Corrección: reubicar el patinillo o adaptar la solución estructural local.
- Normativa relacionada: ninguna directa — coordinación entre dominios.
- Efecto en cadena: no directo.

**214. Sobrestimar la fiabilidad de un análisis estructural sin datos de más de una planta**
- Descripción: se presenta un análisis de coherencia estructural con la misma confianza tenga o no datos de varias plantas disponibles.
- Por qué ocurre: no distinguir el nivel de confianza según la cantidad de datos realmente disponibles (`ARCHITECTURAL_ONTOLOGY.md` F.1 §10).
- Consecuencias: expectativa de certeza incorrecta.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable automáticamente — error de comunicación de confianza.
- Prevención: declarar siempre el nivel de confianza según los datos realmente disponibles (`UNCERTAINTY_MODEL.md`).
- Corrección: corregir la comunicación del nivel de confianza.
- Normativa relacionada: ninguna — error de comunicación.
- Efecto en cadena: no directo.

**215. No distinguir aviso de revisión de conclusión estructural firme**
- Descripción: repetición, formulada como principio general, del error 208.
- Por qué ocurre: mismo origen.
- Consecuencias: mismo tipo.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: mismo mecanismo que el error 208.
- Prevención: mismo mecanismo.
- Corrección: mismo mecanismo.
- Normativa relacionada: ninguna — error de comunicación.
- Efecto en cadena: no directo.

**216. Reforma de tabiquería que en realidad afecta a un elemento de carga no identificado**
- Descripción: consecuencia práctica del error 206 — se ejecuta una demolición de "tabiquería" que resulta ser, en realidad, un elemento de carga.
- Por qué ocurre: mismo origen que el error 206, llevado a su consecuencia de obra real.
- Consecuencias: riesgo estructural real, potencialmente grave, ya en fase de ejecución.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible desde el DXF con fiabilidad, mismo límite que el error 206.
- Prevención: nunca autorizar demolición de partición sin verificación de continuidad vertical previa.
- Corrección: paralización inmediata de obra y verificación estructural real por técnico competente.
- Normativa relacionada: DB-SE.
- Efecto en cadena: sí, el más grave de esta categoría por ocurrir ya en fase de ejecución, no de diseño.

---

## Categoría 12 — Efectos en cadena y conflictos entre dominios (20)

*Cada error de esta categoría es la forma de "error de diseño" de uno de los 20 efectos en cadena empíricos ya catalogados en `CHAIN_REASONING.md` — no se repite aquí su descripción completa cuando ya existe en otra categoría, se cita el número correspondiente y se remite a los diez campos ya descritos.*

**217. No verificar el efecto de ensanchar un pasillo sobre la pieza adyacente** — `CHAIN_REASONING.md` efecto #1.
- Descripción: ensanchar un pasillo por accesibilidad reduce la superficie de la habitación adyacente por debajo del mínimo sin que se verifique.
- Por qué ocurre: resolver el conflicto de accesibilidad de forma local, sin propagar su efecto.
- Consecuencias: incumplimiento sobrevenido en la pieza adyacente.
- Gravedad: Bloqueante.
- Frecuencia: Alta.
- Detección: verificable por recomputo automático de la pieza adyacente tras cualquier cambio de ancho de pasillo.
- Prevención: tratar todo ensanche de pasillo como disparador de recomputo de superficie de piezas adyacentes.
- Corrección: buscar superficie compensatoria en otra pieza de menor prioridad.
- Normativa relacionada: CTE DB-SUA y decreto de habitabilidad.
- Efecto en cadena: es, en sí mismo, el efecto encadenado — no genera uno adicional salvo que la compensación toque una tercera pieza.

**218. No verificar el efecto de ampliar una ventana sobre la demanda energética** — efecto #2, remisión completa al error 68.

**219. No verificar el efecto de desplazar un tabique sobre el pasillo de evacuación** — efecto #3.
- Descripción: ganar superficie de dormitorio desplazando un tabique estrecha el pasillo de evacuación por debajo del mínimo.
- Por qué ocurre: mismo patrón de resolución local sin propagación que el error 217.
- Consecuencias: incumplimiento de evacuación sobrevenido.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: verificable por recomputo automático del pasillo tras cualquier cambio de tabiquería adyacente.
- Prevención: mismo mecanismo que el error 217, aplicado a evacuación.
- Corrección: restituir el ancho del pasillo o buscar la superficie en otra pieza.
- Normativa relacionada: CTE DB-SI.
- Efecto en cadena: es, en sí mismo, el efecto encadenado.

**220. No verificar el efecto de eliminar un muro sobre la compartimentación acústica** — efecto #4, remisión completa al error 126.

**221. No verificar el efecto de reubicar un baño sobre el apilamiento de bajantes** — efecto #5, remisión completa a los errores 184 y 193.

**222. No verificar el efecto de ampliar superficie privativa sobre el rellano común** — efecto #6, remisión completa al error 120.

**223. No verificar todas las exigencias que activa un cambio de uso de golpe** — efecto #7, remisión completa al error 35.

**224. No verificar accesibilidad y evacuación por separado al dividir una vivienda**
- Descripción: dividir una vivienda en dos unidades independientes obliga a que cada una cumpla programa mínimo, accesibilidad y evacuación por separado — no verificarlo dispara incumplimientos en ambas unidades resultantes.
- Por qué ocurre: tratar la división como un cambio administrativo de titularidad sin recomputar cada unidad como un proyecto normativo completo nuevo.
- Consecuencias: dos unidades incumpliendo exigencias que, unidas, sí satisfacían.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no verificable sin recomputo automático completo de ambas unidades resultantes tras la división.
- Prevención: tratar toda división de unidad como disparador de evaluación completa de cada una de las dos resultantes.
- Corrección: ajustar cada unidad individualmente hasta que ambas cumplan.
- Normativa relacionada: todas las que dependen de tipología y programa mínimo.
- Efecto en cadena: es, en sí mismo, el efecto empírico #8 de `CHAIN_REASONING.md`.

**225. No verificar el efecto de fusionar dos viviendas sobre el umbral de exigencia de ascensor** — efecto #9.
- Descripción: fusionar dos unidades reduce el número total de viviendas del edificio, pudiendo cambiar el umbral normativo de exigencia de ascensor o accesibilidad aplicable al conjunto.
- Por qué ocurre: tratar la fusión como cambio interno a esas dos unidades sin verificar su efecto sobre el umbral que afecta a todo el edificio.
- Consecuencias: reevaluación de una exigencia que afecta a todas las unidades del edificio, no solo a las dos fusionadas.
- Gravedad: Riesgo variable.
- Frecuencia: Baja.
- Detección: verificable si el recuento total de unidades se recalcula automáticamente tras la fusión.
- Prevención: tratar toda fusión de unidades como disparador de recomputo del umbral de exigencias a nivel de edificio completo.
- Corrección: reevaluar el umbral aplicable con el nuevo recuento.
- Normativa relacionada: CTE DB-SUA, umbral por número de viviendas.
- Efecto en cadena: es, en sí mismo, el efecto encadenado.

**226. No verificar el efecto simultáneo de mover la escalera principal** — efecto #10, remisión completa al error 212 (el efecto de mayor alcance simultáneo de los 20).

**227. No verificar el efecto de aumentar la altura libre sobre la altura máxima permitida** — efecto #11.
- Descripción: aumentar la altura libre de una planta incrementa la altura total del edificio, pudiendo superar el máximo urbanístico permitido.
- Por qué ocurre: tratar la altura libre como decisión puramente de calidad interior sin verificar su efecto en el cómputo urbanístico de altura total.
- Consecuencias: incumplimiento urbanístico sobrevenido por una decisión de confort interior.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: no reconocible desde un único DXF de planta — dato de sección/alzado.
- Prevención: verificar el margen de altura urbanística disponible antes de decidir cualquier aumento de altura libre.
- Corrección: reducir la altura libre o compensar en otra planta.
- Normativa relacionada: ordenanza de altura reguladora.
- Efecto en cadena: es, en sí mismo, el efecto encadenado.

**228. No verificar el efecto de reducir un retranqueo sobre la servidumbre de luces** — efecto #12, remisión completa al error 13.

**229. No verificar el efecto de ampliar un patio sobre la superficie edificable** — efecto #13, remisión completa a los errores 63 y 72.

**230. No verificar el efecto de cerrar una circulación abierta sobre la calidad espacial** — efecto #14.
- Descripción: cerrar una zona de circulación abierta para cumplir sectorización rompe la relación visual/espacial que sostenía la calidad percibida de una vivienda de planta abierta.
- Por qué ocurre: resolver la exigencia normativa de sectorización sin verificar su efecto en calidad espacial.
- Consecuencias: cumplimiento normativo con pérdida de calidad espacial no comunicada como trade-off.
- Gravedad: Recomendable (la calidad, a diferencia de la evacuación del error 116, no es bloqueante).
- Frecuencia: Baja.
- Detección: no reconocible automáticamente — Nivel C.
- Prevención: comunicar siempre el efecto en calidad cuando se resuelve un requisito normativo con coste espacial.
- Corrección: buscar una solución de sectorización con menor coste de calidad espacial si existe.
- Normativa relacionada: CTE DB-SI (la exigencia que lo origina).
- Efecto en cadena: es, en sí mismo, el efecto encadenado — visto ahora desde su otra cara respecto al error 116.

**231. No verificar el efecto de reforzar aislamiento acústico sobre la superficie útil** — efecto #15, remisión completa al error 131.

**232. No verificar el efecto de añadir una ventana en fachada desfavorable** — efecto #16.
- Descripción: añadir una ventana en una fachada de orientación desfavorable mejora la iluminación de una pieza pero introduce riesgo de sobrecalentamiento o de pérdida de aislamiento acústico si esa fachada da a una zona ruidosa.
- Por qué ocurre: decisión de mejora de iluminación tomada sin verificar la tensión conocida con térmica (Dominio 8) o acústica (Dominio 7) según el contexto de esa fachada específica.
- Consecuencias: mejora de un dominio a costa de un empeoramiento en otro, según el caso.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: parcialmente — depende de datos de contexto (ruido exterior) no siempre disponibles.
- Prevención: verificar el contexto de cada fachada (térmico y acústico) antes de decidir ampliar hueco.
- Corrección: compensar con protección solar o refuerzo acústico según el caso.
- Normativa relacionada: CTE DB-HE y DB-HR, según cuál domine en el caso concreto.
- Efecto en cadena: es, en sí mismo, el efecto encadenado.

**233. No verificar el efecto de cambiar la posición de la cocina sobre el recorrido de fontanería** — efecto #17.
- Descripción: cambiar la posición de la cocina en planta altera el recorrido de fontanería/saneamiento y puede alejarla del baño más cercano, encareciendo o complicando la instalación conjunta.
- Por qué ocurre: decisión de distribución tomada sin verificar el efecto sobre la coherencia de instalaciones ya fijada (Dominio 10).
- Consecuencias: sobrecoste o solución técnica forzada de instalaciones.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible con fiabilidad sin datos de instalaciones reales.
- Prevención: verificar el efecto sobre proximidad de piezas húmedas antes de mover cualquiera de ellas.
- Corrección: reubicar o asumir el sobrecoste de instalación.
- Normativa relacionada: ninguna directa — criterio de coherencia técnica.
- Efecto en cadena: es, en sí mismo, el efecto encadenado.

**234. No verificar el efecto de reducir el número de plantas sobre ocupación y protección contra incendio** — efecto #18.
- Descripción: reducir el número de plantas del edificio cambia el cómputo de ocupación total y la altura de evacuación, lo que puede modificar las exigencias de protección contra incendio que antes aplicaban.
- Por qué ocurre: tratar la reducción de plantas como decisión puramente volumétrica/económica sin recomputar toda la cadena de exigencias de evacuación que dependen de ella.
- Consecuencias: exigencias de protección contra incendio desactualizadas tras el cambio.
- Gravedad: Bloqueante.
- Frecuencia: Baja.
- Detección: verificable si el recomputo de ocupación y altura de evacuación se dispara automáticamente tras el cambio.
- Prevención: tratar todo cambio de número de plantas como disparador de recomputo completo del Dominio 6.
- Corrección: reevaluar toda la cadena de evacuación con el nuevo número de plantas.
- Normativa relacionada: CTE DB-SI.
- Efecto en cadena: es, en sí mismo, el efecto encadenado.

**235. No verificar el efecto de incorporar una rampa sobre el recorrido de evacuación** — efecto #19, remisión completa al error 118.

**236. No verificar el efecto de ampliar dormitorios sin ampliar superficie total** — efecto #20.
- Descripción: ampliar el número de dormitorios de una vivienda sin ampliar su superficie total reduce la superficie media por dormitorio y tensiona el cumplimiento de superficie mínima individual en varias piezas a la vez, no solo en la ampliada.
- Por qué ocurre: decisión de programa (más dormitorios) tomada sin verificar su coste distribuido sobre todas las piezas existentes.
- Consecuencias: varios incumplimientos simultáneos de superficie mínima, no uno aislado.
- Gravedad: Bloqueante.
- Frecuencia: Media.
- Detección: verificable por recomputo automático de todas las piezas de dormitorio tras cualquier cambio de programa de número de dormitorios.
- Prevención: verificar el efecto distribuido sobre todas las piezas antes de aumentar el número de dormitorios sin aumentar superficie total.
- Corrección: ampliar la superficie total o reducir el número de dormitorios al nivel que la superficie disponible sostiene con calidad.
- Normativa relacionada: decreto autonómico de habitabilidad.
- Efecto en cadena: es, en sí mismo, el efecto encadenado de mayor dispersión simultánea de los 20 (afecta a varias piezas a la vez, no a una).

---

## Categoría 13 — Riesgo de visado, documentación y responsabilidad profesional (15)

**237. No documentar la justificación de una solución de zona gris**
- Descripción: se adopta una solución en un punto de interpretación normativa ambigua sin dejar constancia escrita de la justificación.
- Por qué ocurre: presión de plazo, confianza excesiva en que el criterio adoptado "se entiende" sin necesidad de escribirlo.
- Consecuencias: reparo de visado sin defensa documental disponible.
- Gravedad: Riesgo variable.
- Frecuencia: Alta.
- Detección: no verificable automáticamente — ausencia de documento, no de dato geométrico.
- Prevención: documentar toda solución de zona gris en el momento en que se adopta, no después.
- Corrección: redactar la justificación retroactivamente, con el riesgo de menor solidez que si se hubiera hecho a tiempo.
- Normativa relacionada: ninguna directa — proceso de defensa documental.
- Efecto en cadena: no directo.

**238. Presentar un hallazgo técnico menor sin documentación que lo defienda**
- Descripción: un hallazgo técnico de severidad baja se entrega sin la documentación que permitiría defenderlo si genera un reparo.
- Por qué ocurre: subestimar hallazgos menores, cuando en la práctica pueden generar más fricción de visado que uno mayor bien justificado (`ARCHITECTURAL_KNOWLEDGE_MAP.md` Dominio 13 §2).
- Consecuencias: reparo de visado sobre un asunto menor, más costoso de resolver a posteriori que de documentar a tiempo.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable automáticamente.
- Prevención: documentar proporcionalmente al riesgo de fricción de visado, no solo a la severidad técnica.
- Corrección: aportar la documentación cuando se solicite, con el coste de tiempo que eso implica.
- Normativa relacionada: ninguna directa — proceso de visado.
- Efecto en cadena: no directo.

**239. No declarar explícitamente una excepción aplicada**
- Descripción: se aplica una excepción normativa (`CONSTRAINT_MODEL.md` §5) sin declararla de forma explícita en la documentación entregada.
- Por qué ocurre: tratar la excepción como algo implícito en el diseño en vez de como una decisión que requiere declaración formal.
- Consecuencias: la excepción aparece, ante el visado, como un incumplimiento no justificado.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable automáticamente sin trazabilidad de excepciones aplicadas.
- Prevención: declarar toda excepción aplicada de forma explícita, nunca implícita.
- Corrección: documentar la excepción retroactivamente.
- Normativa relacionada: la que corresponda a la excepción concreta.
- Efecto en cadena: no directo.

**240. Confiar en un criterio de riesgo variable como si fuera certeza**
- Descripción: se presenta una conclusión de interpretación normativa ambigua con el mismo tono de seguridad que una conclusión de Nivel 1-2.
- Por qué ocurre: simplificación indebida en la comunicación, perdiendo el matiz de incertidumbre real de un criterio de riesgo variable (`DECISION_ENGINE.md` §2, Tipo 1).
- Consecuencias: expectativa incorrecta del cliente sobre la solidez real de la conclusión.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable automáticamente — error de comunicación.
- Prevención: mantener siempre el registro de riesgo variable distinguido del de certeza (`EXPLANATION_ENGINE.md` §2).
- Corrección: corregir la comunicación al nivel de certeza real.
- Normativa relacionada: ninguna directa — error de comunicación.
- Efecto en cadena: no directo.

**241. No registrar la decisión cuando se aparta de la recomendación técnica**
- Descripción: el arquitecto (o el cliente a través de él) decide de forma distinta a la recomendación técnica sin que quede constancia de la decisión ni de su justificación.
- Por qué ocurre: falta de un mecanismo de registro sistemático de decisiones que se apartan de la recomendación (`REASONING_ENGINE_SPEC.md` entidad 17).
- Consecuencias: pérdida de memoria institucional del proyecto, imposibilidad de defender la decisión más adelante.
- Gravedad: Riesgo variable.
- Frecuencia: Alta — la práctica habitual hoy no registra sistemáticamente estas decisiones.
- Detección: no verificable automáticamente sin un mecanismo de registro de decisiones.
- Prevención: registrar toda decisión que se aparta de una recomendación, con su justificación si se aporta.
- Corrección: reconstruir el registro retroactivamente cuando sea posible.
- Normativa relacionada: ninguna directa — memoria de proyecto.
- Efecto en cadena: no directo.

**242. Omitir referencia normativa exacta en la justificación**
- Descripción: se justifica una solución sin citar el artículo o decreto exacto en que se apoya.
- Por qué ocurre: confianza en que "se sabe" cuál es la norma aplicable sin necesidad de citarla explícitamente.
- Consecuencias: justificación más débil ante una revisión de visado.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable automáticamente sin catálogo de Constraint con fuente normativa obligatoria (`CONSTRAINT_MODEL.md` §8, ya invariante de diseño).
- Prevención: citar siempre la fuente normativa exacta, nunca dejarla implícita.
- Corrección: completar la cita normativa retroactivamente.
- Normativa relacionada: la que corresponda a cada caso concreto.
- Efecto en cadena: no directo.

**243. No actualizar la documentación tras un cambio de última hora antes de la entrega**
- Descripción: repetición, desde el ángulo de riesgo de visado, del error 30.
- Por qué ocurre: mismo origen.
- Consecuencias: documentación de visado desconectada del proyecto real entregado.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: mismo límite que el error 30.
- Prevención: mismo mecanismo que el error 30.
- Corrección: mismo mecanismo que el error 30.
- Normativa relacionada: ninguna directa — proceso de entrega.
- Efecto en cadena: no directo.

**244. Presentar cálculo de superficie sin trazabilidad hasta la geometría real**
- Descripción: se entrega un valor de superficie sin que se pueda verificar de dónde sale exactamente (qué polígono, qué método de cómputo).
- Por qué ocurre: presentación del resultado final sin conservar la Evidence completa que lo sostiene (`EVIDENCE_MODEL.md`, principio rector).
- Consecuencias: cálculo no verificable de forma independiente, debilidad ante cualquier cuestionamiento.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable automáticamente sin trazabilidad estructurada del cálculo.
- Prevención: conservar siempre la trazabilidad completa de cualquier cálculo de superficie presentado.
- Corrección: reconstruir la trazabilidad retroactivamente cuando sea posible.
- Normativa relacionada: criterio de cómputo de superficie.
- Efecto en cadena: no directo.

**245. No advertir al cliente de un riesgo de visado detectado durante el desarrollo**
- Descripción: se detecta un riesgo real de reparo de visado durante el desarrollo del proyecto pero no se comunica al cliente hasta la entrega final, o no se comunica en absoluto.
- Por qué ocurre: aplazar comunicaciones incómodas, o simplemente no priorizar qué información merece comunicarse activamente (`DECISION_ENGINE.md` §12, principio de priorización de información).
- Consecuencias: cliente sorprendido por un reparo que ya se sabía posible desde antes.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable automáticamente — error de comunicación y de proceso.
- Prevención: comunicar todo riesgo de visado relevante en el momento en que se detecta, no esperar a la entrega final.
- Corrección: comunicar tan pronto como se detecte el fallo de proceso.
- Normativa relacionada: ninguna directa — comunicación con el cliente.
- Efecto en cadena: no directo.

**246. Firmar sin haber verificado personalmente las zonas de mayor riesgo normativo**
- Descripción: el arquitecto firmante delega por completo la verificación de las zonas de mayor riesgo del proyecto sin revisión personal propia.
- Por qué ocurre: presión de volumen de trabajo, confianza excesiva en el equipo o en herramientas automáticas.
- Consecuencias: responsabilidad profesional asumida sobre un proyecto no verificado personalmente en sus puntos críticos.
- Gravedad: Riesgo variable.
- Frecuencia: Baja (declarada) — probablemente más alta en la práctica real de lo que se reconoce.
- Detección: no verificable automáticamente — proceso interno del despacho.
- Prevención: mantener siempre revisión personal de las zonas de mayor riesgo, sin importar qué herramientas de apoyo se usen.
- Corrección: revisión personal antes de la firma, aunque sea tardía.
- Normativa relacionada: LOE, responsabilidad del proyectista.
- Efecto en cadena: no directo, es el de mayor gravedad de responsabilidad profesional de toda esta categoría.

**247. No conservar el historial de decisiones sobre conflictos resueltos**
- Descripción: repetición, formulada como principio general, del error 241.
- Por qué ocurre: mismo origen.
- Consecuencias: mismo tipo, formulado como pérdida sistemática de memoria institucional.
- Gravedad: Riesgo variable.
- Frecuencia: Alta.
- Detección: mismo límite que el error 241.
- Prevención: mismo mecanismo.
- Corrección: mismo mecanismo.
- Normativa relacionada: ninguna directa — memoria de proyecto.
- Efecto en cadena: no directo.

**248. Confundir una recomendación de calidad con una exigencia obligatoria al documentar**
- Descripción: la memoria de proyecto presenta una recomendación de Nivel 3-4 con el mismo lenguaje de obligatoriedad que un cumplimiento normativo de Nivel 1-2.
- Por qué ocurre: mismo tipo de confusión que el error 174 y el 240, aplicada específicamente a la documentación formal.
- Consecuencias: expectativa incorrecta sobre qué es exigible y qué no, potencialmente ante el propio visado.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable automáticamente — error de comunicación documental.
- Prevención: mantener siempre el registro de certeza correcto en toda la documentación formal.
- Corrección: corregir el lenguaje de la memoria.
- Normativa relacionada: ninguna directa — error de comunicación.
- Efecto en cadena: no directo.

**249. No justificar documentalmente una solución que se aparta del mínimo normativo estándar**
- Descripción: se adopta una solución por debajo del criterio estándar de un dominio (por ejemplo, un baño único en vivienda de 3 dormitorios en régimen unifamiliar donde es admisible, `evaluate_bathroom_ratio`) sin documentar por qué es aceptable en ese caso concreto.
- Por qué ocurre: confianza en que el régimen de excepción "se aplica solo" sin necesidad de justificación explícita.
- Consecuencias: solución correcta pero no defendible documentalmente si se cuestiona.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable automáticamente sin trazabilidad de qué régimen se aplicó y por qué.
- Prevención: documentar siempre por qué se aplica un régimen distinto del estándar, aunque sea normativamente correcto.
- Corrección: documentar retroactivamente.
- Normativa relacionada: régimen de excepción aplicable en cada caso.
- Efecto en cadena: no directo.

**250. Asumir que un criterio aceptado en un proyecto anterior aplica automáticamente al actual**
- Descripción: se traslada, sin verificación, un criterio de interpretación normativa ya aceptado en un proyecto anterior a uno nuevo con circunstancias potencialmente distintas.
- Por qué ocurre: confianza en el precedente sin verificar que las circunstancias concretas siguen siendo comparables — el mismo riesgo que `CONFLICT_ENGINE.md` §4 ya nombra para el Verificador de Precedente (nunca aplicación automática, siempre exposición para verificación).
- Consecuencias: criterio aplicado incorrectamente si las circunstancias del nuevo proyecto difieren de forma relevante.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable automáticamente sin un mecanismo de comparación de precedente, y aun con él, nunca de forma automática, solo como contexto a verificar.
- Prevención: verificar explícitamente la comparabilidad antes de trasladar un criterio de un proyecto a otro.
- Corrección: revisar el criterio aplicado si la comparabilidad no se sostiene.
- Normativa relacionada: la que corresponda al criterio trasladado.
- Efecto en cadena: no directo.

**251. No revisar la coherencia final de toda la documentación antes de la entrega**
- Descripción: variante de cierre de la categoría — no existe una revisión final que verifique la coherencia conjunta de planos, memoria y justificaciones antes de la entrega a visado.
- Por qué ocurre: presión de plazo en la fase final del proyecto, tratamiento de cada documento como una pieza independiente sin verificación cruzada final.
- Consecuencias: acumulación silenciosa de varios de los errores anteriores de esta categoría, descubiertos todos a la vez en fase de visado.
- Gravedad: Riesgo variable.
- Frecuencia: Alta.
- Detección: no verificable automáticamente de forma completa — requiere revisión cruzada humana o un mecanismo de verificación de coherencia documental integral.
- Prevención: reservar una fase explícita de revisión de coherencia final, nunca asumirla como consecuencia automática del proceso.
- Corrección: revisión completa antes de la entrega, aunque implique retrasar el plazo.
- Normativa relacionada: ninguna directa — proceso de entrega.
- Efecto en cadena: sí, es la síntesis de toda la categoría.

---

## Categoría 14 — Proceso, comunicación y gestión de datos del proyecto (20)

**252. Evaluar con datos de formulario que no llegan al motor de reglas**
- Descripción: repetición explícita, como error de proceso puro, del error 16/17 — el Bug #1 real.
- Por qué ocurre: fallo de propagación de parámetro entre capas del sistema.
- Consecuencias: el de mayor alcance de todo este catálogo.
- Gravedad: Bloqueante.
- Frecuencia: Alta (mientras no se corrija).
- Detección: alta, verificable por test de regresión.
- Prevención: garantizar por diseño que ningún dato declarado se pierda entre la entrada y el motor de reglas.
- Corrección: corregir la propagación (`REFACTOR_MASTERPLAN.md` tarea 5).
- Normativa relacionada: todas las que dependen de tipología/zona.
- Efecto en cadena: sí, el mayor de todo el catálogo.

**253. No verificar que un parámetro declarado se propaga a todos los cálculos que lo necesitan**
- Descripción: variante general del error 252 — el mismo patrón puede repetirse con cualquier parámetro futuro, no solo tipología/zona.
- Por qué ocurre: ausencia de una garantía estructural de propagación completa (`FACT_MODEL.md` §1, principio rector: nunca silencio).
- Consecuencias: el mismo tipo de fallo silencioso, potencialmente con cualquier dato futuro nuevo.
- Gravedad: Bloqueante.
- Frecuencia: Media (riesgo estructural, no solo el caso ya confirmado).
- Detección: verificable con una disciplina de test sistemática por cada nuevo parámetro incorporado.
- Prevención: diseñar el modelo de datos de forma que la propagación incompleta sea estructuralmente imposible, no solo verificada caso a caso.
- Corrección: mismo mecanismo que el error 252, generalizado.
- Normativa relacionada: ninguna directa — riesgo estructural de arquitectura de datos.
- Efecto en cadena: sí, potencialmente tan amplio como el error 252 según qué parámetro afecte.

**254. Rellenar en silencio un dato ausente con un valor por defecto**
- Descripción: formulación general del patrón de Bug #1 — cualquier dato ausente sustituido por un valor por defecto sin que quede registrado que ocurrió.
- Por qué ocurre: patrón de programación cómodo (`.get(clave, valor_por_defecto)`) sin verificación de que el dato realmente existía.
- Consecuencias: evaluación completa basada en un supuesto no verificado, sin que nadie lo sepa.
- Gravedad: Bloqueante.
- Frecuencia: Alta — es, según toda la serie de `docs/brain/`, el patrón de fallo más peligroso de todos.
- Detección: verificable por auditoría de código, buscando sistemáticamente patrones de valor por defecto silencioso.
- Prevención: todo dato ausente debe representarse explícitamente como tal (Unknown), nunca sustituirse en silencio.
- Corrección: sustituir cada valor por defecto silencioso por una representación explícita del vacío.
- Normativa relacionada: ninguna directa — principio de diseño de datos.
- Efecto en cadena: sí, potencialmente tan amplio como el error 252.

**255. No distinguir un hecho observado de una hipótesis asumida al comunicar**
- Descripción: se presenta una hipótesis (una estimación, un supuesto) con el mismo lenguaje que un dato medido directamente.
- Por qué ocurre: simplificación indebida en la comunicación del resultado.
- Consecuencias: pérdida de la distinción epistémica que sostiene la confianza en cualquier conclusión posterior.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable automáticamente sin trazabilidad de origen del dato (Fact vs. Assumption/Estimation).
- Prevención: mantener siempre distinguidas ambas categorías en la comunicación (`UNCERTAINTY_MODEL.md` §8).
- Corrección: corregir la comunicación.
- Normativa relacionada: ninguna directa — error de comunicación.
- Efecto en cadena: no directo.

**256. Presentar una estimación como si fuera un dato medido**
- Descripción: variante concreta del error 255 — el proxy de superficie de ventana (`facade_width × 0,25`) u otro similar se presenta sin marcar que es una aproximación.
- Por qué ocurre: mismo origen que el 255.
- Consecuencias: expectativa de precisión que el método no tiene realmente.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: verificable si el origen del dato (Estimation) está correctamente etiquetado en el sistema.
- Prevención: marcar siempre toda Estimation como tal, nunca indistinguible de un dato observado (`UNCERTAINTY_MODEL.md` §4).
- Corrección: corregir la comunicación.
- Normativa relacionada: ninguna directa — error de comunicación.
- Efecto en cadena: no directo.

**257. No indicar el nivel de confianza de una conclusión**
- Descripción: se presenta una conclusión sin ninguna indicación de si su cadena de razonamiento es sólida (Nivel 1-2) o depende de criterio/hipótesis (Nivel 3-4).
- Por qué ocurre: presión por dar respuestas simples, sin el matiz de confianza que la seriedad profesional exige.
- Consecuencias: el cliente no puede distinguir qué partes del informe confiar más y cuáles menos.
- Gravedad: Riesgo variable.
- Frecuencia: Alta.
- Detección: no verificable automáticamente sin un mecanismo de Confidence explícito (`REASONING_ENGINE_SPEC.md` entidad 20, hoy no implementado en producción).
- Prevención: acompañar toda conclusión con su nivel de confianza cualitativo.
- Corrección: revisar la comunicación de resultados para incorporar el nivel de confianza.
- Normativa relacionada: ninguna directa — error de comunicación.
- Efecto en cadena: no directo.

**258. Evaluar sobre una versión desactualizada tras una revisión del cliente**
- Descripción: repetición, desde el ángulo de comunicación con el cliente, del error 30/45/157.
- Por qué ocurre: mismo origen.
- Consecuencias: mismo tipo.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: mismo límite que el error 30.
- Prevención: mismo mecanismo.
- Corrección: mismo mecanismo.
- Normativa relacionada: ninguna directa — error de proceso.
- Efecto en cadena: no directo.

**259. No verificar coherencia entre memoria escrita y plano**
- Descripción: repetición, formulada como principio general, del error 26.
- Por qué ocurre: mismo origen.
- Consecuencias: mismo tipo.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: mismo mecanismo que el error 26.
- Prevención: mismo mecanismo.
- Corrección: mismo mecanismo.
- Normativa relacionada: ninguna directa — coherencia documental.
- Efecto en cadena: no directo.

**260. Ignorar una preferencia declarada por el cliente al generar una recomendación**
- Descripción: el sistema o el arquitecto genera una recomendación sin considerar una preferencia ya declarada explícitamente por el cliente.
- Por qué ocurre: falta de un mecanismo que capture y consulte sistemáticamente las preferencias declaradas antes de generar recomendaciones (`REASONING_ENGINE_SPEC.md` entidad 13).
- Consecuencias: recomendación desalineada con lo que el cliente ya pidió, generando fricción evitable.
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: no verificable automáticamente sin captura sistemática de Preference.
- Prevención: consultar siempre las preferencias declaradas antes de generar cualquier recomendación.
- Corrección: regenerar la recomendación incorporando la preferencia.
- Normativa relacionada: ninguna — criterio de proceso.
- Efecto en cadena: no directo.

**261. Aplicar una preferencia del cliente por encima de un incumplimiento bloqueante**
- Descripción: se cede a una preferencia declarada del cliente relajando, de hecho, una exigencia bloqueante.
- Por qué ocurre: presión comercial o de relación con el cliente sobre el criterio técnico del arquitecto (`DECISION_ENGINE.md` §9, invariante violada).
- Consecuencias: incumplimiento real oculto tras una decisión presentada como preferencia legítima.
- Gravedad: Bloqueante.
- Frecuencia: Baja (declarada) — de los errores de mayor gravedad ética de todo el catálogo si ocurre.
- Detección: no verificable automáticamente — requiere verificar si la preferencia aplicada contradice un Problem bloqueante activo.
- Prevención: nunca permitir que una preferencia relaje un incumplimiento bloqueante, sin excepción (`DECISION_ENGINE.md` §9).
- Corrección: revertir la decisión y resolver el incumplimiento por la vía correcta.
- Normativa relacionada: la que corresponda al incumplimiento relajado indebidamente.
- Efecto en cadena: no directo, pero de responsabilidad profesional severa.

**262. No comunicar explícitamente cuando una recomendación se aparta de una preferencia**
- Descripción: el sistema o el arquitecto genera una recomendación que no sigue una preferencia declarada, sin decir explícitamente que se está apartando de ella.
- Por qué ocurre: mismo origen general que el error 260, en su forma inversa — la preferencia se conoce pero se ignora sin comunicarlo.
- Consecuencias: el cliente no entiende por qué la recomendación no refleja lo que pidió.
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: no verificable automáticamente sin captura sistemática de Preference.
- Prevención: comunicar siempre explícitamente cuándo y por qué una recomendación se aparta de una preferencia declarada (`DECISION_ENGINE.md` §9).
- Corrección: corregir la comunicación.
- Normativa relacionada: ninguna — criterio de comunicación.
- Efecto en cadena: no directo.

**263. Repetir un análisis desde cero sin aprovechar decisiones ya tomadas**
- Descripción: cada revisión del proyecto se evalúa como si fuera la primera vez, sin memoria de decisiones y conflictos ya resueltos anteriormente.
- Por qué ocurre: ausencia de un mecanismo de memoria del proyecto (`PROJECT_MEMORY.md`, hoy no implementado).
- Consecuencias: ineficiencia y riesgo de contradecir una decisión anterior sin saberlo.
- Gravedad: Riesgo variable.
- Frecuencia: Alta.
- Detección: no verificable automáticamente sin mecanismo de memoria persistente.
- Prevención: mantener memoria de decisiones a lo largo de todo el desarrollo del proyecto.
- Corrección: reconstruir el contexto de decisiones previas antes de continuar el análisis.
- Normativa relacionada: ninguna directa — proceso de gestión de proyecto.
- Efecto en cadena: no directo.

**264. No registrar por qué se descartó una alternativa de diseño ya evaluada**
- Descripción: una alternativa de diseño se evalúa y se descarta, pero no queda constancia de por qué, de forma que puede volver a evaluarse desde cero más adelante.
- Por qué ocurre: mismo origen general que el error 263, específico para Alternatives descartadas (`REASONING_ENGINE_SPEC.md` entidad 16, "queda archivada tanto si se elige como si se descarta").
- Consecuencias: pérdida de tiempo reevaluando algo ya descartado con razón.
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: no verificable automáticamente sin registro de Alternative descartada.
- Prevención: registrar siempre el motivo de descarte de cualquier alternativa evaluada.
- Corrección: reconstruir el registro cuando sea posible.
- Normativa relacionada: ninguna — proceso de gestión de proyecto.
- Efecto en cadena: no directo.

**265. Confundir una discrepancia legítima de criterio con un error del proyecto**
- Descripción: se trata un Conflict Tipo 5 (dos criterios de Nivel 4 igualmente válidos, `CONFLICT_ENGINE.md` §1) como si fuera un error a corregir, en vez de una decisión de diseño legítima a tomar.
- Por qué ocurre: incomodidad con la ambigüedad, presión de "dar una respuesta única" donde legítimamente no existe.
- Consecuencias: presión innecesaria sobre una decisión que, en realidad, no tiene una única respuesta correcta.
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: no verificable automáticamente sin clasificación explícita de tipo de conflicto.
- Prevención: reconocer y comunicar explícitamente cuándo una tensión es una discrepancia legítima, no un error.
- Corrección: reencuadrar la comunicación como elección de criterio, no como corrección pendiente.
- Normativa relacionada: ninguna — criterio de comunicación.
- Efecto en cadena: no directo.

**266. No revisar efectos acumulativos de varios cambios pequeños en la misma sesión**
- Descripción: varios cambios pequeños, cada uno inocuo por separado, cruzan un umbral juntos sin que ninguno individual lo detecte (`CHAIN_REASONING.md` §4, efectos acumulativos).
- Por qué ocurre: verificación de cada cambio de forma aislada, sin memoria del conjunto de cambios de la sesión de edición completa.
- Consecuencias: incumplimiento sobrevenido por la suma, no detectable analizando cada cambio por separado.
- Gravedad: Bloqueante (según qué umbral se cruce).
- Frecuencia: Alta — según `CHAIN_REASONING.md` §4, es exactamente el patrón que un sistema que solo detecta efectos inmediatos falla en capturar en uso real.
- Detección: no verificable con el flujo actual de evaluación de un único estado — requiere registro corriente de sesión (`PROJECT_MEMORY.md` §3, hoy no implementado).
- Prevención: mantener un registro acumulado de cambios de sesión y re-verificar tras cada uno, no solo al final.
- Corrección: identificar y corregir el efecto acumulado una vez detectado.
- Normativa relacionada: la que corresponda al umbral finalmente cruzado.
- Efecto en cadena: sí, por definición — es la categoría de efecto en cadena menos visible de todas.

**267. Aceptar un cambio del cliente sin volver a propagar sus consecuencias**
- Descripción: se acepta un cambio solicitado por el cliente sin verificar su efecto en cadena sobre el resto del proyecto ya evaluado.
- Por qué ocurre: tratar la petición del cliente como un cambio local sin re-ejecutar la verificación completa del proyecto.
- Consecuencias: mismo tipo que numerosos errores de la categoría 12, aquí desde el ángulo de origen del cambio (petición de cliente, no decisión interna del arquitecto).
- Gravedad: Bloqueante (según el efecto en cadena real).
- Frecuencia: Alta.
- Detección: no verificable sin mecanismo de re-propagación automática tras cualquier Change.
- Prevención: tratar todo cambio solicitado por el cliente exactamente igual que cualquier otro cambio, sujeto a re-propagación completa.
- Corrección: re-verificar todo el proyecto tras aceptar el cambio.
- Normativa relacionada: la que corresponda al efecto en cadena concreto.
- Efecto en cadena: sí, es la causa raíz de proceso detrás de la mayoría de la categoría 12.

**268. No verificar consistencia de nomenclatura de piezas entre versiones**
- Descripción: el nombre o etiqueta de una pieza cambia entre versiones del plano sin que se verifique que sigue refiriéndose al mismo espacio real.
- Por qué ocurre: ausencia de un identificador estable de pieza a través de revisiones (`FACT_MODEL.md` §7, id de concepto estable — mecanismo de diseño, no todavía en producción).
- Consecuencias: pérdida de trazabilidad de qué pieza es cuál entre versiones sucesivas del proyecto.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable automáticamente sin un mecanismo de identidad estable de pieza.
- Prevención: mantener nomenclatura consistente entre versiones, o un mecanismo de identidad estable independiente del nombre.
- Corrección: verificar manualmente la correspondencia entre versiones cuando la nomenclatura cambia.
- Normativa relacionada: ninguna directa — trazabilidad de proyecto.
- Efecto en cadena: no directo.

**269. Ignorar que dos observaciones distintas describen el mismo hallazgo real**
- Descripción: dos sistemas o bloques de evaluación distintos (por ejemplo, `evaluator.py` y `spatial_quality.py`) detectan, de forma independiente, el mismo problema real subyacente sin que se reconozca como un único hallazgo.
- Por qué ocurre: ausencia de un mecanismo de deduplicación por causa raíz compartida (`OBSERVATION_MODEL.md` §4, ya diseñado, no implementado en producción).
- Consecuencias: el cliente ve "dos problemas" donde hay uno, con la confusión que eso genera.
- Gravedad: Preferencial.
- Frecuencia: Media — es, literalmente, el caso real ya documentado de la unidad VT6/2 de `ejemplo.dxf`.
- Detección: no verificable automáticamente sin el mecanismo de agrupación por causa raíz.
- Prevención: implementar el mecanismo de deduplicación por causa raíz cuando el volumen de hallazgos lo justifique.
- Corrección: comunicar manualmente la relación entre ambos hallazgos mientras el mecanismo no exista.
- Normativa relacionada: ninguna directa — presentación de resultados.
- Efecto en cadena: no directo.

**270. No priorizar qué información insuficiente merece preguntarse activamente**
- Descripción: se trata cualquier dato ausente con el mismo nivel de urgencia, sin distinguir cuáles cambiarían sustancialmente la conclusión y cuáles no.
- Por qué ocurre: ausencia de un criterio de apalancamiento de decisión (`DECISION_ENGINE.md` §12, ya diseñado) aplicado en la práctica.
- Consecuencias: sobrecarga de preguntas al cliente sobre datos de bajo impacto, o, en sentido inverso, omisión de preguntar sobre un dato realmente crítico.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: no verificable automáticamente sin el mecanismo de apalancamiento implementado.
- Prevención: aplicar sistemáticamente el criterio de apalancamiento antes de decidir qué preguntar activamente.
- Corrección: revisar qué preguntas eran realmente necesarias y cuáles no.
- Normativa relacionada: ninguna directa — criterio de proceso.
- Efecto en cadena: no directo.

**271. Confiar en el criterio ya validado de otro proyecto sin verificar que aplica**
- Descripción: repetición, formulada de forma más general, del error 250.
- Por qué ocurre: mismo origen.
- Consecuencias: mismo tipo.
- Gravedad: Riesgo variable.
- Frecuencia: Media.
- Detección: mismo límite que el error 250.
- Prevención: mismo mecanismo.
- Corrección: mismo mecanismo.
- Normativa relacionada: la que corresponda al criterio trasladado.
- Efecto en cadena: no directo.

---

## Categoría 15 — Relaciones funcionales entre espacios (20)

*Cada error de esta categoría corresponde a la violación de uno de los criterios ya fijados en `FUNCTIONAL_RELATIONS.md` — se cita la sección de origen y se completan los diez campos propios de este catálogo.*

**272. Dormitorio sin proximidad razonable al baño que le sirve** — `FUNCTIONAL_RELATIONS.md` §1.
- Descripción: la distancia entre un Dormitorio y el Baño que lo sirve es mayor de lo que el criterio de proximidad preferente aconseja.
- Por qué ocurre: posición del núcleo húmedo fijada por otros criterios sin ponderar esta relación.
- Consecuencias: pérdida de calidad de uso cotidiano, mismo tipo que el error 168.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: alta, mismo mecanismo que el error 168.
- Prevención: verificar esta proximidad desde el anteproyecto.
- Corrección: reubicar si el margen del proyecto lo permite.
- Normativa relacionada: ninguna — criterio de composición.
- Efecto en cadena: no directo.

**273. Cocina sin proximidad directa al comedor** — §1. Remisión completa al error 179.

**274. Trastero alejado del acceso o vía de servicio** — §1.
- Descripción: el trastero se ubica lejos del punto de acceso o de la vía de servicio de la vivienda, penalizando su uso real.
- Por qué ocurre: posición decidida por disponibilidad de superficie residual sin verificar el criterio de proximidad preferente.
- Consecuencias: pieza formalmente conforme pero de bajo uso real.
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: alta — verificable por distancia entre centroides de Trastero y Vestíbulo/acceso, una vez ambos reconocidos.
- Prevención: verificar esta proximidad al asignar la posición del trastero.
- Corrección: reubicar si el margen del proyecto lo permite.
- Normativa relacionada: ninguna — criterio de composición.
- Efecto en cadena: no directo.

**275. Vestidor sin conexión directa con el dormitorio al que sirve** — §9 (dependencia funcional).
- Descripción: el vestidor no tiene acceso directo desde el dormitorio al que funcionalmente sirve.
- Por qué ocurre: posición decidida sin verificar la dependencia existencial ya fijada en `FUNCTIONAL_RELATIONS.md` §9.
- Consecuencias: pieza que pierde su sentido funcional (indistinguible, en la práctica, de un trastero pequeño).
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: alta, verificable por adyacencia geométrica entre ambas piezas.
- Prevención: verificar la conexión directa como requisito de posición del vestidor.
- Corrección: reubicar o reclasificar como trastero si no se puede resolver la conexión.
- Normativa relacionada: ninguna — criterio de composición.
- Efecto en cadena: no directo.

**276. Aseo de cortesía ubicado en zona privada** — §1.
- Descripción: el aseo destinado a visitas se ubica en la zona de dormitorios en vez de en la zona social.
- Por qué ocurre: no distinguir el criterio de ubicación de Aseo (zona social) del de Baño (proximidad a dormitorios), ambos tratados igual por error.
- Consecuencias: pieza que no cumple su función real de servir a las visitas sin invadir la privacidad de la vivienda.
- Gravedad: Preferencial.
- Frecuencia: Baja.
- Detección: alta, verificable por posición relativa del Aseo respecto a las zonas ya clasificadas.
- Prevención: verificar la ubicación del Aseo contra el criterio específico de zona social, distinto del de Baño.
- Corrección: reubicar si el margen del proyecto lo permite.
- Normativa relacionada: ninguna — criterio de composición.
- Efecto en cadena: no directo.

**277. Recorrido de servicio obligado a atravesar el salón** — §3.
- Descripción: el recorrido de servicio (cocina-lavadero-trastero) no tiene un trayecto propio y debe atravesar el Salón.
- Por qué ocurre: distribución que no reserva un recorrido de servicio diferenciado del social.
- Consecuencias: interferencia constante entre ambos usos, mismo tipo de problema que el error 166.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible sin el grafo de circulación conectado.
- Prevención: verificar la existencia de un recorrido de servicio diferenciado desde el anteproyecto, salvo que el programa no lo sostenga (`FUNCTIONAL_RELATIONS.md` §10.3).
- Corrección: redistribuir para separar ambos recorridos si el margen del proyecto lo permite.
- Normativa relacionada: ninguna — criterio de composición.
- Efecto en cadena: no directo.

**278. Ausencia de filtro entre zona de instalaciones y pieza habitable adyacente** — §5.
- Descripción: repetición, formulada como principio general, del error 124/190.
- Por qué ocurre: mismo origen.
- Consecuencias: mismo tipo.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: alta, mismo mecanismo que el error 123.
- Prevención: interponer siempre un filtro entre espacio técnico y pieza habitable sensible.
- Corrección: reubicar o interponer el filtro.
- Normativa relacionada: ninguna directa — criterio de composición, aunque tensiona con CTE DB-HR si el ruido es real.
- Efecto en cadena: no directo.

**279. Garaje colectivo bajo un dormitorio sin considerar el criterio de composición** — §2.
- Descripción: la posición de un dormitorio en planta coincide, verticalmente, con el garaje colectivo de la planta inferior, sin que se haya evaluado esta relación al distribuir.
- Por qué ocurre: distribución de plantas residenciales y de garaje resuelta de forma independiente.
- Consecuencias: ruido de motor y portón sobre una pieza de descanso, la peor combinación posible según `FUNCTIONAL_RELATIONS.md` §2.
- Gravedad: Recomendable.
- Frecuencia: Media.
- Detección: no reconocible con el flujo actual de un único DXF por evaluación — requiere el conjunto de plantas.
- Prevención: verificar esta coincidencia vertical desde el anteproyecto, priorizando Distribuidor o Trastero sobre garaje.
- Corrección: reasignar usos entre plantas si el margen del proyecto lo permite.
- Normativa relacionada: ninguna directa — criterio de composición.
- Efecto en cadena: no directo.

**280. Distribuidor que solo conecta con una única pieza** — §9.
- Descripción: un elemento etiquetado como Distribuidor solo da acceso a una pieza, sin cumplir su función real de reparto.
- Por qué ocurre: geometría residual de la distribución clasificada como Distribuidor sin verificar que cumple la dependencia funcional mínima (`FUNCTIONAL_RELATIONS.md` §9: conectar más de una pieza).
- Consecuencias: indicio de circulación mal resuelta, no un Distribuidor legítimo.
- Gravedad: Preferencial.
- Frecuencia: Baja.
- Detección: alta — verificable contando cuántas piezas conecta el elemento clasificado como Distribuidor.
- Prevención: verificar esta condición mínima al clasificar una pieza como Distribuidor.
- Corrección: reclasificar como parte de la pieza a la que da acceso, o redistribuir.
- Normativa relacionada: ninguna — criterio de composición.
- Efecto en cadena: no directo.

**281. Comedor sin proximidad ni a cocina ni a salón** — §1.
- Descripción: un Comedor independiente no tiene proximidad razonable con ninguna de las dos piezas de las que depende funcionalmente.
- Por qué ocurre: posición decidida por disponibilidad geométrica sin verificar la dependencia funcional (`FUNCTIONAL_RELATIONS.md` §9).
- Consecuencias: pieza que pierde gran parte de su sentido de uso.
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: alta, verificable por distancia a ambas piezas de referencia.
- Prevención: verificar esta proximidad al asignar la posición del Comedor.
- Corrección: reubicar si el margen del proyecto lo permite.
- Normativa relacionada: ninguna — criterio de composición.
- Efecto en cadena: no directo.

**282. Terraza vinculada a pieza secundaria en vez de a la principal** — §1. Remisión completa al error 180.

**283. Recorrido social que obliga a cruzar la cocina** — §3.
- Descripción: el recorrido que sigue una visita hacia el Salón atraviesa la Cocina.
- Por qué ocurre: distribución que no verifica el recorrido social completo (mismo origen que el error 163/277).
- Consecuencias: exposición de una zona de servicio al recorrido de mayor visibilidad de la vivienda.
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: no reconocible sin el grafo de circulación conectado.
- Prevención: verificar el recorrido social completo desde el anteproyecto.
- Corrección: redistribuir para evitar el cruce.
- Normativa relacionada: ninguna — criterio de composición.
- Efecto en cadena: no directo.

**284. Baño accesible desde el salón sin ningún filtro de privacidad** — §2. Remisión completa al error 182/134.

**285. Núcleo húmedo sin relación de apilamiento con el de la planta inferior** — §1 (proximidad vertical). Remisión completa al error 184.

**286. Zona de día y zona de noche sin ningún elemento de transición reconocible** — §4. Remisión completa al error 163/164.

**287. Pasillo evaluado con el mismo criterio de proporción que una pieza de estar**
- Descripción: se aplica la heurística de "pieza tubo" (pensada para Dormitorio/Salón) a un Distribuidor o Pasillo, que por definición y correctamente es alargado.
- Por qué ocurre: aplicación mecánica de una regla de calidad sin condicionarla al uso real de la pieza (`SPACE_TAXONOMY.md` 4.2, error ya nombrado explícitamente allí).
- Consecuencias: falsa alerta de calidad sobre una pieza que, en realidad, está correctamente proporcionada para su función.
- Gravedad: Preferencial (falso positivo).
- Frecuencia: Media.
- Detección: verificable si el catálogo de heurísticas de calidad excluye explícitamente a Pasillo/Distribuidor de la heurística de proporción.
- Prevención: condicionar toda heurística de calidad al uso real de la pieza antes de aplicarla.
- Corrección: excluir Pasillo/Distribuidor del catálogo de piezas evaluadas por esa heurística concreta.
- Normativa relacionada: ninguna — falso positivo de criterio.
- Efecto en cadena: no directo.

**288. Patinillo sin relación de apoyo verificada con elemento estructural** — remisión completa al error 213.

**289. Recorrido nocturno obligado a cruzar la zona social** — §3.
- Descripción: el trayecto Dormitorio-Baño atraviesa el Salón o la zona de estar en vez de mantenerse dentro de la zona de noche.
- Por qué ocurre: posición del baño fijada sin verificar el recorrido nocturno completo (`FUNCTIONAL_RELATIONS.md` §3, el recorrido más repetido de la vivienda).
- Consecuencias: pérdida de privacidad e incomodidad real en el uso más frecuente de la vivienda.
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: no reconocible sin el grafo de circulación conectado.
- Prevención: verificar que el recorrido nocturno se mantiene dentro de la zona de noche.
- Corrección: reubicar el baño o redistribuir la zonificación.
- Normativa relacionada: ninguna — criterio de composición.
- Efecto en cadena: no directo.

**290. Ausencia de relación funcional entre plaza de garaje y la vivienda a la que sirve** — remisión completa al error 8.1 de vínculo ya tratado en la categoría 8 de errores de estructura/instalaciones (no numerado aparte en esta categoría; ver error 279 para el caso de composición vertical relacionado).
- Descripción: la plaza de garaje asignada a una vivienda no tiene ninguna relación de proximidad razonable con el núcleo de circulación vertical que sirve a esa vivienda.
- Por qué ocurre: asignación de plazas por disponibilidad geométrica sin verificar a qué vivienda sirve cada una.
- Consecuencias: uso cotidiano degradado (recorrido largo desde la plaza hasta la vivienda).
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: no reconocible sin dato de vinculación explícita entre plaza y vivienda.
- Prevención: verificar proximidad razonable al asignar plazas de garaje a viviendas concretas.
- Corrección: reasignar plazas si el margen del proyecto lo permite.
- Normativa relacionada: ninguna — criterio de composición.
- Efecto en cadena: no directo.

**291. Rampa de garaje sin relación coherente con el resto del itinerario del edificio**
- Descripción: la rampa de acceso a garaje se diseña sin coordinación con la posición del resto de itinerarios peatonales del edificio, generando cruces de circulación vehicular y peatonal no resueltos.
- Por qué ocurre: proyecto de rampa resuelto de forma independiente al resto de la circulación del edificio.
- Consecuencias: riesgo real de conflicto entre circulación vehicular y peatonal.
- Gravedad: Recomendable.
- Frecuencia: Baja.
- Detección: no reconocible sin el grafo de circulación conectado combinado con datos de tráfico vehicular.
- Prevención: coordinar la posición de la rampa con el resto de itinerarios desde el anteproyecto.
- Corrección: redistribuir para evitar el cruce, o introducir medidas de seguridad específicas en el punto de conflicto.
- Normativa relacionada: ninguna directa — criterio de composición, con implicación de seguridad.
- Efecto en cadena: no directo.

---

## Categoría 16 — Violación de principios de diseño atemporales (15)

*Cada error de esta categoría corresponde a la violación de uno de los 14 principios ya fijados en `ARCHITECTURAL_PRINCIPLES.md` — ninguno de ellos tiene, por definición, normativa relacionada (`ARCHITECTURAL_PRINCIPLES.md`, criterio de inclusión: principios que seguirían siendo ciertos aunque la norma cambiara).*

**292. Pieza habitable interior sin justificación real de imposibilidad física** — `ARCHITECTURAL_PRINCIPLES.md` B.3. Remisión completa al error 64.

**293. Ausencia de ventilación cruzada en parcela que sí la permite geométricamente** — A.1.
- Descripción: el proyecto no aprovecha la doble orientación disponible en la parcela para dotar de ventilación cruzada a las piezas principales.
- Por qué ocurre: distribución decidida sin verificar el margen geométrico real disponible para este principio.
- Consecuencias: piezas dependientes de ventilación mecánica o de ventilación simple, con peor calidad ambiental de la que la parcela permitiría.
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: no reconocible con fiabilidad hoy — requiere datos de Hueco por fachada.
- Prevención: verificar el margen de doble orientación disponible en fase de anteproyecto.
- Corrección: redistribuir piezas principales hacia fachadas no paralelas si el margen del proyecto lo permite.
- Normativa relacionada: ninguna — principio de diseño, no exigencia legal.
- Efecto en cadena: no directo.

**294. Orientación de piezas sin relación con su uso horario** — A.2. Remisión completa al error 169.

**295. Envolvente muy poco compacta sin justificación en clima de fuerte amplitud térmica** — A.3. Remisión completa al error 143.

**296. Resolver el exceso solar únicamente con climatización mecánica pudiendo resolverse con geometría** — A.4.
- Descripción: se compensa el exceso de radiación solar exclusivamente con capacidad de aire acondicionado, sin considerar ninguna solución geométrica pasiva (voladizo, orientación, vegetación).
- Por qué ocurre: la solución mecánica es más simple de especificar en fase de proyecto que coordinar una solución pasiva desde el diseño.
- Consecuencias: mayor coste de uso a largo plazo y menor durabilidad de la solución (`ARCHITECTURAL_PRINCIPLES.md` D.2, principio de perdurabilidad).
- Gravedad: Preferencial.
- Frecuencia: Alta.
- Detección: no reconocible automáticamente — requiere verificar si existe algún elemento de protección solar pasiva previsto, dato no disponible en un DXF de planta.
- Prevención: considerar siempre la jerarquía de soluciones (pasiva antes que mecánica) desde el anteproyecto.
- Corrección: incorporar protección solar pasiva si el margen del proyecto lo permite.
- Normativa relacionada: ninguna — principio de diseño.
- Efecto en cadena: no directo.

**297. Distribución que no admite ninguna flexibilidad de uso futuro sin obra estructural** — D.1.
- Descripción: toda la tabiquería interior coincide con elementos de carga, de forma que ningún cambio de uso futuro es posible sin intervención estructural.
- Por qué ocurre: no considerar el principio de flexibilidad al decidir qué particiones son estructurales y cuáles no.
- Consecuencias: vivienda incapaz de adaptarse a cambios de composición familiar o de uso a lo largo de su vida útil.
- Gravedad: Preferencial.
- Frecuencia: Baja.
- Detección: no reconocible con fiabilidad — depende de distinguir Muro de carga de Tabique, mismo límite ya señalado repetidamente.
- Prevención: reservar, cuando sea posible, al menos algunas particiones interiores como no estructurales, previendo cambios de uso futuros.
- Corrección: no aplica una vez construido sin esa previsión — es una prevención, no una corrección posterior sencilla.
- Normativa relacionada: ninguna — principio de diseño.
- Efecto en cadena: no directo.

**298. Retícula estructural sin ninguna relación con la distribución interior** — B.4. Remisión completa al error 175.

**299. Accesibilidad resuelta como añadido posterior en vez de como principio de diseño** — C.3. Remisión completa al error 90.

**300. Acceso principal sin legibilidad de recorrido para un visitante nuevo** — C.2.
- Descripción: un visitante que entra por primera vez no puede entender, sin señalización explícita, hacia dónde dirigirse.
- Por qué ocurre: geometría de acceso decidida sin considerar la experiencia de un usuario no familiarizado con el edificio.
- Consecuencias: confusión real de uso cotidiano para visitas y repartidores.
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: no reconocible automáticamente — Nivel C, terreno de "espejo, no juez".
- Prevención: verificar la legibilidad del recorrido de acceso desde el punto de vista de un usuario nuevo, no solo del residente habitual.
- Corrección: redistribuir o señalizar el punto de bifurcación confuso.
- Normativa relacionada: ninguna — principio de diseño.
- Efecto en cadena: no directo.

**301. Solución de diseño irreversible adoptada sin ponderar su coste de equivocarse** — D.3.
- Descripción: se toma una decisión de diseño de baja reversibilidad (posición de núcleo de escalera, volumen general) con la misma ligereza que una decisión fácilmente reversible.
- Por qué ocurre: no aplicar el criterio de reversibilidad como factor de la decisión, tratando todas las decisiones de diseño con el mismo peso.
- Consecuencias: coste desproporcionado si la decisión resulta equivocada más adelante en el desarrollo del proyecto.
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: no verificable automáticamente de forma directa — criterio de proceso de decisión, aunque el mecanismo de techos de reversibilidad ya existe diseñado (`RECOMMENDATION_ENGINE.md` §8).
- Prevención: ponderar siempre la reversibilidad de una decisión antes de tomarla, con mayor cautela cuanto menos reversible sea.
- Corrección: no aplica una vez tomada la decisión irreversible y construida — es puramente preventivo.
- Normativa relacionada: ninguna — principio de diseño.
- Efecto en cadena: no directo, pero potencialmente el de mayor coste si se materializa mal.

**302. Ignorar el mantenimiento futuro de una solución constructiva al decidir el diseño** — D.2. Remisión completa al error 296 en su vertiente de perdurabilidad, más el principio general de `ARCHITECTURAL_PRINCIPLES.md` D.2.

**303. Escala y proporción humana no verificadas en el dimensionado de un elemento de paso** — C.1.
- Descripción: un elemento de paso se dimensiona por criterio de composición sin verificar su coherencia con las proporciones del cuerpo humano que lo usará.
- Por qué ocurre: priorizar composición formal sobre ergonomía básica.
- Consecuencias: elemento normativamente conforme (si cumple el mínimo) pero con proporción incómoda en el uso real.
- Gravedad: Preferencial.
- Frecuencia: Baja.
- Detección: alta para los componentes puramente dimensionales, ya en producción vía el mecanismo de ancho mínimo.
- Prevención: verificar proporción antropométrica, no solo el mínimo normativo, en cualquier elemento de paso.
- Corrección: redimensionar el elemento afectado.
- Normativa relacionada: ninguna — principio de diseño.
- Efecto en cadena: no directo.

**304. Separar por completo los flujos social y de servicio en un programa que no lo sostiene** — B.1 (aplicación forzada del principio).
- Descripción: se fuerza una separación completa de recorridos en una vivienda de superficie reducida, produciendo una circulación general peor que la que resultaría de aceptar un recorrido único bien resuelto.
- Por qué ocurre: aplicación mecánica de un principio de diseño sin verificar si el programa disponible lo sostiene (`ARCHITECTURAL_PRINCIPLES.md` B.1, "cuándo no aplica").
- Consecuencias: pérdida de eficiencia general por perseguir un principio fuera de su rango de aplicación razonable.
- Gravedad: Preferencial.
- Frecuencia: Media.
- Detección: no reconocible automáticamente — juicio de trade-off, Nivel B/C.
- Prevención: verificar si el programa disponible sostiene la separación completa antes de perseguirla como objetivo absoluto.
- Corrección: aceptar un recorrido único mejor resuelto en vez de dos recorridos mal resueltos.
- Normativa relacionada: ninguna — principio de diseño, con excepción ya reconocida en su propia definición.
- Efecto en cadena: no directo.

**305. Forzar una zonificación día/noche rígida en un programa que declaró intención de planta abierta** — B.2 (aplicación forzada del principio).
- Descripción: se impone una separación física estricta entre zona de día y de noche pese a que el cliente declaró explícitamente una intención de vivienda abierta y fluida.
- Por qué ocurre: aplicación mecánica de un principio general sin verificar la intención de diseño declarada (`ARCHITECTURAL_QUALITY.md` §4, `ARCHITECTURAL_PRINCIPLES.md` B.2, "cuándo no aplica").
- Consecuencias: proyecto que contradice la intención explícita del cliente en nombre de un principio general mal aplicado.
- Gravedad: Preferencial.
- Frecuencia: Baja.
- Detección: no verificable automáticamente sin el dato de Preference declarada.
- Prevención: verificar siempre la intención de diseño declarada antes de aplicar un principio general de forma rígida.
- Corrección: revisar la distribución conforme a la intención real del cliente.
- Normativa relacionada: ninguna — principio de diseño, con excepción ya reconocida en su propia definición.
- Efecto en cadena: no directo.

**306. Ignorar la respuesta al lugar por repetir una solución estándar** — remite a `ARCHITECTURAL_QUALITY.md` §1 (respuesta al lugar), el principio raíz de la serie, no repetido como entrada propia en `ARCHITECTURAL_PRINCIPLES.md`.
- Descripción: se aplica una solución de proyecto genérica, idéntica a la que se aplicaría en cualquier otro emplazamiento, sin ninguna respuesta a las condiciones reales del lugar (clima, topografía, contexto urbano).
- Por qué ocurre: economía de proyecto (reutilización de una solución ya probada) sin verificar su coherencia con el emplazamiento real.
- Consecuencias: proyecto correcto pero genérico, la antítesis del principio de respuesta al lugar.
- Gravedad: Preferencial.
- Frecuencia: Alta — es, según `ARCHITECTURAL_QUALITY.md` §1, uno de los síntomas más frecuentes de falta de excelencia en la práctica real.
- Detección: no reconocible automáticamente — Nivel C, terreno de "espejo, no juez".
- Prevención: verificar explícitamente qué del proyecto responde a las condiciones reales del emplazamiento antes de darlo por cerrado.
- Corrección: revisar el proyecto contra las condiciones específicas del lugar.
- Normativa relacionada: ninguna — principio de diseño.
- Efecto en cadena: no directo, es el cierre conceptual de todo el catálogo — el error del que, en última instancia, derivan muchos de los 305 anteriores cuando se persigue una solución genérica en vez de una respuesta real al proyecto concreto.

---

## Los 50 errores que ArchMuse debería detectar siempre

**Criterio de selección, aplicado con disciplina antes de nombrar ningún número:** no son los 50 "más graves" en abstracto — son los 50 que combinan **gravedad alta** (Bloqueante o Riesgo variable de alta frecuencia), **detectabilidad real** con el pipeline de datos actual o uno a corto plazo (nunca un error marcado "no reconocible" en su propia ficha, salvo los pocos casos ya parcialmente mitigados en producción), y **frecuencia alta o media** en proyectos reales. Un error muy grave pero indetectable hoy (por ejemplo, el error 112, resistencia al fuego sin dato constructivo) no entra en esta lista — entraría el día en que ArchMuse tenga esos datos, no antes. Esto es, deliberadamente, la misma disciplina de honestidad que gobierna toda la serie: una lista de "lo que se debería detectar siempre" que incluyera errores no detectables sería, en sí misma, una promesa fabricada.

**Ya en producción o con mecanismo casi listo (17):** 16, 17 (Bug #1, los dos de mayor prioridad absoluta), 21/52 (fusión Salón/Cocina), 36, 37, 38, 40 (superficies mínimas), 47 (jerarquía de dormitorios), 61 (ratio de hueco, vía proxy), 69 (orientación), 81/84 (accesibilidad de extremo a extremo, aunque el mecanismo de grafo falta, el patrón de fallo es el más frecuente documentado), 83 (espacio de giro de baño), 92 (efecto cadena #1, pasillo-pieza adyacente), 123/165 (adyacencia dormitorio-escalera/cocina), 168 (recorrido nocturno), 179 (proximidad cocina-comedor).

**Detectables con extensión razonable del pipeline actual, sin necesitar datos que hoy no existen en absoluto (18):** 19 (recuento de unidades), 27/28 (duplicado/omisión de unidad), 43 (descuento de elementos estructurales en superficie), 54 (eficiencia útil/construida global), 63/72 (patio, si se etiqueta explícitamente), 76/80 (ratio de hueco tras cambio de geometría), 91 (accesibilidad vs. evacuación en el mismo tramo, una vez exista grafo de circulación básico), 108/115 (ocupación tras cambio de uso/superficie), 120 (ancho de escalera común tras cambio adyacente), 131 (superficie tras refuerzo acústico), 159/167 (jerarquía servido/servidor por comparación de superficies), 166 (distribuidor sobredimensionado), 184/193 (coherencia vertical de núcleos húmedos, una vez el flujo procese varias plantas), 236 (efecto cadena #20, dormitorios sin superficie total).

**Errores de proceso y comunicación, detectables por disciplina de diseño del propio sistema, no por geometría (15):** 30/45/157/258 (versión desactualizada — un único mecanismo de versión única de verdad los cubre a los cuatro), 174/240/248 (confundir certeza con criterio — un único mecanismo de vocabulario de confianza los cubre a los tres), 254 (valor por defecto silencioso — el principio rector de toda la serie), 255/256/257 (distinguir hecho de hipótesis, y comunicar el nivel de confianza — tres caras del mismo mecanismo), 261 (preferencia por encima de bloqueante — nunca, sin excepción), 266 (efectos acumulativos de sesión), 267 (re-propagación tras cambio de cliente), 269 (deduplicación de hallazgos por causa raíz compartida, el caso VT6/2).

**Total: 50.** Nótese que 4 de ellos (30, 45, 157, 258) comparten un único mecanismo de corrección, igual que otro grupo de 3 (255-257) y otro de 3 (174, 240, 248) — la lista de 50 errores corresponde, en la práctica, a bastantes menos de 50 mecanismos de detección independientes que construir. Esa es, precisamente, la lectura correcta de esta lista: no son 50 features a implementar una por una, son la evidencia de que un número relativamente pequeño de mecanismos bien construidos (propagación de dato sin pérdida, vocabulario de confianza disciplinado, recomputo automático tras cambio, grafo de circulación básico) cubre la mayoría de los 50 a la vez.

---

## Cierre

Trescientos seis errores, agrupados en dieciséis categorías, no son trescientos seis features distintas que ArchMuse tenga que construir una por una — son, como demuestra la lista final de 50, la superficie visible de un número mucho menor de causas raíz reales: fallos de propagación de dato (categoría 2, 12, 14), ausencia de recomputo automático tras un cambio (repetida en más de sesenta entradas de este catálogo bajo distintos disfraces), confusión entre certeza y criterio en la comunicación (repetida en, al menos, quince entradas distintas), y límites reales y honestos del pipeline de datos actual (DXF 2D sin muros, sin estructura, sin instalaciones, sin sección) que ninguna cantidad de reglas nuevas puede superar sin cambiar la fuente de datos misma. Construir bien un pequeño número de mecanismos generales — la disciplina de "nunca silencio" ya fijada desde `FACT_MODEL.md`, el recomputo automático tras cualquier Change, el vocabulario de confianza distinguido en toda comunicación — previene, de un solo golpe, una fracción mucho mayor de estos 306 errores que perseguir cada uno de ellos por separado con una regla dedicada. Es, en el fondo, la misma lección que toda la serie `docs/brain/` ha repetido desde el primer documento: el conocimiento vale por su estructura, no por su volumen — y una base de 306 errores solo es útil si termina reduciéndose, en la implementación real, a un puñado de garantías estructurales bien construidas, nunca a 306 verificaciones sueltas.

