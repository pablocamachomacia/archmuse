# TECH_REVIEW.md — Auditoría técnica crítica de ArchMuse

**Postura de esta revisión:** la de un CTO que tiene que decidir si este código aguanta cientos de estudios de arquitectura pagando por él. No propone funcionalidad nueva. No se ha escrito ni modificado ningún archivo de producto — todo lo que sigue es lectura, análisis estático (`ruff`, `vulture`) y verificación manual línea a línea de los hallazgos más importantes.

**Alcance:** `analyzer/` (15 módulos, ~7.700 líneas Python), `app.py`, `main.py`, `static/index.html` (SPA, 5.313 líneas).

---

## 0. Veredicto en una frase

El motor de reglas es un activo real y difícil de replicar; todo lo que lo rodea — el envoltorio de producto — está construido a la velocidad de un prototipo de un solo desarrollador, y **tiene al menos un bug confirmado que anula silenciosamente la característica que más se ha publicitado en los últimos commits** (umbrales adaptativos por tipología y zona climática). No es vendible a cientos de clientes tal como está hoy — es vendible a un cliente que sepa que es un prototipo.

---

## 1. Puntuaciones (0-10)

| # | Categoría | Nota | Justificación en una línea |
|---|---|---:|---|
| 1 | Calidad de la arquitectura | **6/10** | Buena separación conceptual por responsabilidad (CTE vs. diseño vs. circulación vs. interpretación de negocio), pero dos frontends de producto (CLI vs. SPA) divergentes y sin capa de servicio real. |
| 2 | Calidad del código | **5/10** | Documentación interna excelente y nombres claros, lastrados por funciones/módulos gigantescos y patrones copiados en vez de reutilizados. |
| 3 | Escalabilidad | **3/10** | Servidor de desarrollo Flask monoproceso, llamada a Claude síncrona dentro del request, sin cola/worker, sin caché, recomputación redundante confirmada. |
| 4 | Mantenibilidad | **4/10** | Cambiar una regla implica tocar a mano una función de 327 líneas y 49 de complejidad ciclomática, sin ningún test que avise si algo se rompe. |
| 5 | Seguridad | **3/10** | Sin autenticación, sin límite de peticiones, `debug=True` en el servidor Flask (ejecución remota de código si se expone fuera de `localhost`). Los aciertos puntuales (escapado de SVG, `secure_filename`, límite de tamaño) no compensan la ausencia de una capa de seguridad real. |
| 6 | Rendimiento | **5/10** | Correcto a la escala actual (un DXF, un usuario), pero con recomputación confirmada (`room_problems` se calcula 3 veces por habitación) y un algoritmo O(n²) ya documentado por el propio autor como asumible "mientras no haya miles de issues". |
| 7 | UX del producto | **7/10** | El diseño de producto es el punto más fuerte del envoltorio: panel de severidad, plan de acción ordenado por impacto en puntuación, visor 3D, transparencia explícita sobre limitaciones. No verificado en navegador durante esta revisión (auditoría estática), la nota se basa en lo que el código implementa. |
| 8 | Calidad del uso de la IA | **6/10** | Degradación correcta y bien pensada si falla la API o no hay clave; pero el contexto que recibe Claude (tipología/zona reales) y el que usa el motor de reglas para el mismo request **no son el mismo** (ver Bug #1) — una inconsistencia interna grave aunque cada mitad por separado esté bien hecha. |
| 9 | Facilidad para añadir nuevas normas | **5/10** | Añadir una regla nueva (`evaluate_*` + dataclass) es mecánico y tiene 40 ejemplos que copiar; pero cablearla también exige tocar a mano `classify_problems` (que ya tiene 327 líneas) — no hay registro/tabla que lo automatice. |
| 10 | Riesgo de deuda técnica | **8/10 (alto)** | Cero tests, dependencias sin fijar, dos productos divergentes, un módulo de 2.966 líneas y una función de 49 de complejidad ciclomática que crecen linealmente con cada norma nueva que se añada. |

**Media simple (1-9, sin contar el riesgo invertido en el 10):** 5,0/10 — un motor prometedor con una base de producto que hoy es la de un prototipo avanzado, no la de un SaaS.

---

## 2. Las 20 peores decisiones técnicas

1. **`app.py:79` no pasa `tipologia` ni `zona_cte` a `evaluate_advanced()`, y `app.py:95-101` no pasa `proyecto` a `serialize_analysis()`.** Resultado: en el flujo real de subir un DXF (`/api/analizar`) — el flujo que usará un cliente de pago con un plano de verdad — **todas** las reglas adaptativas por tipología y zona climática (itinerario accesible, ancho de pasillo, superficie mínima, ratio de baños, condensaciones, compacidad, horas de sol, severidad de accesibilidad) se evalúan siempre con los valores por defecto (`plurifamiliar`, zona `C`), sin importar lo que el arquitecto seleccione en el formulario. Es el bug más grave de todo el proyecto — ver detalle en la sección de Bugs.
2. **`classify_problems` (`evaluator.py:1950`) es una función de 327 líneas, complejidad ciclomática 49, 47 ramas y 11 parámetros** que traduce cada resultado en un `IssueReport` mediante ~25 bloques `if r is not None and not r.passed: issues.append(...)` casi idénticos. Cada norma nueva añade otro bloque a mano — no escala como proceso de ingeniería.
3. **`serialize_analysis` (`api_serializer.py:179`) tiene 19 parámetros posicionales/con nombre.** Cualquier cambio de orden o de valor por defecto es un campo minado; ya ha producido al menos un bug real (#1 de esta lista).
4. **Cuatro módulos completos y activos (`chain_effects.py`, `circulation.py`, `scoring.py`, `spatial_quality.py`, ~1.700 líneas) fuera de control de versiones** en el último estado observado del repositorio — el trabajo más diferencial del producto no está respaldado.
5. **Cero tests automatizados en todo el repositorio.** Con un motor de 40 reglas normativas donde cambiar un umbral en un bloque puede alterar el resultado de otro (ya documentado entre los bloques 15 y 19), no hay red de seguridad para tocar nada.
6. **`app.py` corre con `debug=True` (`app.py:310`).** El depurador interactivo de Werkzeug permite ejecución remota de código; aceptable en un portátil de desarrollo, inaceptable en cualquier despliegue real.
7. **Sin autenticación, sin usuarios, sin límite de peticiones.** Cualquiera con la URL puede consumir cuota de la API de Anthropic sin control.
8. **`evaluator._is_adjacent` (Bloque 16, adyacencia acústica) usa intersección literal de polígonos** cuando en los DXF reales las habitaciones dejan un hueco de hasta 0,38 m por el grosor del muro — la comprobación probablemente no se ha disparado nunca sobre un plano real, y ya existe la solución correcta un módulo más allá (`circulation._rooms_are_connected`) sin haberse aplicado de vuelta.
9. **La misma lógica de geometría "de polígono a puntos SVG" está copiada literalmente tres veces** (`circulation.py:464`, `plan_svg.py:555`, `spatial_quality.py:420`) en vez de vivir en una única función compartida.
10. **`requirements.txt` solo fija límites inferiores (`>=`), sin lockfile.** Una instalación nueva dentro de unos meses puede traer una versión del SDK de Anthropic (que cambia con frecuencia) que rompa algo, sin forma de reproducir el entorno que funciona hoy.
11. **`three.js` se carga en tiempo de ejecución desde `unpkg.com`**, no está vendorizado ni empaquetado — sin conexión a internet o si la CDN falla, el visor 3D (una de las piezas más vistosas del producto) deja de funcionar sin aviso.
12. **Dos frontends de producto divergentes y sin sincronizar:** `main.py`/`reporter.py` (CLI) siguen vivos pero no usan `circulation.py`, `spatial_quality.py`, `chain_effects.py` ni `scoring.py` — cada feature nueva se añade a un producto y se olvida en el otro.
13. **`static/index.html` es un único archivo de 5.313 líneas** — HTML, CSS y 372 funciones JavaScript mezclados, sin build, sin módulos, sin ningún test. Sostenible con un desarrollador, no con dos.
14. **La tabla de percentiles comparativos (`scoring.py`) está inventada** (`TIPOLOGIA_BENCHMARKS`, tres puntos de calibración escritos a mano) pero se presenta al usuario como un percentil objetivo frente a "otros proyectos".
15. **`cte_zonas.py` solo cubre ~30 municipios** y cualquier otro recae silenciosamente en la zona por defecto sin que el aviso de "limitaciones" se lo diga al usuario — el arquitecto no tiene forma de saber que el dato climático es una suposición.
16. **`room_problems()` se ejecuta 3 veces por habitación en cada petición** (`api_serializer.py:71`, `api_serializer.py:227`, `plan_svg.py:546`) sin ningún tipo de caché ni memoización, pese a ser una función con 38 de complejidad ciclomática.
17. **`compute_puntos_ganados` es O(n²) en el número de issues**, documentado como "asumible" por el propio autor — una apuesta de rendimiento no verificada contra un proyecto grande de verdad.
18. **`plan_svg.room_problems` tiene complejidad ciclomática 38 y 37 ramas** — el doble del umbral recomendado, en un módulo que ya hace demasiadas cosas (layout, overlays de problemas, leyendas, tres consumidores distintos).
19. **`evaluator.py` es un módulo de 2.966 líneas** que mezcla definiciones de reglas, dataclasses de resultado, agregación de puntuación (`UnitScore`, `AdvancedAnalysis`), reglas de urbanismo a nivel de edificio y la capa de clasificación — cinco responsabilidades distintas en un solo archivo.
20. **Cuatro llamadas a `zip()` sin `strict=`** (`circulation.py`, `evaluator.py`, `plan_svg.py`, `spatial_quality.py`) en código que procesa geometría de un archivo subido por el usuario — si dos listas de coordenadas llegaran con longitud distinta (geometría DXF mal formada), el resultado es un contorno de habitación truncado en silencio, no un error visible.

---

## 3. Los 20 mejores aciertos

1. **Cobertura normativa real y amplia:** ~40 funciones de regla sobre CTE DB-SI/SUA/HS/HE/HR, LOE y decretos autonómicos de habitabilidad — es el foso competitivo del producto, y replicarlo le costaría meses a un competidor.
2. **Transparencia explícita sobre limitaciones** (`get_missing_data_warnings`): el producto admite por escrito qué NO puede verificar (altura libre, escalera, aislamiento entre viviendas, compartimentación contra incendios) en vez de sobreprometer cumplimiento — muy poco habitual en herramientas de "compliance automático".
3. **Degradación correcta de la IA** (`ai_analyst.py`): sin clave, sin SDK, con error de red, con respuesta no-JSON o con rechazo de los filtros de seguridad, el análisis principal nunca se rompe — solo se omite la sección de diagnóstico narrativo.
4. **Separación conceptual limpia entre cumplimiento normativo (`evaluator.py`) y calidad de diseño no normativa (`spatial_quality.py`)**, documentada explícitamente para no mezclar "ilegal" con "de mal gusto" ni diluir la fiabilidad de `IssueReport.codigo` como cita normativa real.
5. **Un único contrato JSON (`serialize_analysis`) alimenta la misma SPA desde los dos flujos de producto** (DXF real y proyecto generado por IA) — evita duplicar la capa de presentación.
6. **Manejo correcto de subida de archivos:** `secure_filename`, límite de 25MB, directorio temporal con limpieza automática por context manager — higiene básica bien resuelta desde el principio.
7. **Contenido SVG derivado de datos no confiables (etiquetas de habitación del DXF) correctamente escapado con `html.escape`** antes de insertarse en el documento — una defensa contra inyección que la mayoría de prototipos pasa por alto.
8. **`_discard_container_candidates` (`parser.py`) resuelve un problema geométrico genuinamente difícil** (distinguir polígonos de habitación reales de polígonos de agrupación que los contienen) con un umbral validado empíricamente y un primer intento ingenuo documentado como descartado por sus fallos reales.
9. **La tolerancia de hueco entre muros (`WALL_GAP_TOLERANCE_M`) está calibrada con datos reales medidos** (0,03–0,38 m sobre `ejemplo.dxf`), no con una constante inventada.
10. **`compute_puntos_ganados` recalcula el desglose completo por cada issue en vez de restar la deducción nominal a mano**, gestionando correctamente el caso borde de que una categoría ya esté saturada — es una decisión de diseño algorítmico cuidada, no un atajo.
11. **`categoria_for` (`scoring.py`) ordena explícitamente de código más específico a más genérico** para no dejar caer "CTE-DB-SUA" en el cajón de sastre "CTE-DB" antes de tiempo — un detalle de correctitud fácil de pasar por alto.
12. **Validación cruzada real entre dos sistemas de puntuación independientes**: la vivienda que peor puntúa en `evaluator.py` (cumplimiento CTE) también puntúa peor en `spatial_quality.py` (calidad de diseño) sobre el mismo plano real — evidencia empírica de que ambos sistemas son coherentes entre sí, no solo "código que compila".
13. **Documentación interna consistentemente centrada en el *por qué*, no en el *qué***, en prácticamente todos los módulos — el código explica sus propias trampas y decisiones de diseño, algo raro en un proyecto que avanza a este ritmo.
14. **`layout_room_polygons()` se diseñó explícitamente como envoltorio público reutilizable** y lo reutilizan sin reimplementarlo `plan_svg`, `spatial_quality` y `circulation` — anticipación correcta de una necesidad compartida.
15. **Patrón de dataclass `RuleResult`/`*Result` uniforme en las ~40 reglas** (`passed`, `message`) — da una base mecánicamente consistente sobre la que sería fácil automatizar `classify_problems` si se decide corregir el punto #2 de la lista anterior.
16. **`chain_effects.py` reutiliza resultados ya calculados en vez de recalcular sus propias comprobaciones** — documentado explícitamente como "no calcula ningún `passed` propio" —, evitando una segunda fuente de verdad para la misma regla.
17. **Umbrales por tipología y zona climática organizados en tablas de datos** (`UMBRALES_TIPOLOGIA`, `UMBRALES_ZONA`) en vez de cadenas de `if/elif` dispersas — el patrón correcto, aplicado de forma inconsistente (no se usó este mismo patrón en `classify_problems`).
18. **Normalización de texto correcta para nombres de ciudad españoles** (`_normalize` con NFKD): "Málaga", "malaga" y "MÁLAGA" resuelven al mismo valor — un detalle de localización que muchos equipos pasan por alto.
19. **`_fix_console_encoding()` en `main.py`** — atención concreta a que los acentos y la "ñ" no se corrompan en consolas Windows con codepage heredado.
20. **El propio código documenta honestamente sus limitaciones no resueltas** (el hueco de adyacencia acústica, la naturaleza inventada del percentil, la falta de geometría real de solar en retranqueos) — facilita enormemente auditorías como esta, porque el autor ya había hecho la mitad del trabajo de identificarlas.

---

## 4. Código duplicado

- **Patrón `if r is not None and not r.passed: issues.append(_issue(...))` repetido ~25 veces** dentro de `classify_problems` — el mayor bloque de duplicación literal del proyecto.
- **Bucle de conversión de polígono a puntos SVG** (`" ".join(f"{sx:.2f},{sy:.2f}" ... zip(xs, ys))`) copiado igual en `circulation.py:464`, `plan_svg.py:555` y `spatial_quality.py:420`.
- **35+ ocurrencias de `PERF401`** (bucle manual `for x in y: lista.append(...)` en vez de comprensión de lista o `list.extend`) concentradas en `evaluator.py` y `plan_svg.py` — indica desarrollo por copia-pega del mismo bloque en vez de una función auxiliar compartida.
- **Dos implementaciones distintas y no equivalentes de "adyacencia entre habitaciones"**: `evaluator._is_adjacent` (intersección de contornos, inerte en datos reales) y `circulation._rooms_are_connected` / `chain_effects` (tolerancia de distancia, validada). Mismo concepto, dos respuestas distintas según qué módulo se consulte.
- **`room_problems()` invocado tres veces de forma independiente** para el mismo par (habitación, vivienda) en la misma petición, en vez de calcularse una vez y reutilizarse.

## 5. Funciones demasiado largas

| Función | Archivo | Tamaño / complejidad |
|---|---|---|
| `classify_problems` | `evaluator.py:1950` | 327 líneas, complejidad ciclomática 49, 47 ramas, 78 sentencias, 11 parámetros |
| `room_problems` | `plan_svg.py:163` | complejidad ciclomática 38, 37 ramas |
| `generate_pdf` | `pdf_report.py:47` | complejidad ciclomática 14, 96 sentencias, 15 ramas |
| `serialize_analysis` | `api_serializer.py:179` | 137 líneas, 19 parámetros |
| `place_rooms` | `ai_generator.py:252` | complejidad ciclomática 11 |
| `render_report_content` | `reporter.py:310` | complejidad ciclomática 14, 6 parámetros, 13 ramas |
| `print_advanced_report` | `reporter.py:51` | complejidad ciclomática 11, 14 ramas, 64 sentencias |

## 6. Módulos que hacen demasiadas cosas

- **`evaluator.py` (2.966 líneas):** define ~40 reglas, sus dataclasses de resultado, el modelo `Unit`/`UnitScore`/`AdvancedAnalysis`, las reglas de urbanismo a nivel de edificio y la capa de clasificación de severidad (`classify_problems`) — cinco responsabilidades que en cualquier otro contexto vivirían en módulos separados.
- **`static/index.html` (5.313 líneas):** maquetación, hoja de estilos, 372 funciones JavaScript, cliente HTTP, renderizado de 6+ paneles distintos y el motor 3D — toda la aplicación cliente en un único archivo sin separación de módulos.
- **`plan_svg.py` (624 líneas):** layout geométrico, generación de SVG del plano base, overlays de problemas por habitación y renderizado de secciones de informe — consumido por tres módulos distintos, cada uno reimplementando fragmentos de su lógica en vez de que `plan_svg` exponga una API más granular.
- **`api_serializer.py`:** además de serializar, orquesta la llamada a `classify_problems`, `compute_puntos_ganados`, `compute_scoring_breakdown` y `estimar_percentil` en el mismo módulo que construye el JSON — mezcla orquestación de negocio con serialización.

## 7. Código muerto (confirmado, no solo sospechado)

- `analyzer/chain_effects.py:331` — `compute_chain_effects()` no se llama desde ningún sitio; solo se usa su hermana `compute_chain_effects_for_unit()`.
- `analyzer/parser.py:217` — `build_rooms()` (envoltorio de conveniencia sobre `load_document` + `build_rooms_from_document`) no se llama desde ningún sitio.
- `analyzer/spatial_quality.py:448` — `render_spatial_quality_legend_html()` no se llama desde ningún sitio; ni el backend ni la SPA lo usan.
- `analyzer/evaluator.py:730` — `MIN_CORRIDOR_WIDTH_M` (comentado como "fallback si tipología no reconocida") no se lee en ningún punto del código.

## 8. Imports innecesarios

- `analyzer/reporter.py:15` — `UnitScore` se importa de `evaluator` y no se usa en todo el archivo.

(El resto de hallazgos de `ruff` sobre imports son de estilo/orden, no de imports realmente no usados — no se listan aquí por no ser relevantes a nivel funcional.)

## 9. Bugs detectados

### Bug #1 — Crítico: tipología y zona climática reales nunca llegan al motor de reglas en `/api/analizar`

`app.py:79` llama a `evaluate_advanced(rooms, unit_labels=unit_labels, norte_grados=norte_grados)` **sin** pasar `tipologia=` ni `zona_cte=`, aunque ambos se calculan dos líneas más abajo (`app.py:81-83`) a partir del formulario. Y `app.py:95-101` llama a `serialize_analysis(...)` **sin** pasar `proyecto=`, con lo que dentro de `serialize_analysis` (`api_serializer.py:230-231`) `tipologia`/`zona_cte` vuelven a caer en sus valores por defecto (`"plurifamiliar"` / `"C"`).

**Consecuencia real, verificada leyendo el código de las reglas afectadas:**
- `evaluate_itinerario_accesible` solo debería aplicar a `tipologia == "plurifamiliar"` (`evaluator.py:1694`) — pero al recibir siempre el valor por defecto, **se aplica también a viviendas unifamiliares o de rehabilitación subidas como DXF**, generando un aviso IMPORTANTE que no debería existir para ese tipo de edificio.
- La severidad de "baño sin espacio de giro accesible" (`bathroom_accessibility_severity`, `evaluator.py:1986-1988`) debería bajar de CRITICO a IMPORTANTE en unifamiliar/rehabilitación — nunca baja, porque `tipologia` en esa segunda llamada a `classify_problems` (dentro de `serialize_analysis`) siempre es el valor por defecto.
- `evaluate_condensaciones` usa `zona_cte` para decidir si la fachada norte es de riesgo (zonas D/E) — con `zona_cte` siempre en `"C"`, una vivienda real en Madrid o Zaragoza (zona D) nunca recibe este aviso aunque debiera.
- Los umbrales adaptativos de ancho de pasillo, superficie mínima de vivienda y ratio de baños por tipología (`UMBRALES_TIPOLOGIA`), y de compacidad/horas de sol por zona (`UMBRALES_ZONA`) — el trabajo descrito en varios de los últimos commits del proyecto ("tipología en el evaluador — umbrales y severidades adaptativas", "zona CTE automática") — **queda inerte en el flujo de análisis de un DXF real**, que es precisamente el flujo que usará un cliente con un plano de verdad.

Nótese que `build_viviendas_payload` (usado para el contexto que recibe Claude) **sí** recibe el `tipologia`/`zona_cte` correctos — así que hoy el diagnóstico narrativo de la IA y el listado estructurado de problemas pueden describir la misma vivienda con criterios normativos distintos dentro de la misma respuesta.

*(El flujo `/api/generar` no tiene este bug: `app.py:260-289` sí pasa `proyecto=params["proyecto"]` completo a `serialize_analysis`.)*

### Bug #2 — Regla de adyacencia acústica probablemente inerte en producción
Ya documentado por el propio proyecto: `evaluator._is_adjacent` exige intersección literal de contornos, que no ocurre nunca en DXF reales por el grosor de muro (hueco de hasta 0,38 m). El Bloque 16 (dormitorio junto a baño/aseo sin aislamiento verificado) probablemente lleva desde su creación sin dispararse jamás sobre un plano real, mientras `circulation.py` ya demostró la solución correcta (tolerancia de distancia) sin aplicarla de vuelta.

### Bug #3 — Riesgo silencioso en `zip()` sin `strict=`
Cuatro sitios (`circulation.py:464`, `evaluator.py:400`, `plan_svg.py:555`, `spatial_quality.py:420`) combinan dos listas de coordenadas con `zip()` sin verificar que tengan la misma longitud. Sobre geometría derivada de un DXF real (no siempre bien formado), una discrepancia de longitud trunca el contorno en silencio en vez de fallar de forma visible — un plano mal representado sin ningún error en consola ni en la respuesta.

### Bug #4 (menor) — Timestamps sin zona horaria
`pdf_report.py:88` (`datetime.today()`) y `reporter.py:325` (`datetime.now()`) generan marcas de tiempo *naive* sin zona horaria. Irrelevante para un solo usuario en Madrid; se convierte en una fuente real de fechas incorrectas en cuanto haya usuarios o servidores en otra zona horaria.

## 10. Reglas normativas que pueden no ejecutarse nunca (o ejecutarse con el criterio equivocado)

1. **Bloque 16, adyacencia acústica** (`evaluator._is_adjacent`) — probablemente nunca se dispara sobre datos reales (Bug #2).
2. **Todas las reglas adaptativas por tipología/zona en el flujo `/api/analizar`** — no es que no se ejecuten, es que se ejecutan siempre con el mismo criterio por defecto sin importar la vivienda real analizada (Bug #1). Es, en la práctica, tan grave como que no se ejecuten: el resultado no refleja la normativa real aplicable.
3. **`evaluate_acoustic_exposure` en densidad urbana "alta"** — solo se activa si `densidad_urbana` llega correctamente desde `cte_zonas.get_densidad_urbana`; en el flujo `/api/analizar` esta función ni siquiera se invoca (no hay parámetro de ciudad que llegue a `evaluate_advanced`), así que la variante "alta densidad" de este aviso tampoco puede activarse nunca en ese flujo — mismo origen que el Bug #1.

## 11. Cuellos de botella

- **Llamada a la API de Anthropic síncrona, dentro del ciclo de request-response de Flask**, sin cola ni worker en segundo plano — con el servidor de desarrollo monoproceso de Flask, una petición larga (generación de proyecto con IA) bloquea al resto de usuarios concurrentes.
- **`room_problems()` recalculado 3 veces por habitación por petición**, sin caché — escala linealmente mal según crece el número de habitaciones del proyecto.
- **`compute_puntos_ganados` es O(n²)** en el número de issues del proyecto — aceptable con decenas de issues (caso actual), pero un edificio grande con muchas viviendas y muchos incumplimientos puede multiplicar el coste de forma notable.
- **Servidor de desarrollo de Flask (`app.run(debug=True)`), monoproceso, sin WSGI de producción** — el techo de concurrencia real hoy es "un usuario a la vez" en la práctica.
- **Sin ninguna capa de caché** para análisis repetidos del mismo DXF o para llamadas a Claude con el mismo contexto — cada petición vuelve a pagar el coste completo (parseo DXF + ~40 reglas + llamada a IA) aunque el input no haya cambiado.

---

## 12. Roadmap — construir la base antes de vender

*(Sin funcionalidad nueva. El objetivo de las tres fases es que lo que ya existe sea correcto, seguro y sostenible.)*

### FASE 1 — Producto sólido
*Objetivo: que el producto diga la verdad y no se pueda perder trabajo por accidente.*

- Confirmar en git los 4 módulos sin versionar y el resto de cambios pendientes — es la acción de mayor impacto por minuto invertido de todo este documento.
- Corregir el Bug #1: pasar `tipologia`/`zona_cte` a `evaluate_advanced()` y `proyecto` a `serialize_analysis()` en `/api/analizar`. Sin esto, cualquier venta a un estudio real está entregando resultados normativos incorrectos.
- `debug=False` + servidor WSGI de producción (gunicorn/waitress) antes de que esto salga del portátil de Pablo.
- Fijar versiones exactas de dependencias (lockfile) y vendorizar/empaquetar `three.js` en vez de depender de una CDN en tiempo real.
- Etiquetar visiblemente en la interfaz que el percentil comparativo (`scoring.py`) es una estimación orientativa, no un dato de mercado.
- Añadir el aviso de "zona climática por defecto usada" a `get_missing_data_warnings` cuando la ciudad no esté en `cte_zonas.ZONAS_CTE`.
- Añadir `strict=True` (o su equivalente manual) a los 4 usos de `zip()` sobre geometría de usuario.
- Corregir la adyacencia acústica inerte (Bug #2) portando la tolerancia de distancia de `circulation.py` a `evaluator._is_adjacent`.
- Eliminar el código muerto confirmado (`compute_chain_effects`, `parser.build_rooms`, `render_spatial_quality_legend_html`, `MIN_CORRIDOR_WIDTH_M`) y el import no usado en `reporter.py`.

### FASE 2 — Producto excelente
*Objetivo: que se pueda cambiar el código sin miedo, y que aguante más de un usuario a la vez.*

- Suite de tests de regresión sobre el motor de reglas, empezando por `ejemplo.dxf` y por los bloques ya identificados como frágiles (16, 19, condensaciones, umbrales por tipología/zona) — es la precondición real para poder tocar `evaluator.py` con confianza.
- Refactorizar `classify_problems` de 25 bloques repetidos a una tabla de datos declarativa (campo del resultado → severidad, bloque, código, título, impacto, solución) — reduce 327 líneas a una estructura de datos que además hace trivial el punto 9 de las puntuaciones ("facilidad para añadir normas").
- Dividir `evaluator.py` en submódulos por responsabilidad (reglas, modelos de datos, urbanismo de edificio, clasificación) — sin cambiar comportamiento, solo estructura.
- Eliminar la triple recomputación de `room_problems()` — calcularlo una vez por (habitación, vivienda) y reutilizar el resultado.
- Mover la llamada a Claude fuera del ciclo síncrono de request/response (cola/worker o, como mínimo, timeout explícito y manejo de saturación).
- Decidir explícitamente el futuro de `main.py`/`reporter.py`: o se retira la CLI, o se sincroniza con `circulation.py`/`spatial_quality.py`/`chain_effects.py`/`scoring.py` — mantener dos productos divergentes sin decidirlo es deuda que crece sola.
- Añadir autenticación mínima y persistencia de análisis (aunque sea ligera) — condición necesaria para que esto deje de ser una demo y empiece a ser un SaaS con clientes reales, cada uno con su propio espacio.
- Modularizar `static/index.html` con un build step mínimo — no urgente con un solo desarrollador, pero bloqueante en cuanto entre un segundo.

### FASE 3 — Producto líder del mercado
*Objetivo: que la robustez de la base se convierta en ventaja competitiva defendible frente a quien intente copiar la idea.*

- Sustituir la tabla de percentiles inventada por percentiles agregados reales, calculados sobre proyectos analizados de verdad en la plataforma — convierte un placeholder en un dato propietario defendible.
- Ampliar `cte_zonas.py` a cobertura nacional completa (todos los municipios, no solo ~30 capitales) con una fuente de datos verificable, en vez de una tabla escrita a mano.
- Instrumentar el motor de reglas con métricas reales de uso (qué reglas se disparan más, en qué tipologías, con qué severidad) — permite priorizar qué normativa nueva añadir con datos, no con intuición.
- Endurecer la validación geométrica de proyectos generados por IA antes de evaluarlos (sanity-check de que la distribución generada es físicamente coherente), para que una demo en vivo nunca falle de forma vistosa.
- Formalizar `chain_effects.py` (coste estimado + urgencia) como un sistema de reglas de negocio versionado y auditable — es la pieza con más potencial comercial del producto y hoy es la menos probada de todas.
