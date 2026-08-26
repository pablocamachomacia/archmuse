# ROADMAP_VISION_ARQUITECTONICA.md — De checker de planos a copiloto con presencia física real

**Postura de este documento:** el mismo ejercicio que `NORTH_STAR_2031.md` ya hizo para "cumplimiento normativo en tiempo real dentro del BIM" pero aplicado al encargo concreto de Pablo del 2026-08-16 (entornos hiperrealistas, asesor legal/urbanístico, sostenibilidad, navegación profesional). No sustituye a `NORTH_STAR_2031.md` — es un zoom sobre cuatro de sus piezas, con la misma disciplina de "trabajar hacia atrás desde una visión honesta" y el mismo horizonte de fases (1/3/6/12/24 meses), para no crear un segundo calendario que compita con el primero.

**Regla seguida al escribir esto:** cada afirmación sobre "qué existe hoy" se ha verificado leyendo código real de este repositorio el 2026-08-16 (no se ha asumido nada de `PROJECT_AUDIT.md`/`TECH_REVIEW.md`/`MOAT_ANALYSIS.md`/`DESTROY_ARCHMUSE.md` sin comprobarlo, porque esos documentos tienen fecha de julio/principios de agosto y el repositorio ha tenido **54 commits desde entonces** — ver §1).

---

## 0. Resumen para decidir rápido

| Pilar del encargo | Ya existe hoy (verificado) | Lo que falta es... | Coste real |
|---|---|---|---|
| 1. Entornos/materiales hiperrealistas | PBR (hormigón, vidrio con transmisión física), sombras solares por fecha/hora real, terreno con relieve + zócalo de maqueta (implementado hoy mismo), ortofoto real + contorno de parcela + colindantes reales | DEM de elevación real, más materiales (acero, madera), iluminación global, modelos de contexto de alta fidelidad | Medio-alto, y **`DESTROY_ARCHMUSE.md` y `MOAT_ANALYSIS.md` avisan explícitamente de no invertir aquí antes de conectar el 3D a los hallazgos** (ver §3.1) |
| 2. Asesor legal/urbanístico en tiempo real | Reglas de urbanismo de edificio ya evaluadas (ocupación, edificabilidad, altura máxima, retranqueos-proxy) — pero sobre **datos que declara el arquitecto en un formulario**, no sobre planeamiento real consultado automáticamente | Consulta automática al PGOU/planeamiento real por parcela, motor de sugerencia volumétrica por sol/viento/contexto | Alto — es, literalmente, el mismo tipo de trabajo de años que ya describe `MOAT_ANALYSIS.md` §5 para el CTE, aplicado a un dominio de datos mucho más fragmentado (urbanismo municipal español) |
| 3. Sostenibilidad y cultura arquitectónica | Compacidad del edificio y ratio de orientación sur/sureste/suroeste ya se evalúan (`evaluate_building_compactness`, `evaluate_building_orientation_ratio`) | Simulación energética real (autosuficiencia, eficiencia bioclimática con física real), checklist de inspección in situ | Simulación: alto (motor externo). Checklist: **bajo** — la pieza de mayor valor/menor coste de las cuatro |
| 4. Navegación y UX profesional | Presets de direcciones y barra de progreso con % — **implementados hoy mismo, en producción**. Ya existe un módulo `visor-mapa.js` (Mapbox GL JS + Threebox) sin verificar en navegador real por falta de `MAPBOX_TOKEN` | Fluidez tipo Mapbox 3D/Google Earth Studio | Bajo si se reutiliza `visor-mapa.js` con un token real; alto si se intenta igualar esa fluidez reconstruyendo primitivas en three.js a mano dentro del Sandbox |

**La recomendación en una frase:** los cuatro pilares son válidos y conectan con la visión ya escrita, pero el orden importa — conectar el 3D a los hallazgos y el checklist de campo son baratos y de alto valor; el asesor urbanístico real y la simulación energética son apuestas de meses/años de datos, no de sprints; y la hiperrealismo visual debe venir *después*, no antes, de que el visor deje de ser "una demo bonita" (cita literal de `DESTROY_ARCHMUSE.md`).

---

## 1. Estado real del repositorio hoy (2026-08-16) — más reciente que los documentos de auditoría

`PROJECT_AUDIT.md` (2026-07-31), `TECH_REVIEW.md` y `REFACTOR_MASTERPLAN.md` tienen razón en todo lo que dicen a fecha de escritura, pero el repositorio ha tenido **54 commits desde el 31 de julio** (111 en total). Verificado hoy, línea por línea, no asumido:

- **El Bug crítico #1 de `TECH_REVIEW.md` (tipología/zona CTE no llegaban al motor en `/api/analizar`) ya está corregido.** `app.py` pasa hoy `tipologia=`, `zona_cte=` y `densidad_urbana=` reales a `evaluate_advanced()` en el flujo de subir un DXF. **`CLAUDE.md` todavía cita este bug como "sin corregir todavía a fecha de este documento" — ese archivo necesita una actualización, es deuda de documentación, no de código.**
- Los 4 módulos que `PROJECT_AUDIT.md` marcaba como "nunca confirmados en git" (`chain_effects.py`, `circulation.py`, `scoring.py`, `spatial_quality.py`) están versionados.
- Existe ya un directorio `tests/` con al menos un golden-master (`tests/fixtures/golden/G6_api_analizar.json`, `G8_determinismo.json`) — la Tarea 18 de `REFACTOR_MASTERPLAN.md` ("cero tests") está en marcha, no en cero.
- Ha aparecido un sistema de entrevista guiada (`analyzer/interview/*`) y una capa de persistencia (`analyzer/storage.py`) que ninguno de los cinco documentos estratégicos raíz menciona — cambia sustancialmente el análisis de `PROJECT_AUDIT.md` §4 y `TECH_REVIEW.md` §12-Fase 2 ("añadir persistencia" ya no es un hueco, es trabajo en curso que merece su propia revisión).
- Hay ya un embrión real de "asesor urbanístico" (ver §3.2): `evaluate_solar_occupation`, `evaluate_buildability`, `evaluate_max_floors`, `evaluate_retranqueos` — pero sobre datos que declara el arquitecto, no sobre planeamiento real consultado automáticamente.
- Existe ya un visor georreferenciado con Mapbox GL JS + Threebox (`static/visor-mapa.js`) — **nunca probado en un navegador real** (falta `MAPBOX_TOKEN` en este entorno) y **sin ningún botón que lo abra todavía** — es infraestructura construida y verificada solo contra la documentación oficial de Mapbox/Threebox, no contra un navegador.
- Hay trabajo experimental sin versionar y sin mencionar en ningún documento estratégico: `JarvisApp.py`, `analyzer/gltf_exporter.py`, `analyzer/pliego_conector.py`, `analyzer/pliego_extractor.py`, `analyzer/estilos.py`, un entorno `.venv-jarvis/` propio. No se ha auditado su alcance para este documento — **antes de comprometerse a cualquier fase de este roadmap, recomiendo una sesión aparte para decidir qué es esto y si compite por el mismo tiempo de desarrollo.**

**Recomendación de higiene, no negociable antes de comprometer meses de roadmap nuevo:** actualizar `CLAUDE.md` (el bug ya no aplica), y programar un refresco de `PROJECT_AUDIT.md`/`TECH_REVIEW.md` — 54 commits de deriva es demasiado para seguir planificando sobre una foto de hace tres semanas.

---

## 2. Encaje con la visión ya escrita

`NORTH_STAR_2031.md` ya apunta a "un halo sutil de color en cada estancia indica su estado normativo en tiempo real" y a un asesor que decide "qué normativa aplica según ubicación, tipología, uso y fecha del proyecto" — el Pilar 2 del encargo de Pablo (asesor legal/urbanístico) **no es una idea nueva, es la misma visión ya escrita, con el foco puesto en urbanismo municipal además de CTE.** No hace falta reescribir la visión; hace falta ejecutar hacia ella con el mismo rigor de datos que ya exige `NORTH_STAR_2031.md` (auditoría externa, motor de reglas multi-país, nunca inventar un dato).

`MOAT_ANALYSIS.md` §6 y `DESTROY_ARCHMUSE.md` §2 coinciden, de forma casi textual, en un único punto que afecta directamente al Pilar 1 (hiperrealismo) y al Pilar 4 (navegación): **el visor 3D, hoy, "no está conectado al motor de hallazgos: no resalta los problemas detectados sobre el propio edificio en 3D, solo los muestra en el plano SVG. Es una demostración de capacidad técnica, no una herramienta de validación"** (`MOAT_ANALYSIS.md`, cita literal). `DESTROY_ARCHMUSE.md` va más lejos: un competidor con 50M€ **"no la construiría hasta tener el core del producto ganado; cuando la construya, la construiré ya conectada a los hallazgos, algo que ArchMuse todavía no ha hecho."**

Esto no es una razón para no perseguir hiperrealismo — es una razón para no perseguirlo **primero**. Cada hora invertida en materiales más realistas o en terreno más fiel sin haber conectado antes el 3D a los hallazgos normativos profundiza exactamente la debilidad que el propio análisis de foso del proyecto ya identificó como la más citada por dos documentos distintos, escritos desde ángulos opuestos (estrategia de negocio y ataque de competidor).

---

## 3. Análisis honesto de los cuatro pilares

### 3.1 Entornos y materiales hiperrealistas

**Lo que ya existe (verificado hoy):** `viewer-materials.js` ya construye hormigón y vidrio PBR con transmisión física real; `configureSunShadow`/`createSunLight` posicionan el sol por fecha/hora real (`solar-posicion.js`); `viewer-sandbox.js`/`viewer-edificio.js` ya renderizan terreno con relieve orgánico, ortofoto real de alta resolución, contorno de parcela real (Catastro) y edificios colindantes reales (Overpass) extruidos — y, desde esta misma sesión, un zócalo de maqueta física bajo el terreno.

**Lo que de verdad falta para el escenario que describe Pablo** ("junto a un edificio de Norman Foster"): elevación real del terreno (DEM/MDT — deliberadamente diferido a `viewer-edificio.js` §14 de un PRD anterior, nunca implementado), más materiales (acero, madera, piedra), iluminación global/reflejos ambientales más allá del entorno PBR plano actual, y modelos de contexto urbano con más fidelidad que una extrusión gris semitransparente.

**Coste real:** esto es ingeniería gráfica especializada y continua — no una tarea de "una tarde". Y, como se explica en §2, **no es donde vive el foso del producto.** Recomendación: tratarlo como mejora incremental, siempre subordinada a que el 3D ya muestre los hallazgos del motor de reglas encima del propio edificio (§4, Fase 3 meses).

### 3.2 Cerebro arquitectónico y asesor legal/urbanístico

**Lo que ya existe:** `evaluate_solar_occupation`, `evaluate_buildability`, `evaluate_max_floors`, `evaluate_ceiling_height` y `evaluate_retranqueos` (proxy geométrico simple, sin geometría real de solar) ya comprueban ocupación, edificabilidad, altura máxima y retranqueos — en el flujo de generación de proyectos (`/api/generar`). **La entrada normativa (`params["normativa"]`) es un formulario que rellena el arquitecto, no una consulta automática a planeamiento urbanístico real.**

**Lo que pide Pablo — "verificación en tiempo real de normativa urbanística (retranqueos, edificabilidad, alturas máximas)"** — ya es cierto para los NÚMEROS declarados; lo que falta es que esos números **se rellenen solos a partir de la parcela real**, exactamente el mismo tipo de trabajo que `cte_zonas.py` ya resolvió para zona climática (ciudad → zona CTE) pero aplicado a un dominio mucho más fragmentado: en España el planeamiento urbanístico es municipal, no hay una API nacional única, y las convenciones de PGOU varían de ayuntamiento a ayuntamiento. `MOAT_ANALYSIS.md` §5 ya identifica esto como "lo que necesita años" para el CTE — el urbanismo municipal es, si acaso, más fragmentado todavía.

**El "asistente que sugiere volumetrías basadas en orientación solar, viento y contexto histórico/cultural"** es una capacidad de diseño generativo distinta y más ambiciosa que la actual `ai_generator.py` (que hoy genera distribución de habitaciones desde parámetros, no masas optimizadas por criterios ambientales) — es I+D de varios trimestres, no una extensión del motor de reglas.

**Recomendación:** no prometer "verificación urbanística en tiempo real" a nivel nacional. Empezar con **un único municipio real, con datos verificados a mano** (Madrid, que ya es el terreno de pruebas de esta sesión) y aplicar la misma disciplina de honestidad que ya distingue a este proyecto (`get_missing_data_warnings`): decir explícitamente "verificado automáticamente en Madrid; en el resto de municipios, estos datos siguen siendo los que declares tú" en vez de sugerir una cobertura que no existe.

### 3.3 Sostenibilidad y evaluación de cultura arquitectónica

**Lo que ya existe:** compacidad del edificio y ratio de orientación favorable ya se evalúan como parte del Bloque 10 (Eficiencia energética) del flujo de generación. Es una base real, no cero.

**Autosuficiencia energética/eficiencia bioclimática con física real** (ganancia solar, simulación térmica) no existe y no puede construirse extendiendo `evaluator.py` — exige integrar (o construir) un motor de simulación externo, con su propio coste de validación y mantenimiento. Es comparable en escala al reto que ya describe `MOAT_ANALYSIS.md` para `chain_effects.py`: "convertirlas en cifras fiables exige partenariados o años de calibración con proyectos reales ejecutados."

**El checklist técnico de inspección en el terreno** (servidumbres, pendientes, ruido, suministros, orientación real) es, con diferencia, **la pieza de mayor valor por menor coste de las cuatro** — no requiere simulación ni datos externos automatizados, encaja directamente con el horizonte de 24 meses de `NORTH_STAR_2031.md` ("la aplicación de campo de ArchMuse para comparar lo construido contra lo aprobado") y responde a una de las frustraciones que `DESTROY_ARCHMUSE.md` §4 marca como sin resolver por nadie del sector, incluido un competidor con 50M€: "nadie cierra el círculo con la fase de obra." Empezar aquí, como checklist manual (sin verificación automática todavía), es barato y honesto.

### 3.4 Navegación y UX profesional

**Ya implementado hoy mismo** (2026-08-16, `docs/prd/2026-08-16-presets-progreso-y-zocalo-sandbox.md`): los 4 presets de direcciones destacadas y la barra de progreso con % en el Sandbox. Esta parte del pilar 4 ya no es roadmap, es producto en producción.

**"Navegación fluida estilo Mapbox 3D/Google Earth Studio"** merece una aclaración honesta: Mapbox GL JS y Google Earth Studio son, en sí mismos, productos de ingeniería de mapas dedicados (streaming de terreno, tiles vectoriales, LOD adaptativo) — igualar esa fluidez reconstruyendo primitivas propias sobre three.js vainilla (el enfoque actual del Sandbox) no es realista a corto plazo, y no es necesario reinventarlo: **ya existe `static/visor-mapa.js`, construido sobre Mapbox GL JS + Threebox, con slider de sol y "vista desde ventana" — nunca verificado en un navegador real por falta de un `MAPBOX_TOKEN`, y sin ningún botón que lo abra todavía.** El camino más barato hacia la fluidez que pide Pablo es activar y verificar ese módulo ya construido, no perseguir el mismo resultado a mano dentro del Sandbox de tres.js.

---

## 4. Roadmap por fases

*Mismo horizonte que `NORTH_STAR_2031.md` (1/3/6/12/24 meses), para que ambos documentos se lean como una sola hoja de ruta, no dos en competencia.*

### Horizonte: 1 mes — Higiene y conexión, no funcionalidad nueva vistosa

- Actualizar `CLAUDE.md` (el Bug #1 ya no aplica) y programar el refresco de `PROJECT_AUDIT.md`/`TECH_REVIEW.md` (54 commits de deriva).
- Auditar y decidir el estado de `JarvisApp.py`/`gltf_exporter.py`/`pliego_conector.py`/`pliego_extractor.py`/`estilos.py` — ¿es producto, es prototipo interno, se versiona, se retira?
- **Conectar el visor 3D a los hallazgos del motor de reglas** (resaltar sobre el propio edificio en 3D los problemas que hoy solo se ven en el plano SVG) — es la corrección más citada por `MOAT_ANALYSIS.md` y `DESTROY_ARCHMUSE.md`, y es barata comparada con cualquier otro punto de este documento.
- Conseguir un `MAPBOX_TOKEN` real y verificar `visor-mapa.js` en un navegador de verdad por primera vez.

### Horizonte: 3 meses — Primeras piezas de valor real, acotadas y honestas

- Checklist de inspección en el terreno (servidumbres, pendientes, ruido, suministros, orientación real) — manual, sin verificación automática todavía.
- Piloto de "asesor urbanístico" en **un único municipio real** (Madrid), con datos de planeamiento verificados a mano, siguiendo la misma disciplina de `cte_zonas.py` (aviso explícito cuando el dato es una suposición, nunca silencioso).
- Activar `visor-mapa.js` en el flujo real de producto (botón que lo abra) como el "modo contexto" de navegación fluida, en vez de perseguir esa fluidez dentro del Sandbox.
- Extender la evaluación de sostenibilidad ya existente (compacidad, orientación) con 2-3 métricas adicionales que no requieran simulación física (p. ej. ratio de superficie acristalada por orientación).

### Horizonte: 6 meses — Profundidad, con la misma disciplina que ya sostiene el CTE

- Ampliar el asesor urbanístico a 2-3 municipios más, con el mismo criterio de verificación manual antes de automatizar.
- Evaluar de forma seria (spike técnico, no compromiso de producto) si conviene un motor de simulación energética externo, o si el ratio actual (compacidad + orientación) basta como proxy declarado durante más tiempo.
- Primeros materiales adicionales (madera, acero) en el visor, siempre después de que la conexión 3D↔hallazgos del mes 1 esté ya en producción y verificada con clientes reales, no antes.
- DEM real de elevación — evaluarlo primero contra el mismo criterio que ya aplicó `viewer-edificio.js` (§14 de su PRD): ¿aporta valor de validación real, o es solo estética?

### Horizonte: 12 y 24 meses — Convergen con `NORTH_STAR_2031.md`

A partir de aquí este documento deja de tener una fase propia: la "profundidad normativa como cuña de entrada" (`MOAT_ANALYSIS.md`, Pilar 7) ya cubre tanto CTE como urbanismo municipal, y el horizonte de 24 meses de `NORTH_STAR_2031.md` (comprobación en tiempo real dentro de un entorno BIM, app de campo, garantía sobre hallazgos críticos) ya incorpora, de forma natural, el checklist de inspección y el asesor urbanístico como parte del mismo "pasaporte de cumplimiento" que la visión ya describe. No hace falta un segundo roadmap a partir de aquí — hace falta que los pilares 2 y 3 de este documento lleguen a ese punto con datos reales, no inventados.

---

## 5. Riesgos

- **Coste de oportunidad frente a `REFACTOR_MASTERPLAN.md`.** El horizonte de 12 meses de `NORTH_STAR_2031.md` exige arquitectura multi-tenant real (autenticación, aislamiento de datos) que hoy no existe — cualquier fase de este documento que compita por el mismo tiempo de ingeniería que esa base debe perder frente a ella, no competir en igualdad.
- **Hiperrealismo sin conexión a hallazgos profundiza, no corrige, la debilidad ya señalada dos veces** (`MOAT_ANALYSIS.md`, `DESTROY_ARCHMUSE.md`). Es el riesgo de producto más concreto de todo este documento.
- **El asesor urbanístico real es una apuesta de años de datos, no de un sprint** — prometerlo como "verificación en tiempo real" sin acotar el alcance (un municipio, verificado a mano) repite exactamente el error que `PROJECT_AUDIT.md`/`DESTROY_ARCHMUSE.md` ya señalan sobre el percentil comparativo inventado: mostrar como real un dato que no lo es.
- **Simulación energética real es una integración de motor externo**, con su propio coste de mantenimiento y validación — no un ajuste de `evaluator.py`.
- **Trabajo experimental sin auditar** (`JarvisApp.py` y compañía) puede estar compitiendo ya, hoy, por el mismo tiempo de desarrollo que cualquier fase de este roadmap, sin que este documento lo sepa — de ahí la recomendación de auditarlo en el Horizonte de 1 mes antes de comprometerse al resto.

---

## 6. Recomendación de secuencia concreta

Si solo se pudiera elegir un orden de ejecución con la información de hoy:

1. Conectar el visor 3D a los hallazgos del motor de reglas (barato, corrige la debilidad más citada por dos documentos independientes).
2. Checklist de inspección en el terreno (barato, alto valor, alineado con `NORTH_STAR_2031.md`).
3. Verificar `visor-mapa.js` con un `MAPBOX_TOKEN` real — camino más corto hacia la navegación fluida que pide Pablo.
4. Piloto de asesor urbanístico en un único municipio real y verificado (Madrid), nunca presentado como cobertura nacional.
5. Diferir hiperrealismo de materiales/iluminación global y simulación energética real hasta después de 1-4.
6. Housekeeping: actualizar `CLAUDE.md`, refrescar `PROJECT_AUDIT.md`/`TECH_REVIEW.md`, y decidir qué es `JarvisApp.py` y el resto del trabajo experimental sin versionar.

---

**Decisión:** Aprobado 2026-08-16 por Pablo — al 100%, sin recortes. Consolidado como brújula oficial del proyecto: toda propuesta nueva sobre 3D/entorno, asesor urbanístico, sostenibilidad o navegación debe evaluarse contra este documento, igual que ya exige `CLAUDE.md` para `NORTH_STAR_2031.md`/`MOAT_ANALYSIS.md`/etc. La aprobación cubre la secuencia y la honestidad de alcance de §6 — cada fase concreta (conectar 3D↔hallazgos, checklist de campo, piloto de asesor urbanístico...) sigue necesitando su propio PRD antes de tocar código de producto, por la misma regla de proceso de siempre.
