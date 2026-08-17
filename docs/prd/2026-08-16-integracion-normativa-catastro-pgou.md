# PRD — Consulta automática de normativa urbanística por parcela (piloto Madrid)

**Estado:** Implementado con alcance reducido (ver §15) · **Fecha:** 2026-08-16 · **Autor:** ArchMuse (CTO) · **Aprobado por:** Pablo (vía "EJECUCIÓN DE PRD")

---

## 0. Resumen para decidir rápido

Ejecuta `ROADMAP_VISION_ARQUITECTONICA.md` §3.2/§6.4: "piloto de asesor urbanístico en un único municipio real y verificado (Madrid), nunca presentado como cobertura nacional." **Antes de escribir una sola línea de este PRD se ha investigado en vivo la infraestructura real del Ayuntamiento de Madrid** (búsqueda web + `WebFetch` contra los servicios REST reales, 2026-08-16) — igual que este proyecto ya hizo con Catastro/ArcGIS/Overpass. El resultado cambia el alcance honesto de lo que se puede prometer:

**Lo que SÍ existe y es real, verificado hoy:**
- El Ayuntamiento de Madrid publica el PGOUM 97 (vigente en 2026) como servicios ArcGIS REST/OGC reales y públicos en `sigma.madrid.es/hosted/rest/services/` — misma familia técnica que el mosaico de ortofoto ArcGIS ya integrado en `viewer-terreno.js`, así que el patrón de consulta (`query?geometry=...&geometryType=esriGeometryPoint&inSR=4326&f=json`) es conocido y de bajo riesgo técnico.
- Capa real confirmada con geometría consultable por punto: `PGOUM97/PG_CONDICIONES_EDIFICACION` (MapServer, capa 6 "Condiciones de la Edificación", polígonos, campos `CODMANZANA`, `NUMORD`, `COND_EDIF`, `COEF_Z`).
- Capa real confirmada de zonificación: `pgoum97/PG_ORDENACION_SIN_AMBITO` (MapServer, capa 4 "Norma Zonal 1.5", polígonos).

**Lo que NO es tan simple como "pedir el punto y recibir los 4 números" — hallazgo que condiciona todo este PRD:**
1. **Los campos NO son los números finales.** `COND_EDIF` es un código ("Grado 1"–"Grado 5", más "Grado 6: no regulado") que remite a una tabla de la propia normativa impresa (Normas Urbanísticas del PGOUM 97) para traducirse en un `%` de ocupación o un coeficiente de edificabilidad real — verificado leyendo la leyenda (`drawingInfo/renderer/uniqueValueInfos`) del propio servicio, que solo da nombres tipo "Grado 3", no valores numéricos. `COEF_Z` es una cadena de texto libre, no un decimal garantizado.
2. **La cobertura está fragmentada por Norma Zonal, no unificada.** El servicio que sí respondió con datos reales (`PG_ORDENACION_SIN_AMBITO`) resultó llamarse, literalmente, "Norma Zonal 1.5" — sugiriendo que cada Norma Zonal del PGOUM (1.1, 1.2, 1.3, 2.1, 3.1... hay más de una decena) puede vivir en su propio servicio o capa, no en una única capa "toda Madrid, cualquier zona". No se ha confirmado (ni se puede confirmar sin más investigación, fuera del alcance de este documento) que exista una única consulta que resuelva la clave de zona para un punto CUALQUIERA de Madrid.
3. **Disponibilidad del servicio no garantizada**: durante esta misma investigación, `pgoum97/PG_ORDENACION` (el servicio de "Ordenación" general, no el de una Norma Zonal específica) devolvió `"Service not started"` — un servicio ArcGIS parado administrativamente, no un fallo de red. A diferencia de Catastro (SOAP/WFS, disponibilidad de sede electrónica oficial con SLA implícito de administración central) o de Overpass (ya con su propia inestabilidad conocida y ya mitigada en este proyecto), estos servicios municipales no tienen ninguna garantía de disponibilidad continua conocida.
4. **Sistema de coordenadas UTM (EPSG:25830)**, no WGS84 directo — mitigable pidiendo a ArcGIS que reproyecte (`inSR=4326`), pero sin verificar en vivo con una consulta real todavía (Tarea 1 del plan, no una asunción).

**Consecuencia para el alcance de este PRD:** no se puede prometer "edificabilidad permitida, ocupación máxima y retranqueos" como tres números fiables para cualquier parcela de Madrid desde el primer commit. Este PRD separa explícitamente **lo que es una integración de datos real (geometría + código de zona)** de **lo que exige además un trabajo de traducción manual, verificado y acotado (código → número real, para un primer subconjunto pequeño de Normas Zonales)** — mismo criterio que ya aplicó este proyecto a `cte_zonas.py` (cobertura parcial, honesta, ampliable) y al percentil comparativo (nunca presentar un número sin saber de dónde sale).

## 1. Problema que resuelve

Hoy, los límites urbanísticos que alimentan `evaluate_solar_occupation`/`evaluate_buildability`/`evaluate_max_floors`/`evaluate_retranqueos` (`evaluator.py`) y el HUD del Sandbox (implementado en `docs/prd/2026-08-16-conexion-3d-hallazgos-motor-reglas.md`) son **siempre declarados a mano por el arquitecto** — nunca verificados contra el planeamiento real. Un arquitecto puede escribir "edificabilidad 1.5" cuando la norma zonal real de esa parcela concreta dice otra cosa, y ArchMuse no tiene forma de saberlo ni de avisar.

## 2. Usuario afectado

El arquitecto que trabaja sobre una parcela real en Madrid (única cobertura de este piloto) y quiere que los límites urbanísticos del Sandbox/evaluador reflejen el PGOUM real, no un valor que tiene que buscar él mismo en el geoportal municipal.

## 3. Objetivo de negocio

Es exactamente el tipo de "profundidad normativa como cuña de entrada" que `MOAT_ANALYSIS.md` (Pilar 7) identifica como estrategia de expansión geográfica: cada norma real integrada con rigor es simultáneamente mejora de producto y entrada a un mercado regional — y, como advierte el mismo documento, "cuesta meses a un competidor" replicarlo bien, precisamente porque (como demuestra la investigación de este PRD) no es una API sencilla de "pedir y listo".

## 4. Objetivo técnico

- Dada una coordenada real dentro del término municipal de Madrid, obtener de forma automática: código de manzana/parcela normativa, código de Norma Zonal y código de "Grado"/condición de edificación reales del PGOUM 97 vigente.
- Para el subconjunto de Normas Zonales cubierto en esta primera fase (ver §11, Tarea 3), traducir esos códigos a `ocupacion_maxima_pct`/`edificabilidad_maxima`/`plantas_maximas`/`retranqueos_m` numéricos reales, con la tabla de traducción versionada en el propio repositorio (auditable, no una caja negra).
- Fuera de Madrid, o dentro de Madrid pero en una Norma Zonal todavía no traducida: degradar con claridad a la carga manual ya existente — nunca mostrar un número sin saber de dónde sale, nunca bloquear el flujo.
- Los datos automáticos, cuando existen, se inyectan como **valores por defecto editables** en el panel de límites urbanísticos del Sandbox (`viewer-sandbox.js`, ya existe desde el PRD anterior) y en `params["normativa"]` de `evaluator.py` — el arquitecto conserva siempre la última palabra y puede corregir si detecta un error.

## 5. Casos de uso

1. Arquitecto selecciona una parcela real en el Paso 0, dentro de una zona de Madrid ya traducida (p. ej. Norma Zonal 1.5) → al abrir el Sandbox, el panel de límites urbanísticos ya trae "Ocupación máx. 60%, Edificabilidad 0.85 m²/m²" (ejemplo) en vez de los valores genéricos por defecto, con una etiqueta "Fuente: PGOUM 97, Norma Zonal 1.5 (automático)".
2. La misma parcela, pero en una Norma Zonal sin traducir todavía → el panel muestra los valores por defecto genéricos de siempre, con una nota "No se ha podido determinar la normativa automáticamente para esta zona — verifica los límites en el geoportal municipal."
3. Arquitecto con una parcela en Boadilla del Monte (fuera de Madrid capital) → mismo aviso claro y limpio: "Consulta automática de normativa disponible solo en el municipio de Madrid (piloto). Introduce los límites manualmente." Nunca un error técnico, nunca un intento silencioso contra un servicio que no cubre esa zona.
4. El servicio de Madrid está caído (`"Service not started"`, ya observado en vivo durante esta investigación) → mismo aviso que el caso 2/3, nunca un error visible ni un bloqueo — el arquitecto sigue pudiendo trabajar con datos manuales.
5. Arquitecto detecta que el valor automático no coincide con lo que sabe del terreno → lo edita en el mismo panel que ya existe; el cambio no se sobrescribe hasta que se vuelva a abrir el Sandbox con otra parcela.

## 6. Casos límite

- **Punto exactamente en el límite entre dos Normas Zonales** (borde de polígono): la consulta ArcGIS puede devolver 0, 1 o 2 resultados según tolerancia de intersección — se toma el primero, con un aviso "resultado en el límite de zona, verifica manualmente" si hay más de un resultado.
- **Código de Grado/Norma Zonal presente pero no traducido en la tabla local** (cobertura parcial deliberada, §0): tratado exactamente igual que "sin dato" — nunca un error distinto, para no delatar al arquitecto que "casi funciona" cuando en realidad no hay traducción.
- **Servicio de Madrid responde pero con campos vacíos/nulos** (parcela en gestión, suelo no urbanizable, dotación pública sin norma zonal residencial): se trata como "no aplica automáticamente", mismo camino de degradación que el resto.
- **Timeout del servicio municipal**: no debe bloquear la apertura del Sandbox — mismo criterio "best-effort, nunca bloqueante" que ya usa todo el resto de la integración con Catastro/Overpass en este proyecto (`ErrorDeSitio`, avisos en vez de excepciones que rompen el flujo).
- **El arquitecto ya había escrito valores manuales en el panel de límites y luego llega el dato automático** (orden de llegada, ya que la consulta a Madrid puede tardar más que abrir el Sandbox): el valor automático NUNCA pisa un valor que el arquitecto ya haya tocado a mano en esta sesión — solo rellena el valor por defecto si el campo sigue intacto.

## 7. Flujo del usuario

1. En el Paso 0 (o al abrir el Sandbox con coordenadas ya conocidas), se lanza en paralelo (no bloqueante) una consulta a `analyzer.normativa_madrid` con la coordenada real.
2. Si la coordenada cae fuera del bounding box aproximado de Madrid capital, se resuelve al instante con "fuera de piloto", sin llamar a ningún servicio externo.
3. Si cae dentro, se consulta la capa de condiciones de edificación real por punto (`query` ArcGIS REST, `inSR=4326`), con un timeout corto y best-effort.
4. Si el código de zona/grado resultante está en la tabla local de traducción (§11, Tarea 3): se devuelven los 4 valores normativos + una etiqueta de fuente.
5. Si no (zona no traducida, servicio caído, fuera de Madrid, timeout): se devuelve `disponible: false` con un motivo legible, nunca un error.
6. El panel de límites urbanísticos del Sandbox, al recibir la respuesta, rellena los campos que el arquitecto no haya tocado todavía y muestra la etiqueta de fuente/aviso correspondiente.

## 8. Criterios de aceptación

1. Para al menos 3 coordenadas reales dentro de Madrid, verificadas a mano contra el geoportal municipal (captura de pantalla del visor urbanístico oficial comparada con la respuesta de ArchMuse), los 4 valores devueltos coinciden con lo que muestra el geoportal oficial para esa parcela — no una coincidencia aproximada, coincidencia real verificada.
2. Para al menos 1 coordenada real en Madrid pero en una Norma Zonal fuera de la tabla de traducción de esta fase, el sistema degrada con el aviso correcto, nunca con un número inventado.
3. Para al menos 1 coordenada real fuera de Madrid (p. ej. Boadilla, ya usada en pruebas anteriores de esta sesión), se muestra el aviso de "fuera de piloto" sin ninguna llamada al servicio municipal.
4. Simulando el servicio de Madrid caído (mismo error `"Service not started"` observado en vivo durante la investigación de este PRD), el Sandbox sigue abriendo con normalidad, con los valores manuales por defecto de siempre.
5. Un valor ya editado a mano por el arquitecto en el panel no se sobrescribe si la respuesta automática llega después.
6. Cero regresión sobre el HUD urbanístico y el resto del Sandbox ya verificado en el PRD anterior.

## 9. Riesgos

- **El riesgo más grave de todo este PRD: presentar un dato automático incorrecto como si fuera fiable.** Verificado en la propia investigación: `COND_EDIF`/`COEF_Z` son códigos, no números — traducirlos mal (una tabla hecha deprisa, sin verificar contra el texto real de la normativa) sería peor que no tener el dato, porque un arquitecto que confía en un número automático erróneo puede diseñar mal desde el principio. Mitigación: la tabla de traducción de la Tarea 3 se construye y se verifica a mano, punto por punto, contra el documento oficial (`madridlicencias.com`/`wpgeoportal.madrid.es` — Normas Urbanísticas del PGOUM 97, ya localizadas en esta investigación), nunca por inferencia ni por patrón.
- **Disponibilidad del servicio municipal, ya observada como real** (`"Service not started"` en vivo durante la investigación de este PRD, en un servicio DISTINTO al que finalmente se usaría, pero de la misma infraestructura) — sin SLA conocido, a diferencia de Catastro. Mitigación: siempre best-effort, nunca bloqueante, ya integrado en el diseño de este PRD desde el principio (§6).
- **Cobertura fragmentada por Norma Zonal**: el alcance real de "cuántas Normas Zonales cubre la primera versión" puede ser mucho menor de lo que suena "piloto Madrid" — se recomienda comunicarlo internamente como "cobertura inicial de N normas zonales verificadas", nunca como "Madrid cubierto".
- **Coste de mantenimiento de la tabla de traducción**: el PGOUM se modifica por normas complementarias (la búsqueda ya encontró una actualización de noviembre de 2023) — la tabla local puede quedar desactualizada sin que nadie lo note. Mitigación razonable pero fuera de alcance de este PRD: fecha de "última verificación" visible junto a cada entrada de la tabla.
- **Compite por tiempo de desarrollo con el resto del roadmap** (`ROADMAP_VISION_ARQUITECTONICA.md` §5) — es, de los pilares de esa hoja de ruta, el que más se ha revelado como trabajo de datos verificado a mano, no de ingeniería pura; debe presupuestarse como tal.

## 10. Impacto sobre módulos existentes

- **Nuevo** `analyzer/normativa_madrid.py`: cliente del servicio ArcGIS REST de Madrid (consulta por punto, manejo de errores/timeout best-effort) + la tabla local de traducción código→valores (Tarea 3) + función pública `normativa_urbanistica_por_coordenadas(lat, lon) -> dict | None`.
- `app.py`: nuevo endpoint (p. ej. `GET /api/normativa-urbanistica-punto?lat=...&lon=...`), mismo patrón que `/api/entorno-3d-punto`.
- `static/viewer-sandbox.js`: el panel de límites urbanísticos (ya existe) pasa a rellenarse con valores por defecto automáticos cuando estén disponibles, respetando ediciones manuales ya hechas (§6).
- `analyzer/evaluator.py`: **ningún cambio de lógica** — las 4 funciones ya reciben `normativa: dict` como parámetro; este PRD solo cambia de dónde viene ese dict antes de llegar ahí.
- Ningún cambio en Catastro/Overpass/`sitio.py` existentes — es una fuente de datos nueva y paralela, no una sustitución.

## 11. Plan de implementación dividido en pequeñas tareas

1. **Spike de verificación técnica** (antes de escribir producto): confirmar en vivo, con `curl`/consulta real, que `query?geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*&f=json` contra `PGOUM97/PG_CONDICIONES_EDIFICACION/MapServer/6` devuelve un resultado real para una coordenada de prueba conocida (reutilizar una de las parcelas reales ya usadas en esta sesión, p. ej. La Moraleja si cae dentro del término de Madrid, o el centro de Madrid ya usado para Gran Vía). Sin este spike verificado, no se empieza ninguna tarea siguiente.
2. `analyzer/normativa_madrid.py`: cliente HTTP best-effort para la consulta por punto (geometría + código de zona/grado crudo), sin traducción todavía — devuelve los códigos tal cual.
3. **Tabla de traducción código→valores**, verificada a mano contra el documento oficial de Normas Urbanísticas del PGOUM 97, empezando por 2-3 Normas Zonales (las que cubran las zonas de prueba ya usadas en esta sesión) — no todo Madrid de golpe.
4. `app.py`: endpoint nuevo, reutilizando el cliente de la Tarea 2/3.
5. `viewer-sandbox.js`: consumo del endpoint, relleno no destructivo del panel de límites, etiqueta de fuente/aviso.
6. Aviso limpio "fuera de piloto" cuando la coordenada cae fuera del bounding box aproximado de Madrid.
7. Verificación en vivo: los 6 criterios de §8, incluida la comparación manual contra el geoportal oficial de al menos 3 parcelas reales.

## 12. Plan de pruebas

- **Verificación manual contra la fuente oficial** (no solo contra el propio código): para cada parcela de prueba, captura del Visor Urbanístico del Geoportal de Madrid (`madrid.es/go/VisorUrbanistico`) comparada a mano con la respuesta de ArchMuse — es el único criterio de aceptación real para datos normativos, mismo principio que ya aplica este proyecto a los umbrales CTE calibrados contra `ejemplo.dxf`.
- `python -m py_compile` sobre los módulos nuevos.
- Simulación de servicio caído: apuntar temporalmente a una URL que devuelva 503/timeout y confirmar que el Sandbox sigue abriendo con normalidad.

## 13. Métricas para medir el éxito

Cualitativo en esta fase (cobertura inicial pequeña): Pablo confirma que, para las Normas Zonales ya traducidas, el dato automático es correcto al 100% frente al geoportal oficial — un solo error verificado sería motivo de retirar el piloto hasta corregirlo, no de "seguir con una tasa de acierto aceptable" (mismo estándar que `DESTROY_ARCHMUSE.md` §5 ya señala: un hallazgo normativo incorrecto no se perdona una segunda vez).

## 14. Posibles motivos para NO implementar la idea

- **El hallazgo central de este PRD es que "consulta automática de normativa urbanística" suena a una tarde de integración de API y en realidad es, en su mayor parte, un trabajo de traducción de dominio verificado a mano** (códigos de zona → valores reales), del mismo orden de magnitud que ya advertía `MOAT_ANALYSIS.md` §5 para el CTE — "necesitaría seis meses para copiar" también aplica, en sentido inverso, a lo caro que es construirlo bien la primera vez. Si el objetivo era una victoria rápida, esta no lo es; el checklist de inspección en campo (ya implementado) sí lo era, y es un contraste útil para calibrar expectativas.
- **Cobertura inevitablemente parcial durante mucho tiempo**: empezar por 2-3 Normas Zonales dentro de Madrid, cuando el PGOUM tiene más de una decena, puede sentirse como "casi nada" frente a la ambición del nombre del PRD ("piloto Madrid"). Es una decisión consciente (§0/§9), no un recorte de última hora, pero merece gestionarse como tal en la comunicación interna.
- **Alternativa más barata**: en vez de automatizar la consulta, ofrecer un enlace directo al Visor Urbanístico oficial de Madrid desde el panel de límites (un solo clic, sin ningún riesgo de dato incorrecto) y dejar que el arquitecto copie los valores a mano. Aporta menos "magia" pero cero riesgo de un número mal traducido — vale la pena presentarlo como alternativa seria antes de comprometerse a la tabla de traducción de la Tarea 3.
- **Dependencia de un servicio municipal sin SLA conocido y ya observado inestable** (`"Service not started"`, verificado en vivo hoy) introduce un punto de fallo externo que ni Catastro ni Overpass, pese a sus propios problemas ya conocidos en este proyecto, presentan con esa gravedad (un servicio administrativamente parado, no solo lento).

---

## 15. Cierre — qué se implementó de verdad, y qué NO (2026-08-16)

**Antes de tocar código de producto** (repitiendo y ampliando la Tarea 1, el spike técnico, tal y como el propio PRD exige) se hizo una segunda ronda de verificación en vivo, más profunda que la del borrador original, porque el spike original no bastaba para saber si la Tarea 3 (tabla de traducción) era siquiera posible con el rigor que pide §9. Resultado, con evidencia real:

1. **`PGOUM97/PG_CONDICIONES_EDIFICACION/MapServer/6` SÍ funciona** para un punto real (Gran Vía 31, Madrid) — verificado repetidas veces en vivo, con y sin Flask de por medio, geometría reproyectada a EPSG:4326 (`outSR=4326`), campos reales `CODMANZANA=0106013`, `NUMORD=02204`, `COND_EDIF=5` ("Grado 5"), `COEF_Z="-"`.
2. **Esa capa está acotada, por su propia leyenda, a la Norma Zonal 1.5** — no es "cualquier zona de Madrid". Confirmado leyendo `drawingInfo.renderer` del propio servicio.
3. **`pgoum97/PG_ORDENACION`** (el único servicio que resolvería "en qué Norma Zonal está un punto CUALQUIERA" — el prerrequisito real para que esta integración funcione para una parcela arbitraria, no solo para las que ya sabemos que caen en 1.5) **sigue caído** (`"Service not started"`), reconfirmado en vivo el mismo día de esta implementación, no solo en la investigación original del PRD.
4. **`pgoum97/PG_ORDENACION_SIN_AMBITO`** (el nombre sonaba a "sin ámbito" = genérico) **solo contiene, de verdad, la Norma Zonal 1.5** — confirmado listando TODAS sus capas, no es un catálogo de varias normas.
5. **La propia Norma Zonal 1 no se regula con ocupación/edificabilidad/retranqueos.** Investigación documental (ver fuentes) confirma que su modelo real es "fondo edificable + coeficiente ponderado de densidad"; la altura (plantas) se determina caso a caso por las cornisas de los edificios colindantes y aprobación de la CIPHAN, no por el grado; los retranqueos no aplican (tipología de manzana cerrada, a línea de fachada). Ninguno de los 4 campos que `evaluator.py` necesita tiene una traducción numérica honesta posible desde `COND_EDIF`/`COEF_Z` para esta norma.
6. Búsqueda adicional confirma que **la norma que sí encaja con el modelo clásico ocupación/edificabilidad es la Norma Zonal 8 ("vivienda unifamiliar")** — pero no existe hoy ninguna capa ArcGIS pública que indique, para un punto cualquiera, si está en Norma Zonal 8 (el servicio del punto 3, que resolvería eso, está caído).

**Decisión de alcance, tomada aquí, comunicada explícitamente — no un recorte silencioso**: se implementó la Tarea 2 del plan (§11) — cliente real, códigos reales, nunca inventados — y **deliberadamente NO se implementó la Tarea 3** (tabla de traducción código→número) ni el auto-relleno de los 4 campos numéricos del HUD que pedía el encargo. Rellenar `ocupacion_maxima_pct`/`edificabilidad_maxima`/`plantas_maximas`/`retranqueos_m` a partir de `COND_EDIF` habría sido inventar exactamente el dato que el propio PRD señala en §9 como el riesgo más grave de todo el documento — y, más allá de "no verificado todavía", los hallazgos 5-6 de arriba indican que **para la única Norma Zonal con datos reales disponibles, esos 4 campos ni siquiera son el modelo normativo correcto**.

**Lo que SÍ se entrega y funciona, verificado en vivo**:
- `analyzer/normativa_madrid.py`: `normativa_urbanistica_por_coordenadas(lat, lon)`, nunca lanza, 3 caminos honestos verificados con coordenadas reales — (a) Gran Vía 31: `disponible=true`, referencia real (grado, norma zonal, coeficiente, código de manzana); (b) Boadilla del Monte (dentro del bbox rectangular aproximado, pero fuera de la cobertura real de Madrid capital): `disponible=false`, motivo honesto, SÍ hizo la llamada real (que correctamente no encontró nada); (c) Barcelona (claramente fuera del bbox): `disponible=false`, `dentro_de_piloto=false`, **cero llamadas de red** (criterio §8.3 del plan original).
- `GET /api/normativa-urbanistica-punto?lat=...&lon=...` (`app.py`), mismo patrón que `/api/entorno-3d-punto`, verificado con `curl` contra el servidor real corriendo (incluye una respuesta de éxito real completa capturada en vivo).
- `viewer-sandbox.js`: la consulta se lanza en paralelo al abrir el Sandbox (nunca bloquea la barra de progreso ya existente), y el HUD de Urbanismo muestra una **nota de contexto real** (no un campo editable) cuando hay dato: "PGOUM 97 (Madrid), Norma Zonal 1.5, Grado 5 — sin traducción numérica verificada todavía; consulta el geoportal municipal para los valores exactos." Verificado en vivo en Chrome (la variante "no disponible" se vio renderizada en pantalla con su propio estilo, distinto del aviso genérico "sin datos reales de parcela").
- Fuera del bounding box aproximado de Madrid (fuente: `boundingbox` real de Nominatim para "Madrid, España" — misma infraestructura que ya usa `sitio.geocodificar_direccion`, no un valor de memoria): no se muestra ninguna nota (silencio deliberado, para no generar ruido permanente en cada proyecto fuera de Madrid sin ninguna acción que tomar).
- Latencia real observada del servicio municipal, vía dos clientes HTTP distintos (`curl` y `urllib`/Python): muy irregular, 6-20s+, con timeouts reales ocasionales incluso a 20s — reconfirma en vivo, con datos nuevos, el riesgo que el PRD ya señalaba en §9 sin SLA conocido.

**Consecuencia honesta para Pablo**: este piloto, tal y como puede construirse hoy con la infraestructura real de Madrid, no llega a "límites urbanísticos automáticos en el HUD" — llega a "referencia normativa real verificada, mostrada como contexto, con la traducción a números pendiente de un trabajo de dominio que hoy no tiene ni la fuente de datos (`PG_ORDENACION` caído) ni, para Norma Zonal 1, un modelo compatible con `evaluator.py`". Si se quiere seguir, el camino más prometedor no es "arreglar" la Norma Zonal 1, sino perseguir la Norma Zonal 8 (unifamiliar, si aparece una capa/servicio real que la resuelva por punto) — pendiente de una investigación nueva, no incluida en este PRD.

**Fuentes de la investigación documental** (hallazgo 5-6): resumen de PGOUM 97 Norma Zonal 1 (fondo edificable/coeficiente ponderado/altura por CIPHAN) y de Norma Zonal 8 (vivienda unifamiliar) localizados vía búsqueda web dirigida a documentos técnicos y consultas urbanísticas oficiales del Ayuntamiento de Madrid — no un PDF único citado aquí porque la síntesis cruza varias fuentes; disponible el detalle de cada una bajo petición si Pablo quiere auditar la investigación en profundidad.

**Decisión:** Implementado 2026-08-16 con alcance reducido respecto al encargo original — Tarea 2 (§11) entregada y verificada en vivo; Tarea 3 (tabla de traducción numérica) explícitamente NO entregada, por los hallazgos 5-6 de arriba, que no eran conocidos ni por el PRD original ni por el encargo de ejecución.
